# 07 — State Rent, Eviction, CBFS Relay Economics

> Differential analysis: external reviewer (Vending Machine, April–May 2026) vs. live Cowboy CIPs & whitepaper. Read-only round; no CIP/WP edits performed here.
>
> Authoritative sources cross-checked:
> - `/refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md` (§4.4, §12.5, §13 "State Rent", §17.5, §17.6)
> - `/refs/cips/cip-4-storage.md` (QMDB state storage — no rent content)
> - `/refs/cips/cip-9-runner-storage.md` (CBFS / Steamtrain RAS, §5.6, §5.7, §10, §14 parameters)
> - `/refs/cips/ext_cip-9-10-meeting-gap-analysis.md`, `/refs/cips/ext_cip-9-runner-steamtrain-architecture.md`, `/refs/cips/ext_cip-2-9-10-runner-fee-chain.md`
> - Reviewer original: `/tmp/design-review_findings.md` items [15], [29], [34], [57], [58], [59]

## TL;DR

- **Reviewer's headline numbers are real and live.** WP v2 §17.5 pins `rent_rate = 0.001 CBY/byte/year`, `grace_threshold = 10,240 bytes`, `rent_epoch_length = 1 day`, `eviction_threshold = 10 rent‑epochs`. Earlier verification notes that said these numbers were from an older WP version were stale — the v2 WP carries them verbatim. Reviewer item [15]/[59] is correctly grounded.
- **Eviction threshold has already been reconciled in WP v2.** §4.4 ("eviction is eligible after 10 rent‑epochs"), §17.5 ("eviction_threshold = 10 rent‑epochs"), §13 Parameters block (grace 7 + warning 3, no separate eviction constant), and §12.5 (no number) now agree on **10 rent‑epochs**. The "N+11" framing the reviewer flagged at §12.3 is **not present in v2** — §12.5 carries only a one-line summary. The only residual cosmetic drift is §4.4's "**rent‑epoch N+10**" parenthetical wording, which is consistent with "10" but reads as ambiguous. Reviewer item [57] is largely **superseded by v2** but a one-sentence editorial tightening is warranted.
- **Per-rent-epoch length IS specified in v2** (`rent_epoch_length = 1 day`, §17.5 and §4.4) — reviewer item [34] is partially wrong on the length claim. The genuinely missing piece is the **catch-up fee formula's interaction with rent-rate auto-adjust** (does the 10% penalty apply to nominal missed rent or rate-adjusted missed rent?) and a `rent_epoch_length` row in the §13 Parameters table for discoverability.
- **CBFS Relay economics gap is real but smaller than reviewer implies.** CIP-9 §10.4 documents `STORAGE_FEE_BURN_RATE = 10%`, §5.6 enumerates `POR_MISS_PENALTY` / `POR_FRAUD_PENALTY` / `RELAY_EVICTION_PENALTY`, and §14 lists `MIN_RELAY_STAKE`, `POR_CHALLENGE_INTERVAL=600`, `POR_RESPONSE_WINDOW=50`, `POR_CHALLENGE_FEE_SHARE=2%`. **What is missing**: concrete CBY numbers for `STORAGE_FEE_PER_BYTE_PER_EPOCH`, `TRANSFER_FEE_PER_BYTE`, `MIN_STORAGE_BALANCE`, `MIN_RELAY_STAKE`, `POR_MISS_PENALTY`, `POR_FRAUD_PENALTY`, `RELAY_EVICTION_PENALTY`, plus a `RELAY_CHALLENGE_BOND` field that doesn't yet exist. Reviewer's "10/90 split undocumented" claim is **incorrect** — the 10% burn rate is documented; what's missing is the dispatch of the remaining 90% (pro-rata vs. weighted, recorded in §10.4 as "pro-rata by shards held" but only as prose).
- **Recommended actions.** (i) New **CIP-31 "CBFS Rent Schedule"** populates the TBD numbers and adds a `RELAY_CHALLENGE_BOND` parameter; CIP-9 §14 keeps the parameter names, CIP-31 owns the values. (ii) CIP-4 v2 (or a `cip-4-storage` amendment) clarifies catch-up formula interaction with rate-adjust and adds rent-epoch length to the §13 Parameters block reference. (iii) WP §17.5 gets a one-paragraph "rent is CBY-denominated; Tier-0 cadence" note for item [15]/[59] — **no oracle**. (iv) WP §4.4 one-line wording fix replaces "rent-epoch N+10" with "after 10 rent-epochs of accumulated debt" for item [57].

## Items index

| # | Title | Priority | Touches | Status | Action |
|---|-------|----------|---------|--------|--------|
| 15 | State rent CBY-denominated — trivially cheap or punitive | P2 | WP §17.5, §13 | actionable | WP §17.5 paragraph + Tier-0 cadence; decision-register entry |
| 29 | CBFS Relay Node economics undefined (Gap G8) | P1 | CIP-9 §14, new CIP-31 | actionable | new CIP-31 "CBFS Rent Schedule" |
| 34 | Per-rent-epoch length + catch-up mechanics | P2 | WP §17.5, §13; CIP-4 amendment | partially superseded | confirm `rent_epoch_length = 1 day` in §13 Parameters; CIP-4 amendment for catch-up formula |
| 57 | Eviction threshold inconsistency (§4.4 / §12 / §17) | P3 | WP §4.4 | mostly superseded | one-line §4.4 wording tighten only |
| 58 | §17.6 CBFS Relay rates / bond / slashing missing | P1 | WP §17.6, CIP-9 §14, new CIP-31 | actionable | new CIP-31 + WP §17.6 forward reference |
| 59 | State rent CBY-denominated not USD-stable | P2 | WP §17.5 | actionable | folded into item [15]; decision-register oracle vs. governance |

---

## A. Actor state rent (WP §4.4 / §17.5 / CIP-4)

### [15] / [59] — Rent CBY-denominated, not USD-stable          (P2, status: actionable, decision-register)

- **Reviewer source**     : `design-review_findings.md` items [15] (Section 7.2 item 6) and [59] (Whitepaper-Sections-for-Reconsideration CRITICAL §12/17.5/17.6)
- **Reviewer's "current"**: "`rent_rate = 0.001 CBY/byte/year`; 10 KB grace threshold; 1 MB actor = ~1.014 CBY/year … purely token-denominated; at CBY=$0.10 trivially cheap ($0.10/year for 1MB actor); at CBY=$10 punitive ($10.14/year)"
- **Reviewer's proposal** : "Add paragraph acknowledging CBY-denominated assumption; either commit to monitoring + Tier-0 adjustment cadence, OR flag CIP for oracle-anchored rent"
- **Actual current state**:
  - WP §17.5 (`2026-03-21_cowboy-technical-whitepaper-revised-v2.md:931-942`): "`rent_per_rent_epoch = max(0, account_size - grace_threshold) × rent_rate` Parameters: `grace_threshold = 10,240 bytes (10 KB)` `rent_rate = 0.001 CBY/byte/year (governance-adjustable)` `rent_epoch_length = 1 day` `eviction_threshold = 10 rent‑epochs unpaid rent`".
  - WP §4.4 line 561: "Persistent storage incurs **rent** per byte per rent‑epoch, which is governance-tunable."
  - WP §13 line 793: "`target_state_size` = governance-tunable; `grace_period` = 7 rent‑epochs; `warning_period` = 3 rent‑epochs; `catch_up_fee` = 10%; `reserve_multiplier` = 0.1."
  - WP §4.4 line 411 (rate auto-adjust): "`rent_rate_{i+1} = rent_rate_i × (1 + clamp((S - T) / (T × alpha), -delta, +delta))` where S is the current total state size, T is the target (governance‑tunable), alpha = 8, and delta = 0.125."
- **Verification**        : ✅ — reviewer's numbers match the live WP exactly. The auto-adjust formula at §4.4 reacts to **state size pressure**, not to CBY/USD price; the reviewer's USD-volatility concern is correct as written. (Note: the formula at §4.4 does not appear in §17.5; the two presentations could be reconciled but are not contradictory.)
- **Recommendation**      : [WP §17.5 paragraph + decision-register entry; **no oracle** in v1]
- **Specific change**     : Append to WP §17.5: "The rent rate is denominated in CBY. The protocol assumes a Tier-0 governance review cadence (target: every 30 days post-TGE, every 90 days at steady state) to keep the effective USD cost of 1 MiB of actor storage within a target band of `[$1, $10] per year`. Oracle-anchored rent is explicitly deferred — the state-size auto-adjust formula (§4.4) tracks state-bloat pressure but not CBY price; price tracking is governance's responsibility, not the consensus layer's. A future CIP MAY introduce oracle-anchored rent if the governance cadence proves insufficient."
- **Rationale**           : Two reasons to prefer governance monitoring over an oracle. (1) Oracles at the rent-accounting layer would add a consensus-critical external dependency to the per-block state transition — this is the heaviest possible coupling for a cost that, even at 10x CBY, is `~$10/MiB/yr` (small relative to runner-job costs). (2) The state-size auto-adjust at §4.4 already gives the protocol one self-correcting knob (state pressure); a second self-correcting knob (price) on top of governance review is over-engineered for the v1 surface area. Reviewer's "explicit choice over silent CBY-only" point is well-taken — the paragraph above makes that choice explicit and binds Tier-0 to a cadence rather than leaving "governance-tunable" floating.
- **Open questions**      : (a) Are the `[$1, $10] / MiB / yr` target band edges acceptable to Foundation as a published commitment, or should they be left to governance with no published band? (b) Does the 30-day review cadence post-TGE conflict with the Council/Tier-0 minimum-deliberation windows in CIP-12? Verify before WP edit lands.

### [34] — Per-rent-epoch length + catch-up mechanics          (P2, status: partially superseded)

- **Reviewer source**     : `design-review_findings.md` item [34] (Gap G15)
- **Reviewer's "current"**: "Rent epochs exist; their length and catch-up fee mechanics not specified"
- **Reviewer's proposal** : "Specify per-rent-epoch length (e.g., 7 days) and catch-up fee formula"
- **Actual current state**:
  - WP §17.5 line 940: "`rent_epoch_length = 1 day`" (explicit; governance-adjustable since the §17.5 header marks rent params governance-adjustable).
  - WP §4.4 line 415: "Rent is auto‑deducted from the actor's balance each rent epoch (default: 1 day). Actors may also prepay rent for cost certainty, and any account may sponsor rent on behalf of any actor. Each actor maintains a minimum balance reserve (~5 weeks of rent) as a buffer before entering grace period."
  - WP §4.4 line 421 (catch-up formula): "**Grace period (7 rent‑epochs):** Actor remains fully functional; flagged as 'rent overdue'; catch‑up fee accumulates (10% of missed rent)."
  - WP §13 Parameters (`2026-03-21…v2.md:791-793`): does NOT list `rent_epoch_length` — `grace_period`, `warning_period`, `catch_up_fee`, `reserve_multiplier` are present but rent-epoch length is missing from the parameters block.
- **Verification**        : ⚠ — reviewer's "length not specified" claim is **wrong** (it is, at §17.5 and §4.4 default-1-day). Reviewer's catch-up claim is **wrong** (the 10% formula is stated at §4.4 line 421). The genuine residual gaps are (a) `rent_epoch_length` missing from the §13 Parameters table — only its body-text definitions exist, which makes the parameter undiscoverable in the canonical parameter list; (b) the interaction between the 10% catch-up fee and the state-size auto-adjust formula is undefined — does "10% of missed rent" use the rate at the time the rent was missed or the rate at the time of catch-up? CIP-4 currently carries zero rent content (only QMDB physical storage), so the rent specification is whitepaper-only; this is itself a structural weakness (rent normative text should live in a CIP for amend-ability).
- **Recommendation**      : [WP §13 Parameters line edit + CIP-4 v2 (or new CIP-4 amendment block) on catch-up interaction]
- **Specific change**     : (a) WP §13 "State Rent" block: insert `rent_epoch_length = 1 day (governance-tunable);` before `grace_period`. (b) New "Rent" subsection in CIP-4 (CIP-4 v2 amendment): pin catch-up fee semantics — `catch_up_fee_i = 0.10 × missed_rent_i` where `missed_rent_i` uses the **rent rate as it was at epoch i** (i.e., rate applied at the time the rent was originally due, not the rate at catch-up). Add worked example. (c) Reviewer's suggestion of 7-day rent-epoch is **rejected** as launch default — 1-day keeps eviction pressure visible and post-grace catch-up windows tractable; 7-day would compound 7x the per-epoch debt accrual and reduce developer feedback frequency.
- **Rationale**           : The "missing length" claim is a reviewer scan error; the live WP already says 1 day. But the §13 Parameters block is the canonical operator-facing reference — every other param shows up there, rent_epoch_length should too. The catch-up rate-stamping question is a real implementation ambiguity: under §4.4's auto-adjust, the rent rate at "miss time" can differ from rate at "catch-up time" by up to `(1+δ)^k` over k epochs. Pinning catch-up to the miss-time rate is fairer (developer pays the rate they should have paid) and is what the formula's prose ("10% of missed rent") implies; making it explicit closes the ambiguity.
- **Open questions**      : Is "rate at miss-time" implementable cheaply, or does it require per-epoch rate snapshots in actor state? If the latter is too expensive, fall back to a single moving-average rate snapshot per actor per N epochs.

### [57] — Eviction threshold inconsistency (§4.4 / §12 / §17)          (P3, status: mostly superseded)

- **Reviewer source**     : `design-review_findings.md` item [57] (Whitepaper-Sections-for-Reconsideration CRITICAL §12/17.5/17.6)
- **Reviewer's "current"**: "§4.4: 'after 10 rent-epochs'; §12.3: Grace 7 + Warning 3 + 'N+11'; §17.5: 10 rent-epochs — texts disagree by ±1"
- **Reviewer's proposal** : "Reconcile on single threshold (recommend: 10 rent-epochs); rewrite §12.3 to remove 'N+11' framing"
- **Actual current state**:
  - WP §4.4 line 423: "**Eviction (rent‑epoch N+10):** Actor storage and active timers are pruned. Code, address, balance, and storage root hash are preserved."
  - WP §4.4 line 561 (§4.4 normative summary): "If unpaid for **7 rent‑epochs**, an eviction warning begins; eviction is eligible after **10 rent‑epochs**."
  - WP §12.5 line 766-768 (the section the reviewer called §12.3): "**State rent & eviction.** Prevents state bloat; eviction windows protect liveness." — **no N+11 framing present in v2**.
  - WP §17.5 line 941: "`eviction_threshold = 10 rent‑epochs unpaid rent`".
  - WP §17.5 line 948: "Eviction after 10 rent‑epochs of accumulated debt".
- **Verification**        : ⚠ mostly superseded — the §12.3 "N+11" wording the reviewer flagged is **not present in WP v2**; §12.5 has been collapsed to a one-line summary that simply defers to §4.4 / §17.5. §4.4 and §17.5 both pin "10 rent-epochs". The only cosmetic ambiguity is §4.4 line 423's parenthetical "**rent-epoch N+10**" — this is consistent with 10 (the eviction occurs at the 11th epoch, indexed from `N` = first overdue epoch as 0, so `N+10` is the 11th epoch, i.e., 10 epochs after first overdue) but it reads as "10 or 11?" to an unfamiliar reader. Reviewer's reconciliation is already 95% done in v2.
- **Recommendation**      : [WP §4.4 one-line wording fix only]
- **Specific change**     : WP §4.4 line 423, replace "**Eviction (rent‑epoch N+10):**" with "**Eviction (after 10 rent-epochs of unpaid rent — i.e., 7 rent-epochs grace + 3 rent-epochs warning):**". This makes the "10" the single reading and removes any "N+10 vs N+11" parsing ambiguity. No edit to §12.5 (already collapsed) and §17.5 (already says 10) needed.
- **Rationale**           : Reviewer's structural reconciliation has already happened in v2. The remaining issue is a single sentence with ambiguous N-indexing; a 2-line wording fix is sufficient. Treating this as a P3 editorial fix rather than P2 reconciliation reflects what's actually in v2.
- **Open questions**      : None — verify §12.3 reference points at §12.5 throughout the WP and reviewer docs after the edit lands.

---

## B. CBFS Relay economics (CIP-9 / new CIP-31)

### [29] / [58] — CBFS Relay rates / bond / slashing undefined          (P1, status: actionable)

- **Reviewer source**     : `design-review_findings.md` items [29] (Gap G8) and [58] (Whitepaper-Sections-for-Reconsideration CRITICAL §17.6)
- **Reviewer's "current"**: "Mentions per-byte-per-epoch volume rent and Relay attestations, but no concrete rates or slashing schedule … 10%-burn / 90%-relay split observed in `cowboy-ras` crate is not documented in whitepaper at all"
- **Reviewer's proposal** : "Add §17.6 subsection covering per-byte-per-epoch storage rate (concrete value), 10/90 burn/relay split, Relay challenge bond, Relay slashing schedule for proof-of-retrievability failures"
- **Actual current state**:
  - CIP-9 §10.4 line 854: "A portion of the storage fee (`STORAGE_FEE_BURN_RATE`, e.g., 10%) is burned, consistent with CIP-3's deflationary design. The remainder is distributed to Relay Nodes." (The 10/90 split **is** documented; reviewer is partially wrong.)
  - CIP-9 §10.4 line 850: "Account Owner ──(per-epoch storage fee)──► Protocol ──► Relay Nodes (pro-rata by shards held)".
  - CIP-9 §5.6 lines 382-385 (PoR slashing table): "No response within window → `shards_lost` incremented; shard flagged for repair; `POR_MISS_PENALTY` slashed from stake. Invalid response (proof mismatch) → `POR_FRAUD_PENALTY` slashed from stake (higher than miss penalty). 3+ consecutive misses → Relay Node removed from active list; all shards flagged for repair; `RELAY_EVICTION_PENALTY` slashed."
  - CIP-9 §14 lines 1192-1212 (parameters table): `BASE_ATTACHMENT_FEE = 100 CBY`; `STORAGE_FEE_PER_BYTE_PER_EPOCH = TBD`; `TRANSFER_FEE_PER_BYTE = TBD`; `STORAGE_FEE_BURN_RATE = 10%`; `MIN_STORAGE_BALANCE = TBD`; `STORAGE_GRACE_EPOCHS = 7,200 (~24 hours at 12s blocks)`; `MIN_RELAY_STAKE = TBD`; `POR_MISS_PENALTY = TBD`; `POR_FRAUD_PENALTY = TBD`; `RELAY_EVICTION_PENALTY = TBD`; `POR_CHALLENGE_FEE_SHARE = 2%`.
  - CIP-9 §14 — **no `RELAY_CHALLENGE_BOND` parameter exists**. Challenge dispute economics are absent (challenger is "any onchain actor that triggers a challenge via CIP-5 timer" per §5.6 line 389 — challengers post no bond today).
  - WP §17.6 lines 950-962: "Large data … uses Retention Contracts: BlobRef storage / Provider payments … Blob storage is **not cell-metered**. Provider payments are direct CBY transfers negotiated off-chain. See CIP-7 for full specification…". — **§17.6 in v2 describes CIP-7 retention contracts, not CIP-9 RAS / Relay Nodes**. The reviewer's "§17.6 CBFS Relay" attribution is **wrong** — CBFS Relay economics aren't in §17.6 at all; they're in CIP-9 §14.
  - CIP-9 §14 note line 1198: "`STORAGE_GRACE_EPOCHS = 7,200 ~24 hours at 12s blocks`" — **stale block-time assumption**; chain block time is 1 s (WP §6.1), so 7,200 blocks = 2 hours, not 24 hours. Separate latent bug.
- **Verification**        : ✅ core gap is real (concrete CBY values absent, no challenge-bond field, `STORAGE_GRACE_EPOCHS` comment carries stale 12 s assumption); ❌ reviewer's "10/90 split undocumented" claim is wrong (CIP-9 §10.4 states it); ❌ reviewer's "WP §17.6 CBFS" attribution is wrong (§17.6 is CIP-7 retention, not CIP-9 Relay).
- **Recommendation**      : [new **CIP-31 "CBFS Rent Schedule"** + CIP-9 §14 reference rewrite + CIP-9 §14 block-time comment fix + WP §17.6 forward reference]
- **Specific change**     :
  1. **New CIP-31 "CBFS Rent Schedule"** owning numeric values: `STORAGE_FEE_PER_BYTE_PER_EPOCH` (recommend genesis value to be modeled against target operator margin; placeholder `10 nano-CBY/byte/epoch` for `1 day` epochs pending economic model), `TRANSFER_FEE_PER_BYTE` (placeholder `1 nano-CBY/byte`), `MIN_STORAGE_BALANCE = 1 epoch × max(declared_volume_size, 10 MiB)`, `MIN_RELAY_STAKE = 5,000 CBY` (1/2 of runner-stake floor, scaled to capacity tier), `POR_MISS_PENALTY = 10 CBY per missed shard challenge`, `POR_FRAUD_PENALTY = 100 CBY per fraudulent proof` (10× miss), `RELAY_EVICTION_PENALTY = MIN_RELAY_STAKE / 2`, plus new `RELAY_CHALLENGE_BOND = 10 CBY` (challenger bond, refundable on fraud-found, forfeit on frivolous). All TBDs in CIP-9 §14 stay as named parameter references; CIP-31 carries the numbers. (Numbers above are first-cut **straw values** for review, not normative recommendations — economic modeling owns the final values.)
  2. **CIP-9 §10.4 expansion**: add explicit normative line — "The 10% burn / 90% Relay split applies to the storage fee pool after `POR_CHALLENGE_FEE_SHARE = 2%` is reserved for challenge funding. Concrete split: `burn = 0.10 × storage_fee_pool`, `challenge_pool = 0.02 × storage_fee_pool`, `relay_distribution = 0.88 × storage_fee_pool` pro-rata by `(shard_count × shard_age_in_epochs)`." Pro-rata weighting needs the explicit formula — "by shards held" is currently underspecified.
  3. **CIP-9 §5.6 challenge-bond clause**: add `RELAY_CHALLENGE_BOND` requirement — "Challengers MUST escrow `RELAY_CHALLENGE_BOND` CBY when triggering a PoR challenge. Bond is refunded on (a) Relay Node response within window with valid proof (challenger pays no fee — bond returned), (b) Relay Node failure (challenger receives bond back plus finder's fee from `POR_CHALLENGE_FEE_SHARE` pool). Bond is forfeit to the challenge pool if (c) challenger withdraws or (d) challenge is determined frivolous via dispute window." Dispute window: 75 blocks (aligned with CIP-2 `DISPUTE_WINDOW_BLOCKS`).
  4. **CIP-9 §14 block-time comment fix**: replace all `(~X hours at 12s blocks)` annotations with the correct 1 s block-time math. `STORAGE_GRACE_EPOCHS = 7,200` → "~2 hours at 1s blocks". `RELAY_UNSTAKE_DELAY = 7,200` → "~2 hours". `ORPHAN_SHARD_TTL = 7,200` → "~2 hours". `POR_CHALLENGE_INTERVAL = 600` → "~10 minutes at 1s blocks" (currently says "~2 hours at 12s blocks"). `POR_RESPONSE_WINDOW = 50` → "~50 seconds" (currently says "~10 minutes"). **Separately decide whether the intended durations were the 12s-block times** — if so, the constants need a 12× re-scale (`POR_CHALLENGE_INTERVAL` → 7,200 for "~2 hours") rather than a comment edit. This is a normative decision that CIP-31 should resolve.
  5. **WP §17.6 forward-reference (one line)**: append to §17.6 "(CBFS Relay Node economics — per-byte-per-epoch storage rate, burn/relay split, challenge bond, slashing schedule — are specified in CIP-9 §14 and CIP-31.)" §17.6's title "Off-Chain Blob Storage (CIP-7)" stays — it is CIP-7 retention contracts, not CBFS RAS.
- **Rationale**           : CBFS rent schedule belongs in a CIP, not the WP — the WP's job is to declare the system's existence (Relay Registry, PoR challenges, fee flow) and defer numbers to CIP-9 / CIP-31, the same pattern as CIP-2 / CIP-3. A new CIP-31 dedicated to rent schedule keeps CIP-9 focused on the storage data plane (manifests, placement, erasure, CapTokens) and CIP-31 focused on economic constants — this lets economic parameters be governance-tuned independently from data-plane protocol changes. The `RELAY_CHALLENGE_BOND` addition closes a real Sybil-attack vector (free challenges → DoS Relay Nodes with bogus challenges → force expensive proofs). Reviewer's framing of CIP-31 economics being a §17.6 edit is incorrect (CIP-7 lives there); the correct WP touchpoint is a forward reference, not new content. The block-time comment fix is a separate latent bug surfaced during this review — flag and fix.
- **Open questions**      : (a) Economic-modeling owns the final CBY values — straw numbers above are review-baseline only. (b) Is the intended `POR_CHALLENGE_INTERVAL` "every 10 minutes" (current value with 1 s blocks) or "every 2 hours" (the comment's intent at 12 s blocks)? Verify with implementation in `cowboy-ras` and `steamtrain` — if implementation uses 600 blocks today, the comment is wrong; if implementation uses 7,200, the constant is wrong. (c) Should challenge bonds use the same chain-wide `DISPUTE_WINDOW_BLOCKS = 75` constant or a CBFS-specific window? Reusing the chain constant is simpler. (d) Does `MIN_RELAY_STAKE = 5,000 CBY` scale per declared capacity tier, like runner stake scales per `declared_max_job_value`? Probably yes — model after CIP-2 `runner_stake_floor`.

---

## C. Decision-register entries from this topic

1. **State rent denomination — CBY-monitored vs. oracle-anchored** (item [15]/[59]). Recommend CBY-denominated with documented Tier-0 review cadence (30-day post-TGE → 90-day steady-state); explicitly defer oracle-anchored rent to a future CIP. Foundation pre-clear required before WP §17.5 paragraph lands.
2. **CBFS economics home — CIP-9 v2 vs. new CIP-31** (items [29]/[58]). Recommend **new CIP-31 "CBFS Rent Schedule"** — keeps CIP-9 focused on data-plane (manifests, placement, CapTokens, PoR mechanism), CIP-31 owns economic constants. CIP-31 is the authoritative reference for the 10/90 split (currently only in CIP-9 §10.4 prose and the `cowboy-ras` crate).
3. **Per-rent-epoch length genesis default** (item [34]). Recommend **1 day** (governance-tunable). Reviewer's 7-day suggestion rejected — 1-day keeps eviction pressure visible to developers, compounds catch-up debt less, and matches the live WP v2 §17.5 value. Pending: confirmation that 1 day works against the chain's actual block time (86,400 blocks at 1 s — verify mainnet block-time assumption stable).
4. **Eviction threshold canonical value** (item [57]). Recommend **10 rent-epochs** as the single source of truth (already adopted in WP v2 §4.4 / §17.5 / §13). Editorial only — single wording fix at §4.4 line 423.
5. **Catch-up fee rate-stamping** (item [34]). Recommend `catch_up_fee_i = 0.10 × missed_rent_i` where `missed_rent_i` uses the rent rate **at the epoch i where the rent was originally due**, not the catch-up-time rate. Closes ambiguity introduced by §4.4 auto-adjust formula. Foundation can defer to CIP-4 v2 if rate-snapshot cost is prohibitive.
6. **`POR_CHALLENGE_INTERVAL` / `POR_RESPONSE_WINDOW` block-time assumption** (item [58], latent bug). CIP-9 §14 currently comments "~2 hours at 12s blocks" / "~10 minutes at 12s blocks" — chain runs 1 s blocks per WP §6.1. Either the constants are wrong (need 12× upscale) or the comments are wrong (need recompute). Decide and fix in CIP-31 / CIP-9 §14 amendment.
7. **`RELAY_CHALLENGE_BOND` field — new parameter** (item [58]). Recommend adding `RELAY_CHALLENGE_BOND = 10 CBY` to CIP-31, refundable on legitimate challenges, forfeit on frivolous (75-block dispute window). Closes free-challenge DoS surface.

---

## D. New CIPs / amendments proposed

- **New CIP-31 "CBFS Rent Schedule"** (P1, blocks #29 / #58):
  - Pins concrete CBY values for `STORAGE_FEE_PER_BYTE_PER_EPOCH`, `TRANSFER_FEE_PER_BYTE`, `MIN_STORAGE_BALANCE`, `MIN_RELAY_STAKE`, `POR_MISS_PENALTY`, `POR_FRAUD_PENALTY`, `RELAY_EVICTION_PENALTY`, and new `RELAY_CHALLENGE_BOND`.
  - Specifies the 10 / 2 / 88 split (burn / challenge-pool / Relay-pro-rata) with explicit pro-rata weighting formula `(shard_count × shard_age_in_epochs)`.
  - Specifies challenge-bond economics and 75-block dispute window aligned with CIP-2.
  - Resolves the CIP-9 §14 block-time assumption (12 s comments vs. 1 s chain).
  - Owns CBFS rent-schedule amendments going forward; CIP-9 §14 retains only parameter names and defers values to CIP-31.

- **CIP-4 v2 (or CIP-4 amendment block) — "State Rent Normative Anchor"** (P2, blocks #34):
  - Pins catch-up fee semantics: `catch_up_fee_i = 0.10 × missed_rent_i` at miss-time rate.
  - Adds rent-rate snapshot mechanism (or moving-average fallback if per-epoch snapshots are too expensive).
  - Migrates rent normative content out of WP §17.5 prose into CIP-4 v2 (WP keeps a one-paragraph summary + forward reference).
  - Optional: introduces a `rent_rate_floor` and `rent_rate_ceiling` to bound the §4.4 auto-adjust formula (reviewer didn't ask for this but it's a small natural addition given §4.4's compound geometric behavior).

- **WP §17.5 amendment** (P2, blocks #15 / #59):
  - One paragraph appended to §17.5 declaring rent CBY-denominated, Tier-0 cadence (30 / 90 day), target USD band, and explicit oracle-deferral.

- **WP §4.4 line 423 wording fix** (P3, blocks #57):
  - Replace "**Eviction (rent-epoch N+10):**" with "**Eviction (after 10 rent-epochs of unpaid rent — i.e., 7 rent-epochs grace + 3 rent-epochs warning):**".

- **WP §13 Parameters block — "State Rent" row addition** (P2, blocks #34):
  - Insert `rent_epoch_length = 1 day (governance-tunable);` at line 793 (currently the row starts with `target_state_size`).

- **WP §17.6 forward-reference** (P1, blocks #58):
  - Append one line: "(CBFS Relay Node economics — per-byte-per-epoch storage rate, burn/relay split, challenge bond, slashing schedule — are specified in CIP-9 §14 and CIP-31.)" §17.6 title and CIP-7 retention content unchanged.
