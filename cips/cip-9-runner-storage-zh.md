---
title: "CIP-9: Runner 可挂载存储"
description: 为临时性 Runner 作业挂载持久加密卷的协议定义
icon: hard-drive
---

<Note>
  **状态：** 内部评审草案
  **类型：** 标准追踪
  **类别：** 核心
  **创建日期：** 2026-03-18
  **依赖：** CIP-2（链下计算）、CIP-3（费用模型）
</Note>

<Tip>
  CIP-9 定义了为临时性 Runner 作业挂载持久加密存储卷的链上控制面与跨组件接口协议。存储数据面由独立的 `steamtrain-client` 库实现。CIP-10（容器运行时）在本 CIP 基础上构建。
</Tip>

# CIP-9: Runner 可挂载存储

---

## 摘要

Cowboy 链下计算系统（CIP-2）中的 Runner 在设计上是无状态的——每个作业在隔离环境中执行并在完成后终止。这对以下使用场景形成了缺口：在不将数据暴露上链的情况下存储 API 密钥和证书；积累超出链上存储限制（64 KiB 内联上限，白皮书 §7）的大型产出物（二进制、数据集、日志）；在多步骤工作流中的 Runner 之间传递中间状态；以及为长期运行的容器化服务（CIP-10）维护数据库或缓存状态。

本 CIP 引入 **Runner 可挂载存储**：一种为 Runner 作业挂载加密持久卷的协议。链上层负责访问控制、授权凭证（CapToken）签发以及清单根锚定，用于全局共识的数据完整性保障。链下存储数据面由 **Steamtrain** 实现——一个以 POSIX FUSE 文件系统形式暴露给 Runner 的分布式加密存储引擎。

---

## 动机

本设计解决以下四个核心痛点：

1. **密钥管理。** Runner 需要访问 API 密钥、证书和凭证，同时不将其暴露到公共链上。这些机密信息只能被授权 Runner 解密，并可选择性地通过 TEE 认证进行门控。

2. **链下输出。** 计算过程经常产生超过链上 64 KiB 内联限制（白皮书 §7）的产出物。这些产出物必须链下存储，并在链上锚定可验证的内容承诺。

3. **工具链数据流。** 多 Runner 工作流（如 OpenClaw 工具管道）需要在顺序执行的 Runner 之间传递大量中间数据，而无需经由链进行中转。

4. **容器持久化。** CIP-10 容器运行时需要持久存储层，以支持跨作业重启的有状态应用程序、数据库和缓存。

---

## 规范

### 1. 系统 Actor：卷注册表（`0x0000…0009`）

卷注册表是地址为 `0x0000000000000000000000000000000000000009` 的系统 Actor，负责管理存储卷的生命周期、签发 Runner 访问所需的 CapToken，以及记录清单根锚定。

它与现有 Runner 子系统 Actor 共同构成：

| 地址 | 系统 Actor | 职责 |
|------|-----------|------|
| `0x0000…0001` | Runner 注册表 | Runner 质押与能力声明 |
| `0x0000…0002` | 作业分发器 | 作业生命周期与 VRF 选择 |
| `0x0000…0003` | 结果验证器 | 结果验证与回调 |
| `0x0000…0009` | **卷注册表** | 卷生命周期、CapToken 签发、清单锚定 |

### 2. 核心类型

#### 2.1 VolumeId

```rust
/// 全局唯一卷标识符。
/// 计算方式：keccak256(owner_address || nonce_le8)
pub type VolumeId = [u8; 32];
```

#### 2.2 VolumeMode（访问模式）

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VolumeMode {
    /// 完整读写访问。
    ReadWrite,
    /// 仅写访问（Runner 可写入但无法读取已有数据）。
    /// 适用于输出收集场景，不需要读取历史状态。
    WriteOnly,
    /// 只读访问（Runner 可读但不可修改）。
    ReadOnly,
}
```

#### 2.3 VolumeMetadata（卷元数据）

存储于卷注册表 Actor 的存储中，键为 `volume:{volume_id}`：

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumeMetadata {
    pub volume_id: VolumeId,
    /// 所有者地址——唯一可以授予/撤销访问权限及删除卷的方。
    pub owner: Address,
    /// 新签发 CapToken 的默认访问模式（可在每次授权时覆盖）。
    pub default_mode: VolumeMode,
    /// 卷创建时的区块高度。
    pub created_at: u64,
    /// 最近一次在链上锚定的清单根（32 字节，算法无关）。
    /// 在首次提交 VolumeAnchorManifest 之前为 `None`。
    pub manifest_root: Option<[u8; 32]>,
    /// 最近一次清单锚定时的区块高度。
    pub manifest_anchored_at: Option<u64>,
    /// 卷是否已被标记为删除（软删除，等待 GC）。
    pub deleted: bool,
}
```

存储键格式：`b"vol:" || volume_id`（36 字节）。

#### 2.4 CapToken（能力凭证）

CapToken 是一种短期bearer 凭证，授予特定 Runner 挂载特定卷的权限。它由卷所有者使用 **secp256k1**（白皮书 §1.1 中所有外部账户使用的同一密钥类型）签名，使 Steamtrain 存储层无需链上往返即可验证。

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapToken {
    /// 唯一凭证 ID：keccak256(volume_id || grantee || expires_at_le8 || nonce_le8)
    pub token_id: [u8; 32],
    /// 本凭证授权访问的卷。
    pub volume_id: VolumeId,
    /// 被授权使用本凭证的 Runner 地址。
    /// 必须与 Runner 注册表（0x01）中该 Runner 的注册地址一致。
    pub grantee: Address,
    /// 本凭证授予的访问模式。
    pub mode: VolumeMode,
    /// 本凭证在此区块高度后失效。
    /// 签发时必须 > 当前区块高度。建议值：当前高度 + 1000。
    pub expires_at_block: u64,
    /// 每 (owner, volume) 对的单调递增计数器，防止重放攻击。
    pub nonce: u64,
    /// 对以上所有字段的规范序列化（commonware_codec 二进制编码，字段顺序同声明顺序）
    /// 的 secp256k1 可恢复 ECDSA 签名。
    /// 签名密钥必须是卷所有者的密钥（recovered_address == owner）。
    pub signature: [u8; 65],
}
```

**CapToken 验证**（由 Steamtrain 执行，非链上）：
1. 从 `signature` 中恢复签名者地址（对除签名字段外所有字段的规范编码）。
2. 断言 `recovered_address == volume_owner`（通过链上卷注册表查询）。
3. 断言 `current_block <= expires_at_block`（从节点 RPC 获取当前区块）。
4. 断言 `grantee == presenting_runner_address`。
5. 断言卷的 `manifest_root` 条目存在（卷已初始化）。

CapToken 在卷注册表中的存储键：`b"cap:" || token_id`（36 字节）——用于撤销查询。

#### 2.5 VolumeMount（卷挂载声明）

在 `JobSpec` 中声明作业所需的卷：

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumeMount {
    /// 要挂载的卷。
    pub volume_id: VolumeId,
    /// 授权本 Runner 挂载该卷的 CapToken。
    /// 由作业提交者（Actor）在提交作业前通过 VolumeGrantAccess 签发。
    pub cap_token: CapToken,
    /// 卷在 Runner 环境中的挂载路径。
    /// 必须以 `/mnt/` 开头。例如：`/mnt/steamtrain` 或 `/mnt/secrets`。
    pub mount_path: String,
}
```

### 3. JobSpec 扩展

`JobSpec`（定义于 `runner-common`）新增可选的卷挂载列表。该字段使用 `serde(default)` 以完全向后兼容现有序列化的作业规格。

```rust
pub struct JobSpec {
    // ... 所有现有字段保持不变 ...

    /// 作业执行前挂载的卷（CIP-9）。
    /// 默认为空；向后兼容。
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub volume_mounts: Vec<VolumeMount>,
}
```

作业分发器（0x02）**必须**验证：
- 每个 `CapToken.grantee` 与选定 Runner 的地址匹配。
- 每个 `CapToken.expires_at_block > submitted_at_block + timeout_blocks`（凭证在作业可能完成之前不能过期）。
- 对应卷在卷注册表中存在且未被删除。

### 4. 系统指令（40–49）

CIP-9 新增六个 `SystemInstruction` 变体，分发至卷注册表（0x09）。指令编号 40–49 为卷操作保留。

```rust
pub enum SystemInstruction {
    // ... 现有指令 0–35 ...

    // ── CIP-9: 卷指令（40–49）────────────────────────────────────────────────

    /// 创建新卷。
    /// 调用者成为卷所有者。
    /// 触发事件：VolumeCreated { volume_id, owner }
    VolumeCreate {
        /// 卷的默认访问模式。
        default_mode: VolumeMode,
        /// 用于卷 ID 推导的任意调用者字节（可为空）。
        salt: Vec<u8>,
    },                                                              // 40

    /// 签发 CapToken，授予 Runner 对卷的访问权限。
    /// 仅卷所有者可调用。
    /// 触发事件：VolumeAccessGranted { volume_id, grantee, token_id, expires_at_block }
    VolumeGrantAccess {
        volume_id: VolumeId,
        /// 被授权访问的 Runner 地址。
        grantee: Address,
        /// 本凭证的访问模式（可与卷的 default_mode 不同）。
        mode: VolumeMode,
        /// 凭证有效期（从提交区块起算的区块数）。
        /// 必须在 [10, 10_000] 范围内。建议值：1000。
        duration_blocks: u64,
    },                                                              // 41

    /// 在过期前撤销已签发的 CapToken。
    /// 仅卷所有者可调用。
    /// 触发事件：VolumeAccessRevoked { token_id }
    VolumeRevokeAccess {
        token_id: [u8; 32],
    },                                                              // 42

    /// 在链上锚定 Steamtrain 清单根。
    /// 由 Runner 在作业完成后调用（通常与 JobResultSubmit 捆绑提交）。
    /// 调用者必须持有未过期且访问模式为 ReadWrite 或 WriteOnly 的有效 CapToken。
    /// 触发事件：VolumeManifestAnchored { volume_id, manifest_root, anchored_by, height }
    VolumeAnchorManifest {
        volume_id: VolumeId,
        /// Steamtrain 卷 Merkle 树的 32 字节内容寻址根。
        /// 算法无关：以不透明字节存储。Steamtrain 内部使用 BLAKE3。
        manifest_root: [u8; 32],
        /// 授权本次更新的 CapToken（必须具有 ReadWrite 或 WriteOnly 模式）。
        cap_token_id: [u8; 32],
    },                                                              // 43

    /// 删除卷（软删除；存储 GC 在链下执行）。
    /// 仅卷所有者可调用。
    /// 触发事件：VolumeDeleted { volume_id }
    VolumeDelete {
        volume_id: VolumeId,
    },                                                              // 44

    /// 将卷所有权转移给新地址。
    /// 仅当前所有者可调用。
    /// 触发事件：VolumeOwnershipTransferred { volume_id, old_owner, new_owner }
    VolumeTransferOwnership {
        volume_id: VolumeId,
        new_owner: Address,
    },                                                              // 45

    // 46–49 为未来卷操作保留
}
```

### 5. 卷生命周期

```
Actor 调用 VolumeCreate
    │
    ▼
卷注册表（0x09）
    ├── 推导 volume_id = keccak256(caller || nonce_le8 || salt)
    ├── 存储 VolumeMetadata { owner=caller, manifest_root=None, ... }
    └── 触发 VolumeCreated

Actor 调用 VolumeGrantAccess(volume_id, runner_addr, mode, duration)
    │
    ▼
卷注册表
    ├── 断言 caller == volume.owner
    ├── 推导 token_id = keccak256(volume_id || grantee || expires_at_le8 || nonce_le8)
    ├── 用所有者的链上签名密钥（secp256k1）签署 CapToken
    ├── 在注册表中存储 CapToken（用于撤销查询）
    ├── 将 CapToken 字节返回给调用者
    └── 触发 VolumeAccessGranted

Actor 调用 JobSubmit(job_spec, volume_mounts=[{ volume_id, cap_token, "/mnt/data" }])
    │
    ▼
作业分发器（0x02）
    ├── 验证 CapToken 字段（grantee 与选定 Runner 匹配，未过期）
    ├── 在作业分配消息中将 CapToken 字节包含发给 Runner
    └── 继续执行 VRF 选择（CIP-2 §5）

Runner 收到分配的作业
    ├── 链下验证 CapToken 签名（对照卷注册表数据）
    ├── 调用 Steamtrain：mount_volume(cap_token, "/mnt/data")
    ├── 执行作业处理程序（读写 /mnt/data）
    └── 调用 Steamtrain：unmount_volume(volume_id) → 返回 manifest_root: [u8; 32]

Runner 提交结果
    ├── JobResultSubmit（CIP-2）
    └── VolumeAnchorManifest(volume_id, manifest_root, cap_token_id)  ← 原子或顺序提交
```

### 6. Steamtrain 客户端接口

Steamtrain 存储引擎以**独立的 `steamtrain-client` crate**（独立库）形式实现。CIP-9 定义了它必须实现的接口 trait。这将 Runner 运行时与具体的 Steamtrain 实现解耦，并允许未来接入替代存储后端。

```rust
/// 由 `steamtrain-client` crate 实现。
/// 在作业执行前后由 Runner 调用。
#[async_trait]
pub trait VolumeProvider: Send + Sync {
    /// 将卷挂载到本地文件系统的指定路径。
    /// 挂载前在链下验证 CapToken。
    /// 返回当前清单根（写入前的状态）。
    async fn mount_volume(
        &self,
        cap_token: &CapToken,
        mount_path: &str,
    ) -> Result<[u8; 32], StorageError>;

    /// 卸载卷并刷新所有待处理的写入。
    /// 返回反映自挂载以来所有写入的新清单根。
    async fn unmount_volume(
        &self,
        volume_id: &VolumeId,
    ) -> Result<[u8; 32], StorageError>;

    /// 在不挂载的情况下验证 CapToken（用于作业前验证）。
    async fn verify_cap_token(
        &self,
        cap_token: &CapToken,
        current_block: u64,
        volume_owner: &Address,
    ) -> Result<(), StorageError>;
}

/// 授权钩子——由 Runner 实现，用于验证 CapToken。
/// 在初始化时提供给 Steamtrain 引擎。
#[async_trait]
pub trait AuthProvider: Send + Sync {
    async fn validate(
        &self,
        token: &CapToken,
        presenting_runner: &Address,
        current_block: u64,
    ) -> Result<VolumeClaims, StorageError>;
}

/// 从已验证 CapToken 中提取的声明。
pub struct VolumeClaims {
    pub volume_id: VolumeId,
    pub mode: VolumeMode,
    pub expires_at_block: u64,
}

/// 共识钩子——由节点实现，用于锚定清单根。
/// 由 Steamtrain 在存储节点间完成两阶段提交共识后调用。
#[async_trait]
pub trait AuthoritativeStore: Send + Sync {
    /// 在链上锚定清单根。
    /// 返回 VolumeAnchorManifest 指令的交易哈希。
    async fn commit_manifest_root(
        &self,
        volume_id: &VolumeId,
        manifest_root: [u8; 32],
        cap_token_id: [u8; 32],
    ) -> Result<[u8; 32], StorageError>;  // 返回 tx_hash
}

/// 卷生命周期钩子——用于元数据管理和 GC。
#[async_trait]
pub trait ManifestRegistry: Send + Sync {
    async fn get_volume_metadata(&self, volume_id: &VolumeId) -> Result<VolumeMetadata, StorageError>;
    async fn prune_expired_tokens(&self, before_block: u64) -> Result<u64, StorageError>;
}

#[derive(Debug, thiserror::Error)]
pub enum StorageError {
    #[error("无效的 CapToken：{reason}")]
    InvalidCapToken { reason: String },
    #[error("卷不存在：{volume_id:?}")]
    VolumeNotFound { volume_id: VolumeId },
    #[error("挂载失败：{reason}")]
    MountFailed { reason: String },
    #[error("权限拒绝：{reason}")]
    PermissionDenied { reason: String },
    #[error("网络错误：{0}")]
    Network(String),
}
```

**仓库结构：**

```
steamtrain-client/          ← 新独立 crate（本 CIP 定义）
  src/
    lib.rs                  ← 重新导出 trait 和类型
    traits.rs               ← VolumeProvider、AuthProvider、AuthoritativeStore、ManifestRegistry
    types.rs                ← CapToken、VolumeMount、VolumeMode、StorageError（与 runner-common 共享）
    fuse.rs                 ← 由 Steamtrain 引擎支持的 FUSE 挂载实现
    quic.rs                 ← 与 Steamtrain 存储节点的 QUIC 传输
    crypto.rs               ← CapToken 签名验证（secp256k1）
```

该 crate 仅作为 `runner` 工作空间的依赖添加。`node` crate 不依赖它。

### 7. Gas 费用

Gas 费用是共识关键数据。所有值按照 CIP-3 双计量模型以 Cycles 和 Cells 为单位。

| 指令 | Cycles | Cells | 说明 |
|------|--------|-------|------|
| `VolumeCreate` | 5,000 | 500 | 存储约 200 字节的 VolumeMetadata |
| `VolumeGrantAccess` | 3,000 | 150 | 存储 CapToken + 触发事件 |
| `VolumeRevokeAccess` | 1,000 | 50 | 标记凭证已撤销 |
| `VolumeAnchorManifest` | 1,000 | 32 | 存储 32 字节清单根 |
| `VolumeDelete` | 500 | 0 | 仅设置软删除标志 |
| `VolumeTransferOwnership` | 1,000 | 50 | 更新 owner 字段 |
| CapToken 验证（每次挂载，作业前）| 500 | 0 | 链下 secp256k1 验证；无链上费用 |

**链下存储定价**不计入 Gas 计量。Steamtrain 运营方在链下公示定价（每字节每周期的 CBY），类比 Runner 费率卡。Actor 在创建卷时预付存储费用（托管模式）。此模型与白皮书 §17.7（Runner 市场链下定价）一致。

### 8. 权利集成

CIP-9 为权利系统（CIP-2 §7）扩展了新的 `Scope` 和 `Action` 变体，以实现卷访问策略的链上治理：

```rust
// 对 cowboy_types::entitlement 的扩展

pub enum Scope {
    // ... 现有变体 ...
    /// 限定于特定存储卷的范围。
    Volume(VolumeId),
}

pub enum Action {
    // ... 现有变体 ...
    /// 对卷的读取访问。
    VolumeRead(VolumeId),
    /// 对卷的写入访问。
    VolumeWrite(VolumeId),
    /// 对卷的完整读写访问。
    VolumeReadWrite(VolumeId),
}
```

这允许通过权利注册表（0x07）治理卷访问，适用于企业或合规场景，作为 CapToken 直接流程之外的补充机制。当作业设置了 `required_runner_pool`（CIP-2 §7.3）时，作业分发器可额外验证选定 Runner 是否持有相关卷权利。

### 9. 向后兼容性

- `JobSpec.volume_mounts` 使用 `#[serde(default)]`——所有现有作业规格仍然有效，挂载列表默认为空。
- 新指令 40–49 与现有任何指令编号不冲突。
- 地址 `0x09` 处的卷注册表系统 Actor 是新地址；现有 Actor 未使用。
- 未依赖 `steamtrain-client` 的 Runner 可安全忽略 `volume_mounts`（若带有挂载卷的作业被分配给它们，将在挂载时报告 JobFault，而非共识失败）。

### 10. 安全考量

**CapToken 伪造。** CapToken 由卷所有者通过 secp256k1 签名。伪造凭证需要攻破 secp256k1 上的 ECDSA，这在所有外部账户已依赖的安全假设下（白皮书 §1.1）被认为不可行。

**重放攻击。** CapToken 中的 `nonce` 字段对每个 `(owner, volume)` 对单调递增。卷注册表追踪最后签发的 nonce；旧凭证的重放可被检测并拒绝。

**凭证过期篡改。** Runner 无法延长 CapToken 的有效期——`expires_at_block` 在签发时固定，并由所有者签名覆盖。作业分发器在提交时验证过期时间。

**清单根欺骗。** 只有持有 ReadWrite 或 WriteOnly 模式有效 CapToken 的持有者才能提交 `VolumeAnchorManifest`。卷注册表验证 CapToken ID 是否在其存储中且未被撤销。

**存储可用性。** Steamtrain 的纠删码（K 数据分片 + M 奇偶校验分片，Reed-Solomon）确保即使 M 个存储节点同时故障，卷仍可访问。这是链下持久性保证；链上协议不验证分片可用性。

**客户端加密保证。** 数据在离开 Runner 前使用 AES-256-GCM 加密。存储节点从不收到明文。加密密钥是临时的，由 `steamtrain-client` crate 管理。加密密钥丢失意味着数据永久丢失——Actor 负责密钥管理。

**通过卷垃圾邮件进行 DoS。** `VolumeCreate` 需要 5,000 Cycles + 500 Cells，从经济上抑制了批量创建卷。每个 Actor 的活跃卷上限为 **256** 个（治理可调），防止卷注册表 Actor 状态膨胀。

---

## 设计理由

**为何使用独立的 `steamtrain-client` crate？** Steamtrain 引擎是一个独立子系统，有其自己的发布周期、存储节点网络和运维需求。将其耦合到 Runner 二进制文件中会产生难以维护的依赖关系。基于 trait 的接口（类比 Runner 通过 RPC 与节点交互的方式）使 Runner 可以保持存储后端无关性。

**为何使用 CapToken 而非直接使用链上权利？** 链上权利检查需要在卷挂载时（作业执行时）进行链上往返。CapToken 在作业提交前预签发，携带在 `JobSpec` 中，并由 Steamtrain 在链下验证——在关键路径上增加零延迟。链上权利作为长期访问策略的治理层保留。

**为何在链上锚定清单根？** 没有链上锚定，就没有全局一致、防篡改的卷数据记录。任何方都可以独立验证卷的完整性：从链上获取清单根，与 Steamtrain 内容哈希比较——与 blob 多哈希引用相同的信任模型（白皮书 §7.2）。

**为何 `VolumeAnchorManifest` 独立于 `JobResultSubmit`？** 一个作业可能挂载多个卷，但只对其中部分进行写入。锚定是按卷进行的，且仅在使用了写入权限的凭证时才需要。保持独立性有助于可组合性，避免修改现有的 `JobResultSubmit` 指令。Runner 应当在同一交易中提交两者，以保持结果和存储状态的原子性。

---

## 参数（创世默认值）

| 参数 | 值 | 治理可调 |
|------|-----|---------|
| `max_volumes_per_actor` | 256 | 是 |
| `cap_token_min_duration_blocks` | 10 | 是 |
| `cap_token_max_duration_blocks` | 10,000 | 是 |
| `cap_token_recommended_duration_blocks` | 1,000 | 否 |
| `volume_registry_actor` | `0x0000…0009` | 否 |
| `max_cap_tokens_per_volume` | 64 | 是 |
| `manifest_root_bytes` | 32 | 否 |
