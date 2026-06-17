# Marshal Review — CIP-23 v3 (TEE Execution and Composite Attestation)

- **Object:** `docs/cips/cip-23-tee-execution.md` on branch `docs/cip-23-v3` (`cowboy@dc0a64b0`)
- **Change:** v3 consolidated rewrite, `+226 / −355`, single file; supersedes v1 (2026-04-20) and the v2 alignment revision (2026-05-26)
- **Flow:** B (spec-layer) + security lens. **No PR exists yet** — this is a branch review.
- **Verdict:** 🟡 **NEEDS_HUMAN** (advisory; not degraded)
- **Marshal run:** 185 · **Date:** 2026-06-16
- **Requirements extracted:** 17 (13 MUST / 2 SHOULD / 2 MAY)

---

## 1. Executive summary

CIP-23 v3 is a high-quality, security-aware rewrite that resolves the structural problems of v1/v2 and reacts correctly to the 2025-10 **TEE.Fail** disclosure. The spec is internally coherent, and every cross-CIP reference Marshal spot-checked against the current spec tree and node code held up. It is rated **NEEDS_HUMAN** not because of a defect, but because it is a major security-critical CIP design change (a Draft, governance/human sign-off territory) whose new normative security requirements are spec-ahead-of-code with no covering invariants yet, plus a few explicitly-open items (non-final opcodes) to reconcile at implementation time.

Marshal cannot **block** a merge and there is no PR to comment on; this document is the advisory record and a forward-looking implementation checklist.

---

## 2. What v3 changes (vs v1/v2)

| Area | v1/v2 | v3 |
|---|---|---|
| Verification philosophy | One `Deterministic` path conflating confidential + reproducible | **Split:** `TeeAttested` (confidential, 1 replica, attestation *is* verification) vs `Deterministic` (non-confidential, committee byte-match) — §3.4 |
| On-chain attestation | Hand-rolled 7-layer X.509/ECDSA walk (`~120k` cycles, time-non-deterministic) | **SNARK-compressed DCAP proof**; time-dependent collateral becomes a snapshot-anchored circuit input — §3.8 |
| Trust root | Single chip-vendor root | **Multi-root `chip_root ∧ operator_root`** (Proof-of-Cloud) post-TEE.Fail — §3.6 |
| `attest_digest` | `keccak(cae_cbor)` (circular — includes the signature) | `keccak(D-CBOR(CAE with service_sig cleared))` — §3.5 |
| `nonce` | `keccak(task_id ‖ req_hash ‖ submission_block_hash)` (publicly derivable) | adds an on-chain `randomness_beacon` term — §3.5 |
| TCB level | not evaluated | **TCB-level policy step** → `TcbOutOfDate`; governance blacklists a microcode/TCB level via a `CollateralSnapshot` — §3.8.4/§6 |
| Time on-chain | wall-clock-ish | **governance-anchored `CollateralSnapshot` keyed by block height** — deterministic for all validators — §3.8.4 |
| SGX | legacy tier | **rejected** for `TeeAttested`/`Deterministic` (IAS/EPID EOL) — §3.3 |

---

## 3. Security analysis (positives — verified by reading the spec)

These are the properties that make v3 sound; each is a concrete improvement, not boilerplate:

1. **`attest_digest` circularity fix.** Computing the digest over the CAE with `service_sig` cleared removes the impossible self-reference. Correct.
2. **`nonce` unpredictability.** Folding an on-chain beacon in defeats precomputation by a key-extraction adversary — the explicit motivation given TEE.Fail. Correct.
3. **Multi-root trust.** `chip_root ∧ operator_root` is the right structural response to "a forged-but-root-valid quote is achievable with physical access + root." The threat model is stated honestly (chip root does **not** cover physical access; operator root is the mitigation; remote/software adversaries are covered by the chip root alone).
4. **Determinism via `CollateralSnapshot`.** Evaluating cert `notAfter` / CRL `nextUpdate` / TCBInfo dates against a block-height-selected, governance-published snapshot — **never wall-clock** — is exactly what a consensus path needs. Every validator replays the same verdict.
5. **REPORTDATA binding.** `user_data = keccak(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)` cross-binds CPU/GPU/service/task; the CPU quote is worthless without the matching GPU report and key.
6. **Replay + freshness.** `nonce` checked against `seen_nonces[job_id]` over the dispute window; `MAX_QUOTE_AGE = 75 blocks`; cert chain MAY be cached but the **quote** must be fresh per event.
7. **Mode split is implementable.** A confidential (per-recipient encrypted) output is never byte-identical across runners, so it cannot be committee-matched; v3 makes `TeeAttested` attestation-as-verification (1 replica) and keeps `Deterministic` for public outputs.

---

## 4. Cross-CIP consistency verification (one-hand checked against repo)

| Claim in CIP-23 v3 | Verification | Result |
|---|---|---|
| `BLOCK_CYCLES_TARGET = 20,000,000` "per CIP-3 amendment" | `cowboy/docs/cips/cip-3-fee-model.md:20` records `20,000,000` (amended from 10M); node `execution/src/basefee.rs:88` default `20_000_000` | ✅ Consistent |
| Interim trusted-key model on **opcodes 60–63**, "shipped" | `node/types/src/execution.rs`: `SYS_REGISTER_TEE_TRUSTED_KEY=60`, `SYS_REVOKE_TEE_TRUSTED_KEY=61`, `SYS_SUBMIT_TEE_ATTESTATION=62`, `SYS_REVOKE_TEE_ATTESTATION=63` | ✅ Accurate |
| Target opcodes **65–67** for `VerifyCae`/`UpdateCollateral`/`GcNonces` | currently free (next allocated is `SYS_ROTATE_COMMITTEE=74`); spec marks them **non-final placeholders** to reconcile against the CIP-13 master allocation table | ✅ Honest; no current collision (`contract.sys_opcode_uniqueness` guard covers collision at impl) |
| Interim `cbss.rs` model = `operator_root`; SNARK `chip_root` = target/unimplemented | matches the shipped state (CBSS `validate_runner_tee_for_release` consumes the signed-attestation record) | ✅ Honest impl-status reconciliation |
| Governance | CIP amendment (not the whitepaper); supersedes v1/v2 with a changelog; amends CIP-2 §5.4/§9, CIP-10 §12.3 | ✅ No silent constitution↔amendment conflict found |

> Note: the loaded `CLAUDE.md` still states `BLOCK_CYCLES_TARGET = 10_000_000`, which is **stale** vs both the current CIP-3 spec and node code (20M). The CIP-23 claim is correct; CLAUDE.md should be updated separately.

---

## 5. Findings

- 🔵 **LOW — target/capacity naming drift.** CIP-23 v3 (§3.16 + gas table) uses `BLOCK_CYCLES_TARGET = 20,000,000` as the *target*, but CIP-3 §241 defines `20,000,000` as block cycle **capacity** and `10,000,000` as the **target (T_c, 50% of capacity)**. The node constant is named `BLOCK_CYCLES_TARGET` but holds the 20M capacity value. The gas-headroom claim ("verifies well over 100 CAEs per block") depends on which figure is meant. This is a CIP-3/code naming issue, not specific to CIP-23, but v3 inherits the ambiguity — recommend standardizing "target" vs "capacity" terminology across CIP-3, the node constant, and CIP-23.

No medium/high-severity findings. The two consistency concerns Marshal opened (CIP-3 cycles figure; opcode allocation) both resolved to *consistent/honest* after verification.

---

## 6. Coverage gap — spec-ahead-of-code (expected for a Draft, flagged)

Only **P0 (the interim trusted-key model, opcodes 60–63, CBSS `tee_required` gate)** is shipped. The new normative security MUSTs are not yet enforced by any registered invariant because their implementation is roadmapped (P1–P3):

- forged-quote rejection (SNARK chip-root)
- replay rejection (`seen_nonces`)
- REPORTDATA binding equality
- multi-root acceptance (`chip_root ∧ operator_root`)
- TCB-level policy (`TcbOutOfDate`)
- freshness (`MAX_QUOTE_AGE`, binding renewal)
- deterministic collateral selection (no wall-clock)

Most of these are **negative / confidentiality / integrity properties** — they cannot be validated by a functional round-trip proptest (a forged construct can pass a happy-path test). They require **review-lens checks + targeted adversarial tests** at implementation time.

---

## 7. P1 implementation checklist (hazards + invariants to land with the code)

When the chip-root SNARK path lands, each item below should arrive with a test/guard. Shape noted (`hazard` = review-lens negative property; `invariant` = round-trippable positive property).

| # | Property | Shape | Suggested check |
|---|---|---|---|
| 1 | A forged quote (no valid vendor chain) is **rejected** | hazard | red-team vectors: forged/tampered/wrong-root quotes → `AttestFail`; assert no accept path |
| 2 | A replayed `nonce` within the dispute window is **rejected** | invariant | proptest: second `verify_cae` with same `(job_id, nonce)` → `TaskReplayed` |
| 3 | `REPORTDATA != keccak(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)` is **rejected** | invariant | proptest over mutated fields → `NonceBindingFail` |
| 4 | A stale quote (`now − generated_at > MAX_QUOTE_AGE`) or past `deadline` is **rejected** | invariant | boundary proptest at 75 blocks → `TaskExpired` |
| 5 | A `TeeAttested` / `Deterministic+tee_required` result with **only one root** passing is **rejected** | hazard | review-lens: assert acceptance requires `chip_root ∧ operator_root`; vector with valid chip root + invalid operator root → `OperatorRootFail` |
| 6 | A TCB level outside the governance-allowed set is **rejected** | invariant | snapshot with TCBInfo marking level unacceptable → `TcbOutOfDate` |
| 7 | `verify_cae` is **deterministic** across validators (no wall-clock) — same block ⇒ same verdict | invariant | replay same tx at same block height with two snapshots-by-height → identical result; assert no `SystemTime`/clock read in the path |
| 8 | SGX CAE is **rejected** for attested modes | invariant | `tee_type == sgx` → `UnsupportedTeeType` |
| 9 | `attest_digest` is computed over the **sig-cleared** CAE (all consumers agree) | invariant | round-trip: storage/secrets/billing digests equal; mutating `service_sig` does not change `attest_digest` |
| 10 | `nonce` derivation **includes the beacon** (publicly-derivable nonce is non-conformant) | hazard | review-lens at the runner quote-request site; reject a nonce reproducible from public-only inputs |
| 11 | New TEE Verifier error codes are **unique** and consensus-coordinated | invariant | extend the `contract.structured_error_code_uniqueness` guard (opened as `esc-20260615-...`) to cover `TeeVerifyError` once it enters a receipt path |
| 12 | Final opcodes (65–67 placeholders) do **not collide** | invariant | `contract.sys_opcode_uniqueness` already guards this — confirm green after numbering is finalized |

> Item 11 ties to the existing escape ratchet `esc-20260615-structured-error-code-collision` and item 12 to `contract.sys_opcode_uniqueness` (from COW-1024). Both are recurring hazard classes in this codebase.

---

## 8. Verdict rationale

**NEEDS_HUMAN** because:
1. It is a major security-critical CIP design change — Draft, no PR — which is governance / human sign-off territory; Marshal does not rubber-stamp constitution-adjacent security specs.
2. New normative security MUSTs are spec-ahead-of-code with no covering invariants (expected for a Draft, but flagged with the §7 checklist).
3. Non-final opcodes 65–67 must be reconciled against the CIP-13 master allocation table before implementation.

The spec itself is well-formed, internally coherent, and every cross-CIP reference checked out. The dominant remaining work is the SNARK chip-root implementation, opcode finalization, and governance sign-off.

---

*Generated by Marshal (risk-tiering + invariant gate + adversarial review). Advisory only.*
