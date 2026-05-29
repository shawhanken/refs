## Part II — v2 Proposed Deltas (forward-looking; verbatim from former `wp-aligned-deltas.md`)

# Whitepaper Aligned Deltas — CIP-14 / CIP-15 / CIP-16 alignment exercise

**Status:** Proposal (non-modifying companion to `refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised.md`)
**Created:** 2026-04-21
**Scope:** Five proposed additions to a future WP revision, surfaced by the `cip-14-dns-addressable-actors-v2.md` (Part II) / `cip-15-public-asset-hosting-v2.md` (Part II) / `cip-16-custom-domains-v2.md` (Part II) drafting exercise.

This document does not modify the WP. It is a structured proposal for content additions when the WP is next revised.

---

## 0. Why deltas, not a full aligned WP

The Cowboy technical WP (`2026-03-21_cowboy-technical-whitepaper-revised.md`, 1064 lines) is a stable architectural document. Producing a full "aligned WP" would mostly duplicate untouched material and add little.

Instead, this document captures only the additions the alignment exercise surfaced. Each delta is framed as a proposed insertion into a specific WP section, with rationale grounded in the aligned drafts and the codebase positions they reference.

When the WP is next revised, these deltas can be merged in directly. The five deltas correspond one-to-one with the open WP-level questions in Part III of this document §9.

---

## Delta 1 — Stake vs. operating balance separation

### Proposed insertion: §17.x (Runner Marketplace)

WP §17 discusses runner stake, slashing, and rate cards. It implicitly conflates stake with the runner's spendable balance. CIP-14-aligned makes the separation explicit for Gateways; the WP should generalize.

#### Proposed text

> **§17.x — Service-providing nodes: stake vs. operating balance**
>
> Every service-providing node (Runner per CIP-2, Gateway per CIP-14, Relay Node per CIP-9) maintains two distinct balance categories:
>
> - **Stake**: locked CBY held in the relevant registry — `RUNNER_REGISTRY=0x01` (CIP-2), `GATEWAY_REGISTRY=0x0E` (CIP-14), `RELAY_REGISTRY=0x0B` (CIP-9). Slashable per the registry's failure rules. Withdrawable only after an unstaking delay.
> - **Operating balance**: spendable CBY held in the node's operating account. Pays gas for transactions the node submits — result submission, ingress dispatch, storage commitments, heartbeats. Refilled from earned fees and protocol rewards.
>
> These categories MUST NOT be conflated in protocol logic:
>
> - Gas-payment debits MUST come from operating balance only. A node whose operating balance is empty cannot transact regardless of stake size.
> - Slashing MUST debit stake only. A node whose stake covers an operating shortfall is undercollateralized — its `is_active` predicate MUST return false until the shortfall is resolved.
> - Stake is typically locked in the registry actor's state, not in a freely-spendable account; transferring out for fee payment is not a supported path.

### Rationale

CIP-14-aligned §6.3 invoked this separation explicitly when correcting the original CIP-14's "Gateway pays from stake" claim. The same constraint applies to runners (`RUNNER_REGISTRY` already enforces it) and relays (`RELAY_REGISTRY` already enforces it). Surfacing it at WP-level prevents future CIPs from making the same conflation.

---

## Delta 2 — Read-only handler execution as protocol primitive

### Proposed insertion: §6.x (PVM Execution)

WP §6 describes per-actor handler invocation under transaction execution. It does not establish that the same PVM contract supports a read-only invocation mode without a transaction.

#### Proposed text

> **§6.x — Read-only handler execution**
>
> The PVM defines two execution modes for actor handlers:
>
> - **Transactional**: invoked via `ActorMessage`; executes against speculative state; emits side effects (state writes, messages, events, jobs); consumes Cycles + Cells charged to the transaction's fee payer.
> - **Read-only**: invoked via the `read_handler` RPC (CIP-14-aligned §5); executes against committed state; all mutating syscalls trap with `ERR_READONLY_VIOLATION`; consumes Cycles only (caller-absorbed); returns the handler's serialized response.
>
> The trap list is normative. Permitted syscalls in read-only mode: `state_get`, `state_scan_prefix`, plus ambient context (`block_height`, `block_timestamp`, `self_address`). `caller` returns the zero address; `ctx.sender` returns null. **All other syscalls trap immediately.** This includes `randomness` and `emit_event` — both are protocol-observable side effects that have no meaning outside transaction context.
>
> Read-only execution MUST be deterministic across nodes against the same committed state root: two nodes serving the same `read_handler` request at the same `block_height` MUST return byte-identical responses. This determinism property is what permits Gateways (CIP-14) and other future read-relay roles to serve responses without re-executing through consensus.

### Rationale

CIP-14-aligned depends on read-only PVM execution as a protocol-level safety property, not an RPC-layer convenience. Browsers calling `GET myagent.cowboy.network/api/profile` cross multiple Gateways; without protocol-defined determinism, those Gateways can return inconsistent results for the same height. This belongs in the WP execution chapter, alongside the transactional mode's spec.

The original CIP-14 §11.3 omitted `randomness` from the trapped list — `randomness` is exposed at `pvm_host.rs:1372` and would have allowed read-path divergence. The aligned trap list closes this and the WP should reflect it.

---

## Delta 3 — Deferred result storage primitive

### Proposed insertion: §9.x (System Actors)

WP §9 lists Runner Registry, Job Dispatcher, Result Verifier, etc. The WP does not surface the "deferred result storage" pattern as a recurring primitive that future system actors will inherit.

#### Proposed text

> **§9.x — Deferred result storage**
>
> System actors that mediate third-party calls — `GATEWAY_REGISTRY=0x0E` for HTTP ingress (CIP-14), and future system actors for cross-chain bridges, oracle dispatch, sealed bid auctions — generate responses asynchronously. Result storage SHOULD follow a common pattern:
>
> - A dedicated registry actor (e.g., `RECEIPT_REGISTRY=0x0F` for HTTP) owns the result records. Keyed by `request_id`; records carry `target`, `status`, `payload` (when complete), `created_at`, `expires_at`.
> - A single registry-wide pruning loop expires records via TTL. **Per-target timer budgets are NOT consumed.** This avoids the failure mode where a popular `target` exhausts its `MAX_TIMERS_PER_ACTOR=1024` budget within ~1k pending requests.
> - Reads go through the standard `read_handler` RPC against the registry actor — no special "result polling" RPC needed.
>
> Privacy-sensitive results MAY restrict reads to the original mediating gateway (e.g., the dispatching `Gateway` for HTTP receipts).

### Rationale

CIP-14-aligned §8 introduced this as a one-off for HTTP receipts. The constraint generalizes: any future system actor mediating fan-in / fan-out from external sources will hit the same `MAX_TIMERS_PER_ACTOR` ceiling if it pushes receipt management onto target actors. Documenting the pattern at WP level makes "use a registry" the obvious default for new mediating system actors.

---

## Delta 4 — System-mediated message authenticity (revised; selector reservation withdrawn)

> **Note.** An earlier WP-v2 draft of this delta proposed adding a "system-reserved selectors" mechanism (the PVM router would reject non-system senders for reserved selectors like `"http.request"`). That proposal was withdrawn in CIP-14 v2 §6.2 because it broke router-actor forwarding patterns. The revised delta below describes the actually-canonical approach: handler-side `ctx.sender` checks against the canonical sender table.

### Proposed insertion: §6.y (PVM Execution)

WP §6 describes message routing but does not establish that selectors can be system-reserved at the routing layer.

#### Proposed text

> **§6.y — System-reserved selectors**
>
> The PVM message router supports **selector reservation**: a method name (e.g., `"http.request"`) is reserved at the protocol layer such that only specified system actors may emit messages with that selector. Non-system attempts to send a reserved selector are rejected at routing time with `ERR_RESERVED_SELECTOR`.
>
> When an actor receives a message with a reserved selector, the message necessarily originated from a permitted system actor — verifiable by the receiver via `ctx.sender`. This makes the receiver-side identity check a protocol invariant rather than an SDK convention.
>
> Reserved selectors and their permitted senders form a registry analogous to the entitlement registry — append-only, governance-managed, normative.
>
> Initial reservations:
>
> - `"http.request"` — permitted senders: `GATEWAY_REGISTRY=0x0E` (CIP-14-aligned §6.2). Used for system-mediated HTTP command-path dispatch.
> - `"_dns.callback"` — permitted senders: `RESULT_VERIFIER=0x03` (CIP-16-aligned §5.6). Used for system-mediated external-domain verification callbacks.
>
> Reserving a selector is a protocol-level action. New reservations require governance approval and are added to the canonical reservation registry (analogous to adding entries to the entitlement registry).

### Rationale

CIP-14-aligned §6.2 and CIP-16-aligned §5.6 both depend on this pattern. Without it, ingress authenticity and verifier callback authenticity rely on SDK-side `ctx.sender` checks that custom-bytecode actors can ignore. Lifting selector reservation to a normative WP construct removes the SDK-vs-protocol gap and gives future system actors a canonical mechanism for trusted callbacks.

---

## Delta 5 — Owner-mutable per-actor configuration at STORAGE_MANAGER

### Proposed insertion: §9.y (System Actors)

WP §9 covers `STORAGE_MANAGER`'s role as the owner of `StorageCommitment` records. CIP-15-aligned uses `STORAGE_MANAGER` as the home for additional actor-owned configuration (route manifest, CORS config) that updates atomically with deploys. This pattern generalizes.

#### Proposed text

> **§9.y — Owner-mutable per-actor configuration at STORAGE_MANAGER**
>
> `STORAGE_MANAGER=0x0A` hosts per-actor configuration records that the actor's owner mutates by transaction. These records are NOT actor KV — they live in a separate keyspace under `STORAGE_MANAGER`, addressable by `(actor_address, config_kind)`.
>
> Initial config kinds:
>
> - `route_manifest` (CIP-15-aligned §4.1) — HTTP path → static / dynamic routing.
> - `cors_config` (CIP-15-aligned §7.1) — per-path CORS rules.
>
> Properties:
>
> - Mutated only by the actor's owner. Sender check enforced in `STORAGE_MANAGER` instruction handlers, not by SDK.
> - Atomically updatable in the same transaction as `commit_manifest` for the actor's volumes.
> - Read by Gateways and other consumers via the standard `read_handler` RPC against `STORAGE_MANAGER`.
>
> This pattern is a deliberate alternative to storing the same data in actor KV, which would force a `read_handler` call into the *actor* on every Gateway request just to discover routing — defeating the static-serving goal in CIP-15. Future configuration that fits the "deployment-scoped, owner-mutable, infrequently-changed, frequently-read" profile SHOULD follow the same pattern.

### Rationale

CIP-15-aligned moves route manifests out of CBFS volumes (where the original CIP-15 placed them) and into `STORAGE_MANAGER`. This generalizes to any "deployment-scoped, owner-mutable, infrequently-changed" configuration that Gateways or other system actors need to read frequently without invoking the actor itself.

---

## Delta 6 — System actor address allocation correction (WP §9)

### Proposed insertion: §9 amendment (replace existing 0x0A entry)

WP §9 (line 704) currently asserts `0x0A = Container Image Registry (CIP-10)`. This conflicts with the canonical code allocation in `node/runner/src/system_actors.rs:31`, which assigns `0x0A = STORAGE_MANAGER (CIP-9)`. The CIP-9 allocation is implemented and shipping; the WP §9 entry is stale.

WP §9 normative text already says "**If this whitepaper conflicts with CIP-2 on these allocations, CIP-2 is authoritative.**" — but it does not extend the same deference to CIP-9 / CIP-10. This delta does so.

#### Proposed text

> **§9.* — Corrected system actor allocation**
>
> The canonical low-byte system actor allocation, authoritative as `node/runner/src/system_actors.rs` and the CIP v2 series:
>
> | Address | Actor | Source |
> |---:|---|---|
> | `0x01` | Runner Registry | CIP-2 |
> | `0x02` | Job Dispatcher | CIP-2 |
> | `0x03` | Result Verifier | CIP-2 |
> | `0x04` | Secrets Manager | CIP-2 |
> | `0x05` | TEE Verifier | CIP-2 / CIP-23 v2 |
> | `0x06` | DualBasefee | CIP-3 |
> | `0x07` | Entitlement Registry | CIP-2 |
> | `0x08` | Treasury | CIP-2 |
> | `0x09` | Governance | CIP-12 |
> | `0x0A` | **Storage Manager (CIP-9)** — supersedes WP §9's prior "Container Image Registry" claim | CIP-9 |
> | `0x0B` | Relay Registry | CIP-9 |
> | `0x0C` | **Session Actor** (MPP session model; `system_actors.rs:35`) | CIP-8 (retroactive) |
> | `0x0D` | Route Registry | CIP-14 v2.r2 |
> | `0x0E` | Gateway Registry | CIP-14 v2.r2 |
> | `0x0F` | Receipt Registry | CIP-14 v2.r2 |
> | `0x10` | Container Registry | CIP-10 v2.r2 |
> | `0x11` | Payment Gate | CIP-18 r2 |
> | `0x12` | Stream Key Manager | CIP-7 r2 (was 0x06 in v1; conflicted with DUAL_BASEFEE — resolved 2026-05-11) |
>
> **Container Registry** (CIP-10 v2.r2 §1) is at `0x10`, NOT `0x0A`. WP §9 readers should treat the v1 WP table's `0x0A = Container Image Registry` entry as obsolete — code chose `0x0A` for `STORAGE_MANAGER` (CIP-9) because CIP-9 was implemented first and the conflict was resolved in code's favor.
>
> **2026-05-11 r2 shift:** `SESSION_ACTOR = 0x0C` was committed in code at `system_actors.rs:35` after the v2.r1 alignment round (which had drafted `0x0C` = `ROUTE_REGISTRY`). The v2 sequence shifted +1: CIP-14 v2.r2 (`0x0D`/`0x0E`/`0x0F`), CIP-10 v2.r2 (`0x10`), CIP-18 r2 (`0x11`). All four CIP files carry matching r2 revision notes.
>
> **Conflict resolution rule (revised):** If this WP conflicts with any deployed CIP on system actor allocations, the deployed CIP is authoritative; if no CIP is deployed for a contested address, the lowest-numbered CIP claiming the address wins.

### Rationale

WP §9's "0x0A = Container Image Registry" predates the CIP-9 implementation. Code took 0x0A for STORAGE_MANAGER because CIP-9 was further along. CIP-10 v2.r2 §1 reallocated Container Registry to `0x10` to resolve the collision, after CIP-14 v2.r2's `0x0D`/`0x0E`/`0x0F` block which itself shifted +1 around the code-committed `SESSION_ACTOR = 0x0C`. The WP needs to reflect what code did and how the v2 CIP family adapted.

---

## Delta 7 — Payment Layer (CIP-18 r2)

**Proposed WP section:** new §17.y after fee model

WP-v2 does not currently describe a payment layer. All `payment` references in Part I refer to **runner job settlement** (the 89/10/1 split inside CIP-2). Per-request external payment from non-Cowboy clients into actor endpoints — the entire CIP-18 r2 model — has no anchor in Part I.

Proposed §17.y:

> ### 17.y. Payment layer
>
> A dedicated payment layer (CIP-18 r2) makes HTTP-addressable actors monetizable. A new system actor **PaymentGate** at `0x11` holds per-actor `PaymentPolicy` records, escrowed budgets, prepaid passes, and epoch-subscription entitlements. Gateways enforce payment at the network edge under one or both wire formats — **MPP** (IETF `draft-ryan-httpauth-payment`, primary) and **x402** (Coinbase compatibility) — and normalize both into a wire-agnostic `PaymentIntent` before invoking `PaymentGate.settle_payment`.
>
> Four payment models compose orthogonally:
> 1. **Per-request** (client pays at the edge with each call)
> 2. **Actor-funded** (actor pre-deposits a serving budget; clients pay nothing)
> 3. **Prepaid pass** (client purchases N call credits, redeems with each request)
> 4. **Epoch subscription** (rolling time-window unlimited access, reusing CIP-7 epoch primitives)
>
> Default protocol fee: **5%** (`PROTOCOL_PAYMENT_FEE_BPS = 500`). The remainder accrues to the actor's treasury. Inbound EVM-to-Cowboy bridge for ERC-20 stablecoin payments is specified by CIP-18 r2 §12 (deferred implementation; needs a new `bridge.facilitate.evm` runner entitlement).
>
> The MCP transport (CIP-19) reuses the same `PaymentIntent` over JSON-RPC `_meta.payment-authorization` with error code `-32402`.

### Rationale

The payment layer is now a load-bearing concern for actor monetization and agent-to-agent commerce. WP-v2 should acknowledge it at the architecture-overview level even though Parts II/III adopt-or-defer it via CIPs. Without this delta, the WP system-actor table (§9 / Delta 6) lists `PAYMENT_GATE = 0x11` without explaining why it exists.

---

## Delta 8 — MCP Ingress (CIP-19)

**Proposed WP section:** new §6.z after HTTP ingress

WP-v2 mentions "MCP tool calls" only as **outbound** (actors consuming external MCP servers via Runner). The reverse — actor-as-MCP-server, exposing Cowboy actors to every MCP-aware agent runtime as a native peer — is a new ingress pattern introduced by CIP-19 and unrepresented in Part I.

Proposed §6.z:

> ### 6.z. MCP Ingress (CIP-19)
>
> Every actor holding both `ingress.http` (CIP-14 v2.r2) and `ingress.mcp` (CIP-19) entitlements is automatically exposed as a Model Context Protocol (MCP) server at `https://<actor>.cowboy.network/_cowboy/mcp`. The Gateway terminates the MCP streamable HTTP transport (spec version `2025-11-25`), derives the `tools/list` deterministically from the actor's CIP-15 v2.r2 route table (one tool per Method-target route), and dispatches `tools/call` invocations through the same CIP-14 query / command paths an equivalent HTTP request would use. Actor handler code is unchanged.
>
> Payment gating reuses the CIP-18 r2 wire format over JSON-RPC `_meta.payment-authorization`. The MCP error code `-32402` mirrors HTTP `402`.
>
> Tool discovery is deterministic, verifiable, and on-chain-anchored — distinguishing Cowboy actors from MCP servers hosted on opaque infrastructure.

### Rationale

MCP is the standard interface between LLM agents and external tools. Treating every Cowboy actor as natively MCP-callable, with verifiable code and payable per-call, is a major architectural inflection that the WP should describe at the overview level.

---

## Delta 9 — Cross-Chain Architecture (CIP-25)

**Proposed WP section:** new §16.z, supplements existing §16

WP-v2 §16 "Bridge Infrastructure" says (line 830): "Cowboy relies on third-party bridge infrastructure for asset transfers and cross-chain message passing." and "Bridge selection and integration are determined by governance. The protocol does not implement its own bridge validator set."

CIP-25 (Cross-Chain Architecture) proposes a normative three-layer architecture — L1 (state anchoring with pluggable trust backends), L2 (mailbox messaging with exactly-once semantics), L3 (asset bridges, lending, oracles, generic calls) — and identifies **runner-attested committee** as one of four legitimate L1 backends (the others being ZK light client, optimistic, native light client).

These statements partially conflict: WP-v2 §16 says "no protocol-native validator set"; CIP-25 §1.4 + §A.5 says "runner-committee is a first-class backend." Tony's team's existing Cowboy→ETH withdrawal bridge already runs the runner-committee pattern in production, validating the design.

Proposed §16.z:

> ### 16.z. Cross-chain architecture (CIP-25)
>
> The protocol provides a layered cross-chain architecture (CIP-25) rather than relying solely on third-party bridges. Three orthogonal layers:
>
> 1. **L1 — State anchoring.** A pluggable interface (`IChainAnchor`) that exposes verifiable Merkle-proof reads of one chain's block commitments on another. Backends include (a) Cowboy-runner-attested committee, (b) ZK light client, (c) optimistic-with-fraud-window, (d) native light client. All backends produce the same `BlockCommitment` shape.
> 2. **L2 — Mailbox.** A symmetric typed message primitive `(src, dst, sender, recipient, nonce, payload)` providing exactly-once, per-sender-monotonic, integrity-preserving cross-chain delivery on top of any L1 backend.
> 3. **L3 — Applications.** Asset bridges (lock-mint / burn-release), cross-chain lending, oracle / inference relays (extending CIP-7 Watchtower streams cross-chain), generic cross-chain calls.
>
> Which backend is deployed for which chain-pair remains a **governance decision** per §16.2. CIP-25 standardizes the interface contract any backend must satisfy; it does **not** mandate the runner-committee backend protocol-wide. §16's "no protocol validator set" guarantee should be read narrowly as "no single mandatory bridge validator set"; the L1 interface admits both Cowboy-runner backends and pure third-party backends behind the same `IChainAnchor`.

### Rationale

Without this delta, the WP §16 statement and CIP-25's runner-committee proposal read as contradictory. Adding §16.z reframes them as complementary: WP §16 sets the **economic / governance policy** (no protocol-mandated bridge), CIP-25 sets the **architectural pattern** (any backend implements the same interface). Both hold.

---

## 6. Summary

| Delta | Proposed WP section | Required by |
|---|---|---|
| 1 — Stake vs. operating balance | §17.x | CIP-14-aligned §6.3; existing runner / relay practice |
| 2 — Read-only handler execution | §6.x | CIP-14-aligned §5 |
| 3 — Deferred result storage | §9.x | CIP-14-aligned §8 |
| 4 — System-mediated message authenticity (selector reservation withdrawn) | §6.y | CIP-14-aligned §6.2, CIP-16-aligned §5.6 |
| 5 — Owner-mutable config at STORAGE_MANAGER | §9.y | CIP-15-aligned §4.1, §7.1 |
| 6 — System actor address allocation correction (WP §9 0x0A) | §9 amendment | CIP-9, CIP-10 v2 §1 |
| **7 — Payment layer** | §17.y | CIP-18 r2, CIP-19 (companion) |
| **8 — MCP Ingress** | §6.z | CIP-19, CIP-15 v2.r2, CIP-18 r2 |
| **9 — Cross-chain architecture** | §16.z | CIP-25 (also addresses tension with current §16.2 third-party-bridge framing) |

These deltas are scoped to the v2.r2 alignment exercise. They do not address other potential WP revisions (CIP-13 actor-model delegation, CIP-23 TEE execution, CIP-21 liquidity pools, etc.); those would require separate analysis.

---

## 7. Out of scope

- A full re-write of the WP is not justified by CIP-14/15/16 alignment alone. Most of the WP (consensus, gas markets, upgrade governance, account model) remains accurate.
- Any rewording of the WP's framing of self-sovereignty in light of CIP-16-aligned §10 centralization risks (ACME, anycast edge, first-party TLD operation) is left for the WP authors. The brief in Part III of this document §8 surfaces the question; the right framing is editorial, not architectural.
- The Chinese-language WP variants in `refs/whitepaper/` are not addressed here. Whichever variant the project considers canonical should receive the same deltas.

---

