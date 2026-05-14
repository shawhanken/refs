# 03 — Runner Marketplace, Verification, Delegation

## TL;DR

The reviewer's Phase-3 selected design (Concept B base + Lane V opt-in add-on) targets six of the seven big gaps in the live runner spec: static committee sizing, undefined reputation dynamics, lock-out aggregator selection, unspecified non-reveal classification, CBY-denominated stake floor, and zero delegator governance voice. Verified against the live CIP-2 v2 and CIP-13 v2, the reviewer's "current" reads are accurate on every item except commission bounds — CIP-13 v2 §4.4 already pins `MIN_COMMISSION_BPS = 500 (5%)` / `MAX_COMMISSION_BPS = 10000 (100%)`, so item #33 is a Tier-2 governance call (tighten the cap to 30%), not a missing spec.

Recommendations (all analysis-only this round):

- **Adopt at spec level (amend CIP-2 §5/§6/§8):** adaptive committee `M = clip(ceil(2·log₂(N_active)/HHI), 3, 9)`, VRF weight `w = s · sqrt(r)`, EMA reputation with 14-day half-life, eligibility-threshold aggregator (≥ p50, uniform random), aggregator bonus = 1.5% of gross. Each closes a real risk and replaces an undefined or known-fragile constant.
- **Flag for decision register (do not silently amend):** non-reveal 25% fractional slash (cross-listed in `01-slashing.md`), slashed-stake 50/30/20 destination (Tier-3 amendment to WP §8.4 C7), USD-pegged stake floor (oracle dependency at the consensus layer), commission cap tighten from 100% to 30% (governance call, not spec gap), 25% delegator governance weight on runner-parameter Tier-2 proposals.
- **Defer:** Lane V (TEE/ZK opt-in verifiable lane) — recommend "future CIP" once Lane R / Concept B ships and demand is measurable. The reviewer themselves staged Lane V as an opt-in add-on, not a Phase-4 default.
- **Small documentation fix:** pin the semantic-similarity embedding model in the model registry with Tier-3 change semantics (WP §7 or §9 short paragraph). Item #24 / #65 are the same risk and need one sentence to close.

Two reviewer arithmetic items needing correction before adoption: (1) the "14-day half-life = ~250k blocks at 5s slots" parenthetical is wrong — Cowboy is 1s blocks, so 14 days = 1,209,600 blocks; (2) the WP §13 "7,200 blocks ≈ 24h" math error is in scope for `01-slashing.md` / `04-validator-economics.md`, not here.

---

## Items index

| #   | Title                                                       | Priority | Touches             | Status     | Action                                                |
|-----|-------------------------------------------------------------|----------|---------------------|------------|-------------------------------------------------------|
| 7   | Runner economics across 10× CBY price range                 | P2       | CIP-2, CIP-13       | actionable | defer-to-sim + decision register (USD-peg vs CBY)     |
| 9   | Non-reveal denial-of-verification                           | P1       | CIP-2 §6, §8        | actionable | amend CIP-2 §6 (25% slash); cross-ref `01-slashing.md` |
| 10  | Oversell jobs, lose only reputation                         | P2       | CIP-2 §9            | actionable | amend CIP-2 §6 (escalating timeout penalty)           |
| 11  | Aggregator bonus magnitude unspecified                      | P1       | CIP-2 §8; WP §8.4   | actionable | amend CIP-2 §8 + WP §8.4 (1.5% of gross)              |
| 12  | Aggregator "highest reputation" locks out new runners       | P2       | CIP-2 §8            | actionable | amend CIP-2 §8 (eligibility threshold ≥ p50, uniform random) |
| 14  | Static M=5 / N=3 committee                                  | P1       | CIP-2 §5; WP §13    | actionable | amend CIP-2 §5 + WP §13 (adaptive `M = clip(2·log₂(N)/HHI, 3, 9)`) |
| 20  | Delegation concentrates capacity                            | P2       | CIP-13              | partially  | depends on #33 outcome; no separate change            |
| 22  | 3-runner sybil in 5-committee                               | P1       | CIP-2 §5            | actionable | subsumed by #14 adaptive committee                    |
| 24  | Semantic similarity embedding circularity                   | P2       | CIP-2 §9; WP §7     | actionable | WP §7 / §9 add Tier-3 pinning paragraph (also #65)    |
| 33  | Commission bounds                                           | P2       | CIP-13 §4.4         | stale      | resolved in spec; flag governance tightening for decision register |
| 47  | Delegator partial vote weight                               | P2       | CIP-13 §6.1, CIP-12 | actionable | amend CIP-13 §6.1 (25% weight on runner-param Tier-2) |
| 53  | Aggregator bonus formula                                    | P1       | CIP-2 §8; WP §8.4   | actionable | duplicate of #11 — single change resolves both        |
| 55  | Reputation decay/recovery formula                           | P1       | CIP-2 §4 / §6       | actionable | amend CIP-2 (EMA, 14-day half-life, recovery floor)   |
| 56  | Adaptive committee                                          | P1       | CIP-2 §5; WP §13    | actionable | duplicate of #14 — single change resolves both        |
| 65  | Embedding-model circularity (restated)                      | P2       | CIP-2 §9; WP §7     | actionable | duplicate of #24 — single change resolves both        |

---

## A. Committee selection & sizing

### [14] Static `M=5 / N=3` committee — vulnerable at launch          (P1, status: actionable)

- **Reviewer source**     : Design-review.md §7.2 item 2; Whitepaper-Sections-for-Reconsideration.md §9/§19 (Risk R3)
- **Reviewer's "current"**: "Default committee M=5, N=3. With small runner population (e.g., 20 active runners), probability of adversary controlling 3 slots after staking ~60% of total runner stake is non-trivial."
- **Reviewer's proposal** : Adaptive `M = clip(ceil(2 · log₂(N_active) / HHI_runner_stake), 3, 9)`; `N = ceil(2M/3)`; recompute per epoch with EMA-smoothed HHI.
- **Actual current state**:
  - WP §13 (parameters, line 789): `committee M = 5; threshold N = 3; challenge_window = 15 min; challenge_bond = 100 CBY; runner_stake_floor = 10,000 CBY; dispute_window_blocks = 75.`
  - WP §5.2 (line 577): "For HTTP domains, a **committee of M=5** is sampled; **N=3** matching reveals finalize. LLM jobs MAY use committees or single-runner."
  - CIP-2 §5 Fisher-Yates selects M from sorted candidate list (M passed in JobSpec but defaults unspecified at protocol level).
- **Verification**        : ✅ still accurate — both WP and current CIP-2 treat M/N as static parameters.
- **Recommendation**      : amend CIP-2 §5; amend WP §13 (off-chain) and WP §5.2.
- **Specific change**     : Replace fixed M/N with `M_epoch = clip(ceil(2 · log₂(N_active) / HHI_epoch), 3, 9)`, `N_epoch = ceil(2 · M_epoch / 3)`. Compute HHI from active runner stake distribution (effective stake including delegation per CIP-13 §3.2). Recompute once per epoch (3600 blocks); EMA-smooth HHI with the same 14-day half-life used for reputation to absorb single-block shocks (large runner exits).
- **Rationale**           : The reviewer's small-N math is right — with 20 active runners and stake-weighted Fisher-Yates, three colluders can hit N=3 trivially. Adaptive sizing tied to Herfindahl is the conventional response in PoS literature and stays within the existing Fisher-Yates VRF infrastructure (only the committee-size input changes). Floor at 3 preserves liveness for genuinely small populations; cap at 9 bounds settlement gas.
- **Open questions**      : (a) Should M/N be per-epoch globally, or per-job from job-time HHI snapshot? Epoch-level is cheaper and more predictable for runners; per-job is more responsive. Recommend epoch-level for v1, per-job as future refinement. (b) Should `JobSpec` retain a job-submitter override (e.g., "I want M=7 regardless")? Probably yes, capped by the epoch ceiling — this preserves the existing per-job M parameter.

### [22] 3-runner sybil in 5-committee          (P1, status: actionable — duplicate of #14)

- **Reviewer source**     : Design-review.md §6 (Actors row)
- **Reviewer's "current"**: "M=5, N=3 committee; adversary who controls 3 runners can always 'win' consensus. Vulnerable if total active runner count is small."
- **Reviewer's proposal** : "(Same as Risk R3: need adaptive committee sizing)."
- **Actual current state**: Same as #14 (WP §13 line 789).
- **Verification**        : ✅ accurate; this is the same risk as #14 framed from the actor side rather than the marketplace side.
- **Recommendation**      : no separate change — resolved by #14's adaptive committee amendment.
- **Specific change**     : (none — subsumed.)
- **Rationale**           : The reviewer's two write-ups are the same mechanism (small-N Sybil capture) viewed from two stakeholder lenses. One change closes both.

---

## B. Reputation dynamics

### [55] Reputation decay / recovery formula missing          (P1, status: actionable)

- **Reviewer source**     : Design-review.md Gap G4; Whitepaper-Sections-for-Reconsideration.md §9/§19 (Risk R13)
- **Reviewer's "current"**: "Reputation system referenced throughout §9 but never defined. Required to model runner market dynamics and VRF selection distribution; determines whether runner incentives actually work."
- **Reviewer's proposal** : EMA reputation with 14-day half-life; recovery floor on jail exit; reputation factors into VRF weight via `w = s · sqrt(r)`.
- **Actual current state**:
  - CIP-2 §4 (candidate filter step 2): "Reputation filter: `reputation ≥ 50`."
  - CIP-2 §6 (timeout re-selection): "All timed-out runners receive `reputation -= TIMEOUT_PENALTY` (default: 5) … After `SLASH_THRESHOLD` consecutive slashes, a stake slash is triggered."
  - CIP-2 §8: "Aggregator = **the selected runner with the highest reputation** (deterministic, ties broken by address order)."
  - CIP-2 §5 VRF weight: `floor(log2(s / MIN_STAKE + 1)) + 1` — stake only, no reputation factor.
  - No file defines: starting value, max value, recovery dynamics, half-life, or decay rate.
- **Verification**        : ✅ accurate — reputation is used in three different gates (filter, timeout penalty, aggregator selection) without a formal dynamics specification.
- **Recommendation**      : amend CIP-2 §4 (add a new subsection "Reputation dynamics" — currently absent).
- **Specific change**     : Define `r ∈ [0, 100]`, starting `r₀ = 50` at registration. After each settled job, update `r ← r + α · (outcome - r)` where `α = 1 - 2^(-Δt / half_life)` and `outcome ∈ {0, 100}` (clean reveal vs. slash event); for graded outcomes (timeout, schema fail) use `outcome = 25`. Half-life: 14 days at 1s blocks = **1,209,600 blocks** (not the reviewer's "~250k at 5s slots" — see TL;DR note). Recovery floor on jail exit: `r = max(r, 20)` so post-slash runners can climb back into eligibility. VRF weight becomes `w = stake_to_weight(effective_stake) · max(1, floor(sqrt(r)))` — the integer-sqrt term dampens whale-plus-perfect-reputation without zeroing out new runners with `r = r₀ = 50`.
- **Rationale**           : Three live primitives reference reputation. A formula is the minimum needed to make any of them behave predictably; without it, item #14 (adaptive M) and item #12 (eligibility-threshold aggregator) cannot be evaluated either. EMA is the standard choice and is the same family Bittensor's bond mechanism uses; 14-day half-life trades freshness against gaming (a runner cannot rebuild reputation faster than ~2 weeks of consistent good behavior).
- **Open questions**      : (a) Should `outcome` be value-weighted (large job = larger reputation move) to deter the reviewer's value-stacking attack? Probably yes, but adds complexity to settlement; recommend defer to v2. (b) Should the floor-on-jail-exit be parameterized? Recommend yes, `JAIL_EXIT_REPUTATION_FLOOR` Tier-0 tunable.

---

## C. Aggregator role

### [12] Aggregator "highest reputation" locks out new runners          (P2, status: actionable)

- **Reviewer source**     : Design-review.md §6 (Runners row)
- **Reviewer's "current"**: "Designated-aggregator selection is 'highest reputation in the committee'. This means new runners can never be aggregators, which hurts reputation bootstrapping."
- **Reviewer's proposal** : Eligibility threshold ≥ p50 reputation; uniformly random pick among eligible.
- **Actual current state**:
  - CIP-2 §8 line ~424: "Aggregator: **The selected runner with the highest reputation** (deterministic, ties broken by address order). Acts as the coordinator."
- **Verification**        : ✅ accurate verbatim.
- **Recommendation**      : amend CIP-2 §8 ("Result Submission: Commit-Reveal + Designated Aggregator").
- **Specific change**     : Replace "highest reputation" with: "Aggregator: selected uniformly at random (via the same VRF seed extended with the domain separator `'aggregator-select'`) from the subset of committee members whose reputation is at or above the network-wide median (p50). If fewer than one committee member qualifies, fall back to the highest-reputation committee member (deterministic, address-order tiebreak). The p50 reference is recomputed once per epoch from the active-runner reputation distribution."
- **Rationale**           : The current rule creates a perpetual-incumbent dynamic — once a runner is "highest reputation", they aggregate every job they're selected for, accruing the bonus and any aggregator-specific reputation gains. Eligibility-threshold + uniform-random rotation preserves the integrity property (only "trusted enough" runners aggregate) while letting newcomers rotate in once they cross p50. The VRF seed is already deterministic and consensus-fixed, so the random selection adds no new randomness assumption.
- **Open questions**      : What should the fallback rule be if zero committee members meet p50 (possible in a small/young marketplace)? The proposed fallback to "highest" preserves liveness, but flag for review.

### [11] Aggregator bonus magnitude unspecified          (P1, status: actionable)

### [53] §9 / §19 Aggregator bonus formula needed          (P1, status: actionable — duplicate of #11)

- **Reviewer source**     : Design-review.md §6 (Runners row) and Whitepaper-Sections-for-Reconsideration.md §9/§19 (Risk R11)
- **Reviewer's "current"**: "Aggregator bonus is 'a small bonus' with no numeric definition. If too small, no incentive to take the role; if too large, runners optimize for becoming aggregator rather than getting results right."
- **Reviewer's proposal** : 1.5% of gross job payment. Reviewer's formula template: `bonus = max(C_min, k × job_payment)`.
- **Actual current state**:
  - CIP-2 §8 reveal step: "Aggregator receives a small bonus reward for honest aggregation" — no formula, no number anywhere in the file.
  - WP §8.4: `runner_payout = 89%; runner_fee_burn = 10%; job_fee_to_treasury = 1%`. The aggregator bonus is not allocated from any documented bucket.
- **Verification**        : ✅ accurate — the magnitude is genuinely undefined.
- **Recommendation**      : amend CIP-2 §8 + WP §8.4.
- **Specific change**     : Aggregator bonus = `1.5% × gross_job_payment` (i.e., `max_price + tip`), paid only on successful settlement (no bonus on failed verification, slash event, or aggregator-timeout fallback). Funded from the runner share (89%): the aggregator receives their normal pro-rata committee share **plus** the 1.5% bonus, with the bonus subtracted pro-rata from the other M-1 runners' shares. Net split: `runner_share_total = 0.89 × gross`; aggregator gets `(runner_share_total / M) + 0.015 × gross`; each other runner gets `(runner_share_total / M) - (0.015 × gross / (M - 1))`.
- **Rationale**           : 1.5% of gross is enough to make the role attractive (on a $1 job that's $0.015, and aggregator workload is real: collecting reveals over HTTP, running verification logic, submitting the reveal tx) without being so large that runners would prefer aggregation over correct execution. Funding from inside the 89% runner share rather than from burn/treasury buckets keeps the WP §8.4 89/10/1 invariant intact and avoids a Tier-3 amendment to that split (cf. item #36, slashed-stake destination, which DOES require a Tier-3 amendment).
- **Open questions**      : Should the bonus be value-weighted differently for small vs. large jobs (e.g., flat floor `max($0.01 equiv, 1.5% × gross)`)? Reviewer's `max(C_min, k × job_payment)` template suggests yes. Recommend deferring this refinement and shipping the flat 1.5% first.

---

## D. Non-reveal & slashed-stake destination (also covered in `01-slashing.md` — cross-link)

### [9] Commit-without-reveal denial-of-verification          (P1, status: actionable; primary treatment in `01-slashing.md`)

- **Reviewer source**     : Design-review.md §6 (Runners row, Risk R2); Whitepaper-Sections-for-Reconsideration.md §9/§19 (Risk R2 again)
- **Reviewer's "current"**: "Whether the slashing logic treats this as dishonesty or as operational failure is implementation-defined… treating as operational failure opens denial-of-verification attack where adversary commits garbage, waits to see other commits, then refuses if majority unfavourable."
- **Reviewer's proposal** : Default-slash with single timer-based exemption window for legitimate crashes; reviewer's selected design = 25% fractional slash.
- **Actual current state**:
  - CIP-2 §8 fallback rule: "other runners may submit individual reveals after `aggregator_timeout_blocks`; Result Verifier falls back to self-aggregation" — addresses aggregator non-reveal only.
  - CIP-2 §6 covers timeout-based re-selection (`reputation -= TIMEOUT_PENALTY`) but treats commit-without-reveal identically to never-committed — both are "no reveal in window".
- **Verification**        : ✅ accurate — the classification of "committed but did not reveal" is genuinely undefined; current code treats it as operational failure (reputation penalty only).
- **Recommendation**      : amend CIP-2 §6 / §8 (cross-reference `01-slashing.md` for the primary treatment).
- **Specific change**     : Define non-reveal classification: a runner who has submitted a valid commitment but failed to reveal (or have their reveal included by the aggregator) within `reveal_deadline_blocks` of the commit deadline incurs a **25% fractional slash** of their self-bond stake plus reputation penalty, EXCEPT during a single `non_reveal_exempt_blocks` window per runner per epoch (default: one exemption per epoch). Exemption consumes the slot — second non-reveal in same epoch slashes. Cross-references the slashed-stake destination decision (item below).
- **Rationale**           : 25% is large enough to deter the front-running attack (an adversary cannot probabilistically gain more than 25% of stake by waiting to see other commitments) and small enough that a genuine crash doesn't ruin a small runner. The exemption window converts "everyone gets slashed on first crash" into "everyone gets one freebie per epoch" — necessary for new runners who haven't built operational maturity.
- **Open questions**      : Cross-reference. Full treatment of: (a) commit-reveal protocol timing parameters, (b) slashed-stake destination split, (c) interaction with `MAX_DELEGATION_SLASH_PER_EPOCH_BPS` cascade, is in `01-slashing.md`. This file owns only the marketplace-incentive framing.

> **Note**: The "slashed-stake 50% challenger / 30% burn / 20% treasury" split (reviewer's Concept B selection) requires a Tier-3 amendment to WP §8.4 line 716 (`Slashed stake | 100% | Burned`). That is a decision-register item, not a silent amendment. CIP-13 v2 §4 already references `SettlementConfig.slash_*_percent` as governance-tunable — so the routing knobs exist in the spec, but the protocol-default WP §8.4 line still says 100% burn. Listed in §J below.

---

## E. Stake floor (CBY vs USD-pegged)

### [7] Runner economics stability across 10× CBY price range          (P2, status: defer-to-sim + decision register)

- **Reviewer source**     : Design-review.md §1 (Stakeholder Roles); Phase-3 selection Concept B
- **Reviewer's "current"**: "Runner effective stake floor is `max(10k CBY, 1.5× declared_max_job_value)` with ≥10% self-bond. How do runner economics stay stable across a 10× CBY price range?"
- **Reviewer's proposal** : USD-pegged via 7-day TWAP: `effective_stake_CBY ≥ max(10k CBY USD-equiv, 1.5 × declared_max_job_value_USD) / TWAP_CBY_USD_7d`; 25%-depreciation 7-day grace period.
- **Actual current state**:
  - CIP-2 2026-04-15 amend block: `Runner 质押公式: stake >= max(10,000 CBY, 1.5 × declared_max_job_value)`.
  - WP §13 line 789: `runner_stake_floor = 10,000 CBY`.
  - WP §17.10 (Collateral, line 972): `runner_stake >= max(10,000 CBY, 1.5 × declared_max_job_value)`.
  - All three sources are CBY-denominated. No oracle reference, no USD anchor.
- **Verification**        : ✅ accurate — stake floor is purely CBY-denominated and lacks a price-stabilization mechanism.
- **Recommendation**      : **Flag for decision register; default-recommend keeping CBY-denominated for now.**
- **Specific change**     : (proposed for decision, not adopted) USD-pegged stake floor via 7-day TWAP requires: (a) a price oracle in protocol-critical state, (b) consensus determinism guarantees on the TWAP read, (c) handling for periods when the oracle is unavailable (fallback to last-good-value? halt registration?), (d) cascade logic when a 25%+ CBY drop forces every active runner to top up or unbond. Each of these is a meaningful spec exercise.
- **Rationale**           : The reviewer's concern is real — at CBY=$0.10 the floor is $1k (trivial for retail entry), at CBY=$10 it's $100k (locks out everyone but funds). But the fix is heavy: an oracle module at the consensus layer that any registration / stake-check / VRF-weight computation depends on. Default recommendation is to **keep CBY-denominated for v1**, document an explicit monitoring cadence + Tier-0 adjustment trigger in WP §17.10, and revisit once an oracle module ships (CIP-29 event hooks or a dedicated oracle CIP is a natural prerequisite). The risk of CBY-denomination is bounded by governance reaction time; the risk of a poorly-built oracle is consensus-level.
- **Open questions**      : Is there appetite for an oracle CIP in 2026? If yes, USD-peg becomes feasible. If not, recommend explicit monitoring policy in WP.

---

## F. Commission bounds (already-resolved item #33; recommendation tightens)

### [33] Runner commission bounds          (P2, status: stale — partially resolved in CIP-13 v2)

- **Reviewer source**     : Design-review.md Gap G13
- **Reviewer's "current"**: "`commission_bps` is configurable by runner; no documented bounds. Is there a cap on runner commission, or can a runner set 100%?"
- **Reviewer's proposal** : Hard cap 30%, soft floor 5% (Phase-3 selection).
- **Actual current state**:
  - CIP-13 v2 §3.3 `RunnerUpdateDelegationConfig` precondition (3): `MIN_COMMISSION_BPS <= commission_bps <= MAX_COMMISSION_BPS`.
  - CIP-13 v2 §4.4 (line ~616-617):
    `| MIN_COMMISSION_BPS | 500 (5%) | Minimum runner commission. Prevents race-to-zero that harms runner economics. |`
    `| MAX_COMMISSION_BPS | 10000 (100%) | Maximum runner commission. 100% = runner keeps everything, delegation is purely for stake weight. |`
- **Verification**        : ❌ **stale** — bounds DO exist now (CIP-13 v1 created 2026-04-12, post-dates the reviewer's design review). The "uncapped" framing is no longer accurate.
- **Recommendation**      : **No spec change.** Flag the reviewer's tighter cap (30%) for the decision register as a Tier-2 governance call.
- **Specific change**     : (governance call, not spec) `MAX_COMMISSION_BPS` could be adjusted from 10000 (100%) to 3000 (30%) via Tier-2 governance once CIP-12 is live. The `commission_bps` field, precondition, and update flow remain unchanged. The reviewer's "race-to-bottom destabilizes long-run runner economics" argument is plausible but has not been demonstrated on Cowboy specifically; tightening can be done in either direction once data exists.
- **Rationale**           : The spec already has the bounds — what the reviewer wants is for the bounds to be tighter. That's a parameter tuning question for governance, not a CIP-13 amendment. The 5% floor is already correct. The 100% cap is permissive; 30% is conservative; the right number depends on observed delegator-runner negotiation dynamics that don't exist yet.
- **Open questions**      : Should the cap be coupled to delegation amount (higher delegation = lower allowed commission, on antitrust grounds)? Probably not for v1.

### [20] Delegation concentrates capacity / weakens market competition          (P2, status: partially addressed)

- **Reviewer source**     : Design-review.md §6 (Runner Delegators row)
- **Reviewer's "current"**: "Runners can compete by lowering commission into a race to the bottom."
- **Reviewer's proposal** : Couple to #33 — commission bounds prevent the race.
- **Actual current state**: CIP-13 v2 §4.4: `MIN_COMMISSION_BPS = 500` (5% floor).
- **Verification**        : ⚠ partially — the floor exists; whether 5% is sufficient is an empirical question.
- **Recommendation**      : no separate change — resolved by #33's commission-bounds discussion.
- **Specific change**     : (none — subsumed.)
- **Rationale**           : This and #33 are the same mechanism viewed from delegator vs. runner sides. Existing 5% floor is the protocol's answer; "is 5% enough" is a sim/post-launch tuning question.
- **Open questions**      : Same as #33.

---

## G. Delegator governance voice

### [47] Delegator partial vote weight on runner-parameter proposals          (P2, status: actionable)

- **Reviewer source**     : Design-Review-Summary-Cowboy-Input.md §2.6; Whitepaper-Sections-for-Reconsideration.md §11.1-§11.2/§25 (item #62)
- **Reviewer's "current"**: "Delegators have zero governance weight in v1 per CIP-13. Delegators bear slashing risk but cannot influence runner-relevant parameters — future legitimacy problem."
- **Reviewer's proposal** : 25% pro-rata weight on Tier-2 proposals tagged `runner-marketplace-parameter`; zero weight on consensus-layer or other proposals.
- **Actual current state**:
  - CIP-13 v2 §6.1 (verbatim line ~639-644): "For v1 of this CIP, runner-delegated CBY has **zero governance vote weight**. The CBY is locked and economically productive, but it carries no political voice while it is attributed to a runner."
  - CIP-13 v2 §9.6 (future work): "A future CIP may extend CIP-12 to grant vote weight to runner-delegated stake (voted directly by the delegator, not inherited by the runner)."
- **Verification**        : ✅ accurate verbatim.
- **Recommendation**      : amend CIP-13 §6.1 (this is the "future CIP" §9.6 anticipated — propose as CIP-13 §6.1 v3 or as a new CIP-13.1 follow-up).
- **Specific change**     : CIP-12 governance-parameter proposals carry a category tag. For proposals tagged `runner-marketplace-parameter` (specifically: items in CIP-2 §13 / WP §17.10 / WP §7-§9 runner section, and CIP-13 §4 parameter blocks), runner-delegated CBY contributes vote weight at 25% of its pro-rata stake share. Weight is voted **directly by the delegator** (not inherited by the runner). On all other proposal categories, runner-delegated CBY remains at 0% weight (status quo). Eligibility snapshot: same block as the proposal's `voting_start_height`, same as validator-staked weight per CIP-12.
- **Rationale**           : The reviewer's legitimacy argument is sound: delegators carry slashing exposure under CIP-13 §3.6 (capped at 5% per epoch, but real), so they have skin in the game on exactly the parameters this scopes to. 25% is a defensible compromise — enough to be meaningful, not enough to overwhelm validator-staked voice. Scope-limiting to `runner-marketplace-parameter` keeps consensus-layer governance unchanged. Direct-by-delegator rather than runner-inherited prevents commission-style capture (a runner can't use delegator stake to vote for self-favorable parameters against delegator preferences).
- **Open questions**      : (a) How is "runner-marketplace-parameter" tagged on a proposal? Need a CIP-12 amendment to introduce proposal categories, or a heuristic (proposal touches keys under `0x09:params:runner:*`?). (b) Does this require a CIP-12 amendment to introduce category-conditional vote weights? Yes — flag as cross-CIP coordination.

---

## H. Lane V (opt-in verifiable lane) — future option

Not a numbered review item per se, but the second half of the Phase-3 selection (Concept C → Lane V opt-in add-on to Concept B). The reviewer staged Lane V as opt-in, not default, so this is correctly framed as a future-CIP candidate.

**Concept**: A parallel verification lane with `M = 1` (single runner), cryptographic verification via TEE (`0x05`) or future ZK proof, no output-incorrectness slash (only attestation-forgery + availability-breach slashing). Per-lane reputation (`r_V` separate from `r_R`). Lower stake floor: `max(5k CBY-USD-equiv, 1.0 × max_job_value_USD)`. Cross-lane bootstrap one-way `r_R → r_V_init = 0.2 · r_R`.

**Recommendation**: Defer to a future CIP (suggested numbering: CIP-33 or similar, post CIP-29). Reasons:

- **Substrate readiness**: Lane V depends on mature TEE attestation infrastructure (CIP-23) being shipped and on a Cowboy ZK-proof story (currently not even in the CIP pipeline). Both are non-trivial spec exercises.
- **Demand uncertainty**: The reviewer's Concept C selection is explicitly hedged: "60/40 subsidy split is Tier-3 commitment hard to reverse; TEE supply concentration risk (single vendor root-key compromise collapses Lane V)." Shipping at TGE would commit to the architecture before any data on actual demand exists.
- **Concept B already addresses the headline risks**: adaptive committee, EMA reputation, fractional non-reveal, USD-peg, delegator voice. The marginal integrity gain from Lane V over a well-tuned Lane R is bounded.
- **Reviewer agrees**: From `/tmp/concept-selection_findings.md`: "Augmented with: Concept C's Lane V (verifiable/cryptographic) introduced as opt-in pathway, not default."

**Open questions**: Should the CIP-2 spec reserve a `LaneId` field in `JobSpec` now to avoid a breaking change later? Probably yes (one byte, optional, default `Lane::Standard`). That's a small forward-compat amendment, not a Lane V implementation.

---

## I. Verification modes (semantic similarity / embedding circularity)

### [24] Semantic similarity verification has embedding-model circularity          (P2, status: actionable)

### [65] §9.2 Semantic similarity embedding circularity (restated)          (P2, status: actionable — duplicate of #24)

- **Reviewer source**     : Design-review.md §10.2 (Risk R10); Whitepaper-Sections-for-Reconsideration.md §9.2
- **Reviewer's "current"**: "`semantic_similarity` mode exists but embedding model selection is unspecified. If embedding model used for similarity is itself decided by governance, a runner could collude with embedding choice."
- **Reviewer's proposal** : "Embedding model must be pinned in model registry under same governance-flag semantics as inference models; any change is Tier-3+ because it changes consensus-relevant verification."
- **Actual current state**:
  - CIP-2 §9 (Verification Modes table): "**SemanticSimilarity** | N ≥ 3 | Cosine similarity clustering; largest cluster meeting threshold wins."
  - No file specifies which embedding model is used, who chooses it, or how changes are governed.
  - WP §7 §9.2 (LLM Result Verification table line ~296): "`semantic_similarity` | N | Cosine similarity ≥ threshold among reveals | Cluster outliers | Open Q&A, summarisation". Same gap: no model spec.
- **Verification**        : ✅ accurate — embedding model is unspecified.
- **Recommendation**      : amend WP §7 (or CIP-2 §9) — short paragraph.
- **Specific change**     : Add to CIP-2 §9 (`VerificationMode` table): "**SemanticSimilarity** requires runners to use the embedding model pinned in the on-chain model registry at the job's `submission_block`. The model registry entry under `system:executor_registry:embedding_default` at `GOVERNANCE_SYSTEM_ACTOR=0x09` is consensus-relevant: changes require a Tier-3 governance proposal because the embedding model determines what counts as 'similar' for verification, and a change can retroactively invalidate prior verification logic." Mirror the language in WP §7 / §9.2.
- **Rationale**           : The reviewer's circularity argument is real but the fix is small — a single paragraph plus a model-registry key. The pinning pattern already exists for `DNS_VERIFIER_EXECUTOR_HASH` (CIP-2 v2 §3 "JobType::Custom as the extension pattern"); applying it to the embedding model is consistent with the established governance pattern. Tier-3 (vs. Tier-2) is justified because the embedding model is consensus-relevant for any job using `SemanticSimilarity` — a Tier-2 change could in principle re-litigate past verifications.
- **Open questions**      : (a) Should there be a transition period when the pinned embedding model changes (e.g., "old model accepted for 1000 blocks after change")? Probably yes. (b) Should `JobSpec` allow per-job embedding-model override? Probably no — defeats the consensus property.

---

## J. Decision-register entries from this topic

The following are NOT silent amendments — each is flagged for explicit decision before the next CIP/WP revision round.

1. **Adopt adaptive committee** `M = clip(ceil(2 · log₂(N_active) / HHI), 3, 9)` vs. retain static `M=5 / N=3`?
   - Touches: CIP-2 §5, WP §13, WP §5.2.
   - Sim/data needed: capture probability at small N for static vs. adaptive at various HHI levels.

2. **Define EMA reputation formula** with 14-day half-life (1,209,600 blocks at 1s), starting `r₀ = 50`, recovery floor on jail exit `r = max(r, 20)`, VRF weight = `s · sqrt(r)`?
   - Touches: CIP-2 §4 (new "Reputation dynamics" subsection), CIP-2 §5 (VRF weight formula update), WP §7 / §9.
   - Sim/data needed: model whether 14-day half-life games correctly (Bittensor's calibration suggests yes, but Cowboy job mix is different).

3. **Tighten commission cap** from 100% (current `MAX_COMMISSION_BPS = 10000`) to 30% (`MAX_COMMISSION_BPS = 3000`)?
   - Touches: CIP-13 §4.4 (a single parameter change, Tier-2 governance call once CIP-12 is live).
   - Recommendation: defer until empirical race-to-bottom evidence exists.

4. **Pin USD-pegged runner stake floor** (oracle dependency at consensus layer) vs. keep CBY-denominated with monitoring + Tier-0 trigger?
   - Touches: CIP-2 §5, WP §13, WP §17.10; adds oracle dependency to consensus-critical path.
   - Recommendation: **keep CBY for v1**, document monitoring policy. Revisit when an oracle module ships.

5. **Grant delegators 25% governance weight** on Tier-2 proposals tagged `runner-marketplace-parameter`?
   - Touches: CIP-13 §6.1 amendment + new CIP-12 amendment for proposal-category-conditional vote weights.
   - Recommendation: adopt; argument is sound; scope is well-bounded.

6. **Open Lane V** (TEE/ZK opt-in verifiable lane) at TGE vs. defer to future CIP?
   - Touches: new CIP (suggested CIP-33), heavy spec surface (per-lane reputation, lane router, lane-specific stake floor, cross-lane bootstrap).
   - Recommendation: **defer**. Optionally reserve a `LaneId` field in `JobSpec` for forward compat.

7. **Aggregator bonus = 1.5% of gross, funded from runner share**?
   - Touches: CIP-2 §8 (formula), WP §8.4 (clarify 89% includes aggregator bonus, so no change to 89/10/1 split).
   - Recommendation: adopt as Tier-2 governance-tunable default.

8. **Aggregator selection rotates uniformly among p50-or-above committee members** (vs. status quo "highest")?
   - Touches: CIP-2 §8.
   - Recommendation: adopt; closes new-runner bootstrap problem at no integrity cost.

9. **Non-reveal = 25% fractional slash with one per-epoch exemption** (vs. status quo operational-failure-only)?
   - Touches: CIP-2 §6, §8. Primary treatment in `01-slashing.md` — flagged here for runner-marketplace-side cross-reference.
   - Recommendation: adopt with exemption window; argument is in the slashing analysis.

10. **Slashed-stake destination 50% challenger / 30% burn / 20% treasury** (vs. current 100% burn per WP §8.4 C7)?
    - Touches: WP §8.4 line 716 (Tier-3 amendment to a C7 hard commitment), CIP-3 SettlementConfig defaults.
    - Recommendation: full treatment in `01-slashing.md`. **Significant** — this is a Tier-3 amendment, not a parameter tweak.

11. **Pin embedding model for SemanticSimilarity** at `system:executor_registry:embedding_default` under Tier-3 change semantics?
    - Touches: CIP-2 §9, WP §7.
    - Recommendation: adopt; small change, real risk closure.

---

## K. New CIPs / amendments proposed

- **CIP-2 — substantial amendment** (multiple sections, single amendment doc):
  - §4 add "Reputation dynamics" subsection (item #55).
  - §5 amend VRF weight to include `sqrt(r)` factor (item #55).
  - §5 amend committee sizing to adaptive `M = clip(...)` (items #14, #22, #56).
  - §6 amend non-reveal classification (item #9; cross-link `01-slashing.md`).
  - §6 add escalating timeout penalty for capacity oversell (item #10 — escalate from flat `-5` to value-weighted penalty).
  - §8 amend aggregator selection (eligibility threshold ≥ p50, uniform random — item #12).
  - §8 amend aggregator bonus (1.5% of gross — items #11, #53).
  - §9 amend SemanticSimilarity to pin embedding model (items #24, #65).

- **CIP-13 — targeted amendment**:
  - §6.1 grant delegators 25% governance weight on runner-parameter Tier-2 proposals (items #47, #62). Coordinate with CIP-12 amendment for proposal categories.
  - §4.4 commission cap is a governance-tunable decision, not a spec change (item #33).

- **WP §7 / §8.4 / §13 — parameter changes + verification-mode pinning**:
  - §7 / §9.2 add embedding-model pinning paragraph (items #24, #65).
  - §8.4 clarify aggregator-bonus accounting within the 89% runner share (items #11, #53). The slashed-stake destination amendment (50/30/20) is a separate Tier-3 decision-register item.
  - §13 update committee parameters from static to adaptive (items #14, #56) and add reputation parameter block.
  - §17.10 monitor policy for CBY-denominated stake floor (item #7).

- **(optional) New CIP-33 for Lane V architecture**: Deferred. Recommend reserving the spec slot but not authoring at TGE.
