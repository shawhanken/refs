# 05 — Tokenomics, Inflation, Emission Curves

## TL;DR

- **Inflation schedule is out of sync internally.** WP §8.2 still ships the 4-year glidepath `8%/6% → 4%/3% → 2%`, but Chad's Initial-Questions Q6 response commits to the 3-year glidepath `4% → 3% → 2%` ("I'm going to update the whitepaper today to match"). The reviewer's flag is still accurate; the WP edit Chad promised has not landed. This is the single biggest open decision in this topic.
- **Genesis defaults for the macroeconomic anchors are missing.** WP §13 has no entry for `validator_apr_target`, no entry for `security_floor_staked_ratio`, no closed-form emission curve for any of the five Network Distribution buckets (Validator Rewards 180M, Runner Compute Incentives 80M, Developer Grants 30M, Liquidity Mining 23.3M, Community/Airdrops 20M). Reviewer items #17 / #26 / #30 / #31 / #48 / #49 / #66 all still hold.
- **Treasury 1% take is a policy question Chad has verbally accepted (Q4: "fair point and it makes the math weird, i think we're ok with that"). The WP §8.4 spec still shows `89% runner / 10% burn / 1% treasury`; CIP-2 implements it via on-chain `SettlementConfig` at `0x09`. Removal would amend WP §8.4 and require a Tier-3 (`SettlementConfig`) governance hook update — not a code-only change.

## Items index

| # | Title | Priority | Touches | Status | Action |
|---|---|---|---|---|---|
| 3 | Inflation schedule discrepancy (8/6→4/3→2 vs Chad's 4→3→2) | P1 | WP §8.2 | actionable | WP §8.2 edit + decision-register |
| 48 | §8.2 inflation needs genesis defaults for validator economics | P1 | WP §8.2 / §13 | actionable | WP §13 amendment (genesis defaults) |
| 4 | Net inflationary vs deflationary stance | P2 | WP §8.2 | policy-decision | WP §8.2 wording change |
| 17 | Validator APR target unspecified | P1 | WP §13, CIP-12 | actionable | WP §13 add `validator_apr_target` |
| 39 | Validator APR unspecified prevents build-vs-rent decisions | P1 | WP §13 | actionable | merges with #17 |
| 26 | Security-floor inflation trigger unspecified | P1 | WP §8.2 / §13 | actionable | WP §8.2 mechanism + WP §13 defaults |
| 30 | Runner Compute Incentives 80M CBY emission schedule | P1 | WP §8.3, CIP-2 | actionable | WP §8.3 curve + cross-link CIP-2 |
| 49 | Runner Compute Incentives release curve must be defined | P1 | WP §8.3 | actionable | duplicate of #30 — single fix |
| 31 | Liquidity Mining 23.3M CBY emission curve | P2 | WP §8.3 | actionable | WP §8.3 closed-form expression |
| 66 | §8.3 emission curves for all buckets | P1 | WP §8.3 | actionable | per-bucket curves table |
| 2 | Treasury 1% — consider removal (cross-ref) | P2 | WP §8.4, CIP-2 | policy-decision | decision-register + WP §8.4 edit if accepted |
| 41 | Treasury 1% from runner job payments (cross-ref) | P2 | WP §8.4 | policy-decision | merges with #2 |

---

## A. Inflation schedule (WP §8.2) — reconcile with Chad's latest thinking

### [3] / [48] Inflation schedule discrepancy and missing genesis defaults          (P1, status: actionable)

- **Reviewer source**     : `Initial-Questions.md` Q6 (Chad response); `Whitepaper-Sections-for-Reconsideration.md` §8.2 (CRITICAL)
- **Reviewer's "current"**: "Whitepaper §8.2 says inflation is 8%/6% → 4%/3% → 2%; your design-decisions doc (in public docs) says 5% → 1.5%. Which one reflects current thinking?"
- **Reviewer's proposal** : Chad's stated update — "4% year one, 3% year two, 2% steady state … because we have real compute costs, which burn CBY, there is naturally a bit of deflationary pressure, so we want some natural inflation. The 8% seemed too high from talking to Yin and others". Reviewer also asks for `minimum_validator_stake_genesis`, `validator_apr_target` (e.g., 4–6% inflation-adjusted), `security_floor_staked_ratio` (e.g., 33%).
- **Actual current state**:
  - WP §8.2 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:675-679`):
    ```
    | Bootstrap     | 1–2 | 8% / 6%   | Attract validators and runners while fee revenue is immature |
    | Glidepath     | 3–4 | 4% / 3%   | Reduce dilution as fee revenue and network stability improve |
    | Steady-state  | 5+  | 2% floor  | Maintain security budget with low long-run dilution |
    ```
  - WP §8.2 line 681: "Governance MAY adjust the inflation rate within the following guardrails: (a) hard cap of 10% gross annual inflation, (b) maximum annual change of 2 percentage points, (c) timelock + supermajority for any change. A security-floor trigger MAY temporarily increase inflation if the staked ratio falls below a governance-defined threshold; the increase auto-expires when the threshold is recovered."
  - WP §13 line 797 lists `supply, company_reserve, basefee burn, runner_fee_burn, job_fee_to_treasury, runner_payout` — but **does not** list `validator_apr_target`, `security_floor_staked_ratio`, or `minimum_validator_stake` (line 781: `minimum_validator_stake = governance-tunable`, no genesis number).
  - The "5% → 1.5%" variant the reviewer cites from a separate design-decisions doc is **not** present in WP v2 (no grep hit).
- **Verification**        : ✅ still accurate. WP §8.2 still ships the 4-year 8/6→4/3→2 schedule that Chad disowned in Q6. The promised "I'm going to update the whitepaper today" edit has not landed. Reviewer's other variant (5%→1.5%) is dead; Chad's `4→3→2` is the canonical replacement.
- **Recommendation**      : [WP §8.2 edit] + [WP §13 amendment] + [decision-register entry]
- **Specific change**     :
  1. WP §8.2 table: replace with
     ```
     | Bootstrap    | 1 | 4% | Attract validators and runners while fee revenue is immature |
     | Glidepath    | 2 | 3% | Reduce dilution as fee revenue and network stability improve |
     | Steady-state | 3+ | 2% floor | Long-run security budget; burn from real compute provides counterbalance |
     ```
  2. WP §8.2 narrative paragraph: state design intent — "the 2% floor is gross; net inflation depends on real-cycle and runner-fee burn (§8.4). At steady state we target **net slightly inflationary**, with the burn rate acting as a usage-elastic counterbalance rather than a hard deflationary commitment." (This replaces the older "net deflationary at steady state" framing — see item #4.)
  3. WP §13 add three new rows under **Economics**:
     - `validator_apr_target = 4–6%` (inflation-adjusted real rate, Tier-0 tunable, target band)
     - `security_floor_staked_ratio = 33%` (Tier-0 tunable)
     - `security_floor_boost_bps = 200` (additional gross-inflation bps added when staked ratio sits below floor for ≥ 30 consecutive days; auto-expires once recovered for 30 consecutive days)
  4. Decision-register entry G1 (this doc §G): commit to one of the two schedules before next CIP cycle.
- **Rationale**           : Chad's commitment in Q6 is explicit; the WP is the only authoritative artefact contradicting it. The 3-year vs 4-year glidepath difference matters for runner subsidy timing (§8.3 buckets) and validator-APR-at-launch modelling (§13). The genesis defaults are prerequisite for any simulation Phase 5 wants to run on validator economics — without them no build-vs-rent calculation is possible.
- **Open questions**      : (1) Does "year 1" start at TGE or at the first epoch after token unlock cliffs (6 months)? Pin in WP §8.2. (2) Is the 4% Y1 figure paid pro-rata from genesis or front-loaded into the first 6 months? Default to monthly-uniform across each year unless §8.3 emission curves dictate otherwise. (3) Does the hard cap stay at 10% gross under the new schedule, or drop (since the new max is 4%)? Recommend keep 10% — gives governance headroom for emergency security-floor boost.

---

## B. Net inflationary vs deflationary stance

### [4] Net stance — replace "net deflationary at steady state" with "net slightly inflationary"          (P2, status: policy-decision)

- **Reviewer source**     : `Initial-Questions.md` Q5 (Chad response)
- **Reviewer's "current"**: "'Net deflationary at steady state' was the original goal" — but Chad's Q5: "Open to feedback, I'm not sure we have a strong preference here but net slightly inflationary is probably good."
- **Reviewer's proposal** : shift to "net slightly inflationary" stance; real compute burn provides natural deflationary pressure as a counterbalance, not as a target.
- **Actual current state**:
  - WP §8.2 line 673: "Gross inflation is offset by protocol burn mechanisms (§8.4); net inflation depends on network usage."
  - WP §8.4 line 718: "The runner fee burn is the primary deflationary mechanism beyond basefee burns. As network usage grows, the burn rate increases proportionally, creating a reflexive supply-reduction loop that offsets inflation (see §8.2)."
  - Neither line commits to a numerical net target. The "net deflationary at steady state" language the reviewer references is in older design-decisions docs, not in WP v2.
- **Verification**        : ⚠ partially — WP v2 already softened away from "net deflationary"; it now says "net inflation depends on network usage". Chad's Q5 answer is a position update, not a contradiction with the current WP. The reviewer's framing is slightly stale; the substantive question (commit to a target stance) is still open.
- **Recommendation**      : [WP §8.2 edit, editorial]
- **Specific change**     : In WP §8.2, add one explicit sentence after line 673: "At steady state the protocol targets **net slightly inflationary** issuance (gross 2% minus usage-elastic burn). Burn from basefees (§8.4) and runner job payments (§8.4) provides a deflationary counterweight that scales with real network demand, but is not engineered to over-deliver a net-negative supply at steady state." Couple this with the §8.2 rewrite in item #3.
- **Rationale**           : Cheap clarification; aligns documented stance with Chad's expressed preference and avoids the "supply-cap promise" trap. "Net slightly inflationary" is also the only stance compatible with a 2% floor — net deflation at 2% gross would require sustained burn ≥ 2% of supply/yr, which is implausible at launch volumes.
- **Open questions**      : None — purely a wording call.

---

## C. Validator APR target — genesis default missing

### [17] / [39] Validator APR target unspecified at launch          (P1, status: actionable)

- **Reviewer source**     : `Design-review.md` Section 8.2 (CLD key insight); Section 6 (Validators row); `Whitepaper-Sections-for-Reconsideration.md` §8.2 (CRITICAL § 8.2)
- **Reviewer's "current"**: "Inflation is minted and distributed to validators pro-rata, but target APR is not specified … Validator APR target, runner reward scaling, and security-floor trigger threshold are unspecified — this is the single most important finding."
- **Reviewer's proposal** : "Cowboy must commit to genesis defaults for validator economics, even if scheduled for early governance review. … `validator_apr_target` (e.g., 4–6% inflation-adjusted)."
- **Actual current state**:
  - WP §8.2 lines 672-681: schedule is gross inflation; no APR target.
  - WP §13 line 781: "`minimum_validator_stake` = governance-tunable; `epoch` = 3600 blocks (~1 h); `block_time` = 1 s; `finality` = ~2 s; `unbonding_period` = 7 days; `jail_period` = 24 h; `double_sign_slash` = 1%; `consensus_protocol` = Simplex BFT." No `validator_apr_target`.
  - CIP-12 has no validator APR specification either (it deals with governance mechanics, not economics).
- **Verification**        : ✅ still accurate. No `validator_apr_target` exists in WP, CIP-12, or anywhere else in `refs/cips/`.
- **Recommendation**      : [WP §13 add `validator_apr_target`] + [WP §8.2 narrative cross-link]
- **Specific change**     : (a) WP §13 add row: `validator_apr_target = 4–6%` (inflation-adjusted real rate; Tier-0 tunable; documented as a *target band*, not a guarantee). (b) WP §8.2: add one paragraph after the inflation table explaining how gross inflation flows: of the 4%/3%/2% gross issuance, the share allocated to Validator Rewards bucket (180M / 1B = 18%) is distributed pro-rata to active validators, scaled to deliver the `validator_apr_target` band under expected staked-ratio assumptions (e.g., 40-60% staked ratio at maturity). If actual staked ratio falls outside this range, governance recalibrates either the bucket-share or the target band via Tier-0.
- **Rationale**           : Reviewer's argument is sound: without a target APR, validator operators cannot model break-even hardware/ops cost and cannot make build-vs-rent decisions. The 4-6% real-rate band is consistent with the upper end of L1 norms (Cosmos ~7-10% nominal, post-Merge Ethereum ~3-4% real) and is achievable under the new 4→3→2 gross schedule given the 18% validator bucket. Pinning a *band* not a *point* keeps it tunable without inviting micro-amendments.
- **Open questions**      : (1) Should the band be inflation-adjusted (real) or nominal? Recommend real — protects validators from inflation devaluation, and matches Chad's "net slightly inflationary" framing in item #4. (2) Does `validator_apr_target` include delegated stake yield, or only operator-stake yield? Recommend total (operator + delegated, pre-commission) — most legible to validators. (3) What happens if actual APR drifts > ±50% from target band for > 1 epoch (90 days)? Recommend trigger automatic Tier-0 review proposal.

---

## D. Security-floor inflation trigger

### [26] Security-floor inflation trigger unspecified          (P1, status: actionable)

- **Reviewer source**     : `Design-review.md` Gap G3; `Whitepaper-Sections-for-Reconsideration.md` §8.2 (CRITICAL)
- **Reviewer's "current"**: "No trigger threshold defined for when inflation re-arms if staked ratio drops … If CBY crashes early and staking ratio races to zero, no safety valve exists."
- **Reviewer's proposal** : "Define `security_floor_staked_ratio` (e.g., 33%) with stated boost step."
- **Actual current state**:
  - WP §8.2 line 681: "A security-floor trigger MAY temporarily increase inflation if the staked ratio falls below a governance-defined threshold; the increase auto-expires when the threshold is recovered." — mechanism named, threshold and boost step **undefined**.
  - WP §13 — no `security_floor_staked_ratio`, no `security_floor_boost_bps`.
- **Verification**        : ✅ still accurate. The mechanism is referenced but its parameters are deferred to "governance-defined" with no genesis default. This is the exact pattern the reviewer flags as Gap G3.
- **Recommendation**      : [WP §8.2 spec] + [WP §13 add genesis defaults]
- **Specific change**     :
  1. WP §13 add three rows under **Economics**:
     - `security_floor_staked_ratio = 33%` (Tier-0 tunable; the staked ratio below which inflation boost activates)
     - `security_floor_boost_bps = 200` (additional gross-inflation bps applied while ratio sits below floor)
     - `security_floor_persistence_blocks = 2,592,000` (30 days at 1s block time; minimum consecutive duration below floor before boost arms; same for recovery)
  2. WP §8.2: replace the vague last sentence of line 681 with: "If the staked ratio falls below `security_floor_staked_ratio` for `security_floor_persistence_blocks` consecutive blocks, gross inflation is increased by `security_floor_boost_bps` until the ratio recovers above the floor for the same persistence window. The hard cap of 10% gross inflation (clause (a) above) applies regardless of how many concurrent boosts are active."
- **Rationale**           : Mechanism is already named in WP — the reviewer's gap is purely about pinning the parameters. The reviewer's `33%` example is a reasonable conservative floor (below 1/3 stake makes Byzantine attacks much cheaper). The 200 bps boost step is meaningful (raises 2% steady-state to 4% — same as Y1 bootstrap) without being punitive. Exact threshold should still defer to Phase-5 sim, but committing to the *mechanism shape* now closes the gap.
- **Open questions**      : (1) Is the floor measured over staked-CBY only, or staked-CBY + bonded-runner-stake (since runners also secure the network)? Recommend staked-CBY only — runner stake secures runner work, not consensus. (2) Does the persistence window run on wall-clock blocks or on epoch boundaries? Recommend wall-clock blocks (epoch boundaries introduce gaming windows). (3) Should the boost step itself be Tier-0 (fast) or Tier-2 (slower)? Recommend Tier-0 for the parameter, but the *trigger* should be automatic — governance shouldn't have to vote each time the floor breaches.

---

## E. Emission curves (Runner Compute Incentives, Liquidity Mining, all buckets)

### [30] / [49] Runner Compute Incentives 80M CBY emission schedule unspecified          (P1, status: actionable)

- **Reviewer source**     : `Design-review.md` Gap G10; `Whitepaper-Sections-for-Reconsideration.md` §8.2 (CRITICAL); concept-selection §8.2 emission notes
- **Reviewer's "current"**: "80M CBY bucket for Runner Compute Incentives exists; shape ('front-loaded' or linear) and duration unknown."
- **Reviewer's proposal** : "Define the 60-month window distribution (linear, front-loaded, or usage-rate-locked) with per-runner-hour rate formula." Concept-selection §8.2 line 206: "80M CBY genesis bucket, paid out flat per-runner-hour over defined emission window."
- **Actual current state**:
  - WP §8.3 line 702: `Runner Compute Incentives | 8.00% | 80,000,000 | Usage-based; paid per runner-hour`. No window, no rate formula, no curve.
  - CIP-2 has no emission schedule — it specifies job payment flow (`payment_per_runner`) but not the subsidy bucket.
- **Verification**        : ✅ still accurate. The WP literally says "paid per runner-hour" with no rate, no cap per hour, no total window length. No CIP claims ownership of this bucket either.
- **Recommendation**      : [WP §8.3 add per-bucket curve] + [cross-link CIP-2 §settlement]
- **Specific change**     : WP §8.3 — after the Network Distribution table, add a new subsection **"Runner Compute Incentives release curve"**:
  - **Window**: 60 months from TGE (`60 × 30 × 86,400 = 155.52M seconds`).
  - **Distribution shape**: linear with usage-rate-lock. Per-month notional emission = `80M / 60 = 1.333M CBY`. The notional is *available*, not *guaranteed*: actual paid emission per month is `min(notional, total_eligible_runner_hours × per_hour_rate)`, where `per_hour_rate` is governance-tunable (Tier-2) and defaults to `0.20 CBY/runner-hour` at TGE (selected so 1,333,333 CBY/month is fully claimed by ~6,940 healthy-runner-hours/month, ~9-10 sustained runners).
  - **Eligibility**: runner must be `Healthy + serving jobs` for the hour to count (i.e., not just registered — must be actively reporting completion of dispatched work). Idle-but-registered runners earn zero.
  - **Carryover**: unclaimed notional in any month rolls into a *terminal-month catchup pool*, distributed pro-rata in month 60 to runners with > 12 cumulative months of service. Prevents permanent loss of unclaimed subsidy without inflating mid-cycle.
- **Rationale**           : This shape addresses two reviewer concerns simultaneously: (a) it's a closed-form curve simulation can model; (b) the usage-rate-lock prevents the "register and earn" attack the reviewer implicitly worries about in concept-selection (line 206: "paid out flat per-runner-hour"). The reviewer's concern that "post-subsidy economics must work stand-alone" is what motivates the 60-month sunset — long enough to bootstrap, short enough that runners must build a real fee market by year 5.
- **Open questions**      : (1) Should `per_hour_rate` be CBY-denominated (current proposal) or USD-pegged via TWAP? CBY-denominated is simpler and matches the rest of §8 — USD-pegged adds oracle dependency the WP hasn't committed to. Recommend CBY-denominated with Tier-2 review every 6 months. (2) Should "serving jobs" count be threshold-gated (≥ N jobs/hour) or any-job-gated (≥ 1 job/hour)? Recommend any-job — N-job-gated will incentivise job-splitting games. (3) Does the curve flatten or sunset hard at month 60? Recommend hard sunset — anything else creates governance pressure to extend indefinitely.

### [31] Liquidity Mining 23.3M CBY emission curve          (P2, status: actionable)

- **Reviewer source**     : `Design-review.md` Gap G11; `Whitepaper-Sections-for-Reconsideration.md` §8.3 (HIGH)
- **Reviewer's "current"**: "23.3M CBY, 'front-loaded over 12 months' — no actual curve."
- **Reviewer's proposal** : "Specify closed-form expression and first 24 months of monthly CBY emissions."
- **Actual current state**:
  - WP §8.3 line 704: `Liquidity Mining / DEX | 2.33% | 23,300,000 | Front-loaded over 12 months`. No curve.
- **Verification**        : ✅ still accurate.
- **Recommendation**      : [WP §8.3 add closed-form curve]
- **Specific change**     : WP §8.3 — add subsection **"Liquidity Mining release curve"**:
  - **Window**: 24 months (extending the reviewer's 12 to 24 to soften the cliff; reviewer asked for "first 24 months" of emissions which implies their model assumes ≥ 24 months).
  - **Closed form**: exponential decay with monthly half-life 6 months. `emission(month m) = 23.3M × (1 − e^(−ln(2)/6)) × e^(−ln(2)·m/6)` for `m ∈ [0, 23]`, rebased so the 24-month integral exactly equals 23.3M.
  - First 12 months absorb ~94% of bucket; tail months 13-24 absorb ~6% — a soft taper to avoid liquidity cliff.
  - **Eligibility**: DEX LPs on whitelisted CBY-paired pools (whitelisting via Tier-1 governance proposal).
- **Rationale**           : Reviewer asked for a closed-form expression and a 24-month schedule — provided. The 6-month half-life front-loads as the WP intends but avoids the "100% front-loaded → instant cliff" failure mode where LPs leave the moment incentives end.
- **Open questions**      : (1) Whitelist criteria for paired pools — does it include CEX market-maker programs, or DEX-only? Recommend DEX-only at TGE, Tier-1 review at month 6. (2) Should the curve be replaced with a usage-elastic model (emissions scale with TVL)? Defer to Phase-5 sim; closed-form is sufficient for v1.

### [66] §8.3 emission curves for all buckets          (P1, status: actionable)

- **Reviewer source**     : `Whitepaper-Sections-for-Reconsideration.md` §8.3 (HIGH)
- **Reviewer's "current"**: "Buckets specified (180M validator, 80M runner, 23.3M LM, etc.); shapes ('front-loaded') without actual curves."
- **Reviewer's proposal** : "Add per-bucket emission curves to §8.3 — closed-form expression and first 24 months of monthly emissions; mark as Tier-0 governance-tunable but commit genesis defaults."
- **Actual current state**:
  - WP §8.3 lines 699-705: Network Distribution table lists buckets with one-line "Emission Model" descriptors ("Decreasing emission over 60 months", "Usage-based; paid per runner-hour", "Milestone-based, grant committee", "Front-loaded over 12 months", "2 drops (TGE + 6 months)"). **No** closed-form math for any bucket.
- **Verification**        : ✅ still accurate.
- **Recommendation**      : [WP §8.3 add per-bucket curve table + closed forms]
- **Specific change**     : WP §8.3 — after the Network Distribution table, add a single subsection **"§8.3.1 Emission curves (genesis defaults; Tier-0 tunable)"** with one paragraph per bucket:
  | Bucket | CBY | Window | Closed form |
  |---|---|---|---|
  | Validator Rewards | 180,000,000 | 60 months | Geometric decay matched to gross inflation schedule §8.2: monthly emission = `total_minted_that_month × 18% × (validator_bucket_share)`. Not pre-scheduled — emerges from the inflation curve. |
  | Runner Compute Incentives | 80,000,000 | 60 months | Linear notional `80M / 60 mo`, usage-rate-locked at `0.20 CBY/runner-hour`, terminal catchup (see #30 above) |
  | Developer Grants | 30,000,000 | indefinite | Milestone-based, no schedule; committee budget gated by Tier-2 disbursement proposals; CIP-12 §6 path |
  | Liquidity Mining | 23,300,000 | 24 months | Exponential decay, 6-month half-life (see #31 above) |
  | Community / Airdrops | 20,000,000 | 6 months | Two discrete events: 12M at TGE block (`m=0`), 8M at month 6 block. No smoothing in between. |
  - Append note: "All emission curves are governance-tunable at Tier 0 (parameter store) per CIP-12, *except* the closed-form shape and total bucket size which require Tier 2 (treasury/parameter, supermajority + timelock)."
- **Rationale**           : Single coordinated change closes Gap G10, G11, and the reviewer's §8.3 ask in one edit. Decoupling Validator Rewards from a fixed schedule (it tracks inflation §8.2) is intentional — otherwise the WP would have two contradictory sources of truth for validator emission. The Tier-0 / Tier-2 split (parameters tunable, shape locked) matches the protection level the reviewer asked for ("commit genesis defaults").
- **Open questions**      : (1) Should Developer Grants get a hard cap on grants/year (e.g., 6M/year for 5 years to spend the bucket)? Recommend yes, Tier-2 review. (2) Airdrop eligibility criteria (snapshot date, exclusions for team/insiders, anti-sybil) — should be defined in a separate CIP, not WP §8.3 inline. Recommend deferred to "CIP-airdrop" pre-TGE.

---

## F. Treasury 1% take from runner job payments (cross-reference)

### [2] / [41] Treasury 1% from runner job payments          (P2, status: policy-decision)

- **Reviewer source**     : `Initial-Questions.md` Q4 (Chad response); `Design-review.md` Section 1 (Stakeholder Roles, Runners row)
- **Reviewer's "current"**: WP §8.4: `Runner job payments | 89% | Runner(s)` / `10% | Burned` / `1% | Treasury`.
- **Reviewer's proposal** : "Treasury fee is worth a point of discussion. Worth considering removal — not many legitimate chains have a mechanism like that." Chad Q4 response: "Fair point and it makes the math weird, i think we're ok with that."
- **Actual current state**:
  - WP §8.4 lines 713-715 (verbatim, the three-row split as quoted above).
  - WP §13 line 797: "`runner_payout = 89%`; `runner_fee_burn = 10%`; `job_fee_to_treasury = 1%`."
  - CIP-2 doesn't hardcode the split — settlement is implemented via `SettlementConfig { runner_percent, burn_percent, treasury_percent }` stored at `GOVERNANCE_SYSTEM_ACTOR=0x09` (per CLAUDE.md "Settlement Governance (CIP-2 Fix 4)"). Updateable via opcode 40 `UpdateSettlementConfig`, gated to `0x09`.
- **Verification**        : ✅ still accurate. Treasury 1% is in WP §8.4, WP §13, and the on-chain `SettlementConfig` default. Chad's verbal acceptance has not been formalized; the spec still ships the 1%.
- **Recommendation**      : [decision-register entry] — and if accepted, [WP §8.4 edit] + [WP §13 edit] + [CIP-2 amendment to default `SettlementConfig`]
- **Specific change**     : Pending decision. Two viable paths:
  - **Path A — full removal, redirect to burn**: amend split to `90% runner / 10% burn / 0% treasury`. Aligns with "treasury is governance-disbursed, not auto-funded" framing in CIP-12 §3.1 ("[Foundation] receives funds only when a treasury disbursement proposal passes governance"). Cleanest narratively but raises one unit of dilution offset.
  - **Path B — redirect to runner**: amend split to `90% runner / 10% burn / 0% treasury` with the freed 1% going to runner. Same result mechanically as Path A from the burn perspective, but the framing differs — slight increase in runner take.
  - **Path C — keep as-is**: explicit policy choice that 1% to treasury is an acceptable usage-elastic Foundation funding mechanism, no change.
- **Rationale**           : Reviewer's framing is about legitimacy — "not many legitimate chains have a mechanism like that". Chad's response is an acceptance-in-principle but not a spec change. The SettlementConfig already lives at `0x09` and is governance-mutable, so the *technical* cost of changing it post-TGE is low — this is a pre-TGE narrative decision more than a code one. CIP-12 §3.1 framing ("Foundation receives funds only when a treasury disbursement proposal passes governance") actually *contradicts* an auto-fed 1% treasury stream, so Path A is the most internally consistent.
- **Open questions**      : (1) Does the 1% currently fund anything load-bearing (Foundation ops, grants committee bond)? If yes, removal needs an alternative funding source. Recommend audit of any code paths assuming non-zero treasury inflow before deciding. (2) If Path A, should the freed 1% become part of the `runner_fee_burn` (making it 11%) or roll into runner payout (making it 90%)? Recommend burn — strengthens the deflationary counterweight Chad himself cited as motivation in Q5/Q6. (3) Does removal require Tier-3 (system parameter affecting consensus state) or Tier-2 (treasury & disbursement)? CIP-12 §6 framing implies Tier-2; check with the governance section.

---

## G. Decision-register entries from this topic

1. **Inflation schedule**: keep WP §8.2 4-year `8/6→4/3→2` glidepath, or sync to Chad Q6 3-year `4→3→2` glidepath? **Recommended: 3-year** (matches Chad's stated thinking; cleaner story; preserves 10% governance headroom).
2. **Validator APR target**: pin a band (recommended `4–6%` inflation-adjusted) in WP §13 + §8.2 commentary, or leave fully governance-tunable with no genesis default? **Recommended: pin band**, Tier-0 tunable. Without it no validator can model build-vs-rent.
3. **Security-floor trigger**: `security_floor_staked_ratio = 33%` with `+200 bps` boost step over a 30-day persistence window — or different thresholds? **Recommended: 33% + 200 bps + 30 days**, Tier-0 tunable. Defer exact threshold to Phase-5 sim but commit the *mechanism shape* now.
4. **Runner Compute Incentives shape**: linear-with-usage-rate-lock over 60 months (recommended), front-loaded, or pure linear? **Recommended: linear with `0.20 CBY/runner-hour` rate lock and terminal catchup**.
5. **Treasury 1% removal**: confirm Chad's Q4 acceptance and amend WP §8.4 + CIP-2 default `SettlementConfig` to `90% runner / 10% burn / 0% treasury` — **OR** keep as-is? **Recommended: Path A (remove, redirect to burn)** for narrative consistency with CIP-12 §3.1.
6. **"Net inflationary" framing**: replace lingering "net deflationary at steady state" language with explicit "net slightly inflationary; real-cycle burn is counterweight, not target". Editorial WP change. **Recommended: do it now** alongside item #3 rewrite.

---

## H. New CIPs / amendments proposed (analysis-only round; no edits this cycle)

- **WP §8.2 rewrite**: replace inflation schedule with Chad's 3-year glidepath; add design-intent paragraph on net-inflation stance; specify security-floor trigger parameters inline.
- **WP §8.3 expansion**: add §8.3.1 "Emission curves (genesis defaults; Tier-0 tunable)" with closed-form expression and 24-month emission schedule per bucket; cross-reference §8.2 for validator bucket which tracks inflation directly.
- **WP §8.4 amendment** (conditional on item #2 decision): adjust runner job payment split to `90% runner / 10% burn / 0% treasury`.
- **WP §13 additions**: `validator_apr_target = 4-6%`, `security_floor_staked_ratio = 33%`, `security_floor_boost_bps = 200`, `security_floor_persistence_blocks = 2,592,000`, plus any monetary parameters frozen in §8.3.1.
- **CIP-2 settlement default amendment** (conditional on item #2 decision): change `SettlementConfig` genesis default to `runner_percent=90, burn_percent=10, treasury_percent=0`. No new opcode needed — uses existing `UpdateSettlementConfig` path.
- **Potential new CIP-34 "Emission Curves & Macroeconomic Parameters"**: if §8.3.1 grows beyond ~2 pages, extract the closed-form math, eligibility rules, and Tier-0/Tier-2 mutation paths into a dedicated CIP. WP §8.3 then becomes a 1-paragraph forward reference. Recommend defer this decision until the §8.3.1 text is drafted and length is known.
