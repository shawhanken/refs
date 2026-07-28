# CIP-28 BankActor M5-gov-A — RegisterBank (governance) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `RegisterBank` — a CIP-12 governance proposal that, when passed, writes a new `BankEntry` at the next `bank_id` under BankActor 0x16 — enabling banks 2..N (multi-bank), per CIP-28 §3.4 / §6.1.

**Architecture:** RegisterBank is authorized ONLY through the CIP-12 proposal machinery (the codebase deliberately removed naive `tx.from==0x09` external gates). Shape: a new `SubmitRegisterBankProposal` wire instruction → submit handler (copy of `SubmitRegistryProposal`) → `ProposalPayloadKind::RegisterBank` recorded on the `Proposal` → on pass, `ExecuteProposal` dispatch calls `apply_register_bank` (a plain bank-module fn, mirroring the `UpdateContainerSettlementConfig`→`container_registry::set_settlement_config` precedent for a passed-proposal write to a non-0x09 actor). The bank storage primitives (`read_bank_seq`/`write_bank_seq`/`write_bank`) already exist. This is greenfield — no `RegisterBank`/`BankRegistered` symbol exists today.

**Tech Stack:** Rust. Wire codec in the external `cowboy-protocol-codec` (two-repo dance: codec PR → merge → re-pin node — see the M5-core convergence). Node crates: `cowboy-runner` (the on-chain `Proposal` record + `ProposalPayloadKind`), `cowboy-execution` (submit handler + `ExecuteProposal` dispatch + `apply_register_bank`), `cowboy-storage` (event-emitter attribution).

**Scope note:** This is **M5-gov-A** (RegisterBank only). **M5-gov-B** (216 `BankSettleProviderV2` with per-bank token isolation + `SetBankOperator` governance-override) is a stacked follow-up — 216's multi-bank settle is only meaningful once banks 2..N exist (this plan), and its token-isolation needs a `BankEntry`/genesis design decision out of scope here.

---

## Decisions & 待裁 (recommended ★; audit-anchored)

**GD1 — Enactment routing: ★ plain bank-module fn `apply_register_bank(store, ...)`, NO `SystemOrigin` arg.**
Mirrors `container_registry::set_settlement_config` (`container_registry.rs:716`) — the precedent for a passed-proposal write to a non-0x09 actor. RegisterBank writes 0x16 (not 0x09), and `GovWriter` hard-codes 0x09, so it does NOT go through `gov_enact.rs`. Authority = reachability: the fn is `pub(in crate::execution)` and its ONLY caller is the `ExecuteProposal` dispatch arm, which runs only after `SystemOrigin::for_passed_proposal` succeeds (proposal `Passed`). **Advisory (defense-in-depth):** thread `&origin: &SystemOrigin` into the signature purely as a compile-time capability witness (a future second caller then can't reach it without a passed proposal) even though the write target is 0x16; the fn ignores it for the write. Recommended to accept the advisory (cheap, closes the "reachability-only" gap the M5-core diff audit flagged for the container/executor precedents).

**GD2 — Tier binding: ★ MANDATORY `tier == ProposalTier::Registry` guard in the submit handler.**
Confirmed by baseline §9: NO existing `payload_kind → required tier` binding — `tier` is caller-chosen and only fed to `tier.params()`. A `RegisterBank` at Tier 0 (`ParamTuning`: `temp_check_threshold: 0`, `stake_quorum_pct: 5`, `deposit: 1_000`) would create a bank at 1/2 the quorum, no temp-check, 1/5 the deposit that §3.4's "Tier-1 registry write" mandates. → Add `if tier != ProposalTier::Registry { return Err(ExecutionError::InvalidData); }` immediately after `from_u8`. (A general payload→min-tier table is out of scope; this single guard suffices for RegisterBank.)
**§3.4 Tier-3 reconciliation (spec-audit F1):** §3.4 also says "Tier 3 if also upgrading BankActor bytecode." The exact-`Registry` guard does NOT wrongly reject a legitimate Tier-3 RegisterBank, because the Tier-3 case is strictly the *bundled* register-plus-bytecode-upgrade operation — and opcode 216 carries no bytecode field, while the governance model is **one `ProposalPayloadKind` per `Proposal`** (single-payload), so a bundled register+upgrade is not expressible via 216 (it would be a separate system-actor-upgrade proposal type). Standalone RegisterBank is therefore exactly Tier 1; GD2's exact-match is conformant.

**GD6 — operator reserved-band: ★ reject `operator` in the reserved system band `[0x00, 0x100)` (NOT only `!= ZERO`), in BOTH submit and enact.** *(Audit auth-H6 / spec-F2, MEDIUM.)*
§3.4's literal bar is only `operator ≠ 0x00`, but M5-core's `SetBankOperator` rejects the whole reserved band via `require_receiver_ok` (`handlers.rs:109`, `RESERVED_SYSTEM_ADDRESS_LIMIT = 0x100`) with the rationale "a bank whose operator nobody controls is permanently bricked and M5 ships no governance override on this path." A passed RegisterBank could otherwise create a bank whose `operator` is a system actor (0x16/0x09/0x08) — which never originates transactions, so `caller == operator` is never satisfiable → the bank is **permanently bricked** (no rotate/pause/settle ever authorizable). Not fund theft (governance-gated), but a spec-parity footgun the rotation path already guards. → Guard `operator >= RESERVED_SYSTEM_ADDRESS_LIMIT` (reuse the reserved-band predicate) in the submit handler AND in `apply_register_bank` (re-validation). Stronger than §3.4's literal `≠ 0x00`, justified by consistency with `SetBankOperator`.

**GD3 — Overwrite guard: ★ `read_bank(store, id).await?.is_none()` before writing (NOT `seq != 0`).**
`read_bank_seq` returns `Ok(0)` when unset; genesis seeds `bank_seq = 2` (bank 1 pre-seeded). `apply_register_bank` allocates `let id = read_bank_seq(store)?;` then must **refuse to overwrite an existing bank**: `if read_bank(store, id)?.is_some() { return Err(...); }`. A bare `seq != 0` guard would still let a regression that left `bank_seq == 1` clobber the genesis bank's operator/signer (governance-seizing bank 1 via a *registration* proposal). Guard on "the target slot is empty".

**GD4 — `BankRegistered` event attribution: ★ RESOLVED (deep-audit, consensus lens) → attribute to the executor (`tx.from`), emitter UNCHANGED.**
`apply_register_bank` pushes `BankRegistered` into `self.system_events` during `ExecuteProposal`. Those events are drained with the placeholder emitter `= tx.from` (`transaction.rs:340-344`), then `system_event_emitter(&ExecuteProposal{..}, tx.from)` (`speculative.rs:2208`) is consulted — `ExecuteProposal` is absent from every `Some(..)` arm and falls to `_ => None` (`speculative.rs:457`), so the event KEEPS emitter `= tx.from`. This is **deterministic across all nodes** (identical `logs_root`/`receipt_root`) and identical to `governance.proposal.executed` and every other enact event. → **Lock option (a).** Options (b)/(c) — attribute to 0x16 — are **REJECTED**: the emitter returns ONE canonical `Option<Address>` applied to ALL events of the instruction and sees only `Instruction::System(ExecuteProposal{proposal_id})`, NOT the `payload_kind` (loading the proposal from 0x09 storage is out of the storage-crate emitter's reach). It physically cannot tag `BankRegistered`→0x16 while leaving `governance.proposal.executed`→tx.from; adding `ExecuteProposal => Some(0x16)` would re-tag EVERY governance payload's events for EVERY proposal kind → a fleet-wide `receipt_root` flag-day far broader than RegisterBank. So (a) is the ONLY deterministic-and-non-flag-day choice. **Documented divergence:** `BankRegistered` attributes to the proposal executor (governance context), NOT 0x16 — unlike direct `Bank*` system-instruction events; this is intentional and correct given the emitter model. Do NOT change `speculative.rs`.

**GD5 — Opcode number: ★ 216 `SubmitRegisterBankProposal`** (next guaranteed-free opcode; the governance-submit family is already numerically scattered, so a bank-family-adjacent number is not required). M5-gov-B's `BankSettleProviderV2` then takes 217.

---

## File Structure

- **`cowboy-protocol` repo** `crates/cowboy-protocol-codec/src/instruction.rs` — `SYS_SUBMIT_REGISTER_BANK_PROPOSAL = 216` const, `SubmitRegisterBankProposal` variant, opcode-map arm, encode arm, decode arm (name capped 0..=32), + round-trip/opcode tests.
- **`node`** `types/Cargo.toml` (+ the 8 convergence pins) — re-pin to the merged codec rev (coordinate with the M5-core convergence; if M5-core hasn't merged, this stacks on its rev).
- **`node`** `runner/src/types.rs` — `ProposalPayloadKind::RegisterBank` variant + `payload_bank_name` / `payload_bank_operator` / `payload_bank_fiat_mint_signer` fields on `Proposal` (all `#[serde(default)]`).
- **`node`** `execution/src/execution/system_instruction.rs` — `new_governance_proposal` default initializers for the 3 new fields; the `SubmitRegisterBankProposal` submit-handler arm; the `ExecuteProposal` dispatch arm for `RegisterBank`.
- **`node`** `execution/src/bank/mod.rs` (or a new `execution/src/execution/bank_registry.rs`) — `apply_register_bank` + `BankRegistered` event const/encoder.
- **`node`** `execution/src/consensus_event_topics.rs` — register `BankRegistered`.
- **`node`** `execution/src/execution/cbss_pause_gate.rs` — add `ProposalPayloadKind::RegisterBank => false` to `proposal_payload_targets_cbss` (2nd exhaustive match; audit consensus).
- **`node`** `execution/src/econ_invariants.rs` — RegisterBank conservation proptest (Task 7b).
- **NOT** `storage/src/speculative.rs` — GD4 resolved to (a); the emitter is UNCHANGED.

---

## Tasks

### Task 1: Codec — `SubmitRegisterBankProposal` opcode 216 (cowboy-protocol repo)

**Files:** Modify `crates/cowboy-protocol-codec/src/instruction.rs`. Templates (verbatim from baseline): const `SYS_SUBMIT_REGISTRY_PROPOSAL = 112` (:340); variant (:1084); opcode-map (:1812); encode (:2876); decode (:4370); round-trip test (:5621).

- [ ] **Step 1: Write failing round-trip test** (append to the codec test module)

```rust
#[test]
fn submit_register_bank_proposal_round_trips_at_216() {
    for signer in [None, Some(Address::from_bytes([0x51; 20]))] {
        let inst = SystemInstruction::SubmitRegisterBankProposal {
            description_hash: [0x11; 32],
            voting_blocks: 100,
            tier: 1,
            name: b"Second Bank".to_vec(),
            operator: Address::from_bytes([0x42; 20]),
            fiat_mint_signer: signer,
        };
        let bytes = inst.encode();
        assert_eq!(bytes[0], SYS_SUBMIT_REGISTER_BANK_PROPOSAL); // 216
        assert_eq!(SystemInstruction::decode(&bytes).unwrap(), inst);
    }
}
```

- [ ] **Step 2: Run, verify fail.** `cargo test -p cowboy-protocol-codec --features signing,serde submit_register_bank` → FAIL (variant absent).

- [ ] **Step 3: Add the const** (after `SYS_BANK_TRANSFER_OWNERSHIP = 215`):

```rust
/// CIP-28 §3.4 (M5-gov): submit a governance proposal to register a new bank.
pub const SYS_SUBMIT_REGISTER_BANK_PROPOSAL: u8 = 216;
```

- [ ] **Step 4: Add the variant** (near the other `Submit*Proposal` variants):

```rust
/// CIP-28 §3.4 (M5-gov): RegisterBank governance proposal. `name` 1..=32 bytes;
/// `operator` != 0x00 (validated node-side); enacts to BankActor 0x16 on pass.
SubmitRegisterBankProposal {
    description_hash: [u8; 32],
    voting_blocks: u64,
    tier: u8,
    name: Vec<u8>,
    operator: Address,
    fiat_mint_signer: Option<Address>,
},
```

- [ ] **Step 5: Add opcode-map arm:** `Self::SubmitRegisterBankProposal { .. } => SYS_SUBMIT_REGISTER_BANK_PROPOSAL,`

- [ ] **Step 6: Add encode arm** (mirror SubmitRegistryProposal + the opt-addr pattern from `BankSetDefaultCard`):

```rust
SystemInstruction::SubmitRegisterBankProposal {
    description_hash, voting_blocks, tier, name, operator, fiat_mint_signer,
} => {
    SYS_SUBMIT_REGISTER_BANK_PROPOSAL.write(writer);
    description_hash.write(writer);
    voting_blocks.write(writer);
    tier.write(writer);
    name.write(writer);
    operator.write(writer);
    match fiat_mint_signer {
        None => 0u8.write(writer),
        Some(a) => { 1u8.write(writer); a.write(writer); }
    }
}
```

- [ ] **Step 7: Add decode arm** (name capped 0..=32 per §3.4; canonical opt-addr):

```rust
216 => Self::System(Box::new(SystemInstruction::SubmitRegisterBankProposal {
    description_hash: <[u8; 32]>::read(reader)?,
    voting_blocks: u64::read(reader)?,
    tier: u8::read(reader)?,
    name: Vec::<u8>::read_cfg(reader, &(RangeCfg::from(0..=32), ()))?,
    operator: Address::read(reader)?,
    fiat_mint_signer: match u8::read(reader)? {
        0 => None,
        1 => Some(Address::read(reader)?),
        _ => return Err(Error::InvalidEnum(216)),
    },
})),
```

- [ ] **Step 8: Thread through any opcode-uniqueness / proptest test sites** (baseline noted `SubmitRegistryProposal` at :5621, container-settlement proptests at :2990/:4735/:5670/:6716). Add a `SubmitRegisterBankProposal` case to the same lists if they enumerate every variant.

- [ ] **Step 9: Run, verify PASS + compile.** `cargo test -p cowboy-protocol-codec --features signing,serde submit_register_bank` (PASS); `cargo build -p cowboy-protocol-codec` (the `#[deny]` unreachable-pattern guard confirms opcode 216 is unique).

- [ ] **Step 10: Commit + open cowboy-protocol PR.** After merge, re-pin node (Task 2).

### Task 2: Re-pin node to the merged codec rev

**Files:** the 8 workspace pins (see M5-core convergence: `types/Cargo.toml` + `cli` + `execution` + `ras` + `ras-write-relayer` + `rpc` + root `Cargo.toml` + `Cargo.lock`). If M5-gov-A is developed against a local checkout before the codec PR merges, use the same local `[patch]` dev aid as M5-core (DO NOT commit it) and re-pin to the merged rev before the node PR.

- [ ] **Step 1:** Bump the cowboy-protocol rev to the merged main SHA across all pins (keep cbfs on the converged rev; run `check-cowboy-protocol-revisions.py` → single rev).
- [ ] **Step 2:** `cargo build -p cowboy-types -p cowboy-runner -p cowboy-execution` → `SystemInstruction::SubmitRegisterBankProposal` resolves.

### Task 3: `ProposalPayloadKind::RegisterBank` + `Proposal` payload fields

**Files:** `runner/src/types.rs` (enum ~:974; struct payload fields ~:1098) + `execution/src/execution/system_instruction.rs` (`new_governance_proposal` literal ~:6356 — MUST add initializers or the crate won't compile).

- [ ] **Step 1: Add the enum variant** (append before the enum's closing brace, after `RollbackSystemActor`):

```rust
/// CIP-28 §3.4 (M5-gov): on pass, enact `RegisterBank` — write a new BankEntry at
/// the next bank_id under BankActor 0x16 (NOT 0x09).
RegisterBank,
```

`Default` stays `UpdateBasefeeConfig` (unchanged).

- [ ] **Step 2: Add the payload fields** on the `Proposal` struct (near the other `payload_*`):

```rust
/// CIP-28 §3.4 (M5-gov): RegisterBank payload — bank name (1..=32 ASCII),
/// operator (!= ZERO), and optional fiat-mint signer.
#[serde(default)]
pub payload_bank_name: Vec<u8>,
#[serde(default)]
pub payload_bank_operator: Option<[u8; 20]>,
#[serde(default)]
pub payload_bank_fiat_mint_signer: Option<[u8; 20]>,
```

(Use `[u8; 20]` for the address in the serde record — matches how other addr-ish payloads serialize; convert to `cowboy_types::Address` in the enact fn.)

- [ ] **Step 3: Add default initializers** in `new_governance_proposal`'s struct literal (`system_instruction.rs:6356`), else compile fails:

```rust
payload_bank_name: Vec::new(),
payload_bank_operator: None,
payload_bank_fiat_mint_signer: None,
```

- [ ] **Step 4: Verify compile.** `cargo build -p cowboy-runner -p cowboy-execution` → clean.
- [ ] **Step 5: Commit.**

### Task 4: `SubmitRegisterBankProposal` submit handler (with GD2 tier guard + §3.4 validation)

**Files:** `execution/src/execution/system_instruction.rs` — add the arm (copy `SubmitRegistryProposal` at :2077).

- [ ] **Step 1: Write the failing test** (submit-side validation; a small unit test that drives the handler via `execute_system_instruction` or a focused harness — mirror how existing `Submit*Proposal` handlers are tested):

```rust
// Tier != Registry rejected (GD2); name len 0 or >32 rejected; non-ASCII name rejected;
// operator ZERO rejected; a valid Tier-1 submission debits the deposit, bumps the counter,
// persists a TempCheck proposal with payload_kind=RegisterBank + the payload fields, and
// emits governance.proposal.submitted.
```

- [ ] **Step 2: Run, verify fail** (no such arm / variant unhandled → non-exhaustive match error surfaces the site).

- [ ] **Step 3: Implement the arm** (copy SubmitRegistryProposal; add the GD2 guard + §3.4 name/operator validation):

```rust
cowboy_types::SystemInstruction::SubmitRegisterBankProposal {
    description_hash, voting_blocks, tier, name, operator, fiat_mint_signer,
} => {
    use cowboy_runner::{Proposal, ProposalPayloadKind, ProposalTier};
    use cowboy_types::{GOVERNANCE_SYSTEM_ACTOR, MAX_VOTING_BLOCKS, MIN_VOTING_BLOCKS};

    gas_meters.cycles.consume(self.gas_costs.base_cycles)?;
    gas_meters.cells.consume(self.gas_costs.base_cells)?;

    let tier = ProposalTier::from_u8(*tier).ok_or(ExecutionError::InvalidData)?;
    // GD2 (audit): RegisterBank is a Tier-1 registry write — reject any other tier.
    if tier != ProposalTier::Registry {
        return Err(ExecutionError::InvalidData);
    }
    let tier_params = tier.params();
    // CIP-28 §3.4: name 1..=32 printable ASCII; operator not in reserved band (GD6).
    // `is_ascii_graphic() || b' '` forbids control/NUL bytes (audit spec-F3) that a bare
    // `is_ascii()` would admit into consensus state + the BankRegistered event.
    if *voting_blocks < MIN_VOTING_BLOCKS
        || *voting_blocks > MAX_VOTING_BLOCKS
        || *voting_blocks < tier_params.min_voting_blocks
        || name.is_empty()
        || name.len() > 32
        || !name.iter().all(|b| b.is_ascii_graphic() || *b == b' ')
        || *operator < cowboy_types::constants::RESERVED_SYSTEM_ADDRESS_LIMIT
    {
        return Err(ExecutionError::InvalidData);
    }
    let deposit_u64 =
        u64::try_from(tier_params.deposit).map_err(|_| ExecutionError::InvalidData)?;
    if sender_account.balance < deposit_u64 {
        return Err(ExecutionError::InsufficientBalance);
    }
    sender_account.balance -= deposit_u64;

    ensure_gov_actor_exists(store).await?;
    let next_id = read_and_bump_proposal_counter(store).await?;

    let mut proposal = new_governance_proposal(
        next_id, tx.from.as_ref(), description_hash, block_height,
        *voting_blocks, tier, tier_params, ProposalPayloadKind::RegisterBank,
    );
    proposal.payload_bank_name = name.clone();
    proposal.payload_bank_operator = Some(operator.to_fixed_bytes()); // [u8;20]
    proposal.payload_bank_fiat_mint_signer = fiat_mint_signer.map(|a| a.to_fixed_bytes());
    if crate::execution::gov_snapshot::promote_and_snapshot(store, &mut proposal, block_height).await? {
        sender_account.balance = sender_account.balance.saturating_add(deposit_u64);
        proposal.deposit_settled = true;
    }
    store
        .set_actor_storage(&GOVERNANCE_SYSTEM_ACTOR, Proposal::key_for(next_id), proposal.to_storage_bytes())
        .await
        .map_err(ExecutionError::from_store)?;
    self.system_events.push((
        "governance.proposal.submitted".to_string(),
        format!("{{\"id\":{},\"payload\":\"RegisterBank\"}}", next_id).into_bytes(),
    ));
    Ok(None)
}
```

(Use the actual `Address` → `[u8;20]` accessor the codebase uses — `to_fixed_bytes()` / `.0` / `as_ref().try_into()`; match the surrounding code.)

- [ ] **Step 4: Run, verify PASS.**
- [ ] **Step 5: Commit.**

### Task 5: `apply_register_bank` + `ExecuteProposal` dispatch arm + `BankRegistered` (GD1/GD3)

**Files:** new `execution/src/execution/bank_registry.rs` (or in `bank/mod.rs`) for `apply_register_bank` + the event; `system_instruction.rs` (`ExecuteProposal` match ~:4164) for the dispatch arm.

- [ ] **Step 1: Write the failing test** (enact-side, unit): given a `Proposal { payload_kind: RegisterBank, payload_bank_name, payload_bank_operator, .. }` and a store with `bank_seq = 2` + bank 1 present, `apply_register_bank` writes bank 2 (`operator`, `status: Active`, `registered_at`), bumps `bank_seq` to 3, refuses to overwrite an existing slot (GD3), and re-validates name/operator (never trust the stored payload blindly).

```rust
#[tokio::test]
async fn apply_register_bank_creates_next_bank_and_guards_overwrite() {
    // store: write bank 1 + bank_seq = 2
    // apply_register_bank(name="Second", operator=OP2) -> bank 2 = {OP2, Active, h}, bank_seq = 3
    // a second apply with bank_seq rewound to 1 (overwrite genesis) -> Err (GD3)
    // name empty / non-ASCII / operator ZERO in payload -> Err (re-validation)
}
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement `apply_register_bank`** (GD1: plain fn + advisory `&origin` witness; GD3 overwrite guard):

```rust
pub const TOPIC_BANK_REGISTERED: &str = "BankRegistered";

/// `BankRegistered { bank_id, name, operator }`: `bank_id(4 BE) ‖ name_len(2 BE) ‖ name ‖ operator(20)`.
fn encode_bank_registered(bank_id: u32, name: &[u8], operator: &Address) -> Vec<u8> {
    let mut v = Vec::with_capacity(6 + name.len() + 20);
    v.extend_from_slice(&bank_id.to_be_bytes());
    v.extend_from_slice(&(name.len() as u16).to_be_bytes());
    v.extend_from_slice(name);
    v.extend_from_slice(operator.as_ref());
    v
}

/// CIP-28 §3.4 (M5-gov): enact a passed RegisterBank proposal — allocate the next bank_id,
/// write the BankEntry (Active), bump bank_seq, emit BankRegistered. Re-validates the payload
/// (never trust stored bytes). GD3: refuses to overwrite an existing bank slot. `_origin` is an
/// unforgeable capability witness (GD1 advisory) — the write targets 0x16 via the bank helpers,
/// not 0x09, so it is not consumed.
pub(in crate::execution) async fn apply_register_bank<S: StateStore>(
    store: &mut S,
    _origin: &crate::execution::gov_origin::SystemOrigin,
    name: &[u8],
    operator: &Address,
    fiat_mint_signer: Option<Address>,
    block_height: u64,
    events: &mut Vec<(String, Vec<u8>)>,
) -> Result<(), ExecutionError> {
    // Re-validate (defense-in-depth; submit already checked). Mirror the submit guards
    // exactly (GD6 reserved-band + printable-ASCII name) so enact never accepts what
    // submit rejects, and never trusts stored payload bytes blindly.
    if name.is_empty()
        || name.len() > 32
        || !name.iter().all(|b| b.is_ascii_graphic() || *b == b' ')
        || *operator < cowboy_types::constants::RESERVED_SYSTEM_ADDRESS_LIMIT
    {
        return Err(ExecutionError::InvalidData);
    }
    let id = crate::bank::storage::read_bank_seq(store).await?;
    // GD3: never overwrite an existing bank (guards a rewound bank_seq clobbering genesis).
    if crate::bank::storage::read_bank(store, id).await?.is_some() {
        return Err(ExecutionError::InvalidData);
    }
    let next = id.checked_add(1).ok_or(ExecutionError::InvalidData)?; // u32 overflow guard
    let bank = crate::bank::BankEntry {
        bank_id: id,
        name: name.to_vec(),
        operator: *operator,
        fiat_mint_signer,
        status: crate::bank::BankStatus::Active,
        registered_at: block_height,
    };
    crate::bank::storage::write_bank(store, &bank).await?;
    crate::bank::storage::write_bank_seq(store, next).await?;
    events.push((TOPIC_BANK_REGISTERED.to_string(), encode_bank_registered(id, name, operator)));
    Ok(())
}
```

- [ ] **Step 4: Add the `ExecuteProposal` dispatch arm** (`system_instruction.rs`, in the `match proposal.payload_kind` ~:4164, mirror `UpdateContainerSettlementConfig` at :4407):

```rust
ProposalPayloadKind::RegisterBank => {
    // Defense-in-depth (audit auth-H1 residual): re-assert the tier at enact so a
    // future second creation path at a lower tier could not slip a bank through.
    if proposal.tier != cowboy_runner::ProposalTier::Registry {
        return Err(ExecutionError::InvalidData);
    }
    let operator = proposal.payload_bank_operator
        .map(cowboy_types::Address::from)
        .ok_or(ExecutionError::InvalidData)?;
    let signer = proposal.payload_bank_fiat_mint_signer.map(cowboy_types::Address::from);
    crate::execution::bank_registry::apply_register_bank(
        store, &origin, &proposal.payload_bank_name, &operator, signer,
        block_height, &mut self.system_events,
    ).await?;
    "RegisterBank"
}
```

(Use the actual `[u8;20]` → `Address` conversion the codebase uses.)

- [ ] **Step 5: Run, verify PASS.**
- [ ] **Step 6: Commit.**

### Task 6: `BankRegistered` topic registration + `cbss_pause_gate` payload classifier

**Files:** `execution/src/consensus_event_topics.rs` (`KNOWN_CONSENSUS_EVENT_TOPICS`); `execution/src/execution/cbss_pause_gate.rs` (`proposal_payload_targets_cbss`). **GD4 is RESOLVED to option (a) — DO NOT touch `storage/src/speculative.rs`** (the emitter stays unchanged; `BankRegistered` attributes to `tx.from`, the executor — see GD4).

- [ ] **Step 1:** Register `"BankRegistered"` in `KNOWN_CONSENSUS_EVENT_TOPICS` (alphabetical, near the Bank* topics). The build-time source-scan test (`consensus_event_topics_are_registered`, its `const TOPIC_*: &str` branch) enforces it — omitting it fails CI. NOTE: the scan's `events.push(("literal"...)` branch does NOT catch a pushed VARIABLE, but the `const TOPIC_BANK_REGISTERED: &str = "BankRegistered"` declaration IS caught by the const branch, so the const form is required (as written in Task 5).
- [ ] **Step 2 (audit consensus, cbss_pause_gate):** the SECOND exhaustive `match` on `ProposalPayloadKind` — `proposal_payload_targets_cbss()` (`cbss_pause_gate.rs:252`, all 24 variants, no `_` wildcard) — is made non-exhaustive by the new variant. Add `ProposalPayloadKind::RegisterBank => false` (RegisterBank targets 0x16, NOT CBSS 0x04). `cargo build --workspace` (Task 8) compile-forces this, but it is called out here so it is not forgotten. (A wrong `=> true` would gate RegisterBank behind the CBSS pause — deterministic, not a fork, but a behavior bug.)
- [ ] **Step 3:** Run the `consensus_event_topics` registration test + a `cargo build` of execution → PASS.
- [ ] **Step 4: Commit.**

### Task 7: End-to-end governance integration test — REAL Tier-1 endorsement path (audit conservation-F1)

**Files:** `execution/src/execution/tests.rs`.

**⚠ CRITICAL (audit conservation-F1, false-green trap):** Do NOT "mirror the settlement/registry e2e" — those submit at **Tier 0** (`temp_check_threshold: 0` → auto-promotes to Active at submit) and reach "Passed" via `force_snapshots` (which injects `voting_snapshot_total`/`for_votes` WITHOUT casting votes or promoting from TempCheck). RegisterBank is forced to **Tier 1** (GD2), whose `temp_check_threshold: 2` means `promote_and_snapshot` returns FALSE at submit → the proposal sits in **TempCheck**. `EndorseProposal` appears **0 times** in the existing test suite, so there is NO template for the endorsement gate. A naive tier-1 mirror (force_snapshots + ExecuteProposal) leaves the proposal in TempCheck → ExecuteProposal hits the temp-check-expiry branch → **burns the deposit + Cancels** → `apply_register_bank` never runs → the "bank 2 exists" assertion fails RED. **Do NOT "fix" that by hand-constructing `Proposal { state: Passed, .. }` and writing it to storage** — that bypasses GD2, the deposit lifecycle, the 2-endorsement promotion, `resolve_at`, and `for_passed_proposal` = sim≠prod (certifies nothing about the real governance path).

- [ ] **Step 1: Write the REAL end-to-end test** driving the actual Tier-1 path:
  1. `SubmitRegisterBankProposal { tier: 1, name, operator, .. }` — asserts the 5000 CBY deposit is debited and the proposal is stored in `TempCheck`.
  2. Seed 2 distinct runners/endorsers; `EndorseProposal` ×2 — the 2nd endorsement promotes TempCheck→Active AND refunds the deposit (`deposit_settled=true`). Assert both.
  3. Reach a passing tally — `force_snapshots` (injecting the voting weight) OR real `CastVote`, matching how the existing e2e reaches quorum, but ONLY after the proposal is Active.
  4. `ExecuteProposal` at a post-`voting_deadline` block.
  5. Assert: bank 2 exists at `bank_id = 2` (`operator`, `fiat_mint_signer`, `status: Active`, `registered_at`), `bank_seq == 3`, and a `BankRegistered` event is in the block receipt attributed to `tx.from` (per GD4, NOT 0x16).
- [ ] **Step 2: Add the negative cases** — a Tier-0 `SubmitRegisterBankProposal` is rejected at submit (GD2); a `name` with a control byte / len 0 / len 33 rejected; an `operator` in `[0x00,0x100)` rejected (GD6); and (enact-side unit, Task 5 already) a rewound `bank_seq` that would target bank 1 is refused (GD3).
- [ ] **Step 3: Run, verify PASS.** `cargo test -p cowboy-execution register_bank -- --nocapture`.
- [ ] **Step 4: Commit.**

### Task 7b: RegisterBank conservation invariant (audit conservation-F5)

**Files:** `execution/src/econ_invariants.rs`.

**Rationale:** `RegisterBank` is the FOURTH field-only bank mutator (after `SetBankOperator`/`SetBankFiatMintSigner`/`TransferOwnership`) that MUST move no value. M5-core added `econ_bank_rotation_conserves_all_balances` (a pinned-pool, mutation-verified proptest) precisely to seal the #564/#589 "fields-only-assertion" escape class. The Task-5 unit test asserts only bank fields + the GD3 guard — a bug crediting the incoming bank operator at registration would go UNCAUGHT.

- [ ] **Step 1: Add a pinned-pool conservation proptest** (extend `econ_bank_rotation_conserves_all_balances` OR a sibling `econ_bank_register_conserves_all_balances`) that drives the REAL `apply_register_bank` over a FIXED pool including the incoming `operator`, `fiat_mint_signer`, and `0x16`, seeds proptest-random balances, and asserts Σ native CBY AND CUSD `total_supply` are UNCHANGED across the registration (only `bank:id` + `bank_seq` change).
- [ ] **Step 2: Mutation-verify** — inject a stray `credit(operator, 1)` into `apply_register_bank` via scoped sed (commit first per `feedback_commit_before_mutation_test`); confirm the proptest goes RED because `operator` is pinned; revert via scoped sed.
- [ ] **Step 3: Run, verify PASS + RED confirmed. Commit.**

### Task 8: fmt + full build + finalize

- [ ] **Step 1:** `cargo fmt --all` (Format CI).
- [ ] **Step 2:** `cargo build --workspace --all-targets` → clean (a new `ProposalPayloadKind` variant makes every `match proposal.payload_kind` non-exhaustive — the compiler surfaces each site to handle; verify none is missed. Re-run once if a linker flake appears — COW-1068).
- [ ] **Step 3:** `cargo test -p cowboy-execution -p cowboy-runner -p cowboy-storage` → green.
- [ ] **Step 4:** Deep-audit the DIFF (marshal deep-review-flow) — verify the governance path (submit auth via deposit+tier, enact via passed-proposal reachability), GD2/GD3 guards, GD4 attribution, and the ExecuteProposal match exhaustiveness.
- [ ] **Step 5: Commit + open node PR** base=devnet. **Flag-day note (audit consensus Hyp7):** two independent triggers require the same coordinated all-validator upgrade — (1) the codec opcode 216 decode-fork (a legacy node can't decode a `SubmitRegisterBankProposal` tx), AND (2) the new `#[serde(default)] payload_bank_*` fields on `Proposal`, which change the serialized bytes of EVERY proposal written to 0x09 storage (a state-root divergence on any block writing any proposal, not just opcode-216 blocks). The `#[serde(default)]` choice is correct + consistent with all ~40 existing `payload_*` fields (do NOT use `skip_serializing_if`). Both are contained by the coordinated upgrade. Do NOT self-merge.

---

## Self-Review (writing-plans checklist)

- **Spec coverage:** §3.4 RegisterBank (governance-submitted, Tier-1, name 1..=32 ASCII, operator≠ZERO, bump bank_seq, write bank:id, emit BankRegistered{bank_id,name,operator}) → Tasks 1/3/4/5/6. §6.1 multi-bank genesis (bank 1 + bank_seq=2) → untouched (GD3 relies on it).
- **Placeholder scan:** the `Address` ↔ `[u8;20]` accessor names are marked "match the surrounding code" (the exact method — `to_fixed_bytes`/`from`/`.0` — is verified at implementation time); the submit-handler test body is described (the exact harness mirrors existing `Submit*Proposal` tests). These are the only non-literal spots; each names its template.
- **Type consistency:** `bank_id: u32`, `name: Vec<u8>` (cap 32), `operator: Address`/`Option<[u8;20]>` in the serde record, `ProposalTier::Registry`, `ProposalPayloadKind::RegisterBank` — consistent across codec/runner/execution.

## Deep-audit resolution log (4-lens, 2026-07-26 — folded above)

| Finding | Lens | Sev | Resolution |
|---|---|---|---|
| GD4 `BankRegistered` emitter attribution | consensus | HIGH | Locked to **option (a)** — `tx.from`/executor, emitter UNCHANGED; (b)/(c)=0x16 rejected (impossible in per-instruction model / governance-wide flag-day) |
| Task 7 e2e false-green trap (Tier-1 endorsement path has no template) | conservation | HIGH | Task 7 rewritten to the REAL submit→EndorseProposal×2→Active→pass→ExecuteProposal path; explicit anti-shortcut warning |
| operator reserved-band parity | auth-H6 / spec-F2 | MED | GD6 added; reserved-band `[0x00,0x100)` guard in submit + enact |
| Missing conservation proptest (4th field-only mutator) | conservation | MED | Task 7b: pinned-pool proptest driving apply_register_bank, mutation-verified |
| `cbss_pause_gate.rs:252` 2nd exhaustive match omitted | consensus | MED | Task 6 Step 2 + File Structure: `RegisterBank => false` |
| GD2 vs §3.4 Tier-3 | spec-F1 | LOW | GD2 reconciliation note (Tier-3=bundled bytecode, not expressible via opcode 216 single-payload) |
| name `is_ascii()` admits control/NUL | spec-F3 / auth | LOW | printable-ASCII (`is_ascii_graphic() \|\| b' '`) in submit + enact |
| tier not re-asserted at enact | auth-H1 residual | LOW | dispatch arm asserts `proposal.tier == Registry` |
| u32 `bank_seq` overflow | auth / consensus | LOW/INFO | `checked_add` in apply_register_bank |
| serde field addition = broader state-root flag-day | consensus Hyp7 | INFO | Task 8 Step 5 rationale expanded (2 triggers) |
| GD1 reachability / GD2 tier binding / GD3 overwrite / deposit conservation / apply moves no balance / genesis seeds bank_seq=2 / match exhaustiveness | all lenses | — | REFUTED / CONFIRMED-safe (evidence in audit) |
| enact partial-write on Err (atomic-rollback claim) | auth informational | INFO | pre-existing, affects all payloads; confirm during impl (Task 8 Step 4) |

## Original open items (now resolved above — kept for traceability)

1. **GD4 — `BankRegistered` emitter attribution** (consensus): resolve executor/governance-context vs 0x16 BEFORE freezing the event bytes. This is the highest-value open question (a wrong choice is a flag-day).
2. **ExecuteProposal match exhaustiveness** (consensus): the new `ProposalPayloadKind::RegisterBank` must be handled in the `match proposal.payload_kind` AND anywhere else that matches the enum exhaustively (runner serde, any tier/label mapping) — the compiler enforces, but verify no `_ =>` arm silently swallows it into a wrong enactment.
3. **GD2 tier binding** (auth): confirm the `tier != Registry` reject is the ONLY tier a RegisterBank can pass at, and that no other Submit* path can construct a RegisterBank payload at a lower tier.
4. **GD3 overwrite guard** (auth/econ): prove `read_bank(id).is_some()` refusal actually prevents genesis-bank seizure under a rewound/mis-seeded `bank_seq`; confirm `bank_seq` is genesis-seeded to 2.
5. **Deposit conservation** (econ): the tier deposit is debited at submit and refunded on reaching voting / burned on temp-check failure — confirm adding RegisterBank rides the existing `deposit`/`deposit_settled` lifecycle unchanged (no new mint/burn), and that `apply_register_bank` moves NO balance.
6. **Re-validation at enact** (correctness): `apply_register_bank` re-checks name/operator — confirm this can't diverge from the submit-side check in a way that lets a passed proposal enact something the submit rejected (or fail to enact something valid).
7. **Sim≠prod test authenticity** (`feedback_all_plans_deep_review`): the e2e test (Task 7) must drive the REAL submit→vote→pass→ExecuteProposal path, not a hand-constructed `Proposal` shortcut for the pass step.
