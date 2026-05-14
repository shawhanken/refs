# 09 — New CIPs / Substantial Amendments Proposed

> Consolidated synthesis of all new CIPs, substantial CIP amendments, and WP edits surfaced by topic files 01–08. **Read-only round; no CIP / WP file is edited in this synthesis pass.** This file is the canonical inventory the next editorial pass will work from.

## TL;DR

- **3 new CIPs proposed** (titles short): **CIP-30** Validator BFT Slashing Curve & Evidence Model; **CIP-31** CBFS Rent Schedule; **CIP-32** Slashing Reversal Flow (`ReviewSlash` + `evidence_invalidity_proof`).
- **1 new CIP deferred** (do not draft this cycle): **CIP-33** Lane V Verifiable Runner Lane (TEE / ZK opt-in).
- **~8 substantial CIP amendments** across **CIP-1 ×1 (rewrite)**, **CIP-2 ×~7 (multiple sections)**, **CIP-3 ×2**, **CIP-4 ×~2**, **CIP-5 ×1 (sunset §9)**, **CIP-9 ×~3** (block-time bug + new field + §10.4 expansion), **CIP-12 ×~3**, **CIP-13 ×~2**.
- **~14 WP edits proposed**, most gated on the CIPs above. Editorial-only WP edits: 2 (broken `§13.1` xref; dangling `§Timer Rate Limiting` xref).
- **Item disposition (across 01–08)**: roughly **52 actionable**, **4 resolved-in-spec**, **4 dropped (misidentified)**, **~6 deferred-to-sim / Phase-5**, **~5 policy decisions** captured in the decision register (see §D below and 00-summary §三).

---

## A. New CIPs proposed

### CIP-30 — Validator BFT Slashing Curve & Evidence Model

- **Source topic**: [01-slashing.md](../01-slashing.md) §A, §C, §E
- **Scope**:
  - **Evidence Model.** Enumerates the four cryptographically-attributable Simplex BFT offences (notarization equivocation, finality-dummy equivocation, conflicting finalize, proposer equivocation) as normative struct layouts (`SlashingEvidence { offence_type, validator, sig_pair, height, evidence_submitter }`). System-lane classification (5% per WP §11.5). Idempotency rule (same offence settles once).
  - **Slashing Curve.** Polkadot-style quadratic `p_self(x, n) = clip(p_floor, (c · x / n)², 1)`. Per-offence severity table (proposer equivocation × 0.5; notarization / finality-dummy / conflicting finalize × 1.0). Max-of settlement rule. Correlation window = 1 epoch (3,600 blocks).
  - **Stake Bands.** Hysteresis bands as fraction of total staked CBY: `S_in = 0.50%`, `S_low = 0.40%`, `S_out = 0.33%`, `S_max = 5.0%`. Replaces `minimum_validator_stake = governance-tunable` in WP §13.
  - **Distribution.** 95% burn / 5% to evidence-submitter (validator side) — **gated on decision-register #1** (WP §8.4 C7 amendment).
  - **Ramp triggers.** TGE+12mo mandatory review; `total_value_at_risk > 5× bonded_stake` → Tier-0 review of `c`; candidate ceiling > 300 → Tier-0 review.
- **Key parameters**: `c = 3` (Tier-0 tunable), `p_floor = 1%`, `X_safety = 10`, `correlation_window_blocks = 3,600`, `S_in/S_low/S_out/S_max = 0.50/0.40/0.33/5.0% of staked CBY`.
- **Dependencies**: references **CIP-32** for the upper-tail (`x ≥ X_safety`) auto-review gate. Distribution clause is gated on **decision-register #1** (WP §8.4 C7).

### CIP-31 — CBFS Rent Schedule

- **Source topic**: [07-state-rent-cbfs.md](../07-state-rent-cbfs.md) §B, §C, §D
- **Scope**: Concrete CBY values for all `TBD` entries in CIP-9 §14 (`STORAGE_FEE_PER_BYTE_PER_EPOCH`, `TRANSFER_FEE_PER_BYTE`, `MIN_STORAGE_BALANCE`, `MIN_RELAY_STAKE`, `POR_MISS_PENALTY`, `POR_FRAUD_PENALTY`, `RELAY_EVICTION_PENALTY`); new `RELAY_CHALLENGE_BOND` field (challenger-bond economics + 75-block dispute window aligned with CIP-2 `DISPUTE_WINDOW_BLOCKS`); explicit pro-rata weighting formula for Relay distribution (`(shard_count × shard_age_in_epochs)` after 10% burn + 2% challenge-pool reservation); resolution of the CIP-9 §14 stale-block-time bug (constants annotated against 12 s blocks while chain runs 1 s — either rescale constants 12× or correct comments).
- **Key parameters** (straw values, economic modeling owns final): `STORAGE_FEE_PER_BYTE_PER_EPOCH = 10 nano-CBY` (1-day epochs); `TRANSFER_FEE_PER_BYTE = 1 nano-CBY`; `MIN_STORAGE_BALANCE = 1 epoch × max(declared_volume_size, 10 MiB)`; `MIN_RELAY_STAKE = 5,000 CBY`; `POR_MISS_PENALTY = 10 CBY/missed challenge`; `POR_FRAUD_PENALTY = 100 CBY` (10× miss); `RELAY_EVICTION_PENALTY = MIN_RELAY_STAKE / 2`; `RELAY_CHALLENGE_BOND = 10 CBY`. Split: 10% burn / 2% challenge-pool / 88% Relay-pro-rata.
- **Dependencies**: none structural (greenfield). CIP-9 §14 retains parameter names; CIP-31 owns values. CIP-9 §5.6 / §10.4 amendments needed in same revision window.

### CIP-32 — Slashing Reversal Flow (`ReviewSlash` + `evidence_invalidity_proof`)

- **Source topic**: [01-slashing.md](../01-slashing.md) §A "Bug-correlation safety cap & cryptographic reversal"
- **Scope**:
  - **Auto-review.** `Payload::ReviewSlash { evidence_id, x_observed, slashed_set, proposed_action: Affirm | Reverse | Partial(bps) }` automatically opened by `0x09` when correlation window closes with `x ≥ X_safety`. Pre-application gate; 21-day review window. Outcomes: Affirm (apply full curve), Reverse (restore principal + accrued rewards), Partial.
  - **Cryptographic appeal.** `Payload::EvidenceInvalidityAppeal { evidence_id, evidence_invalidity_proof: bytes }` for post-application reversal. Cryptographic-only — proof must demonstrate signature-pair invalidity (e.g., wrong domain separator, malformed BLS aggregate). No discretionary bailout permitted; auto-review is the only pre-application bug path.
  - **Delegator compensation.** Reverse-as-bug outcome credits principal + accrued rewards across slashable tranches per CIP-13 §3.6 cascade.
- **Key parameters**: `X_safety = 10`, `review_window_blocks = 1_814_400` (21 days at 1s blocks), proposal tier = Tier-4.
- **Dependencies**: **CIP-30** references CIP-32 for the upper-tail gate. CIP-13 §3.6 cascade logic is unchanged but invoked in reverse direction on Reverse outcomes.

### CIP-33 — Lane V Verifiable Runner Lane (DEFERRED — do not draft this cycle)

- **Source topic**: [03-runner-marketplace.md](../03-runner-marketplace.md) §H
- **Scope (future)**: parallel verification lane with `M = 1` (single runner), cryptographic verification via TEE (`0x05`) or future ZK proof, no output-incorrectness slash (attestation-forgery + availability-breach only). Per-lane reputation (`r_V` separate from `r_R`). Lower stake floor `max(5k CBY USD-equiv, 1.0 × max_job_value_USD)`. Cross-lane bootstrap one-way `r_R → r_V_init = 0.2 · r_R`.
- **Recommendation**: **DEFERRED**. Reasons: (a) Lane V depends on mature TEE attestation (CIP-23) shipping and on a Cowboy ZK story (not in CIP pipeline); (b) demand uncertainty — reviewer's own selection hedges Lane V as opt-in, not Phase-4 default; (c) Concept B (adaptive committee + EMA reputation + fractional non-reveal + delegator voice) already addresses the headline risks. Optionally **reserve a `LaneId` field in `JobSpec`** for forward compat (small one-byte amendment to CIP-2 v2), but do not author the spec at TGE.

---

## B. Substantial CIP amendments proposed

### CIP-1 — substantial rewrite

- **Source topic**: [02-timer-gba.md](../02-timer-gba.md) §B, §C, §E
- **Scope**: Replace Part I's first-price + exponential-bias auction with **EIP-1559 timer basefee + priority tip + per-actor fairness weight**. Default GBA inline (closes Gap G7): `max_fee_per_cycle = 2 × current_basefee`; `max_priority_fee_per_cycle = previous_block_p50_priority_tip` (default 0 if prior block had no timer activity). SDK convenience: `priority_tier_hint ∈ {economy, standard, fast, urgent}` mapping to `{0.8×, 1.0×, 1.5×, 2.5×}` multipliers on the priority tip. Per-actor fairness weight `W(actor) ∈ [1, 2]` over a 1000-block rolling window applied multiplicatively at inclusion-ordering. Per-timer cycle cap 250k (auction-phase only). Timer-lane multiplier pinned at 1.0×. Migration: drop the `bid: int` parameter; existing CIP-1 v2 (Part II alignment doc) folded into a coherent single document.
- **Touchpoints in current CIP-1**: §4.1 default GBA stub; §4.2 first-price-per-cycle / VCG path; §"Bidding & Auction"; §"Anti-starvation" exponential-bias. CIP-5 §9 (future-auction subsection) is removed in the same revision.

### CIP-2 — multiple amendments

- **Source topics**: [03-runner-marketplace.md](../03-runner-marketplace.md) + [01-slashing.md](../01-slashing.md)
- **§5 amend (committee sizing)**: replace static `M = 5 / N = 3` with adaptive `M_epoch = clip(ceil(2 · log₂(N_active) / HHI_epoch), 3, 9)`, `N_epoch = ceil(2 · M_epoch / 3)`. HHI is EMA-smoothed with 14-day half-life. Epoch-level recompute (3,600 blocks). `JobSpec.M` override permitted up to ceiling.
- **§5 amend (VRF weight)**: change weight from `floor(log2(s / MIN_STAKE + 1)) + 1` (stake only) to `w = stake_to_weight(effective_stake) · max(1, floor(sqrt(r)))` (stake × √reputation), with reputation `r ∈ [0, 100]`.
- **§6 amend (non-reveal classification)**: cross-listed with **CIP-2 §8.5** (see slashing analysis). A runner who has committed but failed to reveal within `reveal_deadline_blocks` incurs a **25% fractional slash** of self-bond, EXCEPT during a single per-epoch `non_reveal_exempt_blocks` window.
- **§6 amend (capacity oversell)**: escalate `TIMEOUT_PENALTY` from flat `-5` to value-weighted (deters runners stacking many low-value jobs to game reputation).
- **New §6A (Reputation Dynamics)**: EMA formula `r_{t+1} = round(α · score_t + (1 - α) · r_t)` with `α = 1 - 0.5^(1/HALF_LIFE_BLOCKS)`, `HALF_LIFE_BLOCKS = 1_209_600` (14 days at 1s blocks; corrected from reviewer's "~250k at 5s slots"). `score_t ∈ {0, 100}` clean/slash; graded `score = 25` for timeout / schema-fail. Recoverable jail-exit floor `r = max(round(0.1 × network_median_reputation), 50)` (proven dishonesty per §8.5 resets to 0). Default initial reputation 50. `HALF_LIFE_BLOCKS` and floor coefficient Tier-2 tunable.
- **§8 amend (aggregator eligibility)**: replace "highest reputation in the committee" with: uniformly random (VRF seed + domain separator `'aggregator-select'`) from committee members at or above `network_p50_reputation`. Fallback to highest if none qualify.
- **§8 amend (aggregator bonus)**: bonus = `1.5% × gross_job_payment`, funded from inside the 89% runner share (no Tier-3 amendment to WP §8.4 89/10/1 split needed). Net: aggregator gets `(0.89 × gross / M) + 0.015 × gross`; each other runner gets `(0.89 × gross / M) - (0.015 × gross / (M-1))`.
- **New §8.5 (Non-reveal classification, normative)**: commit-without-reveal = **proven dishonesty by default**. Single `CrashAttestation { job_id, runner_addr, crash_height ≤ commit_height + crash_exemption_blocks }` exemption (default 50 blocks ≈ 50 s), downgrading to operational failure (reputation penalty only). Slashed at proven-dishonesty rate per `SettlementConfig`; reputation reset to 0.
- **§9 amend (SemanticSimilarity model pinning)**: embedding model pinned in on-chain model registry at `system:executor_registry:embedding_default` under `0x09`. Changes require Tier-3 (consensus-relevant verification). Mirror in WP §7 / §9.2.
- **§5 (verification mode) — USD-pegged stake floor**: **DEFERRED**, gated on oracle availability (decision-register #4).

### CIP-3 — minor amendments

- **Source topic**: [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) §A, §D
- **§2.2.3 amend (lane table)**: add `Fee Multiplier` column. Pin all four lanes (System / Timer / Runner / User) at **1.0×** at genesis. Mark Tier-0 tunable per CIP-12. Mirror the WP §6.3 / §17.9 / §13 table.
- **§6.5 amend (MEV scope)**: add explicit `Out of scope` subsection enumerating three non-mitigated classes: (a) single-block proposer inclusion/censorship, (b) private orderflow MEV, (c) JIT MEV against predictable actor logic. Point at SDK-layer mitigations (commit-reveal, slippage caps).

### CIP-4 — minor amendments (or CIP-4 v2 "State Rent Normative Anchor")

- **Source topic**: [07-state-rent-cbfs.md](../07-state-rent-cbfs.md) §A
- **New §"Rent" subsection**: migrate normative rent content out of WP §17.5 prose into CIP-4 v2. Pin catch-up fee semantics: `catch_up_fee_i = 0.10 × missed_rent_i` where `missed_rent_i` uses the **rent rate at epoch i** (miss-time), not catch-up-time rate. Add rent-rate snapshot mechanism (or moving-average fallback if per-epoch snapshots too expensive).
- **Optional**: introduce `rent_rate_floor` and `rent_rate_ceiling` to bound WP §4.4 auto-adjust geometric drift.

### CIP-5 — minor amendment (sunset §9)

- **Source topic**: [02-timer-gba.md](../02-timer-gba.md) §B "future-auction subsection: REMOVE"
- **Scope**: REMOVE CIP-5 §9 (future-auction subsection). Target design moves entirely to CIP-1 rewrite. CIP-5 §§1–8 (current FIFO, per-fire `fee_payer` model, three-path lifecycle, lane budgets) stay unchanged. Relabel CIP-5 header tip to "current implementation, sunset on CIP-1 (rewrite) ship". CIP-5 §9.9 open questions either resolve in CIP-1 (G7, λ calibration, VCG revenue) or evaporate (reserve price, interaction with CIP-1 GBA).

### CIP-9 — block-time bug + new field + §10.4 expansion

- **Source topic**: [07-state-rent-cbfs.md](../07-state-rent-cbfs.md) §B
- **§14 block-time bug**: parameter comments say "12 s blocks" but the chain runs 1 s (WP §6.1). Recompute / re-comment `POR_CHALLENGE_INTERVAL = 600`, `POR_RESPONSE_WINDOW = 50`, `STORAGE_GRACE_EPOCHS = 7,200`, `RELAY_UNSTAKE_DELAY = 7,200`, `ORPHAN_SHARD_TTL = 7,200`. Decision in CIP-31: either rescale constants 12× (preserve intended human-time durations) or correct comments only (accept the 1-second-derived durations).
- **§14 add `RELAY_CHALLENGE_BOND`**: new parameter (currently missing). Value owned by CIP-31; field added to CIP-9 §14 alongside other Relay parameters.
- **§5.6 challenge-bond clause**: add normative requirement that challengers escrow `RELAY_CHALLENGE_BOND` CBY; bond refunded on valid response or fraud-found, forfeit on withdrawal or frivolous-challenge.
- **§10.4 expansion**: make the **10% burn / 2% challenge-pool / 88% Relay-pro-rata** split explicit with the formula `(shard_count × shard_age_in_epochs)`. Currently only the 10% burn is documented; the 90% remainder is "pro-rata by shards held" as prose.

### CIP-12 — minor amendments

- **Source topic**: [06-governance.md](../06-governance.md) §A, §D, §E
- **§3.2 amend (conditional sunset)**: gated on decision-register #3 (policy decision). If adopted, add: Council *scope* (named powers) auto-reduces by one named power per `sunset_epoch_length` (default 1 year) once `validator_count ≥ N` AND `total_staked_value_usd ≥ V` for two consecutive epochs. Order: (1) Cancellation, (2) Fast-track endorsement, (3) Circuit-breaker pause. Tier-4 override permitted. Suggested defaults: `N = 50`, `V = $50M`.
- **§5.2 commentary (Tier-2 quorum)**: add "Note on Tier 2 quorum" paragraph documenting the whale-capture analysis; explain why the bicameral AND-rule (>50% validator chamber) is the appropriate defense rather than raising stake quorum. No parameter change.
- **§10 rationale (turnout)**: add "On expected turnout" paragraph + Foundation commitment to quarterly governance-health reports for the first 24 months post-TGE.
- **§3.1 Foundation funding (latent contradiction)**: §3.1 says Foundation "receives funds only when a treasury disbursement proposal passes governance" — this contradicts WP §8.4's 1% auto-feed to treasury. Reconcile (likely WP-side, gated on decision-register #2 / Path A removing the 1% line).
- **§6.X new (proposal-tag schema)**: introduce `runner-marketplace-parameter` proposal tag for delegator-weight conditional voting (paired with CIP-13 §6.1 amendment).

### CIP-13 — multiple amendments

- **Source topic**: [03-runner-marketplace.md](../03-runner-marketplace.md) + [06-governance.md](../06-governance.md)
- **§4.4 tighten `MAX_COMMISSION_BPS`** (Tier-2 governance call, not spec change): adjust from `10000 (100%)` to `3000 (30%)` once empirical race-to-bottom data exists. Floor `MIN_COMMISSION_BPS = 500 (5%)` unchanged. **Status: stale claim** — bounds already exist; this is parameter tuning.
- **§6.1 grant delegator vote weight**: runner-delegated CBY carries **25% pro-rata weight** on Tier-2 proposals tagged `runner-marketplace-parameter` (defined in CIP-12 §6.X). Zero weight on all other tiers/tags. Voted directly by delegator (not inherited by runner). Snapshot at `voting_start_height`. Aggregates across all `Active` tranches for a delegator; `Unbonding` tranches count at pre-unbond weight (mirrors CIP-12 §6.2). Tier-0 tunable with soft cap (e.g., max 50%) enforced by CIP-12 validation.

---

## C. WP edits proposed (gated on the CIPs above)

| WP § | Current | Proposed | Gated on |
|---|---|---|---|
| §2.2 line 469 | `(§13.1)` broken xref | repoint to `(§12.1)` (DoS limits — exact target of the validity check) | none (editorial) |
| §3.3 line 520 | dangling "(see §Timer Rate Limiting)" — section does not exist | replace with "(see §5.1 and CIP-5 §5.3)" | none (editorial) |
| §4.4 line 423 | "**Eviction (rent-epoch N+10):**" — ambiguous N-indexing | "**Eviction (after 10 rent-epochs of unpaid rent — i.e., 7 rent-epochs grace + 3 rent-epochs warning):**" | none (editorial) |
| §5.1 (entire) | mixes current FIFO with target auction; "256 timers/actor" disagrees with CIP-5 §6.4's 1,024 | split into §5.1a (current CIP-5 FIFO, 1,024 cap) + §5.1b (target CIP-1 EIP-1559 hybrid summary) | **CIP-1 rewrite** |
| §6 Part I line 395 / §6.3 Part II "Dedicated Lanes" / §17.9 / §13 Lanes block | "Each lane has independent fee multipliers" — no numbers | add `Fee Multiplier` column to all three tables; pin `1.0×` for all four lanes; add `lane_fee_multiplier_*` params to §13; mark Tier-0 tunable | **CIP-3 §2.2.3 amend** |
| §6 Part I line 365 / §13 Consensus / §8.4 fee-sinks | implicit "tips + inflation only" but never stated; no `validator_commission_model` parameter | declare `validator_commission_model = tips_only`; note no other user-derived revenue | none (declarative) |
| §6 Part I line 399 / §6.5 line 658 (MEV) | one-line disclaimer | append explicit `Out of scope` subsection enumerating proposer inclusion/censorship, private orderflow MEV, JIT MEV against predictable actor logic | **CIP-3 §6.5 amend** |
| §8.2 inflation schedule | 4-year glidepath 8%/6% → 4%/3% → 2% | 3-year glidepath 4% → 3% → 2% (matches Chad Q6) | **decision-register #5** (policy) |
| §8.2 (narrative) | "net inflation depends on network usage" — non-commital | "at steady state targets net slightly inflationary; burn is counterweight, not target" | none (editorial; couple to §8.2 rewrite) |
| §8.3 (after Network Distribution table) | per-bucket "Emission Model" prose only ("Front-loaded", "Usage-based") | add §8.3.1 "Emission curves (genesis defaults; Tier-0 tunable)" with closed-form per-bucket math: Runner Compute 80M linear-with-usage-rate-lock over 60 mo; Liquidity Mining 23.3M exponential decay 6-mo half-life over 24 mo; Validator Rewards tracks §8.2; Developer Grants milestone-based; Community/Airdrops 2 discrete drops (12M TGE + 8M m+6) | none (genesis spec) |
| §8.4 row "Slashed stake | 100% | Burned" (C7) | flat 100% burn | conditional: 95/5 burn/submitter (validator side), 50/30/20 challenger/burn/treasury (runner side), OR keep | **decision-register #1** |
| §8.4 row "Runner job payments 1% Treasury" | `89% / 10% / 1%` live | conditional remove → `90% / 10% / 0%` (redirect freed 1% to burn for narrative consistency with CIP-12 §3.1) | **decision-register #5b** (Chad Q4 accepted) |
| §11 (Governance) | "Foundation 5-of-9 multisig sunsets after ~12 months" (contradicts CIP-12 permanent-Council framing) | drop the sunset line; add "see CIP-12 for tier values, quorums, deposits, and voting windows" | **CIP-12 amendment** (item 18/51 already pruned in v2) |
| §11.3 four-row penalty table | flat 1% slash for double-signing / proposer equivocation | Simplex-enumerated table with `p_self(x,n)` curve from CIP-30 | **CIP-30** |
| §11.4 / §20.1 | no `SlashingEvidence` tx format | add evidence transaction format + System-lane classification clause | **CIP-30** |
| §13 parameters block | missing `validator_apr_target`, `security_floor_*`, `S_in/S_low/S_out/S_max`, `rent_epoch_length`, `validator_commission_model` | add genesis defaults: `validator_apr_target = 4–6%`; `security_floor_staked_ratio = 33%`, `security_floor_boost_bps = 200`, `security_floor_persistence_blocks = 2_592_000`; `S_in/S_low/S_out/S_max`; `rent_epoch_length = 1 day`; `validator_commission_model = tips_only`; `lane_fee_multiplier_* = 1.0` ×4 | **CIP-30** + 05-tokenomics |
| §16.2 | "Bridge selection and integration are determined by governance" — current path is worst-of-both-worlds | one of (a) pre-select w/ retirement hatch + TVL cap, (b) launch with bridging disabled, (c) keep current — recommend (b) | **decision-register #3** |
| §17.5 (state rent) | rent CBY-denominated, no oracle, no review cadence | append paragraph: rent CBY-denominated; Tier-0 review cadence (30 day post-TGE → 90 day steady state); target USD band `[$1, $10]/MiB/yr`; oracle explicitly deferred | none (declarative) |
| §17.6 (CBFS / CIP-7) | no forward reference to CBFS rent schedule | append "(CBFS Relay Node economics … specified in CIP-9 §14 and CIP-31.)" | **CIP-31** |

---

## D. Items dispositioned

| Status | Count (approx) | Notes |
|---|---|---|
| actionable | ~52 | Concrete CIP / WP edit identified; most gated on a decision-register entry or a parent CIP |
| resolved (already fixed in current spec) | 4 | #18 / #51 (v2 WP §11 strip resolved tier drift); #33 (CIP-13 already pins commission bounds); #44 (Caleb-owns G7 — resolved by CIP-1 rewrite recommendation) |
| dropped (claim misidentified / against non-existent param) | 4 | #40 / #63 (`unbonding_blocks = 7,200 ≠ 24h` — WP §13 uses `7 days`, not `7,200 blocks`); reviewer's "10/90 split undocumented" partially wrong (CIP-9 §10.4 documents the 10% burn); reviewer's "rent-epoch length not specified" wrong (WP §17.5 says `1 day`) |
| deferred to simulation | ~6 | #19 (validator slash-to-attack-value ratio); `c` curve coefficient calibration; `X_safety` bug-event distribution; EMA `score_t` value-weighting; adaptive-committee shock; fragmentation-attack sizing for per-actor weight |
| policy decision (decision register) | 5 + 2 sub | See 00-summary §三 — WP §8.4 C7 burn vs split; Council sunset thresholds; bridge selection; runner stake floor USD-peg; inflation glidepath 4/3/2 vs 8/6→4/3→2; Chad Q4 1% treasury removal; Tier-2 quorum keep-or-raise |

---

## E. Cross-topic findings the reviewer missed

These are latent issues that surfaced during this analysis but were not in the original reviewer's 70-item list. They should appear in the executive summary so they're not lost.

1. **CIP-13 already has `SettlementConfig.slash_*_percent`** as governance-tunable, which is in **latent drift with WP §8.4 C7 "100% burn"** — if any non-100% configuration is ever applied, the on-chain config silently contradicts the whitepaper commitment. Surfaced in 01-slashing.md item #36.
2. **Reviewer's "14-day half-life ≈ 250k blocks at 5s slots" arithmetic is wrong** — Cowboy uses 1 s blocks, so 14 days = **1,209,600 blocks**, not ~250k. Corrected in 03-runner-marketplace.md and used in CIP-2 §6A (and CIP-2 §6A `JAIL_DURATION_BLOCKS`).
3. **Reviewer's "commission uncapped" claim is STALE** — CIP-13 v2 §4.4 already pins `MIN_COMMISSION_BPS = 500` / `MAX_COMMISSION_BPS = 10000`. The reviewer's tightening to 30% is a Tier-2 governance call, not a spec gap. Surfaced in 03-runner-marketplace.md item #33.
4. **Reviewer's "§13.1" broken xref is actually at WP §2.2 line 469, not §16.2** — the reviewer cited stale pre-v2 section numbering throughout. The fix target (`§12.1`) is the same regardless. Surfaced in 08-doc-fixes.md item #67.
5. **Reviewer's "10/90 burn/relay split undocumented in WP" is partially wrong** — CIP-9 §10.4 line 854 DOES specify `STORAGE_FEE_BURN_RATE = 10%`. What's missing is the explicit dispatch formula for the 90% remainder ("pro-rata by shards held" as prose, not formula) and the `RELAY_CHALLENGE_BOND` field. Surfaced in 07-state-rent-cbfs.md.
6. **CIP-9 §14 parameter comments assume "12 s blocks" but the chain is 1 s** — block-time bug affecting `POR_CHALLENGE_INTERVAL`, `POR_RESPONSE_WINDOW`, `STORAGE_GRACE_EPOCHS`, `RELAY_UNSTAKE_DELAY`, `ORPHAN_SHARD_TTL`. Either constants are wrong (need 12× rescale) or comments are wrong (need recompute). **NEW finding** in 07-state-rent-cbfs.md.
7. **CIP-12 §3.1 contradicts WP §8.4 1% auto-feed**: CIP-12 §3.1 says Foundation "receives funds only when a treasury disbursement proposal passes governance" — directly contradicted by the WP §8.4 row "Runner job payments | 1% | Treasury" which is an automatic, not gated, flow. **NEW finding** in 05-tokenomics-inflation.md item §F.
8. **WP §5.1 timer-per-actor cap = 256 vs CIP-5 §6.4 = 1,024** — silent drift between WP body text and the live CIP. Surfaced only because WP §5.1 was being rewritten anyway. **NEW finding** in 02-timer-gba.md item #60.
9. **WP §3.3 dangling "(see §Timer Rate Limiting)" reference to a non-existent section**. Pure editorial xref break, separate from the within-§5.1 cross-link the reviewer flagged. **NEW finding** in 02-timer-gba.md item #69.
10. **Reviewer's pre-v2 section numbering pattern (§11.3 / §25.3 / §11.5 / §25.5 / §11.6 / §25.6 / §13 / §27 / §16.2 / §12.3)** is consistent drift across all four reviewer documents — they were working from a draft with different layout. Meta-finding in 08-doc-fixes.md "Notes for the next editorial pass": a single grep for `§[2-9][0-9]\.` would surface any remaining dangling pre-v2 numbers; the fix list is likely short.
