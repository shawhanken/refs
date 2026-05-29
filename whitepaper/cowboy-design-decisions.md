# Cowboy: Design Decisions Overview

|               |                           |
| ------------- | ------------------------- |
| **Status**    | Draft for internal review |
| **Type**      | Standards Track           |
| **Category**  | Core                      |
| **Author(s)** | Cowboy Foundation         |
| **Created**   | 2025‑09‑17                |
| **Updated**   | 2026‑01‑18                |
| **License**   | CC0‑1.0                   |

> **Note:** This document explains the "why" behind Cowboy's architecture. For complete technical specifications, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Abstract

We are in the Age of the Agent. Advancements in LLMs have unleashed new modalities for software to act autonomously, but these intelligent systems remain economically handcuffed, trapped behind APIs and corporate accounts. Crypto provides the missing element: permissionless, programmable economic agency. Cowboy is a general-purpose Layer-1 blockchain designed to bridge this gap, enabling AI agents to become native citizens of a digital economy.

Cowboy combines a **Python-based actor-model execution environment** with a **proof‑of‑stake consensus** and a **market for verifiable off‑chain computation**. Smart contracts on Cowboy are **actors**: Python programs with private state, a mailbox for messages, and chain‑native timers for autonomous scheduling. For heavy tasks — LLM inference, web requests, MCP tool calls, or containerized batch jobs — Cowboy integrates a decentralized network of **Runners** who execute jobs and attest to results under selectable trust models: N-of-M consensus, TEEs, and (in V2) ZK-proofs. Jobs MAY mount encrypted volumes through **Steamtrain**, the protocol's client-side-encrypted distributed storage layer.

To ensure fair and predictable resource pricing, Cowboy introduces a **dual-metered gas model**, separating pricing for computation (**Cycles**) and data (**Cells**) into independent, EIP-1559-style fee markets. Security is provided by **Simplex BFT** consensus with **proof‑of‑stake**, fast finality, and mandatory proposer rotation. By bringing the world's most dominant AI programming language, Python, directly on-chain, Cowboy provides the critical infrastructure for the next generation of autonomous agents.

## Introduction

### The Problem: A Chasm Between Intelligence and Agency

Most programmable chains evolved from a synchronous, function-call model, coupling storage, compute, and timing into a single transaction. This paradigm is ill-suited for the asynchrony and complexity of modern autonomous systems. Further, it forces development into nascent ecosystems like Solidity or Rust, alienating the vast majority of AI and enterprise developers who build in Python. Even for teams who bridge this gap, the result is operational chaos: a Frankenstein's monster of cloud servers, cron jobs, oracles, and key management services, held together by brittle off-chain glue.

Critically, these architectures fail to build trust. When an agent makes a decision—rebalancing a portfolio, executing a trade—users reasonably want to know _why_. What data did it see? How did it decide? Today's approach offers no verifiable link between inputs, execution, and outputs. Without this foundation of trust, autonomous agents remain toys, not tools for a robust economy.

### The Solution: Cowboy

Cowboy imports the actor model into a blockchain to provide a native, unified platform for autonomous agents. Every application is a set of actors; each actor is a Python program with deterministic execution, a persistent key/value store, and a mailbox. The chain delivers messages and timers, enforces resource limits, and commits state transitions in blocks. For work that cannot or should not run on-chain, Cowboy exposes a native market where **Runners** execute jobs off-chain and post verifiable results.

This document explains the architectural decisions and trade-offs that shape Cowboy's design. For complete technical specifications, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Key Innovations in Cowboy

General‑purpose chains struggle with data‑hungry, latency‑sensitive apps. Cowboy makes **actors** and **verifiable off‑chain compute** native through four key innovations:

- **Deterministic Python Actors:** A sandboxed Python VM with mailbox messaging, reentrancy (depth‑capped), and first-class support for the world's most popular programming language.
- **Native Timers & Scheduler:** A protocol-level mechanism for autonomous, scheduled execution with dynamic, context-aware gas bidding, eliminating the need for external keeper networks.
- **Verifiable Off-Chain Compute:** An open marketplace for off-chain jobs — LLM inference, HTTP fetches, MCP tool calls, custom compute, and one-shot container batch jobs — with selectable trust models, including N-of-M consensus, TEE attestations, and (in V2) ZK-proofs. Jobs may mount encrypted volumes via **Steamtrain**, the protocol's distributed storage layer; container images run against an on-chain allowlist for supply-chain integrity.
- **Dual-Metered Gas:** Independent pricing and EIP-1559-style fee markets for compute (**Cycles**) and data/storage (**Cells**) to ensure fair and predictable costs.

## Why Python?

Python is the language of AI and the glue of modern software. It is where builders already live, with a massive developer base and an unmatched ecosystem of tools and libraries. Cowboy turns that familiarity into production power: write a simple Python script and deploy an accountable, always‑on actor, while the protocol enforces determinism and safety. The result is a shorter path from idea to launch and a much wider funnel of teams who can build.

The choice of Python reflects a pragmatic trade-off: we prioritize developer accessibility and ecosystem richness over the theoretical performance advantages of lower-level languages. The vast majority of AI tooling, data science libraries, and enterprise software is built in Python. By bringing Python on-chain, Cowboy dramatically lowers the barrier to entry for autonomous agent development.

## The Actor Model

Cowboy's core execution model is based on the actor model, a paradigm that naturally fits autonomous, asynchronous systems. This section explains why actors are the right abstraction and how Cowboy adapts them for blockchain execution.

### Why Actors?

The actor model provides several key advantages for autonomous agents:

1. **Natural Asynchrony:** Actors communicate via asynchronous messages, matching the real-world behavior of autonomous systems that interact with external services, wait for responses, and operate on independent schedules.

2. **Encapsulation:** Each actor has private state that can only be modified through message handlers. This provides strong isolation and prevents many classes of bugs common in shared-state systems.

3. **Composability:** Complex systems emerge from simple actors sending messages to each other. This modularity makes it easier to reason about, test, and audit autonomous systems.

4. **Autonomy:** Actors can schedule their own execution via timers, enabling true autonomy without external keeper networks.

### Single-Block Atomicity: A Fundamental Design Choice

Cowboy provides **atomicity only within a single block**. When an actor's message handler executes, all state reads, writes, and outbound messages within that handler are atomic—they either all commit or all revert. However, **there is no cross-block atomicity**. Once a handler completes and the block is finalized, subsequent handlers (triggered by replies, timers, or new messages) execute in the context of potentially different world state.

### Why Cross-Block Transactions Are Not Provided

Consider an actor that reads state, calls a Runner, and wants to continue execution when the result arrives:

```python
# CONCEPTUAL - NOT HOW COWBOY WORKS
async def handle_trade(self, msg):
    price = self.storage.get("price")       # Block N: reads $100
    if price < 150:
        analysis = await runner.llm(...)     # Suspends... Runner executes...
        # Block N+5: Resumes here
        # But price may now be $200
        # The branch (price < 150) is no longer valid
        self.execute_buy(price)              # Dangerous: stale assumptions
```

This pattern creates fundamental problems:

1. **Stale State:** Values read before the yield may have changed.
2. **Invalid Control Flow:** Branches taken based on pre-yield state may no longer be appropriate.
3. **Composability Explosion:** Nested yields and actor-to-actor calls create a tree of interleavings where each path depends on potentially invalidated assumptions.
4. **Adversarial Griefing:** Attackers can deliberately mutate state between yield points to exploit stale assumptions.

Providing cross-block atomicity would require either global locks (destroying parallelism and creating deadlock vectors) or speculative execution with rollbacks (creating griefing opportunities and unpredictable costs). Cowboy explicitly rejects these approaches.

### The Message-Passing Continuation Model

Instead of implicit continuations, Cowboy uses **explicit message passing** for all asynchronous operations. When an actor needs to perform an off-chain job, it sends a message to the Runner system actor and receives the result as a separate message in a later block:

```python
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

### Design Principles

This model embodies several important principles:

**1. No Hidden Control Flow**

Every state transition is triggered by an explicit message. There are no implicit callbacks or suspended coroutines. Developers can trace execution by following messages.

**2. Runner Is Just Another Actor**

The Runner system is not special syntax—it's a system actor that receives job requests and sends result messages. The same message-passing pattern applies to actor-to-actor communication, timer callbacks, and Runner results.

```
User TX → Actor A → [message] → Runner System Actor → [off-chain execution]
                                        ↓
              Actor A ← [result message] ← Runner System Actor
```

**3. Explicit Context Capture**

Any state needed in the continuation must be explicitly included in the `context` field. This forces developers to think about what data crosses the yield boundary and prevents accidental closure over stale references.

**4. Re-Validation is Mandatory**

The programming model makes it clear that when `handle_analysis_result` executes, it's a new transaction in a new block. Developers must re-read and validate any state assumptions.

### Comparison with Other Models

| Model                        | Atomicity        | Developer Burden | Griefing Resistance            |
| ---------------------------- | ---------------- | ---------------- | ------------------------------ |
| Ethereum (sync calls)        | Single TX        | Low              | High                           |
| Cross-block locks            | Multi-block      | Low              | Low (deadlocks, lock griefing) |
| Optimistic + rollback        | Multi-block      | Medium           | Low (rollback spam)            |
| **Cowboy (message passing)** | **Single block** | **Medium**       | **High**                       |

Cowboy's approach trades some developer convenience for predictable execution semantics and resistance to adversarial manipulation.

## Native Timers and Scheduling

To enable true autonomy, Cowboy provides a protocol-native timer and scheduling mechanism, eliminating the need for external keeper networks. Actors can schedule messages to be sent to themselves or other actors at a future block height or on a recurring interval. The scheduler is designed to be scalable, economically rational, and fair.

### Why Protocol-Level Timers?

External keeper networks (like Ethereum's Gelato or Chainlink Automation) introduce several problems:

1. **Centralization Risk:** Keepers are typically operated by a small number of entities, creating single points of failure.
2. **Cost Inefficiency:** Each keeper network requires separate infrastructure, payment mechanisms, and trust assumptions.
3. **Coordination Overhead:** Actors must integrate with external services, manage subscriptions, and handle keeper failures.
4. **MEV (Maximal Extractable Value) Exposure:** Keepers can observe scheduled transactions and potentially front-run them.

By making timers native to the protocol, Cowboy eliminates these issues while providing better guarantees and lower costs.

### Scalable Design: Height-Indexed Storage

The scheduler stores timers indexed by their target block `height`, with the same-height bucket ordered FIFO by insertion. This keeps the per-block work proportional to the number of timers actually firing this block, not to the total active population, and avoids the operational complexity of a priority queue or tiered calendar.

A separate `LANE_TIMER_CYCLES` budget (20% of the block) is dedicated to timer execution, and a parallel `TIMER_GC_CYCLES` budget handles TTL-expiry cleanup so a sweep storm cannot starve live execution. A per-actor cap (`max_timers_per_actor = 1,024`) bounds individual exposure.

### Economic Rationality: The Per-Fire Fee Payer Model

In the implemented v1 scheduler, each timer records `fee_payer`, `gas_limit_per_fire`, and `expires_at`. At the end of each block the protocol pre-charges `max_cost = gas_limit_per_fire × cycle_basefee + max_cells × cell_basefee` from the `fee_payer`, executes the handler, refunds unused gas, and removes the timer. Timers whose `fee_payer` cannot cover `max_cost`, or whose `expires_at` is reached, self-destruct without firing.

A future **EIP-1559 hybrid** target design (activated via Tier-3 governance) layers a timer-lane basefee and a priority tip on top of this, plus a per-actor fairness weight `W(actor) ∈ [1, 2]` over a 1,000-block rolling window. The fairness weight gives a small inclusion boost to actors whose effective fire rate is below the network median, ensuring eventual execution under sustained bidding congestion without requiring exponential-decay state to be maintained off-block.

This design enables sophisticated scheduling strategies: an actor (or a Gas Bidding Agent acting on its behalf) can adjust `max_fee_per_cycle` and `max_priority_fee_per_cycle` per timer based on urgency, network congestion, and balance.

### Fairness and Liveness

Under the v1 mechanism, timers whose `fee_payer` cannot cover `max_cost` at fire time self-destruct rather than block the lane; well-funded timers always fire. Under the future EIP-1559 hybrid, the per-actor fairness weight described above is the explicit anti-starvation primitive — actors at or below the network-median fire rate get the maximum boost, actors at 2× median or above get none.

### DoS Prevention Philosophy

The timer system is a potential vector for denial-of-service attacks. An adversary could attempt to schedule millions of timers at a single block height, overwhelming execution capacity, or fill the timer queue with spam to crowd out legitimate users. Cowboy employs multiple layers of defense:

- **Per-Actor Timer Limits:** Each actor is limited to a maximum of **1,024 active timers** at any time.
- **Progressive Deposit Model:** Creating a timer requires a deposit that scales with the actor's total active timer count, making large-scale timer spam prohibitively capital-intensive.
- **Same-Block Exponential Pricing:** An exponential surcharge applies when an actor schedules multiple timers for the same block height, preventing "timer bomb" attacks.
- **Timer Queue Basefee:** Similar to EIP-1559, a timer basefee adjusts based on global timer queue pressure, naturally throttling demand when the queue is congested.
- **Per-Block Execution Budget:** Each block reserves a dedicated portion of its compute budget for timer execution, ensuring timer storms cannot completely crowd out regular transactions.

For complete technical details on these mechanisms, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Verifiable Off-Chain Compute

Many applications need access to web data, ML inference, or heavy transforms. Any actor can post a job with a price and latency target. **Runners**—off‑chain workers who stake CBY (the native protocol token)—pick up jobs, execute them, and post results.

This market is **verifiable**: the chain accepts results under various trust models chosen by the developer. Runners who lie or miss deadlines risk being challenged and **slashed**.

### Why Off-Chain Compute?

Not all computation belongs on-chain. LLM inference, web scraping, and complex data transformations are:

1. **Too Expensive:** Running LLM inference on-chain would cost orders of magnitude more than off-chain execution.
2. **Too Slow:** On-chain execution would add unacceptable latency to time-sensitive operations.
3. **Non-Deterministic:** Many real-world tasks (web APIs, LLM outputs) produce different results across runs, making on-chain execution impossible.

Cowboy's Runner marketplace provides a native, verifiable way to execute these tasks off-chain while maintaining trust guarantees.

### Trust Models

Cowboy provides multiple trust models, allowing developers to choose the right balance of security and cost:

| Mode                    | Level of Trust                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------ |
| **N-of-M Quorum**       | Runners execute results; the runtime accepts the consensus result from a committee.              |
| **N-of-M with Dispute** | Runners stake a bond; disputers may prove an incorrect result within a fixed window.             |
| **TEE Attestation**     | An N-of-M committee or single runner executes the result within a Trusted Execution Environment. |
| **ZK-Proof (v2)**       | Runners provide zk-SNARKs with results for cryptographic verification.                           |

This tiered approach allows actors to select the appropriate trust model for their use case: low-stakes tasks can use cheaper N-of-M consensus, while high-value operations can require TEE attestation or ZK proofs.

### LLM Verification Challenges

LLM outputs present a unique verification challenge: unlike deterministic computation, the same prompt can produce semantically equivalent but byte-different outputs. For example:

```
Prompt: "What is the capital of France?"
Runner 1: "The capital of France is Paris."
Runner 2: "Paris is the capital of France."
Runner 3: "France's capital city is Paris."
```

All three outputs are correct, but none match byte-for-byte. Traditional N-of-M quorum fails. Even with identical model weights, temperature=0, and fixed seeds, floating-point variations across hardware can produce different token sequences.

Cowboy addresses this through multiple verification modes:

- **Structured Match:** For tasks with well-defined output fields, verifier functions compare structured data rather than raw text.
- **Semantic Similarity:** For subjective tasks, embedding-based similarity checks ensure semantic equivalence.
- **Economic Bonds:** For truly subjective outputs, runners post bonds and the market judges quality over time.

For complete technical details on verification modes and mechanisms, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Dual-Metered Gas

Ethereum introduced **gas** as a single scalar. Cowboy splits pricing into two independent meters:

- **Cycles** measure compute: Python operations and host calls (e.g., send, set‑timer, blob‑commit) each have a fixed cost. Cycles resemble **Erlang reductions**: a budget of discrete steps that bounds how long a handler runs.
- **Cells** measure bytes: calldata, return data, blobs, and storage all consume cells.

Each block adjusts two basefees (one per meter) using the familiar EIP‑1559 feedback loop. Users specify max prices and optional tips for each meter. Basefees are **burned**, while tips go to validators. This dual model makes fees more predictable and fair.

### Why Separate Meters?

Separating compute and data pricing provides several benefits:

1. **Fair Pricing:** A transaction that processes large amounts of data but does little computation pays for data, not computation. Conversely, a compute-intensive transaction pays for cycles, not data.

2. **Predictable Costs:** Developers can reason about costs independently: "This operation will cost X cycles and Y cells" rather than trying to understand how a single gas scalar maps to both dimensions.

3. **Better Resource Management:** The protocol can adjust pricing for compute and storage independently based on network conditions. If storage is scarce but compute is abundant, cell basefees rise while cycle basefees fall.

4. **EIP-1559 Benefits:** Each meter gets its own EIP-1559-style fee market, providing the same predictability and fee burning benefits that Ethereum users enjoy, but applied to both dimensions.

## Consensus Philosophy

Cowboy uses **Simplex BFT** consensus, a streamlined Byzantine Fault Tolerant protocol chosen for three key properties:

### Why Simplex?

1. **Simplicity:** Simplex achieves consensus with optimal latency while maintaining a simple design and provable liveness. Fewer moving parts means fewer bugs and easier auditing, which is critical for a system managing autonomous agents and financial assets.

2. **Mandatory Proposer Rotation:** Unlike stable-leader protocols (like PBFT) where one validator might propose many consecutive blocks, Simplex rotates proposers every block via a Verifiable Random Function (VRF). This is a deliberate MEV mitigation strategy—no single proposer observes transaction flow across multiple blocks, fundamentally limiting cross-block MEV extraction.

3. **Fast Finality:** With ~1 second blocks and ~2 second finality, Cowboy enables autonomous agents to act on confirmed state quickly. This is critical for time-sensitive operations like trading, arbitrage, and cross-chain interactions.

### MEV Resistance Through Design

Cowboy takes a multi-layered approach to MEV mitigation:

- **VRF-Based Transaction Ordering:** Within each block, transactions are ordered deterministically using VRF. Proposers cannot strategically place their own transactions.
- **Dedicated Lanes:** Block space is partitioned into reserved lanes for system operations, timers, and runner results. Attackers cannot spam the mempool to delay victim transactions.
- **No Encrypted Mempool:** Given the ~2s finality and VRF ordering, the observation window for front-running is already minimal. The marginal benefit of encryption doesn't justify the latency cost.

For complete consensus specifications, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Economic Model

Cowboy's economic design aligns incentives across validators, runners, and actors:

### Deflationary Pressure

All basefees (for both Cycles and Cells) are **burned**, creating deflationary pressure that scales with network usage. This ensures that heavy usage benefits all token holders, not just block producers.

### Validator Rewards

- **Block Inflation:** Validators receive rewards from a declining inflation schedule (5% Year 1-2, decreasing to 1.5% terminal rate).
- **Tips:** Proposers receive transaction tips, incentivizing efficient block production.
- **Conservative Slashing:** Most offenses result in jailing (temporary removal) rather than stake destruction. This encourages validator participation while still removing bad actors.

### Runner Marketplace

Off-chain compute is priced via a **free market**:

- Runners set their own rates via on-chain rate cards
- Jobs are matched to runners based on price, capabilities, and entitlements
- Economic bonds and reputation systems align incentives for honest execution

### State Rent

Persistent storage incurs **ongoing rent**, preventing state bloat and encouraging efficient data lifecycle management. Actors who don't pay rent enter a grace period, then have storage evicted (but can restore it if data is preserved).

For detailed parameters and mechanisms, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Entitlements: Least-Privilege by Default

Cowboy implements a declarative permissions system called **Entitlements** that governs actor and runner capabilities. This system is fundamental to Cowboy's security model.

Entitlements enforce least-privilege by default:

- **Actors declare requirements:** What permissions they need (HTTP domains, TEE access, storage quotas)
- **Runners advertise capabilities:** What they can provide (supported models, geographic regions, TEE hardware)
- **Scheduler enforces matching:** Jobs only run on runners where `requires ⊆ provides`
- **Syscalls are gated:** Operations fail if the actor lacks the corresponding entitlement

This creates an auditable, on-chain permission manifest for every actor. Users can inspect exactly what an actor can do before interacting with it.

For the complete entitlements specification, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Why a Sovereign L1

A natural question arises: why build Cowboy as a sovereign Layer-1 rather than as an Ethereum Layer-2 (rollup), which would inherit Ethereum's security and liquidity?

### L2 Constraints

Ethereum L2s come in two primary flavors, neither of which fits Cowboy's requirements:

**Optimistic Rollups:**

- 7-day withdrawal delay for fraud proof windows
- Agents needing fast liquidity access would be severely constrained
- Sequencer centralization creates MEV and censorship risks

**ZK Rollups:**

- Require execution to be provable in zero-knowledge circuits
- Python is not circuit-friendly; the PVM would need complete reimplementation
- Proving costs for complex actor logic would be prohibitive
- Current ZK-EVM projects took years and billions in funding for EVM alone

Both approaches inherit EVM execution constraints or require building within them, forcing Cowboy to either abandon Python or build an entirely separate proving system.

### Execution Model Incompatibilities

Beyond the VM and proving constraints, Cowboy requires execution primitives that don't exist in Ethereum's model:

**Scheduled Future Execution**

Actors need to schedule work at specific future block heights. The EVM has no native concept of "execute this code at block N"—it only processes transactions submitted to the mempool. On Ethereum, scheduled execution requires external keeper networks (Gelato, Chainlink Automation) that add cost, latency, trust assumptions, and failure modes. Cowboy's native timers are protocol-level primitives that the chain itself executes.

**Actor-Aware Block Building**

Ethereum block builders optimize for MEV extraction and tip maximization. Cowboy's block proposers must understand a fundamentally different priority: *some actors have timers that are overdue and must run soon*. The protocol tracks which timers have been deferred, applies anti-starvation boosts, and reserves dedicated block space for timer execution. This actor-aware scheduling cannot be retrofitted onto an EVM-based L2.

**Guaranteed Execution Lanes**

Cowboy partitions block space into dedicated lanes (system, timer, runner, user) with reserved capacity. A surge in user transactions cannot crowd out timer executions or runner result submissions. Ethereum's single-lane block model provides no such guarantees—during congestion, any transaction type competes equally for inclusion.

**Storage Lifecycle Management**

Ethereum's "pay once, store forever" model doesn't fit an actor-based system where agents may become dormant. Cowboy's state rent model—with grace periods, eviction, and restoration—requires protocol-level enforcement that an L2 inheriting EVM storage semantics cannot provide.

### Why L1 Enables Cowboy's Design

| Capability             | L1 (Sovereign)                                    | L2 (Rollup)                                     |
| ---------------------- | ------------------------------------------------- | ----------------------------------------------- |
| **Custom VM**          | Native PVM with Python                            | Constrained to EVM or custom ZK circuit         |
| **Scheduled execution**| Protocol-native timers with guaranteed inclusion  | External keepers, no execution guarantees       |
| **Block building**     | Actor-aware with anti-starvation, dedicated lanes | MEV-optimized, single priority dimension        |
| **Block time**         | Full control (1s target)                          | Bound by L1 finality for settlement             |
| **Consensus**          | Simplex with VRF ordering, lane isolation         | Inherit sequencer model or Ethereum constraints |
| **Runner integration** | Deep protocol integration with verification modes | Separate oracle infrastructure per capability   |
| **Storage model**      | State rent with eviction and restoration          | EVM "pay once, store forever" semantics         |
| **Upgrade path**       | Sovereign governance                              | Depends on rollup framework and L1 upgrades     |

### The Trade-off

Sovereignty comes with costs:

- **Bridge risk:** Cross-chain asset transfers require trust assumptions beyond Ethereum's security
- **Liquidity fragmentation:** Assets on Cowboy are not natively composable with Ethereum DeFi
- **Validator bootstrapping:** Must attract sufficient stake for economic security

Cowboy accepts these trade-offs because the alternative—forcing autonomous Python agents into EVM constraints or waiting years for ZK-Python infrastructure—would compromise the core value proposition. The bridge design mitigates cross-chain risk through validator committees, rate limits, and future optimistic fallback paths.

## Ethereum Interoperability

Interoperability is a foundational design goal. The same `secp256k1` key can control both a Cowboy account and an EVM address, letting agents hold ETH and ERC-20s, bridge assets, and sign EIP-1559 transactions under tight policy guards enforced by entitlements. The protocol does **not** ship its own bridge validator set — instead, governance selects third-party bridge infrastructure to carry funds and calldata, and exposes the integration to actors through the `bridge.asset` and `bridge.subscribe_event` entitlements. Cowboy actors can subscribe to Ethereum events to trigger on-chain workflows once an `EventListener` system actor (deferred, address to be assigned) is in place.

This interoperability design recognizes that Cowboy and Ethereum serve complementary roles: Ethereum provides liquidity and security for high-value assets, while Cowboy provides the execution environment for autonomous agents. The chosen bridge enables agents to leverage both ecosystems without forcing the protocol to maintain validator sets it does not control.

For complete technical specifications on the bridge and interoperability mechanisms, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Security Philosophy

Cowboy's security model prioritizes simplicity and auditability:

- **Readable Code:** Python's existing analysis and auditing tools, combined with Cowboy's native guards and decorators, place it at a natural advantage when it comes to preventing on-chain attacks.
- **Explicit Semantics:** The message-passing model makes execution flow explicit and traceable.
- **Economic Security:** Staking, slashing, and fee mechanisms align incentives and penalize malicious behavior.
- **Least Privilege:** The Entitlements system enforces least-privilege access by default.

For complete security specifications and considerations, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md).

## Applications

Cowboy's design choices—Python actors, native timers, verifiable off-chain compute—combine to enable a new class of autonomous applications:

- **AI Agents:** Actors that call LLMs for planning or retrieval, with verifiable transcripts and bounded costs. A trading agent could scrape congressional stock disclosures, use an LLM to parse the trades, and autonomously execute a copy-trade.
- **DeFi Automation:** An agent that monitors an ETH/BTC pool and automatically rebalances based on price deviations from a 7-day moving average, all without external keepers.
- **Games:** Per-tick logic with VRF randomness; blob assets stored off-chain but committed on-chain.
- **Oracles:** HTTP committees fetch data from allow‑listed domains with commit‑reveal and disputes.

These applications were previously impractical or impossible on existing platforms. Cowboy provides the missing infrastructure.

---

_For complete technical specifications, parameters, and implementation details, see the [Technical Whitepaper](./cowboy-technical-whitepaper.md)._
