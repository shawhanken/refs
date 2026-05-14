# 🏠 Cowboy Runner Marketplace Concept Selection

<!-- Notion page id: 43fe6c7d-52db-8248-948c-81778b5c732a -->

*Prepared by Vending Machine · April 2026 · Status: Draft for Cowboy team review*


---


### Abstract

This document is the Phase 3 (Concept Selection) output for the **Runner Marketplace** subsystem of the Cowboy Protocol. It systematically evaluates the three concepts produced in the Phase 2 Concept Generation document against five network objectives drawn from the Phase 1 Design Review §9.2, using the four progressively quantitative tools prescribed by the modified MBSE process: a written qualitative comparison, an unweighted Pugh matrix, a weighted Pugh matrix (-3 to +3), and a utility-function calculation that incorporates the operator's importance weightings.

The three concepts under evaluation are:

- **Concept A (Datum) - Closed-Form Whitepaper.** Minimum-change closure of CIP-2/CIP-13 as written: static `M=5, N=3` committee, non-reveal classified as operational failure, linear ±1 reputation, fixed aggregator bonus (2% of runner share), 100% burn of slashed stake (preserves C7), CBY-denominated stake floor, no commission cap.
- **Concept B - Optimistic Marketplace + Challenger Bounty.** Adaptive committee on Herfindahl, fractional 25% non-reveal slash, 50/30/20 challenger/burn/treasury split (requires C7 amendment), Bittensor-style EMA reputation, USD-pegged stake floor, commission cap 30%/floor 5%, 25% delegator weight on runner-parameter proposals.
- **Concept C - Tiered Trust Marketplace.** Bifurcates into Lane V (TEE/ZK, M=1, no output slashing) and Lane R (Concept B's full mechanism). Subsidy split 60/40 toward Lane V. SDK auto-routes by default. Per-lane reputation, per-lane stake floors.
The five objectives this document scores against are §9.2 #2 (Runner Marketplace Integrity), #3 (Developer Attraction and Retention), #1 (Consensus Security), #4 (Long-run Fee Sustainability), and #5 (State Bloat Resistance). The Cowboy team's importance weightings (Tool 4) are reproduced in the Utility Function section below.

The headline result: **Concept B - Optimistic Marketplace + Challenger Bounty** wins the utility ranking with a score of +300, narrowly ahead of **Concept C** (+290), with **Concept A** as the datum (0). The 10-point margin between B and C is approximately 3.3% of the leader's score - well inside the MBSE skill's "close-call" band (within 10%) - meaning the ranking is *not* decisive on the numbers alone. The decisive cell is Concept C's −2 on State Bloat Resistance (per-lane reputation, per-lane registration, SDK auto-router metadata) which costs it 70 utility under the operator's weight (35) and just exceeds its 60-utility gain on Developer Attraction. The recommendation section below explains why Concept B is still the right base mechanism and why Concept C's most distinctive contribution - the cryptographically-verifiable Lane V - should be retained as an *opt-in* pathway in the Phase 4 hybrid rather than dropped entirely.


---


### Network Objectives (Reference)


| # | Objective | Brief description |
|---|---|---|
| 2 | **Runner Marketplace Integrity** | Off-chain compute results are reliably correct and verifiable under each trust model; runner honesty dominates collusion profitability across plausible adversary sizes. Conflicts with #4, #5. |
| 3 | **Developer Attraction and Retention** | Attract Python-competent developers and AI/agent builders in sufficient numbers to populate the actor ecosystem within the first 24 months. Conflicts with #4. |
| 1 | **Consensus Security** | Cost of acquiring ≥⅓ of active validator stake exceeds a target dollar threshold and grows with network value. Indirect runner-stake channel only in v1. |
| 4 | **Long-run Fee Sustainability** | Achieve a state within a defined horizon where fee revenue (basefees burned + tips + runner flows) sufficiently rewards validators/runners without dependence on inflation. Conflicts with #1, #2, #3. |
| 5 | **State Bloat Resistance** | Total on-chain state size grows sub-linearly with usage; eviction operates as a credible pressure-relief valve. Conflicts with #3, #6. |

§10.2 of the Design Review explicitly identifies the runner marketplace as *"the most novel and the most risky subsystem,"* which is why Objective #2 carries the highest individual weight in this analysis (85). The remaining objectives are weighted to reflect their indirect coupling to the runner subsystem rather than their absolute network-level importance.


---


### Tool 1: Qualitative Comparison


#### Concept B - Optimistic Marketplace + Challenger Bounty - vs Datum (Concept A)

**Objective #2 - Runner Marketplace Integrity.** Concept B closes six of the seven runner-specific risks identified in the Design Review §11 risk register at the source of the mechanism: adaptive committee `M = clip(2·log₂(N_active)/HHI, 3, 9)` defeats committee-capture risk (R3) by scaling defence with adversarial concentration; fractional 25% non-reveal slash defeats the strategic non-reveal attack (R2) by introducing a graduated punishment that doesn't bankrupt honest crashes; 50/30/20 slashed-stake split (challenger/burn/treasury) restores explicit economic incentive for third-party challenge submission (R15); EMA reputation with explicit half-life makes the VRF weight distribution deterministic and tunable (R13); eligibility-threshold aggregator (any reputation ≥ p50, not just maximum) closes the new-runner lockout (R11); and USD-pegged stake floor via CBY/USD TWAP defeats the cold-start asymmetry where incumbents get cheap collateral as CBY appreciates. The only R-row Concept B does not improve over Concept A is R10 (`semantic_similarity` mode embedding circularity), which is left in place. Concept A by contrast addresses only R11 partially (via the parameterised aggregator bonus) and leaves the structural integrity problems for a future CIP. Verdict: **+** (dramatically better).

**Objective #3 - Developer Attraction and Retention.** Concept B materially improves runner-marketplace economics for developers in three ways: adaptive committee sizing means actors deploying early (when the runner population is small) are protected by a larger committee, lowering cold-start adversary risk; USD-pegged stake floor stabilises runner pricing across CBY price swings, making per-job cost more predictable for actors planning multi-month workloads; and the eligibility-threshold aggregator combined with EMA reputation means the runner marketplace converges to a wider, more competitive set of operators rather than entrenching the first few well-capitalised teams. Against these, the adaptive committee makes per-job verification cost slightly less predictable (M can vary block-to-block as HHI moves), and the oracle dependency adds one new failure mode developers indirectly inherit. On balance, positive but not dramatic. Verdict: **+** (somewhat better).

**Objective #1 - Consensus Security.** Runner stake and validator stake are separate pools in CIP-13 v1 (validators are self-bonded only; runner staking supports delegation). Concept B's improvements therefore touch consensus security only via the *runner-stake share of total economic security*. The USD-pegged stake floor is the most relevant change - it ensures runner economic security scales with the dollar value of jobs being executed rather than with the spot CBY price, which structurally stabilises the runner-stake portion of total security. Adaptive committee defends against runner-stake-mass attacks at low population. Otherwise the impact is indirect. Verdict: **+** (somewhat better).

**Objective #4 - Long-run Fee Sustainability.** Concept B redirects slashed stake from 100% burn (whitepaper §8.4) to 50/30/20 challenger/burn/treasury. The burn share of slashed stake is reduced by 70 percentage points; the treasury share is a sustainability inflow rather than a destruction; the challenger share leaves the protocol entirely. The 89/10/1 base split on job payments is unchanged, so the dominant fee-burn pathway (10% of every job payment) is preserved. The net long-run effect is mildly negative for the burn flywheel because slashing events, while infrequent, used to contribute 100% of slashed-stake mass to the deflationary pressure and now contribute only 30%. This is partially offset because the existence of the challenger bounty surfaces more bad behaviour for slashing in the first place - i.e., total slashing events may rise - and because commission cap+floor stabilises runner economics over multi-year horizons. On balance, somewhat negative. Verdict: **−** (somewhat worse).

**Objective #5 - State Bloat Resistance.** Concept B adds: a per-runner EMA reputation accumulator (replaces, not adds-to, Concept A's simple counter - same order of magnitude), an oracle commit per epoch for the CBY/USD TWAP, and an active-set HHI computation whose inputs (stake distribution) already exist on-chain. Net additional state is small. Verdict: **S** (roughly the same).


#### Concept C - Tiered Trust Marketplace - vs Datum (Concept A)

**Objective #2 - Runner Marketplace Integrity.** Concept C's bifurcation is qualitatively the strongest possible improvement on integrity for the verifiable subset of jobs: Lane V's `M=1` single-runner execution paired with TEE attestation or ZK proof is *cryptographically verified*, not *economically verified*, which means it cannot be defeated by a 60%-stake adversary the way an optimistic M-of-N committee can. For jobs eligible for Lane V, integrity rises to a structurally-different category. For jobs that fall back to Lane R, Concept C inherits all of Concept B's improvements unchanged. The contained-to-Lane-R `semantic_similarity` mode addresses R10 by exclusion - Lane V disallows it. The trade-off is Lane V's lower stake floor (because output-incorrectness slashing doesn't apply when verification is cryptographic) — if attestation forgery turns out to be more practical than current TEE root-of-trust analysis suggests, Lane V's economic deterrence is weaker than Lane R's. Net: Concept C is dramatically better than Concept A on #2; it is slightly better than Concept B on the integrity dimension because the verifiable-subset security ceiling is higher. Verdict: **+** (dramatically better).

**Objective #3 - Developer Attraction and Retention.** Concept C's Lane V is materially cheaper than Concept B for the same job (no replication overhead), and the SDK `mode=auto` resolver routes by default to whichever lane is supported for the requested model. For TEE/ZK-supported model use cases (which are likely to dominate volume by mid-2027 as TEE inference matures), this is a real cost reduction for developers. Per-lane stake floors also create a specialisation pathway: TEE-capable operators target Lane V at lower stake; commodity GPU operators target Lane R - which grows the runner population faster than a single-mould marketplace would. Cost: developers must understand the lane choice if they ever override `mode=auto`, and Lane V's TEE eligibility for any given model is a moving target governed by the Entitlement Registry. Net: significantly better than Concept A and somewhat better than Concept B. Verdict: **+** (significantly better).

**Objective #1 - Consensus Security.** Concept C inherits Concept B's USD-pegged stake floor for both lanes. Per-lane stake floors mean some runners hold less collateral than they would under Concept A or B (specifically, Lane V's lower floor reflects lower output-slashing risk). The total pool of runner-side economic security is therefore slightly smaller than under Concept B for the same number of runners. Indirect impact on consensus security via the runner-stake channel is marginally below Concept B. Verdict: **+** (somewhat better than Datum, but slightly below Concept B on this dimension).

**Objective #4 - Long-run Fee Sustainability.** Concept C inherits Concept B's 50/30/20 slashing split and adds a Tier-3-level commitment to the 60/40 subsidy split toward Lane V (out of the 80M CBY Runner Compute -ncentives bucket). The subsidy steering is essentially a re-allocation, not a reduction - total CBY emitted is unchanged. Lane V's lower stake floor reduces the slashable mass per runner, marginally lowering slashing-burn potential. The two parallel runner economies could grow total job-payment volume if Lane V brings in TEE-capable runners that wouldn't otherwise participate, which would feed the 10% burn pathway. On balance, similar net effect to Concept B's redirection. Verdict: **−** (somewhat worse, same as B).

**Objective #5 - State Bloat Resistance.** This is Concept C's clearest weakness. Per-lane reputation (`r_V` and `r_R` per runner) roughly doubles the reputation state vs Concept B. Per-lane runner registration creates two parallel runner records per dual-lane operator. The Entitlement Registry must authoritatively store TEE eligibility per model (which it does today, but Concept C makes this load-bearing for the SDK auto-router). Per-lane delegator tranche caps may double active tranche counts for delegators who participate in both lanes. The absolute state contribution is small relative to CBFS storage (which dominates total state), but within the runner subsystem it is materially larger than Concept B's footprint. Verdict: **−** (significantly worse).


---


### Tool 2: Pugh Matrix


| Objective | Concept A (Datum) | Concept B | Concept C |
|---|---|---|---|
| #2 — Runner Marketplace Integrity | DATUM | + | + |
| #3 — Developer Attraction | DATUM | + | + |
| #1 — Consensus Security | DATUM | + | + |
| #4 — Long-run Fee Sustainability | DATUM | − | − |
| #5 — State Bloat Resistance | DATUM | S | − |
| **Total +** | — | **3** | **3** |
| **Total −** | — | **1** | **2** |
| **Total S** | — | **1** | **0** |
| **Net Score** | 0 | **+2** | **+1** |


#### Pugh Matrix Analysis

Both alternatives dominate the datum on the Pugh count: Concept B ties with Concept C at three positives, but Concept B avoids the second negative because its state-bloat impact is essentially neutral while Concept C's is negative. The simple Pugh matrix favours Concept B by one net position.

This is a misleading first read because the unweighted Pugh treats a small advantage and a large advantage equally. Concepts B and C tie on Integrity (#2) at +1 each in the simple matrix but the qualitative reasoning above suggests both are *dramatically* better than the datum - magnitude 3, not magnitude 1. Concept C is *more* dramatically better on Developer Attraction than Concept B is. The weighted Pugh below makes those magnitudes explicit and is the primary source of truth for the recommendation.


---


### Tool 3: Weighted Pugh Matrix (-3 to +3)

Scale: **+3** dramatically better, **+2** significantly better, **+1** somewhat better, **0** same, **−1** somewhat worse, **−2** significantly worse, **−3** dramatically worse.


| Objective | Concept A (Datum) | Concept B | Concept C |
|---|---|---|---|
| #2 — Runner Marketplace Integrity | 0 | **+3** | **+3** |
| #3 — Developer Attraction | 0 | **+1** | **+2** |
| #1 — Consensus Security | 0 | **+1** | **+1** |
| #4 — Long-run Fee Sustainability | 0 | **−1** | **−1** |
| #5 — State Bloat Resistance | 0 | **0** | **−2** |
| **Total Score** | **0** | **+4** | **+3** |


#### Weighted Pugh Analysis

Concepts B and C tie at +3 on Integrity (the dominant objective), reflecting the structural reality that Concept B already maxes out the optimistic-marketplace integrity improvements at +3, while Concept C adds the verifiable-lane improvement on top - but the Pugh ceiling at +3 caps both. Concept C earns its +1 advantage on Developer Attraction (lower cost for verifiable jobs, auto-routing UX) but pays a −2 on State Bloat from the per-lane reputation, registration, and SDK auto-router state. Concepts B and C share identical scores on Consensus Security and Fee Sustainability.

The end result is a +1 unweighted-score lead for Concept B (+4 vs +3). This aligns with the Pugh count and is the first signal that the analysis will favour Concept B once the weighted utility is computed - but the magnitudes are close enough that the operator's importance weights on State Bloat (#5) and Developer Attraction (#3) are decisive. If #5 is weighted at zero and #3 highly, Concept C wins. If #5 carries any meaningful weight and #3 is moderate, Concept B wins. The actual operator weights are below.


---


### Tool 4: Utility Function


#### Objective Importance Weightings

These weightings were provided by the operator (Vending Machine, on behalf of the Cowboy engagement) on 30 April 2026:


| # | Objective | Importance (0–100) |
|---|---|---|
| 2 | Runner Marketplace Integrity | **85** |
| 3 | Developer Attraction and Retention | **60** |
| 1 | Consensus Security | **40** |
| 4 | Long-run Fee Sustainability | **55** |
| 5 | State Bloat Resistance | **35** |

The dominance of #2 (85) reflects the Design Review §10.2's framing of the runner marketplace as the most novel and most risky subsystem - integrity is the load-bearing property of the entire engagement. The #3 weight (60) acknowledges that runner-marketplace UX is a real driver of developer attraction but recognises that #3 is broader than this single subsystem. The #1 weight (40) reflects the indirect coupling of runner stake to consensus security in CIP-13 v1 (validators are self-bonded only). The #4 weight (55) balances the burn-flywheel pressure against the modest absolute size of runner-flow contributions to total fee revenue. The #5 weight (35) reflects that the runner subsystem is a small contributor to total state size relative to CBFS.


#### Utility Calculation

**Utility = Σ (Weighted Pugh Score × Objective Importance)**


| Objective | Importance | Concept A (Datum) |  | Concept B |  | Concept C |  |
|---|---|---|---|---|---|---|---|
|  |  | Score | Utility | Score | Utility | Score | Utility |
| #2 — Runner Marketplace Integrity | 85 | 0 | 0 | +3 | **+255** | +3 | **+255** |
| #3 — Developer Attraction | 60 | 0 | 0 | +1 | **+60** | +2 | **+120** |
| #1 — Consensus Security | 40 | 0 | 0 | +1 | **+40** | +1 | **+40** |
| #4 — Long-run Fee Sustainability | 55 | 0 | 0 | −1 | **−55** | −1 | **−55** |
| #5 — State Bloat Resistance | 35 | 0 | 0 | 0 | **0** | −2 | **−70** |
| **Total Utility** |  |  | **0** |  | **+300** |  | **+290** |


#### Final Ranking


| Rank | Concept | Total Utility Score | Margin vs Next |
|---|---|---|---|
| 🥇 1 | **Concept B — Optimistic Marketplace + Challenger Bounty** | **+300** | +10 |
| 🥈 2 | Concept C — Tiered Trust Marketplace | +290 | +290 |
| 🥉 3 | Concept A — Closed-Form Whitepaper (Datum) | 0 | — |

The 10-point margin between Concept B and Concept C is approximately **3.3% of Concept B's total utility** - well inside the MBSE framework’s "close-call" band (within 10%). **The numerical ranking is therefore not decisive on its own**, and the qualitative reasoning behind the placement carries unusual weight. The decisive cell is Concept C's −2 on State Bloat Resistance - at the operator's #5 weight of 35, this is a 70-utility penalty that just exceeds Concept C's 60-utility advantage on Developer Attraction. If the team weighted #5 below 30 the ranking would flip; if it weighted #3 above 70 the ranking would flip the other way. The Recommendation section addresses this directly.

The 290-point margin between Concept C and Concept A is decisive. Concept A - i.e., the whitepaper as written with minimum-change closures - is dominated by both alternatives under any reasonable weighting that places non-trivial weight on Runner Marketplace Integrity. This is the most important finding of the Phase-3 analysis: **the team's current intent is the weakest of the three options on the network's own stated objectives, and is dominated by Concept B by a wide margin (+300) regardless of how the secondary weights move.**


---


### Recommendation

**Concept B - Optimistic Marketplace + Challenger Bounty - is the recommended winning design for Phase 4 (Critical Design Review), but with Concept C's Lane V incorporated as an *****opt-in***** pathway rather than discarded entirely.** The 10-point utility margin (3.3%) is small enough that the qualitative reasoning behind the choice should drive the Phase-4 decision. The reasoning that puts Concept B ahead is structural: it captures essentially all of Concept C's integrity improvements (six of seven R-row risks closed at the mechanism source) without paying the per-lane state-bloat cost or committing the team to the Tier-3 governance work required to launch a parallel verifiable lane at TGE. The Foundation also avoids pre-committing the 60/40 subsidy steering, which is a Tier-3-level decision that materially shapes the runner-side TEE bootstrapping pathway and is harder to reverse than to defer.

That said, Concept C's most distinctive contribution; Lane V's cryptographically-verified single-runner pathway, is qualitatively different from anything in Concept B and represents real value for two specific job classes: (1) high-sensitivity jobs where the developer needs cryptographic guarantees beyond economic-security committees (e.g., medical-data inference, financial-attestation jobs) and (2) high-volume low-margin jobs where the cost reduction of skipping replication is large enough to change the economics. Discarding Lane V entirely would leave value on the table. The recommended Phase-4 framing is therefore **"ship Concept B as the base mechanism, and introduce Lane V as an opt-in pathway gated on the actor explicitly requesting ****`mode = verifiable`**** rather than as a parallel default lane with auto-routing."** Concretely:

- The base mechanism is Concept B: adaptive committee, EMA reputation, 50/30/20 challenger/burn/treasury split, fractional non-reveal slash, eligibility-threshold aggregator, USD-pegged stake floor, commission cap+floor, partial delegator governance.
- Lane V exists but is not the default. A job lands in Lane V only if the actor explicitly requests `mode = verifiable` *and* the requested model has TEE/ZK eligibility in the Entitlement Registry. There is no SDK `mode = auto` resolver — the developer makes the verification-mode decision explicitly.
- Per-lane reputation and per-lane stake registration apply only to runners who explicitly opt into Lane V; the per-lane state cost scales with TEE-runner adoption rather than being incurred at TGE for every runner.
- The 60/40 subsidy steering is *deferred* to a future CIP and is not pre-committed at TGE. The 80M CBY bucket pays out flat per-runner-hour to all runners, with subsidy steering reserved for governance decision once Lane V demand can be measured.
This hybrid is *not* a fourth concept - it is Concept B with Concept C's most distinctive mechanism added as an opt-in. It captures Concept B's +3 on Integrity (unchanged), Concept C's +2 on Developer Attraction *for the verifiable-job subset* (preserved via opt-in), and reduces Concept C's −2 on State Bloat to approximately 0 (because the per-lane state only exists for runners who opt in, which initially will be a minority). Recomputed utility: roughly +330, comfortably above either pure concept.

Three flags worth surfacing for the Cowboy team before Phase 4 authoring begins:

1. **The numerical ranking is genuinely close.** A 10-point gap on a 300-point leader is within normal cell-judgement noise - the score-by-score reasoning in Appendix A could reasonably move ±1 unit per cell, which is enough to flip the ranking. The team should not treat the B-over-C result as a strong endorsement of B over C - it should treat it as evidence that the hybrid is the right answer because both concepts contribute essential mechanisms.
1. **Concept B requires modifying C7 (the 100% burn pre-commitment).** This is the largest pre-TGE governance commitment in either alternative concept: the slashed-stake destination is currently a Tier-3+ change. The Foundation should pre-clear the 50/30/20 split before Phase 4 commits to it. If the Foundation has a strong prior preference for preserving 100% burn, Concept B (and the recommended hybrid) are both off the table and Concept A becomes the fallback by elimination - at the cost of unaddressed R2, R3, R7, R11, R13, R15.
1. **The USD-pegged stake floor introduces a CBY/USD oracle dependency** that does not exist in any other Cowboy subsystem at TGE. This is a real new failure mode: oracle compromise, oracle delay, and oracle-source price-manipulation are now load-bearing on runner economics. A Phase-4 implementation note should specify the oracle source(s), the TWAP window, the fallback behaviour on oracle stall, and the Tier-2 governance pathway for oracle source changes. If the Foundation has not yet decided on a CBY/USD oracle provider, this decision is upstream of the Phase-4 CDR.

---


### Disclaimer

This documentation is provided for informational purposes only and is based on a modified version of MIT's Model-Based Systems Engineering process adapted for blockchain mechanism design. It does not constitute financial, investment, or legal advice. All concepts described are design proposals; none has been implemented, audited, or formally verified. The utility scores presented are derived from Vending Machine's expert judgement on the relative magnitudes of each concept's effect on each objective, scaled by the operator-supplied importance weightings; reasonable practitioners could disagree on individual cell values within ±1 unit, and the operator should treat the ranking as a structured input to the Phase-4 design decision rather than as a definitive verdict. References to external protocols (EigenLayer, Bittensor, Akash, Ritual, Cosmos, Chainlink) describe their public mechanism designs as of April 2026. References to the Cowboy whitepaper, CIPs, and the 27 April 2026 Cowboy timer-auction discussion reflect public and internal documentation available as of the document date and may be superseded by subsequent Cowboy team decisions. Vending Machine makes no representation that any specific concept or parameter will be selected by the Cowboy team, nor about the eventual launch parameters of the Cowboy Protocol.


---


### Appendix A — Score-by-score reasoning summary (for cross-checking)

For convenience, the table below collapses the qualitative reasoning into one row per (Concept × Objective) cell with a one-line justification for the weighted Pugh score. Use this as a quick sanity-check before Phase 4 commits.


| Cell | Score | One-line justification |
|---|---|---|
| B × #2 | +3 | Closes 6 of 7 R-row runner risks (R2, R3, R7, R11, R13, R15) at mechanism source; only R10 remains. |
| B × #3 | +1 | Adaptive committee + USD-pegged stake floor + open aggregator pool improve cold-start and pricing predictability for actors. |
| B × #1 | +1 | USD-pegged stake floor stabilises runner-stake share of total economic security across CBY price swings. |
| B × #4 | −1 | 50/30/20 split reduces burn share of slashed stake by 70 pp; 89/10/1 base flow unchanged. |
| B × #5 | 0 | EMA reputation replaces (not adds to) Concept A's counter; oracle commit per epoch is small. |
| C × #2 | +3 | Lane V cryptographic verification > optimistic; Lane R inherits Concept B; ceiling at +3 on Pugh scale. |
| C × #3 | +2 | Lane V is materially cheaper for verifiable jobs; SDK auto-routing makes the lane choice UX-invisible by default. |
| C × #1 | +1 | Same USD-pegged stake floor as Concept B; per-lane stake floors slightly reduce total runner-side security. |
| C × #4 | −1 | Inherits Concept B's slashing redirection; 60/40 subsidy steering is reallocation not reduction. |
| C × #5 | −2 | Per-lane reputation doubles state; per-lane registration; SDK auto-router metadata is load-bearing. |


---


### Appendix B — Sources

- *Cowboy Protocol — System Architecture Design Review*, Vending Machine, April 2026 (Notion).
- *Cowboy Runner Marketplace — Concept Generation*, Vending Machine, April 2026 (Notion) — the Phase 2 source document this Phase 3 evaluates.
- *Cowboy meets with Caleb regarding Timers/Auctions*, internal meeting transcript, 27 April 2026 — referenced for design-philosophy framing (DevX as meta-priority; ship simple and instrument).
- *🥾 Whitepaper Sections for Reconsideration*, Vending Machine, April 2026 (Notion) — §9/§19 runner marketplace gap closures.
- EigenLayer slashing redistribution (mainnet July 2025) — [EigenCloud, "Intro to Slashing on EigenLayer: AVS Edition"](https://blog.eigencloud.xyz/intro-to-slashing-on-eigenlayer-avs-edition/).
- Bittensor Yuma EMA reputation — [Bittensor, "Yuma Consensus"](https://docs.learnbittensor.org/learn/yuma-consensus).
- Ritual verifiable inference architecture (Lane V precedent) — [Ritual Foundation, "ZK Proving & Verification"](https://www.ritualfoundation.org/docs/whats-new/evm++-sidecars/zk-proving-and-verification).
