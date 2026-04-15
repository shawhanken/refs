---
type: entity
tags: [system-actors, addresses, authoritative]
sources:
  - node/runner/src/system_actors.rs
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/analysis/2026-04-15_documentation_amendments.md
last_updated: 2026-04-15
status: authoritative
---

# System Actors

Cowboy 在保留地址（`0x01` - `0x0B`）上注册系统 Actor，实现协议级功能。它们与用户 Actor 同构（消息驱动），但由 Genesis 块初始化、拥有特权操作。

---

## 权威地址表

| 地址 | 名称 | 职能 | 规范来源 |
|---|---|---|---|
| `0x01` | RUNNER_REGISTRY | Runner 注册、stake 管理、心跳 | CIP-2 §6 |
| `0x02` | JOB_DISPATCHER | 任务分发、VRF 选择、托管 | CIP-2 §3-4 |
| `0x03` | RESULT_VERIFIER | 结果验证、结算、slashing | CIP-2 §5 |
| `0x04` | SECRETS_MANAGER | 加密秘密分发（TEE 配合）| CIP-2 §8 |
| `0x05` | TEE_VERIFIER | TEE attestation 校验 | CIP-2 §8 |
| `0x06` | DUAL_BASEFEE | Cycles/Cells basefee 状态持久化 | CIP-3 |
| `0x07` | ENTITLEMENT_REGISTRY | Scope/Action/Constraints/Role 授权 | CIP-2 §7 |
| `0x08` | TREASURY | 协议国库（slashing / burn 目的地）| — |
| `0x09` | GOVERNANCE | 治理参数（SettlementConfig 等）| CIP-2 §5 结算 |
| `0x0A` | STORAGE_MANAGER | 链下存储协议元数据（CIP-9）| CIP-9 |
| `0x0B` | RELAY_REGISTRY | 中继节点注册（未来）| — |

**源**: `node/runner/src/system_actors.rs:13-33`

---

## 关键职责详情

### Runner Registry（0x01）
- 接受 `runner register` 交易，检查 `stake >= 10,000 CBY`（注册 floor）
- 维护 `VerificationMode` 声明、`RateCard`（计费）
- 心跳与下线标记

### Job Dispatcher（0x02）
- 客户 `submit_job` → 托管 bond → VRF + stake-weighted sortition（Fisher-Yates）选 Runner
- 超时后 timeout 重新分发
- 见 [[../concepts/vrf-runner-selection]]

### Result Verifier（0x03）
- 接 Runner 结果（`RunnerResult` + 签名）
- 按 Job 声明的 VerificationMode 验证（[[../concepts/runner-verification]]）
- 结算分成（runner / burn / treasury，见 [[../concepts/settlement-slashing]]）
- Dispute 窗口后才执行 slashing

### Dual Basefee（0x06）
- 持久化 `basefee_cycles`、`basefee_cells` 随每块更新
- 由 `storage/src/process_block.rs` 调度 `prepare_block_basefee` / `finalize_block_basefee`
- 公式见 [[../concepts/basefee]]

### Entitlement Registry（0x07）
- 统一权限抽象层：`Scope` × `Action` × `Constraints` × `Role`
- 替代硬编码的 token owner、freeze_authority 等散落检查
- 见 `refs/runner/2026-03-03_Entitlement.md`

### Governance（0x09）
- 存储 `SettlementConfig { runner_percent, burn_percent, treasury_percent }` 于 key `system:settlement_config`
- 唯一有权 emit `UpdateSettlementConfig`（opcode 40）

---

## 源文档冲突 / 漂移

**历史冲突**：白皮书 §9 曾把 `0x01=Messaging`、`0x03=Oracle`，与代码完全冲突。CIP-2 2026-03-09 修订已部分对齐到 `0x04/0x05`，但代码实际扩展到 `0x07-0x0B`。

**workspace CLAUDE.md** 仍列出 `0x91-0x95` 的老地址，应废弃（见 [[../drift]] 条目 B）。

详见 [`refs/analysis/2026-04-15_documentation_amendments.md §二`](../../analysis/2026-04-15_documentation_amendments.md)。

---

## Sources
- `node/runner/src/system_actors.rs:13-33` — 地址常量定义
- `refs/cips/cip-2-offchain-compute.mdx` — Runner 系统规范
- `refs/cips/cip-3-fee-model.mdx` — Basefee actor
- `refs/cips/cip-9-runner-storage.md` — Storage manager
- `refs/runner/2026-03-03_Entitlement.md` — Entitlement 设计
