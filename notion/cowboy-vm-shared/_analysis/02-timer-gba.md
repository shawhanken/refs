# 02 — Timer + Gas Bidding Agent (GBA)

## TL;DR

- **Drop first-price auction from CIP-1.** The whitepaper and CIP-1 v1 promise a first-price + exponential-bias auction. The reviewer's Phase-3 selection (EIP-1559 timer basefee + per-actor fairness weight) is sound — first-price-per-cycle is unstable in repeated knapsack settings, EIP-1559 reuses six years of EVM patterns, and the default-GBA spec collapses to two lines. **Recommended: substantial CIP-1 rewrite (Part II §2 already names this as a future direction).**
- **Split WP §5.1 into "currently implemented (CIP-5 FIFO)" and "target design (CIP-1 EIP-1559 hybrid)".** Today's WP §5.1 only describes the target; readers can't tell what's live. CIP-1 v2 already acknowledges this — pull it into the WP.
- **Close Gap G7 inside the rewritten CIP-1.** Default GBA: `max_fee = 2 × basefee`, `max_priority_fee = previous_block_p50_priority_tip`. Per-actor weight `W(actor) ∈ [1,2]` on a 1000-block window. Per-timer cap 250k cycles (auction-phase only; CIP-5 today caps at 550k and stays). Timer-lane multiplier pinned at 1.0×.

## Items index

| # | Title | Priority | Touches | Status | Action |
|---|---|---|---|---|---|
| 13 | GBA invalid-bid handling unspecified | P1 | CIP-1, CIP-5 §9 | actionable | resolved by CIP-1 rewrite (no bid field in EIP-1559 path) |
| 23 | Default GBA disadvantages unsophisticated actors | P2 | CIP-1, WP §5.1 | actionable | spec default GBA inline in rewritten CIP-1 |
| 28 | Gap G7 — default GBA spec | P2 | CIP-1, CIP-5 §9 | actionable | spec default GBA inline (closes G7) |
| 44 | Caleb owns G7 | P2 | process | resolved | G7 spec recommended below; Caleb signs off |
| 60 | Split CIP-5 current FIFO from CIP-1 target | P1 | WP §5.1 | actionable | WP §5.1 split into 5.1a / 5.1b |
| 69 | Same-block prohibition cross-link | P3 | WP §5.1 | actionable | editorial WP cross-link |

---

## A. Current vs target documentation drift

### [60] Split WP §5.1 — current CIP-5 FIFO from target CIP-1 auction          (P1, status: actionable)

- **Reviewer source**     : `Whitepaper-Sections-for-Reconsideration.md` §5.1 (HIGH)
- **Reviewer's "current"**: "Whitepaper describes target design (GBA auction); implementation is FIFO within height bucket (CIP-5 v2026-03-19)"
- **Reviewer's proposal** : "Split §5.1 into two clearly-labelled subsections: (a) Currently Implemented (CIP-5): FIFO within height bucket, MAX_TIMERS=1024, 550k cycle/cell budget. (b) Target Design (CIP-1): GBA auction, tiered calendar queue, anti-starvation weights"
- **Actual current state**:
  - WP §5.1 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:126-147`): "**Tiered Calendar Queue.** … three tiers …", "**Gas Bidding Agent (GBA).** … the protocol performs a read-only call to the GBA …", "**Fairness and Liveness.** Deferred timers receive a weighted priority boost with exponential decay …", "Per‑actor timer limit: **256** active timers."
  - CIP-5 §1 (`cip-5-timers.md:17`): "This document describes the timer mechanism **as currently implemented** in the Cowboy node. CIP-1 remains the authoritative specification for the broader Actor Message Scheduler (GBA bidding, tiered calendar queue)."
  - CIP-5 §6.4 (`cip-5-timers.md:303-309`): `max_cycles_per_fire: u64, // default 550_000`, `max_timers_per_actor: u32, // default 1_024`
- **Verification**        : ✅ still accurate — WP §5.1 describes the unimplemented target (tiered calendar, GBA auction, exponential bias, 256-timer cap), while CIP-5 ships FIFO with 1,024-timer cap. Note: WP §5.1 says 256 timers/actor, CIP-5 says 1,024 — additional drift the reviewer didn't catch.
- **Recommendation**      : [WP §5.1 edit]
- **Specific change**     : Split §5.1 into 5.1a "Currently Implemented (CIP-5)" — FIFO within height bucket, `max_timers_per_actor = 1,024`, per-fire 550k cycles/550k cells, `LANE_TIMER_CYCLES = 2,000,000`, per-fire `fee_payer` pre-charge + refund, three-path lifecycle, end-of-block delivery — and 5.1b "Target Design (CIP-1)" — EIP-1559 timer basefee + priority tip, per-actor fairness weight, per-timer cycle cap 250k, default GBA inline. Each subsection carries the spec citation in its header (CIP-5 §3-§8 vs CIP-1 future). Drop the standalone "256 active timers" line from §5.1 — it disagrees with CIP-5 §6.4's 1,024.
- **Rationale**           : Required for any reader (internal or external) to tell live from coming. The reviewer's structural recommendation is sound and cheap; CIP-1 v2 already does this textually but the WP doesn't. The 256-vs-1024 discrepancy is a separate latent drift that surfaces only if §5.1 is rewritten.
- **Open questions**      : Should 5.1b still ship in the WP if CIP-1 is being substantively rewritten, or be reduced to a one-line forward reference? Recommend keeping 5.1b in WP but as a 4-5 sentence summary that points at CIP-1.

### [69] Same-block prohibition needs cross-link to k > 16 surcharge          (P3, status: actionable)

- **Reviewer source**     : `Whitepaper-Sections-for-Reconsideration.md` §5.1 (MEDIUM)
- **Reviewer's "current"**: "§5.1 mentions timers MUST NOT fire in current block; elsewhere mentions exponential same-block surcharge for k > 16 timers"
- **Reviewer's proposal** : "Cross-link the two sections"
- **Actual current state**:
  - WP §5.1 DoS table (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:142`): "Timer bomb (many timers, one block) | Exponential same‑block surcharge: `surcharge(k) = base_cost × 2^max(0, k - 16)`"
  - WP §3.3 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:516-520`): "**Timers (chain‑native):** … Timer delivery is **best‑effort**; execution depends on the GBA auction (see §Timer Rate Limiting)."
  - CIP-5 §5.3 (`cip-5-timers.md:199-201`): "Timers created within the current block's transactions MUST NOT fire in the same block. This is enforced by the `height > current_block_height` constraint in `schedule_timer`."
- **Verification**        : ⚠ partially — the surcharge formula and the same-block prohibition appear in the same DoS table (one row above), so they're already physically adjacent in §5.1. The actual drift is between WP §3.3 ("see §Timer Rate Limiting" — a section that doesn't exist) and CIP-5 §5.3, not within §5.1 itself.
- **Recommendation**      : [WP §3.3 edit + WP §5.1 editorial]
- **Specific change**     : (a) In WP §3.3 line 520, replace the dangling "see §Timer Rate Limiting" with "see §5.1 and CIP-5 §5.3". (b) In WP §5.1 (under the new 5.1a from item #60), add one sentence: "Same-block firing is prohibited (CIP-5 §5.3); for actors that try to schedule many same-height timers, the exponential surcharge `surcharge(k) = base_cost × 2^max(0, k-16)` applies (DoS row above)."
- **Rationale**           : Pure editorial. The dangling `§Timer Rate Limiting` reference is the bigger problem — fix it once §5.1 is split anyway.
- **Open questions**      : None.

---

## B. Auction mechanism (CIP-1 / CIP-5 §9 redesign)

### [13] GBA invalid-bid handling unspecified          (P1, status: resolved by mechanism change)

- **Reviewer source**     : `design-review_findings.md` item [13]; `Design-review.md` Section 6, GBAs row
- **Reviewer's "current"**: "What happens if a GBA returns an invalid or maliciously high bid — is the bid clamped, rejected, or does it succeed and drain the owner?"
- **Reviewer's proposal** : "(none specific — flagged as major area of ambiguity requiring simulation)"
- **Actual current state**:
  - CIP-1 v1 §4.2 / CIP-5 §9.7 (`cip-5-timers.md:466-481`): "`bid: int = 0, # NEW: CBY bid for execution priority` … The `bid` is locked at scheduling time and refunded (minus payment) or fully consumed depending on the payment rule, debited from the same `fee_payer` account used for per-fire gas."
  - CIP-5 §9.5 (`cip-5-timers.md:436-456`): "**Target: Greedy VCG** … Winner pays: `bid(runner_up) - Bias(winner)` (floored at the reserve price). **Fallback: First-price auction**".
  - No clamping rule, no validation of GBA-returned bid, no upper bound. A GBA returning `bid = balance(fee_payer)` would drain on a single fire.
- **Verification**        : ✅ still accurate — there is no clamping, no rejection, no upper bound; CIP-5 §9 is silent on invalid GBA returns. The closest defence is the `fee_payer` balance check (CIP-5 §6.3 step 3), which only catches "insufficient funds", not "too high".
- **Recommendation**      : [amend CIP-1 — SUBSTANTIAL REWRITE per recommendation #1 in this document's header]
- **Specific change**     : Replace the first-price/VCG `bid` parameter with an EIP-1559-style `(max_fee_per_cycle, max_priority_fee_per_cycle)` pair. Validation is structural: `max_fee_per_cycle ≥ basefee` is enforced at schedule time (else reject), `max_priority_fee_per_cycle` is implicitly bounded by `max_fee_per_cycle - basefee`. A "maliciously high" GBA return now means a high priority tip — still bounded by `fee_payer` balance via the `max_cost` pre-charge at fire time (CIP-5 §6.3 step 4). No drain attack survives, because the per-fire `max_cost` ceiling already pins the worst-case debit per fire.
- **Rationale**           : This is one of the strongest arguments for the EIP-1559 hybrid: the invalid-bid attack class disappears entirely under EIP-1559 semantics. Six years of EVM operations show no production-class incident where a sophisticated wallet drained itself via tip-overpayment — the structural ceiling holds.
- **Open questions**      : (1) Should `max_priority_fee_per_cycle` itself carry a protocol cap (e.g., `≤ 100 × current_basefee`) as belt-and-suspenders? Recommend no; the per-fire `max_cost` ceiling is already the operational guard. (2) For pre-EIP-1559 CIP-5 callers, the answer to "what if the bid field isn't supplied" is the trivial "use defaults" — clean migration.

### [23] Default GBA disadvantages unsophisticated actors          (P2, status: actionable)

- **Reviewer source**     : `Design-review.md` Section 7.2 item 3; `design-review_findings.md` item [23]
- **Reviewer's "current"**: "GBA auction is not yet live — CIP-5 ships FIFO within height bucket, defers auction to Phase 3. If default GBA is conservative and third-party GBAs more aggressive, actors using defaults systematically deprioritised — creating pressure toward third-party GBA services, which could centralise"
- **Reviewer's proposal** : "(none specific — flags risk; asks for default GBA spec)"
- **Actual current state**:
  - WP §5.1 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:132`): "Actors that do not specify a GBA receive a protocol‑provided default that bids conservatively."
  - CIP-1 v1 §4.1 — no spec of what "conservatively" means.
  - CIP-5 §9.9 (`cip-5-timers.md:498-501`): "Calibration of λ … Reserve price level … VCG revenue gap … Interaction with CIP-1 GBA" — all open, no commitment.
- **Verification**        : ✅ still accurate — "default GBA bids conservatively" is the only existing spec. Under first-price-per-cycle this is a real centralisation pressure (item #23 is correct). Under the EIP-1559 hybrid it becomes a non-issue because the default GBA *is* the optimal strategy for most actors (analogous to MetaMask's default gas estimator on EVM).
- **Recommendation**      : [amend CIP-1 — SUBSTANTIAL REWRITE]
- **Specific change**     : In the rewritten CIP-1, specify the default GBA inline (≈2 lines): `max_fee_per_cycle = 2 × current_basefee` and `max_priority_fee_per_cycle = previous_block_p50_priority_tip`. SDK offers `priority_tier_hint ∈ {economy, standard, fast, urgent}` mapping to `{0.8×, 1.0×, 1.5×, 2.5×}` multipliers on `max_priority_fee_per_cycle`. WP §5.1b carries one-sentence summary; the normative spec lives in CIP-1.
- **Rationale**           : The reviewer's centralisation worry is real under first-price (default = doormat). Under EIP-1559 the default is fee-efficient by construction — sophisticated third-party "GBA-as-a-service" buys you marginal latency at most, not access. Six years of EVM wallets demonstrate the equilibrium.
- **Open questions**      : (1) Should `priority_tier_hint` multipliers be governance-tunable (Tier 2) at launch, or hardcoded? Recommend governance-tunable, so Phase-5 simulation can tighten them. (2) Should `previous_block_p50_priority_tip` fall back to 0 when the prior block had zero timer activity? Yes — and document.

### [28] Gap G7 — default GBA spec          (P2, status: actionable)

- **Reviewer source**     : `Design-review.md` Gap G7; `design-review_findings.md` item [28]
- **Reviewer's "current"**: "Default GBA provided for protocol but its bidding strategy is not specified … Required to model timer market dynamics; interaction with basefee under congestion is unknown"
- **Reviewer's proposal** : "Specify protocol-default GBA bidding strategy for Phase 3 shipping"
- **Actual current state**: Same as item #23 — WP §5.1:132 says "bids conservatively" with no formal spec; CIP-1 v1 silent on numeric default; CIP-5 §9.9 lists open questions but commits to nothing.
- **Verification**        : ✅ still accurate — G7 remains an open gap in both CIP-1 and CIP-5.
- **Recommendation**      : [amend CIP-1 — closes G7 inline]
- **Specific change**     : Identical to item #23 above. G7 is just the gap-register name for the same spec deficit; one spec edit closes both.
- **Rationale**           : Caleb owns G7 internally (per item #44 / Cowboy team notes). The EIP-1559 hybrid converts the question from "design a default GBA bidding strategy" (open-ended research) to "specify a two-parameter estimator" (mechanical, ~2 lines).
- **Open questions**      : Once the EIP-1559 hybrid lands, G7 closes automatically. If the team rejects the rewrite and ships first-price as originally designed (CIP-1 Concept A), the default GBA spec is much harder — Phase-5 simulation against bidding strategies becomes a precondition for shipping.

### [44] Caleb owns G7          (P2, status: resolved by recommendation)

- **Reviewer source**     : `Design-Review-Summary-Cowboy-Input.md` Section 4, Gap G7 notes
- **Reviewer's "current"**: "Gap G7 marked with 'Cowboy - tbh not sure what our v1 is here - Caleb owns'"
- **Reviewer's proposal** : "Caleb to define the v1 default GBA bidding strategy"
- **Actual current state**: Ownership note only — no spec. See item #28.
- **Verification**        : ➖ not addressed in any CIP/WP — purely an internal-ownership marker.
- **Recommendation**      : [no change to CIPs] (resolved once items #23 / #28 land)
- **Specific change**     : Caleb signs off on the default GBA spec proposed in items #23 / #28 (or proposes alternative). No CIP/WP edit specifically for this item.
- **Rationale**           : Process artefact, not a normative deficit. Closes once the default GBA is specified.
- **Open questions**      : None.

---

## C. Default GBA bidding strategy

(Items #23, #28, #44 above all cover this. Single concrete spec for CIP-1 rewrite:)

```
Default GBA, normative (CIP-1 rewrite):
  max_fee_per_cycle         = 2 × current_basefee
  max_priority_fee_per_cycle = previous_block_p50_priority_tip   (default 0 if prior block had no timer activity)

SDK convenience layer (informative):
  priority_tier_hint ∈ {economy, standard, fast, urgent}
  multiplier        ∈ {0.8×,    1.0×,     1.5×,  2.5×}     on max_priority_fee_per_cycle
```

Per-actor fairness weight `W(actor) ∈ [1, 2]` over 1000-block rolling window applied multiplicatively to the priority tip at inclusion-ordering time. Per-timer cycle cap 250k (auction-phase only). Timer-lane multiplier 1.0× flat.

---

## D. Decision-register entries from this topic

1. **Adopt EIP-1559 hybrid in place of first-price auction (CIP-1 substantial rewrite)?** — Recommended YES. First-price-per-cycle is unstable in repeated knapsack settings (well-documented literature); EIP-1559 reuses six-year-mature EVM patterns; default-GBA spec collapses to two lines (closes G7); invalid-bid attack class disappears structurally (item #13). Cost: substantial rewrite of CIP-1 Part I + retirement of CIP-5 §9 (target moves to CIP-1).

2. **Pin Timer-lane multiplier at 1.0× vs subsidy 0.8×?** — Recommended 1.0× flat. Concept B's 0.8× subsidy costs ~20% lane burn revenue (WP §11.5: 100% basefee burned). Per-actor fairness weight already addresses monopolisation. Revisit only if Phase-5 simulation shows monopolisation despite the weight.

3. **Per-timer cap 250k cycles (12.5% of 2M lane) — confirm vs current 550k?** — Recommended: keep CIP-5 §6.4 at 550k for now, introduce 250k *only* with auction activation in CIP-1. The 250k cap exists to prevent single-timer auction-lane monopolisation — irrelevant under FIFO. Mixing the two values mid-spec creates a needless migration question.

4. **Per-actor fairness weight as second-order rule — adopt?** — Recommended YES, with explicit fragmentation-attack acknowledgement. `W(actor) ∈ [1, 2]` over 1000-block window, multiplied into priority tip at inclusion-ordering. Open: fragmentation attack (sophisticated dev deploys 100 actor instances). Phase-5 simulation to size, with per-deployer weight as fallback if fragmentation magnitude is material.

5. **CIP-5 §9 status post-rewrite?** — REMOVE CIP-5 §9 (the future-auction subsection); target design moves entirely to CIP-1. CIP-5 stays narrow to "currently implemented FIFO + per-fire fee model" and is relabelled "current implementation, sunset on CIP-1 ship".

---

## E. New CIPs proposed (or substantial amendments)

- **CIP-1: SUBSTANTIAL REWRITE.** Replace Part I's first-price auction + tiered calendar queue + exponential-bias mechanism with EIP-1559 timer basefee + priority tip + per-actor fairness weight. Default GBA spec inline (closes Gap G7). Per-timer cap 250k cycles. Timer-lane multiplier 1.0× flat. Migration: existing CIP-1 v2 (Part II, alignment-with-CIP-5 doc) becomes obsolete on rewrite — folded back into a coherent single document. The `bid: int` parameter on `schedule_timer` (CIP-5 §9.7) is dropped in favour of `(max_fee_per_cycle, max_priority_fee_per_cycle)`.

- **CIP-5 §9 (future-auction subsection): REMOVE.** Target moves entirely to CIP-1. CIP-5 §§1-8 (current FIFO, per-fire fee_payer model, three-path lifecycle, lane budgets) remain unchanged for now. Relabel CIP-5's header tip: "current implementation, sunset on CIP-1 (rewrite) ship". CIP-5 §9.9 open questions either resolve in CIP-1 (G7, λ calibration, VCG revenue) or evaporate (reserve price, interaction with CIP-1 GBA).

- **WP §5.1: SPLIT.** Subsection 5.1a "Currently Implemented (CIP-5)" — FIFO within height bucket, 1024-timer-per-actor cap, 550k per-fire cycles/cells, `LANE_TIMER_CYCLES = 2,000,000`, per-fire `fee_payer` pre-charge + refund, EOB delivery. Subsection 5.1b "Target Design (CIP-1, rewrite)" — EIP-1559 timer basefee + priority tip, per-actor fairness weight, per-timer 250k cycles, default GBA `(2× basefee, p50 priority tip)`. Each subsection cites its CIP. Drop the legacy "256 active timers" line — disagrees with CIP-5 §6.4's 1,024.

- **WP §3.3: EDITORIAL.** Replace dangling "(see §Timer Rate Limiting)" reference on line 520 with "(see §5.1 and CIP-5 §5.3)". Closes item #69.
