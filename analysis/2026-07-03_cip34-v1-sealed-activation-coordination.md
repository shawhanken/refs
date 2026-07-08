# CIP-34 v1 SEALED — activation coordination (flag-day + committee bootstrap)

Date: 2026-07-03
Owner: (release coordinator / governance)
Scope: bringing the merged CIP-34 v1 SEALED sealed-bid auction from *code-complete* to *live on devnet*.

## 1. State: code-complete + merged

The full v1 SEALED plumbing is merged (devnet / cbss main). End-to-end chain, all seams byte-anchored:

```
governance GovRequestSystemDkg → 0x14 committee (DKG → RotateCommittee writes AccountReleaseKey/MPK)
  → open_auction (auto-registers RegisterTlockRelease for scope=0x14, tag=request_id, target=reveal_height)
  → CBSS committee daemon signs partials (SubmitTlockRelease) by reveal_height
  → solver: GET /cip34/open-auctions (discover) → GET /cbss/account-release-key/0x14 (MPK)
            → seal_cip34_bid → SealedBidSubmitter → SubmitSealedBid
  → head ≥ reveal_height: reveal_auction (combine σ → tlock_ibe_decrypt bids → first-valid winner → settle)
  → liveness: reveal after reveal_height+AUCTION_GRACE with no key → CancelledGraceExpired
```

Merged PR set (this workstream):
- **cowboy-protocol** #18 (revert unused OpenAuction.scope/CancelAuction) ← #19 (`GovRequestSystemDkg` 158)
- **node** #909 (gov-dkg handler) ; #910 (open_auction auto-registers tlock) ← #911 (open-auctions index + `GET /cip34/open-auctions`)
- **cbss** #44 (`seal_cip34_bid`) ← #45 (`SealedBidSubmitter`) ← #46 (solver loop) ← #47 (`RpcCommitteeMpk`) [+ solver production wiring: `RpcAuctionSource`/`RpcChainHead`/`StaticBidStrategy`]
- Prior: node #882/#883/#888/#904/#907, cowboy #195–221, cowboy-protocol #10–15.

## 2. What is NOT code — the two operational gates

### 2a. Bootstrap the 0x14 committee (governance action + DKG ceremony) — MUST precede any auction
`open_auction` and `reveal_auction` both require the `Account(0x14)` `INTENT_SETTLEMENT` committee to have an `AccountReleaseKey` (MPK + shares). It is bootstrapped once:
1. Governance (`GOVERNANCE_SYSTEM_ACTOR` 0x09) submits **`GovRequestSystemDkg { scope: Account(0x14) }`** (opcode 158) — writes a `DkgPending` for the scope and emits `cbss.dkg.requested`.
2. The eligible CBSS committee (selected by the handler) runs the off-chain DKG (the cbssd daemon already handles `cbss.dkg.requested` generically) and commits via **`RotateCommittee { scope: Account(0x14) }`**, which writes the `AccountReleaseKey` (MPK + vss_commitments).
3. Verify: `GET /cbss/account-release-key/0x14` returns a populated `mpk_g2` — auctions can now open.
- Requires ≥ the committee's `t`/`n` of registered CBSS proxies to be live to complete the DKG.
- Reshare/rotation later uses the same `RotateCommittee` path; a re-DKG can be forced with `GovRequestSystemDkg { force_rekey: true }`.

### 2b. Consensus flag-day — activate opcodes 146–158
The sealed-auction / tlock / settlement opcodes (`146`–`158`) move from **decode-reject → decode+dispatch** on a coordinated validator upgrade; new error codes + `cip34.*` / `cbss.*` events enter `receipt_root`. All validators must run identical logic before the flag-day height.
- Pin the codec rev (devnet currently `d25a8dca`) reproducibly across the validator binary + the wallet/client tx encoders.
- `152`/`153` (tlock), `154`/`155`/`156` (open/bid/reveal), `157` (was CancelAuction — **reverted**, unused), `158` (`GovRequestSystemDkg`). Cancel is folded into `reveal_auction` (`CancelledGraceExpired`), not a separate opcode.
- Same flag-day family as the already-planned `Intent*` 146–151 settlement activation — activate the whole 146–158 block together (`refs/analysis/2026-07-02_cip34-v1-sealed-flag-day-coordination.md` is the tlock-slice predecessor; this supersedes/extends it to the full v1 SEALED set).
- Activation mechanism decision (unchanged): devnet = coordinated redeploy; before mainnet, wrap behind a gov-param activation height (`cip1.auction.activation_height` precedent).

## 3. Ordering
1. Flag-day activates 146–158 (so `GovRequestSystemDkg` dispatches).
2. Governance bootstraps the 0x14 committee (§2a) — needs 158 live.
3. Committees + a solver come online (cbssd daemon for signing; a solver with a real `BidStrategy` for bidding).
4. First real auction: `open_auction` → bids → committee signs → `reveal_auction` settles.

## 4. Post-activation verification (devnet)
- `GET /cbss/account-release-key/0x14` → populated MPK (committee bootstrapped).
- `open_auction` → `GET /cip34/open-auctions` lists it; the `TlockRequest` for `(0x14, request_id, reveal_height)` exists.
- ≥ t `SubmitTlockRelease` partials posted by the committee by `reveal_height`.
- A sealed bid (`seal_cip34_bid` + `SealedBidSubmitter`) is accepted; `reveal_auction` at `head ≥ reveal_height` → `Settled` with the ledger effects applied.
- Grace path: an auction with no key by `reveal_height + AUCTION_GRACE` → `CancelledGraceExpired`, no funds trapped.
(The node e2e integration test `test(cip-34): end-to-end sealed auction` pins this whole chain in-process; the devnet run is the live confirmation.)

## 5. Remaining engineering (not activation)
- **Solver — now functional (reference).** All four seams are wired: `AuctionSource`→`RpcAuctionSource` (#48), `CommitteeMpk`→`RpcCommitteeMpk` (#47), `ChainHead`→`RpcChainHead` (#48), and **`BidStrategy`→`FillingBidStrategy` backed by a chain-driven intent feed (cbss #49)**. The feed (`RpcIntentPoller`) scans finalized blocks for `IntentBroadcast` and indexes `intent_hash→Intent` (the intent body is deliberately not on-chain), which `FillingBidStrategy` turns into a conserving single-intent bundle. **Remaining product seam (not activation-blocking):** *selective/priced* bidding — bid only on profitable, inventory-coverable auctions — plus a liveness pre-check (skip expired/consumed intents; needs current height plumbed into `build_bid`). The reference strategy bids every resolvable auction at the user's stated terms (safe: never grief-slashed, just loses if it can't settle).
- **solver-mode dispute/slashing** — **MVP shipped: node #920** (rides this same 156 flag-day). `reveal_auction` now slashes a registered solver whose sealed bid is undecryptable or whose bundle fails to decode / does not fill `request_id`, via the CIP-2 `slash_runner` path (flat `SOLVER_GRIEF_SLASH_WEI = 100 CBY`, best-effort). Winner + valid-but-losing bids are exempt. Adversarial review caught + fixed a post-settle pay-then-fail (grief gas hoisted above the winner loop; regression-locked by mutation). **Follow-ups (not activation-blocking):** (a) governance-tunable bps-of-stake slash schedule replacing the flat constant; (b) slashing the decodes+fills-but-unsettleable bundle (needs a settle dry-run); (c) a challengeable dispute *window* if the objective on-chain evidence model is ever deemed insufficient.
- **v2 cross-chain** (`credit_deposit`/`request_withdraw`) — separate phase, blocked on CIP-25 backend + proof verifier.

### e2e coverage
- **node #919** pins the whole honest chain in-process (open → auto-register tlock → open-auctions index → sealed bid → `t` partials → reveal → `Settled` + ledger effects), driving the real handlers with the real decrypt path.
