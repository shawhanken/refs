# CBQS ↔ CIP-7 Watchtower: Item-by-Item Comparison

**Purpose**: answer the blocking question left by the CBQS design review (`2026-07-27_cbqs-design-review.md`, H1) — **"why can CBQS not be an off-chain delivery class of CIP-7 v2?"**
**Method**: the full CIP-7 text (`cowboy/docs/cips/cip-7-simple-stream-protocol.md`, 1317 lines) plus its deployed implementation (`node/execution/src/stream_key_manager.rs`, `node/runner/src/system_actors.rs:57`), checked item by item against the requirements in CBQS design §1.4–§1.13.

---

## 0 Conclusion (three sentences)

**CBQS is justified as a separate protocol, but roughly a third of its current shape is reinvention.**

1. **It cannot be bolted onto CIP-7**: every delivery, retention, and integrity property of CIP-7 is a **corollary** of "messages are on-chain consensus state". Move the data plane off-chain and those corollaries all lapse — so "add a delivery class" fails architecturally, not for want of effort.
2. **Three structural gaps are real**: single-writer, zero consumer delivery state, and throughput/cost/latency. CIP-7 cannot afford to close them (the fix *is* CBQS), and they constitute CBQS's justification.
3. **But six things must be reused**: recipient-key registration, generation/revocation semantics, wrapped-key identity layout, cursor/stale-cursor error contract, CBY billing flow, and the canonical signing domain. Reusing those six removes about a third of CBQS v1's new concepts and incidentally closes review findings M1 (identity anchor) and M6 (who receives rent).

---

## 1 Architectural divergence (root-cause table)

This table is the root cause of every conclusion below. The two columns are not "different implementation choices" — they are **different premises from which guarantees are derived**.

| Dimension | CIP-7 (deployed) | CBQS (design) |
|---|---|---|
| Message storage | On-chain actor state, committed into `state_root` | Broker-local log/KV, never on chain |
| Append path | One transaction plus gas (`publish`, §Actor Interface:583) | RPC over a persistent connection, **zero chain writes** |
| Source of ordering | Execution determinism: `sequence` MUST be strictly increasing and contiguous (`prev + 1`, §StreamMessage:384) | Broker's single global append order |
| Retention mechanism | Deterministic ring-buffer pruning as a **state transition** (§Ring Buffer Pruning:965-985) | Broker hot window plus consumer-group pins |
| Source of integrity | **The chain is the receipt**; publisher ed25519 signature verifiable by anyone (§Canonical Hashing:492-527) | Provider-signed hash chain / checkpoint chain |
| Number of writers | **A single active `publisher_key`** (`init` takes one key; `rotate_publisher_key` keeps one active) | Arbitrarily many appenders (StreamGrant `append` verb) |
| Consumer delivery state | **None**. Pull consumers "track local cursor" (§Pull Delivery:867) | Consumer group + lease + terminal state + dead-letter |
| Payload ceiling | 16 KiB inline; `MAX_EFFECTIVE_PLAINTEXT_BYTES = 16_344` | 256 KiB inline, overflow via CBFS reference |
| Replay window | `DEFAULT_RING_BUFFER_CAPACITY = 10_000` messages | 7 days or a byte cap (standard); seconds (fast) |
| Encryption granularity | Per-epoch content key, `DEFAULT_KEY_EPOCH_BLOCKS = 600` | Per-generation symmetric data key |
| Key custodian | CBSS committee (IBE to MPK), t-of-n threshold release | CBSS holds the root, member HPKE envelopes fan out |
| Who pays | The **subscriber** buys epoch access (`acquire_epoch_access`) | The **owner** pays stream rent |
| Delivery latency | Key delivery 4–5 blocks, bounded by `REQUEST_FRESHNESS_BLOCKS = 384` | Sub-second push (data plane) |

**How to read it**: CIP-7 needs no ack/retry/lease/receipt because on-chain state substitutes for all of them — a message in consensus is delivered and non-repudiable by construction. Once CBQS moves messages out of consensus it must build receipt chains, leases, and terminal states itself. That is not a feature flag on CIP-7; it is a different derivation.

---

## 2 Item-by-item capability comparison

Verdict values: **Reuse** (CBQS should adopt the existing CIP-7 artifact) · **Extend** (same concept, semantics need widening) · **Gap** (CIP-7 lacks it and cannot afford it) · **Duplicate** (CBQS is rebuilding something CIP-7 already has)

| # | Capability | CIP-7 today | CBQS requirement | Verdict |
|---|---|---|---|---|
| 1 | Ordered append-only sequence | Yes. `head_sequence` / `floor_sequence`, contiguous sequence | Yes, broker sequence | Extend (same semantics, different location) |
| 2 | Multi-writer append | **No**. One active `publisher_key` | Required (multi-producer work queue, 100-person room) | **Gap** |
| 3 | Write authorization (scoped verbs) | No. `subscription_policy: PUBLIC \| PRIVATE_ALLOWLIST` governs **subscription** only; writing means holding the publisher key | StreamGrant `{append, consume, acknowledge, replay, group-admin}` | **Gap** |
| 4 | Cross-account participation | Partial. `payer_account` ≠ `beneficiary_account` (sponsored purchases), but still single-writer | Owner signs grants for another party's holder keys | **Gap** (read side exists, write side does not) |
| 5 | Consumer groups / competing consumption | **No** | One stream, one group, many competing workers | **Gap** |
| 6 | Lease / ack / nack / extend | **No**. §Non-goals:68 lists "Ack/retry protocol in core spec" as out of scope | Required (core of the standard class) | **Gap** |
| 7 | Terminal lifecycle / dead-letter / redrive | **No** | Required | **Gap** |
| 8 | At-least-once plus client dedup | Yes. Push is at-least-once; "Consumers MUST deduplicate by `(stream_id, sequence)`" (§Push:836-839) | Same semantics, dedup key is the client message id | Reuse (semantics already fixed — do not restate differently) |
| 9 | Exactly-once | Explicitly not promised (§Non-goals:67) | Explicitly not promised (§1.13) | Consistent ✓ |
| 10 | Idempotent append | N/A (appends are transactions, deduped by nonce) | Idempotency horizon, replays return the original receipt | Gap (necessary purely because of #1's location change) |
| 11 | Push delivery | Yes. `PUSH`, actor pays fan-out gas, bounded by `max_push_deliveries_per_block` / `max_push_cycles_per_block` | Push-first over a persistent duplex connection with flow-control credits | Extend (CIP-7's push carries an on-chain per-block budget; CBQS has no such constraint) |
| 12 | Pull / long-poll fallback | Yes. `PULL`, `PUSH_WITH_PULL_FALLBACK`, `get_since(cursor, limit)`, `MAX_GET_SINCE_LIMIT = 500` | Long-poll as a fallback for constrained clients | Reuse (**keep the three mode names**) |
| 13 | Stale-cursor error | Yes. `cursor < floor_sequence - 1` → `CURSOR_TOO_OLD` (§965-989) | cursor-too-old plus a signed checkpoint anchor | **Duplicate** (error code and boundary must align — see R4) |
| 14 | Retention window | Yes. Ring-buffer message cap, deterministic pruning | Time/byte hot window plus group pins; **cap triggers backpressure, never eviction** | Extend (CBQS's no-silent-eviction is a new and correct property) |
| 15 | Message integrity | Yes. Publisher ed25519 over a deterministic-CBOR signing payload plus `payload_hash` | Provider-signed hash-chain receipts | Extend (signer moves from publisher to provider because the chain no longer witnesses) |
| 16 | Continuity proof | Implicit (contiguous on-chain sequence plus state root) | Explicit hash chain plus checkpoint chain | Gap (required precisely because it is off-chain) |
| 17 | Payload encryption | Yes. XChaCha20-Poly1305, per-epoch content key, AAD binds `{stream_id, sequence, key_epoch, kind, content_type}` | End-to-end encrypted by default, per-generation data key | Extend (**the AAD-binds-envelope anti-reorder/replay rule should be copied verbatim**) |
| 18 | Key custody root | Yes. IBE to the CBSS committee MPK, t-of-n threshold | CBSS holds the root | Reuse ✓ |
| 19 | Membership fan-out | Yes. Account-scoped X25519; one purchase covers every process the account delegates to; explicitly claims 100 / 1,000 / 10,000 subscribers (§959-963) | One HPKE envelope per member; 100 members = 100 envelopes per generation | **Duplicate** (see R1/R2 — per-member envelopes are more expensive and more complex than account-scoped keys) |
| 20 | Recipient identity registration | Yes. `AccountKeyRegistration` (on-chain, account-scoped, `MAX_ACCOUNT_KEYS_PER_ACCOUNT = 8`, `ACTIVE`/`REVOKED`, must be account-signed) | Member HPKE recipient key (no on-chain registration) | **Duplicate** (reuse the `0x0D` registry — see R2) |
| 21 | Key generations and revocation | Yes. `generation` counter at `0xD \|\| 0x06 \|\| keccak(stream_id) \|\| u64_be(epoch)`; a re-wrap bumps the identity so old σ fails against the new ciphertext; already-unwrapped keys are not retroactively revoked | Encryption-key generation plus authorization generation, with a three-step rotation state machine | **Duplicate** (the same invariant restated — see R3) |
| 22 | Forward/backward isolation | Yes, and stronger. `stream_secret` never leaves the publisher keystore; `content_key_e = HKDF(...)` is independent per epoch, so one generation yields nothing about another | No explicit cross-generation isolation argument | **CIP-7 is stronger; CBQS should supply the argument** |
| 23 | Billing and value flow | Yes. Publisher treasury plus protocol fee → System Treasury `0x08`, `MAX_PROTOCOL_FEE_BPS = 5_000` | Per-stream rent (modeled on CBFS storage fees) | **Duplicate** (should ride the same CBY flow — see R5) |
| 24 | Canonical encoding / signing domain | Yes. Deterministic CBOR (RFC 8949) plus ed25519 plus SHA-256, with tag canonicalization (float64-only, etc.) | StreamGrant wire format is an "open question" | **Duplicate** (see R6 — `cowboy-protocol-codec` is already the single signing-domain owner) |
| 25 | Large-payload offload | No (§Non-goals:70 "External payload URI hosting guarantees"; §1060 lists it as future) | >256 KiB in CBFS, reference carried inside the ciphertext | Gap (CBQS leads here and could feed back into CIP-7) |
| 26 | Header filters | Yes. Deterministic JSON Filter DSL over `kind` / `tags` / `sequence` / `timestamp` | **Explicitly excluded** (§1.13 "server-side semantic filters") | Divergent (CBQS's deliberate omission is reasonable) |
| 27 | Provider / broker role | None (no off-chain broker; validators are the data plane) | `cbqsd` as a new server type plus provider registry and handoff | **Gap** (and the largest risk — see review H3) |
| 28 | Bounded-loss delivery class | None (no on-chain notion of "provisional") | `fast` class: provisional/durable watermarks, broker epoch, void statement | **Gap** (no on-chain counterpart) |
| 29 | Actor bridging | Native (the stream *is* an actor) | Actor-bridge SDK helper; "the broker never calls actors automatically" | Divergent (CIP-7 is stronger; CBQS is deliberately weaker to avoid consensus coupling) |
| 30 | Scheduled ingestion | Yes. `IngestionConfig` plus CIP-5 timers plus CIP-2 tasks | None | CIP-7 only |

**Tally**: of 30 items — 11 gaps (CBQS's justification) · 6 duplicates (should be deleted) · 10 reuse/extend (align names and error contracts) · 3 divergent (each defensible).

---

## 3 Three structural gaps — CBQS's justification

CIP-7 **cannot afford** these three; the fix for each is CBQS itself. This is the argument that belongs in the design's Motivation section.

### G1 Single writer

`init(stream_id, initial_publisher_key, ...)` accepts exactly one publisher key; `publish` step 6 is "Validate signature against active publisher key"; `rotate_publisher_key` maintains a single active key plus a key schedule for historical verification.

**Consequence**: a 100-person chat room (everyone writes), a work queue (many producers), and agent RPC (bidirectional request/reply) are **inexpressible in CIP-7**. Closing the gap means a multi-publisher authorization model, per-writer ordering or global serialization, and write-side revocation — i.e. rebuilding the entire auth layer, which is exactly what StreamGrant is.

### G2 Zero consumer delivery state

CIP-7 §Non-goals item 3 explicitly places "Ack/retry protocol in core spec" out of scope; pull consumers "track local cursor" purely client-side; push is "best-effort, no protocol-level ack or retry".

**Consequence**: **the work queue — one stream, one group, many competing workers, the single most important multi-agent coordination pattern — has no counterpart in CIP-7 at all.** Closing it means putting per-message × per-consumer lease and terminal state on chain, i.e. several chain writes per message — precisely what both documents reject (CBQS §1.14 "On-chain mailbox actor", and CIP-7's own gas model).

### G3 Throughput / cost / latency

16 KiB inline ceiling, one transaction plus gas per `publish`, actor-funded push fan-out bounded by `max_push_deliveries_per_block`, a 10,000-message replay window, and 4–5 blocks of key-delivery latency.

**Consequence**: presence / typing / awareness / CRDT op logs — the targets of CBQS's `fast` class (roughly 10× cheaper, second-scale retention, sub-second push) — are impossible on chain. No amount of parameter tuning changes that.

---

## 4 Six reinventions — reuse instead of rebuild

### R1 Wrapped-key identity layout and generation semantics

CIP-7 already specifies this to the byte: DST `cbss/ibe/cip7-content-key/v1`; `content_key_identity_bytes` (with a `stream_id` length prefix to prevent collisions); `base_wrapped_dek_aad` (binding `committee_epoch`, `selector_byte`, and `override_hash`); `aad = base || compress(U)` (binding the Boneh-Franklin ephemeral — the core of the CIP-24 confidentiality fix); and a `generation` bump that invalidates old σ.

**Recommendation**: have CBQS envelopes adopt that identity/AAD layout and generation semantics directly, swapping only the recipient (member HPKE key instead of committee MPK) and the DST (`cbss/ibe/cbqs-stream-key/v1`, following CIP-7 §258-264's four-layer domain-separation argument). **Do not design a fresh envelope signature field set** — §1.4.4 currently invents a five-tuple signature over stream id / generation / recipient key / ciphertext hash / previous rotation id.

### R2 Recipient identity registration — reuse `0x0D`

CIP-7's `AccountKeyRegistration` is already on-chain, account-scoped, X25519, capped at `MAX_ACCOUNT_KEYS_PER_ACCOUNT = 8`, has an `ACTIVE`/`REVOKED` state machine, must be account-signed, never stores the private key on chain, and explicitly states that the account holder delegates the private key to whatever consumes the stream (CLI, off-chain worker, CIP-2 runner).

CBQS's "member HPKE recipient key" is the same object without on-chain registration, revocation state, or an identity anchor.

**Recommendation**: reuse the `0x0D` account-key registry as the HPKE recipient identity for CBQS members. Three benefits: (1) an entire membership-key state machine disappears; (2) **review finding M1 (identity anchor) closes directly** — revocation gets an on-chain record; (3) applications spanning both protocols manage one key, not two.

### R3 Revocation semantics and terminology

CIP-7's `generation` (one counter per epoch, bumped on re-wrap) and `key_epoch` (a time window) are **two orthogonal concepts**. CBQS collapses both into one `encryption-key generation` and then adds a second `authorization generation`. Three same-named, differently-meaning generations in one system is a predictable long-term source of confusion.

**Recommendation**: settle the terminology. Either adopt CIP-7's two-layer `key_epoch` + `generation`, or rename explicitly (e.g. `grant_epoch` / `dek_version`) and state the mapping to CIP-7 in the spec. **Same name with different meaning is far more expensive than renaming.**

CIP-7 also states an invariant CBQS is missing: **a re-wrap does not retroactively revoke already-unwrapped keys; it only invalidates pending and future releases.** CBQS §1.4.4's three-step rotation should assert the same property explicitly.

### R4 Cursor / stale-cursor error contract

CIP-7: a cursor is stale iff `cursor < floor_sequence - 1` → `CURSOR_TOO_OLD`; `subscribe(start_cursor)` uses the same predicate. CBQS: "below the floor, return an explicit cursor-too-old with a signed checkpoint anchor".

**Recommendation**: align the error code and the boundary predicate verbatim (CBQS is a superset, carrying an extra checkpoint anchor). **Never ship one `CURSOR_TOO_OLD` and one `cursor-too-old` with different off-by-one boundaries** — that class of divergence grows into real SDK bugs. Likewise keep the `PUSH` / `PULL` / `PUSH_WITH_PULL_FALLBACK` mode names.

### R5 CBY billing flow

CIP-7 already fixes it: publisher amount → publisher treasury; protocol fee (within `[0, MAX_PROTOCOL_FEE_BPS]`) → System Treasury `0x08` (the CIP-2 §5.4 shared sink), then governance-allocated across burn / staking / dev fund.

CBQS says only "per-stream rent modeled on CBFS storage fees, paid from the owner account" — no protocol fee, no destination, and no answer for who receives rent when the broker is self-hosted (review M6).

**Recommendation**: ride the same flow and the same protocol-fee mechanism. For self-hosted brokers, rent should follow the CBFS relay analogy (the 89% relay share, CIP-31) and accrue to the provider, with the protocol fee still going to `0x08`. M6 then needs no new mechanism.

### R6 Canonical encoding and signing domain

CIP-7 fixes deterministic CBOR (RFC 8949 canonical) plus ed25519 plus SHA-256, down to a float64-only rule for numeric tags. More importantly, `cbfs_signing.rs` in `cowboy-protocol-codec` is already the **single owner** of the CBFS/RAS signing domain, and its module header records the lesson: node and cbfs each carried a byte-identical copy held together by one parity test — the same fork that caused the 2026-07-11 outage (COW-2608). COW-2649 consequently banned bincode and consolidated to one implementation.

**Recommendation**: StreamGrant's signing bytes must live in `cowboy-protocol-codec` and follow the same `Encoder` conventions (big-endian fixed-width integers, `u64`-BE length prefixes, addresses as EIP-55 checksum strings, `bool` as one byte, explicit `Option<T>` tags), and **signing bytes must never pass through serde or bincode**. §1.15 #1 is right that the wire format is open, but the answer already exists — no new selection is needed.

---

## 5 Conclusion: the boundary (the precondition for two coexisting protocols)

> **CIP-7 Watchtower** = **single-writer, consensus-visible, subscriber-paid** broadcast. Messages are chain state and the chain is the receipt. Fits: news/price/alert feeds, public or paid subscription, messages needing finality and public verifiability, cross-chain egress (CIP-25 §2.6).
>
> **CBQS** = **multi-writer, off-chain, owner-paid** private coordination. Messages live in the broker and the provider's signature is the receipt. Fits: work queues, agent RPC, chat rooms, presence, CRDT op logs — anything needing per-consumer delivery state or high-frequency low-cost transport.
>
> **Decision rule (put it in the spec)**: need **consensus visibility or finality** → CIP-7. Need **multiple writers or per-consumer delivery state** → CBQS. Neither → use the actor mailbox.

This boundary must appear in CBQS's CIP §Motivation and in CIP-7's §Non-goals, cross-referencing each other. Without it, a second stream protocol will keep generating confusion at the SDK and documentation layers.

**Answering the original question**: CBQS cannot be an off-chain delivery class of CIP-7 v2, because every CIP-7 delivery, retention, and integrity guarantee derives from messages being consensus state; once they leave consensus those premises lapse and a different derivation with different artifacts is required. **However**, four control-plane items — recipient registration (R2), generation/revocation semantics (R3), billing flow (R5), and the canonical signing domain (R6) — must reuse CIP-7 and existing artifacts. Doing so removes roughly a third of CBQS v1's new concepts, materially shrinks H2 (the envelope subsystem), and closes M1 (identity anchor) and M6 (rent destination) outright.

---

## 6 Open decisions

1. **Does a CBQS stream need an on-chain anchor object, and in what form?**
   - Option A (new): CBQS owns its stream record (the current design). Independent and clean, but it overlaps the `StreamConfig` concept and needs a new system actor (`0x17`).
   - Option B (reuse): the CBQS on-chain record is an extended form of CIP-7 `StreamConfig` living at `0x0D`, discriminated by a new `delivery_mode: ONCHAIN | OFFCHAIN_BROKER`. Saves a system actor and shares the account-key registry and billing flow, but compresses two semantics into one actor, forcing a re-review of `0x0D`'s storage layout and gas model.
   - **Recommend A, with mandatory reuse of `0x0D`'s `AccountKeyRegistration` and protocol-fee flow**: independent control-plane object, reused control-plane artifacts. That avoids mixing two delivery semantics in one actor while capturing all of R2's and R5's benefit.

2. **Member keys: are per-member HPKE envelopes and CIP-7 account-scoped single keys both needed?**
   With R2 in place, an account-scoped key already covers "every process an account delegates to"; per-member envelopes are only necessary when **per-member revocation** is required. Recommendation: v1 ships account-scoped only (a 100-person room is 100 accounts each with one registered key, with fan-out carried by CBSS — isomorphic to CIP-7's 10,000-subscriber path), and per-member envelopes become a v2 fine-grained-revocation option. **If this holds, review finding H2 dissolves.**

---

_Reviewer: Marshal cognitive loop (manual primary-source verification: full CIP-7 text, deployed implementation, CIP-24/9/10/31, `cowboy-protocol-codec`). Advisory only, non-blocking._
