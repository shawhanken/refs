# 08 — Documentation Drift, Cross-References, Math Errors

## TL;DR

- **2 items resolved** — the governance-tier drift items #18 and #51 are no longer accurate: WP §11 in the current v2 WP has been reduced to a 3-line summary that no longer contradicts CIP-12. The "10% / 33% / >75%" tier numbers the reviewer flagged are gone from the WP entirely; CIP-12 §5.2 is uncontested.
- **2 items dropped** — math-error items #40 and #63 (claim: `unbonding_blocks = 7,200 ≠ 24h`) are misidentified. The current WP §13 specifies `unbonding_period = 7 days` (literal `7 days`, not `7,200 blocks`); no `7,200` constant for unbonding exists anywhere in the current v2 WP. The reviewer was likely citing an older draft or assumed default.
- **1 item actionable** — #67, the broken `(§13.1)` cross-reference in WP §16.2 line 469. §13 exists ("Parameters (Genesis Defaults)") but has no formal §13.1 subsection. Fix is editorial; repoint to `§13` (current canonical Parameters location) or `§12.1` (current DoS-limits subsection). Recommend repointing to `§12.1` — that subsection literally enumerates the transaction-limit maxima the §16.2 reject rule is checking against.
- **1 item cross-referenced** — #69 (§5.1 same-block prohibition cross-link) is owned by `02-timer-gba.md` and listed here only for completeness.

## Items index

| # | Title | Priority | Status | Action |
|---|---|---|---|---|
| 18 | Governance tier values drift (WP vs CIP-12) | P1 | resolved | mark resolved in ledger; no edit |
| 51 | §11.3 / §25.3 tier sync (duplicate of 18) | P1 | resolved | mark resolved; no edit |
| 40 | Unbonding 7,200 blocks ≠ 24h math error | P1 | dropped | claim against parameter that doesn't exist in v2 WP |
| 63 | Unbonding math (HIGH in Whitepaper-Sections doc, duplicate of 40) | P1 | dropped | same |
| 67 | Broken cross-ref `§13.1` in WP §16.2 | P3 | actionable | repoint `(§13.1)` → `(§12.1)` |
| 69 | §5.1 same-block prohibition cross-link | P3 | cross-ref → 02-timer-gba.md | n/a here |

---

### [18] Governance tier values drift (WP §11.3 / §25.3 vs CIP-12)          (P1, status: resolved)

- **Reviewer source**     : `Design-review.md` Section 9.2; `initial-questions.md` Q6 follow-up; `design-review_findings.md` item [18]
- **Reviewer's "current"**: "Whitepaper still shows Tier 0: 10% / Tier 4: 33% / >75%; CIP-12 has these at Tier 0: 5% / Tier 4: 20% / >66%"
- **Reviewer's proposal** : "Replace the §11.3 / §25.3 tier table with the CIP-12 numbers"
- **Actual current state**:
  - WP §11 "Governance & Upgrades" (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:742-745`):

    ```
    ## 11. Governance & Upgrades
    - **Model:** Foundation **5‑of‑9 multisig** sunsets after ~12 months to token‑weighted on‑chain governance.
    - **Timelocks:** Standard actions **7 days**; emergency fast‑track **6 hours**.
    - **Upgrades:** **Hot‑code upgrades** coordinated by governance.
    ```

    Three lines, no tier table, no quorum percentages, no `10%` / `33%` / `>75%` references.
  - There is no §11.3 subsection in the current v2 WP. There is no §25.3 subsection either — Part I tops out at §17 and Part II's "Delta" sections are numbered separately. The reviewer's "§11.3 / §25.3" numbering is from a pre-v2 draft.
  - CIP-12 remains authoritative for tier values, deposits, quorums, and voting windows.
- **Verification**        : ❌ stale — the conflict the reviewer flagged has already been resolved (by stripping the conflicting content from the WP rather than by updating it). CIP-12 §5.2 is uncontested.
- **Recommendation**      : [no change — already resolved]
- **Specific change**     : none required. Record the resolution in the analysis ledger so future readers don't re-open this item.
- **Rationale**           : The pre-v2 WP carried a tier table that drifted out of sync with CIP-12; the v2 WP reorganisation deleted the table and replaced §11 with a three-line forward reference. The deletion is sufficient to close the drift — the WP no longer asserts any specific tier values, so it cannot conflict with CIP-12.
- **Open questions**      :
  - Should the WP §11 three-line summary include an explicit "see CIP-12 for tier values, quorums, deposits, and voting windows" sentence? Not strictly required (the reader can infer this), but a one-line forward reference would be cheap. Defer to the editorial pass — not part of this item.
- **Resolution marker**   : `resolved-2026-05 (v2-WP-strip)` — recommend adding to the analysis ledger.

### [51] §11.3 / §25.3 Tier values must sync to CIP-12          (P1, status: resolved — duplicate of [18])

- **Reviewer source**     : `Whitepaper-Sections-for-Reconsideration.md` §11.3 (CRITICAL); `design-review_findings.md` item [51]
- **Reviewer's "current"**: identical to item [18] above — "Whitepaper: Tier 0: 10%, Tier 4: 33%, >75%; CIP-12: Tier 0: 5%, Tier 4: 20%, >66%"
- **Reviewer's proposal** : "Replace §11.3 / §25.3 tier table with CIP-12 numbers; add proposal-deposit, temperature-check, voting-window columns CIP-12 introduces"
- **Verification**        : ❌ stale — duplicate of [18]; same root claim, same resolution. The "add proposal-deposit / temperature-check / voting-window columns" recommendation is moot since no tier table exists in the v2 WP to add columns to.
- **Recommendation**      : [no change — resolved]
- **Resolution marker**   : same as [18] — `resolved-2026-05 (v2-WP-strip)`.

### [40] Unbonding period arithmetic error (7,200 blocks ≠ 24h)          (P1, status: dropped)

- **Reviewer source**     : `Design-review.md` §13 / §27 Parameters (HIGH in Whitepaper-Sections doc); `design-review_findings.md` item [40]
- **Reviewer's "current"**: "`unbonding_blocks = 7,200 (~24h)` at stated 1-second block time"
- **Reviewer's proposal** : "Either correct comment to '~2 hours' if 7,200 is intentional, or bump constant to 86,400 for ~24 hours. Pick one and reconcile with CIP-13"
- **Actual current state**:
  - WP §13 Consensus block (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:779-781`):

    ```
    `minimum_validator_stake` = governance-tunable; `epoch` = 3600 blocks (~1 h);
    `block_time` = 1 s; `finality` = ~2 s; `unbonding_period` = 7 days;
    `jail_period` = 24 h; `double_sign_slash` = 1%; `consensus_protocol` = Simplex BFT.
    ```

    The unbonding period is literally `7 days`, not a block count. `7,200` does not appear in the v2 WP anywhere as an unbonding constant.
  - Confirmation grep across the v2 WP: the only `7,200`-shaped value is `7200` blocks in the deferred-tx / cycles context, unrelated to unbonding.
  - WP §6 Part I prose (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:359`): "Withdraw (after 7‑day unbonding period)." — consistent with §13.
  - CIP-13 v2 also uses days/epochs rather than the `7,200`-block formulation.
- **Verification**        : ❌ misidentified — the current v2 WP does not contain the alleged arithmetic error. The `7,200 (~24h)` formulation the reviewer cites is not present.
- **Recommendation**      : [drop]
- **Rationale**           :
  - The reviewer was either citing an older internal draft or projecting a default assumption (a chain naming a `~24h` unbonding might plausibly compute `86,400 s / 1 block`, leading the reviewer to expect `86,400` and "find" `7,200` by reading a different table row).
  - The v2 WP expresses unbonding in human time (`7 days`), not block count. There is nothing arithmetically wrong with `7 days` — it's a direct duration and any "7 days = N blocks at 1 s/block" conversion is left to the implementation, not pre-baked into the spec.
  - If the implementation defines a block-count constant somewhere (in `node/types/src/constants.rs` or similar), that constant is a derived value and the right place to validate `block_count × block_time ≈ stated_days` is in the implementation, not the WP. That validation is out of scope for this analysis round.
- **Open questions**      :
  - Should the WP add a parenthetical block-count derivation, e.g. `unbonding_period = 7 days (≈ 604,800 blocks at 1-s block time)`? Recommend no — the derivation drifts as `block_time` is governance-tuned, and the day count is the human-meaningful figure.

### [63] §13 / §27 Unbonding blocks arithmetic error          (P1, status: dropped — duplicate of [40])

- **Reviewer source**     : `Whitepaper-Sections-for-Reconsideration.md` §13 / §27 (HIGH); `design-review_findings.md` item [63]
- **Reviewer's "current"**: identical to item [40] — "`unbonding_blocks = 7,200 (~24h)` at 1-second block time"
- **Reviewer's proposal** : same as [40] — "Either correct comment to '~2 hours' if 7,200 intentional, or bump to 86,400 blocks for 24 hours"
- **Verification**        : ❌ misidentified — duplicate of [40]; same root claim, same resolution.
- **Recommendation**      : [drop]
- **Rationale**           : same as [40]. The "§27 Parameters" reviewer-cited section number is from an older draft layout (where Part II of the WP was numbered §18-§30); in the v2 WP the equivalent content is §13 (Part I) and has no Part II Delta on this topic.

### [67] §4.4 / §16.2 Broken cross-reference to §13.1          (P3, status: actionable)

- **Reviewer source**     : `Whitepaper-Sections-for-Reconsideration.md` §4.4 / §16.2 (MEDIUM); `design-review_findings.md` item [67]
- **Reviewer's "current"**: "§16.2 cites '(§13.1)' which doesn't exist"
- **Reviewer's proposal** : "Fix cross-reference to §12.1 ('DoS limits') or §27 (parameter table)"
- **Actual current state**:
  - WP §2.2 Validity checks (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:467-469`):

    ```
    2.2 **Validity checks.**

    Nodes MUST reject a tx if: (a) limits exceed maxima (§13.1), (b) insufficient balance,
    (c) signature invalid, (d) access list invalid, or (e) payload decoding fails.
    ```

    Note: the reviewer cited `§16.2` but the broken reference is actually in `§2.2`. The line number (`:469`) confirms — §16 covers Ethereum Interop and does not contain this reject-rule list. The reviewer's section number is from an older draft.
  - WP §13 "Parameters (Genesis Defaults)" (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:770-797`): no formal §13.1 subsection. The parameter groups are bolded labels ("**Execution:**", "**Fees:**", "**Consensus:**", "**Dedicated Lanes:**", "**Off-chain:**", "**State Rent:**", "**Economics:**") but not numbered subsections.
  - WP §12.1 "DoS limits (consensus-enforced; governance-tunable)" (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:748-752`):

    ```
    12.1 **DoS limits (consensus-enforced; governance-tunable).**

    - `max_tx_size` = 128 KiB
    - `max_message_depth_per_tx` = 32
    - `per_actor_per_block_cycles` = 1,000,000 (burstable)
    ```

    These are exactly the per-tx maxima that the §2.2 reject rule checks against.
- **Verification**        : ✅ still accurate — the `(§13.1)` reference dangles. The reviewer's recommendation to repoint to `§12.1` is the correct target.
- **Recommendation**      : [WP §2.2 edit — single-line cross-reference fix]
- **Specific change**     : in `2026-03-21_cowboy-technical-whitepaper-revised-v2.md:469`, replace `(§13.1)` with `(§12.1)`. The §13 (parameter table) is also a valid target, but §12.1 is more specific — `§13` enumerates *all* genesis parameters, while `§12.1` enumerates exactly the three per-tx limits the validity check is verifying against.
- **Rationale**           :
  - Pure editorial; the change is one token. §12.1's three limits (`max_tx_size`, `max_message_depth_per_tx`, `per_actor_per_block_cycles`) are precisely the consensus-enforced maxima a node validates at tx-receive time. §13 is the broader parameter dump.
  - The reviewer's "§16.2" location is stale (pre-v2 numbering); the actual broken reference is in `§2.2`. The fix target stays §12.1 regardless.
  - The reviewer's alternative target "§27" doesn't exist in v2; §27 was the parameter dump in an older numbering where Part II ran §18-§30. Today's equivalent is §13.
- **Open questions**      :
  - Should the §12.1 limits be expanded to also include `cycles_limit ≤ block_cycle_capacity` and `cells_limit ≤ block_cell_capacity` (which are also "limits exceed maxima" conditions)? Currently those caps live in CIP-3 §2.2.3 and §2.4. Defer — adding them is a §12.1 content change, not a cross-reference fix. Treat it as a separate item if needed.
- **Priority**            : P3 (editorial). Batch with other v2-WP fixes — does not need to ship standalone.

### [69] §5.1 same-block timer prohibition cross-link          (P3, cross-ref → 02-timer-gba.md)

- See `02-timer-gba.md` item [69] for full treatment. Summary: not a §5.1-internal drift; the actual issue is a dangling `§Timer Rate Limiting` reference in WP §3.3. Recommendation is editorial — repoint that dangling reference and add one explicit cross-link sentence in §5.1.

---

## Decision-register entries from this topic

None — all five owned items resolve to either editorial fixes (1) or no-ops (4: 2 resolved + 2 dropped). No design decision is required; the analysis ledger should simply record:

- `[18]` `resolved-2026-05` (v2-WP strip removed the conflicting tier table)
- `[51]` `resolved-2026-05` (duplicate of [18])
- `[40]` `dropped-2026-05` (claim refers to a constant not present in v2 WP)
- `[63]` `dropped-2026-05` (duplicate of [40])
- `[67]` `actionable-2026-05` — single-line edit: WP §2.2 line 469, replace `(§13.1)` with `(§12.1)`
- `[69]` `cross-ref` → `02-timer-gba.md`

---

## Notes for the next editorial pass on the WP

When the actionable edit (#67) is applied, the same pass should also consider:

1. Adding a forward-reference note to WP §11 ("see CIP-12 for governance tier values, quorums, and voting windows") so item [18] / [51] is explicitly closed in-document rather than only by deletion. This was raised as an open question in [18] above and is not required.
2. Sweeping the v2 WP for other pre-v2 section-number references — the reviewer's persistent confusion between "§11.5 / §25.5", "§11.6 / §25.6", "§11.3 / §25.3", "§13 / §27", "§16.2" all suggest the reviewer was working from a draft with a different layout. A grep for `§[2-9][0-9]\.` would surface any other dangling pre-v2 numbers; the fix list is likely short.

These are recommendations only — not part of any item this file owns.
