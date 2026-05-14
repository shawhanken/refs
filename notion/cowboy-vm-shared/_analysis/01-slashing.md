# 01 — Slashing (Validator + Runner)

> Differential analysis: external reviewer (Vending Machine, April–May 2026) vs. live Cowboy CIPs & whitepaper. Read-only round; no CIP/WP edits performed here.
>
> Authoritative sources cross-checked:
> - `/refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md`
> - `/refs/cips/cip-2-offchain-compute.md` (v2; carries 2026-04-15 amendment block)
> - `/refs/cips/cip-12-governance.md`
> - `/refs/cips/cip-13-runner-delegation.md` (v2)
> - Reviewer originals: `Slashing---System-Architecture-Objectives.md`, `Slashing---Concept-Generation-Selection.md`, `Design-review.md`, `Whitepaper-Sections-for-Reconsideration.md`

## TL;DR

- **Validator BFT slashing is the single largest delta.** WP §11.3 ships flat 1% for double-signing and proposer-equivocation, no enumeration of Simplex's four evidence types, no correlation handling, and `minimum_validator_stake = governance-tunable` with no number. Reviewer proposes a full replacement: quadratic Polkadot curve `(c·x/n)²` with `c=3`, 1% floor, `X_safety=10` bug-correlation cap that auto-opens Tier-4 `ReviewSlash`, cryptographic `evidence_invalidity_proof` reversal, 95/5 burn-to-submitter distribution, and hysteresis stake bands `S_in=0.50%` / `S_low=0.40%` / `S_out=0.33%` / `S_max=5.0%` of staked CBY. → **new CIP-30** + **new CIP-32** recommended; WP §11.3 / §13 edits gated on CIPs landing.
- **Runner slashing has one critical correctness gap and one critical missing formula.** CIP-2 §6 leaves commit-without-reveal as an escalating reputation-then-slash path (`TIMEOUT_PENALTY` → `SLASH_THRESHOLD`), which the reviewer correctly identifies as a denial-of-verification attack vector. CIP-2 also never defines the reputation decay/recovery formula (no EMA, no half-life, no recoverable floor). Both are amendments to CIP-2, not new CIPs.
- **The largest open policy question is WP §8.4 "Slashed stake | 100% | Burned" (commitment C7).** Reviewer's 50/30/20 challenger/burn/treasury split for runner slashing requires a Tier-3 whitepaper amendment. Flag as decision-register item; do not silently propose. Validator-slash 95/5 split is structurally cleaner because the "challenger" is a cryptographically verifiable evidence submitter, but it still touches the same C7 paragraph.
- **Drop reviewer items #40 and #63.** Both cite an "`unbonding_blocks = 7,200 ≠ 24h`" arithmetic error against a string that does not appear in the current WP. WP §13 (parameters) says `unbonding_period = 7 days`; CIP-13 §3.3 uses `UNBONDING_BLOCKS` symbolically without pinning it to 7,200. There is no math error to fix.

## Items index

| # | Title | Priority | Touches | Status | Action |
|---|-------|----------|---------|--------|--------|
| 5 | Runner misbehaviour taxonomy & slashing calibration | P1 | CIP-2 §6 / new CIP-30 (validator side) | actionable | amend CIP-2 + new CIP-30 |
| 8 | Validator 1% slash too conservative | P1 | WP §11.3 / new CIP-30 | actionable | new CIP-30 (replace flat 1%) |
| 9 | Commit-without-reveal denial-of-verification | P1 | CIP-2 §6, §8 | actionable | amend CIP-2 §6 |
| 19 | Slashing-to-attack-value ratio not modelled | P1 | WP §11.3, CIP-2, simulation | defer-to-sim | Phase-5 sim; new CIP-30 records framework |
| 36 | Slashed stake: 100% burn vs. challenger/bounty | P2 | WP §8.4 (C7) | actionable (decision-register) | Foundation pre-clear; WP §8.4 edit + CIP-30 distribution clause |
| 40 | Unbonding period arithmetic error (7,200 ≠ 24h) | — | n/a | dropped | drop — claim references string not in current WP |
| 50 | §11.3 1% slash assumptions need articulation | P1 | WP §11.3 / new CIP-30 | actionable | superseded by new CIP-30 |
| 54 | §9 / §19 non-reveal classification | P1 | CIP-2 §6, §8 | actionable | amend CIP-2 §6 (default-slash + crash exemption) |
| 63 | §13 / §27 unbonding-blocks math error | — | n/a | dropped | drop — same root cause as #40 |
| — | Concept B parameter pack (curve, bands, evidence types, 95/5) | P1 | new CIP-30 / new CIP-32 | actionable | new CIP-30 + CIP-32 |

## A. Validator BFT slashing

### [8] Validator 1% slash too conservative          (P1, status: actionable)

- **Reviewer source**     : `Design-review.md` Section 6 (Validators row); `Whitepaper-Sections-for-Reconsideration.md` CRITICAL §11.3 (item [50]); `Slashing---System-Architecture-Objectives.md` §2.1 / §8
- **Reviewer's "current"**: "At 1%, an adversarial validator weighing expected profit of attack against cost may find the cost too low… Cowboy's flat 1% sits between regimes — neither bootstrap-style 'no burn' nor SOTA value-at-risk-calibrated."
- **Reviewer's proposal** : Replace flat 1% with Polkadot quadratic curve `p_self(x, n) = clip(p_floor, (c·x/n)², 1)`, defaults `c=3`, `p_floor=1%`, `X_safety=10` (≈10% of n≈100 validator set). Curve coefficient is Tier-0 tunable; floor preserves worst-case-actor deterrent.
- **Actual current state**:
  - WP §11.3 (lines 367–378): "Cowboy uses a conservative slashing model — most offenses result in jailing (temporary removal) rather than stake destruction… | Double signing | Jail + slash 1% of stake | | Proposer equivocation | Jail + slash 1% of stake | | Extended downtime (>50% of votes over 1000 blocks) | Jail (no slash) | | Invalid block proposal | Jail (no slash) |"
  - WP §13 (line 781): "`double_sign_slash` = 1%; `consensus_protocol` = Simplex BFT."
- **Verification**        : ✅ still accurate. Reviewer's "current" matches the live WP verbatim.
- **Recommendation**      : **new CIP-30** ("Validator BFT Slashing Curve & Evidence Model"); WP §11.3 edit follows once CIP-30 lands.
- **Specific change**     : Replace the §11.3 four-row table with the Simplex-aligned four-row table:
  - Notarization equivocation → `p_self(x, n)` + permanent tombstone
  - Finality-dummy equivocation → `p_self(x, n)` + permanent tombstone
  - Conflicting finalize → `p_self(x, n)` + permanent tombstone
  - Proposer equivocation → `p_self(x, n) / 2` + permanent tombstone
  - Invalid block proposal → jail only (24h, exponential repeat); no principal slash
  - Extended downtime → jail only; no principal slash
  Defaults: `c=3`, `p_floor=1%`, `X_safety=10`, settlement window = 1 epoch (3,600 blocks). Distribution 95% burn / 5% to evidence-submitter.
- **Rationale**           : The Polkadot shape is the only mainnet-tested curve that structurally distinguishes honest fault from cartel — the symmetry Cowboy explicitly tags as a tension in `Slashing---System-Architecture-Objectives.md` §8. Flat 1% punishes a single misconfigured validator identically to a 5-validator cartel; the curve at `x=1` yields the floor (1%) and at `x=5` yields 2.25%, at `x=10` yields 9%. The 1% floor is preserved precisely to keep the worst-case-actor deterrent that pure `(c·x/n)²` loses at small `x`. Reviewer notes (Polkadot empirical study) that the curve has never fired above 9% in production — every correlated event was bugs, not attacks — hence the bug-correlation cap below.
- **Open questions**      : Phase-5 sim should sweep `c ∈ {3,4,5,6}` against Cowboy-specific validator composition; whether `c=3` should ramp post-TGE. Validator-side EV calculation under state-dependent (within-window) correlation multiplier needs modeling.

### [19] Slashing-to-attack-value ratio not modelled          (P1, status: defer-to-sim)

- **Reviewer source**     : `Design-review.md` Section 1 (initial Q4); `Slashing---System-Architecture-Objectives.md` §3 (Value-density formula)
- **Reviewer's "current"**: "Slashing exists at 1% for validators." (Implied: 1% × `S_low` is not compared against `V_extractable`.)
- **Reviewer's proposal** : Adopt the `V_extractable = V_per_proposer_slot × P_settle_before_revert` formulation; calibrate slash so `S × p_self > V_extractable × P_attack_succeeds`. Reviewer's empirical baseline (TGE+30d, derived from Berachain Feb 2025 / Sei Aug 2023): `V_extractable` $6k–$165k per offence; `Slash at S_low × 1%` ≈ $240–$1,200 — "symbolic at TGE; jail + permanent tombstone is the actual deterrent" (peer-L1 standard at launch).
- **Actual current state**:
  - WP §11.3: see [8] above. No explicit value-density model.
  - WP §13: `minimum_validator_stake` = governance-tunable (no number).
- **Verification**        : ⚠ partially. The model and inputs are not in the WP, but the reviewer's own conclusion — "1% slash is symbolic at TGE; jail + tombstone are the deterrent" — is consistent with the WP's framing of "conservative slashing model — most offenses result in jailing."
- **Recommendation**      : **defer to sim** (Phase-5). Record the framework in CIP-30 as a rationale section but do not encode `V_extractable` numerically at TGE.
- **Specific change**     : CIP-30 rationale subsection states the inequality and points to Phase-5 sim outputs as the basis for any future ramp on `c` or `p_floor`. No WP §11.3 numeric change beyond what [8] already proposes.
- **Rationale**           : The reviewer's own conclusion is that flat slash magnitude at TGE is symbolic; the actual deterrent at launch is jail + permanent tombstone. Adopting Concept B (curve + bug-cap + tombstone) captures the qualitative improvement without committing to a value-at-risk oracle (which is Concept C, deferred). Per `Slashing---Concept-Generation-Selection.md` Phase-3 rationale: "Concept C's VAR feed requires mature bridge inventory, oracle TVL, runner-escrow accounting, all nascent at TGE; Concept B is independent of these."
- **Open questions**      : When (if ever) to layer Concept C's `f(R)` multiplier on top of Concept B; what trigger condition (e.g., `total_value_at_risk > 5× bonded_stake`).

### [Concept B / OQ-S8] Bug-correlation safety cap & cryptographic reversal          (P1, status: actionable)

- **Reviewer source**     : `Slashing---System-Architecture-Objectives.md` §10 (final objectives, two last rows); `Slashing---Concept-Generation-Selection.md` §2.2 Concept B
- **Reviewer's "current"**: WP has no correlation handling; reversal is implicit governance discretion ("every slash gets bailed out" failure mode).
- **Reviewer's proposal** : At `x ≥ X_safety = 10`, automatically open a Tier-4 `ReviewSlash` proposal *before* applying the upper-tail slash. Pre-application gate. Post-application appeal is via `evidence_invalidity_proof` payload (Tier-4 also required), no discretionary bailout. Two outcomes: Affirm (apply full correlation slash) / Reverse-as-bug (restore principal + accrued rewards). Delegator compensation logic on reverse.
- **Actual current state**:
  - WP §11.3: no mention of correlation, no mention of reversal.
  - CIP-12 §5.1: Tier 4 = "Constitutional / meta… modify Security Council membership, change tier parameters…"
  - CIP-12 §3.2: Security Council's circuit-break power is the closest live mechanism but is time-limited (7 days, auto-reverts) and explicitly forbidden on `0x09`.
- **Verification**        : ➖ not addressed. No live `ReviewSlash` payload type or `evidence_invalidity_proof` machinery exists.
- **Recommendation**      : **new CIP-32** ("Slashing Reversal Flow"). Defines `ReviewSlash` proposal payload, auto-proposal flow at `x ≥ X_safety`, `evidence_invalidity_proof` payload format, voting outcomes (Affirm / Reverse / Partial), 21-day review window, delegator compensation logic. CIP-30 references CIP-32 for the upper-tail gate.
- **Specific change**     : CIP-32 specifies:
  - `Payload::ReviewSlash { evidence_id, x_observed, slashed_set, proposed_action: Affirm | Reverse | Partial(bps) }` opened automatically by `0x09` when correlation window closes with `x ≥ X_safety`.
  - `Payload::EvidenceInvalidityAppeal { evidence_id, evidence_invalidity_proof: bytes }` for post-application reversal. Proof must demonstrate cryptographic invalidity of the original signature pair (e.g., wrong domain separator, malformed BLS aggregate). Discretionary "we vote yes because it was a bug" is forbidden — auto-review (above) is the only pre-application bug path.
  - Reverse-as-bug outcome credits the slashed principal back to the validator and to any slashable delegator tranches (cf. CIP-13 §3.6 cascade), plus accrued rewards over the offline period.
- **Rationale**           : Polkadot's empirical study (cited in `Slashing---System-Architecture-Objectives.md` §2.3) shows every documented correlated event was bugs, not cartels; governance reversed effectively all non-trivial cases discretionarily. That outcome — "every slash gets bailed out" — is the failure mode to avoid. Splitting into (a) pre-application auto-review gated on `X_safety` and (b) post-application cryptographic-only appeal preserves recoverability for bugs without making cartel slashes negotiable.
- **Open questions**      : `X_safety = 10` is heuristic (≈10% of n=100); Phase-5 sim should calibrate against bug-event frequency distribution. Validator griefing via intentional co-equivocation to force governance attention — is `X_safety` sufficient deterrent? Review-window length (~21 days) means tentative slashes hold validators offline a long time; whether to allow conditional re-activation pre-affirmation.

### [Validator stake floor / hysteresis bands]          (P1, status: actionable)

- **Reviewer source**     : `Slashing---System-Architecture-Objectives.md` §3.3 ("Minimum validator stake"); Design-review.md G1 (item [25])
- **Reviewer's "current"**: "Whitepaper §11.1 and §13 leaves `minimum_validator_stake` as 'governance-tunable' with no number."
- **Reviewer's proposal** : Sui SIP-39-style relative floor with hysteresis. `S_in = 0.50%`, `S_low = 0.40%`, `S_out = 0.33%`, `S_max = 5.0%` (per-validator cap) — all of total staked CBY. Rationale: token-price-independent, auto-adjusts with network growth, ~200 / 250 / 300 candidate ceiling. `S_max / S_low = 12.5×` headroom, enforces NC ≥ 7.
- **Actual current state**:
  - WP §11 (line 357, validator-set section): "Requirements: stake ≥ `minimum_validator_stake` (governance‑tunable)"
  - WP §13 (line 781): "`minimum_validator_stake` = governance-tunable"
- **Verification**        : ✅ still accurate.
- **Recommendation**      : Encode the four-band table in **new CIP-30** §"Validator Stake Bands"; WP §13 receives a follow-up edit to replace the placeholder with `S_in=0.50%, S_low=0.40%, S_out=0.33%, S_max=5.0%` once CIP-30 ratifies.
- **Specific change**     : CIP-30 normative section:
  > **Stake bands (denominated as fraction of total staked CBY):**
  > | Band | Value | Purpose |
  > | --- | --- | --- |
  > | `S_in` (entry) | 0.50% | New validator entry threshold |
  > | `S_low` (maintenance) | 0.40% | Active-set low watermark |
  > | `S_out` (eviction) | 0.33% | Eviction trigger |
  > | `S_max` (per-validator cap) | 5.0% | Concentration cap, enforces NC ≥ 7 |
  >
  > All bands are Tier-0 tunable. Hysteresis (`S_in > S_low > S_out`) prevents flapping under price volatility. Per-validator cap addresses coalition concentration independently from the correlation-curve mechanism.
- **Rationale**           : Sui SIP-39's structural advantage — fraction-of-staked-supply, auto-adjusting — is the only modern industry reference that ties min stake to network state rather than to an arbitrary token amount. Tighter bands than Sui's 0.03% are warranted because Cowboy targets n≈100, not n≈thousands. The cap is the more important number than the floor because, per `Slashing---System-Architecture-Objectives.md` §3.3.2, coalition-concentration risk is what motivates NC ≥ 7.
- **Open questions**      : Whether to additionally cap by absolute CBY amount as a circuit-breaker against pathological low-stake states (e.g., if total staked drops to 1% of supply); peer chains generally do not.

## B. Runner slashing (non-reveal, dishonesty, slashed-stake destination)

### [9] / [54] Runner commit-without-reveal denial-of-verification          (P1, status: actionable)

- **Reviewer source**     : `Design-review.md` Section 6 (Runners row, Risk R2); `Whitepaper-Sections-for-Reconsideration.md` CRITICAL §9/§19 (item [54])
- **Reviewer's "current"**: "If runner commits hash(result) and then refuses to reveal, treating as operational failure opens denial-of-verification attack where adversary commits garbage, waits to see other commits, then refuses if majority unfavourable. Treating as dishonesty means runner legitimately crashes is slashed for operational failure."
- **Reviewer's proposal** : Classify commit-without-reveal as **proven dishonesty by default** (immediate slash), with a single timer-based exemption window for legitimate crashes.
- **Actual current state**:
  - CIP-2 §6 (lines 214–224): "If no commitment is received within `timeout_blocks`: All timed-out runners receive `reputation -= TIMEOUT_PENALTY` (default: 5)… After `MAX_RETRIES` (default: 3) consecutive failures, the job transitions to `Failed` and `reputation -= SLASH_THRESHOLD` for persistent non-responders. After `SLASH_THRESHOLD` consecutive slashes, a stake slash is triggered."
  - CIP-2 §8 (line 514): "Aggregator Collusion: The Aggregator sees all results before submitting to chain. Mitigations: (1) other runners' commitments are locked before Aggregator submits; (2) other runners can independently reveal if Aggregator is unresponsive; (3) Aggregator's extra reward is forfeit if the submitted VerifiedResult is later challenged."
  - CIP-2 v2 (Part I §6 / §8): no explicit normative rule for the *non-aggregator* runner who commits-without-revealing. WP §9 Job Lifecycle line 260: "Proven dishonesty triggers slashing; operational failures result in reputation penalties only" — does not classify commit-without-reveal.
- **Verification**        : ⚠ partially. The text the reviewer paraphrases ("Whether the slashing logic treats this as dishonesty or as operational failure is implementation-defined") is not literally in CIP-2, but the gap is real — §6 covers the *no-commitment* case (operational, reputation-only escalation) and §8 covers aggregator non-reveal (forfeits aggregator bonus), but neither addresses a runner who commits and then never reveals.
- **Recommendation**      : **amend CIP-2 §6 and §8** in the same revision (likely v2 amendment block addition).
- **Specific change**     : Add to CIP-2 §8 ("Commit-Reveal + Designated Aggregator"):
  > **§8.5 Non-reveal classification (normative).**
  >
  > If a runner has submitted a valid `commit(runner_addr, job_id, hash(result_bytes || runner_sig))` on-chain and fails to submit either (a) its `result_bytes` to the Aggregator off-chain before `commit_deadline_blocks + reveal_window_blocks`, or (b) an independent on-chain reveal after `aggregator_timeout_blocks` elapses without an Aggregator submission, then **non-reveal is treated as proven dishonesty**: the runner is slashed at the proven-dishonesty rate set by `SettlementConfig` (currently 100% of the runner's job-allocated stake, routed to burn per WP §8.4 C7), and the runner's `reputation` is reset to 0.
  >
  > **Single exemption — crash window.** If the runner submits a signed `CrashAttestation { job_id, runner_addr, crash_height ≤ commit_height + crash_exemption_blocks }` within `crash_exemption_blocks` (default: 50 blocks, ≈50s) of its commit, the slash is downgraded to operational failure: `reputation -= TIMEOUT_PENALTY × 4`, no stake slash. The attestation MAY be submitted by the runner's own key or by an externally-attested liveness service (e.g., TEE Verifier `0x05` for TEE-mode runners). Only one `CrashAttestation` per job. `crash_exemption_blocks` is Tier-2 governance-tunable.
- **Rationale**           : The reviewer's diagnosis is correct: classifying commit-without-reveal as operational failure converts the commit-reveal protocol from "binding the runner to its result" to "free option on whether to reveal" — exactly the denial-of-verification vector. Classifying as proven dishonesty by default makes the commit binding. The single crash-attestation exemption preserves legitimate-crash recoverability without weakening the binding (only one attestation per job, must reference an attested crash height before reveal window opens). The economic asymmetry — slashing legitimate crashes is bad, but allowing strategic non-reveals on adversarially observed commits is worse — favors the default-slash classification.
- **Open questions**      : Whether `CrashAttestation` should require an externally-witnessed signature (TEE Verifier, validator co-sign) rather than self-attested, to prevent a strategic runner from forging crashes; whether the exemption should expire per runner per epoch (limit total exemptions, like a rate-limit on legitimate crashes).

### [27] / [55] Runner reputation decay/recovery formula missing          (P1, status: actionable)

- **Reviewer source**     : `Design-review.md` Gap G4 (item [27]); `Whitepaper-Sections-for-Reconsideration.md` CRITICAL §9/§19 (item [55])
- **Reviewer's "current"**: "Reputation system referenced throughout §9 but never defined… no decay/recovery formula or VRF-weight interaction."
- **Reviewer's proposal** : EMA-style recovery with explicit half-life (14 days suggested), recoverable floor on jail exit (`r_floor = 0.1 × network_median`).
- **Actual current state**:
  - CIP-2 §4 line 145: "Reputation filter: `reputation ≥ 50`"
  - CIP-2 §6 lines 218, 223: "`reputation -= TIMEOUT_PENALTY` (default: 5)… `reputation -= SLASH_THRESHOLD` for persistent non-responders"
  - WP §9 (line 278): "Runner‑reported usage is trusted by default, subject to reputation scoring and anomaly detection (>2× expected usage triggers automatic review)."
  - No EMA, no half-life, no recovery formula, no floor anywhere in CIP-2 v1 / v2 or WP §9.
- **Verification**        : ✅ still accurate. Reputation is a bare integer counter with monotonic-decrement-only rules; no recovery path is specified.
- **Recommendation**      : **amend CIP-2 §6 (or new §6A "Reputation Dynamics")** in the same revision as [9] / [54].
- **Specific change**     : Add CIP-2 §6A normative subsection:
  > **§6A Reputation dynamics (normative).**
  >
  > Each runner maintains a `reputation: u32` in the Runner Registry (`0x01`). On each job outcome, the score is updated:
  >
  > `reputation_{t+1} = round(α · score_t + (1 - α) · reputation_t)`
  >
  > where `α = 1 - 0.5^(1 / HALF_LIFE_BLOCKS)`, `HALF_LIFE_BLOCKS = 1_209_600` (14 days at 1s blocks), and `score_t ∈ {0, 100}` is 100 on successful settlement / 0 on operational failure or slash. Default initial reputation on first registration: 50.
  >
  > **Recoverable floor.** A runner exits jail (after `JAIL_DURATION_BLOCKS`, default 14 days = `1_209_600` blocks) with `reputation = max(round(0.1 × network_median_reputation), 50)`. Proven dishonesty (per §8.5) instead resets to 0 and the runner re-enters the candidate pool only by re-registration (new stake, fresh address).
  >
  > Both `HALF_LIFE_BLOCKS` and the jail-exit floor coefficient (`0.1`) are Tier-2 governance-tunable.
- **Rationale**           : An EMA with a 14-day half-life means a single bad job decays out of the reputation signal in ≈2 weeks of clean operation, matching the natural job throughput of a typical runner. A floor on jail exit (cf. Concept B in `Slashing---Concept-Generation-Selection.md`) is the standard pattern from PoS validator design (Cosmos, Polkadot, Aptos) — permanent reputation destruction creates "never re-enter" cliffs that discourage operators from re-registering after legitimate-but-penalised events. The 0.1 × network-median floor prevents a re-entering runner from out-competing established runners on VRF weight, but still allows recovery.
- **Open questions**      : Whether to weight EMA contributions by job *value* (Bittensor's bond-clipping pattern, to prevent runners stacking many low-value jobs to build cheap reputation then defecting on a high-value job); whether `network_median_reputation` should snapshot at jail exit or be live (live invites manipulation by adversarial re-registrations).

### [10] Runners over-accept jobs, capturing fraction as honest work          (P2, status: actionable — partially resolved by [9]/[54])

- **Reviewer source**     : `Design-review.md` Section 6 (Runners row)
- **Reviewer's "current"**: "Operational failures (timeout, empty output, schema violation) trigger reputation penalties only… a runner that accepts more jobs than it can actually serve loses only reputation, while capturing some fraction of jobs as honest work — this creates an incentive misalignment"
- **Reviewer's proposal** : (none specific; flags the asymmetry)
- **Actual current state**:
  - CIP-2 §6 (line 218): "All timed-out runners receive `reputation -= TIMEOUT_PENALTY` (default: 5)"
  - CIP-2 §4 (line 149): "Concurrency filter: `active_jobs < max_concurrent_jobs`"
- **Verification**        : ✅ still accurate. Reputation-only penalty is by design and is independent of the runner's actual concurrent load.
- **Recommendation**      : **no separate CIP** — the proposed §6A EMA dynamics (item [27]/[55]) and §8.5 commit-without-reveal classification (items [9]/[54]) jointly address most of the asymmetry. Specifically, if `TIMEOUT_PENALTY = 5` is applied as a `score_t = 0` event in the EMA, a runner that systematically over-accepts will see reputation decay rapidly enough that VRF weight (CIP-13 §3.2: `effective_stake × sqrt(reputation)`-style) drops them out of the candidate pool well before they can capture significant fraction.
- **Specific change**     : No additional change beyond [27]/[55].
- **Rationale**           : Once reputation is on an EMA with a half-life, over-acceptance is self-limiting. The remaining incentive — capture some honest work before reputation drops — exists for any reputation system and is the inherent cost of not pricing operational failure into stake. Pricing operational failure into stake would conflate crashes with attacks and discourage participation.
- **Open questions**      : Whether `max_concurrent_jobs` should be derived from `effective_stake` (deeper-pocketed runners can handle more jobs) rather than runner-declared.

### [36] Slashed stake — burn vs. challenger bounty (WP §8.4 C7)          (P2, status: actionable — decision-register)

- **Reviewer source**     : `Design-review.md` Section 5 (Value Flow Map notes); `Slashing---Concept-Generation-Selection.md` §1 ("Held constant: 95% burn / 5% submitter")
- **Reviewer's "current"**: "Slashed stake → 100% Burned per whitepaper §8.4"
- **Reviewer's proposal** : Two distinct splits across the two subsystems:
  - **Validator BFT slashing**: 95% burn / 5% to evidence-submitter (Concept B held-constant)
  - **Runner slashing**: 50% to first valid challenger / 30% burn / 20% treasury (Concept B for runner marketplace; Concept C of slashing inherits the 95/5 split)
  Both require Tier-3 amendment to WP §8.4 row "Slashed stake | 100% | Burned" (commitment C7).
- **Actual current state**:
  - WP §8.4 (line 716): "| Slashed stake | 100% | Burned |"
  - CIP-13 v2 frontmatter (line 16): "Slashing routing reuses CIP-3 `SettlementConfig.slash_*_percent` (governance-tunable) instead of hard-coding 50/50 treasury/burn. Per-tranche math is unchanged."
  - CIP-13 §3.6 (line 470): "When a runner is slashed for dishonesty (fabricated results, wrong model under TEE), the slash is distributed proportionally across the runner's self-stake and every slashable tranche under the `is_slashable(T, current_block)` predicate from §3.1."
- **Verification**        : ⚠ partially. WP §8.4 still pins 100% burn, but CIP-13 v2 has *already* introduced a governance-tunable `SettlementConfig.slash_*_percent` that contradicts WP §8.4 if any non-100% configuration is ever applied. This is a live drift the reviewer did not catch.
- **Recommendation**      : **decision-register item — Foundation pre-clearance required**. Two paths:
  1. **Foundation affirms C7 → 100% burn stays**: Then CIP-13's `SettlementConfig.slash_*_percent` is bounded to `slash_burn_percent=100` and the validator-side 95/5 (item [Concept B] above) is rejected.
  2. **Foundation amends C7**: Then WP §8.4 receives a new row split (validator slashing 95/5 burn/submitter; runner slashing 50/30/20 challenger/burn/treasury) and CIP-13's `SettlementConfig` plumbing is the implementation surface. CIP-30 §"Validator distribution" pins 95/5. A separate CIP-2 amendment pins the runner 50/30/20.
- **Specific change**     : Decision-register entry; no edit until Foundation rules.
- **Rationale**           : The "100% burn" commitment is the single hardest-to-reverse piece of Cowboy's tokenomics narrative because it is in the whitepaper (not just a CIP) and is the primary deflationary signal beyond basefee burn (cf. WP §8.4 closing paragraph: "The runner fee burn is the primary deflationary mechanism beyond basefee burns"). The reviewer's argument — third-party monitoring needs an economic incentive — is real but is *partially* solved by the validator-side 5% submitter share, which incentivizes evidence collection without redirecting the majority. The runner-side 50/30/20 is harder to defend because runner slashing volume is expected to dwarf validator slashing volume by orders of magnitude, so the burn flow loss is non-trivial.
- **Open questions**      : Foundation policy on C7. Whether a "challenger bond" mechanism (Cosmos pattern: small bond, refunded on valid challenge) makes 50% bounty griefing-resistant (reviewer's R15 mitigation).

## C. Slashing-evidence inclusion path / submitter bounty

### [Concept B / OQ-S6 / §11.4] Simplex evidence enumeration & System-lane classification          (P1, status: actionable)

- **Reviewer source**     : `Slashing---System-Architecture-Objectives.md` §4 (Simplex evidence model) and §5 (per-block VRF rotation)
- **Reviewer's "current"**: "The current whitepaper §11.3 collapses three of [the four Simplex evidence types] into 'double signing' and omits the dummy-vote case entirely."
- **Reviewer's proposal** : Enumerate four Simplex evidence types (notarization equivocation, finality-dummy equivocation, conflicting finalize, proposer equivocation) explicitly. Classify `SlashingEvidence` as System-lane traffic with guaranteed 5% block budget. Per-block VRF rotation means censorship by single Byzantine leader only delays inclusion by 1 block.
- **Actual current state**:
  - WP §11.3 (lines 373–374): "| Double signing | Jail + slash 1% of stake | | Proposer equivocation | Jail + slash 1% of stake |"  — "double signing" umbrella, no enumeration.
  - WP §11 / §11.5 area (line 390): "| **System** | 5% | Validator updates, governance, slashing |" — slashing *is* in the System lane already, but as "slashing" without classifying `SlashingEvidence` evidence-submission transactions specifically.
- **Verification**        : ⚠ partially. Lane classification is implicitly correct (System lane covers slashing); evidence-type enumeration is genuinely missing.
- **Recommendation**      : **new CIP-30 §"Evidence Model"** enumerates the four types with normative struct layouts; WP §11.3 / §11.4 receive corresponding edits.
- **Specific change**     : CIP-30 §"Evidence Model":
  > **Four cryptographically-attributable Byzantine offences (Simplex BFT):**
  > 1. **Notarization equivocation** — two distinct notarization votes signed by same validator at same height.
  > 2. **Finality-dummy equivocation** — two distinct finality-dummy votes (Simplex-specific safety case) signed by same validator at same height.
  > 3. **Conflicting finalize** — finalize votes on two conflicting blocks at same height.
  > 4. **Proposer equivocation** — two distinct proposed blocks signed by same proposer at same height.
  >
  > Each is provable by a two-signature pair plus the equivocator's BLS public key. `SlashingEvidence { offence_type, validator, sig_pair, height, evidence_submitter }` MUST be classified as System-lane (5% per WP §11.5). Evidence is idempotent: the same offence evidence submitted twice settles only once.
  CIP-30 also normatively pins (per `Slashing---System-Architecture-Objectives.md` OQ-S2): the `commonware-consensus::simplex` crate version that defines the wire format.
- **Rationale**           : The "double signing" umbrella is genuinely ambiguous in Simplex BFT — Simplex's safety proof distinguishes notarization from finality-dummy from finalize as three different message types with different consequence levels for safety violations. Per-block VRF rotation (cited by reviewer as helping inclusion robustness) is the structural reason the System-lane guarantee is sufficient: a single Byzantine proposer can delay inclusion at most 1 block, after which a different (VRF-selected) proposer must propose.
- **Open questions**      : OQ-S5 (`block_hash` digest type ambiguous in WP) — must be pinned in CIP-30 or in WP amendment, since evidence transactions reference block hashes. OQ-S4 (NEW_VIEW message size and frequency) is unrelated to evidence but is a WP §20.1 gap.

### [Distribution: 95% burn / 5% submitter]          (P1, status: actionable — scoped to validator)

- **Reviewer source**     : `Slashing---System-Architecture-Objectives.md` §10; `Slashing---Concept-Generation-Selection.md` §1 (held constant across Concepts A/B/C)
- **Reviewer's "current"**: "Distribution: unclear (burn vs submitter share not specified)" — for validator slashing specifically.
- **Reviewer's proposal** : 95% burn / 5% to evidence submitter.
- **Actual current state**: As covered in [36], WP §8.4 C7 says "Slashed stake | 100% | Burned" for *all* slash sources.
- **Verification**        : ⚠ partially. C7 covers validator slashing implicitly but the WP does not separate validator from runner slash distribution.
- **Recommendation**      : Couple to the [36] decision. If Foundation amends C7, CIP-30 pins the validator-side split at 95/5. Argument for the 5%: structural incentive for third-party validator monitoring (which is currently zero — there is no economic reward for a watcher who submits evidence). Validator-slash volume is expected to be small (Polkadot empirical: <1 event/year at any significant magnitude), so the 5% submitter outflow is bounded.
- **Specific change**     : CIP-30 §"Distribution":
  > Slashed stake from validator BFT offences is distributed:
  > - 95% — burned (preserves WP §8.4 deflationary signal at scale)
  > - 5% — credited to `evidence_submitter` of the `SlashingEvidence` transaction (incentivises third-party monitoring; bounded by Polkadot empirical volume)
- **Rationale**           : 5% of a 1%-of-stake slash on a `S_low`-stake validator at TGE is $12–$60 (per reviewer's TGE+30d numbers) — small enough to not motivate griefing, large enough to fund a watcher's gas cost. The split aligns with Cosmos's evidence-submitter bounty pattern (cited by `Slashing---System-Architecture-Objectives.md` §2.2 precedents).
- **Open questions**      : Whether the submitter share should rise with the curve (5% of `p_self(x,n)·S` rather than 5% flat), which makes high-correlation slashes more attractive to whistleblowers. Probably yes, but flag for Phase-5 sim.

## D. Dropped items (math-error claims that don't reproduce against current WP)

### [40] / [63] Unbonding period arithmetic error          (P1 in reviewer's grading, status: dropped)

- **Reviewer source**     : `Design-review.md` Section 13 (item [40]); `Whitepaper-Sections-for-Reconsideration.md` HIGH §13/§27 (item [63])
- **Reviewer's "current"**: "`unbonding_blocks = 7,200 (~24h)` at stated 1-second block time. 7,200 blocks × 1 s/block = 7,200 s = 2 hours, not 24 hours. Arithmetically wrong."
- **Reviewer's proposal** : Either correct comment to "~2 hours" if 7,200 intentional, or bump to 86,400 blocks for 24 hours; reconcile with CIP-13.
- **Actual current state**:
  - WP §13 (line 781): "`unbonding_period` = 7 days" — denominated in **days**, not blocks.
  - WP §11 / Validator Set (line 359): "Withdraw (after 7‑day unbonding period)."
  - CIP-13 §3.3 uses `UNBONDING_BLOCKS` as a symbolic constant in pseudocode (e.g., line 323: "`claimable_at = block_height + UNBONDING_BLOCKS`") but does not pin it to 7,200 anywhere I found in v2; the §4.2 parameter table (not re-quoted here) is the authoritative source and uses the 7-day value.
- **Verification**        : ❌ stale. The cited string `"unbonding_blocks = 7,200 (~24h)"` is **not in the current whitepaper**. The reviewer is correcting a number that does not appear.
- **Recommendation**      : **drop both items**. No CIP / WP edit required for the cited arithmetic error.
- **Specific change**     : None.
- **Rationale**           : The reviewer either consulted a stale draft or invented the 7,200 figure. WP §13 expresses the unbonding period in days (7 days). CIP-13 uses `UNBONDING_BLOCKS` symbolically. If Cowboy were to pin `UNBONDING_BLOCKS = 604_800` (7 days × 86,400 s/day at 1s blocks) in CIP-13 §4.2, the value would be internally consistent with WP. The arithmetic error claim is not actionable.
- **Open questions**      : Verify CIP-13 §4.2 (parameter table) explicitly states `UNBONDING_BLOCKS = 604_800`. If it uses 7,200 anywhere, *then* the reviewer's claim has bite — but on a different (CIP-13) target, not WP §13. Quick read of CIP-13 v2 did not surface a 7,200 anywhere; recommend a confirmation pass before final dispositioning.

## E. Decision-register entries from this topic

1. **WP §8.4 commitment C7 ("Slashed stake | 100% | Burned").** Hold or amend? Required for *any* of the following: (a) validator 95/5 submitter share, (b) runner 50/30/20 challenger/burn/treasury, (c) CIP-13's already-introduced `SettlementConfig.slash_*_percent` ever taking a non-100%-burn configuration. **Owner: Foundation. Blocks: CIP-30 §"Distribution", CIP-2 §8.5 distribution clause.** Recommend amending; if rejected, fall back to "100% burn, submitter rebate as gas refund only" structure.
2. **Adopt Polkadot quadratic curve `(c·x/n)²` (c=3, floor 1%, `X_safety=10`) in place of flat 1% for validator BFT slashing?** Recommend yes. Curve is Tier-0 tunable; floor preserves worst-case-actor deterrent; bug-cap defers upper-tail to Tier-4 review. **Lands in new CIP-30; WP §11.3 follows.**
3. **Replace `minimum_validator_stake = governance-tunable` with hysteresis bands `S_in=0.50%, S_low=0.40%, S_out=0.33%, S_max=5.0%`?** Recommend yes. Bands are themselves Tier-0 tunable. **Lands in new CIP-30; WP §13 follows.**
4. **New `ReviewSlash` Tier-4 flow + cryptographic `evidence_invalidity_proof` reversal path — adopt as new CIP-32?** Recommend yes. Required for Concept B's bug-correlation safety cap and for non-discretionary reversal. **Lands as new CIP-32; CIP-30 references it for upper-tail gate.**
5. **CIP-2 §6 / §8 amendment: commit-without-reveal → proven dishonesty by default, single `CrashAttestation` exemption.** Recommend yes. Closes denial-of-verification vector. **Amends CIP-2 v2 with new §8.5.**
6. **CIP-2 §6A new: EMA reputation with 14-day half-life and recoverable jail-exit floor.** Recommend yes. Closes the long-standing reputation-formula gap. **Amends CIP-2 v2 with new §6A.**
7. **Drop reviewer items #40 and #63 (unbonding-blocks math error).** The cited "7,200 blocks ≠ 24h" string is not in the current WP. WP §13 uses `unbonding_period = 7 days`. Document the drop. **No action.**

## F. New CIPs proposed

- **CIP-30: Validator BFT Slashing Curve & Evidence Model**
  - §"Evidence Model": four Simplex evidence types, struct layout, System-lane classification, idempotency.
  - §"Slashing Curve": `p_self(x, n) = clip(p_floor, (c·x/n)², 1)`; defaults `c=3, p_floor=1%, X_safety=10`; correlation window = 1 epoch (3,600 blocks); max-of settlement rule; per-offence severity table (incl. proposer-equivocation `× 0.5`).
  - §"Stake Bands": `S_in=0.50%, S_low=0.40%, S_out=0.33%, S_max=5.0%` of staked CBY; Tier-0 tunable.
  - §"Distribution": 95% burn / 5% submitter (validator side; gated on decision-register #1).
  - §"Ramp triggers": (a) total value-at-risk > 5× bonded stake → Tier-0 review; (b) TGE+12mo mandatory review; (c) candidate ceiling > 300 → Tier-0 review on `c`.
  - References CIP-32 for upper-tail gate at `x ≥ X_safety`.
- **CIP-32: Slashing Reversal Flow**
  - §"Auto-review": `Payload::ReviewSlash` auto-opened by `0x09` when correlation window closes with `x ≥ X_safety`; 21-day window; outcomes Affirm / Reverse / Partial.
  - §"Cryptographic appeal": `Payload::EvidenceInvalidityAppeal { evidence_id, evidence_invalidity_proof }`; Tier-4; cryptographic-only (no discretionary bailout).
  - §"Delegator compensation": reverse-as-bug credits principal + accrued rewards across slashable tranches per CIP-13 §3.6.

## G. CIP amendments (not new CIPs)

- **CIP-2 §6A (new): Reputation Dynamics** — EMA with 14-day half-life; recoverable jail-exit floor `r_floor = max(round(0.1 × network_median), 50)`; Tier-2 tunable.
- **CIP-2 §8.5 (new): Non-reveal classification** — default proven dishonesty; single `CrashAttestation` exemption within `crash_exemption_blocks` (default 50 blocks); Tier-2 tunable.

## H. WP edits (deferred until CIPs land)

- **WP §11.3** — replace four-row penalty table with Simplex-enumerated table (CIP-30).
- **WP §11.4 / §20.1** — add `SlashingEvidence` transaction format and System-lane classification clause (CIP-30).
- **WP §13** — replace `minimum_validator_stake = governance-tunable` and `double_sign_slash = 1%` with CIP-30 references; add `S_in/S_low/S_out/S_max` and curve parameter defaults.
- **WP §8.4 row "Slashed stake | 100% | Burned"** — conditional on decision-register #1.

---

*End of slashing differential analysis. Total items dispositioned: 8 actionable (covering reviewer items #5, #8, #9, #19, #36, #50, #54 + Concept B parameter pack), 2 dropped (#40, #63). Two new CIPs proposed (CIP-30, CIP-32); two CIP-2 amendments proposed (§6A, §8.5); WP edits gated on CIPs.*
