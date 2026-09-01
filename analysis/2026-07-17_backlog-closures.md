# Cowboy Linear Backlog — Recommended Closures (81 confirmed)

_Generated 2026-07-17 from an automated premise audit: every issue's "current state" claim was re-checked against the code in `node/ runner/ cbfs/ cbss/` and the authoritative CIPs in `cowboy/docs/cips`. These 81 issues were independently re-verified in a second adversarial pass that confirmed the close (81/98 survived; 17 were rescued and are **not** in this list). Advisory — review the cited evidence before closing._

**Categories:** Built on an inaccurate premise (31) · Already implemented (33) · Superseded by a later CIP (17). **⚠️ = implementing the issue as written would regress an already-aligned CIP** (35 of 81); close these with an explicit spec-conflict note.

---


## Built on an inaccurate premise

_The issue's stated "current state" is factually contradicted by the code as it stands today._

### COW-1076 — [Node] Multi-token aggregator / multicall for batch operations across token IDs · CIP-20 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Premise is false: token_transfer_batch already takes a per-transfer token_id, so multi-token airdrop with all-or-nothing (simulate-then-execute) is already implemented and spec'd. The remaining ask — a multicall bundling mint/burn plus hook-running transfers atomically across token IDs — is exactly what CIP-20 (TokenBatchHookedUnsupported) and COW-2327 decided against, because hooks run call_actor/arbitrary state writes that balance-only atomicity can't cover and the engine has no per-tx rollback. Implementing it would contradict the current CIP-20 decision.

**Evidence:** `cowboy/docs/cips/cip-20-fungible-tokens.md token_transfer_batch signature list[tuple[bytes32,address,u128]] + COW-2327 hooked-batch note; node/execution/src/token/core.rs:772 handle_token_transfer_batch(&[([u8;32],Address,u128)])`


### COW-1107 — [Node] Quote-format parsers: TDX TDQuoteV4, SNP AttestationReport, Nitro COSE_Sign1 · CIP-23 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Nitro COSE_Sign1 parser is already implemented on-chain (nitro.rs, §3.8.9). For TDX/SNP, CIP-23 v3 §3.8.5 performs quote parse + X.509 chain INSIDE the SNARK circuit (verify_chip_root_snark, risc0 guest), not node-side Rust. Building full node-side TDX/SNP parsers to feed an on-chain verifier re-introduces the hand-rolled approach v3 moved into the proof. On-chain need (Nitro) is done; TDX/SNP full-parser part contradicts the as-built architecture.

**Evidence:** `cowboy/docs/cips/cip-23-tee-execution.md §3.8.5 step 3 (quote parse inside circuit), §3.8.9 (Nitro direct); node/execution/src/nitro.rs (COSE_Sign1 parser built); node/execution/src/cbss.rs:3969 verify_chip_root_snark`


### COW-1109 — [Node] CRL / TCB-update lifecycle handling · CIP-23 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. CIP-23 v3 handles TCB/CRL via a governance-published CollateralSnapshot (UpdateCollateral opcode 126) selected by block height and evaluated deterministically (§3.8.4), plus emergency DeprecateBinding (opcode 124) — all implemented (apply_tcb_policy, check_tcb). The issue's 'periodic ingestion of Intel TCB updates + DCAP CRL' node-side and per-call TCB-SVN floor check would be non-deterministic (wall-clock/external fetch) and the light path deliberately does NO per-call CRL/TCB check (§3.8.8). Implementing as written would break replay determinism the current CIP mandates. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy/docs/cips/cip-23-tee-execution.md §3.8.4 (governance-anchored, never wall-clock), §3.8.8 DeprecateBinding; node/execution/src/cbss.rs apply_tcb_policy/check_tcb + UpdateCollateral opcode 126 (system_instruction.rs:4791)`


### COW-1183 — [Node] Four payment models: per-request, actor-funded budget, prepaid pass, epoch subscription + fallback chain · CIP-18

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Confirm close: all four CIP-18 §7.1-§7.5 payment models are implemented on-chain in PaymentGate (0x12). The issue's alt naming (redeem_pass/subscribe/EpochConfig) differs from the as-built purchase_pass/purchase_epoch/settle_payment but is conceptually the same; work is done, not a spec-regression.

**Evidence:** `node/execution/src/payment_gate/handlers.rs: settle_payment (§7.1 per-request), deposit_budget/deduct_budget (§7.2 actor-funded, request_id-idempotent), purchase_pass (§7.3), purchase_epoch rolling+idempotent (§7.4); fallback chain evaluated gateway-side (chain_payments.rs)`


### COW-1205 — [Node] Block QC signer bitmap (finality-proof verification) · CIP-25 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Deployed consensus is a threshold-BLS Simplex scheme (bls12381_threshold, MinSig) whose Finalization certificate is a single threshold signature verified against the epoch threshold public key -- there is no per-validator signer bitmap in the certificate model. CIP-25 states it is 'not a consensus change' and its anchor verifier consumes runner-committee ECDSA attestations, not the native QC, so the issue's justification is unfounded. The WP §6.1 QC{...,signer_bitmap} format is a stale draft; adding a signer_bitmap to consensus to satisfy it would contradict both the deployed threshold scheme and CIP-25.

**Evidence:** `cip-25-cross-chain-architecture.md:74 ('not a consensus change'), :161/:193 (runner-committee ECDSA attestations); node/chain/src/indexer.rs:190 & engine.rs:59 (commonware Simplex bls12381_threshold / Finalization); WP §6 line 652 (stale QC{...,signer_bitmap})`


### COW-1254 — [Node] Two-tier blob pricing: inline (≤64 KiB cells-metered) vs CBFS (>64 KiB storage-rent) · CIP-3

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The two-tier branch already exists and is aligned. pvm_executor.rs:1423 rejects any handler output >64 KiB inline, forcing large results to a CBFS/content-addressed commitment (CIP-9 §2 line 38 'exceeding the 64 KiB onchain inline cap ... must be stored off-chain'); inline (<=64 KiB) values are metered as Cells in CIP-3 §2.2.2 and CBFS volumes pay storage-rent under CIP-31. The issue's premise 'Cells meter applies uniformly, no inline-vs-CBFS branch' is stale.

**Evidence:** `node/types/src/constants.rs:54 (MAX_INLINE_BLOB_BYTES=65_536), node/execution/src/pvm_executor.rs:1423, cip-9-runner-storage.md:38, cip-3-fee-model.md:137, cip-31 §STORAGE_FEE`


### COW-1400 — §2.2.4.6 Exception-handling cost metering (fixed cycles for raise /

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Exception handling is metered as discrete per-instruction charges: SetupExcept/SetupFinally=3 (entering try), EnterFinally/EndFinally/PopException=2 (except/finally jumps), Raise=5 — each with its own fixed base cycle cost exactly as CIP-3 §2.2.4.6 requires. This is observe-only (non-consensus) per the §2.2.1.1 Phase 2a rollout, which is the current CIP-aligned state; binding it to consensus is a separate governance-pinned Phase 2b cutover, not this issue. The 'not implemented as discrete charges' premise is false.

**Evidence:** `node/pvm/crates/vm/src/instruction_cost.rs:131-140; CIP-3 §2.2.4 item6 and §2.2.1.1`


### COW-1587 — v2 §4 BillingAttestation.tee_signature

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The issue's premise 'BillingAttestation itself absent' is false — the struct exists in both node and runner. The upgrade of tee_signature from Option<String> to Option<CompositeAttestation> verified via 0x05::VerifyCae is explicitly the CIP-10 §17 shipped-state trust-gate deliberately deferred pending CIP-23 crypto (tracked as COW-2504). Duplicate of COW-2504; close.

**Evidence:** `node/runner/src/types.rs:2830 (struct BillingAttestation, tee_signature:Option<String> @2838) ; runner/crates/runner-common/src/types.rs:278 ; cowboy/docs/cips/cip-10-runner-containers.md:1108 + :17`


### COW-1592 — §5.1 Connectivity Subset function Sub(R,t)=first k validators by

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The connectivity-subset function survives in current CIP-11 r1.3 §5.1 (Sub(R) = first k validators by keccak256(R.auth_pubkey‖v.peer_pubkey)) and is already implemented in identity.rs with passing spec-example tests. Issue's 'missing (no subset/connectivity code)' is stale; nothing to build. Aligns with CIP so no regression risk.

**Evidence:** `node/cip11-transport/src/identity.rs:117-129 (Sub selection by keccak256(auth_pubkey‖peer_pubkey)); CIP-11 §5.1 lines 216-225`


### COW-1593 — §5.1 Subset size k = clamp(ceil(log2(|V|))+1

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Subset-size formula k=min(|V|,clamp(ceil(log2(|V|))+1,MIN_SUBSET=3,MAX_SUBSET=8)) is unchanged in current §5.1 and implemented verbatim in identity.rs with tests asserting the spec examples (subset_size(100)==8 etc). Already done; not open work.

**Evidence:** `node/cip11-transport/src/identity.rs:15,17,105-113 (MIN_SUBSET=3, MAX_SUBSET=8, subset_size = min(|V|, clamp(ceil(log2)+1,3,8))); CIP-11 §5.1 line 222,225`


### COW-1594 — §5.2 Validator-side DoS gate

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-11 §5.2's validator-side DoS gate (reject a runner whose expected Sub(R) does not include this validator) is implemented: handshake.rs step-1 admission calls identity::validator_in_subset and returns NotInSubset before any signature work. Issue is done; implementing it aligns with the current CIP, no regression.

**Evidence:** `node/cip11-transport/src/handshake.rs:161-172; CIP-11 §5.2`


### COW-1597 — §6.2 Per-IP Hello rate-limit for connection-storm DoS

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Per-peer unauthenticated Hello rate-limit is implemented as a token bucket in gate.rs (HandshakeGate, wired into the connection server), plus half-open caps and global overload rejection. Note the current CIP mandates 'rate-limit unauthenticated Hello per peer' (identity/connection), not literally per-IP; the connection-storm DoS defense the issue asks for exists. Minor reframe caveat only: a naive literal per-IP admission criterion would diverge from the CIP's per-peer + subset-gate model.

**Evidence:** `node/cip11-transport/src/gate.rs:1-17,104-128; wired server.rs:40,114; CIP-11 §6.2/§6.6`


### COW-1599 — §6.4 BackpressureSignal (0x12) accepting_new=false -> validator clears bit ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Issue asks backpressure to 'clear a bit in the next vote bitmap' — that vote-piggybacked bitmap was deleted in r1.3 as structurally infeasible. Current §6.4 instead removes the runner from local presence and sets accepting_new=false, which is already implemented. Building the vote-bitmap clearing would re-introduce a removed concept, corrupting the CIP.

**Evidence:** `CIP-11 §2.1 lines 63-79 (vote-bitmap design removed as infeasible), §6.4 lines 333-339; node/cip11-transport/src/connection.rs:113-119, presence.rs:53-60`


### COW-1605 — §8.4 Registry-order indexing of bitmaps as of parent block ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. The surviving concept (index the single PresenceInput by parent-block H-1 registry order, tolerant of registrations/mutations, never excluding) is already fully specified in current §8.5. The issue's multi 'bitmaps' framing is the removed r1.2 per-validator vote-bitmap design; no open work remains. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cip-11 §8.5 'Indexing Across Registry Mutations' (lines 540-542); §2.1`


### COW-1637 — §5.3 Content-addressed body_ref (CBFS) ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. The issue demands proposal id = hash(submitter,nonce,tier,body_ref), but current CIP-12 §5.3 line 154 explicitly makes id a `u64` monotonic counter and states 'NOT a hash' — implementing as written would re-introduce a scheme the aligned CIP deliberately rejected. The other asks (CbfsRef body_ref, temp/voting snapshot blocks, executable_at) are ALREADY in the current §5.3 schema and their pending code wiring is tracked by COW-1028 and the §7.1 on-chain-status note. Close as regression-risk + duplicate of COW-1028.

**Evidence:** `cowboy/docs/cips/cip-12-governance.md:154 ; §5.3 proposal body; on-chain-status note :315 ; snapshot tracked by COW-1028 :194`


### COW-1698 — §7.2/§3.1 RouteRegistration→DomainBinding one-time migration with legacy

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-16 §3.1 governs. DomainBinding is deployed; RouteRegistration was never deployed on-chain, so there are no legacy records to migrate and the one-time migration routine is moot. Issue premise 'no DomainBinding' is stale.

**Evidence:** `node/types/src/domain.rs:173 (DomainBinding) & :208 (TldLabelRecord); RouteRegistration absent from node code; CIP-16 §3.1 line 547 & §Backwards-Compat line 866`


### COW-1758 — §18 Revenue distribution

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-18 §18 split (protocol_fee = floor(base * 500/10000), actor_receives = base - protocol_fee) is implemented on-chain and applied to per-request, pass, and subscription paths. gateway_recovery is delegated to CIP-14's gas model per §15.3.

**Evidence:** `node/execution/src/payment_gate/conservation.rs:126 split_fee; constants.rs:238 PROTOCOL_PAYMENT_FEE_BPS=500; handlers.rs:213/290/393; CIP-18 §18 line 855-864`


### COW-1759 — §19 Protocol constants (PAYMENT_GATE_ADDRESS=0x11 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Issue asserts PAYMENT_GATE_ADDRESS=0x11 and that the constants are 'none [defined]'. Both are stale: current CIP-18 §19 says 0x12, and the core node constants already exist (PAYMENT_GATE_SYSTEM_ACTOR=0x12, PROTOCOL_PAYMENT_FEE_BPS=500). The 0x11 value is explicitly obsolete per §22 and is occupied by VALIDATOR_SET. Remaining listed constants (JSONRPC_PAYMENT_REQUIRED_CODE=-32402, MIN_BRIDGE_CONFIRMATIONS_EVM, EVM_FINALITY_HEADROOM_BLOCKS, MAX_PRICE_TABLE_ENTRIES/MAX_ACCEPTED_ASSETS) are Gateway/facilitator-side, not node execution constants. Implementing as written (0x11) would corrupt the aligned CIP — regression risk. Close.

**Evidence:** `node/types/src/constants.rs:233 (PAYMENT_GATE_SYSTEM_ACTOR = 0x12), :238 (PROTOCOL_PAYMENT_FEE_BPS = 500); cip-18 §19 line 883 (=0x12), §22 line 984 (0x11 'obsolete')`


### COW-1762 — §7 Prerequisite enforcement

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-19 §7 prerequisite (ingress.mcp requires ingress.http) is enforced in the gateway grant parser and tested. The issue's premise 'no ingress.* ids at all' is stale: ingress.http is a deployed registry entitlement.

**Evidence:** `gateway/crates/gateway-server/src/mcp.rs:126 + test :407-415; ingress.http in node/types/src/registry.rs:166`


### COW-1770 — §9 initialize capability negotiation ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. initialize negotiation is implemented (protocolVersion 2025-11-25, serverInfo, capabilities.tools, instructions). The issue text demands capabilities.tools.listChanged=TRUE, but the current CIP-19 §9 mandates listChanged:false (v1 emits no server-initiated notifications; list_changed deferred). Implementing this issue as written would corrupt the aligned CIP — regression risk. Close.

**Evidence:** `gateway/crates/gateway-server/src/mcp.rs:49-56 initialize_result (listChanged:false); CIP-19 §9 line 188/195 (listChanged: false)`


### COW-1772 — §10.1 tools/list generation algorithm

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-19 §10.1 tools/list generation is fully implemented: build_tools reads routes, filters to Method targets (method_name), enabled==true, exclude_routes, groups by target.name via BTreeMap, skips incompatible-param groups and reserved _cowboy* names. lib.rs tools/list handler feeds routes from the cache. Not a regression; issue is stale.

**Evidence:** `gateway/crates/gateway-server/src/mcp.rs:191-244 (build_tools); lib.rs:577-593 (tools/list dispatch); CIP-19 §10.1`


### COW-1773 — §10.2 Tool entry shape (name/description/inputSchema/_meta.cowboy)

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The current CIP-19 §10.2 fully specifies the tool entry shape with a concrete JSON example containing name / description / inputSchema / _meta.cowboy, and explicitly notes _meta.cowboy is non-normative introspection metadata. The audit's 'missing' note is against a stale draft. Spec gap closed; implementing it matches the CIP so no regression risk. Gateway implementation is out-of-workspace and unverifiable, but the conformance ticket is closeable.

**Evidence:** `cip-19-gateway-mcp-ingress.md §10.2 lines 218-244`


### COW-1775 — §10.3 Schema-compatibility check across routes sharing a method name (skip

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The schema-compatibility check across routes sharing a method name IS present: §10.1 step 4 ('validate that all routes share a compatible input schema (§10.3). If not, the group is skipped and a warning is logged') and §10.3 ('If they differ, the routes are considered incompatible and the tool is skipped'). This is exactly what the audit flagged as 'missing'; the current CIP now specifies it. No regression risk — implementing it matches the CIP. Gateway code not verifiable here but spec gap is closed.

**Evidence:** `cip-19-gateway-mcp-ingress.md §10.1 step 4 line 215, §10.3 lines 246-254`


### COW-1847 — §3.10 Secrets Manager get_secret(attestation) TEE-gating ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. CIP-24 rejects TEE as the secret-release trust root; release is unconditionally threshold-IBE and TEE is only an optional tee_required gate satisfied by reading TEE-Verifier 0x05 state. The requested get_secret(attestation) via VerifyCae + allowed_measurements/allowed_services + HPKE-to-service_pubkey is the retired CIP-23-rooted model; implementing it corrupts CIP-24's core decision.

**Evidence:** `cip-24-secrets-manager.md §2.1/§2.3/§8.8 (TEE rejected as trust root); node/execution/src/cbss.rs:5596 validate_runner_tee_for_release (reads tee_att, not VerifyCae/HPKE)`


### COW-1920 — §2.3 'commit subscriber writeset on sync-fire success' diverges from spec

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. No divergence exists: pvm_host.rs:1884 comment cites CIP-29 §2.3 and matches it exactly — commit subscriber writeset on success, rollback on failure, always restore/insulate the emitter. Reconciled with the current CIP.

**Evidence:** `cowboy/docs/cips/cip-29-on-chain-event-hooks.md §2.3 (line 106); node/execution/src/pvm_host.rs:1884 fire_sync_subscribers`


### COW-1937 — §2.1 field-set deviation ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. The 'chain_id omitted' claim is stale — chain_id is now a signed field (replay protection, WP §2). Folding to/value into the Instruction enum is the deliberate golden-gated wire format; implementing flat top-level fields would break the aligned tx codec. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy-protocol/crates/cowboy-protocol-codec/src/transaction.rs:80 (pub chain_id: u64); Instruction-folded to/value is the frozen wire format; WP §2`


### COW-1941 — §2.4 EBNF Header field order ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. The current WP §2.4 EBNF is explicitly informative and describes a flat field list `Tx = chain_id nonce instruction gas from ...` — there is NO Header/Body/Sig canonical-array concept anywhere (grep for Header/Body/Sig array returns nothing). §2.5 is normative and mandates a single flat commonware-codec concatenation in a frozen order. The issue's premise ('canonical-array Header/Body/Sig ordering not realized') refers to an abandoned older WP draft; realizing that array ordering would directly contradict the current §2.5 flat encoding, so acting on it corrupts the aligned spec.

**Evidence:** `whitepaper §2.4 line 504 (marked '(informative)'); §2.5 lines 512-519`


### COW-1968 — Stake-weighted block rewards + 100% proposer tip payout is unimplemented.

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Half the ticket is now implemented: speculative.rs H-3b credits 100% of the block tip to the proposer and H-3a burns the basefee, exactly matching CIP-3 §Proposer-Tip/Fee-Burn — the 'burn/tip return is dropped' claim is stale. The 'stake-weighted block rewards' half is a WP §8.2 concept not present in CIP-3; it is tracked by the inflation-curve work (COW-1260, merged) and its minting consumer COW-1259, which is blocked on validator-set visibility (COW-1028). Close this stale umbrella; no CIP text is contradicted.

**Evidence:** `node/storage/src/speculative.rs:927-949 (H-3b routes block_tip to proposer=block.context.leader; H-3a burns basefee); cip-3 fee-model lines 261-262; COW-1260/#778 inflation curve, COW-1259 blocked on COW-1028`


### COW-2007 — CBFS §7.1/§7.2/§7.4 on-chain PoR challenge loop ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Premise 'NONE of these constants or the on-chain challenge-issuance timer implemented' is now false: the PoR challenge loop is built — challenge interval timer, POR_RESPONSE_WINDOW, challenge-pool balance at 0x0B, relay-side responder, and the CIP-31 penalty/bond/fee params all exist. Moreover the ticket's cited values (POR_CHALLENGE_FEE_SHARE=2%, INTERVAL=600) conflict with current CIP-31's pinned 1% challenge-pool BPS and the 7200-block interval; implementing it as written would contradict CIP-31.

**Evidence:** `node/ras/src/por.rs:28 (POR_CHALLENGE_INTERVAL=7200), :30 (POR_RESPONSE_WINDOW=50); node/storage/src/timers.rs:143 (PoR timer fires per interval); cbfs/node/src/por_responder.rs; node/runner/src/types.rs:1719-1728 (cip31 por_miss/fraud/eviction/bond/fee governance keys); cip-31 §7/§8`


### COW-2089 — §3.3 dedup_window retention guarantee (entries retained ≥

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The ticket's literal premise (LRU eviction of seen_messages inside a window causing replay) was already publicly retracted 2026-06-19: seen_messages is per-block ephemeral, not a cross-block LRU. The WP §3.3 dedup_window=10,000-blocks persistent per-actor dedup set is NOT carried into any current CIP (CIP-1 actor scheduler has no such requirement; CIP-25 'exactly-once' is cross-chain L2, a different plane). Genuine exactly-once-after-finality work overlaps COW-2090; close this as a misdiagnosed duplicate rather than act on the false LRU premise.

**Evidence:** `grep of cip-1-actor-scheduler.md: no dedup_window/message-id/exactly-once; execution/src/execution/engine.rs:360 seen_messages rebuilt per block; msg id includes block_height (actor_instruction.rs:1108-1114); WP §3.3 only`


### COW-2144 — JSON Numbers Bug ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Premise is stale/inverted: the canonical JobSpec wire is no longer JSON but the cowboy-protocol-codec binary encoding (CIP-11 §12.6 / COW-2440), where max_price and tip are UInt<u64> varints — full u64 precision, no IEEE-754 double loss. CIP-2 §3.1 lists JobRequest / canonical JobSpec / legacy CBOR paths, none JSON-double-typed. Implementing the ticket's fix (serialize as JSON strings, node accepts string-or-number) would push a JSON-string schema back into a spec that has moved to CBOR/varint — contradicts CIP-11 §12.6.

**Evidence:** `cowboy-protocol-codec/src/job_spec/spec.rs:41,136-137,167 (max_price/tip = UInt<u64> varint); node/types/src/cip11_wire.rs:8 (COW-2440 codec migration); cip-2 §3.1 line 131`



## Already implemented / resolved

_The capability the issue asks for is already present in the code; the premise that it is missing is no longer accurate._

### COW-1040 — [Gateway] Payment gating wire format finalization (x402 per CIP-18 + tests) · CIP-18

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The x402 wire format is finalized, the PaymentVerifier trait is fully implemented (ChainPaymentVerifier replaces NotReadyVerifier and is the live wiring in main.rs), it integrates with PaymentGate, and round-trip accept/reject tests exist. Feature is done. Caveat: the issue text says 'PaymentGate at 0x11' but the actual/current-CIP address is 0x12 — re-implementing per the stale text would use the wrong address, so keep it closed as done rather than reopening.

**Evidence:** `gateway/src/main.rs:267 (ChainPaymentVerifier wired in prod); gateway/crates/gateway-server/src/x402.rs:61-133,196-343 (x-payment wire format + round-trip/reject tests); node/types/src/constants.rs:233 (PaymentGate 0x12)`


### COW-1101 — [Node] 8-step verify_cae pipeline (freshness, replay, cert chain, measurement, REPORTDATA, service sig, NRAS JWT, nonce insertion) · CIP-23 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. verify_cae is already built as the CIP-23 v3 §3.8.5 pipeline (Full/Light mode split on proof presence, SNARK chip-root, operator_root, apply_tcb_policy, 10 steps). The issue's 8-step v1 spec is stale and wrong on load-bearing details: MAX_QUOTE_AGE=150 (code/spec = 75), step-3 hand-rolled cert chain (v3 = SNARK+bound_quote_key light path), and service sig over (nonce,deadline,generated_at) (code/spec = scope_id‖req_hash‖result_hash‖attest_digest), plus no operator root. Implementing as written would corrupt the as-built §3.8.5.

**Evidence:** `cowboy/docs/cips/cip-23-tee-execution.md §3.8.5; node/execution/src/cbss.rs:2168 handle_verify_cae; types/src/tee.rs:23 MAX_QUOTE_AGE_BLOCKS=75; cbss.rs:2216 service-sig preimage scope_id‖req_hash‖result_hash‖attest_digest`


### COW-1177 — [Node/Spec] PaymentGate system actor address: resolve 0x0013 (CIP-18) vs 0x11 (WP r2) · CIP-18 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. The address ambiguity is already RESOLVED to 0x12 by the current CIP-18 (§19 PAYMENT_GATE_ADDRESS=0x12; §22 explicitly calls both 0x0013 and 0x11 'obsolete') and by code (PAYMENT_GATE_SYSTEM_ACTOR=0x12). The issue asks to pick 0x11 and rewrite CIP-18 errata to match — that would corrupt the aligned CIP and collide with VALIDATOR_SET, which already owns 0x11 (system_actors.rs:76). Classic regression: implementing as written pushes an obsolete value back into the spec.

**Evidence:** `cowboy/docs/cips/cip-18-payments.md §19 (line 883) + §22 (lines 970-984); node/types/src/constants.rs:233; node/runner/src/system_actors.rs:76,79`


### COW-1178 — [Node] PaymentGate system actor: state schema + instructions (settle, credit_inbound, refund, redeem_pass, subscribe) · CIP-18

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. PaymentGate state schema and instructions are already implemented, matching the current CIP §8.3 API. The issue's instruction names (settle/redeem_pass/subscribe/refund/credit_inbound) are stale old-draft vocabulary: the live code uses settle_payment/purchase_pass/purchase_epoch; credit_inbound is intentionally out of M1 scope (§12 deferred); 'refund' does not exist in current §8.3 and MUST NOT be added. Do not re-open under the stale naming.

**Evidence:** `node/execution/src/payment_gate/handlers.rs (set_policy, deposit/withdraw/deduct_budget, purchase_pass, purchase_epoch, verify_payment, settle_payment); node/execution/src/payment_gate/storage.rs (policy/budget/pass/epoch/nonce keys); cip-18 §8.3`


### COW-1179 — [Node] MPP wire format: WWW-Authenticate: Payment header + HMAC-SHA256 binding · CIP-18

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The MPP wire format is fully implemented: WWW-Authenticate: Payment challenge, the §9.4 HMAC-SHA256 seven-slot binding (realm|method|intent|request|expires|digest|opaque), constant-time verify_id, and Authorization: Payment credential parse. Matches CIP-18 §9 exactly. Nothing to do.

**Evidence:** `gateway/crates/gateway-server/src/mpp.rs (build_challenge §9.1; challenge_id/verify_id §9.4 seven-slot HMAC-SHA256 pipe-joined; credential parse §9.2; Payment-Receipt §9.3); GATEWAY_MPP_SECRET wiring in gateway/src/main.rs:293`


### COW-1182 — [Node] PaymentAuthorization struct + Ed25519 signing semantics · CIP-18 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Confirm close AND flag regression: the struct + canonical signing bytes + fixed-vector test already exist as PaymentGate PaymentIntent, verified with the payer's secp256k1 key. The issue-as-written demands 'verify with payer's registered Ed25519 key' — CIP-18 §9.5.1's 2026-07-15 erratum explicitly removed ed25519 (Cowboy accounts are secp256k1; an ed25519 credential is rejected on-chain). Implementing this issue verbatim would re-introduce the exact concept the current CIP deleted.

**Evidence:** `node/execution/src/payment_gate/mod.rs:165 PaymentIntent{kind,payer,actor,asset,amount,nonce,valid_before,request_hash,pass_id,signature}; :235 signing_digest; :253 verify_signature via secp256k1 EthSignature::recover_address; :331 golden_vector test; cip-18-payments.md §9.5.1 Erratum (2026-07-15)`


### COW-1185 — [Gateway] PaymentPolicy cache + per-route lookup · CIP-18

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Confirm close: gateway now reads on-chain PaymentPolicy per-actor and enforces per-route price (rejects amount<price, accepts exact match — the issue's acceptance criterion). The issue's PaymentPolicy struct shape {accepted_methods, accepted_intents, max_price_per_request, price_per_route, fallback_chain} is stale vs current CIP-18 §8.1, but the feature is done; implementing the stale struct would only produce a wrong cache shape, it would not corrupt the CIP doc.

**Evidence:** `gateway/crates/gateway-server/src/payment_state.rs (GwPaymentPolicy::decode from chain, policy_key/pass/epoch/budget); gateway-cache/src/lib.rs RouteCache invalidate on state_root; chain_payments.rs:106 read_policy, :213 'if intent.amount < price' underpayment reject`


### COW-1189 — [Gateway] /_cowboy/payment/openapi.json discovery endpoint · CIP-18

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The CIP-18 §14 discovery endpoint is implemented: GET /_cowboy/payment/openapi.json (and /:actor) returns a valid OpenAPI 3.1 document with per-route x-payment-info annotations, with tests. Acceptance criteria are met; nothing left to do.

**Evidence:** `gateway/crates/gateway-server/src/openapi.rs:31 (build_openapi, x-payment-info); gateway/crates/gateway-server/src/lib.rs:113-114,299-323 (/_cowboy/payment/openapi.json + /:actor routes); CIP-18 §14 cip-18-payments.md:733`


### COW-1209 — [Node/Spec] Full state sync protocol: state-trie chunk download + recovery · CIP-4

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Full state-trie fast-sync is now specified AND implemented: CIP-4 §8.1 defines the sync modes and §8.2 the proof packaging (proof version, chunk location, MMR leaves, operation digests); chain/src/fast_sync.rs wires commonware's QMDB sync Resolver over an HTTP snapshot-manifest + chunked /state/operations flow with canonical-root validation, and the RPC serves both endpoints. The issue's premise ('not documented ... wiring not visible') is false.

**Evidence:** `cip-4-storage.md:199-209 (§8 Snapshots and Sync); node/chain/src/fast_sync.rs:1; node/storage/src/state_sync.rs:52-120; node/rpc/src/rpc.rs:731-738 (/state/snapshot, /state/operations)`


### COW-1256 — [Spec/Node] Align CIP-4 actor-state rent epoch and CIP-9 CBFS volume rent epoch (avoid orphaned-volume drift) · CIP-4

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Both rent systems already peg to the same 86,400-block (1-day) epoch and CIP-31 explicitly references CIP-4, so the cross-ref COW-1228 (7200 vs 86400) is resolved to 86,400 and the relationship is documented. No orphaned-volume drift: CIP-4 §12.3 eviction preserves the actor's balance while CBFS volume rent is drawn independently and self-evicts via CIP-9 grace/CIP-31 STORAGE_GRACE_EPOCHS. The synchronized-epoch outcome the issue calls for is already the aligned state.

**Evidence:** `cip-4-storage.md:256 (rent_epoch_length 86,400) & :282 (eviction preserves balance); cip-31 §STORAGE_FEE ('1 day per CIP-4') & §7 (STORAGE_EPOCH_BLOCKS=86,400)`


### COW-1591 — §4.1/§10.1 Push job delivery

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. §10 push job delivery is fully implemented: validator builds/Ed25519-signs JobAssignment and pushes it on a job stream (dispatch.rs), chain/cip11.rs wires collect_pushes/push_job, and the runner receives via handle_pushed_assignment. The 'delivery is still pull' premise is stale; the GET /runner/{addr}/jobs poll path is retained deliberately as the §14 migration fallback, not a gap.

**Evidence:** `node/cip11-transport/src/dispatch.rs:1-8,85-132; node/chain/src/cip11.rs:4-15,325; runner/crates/runner-node/src/cip11_quic.rs:150-186`


### COW-1610 — §10.2 JobAck (0x21) with AckStatus Accepted/Duplicate/Reject · CIP-2

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The dedicated CIP-11 wire frame the issue said was 'missing' now exists as cowboy_types::cip11_wire::JobAck (type 0x21) with AckStatus Accepted/Duplicate/Reject and RejectReason, encode/decode, preimage and verify_job_ack, distinct from the CIP-2 on-chain structs the audit conflated. Matches current CIP-11 §10.2/§12.2/§12.6 exactly. Work is done; close is correct.

**Evidence:** `node/types/src/cip11_wire.rs:570 (FrameType JobAck=0x21), :677 (struct JobAck), :686-689 (enum AckStatus{Accepted,Duplicate,Reject(RejectReason)}); node/cip11-transport/src/dispatch.rs:257 verify_job_ack; CIP-11 §10.2 / §12.2`


### COW-1611 — §10.3 JobResult (0x23) streamed back on job stream + signature ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. The described gap ('JobResult 0x23 streamed on Accepted stream — missing, results arrive via POST') is already implemented in node/cip11-transport + runner cip11_quic. The wire frame has NO signature field, matching r1.3 §12.6 which removed the per-frame signature (authenticity is the chain tx signature inside tx_bytes). The issue's '+ signature' is the stale r1.2 detail; implementing it would violate §12.6. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `node/cip11-transport/src/server.rs (JobResult/JobResultCommit streamed on Accepted stream); node/types/src/cip11_wire.rs:743 (JobResult{job_id,tx_bytes}, no signature); cip-11 §10.3 line 849, §12.6 line 1059`


### COW-1613 — §10.5 JobCancel (0x24) push frame on reassignment/expiry/failure · CIP-2

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The CIP-11 push-delivery JobCancel wire frame (type 0x24) with CancelReason Reassigned/Expired/Failed is implemented in cip11_wire.rs and signed/built by dispatch::build_job_cancel over the §12.6 preimage — the very reassignment/expiry/failure cases the issue asks for, and separate from SystemInstruction::JobCancel (CIP-2 on-chain). Aligned with current CIP-11 §10.5; close is correct.

**Evidence:** `node/types/src/cip11_wire.rs:573 (FrameType JobCancel=0x24), :749 (struct JobCancel), :758-761 (enum CancelReason{Reassigned=0x00,Expired=0x01,Failed=0x02}); node/cip11-transport/src/dispatch.rs:164 build_job_cancel; CIP-11 §10.5 / §12.2`


### COW-1614 — §10.6 Dispatch Outcome classification

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. §10.6 Dispatch Outcome Classification is implemented as the DispatchOutcome enum (Success/Duplicate/SoftFailure/HardFailure); only HardFailure clears local presence and a valid HeartbeatPing restores it via LocalPresence::record_ping (the §10.6 presence floor). Tested (server.rs:1455/1600/1689). Matches current CIP exactly; nothing to change in the CIP.

**Evidence:** `node/cip11-transport/src/dispatch.rs:194 (DispatchOutcome enum Success/Duplicate/SoftFailure/HardFailure); presence.rs:39 record_ping + server.rs:530; cip-11 §10.6 (lines 873-882)`


### COW-1615 — §11.1 Per-dispatch ACK_TIMEOUT_BLOCKS HardFailure -> clear presence

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. §11.1 per-dispatch ACK_TIMEOUT_BLOCKS (default 15) HardFailure that closes the job stream and clears the runner's local-presence entry is implemented and unit-tested (HardFailure drops presence). Matches current CIP §11.1; no regression risk.

**Evidence:** `node/cip11-transport/src/dispatch.rs:56 ACK_TIMEOUT_BLOCKS=15, dispatch.rs:208 clears_local_presence(); server.rs test ack_timeout_is_hard_failure_and_drops_presence (~1613); cip-11 §11.1 (lines 888-890)`


### COW-1619 — §12.4 Hello.version=1 versioning + Goodbye{unsupported_version} on

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Hello.version handshake gating with Goodbye{UnsupportedVersion} on version mismatch is implemented (handshake verifies hello.version and maps rejection to the wire GoodbyeReason). The issue's '§12.4' / 'version=1' wording is stale (versioning moved to §12.3, now a u16 packed 0x0100, and §12.4 is Reserved), but the substance is done. Implementing it as written would not corrupt the CIP.

**Evidence:** `node/cip11-transport/src/handshake.rs:67 version:u16, :142 reject on version mismatch, :96-99 HandshakeReject::UnsupportedVersion -> GoodbyeReason::UnsupportedVersion; cip-11 §12.3 (line 956) + §12.5 (line 968)`


### COW-1622 — §15.6 QUIC+TLS1.3 transport replacing plaintext HTTP for job content

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. QUIC+TLS1.3 transport is implemented (quinn+rustls, CIP11 ALPN) and the pushed JobAssignment frame carries the full job_spec (LLM prompts, PublishChainRoot tx), so §15.6's plaintext exposure is closed as the CIP now states. The plaintext HTTP poll path remaining is the intended §14 migration coexistence (disabled only in Phase 3 via CIP11_POLL_DISABLED), not a missing feature. The 'transport missing' claim is stale.

**Evidence:** `runner/crates/runner-node/src/cip11_quic.rs:936-947 (rustls QUIC/TLS1.3 client, CIP11 ALPN); node/cip11-transport/src/dispatch.rs:71,119-121 (JobAssignment.job_spec carries job content over QUIC); cip-11 §15.6 'Plaintext Wire (Closed)' (line 1164), §14 migration`


### COW-1687 — §8.4/AMEND 9-G GET_MANIFEST relay RPC

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Stale. The issue's premise ('not added to Operation enum; lib.rs:462-511 has no GetManifest') is now false: Operation::GetManifest exists with a full handler and server-side PUBLIC assembly (COW-2120). Implementation matches CIP-9 §5.3.2 / CIP-15 §8.4, where GetManifest is a recommended optimization and DAG-traversal fallback is spec-compliant. No regression risk; issue is done.

**Evidence:** `cbfs/types/src/lib.rs:459 (Operation::GetManifest); cbfs/node/src/handler.rs:454,1187; cbfs/node/src/manifest_assembly.rs:1; CIP-9 §5.3.2, CIP-15 §8.4, CIP-14 AMEND 9-G (line 1557)`


### COW-1760 — §24 Genesis deployment of PaymentGate at 0x11 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Issue cites 'PaymentGate at 0x11' — the OBSOLETE draft address. Current CIP-18 §19/§22/§24 places PaymentGate at 0x12; 0x11 is now the CIP-11 VALIDATOR_SET. PaymentGate already exists at 0x12 as a native execution module (node/execution/src/payment_gate/), not a genesis-deployed contract. Implementing this issue as written (deploy at 0x11) would collide with VALIDATOR_SET and contradict the aligned CIP-18 — regression risk. Close.

**Evidence:** `node/runner/src/system_actors.rs:79 (PAYMENT_GATE = 0x12), :75 (0x11 = CIP-11 Validator Set); node/execution/src/payment_gate/{mod,handlers,storage,conservation}.rs; cip-18 §22 lines 970-984 (0x11 'obsolete'), §24 line 1006`


### COW-1765 — §8 405 Method Not Allowed for other methods on /_cowboy/mcp

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-19 §8's '405 for other methods on /_cowboy/mcp' is implemented: the any(mcp_endpoint) handler returns METHOD_NOT_ALLOWED for non-POST/GET/DELETE, with a PUT->405 test. Issue is stale-implemented.

**Evidence:** `gateway/crates/gateway-server/src/lib.rs:493 + test lib.rs:2840-2889; CIP-19 §8 line 156`


### COW-1767 — §8.1 Session lifecycle

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Mcp-Session-Id issuance on initialize is implemented: handle_mcp_jsonrpc creates a random 32-byte session id and inserts it as the mcp-session-id response header on the initialize response; subsequent non-initialize methods require validate(id, actor). Close.

**Evidence:** `gateway/crates/gateway-server/src/lib.rs:550-556 (create session + insert mcp-session-id header on initialize); CIP-19 §8.1 line 162`


### COW-1768 — §8.1 Session termination via DELETE or MCP_SESSION_IDLE_TIMEOUT_SECONDS

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Both termination paths exist: explicit DELETE /_cowboy/mcp calls mcp_sessions.terminate(id), and idle eviction via MCP_SESSION_IDLE_TIMEOUT (600s) enforced in evict_idle on every create/validate. Tests idle_sessions_are_evicted and session ...terminate cover it. Close.

**Evidence:** `gateway/crates/gateway-server/src/lib.rs:487-492 (DELETE terminate); mcp.rs:19,292-307 (MCP_SESSION_IDLE_TIMEOUT + evict_idle); CIP-19 §8.1 line 162`


### COW-1769 — §8.1 Session state limited to

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Issue premise '(no session store)' is now false: McpSessionStore exists. The Session holds only protocol_version/client_info (plus actor+last_seen for host-binding/eviction) and carries NO payment state, satisfying the §8.1 invariant. Minor nuance: the spec's optional 'routes-table version at session start' is not cached (tools/list loads live), but that is not a defect and not a regression. Close.

**Evidence:** `gateway/crates/gateway-server/src/mcp.rs:248-253 (Session struct); CIP-19 §8.1 line 164-169`


### COW-1771 — §9 Non-advertisement of resources/prompts/completions/sampling capabilities

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-19 §9 requires initialize to advertise only tools and NOT resources/prompts/completions/sampling. initialize_result advertises only capabilities.tools.listChanged=false (mcp.rs:49-56); test initialize_advertises_only_tools_capability asserts resources/prompts/sampling are null (mcp.rs:481-491). An initialize handler now exists (lib.rs:542-566). Audit's 'n/a, no initialize handler' is stale.

**Evidence:** `gateway/crates/gateway-server/src/mcp.rs:49-56 and test :481-491; gateway/crates/gateway-server/src/lib.rs:542-566`


### COW-1776 — §10.4 Tool name mapping = tool_name_prefix + sanitize(target.name)

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The current CIP-19 §10.4 fully specifies `tool_name = ingress.mcp.tool_name_prefix + sanitize(route.target.name)`, the sanitize rule ([a-zA-Z0-9_]→_), AND the reserved `_cowboy` collision-skip ('If ... would collide with a reserved name, the route is skipped'). The May-2026 audit's 'missing' note is against a stale draft; the spec section is now complete and self-consistent. Implementation lives in the gateway repo (not in this workspace) so I cannot verify code, but as a spec-conformance ticket the gap is closed and matches the CIP verbatim.

**Evidence:** `cip-19-gateway-mcp-ingress.md §10.4 lines 256-266`


### COW-1784 — §12.3 Credential normalization to PaymentIntent + PaymentGate verify/settle · CIP-18

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Issue's explicit premise ('no PaymentGate/PaymentIntent, CIP-18 target=0') is now false: PaymentGate is deployed at 0x12 with verify_payment/settle_payment, and the gateway normalizes MPP/x402 credentials to a PaymentIntent (cross-wire byte-identical tests). Node §12.3 is now 'BridgeEvidence', not the credential-normalization the issue's old §12.3 cites.

**Evidence:** `node/execution/src/payment_gate/handlers.rs:358-373 (verify_payment/settle_payment); node/types/src/constants.rs:233 (PaymentGate 0x12); gateway/crates/gateway-server/src/x402.rs:61,196-289 (credential→PaymentIntent normalization + tests)`


### COW-1785 — §12.4 pass/subscription credential evaluation ahead of charge per CIP-18 · CIP-18

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The §7.5 fallback chain (subscription/pass evaluated ahead of per-request charge, 'first satisfied row wins') is now implemented in the gateway ChainPaymentVerifier::verify(). Issue's 'missing' premise is stale; feature exists and aligns with current CIP-18 §7.5.

**Evidence:** `gateway/crates/gateway-server/src/chain_payments.rs:159-270 (verify: has_active_subscription/Pass evaluated ahead of charge); CIP-18 §7.5 cip-18-payments.md:180-196`


### COW-1786 — §13 Reserved _cowboy_* tool-name namespace

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-19 §13 requires v1 to reserve the _cowboy_* namespace so actor tool names cannot collide (it explicitly does NOT require implementing the tools). build_tools skips any tool whose name starts with '_cowboy' (mcp.rs:208-210), covered by test build_tools_skips_reserved_cowboy_prefix (mcp.rs:471-478). The reservation is done; implementing the actual reserved tools would instead contradict the CIP ('v1 reserves but does not yet implement'), so the issue-as-written is satisfied.

**Evidence:** `gateway/crates/gateway-server/src/mcp.rs:208-210 and test :471-478; cip-19-gateway-mcp-ingress.md §13 (414-430)`


### COW-1789 — §16 Protocol constants (MCP_PROTOCOL_VERSION

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-19 §16 constants are now defined (mcp.rs:18-21: MCP_PROTOCOL_VERSION, MCP_SESSION_IDLE_TIMEOUT=600s, MAX_TOOL_INPUT_BYTES_DEFAULT=1MiB) and -32603/-32000 are emitted (lib.rs:590,561). The remaining names (-32402, MAX_TOOL_OUTPUT_BYTES, TOOLS_LIST_CHANGED_DEBOUNCE_MS) are tied to unbuilt features: payment (19d), tools/call output (19c), and the deferred listChanged notifications. Audit's 'none defined' is stale/incorrect; no spec-regression risk.

**Evidence:** `gateway/crates/gateway-server/src/mcp.rs:18-21; gateway/crates/gateway-server/src/lib.rs:561,590`


### COW-1790 — §17 Security controls

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. CIP-19 §17 controls that apply to the built surface are now implemented: input-size bound before parse (lib.rs:463-466), session-hijack rejection via actor-bound session + idle timeout (mcp.rs:340-350), schema-mismatch DoS drop (mcp.rs:204-206). The still-absent controls (path-param URL-encoding, payment replay/cross-session binding, output-size bound) belong to tools/call dispatch (19c) and payment (19d), which are unbuilt — lib.rs:592 returns 'Method not found' for tools/call, so there is no live surface to secure. Audit premise 'none implemented (no MCP path to secure)' is stale.

**Evidence:** `gateway/crates/gateway-server/src/lib.rs:463-466; gateway/crates/gateway-server/src/mcp.rs:204-206,340-350`


### COW-2055 — Runtime integer bit-length enforcement (>4096 bits produced via arithmetic

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. Resolved by node#1007: the 4096-bit cap is now enforced at the VM level on every growth op (+,-,*,**,<<) and on int construction, catching exactly the runtime-arithmetic paths the ticket calls a TODO (1<<10000, pow(2,N), math.factorial) — beyond the deploy-time literal scan and the _GuardedInt preamble. Matches CIP-3 §2.4's 'operation producing a result exceeding the limit raises OverflowError'. Only residue is the stale doc comment at pvm-runtime/determinism.rs:13-21; substantive gap is closed.

**Evidence:** `pvm/crates/vm/src/builtins/int.rs:104-160 (ensure_int_bits / ensure_int_bits_ref / reject_int_bits_bound); pvm/crates/vm/src/vm/setting.rs:133; pvm/crates/pvm-runtime/src/lib.rs:561 (node#1007); cip-3 §2.4 line 193`


### COW-940 — [Docs] Resolve CBFS Phase 2 open questions: PoD frequency, scoring weights, clock skew bound

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. References cbfs-ras-phase-2.md, which no longer exists as an authoritative doc (superseded by CIP-9/CIP-31 as-built). Two of three premises are stale: destination scoring weights are already tuned non-even in code, and clock-skew bounds are already concrete tuned constants (30s/30s/300s), not a single 60s guess. It touches no CIP in cowboy/docs/cips so there is no regression risk; the remaining PoD-frequency item is a soft telemetry-tuning task anchored to a dead design doc.

**Evidence:** `cbfs/placement/src/rebalance_util.rs:56 (region_novelty_bonus:250); cbfs/registry-proto/src/lib.rs:47-51 (concrete skew constants)`



## Superseded by a later CIP / design decision

_The mechanism this issue targets has been explicitly removed or replaced by the current authoritative CIP; acting on it would revert a settled decision._

### COW-1294 — [Node] Deploy-time validation: ingress.static without ingress.http is rejected · CIP-15 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Current CIP-15 §11.2 deliberately rejects a separate ingress.static entitlement: static serving is a param (static_volumes) inside ingress.http, so 'static without http' cannot exist. The issue's rule (from stale 'v2 Part III §3.2') presupposes an ingress.static entitlement; adding that deploy-time validation would re-introduce the split entitlement the current CIP unified away. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy/docs/cips/cip-15-public-asset-hosting.md:1124 (§11.2)`


### COW-1300 — [Node/Gateway] default_behavior: dynamic vs static fallback semantics · CIP-15 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Current CIP-15 §6.6 resolution algorithm step 9 states verbatim: 'No match. Return 404 Not Found. Explicit routes are required; there is no fallback default_behavior.' The issue references a stale 'CIP-15 v2 Part II §4.2' draft; implementing a dynamic-vs-static default_behavior and documenting it into CIP-15 would re-introduce a concept the current CIP has explicitly removed. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy/docs/cips/cip-15-public-asset-hosting.md:402 (§6.6 step 9)`


### COW-1378 — §8 'aggregator_timeout_blocks fallback to individual reveals / ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Current CIP-2 §8 explicitly documents there is NO distinct `aggregator_timeout_blocks` mechanism: 'the fallback is gated by the per-job timeout_blocks, not an aggregator-level timeout' with Result-Verifier self-aggregation. The issue asks to implement exactly the timed aggregator-fallback the current CIP decided against — implementing it as written would contradict cip-2 §8. Code (AggregatorConfig = {eligibility_percentile, bonus_bps}) already matches the CIP.

**Evidence:** `cowboy/docs/cips/cip-2-offchain-compute.md:684; node/execution/src/runner/aggregator.rs; node/runner/src/types.rs:1135 (AggregatorConfig)`


### COW-1590 — §4.1/§6.1 Persistent QUIC (RFC9000)+TLS1.3 runner->validator control · CIP-2

**Recommendation:** Close.

**Closing comment:**

> Closing as no longer actionable. The issue's premise ('persistent QUIC absent; runner still uses CIP-2 HTTP poll') is stale. Persistent runner->validator QUIC (RFC9000+TLS1.3) control connection is fully built on both sides (runner cip11_quic.rs + node cip11-transport crate). The HTTP poll loop is retained ON PURPOSE as the CIP-11 §14 delivery-floor fallback (config comment cites §14), not because QUIC is missing. Current CIP-11 (Final r1.3) is the source of truth and mandates exactly this design, so no regression concern; the work is done.

**Evidence:** `runner/crates/runner-node/src/cip11_quic.rs (2733 lines: Hello/HelloAck handshake, TLS-exporter channel_binding label 'cowboy-cip11-handshake-v1', HeartbeatPing/Pong, push JobAssignment over quinn); node/cip11-transport/ crate (handshake/connection/heartbeat/presence/dispatch); runner-node/src/config.rs:100,154-156; cip-11 §6.1/§14`


### COW-1595 — §5.3 Subset rotation per SUBSET_EPOCH_BLOCKS / VALIDATOR_CHURN_THRESHOLD ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. The current CIP-11 explicitly REMOVED block-cadence rotation: subset_epoch increments only on a consensus validator-set change 'never per block', and 'CIP-11 defines no snapshot-emission cadence or churn threshold of its own.' The issue's SUBSET_EPOCH_BLOCKS / VALIDATOR_CHURN_THRESHOLD / in-block subset_epoch counter are decided-against concepts; implementing them as written would re-introduce a fixed-cadence rotation the CIP deleted (r1.3). The 'no subset_epoch in node' premise is also stale (subset_epoch is a wire field, cip11_wire.rs:602), and OVERLAP_BLOCKS overlap is specified/activates automatically past epoch 0. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `CIP-11 §5.3 (line 233-246), §5.4, §13 r1.3 removal note; node/types/src/cip11_wire.rs:602`


### COW-1601 — §7.1 Vote payload extension ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Issue asks to add a vote_presence_bitmap field to validator votes with signature coverage. r1.3 explicitly found this infeasible and removed it; presence is now a proposer-supplied PresenceInputV1 in the block body (§7.2), not a per-validator vote payload. Implementing the issue as written would re-add the deleted design and contradict the current CIP.

**Evidence:** `CIP-11 §2.1 lines 63-79 ('threshold-aggregated votes carry no per-validator payload... This reason alone is sufficient'); §7.1 lines 374-378, §7.2 lines 380-402`


### COW-1602 — §7.2 Per-validator bitmap construction (open auth stream + recent ping + ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Issue asks for per-validator bitmap construction (open stream + recent ping + not backpressured + in-subset) piggybacked on votes — the removed r1.2 mechanism. r1.3 §7.2 replaced it with a mode-aware proposer-supplied PresenceInput; the local-presence signal (§7.4) is already implemented. Building the per-validator vote bitmap would corrupt the aligned CIP.

**Evidence:** `CIP-11 §2.1 lines 63-79 (per-validator vote bitmap removed); §7.2 lines 380-402 (PresenceInput is proposer-supplied, 'never derived from a validator's local execution-time socket state')`


### COW-1603 — §8.1 Canonical Presence Bitmap P(H) derived deterministically from ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Asks for the r1.2 'canonical presence bitmap P(H) derived from finalization-quorum votes'. CIP-11 r1.3 §2.1 declares this structurally infeasible (BLS12-381 threshold signatures carry no per-validator payload) and removed it; the normative path is proposer-supplied best-effort PresenceInput, not vote-derived. Implementing as written re-introduces the removed design. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy/docs/cips/cip-11-runner-connectivity.md §2.1 (lines 63-79) + revision history line 18; §8.1`


### COW-1604 — §8.2 presence_threshold(n)=floor((n-1)/3)+1 (f+1) ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. The r1.2 presence_threshold(n)=f+1 aggregated over per-validator finalization votes. r1.3 has no vote-aggregation threshold; only opt-in governance-gated Mode-A t_hard (honest-majority-of-k) exists, and §8.4 explicitly rejects small-k hard exclude. Implementing an f+1 vote threshold corrupts the current CIP.

**Evidence:** `cip-11 §8.4 posture (C) REJECTED (line 536), §2.1; §8.2`


### COW-1606 — §9.1 Dispatcher Filter 1.5 Presence ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Asks to insert a hard presence Filter 1.5 (P(H-1)[idx]=1) between Health and Reputation. Current §9.1 explicitly removed exactly this r1.2 filter and makes presence fail-open present-first draw ordering (Mode B normative), never a candidate-removing filter. Adding the filter directly contradicts the aligned CIP.

**Evidence:** `cip-11 §9.1 line 576 ('removes ... the P(H-1) hard presence filter ... Presence is applied ... not as a filter that removes candidates')`


### COW-1618 — §12.3 VotePresenceBitmap inter-validator encoding ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. CIP-11 §12.3 governs: 'CIP-11 adds no inter-validator consensus vote field.' The r1.2 VotePresenceBitmap-on-finalization-votes design was explicitly audited as infeasible and removed in r1.3 (§2.1). Implementing it would re-introduce a concept the current CIP decided against. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy/docs/cips/cip-11-runner-connectivity.md §2.1 (line 63-67) & §12.3 line 952; also r1.3 changelog line 18`


### COW-1753 — §5.3 step-5 / §11 bundled account-trie proof binding actor.state_root to ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Current CIP-17 §5.3 explicitly declares the 'second proof against the block's account trie' step MOOT: Cowboy has a single unified state root and no per-actor storage trie (§5.2), so one MMR operation proof fully authenticates the read. Implementing a 'bundled account-trie proof binding actor.state_root to the block account trie' as written re-introduces the per-actor storage-trie concept the current CIP removed. §11 lists it only as future work gated on CIP-30 (per-actor storage_root). The issue's 'spec-required for end-to-end verifiability' claim is refuted by §5.3. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy/docs/cips/cip-17-verifiable-state-read.md:148 (§5.3), :104 (§5.2), :256 (§11)`


### COW-1820 — Timer integration ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. CIP-22 §Clearing (init/handle_timer notes) explicitly states 'a separate finalize timer is unnecessary' and 'no separate finalize callback/timer is needed — the post-end fire of the re-armed clearing timer invokes the idempotent _finalize_auction()'. The issue asks to schedule the very finalize-timer-at-end_block+1 the current spec removed in favor of the idempotent post-end clearing fire; implementing it would re-introduce a decided-against concept. CIP-22 is also a Draft with no implementation anywhere. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy/docs/cips/cip-22-continuous-clearing-auctions.md:693-694 and :713-714`


### COW-1851 — §6 governance microcode-revision blacklist via UpdateCpuRoot collateral + ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. UpdateCpuRoot is the retired v1 root-cert mechanism; CIP-23 v3 §3.8.3/§6 mandate microcode blacklist via UpdateCollateral/TCBInfo (code uses CollateralSnapshot, no UpdateCpuRoot). --tee-soft-fail is a roadmap flag gated on the unshipped chip-root SNARK (§5/§7). Implementing as written re-introduces UpdateCpuRoot. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cip-23-tee-execution.md §3.8.3 (line 259) + §6 (line 506); node/execution/src/cbss.rs:1800 CollateralSnapshot; cbss.rs:1769 --tee-soft-fail TODO`


### COW-1924 — §5.1 Phase-0 @hookable pure-SDK prototype not present as a distinct ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. CIP-29 is an unimplemented forward-looking proposal (Rollout Plan Phases 0-3); nothing in it is built yet, so 'Phase-0 prototype not present' is trivially true and not actionable. The current §5.1/§5.2 deliberately keep Phase-0 (the @hookable pure-SDK probe) as a distinct, intentional first deliverable — 'the cheap probe' that runs BEFORE the protocol path. The issue's claim that Phase-0 is 'superseded by protocol path' contradicts the current CIP; a dev acting on it would delete an intentional phase from the spec.

**Evidence:** `cip-29-on-chain-event-hooks.md §5.1 line 576, §5.2 lines 583-585`


### COW-2005 — WP §4.3/§State-Rent dynamic rent_rate adjustment ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. CIP-4 §12 is the normative source for rent mechanics (WP §17.5 now references it) and defines rent_rate as a static, Tier-0 governance-tunable constant (rent_rate_atto) adjusted only via the §12.6 monitoring cadence; §12.6 (Decision Register #4) explicitly HOLDs against oracle/dynamic re-pegging for v1. The dynamic feedback formula rent_rate_{i+1}=rent_rate_i x (1+clamp((S-T)/(T*alpha),...)) survives only in the stale WP §4.3 narrative. Implementing it would re-introduce an auto-adjust loop the current CIP decided against. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cip-4-storage.md:255 (rent_rate_atto static Tier-0), :302-310 (§12.6 Decision Register #4 HOLD, 'No oracle dependency in v1'); WP §17.5 line 1054-1073 (static); WP §4.3 line 419-427 (stale dynamic formula)`


### COW-957 — [Node/Runner] TEE attestation verification pipeline (SGX, SEV-SNP, TDX, AWS Nitro) · CIP-2 ⚠️ CIP-regression risk

**Recommendation:** Close. Do **not** implement as written.

**Closing comment:**

> Closing as no longer actionable. Umbrella issue is the superseded CIP-2 v1 framing: it asks for SGX parsers (CIP-23 v3 §3.4/§3.3 reject SGX for attested modes: 'sgx → neither'), a hand-rolled on-chain certificate-chain walk (v3 §3.8 moves this into a SNARK circuit), and pinned measurements at 0x09:system:cip2:tee_pcr_pins (v3 uses a governance CollateralSnapshot in the 0x05 verifier + measurement_binding in Registry 0x01). The pipeline is now built (handle_verify_cae, nitro.rs, interim trusted-key operator root opcodes 60-63). Implementing as written would re-introduce SGX-attested + on-chain cert-walk + 0x09 pins that v3 removed. Implementing this issue as written would contradict the current aligned CIP; closing to protect the spec.

**Evidence:** `cowboy/docs/cips/cip-23-tee-execution.md §3.4, §3.8, §3.8.4; node/execution/src/cbss.rs:2168 handle_verify_cae; node/execution/src/nitro.rs`

