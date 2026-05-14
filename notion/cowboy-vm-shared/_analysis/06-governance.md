# 06 — Governance, Security Council, Bridges, Delegator Voice

## TL;DR

- **Security Council sunset (items #46, #61) is a policy decision, not a spec gap.** CIP-12 §3.2 currently frames the Council as "permanent" and removable only via Tier 4. The reviewer's "conditional sunset" framing is sound (launch strong, ratchet down as the network matures) — but the trigger thresholds (validator-count `N`, staked-value `V`) require a values call. Recommend amending CIP-12 §3.2 with a conditional-sunset clause **after** the decision register resolves N and V; suggested defaults `N = 50` active validators, `V = $50M` at oracle TWAP.
- **Bridge selection (items #16, #45, #52) is the largest open governance question.** WP §16.2 and CIP-25 §1.4 both correctly defer backend choice to governance, but launching with both governance and bridge unspecified means the first big vote also bears the largest security decision. **Recommend option (b): launch with EVM bridging disabled** until governance elects a backend post-mainnet. Flag as decision register entry.
- **Delegator partial voice (items #21, #47, #62) is a deferred CIP-13 v2 amendment.** CIP-13 §6.1 explicitly punts to a future CIP, and §9.6 names it as future work. Recommend a CIP-13 v2 amendment granting **25% pro-rata weight on Tier-2 proposals tagged `runner-marketplace-parameter`** only; zero weight elsewhere preserves bicameral safety. Items #18 / #51 (tier drift) are already RESOLVED in WP-v2 — cross-ref to 08-doc-fixes.md. Items #2 / #39 are tokenomics — cross-ref to 05-tokenomics-inflation.md.

## Items index

| # | Title | Priority | Touches | Status | Action |
|---|-------|----------|---------|--------|--------|
| 16 | Bridge trust concentrates risk | P1 | WP §16.2, CIP-25 §1.4 | policy-decision | decision register entry; recommend option (b) |
| 18 | WP governance tier drift vs CIP-12 | P1 | WP §11 | resolved | cross-ref 08-doc-fixes.md |
| 21 | Delegators have zero governance voice | P2 | CIP-13 §6.1, CIP-12 §6 | actionable | CIP-13 v2 amendment (25% weight, runner-param only) |
| 37 | Weak staking governance turnout | P2 | CIP-12 §10 | actionable | doc-only: civic-duty framing + turnout publication |
| 38 | Tier 2 quorum 15% whale-capture | P2 | CIP-12 §5.2 | actionable | keep value, add risk disclosure to CIP-12 commentary |
| 39 | Validator APR unspecified | P1 | WP §8.2/§13 | cross-ref | see 05-tokenomics-inflation.md |
| 45 | Bridge pre-mainnet decision | P1 | WP §16.2 | policy-decision | decision register; option (b) recommended |
| 46 | Security Council conditional sunset | P2 | CIP-12 §3.2 | policy-decision | decision register entry + CIP-12 amendment |
| 47 | Runner delegators 25% on runner-param proposals | P2 | CIP-13 §6.1, CIP-12 §6 | actionable | CIP-13 v2 amendment |
| 51 | §11 governance tier sync to CIP-12 | P1 | WP §11 | resolved | cross-ref 08-doc-fixes.md |
| 52 | §16 / §30 bridge selection pre-mainnet | P1 | WP §16.2 | policy-decision | duplicate of #45 / #16 |
| 61 | §11.1–§11.2 Council conditional sunset | P2 | CIP-12 §3.2 | policy-decision | duplicate of #46 |
| 62 | §11.1–§11.2 delegator 25% weight | P2 | CIP-13 §6.1 | actionable | duplicate of #47 |
| 2  | Treasury 1% removal | P2 | WP §8.3, §13 | cross-ref | see 05-tokenomics-inflation.md |

---

## A. Security Council scope & sunset (items #46, #61)

### [46] / [61] Security Council should have conditional-sunset path tied to network maturity          (P2, status: policy-decision)

- **Reviewer source**     : `Design-Review-Summary-Cowboy-Input.md` §2.6; `Whitepaper-Sections-for-Reconsideration.md` HIGH §11.1–11.2/25; `design-review_findings.md` items [46] and [61]
- **Reviewer's "current"**: "Security Council is 'permanent, reduce only via Tier 4'" — at launch this is prudent; "at year 5 with healthy validator set it may become a political fixture"
- **Reviewer's proposal** : "Replace 'permanent' framing with conditional-sunset clause, e.g., 'Council scope reduces by one named power per year once {validator_count ≥ N AND staked_value ≥ V} for two consecutive epochs'" — N and V left as parameters
- **Actual current state**:
  - CIP-12 §1 (`cip-12-governance.md:21`): "A permanent **Security Council** 7-of-9 multisig that can cancel queued proposals, trigger a fast-track path during emergencies, and circuit-break a system actor."
  - CIP-12 §2 motivation (`cip-12-governance.md:36`): "A **permanent** emergency authority is a feature, not training wheels. Removal of that authority should itself be a governance decision, not a calendar event."
  - CIP-12 §2 (`cip-12-governance.md:39`): "the Security Council is a permanent but removable-by-Tier-4 emergency brake."
  - CIP-12 §10 rationale (`cip-12-governance.md:501`): "**Why a permanent Security Council?** The Council can be removed by the community via Tier 4, so it is not irrevocable. … The community opts in to removing its own safety net when ready — not on an arbitrary calendar date."
- **Verification**        : ✅ accurate — the spec is unambiguously "permanent, removable only via Tier 4." The reviewer is not pointing at a bug; they're proposing a design change.
- **Recommendation**      : [decision register entry; conditional CIP-12 §3.2 amendment]
- **Specific change**     : *If* the policy decision is to adopt conditional sunset, amend CIP-12 §3.2 to add (after the existing "only Tier 4 meta-governance can" line): "Council *scope* (named powers in §3.2.1–§3.2.3) automatically reduces by one named power per `sunset_epoch_length` (Tier 0 param, default 1 year) once the network has sustained `validator_count ≥ sunset_validator_threshold` **and** `total_staked_value_usd ≥ sunset_staked_value_threshold` for two consecutive epochs, as measured by the oracle TWAP defined in CIP-12 §X (TBD). Order of reduction: (1) Cancellation authority; (2) Fast-track endorsement; (3) Circuit-breaker pause. A Tier 4 vote may override the schedule (slow it, halt it, or restart it)." Suggested defaults: `sunset_validator_threshold = 50`, `sunset_staked_value_threshold = $50M`.
- **Rationale**           : Reviewer's framing is sound; the cost is a parameter table and an ordering decision. The spec already permits Tier 4 removal — what's missing is an *automatic* ratchet that doesn't require coordinating a Tier 4 vote during normal operation. Order matters: pause is the most defensive power and should sunset last; cancellation is the most disruptive and should sunset first. The named thresholds are the only piece that genuinely needs a values call.
- **Open questions**      : (1) Validator count `N` — is 50 the right floor? Ethereum-like systems consider 50 a low number, but Cowboy is a young L1 and 50 active is meaningful. (2) Staked-value `V` — denominating in USD requires an oracle (CIP-12 currently has no USD oracle dependency; this is a new coupling). (3) Should `total_staked_value_usd` instead be `staked_ratio_of_supply ≥ X%`, which avoids the oracle dependency? (4) What is `sunset_epoch_length` calibration — 1 year per power means full sunset in 3 years; some reviewers would prefer slower.

---

## B. Governance tier drift (items #18, #51) — RESOLVED

These items flagged WP §11 / §25.3 carrying outdated tier values (Tier 0 = 10% quorum, Tier 4 = 33% / >75%) versus CIP-12's authoritative values (Tier 0 = 5%, Tier 4 = 20% / >66%). WP-v2 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:742-746`) has since been pruned: the WP §11 governance block no longer reproduces the tier table at all — it carries only the "Foundation 5-of-9 multisig sunsets after ~12 months to token-weighted on-chain governance" / "Standard 7 days; emergency fast-track 6 hours" summary. **Cross-reference to `08-doc-fixes.md`** for the residual editorial note: the WP §11 summary should be updated to reference CIP-12 as the authoritative source for tier parameters, and to drop the "5-of-9 multisig sunsets after ~12 months" line, which contradicts CIP-12's permanent-Council framing. No spec change required.

---

## C. Bridge selection (items #16, #45, #52)

### [16] / [45] / [52] Bridge trust assumption concentrates risk; pre-mainnet decision required          (P1, status: policy-decision)

- **Reviewer source**     : `Design-review.md` §7.2 item 7 and §10.7; `Design-Review-Summary-Cowboy-Input.md` §2.7; `Whitepaper-Sections-for-Reconsideration.md` CRITICAL §16/30; `design-review_findings.md` items [16], [45], [52]
- **Reviewer's "current"**: "Protocol explicitly outsources bridge validation to a third party. Whatever security assumptions that bridge makes become Cowboy's assumptions for any value that crosses over. … the whitepaper defers the decision entirely to governance"
- **Reviewer's proposal** : Three options offered, with explicit ranking: "(a) Pre-select bridge via core team with retirement escape hatch + named candidates + security-bound. (b) Launch with bridging disabled, treat as post-launch feature gated on governance-elected bridge. NOT 'both unspecified' — the current implicit path is worst of both worlds."
- **Actual current state**:
  - WP §16.2 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:838-845`): "Cowboy relies on third‑party bridge infrastructure for asset transfers and cross‑chain message passing between Cowboy and Ethereum. … Bridge selection and integration are determined by governance. The protocol does not implement its own bridge validator set."
  - CIP-25 §1.4 (`cip-25-cross-chain-architecture.md:168`): "This CIP standardizes the **interface contract** any L1 backend MUST satisfy (`IChainAnchor`, §1.5). It does NOT mandate a specific backend protocol-wide. … which backend is deployed for which `(source_chain, destination_chain)` pair is a governance decision — including the runner-attested committee backend described in §1.4 / §1.6 (which Tony's team's existing outbound Cowboy→Ethereum withdrawal bridge already runs in production)."
  - CIP-25 §B.5 specifies committee-backend failure modes (`cip-25-cross-chain-architecture.md:201-204`) — runner-majority collusion defenses, reorg handling, stale-commitment GC — and includes a `min_confirmations = 32 slots` default and `stake ≥ k × max_attestable_value` with `k = 10`.
- **Verification**        : ✅ accurate — neither WP §16.2 nor CIP-25 commits to a backend per chain-pair at mainnet. The "first governance vote also bears the largest security decision" critique is correct.
- **Recommendation**      : [decision register entry; recommend option (b) launch with bridging disabled]
- **Specific change**     : *If* option (b) is selected: amend WP §16.2 to state explicitly that "Cowboy launches with no live EVM↔Cowboy asset bridge or generic message bridge enabled. CIP-25 backends (`IChainAnchor` implementations) are deployed only after governance elects a backend for each `(source_chain, destination_chain)` pair via a Tier 2 (treasury / disbursement-class) or Tier 1 (registry) proposal." Wrap with: "The runner-attested committee backend described in CIP-25 §1.4 / §1.6 is the reference implementation, but its deployment requires the same governance election as any third-party backend." *If* option (a) is selected instead: add a "Provisional Bridge Selection" subsection naming the bridge, its security model, its TVL cap (e.g., $5M during provisional period), and the trigger for Tier 2 retirement (e.g., any incident report meeting a defined materiality bar).
- **Rationale**           : Option (c) — current path — is "first big vote also bears largest security decision," which the reviewer correctly identifies as worst-of-both-worlds. Option (a) (core-team pre-select) requires the core team to pick winners, biases toward whatever bridge has the best existing relationship rather than the best security, and concentrates reputational damage on the team if the bridge fails. Option (b) (launch disabled) is the slower path but is honest about what the protocol does at TGE and avoids the bootstrap-governance dilemma. The committee backend defenses in CIP-25 §B.5 are sound but expensive to deploy; gating on governance election is appropriate. Tony's team's existing outbound bridge runs the committee pattern and would be the natural reference implementation for the governance vote.
- **Open questions**      : (1) If option (b), what is the Cowboy→Ethereum withdrawal path at launch — does Tony's team's existing committee-backed bridge run as a permissioned actor (governance-recognized but not blessed) before its formal election, or is even outbound disabled? (2) If option (a), what is the materiality bar for Tier 2 retirement, and what is the TVL cap during the provisional period? (3) Either way: does the EVM stablecoin payment facilitator in CIP-18 r2 §12 ("inbound EVM-to-Cowboy bridge for ERC-20 stablecoin payments") gate on the same governance decision, or does it have its own narrower path? (4) Decision register: which option does the team pick? This is the single highest-stakes governance call in this analysis.

---

## D. Delegator governance voice (items #21, #47, #62)

### [21] / [47] / [62] Runner delegators have zero governance vote weight          (P2, status: actionable)

- **Reviewer source**     : `Design-review.md` Section 6 Runner Delegators row and §10.6; `Design-Review-Summary-Cowboy-Input.md` §2.6; `design-review_findings.md` items [21], [47], [62]
- **Reviewer's "current"**: "Delegators have no governance voice so they cannot influence parameters that affect their returns (burn percentage, payout split, runner committee sizes). This disempowers the most capital-flexible group" (Design-review.md:174)
- **Reviewer's proposal** : "Give delegators partial vote weight (e.g., 25%) on runner-parameter-specific proposals only, deferred to CIP-13 §9.6 follow-up" (item [47]); "a natural compromise … is worth exploring in Phase 2" (Design-review.md §10.6 line 384)
- **Actual current state**:
  - CIP-13 §6.1 (`cip-13-runner-delegation.md:642`): "For v1 of this CIP, runner-delegated CBY has **zero governance vote weight**. … This resolves cleanly against CIP-12's 'staked CBY has weight, unstaked has zero' rule: runner-delegated CBY is neither validator-staked nor unstaked; it simply occupies a third category with no voting rights in v1."
  - CIP-13 §6.1 (`cip-13-runner-delegation.md:644`): "A future CIP MAY extend CIP-12 to grant vote weight to runner-delegated stake (voted directly by the delegator, not inherited by the runner). That extension is deliberately out of scope here to keep the governance surface stable."
  - CIP-13 §9.6 (`cip-13-runner-delegation.md:762`): "A future CIP may extend CIP-12 to grant vote weight to runner-delegated stake (voted directly by the delegator, not inherited by the runner), after live operation of CIP-13 clarifies whether such weight is desired and how to weigh it against validator-delegated stake."
  - CIP-12 §6.2 (`cip-12-governance.md:207`): "**Weight source:** CBY staked to validators (self-stake and delegated stake both count). Unstaked CBY held in wallets has zero weight. This deliberately forces participation through the staking system."
- **Verification**        : ✅ accurate — runner-delegated CBY has zero weight today, and CIP-13 explicitly names this as deferred. Reviewer's framing is correct and aligns with the spec's own future-work pointer.
- **Recommendation**      : [CIP-13 v2 amendment]
- **Specific change**     : Amend CIP-13 §6.1 to add v2 paragraph: "Runner-delegated CBY carries **25% pro-rata vote weight** on Tier-2 proposals tagged `runner-marketplace-parameter` (defined in CIP-12 §X via a new proposal-tag field). For all other proposal tiers and tags — consensus-layer (Tier 0/1/3/4), constitutional (Tier 4), treasury non-runner-marketplace (Tier 2), or any untagged Tier 2 — runner-delegated CBY retains zero weight. The 25% factor applies to the *delegator's* attributed stake, voted directly by the delegator address (never inherited by the runner). The proposal-tag is set by the submitter at proposal time and verified by `0x09` against an allowlist maintained by Tier 0 governance." Add a corresponding CIP-12 §6.X subsection defining the `runner-marketplace-parameter` tag (covers: `runner_burn_pct`, `runner_payout_pct`, `runner_treasury_pct`, `dispute_window_blocks`, committee `M`/`N`, `STAKE_JOB_MULTIPLIER`, `MIN_STAKE`, etc.).
- **Rationale**           : Reviewer's 25% figure is a defensible starting point — high enough to be a meaningful voice on parameters that directly affect delegator yield, low enough that validator-chamber and bicameral-AND safety dominate. Scoping to *runner-marketplace-parameter* Tier-2 proposals only is the load-bearing restriction: it preserves the principle that consensus-layer and constitutional decisions stay with validators + validator-delegated stake, while giving delegators voice on the specific economic levers that affect them. Cross-link to `03-runner-marketplace.md` for the parameter list. Deferring to CIP-13 v2 is consistent with CIP-13's own §9.6 framing.
- **Open questions**      : (1) Should the 25% weight aggregate across multiple runners a delegator delegates to (sum across all `Active` tranches), or apply per-runner (each tranche votes independently)? Recommend sum across all `Active` tranches for the delegator address. (2) Do `Unbonding` tranches count, mirroring CIP-12 §6.2's "still counts at pre-unbond weight"? Recommend yes, for symmetry. (3) The proposal-tag mechanism is new infrastructure; does it require its own CIP-12 amendment for the `params` schema, or can it live in CIP-13 v2 alone? Recommend co-amendment of CIP-12. (4) Should the 25% be itself governance-tunable (Tier 0) or constitutional (Tier 4)? Recommend Tier 0 with a soft cap (e.g., max 50%) enforced by CIP-12 validation.

---

## E. Staking participation / whale capture (items #37, #38)

### [37] Staking governance participation is structurally weak          (P2, status: defer-to-sim)

- **Reviewer source**     : `Design-review.md` Section 6 Staked-CBY Voters row; `design-review_findings.md` item [37]
- **Reviewer's "current"**: "Staking yields are unspecified; governance participation is purely voluntary civic duty. History across Cosmos, Compound, Uniswap shows this leads to <5% effective turnout and whale dominance"
- **Reviewer's proposal** : "(Flags risk; note that Tier 2 requires 15% quorum which is better than most DAOs but still crossable by single large holder)" — no specific fix
- **Actual current state**:
  - CIP-12 §5.2 (`cip-12-governance.md:138-142`): Tier 0 stake quorum 5% / Tier 1 10% / Tier 2 15% / Tier 3 15% / Tier 4 20%. No yield-for-voting incentive; participation is pure civic duty.
  - CIP-12 §6.5 (`cip-12-governance.md:251-276`): participation-triggered extension exists — if stake participation falls below 60% of the tier quorum, voting extends up to 3 times. After the cap the tally finalizes against whoever participated.
  - CIP-12 §10 rationale (`cip-12-governance.md:507`): "**Why staked-only vote weight?** … Requiring stake aligns voting power with long-term interest." No commentary on expected turnout or whale-capture risk.
- **Verification**        : ✅ accurate — turnout is structurally voluntary, no yield-for-voting. The extension mechanism mitigates *timing* attacks but does not solve baseline low turnout.
- **Recommendation**      : [doc-only addition to CIP-12 §10; commit to turnout publication]
- **Specific change**     : Add to CIP-12 §10 rationale: "**On expected turnout.** Token governance across Cosmos, Compound, and Uniswap routinely reports <10% effective turnout. Cowboy's quorum thresholds (5–20%) are calibrated against this empirical baseline, and the participation-triggered voting extension (§6.5) protects against timing-based suppression. The protocol explicitly does **not** offer a yield-for-voting incentive, on the grounds that paying for participation produces noise rather than signal. Realized turnout will be published in the official portal at every proposal finalization, and the Foundation commits to a public quarterly governance-health report for the first 24 months post-TGE."
- **Rationale**           : Pure documentation. The reviewer's structural critique is real but the alternative (yield-for-voting) is worse: it produces low-quality signal and creates a perverse "vote-for-pay" market. The honest answer is that participation will be low, the tier quorums are set with that expectation, and transparency is the mitigation.
- **Open questions**      : (1) Should the Foundation commit on-chain to the quarterly governance-health report (e.g., a `report_ref` parameter that auto-emits a placeholder), or is the commitment off-chain? (2) Does the Watchtower (CIP-7) have a natural role here as a turnout-aggregation feed?

### [38] Governance low turnout enables whale capture at Tier 2          (P2, status: actionable)

- **Reviewer source**     : `Design-review.md` Section 6 Staked-CBY Voters row; `design-review_findings.md` item [38]
- **Reviewer's "current"**: "Tier 2 treasury disbursements need 15% quorum and >55% approval per CIP-12 (2026-04-09), which is *better* than most DAOs but still crossable by a single large holder if not all holders vote"
- **Reviewer's proposal** : "(Structural concern; mitigation via flash-loan snapshotting exists)" — no specific quorum-raise proposed
- **Actual current state**:
  - CIP-12 §5.2 (`cip-12-governance.md:140`): Tier 2 — proposal deposit 5,000 CBY, temp check 5 days, voting 7 days, **stake quorum 15%**, stake approval **>55%**, validator majority **>50%**, timelock 7 days, no fast-track.
  - CIP-12 §6.2 (`cip-12-governance.md:209`): "earlier unstakers who are still in the 7-day unbonding queue at the snapshot **still count** for the full weight they had when they initiated unbonding (prevents griefing by flash-exiting mid-proposal)."
  - CIP-12 §6.2 snapshot semantics (`cip-12-governance.md:209`): "Stake weights for formal voting are frozen at `voting_snapshot_block`" — flash-loaned stake would need to be actually staked (validator stake), wait for snapshot, then vote, then endure 7-day unbond. This is the flash-loan mitigation the reviewer refers to.
- **Verification**        : ✅ accurate — a single ~15%-of-stake holder *could* meet Tier 2 quorum and >55% approval alone, provided they also pass the validator chamber (>50% validator majority). The bicameral AND-rule is the real backstop, not the stake quorum.
- **Recommendation**      : [doc-only addition to CIP-12 §10 + cross-link from §5.2]
- **Specific change**     : Add to CIP-12 §5.2 (after the tier table): "**Note on Tier 2 quorum.** The 15% stake-quorum floor on Tier 2 treasury proposals is meaningfully higher than typical DAO governance (Cosmos / Compound / Uniswap routinely operate at <5% effective participation), but it is mathematically crossable by a single holder controlling ~15% of staked CBY. The real defense at Tier 2 is the **bicameral AND-rule** (§6.1): a Tier 2 proposal must additionally pass `>50% validator majority`. A single stake-whale who does not also control half of active validators cannot pass a Tier 2 proposal unilaterally. Raising the Tier 2 quorum further (e.g., to 20% to match Tier 4) would push toward Tier-3-level friction on routine treasury disbursements and slow the legitimate-disbursement use case; the validator chamber is the appropriate brake."
- **Rationale**           : Reviewer's concern is real but the proposed remediation (raising the quorum) trades against legitimate use. The bicameral rule already makes "single whale captures Tier 2" infeasible *unless* the whale also controls the validator set, which is a much higher bar. Documenting the analysis is more valuable than raising the number.
- **Open questions**      : (1) Is the validator chamber actually independent enough from the stake chamber at launch? At low validator counts (G1 unresolved), a stake whale could plausibly *be* a validator — the bicameral defense weakens. This is partially addressed by the validator-count threshold in #46's sunset clause. (2) Should Tier 2 disbursements above a threshold (e.g., > 5% of treasury) require Tier 3 quorums? Defer to simulation; raises orthogonal questions about treasury policy.

---

## F. Treasury 1% (item #2) / Validator APR (item #39) — cross-references

### [2] Treasury 1% fee removal — cross-reference to 05-tokenomics-inflation.md

CIP-12 §3.1 places the Foundation as a passive recipient of treasury disbursements; CIP-13 §6.2 confirms `runner_percent / burn_percent / treasury_percent` is governance-tunable via CIP-12. WP §13 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:797`): "`runner_fee_burn` = 10%; `job_fee_to_treasury` = 1%; `runner_payout` = 89%". The reviewer's removal proposal (Chad-accepted) is a tokenomics-class change to the burn/payout split, not a governance-mechanism change. **Cross-reference: `05-tokenomics-inflation.md` owns the analysis** — including whether the 1% rolls into burn (raising deflationary pressure), into runner payout (raising runner yield), or is split.

### [39] Validator APR unspecified — cross-reference to 05-tokenomics-inflation.md

WP §13 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:781`): "`minimum_validator_stake` = governance-tunable" and §8.2 inflation schedule does not commit a validator-APR target. CIP-12 §11 references CIP-3 / CIP-9 / CIP-10 as parameter sources but does not itself supply a default validator APR. The reviewer's critique (governance cannot bootstrap if its prerequisites are themselves governance-defined) is correct, but this is a tokenomics genesis-default question, not a governance-mechanism question. **Cross-reference: `05-tokenomics-inflation.md` owns the analysis** — specifically the recommended genesis defaults `validator_apr_target` and `security_floor_staked_ratio` from items [48] / [50].

---

## G. Decision-register entries from this topic

Three load-bearing policy decisions and one secondary value call, surfaced for explicit team decision:

1. **Security Council sunset.** Keep current "permanent, removable only via Tier 4" framing (CIP-12 §3.2), or amend §3.2 with a conditional sunset clause that ratchets named powers down once `validator_count ≥ N` and `total_staked_value ≥ V` for two consecutive epochs? If the latter, what are N and V? Recommended starting point: `N = 50`, `V = $50M` USD at oracle TWAP — but the threshold is the actual call.
2. **Bridge selection.** Pick exactly one:
   - (a) Pre-select a specific third-party bridge via the core team with named retirement criteria and an initial TVL cap.
   - (b) Launch with EVM↔Cowboy bridging disabled; governance elects a backend (third-party or runner-attested per CIP-25) post-mainnet.
   - (c) Current path — leave the WP §16.2 / CIP-25 §1.4 deference language as-is.
   - **Recommendation: option (b).** Option (c) is the worst-of-both-worlds the reviewer correctly flags. This is the single highest-stakes call in this analysis.
3. **Delegator partial voice.** Amend CIP-13 §6.1 in v2 to grant 25% pro-rata weight on Tier-2 proposals tagged `runner-marketplace-parameter` only? Or leave CIP-13 §6.1's zero-weight v1 rule unchanged? Recommended: amend in v2.
4. **Tier 2 quorum 15%.** Keep current value (recommended) and add explicit whale-capture risk disclosure to CIP-12 §5.2 / §10, or raise to 20% to match Tier 4? Recommended: keep + disclose.

---

## H. New CIPs / amendments proposed

Pending the decisions in §G, the concrete edits this topic surfaces:

- **CIP-12 §3.2 amendment (conditional on decision #G.1):** add a Council-scope conditional-sunset clause with three-step ordering (Cancellation → Fast-track → Circuit-break) and `sunset_validator_threshold` / `sunset_staked_value_threshold` parameters. Defaults TBD by decision.
- **CIP-12 §5.2 commentary (decision #G.4):** add a "Note on Tier 2 quorum" paragraph documenting the whale-capture analysis and explaining why the bicameral rule is the appropriate defense rather than a higher quorum.
- **CIP-12 §10 amendment (item #37):** add an "On expected turnout" rationale paragraph + commitment to a quarterly governance-health report for the first 24 months.
- **CIP-13 v2 §6.1 amendment (decision #G.3):** grant runner-delegated CBY 25% pro-rata weight on Tier-2 proposals tagged `runner-marketplace-parameter`; zero weight elsewhere. Co-amendment of CIP-12 §6.X required for the proposal-tag schema and the `runner-marketplace-parameter` parameter allowlist.
- **WP §16.2 rewrite (decision #G.2):** if option (b), explicit "EVM bridging disabled at launch" stance; if option (a), name the bridge, security model, TVL cap, and Tier 2 retirement trigger.
- **(Optional) New CIP-35 "Foundational Bridge Selection"** if option (a) is chosen and a specific bridge with security model is committed; or a deferred CIP if option (b) is chosen, defining the governance election procedure for the first backend.
- **WP §11 editorial (items #18 / #51, RESOLVED via prune):** see `08-doc-fixes.md` — drop the "Foundation 5-of-9 multisig sunsets after ~12 months" line and replace with a CIP-12 forward reference.
