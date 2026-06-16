# tx-canonical Follow-on Plans

> Follow-ons to node draft PR #742 (canonical tx encoding). Three independent workstreams.
> Plan A is implementable NOW (no flag-day dependency). Plans B/C have stated dependencies.
> Source: `refs/analysis/2026-06-16_tx-canonical-encoding-design.md` (§0c/§0d audit findings),
> `refs/analysis/2026-06-16_consensus-codec-hygiene-audit.md` (round-6, B6/B7).

---

# Plan A — Message + TransactionReceipt codec hygiene (node, implementable now)

**Goal:** make `Message::read` (state-root-hashed via `StateValue::MailboxMessage`) and
`TransactionReceipt::Read` strict/injective, closing the same codec-hygiene class the tx work
fixed (B7). Independent of the flag-day. Consensus-relevant for `Message` (state_root); `Receipt`
Read is off the consensus-hash path (receipt_root rebuilds from execution, never decode-then-rehash)
so it's a robustness/RPC fix — lower priority, same pattern.

> **For agentic workers:** use superpowers:subagent-driven-development; checkbox steps.

**Tech:** Rust, `commonware_codec`. Files: `node/types/src/execution.rs` (`Message`, `MessageType`),
`node/storage/src/types.rs` (`TransactionReceipt`).

## Task A1: strict `MessageType` decode (R-class, state_root)
**Files:** `node/types/src/execution.rs` (`MessageType::from_u8` ~:4639; `Message::read` ~:4789)
- [ ] **Step 1 (TDD):** test that a `Message` whose `msg_type` byte is out-of-range (e.g. `5`) is REJECTED on decode (not silently mapped to `Regular`). Build a `Message`, encode, flip the msg_type byte to 5, assert `Message::read(...)` errors.
- [ ] **Step 2:** A strict `MessageType::try_from_u8(v) -> Option<Self>` may already exist (there's a `try_from_u8` at ~:4683 — confirm which enum it's on; if it's `MessagePriority`, add the same for `MessageType`). In `Message::read` (~:4789) replace `MessageType::from_u8(u8::read(reader)?)` with `MessageType::try_from_u8(u8::read(reader)?).ok_or(Error::InvalidEnum(...))?`. Keep `from_u8` if other (non-consensus) callers use it, or migrate them. Run, green, commit `fix(types): strict MessageType decode in Message::read (B7, state-root)`.

## Task A2: strict `has_origin` tag in `Message::read` (R-class, state_root)
**Files:** `node/types/src/execution.rs` (`Message::read` ~:4781)
- [ ] **Step 1 (TDD):** test that `has_origin` byte `2` is rejected (currently `== 1 ? Some : None` silently maps 2→None).
- [ ] **Step 2:** replace `let has_origin = u8::read(reader)?; ... if has_origin == 1` with strict `match u8::read(reader)? { 0 => None-branch, 1 => Some-branch, _ => return Err(Error::InvalidEnum(..)) }`. Run, green, commit `fix(types): strict Option tag for Message.origin (B7)`.

## Task A3: Message trailing-`has_remaining()` tail (R-class — needs a decision)
**Files:** `node/types/src/execution.rs` (`Message::read` ~:4788, see the existing comment ~:4761)
The `(msg_type,timestamp,retry_count,max_retries,trace_id)` tail is gated on `has_remaining()` for
backward-compat with pre-#111 encodings — so a short and a long encoding both decode (non-injective).
- [ ] **Decision (escalate to human):** EITHER (a) introduce a `Message` format version byte (like `Account`/`Timer`/`StateValue` V2 use a discriminant) so the tail is version-gated not `has_remaining`-gated — cleaner but a `Message` wire change (state_root, needs flag-day coordination with PR #742's reset); OR (b) document it as an accepted limitation since `Message::write` always emits the full tail post-upgrade (honest-node encodings are uniform) and the over-read is already mitigated by carrying priority/expires in the `StateValue` V2 discriminant (see the :4761 comment). Recommend (a) folded into the PR #742 flag-day (since both reset Message/mailbox state), or (b) with a documented invariant test. **Do NOT just delete the `has_remaining` branch — that breaks decoding any pre-#111 stored Message until the reset.**

## Task A4: TransactionReceipt::Read strictness (robustness, NOT receipt_root)
**Files:** `node/storage/src/types.rs` (`bloom` read ~:794 `0 => None`; trailing `has_remaining()` ~:903-940)
- [ ] **Note (scope):** receipt_root is `Write`-only canonical (replay rebuilds receipts from execution; never decodes-then-rehashes — verified round-4/6). So these are RPC/storage round-trip robustness, NOT root malleability. Lower priority; do A1–A3 first.
- [ ] **Step 1:** strict `bloom` tag — `match u8::read()? { 0 => None, 1 => Some(read 256B), _ => Err(InvalidEnum) }` (currently `_ => None` buckets unknown tags). Test rejects tag 2.
- [ ] **Step 2:** the 5× chained trailing `has_remaining()` fields — same decision as A3 (version-gate vs documented-limitation). Since this is off-consensus-path, documenting + an invariant test is acceptable. Commit `fix(storage): strict TransactionReceipt bloom tag + document trailing-optional (B7)`.

## A: gate
`cargo test --workspace` green; the storage state-root invariants (`prop_merkle_root_consistent_across_phases` etc.) still pass (A1/A2 change `Message` decode strictness — round-trip of honest encodings is unchanged, only malformed bytes now rejected). Run Marshal — tier high (state_root for A1-A3); verdict needs_human (Message wire/state change) if A3 path (a) is taken.

---

# Plan B — Wallet + SDK byte-parity (cross-repo)

**Goal:** the wallet (JS, separate `wallet/` repo) and the Python SDK reproduce the canonical
commonware-codec transaction encoding byte-for-byte, verified against the shared fixture.

**Dependency:** PR #742 merged (or at least the encoding frozen) + `refs/common/tx-canonical-vectors.json`
(the byte contract — TV1 unsigned hex, TV1 signing hash, TV2 signed hex, fixed key, fields).

**Scope (not yet bite-sized — needs the wallet repo checked out + its current tx-encoding code read first):**
- [ ] **B1 (wallet, JS):** locate the wallet's current tx encoder/signer (`window.cowboy` provider; it currently must match node's OLD serde-CBOR — per `wallet/CLAUDE.md` "tx encoding must stay byte-compatible with node"). Replace it with the canonical commonware-codec encoding: ordered fields (frozen order from the design §5.1), `UInt` varint for the u64s, fixed-BE for u128/Option<u64>, bool-tag Options, length-prefixed Vecs. The signing hash = keccak256(encoding with sigs zeroed). chain_id from the connected node.
- [ ] **B2 (wallet parity test):** a test that loads `tx-canonical-vectors.json` and asserts the wallet encoder reproduces `tv1_unsigned_hex`, `tv1_signing_hash`, and (signing the fixed key) `tv2_signed_hex`. A mismatch is a build failure.
- [ ] **B3 (SDK, Python):** same for any client-side tx construction in the PVM/SDK (`pvm/Lib/.../cowboy_sdk`), against the same fixture. (May be minimal if the SDK doesn't build/sign txs client-side — check first.)
- [ ] **B4:** activation — these land BEFORE the flag-day enforces the new encoding on a live-client env (else wallet-signed txs are rejected). Sequence with PR #742's activation.

> This is a separate spec→plan cycle once the wallet repo is in scope. Estimate after reading the wallet's current encoder.

---

# Plan C — Whitepaper rewrite (cowboy docs)

**Goal:** make WP §2 + Appendix A + the standalone line-198 MUST describe the actual canonical
encoding (commonware-codec, not the stale flat-Ethereum-CBOR description).

**Dependency:** PR #742 (the canonical form is now implemented + frozen in vectors).

**Files:** `cowboy/docs/whitepaper/cowboy-technical-whitepaper.md`.

- [ ] **C1 — §2 (lines ~461-493):** rewrite the flat `[chain_id, nonce, to, value, …, payload, signature]`
  13-element CBOR-array description to the **instruction-tx commonware-codec** form: the frozen field
  array (design §5.1 — note `to`/`value` live inside the typed `Instruction`, not top-level), the
  signing hash = `keccak256(canonical(tx with signatures zeroed))`, `chain_id` replay protection,
  `access_list` as optional/reserved.
- [ ] **C2 — Appendix A:** replace the flat-model test vectors with TV1/TV2 from
  `refs/common/tx-canonical-vectors.json` (the now-normative byte vectors). Make Appendix A normative.
- [ ] **C3 — line 198 (standalone MUST "all trust-boundary data MUST use canonical CBOR, RFC 8949"):**
  this is FALSE codebase-wide (chain types use commonware-codec; CIP-6 §4.2.3 / CIP-11 §4.2.1 / RAS
  serde / CBSS ciborium). Rewrite it **principledly**: each trust boundary MUST use its declared
  canonical encoding (commonware-codec binary for chain consensus types per §2/Appendix A; the CIP-6
  §4.2.3 profile for SDK CBOR; CIP-11 §4.2.1 for connectivity). Do NOT leave a tx-only patch that
  keeps line 198 self-contradictory.
- [ ] **C4:** if the diff touches `docs/cips/**` or `docs/whitepaper/**`, run Marshal flow B
  (conformance) — amending the whitepaper is the highest tier; ensure the CIP/WP requirements it
  changes are covered.

---

## Sequencing across the three
1. **Plan A** can start immediately (node-local; A1/A2 clean; A3/A4 need the version-vs-document decision).
2. **Plans B + C** depend on PR #742 landing (encoding frozen). C is doc-only; B is cross-repo code +
   must precede the flag-day on any live-client environment.
3. All three feed the **same activation/flag-day** as PR #742 (B especially — wallet must emit the new
   format before enforcement reaches it).
