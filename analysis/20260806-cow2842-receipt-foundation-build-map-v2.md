# COW-2842 — Receipt (foundation) e2e — build map **v2** (corrected)

**Status:** supersedes `20260806-cow2842-receipt-foundation-build-map.md` (v1). v1's approach **A1** is right in spirit (harness-native, no off-chain dispatcher) but its **Steps 1–4 are unreachable as written** — they produce a job whose `submitter` is an EOA, and the receipt handler rejects that with `ActorNotFound` before any receipt is recorded. This v2 documents the defect (primary-source cited), gives the corrected **actor-initiated** design, the `job_id` discovery mechanism, and per-step verification points. **No product code touched yet — this is the design to deep-review before implementing.**

> **Deep-review verdict (2026-08-06, primary-source):** the actor-initiated path is **feasible — no second hidden contradiction found**. The single highest risk (parent beacon for M==1) is **discharged by code inspection**: `SeedStore::parent_beacon_canonical` (chain/src/seed_store.rs:148) returns `Some` for every normal running height — the immediately-prior round's verified seed is always retained (a miss can only be the pruned distant past, never the prior round), and bootstrap substitutes the genesis beacon; `None` is an abnormal cache miss. A healthy spawned devnet therefore assigns the job, exactly as the production runner system + `examples/*` rely on. The review also **corrected three mechanism errors** in an earlier draft of this doc (now fixed inline, flagged ⟪DR⟫): the guest emits an **SDK CBOR `runner_job` envelope**, not canonical `-codec` (host re-encodes at COW-2498 convergence point, actor_instruction.rs:1256); the job type is **`mcp`**, not `Custom` (an SDK actor type, no `submit_job` entitlement gate); and **`verification.mode` is not hand-set** — the envelope mapping pins single-runner actor types to `EconomicBond` at M=1 (job_envelope.rs:103-111), which *also* forces M==1 (`single_runner_ok = None | EconomicBond`). Cross-account `secrets=` refs are supported (job_envelope.rs `cbor_secret_ref`).

**Repo:** cbss harness (`crates/cbssd/tests/e2e/cbss_devnet_harness.rs`); node handlers in `node/execution/src/cbss.rs`, `node/execution/src/runner/*`, `node/execution/src/execution/actor_instruction.rs`; codec in `cowboy-protocol/crates/cowboy-protocol-codec/`.

---

## 1. The reachability defect in v1 (why "harness submits JobSubmit directly" fails)

`handle_cbss_submit_release_receipt` (cbss.rs:1284) calls `validate_release_authorization` (cbss.rs:6222), which imposes **two constraints on the same `body.actor`**:

1. **`job_spec.submitter == body.actor`** — `validate_runner_job_assignment` (cbss.rs:6476-6498). `JobNotFound` if the job is absent, `Unauthorized` if submitter ≠ actor, `RunnerNotAssigned` if `body.runner_id ∉ get_job_runners`.
2. **`body.actor` must be a deployed Actor** — cbss.rs:6243-6247: `store.get_actor(&body.actor).await?.ok_or(ExecutionError::ActorNotFound)?`, then `validate_actor_secret_manifest(&actor, …)` needs `actor.manifest`.

These cannot both hold for an EOA, because:

- **`job_spec.submitter` is forced to the tx sender**, not read from the wire — `dispatcher.rs:799` `spec.submitter = submitter;` where `submitter = tx.from` (stamped in `decode_and_admit`, dispatcher.rs:842-853). A harness-submitted `SystemInstruction::JobSubmit` therefore has `submitter = <harness EOA>`.
- **A deployed actor never has a private key** — `ActorInstruction::DeployActor` computes `actor_address = derive_actor_address(sender, salt, &code_hash)` (actor_instruction.rs:475). That derived address can never be a tx `from`, so it can never be a `job_spec.submitter` via a directly-submitted `JobSubmit`.
- `get_actor(<EOA>)` returns `None` (dispatcher.rs:1024 comment: "None if submitter is an EOA or legacy actor").

**Conclusion:** the only address that is simultaneously (a) a `job_spec.submitter` and (b) a manifest-bearing deployed actor is an actor that **submitted the job itself**. v1's Steps 1–2 (harness submits `RunnerRegister` + `JobSubmit`) give an EOA submitter → the receipt tx dies at `ActorNotFound`. v1 conflated "`body.actor` has a manifest" with "`body.actor` is the EOA that submitted the job."

---

## 2. Corrected mechanism — actor-initiated job

An actor submits a job by calling the host `submit_job` API from its PVM handler. That emits an **outgoing message to the job-dispatcher system actor**, which the executor turns into a **deferred `JobSubmit` tx whose `from` is the actor** (actor_instruction.rs:1133 "submit_job creates JobSubmit deferred tx when target is job_dispatcher"). When that deferred tx executes, `dispatcher.rs:799` stamps `submitter = <actor address>`. Now `get_actor(submitter) = Some(actor_with_manifest)` and the receipt authorization chain can pass.

```
DeployActor{code, manifest:secrets.read}  →  actor A_job (derived addr, funded)
        │  ExecuteActor(A_job) triggers its handler → host submit_job(spec)
        ▼
deferred JobSubmit tx (from = A_job)  →  handle_job_submit  →  submitter = A_job,
        M==1 (mcp job → EconomicBond), runner assigned = our dedicated runner R
        ▼
ReleaseRequestBody{ actor=A_job, runner_id=R, secret_id, serve_epoch, … }
        │  runner_sig by R's key; real σ_i from committee over QUIC (accept-all)
        ▼
SubmitReleaseReceipt  →  validate_release_authorization passes  →  cbss.release.receipt_recorded
```

---

## 3. The full authorization chain for a passing receipt (exact requirements)

From `handle_cbss_submit_release_receipt` (cbss.rs:1284-1470), in order. Each row is a constraint the harness setup must satisfy.

| # | Check (cbss.rs) | Requirement |
|---|---|---|
| chain | `validate_release_request_chain` (1296) | `body.chain_id == node chain_id` (harness fixtures use `1`) |
| freshness | 1325-1329, `REQUEST_FRESHNESS_BLOCKS=384` (:86) | `body.request_block ≤ head` and `head − body.request_block ≤ 384` → use a **recent head** |
| ordering | 1330-1332 | `body.request_block ≤ served_at_block ≤ head`; partial returns `served_at_block = request_block+1` → head must have advanced ≥1 block |
| epoch | 1333-1335 | `committee_epoch_at_serve == body.serve_epoch` (both = `dkg_epoch`) |
| sigma≠0 | 1336-1338 | real σ_i (non-zero) |
| runner sig | `verify_release_request_signature` (1339) | `runner_sig` recovers to `body.runner_id` → **sign the request with runner R's key** |
| secret ver | `secret_version_key` (1340-1348) | secret must exist on-chain, `!pending`, `recipient == body.recipient`, `wrap_epoch = Some(dkg_epoch)` |
| **authz** | `validate_release_authorization` (1353) | expanded below |
| proxy sig | `verify_proxy_response_signature` (1357) | real `proxy_sig` from the serving proxy (from the QUIC partial response) |
| committee | 1371-1376 | `args.proxy_id ∈ release_key.committee` at `serve_epoch` (true — real committee member) |
| σ_i pairing | `verify_release_receipt_partial` (1377) | `e(σ_i, G2::gen) == e(identity, public_share[proxy_index])` — holds for a **real** partial over the real committee (identity binds `body.secret_id.account`, `key_hash`, `version`, `wrap_epoch`, `mpk`) |
| fee | `charge_release_receipt_actor(body.actor, …)` (1434) | **`body.actor` (= A_job) must hold ≥ `RELEASE_FEE_PER_RECEIPT`** → fund A_job |

`validate_release_authorization` (cbss.rs:6222-6277) sub-chain:
- `validate_runner_job_assignment` — job exists, `submitter == A_job`, `R ∈ get_job_runners`.
- `release_purpose_for_job_secret(&job_spec, body)` (6416) — the secret **must be declared in the JobSpec**: as `precondition.secret_ref` → `Verify` (needs `secrets.verify`), or a member of `secret_refs` → `Read` (needs `secrets.read`). Else `SecretAccessDenied`. → **JobSpec.secret_refs must contain `SecretKeyRef{account, key_hash}`**.
- `get_actor(A_job).ok_or(ActorNotFound)` then `validate_actor_secret_manifest` (6539) — `A_job.manifest` has an `EntitlementGrant{id:"secrets.read"}` whose `params["keys"]: StrArray` contains an entry resolving (via `parse_secret_manifest_entry`, `secret_key_hash = keccak256(account‖key_name)`) to `(secret account, key_name)` matching `body.secret_id`. Cross-account entry form `"<account_hex>:<KEY_NAME>"` is supported (6589).
- ACL `validate_release_policy_acl` (6262, runs when `policy.actors.is_some() || trading_post.is_none()`) — `policy.actors` must be `Some([… A_job …])` (A_job ≠ secret account, so the same-account fallback does not apply).
- `validate_cip33_release_context` — with `body.cip33 = None` and a non–trading-post key (`trading_post = None`), this is a no-op.
- TEE — set `policy.tee_required = false` to skip `validate_runner_tee_for_release`.

### Consistent variable assignment (collapses the constraints)
- `A_secret` = **`harness.dkg_account()`** — the account that already did the real account DKG (`request_real_account_dkg`) and thus has an `AccountReleaseKey`/committee at `serve_epoch = dkg_epoch`. It owns the secret and is the release-key **recipient**.
- `A_job` = a **freshly deployed actor** (derived addr), **funded** (faucet), manifest `secrets.read → ["<A_secret_hex>:API_KEY"]`. This is `body.actor` and the job submitter.
- `R` = a **freshly registered dedicated runner** (its own key, funded, staked). This is `body.runner_id`.
- Secret: `SetSecret` by `A_secret` — `key_hash = compute_key_hash(A_secret, "API_KEY")`, `wrap_epoch = dkg_epoch`, `recipient = ReleaseKeyRef::Account(A_secret)`, `policy = { actors: Some([A_job]), tee_required: false }`.
- `ReleaseRequestBody`: `chain_id=1, secret_id={A_secret, key_hash}, version, actor=A_job, runner_id=R, recipient=Account(A_secret), job_id=<discovered>, serve_epoch=dkg_epoch, request_block=<recent head>, release_nonce, cip33=None`.

> Note: `body.secret_id.account == recipient account == A_secret` keeps the IBE identity and the release-key committee consistent (mirrors `run_real_validator_partial_sign_load`, which uses one account for secret_id + recipient + committee). Only `body.actor` and `runner_id` differ.

---

## 4. Build steps (v2), each with a verification point

Reused harness scaffolding (all verified present): `spawn_local_cowboy_node`, `spawn_cbssd_committee`, `register_real_chain_proxies`, `request_real_account_dkg` + the three `wait_for_*` helpers, `respawn_committee_accept_all` + `CbssdProxyPartialSignClient` (real QUIC σ_i, COW-1052), `fund_real_chain_address`, `wait_for_real_chain_receipt`/`receipt_status_is_success`/`real_chain_account_balance`/`wait_for_real_chain_height`, `RpcSubmitter::{new,submit_system_instruction,set_secret}`, `ReceiptSubmitter::submit_release_receipt`, `SubmitReleaseReceiptArgs::from_partial_response`, `assert_real_chain_receipt`. Event topic `"SubmitReleaseReceipt" => "cbss.release.receipt_recorded"` already mapped (harness :3284).

**Step A — guest actor (new file, e.g. `crates/cbssd/tests/e2e/fixtures/release_job_actor.py`).** ⟪DR-corrected⟫
Minimal PVM actor whose handler awaits the SDK once: `await cowboy_sdk.runner.mcp("noop-server", "noop-tool", secrets=[["<A_secret_hex>", "API_KEY"]])` (SDK at `node/pvm/Lib/cowboy_sdk/runner.py:159` `mcp(server, tool, *args, **kwargs)`; pattern like `examples/cross_chain_oracle/oracle_c.py`, `examples/bridge/bridge_actor.py`). This emits a CBOR `runner_job` envelope (`{kind:'runner_job', job_type:'mcp', payload:{kwargs:{secrets:[…]}}, …}`); the host re-encodes it to a canonical `JobSpec` at the single convergence point `cbor_envelope_to_canonical_jobspec` (actor_instruction.rs:1256, COW-2498). Consequences, all verified:
- `job_type = "mcp"` → **no `submit_job` entitlement gate** (pvm_host.rs:4287 `_ => None`), so the manifest needs only `secrets.read`.
- Single-runner actor types (`llm/http/mcp/agent`) are pinned to **`VerificationMode::EconomicBond` at M=1** by the envelope mapping (job_envelope.rs:103-111) — do **not** hand-set the mode. `EconomicBond` forces `M==1` (`single_runner_ok = None | EconomicBond`, dispatcher.rs:966-977).
- `parse_secrets` maps the cross-account entry `["<A_secret_hex>", "API_KEY"]` → `SecretRefInput{account:A_secret, key_name:"API_KEY"}` → `job_spec.secret_refs` (job_envelope.rs `cbor_secret_ref`), satisfying `release_purpose_for_job_secret` (Read).
- The job **never has to execute** — the receipt handler only checks assignment; the actor may stay suspended on the awaitable forever.

*Verification:* **DONE** — fixture written at `crates/cbssd/tests/e2e/fixtures/release_job_actor.py` and validated against the prebuilt real PVM (`node/pvm/target/debug/pvm`): it imports cleanly and `@runner.continuation` FSM-compiles into `trigger` + `trigger__resume` (the await point is recognized → the mcp job is emitted). The actor takes the secret account/key via its `trigger` JSON payload (so the manifest/secret account can be the dynamic `dkg_account`, not hard-coded).

**Step B — helper `deploy_release_job_actor(deployer_key, secret_account, key_name) -> Address`.** ⟪DR-corrected⟫
The cbss test crate depends only on `cowboy-protocol-{types,codec}`; `ActorManifest`/`EntitlementGrant` live in node/types (commonware-codec `Write`), **unreachable and un-vendored** — so the harness **cannot encode a manifest in-process**. Deploy via the **`cowboy` CLI** instead (authoritative encoding, no new dep):
`cowboy --indexer-url <rpc> actor deploy --code <fixture .py> --manifest-json <tmp manifest.json> --no-init --salt <hex> --private-key <deployer> --cycles-limit … --cells-limit …` (`cli/src/commands.rs:245`). The manifest JSON is generated in-harness (no static fixture): `{"entitlements":[{"id":"secrets.read","params":{"keys":["<A_secret_hex>:API_KEY"]}}]}` — `EntitlementGrant{id, params: Option<BTreeMap<String,ParamValue>>}`, `ParamValue` is `#[serde(untagged)]` so a JSON string array → `StrArray` (node/types/src/manifest.rs). The CLI prints the derived actor address and exits non-zero on `InvalidManifest`/`UnresolvedImport`. Fund the actor (faucet) so it can pay `RELEASE_FEE_PER_RECEIPT`. The `cowboy` binary must be built from the node workspace (same locate/build path the harness uses for the validator; `-p cowboy-cli --bin cowboy`); the existing `owner_cli` field/`CBSS_E2E_OWNER_CLI_BIN` may supply it. *Verification:* deploy exit 0 + printed address parsed; `GET /actor/{A_job}/manifest` shows `secrets.read`; `real_chain_account_balance(A_job) > 0`.
*(Fallback if the CLI is unavailable in a lane: `cowboy actor manifest-encode --manifest-json <path>` prints the codec bytes to stdout, which the harness wraps into `ActorInstruction::DeployActor{ manifest: Some(bytes), … }` and submits via `RpcSubmitter`.)*

**Step C — register the runner via the `cowboy` CLI.** ⟪DR-corrected⟫
`RunnerRegistration` (node/runner) and its bespoke serde blob + `keccak256` signing are also out of cbss's dependency reach; hand-building the JSON is fragile (must match a deserializer we can't compile against). Use the authoritative CLI: `cowboy runner --rpc-url <rpc> register --private-key <runner> --stake 50000` — `--job-types` **defaults to `llm,http,mcp,agent`** (includes `mcp`) and `--models` to `*` (commands.rs:4188), so the default registration already matches the `mcp` job. Fund the runner (faucet) with ≥ stake first. *Verification:* CLI exit 0; poll `GET /runner/{R}` → 200. Trigger the job **within `HEARTBEAT_TIMEOUT_BLOCKS=100`** blocks (freshness for `get_healthy_active_runners`).

> **Implementation convergence (Steps B–E all use the `cowboy` CLI).** cbss depends only on `cowboy-protocol-{types,codec}`, so runner/actor/manifest types are unreachable — every setup instruction that isn't buildable from codec goes through the CLI (authoritative encoding, mirrors the existing `owner_cli` shell-out): **B** `actor deploy --manifest-json`, **C** `runner register`, **D** `secrets set --actors <A_job> [no --tee-required]` (commands.rs:714 → `SecretPolicy{actors}`), **E** `actor execute --actor <A_job> --handler trigger --payload-text '{"secret_account":"0x<A_secret>","key_name":"API_KEY"}'` (**`--payload-text`**, raw UTF-8 → the fixture's `json.loads`; **not** `--payload-json`, which CBOR-encodes). The harness must locate/build the `cowboy` binary from the node workspace (`-p cowboy-cli --bin cowboy`) — factor a `cowboy_cli_bin()` helper. Only **Step F** (release request + receipt) is built in-process from codec types + `ReceiptSubmitter`, reusing the existing slash-path machinery.

**Step D — set the secret with the ACL, via the `cowboy` CLI.**
`cowboy secrets --rpc-url <rpc> --private-key <A_secret> set API_KEY <value> --actors 0x<A_job> --cbfs-output <tmp> --cbfs-uri cbfs://cow2842` (commands.rs:669/714 → `SetSecretArgs{ policy: SecretPolicy{ actors:[A_job], tee_required:false }, wrap_epoch:dkg_epoch, recipient:Account(A_secret) }`). Extends the existing SetSecret CLI path (harness :1677) with `--actors`. *Verification:* poll `/cbss/secret/{A_secret}/{key_hash}?version=1` until `wrap_epoch == dkg_epoch` (existing assertion, harness :445). `key_hash = compute_key_hash(A_secret, "API_KEY")` must equal the manifest entry's `secret_key_hash(A_secret,"API_KEY")` — both are the canonical `keccak256(account‖key_name)`.

**Step E — trigger via CLI + `job_id` discovery.**
`cowboy actor --rpc-url <rpc> execute --actor 0x<A_job> --handler trigger --payload-text '{"secret_account":"0x<A_secret>","key_name":"API_KEY"}' --private-key <deployer>` fires the fixture's `trigger`; the deferred `JobSubmit` executes in a following block. **Discovery:** the runner `R` is freshly registered and dedicated, so poll **`GET /actor/{R}/jobs`** (→ `runner_jobs_key(R)`, jobs assigned to `R`, runner.rs:653/21) until it returns one `job_id`. Cross-check `GET /job/{job_id}` → `submitter == A_job` and `GET /job/{job_id}/runners` contains `R`. *Verification:* both reads succeed with the expected submitter/runner. `job_id` is `keccak256(deferred_tx.digest ‖ block_height)` (dispatcher.rs:2025) — not harness-predictable, hence the poll.

**Step F — Receipt scenario `run_release_receipt_scenario`.**
Read the committed share (committee/threshold/mpk/vss/activation) as `run_real_validator_partial_sign_load` does; `respawn_committee_accept_all(&slots)`; build `ReleaseRequestBody` per §3 with `request_block = current head` and sign `runner_sig` with `R`'s key; fetch a real σ_i via `CbssdProxyPartialSignClient::partial_sign(endpoint, &signed_request)`; `SubmitReleaseReceiptArgs::from_partial_response(signed_request, response)`; submit via `ReceiptSubmitter::new(node_uri, &some_funded_identity).submit_release_receipt(&args)` (no tx-sender auth on the receipt; fee falls on `A_job`). **Assert** `assert_real_chain_receipt("release_receipt", "SubmitReleaseReceipt", &tx_0x)` → success + `cbss.release.receipt_recorded`. Gate the `#[tokio::test]` behind **`cbss-e2e-accept-all-auth`** (needed for the proxy to serve the request) + the `cowboy_node_workspace_if_present().is_none()` skip, mirroring the COW-1052 stress test (harness :2037-2058).

---

## 5. Risks / open sub-decisions

- **Parent beacon for M==1 — DISCHARGED (code inspection).** `select_runner_committee_simple` returns `InvalidData` if `block_seed_context.parent_beacon_canonical` is `None` once ≥1 candidate exists (dispatcher.rs:2070-2081). The production path (`chain/src/application.rs:672` → `speculative.rs` → `transaction_executor_impl.rs:71`) fills it from `SeedStore::parent_beacon_canonical` (seed_store.rs:148), which is `Some` for every normal height (prior-round verified seed, or genesis beacon at bootstrap) and `None` only on an abnormal cache miss — never the immediately-prior round. So a healthy spawned devnet assigns the `mcp`/`EconomicBond` job. No pre-build probe needed; if a CI run ever fails Step E with `InvalidData` at dispatch, re-examine seed retention, but this is not an expected failure mode.
- **Fees on `A_job`.** `charge_release_receipt_actor` charges `body.actor`; a delinquent actor emits `cbss.actor.delinquent` and can fail. Fund `A_job` generously.
- **Freshness coupling.** Register R → submit job (≤100 blocks) → discover job_id → issue release with `request_block = head` (≤384 back) → σ_i `served_at_block = request_block+1 ≤ head`. Keep the whole tail inside these windows; base `request_block` on the **current** head just before the partial fetch.
- **Do NOT touch Step 5/6 (Liveness / TEE) or the node repo here.** Liveness needs the `cbss-e2e-fast-liveness` consensus-gated node feature (`MIN_CHALLENGE_DELAY_BLOCKS 416 → few`), mirroring `cbss-e2e-fast-dkg-timeout`'s two-layer guard (`compile_error!` on release + `debug_assertions`+feature). The node repo is currently on an unrelated dirty branch — Step 5 is a separate PR after this foundation lands and unblocks on Step F.
- **Job type.** `mcp` is the pick (SDK actor type, `_ => None` entitlement, `EconomicBond`/M==1, cross-account `secrets=` supported). `agent` is an equivalent fallback (also `_ => None`, also `EconomicBond`). Avoid `llm`/`http` (they add `oracle.llm`/`http.fetch` to the manifest). `Custom` is **not** an SDK actor-path type (`build_intent` only accepts `llm/http/mcp/agent` for the actor path; consensus types are `publish_chain_root`), so it cannot be emitted from the guest — do not use it.
- **Actor stays suspended.** The guest `await runner.mcp(...)` suspends on a continuation that never resolves (no runner executes the job). That is intentional and harmless — the block that runs the deferred `JobSubmit` and assigns `R` is complete before the release request is built.

## 6. Validation

**Status: IMPLEMENTED + locally compile-verified (2026-08-06).** Branch `feat/cow2842-release-receipt-e2e` (cbss):
- Fixture `crates/cbssd/tests/e2e/fixtures/release_job_actor.py` — PVM-validated (imports + FSM-compiles to `trigger`/`trigger__resume`).
- Harness (test target `e2e`): `run_release_receipt_scenario` + helpers (`run_cowboy_cli`, `fund_to_at_least`, `wait_for_runner_registered`, `deploy_release_job_actor`, `discover_assigned_job`) and the gated `#[tokio::test] e2e_spawned_cowboy_node_records_real_release_receipt`, all in a `#[cfg(feature = "cbss-e2e-accept-all-auth")] impl DevnetHarness`.
- Product: `ReceiptSubmitter::submit_release_receipt_returning_hash` added (the existing `submit_release_receipt` discarded the hash the harness needs to observe the receipt event).
- Compiles: `cargo test -p cbssd --test e2e --features cbss-e2e-accept-all-auth --no-run` ✓ (and without the feature ✓; `cargo build -p cbssd` ✓); `cargo fmt` + clippy clean on the changed files.

**Verification commands:**
- Local: `cargo test -p cbssd --test e2e --features cbss-e2e-accept-all-auth --no-run` (compile). The `#[tokio::test]` **skips cleanly** (early return + message) when the node workspace is absent (`cowboy_node_workspace_if_present()`), mirroring the siblings.
- CI (real): `CBSS_E2E_SPAWN_COWBOY_NODE=1` + `CBSS_E2E_NODE_WORKSPACE`, `--features cbss-e2e-accept-all-auth`, via the spawned `#[tokio::test]` path. First run builds the `cowboy` CLI (`cargo run -p cowboy-cli`) once.

**Residual (CI-only) unknowns** — correct-by-construction from the verified maps, but first exercised in CI: exact `cowboy` CLI URL-flag acceptance per subcommand (`--indexer-url` for `actor`, `--rpc-url` for `runner`/`secrets`); the default runner rate-card `max_job_value` vs the 50 000-CBY stake 1.5× floor (over-funded to de-risk); `mcp` candidate-filter match for a throwaway server. Any mismatch fails loudly at the corresponding step with full stdio.
