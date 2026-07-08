# COW-2266 — Genesis Parameter Reconciliation Decision Memo (2026-06-22)

**Purpose:** lay out the verified spec↔code parameter drift and a recommended canonical direction per group, so the governance / CIP-3 / CIP-4 owners can rule. **No whitepaper or code change is made by this memo** — these are consensus-economic genesis parameters; the decisions are theirs.

**Source of drift:** Surfaced by a Marshal gate on cowboy PR #169 (whitepaper §6.5 STF, §13.1 Parameter Governance Registry). Values below re-verified against `origin/devnet` on 2026-06-22.

---

## 1. Verified drift table (spec → current devnet code)

| Group | Parameter | Whitepaper | devnet code | Code source |
|-------|-----------|-----------|-------------|-------------|
| Basefee | `T_c` block cycles target | 10,000,000 | **20,000,000** | `types/src/constants.rs:79` |
| Basefee | `T_b` block cells target | 500,000 | **4,000,000** | `constants.rs:83` |
| Basefee | `alpha` (learning-rate denom) | 8 | **96** | `constants.rs:111` |
| Basefee | `delta` (max change) | 0.125 | **1/96 (≈0.0104)** | `constants.rs:115` |
| State rent | `rent_rate` | 0.001 CBY/byte/yr | **≈ 1 CBY/byte/yr** | `system:cip4:rent_config` |
| Lane budget | System share | 5% | **50% (LANE_SYSTEM_CYCLES = 40M)** | `constants.rs:99` |
| Lane budget | User share | 50% | **~28% (22,222,222)** | `constants.rs:88` |
| Lane budget | Runner share | 25% | **~11% (8,888,888)** | `constants.rs:91` |
| Lane budget | Timer share | 20% | **~11% (8,888,890)** | `constants.rs:94` |

Lanes sum to 80M = 4× `T_c`, forming the block hard cap.

---

## 2. Recommended canonical direction (per group)

### 2a. Basefee group (`T_c`, `T_b`, `alpha`, `delta`) → **spec follows code** (recommended)
The code values are deliberate and self-documented:
- `BASEFEE_ALPHA = 96` carries a rationale comment: it recalibrates Ethereum's 12s-block α=8 for Cowboy's 1s blocks (≈ 8 × 12). `delta` cap = `1/ALPHA` follows by construction.
- `T_c`/`T_b` were scaled together (4M cells stays proportional to 20M cycles).

These are internally consistent and intentional. Recommendation: **ratify the code values as canonical genesis economics** and update whitepaper §6.x/§13.1 to 20M / 4M / 96 / 1⁄96. This is a documentation update once ratified — but ratification is a governance act (it fixes genesis fee dynamics).

### 2b. State rent (`rent_rate`) → **decision needed; lean spec-follows-code, but confirm magnitude**
1000× drift (0.001 → ~1 CBY/byte/yr). Unlike basefee, the code value has no in-line rationale tying it to a target storage-cost-of-ownership. Before ratifying ~1 CBY/byte/yr, governance should confirm that is the intended economic weight (it sets the cost of on-chain storage and eviction pressure). Recommendation: **governance confirms the intended rent economics, then spec + code are aligned to the confirmed value** (likely code, but verify the magnitude is deliberate, not a placeholder).

### 2c. Lane budgets → **genuine semantic contradiction; needs a definition first, not just a value pick**
This is not a simple value drift — spec and code use **different semantics**:
- Whitepaper: lane percentages read as *reserved shares of block capacity* (System 5% / Timer 20% / Runner 25% / User 50%).
- Code: `LANE_*_CYCLES` are *absolute per-lane cycle ceilings* that sum to 4× `T_c`, with `LANE_SYSTEM_CYCLES = 2× T_c` specifically so a saturated system lane drives basefee to the EIP-1559 cap (`constants.rs` comment).

Under the code's "absolute ceiling" semantics, System is the *largest* lane (50% of the 80M cap), which **inverts** the whitepaper's "System 5%" reading. PR #169 inscribed the lane budgets into consensus-critical STF §6.5 step 2 without disclosing this divergence.

Recommendation — governance must first **decide what the whitepaper percentages mean**:
- (i) *Reserved minimum shares of the target `T_c`* (floors), orthogonal to the 4×-target absolute ceilings — in which case both can coexist and the spec should state both layers explicitly; or
- (ii) *The actual lane partition* — in which case either the spec percentages or the `LANE_*_CYCLES` constants must change to agree.

This is the highest-risk item (consensus-critical) and should **not** be resolved by unilaterally rewriting either side. It likely warrants a short CIP-3 erratum defining lane-budget semantics precisely.

---

## 3. Already done / not needed

- **Cross-reference fix (action #4):** the whitepaper §13.1 registry already cites **COW-2266** (not the earlier mistaken COW-1234) for the rent reconciliation (whitepaper line ~873). No action.
- **Verified-accurate (no drift):** the §3 cryptographic gas-cost table (BLS 8000 / Ed25519 5000 / secp256k1 10000 / SHA-256 500+8×blk / Keccak 6×32B / HKDF 1000) and all 12 governance storage keys in §13.1 match code.

---

## 4. Remaining open action items (after decisions)

1. Apply the ratified values to whitepaper §6.x/§13.1 (basefee + rent) — docs change, post-ratification.
2. Resolve lane-budget semantics (§2c) — likely a CIP-3 erratum — then align spec/code.
3. Land the CI drift check that §13.1 promises (rejects divergence between the registry table and `constants.rs` / `gas.rs`). **Blocked until 1–2 land** — it cannot pass against the current intentional drift.

---

**Ownership:** basefee/lane = CIP-3 (fee model); rent = CIP-4 (state rent). Per team scope these are other-team / governance decisions. This memo is the decision-ready analysis; the canonical-direction calls are theirs. A condensed version of §1–§2 was also posted as an English comment on COW-2266 (kept Todo).
