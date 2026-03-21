# CIP-9 / CIP-10 会议记录差异分析

**参考会议：** 2026-03-18 内部会议
**参考文档：** CIP-9 Runner Attachable Storage、CIP-10 Container Runtime
**分析基准：** 以 CIP-9 / CIP-10 为准，会议记录为参照，逐条陈述差异与理由

---

## 一、与 CIP-9 的差异

### 差异 1：存储模型 — 临时 Blob vs. 持久加密卷

**会议观点**：

会议设想的是一个类似以太坊 blob 或 IPFS 的**短期内容寄存**服务——存 N 天、按 TTL 计费、不保证持久性。

**CIP-9 立场：** 明确定义的是**持久加密卷**（Persistent Encrypted Volume），有 `VolumeMetadata`、清单根锚定（`VolumeAnchorManifest`）和 Reed-Solomon 纠删码。

**理由：** 会议方案无法满足 CIP-9 §1 动机 1（Secret Management）和动机 3（Tool-Chain Data Flow）。密钥和凭证需要跨作业持久存在，不能因 TTL 过期而丢失；多 Runner 流水线的中间状态也需稳定存储，临时 blob 模型在 Runner 故障重试或流水线跨天执行时会丢数据。TTL 计费适合"输出物投递"场景，已在 §2（Off-Chain Output）中覆盖，但不能作为整个 CIP-9 的底层模型。

---

### 差异 2：访问控制 — 链接即权限 vs. CapToken

**会议观点**：

访问模型是 IPFS 原生的**"知道哈希即可访问"**，没有身份绑定。

**CIP-9 立场：** 引入 `CapToken`——secp256k1 签名的 bearer 凭证，包含 `grantee`（被授权 Runner 地址）、`expires_at_block`、`nonce`（防重放），与 Runner 注册表（0x01）绑定。Steamtrain 层在挂载前做链下签名验证。

**理由：** IPFS 哈希是**公开可读**的——任何人拿到链接都能下载内容。对于含 API key 或私有数据集的卷，这是严重的机密性漏洞。CapToken 将"知道 ID"和"持有授权"解耦，即使 `volume_id` 泄露，未持有有效 CapToken 的 Runner 也无法挂载。这也是 CIP-9 §10（Security Considerations）"CapToken Forgery"一节的核心保障。

---

### 差异 3：协议标识符 — `cowboy://` URL vs. VolumeId

**会议观点**：

会议提出设计一套 `cowboy://` 或类似 URL scheme，用于上传和下载。

**CIP-9 立场：** 使用 `VolumeId = [u8; 32]`（keccak256 派生）作为卷的链上标识符，没有定义用户可见的 URL scheme。文件访问通过 FUSE 挂载点（`/mnt/xxx`）暴露给 Runner。

**理由：** URL scheme 是 SDK/客户端侧的界面设计，不属于共识层协议范畴。CIP-9 故意将"如何定位存储节点"（QUIC transport，在 `steamtrain-client/src/quic.rs`）与"链上如何授权"分开。URL scheme 可以作为 SDK 层的便利封装，但不应成为 CIP 核心类型——否则会将 DNS/HTTP 寻址语义引入共识，增加不确定性。

---

### 差异 4：定价模型 — 按天 TTL 阶梯定价 vs. 链下 Escrow

**会议观点**：

会议方案是**链上计费 + TTL 绑定**，类似 CDN 存储套餐。

**CIP-9 立场：** 链下定价，"Steamtrain 运营方在链下公示定价（CBY per byte per period），类比 Runner 费率卡"（§7 Gas Costs 注释），Actor 在创建卷时预付 escrow。

**理由：** 如果在链上强制绑定 TTL，卷的 GC 时机就成为共识问题——每个节点必须在相同区块对过期卷执行相同操作，增加状态机复杂度。CIP-9 选择软删除（`deleted: bool` 标志）+ 链下 GC，与白皮书 §17.7 的 Runner 市场定价哲学一致：计算资源定价走市场，链上只处理授权和完整性锚定。

**备注：**
TTL 是"预约销毁"，escrow 是"余额驱动续存"。 前者让链负责计时和删除，后者让市场（存储节点）负责判断何时停止服务，链只负责资金的锁定和释放。CIP-9 选择后者，是为了让链上逻辑尽可能简单、确定，将运营复杂度下沉到链下。

---

### 差异 5：清单根锚定 — 会议未提及

整个会议记录中没有出现"清单根"、"内容哈希锚定"、"Merkle root"等概念。

**CIP-9 立场：** `VolumeAnchorManifest`（指令 43）是 CIP-9 的核心机制之一——Runner 每次写入卷后必须将 Steamtrain Merkle tree 的 32 字节根哈希提交上链，作为全局一致的数据完整性承诺。

**理由：** 不锚定清单根，存储层就退化成了纯链下黑盒，无法支持 CIP-2 的结果验证模型。如果 Runner A 写入了数据，Runner B 拿着相同 CapToken 挂载同一卷，链上的 `manifest_root` 是唯一可以让 B 验证"我读到的内容确实是 A 写入的"的机制。这对需要跨 Runner 验证的工具链流水线尤为关键。

---

### 差异 6：加密方案 — 会议仅提 TEE，未提客户端加密

**会议观点**：

会议方案是**传输层 TEE 加密**——数据通过 TEE 的公钥加密后传输，由 TEE 解密。

**CIP-9 立场：** Steamtrain 采用 **AES-256-GCM 客户端加密**——数据在离开 Runner 前就已加密，存储节点始终只见密文（§10 "Client-Side Encryption Guarantee"）。

**理由：** TEE 加密保护的是传输通道，但存储节点仍然持有明文（在 TEE 解密后到写入存储之前）。客户端加密保证存储节点永远无法读取明文，即使存储节点被攻陷也无影响。CIP-9 目标是**零信任存储节点**，TEE 模型满足不了这个要求。TEE 仍在 CIP-9 的授权体系中扮演角色（§10 与 CIP-2 §5.5 的 TEE attestation 集成），但不是加密的核心手段。

---

## 二、与 CIP-10 的差异

### 差异 7：容器用途 — 交互式开发环境 vs. 批处理作业

**会议观点**：
会议涉及的容器概念更接近**长期运行的可预览开发沙箱**（类似 Codex / Claude Code 的远程容器），有 Web UI 预览、可交互。

**CIP-10 立场：** 定义的是**一次性批处理作业**（one-shot job）——Runner 启动容器、执行至退出、收集 stdout/stderr、提交结果。容器生命周期与 Job 生命周期绑定，不支持长期运行进程。

**理由：** CIP-2 的作业模型本身是无状态批处理的——有 `timeout_secs`，执行后即销毁。长期运行容器需要完全不同的生命周期管理（心跳、重启策略、端口映射），这超出了 CIP-2 当前架构范围，也与 Runner 无状态的核心设计矛盾。持久化容器的场景（数据库、缓存层）通过 CIP-9 卷的持久性来满足——**状态在卷里，容器本身仍是临时的**。

---

### 差异 8：容器镜像注册表 — 会议未提，CIP-10 强制要求

会议没有讨论任何镜像哈希校验或链上白名单机制。

**CIP-10 立场：** Container Image Registry（系统 Actor 0x0A，指令 50–53）是强制的——Runner 不得执行未在注册表中存在的镜像哈希（除非 TEE 认证 + `allow_unregistered: true`）。

**理由：** 不设镜像白名单，任何 Actor 都可以向 Runner 提交任意镜像（含恶意代码），Runner 沦为无控制的通用代码执行机器，与 Cowboy 的可验证计算定位完全背离。链上注册表让治理 Actor 可以在镜像被攻陷后快速撤销（`ContainerImageRevoke`，指令 51），是供应链安全的关键控制点。

---

### 差异 9：网络隔离 — 会议未提，CIP-10 默认隔离

会议全程未讨论容器的网络访问控制。

**CIP-10 立场：** 容器作业默认在隔离网络命名空间中运行，无法访问互联网；外网访问必须持有 `ContainerNetworkEgress` Entitlement（CIP-2 §7 权利体系）。

**理由：** CIP-2 的验证模型要求 Runner 输出可被多方复现。如果容器可以任意访问网络（拉取实时数据、调用外部 API），不同 Runner 在不同时刻执行同一作业会产生不同输出，导致多数投票验证失败。网络访问是 CIP-10 确定性的最大威胁，因此默认关闭，通过 Entitlement 显式授权并转移责任。

---

### 差异 10：资源限制 — 会议未提，CIP-10 强制执行

会议没有讨论 CPU、内存、磁盘、PID 的限制机制。

**CIP-10 立场：** `ContainerLimits`（`memory_bytes`、`cpu_millicores`、`timeout_secs`、`disk_bytes`、`pids_max`）全部通过 cgroup v2 强制执行，并在 `RateCard.container_limits` 中声明 Runner 可接受的上限。

**理由：** 没有 cgroup 限制，一个恶意或有 bug 的容器镜像可以消耗 Runner 节点的全部资源，拒绝服务其他作业（DoS），也无法在经济上定价（Runner 不知道一个作业会消耗多少资源）。`ContainerLimits` 是 Runner 报价（RateCard）和作业定价的基础。

---

## 三、汇总表

| # | 类别 | 会议描述 | CIP-9/10 立场 | 差异性质 |
|---|------|---------|--------------|---------|
| 1 | 存储持久性 | TTL Blob，几天后消失 | 持久加密卷 + Merkle 锚定 | 根本性差异（CIP-9 更严格） |
| 2 | 访问控制 | 知道链接即可访问 | CapToken 身份绑定 | 根本性差异（CIP-9 更严格） |
| 3 | 协议标识 | `cowboy://` URL scheme | `VolumeId [u8;32]`，FUSE 挂载 | 界面设计 vs. 协议层（会议是 SDK 视角） |
| 4 | 定价 | 链上 TTL 阶梯 | 链下 escrow | 架构哲学差异 |
| 5 | 清单锚定 | 未提及 | 核心机制（指令 43） | CIP-9 新增需求 |
| 6 | 客户端加密 | TEE 传输加密 | AES-256-GCM 静态加密 | 安全模型差异 |
| 7 | 容器生命周期 | 长期运行、可预览 | 一次性批处理 + TTL | CIP-10 更保守（符合 CIP-2 架构） |
| 8 | 镜像注册表 | 未提及 | 强制链上白名单（0x0A） | CIP-10 新增安全控制 |
| 9 | 网络访问 | 未讨论 | 默认隔离，Entitlement 授权 | CIP-10 更保守 |
| 10 | 资源限制 | 未讨论 | cgroup v2 强制 + RateCard 声明 | CIP-10 新增运维要求 |

---

## 四、结论

会议中所讨论的产品方向的**早期构思**（偏向用户体验和商业落地），CIP-9 / CIP-10 在此基础上进行了**协议层收敛**——在三个维度上做了更严格的约束：

1. **安全性**：客户端加密（差异 6）、CapToken 身份绑定（差异 2）、镜像白名单（差异 8）
2. **可验证性**：清单根锚定（差异 5）、网络隔离保证确定性（差异 9）
3. **架构一致性**：无状态批处理（差异 7）、链下定价（差异 4）

代价是暂时不支持会议中提到的"长期运行可预览容器"场景。该场景技术上可行，可作为 **CIP-10 后续版本**的扩展方向，但需要先完善 CIP-2 的作业生命周期管理（心跳、端口映射、重启策略），再叠加容器持久化能力。

会议中 `cowboy://` URL scheme 的构想（差异 3）和按天阶梯定价模型（差异 4）适合作为 **SDK 层**或**链下市场**的设计，不影响 CIP-9 的链上协议定义。
