# 🥾 Whitepaper Sections for Reconsideration

<!-- Notion page id: e98e6c7d-52db-8367-b84e-017e2ccac285 -->

**Source whitepaper:** *Cowboy: A Layer-1 Blockchain for Autonomous Agents*, April 2026 - Draft v0.9.2

**Driving inputs:** the Phase-1 design review (Risks R1–R15, Gaps G1–G16, Tensions T1–T10, §2 findings), the freshness check vs CIP-12 / CIP-5 / CIP-2 / CIP-13, and the wiki source-authority hierarchy (latest CIP > whitepaper).

> Three priority bands are used throughout this document:
> - **CRITICAL** - design-level changes that must land before TGE; missing today leaves the protocol economically circular or governance-broken.
> - **HIGH** - values or behaviours specified vaguely or out of sync with newer CIPs; load-bearing for simulation.
> - **MEDIUM** - internal inconsistencies, math errors, framing fixes, drift cleanup.


---


### CRITICAL


#### §8.2 Inflation (and §13 / §27 Parameters)

**What's wrong**

- The schedule (8% / 6% → 4% / 3% → 2% floor) is well-defined, but four load-bearing parameters are absent:
  - `minimum_validator_stake` at genesis (G1)
  - the inflation-adjusted validator APR target (G2)
  - the security-floor trigger threshold that re-arms inflation when the staked ratio drops (G3)
  - the runner-reward emission curve for the 80M CBY Runner Compute Incentives bucket (G10)
- §13 / §27 lists `minimum_validator_stake = governance-tunable`, but governance itself requires staked CBY, which requires validators, which requires a stake floor (review §2.1).
**Why it matters**

- Risk R9: staking ratio races to zero if CBY crashes early.
- Risk R12: validators can't make build-vs-rent decisions without a target APR.
- Tension T3 (validator accessibility vs security budget) cannot be resolved without a number.
**Suggested edit**

- Add three concrete genesis defaults that simulation can later refine via Tier-0 governance:
  - `minimum_validator_stake_genesis` = a concrete CBY value
  - `validator_apr_target` = a real-rate band (e.g., 4–6% inflation-adjusted)
  - `security_floor_staked_ratio` = e.g., 33%, with a stated boost step
- Define the Runner Compute Incentives release curve over its 60-month window (linear, front-loaded, or usage-rate-locked).

---


#### §11.3 Slashing (and §25.3 normative tier table)

**What's wrong**

- The 1% double-sign slash is the softest in the L1 class (Cosmos ~5%, Ethereum correlation-scaled to 50%+, Polkadot up to 100%). The whitepaper frames this as deliberate ("jailing rather than stake destruction") but does not articulate the assumption: that reputational and opportunity costs of jailing substitute for economic slashing. At launch those reputational costs **don't yet exist**.
- §11.3 / §25.3 governance tier defaults are now superseded by CIP-12 (2026-04-09). The whitepaper still shows Tier 0: 10% / Tier 4: 33% / >75%; CIP-12 has these at Tier 0: 5% / Tier 4: 20% / >66%. Per the wiki source-authority rule, the CIP wins.
**Why it matters**

- Risk R1 (1% slash too weak); Tension T8; review §2.4.
- The CIP-12 tier drift was flagged in the freshness check.
**Suggested edit**

- Add a paragraph in §11.3 stating the assumption behind 1% (reputational + opportunity cost as the dominant deterrent) and committing to a review trigger (e.g., "if any single offense's economic value exceeds N × stake-at-risk, slashing severity will be escalated via Tier 0").
- Replace the §11.3 / §25.3 tier table with the CIP-12 numbers, and add the proposal-deposit / temperature-check / voting-window columns CIP-12 introduces.

---


#### §16 / §30 Ethereum Interoperability

**What's wrong**

- §16 explicitly defers bridge selection to governance: *"Bridge selection and integration are determined by governance. The protocol does not implement its own bridge validator set."*
- This pushes the most security-critical decision in the entire protocol onto the first major governance vote, which itself launches with unset validator parameters.
**Why it matters**

- Risk R6 (third-party bridge as weakest link) is scored Critical priority for Phase 2.
- Review §2.7 treats this as a latent critical-path item.
- Gap G9 names it explicitly.
**Suggested edit** — replace the open-ended "governance decides" stance with one of:

- **Option (a):** Pre-select a bridge via the core team with a stated retirement-via-governance escape hatch, with named candidate(s) and the security-bound criterion ("bridge stake ≥ Σ TVL bridged").
- **Option (b):** Launch with bridging disabled at the protocol level and treat Ethereum interop as a post-launch feature gated on a governance-elected bridge meeting criterion (a).
The current implicit path - ‘launch with both governance and bridge unspecified’ - should be removed.


---


#### §9 / §19 Runner Marketplace

**What's wrong** - three load-bearing economic mechanisms are described qualitatively but not parameterised:

- **Aggregator bonus magnitude.** §9 / §19.3 says "a small bonus" with no formula or range (G5, R11).
- **Behaviour on commit-without-reveal.** §19.3 specifies the aggregator timeout but not the **classification** of a non-revealing non-aggregator runner (operational failure → reputation only, vs proven dishonesty → slash). This binary determines whether the 89/10/1 split is honest pricing of integrity (G6, R2).
- **Reputation decay/recovery functions and their interaction with VRF selection weight** — referenced throughout §9 but never defined (G4, R13).
Additionally:

- The static M=5 / N=3 committee size is fixed for the lifetime of the protocol with no adaptive sizing rule, even though committee-capture probability is acutely population-sensitive at low runner counts (R3, T1).
**Why it matters**

- Review §2.2 names runner-market integrity as the highest-novelty / highest-risk subsystem.
- Three of the top five Phase-2 priority risks (R2, R3, R11, R13) live here.
**Suggested edit** - add §9.4 (or expand §19) with:

- A formula for the aggregator bonus tied to job size, e.g. `bonus = max(C_min, k × job_payment)`, with `C_min` in CBY.
- An explicit ruling on non-reveal: classify as proven dishonesty by default (slash), with a single timer-based exemption window for legitimate crashes.
- A reputation-decay specification: an EMA-style recovery formula with stated half-life and floor.
- An adaptive committee rule: `M = max(M_min, ceil(α × log₂(active_runner_count)))`, with `M_min = 5` at launch.

---


#### §12 / §17.5 / §17.6 State Rent + CBFS Storage

**What's wrong** - three distinct issues, currently bundled:

1. **Internal inconsistency on actor-state eviction timing.** §4.4 says eviction "after 10 rent-epochs"; §12.3 describes Grace 7 + Warning 3 + "Eviction (rent-epoch N+11)" - i.e. 11; §17.5 says `eviction_threshold = 10 rent-epochs unpaid rent`. The text disagrees with itself by ±1 epoch.
1. **CBFS Relay economics fully undefined.** §17.6 mentions per-byte-per-epoch volume rent and Relay attestations, but no per-byte rate, no challenge bond, no Relay slashing schedule (G8). The 10%-burn / 90%-relay split observed in the `cowboy-ras` crate (`STORAGE_FEE_BURN_BPS = 1000`) is not documented in the whitepaper at all.
1. **Rent is CBY-denominated, not USD-stable.** At CBY=$0.10 the 0.001 CBY/byte/year rate is trivially cheap; at CBY=$10 it becomes punitive. The auto-adjustment formula self-corrects in CBY terms only.
**Why it matters**

- Gaps G8, G15.
- Risks R5, R14.
- Tension T2.
- Review §2.5.
**Suggested edit**

- Reconcile §4.4 / §12.3 / §17.5 on a single eviction threshold (recommend: 10 rent-epochs) and rewrite §12.3 to remove the "N+11" framing.
- Add a §17.6 subsection covering the CBFS Relay control plane: per-byte-per-epoch storage rate (concrete starting value), 10/90 burn/relay split, Relay challenge bond, and Relay slashing schedule for proof-of-retrievability failures.
- Add a paragraph acknowledging the CBY-denominated rent assumption and either commit to monitoring + Tier-0 adjustment cadence, or flag a future CIP for oracle-anchored rent.

---


### HIGH


#### §5.1 Native Timers and the Actor Scheduler

**What's wrong**

- The whitepaper describes the **target** design (CIP-1 with tiered calendar queue + Gas Bidding Agent auction).
- The currently-implemented behaviour, per CIP-5 (rev 2026-03-19), is **FIFO within a height bucket with the auction deferred to Phase 3** - this is what's running on devnet today.
**Why it matters**

- Wiki drift table.
- Review §2.3.
- Risk R4 (default GBA disadvantages non-sophisticated actors) only matters once GBA ships.
**Suggested edit** - split §5.1 into two clearly-labelled subsections:

- **Currently Implemented (CIP-5):** FIFO within height bucket; `MAX_TIMERS_PER_ACTOR = 1024`; fixed 550k cycle / 550k cell budget per fire.
- **Target Design (CIP-1):** GBA auction, tiered calendar queue, anti-starvation weights. Note clearly that this ships in CIP-5 Phase 3.

---


#### §11.1 / §25 Governance — Security Council and Delegator Voice

**What's wrong**

- The Security Council is "permanent, reduce only via Tier 4" (§11.2). No sunset path tied to network maturity is specified. At launch this is prudent; at year 5 with a healthy validator set it may become a political fixture (T9, review §10.9).
- Runner-delegated CBY has zero governance weight in v1 (§11.1, per CIP-13 §6.1). Delegators bear slashing risk but cannot influence runner-relevant parameters - a future legitimacy problem (R7, review §10.6).
**Suggested edit**

- Replace "permanent" framing with a **conditional-sunset clause**: e.g., "Council scope reduces by one named power per year once {validator_count ≥ N AND staked_value ≥ V} for two consecutive epochs," with concrete N / V values to be set in CIP-12 amendment.
- Add a path for **partial delegator vote weight** (e.g., 25%) on **runner-parameter-specific proposals only**, deferred to CIP-13 §9.6 follow-up.

---


#### §13 / §27 Parameters - Math Errors and Missing Defaults

**What's wrong**

- `unbonding_blocks = 7,200 (~24h)` is arithmetically wrong at the stated 1-second block time. 7,200 blocks at 1 block/sec = 7,200 s = 2 h. For ~24 h you need ~86,400 blocks.
- Several parameters required for simulation (G1, G3, G10, G11, G15, G16) are missing from §13 / §27 entirely.
**Suggested edit**

- Either correct the comment to "~2 hours" if 7,200 is intentional, or bump the constant to 86,400 if 24 hours is intentional. Pick one and reconcile with CIP-13.
- Audit §13 and add genesis defaults for the parameters listed in the Gaps register.

---


#### §9.2 LLM Result Verification

**What's wrong**

- The `semantic_similarity` mode threshold is unspecified.
- A circularity exists if the embedding model used for similarity is itself decided by governance (R10): a runner could collude with the embedding choice.
- The whitepaper doesn't acknowledge or address the issue.
**Suggested edit** - add a one-paragraph note stating that:

- The embedding model used for `semantic_similarity` verification must be pinned in the model registry under the same governance-flag/ban semantics as inference models.
- Any change to the embedding model is itself a Tier-3 (or higher) proposal because it changes consensus-relevant verification semantics.

---


#### §8.3 Distribution - Emission Curves

**What's wrong**

- The distribution table specifies bucket sizes (180M validator, 80M runner, 23.3M LM, etc.) and high-level shapes ("front-loaded over 12 months"), but no actual curves.
- For simulation we need the function form (linear / exponential / step) and the per-step CBY rate.
**Suggested edit**

- Add per-bucket emission curves to §8.3 - at minimum the closed-form expression and the first 24 months of monthly CBY emissions.
- Mark these as Tier-0 governance-tunable but commit to genesis defaults.

---


### MEDIUM


#### §4.4 / §16.2 Broken cross-reference

**What's wrong** - §16.2 cites "(§13.1)" for transaction-validity limits. §13 (the State Transition Function) has no §13.1 sub-section. The intended target is §12.1 ("DoS limits") or §27 (the parameter table).

**Suggested edit** - fix the cross-reference.


---


#### §11.5 / §25.5 Dedicated Lanes - Implementation Note

**What's wrong** - the lane allocation (System 5 / Timer 20 / Runner 25 / User 50) matches CIP-3, but the per-lane fee multipliers are referenced ("each lane has independent fee multipliers") without being specified.

**Suggested edit** - either commit to genesis multipliers (e.g., 1.0× / 0.8× / 1.0× / 1.0×) or explicitly mark them as Tier-0 governance-tunable with a short rationale for what each multiplier is intended to incentivise.


---


#### §5.1 Same-Block Timer Prohibition Wording

**What's wrong** - §5.1 says timers "MUST NOT fire in the current block" (good) and elsewhere mentions an exponential same-block surcharge for k > 16 timers at the same height. The two sections need cross-referencing.

**Suggested edit** - cross-link.


---


#### §11.6 / §25.6 MEV Reduction - Limitations

**What's wrong** - the whitepaper currently lists what Cowboy's MEV mitigation **does**. It should also clearly enumerate what it does **not** prevent: proposer inclusion / censorship, private orderflow MEV, JIT MEV against actors with predictable handler logic.

**Suggested edit** - append an explicit "Out of scope" subsection to §11.6 / §25.6.


---


### Section-priority summary


| Priority | Whitepaper section(s) | Theme | Delegation |
|---|---|---|---|
| CRITICAL | §8.2 + §13 / §27 | Inflation parameters, validator economics genesis defaults | VM Sims |
| CRITICAL | §11.3 / §25.3 | Slashing rationale + governance tier values (sync to CIP-12) | @user  |
| CRITICAL | §16 / §30 | Bridge selection - pre-mainnet decision | Cowboy |
| CRITICAL | §9 / §19 | Runner marketplace and timer + GBA integrity | @user  |
| CRITICAL | §12 / §17.5 / §17.6 | State rent reconciliation + CBFS Relay economics | @user  |
| HIGH | §5.1 | Split current (CIP-5 FIFO) vs target (CIP-1 GBA auction) | @user  |
| HIGH | §11.1–§11.2 / §25 | Council sunset path + delegator partial vote weight | @user  |
| HIGH | §13 / §27 | Math fix on `unbonding_blocks` + missing genesis defaults | @user  |
| HIGH | §9.2 | `semantic_similarity` embedding-model circularity | @user  |
| HIGH | §8.3 | Per-bucket emission curves | VM Sims |
| MEDIUM | §16.2 | Broken §13.1 cross-reference | @user  |
| MEDIUM | §11.5 / §25.5 | Per-lane fee-multiplier defaults | Cowboy |
| MEDIUM | §5.1 | Same-block surcharge cross-link | @user  |
| MEDIUM | §11.6 / §25.6 | Explicit MEV limitations | @user  |


---


### Scope notes

> This is **not** a recommendation that the whitepaper land any specific number - only that a number land in each cell that is currently empty or out of sync with a newer CIP. Phase 5 simulation is the place where the candidate numbers are stress-tested before they go into a Tier-0 proposal.

> This is also **not** a complete diff against the whitepaper text. Editorial nits, typos, and cross-references that don't change the design are out of scope here.

**Expected throughput from this list:** Cowboy Labs reviews each row and marks "agreed / disagreed / already addressed in CIP-X / will fix in next draft," and we get a clean v0.9.3 that VM's Phase 2 simulation can anchor to.
