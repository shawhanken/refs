---
type: entity
tags: [system-actors, addresses, authoritative]
sources:
  - node/runner/src/system_actors.rs
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/cips/cip-12-governance.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-23-tee-execution.md
  - refs/analysis/2026-04-15_documentation_amendments.md
last_updated: 2026-04-20
status: authoritative
---

# System Actors

Cowboy 在保留地址段注册系统 Actor，实现协议级功能。它们与用户 Actor 同构（消息驱动），但由 Genesis 块初始化、拥有特权操作。原始段 `0x01-0x0B` 已实装；CIP-14 起扩展到双字节段 `0x00NN`。

---

## 权威地址表

| 地址 | 名称 | 职能 | 规范来源 |
|---|---|---|---|
| `0x01` | RUNNER_REGISTRY | Runner 注册、stake 管理、心跳 | CIP-2 §6 |
| `0x02` | JOB_DISPATCHER | 任务分发、VRF 选择、托管 | CIP-2 §3-4 |
| `0x03` | RESULT_VERIFIER | 结果验证、结算、slashing | CIP-2 §5 |
| `0x04` | SECRETS_MANAGER | 加密秘密分发（TEE 配合）| CIP-2 §8 |
| `0x05` | TEE_VERIFIER | TEE attestation 校验 | CIP-2 §8；**CIP-23 全面接线** |
| `0x06` | DUAL_BASEFEE | Cycles/Cells basefee 状态持久化 | CIP-3 |
| `0x07` | ENTITLEMENT_REGISTRY | Scope/Action/Constraints/Role 授权 | CIP-2 §7 |
| `0x08` | TREASURY | 协议国库（slashing / burn 目的地）| — |
| `0x09` | GOVERNANCE | 治理参数（SettlementConfig 等）| CIP-2 §5 结算 |
| `0x0A` | STORAGE_MANAGER | 链下存储协议元数据（CIP-9）| CIP-9 |
| `0x0B` | RELAY_REGISTRY | 中继节点注册（未来）| — |
| `0x0011` 🆕 | ROUTE_REGISTRY | FQDN → actor 映射；注册/续费/外部域绑定 | CIP-14 §7, CIP-16 §7 |
| `0x0012` 🆕 | GATEWAY_REGISTRY | Gateway 节点注册 + 心跳 + command-path 系统中介 `dispatch()` | CIP-14 §9 |

**源**: `node/runner/src/system_actors.rs:13-33`

---

## 关键职责详情

### Runner Registry（0x01）
- 接受 `runner register` 交易，检查 `stake >= 10,000 CBY`（注册 floor）
- 维护 `VerificationMode` 声明、`RateCard`（计费）
- 心跳与下线标记
- **规范扩展（CIP-13, Draft）**：承载 Stake 委托（`DelegationConfig` / `DelegationTranche` / `DelegationTotals` 等存储键族）。详见 [[../concepts/runner-delegation]]。

### Job Dispatcher（0x02）
- 客户 `submit_job` → 托管 bond → VRF + stake-weighted sortition（Fisher-Yates）选 Runner
- 超时后 timeout 重新分发
- 见 [[../concepts/vrf-runner-selection]]

### Result Verifier（0x03）
- 接 Runner 结果（`RunnerResult` + 签名）
- 按 Job 声明的 VerificationMode 验证（[[../concepts/runner-verification]]）
- 结算分成（runner / burn / treasury，见 [[../concepts/settlement-slashing]]）
- Dispute 窗口后才执行 slashing
- **规范扩展（CIP-13, Draft）**：若 Runner 接受委托，`per_runner_share` 再按 `delegator_pool / runner_commission` 拆分到 Active Tranche；`slash_runner()` 级联到 Tranche（per-epoch cap）。见 [[../concepts/runner-delegation]]。

### Dual Basefee（0x06）
- 持久化 `basefee_cycles`、`basefee_cells` 随每块更新
- 由 `storage/src/process_block.rs` 调度 `prepare_block_basefee` / `finalize_block_basefee`
- 公式见 [[../concepts/basefee]]

### Entitlement Registry（0x07）
- 统一权限抽象层：`Scope` × `Action` × `Constraints` × `Role`
- 替代硬编码的 token owner、freeze_authority 等散落检查
- 见 `refs/runner/2026-03-03_Entitlement.md`

### Governance（0x09）
- **当前实装**：存储 `SettlementConfig { runner_percent, burn_percent, treasury_percent }` 于 key `system:settlement_config`；唯一有权 emit `UpdateSettlementConfig`（opcode 40）
- **规范（CIP-12, Draft）**：完整治理 Actor，承载双院投票、Tier 0–4 提案、Temp check、Security Council Cancel/Fast-Track/Circuit-Break、系统 Actor 字节码升级。自身升级必须走 Tier 4 `MetaGovernance { UpgradeGovernance }`；**不可 pause**（会死锁治理）。详见 [[../concepts/governance]]。
- **TEE 根证书治理（CIP-23, Draft）**：通过 `0x05::UpdateCpuRoot` / `UpdateNrasRoot` 指令更新 Intel / AMD / AWS / NVIDIA 根证书；`effective_at` 强制 ≥ 1 week 延迟。

### TEE Verifier（0x05）
- **当前实装**：占位桩，`verify()` 无条件返回 `Ok(())`（见 `runner/crates/tee-verifier/src/verifier.rs`）。
- **规范（CIP-23, Draft）**：承载 CAE（Composite Attestation Envelope）真实验证流水线 —— 证书链 / measurement 白名单 / `REPORTDATA` 绑定 / 服务签名 / NRAS token。**opcodes 50–53**: `VerifyCae`, `UpdateCpuRoot`, `UpdateNrasRoot`, `GcNonces`。measurement 白名单存在 Runner Registry (`0x01.measurement_binding`)，不重复。详见 [[../concepts/tee-attestation]]。

### Route Registry（0x0011，CIP-14 新地址段）
- `name → actor_address` 正向解析 + `actor → names` 反向；`resolve` / `register` / `renew` / `set_actor` 等。
- CIP-16 扩展到三类命名空间：`cowboy.network` / 首party TLD (`.cow`, `.cowboy`) / 外部 FQDN（TXT 挑战 + ACME 委派）。
- 详见 [[route-registry]] / [[../concepts/dns-addressable-actors]] / [[../concepts/custom-domains]]。

### Gateway Registry（0x0012，CIP-14 新地址段）
- Gateway 节点注册 + 心跳（`MAX_GATEWAY_HEALTH = 3600 blocks`）+ stake 锁定（`MIN_GATEWAY_STAKE` 治理设）。
- **Command 路径系统中介**: Gateway 把 HTTP 请求封装为 `dispatch(target, envelope)`，由 `0x0012` 验证"来源是 active Gateway" 后再转发到目标 Actor —— Actor 看到的 `ctx.sender == 0x0012`，天然防伪造。
- 详见 [[gateway]] / [[../concepts/dns-addressable-actors]]。

---

## 源文档冲突 / 漂移

**历史冲突**：白皮书 §9 曾把 `0x01=Messaging`、`0x03=Oracle`，与代码完全冲突。CIP-2 2026-03-09 修订已部分对齐到 `0x04/0x05`，但代码实际扩展到 `0x07-0x0B`。

**workspace CLAUDE.md** 仍列出 `0x91-0x95` 的老地址，应废弃（见 [[../drift]] 条目 B）。CIP-23 §3.2 明确"supersedes conflicting listings in `CLAUDE.md` and `node/types/README.md`"。

**新地址段 `0x0011` / `0x0012`**：CIP-14 首次跳出 `0x01-0x0B` 单字节保留段；实现时需在 `node/runner/src/system_actors.rs` 追加常量并同步 workspace CLAUDE.md。

详见 [`refs/analysis/2026-04-15_documentation_amendments.md §二`](../../analysis/2026-04-15_documentation_amendments.md)。

---

## Sources
- `node/runner/src/system_actors.rs:13-33` — 地址常量定义
- `refs/cips/cip-2-offchain-compute.mdx` — Runner 系统规范
- `refs/cips/cip-3-fee-model.mdx` — Basefee actor
- `refs/cips/cip-9-runner-storage.md` — Storage manager
- `refs/cips/cip-12-governance.md` — `0x09` 完整治理规范（Draft）
- `refs/cips/cip-13-runner-delegation.md` — `0x01` 委托扩展（Draft）
- `refs/cips/cip-14-dns-addressable-actors.md` — `0x0011` / `0x0012` 新地址段（Draft）
- `refs/cips/cip-16-custom-domains.md` — `0x0011` 扩展（TLD / external FQDN, Draft）
- `refs/cips/cip-23-tee-execution.md` — `0x05` 真实 attestation 流水线（Draft）
- `refs/runner/2026-03-03_Entitlement.md` — Entitlement 设计
