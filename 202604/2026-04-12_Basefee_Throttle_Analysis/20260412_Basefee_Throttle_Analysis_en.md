# Devnet Basefee Throttle Analysis: New vs Old Parameters

**Document date:** 2026-04-12
**Scope:** Cowboy `devnet` on-chain economic parameters
**Companion document:** [`20260412_Devnet_Basefee_Economics_en.md`](20260412_Devnet_Basefee_Economics_en.md) (evolution timeline)
**Simulation scripts:** `basefee_sim_split.py`, `basefee_throttle.py` (integer arithmetic ported line-by-line from `node/execution/src/basefee.rs::update_one`)

---

## 0. Executive Summary

Under a 180-second production-like fluctuating load, the early devnet parameters cause `cycle_basefee` to span **5 orders of magnitude** and `cell_basefee` to span **7 orders of magnitude**—the cost of the same transfer can differ by a factor of ~100,000 within a two-minute window. The current devnet lifts `BASEFEE_ALPHA` from 8 to 96 (to match 1-second block cadence), raises `BLOCK_CYCLES_TARGET` from 5M to 20M, symmetrizes the genesis price, adds usage accounting for failed transactions, and raises `MIN_BASEFEE` structurally above the integer-truncation region. Against the identical demand curve:

| Metric | Early devnet | Current devnet | Improvement |
|---|---:|---:|---|
| `cycle_basefee` max/min | **393,144×** | **1.71×** | 5 orders of magnitude |
| `cell_basefee` max/min | **30,985,936×** | **1.33×** | 7 orders of magnitude |
| basefee change during spam window | **−87%** (inverted) | **−4%** (stable) | direction reversed |
| Attacker cost for a 40-block spam burst | 0.00 CBY | 0.37 CBY | free → paid |
| Idle-recovery half-life | unstable (freezes at floor) | **66 blocks** | predictable |

The core finding: the new parameters are not about making the chain "cheaper" or "more expensive"—**they move the EIP-1559 control loop out of a chaotic-saturation regime and into its linear-response regime**.

---

## 1. Parameter Comparison

Parameters are drawn from `node/types/src/constants.rs` and `node/execution/src/basefee.rs`.

| Dimension | Early devnet (old) | Current devnet (new) | Notes |
|---|---|---|---|
| `BASEFEE_ALPHA` | 8 | **96** | Learning-rate denominator; 96 matches 1 s block cadence |
| `BASEFEE_MAX_CHANGE_DENOM` | 8 | **96** | Per-block change cap |
| Per-block max change | ±12.5% | **±1.042%** | 96-block cumulative ≈ Ethereum 12 s block ±12.5% |
| `BLOCK_CYCLES_TARGET` | 5M | **20M** | Aligned with 1500–2500 tps operating band |
| `BLOCK_CELLS_TARGET` | 500k | **4M** | Scaled with cycles |
| Per-block hard cap (all lanes) | ~20M | **80M** (4×T_c) | System lane 40M = 2×T_c |
| `INITIAL_CYCLE_BASEFEE` | 1e9 | 1e9 | Unchanged |
| `INITIAL_CELL_BASEFEE` | **1e8** (asymmetric) | **1e9** (symmetric) | Fixes asymmetric price signal |
| `MIN_BASEFEE` | 1 | **1e6** | Structurally ≥ `DENOM × 100`, out of truncation region |
| Down-step symmetry | `max(delta, 1)` bug | Pure geometric update | Removes −1 drift |
| Failed-tx usage accounting | No | **Yes** | `BASE_CYCLES_SPAM_PENALTY = 5000` |

---

## 2. Methodology

### 2.1 Formula Port

The simulation directly ports the integer arithmetic of `update_one`:

```text
delta       = basefee × (used − target) / target / ALPHA
delta       = min(delta, basefee / DENOM)        # per-block change cap
new_basefee = clamp(basefee ± delta, MIN_BASEFEE, MAX_BASEFEE)
```

The early version carries two additional known defects:
- **Symmetry bug:** `delta = max(delta, 1)` on the down-leg injects a −1 constant drift; the basefee is drained to the floor under mildly-under-target load.
- **Spam blind spot:** failed transactions contribute `used_cycles = 0`, so a spam burst looks like "suddenly idle" from the basefee controller's point of view.

### 2.2 Two Load Profiles

- **Profile A (fluctuating production load):** 180 seconds, two sinusoidal peaks plus 6% normal noise, with a 20-block failed-tx spam window. Used in experiments 1 and 2.
- **Profile B (step-function overload + spam attack):** 320 seconds = 40 s baseline + 200 s flood + 80 s recovery; plus a separate 180-second spam-only test. Used in experiment 3.

Both profiles feed the **absolute demand** to both parameter sets—any difference in behavior comes entirely from the economic parameters themselves.

### 2.3 User Demand Model (Experiment 3)

Each block, N users arrive with `max_fee_per_cycle ~ Lognormal(ln(1.5e9), σ=0.35)`. A user is admitted iff `max_fee ≥ basefee` and there is lane capacity. This models the real price-discovery process: only users willing to pay enter the block, the rest are **priced out**.

---

## 3. Experiment 1: Cycles Basefee Time-Series under Fluctuating Load

![cycles timeseries](basefee_cycles_timeseries.png)

**Quantitative comparison (max/min ratio):**
- **NEW = 1.71×** (stays near 1e9, high 1.38e9, low 0.81e9)
- **OLD = 393,144×** (climbs from 4.3e8 all the way to 1.68e14, spanning 5.5 orders of magnitude)

**Walkthrough** (following the red line left to right):

1. **t = 0–20 s, baseline segment:** demand is 3.5M, well below the old target of 5M. The formula-computed delta would be a few hundred, but `max(delta, 1)` anchors it to a −1 constant drift and the old basefee slowly decays from 1e9. This is the root cause of the 2026-04-11 bench incident: "under mild underload, basefee gets drained." The new parameters use the true proportional delta, dipping steadily to 0.81× before naturally recovering.
2. **t = 20–50 s, first rising wave:** demand climbs linearly from 3.5M to 52M. **The old parameters have a per-block hard cap of only 20M**, so from t=30s every block is pinned at 2×T_c and beyond. With ALPHA=8 ⇒ +12.5%/s compounded ⇒ basefee grows ~35× in 30 seconds. The new parameters, with ALPHA=96 (matching 1 s cadence), rise only 1.18× under the same overload.
3. **t = 50–70 s, failed-tx storm (orange band):** the attacker floods 3000 reverts/block during the most expensive window. **Old parameters record failed-tx usage as 0**—from the basefee controller's view this looks like "sudden cooling," and the red line shows a small dip around t=60. This moves the basefee in the **wrong direction** for throttling. The new parameters credit `5000 × 3000 = 15M cycles` to `used`, which actually tightens things further—the anti-spam mechanism working as intended.
4. **t = 70–180 s, second wave:** with ALPHA=8, even the +1.042% per-block cap cannot contain the sustained overload; the old basefee climbs geometrically to 1.68e14 (≈170,000× the genesis price). Even in the second-wave trough (around t=180 s), the old basefee only falls from the peak to 8e13—the **66-block half-life** compresses to ≈5.5 blocks under ALPHA=8, but the basefee first has to come down, and the sustained fluctuation never lets it. The new parameters rise gently to 1.38× during the second wave and retreat calmly into the troughs.

**Bottom panel (new-only, linear close-up):** you can see the real behavior—two tidal cycles of 0.8× → 1.2× → 1.0×, perfectly tracking the load rhythm; the spam window only lifts the curve slightly above the no-attack baseline. **This is exactly what CIP-3 §2.4 asks for: fast enough to respond, slow enough to stay stable.**

---

## 4. Experiment 2: Cells Basefee Time-Series under Fluctuating Load

![cells timeseries](basefee_cells_timeseries.png)

**Quantitative comparison:**
- **NEW = 1.33×** (0.80e9 → 1.06e9, extremely gentle)
- **OLD = 30,985,936×** (1e8 → 3.24e15, nearly 7.5 orders of magnitude)

**Walkthrough:**

1. **The decisive effect of scaling T_b by 8×:** old `BLOCK_CELLS_TARGET = 500k`, and the peak demand of 8.5M cells equals **17× the old target**. The old cell basefee enters its full-rate climb at the very beginning of the first wave. With new `BLOCK_CELLS_TARGET = 4M`, the peak is only **2.1× the new target**—exactly the "signal but do not panic" region.
2. **Why a symmetric genesis price matters:** the old initial cell basefee = 1e8 (10× cheaper than cycles), sending users **the false signal that "data is cheap."** When the peak arrives, the price compounds from a 1e8 starting point under ALPHA=8 and reaches 1e15 within 5 minutes—a fatal price cliff for any DApp. The new parameters start symmetrically at 1e9, and even in the worst-case scenario the price only climbs 6%.
3. **Failed-tx storms have almost no effect on cells** (failed txs rarely write data), so the orange window shows no inflection on the cells chart. This confirms that failed-tx spam is primarily a **compute-lane attack vector**, and the new parameters specifically add a spam penalty to the compute lane.
4. **Bottom panel (new-only, linear close-up):** two smooth 0.80 ↔ 1.06 oscillations, in phase with the load, amplitude about ±13%, as regular as a sine wave. **The control loop shows neither phase lag nor ringing**—the ALPHA=96 damping sits exactly between underdamped and critically damped.

---

## 5. Throttle Effectiveness: Four Measurable Dimensions

In one sentence: **throttling is not a single metric—it is a composite of four orthogonal properties.** Each dimension needs its own experiment and its own observable.

![throttle effect](basefee_throttle_effect.png)

### 5.1 Dimension 1: Price-Based Clearing (price discovery)

**Observable:** does `admitted tx/block` converge to the target in steady state?

**Experiment A results (200-block sustained flood, 4000 offered tx/block):**

| | target | steady-state admitted | error | CV |
|---|---:|---:|---:|---:|
| **NEW** | 2000 | 2188 | +9.4% | 0.071 |
| **OLD** |  500 |  499 | −0.2% | 0.077 |

At first glance both converge. **But look at the opening of the flood in the second panel:** OLD's admitted is pinned at exactly 2000—that is `cycles_cap = 20M / 10k = 2000`, the **per-block hard cap**. OLD's first 20 blocks are "cap-bound throttling" (binary), not "price-based clearing." NEW produces a smooth 4190 → 2188 **price curve**, filtering out 31.7% of marginal users through price signals.

> **Takeaway:** NEW lets the basefee itself price the excess demand out; OLD's warm-up relies on the per-block hard cap. The latter is not how EIP-1559 is supposed to work.

### 5.2 Dimension 2: Stability (low variance, low CV)

**Observable:** basefee's max/min ratio and std/mean under real fluctuating load.

Under sustained overload, both regimes show CV ~0.07. But experiments 1 and 2 have already proven: **under 1-second-scale demand pulses, OLD basefee spans 5 to 7 orders of magnitude**. The reason is that ALPHA=8 makes OLD react violently (±12.5%/s) to every peak and trough, while NEW's ±1.042%/s provides sufficient damping.

> **Takeaway:** sustained overload is the easy case for EIP-1559; the real challenge is cumulative stability under 1-second-scale pulses. On the fluctuating-load test, NEW's cycles volatility ratio is 1.71× vs OLD's 393,144×—this is the value of damping.

### 5.3 Dimension 3: Spam Resistance (failed tx must count toward usage)

**Observable:** the direction of basefee within the spam window, and the attacker's cumulative cost.

**Experiment B results (300 tx/block baseline + 40 blocks × 3000 failed tx/block):**

| | basefee change during spam | attacker cumulative burn |
|---|---|---:|
| **NEW** | 6.38e8 → 6.12e8 (−4%, stable) | **0.37 CBY** |
| **OLD** | 7.08e7 → **9.38e6 (−87%)** | **0.00 CBY** |

This is the most striking data point: **during the attack, OLD's basefee actually drops by 87%.** The reason is that OLD does not count failed-tx cycles toward `used`, so the chain looks **quieter than usual** (only the 300-tx baseline traffic remains, well below target), and basefee follows the under-load rule downward. The consequences:

- The attacker pays nothing
- **Normal users' gas actually becomes cheaper during the attack**
- While the chain is under attack, the basefee signal tells the world "it's idle, come on in"

NEW credits `BASE_CYCLES_SPAM_PENALTY = 5000` to usage, so during the spam window `used = 300·10k + 3000·5k = 18M`, close to the target of 20M, and basefee holds steady. The attacker must pay real CBY for the cycles they consume.

> **Takeaway:** spam resistance is the hardest test of throttling. Under OLD, the basefee is actively **pushed downward** by the attacker—this is not throttle failure, it is anti-throttling. NEW makes the attacker pay 0.37 CBY for a 40-second attack, which is exactly what CIP-3 §17.2 intends.

### 5.4 Dimension 4: Predictable Recovery (Half-Life)

**Observable:** the time constant for basefee to return to genesis after a flood ends.

- **NEW's under-load decay is `bf/96` per block**, and the analytical half-life is `log(0.5) / log(95/96) ≈ 66 blocks = 66 seconds`. This is a **fixed number you can put in an SLA**.
- **OLD's `max(delta, 1)` bug** means the decay at low values is dominated by the −1 constant, so the half-life "depends on the current basefee value," and in the range `[1, 8)` it freezes altogether—which is precisely how the 2026-04-11 bench incident arose.

> **Takeaway:** users and wallets need to know "how long until prices come back down after a peak." NEW offers a 66-second half-life commitment; OLD cannot give any deterministic answer.

---

## 6. Why the New Parameters Are Better: Cause-Effect Table

Every phenomenon on the charts traces back to a specific parameter change or bug fix:

| Phenomenon on the chart | Root cause | Parameter change | Real-world benefit |
|---|---|---|---|
| OLD red line explodes exponentially to 1e14/1e15 | ALPHA=8 is 12× too fast for 1 s blocks | `BASEFEE_ALPHA: 8 → 96` | Per-second adjustment rate aligns with Ethereum's 12 s blocks; five-minute fluctuations no longer drive price to absurd levels |
| OLD red line spends most of its time in the "max rate" region | T_c=5M / T_b=500k are too small | Targets scaled by **4× / 8×** | Production load falls within the target band; EIP-1559 operates in its linear-response region, not saturated at the cap |
| OLD cell basefee starts 10× cheaper | Asymmetric genesis price | Initial cell 1e8 → **1e9** | Both resources priced on the same scale; wallet strategy simplifies |
| OLD line drifts down to 1 during underload | `max(delta,1)` bug + `MIN_BASEFEE=1` | Remove asymmetric drift; **`MIN_BASEFEE=1e6`** structurally ≥ `DENOM × 100` | Under-load basefee honestly reflects demand, no longer freezes |
| OLD line flips negative 87% during spam window | Failed-tx usage recorded as 0 | **`BASE_CYCLES_SPAM_PENALTY=5000`** counts toward usage | Anti-spam throttle direction is correct; attackers must pay |
| OLD line hits 20M per-block hard cap on the first wave | Lane total is too small | Lane total **20M → 80M** (System 40M = 2×T_c) | A single System-lane flood can saturate EIP-1559 response; bandwidth headroom ≈ 2000–4000 tps transfers |
| OLD throttles by hitting the cap, not by price | Early `cycles_cap`/target ratio is too small | Lane recalibration + target expansion | Marginal-user clearing is done by price signal, not "first come, first served" |

---

## 7. Scope and Limits of the Findings

- **Not a claim that "NEW is cheaper":** under sustained overload both regimes price marginal users out—this is not a cost question.
- **Not a claim that "NEW responds faster":** NEW's single-block convergence is actually 12× slower than OLD (ALPHA=96 is deliberate: slower steps mean better damping).
- **Only a claim about throttle quality** (smoothness, price mechanism, spam resistance, predictable recovery)—these are what EIP-1559 is actually responsible for.

---

## 8. Conclusion

> Under the same 180-second twin-peak production-like load profile, the early devnet parameters span 5 orders of magnitude on `cycle_basefee` and 7 on `cell_basefee`—the cost of the same transfer can differ by ~100,000× within two minutes, which is unacceptable for any DApp. The root cause is not the formula, but three **parameter mismatches** (ALPHA inherited from Ethereum's 12 s blocks, targets drawn from an early throughput vision, asymmetric initial prices) plus two **implementation bugs** (−1 drift, failed txs not counted toward usage).
>
> The current devnet lifts ALPHA to 96 to match 1-second block cadence, raises targets to 20M/4M to match the 1500–2500 tps operating band, symmetrizes the initial price, adds the spam penalty, and moves `MIN_BASEFEE` structurally above the integer-truncation region. **Against the identical load curve, the cycles basefee volatility ratio drops from 393,144× to 1.71×, and cells from 30,985,936× to 1.33×**; during spam the basefee no longer flips downward, and the attacker moves from free to paid; idle recovery now has a deterministic 66-second half-life.
>
> This is not a matter of cheaper, more expensive, or more conservative—**it is about moving the pricing mechanism into its linear-response region**, making the protocol constants coherent with the physical block cadence and the product-level throughput target. Throttling is the outcome; parameter alignment is the cause.

---

## Appendix: Chart Index

| Experiment | File | Description |
|---|---|---|
| 1 | [`basefee_cycles_timeseries.png`](basefee_cycles_timeseries.png) | Cycles basefee time-series (fluctuating load, 180 s) |
| 2 | [`basefee_cells_timeseries.png`](basefee_cells_timeseries.png) | Cells basefee time-series (fluctuating load, 180 s) |
| 3 | [`basefee_throttle_effect.png`](basefee_throttle_effect.png) | Four-dimensional throttle evaluation (sustained overload + spam) |
| Overview | [`basefee_old_vs_new.png`](basefee_old_vs_new.png) | Combined three-panel view (load + cycles + cells) |
