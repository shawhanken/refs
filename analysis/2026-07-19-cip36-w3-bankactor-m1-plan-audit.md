# Deep Audit — CIP-28 BankActor M1 Implementation Plan

- **Date**: 2026-07-19
- **Target**: `refs/analysis/2026-07-19-cip36-w3-bankactor-m1-implementation-plan.md`
- **Method**: 5 parallel adversarial lenses (codec/opcode/wire · system-actor integration · data-model/serde-determinism · genesis/activation/fork · spec-compliance/gaps), each verified against live `node/` + `cowboy-protocol/` source and CIP-28/CIP-36 spec.
- **Verdict**: The plan's **address, opcode, derivation, and storage-key mechanics are correct** (verified byte-for-byte). But it has **1 unimplementable-as-written operation, 1 compile break, and a cluster of consensus/commitment defects** — most of which the plan's own "let the compiler flag it" verification cannot catch. Do **not** execute as written; apply the revisions below first.

---

## Severity-ranked findings

| # | Sev | Area | One-line |
|---|-----|------|----------|
| A1 | **BLOCKER** | storage | `CloseCard`/`Withdraw` "sweep all token balances" is unimplementable — no per-holder token enumeration exists (56-byte hashed `bal:` keys, no by-owner index; only a global chain-wide `mints_index`, unbounded, and M1 has no gas → griefing DoS) |
| A2 | **BLOCKER** | compile | `Address::from_slice(&h[12..32])` does not exist — use `Address::from_bytes(h[12..32].try_into().unwrap())` |
| A3 | **HIGH** | consensus encoding | Stored `CardEntry`/`BankEntry`/`CardPolicy` byte layout is **unpinned + self-contradictory** ("JSON/borsh" vs "mirror payment_gate" which is hand-rolled fixed bytes / no serde vs "implement serde"). Feeds `state_root`. No golden-vector KAT (round-trip can't catch cross-version drift) |
| A4 | **HIGH** | fork / rollout | Activation-gate + genesis-seed are **mutually contradictory**: an execution-layer gate cannot stop a *new-opcode decode fork* during rolling upgrade; the gate's source is unspecified (const vs genesis vs 0x09 gov-param); genesis seed fires only at block 0, so an already-running devnet has **no `bank:1`** → gate would enable an empty bank, every `IssueCard` fails |
| A5 | **HIGH** | consensus commitment | Card events get attributed to **`tx.from`, not BankActor `0x16`**, inside `logs_root`/bloom — `system_event_emitter` (`speculative.rs:390`) has a `_ => None` catch-all that **silently absorbs** the new `Bank*` variants with zero compiler error (COW-2435/TOB-18 provenance). Not in the plan's touch-list |
| A6 | **HIGH** | fund safety | The circuit-breaker **does not stop the card money path**: balance moves (`set_account`) aren't pause-gated (only `0x16` actor-storage writes are). Deposit/Withdraw succeed while paused; `CloseCard` sweeps funds then fails the `0x16` status write under pause → **pay-then-fail** (funds gone, card un-closed, indices dangling). Needs an instruction-level `assert_bank_not_paused` before any balance move |
| A7 | **HIGH** | cross-repo build | Re-pinning node to a codec descendant of `main` silently introduces `TokenBurnFrom` (opcode 24) — node devnet currently pins `b373b9a9` which has **no** opcode 24. That breaks every node `SystemInstruction` exhaustive match, unbudgeted by Task 8 |
| A8 | MED | spec | `issuance_principal` (CIP-36 §7, stamped at **IssueCard**, "the sybil hinge") is omitted from `CardEntry`; deferring to M4 forces a live stored-schema migration. Reserve the field now |
| A9 | MED | spec | `IssueCard` drops two §3.1 **write-time** validations: `gas_payment_token ∈ {Native, whitelisted stable}` and policy field bounds (`allowed_receivers ≤ 64`, `allowed_syscall_kinds ≤ 16` — semantic, not just the wire byte-cap). Genesis seeds no stablecoin whitelist to validate against |
| A10 | MED | wire | `initial_policy` bound `RangeCfg::from(0..=1024)` is too small — a max-legal `CardPolicy` (64 receivers × 20B = 1280B alone) is undecodable. PaymentGate uses `0..=8192`; keep wire cap == stored cap |
| A11 | MED | encoding | `CardPolicy` has **two** encodings (wire `Vec<u8>` + stored in `CardEntry`) with raw-store-vs-re-encode undecided — payment_gate stores raw to avoid decode→re-encode drift |
| A12 | MED | spec/CUSD | `Withdraw`/`CloseCard` to arbitrary `to`/`refund_to` collide with CUSD's mandatory transfer-hook allowlist (only `card↔PG`, `card↔owner`) — fails safe, but the sweep only works when `refund_to == owner`; unflagged |
| L1 | LOW | genesis | Operator for `bank_id=1` has **no council *address*** to reuse (`Council` is a `SignerSet`, not an `Address`); needs an explicit `GenesisConfig.bank_operator: Address` field, else a placeholder is baked into consensus genesis |
| L2 | LOW | model | `allowed_syscall_kinds: Vec<u16>` is lossy vs spec `Vec<SyscallKind>` (`Send=0` vs `Custom(0)` indistinguishable) |
| L3 | LOW | validation | `Withdraw.to` / `CloseCard.refund_to` bypass `validate_balance_recipient` → can send to zero / system-band addresses |
| L4 | LOW | tests | Frozen-branch TDD tests are unreachable in M1 (no Freeze until M3) — only reachable via a storage backdoor; plan presents them as normal handler tests |
| L5 | LOW | drift | Deposit missing `bank.status==Active`; CloseCard missing "not the default card" (M2) + "clear window"; `PayCurrency` enum vs `token: Address (0x0=CBY)` two currency reprs; `amount: u128` vs native CBY `u64` |
| L6 | LOW | doc-sync | CIP-28 body + WP §9.1 still say `0x13`; CIP-13 §1 opcode master table needs `200–203` — plan doesn't budget the doc amendments |
| L7 | LOW | tests | `system_actor_addrs_unique_across_namespaces` `entries[]` is hand-maintained (not from `ALL`) — add `BANK_ACTOR`/`BANK_ACTOR_SYSTEM_ACTOR` + alias group |

### Verified-correct (do not re-litigate)
`0x16` is free and correct (2026-07-14 reassignment `0x0D→0x13→0x16`; `0x13`=CONTAINER_REGISTRY); `ALL.len()` 22→23; card derivation matches CIP-28 §2.6 **exactly** (domain/BE widths/`[12..32]`); storage keys match §2.1 byte-for-byte (no prefix collision); `SystemInstruction`-variants IS "the style of SessionActor" (no separate `BankInstruction` category exists; a new top-level category would need a `TX_CATEGORY` byte — refuted the alternative); opcodes 200–203 free, 157 poisoned (correctly avoided); dispatch `match inst` has **no** catch-all (Bank arm is compiler-enforced); band-guard/rent is a non-issue for `0x16` and for keccak card addresses; the pause-roster test `pausable_matches_roster` makes adding `0x16` to `PAUSABLE_LOW_BYTES` mandatory (Task 2 covers it); M1 is genuinely **independent of W1/W2** (uses `handle_token_transfer` + native balance, no `burn_from`, no PG multi-party). serde_json on these struct shapes is **not** a per-validator fork (no maps/floats; Vecs order-preserving; `preserve_order` off).

---

## Required plan revisions

### R1 (A1) — Redesign `CloseCard`/`Withdraw` sweep to a bounded known-token set
Replace "move all token balances out" with: sweep only **native CBY + the genesis stablecoin whitelist** (the same whitelist A9 introduces). For any other CIP-20 token a card holds, rely on CIP-28 §5.3's post-Close **`Withdraw` residual-rescue** (Closed cards remain `Withdraw`-able) — spec-consistent and O(1). Never iterate the global `mints_index` (unbounded, un-gassed in M1 → DoS). Document that arbitrary reserve tokens are recovered via explicit `Withdraw`, not auto-swept.

### R2 (A4, A7) — Ship M1 as a **fresh devnet re-genesis**; drop `bank_activation_height`; sequence after W1
- **Drop the activation gate for M1.** On a fresh genesis every node runs the new binary from block 0, `bank:1` exists from block 0, opcodes 200–203 are known to all — there is nothing to gate and no legacy peer to fork against. The gate is *ineffective* against a new-opcode decode fork anyway (a legacy node can't decode the tx) and *redundant* on fresh genesis. **Defer activation-height machinery to M2**, where the fee-settle charge-fork actually touches a running chain and needs a genesis-derived, `verify()`-checked, 0x09-sourced flag-day (per PR#932/#934 principle).
- **Sequencing/build (A7):** branch the codec off node's actual pin `b373b9a9` (bank-only, no opcode 24) **or** land W3 after the W1 node-side handler branch merges to devnet. Do not silently inherit `TokenBurnFrom` via a `main`-descendant re-pin without budgeting node's opcode-24 arms.
- **If in-place upgrade of the live devnet is mandatory instead** (deployment decision — needs the team): the gate must (i) source from genesis/0x09 committed state, (ii) live at mempool-admission + `verify()` (block validity), not execution, and (iii) pair with a height-triggered `bank:1` materialization — none of which M1 currently contains. **This is the one open decision for the user: fresh re-genesis (recommended) vs in-place upgrade.**

### R3 (A2, A3, A11, L2) — Pin one stored encoding + golden KAT
- Fix `Address::from_bytes(h[12..32].try_into().unwrap())`.
- Encode stored structs with **hand-rolled fixed-layout bytes**, mirroring `payment_gate/mod.rs` (`PaymentPolicy::encode/decode`) — not serde — and **store `CardPolicy` raw** (the received wire bytes), like `payment_gate::write_policy_raw`, so there is exactly one `CardPolicy` encoding. Add a pinned-hex **golden-vector KAT** for `CardEntry`/`BankEntry`/`CardPolicy` (mirror `policy_v1_golden_vector`). Encode `allowed_syscall_kinds` faithfully (tag+u16 for `Custom`), not `Vec<u16>`.

### R4 (A5, A6) — Add the two missing consensus touch-sites to the plan
- **A5:** add `SystemInstruction::BankIssueCard | BankDeposit | BankWithdraw | BankCloseCard => Some(BANK_ACTOR_SYSTEM_ACTOR)` to `system_event_emitter` (`storage/src/speculative.rs:390`), + an attribution golden test. (Consciously decide Bank attribution — don't inherit the `_ => None` gap.)
- **A6:** add an instruction-level `assert_bank_not_paused_for_instruction(...)` at the **top** of the Bank dispatch arm (mirror `cbss_pause_gate` at `system_instruction.rs:52-58`), rejecting before any balance move — otherwise pause is illusory for the money path and CloseCard is pay-then-fail under pause.

### R5 (A8, A9, A12, L1) — Spec-faithful IssueCard + genesis
- Reserve `issuance_principal: [u8;32]` in `CardEntry` now (M1 may write zero/None; M4 populates) to avoid a live schema migration.
- IssueCard must validate (write-time): `gas_payment_token ∈ {Native} ∪ genesis-stablecoin-whitelist`; `allowed_receivers.len() ≤ 64`; `allowed_syscall_kinds.len() ≤ 16`.
- Genesis (Task 7): add a **stablecoin whitelist** (initially the CUSD token id, or empty on plain devnet) + an explicit `GenesisConfig.bank_operator: Address` field for `bank_id=1` (don't hand-wave "council address" — `Council` is a SignerSet).
- Document the CUSD escrow-hook interaction (A12): for CUSD, `Withdraw`/`CloseCard` succeed only when `to`/`refund_to == owner` (hook allowlist); fails safe otherwise.

### R6 (A10, L3, L5, L6) — Smaller fixes
- Raise `initial_policy` wire+stored bound to `0..=8192` (match PaymentGate); wire cap == stored cap.
- Validate `Withdraw.to` / `CloseCard.refund_to` via `validate_balance_recipient` (reject zero / system-band).
- Unify currency representation (use `PayCurrency` consistently; reconcile `u128` amount vs native CBY `u64`); add the deferred-precondition notes (Deposit `bank.status==Active`; CloseCard gains "not default card" + "clear window" in M2).
- Budget the doc amendments: CIP-28 body `0x13→0x16`, WP §9.1 row, CIP-13 §1 master table `200–203`. Add `entries[]` + alias group to `system_actor_addrs_unique_across_namespaces`.
- Drop/relabel the unreachable frozen TDD tests (L4) as forward-compat storage-backdoor tests, not handler tests.

---

## Net effect on the plan
- **Simpler**, not more complex: R2 removes the entire activation-gate subsystem from M1 (deletes 3 HIGH findings) in exchange for a fresh re-genesis.
- **Two net-new touch-sites** the plan missed: `system_event_emitter` (A5) and a bank pause-gate (A6) — both consensus-relevant, neither compiler-caught.
- **One design change** to CloseCard/Withdraw (bounded sweep + residual rescue, A1).
- **One open decision for the team**: fresh re-genesis (recommended) vs in-place upgrade of the live devnet (R2).
- Every derivation/opcode/key mechanic stands as written (verified byte-for-byte).
