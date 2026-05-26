# Cowboy Platform Code Completion Audit Report (2026-05-26)

**Audit Date**: 2026-05-26
**Prior Baseline**: [`2026-05-15_CIP_IMPLEMENTATION_AUDIT_CN.md`](./2026-05-15_CIP_IMPLEMENTATION_AUDIT_CN.md) (11-day-prior parallel 9-agent audit)
**Audit Scope**:
- **Whitepaper**: `refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md` (v2.r2)
- **CIP documents**: 30 files in `refs/cips/` (cip-1 to cip-31, includes cip-15-gateway-implementation; cip-27/30 not drafted)
- **Code**: `main` branches of four repos — [`cowboyinc/node`](https://github.com/cowboyinc/node), [`cowboyinc/runner`](https://github.com/cowboyinc/runner), [`cowboyinc/cbss`](https://github.com/cowboyinc/cbss), [`cowboyinc/cbfs`](https://github.com/cowboyinc/cbfs)

**Audit Method**: Built on the 5/15 audit baseline, layered with findings from the 2026-05-26 spec ↔ code alignment sweep (see `wiki/log.md` 5/26 enhance/lint entries) + 6 parallel sub-agents grep'ing 30 CIPs × 4 repos. Status-changed CIPs include precise evidence; unchanged CIPs reuse 5/15 conclusions tagged "5/15 audit baseline".

**Legend**: ✅ ≥85% / 🟢 60-85% / 🟡 25-60% / 🟠 5-25% / ❌ <5% / ⚠️ deviation present

---

## Table of Contents

- [0. Whitepaper Architectural Baseline (WP v2.r2)](#0-whitepaper-architectural-baseline-wp-v2r2)
- [1. Key Changes Since 5/15 Audit](#1-key-changes-since-515-audit)
- [2. Overview Matrix (2026-05-26 State)](#2-overview-matrix-2026-05-26-state)
- [3. Per-CIP Detailed Analysis](#3-per-cip-detailed-analysis)
  - [3.1 Actor & Compute Layer (CIP-1/2/6)](#31-actor--compute-layer-cip-126)
  - [3.2 Storage & Filesystem (CIP-4/9/31)](#32-storage--filesystem-cip-4931)
  - [3.3 Runner System (CIP-10/11/13)](#33-runner-system-cip-101113)
  - [3.4 Networking & Sessions (CIP-7/8/15/19)](#34-networking--sessions-cip-781519)
  - [3.5 Addressing & Governance (CIP-5/12/14/16/17)](#35-addressing--governance-cip-51214161-7)
  - [3.6 Finance & Tokens (CIP-3/18/20/21/22/26/28)](#36-finance--tokens-cip-31820212226-28)
  - [3.7 Advanced Features (CIP-23/24/25/29)](#37-advanced-features-cip-232425-29)
- [4. Cross-Cutting Findings](#4-cross-cutting-findings)
- [5. Node Repository Code Asset Inventory](#5-node-repository-code-asset-inventory)
- [6. Risks & Priority Recommendations](#6-risks--priority-recommendations)
- [7. Whitepaper Genesis Parameters vs Code — Item-by-Item](#7-whitepaper-genesis-parameters-vs-code--item-by-item)
- [8. Whitepaper Part II Nine Deltas — Implementation Status](#8-whitepaper-part-ii-nine-deltas--implementation-status)
- [9. Items Unchanged Since 5/15 Audit](#9-items-unchanged-since-515-audit)
- [10. Conclusion](#10-conclusion)

---

## 0. Whitepaper Architectural Baseline (WP v2.r2)

The whitepaper `2026-03-21_cowboy-technical-whitepaper-revised-v2.md` is the top-level spec document, divided into three parts:

| Part | Content | Status |
|---|---|---|
| **Part I** | Original v1 text (17 chapters + Appendix A), including §9 system actor table, §13 genesis parameter table, §17 complete fee model | Current spec (canonical) |
| **Part II** | 9 Deltas (forward-looking proposals emerging from CIP-14/15/16 alignment exercises) | Proposals; partially adopted |
| **Part III** | WP vs CIP consistency audit brief | One-shot audit, non-normative |

**Conflict Rules**: Part I is currently authoritative; Part II overrides corresponding Part I sections once adopted; Delta 6 (§9 system actor table fix) has been folded into v2.r2.

### 0.1 Core Architecture Described by WP

The WP **Abstract** + **Architectural Overview** define four platform pillars:

1. **Deterministic Python Actors** — deterministic PVM (Python 3.11.8), reentrancy ≤32, 10 MiB memory, module whitelist
2. **Native Timers & Scheduler** — tiered calendar queue + GBA + same-block penalty + per-actor cap of 1,024
3. **Verifiable Off-Chain Compute** — Runner market, VRF selection, commit-reveal, 6 verification modes
4. **Dual-Metered Gas** — Cycles + Cells as independent EIP-1559 markets

### 0.2 WP §9 System Actor Table vs Code (including 5/26 new 0x1D)

| Address | WP §9 (v2.r2 revised) | Code | Status |
|---|---|---|---|
| 0x01 | Runner Registry | `RUNNER_REGISTRY` | ✅ aligned |
| 0x02 | Job Dispatcher | `JOB_DISPATCHER` | ✅ aligned |
| 0x03 | Result Verifier | `RESULT_VERIFIER` | ✅ aligned |
| 0x04 | Secrets Manager (CBSS) | `SECRETS_MANAGER` | ✅ aligned (CIP-24 shipped) |
| 0x05 | TEE Verifier | `TEE_VERIFIER` | ✅ aligned |
| 0x06 | DualBasefee | `BASEFEE_SYSTEM_ACTOR` | ✅ aligned |
| 0x07 | Entitlement Registry | `ENTITLEMENT_REGISTRY` | ✅ aligned |
| 0x08 | Treasury | `TREASURY` | ✅ aligned |
| 0x09 | Governance | `GOVERNANCE_SYSTEM_ACTOR` | ✅ aligned |
| **0x0A** | **Storage Manager (CIP-9)** | **`STORAGE_MANAGER`** | ✅ aligned (Delta 6 fix) |
| 0x0B | Relay Registry (CIP-9) | `RELAY_REGISTRY` | ✅ aligned |
| 0x0C | Session Actor (CIP-8) | `SESSION_ACTOR` | ✅ aligned |
| 0x0D | Route Registry (CIP-14 v2) | unassigned | ❌ unimplemented |
| 0x0E | Gateway Registry (CIP-14 v2) | unassigned | ❌ unimplemented |
| 0x0F | Receipt Registry (CIP-14 v2) | unassigned | ❌ unimplemented |
| 0x10 | Container Registry (CIP-10 v2) | unassigned | ❌ unimplemented |
| 0x11 | Payment Gate (CIP-18 r2) | unassigned | ❌ unimplemented |
| 0x12 | Stream Key Manager (CIP-7 r2) | unassigned | ❌ unimplemented |
| 0x13 | Bank Actor (CIP-28) | unassigned | ❌ unimplemented |
| **0x1D** | **Event Subscription (CIP-29, host-intercepted virtual)** | **`EVENT_SUBSCRIPTION_SYSTEM_ACTOR`** | ✅ **5/26 new** (`constants.rs:156`) |

**5/26 key changes**:
- `0x1D` is a protocol-level **new activation pattern** — virtual system actor, not in the `0x01-0x0F` reserved range, routed via interception at `pvm_host::call_actor:1867-1881`.
- CIP-28 BankActor moved `0x0D → 0x13` (yielding `0x0D` to CIP-14 v2 Route Registry, drift.md C-1 closed 5/26).
- CIP-29 EVENT_SUB moved from declared `0x0A` (collided with CIP-9) to `0x1D` (drift.md C-2 closed 5/26).

### 0.3 WP §5.1a vs §5.1b — Deployed vs Target Design

WP §5.1 explicitly distinguishes two tiers:

- **§5.1a (deployed)**: CIP-5 FIFO + same-height FIFO buckets + per-fire `fee_payer` + `LANE_TIMER_CYCLES=2,000,000` (20% of block per CIP-3 §2.2.3) + `TIMER_GC_CYCLES` independent GC lane + per-actor cap 1,024 + same-block ban
- **§5.1b (target)**: CIP-1 v3 EIP-1559 timer-lane basefee + `priority_tip` + per-actor fairness weight `W(actor) ∈ [1,2]` + 250k auction-phase cycle cap + `priority_tier_hint` SDK enum

**Audit Observation**: Code is at §5.1a; §5.1b **target is fully empty** (see §3.1). But §5.1a has one deviation: WP says `LANE_TIMER_CYCLES = 2,000,000` (20% × 10M target), **code value is `8,888,890`** — see §7 for detailed reconciliation.

### 0.4 Realities WP Explicitly Locks Down

The WP text itself (and the v2.r2 metadata) repeatedly admits current state:

- "**CIP-9 manifest anchoring (deferred)**" — §12.2 / §17.6
- "**CIP-10 image allowlists**" — §12.2 (depends on unimplemented Container Registry)
- "**ZK-Proof (v2)**" — §5 table + §5.3, explicitly future v2
- "**delegation deferred to v2**" — §6 validator set
- "**no encrypted mempool**" — §6.4 / §6.5
- "**EventListener (CIP-7, deferred)**" — §16.3

---

## 1. Key Changes Since 5/15 Audit

Within 11 days, 6 CIPs show meaningful status changes, driven primarily by CBSS large-scale landing and CIP-29 framework implementation:

| CIP | 5/15 State | 5/26 State | Triggering Evidence |
|---|---|---|---|
| **CIP-24 (CBSS)** | (not listed in 5/15 audit) | 🟢 **~80%** | Massive code landing: 11,600 lines in `node/` (`execution/src/cbss.rs:7738` + `types/src/cbss.rs:1906` + `rpc/src/handlers/cbss.rs:1956`) + standalone `cbss/` workspace 29,448 lines (cbssd / cbss-crypto / cbss-client / cbss-types); **all 21 SystemInstruction handlers in code** (60-63 TEE keys + 68-84 CBSS main, `node/types/src/execution.rs:653-681`); BLS12-381 threshold IBE / DKG / proxy registry / release receipt — full stack present |
| **CIP-29 (Event Hooks)** | ❌ <5% | 🟢 **~55%** | `node/types/src/constants.rs:156` `EVENT_SUBSCRIPTION_SYSTEM_ACTOR = 0x1D`; 914 lines across three files: `storage/src/event_subs.rs` (410) + `execution/src/execution/event_fire.rs` (151) + `execution/src/execution/event_sub_system_actor.rs` (353); 3 read RPCs (`get_rank` / `get_topic_orderbook` / `get_min_bid_for_rank`) routed via `pvm_host::call_actor:1867-1881` interception; `EmitOrigin` DeferredTx metadata tag + `MAX_TOPIC_BYTES=64` / `MAX_EVENT_PAYLOAD_BYTES=4096` / `ASYNC_FIRES_PER_DEFER_TX=64` constants; StatePrefix moved to `EVENT_SUB=0x0E` / `EVENT_SUB_INDEX_VALUE=0x0F` (resolved CIP-26 collision); spec §2.6 also synchronized to `0x1D` by this audit |
| **CIP-9** | 🟡 70% | 🟢 73% | §13 AMEND 9-J completed: `SubmitDrainRelayProposal`(85) / `SubmitAutoDrainPolicyProposal`(86) now in code (`node/execution/src/execution/system_instruction.rs:747-905`); this audit fully aligned spec to code |
| **CIP-12** | demo level | 🟡 30% | `ProposalPayloadKind` extended from 1 (`UpdateBasefeeConfig`) to 3 (+`DrainRelay` + `UpdateAutoDrainPolicy`, `node/runner/src/types.rs:835`); generic `ExecuteProposal`(47) path via `SubmitDrainRelayProposal`(85) / `SubmitAutoDrainPolicyProposal`(86) in code |
| **CIP-23** | 🟡 ~25% | 🟡 ~30% | TEE Verifier support opcodes 60-63 in code (`SYS_REGISTER_TEE_TRUSTED_KEY` etc., driven by CIP-24 §3.3; CIP-23 v2 reuses); but CAE composite attestation / cert chains / nonce replay protection / dispatcher MeasurementBinding filtering all still missing |
| **CIP-8** | ✅ ~90% | ✅ ~92% | All 6 opcodes 52-57 confirmed in code (`SYS_SESSION_OPEN`…`SYS_SESSION_SLASH`); **Slash still stubbed** (`node/execution/src/runner/session.rs:371-380` returns `UnsupportedInstruction`, awaits verifier-arbitration milestone) |

The other 24 CIPs are unchanged in status (see §9).

---

## 2. Overview Matrix (2026-05-26 State)

### 2.1 Implementation State Distribution

| State | Count | CIPs |
|---|---:|---|
| ✅ ≥85% | 6 | CIP-2 / CIP-5 / CIP-6 / CIP-8 / CIP-20 / CIP-26 |
| 🟢 60-85% | 7 | CIP-3 / CIP-4 / CIP-9 / CIP-17 / CIP-24 / CIP-25 / CIP-29 |
| 🟡 25-60% | 2 | CIP-12 / CIP-23 |
| 🟠 5-25% | 5 | CIP-1 / CIP-7 / CIP-14 / CIP-15 / CIP-31 |
| ❌ <5% | 9 | CIP-10 / CIP-11 / CIP-13 / CIP-16 / CIP-18 / CIP-19 / CIP-21 / CIP-22 / CIP-28 |

### 2.2 Full CIP Detailed Matrix

| CIP | Topic | Progress | Key Code Assets / Gaps |
|---|---|---|---|
| **CIP-1** | Actor Scheduler v3 (EIP-1559 timer lane) | 🟠 ~5% | Still only CIP-5 FIFO baseline; v3 tiered calendar queue + GBA + fairness weights all absent |
| **CIP-2** | Off-Chain Verifiable Compute v1 | ✅ ~85% | Core skeleton complete (RUNNER_REGISTRY / JOB_DISPATCHER / RESULT_VERIFIER + VRF + commit-reveal + 6 modes); v2 DNS check / v3 mechanism reforms missing |
| **CIP-3** | Cycles+Cells Dual-Metered Fee Model | 🟢 70% | EIP-1559 dual metering complete (`basefee.rs`); **lane multiplier absent**; lane budgets diverge 4× from spec |
| **CIP-4** | On-Chain State Storage | 🟢 75% | QMDB + Merkle proofs complete; **§12 state rent fully missing**; StatePrefix layout diverges from spec |
| **CIP-5** | Native Timers (revised) | ✅ ~93% | Model B end-to-end complete; **carry-forward bug known** (`speculative.rs:751`) |
| **CIP-6** | Python SDK / Actor API | ✅ ~95% | Full surface: three call primitives / FSM compiler / Continuation; this session synchronized CIP-6 spec to new "In-PVM Actor SDK (cowboy_sdk)" framing |
| **CIP-7** | Simple Stream Protocol r2 | 🟠 ~10% | Only one Python demo; `0x12 STREAM_KEY_MANAGER` system actor entirely absent; spec r2 fixed v1 `0x06` conflict |
| **CIP-8** | MPP Session (retroactive) | ✅ ~92% | All 6 opcodes 52-57 in code; on-chain `SESSION_ACTOR=0x0C` + off-chain voucher lib (`runner-common/voucher.rs`) + EIP-712 domain; **only `handle_session_slash` is `UnsupportedInstruction` stub** (`session.rs:371-380`), awaits CIP-2 dispute arbitration milestone |
| **CIP-9** | Runner Storage / CBFS | 🟢 73% | Data plane complete (StorageCommitment / CapToken / Relay scheduling); **§13 DrainRelay / AutoDrainPolicy governance plane newly aligned** (opcodes 85/86); GET_MANIFEST RPC still missing, ManifestCommitted event not emitted, PoR economics not fully wired |
| **CIP-10** | Runner Containers (OCI) | ❌ 0% | Fully unimplemented: no OCI / cgroups / GPU / network policy / Container Registry 0x10 |
| **CIP-11** | Runner QUIC Push Connectivity | ❌ 0% | Fully unimplemented: no QUIC channels / presence bitmap / MRU stickiness |
| **CIP-12** | On-Chain Governance | 🟡 30% | demo `SubmitProposal/CastVote/ExecuteProposal` present; **3 `ProposalPayloadKind` variants landed** (including CIP-9 §13 two); no bicameral / Tier / Security Council / fast-track |
| **CIP-13** | Runner Stake Delegation v2 | ❌ 0% | Still unimplemented; **opcode 52-56 historical claim collides with code CIP-8 Session 52-57** (this session's spec marked TBD ≥87) |
| **CIP-14** | DNS Addressable Actor v2 | 🟠 ~5% | Only `POST /actor/read` hits read-only semantics; no `0x0D` Route / `0x0E` Gateway / `0x0F` Receipt Registry; no IngressDispatch (65) / CompleteReceipt (66) |
| **CIP-15** | Gateway Implementation + Public Assets v2 | 🟠 ~10% | Only CBFS Visibility::Public base; no Gateway HTTP serving; no on-chain route_manifest / cors_config |
| **CIP-16** | Custom Domains / TLD v2 | ❌ 0% | Fully unimplemented |
| **CIP-17** | Verifiable State Read RPC | 🟢 80% | `/proof/storage/*` etc. complete; endpoint paths / `block_hash` / `absent` fields diverge from spec |
| **CIP-18** | Payments (PaymentGate `0x11`) r2 | ❌ 0% | Fully unimplemented (2026-05-11 r2 freshly finalized, address range `0x0013→0x11` rearranged) |
| **CIP-19** | Gateway MCP Ingress | ❌ 0% | Depends on CIP-14/15/18 (all absent); `runner-mcp` is outbound client, opposite direction |
| **CIP-20** | Fungible Tokens | ✅ ~85% | Core complete; `on_transfer` post-hook missing, events not emitted, hook cells cap unwired |
| **CIP-21** | DEX / Liquidity Pools | ❌ 0% | Fully unimplemented |
| **CIP-22** | Continuous Clearing Auctions | ❌ 0% | Fully unimplemented |
| **CIP-23** | TEE Execution | 🟡 ~30% | Signature verification skeleton + TEE Verifier support opcodes 60-63 in code (driven by CIP-24 §3.3); CAE composite attestation / cert chains / nonce replay protection / dispatcher MeasurementBinding filtering still missing |
| **CIP-24** | Cowboy Secret Service (CBSS) | 🟢 **~80%** | **Massive code landing**: all 21 SystemInstruction handlers (60-63 TEE keys + 68-84 CBSS main); BLS12-381 threshold IBE / DKG ceremony / proxy registry / release receipt / liveness challenge / reshare / forced deregister — all in code; standalone `cbssd` daemon + cbss-crypto / cbss-client / cbss-types workspace. **Only** Intel DCAP/TDX + AMD SEV-SNP full cert-chain vendor collateral verification deferred to v1.1 pre-mainnet milestone |
| **CIP-25** | Cross-Chain Architecture | 🟢 ~60% | Cowboy↔Ethereum demo bridge functional; fraud proofs are stubs / no ZK / no optimistic / no native LC / no multi-chain |
| **CIP-26** | Account-Scoped Libraries | ✅ ~95% | Full surface + end-to-end example; **one of the most mature CIPs** |
| **CIP-28** | Agent Banking (BankActor) | ❌ 0% | Only HTML mock-up (2026-05-12 finalized, this session r1.1 moved address `0x0D` → `0x13`) |
| **CIP-29** | On-Chain Event Hooks | 🟢 **~55%** | `EVENT_SUBSCRIPTION_SYSTEM_ACTOR=0x1D` virtual actor + Phase 1 sync fire + Phase 2 bid-sorted async fire framework; 3 read RPCs; emit_event + EmitOrigin DeferredTx metadata; StatePrefix moved to avoid CIP-26 collision. **Main gaps**: bid orderbook persistence depth / async fire path full test coverage / Phase 3 cross-block fire chain |
| **CIP-31** | CBFS Rent Schedule | 🟠 ~10% | Three-way split missing / challenge bond missing / slashing table missing; rate values off by 10× |

---

## 3. Per-CIP Detailed Analysis

### 3.1 Actor & Compute Layer (CIP-1/2/6)

#### CIP-1 v3 — Actor Scheduler

**Conclusion**: v1 tiered calendar queue, v3 EIP-1559 timer-lane base fee, and per-actor fairness weights are **all fully unimplemented**. Code sits at the CIP-5 FIFO baseline (which the spec permits as a pre-activation state).

| Requirement | Status | Evidence |
|---|---|---|
| Tx-then-Timer block ordering | ✅ | `node/storage/src/speculative.rs:204-302` |
| Three-path lifecycle (natural / TTL / bankruptcy-suicide) | ✅ | `speculative.rs:626-728` |
| System instructions 48/49/50 (Cancel/UpdateConfig/Extend) | ✅ | `types/src/execution.rs:539,543,548` |
| `LANE_TIMER_CYCLES` execution lane | ✅ | `constants.rs:61` = 8,888,890 |
| **Carry-forward** (skipped timer should slip to next block) | ❌ | `speculative.rs:751` skips but does not reindex — known bug |
| **Tiered calendar queue (Ring/Epoch/Overflow)** | ❌ | `storage/src/timers.rs` is only a flat per-height map |
| **GBA / `getGasBid(context)`** | ❌ | No code |
| **EIP-1559 timer-lane basefee** | ❌ | `basefee.rs:37-74` only has `cycle_basefee` + `cell_basefee` |
| **`max_fee_per_cycle` in schedule_timer** | ❌ | `pvm_host.rs:1606-1725` signature lacks fee fields |
| **Fairness weight `W(actor) ∈ [1,2]`** | ❌ | No `FAIRNESS_WINDOW_BLOCKS` computation |
| **`priority_tier_hint` enum** | ❌ | Not present in SDK |

#### CIP-2 — Off-Chain Verifiable Compute

**Conclusion**: v1 backbone complete; multiple v2/v3 reforms unimplemented. 5/15 baseline unchanged.

✅ Implemented:
- System actors `0x01-0x07` + extensions `0x08`(Treasury) / `0x09`(Governance) / `0x0A`(StorageManager) / `0x0B`(RelayRegistry) / `0x0C`(Session)
- `JobSpec` schema (`runner-common/types.rs:101-117`)
- Fisher-Yates VRF seed = `Keccak256(block_hash || "cowboy-runner-select-v2:" || job_id || submitted_at_le8)` (`dispatcher.rs:1095-1108`)
- Candidates sorted by address bytes ascending (`dispatcher.rs:1266`)
- Logarithmic weight `stake_to_weight` (`dispatcher.rs:64-72`)
- 7-stage candidate filtering (health/rep≥50/capability/TEE/price/concurrency/pool stake), actually has additional probation, attachments, stake×1.5
- Retry seed = `Keccak256(original_seed || "retry:" || retry_count_le4)` (`dispatcher.rs:1429-1437`)
- Commit-reveal flow (`verifier.rs:35-200`), commit deadline at `submitted_at + 0.6 * timeout_blocks`
- 6 VerificationMode variants (`runner-common/types.rs:325-383`)
- Entitlement Registry types + instructions 30-35 (`types/src/entitlement.rs`, `types/src/execution.rs:517-522`)
- TEE Verifier + CBSS Secrets Manager system actors (`execution/src/cbss.rs:1106-1500+`)

❌ Missing:
- v2 DNS check variants (`DnsTxtRecordMatch` / `DnsCnameMatch`)
- v3 `CrashAttestation` mechanism
- v3 `SlashDistribution { burn_bps, submitter_bps, treasury_bps }` schema
- v3 aggregator bonus `aggregator_bonus_bps = 150`
- v3 HHI-adaptive committee sizing
- v3 VRF weight `w = stake × sqrt(reputation)` (currently uses `stake_to_weight × completion_rate / REPUTATION_WEIGHT_SCALE`)
- v3 pinned semantic similarity model `0x09/system:cip2:semantic_similarity_embedding_model`

#### CIP-6 — Python SDK

**Conclusion**: The **most complete** CIP in this audit (~95%). This session synchronized CIP-6 spec to "In-PVM Actor SDK (cowboy_sdk)" new framing.

✅ Fully implemented (in `node/pvm/Lib/cowboy_sdk/`):
- Three call primitives: `call()` / `send()` / `await runner.*` (`call.py:17`, `send.py:18`, `runner.py:80`)
- `ActorRef` syntax sugar
- `@reentrancy_guard`, `@runner.continuation`, `@actor.continuation`
- FSM-AST compiler (`_compiler.py:64`) statically enforces ≤8 awaits, bans nested await, bans recursive await
- `capture()` explicit state capture
- Limits exactly match spec: `_MAX_CONT_SIZE=64*1024`, `_MAX_CONT_COUNT=100`, await cap = 8
- `guard_unchanged=[...]` decorator-level guards
- `storage.guard(key)` returns `GuardedValue`
- `Retry` exponential backoff
- `TaskGroup` structured concurrency (`taskgroup.py:108`)
- `CowboyModel` deterministic type stack
- `SoftFloat`, `ordered_set`, `BlockHeight`
- `Verify` builder + 16 built-in validators (incl. `no_prompt_leak`, `entropy_check`)
- `@pure`, `@deferred`, `@public`, `@callable_by(OWNER|SELF)`

❌ Gaps:
- `priority_tier_hint` enum (depends on CIP-1 v3, unimplemented)
- CLI version drift (self-reports v0.1.1 / 0.0.24, actually 0.0.29)

---

### 3.2 Storage & Filesystem (CIP-4/9/31)

#### CIP-4 — On-Chain State Storage

✅ Implemented:
- 54-byte fixed key (`state_key.rs:22`)
- QMDB three-tier Ledger/State/Aux pipeline (`chain/src/application.rs:619-689`)
- Speculative cache cap 8 (`blockchain_storage.rs:44`)
- Merkle proof full RPC: `/proof/account`, `/proof/actor`, `/proof/storage`, `/proof/tx`, `/proof/receipt`, `/proof/multi` (`rpc/src/handlers/proof.rs`)
- Standalone `cowboy-proof-verifier` crate
- Parameters: `MAX_TIMERS_PER_ACTOR=1024`, `MAX_PENDING_DEFERRED_PER_ACTOR=64`, etc.

🟡 Deviations from spec:
- Route key is **20 bytes** instead of spec's 21 (suffix 33 instead of 32)
- Prefix enum starts at `0x01` instead of `0x00`: `Account=0x01`, `Actor=0x02`, `ActorStorage=0x03`, … `SystemState=0x0A`
- Added production prefixes: `Code=0x0F`, `ActorMailboxHead=0x10`, `Library=0x14`, `TxReturnData=0x16`, `PublishRootDedup=0x17`
- **5/26 additions**: `EVENT_SUB=0x0E`, `EVENT_SUB_INDEX_VALUE=0x0F` (CIP-29 shipped, avoiding CIP-26's `Library=0x14` / `ActorLibPin=0x15`)

❌ **Critical missing**:
- **§12 state rent fully unimplemented** — no `rent_debt`, `grace_threshold`, `rent_rate`, `account_size_bytes`, `rent_catchup_bps`, no `system:cip4:rent_*` governance keys

#### CIP-9 — Runner Storage / CBFS

**Architecture map** (`cbfs/`):
- `cbfs/types/` — 1604 LOC, spec types
- `cbfs/store/` — Sled blob store
- `cbfs/placement/` — Sled placement CAS
- `cbfs/manifest/` — Merkle building
- `cbfs/erasure/` — Reed-Solomon GF(8)
- `cbfs/crypto/` — AES-256-GCM, DEK wrap/unwrap, BLAKE3
- `cbfs/transport/` — QUIC + TLS + protocol framing
- `cbfs/fuse/` — POSIX FUSE mount
- `cbfs/sdk/` — `Volume::create/open` etc. SDK
- `cbfs/cli/`, `cbfs/node/`, `cbfs/hooks/`, `cbfs/cowboy-ras/`, `cbfs/auth/`

✅ Implemented:
- `0x0A STORAGE_MANAGER`, `0x0B RELAY_REGISTRY`
- `StorageCommitment` schema (with production fields `paid_until_epoch`, `escrow_balance`)
- 4-state machine `ACTIVE → GRACE_PERIOD → DELETED → GARBAGE_COLLECTING`
- `Visibility::Public/Private`
- Reed-Solomon K∈[2..16], M∈[1..8], default 4/6
- AES-256-GCM client-side encryption + 12-byte Nonce
- BLAKE3 + power-of-2 padded Merkle (exact match to v2.r2 §3)
- Operation enum: PutShard, GetShard, DeleteShard, ProveShard, GetPlacement, PutPlacement, ReplicatePlacement, Ping, etc.
- Autonomous 2-phase shard repair (`cbfs/node/src/repair.rs:130-275`)
- Orphan shard GC
- FUSE mount + 5-second push/pull sync daemon
- Two-tier commit (Steamtrain + on-chain `commit_manifest_v2`)
- Volume create / undelete / commit_manifest_v2 endpoints
- Library is not a sidecar (`runner-storage` directly embeds `cbfs_sdk`, `cbfs_fuse`, `cbfs_transport`)
- **5/26 addition**: §13 AMEND 9-J `SubmitDrainRelayProposal`(85) / `SubmitAutoDrainPolicyProposal`(86) governance plane in code (`node/execution/src/execution/system_instruction.rs:747-905`)

❌ Missing:
- **AMEND 9-G `GET_MANIFEST` RPC** — Operation enum lacks this variant
- **AMEND 9-H `ManifestCommitted` chain event** — never emitted
- **PoR challenge plane** — `shard_inclusion_proof` hardcoded empty (`cbfs/node/src/handler.rs:793`); no on-chain PoR timer, verifier, `POR_CHALLENGE_INTERVAL`/`POR_MISS_PENALTY`/`POR_RESPONSE_WINDOW` constants
- **`transfer_volume`**
- **Volume capacity / account quota limits** (`MAX_VOLUMES_PER_ACCOUNT=256`, `MAX_VOLUME_SIZE=100GiB` not coded)
- **`VOLUME_CREATION_FEE` / `BASE_ATTACHMENT_FEE`** fee constants
- **`STORAGE_GRACE_EPOCHS = 2`** (spec 86,400, 10× deviation)
- **HKDF + `wrapping_key_hash`** path (production uses `sealed_runner_keys` instead)

#### CIP-31 — CBFS Rent Schedule

**Conclusion**: **least complete spec** in this domain. 5/15 baseline unchanged.

| Requirement | Status | Evidence |
|---|---|---|
| `STORAGE_FEE_PER_BYTE_PER_EPOCH = 10` nano-CBY | ❌ | Actual value = 1 (10× deviation), `cowboy-ras/src/lib.rs:25` |
| `TRANSFER_FEE_PER_BYTE = 1` | ❌ | Constant does not exist |
| **10/2/88 three-way split** | ❌ | Only two-way (10/90), `split_storage_fee` returns `(burned, relay_rewards)` |
| **Pro-rata weight `shard_count × shard_age`** | ❌ | No `MAX_SHARD_AGE_FOR_WEIGHTING` |
| `MIN_RELAY_STAKE = 5,000 CBY` | ❌ | Does not exist |
| **`RELAY_CHALLENGE_BOND = 10 CBY`** | ❌ | Fully missing |
| `POR_CHALLENGE_FEE` / `CHALLENGER_BOUNTY` | ❌ | Does not exist |
| **Slashing table** (`POR_MISS_PENALTY=50` etc.) | ❌ | Entirely absent |
| Storage Manager `0x0A` / Relay Registry `0x0B` | ✅ | `cbfs/cowboy-ras/src/system_actors.rs:11-18` |

---

### 3.3 Runner System (CIP-10/11/13)

#### Runner Workspace Crate Map (`runner/crates/`)

- `runner-node` — main binary; `start_job_listener` polling loop
- `runner-common` — shared types (`JobSpec`, `JobAssignment`, `RunnerResult`), ECDSA signing, voucher serde
- `chain-client` — chain REST client
- `runner-llm`, `runner-http`, `runner-mcp`, `runner-agent` — Job executors
- `runner-tee` — TEE attestation generation
- `runner-storage` — CIP-9 volume orchestration
- `runner-registry`, `job-dispatcher`, `result-verifier`, `tee-verifier` — off-chain Rust mirrors of system-actor handlers (for tests)
- `runner-consensus` — N-of-M aggregation + BLS VRF stub

#### CIP-10 — Container Runtime

**Conclusion**: **fully 0% implementation**. 5/15 baseline unchanged.

❌ All missing:
- OCI image format / digest pinning
- `RuntimeConfig` fields on JobSpec
- Container creation (cgroups v2, namespaces, overlayfs) — `JobType` is only Llm/Http/Mcp/Custom/PublishChainRoot/Agent
- FUSE mount to `/mnt/volumes/*` (currently mounts directly on host filesystem)
- `ResourceLimits` (CPU milli-cores, scratch disk, GPU) — current `ResourceBounds` is LLM-only
- Resource classes (`small`/`medium`/`large`/`gpu-*`)
- Runner capability advertisement (GPU devices, cached base images)
- GPU passthrough (NVIDIA/ROCm)
- `NetworkPolicy` (NONE/ALLOWLIST)
- Container lifecycle (pull → create → mount → exec → teardown)
- `Container Registry` system actor `0x10`
- Opcodes 61-64 (**5/26 new conflict**: these opcodes are now occupied by CIP-24 §3.3 TEE keys; CIP-10 v2 activation must renumber to ≥87)
- `BillingAttestation` with `cgroup_digest`

> Note: `runner-agent`'s "Sandbox" is only path pre-check (`fs_tools.rs:66`), not OS-level isolation.

#### CIP-11 — Runner Connectivity & Push

**Conclusion**: **fully 0% implementation**. Currently uses 5-second HTTP polling + on-chain heartbeat. 5/15 baseline unchanged.

❌ All missing:
- Connectivity subset function `Sub(R, t)`
- QUIC control + job streams (`quinn` is only used by cbfs-transport for storage shard fetching)
- `Hello`/`HelloAck` handshake
- `HeartbeatPing`/`Pong`, `BackpressureSignal`, `CapabilityDelta` frames
- Presence bitmap carried by votes
- Presence filter in dispatcher (current filter chain lacks it)
- MRU weight multiplier
- Push-style `JobAssignment`
- `JobAck`/`JobProgress`/`JobResult`/`JobCancel` frames

#### CIP-13 — Runner Stake Delegation v2

**Conclusion**: **fully 0% implementation**, and has **opcode conflicts**.

❌ All missing:
- `DelegationConfig` fields
- `DelegationTranche`/`TrancheStatus`/`DelegationTotals` types
- Opcodes 52-56 `RunnerUpdateDelegationConfig` etc.
- `effective_stake` in VRF
- Pro-rata payout to delegators

⚠️ **Conflict** (5/26 spec-side resolved):
- v1 spec claimed 52-56 for delegation, **but code 52-57 is used by MPP Session** (`SYS_SESSION_OPEN=52` … `SYS_SESSION_SLASH=57`)
- This session's spec marked CIP-13 v2 §1 master opcode table as TBD ≥87 (drift.md C-3 closed)

#### Runner Fee Chain Analysis (CIP-2/9/10 cross-cutting)

Three independent fee flows:
- **Flow 1 (Runner job payment, CIP-2)**: ✅ implemented (default 89/10/1 split)
- **Flow 2 (Storage rent, CIP-9)**: ❌ no epoch debit loop
- **Flow 3 (Container compute, CIP-10)**: ❌ fully missing

---

### 3.4 Networking & Sessions (CIP-7/8/15/19)

#### CIP-7 — Simple Stream Protocol r2

**Conclusion**: Only a non-canonical Python demo (`/node/cli/actors/stream_actor.py`), implements coarse publish/subscribe. 5/15 baseline unchanged.

❌ All missing:
- Canonical `StreamMessage` (13 fields, CBOR + ed25519)
- Ring buffer (`head_sequence`, `floor_sequence`, `DEFAULT_RING_BUFFER_CAPACITY=10_000`)
- JSON Filter DSL
- **`0x12 STREAM_KEY_MANAGER`** system actor
- `stream_encrypt`/`stream_decrypt`/`acquire_epoch_access`/`register_account_key` HostApi
- `PaidStreamConfig`/`Entitlement`/`AccountKeyRegistration`/`KeyAccessReceipt` types
- XChaCha20-Poly1305 (`NONCE_BYTES=24`, `TAG_BYTES=16`)
- CBY epoch billing + `EpochAccessPurchased` event
- 9 events (`StreamMessagePublished` etc.)

#### CIP-8 — MPP Session

**Conclusion**: One of the **most complete** in this audit (~92%, 5/26 slight rise from ~90%).

✅ Implemented:
- `SESSION_ACTOR=0x0C` (`system_actors.rs:35`)
- Storage layout `b"session:" || session_id`
- `Session`, `SessionAsset::Cby`, `SessionVoucher` (with 65-byte signature)
- EIP-712 domain `"Cowboy MPP Session" v1` (`types/src/session_eip712.rs`)
- **All 6 opcodes 52-57 confirmed in code**: `SYS_SESSION_OPEN/DEPOSIT/SETTLE/CLOSE/FINALIZE/SLASH`
- 6 handlers: `OpenSession`/`Deposit`/`Settle`/`CloseSession`/`Finalize`/`Slash` (last returns `Unsupported`, per §8.6)
- 5 voucher checks (session_id, status window, expiry, nonce monotonic, cumulative cap)
- 89/10/1 settlement split reuses CIP-2 SettlementConfig
- `DISPUTE_WINDOW_BLOCKS=75`
- Off-chain voucher lib (`runner-common/src/voucher.rs`) includes EIP-712 domain and sign/recover
- 3 working demos (`examples/mpp_session/`, `llm_session/`, `session_chain_e2e/`)

🟡 Minor deviations:
- `SessionStatus::Slashed{...}` variant missing
- Storage uses `serde_json` instead of spec's bincode
- **Slash still stubbed** (`node/execution/src/runner/session.rs:371-380` returns `UnsupportedInstruction`) — awaits CIP-2 dispute arbitration milestone

#### CIP-15 — Gateway Implementation + Public Assets

**Conclusion**: Gateway HTTP serving **fully absent**. 5/15 baseline unchanged.

❌ Missing:
- Gateway HTTP server crate
- `ROUTE_REGISTRY (0x0D)`, `GATEWAY_REGISTRY (0x0E)`, `RECEIPT_REGISTRY (0x0F)`
- `ingress.http`, `ingress.static`, `ingress.mcp`, `dns.attach_external` entitlements
- On-chain route manifest + `update_route_manifest` handler
- `_meta/routes.json` / `_meta/cors.json` etc.
- `/_cowboy/*` reserved path interception
- Per-volume metadata cache, object LRU, hedged-parallel shard fetch
- `PaymentGate (0x11)`

✅ Adjacent code only:
- CBFS Visibility::Public + commit_manifest_v2
- BLAKE3 power-of-2 padded Merkle (`cbfs/manifest/src/merkle.rs:24-68`)
- `POST /actor/read` read handler primitive (`rpc/handlers/actor.rs:39`)

#### CIP-19 — Gateway MCP Ingress

**Conclusion**: **fully 0% implementation**. The two MCP-named artifacts both point the wrong way:
- `runner-mcp` is an MCP **client** (CIP-2 executor backend, outbound)
- `monorepo/mcp` is a third-party Commonware doc MCP server

---

### 3.5 Addressing & Governance (CIP-5/12/14/16/17)

#### CIP-5 — Native Timers

**Conclusion**: ~93% complete. 5/15 baseline unchanged.

✅ Fully implemented:
- `Timer` struct (8-field Model-B schema)
- Storage + per-height index (FIFO)
- `MAX_TIMERS_PER_ACTOR=1024` cap
- Timer ID = `keccak256(actor‖height_be‖payload‖nonce_be)`
- 5 PVM syscalls: `schedule_timer`, `schedule_timer_ex`, `extend_timer`, `cancel_timer` + ownership checks
- `fee_payer` validation (reject ZERO, system band `0x01..0x0F`, third-party restriction)
- EOB FIFO dispatch + three-path classification
- Pre-charge `max_cost` to `fee_payer`, refund per actual cost
- TTL/bankruptcy-suicide event emission
- Deferred-tx construction (origin = zero hash)
- `LANE_TIMER_CYCLES` + `TIMER_GC_CYCLES` dual lanes
- Governance-tunable `TimerConfig`
- Opcodes 48/49/50 (`SYS_CANCEL_TIMER/UPDATE_TIMER_CONFIG/EXTEND_TIMER`)

❌ Missing:
- §9 future EIP-1559 timer auction (depends on CIP-1 v3, unimplemented)

⚠️ **Known bug** (`speculative.rs:751`): Timers exceeding lane budget are skipped via `continue` but `height` field is not updated; `get_timers_by_height` strict-matches height, so the next block never re-selects them — **over-budget timers are permanently lost**.

#### CIP-12 — Governance

**Conclusion**: Demo level only. Code self-admits "Simplified vs. CIP-12" (`runner/src/types.rs:819,856`). 5/26 slight rise to 30%:

✅ Implemented:
- `0x09 GOVERNANCE_SYSTEM_ACTOR`
- Opcodes 45-47 (`SUBMIT_PROPOSAL/CAST_VOTE/EXECUTE_PROPOSAL`)
- Proposal storage + RPCs (`/governance/proposals` etc.)
- **3 payload kinds** (5/26 expanded from 1 to 3): `UpdateBasefeeConfig`, `DrainRelay`, `UpdateAutoDrainPolicy`
- Opcodes 85/86 `SubmitDrainRelayProposal/SubmitAutoDrainPolicyProposal` generic `ExecuteProposal`(47) path
- Smoke test (`examples/governance/smoke-voting.mjs`)

❌ All missing:
- Bicameral voting (stake house + validator house)
- Tier 0-4 hierarchy
- Temperature check
- Timelock
- 7-of-9 Security Council (cancel / fast-track / circuit-break)
- System actor upgrade workflow (`SystemActorUpgrade`, rollback_slot, pending_upgrades)
- `MetaGovernance` payload
- Proposal deposit (refund vs burn)
- Vote extension mechanism
- `TreasuryDisbursement` / `RegistryUpdate` payloads

#### CIP-14 — DNS Addressable Actor

**Conclusion**: On-chain side of this spec **fully unimplemented**. 5/15 baseline unchanged.

✅ Adjacent code only:
- `POST /actor/read` endpoint (`rpc/src/rpc.rs:228`), executes `read_only=true` handler
- PVM read-only mode + complete syscall trap table (`pvm_host.rs` `deny_if_read_only`)

❌ Missing:
- `ROUTE_REGISTRY (0x0D)` / `GATEWAY_REGISTRY (0x0E)` / `RECEIPT_REGISTRY (0x0F)`
- `RouteRegistration` schema
- `ingress.http` entitlement
- `IngressDispatch` opcode
- `read_handler` RPC naming (current path is different)
- Domain-length-tiered registration fee + grace period + Dutch auction
- Gateway heartbeat/dispatch API

#### CIP-16 — Custom Domains

**Conclusion**: **fully 0% implementation**. The only adjacent thing is the pre-existing `VerificationMode::MajorityVote` (used by CIP-2); everything else absent.

#### CIP-17 — Verifiable State Read

**Conclusion**: **Functionally complete but with naming differences**. 5/15 baseline unchanged.

🟡 Implemented but name/format differs from spec:
- Endpoint: `/proof/storage/{addr}/{key}` instead of `/state/{addr}/{key_hex}`
- Proof: QMDB MMR (BLAKE3) instead of MPT siblings (keccak)
- Response missing `block_hash` and `absent` fields
- No `prove=false` query parameter
- ✅ `/proof/multi` batch read implemented (spec lists as future work)

---

### 3.6 Finance & Tokens (CIP-3/18/20/21/22/26/28)

#### CIP-3 — Dual-Metered Fee Model

✅ Implemented:
- Cycle metering + Cell metering
- 4 execution lanes: User/Runner/Timer/System
- EIP-1559 update formula (`basefee.rs:223-264`, `ALPHA=96`, `DENOM=96`, `MIN_BASEFEE=10_000`, `MAX_BASEFEE=1e24`)
- Genesis + persistence (`BASEFEE_SYSTEM_ACTOR=0x06`)
- Tx fee composition: burn (basefee) + proposer tip
- Governance-tunable `BasefeeConfig`

🟡 Deviations:
- Lane budgets vs spec (5M/2.5M/2M/0.5M) → code 22M/8.9M/8.9M/40M, ~4× scaling (self-admitted tuning)
- **Execution lane fee multiplier (§2.2.3) fully absent** — no `lane_fee_multiplier` governance key
- Transfer base cost uses 2026-04-15 amendment (5000 cycles / 500 cells), not original CIP-3 21k

#### CIP-18 — Payments (PaymentGate 0x11)

**Conclusion**: **fully 0% implementation** (CIP r2 freshly finalized 2026-05-11). 5/15 baseline unchanged.

❌ All missing:
- `PAYMENT_GATE_ADDRESS = 0x11`
- `PaymentPolicy`/`PaymentIntent`/`PaymentBinding` types
- MPP wire format (`WWW-Authenticate: Payment`, `Payment-Receipt` etc.)
- x402 wire format (`PAYMENT-REQUIRED`, `PAYMENT-SIGNATURE` etc.)
- 4 payment models (per-request, actor-funded, prepaid pass, epoch subscription)
- Inbound EVM bridge facilitator (`bridge.facilitate.evm` entitlement)
- MCP gating (`-32402` JSON-RPC, `_meta.payment-authorization`)
- OpenAPI discovery `/_cowboy/payment/openapi.json`

> Note: `examples/bridge/` is the outbound CBY→ETH bridge (mature), but inbound facilitator is missing.

#### CIP-20 — Fungible Tokens

**Conclusion**: ~85% complete. 5/15 baseline unchanged.

✅ Implemented:
- `TokenMint` data struct (`token/src/types.rs:50-64`), `u128` amount type (per 2026-03-27 amendment)
- Token Registry system actor
- Storage layout: mints/balances/allowances/frozen
- All 7 operations: `token_create`, `token_transfer`, `token_transfer_from`, `token_approve`, `token_mint`, `token_burn`, `token_transfer_batch`
- Admin operations: `token_freeze_account`, `token_unfreeze_account`, `token_set_hook`, `token_transfer_ownership`
- `can_transfer` pre-hook + 50k cycles cap
- Reentrancy guard (`TokenHookReentrancy` error)
- `MAX_SUPPLY` check
- E2E example (`examples/token/`)

❌ Missing:
- **`on_transfer` post-hook** (spec requires pre + post)
- **Standardized event emission** (`TokenTransfer`, `TokenApproval`, `TokenMint`, `TokenBurn`, `TokenFrozen` etc. all without `emit_event` calls) — blocks indexer + compliance
- **Hook cells cap** (Phase 2 work)

#### CIP-21 — DEX & Liquidity Pools

**Conclusion**: **fully 0% implementation**. 5/15 baseline unchanged.

❌ All missing:
- `amm_get_amount_out` platform primitive
- `amm_get_amount_in`, `amm_quote`
- `amm_tick_to_sqrt_price` (Q64.96)
- `amm_swap_exact_in`/`amm_swap_exact_out`
- V2 constant product pool actor
- V3 concentrated liquidity pool actor
- Factory `create_v2_pool` / `create_v3_pool`
- Standard fee tiers (1/5/30/100 bps)
- Native TWAP oracle
- MEV protection hooks

#### CIP-22 — Continuous Clearing Auctions

**Conclusion**: **fully 0% implementation**. Depends on CIP-21 (also unimplemented).

#### CIP-26 — Account-Scoped Libraries

**Conclusion**: One of the **most complete** in this audit (~95%). 5/15 baseline unchanged.

✅ Fully implemented:
- `ActorLibrary` struct
- `StatePrefix::Library=0x14`, `ActorLibPin=0x15`
- `LibraryInstruction::PublishLibrary`, `RemoveLibrary`
- Handlers (`execution/src/execution/library_instruction.rs:54-120`)
- Name validation regex `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$`
- Code size cap `MAX_LIBRARY_CODE_BYTES=131_072`
- AST scan (`rustpython_compiler::extract_top_level_imports`)
- Stdlib + SDK whitelist filtering
- Cross-account import refusal (`UnresolvedImport`)
- `MAX_LIBS_PER_ACTOR=8`, `MAX_TOTAL_LIB_BYTES=131_072`
- Pin stays put after publisher republishes
- Pre-loaded into `sys.modules` before deploy
- CLI `cowboy lib publish/remove/list`
- End-to-end example `examples/cip26_account_libraries/start_all.sh --test`

❓ To verify:
- `LibraryPublished` event emission
- Per-call load gas (`len(code) × 5` cycles)

#### CIP-28 — Agent Banking

**Conclusion**: **Only HTML mock-up**. CIP finalized 2026-05-12; this session r1.1 moved address `0x0D → 0x13` (drift.md C-1 closed).

❌ All missing:
- `BankActor` system actor `0x13` (**5/26 renumbered**, original `0x0D` yielded to CIP-14 Route Registry)
- `BankEntry`/`CardEntry`/`CardPolicy`/`SpendWindow` types
- Card address derivation `keccak256(DOMAIN ‖ bank_id ‖ owner ‖ agent ‖ nonce)[12..32]`
- 15+ `BankInstruction` variants
- Third gas-deduction path (`tx.fee_payer_override` → BankActor.charge_gas)
- Limits (per_hour/day/month)
- Whitelists (`allowed_receivers`, `allowed_syscall_kinds`)
- `FiatMintVoucher` signature verification + `voucher_used` replay table
- Multi-bank governance addition workflow
- Pre-check + post-settlement pipeline
- `bank_activation_height` feature gate

🟡 Only:
- UI mock: `examples/cip28_agent_banking/index.html` (2606 lines of Chinese HTML)

---

### 3.7 Advanced Features (CIP-23/24/25/29)

#### CIP-23 — TEE Execution

**Conclusion**: ~30% (5/26 slight rise from 25%). Signature verification skeleton in place, but the composite attestation required by spec entirely absent.

✅ Implemented:
- `TEE_VERIFIER=0x05` assigned
- `sec.tee_required` entitlement
- `CANONICAL_TEE_TYPES` includes `nitro`
- TEE attestation handlers (`cbss.rs:1106-1287`): `register_tee_trusted_key`, `submit_tee_attestation`, `revoke_tee_attestation`
- **TEE Verifier support opcodes 60-63 in code** (`SYS_REGISTER_TEE_TRUSTED_KEY` etc., driven by CIP-24 §3.3; CIP-23 v2 reuses)
- Off-chain `tee-verifier` crate (P-256/P-384 signature verify + domain prefix `cowboy/tee-verifier/ecdsa-attestation/v1`)
- Result Verifier rejects Deterministic results lacking `tee_required`

❌ Critical missing:
- **`CompositeAttestation`** composite envelope (CPU+GPU+ServiceSig+Freshness) — only flat `TeeAttestation`
- **`0x05::VerifyCae`** verification pipeline — no nonce/seen-nonces, no freshness deadline, no GPU/NCC/NRAS, no `REPORTDATA = keccak(nonce ‖ pubkey ‖ gpu_measurement)`
- **Cert chain verification** — non DCAP / NRAS / VCEK / Nitro root chain, only trusted-key whitelist
- **`MeasurementBinding`** in Runner Registry — current `RunnerCapabilities` still only has `tee_support: Option<String>`
- **Dispatcher still uses deprecated boolean filter** (`dispatcher.rs:1186`) — explicitly banned by spec
- **Result Verifier does not call VerifyCae** — `result-verifier/src/verifier.rs:291` literal `// TODO: verify TEE attestation`
- **Secrets Manager `0x04` not TEE-gated**
- **`BillingAttestation` fields** (CIP-10 linkage)
- **`tee_call` SDK helper**
- **`MeasurementBinding` renewal** (604,800 blocks)
- **Opcode drift**: implemented at 60-63, v1 spec at 50-53, v2 spec at 57-60 — **conflicts with both**

#### CIP-24 — Cowboy Secret Service (CBSS)

**Conclusion**: **5/26 biggest change** — from not-listed in 5/15 audit to 🟢 **~80%**. Most complex single subsystem.

✅ Large-scale landing (41,000+ lines of code):
- **In node**: `execution/src/cbss.rs` (7,738 lines) + `types/src/cbss.rs` (1,906 lines) + `rpc/src/handlers/cbss.rs` (1,956 lines) = **11,600 lines**
- **Standalone workspace** (`cbss/`): cbssd / cbss-crypto / cbss-client / cbss-types = **29,448 lines**
- **All 21 SystemInstruction handlers in code** (`node/types/src/execution.rs:653-681`):
  - **60-63** TEE keys (`SYS_REGISTER_TEE_TRUSTED_KEY`, `SYS_SUBMIT_TEE_ATTESTATION`, `SYS_REVOKE_TEE_ATTESTATION`, `SYS_REGISTER_PROXY_TEE_KEY`)
  - **68-84** CBSS main (17): `SetSecret`, `UpdateSecretMeta`, `DeleteSecret`, `RotateSecretEpoch`, `AccessSecret`, `SetReleasePolicy`, `SubmitReleaseReceipt`, `CompleteDkg`, `SubmitDkgShare`, `StartReshare`, `SubmitReshareShare`, `CompleteReshare`, `SubmitLivenessProof`, `RegisterCbssProxy`, `DeregisterCbssProxy`, `UpdateProxyConfig`, `ForcedDeregisterCbssProxy`
- **Crypto library** (`cbss-crypto`): BLS12-381 threshold IBE + DKG ceremony + proxy registry + release receipt + liveness challenge + reshare + forced deregister — full stack
- **Standalone daemon** `cbssd` + cbss-client + cbss-types

❌ Only remaining:
- Intel DCAP/TDX full cert-chain vendor collateral verification
- AMD SEV-SNP full cert-chain vendor collateral verification
- Both deferred to **v1.1 pre-mainnet milestone**

#### CIP-25 — Cross-Chain Architecture

**Conclusion**: ~60% complete; the **only CIP in this audit with a complete cross-chain demo**. 5/15 baseline unchanged.

✅ Implemented:
- **L1**: `IChainAnchor` interface (`bridge/contracts/src/IChainAnchor.sol`)
- **L1**: `CowboyLightClient.sol` (2-of-3 ECDSA committee, `Anchor.v1` domain prefix)
- **L1**: `Anchor_C` (Ethereum-roots anchor, `bridge/anchor_c.py`)
- **L1**: `JobType::PublishChainRoot` (`runner/src/types.rs:260-266`)
- **L2**: `Mailbox_C` + `Mailbox_E.sol` (`send`/`deliver` + exactly-once + payload-hash binding)
- **L2**: source-side pre-payment + `reclaim_fee` + `bump_fee`
- **L2**: `on_timeout` L3 callback
- **L3**: asset bridge (lock-mint + burn-release) `AssetLock` + `AssetMint` + `WCBY` + `bridge_actor.py`
- 14+ E2E test scripts (`test_bridge_e2e.sh`, `test_reverse_e2e.sh`, `test_fraud_window_e2e.sh` etc.)

🟡 / ❌ Missing:
- `BlockCommitment` is only `(txRoot, receiptRoot)`, missing `state_root`/`parent_hash`/`finalized_at`
- **Fraud proof is stub** — `FraudWindow.sol::_verifyFraudEvidence` accepts any non-empty evidence
- **Committee dispute slashing** not wired end-to-end
- **`commitment_revoked` reorg primitive** missing
- **`send_stream` / `deliver_stream`** cross-chain streams missing
- **ZK / optimistic / native LC** backends missing
- **BLS / threshold-ECDSA aggregation** missing
- **Multi-chain support**: only Cowboy↔Ethereum; `ChainKind` only supports `COWBOY=0`, `ETHEREUM=1`
- **L3 generic cross-chain call dispatcher** missing

#### CIP-29 — On-Chain Event Hooks

**Conclusion**: **5/26 second-biggest change** — from ❌ <5% to 🟢 **~55%**. Phase 1 + Phase 2 framework fully implemented in 11 days.

✅ Implemented:
- **`EVENT_SUBSCRIPTION_SYSTEM_ACTOR=0x1D`** virtual actor (`node/types/src/constants.rs:156`)
- **914 lines across three files**:
  - `storage/src/event_subs.rs` (410 lines): subscription persistence, orderbook, indexing
  - `execution/src/execution/event_fire.rs` (151 lines): Phase 1 sync fire + Phase 2 async fire framework
  - `execution/src/execution/event_sub_system_actor.rs` (353 lines): subscription handlers
- **3 read RPCs** (routed via `pvm_host::call_actor:1867-1881` interception):
  - `get_rank(topic, subscriber)`
  - `get_topic_orderbook(topic)`
  - `get_min_bid_for_rank(topic, rank)`
- **`emit_event` host API** + `EmitOrigin` DeferredTx metadata tag
- **Protocol constants**: `MAX_TOPIC_BYTES=64`, `MAX_EVENT_PAYLOAD_BYTES=4096`, `ASYNC_FIRES_PER_DEFER_TX=64`
- **StatePrefix collision resolved**: moved to `EVENT_SUB=0x0E` / `EVENT_SUB_INDEX_VALUE=0x0F` (avoiding CIP-26's `Library=0x14` / `ActorLibPin=0x15`)
- Spec §2.6 synchronized to `0x1D` by this audit (drift.md C-2 closed)

❌ Main gaps:
- Bid orderbook persistence depth (currently only top-K)
- Async fire path full test coverage
- Phase 3 cross-block fire chain (overflow continues firing in next block)
- SDK `@emit` / `@on_event` decorators

---

## 4. Cross-Cutting Findings

### 4.1 System Actor Address Space (2026-05-26 State)

Code space splits into three bands:

```
0x01..=0x0C  (12, deployment-type in code)         RUNNER_REGISTRY through SESSION_ACTOR
0x1D          (1, host-intercepted virtual)         EVENT_SUBSCRIPTION_SYSTEM_ACTOR
0x0D..=0x13  (7, spec-only)                        Route/Gateway/Receipt/Container/PaymentGate/StreamKey/Bank
```

The reserved band `0x01..=0x0F` is barred from actor deployment / from being used as `fee_payer_override` in `pvm_host.rs:1961, 4291`; `0x1D` sits outside the reserved band and uses host-interception. This is a new protocol-level mode distinction (see [`refs/wiki/entities/system-actors.md`](../wiki/entities/system-actors.md) §"Two activation models").

| Address | Planned | From | Status |
|---|---|---|---|
| `0x0D` | ROUTE_REGISTRY | CIP-14 v2 | unassigned |
| `0x0E` | GATEWAY_REGISTRY | CIP-14 v2 | unassigned |
| `0x0F` | RECEIPT_REGISTRY | CIP-14 v2 | unassigned |
| `0x10` | CONTAINER_REGISTRY | CIP-10 v2 | unassigned |
| `0x11` | PAYMENT_GATE | CIP-18 r2 | unassigned |
| `0x12` | STREAM_KEY_MANAGER | CIP-7 r2 | unassigned |
| `0x13` | BANK_ACTOR | CIP-28 r1.1 | unassigned (5/26 renumbered from 0x0D) |
| `0x1D` | EVENT_SUBSCRIPTION | CIP-29 | ✅ **code shipped** |

### 4.2 SystemInstruction Opcode Actual Allocation (`node/types/src/execution.rs:591-699`)

| Band | Purpose | CIP | Status |
|---|---|---|---|
| 0-9 | Base + Runner Registry + Job Dispatch | CIP-2 | ✅ in code |
| 10-20 | Token operations | CIP-20 | ✅ in code |
| 21-29 | (reserved) | — | (free) |
| 30-35 | Entitlement | CIP-2 §7 | ✅ in code |
| 36-39 | (reserved) | — | (free) |
| 40-51 | Settlement / Fund / Key / Upgrade / Basefee / Proposal / Timer / DeployCode | CIP-2/3/5/12 | ✅ in code |
| **52-57** | **MPP Session** (Open/Deposit/Settle/Close/Finalize/Slash) | **CIP-8** | **✅ in code** |
| 58-59 | (free) | — | (free) |
| **60-63** | **TEE Verifier support** (RegisterTeeTrustedKey/Revoke/Submit/Revoke) | **CIP-24 §3.3** | **✅ in code** |
| 64-67 | (free) | — | (free); CIP-14 v2 / CIP-16 v2 expected to land at 65-67 |
| **68-84** | **CBSS main allocation** (SetSecret…ForcedDeregisterCbssProxy, 17) | **CIP-24 §3.3** | **✅ in code** |
| **85-86** | **CIP-9 §13** (SubmitDrainRelayProposal/SubmitAutoDrainPolicyProposal) | **CIP-9 §13** | **✅ in code** |
| 87+ | (free) | — | reserved for CIP-13 / CIP-23 v2 / CIP-10 v2 / CIP-28 etc. unactivated v2 proposals |

**Early v2-proposal claims occupying 52-67 all conflict with code** (CIP-13 52-56 collides with Session; CIP-23 57-60 collides with Session+TEE keys; CIP-10 61-64 collides with TEE keys). **They must renumber to ≥87 at activation**. This audit rewrote CIP-13 v2 §1 master table from the code-authoritative viewpoint.

### 4.3 Cross-CIP Consistency Items Closed (drift.md C-1/C-2/C-3/C-4 + L-5)

- C-1 ✅ CIP-28 BankActor `0x0D → 0x13` (yields to CIP-14 v2.r2 ROUTE_REGISTRY)
- C-2 ✅ CIP-29 spec `0x0A → 0x1D` (align to code authority)
- C-3 ✅ CIP-13 v2 §1 master opcode table rewritten from code-authoritative viewpoint
- C-4 ✅ CIP-9 §13 added AMEND 9-J normalizing DrainRelay / AutoDrainPolicy
- L-5 ✅ Block time unified to 1s (CIP-11 r1.2 + CIP-23 r1 rescaled in sync)

### 4.4 StatePrefix Namespace (5/26 collision resolution)

When CIP-29 was shipped, it adopted `EVENT_SUB=0x0E` / `EVENT_SUB_INDEX_VALUE=0x0F`, avoiding CIP-26's `Library=0x14` / `ActorLibPin=0x15`. The comment block at `node/storage/src/state_key.rs:85-92` records a historical collision (`PublishRootDedup` moved `0x14` → `0x16` → `0x17`).

### 4.5 Entitlement Registry Drift

The test `registry_has_exactly_15_entries` in `node/types/src/registry.rs` locks 15 items. **Missing** (and more besides):
- `ingress.http`, `ingress.static`, `ingress.mcp` (CIP-14, 15, 19)
- `dns.attach_external` (CIP-16)
- `payment.gate` (CIP-18)
- `bridge.subscribe_event` (CIP-29, 5/26 pending)

### 4.6 Beyond-Spec Implementation (also needs documentation)

- `JobType::Agent`, `JobType::PublishChainRoot` (not in CIP-2 v1)
- `Action::UseOwnerBalance` (entitlement.rs:103)
- `Code=0x0F`, `Library=0x14`, `ActorLibPin=0x15`, `EVENT_SUB=0x0E`, `EVENT_SUB_INDEX_VALUE=0x0F` and other production prefixes (not in CIP-4)
- Treasury `0x08`, Governance `0x09`, `0x1D EVENT_SUBSCRIPTION` and other system actor extensions

---

## 5. Node Repository Code Asset Inventory

### 5.1 Major Workspace Crate Maturity

| Crate | LOC (src) | Tests | Maturity |
|---|---:|---:|---|
| execution | ~32,000 (incl. cbss.rs +7,738) | **747+** | mature (most active) |
| rpc | ~19,500 (incl. cbss handlers +1,956) | 560 | mature |
| storage | ~17,500 (incl. event_subs.rs +410) | 370 | mature |
| types | ~14,100 (incl. cbss.rs +1,906) | 355 | mature |
| chain | ~7,800 | 109 | mature |
| client | ~4,300 | 142 | mature |
| cli | larger | 183 | functional (**8 TODO placeholders**) |
| proof-verifier | small | 110 | functional |
| indexer | small | 136 | functional |
| validator | binary | 0 | mature (orchestration) |
| inspector | 495 | **0** | WIP (self-labeled ALPHA) |
| dev_runner | small | 0 | functional |
| runner / ras / token | type crates | 47/27/11 | functional |

**5/26 new standalone workspace**:
- `cbss/` — 29,448 lines (cbssd daemon + cbss-crypto + cbss-client + cbss-types)

**Total tests**: ~3,000+ `#[test]` (5/15 ~2,977 → 5/26 +CBSS tests).

### 5.2 Large Files & Single-Point Complexity

- **`execution/src/cbss.rs` — 7,738 LOC (CIP-24 CBSS / DKG, 5/26 largest single file)**
- `types/src/execution.rs` — 6,445 LOC (opcode table)
- `rpc/handlers/ras.rs` — 6,841 LOC (CIP-9 RAS RPC)
- `execution/src/execution/tests.rs` — 7,503 LOC (test set)
- `execution/src/pvm_host.rs` — 3,691 LOC (host API)
- `rpc/handlers/runner.rs` — 3,510 LOC (runner RPC)
- `storage/src/speculative.rs` — 2,722 LOC (includes timer scheduling bug)

### 5.3 21+ Example Apps

| Category | Examples |
|---|---|
| **Mature** (with E2E tests) | `bridge`, `entitlements`, `multi_call`, `multisig-safe`, `token`, `proof`, `timers_demo`, `cip26_account_libraries` |
| **Functional** | `llm_chat`, `llm_session`, `llm_session_web`, `mpp_session`, `session_chain_e2e`, `governance`, `runner_dashboard`, `indexer_test`, `poison_tx_test`, `restart_test`, `ring-demo`, `passkey-wallet` |
| **Stub/WIP** | `cip28_agent_banking` (HTML mock only) |

### 5.4 Notable TODO Concentrations

| Location | Count | Notes |
|---|---:|---|
| cli/src/commands.rs | 8 | balance, nonce, account info, submission, status, block-range queries — placeholders for user-visible CLI verbs |
| examples | 7 | mostly in Solidity test scripts |
| execution | 3 | test-related or small error types |
| chain | 2 | `application.rs:114, 577` test-only min block interval |
| pvm-runtime | 1 | upstream fork |
| **result-verifier** | 1 | **`verifier.rs:291`: `// TODO: verify TEE attestation`** (CIP-23 critical gap) |

### 5.5 CIP Mention Frequency in Rust Code

Across `chain/`, `execution/`, `rpc/`, `runner/`, `ras/`, `token/`, `storage/`, `types/`, `client/`, `cli/`, `validator/`, `cbss/`:

**5/26 update**: CIP-24 (300+ new) · CIP-29 (45+ new) · CIP-3 (80) · CIP-9 (64+) · CIP-25 (64) · CIP-26 (47) · CIP-20 (45) · CIP-2 (36) · CIP-5 (11) · CIP-12 (4) · CIP-6 (1) · CIP-4 (1)

Note: CIP-1/7/8/10/11/13/14/15/16/17/18/19/21/22/23/28/31 etc. appear less frequently in code comments — consistent with their implementation degree.

---

## 6. Risks & Priority Recommendations

### 6.1 Most Urgent Code-Spec Deviations (Address Immediately)

1. **CIP-1 carry-forward bug** (`speculative.rs:751`) — over-budget timers permanently lost, **correctness issue**
2. **CIP-23 dispatcher still uses deprecated boolean filter** (`dispatcher.rs:1186`) — **security anti-pattern explicitly named by spec** still in production
3. **CIP-23 Result Verifier does not call VerifyCae** (`result-verifier/src/verifier.rs:291`) — literal `// TODO: verify TEE attestation`, **Deterministic mode in fact unverified**
4. **CIP-9 PoR `shard_inclusion_proof` hardcoded empty** (`cbfs/node/src/handler.rs:793`) — **PoR cryptographically inactive**
5. **CIP-31 storage rate off by 10×** — economic parameter should be corrected via governance
6. **CIP-8 Slash still stubbed** (`session.rs:371-380`) — returns `UnsupportedInstruction`, awaits CIP-2 dispute arbitration milestone

### 6.2 Large Structural Gaps (Ordered by Dependency)

1. **CIP-4 §12 state rent** — fully unimplemented, on-chain state growth unchecked
2. **System Actor address space `0x0D-0x13`** — blocks CIP-10/14/15/18/28
3. **Gateway HTTP edge** — blocks entire CIP-14/15/16/18/19 ingress stack
4. **CIP-10 container runtime** — runner currently in-process; all sandbox/billing/GPU work pending
5. **CIP-11 QUIC push** — still depends on 5-second job polling
6. **CIP-12 bicameral governance** — currently demo level; all Tier 0-4, Security Council, timelocks pending
7. **CIP-21/22 DeFi stack** — completely blank
8. **CIP-13 Delegation v2** — opcodes spec-side marked TBD ≥87; implementation pending

### 6.3 P0 (Highest-ROI Wrap-up, 1-3 weeks)

| Item | Effort | Payoff |
|---|---|---|
| **CIP-8 Slash wired to CIP-2 verifier-arbitration** | Medium (depends on CIP-2 dispute milestone) | CIP-8 ✅ 100% |
| **CIP-3 lane multiplier landed in code** | Small (single file) | CIP-3 → ✅ 85%; resolves lane-budget 4× deviation |
| **CIP-9 GET_MANIFEST RPC + ManifestCommitted event** | Medium (CBFS RPC wiring) | CIP-9 → ✅ 90%; unblocks entire CIP-15 family |
| **CIP-29 Phase 2 async fire complete + bid orderbook persistence** | Medium (event subsystem has foundation) | CIP-29 → ✅ 85% |
| **CIP-1 carry-forward bug fix** | Small (`speculative.rs:751` reindex) | Stops permanent timer loss |
| **CIP-23 remove deprecated boolean filter + Result Verifier calls VerifyCae** | Medium | Removes known security anti-pattern |
| **CIP-17 interface alignment** (add `block_hash`, `absent`, `prove` fields) | Small | CIP-17 → ✅ 95% |
| **CIP-20 events + `on_transfer` + hook cells cap** | Medium | CIP-20 → ✅ 95%; unblocks indexer / compliance |
| **CIP-26 events + per-call load gas** | Small | CIP-26 → ✅ 100% |

### 6.4 P1 (v2 Series Pre-Activation, 1-2 months)

| Item | Effort | Unlocks |
|---|---|---|
| **CIP-13 delegation handlers renumber to ≥87 + implement** | Large | CIP-13 Runner delegation + unlocks v2 economic model |
| **CIP-23 v2 CAE pipeline + cert chains + nonce GC** | Large | CIP-23 → 🟢 60%; unlocks truly usable Deterministic mode |
| **CIP-14 v2 RouteRegistry/GatewayRegistry/ReceiptRegistry shipped at 0x0D-0x0F** | Large | Entire CIP-14/15/16/18/19 family |
| **CIP-12 bicameral + Tier + Security Council** | Large | CIP-12 → 🟢 70%; unlocks governance usability |
| **CIP-24 Intel DCAP/TDX + AMD SEV-SNP full cert chains** | Medium | CIP-24 → ✅ 95%; v1.1 pre-mainnet ready |

### 6.5 P2 (Mid-Scale Feature Families, 2-4 months)

- **CIP-15 v2 + Gateway HTTP serving + CORS / route_manifest on-chain config** — entire CIP-15 family
- **CIP-18 PaymentGate `0x11`** — entirely spec-only, needs CIP-14/15 base
- **CIP-10 OCI container runtime** — needs OCI / cgroups / GPU integration
- **CIP-19 MCP Ingress** — invert `runner-mcp` direction + Gateway integration
- **CIP-4 §12 state rent** — full table implementation + governance keys + eviction loop

### 6.6 P3 (Ecosystem Expansion, 4+ months)

CIP-7 stream encryption / CIP-11 QUIC push / CIP-21 DEX / CIP-22 auctions / CIP-28 BankActor / CIP-31 complete rent split

### 6.7 Governance Recommendations

1. **Establish a single authoritative system actor / opcode / StatePrefix allocation table** — current drift.md has closed major conflicts; should be institutionalized as a continuously maintained doc
2. **Periodic CIP doc ↔ code drift sync** — existing `<Warning>` blocks (CIP-3, CIP-20) should be institutionalized
3. **Promote `node/docs/spikes/cip-code-audit.md` to a continuously maintained doc**
4. **Adopt WP Part II 9 Deltas** — Delta 6 landed in v2.r2; the rest should keep moving forward

---

## 7. Whitepaper Genesis Parameters vs Code — Item-by-Item

Genesis parameters locked in WP §13 + §17, item by item against code:

### 7.1 Execution

| WP Parameter | WP Value | Code Value | Status | Evidence |
|---|---|---|---|---|
| `memory_per_call` | 10 MiB | 10 MiB | ✅ | `types/src/constants.rs` |
| `storage_quota_per_actor` | 1 MiB (max 8 MiB) | same | ✅ | same |
| `reentrancy_depth` | 32 | 32 | ✅ | same |
| `fanout_per_tx` | 1024 | 1024 | ✅ | same |
| `mailbox_capacity_bytes` | 1,000,000 | 1,000,000 | ✅ | same |
| `dedup_window` | 10,000 blocks | 10,000 | ✅ | same |
| `/tmp` cap | 256 KiB | — | ❓ | not separately verified |
| recursion limit | 256 | — | ❓ | RustPython default |
| `PYTHONHASHSEED` | 0 | — | ❓ | not directly verified |
| `MAX_TIMERS_PER_ACTOR` | 1,024 (§5.1a) | 1,024 | ✅ | `constants.rs:184` |

### 7.2 Dual Basefee — §4.2 / §17.8

| WP Parameter | WP Value | Code Value | Status | Notes |
|---|---|---|---|---|
| **`T_c` (cycles target)** | **10,000,000** | **20,000,000** | ⚠️ **deviation** | `constants.rs:46` `BLOCK_CYCLES_TARGET=20_000_000` (2026-04-15 amendment) |
| `cycles cap` | 20,000,000 | — | ❓ | implemented as target |
| **`T_b` (cells target)** | **500,000** | **4,000,000** | ⚠️ **deviation 8×** | `constants.rs:50` `BLOCK_CELLS_TARGET=4_000_000` |
| `cells cap` | 1,000,000 | — | ❓ | same as above |
| **`α` (BASEFEE_ALPHA)** | **8** | **96** | ⚠️ **deviation 12×** | `constants.rs:78-108` `BASEFEE_ALPHA=96` |
| **`δ` (max change)** | **0.125 (12.5%)** | **1/96** | ⚠️ **deviation** | `BASEFEE_MAX_CHANGE_DENOM=96` (≈ 1.04%/block, smoother) |
| `MIN_BASEFEE` | 1 | 10,000 | ⚠️ **deviation** | `MIN_BASEFEE=10_000` (satisfies `MIN ≥ DENOM×100` const-assert) |
| basefee burn | 100% | 100% | ✅ | `basefee.rs:201-206` |

> **Reading**: The α/δ deviation is not a bug — code uses smoother market-update parameters (≤~1% change per block) but the **WP text has not been updated**. If WP is to govern, either fold α=96 etc. into WP or formally lock it via a CIP-3 amendment.

### 7.3 Consensus — §13

| WP Parameter | WP Value | Code Value | Status |
|---|---|---|---|
| `block_time` | 1 s | 1 s | ✅ (5/26 unified L-5) |
| `finality` | ~2 s | ~2 s | ✅ |
| `epoch` | 3600 blocks (~1h) | 3600 | ✅ |
| `unbonding_period` | 7 days | 7 days | ✅ |
| `jail_period` | 24 h | 24 h | ✅ |
| `double_sign_slash` | 1% | 1% | ✅ |
| consensus protocol | Simplex BFT | Simplex BFT | ✅ |
| validator set | self-stake only (delegation v2 deferred) | self-stake only | ✅ |

### 7.4 Dedicated Lanes — §6.3 / §17.9

| Lane | WP reserved capacity | WP period budget | Code value | Status |
|---|---|---|---|---|
| **System** | 5% | 500,000 cycles | 40,000,000 | ⚠️ 80× deviation |
| **Timer** | 20% | 2,000,000 | 8,888,890 | ⚠️ 4.4× deviation |
| **Runner** | 25% | 2,500,000 | 8,888,888 | ⚠️ 3.6× deviation |
| **User** | 50% | 5,000,000 | 22,222,222 | ⚠️ 4.4× deviation |
| Per-lane fee multiplier | 1.0× | **lane_fee_multiplier missing** | ❌ | **no `lane_fee_multiplier` symbol** |

> **Reading**: All lane budgets diverge ≥3.6× from WP (System has the largest 80× but agrees with WP — WP's 0.5M is clearly too small; the code's 40M is closer to reasonable). **This is the largest numeric drift between WP and code**. The code itself self-admits the deviation from WP §4.3 at `constants.rs:44-45`.

### 7.5 Off-Chain Compute — §13

| WP Parameter | WP Value | Code State | Notes |
|---|---|---|---|
| Committee `M`/`N` (v1 fixed) | 5/3 | 5/3 ✅ | static default matches |
| Committee `M`/`N` (v3 adaptive) | `M = clip(ceil(2·log₂(N_active) / max(HHI, 0.01)), 3, 9)` | ❌ | HHI adaptive unimplemented |
| `challenge_window` | 15 min | ✅ | `verifier.rs:27` doc |
| `challenge_bond` | 100 CBY | ✅ | implemented |
| `runner_stake_floor` | 10,000 CBY | ✅ | `dispatcher.rs:1218-1226` |
| `dispute_window_blocks` | 75 | ✅ | `constants.rs:235` |
| `reputation_half_life_blocks` | 1,209,600 (~14 days @1s) | 🟡 | event-ledger reputation system present; 14-day half-life EMA not clearly evidenced |
| `aggregator_eligibility_percentile` | 50 (p50) | ❌ | does not exist |
| **`aggregator_bonus_bps`** | **150 (1.5%)** | ❌ | **no aggregator bonus path** |
| `non_reveal_slash_bps` | 2500 (25%) | ❌ | absent |
| `slash_distribution.{burn_bps, submitter_bps, treasury_bps}` | (10000, 0, 0) | ❌ | no `SlashDistribution` struct |
| Total verification modes | 6 | 6 | ✅ |

### 7.6 State Rent — §13 / §17.5 (spec CIP-4 §12)

| WP Parameter | WP Value | Code State |
|---|---|---|
| `target_state_size` | governance-tunable | ❌ |
| `grace_period` | 7 rent-epochs | ❌ |
| `warning_period` | 3 rent-epochs | ❌ |
| `catch_up_fee` / `rent_catchup_bps` | 10% / 1000 | ❌ |
| `reserve_multiplier` | 0.1 (5 weeks equiv) | ❌ |
| `rent_rate` | 0.001 CBY/byte/year | ❌ |
| `rent_epoch_length` | 86,400 blocks (~1 day) | ❌ |
| `eviction_threshold_epochs` | 10 | ❌ |
| `grace_threshold` | 10,240 bytes (10 KB) | ❌ |
| Entire state rent subsystem | (on-chain debit + grace + eviction + restoration) | ❌ |

> **§17.5 is one of the most complete concrete subsystem specs in WP, yet code is 100% unimplemented.** WP also has a "CBY-denominated monitoring clause" requiring the Foundation to publish USD value monthly — that off-chain workflow has also not started.

### 7.7 Economics — §8 / §13

| WP Parameter | WP Value | Code/Chain |
|---|---|---|
| `supply` total issuance | 1,000,000,000 CBY | ✅ |
| `company_reserve` | 66.67% | (genesis config) |
| Inflation schedule | 8%/6%/4%/3%/2% | ❓ not verified against production code |
| `basefee burn` | 100% | ✅ |
| `runner_fee_burn` | 10% | ✅ |
| `job_fee_to_treasury` | 1% | ✅ |
| `runner_payout` | 89% | ✅ |
| Slashed stake → burn | 100% | ✅ (HOLD path) |

### 7.8 Data Availability — §7

| WP Parameter | WP Value | Code |
|---|---|---|
| `Inline blob cap` | 64 KiB | ✅ |
| On-chain commitment | multihash | ✅ |

### 7.9 Key WP-Locked Items Inconsistent With Code (one-line summary)

- **`T_c` 10M vs code 20M** (target)
- **`T_b` 500K vs code 4M** (target, 8× deviation)
- **`α=8` vs code 96** (12× deviation)
- **`δ=0.125` vs code 1/96** (smoother)
- **Lane budgets** WP vs code diverge ≥3.6× across the board
- **Lane fee multiplier** WP explicit 1.0× per lane, code lacks the symbol
- **State Rent** WP §17.5 full table is 0% in code
- **Aggregator bonus 1.5%** WP §13 + §8.4 hardcoded; code unimplemented
- **System actor 0x1D** absent from WP §9; code-side new (CIP-29 host-intercepted virtual activation model)

---

## 8. Whitepaper Part II Nine Deltas — Implementation Status

Part II contains 9 forward-looking v2 proposals (Delta 6 has been adopted into WP v2.r2 main body; the rest remain proposals).

| Delta | Topic | Status | Notes |
|:---:|---|---|---|
| **1** | Gateway stake / operating balance separation | ❌ 0% | CIP-14 v2 pending activation |
| **2** | Route CORS priority + Read-only handler as protocol primitive | 🟡 — runner-side separation implicit; PVM read-only + trap table shipped but endpoint path not aligned | CIP-15 v2 / CIP-14 v2 pending activation |
| **3** | Deferred-result storage pattern (`RECEIPT_REGISTRY` shared pruning loop) | ❌ 0% | `0x0F` unassigned, CIP-14 v2 §8 |
| **4** | TEE three-tier chain (system reserved selectors + CAE) | 🟡 25% → 30% | CIP-23 signature verify skeleton present; CAE / cert chains / nonce still missing; TEE keys ops 60-63 driven by CIP-24 landing |
| **5** | STORAGE_MANAGER holds actor config (route_manifest / cors_config) | ❌ 0% | CIP-15 v2 §4.1 pending activation |
| **6** | §9 table fix + v2 address band (0x0A = STORAGE_MANAGER) | ✅ **adopted into v2.r2** | This session added status column + new `0x1D` row |
| **7** | Payments (PaymentGate `0x11`, MPP+x402, 4 models) | ❌ 0% | CIP-18 r2 pending activation |
| **8** | MCP Ingress (actor as MCP server) | ❌ 0% | CIP-19 pending activation, needs CIP-14/15/18 base |
| **9** | Cross-Chain L1+L2+L3 | 🟢 60% | CIP-25 Cowboy↔Ethereum demo bridge functional, runner-committee backend deployed |

### 8.1 Delta Implementation Groups

- **Landed**: Delta 6 (adopted in v2.r2), Delta 9 (CIP-25 ~60%)
- **Partially landed**: Delta 2 (PVM read-only), Delta 4 (CIP-23 signature verify + TEE keys ops)
- **Fully unimplemented**: Delta 1, 3, 5, 7, 8

### 8.2 Delta 7-8 (Payments + MCP) — Platform Monetization Foundation

Delta 7 (PaymentGate) and Delta 8 (MCP Ingress) together form the "actor monetization" core architectural layer. WP v1 had neither layer; Delta 7-8 are new directions to let the Cowboy platform interface with the AI-agent economy.

**Current blocker**: Delta 7 depends on `0x11`; Delta 8 depends on Gateway (CIP-14/15) + Delta 7. Entire chain at 0% in code.

### 8.3 Delta 9 — Cross-Chain Architecture and Tension With §16

WP §16.2 explicitly says: "Cowboy relies on third-party bridge infrastructure ... the protocol does not implement its own bridge validator set." But CIP-25 (+ Delta 9) proposes a **runner-attested committee** as L1 backend, which is in effect **a protocol-level bridge validator set** (though it reuses CIP-2's Runner Registry).

Delta 9's resolution: **WP §16.2's "no protocol validator set" should be read narrowly as "no single mandatory bridge validator set"**; CIP-25's `IChainAnchor` allows third-party and Cowboy-runner backends to coexist.

The code has shipped the runner-committee path (`examples/bridge/` complete Cowboy↔Ethereum, includes `JobType::PublishChainRoot`, Anchor_C, `CowboyLightClient.sol`, L2 Mailbox, L3 asset bridge); facts ahead of docs. WP needs to adopt Delta 9 to remove self-contradiction.

---

## 9. Items Unchanged Since 5/15 Audit

The following CIPs have not significantly changed status since 5/15; this audit reuses prior conclusions:

- **Unchanged ❌ 0%**: CIP-10 / CIP-11 / CIP-13 / CIP-16 / CIP-18 / CIP-19 / CIP-21 / CIP-22 / CIP-28
- **Unchanged 🟠 5-25%**: CIP-1 / CIP-7 / CIP-14 / CIP-15 / CIP-31
- **Unchanged 🟢/✅**: CIP-2 / CIP-3 / CIP-4 / CIP-5 / CIP-6 / CIP-17 / CIP-20 / CIP-25 / CIP-26

For detailed analysis, refer back to [`2026-05-15_CIP_IMPLEMENTATION_AUDIT_CN.md`](./2026-05-15_CIP_IMPLEMENTATION_AUDIT_CN.md) §2, §3, §6.

---

## 10. Conclusion

The codebase is overall in a **trunk-capability complete, surrounding-ecosystem-pending, cryptographic-infrastructure-greatly-advanced** stage. Two most significant 5/26-over-5/15 surprises:

### 10.1 Two Breakthroughs

1. **CIP-24 (CBSS) from not-listed in 5/15 audit to 5/26 ~80%** — 41,000+ lines of code (node 11.6K + cbss workspace 29.4K), one of the most complex single subsystems today. All 21 handlers implemented, standalone daemon `cbssd` + complete crypto library (BLS12-381 threshold IBE + DKG + proxy registry + release receipt + liveness + reshare + forced deregister). Only Intel DCAP/TDX and AMD SEV-SNP full cert-chain verification deferred to pre-mainnet milestone.

2. **CIP-29 from <5% to 55%** — Event Hooks implemented complete Phase 1 + Phase 2 framework in 11 days. `0x1D` virtual actor + 3 read RPCs + sync/async fire + EmitOrigin DeferredTx pattern all in code. Introduces a protocol-level new activation pattern (host-intercepted virtual actor), coexisting with traditional deployment-type system actors (`0x01-0x0F`).

### 10.2 Overall Trends

- ✅/🟢-level CIP count rose from 12 to 13 (CIP-29 upgraded + CIP-24 entered the list)
- ❌-level CIP count holds at 9 (departing items balanced by new challengers)
- Average completion rose from ~40% to ~45%

### 10.3 Mature (Production Grade)

CIP-2 (off-chain compute), CIP-5 (timers), CIP-6 (SDK), CIP-8 (MPP Session, only Slash stubbed), CIP-20 (tokens), CIP-25 (cross-chain bridge demo), CIP-26 (account libraries).

These CIPs all have complete implementation + test coverage + end-to-end examples, and align with WP Part I descriptions.

### 10.4 Nearing Completion (🟢, Recommend Wrap-up)

CIP-3 (fee model — lane multiplier missing), CIP-4 (state rent §12 missing), CIP-9 (PoR economics missing), CIP-17 (interface name differences), CIP-24 (vendor collateral only), CIP-29 (async fire completion).

### 10.5 Completely Blank or Demo Only

CIP-1 v3, CIP-7, CIP-10, CIP-11, CIP-13, CIP-14, CIP-15, CIP-16, CIP-18, CIP-19, CIP-21, CIP-22, CIP-28, CIP-31, and CIP-12's bicameral/Council layer, WP Part II Delta 3/5/7/8.

### 10.6 Three-Layer (WP / CIP / Code) Drift Management

This audit has established a stable workflow:

- `wiki/drift.md` tracks in-progress drifts (C-1 ~ C-4 + L-5 closed this period)
- `refs/cips/cip-13-runner-delegation.md` §1 as the code-authoritative opcode master table
- `refs/wiki/entities/system-actors.md` as the code-authoritative system actor table
- Every cross-CIP revision appends a `wiki/log.md` chronological entry

**1. WP ↔ Code drift**: α=8/96, lane budgets ≥3.6×, `T_b` 8× deviation, State Rent 100% unimplemented, Lane fee multiplier symbol missing, `0x1D` virtual actor pattern absent from WP.

**2. WP ↔ CIP drift**: Delta 6 landed (§9 table fix); Delta 9 tension with §16.2 awaiting WP formal adoption.

**3. CIP ↔ Code drift** (closed 5/26): CIP-28 0x0D→0x13, CIP-29 0x0A→0x1D, CIP-13 v2 opcodes marked TBD ≥87, CIP-9 §13 AMEND 9-J completed.

### 10.7 Next Audit Recommendation

In 4-6 weeks, do the next baseline; focus on:
- **CIP-13 v2** implementation progress (after opcodes renumber to ≥87)
- **CIP-23 v2** CAE pipeline + cert chains
- **CIP-14 v2** RouteRegistry/GatewayRegistry/ReceiptRegistry shipping at `0x0D-0x0F`
- **CIP-24** Intel DCAP/TDX + AMD SEV-SNP full cert-chain vendor collateral

---

**End of report**

> This report is based on the 2026-05-26 code state and Whitepaper v2.r2 (2026-05-11 update). The cited `file:line` references are accurate at that time; subsequent refactors may change them.
> Whitepaper reference: `refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md` (Part I v1 / Part II 9 Deltas / Part III alignment audit brief).
> Per-item probe evidence for this audit is traceable in `wiki/log.md` 5/26 lint+ingest and enhance entries.
> Raw output from the 6 parallel sub-agents is available on request.
