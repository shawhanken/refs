---
type: entity
tags: [system-actors, addresses, authoritative]
sources:
  - node/runner/src/system_actors.rs
  - node/types/src/constants.rs
  - node/types/src/execution.rs
  - node/execution/src/pvm_host.rs
  - node/execution/src/execution/event_sub_system_actor.rs
  - refs/cips/cip-2-offchain-compute.md
  - refs/cips/cip-7-simple-stream-protocol.md
  - refs/cips/cip-8-mpp-session.md
  - refs/cips/cip-9-runner-storage.md
  - refs/cips/cip-10-runner-containers.md
  - refs/cips/cip-12-governance.md
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-18-payments.md
  - refs/cips/cip-23-tee-execution.md
  - refs/cips/cip-24-secrets-manager.md
  - refs/cips/cip-28-cowboy-agent-banking.md
  - refs/cips/cip-29-on-chain-event-hooks-en.md
  - refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md
last_updated: 2026-08-15 (全表按代码 pin 测试 `runner/src/system_actors.rs` 重写：0x0D-0x1E 段整体校正 + 补 0x11/0x14/0x16/0x17/0x1E；作废旧 spec-only 段；前值 2026-05-26)
status: authoritative
---

# System Actors

Cowboy 在保留低位地址注册系统 Actor，承载协议级功能。它们与用户 Actor 同构（消息驱动），但由 genesis 初始化、拥有特权操作。

> **[2026-08-15 更正]** 旧版（2026-05-26）把 `0x0D–0x13` 整段标为 "spec-only" 并给了错误的名称映射：`STREAM_KEY_MANAGER` 已实装在 **`0x0D`**，把 ROUTE/GATEWAY/RECEIPT 各推后一位，且 `0x11/0x14/0x16/0x17/0x1E` 缺失。下表已按 pin 测试 **`node/runner/src/system_actors.rs`（`well_known_low_byte_assignments`）** 校正——该段现在**全部已声明为常量**，不再是 spec-only。未列出的 `0x15 / 0x18–0x1C / 0x1F+` 为未分配。

地址空间现状（权威来源：`node/runner/src/system_actors.rs` 的 `SystemActorAddresses` 宏 + `well_known_low_byte_assignments` 测试；`node/types/src/constants.rs`）：`0x01–0x1E` 已声明常量，保留段 `< 0x100` 在 `pvm_host.rs` 中禁止用户 actor 部署 / 禁作 `fee_payer_override`。`0x1D`（EVENT_SUBSCRIPTION）是**虚拟型**——`call_actor` 拦截路由到 RPC dispatch，不部署 actor 代码。

---

## 权威地址表（2026-08-15，校正自 `system_actors.rs`）

| 地址 | 名称 | 职能 | 规范来源 | 状态 |
|---|---|---|---|---|
| `0x01` | RUNNER_REGISTRY | Runner 注册、stake、心跳；CIP-13 v2 委托扩展 | CIP-2 §6 / CIP-13 v2 | ✅ 代码 |
| `0x02` | JOB_DISPATCHER | 任务分发、VRF 选择、托管 | CIP-2 §3-4 | ✅ 代码 |
| `0x03` | RESULT_VERIFIER | 结果验证、结算、slashing | CIP-2 §5 | ✅ 代码 |
| `0x04` | SECRETS_MANAGER | CBSS 链上面：per-secret 记录、release-key registry、proxy registry | CIP-24 §3.2 | ✅ 代码 |
| `0x05` | TEE_VERIFIER | TEE attestation 校验；trusted key（opcodes 60-63）+ attestation 记录 | CIP-2 §8 / CIP-23 v2 / CIP-24 §3.3 | ✅ 代码 |
| `0x06` | DUAL_BASEFEE | Cycles/Cells basefee 状态；CIP-5 revised `TimerConfig` 也存这里 | CIP-3 / CIP-5 §6.4 | ✅ 代码 |
| `0x07` | ENTITLEMENT_REGISTRY | Scope/Action/Constraints/Role 授权 | CIP-2 §7 | ✅ 代码 |
| `0x08` | TREASURY | 协议国库（slashing / burn 目的地） | — | ✅ 代码 |
| `0x09` | GOVERNANCE | 治理参数；`SettlementConfig` + `Proposal` 表；DrainRelay / AutoDrainPolicy（CIP-9 §13） | CIP-12 / CIP-9 §13 | ✅ 代码 |
| `0x0A` | STORAGE_MANAGER | CIP-9 链下存储元数据 / 路由清单 / CORS | CIP-9 §11.1 | ✅ 代码 |
| `0x0B` | RELAY_REGISTRY | CIP-9 中继节点注册；`AutoDrainPolicyConfig`（CIP-9 §13.4） | CIP-9 §11.2 | ✅ 代码 |
| `0x0C` | SESSION_ACTOR | MPP Session：托管 + 累积 voucher 结算 + dispute hook | CIP-8 | ✅ 代码 |
| `0x0D` | **STREAM_KEY_MANAGER** | VM-level 流加密 / 按 epoch 密钥发放 / CBY 计费（CIP-7；占用 0x0D，ROUTE 顺延到 0x0E） | CIP-7 r2 §4 | ✅ 代码 |
| `0x0E` | ROUTE_REGISTRY | FQDN → actor 映射；注册 / 续费 / 外部域绑定（spec 原写 0x0D，因 0x0D 已被 STREAM_KEY_MANAGER 占用而顺延至 0x0E） | CIP-16 | ✅ 代码 |
| `0x0F` | GATEWAY_REGISTRY | Gateway 边缘广告 + 心跳 + command-path 系统中介 | CIP-16 | ✅ 代码 |
| `0x10` | RECEIPT_REGISTRY | domain-action 收据存储 | CIP-16 | ✅ 代码 |
| `0x11` | VALIDATOR_SET | CIP-11 验证者集快照 | CIP-11 | ✅ 代码 |
| `0x12` | PAYMENT_GATE | 付款策略 / 预算 / Pass / Subscription / 入站 EVM bridge | CIP-18 r2 §8 | ✅ 代码 |
| `0x13` | CONTAINER_REGISTRY | OCI 镜像 / 资源类 allowlist；治理可写 | CIP-10 v2.r2 §1 | ✅ 代码 |
| `0x14` | INTENT_SETTLEMENT | CIP-10 v2 意图结算账户 | CIP-10 v2 | ✅ 代码 |
| `0x16` | BANK_ACTOR | Agent banking 原语（cards / gas 路由 / 策略） | CIP-28 | ✅ 代码 |
| `0x17` | STREAM_REGISTRY | CBQS 流 / provider 记录 | CIP-39 | ✅ 代码 |
| `0x1D` | EVENT_SUBSCRIPTION | CIP-29 on-chain event hooks：竞价市场查询 RPC（`get_rank` / `get_topic_orderbook` / `get_min_bid_for_rank`） | CIP-29 §2.6 | ✅ 代码（虚拟/拦截） |
| `0x1E` | TRADING_POST | actor hiring 与分发 rails | CIP-33 | ✅ 代码 |

**源**：`node/runner/src/system_actors.rs`（`SystemActorAddresses` 宏 + `well_known_low_byte_assignments` 测试，钉住 `0x01–0x1E` 全部映射）+ `node/types/src/constants.rs`（`VALIDATOR_SET=0x11`、`EVENT_SUBSCRIPTION=0x1D`、`TRADING_POST=0x1E` 等）。改地址即改此二处并跑该测试。

---

## 两类激活模型

代码同时存在两种"系统 actor"的实现模式：

### 1. 部署型（band-protected，`0x01-0x0F`）
- 在 `node/runner/src/system_actors.rs` 声明 `Address` 常量
- 由 genesis 写入实际 Actor 记录（含 `code_hash`、`manifest` 等）
- `pvm_host.rs:1961, 4291` 禁止用户 actor 部署到此地址段，禁作 `fee_payer_override`
- 通过 SystemInstruction opcode 或 ActorMessage 路由
- 当前 12 个，最后一个是 `0x0C SESSION_ACTOR`

### 2. 虚拟拦截型（host-intercepted，`≥0x10`）
- 不在 `system_actors.rs` 注册（也不必有 Actor 记录）
- `pvm_host::call_actor` 检查目标地址是否等于该常量，若匹配则路由到 host-side dispatcher
- 不消耗保留段 `0x01-0x0F` 名额
- 适合"thin RPC surface"（仅读、不改 actor KV）
- 当前 1 个：`0x1D EVENT_SUBSCRIPTION_SYSTEM_ACTOR`

**Spec-only 地址 (`0x0D-0x13`) 激活时择一**：扩 reserved band 到目标地址 + 注册 `Address` const（沿 v2 序列）；**或** 改用 `0x1D` 那种 interception 模式（避开保留段强制）。CIP-28 §0 的 "Code activation note" 已在 spec 内显式留这个决定。

---

## 关键职责详情

### Runner Registry（0x01）
- 接受 `runner register`，检查 `stake >= 10,000 CBY` + 1.5× declared_max_job_value
- 维护 `VerificationMode` 声明、`RateCard`、心跳、reputation
- **CIP-13 v2**（spec-only）：扩展 stake 委托（`DelegationConfig` / `DelegationTranche` / `DelegationTotals`）；VRF 权重基于 `effective_stake`（详见 [[../concepts/runner-delegation]]）
- **CIP-23 v2**（spec-only）：可选 `MeasurementBinding` attestation-first 注册

### Job Dispatcher（0x02）
- `submit_job` → 托管 bond → VRF + stake-weighted Fisher-Yates sortition
- 超时 → re-selection；见 [[../concepts/vrf-runner-selection]]

### Result Verifier（0x03）
- 接 Runner 结果，按 Job 声明的 `VerificationMode` 验证（[[../concepts/runner-verification]]）
- 结算分成 runner / burn / treasury（[[../concepts/settlement-slashing]]）
- Dispute 窗口（CIP-2 §6 `DISPUTE_WINDOW_BLOCKS=75`）后才执行 slashing

### Secrets Manager（0x04，CBSS 链上面，CIP-24）
- **CIP-24 实装范围**：per-secret 记录（`SecretVersion`）、per-account release-key（BLS12-381 阈值 DKG）、proxy registry、ACL、release receipt
- 配合 0x05 TEE Verifier 做 attestation 校验（`tee_required` 路径，CIP-24 §3.3）
- 详见 [[../concepts/runner-verification]]（仅简要；CBSS 自有 wiki 概念待补）

### TEE Verifier（0x05）
- 当前实装：trusted key 表 + attestation 记录的写入（opcodes 60-63 `RegisterTeeTrustedKey` / `RevokeTeeTrustedKey` / `SubmitTeeAttestation` / `RevokeTeeAttestation`，CIP-24 §3.3）
- CIP-23 v2 设计的完整 CAE 流水线（证书链、measurement 白名单、`REPORTDATA` 绑定、NRAS token）属 spec-only，激活时 opcodes 落 ≥87 free range（详见 CIP-13 §1 主表）
- 详见 [[../concepts/tee-attestation]]

### Dual Basefee（0x06）
- 持久化 `basefee_cycles`、`basefee_cells` 每块更新
- `TimerConfig` 也存这里（CIP-5 revised）
- 公式见 [[../concepts/basefee]]

### Entitlement Registry（0x07）
- 统一权限抽象：`Scope` × `Action` × `Constraints` × `Role`
- 详见 `refs/runner/2026-03-03_Entitlement.md`；CIP-14/15/16 v2 各拟新增 1 个 entry（`ingress.http` / `ingress.static` / `dns.attach_external`）属激活 precondition

### Governance（0x09）
- **当前实装**：`SettlementConfig`、`Proposal` 表、`PROPOSAL_COUNTER_KEY`、`BasefeeConfig`
- 提案类型（`ProposalPayloadKind`）：
  - `UpdateBasefeeConfig`（CIP-3）—— 通过 opcode 45 `SubmitProposal` 路径（裸 proposal）
  - `DrainRelay`（CIP-9 §13.3）—— opcode 85 `SubmitDrainRelayProposal` ✅ 代码
  - `UpdateAutoDrainPolicy`（CIP-9 §13.4）—— opcode 86 `SubmitAutoDrainPolicyProposal` ✅ 代码
- `CastVote` (opcode 46) / `ExecuteProposal` (opcode 47) 通用执行路径
- **CIP-12 完整治理设计**（双院、Tier 0-4、Security Council）属 spec-only；详见 [[../concepts/governance]]

### Storage Manager（0x0A，CIP-9）
- `StorageCommitment` 记录、CapToken issuance/revoke、Relay 调度
- PoR 挑战 timer 的 `fee_payer = 0x0A`（CIP-9 v2 §12）
- CIP-15 v2 拟扩展 route_manifest / cors_config（spec-only）

### Relay Registry（0x0B，CIP-9）
- 中继节点 profile + active list + shard 分配
- **CIP-9 §13.4 自动排水策略**存这里：`0x0B:AUTO_DRAIN_POLICY_KEY` ✅ 代码
- 治理-触发排水扫描队列：`auto_drain_governance_scan_key(...)`（CIP-9 §13.3）

### Session Actor（0x0C，CIP-8）
- MPP Session 模型：payer `OpenSession` 托管 `max_amount`；客户端经 EIP-712 voucher 累积 cumulative_amount；Runner 周期 `Settle` 链上结算；`CloseSession` → dispute → `Finalize` 退款
- **opcodes 52-57**（`SessionOpen` / `Deposit` / `Settle` / `Close` / `Finalize` / `Slash`）✅ 代码
- 详见 [[../concepts/mpp-session]]

### Event Subscription System Actor（0x1D，CIP-29，**虚拟**）
- **机制**：`pvm_host::call_actor` 拦截目标为 `0x1D` 的调用，路由到 `execution::event_sub_system_actor::dispatch_rpc`；不部署 actor 代码
- **三个只读 RPC**：
  - `get_rank(sub_id) -> u32` —— 当前订阅在竞价市场中的排名（0-indexed；< MAX_SYNC_FIRES_PER_TOPIC 即下次 emit 会被同步 fire）
  - `get_topic_orderbook(emitter, topic, limit) -> Vec<OrderbookEntry>` —— 竞价行情前 N 名
  - `get_min_bid_for_rank(emitter, topic, rank) -> u128` —— 进入指定 rank 所需最小出价
- **Phase 2 事件 fire**：emit 时按出价排序，前 `MAX_SYNC_FIRES_PER_TOPIC` 同步 fire；溢出经 DeferredTx 异步 fire（`EmitOrigin` metadata tag，`node/types/src/execution.rs`）
- 详见 CIP-29 §2.6（暂未单建 wiki 概念页）

---

## ~~Spec-only 段（`0x0D-0x13`，待激活）~~ —— 已作废（2026-08-15）

> **[2026-08-15 更正]** 本节旧版把 `0x0D-0x13` 列为「spec-only 待激活」并给了**已过时的地址映射**（ROUTE=0x0D … BANK_ACTOR=0x13）。这些 actor **现已全部在代码声明**（见上方权威地址表 + `runner/src/system_actors.rs`），且最终落位与旧 spec 序列不同：`STREAM_KEY_MANAGER` 占 `0x0D`（非旧写的 `0x12`）、`VALIDATOR_SET` 占 `0x11`，把 ROUTE→`0x0E` / GATEWAY→`0x0F` / RECEIPT→`0x10` / PAYMENT_GATE→`0x12` / CONTAINER→`0x13`；`BANK_ACTOR` 落 `0x16`。旧 spec 沿革（草案地址演变）见 CIP-7/14/16/10/18/28 各文本及 [[../drift]] 历史条目。**以上方权威地址表为准。**

---

## 源文档冲突 / 漂移

历次解决的 v2 v1 重排与 v1 单方面 claim 已在 [[../drift]] 看板归档（C-1 / C-2 / C-3 / C-4 + V-1 / V-3 / V-7）。当前仍开放的项：

1. ~~**V-1**：7 个 spec-only 系统 actor（`0x0D-0x13`）等代码激活~~ —— **已闭合（2026-08-15）**：这些 actor 均已在 `runner/src/system_actors.rs` 声明，落位见上方权威表（较旧 spec 序列后移；`0x0D=STREAM_KEY_MANAGER`、`0x11=VALIDATOR_SET` 占位所致）。
2. **V-3**：CIP-13 v2 / CIP-23 v2 / CIP-10 v2 / CIP-14 v2 / CIP-16 v2 的 opcode 提案与代码撞号；激活时需重号到 free range。CIP-13 §1 主表已重写并显式留 "aspirational allocations" 段。（opcode 层，与上方地址表分开跟踪）

详见 [[../drift]]。

---

## Sources

- `node/runner/src/system_actors.rs` —— `SystemActorAddresses` 宏声明 `0x01-0x1E` 全部映射 + `ALL` 注册表 + `well_known_low_byte_assignments` pin 测试（本页权威来源）
- `node/types/src/constants.rs:146,149,152,156` —— 别名 const（`CBSS_SYSTEM_ACTOR=0x04` / `BASEFEE_SYSTEM_ACTOR=0x06` / `GOVERNANCE_SYSTEM_ACTOR=0x09`） + `EVENT_SUBSCRIPTION_SYSTEM_ACTOR=0x1D`
- `node/execution/src/pvm_host.rs:1867-1881` —— `0x1D` 拦截 dispatch；`pvm_host.rs:1961, 4291` —— 保留段 `0x01..=0x0F` 检查
- `node/execution/src/execution/event_sub_system_actor.rs` —— `0x1D` 的 RPC handler 集合
- `node/types/src/execution.rs:591-699` + `1870-2130` —— `SYS_*` opcode 常量 + Decode dispatch
- `refs/cips/cip-2-offchain-compute.md` —— 顶部 Warning 内 2026-05-26 三段式地址表
- `refs/cips/cip-7-simple-stream-protocol.md` §4 —— Stream Key Manager（spec 文本曾写 `0x12`；代码落 `0x0D`，见上方权威表）
- `refs/cips/cip-8-mpp-session.md` §4 —— Session Actor `0x0C`（追认代码）
- `refs/cips/cip-9-runner-storage.md` §11 / §13 —— Storage Manager `0x0A` + Relay Registry `0x0B` + DrainRelay/AutoDrainPolicy
- `refs/cips/cip-10-runner-containers.md` §1 —— Container Registry `0x10` (v2.r2)
- `refs/cips/cip-12-governance.md` §1 / §7 —— 双院治理 + 系统 actor 范围三段式
- `refs/cips/cip-13-runner-delegation.md` §1 —— **代码权威 opcode 主表**（2026-05-26 重写）
- `refs/cips/cip-14-dns-addressable-actors.md` —— ROUTE/GATEWAY/RECEIPT `0x0D-0x0F` (v2.r2)
- `refs/cips/cip-18-payments.md` §8 / §22 —— PaymentGate `0x11` (r2)
- `refs/cips/cip-23-tee-execution.md` —— TEE Verifier `0x05` 的真实 attestation 流水线设计
- `refs/cips/cip-24-secrets-manager.md` §3 —— CBSS 链上面 + TEE keys opcodes 60-63
- `refs/cips/cip-28-cowboy-agent-banking.md` —— BankActor `0x13` (r1.1) + Code activation note
- `refs/cips/cip-29-on-chain-event-hooks-en.md` §2.6 —— Event Subscription `0x1D` 拦截模型
- `refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md` §13 —— 系统 actor 表（含状态列，2026-05-26 更新）
