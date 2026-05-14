# WP Impact Matrix

> Tabular synthesis of every whitepaper section touched by topic files 01–08. One row per WP § + change. Cross-reference: [09-new-cips-proposed.md](../09-new-cips-proposed.md) §C, [cip-impact-matrix.md](./cip-impact-matrix.md).
>
> **Severity:** high = touches consensus / commitment / value flow; medium = mechanism specification gap; low = parameter declaration; editorial = wording / cross-reference only.
>
> **Gated on decision:** explicit policy call required before edit lands. See 00-summary §三 (Decision Register).

| WP § | Current | Proposed | Severity | Gated on | Source topic |
|---|---|---|---|---|---|
| **§2.2 line 469** | `(§13.1)` — broken cross-reference, target doesn't exist | repoint to `(§12.1)` (DoS limits, exact target of validity check) | editorial | none | [08-doc-fixes.md](../08-doc-fixes.md) #67 |
| **§3.3 line 520** | dangling "(see §Timer Rate Limiting)" — section does not exist | replace with "(see §5.1 and CIP-5 §5.3)" | editorial | none | [02-timer-gba.md](../02-timer-gba.md) #69 |
| **§4.4 line 423** | "**Eviction (rent-epoch N+10):**" — ambiguous N-indexing | "**Eviction (after 10 rent-epochs of unpaid rent — i.e., 7 rent-epochs grace + 3 rent-epochs warning):**" | editorial | none | [07-state-rent-cbfs.md](../07-state-rent-cbfs.md) #57 |
| **§5.1 (entire subsection)** | mixes current FIFO with target auction; "256 timers/actor" silently disagrees with CIP-5 §6.4's 1,024 | split into §5.1a (current CIP-5 FIFO + 1,024 cap + 550k cycles/cells per fire) and §5.1b (CIP-1 EIP-1559 target summary) | medium | **CIP-1 rewrite** | [02-timer-gba.md](../02-timer-gba.md) #60 |
| **§5.1 (DoS table)** | references same-block prohibition + k > 16 surcharge in physically adjacent rows | add explicit cross-link sentence to CIP-5 §5.3 | editorial | (couple to §5.1 split) | [02-timer-gba.md](../02-timer-gba.md) #69 |
| **§6 Part I line 365** | "Block rewards … Proposers additionally receive transaction tips. Staking is self-bonded only" | "Block rewards (from inflation per §8.2) … Proposers additionally receive 100% of cycle/cell tips on blocks they finalize. No per-tx validator commission or surcharge is charged to users beyond tips." | low | none (declarative) | [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) #32 |
| **§6 Part I line 395 / §6.3 Part II "Dedicated Lanes"** | "Each lane has independent fee multipliers applied to the global basefees" — no numerical values | add `Fee Multiplier` column to lanes table; pin `1.0× ∀ lanes` at genesis; mark Tier-0 tunable | medium | **CIP-3 §2.2.3 amend** | [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) #68 |
| **§6 Part I line 399 (MEV Reduction prose)** | one-line disclaimer "This does not prevent proposer inclusion/censorship or private orderflow MEV" | "This does not prevent (a) single-block proposer inclusion/censorship, (b) private orderflow MEV, or (c) JIT MEV against predictable actor logic — see §6.5 for the explicit out-of-scope list." | low | **CIP-3 §6.5 amend** | [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) #70 |
| **§6.5 Part II (MEV Reduction)** | one disclaimer line at :648 buried in body text | append bolded `Out of scope` subsection enumerating: (i) single-block proposer inclusion/censorship, (ii) private orderflow MEV, (iii) JIT MEV against predictable actor logic; point at SDK-layer mitigations | medium | **CIP-3 §6.5 amend** | [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) #70 |
| **§8.2 inflation schedule table** | 4-year glidepath `8%/6% (Y1-2) → 4%/3% (Y3-4) → 2% (Y5+)` | 3-year glidepath `4% (Y1) → 3% (Y2) → 2% (Y3+)` to match Chad Q6 | high | **decision #5** (policy) | [05-tokenomics-inflation.md](../05-tokenomics-inflation.md) #3 |
| **§8.2 narrative** | "Gross inflation is offset by protocol burn … net inflation depends on network usage" — non-committal | "At steady state the protocol targets **net slightly inflationary** issuance … real-cycle burn is counterweight, not engineered to over-deliver net-negative supply" | editorial | (couple to §8.2 rewrite) | [05-tokenomics-inflation.md](../05-tokenomics-inflation.md) #4 |
| **§8.2 security-floor mechanism** | "security-floor trigger MAY temporarily increase inflation … threshold governance-defined" — parameters undefined | spec the parameters: ratio < `security_floor_staked_ratio` for `security_floor_persistence_blocks` triggers `+security_floor_boost_bps` boost; 10% gross hard cap retained | medium | none | [05-tokenomics-inflation.md](../05-tokenomics-inflation.md) #26 |
| **§8.3 Network Distribution** | per-bucket "Emission Model" prose only ("Front-loaded over 12 months", "Usage-based; paid per runner-hour") — no closed forms | add §8.3.1 "Emission curves (genesis defaults; Tier-0 tunable)" with closed-form per-bucket math: Runner Compute 80M linear-with-usage-rate-lock 60mo (`0.20 CBY/runner-hour`, terminal catchup); Liquidity Mining 23.3M exponential decay 6-mo half-life over 24mo; Validator Rewards tracks §8.2; Developer Grants milestone-based; Community/Airdrops 2 drops (12M TGE + 8M m+6) | high | none (genesis spec) | [05-tokenomics-inflation.md](../05-tokenomics-inflation.md) #30, #31, #49, #66 |
| **§8.4 row "Slashed stake \| 100% \| Burned" (C7)** | flat 100% burn for ALL slash sources | conditional: 95% burn / 5% submitter (validator side, CIP-30); 50% challenger / 30% burn / 20% treasury (runner side, CIP-2 §8.5); OR keep 100% burn | high | **decision #1** | [01-slashing.md](../01-slashing.md) #36 |
| **§8.4 row "Runner job payments \| 89% / 10% / 1%"** | 1% to treasury (auto-feed; contradicts CIP-12 §3.1 framing) | Path A: `90% / 10% / 0%` (redirect 1% to burn for narrative consistency); Path B: redirect 1% to runner (`90% / 10% / 0%`); Path C: keep | medium | **decision #5b** (Chad Q4 accepted) | [05-tokenomics-inflation.md](../05-tokenomics-inflation.md) #2, [06-governance.md](../06-governance.md) §F |
| **§8.4 (fee-sinks table note)** | no explicit "no other validator revenue from users" line | append note: "Validators receive no other revenue stream from users; their entire user-derived income is the `tips` line above. Inflation rewards (§8.2) accrue independently and are stake-proportional." | low | none (clarify) | [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) #32 |
| **§11 (Governance & Upgrades)** | "Foundation 5-of-9 multisig sunsets after ~12 months" — contradicts CIP-12 permanent-Council framing | drop sunset line; replace with "see CIP-12 for tier values, quorums, deposits, voting windows" | editorial | **CIP-12 amendment** | [06-governance.md](../06-governance.md) §B (#18 / #51 resolved-by-strip in v2) |
| **§11 (Security Council)** | "permanent, removable only via Tier 4" | conditional sunset (per decision #3): Council scope auto-reduces by one named power per `sunset_epoch_length` once `validator_count ≥ N AND total_staked_value ≥ V` for 2 consecutive epochs; Tier-4 override permitted | medium | **decision #3** (sunset thresholds) | [06-governance.md](../06-governance.md) #46, #61 |
| **§11.3 (Validator penalty table)** | four flat rows: "Double signing \| Jail + slash 1%"; "Proposer equivocation \| Jail + slash 1%"; "Extended downtime \| Jail (no slash)"; "Invalid block proposal \| Jail (no slash)" | Simplex-enumerated table from CIP-30: notarization equivocation, finality-dummy equivocation, conflicting finalize → `p_self(x, n)` + permanent tombstone; proposer equivocation → `p_self(x, n) / 2` + tombstone; invalid block proposal → jail only; extended downtime → jail only | high | **CIP-30** | [01-slashing.md](../01-slashing.md) #8, #50 |
| **§11.4 / §20.1** | no `SlashingEvidence` transaction format | add evidence transaction format + System-lane classification clause from CIP-30 (idempotency, sig_pair, height, evidence_submitter) | medium | **CIP-30** | [01-slashing.md](../01-slashing.md) §C |
| **§13 parameters (Consensus)** | `minimum_validator_stake = governance-tunable`, `double_sign_slash = 1%` | replace with CIP-30 references; add `S_in = 0.50%, S_low = 0.40%, S_out = 0.33%, S_max = 5.0%`; add `c = 3, p_floor = 1%, X_safety = 10, correlation_window_blocks = 3,600`; add `validator_commission_model = tips_only` | medium | **CIP-30** + #32 | [01-slashing.md](../01-slashing.md), [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) #32 |
| **§13 parameters (Economics)** | missing `validator_apr_target`, `security_floor_*` | add: `validator_apr_target = 4–6%` (inflation-adjusted, Tier-0 band); `security_floor_staked_ratio = 33%`; `security_floor_boost_bps = 200`; `security_floor_persistence_blocks = 2_592_000` (30 days at 1 s) | medium | (couple to §8.2 spec) | [05-tokenomics-inflation.md](../05-tokenomics-inflation.md) #17, #26, #39, #48 |
| **§13 parameters (State Rent)** | missing `rent_epoch_length` from canonical parameter list (body text says `1 day` but not in table) | insert `rent_epoch_length = 1 day (governance-tunable);` at line 793 | low | none | [07-state-rent-cbfs.md](../07-state-rent-cbfs.md) #34 |
| **§13 parameters (Dedicated Lanes)** | lane capacity %s enumerated; no lane-multiplier params | add `lane_fee_multiplier_system / _timer / _runner / _user = 1.0` (all Tier-0 tunable per CIP-12) | low | **CIP-3 §2.2.3 amend** | [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) #68 |
| **§16.2 (Bridges)** | "Bridge selection and integration are determined by governance" — current path is worst-of-both-worlds (first big vote also bears largest security decision) | one of: (a) pre-select specific bridge w/ retirement hatch + TVL cap; (b) launch with EVM↔Cowboy bridging disabled, governance elects backend post-mainnet; (c) keep current | high | **decision #3** (bridge selection) — recommend (b) | [06-governance.md](../06-governance.md) #16, #45, #52 |
| **§17.5 (state rent)** | `rent_rate = 0.001 CBY/byte/year` etc.; no oracle, no review cadence, no USD anchor | append paragraph: rent CBY-denominated; Tier-0 review cadence (30-day post-TGE → 90-day steady state); target USD band `[$1, $10]/MiB/yr`; oracle-anchored rent explicitly deferred | low | **decision #4** (no oracle in v1) | [07-state-rent-cbfs.md](../07-state-rent-cbfs.md) #15, #59 |
| **§17.6 (CBFS / CIP-7)** | no forward reference to CBFS rent schedule (§17.6 actually describes CIP-7 retention contracts, not CIP-9 Relay economics) | append one line: "(CBFS Relay Node economics — per-byte-per-epoch storage rate, burn/relay split, challenge bond, slashing schedule — are specified in CIP-9 §14 and CIP-31.)" | low | **CIP-31** | [07-state-rent-cbfs.md](../07-state-rent-cbfs.md) #58 |
| **§17.9 (Reserved Capacity table)** | cycle budgets present; no `Fee Multiplier` column | add `Fee Multiplier` column matching §6.3; pin `1.0× ∀ lanes` | low | **CIP-3 §2.2.3 amend** | [04-fee-model-and-lanes.md](../04-fee-model-and-lanes.md) #68 |
| **§17.10 (Collateral)** | `runner_stake >= max(10,000 CBY, 1.5 × declared_max_job_value)` — CBY-denominated, no monitoring policy | (if decision #4 = "keep CBY-denominated") document explicit monitoring + Tier-0 adjustment trigger | low | **decision #4** | [03-runner-marketplace.md](../03-runner-marketplace.md) #7 |

## Severity distribution

| Severity | Count | Notes |
|---|---|---|
| high | 6 | §8.2 schedule, §8.3 emission curves, §8.4 C7 slashed-stake split, §11.3 validator penalty table, §16.2 bridges, §11 Security Council sunset |
| medium | 9 | §5.1 split, §6 lane multiplier columns, §6.5 MEV scope, §8.2 security-floor mech, §8.4 1% treasury removal, §11 governance summary, §11.4/§20.1 SlashingEvidence, §13 stake bands, §13 economics block |
| low | 9 | §13 sub-rows, §17.5 paragraph, §17.6 fwd-ref, §17.9 column, §17.10 monitoring, §6 commission line, §6 MEV inline, §8.2 narrative, §8.4 note |
| editorial | 4 | §2.2 xref, §3.3 xref, §4.4 wording, §5.1 DoS cross-link |

## Gating distribution

| Gated on | Count | Notes |
|---|---|---|
| none / editorial | 9 | Can land standalone in next editorial pass |
| CIP-30 | 4 | §11.3 / §11.4 / §13 (consensus block) / §20.1 |
| CIP-3 amendments | 4 | §6 / §6.5 / §13 lanes / §17.9 |
| CIP-1 rewrite | 1 | §5.1 split |
| CIP-31 | 1 | §17.6 fwd-ref |
| CIP-12 amendment | 1 | §11 sunset-line drop |
| Decision #1 (WP §8.4 C7) | 1 | §8.4 slashed-stake row |
| Decision #3 (bridge / Council) | 2 | §11 Council sunset, §16.2 bridges |
| Decision #4 (CBY vs oracle) | 2 | §17.5, §17.10 |
| Decision #5 (inflation glidepath) | 1 | §8.2 schedule |
| Decision #5b (Chad Q4 1% removal) | 1 | §8.4 treasury row |
