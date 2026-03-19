---
title: "CIP-10: 容器运行时"
description: 将 OCI 兼容容器镜像作为可验证链下计算作业执行的协议定义
icon: container
---

<Note>
  **状态：** 内部评审草案
  **类型：** 标准追踪
  **类别：** 核心
  **创建日期：** 2026-03-18
  **依赖：** CIP-2（链下计算）、CIP-3（费用模型）、CIP-9（Runner 可挂载存储）
</Note>

<Tip>
  CIP-10 在 CIP-2 基础上新增原生容器执行模式。Runner 在 Linux 命名空间沙箱中执行 OCI 兼容镜像。CIP-9 卷为跨容器重启提供持久文件系统状态。容器镜像注册表（系统 Actor `0x0A`）管理已授权镜像的链上许可列表。
</Tip>

# CIP-10: 容器运行时

---

## 摘要

本 CIP 为 Cowboy 链下计算系统（CIP-2）指定了容器执行模式。现有作业类型（`Llm`、`Http`、`Mcp`、`Custom`）涵盖了明确边界的请求-响应型工作负载，而大量计算任务——ML 流水线阶段、数据变换作业、多二进制工作流、有状态微服务——需要具备完整 OS 级隔离的原生执行环境。基于 OCI（开放容器倡议）镜像规范的容器模型恰好能提供这一切：可复现的、内容寻址的执行单元，具有成熟的资源隔离语义。

CIP-10 引入：

- `Container` `JobType` 变体及用于描述容器作业参数的 `ContainerSpec` 结构体。
- **容器镜像注册表**（系统 Actor `0x0000…000A`），维护已验证镜像哈希的链上许可列表，防止执行任意或被篡改的镜像。
- Runner 端的生命周期协议，涵盖镜像拉取、验证、沙箱化和执行，并与 CIP-9 卷挂载完整集成。
- `RateCard` 扩展，用于 Runner 声明容器执行能力。

---

## 动机

本设计的四个驱动场景：

1. **原生工具链执行。** 许多数据处理工作负载需要无法用 Python Actor 或 HTTP 调用表达的编译型二进制文件（ffmpeg、ImageMagick、自定义 CLI 工具）。将其打包为 OCI 镜像提供了通用的分发机制。

2. **可复现 ML 推理。** 推理运行时（vLLM、Triton、ONNX Runtime）以容器镜像形式分发，具有已知的摘要值。在 `ContainerSpec` 中固定 `image_hash` 使执行环境成为协议级作业规格的一部分，可被所有方验证。

3. **多 Runner 流水线。** 工具管道（如 OpenClaw）顺序链接多个 Runner。CIP-9 卷在各阶段之间传递中间数据。容器镜像可以使用任意语言和依赖实现流水线阶段，与 Runner 自身的运行时解耦。

4. **有状态服务。** 长期运行的进程（数据库服务器、缓存层）同时需要持久存储（CIP-9）和进程级隔离。容器运行时提供隔离；本 CIP 提供协议绑定。

---

## 规范

### 1. 系统 Actor：容器镜像注册表（`0x0000…000A`）

容器镜像注册表是地址为 `0x000000000000000000000000000000000000000A` 的系统 Actor，维护已授权容器镜像哈希的链上许可列表。Runner **不得**执行哈希未在注册表中存在的镜像（除非作业提交者通过显式设置 `allow_unregistered: true` 标志，且该标志要求 TEE 认证，见 §9.3）。

| 地址 | 系统 Actor | 职责 |
|------|-----------|------|
| `0x0000…0001` | Runner 注册表 | Runner 质押与能力声明 |
| `0x0000…0002` | 作业分发器 | 作业生命周期与 VRF 选择 |
| `0x0000…0009` | 卷注册表 | 卷生命周期、CapToken 签发、清单锚定 |
| `0x0000…000A` | **容器镜像注册表** | 镜像哈希许可列表、策略管理 |

#### 1.1 ImageEntry（镜像条目）

存储键 `b"img:" || image_hash`（36 字节）：

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageEntry {
    /// OCI 镜像清单的 32 字节内容哈希。
    pub image_hash: [u8; 32],
    /// 生成 `image_hash` 所用的哈希算法。
    pub hash_algo: ImageHashAlgo,
    /// 可读名称/版本标签。不用于验证——仅供参考。
    pub label: String,
    /// 本条目注册时的区块高度。
    pub registered_at: u64,
    /// 注册本镜像的地址。
    pub registrant: Address,
    /// 本镜像当前是否允许执行。
    pub active: bool,
    /// 控制哪些 Runner 可执行本镜像的可选策略。
    pub policy: Option<ImagePolicy>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ImageHashAlgo {
    /// SHA-256（OCI/Docker 标准默认）
    Sha256,
    /// BLAKE3（Steamtrain 和 Cowboy 存储原语使用）
    Blake3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ImagePolicy {
    /// 任何已注册的 Runner 均可执行本镜像。
    AnyRunner,
    /// 仅持有有效 TEE 认证的 Runner 可执行本镜像。
    TeeRequired,
    /// 仅指定权利池中的 Runner 可执行本镜像。
    EntitlementPool { pool_id: [u8; 32] },
}
```

### 2. 核心类型

#### 2.1 ContainerSpec（容器规格）

容器作业的完整规格，嵌入于 `JobType::Container` 中。

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerSpec {
    /// OCI 镜像内容哈希。
    /// 必须与容器镜像注册表（0x0A）中已注册的活跃 `ImageEntry` 匹配，
    /// 除非 `allow_unregistered` 为 true（需要 TEE 认证，见 §9.3）。
    pub image_hash: [u8; 32],
    /// `image_hash` 的哈希算法。
    #[serde(default)]
    pub image_hash_algo: ImageHashAlgo,
    /// 用于拉取的可选 OCI 镜像引用（如 "docker.io/library/python:3.12"）。
    /// Runner 将其作为定位镜像的提示；哈希是权威身份标识。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub image_ref: Option<String>,
    /// 覆盖镜像默认的 ENTRYPOINT。
    /// 若为空，使用镜像声明的入口点。
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub entrypoint: Vec<String>,
    /// 传递给入口点的参数。
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub args: Vec<String>,
    /// 以 (KEY, value) 对形式追加的环境变量。
    /// 与镜像默认 ENV 声明合并（可覆盖）。
    /// 禁止包含机密信息——请使用挂载到已知路径的 CIP-9 卷。
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub env: Vec<(String, String)>,
    /// 由 Runner 通过 cgroup v2 强制执行的资源限制。
    pub limits: ContainerLimits,
    /// 容器内的工作目录。
    /// 默认为镜像声明的 WORKDIR，若未设置则为 `/`。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub working_dir: Option<String>,
    /// 若为 true，允许执行未在容器镜像注册表中注册的镜像。
    /// 需要 Runner 的 TEE 认证（见 §9.3）。默认：false。
    #[serde(default)]
    pub allow_unregistered: bool,
}

impl Default for ImageHashAlgo {
    fn default() -> Self {
        ImageHashAlgo::Sha256
    }
}
```

#### 2.2 ContainerLimits（资源限制）

由 Runner 通过 cgroup v2 + Linux 命名空间强制执行的资源限制。这些值与 Runner 的 `RateCard` 协商（见 §6）。

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerLimits {
    /// 最大常驻内存（字节）。
    /// 通过 cgroup v2 `memory.max` 强制执行。默认：512 MiB。
    #[serde(default = "ContainerLimits::default_memory")]
    pub memory_bytes: u64,
    /// CPU 配额（毫核，1000 = 1 个物理核心）。
    /// 通过 cgroup v2 `cpu.max`（配额/周期）强制执行。默认：1000。
    #[serde(default = "ContainerLimits::default_cpu")]
    pub cpu_millicores: u32,
    /// 最大挂钟执行时间（秒）。
    /// 超时后容器将被 SIGKILL。默认：60。
    /// 必须 ≤ 作业的 `ResourceBounds.max_wall_time_seconds`。
    #[serde(default = "ContainerLimits::default_timeout")]
    pub timeout_secs: u32,
    /// 最大临时层磁盘使用量（字节，仅限容器文件系统写入）。
    /// 不包含 CIP-9 卷挂载（有独立配额）。
    /// 通过 overlayfs 配额或 dm-thin 强制执行。默认：1 GiB。
    #[serde(default = "ContainerLimits::default_disk")]
    pub disk_bytes: u64,
    /// 容器内最大 PID 数量。
    /// 通过 cgroup v2 `pids.max` 强制执行。默认：512。
    #[serde(default = "ContainerLimits::default_pids")]
    pub pids_max: u32,
}

impl ContainerLimits {
    fn default_memory() -> u64 { 512 * 1024 * 1024 }     // 512 MiB
    fn default_cpu() -> u32 { 1000 }                       // 1 核
    fn default_timeout() -> u32 { 60 }                     // 60 秒
    fn default_disk() -> u64 { 1024 * 1024 * 1024 }       // 1 GiB
    fn default_pids() -> u32 { 512 }
}
```

### 3. JobType 扩展

`JobType`（定义于 `runner-common`）新增 `Container` 变体：

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum JobType {
    // ... 现有变体（Llm、Http、Mcp、Custom）保持不变 ...

    /// 执行 OCI 容器镜像（CIP-10）。
    Container {
        /// 完整的容器执行规格。
        spec: ContainerSpec,
    },
}
```

该变体的 `#[serde(tag = "type")]` 判别符为 `"Container"`，与现有 Rust 枚举 serde 约定一致。

### 4. JobSpec 扩展

`JobSpec` 已通过 CIP-9 携带 `volume_mounts: Vec<VolumeMount>`。CIP-10 无需对 `JobSpec` 进行结构性修改——容器规格嵌入于 `JobType::Container` 内部。但对容器作业新增以下验证规则：

**作业分发器（0x02）必须：**
1. 验证 `spec.image_hash` 在容器镜像注册表（0x0A）中作为活跃条目存在，或 `spec.allow_unregistered == true` 且作业元数据中包含有效 TEE 认证。
2. 验证选定 Runner 的 `RateCard.supported_job_types` 包含 `"Container"`。
3. 验证 `spec.limits.timeout_secs ≤ job.bounds.max_wall_time_seconds`。
4. 应用所有 CIP-9 `VolumeMount` 验证（CapToken 被授权方、过期时间、卷存在性）。

**Runner 必须：**
1. 拉取后（§5.3）在执行前验证镜像哈希。
2. 通过 cgroup v2 强制执行所有 `ContainerLimits`。
3. 将 CIP-9 卷挂载到容器命名空间中声明的 `mount_path`。

### 5. Runner 容器生命周期

Runner 对 `Container` 作业执行以下序列。每个步骤均为强制；任意步骤失败将导致 `JobFault`（CIP-2 §6.4）而非 `JobResult`。

```
 1. 接收 作业分配（CIP-2 §5）
    │
 2. 验证 容器规格
    │  ├── 通过节点 RPC 检查镜像哈希是否在容器镜像注册表（0x0A）中
    │  ├── 检查 Runner 自身能力（OCI 运行时是否可用）
    │  └── 对照 Runner 的 RateCard 验证 ContainerLimits
    │
 3. 拉取 镜像
    │  ├── 检查本地镜像缓存（以 image_hash 为键）
    │  ├── 若未缓存：从 image_ref（OCI 仓库）或对等 Runner 获取
    │  └── 验证拉取的清单哈希 == spec.image_hash（不匹配则中止）
    │
 4. 挂载 CIP-9 卷（对 job_spec.volume_mounts 中的每个 VolumeMount）
    │  ├── 链下验证 CapToken 签名（VolumeProvider::verify_cap_token）
    │  └── steamtrain_client.mount_volume(cap_token, mount_path)
    │
 5. 准备 沙箱
    │  ├── 创建 Linux 命名空间：user、mount、pid、uts、ipc
    │  │   （网络命名空间：默认隔离——无法访问互联网，
    │  │    除非 Runner 持有本作业的网络权利，CIP-2 §7）
    │  ├── 配置 overlayfs：lower=镜像层，upper=临时读写层
    │  ├── 将 CIP-9 卷 FUSE 挂载点绑定挂载到容器 mount 命名空间
    │  ├── 应用 cgroup v2 限制（memory、cpu、pids、io）
    │  └── 设置 UID/GID 映射（user 命名空间：容器 root → 非特权宿主 UID）
    │
 6. 执行
    │  ├── 启动容器进程：entrypoint + args、env、working_dir
    │  ├── 捕获 stdout/stderr（管道，各最多 1 MiB）
    │  └── 等待：进程退出 或 timeout_secs 截止时间（超时则 SIGKILL）
    │
 7. 收集 输出
    │  ├── exit_code: i32
    │  ├── stdout: Vec<u8>（截断至 1 MiB）
    │  └── stderr: Vec<u8>（截断至 64 KiB，仅供诊断）
    │
 8. 卸载 CIP-9 卷（对每个已挂载的卷）
    │  └── steamtrain_client.unmount_volume(volume_id) → manifest_root: [u8; 32]
    │
 9. 提交 结果（尽量在单笔交易中）
    │  ├── JobResultSubmit（CIP-2 §6.3）：{ exit_code, stdout, stderr_hash }
    │  └── VolumeAnchorManifest（CIP-9 §4，指令 43）：每个写入卷提交一次
```

#### 5.1 输出编码

容器作业结果编码为 `ContainerOutput`：

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerOutput {
    /// 进程退出码。0 = 成功。非零 = 应用层失败。
    pub exit_code: i32,
    /// 捕获的 stdout，最多 1 MiB。推荐 UTF-8，但不强制。
    pub stdout: Vec<u8>,
    /// 完整 stderr 流的 BLAKE3 哈希（如需要可链下存储）。
    pub stderr_hash: [u8; 32],
    /// 挂钟执行时长（毫秒）。
    pub duration_ms: u64,
    /// 峰值常驻内存使用量（字节）。
    pub peak_memory_bytes: u64,
}
```

`stdout` 载荷用作验证目的的规范作业输出（CIP-2 §6.2）。非零 `exit_code` 被结果验证器（0x03）视为作业失败，除非 Actor 的回调明确处理了该情况。

#### 5.2 镜像缓存管理

Runner 维护本地 OCI 层缓存，以 `(image_hash, hash_algo)` 为键。缓存层在多个作业间共享。当缓存超过 Runner 配置的上限时应用 LRU 淘汰策略（非协议规定；Runner 本地配置）。Runner **不得**淘汰当前正在被执行中容器使用的层。

#### 5.3 哈希验证

拉取镜像后，Runner 重新计算 OCI 镜像清单 JSON 的哈希，并与 `spec.image_hash` 进行比对。所用算法由 `spec.image_hash_algo` 指定：

- **Sha256**：`sha256(manifest_json_bytes)`——与 `docker pull`/`skopeo` 标准 `sha256:` 摘要兼容。
- **Blake3**：`blake3(manifest_json_bytes)`——速度更快，与 Steamtrain 内部哈希一致。

若计算出的哈希与 `spec.image_hash` 不匹配，Runner **不得**启动容器，**必须**报告 `reason: ImageHashMismatch` 的 `JobFault`。

### 6. RateCard 扩展

`RateCard`（定义于 `runner/types.rs`，在 CIP-2 C-1 中扩展）新增容器能力声明字段：

```rust
pub struct RateCard {
    // ... 所有现有字段 ...

    /// 本 Runner 是否支持 CIP-10 容器作业执行。
    /// 默认：false（Runner 显式选择加入）。
    #[serde(default)]
    pub supports_containers: bool,

    /// 本 Runner 将接受的最大 ContainerLimits。
    /// 超过这些值的作业在分发时被拒绝。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub container_limits: Option<ContainerCapacity>,

    /// 本 Runner 支持的 OCI 镜像拉取来源。
    /// Runner 可限制为受信任的仓库或仅对等拉取。
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub allowed_image_registries: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerCapacity {
    pub max_memory_bytes: u64,
    pub max_cpu_millicores: u32,
    pub max_timeout_secs: u32,
    pub max_disk_bytes: u64,
    pub max_volume_mounts: u32,
}
```

### 7. 系统指令（50–54）

CIP-10 新增五个 `SystemInstruction` 变体，分发至容器镜像注册表（0x0A）。指令编号 50–54 为容器镜像管理保留。

```rust
pub enum SystemInstruction {
    // ... 现有指令 0–49 ...

    // ── CIP-10: 容器镜像指令（50–54）────────────────────────────────────────

    /// 将容器镜像哈希注册到许可列表。
    /// 调用者成为 `registrant`，可撤销或更新该条目。
    /// 触发事件：ContainerImageRegistered { image_hash, registrant, label }
    ContainerImageRegister {
        /// OCI 镜像清单的 32 字节内容哈希。
        image_hash: [u8; 32],
        /// 所用哈希算法。
        hash_algo: ImageHashAlgo,
        /// 可读标签（名称 + 版本标签）。最多 128 字节。
        label: String,
        /// 可选执行策略。默认：AnyRunner。
        policy: Option<ImagePolicy>,
    },                                                          // 50

    /// 停用已注册镜像（阻止新作业使用）。
    /// 仅原始 `registrant` 或治理 Actor 可调用。
    /// 正在运行的作业不受影响。
    /// 触发事件：ContainerImageRevoked { image_hash, revoked_by }
    ContainerImageRevoke {
        image_hash: [u8; 32],
    },                                                          // 51

    /// 更新已注册镜像的执行策略。
    /// 仅原始 `registrant` 可调用。
    /// 触发事件：ContainerImagePolicyUpdated { image_hash, new_policy }
    ContainerImageSetPolicy {
        image_hash: [u8; 32],
        policy: ImagePolicy,
    },                                                          // 52

    /// 重新激活已被撤销的镜像。
    /// 仅原始 `registrant` 可调用。
    /// 触发事件：ContainerImageReactivated { image_hash }
    ContainerImageReactivate {
        image_hash: [u8; 32],
    },                                                          // 53

    // 54 为未来容器镜像操作保留
}
```

### 8. 网络模型

默认情况下，容器作业在**隔离的网络命名空间**中执行，无法访问互联网。这与 CIP-2 的确定性和隔离要求一致：Runner 输出必须可复现，不得依赖其他方无法验证的外部状态。

容器作业的互联网访问遵循**权利模型**（CIP-2 §7）：

```rust
// 对 CIP-2 权利类型的扩展
pub enum Action {
    // ... 现有变体 ...
    /// 允许 actor_address 提交的容器作业访问互联网端点。
    ContainerNetworkEgress { allowed_hosts: Vec<String> },
}
```

当容器作业持有有效的 `ContainerNetworkEgress` 权利时，Runner 创建带有 NAT 网关连接到允许主机的网络命名空间（通过 iptables 出口过滤）。作业运营方负责确保任何网络来源数据的确定性（例如，在验证前通过 CIP-9 卷作为写透缓存并在链上锚定）。

### 9. 安全考量

#### 9.1 镜像哈希固定

`ContainerSpec` 中的 `image_hash` 是镜像的权威身份标识。Runner 在拉取后、执行前验证哈希。不匹配将无条件触发 `JobFault`。这可防止供应链攻击：即使仓库被攻陷，作业规格中的镜像摘要保持不变，篡改的镜像无法通过验证。

#### 9.2 命名空间隔离

所有容器作业在隔离的 Linux 命名空间中执行：

| 命名空间 | 作用 |
|---------|------|
| `user` | 将容器 root 映射到非特权宿主 UID（无法提升权限） |
| `mount` | 隔离的文件系统视图；宿主文件系统不可见 |
| `pid` | 隔离的 PID 空间；宿主进程不可见 |
| `uts` | 隔离的主机名（防止基于主机名的指纹识别） |
| `ipc` | 隔离的 System V IPC 和 POSIX 消息队列 |
| `net` | 隔离的网络（默认无互联网；见 §8） |

**`cgroup` v2** 强制执行 `memory.max`、`cpu.max`、`pids.max` 和 `io.max`。Runner **必须**使用 cgroup v2；不支持 cgroup v2 的内核上运行的 Runner **不得**声明 `supports_containers: true`。

#### 9.3 未注册镜像执行

`allow_unregistered: true` 允许执行未在容器镜像注册表中的镜像。此功能仅限开发工作流和受信任的 TEE 环境使用。要求：

1. 作业**必须**在其元数据中包含 `tee_attestation` 字段（根据 CIP-2 TEE 认证协议 §5.5）。
2. Runner **必须**在 Runner 注册表（0x01）中以 `TeeCapability` 注册。
3. TEE 验证器（0x05）**必须**在作业分发前验证认证信息。

此机制允许 TEE 保护的 Runner 在不公开哈希的情况下执行专有镜像，同时仍提供执行完整性的密码学证明。

#### 9.4 卷挂载隔离

CIP-9 卷通过容器 mount 命名空间内的 FUSE 绑定挂载接入容器。Runner 的宿主文件系统从容器内部永远不可访问。卷的 `WriteOnly` 模式在 FUSE 层强制执行：读取操作返回 `EPERM`。

#### 9.5 临时层清理

作业完成后（无论退出码），Runner 销毁临时的 overlayfs upper 层。写入容器文件系统（而非 CIP-9 卷）的敏感数据将丢失。需要持久化的 Actor **必须**使用 CIP-9 卷。

#### 9.6 环境变量机密性

环境变量携带在 `JobSpec` 中，通过 CIP-2 作业分配协议分发给分配的 Runner。它们**不是机密**——对 Runner 以及任何能访问作业规格的人可见。敏感配置（API 密钥、凭证）**必须**存储在 CIP-9 卷中，而非 `ContainerSpec.env`。

---

## 设计理由

**为何选择 OCI 镜像而非自定义格式？** OCI 是行业标准，拥有丰富的生态系统（Docker、Podman、BuildKit、containerd）。复用它避免了重新发明分发、分层和工具链。内容寻址摘要与协议的哈希固定身份模型自然契合。

**为何在链上设置容器镜像注册表？** 没有链上许可列表，任何作业运营方都可以提交任意镜像哈希，Runner 将在没有协议级监督的情况下执行它们。注册表提供了治理层：运营方注册已知可信镜像，治理 Actor 可以撤销被攻陷的镜像，策略系统支持企业隔离要求（TEE、权利池）。

**为何不使用密钥管理器（0x04）存储镜像凭证？** 密钥管理器有意与链下 Runner 隔离（它在 PVM 内运行）。容器镜像仓库凭证是 Runner 的运维配置，而非协议级机密。Runner 通过带外方式配置自己的 OCI 仓库认证（docker login 凭证等）。

**为何将 `ContainerLimits` 与 `ResourceBounds` 分开？** `ResourceBounds` 是 CIP-2 概念，以与 LLM 作业相关的 token 预算（`max_input_tokens`、`max_output_tokens`）为中心。容器作业有完全不同的资源维度（内存、CPU、磁盘、pids）。复用 `ResourceBounds` 需要添加对非容器作业毫无意义的 CPU/磁盘字段。分开定义使两者都保持简洁。

**为何默认网络隔离？** 不确定性是 CIP-2 验证模型的主要威胁。获取外部数据的容器将在不同 Runner 上产生不同输出，导致验证失败。通过权利选择加入网络强制要求作业运营方明确承认此风险，并承担确保网络来源数据确定性的责任。

---

## 向后兼容性

- 新的 `JobType::Container` 变体使用 `#[serde(tag = "type")]`，判别符为 `"Container"`。使用 `#[serde(other)]` 或忽略未知变体的现有反序列化器将优雅地跳过它。
- 不支持容器（`supports_containers: false`）的 Runner 永远不会被作业分发器分配 `Container` 作业——分发逻辑已根据 RateCard 能力进行过滤。
- 指令编号 50–54 与现有任何指令编号（0–49）不冲突。
- `0x0A` 处的容器镜像注册表是新地址，无冲突。

---

## Gas 费用

所有值按照 CIP-3 双计量模型以 Cycles 和 Cells 为单位。

| 指令 | Cycles | Cells | 说明 |
|------|--------|-------|------|
| `ContainerImageRegister` | 10,000 | 200 | 存储 `ImageEntry` + 标签 |
| `ContainerImageRevoke` | 1,000 | 0 | 翻转 `active` 标志 |
| `ContainerImageSetPolicy` | 2,000 | 100 | 覆盖策略字段 |
| `ContainerImageReactivate` | 1,000 | 0 | 翻转 `active` 标志 |
| 作业分发（Container） | 与 CIP-2 基础相同 | + `ContainerSpec` 字节计为 Cells | `ContainerSpec` 计入作业提交的 Cell 费用 |

**容器执行成本**通过 Runner 的 RateCard 在链下定价，与 CIP-2 市场模型（§4）一致。Runner 可能对容器作业收取高于 LLM/HTTP 作业的费用，以反映基础设施成本（镜像缓存存储、OCI 运行时开销、cgroup 管理）。

---

## 参数（创世默认值）

| 参数 | 值 | 治理可调 |
|------|-----|---------|
| `container_image_registry_actor` | `0x0000…000A` | 否 |
| `max_image_label_bytes` | 128 | 是 |
| `max_container_stdout_bytes` | 1,048,576（1 MiB） | 是 |
| `max_container_stderr_bytes` | 65,536（64 KiB） | 是 |
| `default_container_memory_bytes` | 536,870,912（512 MiB） | 是 |
| `default_container_cpu_millicores` | 1,000 | 是 |
| `default_container_timeout_secs` | 60 | 是 |
| `default_container_disk_bytes` | 1,073,741,824（1 GiB） | 是 |
| `default_container_pids_max` | 512 | 是 |
| `max_container_volume_mounts` | 8 | 是 |
