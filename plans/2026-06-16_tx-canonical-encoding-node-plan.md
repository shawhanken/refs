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
| `node/types/src/execution.rs` | `Transaction` struct + `Write`/`Read`/`EncodeSize` + `signing_hash`/`digest` + verify | Modify: add 2 fields; rewrite codec; replace `payload_*` with `signing_hash`/`signing_preimage`; **migrate `digest_preimage` (Task 5b, F1)** |
| `node/types/src/constants.rs` | error code + `MAX_TRANSACTION_BYTES` + Cfg bound consts | Modify: add `E_TX_WRONG_CHAIN_ID`; `*_CFG`/`MAX_ADDITIONAL_SIGNERS` |
| `node/types/src/tx_vectors.rs` | frozen conformance vectors TV1/TV2 + tests | Create |
| `node/rpc/src/handlers/chain.rs` | submission boundary | Modify: `Submission::decode` (reject trailing) + re-home `MAX_TRANSACTION_BYTES` (Task 3 §4, F3/F5) |
| `node/chain/src/mempool_listener.rs` | mempool decode boundary | Modify: same strict-decode fix (F3) |
| `node/rpc/src/handlers/runner.rs` | runner message-to-sign / heartbeat | Modify: migrate `payload_hash`→`signing_hash` (Task 9b, F2) |
| `node/cli/src/commands.rs` | cli tx signing | Modify: migrate `payload_*`→`signing_hash` (Task 9b, F2) |
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
        // access_list / metadata Cfg: see the "Note on Cfg" below for the exact nested
        // (RangeCfg, ..) types — these are net-new, no template exists. Use bounded RangeCfg.
        let access_list = Option::<Vec<(Address, Vec<[u8; 32]>)>>::read_cfg(reader, &ACCESS_LIST_CFG)?;
        let metadata = Vec::<u8>::read_cfg(reader, &METADATA_CFG)?;
        let origin_tx_hash = Option::<Digest>::read(reader)?;
        let origin_remaining_cycles = Option::<u64>::read(reader)?;
        let origin_remaining_cells = Option::<u64>::read(reader)?;
        let signature = EthSignature::read(reader)?;
        let additional_signers = Vec::<(Address, EthSignature)>::read_cfg(reader, &ADDITIONAL_SIGNERS_CFG)?;
        Ok(Self { chain_id, nonce, instruction, cycles_limit, cells_limit,
            max_fee_per_cycle, max_fee_per_cell, max_priority_fee_per_cycle,
            max_priority_fee_per_cell, from, access_list, metadata, origin_tx_hash,
            origin_remaining_cycles, origin_remaining_cells, signature, additional_signers })
    }
}
```

**Note on `Cfg` (F4 — this is net-new codec work, not a copy):** `additional_signers`
(`Vec<(Address, EthSignature)>`) and `access_list` (`Option<Vec<(Address, Vec<[u8;32]>)>>`)
were previously serialized inside the whole-tx serde-CBOR blob — **there is no existing
commonware-codec read of a `Vec<(Address, ...)>` tuple to copy.** Write it explicitly:
- `Vec<T>::read_cfg` takes `(RangeCfg, T::Cfg)`. For a tuple `(A, B)`, `T::Cfg = (A::Cfg, B::Cfg)`.
- `Address::Cfg = ()`, `EthSignature::Cfg = ()`, `[u8;32]::Cfg = ()`.
- So `additional_signers` Cfg is `(RangeCfg, ((), ()))`; `metadata: Vec<u8>` is `(RangeCfg, ())`;
  `access_list: Option<Vec<(Address, Vec<[u8;32]>)>>` is `Option`-tag + the inner Vec Cfg
  `(RangeCfg, ((), (RangeCfg, ())))`.
- Pick the `RangeCfg` upper bounds from sane limits (reuse a `MAX_TRANSACTION_BYTES`-derived
  element cap; e.g. a small `MAX_ADDITIONAL_SIGNERS` and access-list bounds). **Do not** use
  unbounded `..` for attacker-controlled `Vec`s. Verify the exact `RangeCfg` constructor
  spelling against `commonware_codec` (it is `RangeCfg::from(..=N)` / a range), and confirm
  `EthSignature` actually `impl`s `Read`/`Write`/`FixedSize` (it does — `signature.rs:105`).

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

- [ ] **Step 4: Enforce strict decoding at the real submission boundary (F3 + F5)**

The production decode is `Submission::read(&mut body.as_ref())` at
`node/rpc/src/handlers/chain.rs:221` (and the mempool listener path). **`commonware_codec::Read::read_cfg`
does NOT check end-of-buffer** — only `Decode::decode`/`decode_cfg` does (`Error::ExtraData`).
So switch the boundary to the end-of-buffer-checking decode and reject trailing bytes:

```rust
// node/rpc/src/handlers/chain.rs ~:221 — was Submission::read(&mut body.as_ref())
use commonware_codec::DecodeExt; // or Decode
let submission = match Submission::decode(body.as_ref()) { // rejects trailing bytes (ExtraData)
    Ok(s) => s,
    Err(e) => return /* 400 invalid submission */,
};
```

Also **re-home the `MAX_TRANSACTION_BYTES` bound** that previously lived inside the deleted
length-prefixed `Transaction::read` (`constants.rs` + old `:411`): enforce it at this boundary
(reject a submission whose encoded tx exceeds `MAX_TRANSACTION_BYTES`). Apply the same
`decode`-not-`read` + size-bound fix to the mempool listener path
(`node/chain/src/mempool_listener.rs:175`), which decodes **`Pending::read`** (not
`Submission`/`Transaction`) — `Pending` has `Cfg=()`, so switch it to `Pending::decode(data)`
to reject trailing bytes.

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

- [ ] **Step 1: Write the failing tests against the REAL decode path**

Use `Submission::decode` (the end-of-buffer-checking codec extension) — the same call the
boundary uses (Task 3 Step 4) — not a fictional helper. Put this test in the crate that owns
`Submission` (`cowboy-types`).

```rust
// Submission is an ENUM (api.rs:437): variants Seed/Transactions/Summary — there is NO
// `Submission::single`. Use the Transactions variant.
#[test]
fn submission_decode_rejects_trailing_bytes() {
    let sub = Submission::Transactions(vec![sample_signed_tx()]);
    let mut bytes = sub.encode().to_vec();
    bytes.push(0xAA); // trailing garbage
    assert!(Submission::decode(bytes.as_ref()).is_err(),
        "trailing bytes after a submission must be rejected (ExtraData)");
}

#[test]
fn submission_decode_rejects_truncated() {
    let sub = Submission::Transactions(vec![sample_signed_tx()]);
    let bytes = sub.encode();
    assert!(Submission::decode(&bytes[..bytes.len() - 1]).is_err());
}

#[test]
fn tx_read_rejects_truncated() {
    let tx = sample_signed_tx();
    let bytes = tx.encode();
    assert!(Transaction::read(&mut &bytes[..bytes.len() - 1]).is_err());
}
```

- [ ] **Step 2: Run**

Run: `cargo test -p cowboy-types -- submission_decode_rejects tx_read_rejects -- --nocapture`
Expected: PASS once Task 3 Step 4 switches the boundary to `decode`. (`read`-vs-`decode` is the
whole point: `read` ignores trailing bytes, `decode` rejects them.)

- [ ] **Step 3: Commit**

```bash
git add node/types/src/execution.rs
git commit -m "test(types): tx decode rejects trailing/truncated bytes (anti-malleability)"
```

---

## Task 5: `signing_hash` over canonical encoding; delete `PayloadSign`

> **ORDERING (S1):** Task 5 deletes `payload_bytes`, but `digest_preimage()` still calls it
> until Task 5b migrates it. **Do Task 5b's `digest_preimage` migration in the SAME change as
> the `payload_bytes` deletion** (Steps below: add `signing_preimage` + `signing_hash` first,
> then migrate `digest_preimage` (5b Step 3), THEN delete `payload_bytes`). The document
> numbers 5 → 5b but the deletion must come last.

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
        keccak256(&self.signing_preimage())
    }

    /// Canonical encoding with every signature zeroed (signer addresses kept).
    /// Shared by `signing_hash` AND `digest_preimage` (Task 5b), so the tx
    /// identity is signature-independent and there is one canonical preimage.
    pub fn signing_preimage(&self) -> Vec<u8> {
        let mut bare = self.clone();
        bare.signature = EthSignature::ZERO;
        for (_addr, sig) in bare.additional_signers.iter_mut() {
            *sig = EthSignature::ZERO;
        }
        bare.encode().to_vec()
    }
}
```

`keccak256` is called bare (it is `use`d in the crate already, `execution.rs:5/175`) — **not**
`cowboy_types::keccak256` (that path does not resolve inside the `cowboy-types` crate).

Delete `payload_bytes` and `payload_hash` (and the inner `PayloadSign` struct). Update the
sign helpers (`:189`, `:241`) to sign `self.signing_hash()`. (Note: `digest_preimage` is
migrated to reuse `signing_preimage` in **Task 5b** — do that before deleting `payload_bytes`,
or `digest_preimage` won't compile.)

- [ ] **Step 4: Update `verify()`** (`:317`) — replace the `payload_hash(...)` call with
`self.signing_hash()`, recovering each signer against it. Keep the deferred-tx branch
unchanged (deferred txs are not signature-verified).

```rust
// in verify(), non-deferred branch.
// recover_address returns Result<Address, RecoveryError> (signature.rs:70) — match Ok, not Some.
let hash = self.signing_hash();
match self.signature.recover_address(&hash) {
    Ok(addr) if addr == self.from => {}
    _ => return false,
}
for (addr, sig) in &self.additional_signers {
    match sig.recover_address(&hash) {
        Ok(rec) if &rec == addr => {}
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

## Task 5b: Migrate `digest()` / `digest_preimage()` to the canonical encoding (F1 — critical)

The chain's tx identity is `Transaction::digest() = keccak256(digest_preimage())`
(`execution.rs:438`), used for the tx-root Merkle leaves (`storage/src/merkle_utils.rs`),
receipt keys + tx-location (`storage/src/process_block.rs`), the indexer
(`chain/src/indexer.rs`), and deferred-origin checks. `digest_preimage()` (`:444`) currently
calls the deleted `payload_bytes` **and** manually appends deferred extras (`origin_tx_hash`
+ origin gas as BE bytes). After this work those fields are intrinsic canonical fields, so the
manual append is redundant. **The tx identity stays signature-independent** (today's property):
`digest_preimage` reuses `signing_preimage` (signatures zeroed). Result: `tx_hash == signing_hash`.

> **Note:** `tx_hash == signing_hash` is intentional and benign. `digest()` is **already**
> signature-independent today (it hashes `payload_bytes`, which excludes the signature), so no
> consumer assumes `tx_hash` commits to the signature — verified: `merkle_utils.rs:20`,
> `process_block.rs:47`, and the indexer all just consume `digest()`. This matches the prior
> behavior; it is not a semantic change downstream.

**Files:**
- Modify: `node/types/src/execution.rs:438-485` (`digest`, `digest_preimage`)

- [ ] **Step 1: Write the failing test**

```rust
#[test]
fn digest_preimage_is_canonical_signature_independent() {
    let tx = sample_signed_tx();
    // identity excludes the signature (re-signing / s-malleability must not change the digest)
    let mut tx2 = tx.clone();
    tx2.signature = EthSignature::ZERO;
    assert_eq!(tx.digest(), tx2.digest(), "digest must be signature-independent");
    // identity DOES cover content (metadata, chain_id, instruction)
    let mut tx3 = tx.clone();
    tx3.metadata = b"y".to_vec();
    assert_ne!(tx.digest(), tx3.digest());
    // digest preimage == signing preimage (one canonical preimage)
    assert_eq!(tx.digest_preimage(), tx.signing_preimage());
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-types digest_preimage_is_canonical_signature_independent -- --exact`
Expected: FAIL (old `digest_preimage` uses `payload_bytes` + manual deferred append).

- [ ] **Step 3: Reimplement `digest_preimage`**

```rust
impl Transaction {
    /// The canonical BMT-leaf preimage: the signature-independent canonical
    /// encoding (origin_* fields are intrinsic, so no manual deferred append).
    pub fn digest_preimage(&self) -> Vec<u8> {
        self.signing_preimage()
    }
}
```

`digest()` (`:438`) is unchanged: `Digest::from(keccak256(&self.digest_preimage()))`.

- [ ] **Step 4: Run + full digest/deferred regression**

Run: `cargo test -p cowboy-types -- digest && cargo test -p cowboy-execution -- deferred`
Expected: PASS. Fix any deferred-tx test that hard-coded the old preimage layout; the
`origin_tx_hash` tamper-resistance property still holds (those fields are in the canonical
encoding).

- [ ] **Step 5: Note the cross-repo ripple (do NOT change here)**

The Solidity bridge re-derives `keccak256(digest_preimage())` (comment at `:446-448`). Its
leaf re-derivation must move to the canonical encoder. Add a one-line note to the follow-on
cross-repo plan; under the devnet flag-day there is likely no live bridge to migrate yet.

- [ ] **Step 6: Commit**

```bash
cargo fmt --all
git add node/types/src/execution.rs
git commit -m "feat(types): tx digest over canonical signature-independent preimage (COW-1944/F1)"
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

## Task 9b: Migrate same-workspace `payload_*` callers — cli + rpc/runner (F2 — in scope)

Deleting `payload_bytes`/`payload_hash` (Task 5) breaks node-internal callers that the spec
wrongly deferred. These MUST migrate to `signing_hash()` in this plan, or those flows fail
`verify()` / won't compile.

**Files:**
- Modify: `node/rpc/src/handlers/runner.rs` — ALL `Transaction::payload_bytes`/`payload_hash`
  call sites. There are more than heartbeat: `heartbeat_payload_hash` (`:272-273`, used `:398/409/459`)
  PLUS the message-to-sign endpoints at **`:944, :1071, :1208, :1309, :1469, :1587`**
  (job-result, registration, etc.). `:882` is only a doc comment — the real calls are the six
  above. Every one breaks when Task 5 deletes `payload_bytes`; `cargo build -p cowboy-rpc`
  (Step 3) is the backstop, but migrate them all deliberately.
- Modify: `node/cli/src/commands.rs` (tx signing call sites that use `payload_hash`/`payload_bytes`)

- [ ] **Step 1: Migrate the runner message-to-sign hashes (all 7 sites)**

Each site builds the `Transaction` the runner will submit and must hand the runner **the same
hash `verify()` now checks** = `tx.signing_hash()`. For `heartbeat_payload_hash` (`:273`) and
each of the six message-to-sign endpoints, construct the `Transaction` and return
`tx.signing_hash()`; the recover side (`:460 recover_address(&payload_hash)`) already returns
`Result` — feed it the new hash; `message_to_sign_base64` (`:409`) encodes the new hash bytes.

**chain_id threading (REQUIRED — Task 1 made `chain_id` mandatory, Task 9 rejects mismatches):**
the server-built tx for heartbeat/each endpoint must set `chain_id = node's configured chain_id`
(the same value admission checks) and `access_list: None`, so the hash it signs matches the tx
that passes admission. Source `node_chain_id` from the node config already threaded for Task 9;
do NOT take it from the (untrusted) request body.

- [ ] **Step 2: Migrate cli signing**

In `node/cli/src/commands.rs`, replace any `Transaction::payload_hash(...)`/`payload_bytes(...)`
construction with `tx.signing_hash()` on the assembled `Transaction` (set `chain_id` from the
node's configured chain id; `access_list: None`).

- [ ] **Step 3: Build the affected crates**

Run: `cargo build -p cowboy-rpc -p cowboy-cli`
Expected: compiles (no references to the deleted `payload_hash`/`payload_bytes`).

- [ ] **Step 4: Test the runner heartbeat sign/verify round-trip**

Run: `cargo test -p cowboy-rpc -- heartbeat`
Expected: the endpoint's returned hash, when signed, is accepted by the recover path (update
the existing heartbeat test to the new hash).

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add node/rpc/src/handlers/runner.rs node/cli/src/commands.rs
git commit -m "feat: migrate cli + runner message-to-sign to canonical signing_hash (F2)"
```

---

## Task 10: Full workspace regression + invariant gate

- [ ] **Step 1: Run the full suite**

Run: `cd node && CARGO_TARGET_DIR=$PWD/.cargo-target cargo test --workspace`
Expected: green. Known tests that WILL break and must be rewritten to `signing_hash`/canonical
`encode`/`digest`: `test_transaction_codec_roundtrip` (`execution.rs:5585`), the
`payload_hash`/`payload_bytes` tests (`:8573-8632`, `:6283`), the `digest_preimage` tests
(`:5716, 5739`), and any golden test with hard-coded serde-CBOR tx bytes. Also the runner
heartbeat test (Task 9b) and any chain/storage test asserting a specific `tx.digest()`/tx-root.

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

## In scope (folded in from the audit, F1/F2/F3)
- **`digest()`/`tx_hash` migration** (Task 5b) — was the critical omission (F1).
- **node cli + rpc/runner message-to-sign** (Task 9b) — same-workspace `payload_*` callers (F2).
- **Strict trailing-byte rejection + `MAX_TRANSACTION_BYTES` re-home** at `Submission::decode`
  and the mempool listener (Task 3 §4 / Task 4) (F3/F5).

## Out of scope (separate follow-on plans)
- **Wallet parity** (JS commonware-codec encoder + keccak, byte-parity vs `refs/common/tx-canonical-vectors.json`).
- **SDK (python)** client switch to canonical signing.
- **Solidity bridge** BMT-leaf re-derivation must move to the canonical encoder (F1 ripple) —
  cross-repo coordination item; likely no live bridge under the devnet flag-day.
- **WP rewrite** (cowboy docs): §2 + Appendix A **and the standalone MUST at WP line 198**
  ("all data crossing trust boundaries MUST use canonical CBOR") **and §2.2(d)** (access-list
  invalid ⇒ reject) — re-state for the commonware-codec canonical encoding + advisory access_list (F5).
- **Flag-day activation** runbook + coordinated devnet reset.
- **Header/Block canonicalization (COW-1941)** and **address/code_hash canonicalization (COW-1934/1935)** — sibling specs.

## Open items to resolve during review (not blockers)
- Exact `RangeCfg` constructor spelling for the net-new `Vec<(Address, …)>` reads (no template
  exists — see Task 3's "Note on Cfg", F4); define `ACCESS_LIST_CFG`/`METADATA_CFG`/`ADDITIONAL_SIGNERS_CFG`.
- **`chain_id` decision (resolved):** pin a concrete devnet `chain_id` in genesis (genesis
  currently `Option<u64>` defaulting to `None`); clients use it; admission rejects mismatch —
  no "accept-any" in non-test config. Confirm the pinned value with the genesis owner.
- Max-length constants for `metadata`/`access_list`/`additional_signers` (derive from `MAX_TRANSACTION_BYTES`).
