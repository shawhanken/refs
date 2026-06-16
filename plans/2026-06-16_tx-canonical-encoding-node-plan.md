# Canonical Transaction Encoding — Node Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Transaction` use the same deterministic, ordered `commonware-codec` binary encoding the rest of the chain already uses (Block/Instruction), add `chain_id` (replay protection) and an optional reserved `access_list`, sign over the canonical encoding (deleting the drift-prone `PayloadSign`), and pin conformance vectors.

**Architecture:** Replace `Transaction`'s lone serde-CBOR `Write`/`Read`/`EncodeSize` (`node/types/src/execution.rs:397`) with ordered `commonware-codec` field writes, mirroring `Block::write` (`:4042`) and reusing `Instruction`'s existing `Write`/`Read` (`:1647`/`:2581`). The signing hash becomes `keccak256(canonical_encode(tx with signatures zeroed))`. `chain_id` is added to the struct and validated at admission.

**Tech Stack:** Rust, `commonware_codec::{Write, Read, ReadExt, EncodeSize, varint::UInt, RangeCfg, Error}`, `keccak256`, `secp256k1` ecrecover (`EthSignature`).

**Spec:** `refs/analysis/2026-06-16_tx-canonical-encoding-design.md` (see §0 refinement: encoding primitive = commonware-codec). This plan covers the **node core** (spec PRs 1–3, unified by the commonware-codec decision). Wallet/cli/SDK parity, the WP §2 rewrite, and flag-day activation are **separate follow-on plans** (they depend on the vectors this plan produces).

**Scope note — this plan is consensus-relevant:** it changes the tx wire encoding, `tx_hash`, the signing hash, and the tx struct shape. It is intended to land behind a coordinated devnet flag-day (see spec §7). Marshal verdict will be `needs_human`; that is expected.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `node/types/src/execution.rs` | `Transaction` struct + `Write`/`Read`/`EncodeSize` + signing/verify | Modify: add 2 fields; rewrite codec; replace `payload_*` with `signing_hash` |
| `node/types/src/constants.rs` | error slug/code for chain-id mismatch | Modify: add `E_TX_WRONG_CHAIN_ID` |
| `node/types/src/tx_vectors.rs` | frozen conformance vectors TV1/TV2 + tests | Create |
| `node/<admission path>` (chain/mempool) | reject wrong `chain_id` | Modify (Task 9) |

The canonical **field order** is frozen (spec §5.1):
`chain_id, nonce, instruction, cycles_limit, cells_limit, max_fee_per_cycle, max_fee_per_cell, max_priority_fee_per_cycle, max_priority_fee_per_cell, from, access_list, metadata, origin_tx_hash, origin_remaining_cycles, origin_remaining_cells, signature, additional_signers`.

---

## Task 1: Add `chain_id` + `access_list` fields to `Transaction`

**Files:**
- Modify: `node/types/src/execution.rs` (the `pub struct Transaction` at ~line 63)

- [ ] **Step 1: Add the fields to the struct**

In `pub struct Transaction { ... }`, add `chain_id` as the first field and `access_list` after `from`:

```rust
pub struct Transaction {
    /// Chain this transaction is valid on (replay protection, WP §2). Bound into
    /// the signing hash; admission rejects a mismatch.
    pub chain_id: u64,
    pub nonce: u64,
    pub instruction: Instruction,
    // ... existing gas fields unchanged ...
    pub from: Address,
    /// Optional, advisory/reserved access list (WP §2). v1: always `None`, not
    /// enforced; reserved for future parallel-scheduling/prefetch.
    #[serde(default)]
    pub access_list: Option<Vec<(Address, Vec<[u8; 32]>)>>,
    pub signature: EthSignature,
    // ... existing additional_signers / origin_* / metadata unchanged ...
}
```

- [ ] **Step 2: Fix all `Transaction { .. }` literal constructions to set the new fields**

Run: `cargo build -p cowboy-types 2>&1 | grep -E "missing field (chain_id|access_list)"`
Expected: a list of construction sites. For each, add `chain_id: <appropriate>, access_list: None,`. Test/helper constructions use `chain_id: 0` (or the test chain id); real builders thread the configured chain id. (Deferred-tx construction at `:308` uses `chain_id: 0`, `access_list: None`.)

- [ ] **Step 3: Build to green**

Run: `cargo build -p cowboy-types`
Expected: compiles (codec/signing updated in later tasks may still warn; no errors).

- [ ] **Step 4: Commit**

```bash
git add node/types/src/execution.rs
git commit -m "feat(types): add chain_id + reserved access_list to Transaction (COW-1212/1215/1937)"
```

---

## Task 2: Write the failing canonical round-trip test

**Files:**
- Modify: `node/types/src/execution.rs` (tests module, near the existing tx tests ~line 8565)

- [ ] **Step 1: Add the test**

```rust
#[test]
fn tx_canonical_roundtrip_is_byte_identical() {
    let tx = sample_signed_tx(); // helper: a System(Transfer) tx, chain_id=42, access_list=None
    let bytes = tx.encode();                       // commonware_codec::Encode
    let decoded = Transaction::decode(&mut bytes.as_ref()).expect("decode");
    assert_eq!(decoded, tx, "decode∘encode must be identity");
    assert_eq!(decoded.encode(), bytes, "re-encode must be byte-identical");
}
```

Add the `sample_signed_tx()` helper in the tests module (build a `Transaction` with
`chain_id: 42`, a `System(Transfer { to, amount })` instruction, fixed gas, sign with a
fixed key via the existing signing helper updated in Task 5).

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-types tx_canonical_roundtrip_is_byte_identical -- --exact`
Expected: FAIL — currently `encode` is serde-CBOR (still passes round-trip but) the test pins behavior we are about to change; if it passes now, it will guard the rewrite in Task 3. (If it passes pre-rewrite, keep it as a regression guard.)

- [ ] **Step 3: Commit the test**

```bash
git add node/types/src/execution.rs
git commit -m "test(types): pin canonical tx round-trip"
```

---

## Task 3: Rewrite `Transaction` `Write`/`Read`/`EncodeSize` to ordered commonware-codec

**Files:**
- Modify: `node/types/src/execution.rs:397-432` (the three impls)

This replaces the serde-CBOR outlier. **Mirror the established idiom in `Block::write` (`:4042`)
and `Instruction::read` (`:2581`)**: `UInt(x).write(writer)` for `u64`; `.write(writer)` for
typed fields (`Address`, `EthSignature`, `Instruction`); `Option`/`Vec`/tuple via their
`commonware-codec` impls. **Reuse `Instruction`'s existing `Write`/`Read` unchanged.**

- [ ] **Step 1: Replace `impl Write for Transaction`**

```rust
impl Write for Transaction {
    fn write(&self, writer: &mut impl BufMut) {
        UInt(self.chain_id).write(writer);
        UInt(self.nonce).write(writer);
        self.instruction.write(writer);
        UInt(self.cycles_limit).write(writer);
        UInt(self.cells_limit).write(writer);
        UInt(self.max_fee_per_cycle).write(writer);
        UInt(self.max_fee_per_cell).write(writer);
        UInt(self.max_priority_fee_per_cycle).write(writer);
        UInt(self.max_priority_fee_per_cell).write(writer);
        self.from.write(writer);
        self.access_list.write(writer);          // Option<Vec<(Address, Vec<[u8;32]>)>>
        self.metadata.write(writer);             // Vec<u8>
        self.origin_tx_hash.write(writer);       // Option<Digest>
        self.origin_remaining_cycles.write(writer); // Option<u64>
        self.origin_remaining_cells.write(writer);
        self.signature.write(writer);
        self.additional_signers.write(writer);   // Vec<(Address, EthSignature)>
    }
}
```

(If `Option<u64>`/`Vec<(...)>` need an explicit length/varint wrapper to match the rest of the
codebase, follow exactly what `Block::write`/`Account::write` do for the analogous types —
those are the authoritative idiom; do not invent a different one.)

- [ ] **Step 2: Replace `impl Read for Transaction` with a STRICT reader**

```rust
impl Read for Transaction {
    type Cfg = ();
    fn read_cfg(reader: &mut impl Buf, _: &Self::Cfg) -> Result<Self, Error> {
        let chain_id = UInt::<u64>::read(reader)?.into();
        let nonce = UInt::<u64>::read(reader)?.into();
        let instruction = Instruction::read(reader)?;
        let cycles_limit = UInt::<u64>::read(reader)?.into();
        let cells_limit = UInt::<u64>::read(reader)?.into();
        let max_fee_per_cycle = UInt::<u64>::read(reader)?.into();
        let max_fee_per_cell = UInt::<u64>::read(reader)?.into();
        let max_priority_fee_per_cycle = UInt::<u64>::read(reader)?.into();
        let max_priority_fee_per_cell = UInt::<u64>::read(reader)?.into();
        let from = Address::read(reader)?;
        let access_list = Option::<Vec<(Address, Vec<[u8; 32]>)>>::read_cfg(reader, &(.., (.., ()).into()).into())?; // see note
        let metadata = Vec::<u8>::read_cfg(reader, &(..).into())?;
        let origin_tx_hash = Option::<Digest>::read(reader)?;
        let origin_remaining_cycles = Option::<u64>::read(reader)?;
        let origin_remaining_cells = Option::<u64>::read(reader)?;
        let signature = EthSignature::read(reader)?;
        let additional_signers = Vec::<(Address, EthSignature)>::read_cfg(reader, &(.., ()).into())?;
        Ok(Self { chain_id, nonce, instruction, cycles_limit, cells_limit,
            max_fee_per_cycle, max_fee_per_cell, max_priority_fee_per_cycle,
            max_priority_fee_per_cell, from, access_list, metadata, origin_tx_hash,
            origin_remaining_cycles, origin_remaining_cells, signature, additional_signers })
    }
}
```

**Note on `Cfg` for `Vec`/`Option<Vec>`:** the exact `RangeCfg` arguments must match how the
codebase reads bounded `Vec`s elsewhere (search `read_cfg` in `execution.rs` — e.g. how
`Block::read` reads `transactions`, how `Account::read` reads its `Vec`s). Copy that idiom
exactly; the bound for `metadata`/`access_list`/`additional_signers` should reuse the existing
length-bound constants (e.g. `MAX_TRANSACTION_BYTES`-derived). Do not introduce unbounded reads.

- [ ] **Step 3: Replace `impl EncodeSize for Transaction`** with the sum of field `encode_size()`s (same field order), mirroring `Block`'s `EncodeSize` (`:4141`).

```rust
impl EncodeSize for Transaction {
    fn encode_size(&self) -> usize {
        UInt(self.chain_id).encode_size()
            + UInt(self.nonce).encode_size()
            + self.instruction.encode_size()
            + UInt(self.cycles_limit).encode_size()
            // ... all fields in order ...
            + self.signature.encode_size()
            + self.additional_signers.encode_size()
    }
}
```

- [ ] **Step 4: Enforce strict decoding at the call boundary**

Find where a tx is decoded from a length-delimited buffer (submission/mempool). Ensure the
decoder rejects **trailing bytes** after a full `Transaction::read` (no leftover in the
delimited region) and a wrong byte length. If the existing framing already length-delimits and
checks `remaining()`, assert that property in a test (Task 4); otherwise add the check.

- [ ] **Step 5: Run the round-trip test**

Run: `cargo test -p cowboy-types tx_canonical_roundtrip_is_byte_identical -- --exact`
Expected: PASS.

- [ ] **Step 6: Remove now-unused serde-CBOR imports if orphaned by this change** (`into_writer`/`from_reader`/`Cursor`) — only if no other code in the file uses them (grep first).

- [ ] **Step 7: Commit**

```bash
cargo fmt --all
git add node/types/src/execution.rs
git commit -m "feat(types): encode Transaction with ordered commonware-codec, not serde-CBOR (COW-1942/1937)"
```

---

## Task 4: Malleability — strict decode rejects non-canonical input

**Files:**
- Modify: `node/types/src/execution.rs` (tests module)

- [ ] **Step 1: Write the failing tests**

```rust
#[test]
fn tx_decode_rejects_trailing_bytes() {
    let tx = sample_signed_tx();
    let mut bytes = tx.encode().to_vec();
    bytes.push(0xAA); // trailing garbage
    // The submission-layer decoder (length-delimited) must reject extra bytes.
    assert!(decode_tx_strict(&bytes).is_err(), "trailing bytes must be rejected");
}

#[test]
fn tx_decode_rejects_truncated() {
    let tx = sample_signed_tx();
    let bytes = tx.encode();
    let truncated = &bytes[..bytes.len() - 1];
    assert!(Transaction::decode(&mut <&[u8]>::clone(&truncated)).is_err());
}
```

`decode_tx_strict` is the submission-boundary decoder from Task 3 Step 4 (exact-length). If the
boundary is in another crate, place this test there instead and import the helper.

- [ ] **Step 2: Run to verify they fail / then pass after Task 3's strict boundary**

Run: `cargo test -p cowboy-types tx_decode_rejects -- --nocapture`
Expected: PASS once Task 3 Step 4 is in place (trailing/truncated rejected).

- [ ] **Step 3: Commit**

```bash
git add node/types/src/execution.rs
git commit -m "test(types): tx decode rejects trailing/truncated bytes (anti-malleability)"
```

---

## Task 5: `signing_hash` over canonical encoding; delete `PayloadSign`

**Files:**
- Modify: `node/types/src/execution.rs` (`payload_bytes`/`payload_hash` ~line 110-160; `verify` ~line 317-390; sign helpers ~line 189/241)

- [ ] **Step 1: Write the failing test**

```rust
#[test]
fn signing_hash_covers_all_signed_fields_and_excludes_signatures() {
    let mut tx = sample_signed_tx();
    let h0 = tx.signing_hash();
    // Mutating a previously-unsigned field (metadata) MUST change the hash now.
    tx.metadata = b"x".to_vec();
    assert_ne!(tx.signing_hash(), h0, "metadata must be covered by the signing hash");
    // Zeroing the signature must NOT change the signing hash (sig excluded).
    let mut tx2 = sample_signed_tx();
    let before = tx2.signing_hash();
    tx2.signature = EthSignature::ZERO;
    assert_eq!(tx2.signing_hash(), before, "signature must be excluded");
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-types signing_hash_covers_all_signed_fields_and_excludes_signatures -- --exact`
Expected: FAIL — `signing_hash` does not exist yet.

- [ ] **Step 3: Implement `signing_hash` and delete `PayloadSign`**

```rust
impl Transaction {
    /// keccak256 of the canonical encoding with all signatures zeroed (signer
    /// addresses retained). This is what every signer signs. Replaces PayloadSign.
    pub fn signing_hash(&self) -> [u8; 32] {
        let mut bare = self.clone();
        bare.signature = EthSignature::ZERO;
        for (_addr, sig) in bare.additional_signers.iter_mut() {
            *sig = EthSignature::ZERO;
        }
        cowboy_types::keccak256(&bare.encode())
    }
}
```

Delete `payload_bytes` and `payload_hash` (and the inner `PayloadSign` struct). Update the
sign helpers (`:189`, `:241`) to sign `self.signing_hash()`.

- [ ] **Step 4: Update `verify()`** (`:317`) — replace the `payload_hash(...)` call with
`self.signing_hash()`, recovering each signer against it. Keep the deferred-tx branch
unchanged (deferred txs are not signature-verified).

```rust
// in verify(), non-deferred branch:
let hash = self.signing_hash();
match self.signature.recover_address(&hash) {
    Some(addr) if addr == self.from => {}
    _ => return false,
}
for (addr, sig) in &self.additional_signers {
    match sig.recover_address(&hash) {
        Some(rec) if &rec == addr => {}
        _ => return false,
    }
}
true
```

- [ ] **Step 5: Run signing + existing signature tests**

Run: `cargo test -p cowboy-types -- signing_hash verify signature payload`
Expected: new test PASS; update/delete the old `payload_hash` tests (`:8599+`) that referenced the removed API — rewrite them to call `signing_hash()`.

- [ ] **Step 6: Commit**

```bash
cargo fmt --all
git add node/types/src/execution.rs
git commit -m "feat(types): sign over canonical encoding, delete PayloadSign drift (COW-1944)"
```

---

## Task 6: `chain_id` is bound into the signing hash (replay protection)

**Files:**
- Modify: `node/types/src/execution.rs` (tests module)

- [ ] **Step 1: Write the failing test**

```rust
#[test]
fn signing_hash_changes_with_chain_id() {
    let mut a = sample_signed_tx();      // chain_id = 42
    let mut b = a.clone();
    b.chain_id = 43;
    assert_ne!(a.signing_hash(), b.signing_hash(),
        "chain_id must be covered by the signing hash (replay protection)");
}
```

- [ ] **Step 2: Run**

Run: `cargo test -p cowboy-types signing_hash_changes_with_chain_id -- --exact`
Expected: PASS (chain_id is the first encoded field, already covered by Task 3+5). This test
locks COW-1212 at the type layer.

- [ ] **Step 3: Commit**

```bash
git add node/types/src/execution.rs
git commit -m "test(types): chain_id bound into signing hash (COW-1212)"
```

---

## Task 7: Error code for chain-id mismatch

**Files:**
- Modify: `node/types/src/constants.rs` (error slug/code table; follow the four-part format from COW-386)

- [ ] **Step 1: Add the slug + code**

Find the error registry (where `ERROR_SLUG`/`HOST_ERROR_CODE` mappings live, per COW-386/387).
Add `E_TX_WRONG_CHAIN_ID` with the next free code, four-part fields (what/why/fix/link):
- what: "transaction chain_id does not match this chain"
- why: "replay protection (WP §2): a tx signed for chain X is invalid on chain Y"
- fix: "rebuild and re-sign the tx with the node's chain_id"

- [ ] **Step 2: Build**

Run: `cargo build -p cowboy-types`
Expected: compiles.

- [ ] **Step 3: Commit**

```bash
git add node/types/src/constants.rs
git commit -m "feat(types): add E_TX_WRONG_CHAIN_ID structured error (COW-1212)"
```

---

## Task 8: Conformance vectors TV1/TV2 (frozen)

**Files:**
- Create: `node/types/src/tx_vectors.rs`
- Modify: `node/types/src/lib.rs` (add `mod tx_vectors;` under `#[cfg(test)]` or as a `pub mod` if shared)

- [ ] **Step 1: Write the test that pins the vectors**

```rust
//! Frozen canonical-encoding conformance vectors (WP §2 / COW-1945).
//! These hex strings are the contract clients (wallet/cli/SDK) must reproduce.
#[cfg(test)]
mod tests {
    use super::super::*;

    fn tv_transfer() -> Transaction {
        // chain_id=42, nonce=0, System(Transfer{to=0x1111..,amount=1}), fixed gas, from=0x..,
        // access_list=None, metadata=[], no additional signers, unsigned (signature=ZERO).
        // (construct deterministically — fixed addresses/keys)
        unimplemented_construct() // replace with the explicit literal in Step 3
    }

    #[test]
    fn tv1_unsigned_encoding_is_frozen() {
        let tx = tv_transfer();
        assert_eq!(hex::encode(tx.encode()), TV1_UNSIGNED_HEX);
        assert_eq!(hex::encode(tx.signing_hash()), TV1_SIGNING_HASH_HEX);
    }

    #[test]
    fn tv2_signed_encoding_is_frozen() {
        let tx = tv_transfer_signed(); // tv_transfer signed with FIXED_KEY
        assert_eq!(hex::encode(tx.encode()), TV2_SIGNED_HEX);
        assert!(tx.verify());
    }
}
```

- [ ] **Step 2: Run to get the actual hex (vectors are derived, then frozen)**

Run: `cargo test -p cowboy-types tv1_unsigned_encoding_is_frozen -- --nocapture` with the
asserts temporarily `println!`-ing the actual values; copy the real hex into the `TV*_HEX`
consts. Then restore the asserts. (This is the one place where the expected value is *produced*
by the implementation and then frozen — review the bytes by hand against §5.1 field order
before freezing.)

- [ ] **Step 3: Freeze the consts + write the shared JSON fixture**

Write `refs/common/tx-canonical-vectors.json` with `{tv1_unsigned_hex, tv1_signing_hash, tv2_signed_hex, fixed_key, fields}` so wallet/cli/SDK plans consume the same source of truth.

- [ ] **Step 4: Run**

Run: `cargo test -p cowboy-types tx_vectors`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add node/types/src/tx_vectors.rs node/types/src/lib.rs refs/common/tx-canonical-vectors.json
git commit -m "test(types): freeze canonical tx conformance vectors TV1/TV2 (COW-1945)"
```

---

## Task 9: Reject wrong `chain_id` at admission

**Files:**
- Modify: the tx-admission path (likely `node/chain/src/mempool.rs` or `node/rpc` submission / `node/execution` pre-exec validation — grep `fn admit`/`fn validate_transaction`/`MempoolOps::add`)

- [ ] **Step 1: Locate the admission validation + write the failing test**

Find where a submitted tx is first validated (signature/nonce checks). Add a test there:

```rust
#[test]
fn admission_rejects_wrong_chain_id() {
    let node_chain_id = 42;
    let mut tx = sample_signed_tx();      // chain_id = 42 → ok
    assert!(validate_admission(&tx, node_chain_id).is_ok());
    tx.chain_id = 43;
    // re-sign so the signature is valid but chain_id is wrong
    let tx = resign(tx);
    let err = validate_admission(&tx, node_chain_id).unwrap_err();
    assert_eq!(err.code(), ErrorCode::TxWrongChainId);
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p <admission-crate> admission_rejects_wrong_chain_id -- --exact`
Expected: FAIL.

- [ ] **Step 3: Add the check**

In the admission validator, after structural checks, before signature acceptance:

```rust
if tx.chain_id != node_chain_id {
    return Err(ApiError::structured(ErrorCode::TxWrongChainId, /* four-part fields */));
}
```

Source `node_chain_id` from the genesis config already threaded into the node (the
`chain_id: Option<u64>` in `chain/src/genesis.rs`; treat `None` as "accept any" only in test
config, or pin a devnet default — decide with the genesis owner during review).

- [ ] **Step 4: Run**

Run: `cargo test -p <admission-crate> admission_rejects_wrong_chain_id -- --exact`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add node/<admission path>
git commit -m "feat: reject transactions with mismatched chain_id at admission (COW-1212)"
```

---

## Task 10: Full workspace regression + invariant gate

- [ ] **Step 1: Run the full suite**

Run: `cd node && CARGO_TARGET_DIR=$PWD/.cargo-target cargo test --workspace`
Expected: green. Fix any test that hard-coded the old serde-CBOR tx bytes or `payload_hash` API
(rewrite to `signing_hash`/canonical `encode`).

- [ ] **Step 2: Run the econ + tx invariants explicitly**

Run: `cargo test -p cowboy-execution econ_invariants && cargo test -p cowboy-types -- tx_ signing_ canonical`
Expected: green.

- [ ] **Step 3: `cargo fmt` gate**

Run: `cargo fmt --all -- --check`
Expected: clean.

- [ ] **Step 4: Final commit if fmt changed anything**

```bash
git add -A && git commit -m "chore: fmt + regression fixes for canonical tx encoding"
```

---

## Out of scope (separate follow-on plans)
- **Wallet parity** (JS commonware-codec encoder + keccak, byte-parity vs `refs/common/tx-canonical-vectors.json`).
- **cli / SDK / runner** switch to canonical signing.
- **WP §2 + Appendix A rewrite** (cowboy docs) describing the canonical commonware-codec encoding.
- **Flag-day activation** runbook + coordinated devnet reset.
- **Header/Block canonicalization (COW-1941)** and **address/code_hash canonicalization (COW-1934/1935)** — sibling specs.

## Open items to resolve during review (not blockers)
- Exact `RangeCfg`/length-bound arguments for `Vec`/`Option<Vec>` reads — copy the existing
  `Block::read`/`Account::read` idiom verbatim.
- `chain_id` `None` handling in genesis (accept-any vs pinned devnet default) — genesis owner.
- Whether `metadata`/`access_list` need their own max-length constants (reuse `MAX_TRANSACTION_BYTES`-derived bound).
