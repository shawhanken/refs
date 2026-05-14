# CIP-31: CBFS Rent Schedule

| Field           | Value                                                                                          |
| --------------- | ---------------------------------------------------------------------------------------------- |
| **CIP**         | 31                                                                                             |
| **Title**       | CBFS Rent Schedule, Relay Challenge Bond, and Slashing Curve                                   |
| **Status**      | Draft                                                                                          |
| **Type**        | Standards Track (Economic / Parameter)                                                         |
| **Created**     | 2026-05-14                                                                                     |
| **Author(s)**   | Cowboy Foundation                                                                              |
| **Depends-on**  | CIP-9 (RAS / CBFS), CIP-3 (fee model), CIP-12 (governance)                                     |
| **Required-by** | CIP-9 §10.4 / §14 (replaces TBD parameter values); WP §17.6 (forward reference)                |

## Abstract

This CIP pins concrete CBY values for every parameter that CIP-9 (Runner Storage / CBFS) currently labels `TBD`, adds a new `RELAY_CHALLENGE_BOND` field, makes the existing 10 / 2 / 88 burn / challenge-pool / Relay revenue split explicit in normative text, and defines the pro-rata weighting formula that distributes the 88% Relay share across active Relay Nodes. Once this CIP lands, no CIP-9 §14 row carries `TBD`; every CBFS economic constant has either a value or a Tier-0 governance pointer with a numeric default.

This CIP **does not** introduce any new mechanism in CIP-9: every parameter named here already exists in CIP-9 §5 / §10 / §14 (or is the natural completion of the existing split-with-challenge-share schema). The new field `RELAY_CHALLENGE_BOND` is added because the analysis surfaced that the challenge flow described in CIP-9 §5.6 cannot be griefing-resistant without it.

## Motivation

The 2026-04 architecture review flagged "CBFS Relay Node economics fully undefined" as a P1 gap: the rent rate, the 10 / 2 / 88 split, the per-Relay weighting formula, the challenge bond, and the slashing magnitudes were nowhere in any spec (and the partial values in the `cowboy-ras` crate were not authoritative). Pinning these is required to:

1. Let Relay operators run capacity-planning math before mainnet.
2. Let storage-rate volatility (CBY-denominated rent vs USD/GB/yr reality) be observable, monitored, and Tier-0-adjustable on a documented cadence.
3. Provide the challenger economic incentive that makes Proof-of-Retrievability honest in steady state.
4. Bound the worst-case Relay-side loss in slashing events.

This CIP picks values that put the launch-state economics in a defensible band ($1–$10 per MiB-year at CBY = $1) and that compose cleanly with CIP-3's deflationary signals (basefee burn) and CIP-2's dispute window.

## Specification

### 1. Storage Fee Rate

```
STORAGE_FEE_PER_BYTE_PER_EPOCH = 10  // nano-CBY per byte per rent epoch (1 day per CIP-4)
```

Per 1 MiB of stored data per year: `10 nano-CBY × 1,048,576 bytes × 365 epochs ≈ 3.83 CBY/MiB/year`. At CBY = $1 this is ≈ $3.83 / MiB / year (i.e. ~$3.7k / TiB / year — within commodity cloud cold-storage band).

**Mutability:** Tier-0 governance, stored at `0x09` under key `system:cbfs:storage_fee_per_byte_per_epoch`. The Tier-0 review cadence is 30-day post-TGE → 90-day steady state; the target USD-equivalent band is `[$1, $10] / MiB / year`. If the rate drifts outside the band for two consecutive review windows, a Tier-0 proposal MUST be filed.

### 2. Transfer Fee Rate

```
TRANSFER_FEE_PER_BYTE = 1  // nano-CBY per byte served on read
```

A Runner reading a 100 MiB object pays `1 nano-CBY × 100 × 1,048,576 ≈ 0.105 CBY` per read at this rate. Goes entirely to the serving Relay (no burn, no challenge-pool share).

**Mutability:** Tier-0, key `system:cbfs:transfer_fee_per_byte`.

### 3. Minimum Storage Balance

```
MIN_STORAGE_BALANCE = STORAGE_FEE_PER_BYTE_PER_EPOCH × volume_size_bytes × 1
```

i.e. one epoch of fees at the current rate for the volume's current size. Falls below this triggers `STORAGE_GRACE_EPOCHS` per CIP-9 §10.3.

**Mutability:** formula-derived; the multiplier `1` (one epoch) is Tier-0-tunable via `system:cbfs:min_storage_balance_epochs`.

### 4. Fee Distribution Split (`10 / 2 / 88`)

For each epochly storage-fee batch collected from an account:

| Share | Destination                                                | Rationale |
| ----- | ---------------------------------------------------------- | --------- |
| **10%** | **Burn** (sent to `0x00`)                                | Deflationary signal aligned with CIP-3 basefee burn |
| **2%** | **PoR Challenge Pool** (accrued at `0x0B` Relay Registry) | Funds challenger bounties (§7 below); paid out on valid `por_challenge` settlement |
| **88%** | **Relay pro-rata distribution**                          | Active Relays, weighted by `weight_i = (shard_count_i × shard_age_in_epochs_i)` (§5 below) |

Implementation contract:

- `STORAGE_FEE_BURN_BPS = 1000` (10%)
- `STORAGE_FEE_CHALLENGE_POOL_BPS = 200` (2%)
- `STORAGE_FEE_RELAY_BPS = 8800` (88%)
- Invariant: `STORAGE_FEE_BURN_BPS + STORAGE_FEE_CHALLENGE_POOL_BPS + STORAGE_FEE_RELAY_BPS == 10000`

**Mutability:** Tier-0 governance under `system:cbfs:fee_split`; the invariant MUST hold after any proposal.

**Relationship to CIP-9 §10.4 prose:** the current §10.4 text says "10% burn + remainder to Relays". That sentence is a simplification — the actual split is 10 / 2 / 88 (the 2% is `POR_CHALLENGE_FEE_SHARE` in CIP-9 §14). CIP-9 §10.4 is amended in lockstep with this CIP to reflect the three-way split explicitly (no semantic change; just making the schema visible to the reader).

### 5. Relay Pro-Rata Weight Formula

```
weight_i  = shard_count_i × shard_age_in_epochs_i
share_i   = weight_i / Σ_j weight_j
payout_i  = share_i × (storage_fees_collected × 0.88)
```

- `shard_count_i` is the number of unique shards Relay `i` currently holds and serves with valid PoR responses in the prior epoch.
- `shard_age_in_epochs_i` is `min(epochs_since_assignment, MAX_SHARD_AGE_FOR_WEIGHTING)` where `MAX_SHARD_AGE_FOR_WEIGHTING = 90` epochs (~3 months at 1-day epochs). The cap prevents permanent first-mover advantage.

**Rationale.** Pure shard-count weighting rewards Relays that load shards fast but never repair; pure age weighting rewards squatters. The product rewards Relays that take on real storage AND keep it healthy over time. The 90-epoch cap is a Tier-0 parameter.

**Mutability:** Tier-2 governance (changes the revenue distribution mechanism). Key: `system:cbfs:relay_weight_formula`. Tier-0 may not change the formula structure, only `MAX_SHARD_AGE_FOR_WEIGHTING`.

### 6. Minimum Relay Stake

```
MIN_RELAY_STAKE = 5_000 CBY
```

Required to register a Relay Node via the Relay Registry (`0x0B`). Sized to be meaningful relative to a single Relay's expected month-1 revenue (a single Relay holding ~1 TiB of shards at the rates above would earn ~$320 / month at CBY=$1, so a 5,000 CBY (~$5,000) stake is ~15 months of revenue — high enough to deter spam, low enough to admit professional operators).

**Mutability:** Tier-0, key `system:cbfs:min_relay_stake`.

### 7. Relay Challenge Bond (**new field**)

```
RELAY_CHALLENGE_BOND = 10 CBY
```

The CBY a challenger MUST post when calling `por_challenge(shard_id, byte_offset, byte_length)`. This is **new** — CIP-9 §5.6 currently describes PoR challenges but specifies no challenger bond. Without a bond, a malicious actor can submit unlimited challenges to grief Relay Nodes (each forces a `POR_RESPONSE_WINDOW` Relay-side computation).

**Lifecycle:**

- Bond is escrowed at `0x0B` for the duration of the challenge window.
- If the Relay responds correctly within `POR_RESPONSE_WINDOW` blocks: bond is refunded to the challenger minus a `POR_CHALLENGE_FEE = 1 CBY` (kept by `0x0B` as the per-challenge cost; deters frivolous challenges).
- If the Relay fails or responds incorrectly: bond is refunded in full **and** the challenger additionally receives a `CHALLENGER_BOUNTY = 5 CBY` from the PoR challenge pool (§4 above).
- The Relay is slashed per §8 below.

**Mutability:** Tier-0, key `system:cbfs:relay_challenge_bond`. `POR_CHALLENGE_FEE` and `CHALLENGER_BOUNTY` are sub-keys, both Tier-0.

### 8. Slashing Schedule

The three CIP-9 §14 TBD penalty rows are pinned as:

```
POR_MISS_PENALTY        = 50  CBY     // Relay failed to respond within POR_RESPONSE_WINDOW
POR_FRAUD_PENALTY       = 500 CBY     // Relay responded with provably invalid data (> MISS by 10×)
RELAY_EVICTION_PENALTY  = 2000 CBY    // Relay forcibly removed from registry (multiple consecutive frauds, or refusal to repair under §5.5)
```

**Rationale:** A single miss is operational noise (Relays restart, NICs flap). A fraud response is provably dishonest. Eviction is the terminal state.

**Distribution of slashed Relay stake.** Slashed Relay CBY follows the same three-way split as storage fees: **10% burn / 2% challenge pool / 88% pro-rata to the *other* Relays** (i.e. the slashed Relay is excluded from the pro-rata distribution that epoch). This composes cleanly with CIP-3's deflationary design and recycles deterrent capital into the network rather than wholesale burn.

**Mutability:** All three penalty rows are Tier-0, keys `system:cbfs:por_miss_penalty`, `:por_fraud_penalty`, `:relay_eviction_penalty`.

### 9. Dispute Window

The on-chain dispute window for a Relay's challenge response is **75 blocks** (`DISPUTE_WINDOW_BLOCKS` per WP §13), aligned with CIP-2's runner-result dispute window. After 75 blocks the response settles; no later reversal except via cryptographic `EvidenceInvalidityAppeal` (see CIP-32 once authored).

### 10. Parameter Storage at `0x0B` Relay Registry

All values above are stored at the **Relay Registry** system actor (`0x0B`) under the `system:cbfs:` key prefix. The Storage Manager system actor (`0x0A` per CIP-9 §11.1) reads these keys at the start of each rent-epoch to settle fees.

```
0x0B keys (CIP-31):
  system:cbfs:storage_fee_per_byte_per_epoch       u64 (nano-CBY)
  system:cbfs:transfer_fee_per_byte                u64 (nano-CBY)
  system:cbfs:fee_split.burn_bps                   u16 (default 1000)
  system:cbfs:fee_split.challenge_pool_bps         u16 (default 200)
  system:cbfs:fee_split.relay_bps                  u16 (default 8800)
  system:cbfs:min_storage_balance_epochs           u16 (default 1)
  system:cbfs:min_relay_stake                      u64 (CBY)
  system:cbfs:relay_challenge_bond                 u64 (CBY)
  system:cbfs:por_challenge_fee                    u64 (CBY, default 1)
  system:cbfs:challenger_bounty                    u64 (CBY, default 5)
  system:cbfs:por_miss_penalty                     u64 (CBY)
  system:cbfs:por_fraud_penalty                    u64 (CBY)
  system:cbfs:relay_eviction_penalty               u64 (CBY)
  system:cbfs:max_shard_age_for_weighting          u16 (default 90)
```

### 11. Genesis-defaults Summary Table

| Parameter                                | Default       | Mutability | Key                                                |
| ---------------------------------------- | ------------- | ---------- | -------------------------------------------------- |
| `STORAGE_FEE_PER_BYTE_PER_EPOCH`         | 10 nano-CBY   | Tier-0     | `system:cbfs:storage_fee_per_byte_per_epoch`       |
| `TRANSFER_FEE_PER_BYTE`                  | 1 nano-CBY    | Tier-0     | `system:cbfs:transfer_fee_per_byte`                |
| `STORAGE_FEE_BURN_BPS`                   | 1000 (10%)    | Tier-0     | `system:cbfs:fee_split.burn_bps`                   |
| `STORAGE_FEE_CHALLENGE_POOL_BPS`         | 200 (2%)      | Tier-0     | `system:cbfs:fee_split.challenge_pool_bps`         |
| `STORAGE_FEE_RELAY_BPS`                  | 8800 (88%)    | Tier-0     | `system:cbfs:fee_split.relay_bps`                  |
| `MIN_STORAGE_BALANCE_EPOCHS`             | 1             | Tier-0     | `system:cbfs:min_storage_balance_epochs`           |
| `MIN_RELAY_STAKE`                        | 5,000 CBY     | Tier-0     | `system:cbfs:min_relay_stake`                      |
| `RELAY_CHALLENGE_BOND` (**new**)         | 10 CBY        | Tier-0     | `system:cbfs:relay_challenge_bond`                 |
| `POR_CHALLENGE_FEE`                      | 1 CBY         | Tier-0     | `system:cbfs:por_challenge_fee`                    |
| `CHALLENGER_BOUNTY`                      | 5 CBY         | Tier-0     | `system:cbfs:challenger_bounty`                    |
| `POR_MISS_PENALTY`                       | 50 CBY        | Tier-0     | `system:cbfs:por_miss_penalty`                     |
| `POR_FRAUD_PENALTY`                      | 500 CBY       | Tier-0     | `system:cbfs:por_fraud_penalty`                    |
| `RELAY_EVICTION_PENALTY`                 | 2,000 CBY     | Tier-0     | `system:cbfs:relay_eviction_penalty`               |
| `MAX_SHARD_AGE_FOR_WEIGHTING`            | 90 epochs     | Tier-0     | `system:cbfs:max_shard_age_for_weighting`          |
| Relay weight formula structure           | (§5)          | Tier-2     | `system:cbfs:relay_weight_formula`                 |

## Rationale

**Why a separate CIP rather than amending CIP-9 inline.** CIP-9 owns the **data plane** (shards, manifests, erasure coding, PoR mechanics). CIP-31 owns the **economic plane** (rates, splits, bonds, slashing magnitudes). Splitting them lets governance touch the economic surface (Tier-0 / Tier-2) without re-opening the data-plane spec. This mirrors CIP-3 ↔ WP §13 (mechanism vs parameter values).

**Why these specific values.** The storage rate is derived to land in the $1–$10 / MiB / yr USD band at CBY = $1, which sits between commodity cloud cold storage (S3 Glacier ~$0.01 / GiB / month ≈ $0.12 / GiB / yr) and hot cloud storage (~$0.20 / GiB / month ≈ $2.4 / GiB / yr). Higher than Glacier because storage on Relay Nodes is read-immediately, not archive-tier; lower than S3-hot because there's no SLA-grade replication beyond `K + M = 4 + 2` erasure coding.

**Why 10 / 2 / 88 specifically.** The 10% burn matches CIP-3's basefee-burn design. The 2% challenge pool is the smallest workable size — any smaller and a `CHALLENGER_BOUNTY = 5 CBY` cannot accrue from a 1 TiB-scale storage account in less than tens of epochs. The 88% remainder is the practical relay-economy share. The reviewer's Phase-3 selection lists 10/90 as one variant and 10/2/88 as the recommended; we adopt the latter.

**Why `RELAY_CHALLENGE_BOND = 10 CBY`.** Sized to 1/5 of `POR_MISS_PENALTY`, so a challenger who provokes a miss is net economically positive (`+5 bounty − 1 challenge fee = +4 CBY` per valid challenge) while a frivolous challenger loses the 1 CBY fee deterministically.

**Why CBY-denominated, not USD-pegged.** The analysis decision-register item #4 selected CBY-denominated with Tier-0 monitoring cadence, deliberately avoiding a consensus-layer oracle dependency in v1. Re-pegging to USD is a future option, gated on a forthcoming oracle CIP.

## Security Considerations

1. **Challenge griefing.** Without `RELAY_CHALLENGE_BOND` a single attacker could submit thousands of cheap challenges per block. The bond + per-challenge fee (`1 CBY`) make this economically irrational at any rate above one valid challenge per ten attempts.
2. **Rate cliff.** Storage rate as a Tier-0 parameter means a single proposal could spike rent 10× in one epoch. The 30/90-day review cadence in §1 is documentation only; the protocol-level guardrail is CIP-12's Tier-0 timelock (3 days) plus the per-epoch grace period (`STORAGE_GRACE_EPOCHS` = 86,400 blocks = ~24 h) that lets evicted volumes recover.
3. **Pro-rata gaming.** The weight formula `shard_count × shard_age` is hard to game: shard assignment is VRF-controlled (CIP-9 §5.3), shard age accrues only with valid PoR responses, and the 90-epoch cap prevents permanent capture.
4. **Slashed-stake recycling.** The 10/2/88 split for slashed Relay stake (§8) sends 88% to the *other* Relays. This composes with the deflationary signal (10% burn) and provides an economic incentive for healthy Relays to call out misbehaving peers — without creating a perverse incentive to frame innocent peers (since the bounty is in the 2% challenge pool, not in the 88% pro-rata share).

## Open Questions

1. **Storage rate ceiling.** Should there be a hard cap on `STORAGE_FEE_PER_BYTE_PER_EPOCH` (say, 1,000 nano-CBY) to prevent emergency-governance overshoot? Reviewer flagged this; deferred to a Phase-5 simulation pass.
2. **Per-Relay cap.** Should a single Relay's share `share_i` be capped at, say, 5% of the total pro-rata pool to prevent revenue concentration? Currently uncapped; revisit once Relay set is large enough that concentration is measurable.
3. **Cross-actor cross-Relay slashing correlation.** If a single TEE vendor compromise causes correlated PoR failures across many Relays, the current per-Relay slash applies independently. Recommended future amendment: a correlation cap analogous to CIP-30's validator `X_safety`, deferred to a follow-up CIP-31.r2.

## Backwards Compatibility

This CIP introduces **no semantic change** to CIP-9. Every parameter named here is either:

- a TBD row in CIP-9 §14 being filled in with a concrete value (10 of 13 rows), or
- a renaming / explicit-bps version of the schema already present (`STORAGE_FEE_BURN_RATE` 10% becomes `STORAGE_FEE_BURN_BPS = 1000`; `POR_CHALLENGE_FEE_SHARE` 2% becomes `STORAGE_FEE_CHALLENGE_POOL_BPS = 200`), or
- a brand-new field (`RELAY_CHALLENGE_BOND`, `POR_CHALLENGE_FEE`, `CHALLENGER_BOUNTY`, `MAX_SHARD_AGE_FOR_WEIGHTING`) that supplements but does not replace CIP-9 mechanism.

Existing Relay Nodes registered under CIP-9 v1 continue to operate; the schema additions become active at the rent-epoch boundary following CIP-31 activation.

## Reference Implementation

To be authored in the `cowboy-ras` crate alongside the existing storage-fee accounting. Key code paths:

- `0x0A` Storage Manager: per-epoch fee debit; split into three sub-allocations per §4 above.
- `0x0B` Relay Registry: PoR challenge accept/refund flow (§7); slash routing (§8).
- Test vectors: see `node/crates/cowboy-ras/tests/cip31_split_test.rs` (to be added).

## References

- CIP-9 — Runner Storage (Steamtrain / CBFS): the data-plane spec this CIP completes.
- CIP-3 — Dual-Metered Fee Model: cycle/cell metering and basefee burn; this CIP's burn share aligns with §2.4.
- CIP-12 — On-Chain Governance: Tier-0 / Tier-2 framework used here.
- WP §17.6 — Off-Chain Blob Storage: forward references this CIP for Relay Node economics.
- WP §13 — Parameters block: `dispute_window_blocks = 75` used in §9 above.
