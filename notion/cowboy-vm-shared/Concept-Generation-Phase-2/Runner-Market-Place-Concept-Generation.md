# 🎉 Runner Market Place Concept Generation

<!-- Notion page id: 8dee6c7d-52db-83cf-8128-0152b6e5b1dc -->

*Prepared by Vending Machine · April 2026 · Status: Draft for Cowboy team reviewSibling document to: Cowboy Protocol - System Architecture Design Review (April 2026)*


---


### Abstract

This document is the Phase 2 (Concept Generation) output for the **Runner Marketplace** subsystem of the Cowboy Protocol. It presents three meaningfully distinct design concepts that resolve the open questions and design risks raised in §10–§12 of the *Cowboy Protocol - System Architecture Design Review*, scored against the two network objectives most directly governed by this subsystem:

- **Objective #2 - Runner Marketplace Integrity:** off-chain compute results are reliably correct and verifiable under each trust model, with runner honesty dominating collusion profitability across plausible adversary sizes.
- **Objective #3 - Developer Attraction & Retention:** Python-competent developers and AI/agent builders find the runner marketplace cheap, predictable, and trust-appropriate enough to populate the actor ecosystem within the first 24 months.
Concept Selection (Phase 3) will follow in separate documents once the Cowboy team has reviewed and approved the suggested concepts here.

The three concepts are designed to span a real design space rather than to vary a single parameter. They explicitly differ in how they answer the seven design questions identified in the design review's risk register: (R2) non-reveal classification, (R3) committee adaptivity, (R7) delegator governance, (R11) aggregator role, (R13) reputation dynamics, (R15) slashed-stake destination, plus the cross-cutting cold-start economics question (CBY-denominated stake floor vs. USD-valued jobs).

A guiding principle, drawn from the team philosophy, is that **a simpler design that the team can ship and instrument frequently outperforms a theoretically optimal design that the team cannot calibrate against live data.** Each concept is therefore presented in a state we believe is launchable, with an explicit "post-launch tightening" pathway rather than a static fully-parameterised mechanism.


---


### Design Space

The runner marketplace lives at the intersection of ten design dimensions. The table below maps each, and the row "Concept choices" at the end shows where each concept sits - the spread is what makes the three concepts genuinely different.


| # | Dimension | Options |
|---|---|---|
| 1 | **Slashing trigger** | Proven dishonesty only / Extended (incl. non-reveal as fractional slash) / Cryptographic-where-possible (no slash on output when verification is cryptographic) |
| 2 | **Slashed-stake destination** | 100% burn (whitepaper §8.4) / Multi-split (challenger / burn / treasury) / Lane-conditional |
| 3 | **Committee sizing** | Static M=5/N=3 / Adaptive on runner-set concentration / Per-lane (M=1 verifiable, M≥5 replicated) |
| 4 | **VRF weight function** | Pure stake (`w = s`) / Stake × reputation (`w = s^α · r^β`) / Reputation-primary |
| 5 | **Reputation dynamics** | Unspecified (status quo) / Simple linear decay / Exponentially-weighted moving average with explicit half-life |
| 6 | **Stake-floor pegging** | CBY-denominated (whitepaper) / USD-pegged via TWAP oracle / Hybrid (CBY floor + USD ceiling) |
| 7 | **Commission market** | Uncapped (whitepaper) / Cap only / Cap + floor |
| 8 | **Delegator governance** | None (whitepaper) / Partial weight on runner-parameter Tier-2 proposals / Full pro-rata |
| 9 | **Aggregator selection** | Highest-reputation (whitepaper, locks out new runners) / Eligibility threshold (multiple candidates above p50) / Lane-conditional |
| 10 | **Subsidy targeting** | Flat per-runner-hour / Tiered toward verifiable lane / Output-quality-weighted |

> **Concept choices (preview)**
> 
> | Dim | A: Closed-Form Whitepaper | B: Optimistic Marketplace | C: Tiered Trust Marketplace |
> |---|---|---|---|
> | 1 | Proven dishonesty only | Extended (non-reveal = fractional slash) | Lane-V cryptographic-only / Lane-R extended |
> | 2 | 100% burn | Multi-split (50/30/20) | Lane-conditional |
> | 3 | Static M=5/N=3 | Adaptive on Herfindahl | Per-lane (V: M=1, R: M=5/N=3) |
> | 4 | Pure stake | `s¹ · r^0.5` | `s¹ · r^0.5` per-lane |
> | 5 | Simple linear (immediate-zero on slash) | EMA, half-life `H_R` blocks | EMA per-lane |
> | 6 | CBY-denominated | USD-pegged TWAP | USD-pegged TWAP |
> | 7 | Uncapped | Cap 30% / floor 5% | Cap 30% / floor 5% |
> | 8 | None | Partial 25% on runner params | Partial on Lane R only |
> | 9 | Highest reputation | Eligibility threshold (p50) | Lane R only, eligibility threshold |
> | 10 | Flat per-runner-hour | Flat per-runner-hour | 60/40 toward Lane V |
> 


---


### Concept A: Closed-Form Whitepaper - DATUM


#### One-line summary

Resolve every open question in the existing CIP-2 / CIP-13 architecture with the *minimum* viable closure: keep static committees, keep 100% burn, classify non-reveal as operational failure, parameterise the aggregator bonus with a single number, and ship.


#### Overview

Concept A treats the design review as a *gap-closure exercise*, not an architectural redesign. The whitepaper §8.2/§8.4 schedules and the CIP-2/CIP-13 architecture are taken as essentially correct; the work is to specify the smallest set of additional values needed to make the system unambiguous at launch. This is the most defensible position to start from because it preserves hard commitment C7 (slashed-stake destination is pre-committed; any change is Tier-3+) and avoids any architectural change that would require additional CIPs before TGE.

The design philosophy mirrors the team's stated preference of **launching simple and instrumenting hard** - defer optimisation until live runner data exposes which parameters actually matter. Concept A's reputation, aggregator-bonus, and non-reveal rules are the simplest defaults that don't violate the whitepaper's stated intent. They are explicitly intended to be revisited in 6–12 months once the marketplace has produced enough job/challenge history to calibrate.

The cost of this conservatism is twofold. (1) The 100% burn destination preserves C7 but leaves no challenger bounty - meaning challenge incentive must come from reputation upside alone, which is unmeasured. (2) The CBY-denominated stake floor is left exposed to the cold-start economics asymmetry flagged in §7.2 of the design review (low CBY price → cheap collateral; high CBY price → incumbents entrenched).


#### Architecture diagram

![Screenshot 2026-05-05 at 22.26.34.png](./assets/d56e6c7d_Screenshot_2026-05-05_at_22.26.34.png)


#### Key mechanisms

- **Committee selection (CIP-2 unchanged).** Fisher-Yates stake-weighted VRF sortition with log₂-compressed selection weights. Default `M = 5, N = 3` for all jobs regardless of declared value.
- **Sortition weight.** `w_i = log₂(1 + s_i)` - pure stake-weighted; no reputation factor in selection (reputation only governs aggregator role and max job value, as the whitepaper specifies).
- **Aggregator role.** Designated aggregator = highest-reputation member of the selected committee, paid an explicit aggregator bonus of **2% of the runner's 89% share** (≈ 1.78% of gross job payment), funded out of the runner share (no protocol-side change to the 89/10/1 split).
- **Non-reveal classification.** A runner that commits but does not reveal within `reveal_window_blocks = 4` is treated as **operational failure** - a reputation penalty equivalent to one missed job, but **no slashing**. Rationale: this preserves the whitepaper position that slashing requires *proof of dishonesty*, and avoids slashing legitimate crashes.
- **Reputation dynamics.** Linear: each successful job adds `+1` to a reputation counter capped at `R_max = 1000`; each operational failure subtracts `−1`; proven dishonesty resets to `0` and triggers a 14-day jail. Recovery rate is symmetric to decay rate. *No EMA, no half-life - minimum-viable simplicity.*
- **Slashing.** Whitepaper §8.4 unchanged: 100% burn of slashed stake on proven dishonesty.
- **Stake floor.** CBY-denominated as written: `effective_stake ≥ max(10,000 CBY, 1.5 × declared_max_job_value_in_CBY)`. The conversion from `declared_max_job_value` (USD-priced) to CBY is left to the runner at registration.
- **Commission market.** Uncapped `commission_bps`. Delegators discipline runners via market exit; `UNBONDING_BLOCKS ≈ 24h` is the friction.
- **Subsidy.** 8% genesis bucket (80M CBY) paid out flat per-runner-hour over a defined emission window (Cowboy to set; placeholder 36 months).
- **Delegator governance.** None. Delegators retain only economic exposure.

#### Stakeholder impact


| Stakeholder | Impact vs. status quo (whitepaper-as-written) |
|---|---|
| Validators | No change. |
| Runners | Marginally clearer: aggregator-bonus number now exists; non-reveal classification removes ambiguity. Reputation recovery path is explicit. |
| Runner Delegators | Unchanged exposure. Race-to-the-bottom on `commission_bps` remains unconstrained. No governance voice. |
| Actors / Developers | Marginally more predictable: aggregator pricing is now a known number that flows into job-cost estimation. No improvement to cold-start adversary risk (R3) at low runner counts. |
| TEE Vendors / Model Publishers | No change. |
| Treasury | Unchanged (1% of job payments). |


#### Brief analysis

- **Strengths.** Fastest path to TGE. Minimal CIP authoring required. Preserves C7 hard commitment. No new oracle dependency. Reputation behaviour is intuitive. Non-reveal rule is a single sentence.
- **Weaknesses.** Doesn't address R3 (static committee → capture risk at low runner counts). Doesn't address R15 (no challenger bounty). Doesn't address R7 (delegator disenfranchisement). Aggregator selection still locks out new runners (tail of R11). Cold-start CBY/USD asymmetry untouched.
- **Risks.** Concept A is the *highest-bootstrap-risk* concept on Objective #2, because its only defence at low runner counts is the deterrent effect of reputation loss - and the deterrent is uncalibrated until enough jobs have flowed to populate the reputation counter. If an early adversary stakes ~60% of total runner stake during the first 2 weeks, the static `M=5, N=3` committee gives them ≥3 slots with high probability and they extract value before reputation catches up.
- **Precedents.** Cosmos SDK validator self-bonding without delegation is the closest cousin for the validator side of the architecture; for the off-chain compute marketplace there is no exact precedent - the closest is Akash's classical-CPU marketplace, which uses a reverse-auction reputation-only model (no slashing) and has not had to face this trade-off because its compute is not consensus-critical. The non-reveal-as-operational-failure choice mirrors how Chainlink OCR2 treats observation no-shows (reputation only, no slashing), which has worked at low TVL but is widely regarded as a vulnerability if challenged at scale.

#### Reason for datum selection

Concept A is the datum because it represents the team's **current intent expressed in the minimum number of additional decisions**. It is the design that ships if the Cowboy team's answer to every Phase-2 question is "the simplest closure consistent with the whitepaper." Every other concept must justify why its added complexity earns its keep against this baseline.


---


### Concept B: Optimistic Marketplace + Challenger Bounty


#### One-line summary

Borrow the *economic* security pattern of optimistic rollups and EigenLayer custom slashing: smaller adaptive committees defended by an explicit challenger bounty, fractional non-reveal slashing, EMA reputation with explicit half-life, and a USD-pegged stake floor.


#### Overview

Concept B accepts the underlying CIP-2 commit-reveal architecture but redistributes the slashed-stake destination and changes the committee-sizing function so that economic security scales with adversarial capability rather than being a static parameter. It is inspired by EigenLayer's April 2025 deployment of programmable slashing redistribution, which demonstrated on mainnet that AVSs can route slashed stake to a challenger bounty rather than to a burn sink - restoring the bug-bounty-on-chain economics that the whitepaper §8.4 100%-burn rule explicitly forecloses.

The central trade-off is that Concept B requires modifying the C7 hard commitment (100% burn of slashed stake). The proposed split is **50% to the first valid challenger, 30% burn, 20% to treasury**. The 30% burn keeps a deflationary signal alive - it just becomes a secondary, not a primary, function of slashing - and the 20% to treasury continues to fund protocol-level work. The 50% bounty is the smallest fraction that meaningfully changes challenger economics at typical job values; below ~30% the bounty is dominated by the gas cost of submitting a challenge and the time cost of running verification. This change requires a Tier-3+ governance proposal and team commitment to it pre-TGE.

The non-reveal rule is the second substantive change. Rather than treating commit-without-reveal as either operational failure (Concept A's choice) or full slash, Concept B introduces a **fractional non-reveal slash** - currently sized at 25% of the runner's effective stake - that is large enough to deter strategic non-reveal but small enough that a runner who legitimately crashes mid-job is not bankrupted. The existence of this intermediate tier is itself the design contribution; the exact 25% should be calibrated by simulation in Phase 5.

Reputation gets an explicit functional form: a Bittensor-Yuma-style exponentially-weighted moving average over (a) challenge survival rate and (b) uptime, with a tunable half-life. VRF weight then becomes `w_i = s_i^α · r_i^β`, with `α = 1, β = 0.5` at launch - meaning a runner with 4× the reputation of another, holding stake constant, only gets 2× the selection weight. This dampens the "rich-get-richer" feedback loop without erasing the incentive to maintain reputation.

Finally, the stake floor is USD-pegged via a 7-day TWAP from the CBY/USD oracle - protecting both new entrants (when CBY appreciates) and the protocol (when CBY depreciates).


#### Architecture diagram

![Screenshot 2026-05-05 at 22.30.12.png](./assets/ac0e6c7d_Screenshot_2026-05-05_at_22.30.12.png)


#### Key mechanisms

- **Adaptive committee size.** `M = clip(ceil(2 · log₂(N_active) / HHI_runner_stake), 3, 9)` where `HHI_runner_stake` is the Herfindahl–Hirschman index of stake across active runners (1 = monopoly, ~0 = perfectly distributed). At launch, with few runners and concentrated stake, M defaults toward 9; as the runner set grows and disperses, M relaxes toward 3. Threshold `N = ceil(2M/3)` always.
- **Sortition weight.** `w_i = s_i^α · r_i^β` with `α = 1, β = 0.5` at launch. Both governance-tunable.
- **Aggregator role.** Eligibility threshold rather than maximum: any committee member with reputation ≥ network-wide p50 may aggregate; a single aggregator is selected uniformly at random from this set per job. New runners are not permanently locked out - once their reputation crosses p50, they enter the eligibility pool. Bonus is **1.5% of gross job payment**, paid only on successful settlement.
- **Non-reveal slashing.** Commit-without-reveal within the window triggers a **25% fractional slash** of the runner's effective stake (not full slash). The slashed amount enters the same 50/30/20 split as proven-dishonesty slashes. The fraction is governance-tunable (Tier-2).
- **Slashed-stake destination.** **50% to first valid challenger**, **30% burn**, **20% to treasury**. Challenger is the EOA / contract that submits the proof of dishonesty (per the EigenLayer model). For non-reveal slashes, the "challenger" is the protocol itself and the 50% goes to a `0x09`routed challenge-bounty pool to incentivise future submissions.
- **Reputation dynamics.** EMA over a `H_R = 14-day` half-life (i.e., ~250k blocks at 5s slots), tracking `(survived_challenges + uptime_score) / total_jobs`. Proven dishonesty zeros reputation and triggers `JAIL_DURATION_BLOCKS = 14d`; on jail exit reputation restarts from a `r_floor = 0.1 · network_median` to give recovering runners a non-zero selection probability.
- **Stake floor.** USD-pegged: `effective_stake_CBY ≥ max(10k_CBY_equivalent_USD, 1.5 × declared_max_job_value_USD) / TWAP_CBY_USD_7d`. Recomputed at registration and at every reputation epoch (`E_R = 1 day`). If CBY depreciates beyond a band (e.g., 25% intra-epoch), runners are given a 7-day grace period to top up before automatic deregistration.
- **Commission market.** Hard cap `commission_bps ≤ 3000` (30%); soft floor `commission_bps ≥ 500` (5%) enforced at registration to prevent a race-to-zero that destabilises long-run runner economics.
- **Subsidy.** Same 80M CBY bucket, paid out flat per-runner-hour. (Concept B does not differentiate subsidy by lane - there is only one lane.)
- **Delegator governance.** Partial - delegators receive **25% pro-rata weight** on Tier-2 proposals tagged `runner-marketplace-parameter`, computed as `0.25 × delegated_stake / total_delegated_stake`. They retain zero weight on consensus-layer or non-runner-marketplace proposals.

#### Stakeholder impact


| Stakeholder | Impact vs. status quo (whitepaper-as-written) |
|---|---|
| Validators | No change to validator economics. |
| Runners | Modestly higher operational discipline required (non-reveal becomes a real cost). Reputation pathway is explicit and recoverable. New runners can become aggregators once they cross p50. Stake floor decouples from CBY price, reducing cold-start anxiety. |
| Runner Delegators | Gain a real (if minority) governance voice on parameters that affect their returns. Race-to-the-bottom on `commission_bps` is bounded - a runner cannot offer 1% commission to crowd out competitors and then re-raise after delegators are locked in. |
| Actors / Developers | Higher base security at low runner counts (adaptive committee scales up). Aggregator selection no longer shelf-stable for incumbents → wider runner pool over time → more competition → better pricing. |
| Challengers (new role) | Receive 50% of slashed stake on successful challenge - for the first time, an explicit economic role exists for third parties to police runner integrity. Likely candidates: client-side observers, Foundation-funded watchdogs at launch, eventually independent indexers. |
| TEE Vendors / Model Publishers | No change. |
| Treasury | Gains 20% of slashed stake in addition to the existing 1% of job payments. |


#### Brief analysis

- **Strengths.** Directly addresses R2 (non-reveal), R3 (committee scaling), R7 (delegator disenfranchisement, partially), R11 (aggregator lockout), R13 (reputation dynamics), R15 (challenger bounty) - six of the seven runner-specific risks. Aligns with the auction-design philosophy from the 27 Apr discussion: *order matters when premium is paid* (a high-stake runner with high reputation should win committee slots, but not deterministically).
- **Weaknesses.** Requires modifying C7 (100% burn pre-commitment) - pre-TGE governance work and explicit team buy-in. Requires a CBY/USD oracle dependency at launch (currently unspecified in the whitepaper). Adaptive committee sizing makes per-job cost less predictable for developers - a tension with Objective #3.
- **Risks.** Three principal risks. (1) **Challenger bounty griefing:** if a malicious actor learns to fabricate plausible-looking challenges, they can extract gas-fee deposits; mitigation is a small challenger bond (e.g., 100 CBY) refundable on valid submission. (2) **EMA reputation gaming:** runners can stack many low-value jobs to raise reputation cheaply, then defect on a high-value job. Mitigation: weight EMA contributions by job value (Bittensor's bond-clipping pattern). (3) **Adaptive M shock:** if HHI moves sharply (e.g., a large runner exits), per-job costs jump suddenly. Mitigation: smooth M with an EMA on HHI itself.
- **Precedents.** EigenLayer's slashing redistribution (mainnet July 2025) is the direct inspiration for the multi-split, particularly Othentic's challenger-as-EOA model. Bittensor's Yuma EMA bonds and weight clipping inform the reputation function; their experience confirms that EMA half-life is the most load-bearing governance parameter. Optimistic rollup dispute games (Optimism, Arbitrum) provide the "fraction of bond to challenger" prior - implementations vary but the principle is well-established. The "Hollow Victory" 2025 paper on dispute-game incentive misalignment is a useful negative example for parameter calibration.

---


### Concept C: Tiered Trust Marketplace


#### One-line summary

Bifurcate the marketplace into a **verifiable lane** (TEE / ZK-attested, single-runner, no output slashing) and a **replicated lane** (commit-reveal with the Concept B challenger-bounty + non-reveal hardening). Developers explicitly choose at job-submission, and the subsidy is steered toward bootstrapping the verifiable lane.


#### Overview

Concept C goes further than Concept B by treating verification mode as a *first-class* market dimension rather than a per-job parameter. Today's CIP-2 already permits six verification modes (TEE, ZK, semantic_similarity, etc.) but routes them all through the same M=5/N=3 committee plumbing. Concept C argues that this is structurally inefficient: when a job is verified by a TEE attestation or a ZK proof, replication adds cost without adding security - the verification is *cryptographic*, not *economic*. Conversely, when no cryptographic verification is feasible, replication is the only defence and should be done with full economic weight (challenger bounty + non-reveal slash).

The concept therefore exposes two lanes to developers:

- **Lane V (Verifiable):** Single-runner execution (`M = 1`). Verification is an attestation (TEE) or proof (ZK) checked by the Result Verifier `0x03` / TEE Verifier `0x05`. There is **no slashing for output incorrectness** (a correct attestation cannot accompany an incorrect computation). Slashing exists only for *attestation forgery* (e.g., a runner submitting a TEE attestation it does not in fact possess) and for non-availability beyond a defined SLA. Lower price, lower latency, narrower model coverage (only TEE-supported or ZK-circuit-supported models).
- **Lane R (Replicated):** Default `M = 5 / N = 3` commit-reveal with the full Concept B mechanism (50/30/20 challenger split, fractional non-reveal slash, eligibility-threshold aggregator, EMA reputation). Higher price, higher latency, supports any model.
The 80M CBY Runner Compute Incentives bucket is split **60% / 40% toward Lane V** to bootstrap TEE adoption, because the TEE hardware capex is the load-bearing barrier to entry on the verifiable lane and the protocol benefits structurally from more verifiable supply. The split is intentionally large enough to matter (Lane V will see ~1.5× the per-runner-hour subsidy of Lane R for the same active hours) but not so large that Lane R is starved.

The trade-off is **complexity at the developer interface** - actors must now make a verification-mode decision at job-submission time. Concept C addresses this by providing a default mode in the SDK (`mode = "auto"` selects Lane V if the requested model has TEE support, else Lane R) and by ensuring the price differential is large enough that the choice is unambiguous in most cases.

This bifurcation is structurally similar to the Bittensor "subnet" pattern (multiple sub-markets with different incentive functions sharing one token) and to Ritual's sidecar architecture (TEE, ZK, optimistic, probabilistic verification all natively supported and routed by the application). It is a meaningful departure from the whitepaper's "one runner marketplace, six verification modes" framing.


#### Architecture diagram

![Screenshot 2026-05-05 at 22.44.51.png](./assets/caae6c7d_Screenshot_2026-05-05_at_22.44.51.png)


#### Key mechanisms

- **Lane V - committee.** `M = 1`. Runner is selected by VRF weighted by lane-V reputation. No threshold; the single runner's attestation is checked by `0x05` / `0x03`.
- **Lane V - verification.** Cryptographic only. Allowed verification modes: `tee_intel_sgx`, `tee_amd_sev`, `tee_arm_trustzone`, `zk_circuit`. The `semantic_similarity` and `none` modes are **disallowed in Lane V** (and the design review's R10 circularity issue is thereby contained to Lane R).
- **Lane V - slashing.** Output incorrectness is not slashable (verification is cryptographic). Slashable conditions are: (a) attestation forgery — runner submits an attestation purportedly from a TEE root key it does not control, detectable by the `0x05` TEE Verifier on root-key mismatch; (b) availability failure beyond per-actor SLA. Slash size: 100% on attestation forgery (proof-of-fraud is binary), 10% on availability breach. Same 50/30/20 split as Lane R.
- **Lane R - full Concept B.** All Concept B mechanisms apply unchanged within Lane R: adaptive committee size, EMA reputation, fractional non-reveal slash, challenger bounty, eligibility-threshold aggregator.
- **Reputation - per-lane.** A runner has separate reputation scores `r_V` and `r_R`. Cross-lane signal is one-way: high `r_R` (≥ p75) gives a small bootstrap to `r_V` (`r_V_init = 0.2 · r_R`) but not the reverse, because Lane V verification is cryptographic and does not generate the same kind of "honesty signal" that would inform Lane R.
- **Stake floor - per-lane.** A runner registers separately for each lane; the stake floor for Lane V is **lower** (`max(5k CBY equiv USD, 1.0 × declared_max_job_value)`) because output slashing risk is structurally lower; Lane R retains Concept B's full floor (`max(10k CBY equiv USD, 1.5 ×...)`).
- **Subsidy split.** Of the 8% genesis (80M CBY) Runner Compute Incentives bucket: **60% → Lane V** (~48M CBY), **40% → Lane R** (~32M CBY). Within each lane, payout is flat per-runner-hour over a defined emission window.
- **Commission market.** Cap 30% / floor 5% in both lanes (per Concept B).
- **Delegator governance.** Partial 25% on Lane R parameter Tier-2 proposals only. Lane V parameters are governed without delegator weight, because Lane V delegators bear materially less slashing risk.
- **Default routing.** SDK exposes `mode = "auto" | "verifiable" | "replicated"`. The `auto` resolver checks the Entitlement Registry for TEE/ZK support of the requested model and routes Lane V if available. This means most developers never see the lane choice; the bifurcation is structural but UX-invisible by default.

#### Stakeholder impact


| Stakeholder | Impact vs. status quo (whitepaper-as-written) |
|---|---|
| Validators | No change to validator economics. |
| Runners | Bifurcated business decision: TEE-capable runners can target Lane V (lower per-job revenue, higher volume, lower slashing risk, more subsidy); commodity GPU runners stay on Lane R (higher per-job revenue, full M=5 replication). Allows specialisation rather than forcing all runners into one mould. |
| Runner Delegators | Lane choice when delegating. Lane V delegations face less slashing risk but no governance voice; Lane R delegations face more risk but get partial governance weight. Symmetric trade-off; market sorts naturally. |
| Actors / Developers | More options, more decisions - but `mode = auto` makes the default ergonomic. Higher predictability on Lane V (single-runner cost is deterministic; committee adaptivity does not apply). Lower base price for verifiable jobs. |
| TEE Vendors | Materially advantaged - Lane V exists because of TEE attestation. Subsidy split toward Lane V drives TEE-runner growth. Long-run dependency risk on TEE supply chains. |
| Model Publishers | Models with TEE/ZK circuit support become more economically attractive (eligible for Lane V with lower fees). Creates a market signal for TEE-friendly model architectures. |
| Treasury | Gains 20% of slashed stake (both lanes); Lane V slashes are rarer but binary 100%. |


#### Brief analysis

- **Strengths.** Highest scoring on Objective #2 (integrity) for the cryptographically-verifiable subset of jobs, because it stops paying for replication that adds no security. Highest scoring on Objective #3 (developer attraction) for the same job class - Lane V is materially cheaper. Lane R inherits all of Concept B's improvements. Subsidy steering pre-commits the 8% bucket to a structural goal (TEE bootstrap) rather than uniform per-runner-hour distribution.
- **Weaknesses.** Largest implementation surface area. Two parallel slashing/reputation systems doubles the audit cost and the parameter space. The auto-routing SDK is now a piece of trust-critical infrastructure (a malicious or buggy auto-router could route a job that ought to be replicated into Lane V). The 60/40 subsidy split is a Tier-3 commitment that is hard to reverse.
- **Risks.** Three principal risks. (1) **TEE supply concentration** - if Lane V is dominated by one TEE vendor's attestations and that vendor experiences a root-key compromise (cf. the recurring SGX vulnerabilities), the whole lane temporarily collapses. Mitigation: per-vendor lane caps (e.g., no single TEE vendor accounts for >40% of Lane V jobs in a 30-day window). (2) **Demand bifurcation** - if developers overwhelmingly pick Lane V for cost, Lane R subsidy is wasted; if they overwhelmingly pick Lane R for model coverage, Lane V never bootstraps. Mitigation: subsidy split is governance-tunable (Tier-2). (3) **SDK auto-router complexity** - model-by-model TEE eligibility is a moving target; the Entitlement Registry must be authoritative. Mitigation: cache TEE eligibility on-chain in the Entitlement Registry rather than off-chain in the SDK.
- **Precedents.** Bittensor's subnet model (multiple parallel sub-markets within one token economy) is the closest architectural cousin and confirms that two-lane systems can coexist economically without one cannibalising the other, provided the price/security trade-off is real. Ritual's sidecar architecture (TEE, ZK, optimistic, probabilistic verification all first-class) plus its Resonance fee mechanism (two-sided heterogeneous-hardware pricing) is the closest mechanism-design cousin. Akash's split between CPU and GPU markets demonstrates that a single token can support two structurally different supply markets without governance fragmentation. EigenLayer's slashing redistribution underlies Lane R's challenger split (same as Concept B).

---


### Summary Comparison


| Dimension | A - Closed-Form Whitepaper (DATUM) | B - Optimistic Marketplace | C - Tiered Trust Marketplace |
|---|---|---|---|
| **Architectural change vs whitepaper** | None | Single architecture, parameter & destination changes | Bifurcated lane architecture |
| **Risks closed (R2/R3/R7/R11/R13/R15)** | Partial R11 only (aggregator bonus magnitude) | All six | All six (R3 only in Lane R) |
| **C7 (100% burn) preserved?** | Yes | No - requires Tier-3 amendment | No - requires Tier-3 amendment |
| **New oracle dependency?** | No | Yes (CBY/USD TWAP) | Yes (CBY/USD TWAP) |
| **Cold-start cap-of-stake risk** | Highest (static M=5/N=3) | Lower (adaptive M scales with HHI) | Lowest in Lane V (M=1, cryptographic); Lane R = Concept B |
| **Developer-facing complexity** | Lowest (one mechanism) | Medium (predictable M variance) | Highest API surface, lowest cost on supported models (auto-routed) |
| **Implementation cost** | Low (gap-closure) | Medium (one new architecture) | High (two parallel architectures + SDK auto-router) |
| **Time-to-launch impact** | None | +1 CIP, +1 oracle integration | +2 CIPs, +1 oracle integration, +SDK work |
| **Time-to-iterate post-launch** | Easiest to instrument and tune | Easiest to formally verify (single rule set) | Easiest to grow into (each lane evolves independently) |
| **Governance footprint** | Smallest (no Tier-3 amendments) | One Tier-3 amendment (C7) | Two Tier-3 amendments (C7 + lane introduction) |
| **Best fit for Objective #2 (integrity)** | Weakest at low N_runners | Stronger; bounty restores challenge incentive | Strongest where cryptographic verification is feasible |
| **Best fit for Objective #3 (dev attraction)** | Predictable but expensive at low N | Better pricing dynamics, less predictable per-job cost | Cheapest for verifiable jobs (default for most actors); more predictable |


---


### Recommended Next Steps

1. **Cowboy team selects scope of Phase 3 (Concept Selection).** The MBSE process treats this as a checkpoint: which two-or-three of these concepts do you want carried forward into a Pugh-matrix scoring? If Concept C's bifurcation is off the table for organisational or timeline reasons, declare that now and we proceed with A vs. B only.
1. **Confirm the network objective list to score against.** This document is scored against §9.2 Objectives **#2 (Runner Marketplace Integrity)** and **#3 (Developer Attraction)** per the operator's confirmation. Phase 3 will additionally need importance weights (0–100) on each objective from the Cowboy team.
1. **Resolve gap G6 in parallel.** Whichever concept is selected, the Cowboy team's view on whether non-reveal is operational-failure (Concept A) or fractional-slash (Concepts B/C) is independently load-bearing and can be confirmed in advance of Phase 3.
1. **Pre-clear C7 amendment with Foundation if Concepts B or C advance.** The 100%-burn pre-commitment is currently a Tier-3+ change; both alternative concepts require redirecting some fraction of slashed stake to a challenger bounty. If the Foundation has a strong prior preference here, Phase 3 weighting can reflect that.
1. **Calibrate adaptive M and reputation EMA half-life via simulation (Phase 5).** These are the two parameters whose stable region is most sensitive to live runner-set composition; they are also the two that Caleb's 27 Apr discussion correctly identifies as needing post-launch data rather than pre-launch theory.

---


### Disclaimer

This documentation is provided for informational purposes only and is based on a modified version of MIT's Model-Based Systems Engineering process adapted for blockchain mechanism design. It does not constitute financial, investment, or legal advice. All concepts described are design proposals; none has been implemented, audited, or formally verified. References to existing protocols (EigenLayer, Bittensor, Akash, Ritual, Optimistic Rollups, Cosmos, Chainlink) describe their public mechanism designs as of April 2026 and may be superseded by subsequent protocol changes. References to Cowboy whitepaper sections, CIPs, and parameter values reflect public documentation available as of the design review date and may be superseded by subsequent Cowboy team decisions. Vending Machine makes no representation that any specific concept or parameter will be selected by the Cowboy team, nor about the eventual launch parameters of the Cowboy Protocol.


---


### Appendix A — Mapping concepts to design-review risks and gaps


| Risk / Gap | Concept A handles via | Concept B handles via | Concept C handles via |
|---|---|---|---|
| **R2** Non-reveal | Operational failure (reputation only) | Fractional 25% slash → 50/30/20 split | Lane R: same as Concept B; Lane V: not applicable (no commit-reveal) |
| **R3** Static committee capture | Unaddressed | Adaptive M = `clip(2·log₂(N)/HHI, 3, 9)` | Lane V: M=1 (capture irrelevant; cryptographic verification); Lane R: as Concept B |
| **R7** Delegator disenfranchisement | Unaddressed | 25% partial weight on runner-param Tier-2 | 25% on Lane R params only |
| **R10** semantic_similarity circularity | Unaddressed | Unaddressed (still permitted) | Contained - `semantic_similarity` is disallowed in Lane V; remains in Lane R as today |
| **R11** Aggregator bonus magnitude / lockout | Bonus = 2% of runner share; "highest reputation" lockout retained | Bonus = 1.5% of gross; eligibility threshold (≥ p50) | Lane R only; same as Concept B; Lane V has no aggregator |
| **R13** Reputation dynamics unspecified | Linear ±1 with R_max=1000; immediate-zero on slash | EMA, half-life H_R = 14d, jail floor r_floor = 0.1 × median | EMA per-lane (r_V, r_R); cross-lane bootstrap r_V_init = 0.2·r_R |
| **R15** 100% burn → no challenger bounty | Unaddressed (preserves C7) | 50/30/20 split (challenger / burn / treasury) | Same split (both lanes) |
| **G4** Reputation decay/recovery formulas | Linear, symmetric | EMA with explicit half-life | EMA per-lane |
| **G5** Aggregator bonus computation | 2% of runner's 89% share | 1.5% of gross, on settlement only | Lane R only |
| **G6** Non-reveal classification | Operational failure | Fractional slash | Lane R: fractional; Lane V: N/A |
| **G10** Subsidy emission schedule | Flat per-runner-hour over Cowboy-set window | Same as A | 60/40 split toward Lane V; flat per-runner-hour within each lane |
| **G13** `commission_bps` cap | None | Cap 30%, floor 5% | Cap 30%, floor 5% |
| **Cold-start CBY/USD asymmetry** | Unaddressed (CBY-denominated) | USD-pegged via 7-day TWAP; per-epoch recompute | USD-pegged; per-lane stake floors |


---


### Appendix B — Sources

- *Cowboy Protocol — System Architecture Design Review*, Vending Machine, April 2026 (Notion).
- *Cowboy meets with Caleb regarding Timers/Auctions*, internal meeting transcript, 27 April 2026.
- EigenLayer slashing redistribution (mainnet July 2025) — [EigenCloud, "Intro to Slashing on EigenLayer: AVS Edition"](https://blog.eigencloud.xyz/intro-to-slashing-on-eigenlayer-avs-edition/); [Khushi, "Programmable Slashing on EigenLayer: A Deep Dive into Othentic's Design Space"](https://medium.com/@smilewithkhushi/programmable-slashing-on-eigenlayer-a-deep-dive-into-othentics-design-space-8c9bad970e46).
- Bittensor Yuma consensus & EMA bonds — [Bittensor, "Yuma Consensus"](https://docs.learnbittensor.org/learn/yuma-consensus); [Bittensor, "Understanding Incentive Mechanisms"](https://docs.learnbittensor.org/learn/anatomy-of-incentive-mechanism).
- Ritual verifiable inference architecture — [Ritual Foundation, "ZK Proving & Verification"](https://www.ritualfoundation.org/docs/whats-new/evm++-sidecars/zk-proving-and-verification); [Equilibrium Labs, "State of Verifiable Inference & Future Directions"](https://equilibrium.co/writing/state-of-verifiable-inference).
- Akash Burn-Mint Equilibrium and reverse-auction marketplace — [Akash Network](https://akash.network/); [Messari, Akash Network project page](https://messari.io/project/akash-network-2).
- Optimistic rollup challenger reward design — [Alchemy, "How Do Optimistic Rollups Work"](https://www.alchemy.com/overviews/optimistic-rollups); ["Hollow Victory: How Malicious Proposers Exploit Validator Incentives in Optimistic Rollup Dispute Games"](https://arxiv.org/html/2504.05094v1) (April 2025).
