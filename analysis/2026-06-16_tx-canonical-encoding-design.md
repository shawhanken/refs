# Design — Canonical Transaction Encoding & Signing (WP §2 conformance)

**Date:** 2026-06-16
**Status:** Design approved (brainstorming), pending implementation plan.
**Cluster (B-3):** COW-1937, 1942, 1943, 1944, 1212, 1215, 1945.
**Spec authority decided:** the implemented **instruction-based** transaction model is
authoritative; the whitepaper §2 flat-Ethereum-tx description is stale and will be
**rewritten** to describe the canonical instruction-tx form. We do **not** flatten the tx
to `to/value/payload`.

---

## 1. Problem

Whitepaper §2 (cowboy-technical-whitepaper.md, lines 461–493, normative) defines a
transaction as a flat 13-element ordered CBOR array
`[chain_id, nonce, to, value, cycles_limit, cells_limit, tip×2, access_list, payload, signature]`
with signing hash `keccak256(CBOR(Tx_without_signature))`. The implementation
(`node/types/src/execution.rs`) diverges on every axis:

1. **Model.** `to`/`value`/`payload` are folded into a typed `Instruction` enum
   (`System | Actor | Custom | Library`, with its own `TX_CATEGORY_*` wire opcodes). This
   model is intentional and richer (system instructions, deploy, library ops, multi-call);
   flattening it would be a severe regression.
2. **Encoding.** `Transaction::write` does `into_writer(self)` → serde-CBOR **map**
   (field-name keys), not an ordered array.
3. **Signing.** The signing hash is computed over a **separate `PayloadSign` subset struct**
   (`Transaction::payload_bytes`), not over the real transaction. The subset can silently
   drift from the wire tx (a field added to `Transaction` but not to `PayloadSign` is
   unsigned and malleable). (COW-1944)
4. **Replay.** There is **no `chain_id` in the signed payload** (genesis carries
   `chain_id: Option<u64>` but the tx does not), so a signed tx is replayable across
   chains/forks. (COW-1212)
5. **access_list.** Absent from the tx; the audit ticket calls validation an "empty stub".
   (COW-1215)

**Context:** this is **devnet** (genesis-configurable `chain_id`, deploy-to-dev CI). There is
no live-mainnet transaction stream requiring backward compatibility, so migration can be a
single coordinated flag-day / devnet reset rather than a dual-format transition.

---

## 2. Decisions (locked)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Instruction model authoritative; rewrite WP §2 + Appendix A** to describe the canonical instruction-tx. | The instruction model is core and superior; regressing to flat `to/value/payload` would destroy system/deploy/library/multi-call. |
| D2 | **`access_list` kept as an OPTIONAL, advisory/reserved field; NOT enforced in v1.** WP documents it as reserved for future parallel-scheduling/prefetch. | The instruction already names its target; Cowboy has no EVM access-list gas mechanics. Normative enforcement is a large consensus surface with no current benefit. The empty stub becomes a documented design choice, not a bug. |
| D3 | **Clean-break flag-day / devnet reset.** Single activation point; node + all tx producers switch together; no dual-format support code. | Devnet ⇒ no tx backward-compat burden. Simplest, least code. |

---

## 3. Scope

**In (v1):**
- COW-1937 — canonical field set (the real instruction-tx fields, frozen order).
- COW-1942 — deterministic ordered-array CBOR encoding (replace serde map).
- COW-1943 — `to`/`value` stay inside `Instruction` (resolved by D1); add optional `access_list`.
- COW-1944 — signing hash over `canonical(tx with signatures nulled)`; delete `PayloadSign`.
- COW-1212 — `chain_id` in the signed payload + admission validation.
- COW-1215 — `access_list` semantics (resolved by D2: optional advisory).
- COW-1945 — pinned conformance test vectors (TV1 unsigned, TV2 signed).

**Out (explicitly deferred to sibling specs, to keep this plan single-purpose):**
- COW-1941 — Header/Block canonical array encoding. Touches `block_hash` (a distinct
  consensus surface). Reuses this design's canonical-codec machinery; phase-2 sibling.
- COW-1934 / 1935 — `python_source` canonicalization (UTF-8/NFC/LF/no-BOM) and CREATE2-style
  actor-address derivation. Related "canonicalization" theme but independent of tx encoding.
- COW-1753 — CIP-17 bundled account-trie state-read proof. Unrelated.

---

## 4. Units (single responsibility, independently testable)

### 4.1 `canonical` codec — `node/types/src/canonical.rs` (new)
- **Responsibility:** deterministic bytes ↔ `Transaction`.
- **Interface:** `encode(tx: &Transaction) -> Vec<u8>`; `decode(bytes: &[u8]) -> Result<Transaction, CodecError>`.
- **Encoding rules (RFC 8949 §4.2.1 "core deterministic" subset):**
  - Top level is a **definite-length CBOR array** whose elements are the transaction fields
    in the **frozen order** of §5.1.
  - Integers use **minimal-length** encoding; **no** floating point; **no** indefinite-length
    items; map/array lengths are definite. Byte strings (addresses, hashes, signature,
    metadata) are major-type-2 with minimal length headers.
  - `Instruction` is encoded as its own deterministic sub-array `[category, sub_type, body]`
    consistent with the existing `tx_type()` opcode scheme (so the typed enum has a stable,
    canonical wire form). `body` is the recursive deterministic encoding of the selected
    variant's fields.
  - `Option<T>` encodes as CBOR `null` (absent) or the value (present). `Vec<T>` as a
    definite-length array.
  - **The deterministic rules apply recursively** to every nested structure (the instruction
    body and all its sub-fields, `access_list` entries, `additional_signers` entries), so the
    entire transaction tree has exactly one canonical byte form.
- **Strict decoding (anti-malleability — consensus-critical):** `decode` MUST **reject**
  (not normalize) any input that is not the exact canonical encoding: non-minimal integers,
  indefinite-length items, trailing bytes after the array, wrong element count, duplicate or
  unexpected structure. **Invariant:** every `Transaction` has exactly one valid byte
  encoding, and `decode(encode(tx)) == tx` and `encode(decode(b)) == b` for all canonical `b`.
- **Depends on:** a CBOR primitive layer (evaluate `ciborium`/the existing `into_writer` low
  level vs a hand-rolled minimal writer — the implementation plan picks one; the requirement
  is determinism + strictness, not the library).

### 4.2 `chain_id` field + admission validation
- Add `chain_id: u64` to `Transaction` (§5.1). Sourced by clients from the node's genesis
  `chain_id`. Included in canonical encoding and the signing hash.
- **Admission:** reject a tx whose `chain_id != node.chain_id` with a new structured error
  (e.g. `E_TX_WRONG_CHAIN_ID`). The error code enters the receipt/StructuredError path, so
  this is consensus-relevant.

### 4.3 signing-hash function (replaces `payload_bytes`/`payload_hash`/`PayloadSign`)
- `signing_hash(tx: &Transaction) -> [u8; 32]` = `keccak256(canonical_encode(tx'))` where
  `tx'` is `tx` with the **primary `signature` set to `EthSignature::ZERO`** and **each
  `additional_signers[i].1` (the signature) zeroed**, while the **signer addresses
  (`from`, `additional_signers[i].0`) are retained** (so the signed payload still binds the
  signer set, preventing cross-account replay — preserving today's property).
- Multi-sig: every signer signs the **same** `signing_hash`.
- **Deferred transactions** (`is_deferred()`: nonce=0, `signature == ZERO`,
  `origin_remaining_*` present) are **system-injected and never user-signed**; their
  authenticity continues to be enforced by the `origin_remaining_*` bound checks in
  `verify()`. The canonical encoding still includes the `origin_*` fields so `tx_hash` is
  deterministic, but the signing-hash/`ecrecover` path is taken only for non-deferred txs.

### 4.4 `tx_hash`
- `tx_hash(tx) = keccak256(canonical_encode(full signed tx))` — one canonical form
  end-to-end (admission, mempool keys, receipts, block tx-root).

### 4.5 conformance test vectors — shared fixture
- `TV1` (unsigned: signatures null) and `TV2` (signed) for a representative instruction tx
  (e.g. a `System(Transfer)` to a fixed address with fixed gas), pinned as lowercase hex.
- Stored once as a shared JSON fixture (e.g. `refs/common/tx-canonical-vectors.json` or a
  path both node and wallet check out) and consumed by:
  - a node conformance test (`canonical_encode` of TV inputs == pinned hex; `signing_hash` of
    TV2 == pinned hash),
  - the wallet byte-parity test (§6).
- These vectors **replace** WP Appendix A's flat-model vectors.

### 4.6 WP rewrite — `cowboy/docs/whitepaper/cowboy-technical-whitepaper.md`
- Rewrite §2 (Transaction Types & Encoding) and Appendix A to describe the **instruction-tx**
  canonical form: the frozen field array (§5.1), the `Instruction` sub-encoding, the
  signing-hash rule, `chain_id`, and `access_list` as reserved/advisory. Promote the
  encoding section to remain **normative**; Appendix A vectors become normative and match the
  shared fixture.

---

## 5. Canonical transaction shape

### 5.1 Frozen field order (the canonical array)
The canonical encoding is a definite-length array of these elements **in this order**
(order is part of the spec and MUST NOT change without a new tx format version):

```
[ chain_id,
  nonce,
  instruction,                    # sub-array [category, sub_type, body]
  cycles_limit,
  cells_limit,
  max_fee_per_cycle,
  max_fee_per_cell,
  max_priority_fee_per_cycle,
  max_priority_fee_per_cell,
  from,                           # 20-byte address
  access_list,                    # null | [[address, [storage_key,...]], ...]
  metadata,                       # byte string (may be empty)
  origin_tx_hash,                 # null | 32-byte (deferred only)
  origin_remaining_cycles,        # null | u64  (deferred only)
  origin_remaining_cells,         # null | u64  (deferred only)
  signature,                      # 65-byte; ZERO in TV1 / deferred
  additional_signers ]            # [[address, signature], ...] (may be empty)
```

Notes:
- `to`/`value` are **not** top-level — they live inside `instruction` (e.g.
  `System(Transfer{to, amount})`), per D1.
- `access_list` is present but `null` in v1 (D2).
- The deferred-only fields (`origin_*`) are `null` for ordinary user txs.

### 5.2 Signing vs hashing
- **Signing hash:** `keccak256(canonical_encode(tx with signature=ZERO and all
  additional_signers signatures zeroed; addresses kept))`.
- **tx_hash:** `keccak256(canonical_encode(full tx))`.

---

## 6. Cross-repo coordination

Changing the encoding/signing/`tx_hash` ripples to **every transaction producer**, which must
emit byte-identical canonical encodings:

| Repo | Component | Work |
|---|---|---|
| node | `types` (encode/sign/verify/admission) | the core change |
| wallet | JS signer (`window.cowboy`, tx encoder) | **highest risk** — re-implement deterministic CBOR array + keccak in JS, byte-identical to node |
| node/cli | tx builder | switch to canonical signing |
| pvm/SDK (python) | any client-side tx construction | switch to canonical signing |
| runner | result/job tx submission (if it builds txs) | switch to canonical signing |

**Byte-parity mechanism:** the shared TV fixture (§4.5) is the single source of truth; node and
wallet both run a test asserting their encoder reproduces the pinned TV hex and signing hash.
A mismatch is a build failure on either side.

---

## 7. Migration / activation (flag-day)

1. Land node PRs (additive first, then the switch) on devnet behind the flag-day.
2. Land client PRs (wallet/cli/SDK/runner) so producers emit the new format.
3. Coordinate a **single activation** — devnet reset or an activation height — at which the
   node enforces canonical encoding + `chain_id` + the new signing hash, and all clients are
   already emitting it. No dual-format window.
4. Publish a short rollout runbook (order, who flips what, rollback = revert to the reset
   point). Marshal verdict on the consensus PRs will be **needs_human** (tx_hash/state-root
   change) — expected; the runbook is the coordination artifact.

---

## 8. Testing & conformance invariants

| Invariant / test | Asserts |
|---|---|
| `contract.tx_canonical_roundtrip` | `encode→decode→encode` is byte-identical; `decode` **rejects** the 5 non-canonical classes (non-minimal int, indefinite length, trailing bytes, wrong element count, malformed sub-structure). |
| `contract.tx_signing_hash_vector` | `signing_hash(TV2 inputs)` == pinned hash; `canonical_encode(TV1)` == pinned hex. |
| `contract.tx_chain_id_replay` | a tx with `chain_id != node.chain_id` is rejected at admission. |
| wallet byte-parity test | wallet encoder reproduces the shared TV hex + signing hash. |
| existing tx/signature/mempool/econ suites | remain green (regression). |

All of the above run through the Marshal invariant gate. Because the change moves
`tx_hash`/`state-root`, the consensus PRs are coordinated-rollout (needs_human).

---

## 9. PR sequence (each independently reviewable)

1. **PR1 (node):** `canonical` codec module + golden round-trip + malleability tests. Purely
   additive (parallel encoder), no behavior change.
2. **PR2 (node):** add `chain_id` + `access_list` fields to `Transaction`; include them in the
   canonical encoding; validate `chain_id` at admission. (Consensus: tx shape change.)
3. **PR3 (node):** switch wire encoding + signing hash + `tx_hash` to canonical; delete
   `PayloadSign`; enable strict decoding; pin TV1/TV2 conformance tests. (Consensus: the
   flag-day change.)
4. **PR4 (wallet):** JS canonical encoder + keccak; byte-parity test vs shared TV.
5. **PR5 (cli / SDK / runner):** switch tx construction to canonical signing.
6. **PR6 (cowboy docs):** rewrite WP §2 + Appendix A as normative instruction-tx encoding.
7. **Activation:** coordinated devnet reset / flag-day across all repos.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Wallet JS byte-parity (deterministic CBOR is easy to get subtly wrong) | Shared TV fixture + parity tests on both sides; node ships the vectors first. |
| Strict-canonical determinism (all nodes must agree accept/reject for any byte string) | Hand-specified strict decoder + the 5-class malleability test suite; no "normalize then accept". |
| Consensus activation across 6 PRs / 4 repos | Explicit PR ordering + rollout runbook + flag-day; revert = reset point. |
| Deferred-tx fields are not user-signed | Sign/verify path branches on `is_deferred()`; canonical encoding still includes `origin_*` for `tx_hash` determinism. |
| Scope creep into Header/Block (1941) or address derivation (1934/1935) | Explicitly out of scope; sibling specs reuse the codec. |

---

## 11. Open items for the implementation plan (not design blockers)
- Choose the CBOR primitive layer for the strict deterministic codec (library vs hand-rolled).
- Final home/path of the shared TV fixture readable by both node and wallet.
- Exact new error-code slug/number for `chain_id` mismatch (follow the four-part error format,
  COW-386).
