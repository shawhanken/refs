# CIP-34 v1 SEALED-bid reveal consumer — design (MVP)

Date: 2026-07-02
Status: design approved, pending implementation plan
Repo: node (stacks on #888 `feat/cip-34-sealed-auction-handlers`)
Spec authority: `cowboy/docs/cips/cip-34-cross-chain-settlement-near-intents.md` §Sealed-Bid Auctions; CIP-24 §3.4.6 (tlock)

## Problem

CIP-34 v1 SEALED has the bid-collection phase (node #888: `open_auction` / `submit_sealed_bid`, opcodes 154/155) and the CIP-24 §3.4.6 tlock release backend (merged #882/#883) + off-chain committee signing (cbss #41 / node #892). The missing core piece is the **reveal consumer**: at/after `reveal_height`, combine the tlock release `σ`, decrypt the sealed bids, pick the best valid settlement bundle, and apply it. Without it, sealed auctions collect bids that are never cleared.

The CIP-34 spec's `reveal(request_id)`: "the NATIVE handler (no PVM decryptor) fetches the CIP-24 release key for identity=request_id, decrypts all bids, selects the best valid bundle by Settlement-MinReceive surplus, and applies it via the settle() path." Plus a liveness fallback if the committee never releases.

## Goal / non-goals

**Goal (MVP):** permissionless on-chain reveal (combine-off-chain σ, verify, decrypt, select best by MinReceive surplus, settle) + permissionless cancel/refund liveness fallback after `AUCTION_GRACE`.

**Non-goals (follow-ups):** solver-mode dispute/slashing (undecryptable / invalid-bundle → CIP-2 slash within a dispute window; spec calls it a v1 deliverable, deferred); the "degrade to OPEN" fallback variant; encrypted-*intent* private order flow.

## Key decisions (from brainstorming, revised 2026-07-02 to align with merged upstream codec)

> **PIVOT (2026-07-02):** cowboy-protocol **#14 (`dadd933`) already merged** `RevealAuction` (opcode 156) as `RevealAuctionArgs { request_id }` — carrying ONLY `request_id`, with the explicit intent that "the node's native handler **Lagrange-combines the partials**, decrypts every sealed bid ... and applies it via settle" (permissionless, ExpireDkgPending/GcNonces idiom). This is **option B (on-chain aggregation)**, the opposite of the brainstormed option A (tx carries σ). To avoid fighting a just-merged upstream type, the design is **aligned to option B**. RevealAuction codec is therefore already done; this work adds only `CancelAuction (157)` + `OpenAuctionArgs.scope` to the codec.

1. **σ acquisition + trigger (option B, aligned to #14):** a permissionless **`RevealAuction { request_id }` tx** (no σ carried). The native handler reads the on-chain `TlockPartialSet` for `I_tlock = hash_to_G1(request_id ‖ le(reveal_height), "cbss/tlock/v1")`, and **Lagrange-combines ≥ t partials on-chain in G1** (mirroring cbss-crypto `combine_partials`) into `σ = MSK · I_tlock`, then decrypts. **No MPK-verify-σ step is needed** — each partial was already pairing-verified at `SubmitTlockRelease`, so combining verified partials yields a valid σ and there is no bogus-σ grief vector (the caller supplies only `request_id`). If fewer than `t` partials are posted, the reveal reverts (`RevealNotEnoughPartials`) — the caller retries once the committee has posted enough, or `CancelAuction` after grace. Note the reveal must run **within the tlock retention window** `[reveal_height, target_height + TLOCK_RETENTION)` (256 blocks) while the partials are still on-chain; `AUCTION_GRACE` (50) < 256, so the cancel fallback is always inside retention. No timer dependency; matches the permissionless public-artifact model.
2. **Liveness fallback:** a permissionless **`CancelAuction`** after `reveal_height + AUCTION_GRACE` (default 50) — clears auction+bid state, never traps funds. (Not "degrade to OPEN".)
3. **Dispute/slashing:** OUT of MVP. Undecryptable / invalid bids are **skipped** (not selected); no slashing.
4. **Winner rule:** best valid `SettlementBundle` by **MinReceive surplus** (per spec); deterministic tie-break.
5. **CBSS scope:** still **pinned authoritatively at open time** — under option B the handler needs the scope to locate the on-chain partial set (`tlock_id = keccak(canonical(scope) ‖ request_id ‖ le(reveal_height))`) and to map each partial's `proxy_id` → committee index for Lagrange. Since #888's `OpenAuctionArgs`/`Auction` carry no scope, **extend #888** (this stack): add `scope: ReleaseKeyRef` to `OpenAuctionArgs`, store it in the `Auction` record, and have `open_auction` also write the `RegisterTlockRelease` so the committee auto-signs.

## Components

### A. #888 extension (prerequisite, folded into this stack)

- **codec** (cowboy-protocol): add `scope: ReleaseKeyRef` to `OpenAuctionArgs` (a new rev after `bf56c001`).
- **`open_auction` handler** (settlement.rs): store `scope` in the `Auction` record; additionally write a `RegisterTlockRelease(scope, tag = request_id, target_height = reveal_height)` via the CIP-24 §3.4.6 register path, reusing its guards (scope resolves to a committee, `MIN_TLOCK_LEAD_BLOCKS` lead, per-block cap, dedup). This makes the committee sign by `reveal_height` with no separate manual registration.
- `Auction` decoded struct gains `scope`.

### B. System instructions (codec)

- `RevealAuction { request_id: [u8;32] }` (156) — **ALREADY MERGED upstream (cowboy-protocol #14, `dadd933`)**. No change.
- `CancelAuction { request_id: [u8;32] }` (157) — **new, this work** (a codec rev after `dadd933`).
- `OpenAuctionArgs.scope: ReleaseKeyRef` — **new field, this work** (same codec rev).
- New error codes next-free after #888's E1746–E1751 (e.g. `AuctionRevealTooEarly`, `RevealNotEnoughPartials`, `AuctionNotOpen`, `AuctionCancelTooEarly`, `AuctionAlreadyRevealed`). (No `AuctionInvalidReleaseKey` — option B needs no σ-verify.)
- Add 157 to `sys_opcode_uniqueness` (156 already added by #14).

### C. `handle_reveal_auction` (settlement.rs) — option B

1. `read_auction(request_id)` → must exist and be open (not already revealed); else `AuctionNotOpen`.
2. `head ≥ auction.reveal_height` else `AuctionRevealTooEarly`.
3. `I_tlock = compute_tlock_identity(request_id, auction.reveal_height)` (request_id is the tag).
4. **Combine σ on-chain from the stored partials.** Read the `TlockPartialSet` for `tlock_id(auction.scope, request_id, auction.reveal_height)`. `load_current_release_key_view(auction.scope)` gives the committee + threshold `t`; map each stored partial's `proxy_id` → its 1-based committee index. If `< t` partials → `RevealNotEnoughPartials` (revert; caller retries later or cancels after grace). `combine_partials(&[(index, g1_from_bytes(partial))…], t)` (mirror cbss-crypto: Lagrange in G1) → `σ = MSK · I_tlock`. No MPK-verify needed — each partial was pairing-verified at `SubmitTlockRelease`, so a combination of ≥ t verified partials is a valid σ and there is no caller-supplied σ to forge.
5. `read_auction_bidders(request_id)` (bounded `MAX_SEALED_BIDS_PER_AUCTION = 256`); for each solver read `sealed_bid_key`.
6. For each bid envelope (CIP-24 tlock IBE: carries `U ∈ G2` + AES-256-GCM ct/nonce + aad): `K = HKDF-SHA256(serialize(e(σ, U)), "cbss/tlock/v1" ‖ aad)`; AES-256-GCM-decrypt → `SettlementBundle`. On decrypt/parse failure → **skip** (undecryptable; future dispute).
7. Validate each decoded bundle via the **existing settle validation** (value conservation, intent signatures, floors — the same checks `IntentSettle` runs). Compute MinReceive surplus. Select the **best valid** bundle: max surplus; deterministic tie-break (lowest solver address, then first-bid order).
8. Apply the winner via the **existing `settle()` apply path** (0x14 ledger apply, compute-then-commit — no partial writes on failure). Mark the auction revealed / delete auction + bids + bidder-list state (prevent re-reveal). Emit `cip34.AuctionRevealed { request_id, winner, surplus }`.
9. If no valid bundle → close with no settlement; emit `cip34.AuctionRevealedEmpty`. The originator's ledger deposit stays withdrawable.

### D. `handle_cancel_auction` (settlement.rs)

- `read_auction` must exist and not be revealed; `head ≥ auction.reveal_height + AUCTION_GRACE` else `AuctionCancelTooEarly`. Permissionless. Clears auction + bids + bidder-list state. The originator's ledger balance was never moved by the auction (funds move only at settle), so this releases the auction so the intent can settle OPEN or be withdrawn. Emit `cip34.AuctionCancelled`.

## New on-chain crypto surface (notable)

The reveal introduces two on-chain crypto surfaces in the execution engine: (i) **G1 Lagrange combine** of the stored partials into σ (mirror cbss-crypto `combine_partials` — scalar muls/adds in G1, deterministic, bounded by `t`), and (ii) **AEAD decryption**: `pairing e(σ, U)` (blstrs — already available), `HKDF-SHA256`, and `AES-256-GCM` decrypt. node currently verifies tlock partials on-chain but the secret-release *decrypt* is done off-chain by the runner, so there is no on-chain `ibe_decrypt` today. This adds deterministic deps (`aes-gcm`, `hkdf`, `sha2`) to the execution crate. All deterministic; bounded by `MAX_SEALED_BIDS_PER_AUCTION`. The bid envelope byte format mirrors cbss-crypto's `ibe_encrypt`/`ibe_decrypt` (`U = compress(r·G2_gen)`, AES-GCM(ct,nonce), aad) — pinned in the implementation plan with a cross-impl vector against cbss-crypto (the same discipline as the tlock identity vector).

## Consensus

`RevealAuction`/`CancelAuction` are consensus system instructions: opcodes 156/157 flip decode-reject → dispatch; new error codes enter `receipt_root`; settle side effects + `cip34.*` events enter state/receipt roots. Activates on the CIP-34 flag-day (same family as 146–155). Uses compute-then-commit (no partial writes on a failed reveal) per the engine's no-rollback constraint.

## Testing

- **σ verify:** genuine σ (from a seeded committee, real VSS + polynomial) passes; a wrong σ is rejected `AuctionInvalidReleaseKey` and leaves auction state intact (anti-grief).
- **decrypt round-trip:** a bid encrypted (mirror cbss-crypto `ibe_encrypt`) to `identity=request_id`, `reveal_height` decrypts with σ to the exact `SettlementBundle`; a bid under a different identity/σ fails the AEAD tag → skipped. Cross-impl envelope vector vs cbss-crypto.
- **winner selection:** highest-MinReceive-surplus valid bundle wins; an invalid/undecryptable bid is skipped; deterministic tie-break.
- **settle integration:** the winning bundle applies via the existing settle path (conservation holds; ledger updated); a bundle that fails conservation is not selected.
- **liveness:** before `reveal_height` → TooEarly; a valid reveal closes the auction and blocks a second reveal; `CancelAuction` before grace → TooEarly, after grace on an unrevealed auction → clears state; cancel after a successful reveal → AuctionNotOpen.
- **#888 extension:** `open_auction` stores `scope` and registers the tlock request (assert the `tlock_req:` record exists for `(scope, request_id, reveal_height)`).

## PR structure

Stacks on **#888** (`feat/cip-34-sealed-auction-handlers`): codec rev (add `scope` + opcodes 156/157) → #888 extension (scope + tlock register) → reveal handler → cancel handler → e2e. When #888 merges to devnet, rebase onto devnet (as with #892).

## Dependencies / sequencing

- Needs cbss #41 + node #892 (off-chain committee signing) deployed for the committee to actually produce σ — otherwise a reveal caller has no partials to combine. All three + #888 + this land under the CIP-34 §SEALED flag-day.
- codec: a new cowboy-protocol rev adding `OpenAuctionArgs.scope` + `RevealAuction`/`CancelAuction` (156/157), after `bf56c001`.
