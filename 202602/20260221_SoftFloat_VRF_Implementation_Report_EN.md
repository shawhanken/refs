# SoftFloat + VRF Implementation Report

**Date**: 2026-02-21  
**Scope**: SoftFloat deterministic float and three-layer VRF implementation completed in this session.

---

## 1. Test Results Summary

| Module | Tests | Status |
|--------|-------|--------|
| `rustpython-vm::softfloat` | 56 passed | ✅ |
| `cowboy-chain::pvm_host` | 11 passed | ✅ |
| `runner-registry::ecvrf` | 11 passed | ✅ |
| `runner-consensus::threshold_bls_vrf` | 11 passed | ✅ |

**Total: 89 tests, all passed, 0 failed.**

---

## 2. SoftFloat Implementation

### 2.1 Goal

Replace all PVM functions that relied on hardware floating-point with pure-software F64 operations via the `softfloat` crate, ensuring bit-identical results across x86_64, aarch64, riscv64, and wasm32.

### 2.2 `node/pvm/crates/vm/src/softfloat.rs`

**Twelve functions previously using hardware f64 are now implemented in pure SoftFloat F64:**

| Function | Implementation |
|----------|----------------|
| `tan` | `sin(x) / cos(x)` |
| `pow` | `exp(b·ln(a))` with full IEEE 754 edge cases (NaN, ±∞, negative base) |
| `sinh` | `(e^x − e^{-x}) / 2`, small-value shortcut to avoid cancellation |
| `cosh` | `(e^x + e^{-x}) / 2` |
| `tanh` | `(e^{2x}−1)/(e^{2x}+1)`, saturates to ±1 for \|x\|≥19 |
| `asinh` | `ln(x + √(x²+1))` |
| `acosh` | `ln(x + √(x²−1))`, domain x≥1 |
| `atanh` | `ln((1+x)/(1−x)) / 2`, domain \|x\|<1 |
| `atan` | Two-step range reduction + 21-term Taylor polynomial (Horner) |
| `asin` | `atan(x/√(1−x²))` with (1−x)(1+x) for stability near ±1 |
| `acos` | `π/2 − asin(x)` |
| `atan2` | Quadrant logic + SoftFloat `atan(y/x)` |

**Tests:** Basic ops, roots, exp/ln, trig/inverse trig, hyperbolic, rounding, modulo, floor_div; cross-platform bit-level determinism; IEEE 754 special values; ULP accuracy vs native f64. Count: 38 → 56.

### 2.3 `node/pvm/crates/stdlib/src/math.rs`

**Ten Python `math` functions now have `enable_softfloat` branches:**

`exp2`, `expm1`, `log`, `log2`, `log10`, `log1p` (using softfloat add), `cos`, `asin`, `cbrt`, `fmod` (`py_fmod`), `hypot` (with `vm` parameter for softfloat path).

### 2.4 CI `node/pvm/.github/workflows/softfloat-cross-platform.yml`

Matrix: x86_64, aarch64, **riscv64gc-unknown-linux-gnu**, **wasm32-wasip1**. wasm32 uses Wasmtime. New job `softfloat-bit-consistency` compares test outcomes across targets.

---

## 3. VRF Implementation

### 3.1 Layer 1 — PVM randomness: HKDF-SHA256

**File:** `node/chain/src/pvm_host.rs`

`randomness(domain)` changed from `SHA256(block_hash || domain)` to **HKDF-SHA256** (IKM = block_hash, salt = `"cowboy-pvm-randomness-v1"`, info = domain). Dependencies: sha2, hmac, hkdf. Tests include RFC 5869 test vector. Comments document the future VRF beacon integration point (swap IKM to `block_vrf_output`).

**Incidental fix:** `node/chain/src/execution.rs` — `k != "_handler"` → `k.as_str() != "_handler"`.

### 3.2 Layer 2 — Runner committee selection: EC-VRF (RFC 9381)

**New file:** `runner/crates/runner-registry/src/ecvrf.rs`

IETF EC-VRF-EDWARDS25519-SHA512-TAI; types: `VrfSecretKey`, `VrfPublicKey`, `VrfProof` (80 bytes), `VrfOutput` (64 bytes). API: `vrf_prove(sk, alpha)`, `vrf_verify(pk, alpha, proof)`, `vrf_output_to_seed`.

**registry.rs:** `vrf_select_runners` now uses HMAC-SHA256(key = vrf_seed) for deterministic index selection.

**dispatcher.rs:** `generate_vrf_seed` uses full EC-VRF prove; alpha = job_id || block_height || submitter; key from placeholder or `DISPATCHER_VRF_SK_HEX` env; fallback to SHA256(alpha) on prove failure.

**Tests:** 11 ecvrf unit tests (roundtrip, determinism, wrong alpha/pk, tampered proof, etc.).

### 3.3 Layer 3 — Consensus: Threshold-BLS VRF framework

**New file:** `runner/crates/runner-consensus/src/threshold_bls_vrf.rs`

t-of-n Shamir shares; `BlsSecretShare`, `BlsAggregatePublicKey`, `VrfShare`, `ThresholdVrfOutput`. Share = H(round_input)^{sk_i}; aggregate via Lagrange interpolation in the exponent; verify with pairing. `hash_to_g1` currently: SHA-512 → scalar → scalar·G1; doc states production should use RFC 9380 hash-to-curve.

**Tests:** 11 (hash_to_g1, share aggregation, insufficient/duplicate shares, serialization, pairing verification, Lagrange constant recovery).

---

## 4. File Change Manifest

**SoftFloat:**  
`node/pvm/crates/vm/src/softfloat.rs`, `node/pvm/crates/stdlib/src/math.rs`, `node/pvm/.github/workflows/softfloat-cross-platform.yml`

**VRF L1:**  
`node/chain/Cargo.toml`, `node/chain/src/pvm_host.rs`, `node/chain/src/execution.rs`

**VRF L2:**  
`runner/Cargo.toml`, `runner/crates/runner-registry/Cargo.toml`, `runner/crates/runner-registry/src/ecvrf.rs` (new), `runner/crates/runner-registry/src/lib.rs`, `runner/crates/runner-registry/src/registry.rs`, `runner/crates/job-dispatcher/Cargo.toml`, `runner/crates/job-dispatcher/src/dispatcher.rs`

**VRF L3:**  
`runner/crates/runner-consensus/Cargo.toml`, `runner/crates/runner-consensus/src/threshold_bls_vrf.rs` (new), `runner/crates/runner-consensus/src/lib.rs`

---

## 5. Test Commands

```bash
cd node/pvm && cargo test -p rustpython-vm --lib softfloat
cd node && cargo test -p cowboy-chain --lib pvm_host
cd runner && cargo test -p runner-registry --lib ecvrf
cd runner && cargo test -p runner-consensus --lib threshold_bls_vrf
```

---

## 6. Follow-ups

1. **SoftFloat:** Enabling stdlib-dependent pvm-runtime integration tests in CI is blocked by pre-existing `rustpython-stdlib`/`random.rs` (mt19937/rand_core) build errors.
2. **EC-VRF:** Production: inject `DISPATCHER_VRF_SK_HEX`; on-chain: call `vrf_verify(pk, alpha, proof)` when proofs are stored.
3. **Threshold-BLS:** Replace `hash_to_g1` with RFC 9380 hash-to-curve; add block header fields `vrf_output`, `vrf_proof_shares`; feed `block_vrf_output` into pvm_host for beacon integration.
