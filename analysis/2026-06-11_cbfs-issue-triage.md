# CBFS-Related Issue Triage (pavilionledger / unassigned, uncompleted)

**Date:** 2026-06-11
**Source:** Linear team COW. Filter = assignee ∈ {pavilionledger, none} AND state ∉ {completed, canceled}.
**Pool:** 729 uncompleted issues → 89 title-keyword candidates → **53 core CBFS** (+ a borderline appendix).

## Scope definition

"CBFS-related" = the distributed encrypted erasure-coded storage subsystem (CIP-9 RAS, the former
*steamtrain*): the `cbfs/` repo (auth/crypto/erasure/manifest/placement/fuse/node/store/transport/
sdk), the on-chain Storage Manager (`0x0A`) / Relay Registry (`0x0B`) + RAS handlers in `node/`,
the gateway CBFS read path (`gateway-cbfs`), relay PoR/economics, and owner/relay auth.

**Counted as core** even when filed under "Node Hardening": the gateway-cbfs manifest/shard read
family (879/884/887/892/893/900) — it *is* the CBFS read path.

> ⚠️ **Overlap with runner triage:** CIP-9 is "CBFS-**backed runner** storage", so 8 issues appear
> in **both** this list and `2026-06-11_runner-issue-triage.md` (COW-929, 933, 937, 2115, 2116*,
> 2117, 2118, 2183). They are runner⇄storage seam items. (*2116 lives in runner triage only.)

> ℹ️ **Adjacent but excluded** (separate subsystem; see appendix): node blob/DA layer (WP §7,
> COW-1252–1258/1228), CIP-30 per-actor storage-root (1275/1277/1281/1282), PvmHost actor-KV
> quota/logging (95/137/175/202), CIP-4 actor-state rent. These are "storage" but *not* CBFS files.

---

## Tiers (easy → hard) — 53 core

### Tier 1 — Docs / spec & trivial one-liners (hours, near-zero risk) — 4
| ID | Sev | Title | Note |
|----|-----|-------|------|
| COW-941 | — | Remove Steamtrain references from CIP-9 title | doc/rename; Charles requested |
| COW-940 | low | Resolve CBFS Phase-2 open questions (PoD freq, scoring weights, clock skew) | pick values + write into code/spec |
| COW-935 | low | Wire node `capacity_bytes` to config (hardcoded 0) | read config + CLI flag |
| COW-2117 | — | Registrar require x25519 before `storage_support` | author: "one-liner-ish" footgun (shared w/ runner) |

### Tier 2 — Small bounded fixes / validation (≤1 day, localized) — 8
| ID | Sev | Title | Note |
|----|-----|-------|------|
| COW-923 | high | Strict SDK read mode (no placement-address fallback) | **security**: malicious placement → attacker relay |
| COW-2095 | — | (owner,name)→volume_id resolution broken (404) | bug; repair owner-domain read path |
| COW-2096 | — | Mount-allowlist principal ambiguous (Account vs Actor) | bug; unify principal model |
| COW-2011 | — | Prefix-overlap rejection on write-token issuance | add overlap check at issuance |
| COW-2118 | — | Structured `InsufficientStorageCapableRunners` error | replace opaque error (shared w/ runner) |
| COW-2094 | — | Wipe relay sled stores on re-genesis + logrotate | ops; stops repair churn / disk-fill crash-loop |
| COW-887 | — | GET_SHARD RPC client + K-shard reconstruction fallback | client read path |
| COW-922 | high | Public-read short-circuit on GetPlacement + GetShard | partial today; finish public-read auth |

### Tier 3 — Moderate features / tests / wiring (a few days) — 24
**Read path / manifest & shard (10):**
COW-886 (GET_MANIFEST RPC client), COW-920 (GetManifest Relay RPC — AMEND 9-G),
COW-2120 (GET_MANIFEST relay server assembly+cache), COW-894 (ManifestCommitted event subscription),
COW-921 (emit ManifestCommitted chain event — AMEND 9-H), COW-914 (commit events silently lost via
`put-many` — **data-loss bug**), COW-884 (per-volume metadata cache), COW-892 (replace HttpCbfsClient
prototype), COW-893 (MANIFEST_POLL_INTERVAL refresh loop), COW-900 (hedged parallel shard fetch),
COW-879 (storage-status-driven volume serving).

**Auth & client UX (6):** COW-925 (`cbfs auth setup/rotate/revoke/...` CLI), COW-926 (signed request
envelope on all `/ras/` endpoints), COW-928 (OwnerCapTokenV1 validation path; removes 2 `panic!`),
COW-931 (CLI connection pooling), COW-932 (volume-meta + token caching), COW-933 (multi-source relay
registry refresh — shared w/ runner).

**Tests & hardening (3):** COW-934 (convert 34 prod `panic!/unimplemented!/todo!` → typed errors),
COW-936 (tests for 12 zero-coverage packages: crypto/erasure first), COW-937 (CIP-9 integration tests
— shared w/ runner).

**Ops / migration / SDK (5):** COW-2181 (manifest-shard gap migration CLI), COW-2182 (NodeSelector
region/operator/health diversity), COW-2185 (turnkey owner-token refresh for FUSE), COW-2186
(Prometheus metrics for Gateway + RAS), COW-987 (SDK `runtime.mount(volume_id, access_mode)`).

### Tier 4 — Substantial subsystems / auth / economics (~1–2 weeks) — 11
| ID | Sev | Title | Note |
|----|-----|-------|------|
| COW-924 | high | Direct RAS+QUIC reader replacing HTTP wrapper | production gateway client (metadata→strict set→QUIC→verify) |
| COW-929 | med | Relay registry: `relay_identity_pubkey` + chain-verified handshake | closes TOFU trust loop (shared w/ runner) |
| COW-930 | med | Cowboy-mode `cbfs mount` token-refresh (design + impl) | currently errors by design; pick architecture |
| COW-2115 | — | Wire owner-auth signing to canonical encoding + cross-lang vectors | signing-bytes correctness (shared w/ runner) |
| COW-2152 | — | Validate `per_relay_effective_deltas` at commit | **security**: CapToken holder can rewrite whole manifest_root |
| COW-1545 | — | `reserve_storage_balance` / `get_storage_usage` owner API | RAS route surface gaps |
| COW-2009 | — | RELAY_UNSTAKE_DELAY 7,200-block cooldown after drain | economic layer; field exists, gate unwired |
| COW-2010 | — | Fee components (VOLUME_CREATION/ATTACHMENT/TRANSFER) | only rent charged today |
| COW-2180 | — | Concurrent drain coordination (destination token-bucket) | anti-thundering-herd on drain |
| COW-2184 | — | Full relay rewards distribution (pro-rata shard×age) | only drain-completion payout today |
| COW-2205 | sec | Harden cowboy-ras-write-relayer distribution (signing + S3 immutability) | **security**; follow-up to COW-2188/#648 |

### Tier 5 — Proof-of-Retrievability + economic enforcement (hard, soundness-critical, multi-week) — 6
Treat as **one coordinated epic** — deep dependency chain, crypto soundness + slashing economics,
**nothing in code today** (zero refs to `por_challenge`/`PorChallenge`).
| ID | Sev | Title |
|----|-----|-------|
| COW-2112 | — | PoR per-shard chunk-roots + shard_root + challenge nonce (commitment foundation) |
| COW-917 | high | PoR on-chain mechanism: `por_challenge` instruction at `0x0B` + bonds |
| COW-918 | high | Spot-check responder: byte-range read + Merkle `byte_range_proof` |
| COW-919 | high | PoR challenge timer via CIP-5, `fee_payer = STORAGE_MANAGER` |
| COW-2007 | — | On-chain PoR challenge loop + constants (interval/window/penalties) |
| COW-2183 | — | PoR challenge/response + PoR-miss slashing, end-to-end (challenger bounty) |

---

## Quick recommendation
- **Fast wins (in-scope, not blocked):** Tier 1 (941/940/935/2117) + Tier 2 bug/security fixes
  (923, 2095, 2096, 2152→but that's T4). Start with COW-923 (placement-fallback redirect) and the
  two `mesa` bring-up bugs COW-2095/2096 — small, high operator value.
- **Coherent epics, plan as units, don't ticket-by-ticket:** the **PoR/economics** cluster
  (Tier 5 + COW-2009/2010/2184) and the **manifest/shard read-path** cluster (Tier 3 read group).
- **Security cluster worth batching:** COW-923, 2152, 2205, 926, 929 (auth/trust hardening).
- The CIP-9 ⇄ runner seam (929/933/937/2115/2117/2118/2183) overlaps the runner triage — sequence
  with whoever owns runner work to avoid double-effort.

---

## Appendix — Adjacent "storage" issues (NOT counted as CBFS; pull in if scope widens)

**Node blob / DA layer (WP §7) — 8:** COW-1252 (retitle: no separate DA layer; all blobs are CBFS),
COW-1253 (enforce 64 KiB inline blob cap), COW-1254 (two-tier inline-vs-CBFS pricing), COW-1255
(blob-commit cycles metering), COW-1256 (align CIP-4/CIP-9 rent epochs), COW-1257 (blob lifecycle
TTL/pruning), COW-1258 (blob lifecycle integration tests), COW-1228 (reconcile STORAGE_EPOCH_BLOCKS
7200 vs 86400). → These are the *node* blob path that anchors >64 KiB to CBFS; arguably in-scope if
you own the blob↔CBFS seam.

**CIP-30 per-actor storage root — 4:** COW-1275/1277/1281/1282. → Actor *state* Merkle root, not
CBFS files.

**PvmHost actor-KV storage — 4:** COW-95/137/175/202 (quota/batch-read/size-tracking/access-log). →
Actor key-value store, unrelated to CBFS.

**Misc storage-keyword (excluded):** COW-363 (secrets CLI), 379/434 (SDK storage stubs), 1003
(CIP-7 ingestion→encrypt→publish), 1065 (CBSS storage-prefix doc), 1117 (cross-chain fee), 1133/1271
(doc/traceability), 1150 (event-sub entitlement gating), 1573/1637/1660/1846 (other-CIP storage
refs), 2056 (C-ABI cross-VM), 2203 (CIP-31 ras-constant propagation — could fold into Tier 4),
2209 (Builder: "see/edit your CBFS files" UX — vague, needs scoping).
