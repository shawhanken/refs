# CIP-34 Demo — Proper End-to-End Fix Plan (no workarounds)

Goal: the CIP-34 cross-chain chat demo runs end-to-end through the REAL CIP-25 bridge —
natural-language chat → GLM parse → on-chain CIP-34 Withdraw intent → `bridge_actor.withdraw`
burns bCBY → 3-runner committee attests → `isFinalized` on real Sepolia — with the LLM
runner and the bridge committee coexisting on one chain.

## Root causes (3 layers, all confirmed)
1. **Runner nonce collision** (COW-2278) — already fixed upstream (runner #117); local runner
   checkout is 24 commits stale (detached HEAD @ 973f53f, one day before #117). *No fix needed —
   update local runner to devnet.*
2. **COW-2497** — CIP-2 v3 adaptive committee sizing draws `M` from network-wide `n_active` but
   eligibility is per-`job_type`; heterogeneous runners → single-capability job types starve
   (`InsufficientRunners`). *Fix implemented (dispatcher.rs:700 clamp M to job_type-eligible pool),
   compiles, in binary.*
3. **COW-2498** — COW-2440 slice-2 (#906, WIP) made the node's job decode canonical-only and
   deleted the CBOR path, but the frozen `cowboy_sdk` still CBOR-encodes JobSpecs → every
   actor→runner job fails admission (`unsupported version`). *This is the actual blocker.*

## Fix strategy for COW-2498: A1 (host-side re-encode) — Medium, ~1-1.5 days
Decode the SDK CBOR envelope at the one Rust convergence point and re-encode to canonical
JobSpec bytes before the `JobSubmit` deferred tx is built. Mapping is recoverable from git
(`b89578a3^` `parse_legacy_cbor_job_spec`); `job_spec::normalize()` fills all defaults.

---

## Phase 0 — DONE
- [x] COW-2497 dispatcher fix implemented + compiled + in validator binary.
- [x] COW-2497 + COW-2498 Linear tickets filed.
- [x] Root cause of COW-2498 confirmed (SDK CBOR vs node canonical; no migrated SDK exists).

## Phase 1 — Implement COW-2498 Strategy A1 (the crux)
Files: `execution/src/execution/actor_instruction.rs` (wire-in), new helper (re-created
`execution/src/runner/normalize.rs` OR private fn), tests.
- [ ] 1.1 Recover the CBOR→JobSpec mapping: `git show b89578a3^:execution/src/runner/dispatcher.rs`
      → `parse_legacy_cbor_job_spec` (~lines 570-1010) + `cbor_map_get`/`cbor_secret_key_ref`/
      `cbor_precondition` helpers.
- [ ] 1.2 New helper `cbor_envelope_to_canonical_jobspec(bytes, caller) -> Result<Vec<u8>>`:
      ciborium-decode `{kind:'runner_job', job_type, payload:{args,kwargs}, cid, reply_handler}`,
      map per job_type to codec `JobIntent`/`JobRequest`, `callback = {actor: caller, handler:
      reply_handler, payload: cid}`, `normalize(req) -> JobSpec`, `Encode::encode -> Vec<u8>`.
- [ ] 1.3 Field conversions to checked codec types: `f64→Milli`, `headers map→HeaderMap`
      (sorted/dedup), `body/arguments/params→CanonicalJsonBytes` (ciborium value → canonical JSON
      bridge — the fiddliest bit), `secrets→SecretRefInput{account,key_name}`, `verify→VerifyInput`.
- [ ] 1.4 Wire in at `actor_instruction.rs` `is_job_dispatcher` branch (~1210): replace
      `job_spec: outgoing_message.payload.clone()` with the re-encoded canonical bytes; fail-closed
      (`warn!` + skip deferred tx) on re-encode error. Covers BOTH `runner.llm` and `submit_job` paths.
- [ ] 1.5 Tests: round-trip (SDK-CBOR → helper → `decode_canonical` OK → `validate` OK) for
      llm/http/mcp/agent; port relevant `parse_job_spec_*`/`detect_job_type_*` unit tests.
- [ ] 1.6 `cargo fmt` + `cargo check -p cowboy-execution` green; `cargo test -p cowboy-execution`
      new tests pass.

## Phase 2 — Build + full clean redo
- [ ] 2.1 `cargo build --release -p validator` (bundles COW-2498 A1 + COW-2497 dispatcher fix).
- [ ] 2.2 **CRITICAL (audit-found 2nd skew): update local runner to devnet `95e44db`** —
      `git -C runner fetch && git checkout devnet && git pull` (discard my local nonce patch; devnet
      has #117 COW-2278 proper). The node (devnet) serves job assignments as a **canonical blob**
      (`query.rs::encode_job_spec_blob`/`decode_job_spec_blob` → `JobSpec::decode_canonical`), and
      only runner **#137 (COW-2447 slice-3)** decodes canonical assignments. The stale local runner
      (973f53f, pre-#137) expects the OLD format → would fail to decode the assignment even after the
      node A1 fix. Rebuild runner clean (`cargo build --release --bin runner-node`; the 24 commits
      include cross-repo pin flips COW-2352/2360, so expect a fuller rebuild).
      Consistent set: node(devnet+A1+COW-2497 canonical) ↔ runner(devnet #117+#137 canonical) ↔
      SDK(CBOR, bridged by A1).
- [ ] 2.3 Clean-restart Cowboy stack (`start_cowboy.sh`, faucet in config) → fresh chain (no
      mempool desync) + LLM runner (nonce 0) + chat actor.
- [ ] 2.4 Deploy bridge on fresh chain (`ETH_NETWORK=sepolia start_all.sh --no-clean`) → committee
      + Sepolia contracts + `.env.deploy`.
- [ ] 2.5 Copy `.env.deploy` → demo `env/bridge/deployed.env`; start demo server with bridge env.

## Phase 3 — Validate end-to-end
- [ ] 3.1 Chat "send N bucks to 0x…": LLM job ASSIGNED (COW-2497) + EXECUTED (COW-2498) → intent
      emitted (`chat:N` status=emitted, kind=Withdraw).
- [ ] 3.2 Real bridge leg: server calls `bridge_actor.withdraw` → burns bCBY → `publish_chain_root`
      job → committee `submitted_light_client` → `CowboyLightClient.isFinalized(0,H)==true` on Sepolia.
- [ ] 3.3 Browser walkthrough at :8780 (or curl proof): 走桥 end-to-end.

## Follow-ups (out of demo scope)
- COW-2498 proper: this A1 host re-encode should land as a node PR (flag-day) + close the WIP #906.
- COW-2497: land the dispatcher clamp as a node PR.
- Optionally route SDK `runner.send` through `submit_job` so entitlement gating covers the
  `send_message` path (separate follow-up noted by scope analysis).
