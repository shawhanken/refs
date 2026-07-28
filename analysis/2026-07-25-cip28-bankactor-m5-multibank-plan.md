# CIP-28 BankActor M5 — Multi-Bank + Rotation + Card Ownership Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the CIP-28 BankActor (0x16) M5 roadmap line (`cip-28...md:777` "Multi-bank + ownership transfer"): per-bank operator/fiat-signer rotation, card ownership transfer, and (in the governance sub-milestone) multi-bank registration + multi-bank provider settlement.

**Architecture:** The storage layer is *already* fully `bank_id`-parametric (`BankEntry`, all card/index/nonce/voucher keys carry `bank_id`; `read_bank`/`write_bank`/`read_bank_seq`/`write_bank_seq` exist). M5 fills the **instruction/handler layer**. All additions are strictly additive (new opcodes / new proposal variant) — never a reshape of an existing wire variant (a reshape = decode-fork, the M4 opcode-200 lesson). **This plan was hardened after a 4-lens adversarial deep-audit** (consensus / auth / conservation / spec); the audit's findings (3 HIGH, 5 MED) are folded below and each mapped to the task that closes it.

**Tech Stack:** Rust. Wire codec in the external git crate `cowboy-protocol-codec` (repo `cowboyinc/cowboy-protocol`, pinned by rev in `types/Cargo.toml:49`); node crates `cowboy-execution` (`execution/src/`), `cowboy-chain` (`chain/src/application.rs`), `cowboy-types`, `cowboy-runner`, and `cowboy-storage` (`storage/src/speculative.rs` — event-emitter attribution, a consensus site). Two-repo dance: codec PR → merge → re-pin node.

> **⚠ CONSENSUS FLAG-DAY (audit consensus-F4).** `BANK_ACTIVATION_HEIGHT` is now `10` (bank-v2 is LIVE on devnet from height 10), NOT the `u64::MAX` land-gated-off sentinel the earlier milestones assumed. The `tx_is_bank_v2` below-activation gate only protects blocks *below* height 10; a live network already past 10 gets ZERO protection from it. Adding decodable opcodes 213/214/215 is therefore a **hard codec flag-day**: a legacy node (old codec) receiving a block with a new opcode at height ≥10 cannot decode it and rejects the block wholesale while upgraded nodes accept → fork. **M5 requires a coordinated all-validator binary upgrade before the first 213/214/215 tx is submitted.** The gate/tests are correctness scaffolding, not the deployment safety mechanism — the fleet upgrade is.

---

## Decisions & 待裁 (audit-hardened; recommended choice ★, with the deep-audit finding that settled it)

**D1 — chain_id preimage binding: ★ EXCLUDE from M5 (defer; needs CIP amendment first).**
CIP-28 §3.3 (`cip-28...md:301-303`) and CIP-36 §7 (`cip-36...md:178`) state the voucher preimage binds `bank_id` but NOT `chain_id` (per-chain distinct HSM keys are the cross-chain-replay defense; `voucher_id = hash(stripe_charge_id ‖ chain_id ‖ bank_id)` puts chain_id in the *id value*, not the signed preimage). Binding chain_id into the preimage contradicts the spec and would invalidate the golden-vector KATs = consensus flag-day. **Audit spec-H4 CONFIRMS this reading is conformant** and further notes M5-core adds *no signed voucher at all* (rotations + card transfer are `caller==owner/operator`, no preimage) → chain_id is fully N/A to M5-core. → Do NOT implement in M5; a future amendment + new golden vectors would be its own flag-day.

**D2 — provider settlement `bank_id`: ★ MOVE `BankSettleProviderV2` (opcode 216) to M5-gov, ship it WITH RegisterBank + per-bank token isolation.** *(Changed by audit spec-H2 / auth-M3 / consensus-F2.)*
Original plan put a `bank_id`-carrying settle in M5-core. **Audit spec-H2 (MED-HIGH) proved a latent isolation break:** opcode 215 as originally drafted threads `bank_id` into the *auth* (`read_bank(bank_id).operator`) but still burns the hard-coded `CUSD_TOKEN_ID` (bank 1's token; CUSD `burn_from_authority` is globally 0x16). Once RegisterBank (M5-gov) creates banks 2..N, *every* registered bank's operator could burn CUSD from any CUSD-holder — a §6.1 authority-isolation break. Multi-bank settle is only *meaningful* once a 2nd bank exists (M5-gov), and its token-scoping MUST be designed together with bank creation. → **Defer to M5-gov** as opcode **216 `BankSettleProviderV2`**, where the settled-token isolation is resolved (see M5-gov T-S). Opcode **211 `BankSettleProvider` stays exactly as-is** (bank-1 CUSD settle) — untouched, no decode-fork. (Alternative rejected: ship 215 in M5-core with a "genesis-bank-only CUSD" guard — it would be functionally identical to 211 until per-bank tokens exist, i.e. dead surface; cleaner to defer.)

**D3 — `RegisterBank` authorization: ★ CIP-12 governance proposal → ExecuteProposal → `apply_register_bank` (M5-gov).**
The codebase deliberately removed every naive `tx.from == 0x09` external governance gate (COW-1028/1026/1019); governance actions apply only via a passed proposal (`system_instruction.rs:652-687`). CIP-28 §3.4 (`cip-28...md:312`) says RegisterBank is "authorized via CIP-12 governance proposal (Tier 1 registry write)". **Audit spec-H6 CONFIRMS** the proposal routing conforms to every §3.4 MUST. → New governance proposal variant + `apply_register_bank`; does NOT consume a bank SystemInstruction opcode. Scoped M5-gov (governance baseline confirmed SMALL — see M5-gov).

**D4 — `SetBankOperator` dual auth: ★ external opcode 213 (`caller==operator`) in M5-core AND the CIP-12 governance-override branch in M5-gov — NOT "deferred unless requested".** *(Strengthened by audit spec-H3 / auth-M2.)*
Spec §3.4 (`cip-28...md:313`): "caller == current operator, OR authorized via CIP-12 governance". **Audit spec-H3 (MED) flagged deferring the governance branch as a spec-completeness gap:** it is the *recovery path* for a lost/compromised operator key — and audit auth-M2 (MED) shows M5-core's `SetBankOperator` can irreversibly brick a bank (rotate to an unspendable address) with **no recovery** if the governance override is absent. → Commit the governance-override (`SubmitSetBankOperatorProposal` / `apply_set_bank_operator`) to **M5-gov scope** (not optional). M5-core ships the operator-branch opcode 213 with a reserved-band guard (audit auth-M2 fix, Task 3).

**D5 — `SetBankFiatMintSigner`: ★ external opcode 214, `caller==operator` (M5-core).**
Spec §3.4 (`cip-28...md:314`). **Audit auth-Hyp2 CONFIRMS** rotating to `None` is safe (fail-closes the mint: `bank_mint_from_fiat_voucher` `ok_or`-fails on a `None` signer, `handlers.rs:1462`, before any state change; withdraw/settle authorize on `operator` not the signer, so no funds strand). Note: the spec *roadmap table* lists it under M4 (`cip-28...md:776`) but it is unimplemented; M5 delivers it.

**D6 — `TransferOwnership`: ★ ADD as a NEW card-owner opcode 215 in M5-core — it is a CARD operation, NOT bank-operator rotation.** *(CORRECTED by audit spec-H1, HIGH.)*
The prior plan mis-collapsed `TransferOwnership` into `SetBankOperator`. **Audit spec-H1 (HIGH) proved a category error:** §3.1 (`cip-28...md:251`) defines `TransferOwnership { card_address, new_owner, set_locked: bool }` — auth `caller == card owner`, `new_owner ≠ 0x00`; mutates `CardEntry.owner` (NOT the address, `:217`); if `set_locked`, sets `locked_after_transfer = true`; emits `CardOwnerTransferred { card, old_owner, new_owner, locked }` (§3.6 `:331`). It is a **Card-Owner** op (`:85`), distinct entity/fields/auth/event from `SetBankOperator` (a bank-governance op). The roadmap line 777 pairs *two distinct* ops. The `locked_after_transfer` *consumer* already exists (`handlers.rs:820` rejects `SetPolicy` on a locked self-custodied card) but its *producer* — the `set_locked` path — does not; M5 must deliver it. → Add card `TransferOwnership` (opcode 215 `BankTransferOwnership`, handler, `CardOwnerTransferred` event, `locked_after_transfer` producer) as its own M5-core task (Task 5).

---

## Sub-milestone structure (audit-restructured)

- **M5-core** (this plan, concrete below): opcodes **213 `SetBankOperator`** (operator branch), **214 `SetBankFiatMintSigner`**, **215 `BankTransferOwnership`** (card ownership transfer) — all operate safely on *existing* banks/cards. Plus the three cross-cutting consensus/safety sites the audit surfaced: **event-emitter attribution** (`speculative.rs`, HIGH consensus-F1), **Council-pause admission** (`bank_pause_gate.rs`, HIGH auth-H1), and the **below-activation gate** — plus hardened conservation invariants. No governance-subsystem dependency; no new bank is created (so the M5-gov isolation questions don't arise here).
- **M5-gov** (scoped, concrete below): `RegisterBank` CIP-12 proposal (creates banks 2..N) + **216 `BankSettleProviderV2`** (multi-bank settle, WITH per-bank token isolation resolving spec-H2) + `SetBankOperator` governance-override (recovery path, D4). Delivered as a stacked follow-up so multi-bank settle's isolation is designed alongside bank creation.

Deliver M5-core first (this plan → deep-audit of the DIFF → harden → PR), then M5-gov as a stacked follow-up (its own plan → deep-audit).

---

## Cross-cutting consensus/safety sites (audit-surfaced — every new bank opcode MUST touch ALL of these)

Any new bank SystemInstruction opcode is not "one handler" — it has **five** mandatory touch-points. Missing any one is a fork or a kill-switch hole. This checklist applies to 213/214/215 (and later 216):

1. **Codec** (`cowboy-protocol-codec`): opcode const + variant + encode + decode + round-trip test. The `#[deny]` unreachable-pattern guard (`:3777`) compile-checks opcode uniqueness.
2. **Dispatch** (`system_instruction.rs`): a **standalone top-level match arm** (mirror `BankSettleProvider` `:5182` / `BankIssueCardV2` `:5109`) — **NOT** added to the grouped `:4960-4968` guard whose inner match ends in `_ => unreachable!()` (audit consensus-F3: adding to that guard without an inner arm = deterministic **panic/halt**).
3. **Activation gate** (`chain/src/application.rs`): add to `tx_is_bank_v2` (`:2601`) — the SINGLE predicate feeding both propose-exclusion (`:1832`) and `do_verify` block-reject (`:2103`). Omission = fork below activation (audit consensus-F9, load-bearing).
4. **Event-emitter attribution** (`storage/src/speculative.rs:391-452`): add the variant to the Bank arm (`:448`) so its events attribute to `0x16` (`BANK_ACTOR_SYSTEM_ACTOR`). **Omission = the events keep emitter `= tx.from`, changing `logs_root → receipt_root` — a consensus divergence** (audit consensus-F1, HIGH). The handler doc-comments claim "attributes to 0x16 by `speculative::system_event_emitter`" — that claim is FALSE unless this match is edited.
5. **Council-pause admission** (`execution/src/execution/bank_pause_gate.rs:12-30`): add the variant to `system_instruction_targets_bank` so a Council emergency freeze of 0x16 blocks it (`assert_bank_not_paused_for_instruction`, `system_instruction.rs:63`). **Omission = the emergency kill-switch is selectively ineffective for the new op** (audit auth-H1, HIGH — most critical for value-moving ops).

Task 6 below drives sites 2–5 for all three opcodes in one place; site 1 is Task 1.

---

## File Structure (M5-core)

- **`cowboy-protocol` repo** `crates/cowboy-protocol-codec/src/instruction.rs` — 3 opcode consts (213/214/215), 3 variants, 3 encode+decode arms, 3 round-trip tests.
- **`node`** `types/Cargo.toml` — re-pin `cowboy-protocol-codec` rev to the merged codec SHA.
- **`node`** `execution/src/bank/handlers.rs` — `set_bank_operator` (213), `set_bank_fiat_mint_signer` (214), `transfer_card_ownership` (215) handlers; new event encoders + topics; a shared reserved-band guard reuse.
- **`node`** `execution/src/bank/mod.rs` — `CardEntry` already has `owner` + `locked_after_transfer` (verify field names); no struct change expected.
- **`node`** `execution/src/execution/system_instruction.rs` — 3 standalone dispatch arms.
- **`node`** `execution/src/execution/bank_pause_gate.rs` — add 3 variants to `system_instruction_targets_bank`.
- **`node`** `storage/src/speculative.rs` — add 3 variants to the Bank arm of `system_event_emitter`; extend `bank_events_attribute_to_bank_actor` test.
- **`node`** `chain/src/application.rs` — extend `tx_is_bank_v2`; add M5 gate test.
- **`node`** `execution/src/econ_invariants.rs` + `execution/src/execution/tests.rs` — hardened conservation invariants (audit conserv-F1/F2).

---

## M5-core Tasks

### Task 1: Codec — opcodes 213/214/215 (cowboy-protocol repo)

**Files:** Modify `crates/cowboy-protocol-codec/src/instruction.rs` (consts near `:367-384`; variants near `:657-722`; encode near `:1721-1733`; decode near `:3865-3929`; tests same file). Match the neighboring `BankPauseBank`/`BankSettleProvider` arms' exact reader/encoder helper names (`push_opt_addr`, `read_u32_be`, `read_addr`, `read_opt_addr`, the encode-buffer identifier).

- [ ] **Step 1: Write failing round-trip tests**

```rust
#[test]
fn set_bank_operator_roundtrip() {
    let inst = SystemInstruction::SetBankOperator { bank_id: 7, new_operator: Address::from_low_u64(0xABCD) };
    let b = inst.encode();
    assert_eq!(b[0], SYS_BANK_SET_BANK_OPERATOR); // 213
    assert_eq!(SystemInstruction::decode(&b).unwrap(), inst);
}
#[test]
fn set_bank_fiat_mint_signer_roundtrip() {
    for signer in [None, Some(Address::from_low_u64(0xBEEF))] {
        let inst = SystemInstruction::SetBankFiatMintSigner { bank_id: 3, new_signer: signer };
        let b = inst.encode();
        assert_eq!(b[0], SYS_BANK_SET_BANK_FIAT_MINT_SIGNER); // 214
        assert_eq!(SystemInstruction::decode(&b).unwrap(), inst);
    }
}
#[test]
fn bank_transfer_ownership_roundtrip() {
    for set_locked in [false, true] {
        let inst = SystemInstruction::BankTransferOwnership {
            card_address: Address::from_low_u64(0xCA5D), new_owner: Address::from_low_u64(0x0E), set_locked };
        let b = inst.encode();
        assert_eq!(b[0], SYS_BANK_TRANSFER_OWNERSHIP); // 215
        assert_eq!(SystemInstruction::decode(&b).unwrap(), inst);
    }
}
```

- [ ] **Step 2: Run, verify fail to compile.** `cargo test -p cowboy-protocol-codec _roundtrip` → FAIL (variants absent).

- [ ] **Step 3: Add opcode constants** (after `SYS_BANK_ISSUE_CARD_V2 = 212`)

```rust
pub const SYS_BANK_SET_BANK_OPERATOR: u8 = 213;
pub const SYS_BANK_SET_BANK_FIAT_MINT_SIGNER: u8 = 214;
pub const SYS_BANK_TRANSFER_OWNERSHIP: u8 = 215;
```

- [ ] **Step 4: Add enum variants**

```rust
/// CIP-28 §3.4 (M5): rotate a bank's operator. Auth: caller == current operator.
SetBankOperator { bank_id: u32, new_operator: Address },
/// CIP-28 §3.4 (M5): rotate/remove a bank's fiat-mint signer. Auth: caller == operator.
/// `None` removes the signer (fail-closes the fiat-mint path).
SetBankFiatMintSigner { bank_id: u32, new_signer: Option<Address> },
/// CIP-28 §3.1 (M5): transfer a card's owner. Auth: caller == current card owner.
/// `set_locked` sets `locked_after_transfer` (§5.4), barring later self-custody policy edits.
BankTransferOwnership { card_address: Address, new_owner: Address, set_locked: bool },
```

- [ ] **Step 5: Add encode arms** (fixed BE; `push_opt_addr` for the option; `set_locked` as 1 byte 0/1)

```rust
SystemInstruction::SetBankOperator { bank_id, new_operator } => {
    out.push(SYS_BANK_SET_BANK_OPERATOR);
    out.extend_from_slice(&bank_id.to_be_bytes());
    out.extend_from_slice(new_operator.as_ref());
}
SystemInstruction::SetBankFiatMintSigner { bank_id, new_signer } => {
    out.push(SYS_BANK_SET_BANK_FIAT_MINT_SIGNER);
    out.extend_from_slice(&bank_id.to_be_bytes());
    push_opt_addr(&mut out, new_signer);
}
SystemInstruction::BankTransferOwnership { card_address, new_owner, set_locked } => {
    out.push(SYS_BANK_TRANSFER_OWNERSHIP);
    out.extend_from_slice(card_address.as_ref());
    out.extend_from_slice(new_owner.as_ref());
    out.push(if *set_locked { 1 } else { 0 });
}
```

- [ ] **Step 6: Add decode arms** (mirror the neighboring 208/211 decoders; reject a `set_locked` byte >1 as `InvalidData` for canonical encoding)

```rust
SYS_BANK_SET_BANK_OPERATOR => SystemInstruction::SetBankOperator {
    bank_id: read_u32_be(&mut cur)?, new_operator: read_addr(&mut cur)? },
SYS_BANK_SET_BANK_FIAT_MINT_SIGNER => SystemInstruction::SetBankFiatMintSigner {
    bank_id: read_u32_be(&mut cur)?, new_signer: read_opt_addr(&mut cur)? },
SYS_BANK_TRANSFER_OWNERSHIP => {
    let card_address = read_addr(&mut cur)?;
    let new_owner = read_addr(&mut cur)?;
    let set_locked = match read_u8(&mut cur)? { 0 => false, 1 => true, _ => return Err(/*InvalidData*/) };
    SystemInstruction::BankTransferOwnership { card_address, new_owner, set_locked }
}
```

- [ ] **Step 7: Run, verify PASS + compile.** `cargo test -p cowboy-protocol-codec _roundtrip` (3 PASS); `cargo build -p cowboy-protocol-codec` (the `#[deny]` guard confirms opcode uniqueness).

- [ ] **Step 8: Commit + open cowboy-protocol PR.** `feat(cip28): add M5 bank opcodes 213 SetBankOperator, 214 SetBankFiatMintSigner, 215 BankTransferOwnership`. After merge, note the merged MAIN SHA for Task 2.

### Task 2: Re-pin node to the merged codec rev

**Files:** Modify `node/types/Cargo.toml` (`cowboy-protocol-codec` `rev = "..."`).
- [ ] **Step 1:** Update `rev` to the merged cowboy-protocol **main** SHA (NOT the feature-branch SHA — squash-merge re-pin lesson).
- [ ] **Step 2:** `cargo build -p cowboy-types -p cowboy-execution 2>&1 | tail` → compiles; new variants resolve. Do NOT commit `Cargo.lock`.

### Task 3: `set_bank_operator` handler (213) — with reserved-band guard (audit auth-M2)

**Files:** Modify `execution/src/bank/handlers.rs` (handler + `TOPIC_BANK_OPERATOR_SET` near `:55` + `encode_bank_and_operator` near `:274`).

- [ ] **Step 1: Write the failing test**

```rust
#[tokio::test]
async fn set_bank_operator_rotates_authz_and_reserved_band() {
    let mut s = test_store_with_genesis_bank().await; // bank 1, operator = OP
    let mut events = Vec::new();
    let new_op = addr(0x9E);
    // wrong caller rejected
    assert!(matches!(set_bank_operator(&mut s, &mut events, GENESIS_BANK_ID, &new_op, &addr(0xBAD)).await, Err(ExecutionError::Unauthorized)));
    // ZERO rejected
    assert!(matches!(set_bank_operator(&mut s, &mut events, GENESIS_BANK_ID, &Address::ZERO, &OP).await, Err(ExecutionError::InvalidData)));
    // reserved system band [0x00, 0x100) rejected (audit auth-M2)
    assert!(matches!(set_bank_operator(&mut s, &mut events, GENESIS_BANK_ID, &Address::from_low_u64(0x16), &OP).await, Err(ExecutionError::InvalidData)));
    // operator rotates to a valid EOA
    set_bank_operator(&mut s, &mut events, GENESIS_BANK_ID, &new_op, &OP).await.unwrap();
    assert_eq!(storage::read_bank(&s, GENESIS_BANK_ID).await.unwrap().unwrap().operator, new_op);
    assert_eq!(events.last().unwrap().0, TOPIC_BANK_OPERATOR_SET);
    // old operator can no longer rotate
    assert!(matches!(set_bank_operator(&mut s, &mut events, GENESIS_BANK_ID, &OP, &OP).await, Err(ExecutionError::Unauthorized)));
}
```

- [ ] **Step 2: Run, verify fail.** `cargo test -p cowboy-execution set_bank_operator_rotates`.

- [ ] **Step 3: Implement** (pause_bank pattern + reserved-band guard). Reuse the existing reserved-band check: `require_receiver_ok` (`handlers.rs:105-110`) refuses `[0x00, 0x100)`; extract or mirror its predicate as `fn is_reserved_band(a: &Address) -> bool` and apply it.

```rust
pub const TOPIC_BANK_OPERATOR_SET: &str = "BankOperatorSet";

/// `BankOperatorSet { bank_id, new_operator }`: `bank_id(4 BE) ‖ new_operator(20)`.
fn encode_bank_and_operator(bank_id: u32, new_operator: &Address) -> Vec<u8> {
    let mut v = Vec::with_capacity(24);
    v.extend_from_slice(&bank_id.to_be_bytes());
    v.extend_from_slice(new_operator.as_ref());
    v
}

/// `SetBankOperator` (CIP-28 §3.4, opcode 213): the bank's current `operator` rotates
/// ownership to `new_operator`. Check-then-apply. Emits `BankOperatorSet`.
/// Rejects `new_operator` in the reserved system band `[0x00, 0x100)` (incl. ZERO): a
/// bank whose operator nobody controls is permanently bricked, and M5-core ships no
/// governance override (that recovery path is M5-gov). Emits `BankOperatorSet`.
pub async fn set_bank_operator<S: StateStore>(
    store: &mut S, events: &mut Vec<(String, Vec<u8>)>, bank_id: u32,
    new_operator: &Address, caller: &Address,
) -> Result<(), ExecutionError> {
    let mut bank = storage::read_bank(store, bank_id).await?.ok_or(ExecutionError::InvalidData)?;
    if *caller != bank.operator { return Err(ExecutionError::Unauthorized); }
    if is_reserved_band(new_operator) { return Err(ExecutionError::InvalidData); }
    bank.operator = *new_operator;
    storage::write_bank(store, &bank).await?;
    events.push((TOPIC_BANK_OPERATOR_SET.to_string(), encode_bank_and_operator(bank_id, new_operator)));
    Ok(())
}
```

- [ ] **Step 4: Run, verify PASS.** `cargo test -p cowboy-execution set_bank_operator_rotates -- --nocapture`.
- [ ] **Step 5: Commit.** `feat(cip28): M5 set_bank_operator handler (213) with reserved-band guard`.

### Task 4: `set_bank_fiat_mint_signer` handler (214)

**Files:** Modify `execution/src/bank/handlers.rs` (handler + `TOPIC_BANK_FIAT_SIGNER_SET` + `encode_bank_and_opt_signer`; widen `push_opt_addr` to `pub(crate)` if private to mod.rs).

- [ ] **Step 1: Write the failing test**

```rust
#[tokio::test]
async fn set_bank_fiat_mint_signer_rotate_and_remove() {
    let mut s = test_store_with_genesis_bank().await; // operator = OP, signer = Some(SIG)
    let mut events = Vec::new();
    let new_sig = addr(0x51);
    assert!(matches!(set_bank_fiat_mint_signer(&mut s, &mut events, GENESIS_BANK_ID, Some(new_sig), &addr(0xBAD)).await, Err(ExecutionError::Unauthorized)));
    set_bank_fiat_mint_signer(&mut s, &mut events, GENESIS_BANK_ID, Some(new_sig), &OP).await.unwrap();
    assert_eq!(storage::read_bank(&s, GENESIS_BANK_ID).await.unwrap().unwrap().fiat_mint_signer, Some(new_sig));
    assert_eq!(events.last().unwrap().0, TOPIC_BANK_FIAT_SIGNER_SET);
    set_bank_fiat_mint_signer(&mut s, &mut events, GENESIS_BANK_ID, None, &OP).await.unwrap();
    assert_eq!(storage::read_bank(&s, GENESIS_BANK_ID).await.unwrap().unwrap().fiat_mint_signer, None);
}
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** (pause_bank pattern; no reserved-band guard needed — a `None`/reserved signer only fail-closes the mint, per audit auth-Hyp2 REFUTED-safe).

```rust
pub const TOPIC_BANK_FIAT_SIGNER_SET: &str = "BankFiatSignerSet";

/// `BankFiatSignerSet { bank_id, new_signer }`: `bank_id(4 BE) ‖ opt_addr(new_signer)`.
fn encode_bank_and_opt_signer(bank_id: u32, new_signer: &Option<Address>) -> Vec<u8> {
    let mut v = Vec::with_capacity(25);
    v.extend_from_slice(&bank_id.to_be_bytes());
    push_opt_addr(&mut v, new_signer);
    v
}

/// `SetBankFiatMintSigner` (CIP-28 §3.4, opcode 214): the bank `operator` rotates or
/// removes (`None`) the fiat-mint signer. Removing fail-closes `bank_mint_from_fiat_voucher`
/// (`ok_or` on a `None` signer). Emits `BankFiatSignerSet`.
pub async fn set_bank_fiat_mint_signer<S: StateStore>(
    store: &mut S, events: &mut Vec<(String, Vec<u8>)>, bank_id: u32,
    new_signer: Option<Address>, caller: &Address,
) -> Result<(), ExecutionError> {
    let mut bank = storage::read_bank(store, bank_id).await?.ok_or(ExecutionError::InvalidData)?;
    if *caller != bank.operator { return Err(ExecutionError::Unauthorized); }
    bank.fiat_mint_signer = new_signer;
    storage::write_bank(store, &bank).await?;
    events.push((TOPIC_BANK_FIAT_SIGNER_SET.to_string(), encode_bank_and_opt_signer(bank_id, &new_signer)));
    Ok(())
}
```

- [ ] **Step 4: Run, verify PASS.**
- [ ] **Step 5: Commit.**

### Task 5: `transfer_card_ownership` handler (215) — card owner transfer + lock producer (audit spec-H1)

**Files:** Modify `execution/src/bank/handlers.rs` (handler + `TOPIC_CARD_OWNER_TRANSFERRED` + `encode_card_owner_transferred`). First **read `CardEntry`** (`mod.rs` near `:500-516`) to confirm the exact field names for `owner`, `locked_after_transfer`, and any owner→card index that must be re-pointed on transfer.

- [ ] **Step 0: Read `CardEntry` + the owner index.** Confirm whether transferring `owner` requires updating `card_by_owner_key(owner, bank_id, idx)` (`storage.rs:58`) / `card_owner_count_key`. If the owner index must move to the new owner, that is part of this handler; if the index is only a discovery aid keyed at issuance, document that `TransferOwnership` updates `CardEntry.owner` but does NOT reindex (and whether that is spec-acceptable per §3.1). **Flag this for the diff deep-audit** — an un-reindexed transfer could leave the card discoverable under the old owner.

- [ ] **Step 1: Write the failing test**

```rust
#[tokio::test]
async fn transfer_card_ownership_authz_lock_and_owner() {
    let mut s = test_store_with_card().await; // card C, owner = OWN, unlocked
    let mut events = Vec::new();
    let new_owner = addr(0x0E);
    // non-owner rejected
    assert!(matches!(transfer_card_ownership(&mut s, &mut events, &C, &new_owner, false, &addr(0xBAD)).await, Err(ExecutionError::Unauthorized)));
    // new_owner ZERO rejected (§3.1 new_owner != 0x00)
    assert!(matches!(transfer_card_ownership(&mut s, &mut events, &C, &Address::ZERO, false, &OWN).await, Err(ExecutionError::InvalidData)));
    // owner transfers with set_locked
    transfer_card_ownership(&mut s, &mut events, &C, &new_owner, true, &OWN).await.unwrap();
    let card = storage::read_card(&s, &C).await.unwrap().unwrap();
    assert_eq!(card.owner, new_owner);
    assert!(card.locked_after_transfer);
    assert_eq!(events.last().unwrap().0, TOPIC_CARD_OWNER_TRANSFERRED);
    // old owner can no longer transfer
    assert!(matches!(transfer_card_ownership(&mut s, &mut events, &C, &OWN, false, &OWN).await, Err(ExecutionError::Unauthorized)));
    // locked card: SetPolicy by new owner now rejected (the §5.4 consumer at handlers.rs:820)
    assert!(matches!(set_policy(&mut s, &mut events, &C, &some_policy(), &new_owner).await, Err(ExecutionError::Unauthorized) | Err(ExecutionError::InvalidData)));
}
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** (§3.1: auth `caller == card.owner`, `new_owner != ZERO`, set `owner`, conditionally set `locked_after_transfer`, emit `CardOwnerTransferred { card, old_owner, new_owner, locked }`).

```rust
pub const TOPIC_CARD_OWNER_TRANSFERRED: &str = "CardOwnerTransferred";

/// `CardOwnerTransferred { card, old_owner, new_owner, locked }`:
/// `card(20) ‖ old_owner(20) ‖ new_owner(20) ‖ locked(1)`.
fn encode_card_owner_transferred(card: &Address, old_owner: &Address, new_owner: &Address, locked: bool) -> Vec<u8> {
    let mut v = Vec::with_capacity(61);
    v.extend_from_slice(card.as_ref());
    v.extend_from_slice(old_owner.as_ref());
    v.extend_from_slice(new_owner.as_ref());
    v.push(if locked { 1 } else { 0 });
    v
}

/// `TransferOwnership` (CIP-28 §3.1, opcode 215): the card's current `owner` transfers
/// ownership to `new_owner`; if `set_locked`, sets `locked_after_transfer` (§5.4), which
/// bars later self-custody `SetPolicy` (consumer at handlers.rs:820). Does NOT change the
/// card address — only `CardEntry.owner`. Check-then-apply. Emits `CardOwnerTransferred`.
pub async fn transfer_card_ownership<S: StateStore>(
    store: &mut S, events: &mut Vec<(String, Vec<u8>)>, card_address: &Address,
    new_owner: &Address, set_locked: bool, caller: &Address,
) -> Result<(), ExecutionError> {
    let mut card = storage::read_card(store, card_address).await?.ok_or(ExecutionError::InvalidData)?;
    if *caller != card.owner { return Err(ExecutionError::Unauthorized); }
    if *new_owner == Address::ZERO { return Err(ExecutionError::InvalidData); }
    let old_owner = card.owner;
    card.owner = *new_owner;
    if set_locked { card.locked_after_transfer = true; } // §3.1: set_locked only sets, never clears
    storage::write_card(store, &card).await?;
    events.push((TOPIC_CARD_OWNER_TRANSFERRED.to_string(),
        encode_card_owner_transferred(card_address, &old_owner, new_owner, set_locked)));
    Ok(())
}
```

(Use the actual `CardEntry` write helper — `storage::write_card` or the equivalent used by `set_policy`/`freeze`.)

- [ ] **Step 4: Run, verify PASS.** `cargo test -p cowboy-execution transfer_card_ownership -- --nocapture`.
- [ ] **Step 5: Commit.**

### Task 6: Wire the 5 consensus/safety sites for 213/214/215

**Files:** `execution/src/execution/system_instruction.rs` (dispatch), `execution/src/execution/bank_pause_gate.rs` (Council-pause), `storage/src/speculative.rs` (emitter), `chain/src/application.rs` (activation gate + test). See the "Cross-cutting" checklist above — sites 2–5.

- [ ] **Step 1: Dispatch (site 2)** — add THREE **standalone top-level arms** (mirror `BankSettleProvider` `:5182`), NOT to the `:4960-4968` grouped guard (audit consensus-F3 — that path hits `unreachable!()`):

```rust
cowboy_types::SystemInstruction::SetBankOperator { bank_id, new_operator } => {
    gas_meters.cycles.consume(self.gas_costs.base_cycles)?;
    gas_meters.cells.consume(self.gas_costs.base_cells)?;
    bank::set_bank_operator(store, &mut self.system_events, *bank_id, new_operator, sender).await.map(|_| None)
}
cowboy_types::SystemInstruction::SetBankFiatMintSigner { bank_id, new_signer } => {
    gas_meters.cycles.consume(self.gas_costs.base_cycles)?;
    gas_meters.cells.consume(self.gas_costs.base_cells)?;
    bank::set_bank_fiat_mint_signer(store, &mut self.system_events, *bank_id, *new_signer, sender).await.map(|_| None)
}
cowboy_types::SystemInstruction::BankTransferOwnership { card_address, new_owner, set_locked } => {
    gas_meters.cycles.consume(self.gas_costs.base_cycles)?;
    gas_meters.cells.consume(self.gas_costs.base_cells)?;
    bank::transfer_card_ownership(store, &mut self.system_events, card_address, new_owner, *set_locked, sender).await.map(|_| None)
}
```

(Confirm `sender` is `&tx.from` here — audit auth-Hyp1 confirmed both production call sites pass `&tx.from`, signature-bound.)

- [ ] **Step 2: Council-pause (site 5)** — add all three to `system_instruction_targets_bank` (`bank_pause_gate.rs:12-30`):

```rust
| SystemInstruction::SetBankOperator { .. }
| SystemInstruction::SetBankFiatMintSigner { .. }
| SystemInstruction::BankTransferOwnership { .. } => true,
```

- [ ] **Step 3: Emitter attribution (site 4)** — add all three to the Bank arm of `system_event_emitter` (`speculative.rs:448`):

```rust
| SystemInstruction::SetBankOperator { .. }
| SystemInstruction::SetBankFiatMintSigner { .. }
| SystemInstruction::BankTransferOwnership { .. } => Some(BANK_ACTOR_SYSTEM_ACTOR),
```

- [ ] **Step 4: Activation gate (site 3)** — extend `tx_is_bank_v2` (`application.rs:2601`):

```rust
| BankSettleProvider | BankIssueCardV2
| SetBankOperator | SetBankFiatMintSigner | BankTransferOwnership => true,
```

- [ ] **Step 5: Write the gate + emitter tests**

```rust
// chain: gate coverage (mirror bank_m4_opcodes_210_to_212_gated_below_activation)
#[test]
fn bank_m5_opcodes_213_to_215_gated_below_activation() {
    for inst in [
        SystemInstruction::SetBankOperator { bank_id: 1, new_operator: Address::from_low_u64(1) },
        SystemInstruction::SetBankFiatMintSigner { bank_id: 1, new_signer: None },
        SystemInstruction::BankTransferOwnership { card_address: Address::from_low_u64(2), new_owner: Address::from_low_u64(3), set_locked: false },
    ] { assert!(tx_is_bank_v2(&tx_with(inst))); assert!(block_below_activation_rejects(inst)); }
}
// storage: emitter attribution (extend bank_events_attribute_to_bank_actor, speculative.rs:3336)
// assert system_event_emitter(&SetBankOperator{..}) == Some(BANK_ACTOR_SYSTEM_ACTOR), and same for 214/215.
```

- [ ] **Step 6: Run all four sites' tests, verify PASS.** `cargo test -p cowboy-chain bank_m5 && cargo test -p cowboy-storage bank_events_attribute && cargo test -p cowboy-execution set_bank_ transfer_card_ownership`.

- [ ] **Step 7: Commit.** `feat(cip28): M5 wire 213/214/215 — dispatch, council-pause, emitter, activation gate`.

### Task 7: Conservation invariants — CONCRETE, pinned-pool, mutation-verified (audit conserv-F1/F2)

**Files:** `execution/src/econ_invariants.rs` + `execution/src/execution/tests.rs`. **Mandatory rigor (audit conserv-F1/F2 — the prose-stub false-green is the #564/#589 escape class):** each proptest MUST have a concrete `prop_assert*` body over a **FIXED account pool** that includes every address the handler touches, assert BOTH native-CBY Σ AND CUSD `total_supply` are conserved, and have a NAMED mutation that turns it RED. Mirror `econ_token_supply_conservation` (`econ_invariants.rs:550/607-624`, fixed `TOKEN_POOL`, `Σ == total_supply` after every op) and `econ_bank_fiat_mint_then_settle_conserves_supply` (`:995-996`, asserts BOTH `supply == mint-burn` AND `Σ CUSD == supply`).

- [ ] **Step 1: Write `econ_bank_rotation_conserves_all_balances`** — a FIXED pool `[OP, new_op, SIG, new_sig, provider, 0x16]`; snapshot `Σ native CBY over the pool` and `CUSD total_supply` before; run `set_bank_operator` + `set_bank_fiat_mint_signer` + `transfer_card_ownership`; `prop_assert_eq!` both snapshots after (rotations/transfer move NO value; only `BankEntry.operator`/`fiat_mint_signer`/`CardEntry.owner` change). NO empty strategy / no `prop_assume` that can starve cases.

- [ ] **Step 2: Mutation-check (RED-verify)** — inject a stray `credit(new_op, 1)` into `set_bank_operator` via scoped sed (commit first per `feedback_commit_before_mutation_test`); confirm `econ_bank_rotation_conserves_all_balances` goes RED **because `new_op` is in the pinned pool** (the audit-F1 hazard: an unpinned pool misses the credit). Revert via scoped sed (NOT `git checkout`).

- [ ] **Step 3: Full-execute conservation** in `mod bank_tx_conservation` (`execution/src/execution/tests.rs`) — drive `execute_transaction` with a real `SetBankOperator` tx (production dispatch path, sim==prod per audit conserv-F3) and assert the block's `Σ balances == prior` and `receipt_root` includes the 0x16-attributed `BankOperatorSet` event (ties Task 6 site-4 to a test).

- [ ] **Step 4: Run, verify PASS + mutation RED confirmed.** `cargo test -p cowboy-execution econ_bank_rotation bank_tx_conservation -- --nocapture`.
- [ ] **Step 5: Commit.**

### Task 8: fmt + full-workspace build + finalize

- [ ] **Step 1:** `cargo fmt --all` (Format CI must pass — `feedback_cargo_fmt_before_commit`).
- [ ] **Step 2:** Full-workspace build (an opcode/enum addition can break validator/cli/rpc — `feedback_shared_struct_field_workspace_build`): `cargo build --workspace --all-targets 2>&1 | tail` → clean.
- [ ] **Step 3:** `cargo test -p cowboy-execution -p cowboy-chain -p cowboy-storage -p cowboy-types 2>&1 | tail` → green (bank + gate + emitter + econ + cip28).
- [ ] **Step 4:** Deep-audit the DIFF (marshal deep-review-flow) BEFORE the PR — verify all 5 consensus/safety sites are wired for all 3 opcodes, the mutation actually reddens, and the Task-5 owner-reindex question is resolved.
- [ ] **Step 5: Commit + open node PR** base=devnet. Body: note the **consensus flag-day** (all-validator upgrade before first 213/214/215 tx); ends with the Claude Code line; NO AI attribution in commits. Do NOT self-merge (flag-day = fleet coordination).

---

## M5-gov (scoped; concrete — governance baseline confirmed SMALL, audit-hardened)

Adds `RegisterBank` (banks 2..N) + `BankSettleProviderV2` (216, multi-bank settle WITH token isolation) + `SetBankOperator` governance-override (recovery). Templates: submit-side `SubmitRegistryProposal` (`system_instruction.rs:2077`); enact-side `container_registry::set_settlement_config` (`container_registry.rs:716`) — the non-0x09-actor passed-proposal write precedent (RegisterBank writes 0x16, so NOT via `gov_enact.rs`/`GovWriter`, which hard-code 0x09). Genesis untouched (bank 1 + `bank_seq=2` seeded).

**M5-gov design decisions (audit-hardened):**
- **G-D1 enactment routing: ★ plain bank-registry module fn, reachable only from `ExecuteProposal`** (mirror container/executor registries). Audit auth-Hyp4 CONFIRMED reachability = authority (one production caller each, `payload_kind` set only by submit handlers, runs only after `SystemOrigin::for_passed_proposal` → `Passed`). **Advisory (audit auth-Hyp4):** consider threading `&origin` into `apply_register_bank` for capability parity even though the target is 0x16 — a future refactor adding another caller would otherwise silently bypass governance.
- **G-D2 tier binding: ★ MANDATORY `payload_kind → min_tier` check (NOT "optional").** *(Audit auth-H2, HIGH.)* `SubmitRegistryProposal` reads the tier straight off the wire (`system_instruction.rs:2095`) with no payload→tier binding; a `RegisterBank` submitted at Tier 0 (`ParamTuning`: `temp_check_threshold: 0`, `stake_quorum_pct: 5`, `deposit: 1_000`) would create a bank at 1/2 the quorum / no temp-check / 1/5 the deposit the spec's "Tier-1 registry write" mandates. → The submit handler MUST reject `RegisterBank` unless `tier == ProposalTier::Registry` (ideally a general `payload_kind → min_tier` table so the whole submit surface stops trusting the wire tier).
- **G-D3 overwrite guard: ★ `read_bank(store, seq).await?.is_none()` (NOT `seq != 0`).** *(Audit auth-M1, MED.)* `read_bank_seq` returns `Ok(0)` when absent and `write_bank` is an unconditional overwrite; a `seq != 0` guard still lets a regression that left `bank_seq == 1` overwrite the genesis bank's operator/signer (governance-seizing bank 1 via a *registration* proposal). Guard on "never overwrite an existing bank".
- **G-D4 216 `BankSettleProviderV2` token isolation: ★ a bank may settle ONLY a token it is authorized for.** *(Audit spec-H2, MED-HIGH.)* Do NOT let an arbitrary bank operator burn CUSD (bank 1's token). Options to resolve when M5-gov is designed: (a) add a per-bank `settle_token` / payout-token to `BankEntry` and enforce `token == bank.settle_token`; or (b) restrict CUSD settlement to the genesis bank and require third-party banks to name their own mint. Pick + spec-note in CIP-36 §6.3 (make the note **normative**, audit spec-H5). Also revisit the **global `settlement_used` marker** here (audit consensus-F2 / auth-M3): bank-scope it OR give an explicit adversarial justification that cross-bank `settlement_id`s are unpredictable — a compromised bank-A operator pre-consuming bank-B's id is a silent-no-op accounting hole otherwise.

**Concrete task outline (finalize into bite-sized TDD when M5-gov is picked up):**
- **G1 (codec):** `SubmitRegisterBankProposal { description_hash, voting_blocks, tier, name, operator, fiat_mint_signer: Option<Address> }` + opcode 216 `BankSettleProviderV2 { bank_id, token, provider, amount, settlement_id }` (note: carries an explicit `token` per G-D4) + `SubmitSetBankOperatorProposal`. Round-trip tests. Two-repo (share the M5-core codec PR if co-developed).
- **G2 (proposal record, node/runner):** `ProposalPayloadKind::RegisterBank` + `SetBankOperatorGov` variants (`runner/src/types.rs:~974`) + payload fields (all `#[serde(default)]`); update the two struct literals (`system_instruction.rs:6296`, `gov_origin.rs:139`). Map both → `ProposalTier::Registry` and enforce G-D2.
- **G3 (submit handler):** copy `SubmitRegistryProposal` (`:2077`); validate `name` 1..=32 ASCII + `operator != ZERO` (+ reserved-band); enforce G-D2 tier; deposit/promote/persist/emit.
- **G4 (dispatch + enact):** `ExecuteProposal` arms (`:4164`) → `apply_register_bank` / `apply_set_bank_operator`. `apply_register_bank`: `read_bank_seq` → **G-D3 guard** → `write_bank(BankEntry{ bank_id: seq, name, operator, fiat_mint_signer, status: Active, registered_at: block_height })` → `write_bank_seq(seq+1)` → emit `BankRegistered { bank_id, name, operator }` (audit spec-H6: payload MUST carry name+operator, not just bank_id).
- **G5 (216 handler):** `bank_settle_provider_for(store, bank_id, token, ...)` with the G-D4 token-authorization check; keep 211 as the bank-1 CUSD shortcut; wire ALL 5 consensus/safety sites (dispatch/pause-gate/emitter/gate/gate-test) for 216 — same checklist.
- **G6 (tests):** submit→vote→pass→execute integration (2nd bank at `bank_id=2`; Tier-0 RegisterBank REJECTED per G-D2; genesis-bank overwrite REJECTED per G-D3); then `SetBankOperator`/216 under `bank_id=2` work; cross-bank CUSD-burn attempt REJECTED per G-D4; conservation (RegisterBank moves no balance beyond the governance deposit, which the proposal lifecycle already accounts for — audit conserv-F8).

---

## Self-Review (writing-plans checklist)

- **Spec coverage:** SetBankOperator (§3.4→Task 3 + M5-gov override), SetBankFiatMintSigner (§3.4→Task 4), TransferOwnership (§3.1→Task 5, audit spec-H1), multi-bank settle (§6.3→M5-gov 216, D2/G-D4), RegisterBank (§3.4/§6.1→M5-gov, D3), chain_id (excluded, D1 — spec CONFORMS). Every roadmap-777 item mapped.
- **Placeholder scan:** codec helper names marked "match the neighboring arm" (external crate identifiers); test-store constructors (`test_store_with_genesis_bank`/`test_store_with_card`) reuse the existing bank-test harness. Task 5 Step 0 explicitly reads `CardEntry` before implementing (owner-reindex question flagged for the diff audit). These are the only non-literal spots; each names its concrete template.
- **Type consistency:** `bank_id: u32`, `Option<Address>` opt-addr, `[u8;32]`, `u128`, `set_locked: bool` — consistent across tasks and with `BankEntry`/`CardEntry`.

## Deep-audit resolution log (4-lens, 2026-07-25)

| Finding | Lens | Sev | Resolution |
|---|---|---|---|
| Events not attributed to 0x16 (missing `speculative.rs`) | consensus-F1 | HIGH | Task 6 Step 3 (site 4) + emitter test |
| `TransferOwnership` is a CARD op, wrongly collapsed | spec-H1 | HIGH | D6 corrected; Task 5 adds it (opcode 215) |
| New ops escape Council-pause kill-switch | auth-H1 | HIGH | Task 6 Step 2 (site 5) |
| RegisterBank tier binding "optional" | auth-H2 | HIGH | G-D2 MANDATORY tier check |
| 216 burns CUSD regardless of bank (isolation) | spec-H2 | MED-HI | D2: defer 215→216 to M5-gov WITH G-D4 token isolation |
| SetBankOperator gov-override deferred | spec-H3/auth-M2 | MED | D4: committed to M5-gov (recovery path) |
| Rotation/settle proptests are prose stubs | conserv-F1/F2 | MED | Task 7: concrete pinned-pool + dual-Σ + RED mutation |
| `apply_register_bank` guard too weak | auth-M1 | MED | G-D3: `read_bank(seq).is_none()` |
| SetBankOperator no reserved-band guard → brick | auth-M2 | MED | Task 3: `is_reserved_band` guard |
| Global settlement_used cross-bank griefing | consensus-F2/auth-M3 | MED | G-D4: revisit before M5-gov (bank-scope or justify) |
| Dispatch guard wording → `unreachable!()` | consensus-F3 | LOW | Task 6 Step 1: standalone arms, explicit |
| Above-activation is a hard flag-day | consensus-F4 | LOW | Flag-day banner at top; Task 8 Step 5 |
| §6.3 note should be normative | spec-H5 | LOW | G-D4 (normative note) |
| BankRegistered payload {bank_id,name,operator} | spec-H6 | LOW | G4 |
| Confused-deputy / dual-auth / enact reachability / signer-remove / cross-bank auth | all lenses | — | REFUTED (evidence in audit) |
