"""Generate two separate time-series charts (cycles, cells) for old vs new."""
import numpy as np
import matplotlib.pyplot as plt

BLOCKS = 180

NEW = dict(label="Current devnet (new)", color="#1f77b4",
           alpha=96, denom=96,
           cycles_target=20_000_000, cells_target=4_000_000,
           cycles_cap=80_000_000, cells_cap=16_000_000,
           init_cycle=1_000_000_000, init_cell=1_000_000_000,
           min_bf=1_000_000, asym_floor_bug=False, failed_counts_up=True)

OLD = dict(label="Early devnet (old)", color="#d62728",
           alpha=8, denom=8,
           cycles_target=5_000_000, cells_target=500_000,
           cycles_cap=20_000_000, cells_cap=2_000_000,
           init_cycle=1_000_000_000, init_cell=100_000_000,
           min_bf=1, asym_floor_bug=True, failed_counts_up=False)

def update_one(bf, used, target, alpha, denom, min_bf, bug):
    if target == 0:
        return bf
    bf = int(bf)
    max_delta = bf // denom
    if used > target:
        delta = min(bf * (used - target) // target // alpha, max_delta)
        nbf = bf + delta
    elif used < target:
        delta = min(bf * (target - used) // target // alpha, max_delta)
        if bug:
            delta = max(delta, 1)
        nbf = max(bf - delta, 0)
    else:
        nbf = bf
    return max(nbf, min_bf)

def simulate(p, dc, db, failed):
    cyc, cel = p["init_cycle"], p["init_cell"]
    C, B = [], []
    for d_c, d_b, f in zip(dc, db, failed):
        uc = min(int(d_c), p["cycles_cap"])
        ub = min(int(d_b), p["cells_cap"])
        if p["failed_counts_up"]:
            uc += f * 5_000
        cyc = update_one(cyc, uc, p["cycles_target"], p["alpha"], p["denom"],
                         p["min_bf"], p["asym_floor_bug"])
        cel = update_one(cel, ub, p["cells_target"], p["alpha"], p["denom"],
                         p["min_bf"], p["asym_floor_bug"])
        C.append(cyc); B.append(cel)
    return np.array(C), np.array(B)

rng = np.random.default_rng(7)
baseline_c, peak_c = 3_500_000, 52_000_000
baseline_b, peak_b =   700_000,  8_500_000
demand_c = np.full(BLOCKS, baseline_c, dtype=float)
demand_b = np.full(BLOCKS, baseline_b, dtype=float)

def hump(a, t0, t1, lo, hi, shape=1.0):
    for i in range(t0, t1):
        x = (i - t0) / (t1 - t0)
        a[i] += (hi - lo) * (np.sin(np.pi * x) ** shape)

hump(demand_c, 20, 75, baseline_c, peak_c, 1.2)
hump(demand_b, 20, 75, baseline_b, peak_b, 1.2)
hump(demand_c, 95, 165, baseline_c, peak_c * 0.88, 1.0)
hump(demand_b, 95, 165, baseline_b, peak_b * 0.88, 1.0)
demand_c *= 1 + rng.normal(0, 0.06, BLOCKS)
demand_b *= 1 + rng.normal(0, 0.06, BLOCKS)
demand_c = np.clip(demand_c, 200_000, None)
demand_b = np.clip(demand_b,  50_000, None)

failed = np.zeros(BLOCKS, dtype=int)
failed[50:70] = 3000

new_c, new_b = simulate(NEW, demand_c, demand_b, failed)
old_c, old_b = simulate(OLD, demand_c, demand_b, failed)
t = np.arange(BLOCKS)

def draw(dim_name, new_series, old_series, target_new, target_old, out_path,
         init_new, unit):
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(12, 11), sharex=True,
        gridspec_kw={"height_ratios": [0.9, 1.5, 1.3]})

    # Panel 1: offered load (as % of new target) so both regimes are visible.
    offered_new = (demand_c if dim_name == "cycles" else demand_b) / target_new
    ax1.fill_between(t, 0, offered_new, color="#999", alpha=0.35,
                     label="Offered load (× new target)")
    ax1.axhline(1.0, color=NEW["color"], ls=":", lw=1,
                label="New target (=1×)")
    ax1.axhline(target_new / target_old, color=OLD["color"], ls=":", lw=1,
                label=f"Old target (={target_new//target_old}× smaller)")
    ax1.axvspan(50, 70, color="orange", alpha=0.15, label="Failed-tx spam")
    ax1.set_ylabel(f"Offered {dim_name}\n(× new target)")
    ax1.set_title(f"180-second fluctuating load — {dim_name} dimension")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper right", fontsize=8, ncol=2)

    # Panel 2: log-scale old vs new — the headline.
    ax2.plot(t, new_series, color=NEW["color"], lw=2.2, label=NEW["label"])
    ax2.plot(t, old_series, color=OLD["color"], lw=2.2, label=OLD["label"])
    ax2.axvspan(50, 70, color="orange", alpha=0.08)
    ax2.set_yscale("log")
    ax2.set_ylabel(f"{dim_name}_basefee\n(atto{unit}, log scale)")
    ax2.set_title(f"{dim_name.capitalize()} basefee over 180s — old vs new (log)")
    ax2.grid(alpha=0.3, which="both")
    ax2.legend(loc="lower right", fontsize=9)

    ratio_old = old_series.max() / max(old_series.min(), 1)
    ratio_new = new_series.max() / max(new_series.min(), 1)
    ax2.text(0.02, 0.96,
             f"Volatility (max/min):\n"
             f"  new = {ratio_new:.2f}×\n"
             f"  old = {ratio_old:,.0f}×",
             transform=ax2.transAxes, va="top", fontsize=9,
             bbox=dict(boxstyle="round", fc="white", alpha=0.85, ec="#aaa"))

    # Panel 3: linear close-up of NEW only — see the micro-dynamics.
    ax3.plot(t, new_series / init_new, color=NEW["color"], lw=2.2,
             label=NEW["label"])
    ax3.axhline(1.0, color="#555", ls=":", lw=1, label="Genesis (=1.0)")
    ax3.axvspan(50, 70, color="orange", alpha=0.08)
    ax3.set_ylabel(f"{dim_name}_basefee\n(÷ 1e9, linear)")
    ax3.set_xlabel("Time (seconds / block height)")
    ax3.set_title(f"{dim_name.capitalize()} basefee — NEW only, linear close-up")
    ax3.grid(alpha=0.3)
    ax3.legend(loc="lower right", fontsize=9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    print(f"Saved: {out_path}")

draw("cycles", new_c, old_c,
     NEW["cycles_target"], OLD["cycles_target"],
     "/home/ubuntu/workspace/refs/202604/basefee_cycles_timeseries.png",
     NEW["init_cycle"], "CBY")

draw("cells", new_b, old_b,
     NEW["cells_target"], OLD["cells_target"],
     "/home/ubuntu/workspace/refs/202604/basefee_cells_timeseries.png",
     NEW["init_cell"], "CBY")

# Print narrative-useful metrics
print("\n=== Metrics for narrative ===")
print(f"Cycles  new  min={new_c.min():.3e}  max={new_c.max():.3e}  ratio={new_c.max()/new_c.min():.2f}x")
print(f"Cycles  old  min={old_c.min():.3e}  max={old_c.max():.3e}  ratio={old_c.max()/old_c.min():.2f}x")
print(f"Cells   new  min={new_b.min():.3e}  max={new_b.max():.3e}  ratio={new_b.max()/new_b.min():.2f}x")
print(f"Cells   old  min={old_b.min():.3e}  max={old_b.max():.3e}  ratio={old_b.max()/old_b.min():.2f}x")
print(f"\nBlocks where old cycle basefee >10x genesis: {(old_c > 1e10).sum()}")
print(f"Blocks where new cycle basefee >10x genesis: {(new_c > 1e10).sum()}")
print(f"Max cycle basefee spike (old / new): {old_c.max()/new_c.max():.1f}×")
print(f"Max cell  basefee spike (old / new): {old_b.max()/new_b.max():.1f}×")
