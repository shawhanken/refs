# 🚟 Timer + GBA Concept Generation

<!-- Notion page id: d6ae6c7d-52db-83c5-bb70-015867c5c646 -->

*Prepared by Vending Machine · April 2026 · Status: Draft for Cowboy team review*


---


### Abstract

This document is the Phase 2 (Concept Generation) output for the **Timer Auction + Gas Bidding Agent (GBA)** subsystem of the Cowboy Protocol. It presents three meaningfully distinct design concepts for the *target* CIP-1 design that is currently scheduled to ship in CIP-5 Phase 3 - i.e. for the moment when the timer scheduler moves from FIFO-within-height-bucket (CIP-5 rev 2026-03-19, current devnet behaviour) to a fee-prioritised mechanism inside the 20% Timer lane.

Concepts are evaluated against the two network objectives that govern this subsystem in the design review:

- **Objective #7 - Timer Liveness and Fairness:** non-adversarial timers fire within a bounded delay from their scheduled block, even under congestion, and no single actor can monopolise the timer lane.
- **Objective #8 - Predictable Fee UX:** wallet-level fee estimation achieves within-X% accuracy across 95% of transactions under normal load, such that users are rarely surprised by final cost.
The design review's §9.4 explicitly flags these two objectives as *opposed* - "aggressive GBA auctioning produces volatile, unpredictable effective fees for timer-using actors." Resolving that tension is the central design problem here. The three concepts each pick a different point on the resulting Pareto frontier: closing the whitepaper's target as written (most fairness, least predictability), borrowing a uniform-price/Ausubel mechanism (better truthfulness and predictability, more architectural change), or replacing the auction entirely with an EIP-1559-style timer basefee + priority tip (most predictable, least direct fairness control - fairness is delivered by basefee dropping when the lane is under-utilised rather than by per-timer bias accumulation).

A guiding principle, drawn from the 27 April 2026 Cowboy/Caleb timer-auction discussion, is that **a simpler design that the team can ship and instrument outperforms a theoretically optimal design that the team cannot calibrate against live data, *****and***** that developer experience (DevX) - predictability of cost and ordering - is the meta-objective that subsumes all others.** Each concept therefore commits to a specific default GBA behaviour that an actor can use unmodified, so that "didn't bring my own GBA" is never a competitive disadvantage that drives developers to a centralised third-party GBA service (Risk R4).


---


### Design Space

The timer + GBA subsystem lives at the intersection of ten design dimensions. The three concepts span this space; the table below shows the spread.


| # | Dimension | Options |
|---|---|---|
| 1 | **Pricing rule** | First-price-per-cycle / Uniform-price (greedy VCG approximation) / EIP-1559 basefee + priority tip / Sealed-bid commit-reveal |
| 2 | **Bias / anti-starvation mechanism** | Uncapped exponential `e^(λt)` (whitepaper) / Capped exponential / Per-actor fairness weight / Lane-utilisation priority floor |
| 3 | **Bid validation** | Unconditional execute (whitepaper ambiguity) / Clamp to actor balance / Reject above max-fee |
| 4 | **Per-timer cycle cap** | Uncapped (whitepaper) / Per-timer cap / Per-actor-per-block cap |
| 5 | **Auction frequency** | Block-by-block (whitepaper) / Batch over N blocks / Tiered (block ring + epoch queue + overflow BST per CIP-1) |
| 6 | **Default GBA bidding strategy** | Vanilla basefee multiplier (Caleb 27 Apr) / Value-aware (actor supplies value function) / EIP-1559 wallet-style estimator |
| 7 | **GBA bid pricing visibility** | Opaque (sealed) / Partial (last-block clearing price published) / Full (all bids visible) |
| 8 | **Pre-pay / escrow model** | Per-block deposit / Lazy charge on inclusion / Escrow at scheduling, refund on cancel |
| 9 | **Cycle-meter for GBA itself** | GBA pays cycles per bid (whitepaper, anti-spam) / Free bid evaluation / Capped bid cost |
| 10 | **Lane fee multiplier** | Flat 1.0× / Per-lane independent / Dynamic with utilisation |

> **Concept choices (preview)**
> 
> | Dim | A - Whitepaper Target Closure | B - Uniform-Price + Per-Actor Fairness | C - EIP-1559 Timer Basefee |
> |---|---|---|---|
> | 1 | First-price-per-cycle | Uniform-price (clearing = highest losing) | EIP-1559 basefee + priority tip |
> | 2 | Capped exponential `e^(λt)` to 5× | Per-actor fairness weight `W ∈ [1, 2]` | Lane-utilisation priority floor |
> | 3 | Clamp to actor balance | Clamp to actor balance | Reject above `max_fee` |
> | 4 | Uncapped (status quo) | 250k cycles per timer | 250k cycles per timer |
> | 5 | Block-by-block | Block-by-block | Block-by-block (no auction; sorted include) |
> | 6 | Vanilla basefee multiplier | Value-aware | EIP-1559 wallet estimator |
> | 7 | Sealed | Partial (clearing price published) | Full (basefee published; tip distribution published) |
> | 8 | Lazy charge | Lazy charge | Lazy charge |
> | 9 | GBA pays cycles per bid | GBA pays cycles per bid | GBA pays cycles per bid |
> | 10 | 1.0× flat | 0.8× (timer subsidy) — governance-tunable | 1.0× flat |
> 


---


### Concept A: Whitepaper Target Closure - DATUM


#### One-line summary

Ship the CIP-1 target design as the whitepaper describes it - first-price-per-cycle bidding inside the Timer lane, with the exponential bias multiplier capped to prevent bias-gaming and the protocol-default GBA spec'd to a vanilla basefee multiplier.


#### Overview

Concept A is the minimum-change closure of the design the Cowboy team has already committed to in writing. The whitepaper §5.1 target design and the "Whitepaper Sections for Reconsideration" doc both anchor on a tiered calendar queue + GBA auction inside the 20% Timer lane with per-actor anti-starvation weights. Concept A respects that architecture and adds the smallest set of additional decisions needed to make the system unambiguous: bid validation behaviour (clamp to balance, never overdraft), bias multiplier ceiling (cap at 5× base bid to prevent the "bid 0 every block to accumulate bias" attack Caleb flagged), and a concrete default-GBA strategy (vanilla multiplier on the timer-lane basefee, increment until executed - exactly the behaviour Caleb described as "what the default GBA does today" in the 27 Apr discussion).

The strength of Concept A is that no architectural CIP needs to be authored; Cowboy can ship CIP-5 Phase 3 with the GBA auction described in CIP-1 and the additions above as parameters. The weakness is structural: first-price auctions are known to be unstable in repeated knapsack settings (a result well-documented in the literature and observed empirically in pre-EIP-1559 Ethereum and current Bitcoin block-space markets), and the exponential bias multiplier - even capped - is fundamentally a *retrospective* fairness mechanism that tries to compensate for a missed inclusion rather than prevent the missed inclusion in the first place. Caleb's instinct that the bias multiplier introduces a surface for game-ability is correct, and Concept A only partially addresses it.


#### Architecture diagram

![Screenshot 2026-05-05 at 12.25.33.png](./assets/4aae6c7d_Screenshot_2026-05-05_at_12.25.33.png)


#### Key mechanisms

- **Auction.** First-price-per-cycle, block-by-block, sealed bids inside the Timer lane (20% of block cycles ≈ 2M cycles).
- **Tiered queue (CIP-1 unchanged).** Block ring → epoch queue → overflow Merkleized BST. Lookups are `O(log n)` for the BST and `O(1)` for the block ring.
- **Bid validation.** Bid is **clamped** to `min(submitted_bid, actor_balance / declared_cycles)`. A GBA cannot drain its owner's balance via an irrationally high bid.
- **Bias multiplier.** Effective ranking score per timer = `bid_per_cycle × min(e^(λ · age), 5.0)`. The cap at 5× addresses the bias-gaming attack: a runner cannot bid zero indefinitely and rely on bias growing unboundedly.
- **Default GBA strategy.** `bid_per_cycle = max(timer_basefee × 2, recent_clearing_price_p50)`. If the timer is deferred, increment the multiplier by 0.5× per block deferred, capped at 5×. This is the "vanilla" GBA Caleb described as the current default. Cycles charged for GBA execution are paid out of the actor's balance per the whitepaper §6 GBA-as-actor model.
- **Per-timer cycle cap.** None added - preserves the whitepaper status quo. (Acknowledged weakness; flagged as a Phase 5 simulation question.)
- **Anti-starvation.** Exponential bias `e^(λ · age)` to the cap, applied to the ordering score (not to the bid itself). The actor still pays its bid, not its biased bid.
- **Lane multiplier.** Flat 1.0× - Timer-lane basefee tracks the Cycles basefee unmodified.
- **Pre-pay / escrow.** Lazy - actor pays at execution time, not at scheduling. The progressive timer deposit (already in CIP-5) handles the abuse vector of scheduling many timers without intent to pay.

#### Stakeholder impact


| Stakeholder | Impact vs. status quo (whitepaper-as-written, gaps closed) |
|---|---|
| Validators | No change to validator economics; tips continue to flow to proposer. |
| Actors / Developers | First clarity on what the default GBA actually does. Can use it without writing custom logic. Bid cost is *less* predictable than alternatives because first-price clearing varies block-to-block. |
| GBAs (third-party) | Real opportunity: a GBA that learns time-of-day patterns or actor-specific value functions can outbid the default consistently. This is also the *risk:* see R4. |
| End Users (EOAs) | No direct impact. |
| Treasury | Indirect: timer-lane basefee burn flows are a small share of total burn. |
| Security Council | No change. |


#### Brief analysis

- **Strengths.** Smallest deviation from the whitepaper target design - the path of least architectural resistance. Closes G7 (default GBA) and the bias-gaming attack with two parameter additions. Preserves the entire CIP-1 tiered calendar queue work that has already been done.
- **Weaknesses.** First-price auctions over a knapsack with repeated rounds are theoretically unstable: the dominant strategy is hard to find even with full information, and Caleb's intuition in the 27 Apr discussion that "people would just try to outbid each other constantly" is exactly the failure mode the literature predicts. Bias multiplier - even capped - is retrospective: it patches a missed-inclusion problem rather than preventing it. Default GBA's "increment by 0.5× per block deferred" rule means actors using the default in congestion pay materially more than sophisticated actors with value-aware GBAs (R4).
- **Risks.** (1) **Default-vs-third-party GBA divergence.** Once third-party GBA-as-a-service emerges (and it will - there is real revenue in saving actors money), default-GBA actors are systematically deprioritised. (2) **Repeated-knapsack equilibrium drift.** Without a stable equilibrium, the clearing price under congestion can spike unpredictably (the same instability EIP-1559 was designed to fix). (3) **Bias-cap calibration.** The 5× cap is arbitrary for now; if it's too low, anti-starvation fails for genuinely deferred timers; if it's too high, the gaming attack persists. Phase-5 simulation should sweep this.
- **Precedents.** Pre-EIP-1559 Ethereum (first-price auction for block space) is the closest cousin and is the precise example most often cited as why first-price block-space auctions are problematic (see *EIP-1559 in Retrospect*, Decentralized Thoughts, 2022). Bitcoin's transaction fee market is the same pattern at lower throughput; the empirical studies cited in the design space research show users could have saved $272M by not using first-price. Solana's pre-Jito priority-fee model is also first-price; its evolution toward Jito tips is a market-driven correction we should not reproduce.

#### Reason for datum selection

Concept A is the datum because it is the team's **existing intent** as captured in the whitepaper §5.1 target design and the CIP-1 specification. It represents the design that ships if the answer to every Phase-2 question is "the simplest closure consistent with what we already wrote."


---


### Concept B: Uniform-Price + Per-Actor Fairness


#### One-line summary

Replace first-price-per-cycle with a uniform-price (greedy VCG-approximation) clearing, replace the exponential bias multiplier with a per-actor fairness weight, and ship a value-aware default GBA so honest bidding is the dominant strategy regardless of GBA sophistication.


#### Overview

Concept B is the design Caleb himself was leaning toward in the 27 April discussion: "uniform-price… is kind of like a second-price auction, which in general everything gets more complicated because it's a knapsack auction and it's repeated. So in general for auctions, second-price auctions are kind of nice because honest bidding is a weakly dominant equilibrium." He correctly identified that the *exact* VCG mechanism is computationally expensive in a knapsack setting and that uniform-price is the standard greedy approximation. Concept B commits to that mechanism and pairs it with two structural changes that, together, address the design review's R4 (default-GBA disadvantage) and the bias-gaming attack Caleb separately flagged.

The first structural change is replacing the exponential bias multiplier with a **per-actor fairness weight**. Bias-gaming works because exponential bias accrues *per timer* and resets only when the timer fires - meaning an actor can run thousands of cheap "zero-bid" timers, accumulate bias on each, and then use that bias to discount real-value timers later. A per-actor weight flips this: an actor's *recent execution rate* relative to the network median determines a multiplicative weight on its current bid, capped at 2×. An actor that has been deferred more than median gets a boost; an actor that has captured more than its share of recent slots is implicitly de-prioritised. The weight is per-actor not per-timer, so spamming low-value timers doesn't accumulate exploitable bias.

The second structural change is a **value-aware default GBA**. The actor exposes a `value_function(time) -> CBY` (defaulting to a flat per-cycle CBY value if unspecified), and the default GBA bids `max(0, value_function(next_block) - opportunity_cost_estimate) / declared_cycles`. Because the auction is uniform-price (clearing = highest *losing* bid per cycle), honest bidding of the actor's true marginal value is weakly dominant - there is no advantage to a sophisticated third-party GBA over the default, except in the value-estimation step itself (which is structural to the application, not the bidding). This is the most direct mitigation of R4 in any concept.


#### Architecture diagram

![Screenshot 2026-05-05 at 12.24.48.png](./assets/72ce6c7d_Screenshot_2026-05-05_at_12.24.48.png)


#### Key mechanisms

- **Auction.** Uniform-price (greedy VCG approximation), block-by-block. Bids are sealed within the block; the clearing price is computed at block close and published.
- **Bid validation.** Clamp to `actor_balance / declared_cycles`.
- **Per-actor fairness weight.** `W(actor) = 1 + α · max(0, (median_recent_exec_rate - actor_recent_exec_rate) / median_recent_exec_rate)`, capped at 2.0. `α` is governance-tunable; suggested launch value `α = 1.0`. Computed over a rolling 1,000-block window. Effective ranking bid = `bid_per_cycle × W(actor)`.
- **Clearing price.** After ranking by effective bid, fill the 2M-cycle Timer lane greedily until full. The clearing price = the *highest losing* `bid_per_cycle` in the cohort (i.e., the bid of the marginal excluded timer). All winners pay `clearing_price × declared_cycles`. This is the "uniform price = effectively second-price" property Caleb cited.
- **Default GBA strategy.** `bid_per_cycle = max(0, actor.value_function(H+1) - α_op · clearing_price_p20_last_50_blocks) / declared_cycles`, where `α_op` is the actor's risk-aversion parameter (default 0.5). Honest reporting of `value_function` is weakly dominant under uniform-price; the GBA does not need to model competitor behaviour.
- **Per-timer cycle cap.** 250k cycles per timer fire (12.5% of the lane). Prevents a single high-value timer from monopolising the lane and creates a natural diversification incentive.
- **Lane multiplier.** 0.8× at launch (lane subsidy to encourage timer adoption) - governance-tunable per the whitepaper §11.5 reconsideration note.
- **Pre-pay / escrow.** Lazy charge at execution.
- **Cycle-meter for GBA.** Unchanged from whitepaper - GBA pays cycles per bid evaluation as anti-spam.

#### Stakeholder impact


| Stakeholder | Impact vs. status quo |
|---|---|
| Validators | Modestly higher tip aggregation work (uniform-price computation per block); negligible impact. |
| Actors / Developers | Honest bidding is dominant strategy → no advantage from custom GBAs over the default → R4 closed at the source. Per-actor fairness weight gives quieter actors a structural boost during congestion, exactly addressing Objective #7's "no single actor monopolises the timer lane." |
| GBAs (third-party) | Reduced economic role - uniform-price minimises the value of "smarter" bidding. Third-party GBAs can still differentiate on value-function modelling, dashboards, multi-timer coordination, but not on outbidding. |
| End Users (EOAs) | More predictable timer-execution costs because clearing prices are smoother under uniform-price than first-price. |
| Treasury | Slightly lower burn revenue at launch due to 0.8× lane multiplier; offset partially by higher overall timer adoption (testable hypothesis). |
| Security Council | No change. |


#### Brief analysis

- **Strengths.** Directly addresses R4 (default-GBA disadvantage) at the mechanism level rather than via UX defaults. Replaces bias-gaming-prone exponential bias with per-actor fairness that cannot be gamed via timer spam. Caleb's preferred mechanism per his 27 Apr framing - should land well with the team. Aligns with the literature trajectory away from first-price for repeated multi-unit auctions.
- **Weaknesses.** Greedy uniform-price is an *approximation* of VCG, not VCG itself; the truthfulness property is **weakly dominant**, not strictly dominant - there exist edge cases where misreporting can be marginally beneficial. The per-actor fairness weight requires a rolling per-actor execution counter, adding state. The 250k per-timer cap is a real constraint on developers writing computationally-heavy timers. Lane multiplier of 0.8× is a Tier-2 commitment of revenue that needs Foundation buy-in.
- **Risks.** (1) **Per-actor weight gaming via actor fragmentation.** A sophisticated developer could deploy 100 actors each running a fragment of the workload, gaming the per-actor weight by treating each as a separate "quiet" actor. Mitigation: per-deployer weight (using actor-deployment trace) rather than per-actor - but this requires deeper actor metadata than CIP-2 exposes today. Phase-5 simulation should test the magnitude of this threat. (2) **Clearing-price visibility creates a back-channel.** Publishing the clearing price at block close lets next-block bidders anchor on it; this is generally good (predictability) but enables collusion via the public clearing-price signal. (3) **Median-rate computation.** The "median recent exec rate" is a network-wide statistic; changes (e.g., new actors joining) move the median, briefly disadvantaging incumbents. Suggested smoothing via 1,000-block window absorbs most of this, but spikes are possible.
- **Precedents.** **Ausubel auction** (multi-unit Vickrey, dynamic) provides the strongest theoretical foundation for the weakly-dominant honest-bidding property. **Cosmos ****`x/auction`**** modules** implement uniform-price clearing at lower scale and are a useful Solidity-equivalent reference. **Google's Generalised Second-Price (GSP)** for ad slots is operationally similar; it has been criticised for not being strictly truthful but operates well in practice - instructive for Concept B's expected behaviour. The 250k per-timer cap mirrors **Solana's compute-unit per-transaction limit** (1.4M, scaled down for the Cowboy lane size).

---


### Concept C: EIP-1559 Timer Basefee + Priority Tip


#### One-line summary

Drop the per-block auction entirely. Replace it with a Timer-lane EIP-1559 mechanism - basefee that adjusts to lane utilisation, plus a priority tip - and let the wallet/GBA fee-estimation patterns the entire industry uses today take care of predictability.


#### Overview

Concept C takes the most architecturally aggressive position: the auction itself is the source of unpredictability, so remove the auction. Instead, the Timer lane gets its own EIP-1559 mechanism: a lane basefee that adjusts each block based on lane utilisation (target = 50% of the 2M-cycle lane, max 12.5% adjustment per block), plus a priority tip per cycle. Timers are sorted by `priority_tip_per_cycle` and included up to the lane budget; basefee is burned, tip goes to the proposer. This *is* the EIP-1559 design specialised to a sub-lane.

The benefits are:

1. **Objective #8 (Predictable Fee UX) becomes trivial.** Every wallet, RPC, and SDK in the Ethereum ecosystem already implements EIP-1559 fee estimation. Cowboy timer-fee estimation reuses that work. There is no "default GBA strategy" to specify and audit (G7 closes by elimination). The default GBA is `max_fee_per_cycle = 2 × current_basefee, max_priority_fee_per_cycle = previous_block_p50_priority_fee` - exactly what MetaMask's "Medium" preset does for L1.
1. **Objective #7 (Liveness/Fairness) is delivered by basefee dropping.** When the lane is under-utilised (e.g., < 30% of 2M cycles consumed), the basefee falls; in steady state the basefee tracks demand. A timer that doesn't fit in one block at its declared `max_fee_per_cycle` will fit a few blocks later as the basefee falls. This replaces the exponential bias multiplier with a *prospective* mechanism (the price drops to meet demand) rather than a *retrospective* one (the bid gets bonus weight after being deferred). The bias-gaming attack is structurally impossible - there is no bias to game.
1. **R4 closes by elimination.** When the rule is "your priority tip × cycle count is your priority," there is no opaque clearing-price signal that sophisticated GBAs can exploit better than naive ones. Industrial wallets do it correctly; specialised GBAs add value only in the value-estimation step (which is application-specific, not mechanism-specific).
The cost is honest engagement with the trade-off: the design review's §9.4 explicitly notes that "aggressive GBA auctioning produces volatile, unpredictable effective fees." Concept C resolves the tension by abolishing the auction, but in doing so it abandons the explicit "ordering should respect premium when premium is paid" principle Caleb articulated - at least in its strongest form. Under EIP-1559, two timers with different `priority_tip_per_cycle` are ordered by tip, which respects premium; but two timers with the same tip but very different *willingness-to-pay* are not differentiated. For most actors this is fine; for actors with strong time-of-execution preferences (e.g., a DeFi liquidator that needs execution at exactly the right moment) it is potentially a regression versus an explicit auction. Concept C offers an explicit `priority_tier_hint` in the SDK that nudges the GBA to bid more aggressively, but this is a UX overlay rather than a mechanism feature.


#### Architecture diagram

![Screenshot 2026-05-05 at 13.29.28.png](./assets/189e6c7d_Screenshot_2026-05-05_at_13.29.28.png)


#### Key mechanisms

- **Timer-lane basefee.** A dedicated basefee for the Timer lane (in addition to, not replacing, the cycles basefee per CIP-3). Adjustment per block: `bf_{H+1} = bf_H × (1 + clip((u - 0.5) / 0.5, -0.125, 0.125))` where `u = cycles_consumed_in_lane / 2,000,000`. This is the EIP-1559 formula scoped to the 2M-cycle Timer lane, with target 50% utilisation and 12.5% max adjustment. Burned on inclusion, per whitepaper §11.5.
- **Priority tip.** Per-cycle tip on top of basefee. Goes to proposer. Default GBA uses last block's p50 tip as launch estimate.
- **Inclusion rule.** Sort due-cohort timers by `priority_tip_per_cycle` (descending). Fill the lane up to 2M cycles. Excluded timers roll over to the next block at the same `max_fee_per_cycle` (no bias multiplier; no per-block re-bidding required).
- **Default GBA strategy.** `max_fee_per_cycle = 2 × current_basefee`, `max_priority_fee_per_cycle = previous_block_p50_priority_tip`. Updated at each scheduling event from on-chain state. Supports a `priority_tier_hint` ∈ {economy, standard, fast, urgent} that maps to multipliers {0.8×, 1.0×, 1.5×, 2.5×} on the priority-fee component - same UX as MetaMask's gas presets.
- **Per-timer cycle cap.** 250k cycles per timer fire.
- **Lane multiplier.** Flat 1.0×. The basefee adjustment carries the dynamic load; an additional fixed multiplier would just shift the steady state.
- **Anti-starvation.** Implicit: if your timer is rolled over for many blocks because tips are higher elsewhere, the lane basefee is falling (because the *Timer lane itself* must be congested for that to happen, which means utilisation > 50%, which means basefee is rising - wait, this is the opposite). Re-stating: if the lane is congested, basefee rises and excluded timers roll over until either (a) the actor raises `max_fee_per_cycle` via re-scheduling, or (b) congestion subsides. There is no permanent starvation as long as the actor's `max_fee` is at or above the steady-state basefee.
- **Pre-pay / escrow.** Same as A and B - lazy charge at execution.
- **Cycle-meter for GBA.** Unchanged.

#### Stakeholder impact


| Stakeholder | Impact vs. status quo |
|---|---|
| Validators | Same flow - basefee burn and priority-fee tip are familiar patterns; no new aggregation work. |
| Actors / Developers | Highest predictability across all three concepts. EIP-1559 fee estimation is industry-standard; SDKs and wallets already do this. Cost: actors with strong time-of-execution preferences (e.g., MEV-exploiting timers) get less ordering control than under an explicit auction. The `priority_tier_hint` partially closes this. |
| GBAs (third-party) | Sharply reduced economic role. EIP-1559 bidding is a solved problem; third-party GBAs add value mainly in value-estimation (application-specific), in cross-actor coordination, or as managed services. This is healthy - it pushes GBA innovation toward application logic, not mechanism arbitrage. |
| End Users (EOAs) | Indirect benefit: predictable wallet UI for any flow that involves a scheduled timer. |
| Treasury | Same burn flow. Tips to validators are higher under congestion than under uniform-price, mildly negative for "fee sustainability" in Objective #4 (out of scope here). |
| Security Council | No change. |


#### Brief analysis

- **Strengths.** Highest score on Objective #8 (Predictable Fee UX) - by using the most-deployed fee mechanism in the industry, predictability is solved by reuse rather than by design. Highest score on R4 closure (no opaque auction signal to exploit). Eliminates the bias multiplier entirely and with it the bias-gaming attack. Eliminates G7 by reducing the default GBA to a wallet-style estimator. Smallest GBA-specification surface area to audit.
- **Weaknesses.** Under-delivers on Objective #7's "ordering should respect premium when premium is paid" (Caleb's 27 Apr point) compared to an explicit auction. Two timers with the same tip but different value get the same priority. Adding the `priority_tier_hint` overlay restores some ordering control but it is a UX overlay, not a first-class mechanism.
- **Risks.** (1) **MEV-shaped timers want explicit auctions.** A timer that captures MEV (e.g., liquidations, arbitrage) has a very high willingness-to-pay for exact-block execution. Under EIP-1559, such timers will pay aggressive priority tips and effectively re-create an auction *via tip levels* - at which point Concept C is operationally similar to Concept A but with smoother basefee dynamics. This is fine *if* MEV-shaped timers stay a small share of total timer volume; it becomes a problem if they are dominant, because high-tip timers can monopolise the lane. Mitigation: the per-timer 250k cycle cap limits any one timer to 12.5% of the lane regardless of tip. (2) **Lane utilisation target calibration.** The 50% target assumes ~50% lane headroom is the right balance between throughput and price-stability. Phase-5 simulation should sweep this; Ethereum's choice of 50% is well-studied but the timer workload's smoothness profile may differ. (3) **Roll-over latency under sustained congestion.** Under a multi-block congestion spike, timers keep rolling forward at their `max_fee_per_cycle`. If the basefee rises above their max for many blocks, they remain stuck. The actor must re-schedule with a higher `max_fee` to recover. This is a UX cost at the tail.
- **Precedents.** **Ethereum EIP-1559** (live since Aug 2021) is the direct ancestor and the empirical evidence base. The decentralizedthoughts.github.io retrospective and Tim Roughgarden's analysis are the standard references. **Solana priority fees + Jito tips** show what happens when a non-EIP-1559 chain bolts on a tip auction post-hoc - Jito tips now account for >60% of non-base-fee revenue, which is exactly the sort of unintended centralisation Concept C avoids by integrating the tip into the base mechanism. **Optimism / Arbitrum / Base** are EIP-1559 forks with sub-lane equivalents - concrete evidence that the mechanism scales down to a single lane within a multi-lane context. **Gelato Network's automation pricing** charges a percentage of gas cost, which is the pattern Cowboy's GBA-as-a-service market would converge on under Concept C.

---


### Summary Comparison


| Dimension | A: Whitepaper Target Closure (DATUM) | B: Uniform-Price + Per-Actor Fairness | C: EIP-1559 Timer Basefee |
|---|---|---|---|
| **Architectural change vs whitepaper target** | Minimum (parameter additions only) | Mechanism replacement (auction rule + bias) | Mechanism replacement (auction → EIP-1559) |
| **Risks closed (R4 default GBA disadvantage)** | Partial (default-GBA spec'd, but still disadvantaged) | At source (uniform-price → no bidding edge) | At source (no auction → no bidding edge) |
| **Bias-gaming attack** | Cap at 5× - partial mitigation | Replaced with per-actor weight - eliminated | Eliminated by removing bias entirely |
| **Game-ability surface (Caleb 27 Apr)** | First-price equilibrium difficulty + bias | Fragmentation across actors (testable) | Tip-level mini-auction (limited by per-timer cap) |
| **DevX (Caleb's meta-objective)** | Ambiguous - depends on default-GBA quality | Predictable clearing prices, honest bidding | Highest - industry-standard EIP-1559 |
| **Best fit for Objective #7 (liveness / fairness)** | Retrospective bias mitigation | Strongest - per-actor fairness directly enforces "no monopolisation" | Implicit via basefee dropping; weaker on hard fairness guarantees |
| **Best fit for Objective #8 (predictable fee UX)** | Weakest - first-price clearing volatility | Stronger - uniform-price clearing smoother | Strongest - reuses EIP-1559 fee estimation |
| **Default GBA complexity** | Vanilla multiplier - moderate | Value-aware - moderate | EIP-1559 estimator - minimal (industry-standard) |
| **Per-timer cycle cap** | None (status quo weakness) | 250k | 250k |
| **CIP authoring required** | None (parameter additions) | One CIP (mechanism + per-actor weight) | One CIP (lane EIP-1559) |
| **Whitepaper §11.5 lane multiplier setting** | 1.0× | 0.8× (timer subsidy) | 1.0× |
| **C7 / hard-commitments touched** | None | None | None |
| **Phase-5 simulation parameters** | Bias cap, default-GBA increment rule | α (per-actor weight scale), 1000-block window, lane multiplier | Lane utilisation target, basefee adjustment ceiling |


---


### How the three concepts relate to the Caleb 27 April discussion

Quoting from Caleb's framing during that call:

> *"For auctions, second-price auctions are kind of nice because honest bidding is a weakly dominant equilibrium… the uniform price auction. That's kind of the one I've been working on recently and kind of comparing that to the first price auction."*

→ **Concept B** is the formalisation of this preference, augmented with the per-actor fairness weight to address the bias-gaming concern Caleb raised separately in the same call.

> *"That bias really, it's just to ensure liveness… it doesn't really need to be added all the time… one of the ideas I was playing around with was maybe we cap the opportunity cost of adding this bias."*

→ All three concepts respect this. **Concept A** caps the multiplier at 5×. **Concept B** replaces the per-timer bias with a per-actor weight that is structurally bounded. **Concept C** removes the bias entirely.

> *"I think one of the things that Chad said was he wants it to be easy and predictable for developers essentially."*

→ This is the meta-objective. Ranking against it: **Concept C > Concept B > Concept A**. Concept C wins this dimension definitively because it imports a battle-tested fee mechanism. Concept B wins on "ordering respects premium" but loses some predictability. Concept A is weakest on this dimension by construction.

> *"Sometimes the best design isn't even possible until we get live data… the full fledged mechanism is kind of launched in a more simplistic state."*

→ All three concepts are launchable. **Concept C** is the most "launch-simple" because it reuses EIP-1559 implementations from existing EVM stacks. **Concept A** is the most "launch-aligned with team intent." **Concept B** sits between them in launch complexity.


---


### Recommended Next Steps

1. **Cowboy/Caleb selects scope of Phase 3 (Concept Selection).** All three concepts pass MVE constraints. Caleb's preference (uniform-price) maps to Concept B; the team's existing intent (whitepaper §5.1 target) maps to Concept A; the lowest-risk-on-DevX option is Concept C. We recommend carrying all three forward unless the team rules one out for organisational reasons.
1. **Confirm objectives and weights.** This document is scored against §9.2 Objectives **#7 (Timer Liveness and Fairness)** and **#8 (Predictable Fee UX)**. Phase 3 will need importance weights (0–100) per objective. Given the design review's §9.4 explicit tension between #7 and #8, the relative weighting is the load-bearing decision.
1. **Resolve gap G7 in parallel.** Whichever concept is selected, the Cowboy team's view on the default GBA's bidding strategy is independently load-bearing. Concept A specifies a vanilla multiplier; Concept B specifies a value-aware estimator; Concept C specifies an EIP-1559 estimator. Pre-clearing this with the scheduler team accelerates Phase 4.
1. **Coordinate with the Runner Marketplace concept generation.** Both subsystems compete for block cycles (Runner = 25%, Timer = 20%). Lane fee multipliers (whitepaper §11.5 reconsideration) are a cross-subsystem decision; Concept B for the timer subsystem proposes 0.8× while the Runner concepts assume 1.0×. The eventual Critical Design Review needs to make the lane-multiplier setting consistent across subsystems.
1. **Scope Phase-5 simulation now.** For Concept A, the load-bearing parameter is the bias cap (5× is a placeholder). For Concept B, it is the per-actor weight scale α and the rolling window length. For Concept C, it is the lane-utilisation target. All three can be parameterised in a single RadCad model with the auction rule as a switchable component - efficient if Cowboy elects to prototype before locking the choice.

---


### Disclaimer

This documentation is provided for informational purposes only and is based on a modified version of MIT's Model-Based Systems Engineering process adapted for blockchain mechanism design. It does not constitute financial, investment, or legal advice. All concepts described are design proposals; none has been implemented, audited, or formally verified. References to existing protocols (Ethereum / EIP-1559, Solana / Jito, Bitcoin, Cosmos, Optimism / Arbitrum / Base, Gelato, Chainlink Automation) describe their public mechanism designs as of April 2026 and may be superseded by subsequent protocol changes. References to Cowboy whitepaper sections, CIPs, and parameter values reflect public documentation available as of the design review date and may be superseded by subsequent Cowboy team decisions. References to the 27 April 2026 Cowboy/Caleb timer-auction discussion paraphrase the meeting transcript; readers should treat the original transcript as authoritative on Caleb's stated preferences. Vending Machine makes no representation that any specific concept or parameter will be selected by the Cowboy team, nor about the eventual launch parameters of the Cowboy Protocol.


---


### Appendix A — Mapping concepts to design-review risks and gaps


| Risk / Gap | Concept A: Whitepaper Target Closure | Concept B: Uniform-Price + Per-Actor Fairness | Concept C: EIP-1559 Timer Basefee |
|---|---|---|---|
| **R4** Default GBA disadvantages non-sophisticated actors | Partial - default GBA spec'd, but still systematically out-bid by sophisticated GBAs | Closed at source - uniform-price makes honest bidding weakly dominant; sophistication offers no edge in bidding | Closed at source - EIP-1559 mechanism makes wallet-style estimation industry-standard; sophistication offers no edge |
| **G7** Default GBA bidding strategy spec | Vanilla basefee multiplier (Caleb's described default) | Value-aware: `max(0, value(t+1) − α_op·p20_clearing) / cycles` | EIP-1559 estimator: `max_fee = 2·basefee, max_priority_fee = p50_priority_fee` |
| **Bias-gaming attack** (Caleb, 27 Apr) | Cap exponential bias at 5× | Replace with per-actor fairness weight (cannot be gamed via timer spam) | No bias - eliminated structurally |
| **First-price knapsack equilibrium difficulty** | Unaddressed (inherent to first-price) | Resolved - uniform-price clearing | Resolved - no auction at all |
| **Per-timer cycle cap missing** | Unaddressed (status quo) | 250k cycles per timer fire | 250k cycles per timer fire |
| **GBA invalid bid handling** | Clamp to actor balance | Clamp to actor balance | Reject above declared `max_fee` |
| **Whitepaper §11.5 per-lane fee multiplier** | 1.0× flat | 0.8× (governance-tunable) | 1.0× flat |
| **Objective #7 (timer liveness/fairness)** | Capped exponential bias (retrospective) | Per-actor fairness weight (prospective and structural) | Implicit via basefee dropping when lane under-utilised |
| **Objective #8 (predictable fee UX)** | Weakest - first-price clearing volatility | Stronger - uniform-price smoother | Strongest - EIP-1559 standard wallet estimation |
| **Statistical-pattern exploitation** (Caleb, 27 Apr) | Possible - first-price + bias creates many statistical signals | Constrained - uniform-price reveals only the clearing price; weight is per-actor not per-timer | Constrained - fee history is the only signal, already studied in EIP-1559 literature |


---


### Appendix B — Sources

- *Cowboy Protocol — System Architecture Design Review*, Vending Machine, April 2026 (Notion).
- *Cowboy meets with Caleb regarding Timers/Auctions*, internal meeting transcript, 27 April 2026.
- *🥾 Whitepaper Sections for Reconsideration*, Vending Machine, April 2026 (Notion) — §5.1 split between current FIFO (CIP-5 rev 2026-03-19) and target GBA auction (CIP-1).
- *Cowboy Runner Marketplace — Concept Generation*, Vending Machine, April 2026 — sibling document; cross-references on lane fee multipliers.
- EIP-1559 mechanism design — [Ethereum EIPs / EIP-1559 spec](https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1559.md); [Decentralized Thoughts — ](https://decentralizedthoughts.github.io/2022-03-10-eip1559/)[*EIP-1559 In Retrospect*](https://decentralizedthoughts.github.io/2022-03-10-eip1559/)[ (2022)](https://decentralizedthoughts.github.io/2022-03-10-eip1559/); [Roughgarden — ](https://ethereum.github.io/abm1559/notebooks/eip1559.html)[*EIP 1559: A transaction fee market proposal*](https://ethereum.github.io/abm1559/notebooks/eip1559.html)[ (notebook)](https://ethereum.github.io/abm1559/notebooks/eip1559.html); [Empirical Analysis of EIP-1559 (arXiv 2201.05574)](https://arxiv.org/pdf/2201.05574).
- Solana priority fees and Jito tip auction — [Helius — ](https://www.helius.dev/blog/block-assembly-marketplace-bam)[*Block Assembly Marketplace (BAM)*](https://www.helius.dev/blog/block-assembly-marketplace-bam); [QuickNode — ](https://blog.quicknode.com/solana-mev-economics-jito-bundles-liquid-staking-guide/)[*Solana MEV Economics: Jito, Bundles, Liquid Staking*](https://blog.quicknode.com/solana-mev-economics-jito-bundles-liquid-staking-guide/); [Helius — ](https://www.helius.dev/blog/solana-local-fee-markets)[*The Truth about Solana Local Fee Markets*](https://www.helius.dev/blog/solana-local-fee-markets).
- Gelato automation pricing model — [Gelato Web3 Functions](https://www.gelato.network/web3-functions).
- Auction theory references — [Wikipedia — Knapsack auction](https://en.wikipedia.org/wiki/Knapsack_auction); [Wikipedia — Vickrey–Clarke–Groves auction](https://en.wikipedia.org/wiki/Vickrey%E2%80%93Clarke%E2%80%93Groves_auction); [Ausubel — ](https://www.cs.cmu.edu/~sandholm/cs15-892F15/Ausubel_Auction_Theory_Palgrave.pdf)[*Auction Theory for the New Economy*](https://www.cs.cmu.edu/~sandholm/cs15-892F15/Ausubel_Auction_Theory_Palgrave.pdf).
- Adaptive transaction fee mechanisms in blockchains — [*Tiered Mechanisms for Blockchain Transaction Fees*](https://arxiv.org/pdf/2304.06014)[ (arXiv 2304.06014)](https://arxiv.org/pdf/2304.06014); [*Blockchain Fee Policies: Quantity- vs Price-Control Design across Protocols*](https://abdouecon.github.io/research/papers/feepolicies.pdf).
