# COW-2842 — real-validator spawned e2e: Receipt (foundation) + TeeAttestation + Liveness — build map

**Status:** feasibility fully traced (2026-08-06), approach **A1 (harness-native)** chosen. This is the actionable build plan; the three scenarios are **coupled** and all rest on the Receipt foundation below. Spawned e2e is **compile-verifiable locally; real validation is the branch-push CI pipeline** (`test-e2e-full-cbss.sh` / the `#[tokio::test]` harness with `CBSS_E2E_SPAWN_COWBOY_NODE=1`).
**Repo:** cbss (`crates/cbssd/tests/e2e/cbss_devnet_harness.rs`), against node handlers in `node/execution/src/cbss.rs` + `node/execution/src/runner/*`.

## Why the three are coupled (the key finding)

A CIP-24 **liveness challenge references an on-chain release receipt** (`handle_submit_liveness_challenge`, `cbss.rs:2780`: `load_json::<ReleaseReceiptSet>(release_receipt_key(release_id)).ok_or(InvalidData)`; `validate_liveness_attempt_proof` needs ≥threshold partials + the target proxy in the committee snapshot). And a **release receipt requires a real runner-job** (`handle_submit_release_receipt` → `validate_runner_job_assignment`, `cbss.rs:6476`: `get_job_spec(job_id)` → `JobNotFound`; `job_spec.submitter == body.actor`; `body.runner_id ∈ get_job_runners(job_id)`). So:

```
real runner-job (register runner + submit job → on-chain assignment)
        └─> Receipt scenario  (release request bound to that job → SubmitReleaseReceipt → cbss.release.receipt_recorded)
                └─> Liveness scenario (challenge a proxy re: that receipt; needs MIN_CHALLENGE_DELAY shrunk)
        TeeAttestation scenario (tee-required job variant → SubmitTeeAttestation)
```

The existing release scenarios use a **synthetic** `job_id = 0x5109` and only exercise the **slash** path (`SlashCbssProxy`, which uses the receipt as *evidence* and skips job validation) — which is exactly why the receipt-recorded path was deferred.

## Confirmed mechanism (feasibility)

- The harness submitter `cbssd::RpcSubmitter::submit_system_instruction(SystemInstruction)` is **`pub`** (`receipt_submitter.rs:610`) → the harness can submit **any** system instruction, incl. `SystemInstruction::RunnerRegister { registration: Vec<u8>, signature: Vec<u8> }` (`cowboy-protocol-codec/src/instruction.rs:623`).
- **Job assignment is on-chain and automatic** on job submit: the job-dispatcher system actor (0x92) `handle_job_submit` (`dispatcher.rs:811`) → `put_job_spec` + `expose_job_to_runners(store, job_id, &assigned)` (`:1919`). So no off-chain dispatcher daemon is required — a real `JobSubmit` tx suffices, given a registered matching runner.
- Reused scaffolding already in the harness: `spawn_local_cowboy_node`, `spawn_cbssd_committee`, `register_real_chain_proxies`, `set_secret`/SetSecret, DKG request/epoch waits, `fund_real_chain_address` (faucet), the **real QUIC partial-sign** flow (`run_real_validator_partial_sign_load`, COW-1052), `assert_real_chain_receipt`, `RpcSubmitter::submit_release_receipt`.

## Build steps (A1)

**Step 1 — harness helper `register_real_runner(key, rate_card, stake) -> Address`.**
Build `node/runner/src/types.rs::RunnerRegistration` (~20 fields; most default: reputation/active_jobs/entitlements/etc.), serialize to the registration blob + secp256k1-sign it, submit `SystemInstruction::RunnerRegister { registration, signature }` via `RpcSubmitter::submit_system_instruction`. Fund + stake the runner first (min stake per `CBSS`/`runner` constants). Assert the register tx receipt succeeds; poll `GET /runner/{addr}` (or the registry read) until the runner is visible.

**Step 2 — harness helper `submit_real_job(submitter_key, requirements) -> (JobId, assigned_runner)`.**
Submit a real `JobSubmit` (find the exact instruction/opcode that reaches `handle_job_submit`; note CIP-2 **v3 adaptive-M** needs block-seed/beacon context — use the **M==1** path to avoid the parent-beacon requirement, `dispatcher.rs:2078`). Requirements must match the Step-1 runner's rate card so the dispatcher assigns it. Poll `runner_query::get_job_runners` via RPC until the runner appears in the assigned set; return `(job_id, runner)`.

**Step 3 — actor secret-manifest entitlement.**
The release's `body.actor` must have a manifest granting `secrets.read` (or `secrets.verify`) for the secret (`validate_actor_secret_manifest`, `cbss.rs:6539`; `ReleasePurpose::Read/Verify`). Set the secret with an owner/actor whose manifest carries the entitlement (extend the existing `set_secret` setup), and make `body.actor == job_spec.submitter`.

**Step 4 — Receipt scenario `run_release_receipt_scenario`.**
Build `ReleaseRequestBody { job_id, actor=submitter, runner_id=assigned, secret_id, serve_epoch=dkg_epoch, request_block=<real head>, … }`; sign it with the runner key (`Secp256k1ReleaseRequestSigner`). Fetch a **real σ_i** from the spawned cbssd committee over QUIC (reuse the COW-1052 partial path) rather than a synthetic generator point, so `validate_liveness_attempt_proof` will later accept it. Assemble `SubmitReleaseReceiptArgs { runner_request, proxy_id, sigma_i, committee_epoch_at_serve, served_at_block, proxy_sig }` and submit via `RpcSubmitter::submit_release_receipt`. **Assert** `assert_real_chain_receipt("release_receipt", "SubmitReleaseReceipt", tx)` **and** watch for the `cbss.release.receipt_recorded` event (topic mapped at harness `:3284`). Add a `#[tokio::test]` entry gated like the siblings (`CBSS_E2E_SPAWN_COWBOY_NODE` / workspace-present skip).

**Step 5 (unlocks on 4) — Liveness scenario + `cbss-e2e-fast-liveness` node feature.**
Add a consensus-gated fast feature mirroring `cbss-e2e-fast-dkg-timeout` **exactly** (`cbss.rs:74-84`: `compile_error!` on release + `cfg(all(debug_assertions, feature))`; wire it through `execution`/`chain`/`validator` Cargo.toml). Gate `MIN_CHALLENGE_DELAY_BLOCKS` (prod `REQUEST_FRESHNESS_BLOCKS + 32 = 416`) down to a few blocks so a challenge is admissible shortly after the Step-4 receipt (`cbss.rs:87`). Scenario: submit a `SubmitLivenessChallenge` against a proxy **in** the receipt's set → auto-`Resolved` + bond refund (fast path, no response wait); optionally the unresolved→`SubmitLivenessChallengeResponse` path (cbssd responds via `receipt_submitter.rs:263`) within `LIVENESS_RESPONSE_BLOCKS`.

**Step 6 — TeeAttestation scenario.**
A tee-required job variant (registry `tee_required`) + trusted key; drive `SubmitTeeAttestation` (`cbss.rs:1774`, same `JobNotFound` gate → reuse Steps 1-2 with a tee-required rate card). Lowest priority; may itself defer if the tee-required job setup proves heavy.

## Risks / notes
- **Consensus safety of the fast feature (Step 5):** it shrinks a consensus constant — it MUST carry the same two-layer guard as fast-dkg-timeout (`compile_error!` on release, `debug_assertions`+feature gate), or a feature-built validator forks. Do not shrink `REQUEST_FRESHNESS_BLOCKS` globally (used by release freshness + receipt GC); gate `MIN_CHALLENGE_DELAY_BLOCKS` (and its derived `LIVENESS_CHALLENGE_MAX_AGE_BLOCKS`) specifically.
- **Determinism:** `served_at_block`/`serve_epoch`/`request_block` must be real chain values from the spawned node, and the σ_i real (from QUIC), or `validate_liveness_attempt_proof` rejects.
- **Validation:** compile-check with `cargo test -p cbssd --test <harness> --no-run`; real run is CI (`CBSS_E2E_SPAWN_COWBOY_NODE=1` + `CBSS_E2E_NODE_WORKSPACE`). Each `#[tokio::test]` must **skip cleanly** (early return + message) when the workspace/node isn't present, like the siblings at `:1905-2116`.
