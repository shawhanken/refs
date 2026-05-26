---
type: concept
tags: [settlement, slashing, governance, economics, cip-13, cip-14, cip-10]
sources:
  - node/execution/src/runner/verifier.rs
  - node/types/src/execution.rs
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-10-runner-containers.md
  - refs/economics/2026-04-13_fee-audit-report.md
last_updated: 2026-04-21
status: authoritative
---

# Settlement 与 Slashing

Runner 任务的经济结算与惩罚规则。

---

## SettlementConfig（多池 + 治理可调）

持久化在 System Actor `0x09`（GOVERNANCE）下，按 `target_pool` 分多个 key（CIP-14 v2 Part III §6 canonical enum）。每池结构：

```rust
SettlementConfig {
    runner_percent: u16,
    burn_percent: u16,
    treasury_percent: u16,
}
```

三者和 = 10,000（bps）。所有 pool 共用 `UpdateSettlementConfig` (**opcode 40**) 指令，sender 必须 `0x09`，`target_pool` 携带变体：

| target_pool | 池 | 来源 CIP | 存储 key |
|---:|---|---|---|
| 0 | `MAIN` | CIP-3（既有）| `system:settlement_config` |
| 1 | `REGISTRY` | CIP-14 v2 §4.5 | `system:registry_settlement_config` |
| 2 | `GATEWAY_POOL` | CIP-14 v2 §7.4 | `system:gateway_pool_config` |
| 3 | `CONTAINER` | CIP-10 v2 §2 | `system:container_settlement_config` |
| 4 | `REGISTRY_TLD_COW` | CIP-16 v2 §4 (optional override) | `system:registry_tld_cow_config` |
| 5 | `REGISTRY_TLD_COWBOY` | CIP-16 v2 §4 (optional override) | `system:registry_tld_cowboy_config` |
| 6+ | 保留（未来 CIP）| — | — |

handler MUST exhaustive switch；未知 `target_pool` MUST 拒绝以 `ERR_UNKNOWN_POOL`。新池必须 CIP 显式扩展此表（soft governance）。

---

## Tip 分配（正常结算）

用户交易 / Job bond 的 tip（basefee 以上部分）按 SettlementConfig 分配：
- **runner_percent** → Runner
- **burn_percent** → 销毁（从总供给扣除）
- **treasury_percent** → Treasury（`0x08`）

**Basefee 部分 100% burn**（不受 SettlementConfig 影响）。

---

## Slashing 规则

触发条件（详见 [[runner-verification]]）：
- `Deterministic` 模式下字节不匹配
- `MajorityVote` 中的少数派
- TEE attestation 失败
- Dispute 被判定有效

**分配**（`verifier.rs::slash_runner()`）：
- **默认 50% Treasury** (`0x08`) / **50% Burn**
- **CIP-13 v2 §4** 改用 `system:settlement_config.slash_treasury_percent` 治理可调（仍走 `UpdateSettlementConfig` opcode 40，不引入新指令）

**额外效应**:
- `runners_to_slash: Vec<Address>` 挂在 `VerifiedResult`，执行器批量处理
- 若被 slash 后 `stake < MIN_STAKE` → 设 `reputation = 0`（冻结接单）
- 不会直接从 Registry 删除，保留历史可审计

---

## Dispute Window

- `DISPUTE_WINDOW_BLOCKS = 75`
- 结算记为 pending，窗口内可被 dispute 挑战
- 窗口后 finalize；slash（如有）在 finalize 时执行

---

## 委托扩展（CIP-13 v2）

若 Runner 打开 `DelegationConfig` 接受委托，结算与 slash 多一层分账：

- **Settlement**：每 Runner 的份额先按 `delegator_pool = share × total_active / (self + total_active)` 切出，扣 `commission_bps` 后按 Active Tranche `amount` 比例分给 delegator。舍入余数归 Runner（runner/delegator 界）与最小 `tranche_id`（tranche 界）。
- **Slashing**：基底 = `self_stake + Σ slashable_tranches`，其中 slashable 包含 Active 与 `now < claimable_at` 的 Unbonding Tranche。自质押不受封顶；Delegator 侧受 `MAX_DELEGATION_SLASH_PER_EPOCH_BPS`（默认 500 bps）per-epoch 限制；超出差额不跨 epoch 延迟（emit `DelegationSlashCapped`）。Treasury/burn 路由读 SettlementConfig（默认 50/50，治理可调）。
- 详见 [[runner-delegation]]。

---

## 相关
- [[../entities/system-actors]] — 0x03 / 0x08 / 0x09
- [[../entities/runner-lifecycle]] — Phase 6-7
- [[runner-verification]] — 触发 slashing 的场景
- [[runner-delegation]] — 委托分账与 slash 级联（Draft）
- [[governance]] — `SettlementConfig` 与 `0x09` 的完整规范（Draft）
- [[dual-gas-model]] — Tip 源于双 gas 计费
- [[../parameters]] — DISPUTE_WINDOW_BLOCKS
