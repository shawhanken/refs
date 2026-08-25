#!/usr/bin/env python3
"""Settlement-window sizing for a Cowboy-hosted CLOB exchange.

Companion to 20260825_hyperliquid_cowboy_component_mapping.md, section 9.
Every constant is quoted from node/ source with its file and line, so the result
can be re-derived against the tree at any commit.
"""
from math import exp, ceil

# --- PROVENANCE -----------------------------------------------------------
# node/types/src/constants.rs
BLOCK_CYCLES_TARGET   = 20_000_000     # :82  (WP 4.3 says 10M -- code diverges deliberately)
BLOCK_CELLS_TARGET    =  4_000_000     # :86  (WP 4.3 says 500k -- code diverges deliberately)
LANE_USER_CYCLES      = 22_222_222     # :90
LANE_RUNNER_CYCLES    =  8_888_888     # :94
DISPUTE_WINDOW_BLOCKS = 75             # :2003
BLOCK_SECONDS         = 1.0            # WP-v2 6.1/13, CIP-11 r1.2, CIP-23 r1

# node/execution/src/gas.rs (GasCosts::default)
BASE_CYCLES, BASE_CELLS                 = 5_000, 500
STORAGE_WRITE_CYCLES, STORAGE_WRITE_CELLS = 200, 1_000
TOKEN_TRANSFER_CYCLES, TOKEN_TRANSFER_CELLS = 1_000, 64
TOKEN_BATCH_PER_TRANSFER_CYCLES         = 500
TOKEN_BATCH_BASE_CYCLES                 = 500
JOB_RESULT_SUBMIT_CYCLES, JOB_RESULT_SUBMIT_CELLS = 50_000, 5_000
ACTOR_MSG_CYCLES, ACTOR_MSG_CELLS       = 10_000, 1_000
CALLDATA_CELLS_PER_BYTE                 = 1

ENTRY_CALLDATA_BYTES = 64   # addr(20) + i128 position delta + i128 collateral delta + pad
PVM_LOOP_CYCLES      = 2_000  # charged cost of one interpreted loop iteration

# --- two settlement encodings --------------------------------------------
# A) "position-write": each account's position is actor state -> 1 storage write
#    inside a PVM loop, plus a collateral leg.
ENTRY_A_CELLS  = ENTRY_CALLDATA_BYTES*CALLDATA_CELLS_PER_BYTE + STORAGE_WRITE_CELLS + TOKEN_TRANSFER_CELLS
ENTRY_A_CYCLES = STORAGE_WRITE_CYCLES + PVM_LOOP_CYCLES + TOKEN_BATCH_PER_TRANSFER_CYCLES + TOKEN_TRANSFER_CYCLES

# B) "token-only": position is represented as a CIP-20 balance, so settlement is
#    a native batch transfer -- Rust, no PVM loop.
ENTRY_B_CELLS  = ENTRY_CALLDATA_BYTES*CALLDATA_CELLS_PER_BYTE + TOKEN_TRANSFER_CELLS
ENTRY_B_CYCLES = TOKEN_BATCH_PER_TRANSFER_CYCLES + TOKEN_TRANSFER_CYCLES

FIXED_CELLS  = BASE_CELLS + JOB_RESULT_SUBMIT_CELLS + ACTOR_MSG_CELLS + TOKEN_TRANSFER_CELLS
FIXED_CYCLES = BASE_CYCLES + JOB_RESULT_SUBMIT_CYCLES + ACTOR_MSG_CYCLES + TOKEN_BATCH_BASE_CYCLES

def capacity(entry_cells, entry_cycles, lane_cycles, phi):
    """Max settled accounts per block. phi = fraction of the cell target we claim."""
    by_cells  = (phi*BLOCK_CELLS_TARGET - FIXED_CELLS) / entry_cells
    by_cycles = (lane_cycles - FIXED_CYCLES) / entry_cycles
    return max(0, int(min(by_cells, by_cycles))), ("cells" if by_cells < by_cycles else "cycles")

def distinct_accounts(N_active, fills_per_sec, W):
    """Occupancy: distinct accounts touched by 2*F*W account-slots over N_active."""
    slots = 2.0*fills_per_sec*W
    return N_active*(1.0 - exp(-slots/N_active))

print("="*78)
print("PER-ENTRY COST")
print("="*78)
print(f"  A position-write : {ENTRY_A_CELLS:>6} cells  {ENTRY_A_CYCLES:>7} cycles")
print(f"  B token-only     : {ENTRY_B_CELLS:>6} cells  {ENTRY_B_CYCLES:>7} cycles")
print(f"  fixed per batch  : {FIXED_CELLS:>6} cells  {FIXED_CYCLES:>7} cycles")

print()
print("="*78)
print("CAPACITY  (settled accounts per 1s block)")
print("="*78)
print(f"{'encoding':<16}{'lane':<10}{'phi':<7}{'accts/block':>13}  binds")
print("-"*78)
rows = {}
for name, ec, ecy in (("A position-write", ENTRY_A_CELLS, ENTRY_A_CYCLES),
                      ("B token-only",     ENTRY_B_CELLS, ENTRY_B_CYCLES)):
    for lane_name, lane in (("RUNNER", LANE_RUNNER_CYCLES), ("USER", LANE_USER_CYCLES)):
        for phi in (0.25, 0.50, 1.00):
            cap, binds = capacity(ec, ecy, lane, phi)
            print(f"{name:<16}{lane_name:<10}{phi:<7.2f}{cap:>13,}  {binds}")
            rows[(name, lane_name, phi)] = cap

print()
print("="*78)
print("PER-BLOCK SETTLEMENT FEASIBILITY  (W = 1 block)")
print("="*78)
print("At W=1 there is no netting: load = 2 x fills/sec (both sides of each fill).")
print(f"{'encoding / lane / phi':<34}{'max sustainable fills/sec':>27}{'fills/day':>16}")
print("-"*78)
for k in [("A position-write","RUNNER",0.50), ("A position-write","USER",0.50),
          ("B token-only","RUNNER",0.50),     ("B token-only","USER",0.50),
          ("B token-only","USER",1.00)]:
    C = rows[k]
    F_max = C/2.0
    print(f"{k[0]+' / '+k[1]+' / '+format(k[2],'.2f'):<34}{F_max:>27,.0f}{F_max*86400:>16,.0f}")

print()
print("="*78)
print("WHEN W=1 IS NOT ENOUGH: required window at the netting knee")
print("="*78)
C = rows[("B token-only","USER",0.50)]
print(f"capacity C = {C:,} accounts/block  (encoding B, USER lane, phi=0.50)")
print(f"{'N_active':>10}{'fills/sec':>11}{'knee W*':>10}{'min feasible W':>16}{'accts/batch':>13}{'load/s':>9}")
print("-"*78)
for N_active in (5_000, 50_000):
    for F in (100, 1_000, 5_000, 20_000):
        knee = N_active/(2.0*F)
        W = 1
        while W <= 3600:
            B = distinct_accounts(N_active, F, W)
            if B/W <= C: break
            W += 1
        B = distinct_accounts(N_active, F, W)
        flag = "" if W <= 3600 else " INFEASIBLE"
        print(f"{N_active:>10,}{F:>11,}{knee:>10.1f}{W:>16,}{B:>13,.0f}{B/W:>9,.0f}{flag}")

print()
print("="*78)
print("TIME TO FINALITY")
print("="*78)
for W in (1, 5, 15, 60):
    print(f"  W={W:>3}s  ->  settle {W}s + dispute {DISPUTE_WINDOW_BLOCKS}s = {W+DISPUTE_WINDOW_BLOCKS}s to final")
