# CIP-28 BankActor — M3-core (policy triad + F1 fix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** The card **policy triad** — per-hour/day/month spend caps enforced in `charge_gas`, `allowed_receivers` whitelist, `Freeze`/`PauseBank` — plus `SetPolicy` and the **F1** consent fix. All gated behind `BANK_ACTIVATION_HEIGHT = u64::MAX` (inert until a coordinated flag-day).

**Architecture:** Stacked on M2 (`feat/cip28-bankactor-m2`). M2's `bank_charge_gas` is a drop-in card debit at the actor-pays fee tier; M3 makes it **roll the SpendWindow + enforce caps + check the receiver whitelist** before debiting (factored into a reusable helper). Five new operator/owner instructions (`SetPolicy` 205, `Freeze` 206, `Unfreeze` 207, `PauseBank` 208, `UnpauseBank` 209) are additive opcodes gated by the same block-level `do_verify` scan M2 introduced (extended to cover 204–209). `CardPolicy`/`SpendWindow` are already stored on `CardEntry` (M1); M3 is the first code to enforce/mutate them.

**Tech Stack:** Rust. `cowboy-protocol` codec (branch off M2 codec tip `bc20a68`) + `node` (branch off `feat/cip28-bankactor-m2`). Stacked PRs on M2 (#48 / #1085).

---

## Decisions (2026-07-20)

1. **Scope = M3-core** (user-decided). IN: `SetPolicy` (owner + `locked_after_transfer`); SpendWindow per-hour/day/month cap enforcement in `charge_gas`; `allowed_receivers` enforcement (callee = the ExecuteActor target); `Freeze`/`Unfreeze` (card) + `PauseBank`/`UnpauseBank` (bank), operator-gated; **F1(b)** — restrict `set_default_card` owner-set. **DEFERRED (M3.5/M4):** `allowed_syscall_kinds` (the outer instruction is always a generic `ExecuteActor`, which does not statically map to a `SyscallKind` — needs a CIP-28 §5.2 mapping decision), `GasCharged` event, timer-card integration, `Token(U)`-gas peg (§4.4).
2. **Cap-breach behavior = partial cover, then fall through** (mirrors M2's model). In `charge_gas`, `covered = amount.min(card_balance).min(remaining_headroom)` across the three tiers; the uncovered remainder falls through to the actor→owner→sender cascade (existing). Conservation stays automatic (card debits exactly `covered`, accumulated into the window). A cap of `None` = no limit on that tier.
3. **`allowed_receivers` at the fee tier**: the primary receiver of an `ExecuteActor{actor}` is the **callee `actor`**. If `policy.allowed_receivers` is non-empty and `actor ∉ allowed_receivers`, the card does not pay (`covered = 0`, fall through) — a graceful non-payment, not a tx reject (consistent with M2 fall-through). Empty list = any receiver.
4. **Activation gate**: all M3 opcodes (205–209) + the enforcement behavior are gated by `BANK_ACTIVATION_HEIGHT` (unchanged const, `u64::MAX`). Extend M2's block-level `do_verify` predicate (`block_has_bank_v2_tx`/`tx_is_bank_v2`) to cover **204–209** (all post-M1 additive bank opcodes) — below the height a block carrying any is rejected wholesale (mirror `block_has_foreign_chain_tx`; NOT a tx-level Err). M1's 200–203 ship via re-genesis (ungated); 204–209 are the coordinated-flag-day set.
5. **F1 = (b) restrict `set_default_card`** (self-contained, no wire change): in the owner-set branch, allow the owner to set an agent's default ONLY when the agent currently has no default (`read_default_card == None`) OR the existing default's owner == caller. Closes the "attacker owns a card naming a victim agent → overrides the victim's default" vector. (Full IssueCard agent-consent — option (a) — is a larger wire/SDK change, deferred.)
6. **BLOCKS_PER_* constants** added to `types/src/constants.rs`: `BLOCKS_PER_HOUR = 3_600`, `BLOCKS_PER_DAY = 86_400`, `BLOCKS_PER_MONTH = 2_592_000` (1s block cadence; 30-day month, matching `MAX_TIMER_TTL_BLOCKS`).
7. **Operator auth** for Freeze/Unfreeze/PauseBank/UnpauseBank = `caller == bank.operator` (the M1 genesis-seeded `BankEntry.operator`, an EOA/multisig address). Mirror the `caller == card.owner` equality-gate pattern.

---

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

## Task 3: `charge_gas` — SpendWindow caps + allowed_receivers (consensus core)
- [ ] Factor a helper `apply_spend_window_and_caps(card: &mut CardEntry, amount: u64, block_height: u64) -> u64` (returns the cap-limited coverable amount): for each tier compute `period_id = block_height / BLOCKS_PER_*`; if `card.window.*_period_id != period_id` reset `*_spent = 0`, set the id; `headroom_tier = cap.map(|c| c.saturating_sub(*_spent)).unwrap_or(u128::MAX)`; `coverable = amount.min(min headroom across tiers, clamped to u64)`; the caller accumulates `*_spent += covered` AFTER the actual debit (covered may be < coverable if card balance is lower). Keep it pure over the card struct (no store).
- [ ] Widen `bank_charge_gas` to `bank_charge_gas(store, card_addr, receiver: &Address, amount, block_height)`; load card as `mut`; after the M2 eligibility fall-throughs: **allowed_receivers** — `if !card.policy.allowed_receivers.is_empty() && !card.policy.allowed_receivers.contains(receiver) { return Ok(0) }` (Decision 3); **caps** — `coverable = apply_spend_window_and_caps(&mut card, amount, block_height)`; `covered = coverable.min(card_account.balance)`; if `covered == 0 { return Ok(0) }`; debit; `card.window.{hour,day,month}_spent += covered as u128`; `write_card`; return covered.
- [ ] Call site (`transaction.rs:477`): pass `actor` (the callee = receiver) → `bank_charge_gas(store, &card, actor, total_fee, block_height)`.
- [ ] Update M2's `bank_charge_gas` unit tests (signature) + add: cap breach → partial cover then fall-through (conservation still holds — assert Σ deltas + burn + tip == 0); window roll across a period boundary resets spent; receiver not in a non-empty whitelist → card pays 0 (fall through); `None` caps = unlimited.
- [ ] **Conservation is the key test** — the cap only changes how much the card covers vs the actor/sender; sender escrow/refund untouched → supply conserved (re-run `econ_invariants`).

## Task 4: SetPolicy + Freeze/Unfreeze + PauseBank/UnpauseBank handlers
- [ ] `set_policy(store, card_address, policy_raw, caller)`: owner-only (`caller == card.owner`); **§5.4 lock** — `if card.policy.locked_after_transfer && card.owner == card.agent { return Err }`; `CardPolicy::decode(policy_raw)?` (enforces ≤64/≤16); overwrite `card.policy` (leave `window` untouched); `write_card`; emit `CardPolicySet`.
- [ ] `freeze(store, card_address, reason, caller)`: `caller == bank.operator` (load bank via card.bank_id); `card.status = Frozen`; `write_card`; emit `CardFrozen{reason}`. `unfreeze`: operator; `Frozen → Active` (or `Expired` if `expires_at` passed); emit `CardUnfrozen`.
- [ ] `pause_bank(store, bank_id, reason, caller)`: `caller == bank.operator`; `bank.status = Paused`; `write_bank`; emit `BankPaused`. `unpause_bank`: operator; `Paused → Active`; emit `BankUnpaused`.
- [ ] Dispatch arms (system_instruction.rs bank block) + `bank_pause_gate` classifier + `speculative.rs` emitter (→ 0x16) + `indexer/json.rs` + register the new topics in `consensus_event_topics.rs`.
- [ ] Tests: SetPolicy owner-only + lock reject + policy bounds; Freeze by operator (non-operator rejected) → charge_gas/deposit now fall-through/reject on the Frozen card (Frozen no longer dead-branch); Unfreeze; PauseBank by operator → deposit/issue/charge rejected (bank Active check) → Unpause restores.

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
