# Design — Canonical Transaction Encoding & Signing (WP §2 conformance)

**Date:** 2026-06-16
**Status:** Design approved (brainstorming), pending implementation plan.
**Cluster (B-3):** COW-1937, 1942, 1943, 1944, 1212, 1215, 1945.
**Spec authority decided:** the implemented **instruction-based** transaction model is
authoritative; the whitepaper §2 flat-Ethereum-tx description is stale and will be
**rewritten** to describe the canonical instruction-tx form. We do **not** flatten the tx
to `to/value/payload`.

---

## 0. Refinement (2026-06-16): encoding primitive = commonware-codec, not CBOR

Plan-time grounding found that `Instruction`, `Block`, `Notarized`, `Actor`, `Message`,
`Account`, etc. **already use a deterministic, ordered `commonware_codec::{Write, Read}`
binary encoding** (`node/types/src/execution.rs:1647` Instruction, `:4042` Block — the latter
is what `block_hash`/consensus is built on). **`Transaction` is the lone outlier**: its
`Write` does `ciborium::into_writer(self)` → a serde-CBOR **map** (`execution.rs:397`). That
serde-CBOR map is the actual root cause of the "map vs array / non-canonical" defect.

**Decision (supersedes the "CBOR" framing in §4.1, §5, §4.6, §6, §11 below):** the canonical
encoding is the **ordered `commonware-codec` binary encoding**, reusing `Instruction`'s
existing `Write`/`Read`. We rewrite `Transaction::{Write, Read, EncodeSize}` to the ordered
field pattern that `Block` already uses (instead of serde-CBOR), add the new fields, and
define the signing hash over this encoding. WP §2 + Appendix A are rewritten to describe the
**canonical commonware-codec binary encoding** (not CBOR). This eliminates the outlier,
reuses the whole existing deterministic Instruction encoding (no per-variant re-encoding),
and aligns the tx with the consensus encoding used everywhere else. Wherever the sections
below say "CBOR array", read "ordered commonware-codec encoding"; the field order in §5.1 and
all other decisions stand unchanged.

---

## 0b. Audit fixes (2026-06-16, folding Marshal F1–F6)

An independent adversarial audit (Marshal, run #186) verified the determinism foundation and
the encoding decision as sound, but found real gaps. Resolutions (these SUPERSEDE the
matching text below; the node plan implements them):

- **F1 (critical) — `tx_hash` / `digest()` must be migrated explicitly.** The chain's tx
  identity is `Transaction::digest() = keccak256(digest_preimage())`, and `digest_preimage()`
  currently calls `payload_bytes()` (deleted by this work) plus a manual deferred-extras
  append (`execution.rs:444-485`). **Resolution:** `digest_preimage()` becomes the canonical
  `encode()` of the transaction **with all signatures zeroed** (the same preimage as
  `signing_hash`). This (a) removes the `payload_bytes` dependency, (b) makes `origin_*`
  intrinsic canonical fields so the manual deferred append disappears, (c) keeps the tx
  identity **signature-independent** (preserving today's property and closing ECDSA
  s-value malleability on identity). Consequence: `tx_hash == signing_hash` (same preimage).
  This supersedes §4.4's "encode(full signed tx)" — the canonical preimage **excludes**
  signatures. **Ripple:** the Solidity bridge re-derives `keccak256(digest_preimage())`
  (`execution.rs:446-448` comment) → its leaf re-derivation must switch to the canonical
  encoder; tracked as a cross-repo coordination item (devnet-flag-day, likely no live bridge).

- **F2 (high) — cli + the node's runner message-to-sign endpoint are IN SCOPE.** Deleting
  `payload_bytes`/`payload_hash` breaks same-workspace callers: `node/cli/src/commands.rs`
  signing and **`node/rpc/src/handlers/runner.rs`** (`heartbeat_payload_hash` `:273`, the
  `/…/message-to-sign` endpoints `:882+`) — the server-side hash the node hands runners to
  sign. These are node-internal and MUST migrate to `signing_hash()` in this plan (not the
  follow-on), or runner/heartbeat txs fail `verify()`.

- **F3 (high) — strict trailing-byte rejection at the real boundary.** The production decode
  is `Submission::read(&mut body.as_ref())` (`node/rpc/src/handlers/chain.rs:221`).
  `commonware_codec::Read::read_cfg` does **not** check end-of-buffer; only `Decode::decode`
  does (`Error::ExtraData`). **Resolution:** the submission boundary must use the
  end-of-buffer-checking decode (or assert `remaining() == 0`) and reject trailing bytes;
  tests target the real `Submission`/admission path, not a fictional helper.

- **F4 (medium) — plan snippets corrected:** `recover_address` returns `Result` (match
  `Ok(..)`, not `Some(..)`); `keccak256` is called bare/`crate::` inside the types crate (not
  `cowboy_types::`); the `Vec<(Address, Vec<[u8;32]>)>` (access_list) and
  `Vec<(Address, EthSignature)>` (additional_signers) codecs are **net-new** (no existing
  template to copy — they previously rode inside the whole-tx serde-CBOR blob).

- **F5 (med/low) — WP scope + bounds.** The WP rewrite must also amend the **standalone
  normative MUST at WP line 198** ("all data crossing trust boundaries MUST use canonical
  CBOR, RFC 8949") and **§2.2(d)** (access-list-invalid ⇒ reject) — not just §2/Appendix A.
  `MAX_TRANSACTION_BYTES` (`constants.rs`) is currently enforced inside the length-prefixed
  `Transaction::read`; with the prefix gone it must be re-homed to the submission boundary.

- **F6 (low) — accuracy.** `is_deferred()` is **purely `origin_tx_hash.is_some()`**
  (`execution.rs:277`) — §4.3's "(nonce=0, signature==ZERO, origin_remaining_* present)"
  describes conditions `verify()` checks for deferred txs, not the discriminant. **chain_id
  `None` decision:** genesis `chain_id` is `Option<u64>` defaulting to `None`; for devnet we
  **pin a concrete devnet `chain_id` in genesis** and clients use it — admission rejects any
  mismatch (no "accept-any" mode in non-test config). (See R3 — this must be an ordered
  activation step, not an invisible prerequisite.)

---

## 0c. Round-3 deep-audit fixes (2026-06-16, Marshal run #188 — block-for-revision)

A third, deeper audit walked the **`Instruction` leaf types** the first two rounds assumed
clean, and found the central anti-malleability invariant (§4.1: "every tx has exactly one
canonical byte encoding; `decode∘encode == id`") is **FALSE** for the reused codec. These are
MUST-FIX before implementation:

- **R1 (CRITICAL) — `Instruction` codec is non-injective on `Custom`.** `Instruction::Write`
  for `Custom{module, action, data}` emits `module` **raw** (`execution.rs:2554`), but
  `Instruction::read` dispatches on that first byte (`0→System, 1→Actor, 3→Library`, else
  `Custom`, `:3348`). So `Custom{module: 0, action: 0, data: <20 bytes>}` encodes to the **same
  bytes** as `System(CreateAccount{account})`, and `decode(encode(Custom{module:0,..}))`
  returns `System(...)` — not identity. The OLD serde-CBOR map was injective here (field-name
  keyed), so switching is a **regression** on the exact axis this work targets; it is also
  **untested** (the existing round-trip only uses `module: 5`). **Resolution (decide in the
  plan):** EITHER (a) make the codec injective — `Custom::write` pins the category byte
  (`TX_CATEGORY_CUSTOM = 2`) and stores `module` in the body, `Read` dispatches on `2` →
  `Custom` (verify the blast radius first: `Instruction` reaches consensus only via
  `Transaction` inside `Block.transactions`, so this is contained in the same flag-day **iff**
  nothing else encodes `Instruction` outside a tx — confirm by grep); OR (b) keep the codec but
  **reject `Custom{module ∈ {0,1,3}}` at admission/construction** and **scope §4.1's invariant
  to admission-valid txs**. Either way: add round-trip tests over `module ∈ {0,1,2,3}`. (a) is
  the truly-canonical fix; (b) is lower-blast-radius. Default to (a) if the grep shows
  `Instruction` is tx-only.

- **R2 (HIGH) — `Constraints` bool fields are non-strict.** `Constraints` (`entitlement.rs:262`,
  carried by `EntitlementGrant/Delegate/CreateRole`) writes `(self.delegatable as u8)` and reads
  `u8::read()? != 0` (`:326/367`), so byte `0x02` decodes `true` and re-encodes `0x01` —
  `encode∘decode != id`, a malleability vector reachable from user txs. Commonware's own
  `bool::read` rejects non-0/1; the manual `!= 0` is the hole. **Fix:** strict bool decode.

- **R3 (HIGH, ops/liveness) — genesis `chain_id` flag-day trap.** `chain_id` defaults to `None`
  everywhere except the local-setup path. If activation ships the `tx.chain_id != node_chain_id`
  admission check while genesis stays `None` (and `None` is treated as a concrete value), **every
  tx is rejected → chain halt**. **Resolution:** promote "update genesis `chain_id` to the pinned
  devnet value" to an **explicit, first, blocking step** of the activation runbook (§7); in
  non-test config, `None` ⇒ **hard startup error** (never silent accept-any, or replay protection
  is void).

- **R4 (doc, MUST for wallet/SDK byte-parity) — §4.1's specifics are actively misleading.** The
  §0 blanket "read CBOR as commonware-codec" does NOT neutralize §4.1's concrete rules, which a
  wallet/SDK implementer follows literally. §4.1's "definite-length CBOR array",
  "minimal-length integers", "Option = CBOR null" are all WRONG for commonware-codec, which is:
  a **flat concatenation** (no array wrapper); **mixed integers** — minimal **varint (`UInt`)**
  for the bare `u64` (chain_id/nonce/gas) but **fixed-width big-endian** for `u128` amounts and
  `Option<u64>` payloads; **`Option` = a `bool`(0/1) tag + value** (never "null"); byte strings =
  **varint length + bytes**. §4.1 below is corrected accordingly, and the **TV fixture (§4.5) is
  the byte authority**. The moot "evaluate ciborium vs hand-rolled" open items (§4.1 / §11) are
  struck — the primitive is decided (commonware-codec).

- **R5 (test) — `EncodeSize` exactness.** The hand-written `Transaction::EncodeSize` (17 fields)
  must exactly equal the `Write` byte length or commonware-codec mis-sizes buffers. Add an
  `assert_eq!(tx.encode_size(), tx.encode().len())` test.

**Verified solid by round-3 (no action):** bounded-`Vec` decode rejects an out-of-range length
**before** allocation (no decode-bomb); `UInt` is strict-minimal; the reused
`Instruction::EncodeSize` matches its `Write`; all tx-reachable leaf types are deterministic
(CBSS fixed-size; `ActorManifest` uses a sorted `BTreeMap`, not `HashMap`; no floats); the
deferred-tx preimage migration is coherent and the devnet reset is **genuinely required** (not
merely convenient — pre-flag-day `origin_tx_hash` values would otherwise fail the parent-receipt
check).

---

## 0d. Round-4 exhaustive-audit fixes (2026-06-16, Marshal run #189)

Round 4 went EXHAUSTIVE where round 3 sampled — it enumerated every tx-reachable enum and bool.
Net: the canonical invariant is **achievable with a handful of enumerable point-fixes plus one
semantic rule** (not a systemic codec problem). New MUST-FIX beyond R1/R2:

- **R6 (HIGH) — a SECOND non-strict bool R2 missed.** `SystemInstruction::RunnerUpdateDelegationConfig.accept_delegation`
  writes `if {1u8} else {0u8}` (`execution.rs:2058`) and reads `u8::read()? != 0` (`:2845`) —
  opcode 119, user-submittable; `0x02` → `true` → re-encodes `0x01`. R2 only fixed `Constraints`
  in `entitlement.rs`; this `execution.rs` site is identical. **Fix:** same strict
  `match {0,1,_=>Err}`. (Note: ~6 sibling bools in the same impl ARE strict — this is an
  inconsistent-copy hazard; the test in R10 must catch any others mechanically.)

- **R7 (HIGH) — `additional_signers` has no canonical order or uniqueness.** `verify()`
  (`execution.rs:346`) iterates `additional_signers` in stored order, checking each `(addr,sig)`
  recovers to `addr`; it enforces **neither order nor dedup**, and `all_signer_addresses()`
  (`:100`) is order-dependent. So the same signer SET in two orders — or padded with duplicate
  valid entries — yields **distinct `tx_hash`/`signing_hash`** for one logical authorization =
  tx-identity malleability. **This lives in `verify()`, not the codec**, which is why the
  codec-focused rounds 1–3 structurally could not find it. **Fix:** require `additional_signers`
  to be **sorted by address with no duplicates** (reject otherwise at `verify()`/admission), and
  bound by `MAX_ADDITIONAL_SIGNERS`.

- **R8 (MEDIUM) — `SessionVoucher` signature pad/truncate is non-injective.** `session.rs:156`
  pads/truncates `signature` to `VOUCHER_SIGNATURE_LEN` on write and always reads that length, so
  a short/long-padded voucher normalizes on decode (`encode∘decode != id`). Tx-reachable via
  `SessionSettle` (op 54) / `SessionSlash` (op 57). **Fix:** reject `signature.len() != VOUCHER_SIGNATURE_LEN`
  at decode/construction.

- **R9 (MEDIUM, plan) — `METADATA_CFG` lower bound.** The `metadata` `RangeCfg` upper bound MUST
  be **≥ the max CIP-29 envelope (~6.4 KB)**, or system event-fire **deferred** txs fail to
  decode. Pin it precisely (not "open").

- **R10 (test mandate) — exhaustive round-trip.** The conformance round-trip test must iterate
  **every `SystemInstruction` opcode and every tx-reachable nested enum** (not just `Custom`
  modules) — the only mechanical guarantee that no further `!= 0`/catch-all site survives.

- **(LOW)** CIP-29 `EmitOrigin::from_metadata_bytes` ignores trailing bytes (`:563`) — defense
  in depth only (CIP-29 rides deferred/system txs the node builds; not a tx-canonical break).

**Confirmed by round-4 (no action):** R1 blast radius is **CONTAINED** — `Instruction` reaches
consensus ONLY via `Transaction` in `Block.transactions` (receipts store `tx_type:u8`, not the
full `Instruction`), so **plan Task 2b path (a) — change the `Custom` encoding — is safe** in the
tx flag-day. Also: because F1 makes `tx_hash`/`digest` **signature-independent**, neither `v`-
nor s-malleability of `EthSignature` can fork tx identity (the one axis where the design fully
holds). Exhaustively-checked-clean enums: all `SystemInstruction`/`ActorInstruction`/`LibraryInstruction`
sub-dispatch (`_ => Err(InvalidEnum)`), `Scope`/`Action`, all `cbss` enums, `SessionAsset`,
`Submission`/`UpdatesFilter`, the leaf primitives `Address`/`EthSignature`/`Digest`.

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
- **Encoding rules (commonware-codec; corrected per R4 — NOT CBOR):**
  - **Flat concatenation** of the transaction fields in the **frozen order** of §5.1 — there
    is **no array wrapper** (commonware-codec writes fields back-to-back).
  - **Mixed integer encodings (match the existing impls exactly):** bare `u64` fields
    (`chain_id`, `nonce`, gas/fee fields) use minimal **varint `UInt`**; `u128` amounts and
    `Option<u64>` payloads use **fixed-width big-endian**; collection lengths use varint.
  - `Option<T>` = a **`bool` (0x00/0x01) tag followed by the value if present** — never CBOR
    "null". `Vec<T>` / byte strings = **varint length prefix + elements/bytes**.
  - No floating point; no indefinite-length items; every integer/`bool` has a unique strict
    form (`UInt` rejects non-minimal; `bool` must reject bytes ∉ {0,1} — see R2).
  - **The TV fixture (§4.5) is the authoritative byte reference;** clients reproduce it, not
    a prose reading of these bullets.
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
- **Primitive layer (decided, R4):** the existing `commonware-codec` `Write`/`Read` — no new
  CBOR layer, no `ciborium`. Reuse `Instruction`'s impls and write the `Transaction` field
  encoding in the same idiom as `Block::write`.

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
- ~~Choose the CBOR primitive layer~~ — DECIDED (R4): reuse `commonware-codec` (not CBOR).
- Final home/path of the shared TV fixture readable by both node and wallet.
- Exact new error-code slug/number for `chain_id` mismatch (follow the four-part error format,
  COW-386).
