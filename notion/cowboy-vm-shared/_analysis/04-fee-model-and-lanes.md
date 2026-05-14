# 04 — Fee Model, Lanes, MEV Scope

## TL;DR

- **Per-lane fee multipliers are referenced but never quantified** in the WP. WP §6 (revised v2 — sections renumbered from the reviewer's "§11.5 / §25.5") states `Each lane has independent fee multipliers applied to the global cycle/cell basefees`, and CIP-3 §2.2.3 partitions the cycle budget into lane shares — but no document assigns numerical multipliers. **Recommended: pin all 4 lanes at 1.0× for launch**, declare the multiplier vector Tier-0 governance-tunable, and add an inline table to WP §6 (currently the "Dedicated Lanes" subsection) and CIP-3 §2.2.3. This is consistent with the Phase-3 hybrid decision already recorded in 02-timer-gba.md.
- **Validator commission model does not exist** in any current CIP or WP section. Reviewer's gap is real. **Recommended: commit explicitly to "no separate validator commission — validators receive 100% of tips on blocks they propose plus inflation rewards proportional to stake"** and add a single line to WP §13 (Parameters) and to the inflation paragraph in WP §6 / §8 stating this.
- **Runner commission bounds are already spec'd** in CIP-13 (`MIN_COMMISSION_BPS = 500`, `MAX_COMMISSION_BPS = 10000`). This item is treated authoritatively in 03-runner-marketplace.md; cross-reference only here.
- **MEV scope** — both WP §6.5 (Part II) and WP §6 (Part I "MEV Reduction" prose) already include one disclaimer line ("This does not prevent proposer inclusion/censorship or private orderflow MEV"). Reviewer's recommendation is half-implemented; an explicit `Out of scope` bulleted subsection should be added so the disclosed limits are not buried.

## Items index

| # | Title | Priority | Touches | Status | Action |
|---|---|---|---|---|---|
| 68 | Per-lane fee multipliers unspecified | P2 | WP §6 / §17.9, CIP-3 §2.2.3 | actionable | pin 1.0× ∀ lanes; add table to WP §6 and CIP-3 §2.2.3; mark Tier-0 tunable |
| 32 | Validator commission model unspecified | P2 | WP §13, WP §8 | actionable | declare "tips + inflation only, no separate commission" in WP §13 |
| 33 | Runner commission bounds | P2 | CIP-13 | resolved | cross-ref only — see 03-runner-marketplace.md |
| 70 | MEV reduction must list non-mitigated attacks | P2 | WP §6 (Part I MEV Reduction), WP §6.5 (Part II) | actionable | append explicit `Out of scope` subsection enumerating: proposer inclusion/censorship, private orderflow, JIT MEV |

---

## A. Per-lane fee multipliers (numerical values)

### [68] §11.5 / §25.5 Per-lane fee multipliers unspecified          (P2, status: actionable)

- **Reviewer source**     : `Whitepaper-Sections-for-Reconsideration.md` §11.5/§25.5 (MEDIUM); `design-review_findings.md` item [68]
- **Reviewer's "current"**: "Lane allocation (System 5 / Timer 20 / Runner 25 / User 50) matches CIP-3; per-lane fee multipliers referenced but not specified"
- **Reviewer's proposal** : "Either commit to genesis multipliers (e.g., 1.0× / 0.8× / 1.0× / 1.0×) or mark as Tier-0 governance-tunable with rationale"
- **Actual current state**:
  - WP §6 "Dedicated Lanes" — Part I prose (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:395`): "Each lane has independent fee multipliers applied to the global basefees." No numerical values.
  - WP §6.3 — Part II normative version (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:626`): "Each lane has independent fee multipliers applied to the global cycle/cell basefees" — same wording, same omission.
  - WP §17.9 "Reserved Capacity (Execution Lanes)" (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:1010-1023`): table lists cycle budgets (Timer 2M, Runner 2.5M, System 0.5M, User 5M) but no fee-multiplier column.
  - CIP-3 §2.2.3 (`cip-3-fee-model.md:107-116`): "The block cycle budget is partitioned into reserved lanes …" with a 4-row table; no multiplier column.
  - WP §13 Parameters (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:783-785`): lane capacity percentages enumerated; no lane-multiplier parameters.
  - **Section-numbering note:** the reviewer's "§11.5 / §25.5" maps to the current v2 WP's "Dedicated Lanes" subsection of §6 (Part I) and §6.3 (Part II). The renumbering happened during the v2 reorganisation; cross-references in the analysis ledger should track the current numbering.
- **Verification**        : ✅ still accurate — three documents reference per-lane multipliers, none specify values.
- **Recommendation**      : [WP §6 / §17.9 / §13 edit + CIP-3 §2.2.3 edit]
- **Specific change**     :
  1. **WP §6.3** (Part II normative) — extend the dedicated-lanes table with a `Fee Multiplier` column:

     ```
     | Lane    | Reserved Capacity | Priority | Fee Multiplier | Contents                |
     | System  | 5%                | Highest  | 1.0×           | Validator updates, gov. |
     | Timer   | 20%               | High     | 1.0×           | Scheduled timer execs   |
     | Runner  | 25%               | High     | 1.0×           | Runner job results …    |
     | User    | 50%               | Normal   | 1.0×           | User transactions       |
     ```

     Add one sentence beneath: "Effective per-tx basefee = global basefee × lane multiplier. All four multipliers are pinned at 1.0× at genesis (no subsidy) and are Tier-0 governance-tunable." Mirror this change in the Part I prose (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:395`).
  2. **WP §17.9** — add the same `Fee Multiplier` column to the §17.9 table at line 1013.
  3. **WP §13** (Parameters) — add a new sub-bullet under **Dedicated Lanes** (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:783-785`): "`lane_fee_multiplier_system = 1.0`; `lane_fee_multiplier_timer = 1.0`; `lane_fee_multiplier_runner = 1.0`; `lane_fee_multiplier_user = 1.0`; all Tier-0 governance-tunable per CIP-12."
  4. **CIP-3 §2.2.3** — extend the lane table with a `Fee Multiplier` column matching the WP, and add a sentence below: "Lane multipliers default to 1.0× at genesis. Governance may differentiate lanes (e.g., subsidise the Timer lane to bootstrap autonomous-actor adoption); changes follow Tier-0 procedure per CIP-12."
- **Rationale**           :
  - The reviewer's example `0.8× Timer subsidy` is a Concept-B holdover from the Phase-3 Timer/GBA mechanism selection. The Phase-3 hybrid decision (recorded in `02-timer-gba.md` and `concept-selection_findings.md:93`) explicitly pinned the Timer-lane multiplier at 1.0× because EIP-1559 + per-actor fairness weight already provides the bootstrapping signal the 0.8× subsidy was meant to provide; the 20% revenue cost of a subsidised Timer lane was the decisive close-call factor.
  - Pinning all four at 1.0× preserves linearity of the dual-basefee market (CIP-3 §2.4) at launch. Any lane-differentiation decision can then be made post-launch on real utilisation data rather than guessed at genesis.
  - Marking the multipliers as Tier-0 (Operational Parameters per CIP-12 §5.1) keeps adjustment cost low if a subsidy or surcharge is later wanted.
- **Open questions**      :
  - Should the System-lane multiplier be lower than 1.0× (e.g., 0.5×) on the theory that system transactions are protocol overhead and shouldn't be revenue-extracted from? Current recommendation: no — System lane is 5% of capacity, the revenue impact is negligible, and a multiplier <1.0× creates an arbitrage incentive to misclassify transactions. Defer to post-launch.
  - Multiplier semantics: multiply the basefee only (cleanest — basefee burns scale, tips don't) or the entire per-tx cost (basefee + tip)? Recommend basefee only, which is what "applied to the global basefees" already implies. Document this explicitly in the WP edit.

---

## B. Validator commission model (does it exist?)

### [32] Validator commission model unspecified          (P2, status: actionable)

- **Reviewer source**     : `Design-review.md` Gap G12; `design-review_findings.md` item [32]
- **Reviewer's "current"**: "Can validators charge users additional per-block fees, or only receive tips?"
- **Reviewer's proposal** : "Specify validator commission model"
- **Actual current state**:
  - WP §6 Part I (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:365`): "Block rewards (from inflation) are distributed proportionally to stake. Proposers additionally receive transaction tips. Staking is self-bonded only; delegation is deferred to v2."
  - WP §8.4 fee-sinks table (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:709-712`): "Cycle & Cell tips → 100% → Proposer / validators". No row for any other validator revenue stream.
  - WP §13 Parameters (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:779-781`): consensus parameters listed; no `validator_commission_*` field.
  - CIP-12 governance — no mention of validator commission as a governance parameter.
  - CIP-13 runner-delegation defines `commission_bps` but explicitly for runner delegators, not validators (validator delegation is v2-deferred per WP §6 line 365 above).
- **Verification**        : ✅ accurate — the reviewer is correct that the validator revenue model is implicit. The WP states "tips + inflation" in two separate places but never says "and nothing else"; a downstream reader could reasonably wonder whether a per-block "validator fee" mechanism is planned (it is not).
- **Recommendation**      : [WP §6 + WP §13 + WP §8.4 edits — minimal, declarative]
- **Specific change**     :
  1. **WP §6 Part I** — replace `2026-03-21_cowboy-technical-whitepaper-revised-v2.md:365` with: "Block rewards (from inflation per §8.2) are distributed proportionally to stake. Proposers additionally receive 100% of cycle/cell tips on blocks they finalize. No per-tx validator commission or surcharge is charged to users beyond tips. Staking is self-bonded only; delegation is deferred to v2."
  2. **WP §13** — add under **Consensus** (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:779-781`): "`validator_commission_model = tips_only` (proposers receive 100% of tips on blocks they finalize plus stake-proportional inflation; no separate user-facing commission)."
  3. **WP §8.4** — add a note line beneath the fee-sinks table at line 712: "Validators receive no other revenue stream from users; their entire user-derived income is the `tips` line above. Inflation rewards (§8.2) accrue independently and are stake-proportional."
- **Rationale**           :
  - The reviewer's gap is real but the answer is "no commission" — not "we forgot to design it". Stating this explicitly closes the gap with zero mechanism change.
  - This matches the EIP-1559 mental model: basefee burned, tips to proposer. Adding a separate commission would either double-bill users or create misaligned incentives; the simplest defensible position is no commission.
  - Naming `validator_commission_model = tips_only` as a parameter lets governance later switch models (e.g., to introduce a fixed user-paid commission) under CIP-12 Tier-3 (Consensus/Economics).
- **Open questions**      :
  - Should validators be permitted to *voluntarily* set a commission floor (i.e., refuse blocks below a tip-per-cycle threshold)? They can already do this off-protocol by simply not proposing those transactions; no spec change needed. Mention this in the rationale of the WP §6 edit but don't formalise it.
  - When validator delegation arrives in v2, the question reopens: validators will need a commission analogous to runners' `commission_bps`. Recommendation: mirror the CIP-13 model 1:1 when v2 delegation lands; do not pre-spec it now.

---

## C. Runner commission bounds — see 03-runner-marketplace.md

### [33] Runner commission bounds          (P2, status: resolved — cross-referenced)

- **Reviewer source**     : `Design-review.md` Gap G13; `design-review_findings.md` item [33]
- **Reviewer's recommendation** : "Specify `commission_bps` bounds (likely 0–100% or with a floor)"
- **Actual current state**:
  - CIP-13 §3.3 validation rule (`cip-13-runner-delegation.md:208`): "`MIN_COMMISSION_BPS <= commission_bps <= MAX_COMMISSION_BPS`".
  - CIP-13 constants table (`cip-13-runner-delegation.md:616-617`): `MIN_COMMISSION_BPS = 500 (5%)`; `MAX_COMMISSION_BPS = 10000 (100%)`.
  - CIP-13 rationale (`cip-13-runner-delegation.md:768`): "The `MIN_COMMISSION_BPS` floor prevents a race-to-zero that would harm runner sustainability."
- **Verification**        : ❌ stale — the reviewer's claim is no longer accurate. CIP-13 (current revision) already specifies both bounds and rationale.
- **Recommendation**      : [no change here — see 03-runner-marketplace.md for full treatment]
- **Cross-reference**     : `03-runner-marketplace.md` item [33] owns this; this file lists it only to keep the design-review item index complete. The 5%–100% bracket exactly matches `concept-selection_findings.md:194-195` Concept-B hybrid (`hard cap commission_bps ≤ 3000` / `soft floor ≥ 500`) — note the *hard cap* is currently 100% in CIP-13, not the 30% from concept-selection. That divergence is a separate open question owned by 03-runner-marketplace.md.

---

## D. MEV reduction scope — explicit "out of scope" list

### [70] §11.6 / §25.6 MEV reduction scope must explicitly list what it does NOT prevent          (P2, status: actionable)

- **Reviewer source**     : `Whitepaper-Sections-for-Reconsideration.md` §11.6 / §25.6 (MEDIUM); `design-review_findings.md` item [70]
- **Reviewer's "current"**: "Whitepaper lists MEV mitigation measures but not non-mitigated attacks"
- **Reviewer's proposal** : "Append explicit 'Out of scope' subsection to §11.6 / §25.6"
- **Actual current state**:
  - WP §6 Part I "MEV Reduction" (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:397-399`): four-mechanism prose ending with: "This does not prevent proposer inclusion/censorship or private orderflow MEV."
  - WP §6.5 Part II "MEV Reduction (Limitations Apply)" (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:634-658`): expanded prose covering rotation, VRF ordering, fast finality, dedicated lanes, no encrypted mempool. Contains one inline note at `:648`: "Note: This does not prevent proposer inclusion/censorship or private orderflow MEV." JIT MEV against predictable actor logic is not mentioned anywhere.
  - **Section-numbering note:** the reviewer's "§11.6 / §25.6" maps to the current WP's "MEV Reduction" subsection of §6 (Part I) and §6.5 (Part II) after the v2 reorganisation.
- **Verification**        : ⚠ partially — one disclaimer line exists in each Part, but it is short, buried, and missing JIT MEV. The reviewer is right that an explicit `Out of scope` block is needed.
- **Recommendation**      : [WP §6.5 edit (primary) + WP §6 edit (mirror)]
- **Specific change**     :
  1. **WP §6.5** (Part II) — after the existing "No encrypted mempool" paragraph at `2026-03-21_cowboy-technical-whitepaper-revised-v2.md:658`, append a new bolded subsection:

     ```
     **Out of scope (not mitigated by this design).** Cowboy's MEV strategy does NOT
     prevent the following classes of extraction; users and developers should design
     defensively where these matter:

     - **Single-block proposer inclusion / censorship.** A proposer can choose to
       omit a specific user's transaction from the block it proposes. VRF rotation
       limits the damage to one block (~1 second); the same transaction will be
       eligible for inclusion in the next block under a different proposer.
       Sustained per-validator censorship is detectable post-hoc via the public
       mempool but is not prevented in-protocol in v1.
     - **Private orderflow MEV.** Users routing transactions through private
       relays or off-protocol RFQ systems forgo the public-mempool ordering
       guarantees. The protocol cannot mitigate MEV in flows it does not see.
     - **JIT (just-in-time) MEV against predictable actor logic.** An attacker
       who can predict an actor's behaviour (e.g., a deterministic AMM with a
       publicly known curve) can construct a same-block back-running or
       sandwich-equivalent transaction. VRF ordering randomises position within
       the block but does not prevent the same set of transactions from being
       co-included. Mitigation is at the actor/SDK layer (commit-reveal patterns,
       order-flow auctions in actor logic, slippage caps).
     ```

  2. **WP §6 Part I** — replace the short disclaimer line at `2026-03-21_cowboy-technical-whitepaper-revised-v2.md:399` with: "This does not prevent (a) single-block proposer inclusion/censorship, (b) private orderflow MEV, or (c) JIT MEV against predictable actor logic — see §6.5 for the explicit out-of-scope list."
- **Rationale**           :
  - The disclaimer line already in the WP is correct but easy to miss; the reviewer's request is fundamentally a transparency/UX one and the cost is one paragraph.
  - Naming JIT MEV explicitly is the highest-value addition — Cowboy's actor model makes deterministic actor logic the norm, so JIT-style attacks against AMMs and predictable schedulers are a foreseeable threat. Pointing developers at the SDK-layer mitigation (commit-reveal, slippage caps) is the right place to put the burden; the protocol cannot.
  - The recommendation deliberately does not introduce any new mechanism — it formalises and expands an existing one-line disclaimer.
- **Open questions**      :
  - Should "long-range MEV" (e.g., chain-rollback attacks past finality) be listed? Recommend no — Simplex finality is already discussed in §6.1 and treating it as in-scope here would be confusing. The MEV section should cover transaction-ordering and inclusion attacks specifically.
  - Should there be a forward link to a hypothetical CIP-X on private orderflow / order-flow auctions? Only if such a CIP is drafted; today the entry would dangle.

---

## E. Decision-register entries

These are the decisions the analysis recommends recording in the project decision register before any WP/CIP edit lands.

1. **Lane fee multipliers**: pin at **1.0× across all 4 lanes (System / Timer / Runner / User)** at launch (no subsidy, no surcharge). Reviewer's example `0.8× Timer subsidy` is rejected as a Concept-B holdover; the Phase-3 hybrid pins Timer at 1.0× (already in `02-timer-gba.md`). Declare the multiplier vector Tier-0 governance-tunable per CIP-12.
2. **Validator commission model**: pin to **`tips_only`** — validators receive 100% of tips on blocks they finalize plus stake-proportional inflation. No separate user-facing commission. Add as named parameter in WP §13 so governance can switch model later under Tier-3 if v2 delegation introduces one.
3. **Runner commission bounds**: defer to 03-runner-marketplace.md. Note the divergence between current CIP-13 (`MAX_COMMISSION_BPS = 10000`, i.e. 100%) and the concept-selection Phase-3 hybrid (`commission_bps ≤ 3000`, i.e. 30%) — that resolution is owned upstream.
4. **MEV scope**: the WP's existing one-line disclaimer is upgraded to an explicit three-class `Out of scope` subsection in WP §6.5, with the headline `Single-block proposer inclusion/censorship`, `Private orderflow MEV`, and `JIT MEV against predictable actor logic`. No mechanism change; transparency only.

---

## F. WP / CIP edits proposed (deferred to next pass)

| Touch | Section | Action | Source item |
|---|---|---|---|
| WP §6 Part I (line 395) | Dedicated Lanes | Add `Fee Multiplier` column to the lanes table; pin 1.0× | 68 |
| WP §6.3 Part II (line 615-620) | Dedicated Lanes (normative) | Add `Fee Multiplier` column; pin 1.0× | 68 |
| WP §17.9 (line 1013) | Reserved Capacity table | Add `Fee Multiplier` column; pin 1.0× | 68 |
| WP §13 Lanes block (line 783-785) | Parameters | Add four `lane_fee_multiplier_*` parameters at 1.0× | 68 |
| WP §6 Part I (line 365) | Staking and Rewards | Replace prose to make "tips + inflation only, no commission" explicit | 32 |
| WP §13 Consensus block (line 779-781) | Parameters | Add `validator_commission_model = tips_only` | 32 |
| WP §8.4 (line 707-712) | Fee sinks | Add note clarifying no other validator revenue from users | 32 |
| WP §6.5 (line 658) | MEV Reduction | Append `Out of scope` subsection enumerating 3 attack classes | 70 |
| WP §6 Part I (line 399) | MEV Reduction prose | Expand disclaimer to list 3 attack classes + forward link to §6.5 | 70 |
| CIP-3 §2.2.3 (line 109-116) | Execution Lanes | Add `Fee Multiplier` column matching WP; note Tier-0 tunable | 68 |

All four items are P2; the four-document fee-multiplier edit (#68) is the largest single change and should be batched. The MEV edit (#70) and the validator-commission edit (#32) are self-contained and can land independently.
