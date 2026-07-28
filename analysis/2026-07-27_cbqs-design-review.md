# CBQS Design Review: Feasibility, Technical Risk, and New-Concept Emergence

**Subject**: `refs/analysis/2026-07-27_cbqs-design.zh.md`
**Date**: 2026-07-27
**Verdict**: `escalate` — the direction holds and the document is more honest about failure modes than most design drafts, but there are **two HIGH-severity premise errors** material enough to change the v1 scope decision, plus one self-contradictory v1 boundary.

**Scope and limits of this review (stated plainly)**: the subject is a design document, not a code diff, so Marshal's invariant gate and the `/code-review ultra` adversarial pass are **both inapplicable and were not run**. Every conclusion below comes from manual verification against primary sources (the actual code and specs under `cowboy/docs/cips/`, `cowboy/docs/whitepaper/`, `node/`, `cowboy-protocol/`, `cbss/`, `runner/`). Evidence is cited as `file:line` so each claim can be checked independently. No subagents were dispatched.

---

## 0 Executive summary

**Verdict: `escalate`. The direction is right, but the v1 scope must change before work starts.**

### The three-sentence version

The gap CBQS wants to fill — a durable off-chain coordination layer — is real, and the document is more honest about failure modes than most design drafts. But two of its key arguments rest on wrong premises: **it treats an already-deployed on-chain protocol as a draft**, and **it uses a governance-tunable parameter as if it were a structural wall**. Fix those two and 30–50% of the new concepts disappear from v1 outright.

### Two HIGH-severity premise errors

1. **CIP-7 Watchtower is not a draft — it is the deployed canonical stream protocol** (system actor `0x0D`, a 2390-line handler, a hard dependency of CIP-25). It already has push/pull, a replay window, `CURSOR_TOO_OLD`, per-epoch key rotation, CBSS custody, X25519 recipients, `WrappedContentKey`, and CBY billing, and it explicitly claims support for 100–10,000 subscribers. CBQS rebuilds that entire vocabulary off-chain with different semantics.
2. **The "CBSS 64-principal ACL cap" is not a wall** — it is a §4.5 governance parameter; CIP-24's ACL is a runtime gate and `wrapped_dek` is O(1). The real blocker is job binding. The consequence: v1's largest bespoke component (envelope fan-out plus the companion key stream) is built over a gap the CBSS team may close themselves.

### One undeliverable boundary

Provider handoff is simultaneously "an open question needing a design pass before the CIP" and "a v1 acceptance gate", while the v1 deliverables list contains no epoch, fencing, or continuity anchor at all. A single provider exclusively owning the hash chain, leases, and cursors is a single point of failure: CBQS inherits every availability problem CBFS avoids through erasure coding and autonomous repair, with no equivalent mechanism.

### New-concept emergence: **high**

Roughly 25 new nouns, of which ~8 collide by name but not by meaning with CIP-7 (the expensive category — it poisons the SDK and the docs for years) and ~4 are CBFS synonyms with drifted semantics. `consumer group` would become the system's first object with authority but no on-chain record. In magnitude this is a **CIP-9-scale subsystem**, and simultaneously the third off-chain daemon family and the second stream protocol — **not one slice, but multiple quarters**.

### The shortest correct next step (two blockers, both paperwork rather than code)

1. Build the CIP-7 item-by-item comparison table and answer why this cannot be an off-chain delivery class of CIP-7 v2.
2. Settle the persistent-workload release path with the CBSS team. If viable, the entire envelope subsystem leaves v1, retiring two HIGHs and one MED together.

The remaining four items are scope convergence: bind the grantee to the CIP-10 Persistent Workload registry record (`0x13`) instead of a bespoke holder key; state plainly that v1 is single-provider with no handoff promise; defer the `fast` class to v2; allocate the address and opcode band from `0x17`.

**Worth keeping**: the honest trust posture, the interruption-safety argument for three-step rotation, the loss-visibility design in the fast class, and never silently evicting live records. These are stronger than comparable drafts — do not cut them along with the rest.

---

## 1 Premise verification (primary sources)

| Document claim | Verification | Evidence |
|---|---|---|
| Watchtower / CIP-7 is a "**proposed** draft, public actor-native stream" | ❌ **Wrong**. CIP-7 calls itself "the canonical stream protocol for Cowboy", is a 1317-line spec, and is **code-deployed**: Stream Key Manager system actor `0x0D`, a 2390-line handler, a PVM host seed | `cowboy/docs/cips/cip-7-simple-stream-protocol.md:1-30`; `node/runner/src/system_actors.rs:57`; `node/execution/src/stream_key_manager.rs` (2390 lines); `node/pvm/crates/pvm-host/src/lib.rs:694` |
| CBSS is unsuitable for chat-room scale because of a "64-actor ACL cap" | ⚠️ **Misattributed**. `MAX_ACL_ACTORS = 64` is a **governance-tunable §4.5 parameter**; CIP-24 states explicitly that the ACL is a runtime gate, not a cryptographic recipient list — `wrapped_dek` is **O(1)** regardless of ACL size, and ACL edits require no re-wrap. The actual structural blocker is §3.7's `(actor, runner_id, job_id, secret_id)` job binding plus the freshness window | `cip-24-secrets-manager.md:1257` (parameter table), `:134`, `:209`, `:533` vs `:660`, `:822` |
| CIP-7 cannot do membership-scale fan-out | ❌ CIP-7 states "Model supports large subscriber sets (100, 1,000, 10,000)" using **account-scoped X25519 + CBSS threshold proxy re-encryption + epoch keys**, and already defines a `WrappedContentKey` type | `cip-7-simple-stream-protocol.md:923-963`, `:340` |
| `OwnerCapTokenV1` is owner-only, bearer, with only a coarse access mode and path prefix | ✅ Correct | `cowboy-protocol/crates/cowboy-protocol-codec/src/cbfs_signing.rs:87-101` |
| `delegated_request_signing_bytes` plus the delegation-cert layer are reusable | ✅ Present, and already consolidated into a single owner by COW-2649 (node/cbfs copies deleted) | same file `:201`, `:246`; module header |
| HPKE envelopes have precedent | ✅ `hpke 0.12` (`x25519` feature) is already a workspace dependency in cbss and runner | `cbss/Cargo.toml:116`, `runner/Cargo.toml:211`, `runner/crates/runner-storage/Cargo.toml:31` |
| Provider registry follows "the CBFS-relay pattern, stream assigned at creation" | ⚠️ True only for the control plane. The CBFS data plane is **erasure-coded across many relays with PlacementRecords, CAS versioning, autonomous repair, and drain rebalancing** — not single assignment | `cip-9-runner-storage.md:267`, `:289`, `:307`, `:311` |
| Companion draft `cowboy/internal-docs/engineering/cbmq-high-level-design.md` | ❌ Does not exist in the workspace (`cowboy/internal-docs/engineering/` contains only `testing/`) | `find` returns nothing |
| "Cowboy provides no durable off-chain backplane" | ⚠️ Partly true. Durable off-chain **workloads** already exist: CIP-10 v2 Persistent Workloads carry a mandatory on-chain registry record (Container Registry `0x13`) governing identity, ownership, and lifecycle. The document never references it | `cip-10-runner-containers.md:1192`, `:1200`, `:1216` |

---

## 2 HIGH-severity risks

### H1 — Head-on concept collision with a deployed CIP-7, with no integration analysis

CIP-7 already owns: the stream model; `PUSH` / `PULL` / `PUSH_WITH_PULL_FALLBACK` delivery; a bounded replay window with explicit `CURSOR_TOO_OLD`; per-epoch content keys with deterministic rotation cutover; CBSS-held key custody; X25519 recipient identity; `WrappedContentKey` (i.e. the "wrapped envelope"); publisher key rotation; canonical hashing/signing; and CBY billing with a protocol fee.

CBQS **reinvents that entire vocabulary off-chain with different semantics**. The one line in §1.11 — "share envelope/cursor/SDK conventions where convenient" — is not an integration analysis. Worse, CIP-25 lists CIP-7 as a hard dependency (`cip-25-cross-chain-architecture.md:13`, `:279`, `:301`), so two coexisting stream protocols contaminate the cross-chain line directly.

**Requirement**: before a CIP, add a section that walks CIP-7 capability by capability and answers explicitly, "**why can this not be an off-chain delivery class of CIP-7 v2?**" — rather than demoting CIP-7 to a "draft".

**Done**: the comparison table is at `2026-07-27_cbqs-vs-cip7-comparison.md` (30 capabilities: 11 gaps / 6 duplicates / 10 reuse-or-extend / 3 divergent). Conclusion: CBQS **is** justified as a separate protocol — single-writer, zero consumer delivery state, and throughput/cost are three structural gaps CIP-7 cannot afford — but its control plane must reuse four existing CIP-7 artifacts; doing so dissolves H2 along with M1 and M6.

### H2 — The largest new subsystem (envelope fan-out) is built on a gap that may get closed

The companion key stream in §1.4.4 costs: one extra on-chain record per encrypted stream, dual member keys (holder signing + HPKE recipient), a signed envelope chain, a three-step rotation state machine, and N envelopes per generation.

Yet §1.4.4 bullet 4 concedes that "a direct CBSS persistent-workload release path would let small streams skip the envelope mechanism", and files it under §1.15 open questions. In other words, **v1's largest bespoke component is the fallback for a CBSS gap that the CBSS team may close themselves**. Combined with H1 (CIP-7 already reaches 10,000 subscribers via CBSS with account-scoped keys), this path deserves two weeks of design work with the CBSS team *before* any envelope machinery is built.

### H3 — Self-contradictory v1 boundary: provider handoff is simultaneously an open question and an acceptance gate

- §1.15 #4: handoff "needs a design pass before the CIP".
- §1.13 acceptance tests: require "a provider-handoff drill under live traffic".
- §1.13 v1 deliverables: contain **none** of provider epoch, signing-key transition record, fencing, continuity anchor, or rollback detection.

Meanwhile §1.10 concedes that a stream's provider exclusively owns its signed hash chain, leases, and cursors — a **single point of failure**. CBQS inherits every availability problem that CBFS avoids via erasure coding, PlacementRecords, and autonomous repair, without any equivalent mechanism. This is the single largest engineering risk in the design and it is not in v1 scope. The current "open question + acceptance gate" combination is undeliverable as written.

---

## 3 MED-severity risks

### M1 — Workload identity has no on-chain anchor

StreamGrant binds to a grantee holder public key, but the document never says where a runner-hosted workload's holder key comes from, or how it survives rescheduling onto a different runner:

- baked into the container image → the runner operator can extract it;
- generated per instance → every restart requires the owner to be online to re-issue the grant, which directly contradicts the §1.4.4 selling point that "a dead participant can never freeze membership".

**Off-the-shelf fix**: CIP-10 v2 Persistent Workloads already carry a **mandatory on-chain registry record** governing identity, ownership, lifecycle, and route eligibility (Container Registry `0x13`). StreamGrant's grantee should bind to that record so revocation and rotation have a chain anchor, instead of inventing a loose parallel holder-key lifecycle.

### M2 — No system-actor address or opcode allocation

CBQS needs at minimum a stream registry (plus provider registry) system actor. Whitepaper §9.1 mandates that a new system actor **MUST** claim the next free slot in the dense sequence (currently `0x17`) and update the address table in the same change (`cowboy/docs/whitepaper/cowboy-technical-whitepaper.md:861`). It also needs a new system-instruction opcode band (create / configure / delete stream, rotate admin key, bump both generations, register / assign provider).

This repository has a history of both address collisions (`0x11`/`0x13` reconciliation, `cowboy-technical-whitepaper.md:863`) and opcode collisions (CIP-12 governance opcodes 103–107 colliding with CIP-16). Neither can be left blank.

### M3 — Unbounded revocation latency

The broker does not read the chain per request; it tracks stream records to determine the current generation. Effective revocation latency is therefore broker chain-follow lag plus grant TTL. The document bounds neither, and never specifies how `cbqsd` follows the chain (RPC polling? reorg handling?). Cowboy's Simplex BFT gives finality, so reorg exposure is bounded — but that belongs in the spec as an explicit assumption, not as an unstated default.

### M4 — Control-plane cost of membership churn is understated

Removing one member requires: a CBSS release to the rotation workload (a t-of-n round trip, constrained by `REQUEST_FRESHNESS_BLOCKS` ≈ 6 minutes) + publishing N envelopes + one on-chain generation-bump transaction. A 100-person room with frequent joins/leaves produces a rotation storm.

"Zero chain writes on the data path" holds, but **the membership-change path is on-chain and CBSS-latency-bound** — and §1.13's first acceptance test is a 100-person chat room. §1.15 #2 lists release latency as an open question; acceptance will hit it head-on.

### M5 — The fast class makes censorship cheap and deniable

A broker epoch bump plus a void statement is **cryptographically indistinguishable** from a real crash. A malicious provider can "crash" to erase anything past the last durable checkpoint, and the observable behavior matches a hardware failure. The document is honest that non-delivery can only be evidenced, not prevented — but it does not note that the fast class removes **the evidencing capability itself**. With no staking in v1 (§1.10), the fast class carries essentially no adversarial guarantee — and both §1.13 acceptance applications (ClawChat, Homestead CRDT) run on it.

Secondary application burden: consumers observe provisional records and may act on them (a chat message is already rendered); on a void the application must roll back local state. Exposing a void event in the SDK just relocates that reconciliation work into every application.

### M6 — Billing is decoupled from actual consumption

Rent is charged on-chain per stream from the owner account, while real resource consumption (bytes, retention pinned by stalled groups) happens off-chain at the broker. CBFS ties the two together with Proof-of-Retrievability, challenge bonds, and signed usage reports (`relay_usage_signing_bytes` / `ReportUsageRequest`). CBQS v1 has none of that; the broker's only lever is backpressure refusal. The document also never defines who receives the CBY rent when the broker is self-hosted.

---

## 4 New-concept emergence relative to existing Cowboy

The document introduces roughly **25 new nouns**:

`cbqsd`, stream record, StreamGrant, holder signing key / HPKE recipient key pair, authorization generation, encryption-key generation, consumer group, lease, the three terminal states (ACKED / DEAD_LETTERED / EXPIRED), dead-letter lane, redrive cycle, delivery class, provisional / durable watermark, broker epoch, void statement, checkpoint receipt, hash-chain append receipt, key stream, rotation authority, envelope set / rotation id, provider epoch / fencing / continuity anchor, idempotency horizon, backpressure refusal, actor bridge helper, inline limit.

Distribution:

1. **~8 collide by name or meaning with CIP-7**: stream, cursor, replay window, cursor-too-old, key generation/epoch, wrapped envelope, push/pull, subscription. **This is the expensive category** — same name, different meaning, poisoning the SDK, the docs, and onboarding for years.
2. **~4 are CBFS synonyms with shifted semantics**: owner cap → grant, provider registry, retention/quota, rent.
3. **`consumer group` would be the system's first object with authority but no on-chain record** (§1.4.1 states it is not a chain object; the broker creates and configures it under the stream's admin authority). By contrast: a CBFS volume has a `StorageCommitment`, a CBSS secret has an on-chain SecretVersion, a CIP-10 persistent workload has a mandatory registry record. This is a **new trust category**, and the document never argues affirmatively for why it can go unanchored.

**Magnitude**: this is a **CIP-9-scale subsystem**, and simultaneously the system's **third off-chain daemon family** (cbfs relay, cbssd, cbqsd) and **second stream protocol**. §1.13's v1 list holds 14 deliverables including a new daemon, a new auth protocol, a new key-distribution subsystem, two delivery classes, a push transport with flow control, an SDK, CBFS composition, and quotas — with a provider-handoff drill bolted on. Against the team's current concurrent load (CIP-28 / CIP-34 / CIP-36), **this is not one slice; it is multiple quarters**.

---

## 5 Recommended convergence path

1. **Produce the CIP-7 comparison table first** (blocking). Enumerate CIP-7's existing capabilities against CBQS's requirements and answer explicitly why this is not an off-chain delivery class of CIP-7 v2. This step alone may eliminate 30–50% of the new concepts.
2. **Ask the CBSS team about the persistent-workload release path first** (blocking). If viable, the entire envelope subsystem leaves v1, retiring two HIGHs and one MED.
3. **Bind the grantee to the CIP-10 persistent-workload registry record** instead of inventing a holder-key lifecycle (resolves M1).
4. **Cut v1 to a single provider with no handoff promise**: state plainly that "v1 = one provider; its failure is downtime — an SLA concern, not a correctness concern", and move handoff, together with that §1.13 acceptance item, to v2.
5. **Defer the `fast` class to v2**, or state explicitly that it offers no adversarial guarantee in v1 (no staking). Let standard plus hash-chain receipts stabilize first.
6. **Allocate the address and opcode band** (from `0x17`) and update whitepaper §9.1 in the same change.
7. Fix the dangling `cbmq-high-level-design.md` reference.

---

## 6 What is worth keeping

These are genuine strengths relative to comparable design documents and should survive convergence:

- **An honest trust posture**: it protects content confidentiality only, explicitly declines to hide the communication topology, and enumerates layer by layer what the chain records, CBSS activity, and broker metadata each leak. That beats vague privacy promises.
- **The interruption-safety argument for the three-step rotation state machine** (§1.4.4 bullet 3): stopping between steps is still safe, with N+1 dormant. This class of "partially completed is still correct" reasoning is exactly what this repository's historical incidents (the pay-then-fail conservation hole) lacked.
- **Loss visibility in the fast class** (§1.6.1): `(broker epoch, sequence)` identity, no sequence reuse across epochs, an explicit void statement. Far more honest than "best effort, silent loss". M5 critiques its adversarial ceiling, not its engineering.
- **The rejected-alternatives list (§1.14) gives reasons rather than conclusions**, including why managed RabbitMQ cannot be the client-facing system.
- **Live records are never silently evicted** (§1.7): the cap triggers backpressure, not eviction. That is the right default.

---

_Reviewer: Marshal cognitive loop (manual primary-source verification; invariant gate not run, no subagents dispatched). Advisory only, non-blocking._
