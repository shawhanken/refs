"""
Throttle-effect demonstration — long-flood version.

Two experiments on the same axes:
  1. Sustained-overload throttle test: 200-block flood of 4000 tx/block
     (≈2× new target, ≈8× old target). Shows steady-state convergence.
  2. Spam-cost test: a 30-block window of 3000 reverts/block on top of the
     baseline. Shows that only the new parameters make spam expensive.

We plot:
  - offered / admitted / target
  - price-out fraction
  - cycle basefee (log)
  - cumulative attacker burn (for the spam test)
"""
import numpy as np
import matplotlib.pyplot as plt

CYCLES_PER_TX = 10_000

NEW = dict(label="Current devnet (new)", color="#1f77b4",
           alpha=96, denom=96,
           cycles_target=20_000_000, cells_target=4_000_000,
           cycles_cap=80_000_000,
           init_cycle=1_000_000_000, init_cell=1_000_000_000,
           min_bf=1_000_000, asym_floor_bug=False,
           failed_counts_up=True,
           spam_penalty=5_000)

OLD = dict(label="Early devnet (old)", color="#d62728",
           alpha=8, denom=8,
           cycles_target=5_000_000, cells_target=500_000,
           cycles_cap=20_000_000,
           init_cycle=1_000_000_000, init_cell=100_000_000,
           min_bf=1, asym_floor_bug=True,
           failed_counts_up=False,
           spam_penalty=0)

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

# ---------- simulation ----------
def simulate(p, offered, failed_txs, max_fee_median=1.5e9, sigma=0.35, seed=11):
    rng = np.random.default_rng(seed)
    cyc = p["init_cycle"]
    tx_cap = p["cycles_cap"] // CYCLES_PER_TX

    bf_h, offered_h, admitted_h, priced_out_h = [], [], [], []
    atk_cum = 0
    atk_h = []

    for t, (n_off, n_fail) in enumerate(zip(offered, failed_txs)):
        n_off = int(n_off)
        max_fees = rng.lognormal(np.log(max_fee_median), sigma, n_off)
        willing = int((max_fees >= cyc).sum())
        n_admit = min(willing, tx_cap)
        n_priced = n_off - willing

        used_cycles = n_admit * CYCLES_PER_TX
        if p["failed_counts_up"]:
            used_cycles += n_fail * p["spam_penalty"]

        # Attacker burn this block (basefee × cycles committed by failed tx).
        # On new: spam_penalty × basefee is charged; on old: failed tx don't
        # count so the attacker pays nothing for them in basefee terms.
        if p["failed_counts_up"]:
            atk_cum += n_fail * p["spam_penalty"] * cyc
        atk_h.append(atk_cum)

        bf_h.append(cyc)
        offered_h.append(n_off)
        admitted_h.append(n_admit)
        priced_out_h.append(n_priced)

        cyc = update_one(cyc, used_cycles, p["cycles_target"],
                         p["alpha"], p["denom"], p["min_bf"], p["asym_floor_bug"])

    return dict(bf=np.array(bf_h),
                offered=np.array(offered_h),
                admitted=np.array(admitted_h),
                priced_out=np.array(priced_out_h),
                atk=np.array(atk_h))

# ======================================================================
# Experiment A: 200-block sustained flood
# ======================================================================
BLOCKS_A = 320
offered_A = np.full(BLOCKS_A, 300, dtype=float)    # baseline
offered_A[40:240] = 4000                            # 200-block flood
rng_ = np.random.default_rng(99)
offered_A *= 1 + rng_.normal(0, 0.04, BLOCKS_A)
offered_A = np.clip(offered_A, 10, None)
failed_A = np.zeros(BLOCKS_A, dtype=int)           # no spam in this test

new_A = simulate(NEW, offered_A, failed_A)
old_A = simulate(OLD, offered_A, failed_A)

new_target_tx = NEW["cycles_target"] // CYCLES_PER_TX   # 2000
old_target_tx = OLD["cycles_target"] // CYCLES_PER_TX   #  500

# ======================================================================
# Experiment B: failed-tx spam window
# ======================================================================
BLOCKS_B = 180
offered_B = np.full(BLOCKS_B, 300, dtype=float)         # steady light traffic
offered_B *= 1 + rng_.normal(0, 0.04, BLOCKS_B)
failed_B = np.zeros(BLOCKS_B, dtype=int)
failed_B[50:90] = 3000                                  # 40-block revert spam

new_B = simulate(NEW, offered_B, failed_B)
old_B = simulate(OLD, offered_B, failed_B)

# ======================================================================
# Plot — one figure, six panels
# ======================================================================
fig = plt.figure(figsize=(14, 15))
gs = fig.add_gridspec(6, 1, height_ratios=[1, 1.3, 1.2, 1.0, 1.2, 1.2],
                      hspace=0.55)

t_A = np.arange(BLOCKS_A)

# --- A.1 offered demand
ax = fig.add_subplot(gs[0])
ax.fill_between(t_A, 0, offered_A, color="#666", alpha=0.35,
                label="Offered tx/block")
ax.axhline(new_target_tx, color=NEW["color"], ls=":", lw=1.2,
           label=f"NEW target = {new_target_tx}")
ax.axhline(old_target_tx, color=OLD["color"], ls=":", lw=1.2,
           label=f"OLD target = {old_target_tx}")
ax.axvspan(40, 240, color="orange", alpha=0.08,
           label="200-block sustained flood")
ax.set_ylabel("Offered tx/block")
ax.set_title("Experiment A — 200-block sustained overload "
             "(4000 offered tx/block, 2× new target, 8× old target)")
ax.grid(alpha=0.3)
ax.legend(loc="upper right", fontsize=8, ncol=2)

# --- A.2 admitted tx (the throttle output)
ax = fig.add_subplot(gs[1])
ax.plot(t_A, new_A["admitted"], color=NEW["color"], lw=2,
        label=f"{NEW['label']} — admitted")
ax.plot(t_A, old_A["admitted"], color=OLD["color"], lw=2,
        label=f"{OLD['label']} — admitted")
ax.axhline(new_target_tx, color=NEW["color"], ls=":", lw=1)
ax.axhline(old_target_tx, color=OLD["color"], ls=":", lw=1)
ax.axvspan(40, 240, color="orange", alpha=0.08)
ax.set_ylabel("Admitted tx/block")
ax.set_title("Throttle output — admitted tx/block. "
             "Must converge to TARGET and stay there")
ax.grid(alpha=0.3)
ax.legend(loc="upper right", fontsize=9)

# compute steady-state window (last 80 blocks of flood)
ss_range = (160, 240)
for p_name, r, tgt, col in [("NEW", new_A, new_target_tx, NEW["color"]),
                             ("OLD", old_A, old_target_tx, OLD["color"])]:
    ss = r["admitted"][ss_range[0]:ss_range[1]]
    mean = ss.mean()
    err = (mean - tgt) / tgt * 100
    cv = ss.std() / mean
    ax.text(0.02 if p_name == "NEW" else 0.22, 0.95,
            f"{p_name} steady-state (t=160-240):\n"
            f"  mean={mean:.0f}  (target {tgt})\n"
            f"  error={err:+.1f}%\n"
            f"  CV={cv:.3f}",
            transform=ax.transAxes, va="top", fontsize=8, color=col,
            bbox=dict(boxstyle="round", fc="white", alpha=0.85, ec=col))

# --- A.3 price-out fraction
ax = fig.add_subplot(gs[2])
new_pofrac = new_A["priced_out"] / np.maximum(new_A["offered"], 1) * 100
old_pofrac = old_A["priced_out"] / np.maximum(old_A["offered"], 1) * 100
ax.plot(t_A, new_pofrac, color=NEW["color"], lw=2, label=NEW["label"])
ax.plot(t_A, old_pofrac, color=OLD["color"], lw=2, label=OLD["label"])
ax.axvspan(40, 240, color="orange", alpha=0.08)
ax.set_ylabel("Priced-out users (%)")
ax.set_ylim(-2, 102)
ax.set_title("Price signal → user self-exclusion (max_fee < basefee)")
ax.grid(alpha=0.3)
ax.legend(loc="upper right", fontsize=9)

# --- A.4 basefee (log)
ax = fig.add_subplot(gs[3])
ax.plot(t_A, new_A["bf"], color=NEW["color"], lw=2, label=NEW["label"])
ax.plot(t_A, old_A["bf"], color=OLD["color"], lw=2, label=OLD["label"])
ax.axvspan(40, 240, color="orange", alpha=0.08)
ax.set_yscale("log")
ax.set_ylabel("cycle_basefee (attoCBY, log)")
ax.set_title("Control signal")
ax.set_xlabel("Time (s)")
ax.grid(alpha=0.3, which="both")
ax.legend(loc="upper right", fontsize=9)

# ======================================================================
# Experiment B panels
# ======================================================================
t_B = np.arange(BLOCKS_B)

ax = fig.add_subplot(gs[4])
ax.plot(t_B, new_B["bf"], color=NEW["color"], lw=2, label=NEW["label"])
ax.plot(t_B, old_B["bf"], color=OLD["color"], lw=2, label=OLD["label"])
ax.axvspan(50, 90, color="orange", alpha=0.15,
           label="3000 failed tx/block")
ax.set_yscale("log")
ax.set_ylabel("cycle_basefee (attoCBY, log)")
ax.set_title("Experiment B — failed-tx spam (light baseline traffic + 40-block revert flood).\n"
             "Does the basefee respond to spam?")
ax.grid(alpha=0.3, which="both")
ax.legend(loc="upper left", fontsize=9)

ax = fig.add_subplot(gs[5])
# Attacker total burn in CBY (1 CBY = 1e18 attoCBY)
ax.plot(t_B, new_B["atk"] / 1e18, color=NEW["color"], lw=2,
        label=f"{NEW['label']} — spam counts toward usage")
ax.plot(t_B, old_B["atk"] / 1e18, color=OLD["color"], lw=2,
        label=f"{OLD['label']} — spam = free (usage=0)")
ax.axvspan(50, 90, color="orange", alpha=0.15)
ax.set_ylabel("Attacker cumulative burn (CBY)")
ax.set_xlabel("Time (s)")
ax.set_title("Attacker cost of the revert-spam attack")
ax.grid(alpha=0.3)
ax.legend(loc="upper left", fontsize=9)

plt.suptitle("Basefee throttle effect: new vs old parameters",
             fontsize=14, y=0.995)

out = "/home/ubuntu/workspace/refs/202604/basefee_throttle_effect.png"
plt.savefig(out, dpi=130, bbox_inches="tight")
print(f"Saved: {out}")

# ---------------- printed metrics ----------------
def metrics(name, r, target_tx, flood=(40, 240)):
    a, b = flood
    window = r["admitted"][a:b]
    ss_start = (a + b) // 2
    ss = r["admitted"][ss_start:b]
    priced_total = int(r["priced_out"][a:b].sum())
    offered_total = int(r["offered"][a:b].sum())
    print(f"\n{name}  (target {target_tx} tx/block)")
    print(f"  flood admitted: mean {window.mean():.0f}, "
          f"max {window.max():.0f}, min {window.min():.0f}")
    print(f"  steady-state (last half): mean {ss.mean():.0f} "
          f"(error {(ss.mean()-target_tx)/target_tx*100:+.1f}%), "
          f"CV {ss.std()/ss.mean():.3f}")
    print(f"  priced-out ratio (flood): {priced_total/offered_total*100:.1f}%")
    print(f"  basefee final at flood end: {r['bf'][b-1]:.3e}")

print("\n=== Experiment A — sustained overload ===")
metrics("NEW", new_A, new_target_tx)
metrics("OLD", old_A, old_target_tx)

print("\n=== Experiment B — spam attack ===")
new_spam_bf_end = new_B["bf"][89]
old_spam_bf_end = old_B["bf"][89]
new_spam_bf_start = new_B["bf"][50]
old_spam_bf_start = old_B["bf"][50]
print(f"  NEW basefee during spam: {new_spam_bf_start:.2e} → {new_spam_bf_end:.2e}  "
      f"({new_spam_bf_end/new_spam_bf_start:.2f}×)")
print(f"  OLD basefee during spam: {old_spam_bf_start:.2e} → {old_spam_bf_end:.2e}  "
      f"({old_spam_bf_end/old_spam_bf_start:.2f}×)")
print(f"  NEW attacker total burn:  {new_B['atk'][-1]/1e18:.2f} CBY")
print(f"  OLD attacker total burn:  {old_B['atk'][-1]/1e18:.2f} CBY  (← no throttle, no cost)")
