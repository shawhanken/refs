# CIP-28 BankActor — M1 Skeleton (CIP-36 W3, stage 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `BankActor` system actor at `0x16` with the M1 card primitive — genesis-seeded "Cowboy Banking" (`bank_id = 1`), deterministic card-address derivation, and the `IssueCard` / `Deposit` / `Withdraw` / `CloseCard` instructions with owner/agent indices — so "every agent has its own on-chain bank card" is demoable. No gas-charging, no policy enforcement, no fiat bridge (those are M2/M3/M4).

**Architecture:** BankActor mirrors the existing PaymentGate (`0x12`) system actor exactly: a reserved-band native address (recognized by address, not deployed bytecode), its own `SYS_BANK_*` `SystemInstruction` family in the codec, a `node/execution/src/bank/` handler+storage module keyed under the bank's actor-storage namespace, and dispatch through the big `execute_system_instruction` match. A card is a derived 20-byte address that is itself a normal token holder — balances live in the existing CBY/CIP-20 ledger; BankActor stores only card metadata.

**Tech Stack:** Rust. Two git repos: `cowboy-protocol` (wire codec; **branch off node's actual pin `876d5e83`** — W1/`TokenBurnFrom` has already landed on devnet and node references it, so branch off the pinned rev that HAS opcode 24; the earlier `b373b9a9` idea is void) and `node` (base `devnet`). commonware-codec positional wire format; QMDB-backed actor storage; **hand-rolled fixed-layout byte codec for stored structs** (mirror `payment_gate/mod.rs`, NOT serde — audit R3), pinned by golden-vector KATs.

---

## Decisions taken (marked for review; defaults chosen per CIP-36 §13.1 + PaymentGate precedent)

1. **Activation mechanism = reserved-band constant** (NOT `call_actor` interception). Add `BANK_ACTOR = 0x16` to the system-actor registry + `BANK_ACTOR_SYSTEM_ACTOR` const; the reserved band (`< 0x100`) already makes it native + rent-exempt. This matches PaymentGate/TradingPost. (CIP-36 §13.1 left the mechanism open; this is the simpler, precedented choice.)
2. **Instruction family = `SystemInstruction` variants `SYS_BANK_*` starting at opcode 200** (workload ends at 199; 200+ confirmed free). This avoids the token block (24 = `TokenBurnFrom` is already upstream; 25 may be taken by the other session's W1/W2). Structured payloads (`CardPolicy`) ride as bounded `Vec<u8>` per the codec's PaymentGate convention, keeping type evolution off the wire.
3. **M1 scope.** `SetDefaultCard`/`charge_gas` = M2; policy triad (`SetPolicy`/`Freeze`/windows) = M3; `MintFromFiatVoucher` = M4; multi-bank/`TransferOwnership` = M5. M1 **stores** `CardPolicy`/`SpendWindow` (no enforcement) **but still performs the §3.1 write-time validations** (`gas_payment_token ∈ {Native} ∪ genesis stablecoin whitelist`; `allowed_receivers.len() ≤ 64`; `allowed_syscall_kinds.len() ≤ 16`) — those are issuance invariants, not charge-time enforcement. **`issuance_principal: [u8;32]` is reserved in `CardEntry` now** (CIP-36 §7 stamps it at IssueCard; M1 writes zeros, M4 populates) to avoid a live stored-schema migration.
4. **Genesis seed** one bank: `bank_id = 1` "Cowboy Banking", `fiat_mint_signer = None` (M4). Operator comes from a **new explicit `GenesisConfig.bank_operator: Address` field** — NOT "reuse council" (`Council` is a `SignerSet`, not an `Address`). Genesis also seeds a **stablecoin whitelist** (the CUSD token id, or empty on plain devnet) that IssueCard validates against.
5. **Deployment = fresh re-genesis (decided 2026-07-19); NO activation gate in M1.** Every node runs the new binary from block 0, so `bank:1` + opcodes 200–203 exist from genesis and there is no legacy peer to fork against. The former `bank_activation_height` design is **removed** — an execution-layer gate cannot stop a new-opcode decode fork anyway, and it is redundant on fresh genesis. The activation-height/flag-day machinery is **deferred to M2**, where the fee-settle charge-fork touches a running chain and needs a genesis-derived, `verify()`-checked, 0x09-sourced gate (PR#932/#934 pattern).

---

## Deep-audit revisions applied (2026-07-19 — BINDING; supersede any conflicting task text below)

Full detail: `refs/analysis/2026-07-19_cip36-w3-bankactor-m1-plan-audit.md`. Where a task step below still reflects the pre-audit design, these win:

- **R1 (A1, BLOCKER) — bounded sweep.** `CloseCard`/`Withdraw` must NOT "sweep all token balances" (there is no per-holder token enumeration; the only enumeration is the global, unbounded `mints_index` — a griefing DoS under M1's no-gas). Sweep only **native CBY + the genesis stablecoin whitelist**; recover any other reserve token via CIP-28 §5.3 post-Close **residual `Withdraw`** (Closed cards stay `Withdraw`-able). O(1), spec-consistent.
- **R2 (A4/A7) — fresh re-genesis, no gate; sequencing.** Delete the `bank_activation_height` gate (Decision 5). Branch the codec off node's current pin **`b373b9a9`** (bank-only — avoids silently pulling in `TokenBurnFrom` opcode 24) **or** land W3 after the W1 node branch merges to devnet and budget node's opcode-24 arms.
- **R3 (A2/A3/A11/L2) — pin ONE stored encoding.** Fix `Address::from_bytes(h[12..32].try_into().unwrap())` (there is no `from_slice`). Encode stored structs as **hand-rolled fixed-layout bytes** mirroring `payment_gate/mod.rs` (NOT serde), **store `CardPolicy` raw** (one encoding only), add a **pinned-hex golden-vector KAT** for `CardEntry`/`BankEntry`/`CardPolicy`. Encode `allowed_syscall_kinds` faithfully (tag+u16 for `Custom`), not `Vec<u16>`.
- **R4 (A5/A6) — two missing consensus touch-sites (neither compiler-caught):**
  - Add `SystemInstruction::BankIssueCard | BankDeposit | BankWithdraw | BankCloseCard => Some(BANK_ACTOR_SYSTEM_ACTOR)` to `system_event_emitter` (`node/storage/src/speculative.rs:390`) + an attribution golden test — else card events are committed to `logs_root` as `tx.from` (COW-2435 provenance break).
  - Add `assert_bank_not_paused_for_instruction(...)` at the **top** of the Bank dispatch arm (mirror `cbss_pause_gate`, `system_instruction.rs:52-58`), **before any balance move** — else pause is illusory for the money path and `CloseCard` is pay-then-fail under pause.
- **R5 (A8/A9/A12/L1) — spec-faithful IssueCard + genesis** (folded into Decisions 3–4 above; also document the CUSD escrow-hook: `Withdraw`/`CloseCard` succeed only when `to`/`refund_to == owner` for CUSD).
- **R6 (A10/L3/L5/L6/L7) — smaller fixes.** `initial_policy` bound → `0..=8192` (wire cap == stored cap). Validate `Withdraw.to`/`CloseCard.refund_to` via `validate_balance_recipient`. Unify currency repr on `PayCurrency`. Add `entries[]` + alias group to `system_actor_addrs_unique_across_namespaces`. Budget doc amendments (CIP-28 body `0x13→0x16`, WP §9.1 row, CIP-13 §1 master table 200–203). Relabel unreachable frozen tests as forward-compat storage-backdoor tests.

## Repos, branches, ordering (cross-repo, like W1)

- **`cowboy-protocol`** (codec) — base `main`. Adds the `SYS_BANK_*` opcode block + `Bank*` variants + encode/size/decode + uniqueness rows. PR merges first.
- **`node`** — base `devnet`. Adds address/const, `bank/` module, dispatch, genesis seed, pause entry, event topics, and the codec rev-pin bump. During dev, use a local `[patch]` pointing `cowboy-protocol-codec` at the on-disk sibling (same as W1 Task 1); remove + re-pin to the merged codec SHA at the end.
- **Branch:** `feat/cip28-bankactor-m1` in each repo.
- **Discipline:** `cargo fmt --all` before each commit; never commit `Cargo.lock`; local commits only until a finalize task (push/PR is user-gated).

---

## File Structure

**`cowboy-protocol`:**
- Modify `crates/cowboy-protocol-codec/src/instruction.rs` — `SYS_BANK_*` const block (near :358, after workload 199), `Bank*` variants (near :465), `sub_type()`/encode/`encode_size`/decode arms, uniqueness rows are in node (see below).

**`node`:**
- Modify `runner/src/system_actors.rs` — `BANK_ACTOR = 0x16` in the macro list; bump `ALL.len()` 22→23.
- Modify `types/src/constants.rs` — `BANK_ACTOR_SYSTEM_ACTOR` const; `BANK_ACTIVATION_HEIGHT` handling (or genesis field).
- Modify `types/src/pause.rs` — add `0x16` to `PAUSABLE_LOW_BYTES`.
- Modify `types/src/execution.rs` — append `SYS_BANK_*` rows to `sys_opcode_uniqueness`.
- Modify `types/Cargo.toml` — re-pin codec rev (finalize task).
- Create `execution/src/bank/mod.rs` — `CardEntry`, `BankEntry`, `CardPolicy`, `SpendWindow`, `PayCurrency`, `CardStatus`, serde, card derivation, errors.
- Create `execution/src/bank/storage.rs` — key schema + typed R/W under `BANK_ACTOR_SYSTEM_ACTOR`.
- Create `execution/src/bank/handlers.rs` — `issue_card`, `deposit`, `withdraw`, `close_card`.
- Modify `execution/src/lib.rs` — `pub mod bank;`.
- Modify `execution/src/execution/system_instruction.rs` — `Bank*` outer-guard dispatch arm + inner match.
- Modify `chain/src/genesis.rs` — seed BankActor actor entry + `bank_id=1` storage triple; update the COW-1277 placeholder guard test if it enumerates seeded addresses.
- Modify `execution/src/consensus_event_topics.rs` — register `Card*`/`Bank*` topics.

---

## Data model (`execution/src/bank/mod.rs`) — from CIP-28 §2

```rust
use cowboy_types::Address;

pub const CARD_DERIVATION_DOMAIN: &[u8] = b"CowboyBankCard\x01";
pub const GENESIS_BANK_ID: u32 = 1;

#[derive(Debug, Clone, PartialEq)]
pub enum PayCurrency { Native, Token(Address) }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CardStatus { Active, Frozen, Closed, Expired }

#[derive(Debug, Clone, PartialEq)]
pub struct CardPolicy {
    pub per_hour_cap: Option<u128>,
    pub per_day_cap: Option<u128>,
    pub per_month_cap: Option<u128>,
    pub allowed_receivers: Vec<Address>,     // <= 64; empty = any
    pub allowed_syscall_kinds: Vec<u16>,     // <= 16 opcodes; empty = any (M1 stores, M3 enforces)
    pub locked_after_transfer: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SpendWindow {
    pub hour_period_id: u64,  pub hour_spent: u128,
    pub day_period_id: u64,   pub day_spent: u128,
    pub month_period_id: u64, pub month_spent: u128,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BankEntry {
    pub bank_id: u32,
    pub name: Vec<u8>,                 // 1..=32 ASCII
    pub operator: Address,
    pub fiat_mint_signer: Option<Address>,
    pub status: BankStatus,            // Active | Paused
    pub registered_at: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BankStatus { Active, Paused }

#[derive(Debug, Clone, PartialEq)]
pub struct CardEntry {
    pub card_address: Address,
    pub bank_id: u32,
    pub owner: Address,
    pub agent: Address,
    pub issue_nonce: u64,
    pub issuance_principal: [u8; 32],  // CIP-36 §7 sybil hinge; M1 writes zeros, M4 populates (reserved now to avoid a live schema migration)
    pub created_at: u64,
    pub last_renewed_at: u64,
    pub expires_at: Option<u64>,
    pub status: CardStatus,
    pub gas_payment_token: PayCurrency,
    pub policy: CardPolicy,
    pub window: SpendWindow,
}

/// CIP-28 §2.6: keccak256(DOMAIN || bank_id_be4 || owner || agent || nonce_be8)[12..32].
pub fn derive_card_address(bank_id: u32, owner: &Address, agent: &Address, issue_nonce: u64) -> Address {
    let mut buf = Vec::with_capacity(14 + 20 + 20 + 8);
    buf.extend_from_slice(CARD_DERIVATION_DOMAIN);
    buf.extend_from_slice(&bank_id.to_be_bytes());
    buf.extend_from_slice(owner.as_ref());
    buf.extend_from_slice(agent.as_ref());
    buf.extend_from_slice(&issue_nonce.to_be_bytes());
    let h = /* keccak256 helper used elsewhere in node, e.g. cowboy_types::keccak256 */ keccak256(&buf);
    Address::from_bytes(h[12..32].try_into().unwrap()) // NB: there is NO Address::from_slice
}
```

Use the SAME keccak256 helper `handle_token_create` uses (it computes token_id via `keccak256`). Serde: mirror how `payment_gate/mod.rs` serializes its structs (bounded, deterministic). `CardPolicy` is what rides the wire as a bounded `Vec<u8>` (serialize with the node-side codec, cap ~1 KiB).

## Storage keys (`execution/src/bank/storage.rs`) — mirror `payment_gate/storage.rs`

All R/W via `get_actor_storage(&BANK_ACTOR_SYSTEM_ACTOR, key)` / `set_actor_storage`. ASCII-prefixed keys (CIP-28 §2.1):
- `b"bank:" || bank_id_be4` → `BankEntry`
- `b"bank_seq"` → `u32_be4` (next bank_id; genesis writes `2`)
- `b"card:" || card_addr_20` → `CardEntry`
- `b"card_by_owner:" || owner_20 || bank_id_be4 || idx_be4` → `card_addr_20`
- `b"card_by_agent:" || agent_20 || bank_id_be4 || idx_be4` → `card_addr_20`
- `b"issue_nonce:" || bank_id_be4 || owner_20 || agent_20` → `u64_be8`

## M1 instructions (codec `SYS_BANK_*`, node handlers)

| Opcode | Variant | Fields | Handler behavior (M1) |
|---|---|---|---|
| 200 | `BankIssueCard` | `bank_id: u32, agent: Address, gas_payment_token: PayCurrency, initial_policy: Vec<u8>, expires_at: Option<u64>` | bank Active; caller = `tx.from` becomes owner; bump `issue_nonce`; derive addr; write `CardEntry` (status Active, window zeroed) + owner/agent indices; emit `CardIssued` |
| 201 | `BankDeposit` | `card_address: Address, token: Address, amount: u128` | card Active/Frozen; move `amount` of `token` (0x0=CBY) from caller → card_address via the existing ledger; emit `CardDeposited` |
| 202 | `BankWithdraw` | `card_address: Address, token: Address, amount: u128, to: Address` | caller == owner; status ≠ Frozen; balance sufficient; move token card_address → `to`; emit `CardWithdrawn` |
| 203 | `BankCloseCard` | `card_address: Address, refund_to: Address` | caller == owner; status ≠ Closed; move all token balances out to `refund_to`; status → Closed; remove indices; emit `CardClosed` |

`PayCurrency` on the wire = tag byte (`0` = Native, `1` = Token + 20-byte address), mirroring the codec's other tagged options.

---

## Task 0: Dev setup (branches + local codec patch)

Same as W1 Task 1, with one difference (audit R2/A7): **branch the codec off `b373b9a9`** — node's *current* codec pin in `node/types/Cargo.toml` — NOT `main` HEAD. `main` HEAD (`d00e1b9`) already carries `TokenBurnFrom` (opcode 24); branching off `b373b9a9` keeps this a **bank-only** delta so the later node rev-pin bump doesn't silently introduce opcode-24 exhaustive-match breakage. (If W1's node branch has already merged to devnet by the time you start, you may instead branch off `main` and budget node's `TokenBurnFrom` arms — but bank-only off `b373b9a9` is the low-risk default.)

Steps: `cd cowboy-protocol && git fetch && git checkout -b feat/cip28-bankactor-m1 b373b9a9`; `cd node && git checkout devnet && git pull && git checkout -b feat/cip28-bankactor-m1`; add the `[patch."https://github.com/cowboyinc/cowboy-protocol.git"] cowboy-protocol-codec = { path = "../cowboy-protocol/crates/cowboy-protocol-codec" }` block to `node/Cargo.toml`; `cargo build -p cowboy-types` to confirm resolution; commit the patch (node only). Do NOT push.

## Task 1: Codec — `SYS_BANK_*` block + `Bank*` variants (opcodes 200–203)

**Files:** `cowboy-protocol/crates/cowboy-protocol-codec/src/instruction.rs`.
TDD: add roundtrip tests for all four variants (with a `Some(addr)`/`None` `expires_at`, both `PayCurrency` tags, a non-empty `initial_policy`), confirm they fail to compile, then:
- Const block after workload 199: `SYS_BANK_ISSUE_CARD = 200 … SYS_BANK_CLOSE_CARD = 203` (contiguous, with a header comment referencing CIP-28 / actor 0x16).
- Variants near the PaymentGate block. `PayCurrency` encodes as a tag byte (`0`=Native, `1`=Token+Address); `Option<u64>` (`expires_at`) as the existing manual tag-byte Option pattern (`None=>0u8`, `Some=>{1u8; v.write}`); `initial_policy: Vec<u8>` via `Vec::<u8>::read_cfg(reader, &(RangeCfg::from(0..=8192), ()))` — **8192, not 1024** (audit A10: 64 receivers × 20B = 1280B alone exceeds 1024; wire cap must equal the stored-blob cap in Task 3 Step 6).
- `sub_type()`, `Write`, `encode_size`, `Read` (literal `200..=203` or const — use const names for readability) arms.
Verify: full codec suite green; `--features signing --test golden_vectors` still green (no existing opcode touched). Commit.

## Task 2: Node — address, const, pause, uniqueness

**Files:** `runner/src/system_actors.rs`, `types/src/constants.rs`, `types/src/pause.rs`, `types/src/execution.rs`.
- Add `BANK_ACTOR = 0x16` to the macro list; bump the `ALL.len()` assertion 22→23 (test `registry_is_exhaustive_nonzero_and_in_reserved_band`).
- Add `pub const BANK_ACTOR_SYSTEM_ACTOR: Address = Address::from_low_u64(0x16);` in `constants.rs` (near `INTENT_SETTLEMENT_SYSTEM_ACTOR`).
- Add `0x16,` to `PAUSABLE_LOW_BYTES` in `pause.rs`.
- Append `SYS_BANK_ISSUE_CARD … SYS_BANK_CLOSE_CARD` rows to the `sys_opcode_uniqueness` pinned list in `execution.rs`.
Verify: `cargo test -p cowboy-types -p cowboy-runner` green (address/uniqueness/pause tests). Commit.

## Task 3: `bank/mod.rs` — data model, derivation, hand-rolled fixed-layout codec, golden KAT

**Files:** create `execution/src/bank/mod.rs`; `execution/src/lib.rs` (`pub mod bank;`).
**Encoding rule (audit R3):** stored structs use **hand-rolled fixed/variable-layout bytes** exactly like `payment_gate/mod.rs::PaymentPolicy` — **NOT serde**. Conventions: integers big-endian (`to_be_bytes`/`from_be_bytes`); `bool` = 1 byte; enums = 1 byte via `as_u8`/`from_u8` (validating); `Address` = 20 raw bytes (`.as_ref()` / `addr20`); `Option<T>` = 1-byte present/absent tag then the value; variable Vecs = `u16` BE length prefix + `MAX` cap on decode + trailing-byte rejection. `CardPolicy` is **stored raw** (the exact wire `Vec<u8>`), never decode→re-encode.

- [ ] **Step 1: module skeleton + imports + `pub mod bank;`**

`execution/src/lib.rs`: add `pub mod bank;` next to `pub mod payment_gate;`. Create `bank/mod.rs` with:
```rust
use crate::error::ExecutionError;
use cowboy_types::{Address, keccak256};

pub const CARD_DERIVATION_DOMAIN: &[u8] = b"CowboyBankCard\x01"; // 15 bytes
pub const GENESIS_BANK_ID: u32 = 1;
pub const MAX_ALLOWED_RECEIVERS: usize = 64;
pub const MAX_ALLOWED_SYSCALL_KINDS: usize = 16;

fn addr20(s: &[u8]) -> Address { Address::from_bytes(s.try_into().expect("20-byte address")) }
```

- [ ] **Step 2: enums (`PayCurrency`, `CardStatus`, `BankStatus`, `SyscallKind`) with `as_u8`/`from_u8`**

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CardStatus { Active, Frozen, Closed, Expired }
impl CardStatus {
    fn as_u8(self) -> u8 { match self { Self::Active=>0, Self::Frozen=>1, Self::Closed=>2, Self::Expired=>3 } }
    fn from_u8(b: u8) -> Result<Self, ExecutionError> {
        Ok(match b { 0=>Self::Active,1=>Self::Frozen,2=>Self::Closed,3=>Self::Expired,_=>return Err(ExecutionError::InvalidData) })
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BankStatus { Active, Paused }
impl BankStatus { fn as_u8(self)->u8{match self{Self::Active=>0,Self::Paused=>1}} fn from_u8(b:u8)->Result<Self,ExecutionError>{Ok(match b{0=>Self::Active,1=>Self::Paused,_=>return Err(ExecutionError::InvalidData)})} }
```
`PayCurrency` is a tagged Option-of-Address in disguise (0=Native, 1=Token+20B):
```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PayCurrency { Native, Token(Address) }
```
`SyscallKind` faithful to CIP-28 §2.4 (audit L2 — do NOT flatten to `u16`): encode as a 1-byte discriminant, and for `Custom(u16)` a trailing `u16` BE:
```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SyscallKind { Send, DeployActor, PublishLibrary, Token, CrossChain, Session, Cbss, Custom(u16) }
// encode: push discriminant; if Custom, push 2 BE bytes. decode: read 1 byte; if == CUSTOM_TAG read u16.
```

- [ ] **Step 3: structs (`CardPolicy`, `SpendWindow`, `BankEntry`, `CardEntry`)**

Use the revised data model in this plan's "Data model" section verbatim, including `pub issuance_principal: [u8; 32]` on `CardEntry` (M1 writes zeros).

- [ ] **Step 4: `derive_card_address` (failing KAT first)**

Write the KAT test, run it (fails — fn missing), then implement:
```rust
pub fn derive_card_address(bank_id: u32, owner: &Address, agent: &Address, issue_nonce: u64) -> Address {
    let mut buf = Vec::with_capacity(CARD_DERIVATION_DOMAIN.len() + 4 + 20 + 20 + 8);
    buf.extend_from_slice(CARD_DERIVATION_DOMAIN);
    buf.extend_from_slice(&bank_id.to_be_bytes());
    buf.extend_from_slice(owner.as_ref());
    buf.extend_from_slice(agent.as_ref());
    buf.extend_from_slice(&issue_nonce.to_be_bytes());
    let h = keccak256(&buf);
    Address::from_bytes(h[12..32].try_into().unwrap()) // NB: NO Address::from_slice
}
```
Test (`#[cfg(test)]`): pin the derived address for a fixed tuple as a hex KAT; assert changing `owner` changes the address (salt) and re-deriving the same tuple is stable.

- [ ] **Step 5: `BankEntry::encode/decode` + golden KAT**

Fixed+variable layout: `bank_id`(4 BE) · `status`(1) · `operator`(20) · `fiat_mint_signer` Option-tag(1)+[20] · `registered_at`(8 BE) · `name` u16-len-prefix+bytes (cap 32). Mirror `PaymentPolicy::decode`'s bounds-checked `take` + trailing-byte guard. Add `bank_entry_golden_vector` pinning `hex::encode(sample.encode())`.

- [ ] **Step 6: `CardEntry::encode/decode` + golden KAT**

Fixed order: `card_address`(20)·`bank_id`(4)·`owner`(20)·`agent`(20)·`issue_nonce`(8)·`issuance_principal`(32)·`created_at`(8)·`last_renewed_at`(8)·`expires_at` Option-tag(1)+[8]·`status`(1)·`gas_payment_token` PayCurrency-tag(1)+[20]·`policy` u16-len-prefix + **raw policy bytes** (cap 8192). Add `card_entry_golden_vector` KAT. (Store the policy as the raw bytes received on the wire — do not decode/re-encode.)

- [ ] **Step 7: run all bank/mod tests, commit**

`cargo test -p cowboy-execution bank:: 2>&1 | tail`; expect green. Commit `execution/src/bank/mod.rs` + `execution/src/lib.rs`.

## Task 4: `bank/storage.rs` — key schema + typed R/W

**Files:** create `execution/src/bank/storage.rs`.
TDD: key-layout test (prefix bytes + lengths) mirroring `payment_gate/storage.rs:226`. Implement `get_raw`/`set_raw` pinned to `BANK_ACTOR_SYSTEM_ACTOR`, key builders (`bank_key`, `bank_seq_key`, `card_key`, `card_by_owner_key`, `card_by_agent_key`, `issue_nonce_key`, **`stablecoin_whitelist_key`** — the last read by `issue_card`/`close_card` and seeded in Task 7), and typed accessors `read_bank`/`write_bank`/`read_card`/`write_card`/`read_issue_nonce`/`bump_issue_nonce`/`append_owner_index`/`append_agent_index`/`remove_indices`/`stablecoin_whitelist_contains`/`genesis_stablecoin_whitelist`. `write_card` takes the raw policy bytes so the stored `CardEntry` carries the wire-raw `CardPolicy` (Task 3 R3). Make these `pub`/`pub(crate)` as needed so `chain/src/genesis.rs` (Task 7) can call `bank_key`/`bank_seq_key`/`stablecoin_whitelist_key` + `BankEntry::encode`. Commit.

## Task 5: `bank/handlers.rs` — issue / deposit / withdraw / close (audit-revised)

**Files:** create `execution/src/bank/handlers.rs`; register topics in `consensus_event_topics.rs`.
**Discipline:** every handler is **check-then-apply** — validate ALL preconditions before the first state write (the speculative engine does not roll back partial writes on `Err`; a mid-handler balance move followed by a failing write = fund loss). Handlers are methods on `ExecutionEngine` (like `handle_token_transfer`) or free fns taking `store`; mirror the `payment_gate/handlers.rs` shape and its test setup.

**Balance-move primitives (audit-confirmed):**
- CIP-20: `read_balance(store, &token_registry::balance_key(&addr, token_id))` / `write_balance(...)`.
- Native CBY: `store.get_account(&addr) -> Option<Account>`; `Account.balance: u128`; `store.set_account(addr, acct)`.
- **No per-holder token enumeration exists** — do NOT iterate `get_tokens_index()` (global, unbounded, un-gassed in M1 → DoS).
- Recipient validation (inline, `ExecutionError` flavor of `validate_balance_recipient`): reject 20-byte-zero and the `0x01..=0x0F` system band.

- [ ] **Step 1: shared helpers — `require_receiver_ok`, `move_currency`**

```rust
/// Reject zero and the 0x01..=0x0F system band (mirror pvm_host::validate_balance_recipient, ExecutionError flavor).
fn require_receiver_ok(to: &Address) -> Result<(), ExecutionError> {
    let b = to.as_ref();
    if b == [0u8; 20] { return Err(ExecutionError::InvalidData); }
    if b[..19].iter().all(|x| *x == 0) && b[19] <= 0x0F && b[19] != 0 { return Err(ExecutionError::InvalidData); }
    Ok(())
}
/// Move `amount` of `cur` from `from` to `to`, check-then-apply. CBY via Account.balance, token via balance_key.
async fn move_currency<S: StateStore>(store: &mut S, cur: PayCurrency, from: &Address, to: &Address, amount: u128) -> Result<(), ExecutionError> { /* read both, verify from-balance >= amount, then write both */ }
```
(For native CBY, `Account.balance` is `u128`; a card address is a plain account created on first credit via `get_account(..).unwrap_or_else(Account::new)`.)

- [ ] **Step 2: `issue_card` — §3.1 validations + derivation + indices (TDD)**

Tests first: happy path persists `CardEntry` at `derive_card_address(...)` + `card_by_owner`/`card_by_agent` indices + bumps `issue_nonce`; two issues for same (bank,owner,agent) → two distinct addresses; **bank absent/Paused → error**; **`gas_payment_token` = Token(x) where x ∉ genesis stablecoin whitelist → error**; **`allowed_receivers.len() > 64` or `allowed_syscall_kinds.len() > 16` → error** (audit A9). Then implement:
```rust
pub async fn issue_card<S: StateStore>(store, bank_id: u32, agent: &Address, gas_payment_token: PayCurrency,
    initial_policy_raw: &[u8], expires_at: Option<u64>, caller: &Address, block_height: u64) -> Result<Address, ExecutionError> {
    let bank = read_bank(store, bank_id).await?.ok_or(ExecutionError::InvalidData)?;
    if bank.status != BankStatus::Active { return Err(ExecutionError::InvalidData); }
    // gas_payment_token whitelist (Native always ok; Token must be in genesis whitelist)
    if let PayCurrency::Token(t) = gas_payment_token { if !stablecoin_whitelist_contains(store, &t).await? { return Err(ExecutionError::InvalidData); } }
    let policy = CardPolicy::decode(initial_policy_raw)?; // validates ≤64 receivers / ≤16 syscall kinds inside decode
    let nonce = read_issue_nonce(store, bank_id, caller, agent).await?;
    let card_address = derive_card_address(bank_id, caller, agent, nonce);
    // build CardEntry { status: Active, issuance_principal: [0u8;32], window: zeroed, policy, gas_payment_token, .. }, store raw policy bytes
    write_card(store, &card_address, &entry, initial_policy_raw).await?;
    append_owner_index(store, caller, bank_id, &card_address).await?;
    append_agent_index(store, agent, bank_id, &card_address).await?;
    bump_issue_nonce(store, bank_id, caller, agent).await?;
    self.system_events.push((BANK_EVT_CARD_ISSUED.into(), encode_card_issued(&card_address, bank_id, caller, agent, expires_at)));
    Ok(card_address)
}
```
Enforce `≤64`/`≤16` inside `CardPolicy::decode` (so it's a single choke point) AND assert here.

- [ ] **Step 3: `deposit` — move funds card-ward (TDD)**

Tests: moves CBY and a CIP-20 token caller→card; unknown card → error; `amount == 0` → error; a Frozen card still accepts (forward-compat; reachable only via storage backdoor in M1 — label the test as such, audit L4). Implement: load card (must exist; status ≠ Closed), `amount != 0`, then `move_currency(store, cur, caller, &card_address, amount)`, emit `CardDeposited`.

- [ ] **Step 4: `withdraw` — owner-only + recipient validation (TDD)**

Tests: non-owner → error; insufficient balance → error; `require_receiver_ok` rejects zero/system-band `to`; frozen → error (backdoor); happy path moves card→to. Implement: load card; `caller == card.owner` else error; `card.status != Frozen`; `require_receiver_ok(to)?`; `move_currency(store, cur, &card_address, to, amount)`; emit `CardWithdrawn`.

- [ ] **Step 5: `close_card` — BOUNDED sweep + residual rescue (audit R1, TDD)**

Tests: owner-only; `require_receiver_ok(refund_to)`; sweeps **CBY + each genesis-whitelisted stablecoin** the card holds to `refund_to`; sets `status=Closed`; removes indices; re-close → error; a non-whitelisted reserve token is **left on the card** (recoverable via post-Close `Withdraw`) — assert it is NOT swept. Implement:
```rust
pub async fn close_card<S: StateStore>(store, card_address: &Address, refund_to: &Address, caller: &Address) -> Result<(), ExecutionError> {
    let mut card = read_card(store, card_address).await?.ok_or(ExecutionError::InvalidData)?;
    if card.status == CardStatus::Closed { return Err(ExecutionError::InvalidData); }
    if card.owner != *caller { return Err(ExecutionError::InvalidData); }
    require_receiver_ok(refund_to)?;
    // BOUNDED sweep: native CBY + genesis stablecoin whitelist ONLY (audit A1 — no global mints_index scan)
    let bal_cby = /* card CBY balance */;
    if bal_cby > 0 { move_currency(store, PayCurrency::Native, card_address, refund_to, bal_cby).await?; }
    for token in genesis_stablecoin_whitelist(store).await? {
        let b = read_balance(store, &token_registry::balance_key(card_address, &token)).await?;
        if b > 0 { move_currency(store, PayCurrency::Token(token), card_address, refund_to, b).await?; }
    }
    card.status = CardStatus::Closed;
    write_card(store, card_address, &card, &card_policy_raw).await?;
    remove_indices(store, &card).await?;
    self.system_events.push((BANK_EVT_CARD_CLOSED.into(), encode_card_closed(card_address, refund_to)));
    Ok(())
}
```
Doc-comment: arbitrary reserve tokens are recovered via explicit `Withdraw` on the Closed card (CIP-28 §5.3), NOT auto-swept. For CUSD (mandatory transfer hook), sweep/withdraw succeed only when `refund_to == owner` (audit A12) — note in the handler doc.

- [ ] **Step 6: register event topics + commit**

Add `TokenBankCardIssued`/`...Deposited`/`...Withdrawn`/`...Closed` (or `CardIssued` etc. — pick names) to `consensus_event_topics.rs` `KNOWN_CONSENSUS_EVENT_TOPICS` (the `consensus_event_topics_are_registered` test fails otherwise). `cargo test -p cowboy-execution bank`; commit.

## Task 6: Dispatch + bank pause gate + event-emitter attribution (NO activation gate)

**Files:** `execution/src/execution/system_instruction.rs`, new `execution/src/execution/bank_pause_gate.rs` (mirror `cbss_pause_gate.rs`), `storage/src/speculative.rs`.
There is **no** activation-height gate (Decision 5 / R2). Three sub-changes:

- [ ] **Step 1: bank pause gate (mirror cbss_pause_gate)**

Create `execution/src/execution/bank_pause_gate.rs`:
```rust
pub(crate) fn system_instruction_targets_bank(inst: &SystemInstruction) -> bool {
    matches!(inst,
        SystemInstruction::BankIssueCard { .. } | SystemInstruction::BankDeposit { .. }
        | SystemInstruction::BankWithdraw { .. } | SystemInstruction::BankCloseCard { .. })
}
pub(crate) async fn assert_bank_not_paused_for_instruction<S: StateStore>(
    store: &S, inst: &SystemInstruction, block_height: u64,
) -> Result<(), ExecutionError>
where <S as StateStore>::Error: std::error::Error + Send + Sync + 'static {
    if system_instruction_targets_bank(inst) {
        crate::execution::council::assert_target_not_paused(store, &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, block_height).await?;
    }
    Ok(())
}
```
Call it in `execute_system_instruction` **right after the CBSS gate** (`system_instruction.rs:52-58`), before `match inst`:
```rust
super::bank_pause_gate::assert_bank_not_paused_for_instruction(store, inst, block_height).await?;
```
(No `activation` param — the gate is unconditional; being pausable is the whole point, audit A6.) TDD: pause `0x16` via council, assert a `BankDeposit` is rejected **before** any balance move (mirror a cbss-pause test).

- [ ] **Step 2: dispatch arm (mirror PaymentGate `:4809`)**

```rust
cowboy_types::SystemInstruction::BankIssueCard { .. }
| cowboy_types::SystemInstruction::BankDeposit { .. }
| cowboy_types::SystemInstruction::BankWithdraw { .. }
| cowboy_types::SystemInstruction::BankCloseCard { .. } => {
    use crate::bank::handlers as bank;
    gas_meters.cycles.consume(self.gas_costs.base_cycles)?;
    gas_meters.cells.consume(self.gas_costs.base_cells)?;
    match inst {
        cowboy_types::SystemInstruction::BankIssueCard { bank_id, agent, gas_payment_token, initial_policy, expires_at } =>
            self.issue_card(store, *bank_id, agent, gas_payment_token.into(), initial_policy, *expires_at, sender, block_height).await.map(|_| None),
        cowboy_types::SystemInstruction::BankDeposit { card_address, token, amount } =>
            self.bank_deposit(store, card_address, token, *amount, sender, sender_account).await.map(|_| None),
        cowboy_types::SystemInstruction::BankWithdraw { card_address, token, amount, to } =>
            self.bank_withdraw(store, card_address, token, *amount, to, sender).await.map(|_| None),
        cowboy_types::SystemInstruction::BankCloseCard { card_address, refund_to } =>
            self.bank_close_card(store, card_address, refund_to, sender).await.map(|_| None),
        _ => unreachable!("outer arm restricts to Bank variants"),
    }
}
```
(Convert the codec `PayCurrency`/`token: Address` wire form to the `bank::PayCurrency` used by handlers — decide one representation, audit L5. Context vars `store,sender,sender_account,gas_meters,block_height` are in scope per `execute_system_instruction` params.)

- [ ] **Step 3: event-emitter attribution (audit A5 — the compiler will NOT flag this)**

In `storage/src/speculative.rs`, add `BANK_ACTOR_SYSTEM_ACTOR` to the `cowboy_types` import (line 39) and add this arm to `system_event_emitter`'s inner `Instruction::System` match, **immediately before the `_ => None` catch-all (~line 425)**:
```rust
SystemInstruction::BankIssueCard { .. } | SystemInstruction::BankDeposit { .. }
| SystemInstruction::BankWithdraw { .. } | SystemInstruction::BankCloseCard { .. }
    => Some(BANK_ACTOR_SYSTEM_ACTOR),
```
TDD: an attribution test asserting a `BankIssueCard` event's committed emitter is `0x16`, not `tx.from`.

- [ ] **Step 4: routing test + commit**

Submit a `BankIssueCard` through `execute_system_instruction` and assert a `CardEntry` is persisted at `derive_card_address(...)`. `cargo test -p cowboy-execution`. Commit.

## Task 7: Genesis — `GenesisConfig` fields + seed Cowboy Banking (bank_id = 1)

**Files:** `chain/src/genesis.rs`.

- [ ] **Step 1: add `GenesisConfig` fields (audit L1/A9)**

Next to `council` (~:262-269), add:
```rust
    #[serde(default)] pub bank_operator: cowboy_types::Address,
    #[serde(default)] pub stablecoin_whitelist: Vec<cowboy_types::Address>,
```
In `validate()` (~:561), reject a zero `bank_operator` (a real operator is required for a real testnet; a placeholder-zero is only tolerable if you consciously allow it on devnet — flag in the error message).

- [ ] **Step 2: seed the BankActor account + bank:1 (mirror `trading_post` + council)**

In `create_runner_system_actors`, after the `trading_post` block:
```rust
let bank_addr = cowboy_types::BANK_ACTOR_SYSTEM_ACTOR;
let bank_code_hash = register_code(b"# Bank System Actor (CIP-28)".to_vec());
actors.push((bank_addr, Actor {
    address: bank_addr, code_hash: bank_code_hash, nonce: 0, parent: Address::ZERO,
    storage_root: cowboy_types::EMPTY_STORAGE_ROOT,           // placeholder root (COW-1277 guard passes unchanged)
    manifest: None, children_count: 0, transfer_block: 0, transfer_block_amount: 0,
    quota_bytes: cowboy_types::constants::RENT_QUOTA_BASE, rent_debt: 0, last_settled_epoch: 0,
    rate_stamped_atto: 0, bond_locked_atto: 0, dormant_since_epoch: None, pre_evict_storage_hash: None,
}));
// bank_id = 1 "Cowboy Banking" — encode with the SAME hand-rolled codec the runtime read path uses (NOT serde_json)
let bank1 = cowboy_execution::bank::BankEntry {
    bank_id: 1, name: b"Cowboy Banking".to_vec(), operator: self.bank_operator,
    fiat_mint_signer: None, status: BankStatus::Active, registered_at: 0,
};
initial_storage.push((bank_addr, cowboy_execution::bank::storage::bank_key(1), bank1.encode()));
initial_storage.push((bank_addr, cowboy_execution::bank::storage::bank_seq_key(), 2u32.to_be_bytes().to_vec()));
// stablecoin whitelist under a dedicated key (read by issue_card / close_card)
initial_storage.push((bank_addr, cowboy_execution::bank::storage::stablecoin_whitelist_key(), encode_addr_list(&self.stablecoin_whitelist)));
```
**Key point:** the seeded `BankEntry` bytes MUST equal what `read_bank`/`BankEntry::decode` (Task 4) expects — use `bank1.encode()`, not `serde_json`. (The COW-1277 guard test iterates seeded actors and asserts `storage_root == EMPTY_STORAGE_ROOT`; since we seed with the placeholder root, it passes with **no edit** — audit F6.)

- [ ] **Step 3: TDD + commit**

Genesis test: build a `GenesisConfig` with a non-zero `bank_operator` + a one-token whitelist, run `create_runner_system_actors`, apply `initial_storage`, and assert `read_bank(1)` returns the Cowboy Banking entry with the configured operator, `bank_seq == 2`, and the whitelist round-trips. Confirm `genesis_seeded_actors_carry_placeholder_empty_storage_root_pending_cow_1277` still passes unchanged. Commit.

## Task 8: Full workspace green + finalize

- `cargo build --workspace` + `cargo test --workspace` + `cargo clippy --workspace --all-targets` green.
- Add any exhaustive-match arms the compiler flags for the new `Bank*` opcodes (indexer JSON, speculative actor-classifier, cbss pause gate — mirror how they treat PaymentGate opcodes).
- **Finalize (user-gated, like W1 Task 9):** push both branches, open PRs (codec base `main`, node base `devnet`), bump the codec rev-pin in `node/types/Cargo.toml` to the merged SHA + remove the dev `[patch]`. Customer summary + flag-day note (new system actor + opcodes + genesis state → coordinated `bank_activation_height`). **Do NOT push without explicit user authorization.**

---

## Staging beyond M1 (separate plans)
- **M2** — `SetDefaultCard`; tx-level `fee_payer_override` (codec, cross-repo, wallet-compat); `BankActor.charge_gas` Phase-1 reserve / Phase-2 settle in the fee-settle fork; timer-deferred integration.
- **M3** — `SetPolicy`; `SpendWindow` roll/enforce; whitelist match; `Freeze`/`Unfreeze`/`PauseBank`; `locked_after_transfer`.
- **M4** — `MintFromFiatVoucher` + `voucher_used:` replay set; `SetBankFiatMintSigner`; `issuance_principal` + `IssuancePrincipalVoucher`; off-chain gateway (separate service).
- **M5** — `RegisterBank`/`SetBankOperator`; multi-bank isolation; `TransferOwnership`.
- **settle_provider (CIP-36 §6.3)** rides on M4 + W1 `burn_from` (now upstream at opcode 24) — a separate task once W1 merges.

## Self-Review
- Spec coverage (CIP-28 M1 def): 0x16 placement → Task 2; genesis Cowboy Banking → Task 7; IssueCard/Deposit/Withdraw/CloseCard → Tasks 1 (wire) + 5 (handlers); card derivation → Task 3; card_by_owner/agent indices → Tasks 4 + 5. ✓
- Deferred-correctly: policy enforcement/windows (stored not enforced, M3), gas-charging (M2), fiat (M4), default-card (M2) — explicitly out of M1 per Decision 3.
- Cross-repo ordering + rev-pin mirrors the proven W1 flow. Consensus/flag-day surfaced (Decision 5, Task 8).
