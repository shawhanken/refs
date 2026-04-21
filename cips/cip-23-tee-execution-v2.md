---
title: "CIP-23: TEE Execution and Composite Attestation (v2)"
description: Code-aligned v2 — three-layer TEE chain (entitlement / job spec / measurement binding) explicit, CIP-13 delegation interaction, opcode space confirmation, nitro added to canonical TEE types
---

# CIP-23 v2

> **Versioning.** This is v2 of CIP-23. v1 is the canonical document `cip-23-tee-execution.md` (preserved verbatim as Part I). v2 = v1 + the alignment revision (Part II).
>
> **Conflict rule:** Part II is canonical wherever it contradicts Part I. CIP-23 v1 is mature (Created 2026-04-20); v2 is a tightly-scoped clarification layer.
>
> **Summary of v2 changes**
>
> - **TEE three-layer chain** made explicit: `sec.tee_required` entitlement (manifest) → `VerificationConfig.tee_required` (job spec) → `measurement_binding` (runner). Each at a different lifecycle moment, providing defense in depth.
> - **`nitro` added to `CANONICAL_TEE_TYPES`** (`registry.rs:211`). v1 §3.3 lists Nitro as a secondary backend but the registry's canonical list does not yet include it.
> - **CIP-13 delegation interaction** clarified: TEE eligibility is a categorical capability check (not stake-thresholded). Delegation increases VRF weight but does not confer eligibility.
> - **Opcode space confirmed**: 50–53 do not collide with CIP-13 v2 (44–48) or CIP-10 v2 (60–63).
> - **`sec.tee_required` → `VerificationMode` mapping** spelled out: `tdx`/`sev`/`nitro` eligible for `Deterministic`; `sgx` legacy-only (`EconomicBond` / others), per v1 §3.3.

---

## Part I — v1 Specification (verbatim from `cip-23-tee-execution.md`)


<Note>
  **Status:** Draft<br/>
  **Type:** Standards Track<br/>
  **Category:** Core<br/>
  **Created:** 2026-04-20<br/>
  **Requires:** CIP-2, CIP-3, CIP-10<br/>
  **Related:** CIP-1 (deferred callbacks), CIP-9 (off-chain storage for CAE bodies)
</Note>

## 1. Abstract

This proposal specifies **TEE Execution** for Cowboy — a hardware-backed, end-to-end verifiable path for off-chain AI and privacy-sensitive workloads. It standardizes a **Composite Attestation Envelope (CAE)** that binds an Intel TDX (or AMD SEV-SNP / AWS Nitro) CPU quote together with an NVIDIA NCC GPU report and a service signature into one on-chain-verifiable receipt. It also upgrades the `TEE Verifier` system Actor at `0x05` from its current stub state into a real attestation verification pipeline, and converts the `CIP-2 VerificationMode::Deterministic` path from a field-presence flag into a cryptographically enforced guarantee.

Key properties:

- **Hardware-rooted trust.** Every TEE result carries a CAE whose CPU quote (TDX `TDQuoteV4`, SNP `AttestationReport`, or Nitro `COSE_Sign1`) chains back to a vendor root certificate recorded on-chain.
- **CPU + GPU composite.** AI workloads require both confidential VM isolation and GPU memory protection. CAE binds the two via `user_data = keccak(nonce ‖ service_pubkey ‖ gpu_measurement)` inside the CPU quote.
- **Verify / replay decoupling.** The chain validates a CAE once; any node can later replay verification deterministically against Registry anchors without re-contacting the TEE.
- **No new syscall.** A single-entry `tee_call` ergonomic is expressed as a thin SDK helper over `CIP-2 SubmitJob`, preserving PVM determinism and requiring zero Actor-code changes.
- **Confidential Containers alignment.** CVM images follow CoCo + Trustee conventions, reusing CIP-10's OCI stack and avoiding bespoke enclave SDKs.
- **Attestation-first Runner registration.** A Runner cannot enter the TEE-eligible candidate pool without binding a valid CPU (and optionally GPU) measurement at registration time.

This CIP does **not** require every Runner to run in a TEE; non-TEE Runners continue to serve `None`, `EconomicBond`, `MajorityVote`, `StructuredMatch`, and `SemanticSimilarity` jobs unchanged.

---

## 2. Motivation

CIP-2 introduces a `tee_required` flag and a `Deterministic` verification mode, and reserves `0x05` for a TEE Verifier. The current code, however, is scaffolding only:

- `runner/crates/tee-verifier/src/verifier.rs` — `verify()` unconditionally returns `Ok(())`.
- `runner/crates/result-verifier/src/verifier.rs` — `Deterministic + tee_required` only checks that the `tee_attestation` field is present; it never invokes any verifier.
- `node/execution/src/runner/dispatcher.rs` — `tee_required` filters on a self-declared `runner.capabilities.tee_support` boolean with no cryptographic proof.
- `runner/crates/secrets-manager/src/manager.rs` — `get_secret()` accepts an attestation argument but ignores it.
- `runner/` has no quote-generation code, no DCAP/NRAS/SNP client, and no CVM/CoCo integration.

At the same time, a large body of Cowboy design work (prior research on PythonVM × TEE secure-kernel patterns, the 2026-04 TEE landscape review, the revised whitepaper §5.5 "TEE option", and CIP-10 §12.3 `BillingAttestation`) presumes that a real attestation pipeline will exist. This CIP defines that pipeline.

The industry landscape as of 2026-Q2 also dictates concrete choices: Intel IAS/EPID reached end-of-life on 2025-04-02, shifting the ecosystem to DCAP / Intel Trust Authority and to VM-level confidential computing (TDX, SEV-SNP); NVIDIA Confidential Compute (NCC) on H100/H200 is the de facto GPU TEE for AI; Confidential Containers (CoCo) and Trustee have become the deployable platform layer over raw hardware enclaves.

---

## 3. Specification

### 3.1 Terminology

- **CVM** — Confidential Virtual Machine. A VM whose memory is hardware-encrypted and attested (TDX Trust Domain, SEV-SNP VM, Nitro Enclave).
- **NCC** — NVIDIA Confidential Compute. Per-GPU hardware attestation producing a report signed by an NVIDIA-rooted key and a companion EAT token from the NVIDIA Remote Attestation Service (NRAS).
- **Quote** — A signed, hardware-generated attestation blob bound to an enclave/VM measurement and a caller-supplied `user_data`.
- **Measurement** — A hash of the initial state of the TEE (e.g., TDX `MRTD`, SNP `LAUNCH_DIGEST`, Nitro `PCR0..3`).
- **CAE** — Composite Attestation Envelope, defined in §3.4.
- **Measurement Binding** — On-chain Registry record that ties a Runner address to specific CPU/GPU measurements and a service public key, established at registration time.
- **Freshness Anchor** — The `(nonce, deadline, generated_at)` triple embedded in a CAE that prevents replay.

### 3.2 System Actor Map (authoritative)

This CIP supersedes conflicting address listings in `CLAUDE.md` and `node/types/README.md`. The canonical code in `node/runner/src/system_actors.rs` is authoritative.

| Address | Actor | Role |
|---------|-------|------|
| `0x01` | Runner Registry | Stake, capabilities, **measurement binding** (NEW) |
| `0x02` | Job Dispatcher | VRF selection, candidate filter |
| `0x03` | Result Verifier | Commit-reveal, verification mode dispatch |
| `0x04` | Secrets Manager | TEE-gated secret release (wired to `0x05`) |
| `0x05` | **TEE Verifier** | CAE verification (this CIP) |

### 3.3 Hardware Stack

| Tier | Choice | Role |
|------|--------|------|
| **Primary CPU** | Intel TDX | Confidential VM, VM-level isolation |
| **Primary GPU** | NVIDIA NCC (H100 / H200) | Confidential GPU for AI |
| **Secondary CPU** | AMD SEV-SNP, AWS Nitro Enclaves | Alternate backends, same CAE |
| **Tertiary** | ARM CCA, Intel SGX (legacy, `EconomicBond` only) | Not eligible for `Deterministic` mode |
| **Enablement** | Confidential Containers (CoCo) + Trustee / KBS | Attestation agent, key broker |
| **Attestation** | Intel DCAP or Intel Trust Authority; NVIDIA NRAS; AMD VCEK; AWS Nitro root | Quote collateral + verification |

Base CVM image: `cowboy/runner-tee-base:v1` (extends CIP-10 §5.5), with a reproducible build (Yocto/buildroot) so its measurement is publicly verifiable.

### 3.4 Composite Attestation Envelope (CAE v1)

Encoded as D-CBOR (same determinism guarantees as CIP-3). Top-level:

```rust
pub struct CompositeAttestation {
    pub version:     u16,                         // = 1
    pub cpu:         CpuAttestation,
    pub gpu:         Option<GpuAttestation>,      // required for AI jobs
    pub service_sig: ServiceSignature,
    pub freshness:   FreshnessAnchor,
    pub extra:       BTreeMap<String, Vec<u8>>,   // reserved
}

pub struct CpuAttestation {
    pub tee_type:       CpuTeeType,               // Tdx | SevSnp | Nitro | Sgx
    pub quote:          Vec<u8>,                  // raw quote bytes
    pub cert_chain_cid: Cid,                      // CIP-9 CID for full cert chain
    pub measurement:    [u8; 48],                 // MRTD / LAUNCH_DIGEST / PCR0..3
    pub pcr_extension:  Option<[u8; 32]>,         // RTMR (TDX runtime measurement)
}

pub struct GpuAttestation {
    pub tee_type:          GpuTeeType,            // NvidiaNcc
    pub nras_token:        Vec<u8>,               // NRAS-signed EAT (JWT)
    pub gpu_measurement:   [u8; 48],
    pub bound_cpu_pubkey:  [u8; 32],              // dstack-style CPU↔GPU binding
}

pub struct ServiceSignature {
    pub scheme:         SigScheme,                // Ed25519 | EcdsaP256
    pub service_pubkey: [u8; 32],
    pub sig:            Vec<u8>,                  // Sign(sk, task_id ‖ req_hash ‖ H(result) ‖ attest_digest)
}

pub struct FreshnessAnchor {
    pub nonce:        [u8; 32],                   // keccak(task_id ‖ req_hash ‖ submission_block_hash)
    pub deadline:     u64,                        // block height
    pub generated_at: u64,                        // block height at quote request
}
```

**Binding rule (MANDATORY).** The CPU quote's `REPORTDATA` (or SNP `REPORT_DATA`, Nitro `user_data`) MUST equal:

```
user_data = keccak256(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)
```

This binds the CPU attestation, the service signing key, the GPU NCC measurement, and the task into an atomic, tamper-evident receipt.

### 3.5 On-chain Storage Strategy

| Field | Where | Rationale |
|-------|-------|-----------|
| `attest_digest = keccak(cae_cbor)` | `task/result/<task_id>.cae_digest` | Audit handle |
| `cpu_measurement`, `gpu_measurement`, `service_pubkey` | Runner Registry `measurement_binding` | No duplication |
| Full CAE (30–100 KiB) | CIP-9 Relay Nodes / IPFS; on-chain stores CID only | Avoid state bloat |
| `seen_nonces[task_id]` | TEE Verifier state, GC'd after `DISPUTE_WINDOW_BLOCKS` | Replay protection |

### 3.6 TEE Verifier Actor (`0x05`)

#### 3.6.1 State

```rust
pub struct TeeVerifierState {
    pub cpu_roots: BTreeMap<CpuTeeType, Vec<RootCert>>,   // governance-updated
    pub nras_root: Vec<u8>,                                // NVIDIA NRAS pubkey
    pub seen_nonces: BTreeMap<JobId, BTreeSet<[u8; 32]>>,  // replay guard
    pub last_gc_block: u64,
}
```

`measurement` whitelists are held in the Runner Registry (per-service / per-runner `measurement_binding`), not duplicated here.

#### 3.6.2 System Instructions (opcodes 50–53)

| Opcode | Instruction | Caller | Behavior |
|:------:|-------------|--------|----------|
| 50 | `VerifyCae { cae, job_id, req_hash, result_hash }` | Result Verifier `0x03` | Runs §3.6.3 pipeline |
| 51 | `UpdateCpuRoot { tee_type, cert_der, effective_at }` | Governance `0x09` | ≥ 1-week delay before `effective_at` |
| 52 | `UpdateNrasRoot { pubkey, effective_at }` | Governance `0x09` | Same delay policy |
| 53 | `GcNonces { upto_block }` | Permissionless | Cleans `seen_nonces` older than `upto_block` |

#### 3.6.3 Verification Pipeline

```text
fn verify_cae(cae, job_id, req_hash, result_hash, registry) -> Result<(), TeeVerifyError>:
    1. Freshness:   now ≤ cae.freshness.deadline
                 AND (now − cae.freshness.generated_at) ≤ MAX_QUOTE_AGE       (= 150 blocks)
    2. Replay:      cae.freshness.nonce ∉ seen_nonces[job_id]
    3. Cert chain:  verify(cae.cpu.quote) against cpu_roots[cae.cpu.tee_type]
                    — TDX  : PCS root → TD Module → TD
                    — SNP  : AMD root → VCEK → Report
                    — Nitro: AWS Nitro root → signing cert → attestation doc
    4. Measurement: cae.cpu.measurement  ∈ registry.binding(service).allowed_cpu_measurements
                AND cae.gpu?.gpu_measurement ∈ registry.binding(service).allowed_gpu_measurements
    5. Binding:     quote.REPORTDATA == keccak(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)
    6. Service sig: verify(service_pubkey, task_id ‖ req_hash ‖ result_hash ‖ attest_digest, sig)
    7. NRAS (if GPU): verify JWT against nras_root
                      AND token.claims.measurement == cae.gpu.gpu_measurement
    8. Accept → insert nonce into seen_nonces[job_id]; else → TeeVerifyError::<kind>
```

#### 3.6.4 Error Codes

```rust
pub enum TeeVerifyError {
    AttestFail,         // cert-chain failure
    RegistryMismatch,   // measurement not whitelisted
    SigInvalid,         // service signature invalid
    TaskExpired,        // deadline or MAX_QUOTE_AGE exceeded
    TaskReplayed,       // nonce already seen
    InvalidResultHash,  // result_hash != value in signed envelope
    UnsupportedTeeType, // root cert for this TEE type not configured
    NonceBindingFail,   // REPORTDATA mismatch
    TeeUnavailable,     // shared code path for sync callers (Runner couldn't get quote)
}
```

#### 3.6.5 Gas Budget

| Operation | Cycles | Cells |
|-----------|:------:|:-----:|
| `VerifyCae` (TDX + NCC), total | 200,000 | 64 |
| — Cert chain (≈7-layer ECDSA) | 120,000 | — |
| — measurement lookup (Registry) | 500 | — |
| — nonce set insert | 1,000 | 32 |
| `UpdateCpuRoot` / `UpdateNrasRoot` | 5,000 | 500 |
| `GcNonces` (per 1,000 entries) | 10,000 | 0 |

At `BLOCK_CYCLES_TARGET = 10_000_000`, a block can verify ≈ 50 CAEs before exhausting the target — sufficient headroom for the Runner lane.

### 3.7 Runner Registry Extension

`RunnerRecord` gains:

```rust
pub struct MeasurementBinding {
    pub cpu_tee_type:             CpuTeeType,
    pub allowed_cpu_measurements: BTreeSet<[u8; 48]>,
    pub allowed_gpu_measurements: BTreeSet<[u8; 48]>,     // empty → GPU not required
    pub service_pubkey:           [u8; 32],
    pub bound_at:                 u64,                     // block height
    pub expires_at:               u64,                     // default bound_at + RENEWAL_PERIOD
    pub status:                   BindingStatus,           // Active | Deprecated | Revoked
}
```

Registration flow (replaces current flag-only logic):

```text
1. Runner boots a CVM; guest-agent derives a service keypair.
2. Runner submits RegisterRunner(stake, rate_card, initial_cae, service_pubkey, claimed_measurements).
3. Runner Registry cross-Actor calls TEE Verifier `0x05::VerifyCae` with:
       nonce = keccak(runner_addr ‖ registration_block_hash)
4. On success: persist MeasurementBinding with status = Active.
5. On failure: reject; stake untouched.
```

**Renewal.** A binding MUST be renewed every `BINDING_RENEWAL_PERIOD` blocks (default 12,096 ≈ 7 days at 500 ms). Expired bindings transition to `Deprecated` and are no longer eligible for the TEE candidate pool, though historical results they signed remain verifiable.

### 3.8 Dispatcher Filter Change (CIP-2 §5.4 amendment)

Step 4 of CIP-2 §5.4 is amended to read:

> 4. **TEE filter:** If `tee_required`, the runner's `Runner Registry` record MUST contain a `measurement_binding` whose `status == Active` and `expires_at > submission_block`. Self-declared `capabilities.tee_support` booleans MUST NOT be used as a proof of TEE capability after this CIP activates.

### 3.9 Result Verifier Change (CIP-2 §9 amendment)

For `VerificationMode::Deterministic`:

1. Every result MUST carry a `CompositeAttestation`.
2. The Result Verifier invokes `TEE_VERIFIER::VerifyCae` for each result before performing the byte-identical match.
3. Any CAE failure fails the entire job (no partial results).

For all other modes, a CAE MAY be attached and, if present, MUST verify — but its absence does not fail the result.

### 3.10 Secrets Manager Integration

`Secrets Manager (0x04)` amends `get_secret`:

```rust
async fn get_secret(
    secret_id: SecretId,
    attestation: CompositeAttestation,           // now MANDATORY
    task_id: JobId,
) -> Result<SealedSecret, SecretError> {
    let policy = self.policies.get(&secret_id).ok_or(NotFound)?;
    // Cross-actor call into TEE Verifier
    verify_cae(&attestation, task_id, req_hash, result_hash = H(""))?;
    require!(policy.allowed_measurements.contains(&attestation.cpu.measurement));
    require!(policy.allowed_services.contains(&attestation.service_sig.service_pubkey));
    Ok(self.kbs.fetch_wrapped(secret_id, attestation.service_sig.service_pubkey).await?)
}
```

Secrets are delivered HPKE-wrapped to the Runner's `service_pubkey`; cleartext exists only inside the CVM.

### 3.11 `tee_call` SDK Helper

No new PVM syscall. `cowboy_sdk.tee.tee_call(...)` is a pure Python wrapper that emits a `SubmitJob` instruction with `VerificationMode::Deterministic` and `tee_required = true`. PVM determinism is unaffected.

### 3.12 BillingAttestation Reuse (CIP-10 §12.3 amendment)

The `BillingAttestation.tee_signature` field is redefined as:

```rust
pub tee_signature: Option<CompositeAttestation>,
```

Billing-path CAE verification uses the same `0x05::VerifyCae` pipeline, with `result_hash = keccak(billing_fields_rlp)`. No separate attestation protocol is introduced.

### 3.13 Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `MAX_QUOTE_AGE` | 150 blocks (≈75 s @ 500 ms) | Quote freshness window |
| `BINDING_RENEWAL_PERIOD` | 12,096 blocks (≈7 days) | Measurement binding re-attestation |
| `ROOT_UPDATE_DELAY` | 1 week | Governance delay for `UpdateCpuRoot` / `UpdateNrasRoot` |
| `SEEN_NONCE_GC_WINDOW` | = `DISPUTE_WINDOW_BLOCKS` (75) | When nonces can be GC'd |
| `MAX_CAE_ON_CHAIN_BYTES` | 64 (digest only) | Full CAE stored off-chain (CIP-9) |

---

## 4. Rationale

- **CPU + GPU composite via `REPORTDATA` binding.** Separate attestations for CPU and GPU can be mixed and matched by an adversary if not cross-bound. The `user_data = keccak(nonce ‖ pubkey ‖ gpu_measurement)` rule makes the CPU quote worthless without the matching GPU report and service key.
- **On-chain digest, off-chain body.** A full TDX quote plus cert chain is 30–100 KiB; anchoring only `attest_digest` keeps state growth linear in `block_count`, not in attestation size. The full CAE lives on CIP-9 Relay Nodes and is fetched on demand for audit.
- **Attestation-first registration vs. per-job attestation only.** Attesting only at job time admits a race: a Runner could attest, then swap binaries, then answer the job. Binding measurements at registration plus per-job CAE with `user_data` nonce binding closes this window — any binary swap invalidates both the binding and the per-job quote.
- **`0x04` and `0x05` as separate Actors.** The Secrets Manager is consumer-facing and policy-heavy; the TEE Verifier is a primitive. Splitting them lets other consumers (Registry registration, BillingAttestation, future CIPs) reuse the verifier without pulling in secret-release semantics.
- **Digest-only nonce set with `DISPUTE_WINDOW_BLOCKS` GC.** Nonces only need to prevent replay within the dispute window; longer retention wastes state.
- **No PVM syscall.** Introducing `tee_call` at the PVM layer would risk injecting non-determinism. Emitting a plain `SubmitJob` with `Deterministic + tee_required` achieves the same developer ergonomics with zero VM surface change.

---

## 5. Backwards Compatibility

- **Runners without TEE** continue to operate; they cannot be selected for jobs with `tee_required = true` (this was already the contract in CIP-2, but was not cryptographically enforced before this CIP).
- **Self-declared `runner.capabilities.tee_support`** is deprecated. After activation, the dispatcher ignores this field; `measurement_binding` is authoritative. Runners currently advertising a TEE boolean MUST re-register with a valid CAE before the activation block.
- **Existing `Deterministic` jobs** that relied on non-enforced `tee_required` MUST be updated; Runner operators MUST attest before activation to avoid job failures. A `--tee-soft-fail` flag on the Result Verifier is provided for one release only, emitting warnings instead of rejections; it is removed at the next release.
- **CIP-10 `BillingAttestation`** gains a richer `tee_signature` type. Old records with an empty field continue to route through the non-TEE dispute window (CIP-10 §12.3 unchanged).

---

## 6. Security Considerations

- **Forged quotes.** Rejected by root-certificate-chain verification. IAS/EPID (SGX legacy) is explicitly not accepted for `Deterministic` mode; it reached end-of-life on 2025-04-02.
- **Replay.** `nonce` is bound inside `REPORTDATA` and checked against `seen_nonces[task_id]` for the entire dispute window.
- **Measurement backdoor via governance.** `UpdateCpuRoot` / `UpdateNrasRoot` require a ≥ 7-day delay and Governance-controlled signing, mirroring the existing `GOVERNANCE_SYSTEM_ACTOR = 0x09` pattern.
- **NRAS centralization.** NVIDIA's attestation service is centralized. This CIP accepts the dependency for Phase 2; a threshold multi-provider fallback is deferred to a follow-up CIP.
- **CAE availability.** If CIP-9 Relay Nodes serving a CAE body are unreachable, the on-chain `attest_digest` still proves the receipt exists, but auditability is degraded. Runners SHOULD pin CAEs on at least `k` Relay Nodes where `k ≥ erasure-coding reconstruction threshold`.
- **GPU memory residue.** Addressed by CIP-10 §14.6 (MIG isolation, memory clearing) — not re-specified here.
- **Side channels on TEE hardware.** Known side-channel classes (e.g., foreshadow, downfall, platypus) are vendor-patched over time. Governance MAY temporarily blacklist a CPU microcode revision via `UpdateCpuRoot` collateral.
- **TDX supply concentration.** Today TDX is primarily available on Azure and GCP instance families. `Scope::RunnerPool(tdx_pool_id)` (CIP-2 §7) lets submitters require specific clouds or geographic regions; this CIP takes no position on which pool is preferred.
- **Soft-fail window risk.** The transitional `--tee-soft-fail` flag temporarily admits unverified attestations; operators MUST monitor for anomalous results during this window.

---

## 7. Implementation Roadmap

| Phase | Duration | Deliverable | Exit Criteria |
|:-----:|:--------:|-------------|---------------|
| **P0 — Scaffolding** | 2 weeks | Types, opcodes 50–53 (stub logic), `tee-runtime` crate skeleton | Workspace compiles; mock CAE round-trip in tests |
| **P1 — TDX-only MVP** | 6 weeks | Intel DCAP verification on-chain; Runner quote generation via `/dev/tdx_guest`; attestation-first registration; `Deterministic + tee_required` end-to-end | `examples/llm_chat` runs on TDX hardware; red-team: forged/mismatched/replayed quotes all rejected |
| **P2 — CPU + GPU + CoCo** | 6 weeks | NVIDIA NCC + NRAS; CoCo Kata UVM + Trustee KBS; Secrets Manager TEE-gating | Real LLM inference task with composite CAE fulfilled on-chain |
| **P3 — Multi-backend + Billing** | 4 weeks | SEV-SNP, Nitro secondary backends; CIP-10 `BillingAttestation.tee_signature` wired to `0x05`; governance measurement updates | ≥ 2 TEE backends live; dispute window exercised against a malicious Runner |

Total: ≈ 18 weeks. Runs in parallel with CIP-10 container runtime work, sharing the CoCo + Trustee stack.

---

## Appendix A: Reference Mapping (PythonVM × TEE prior art ↔ Cowboy)

| Prior-art term | Cowboy equivalent |
|----------------|-------------------|
| `tee_call` syscall | `cowboy_sdk.tee.tee_call()` → `SubmitJob` instruction |
| CAE | `cowboy_types::tee::CompositeAttestation` |
| Service Registry | CIP-2 Runner Registry + `measurement_binding` |
| `MsgFulfillAIRequest` | `submit_verified_result` (CIP-2 commit-reveal) |
| `AIRequest` / `AIFulfill` events | `JobSubmitted` / `JobFulfilled` (+ optional `tee_attested` flag) |
| pyvm-contract / pyvm-agent | Cowboy PVM (RustPython) / CIP-10 OCI CPython container |
| verify / replay path | Cowboy speculative execution + cached batch apply |

## Appendix B: 2026-04 TEE Landscape Survey

This appendix captures the TEE ecosystem snapshot that informed the hardware selections in §3.3, the `Deterministic`-mode restrictions in §3.9, and the Roadmap backend ordering in §7. "Cowboy positioning" records how this CIP treats each entry.

### B.1 Hardware / Platform / Cloud Execution Environments

| Project | Arch | Type | Isolation Mechanism | Open Source | Cloud Integration | 2026-04 Status & Cowboy Positioning |
|---------|------|------|---------------------|-------------|-------------------|------------------------------------|
| **Intel SGX** | x86 | Enclave | CPU-level memory encryption + EPC + enclave | Partial (HW proprietary; Linux stack open) | Azure Confidential Compute (SGX VM / AKS nodes) | IAS/EPID reached EOL on 2025-04-02; ecosystem shifted to DCAP / Intel Trust Authority. Linux SGX stack still maintained. **Cowboy:** `legacy` tier; permissible only with `EconomicBond` mode, **not** permitted for `Deterministic` (§3.3, §3.9). |
| **Intel TDX** | x86 | Confidential VM | VM-level HW isolation + memory encryption + Trust Domain | Partial (HW proprietary; parts of ecosystem open) | Azure / Google / Alibaba | Intel positions TDX as its newest confidential computing path; Azure and Google offer TDX-based confidential VMs. **Cowboy:** **primary CPU backend** (§3.3); P1 MVP target (§7). |
| **AMD SEV / SEV-ES / SNP** | x86 | VM memory encryption | Per-VM key + page-level encryption; SNP adds integrity | Partial (HW proprietary; QEMU/KVM open) | Azure Confidential VM, Google Confidential VM | SEV-SNP is the mainline; SEV / SEV-ES are historical evolutionary stages. Major clouds emphasize no-code-change VM-level confidential computing. **Cowboy:** **secondary backend** (§3.3); P3 target (§7). |
| **AWS Nitro Enclaves** | Nitro (Intel / AMD / Graviton) | Isolated enclave VM | Nitro isolation + vsock-only local comm + no network / no persistence | Partial (platform proprietary; CLI / SDK open) | AWS EC2 / KMS | Mature AWS path; supports most Intel / AMD / Graviton Nitro instances. Parent may run Linux or Windows Server 2016+; enclave itself is Linux-only. **Cowboy:** **secondary backend** (§3.3); P3 target (§7). |
| **ARM TrustZone / OP-TEE** | ARM | Secure World TEE | Secure / Normal World separation | Yes (OP-TEE) | OP-TEE / device-vendor ecosystem | OP-TEE repositories were still active through 2025; TrustZone remains the mainstream TEE for mobile and embedded devices. **Cowboy:** **not targeted** in this CIP — device-side TEE is out of scope for server-side off-chain compute. |
| **Arm CCA / RME / Realm** | Armv9-A | Realm / Confidential VM | RME + Realm World + Root/Monitor | Partial (reference stack open) | Arm reference ecosystem (emerging) | Arm has positioned CCA as the server-side confidential computing path for cloud and AI; attestation tooling is available but ecosystem is young. **Cowboy:** **tertiary backend** (§3.3); considered once commercial availability stabilizes. |

### B.2 Runtime / SDK / Container Enablement Layer

| Project | Platform | Type | Isolation | Open Source | 2026-04 Status & Cowboy Positioning |
|---------|----------|------|-----------|-------------|-------------------------------------|
| **Gramine** | x86 (SGX) | LibOS for SGX | LibOS + SGX enclave | Yes | Official docs position it as a way to run Linux apps inside Intel SGX; latest release v1.9. SGX-centric, not a multi-backend LibOS. **Cowboy:** **not used** — CIP-23 skips SGX LibOS in favor of VM-level confidential compute (TDX/SNP). |
| **Occlum** | x86 (SGX) | LibOS for SGX | Multi-process LibOS in one enclave + SGX | Yes (Apache-2.0 / BSD) | Latest release 0.31.0 (2025-03-24); continued focus on high-performance SGX LibOS. **Cowboy:** **not used** — same rationale as Gramine. |
| **Open Enclave SDK** | x86 / ARM | Enclave SDK | SDK abstraction + backend enclave / TEE | Yes (MIT) | README still emphasizes Intel SGX and preview-level OP-TEE / TrustZone support; repo updated in 2025. Developer SDK, not a low-modification migration path. **Cowboy:** **not used** — CIP-23 builds directly on DCAP + NRAS rather than an abstracted enclave SDK. |
| **Confidential Containers (CoCo) / Trustee** | Multi-arch | Confidential container stack | Kata UVM / TEE + remote attestation + KBS secret release | Yes | Official docs cover TDX / SNP / SGX / Arm CCA attestation via Trustee; CoCo has become the deployable platform layer over raw hardware TEEs. **Cowboy:** **primary enablement layer** (§3.3, §3.10); reused from CIP-10 container runtime. Trustee/KBS is the basis for `Secrets Manager (0x04)` secret release. |

### B.3 Research / Simulation / Archived Projects (non-authoritative)

| Project | Platform | Type | Open Source | 2026-04 Status & Cowboy Positioning |
|---------|----------|------|-------------|-------------------------------------|
| **Open-TEE** | x86 / Linux | Virtual TEE / simulation framework | Yes (Apache-2.0) | Development / testing tool for GP API prototyping; not a production hardware confidential computing solution. **Cowboy:** **not used** beyond possible local test scaffolding. |
| **Keystone** | RISC-V | Enclave framework | Yes | Official docs still mark as version 0.X and research-oriented; repo updated in 2025. **Cowboy:** tracked for long-term RISC-V / research track; not a commercial target. |
| **Hex Five MultiZone** | RISC-V | Embedded partition TEE | Yes (main repo archived 2025-05-07, read-only) | Archived; historical reference only. **Cowboy:** **not considered**. |
| **Sanctum** | RISC-V research prototype | Secure processor architecture | Yes (research prototype) | MIT CSAIL project page last updated 2017-10-13; a historical research project. **Cowboy:** **not considered**. |

### B.4 Authoritative Sources

- Intel TDX: <https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/overview.html> · <https://learn.microsoft.com/en-us/azure/confidential-computing/virtual-machine-options> · <https://cloud.google.com/confidential-computing/confidential-vm/docs/supported-configurations>
- Intel SGX / IAS EOL: <https://community.intel.com/t5/Intel-Software-Guard-Extensions/IAS-End-of-Life-Announcement/td-p/1545831> · <https://github.com/intel/confidential-computing.sgx> · <https://learn.microsoft.com/en-us/azure/confidential-computing/confidential-nodes-aks-overview>
- AMD SEV / SEV-SNP: <https://www.amd.com/en/products/processors/server/epyc/confidential-computing.html> · <https://www.qemu.org/docs/master/system/i386/amd-memory-encryption.html> · <https://cloud.google.com/confidential-computing/confidential-vm/docs/confidential-vm-overview> · <https://learn.microsoft.com/en-us/azure/confidential-computing/skr-flow-confidential-vm-sev-snp>
- AWS Nitro Enclaves: <https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave.html> · <https://docs.aws.amazon.com/enclaves/latest/user/getting-started.html> · <https://docs.aws.amazon.com/enclaves/latest/user/hello-kms.html>
- ARM TrustZone / OP-TEE: <https://optee.readthedocs.io/en/latest/general/about.html> · <https://github.com/op-tee>
- Arm CCA / Realm: <https://www.arm.com/architecture/security-features/arm-confidential-compute-architecture> · <https://learn.arm.com/learning-paths/cross-platform/cca_rme/cca/> · <https://learn.arm.com/learning-paths/servers-and-cloud-computing/cca-container/overview/>
- Gramine: <https://gramine.readthedocs.io/> · <https://github.com/gramineproject/gramine/releases>
- Occlum: <https://github.com/occlum/occlum> · <https://github.com/occlum/occlum/releases>
- Open Enclave SDK: <https://github.com/openenclave/openenclave>
- Confidential Containers / Trustee: <https://confidentialcontainers.org/docs/overview/> · <https://confidentialcontainers.org/docs/attestation/> · <https://confidentialcontainers.org/docs/attestation/installation/>
- Open-TEE: <https://github.com/Open-TEE/Open-TEE> · <https://open-tee.github.io/documentation/>
- Keystone: <https://docs.keystone-enclave.org/en/latest/Getting-Started/index.html> · <https://github.com/keystone-enclave>
- Hex Five MultiZone: <https://github.com/hex-five/multizone-sdk>
- Sanctum: <https://www.csail.mit.edu/research/sanctum-secure-processor>
- Internal Cowboy research — PythonVM × TEE secure-kernel architecture notes (see `research/`)
- Design background: `refs/plans/cowboy-tee-execution-design.md`

---

## Part II — v2 Revision (canonical; entitlement chain + interaction maps)

### 0. What this revision does

CIP-23 v1 (Created 2026-04-20) is the most recent CIP and is broadly well-aligned. v2 layers four clarifications:

1. The **TEE three-layer chain** — `sec.tee_required` entitlement vs. `VerificationConfig.tee_required` job-spec field vs. `measurement_binding` runner record. v1 doesn't make the lifecycle relationship explicit.
2. The **CIP-13 delegation interaction** — delegation does not affect TEE eligibility.
3. The **opcode space** — confirm 50–53 don't collide with CIP-13 v2's renumbered 44–48 or with CIP-10 v2's 60–63.
4. The `sec.tee_required` entitlement's `tee_type` parameter mapping to `VerificationMode` eligibility, and the addition of `nitro` to the canonical TEE-type list.

CIP-23 v1 §3.2 already declares itself authoritative on system actor addresses; v2 carries this forward.

### 1. The TEE three-layer chain

A TEE-required job touches three independent layers, each at a different lifecycle moment:

| Layer | Field / record | When set | Authority |
|---|---|---|---|
| **Actor manifest** | `sec.tee_required` entitlement (`registry.rs:158-167`) | Actor deploy time | Actor owner |
| **Job spec** | `VerificationConfig.tee_required: bool` (`runner/src/types.rs:171`) | At `submit_task` time | Submitter |
| **Runner record** | `measurement_binding` (CIP-23 §3.7) | Runner registration / renewal | Runner |

Resolution rule:

- If the actor's manifest declares `sec.tee_required`, all jobs the actor submits MUST set `tee_required = true` in the job spec. Submitter-side validation (`pvm_host.rs::submit_job`) rejects jobs that violate.
- The dispatcher (CIP-23 §3.8 amendment to CIP-2 §5.4) selects only runners whose `measurement_binding.status == Active` AND `expires_at > submission_block` for jobs with `tee_required = true`.
- The Result Verifier (CIP-23 §3.9 amendment to CIP-2 §9) requires `CompositeAttestation` on every `Deterministic + tee_required` result.

The three layers are checked at three different times and provide defense in depth: the manifest layer prevents the actor from omitting TEE on its own jobs; the job-spec layer is the runtime carrier; the runner layer is the cryptographic guarantee.

### 2. `sec.tee_required` entitlement parameters → `VerificationMode` eligibility

`registry.rs:158-167` defines `sec.tee_required` with required parameter `tee_type: Str` (canonical values currently: `sgx`, `sev`, `tdx` per `registry.rs:211`). CIP-23 v1 §3.3 deprecates `sgx` for `Deterministic` (legacy tier) and adds Nitro as a secondary backend. v2 maps these explicitly:

| `tee_type` value | Eligible `VerificationMode` after CIP-23 |
|---|---|
| `tdx` | All modes including `Deterministic` |
| `sev` | All modes including `Deterministic` |
| `nitro` (new in CIP-23) | All modes including `Deterministic` |
| `sgx` | All modes EXCEPT `Deterministic` (legacy tier per v1 §3.3) |

`registry.rs::CANONICAL_TEE_TYPES` (currently `&["sgx", "sev", "tdx"]`) MUST add `"nitro"` to the valid set per CIP-23 v1 §3.3. This is a one-line code change — append `"nitro"` to the const slice.

### 3. Interaction with CIP-13 (delegation)

A runner with delegations MAY hold a TEE `measurement_binding`. Properties:

- Delegated stake counts toward the runner's `effective_stake` for VRF selection weight (per CIP-13 v2 §2 amendment to CIP-2 §5).
- Delegated stake does NOT affect TEE eligibility. Eligibility is determined solely by `measurement_binding.status` per CIP-23 §3.8 — a categorical capability check, not a stake threshold.
- A runner with low self-stake but high delegated stake CAN be a high-throughput TEE runner: eligible because of `measurement_binding`, high VRF weight because of `effective_stake`. The 10% `MIN_SELF_BOND_BPS` (CIP-13 §4.2) ensures meaningful skin in the game even when most stake is delegated.
- Slashing for forged attestation: self-stake is uncapped; delegator slash is capped at `MAX_DELEGATION_SLASH_PER_EPOCH_BPS = 500` (5%) per the CIP-13 §3.6 algorithm.

### 4. Opcode space confirmation

| Opcode range | Instructions | Source |
|---:|---|---|
| 40–43 | `UpdateSettlementConfig`, `FundActor`, `KeyDelivery`, `UpgradeActor` | current code |
| 44–48 | CIP-13 delegation instructions (renumbered from v1) | CIP-13 v2 §1 |
| 49 | (reserved) | — |
| **50–53** | **`VerifyCae`, `UpdateCpuRoot`, `UpdateNrasRoot`, `GcNonces`** | **CIP-23 (this CIP)** |
| 54–59 | (reserved) | — |
| 60–63 | Container Registry instructions | CIP-10 v2 §5 |

No collisions. CIP-23 v1 §3.6.2 opcode 50–53 allocations stand.

### 5. Secrets Manager interaction with delegation

CIP-23 v1 §3.10 makes `get_secret` require a `CompositeAttestation`. v2 clarifies: a runner accepting delegations may still request and use secrets via `get_secret` — release is gated on TEE measurement, not on stake source. Delegators have no claim on or visibility into secrets accessed by the runner they delegate to.

### 6. Backwards compatibility

CIP-23 v1 is itself in P0 (Scaffolding) status per its §7 roadmap. v2 changes are tightly scoped clarifications:

- Layer separation in §1 is documentation, not a state change.
- `nitro` addition to `CANONICAL_TEE_TYPES` is a one-line code change.
- Opcode confirmation is documentation.
- CIP-13 interaction is documentation.

No existing deployed system is affected.

