# CIP-28 BankActor — M2 (default-card gas charging) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Let an agent's transactions pay gas from its **default bank card** — `SetDefaultCard` + a `BankActor.charge_gas` reserve/settle fork in the fee-settle path, gated by a `BANK_ACTIVATION_HEIGHT` flag-day const. Delivers "every agent has a default card that auto-pays its gas" **without touching the Transaction wire format**.

**Architecture:** Reuses the existing per-actor fee-settle two-phase structure in `execute_transaction` (escrow at `transaction.rs:180-201`, settle/refund at `:442-506`) and models the distinct-sponsor debit/refund on the proven **timer `fee_payer_override` precedent** (`storage/src/speculative.rs:1727-1856`). Card charging is priced at **snapshotted dual basefees** (like the timer `max_cost`), not the tx `max_fee`. A card is detected via `bank::storage::read_card` under `0x16`, probed only when `tx.from` is an actor with a default card (keeps the no-card hot path free).

**Tech Stack:** Rust. `cowboy-protocol` codec (branch off M1 codec tip `18fe165`) + `node` (branch off M1 branch `feat/cip28-bankactor-m1`, stacked). Stacked on M1 (PRs cowboy-protocol#47 / node#1078).

---

## Decisions (marked; defaults per the 2026-07-20 baseline maps)

1. **Scope = default-card path ONLY (decided 2026-07-20).** CIP-28 §2.7 item 2 (`tx.from` is an actor with `agent_default_card` → charge_gas). The explicit tx-level `fee_payer_override` (§2.7 item 1) is **deferred** — it requires a `Transaction` wire field = a hard flag-day (bump `CURRENT_TX_VERSION` 1→2, regenerate all 7 golden vectors, rebuild+republish `@cowboyinc/protocol-wasm` for wallet, validator-coordinated fork; `tx_format` is `FORK_ONLY`, cannot go through 0x09). M2a needs **no tx wire change, no version bump, no golden regen, no wallet rebuild**.
2. **Activation = compile-time const `BANK_ACTIVATION_HEIGHT: u64 = u64::MAX`** in `node/types/src/constants.rs` beside `CBSS_PAUSE_REJECT_ACTIVATION_HEIGHT` (the #934 land-gated-off-by-default doctrine). Deterministic, genesis-independent. Deploy either via **fresh re-genesis** (set height 0, stacked on M1's re-genesis) OR **in-place upgrade** of a running chain (set a future height, cut a release). The `SetDefaultCard` opcode (204) is a NEW decodable type → gate it at **mempool admission + `verify()`** below the height (a legacy node can't decode it, so it must never be included below height — mirror the M1 A4 analysis / CIP-15 `gate_route_serving_endpoint` shape). The `charge_gas` behavior change is gated at **execution** (below height → actor pays own balance, byte-identical to legacy).
3. **`charge_gas` M2 scope = reserve/settle only; NO policy/cap/window enforcement** (that is CIP-28 M3). Phase-1: static checks (bank Active, card Active, not expired) + CIP-3 reserve at snapshotted basefee + balance check + debit the card's funding account. Phase-2: recompute actual at the snapshotted basefees + refund the difference to the card. `SpendWindow` roll + `per_hour/day/month_cap` + `allowed_receivers`/`allowed_syscall_kinds` enforcement are **M3** (the card entry already carries the fields; M2 does not read them for enforcement).
4. **Native gas only in M2.** `charge_gas` charges from a card whose `gas_payment_token == Native` (attoCBY from the card's `Account.balance`). A `Token(U)` gas card needs the genesis-fixed peg (CIP-28 §4.4) — **deferred**; when `tx.from`'s default card is Token-gas, M2 **falls back to the normal actor-pays path** (own balance), tx still executes. Document.
5. **Hot-path guard.** Probe `read_card`/`agent_default_card` ONLY when `tx.from` resolves to an actor address (not a plain EOA) and the block is at/above `BANK_ACTIVATION_HEIGHT`. Add/read the `b"agent_default_card:" || agent` key only in that branch, so ordinary EOA txs pay zero extra reads.

---

## Deep-audit revisions (2026-07-20 — BINDING; supersede conflicting text below)

A 3-lens plan audit found a fundamental keying flaw + consensus-fatal gaps. Decision (2026-07-20): re-key card-pays off the **callee actor**, which collapses most of the fixes. These win over any conflicting task text:

- **RH1 (was H1, CRITICAL) — key card-pays off the `ExecuteActor` CALLEE, not `tx.from`.** As-built, `tx.from` is the ecrecover'd EOA signer (`transaction.rs:101-119,234`) — a PVM actor holds no key, so `get_actor(tx.from)` is ~never `Some`; and actor-origin txs are CIP-34 deferred Intents that `return` before the fee fork. The reachable flow is `Instruction::Actor(ExecuteActor{actor})` where the agent is the **callee**. **Integrate at the existing actor-pays tier (`transaction.rs:449-469`)**: when the tx is `ExecuteActor{actor}`, `block_height >= BANK_ACTIVATION_HEIGHT`, and `actor` has a Native, Active default card, debit the card **instead of** `actor_account.balance` for the actor's fee portion. Semantics: "the agent's card subsidizes calls to the agent" (≈ CIP-18 actor-funded).
- **RH2 (was DEFECT1/H3/DEFECT3, CRITICAL) — conservation is now automatic; NO ReservationToken / two-phase / snapshot-basefee.** Because we hook at the settle tier, `total_fee` (the actual, `:440`) is already known — the card pays it in ONE debit, a drop-in replacement of the actor debit. The **sender escrow (`:180-201`) and refund (`:505`) are UNTOUCHED** (sender escrows, `sender_pays` drops by what the card covered, sender refunded) → supply conserved with no new mechanism, no mint, no double-burn, and no zero-balance-actor stranding (the actor is the callee, not the sender). Task 3 is **rewritten** below to this model; the old reserve/settle/ReservationToken design is void.
- **RH3 (was H4/M1, resolved) — insufficient/Token/inactive card falls through to the existing owner→sender residual cascade** (exactly today's actor-pays behavior), so nothing bricks and there is one consistent behavior (no reject-vs-fallback split). A `Token(U)` gas card is treated as "can't pay CBY fees in M2" → fall through (M3 adds the peg).
- **RH4 (was fork-class DEFECT, CRITICAL) — opcode-204 gate MUST be a block-level `do_verify()` content scan** that `return false` below `BANK_ACTIVATION_HEIGHT`, modeled on `block_has_foreign_chain_tx` (`application.rs:2481`, used at `:2026-2033`), **plus** propose/mempool exclusion. A tx-level `Err` gate (the `cbss_pause_gate` shape the old plan cited) yields a *failed receipt in a still-valid block* that upgraded `verify()` accepts while legacy nodes reject the undecodable block → the M1-A4 decode fork. Do NOT use the tx-level shape for the new opcode.
- **RH5 (was H2, HIGH) — `CloseCard` must gain the §3.1 "not the default card" guard AND clear the `agent_default_card` pointer on close.** M1's `bank_close_card` predates default cards; without this a closed default bricks the agent. Add to Task 2.
- **RH6 — deploy invariant + #934 two-step (state explicitly).** M2 in-place upgrades are applied ONLY to an already-M1-live chain (200-203 already decode everywhere); there is no pre-bank→M1+M2 in-place path. M2 binaries ship `BANK_ACTIVATION_HEIGHT = u64::MAX`; a *follow-up* release sets the real height after full validator upgrade. On a fresh M1+M2 re-genesis, height = 0 and the gate's below-height branch is exercised only in tests — so its block-level `do_verify` semantics (RH4) must still be correct for the future in-place cut.
- **RH7 — defer `GasCharged` event to M3.** M2 emits NO `GasCharged` event (avoids the unregistered-topic / can't-attribute-to-0x16 / truncated-payload problems: the emitter keys off the instruction, and this fires from an arbitrary `ExecuteActor` tx). The card debit is observable in account state. M3 adds `GasCharged` with the full §3.6 payload (`tx_digest,receiver,syscall_kind,…`) and a dedicated 0x16 attribution channel.
- **RH8 — defer timer-deferred card integration to M3** (Task 4 removed from M2). It needs the same callee/sponsor reconciliation; the M2 headline (calls to an agent are gassed by the agent's card) doesn't require it.
- **RL1 — activation-safety coupling (document):** with caps deferred to M3, an activated M2 lets a compromised agent drain the whole default-card balance on gas (bounded by the card balance — the vault caps blast radius to the card, not the owner's wallet). **M2 MUST NOT be activated in production ahead of M3.** Note in the const doc-comment.

**Net:** M2 is now SIMPLER — a drop-in card debit at the actor-pays tier (no reservation machinery), a block-level opcode gate, a CloseCard guard, and two deferrals (GasCharged, timer). Decisions 3 (no caps), 5 (hot-path guard — now: probe only for `ExecuteActor` callees at/above height) stand. Decision 4 is replaced by RH3 (fall-through, not silent actor-pay divert).

## Baseline anchors (from the 2026-07-20 maps — verify before editing)

- Fee-settle entry: `execution/src/execution/transaction.rs::execute_transaction` (:47-67). Escrow debit `:180-201` (`sender.balance -= max_total_cost`). Settle cascade + `gas_refund` `:442-506`. Fee domain **u64**; basefees **u128** (`self.current_basefee: DualBasefee`, `basefee.rs:42-48`).
- CIP-3 settle math: `basefee.rs::compute_tx_fees` (:448-475); lane-effective `effective_for_lane` (:430-435).
- Timer sponsor precedent (the reserve/refund template): precharge `storage/src/speculative.rs:1727-1748`; settle+refund `:1818-1858`; `set_timer_fee_payer` skip-double-charge `:1779-1780` + `transaction.rs:881-886`.
- Card read: `bank::storage::read_card` (`execution/src/bank/storage.rs:166`), `card_key` (`:38`). `CardEntry` (`bank/mod.rs:404-418`): `bank_id, owner, agent, status, gas_payment_token, policy, window`.
- Activation precedents: const `CBSS_PAUSE_REJECT_ACTIVATION_HEIGHT` (`types/constants.rs:611`); gate shape `execution/src/runner/registry.rs::gate_route_serving_endpoint` (:101-115); admission gate `cbss_pause_gate.rs:267-282` wired at `system_instruction.rs:48-56`.
- Async: use `execution::actor_instruction::block_on_local` (`:46-72`), NOT `futures::executor::block_on`.
- New opcode: `SYS_BANK_SET_DEFAULT_CARD = 204` (200-203 taken by M1; 204 free).

---

## File structure
**`cowboy-protocol`:** `crates/cowboy-protocol-codec/src/instruction.rs` — `SYS_BANK_SET_DEFAULT_CARD=204` + `BankSetDefaultCard { agent: Address, card_address: Option<Address> }` variant + codec arms.
**`node`:**
- `types/src/constants.rs` — `BANK_ACTIVATION_HEIGHT`.
- `types/src/execution.rs` — `sys_opcode_uniqueness` row 204.
- `execution/src/bank/storage.rs` — `agent_default_card_key` + `read/write/delete_default_card`.
- `execution/src/bank/handlers.rs` — `set_default_card` handler; `charge_gas` Phase-1/Phase-2 + `ReservationToken`.
- `execution/src/execution/system_instruction.rs` — `BankSetDefaultCard` dispatch arm (in the bank outer-guard) + admission/verify height gate on opcode 204.
- `execution/src/execution/bank_pause_gate.rs` — add `BankSetDefaultCard` to the classifier.
- `execution/src/execution/transaction.rs` — the payer-resolution fork (Phase-1 at :180, Phase-2 at :442), height-gated.
- `storage/src/speculative.rs` — `system_event_emitter` + actor-classifier arms for `BankSetDefaultCard`; timer-path card status check (T4).
- `indexer/src/json.rs` — `BankSetDefaultCard` arm.
- `chain/src/genesis.rs` — (only if a genesis `bank_activation_height` data field is chosen over the const; default = const, so no genesis change).

---

## Task 0: Dev setup (stacked branches)
Branch `feat/cip28-bankactor-m2` in both repos, based on the M1 branches:
```bash
cd /home/ubuntu/workspace/cowboy-protocol && git checkout -b feat/cip28-bankactor-m2 feat/cip28-bankactor-m1
cd /home/ubuntu/workspace/node && git checkout -b feat/cip28-bankactor-m2 feat/cip28-bankactor-m1
```
Re-add the dev `[patch]` to `node/Cargo.toml` (points `cowboy-protocol-codec` at the on-disk sibling so M2 codec changes build) — same as M1 Task 0. `cargo build -p cowboy-types`. Commit the patch (node). Do NOT push.

## Task 1: Codec — `BankSetDefaultCard` opcode 204 (additive)
Mirror M1's `BankCloseCard`. `SYS_BANK_SET_DEFAULT_CARD = 204`; variant `BankSetDefaultCard { agent: Address, card_address: Option<Address> }` (`card_address` = `None` clears the default). Add sub_type/encode/encode_size/decode arms; `Option<Address>` uses the manual present/absent tag. Roundtrip + opcode-204 tests. Golden vectors untouched (pure addition). Commit (codec).

## Task 2: Node — const, storage, SetDefaultCard handler + gated dispatch
- [ ] `BANK_ACTIVATION_HEIGHT: u64 = u64::MAX` in `constants.rs` (doc: #934 land-gated-off; re-genesis sets 0).
- [ ] `sys_opcode_uniqueness` row `("SYS_BANK_SET_DEFAULT_CARD", 204)`.
- [ ] `bank/storage.rs`: `agent_default_card_key(agent) = b"agent_default_card:" || agent(20)`; `read_default_card(store, agent) -> Option<Address>`, `write_default_card`, `delete_default_card`. Key-layout test.
- [ ] `bank/handlers.rs::set_default_card(store, agent, card_address: Option<Address>, caller)`: caller == agent OR caller == card.owner (load card to check owner when Some); if `Some(addr)`: `read_card(addr)` exists, `card.agent == agent`, `card.status == Active`; write; if `None`: delete. Emit `CardDefaultSet`. Register the topic.
- [ ] **`set_default_card` for `None` (RL2 fix):** for `card_address = None`, load the *current* default (`read_default_card(agent)`) and allow the clear if `caller == agent` OR `caller == current_default_card.owner`; else reject. (Otherwise only the agent could ever unset, deviating from §3.2.)
- [ ] Dispatch: add `BankSetDefaultCard` to the bank outer-guard arm + inner match in `system_instruction.rs`; add to `bank_pause_gate` classifier, `speculative.rs` emitter (→ `Some(BANK_ACTOR_SYSTEM_ACTOR)`) + actor-classifier, `indexer/json.rs`.
- [ ] **RH5 — amend M1 `bank_close_card`:** reject if the card is the agent's default (§3.1 "not the default card"); on a successful close also `delete_default_card(card.agent)` if it pointed here (belt-and-suspenders against a dangling pointer). Add a test: close-of-default rejected; and (if close is allowed after unset) the pointer is cleared.
- [ ] **RH4 — block-level opcode-204 gate (NOT tx-level).** A `BankSetDefaultCard` (opcode 204) is a NEW decodable type; a legacy node can't decode it, so below `BANK_ACTIVATION_HEIGHT` the block must be rejected **wholesale**, matching legacy. Implement as: (a) `do_verify()` scans `block.transactions` and `return false` if any tx is opcode-204 and `block_height < BANK_ACTIVATION_HEIGHT` — model on `block_has_foreign_chain_tx` (`application.rs:2481`, used at `:2026-2033`); (b) propose/mempool exclusion below height (necessary, not sufficient). Do NOT use a tx-level `Err` gate (`cbss_pause_gate` shape) — that yields a failed receipt in a still-valid block that upgraded `verify()` accepts while legacy rejects the undecodable block = decode fork (RH4). Test: a block containing a 204 tx below height → `do_verify` returns false; at/above height → accepted.
Tests: handler happy/reject paths; the block-level gate (below-height block reject); storage round-trip.

## Task 3: `BankActor.charge_gas` + fee-settle fork (the consensus core)
> **REWRITTEN per RH1/RH2/RH3.** No `ReservationToken`, no two-phase reserve, no snapshot basefee. The card is a **drop-in debit at the actor-pays settle tier** where the actual fee is already known; sender escrow/refund are untouched → conservation is automatic; insufficient/ineligible card falls through the existing owner→sender residual cascade.

- [ ] **`bank_charge_gas(store, card_addr, amount: u64, block_height) -> Result<u64, ExecutionError>`** (in `bank/handlers.rs`): returns how much of `amount` the card actually covered. Load `read_card` (missing/None → return `0` = card covered nothing, caller falls through); load `read_bank(card.bank_id)`; **eligibility (all → return `0`/fall-through, NOT an error): `bank.status == Active`, `card.status == Active`, `expires_at.map(|e| block_height < e).unwrap_or(true)`, `card.gas_payment_token == Native`**; then `covered = amount.min(card_account.balance)`; debit `card_account.balance -= covered`; persist; return `covered`. NO caps/window (M3), NO event (RH7). check-then-apply: the debit is the only write and happens after all eligibility checks.
- [ ] **Hook at the actor-pays tier** (`transaction.rs:449-469`). Today: `let from_actor = total_fee.min(actor_account.balance); actor_account.balance -= from_actor;`. Change to: **before** debiting the actor's own balance, when `block_height >= BANK_ACTIVATION_HEIGHT` and `read_default_card(actor)` is `Some(card)`, try `let from_card = bank_charge_gas(store, &card, total_fee, block_height)?;` — the card covers `from_card`; only the *remainder* (`total_fee - from_card`) proceeds to the existing actor-own-balance debit, then the owner→sender residual cascade (unchanged). If no default card / below height, behavior is byte-identical to today. The `read_default_card(actor)` probe is the ONLY new read and fires only for `ExecuteActor` callees at/above the height (Decision 5 hot-path guard).
- [ ] **Do NOT touch** `:180-201` (sender escrow) or `:505-509` (refund + burn/tip accumulation). `total_fee` and the burn/tip split are computed exactly as today (`:430-440`); the card just changes *who* funds the actor's share, so `block_burn`/`block_tip` and the sender refund stay conserved automatically. (Card gas therefore currently includes the same burn+tip split the actor would have paid — i.e. the agent's card DOES fund the proposer tip. If CIP-28 §4.2 basefee-only-no-tip is desired, that is an M3 refinement; M2's drop-in keeps conservation trivial by paying the same `total_fee` the actor-pays tier already used.)
- [ ] **Async:** the settle tier is already `async`/`.await`; keep `bank_charge_gas` async (`store.get_account(...).await`), no `block_on_local` needed here.

Tests (conservation is the key one):
- Native default card on the callee `actor` funds the tx: card balance drops by `total_fee`, `actor`'s own balance untouched, sender escrow refunded as usual; **`block_burn + block_tip` delta == card debit** and total supply conserved (assert).
- Card can't fully cover → remainder falls to actor-own then owner→sender residual (existing cascade), tx still succeeds; conserved.
- Token-gas / Frozen / Expired / Closed default card, or no default card → byte-identical to today (actor pays own balance).
- Below `BANK_ACTIVATION_HEIGHT` → card ignored, byte-identical to legacy.

## Task 4: Full workspace green + finalize (GATED)
`cargo build/test/clippy --workspace` green; mop up exhaustive matches for opcode 204; golden vectors (codec) untouched. **Finalize (user-gated):** codec PR (base = M1 codec branch or main after M1 merges) + node PR (base = `feat/cip28-bankactor-m1`, stacked) + rev-pin bump. Do NOT push without explicit user authorization.

---

## Staging beyond M2
- **M2b (deferred)** — explicit tx `fee_payer_override` (the wire flag-day: version 1→2, golden regen, wallet WASM).
- **M3** — `SetPolicy`; enforce `SpendWindow` caps + `allowed_receivers`/`allowed_syscall_kinds` inside `charge_gas`; `Freeze`/`Unfreeze`/`PauseBank`; `locked_after_transfer`. Token(U)-gas via genesis peg (§4.4).
- **M4** — `MintFromFiatVoucher` + `issuance_principal` population; off-chain gateway. **settle_provider (CIP-36 §6.3)** on M4 + W1 `burn_from`.
- **M5** — `RegisterBank`/`SetBankOperator`; multi-bank; `TransferOwnership`.

## Self-review vs CIP-28 §7.2 M2 (post-audit)
- SetDefaultCard → Task 1+2. Card-pays fee fork (callee-keyed drop-in at the actor-pays tier) → Task 3. Deferred correctly: explicit tx `fee_payer_override` (M2b — wire flag-day, Decision 1); policy/cap/window enforcement + `GasCharged` event + timer-card integration + Token(U)-gas peg (M3, RH7/RH8/Decision 3); actor-origin/CIP-34-deferred card payment (out of scope — those bypass the fee fork). Consensus/flag-day: `BANK_ACTIVATION_HEIGHT` const (u64::MAX, #934 two-step, RH6), **block-level `do_verify` opcode-204 gate (RH4)**, conservation-by-construction (RH2 — sender escrow/refund untouched). Activation-safety: MUST NOT activate before M3 (RL1). Semantics: agent's card subsidizes calls to the agent (RH1).
