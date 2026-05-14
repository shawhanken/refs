# 🛷 Design Review Summary (Cowboy Input)

<!-- Notion page id: 817e6c7d-52db-820f-a257-016a2b1ccc55 -->

The sections that follow are the decision-forcing core of this design review. They isolate the choices that only Cowboy Labs can make - choices that cannot be derived from the architecture alone and that will drive every subsequent phase of the tokenomics work.
The material is organised in four parts. Section 1 surfaces the design tensions that came out of the architecture analysis, proposes a draft list of network objectives for Cowboy Labs to confirm, declares the hard constraints, and maps the interdependencies between objectives. Section 2 synthesises the seven findings we consider load-bearing for Phase 2 concept generation. Section 3 is a compact risk register with severity, likelihood, and Phase-2 priority. Section 4 enumerates the gaps in the public record that must be filled before simulation can proceed.
Nothing here prescribes a parameter value. The purpose of this summary is to converge on what the network is optimising for, what it is constrained by, and what is currently unknown - in that order.


### 1. Network Objectives Review


#### 1.1 Design Tensions Identified

The system architecture analysis above reveals several tensions that any objective prioritisation must resolve. These tensions are what make the objective-weighting exercise meaningful — they are the real choices.

1. **Decentralisation vs. runner marketplace bootstrap.** A small committee (M=5, N=3) is robust if the runner set is large and independent, but vulnerable in the early network. Subsidies accelerate runner capacity but also let well-capitalised early operators entrench before the wider market forms.
1. **Storage affordability vs. state bloat defence.** State rent at 0.001 CBY/byte/year is cheap enough to keep developers happy while CBY is cheap, but state bloat is permanent and the design pays for it forever. A rent rate that auto-adjusts to CBY/USD price is logically correct but introduces oracle risk.
1. **Validator accessibility vs. security budget.** Lower `minimum_validator_stake` → more decentralised validator set → less collateral behind each consensus vote. Higher minimum → fewer, richer validators → more collateral but more centralised.
1. **LLM non-determinism vs. verifiability.** Six verification modes is a thoughtful recognition that LLM outputs aren't reproducible, but it pushes the trust decision onto developers who may choose the cheapest mode (`none`) without understanding the implications.
1. **Governance agility vs. predictability.** Five-tier governance with hot-code upgrades is powerful but means the protocol is genuinely mutable. Users must trust the ongoing governance process, not just the launch design.
1. **Open runner market vs. model publisher gatekeeping.** Permissionless model registry is good; governance flag/ban is pragmatic but creates a future political fight the first time it's used.
1. **Dual-meter precision vs. UX simplicity.** Cycle and Cell fees are microeconomically superior to single-gas but require wallets to estimate two metered quantities and users to think about both. Ethereum users spent years learning a single gas number.
1. **Slashing conservatism vs. deterrent strength.** The 1% validator slash is industry-low and favours validator onboarding, but leaves the network with thin defence-in-depth against determined attackers who have outside upside.
1. **Security Council permanence vs. progressive decentralisation.** A 7-of-9 permanent emergency council is safer at launch but can become a political fixture. The "reduce only via Tier 4" rule is smart but needs honest execution.
1. **Ethereum interop convenience vs. third-party bridge risk.** Shared keys are a genuine UX win; delegating bridge security to third parties concentrates risk outside the protocol's own verification.

#### 1.2 Proposed Network Objectives (DRAFT - for Cowboy team confirmation)

The following is Vending Machine's proposed objectives list derived from the architecture analysis. These are framed to be specific, measurable, and mutually distinguishable. They should be treated as a starting point for the live review session with the Cowboy team, not as a final list.


| # | Objective | Type | Description | Conflicts With | Measurement | Confirmed |
|---|---|---|---|---|---|---|
| 1 | **Consensus security** | Objective | Maintain economic security of Simplex BFT PoS such that the cost of acquiring ≥⅓ of active validator stake exceeds a target dollar threshold at launch and grows with network value. | 4, 6 | Total staked value (USD) / estimated attack cost; inflation-adjusted validator APR | ☐ |
| 2 | **Runner marketplace integrity** | Objective | Ensure that off-chain compute results are reliably correct and verifiable under each trust model, with runner honesty dominating collusion profitability across plausible adversary sizes. | 4, 5 | % of jobs verified successfully; challenge rate; successful challenges / total challenges; runner churn | ☐ |
| 3 | **Developer attraction and retention** | Objective | Attract Python-competent developers and AI/agent builders in sufficient numbers to populate the actor ecosystem within the first 24 months. | 4 | # of unique deploying addresses per month; # of active (non-evicted) actors; deposited CBY in non-system actors | ☐ |
| 4 | Inference Incentivisation (GPU competition) | Objective | Financially attract GPU usage and model operation in order for the protocol to grow. Needs to be viable financial option for GPU usage so that runner networks can grow organically. | 4 | # of unique onboarded runners and amount of activity per month. (High reputation runners with minimum deposited/ delegated CBY). | ☐ |
| 5 | **Long-run fee sustainability** | Objective | Achieve a state within a defined horizon (e.g., 5 years) where fee revenue (from basefees burned + tips + runner flows) sufficiently rewards validators and runners without dependence on inflation. | 1, 2, 3 | Ratio of (tips + runner flows) to inflation rewards; burn vs. mint net over 90-day windows | ☐ |
| 6 | **Resistance to state bloat and eviction griefing** | Objective | Keep the total on-chain state size growing sub-linearly with usage, with eviction operating as a credible but humane pressure-relief valve. | 3, 6 | Total state size trajectory; eviction events per month; restoration events per month | ☐ |
| 7 | **Accessibility of governance participation** | Objective | Ensure that effective voting turnout exceeds a threshold across proposal tiers and that no single holder or validator can unilaterally pass a Tier 2+ proposal. | 1, 9 | % of staked CBY voting; Gini of voting power; % proposals passing below 15% participation | ☐ |
| 8 | **Timer liveness and fairness** | Objective | Ensure that non-adversarial timers fire within a bounded delay from their scheduled block, even under congestion, and that no single actor can monopolise the timer lane. | 8 | Median delay between scheduled and actual fire block; % of timers deferred more than N blocks; actor concentration in executed timers | ☐ |
| 9 | **Predictable fee UX** | Objective | Wallet-level fee estimation achieves within-X% accuracy across 95% of transactions under normal load, such that users are rarely surprised by final cost. | 7 | % of txs where `final_fee / estimated_fee ∈ [0.85, 1.15]`; basefee volatility (std/mean per epoch) | ☐ |
| 10 | **Credible decentralisation of the Security Council and Foundation** | Objective | Over time, visibly demonstrate that the Security Council's emergency powers are used sparingly, with retroactive ratification and with membership that is not dominated by Foundation-aligned individuals. | 6 | Council actions per year; ratification passage %; Foundation-held Council seats (SHOULD be ≤1); rotation rate | ☐ |
| 11 | **Bridge security bound** | Objective | Any asset bridged from Ethereum is protected by a third-party bridge whose economic security (staked value behind the bridge) meets or exceeds the total value currently bridged. | 10 | Σ TVL bridged / Σ bridge operator stake ratio; diversification across multiple bridges | ☐ |


#### 1.3 Constraints (Hard Requirements)

These are proposed as *constraints* (pass/fail), not optimised objectives. Designs that violate constraints should be eliminated rather than scored.


| # | Constraint | Rationale |
|---|---|---|
| C1 | **Determinism is inviolable.** No mechanism may introduce non-determinism into PVM execution under any threat model. | Loss of determinism breaks consensus safety. |
| C2 | **Safety under f < n/3 Byzantine validators must be preserved.** | Simplex BFT assumption is load-bearing for the entire design. |
| C3 | **No user may be forced to lose funds through protocol-defined mechanisms** (other than explicit staking bonds, governance-approved slashing, fees, or rent paid for services rendered). | Reasonable property-rights floor. |
| C4 | **No single entity may unilaterally pass a Tier 2+ governance proposal.** | Codifies "no plutocrat can spend the treasury alone." |
| C5 | **The Security Council cannot propose, upgrade, or disburse directly** - it can only intervene on queued actions. | Preserves the intended separation of powers. |
| C6 | **Determinism of the cost table must be preserved across upgrades.** Cost table changes are consensus-critical and Tier 3 at minimum. | Prevents stealth changes that break cross-validator agreement. |
| C7 | **Slashed stake destination must be pre-committed** (currently 100% burn). Any change to this destination is itself Tier 3+. | Prevents governance capture via "redirect slash to favoured party." |


---


### 2. Preliminary Discussion

Synthesising across the preceding sections, we identify seven key findings that should shape the remaining phases of this engagement.


#### 2.1 The protocol is well-architected at the component level and under-specified at the economic anchor level

Cowboy's technical design is mature: the dual-metered fee model is a genuine improvement over single-gas, the tiered calendar queue with GBA auctioning is novel and thoughtful as a target design (CIP-1; CIP-5 currently ships FIFO-within-height-bucket with the auction deferred to Phase 3), the commit-reveal runner protocol with six verification modes correctly handles the non-determinism of LLM outputs, and the QMDB + Blake3 storage choice is a deliberate performance engineering decision. The bicameral governance with tiered timelocks and the narrow Security Council design is more carefully thought through than most L1s.

However, three categories of parameters are deferred to "governance-defined" in the public docs: (a) **validator economics** (minimum stake, APR target, security-floor trigger), (b) **runner reputation dynamics** (decay rate, recovery rate, implied VRF weight functions), and (c) **bridge selection**. Each of these is load-bearing at launch. A protocol cannot launch with governance-defined validator minimum stake and expect governance to function, because governance itself requires staked CBY that requires validators that require a minimum stake. This circularity must be broken by committing to genesis defaults — even if those defaults are scheduled for early governance review.


#### 2.2 The Runner marketplace is the most novel and the most risky subsystem

The runner marketplace is Cowboy's most differentiated claim. It is also the subsystem with the most unanswered design questions:

- Committee size (M=5, N=3) is static; adaptive sizing is not specified.
- Aggregator bonus magnitude is unspecified.
- Behaviour under non-reveal is unspecified.
- Reputation decay/recovery mathematics are unspecified.
- Interaction between `semantic_similarity` mode and embedding model selection is a potential circularity.
- Economic circularity: a runner's effective stake floor is CBY-denominated but jobs are USD-valuable.
Of these, the non-reveal case and the reputation dynamics are the most urgent to resolve because they directly determine whether the 10% burn + 1% treasury split is a correct pricing of marketplace integrity.


#### 2.3 The timer subsystem is load-bearing but has significant unknowns

Actors that schedule themselves are the core value proposition - without reliable timers, Cowboy is just Ethereum with Python. The tiered calendar queue is a sound target design (CIP-1) and the DoS mitigations are thorough, but CIP-5 (rev 2026-03-19) currently ships a simpler FIFO-within-height-bucket implementation with the GBA auction deferred to Phase 3. When the auction does ship, the GBA concept elegantly sidesteps the problem of pre-paying for distant future execution. But the default GBA bidding strategy, the GBA invalid-bid handling, and the interaction between timer basefee (which rises with queue depth) and actor balance thresholds are all currently specified at the level of mechanism, not parameter. Simulation is the only way to find the stable region here.


#### 2.4 The 1% validator slashing is an explicit, conscious tradeoff - but the tradeoff must be made clear

Cosmos slashes ~5% for double-signing. Ethereum has correlation-scaled slashing that can reach 50%+ for coordinated attacks. Polkadot slashes up to 100%. Cowboy at 1% is the softest in the class. The whitepaper frames this as deliberate conservatism ("jailing rather than stake destruction"), which is a defensible position - but it implicitly assumes that reputational cost and opportunity cost of jailing are high enough to substitute for economic slashing. Whether that assumption holds at launch, when validator reputations don't yet exist, is worth explicit team confirmation.


#### 2.5 State rent + eviction is elegant but depends on stable CBY/USD

The rent formula uses `rent_rate = 0.001 CBY/byte/year` as a starting point. This is CBY-denominated. If CBY appreciates 10×, rent costs 10× in USD. If CBY crashes 10×, state bloat becomes free in real terms. Since rent adjusts based on total state size (`rent_rate_{i+1} = rent_rate_i × (1 + clamp((S - T) / (T × α), -δ, +δ))`) the system *does* self-correct for over-consumption, but only in CBY terms. A dollar-stable rent would require an oracle, which introduces a different trust assumption. The current design is defensible but should be stress-tested against extreme CBY price paths.


#### 2.6 Runner delegators are the disempowered majority

CIP-13 creates a capital-flexible group who bears slashing risk but has zero governance voice. This is defensible at launch (delegators may not be knowledgeable enough to vote well) but creates a future legitimacy problem: the group whose behaviour most affects runner health has no say in runner-relevant parameters. A natural compromise - giving delegators partial vote weight (e.g., 25%) on runner-parameter-specific proposals only - is worth exploring in Phase 2.


#### 2.7 The bridge question is a latent critical path

The whitepaper's Ethereum interop section is explicit: "Bridge selection and integration are determined by governance. The protocol does not implement its own bridge validator set." This means the first governance vote will be, effectively, choosing the security model for any value bridged from Ethereum. This is an enormous decision to push onto a governance process that is itself new. Two concrete options to prepare before mainnet:

1. **Pre-select a bridge via the core team** with a commitment to retire it via governance if it misbehaves.
1. **Launch with no bridge** and treat Ethereum interop as a post-launch feature gated by governance selection.
The current implicit path - launch with governance unspecified and the bridge also unspecified - is the worst of both worlds.


---


### 3. Risk Register (summary)

A compact risk register derived from the architecture analysis. Severity uses L/M/H; Likelihood is a rough prior given the design as-specified; Phase-2 priority indicates which risks should drive concept generation.


| # | Risk | Severity | Likelihood | Owner | Phase-2 Priority |
|---|---|---|---|---|---|
| R1 | Validator slash (1%) too weak to deter coordinated attacks at scale | H | M | Cowboy consensus team | High |
| R2 | Runner non-reveal attack exploits ambiguous slashing classification | H | M | Runner subsystem team | Critical |
| R3 | Small runner population allows committee capture at M=5, N=3 | H | H at launch, L at scale | Runner team | High |
| R4 | Default GBA behaviour systematically disadvantages non-GBA-sophisticated actors | M | H | Scheduler team | Medium |
| R5 | CBY price volatility makes state rent either punitive or ineffective | M | H | Economics / governance | Medium |
| R6 | Third-party bridge choice becomes the weakest link in network security | H | M | Governance | Critical |
| R7 | Runner delegator disenfranchisement produces post-launch legitimacy crisis | M | M | Governance | Medium |
| R8 | Governance low turnout enables whale capture at Tier 2 (15% quorum per CIP-12) | M | M | Governance | Medium |
| R9 | Security-floor inflation trigger threshold unspecified → staking ratio races to zero if CBY crashes early | H | L | Economics team | High |
| R10 | `semantic_similarity` verification mode has embedding-model circularity | M | H | Runner team | Medium |
| R11 | Aggregator bonus size is under-specified → either no-one aggregates or everyone games for the role | M | H | Runner team | High |
| R12 | Validator APR unspecified at launch → validators can't make build-vs-rent decisions | H | H | Economics team | Critical |
| R13 | Reputation dynamics for runners are unspecified → VRF weight distribution is unknown | M | H | Runner team | High |
| R14 | State rent is CBY-denominated, no oracle path to USD-stable rent | M | M | Economics team | Medium |
| R15 | Slashed stake burn prevents bounty for challengers; reduces challenge incentive | M | M | Runner team / Economics | Medium |


---


### 4. Gaps Requiring Team Clarification

Items where the materials reviewed (whitepaper, public docs, GitHub, CIP index) do not contain enough detail to complete the analysis. These should be raised with the Cowboy team before proceeding to Phase 2.


| # | Gap | Why it matters | Handled by VM? | Cowboy Team Notes |
|---|---|---|---|---|
| G1 | **`minimum_validator_stake`** genesis default | Required to size the validator set and estimate security budget | Yes |  |
| G2 | **Validator APR target** (or equivalent emission formula) | Required to model B1 loop and validator participation decisions | Yes |  |
| G3 | **Security-floor inflation trigger threshold** (staked-ratio below which inflation rises) | Required to model worst-case inflation schedules and validator onboarding | Yes |  |
| G4 | **Runner reputation decay and recovery formulas** | Required to model runner market dynamics and VRF selection distribution | Cowboy |  |
| G5 | **Aggregator bonus size and computation** | Required to model aggregator incentive and committee dynamics | Y/N |  |
| G6 | **Protocol behaviour on runner commit-without-reveal** | Determines whether commit-reveal is cryptographically honest |  |  |
| G7 | **Default GBA bidding strategy spec** | Required to model timer market dynamics | Cowboy - tbh not sure what our v1 is here - Caleb owns |  |
| G8 | **CBFS Relay Node economics** - rent rates, challenge bond, slashing schedule | Required to model storage economy | Y/N |  |
| G9 | **Bridge selection process and candidate bridges** | Required to assess pre-mainnet risk | Cowboy |  |
| G10 | **Runner Compute Incentives emission schedule** - over what period are the 80M CBY disbursed, and what's the per-runner-hour rate formula | Required to model runner economics at each phase | Yes |  |
| G11 | **Liquidity Mining emission curve** (23.3M CBY, "front-loaded over 12 months") | Required to model float and price discovery | Yes - at least initial schedule |  |
| G12 | **Validator commission model** - can they charge users additional per-block fees, or only receive tips? | Required to model validator revenue | Yes |  |
| G13 | **`commission_bps`**** bounds** - is there a cap on runner commission, or can a runner set 100%? | Required to model delegator UX and race-to-the-bottom risk | Y/N |  |
| G14 | **Unbonding lifecycle for runners** - CIP-13 §3.3–§3.4 confirms `UNBONDING_BLOCKS` applies to delegator tranches; runner self-bond unbonding is handled through `RunnerDeregister`, which force-initiates unbonding on all tranches. (Partially resolved.) | Required to model exit dynamics | Y/N |  |
| G15 | **Per-rent-epoch length and catch-up fee mechanics** | Required to model eviction pressure | Y/N |  |
| G16 | **Governance parameter store initial values** - many parameters are "governance-tunable" with genesis defaults not explicitly listed | Required to understand launch state | Y/N |  |


### **Conclusion**

What we need from Cowboy Labs, in priority order:

1. **Confirm the network objectives in §1.2.** Mark each row ✔ as-is, revise the wording, or remove it. Tell us if we've missed one. This list is the scoring rubric for every concept we generate in Phase 2, so it has to be right before we move.
1. **Ratify or amend the constraints in §1.3.** These are pass/fail. Concepts that violate them will be eliminated rather than scored.
1. **Validate the tensions in §1.1 and the seven findings in §2.** Push back where our reading of the design diverges from your internal understanding — we'd rather correct now than carry drift into the simulation.
1. **Resolve the gaps in §4 (G1–G16).** Several are genuinely open; a few may already have internal answers that simply haven't surfaced in the public corpus.
