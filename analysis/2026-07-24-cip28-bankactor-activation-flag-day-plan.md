# CIP-28 BankActor — Activation Flag-Day Plan

> **For agentic workers:** this is a flag-day / operations plan, not a code milestone. The code is all merged and dormant; activation is a coordinated release + re-genesis. It is **consensus-critical** — read the whole doc before touching `BANK_ACTIVATION_HEIGHT`.

**Goal:** Turn on the merged-but-dormant CIP-28 BankActor surface (M1–M4 + M3.5 whitelist/GasCharged + M3.6 token-gas) by setting the compile-time gate `BANK_ACTIVATION_HEIGHT` (currently `u64::MAX`) and providing a genesis that seeds the bank state the active surface needs.

**Architecture:** A single network-wide compile-time constant gates opcodes **204–212** at two consensus points in `chain/src/application.rs` (block-level `do_verify` reject + propose-time exclusion) and two state-effect points in `execution/src/execution/transaction.rs` (A2 admission + settle-time gas charge). Below the height every node is byte-identical; at/above it the gated surface executes. **The bank's functional state (operator key, CUSD token + hook, gas pegs, `0x16` CBY reserve, fiat-mint signer) is seeded only at genesis, and the currently-running devnet genesis has none of it** — so a *functional* activation requires a coordinated **re-genesis**, not an in-place height bump.

**Tech Stack:** `types/src/constants.rs` (the constant), `chain/src/genesis.rs` + `validator/src/setup.rs` (genesis seeding), `scripts/run_build.sh` / `restart_validator.sh` (re-genesis + restart), the node CI + a devnet smoke suite.

---

## Baseline (verified — see 2026-07-24 activation baseline scan)

- **Gate constant:** `pub const BANK_ACTIVATION_HEIGHT: u64 = u64::MAX;` at `types/src/constants.rs:722` (doc `:711-721`). Compile-time, network-wide.
- **Gated opcodes:** `tx_is_bank_v2` (`chain/src/application.rs:2601-2624`) flags exactly **204 BankSetDefaultCard, 205 SetPolicy, 206 Freeze, 207 Unfreeze, 208 PauseBank, 209 UnpauseBank, 210 MintFromFiatVoucher, 211 SettleProvider, 212 IssueCardV2**. **200–203 (M1 issue/deposit/withdraw/close) are NOT gated — always-live** at every height.
- **Consensus enforcement:** block-level reject `application.rs:2103-2110` (`height < BANK_ACTIVATION_HEIGHT && block_has_bank_v2_tx → return false` — wholesale, deliberately not a tx-level Err → no decode-fork); propose-time exclusion `application.rs:1829-1834`. No mempool/RPC gate.
- **State-effect gates:** A2 admission `transaction.rs:233` (`!below_activation && …`); settle-time card gas charge `transaction.rs:558`. Below the height the default-card gas path never fires; an un-gated coupling (M1 CloseCard reads `agent_default_card:`, only written by gated 204) stays byte-identical below the height — **invariant: no other writer of `agent_default_card:`** (`handlers.rs:1374-1385`).
- **Genesis seeding** (`chain/src/genesis.rs`): always seeds the `0x16` BankActor + `bank_id=1` `BankEntry` (`operator = config.bank_operator`, `fiat_mint_signer = config.bank_fiat_mint_signer`, Active) + the (possibly empty) `stablecoin_whitelist`; conditionally seeds gas pegs, CUSD (`seed_cusd`), and the `0x16` CBY reserve (`bank_cby_reserve>0`). `validate()` folds the reserve into the CBY supply invariant (unaccounted reserve → rejected) and enforces peg num/den≠0 + whitelist membership + no-dup.
- **`GenesisConfig` bank defaults (OFF):** `bank_operator = ZERO`, `stablecoin_whitelist = []`, `bank_fiat_mint_signer = None`, `seed_cusd = false`, `gas_pegs = []`, `bank_cby_reserve = 0` (`genesis.rs:515-520`).
- **Dev genesis (`validator/src/setup.rs:130-144`):** `bank_operator = bank_fiat_mint_signer = dev_bank_gateway_address()` (**same** deterministic dev key, seed `0xB0A7`); `seed_cusd = true`; `stablecoin_whitelist = [CUSD_TOKEN_ID]`; `gas_pegs = [(CUSD_TOKEN_ID, 1, 1)]`; `bank_cby_reserve = 1_000_000_000_000`.
- **Currently-running devnet genesis has NO bank state** (operator ZERO, no CUSD/pegs/reserve — it predates M4/M3.6). **Genesis is immutable once generated; there is no in-place migration path** — `run_build.sh` does `rm -rf test` + `setup generate`; `restart_validator.sh` keeps `genesis.json`.
- **Test dependency:** execution tests exercise the active path at a **local** `const BANK_H = u64::MAX` (`tests.rs:16934`) — survives any real constant value. **Four "below-activation" tests hardcode height 1** — `cip28_card_ignored_below_activation_height` (`tests.rs:17876`) and the three RC8 gate tests (`application.rs:2701/2752/2813`) — they **break only if the constant is set to 0 or 1**; a large finite future height breaks none.

---

## Two activation horizons

This plan separates a **near-term devnet activation** (doable now, the concrete deliverable) from a **production activation** (blocked on additional work, enumerated so it is not assumed done).

### Horizon 1 — Devnet activation (Mode B, re-genesis) — THIS PLAN'S DELIVERABLE
A fresh re-genesis with the dev bank surface seeded and `BANK_ACTIVATION_HEIGHT` low. Because every validator starts from the **same fresh genesis**, there is **no mixed-version flag-day window** — activation is genesis-time, not a mid-chain event. This is the mode the code was written for (`constants.rs:718`: "a fresh re-genesis sets 0").

### Horizon 2 — Production/mainnet activation — GATED, NOT IN SCOPE HERE
A live value-bearing chain **cannot re-genesis**, and there is **no state-migration path** to introduce the bank genesis state (operator, CUSD token, pegs, reserve) into a running chain. So production CIP-28 launch requires EITHER (a) launching the bank on a **fresh chain** whose genesis seeds the surface, OR (b) building a **migration handler** that injects the bank genesis state at the activation height (not built). Plus the production-key / preimage / chain_id / reserve preconditions in §"Production preconditions" below. **Do not activate on a value-bearing chain until these are resolved.**

---

## Scope decisions (待裁 / to-be-ruled)

1. **Activation height value for devnet.** RECOMMENDED **a small non-zero height** (e.g. `10`) rather than `0`. Rationale: (a) it keeps a brief pre-activation window so the block-level gate is genuinely exercised on the live devnet (blocks 0–9 exclude bank-v2, block 10+ admit) — a real end-to-end check of the consensus gate before it matters; (b) it does **not** break the four "below-activation @ height 1" tests (height 1 stays below 10), so no test rework is needed. Alternative: `0` (bank live from genesis) — simplest semantically but requires reworking/removing the four below-activation tests (their height-1 "below" case is no longer below). If the reader prefers `0`, Task 2 covers the test rework.
2. **Devnet key model.** RECOMMENDED keep the dev shared `dev_bank_gateway_address()` for `bank_operator` + `bank_fiat_mint_signer` on devnet (it is a test key; the smoke suite signs with it). Flag that production MUST split these into distinct HSM-held keys (Horizon 2).
3. **Activate all opcodes at once vs staged.** RECOMMENDED **all at once** — the surface was designed and audited as a unit, M3 spend-caps gate M2 default-card gas, and staging would need extra intermediate gates. The single constant activates 204–212 together.
4. **Reserve size for devnet.** RECOMMENDED keep `1e12` (`setup.rs:74`); note it is a fixed genesis balance with no top-up path — if the token-gas smoke test drains it, cards degrade to actor-pays (graceful). Production sizing/top-up is Horizon 2.

---

## Consensus-safety analysis (read before choosing a mode)

- **Mode B (re-genesis, chosen for devnet):** no mixed-version *activation-timing* window — the gate value is baked into every binary before block 0. **This removes the coordination-timing fork risk, NOT the binary-parity requirement:** the constant is compile-time in the *validator* binary, so an identical `genesis.json` does NOT prove an identical gate — two nodes at the same genesis but different `BANK_ACTIVATION_HEIGHT` binaries boot identically, then **fork on the first 204–212 tx at height ≥ the lower height** (the stale-`u64::MAX` node rejects the block the upgraded node admits). So a fleet MUST verify **binary constant parity**, not just genesis-hash parity. On the single-validator (`--peers 1`) deliverable this is moot (one node agrees with itself). Two other fork risks to avoid: **`setup generate` derives all keys from `OsRng` (non-deterministic)** — peer signers (`setup.rs:1136`), user accounts (`:1152`), the BLS threshold set (`:1163`) — so two validators each independently running `run_build.sh` produce **DIFFERENT `genesis.json`** (different account addresses + validator-set snapshot + BLS shares) → different genesis state root → **the fleet never agrees, fork/halt at block 0.** For a **single-validator** devnet (`--peers 1`, what `run_build.sh` produces) this is a non-issue (the node agrees with itself). For a **multi-validator** fleet the correct procedure is: **ONE** host runs `setup generate --peers N` **once** (it emits all N per-node configs + a SINGLE shared `genesis.json`), then distributes that one `genesis.json` + each node's secret config; validators MUST NOT each regenerate. So the requirement is: every validator runs the same release **and boots from the one shared genesis** — for a fleet, `run_build.sh`-per-node is WRONG.
- **Mode A (in-place future height) — NOT used for devnet, documented for completeness:** consensus-safe **only if 100% of validators run the new constant before the height is reached**; the first block carrying a 204–212 tx at/after the height is accepted by upgraded nodes and **rejected wholesale by any node still on `u64::MAX` → consensus split**. AND on the current devnet it would be *functionally inert* (genesis lacks operator/CUSD/pegs/reserve). So Mode A is unsuitable here on both counts.

---

## Tasks

### Task 1: Pre-activation readiness gate (checklist — do NOT proceed until all ✓)

- [ ] All bank milestones merged on the target branch: M1, M2, M3-core, M3.5 (#1090), M4 (#1115), M3.6 (#1125). Verify the deployed binary is at/after the M3.6 merge (`git log --oneline | grep -E "M3.6|M4|M3.5"`).
- [ ] `validator/src/setup.rs` seeds the full bank surface (operator, fiat signer, `seed_cusd=true`, `[CUSD]` whitelist, `[(CUSD,1,1)]` peg, non-zero reserve) — confirm `setup.rs:130-144` unchanged.
- [ ] `GenesisConfig::validate()` passes for the dev config (reserve reconciled with `total_supply`, pegs valid + whitelisted). Covered by `cargo test -p cowboy-chain genesis`.
- [ ] The full suite is green on the target branch (`execution` + `chain` + `storage` + `types`).
- [ ] Confirm no un-audited writer of `agent_default_card:` was introduced (the CloseCard coupling invariant, `handlers.rs:1374-1385`).
- [ ] **(RECOMMENDED before calling the econ gate "green" — ratchet the #564/#589 escape class)** The activated bank econ paths — `bank_charge_gas_token`'s CBY paymaster leg (`handlers.rs:1073`, the `card_paid` fold + `0x16` `saturating_sub`) and the 210/211 CUSD supply across mint→pay→settle — are covered only by **point-wise unit tests** (`cip28_m36_paymaster_*`, `_liquidity_bound`, `_capped_by_headroom`), NOT by any property-based Σ-conservation invariant in `econ_invariants.rs` (which covers *generic* CIP-20 mint/burn/transfer + `compute_tx_fees`, but not the paymaster swap or the fiat handlers). "Full suite green" therefore implies stronger econ coverage than exists. The deep re-review deep-audit deemed this **advisory, not a demonstrated leak** (the point-wise tests are thorough), but the precedent (registered-but-missing econ invariants = false pass) says: add a `bank_charge_gas_token` + mint/settle Σ-conservation proptest (Σ CBY + Σ CUSD over an op stream, à la `assert_supply_conserved`) and register it, so the econ gate genuinely covers the activated surface. Optionally open a Marshal ratchet.
- [ ] (Cosmetic cleanup — do in one pass) Stale "opcodes 204-209" / "u64::MAX flag-day sentinel" strings that become misleading after activation (predicates are all correct — no consensus effect): `chain/src/application.rs` warn/comment (the actual `warn!` is ~`:2108`, gate comment ~`:2095`/`:2618`); `execution/src/execution/transaction.rs:200,204,555-556,634`; `execution/src/execution/tests.rs:16933,17884`; and — now stale since the §6.2 amendment landed — `execution/src/bank/mod.rs:39,58,90` + the CUSD hook Python comment, which still say the `card→BANK` flow is "pending a CIP-36 §6.2 amendment" (it is merged). Update all so the activation log/review is not misleading.

### Task 2: Set the activation constant (+ test adaptation only if value ≤ 1)

**Files:** `types/src/constants.rs:711-722`.

- [ ] **Step 1 — edit the constant.** Change `pub const BANK_ACTIVATION_HEIGHT: u64 = u64::MAX;` to the ruled value (recommended `10`). Update the doc comment `:711-721` to record the activation decision (value, date, mode = re-genesis) instead of the "not-yet-scheduled / u64::MAX" text.

```rust
/// CIP-28 BankActor v2 activation height. ACTIVATED <YYYY-MM-DD> on devnet via a
/// coordinated re-genesis (Mode B): opcodes 204–212 are admissible at/above this height;
/// below it a block carrying any is rejected wholesale by `do_verify`. Set low (a fresh
/// re-genesis seeds the bank surface at genesis and every validator starts identical, so
/// there is no mixed-version window). Production activation on a value-bearing chain needs
/// distinct HSM keys + a migration path for the bank genesis state — see the flag-day plan.
pub const BANK_ACTIVATION_HEIGHT: u64 = 10;
```

- [ ] **Step 2 — (ONLY IF the ruled value is 0 or 1) adapt the four below-activation tests.** They hardcode `height = 1` as the "below" case, which is no longer below a value of 0/1. Rework each so the below-case uses a height genuinely `< BANK_ACTIVATION_HEIGHT` (skip/remove the height-1 assertion when the constant ≤ 1, or gate the sub-assertion on `BANK_ACTIVATION_HEIGHT > 1`):
  - `execution/src/execution/tests.rs:17876` `cip28_card_ignored_below_activation_height`
  - `chain/src/application.rs:2701` `bank_v2_tx_below_activation_height_rejected`
  - `chain/src/application.rs:2752` `bank_m3_opcodes_205_to_209_gated_below_activation`
  - `chain/src/application.rs:2813` `bank_m4_opcodes_210_to_212_gated_below_activation`
  For the recommended value `10`, **no test change is needed** — verify by running them.

- [ ] **Step 3 — run:** `cargo test -p cowboy-execution 'execution::tests::cip28' && cargo test -p cowboy-chain 'application::tests::bank'`. Expected: all pass (with value `10`, unchanged).
- [ ] **Step 4 — build the workspace** to confirm the constant change compiles everywhere it is read (`application.rs:1832,2103`; `transaction.rs:233,558`).
- [ ] **Step 4b — (CRITICAL, compile-time delivery) rebuild the VALIDATOR binary.** `BANK_ACTIVATION_HEIGHT` is a `pub const` baked into the **validator** binary's gates — it is NOT in `genesis.json`, and `run_build.sh` (Task 3) rebuilds only the `setup` binary (which never reads it). The default `start_validator.sh` path uses `cargo run -p validator --bin validator` and recompiles, so it picks up the edit — BUT if the smoke suite is driven by a **prebuilt release binary** (`VALIDATOR_EXE=…`, or the `examples/*/start_all.sh` harnesses that require pre-built release binaries), you MUST `cargo build --release` after the edit, or the node runs the stale `u64::MAX` gate against a bank-seeded genesis → every 204–212 tx is rejected wholesale and the whole surface looks dormant (a confusing false-negative activation, not a fork). Confirm the running validator binary carries the new value before smoke-testing.
- [ ] **Step 5 — commit** `chore(cip28): activate BankActor v2 at height N (devnet re-genesis)` (NO AI attribution).

### Task 3: Re-genesis the devnet + restart

**Files:** `scripts/run_build.sh` (wipes `test/` + `setup generate`), `scripts/start_validator.sh`.

- [ ] **Step 1 — regenerate genesis + config** with the activation binary: `./scripts/run_build.sh` (this `rm -rf test/` and runs `setup generate`, producing `test/genesis.json` with the full dev bank surface + the new constant baked into the binary).
- [ ] **Step 2 — verify the seeded genesis** (`test/genesis.json`): `bank_operator` is the non-ZERO dev gateway; `bank_fiat_mint_signer = Some(dev gateway)`; `seed_cusd = true`; `stablecoin_whitelist = [CUSD_TOKEN_ID]`; `gas_pegs = [(CUSD, 1, 1)]`; `bank_cby_reserve = 1e12`. (These come from `setup.rs`; confirm they serialized.)
- [ ] **Step 3 — start the validator:** `./scripts/start_validator.sh`. Confirm it produces blocks past the activation height (blocks 0–9 are pre-activation, block 10+ active). **Do NOT use `restart_validator.sh` alone** — it keeps the existing `test/genesis.json` (`restart_validator.sh:35` clears only DB/logs/storage), so on the new binary it would boot the OLD bank-less genesis → a silently non-functional (operator ZERO, no CUSD/pegs/reserve) devnet, not a fork. `run_build.sh` (which `rm -rf test` + `setup generate`) is required to regenerate genesis with the bank surface.
- [ ] **Multi-validator note (HARD — genesis is NOT reproducible across independent runs):** `setup generate` uses `OsRng`, so each `run_build.sh` yields a different `genesis.json`. For a fleet, do NOT have each node run `run_build.sh` (→ fork at block 0). Instead: **one** host runs `setup generate --peers N` **once**, producing the N per-node secret configs + a **single** `genesis.json`; distribute that one `genesis.json` + each node's config; every validator boots from the identical shared genesis on the same activation binary.

### Task 4: End-to-end smoke suite on the activated devnet (verification matrix)

Run against the live activated devnet (via CLI / RPC / an integration test signing with the dev gateway key). Each row proves one activated surface actually works on-chain (not just in unit tests). Below activation (blocks < 10) a bank-v2 tx MUST be excluded/rejected; at/above, it MUST succeed.

- [ ] **Gate (consensus):** a `BankIssueCardV2` (212) tx submitted for a pre-activation block is excluded at propose and a hand-crafted block carrying one is rejected by `do_verify`; the same tx at height ≥ 10 is admitted. **Timing:** the live below-activation window is only blocks 0–9 (a few seconds at normal cadence), so to observe propose-exclusion / `do_verify`-reject live the bank-v2 tx must be in the mempool *during* bootstrap, before height 10. If that is impractical, rely on the four unit tests (`cip28_card_ignored_below_activation_height`, the RC8 gate tests) for the below-case and smoke-test only the at/above admission live.
- [ ] **M4 consent (212):** issue a card with a gateway-signed `IssuancePrincipalVoucher` (`owner_or_agent == sender`); a voucher naming a different owner is rejected; a replayed nonce is rejected. Card records the signed `issuance_principal`; the `card↔owner` CUSD allow-pair is written.
- [ ] **M4 fiat mint (210):** `MintFromFiatVoucher` signed by `fiat_mint_signer` mints CUSD to a card (supply +amount); replay of the same `voucher_id` is a no-op; wrong signer / amount==0 / Closed card rejected. `FiatMinted` event attributed to `0x16`.
- [ ] **M4 settle (211):** operator `settle_provider` burns CUSD from a provider (supply −amount); a replayed `settlement_id` is an idempotent no-op; non-operator rejected; insolvent provider rejected. `ProviderSettled` event.
- [ ] **CUSD hook (§6.2):** `card → owner` admitted (pair present); `card → PG`, `PG → recipient` pay-out, `BANK → card` admitted; arbitrary P2P `card → other` rejected.
- [ ] **M2/M3 lifecycle:** set a default card (204); set policy (205); freeze/unfreeze (206/207); pause/unpause bank (208/209) — each operator/owner-authorized against the non-ZERO dev operator; a paused bank rejects deposit/issue but allows withdraw.
- [ ] **M3.5 whitelist + GasCharged (native):** a default card funds an `ExecuteActor`'s gas; a card whose `allowed_receivers`/`allowed_syscall_kinds` excludes the call is rejected pre-execution; a `GasCharged` event (attributed to `0x16`) is emitted; per-hour/day/month caps enforced.
- [ ] **M3.6 token-gas (paymaster):** a `Token(CUSD)` default card funds gas — its CUSD moves to `0x16`, the `0x16` reserve funds the CBY burn/tip, `GasCharged` carries U units; when the reserve is exhausted the card degrades to actor-pays (no failure); Σ CBY and Σ CUSD conserved across the settle.
- [ ] **Conservation (full-sum, not directional):** before/after a mint→pay-gas→settle sequence, assert the full set sums — `Σ CBY over {all accounts incl. 0x16} + block burn + tip == prior total`, and `Σ CUSD balances == CUSD total_supply` (mint raised supply by exactly the minted amount, settle lowered it by exactly the burned amount). A directional "supply only moves by mint/burn" check is weaker and can miss a leak; assert the equalities.

### Task 5: Rollback

- [ ] If a smoke test reveals a defect, rollback is a re-genesis with `BANK_ACTIVATION_HEIGHT = u64::MAX` (revert Task 2) + **rebuild the validator binary** (same compile-time-delivery reason as Task 2 Step 4b — the reverted constant reaches the running gate only via a validator rebuild) + `run_build.sh`. State-wise the rollback is clean: `run_build.sh` does `rm -rf test/` and all DB/storage/genesis/keys live under `test/` — **no persisted artifact survives**. Because devnet is a fresh chain, reverting is another coordinated wipe-and-restart, no state to preserve. Document the failing case, fix on a branch, re-run the flow. (No mainnet rollback concern — Horizon 2 is not in scope.)

---

## Production preconditions (Horizon 2 — MUST resolve before any value-bearing activation)

These are **not** blockers for the devnet activation but MUST be tracked and resolved before CIP-28 goes live on a real chain:

1. **Distinct HSM keys.** Devnet uses one `dev_bank_gateway_address()` for both `bank_operator` (consent/issuance signer, verified `handlers.rs:665`) and `bank_fiat_mint_signer` (fiat-mint signer, verified `handlers.rs:1491`). Production needs **separate, HSM-held** keys (`setup.rs:41-45` flags this).
2. **Voucher preimage §3.3 amendment.** The signed preimage is hand-rolled fixed-BE (`bank/mod.rs:655,677-698`), but CIP-28 §3.3 specifies `rlp(voucher)`. Any external gateway must sign the **implemented BE preimage** (devnet is internally consistent — the dev gateway and the chain both use BE — so this is not a devnet blocker). **Recommendation (from the deep re-review): land the CIP-28 §3.3 amendment NOW rather than gating it on gateway integration** — it is a zero-consensus-cost docs change, the spec is the source of truth, and a third-party gateway reading §3.3 today would build `rlp` and be silently incompatible. Pair it with a cross-repo golden vector. (M4 Finding-2.)
3. **`chain_id` binding.** The voucher preimages carry a type-domain tag but **no network id** — a signer key reused across chains lets a voucher replay. Either bind `chain_id` into the preimage (a preimage/golden change) or mandate distinct per-chain signer keys operationally.
4. **`0x16` reserve sizing + top-up.** The paymaster CBY reserve is a fixed genesis balance with no top-up path; size it for real subsidy volume or establish a governance/market-making refill before relying on token-gas at scale.
5. **No migration path for a running chain.** A live chain cannot re-genesis and there is no handler to inject the bank genesis state (operator/CUSD/pegs/reserve) mid-chain. Production CIP-28 must launch on a **fresh chain** or a migration handler must be built.
6. **Mode-A flag-day discipline (if ever used):** if activation is ever an in-place height bump on a bank-seeded chain, 100% validator upgrade before the height is mandatory (else fork).

---

## Self-Review checklist

- **Spec coverage:** the plan activates exactly the gated opcodes 204–212; 200–203 are already live; the smoke matrix covers every activated surface (consent/mint/settle/hook/lifecycle/whitelist/token-gas/conservation).
- **Consensus safety:** re-genesis (Mode B) has no mixed-version window; Mode A's fork risk + functional-inertness on the current devnet are documented and Mode A is not used.
- **Test impact:** identified exactly the four below-activation tests that break iff the constant ≤ 1; the recommended value `10` breaks none.
- **No placeholders:** the constant edit, the re-genesis procedure, and the seeded-genesis verification are concrete; the smoke matrix names each surface + its accept/reject case.
- **Production honesty:** the Horizon-2 preconditions (HSM keys, preimage amendment, chain_id, reserve, migration) are enumerated, not assumed done.

## Verification matrix (what proves activation succeeded)

| Requirement | Proof |
|---|---|
| Constant set, compiles | Task 2 Step 3-4 (tests + workspace build) |
| Genesis seeds bank surface | Task 3 Step 2 (inspect `test/genesis.json`) |
| Consensus gate works live | Task 4 row "Gate" (pre-activation exclude/reject, at-activation admit) |
| Consent / mint / settle | Task 4 rows M4 212/210/211 |
| CUSD compliance perimeter | Task 4 row "CUSD hook" |
| Lifecycle + whitelist + caps | Task 4 rows M2/M3, M3.5 |
| Token-gas paymaster + conservation | Task 4 rows M3.6, Conservation |
| Rollback available | Task 5 |
| Production gaps tracked | Horizon-2 preconditions § 1–6 |

**Commit-message rule:** NO AI attribution (node repo). **Finalize (re-genesis + restart) is an operational action on shared devnet infra — user-gated; do not wipe/restart the devnet without explicit authorization.**
