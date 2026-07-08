# CIP-34 v1 SEALED — Flag-Day Activation Coordination

Date: 2026-07-02
Owner: (pavilionledger / release coordinator)
Scope: coordinated activation of the CIP-34 v1 SEALED-bid auction stack (opcodes **152–156**), building on the already-live M2 intent settlement (146–149).

Supersedes the readiness table of `2026-07-02_cip24-tlock-flag-day-coordination.md` (written before the reveal/consumer slice landed; the tlock opcodes 152/153 are folded into this one atomic upgrade).

---

## 0. TL;DR — where we stand

The **entire on-chain consensus surface for v1 SEALED is now merged to `devnet`** (`origin/devnet` @ `3ccd19d9`):

| Slice | PR | Merge commit | Opcodes |
|---|---|---|---|
| tlock release backend (CIP-24 §3.4.6) | #882 | on devnet | 152, 153 |
| SEALED lifecycle (open / submit bid) | #888 | `88097306` | 154, 155 |
| SEALED reveal (on-chain threshold-IBE decrypt + settle) | #904 (was #893) | `3ccd19d9` | 156 |
| SEALED reveal → WrappedDek reconciliation | #907 | `65dfde3d` | 156 (envelope) |
| codec pin | cowboy-protocol #12/#13/#14 | rev `dadd9330` | 152–156 defs |

> **Status update (2026-07-03):** the reveal envelope was reconciled onto the WrappedDek track (node #907, merged devnet). **Both off-chain liveness prerequisites are now merged to their mains** — cbss #41 (committee release daemon) + #42 (bid encryptor) on cbss `main` (`33c17ae`); node reveal on devnet. The crypto cross-anchor is mechanically verified on both mains. CIP-34 v1 SEALED is now **code-complete**; what remains is deployment/ops + governance, not code (§4 residuals).

**Two distinct milestones — do not conflate:**

1. **Consensus flag-day** (activate opcodes 152–156). *Ready now.* The reveal consumer exists and is safe: unrevealable auctions do not lock bids, they **cancel + refund** at `reveal_height + AUCTION_GRACE(50)`. Activating the surface is safe even before a live committee exists (auctions simply refund on timeout).
2. **Feature go-live** (announce sealed auctions as *usable*). Gating code has largely landed; remaining gates are **operational/governance, not code**: (a) deploy the node devnet binary carrying 152–156 + run a live `cbssd` committee; (b) a solver bid-sealing client that uses the CIP-34 base-AAD; (c) commit the CIP-34 spec. Until (a), every auction is consensus-safe but functionally inert (reveals refund at grace).

**Recommendation:** proceed with the consensus flag-day (fleet redeploy, option A) whenever convenient; treat feature go-live as a **separate, later** announcement gated on §4. Do not gate the consensus activation on the off-chain work — the grace/refund fallback makes early activation harmless.

---

## 1. What "flag-day" means here — no in-code activation gate

There is **no per-opcode activation-height gate** in the code. `system_instruction.rs:1663` comment: *"Opcodes now decode+dispatch instead of decode-reject → consensus flag-day."* The switch happens the moment a validator runs the new binary:

- A validator **with** the new binary decodes + dispatches opcodes 152–156.
- A validator **without** it rejects them at the codec layer (`Instruction::decode → Err`).
- The first block containing any such tx under a partial rollout → **`state_root` / `receipt_root` divergence → fork.**

Therefore **all validators must switch at the same height.** Two mechanisms (same choice as the tlock memo §4):

- **(A) Coordinated fleet redeploy** — schedule a window; all validators upgrade in lockstep. Simplest for devnet; a straggler forks until it catches up. **Acceptable for devnet.**
- **(B) Gov-param activation height** — gate opcode 152–156 dispatch behind a single on-chain height (precedent: `cip1.auction.activation_height`, `activation_delay_blocks`). Deterministic switch + flip-off rollback. **Required posture for the mainnet track.** If chosen, it is a small dispatch-guard addition — call it out before the mainnet cut.

---

## 2. Opcode inventory (146–156) & consensus status on devnet

| Opcode | Instruction | Status on devnet | Notes |
|---|---|---|---|
| 146 | IntentDeposit | **live** (#861, M2) | OPEN-mode custody |
| 147 | IntentWithdraw | **live** (#861) | |
| 148 | IntentSettle | **live** (#861) | account + broadcast auth paths |
| 149 | IntentBroadcast | **live** (#861) | resting record now stores `signer(20)‖deadline(8)` (changed by #904 — see §5) |
| 150 | IntentRequestWithdraw | **stub** | `UnsupportedInstruction` (v2 cross-chain, needs CIP-25) — `system_instruction.rs:1648` |
| 151 | IntentCreditDeposit | **stub** | `UnsupportedInstruction` (v2 inbound mint) — `:1654` |
| **152** | RegisterTlockRelease | **newly merged** (#882) | CIP-24 §3.4.6; gas E-const; E1739–E1745 |
| **153** | SubmitTlockRelease | **newly merged** (#882) | committee partial submission |
| **154** | OpenAuction | **newly merged** (#888) | AuctionGrant sig verify, nonce consume |
| **155** | SubmitSealedBid | **newly merged** (#888) | CIP-2-registered solvers; per-auction bidder list |
| **156** | RevealAuction | **newly merged** (#904) | permissionless; on-chain threshold-IBE decrypt + settle |

**This flag-day activates 152–156.** 146–149 are already live (activated with #861's deploy); 150/151 remain dormant stubs (v2).

**Consensus surface added by this batch:**
- Opcodes 152–156: decode-reject → decode+dispatch.
- Error codes **E1739–E1745** (tlock) + **E1746–E1754** (auction) → `receipt_root` (failed-tx `StructuredError` fields are consensus — see `project_node_events_consensus_receipt_root`).
- Events `cbss.tlock.*` + `cip34.{AuctionOpened,SealedBidSubmitted,AuctionRevealed,AuctionCancelled}` → `logs_root` → `receipt_root`.
- New gas constants (tlock register/submit; per-bid decrypt; per-settle-attempt).
- Codec rev `dadd9330` (adds the tlock/auction `*Args` + opcodes 152–156).

---

## 3. Pre-activation audit blockers — status

The #888/#893 multi-round independent audits raised blockers to be closed **before** flag-day. Current status:

| Finding | Severity | Status |
|---|---|---|
| `open_auction` never binds `grant.originator` to the true owner of `request_id` → attacker squats a victim's auction slot | HIGH | ✅ **RESOLVED** — landed in #904 (`ba09bbc2`). `broadcast_intent` resting record now stores `signer`; `open_auction` checks `resting_signer(request_id) == grant.originator`. |
| Auction state (`auc:`/`abl:`/`abid:`) has no GC → unbounded consensus-state growth (0x14 is kv/byte-cap exempt) | MEDIUM | ✅ **MITIGATED** — permissionless `clear_auction` on reveal/cancel deletes all three families; anyone can cancel-clear after `reveal_height + GRACE`, so no permanent orphans. Residual: proactive gc-sweep (follow-up, non-blocking). |
| Reveal liveness — committee fails to release key | (liveness) | ✅ **IMPLEMENTED** — `AUCTION_GRACE = 50` (`settlement.rs:831`); reveal returns `TlockNotReleased` until `reveal_height + 50`, then cancels + refunds. Bids never lock. |
| Permanent brick (unsettleable bid reverts reveal forever) | HIGH | ✅ **RESOLVED** — try-settle loop skips candidates (`settle_bundle` is compute-then-commit; `Err` leaves no state). |
| Gas underestimate (flat base for N-bid decrypt) | HIGH | ✅ **RESOLVED** — per-bid decrypt + per-settle-attempt-intent charging. |
| Winner not bound to `request_id` (empty bundle could win) | MEDIUM | ✅ **RESOLVED** — winner must contain an intent with `intent_hash == request_id`. |

**All audit blockers are closed on devnet.** Bounds in place: `MAX_SEALED_BIDS_PER_AUCTION = 256`, `MAX_AUCTION_REVEAL_HORIZON = 1_000_000`, bid envelope `MAX_SEALED_BID_BYTES = 8192`, tlock tag ≤ 64B.

---

## 4. Cross-repo liveness prerequisites (gate FEATURE go-live, NOT consensus)

These make the feature *usable*. None affects consensus safety — with them absent, auctions cancel+refund harmlessly.

> **Correction (2026-07-02, later):** an earlier draft of this table marked the committee driver and the bid encryptor as ❌ absent. That was wrong — both **exist as open PRs on the WrappedDek track** (cbss #41 + #42). The node reveal path has been **reconciled onto that track** (node #907, adopting `tlock_ibe.rs`; supersedes #904's bespoke envelope). Updated status below.

| Prerequisite | Repo | Status (2026-07-02) | Evidence |
|---|---|---|---|
| **Off-chain tlock committee release driver** — watches pending `RegisterTlockRelease`, computes `partial = share · I_tlock` at `target_height`, submits `SubmitTlockRelease` | cbss (`cbssd`) | ✅ **merged to cbss `main`** | cbss **#41** merged `33c17ae` (2026-07-03) — `TlockReleaseSubmitter` + `chain_watcher.tlock_requests()` + sign-and-submit each poll tick; carries #42 (encryptor) + #43 (share-zeroize hardening). Remaining: **deploy a live committee** (run `cbssd` against devnet) — until a committee actually releases, every reveal hits `TlockNotReleased` → refund at grace. |
| **Client bid encryptor** matching the on-chain envelope | cbss-crypto | ✅ **merged to cbss `main`; cross-vector verified on main** | cbss **#42** (in #41 stack) — `tlock_ibe_encrypt` emitting the versioned `WrappedDek` (v2), same kernel as CIP-24 §3.4.3 IBE (domain `cbss/tlock/v1`). **Cross-repo byte-agreement MECHANICAL on cbss `main`** (node #907 audit Finding A closed): `tlock_ibe_decrypt_matches_node_onchain_vector` + `tlock_identity_matches_node_pinned_vector` green (6/0), node `tlock_ibe.rs` vectors byte-identical (whitespace aside) — both repos decrypt the same envelope + hash the same identity; #43 zeroize fix did not perturb the vector. **Base-AAD contract to lock:** `request_id(32) ‖ u64_le(reveal_height)` — cbss #42's vector uses a placeholder base-AAD; the real bid-sealing **solver client** must use the CIP-34 layout (still downstream — no committed bid-sealing caller yet). |
| **tlock-requests discovery RPC** — proxies/committee find pending requests | node rpc | 🟡 **in review** | shawhanken #892 (`GET /cbss/tlock-requests`) + my fixups #903 (response cap). Not consensus; needed for committee liveness. |
| **Node reveal ↔ WrappedDek reconciliation** | node | 🟡 **in review** | node **#907** — reveal decrypts the WrappedDek envelope via `tlock_ibe.rs` (adopted from `feat/cip34-reveal-consumer`), superseding #904's bespoke wrap. Consensus (changes on-chain bid wire format); pre-flag-day so zero-live-risk. |
| **§5.3 error-table doc-sync** | cowboy | 🟡 **open** | #218 (docs only, no consensus). Land in the window. |
| **Committed CIP-34 spec** | cowboy | 🟡 **exists; as-built alignment in review** | `cowboy/docs/cips/cip-34-cross-chain-settlement-near-intents.md` already exists (r1–r6 design). **PR #221 (r7)** aligns §Sealed-Bid + opcodes/params/events/errors to the merged implementation (reveal = permissionless tx not timer; WrappedDek envelope; base-AAD contract; etc.). Not a flag-day blocker — spec catching up to code. |

**Cross-repo contract to lock before feature go-live:** the CIP-34 bid **base-AAD = `request_id(32) ‖ u64_le(reveal_height)`**. The node reveal reconstructs exactly this and full-equality-checks `WrappedDek.aad == base_aad ‖ compress(U)`. cbss #42's encrypt unit test currently uses a placeholder base-AAD; the real bid-sealing caller must use this layout. This is the single most likely place for a silent field-order/endianness mismatch — a shared bid-level helper (or committed doc note) is the safeguard.

---

## 5. Consensus behavior change to a *live* instruction (149)

#904 changed `IntentBroadcast`'s resting record value from `deadline(8)` to `signer(20)‖deadline(8)` (to enable the originator-binding fix). `IntentBroadcast` (149) is **already live** since #861. This is a **storage-format change to a live instruction** — the value written differs from the moment the new binary runs, so it is part of *this* flag-day and cannot lead or lag it. (Old records written by the pre-#904 binary have no `signer` prefix; `resting_signer` reads assume the new layout. On devnet this is covered by the coordinated redeploy from a clean-ish state; **for mainnet, a gov-param height (option B) is the safe cut** so old and new records don't coexist across the boundary. Call this out explicitly at the mainnet cut.)

---

## 6. Merge order & remaining PRs

Consensus stack (mine) — **already merged to devnet** in dependency order:
1. ✅ #882 (152/153) → devnet.
2. ✅ #888 (154/155) → devnet (`88097306`).
3. ✅ #904 (156, incl. originator-binding fix) → devnet (`3ccd19d9`).

Remaining (not mine to merge):
- **#903 → #892 → devnet** — shawhanken's tlock-requests RPC; my fixups #903 folds into his branch at his discretion. Not consensus.
- **cowboy #218 → main** — docs; land in the flag-day window.

---

## 7. Rollout sequence (recommended)

**Phase 1 — Consensus flag-day (ready once #907 lands):**
1. Merge node **#907** (WrappedDek reveal reconciliation) → devnet first — it changes the on-chain bid wire format and must be in the flag-day binary.
2. Announce flag-day height **H** (option A devnet redeploy) — or set gov-param `…v1sealed.activation_height = H` if wrapping in option B.
3. Distribute the devnet binary (post-#907, codec `dadd9330`).
4. All validators upgrade before **H**.
5. Merge #218 → cowboy `main` in the same window.
6. **Post-H verify:** no `state_root`/`receipt_root` divergence around **H**; E1739–E1754 surface correctly in failed-tx receipts; a `RegisterTlockRelease` + `OpenAuction` + `SubmitSealedBid` round-trips; a reveal past `reveal_height+GRACE` with no key cancels + refunds.

**Phase 2 — Feature go-live (later, gated on §4):**
7. Merge cbss **#41** (committee release daemon; now also carries #42's encryptor after `3c818a03`) → cbss `main`. **Finding A (vacuous golden vector) is CLOSED**: #42 is committed and the cross-vector is now mechanical — cbss's `tlock_ibe_decrypt_matches_node_onchain_vector` + `tlock_identity_matches_node_pinned_vector` are green against the byte-identical node vectors (verified 2026-07-02). Remaining before activation: (a) #41 merges to cbss `main` + deploys a live committee; (b) confirm the real bid-sealing client uses base-AAD = `request_id ‖ u64_le(reveal_height)` (cbss #42's test uses a placeholder); (c) nice-to-have: a committed encrypt-path reproduction test (both current vectors only exercise decrypt). Retire the standalone `feat/cip34-reveal-consumer` decryptor (adopted into #907).
8. Merge #892/#903 (RPC discovery).
9. Merge the CIP-34 as-built spec alignment (cowboy **#221**, r7) so the spec-of-record matches the deployed behaviour.
10. End-to-end on devnet: real committee releases key at `target_height` → reveal Lagrange-combines ≥t partials → decrypts bids → settles winner. Announce usable.

---

## 8. Rollback / abort

- **Pre-H:** abort by not upgrading — no state touched.
- **Post-H divergence (option A):** coordinated downgrade + rewind to pre-H (devnet-acceptable). This is the argument for **option B on mainnet** — a gov-param gate flips activation off without a rewind.
- **The 149 resting-record format change (§5) rides with this set** — cannot be reverted alone once records with the new layout exist. Roll the whole batch back together.

---

## Reference

- Spec: CIP-24 §3.4.6 (cowboy #212), §3.3/§3.5; CIP-34 v1 SEALED (planning docs only — not yet committed to `docs/cips/`).
- Code: node #882 (tlock 152/153) + #888 (auction 154/155) + #904 (reveal 156). `origin/devnet` @ `3ccd19d9`. Codec `dadd9330`.
- Params: `AUCTION_GRACE=50`, `MAX_AUCTION_REVEAL_HORIZON=1_000_000`, `MAX_SEALED_BIDS_PER_AUCTION=256`, `MAX_SEALED_BID_BYTES=8192`.
- On-chain envelope contract: `cbss.rs::tlock_bid_wire_format_golden`.
- Predecessor memo (tlock-only, readiness table superseded here): `2026-07-02_cip24-tlock-flag-day-coordination.md`.
- Memory: `project_cip34_implementation`, `project_node_events_consensus_receipt_root`.
