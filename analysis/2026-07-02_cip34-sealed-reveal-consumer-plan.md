# CIP-34 v1 SEALED-bid reveal consumer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Permissionlessly reveal a CIP-34 sealed auction after `reveal_height` — verify the tlock release σ, decrypt the sealed bids on-chain, select the best valid `SettlementBundle` by MinReceive surplus, and apply it via the settle path — plus a permissionless cancel/refund fallback after `AUCTION_GRACE`.

**Architecture:** New consensus system instructions `RevealAuction`/`CancelAuction` (opcodes 156/157) on top of #888's auction lifecycle, extended so the auction pins a CBSS `scope`. The reveal verifies σ against the committee MPK (one pairing), ports cbss-crypto's `ibe_decrypt` on-chain (pairing + HKDF-SHA256 + AES-256-GCM), ranks decrypted bundles by `conservation_surplus()`, and applies the winner through a validate/apply split of `settle_bundle`.

**Tech Stack:** Rust; `blstrs` (pairing, already in execution); new execution deps `hkdf`,`sha2`,`aes-gcm`; `cowboy-protocol-codec` (new rev); node `cowboy-execution`.

**Spec:** `refs/analysis/2026-07-02_cip34-sealed-reveal-consumer-design.md`.

---

## File structure

**cowboy-protocol** (new rev after `bf56c001`):
- `crates/cowboy-protocol-codec/src/settlement.rs` — add `scope: ReleaseKeyRef` to `OpenAuctionArgs`; add `RevealAuctionArgs { request_id, sigma: G1Bytes }`, `CancelAuctionArgs { request_id }`.
- `.../src/instruction.rs` (or where `SystemInstruction`/`sub_type()` lives) — `RevealAuction=156`, `CancelAuction=157` variants + opcode-uniqueness.

**node** (branch stacked on `feat/cip-34-sealed-auction-handlers` = #888):
- `types/Cargo.toml` / `execution/Cargo.toml` — bump codec rev; add `hkdf`,`sha2`,`aes-gcm` to execution.
- `execution/src/tlock_ibe.rs` (new) — on-chain `ibe_decrypt` port + envelope decode, mirrored from cbss-crypto with a cross-impl vector.
- `execution/src/settlement.rs` — `Auction.scope`; `open_auction` registers tlock; split `settle_bundle` → `validate_bundle` (pure surplus) + `apply_bundle`; `handle_reveal_auction`; `handle_cancel_auction`; new keys/events.
- `execution/src/execution/system_instruction.rs` — dispatch 156/157.
- `execution/src/error.rs` + `structured_error_map.rs` — new auction error codes.

---

## PR 0 — cowboy-protocol codec (prerequisite; tag a new rev)

> **Aligned to upstream #14 (`dadd933`):** `RevealAuction { request_id }` (opcode 156) is ALREADY merged on cowboy-protocol `main` — do NOT redefine it or add a `sigma` field (the node handler combines σ on-chain from the stored partials). This task adds only the two still-missing pieces.

### Task 1: codec — OpenAuctionArgs.scope + CancelAuction (157)

**Files:** `crates/cowboy-protocol-codec/src/settlement.rs`, `.../instruction.rs`. Base branch: `main` (at `dadd933`).

- [ ] **Step 1: failing test** — in the codec settlement tests:
```rust
#[test]
fn open_auction_scope_and_cancel_round_trip() {
    let o = OpenAuctionArgs { reveal_height: 200, grant: sample_grant(), grant_sig: sample_sig(),
                              scope: ReleaseKeyRef::Account(Address::from([1u8;20])) };
    assert_eq!(OpenAuctionArgs::decode(&mut o.encode().as_ref()).unwrap(), o);
    let c = CancelAuctionArgs { request_id: [9u8;32] };
    assert_eq!(CancelAuctionArgs::decode(&mut c.encode().as_ref()).unwrap(), c);
}
```
(use whatever the codec's existing test helpers are for grant/sig; the point is round-trip.)
- [ ] **Step 2: run → FAIL** (field/type not defined).
- [ ] **Step 3: implement.** Add `pub scope: ReleaseKeyRef` to `OpenAuctionArgs`, appended LAST in its `Write`/`Read`/`EncodeSize` (clean additive layout after `grant_sig`). Add:
```rust
pub struct CancelAuctionArgs { pub request_id: [u8;32] }
```
with `Write`/`Read`/`EncodeSize` mirroring the sibling `RevealAuctionArgs` (a single `[u8;32]` field — copy its impl exactly). Import `ReleaseKeyRef` from the cbss codec module if not already in scope (it is used by the tlock args already).
- [ ] **Step 4: add SystemInstruction variant** `CancelAuction(CancelAuctionArgs) = 157` (next-free after `SYS_REVEAL_AUCTION = 156`) in the enum + `sub_type()` (`SYS_CANCEL_AUCTION = 157`) + `write`/`read` dispatch + `encode_size`; the `#[deny(unreachable_patterns)]` uniqueness guard covers it (add an explicit uniqueness-test line if the file has one, mirroring 156).
- [ ] **Step 5: run → PASS**; `cargo test -p cowboy-protocol-codec`.
- [ ] **Step 6: commit + push + note rev** — commit `feat(codec): CIP-34 OpenAuction.scope + CancelAuction (157)`, push to a branch, and record the new rev SHA (call it `<REVEAL_REV>`) for the node bump (node points at a git rev, so it must be pushed/fetchable — same as #14/#13).

> NOTE: `OpenAuctionArgs.scope` is an additive field on a type #888 already uses — Task 3 updates #888's `open_auction` handler + any node-side `OpenAuctionArgs` construction/tests to supply `scope`.

---

## PR A — node (stacked on #888)

### Task 2: bump codec rev + execution crypto deps + dispatch skeleton

**Files:** `types/Cargo.toml`, `execution/Cargo.toml`, `execution/src/execution/system_instruction.rs`

- [ ] **Step 1:** bump `cowboy-protocol-{types,codec}` rev to `<REVEAL_REV>` in the node workspace `Cargo.toml`; `cargo update -p cowboy-protocol-codec -p cowboy-protocol-types`.
- [ ] **Step 2:** add to `execution/Cargo.toml`: `hkdf = "0.12"`, `sha2 = "0.10"`, `aes-gcm = "0.10"` (match cbss-crypto's versions — check `cbss/crates/cbss-crypto/Cargo.toml` and pin the SAME majors so the AEAD/HKDF outputs are byte-identical).
- [ ] **Step 3:** in `system_instruction.rs`, add match arms dispatching `SystemInstruction::RevealAuction(args)` → `handle_reveal_auction(...)` and `CancelAuction(args)` → `handle_cancel_auction(...)` (stubs returning `Ok(None)` for now; real handlers in Tasks 6-7). Pass `block_height` + `state.chain_id` as the sibling settlement arms do.
- [ ] **Step 4:** `cargo build -p cowboy-execution` → clean.
- [ ] **Step 5: commit** `build(node): bump codec to <REVEAL_REV>; add aead/hkdf deps; dispatch RevealAuction/CancelAuction`.

### Task 3: #888 extension — Auction.scope + open_auction registers the tlock request

**Files:** `execution/src/settlement.rs`

- [ ] **Step 1: failing test** — extend the open_auction test: after `open_auction` with a `scope`, assert (a) `read_auction(request_id).scope == scope`, and (b) a `TlockRequest` record exists for `(scope, request_id, reveal_height)` (reuse the CIP-24 helpers `tlock_request_key`/`tlock_id` — now `pub` from #892's Task 7; if not accessible, call the register handler and read it back):
```rust
let a = read_auction(&store, &rid).await.unwrap().unwrap();
assert_eq!(a.scope, scope);
assert!(load_json::<_, TlockRequest>(&store, &tlock_request_key(&tlock_id(&scope,&rid,reveal_height))).await.unwrap().is_some());
```
- [ ] **Step 2: run → FAIL.**
- [ ] **Step 3: implement.** In `open_auction`: read `args.scope`; write it into the `Auction` record (`auction_key` value now `reveal_height(8) ‖ coordinator(20) ‖ scope(canonical)`; update `Auction` struct + `read_auction`/encode). Then call the CIP-24 §3.4.6 register path — `self.handle_cbss_register_tlock_release(store, &RegisterTlockReleaseArgs { scope: args.scope.clone(), tag: request_id.to_vec(), target_height: reveal_height }, gas_meters, block_height)` — mapping its errors into auction errors (a `TlockLeadTooShort` means `reveal_height` is too near; surface as an open_auction rejection). Reuse its guards (scope resolves to a committee, lead, cap, dedup).
- [ ] **Step 4: run → PASS**; `cargo test -p cowboy-execution open_auction`.
- [ ] **Step 5: commit** `feat(cip-34): open_auction pins CBSS scope + registers the tlock release request`.

> Verify against the codec: `OpenAuctionArgs.scope` (Task 1) must be populated by any node-side test constructing an `OpenAuctionArgs` (#888's tests) — update them to pass a scope.

### Task 4: on-chain tlock IBE decrypt (port of cbss-crypto), with cross-impl vector

**Files:** `execution/src/tlock_ibe.rs` (new), `execution/src/lib.rs` (mod)

- [ ] **Step 1: failing cross-impl vector test.** First emit a canonical envelope from cbss-crypto: in cbss-crypto, `ibe_encrypt` a known plaintext to `identity = tlock_identity(b"cip34-request-id", 200)` with a fixed `r` (or capture the envelope bytes + the decrypting σ). Record `{envelope_hex, sigma_hex, aad_hex, plaintext}`. Then in `tlock_ibe.rs` tests:
```rust
#[test]
fn ibe_decrypt_matches_cbss_vector() {
    let sigma = g1_from_bytes_hex("<sigma_hex>");
    let env = decode_wrapped_dek_hex("<envelope_hex>");
    let pt = tlock_ibe_decrypt(&sigma, &env, &hex!("<aad_hex>")).unwrap();
    assert_eq!(pt, hex!("<plaintext_hex>"));
}
```
- [ ] **Step 2: run → FAIL.**
- [ ] **Step 3: implement `tlock_ibe_decrypt`** mirroring `cbss/crates/cbss-crypto/src/ibe.rs::ibe_decrypt` + `envelope.rs::WrappedDek` byte layout EXACTLY:
```rust
// env: version(1)=WRAPPED_DEK_FORMAT_VERSION(2), ciphertext, nonce[12], ephemeral_u[96], aad
pub fn tlock_ibe_decrypt(sigma: &G1Projective, env: &WrappedDek, aad: &[u8]) -> Result<Vec<u8>, ExecutionError> {
    reject_g1_identity(sigma)?;
    let u = decode_nonidentity_g2(&env.ephemeral_u)?;
    let expected_aad = [aad, &env.ephemeral_u].concat();   // extend_aad_with_u
    if env.aad != expected_aad { return Err(ExecutionError::InvalidData); }
    let gt = pairing(&G1Affine::from(sigma), &G2Affine::from(&u)); // e(σ, U) = e(I,MPK)^r
    let k = hkdf_sha256(&gt_to_compressed(&gt), b"cbss/tlock/v1", &env.aad, 32); // salt="cbss/tlock/v1"
    aes256gcm_decrypt(&k, &env.nonce, &env.ciphertext, &env.aad).map_err(|_| ExecutionError::CiphertextCorrupted)
}
```
Use the SAME HKDF salt/info discipline as §3.4.3 (salt = `b"cbss/tlock/v1"`, info = `"cbss/tlock/v1" || aad`, L=32) and `serialize(Gt)` = blstrs `Gt::to_compressed()` (288 bytes) — mirror cbss-crypto exactly or the key differs. Port `WrappedDek` decode (or reuse the codec's `WrappedDek` if the node already re-exports it — check `types/src/cbss.rs`).
- [ ] **Step 4: run → PASS** (byte-identical to cbss-crypto).
- [ ] **Step 5: commit** `feat(execution): on-chain tlock IBE decrypt (port of cbss-crypto, cross-impl vector)`.

### Task 5: split settle_bundle into validate (pure surplus) + apply

**Files:** `execution/src/settlement.rs`

- [ ] **Step 1: failing test** — assert a pure `validate_bundle` returns the surplus WITHOUT mutating balances, and `apply_bundle` mutates:
```rust
#[test] async fn validate_bundle_is_pure_then_apply_commits() { /* seed; validate → surplus, balances unchanged; apply → balances change */ }
```
- [ ] **Step 2: run → FAIL.**
- [ ] **Step 3: refactor.** Extract from the current `settle_bundle` (settlement.rs:430): `validate_bundle(store, bundle, chain_id, block_height) -> Result<(Vec<TokenDiff> /*surplus*/, Vec<((Address,[u8;32]),i128)> /*deltas*/, Vec<(Address,u64)> /*nonces to consume*/), ExecutionError>` doing conservation + all auth checks + delta computation but NO writes; and `apply_bundle(store, deltas, nonces, block_height)` doing the writes (balance updates + nonce-consume). Redefine `settle_bundle = validate_bundle then apply_bundle` so existing `IntentSettle` behavior is byte-identical. Keep the compute-then-commit guarantee.
- [ ] **Step 4: run → PASS**; re-run existing settle tests (`cargo test -p cowboy-execution settle`) — all still green (behavior preserved).
- [ ] **Step 5: commit** `refactor(cip-34): split settle_bundle into pure validate_bundle + apply_bundle`.

### Task 6: handle_reveal_auction

**Files:** `execution/src/settlement.rs`, `error.rs`, `structured_error_map.rs`

- [ ] **Step 1: failing tests** (mirror #888's tlock fixtures — `seed_tlock_store`/`tlock_committee_fixture`; post ≥t partials via `handle_cbss_submit_tlock_release` as the tlock tests do; encrypt bids with the Task-4 envelope):
  - t partials on-chain + 2 valid bids of different surplus → higher-surplus bundle applied (balances moved), `cip34.AuctionRevealed` emitted, auction closed, second reveal → `AuctionNotOpen`;
  - `head < reveal_height` → `AuctionRevealTooEarly`;
  - `< t` partials posted → `RevealNotEnoughPartials`, auction untouched;
  - an undecryptable bid is skipped, a valid one still wins;
  - no valid bids → `cip34.AuctionRevealedEmpty`, no settlement.
- [ ] **Step 2: run → FAIL.**
- [ ] **Step 3: implement `handle_reveal_auction(store, args, gas, block_height, chain_id)`** — `args: RevealAuctionArgs { request_id }` (NO sigma; option B, aligned to upstream #14):
  1. `let auction = read_auction(store, &args.request_id).await?.ok_or(AuctionNotOpen)?;`
  2. `if block_height < auction.reveal_height { return Err(AuctionRevealTooEarly) }`
  3. `let i_tlock = compute_tlock_identity(&args.request_id, auction.reveal_height);`
  4. **Combine σ on-chain from stored partials** (no σ carried, no MPK-verify — partials were pairing-verified at submit): `let view = load_current_release_key_view(store, &auction.scope).await?;` read `TlockPartialSet` at `tlock_partials_key(&tlock_id(&auction.scope, &args.request_id, auction.reveal_height))`; map each entry's `proxy_id` → 1-based index via `view.committee`; if `entries.len() < view.threshold` → `RevealNotEnoughPartials`; `let sigma = combine_partials(&pairs, view.threshold as usize)?;` (Task 4b: mirror cbss-crypto `combine_partials`, Lagrange in G1).
  5. `let bidders = read_auction_bidders(store, &args.request_id).await?;` for each solver read `sealed_bid_key`, decode the `WrappedDek` envelope, `tlock_ibe_decrypt(&sigma, &env, &aad)` where `aad = base_aad(request_id, reveal_height)` (the identity's base aad — pin the exact bytes to match the encryptor). On error → skip (log).
  6. Decode each plaintext as `SettlementBundle` (skip on decode error). For each, `validate_bundle(...)` (Task 5, pure) → if Ok, keep `(solver, surplus, deltas, nonces)`.
  7. Select best: max total surplus (sum the `surplus` TokenDiffs' value per the MinReceive rule); tie-break lowest solver address. If none → emit `cip34.AuctionRevealedEmpty`, delete auction+bids+bidder-list, `Ok`.
  8. `apply_bundle(store, winner.deltas, winner.nonces, block_height)`; delete auction + all bids + bidder-list (prevent re-reveal); emit `cip34.AuctionRevealed { request_id, winner_solver, surplus }`.
  - charge gas (base + per-bid pairing/AEAD; price like a bounded loop over ≤256 bids).
- [ ] **Step 4: add errors** `AuctionRevealTooEarly`, `RevealNotEnoughPartials`, `AuctionNotOpen` to `error.rs` + `structured_error_map.rs` (next-free after #888's E1751).
- [ ] **Task 4b (fold into Task 4): on-chain `combine_partials`** — port cbss-crypto `threshold::combine_partials(&[(ProxyIndex, G1Projective)], threshold) -> Result<G1Projective>` into `execution/src/tlock_ibe.rs` (Lagrange interpolation at x=0 in G1; reject dup/zero indices). Cross-check against cbss-crypto with a shared vector (a fixture polynomial's t partials combine to `MSK·I_tlock`, equal to `secret · I_tlock`).
- [ ] **Step 5: run → PASS.**
- [ ] **Step 6: commit** `feat(cip-34): handle_reveal_auction (combine σ on-chain, decrypt bids, settle best by surplus)`.

### Task 7: handle_cancel_auction

**Files:** `execution/src/settlement.rs`, `error.rs`, `structured_error_map.rs`

- [ ] **Step 1: failing tests:** before `reveal_height+AUCTION_GRACE` → `AuctionCancelTooEarly`; after grace on an open auction → auction+bids+bidder-list cleared, `cip34.AuctionCancelled` emitted; cancel after a successful reveal → `AuctionNotOpen`.
- [ ] **Step 2: run → FAIL.**
- [ ] **Step 3: implement `handle_cancel_auction(store, args, gas, block_height)`:** `read_auction` → `AuctionNotOpen` if missing; `if block_height < auction.reveal_height + AUCTION_GRACE { return Err(AuctionCancelTooEarly) }`; delete auction + bids (enumerate via `read_auction_bidders`) + bidder-list; emit `cip34.AuctionCancelled { request_id }`. (Originator ledger balance was never moved by the auction, so no balance refund is needed — this releases the auction so the intent can settle OPEN or be withdrawn.) Add `AuctionCancelTooEarly` error.
- [ ] **Step 4: run → PASS.**
- [ ] **Step 5: commit** `feat(cip-34): handle_cancel_auction (permissionless liveness fallback after AUCTION_GRACE)`.

### Task 8: end-to-end test

**Files:** `execution/src/settlement.rs` tests

- [ ] **Step 1: e2e test** — seed a committee (`seed_tlock_store`); `open_auction(scope, request_id, reveal_height)` (asserts tlock request registered); `submit_sealed_bid` for 2 solvers with bids encrypted (Task-4 envelope) to `identity=request_id`,`reveal_height`, containing valid `SettlementBundle`s of different surplus; combine σ from the fixture polynomial (like `tlock_partial_for` + Lagrange, or directly `MSK·I_tlock` from the fixture master secret); advance to `reveal_height`; `handle_reveal_auction(request_id, σ)`; assert the higher-surplus bundle's ledger effects applied + `AuctionRevealed`. Confirms open→bid→σ→reveal→settle closes.
- [ ] **Step 2: run → PASS.**
- [ ] **Step 3: commit** `test(cip-34): sealed auction open→bid→reveal→settle e2e`.

---

## Self-review (author checklist — completed)

- **Spec coverage:** σ-carried-tx + pairing verify (T6.4); on-chain decrypt (T4 + T6.5-6); scope pinned at open + tlock register (T2 codec + T3); winner by MinReceive surplus + tie-break (T6.7); apply via settle path (T5 + T6.8); cancel after grace (T7); opcodes 156/157 + errors (T1/T2/T6/T7); new AEAD deps + cross-impl vector (T2/T4); e2e (T8). Non-goals (dispute/slashing, degrade-to-OPEN, encrypted-intent) correctly absent. ✅
- **Placeholder scan:** the heavy boilerplate (codec Write/Read impls T1, exact WrappedDek byte offsets T4, settle internals T5) is expressed as "mirror `<named file>` exactly" — deliberate must-read pointers (the referenced code is the source of truth), not TBDs; every novel/risky unit (ibe decrypt port + vector, σ verify, validate/apply split, reveal selection) has concrete code/steps. The `<REVEAL_REV>` and vector hex are produced by a step (T1 commit / T4 Step 1), not left blank.
- **Type consistency:** `compute_tlock_identity(&[u8],u64)->G1Projective`, `load_current_release_key_view→ReleaseKeyView{vss_commitments,..}`, `tlock_ibe_decrypt(&G1Projective,&WrappedDek,&[u8])->Result<Vec<u8>>`, `validate_bundle→(surplus,deltas,nonces)` / `apply_bundle(deltas,nonces)`, `Auction{reveal_height,coordinator,scope}`, args `RevealAuctionArgs{request_id,sigma}` / `CancelAuctionArgs{request_id}` — consistent across tasks. ✅

## Implementer must-reads (mirror targets)
- `cbss/crates/cbss-crypto/src/{ibe.rs,envelope.rs}` (T4 decrypt port + WrappedDek layout + HKDF/Gt serialization).
- node #888 `execution/src/settlement.rs` `open_auction`/`submit_sealed_bid`/`auction_key`/`read_auction`/`read_auction_bidders`/`sealed_bid_key` (T2/T3/T6/T7).
- node `execution/src/cbss.rs` `compute_tlock_identity`,`load_current_release_key_view`,`g1_from_bytes`,`public_share_commitment`,`RegisterTlockReleaseArgs`,`handle_cbss_register_tlock_release` (T3/T6).
- `execution/src/settlement.rs:430` `settle_bundle` + `conservation_surplus()` on `SettlementBundle` (T5).
- codec `crates/cowboy-protocol-codec/src/settlement.rs` `OpenAuctionArgs`/`SubmitSealedBidArgs`/`AuctionGrant` (T1).

## Sequencing
codec rev (PR 0) → node stack on #888 (T2–T8). When #888 merges to devnet, rebase the node branch onto devnet. Activates with cbss#41 + node#892 + #888 under the CIP-34 §SEALED flag-day.
