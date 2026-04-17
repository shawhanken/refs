# Plan: Lower basefee constants to fix excessive transfer fees

## Context

A simple 10 CBY transfer costs ~21 CBY total (10 transfer + ~11 gas) even when the network is completely idle and basefee is at the absolute floor (`MIN_BASEFEE`). Root cause: the token has 9-digit precision (1 CBY = 1e9 internal units), but basefee constants were set assuming 18-digit precision (like Ethereum). This makes `MIN_BASEFEE = 1,000,000` result in a minimum cost of **0.001 CBY per cycle**, and a transfer (10,000 cycles) costs **10+ CBY** in gas alone.

**Fix**: Reduce `MIN_BASEFEE` and `INITIAL_*_BASEFEE` by 100×. This is purely an economic parameter change — no gas costs, lane budgets, or TPS characteristics are altered.

## New Values

| Constant | Current | New | Rationale |
|---|---|---|---|
| `MIN_BASEFEE` | 1,000,000 | **10,000** | Transfer floor fee: 11,070 × 10,000 / 1e9 ≈ **0.11 CBY**. Passes compile-time assert: 10,000 ≥ 96 × 100 = 9,600 |
| `INITIAL_CYCLE_BASEFEE` | 1,000,000,000 | **1,000,000** | 100× MIN. Genesis transfer ≈ 11 CBY, decays to floor in ~7 min idle. Keeps 3 orders of magnitude headroom for EIP-1559 ramp. |
| `INITIAL_CELL_BASEFEE` | 1,000,000,000 | **1,000,000** | Symmetric with cycles |

### Fee comparison (simple transfer: 10,000 cycles + ~1,070 cells)

| Scenario | Current | After |
|---|---|---|
| At MIN_BASEFEE (idle) | 11.07 CBY | **0.11 CBY** |
| At genesis INITIAL | 11,070 CBY | **11.07 CBY** (decays in ~7 min) |
| Max Fee pre-check (50k/50k limits, at MIN) | 125 CBY | **1.25 CBY** |

### Performance impact: NONE
- `BLOCK_CYCLES_TARGET`, `BLOCK_CELLS_TARGET` unchanged
- All gas costs (`base_cycles`, `transfer_cycles`, etc.) unchanged
- Lane budgets unchanged
- TPS capacity unchanged

### EIP-1559 behavior at new MIN_BASEFEE = 10,000
- `max_delta = 10,000 / 96 = 104` — well above truncation zone
- 1% overload delta: `10,000 × 0.01 / 96 ≈ 1` — still non-zero
- Compile-time assert: `10,000 >= 96 * 100 = 9,600` ✓

## Files to Modify

### 1. `types/src/constants.rs` (lines 84-108)
- Change `INITIAL_CYCLE_BASEFEE`: `1_000_000_000` → `1_000_000`
- Change `INITIAL_CELL_BASEFEE`: `1_000_000_000` → `1_000_000`
- Change `MIN_BASEFEE`: `1_000_000` → `10_000`
- Update associated doc comments (fix "attoCBY" → just clarify units match balance denomination, update fee calculation examples)

### 2. `execution/src/basefee.rs` — tests only
- Tests at lines 239, 240, 266, 267 etc. use `1_000_000_000` as arbitrary basefee test values → these are ≥ new MIN (10,000), **no change needed**
- Serialization roundtrip test (line 384-397) hardcodes `1_000_000_000` → **no change needed** (testing serde, not constants; values ≥ MIN)
- Tests using `MIN_BASEFEE` constant directly (lines 323-335, 529-549, 646-655) → **auto-adapt**, no change needed

### 3. `rpc/src/responses.rs` (line 491-498) — update example values
- Change `"1000000000"` → `"1000000"` and `"1100000000"` → `"1250000"`, `"110000000"` → `"125000"` (suggested = basefee × 1.25)

### 4. `rpc/src/openapi.rs` (line 727-733) — update example values
- Same changes as responses.rs

### 5. `rpc/src/handlers/chain.rs` (lines 1119-1120, 1555-1563) — update test fixtures
- `basefee_response_fields_are_strings` test: values are arbitrary, **no functional change needed** (just testing string type)
- `basefee_response_round_trip` test: update hardcoded values to match new INITIAL for documentation consistency

### 6. `rpc/src/rpc.rs` (line 997-998) — update test fixture
- Update suggested_max_fee test values

### 7. `execution/src/execution/tests.rs`
- Test `basefee_too_low_rejected` (line 1027): explicitly sets basefee to `1_000_000` — still works (1 < 1,000,000), **no change needed**
- Tests with `max_fee = 2_000_000_000`: still >> new MIN_BASEFEE (10,000), **no change needed**
- Comment at line 3657 says "≥ MIN_BASEFEE" — still true, **no change needed**

### 8. `execution/src/execution/engine.rs` (lines 97-98, 116-117)
- Uses `crate::basefee::MIN_BASEFEE` (re-exported constant) → **auto-adapts**, no change needed

## Impact on Existing Devnet

The current devnet has basefee stored as ~1,000,000 (at old MIN floor). After deploying new code:
- `load_from_storage` clamp: stored value (1,000,000) > new MIN (10,000), so it loads as-is
- Basefee will decay from 1,000,000 to 10,000 over ~7 min of idle blocks
- No immediate disruption; fees gradually decrease

## Verification

1. **Compile-time**: `cargo build --workspace` — the basefee.rs compile-time assert (`MIN_BASEFEE >= BASEFEE_MAX_CHANGE_DENOM * 100`) must pass
2. **Unit tests**: `cargo test --workspace` — all ~130+ tests pass
3. **Specific basefee tests**: `cargo test -p cowboy-execution -- basefee --nocapture`
4. **E2E**: Start validator, check `/basefee` endpoint returns new values, send a transfer and verify fee ≈ 0.11 CBY
