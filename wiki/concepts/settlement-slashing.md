---
type: concept
tags: [settlement, slashing, governance, economics]
sources:
  - node/execution/src/runner/verifier.rs
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/economics/2026-04-13_fee-audit-report.md
last_updated: 2026-04-15
status: authoritative
---

# Settlement 与 Slashing

Runner 任务的经济结算与惩罚规则。

---

## SettlementConfig

持久化在 System Actor `0x09`（GOVERNANCE）下 key `system:settlement_config`：

```rust
SettlementConfig {
    runner_percent: u16,
    burn_percent: u16,
    treasury_percent: u16,
}
```

三者和 = 10,000（bps）。默认值由治理设定，可通过 `UpdateSettlementConfig`（opcode 40）变更；**仅 `0x09` 有权发起**（`system_instruction.rs` 授权检查）。

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
- **50% Treasury**（`0x08`）
- **50% Burn**

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

## 相关
- [[../entities/system-actors]] — 0x03 / 0x08 / 0x09
- [[../entities/runner-lifecycle]] — Phase 6-7
- [[runner-verification]] — 触发 slashing 的场景
- [[dual-gas-model]] — Tip 源于双 gas 计费
- [[../parameters]] — DISPUTE_WINDOW_BLOCKS
