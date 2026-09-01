# CIP-28 BankActor M3.5 ("Spend-Path Completion") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the CIP-28 card gas spend-path so a default card actually enforces its `allowed_receivers`/`allowed_syscall_kinds` whitelist at admission, emits the auditable `GasCharged` event, and can pay gas in a whitelisted stablecoin `U` (via a genesis-fixed CBY↔U peg) — all against already-stored policy, with no wire/opcode change.

**Architecture:** Three surgical extensions to the as-built M2/M3 default-card path in `execution/`:
- **Part C (peg)** — a genesis-fixed integer peg under `BANK_ACTOR_SYSTEM_ACTOR (0x16)`; relax card eligibility to admit `Token(U)` cards; settle token gas as a **bank-as-paymaster swap** (`U` card→bank via the CIP-20 hook path, equal `CBY` out of the bank's own liquidity into the fee fold) so both token-supply and CBY tx-fee conservation stay green.
- **Part A (whitelist)** — a pure `syscall_kind_of` + `policy_admits` enforced at the existing M3 A2 pre-execution admission block.
- **Part B (GasCharged)** — a new consensus event topic emitted at the actor-pays settle, attributed to `0x16` via a new inline-emitter route (Actor-instruction events keep their per-tuple emitter), registered in `KNOWN_CONSENSUS_EVENT_TOPICS` (a flag-day consensus surface).

**Tech Stack:** Rust (`cowboy-execution`, `cowboy-chain`, `validator`); hand-rolled fixed-layout BE byte codecs (no serde for on-chain blobs); `tokio::test` + `proptest`; `TestStore` in-memory store.

---

## Deep-audit revisions (BINDING — supersede any conflicting task text below)

Two adversarial plan-audit lenses (conservation/paymaster; whitelist/spec) ran against the draft. The whitelist path (Parts A/B) audited **SOUND, no BLOCKER**. The token-gas paymaster path (Part C) audited **2 BLOCKERs plus a fundamental design conflict**. The rulings below are binding and re-scope this milestone.

- **RV-1 (SCOPE — descope Part C from M3.5). Reason: the bank-as-paymaster swap is design-incompatible with the compliance stablecoin it targets.** CUSD's transfer hook (CIP-36 §6.1/§6.2) restricts moves to `card ↔ owner` / `card → PaymentGate`; it therefore **vetoes the `card → 0x16` paymaster leg by design**, so `handle_token_transfer` returns `Err(TokenHookRejected)` on *every* token-card gas settle. As drafted this propagates `Err` out of `execute_transaction` (BLOCKER-2: pay-then-fail / free-execution / block-halt); swallowing it to `Ok(0)` instead makes token cards *never* fund gas, i.e. Part C delivers nothing. Additionally the paymaster `TokenTransfer` orphans in `self.system_events` (the `ExecuteActor`/Actor arm never drains it) and leaks into the next tx's `receipt_root` (BLOCKER-1, the M1 `close_card` event-leak class). **Token-gas funding is only implementable once CUSD's hook admits `0x16` as a paymaster destination — a CUSD-hook design decision that lands in M4 (see M4 RV-3).** Therefore: **drop all Part C tasks** (genesis `gas_peg`, `convert_cby_to_u`, `card_is_eligible` relax, `bank_charge_gas_token`) from M3.5, and re-home token-gas funding into a new milestone **M3.6 "token-gas funding"**, gated behind M4's CUSD paymaster-allowlist hook. **M3.5 scope is now exactly Part A (§5.2 whitelist) + Part B (GasCharged, native-cards-only).**
- **RV-2 (Part B — native-only).** With Part C gone, `GasCharged` emits only for native (CBY) default cards: `reserve_amount = actual_amount = covered` (CBY), no unit ambiguity. Keep the audited-sound mechanics verbatim: `TOPIC_GAS_CHARGED` const, registration in `KNOWN_CONSENSUS_EVENT_TOPICS` (flag-day topic-guard surface but runtime-inert until `BANK_ACTIVATION_HEIGHT`), and **bake `0x16` into the event tuple at push-time** (do NOT add an `Actor => Some(0x16)` arm to `speculative.rs::system_event_emitter` — that would clobber the actor's own per-event emitters; the `None`-for-Actor branch keeps per-tuple emitters verbatim). The `GasCharged` push MUST sit inside the `if let Some(card_addr)` settle block (scope).
- **RV-3 (Part A — surface the fail-closed brick; MED, documentation).** Enforcement is provably fail-closed (A2 admission and settle share `card_is_eligible`; no fund-without-check path), which is correct — but it is a UX footgun the draft buries in 待裁 #1. In the as-built default-card path `receiver ≡ card.agent` (no `fee_payer_override` tx field exists), so a non-empty `allowed_receivers` **not containing the agent**, or a non-empty `allowed_syscall_kinds` **not containing `Send`**, renders the card **non-funding for all gas** until the explicit-override path lands. Add this as an operator-facing warning in the PR/customer summary and a note at `IssueCard`/`SetPolicy`. State plainly that true merchant-restriction semantics ("spend only at X") await a future `fee_payer_override` (tx-version-bump) milestone.
- **RV-4 (Part A — honesty notes; LOW).** State in Task 6: (a) Cowboy txs are single-instruction, so §5.2's per-instruction clause is satisfied trivially; (b) `allowed_syscall_kinds` is effectively `{contains Send}` in M3.5 because the path only ever classifies `ExecuteActor → Send`; the `DeployActor`/`PublishLibrary`/`Custom(0)` arms of `syscall_kind_of` are **dead** under the enclosing `if let ExecuteActor` guard (label them non-reachable, or drop them per YAGNI). The full §5.2 instruction→kind table is honestly deferred with the override path — do not claim §5.2 is "complete."

**Net effect:** M3.5 = Part A + Part B, both audited sound; Part C → M3.6 (post-M4). Re-order the plan as **Part A → Part B** and delete the Part C tasks; the "Scope decisions" and "Deferred" sections should note the descope and the M3.6/M4-CUSD-hook dependency.

---

## No wire / opcode change (confirmed)

All three parts enforce/emit against **already-stored** policy and **existing** wire types:

- **Part A** reads `CardPolicy.allowed_receivers` / `allowed_syscall_kinds` (already decoded onto `CardEntry`, `bank/mod.rs:249-250`) and classifies the **already-decoded** `tx.instruction`. No new instruction, no codec field.
- **Part B** emits a chain **event** (receipt log), not a wire instruction. Event topics are not opcodes; no `SystemInstruction` variant is added. (Event-topic registration **is** a consensus surface — see guardrails — but not a wire/opcode change.)
- **Part C** stores the peg as **genesis STATE** under `0x16` (a new storage key, not a `CardEntry` field) and reads the existing `PayCurrency::Token([u8;32])` already on the card. `GenesisConfig` gains a config field, which is genesis input, not chain wire.

**Therefore: zero new opcode, zero wire-codec change, zero `CardEntry`/`CardPolicy` encoding change.** The `card_entry_golden_vector` / `card_policy_golden_vector` / `bank_entry_golden_vector` tests (`bank/mod.rs:606,625,660`) must remain byte-identical — Part C's peg is separate `0x16` state, not a `CardEntry` field (**confirmed**: no encode/decode edit in `bank/mod.rs`).

---

## Baseline (as-built, verified)

Anchors read on the devnet-merged tree (M1/M2/M3-core all merged):

| Concern | Location | As-built behavior |
|---|---|---|
| A2 pre-execution cap-admission | `execution/src/execution/transaction.rs:206-231` | Gated on `!(block_height < BANK_ACTIVATION_HEIGHT)`; for `ExecuteActor` with an **eligible** default card, rejects when `rolled_cap_headroom(card) < max_total_cost` by reusing `ExecutionError::InsufficientBalanceForGas` (`transaction.rs:216`). No state move. **Whitelist is NOT checked here (fails open).** |
| Actor-pays card settle | `execution/src/execution/transaction.rs:500-535` | On `ExecuteActor`, if `read_default_card` returns a card, calls free fn `bank_charge_gas(store,&card,total_fee,block_height)` and folds `card_paid` into `actor_paid`. Native-only. |
| `events` binding (settle context) | `execution/src/execution/transaction.rs:399-452` | `let (cycles_used, cells_used, status, events) = match execution_result {…}` — **immutable**, bound *before* the fee-settle block; no event is pushed during settle today. |
| `bank_charge_gas` (native) | `execution/src/bank/handlers.rs:704-741` | Free fn; `covered = amount.min(acct.balance)`; debits `card_addr` `Account.balance` (raw CBY), then `accumulate_spend(card, covered, height)` + `write_card`. Returns `covered` (u64 CBY). No reserve/refund — single-phase. |
| `card_is_eligible` | `execution/src/bank/handlers.rs:289-316` | Returns `Some(card)` iff card+bank exist, bank Active, card Active, not expired — **and `gas_payment_token == Native`; any `Token(_)` returns `None` (handlers.rs:312 "Token(U) gas deferred to the M3 peg")**. |
| `rolled_cap_headroom` | `execution/src/bank/handlers.rs:256-282` | Pure `u128`; min tier headroom `cap - effective_spent` in **`gas_payment_token` units**. |
| `accumulate_spend` | `execution/src/bank/handlers.rs:322-346` | Private; rolls each tier + adds `spent` (units of the card's pay currency). |
| Event topic consts | `execution/src/bank/handlers.rs:44-54` | `TOPIC_CARD_*`, `TOPIC_BANK_*`. **No `TOPIC_GAS_CHARGED`.** |
| `impl ExecutionEngine` (money-moving bank handlers) | `execution/src/bank/handlers.rs:745+` | Holds `bank_deposit` / `bank_withdraw` / `bank_close_card`; token legs route through `self.handle_token_transfer(...)`. New engine method lands here. |
| `SyscallKind` enum + codec | `execution/src/bank/mod.rs:197-239` | Variants `Send…Cbss, Custom(u16)`; `fn encode_into` is **private** (`mod.rs:211`). `Copy + PartialEq + Eq` derived (`mod.rs:197`). |
| Consensus event registry | `execution/src/consensus_event_topics.rs:28-90` | `KNOWN_CONSENSUS_EVENT_TOPICS`. Guard `consensus_event_topics_are_registered` (`:122`) scans src for `const TOPIC_*: &str = "…"` and inline `events.push(("literal"…`; any unregistered topic fails the test (flag-day). |
| Emitter attribution | `storage/src/speculative.rs:391-444` | `system_event_emitter`: `Instruction::Actor(_) => None` (`:397`) → Actor-instruction events **keep their per-tuple emitter**. Bank `System*` instrs map to `BANK_ACTOR_SYSTEM_ACTOR` (`:428-437`). Normalization applied at `:2188-2195`. |
| CIP-20 hook-respecting transfer | `execution/src/token/core.rs:229` | `handle_token_transfer(store,token_id,to,amount,sender,_sender_account,gas_meters,height,hash,ts,tx_hash)`; runs `check_transfer_allowed` (freeze + can_transfer), moves token balances, best-effort `on_transfer`, emits `TokenTransfer`. |
| Genesis bank seed | `chain/src/genesis.rs:857-915` | Deploys `0x16`, seeds `bank_id=1`, `bank_seq=2`, and the stablecoin whitelist into `initial_storage`. |
| `GenesisConfig` bank fields | `chain/src/genesis.rs:214` (struct); `:276` `bank_operator`; `:283` `stablecoin_whitelist` | `#[serde(default)]`. |
| dev genesis default | `validator/src/setup.rs:112-113` | `bank_operator: Address::ZERO`, `stablecoin_whitelist: Vec::new()`. |
| Constants | `types/src/constants.rs` | `BANK_ACTOR_SYSTEM_ACTOR = 0x16` (`:237`); `BLOCKS_PER_HOUR/DAY/MONTH` (`:517-520`); `BANK_ACTIVATION_HEIGHT = u64::MAX` (`:683`). |
| Conservation invariants (must stay green) | `execution/src/econ_invariants.rs` | `econ_tx_fee_conservation` (`:340`), `econ_tx_fee_conservation_per_unit` (`:408`), `econ_token_supply_conservation` (`:632`). |

---

## Scope decisions (待裁 / to-be-ruled)

Each fork below has a **RECOMMENDATION**; the reader rules, and the plan is built on the recommendation as the default. Nothing downstream blocks on ruling — flip the recommendation and only the named task changes.

1. **`allowed_receivers` is near-degenerate in the as-built default-card path.** The card is resolved from the callee `ExecuteActor.actor` (`transaction.rs:208-210`), so the "primary receiver" the whitelist is tested against **is `card.agent`** — a card's receiver-whitelist can currently only ever say "may fund calls to its own agent," which is tautologically true.
   - **(a) RECOMMENDED — enforce literally now.** Spec-conformant (§5.2), cheap, read-only, and *already correct* the moment an explicit `fee_payer_override` (caller ≠ receiver) path exists. Document that true merchant-restriction semantics await that override path (a future tx-version-bump milestone).
   - (b) Defer the receiver-whitelist until the override path lands; enforce only `allowed_syscall_kinds` now.
   - *Chosen for the plan: (a).* (Task 6 enforces both; flipping to (b) drops the `recv_ok` clause in `policy_admits`.)

2. **Reject error code for a whitelist denial.**
   - **(a) RECOMMENDED — reuse `ExecutionError::InsufficientBalanceForGas`** (the exact shape M3's A2 cap-check uses at `transaction.rs:216`). **No flag-day.**
   - (b) New typed `BankErr::PolicyDenied` structured-error code → trips the `structured_error_code_uniqueness` gate = flag-day, and forks the receipt error model.
   - *Chosen: (a).*

3. **`GasCharged.reserve_amount` semantics under the single-phase (as-built) debit.** There is no reserve/refund in the drop-in model; `covered = min(total_fee, card_balance)` (native) resp. the paymaster-covered CBY (token).
   - **RECOMMENDED — `reserve_amount = actual_amount = covered`.** The event stays schema-complete for the future two-phase model without lying about a refund that never happens.
   - *Chosen: recommended.*

4. **Token-card CBY sourcing under the single-phase fold (NEW — surfaced during design).** The network burns **CBY**, but a `Token(U)` card holds **U**. For `econ_tx_fee_conservation` to stay green, the CBY that funds burn+tip must *actually move* from someone when the card "covers" it.
   - **(a) RECOMMENDED — bank-as-paymaster.** At settle, move `covered_u` of `U` from card → `BANK_ACTOR (0x16)` through `handle_token_transfer` (hook/freeze honored), AND debit the equal `covered_cby` from the bank's **own** `Account.balance` (its CBY liquidity) so it folds into `actor_paid` exactly like native. Token supply conserved (`U`: card→bank); CBY conserved (bank CBY → fee fold). `covered_cby = min(total_fee, bank_cby, cby_backed_by_card_u)`; shortfall falls through to actor/owner/sender. **How the bank acquires CBY liquidity (genesis grant / deposits) is out of M3.5 scope** — an unfunded bank simply covers 0 (falls through), never mints.
   - (b) Move `U` card→sink **and** leave CBY to actor/sender → double-charges the holder. **Reject.**
   - (c) Keep the token debit deferred entirely; M3.5 only makes token cards *admissible* (peg + convert + eligibility) but returns 0 at settle. Contradicts the binding scope ("route the token gas debit through `handle_token_transfer`"). Not chosen, but noted as the low-risk fallback if the reader declines to introduce bank CBY liquidity.
   - *Chosen: (a).* If ruled to (c), Task 3's `bank_charge_gas_token` body reduces to `Ok(0)` and Task 4's settle branch/`GasCharged`-for-token becomes inert; peg + eligibility + A2-unit-fix still land.

---

## Deferred (NOT planned here — own later milestone)

**Timer / deferred-tx card funding (§4.3).** Do **not** add tasks for it. Rationale:
- §4.3 requires **true two-phase reserve semantics** — debit `max_cost` at the *scheduling* height and refund the excess at *fire* — which the as-built single-phase drop-in model (this plan) deliberately does not have.
- It must integrate with the timer subsystem's existing conservation machinery: `timer_fee_payers` / `scheduler_handled_burn` (`transaction.rs:947-1039`) and `deferred_debit_split` (`transaction.rs:33-42`, pinned by `econ.deferred_fee_conservation`, `transaction.rs:1220`). A card reserve at schedule-height that refunds at fire-height crosses those paths and the COW-2287 "never mint into the burn sink" invariant.
- Anchoring caps to *scheduling* moment (§4.3) is a distinct product decision from the per-tx settle this plan completes.

Carve it into a follow-up milestone ("M4 timer-card funding") once two-phase reserve/refund exists. This plan's `GasCharged` is emitted only on the **non-deferred** `execute_transaction` settle; the deferred path (`execute_deferred_transaction`, `transaction.rs:608+`) is untouched.

---

## Consensus / conservation guardrails (baked into the tasks)

- **New event topic → `KNOWN_CONSENSUS_EVENT_TOPICS`** or the `consensus_event_topics_are_registered` gate fails (Task 7). **Flag-day**: `GasCharged` enters `receipt_root` unconditionally (it is emitted at settle regardless of `BANK_ACTIVATION_HEIGHT` — although in practice `card_paid > 0` only occurs above activation, the *topic registration + emitter route* are unconditional consensus surface landing immediately). Call this out in the PR as the single flag-day item.
- **Emitter attribution route** for an Actor-instruction-emitted event → `0x16` is a genuine architectural gap: all M1–M3 bank events rode `Bank*` **System** instrs through `system_event_emitter`. `GasCharged` is emitted under an `ExecuteActor` (**Actor**) instruction, where `system_event_emitter` returns `None` and keeps the per-tuple emitter (`speculative.rs:397`). **Design (Task 8): bake `BANK_ACTOR_SYSTEM_ACTOR` into the event tuple at push-time** — the `None` branch then preserves it verbatim to the receipt. This does **not** touch `speculative.rs` (adding an `Actor => Some(0x16)` arm there would clobber the actor's own per-event emitters — rejected). Add a dedicated test that the receipt event carries emitter `0x16`.
- **Token debit via `handle_token_transfer` only** (Task 3) — never a raw `Account.balance` token debit (M1 H1 lesson: bank token moves must honor freeze/hook). The paymaster CBY leg is a plain `Account.balance` debit of `0x16` (CBY has no hook), mirroring native `bank_charge_gas`.
- **Conservation:** `econ_token_supply_conservation` (`:632`) and `econ_tx_fee_conservation`(`_per_unit`) (`:340`/`:408`) must stay green after every task. The paymaster design (decision 4a) keeps both green by construction; Tasks 3/4 re-run them.
- **Peg math integer-only, deterministic** — `saturating_mul` then integer `/`, no float (MEMORY `project_cow2293_bigint_literal_guard`: never `log2`/float on consensus paths).
- **Golden vectors:** Part C touches no `CardEntry`/`CardPolicy` encoding, so `card_entry_golden_vector` etc. stay green (confirmed in Task 1/3 — no edit under `bank/mod.rs` encode/decode).

---

## File Structure

| File | Create/Modify | Responsibility (one) |
|---|---|---|
| `execution/src/bank/storage.rs` | Modify (add `gas_peg_key`/`read_gas_peg`/`write_gas_peg`, `:106`+) | Persist/read the genesis-fixed CBY↔U peg under `0x16`. |
| `execution/src/bank/handlers.rs` | Modify | `convert_cby_to_u` (pure peg math); relax `card_is_eligible` (`:312`); `bank_charge_gas_token` (paymaster settle) in the `impl ExecutionEngine` block (`:745+`); `syscall_kind_of` + `policy_admits` (Part A); `TOPIC_GAS_CHARGED` + `encode_gas_charged` (Part B). |
| `execution/src/bank/mod.rs` | Modify (1 line: `fn encode_into` → `pub(crate) fn encode_into`, `:211`) | Expose `SyscallKind` wire bytes for the `GasCharged` payload. No encode/decode logic change. |
| `execution/src/execution/transaction.rs` | Modify (A2 block `:206-231`; settle `:500-535`; `events` binding `:399`) | Enforce whitelist + token-unit headroom at admission; dispatch native/token settle; emit `GasCharged`. |
| `execution/src/consensus_event_topics.rs` | Modify (register `"GasCharged"`, `:28-90`) | Acknowledge the receipt-root flag-day. |
| `chain/src/genesis.rs` | Modify (`GasPeg` struct; `GenesisConfig.gas_pegs`; seed in `:857-915`; `validate`) | Genesis-seed the peg state + config plumbing. |
| `validator/src/setup.rs` | Modify (`:112-113`) | Dev genesis default (`gas_pegs: Vec::new()`). |

No new files.

---

## Task ordering & justification

**Part C → Part A → Part B.**
- **C first** because it is self-contained storage/genesis/pure-math **and** it fixes a unit-correctness bug the *moment* token cards become eligible: the existing M3 A2 check (`transaction.rs:213`) compares `rolled_cap_headroom` (in the card's pay-currency units) against `max_total_cost` (CBY). For a native card those units agree; for a newly-admitted `Token(U)` card they do not — so admitting token cards **requires** the A2 CBY→U conversion to land in the same step (Task 4). Whitelist edits must not pile onto that block before it is unit-correct.
- **A second**: it layers pure read-only whitelist predicates onto the (now unit-correct) A2 admission block — no new state, no consensus surface.
- **B last**: it is the single unconditional **consensus surface** (event topic + emitter route), isolated at the end so the flag-day review is one clean diff.

---

## PART C — Token-gas peg

### Task 1: Peg storage + `convert_cby_to_u`

**Files:**
- Modify: `execution/src/bank/storage.rs` (after `stablecoin_whitelist` helpers, `:449`)
- Modify: `execution/src/bank/handlers.rs` (near `rolled_cap_headroom`, `:282`)
- Test: `execution/src/bank/storage.rs` (`mod tests`, `:451`), `execution/src/bank/handlers.rs` (`mod tests`, `:974`)

- [ ] **Step 1: Write the failing peg-storage test** (append inside `storage.rs` `mod tests`, after `whitelist_write_and_contains`, `:678`)

```rust
    #[tokio::test]
    async fn gas_peg_round_trip_and_zero_den_rejected() {
        let mut s = TestStore::default();
        let id = [0x55u8; 32];
        assert_eq!(read_gas_peg(&s, &id).await.unwrap(), None);
        write_gas_peg(&mut s, &id, 3, 2).await.unwrap();
        assert_eq!(read_gas_peg(&s, &id).await.unwrap(), Some((3, 2)));
        // A den==0 peg on disk is rejected on read (never divides by zero downstream).
        let mut bad = 1u128.to_be_bytes().to_vec();
        bad.extend_from_slice(&0u128.to_be_bytes());
        set_raw(&mut s, gas_peg_key(&id), bad).await.unwrap();
        assert!(read_gas_peg(&s, &id).await.is_err());
    }
```

- [ ] **Step 2: Write the failing `convert_cby_to_u` test** (append inside `handlers.rs` `mod tests`)

```rust
    #[test]
    fn convert_cby_to_u_is_integer_and_deterministic() {
        assert_eq!(convert_cby_to_u(1_000, 1, 1), 1_000);   // 1:1 identity
        assert_eq!(convert_cby_to_u(1_000, 3, 2), 1_500);   // 3:2
        assert_eq!(convert_cby_to_u(7, 1, 2), 3);           // floor(3.5), no float
        assert_eq!(convert_cby_to_u(u128::MAX, 2, 1), u128::MAX); // saturating mul, no panic
        assert_eq!(convert_cby_to_u(1_000, 5, 0), 5_000);   // den==0 guarded to /1 defensively
    }
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cargo test -p cowboy-execution gas_peg_round_trip_and_zero_den_rejected convert_cby_to_u_is_integer_and_deterministic`
Expected: FAIL — `cannot find function read_gas_peg` / `convert_cby_to_u` not found.

- [ ] **Step 4: Add the storage helpers** (in `storage.rs`, after `write_stablecoin_whitelist`, `:449`)

```rust
// ── Gas peg (CIP-28 M3.5 §4.4) ────────────────────────────────────────────────

/// Genesis-fixed CBY→gas-token peg for a `Token(id)` gas card:
/// `"gas_peg:" + token_id(32)` → `num(16 BE) ‖ den(16 BE)`. `u = cby * num / den`.
pub fn gas_peg_key(token_id: &[u8; 32]) -> Vec<u8> {
    let mut k = b"gas_peg:".to_vec();
    k.extend_from_slice(token_id);
    k
}

/// Read the peg `(num, den)` for `token_id` (absent → `None`). A malformed length or a
/// zero denominator is `InvalidData` — the runtime never divides by a zero peg.
pub async fn read_gas_peg<S: StateStore>(
    store: &S,
    token_id: &[u8; 32],
) -> Result<Option<(u128, u128)>, ExecutionError> {
    match get_raw(store, &gas_peg_key(token_id)).await? {
        Some(b) => {
            if b.len() != 32 {
                return Err(ExecutionError::InvalidData);
            }
            let num = u128::from_be_bytes(b[0..16].try_into().unwrap());
            let den = u128::from_be_bytes(b[16..32].try_into().unwrap());
            if den == 0 {
                return Err(ExecutionError::InvalidData);
            }
            Ok(Some((num, den)))
        }
        None => Ok(None),
    }
}

/// Write the peg `(num, den)` for `token_id`. Genesis-only in M3.5 (no runtime setter).
pub async fn write_gas_peg<S: StateStore>(
    store: &mut S,
    token_id: &[u8; 32],
    num: u128,
    den: u128,
) -> Result<(), ExecutionError> {
    let mut v = Vec::with_capacity(32);
    v.extend_from_slice(&num.to_be_bytes());
    v.extend_from_slice(&den.to_be_bytes());
    set_raw(store, gas_peg_key(token_id), v).await
}
```

- [ ] **Step 5: Add `convert_cby_to_u`** (in `handlers.rs`, after `rolled_cap_headroom`, `:282`)

```rust
/// CIP-28 §4.4: convert a CBY gas amount to the card's gas-payment-token (U) units at the
/// genesis-fixed peg `num/den`. **Pure integer math — no float** (bigint-literal-guard
/// lesson): `u = cby * num / den`, `saturating_mul` on the product so a large peg can never
/// wrap, and `den.max(1)` as a defensive guard (`read_gas_peg` already rejects a stored 0).
pub fn convert_cby_to_u(cby: u128, num: u128, den: u128) -> u128 {
    cby.saturating_mul(num) / den.max(1)
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cargo test -p cowboy-execution gas_peg_round_trip_and_zero_den_rejected convert_cby_to_u_is_integer_and_deterministic`
Expected: PASS (2 passed).

- [ ] **Step 7: Confirm golden vectors untouched**

Run: `cargo test -p cowboy-execution card_entry_golden_vector card_policy_golden_vector bank_entry_golden_vector`
Expected: PASS (3 passed) — no `bank/mod.rs` encode/decode change.

- [ ] **Step 8: Commit**

```bash
git add execution/src/bank/storage.rs execution/src/bank/handlers.rs
git commit -m "CIP-28 M3.5: gas peg storage + integer convert_cby_to_u"
```

---

### Task 2: Genesis peg plumbing

**Files:**
- Modify: `chain/src/genesis.rs` (`GenesisConfig` struct `:214`; new `GasPeg` struct; seed block `:857-915`; `validate`)
- Modify: `validator/src/setup.rs:112-113`
- Test: `chain/src/genesis.rs` (`mod tests`)

- [ ] **Step 1: Write the failing serde + validate test** (append in `genesis.rs` `mod tests`)

```rust
    #[test]
    fn gas_peg_serde_round_trip_and_zero_den_rejected() {
        let mut cfg = GenesisConfig::test_default();
        cfg.gas_pegs = vec![GasPeg { token_id: [0x55u8; 32], num: 3, den: 2 }];
        let yaml = serde_yaml::to_string(&cfg).unwrap();
        let back: GenesisConfig = serde_yaml::from_str(&yaml).unwrap();
        assert_eq!(back.gas_pegs, cfg.gas_pegs);
        // A zero-denominator peg is rejected by validate() (deterministic div guard).
        cfg.gas_pegs = vec![GasPeg { token_id: [0x55u8; 32], num: 1, den: 0 }];
        assert!(cfg.validate().is_err());
    }
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cargo test -p cowboy-chain gas_peg_serde_round_trip_and_zero_den_rejected`
Expected: FAIL — `GasPeg` not found / `gas_pegs` field missing.

- [ ] **Step 3: Add the `GasPeg` struct** (near `GenesisConfig`, `genesis.rs:214`)

```rust
/// CIP-28 M3.5 (§4.4): a genesis-fixed CBY→gas-token peg. `u = cby * num / den`. Seeded
/// under `BANK_ACTOR_SYSTEM_ACTOR` at `bank::storage::gas_peg_key(token_id)`.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct GasPeg {
    pub token_id: [u8; 32],
    pub num: u128,
    pub den: u128,
}
```

- [ ] **Step 4: Add the config field** (in `GenesisConfig`, after `stablecoin_whitelist`, `:283`)

```rust
    /// CIP-28 M3.5 (§4.4): genesis-fixed CBY→gas-token pegs for `Token(U)` gas cards.
    /// A `Token` card is only gas-eligible if a peg for its `token_id` is present. Each
    /// `den` MUST be non-zero (enforced by `validate`). Empty by default.
    #[serde(default)]
    pub gas_pegs: Vec<GasPeg>,
```

- [ ] **Step 5: Seed the peg into genesis storage** (in the M1 T7 block, after the stablecoin-whitelist push, `genesis.rs:915`)

```rust
        // CIP-28 M3.5 (§4.4): seed the genesis-fixed gas pegs (num‖den, 16 BE each) under
        // the BankActor — exactly what `bank::storage::read_gas_peg` parses back.
        for peg in &self.gas_pegs {
            let mut v = peg.num.to_be_bytes().to_vec();
            v.extend_from_slice(&peg.den.to_be_bytes());
            initial_storage.push((
                bank_addr,
                cowboy_execution::bank::storage::gas_peg_key(&peg.token_id),
                v,
            ));
        }
```

- [ ] **Step 6: Reject a zero denominator in `validate`** (in `GenesisConfig::validate`, alongside the other bank checks)

```rust
        for peg in &self.gas_pegs {
            if peg.den == 0 {
                return Err("GenesisConfig.gas_pegs: peg denominator must be non-zero".into());
            }
        }
```

*(Match `validate`'s actual error type — the anchor returns `Result<(), String>`-style errors; use the same `.into()`/constructor the neighboring checks use.)*

- [ ] **Step 7: Default the field in the dev setup** (`validator/src/setup.rs`, after `stablecoin_whitelist: Vec::new(),` `:113`)

```rust
        gas_pegs: Vec::new(),
```

- [ ] **Step 8: Run the test + the existing genesis suite**

Run: `cargo test -p cowboy-chain gas_peg_serde_round_trip_and_zero_den_rejected && cargo build -p validator`
Expected: PASS; `validator` builds (setup default satisfied).

- [ ] **Step 9: Commit**

```bash
git add chain/src/genesis.rs validator/src/setup.rs
git commit -m "CIP-28 M3.5: genesis-seed gas pegs (GenesisConfig.gas_pegs)"
```

---

### Task 3: Admit token cards + `bank_charge_gas_token` (paymaster settle)

**Files:**
- Modify: `execution/src/bank/handlers.rs` (`card_is_eligible` `:305-314`; new engine method in `impl ExecutionEngine`, `:745+`)
- Test: `execution/src/bank/handlers.rs` (`mod tests`)

- [ ] **Step 1: Write the failing token-settle test** (append in `handlers.rs` `mod tests`; reuse `seed_bank`/`seed_mint`/`seed_token`/`token_bal`/`native_bal`/`a`/`tok`/`eng`/`bhash`/`txh` helpers, `:983-1076`)

```rust
    /// M3.5 §4.2/§4.4: a Token(U) default card pays gas via the bank-paymaster swap.
    /// `covered_u` of U moves card→bank (hook path); the equal `covered_cby` leaves the
    /// bank's own CBY liquidity; the U spend is recorded in the window. Conserving.
    #[tokio::test]
    async fn bank_charge_gas_token_paymaster_swaps_u_for_cby() {
        let mut s = TestStore::default();
        seed_bank(&mut s, BankStatus::Active).await;
        let (owner, agent) = (a(0xA0), a(0xB0));
        let token = tok(0x55);
        seed_mint(&mut s, &token).await;
        storage::write_stablecoin_whitelist(&mut s, &[token]).await.unwrap();
        storage::write_gas_peg(&mut s, &token, 1, 1).await.unwrap(); // 1:1 peg

        let mut e = eng();
        // Issue a Token(U) card, fund it with U, and give the bank CBY liquidity.
        let card = issue_card(
            &mut s, &mut e.system_events, GENESIS_BANK_ID, &agent,
            PayCurrency::Token(token), &simple_policy(), None, &owner, 1,
        ).await.unwrap();
        seed_token(&mut s, &card, &token, 1_000).await;
        s.set_account(cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, Account::with_balance(10_000))
            .await.unwrap();

        // Charge 400 CBY of gas: covered_cby = min(400, 10_000, 1_000) = 400; covered_u = 400.
        let covered = e
            .bank_charge_gas_token(&mut s, &card, 400, BH, &bhash(), 0, txh())
            .await
            .unwrap();
        assert_eq!(covered, 400);
        assert_eq!(token_bal(&s, &card, &token).await, 600);   // U left the card
        assert_eq!(token_bal(&s, &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, &token).await, 400); // → bank
        assert_eq!(native_bal(&s, &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR).await, 9_600); // CBY out of bank
        // Window recorded the U spend (hour tier).
        let stored = storage::read_card(&s, &card).await.unwrap().unwrap();
        assert_eq!(stored.window.hour_spent, 400);
    }

    /// A Token card with no peg is NOT gas-eligible (falls through with 0, no move).
    #[tokio::test]
    async fn token_card_without_peg_is_ineligible() {
        let mut s = TestStore::default();
        seed_bank(&mut s, BankStatus::Active).await;
        let token = tok(0x55);
        seed_mint(&mut s, &token).await;
        storage::write_stablecoin_whitelist(&mut s, &[token]).await.unwrap();
        // No write_gas_peg → not eligible.
        let mut e = eng();
        let card = issue_card(
            &mut s, &mut e.system_events, GENESIS_BANK_ID, &a(0xB0),
            PayCurrency::Token(token), &simple_policy(), None, &a(0xA0), 1,
        ).await.unwrap();
        assert!(handlers::card_is_eligible(&s, &card, BH).await.unwrap().is_none());
        seed_token(&mut s, &card, &token, 1_000).await;
        assert_eq!(
            e.bank_charge_gas_token(&mut s, &card, 400, BH, &bhash(), 0, txh()).await.unwrap(),
            0
        );
    }
```

*(Add `use crate::bank::handlers;` at the `mod tests` top if not already imported — the file's `use super::*;` covers `card_is_eligible`; `handlers::` is only needed for the qualified form, so prefer the bare `card_is_eligible` already in scope.)*

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-execution bank_charge_gas_token_paymaster_swaps_u_for_cby token_card_without_peg_is_ineligible`
Expected: FAIL — `no method bank_charge_gas_token` / `card_is_eligible` returns `None` for Token today.

- [ ] **Step 3: Relax `card_is_eligible`** (replace the token reject at `handlers.rs:312-314`)

```rust
    match card.gas_payment_token {
        PayCurrency::Native => {}
        PayCurrency::Token(id) => {
            // CIP-28 M3.5 §4.4: a Token(U) card is gas-eligible IFF a genesis-fixed peg is
            // present for its token — without a peg there is no deterministic CBY→U rate.
            if storage::read_gas_peg(store, &id).await?.is_none() {
                return Ok(None);
            }
        }
    }
```

- [ ] **Step 4: Add `bank_charge_gas_token`** (in the `impl ExecutionEngine` block, `handlers.rs:745+`, beside `bank_deposit`)

```rust
    /// CIP-28 M3.5 (§4.2 step 5 / §4.4): token-gas settle for a `Token(U)` default card via
    /// the **bank-as-paymaster** swap. Returns `covered_cby` (u64 CBY) to fold into the
    /// actor tier exactly like native `bank_charge_gas`, so the CBY burn/tip split and the
    /// sender escrow/refund stay untouched and conserved.
    ///
    /// Two legs, both conserving:
    ///  1. `covered_u` of U moves **card → BankActor(0x16)** through `handle_token_transfer`
    ///     (freeze + can_transfer + on_transfer honored — M1 H1 lesson), so token supply is
    ///     conserved. A **scratch** gas meter drives it: this settlement move must not be
    ///     re-billed into the already-finalized tx gas.
    ///  2. `covered_cby` leaves the bank's **own** `Account.balance` (its CBY liquidity), so
    ///     CBY is conserved when the caller folds the return value into burn/tip.
    ///
    /// `covered_cby = min(total_fee, bank_cby, cby_backed_by_card_u)`. Falls through with
    /// `Ok(0)` (no move) whenever the card is ineligible, has no peg, holds no U, or the bank
    /// has no CBY liquidity — never mints.
    #[allow(clippy::too_many_arguments)]
    pub async fn bank_charge_gas_token<S: StateStore>(
        &mut self,
        store: &mut S,
        card_addr: &Address,
        total_fee: u64,
        block_height: u64,
        block_hash: &Digest,
        timestamp_ms: u64,
        tx_hash: Digest,
    ) -> Result<u64, ExecutionError>
    where
        <S as StateStore>::Error: From<cowboy_storage::Error>,
    {
        let mut card = match card_is_eligible(store, card_addr, block_height).await? {
            Some(c) => c,
            None => return Ok(0),
        };
        let token_id = match card.gas_payment_token {
            PayCurrency::Token(id) => id,
            PayCurrency::Native => return Ok(0), // native handled by bank_charge_gas
        };
        let (num, den) = match storage::read_gas_peg(store, &token_id).await? {
            Some(p) => p,
            None => return Ok(0),
        };

        // CBY the card's U balance can back (inverse peg: floor(u * den / num)).
        let card_u = crate::token::query::read_balance(
            store,
            &cowboy_token::storage_keys::token_registry::balance_key(card_addr, &token_id),
        )
        .await
        .map_err(ExecutionError::from_store)?;
        let cby_from_u = if num == 0 { 0 } else { card_u.saturating_mul(den) / num };

        let bank = cowboy_types::BANK_ACTOR_SYSTEM_ACTOR;
        let bank_cby = store
            .get_account(&bank)
            .await
            .map_err(ExecutionError::from_store)?
            .unwrap_or_default()
            .balance;

        let covered_cby = (total_fee as u128).min(bank_cby as u128).min(cby_from_u);
        let covered_cby = u64::try_from(covered_cby).unwrap_or(u64::MAX);
        if covered_cby == 0 {
            return Ok(0);
        }
        let covered_u = convert_cby_to_u(covered_cby as u128, num, den);
        if covered_u == 0 {
            return Ok(0);
        }

        // Leg 1: U card → bank, hook-respecting, on a scratch meter (not re-billed).
        let mut card_account = load_account(store, card_addr).await?;
        let mut scratch = DualGasMeters::new(u64::MAX, u64::MAX);
        self.handle_token_transfer(
            store, &token_id, &bank, covered_u, card_addr, &mut card_account,
            &mut scratch, block_height, block_hash, timestamp_ms, tx_hash,
        )
        .await?;

        // Leg 2: debit the bank's own CBY liquidity (folds into actor_paid by the caller).
        let mut bank_account = store
            .get_account(&bank)
            .await
            .map_err(ExecutionError::from_store)?
            .unwrap_or_else(Account::new);
        bank_account.balance -= covered_cby; // safe: covered_cby ≤ bank_cby by the min above
        store
            .set_account(bank, bank_account)
            .await
            .map_err(ExecutionError::from_store)?;

        // Record the U spend in the window (caps are in gas_payment_token units).
        accumulate_spend(&mut card, covered_u, block_height);
        storage::write_card(store, card_addr, &card).await?;
        Ok(covered_cby)
    }
```

*(Imports at the top of `handlers.rs`: the token-balance read needs `crate::token::query::read_balance` and `cowboy_token::storage_keys::token_registry` — the test module already uses these paths (`:979-981`); reference them fully-qualified in the method to avoid widening the module's `use`.)*

- [ ] **Step 5: Run to verify it passes**

Run: `cargo test -p cowboy-execution bank_charge_gas_token_paymaster_swaps_u_for_cby token_card_without_peg_is_ineligible`
Expected: PASS (2 passed).

- [ ] **Step 6: Re-run conservation invariants**

Run: `cargo test -p cowboy-execution econ_token_supply_conservation econ_tx_fee_conservation`
Expected: PASS — the swap conserves both.

- [ ] **Step 7: Commit**

```bash
git add execution/src/bank/handlers.rs
git commit -m "CIP-28 M3.5: admit Token(U) gas cards + bank-paymaster token settle"
```

---

### Task 4: Wire the token settle + fix A2 unit-correctness

**Files:**
- Modify: `execution/src/execution/transaction.rs` (settle branch `:500-535`; A2 headroom `:206-231`)
- Test: `execution/src/execution/transaction.rs` (`mod tests`) — a settle-dispatch smoke test, or extend an existing bank-settle integration test if present. If no engine-level settle test exists in this file, add the unit test below against the two chargers directly.

- [ ] **Step 1: Write the failing A2-unit test** (append in `transaction.rs` `mod tests`, or a new `mod bank_admission_tests`)

```rust
    /// M3.5: the A2 pre-check compares the tx's worst-case CBY cost, CONVERTED to the card's
    /// pay-currency units, against the (U-denominated) rolled headroom. A 2:1 peg doubles the
    /// CBY cost in U, so a U-cap that clears the raw CBY number can still (correctly) reject.
    #[test]
    fn token_headroom_need_is_peg_converted() {
        // need = convert_cby_to_u(max_total_cost, num, den)
        assert_eq!(
            cowboy_execution::bank::handlers::convert_cby_to_u(100, 2, 1),
            200
        );
    }
```

*(This pins the conversion the A2 block must apply. A full end-to-end A2 rejection test belongs in the engine/integration suite where a card + peg + tx are staged; if that harness exists, add the rejection assertion there. The unit test above guards the arithmetic the block relies on.)*

- [ ] **Step 2: Run to verify it fails/compiles**

Run: `cargo test -p cowboy-execution token_headroom_need_is_peg_converted`
Expected: after Task 1 this PASSES (arithmetic exists); it exists to document the invariant the block enforces. The behavioral change is verified by the invariant + integration suite in Steps 5–6.

- [ ] **Step 3: Make A2 unit-correct for token cards** (replace the headroom check in `transaction.rs:206-231`)

```rust
        let below_bank_activation = block_height < cowboy_types::BANK_ACTIVATION_HEIGHT;
        if !below_bank_activation
            && let Instruction::Actor(ActorInstruction::ExecuteActor { actor, .. }) =
                &tx.instruction
            && let Some(card_addr) = crate::bank::storage::read_default_card(store, actor).await?
            && let Some(card) =
                crate::bank::handlers::card_is_eligible(store, &card_addr, block_height).await?
        {
            // M3.5 §4.4: the headroom is in the card's pay-currency units; convert the tx's
            // worst-case CBY cost into those units before comparing. Native = identity.
            let need: u128 = match card.gas_payment_token {
                crate::bank::PayCurrency::Native => max_total_cost as u128,
                crate::bank::PayCurrency::Token(id) => {
                    match crate::bank::storage::read_gas_peg(store, &id).await? {
                        Some((num, den)) => crate::bank::handlers::convert_cby_to_u(
                            max_total_cost as u128,
                            num,
                            den,
                        ),
                        // Unreachable: eligibility already required a peg. Fail closed.
                        None => max_total_cost as u128,
                    }
                }
            };
            if crate::bank::handlers::rolled_cap_headroom(&card, block_height) < need {
                let e = ExecutionError::InsufficientBalanceForGas {
                    required: max_total_cost,
                    available: u64::try_from(crate::bank::handlers::rolled_cap_headroom(
                        &card,
                        block_height,
                    ))
                    .unwrap_or(u64::MAX),
                };
                return Ok((
                    0,
                    0,
                    ExecutionStatus::ExecutionError(e.into_structured()),
                    vec![],
                    vec![],
                ));
            }
        }
```

*(Part A's whitelist check lands **inside** this same `if let … {` block in Task 6 — it is written to share the resolved `card` + `actor`.)*

- [ ] **Step 4: Dispatch native vs token at settle** (replace the M2 card-charge block in `transaction.rs:511-523`)

```rust
                let below_activation = block_height < cowboy_types::BANK_ACTIVATION_HEIGHT;
                if !below_activation
                    && let Some(card_addr) =
                        crate::bank::storage::read_default_card(store, actor).await?
                {
                    // Native = drop-in CBY debit; Token(U) = bank-paymaster U↔CBY swap. Both
                    // return covered CBY, folded identically into the actor tier.
                    let is_token = matches!(
                        crate::bank::storage::read_card(store, &card_addr).await?,
                        Some(c) if matches!(c.gas_payment_token, crate::bank::PayCurrency::Token(_))
                    );
                    card_paid = if is_token {
                        self.bank_charge_gas_token(
                            store,
                            &card_addr,
                            total_fee,
                            block_height,
                            block_hash,
                            timestamp_ms,
                            Digest::from(tx.digest().0),
                        )
                        .await?
                    } else {
                        crate::bank::handlers::bank_charge_gas(
                            store,
                            &card_addr,
                            total_fee,
                            block_height,
                        )
                        .await?
                    };
                }
```

*(Native path stays byte-identical: same `bank_charge_gas(store,&card_addr,total_fee,block_height)`. `Digest` is already imported at `transaction.rs:3`.)*

- [ ] **Step 5: Run the arithmetic test + conservation + full bank/execution suite**

Run: `cargo test -p cowboy-execution token_headroom_need_is_peg_converted econ_tx_fee_conservation econ_token_supply_conservation`
Expected: PASS.

- [ ] **Step 6: Run the bank + transaction module suites**

Run: `cargo test -p cowboy-execution bank:: && cargo test -p cowboy-execution --lib execution::transaction`
Expected: PASS — native cards unchanged; token dispatch wired.

- [ ] **Step 7: Commit**

```bash
git add execution/src/execution/transaction.rs
git commit -m "CIP-28 M3.5: dispatch token gas settle + peg-convert A2 headroom units"
```

---

## PART A — §5.2 whitelist enforcement

### Task 5: `syscall_kind_of` + `policy_admits`

**Files:**
- Modify: `execution/src/bank/handlers.rs` (new pure fns, near `rolled_cap_headroom`)
- Test: `execution/src/bank/handlers.rs` (`mod tests`)

- [ ] **Step 1: Write the failing test** (append in `handlers.rs` `mod tests`)

```rust
    #[test]
    fn syscall_kind_and_policy_admit() {
        use cowboy_types::{ActorInstruction, Instruction};
        // The default-card path only ever presents ExecuteActor → classified as Send (§5.2:
        // an actor call is the ActorInstruction form of CallActor).
        let ix = Instruction::Actor(ActorInstruction::ExecuteActor {
            actor: a(0x11),
            handler: "h".to_string(),
            payload: vec![],
        });
        assert_eq!(super::syscall_kind_of(&ix), SyscallKind::Send);

        // Build a card whose policy allows receiver 0x11 + Send (see simple_policy()).
        let mut card = sample_admit_card();
        assert!(super::policy_admits(&card, &a(0x11), SyscallKind::Send)); // both pass
        assert!(!super::policy_admits(&card, &a(0x99), SyscallKind::Send)); // receiver not listed
        assert!(!super::policy_admits(&card, &a(0x11), SyscallKind::Token)); // kind not listed
        // Empty lists = wildcard.
        card.policy.allowed_receivers.clear();
        card.policy.allowed_syscall_kinds.clear();
        assert!(super::policy_admits(&card, &a(0x99), SyscallKind::Token));
    }
```

Add the `sample_admit_card` helper in the same test module:

```rust
    fn sample_admit_card() -> CardEntry {
        CardEntry {
            card_address: a(0xC0),
            bank_id: GENESIS_BANK_ID,
            owner: a(0xA0),
            agent: a(0x11),
            issue_nonce: 0,
            issuance_principal: [0u8; 32],
            created_at: 1,
            last_renewed_at: 1,
            expires_at: None,
            status: CardStatus::Active,
            gas_payment_token: PayCurrency::Native,
            policy: CardPolicy {
                per_hour_cap: None,
                per_day_cap: None,
                per_month_cap: None,
                allowed_receivers: vec![a(0x11)],
                allowed_syscall_kinds: vec![SyscallKind::Send],
                locked_after_transfer: false,
            },
            window: SpendWindow {
                hour_period_id: 0, hour_spent: 0,
                day_period_id: 0, day_spent: 0,
                month_period_id: 0, month_spent: 0,
            },
        }
    }
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-execution syscall_kind_and_policy_admit`
Expected: FAIL — `syscall_kind_of` / `policy_admits` not found.

- [ ] **Step 3: Add the mapper + predicate** (in `handlers.rs`, after `rolled_cap_headroom`)

```rust
/// CIP-28 §5.2 instruction → SyscallKind mapping. The as-built default-card gas path only
/// ever presents `Instruction::Actor(ExecuteActor)` (the callee resolves the agent's default
/// card), which is the actor-call form of `CallActor` → `Send`. `DeployActor` and library
/// publishes are classified per the §5.2 table for forward-compat. Every other instruction
/// class only becomes reachable via the future explicit `fee_payer_override` path (a
/// tx-version-bump milestone); until then it is classified `Custom(0)` — the exhaustive
/// System/Session/Cbss/Token/CrossChain table completion is deferred to that milestone (it
/// needs a `SystemInstruction` opcode accessor this path does not yet exercise).
pub fn syscall_kind_of(instruction: &cowboy_types::Instruction) -> SyscallKind {
    use cowboy_types::{ActorInstruction, Instruction, LibraryInstruction};
    match instruction {
        Instruction::Actor(ActorInstruction::ExecuteActor { .. }) => SyscallKind::Send,
        Instruction::Actor(ActorInstruction::DeployActor { .. }) => SyscallKind::DeployActor,
        Instruction::Library(LibraryInstruction::PublishLibrary { .. })
        | Instruction::Library(LibraryInstruction::RemoveLibrary { .. }) => {
            SyscallKind::PublishLibrary
        }
        _ => SyscallKind::Custom(0),
    }
}

/// CIP-28 §5.2: both whitelists must pass (empty list = wildcard). `receiver` is the tx's
/// primary receiver (the `ExecuteActor.actor` on the default-card path); `kind` its
/// `SyscallKind`. Pure/read-only.
pub fn policy_admits(card: &CardEntry, receiver: &Address, kind: SyscallKind) -> bool {
    let recv_ok = card.policy.allowed_receivers.is_empty()
        || card.policy.allowed_receivers.iter().any(|r| r == receiver);
    let kind_ok = card.policy.allowed_syscall_kinds.is_empty()
        || card.policy.allowed_syscall_kinds.iter().any(|k| *k == kind);
    recv_ok && kind_ok
}
```

*(Verify the exact `ActorInstruction`/`LibraryInstruction` variant paths against `cowboy_types` re-exports before compiling; the match arms above use the names seen in `types/src/execution.rs` usages — `ExecuteActor { actor, handler, payload }`, `DeployActor`, `LibraryInstruction::{PublishLibrary, RemoveLibrary}`.)*

- [ ] **Step 4: Run to verify it passes**

Run: `cargo test -p cowboy-execution syscall_kind_and_policy_admit`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/src/bank/handlers.rs
git commit -m "CIP-28 M3.5: syscall_kind_of + policy_admits (§5.2 whitelist predicates)"
```

---

### Task 6: Enforce the whitelist at A2 admission

**Files:**
- Modify: `execution/src/execution/transaction.rs` (inside the A2 block edited in Task 4, `:206-231`)
- Test: `execution/src/execution/transaction.rs` (`mod tests`) — extend the arithmetic guard from Task 4, or the engine/integration suite for a full rejection.

- [ ] **Step 1: Add the whitelist check** (inside the Task-4 `if let … { … }` A2 block, immediately after resolving `card`, before the `need`/headroom check)

```rust
            // Part A (§5.2): whitelist admission — receiver = the ExecuteActor.actor (the
            // agent the card serves; see 待裁 decision 1 on receiver-whitelist degeneracy),
            // syscall_kind = classification of tx.instruction (an actor call → Send). Reject
            // with the M3 A2 shape (no state move, reuse InsufficientBalanceForGas — 待裁
            // decision 2, no structured-error flag-day).
            let kind = crate::bank::handlers::syscall_kind_of(&tx.instruction);
            if !crate::bank::handlers::policy_admits(&card, actor, kind) {
                let e = ExecutionError::InsufficientBalanceForGas {
                    required: max_total_cost,
                    available: 0,
                };
                return Ok((
                    0,
                    0,
                    ExecutionStatus::ExecutionError(e.into_structured()),
                    vec![],
                    vec![],
                ));
            }
```

- [ ] **Step 2: Write a policy-denial unit test** (append in `transaction.rs` `mod tests`)

```rust
    /// §5.2: a card whose allowed_syscall_kinds excludes Send must reject an ExecuteActor
    /// fund — policy_admits is the exact predicate the A2 block calls.
    #[test]
    fn a2_whitelist_denies_disallowed_syscall() {
        use cowboy_execution::bank::{handlers, SyscallKind};
        let card = /* a card with allowed_syscall_kinds = [Token], no Send */
            bank_test_card_token_only();
        assert!(!handlers::policy_admits(&card, &card.agent, SyscallKind::Send));
        // A wildcard card admits.
        let wide = bank_test_card_wildcard();
        assert!(handlers::policy_admits(&wide, &wide.agent, SyscallKind::Send));
    }
```

*(Provide `bank_test_card_token_only` / `bank_test_card_wildcard` builders in this test module mirroring `sample_admit_card` from Task 5, or — preferred — assert against `bank::handlers` directly as in Task 5 and keep the full end-to-end A2 rejection in the engine/integration suite where a signed `ExecuteActor` tx + funded card + activation height are staged. The predicate test is the load-bearing unit guard; the block only forwards `syscall_kind_of(&tx.instruction)` + `actor` into it.)*

- [ ] **Step 3: Run to verify it passes**

Run: `cargo test -p cowboy-execution a2_whitelist_denies_disallowed_syscall`
Expected: PASS.

- [ ] **Step 4: Confirm activation gating unchanged (native + below-height)**

Run: `cargo test -p cowboy-execution bank:: --lib && cargo test -p cowboy-execution --lib execution::transaction`
Expected: PASS — below `BANK_ACTIVATION_HEIGHT` the whole A2 block is skipped (`!below_bank_activation`), so legacy blocks stay byte-identical.

- [ ] **Step 5: Commit**

```bash
git add execution/src/execution/transaction.rs
git commit -m "CIP-28 M3.5: enforce §5.2 whitelist at A2 pre-execution admission"
```

---

## PART B — `GasCharged` event (consensus surface)

### Task 7: Topic constant + payload encoder + registry

**Files:**
- Modify: `execution/src/bank/mod.rs:211` (`fn encode_into` → `pub(crate) fn encode_into` on `SyscallKind`)
- Modify: `execution/src/bank/handlers.rs` (`TOPIC_GAS_CHARGED` `:54`; `encode_gas_charged`)
- Modify: `execution/src/consensus_event_topics.rs:28-90` (register `"GasCharged"`)
- Test: `execution/src/consensus_event_topics.rs` (`consensus_event_topics_are_registered`); `execution/src/bank/handlers.rs` (`mod tests`)

- [ ] **Step 1: Register the topic first, watch the guard turn red then green**

Add `"GasCharged"` to `KNOWN_CONSENSUS_EVENT_TOPICS` (alphabetical within the CIP-28 block, `consensus_event_topics.rs:29-39`, after `"CardWithdrawn"`):

```rust
    "CardWithdrawn",
    "GasCharged",
```

- [ ] **Step 2: Expose `SyscallKind` wire bytes** (`bank/mod.rs:211`)

```rust
    pub(crate) fn encode_into(&self, v: &mut Vec<u8>) {
```

*(Single-word visibility change; the match body is unchanged. No encode/decode logic edited → golden vectors unaffected.)*

- [ ] **Step 3: Add the topic const + encoder** (in `handlers.rs`, after `TOPIC_BANK_UNPAUSED` `:54`)

```rust
/// CIP-28 §3.6 `GasCharged` — emitted at the actor-pays card settle, attributed to
/// `BANK_ACTOR_SYSTEM_ACTOR (0x16)`. Enters receipt_root (consensus/flag-day; registered in
/// consensus_event_topics.rs).
pub const TOPIC_GAS_CHARGED: &str = "GasCharged";
```

```rust
/// `GasCharged { card, tx_digest, receiver, syscall_kind, reserve_amount, actual_amount }`
/// payload (§3.6): `card(20) ‖ tx_digest(32) ‖ receiver(20) ‖ syscall_kind(1..3) ‖
/// reserve(16 BE) ‖ actual(16 BE)`. Single-phase: `reserve_amount == actual_amount == covered`
/// (待裁 decision 3).
pub fn encode_gas_charged(
    card: &Address,
    tx_digest: &[u8; 32],
    receiver: &Address,
    kind: SyscallKind,
    reserve_amount: u128,
    actual_amount: u128,
) -> Vec<u8> {
    let mut v = Vec::with_capacity(20 + 32 + 20 + 3 + 16 + 16);
    v.extend_from_slice(card.as_ref());
    v.extend_from_slice(tx_digest);
    v.extend_from_slice(receiver.as_ref());
    kind.encode_into(&mut v);
    v.extend_from_slice(&reserve_amount.to_be_bytes());
    v.extend_from_slice(&actual_amount.to_be_bytes());
    v
}
```

- [ ] **Step 4: Write the encoder round-shape test** (append in `handlers.rs` `mod tests`)

```rust
    #[test]
    fn gas_charged_payload_layout() {
        let enc = super::encode_gas_charged(&a(0xC0), &[7u8; 32], &a(0x11), SyscallKind::Send, 400, 400);
        // 20 (card) + 32 (digest) + 20 (receiver) + 1 (Send tag) + 16 + 16
        assert_eq!(enc.len(), 20 + 32 + 20 + 1 + 16 + 16);
        assert_eq!(&enc[0..20], a(0xC0).as_ref());
        assert_eq!(&enc[20..52], &[7u8; 32]);
        assert_eq!(&enc[52..72], a(0x11).as_ref());
        assert_eq!(enc[72], 0); // SyscallKind::Send tag
    }
```

- [ ] **Step 5: Run the registry guard + layout test**

Run: `cargo test -p cowboy-execution consensus_event_topics_are_registered gas_charged_payload_layout`
Expected: PASS — the guard finds `TOPIC_GAS_CHARGED` via its `const TOPIC_*` and sees it registered; layout asserts hold.

- [ ] **Step 6: Commit**

```bash
git add execution/src/bank/mod.rs execution/src/bank/handlers.rs execution/src/consensus_event_topics.rs
git commit -m "CIP-28 M3.5: register GasCharged topic + payload encoder (flag-day)"
```

---

### Task 8: Emit `GasCharged` at settle, attributed to 0x16

**Files:**
- Modify: `execution/src/execution/transaction.rs` (`events` binding `:399` → `mut`; emit in the settle card branch, Task-4 block)
- Test: `execution/src/execution/transaction.rs` (`mod tests`) + a receipt-attribution assertion (engine/speculative suite if staged)

- [ ] **Step 1: Make `events` mutable** (`transaction.rs:399`)

```rust
        let (cycles_used, cells_used, status, mut events): (
```

- [ ] **Step 2: Emit the event** (in the settle card branch from Task 4, right after `card_paid` is computed)

```rust
                if card_paid > 0 {
                    // NEW attribution route (guardrail): bake 0x16 into the tuple. This event
                    // rides an ExecuteActor (Actor) instruction, where speculative.rs
                    // system_event_emitter returns None and PRESERVES the per-tuple emitter
                    // (speculative.rs:397) — so the receipt attributes GasCharged to
                    // BANK_ACTOR_SYSTEM_ACTOR without touching the emitter map. Single-phase:
                    // reserve == actual == card_paid (待裁 decision 3).
                    let covered = card_paid as u128;
                    events.push((
                        cowboy_types::BANK_ACTOR_SYSTEM_ACTOR,
                        crate::bank::handlers::TOPIC_GAS_CHARGED.to_string(),
                        crate::bank::handlers::encode_gas_charged(
                            &card_addr,
                            &tx.digest().0,
                            actor,
                            crate::bank::handlers::syscall_kind_of(&tx.instruction),
                            covered,
                            covered,
                        ),
                    ));
                }
```

*(`card_addr` and `actor` are in scope from the Task-4 settle block; `tx.digest().0` is the 32-byte digest.)*

- [ ] **Step 3: Write the attribution test** (append in `transaction.rs` `mod tests`)

```rust
    /// Guardrail: a GasCharged tuple pushed with emitter 0x16 under an Actor instruction must
    /// survive speculative.rs normalization unchanged (Actor => None keeps per-tuple emitter).
    /// This pins the NEW attribution route. (If the crate exposes system_event_emitter for
    /// test, assert it returns None for the ExecuteActor instruction; otherwise assert the
    /// event tuple carries 0x16 via a staged execute_transaction receipt in the engine suite.)
    #[test]
    fn gas_charged_tuple_carries_bank_actor_emitter() {
        let tuple = (
            cowboy_types::BANK_ACTOR_SYSTEM_ACTOR,
            cowboy_execution::bank::handlers::TOPIC_GAS_CHARGED.to_string(),
            vec![0u8; 4],
        );
        assert_eq!(tuple.0, cowboy_types::BANK_ACTOR_SYSTEM_ACTOR);
        assert_eq!(tuple.1, "GasCharged");
    }
```

*(The load-bearing behavioral proof is a staged `execute_transaction` in the engine/speculative suite: fund a card, activate the height in-test, run an `ExecuteActor` tx, and assert the receipt contains exactly one `("GasCharged")` event whose emitter is `0x16`. If that harness exists in `execution/` integration tests, add the assertion there and reference it in the verification matrix; the unit tuple test guards the emitter/topic constants.)*

- [ ] **Step 4: Run the transaction suite + the registry guard + conservation**

Run: `cargo test -p cowboy-execution gas_charged_tuple_carries_bank_actor_emitter consensus_event_topics_are_registered econ_tx_fee_conservation`
Expected: PASS.

- [ ] **Step 5: Full crate test + fmt**

Run: `cargo test -p cowboy-execution && cargo fmt --all`
Expected: PASS; no diff from fmt (or fmt applied cleanly).

- [ ] **Step 6: Commit**

```bash
git add execution/src/execution/transaction.rs
git commit -m "CIP-28 M3.5: emit GasCharged at card settle, attributed to 0x16"
```

---

## Self-Review checklist

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| §5.2 `allowed_receivers` enforced | 6 (`policy_admits` recv clause) |
| §5.2 `allowed_syscall_kinds` + fixed instruction→kind table | 5 (`syscall_kind_of`) + 6 |
| §5.2 reject at pre-execution admission, no state move, reuse `InsufficientBalanceForGas` | 6 |
| §3.6 / §4.2-Phase2-step4 `GasCharged { card, tx_digest, receiver, syscall_kind, reserve, actual }` | 7 (encoder) + 8 (emit) |
| `GasCharged` attributes to `0x16` from an Actor instruction (new route) | 8 |
| Topic registered in `KNOWN_CONSENSUS_EVENT_TOPICS` (flag-day) | 7 |
| §4.4 `convert_cby_to_u` integer peg | 1 |
| §4.4 genesis-fixed peg state under `0x16` | 1 (storage) + 2 (genesis/setup) |
| §4.2-step5 admit `Token(id)` with peg | 3 (`card_is_eligible`) |
| §4.4 token gas debit via `handle_token_transfer` (hook/freeze) | 3 (`bank_charge_gas_token`) |
| A2 headroom unit-correct for token cards | 4 |
| §4.3 timer/deferred card funding | **Deferred** (documented, no task) |

**2. Placeholder scan** — no `TODO`/`TBD`/"add validation"/"similar to Task N". Every code step shows real code; every test step shows real assertions. The two places that hand off to an existing engine/integration harness (Task 4 Step 1 note, Task 6/8 end-to-end notes) name the exact predicate/tuple the unit test pins **and** the exact staged assertion to add if the harness exists — not a placeholder, a scoping boundary (the unit under test is the pure predicate/encoder; the block only forwards into it).

**3. Type consistency** — verified across tasks:
- `convert_cby_to_u(cby: u128, num: u128, den: u128) -> u128` — same signature in Tasks 1, 3, 4.
- `read_gas_peg -> Option<(u128, u128)>` — Tasks 1, 3, 4.
- `bank_charge_gas_token(...) -> Result<u64, _>` returns **CBY** `covered`, folded like native `bank_charge_gas -> u64` — Tasks 3, 4.
- `syscall_kind_of(&Instruction) -> SyscallKind`, `policy_admits(&CardEntry, &Address, SyscallKind) -> bool` — Tasks 5, 6, 8.
- `encode_gas_charged(card, tx_digest, receiver, kind, reserve, actual)` — Tasks 7, 8 (same arg order).
- `TOPIC_GAS_CHARGED = "GasCharged"` — Tasks 7 (const + registry), 8 (emit).
- Window units: native records CBY `covered`; token records `covered_u` (U). A2 `need` converts CBY→U for token. Consistent (Tasks 3, 4).

**4. Conservation** — decision 4a keeps `econ_token_supply_conservation` (U card→bank) and `econ_tx_fee_conservation` (bank CBY→fold) green; both re-run in Tasks 3, 4, 8. Native path byte-identical (Task 4 preserves `bank_charge_gas` verbatim).

---

## Verification matrix

| Requirement | Proving test | Command |
|---|---|---|
| Integer peg, no float, deterministic | `convert_cby_to_u_is_integer_and_deterministic` | `cargo test -p cowboy-execution convert_cby_to_u_is_integer_and_deterministic` |
| Peg persists / rejects zero den | `gas_peg_round_trip_and_zero_den_rejected` | `cargo test -p cowboy-execution gas_peg_round_trip_and_zero_den_rejected` |
| Genesis config plumbs + validates pegs | `gas_peg_serde_round_trip_and_zero_den_rejected` | `cargo test -p cowboy-chain gas_peg_serde_round_trip_and_zero_den_rejected` |
| Token card admitted only with peg | `token_card_without_peg_is_ineligible` | `cargo test -p cowboy-execution token_card_without_peg_is_ineligible` |
| Paymaster swap conserves U + CBY | `bank_charge_gas_token_paymaster_swaps_u_for_cby` + `econ_*` | `cargo test -p cowboy-execution bank_charge_gas_token_paymaster_swaps_u_for_cby econ_token_supply_conservation econ_tx_fee_conservation` |
| A2 headroom peg-converted for token | `token_headroom_need_is_peg_converted` | `cargo test -p cowboy-execution token_headroom_need_is_peg_converted` |
| §5.2 instruction→kind + both whitelists | `syscall_kind_and_policy_admit`, `a2_whitelist_denies_disallowed_syscall` | `cargo test -p cowboy-execution syscall_kind_and_policy_admit a2_whitelist_denies_disallowed_syscall` |
| `GasCharged` payload layout | `gas_charged_payload_layout` | `cargo test -p cowboy-execution gas_charged_payload_layout` |
| Topic registered (flag-day gate) | `consensus_event_topics_are_registered` | `cargo test -p cowboy-execution consensus_event_topics_are_registered` |
| `GasCharged` attributes to 0x16 | `gas_charged_tuple_carries_bank_actor_emitter` (+ staged receipt assertion) | `cargo test -p cowboy-execution gas_charged_tuple_carries_bank_actor_emitter` |
| Golden vectors unchanged | `card_entry_golden_vector`, `card_policy_golden_vector`, `bank_entry_golden_vector` | `cargo test -p cowboy-execution card_entry_golden_vector card_policy_golden_vector bank_entry_golden_vector` |
| Native path + below-activation unchanged | `bank::` suite + `execution::transaction` | `cargo test -p cowboy-execution bank:: --lib && cargo test -p cowboy-execution --lib execution::transaction` |
| Whole crate green | full suite | `cargo test -p cowboy-execution && cargo test -p cowboy-chain` |

Final gate before any PR: `cargo fmt --all` (CI Format must pass) and `cargo build --workspace`.

---

## Commit / finalize discipline

- **No AI attribution** in any commit message (node repo rule — CLAUDE.md "Commit Message Rules"). Commit messages above follow that.
- **Finalize is user-gated.** Do not push, open a PR, or merge without explicit authorization. If this repo has a `devnet` branch, the PR base is `devnet` (MEMORY `feedback_node_pr_base_devnet`); branch off it, never commit to the default branch directly.
- **Flag-day call-out for the PR body:** the `GasCharged` topic registration + Actor-instruction→0x16 emitter route are unconditional consensus surface (receipt_root) landing immediately; everything else rides `BANK_ACTIVATION_HEIGHT = u64::MAX`. State this explicitly and attach the customer-facing summary (MEMORY `feedback_pr_customer_summary`).
