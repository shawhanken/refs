---
type: entity
tags: [system-actors, addresses, authoritative]
sources:
  - node/runner/src/system_actors.rs
  - node/types/src/execution.rs
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/cips/cip-9-runner-storage.md
  - refs/cips/cip-10-runner-containers-v2.md
  - refs/cips/cip-12-governance.md
  - refs/cips/cip-13-runner-delegation-v2.md
  - refs/cips/cip-14-dns-addressable-actors-v2.md
  - refs/cips/cip-18-payments.md
  - refs/cips/cip-23-tee-execution-v2.md
  - refs/analysis/2026-04-15_documentation_amendments.md
last_updated: 2026-05-11
status: authoritative
---

# System Actors

Cowboy 在保留地址段注册系统 Actor，实现协议级功能。它们与用户 Actor 同构（消息驱动），但由 Genesis 块初始化、拥有特权操作。当前代码实装到 `0x0B`；CIP v2 系列把分配延展到 `0x0F`（**仍在保留段 `0x00..0x0100` 内**，不再使用 v1 草案的 `0x0011`/`0x0012` 双字节地址）。

---

## 权威地址表

| 地址 | 名称 | 职能 | 规范来源 | 状态 |
|---|---|---|---|---|
| `0x01` | RUNNER_REGISTRY | Runner 注册、stake、心跳；CIP-13 v2 委托扩展 | CIP-2 §6 / CIP-13 v2 | 代码 |
| `0x02` | JOB_DISPATCHER | 任务分发、VRF 选择、托管 | CIP-2 §3-4 | 代码 |
| `0x03` | RESULT_VERIFIER | 结果验证、结算、slashing；CIP-16 v2 `ExternalDomainCallback` 入口 | CIP-2 §5 | 代码 |
| `0x04` | SECRETS_MANAGER | 加密秘密分发；CIP-23 v2 强制 CompositeAttestation | CIP-2 §8 / CIP-23 v2 §3.10 | 代码 (stub) |
| `0x05` | TEE_VERIFIER | TEE attestation 校验 | CIP-2 §8 / **CIP-23 v2 全面接线** | 代码 (stub) |
| `0x06` | DUAL_BASEFEE / BASEFEE_SYSTEM_ACTOR | Cycles/Cells basefee 状态；CIP-5 revised `TimerConfig` 也存这里 | CIP-3 / CIP-5 §6.4 | 代码 |
| `0x07` | ENTITLEMENT_REGISTRY | Scope/Action/Constraints/Role 授权 | CIP-2 §7 | 代码 |
| `0x08` | TREASURY | 协议国库（slashing / burn 目的地）| — | 代码 |
| `0x09` | GOVERNANCE | 治理参数；`SettlementConfig` 五种 `target_pool` 变体（见下）| CIP-2 §5 / CIP-12 / CIP-14 v2 / CIP-10 v2 | 代码 |
| `0x0A` | STORAGE_MANAGER | CIP-9 链下存储元数据；CIP-15 v2 路由清单 / CORS 配置 | CIP-9 §11.1 / CIP-15 v2 §4.1 §7.1 | 代码 |
| `0x0B` | RELAY_REGISTRY | CIP-9 中继节点注册 | CIP-9 §11.2 | 代码 |
| `0x0C` | SESSION_ACTOR | MPP Session 模型：托管 + 累积 voucher 结算 + dispute hook | code (`system_actors.rs:35`) + MPP Session research/plan | **代码已实装** |
| `0x0D` 🆕 | ROUTE_REGISTRY | FQDN → actor 映射；注册 / 续费 / 外部域绑定 | **CIP-14 v2.r2** §4 | v2 提案（precondition）|
| `0x0E` 🆕 | GATEWAY_REGISTRY | Gateway 节点注册 + 心跳 + command-path 系统中介 `dispatch()` | **CIP-14 v2.r2** §7 | v2 提案 |
| `0x0F` 🆕 | RECEIPT_REGISTRY | HTTP 命令路径异步结果存储；单一全局 prune 循环 | **CIP-14 v2.r2** §8 | v2 提案 |
| `0x10` 🆕 | CONTAINER_REGISTRY | OCI 镜像 / 资源类 allowlist；治理可写 | **CIP-10 v2.r2** §1 | v2 提案 |
| `0x11` 🆕 | PAYMENT_GATE | 付款策略 / 预算 / Pass / Subscription / 入站 EVM bridge credit | **CIP-18 r2** §8 | CIP Draft |
| `0x12` 🆕 | STREAM_KEY_MANAGER | CIP-7 r2：VM-level 流加密 / 按 epoch 密钥发放 / CBY 计费（v1 草案曾占 `0x06`，与 DUAL_BASEFEE 冲突，r2 重排到 `0x12`）| **CIP-7 r2** §4 | CIP Draft |

**源**: `node/runner/src/system_actors.rs:13-35`（`0x01`–`0x0C` 实装）+ CIP v2.r2 系列（`0x0D`–`0x10` 提案）+ CIP-18 r2 (`0x11`) + CIP-7 r2 (`0x12`)。

> **2026-05-11 r2 地址段重排**：上一轮 wiki 把 `0x0C` 标为"v2 提案"是误判 —— `0x0C = SESSION_ACTOR` 已 commit 入代码 (`system_actors.rs:35`，含 `node/types/src/session.rs` / `session_eip712.rs` / `runner/crates/runner-common/src/voucher.rs` 全栈)。CIP-14 v2 / CIP-10 v2 / CIP-18 同步发 r2 重排：ROUTE_REGISTRY `0x0C` → `0x0D`，GATEWAY_REGISTRY `0x0D` → `0x0E`，RECEIPT_REGISTRY `0x0E` → `0x0F`，CONTAINER_REGISTRY `0x0F` → `0x10`，PAYMENT_GATE `0x0013` → `0x11`。这一重排只动文档不动代码，符合"代码先到先得"原则。

> **WP §9 漂移修正**：白皮书 §9 line 704 旧表把 `0x0A` 标为 `Container Image Registry`。**这是错的** —— 代码先于 WP 把 `0x0A` 给了 STORAGE_MANAGER（CIP-9）。CIP-10 v2 §1 把 Container Registry 重新分配到 `0x0F`。WP-v2 Part II Delta 6 已显式修正。

---

## 关键职责详情

### Runner Registry（0x01）
- 接受 `runner register`，检查 `stake >= 10,000 CBY`（floor）
- 维护 `VerificationMode` 声明、`RateCard`、心跳与下线
- **CIP-13 v2**：承载 Stake 委托（`DelegationConfig` / `DelegationTranche` / `DelegationTotals` / `DelegationDelegatorSummary`）。VRF 权重与最大 Job 价值基于 `effective_stake = registration.stake + delegation_totals.total_active`（详见 [[../concepts/runner-delegation]]）。
- **CIP-23 v2**：可选 `MeasurementBinding` 字段（attestation-first 注册）；TEE 资格独立于 stake，是分类能力（详见 [[../concepts/tee-attestation]]）。

### Job Dispatcher（0x02）
- 客户 `submit_job` → 托管 bond → VRF + stake-weighted sortition（Fisher-Yates）选 Runner
- 超时 timeout → 重新分发
- **CIP-13 v2 修正**：选择公式分母改用 `effective_stake`（CIP-2 §5.4 amendment）
- **CIP-23 v2 修正**：`tee_required` 过滤改用 `MeasurementBinding.status == Active && expires_at > submission_block`（不再用自报 `capabilities.tee_support` 布尔）
- 见 [[../concepts/vrf-runner-selection]]

### Result Verifier（0x03）
- 接 Runner 结果，按 Job 声明的 `VerificationMode` 验证（[[../concepts/runner-verification]]）
- 结算分成（runner / burn / treasury，[[../concepts/settlement-slashing]]）
- Dispute 窗口后才执行 slashing
- **CIP-13 v2**：`per_runner_share` 进一步按 `delegator_pool / runner_commission` 拆分到 Active Tranche；`slash_runner()` 级联到 Tranche（per-epoch cap 5%）
- **CIP-16 v2**：是 `ExternalDomainCallback`（opcode 67）的 sender allowlist —— DNS 验证完成后由 `0x03` 转发到 `ROUTE_REGISTRY`，使`complete_attach_external` 不可伪造

### Secrets Manager（0x04）
- 当前实装：占位
- **CIP-23 v2 §3.10**：`get_secret` 强制要求 `CompositeAttestation`（不再是可选）；秘密用 HPKE 包给 Runner 的 `service_pubkey`，明文仅在 CVM 内部存在

### TEE Verifier（0x05）
- **当前实装**：占位桩，`verify()` 无条件返回 `Ok(())`
- **CIP-23 v2**：承载 CAE 真实验证流水线 —— 证书链 / measurement 白名单 / `REPORTDATA` 绑定 / 服务签名 / NRAS token
- **opcodes 57–60**（CIP-23 v2 §4，从 v1 §3.6.2 的 50–53 改正）：`VerifyCae` / `UpdateCpuRoot` / `UpdateNrasRoot` / `GcNonces`
- measurement 白名单存在 Runner Registry (`0x01.measurement_binding`)，不重复
- 详见 [[../concepts/tee-attestation]]

### Dual Basefee / BASEFEE_SYSTEM_ACTOR（0x06）
- 持久化 `basefee_cycles`、`basefee_cells` 随每块更新
- **CIP-5 revised**：`TimerConfig` 也存在这里（`state:actor:0x06:kv:system:timer_config`），通过 `SYS_UPDATE_TIMER_CONFIG` (opcode 49) 更新
- 公式见 [[../concepts/basefee]]

### Entitlement Registry（0x07）
- 统一权限抽象层：`Scope` × `Action` × `Constraints` × `Role`
- **当前 14 entries**（`node/types/src/registry.rs:208`）；CIP-14/15/16 v2 各需 1 个新 entry（`ingress.http` / `ingress.static` / `dns.attach_external`）作为 **precondition** 才能激活
- 见 `refs/runner/2026-03-03_Entitlement.md`

### Governance（0x09）
- **当前实装**：存储 `SettlementConfig { runner_percent, burn_percent, treasury_percent }`；`UpdateSettlementConfig`（opcode 40）唯一入口
- **CIP-12（Draft）**：完整双院治理、Tier 0–4 提案、Security Council、系统 Actor 升级（详见 [[../concepts/governance]]）
- **CIP-23 v2**：`UpdateCpuRoot` / `UpdateNrasRoot` 也是治理 sender；`effective_at` 强制 ≥ 1 week 延迟
- **CIP-14/15/10 v2** 共用 `target_pool` 枚举（`UpdateSettlementConfig` 携带），权威表见 [[../concepts/settlement-slashing]] / CIP-14 v2 Part III §6

### Storage Manager（0x0A，CIP-9 真名 + CIP-15 v2 扩展）
- **CIP-9**：`StorageCommitment` 记录、CapToken issuance/revoke、Relay 调度
- **CIP-15 v2 §4.1 / §7.1**：承载 actor-owned `route_manifest` 与 `cors_config`（按 `actor_address` 索引），通过普通 ActorMessage 而非新 SystemInstruction 访问
- **WP §9 旧表错把 `0x0A` 给了 Container Image Registry** —— 已由 WP-v2 Delta 6 修正

### Relay Registry（0x0B，CIP-9）
- 中继节点 profile + 活跃列表 + shard 分配索引

### Route Registry（0x0C，CIP-14 v2）
- `name → actor_address` 正向解析 + `actor → names` 反向；`resolve` / `register` / `renew` / `set_actor` 等均为 ActorMessage
- CIP-16 v2 扩展三类命名空间：`cowboy.network` / `.cow|.cowboy` / 外部 FQDN（TXT 挑战 + ACME 委派）
- **历史地址**：v1 草案用 `0x0011`，v2 收回到 `0x0C` 紧跟现有序列
- 详见 [[route-registry]] / [[../concepts/dns-addressable-actors]] / [[../concepts/custom-domains]]

### Gateway Registry（0x0D，CIP-14 v2）
- Gateway 节点注册 + 心跳（`MAX_GATEWAY_HEALTH = 3600 blocks`）+ stake（`MIN_GATEWAY_STAKE` 治理设）
- **Command 路径系统中介**：Gateway 把 HTTP 请求封装为 `dispatch(target, envelope)`（**opcode 65 `IngressDispatch`**，CIP-14 v2 §6.1）；dispatcher 验证 sender 是 active Gateway 后转发给目标 Actor，目标看到 `ctx.sender == 0x0D`
- **历史地址**：v1 草案用 `0x0012`，v2 收回到 `0x0D`
- 详见 [[gateway]] / [[../concepts/dns-addressable-actors]]

### Receipt Registry（0x0E，CIP-14 v2）
- HTTP 命令路径异步结果存储；替代原 v1 SDK 约定的 `_http/results/{request_id}` actor-KV 模式（避免每请求一个 cleanup timer 撞 `MAX_TIMERS_PER_ACTOR=1024`）
- 单全局 prune 循环按 `expires_at` 清理
- **opcode 66 `CompleteReceipt`**：sender 必须是 receipt 的 `target_actor`
- 详见 [[../concepts/dns-addressable-actors]] §8

### Container Registry（0x0F，CIP-10 v2）
- 治理-only：OCI 镜像 allowlist + 资源类（`ResourceClass`）注册
- **opcodes 61–64**：`RegisterBaseImage` / `DeregisterBaseImage` / `RegisterResourceClass` / `DeregisterResourceClass`（sender 必须是 `0x09`）
- 容器计算费走 `system:container_settlement_config`（`target_pool: CONTAINER`）
- BillingAttestation 的 `tee_signature` 自 CIP-23 v2 §3.12 起改用 `Option<CompositeAttestation>`，**每次 billing event 临时生成**（不缓存 `measurement_binding` quote），由 `0x0F` 调 `0x05::VerifyCae` 校验

### Session Actor（`0x0C`，code 已实装 + MPP Session research/plan）
- **当前实装**：`node/runner/src/system_actors.rs:35` `SESSION_ACTOR = 0x0C`；`node/types/src/session.rs` Session 记录 + storage_keys；`node/types/src/session_eip712.rs` EIP-712 domain；`node/execution/src/runner/session.rs` 链上 handler 框架；`runner/crates/runner-common/src/voucher.rs` 链下 voucher + 签名/恢复
- **职能**：MPP Session 模式 — payer 在 `OpenSession` 时托管 `max_amount`；客户端 → Runner 调用经 EIP-712 签名 voucher 累积 cumulative_amount；Runner 周期/阈值/临近过期调 `Settle` 链上结算（按 SettlementConfig 89/10/1）；payer 调 `CloseSession` 进 dispute 窗口；窗口结束后 `Finalize` 退还余款
- **选址依据**：MPP Session research (2026-04-28) + plan (2026-05-06) 早于 CIP-14 v2 alignment round 6 (2026-04-21) ⚠️ 但代码先 commit；CIP-14 v2.r2 (2026-05-11) 接受 `0x0C` 归 SESSION_ACTOR 并把自身后移 +1
- **后续工作**：起 CIP 草案（暂称 CIP-2X / `cip-2x-mpp-session.md`）正式纳入主表；当前 V-11 状态从"撞地址"修正为"待补 CIP 草案"
- 详见 [[../concepts/mpp-session]]

---

### PaymentGate（`0x11`，CIP-18 r2 Draft）
- **当前实装**：无
- **职能**：单 system actor 承载 `PaymentPolicy` 表（per actor）+ `BudgetBalance` + `Pass` + `EpochEntitlement` + nonce table + 入站 EVM credit；handler API 含 `set_policy` / `get_policy` / `deposit_budget` / `withdraw_budget` / `purchase_pass` / `purchase_epoch` / `verify_payment` / `settle_payment` / `deduct_budget` / `credit_inbound`（详见 [[../concepts/payments]]）
- **opcode**：无新 SystemInstruction（所有调用均为 ActorMessage to `0x11`）
- **付款 wire**：Gateway 边缘 enforce；MPP（Authorization: Payment）+ x402（PAYMENT-SIGNATURE）双 wire 并行 normalize 为内部 `PaymentIntent`
- **新 Entitlements**：`payment.gate`（actor 持，前置 `ingress.http`）/ `bridge.facilitate.evm`（runner 持，deferred）—— 见 [[../drift]] V-15
- **2026-05-11 r2 地址**：从 `0x0013` 后移到 `0x11`，对齐 v2 单字节序列（在 CIP-10 v2.r2 `0x10` 之后）。CIP-18 §22 rationale 同步重写
- 详见 [[../concepts/payments]]

---

## 源文档冲突 / 漂移

**1. v1 → v2 地址段重命名**
- CIP-14 v1 用 `0x0011` / `0x0012`，CIP-14 v2 收回到紧跟序列的 `0x0C` / `0x0D`（外加 `0x0E` Receipt）；CIP-10 v2 取 `0x0F`
- 三处 v2 文档的 Part III §1 系统 actor 表已对齐，本页采用 v2 编号

**2. WP §9 line 704 错配 `0x0A`**
- WP 旧表声明 `0x0A = Container Image Registry`
- 代码与 CIP-9 选 `0x0A = STORAGE_MANAGER`
- WP-v2 Delta 6 + 本表已修正；CIP-10 v2 把 Container Registry 改到 `0x0F`

**3. workspace CLAUDE.md 旧地址 `0x91-0x95`**
- 应废弃；CIP-23 §3.2 明确 "supersedes conflicting listings in `CLAUDE.md` and `node/types/README.md`"

**4. 实装 vs spec 的 precondition gap**
- `0x0C` / `0x0D` / `0x0E` / `0x0F` 在代码中尚未存在；属于 v2 协议 precondition（详见 [[../drift]]）
- 实现时需在 `node/runner/src/system_actors.rs` 追加常量 + 同步 workspace CLAUDE.md

**5. MPP Session 提案 `0x0C` 撞 ROUTE_REGISTRY**
- 研究文档（2026-04-28）/ 计划（2026-05-06）提议 `SESSION_ACTOR = 0x0C`
- CIP-14 v2 §1 已把 `0x0C` 分配给 `ROUTE_REGISTRY`
- 研究文档未引入 v2 alignment 上下文；激活前必须治理选址（[[../drift]] V-11）

**6. CIP-18 PaymentGate `0x13` 沿用 CIP-14 v1 numbering**
- CIP-18 §22 rationale 把 `0x0013` 续到 v1 的 `0x0011/0x0012`（CIP-14 v1 老分配）
- v2 主表上 CIP-10 v2 已取 `0x0F`，按单字节连续序列 PaymentGate 应落 `0x10`
- 激活前需在主表确认 PaymentGate slot 并同步 CIP-18（[[../drift]] V-14）

详见 [`refs/analysis/2026-04-15_documentation_amendments.md §二`](../../analysis/2026-04-15_documentation_amendments.md)。

---

## Sources
- `node/runner/src/system_actors.rs:13-33` — 地址常量定义（实装 `0x01`-`0x0B`）
- `node/types/src/execution.rs:482-541` — SystemInstruction opcode 常量（含 CIP-5 revised 引入的 48/49/50）
- `refs/cips/cip-2-offchain-compute.mdx` — Runner 系统规范
- `refs/cips/cip-9-runner-storage.md` — Storage Manager `0x0A` 权威定义
- `refs/cips/cip-10-runner-containers-v2.md` §1 — Container Registry `0x0F`
- `refs/cips/cip-12-governance.md` — `0x09` 完整治理规范（Draft）
- `refs/cips/cip-13-runner-delegation-v2.md` §1 — opcode 主分配表（v2 系列权威）
- `refs/cips/cip-14-dns-addressable-actors-v2.md` — `0x0C` / `0x0D` / `0x0E` 提案
- `refs/cips/cip-16-custom-domains-v2.md` — `0x0C` 扩展（TLD / external FQDN, Draft）
- `refs/cips/cip-18-payments.md` §8 / §22 — PaymentGate `0x13` 提案 + sequential allocation rationale
- `refs/cips/cip-23-tee-execution-v2.md` §4 — `0x05` 真实 attestation 流水线 + opcodes 57–60
- `refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md` Part II Delta 6 — WP §9 0x0A 修正
- `refs/runner/2026-04-28_MPP_Session_Research.md` §5.3 — Session Actor 提案（与 `0x0C` ROUTE_REGISTRY 冲突）
- `refs/plans/2026-05-06_mpp_session_implementation.md` §3.1 — Session Actor 实施计划（PoC 阶段）
