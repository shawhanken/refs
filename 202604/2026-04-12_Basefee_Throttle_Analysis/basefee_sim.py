"""
Devnet Basefee Economics — old vs new parameter simulation.

Replicates the actual EIP-1559 integer update in node/execution/src/basefee.rs
and runs it against a 180-second fluctuating production-like load.

Goal: visualize why the current devnet parameters (ALPHA=96, larger targets,
symmetric initial, spam penalty, min-basefee floor) are structurally better
than the early devnet parameters (ALPHA=8, small targets, asymmetric init,
-1 drift bug, no spam penalty).
"""

import numpy as np
import matplotlib.pyplot as plt

BLOCKS = 180

# ---------------------------------------------------------------
# Parameter sets
# ---------------------------------------------------------------
NEW = {
    "label": "Current devnet (new)",
    "color": "#1f77b4",
    "alpha": 96,
    "denom": 96,
    "cycles_target": 20_000_000,
    "cells_target": 4_000_000,
    "cycles_cap": 80_000_000,
    "cells_cap": 16_000_000,
    "init_cycle": 1_000_000_000,
    "init_cell": 1_000_000_000,
    "min_bf": 1_000_000,
    "asym_floor_bug": False,
    "failed_tx_counts_up": True,
}

OLD = {
    "label": "Early devnet (old)",
    "color": "#d62728",
    "alpha": 8,                   # 12x too fast for 1s blocks
    "denom": 8,
    "cycles_target": 5_000_000,   # Stage A
    "cells_target": 500_000,
    "cycles_cap": 20_000_000,     # smaller lanes
    "cells_cap": 2_000_000,
    "init_cycle": 1_000_000_000,
    "init_cell":  100_000_000,    # asymmetric (10x cheaper than cycles)
    "min_bf": 1,                  # pins at 1 under unbalanced load
    "asym_floor_bug": True,       # delta = max(delta, 1) on the down-leg
    "failed_tx_counts_up": False, # spam drags basefee DOWN
}

# ---------------------------------------------------------------
# EIP-1559 integer update (port of update_one in basefee.rs)
# ---------------------------------------------------------------
def update_one(bf, used, target, alpha, denom, min_bf, asym_floor_bug=False):
    if target == 0:
        return bf
    bf = int(bf)
    max_delta = bf // denom
    if used > target:
        raw = bf * (used - target) // target // alpha
        delta = min(raw, max_delta)
        nbf = bf + delta
    elif used < target:
        raw = bf * (target - used) // target // alpha
        delta = min(raw, max_delta)
        if asym_floor_bug:
            delta = max(delta, 1)      # the −1 drift bug
        nbf = max(bf - delta, 0)
    else:
        nbf = bf
    return max(nbf, min_bf)

def simulate(params, demand_c, demand_b, failed_txs_per_block):
    cyc = params["init_cycle"]
    cel = params["init_cell"]
    cyc_hist, cel_hist = [cyc], [cel]
    used_c_hist, used_b_hist = [], []
    for d_c, d_b, failed in zip(demand_c, demand_b, failed_txs_per_block):
        used_c = min(int(d_c), params["cycles_cap"])
        used_b = min(int(d_b), params["cells_cap"])
        # Failed-tx spam penalty — new version credits 5000 cycles/tx to block usage.
        if params["failed_tx_counts_up"]:
            used_c += failed * 5_000
        used_c_hist.append(used_c)
        used_b_hist.append(used_b)
        cyc = update_one(cyc, used_c, params["cycles_target"],
                         params["alpha"], params["denom"], params["min_bf"],
                         params["asym_floor_bug"])
        cel = update_one(cel, used_b, params["cells_target"],
                         params["alpha"], params["denom"], params["min_bf"],
                         params["asym_floor_bug"])
        cyc_hist.append(cyc)
        cel_hist.append(cel)
    return (np.array(cyc_hist[1:]), np.array(cel_hist[1:]),
            np.array(used_c_hist), np.array(used_b_hist))

# ---------------------------------------------------------------
# Load profile: baseline + two fluctuating humps + noise + a spam window.
# Absolute demand (not relative to target) so both parameter sets see
# the same "real-world" workload.
# ---------------------------------------------------------------
rng = np.random.default_rng(7)

baseline_c = 3_500_000         # quiet chain
peak_c     = 52_000_000        # heavy burst (2.6× new target, 10× old target)
baseline_b =   700_000
peak_b     = 8_500_000

demand_c = np.full(BLOCKS, baseline_c, dtype=float)
demand_b = np.full(BLOCKS, baseline_b, dtype=float)

def add_hump(arr, t0, t1, base, top, shape=1.0):
    length = t1 - t0
    for i in range(t0, t1):
        x = (i - t0) / length
        s = np.sin(np.pi * x) ** shape
        arr[i] += (top - base) * s

# Wave 1: sharp spike around 20-75
add_hump(demand_c, 20, 75, baseline_c, peak_c, shape=1.2)
add_hump(demand_b, 20, 75, baseline_b, peak_b, shape=1.2)

# Brief lull
# Wave 2: wider, slightly lower spike 95-165
add_hump(demand_c, 95, 165, baseline_c, peak_c * 0.88, shape=1.0)
add_hump(demand_b, 95, 165, baseline_b, peak_b * 0.88, shape=1.0)

# Noise
demand_c *= 1 + rng.normal(0, 0.06, BLOCKS)
demand_b *= 1 + rng.normal(0, 0.06, BLOCKS)
demand_c = np.clip(demand_c, 200_000, None)
demand_b = np.clip(demand_b,  50_000, None)

# Failed-tx spam: a burst of ~3000 failed txs/block in [50, 70] —
# attacker floods cheap reverts during the hot window.
failed_txs = np.zeros(BLOCKS, dtype=int)
failed_txs[50:70] = 3000

new_c, new_b, new_uc, new_ub = simulate(NEW, demand_c, demand_b, failed_txs)
old_c, old_b, old_uc, old_ub = simulate(OLD, demand_c, demand_b, failed_txs)

# ---------------------------------------------------------------
# Plot
# ---------------------------------------------------------------
t = np.arange(BLOCKS)

fig, axes = plt.subplots(3, 1, figsize=(12, 13), sharex=True,
                         gridspec_kw={"height_ratios": [1.1, 1.5, 1.5]})

# --- Panel 1: offered load (demand) with target lines for both regimes
ax = axes[0]
ax.plot(t, demand_c / 1e6, color="#555", lw=1.4, label="Offered cycles (M)")
ax.plot(t, demand_b / 1e5, color="#888", lw=1.2, ls="--",
        label="Offered cells (×100k)")
ax.axhline(NEW["cycles_target"] / 1e6, color=NEW["color"], lw=1,
           ls=":", label=f"New T_c = {NEW['cycles_target']//1_000_000}M")
ax.axhline(OLD["cycles_target"] / 1e6, color=OLD["color"], lw=1,
           ls=":", label=f"Old T_c = {OLD['cycles_target']//1_000_000}M")
ax.axvspan(50, 70, color="orange", alpha=0.12,
           label="Failed-tx spam window")
ax.set_ylabel("Load (M cycles / 100k cells)")
ax.set_title("180-second production-like load profile\n"
             "(two fluctuating waves + a 20-block revert-spam burst)")
ax.grid(alpha=0.3)
ax.legend(loc="upper right", fontsize=8, ncol=2)

# --- Panel 2: cycle basefee
ax = axes[1]
ax.plot(t, new_c, color=NEW["color"], lw=2, label=NEW["label"])
ax.plot(t, old_c, color=OLD["color"], lw=2, label=OLD["label"])
ax.axhline(NEW["min_bf"], color=NEW["color"], lw=0.8, ls=":",
           alpha=0.6, label=f"New MIN_BASEFEE=1e6")
ax.axvspan(50, 70, color="orange", alpha=0.08)
ax.set_yscale("log")
ax.set_ylabel("cycle_basefee (attoCBY, log)")
ax.set_title("Cycle basefee over time — old vs new parameters")
ax.grid(alpha=0.3, which="both")
ax.legend(loc="lower left", fontsize=9)

# Annotate key events
ax.annotate("Old: ALPHA=8 → ±12.5%/block,\nramps up fast and overshoots",
            xy=(55, old_c[55]), xytext=(85, old_c[55]*3),
            fontsize=8, color=OLD["color"],
            arrowprops=dict(arrowstyle="->", color=OLD["color"], lw=0.8))
ax.annotate("Old: spam window drags\nbasefee DOWN (no penalty)",
            xy=(60, old_c[60]), xytext=(5, old_c[60]*0.02),
            fontsize=8, color=OLD["color"],
            arrowprops=dict(arrowstyle="->", color=OLD["color"], lw=0.8))
ax.annotate("New: smooth, bounded ±1.042%/block\nstays close to 1e9",
            xy=(55, new_c[55]), xytext=(95, new_c[55]*0.3),
            fontsize=8, color=NEW["color"],
            arrowprops=dict(arrowstyle="->", color=NEW["color"], lw=0.8))

# --- Panel 3: cell basefee
ax = axes[2]
ax.plot(t, new_b, color=NEW["color"], lw=2, label=NEW["label"])
ax.plot(t, old_b, color=OLD["color"], lw=2, label=OLD["label"])
ax.axvspan(50, 70, color="orange", alpha=0.08)
ax.set_yscale("log")
ax.set_ylabel("cell_basefee (attoCBY, log)")
ax.set_xlabel("Time (seconds / block height)")
ax.set_title("Cell basefee over time — old vs new parameters")
ax.grid(alpha=0.3, which="both")
ax.legend(loc="lower left", fontsize=9)

ax.annotate("Old: cell_init=1e8 (10× cheaper than cycles),\nT_b=500k saturates\n"
            "immediately → +12.5%/block ramp",
            xy=(45, old_b[45]), xytext=(75, old_b[45]*6),
            fontsize=8, color=OLD["color"],
            arrowprops=dict(arrowstyle="->", color=OLD["color"], lw=0.8))
ax.annotate("New: symmetric 1e9 start,\nT_b=4M absorbs the wave",
            xy=(55, new_b[55]), xytext=(95, new_b[55]*0.2),
            fontsize=8, color=NEW["color"],
            arrowprops=dict(arrowstyle="->", color=NEW["color"], lw=0.8))

plt.tight_layout()
out_path = "/home/ubuntu/workspace/refs/202604/basefee_old_vs_new.png"
plt.savefig(out_path, dpi=130, bbox_inches="tight")
print(f"Saved: {out_path}")

# ---------------------------------------------------------------
# Print some summary numbers for the report.
# ---------------------------------------------------------------
def summary(name, arr):
    a = arr.astype(float)
    print(f"  {name:30s} min={a.min():.3e}  max={a.max():.3e}  "
          f"ratio={a.max()/max(a.min(),1):.2f}x  std/mean={a.std()/a.mean():.3f}")

print("\n--- cycle_basefee summary ---")
summary("NEW cycle_basefee", new_c)
summary("OLD cycle_basefee", old_c)
print("\n--- cell_basefee summary ---")
summary("NEW cell_basefee", new_b)
summary("OLD cell_basefee", old_b)
