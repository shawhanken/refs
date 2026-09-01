# CIP-28 BankActor — M3-core (policy triad + F1 fix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** The card **policy triad** — per-hour/day/month spend caps enforced in `charge_gas`, `allowed_receivers` whitelist, `Freeze`/`PauseBank` — plus `SetPolicy` and the **F1** consent fix. All gated behind `BANK_ACTIVATION_HEIGHT = u64::MAX` (inert until a coordinated flag-day).

**Architecture:** Stacked on M2 (`feat/cip28-bankactor-m2`). M2's `bank_charge_gas` is a drop-in card debit at the actor-pays fee tier; M3 makes it **roll the SpendWindow + enforce caps + check the receiver whitelist** before debiting (factored into a reusable helper). Five new operator/owner instructions (`SetPolicy` 205, `Freeze` 206, `Unfreeze` 207, `PauseBank` 208, `UnpauseBank` 209) are additive opcodes gated by the same block-level `do_verify` scan M2 introduced (extended to cover 204–209). `CardPolicy`/`SpendWindow` are already stored on `CardEntry` (M1); M3 is the first code to enforce/mutate them.

**Tech Stack:** Rust. `cowboy-protocol` codec (branch off M2 codec tip `bc20a68`) + `node` (branch off `feat/cip28-bankactor-m2`). Stacked PRs on M2 (#48 / #1085).

---

## Decisions (2026-07-20)

1. **Scope = M3-core** (user-decided). IN: `SetPolicy` (owner + `locked_after_transfer`); SpendWindow per-hour/day/month cap enforcement in `charge_gas`; `allowed_receivers` enforcement (callee = the ExecuteActor target); `Freeze`/`Unfreeze` (card) + `PauseBank`/`UnpauseBank` (bank), operator-gated; **F1(b)** — restrict `set_default_card` owner-set. **DEFERRED (M3.5/M4):** `allowed_syscall_kinds` (the outer instruction is always a generic `ExecuteActor`, which does not statically map to a `SyscallKind` — needs a CIP-28 §5.2 mapping decision), `GasCharged` event, timer-card integration, `Token(U)`-gas peg (§4.4).
2. **Cap-breach = REJECT (spec §4.2), via a pre-execution admission check** — SUPERSEDED, see RC1. (The original fall-through idea violated §4.2 and made the cap toothless.) An eligible default card whose rolled cap headroom `< max_total_cost` rejects the tx pre-execution; ineligible cards still fall through; settle charges actual + accumulates the window. Conservation unchanged (settle debits `covered`, accumulated).
3. **`allowed_receivers` — DEFERRED to M3.5** — SUPERSEDED, see RC2. (At the fee tier `receiver == card.agent`, a degenerate self-check; it can't express the spec whitelist. Deferred with `allowed_syscall_kinds`.) M3-core enforces **caps only** + the M2 eligibility checks.
4. **Activation gate**: all M3 opcodes (205–209) + the enforcement behavior are gated by `BANK_ACTIVATION_HEIGHT` (unchanged const, `u64::MAX`). Extend M2's block-level `do_verify` predicate (`block_has_bank_v2_tx`/`tx_is_bank_v2`) to cover **204–209** (all post-M1 additive bank opcodes) — below the height a block carrying any is rejected wholesale (mirror `block_has_foreign_chain_tx`; NOT a tx-level Err). M1's 200–203 ship via re-genesis (ungated); 204–209 are the coordinated-flag-day set.
5. **F1 = (b) restrict `set_default_card`** (self-contained, no wire change): in the owner-set branch, allow the owner to set an agent's default ONLY when the agent currently has no default (`read_default_card == None`) OR the existing default's owner == caller. Closes the "attacker owns a card naming a victim agent → overrides the victim's default" vector. (Full IssueCard agent-consent — option (a) — is a larger wire/SDK change, deferred.)
6. **BLOCKS_PER_* constants** added to `types/src/constants.rs`: `BLOCKS_PER_HOUR = 3_600`, `BLOCKS_PER_DAY = 86_400`, `BLOCKS_PER_MONTH = 2_592_000` (1s block cadence; 30-day month, matching `MAX_TIMER_TTL_BLOCKS`).
7. **Operator auth** for Freeze/Unfreeze/PauseBank/UnpauseBank = `caller == bank.operator` (the M1 genesis-seeded `BankEntry.operator`, an EOA/multisig address). Mirror the `caller == card.owner` equality-gate pattern.

---

## Deep-audit revisions (2026-07-20 — BINDING; supersede conflicting text below)

A 2-lens plan audit found spec-violating caps semantics, a mis-wired `allowed_receivers`, and 4 state-machine defects that go live when Freeze/PauseBank ship. These win:

- **RC1 (was DEFECT-1/D5, HIGH) — caps = REJECT, not fall-through** (CIP-28 §4.2/§4.5: `CapExceeded → reject`). Fall-through makes the cap toothless (any downstream tier funds the overflow). **Implement as a pre-execution admission check** (user-decided): early in `execute_transaction` (near the escrow, pre-instruction, gated by `BANK_ACTIVATION_HEIGHT`), if `tx.instruction` is `ExecuteActor{actor}` and `actor` has an **eligible** default card (Native, Active, not expired, bank Active) and the card's (rolled, read-only) cap headroom `< max_total_cost` → **reject the tx** (an OutOfFunds-equivalent / `BankCapExceeded`, deterministic, no instruction effect — joins the existing pre-execution escrow-reject family). The settle-tier drop-in (M2) then charges the **actual** from the card + accumulates the window (`*_spent += covered`); since `actual ≤ max_total_cost ≤ headroom`, settle can never breach — no cap re-check needed at settle. An **ineligible** card still falls through (M2); only an **eligible** card whose cap can't cover the worst case rejects. The read-only pre-check rolls the window in-memory (deterministic `period_id = height/BLOCKS_PER_*`) but does NOT persist; the settle does the real roll+accumulate+`write_card`.
- **RC2 (was DEFECT-2/D4, HIGH) — DEFER `allowed_receivers`** to M3.5 alongside `allowed_syscall_kinds`. At the fee tier the card is `read_default_card(actor)` so `receiver == actor == card.agent` — a degenerate self-check ("is the agent in its own whitelist"); a real receiver whitelist would `covered=0`-brick the card and can't see the agent's inner cross-actor calls (same `ExecuteActor`-outer-instruction blocker that defers syscall_kinds). Remove `allowed_receivers` from Task 3; M3-core enforces **caps only** (+ the M2 eligibility checks).
- **RC3 (was D1, HIGH) — Freeze/Unfreeze status preconditions.** `Freeze` requires `card.status == Active` (reject Closed/Frozen/Expired); `Unfreeze` requires `card.status == Frozen` (reject others). Else a Closed card resurrects to Active with no indices (§5.3 Closed = "no other write").
- **RC4 (was D2, HIGH) — remove the `bank.status == Active` check from `bank_withdraw`.** §3.3: PauseBank stops charge/deposit/issue but **withdraw stays allowed** (§1.4 pause disables charges, does not confiscate). `PauseBank` is the first writer of `Paused`; without this fix a pause traps every owner's funds. (Deposit/issue/charge keep their bank-Active check; withdraw drops it.)
- **RC5 (was D3, HIGH) — `bank_close_card` gains a `status != Frozen` guard.** Close does a native sweep to `refund_to` (a withdraw-equivalent); §5.3 denies fund extraction on a Frozen card. Without this, an owner under a compliance freeze closes the card to extract native, defeating the operator hold.
- **RC6 (was D8, MED) — `set_policy` status guard**: allow only `status ∈ {Active, Frozen}` (§5.3 Frozen permits SetPolicy; Closed/Expired do not).
- **RC7 (was DEFECT-3, LOW) — u128-clamp order**: compute `coverable = min(amount as u128, headroom_hour, headroom_day, headroom_month) as u64` (min in u128, cast last). Casting a per-tier headroom to u64 before the min can silently truncate (`2^64 as u64 == 0` → spurious 0).
- **RC8 — gate tests**: extend `tx_is_bank_v2` to opcodes **204–209** (all post-M1 additive) and add a below-height `do_verify`-reject test for **each** of 205–209 (not just 205) — the match is hand-maintained; a missed opcode = decode fork.
- **RC9 (was D6/D7) — document, not block**: F1(b) closes the primary override vector but a front-runner can lock out a **guardian** from bootstrapping a *fresh* agent's default (the agent itself always self-heals; griefing, not theft) — note it (full IssueCard agent-consent = M4). And the devnet genesis `bank_operator = Address::ZERO` makes Freeze/PauseBank un-invokable (zero can't sign → no auth bypass, but a real M3 deployment MUST re-genesis with a non-zero operator — an operability precondition).

## Baseline anchors (2026-07-20 map — verify before editing)

- `bank_charge_gas` (M2): `execution/src/bank/handlers.rs:373-419` — eligibility fall-throughs (`:388-400`) then native debit `covered = amount.min(acct.balance)` (`:409`) + `set_account` (`:414`). **Make `card` mut, add roll+cap+receiver between `:400` and the debit, persist via `write_card`.**
- Fee-fork call site: `execution/src/execution/transaction.rs:449-484` — `if let Instruction::Actor(ActorInstruction::ExecuteActor { actor, .. })`, `read_default_card(store, actor)` (`:475`), `bank_charge_gas(store, &card, total_fee, block_height)` (`:477`). Pass `actor` (the receiver) into charge_gas for §3.
- `CardPolicy` `bank/mod.rs:244-252`; `SpendWindow` `:324-332` (already on `CardEntry`, zero-init at issue `handlers.rs:267-274`).
- `BankEntry.operator` `bank/mod.rs:357-364`; genesis-seeded via M1 T7 `initial_storage` (GenesisConfig.bank_operator).
- Status: `CardStatus`/`BankStatus` `bank/mod.rs:116-165`; read in every handler; set only to Closed/Active today (Freeze/Pause are the first writers of Frozen/Paused).
- `set_default_card` owner-set branch `handlers.rs:314-332` (F1); `read_default_card` `storage.rs`.
- Codec: `SYS_BANK_* 200-204` `cowboy-protocol/.../instruction.rs:367-371`; decode ends `204 =>` `:3638`. 205-209 free.
- Block-level gate: `chain/src/application.rs` `block_has_bank_v2_tx`/`tx_is_bank_v2` (M2) + `do_verify` scan (~:2050) + propose exclusion (~:1779).
- Orphaned reader (M2-audit cleanup): `bank::storage::genesis_stablecoin_whitelist` (Vec reader) — only tests use it now; `stablecoin_whitelist_contains` still live in `issue_card`.

---

## Task 0: Dev setup (stacked on M2)
Branch `feat/cip28-bankactor-m3` off `feat/cip28-bankactor-m2` in both repos; re-add the dev `[patch]` to `node/Cargo.toml`; `cargo build -p cowboy-types`; commit the patch (node). Do NOT push.

## Task 1: Codec — 5 new SYS_BANK_* instructions (205–209)
Mirror M2's `BankSetDefaultCard`. Add (all additive):
- `BankSetPolicy { card_address: Address, policy: Vec<u8> }` (205) — `policy` = a serialized `CardPolicy` bounded `0..=8192` (same as M1 `initial_policy`).
- `BankFreeze { card_address: Address, reason: Vec<u8> }` (206) — `reason` bounded `0..=256`.
- `BankUnfreeze { card_address: Address }` (207).
- `BankPauseBank { bank_id: u32, reason: Vec<u8> }` (208) — `reason` `0..=256`.
- `BankUnpauseBank { bank_id: u32 }` (209).
Const block + variants + `sub_type`/encode/encode_size/decode. Roundtrip + opcode tests. Golden vectors untouched (additive). Commit (codec).

## Task 2: Node — consts, uniqueness, extend the block-level gate
- [ ] `BLOCKS_PER_HOUR/DAY/MONTH` in `constants.rs` (Decision 6).
- [ ] `sys_opcode_uniqueness` rows for 205–209.
- [ ] Extend `chain/src/application.rs` `tx_is_bank_v2` to match **all** of opcodes 204–209 (BankSetDefaultCard + the 5 new) — so the block-level `do_verify` gate + propose exclusion reject any of them below `BANK_ACTIVATION_HEIGHT` (Decision 4). Test: a block with a 205 tx below height → `do_verify` false.

## Task 3: SpendWindow caps — pre-execution reject + settle accumulate (consensus core; RC1/RC2/RC7)
No `allowed_receivers` (deferred, RC2). Caps are enforced as a **pre-execution reject** + a **settle-time window accumulate**.

- [ ] **Pure headroom helper** `rolled_cap_headroom(card: &CardEntry, block_height: u64) -> u128` (read-only; does NOT mutate/persist): for each tier compute `period_id = block_height / BLOCKS_PER_*`; the tier's effective spent is `if card.window.*_period_id == period_id { card.window.*_spent } else { 0 }` (a rolled period has 0 spent); `headroom_tier = cap.map(|c| c.saturating_sub(effective_spent)).unwrap_or(u128::MAX)`; return `min(headroom_hour, headroom_day, headroom_month)` (all u128; RC7 — stay in u128, do not cast per-tier to u64).
- [ ] **Pre-execution cap-admission check** in `execute_transaction` (near the escrow ~:180, before the instruction runs; gated `if block_height >= BANK_ACTIVATION_HEIGHT`): if `tx.instruction` is `ExecuteActor{actor}` and `read_default_card(store, actor)` is `Some(card_addr)` and that card is **eligible** (Native gas, `status==Active`, not expired, bank `Active` — reuse the M2 eligibility predicate), and `rolled_cap_headroom(card, block_height) < (max_total_cost as u128)` → **reject the tx** with an OutOfFunds-equivalent / `BankCapExceeded` structured error (deterministic; the instruction never executes; nonce consumed like the sender-escrow OutOfFunds path). An **ineligible** card / no default card → no cap check here (M2 fall-through at settle handles it). NOTE: this pre-check is read-only (no `write_card`) — the window is rolled in-memory only.
- [ ] **Settle-time accumulate** in `bank_charge_gas` (keep the M2 signature `(store, card_addr, amount, block_height)` — no `receiver`): after the M2 eligibility fall-throughs and the balance-clamped `covered = amount.min(card_account.balance)`, before returning: roll+persist the window — for each tier, if `window.*_period_id != period_id` set `*_spent = 0` and the id; `window.*_spent += covered as u128` (u128, can't overflow: with a cap, `spent ≤ cap`; the pre-check guaranteed headroom ≥ max ≥ actual ≥ covered, so accumulation never breaches); `write_card`. (Because the pre-check already rejected a cap-breaching tx, settle never needs to cap `covered` — it debits `min(amount, balance)` as M2 and just records it.)
- [ ] Update M2's `bank_charge_gas` tests + add: **cap breach → tx REJECTS pre-execution** (assert the tx fails with the cap error, the card is NOT debited, and — the conservation invariant — a rejected tx moves no funds); within-cap tx charges the card + accumulates spent; window roll across a period boundary resets spent then accumulates; `None` caps = unlimited (never rejects on that tier); two card-paid txs in one block accumulate sequentially (deterministic).
- [ ] **Conservation** — a within-cap tx is exactly the M2 fold (card debits `covered`, sender escrow/refund untouched); a cap-rejected tx moves no funds. Re-run `econ_invariants` (must stay 11/11).

## Task 4: SetPolicy + Freeze/Unfreeze + PauseBank/UnpauseBank handlers (with the RC3–RC6 state-machine fixes)
- [ ] `set_policy(store, card_address, policy_raw, caller)`: owner-only (`caller == card.owner`); **RC6 status guard** — reject unless `status ∈ {Active, Frozen}` (§5.3; Closed/Expired can't SetPolicy); **§5.4 lock** — `if card.policy.locked_after_transfer && card.owner == card.agent { return Err }`; `CardPolicy::decode(policy_raw)?` (≤64/≤16); overwrite `card.policy`, **leave `window` untouched** (a policy change can't reset spent); `write_card`; emit `CardPolicySet`.
- [ ] `freeze(store, card_address, reason, caller)`: `caller == bank.operator` (load bank via `card.bank_id`); **RC3** require `card.status == Active` (reject Closed/Frozen/Expired — no resurrection); `card.status = Frozen`; `write_card`; emit `CardFrozen{reason}`. `unfreeze`: operator; **RC3** require `card.status == Frozen`; → `Active` (or `Expired` if `expires_at` passed); emit `CardUnfrozen`.
- [ ] `pause_bank(store, bank_id, reason, caller)`: `caller == bank.operator`; `bank.status = Paused`; `write_bank`; emit `BankPaused`. `unpause_bank`: operator; `Paused → Active`; emit `BankUnpaused`.
- [ ] **RC4 — remove the `bank.status == Active` check from `bank_withdraw`** (§3.3: withdraw stays allowed under a paused bank; §1.4 pause ≠ confiscation). Keep it on deposit/issue/charge.
- [ ] **RC5 — add `if card.status == Frozen { return Err }` to `bank_close_card`** (Frozen denies the native-sweep fund extraction; §5.3).
- [ ] Dispatch arms (system_instruction.rs bank block) + `bank_pause_gate` classifier + `speculative.rs` emitter (→ 0x16) + `indexer/json.rs` + register the new topics (`CardPolicySet`/`CardFrozen`/`CardUnfrozen`/`BankPaused`/`BankUnpaused`) in `consensus_event_topics.rs`.
- [ ] Tests (Frozen/Paused are now the FIRST reachable — dead branches wake up): SetPolicy owner-only + Closed-reject + lock reject + bounds; Freeze by operator (non-operator + non-Active rejected) → `charge_gas` falls through / `withdraw` rejected / **deposit still ALLOWED** (§5.3) / **close rejected** (RC5) on the Frozen card; Unfreeze (non-Frozen rejected); PauseBank by operator → deposit/issue/charge rejected but **withdraw still succeeds** (RC4) → Unpause restores. Cross-bank: operator(A) can't freeze bank-B's card (resolved via `card.bank_id`).

## Task 5: F1(b) + cleanup
- [ ] `set_default_card` owner-set branch (Decision 5): when `caller == card.owner && caller != agent`, additionally require `read_default_card(agent)?` is `None` OR its card's `owner == caller`; else `Err(Unauthorized)`. Test: attacker (owns card naming victim agent) cannot override the victim's existing (different-owner) default; the agent itself and a same-owner re-point still work.
- [ ] Remove the orphaned `genesis_stablecoin_whitelist` Vec reader (M2-audit cleanup) if still unused by production after M3; keep `stablecoin_whitelist_contains`. Fix the stale doc comment naming it.

## Task 6: Full workspace green + deep-audit diff + finalize (GATED)
`cargo build/test/clippy --workspace` green; exhaustive matches for 205–209; `econ_invariants` + `token` green; golden vectors (codec) untouched. Deep-audit the diff (caps conservation, Frozen/Paused now-live reachability, operator-auth, F1, the extended gate). **Finalize (user-gated):** codec PR (base = M2 codec branch or main) + node PR (base = `feat/cip28-bankactor-m2`, stacked) + rev-pin bump. Do NOT push without explicit user authorization.

---

## Staging beyond M3-core
- **M3.5** — `allowed_syscall_kinds` (needs the CIP-28 §5.2 ExecuteActor→SyscallKind mapping decision), `GasCharged` event (explicit 0x16 emitter into the fee-fork's local events vec + §3.6 payload + topic registration), timer-card integration (shared window logic at the timer precharge), `Token(U)`-gas peg (§4.4 genesis-fixed rate).
- **M4** — `MintFromFiatVoucher` + `issuance_principal` population; off-chain gateway; `settle_provider` (§6.3, on M4 + W1 burn_from). Full IssueCard agent-consent (F1 option a).
- **M5** — `RegisterBank`/`SetBankOperator`; multi-bank; `TransferOwnership`.

## Self-review vs CIP-28 §7.2 M3
- SetPolicy → T4. SpendWindow enforcement → T3. whitelist match (receivers) → T3. Freeze/Unfreeze/PauseBank → T4. `locked_after_transfer` → T4. Deferred (documented, Decision 1): allowed_syscall_kinds, GasCharged, timer, Token-gas peg. Consensus/flag-day: all gated at `BANK_ACTIVATION_HEIGHT`, block-level gate extended to 204–209 (Decision 4), caps conserve supply (Decision 2). F1 override vector closed (Decision 5).
