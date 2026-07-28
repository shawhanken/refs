# COW-2504 — TEE-signed BillingAttestation → CAE verify pipeline: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use `- [ ]` checkboxes.

**Goal:** A container-billing meter becomes chain-authoritative — settled immediately and immune to disputes (CIP-10 §12.3) — **if and only if** the runner's `BillingAttestation` carries a Composite Attestation Envelope (CAE) that passes chain-side verification binding the CAE to `(job_id, runner, metered fields)`; otherwise settlement stays behind the dispute window exactly as today.

**Architecture:** Reuse the *shipped* per-result **light** CAE verify (`verify_result_cae_light`, `node/execution/src/cbss.rs:4203`) — freshness + replay + Ed25519 service-sig + Active `MeasurementBinding`, **no SNARK** — applied to a new **billing preimage** (`result_hash = keccak(billing_fields)`, `scope_id = billing_id`, `req_hash = empty_req_hash()`, per CIP-23 §3.5 billing row). The runner produces the billing CAE with the byte-identical producer contract it already uses for job-result CAEs (`nitro_cae.rs`). The immediate-settle path is **activation-gated dormant** (`BILLING_TEE_IMMEDIATE_ACTIVATION_HEIGHT = u64::MAX`) so the change is byte-identical below activation and flips as a coordinated flag-day — the same idiom as `TEE_REQUIRE_BINDING_ACTIVATION_HEIGHT`. The load-bearing invariant — *authority comes only from a verified CAE, never from a marker's presence* (`spoofed_tee_signature_grants_no_authority`, `verifier.rs:8981`) — is preserved and extended.

**Tech Stack:** Rust. node crates `cowboy-types` (`tee.rs`), `cowboy-execution` (`cbss.rs`, `runner/verifier.rs`, `execution/system_instruction.rs`), `cowboy-runner` types; runner crates `runner-tee`, `runner-container`, `runner-common`. BLAKE3/keccak256 + Ed25519 via `commonware_cryptography`; D-CBOR via `ciborium`.

---

## 0. Scope, non-goals, and the central invariant

**In scope.** (1) A canonical, byte-identical-across-stacks `billing_fields` preimage + `billing_id`; (2) the runner producing a billing-path CAE (today `tee_signature: None`, `cae: None` at `runner/crates/runner-container/src/executor.rs:248,252`); (3) a chain-side `verify_billing_cae_light`; (4) an activation-gated immediate-settle in `settle_container_compute` and a matching dispute rejection; (5) preserving/extending the anti-spoof invariant; (6) the stale `0x11` doc-comment.

**Non-goals.** The **SNARK chip-root** pipeline (`VerifyCae` opcode 125 Full mode, `handle_verify_cae`, `cbss.rs:2317`) — the light path deliberately skips it (CIP-23 §3.8.5). No new opcode (the immediate-settle is inline in the existing result-finalization path; dispute rejection is in the existing `DisputeContainerBilling` handler, opcode 165). The `binary64`/WP-§207 governance question (CIP-23 §3.5.1a) does **not** touch billing — billing fields are integers, so `billing_fields` has no float ambiguity.

**The invariant that must never regress (`verifier.rs:1088-1098`, test `verifier.rs:8981`):** a `tee_signature`/attestation *marker* grants nothing. Authority to settle immediately and reject a dispute MUST derive **only** from `verify_billing_cae_light(...) == Ok`. A present-but-unverifiable CAE, a self-report (`metered:false`), or a spoofed string all keep the current deferred-behind-window behavior and full-escrow-on-dispute. Every task below is written to hold this.

---

## 1. Architecture decisions (locked)

**D1 — Reuse the light verify, not the SNARK.** CIP-23 §3.8.5 defines a `Light` mode (per-call, hot path) that verifies the quote signature against the binding's `bound_quote_key` and skips the SNARK. `verify_result_cae_light` (`cbss.rs:4203`) already implements it for job results. Billing clones this with billing preimages. This keeps COW-2504 bounded and consistent with the shipped trust model (§3.8.2 interim/operator-root + Nitro-on-service-sig).

**D2 — Billing has its own CAE + preimage, distinct from the job-result CAE.** The job CAE binds `result_hash = keccak(result.data)` (`cae_result_hash`, `verifier.rs:1832`). Billing must bind the *metered fields*, so it needs its own preimage and its own CAE carried inside `BillingAttestation` (per CIP-10 §12.3: "`BillingAttestation.tee_signature` will upgrade to `CompositeAttestation`"). We replace `tee_signature: Option<String>` with `tee_attestation: Option<Vec<u8>>` = D-CBOR of a `CompositeAttestation`.

**D3 — Canonical `billing_fields` preimage is a consensus surface → single-sourced + golden-pinned + byte-identical on both stacks.** `BillingAttestation` is transported as serde-JSON inside `RunnerResult.data.billing` and read by execution at settlement, so a non-canonical preimage that differs runner-vs-node would make every honest attestation fail verification (or worse, verify inconsistently across validators). Treat it exactly like the CIP-11 §12.6 wire mirrors: define once in `cowboy_types::tee`, mirror byte-for-byte in the runner, and pin a shared golden-hex fixture on both sides (the discipline from the JobProgress/CapabilityDelta work). The spec calls it `billing_fields_rlp`; the name is nominal — Cowboy uses fixed-layout big-endian concatenation, not Ethereum RLP. Wire it through the already-present-but-unused `reportdata_billing` (`tee.rs:292`).

**D4 — Activation-gated dormant.** New `BILLING_TEE_IMMEDIATE_ACTIVATION_HEIGHT: u64 = u64::MAX` in `constants.rs`, threaded through a `billing_tee_immediate_active(block_height, activation_height)` predicate (the MRU idiom — never inline-compare against the `u64::MAX` const). Below activation: `settle_container_compute` ignores any CAE and defers as today → byte-identical. At/above: a verified CAE settles immediately and marks the settlement CAE-final so a later dispute is rejected. Activation is a coordinated flag-day, out of scope for this ticket.

**D5 — `billing_id`.** CIP-23 §3.5 billing row uses `scope_id = billing_id` with `nonce = keccak(billing_fields_excl_sig ‖ submission_block_hash ‖ b)`. Define `billing_id = keccak256(job_id ‖ runner_addr)` (a stable per-(job,runner) identifier; the freshness/replay protection comes from `nonce` + `seen_nonces[job_id]`, not from `billing_id`). Pin it. `req_hash = empty_req_hash()` (`tee.rs:274`), matching the other request-less paths so the service-sig preimage stays byte-exact.

---

## 2. File structure

- **`node/types/src/tee.rs`** — add `billing_fields_preimage(job_id, runner, fields) -> Vec<u8>`, `billing_id(job_id, runner) -> [u8;32]`, `billing_result_hash(...)`; wire `reportdata_billing`. Golden-pinned tests. *Responsibility: the canonical billing preimage, single source of truth.*
- **`node/runner/src/types.rs`** — `BillingAttestation.tee_signature: Option<String>` → `tee_attestation: Option<Vec<u8>>`; keep `actual_compute_cost()`. *Node-side view read at settlement.*
- **`runner/crates/runner-common/src/types.rs`** — mirror the `BillingAttestation` field change (+ fix stale `0x11` comment at `:270`). *Runner-side producer type.*
- **`runner/crates/runner-tee/src/billing_attestor.rs`** (new) — produce a billing CAE, mirror of `result_attestor.rs`. *Runner CAE producer.*
- **`runner/crates/runner-tee/src/billing_preimage.rs`** (new, or in runner-common) — byte-identical mirror of `billing_fields_preimage`/`billing_id` + shared golden fixture. *Producer-side canonical preimage.*
- **`runner/crates/runner-container/src/executor.rs`** — replace `tee_signature: None` (`:248`) with an optional billing CAE when a TEE signer is present. *Wire producer into the container result.*
- **`node/execution/src/cbss.rs`** — add `verify_billing_cae_light(...)` cloning `verify_result_cae_light` (`:4203`) with billing preimages; reuse `verify_service_sig` (`:4066`). *Chain verify.*
- **`node/types/src/constants.rs`** — `BILLING_TEE_IMMEDIATE_ACTIVATION_HEIGHT`. *Dormant gate.*
- **`node/execution/src/runner/verifier.rs`** — `settle_container_compute` (`:1065`): gated immediate-settle on verified CAE; mark `PendingContainerSettlement` CAE-final. `finalize_container_settlements` (`:1275`) and the CAE-final flag. Preserve/extend `spoofed_tee_signature_grants_no_authority` (`:8981`). *Settlement gate.*
- **`node/runner/src/types.rs`** — `PendingContainerSettlement` (`:3063`): add `cae_final: bool` so a CAE-settled record is not re-openable by dispute.
- **`node/execution/src/execution/system_instruction.rs`** — `DisputeContainerBilling` (`:5694`): reject (no-op or explicit error) when `pending.cae_final`. *Dispute rejection.*

---

## 3. Tasks

### Task 1: Canonical billing preimage + `billing_id` (node/types)

**Files:** Modify `node/types/src/tee.rs`; Test: inline `#[cfg(test)]` in the same file.

- [ ] **Step 1 — Write the failing golden test.** Add to `tee.rs` tests: fixed inputs (`job_id = [0x11;32]`, `runner = [0x22;20]`, a `BillingAttestation` with `cpu_used_millicores: 1500, peak_memory_mib: 256, actual_duration_ms: 4200, gpu_seconds: 0, bytes_egressed: 1_048_576, cgroup_digest: [0x33;32], metered: true`) and assert `hex(billing_fields_preimage(...))` and `hex(billing_id(...))` equal pinned literals (initially `""`, filled from step-3 output). Also assert `billing_fields_preimage` is independent of `tee_attestation` (attestation field excluded — "`_excl_sig`").

- [ ] **Step 2 — Run, expect fail** (`billing_fields_preimage` undefined). `cargo test -p cowboy-types --lib tee::` → FAIL.

- [ ] **Step 3 — Implement.** Fixed-layout, big-endian, length-free (all fixed-width) so it is unambiguous:
```rust
/// CIP-23 §3.5 billing path — canonical preimage over the metered fields, bound
/// to (job_id, runner). Fixed-width big-endian; the `tee_attestation` field is
/// EXCLUDED ("billing_fields_excl_sig"). Byte-identical on runner and node.
pub fn billing_fields_preimage(job_id: &[u8; 32], runner: &[u8; 20], f: &BillingFields) -> Vec<u8> {
    let mut p = Vec::with_capacity(32 + 20 + 4 + 4 + 4 + 4 + 8 + 32 + 1);
    p.extend_from_slice(job_id);
    p.extend_from_slice(runner);
    p.extend_from_slice(&f.cpu_used_millicores.to_be_bytes());
    p.extend_from_slice(&f.peak_memory_mib.to_be_bytes());
    p.extend_from_slice(&f.actual_duration_ms.to_be_bytes());
    p.extend_from_slice(&f.gpu_seconds.to_be_bytes());
    p.extend_from_slice(&f.bytes_egressed.to_be_bytes());
    p.extend_from_slice(&f.cgroup_digest);
    p.push(f.metered as u8);
    p
}
pub fn billing_id(job_id: &[u8; 32], runner: &[u8; 20]) -> [u8; 32] {
    let mut b = Vec::with_capacity(52); b.extend_from_slice(job_id); b.extend_from_slice(runner);
    keccak256(&b)
}
/// result_hash for the billing CAE = keccak256(billing_fields_preimage).
pub fn billing_result_hash(job_id: &[u8;32], runner: &[u8;20], f: &BillingFields) -> [u8;32] {
    keccak256(&billing_fields_preimage(job_id, runner, f))
}
```
`BillingFields` is a small borrowed view (the 7 metered fields) so `types` need not depend on the `runner` crate's `BillingAttestation`. Run once with `--nocapture` printing the hex, paste the literals into Step 1.

- [ ] **Step 4 — Run, expect pass.** `cargo test -p cowboy-types --lib tee::` → PASS. Confirm the "excludes attestation" assertion holds (mutating `tee_attestation` leaves the preimage unchanged — it isn't an input, so this is structural).

- [ ] **Step 5 — Commit.** `feat(types): CIP-23 §3.5 canonical billing preimage + billing_id (COW-2504)`.

### Task 2: Runner-side byte-identical mirror + cross-stack golden fixture

**Files:** Create `runner/crates/runner-common/src/billing_preimage.rs`; Modify `runner-common/src/lib.rs`; Test: inline.

- [ ] **Step 1 — Failing test:** the SAME fixed inputs and the SAME pinned hex literals as Task 1 Step 1, asserting the runner's `billing_fields_preimage`/`billing_id` reproduce them. This is the cross-stack byte-identity pin (mirrors the JobProgress/CapabilityDelta golden-hex discipline).
- [ ] **Step 2 — Run, expect fail.** `cargo test -p runner-common billing_preimage` → FAIL.
- [ ] **Step 3 — Implement** a verbatim copy of the Task-1 functions (keccak256 via the runner's crypto util; `BillingFields` local mirror). No re-derivation — identical bytes.
- [ ] **Step 4 — Run, expect pass.** Same literals ⇒ PASS proves both stacks agree.
- [ ] **Step 5 — Commit.** `feat(runner-common): byte-identical billing preimage mirror + golden pin (COW-2504)`.

### Task 3: `BillingAttestation` carries a CAE

**Files:** Modify `node/runner/src/types.rs:3014`, `runner/crates/runner-common/src/types.rs`; Test: serde round-trip inline.

- [ ] **Step 1 — Failing test:** a `BillingAttestation { tee_attestation: Some(vec![1,2,3]), .. }` serde-JSON round-trips and, when `tee_attestation: None`, deserializes from the *old* JSON shape too (back-compat: absent field → `None`). Assert `actual_compute_cost()` is unchanged.
- [ ] **Step 2 — Run, expect fail** (field named `tee_signature`). FAIL.
- [ ] **Step 3 — Implement:** rename `tee_signature: Option<String>` → `tee_attestation: Option<Vec<u8>>` (`#[serde(default)]`, D-CBOR-encoded `CompositeAttestation`) in BOTH `node/runner/src/types.rs` and `runner-common`. Update the two node-side test constructions (`verifier.rs:4789/8758`) and the runner producer site to the new field name (producer set to `None` for now — Task 4 fills it). Keep field order/serde stable elsewhere.
- [ ] **Step 4 — Run, expect pass:** `cargo test -p cowboy-runner --lib` and `cargo test -p runner-common`. Then `cargo build --workspace` in node (shared struct → build validator/cli too, per the shared-struct rule).
- [ ] **Step 5 — Commit.** `refactor(billing): BillingAttestation carries an optional CAE (was unverified string) (COW-2504)`.

### Task 4: Runner produces the billing CAE

**Files:** Create `runner/crates/runner-tee/src/billing_attestor.rs`; Modify `runner-tee/src/lib.rs`, `runner/crates/runner-container/src/executor.rs:237-252`; Test: inline producer↔preimage test.

- [ ] **Step 1 — Failing test:** given a test Ed25519 signer, `BillingAttestor::attest(job_id, runner, &fields, now)` returns a `CompositeAttestation` whose `service_sig` verifies against the SAME preimage the node will check: `service_sig` over `billing_id ‖ empty_req_hash() ‖ billing_result_hash ‖ attest_digest`, and `reportdata_billing(nonce, service_pubkey, billing_fields_preimage)` matches. Assert byte-identity of the signed preimage with `verify_service_sig`'s construction.
- [ ] **Step 2 — Run, expect fail.** FAIL (attestor absent).
- [ ] **Step 3 — Implement** `billing_attestor.rs` as a mirror of `result_attestor.rs` (`:68`) / `assemble_nitro_cae` (`nitro_cae.rs:162`), but: `scope_id = billing_id`, `req_hash = empty_req_hash()`, `result_hash = billing_result_hash(...)`, `nonce = keccak(billing_fields_preimage ‖ submission_block_hash ‖ b)` (§3.5 billing nonce), `REPORTDATA` via `reportdata_billing`, freshness `now + FRESHNESS_WINDOW_BLOCKS` (`:23`, ≤ 75). Then wire `executor.rs:248`: when a TEE billing signer is configured, set `tee_attestation: Some(d_cbor(cae))`; otherwise `None` (unchanged non-TEE path).
- [ ] **Step 4 — Run, expect pass.** `cargo test -p runner-tee billing`.
- [ ] **Step 5 — Commit.** `feat(runner-tee): produce a billing-path CAE bound to the metered fields (COW-2504)`.

### Task 5: Chain-side `verify_billing_cae_light`

**Files:** Modify `node/execution/src/cbss.rs` (near `verify_result_cae_light:4203`); Test: inline positive + 4 negative cases.

- [ ] **Step 1 — Failing tests:** (a) a CAE produced by Task-4's attestor over fixed billing fields **verifies**; (b) tamper each field (e.g. `cpu_used_millicores+1`) → `result_hash` mismatch → **reject**; (c) wrong runner (binding/service key mismatch) → **reject**; (d) stale freshness (`generated_at` too old) → **reject**; (e) replayed nonce (`seen_nonces[job_id]`) → **reject**.
- [ ] **Step 2 — Run, expect fail.** FAIL (`verify_billing_cae_light` absent).
- [ ] **Step 3 — Implement** by cloning `verify_result_cae_light` (`cbss.rs:4203`): identical freshness (1), replay (2), `verify_service_sig` (`:4066`) over `billing_id ‖ empty_req_hash() ‖ result_hash ‖ attest_digest`, Active `MeasurementBinding` for `runner`, measurement whitelist, DCAP quote-sig vs `bound_quote_key`+REPORTDATA (Nitro rests on the service sig). Signature: `verify_billing_cae_light(cae, job_id, runner, result_hash, registry, snapshot, block_height) -> Result<(), TeeVerifyError>`. Factor the shared steps (1,2,7,binding) into a helper both light verifiers call, to avoid drift — but keep the two public entry points.
- [ ] **Step 4 — Run, expect pass.** `cargo test -p cowboy-execution -- cbss::` billing cases green; `verify_result_cae_light` tests still green (no regression from the refactor).
- [ ] **Step 5 — Commit.** `feat(execution): verify_billing_cae_light — light CAE verify over the billing preimage (COW-2504)`.

### Task 6: Activation-gated immediate settle

**Files:** Modify `node/types/src/constants.rs`, `node/runner/src/types.rs` (`PendingContainerSettlement`), `node/execution/src/runner/verifier.rs` (`settle_container_compute:1065`); Test: inline gated-behavior tests.

- [ ] **Step 1 — Failing tests:** with `activation_height = 0` (active), a settlement whose billing carries a CAE that `verify_billing_cae_light` accepts → **immediate** settle (`settle_at_block == block_height`, `disputed=false`, `cae_final=true`, `actual` = metered cost). With `activation_height = u64::MAX` (dormant) and the SAME input → **deferred** exactly as today (`settle_at_block == block_height + window`, `cae_final=false`). A CAE that fails verification, at either height → **deferred** (never immediate).
- [ ] **Step 2 — Run, expect fail.** FAIL (no gate / no `cae_final`).
- [ ] **Step 3 — Implement:** add `BILLING_TEE_IMMEDIATE_ACTIVATION_HEIGHT: u64 = u64::MAX;` + `#[inline] fn billing_tee_immediate_active(h: u64, act: u64) -> bool { h >= act }`. Add `cae_final: bool` to `PendingContainerSettlement`. In `settle_container_compute`, AFTER the existing `metered` decision (`:1099-1113`), if `billing_tee_immediate_active(block_height, ACT)` AND `tee_attestation` present AND `verify_billing_cae_light(...) == Ok`, set `settle_at_block = block_height`, `cae_final = true` (the verified metered cost is authoritative). Otherwise unchanged. The verified path still `.min(lock.amount)`.
- [ ] **Step 4 — Run, expect pass.** Gated tests green. `cargo test -p cowboy-execution -- verifier::` green.
- [ ] **Step 5 — Commit.** `feat(execution): gated immediate settle on a verified billing CAE (dormant) (COW-2504)`.

### Task 7: Dispute rejection + preserve/extend the anti-spoof invariant

**Files:** Modify `node/execution/src/execution/system_instruction.rs` (`DisputeContainerBilling:5694`); Modify tests in `node/execution/src/runner/verifier.rs`.

- [ ] **Step 1 — Failing / guard tests:**
  - **Extend `spoofed_tee_signature_grants_no_authority` (`:8981`)** to the new field: `tee_attestation: Some(<garbage bytes>)`, `metered:false` → still deferred, full escrow on dispute, `cae_final=false`. **This test MUST stay green throughout** — it is the anti-spoof invariant.
  - New `verified_cae_settlement_rejects_dispute`: with activation active + a valid CAE (Task 6 immediate settle, `cae_final=true`), a `DisputeContainerBilling` from the submitter within the window is **rejected** (settlement unchanged, no reputation hit misfire).
  - New `unverified_cae_dispute_still_charges_full`: garbage `tee_attestation` → dispute succeeds → finalize charges full escrow (current behavior).
- [ ] **Step 2 — Run, expect fail** on the two new tests. FAIL.
- [ ] **Step 3 — Implement:** in `DisputeContainerBilling` (`:5705` area), after loading `pending`, if `pending.cae_final` → return without setting `disputed` (idempotent no-op or an explicit `Err(AlreadyTeeFinal)`; pick no-op to match the existing idempotent-if-disputed shape at `:5711`). Leave all non-CAE paths untouched.
- [ ] **Step 4 — Run, expect pass.** All three tests green; full `cargo test -p cowboy-execution` green (no regression).
- [ ] **Step 5 — Commit.** `feat(execution): a CAE-final settlement rejects disputes; preserve anti-spoof invariant (COW-2504)`.

### Task 8: Stale address comment + docs

**Files:** Modify `runner/crates/runner-common/src/types.rs:270`; add a CIP-10 §12.3 / CIP-23 §3.5 impl note.

- [ ] **Step 1:** Fix the stale `"(0x11)"` doc-comment to `0x13` (Container Registry; `system_actors.rs:72`). No code change.
- [ ] **Step 2:** Add a short note in the PR body / a `refs/` doc: activation is a coordinated flag-day (`BILLING_TEE_IMMEDIATE_ACTIVATION_HEIGHT`), dormant until governance flips it alongside the other TEE gates.
- [ ] **Step 3 — Commit.** `docs(billing): correct stale 0x11→0x13 container-registry comment (COW-2504)`.

---

## 4. Activation / rollout

Dormant on merge (`u64::MAX`). Below activation: `settle_container_compute` never takes the CAE branch → **byte-identical** settlement/state root; the only observable change is the runner *carrying* a CAE in `data.billing` (informational, ignored by execution) and the `BillingAttestation` field rename (a serde field name — verify no external consumer keys on `tee_signature`; the wallet/indexer read `data` opaquely, but grep `tee_signature` across `wallet/`, `gateway/`, `cbfs/` before merge). Activation is a coordinated flag-day flip, sequenced with `TEE_REQUIRE_BINDING_ACTIVATION_HEIGHT` (a verified binding must exist for the runner before immediate-settle is meaningful) — out of scope here.

## 5. Review focus (for the marshal pass before/after implementation)

1. **Anti-spoof invariant** — the crux. `verify_billing_cae_light == Ok` is the *only* authority source; assert via `spoofed_tee_signature_grants_no_authority` staying green + a mutation check (force `verify_billing_cae_light` to `Ok(())` unconditionally → the spoof test must go RED).
2. **Cross-stack preimage byte-identity** — Task 1/2 golden pins must be the same literals; a drift = every honest attestation fails (liveness) or, worse, validators disagree. Mutation: change one field's width on one side → RED.
3. **Dormancy** — Task 6's `activation_height = u64::MAX` path must be byte-identical to pre-change `settle_container_compute`. Mutation: flip `billing_tee_immediate_active` to always-true → a "dormant defers" test must go RED.
4. **Replay/freshness** — billing `nonce` shares `seen_nonces[job_id]` with the job CAE; confirm no nonce collision lets a job CAE replay as a billing CAE or vice versa (distinct `scope_id`/`result_hash` already separate them, but assert it).
5. **`.min(lock.amount)`** must remain on the verified path — a verified CAE authenticates the *meter*, not the right to exceed the pre-locked escrow.

## 6. Recommended slicing

Three PRs, each independently green, base `devnet`:
- **PR-1 (Tasks 1–3):** canonical preimage (both stacks) + `BillingAttestation` field change. Pure types/serde; no behavior change. Low risk, unblocks the rest.
- **PR-2 (Tasks 4–5):** runner billing-CAE producer + chain `verify_billing_cae_light`. Adds capability; still no settlement behavior change (nothing calls the verify yet in the hot path except tests).
- **PR-3 (Tasks 6–8):** the gated immediate-settle + dispute rejection + invariant tests. The consensus-adjacent slice — dormant, flag-day-gated; gets the heaviest marshal/mutation pass.

## 7. Anchors (verified 2026-07-28)

`CompositeAttestation`/`attest_digest`/`reportdata_billing`/`empty_req_hash` — `node/types/src/tee.rs:224,279,292,274`. `verify_result_cae_light` — `cbss.rs:4203`; `verify_service_sig` — `cbss.rs:4066`; `handle_verify_cae` (Full, out of scope) — `cbss.rs:2317`; `VerifyCae` opcode 125 — `cowboy-protocol-codec/src/instruction.rs:200`. `cae_result_hash` — `verifier.rs:1832`; `settle_container_compute` — `verifier.rs:1065`; `finalize_container_settlements` — `verifier.rs:1275`; anti-spoof comment/test — `verifier.rs:1088,8981`. `DisputeContainerBilling` — `system_instruction.rs:5694` (opcode `SYS_DISPUTE_CONTAINER_BILLING=165`). `BillingAttestation` — `node/runner/src/types.rs:3014`; `PendingContainerSettlement` — `:3063`. Runner producer — `runner-container/src/executor.rs:237-252`; `result_attestor`/`assemble_nitro_cae` — `runner-tee/src/result_attestor.rs:68`, `nitro_cae.rs:162`. Gates — `constants.rs:779,787`; Container Registry `0x13` — `system_actors.rs:72`; stale `0x11` comment — `runner-common/src/types.rs:270`.
