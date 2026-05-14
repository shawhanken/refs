# 🥌 Timer + GBA Concept Selection

<!-- Notion page id: f91e6c7d-52db-8395-bcad-814f75d1727c -->

*Prepared by Vending Machine · April 2026 · Status: Draft for Cowboy team review*


---


### Abstract

This document is the Phase 3 (Concept Selection) output for the **Timer Auction + Gas Bidding Agent (GBA)** subsystem of the Cowboy Protocol. It systematically evaluates the three concepts produced in the Phase 2 Concept Generation document against the network objectives defined in the Phase 1 Design Review §9.2, using the four progressively quantitative tools prescribed by the modified MBSE process: a written qualitative comparison, an unweighted Pugh matrix, a weighted Pugh matrix (-3 to +3), and a utility-function calculation that incorporates the operator's importance weightings on each objective.

The three concepts under evaluation are:

- **Concept A (Datum) - Whitepaper Target Closure.** First-price-per-cycle auction with capped exponential bias (5×) and a vanilla-multiplier default GBA. Smallest deviation from the team's existing CIP-1 intent.
- **Concept B - Uniform-Price + Per-Actor Fairness.** Greedy VCG-approximation clearing, per-actor fairness weight replacing per-timer exponential bias, value-aware default GBA, 0.8× lane multiplier as a launch subsidy.
- **Concept C - EIP-1559 Timer Basefee.** Drops the per-block auction; uses a Timer-lane EIP-1559 mechanism (basefee adjusts to lane utilisation; priority tip orders inclusion). Reuses industry-standard wallet fee estimation.
The four objectives this document scores against are §9.2 #7 (Timer Liveness and Fairness), #8 (Predictable Fee UX), #3 (Developer Attraction and Retention), and #4 (Long-run Fee Sustainability). The Cowboy team's importance weightings (Tool 4) are reproduced in the Utility Function section below.

The headline result: **Concept C - EIP-1559 Timer Basefee** wins the utility ranking with a score of +220, narrowly ahead of **Concept B** (+210), with **Concept A** as the datum (0). The 10-point margin between C and B is approximately 4.5% of the leader's score - well inside the MBSE defined "close-call" band (within 10%) - meaning the ranking is *not* decisive on the numbers alone and the qualitative reasoning carries unusual weight. The recommendation section below explains why Concept C is still the right base mechanism to take into Phase 4, but with Concept B's per-actor fairness weight bolted on as an explicit second-order rule. A Critical Design Review authored against this hybrid would dominate either pure concept on the operator's stated weightings.


---


### Network Objectives (Reference)


| # | Objective | Brief description | Consequence of Objective failure |
|---|---|---|---|
| 7 | **Timer Liveness and Fairness** | Non-adversarial timers fire within a bounded delay from their scheduled block, even under congestion, and no single actor can monopolise the timer lane. Conflicts with #8. |  |
| 8 | **Predictable Fee UX** | Wallet-level fee estimation achieves within-X% accuracy across 95% of transactions under normal load. Conflicts with #7. |  |
| 3 | **Developer Attraction and Retention** | Attract Python-competent developers and AI/agent builders in sufficient numbers to populate the actor ecosystem within the first 24 months. |  |
| 4 | **Long-run Fee Sustainability** | Achieve a state within a defined horizon where fee revenue (basefees burned + tips + runner flows) sufficiently rewards validators/runners without dependence on inflation. |  |

§9.4 of the Design Review explicitly flags #7 and #8 as opposed: *"aggressive GBA auctioning produces volatile, unpredictable effective fees for timer-using actors."* Resolving that tension is the central decision this Phase-3 process makes.


---


### Tool 1: Qualitative Comparison


#### Concept B - Uniform-Price + Per-Actor Fairness - vs Datum (Concept A)

**Objective #7 - Timer Liveness and Fairness.** Concept B replaces Concept A's per-timer exponential bias multiplier with a per-actor fairness weight `W(actor) ∈ [1, 2]` derived from the actor's recent execution rate vs the network median over a 1,000-block rolling window. The structural difference matters: Concept A's bias is *retrospective and per-timer* (a timer earns bias by being deferred, which can be partially gamed by spamming low-bid timers to accumulate bias on each), whereas Concept B's weight is *prospective and per-actor* (an actor that has captured fewer recent slots than the median gets an explicit boost on its current bids, regardless of how many timers it submits). The bias-gaming attack Caleb explicitly flagged in the 27 April discussion is structurally impossible against Concept B because the weight is applied to bid × cycle product, not accumulated per-timer-deferral. Concept B is also more directly aligned with the literal text of Objective #7's "no single actor can monopolise the timer lane" - the per-actor weight is a direct enforcement of that property. Verdict: **+** (significantly better).

**Objective #8 - Predictable Fee UX.** Concept B's uniform-price clearing produces a smoother price trajectory than Concept A's first-price clearing because winners pay the *highest losing* bid per cycle rather than their own bid; this caps the upside of sophisticated bidders and pulls the realised price toward the network's marginal value-of-execution. Concept B also publishes the clearing price at block close, giving actors and GBAs a public anchor for next-block estimation. However, the realised price still depends on the bid distribution within each block, which is inherently more variable than Concept C's EIP-1559 basefee-and-tip model. Verdict: **+** (somewhat better).

**Objective #3 - Developer Attraction and Retention.** Concept B's value-aware default GBA means a developer can ship an actor with the protocol-default GBA and not be systematically out-competed by sophisticated third-party GBAs - because honest bidding is weakly dominant under uniform-price, sophistication offers no edge in the *bidding* step. Sophistication can still help in the *value-estimation* step (knowing the actor's marginal value), but that is application-specific work the developer would do anyway. Concept A's first-price design, by contrast, creates an asymmetric advantage for sophisticated GBAs that ratchets pressure on developers to either build custom GBAs or pay for GBA-as-a-service - which is exactly the centralisation pressure Risk R4 flagged. Verdict: **+** (somewhat better).

**Objective #4 - Long-run Fee Sustainability.** Concept B sets the per-lane fee multiplier (whitepaper §11.5 reconsideration) at 0.8× as an explicit launch-period timer subsidy - an immediate 20% reduction in fee flow from this subsystem relative to Concept A's 1.0× setting. Timer-lane fees are a relatively small share of total fee flow today, but at scale this is real revenue forgone. The rationale (subsidising timer adoption to drive ecosystem growth) is defensible but is in direct tension with #4. The hypothesis that lower lane multiplier produces more timer activity which produces more *total* fees is a testable Phase-5 simulation question; under conservative assumptions (no demand elasticity from the multiplier change) the immediate burn-flywheel impact is negative. Verdict: **−** (somewhat worse).


#### Concept C - EIP-1559 Timer Basefee - vs Datum (Concept A)

**Objective #7 - Timer Liveness and Fairness.** Concept C eliminates the bias multiplier entirely and relies on the basefee-falling-when-lane-under-utilised dynamic for anti-starvation. This is a *prospective* mechanism - the price drops to meet demand - but it is contingent: it works as a fairness mechanism only when lane utilisation actually falls. Under sustained congestion (utilisation > 50% for many blocks), the basefee keeps rising and a deferred timer with `max_fee_per_cycle` below the rising basefee gets stuck rolling forward indefinitely. There is no explicit per-actor or per-timer fairness mechanism; ordering within a block is purely by `priority_tip_per_cycle`. The 250k per-timer cycle cap (12.5% of lane) prevents single-timer monopolisation, and EIP-1559's smoother price trajectory does prevent some pathological cases compared to Concept A's first-price + bias, but the absence of an explicit fairness rule is a real regression on the literal objective text ("no single actor can monopolise the timer lane"). An actor willing to pay aggressive priority tips can dominate the lane during congestion in ways Concept B's per-actor weight would prevent. Verdict: **−** (somewhat worse).

**Objective #8 - Predictable Fee UX.** This is Concept C's strongest dimension by a wide margin. EIP-1559 has been live on Ethereum since August 2021; every wallet, RPC, SDK, and indexer in the EVM ecosystem already implements its fee estimation. Cowboy timer-fee estimation reuses that code path verbatim. The basefee adjustment is bounded (max 12.5% per block) and deterministic given the previous block's lane utilisation, so wallets can compute next-block basefee with no uncertainty. The priority tip is ordered by per-cycle value, which is what every Ethereum-style wallet already estimates. The default GBA spec collapses to two lines of code (`max_fee = 2 × basefee, max_priority_fee = previous_block_p50_priority_tip`) — exactly MetaMask's "Medium" preset, generalised to a per-cycle metric. Concept A's first-price clearing volatility is well-documented as the single biggest contributor to Ethereum's pre-EIP-1559 UX problems. The empirical evidence base is overwhelming. Verdict: **+** (dramatically better).

**Objective #3 - Developer Attraction and Retention.** Concept C inherits the EIP-1559 developer ergonomics that the EVM ecosystem has standardised around. A Python developer using Cowboy SDK does not need to understand auctions, bias multipliers, or value-aware GBAs - they set `max_fee_per_cycle` and `max_priority_fee_per_cycle` and the rest is handled by the SDK estimator. Concept A's first-price + bias system requires either using the (systematically-disadvantaged) default GBA or building a custom GBA - both of which add cognitive load. The `priority_tier_hint` overlay (`{economy, standard, fast, urgent}` mapped to tip multipliers) gives developers familiar UX vocabulary that maps directly to MetaMask gas presets. Verdict: **+** (significantly better).

**Objective #4 - Long-run Fee Sustainability.** Concept C uses a 1.0× lane multiplier (same as Concept A), and the basefee burn dynamic mirrors the whitepaper's §11.5 intent ("basefees 100% burned, tips to proposer"). There is one subtlety: under congestion, Concept C's priority-tip share grows relative to the basefee share (because the basefee is bounded below by the EIP-1559 adjustment), which means more revenue routes to validators and less to burn during peak demand. Over the full price cycle this is approximately a wash - the basefee rises to absorb most of the demand pressure - and the long-term burn flywheel is preserved. Verdict: **S** (roughly the same).


---


### Tool 2: Pugh Matrix


| Objective | Concept A (Datum) | Concept B | Concept C |
|---|---|---|---|
| #7 — Timer Liveness and Fairness | DATUM | + | − |
| #8 — Predictable Fee UX | DATUM | + | + |
| #3 — Developer Attraction | DATUM | + | + |
| #4 — Long-run Fee Sustainability | DATUM | − | S |
| **Total +** | — | **3** | **2** |
| **Total −** | — | **1** | **1** |
| **Total S** | — | **0** | **1** |
| **Net Score** | 0 | **+2** | **+1** |


#### Pugh Matrix Analysis

Both alternatives dominate the datum on the simple Pugh count: every concept beats Concept A on at least two objectives. Concept B has the higher net Pugh score (+2 vs +1) because its strengths span three objectives (#7, #8, #3) while Concept C's strengths span only two (#8, #3) and it carries a real weakness on #7. The simple Pugh matrix slightly favours Concept B.

This is, however, a misleading first read. The unweighted Pugh treats a small advantage and a large advantage equally - it cannot distinguish "Concept C is *dramatically* better on #8" from "Concept B is *somewhat* better on #8." The weighted Pugh below makes those magnitudes explicit; once that's done, the picture flips.


---


### Tool 3: Weighted Pugh Matrix (-3 to +3)

Scale: **+3** dramatically better, **+2** significantly better, **+1** somewhat better, **0** same, **−1** somewhat worse, **−2** significantly worse, **−3** dramatically worse.


| Objective | Concept A (Datum) | Concept B | Concept C |
|---|---|---|---|
| #7 — Timer Liveness and Fairness | 0 | **+2** | **−1** |
| #8 — Predictable Fee UX | 0 | **+1** | **+3** |
| #3 — Developer Attraction | 0 | **+1** | **+2** |
| #4 — Long-run Fee Sustainability | 0 | **−1** | **0** |
| **Total Score** | **0** | **+3** | **+4** |


#### Weighted Pugh Analysis

Once magnitudes are accounted for, the ranking shifts back to Concept C: its +3 on Predictable Fee UX is the single largest individual cell on the matrix and reflects a structural advantage (reuse of the most-deployed fee mechanism in the industry) that is qualitatively different from any of Concept B's +1/+2 advantages. The intuition is that a +3 on a single critical objective is hard to overcome with three +1s on other objectives.

That said, the +1 difference at the unweighted-score level (Concept C +4 vs Concept B +3) is small in absolute terms, and once Tool 4's importance weights are applied with #7 = 80 (the operator's chosen weight, the highest of the four), the picture compresses further: Concept C's −1 on #7 becomes a 80-point utility penalty, while Concept B's +2 on the same objective becomes a 160-point utility gain. The end result is a 10-point Concept-C win - within the close-call band - for which the qualitative reasoning carries unusual weight.

The most useful insight from the weighted matrix is *structural*: Concepts B and C have largely complementary strength profiles. Concept B is the per-actor-fairness specialist; Concept C is the predictability-and-DevX specialist. Concept A is dominated on every dimension where it matters and survives in this analysis only because it represents the team's existing intent and lowest-implementation-cost path. The Recommendation section returns to whether B and C can be combined - and concludes that they can and should be.


---


### Tool 4: Utility Function


#### Objective Importance Weightings

These weightings were provided by the operator (Vending Machine, on behalf of the Cowboy engagement) on 30 April 2026:


| # | Objective | Importance (0–100) |
|---|---|---|
| 7 | Timer Liveness and Fairness | **80** |
| 8 | Predictable Fee UX | **70** |
| 3 | Developer Attraction and Retention | **45** |
| 4 | Long-run Fee Sustainability | **65** |

The slight lift on #7 (80) over #8 (70) reflects an explicit operator judgement that fairness - the literal "no single actor can monopolise the timer lane" property - should weigh marginally more than predictability when the two are forced into trade-off, even though Caleb's 27 April framing emphasised DevX as a meta-priority. This calibration matters: it cuts the gap between Concepts C and B from 22% to 4.5%, which the recommendation section addresses head-on. The #4 weight (65) signals that long-run sustainability is treated as comparably important to the directly-subsystem-relevant objectives despite this subsystem contributing only a fraction of total fee flow. The #3 weight (45, "moderate") deliberately discounts developer attraction to avoid double-counting the predictability-related share of #3 that is already captured under #8.


#### Utility Calculation

**Utility = Σ (Weighted Pugh Score × Objective Importance)**


| Objective | Importance | Concept A (Datum) |  | Concept B |  | Concept C |  |
|---|---|---|---|---|---|---|---|
|  |  | Score | Utility | Score | Utility | Score | Utility |
| #7: Timer Liveness and Fairness | 80 | 0 | 0 | +2 | **+160** | −1 | **−80** |
| #8: Predictable Fee UX | 70 | 0 | 0 | +1 | **+70** | +3 | **+210** |
| #3: Developer Attraction | 45 | 0 | 0 | +1 | **+45** | +2 | **+90** |
| #4: Long-run Fee Sustainability | 65 | 0 | 0 | −1 | **−65** | 0 | **0** |
| **Total Utility** |  |  | **0** |  | **+210** |  | **+220** |


#### Final Ranking


| Rank | Concept | Total Utility Score | Margin vs Next |
|---|---|---|---|
| 🥇 1 | **Concept C: EIP-1559 Timer Basefee** | **+220** | +10 |
| 🥈 2 | Concept B: Uniform-Price + Per-Actor Fairness | +210 | +210 |
| 🥉 3 | Concept A: Whitepaper Target Closure (Datum) | 0 | — |

The 10-point margin between Concept C and Concept B is approximately **4.5% of Concept C's total utility** - well inside the MBSE framework’s "close-call" band (within 10%). **The numerical ranking is therefore not decisive on its own**, and the qualitative reasoning behind the placement carries more weight than usual. Concept C wins on the strength of its +3 on Predictable Fee UX (a structural advantage from reusing six years of EIP-1559 deployment); Concept B is held back primarily by the −1 on Fee Sustainability (the 0.8× lane multiplier subsidy). If Cowboy is willing to drop Concept B's lane subsidy and ship at 1.0×, that single change adds back +65 utility and Concept B leapfrogs Concept C at +275. This is one of the choices the recommendation section asks the team to make explicitly.

The 210-point margin between Concept B and Concept A is decisive. Concept A - i.e., the whitepaper's target design as written - is dominated by both alternatives under any reasonable weighting that places non-trivial weight on Predictable Fee UX or on Timer Liveness/Fairness. This is the most important finding of the Phase-3 analysis: **the team's current intent is the weakest of the three options on the network's own stated objectives.**


---


### Recommendation

**Concept C: EIP-1559 Timer Basefee - is the recommended winning design for Phase 4 (Critical Design Review), but only marginally over Concept B and only as the *****base mechanism***** for a hybrid that incorporates Concept B's per-actor fairness weight.** The 10-point utility margin (4.5%) is small enough that the qualitative reasoning behind the choice - not the numerical scores - should drive the Phase-4 decision. The reasoning that puts Concept C ahead is structural rather than circumstantial: it inherits the most-deployed fee mechanism in the industry and, in doing so, solves the Predictable Fee UX objective by reuse rather than by design. Cowboy’s meta-priority - *"easy and predictable for developers"* - is delivered by Concept C with the smallest specification surface area and the largest pre-existing implementation base across SDKs, wallets, and infrastructure. The path to TGE is also the lowest-risk among the three concepts because the mechanism has six years of mainnet operation across Ethereum and its derivatives.

That said, Concept C has a real and acknowledged weakness on Objective #7 (Timer Liveness and Fairness - weight 80, the highest individual weight): it relies on the basefee-falling dynamic for anti-starvation rather than an explicit per-actor or per-timer fairness rule. Under sustained congestion this can let high-tip actors monopolise the lane in ways that Concept B's per-actor weight would explicitly prevent. With the operator's #7 weight at 80, this single −1 score costs Concept C 80 utility - and is the single largest reason the C-vs-B margin is only 10 points instead of the 40 it would have been at #7 = 70. The recommended Phase-4 framing is therefore **not "ship Concept C as written"** but **"ship Concept C as the base mechanism, with Concept B's per-actor fairness weight bolted on as an explicit second-order rule."** Concretely:

- The base mechanism is Concept C: Timer-lane EIP-1559 basefee, priority tip orders inclusion, default GBA is the EIP-1559 estimator, no per-block auction.
- On top of that, the inclusion-ordering step is modified so that ranking within a block is by `priority_tip_per_cycle × W(actor)` rather than by `priority_tip_per_cycle` alone, where `W(actor) ∈ [1, 2]` is Concept B's per-actor fairness weight computed from the rolling 1,000-block execution history.
- This adds one piece of state (the per-actor execution counter) and one multiplication to the inclusion-ordering rule, but otherwise preserves the EIP-1559 mechanics and the wallet/SDK reuse.
This hybrid is *not* a fourth concept - it is Concept C with the strongest single mechanism from Concept B added in. It captures Concept C's +3 on Predictable Fee UX (the basefee, default GBA spec, and SDK reuse are all unchanged) and lifts its #7 score from −1 to approximately +1, which would add 160 utility and push the recomputed score to ~+380 - well clear of either pure concept. We recommend the Phase-4 Critical Design Review be authored against this hybrid rather than against either pure concept.

Three flags worth surfacing for the Cowboy team before Phase 4 authoring begins:

1. **The numerical ranking is genuinely close.** A 10-point gap on a 220-point leader is within normal cell-judgement noise (the score-by-score reasoning in Appendix A could reasonably move ±1 unit per cell, which translates to ±~70 utility per cell). The team should not treat the C-over-B ranking as a strong endorsement of C over B - it should treat it as evidence that the hybrid is the right answer because both concepts contribute essential mechanisms.
1. **The single biggest lever is Concept B's lane multiplier.** Concept B as scored takes a −1 on #4 (Fee Sustainability) for the 0.8× lane subsidy, which costs −65 utility. If the Cowboy team decides not to subsidise the timer lane and ships Concept B at 1.0×, that −65 disappears and Concept B leapfrogs Concept C at +275. If the team has strong views on whether to subsidise timer adoption, that decision is *upstream* of the C-vs-B selection and should be made first.
1. **Concept B's per-actor fairness weight has a known fragmentation risk** that the recommended hybrid inherits. A sophisticated developer could deploy 100 actors each running a fragment of one workload, gaming the per-actor weight by treating each as a separate "quiet" actor. The cleanest mitigation is to compute `W(deployer)` (using the actor-deployment trace) rather than `W(actor)`, but this requires deeper actor metadata than CIP-2 currently exposes. This should be a Phase-5 simulation question and a Phase-4 implementation note.

---


### Disclaimer

This documentation is provided for informational purposes only and is based on a modified version of MIT's Model-Based Systems Engineering process adapted for blockchain mechanism design. It does not constitute financial, investment, or legal advice. All concepts described are design proposals; none has been implemented, audited, or formally verified. The utility scores presented are derived from Vending Machine's expert judgement on the relative magnitudes of each concept's effect on each objective, scaled by the operator-supplied importance weightings; reasonable practitioners could disagree on individual cell values within ±1 unit, and the operator should treat the ranking as a structured input to the Phase-4 design decision rather than as a definitive verdict. References to external protocols (Ethereum / EIP-1559, Solana, Bitcoin, Cosmos, Optimism / Arbitrum / Base, Gelato) describe their public mechanism designs as of April 2026. References to the Cowboy whitepaper, CIPs, and the 27 April 2026 Cowboy/Caleb timer-auction discussion reflect public and internal documentation available as of the document date and may be superseded by subsequent Cowboy team decisions. Vending Machine makes no representation that any specific concept or parameter will be selected by the Cowboy team, nor about the eventual launch parameters of the Cowboy Protocol.


---


### Appendix A — Score-by-score reasoning summary (for cross-checking)

For convenience, the table below collapses the qualitative reasoning into one row per (Concept × Objective) cell with a one-line justification for the weighted Pugh score. Use this as a quick sanity-check before Phase 4 commits.


| Cell | Score | One-line justification |
|---|---|---|
| B × #7 | +2 | Per-actor fairness weight is prospective and per-actor; closes the bias-gaming attack at source. |
| B × #8 | +1 | Uniform-price clearing smoother than first-price; honest bidding weakly dominant per Caleb 27 Apr. |
| B × #3 | +1 | Default GBA is competitive without sophistication; closes R4 at source. |
| B × #4 | −1 | 0.8× lane multiplier is an explicit ~20% subsystem fee subsidy; revenue forgone at launch. |
| C × #7 | −1 | No explicit fairness rule; basefee-drop is contingent on lane under-utilisation; per-timer 250k cap mitigates monopolisation but doesn't enforce per-actor fairness. |
| C × #8 | +3 | Reuses six-year-old EIP-1559 wallet/SDK fee estimation across the entire EVM ecosystem; predictability solved by reuse. |
| C × #3 | +2 | Industry-standard fee UX; default GBA is a two-line wallet estimator; `priority_tier_hint` overlay maps to MetaMask presets. |
| C × #4 | 0 | 1.0× lane multiplier preserves burn share; tip-vs-burn share shifts under congestion but net long-run burn is approximately preserved. |


---


### Appendix B - Sources

- *Cowboy Protocol — System Architecture Design Review*, Vending Machine, April 2026 (Notion).
- *Cowboy Timer Auction + GBA — Concept Generation*, Vending Machine, April 2026 (Notion) — the Phase 2 source document this Phase 3 evaluates.
- *Cowboy meets with Caleb regarding Timers/Auctions*, internal meeting transcript, 27 April 2026.
- *🥾 Whitepaper Sections for Reconsideration*, Vending Machine, April 2026 (Notion) — §5.1 split between current FIFO (CIP-5 rev 2026-03-19) and target GBA auction (CIP-1).
- EIP-1559 mechanism design — [Ethereum EIPs / EIP-1559 spec](https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1559.md); [Decentralized Thoughts — ](https://decentralizedthoughts.github.io/2022-03-10-eip1559/)[*EIP-1559 In Retrospect*](https://decentralizedthoughts.github.io/2022-03-10-eip1559/)[ (2022)](https://decentralizedthoughts.github.io/2022-03-10-eip1559/); [Empirical Analysis of EIP-1559 (arXiv 2201.05574)](https://arxiv.org/pdf/2201.05574).
- Auction theory references — [Wikipedia — Knapsack auction](https://en.wikipedia.org/wiki/Knapsack_auction); [Wikipedia — Vickrey–Clarke–Groves auction](https://en.wikipedia.org/wiki/Vickrey%E2%80%93Clarke%E2%80%93Groves_auction); [Ausubel — ](https://www.cs.cmu.edu/~sandholm/cs15-892F15/Ausubel_Auction_Theory_Palgrave.pdf)[*Auction Theory for the New Economy*](https://www.cs.cmu.edu/~sandholm/cs15-892F15/Ausubel_Auction_Theory_Palgrave.pdf).
