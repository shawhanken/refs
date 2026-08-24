# CIP-39 Simplification Plan — document version 2

**Date:** 2026-08-24
**Scope:** `cowboy` branch `spec/cip-39-v2` (base `main` @ `beb1e5c`) — the rewrite plus twelve rounds of Marshal deep review and their fix passes (see §9)
**Companion to:** `docs/cips/cip-39-cowboy-queue-system.md` (rewritten), `docs/cips/cip-39-gas-vectors-v2.json` (new)

---

## 1. The brief, and the yardstick it sets

From the 2026-08-24 engineering sync:

> The queueing system was designed *overly*. What it is, underneath, is a message
> queue between runners — the kind of thing you would get from Kafka or RabbitMQ.
> The chain part should be a **governance layer**: put the queue's *configuration*
> on chain — concurrency, fees — and let governance change it. The queue itself
> should run without knowing the chain exists. Nobody reads the per-message state
> we write on chain anyway.

That is the yardstick every change below is measured against, plus one correction
we owe the room: the on-chain data is not unread. `cbqsd` reads it, on **every
request**, and fails closed when it is stale. That is why the decoupling has to be
done deliberately rather than by deletion — §2 item 1.

A second correction: the throughput ceiling the team worried about is not caused
by writing to the chain. It is caused by one client signature, one broker
signature, and one synchronous `fsync` **per message**, plus two hash-chain
updates. Removing the chain from the data path without removing those would not
have moved the number — §2 item 4.

## 2. What changed, why, and what it costs

Twelve changes, ordered by how much they remove. Each states honestly what the
protocol gives up, because every one of them gives up something.

### 1. The broker no longer reads the chain per request

| | |
| --- | --- |
| **v1** | Every request acquires one `FinalizedViewV1` and evaluates stream record, provider record, status, escrow, keys, generations, and bounds from that immutable snapshot. The broker **MUST fail closed** when its view is older than `cbqs.max_chain_staleness_blocks` (default 30 blocks). `/readyz` was gated on chain reachability. |
| **v2** | The broker refreshes a registry snapshot every `cbqs.snapshot_refresh_ms` (default 2s) and serves from it. A failed refresh does not stop service and does not make the broker unready; it raises a `degraded` flag and a snapshot-age gauge. The only thing refused during an outage is a session for a stream the snapshot has never seen (`StreamUnknownToBroker`, 3950). |
| **Why** | This is the brief, literally: the queue runs without the chain. It also removes the failure mode where a consensus stall takes the whole messaging fabric down — the fabric that agent coordination runs on. |
| **Cost** | Revocation and suspension reach an *established* session within one refresh interval under normal operation, and not at all during a chain outage. Two bounds keep that from being unbounded: `cbqs.max_snapshot_age_blocks` refuses *new* sessions against a stale snapshot — which is what binds a broker that never refreshes on purpose — and `cbqs.max_grant_ttl_ms` caps how long any outstanding grant survives. CIP-39 §3, §7 and Security Considerations state this rather than hiding it. |

### 2. Billing moves from per-stream capacity pricing to a flat per-account balance

| | |
| --- | --- |
| **v1** | Three priced capacity dimensions per stream; two admission paths (a provider-signed `PriceQuoteV1` or a genesis-frozen `BaseRateScheduleV1`); a `pricing_generation`; four per-provider reservation counters with four matching caps; per-stream `escrow_balance`; a creation charge of `rate × 604,800`; a pinned `suspension_grace_deadline_block`; a `DataExpired` status. |
| **v2** | One governance parameter `cbqs.stream_rate_per_block`, **snapshotted into each stream record at creation** so a later write is prospective; one prepaid balance per **owner**; a flat `CBQS_STREAM_CREATION_CHARGE` protocol constant debited from the native account; and three statuses (`Active`/`Suspended`/`Closed`), where `Suspended` stops the meter. `settle()` is about twenty lines including the suspended branch. |
| **Why** | A capacity market implemented inside consensus is what most of the registry's state, most of its instructions, and most of its failure modes were for. Capacity is bounded instead by per-stream ceilings the broker already has to enforce, plus each provider's own `max_streams` and `accepts_new`. |
| **Cost** | Three, all now stated in the CIP rather than left to be found: no price discrimination (a heavy and a light stream pay the same); no way to reprice an existing stream, since the rate is snapshotted; and a provider's collectible is no longer isolated from the owner's other streams, so settlement cadence replaces escrow as its protection and the broker's availability check has to be conservative (`balance >= due × active_streams`). |
| **Also fixed** | v1's `CBQS_MIN_RATE_PER_BLOCK = 8_000 // wei per block` disagreed with v1 §4.5's "rates are denominated in nano-CBY" by nine orders of magnitude — the implementation (`node/execution/src/cbqs/storage.rs:44`) reads nano-CBY. v2 says nano-CBY once, in one place. |

### 3. Stream configuration leaves the chain

| | |
| --- | --- |
| **v1** | `StreamConfigV1` (12 fields) is consensus state, validated field-by-field against a table with two different sources of truth (LIVE governance scalars vs IMMUTABLE §18 maxima), plus a cross-field rule (`max_message_bytes × fast_batch_max_records ≤ 256 MiB`) and a cross-record invariant tying a key stream's retention to its main stream's. |
| **v2** | Retention, message size, throughput, visibility, and attempt defaults are **broker settings** (`SetStreamSettings`, `STREAM_ADMIN` verb), each validated against one named governance ceiling. The chain holds no stream configuration. |
| **Why** | These are enforced by the broker and observed by the broker. On chain they made every tuning change a transaction and produced the validation table, the cross-field rule, and the cross-record invariant — three sources of bugs for a knob a broker API can set. |
| **Cost** | Configuration is no longer publicly auditable from chain state. Ceilings still are, and they are what bound a provider's exposure. |

### 4. Per-message signatures and per-message `fsync` become per-batch

| | |
| --- | --- |
| **v1** | Every request — including reads — carries a `RequestProofV1` Ed25519 signature the broker verifies. Every append returns a broker-signed `AppendReceiptV1` after a synchronous durable commit, threaded into a global **and** a per-lane hash chain. Every `Ack`/`Nack`/`Extend`/`Reject`/`Redrive`/group mutation (12 actions) returns its own signed receipt on its own chain. |
| **v2** | Proof of possession happens **once**, at session open. Appends are committed in group-commit batches (`cbqs.commit_batch_max_ms` = 20ms, `commit_batch_max_records` = 1024), and one `CheckpointReceiptV2` is signed per batch over a flat `records_digest` linked to the previous checkpoint. |
| **Why** | This — not the chain — is the throughput ceiling. v1 pays, end-to-end per message, two client signatures, two broker verifications, two broker signatures, and two synchronous durable commits — one set for the append, one for the acknowledgement. v2 pays one broker signature and one durable commit per *batch*, and no asymmetric cryptography per request. Group commit is how ordinary brokers reach their numbers. |
| **Cost** | Evidence granularity drops from a record to a batch, and a client can no longer prove *which* record inside a committed batch was tampered with — only that the batch's digest does not match. Given that v1 has no dispute or slashing path (its own §2 says so), the finer evidence had no enforcement to feed. |

### 5. The `fast` delivery class is deferred

| | |
| --- | --- |
| **v1** | A second class with provisional acknowledgement, `broker_epoch`, `FastLineageV1`, `BrokerEpochTransitionV1` with `Clean`/`Void` semantics, provisional and durable watermarks, lineage adoption, and a normative CRDT resynchronisation procedure. |
| **v2** | One class. The `fast` class moves to a follow-up CIP. |
| **Why** | Two durability models, two crash-recovery paths, and two identifier shapes in one document before either had a user. |
| **Cost** | Presence and CRDT workloads pay durable-commit latency (one batch window, ~20ms) instead of provisional acknowledgement. That is a real regression for Yjs-style presence and is the item most likely to need reinstating first. |

### 6. Lane-partitioned Merkle proofs are deferred with it

| | |
| --- | --- |
| **v1** | `merkle_root_v1` (odd-node promotion, with a written argument about length ambiguity), `sparse_root_v1` (fixed-depth-256 sparse tree, bitmap proofs, canonical descent, empty-subtree constants), per-lane presence/absence proofs per batch, omission detection, verifying-subscription batch ordering, and two verification modes — about 400 lines. |
| **v2** | One flat `records_digest` per batch. §11 states plainly that a lane-scoped subscriber cannot verify a checkpoint, and that the workaround is one stream per verification domain. |
| **Why** | The mechanism detects a real defect (silent per-lane omission) that nothing in v1 can act on: no dispute, no staking, no slashing, and v1's own remedy for a failed provider is "migrate away". |
| **Cost** | Stated, not hidden: lane-scoped verification is unavailable. Reinstating it belongs with the dispute path that makes detection actionable. |

### 7. Platform encryption and key rotation leave the protocol

| | |
| --- | --- |
| **v1** | XChaCha20-Poly1305 record encryption, HPKE per-member envelopes, a `stream_root` escrowed in CBSS, a rotation actor, `KeyRotationBatchV1` with three-step chunked upload, `KeyBatchReceiptV1`, an `ActivateKeyGeneration` **chain instruction**, an `encryption_generation` on chain, and a second chain-created **key stream** per encrypted stream with atomic lifecycle and a cross-stream retention invariant. |
| **v2** | Payloads are opaque bytes. Applications encrypt before appending and distribute keys themselves (CBSS remains available to them as an ordinary service). |
| **Why** | It removes a chain instruction, a chain object, a chain generation counter, a hard CIP-24 dependency, and the only cross-record invariant left in the registry. |
| **Cost** | The platform no longer offers managed membership encryption; an application that does not encrypt has handed its provider plaintext. Security Considerations says exactly that. |

### 8. Receipt families collapse from 14 signed object types to 3

v1 defined a signing registry of 14: price quote, grant, session proof, request
proof, key-rotation batch, key-batch receipt, broker-epoch transition, checkpoint,
append receipt, delivery-state receipt, snapshot manifest, and three retention
anchors. v2 signs three: `StreamGrantV2`, `SessionProofV2`, `CheckpointReceiptV2`.
Retention floors become a `u64` in an error payload; the rest went with the
features above.

### 9. Endpoint validation leaves consensus

v1 ran a five-rule algorithm at consensus admission — forbidden-byte scan, a
byte-exact scheme compare with a two-paragraph erratum, a WHATWG URL parse, a
raw authority scan for `@`, and IPv4/IPv6 special-range blocklists — pinned by
37 normative accept/reject vectors, about 160 lines. Any parse difference
between two node implementations is a consensus fork, and v1 concedes in the
same section that admission cannot check DNS, so **the client must revalidate
anyway**.

v2 keeps three byte-level rules — a bounded endpoint count, a bounded URI
length, and every byte in `0x21`–`0x7E` with a byte-exact `wss://` prefix — and
puts the address policy on the dialer (§11.4), where the resolved address is
actually known.

**The host grammar went in two stages, and the second is the more interesting
one.** The first draft of v2 replaced v1's parse-based rules with a written
grammar for the authority: canonical dotted-quad, RFC 5952 lowercase IPv6 in
brackets, DNS labels whose last label begins with a letter, and a port with no
leading zero and not 443. That was a real improvement over parsing — a grammar
has no dependency on a URL library's quirks — and it survived ten rounds of
review.

Round 11's determinism lens then proved it was itself a live fork. "The
canonical lowercase form of RFC 5952" does not name one form: RFC 5952 §5
leaves the mixed hex/dot-decimal notation for IPv4-mapped addresses a
*recommendation*, so the two mainstream standard libraries disagree — Rust
renders `::ffff:c000:201` as `::ffff:192.0.2.1`, and Python renders
`::ffff:192.0.2.1` as `::ffff:c000:201`. Any sane implementation of "is this
text canonical" is parse-then-reformat-then-compare, so a Rust validator admits
a `RegisterProvider` a Python validator rejects. Both honestly implement the
sentence. None of the vectors in the block would have caught it, because none
was in that address class.

The obvious repair was to hand-write an IPv6 grammar. Instead the whole rule was
deleted, on the ground that it was never buying anything: consensus **stores**
this field and never interprets it — no rule compares two endpoints, no handler
resolves one — and the only reader that acts on it is a client deciding where
to dial, which §11.4 governs after resolution on the address actually reached.
Every vector the grammar existed for lands somewhere §11.4 already covers:
`wss://0251.0376.0251.0376/ws` is a link-local address to a parser and an
ordinary name to a byte scanner, and §11.4 rejects the first outright and
rejects whatever the second resolves to.

What is given up is stated in the CIP: consensus no longer guarantees that a
registered endpoint is syntactically dialable. A provider that registers
nonsense has burned its own 5 CBY registration charge and is unreachable —
self-harm, priced, and visible. What is gained is about a hundred lines and the
**whole fork class** rather than one instance of it, plus one fewer thing every
validator implementation has to get bit-identical.

### 10. Lanes stop carrying protocol machinery

Lanes stay — one stream per wiki page is the wrong shape and always was. What
leaves is everything bolted onto them: per-lane receipt chains, per-lane retention
anchors, per-lane Merkle proofs, provider-event records for lane create/close
(`LaneEventV1`, with its synthetic message id and origin/kind enums), and the
per-grant lane-creation rate caveat. Topology discovery is `ListLanes`.

### 11. One event per instruction

v1 had 12 event topics and a normative "net status edge" rule to disambiguate the
two settlements inside `TopUpStream`. v2 has 8 topics, exactly one per
instruction, and no status events at all: a consumer that needs to know whether a
settlement suspended or revived a stream reads `status` from `0x17` at that block,
which v1's own §19 already established as the pattern.

### 12. Application guidance leaves the specification

v1 §16.2 specified Homestead — a product — including its 463-page synthetic
fixture, which lane types should use which verification mode, and how its search
workload should be authorized. That is application design, and it is gone.

## 3. Before / after

Every number is derived from the two documents, not asserted, and recomputed at
each round. Reproduce from a `cowboy` checkout on `spec/cip-39-v2` with
[`cip39_metrics.py`](cip39_metrics.py) beside this file, run against
`origin/main`'s copy of the document as v1.

| Metric | v1 | v2 | Δ |
| --- | ---: | ---: | ---: |
| Specification lines | 4,827 | 2,923 | −39% |
| RFC-2119 `MUST` occurrences | 331 | 139 | −58% |
| — of which `MUST NOT` | 66 | 21 | −68% |
| Chain instructions | 9 | 8 | −1 |
| `StreamRecord` fields | 26 | 9 | −65% |
| `StreamConfig` fields on chain | 12 | 0 | −100% |
| `RecordHeader` fields | 10 | 5 | −50% |
| Signed object types | 14 | 3 | −79% |
| Governance parameters | 56 | 34 | −39% |
| — of which genesis-frozen, never read live | 12 | 0 | — |
| — named in the per-instruction state-read table | n/a | 4 | — |
| Chain events | 12 | 8 | −33% |
| Typed error codes | 46 | 45 | −2% |
| State reads reserved across all instructions | 233 | 48 | −79% |
| State writes reserved across all instructions | 50 | 33 | −34% |
| `CreateStream` reads / writes | 34 / 11 | 11 / 8 | −68% / −27% |
| Required CIPs | 8 | 3 | −62% |
| Ed25519 verifications per appended message | 1 | 0 | — |
| Provider signatures per appended message | 1 | 1 per batch | up to 1,024 records/batch |
| Synchronous durable commits per appended message | 1 | 1 per batch | up to 1,024 records/batch |

Four rows deserve a note, because the headline number either understates or
overstates what actually changed.

**Error codes barely moved — 46 to 45 — and that is the honest number.** Three
v1 codes went with the base-rate machinery, and round 11 *added* two
(`MalformedFrame`, `SessionNotOpen`) for denial classes v1 named in its
precedence rule and never assigned, which meant the most common wire failure
had no number and `cbqsd` had invented `3998` outside the band. A simpler
protocol does not need fewer names for failures. It needs fewer ways to fail —
which is what the state and instruction rows measure.

**Governance parameters are 56, not the 44 an earlier draft of this document
reported.** That 44 excluded the twelve genesis-frozen `cbqs.base_rate.*` rows
and then listed them again as a sub-row, so it double-counted against itself.

**"Read by a consensus handler" is 4 for v2 and unstated for v1.** v2's §15.1
carries a per-instruction state-read table, so the number is mechanical:
`max_provider_endpoints`, `max_provider_endpoint_uri_bytes`,
`max_streams_per_account`, and `stream_rate_per_block`. v1 has no equivalent
table — its reserved-I/O table lists counts only — so an earlier draft's "25"
was not reproducible from the documents and has been withdrawn rather than
restated with a footnote.

**State writes fell far less than reads: −34% against −79%.** That gap is real
and worth naming, because it is the shape of the whole redesign. Reads
collapsed because authorization and configuration left consensus entirely. Writes
did not, because v2 moved *money* onto the chain path that v1 kept in
per-stream escrow: five of the eight instructions now touch custody, the
provider's native account, and the Platform Fee Account. Settlement is the one
thing that has to stay on chain, and it is what the remaining writes are.

Dependencies dropped: CIP-9 (CBFS), CIP-24 (CBSS), CIP-36 (administered CBY
rate), and CIP-2/CIP-10 as *requirements* (they remain related — runner
workloads are CBQS clients). v2 requires CIP-3, CIP-12, and CIP-31 §4 for the
Platform Fee Account rule it cites.

The figures are lower than the first draft's because the deep review put ~570
lines back: the effective-rent-height definition, the signing registry, the
request-body table, the address ranges §11.4 now enumerates, the group-config
validity rules, and the conformance items. Simplification that deletes a
definition another rule depends on is not simplification — §9 records which
deletions the review reversed and why.

## 4. What was deliberately kept

Simplification is not deletion, and these survived on purpose:

- **Chain-controlled authorization.** Grants signed by an on-chain admin key with
  a generation counter. Without it CBQS is a broker with a private customer table,
  not a Cowboy service.
- **Provider registry with consent.** `accepts_new` and `max_streams`, so a
  permissionless registry cannot commit a provider past its capacity.
- **At-least-once semantics in full.** Leases, visibility timeouts, attempts,
  dead-letter, redrive, strict-FIFO, idempotent append. A work queue without these
  is not a work queue.
- **Credit-based flow control**, because backpressure has to be explicit.
- **Durable-before-ack**, because the alternative is silent loss.
- **The custody discipline.** Every credit is debited from custody in the same
  transition; handlers fail closed rather than mint.
- **Gas vectors as a normative artifact**, regenerated as
  `cip-39-gas-vectors-v2.json` and pinned by SHA-256 in §15.1.

## 5. Activation

CBQS has never activated on a network whose state must be preserved, and v1
already declared itself reset-only and pre-launch (v1 §13.2). v2 therefore
activates as a **reset, not a migration**, and CIP-39 §19 states the five rules:
genesis seeds the singleton and every §16 parameter and no base-rate schedule
and validates the two economic invariants; genesis validation rejects any of the
29 retired `cbqs.*` keys, **named individually** so a validator can be built from
the document alone; handlers reject a `SYS_CBQS` payload whose version byte is
not `2`; decoders reject stored records whose version byte is not `2` — §4 gives
every stored record that byte precisely so the rule has a referent; and a broker
store carries a `cbqs/store-format = 2` marker that a v2 broker refuses to open
without.

Every canonical object carries `version = 2`, so nothing v1 wrote can be
misread as v2 — the failure mode is a decode rejection, which is the one we want.

## 6. Cross-document changes in this branch

A specification change that leaves sibling documents asserting the old design is
drift, so the same branch carries:

| File | Change |
| --- | --- |
| `docs/cips/cip-39-cowboy-queue-system.md` | Rewritten as document version 2. |
| `docs/cips/cip-39-gas-vectors-v2.json` | New; 27 vectors over 8 instructions — 19 success paths and 8 rejection paths — pinned by SHA-256 in §15.1. |
| `docs/cips/cip-39-gas-vectors-v1.json` | Deleted — it pins nine instructions that no longer exist. |
| `docs/cips/cip-36-phased-launch-cusd.md` | Two statements about CIP-39 that v2 falsifies: "CBQS reserved capacity" and "CIP-39's schedule is genesis-frozen and carries no band". |
| `docs/cips/cip-42-statusz.md` | Its worked example said a cbqsd that cannot read chain state is `unhealthy`; under §18 that condition is `degraded`. |
| `docs/whitepaper/cowboy-technical-whitepaper.md` | The `0x17` row said "pricing, escrow custody"; it is now prepaid-balance custody. |
| `docs/whitepaper/cowboy-cbqs-whitepaper.md` | Status note: this whitepaper describes v1, CIP-39 is authoritative where they disagree, with a section-level map of what v2 removed. A full rewrite is deferred (W6). |
| `docs/whitepaper/changelog.md` | Entry for both whitepaper changes. |

## 6a. One observation handed back rather than acted on

CIP-12 §7's pausable-actor allowlist is `{0x04, 0x05, 0x06, 0x07, 0x08, 0x0C,
0x0D, 0x0E, 0x0F, 0x10, 0x13, 0x14, 0x1D, 0x1E}`, while the implementation it
cites (`node/types/src/pause.rs`, `PAUSABLE_LOW_BYTES`) admits **every address
in `0x01`–`0x1E` except `0x09` and `0x11`**, and its comment calls those two
"the only two, final" — which the CIP's own exclusion rationale contradicts for
`0x01`–`0x03`, `0x0A`, `0x0B`, and `0x12`.

An earlier revision of this branch amended that list. The amendment has been
**reverted**, for two reasons. CIP-39 v2 no longer depends on `0x17` being
pausable — the rent clock that needed it is gone — so the change had lost its
justification and would have left a governance surface citing a rule that does
not exist. And which document is right about the other six addresses is CIP-12's
question, not something a queue CIP should settle as a side effect.

It is recorded here so it is not lost.

## 7. Implementation work breakdown

Sizes are the **current** size of each module the item touches, not a promise of
how many lines get deleted.

| # | Work item | Modules | Current size | Consensus? |
| --- | --- | --- | ---: | --- |
| W1 | Session-level auth; drop `RequestProofV1`; drop the long-poll binding | `cbqsd/src/session.rs`, `transport/connection.rs`, `codec::cbqs` | ~5.1k | no |
| W2 | Group commit + one checkpoint per batch; delete per-record and per-action receipt chains | `cbqsd/src/receipt.rs`, `standard_append.rs`, `standard_delivery.rs`, `storage.rs` | ~10.2k | no |
| W3 | Delete the `fast` class and the lane-proof machinery | `cbqsd/src/transport/fast.rs`, proof paths in `codec::cbqs` | ~2.0k + codec | no |
| W4 | Registry rewrite: flat account billing, drop config/quote/schedule/reservations, 8 instructions, 8 events | `node/execution/src/cbqs/*`, `node/cbqs/*`, `codec::cbqs` | 9.4k + 1.7k + 11.0k | **yes — reset** |
| W5 | Snapshot-based authorization; degraded mode; `/readyz` semantics | `cbqsd/src/broker_state.rs`, `authorization.rs`, `transport/chain.rs`, `transport/ops.rs` | ~1.8k | no |
| W6 | Rewrite the CBQS whitepaper against v2 | `docs/whitepaper/cowboy-cbqs-whitepaper.md` | 1.5k | no |
| W7 | Update the downstream repo docs that publish v1 semantics | `cbqs/README.md`, `cowboy-protocol/crates/cowboy-protocol-cbqs-wasm/README.md` | ~0.4k | no |

W7 is deliberately **not** in this branch: those files live in other
repositories, and their claims (end-to-end encryption by default, per-request
signatures, two delivery classes, `/frames` long-poll, `/readyz` gated on chain
reachability, and four CIP-39 section citations that v2 renumbers) become false
only when v2 is accepted. They ship with the implementation PRs that make them
true. Listing them here is the commitment; the review found them, and leaving
them unlisted would have been the drift.

W1, W2, W3, and W5 are broker-only and can land before W4. W4 is the flag-day and
should land as one commit against a fresh devnet genesis.

The existing test suites are the risk, not the source: `cbqsd` carries ~16k lines
of tests and `node/execution/src/cbqs` ~6.6k, much of it pinned to surfaces v2
deletes. Expect the test delta to exceed the source delta.

## 8. Open questions for the customer

These are decisions we should not make unilaterally:

1. **Is `fast` needed for the first release?** If Homestead presence ships on
   CBQS, item 5 is a regression they will feel, and the answer changes the
   sequencing of W3.
2. **Is managed encryption a product requirement?** Item 7 assumes applications
   own their keys. If the platform must offer it, it should come back as its own
   CIP over an opaque-payload core rather than woven into the registry.
3. **Is flat pricing acceptable for v1**, or do we need two or three tiers on day
   one? Tiers are a small, additive change to §6; capacity-priced quotes are not.
4. **Who operates providers at launch?** If the answer is "only us", the
   provider-consent counters (`accepts_new`, `max_streams`) could also go.

## 9. What the deep review changed

This rewrite has been through **twelve rounds** of Marshal deep review — six
adversarial lenses per round (correctness, spec coherence, cross-repo,
security, economics, determinism), each round followed by a fix pass and a
fresh review of the fixes. Every round found something. That is the honest
headline, and the pattern underneath it is the part worth recording, because it
is the risk profile of any simplification pass.

**Most early findings were deletions of machinery that something else still
depended on** — not bad new design. Six were reversed in the first fix pass:

| Deleted in the first draft | Why it had to come back |
| --- | --- |
| `coverage(H)` / effective rent height and the pause-accounting record | §6 still subtracted CIP-12 pause coverage. Without the formula two honest nodes compute different `due`, i.e. different balances — a state fork. Worse, stored heights ended up on a different clock from `H`, so `require H >= last_settled_block` could fail permanently, which wedges `CloseStream`, which pins `active_streams` above zero, which locks the owner's balance forever. |
| The signing-domain registry | v2 named three signing functions and defined no preimage for any of them. |
| Per-stream rate snapshotting | Reading the rate live meant a governance write retroactively rebilled every unsettled interval on the network at the new rate. |
| Request bodies and the `session_id` on request frames | Removing per-request signatures removed the only field binding a request to its authenticated session. |
| `max_lane_creates_per_min` and a staleness bound | Their absence let one holder burn a stream's permanent lane namespace, and let a broker that simply never refreshes ignore every revocation forever. |
| Per-group visibility ceiling and a per-record deadline | Without them one never-acknowledging group could hold delivery state open indefinitely. (The retention half of this was later solved differently: §12's floor now advances on time or bytes without consulting group state at all, so no group can pin it.) |

**Later rounds found a different and more instructive failure: the fixes
themselves.** Five distinct shapes recurred often enough to be named, and all
five are shapes a human reviewer of a large specification should expect.

1. **A stale restatement survives the fix.** Rounds 6 through 11 each left at
   least one. The worst case took six rounds to die: §9.2's "Live records MUST
   NOT be evicted under capacity pressure; the broker returns `Backpressure`
   instead" was the authority §12 cited, and when §12 was rewritten to evict on
   a byte bound, the sentence stayed. A round-10 sweep declared it absent
   because it grepped `"under pressure"` and the text reads `"under capacity
   pressure"`. Three lenses found it independently in round 11.
2. **A recommendation lands as the shortest possible edit** and loses the
   property it was meant to add.
3. **The fix breaks a neighbour.** Round 11 introduced a blank line that
   silently split seven of the eight rows out of the chain-instruction table,
   and inserted a sentence into a run of two that a following sentence counts
   as "these two rules".
4. **A count goes stale when the thing counted changes.** Round 10 rewrote a
   rule from "four checks" to "three rejections" and left §19 asserting four.
5. **A rationale outlives the design it justifies.** Several paragraphs
   correctly stated a rule while explaining it by a hazard a later round had
   already removed — true conclusion, dead argument.

The countermeasure that worked was not more care. It was a mechanical
pre-commit sweep that greps **the concept keywords of every rule changed** and
checks every hit, plus structural checks for tables, list indentation, and
counted self-claims. The sweep is in the process, not in anyone's intentions.

**Round 11 also produced the largest single simplification of the whole pass,
and it came from a defect.** The determinism lens proved that §4.1's endpoint
host grammar was a live consensus fork: "the canonical lowercase form of RFC
5952" is not one form, because RFC 5952 §5 leaves the mixed notation for
IPv4-mapped addresses a recommendation, so Rust and Python canonicalise
`::ffff:192.0.2.1` in opposite directions. Two honest validators admit
different `RegisterProvider` bytes. The obvious repair was to hand-write an
IPv6 grammar. Instead the whole rule was deleted: consensus stores the endpoint
and never interprets it, and §11.4 already governs dialing after resolution, on
the address actually reached. That removed about a hundred lines and the entire
fork class rather than one instance of it — the clearest example in this pass
of a defect report pointing at a deletion rather than an addition.

**Three new rules were added that version 1 did not have**, because pooling the
balance created exposures per-stream escrow did not have:

- the broker's availability check multiplies by `active_streams`, so one
  stream's funding cannot buy service on an owner's whole fleet;
- a suspended account stops accruing rent, so an abandoned stream does not
  compound a bill for months of non-service; and
- the assigned provider may close a stream whose account cannot fund the next
  block (§5.1), so a provider is not held to an owner who has stopped
  participating.

**Two economic properties are stated as costs rather than left to be
discovered**: a provider's collectible is no longer isolated from the owner's
other streams, so settlement cadence replaces escrow as its protection; and
snapshotting the rate means v2 has no way to reprice an existing stream.

## 10. Self-review against the review gate

Checked before proposing, since these are the classes that usually survive into a
spec PR:

- **Consensus change is stated, not implied.** §19 rules 1–5, with the reset
  precedent quoted from v1's own text.
- **Encoding injectivity.** Every option keeps an explicit presence tag; §4 states
  that two distinct values must not share canonical bytes.
- **No number restated from another document.** v2 quotes no USD figure and no
  CIP-31/CIP-36 constant; `0x18` is cited to CIP-31 §4, which was read to confirm
  it (`docs/cips/cip-31-cbfs-rent-schedule.md:71,86`).
- **No unobservable `MUST`.** §19 lists the conformance surface, and every
  normative rule resolves to chain state, canonical bytes, or a broker response.
- **No derived-instead-of-enumerated gate.** §14 names each setting's ceiling in a
  table rather than saying "validated against its §16 ceiling".
- **No redundant field that can disagree with itself.** `record_count` was dropped
  from `CheckpointReceiptV2` because it is `last - first + 1`.
- **No dead future-proofing.** The single-variant transport enum and `provider_epoch`
  (fixed at zero in v1) are gone; the pinned-but-unwritable `pending` schedule went
  with the schedule.
- **Pinned artifact digest verified after generation**, not asserted:
  `sha256sum docs/cips/cip-39-gas-vectors-v2.json` matches §15.1.
- **Sibling documents reconciled** (§6 above), including the whitepaper that would
  otherwise have kept describing v1 with no marker.
