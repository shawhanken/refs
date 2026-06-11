# Runner ⇄ CBFS ⇄ CBSS — Seam & Overlap Map

**Date:** 2026-06-11
**Companion to:** `2026-06-11_{runner,cbfs,cbss}-issue-triage.md`
**Purpose:** flag issues that touch >1 subsystem (or share a system actor / code path) so they're
sequenced once, not implemented twice by parallel owners.

**Set sizes:** runner = 67, CBFS-core = 47, CBSS-core = 24. Direct overlaps = 8.
**Distinct union = 130 issues.**

---

## A. Direct overlaps — the *same* issue appears in two triages (8)

### A1. runner ∩ CBFS — "CBFS-backed runner storage" seam (7)
CIP-9 makes the runner a storage provider, so these are genuinely dual-subsystem. **Own them once.**
| ID | Sev | Title | Seam |
|----|-----|-------|------|
| COW-2117 | — | Registrar require x25519 before `storage_support` | runner registration ↔ relay eligibility |
| COW-2118 | — | Structured `InsufficientStorageCapableRunners` dispatch error | runner dispatcher ↔ storage capability gate |
| COW-937 | med | CIP-9 integration tests (manifest round-trip, access modes) | runner test harness ↔ CBFS contract |
| COW-933 | low | Multi-source relay registry refresh + background fetch | runner client ↔ CBFS relay registry |
| COW-929 | med | Relay registry `relay_identity_pubkey` + chain-verified handshake | runner/node registry ↔ CBFS relay trust |
| COW-2115 | — | Owner-auth signing → canonical encoding (registry-proto) | runner-signed ops ↔ CBFS owner-auth |
| COW-2183 | — | PoR challenge/response + PoR-miss slashing (end-to-end) | runner-as-relay slashing ↔ CBFS PoR |

> Also seam-adjacent but in **runner triage only** (no storage keyword in title, so missed by the
> CBFS keyword pass): **COW-2116** "[Runner/Node] Wire runner deregister/re-register" — a CIP-9
> v2-refactor item; treat it with this cluster.

### A2. runner ∩ CBSS — TEE secret-gating seam (1)
| ID | Title | Seam |
|----|-------|------|
| COW-1847 | Secrets-Manager `get_secret(attestation)` TEE-gating | CBSS secret release ↔ runner CIP-23 attestation (cross-call `0x05::VerifyCae` + HPKE delivery) |

### A3. CBFS ∩ CBSS — none directly
(But CBSS encrypts runner-storage DEKs in practice; no shared *issue* in the uncompleted set.)

---

## B. Thematic seams — *distinct* issues, *shared* component/contract (sequence together)

### B1. ⭐ CIP-23 Composite-Attestation / TEE Verifier `0x05` — the biggest cross-cutting epic
The TEE Verifier (`0x05`), CAE envelope, freshness anchor, quote parsers and vendor cert-chains are
**shared infrastructure** consumed by three different callers. Build the pipeline **once**, then wire
each consumer. Starting any consumer before the pipeline = stubbing against a moving target.
| Subsystem | Issues | Role |
|-----------|--------|------|
| **Pipeline (runner triage T5)** | COW-957, 1098, 1099, 1100, 1101, 1102, 1103, 1107, 1108, 1110, 1111, 1301, 1309, 1849, 1850 | CAE struct, verify_cae 8-step, quote parsers, root-cert registry, registration |
| **CBSS consumer (CBSS T4)** | COW-1051 (DCAP/VLEK vendor cert-chain), COW-1847 (secret TEE-gating) | secret release gated on attestation |
| **Container billing (runner Parked, CIP-10 canceled)** | COW-1576, 1587 | BillingAttestation.tee_signature via `0x05::VerifyCae` |

→ **Action:** scope COW-1100/1101/1107/1108 (verifier + parsers + roots) as the foundation; 1051 and
1847 are vendor-specific / consumer leaves that attach after. Confirm CIP-2-family ownership first.

### B2. ⭐ CIP-9 PoR & relay economics — shared Storage Manager `0x0A` / Relay Registry `0x0B`
PoR soundness + slashing + relay rewards form one economic layer; the runner appears as a relay.
| Subsystem | Issues | Role |
|-----------|--------|------|
| **CBFS PoR (CBFS T5)** | COW-2112, 917, 918, 919, 2007, 2183 | chunk-roots → challenge → responder → timer → slashing |
| **CBFS relay economics (CBFS T4)** | COW-2009 (unstake delay), 2010 (fees), 2184 (rewards) | stake/reward/penalty wiring |
| **runner-as-relay (runner ∩ CBFS)** | COW-2183, 2117, 2118 | storage-capable runner gating + PoR slash |

→ **Action:** COW-2112 (commit chunk-roots) is the foundation for all PoR; do it first. 2183 is the
end-to-end umbrella — keep it as the epic tracker, not a parallel implementation.

### B3. Canonical encoding / signing-bytes correctness (cross-language wire stability)
Same hazard class — Rust-serialized signing bytes diverge from the canonical spec, breaking non-Rust
signers. Fix with one canonical-codec discipline + conformance vectors.
| ID | Subsystem | Note |
|----|-----------|------|
| COW-2115 | CBFS/runner | owner-auth `bincode` → `canonical.rs` + cross-lang vectors |
| COW-1060 | CBSS | AAD endianness mixed LE/BE — pick & pin |
| COW-1376 | runner (CIP-2) | reveal Ed25519 sig over `result_bytes` ignored today |

### B4. "Evidence → slash → distribute" enforcement pattern (3 distinct system actors)
Not shared code, but the **same review checklist** applies (provable-after-rotate, bounded KV,
challenger payout, burn/treasury split). Worth one reviewer across all three.
| ID | Subsystem | Slash trigger |
|----|-----------|---------------|
| COW-2109, 962 | runner | result mismatch / dispute |
| COW-917, 2183 | CBFS | PoR miss / fraud |
| COW-1057, 1053 | CBSS | DKG sabotage / forged σ_i |

---

## C. Sequencing recommendation (cross-subsystem)

1. **Independent fast wins first** — clear the per-subsystem Tier 1/2 batches (no cross deps). The 7
   runner∩CBFS overlaps are mostly small (2117/2118/933/937) — assign to **one** owner to avoid
   double work.
2. **Two foundation tickets unlock the most:** COW-1100/1101 (TEE verifier+pipeline) and COW-2112
   (PoR chunk-roots). Everything in B1/B2 waits on these.
3. **Hold the TEE leaves** (1051, 1847, 1576/1587) until B1 foundation lands.
4. **One reviewer for the slash-pattern set** (B4) to keep the economic invariants consistent across
   runner / CBFS / CBSS.

> Ownership caveat (from team-scope notes): CIP-2 family (CIP-2/8/10/11/23) has historically been
> another team's domain. CBFS (CIP-9) storage + CBSS (CIP-24) audit fixes are the cleaner "ours".
> The B1 TEE epic straddles both — confirm ownership before committing.
