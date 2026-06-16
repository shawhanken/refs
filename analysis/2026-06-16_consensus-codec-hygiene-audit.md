# Consensus-Codec Hygiene Audit (codebase-wide)

**Date:** 2026-06-16 · **Marshal round-6** (3 parallel auditors: state_root / receipt_root / block+grep).
**Scope:** every type Merkle-hashed into a consensus root (`state_root`, `receipt_root`/`logs_root`,
`block_hash`), checked for the 5 non-canonical-codec defect patterns the tx work surfaced
(non-injective discriminant, non-strict bool/enum, pad/truncate, trailing-optional, embedded
serde/HashMap/float). This is the **generalization of B7** (`Message` in state_root), a separate
scope from the tx-canonical plan.

## Headline

**This is a handful of point-fixes, not systemic rot.** The consensus-hash path is mostly
canonical-by-construction: `Block`/`logs_root`/`ConsumedSeedsV1` use manual length-prefixed
keccak; `StateValue`/`Account`/`Actor`/`Value` and the cbss enums use strict
`_ => Err(InvalidEnum)` discriminants. A strict-codec discipline is already taking hold
(`MessagePriority::try_from_u8`, `ConsumedSeedsV1` strict decoder — both almanax-driven).

## Key clarification (resolves the auditors' apparent disagreement)

The `Instruction::Custom` / `accept_delegation` / `Constraints` defects live in the
**`commonware-codec` `Instruction` codec, which is TEST-ONLY today** — production `Transaction::Write`
(`execution.rs:397`) is serde-CBOR (`into_writer`), so the commonware `Instruction::Write`/`Read`
is not on any live consensus-hash path. **The tx-canonical plan ACTIVATES them**: once
`Transaction` switches to commonware-codec, `StateValue::DeferredTx(Transaction)` (state_root) and
`Block.transactions` (tx_root) both route through the commonware `Instruction` codec. Therefore
**plan Tasks 2b/2c (Custom injectivity + strict bools) are a necessary PREREQUISITE of the tx
plan**, not fixes to a currently-live bug. The codebase is healthier than the tx audit implied.

## Findings (consensus-hashed types only)

| # | Site | Pattern | Root | Status | Severity |
|---|------|---------|------|--------|----------|
| 1 | `Message::read` `MessageType::from_u8` maps out-of-range → `Regular` (`execution.rs:4789`/`:4639`) | #2 non-strict enum | state_root (`StateValue::MailboxMessage`) | **NEW (pinpoints B7)** | MEDIUM |
| 2 | `Message::read` `has_origin == 1 else None` (`execution.rs:4782`); byte 2 → None | #2 | state_root | known (B7) | LOW-MED |
| 3 | `Message::read` trailing `has_remaining()` block (`execution.rs:4788`) | #4 | state_root | known (B7) | LOW (partly mitigated — priority/expires moved to StateValue V2) |
| 4 | `TransactionReceipt::Read` `bloom` `_ => None` catch-all (`storage/types.rs:935`) | #1/#2 | receipt_root | **NEW** | LOW¹ |
| 5 | `TransactionReceipt::Read` 5× chained trailing `has_remaining()` (`storage/types.rs:903-940`) | #4 | receipt_root | **NEW** | LOW¹ |
| 6 | `Instruction::Custom` raw-discriminant collision (`execution.rs:2554`/`:3348`) | #1 | latent → tx_root+state_root after plan | known (R1) | HIGH **iff plan lands** — fixed by Task 2b |
| 7 | `Constraints` `delegatable`/`revocable` `as u8`/`!= 0` (`entitlement.rs:326/367`) | #2 | latent → state_root after plan | known (R2) | HIGH **iff plan lands** — Task 2c |
| 8 | `accept_delegation` `u8 != 0` (`execution.rs:2845`) | #2 | latent → state_root after plan | known (R6) | HIGH **iff plan lands** — Task 2c |
| 9 | `SessionVoucher` pad/truncate (`session.rs:154`) | #3 | none (RPC voucher, not a state codec) | known (R8) | LOW (wire only) |

¹ **receipt_root is `Write`-only canonical:** the replay/verify path rebuilds receipts from
execution and never decodes-then-rehashes (`state_invariants.rs:480`, `speculative.rs:1485`), so
`TransactionReceipt::Read` defects are RPC/storage round-trip bugs, **not** receipt_root
malleability. (Contrast `state_root`: state-sync decodes `StateValue` from untrusted peer bytes
(`state_sync.rs:11`), so state-codec Read strictness does matter there.)

## Verified CLEAN (auditable coverage)

- **state_root / `StateValue` family (16 variants):** `StateValue` outer enum, `Account`, `Actor`
  (+`ActorManifest`/`EntitlementGrant`/`ParamValue`, `BTreeMap` deterministic), `Timer`/`TimerList`,
  `DeferredTxList`, `ActorEventList`/`ActorEvent`, `ActorLibrary`/`ActorLibPin`,
  `ActorEventSubscription`, `EventSubIndex(+Entry)`, `FairnessCounter` (fixed-ring `!= WINDOW → Err`),
  `ActorStorageEntry`/`SystemBytes`/`Code` (capped `Vec<u8>`), `MessagePriority` (strict `try_from_u8`).
- **receipt_root family:** `ExecutionStatus` (strict `_ => InvalidEnum`), `StructuredError` Write
  (injective; `from_code` deterministic static-slice lookup, unknown→`E1900` preserving raw code),
  `compute_logs_root` (uniform `u32`-BE, golden-vector-pinned), `compute_bloom`, event payload
  encoders (opaque deterministic blobs; mixed LE/BE internal but per-producer deterministic).
- **block_hash:** `Block::compute_digest` (manual length-prefixed keccak; `extra_data` excluded),
  `Notarized`/`Finalized` (cross-check `proof.payload == block.digest()`), `ConsumedSeedsV1`
  (hand-written canonical CBOR + strict decoder — gold standard).
- **grep sweep:** all `serde_json`/`ciborium`/`bincode`/`HashMap` hits in consensus types are either
  `#[cfg(test)]`, WASM/JS bindings, or over all-integer/`BTreeMap` structs (deterministic). `FaultClass`/
  `ChallengeReason` write `as u8` but read strict `_ => InvalidEnum`. No floats in any consensus type.

## Recommendations (→ tickets; auto-mode blocks unrequested issueCreate, so fold into a human-filed ticket)

1. **`Message::read` strict + injective** (findings 1–3): replace `MessageType::from_u8` with a
   strict `try_from_u8 → Err` (mirror the `MessagePriority` hardening), make `has_origin` a strict
   `0/1/_=>Err` tag, and resolve the trailing-`has_remaining()` tail (version-gate it like `Timer`).
   MEDIUM, state_root-reachable via state-sync. **Separate ticket** (independent of the tx plan).
2. **`TransactionReceipt::Read` strictness** (findings 4–5): strict `bloom` tag + drop the
   trailing-optional chain (version-gate). LOW (Write-canonical), but tidy + matches the discipline.
   **Separate ticket.**
3. **Shared strict-codec helpers** (cheap insurance): a `read_strict_bool` and
   `read_enum_or_err`/`try_from_u8` helper used everywhere, so `as u8`/`!= 0`/`from_u8` cannot
   reappear. Optional; the codebase does not show pervasive failure demanding a sweep.
4. **Findings 6–8 are already owned by the tx-canonical plan** (Tasks 2b/2c) as prerequisites.
   No separate ticket; just don't land the tx-codec switch without them.

## Bottom line

Six audit rounds (tx-codec internals ×4, tx regressions+adjacent ×1, codebase-wide hygiene ×1)
converge: the tx-canonical design+plan is implementable with its folded fixes; the broader
codebase has **2 small additional consensus-codec point-fixes** (`Message`, `TransactionReceipt`
Read) worth separate tickets, and is otherwise canonical-by-construction. No systemic rewrite needed.
