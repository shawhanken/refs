# Runner-Related Issue Triage (pavilionledger / unassigned, uncompleted)

**Date:** 2026-06-11
**Source:** Linear team COW. Filter = assignee ∈ {pavilionledger, none} AND state ∉ {completed, canceled}.
**Pool:** 729 uncompleted issues → **67 runner-subsystem issues** after project + title filtering.

## Scope definition

"Runner-related" = the off-chain compute runner subsystem and its on-chain counterparts:
CIP-2 (verifiable off-chain compute, dispatcher/verifier/registry/slashing), CIP-8 (MPP
sessions), CIP-9 (CBFS-backed runner storage / relay), CIP-10 (container runtime — **project
Canceled**), CIP-11 (runner↔validator connectivity & push delivery), CIP-23 (TEE execution &
composite attestation), plus runner-tagged items in CIP-25 (cross-chain runner roles), CIP-16
(DNS-job runner wiring), CIP-18 (bridge-facilitator runner role), and Node Hardening.

**Excluded** (share keywords but different subsystem): CIP-19 gateway MCP ingress, CIP-14/16
gateway/DNS routing, CIP-24 CBSS, CIP-17 state-read RPC, consensus/whitepaper, DEX, payments
core, governance.

> ⚠️ Scope caveat: a large share of this list is **CIP-2 family** (CIP-2/8/10/11/23), which per
> team-scope notes has historically been another team's domain. Confirm ownership before picking
> these up. The CIP-9 (storage) and security/observability items are the safest "ours".

---

## Tiers (easy → hard)

### Tier 1 — Docs / spec clarifications & one-liners (hours, near-zero risk) — 6
| ID | State | Title | Note |
|----|-------|-------|------|
| COW-1009 | Backlog | Document deferred `SessionStatus::Slashed` variant | add TODO + spec note |
| COW-1008 | Backlog | Clarify `SessionStatus::Disputed` fields | decision + spec/code comment |
| COW-1012 | Backlog | Pin production `COWBOY_SESSION_CHAIN_ID` | constant + 2 call sites + startup assert |
| COW-2117 | Backlog | Registrar must require x25519 before `storage_support` | author calls it "one-liner-ish" footgun fix |
| COW-606 | Backlog | Unbounded hex decode in runner (`job_id`) → OOM | require 64 hex chars before decode; security:low |
| COW-1013 | Backlog | Extend `Disputed` with `opened_at: u64` | small, but **blocked** on Slash-milestone design |

### Tier 2 — Small bounded fixes / validation (≤1 day, localized) — 7
| ID | State | Title | Note |
|----|-------|-------|------|
| COW-1373 | Backlog | §3 full JobSpec validation (bounds≠0, max_price>0, timeout>0) | only `runners==0` enforced today |
| COW-1376 | Backlog | §8 verify runner Ed25519 sig over `result_bytes` on reveals | reveal sig currently ignored |
| COW-2118 | Backlog | Structured `InsufficientStorageCapableRunners` dispatch error | replace opaque `InsufficientRunners` |
| COW-1540 | Backlog | OpenSession "runner is registered" precondition | add registry lookup in `session.rs` |
| COW-2116 | Backlog | Wire runner deregister/re-register E2E | impl handler (refund stake) + CLI verb |
| COW-1712 | Backlog | Wire `execute_dns_job` into runner worker loop | code exists, just not called in binary |
| COW-425 | Backlog | Observability: runner job tracker | **no description — needs scoping** |

### Tier 3 — Moderate features / tests / wiring (a few days) — 13
| ID | State | Title | Note |
|----|-------|-------|------|
| COW-1011 | Backlog | Session integration tests → full E2E flow | tests |
| COW-937 | Backlog | CIP-9 integration tests (manifest round-trip, access modes, cache) | tests |
| COW-1541 | Backlog | Emit real chain events (SessionOpened/Deposited/…) | currently only `info!` logs |
| COW-1543 | Backlog | Runner session bootstrap: chain-event subscriber (replace PoC HTTP push) | runner side |
| COW-933 | Backlog | Multi-source relay registry refresh + background fetch | availability |
| COW-1542 | Backlog | `SessionAsset::Cip20` token-escrow path | currently rejected `UnsupportedInstruction` |
| COW-1308 | Todo | CIP-2 v3 end-to-end economic example/case study | demo of full job→settle→slash flow |
| COW-1605 | Backlog | §8.4 Registry-order bitmap indexing as of parent block | dispatcher data |
| COW-1606 | Backlog | §9.1 Dispatcher Presence filter (Filter 1.5) | new filter in selection chain |
| COW-1608 | Backlog | §9.4 Dispatcher MRU state read path (`mru_key`) | new state |
| COW-1609 | Backlog | §9.4 Result Verifier MRU write path | pairs with 1608 |
| COW-1614 | Backlog | §10.6 Dispatch Outcome classification + presence floor | state machine |
| COW-1615 | Backlog | §11.1 Per-dispatch ACK_TIMEOUT → clear presence | depends on push delivery |

### Tier 4 — Substantial subsystems / economics / state machines (~1–2 weeks) — 8
| ID | State | Title | Note |
|----|-------|-------|------|
| COW-962 | Todo | Dispute window: on-chain challenge/evidence/re-verification handler | new system path |
| COW-2109 | Todo | Activate 50/30/20 slash split + challenger payout + fix split inconsistency | economics; spec §6 vs §10 contradiction |
| COW-2111 | Todo | USD-pegged runner stake floor | **depends on oracle**; TWAP/grace/epoch logic |
| COW-929 | Backlog | Relay registry: `relay_identity_pubkey` + chain-verified handshake | closes TOFU trust loop |
| COW-2115 | Backlog | Wire owner-auth signing to canonical encoding + cross-lang vectors | CIP-9 W5; signing-bytes correctness |
| COW-2183 | Backlog | CBFS Proof-of-Retrievability challenge/response + PoR-miss slashing | whole economic layer, not in code |
| COW-1591 | Backlog | §4.1/§10.1 Push job delivery (validator pushes JobAssignment) | replaces pull loop |
| COW-1611 | Backlog | §10.3 JobResult streamed back on job stream + sig | depends on push transport |

### Tier 5 — Hard: crypto / cross-chain / transport / cross-team (multi-week, often blocked) — 23
**TEE / Composite Attestation (CIP-23) — 16** (heavily interdependent, crypto-heavy, severity:high):
COW-957 (full SGX/SEV-SNP/TDX/Nitro pipeline — currently a stub), COW-1098 (CAE envelope + D-CBOR),
COW-1099 (REPORTDATA binding rule), COW-1100 (TEE Verifier 0x05 opcodes 57–60 + state),
COW-1101 (8-step verify_cae pipeline), COW-1102 (MeasurementBinding + registry ext),
COW-1103 (attestation-first registration cross-call), COW-1107 (TDX/SNP/Nitro quote parsers),
COW-1108 (root-cert registry + governance delay), COW-1110 (FreshnessAnchor + replay),
COW-1111 (NVIDIA NRAS GPU attestation), COW-1301 (BillingAttestation CAE freshness; Bug),
COW-1309 (`tee_call` SDK helper), COW-1847 (Secrets-Manager get_secret TEE-gating),
COW-1849 (execute-in-TEE body — stub), COW-1850 (CIP-13 delegation × measurement binding).

**Cross-chain runner (CIP-25) — 4:** COW-1114 (runner-committee 2-of-3 verifier),
COW-1119 (reorg-detection daemon + commitment_revoked), COW-1120 (per-chain min_confirmations),
COW-1122 (`generate_inclusion_proof` job type).

**Transport (CIP-11) — 2:** COW-1590 (persistent QUIC+TLS1.3 control connection),
COW-1622 (QUIC+TLS replacing plaintext HTTP job content).

**Bridge (CIP-18) — 1:** COW-1184 (EVM bridge-facilitator runner role + BridgeEvidence).

### Parked — CIP-10 Container Runtime (project **Canceled**) — 10
Full container subsystem; **project is canceled**, so likely not actionable — verify before any work.
COW-1570 (exit-code→status map), COW-1571 (OffchainTask.runtime_config), COW-1572 (Container
Registry actor), COW-1576 (BillingAttestation struct), COW-1577 (attestation settlement),
COW-1581 (clean container env), COW-1584 (actor addr 0x10), COW-1585 (ContainerSettlementConfig),
COW-1586 (three-flow escrow), COW-1587 (BillingAttestation.tee_signature).

---

## Quick recommendation
Start at **Tier 1 → Tier 2** for fast, low-risk wins (esp. CIP-9 ones COW-2117/2116/2118 and
security COW-606, which are clearly in-scope and not blocked). Treat the **CIP-23 TEE cluster** as
one coordinated epic, not 16 independent tickets (deep dependency chain: CAE struct → freshness →
binding → verifier opcodes → pipeline → registration). Confirm CIP-2-family ownership and the
CIP-10 cancellation status before committing to Tiers 4–5.
