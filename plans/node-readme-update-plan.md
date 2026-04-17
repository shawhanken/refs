# Plan: Update node/ READMEs on devnet branch

## Context

The user asked to update all README docs under `node/`, scoped to the current devnet branch. An audit comparing every first-party README against current code identified 7 concrete staleness issues — some constants are off by 2× (e.g. `BLOCK_CYCLES_TARGET` was doubled from 10M → 20M; `BLOCK_CELLS_TARGET` was raised from 500K → 4M), and several recent features (per-bytecode-instruction gas tracking, dual `/basefee` response shape, system actor addresses) aren't yet documented. The audit verified that most READMEs are already accurate; only a focused subset needs changes.

Out of scope (per user): `pvm/Lib/**`, `pvm/crates/vm/Lib/**`, `.pytest_cache/**`, `examples/**`, and other upstream/third-party trees.

## Verified facts driving edits

From `node/types/src/constants.rs`:
- Line 46: `BLOCK_CYCLES_TARGET = 20_000_000` (not 10M as CLAUDE.md states)
- Line 50: `BLOCK_CELLS_TARGET = 4_000_000` (not 500K)
- Line 66: `LANE_SYSTEM_CYCLES = 40_000_000`

`node/bench/README_CN.md:149` still quotes `BLOCK_CYCLES_TARGET(10M)` — the single stale reference in that file.

`node/execution/README.md` does not yet mention per-instruction gas tracking (commit 20dc11e) nor the basefee/EIP-1559 modules (`basefee.rs`, `gas.rs`).

`node/types/README.md` has a "Constants" section but no system actor address table (0x06, 0x09, 0x91–0x95).

## Changes (7 files)

### HIGH priority — factual corrections

1. **`node/bench/README_CN.md`** (line 149)
   - Replace `BLOCK_CYCLES_TARGET(10M)` with `BLOCK_CYCLES_TARGET(20M)`.
   - Scan surrounding throughput tables for any derived numbers that assumed 10M; fix or add a note if present.

### MEDIUM priority — missing documentation

2. **`node/execution/README.md`**
   - Add `basefee` and `gas` rows to the Modules table (covering `basefee.rs`, `gas.rs`).
   - Add a short "Gas Telemetry" subsection noting per-bytecode-instruction gas tracking (`instr_gas_accum` in `pvm_executor.rs`, `enable_gas` flag in `engine.rs`).

3. **`node/types/README.md`**
   - Add a "System Actor Addresses" table after the existing Constants section:
     - `0x06` Basefee, `0x09` Governance, `0x91` Runner Registry, `0x92` Job Dispatcher, `0x93` Result Verifier, `0x94` Secrets Manager, `0x95` TEE Verifier.
   - Merge the two separate "Constants" sections (lines 32 and 67) into one to remove duplication.

4. **`node/rpc/README.md`** (`/basefee` endpoint section, ~line 44 + response example around 140–152)
   - Expand the `/basefee` response example to show both `cycle_basefee` and `cell_basefee` as distinct `u128` fields.

### LOW priority — minor cleanups

5. **`node/tools/fee-simulator/README.md`**
   - Add one-line clarification at the top of the FEE TABLE section that the simulator defaults to `BLOCK_CYCLES_TARGET = 20_000_000` (matching current chain constant), noting the CIP-3 whitepaper §4.3 reference value of 10M is historical.

6. **`node/cli/README.md`** (line 233)
   - Either drop the hard-coded "14 recognized ids" count or verify against `types/src/registry.rs` and update. Simplest: change to "see `types/src/registry.rs` for the recognized ids" with no count.

7. **`node/validator/README.md`**
   - Add a cross-reference to `rpc/README.md` at the top of the duplicated RPC endpoint section (don't delete the content — it's used as a setup quick-ref — just point readers to the canonical doc).

## Files NOT touched (verified OK by audit)

`node/README.md`, `chain/README.md`, `storage/README.md`, `client/README.md`, `token/README.md`, `indexer/README.md`, `dev_runner/README.md`, `inspector/README.md`, `proof-verifier/README.md`, `pvm/README.md`, `bench/README.md` (EN), `runner/README.md`, `tools/fee-simulator/README_CN.md`.

## Verification

- Re-grep for stale constants after edits:
  - `grep -rn "10M\|10_000_000" node/bench node/tools node/execution node/types node/rpc node/cli node/validator` — should return zero hits referencing the block cycles target.
  - `grep -rn "500[_,]?000" node/` in basefee/target contexts — should show only legitimate values.
- Confirm every new system actor address matches `node/types/src/constants.rs` and `node/runner/src/system_actors.rs`.
- Open the changed READMEs and visually confirm Markdown tables render (no broken pipes / misaligned columns).
- `git diff --stat` should show exactly 7 files changed, all under `node/`, no code changes.

## Non-goals

- Rewriting any README from scratch.
- Translating between EN/CN variants (only fix factual drift in `bench/README_CN.md`).
- Touching `examples/**` or any `pvm/Lib/**` stdlib READMEs.
- Updating `CLAUDE.md` (even though its 10M/500K numbers are stale — that's a separate ask).
