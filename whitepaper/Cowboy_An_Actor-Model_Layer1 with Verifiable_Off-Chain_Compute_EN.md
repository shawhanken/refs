# Cowboy: An Actor-Model Layer-1 with Verifiable Off-Chain Compute

**Status** Draft for internal review  
**Type** Standards Track  
**Category** Core  
**Author(s)** Cowboy Foundation  
**Created** 2025-09-17  
**Updated** 2025-12-14  
**License** CCO-1.0

## Abstract

We are in the Age of the Agent. Advancements in LLMs have unleashed new modalities for software to act autonomously, but these intelligent systems remain economically handcuffed, trapped behind APIs and corporate accounts. Crypto provides the missing element: permissionless, programmable economic agency. Cowboy is a general-purpose Layer-1 blockchain designed to bridge this gap, enabling AI agents to become native citizens of a digital economy.

Cowboy combines a **Python-based actor-model execution environment** with a **proof-of-stake consensus** and a **market for verifiable off-chain computation**. Smart contracts on Cowboy are **actors**: Python programs with private state, a mailbox for messages, and chain-native timers for autonomous scheduling. For heavy tasks like LLM inference or web requests, Cowboy integrates a decentralized network of **Runners** who execute jobs and attest to results under selectable trust models: N-of-M consensus, TEEs, and (in V2) ZK-proofs.

To ensure fair and predictable resource pricing, Cowboy introduces a **dual-metered gas model**, separating pricing for computation (**Cycles**) and data (**Cells**) into independent, EIP-1559-style fee markets. Security is provided by **Simplex BFT proof-of-stake** with fast finality and mandatory proposer rotation. By bringing the world’s most dominant AI programming language, Python, directly on-chain, Cowboy provides the critical infrastructure for the next generation of autonomous agents.

## Introduction

### The Problem: A Chasm Between Intelligence and Agency

Most programmable chains evolved from a synchronous, function-call model, coupling storage, compute, and timing into a single transaction. This paradigm is ill-suited for the asynchrony and complexity of modern autonomous systems. Further, it forces development into nascent ecosystems like Solidity or Rust, alienating the vast majority of AI and enterprise developers who build in Python. Even for teams who bridge this gap, the result is operational chaos: a Frankenstein’s monster of cloud servers, cron jobs, oracles, and key management services, held together by brittle off-chain glue.

Critically, these architectures fail to build trust. When an agent makes a decision—rebalancing a portfolio, executing a trade—users reasonably want to know why. What data did it see? How did it decide? Today’s approach offers no verifiable link between inputs, execution, and outputs. Without this foundation of trust, autonomous agents remain toys, not tools for a robust economy.

**The Solution: Cowboy**

Cowboy imports the actor model into a blockchain to provide a native, unified platform for autonomous agents. Every application is a set of actors; each actor is a Python program with deterministic execution, a persistent key/value store, and a mailbox. The chain delivers messages and timers, enforces resource limits, and commits state transitions in blocks. For work that cannot or should not run on-chain, Cowboy exposes a native market where **Runners** execute jobs off-chain and post verifiable results.

This document presents Cowboy's architecture, the state transition function, the economic mechanisms for fees and verification, and an initial parameter set.

### Key Innovations in Cowboy

General-purpose chains struggle with data-hungry, latency-sensitive apps. Cowboy makes **actors** and **verifiable off-chain compute** native through four key innovations:

*   ***Deterministic Python Actors:** A sandboxed Python VM with mailbox messaging, reentrancy (depth-capped), and first-class support for the world's most popular programming language.
*   ***Native Timers & Scheduler:** A protocol-level mechanism for autonomous, scheduled execution with dynamic, context-aware gas bidding, eliminating the need for external keeper networks.
*   ***Verifiable Off-Chain Compute:** An open marketplace for off-chain jobs (e.g., LLM inference, API calls) with selectable trust models, including N-of-M consensus, TEE attestations, and (in V2) ZK-proofs.
*   ***Dual-Metered Gas:** Independent pricing and EIP-1559-style fee markets for compute (**Cycles**) and data/storage (**Cells**) to ensure fair and predictable costs.

### Accounts and State

Cowboy distinguishes two object types:

*   ***External Accounts (EOAs):** Controlled by private keys (secp256k1). They initiate transactions and hold balances of CBY and other assets.
*   ***Actors:** Autonomous Python programs executed in the PVM (Python Virtual Machine). Actors own storage, receive messages, and can send messages to other actors.

Each object has a 20-byte address. Actor addresses are computed CREATE2-style from the creator address, a salt, and the code hash. The **world state** is a mapping:

`State : Address -> { balance, nonce, code_hash?, storage?, metadata }`

where actor storage is a key/value map with a quota (default 1 MiB) and rent. System actors and precompiles occupy a reserved prefix of the address space.

### Transactions and Message Passing

A user interacts with Cowboy by sending a **transaction** (signed with secp256k1) specifying a destination, a payload, and resource limits: a **cycles limit** and a **cells limit** alongside maximum and tip prices for each.

An actor interacts with other actors by sending **messages**. Messages carry a small payload, may transfer value, and may trigger further messages. Delivery is **exactly-once**, and actors may schedule **timers** that insert messages at a future block height. To avoid denial-of-service through explosive fanout, Cowboy caps the number of messages any transaction (and its triggered cascades) can enqueue.

**Native Timers and the Actor Scheduler**

To enable true autonomy, Cowboy provides a protocol-native timer and scheduling mechanism, eliminating the need for external keeper networks. Actors can schedule messages to be sent to themselves or other actors at a future block height or on a recurring interval. The scheduler is designed to be scalable, economically rational, and fair.

**Scalable Design: The Tiered Calendar Queue** The scheduler uses a multi-layered **tiered calendar queue** to manage timers efficiently across different time horizons without compromising performance. This architecture consists of three levels:

*   ***Tier 1: Block Ring Buffer:** An O(1) queue for imminent timers, organized as a ring buffer where each slot represents a single block. This handles near-term scheduling with maximum efficiency.
*   ***Tier 2: Epoch Queue:** A medium-term queue for timers scheduled in future epochs. Timers from this queue are efficiently migrated in batches to the Block Ring Buffer at the start of each new epoch.
*   ***Tier 3: Overflow Sorted Set:** A Merkleized binary search tree for very long-term timers that fall outside the Epoch Queue's range, ensuring the protocol can handle any future-dated schedule.

This tiered design ensures that the per-block work of processing timers remains constant and small, regardless of the total number of scheduled timers.

**Economic Rationality: The Gas Bidding Agent (GBA)** A key innovation in Cowboy's scheduler is the concept of the **Gas Bidding Agent (GBA)**. Instead of pre-paying a fixed gas fee, an actor designates a GBA (which is another actor) to dynamically bid for its timer's execution when it becomes due.

When a timer is ready to be executed, the protocol performs a read-only call to the actor's GBA, providing it with a rich context object containing real-time data like network congestion (current base fees), the timer's urgency (how many blocks it has been delayed), and the owner's balance. The GBA uses this context to return a competitive gas bid. This creates an intra-block auction for a dedicated portion of the block's compute budget, ensuring that high-priority tasks can get executed even during periods of high network traffic. To ensure a simple developer experience, actors which do not specify a GBA receive the network default.

**Fairness and Liveness** Timers that are not executed due to low bids or network congestion are automatically deferred to the next block. To prevent "timer starvation" where an actor is perpetually outbid, the protocol tracks an actor's scheduling history. It uses a weighted priority system with exponential decay to give a small boost to actors whose timers have been repeatedly deferred, ensuring eventual execution and maintaining network fairness.

**Timer Rate Limiting and DoS Prevention** The timer system is a potential vector for denial-of-service attacks. An adversary could attempt to schedule millions of timers at a single block height, overwhelming execution capacity, or fill the timer queue with spam to crowd out legitimate users. Cowboy employs multiple layers of defense:

**Per-Actor Timer Limits**

Each actor is limited to a maximum of **1,024 active timers** at any time. This hard cap prevents any single actor from monopolizing the timer queue. Attempts to schedule beyond this limit MUST revert.

**Progressive Deposit Model**

Creating a timer requires a **deposit** that scales with the actor's total active timer count:

`deposit(n) = base_deposit × (1 + floor(n / 100))`

Where n is the actor's current active timer count and `base_deposit` is a governance-tunable parameter (default: **10 CBY**). This means:

*   *Timers 1-99: 10 CBY each
*   *Timers 100-199: 20 CBY each
*   *Timers 200-299: 30 CBY each
*   ...and so on

Deposits are **fully refunded** when the timer fires or is cancelled. This model allows legitimate actors with few timers to operate cheaply while making large-scale timer spam prohibitively capital-intensive.

### Same-Block Exponential Pricing

To prevent "timer bomb" attacks where an actor schedules many timers for the same target block, an **exponential surcharge** applies when an actor schedules multiple timers for the same block height:

`surcharge(k) = base_cost × 2^max(0, k - 16)`

Where k is the number of timers this actor already has scheduled for the target block. The first 16 timers for any given block cost the base rate. Beyond that:

*   *Timer 17: 2× base cost
*   *Timer 18: 4× base cost
*   *Timer 19: 8× base cost
*   *Timer 32: 65,536× base cost

This allows legitimate use cases (e.g., an actor scheduling a handful of related timers for the same block) while making concentrated timer attacks economically infeasible.

### Timer Queue Basefee

Similar to the EIP-1559 basefee mechanism for cycles and cells, Cowboy maintains a **timer basefee** that adjusts based on global timer queue pressure:

`timer_basefee_{i+1} = timer_basefee_i × (1 + clamp((Q - T) / (T × alpha), -delta, +delta))`

Where:

*   *Q = current total timer queue depth (across all tiers)
*   *T = target queue depth (governance-tunable, default: **100,000**)
*   *alpha = **8**, delta = **0.125** (same as cycle/cell basefees)

When the timer queue is congested, the basefee rises, making timer creation more expensive and naturally throttling demand. The timer basefee is **burned**, aligning incentives with network health.

### Per-Block Execution Budget

Each block reserves a dedicated portion of its compute budget for timer execution:

*   ***Timer budget:** 20% of block cycle capacity (default: **2,000,000 cycles**)
*   *Timers compete for this budget via the GBA auction
*   *Remaining 80% is available for user transactions

This separation ensures that timer storms cannot completely crowd out regular transactions, and vice versa.

**Attack Mitigation Summary**

| Attack Vector | Mitigation |
| :--- | :--- |
| Schedule millions of timers | Progressive deposit (capital lockup) |
| Sybil attack across many actors | Per-block execution budget caps total work |
| Timer bomb (many timers, one block) | Exponential same-block surcharge |
| Fill queue far in advance | Timer basefee rises with queue depth |
| Outbid everyone perpetually | Anti-starvation boost for deferred timers |
| DoS then cancel for refund | Deposits are only refunded after fire/cancel; surcharges are not refunded |

*Note: The exponential same-block surcharge is a **fee**, not a deposit—it is burned and not refunded on cancellation. This prevents an attacker from locking up block capacity and then cancelling to recover costs.*

## Asynchronous Execution and Multi-Block Semantics

A fundamental property of the actor model is that message passing is inherently asynchronous. In Cowboy, this asynchrony becomes especially important when actors interact with off-chain Runners, as job execution may span multiple blocks. This section defines the execution semantics and the programming model developers must follow.

### The Single-Block Atomicity Guarantee

Cowboy provides **atomicity only within a single block**. When an actor’s message handler executes, all state reads, writes, and outbound messages within that handler are atomic—they either all commit or all revert. However, **there is no cross-block atomicity**. Once a handler completes and the block is finalized, subsequent handlers (triggered by replies, timers, or new messages) execute in the context of potentially different world state.

### Why Cross-Block Transactions Are Not Provided

Consider an actor that reads state, calls a Runner, and wants to continue execution when the result arrives:

```
# CONCEPTUAL - NOT HOW COWBOY WORKS
async def handle_trade(self, msg):
    price = self.storage.get("price") # Block N: reads $100
    if price < 150:
        analysis = await runner.llm(...) # Suspends... Runner executes...
        # Block N+5: Resumes here
        # But price may now be $200
        # The branch (price < 150) is no longer valid
        self.execute_buy(price) # Dangerous: stale assumptions
```

This pattern creates fundamental problems:

1.  **Stale State:** Values read before the yield may have changed.
2.  **Invalid Control Flow:** Branches taken based on pre-yield state may no longer be appropriate.
3.  **Composability Explosion:** Nested yields and actor-to-actor calls create a tree of inter-leavings where each path depends on potentially invalidated assumptions.
4.  **Adversarial Griefing:** Attackers can deliberately mutate state between yield points to exploit stale assumptions.

Providing cross-block atomicity would require either global locks (destroying parallelism and creating deadlock vectors) or speculative execution with rollbacks (creating griefing opportunities and unpredictable costs). Cowboy explicitly rejects these approaches.

**The Message-Passing Continuation Model**

Instead of implicit continuations, Cowboy uses **explicit message passing** for all asynchronous operations. When an actor needs to perform an off-chain job, it sends a message to the Runner system actor and receives the result as a separate message in a later block:

```
from cowboy_sdk import actor, send, RUNNER

@actor
class TradingBot:

    def handle_trade(self, msg):
        """Initiate a trade analysis - Block N"""
        price = self.storage.get("price")

        if price < 150:
            # Send job request to Runner system actor
            # Include all context needed to continue later
            send(RUNNER, {
                "job_type": "llm",
                "prompt": f"Analyze buying opportunity at ${price}",
                "reply_to": self.address,
                "reply_handler": "handle_analysis_result",
                "context": {
                    "original_price": price,
                    "request_block": current_block()
                }
            })

    def handle_analysis_result(self, msg):
        """Process Runner result - Block N+K"""
        result = msg.result
        context = msg.context

        # Re-read current state
        current_price = self.storage.get("price")

        # Validate assumptions before proceeding
        if current_price != context["original_price"]:
            # Price changed - abort or re-evaluate
            self.storage.set("last_abort_reason", "price_changed")
            return

        # Assumptions valid - proceed with action
        if "bullish" in result.lower():
            self.execute_buy(current_price)
```

**Design Principles**

This model embodies several important principles:

1.  **No Hidden Control Flow**
    Every state transition is triggered by an explicit message. There are no implicit callbacks or suspended coroutines. Developers can trace execution by following messages.
2.  **Runner Is Just Another Actor**
    The Runner system is not special syntax—it’s a system actor that receives job requests and sends result messages. The same message-passing pattern applies to actor-to-actor communication, timer callbacks, and Runner results.
    ```
    User TX -> Actor A -> [message] -> Runner System Actor -> [off-chain execution]
                                         ↓
    Actor A <- [result message] <- Runner System Actor
    ```
3.  **Explicit Context Capture**
    Any state needed in the continuation must be explicitly included in the context field. This forces developers to think about what data crosses the yield boundary and prevents accidental closure over stale references.
4.  **Re-Validation is Mandatory**
    The programming model makes it clear that when `handle_analysis_result` executes, it’s a new transaction in a new block. Developers must re-read and validate any state assumptions.

**Correlation and Message Ordering**

The protocol provides infrastructure for correlating requests and responses:
*   **Correlation IDs:** Each outbound job request includes a unique `correlation_id`. The Runner system actor includes this ID in the response message, allowing actors to match responses to requests.
*   **No Ordering Guarantees:** If an actor sends multiple Runner requests, responses may arrive in any order. Actors must handle out-of-order delivery.

**Timeout and Failure Handling**

Asynchronous operations can fail silently—a Runner may crash, a network partition may occur, or a job may simply take too long. Actors MUST implement timeout handling for any operation that depends on an external response. The recommended pattern combines correlation tracking with native timers:

```
def handle_trade(self, msg):
    correlation_id = generate_id()

    # Store pending request info
    self.storage.set(f"pending:{correlation_id}", {
        "type": "trade_analysis",
        "submitted_block": current_block(),
        "context": {...}
    })

    # Send job request
    send(RUNNER, {
        "correlation_id": correlation_id,
        "job_type": "llm", ... })

    # Schedule timeout - returns a timer_id for later cancellation
    timer_id = set_timer(
        height=current_block() + 100,
        handler="handle_timeout",
        data={"correlation_id": correlation_id}
    )
    # Store timer_id so we can cancel it when result arrives
    self.storage.set(f"timer:{correlation_id}", timer_id)

def handle_analysis_result(self, msg):
    correlation_id = msg.correlation_id
    # Cancel timeout timer using stored timer_id
    timer_id = self.storage.get(f"timer:{correlation_id}")
    if timer_id:
        cancel_timer(timer_id)
        self.storage.delete(f"timer:{correlation_id}")

    # Process result
    pending = self.storage.get(f"pending:{correlation_id}")
    if pending is None:
        return # Already timed out or duplicate
    self.storage.delete(f"pending:{correlation_id}")

    # Continue processing...

def handle_timeout(self, msg):
    correlation_id = msg.correlation_id
    pending = self.storage.get(f"pending:{correlation_id}")
    if pending is None:
        return # Result already arrived

    # Clean up
    self.storage.delete(f"pending:{correlation_id}")
    self.storage.delete(f"timer:{correlation_id}")

    # Handle timeout - retry, abort, or escalate
    self.handle_job_failure(correlation_id, "timeout")
```

**Key points:**
*   Store the `timer_id` returned by `set_timer()` so it can be cancelled when the result arrives.
*   Always check for the pending request before processing—it may have been cleaned up by a timeout.
*   Clean up all associated state (pending request, timer reference) in both success and timeout paths.
*   Consider implementing retry logic with exponential backoff for transient failures.

**SDK Ergonomics**

While the protocol uses explicit message passing, the SDK provides ergonomic helpers that compile down to this pattern:

```
from cowboy_sdk import actor, runner

@actor
class TradingBot:

    @runner.continuation
    async def handle_trade(self, msg):
        price = self.storage.get("price")

        if price < 150:
            # SDK helper - compiles to message passing
            result = await runner.llm(
                prompt=f"Analyze buying opportunity at ${price}",
                context={"original_price": price}
            )

            # Developer still validates - SDK doesn't hide this
            if self.storage.get("price") != result.context["original_price"]:
                return

            if "bullish" in result.output.lower():
                self.execute_buy(price)
```

The `@runner.continuation` decorator transforms the async function into:
1.  A request handler that sends the message and stores continuation state.
2.  A result handler that retrieves continuation state and resumes execution.

This is syntactic sugar only—the underlying execution model remains explicit message passing with single-block atomicity.

**Comparison with Other Models**

| Model | Atomicity | Developer Burden | Griefing Resistance |
| :--- | :--- | :--- | :--- |
| Ethereum (sync calls) | Single TX | Low | High |
| Cross-block locks | Multi-block | Low | Low (deadlocks, lock griefing) |
| Optimistic + rollback | Multi-block | Medium | Low (rollback spam) |
| Cowboy (message passing) | Single block | Medium | High |

Cowboy's approach trades some developer convenience for predictable execution semantics and resistance to adversarial manipulation.

## The Cowboy Actor VM (PVM)

**Why Python?**

Python is the language of AI and the glue of modern software. It is where builders already live, with a massive developer base and an unmatched ecosystem of tools and libraries. Cowboy turns that familiarity into production power: write a simple Python script and deploy an accountable, always-on actor, while the protocol enforces determinism and safety. The result is a shorter path from idea to launch and a much wider funnel of teams who can build.

### Execution Environment and Determinism Guarantees

Actors are **Python programs** executed in the PVM inside a deterministic sandbox. For the network to reach consensus, every node must produce the exact same result from the same code. This section specifies the comprehensive set of consensus-critical rules that guarantee determinism.

#### Runtime Environment

*   ***No JIT Compilation:** The PVM operates in pure interpretation mode. Just-In-Time compilation is forbidden, as JIT optimizations are a source of non-determinism across runs and platforms.
*   ***Deterministic Memory Management:** Memory is managed via deterministic reference counting. The cyclic garbage collector is disabled. Objects are deallocated immediately when their reference count reaches zero, ensuring predictable memory behavior.
*   ***Fixed Recursion Limit:** The recursion limit MUST be set to a consensus-defined constant (**256** by default). Stack depth enforcement is integrated with cycle metering.

#### Numeric Determinism

*   ***Floating-Point Operations:** All floating-point operations MUST use a cross-platform, deterministic software-based math library (softfloat), not the host machine's native FPU. This prevents micro-variations across different CPU architectures (x86 vs ARM, different FPU implementations).
*   ***Integer Arithmetic:** Python's arbitrary-precision integers are deterministic. No overflow behavior varies across platforms.
*   ***Decimal Module:** If the decimal module is included in the whitelist, it MUST use a fixed rounding mode (ROUND_HALF_EVEN) and fixed precision, specified at the consensus level.
*   ***Math Functions:** Transcendental functions (sin, cos, log, exp, etc.) MUST use deterministic implementations from the softfloat library, not platform-native libm.

#### Hash Seed and Collection Ordering

Python's default hash randomization (`PYTHONHASHSEED`) is a critical source of non-determinism. The PVM enforces:

*   ***Fixed Hash Seed:** `PYTHONHASHSEED` MUST be set to a consensus-defined constant (0). This ensures `hash()` returns identical values across all nodes.
*   ***Dictionary Ordering:** Python 3.7+ guarantees insertion-order iteration for dict. This is deterministic and permitted.
*   ***Set Replacement:** The built-in `set` and `frozenset` types have non-deterministic iteration order even with a fixed hash seed (due to hash collisions and table resizing). The PVM MUST replace `set` with `ordered_set`, an insertion-ordered set implementation provided by the standard library. Code using `set` syntax transparently receives `ordered_set` semantics.
*   ***Forbidden Hash Operations:** Actors MUST NOT rely on `hash()` values for anything persisted to storage or sent in messages, as hash values are not guaranteed stable across PVM versions.

**String and Text Handling**

*   ***Unicode Normalization:** All string comparisons MUST use NFC (Canonical Decomposition, followed by Canonical Composition) normalization. The PVM normalizes all input strings to NFC on ingestion.
*   ***Fixed Locale:** The locale MUST be fixed to C.UTF-8 (POSIX). Locale-dependent operations (collation, case conversion) use Unicode rules, not system locale.
*   ***Case Folding:** Case-insensitive comparisons MUST use Unicode case folding (`str.casefold()`), which is locale-independent.
*   ***String Interning:** Identity comparisons (`is`) on strings are forbidden in user code. The PVM MAY raise a warning or error. Use equality (`==`) for string comparison.
*   ***Encoding:** All strings are UTF-8. Other encodings MUST be explicitly converted via `encode()`/`decode()` with the `errors='strict'` policy.

**Serialization**

All data that crosses trust boundaries (storage, messages, Runner job parameters) MUST use a canonical serialization format:

*   ***Format:** CBOR (RFC 8949) with Core Deterministic Encoding Requirements (Section 4.2).
*   ***Canonical Rules:**
    *   Map keys MUST be sorted by byte-wise lexicographic order of their encoded form.
    *   Integers MUST use the shortest encoding.
    *   No indefinite-length arrays or maps.
    *   Floats MUST be encoded as 64-bit IEEE 754 (no float16/float32 downcasting).
    *   No duplicate map keys.
*   ***Forbidden:** The pickle module is forbidden. It is non-deterministic, insecure, and version-dependent.
*   ***JSON:** If JSON is needed for human-readable output, `json.dumps()` MUST use `sort_keys=True`, `separators=(',',':')`, and `ensure_ascii=False`.
*   ***Custom Types:** User-defined classes that need serialization MUST implement the `__cowboy_serialize__()` and `__cowboy_deserialize__()` protocol methods.

**Module and Dependency Management**

*   ***Whitelisted Imports:** Actors can only import modules from a strict, consensus-defined whitelist. Each module is pinned to an exact version.
*   ***No C Extensions:** C extension modules (numpy, pandas, etc.) are forbidden. They introduce hardware-dependent behavior, platform-specific optimizations, and are difficult to audit for determinism.
*   ***No Dynamic Imports:** `importlib`, `__import__()`, and dynamic module loading are forbidden.
*   ***Initial Whitelist (v1):**
    *   `collections`, `dataclasses`, `enum`, `functools`, `itertools`
    *   `json` (with canonical constraints), `re`, `struct`
    *   `math` (deterministic implementation), `decimal` (fixed precision)
    *   `typing`, `abc`
    *   `hashlib` (for keccak256, sha256)
    *   `cowboy_sdk` (Cowboy standard library)
    Additional modules MAY be added via governance after determinism audit.

**Exception Handling**

*   ***Exception Types:** Exception types and their inheritance hierarchy are deterministic.
*   ***Exception Messages:** Exception message strings MAY vary across platforms or Python versions. Actors MUST NOT branch on exception message text content.
*   ***Tracebacks:** Traceback objects are stripped before any on-chain storage or message passing. They are available only for local debugging.

**Forbidden Operations and Patterns**

The following operations are forbidden and will raise `DeterminismError` at parse time or runtime:

| Category | Forbidden |
| :--- | :--- |
| **System** | `sys.exit()`, `os.environ`, `os.system()`, `subprocess.*` |
| **Time** | `time.time()`, `datetime.now()`, `time.sleep()` |
| **Randomness** | `random.*` (use `cowboy_sdk.vrf` instead) |
| **Networking** | `socket.*`, `urllib.*`, `http.*`, `requests.*` |
| **Filesystem** | All except `/tmp` scratch space (256 KiB limit, wiped post-handler) |
| **Reflection** | `eval()`, `exec()`, `compile()`, `globals()` modification, `setattr()` on modules |
| **Introspection** | `sys._getframe()`, `inspect.currentframe()`, `gc.*` |
| **Weak References** | `weakref.*` (non-deterministic collection timing) |
| **Threading** | `threading.*`, `multiprocessing.*`, `concurrent.*` |
| **Identity** | `is` comparisons on strings or numbers (use `==`) |

**Determinism Testing**

The reference PVM implementation includes a **determinism test harness** that:
1.  Executes actor code on multiple platforms (x86, ARM) and Python builds.
2.  Compares all outputs, state transitions, and cycle counts.
3.  Flags any divergence as a consensus-critical bug.

Actors deployed to mainnet SHOULD be tested with this harness during development.

Each handler invocation receives a fixed amount of memory (10 MiB by default) and is metered in cycles and cells.

Actor storage is persistent and subject to **rent**. This mechanism keeps full nodes compact and encourages efficient data lifecycle policies.

### A New Security Model

The vast majority of wallet hacks in the Ethereum ecosystem are due to code audit bugs. While borrowing from the lessons of Ethereum, Solidity, and Bitcoin over the past decade, our new security model is simple: the code is easy to read. Python's existing analysis and auditing tools, combined with Cowboy's native guards and decorators, place it at a natural advantage when it comes to preventing on-chain attacks.

#### Storage and State Persistence

Cowboy's storage architecture is designed for verifiability, performance, and cross-VM compatibility. It is built on a three-layer model:

1.  **The Ledger:** An append-only log of blocks, serving as the sequential, historical source of truth for all transactions.
2.  **The Triedb:** The canonical state repository, which uses a **Merkle-Patricia Trie (MPT)**, similar to Ethereum, to generate a verifiable `state_root` for each block. This layer holds the authoritative state of all accounts, code, and storage.
3.  **Auxiliary Indexes:** Rebuildable, read-optimized tables for data like transaction hashes or event topics. These indexes are derived from the Ledger and Triedb and allow for fast queries without being part of the consensus-critical state root.

This design ensures compatibility with existing MPT-based tooling while providing enhanced query performance.

**Cross-VM Compatibility**

To support both the native Python VM (PVM) and a future EVM execution environment, the state trie is designed to be VM-neutral.

*   ***State Separation:** A `vm_ns` (VM namespace) flag is embedded directly into storage keys. This allows PVM and EVM storage slots for the same address to coexist without collision, enabling a single actor address to have state in both environments.
*   ***Cross-VM Calls:** A standardized C-ABI (Application Binary Interface) wrapper is defined at the protocol level. This allows the storage layer to remain neutral while enabling seamless and predictable calls between the PVM and EVM.

All actor storage is subject to **state rent**, paid in CBY. This mechanism requires actors to pay for the storage they occupy over time, preventing state bloat and encouraging efficient data management. If rent is not paid, the storage may be pruned by the network after a grace period.

**Pricing: Cycles and Cells**

Ethereum introduced **gas** as a single scalar. Cowboy splits pricing into two independent meters:

*   ***Cycles** measure compute: Python operations and host calls (e.g., send, set-timer, blob-commit) each have a fixed cost. Cycles resemble **Erlang reductions**: a budget of discrete steps that bounds how long a handler runs.
*   ***Cells** measure bytes: calldata, return data, blobs, and storage all consume cells.

Each block adjusts two basefees (one per meter) using the familiar EIP-1559 feedback loop. Users specify max prices and optional tips for each meter. Basefees are **burned**, while tips go to validators. This dual model makes fees more predictable and fair.

**On-Chain Metering**

To ensure deterministic execution, Cowboy's on-chain resource consumption is metered with precision:

*   ***Cycles:** Computational work is metered by instrumenting the Python VM at the bytecode level. Every instruction has a fixed Cycle cost, defined in a consensus-critical cost table. This approach ensures that all computational paths, including loops and function calls, are accurately measured.
*   ***Cells:** Data and storage work is metered at specific I/O boundaries. Cells (where 1 Cell = 1 byte) are consumed for transaction payloads, return data, state storage (`storage_set`), and temporary scratch space used by an actor during execution.

This strict, deterministic metering is the primary defense against computational and state-based denial-of-service attacks.

**Off-Chain Fee Model** It is critical to distinguish on-chain gas from off-chain job fees. The protocol does **not** calculate gas for Runner execution. Instead, it facilitates a free market where Runners set their own prices.

A Runner's operational costs (CPU time, memory, data transfer) determine its market price for a given job. Runners are free to ignore jobs they deem underpriced. This model allows for efficient price discovery for real-world resources and accommodates a wide range of computational tasks, from simple data fetching to intensive AI model inference, without burdening the on-chain consensus with non-deterministic and complex cost calculations.

### Off-Chain Compute: The Runner Marketplace

Many applications need access to web data, ML inference, or heavy transforms. Any actor can post a job with a price and latency target. **Runners**—off-chain workers who stake CBY—pick up jobs, execute them, and post results.

This market is **verifiable**: the chain accepts results under various trust models chosen by the developer. Runners who lie or miss deadlines risk being challenged and **slashed**.

**Asynchronous Task Framework and Runner Reliability**

To ensure that off-chain computation does not impact the stability of the core network, Cowboy implements a fully asynchronous and deferred task framework. The lifecycle of an off-chain job is decoupled from the main transaction flow:

1.  **Task Submission:** An actor submits a task by calling a dispatcher contract. The submission defines the task, the number of Runners required, and a `result_schema` that specifies the expected output format and constraints (e.g., max return size).
2.  **Runner Selection & Health:** A committee of Runners is implicitly and deterministically selected for the task using a Verifiable Random Function (VRF). This selection is made from a dynamic **active runner list**. To remain on this list, Runners must periodically send a `heartbeat()` transaction, ensuring that tasks are only assigned to nodes that are proven to be online and responsive.
3.  **Execution and Submission:** Selected Runners execute the task. If a Runner chooses not to perform the work, it can call a `skip_task` function, explicitly and verifiably passing responsibility to the next Runner in the deterministic sequence. Results are submitted to a dedicated contract.
4.  **Deferred Callback:** Once the required number of results are collected, the system constructs and signs a _deferred transaction_. This transaction, which contains the call to the original actor's callback function, is then executed in a future block.

This deferred model ensures that even long-running off-chain jobs or network delays do not congest the primary execution of the chain. The mandatory `result_schema` provides clarity for Runners, while the health and skipping mechanisms create a robust and self-healing network of off-chain workers.

**Cowboy's Off-Chain Tiered Trust Model**

| Mode | Level of Trust |
| :--- | :--- |
| **N-of-M Quorum** | Runners execute results; the runtime accepts the consensus result from a committee. |
| **N-of-M with Dispute** | Runners stake a bond; disputers may prove an incorrect result within a fixed window. |
| **TEE Attestation** | An N-of-M committee or single runner executes the result within a Trusted Execution Environment. |
| **ZK-Proof (v2)** | Runners provide zk-SNARKs with results for cryptographic verification. |

Runners and actors are matched by their **Entitlements**, a framework for policy and security constraints (e.g., TEE-only, data residency).

**Runner Resource Accounting and Pricing**

Off-chain computation cannot be directly metered by the protocol—runners execute on their own hardware outside of consensus. This section specifies how Cowboy handles resource accounting, price discovery, and payment for off-chain jobs.

**Resource Bounds** Every job submission MUST include explicit resource bounds specified by the actor:

```
job_spec = {
    "type": "llm",
    "model_id": "0x...",        # Registered model hash
    "prompt": "...",
    "bounds": {
        "max_input_tokens": 4000,      # Maximum input size
        "max_output_tokens": 2000,     # Maximum output size
        "max_wall_time_seconds": 60,   # Maximum execution time
        "max_memory_mb": 512,          # Maximum memory usage
        "max_retries": 2,              # Retries on transient failure
        "max_price": 100_000_000       # Maximum price in CBY wei
    },
    "trust_model": "n_of_m",
    "tee_required": false
}
```

Bounds serve multiple purposes:
*   *Cost ceiling:* The actor knows their maximum exposure before submitting.
*   *Runner filtering:* Runners can evaluate whether they can fulfill the job within bounds.
*   *Timeout enforcement:* Jobs exceeding `max_wall_time_seconds` are considered failed.
*   *DoS prevention:* Unbounded jobs are rejected at submission.

If a runner cannot complete a job within the specified bounds, the job fails. The runner is not penalized for failing to complete an impossible job (see Payment and Failure Handling below).

**Price Discovery: Posted Prices with Priority Tips** Cowboy uses a hybrid pricing model combining posted prices with optional priority tips:

**Runner Rate Cards**

Runners publish rate cards to the Runner Registry, specifying their prices per resource unit:

```
rate_card = {
    "runner_address": "0x...",
    "rates": {
        "llm_input_token": 1000,      # CBY wei per input token
        "llm_output_token": 3000,     # CBY wei per output token
        "http_request": 50000,        # CBY wei per HTTP request
        "compute_second": 10000,      # CBY wei per second of compute
        ...
    },
    "supported_models": ["0x...", "0x..."],
    "min_job_value": 10000,           # Minimum job size
    "max_job_value": 10_000_000_000,  # Maximum job size
    "entitlements": ["tee_sgx", "region_us"]
}
```

Rate cards are stored on-chain and can be updated by the runner at any time (subject to a cooldown period to prevent manipulation).

**Job Pricing**

When an actor submits a job, the expected price is calculated from the runner's rate card and the job's resource bounds:

`expected_price = Σ(rate[resource] × bounds[resource])`

The actor escrows `max_price` at submission. The actual payment is:

`actual_payment = min(reported_usage × rates, max_price)`

**Priority Tips**

For time-sensitive jobs, actors can include a **tip** that goes directly to the runner(s):

```
job_spec = {
    ...
    "max_price": 100_000_000,
    "tip": 10_000_000, # Priority tip, paid on completion
}
```

Tips incentivize runners to prioritize jobs during periods of high demand. The tip is paid in addition to the usage-based fee.

**Runner Selection**

When a job is submitted, the protocol:
1.  Filters runners by entitlements (actor's requirements ⊆ runner's capabilities).
2.  Filters runners by supported models.
3.  Filters runners by price (runner's expected price ≤ actor's `max_price`).
4.  Selects committee via VRF from eligible runners.

This creates a competitive market: runners with lower rates and better entitlements are more likely to be selected.

**Trust Model for Resource Reporting** Runners report their actual resource usage when submitting results. The protocol uses a **trust-but-verify** model with escalating assurance levels:

**Default: Reputation-Based Trust**

For most jobs, the protocol trusts runner-reported usage, subject to:
1.  **Reputation scores:** Runners accumulate reputation based on successful job completions, disputes lost, and uptime. Low-reputation runners may be excluded from job selection.
2.  **Anomaly detection:** If reported usage is >2× the expected usage (based on job type and historical data), the result is automatically flagged for review.
3.  **Slashing for fraud:** If a runner is proven to have misreported usage (via challenge), they are slashed 30% of their stake.

**Optional: TEE-Attested Metering**

For high-value jobs or when stronger guarantees are required, actors can set `tee_required: true`. In TEE mode:
1.  The runner executes the job inside a Trusted Execution Environment (SGX, TDX, or SEV).
2.  The TEE measures actual resource consumption.
3.  The runner submits an attestation report alongside the result.
4.  The protocol verifies the attestation against known-good TEE measurements.
5.  Reported usage in the attestation is authoritative.

TEE-attested jobs command a premium (runners set separate rates for TEE execution), but provide cryptographic guarantees of correct metering.

**Attestation Verification**

TEE attestations are verified by a dedicated system actor (`0x97` TEE Verifier) that maintains:
*   A registry of trusted TEE signing keys (updated via governance).
*   Expected measurement hashes for approved runner software.
*   Revocation lists for compromised keys.

**Payment and Failure Handling**

Payment depends on the outcome of the job and the reason for any failure:

| Outcome | Runner Payment | Actor Refund | Rationale |
| :--- | :--- | :--- | :--- |
| **Success** | `min(reported_usage × rates, max_price) + tip` | `max_price - actual_payment` | Normal completion |
| **Runner fault** (timeout, invalid result, crash) | 0 | 100% of escrow | Runner failed to perform |
| **Impossible job** (bounds too tight) | 0 | 100% of escrow | Actor set unrealistic bounds |
| **Actor fault** (malformed input) | 0 | 0 | Actor submitted bad job |
| **External fault** (API down, model unavailable) | Pro-rata based on progress | Remainder of escrow | Neither party at fault |
| **Timeout (no fault)** | Minimum fee (gas cost recovery) | Remainder of escrow | Network delay, no one at fault |

**Determining Fault**

Fault determination follows these rules:
1.  **Runner fault:** Runner accepted the job but failed to deliver a valid result within bounds. Evidence: timeout exceeded, result fails schema validation, or N-of-M quorum shows divergent results.
2.  **Impossible job:** Runner demonstrates that the job cannot be completed within bounds. Evidence: multiple runners report the same failure mode (e.g., "output exceeded max_tokens at 50% completion").
3.  **Actor fault:** Job input is malformed or violates protocol rules. Evidence: schema validation failure on input, or runner returns standardized error code.
4.  **External fault:** Failure due to external dependencies. Evidence: runner provides proof of external failure (e.g., HTTP 503 response, API rate limit).

**Pro-Rata Payment**

For impossible jobs and external faults, runners receive partial payment based on demonstrable progress:

`pro_rata_payment = (work_completed / total_work_estimate) × expected_price`

For LLM jobs, `work_completed` is measured in tokens generated before failure. For HTTP jobs, it may be measured in requests completed. For MCP jobs, it is measured by tool calls completed. The runner must provide evidence of partial completion (e.g., partial output, intermediate state hash).

**Dispute Resolution** Any party can challenge a job outcome within the challenge window (15 minutes):

**Actor challenges runner (overcharge):**
1.  Actor posts 100 CBY bond.
2.  Actor provides evidence: benchmark data, comparable job costs, statistical analysis.
3.  Arbitration: If reported usage is >3σ above expected for job type, runner is presumed to have overcharged.
4.  Resolution: Runner slashed, actor refunded difference + challenger reward.

**Runner challenges actor (unfair fault assignment):**
1.  Runner posts 100 CBY bond.
2.  Runner provides evidence: execution logs, TEE attestation, proof of external failure.
3.  Arbitration: Review of evidence against fault criteria.
4.  Resolution: If runner was wrongly faulted, receive payment + bond back; actor loses dispute bond.

**Third-party challenges (collusion, fraud):**
1.  Anyone can challenge suspicious patterns (e.g., runner and actor colluding on fake jobs).
2.  Evidence: on-chain analysis, statistical anomalies.
3.  Resolution: Both parties slashed if collusion proven, challenger rewarded.

**Anti-Gaming Measures** The resource accounting system includes safeguards against manipulation:
1.  **Rate card cooldown:** Runners cannot change rates more than once per epoch (1 hour). Prevents bait-and-switch.
2.  **Minimum job value:** Runners can set a minimum job value to avoid spam.
3.  **Reputation decay:** Reputation scores decay over time, requiring ongoing good behavior.
4.  **Sybil resistance:** New runners start with zero reputation and limited job allocation. Building reputation requires stake lockup time.
5.  **Price bands:** Governance can set acceptable price ranges for job types. Runners outside bands are flagged (not excluded, but visible to actors).

**LLM Result Verification**

LLM outputs present a unique verification challenge: unlike deterministic computation, the same prompt can produce semantically equivalent but byte-different outputs. This section defines how Cowboy achieves consensus on inherently non-deterministic results.

**The Challenge of Non-Deterministic Outputs** For deterministic jobs (e.g., HTTP fetch, hash computation), verification is straightforward—all honest runners produce identical outputs. LLM inference breaks this assumption:

```
Prompt: "What is the capital of France?"

Runner 1: "The capital of France is Paris."
Runner 2: "Paris is the capital of France."
Runner 3: "France's capital city is Paris."
```

All three outputs are correct, but none match byte-for-byte. Traditional N-of-M quorum fails. Even with identical model weights, `temperature=0`, and fixed seeds, floating-point variations across hardware can produce different token sequences.

For subjective tasks (summarization, creative writing, recommendations), the problem deepens—there may be no single “correct” answer.

**Verification Modes** Cowboy provides multiple verification modes suited to different job types. Actors select the appropriate mode based on their correctness requirements and cost tolerance:

| Mode | Runners | Verification | Challenge Scope | Cost | Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| none | 1 | None | Non-delivery only | Lowest | Prototyping, low-stakes |
| economic_bond | 1 | Objective checks | Objective failures | Low | Subjective generation |
| majority_vote | N-of-M | Vote on field value | Objective failures | Medium | Classification |
| structured_match | N-of-M | Verifier functions | Objective failures | Medium | Structured extraction |
| deterministic | N-of-M | Exact match + TEE | Full reproduction | High | Critical deterministic |
| semantic_similarity | N-of-M | Embedding threshold | Objective failures | High | Subjective with similarity |

Mode selection in job spec:

```
job_spec = {
    "type": "llm",
    "model_id": "0x...",
    "prompt": "...",
    "verification": {
        "mode": "structured_match",
        "runners": 3,
        "threshold": 2, # 2-of-3 must agree
        "checks": [...]
    }
}
```

**Verification Mode Details**

**none Mode**
Single runner, no verification. The protocol only guarantees that a result was returned within bounds. No challenge window for output quality.
```
"verification": {"mode": "none"}
```
Use for: prototyping, internal logic, high-volume low-stakes tasks where speed matters more than correctness guarantees.

**economic_bond Mode**
Single runner posts a bond. Output is subject to objective checks only. The actor accepts subjective risk.
```
"verification": {
    "mode": "economic_bond",
    "bond_multiplier": 2.0, # Runner bonds 2x job value
    "objective_checks": ["schema_valid", "min_length", "no_prompt_leak"]
}
```
Use for: subjective generation (summaries, creative writing) where the market, not the protocol, judges quality. Runners with poor subjective outputs lose reputation over time as actors avoid them.

**majority_vote Mode**
N-of-M runners execute the job. A specified field must achieve majority consensus.
```
"verification": {
    "mode": "majority_vote",
    "runners": 5,
    "threshold": 3,
    "vote_field": "classification" # Field to vote on
}
```
Result is accepted when ≥`threshold` runners return the same value for `vote_field`. Other fields (e.g., reasoning) are taken from any agreeing runner.
Use for: classification, sentiment analysis, yes/no decisions, categorical outputs.

**structured_match Mode**
N-of-M runners execute the job. Results are compared using SDK verifier functions on specified fields.
```
"verification": {
    "mode": "structured_match",
    "runners": 3,
    "threshold": 2,
    "checks": [
        {"fn": "json_schema_valid", "schema": {...}},
        {"fn": "structured_match", "fields": ["entity_name", "entity_type"]},
        {"fn": "numeric_tolerance", "field": "confidence", "tolerance": 0.05}
    ]
}
```
Use for: entity extraction, data parsing, structured Q&A, any task with well-defined output fields.

**deterministic Mode**
N-of-M runners execute with pinned configuration. Outputs must match exactly. TEE attestation required.
```
"verification": {
    "mode": "deterministic",
    "runners": 3,
    "threshold": 3, # All must match
    "tee_required": true,
    "inference_config": {
        "temperature": 0,
        "seed": 12345,
        "framework": "vllm@0.4.1"
    }
}
```
Use for: critical decisions requiring reproducibility, audit trails, regulatory compliance.

**semantic_similarity Mode**
N-of-M runners execute the job. Outputs are compared using embedding similarity.
```
"verification": {
    "mode": "semantic_similarity",
    "runners": 3,
    "threshold": 2,
    "similarity_threshold": 0.85,
    "embedding_model": "0x..." # Pinned embedding model
}
```
Runners compute embeddings locally using the specified model. Results are considered matching if cosine similarity exceeds threshold. At least `threshold` runners must form a matching cluster.

*Trust assumption:* The security of this mode depends on community trust in the specified embedding model. A compromised or poorly-chosen embedding model could map semantically different outputs to similar vectors, undermining verification. Actors should use well-established, deterministic embedding models from the protocol's approved set.

Use for: summaries, paraphrasing, translation—tasks where semantic equivalence matters more than exact wording.

**SDK Verifier Functions** The SDK provides a standard library of verifier functions for `structured_match` mode. These execute on the runner alongside the main job:

| Function | Description | Parameters |
| :--- | :--- | :--- |
| `exact_match()` | Byte-for-byte equality | — |
| `json_schema_valid(schema)` | Validates against JSON schema | `schema`: JSON Schema object |
| `structured_match(fields)` | Specified fields must match | `fields`: list of field names |
| `majority_vote(field)` | Field value with >50% agreement | `field`: field name |
| `supermajority_vote(field, threshold)` | Field value with >`threshold` agreement | `field`, `threshold` |
| `numeric_tolerance(field, tolerance)` | Numbers within ±`tolerance` | `field`, `tolerance` |
| `numeric_range(field, min, max)` | Number within bounds | `field`, `min`, `max` |
| `set_equality(field)` | Unordered collection equality | `field` |
| `contains_all(substrings)` | Output contains required strings | `substrings`: list |
| `contains_none(substrings)` | Output excludes strings | `substrings`: list |
| `regex_match(pattern)` | Output matches regex | `pattern` |
| `length_bounds(min, max)` | Output length within bounds | `min`, `max` |
| `semantic_similarity(threshold)` | Embedding cosine similarity | `threshold` |
| `no_prompt_leak()` | Output doesn't contain system prompt | — |
| `entropy_check(min_entropy)` | Output isn't repetitive/degenerate | `min_entropy` |

**Custom Verifier Functions**
Actors can deploy custom verifier functions as actors. Custom verifiers are invoked by the protocol after runner submission:
```
"verification": {
    "mode": "structured_match",
    "checks": [
        {"fn": "json_schema_valid"},
        {"fn": "custom", "actor": "0x...", "method": "verify_output"}
    ]
}
```
The custom verifier actor receives:
*   The job spec.
*   All runner outputs.
*   Runner metadata (addresses, attestations).
And returns:
*   `{valid: true, canonical_output: ...}` — accept, with optional canonical output.
*   `{valid: false, reason: ...}` — reject all outputs.

Custom verifier execution consumes on-chain cycles (paid by actor). This enables domain-specific verification logic (e.g., checking SQL query results against a database, validating code compiles).

**Objective Failure Criteria** Regardless of verification mode, certain failures are objectively verifiable and result in runner slashing:

| Failure | Detection | Penalty |
| :--- | :--- | :--- |
| Schema violation | Output fails declared JSON schema | Slash 10% |
| Timeout | No result within `max_wall_time` | Slash 5% |
| Empty/garbage output | Output below `min_length` or fails entropy check | Slash 10% |
| Wrong model | TEE attestation shows different model hash | Slash 30% |
| Non-delivery | Runner accepted job but never submitted | Slash 20% |
| Prompt injection leak | Output contains system prompt markers | Slash 15% |

These checks run automatically. No challenge required—the protocol detects and penalizes.

**Subjective Correctness and the Market** For subjective outputs (summaries, creative content, recommendations), Cowboy explicitly **does not** attempt to define "correct." Instead:
1.  **Actors accept risk** when choosing `economic_bond` or `none` modes.
2.  **Reputation reflects quality** — actors who receive poor outputs stop using that runner.
3.  **Competition drives quality** — runners with better outputs earn more jobs.
4.  **Transparency enables choice** — runner stats (completion rate, dispute rate, repeat usage) are public.

This philosophy reflects a key design principle: **the protocol guarantees execution integrity, not output quality**. Quality is a market outcome.

**Challenge Scope by Mode**

| Mode | Challengeable | Evidence Required |
| :--- | :--- | :--- |
| none | Non-delivery only | Timeout proof |
| economic_bond | Objective failures | Schema/entropy/leak check |
| majority_vote | Objective failures | Schema/entropy/leak check |
| structured_match | Objective failures | Schema/verifier check |
| deterministic | Full reproduction | Matching config + divergent output |
| semantic_similarity | Objective failures | Schema/entropy/leak check |

For deterministic mode, challengers can dispute by providing reproduction evidence: exact config + proof that re-execution produces different output. Protocol selects neutral runners to verify.

**External Data and Oracle Semantics**

Cowboy actors frequently need access to external data: price feeds, web APIs, public datasets, and web pages. Unlike on-chain computation, external data is inherently mutable and non-deterministic. This section defines how Cowboy handles verification of external data sources.

**Sources of Non-Determinism** External data fetches can produce different results for legitimate reasons:

| Source | Example |
| :--- | :--- |
| Content changes | Website updated between runner requests |
| Geo-variation | Different content served to different regions |
| Time-sensitivity | Prices, news change by the second |
| Rate limiting | Some runners throttled, others not |
| CDN caching | Different edge nodes serve different versions |
| A/B testing | Site serves different versions to different users |
| Dynamic rendering | JS-rendered content varies by timing |

Even with N-of-M quorum, runners hitting the same URL within seconds can receive different responses. The protocol must define what "consensus" means for mutable data.

**Data Source Classification** Different external data sources require different verification strategies:

| Type | Characteristics | Verification Strategy |
| :--- | :--- | :--- |
| Deterministic API | Versioned, stable, structured (blockchain RPC, static files) | Exact match |
| Semi-stable API | Structured with variable metadata (REST APIs with timestamps) | Structured match, ignore metadata |
| Time-series data | Values change over time (price feeds) | Median/majority with freshness bounds |
| Web scraping | Unstructured, highly variable (HTML pages) | Extraction-based matching |
| Authenticated endpoints | Requires credentials | Single runner + TEE + secrets management |

**Freshness Requirements** Actors specify data freshness constraints:
```
job_spec = {
    "type": "http",
    "url": "https://api.exchange.com/price/BTC",
    "freshness": {
        "max_age_seconds": 10,
        "timestamp_field": "$.data.timestamp",
        "reference": "block" # or "submission", "absolute"
    }
}
```
Reference modes:
*   `block` — Data timestamp must be within `max_age_seconds` of the block timestamp when results are committed.
*   `submission` — Data timestamp must be within `max_age_seconds` of job submission time.
*   `absolute` — Actor specifies an exact timestamp; data must be from that point in time (tolerance).

Runners MUST:
1.  Fetch data from the source.
2.  Extract timestamp from specified field (or use fetch time if no field specified).
3.  Reject and retry if timestamp is outside freshness window.
4.  Include fetch metadata in result attestation.

**Snapshot Modes** When multiple runners fetch mutable data, the protocol must select a canonical result. Actors specify snapshot semantics:
```
job_spec = {
    "type": "http",
    "url": "...",
    "snapshot": {
        "mode": "first_valid"
    }
}
```
Available modes:
*   `first_valid` — First runner to submit a valid result sets the canonical snapshot. Other runners verify they could obtain similar data (within verification tolerance), but the first result is authoritative. Best for: web content, API responses where any valid snapshot is acceptable.
*   `median` — For numeric data, take the median value across all runner results. Outliers (beyond `outlier_threshold`) are flagged but don’t prevent consensus. Best for: price feeds, numeric measurements.
    ```
    "snapshot": {
        "mode": "median",
        "outlier_threshold": 0.02 # Flag results >2% from median
    }
    ```
*   `majority` — For categorical or structured data, accept the value returned by a majority of runners. Best for: status checks, boolean conditions, categorical API responses.
*   `latest` — Accept the most recent valid result (by timestamp). Useful when fresher data is strictly preferred. Best for: rapidly-changing feeds where recency trumps consensus.

**Extraction-Based Verification** For web scraping and unstructured sources, compare extracted data rather than raw responses:

```
job_spec = {
    "type": "http_extract",
    "url": "https://disclosures.house.gov/...",
    "extraction": {
        "method": "css_selector", # or "xpath", "regex", "jsonpath"
        "selectors": {
            "representative": "div.member-name::text",
            "ticker": "td.asset-ticker::text",
            "transaction_type": "td.tx-type::text",
            "amount": "td.amount::text"
        },
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "representative": {"type": "string"},
                    "ticker": {"type": "string"},
                    "transaction_type": {"enum": ["buy", "sell"]},
                    "amount": {"type": "string"}
                }
            }
        }
    },
    "verification": {
        "mode": "structured_match",
        "runners": 3,
        "threshold": 2,
        "fields": ["[*].ticker", "[*].transaction_type"]
    }
}
```

Runners:
1.  Fetch the URL.
2.  Apply extraction rules to raw response.
3.  Validate extracted data against schema.
4.  Submit extracted data (not raw HTML).

Verification compares extracted fields across runners. Raw response differences (ads, timestamps, session tokens) don't cause verification failures.

**Domain Entitlements** HTTP access is governed by the Entitlements system. Actors declare which domains they need access to, and runners advertise which domains they can fetch:

```
# Actor entitlement (in deployment manifest)
"entitlements": {
    "http_domains": ["api.coingecko.com", "disclosures.house.gov"]
}

# Runner capability
"capabilities": {
    "http_domains": ["*"] # or specific list
}
```

The protocol provides curated domain sets for common use cases:

| Domain Set | Contents |
| :--- | :--- |
| `price_feeds` | Major exchange APIs, CoinGecko, etc. |
| `government_us` | SEC, Congress, Federal Register |
| `social_apis` | Twitter/X API, Reddit API (authenticated) |
| `blockchain_rpc` | Ethereum, Bitcoin, major L2 RPC endpoints |

Actors can require a domain set:
```
"entitlements": {
    "http_domain_set": "price_feeds"
}
```
Runners who don't support required domains are excluded from job selection.

**Source Attestation** Runners provide cryptographic evidence of data provenance:
```
result = {
    "data": {...},
    "attestation": {
        "fetch_timestamp": 1702500000,
        "url": "https://...",
        "http_status": 200,
        "response_hash": "0x...",      # Hash of raw response
        "tls_cert_fingerprint": "0x...", # Proves connection to real server
        "response_headers": {
            "etag": "...",
            "cache-control": "...",
            "last-modified": "..."
        }
    }
}
```

Attestations enable:
*   After-the-fact auditing of data sources.
*   Dispute resolution when data changes.
*   Proof that runner connected to authentic server (not MITM).

For TEE-enabled jobs, the attestation is signed by the TEE enclave, providing hardware-backed proof.

**Secrets Management** Authenticated API access requires credential handling. Cowboy provides a dedicated Secrets Manager system actor (`0x08`) for secure credential storage:

**Architecture:**
```
Actor Storage (encrypted) <- Actor writes secrets
↓
Secrets Manager (0x08)
↓
TEE Runner (decrypts in enclave)
↓
External API
```

Storing secrets:
```
from cowboy_sdk import secrets

# Actor stores an API key (encrypted to authorized runners)
secrets.store(
    key="broker_api_key",
    value="sk-...",
    access_policy={
        "runners": ["tee_required"],    # Only TEE runners
        "entitlements": ["region_us"],    # Only US-based runners
        "job_types": ["http"]            # Only for HTTP jobs
    }
)
```

Using secrets in jobs:
```
job_spec = {
    "type": "http",
    "url": "https://api.broker.com/portfolio",
    "auth": {
        "type": "bearer",
        "secret_ref": "broker_api_key"  # Reference to stored secret
    },
    "verification": {
        "mode": "economic_bond",
        "tee_required": true
    }
}
```

How it works:
1.  Actor encrypts secret to the Secrets Manager's public key.
2.  Secret is stored on-chain (encrypted) with access policy.
3.  When a job references the secret, protocol verifies runner meets access policy.
4.  Runner's TEE requests secret from Secrets Manager.
5.  Secrets Manager verifies TEE attestation, releases secret encrypted to enclave.
6.  Secret is decrypted only inside TEE, never exposed to runner operator.

Security properties:
*   Secrets are never stored in plaintext on-chain.
*   Runner operators cannot access secrets (TEE isolation).
*   Access policies are enforced by the protocol.
*   Secret rotation is supported (actors can update values).
*   Audit log of secret access is maintained.

**Limitations:**
*   Requires TEE-capable runners (limits runner pool).
*   Actor must trust TEE implementation.
*   Secrets Manager is a system actor (governance-controlled).

**Verification Modes for HTTP Jobs** HTTP jobs support the same verification modes as LLM jobs, with adaptations for external data:

| Mode | Runners | Snapshot | Verification |
| :--- | :--- | :--- | :--- |
| none | 1 | N/A | Non-delivery only |
| economic_bond | 1 | N/A | Schema + freshness |
| majority | N-of-M | majority | Extracted fields match |
| median | N-of-M | median | Numeric tolerance |
| structured_match | N-of-M | first_valid | Verifier functions |
| deterministic | N-of-M | Exact | Byte-equality (static sources only) |

**Example: Price Feed Oracle**

```
job_spec = {
    "type": "http",
    "url": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
    "freshness": {
        "max_age_seconds": 30,
        "reference": "block"
    },
    "extraction": {
        "method": "jsonpath",
        "selectors": {
            "price": "$.bitcoin.usd"
        }
    },
    "snapshot": {
        "mode": "median",
        "outlier_threshold": 0.01
    },
    "verification": {
        "mode": "median",
        "runners": 5,
        "threshold": 3
    }
}
```

Five runners fetch the price. The median value is accepted as canonical. Any runner reporting a price >1% from median is flagged (potential manipulation or stale cache).

## Randomness

Each block derives a random beacon from the previous quorum certificate using a threshold BLS VRF. Actors can access this for fair committee sampling, lotteries, and games.

## Consensus and Networking

Cowboy uses **Simplex consensus**, a BFT protocol optimized for simplicity, fast finality, and MEV resistance through mandatory proposer rotation.

### Protocol Overview

**Simplex** is a streamlined BFT protocol that achieves consensus with optimal latency while maintaining a simple design and provable liveness. Unlike protocols with stable leaders (PBFT), Simplex rotates proposers every block—a deliberate choice that reduces MEV extraction opportunities.

**Consensus flow:**
1.  **Propose:** The current proposer (selected by VRF) broadcasts a block proposal.
2.  **Vote:** Validators vote on the proposal; votes are buffered until quorum.
3.  **Certify:** Upon reaching `2f+1` votes, a Quorum Certificate (QC) is formed.
4.  **Finalize:** Block with QC from the next round is final and irreversible.

Under **partial synchrony**, the protocol guarantees safety (no conflicting blocks finalized) at all times, and liveness (progress) when network delay is bounded.

**Key parameters:**
*   ***Block time:*** ~1 second target.
*   ***Finally:*** ~2 seconds under normal conditions.
*   ***Fault tolerance:*** Tolerates up to `f < n/3` Byzantine validators.

**Buffered signature verification:**
To optimize performance, Cowboy buffers incoming validator signatures and performs batch verification when quorum (`2f+1`) is reached, rather than verifying each signature individually. This reduces CPU overhead by ~65% compared to eager verification. If batch verification fails, a binary search identifies the offending signature(s) and the peer is blocked.

### Validator Set

The validator set is **open and permissionless**. Any account that meets the minimum stake threshold may register as a validator:

**Requirements:**
*   Stake ≥ minimum validator_stake (governance-tunable).
*   Self-stake only (no delegation in v1).
*   Must run compliant validator software.
*   Must maintain network connectivity.

**No fixed cap** on validator count. BLS signature aggregation ensures consensus efficiency regardless of set size. Economic factors (reward dilution, minimum stake) provide natural bounds.

**Validator lifecycle:**
1.  **Register:** Stake CBY, submit validator public key (BLS12-381).
2.  **Activate:** Validator becomes active at next epoch boundary.
3.  **Operate:** Propose blocks, vote, earn rewards.
4.  **Exit:** Signal unbonding; stake locked for unbonding period.
5.  **Withdraw:** After unbonding period, stake is returned.

**Epochs and Rotation**

**Epoch structure:**
*   **Epoch duration:** 3600 blocks (~1 hour).
*   **Validator set updates:** Only at epoch boundaries.
*   **Proposer selection:** Per-block VRF, weighted by stake.

At each epoch boundary:
1.  New validators who registered during the epoch are activated.
2.  Validators who signaled exit are removed from active set.
3.  Slashing penalties are applied.
4.  Epoch randomness seed is derived from previous epoch’s final QC.

**Proposer rotation:** Each block’s proposer is selected via VRF:
`proposer = VRF_select(epoch_seed, block_height, active_validators, stakes)`
Selection probability is proportional to stake, ensuring larger stakers propose more often (and earn more tips).

**Staking and Rewards**

**Staking:**
*   Minimum stake: Governance-tunable (e.g., 50,000 CBY at genesis).
*   No maximum stake per validator.
*   Self-bonded only: delegation deferred to v2.

**Rewards:** Block rewards (from inflation) are distributed proportionally to stake:
`validator_reward = (validator_stake / total_staked) × block_inflation_reward`
Proposers additionally receive transaction tips for their proposed blocks.

**Unbonding:**
*   Unbonding period: **7 days**.
*   During unbonding, stake is not counted for consensus.
*   Stake can still be slashed during unbonding (for offenses discovered late).
*   After unbonding completes, stake is withdrawable.

**Slashing**

Cowboy uses a **conservative slashing model** that prioritizes validator participation over punitive penalties. Most offenses result in jailing (temporary removal) rather than stake destruction:

| Offense | Detection | Penalty |
| :--- | :--- | :--- |
| **Double signing** | Two valid signatures for different blocks at same height | Jail + slash 1% of stake |
| **Proposer equivocation** | Two different valid proposals for same slot | Jail + slash 1% of stake |
| **Extended downtime** | Missing >50% of votes over 1000 blocks | Jail (no slash) |
| **Invalid block proposal** | Block fails consensus validation | Jail (no slash) |

**Jailing:**
*   Jailed validators are removed from active set immediately.
*   Must wait jail period (24 hours) before unjailing.
*   Unjailing requires explicit transaction from validator.
*   Repeated offenses increase jail duration exponentially.

**Rationale for conservative slashing:**
*   Encourages validator participation (lower risk).
*   Protects against accidental slashing from bugs/misconfig.
*   Jailing still removes bad actors from consensus.
*   Severe offenses (double signing) still incur economic penalty.

**View Changes and Leader Failure**

If the current proposer fails to produce a block (crash, network partition), the protocol executes a **view change:**
1.  **Timeout:** Validators waiting for proposal trigger timeout after `block_time × 2`.
2.  **New-View:** Validators broadcast highest QC they’ve seen.
3.  **Leader election:** Next leader is determined by VRF (skipping failed proposer).
4.  **Resume:** New leader proposes block extending highest QC.

View changes add latency but preserve safety. The protocol ensures no conflicting blocks can be finalized even during leader failures.

**Finally and Reorgs**

**Finally guarantee:** Once a block has a Commit Certificate (CC), it is **final and irreversible**. No honest validator will vote for a conflicting block.

**Pre-finality window:** Blocks without CC may theoretically be reverted (reorg). In practice, with 1-second blocks and 2-round commit, the pre-finality window is ~2 seconds.

**Runner handling of reorgs:**
*   Runners are **stateless** with respect to chain state.
*   Jobs reference block height, not block hash.
*   If a reorg occurs before finality, affected jobs may need to resubmit.
*   Actors should design handlers to be **idempotent** (safe to replay).
*   For critical jobs, actors can wait for finality before considering results confirmed.

**Network Layer**

**Transport:** QUIC over TLS 1.3 (required).

**Gossip protocol:**
*   Transactions: Flood to all peers.
*   Blocks: Proposer broadcasts; validators relay.
*   Votes: Direct to proposer (reduces gossip overhead).

**Peer discovery:** DHT-based with bootstrap nodes.

**Message authentication:** All consensus messages signed with validator's BLS key.

**Dedicated Lanes**

Block space is partitioned into **dedicated lanes** with reserved capacity, ensuring that autonomous actor operations (timers, runner results) are not crowded out by user transaction spikes:

| Lane | Reserved Capacity | Priority | Contents |
| :--- | :--- | :--- | :--- |
| **System** | 5% | Highest | Validator updates, governance, slashing |
| **Timer** | 20% | High | Scheduled timer executions |
| **Runner** | 25% | High | Runner job results and attestations |
| **User** | 50% | Normal | User-initiated transactions |

**Lane semantics:**
*   Each lane has its own basefee, adjusted independently based on lane utilization.
*   Unused capacity in higher-priority lanes cascades down to lower-priority lanes.
*   Transactions are tagged by type at submission; the proposer cannot reassign lanes.
*   If a lane is full, excess transactions wait for the next block (no spillover to other lanes).

**Example:** A DeFi actor with scheduled timer-based rebalancing will execute reliably even during a user transaction surge, because the timer lane has 20% reserved capacity that user transactions cannot consume.

**MEV Prevention**

Cowboy takes a multi-layered approach to MEV mitigation, avoiding the latency cost of encrypted mempools while still providing strong guarantees:

1.  **Mandatory Proposer Rotation**
    Simplex consensus rotates proposers every block via VRF. Unlike protocols with stable leaders (where one validator might propose 10+ consecutive blocks), no single proposer observes transaction flow across multiple blocks. This fundamentally limits:
    *   Cross-block MEV strategies.
    *   Block-builder collusion patterns.
    *   Proposer-searcher relationships.
2.  **VRF-Based Transaction Ordering**
    Within each block, the proposer orders transactions deterministically using VRF:
    `order_key = VRF(proposer_key, tx_hash, block_height)`
    The proposer commits to this ordering in the block header. Validators verify the ordering is correct—any deviation causes block rejection. This prevents:
    *   Strategic transaction placement by proposers.
    *   Insertion of proposer’s own transactions at advantageous positions.
    *   Sandwich attack construction.
3.  **Fast Finality Window**
    With ~1s blocks and ~2s finality:
    *   **Observation window:** Attackers have less than 1s from tx broadcast to block inclusion.
    *   **Reorg risk:** Zero after finality; attacks requiring reorgs are impossible.
    *   **Front-running:** Extremely difficult given the tight timing constraints.
4.  **Lane Isolation**
    Dedicated lanes prevent a class of MEV attacks where adversaries spam the mempool to delay victim transactions:
    *   Timer-triggered trades execute regardless of user lane congestion.
    *   Runner results post reliably even during activity spikes.
    *   Adversaries cannot selectively delay transactions by lane type.

**Why No Encrypted Mempool**
Commit-reveal schemes (e.g., threshold encryption) add one block of latency for decryption. Given Cowboy’s already-minimal MEV surface:
*   VRF ordering removes proposer discretion.
*   Rotation prevents multi-block observation.
*   Fast finality closes the timing window.
*   Lane separation prevents congestion attacks.
The marginal benefit of encryption doesn’t justify the latency and complexity cost. This decision may be revisited if empirical MEV data warrants it.

## Data Availability, State Rent, and Storage

This section specifies how Cowboy manages on-chain data, state growth, and the economic mechanisms that keep the network sustainable.

### Inline Data vs. Blobs

Small outputs (≤ 64 KiB) are stored inline and paid for with cells. Larger artifacts MUST be stored as content-addressed blobs (e.g., IPFS) with the multihash referenced on-chain.

| Data Size | Storage Method | Payment |
| :--- | :--- | :--- |
| ≤ 64 KiB | Inline (on-chain) | Cells (one-time) + rent |
| > 64 KiB | External blob (IPFS, Arweave) | Cells for hash only |

### State Rent Model

All persistent actor storage is subject to state rent—an ongoing fee for occupying space in the global state trie. Rent creates economic pressure to use storage efficiently and ensures that inactive or abandoned actors don’t bloat the network indefinitely.

**Market-Based Rent Pricing**

Rent rates adjust dynamically based on total network state size, similar to EIP-1559 fee adjustment:

`rent_rate_(i+1) = rent_rate_i × (1 + clamp((S - T) / (T × alpha), -delta, +delta))`

Where:
*   S = current total state size (bytes across all actors).
*   T = target state size (governance-tunable, e.g., 100 GB).
*   alpha = 8, delta = 0.125 (same as cycle/cell basefees).

When state grows beyond target, rent rises, discouraging new storage and incentivizing cleanup. When state shrinks, rent falls, making storage cheaper.

**Rent calculation per actor:**

`epoch_rent = actor_storage_bytes × rent_rate_per_byte_per_epoch`

**Rent Payment Options** Actors can pay rent in two ways:

1.  **Auto-deduct (default)**
    Each epoch, rent is automatically deducted from the actor's CBY balance:
    ```
    On epoch boundary:
      if actor.balance >= epoch_rent:
        actor.balance -= epoch_rent
      else:
        enter_grace_period(actor)
    ```
2.  **Prepaid rent**
    Actors can deposit rent in advance for predictable costs:
    ```
    from cowboy_sdk import rent

    # Prepay rent for 1000 epochs
    rent.prepay(epochs=1000)

    # Check rent status
    status = rent.status() # {paid_through_epoch: 15000, balance_epochs: 847}
    ```
    Prepaid rent is non-refundable but provides cost certainty.
3.  **Sponsored rent**
    Any account can pay rent on behalf of any actor:
    `rent.sponsor(actor_address="0x...", epochs=100)`
    This enables "keep-alive" services for public goods or critical infrastructure.

**Minimum Balance Reserve** To prevent actors from accidentally spending all their CBY and entering grace period, each actor has a **minimum balance reserve**:

`minimum_reserve = estimated_annual_rent × reserve_multiplier`

Where `reserve_multiplier` is governance-tunable (default: 0.1, i.e., ~5 weeks of rent).

The reserve:
*   Cannot be spent on transactions or jobs.
*   Is automatically used for rent if main balance is insufficient.
*   Provides a buffer before grace period begins.
*   Can be withdrawn only when closing the actor.

**Grace Period and Eviction**

When an actor cannot pay rent (balance and reserve exhausted, no prepaid epochs remaining), they enter a grace period:

**Timeline:**
```
Epoch N: Rent due, insufficient funds -> Grace period begins
Epoch N+168: Grace period ends (7 days) -> Warning period begins
Epoch N+240: Warning period ends (3 more days) -> Eviction eligible
Epoch N+241: Storage evicted
```
Total time from first missed payment to eviction: 10 days.

During grace period:
*   Actor remains fully functional.
*   Can still receive messages, execute handlers, modify storage.
*   Actor is flagged as “rent overdue” (visible on-chain).
*   A catch-up fee accumulates (10% of missed rent).

During warning period:
*   Same as grace period.
*   Actor is flagged as “eviction imminent”.
*   Events emitted to alert dependent actors.

**Catch-up fee:**
To exit grace period: `payment_required = missed_rent × 1.1`
This 10% penalty discourages intentionally entering grace period to defer payment.

**Eviction Mechanics**

When eviction occurs:

**What is evicted:**
*   Actor’s storage (all key-value data).
*   Active timers associated with the actor.

**What is preserved:**
*   Actor’s code (immutable, stored separately).
*   Actor’s address (reserved, cannot be reused).
*   Actor’s balance (if any remains).
*   Storage root hash (for potential restoration).

**Eviction process:**
1.  Storage root hash is recorded on-chain.
2.  All storage keys are marked for deletion.
3.  Storage is pruned from active state trie at next epoch.
4.  Actor enters “dormant” state.

**Dormant actors:**
*   Cannot execute handlers (no storage to read/write).
*   Can still receive CBY transfers.
*   Can be restored if storage data is provided.

**Storage Restoration**

Evicted storage can be restored if the original data is available:

**Requirements:**
1.  Original storage data (e.g., from backup, archive node, or third party).
2.  Data must hash to the recorded storage root.
3.  Payment of all back-rent plus catch-up fees.

**Restoration process:**
```
from cowboy_sdk import storage

# Anyone with the data can restore an actor
storage.restore(
    actor_address="0x...",
    storage_data=original_data,  # Must match recorded root hash
    pay_from=sponsor_address    # Can be actor itself or sponsor
)
```

Cost to restore: `restoration_cost = back_rent + (back_rent × 0.1) + current_epoch_rent`

This mechanism allows:
*   Actors to backup their own storage and self-restore.
*   Third parties to restore important public infrastructure.
*   Recovery from accidental rent lapses.

*Note: If no one has the original data, storage is permanently lost. Actors should maintain off-chain backups of critical data.*

**Ledger Growth and Pruning**

**Block Storage** Blocks are append-only and never pruned from the canonical chain:

*Block data per year (estimate):*
~1 KB/block × 86,400 blocks/day × 365 days ≈ 31 GB/year
This is the minimum storage requirement for full nodes.

**State Storage** The state trie holds current account balances, actor code, and actor storage:
*   Full nodes keep only the current state trie.
*   Historical state (old trie versions) can be pruned after finality.
*   State size is bounded by rent economics—high rent discourages bloat.

**Archive Nodes** Archive nodes keep full historical state for every block:
*   Required for historical queries, indexing, block explorers.
*   Not required for consensus participation.
*   Can reconstruct any historical state.
*   Enable storage restoration for evicted actors.

**Node Types**

| Node Type | Blocks | Current State | Historical State | Storage Est. (Year 1) |
| :--- | :--- | :--- | :--- | :--- |
| Light client | Headers only | Merkle proofs | No | < 1 GB |
| Full node | All | Yes | Pruned | ~50-100 GB |
| Archive node | All | Yes | All | ~500 GB+ |

**Light Clients**

Light clients enable trustless verification without storing full state:

**Capabilities:**
*   Verify block headers form valid chain.
*   Verify transaction inclusion via Merkle proofs.
*   Verify state queries via Merkle proofs against state root.
*   Submit transactions.

**Limitations:**
*   Cannot execute arbitrary queries without full node.
*   Rely on full nodes for proof generation.

**Use cases:** Mobile wallets, embedded devices, browser extensions.

**Storage Quotas and Bonds**

Each actor has a base storage quota and can extend it with bonds:

| Quota Tier | Storage Limit | Requirement |
| :--- | :--- | :--- |
| Base | 1 MiB | Default for all actors |
| Extended | Up to 8 MiB | Storage bond required |

**Storage bond:**
`bond_required = (requested_quota - 1 MiB) × bond_rate_per_byte`

The bond is:
*   Locked while quota is in use.
*   Returned when quota is reduced.
*   Forfeited if actor is evicted (incentivizes rent payment).
*   Subject to rent on the full allocated quota (not just used storage).

## Monetary Policy and Fees

The native asset is **CBY**. Cowboy launches with a genesis supply of 1 billion CBY and a declining issuance schedule to reward validators.

### Inflation Schedule

**Emission rate** (decreasing over time):
*   **Year 1-2:** 8% annual inflation.
*   **Year 3-4:** 5% annual inflation.
*   **Year 5-6:** 3% annual inflation.
*   **Year 7-10:** 2% annual inflation.
*   **Year 10+:** 1% terminal inflation.

### Fee Distribution

*   **Basefees (Cycles & Cells):** 100% burned.
*   **Tips:** Paid to block proposers.
*   **Off-Chain Job Payments:** Flow to Runners, with a small percentage to the protocol treasury.

Because basefees are burned, the net supply may become deflationary if the chain is heavily used.

### Governance and Upgrades

Early governance is conducted by a **foundation multisig** with a standard timelock, sunsetting into token-weighted on-chain governance. Upgrades are shipped as **hot-code upgrades**, coordinated by governance.

### Applications

Cowboy is designed for real-world, autonomous workloads.
*   **AI Agents:** Actors that call LLMs for planning or retrieval, with verifiable transcripts and bounded costs. A trading agent could, for example, scrape congressional stock disclosures, use an LLM to parse the trades, and autonomously execute a copy-trade.
*   **DeFi Automation:** An agent that monitors an ETH/BTC pool and automatically rebalances it based on price deviations from a 7-day moving average, all without external keepers.
*   **Games:** Per-tick logic with VRF randomness; blob assets stored off-chain but committed on-chain.
*   **Oracles:** HTTP committees fetch data from allow-listed domains with commit-reveal and disputes.

### Why a Sovereign L1

A natural question arises: why build Cowboy as a sovereign Layer-1 rather than as an Ethereum Layer-2 (rollup), which would inherit Ethereum's security and liquidity?

**L2 Constraints**

Ethereum L2s come in two primary flavors, neither of which fits Cowboy's requirements:

**Optimistic Rollups:**
*   7-day withdrawal delay for fraud proof windows.
*   Agents needing fast liquidity access would be severely constrained.
*   Sequencer centralization creates MEV and censorship risks.

**ZK Rollups:**
*   Require execution to be provable in zero-knowledge circuits.
*   Python is not circuit-friendly; the PVM would need complete reimplementation.
*   Proving costs for complex actor logic would be prohibitive.
*   Current ZK-EVM projects took years and billions in funding for EVM alone.

Both approaches inherit EVM execution constraints or require building within them, forcing Cowboy to either abandon Python or build an entirely separate proving system.

**Why L1 Enables Cowboy's Design**

| Capability | L1 (Sovereign) | L2 (Rollup) |
| :--- | :--- | :--- |
| **Custom VM** | Native PVM with Python | Constrained to EVM or custom ZK circuit |
| **Block time** | Full control (1s target) | Bound by L1 finality for settlement |
| **Consensus** | Simplex with dedicated lanes, VRF ordering | Inherit sequencer model or Ethereum constraints |
| **Native timers** | Protocol-level, gas-efficient | Requires external keeper networks |
| **Runner integration** | Deep protocol integration with verification modes | Separate oracle infrastructure per capability |
| **Upgrade path** | Sovereign governance | Depends on rollup framework and L1 upgrades |

**The Trade-off**

Sovereignty comes with costs:
*   **Bridge risk:** Cross-chain asset transfers require trust assumptions beyond Ethereum’s security.
*   **Liquidity fragmentation:** Assets on Cowboy are not natively composable with Ethereum DeFi.
*   **Validator bootstrapping:** Must attract sufficient stake for economic security.

Cowboy accepts these trade-offs because the alternative—forcing autonomous Python agents into EVM constraints or waiting years for ZK-Python infrastructure—would compromise the core value proposition. The bridge design ($16) mitigates cross-chain risk through validator committees, rate limits, and future optimistic fallback paths.

## Ethereum Interoperability

Interoperability is a foundational design goal. The same secp256k1 key can control both a Cowboy account and an EVM address, letting agents hold ETH and ERC-20s, bridge assets, and sign EIP-1559 transactions under tight policy guards enforced by entitlements. A canonical bridge will carry funds and calldata, while Cowboy actors can subscribe to Ethereum events to trigger on-chain workflows.

## The State Transition Function

At the heart of Cowboy lies a deterministic state transition function that takes a block and an input state and returns the next state.

Let σ be the global state, B a block with transactions T_i, basefees (bf_c, bf_b), and randomness R.

1.  **Header/Proposer:** determined by Simplex; R derives from the parent QC.
2.  **Execute Transactions (ordered):**
    *   Validate signature, nonce, and balance.
    *   Initialize meters with user limits; charge intrinsic cells.
    *   Dispatch to target. Actor may send messages (fanout ≤ 1,024), schedule timers, and commit blobs; reentrancy depth ≤ 32.
    *   Enforce memory (10 MiB), mailbox (≤ 1,000,000), and storage quotas.
    *   Deduct fees: `cycles_used*(bf_c+tip_c) + cells_used*(bf_b+tip_b)`; burn basefees.
3.  **Deliver Timers:** Inject due timers at height(B).
4.  **Resolve Jobs:** Process commitments, reveals, challenges, and payouts.
5.  **Adjust Basefees:** Update (bf_c, bf_b) via EIP-1559 feedback.
6.  **Mint Rewards:** Distribute per-block inflation to validators.

A single reference implementation defines the canonical metering table for cycles.

**Terminology**

*   **Actor:** A Python program with persistent key/value state and a mailbox.
*   **Message:** A datagram delivered to an actor handler.
*   **Cycle:** Unit of metered on-chain compute.
*   **Cell:** Unit of metered bytes (1 cell = 1 byte).
*   **Runner:** Off-chain worker that executes a job and returns an attested result.
*   **Entitlement:** A permission governing an actor’s or runner’s capabilities.
*   **Model:** A registry entry describing an off-chain compute model’s digest and metadata.

**Normative Conventions**

This document uses MUST/SHOULD/MAY as defined in RFC 2119. Parameters marked **governance-tunable** can be changed by on-chain governance (see §11).

## 1. Accounts, Addresses, and Keys

### 1.1 Signatures.
External accounts MUST use **secp256k1** (ECDSA) with chain-id separation.

### 1.2 Actor address derivation (CREATE2-style).
New actor addresses MUST be: `addr = last_20_bytes(keccak256(creator || salt || code_hash))` where `code_hash = keccak256(python_source_bytes)`.

### 1.3 System address space.
The range `0x0000...0100` is reserved for **system actors and precompiles** (see §10).

## 2. Transaction Types & Encoding

### 2.1 Typed tx (EIP-1559 style, dual meters).
A transaction MUST include: `chain_id, nonce, to, value, cycles_limit, cells_limit, max_fee_per_cycle, max_fee_per_cell, tip_per_cycle, tip_per_cell, access_list?, payload, signature`.

### 2.2 Validity checks.
Nodes MUST reject a tx if: (a) limits exceed maxima (§13.1), (b) insufficient balance, (c) signature invalid, (d) access list invalid, or (e) payload decoding fails.

### 2.3 Fee accounting.
Let bc, bb be the block basefees for cycles/cells. Fees are: `fee = cycles_used * (bc + min(tip_per_cycle, max_fee_per_cycle - bc)) + cells_used * (bb + min(tip_per_cell, max_fee_per_cell - bb))`. Unused limits MUST be refunded at the user’s `max_fee * rates`.

### 2.4 EBNF (informative).
```
Tx = Header Body Sig
Header = chain_id nonce to value cycles_limit cells_limit max_fee_per_cycle max_fee_per_cell tip_per_cycle tip_per_cell [access_list]
Body = payload
Sig = secp256k1_signature_recoverable
```

## 3. Execution Model (Actors)

### 3.1 Runtime & Determinism.
*   Official SDKs: **Python SDK**. The runtime MUST enforce determinism:
    *   **Allowed operations**: Standard Python operations, file I/O limited to /tmp, cooperative yields via async/await.
    *   **Forbidden**: `sys.exit()`, random module (except chain VRF), `time.time()`/`datetime.now()`, `os.environ` access, socket/network operations, subprocess calls, path traversal outside /tmp.
    *   **Floating point**: Permitted; Cowboy provides a deterministic math library.
    *   **Scratch space**: `/tmp` MUST be per-invocation, capped at **256 KiB** (counts toward cells_used), wiped post-handler.

### 3.2 Memory & Storage.
*   **Per-call memory limit:** **10 MiB** heap memory.
*   **Per-actor persistent storage quota:** **1 MiB** (governance-tunable) with **state rent** (§4.4).
*   **Quota extensions:** An actor MAY post a **storage bond** up to **8 MiB** total; rent applies to the full allocated quota.

### 3.3 Messaging, Reentrancy, Timers.
*   **Delivery:** **Exactly-once**. Each message ID MUST be `keccak256(sender|nonce|msg_hash)` and recorded in a per-actor dedup set.
*   **Mailbox:** Capacity **1,000,000 items**; enqueue beyond the limit MUST revert.
*   **Per-tx fanout:** A transaction (including all nested sends) MUST NOT enqueue more than **1,024** messages.
*   **Reentrancy:** Allowed; **recursion/await depth cap = 32**.
*   **Timers (chain-native):** The following timer primitives are provided:
    *   `timer_id = set_timer(height, handler, data)` -- Schedule a one-time timer for the specified block height. Returns a unique timer_id.
    *   `timer_id = set_interval(every_n_blocks, handler, data)` -- Schedule a recurring timer. Returns a unique timer_id.
    *   `cancel_timer(timer_id)` -- Cancel a pending timer by its ID. Returns the deposit if successful.
    *   Timer delivery is **best-effort**; execution depends on the GBA auction (see Timer Rate Limiting).

### 3.4 Randomness.
*   Validators MUST generate a threshold-BLS VRF per block: `R_n = VRF_sk_epoch(QC_n-1))`. Actors MAY call an API which returns `HKDF(R_n, label)`.

### 3.5 Partial cost table (informative).
*   Exact metering is consensus-critical; implementers MUST match the reference cost table.

| Primitive | Cycles |
| :--- | :--- |
| Python arithmetic ops | 1 |
| Python function call | 10 |
| Dictionary get/set | 3 |
| List append/access | 2 |
| String operations (per char) | 1 |
| host: mailbox send (per msg excl. payload) | 80 |
| host: timer set/cancel | 200 |
| host: blob commit (per KiB) | 40 |

*Note: Cells meter bytes (payload, return data, inline blobs ≤ 64 KiB, /tmp).*

## 4. Fees, Metering, and Basefee Adjustment

### 4.1 Meters.
*   **Cycles:** Deterministic step count over Python operations + host calls.
*   **Cells:** Bytes used by calldata, return data, inline blobs (≤ 64 KiB), and /tmp.

### 4.2 Dual EIP-1559 basefees.
Let U_c, T_c be cycles usage/target; U_b, T_b be cells usage/target. With elasticity E=2 (hard cap E\*T_\*), adjustment uses:
`basefee_x_i+1 = max(1, basefee_x_i) * (1 + clamp((U_x - T_x)/(T_x*alpha), -delta, +delta)))`
where x ∈ {cycle, cell}, alpha = 8, delta = 0.125. Nodes MUST burn 100% of basefees; tips go to proposers/validators.

### 4.3 Targets (genesis defaults).
*   T_c (cycles target): 10,000,000 cycles (cap 20,000,000).
*   T_b (cells target): 500,000 bytes (cap 1,000,000).

### 4.4 State rent.
Persistent storage incurs rent per byte per epoch, which is governance-tunable. If unpaid for 90 epochs, keys MAY be pruned after a 30-epoch grace period.

## 5. Off-Chain Compute

### 5.1 Model registry.
`model_id = keccak256(weights|arch|tokenizer|license)` MUST uniquely identify a model revision. Publishing is permissionless with a refundable 1,000 CBY deposit. Governance MAY flag/ban models.

### 5.2 Runner staking.
Runners MUST stake `max(10,000 CBY, 1.5 × declared_max_job_value)` in the Runner Registry.

### 5.3 Job lifecycle.
1.  **Post:** Actor posts a job with escrowed price.
2.  **Assign:** For HTTP domains, a committee of M=5 is sampled; N=3 matching reveals finalize. LLM jobs MAY use committees or single-runner.
3.  **Commit:** Runner returns `commit = keccak256(output|salt)`.
4.  **Reveal:** Runner reveals `{output, salt, proof?}`.
5.  **Challenge:** A challenge window of 15 min is opened, requiring a 100 CBY bond.
6.  **Resolve:** Proven fault = 30% slash of active stake (70% to challenger, 30% burned).
7.  **Payout:** On finalization, 99% of job payment to runner(s), 1% to Treasury.

### 5.4 Determinism & bounds.
Jobs MUST pin `toolchain_digest` and `seed`. On-chain return data MUST be ≤ 64 KiB.

### 5.5 TEE option.
A job MAY set `tee_required=true`. A valid attestation MUST match accepted policies.

## 6. Consensus, Randomness, and Networking

### 6.1 Consensus.
**Simplex BFT PoS;** ~1s target block time; **finality on commit** (~2s). Proposers rotate every block using the VRF beacon (mandatory rotation for MEV resistance). Votes aggregate via **BLS12-381** with buffered batch verification.

### 6.2 P2P transport.
Implementations MUST support QUIC over TLS 1.3.

### 6.3 Dedicated Lanes.
Block space is partitioned into **dedicated lanes** with reserved capacity:

| Lane | Reserved Capacity | Priority | Contents |
| :--- | :--- | :--- | :--- |
| **System** | 5% | Highest | Validator updates, governance, slashing |
| **Timer** | 20% | High | Scheduled timer executions |
| **Runner** | 25% | High | Runner job results and attestations |
| **User** | 50% | Normal | User transactions |

Lane guarantees:
*   Timer and runner lanes prevent user transaction spam from blocking autonomous actor execution.
*   Unused capacity in higher-priority lanes cascades to lower-priority lanes.
*   Each lane has independent basefee tracking.

### 6.4 Gossip (mempool).
Public mempool with **FIFO within fee tiers**. Transactions are tagged by lane type. No private builders or encrypted mempool in v1—MEV resistance relies on fast finality and mandatory proposer rotation.

### 6.5 MEV Prevention.
Cowboy's MEV mitigation strategy combines multiple mechanisms:

**Mandatory proposer rotation:** Simplex consensus rotates proposers every block via VRF. Unlike stable-leader protocols, no single validator can observe transaction flow across multiple blocks, limiting MEV extraction windows.

**VRF-based transaction ordering:** Within each block, transactions are ordered by: `order_key = VRF(proposer_key, tx_hash, block_height)`. This deterministic-but-unpredictable ordering prevents proposers from strategically placing their own transactions.

**Fast finality:** ~2 second finality (2 Simplex rounds) minimizes the window for:
*   Front-running (limited observation time).
*   Sandwich attacks (high risk of failed execution).
*   Time-bandit attacks (chain never reorgs past finality).

**Dedicated lanes:** Reserved capacity for timers and runners ensures autonomous actors execute reliably regardless of user mempool congestion. Attackers cannot spam the user lane to delay victim transactions in other lanes.

**No encrypted mempool:** Commit-reveal schemes add latency and complexity. Given ~1s blocks and ~2s finality, the observation window is already minimal. The combination of VRF ordering + rotation + fast finality provides sufficient MEV resistance without the latency cost of encryption.

## 7. Data Availability & Blobs

### 7.1 Inline cap.
Inline blob cap is **64 KiB** per output.

### 7.2 External blobs.
Larger data MUST be **content-addressed** (e.g., IPFS). The on-chain commitment MUST be a multihash.

## 8. Economics, Inflation, and Fees

### 8.1 Ticker & supply.
CBY. Genesis supply **1,000,000,000 CBY**.

### 8.2 Inflation.
A decreasing inflation schedule is used to bootstrap network security.
*   **Year 1-2:** 8% annual inflation.
*   **Year 3-4:** 5% annual inflation.
*   **Year 5-6:** 3% annual inflation.
*   **Year 7-10:** 2% annual inflation.
*   **Year 10+:** 1% terminal inflation.

### 8.3 Distribution at genesis.
Validators **25%,** Treasury **25%,** Ecosystem **30%,** Investors **20%** (standard vesting).

### 8.4 Fee sinks & splits.
Basefees: **100% burned**. Tips: to proposers/validators. Off-chain job payments: **99%** to runners, **1%** to Treasury.

## 9. System Actors & Precompiles

*   ***0x01 Messaging:*** Enqueue and fanout messages.
*   ***0x02 Timers:*** Schedule/cancel timers.
*   ***0x03 Oracle/Runner:*** Manage off-chain jobs.
*   ***0x04 Blob store:*** Commit/retrieve blob multihashes.
*   ***0x05 Signer utils:*** secp/BLS/VRF helpers.
*   ***0x06 EventListener:*** Ethereum event subscriptions (see §16).
*   ***0x07 TEE Verifier:*** Verify TEE attestations against trusted measurements.
*   ***0x08 Secrets Manager:*** Secure credential storage and access control for TEE runners.

## 10. Developer Experience (DX)

*   ***SDKs:*** A primary Python SDK (`cowboy-py`) is provided.
*   ***Local dev:*** A suite of tools including a single-node devnet (`cowboyd`), runner simulator, faucet, and explorer will be available.
*   ***Best practices:*** Reentrancy guards, capability-scoped handles, and idempotent message handling are encouraged via the SDK.

## 11. Governance & Upgrades

*   ***Model:*** Foundation **5-of-9 multisig** sunsets after ~12 months to token-weighted on-chain governance.
*   ***Timelocks:*** Standard actions **7 days;** emergency fast-track **6 hours.**
*   ***Upgrades:*** **Hot-code upgrades** coordinated by governance.

## 12. Security Considerations

### 12.1 DoS limits (consensus-enforced; governance-tunable).
*   `max_tx_size = 128 KiB`
*   `max_message_depth_per_tx = 32`
*   `per_actor_per_block_cycles = 1,000,000` (burstable)

### 12.2 Runner safety.
Slashing for equivocation or invalid results. Committees mitigate single-runner faults.

### 12.3 Reentrancy.
Allowed but depth-capped; stdlib provides reentrancy guards.

### 12.4 Randomness bias.
Threshold-BLS VRF with epoch keys; actors derive sub-randomness via HKDF.

### 12.5 State rent & eviction.
Prevents state bloat; eviction windows protect liveness.

## 13. Parameters (Genesis Defaults)

**Execution:**
`memory_per_call = 10 MiB; storage_quota_per_actor = 1 MiB; reentrancy_depth = 32; fanout_per_tx = 1024.`

**Fees:**
`T_c = 10,000,000 cycles; T_b = 500,000 bytes; alpha = 8; delta = 0.125.`

**Consensus:**
`minimum_validator_stake = governance-tunable; epoch = 3600 blocks (~1 h); block_time = 1 s; finality = ~2 s; unbonding_period = 7 days; jail_period = 24 h; double_sign_slash = 1%; consensus_protocol = Simplex BFT.`

**Dedicated Lanes:**
`system_lane_capacity = 5%; timer_lane_capacity = 20%; runner_lane_capacity = 25%; user_lane_capacity = 50%.`

**Off-chain:**
`committee M = 5; threshold N = 3; challenge_window = 15 min; challenge_bond = 100 CBY; runner_stake_floor = 10,000 CBY.`

**State Rent:**
`target_state_size = governance-tunable; grace_period = 168 epochs (7 days); warning_period = 72 epochs (3 days); catch_up_fee = 10%; reserve_multiplier = 0.1.`

**Economics:**
`supply = 1,000,000,000; inflation follows the schedule in §8.2; basefee_burn = 100%; job_fee_to_treasury = 1%.`

## 14. Differences vs. Ethereum

*   **Execution:** Python actors vs. EVM contracts.
*   **Fees:** Dual meters (cycles/cells) vs. single gas scalar.
*   **Timers:** Native timers vs. external keepers.
*   **Off-chain compute:** Native verifiable market vs. external oracles.
*   **State:** Rent with eviction vs. indefinite storage.

## 15. Entitlements

A declarative, composable permissions system governs the capabilities of actors and runners. Entitlements control access to resources like networking, storage, and execution parameters, enforcing least-privilege by default. The system is enforced at deployment time, by the scheduler, and at the VM syscall gate.

### 15.1 Goals
*   Least privilege by default.
*   Deterministic enforcement.
*   Declarative & composable.
*   Auditable on-chain.

### 15.2 Objects & lifecycle
*   **Actor Entitlements:** Permissions the actor requires.
*   **Runner Entitlements:** Capabilities the runner provides.

### 15.3 Rules
1.  MUST: Actors require entitlements; runners provide them.
2.  MUST: Scheduler matches only if `requires ⊆ provides`.
3.  MUST: Syscalls fail if the corresponding entitlement is missing.
4.  MUST: Child actors only inherit entitlements marked `inheritable: true`.

*(For a full list of entitlements, refer to protocol specifications).*

## 16. Ethereum Interoperability

Cowboy’s interoperability with Ethereum is a primary design goal, enabling seamless asset transfer and cross-chain communication. This is achieved through a combination of shared cryptographic primitives, a canonical bridge, and event subscription mechanisms.

### 16.1. Account Unification
*   Cowboy external accounts (EOAs) MUST use the same `secp256k1` elliptic curve for signatures as Ethereum. This allows a single private key to control accounts on both networks, simplifying key management for users and agents.
*   An actor, through a host call, MAY verify an EIP-712 signed data structure against a given Ethereum address, enabling actors to validate off-chain authorizations from Ethereum users.

### 16.2. Canonical Bridge
A canonical, trust-minimized bridge contract deployed on both Cowboy and Ethereum SHALL facilitate the transfer of assets and arbitrary message data.

**Asset Bridging:**
*   The bridge MUST support the locking of native ETH and ERC-20 tokens on Ethereum to mint a corresponding wrapped representation on Cowboy (wETH, wERC-20).
*   Conversely, the bridge MUST support the burning of wrapped assets on Cowboy to unlock the corresponding native assets on Ethereum.
*   Bridge operations SHALL be secured by a committee of validators running light clients of the counterparty chain, with security bonds slashable on-chain for malicious behavior.

**Generic Message Passing:**
*   The bridge protocol MUST allow a transaction on one chain to trigger a corresponding message call to a designated recipient actor/contract on the other.
*   The payload of a cross-chain message MUST be included in the event logs of the source chain’s bridge contract, which the destination chain’s bridge validators can verify.

### 16.3. Event Subscription (Ethereum to Cowboy)
*   Cowboy actors MAY subscribe to event logs emitted by specific contracts on the Ethereum blockchain.
*   A system actor on Cowboy, `0x06 EventListener`, SHALL manage these subscriptions. This actor relies on the bridge validator set to act as a decentralized oracle, monitoring the Ethereum chain for specified events.
*   When a subscribed event is confirmed (i.e., finalized on Ethereum), the EventListener actor MUST enqueue a message to the subscribing Cowboy actor, delivering the event’s topic and data as the message payload.
*   The cost of this subscription service SHALL be paid by the actor in CBY, covering the gas fees incurred by the oracle validators on Ethereum.

### 16.4. Policy and Security
*   All interoperability functions available to an actor, such as `bridge_asset` or `subscribe_event`, MUST be governed by the Entitlements system (§15).
*   An actor’s deployment manifest MUST declare the specific Ethereum contracts it is permitted to interact with and the types of assets it is allowed to bridge, enforcing the principle of least privilege.

**End of specification.**