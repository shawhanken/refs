# Cowboy: Technical Whitepaper

| Field | Value |
|-------|-------|
| Status | Draft for internal review |
| Type | Standards Track |
| Category | Core |
| Author(s) | Cowboy Foundation |
| Created | 2025‑09‑17 |
| Updated | 2026‑02‑15 |
| License | CC0‑1.0 |

Note: This document provides complete technical specifications for Cowboy. For architec-
tural rationale and design decisions, see the Design Decisions Overview.

## 1.1 Abstract

Cowboy is a general-purpose Layer-1 blockchain that combines a Python-based actor-model
execution environment with a proof‑of‑stake consensus and a market for verifiable
off‑chain computation. Smart contracts on Cowboy are actors: Python programs with private
state, a mailbox for messages, and chain‑native timers for autonomous scheduling. For heavy
tasks like LLM inference or web requests, Cowboy integrates a decentralized network of Runners
who execute jobs and attest to results under selectable trust models: N-of-M consensus, TEEs,
and (in V2) ZK-proofs.

Cowboy introduces a dual-metered gas model, separating pricing for computation (Cycles)
and data (Cells) into independent, EIP-1559-style fee markets. Security is provided by Simplex
BFT consensus with proof‑of‑stake, fast finality, and mandatory proposer rotation.

This document specifies Cowboy’s complete technical architecture, state transition function,
economic mechanisms, consensus protocol, and all implementation parameters.

## 1.2 Introduction

Cowboy is designed to enable autonomous agents by providing a native blockchain execution
environment optimized for asynchronous, Python-based applications. This document provides
complete technical specifications for implementers, auditors, and protocol developers.

Ethereum gave us programmable money, but its execution model is fundamentally reactive —
smart contracts sit inert until an externally-controlled system calls them. Cowboy introduces a

new unit of execution: the actor, an immortal, stateful program that schedules itself into the
future, bids for its own blockspace, and runs indefinitely without a human in the loop. No amount
of keeper networks or cron-job infrastructure on Ethereum provides a first-class primitive for
autonomous, self-funding, self-scheduling programs. This new model requires a new protocol.

Cowboy further innovates by adopting Python as its execution language, replacing the domain-
specific languages required by existing chains (Solidity on Ethereum, Rust on Solana). Python’s
ubiquity in AI and general-purpose development reduces the barrier to entry for both human
developers and AI coding agents, which already generate Python more reliably than niche smart
contract languages.

For architectural rationale and design decisions, see the Design Decisions Overview.

## 1.3 Architectural Overview

This section is descriptive and non‑binding. Normative requirements are in §§1–17.

### 1.3.1 Terminology

- Actor: A Python program with persistent key/value state and a mailbox.
- Message: A datagram delivered to an actor handler.
- Cycle: Unit of metered on‑chain compute.
- Cell: Unit of metered bytes (1 cell = 1 byte).
- Runner: Off‑chain worker that executes a job and returns an attested result.
- Entitlement: A permission governing an actor’s or runner’s capabilities.
- GBA: Gas Bidding Agent — an actor that dynamically bids for timer execution on behalf
of another actor.

### 1.3.2 Key Features

Cowboy implements four core technical features:

- Deterministic Python Actors. Smart contracts on Cowboy are actors: Python programs
with private state, a mailbox for asynchronous messages, and chain‑native timers. Actors
execute in a sandboxed Python VM (PVM) pinned to Python 3.11.8 with deterministic
floating‑point (softfloat), disabled GC, fixed hash seed, and a whitelisted module set.
Reentrancy is depth‑capped to 32; per‑call memory is bounded at 10 MiB.

- Native Timers & Scheduler. Actors schedule their own future execution via set_timer
and set_interval without external keeper infrastructure. The scheduler uses a tiered

calendar queue and a Gas Bidding Agent (GBA) mechanism that dynamically bids for
timer execution at block time. Anti‑DoS measures include progressive deposits, exponential
same‑block surcharges, per‑actor timer caps, and a dynamic timer basefee.
- Verifiable Off‑Chain Compute. A decentralized Runner marketplace executes jobs
(LLM inference, HTTP fetches, custom compute) off‑chain. Runners stake CBY and are
selected via VRF. Results are verified under developer‑selected trust models: N‑of‑M
quorum, economic bond, TEE attestation, structured matching, semantic similarity, or (in
v2) ZK‑proofs. A commit‑reveal protocol with a 15‑minute challenge window and slashing
enforces honesty.
- Dual‑Metered Gas. Two independent fee markets price computation (Cycles) and data
(Cells) separately. Each meter uses a basefee that adjusts dynamically with demand and
is burned; tips go to proposers. This prevents cross‑subsidization between compute‑heavy
and storage‑heavy workloads.

### 1.3.3 Differences vs. Ethereum

| Aspect | Ethereum | Cowboy |
|--------|----------|--------|
| Execution | EVM bytecode (Solidity) | Python actors in sandboxed PVM |
| Fees | Single gas scalar | Dual meters (Cycles + Cells) |
| Scheduling | External keepers required | Native timers with GBA auction |
| Off‑chain compute | External oracles | Verifiable Runner marketplace |
| State management | Indefinite storage | Rent with eviction and restoration |

## 1.4 Accounts and State

Cowboy distinguishes two object types:

- External Accounts (EOAs): Controlled by private keys. They initiate transactions and
hold balances of CBY and other assets. Key management may be abstracted via passkeys
or other WebAuthn‑compatible mechanisms in future protocol versions.

- Actors: Autonomous Python programs executed in the PVM. Actors own storage, receive
messages, and can send messages to other actors.

Each object has a 20‑byte address. Actor addresses are computed CREATE2‑style from the
creator address, a salt, and the code hash. The world state is a mapping:

State : Address → { balance, nonce, code_hash?, storage?, metadata }

where actor storage is a key/value map subject to quotas and rent. System actors and precompiles
occupy a reserved prefix of the address space (0x0000…0100).

## 1.5 Transactions and Message Passing

A user interacts with Cowboy by sending a signed transaction specifying a destination, a
payload, and resource limits: a cycles limit and a cells limit alongside maximum and tip prices
for each.

An actor interacts with other actors by sending messages. Messages carry a payload, may
transfer value, and may trigger further messages. Delivery is exactly‑once after finality;
before finality it is at‑least‑once and may be reverted. Handlers MUST be idempotent. Actors
may schedule timers that insert messages at a future block height. To avoid denial‑of‑service
through explosive fanout, a transaction (including all nested sends) MUST NOT enqueue more
than 1,024 messages.

### 1.5.1 Native Timers and the Actor Scheduler

Cowboy provides protocol‑native timers, eliminating the need for external keeper networks.
Actors schedule messages to themselves or other actors at a future block height or on a recurring
interval.

### Tiered Calendar Queue. The scheduler uses three tiers to manage timers across different
time horizons with constant per‑block cost:

- Tier 1 — Block Ring Buffer: Imminent timers, one slot per block. O(1) enqueue/de-
queue.
- Tier 2 — Epoch Queue: Medium‑term timers, migrated in batches to Tier 1 at epoch
boundaries. O(1) amortized.
- Tier 3 — Overflow Sorted Set: Long‑horizon timers in a Merkleized binary search tree.
O(log n).

### Gas Bidding Agent (GBA). Rather than pre‑paying a fixed gas fee, an actor may designate
a GBA — another actor that dynamically bids for timer execution on its behalf. Actors that

do not specify a GBA receive a protocol‑provided default that bids conservatively. When a
timer becomes due, the protocol performs a read‑only call to the GBA with a context containing
current basefees, timer urgency (how many blocks deferred), and the owner’s balance. The GBA
returns a competitive bid, creating an intra‑block auction for the timer lane’s compute budget.

### Fairness and Liveness. Deferred timers receive a weighted priority boost with exponential
decay, preventing perpetual starvation by high‑bidding actors.

**DoS Prevention. Multiple layers protect the timer system:**

Attack Vector                     Mitigation

Schedule millions of timers       Progressive deposit: deposit(n) = base_deposit × (1 +
floor(n / 100))
Sybil attack across many actors   Per‑block execution budget caps total timer work (20% of
block cycles)
Timer bomb (many timers, one      Exponential same‑block surcharge: surcharge(k) =
block)                            base_cost × 2^max(0, k - 16)
Fill queue far in advance         Timer basefee rises automatically as queue depth exceeds
target
Outbid everyone perpetually       Anti‑starvation boost for deferred timers
DoS then cancel for refund        Surcharges are burned, not refunded on cancellation

Per‑actor timer limit: 256 active timers. Deposits are refunded when a timer fires or is
cancelled.

## 1.6 Asynchronous Execution and Multi‑Block Semantics

### 1.6.1 Single‑Block Atomicity

Cowboy provides atomicity only within a single block. All state reads, writes, and outbound
messages within a handler are atomic — they either all commit or all revert. There is no
cross‑block atomicity. Once a handler completes and the block is finalized, subsequent handlers
execute in potentially different world state.

### 1.6.2 Why No Cross‑Block Transactions

Cross‑block atomicity would require either global locks (destroying parallelism and creating
deadlock vectors) or speculative execution with rollbacks (creating griefing opportunities and
unpredictable costs). Cowboy explicitly rejects both approaches.

The fundamental problems with suspending execution across blocks are: (1) stale state —
values read before the yield may have changed; (2) invalid control flow — branches taken on
pre‑yield state may no longer be appropriate; (3) composability explosion — nested yields create
interleavings where each path depends on invalidated assumptions; (4) adversarial griefing —
attackers can mutate state between yield points.

### 1.6.3 Message‑Passing Continuation Model

Instead of implicit continuations, Cowboy uses explicit message passing for all asynchronous
operations. When an actor dispatches an off‑chain job, the result arrives as a separate message
in a later block. The actor must re‑read and re‑validate any state assumptions in the callback
handler.

This model requires explicit context capture — any state needed in the continuation must be
included in the outbound message. Correlation IDs enable matching responses to requests. If an
actor sends multiple requests, responses may arrive in any order.

Actors MUST implement timeout handling for operations that depend on external responses.
The recommended pattern combines correlation tracking with native timers: schedule a timeout
timer alongside each outbound request, and cancel the timer when the response arrives.

Developer
Model                         Atomicity         Burden            Griefing Resistance

Ethereum (sync calls)         Single TX         Low               High
Cross‑block locks             Multi‑block       Low               Low (deadlocks, lock
griefing)
Optimistic + rollback         Multi‑block       Medium            Low (rollback spam)
Cowboy (message               Single block      Medium            High
passing)

## 1.7 The Cowboy Actor VM (PVM)

Cowboy uses Python as its execution language. The PVM executes Python bytecode in a
deterministic sandbox pinned to Python 3.11.8, with restrictions to ensure identical results across
all nodes.

### 1.7.1 Determinism Guarantees

**Runtime Environment:**

- No JIT compilation — pure interpretation mode only.
- Deterministic memory management via reference counting. The cyclic garbage collector is
disabled; creating reference cycles MUST raise DeterminismError.
- Fixed recursion limit: 256 (integrated with cycle metering).

**Numeric Determinism:**

- All floating‑point operations use a cross‑platform software math library (softfloat), not the
host FPU.
- Transcendental functions (sin, cos, log, exp, etc.) use deterministic softfloat implementa-
tions.
- If the decimal module is used, it MUST use fixed rounding mode (ROUND_HALF_EVEN) and
fixed precision.

**Collection Ordering:**

- PYTHONHASHSEED fixed to 0.
- dict iteration is insertion‑ordered (deterministic per Python 3.7+).
- Built‑in set and frozenset are replaced with ordered_set from cowboy_sdk.collections
(transparent to user code).

**Serialization:**

- All data crossing trust boundaries MUST use canonical CBOR (RFC 8949, §4.2): sorted
map keys, shortest integer encoding, no indefinite‑length containers, 64‑bit floats only.
- pickle is forbidden. JSON output MUST use sort_keys=True, separators=(',',
':').

**Module Whitelist (v1):**

collections, dataclasses, enum, functools, itertools, json, re, struct, math, decimal,
typing, abc, hashlib, cowboy_sdk. No C extensions. No dynamic imports. Additional modules
may be added via governance after determinism audit.

**Forbidden Operations:**

Category               Forbidden

System                 sys.exit(), os.environ, os.system(), subprocess.*
Time                   time.time(), datetime.now(), time.sleep()
Randomness             random.* (use cowboy_sdk.vrf instead)
Networking             socket.*, urllib.*, http.*, requests.*
Filesystem             All except /tmp scratch space (256 KiB limit, wiped post‑handler)
Reflection             eval(), exec(), compile(), globals() modification
Introspection          sys._getframe(), inspect.currentframe(), gc.*
Weak References        weakref.* (non‑deterministic collection timing)
Threading              threading.*, multiprocessing.*, concurrent.*
Identity               is comparisons on strings or numbers (use ==)

### 1.7.2 Storage and State Persistence

The storage architecture uses a three‑layer model:

1. **The Ledger:** Append‑only log of blocks — the sequential, historical source of truth.
2. **The Triedb:** Merkle‑Patricia Trie generating a verifiable state_root per block, holding
all account, code, and storage state.
3. **Auxiliary Indexes:** Rebuildable, read‑optimized tables for transaction hashes, event
topics, etc. Not part of the consensus‑critical state root.

Cross‑VM Compatibility. A vm_ns (VM namespace) flag in storage keys allows PVM and
future EVM storage to coexist without collision at the same address. A standardized C‑ABI
wrapper enables cross‑VM calls.

All actor storage is subject to state rent (see §4.4 and the Data Availability section below).

## 1.8 Pricing: Cycles and Cells

Ethereum uses a single gas scalar. Cowboy splits pricing into two independent meters:

- Cycles measure compute: Python operations and host calls each have a fixed cost defined
in a consensus‑critical cost table. Cycles resemble Erlang reductions — a budget of discrete

steps bounding handler execution.
- Cells measure bytes: calldata, return data, blobs, and storage writes all consume cells (1
cell = 1 byte).

Each block adjusts two basefees (one per meter) dynamically based on demand. Users specify
max prices and optional tips for each meter. Basefees are burned; tips go to proposers.

The protocol does not meter off‑chain Runner execution. Runners set their own prices in a free
market, and actors escrow CBY at submission. This separates deterministic on‑chain metering
from non‑deterministic off‑chain resource pricing.

## 1.9 Off‑Chain Compute: The Runner Marketplace

Actors can outsource computation — LLM inference, HTTP fetches, heavy transforms — to a
decentralized network of Runners who stake CBY. The marketplace is verifiable: the chain
accepts results under trust models chosen by the developer, and dishonest runners risk slashing.

**Job Lifecycle:**

1. **Post:** Actor submits a job with escrowed price, resource bounds, and trust model.
2. **Assign:** A committee of M runners is selected via VRF from eligible (staked, healthy)
runners.
3. **Commit:** Runners return commit = keccak256(output || salt).
4. **Reveal:** Runners reveal {output, salt, proof?}.
5. **Challenge:** A 15‑minute window opens; challengers post a 100 CBY bond.
6. **Resolve:** Proven dishonesty triggers slashing; operational failures result in reputation
penalties only.
7. **Payout:** 99% of job payment to runner(s), 1% to Treasury.

**Trust Models:**

Mode                 Level of Trust

N‑of‑M Quorum        Committee executes; runtime accepts consensus result.
N‑of‑M with          Runners stake a bond; disputers may prove incorrect results within a fixed
Dispute              window.
TEE Attestation      Execution within a Trusted Execution Environment; attestation verified
on‑chain.
ZK‑Proof (v2)        Runners provide zk‑SNARKs for cryptographic verification.

Runners and actors are matched by Entitlements — a declarative permissions framework
governing capabilities such as TEE requirements, data residency, and supported models (see
§15).

### 1.9.1 Runner Resource Accounting

Every job submission includes explicit resource bounds (max tokens, max wall time, max
memory, max price). Runners publish rate cards to an on‑chain registry. Job pricing follows:
actual_payment = min(reported_usage × rates, max_price). Tips incentivize priority dur-
ing high demand.

Runner‑reported usage is trusted by default, subject to reputation scoring and anomaly detection
(>2× expected usage triggers automatic review). For stronger guarantees, actors can require
TEE‑attested metering. Proven dishonesty (e.g., fabricated results, misreported usage) is subject
to stake slashing via the challenge mechanism; operational failures (timeouts, crashes) result in
reputation penalties only.

**Payment and Failure Handling:**

Outcome                                Runner Payment                      Actor Refund

Success                                min(reported_usage × rates,         max_price -
max_price) + tip                    actual_payment
Runner fault (timeout, invalid         0                                   100% of escrow
result, crash)
Impossible job (bounds too tight)      Pro‑rata based on progress          Remainder of escrow
Actor fault (malformed input)          Minimum fee (gas cost recovery)     Remainder of escrow
External fault (API down, model        Pro‑rata based on progress          Remainder of escrow
unavailable)

### 1.9.2 LLM Result Verification

LLM outputs are inherently non‑deterministic — the same prompt can produce semantically
equivalent but byte‑different outputs. Cowboy provides multiple verification modes:

Run-                           Challenge
Mode                  ners      Verification         Scope              Use Case

none                  1         None                 Non‑delivery       Prototyping, low‑stakes
only
economic_bond         1         Objective checks     Objective          Subjective generation
failures
majority_vote         N‑of‑M    Vote on field        Objective          Classification
value                failures
structured_match      N‑of‑M    Verifier functions   Objective          Structured extraction
failures
deterministic         N‑of‑M    Exact match +        Full               Critical deterministic
TEE                  reproduction
semantic_similarityN‑of‑M       Embedding            Objective          Subjective with
threshold            failures           similarity

These modes provide economic assurance, not cryptographic correctness, except where TEE
or ZK verification is explicitly required. The protocol guarantees execution integrity, not output
quality — quality is a market outcome.

Objective Failure Criteria (automatically detected, no challenge required):

Failure                   Detection                                    Consequence

Schema violation          Output fails declared JSON schema            Reputation penalty, no
payment
Timeout                   No result within max_wall_time               Reputation penalty, no
payment
Empty/garbage             Output below min_length or fails entropy     Reputation penalty, no
output                    check                                        payment
Non‑delivery              Runner accepted job but never submitted      Reputation penalty, no
payment
Wrong model               TEE attestation shows different model        Slash (proven dishonesty)
hash

Failure                    Detection                                    Consequence

Prompt injection leak      Output contains system prompt markers        Reputation penalty, no
payment

Only proven dishonesty (fabricated results, wrong model with TEE attestation) triggers stake
slashing. Operational failures reduce the runner’s reputation score, affecting future job selection,
but do not destroy stake.

### 1.9.3 External Data and Oracle Semantics

Actors frequently need external data: price feeds, web APIs, public datasets. External data
is inherently mutable and non‑deterministic. Different sources require different verification
strategies:

Source Type             Characteristics                              Verification Strategy

Deterministic API       Versioned, stable, structured (blockchain     Exact match
RPC, static files)
Semi‑stable API         Structured with variable metadata (REST       Structured match, ignore
APIs)                                         metadata
Time‑series data        Values change over time (price feeds)         Median/majority with
freshness bounds
Web scraping            Unstructured, highly variable (HTML           Extraction‑based matching
pages)
Authenticated           Requires credentials                          Single runner + TEE
endpoints

### Freshness. Actors specify freshness constraints with a reference mode (block, submission, or
absolute) and a max_age_seconds parameter.
### Snapshot Modes. When multiple runners fetch mutable data, the protocol selects a canonical
result via one of: first_valid (first runner’s result is authoritative), median (for numeric data),
majority (for categorical data), or latest (most recent by timestamp).
### Extraction‑Based Verification. For web scraping, runners apply extraction rules (CSS selec-
tors, XPath, JSONPath, regex) and submit extracted data rather than raw HTML. Verification
compares extracted fields, ignoring irrelevant page differences.

HTTP access is governed by the Entitlements system. Actors declare required domains; run-
ners advertise supported domains. The protocol provides curated domain sets (price_feeds,
government_us, social_apis, blockchain_rpc).

## 1.10 Randomness

Each block derives a random beacon from the previous quorum certificate using a threshold
BLS VRF. Actors access sub‑randomness via HKDF(R_n, label) for fair committee sampling,
lotteries, and games.

## 1.11 Consensus and Networking

Cowboy uses Simplex BFT with proof‑of‑stake. Key parameters: ~1‑second blocks, ~2‑second
finality, fault tolerance up to f < n/3 Byzantine validators.

**Consensus Flow:**

1. **Propose:** Current proposer (selected by VRF, weighted by stake) broadcasts a block.
2. **Vote:** Validators vote; signatures are buffered and batch‑verified at quorum (2f+1).
3. **Certify:** A Quorum Certificate (QC) is formed from 2f+1 votes.
4. **Finalize:** A block is final when its direct child has a QC (two‑chain commit).

Under partial synchrony, the protocol guarantees safety at all times and liveness when network
delay is bounded. If a proposer fails, validators execute a view change: broadcast their highest
QC, and the next VRF‑selected leader proposes extending the highest‑QC block.

### 1.11.1 Validator Set

The validator set is open and permissionless. Requirements: stake ≥ minimum_validator_stake
(governance‑tunable), self‑stake only (no delegation in v1), compliant validator software. No
protocol cap on validator count.

Lifecycle: Register (stake CBY, submit BLS12‑381 key) → Activate (next epoch boundary)
→ Operate (propose, vote, earn rewards) → Exit (signal unbonding) → Withdraw (after 7‑day
unbonding period).

Epochs: 3600 blocks (~1 hour). Validator set updates, slashing penalties, and epoch randomness
derivation occur at epoch boundaries.

### 1.11.2 Staking and Rewards

Block rewards (from inflation) are distributed proportionally to stake. Proposers additionally
receive transaction tips. Staking is self‑bonded only; delegation is deferred to v2.

### 1.11.3 Slashing

Cowboy uses a conservative slashing model — most offenses result in jailing (temporary removal)
rather than stake destruction:

Offense                                                 Penalty

Double signing                                          Jail + slash 1% of stake
Proposer equivocation                                   Jail + slash 1% of stake
Extended downtime (>50% of votes over 1000 blocks)      Jail (no slash)
Invalid block proposal                                  Jail (no slash)

Jailed validators must wait 24 hours before unjailing. Repeated offenses increase jail duration
exponentially.

### 1.11.4 Network Layer

Transport: QUIC over TLS 1.3 (required). Gossip: transactions flood to all peers; blocks
are relayed by validators; votes go directly to the proposer. Peer discovery: DHT‑based with
bootstrap nodes.

### 1.11.5 Dedicated Lanes

Block space is partitioned into dedicated lanes with reserved capacity:

Lane              Reserved Capacity        Contents

System            5%                       Validator updates, governance, slashing
Timer             20%                      Scheduled timer executions
Runner            25%                      Runner job results and attestations
User              50%                      User‑initiated transactions

Unused capacity in higher‑priority lanes cascades to lower‑priority lanes. Transactions are tagged
by type at submission; the proposer cannot reassign lanes. Each lane has independent fee
multipliers applied to the global basefees.

### 1.11.6 MEV Reduction

Cowboy mitigates MEV through four mechanisms: (1) mandatory per‑block proposer rotation
via VRF prevents multi‑block observation; (2) VRF‑based transaction ordering within blocks
prevents strategic placement; (3) ~2‑second finality minimizes the observation window; (4) lane
isolation prevents congestion attacks that delay victim transactions. No encrypted mempool is
used — the marginal benefit does not justify the added latency given the already‑minimal MEV
surface. This does not prevent proposer inclusion/censorship or private orderflow MEV.

## 1.12 Data Availability, State Rent, and Storage

### 1.12.1 Inline Data vs. Blobs

Small outputs (≤ 64 KiB) are stored inline and paid for with cells. Larger artifacts MUST be
stored as content‑addressed blobs (e.g., IPFS) with the multihash referenced on‑chain.

### 1.12.2 State Rent

All persistent actor storage is subject to state rent — an ongoing fee for occupying space in the
global state trie. Rent rates adjust dynamically based on total network state size:

rent_rate_{i+1} = rent_rate_i × (1 + clamp((S - T) / (T × alpha), -delta,
+delta))

where S is the current total state size, T is the target (governance‑tunable), alpha = 8, and delta
= 0.125.

Rent is auto‑deducted from the actor’s balance each rent epoch (default: 1 day). Actors may
also prepay rent for cost certainty, and any account may sponsor rent on behalf of any actor.
Each actor maintains a minimum balance reserve (~5 weeks of rent) as a buffer before entering
grace period.

### 1.12.3 Grace Period and Eviction

When an actor cannot pay rent (balance, reserve, and prepaid epochs exhausted):

- Grace period (7 rent‑epochs): Actor remains fully functional; flagged as “rent overdue”;
catch‑up fee accumulates (10% of missed rent).
- Warning period (3 rent‑epochs): Actor flagged as “eviction imminent”; events emitted
to alert dependent actors.
- Eviction (rent‑epoch N+11): Actor storage and active timers are pruned. Code,
address, balance, and storage root hash are preserved. The actor enters a “dormant” state.

Evicted storage can be restored by anyone who provides the original data (verified against the
recorded root hash) and pays back‑rent plus catch‑up fees.

### 1.12.4 Storage Quotas

Each actor has a base storage quota of 1 MiB, extendable up to 8 MiB via a storage bond.
The bond is locked while the quota is in use, returned when reduced, and forfeited if the actor is
evicted. Rent applies to the full allocated quota.

## 1.13 The State Transition Function

The state transition function takes a block and an input state and returns the next state. Let 𝜎
be the global state, B a block with transactions T_i, basefees (bf_c, bf_b), and randomness
R.

1. **Header/Proposer:** Determined by Simplex; R derives from the parent QC.
2. **Execute Transactions:** Per‑lane selection, then VRF ordering. For each transaction:
validate signature, nonce, and balance; initialize meters; dispatch to target (fanout ≤ 1,024,
reentrancy depth ≤ 32); enforce memory (10 MiB), mailbox (≤ 1,000,000 bytes), and
storage quotas; deduct fees and burn basefees.
3. **Deliver Timers:** Inject due timers at height(B).
4. **Resolve Jobs:** Process commitments, reveals, challenges, and payouts.
5. **Adjust Basefees:** Update (bf_c, bf_b) based on block utilization.
6. **Mint Rewards:** Distribute per‑block inflation to validators.

### Normative Conventions

This document uses MUST/SHOULD/MAY as defined in RFC 2119. Parameters marked
governance‑tunable can be changed by on‑chain governance (see §11).

## 1. Accounts, Addresses, and Keys

### 1.1 Signatures.

External accounts MUST use secp256k1 (ECDSA) with chain‑id separation.

### 1.2 Actor address derivation (CREATE2‑style).

New actor addresses MUST be: addr = last_20_bytes(keccak256(creator || salt ||
code_hash)) where code_hash = keccak256(python_source_bytes).

python_source_bytes MUST be canonicalized as UTF‑8, NFC‑normalized, LF line endings,
and no BOM. The canonical bytes are what are hashed and stored.

### 1.3 System address space.

The range 0x0000…0100 is reserved for system actors and precompiles (see §10).

## 2. Transaction Types & Encoding

### 2.1 Typed tx (EIP‑1559 style, dual meters).

A transaction MUST include: chain_id, nonce, to, value, cycles_limit, cells_limit,
max_fee_per_cycle, max_fee_per_cell, tip_per_cycle, tip_per_cell, access_list?,
payload, signature.

### 2.2 Validity checks.

Nodes MUST reject a tx if: (a) limits exceed maxima (§13.1), (b) insufficient balance, (c)
signature invalid, (d) access list invalid, or (e) payload decoding fails.

### 2.3 Fee accounting.

Let bc, bb be the block basefees for cycles/cells. Fees are: fee = cycles_used
* (bc + min(tip_per_cycle, max_fee_per_cycle - bc)) + cells_used * (bb +
min(tip_per_cell, max_fee_per_cell - bb)).   Unused limits MUST be refunded at
the user’s max_fee_* rates.

### 2.4 EBNF (informative).

Tx = Header Body Sig Header = chain_id nonce to value cycles_limit cells_limit
max_fee_per_cycle max_fee_per_cell tip_per_cycle tip_per_cell [access_list]
Body = payload Sig = secp256k1_signature_recoverable

### 2.5 Encoding (normative).

Transactions MUST be encoded as canonical CBOR (RFC 8949, deterministic encoding) arrays
in fixed field order:

Tx = [chain_id, nonce, to, value, cycles_limit, cells_limit, max_fee_per_cycle,
max_fee_per_cell, tip_per_cycle, tip_per_cell, access_list, payload, signature]

- to is a 20‑byte address or null for actor creation.
- access_list is either null or a list of [address, storage_keys[]] pairs.
- signature = [y_parity, r, s] where y_parity ∈ {0,1} and r,s are 32‑byte big‑en-
dian byte strings.
- The signing hash MUST be keccak256(CBOR(Tx_without_signature)), where
Tx_without_signature is the same array with the signature field set to null.

## 3. Execution Model (Actors)

### 3.1 Runtime & Determinism.

- Official SDKs: Python SDK. The runtime MUST enforce determinism:

  - Allowed operations: Standard Python operations, file I/O limited to /tmp;
async/await is syntax sugar only and does not suspend across blocks.
  - Forbidden: sys.exit(), random module (except chain VRF), time.time()/datetime.now(),
os.environ access, socket/network operations, subprocess calls, path traversal
outside /tmp.
  - Floating point: Permitted; Cowboy provides a deterministic math library.
  - Scratch space: /tmp MUST be per‑invocation, capped at 256 KiB (counts toward
cells_used), wiped post‑handler.

### 3.2 Memory & Storage.

- Per‑call memory limit: 10 MiB heap memory.
- Per‑actor persistent storage quota: 1 MiB (governance‑tunable) with state rent
(§4.4).
- Quota extensions: An actor MAY post a storage bond up to 8 MiB total; rent applies
to the full allocated quota.

### 3.3 Messaging, Reentrancy, Timers.

- Delivery: Exactly‑once after finality (before finality: at‑least‑once). Each message
ID MUST be keccak256(sender||nonce||msg_hash) and recorded in a per‑actor dedup
set (counts toward actor storage or a separate metered mailbox store). Dedup entries
MUST be retained for at least dedup_window after finality.
- Mailbox: Capacity 1,000,000 bytes (or equivalent cell‑metered limit); enqueue beyond
the limit MUST revert.

- Per‑tx fanout: A transaction (including all nested sends) MUST NOT enqueue more
than 1,024 messages.
- Reentrancy: Allowed within a single block only; there is no synchronous call/return
across blocks. Recursion/await depth cap = 32.
- Timers (chain‑native): The following timer primitives are provided:

  - timer_id = set_timer(height, handler, data) — Schedule a one-time timer for
the specified block height. Returns a unique timer_id.
  - timer_id = set_interval(every_n_blocks, handler, data) — Schedule a recur-
ring timer. Returns a unique timer_id.
  - cancel_timer(timer_id) — Cancel a pending timer by its ID. Returns the deposit
if successful.
  - Timer delivery is best‑effort; execution depends on the GBA auction (see §Timer
Rate Limiting).

### 3.4 Randomness.

- Validators MUST generate a threshold‑BLS VRF per block: R_n = VRF_sk_epoch(QC_{n-
1}). Actors MAY call an API which returns HKDF(R_n, label).

### 3.5 Partial cost table (informative).

- Exact metering is consensus‑critical; implementers MUST match the reference cost table.

Primitive                                    Cycles

Python arithmetic ops                             1
Python function call                             10
Dictionary get/set                                3
List append/access                                2
String operations (per char)                      1
host: mailbox send (per msg excl. payload)       80
host: timer set/cancel                          200
host: blob commit (per KiB)                      40

Note: Cells meter bytes (payload, return data, inline blobs ≤ 64 KiB, /tmp).

## 4. Fees, Metering, and Basefee Adjustment

### 4.1 Meters.

- Cycles: Deterministic step count over Python operations + host calls.
- Cells: Bytes used by calldata, return data, inline blobs (≤ 64 KiB), and /tmp.

### 4.2 Dual EIP‑1559 basefees. Let U_c, T_c be cycles usage/target; U_b, T_b be cells usage/target.
With elasticity E=2 (hard cap E*T_*), adjustment uses:

basefee_{x,i+1} = max(1, basefee_{x,i} * (1 + clamp((U_x - T_x)/(T_x*alpha),
-delta, +delta)))

where x ∈ {cycle, cell}, alpha = 8, delta = 0.125. Nodes MUST burn 100% of basefees;
tips go to proposers/validators.

### 4.3 Targets (genesis defaults).

- T_c (cycles target): 10,000,000 cycles (cap 20,000,000).
- T_b (cells target): 500,000 bytes (cap 1,000,000).

### 4.4 State rent. Persistent storage incurs rent per byte per rent‑epoch, which is governance-
tunable. If unpaid for 7 rent‑epochs, an eviction warning begins; eviction is eligible after 10
rent‑epochs.

## 5. Off‑Chain Compute

### 5.1 Model registry.

model_id = keccak256(weights||arch||tokenizer||license) MUST uniquely identify a
model revision. Publishing is permissionless with a refundable 1,000 CBY deposit. Gover-
nance MAY flag/ban models.

### 5.2 Runner staking.

Runners MUST stake max(10,000 CBY, 1.5 × declared_max_job_value) in the Runner Reg-
istry.

### 5.3 Job lifecycle.

1. **Post:** Actor posts a job with escrowed price.
2. **Assign:** For HTTP domains, a committee of M=5 is sampled; N=3 matching reveals
finalize. LLM jobs MAY use committees or single-runner.
3. **Commit:** Runner returns commit = keccak256(output||salt).
4. **Reveal:** Runner reveals {output, salt, proof?}.

5. **Challenge:** A challenge window of 15 min is opened, requiring a 100 CBY bond.
6. **Resolve:** Proven dishonesty ⇒ stake slashing via challenge mechanism. Operational
failures (timeouts, crashes) result in reputation penalties only.
7. **Payout:** On finalization, 99% of job payment to runner(s), 1% to Treasury.

### 5.4 Determinism & bounds.

Jobs MUST pin toolchain_digest and seed. On‑chain return data MUST be ≤ 64 KiB.

### 5.5 TEE option.

A job MAY set tee_required=true. A valid attestation MUST match accepted policies.

## 6. Consensus, Randomness, and Networking

### 6.1 Consensus.

Simplex BFT PoS; ~1s target block time; finality on commit (~2s). Proposers rotate every
block using the VRF beacon (mandatory rotation for MEV resistance). Votes aggregate via
BLS12‑381 with buffered batch verification.

Message types (normative): PROPOSE, VOTE, NEW_VIEW.

Quorum certificate (QC): QC = {block_hash, height, round, aggregated_signature,
signer_bitmap} where aggregated_signature is BLS12‑381 over the block_hash || height
|| round domain.

VRF: Each block header MUST include the proposer’s VRF output and proof for the current
height; validators MUST verify it against the epoch seed.

Finality rule: A block B_h is final when its direct child has a QC (two‑chain commit). Concretely,
if QC(B_{h+1}) exists and B_h is the parent of B_{h+1}, then B_h is finalized. Implementations
MAY expose both “commit” and “finalized” states explicitly.

View change: On timeout, validators broadcast NEW_VIEW containing their highest known QC.
The next proposer MUST build on the highest‑QC block.

### 6.2 P2P transport.

Implementations MUST support QUIC over TLS 1.3.

### 6.3 Dedicated Lanes.

Block space is partitioned into dedicated lanes with reserved capacity:

Lane          Reserved Capacity      Priority    Contents

System        5%                     Highest     Validator updates, governance, slashing
Timer         20%                    High        Scheduled timer executions
Runner        25%                    High        Runner job results and attestations
User          50%                    Normal      User transactions

Lane guarantees:

- Timer and runner lanes prevent user transaction spam from blocking autonomous actor
execution
- Unused capacity in higher-priority lanes cascades to lower-priority lanes
- Each lane has independent fee multipliers applied to the global cycle/cell basefees

### 6.4 Gossip (mempool).

Public mempool prioritized by effective fee. Within each lane, proposers select transactions by
highest effective fee up to lane capacity (ties broken by tx_hash), then apply VRF ordering
within the selected set. For ordering, effective_fee is computed using intrinsic costs only:
effective_fee = intrinsic_cycles × min(max_fee_per_cycle, basefee_cycle +
tip_per_cycle) + intrinsic_cells × min(max_fee_per_cell, basefee_cell + tip_per_cell).
Transactions are tagged by lane type. No private builders or encrypted mempool in v1—MEV
resistance relies on fast finality and mandatory proposer rotation.

### 6.5 MEV Reduction (Limitations Apply).

Cowboy’s MEV mitigation strategy combines multiple mechanisms:

Mandatory proposer rotation: Simplex consensus rotates proposers every block via VRF.
Unlike stable-leader protocols, no single validator can observe transaction flow across multiple
blocks, limiting MEV extraction windows.

VRF-based transaction ordering: Within each block, transactions are ordered by:

order_key = VRF(proposer_key, tx_hash, block_height)

This deterministic-but-unpredictable ordering prevents proposers from strategically placing their
own transactions.

Note: This does not prevent proposer inclusion/censorship or private orderflow MEV.

Fast finality: ~2 second finality (2 Simplex rounds) minimizes the window for:

- Front-running (limited observation time)
- Sandwich attacks (high risk of failed execution)
- Time-bandit attacks (chain never reorgs past finality)

Dedicated lanes: Reserved capacity for timers and runners ensures autonomous actors execute
reliably regardless of user mempool congestion. Attackers cannot spam the user lane to delay
victim transactions in other lanes.

No encrypted mempool: Commit-reveal schemes add latency and complexity. Given ~1s
blocks and ~2s finality, the observation window is already minimal. The combination of VRF
ordering + rotation + fast finality provides sufficient MEV resistance without the latency cost of
encryption.

## 7. Data Availability & Blobs

### 7.1 Inline cap.

Inline blob cap is 64 KiB per output.

### 7.2 External blobs.

Larger data MUST be content‑addressed (e.g., IPFS). The on‑chain commitment MUST be a
multihash.

## 8. Economics, Inflation, and Fees

### 8.1 Ticker & supply. CBY. Genesis supply 1,000,000,000 CBY.

### 8.2 Inflation. A decreasing inflation schedule is used to bootstrap network security.

- Year 1-2: 8% annual inflation
- Year 3-4: 5% annual inflation
- Year 5-6: 3% annual inflation
- Year 7-10: 2% annual inflation
- Year 10+: 1% terminal inflation

### 8.3 Distribution at genesis.

Validators 25%, Treasury 25%, Ecosystem 30%, Investors 20% (standard vesting).

### 8.4 Fee sinks & splits.

Basefees: 100% burned. Tips: to proposers/validators. Off‑chain job payments: 99% to
runners, 1% to Treasury.

## 9. System Actors & Precompiles

- 0x01 Messaging: Enqueue and fanout messages.
- 0x02 Timers: Schedule/cancel timers.
- 0x03 Oracle/Runner: Manage off-chain jobs.
- 0x04 Blob store: Commit/retrieve blob multihashes.
- 0x05 Signer utils: secp/BLS/VRF helpers.
- 0x06 EventListener: Ethereum event subscriptions (see §16).
- 0x07 TEE Verifier: Verify TEE attestations against trusted measurements.
- 0x08 Secrets Manager: Secure credential storage and access control for TEE runners.

## 10. Developer Experience (DX)

- SDKs: A primary Python SDK (cowboy-py) is provided.
- Local dev: A suite of tools including a single-node devnet (cowboyd), runner simulator,
faucet, and explorer will be available.
- Best practices: Reentrancy guards, capability-scoped handles, and idempotent message
handling are encouraged via the SDK.

## 11. Governance & Upgrades

- Model: Foundation 5‑of‑9 multisig sunsets after ~12 months to token‑weighted on‑chain
governance.
- Timelocks: Standard actions 7 days; emergency fast‑track 6 hours.
- Upgrades: Hot‑code upgrades coordinated by governance.

## 12. Security Considerations

### 12.1 DoS limits (consensus‑enforced; governance‑tunable).

- max_tx_size = 128 KiB
- max_message_depth_per_tx = 32
- per_actor_per_block_cycles = 1,000,000 (burstable)

### 12.2 Runner safety.

Slashing for proven dishonesty (fabricated results, wrong model). Operational failures result in
reputation penalties only. Committees mitigate single‑runner faults.

### 12.3 Reentrancy.

Allowed but depth‑capped; stdlib provides reentrancy guards.

### 12.4 Randomness bias.

Threshold‑BLS VRF with epoch keys; actors derive sub‑randomness via HKDF.

### 12.5 State rent & eviction.

Prevents state bloat; eviction windows protect liveness.

## 13. Parameters (Genesis Defaults)

**Execution:**

memory_per_call = 10 MiB; storage_quota_per_actor = 1 MiB; reentrancy_depth =
32; fanout_per_tx = 1024; mailbox_capacity_bytes = 1,000,000; dedup_window = 10,000
blocks.

**Fees:**

T_c = 10,000,000 cycles; T_b = 500,000 bytes; alpha = 8; delta = 0.125.

**Consensus:**

minimum_validator_stake = governance-tunable; epoch = 3600 blocks (~1 h); block_time =
1 s; finality = ~2 s; unbonding_period = 7 days; jail_period = 24 h; double_sign_slash
= 1%; consensus_protocol = Simplex BFT.

**Dedicated Lanes:**

system_lane_capacity = 5%; timer_lane_capacity = 20%; runner_lane_capacity = 25%;
user_lane_capacity = 50%.

**Off‑chain:**

committee M = 5; threshold N = 3; challenge_window = 15 min; challenge_bond = 100
CBY; runner_stake_floor = 10,000 CBY.

**State Rent:**

target_state_size = governance-tunable; grace_period = 7 rent‑epochs; warning_period =
3 rent‑epochs; catch_up_fee = 10%; reserve_multiplier = 0.1.

**Economics:**

supply = 1,000,000,000; inflation follows the schedule in §8.2; basefee burn = 100%; job fee
to treasury = 1%.

## 14. Differences vs. Ethereum

- Execution: Python actors vs. EVM contracts.
- Fees: Dual meters (cycles/cells) vs. single gas scalar.
- Timers: Native timers vs. external keepers.
- Off‑chain compute: Native verifiable market vs. external oracles.
- State: Rent with eviction vs. indefinite storage.

## 15. Entitlements

A declarative, composable permissions system governs the capabilities of actors and runners.
Entitlements control access to resources like networking, storage, and execution parameters,
enforcing least-privilege by default. The system is enforced at deployment time, by the scheduler,
and at the VM syscall gate.

### 15.1 Goals

- Least privilege by default.
- Deterministic enforcement.
- Declarative & composable.
- Auditable on-chain.

### 15.2 Objects & lifecycle

- Actor Entitlements: Permissions the actor requires.
- Runner Entitlements: Capabilities the runner provides.

### 15.3 Rules

## 1. MUST: Actors require entitlements; runners provide them.
## 2. MUST: Scheduler matches only if requires ⊆ provides.
## 3. MUST: Syscalls fail if the corresponding entitlement is missing.
## 4. MUST: Child actors only inherit entitlements marked inheritable:true.

(For a full list of entitlements, see the Entitlements Specification.)

## 16. Ethereum Interoperability

Cowboy’s interoperability with Ethereum is a primary design goal, enabling seamless asset
transfer and cross-chain communication. This is achieved through a combination of shared
cryptographic primitives, a canonical bridge, and event subscription mechanisms.

### 16.1. Account Unification

- Cowboy external accounts (EOAs) MUST use the same secp256k1 elliptic curve for
signatures as Ethereum. This allows a single private key to control accounts on both
networks, simplifying key management for users and agents.
- An actor, through a host call, MAY verify an EIP-712 signed data structure against a
given Ethereum address, enabling actors to validate off-chain authorizations from Ethereum
users.

### 16.2. Bridge Infrastructure

Cowboy relies on third‑party bridge infrastructure for asset transfers and cross‑chain message
passing between Cowboy and Ethereum.

Requirements:

- The bridge MUST support the locking of native ETH and ERC-20 tokens on Ethereum to
mint a corresponding wrapped representation on Cowboy (wETH, wERC-20), and the reverse
burn‑to‑unlock flow.
- The bridge MUST support generic message passing: a transaction on one chain triggering
a message call to a designated recipient on the other.
- Bridge selection and integration are determined by governance. The protocol does not
implement its own bridge validator set.

### 16.3. Event Subscription (Ethereum to Cowboy)

- Cowboy actors MAY subscribe to event logs emitted by specific contracts on the Ethereum
blockchain.
- A system actor on Cowboy, 0x06 EventListener, SHALL manage these subscriptions.
This actor relies on the bridge validator set to act as a decentralized oracle, monitoring the
Ethereum chain for specified events.
- When a subscribed event is confirmed (i.e., finalized on Ethereum), the EventListener
actor MUST enqueue a message to the subscribing Cowboy actor, delivering the event’s
topic and data as the message payload.
- The cost of this subscription service SHALL be paid by the actor in CBY, covering the gas
fees incurred by the oracle validators on Ethereum.

### 16.4. Policy and Security

- All interoperability functions available to an actor, such as bridge_asset or
subscribe_event, MUST be governed by the Entitlements system (§15).
- An actor’s deployment manifest MUST declare the specific Ethereum contracts it is
permitted to interact with and the types of assets it is allowed to bridge, enforcing the
principle of least privilege.

## 17. Fee Model Specification

This section is authoritative; any conflicting values elsewhere are non‑normative.

### 17.1. Overview

Cowboy uses a dual-metered fee system:

Meter                          Unit                        Purpose

Cycles                         Compute units               CPU time, opcode execution, actor
API calls
Cells                          Data units (bytes)          Storage writes, calldata, bandwidth

Both meters use independent EIP-1559-style basefee adjustment. Fees are paid in CBY.

Three cost domains: 1. On-chain execution — Cycles consumed by transaction processing
## 2. On-chain storage — Cells consumed by state writes + ongoing state rent 3. Off-chain
services — Direct CBY payments to Runners (LLM inference) and Providers (blob storage)

### 17.2. Transaction Intrinsic Costs

Every transaction pays a base cost before execution begins:

Transaction Type   Base Cycles    Base Cells          Notes

Transfer           21,000         0                   EOA-to-EOA value transfer

Transaction Type     Base Cycles    Base Cells            Notes

Deploy               100,000        code_size             Actor deployment
ActorMessage         21,000         calldata_size         Method invocation
LlmRequest           10,000         prompt_size           Off-chain inference request
TimerSchedule        5,000          64                    Schedule future execution

### 17.3. Execution Costs (Cycles)

#### 1.13.0.1 Opcode Costs Python opcode costs are implementation-defined and not protocol-
specified. The runtime MUST ensure deterministic cycle consumption across all validators.

#### 1.13.0.2 Actor API Costs

Operation                 Base Cost      Variable Cost

send_message()            1,000 cycles   —
storage_read()            500 cycles     +1 cycle/byte read
storage_write()           5,000 cycles   +10 cycles/byte written
hash()                    100 cycles     +1 cycle/byte hashed
verify_signature()        3,000 cycles   —
get_block_info()          100 cycles     —
emit_event()              500 cycles     +5 cycles/byte

#### 1.13.0.3 Platform Token Costs (CIP-20)

Operation                      Cycles   Cells

token_transfer()               1,000    64
token_transfer_from()          1,500    96
token_approve()                500      32
token_balance_of()             100      0

Operation                   Cycles   Cells

token_mint()                1,000    64
token_burn()                500      64
token_create()              10,000   256 + name + symbol

Validation hooks add up to 50,000 cycles per transfer (capped).

### 17.4. On-Chain Storage Costs (Cells)

Operation        Cell Cost

State write      1 cell/byte written
State read       0.01 cells/byte (bandwidth metering)
Calldata         1 cell/byte of transaction data
Event emission   0.5 cells/byte of event data

### 17.5. State Rent

Accounts exceeding the grace threshold pay ongoing rent:

rent_per_rent_epoch = max(0, account_size - grace_threshold) × rent_rate

Parameters:
grace_threshold = 10,240 bytes (10 KB)
rent_rate       = 0.001 CBY/byte/year (governance-adjustable)
rent_epoch_length = 1 day
eviction_threshold = 10 rent‑epochs unpaid rent

Grace period behavior: - Accounts ≤10 KB: No rent charged - Accounts >10 KB: Rent
charged on excess bytes only - Unpaid rent accumulates as debt against the account - Eviction
after 10 rent‑epochs of accumulated debt (state archived to blob storage, recoverable upon debt
repayment)

### 17.6. Off-Chain Blob Storage (CIP-7)

Large data (images, datasets, AI inference traces) uses Retention Contracts:

Cost Component      How Charged

BlobRef storage     ~64 bytes on-chain → Cell cost + state rent
Provider payments   Direct CBY to Provider via escrow (market rate)

Blob storage is not cell-metered. Provider payments are direct CBY transfers negotiated
off-chain. See CIP-7 for full specification of: - Retention policies and SLAs - Provider staking and
availability commitments - Watchtower auditing and challenge mechanism - Payment schedules
and slashing conditions

### 17.7. Off-Chain Compute (Runner Marketplace)

LLM inference is not gas-metered. Runners operate in a competitive marketplace:

Aspect                              Specification

Pricing                             Runners post quotes (CBY per token, per model)
Selection                           Users specify max_price in LlmRequest; matching via
auction or direct selection
Settlement                          CBY payment upon verified result delivery
Collateral                          runner_stake >= 10 × average_job_value
Verification                        Attestation + random re-execution challenges

The protocol does NOT specify LLM pricing—this is determined by market dynamics between
users and runners.

### 17.8. Fee Adjustment (EIP-1559 Style)

Both Cycles and Cells use independent basefee adjustment:

next_basefee = basefee × (1 + 𝛿 × (usage - target) / target)

Cycle parameters: | Parameter | Value | |———–|——-| | Target | 10,000,000 cycles/block |
| Cap | 20,000,000 cycles/block | | 𝛿 (delta) | 0.125 (12.5% max change) | | 𝛼 (smoothing) | 8
blocks |

Cell parameters: | Parameter | Value | |———–|——-| | Target | 500,000 bytes/block | | Cap |
1,000,000 bytes/block | | 𝛿 (delta) | 0.125 (12.5% max change) | | 𝛼 (smoothing) | 8 blocks |

Basefee burning: 100% of basefee revenue is burned, creating deflationary pressure proportional
to network usage.

### 17.9. Reserved Capacity (Execution Lanes)

Block space is partitioned to guarantee execution for critical transaction types:

Lane      Cycle Budget    Percentage    Purpose

Timer     2,000,000       20%           Scheduled actor execution
Runner    2,500,000       25%           LLM result callbacks
System    500,000         5%            Governance, upgrades
User      5,000,000       50%           Regular transactions

Lane behavior: - Unused capacity in reserved lanes spills to User lane - User lane cannot borrow
from reserved lanes - Timer lane has highest priority within its reserved capacity; execution is
still subject to GBA bidding and per‑block limits

### 17.10. Fee Estimation

Wallets and applications SHOULD estimate fees as:

def estimate_fee(tx):
intrinsic_cycles = INTRINSIC_COSTS[tx.type]
intrinsic_cells = len(tx.calldata)

# Estimate execution cost (via simulation or heuristics)
execution_cycles = simulate_execution(tx)
execution_cells = estimate_storage_writes(tx)

total_cycles = intrinsic_cycles + execution_cycles
total_cells = intrinsic_cells + execution_cells

# Apply current basefees
cycle_fee = total_cycles * cycle_basefee
cell_fee = total_cells * cell_basefee

# Add priority tip
priority_fee = (total_cycles * tip_per_cycle) + (total_cells * tip_per_cell)

return cycle_fee + cell_fee + priority_fee

Appendix A. Transaction Encoding Test Vectors (Informative)

These vectors specify canonical CBOR encodings. Hex is lowercase, no 0x prefix.
Vector 1: Unsigned transfer (signature = null)
Fields:

- chain_id=1
- nonce=0
- to=0x1111111111111111111111111111111111111111
- value=1
- cycles_limit=21000
- cells_limit=0
- max_fee_per_cycle=10
- max_fee_per_cell=2
- tip_per_cycle=1
- tip_per_cell=0
- access_list=null
- payload=0x (empty bytes)
- signature=null

CBOR hex:

8d010054111111111111111111111111111111111111111101195208000a020100f640f6

The signing hash is keccak256(CBOR(Tx_without_signature)) where the signature field is
null (as above).
Vector 2: Signed transfer
Same fields as Vector 1, with:

- signature=[y_parity=0, r=0x01*32, s=0x02*32]

CBOR hex:

8d010054111111111111111111111111111111111111111101195208000a020100f6408300582001010101010101

### End of specification.
