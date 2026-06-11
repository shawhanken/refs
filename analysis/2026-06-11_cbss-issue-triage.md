# CBSS-Related Issue Triage (pavilionledger / unassigned, uncompleted)

**Date:** 2026-06-11
**Source:** Linear team COW. Filter = assignee ∈ {pavilionledger, none} AND state ∉ {completed, canceled}.
**Pool:** 729 uncompleted → 47 title-keyword candidates → **24 core CBSS**.

## Scope definition

"CBSS-related" = the Cowboy Secret Service (CIP-24): threshold-IBE / DKG secret release — `cbssd`
daemon (`runner/crates/cbssd`), `cbss-client`, `cbss-crypto` (BLS/IBE), `cbss-types`, plus the
on-chain CBSS handler (`node/execution/src/cbss.rs`), Secrets-Manager system actor (`0x94`), and
RPC (`node/rpc/src/handlers/cbss.rs`). Most items are from the **v1.1 DoD audit** (`v1.1-DOD-*`).

> ⚠️ **Overlap / seam:** COW-1847 (Secrets-Manager `get_secret` TEE-gating) and COW-1051 (TEE
> vendor-quote chain-of-trust) sit on the **CBSS ⇄ CIP-23 TEE** seam — 1847 also appears in the
> runner triage Tier 5. They're blocked on / share the TEE attestation pipeline.

> ℹ️ **Excluded** (matched "secret/threshold/envelope/BLS/release" but different subsystem):
> CIP-29 event hooks (1148/1149/1152/1920), CIP-22 auction *release-schedule* (1194/1197/1807),
> CIP-19/16/14 *Http**Envelope*** (1680/1721/1778/1780), CIP-11 frame envelope (1595/1604/1617),
> CIP-25 light-client BLS (1898), CIP-2 reveal sig (1376/1378), CIP-18 PaymentGate (1178),
> CBFS signed envelope (926), secrets CLI (363).

---

## Tiers (easy → hard) — 24 core

### Tier 1 — Docs / comments / one-liner KV-cleanup (hours, near-zero risk) — 8
| ID | Sev | Title | Note |
|----|-----|-------|------|
| COW-1059 | med | Liveness index key cleanup on expire/response | add `delete_key` calls — KV-bloat fix, ~one-liner |
| COW-1070 | low | Document residual H8 blocker prominently | warning comment at Commonware dep in `Cargo.toml` |
| COW-1065 | low | CBSS storage-prefix documentation block | list reserved sub-keys; xref `state_key.rs` |
| COW-1066 | low | Operator-level Sybil-defense documentation | comment block on committee-dedup invariant |
| COW-1069 | low | Modulo-bias note in `weighted_proxy_position` | comment (bias negligible at u128) |
| COW-1064 | low | DOD-01 aggregate cargo log | tooling: one command → DoD artifact |
| COW-1060 | low | AAD endianness consistency | decide A (doc as wire-stable) / B (standardize BE) |
| COW-1068 | low | HPKE/DKG pubkey curve-membership check | add check **or** document safe-to-skip |

### Tier 2 — Small bounded bug-fixes / codec tightening / tests (≤1 day) — 7
| ID | Sev | Title | Note |
|----|-----|-------|------|
| COW-1061 | med | Tighten ACL codec cap to 64 at **decode** | fail-closed; `MAX_ACL_ACTORS` 1024→64 |
| COW-1067 | med | TEE expiry off-by-one boundary audit | confirm inclusive/exclusive + 3 boundary tests |
| COW-1056 | med | Release-receipt `release_id` collateral fields + GC | add `serve_epoch`; expire stale sets (bound KV) |
| COW-1062 | high | RPC pagination on `GET /cbss/proxies` | `?offset/limit` + tighten pubkey codec; multi-MB resp today |
| COW-1063 | med | Handler 404/410/409 branch tests | tombstone-vs-not-found-vs-pending coverage |
| COW-1058 | med | Liveness health-score attrition rate limit | cap `max_health_loss_per_epoch_bps` (anti-drain) |
| COW-1055 | high | Pin Commonware branch as protected annotated tag (H8) | **out-of-repo** action; supply-chain pin (rewritable today) |

### Tier 3 — Moderate features / test-harness restoration / persistence (a few days) — 5
| ID | Sev | Title | Note |
|----|-----|-------|------|
| COW-1050 | high | Restore lost §5.9 spawned-DKG e2e suite (DOD-04) | 3 e2e tests dropped in a merge; rebuild harness |
| COW-1052 | med | Real-validator stress test (DOD-08) | swap wiremock → spawned-validator fixture |
| COW-1054 | med | Real-validator scenario matrix (DOD-05/07) | 5 cbssd-spontaneous scenarios on live devnet |
| COW-1057 | med | DKG sabotage evidence provable post-rotate | **security**: persist `DkgCeremonyRecord` so dealer stays slashable |
| COW-2212 | — | add CBSS support | **no description — needs scoping** (likely client/SDK integration) |

### Tier 4 — Substantial crypto / adversarial harness / TEE-gated paths (~1–2 weeks) — 4
| ID | Sev | Title | Note |
|----|-----|-------|------|
| COW-1053 | med | Fake-cbssd binary serving forged σ_i over QUIC (DOD-09) | adversarial test binary + QUIC adapter; expects `cbss.proxy.slashed` |
| COW-1051 | high | TEE vendor-quote chain-of-trust (DOD-07-TEE) | Intel DCAP (PCK/TCB/QE/CRL) + AMD VLEK cert chains — **shares CIP-23 TEE work** |
| COW-1546 | — | Secrets-Manager direct sealed-DEK fetch path (v2 §9.2) | replace dispatcher-mediated delivery; v1 only today |
| COW-1847 | — | Secrets-Manager `get_secret(attestation)` TEE-gating | cross-call VerifyCae + allowed_measurements + HPKE delivery — **blocked on CIP-23 pipeline** (also runner Tier 5) |

---

## Quick recommendation
- **Fast, safe wins:** nearly all of Tier 1 + Tier 2 are self-contained `cbss.rs`/RPC fixes from the
  v1.1 DoD audit with crisp acceptance criteria — ideal batch. Start with the **bounded-growth /
  fail-closed** cluster (1059, 1061, 1056, 1062) and the security-relevant ones (1058, 1057).
- **Decision-only tickets (cheapest):** 1060/1068/1069 just need a recorded A-vs-B decision — clear
  these in one pass with whoever owns `cbss-crypto`.
- **Supply-chain:** COW-1055 + COW-1070 are the same H8 Commonware-pin hazard — do them together
  (one is the fix, one is the interim warning).
- **Test-harness epic:** 1050/1052/1053/1054 all rebuild the spawned-validator / adversarial e2e
  matrix — plan as one harness effort, not four tickets.
- **Hold for TEE:** 1051/1847 depend on the CIP-23 composite-attestation pipeline (runner Tier 5).
  Don't start them before that pipeline lands or you'll stub against a moving target.
