# Consistency & Ordering Matrix

> **Constraint:** No proposed edit may introduce new CIP↔CIP or CIP↔WP
> divergence. This document enumerates every co-change coupling implied by
> the recommendations in topic files 01–08, groups them into atomic landing
> batches, and gives a conditional text plan for each Decision-Register
> outcome.
>
> Read alongside [cip-impact-matrix.md](./cip-impact-matrix.md),
> [wp-impact-matrix.md](./wp-impact-matrix.md), and
> [../09-new-cips-proposed.md](../09-new-cips-proposed.md).

---

## §A. Pre-existing latent drifts (must resolve, not extend)

These are inconsistencies that already exist in the current corpus, surfaced
during analysis. **Any edit batch that touches these surfaces MUST either
fix the drift or leave it untouched — never extend it.**

| # | Drift | Anchor 1 | Anchor 2 | Resolution policy |
|---|---|---|---|---|
| D1 | Slashed-stake routing schema vs flat-burn commitment | CIP-13 v2 `SettlementConfig.slash_*_percent` (mutable, 0x09-owned) | WP §8.4 C7 row "Slashed stake \| 100% \| Burned" | Until Decision #1 lands, CIP-13 v2 SettlementConfig **default values** MUST be `(100, 0, 0)` and the §note MUST say "non-100% configurations contradict WP §8.4 C7 until C7 is amended via Tier-3". |
| D2 | Treasury auto-feed vs governance-only funding | WP §8.4 "Runner job payments \| 1% \| Treasury" (auto-feed) | CIP-12 §3.1 "Foundation receives funds only when a treasury disbursement proposal passes governance" | Either remove the 1% auto-feed (Decision #5b Path A) **or** amend CIP-12 §3.1 to carve out `protocol-auto-feeds` as a category distinct from "Foundation disbursement". Cannot land any other Treasury-related text until one of the two is chosen. |
| D3 | Foundation 5-of-9 sunset vs permanent Council | WP §11 line "Foundation 5-of-9 multisig sunsets after ~12 months" | CIP-12 §3.2 "permanent Security Council 7-of-9" | The WP line is stale. **Drop it** in the same batch as any other §11 edit; do not let any §11 rewrite carry it forward. |
| D4 | Timer cap drift | WP §5.1 "Per-actor timer limit: 256 active timers" | CIP-5 §6.4 `max_timers_per_actor: u32, // default 1_024` | Resolve when §5.1 is split (Batch B2 below). The split MUST drop the 256 number; 5.1a takes 1,024 verbatim from CIP-5. |
| D5 | Timer scheduling drift | WP §5.1 describes target auction; CIP-5 §1 describes current FIFO | WP §5.1 vs CIP-5 §§1–8 | Split WP §5.1 into 5.1a (CIP-5 current) + 5.1b (CIP-1 target). The split is atomic with the CIP-1 rewrite (Batch B2). |
| D6 | Dangling cross-references | WP §2.2 line 469 `(§13.1)`, WP §3.3 line 520 `(see §Timer Rate Limiting)` | (no real anchor) | Editorial fixes, can land in Batch B1 (no gate). Must NOT repeat in any new draft. |
| D7 | Eviction wording | WP §4.4 "Eviction (rent-epoch N+10)" vs WP §17.5 "after 10 rent-epochs" | both reference same threshold | Pick "after 10 rent-epochs" wording and use that string verbatim in both (Batch B1). |
| D8 | CBFS Relay constant block-time assumption | CIP-9 §14 comments "~2 hours at 12s blocks" etc. | WP §6.1 `block_time = 1 s` | Either rescale every constant (`× 12`) or rewrite every comment. **Pick one** in CIP-9 §14 edit and apply uniformly — partial fix creates new drift inside CIP-9 itself. |
| D9 | Lane multiplier mentions vs missing values | WP §6 line 365, WP §6.3 lanes table, WP §13 parameters, WP §17.9 reserved-capacity, CIP-3 §2.2.3 all reference "per-lane fee multipliers" | no concrete values exist anywhere | Pin `1.0× ∀ lanes` in **all five** locations in the same batch (B3). One missed location = silent drift. |
| D10 | Reviewer pre-v2 §-numbering | Reviewer cites §11.3 / §25.3 / §11.5 / §25.5 / §16.2 / §13 / §27 etc. — only some still exist in v2 | (meta) | Pre-merge grep must confirm every WP section cited in CIPs / other WP sections resolves in v2 numbering. |

---

## §B. Cross-document references introduced by the recommendations

Every entry below is a NEW CIP↔CIP, CIP↔WP, or WP↔WP link. Each link is
**bidirectional**: both endpoints must be edited together or one will
dangle.

### B.1 New CIP-30 (Validator BFT Slashing)

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-30 §"Bug cap" → CIP-32 `Payload::ReviewSlash` | outgoing | CIP-32 defines `Payload::ReviewSlash { evidence_id, x_observed, slashed_set, proposed_action }` | **MUST land atomic with CIP-32** |
| WP §11.3 (new table) → CIP-30 evidence types | outgoing | CIP-30 §"Evidence Model" enumerates the four Simplex types verbatim | atomic |
| WP §13 (new constants) → CIP-30 parameter names | outgoing | CIP-30 declares `c, p_floor, X_safety, S_in, S_low, S_out, S_max, correlation_window_blocks` | atomic |
| CIP-30 §"Tier" classification → CIP-12 §5.x | outgoing | CIP-12 acknowledges Tier-0 tunability of `c, p_floor, X_safety, S_*` | atomic with CIP-12 §5.x amend |
| CIP-30 §"Distribution" → WP §8.4 C7 row | conditional | WP §8.4 row must match: `(95%, 5%)` (validator side) if Decision #1 = AMEND; or `(100%, 0%)` otherwise | gated by Decision #1 |

### B.2 New CIP-32 (Slashing Reversal)

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-32 §"Delegator compensation" → CIP-13 §3.6 | outgoing | CIP-13 §3.6 wording must describe `slashable tranches` and reverse-flow restoration | If CIP-13 §3.6 doesn't already cover reversal, **amend CIP-13 in same batch** |
| CIP-32 `EvidenceInvalidityAppeal` → CIP-30 evidence_id schema | outgoing | CIP-30 defines `evidence_id` type | atomic with CIP-30 |
| CIP-32 §"Tier-4" → CIP-12 §5.2 / §6 | outgoing | CIP-12 acknowledges new Tier-4 proposal class `EvidenceInvalidityAppeal` | atomic with CIP-12 §5.2 amend |

### B.3 New CIP-31 (CBFS Rent Schedule)

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-31 → CIP-9 §14 parameter names | outgoing | CIP-9 §14 lists names + `(value defined in CIP-31)`; numeric TBDs removed | **MUST land atomic with CIP-9 §14 edit** |
| CIP-31 split formula → CIP-9 §10.4 | outgoing | CIP-9 §10.4 split = `10/2/88` matches CIP-31; if CIP-9 §10.4 currently says `10%/pro-rata` only, expand to three-way split | atomic |
| WP §17.6 → CIP-31 forward-reference | outgoing | WP §17.6 one-line forward ref must point at CIP-9 §14 + CIP-31 | atomic |
| CIP-31 `RELAY_CHALLENGE_BOND` (new field) → CIP-9 §5.6 (challenge bond clause) | outgoing | CIP-9 §5.6 must declare the field name + describe lifecycle | atomic |
| CIP-31 dispute window → CIP-2 `DISPUTE_WINDOW_BLOCKS` | outgoing | Value MUST equal 75 (CIP-2 §6 constant) | no new edit; check at merge |

### B.4 CIP-1 rewrite (Timer EIP-1559)

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-1 rewrite → CIP-5 §6 baseline (current FIFO) | outgoing | CIP-5 header tip mentions "sunset on CIP-1 ship"; §9 removed | **MUST land atomic with CIP-5 §9 removal** |
| WP §5.1a → CIP-5 §6 / §6.4 verbatim numbers | outgoing | WP §5.1a quotes `max_timers_per_actor = 1024`, `max_cycles_per_fire = 550_000`, `max_cells_per_fire = 550_000`, `LANE_TIMER_CYCLES = 2_000_000` | atomic |
| WP §5.1b → CIP-1 normative spec | outgoing | WP §5.1b summary lines match CIP-1 (default GBA, EIP-1559 basefee, W∈[1,2] weight, 250k auction-phase cap) | atomic |
| WP §3.3 "Timers" line 520 → §5.1 + CIP-5 §5.3 | outgoing | replace dangling `(see §Timer Rate Limiting)`; new target `§5.1 and CIP-5 §5.3` | atomic with §5.1 split |
| CIP-1 priority-tier multipliers → CIP-12 §5.x Tier-2 scope | outgoing | CIP-12 Tier-2 list includes `priority_tier_hint multipliers` | atomic with CIP-12 §5.2 amend |

### B.5 CIP-2 multi-amendment

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-2 §5 (adaptive committee) → WP §13 `committee M, threshold N` | outgoing | WP §13 replaces `M = 5; N = 3` with "see CIP-2 §5"; or with the formula | atomic |
| CIP-2 §5 (adaptive committee) → WP §7 (runner selection narrative) | outgoing | WP §7 prose stops saying "fixed 5/3 committee" | atomic |
| CIP-2 §6A (EMA reputation, half-life 1,209,600 blocks) → WP §13 | outgoing | WP §13 adds `reputation_half_life_blocks = 1_209_600` and `JAIL_DURATION_BLOCKS` | atomic |
| CIP-2 §8 (aggregator eligibility + 1.5% gross) → WP §8.4 + §13 | outgoing | WP §13 adds `aggregator_bonus_bps = 150` (of gross), `aggregator_eligibility_percentile = 50`; WP §8.4 footnote acknowledges aggregator bonus is paid from runner's 89% share | atomic |
| CIP-2 §8.5 (non-reveal slash routing) → CIP-13 v2 SettlementConfig | outgoing | CIP-13 SettlementConfig MUST accept and route the slash; default `(100,0,0)` until Decision #1 amends | depends on Decision #1 path |
| CIP-2 §8.5 (non-reveal slash distribution) → WP §8.4 C7 row | outgoing | WP §8.4 row reflects runner-side split: `(50,30,20)` if Decision #1 = AMEND; `(100,0,0)` otherwise | gated by Decision #1 |
| CIP-2 §9 (embedding pinning) → CIP-12 §7 Tier-3 process | outgoing | CIP-12 §7 lists `model_registry.embedding_default` as Tier-3 mutable | atomic with CIP-12 §7 amend |
| CIP-2 (USD-pegged stake floor, deferred) | n/a | NO change in this round (Decision #4 default: keep CBY-denominated) | no edit; just affirm |

### B.6 CIP-13 amendments

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-13 §6.1 v2 (25% delegator vote) → CIP-12 §6.X proposal-tag schema | outgoing | CIP-12 §6.X declares `proposal_tags ⊂ { runner-marketplace-parameter, ... }` and the 25% weighting rule | **MUST land atomic with CIP-12 §6.X NEW subsection** |
| CIP-13 §3.6 (slashing cascade language) → CIP-32 §"Delegator compensation" | bidirectional | language must agree on `slashable tranches` and reverse-credit semantics | atomic with CIP-32 |
| CIP-13 §4.4 commission tighten | n/a | NO spec change this round (Tier-2 governance call uses existing schema) | no edit |

### B.7 CIP-3 minor

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-3 §2.2.3 lane Fee Multiplier column → WP §6.3 lanes table | outgoing | WP §6.3 mirrors the `1.0× ∀ lanes` column | atomic |
| CIP-3 §2.2.3 → WP §13 (new `lane_fee_multiplier_*` params) | outgoing | WP §13 lists the four multipliers, all `1.0`, Tier-0 tunable | atomic |
| CIP-3 §2.2.3 → WP §17.9 reserved-capacity table | outgoing | §17.9 adds Fee Multiplier column matching §6.3 | atomic |
| CIP-3 §6.5 MEV "Out of scope" → WP §6 line 399 + WP §6.5 (Part II) | outgoing | both WP locations enumerate the same three exclusions in same order | atomic |

### B.8 CIP-4 minor

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-4 v2 §"Rent" → WP §17.5 | outgoing | WP §17.5 either retains the same text or carries a one-line "(canonical spec: CIP-4 §X)" pointer | atomic |
| CIP-4 v2 catch-up formula → WP §4.4 line 423 wording | outgoing | both say `after 10 rent-epochs` (D7) | atomic |
| CIP-4 v2 `rent_epoch_length = 1 day` → WP §13 | outgoing | WP §13 declares the parameter explicitly | atomic |

### B.9 CIP-9 minor (block-time bug)

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-9 §14 comments | n/a | rescale OR re-comment uniformly (D8); CIP-31 cross-references must match the chosen interpretation | self-contained but **affects CIP-31 numbers** if rescale path is chosen |

### B.10 CIP-12 amendments

| References | Direction | Endpoint must contain | Co-change |
|---|---|---|---|
| CIP-12 §3.2 Council conditional sunset → WP §11 (Security Council para) | outgoing | WP §11 mirrors `sunset_thresholds = { N=50 validators, V=$50M USD-TWAP, sunset_epoch_length = 1 year }` (defaults; Tier-4 tunable) | gated by Decision #2 |
| CIP-12 §3.1 vs WP §8.4 1% auto-feed | bidirectional | either CIP-12 §3.1 carves out auto-feeds, OR WP §8.4 removes the 1% row | gated by Decision #5b |
| CIP-12 §5.2 Tier-0 list → CIP-30 + CIP-1 priority-tier multipliers | outgoing | Tier-0 list grows; ensure no item ends up in two tiers | atomic with the amending CIPs |
| CIP-12 §6.X (NEW proposal-tag schema) → CIP-13 §6.1 v2 | bidirectional | tag enum must match exactly the strings CIP-13 §6.1 v2 references | atomic |
| CIP-12 §7 (Tier-3 list expansion) → CIP-2 §9 embedding pinning | outgoing | Tier-3 list explicitly includes `model_registry.embedding_default` change | atomic with CIP-2 §9 amend |
| WP §11 "Foundation 5-of-9 multisig sunsets after ~12 months" (D3) | outgoing | line dropped in any §11 edit | atomic with any §11 amend |

### B.11 WP-only editorial (no CIP gate)

- WP §2.2:469 `(§13.1)` → `(§12.1)`
- WP §3.3:520 `(see §Timer Rate Limiting)` → `(see §5.1 and CIP-5 §5.3)`
- WP §4.4:423 wording → "Eviction (after 10 rent-epochs of unpaid rent — 7 grace + 3 warning)"
- WP §11 drop stale "Foundation 5-of-9 multisig sunsets" line (D3) — pair with CIP-12 amendment batch but can also land standalone if CIP-12 not amended this batch.

---

## §C. Atomic landing batches (recommended order)

Each batch is **internally drift-free**. A batch may be skipped or
re-ordered, but no batch may be **partially** applied without re-checking
the consistency invariants in §E.

### Batch B0 — Editorial-only fixes (no gate)

- WP §2.2:469 → `(§12.1)`
- WP §3.3:520 → `(see §5.1 and CIP-5 §5.3)` (this is also B2-coupled; if B2 is happening in same release, do it in B2)
- WP §4.4:423 wording fix
- WP §11 drop "Foundation 5-of-9 sunsets" stale line (D3)
- CIP-9 §14 block-time comments OR rescale (D8)

**Resolves:** D6, D7, D3, D8.
**Gate:** none.
**Verification grep:** see §E below.

### Batch B1 — CIP-30 + CIP-32 + WP §11.3 / §11.4 / §13 (consensus block)

Land together:

- New CIP-30 (Validator BFT Slashing Curve + Evidence Model)
- New CIP-32 (Slashing Reversal Flow)
- WP §11.3 four-row table → CIP-30 enumerated table
- WP §11.4 / §20.1 → `SlashingEvidence` transaction format
- WP §13 consensus-block parameters: `S_in / S_low / S_out / S_max / c / p_floor / X_safety / correlation_window_blocks` added; `double_sign_slash = 1%` removed
- CIP-12 §5.2 Tier-0 list extension to include the new constants
- CIP-12 §7 (only the new evidence-class line) if CIP-32 introduces Tier-4 `EvidenceInvalidityAppeal`

**Distribution clause (CIP-30 §"Distribution") and WP §8.4 C7 row are
NOT in this batch** — they depend on Decision #1.

**Resolves:** items #5, #8, #19, #50 (slashing taxonomy + curve + bands).
**Pre-existing-drift status:** D1 still present (default-burn config unchanged).
**Gate:** none (mechanism scaffolding only).

### Batch B1.D1 — Decision #1 lands (WP §8.4 C7 amendment)

If Decision #1 = AMEND:
- WP §8.4 C7 row → `Slashed stake (validator) | 95% Burn / 5% Submitter`; `Slashed stake (runner) | 50% Challenger / 30% Burn / 20% Treasury`
- CIP-30 §"Distribution" sets validator-side defaults `(95, 5)`
- CIP-2 §8.5 sets runner-side defaults `(50, 30, 20)`
- CIP-13 v2 SettlementConfig **default values change** to match these
- CIP-13 v2 §note retires the "non-100% configurations contradict WP §8.4 C7" caveat

If Decision #1 = HOLD:
- WP §8.4 C7 row unchanged
- CIP-30 §"Distribution" defaults `(100, 0)`; field retained for future Tier-3
- CIP-2 §8.5 defaults `(100, 0, 0)`; field retained
- CIP-13 v2 SettlementConfig defaults `(100, 0, 0)`; **the §note declaring contradiction MUST stay until C7 is amended**

**This batch MUST land atomically with whichever choice is made.**

### Batch B2 — CIP-1 rewrite + CIP-5 sunset §9 + WP §5.1 split

- CIP-1 rewrite (Part I), CIP-5 §9 REMOVE, CIP-5 header tip relabel
- WP §5.1 split into 5.1a (current CIP-5 numbers verbatim) + 5.1b (CIP-1 target summary)
- WP §3.3:520 dangling ref repointed (if not already done in B0)
- WP §5.1 "256 timers" line dropped (D4 resolution)
- CIP-12 §5.2 Tier-2 list includes priority-tier multipliers if not done in B1

**Resolves:** items #13, #23, #28, #44, #60, #69; D4, D5.
**Gate:** none structural — but **see §D** for whether B1 or B2 lands first; both are independent.

### Batch B3 — CIP-2 multi-amendment + WP §7 / §8.4 / §13

- CIP-2 §5 (adaptive committee + VRF weight)
- CIP-2 §6A (new) EMA reputation
- CIP-2 §8 (aggregator eligibility + 1.5% gross)
- CIP-2 §8.5 (new) non-reveal classification (distribution defaults match B1.D1 outcome)
- CIP-2 §9 (embedding pinning + Tier-3 change)
- WP §7 prose update (no static M=5/N=3)
- WP §13 adds `reputation_half_life_blocks`, `aggregator_bonus_bps`, `aggregator_eligibility_percentile`; removes `committee M = 5; N = 3` literal
- WP §8.4 footnote: aggregator bonus from runner share
- CIP-12 §7 Tier-3 list includes `model_registry.embedding_default`

**Resolves:** items #9 (cross-ref to B1.D1), #10, #11/#53, #12, #14/#56, #22, #24/#65, #27/#55.
**Gate:** distribution clause depends on B1.D1.
**Couples with:** B1 (CIP-30 references) and B1.D1 (distribution).

### Batch B4 — CIP-3 lane multipliers + MEV scope

- CIP-3 §2.2.3 lane table + Fee Multiplier column
- CIP-3 §6.5 MEV out-of-scope
- WP §6.3 lanes table (mirror)
- WP §13 lane_fee_multiplier_* params (mirror)
- WP §17.9 reserved-capacity table (mirror)
- WP §6 line 399 + WP §6.5 MEV exclusions (mirror)
- WP §6 line 365 validator-revenue clarification (no separate user commission)

**Resolves:** items #32, #68, #70. Resolves D9 in one shot — all five lane-multiplier references converge.
**Gate:** none.

### Batch B5 — Tokenomics block (WP §8.2 / §8.3 / §8.4 / §13 economics)

Lands together (after Decision #5 and #5b):

- WP §8.2 inflation schedule replaced (4y → 3y) if Decision #5 = AMEND
- WP §8.2 net-stance language replaced ("net slightly inflationary, burn is counterweight")
- WP §8.2 security-floor mechanism parameters spelled out
- WP §8.3.1 (new) per-bucket emission curves
- WP §8.4 treasury row updated per Decision #5b (Path A / B / C)
- WP §13 economics-block adds `validator_apr_target`, `security_floor_staked_ratio`, `security_floor_boost_bps`, `security_floor_persistence_blocks`
- CIP-12 §3.1 amended (carve out auto-feeds) **only if** Decision #5b = Path C (keep 1%); otherwise §3.1 reads cleanly
- (Optional) CIP-34 authored for emission curves if §8.3.1 length warrants

**Resolves:** items #3, #4, #17, #26, #30, #31, #39, #41, #48, #49, #66; D2, D3 cleanup.
**Gate:** Decision #5, #5b.

### Batch B6 — CBFS rent (CIP-31 + CIP-9 + WP §17)

- New CIP-31 (CBFS Rent Schedule)
- CIP-9 §14 TBDs → pointers to CIP-31; block-time question already resolved in B0
- CIP-9 §10.4 split formula expanded to 10/2/88
- CIP-9 §5.6 RELAY_CHALLENGE_BOND clause
- WP §17.6 forward-reference line added

**Resolves:** items #29, #58.
**Gate:** Decision #4 path "keep CBY-denominated" (otherwise CIP-31 oracle dependency adds a co-change with a future oracle CIP).

### Batch B7 — Governance / Council / Bridge (CIP-12 + WP §11 + §16.2)

- CIP-12 §3.2 Council conditional sunset (gated by Decision #2)
- WP §11 Council sunset mirror
- CIP-12 §6.X (NEW) proposal-tag schema for `runner-marketplace-parameter`
- CIP-13 §6.1 v2 (25% delegator vote)
- WP §16.2 bridge stance per Decision #3
- (conditional) New CIP-35 if Decision #3 = option (a)
- WP §11 commentary on Tier-2 quorum + turnout transparency commitment

**Resolves:** items #2 (cross-ref), #16, #21, #37, #38, #45, #46, #47, #52, #61, #62.
**Gate:** Decisions #2, #3.

### Batch B8 — Stake-floor pinning + CIP-4 rent move

- WP §17.5 paragraph re-affirming CBY-denominated rent + Tier-0 cadence (gated by Decision #4)
- WP §17.10 monitoring policy
- CIP-4 v2 rent text migration from WP §17.5

**Resolves:** items #7, #15, #34, #57, #59; D7 if not done in B0.
**Gate:** Decision #4.

---

## §D. Conditional branches by Decision-Register outcome

For each policy decision, the **consistent text** under each branch is
specified. Pick a branch BEFORE editing.

### Decision #1 — WP §8.4 C7 (slashed-stake distribution)

**Path "AMEND"** (recommended):
- WP §8.4 row: validator `(95, 5)`; runner `(50, 30, 20)`
- CIP-30 §"Distribution" defaults: `(95, 5)`
- CIP-2 §8.5 defaults: `(50, 30, 20)`
- CIP-13 v2 SettlementConfig defaults: `(50, 30, 20)` for runner ops, `(95, 5)` for validator ops
- CIP-13 v2 §note: REMOVE the "contradicts WP §8.4 C7" caveat

**Path "HOLD"** (preserves status quo):
- WP §8.4 row: unchanged
- CIP-30 §"Distribution" defaults: `(100, 0)`
- CIP-2 §8.5 defaults: `(100, 0, 0)`
- CIP-13 v2 SettlementConfig defaults: `(100, 0, 0)`
- CIP-13 v2 §note RETAINED until a future C7 amendment
- Submitter bounty (CIP-30) and challenger bounty (CIP-2 §8.5) become **placeholder fields with no economic value** — flag prominently as inactive until C7 amends

### Decision #2 — Security Council conditional sunset

**Path "AMEND"** (recommended; default `N=50, V=$50M`):
- CIP-12 §3.2 adds sunset clause; "permanent" framing softened to "removable by sunset OR Tier 4"
- WP §11 Security Council para mirrors the same thresholds verbatim

**Path "HOLD"**:
- CIP-12 §3.2 unchanged ("permanent, removable only via Tier 4")
- WP §11 unchanged on the Council para
- (the stale "Foundation 5-of-9 sunsets" line is still dropped — that's D3, unrelated)

### Decision #3 — Bridge selection

**Path (a) "pre-select with retirement hatch"**:
- WP §16.2 names the bridge, security model, TVL cap, Tier-2 retirement trigger
- New CIP-35 authored
- CIP-25 unchanged

**Path (b) "launch with bridging disabled"** (recommended):
- WP §16.2 rewritten to "EVM↔Cowboy bridging is disabled at genesis. Governance elects a backend per CIP-25 via Tier-2/3 post-mainnet."
- CIP-25 unchanged
- No CIP-35

**Path (c) "keep current (fully deferred)"**:
- No WP/CIP edit
- Decision-register entry stays open; next batch pass MUST treat as a re-decision

### Decision #4 — Runner stake floor

**Path "CBY-denominated + monitoring"** (recommended):
- WP §17.10 + §17.5 add monitoring cadence + Tier-0 trigger paragraphs
- CIP-2 §5 unchanged (current `max(10k CBY, 1.5 × declared_max_job_value)`)
- No oracle dependency introduced

**Path "USD-pegged via TWAP"**:
- WP §17.10 amended to TWAP formula
- CIP-2 §5 amended
- **New CIP needed** for the consensus-layer oracle module; CIP-31 also acquires USD-anchor option
- Effectively pushes the batch into a future round (oracle CIP doesn't exist yet)

### Decision #5 — Inflation glidepath

**Path "AMEND to 3-year 4 → 3 → 2"** (recommended):
- WP §8.2 table replaced
- WP §13 economics-block updated to match

**Path "HOLD on 4-year 8/6 → 4/3 → 2"**:
- WP §8.2 unchanged
- WP §13 unchanged (no contradiction)

### Decision #5b — Treasury 1%

**Path A "remove, redirect to burn"** (recommended):
- WP §8.4 row: `89% / 11% / 0%` OR `90% / 10% / 0%` (depends on whether runner share grows or stays — recommend keeping `89%` to runners and adding the 1% to burn → `89% / 11% / 0%`)
- CIP-2 SettlementConfig defaults updated to match
- CIP-12 §3.1 unchanged (now consistent — Foundation only via governance)

**Path B "remove, redirect to runner"**:
- WP §8.4 row: `90% / 10% / 0%`
- CIP-2 SettlementConfig defaults updated
- CIP-12 §3.1 unchanged

**Path C "keep 1%"**:
- WP §8.4 row unchanged
- **CIP-12 §3.1 MUST be amended** to carve out protocol auto-feeds (resolves D2)

### Decision #5c — Commission cap

(No spec change in either branch; this is a Tier-2 governance call that
uses CIP-13's existing `MAX_COMMISSION_BPS` field.)

---

## §E. Pre-merge verification grep checklist

Before merging any batch, the following grep invariants MUST pass.
Failures indicate new drift.

| # | Check (run from repo root) | Pass condition |
|---|---|---|
| V1 | `rg -n "1% .*[Bb]urn" refs/whitepaper/ refs/cips/` | Every occurrence aligns with the chosen Decision #1 branch |
| V2 | `rg -n "(M ?= ?5\|N ?= ?3)" refs/whitepaper/ refs/cips/cip-2*` | Zero hits in WP §13 + CIP-2 §5 after B3 lands |
| V3 | `rg -n "256.*active timers\|max_timers_per_actor.*256" refs/whitepaper/ refs/cips/` | Zero hits after B2 lands |
| V4 | `rg -n "\(§13\.1\)" refs/whitepaper/` | Zero hits after B0 lands |
| V5 | `rg -n "§Timer Rate Limiting" refs/whitepaper/` | Zero hits after B0 (or B2) lands |
| V6 | `rg -n "Foundation .* 5-of-9.* sunsets" refs/whitepaper/` | Zero hits after B0 (or B7) lands |
| V7 | `rg -n "12 ?s.*blocks?\|at 12s" refs/cips/cip-9*` | Either zero hits (re-comment path) OR every hit accompanied by recomputed `× 12` constant (rescale path); no half-fix |
| V8 | `rg -n "8%.*6%\|6%.*4%.*3%.*2%" refs/whitepaper/` | Per Decision #5 branch |
| V9 | `rg -n "lane.*multiplier" refs/whitepaper/ refs/cips/cip-3*` | If pinned in CIP-3 §2.2.3, every reference says `1.0×` (or "Tier-0 tunable per CIP-3 §2.2.3") |
| V10 | `rg -n "permanent.*Security Council\|permanent.*Council 7-of-9" refs/whitepaper/ refs/cips/cip-12*` | Per Decision #2 branch; consistent across both files |
| V11 | `rg -n "1,209,600\|reputation_half_life" refs/whitepaper/ refs/cips/` | After B3, value matches in CIP-2 §6A and WP §13 |
| V12 | `rg -n "250k.*at 5s\|250000.*5s\|14[- ]day.*250" refs/cips/ refs/whitepaper/ refs/notion/cowboy-vm-shared/_analysis/` | Zero hits (reviewer's erroneous arithmetic must not propagate) |
| V13 | `rg -n "SettlementConfig" refs/cips/cip-13*` | CIP-13 §note about C7 either retained (HOLD path) or removed (AMEND path); never half-state |
| V14 | `rg -n "Treasury.*1%\|job_fee_to_treasury" refs/whitepaper/ refs/cips/` | Per Decision #5b branch; consistent everywhere |
| V15 | `rg -n "MIN_COMMISSION_BPS\|MAX_COMMISSION_BPS" refs/cips/cip-13*` | Field exists, values match current (5% / 100%); if tightened, all three places update together |
| V16 | `rg -n "ReviewSlash\|evidence_invalidity_proof" refs/cips/` | If present in CIP-30, must also be defined in CIP-32 |
| V17 | `rg -n "RELAY_CHALLENGE_BOND" refs/cips/cip-9* refs/cips/cip-31*` | Both files reference the field; CIP-31 owns the value, CIP-9 declares the name |
| V18 | `rg -n "runner-marketplace-parameter" refs/cips/cip-12* refs/cips/cip-13*` | Both files reference the tag string; consistent spelling |
| V19 | `rg -n "default.*GBA\|default_gba" refs/whitepaper/ refs/cips/cip-1* refs/cips/cip-5*` | After B2, only CIP-1 carries normative spec; WP §5.1b summarizes; CIP-5 contains no default-GBA spec |
| V20 | (manual) every §-reference in CIPs to the WP resolves in the current v2 file (`refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md`) | All anchors valid; no pre-v2 `§25.x` survivors |

---

## §F. Quick-look invariant statements (for next editor's checklist)

The post-edit corpus MUST satisfy:

1. **One source of truth per fact.** Every numeric parameter has a unique
   normative home (CIP for mechanism, WP §13 for parameter declaration).
   If a number appears in both, they MUST be identical strings.
2. **No dangling cross-references.** Every `§X.Y` and `(§X)` in CIPs and
   the WP resolves in the current v2 WP numbering.
3. **No silent capability drift.** If a field exists in a CIP schema (e.g.
   `SettlementConfig.slash_*_percent`), the default values MUST conform
   to the strictest commitment elsewhere (e.g. WP §8.4 C7); the schema's
   note MUST acknowledge any latent permission to deviate.
4. **Reviewer's pre-v2 numbering is purged.** No `§11.3`, `§11.5`, `§25.3`,
   `§25.5`, `§27`, `§16.2` ref appears in our analysis or in eventual
   edits unless that exact section exists in v2.
5. **Every policy-decision branch leaves the corpus internally
   consistent.** Picking HOLD on Decision #1 doesn't strand
   submitter/challenger fields — flag them as inactive.
6. **Atomic batches.** If a batch is started but cannot complete (e.g.
   Decision blocks one of its items), roll back the whole batch; do not
   land a partial.

---

*End of consistency-and-ordering matrix. Update this file in lockstep with
any new recommendation or decision-register outcome.*
