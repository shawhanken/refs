---
title: "CIP-3: Dual-Metered Fee Model"
description: Authoritative specification for Cycles, Cells, and fee markets
icon: gauge-high
---

<Note>
  **Status:** Draft for Internal Review  
  **Type:** Standards Track  
  **Category:** Core  
  **Created:** 2025-10-03
</Note>

<Tip>
  This specification defines Cowboy’s dual-metered gas (Cycles/Cells) and independent EIP‑1559 fee markets. Content below mirrors the CIP text verbatim.
</Tip>

<Warning>
  **修正案（2026-04-15）**: 以下参数以代码为准：
  - `BLOCK_CYCLES_TARGET = 20,000,000`（CIP 原文 10,000,000）
  - `BLOCK_CELLS_TARGET = 4,000,000`（CIP 原文 500,000）
  - **Basefee 更新公式**: 几何更新 `Δ = basefee × |used−target| / target / ALPHA`，clamp 到 `basefee / DENOM`；`ALPHA = 96`（非 8）、`DENOM = 96`、`MIN_BASEFEE = 10,000`（非 1）、`MAX_BASEFEE = 10²⁴`
  - **Transfer 成本**: `5,000 cycles / 500 cells`（CIP 原文 21,000 cycles / 0 cells）

  详见 [`analysis/2026-04-15_documentation_amendments.md §一`](../analysis/2026-04-15_documentation_amendments.md)。
</Warning>

### **Cowboy Improvement Proposal (CIP-3): Dual-Metered Gas Calculation and Dynamic Fee Market**

**Status:** Draft for internal review

**Type:** Standards Track

**Category:** Core

### **Abstract**

Existing programmable blockchains face two major challenges in resource pricing: **inequitable fee models** and **non-deterministic execution metering**. A single gas unit cannot distinguish between computation and storage costs, leading to inefficient resource pricing and unpredictable fees. Furthermore, to securely support high-level languages like Python on-chain, the core problem of "how to deterministically meter its execution" must be solved; otherwise, the network cannot achieve consensus.

This CIP directly confronts these challenges by providing a definitive solution for Cowboy's dual-metered gas system. It explicitly divides resource consumption into two dimensions:

* **Cycles:** By instrumenting the virtual machine at the bytecode level, every **computational** step is precisely metered.  
* **Cells:** By accounting at I/O boundaries, every byte of **data** payload and state storage is precisely metered.

This proposal provides an authoritative, implementable engineering specification for these two mechanisms and their corresponding dynamic fee markets, thereby establishing a fair, predictable, and deterministic economic foundation for the Cowboy network.

### **1. Motivation**

The Cowboy Whitepaper introduces a novel dual-fee model to create more predictable costs and fairly price distinct resources: computation and data. However, for a decentralized network of clients to maintain consensus, the *exact* method of calculating this usage must be rigorously defined.

This CIP is necessary to:

* **Ensure Determinism:** Provide a canonical reference for how Python VM operations translate into Cycles and Cells, preventing consensus failures due to differing client implementations.  
* **Create a Fair Resource Market:** Formally separate the costs of on-chain state transitions from the costs of off-chain, real-world computation, allowing a more efficient market to form for each.  
* **Prevent DoS Attacks:** Standardize the resource limits (cycles_limit, cells_limit) and their enforcement within the VM, providing a robust defense against computational and state-bloat attacks.  
* **Clarify Runner Economics:** Define how Runners, operating in diverse environments like containers and TEEs, should conceptualize their costs, fostering a healthy and competitive off-chain marketplace.

### **2. Specification**

#### **2.1 Core Definitions**

* **Cycle (unit: c)**: A unit of abstract computational work. Every Python bytecode operation and every host function call has a fixed Cycle cost. This is analogous to an instruction step count.  
* **Cell (unit: b)**: A unit of data or storage work, where **1 Cell is equivalent to 1 byte**. Cells are consumed by transaction payloads, return data, state storage, and temporary scratch space.

#### **2.2 On-Chain Metering: The Actor VM**

The Actor's Python VM MUST implement both Cycle and Cell metering. The following describes the reference implementation strategy within a Python VM interpreter.

**2.2.1 Cycle Calculation (Instruction-based Metering)**

Cycles are metered by instrumenting the core bytecode execution loop of the Python VM.

* **Mechanism:** Before the execution of each Python bytecode instruction, a corresponding cost is deducted from the call's remaining cycles_limit. If the cost exceeds the remaining limit, execution MUST halt immediately with an "Out of Cycles" error.  
* **Cost Table:** A static, consensus-critical cost table (`HashMap<Instruction, u64>`) maps every Python bytecode instruction to a fixed Cycle cost. This table forms part of the protocol constants.  
  **Partial Cost Table (Cycles):**

| Operation Type | Cycles Cost |
| :---- | ----: |
| Python Arithmetic Ops (+, -, *, /, %) | 1 |
| Python Function Call | 10 |
| Dictionary Get/Set | 3 |
| List Append/Access | 2 |
| String Operation (per character) | 1 |
| Mailbox Send (per message, payload extra) | 80 |
| Set Timer (+ cells) | 200 |
| Cancel Timer | 200 |
| Commit Blob (per KiB) | 40 |
| Storage KV Read (per call) | 10 |
| Storage KV Write (per call, + cells) | 200 |
| Cryptography (secp256k1 signature verification) | 10,000 |
| Cryptography (BLS signature verification) | 8,000 |
| Hashing (keccak256, per 32 bytes) | 6 |

**2.2.2 Cell Calculation (Event-based Metering)**

Unlike Cycles, Cells are not consumed on every instruction. They are consumed at specific events where data is read, written, or stored.

* **Mechanism:** Cell costs are charged by explicit calls to meter.consume_cells(byte_count) within the Python VM's host functions and at the transaction processing boundary.  
* **Metering Points:**  
  1. **Intrinsic Calldata:** Before Python VM execution begins, the size of the transaction's payload is charged as Cells.  
  2. **Host Function Calls:** Host functions that interact with storage or data MUST charge for it.  
     * storage_set(key, value): charges key.len() + value.len() Cells.  
     * put_blob(data): charges data.len() Cells.  
  3. **/tmp Scratch Space:** I/O to the per-invocation /tmp space is metered. A call to file.write(data) MUST immediately charge data.len() Cells.  
  4. **Return Data:** After an Actor's handler successfully returns, the byte size of its return value is charged as Cells.

**2.2.3 Execution Lanes**

The block cycle budget is partitioned into reserved lanes to prevent any single transaction type from monopolizing block space (see Whitepaper §17.9):

| Lane | Budget | Share | Fee Multiplier |
|------|--------|-------|----------------|
| User | 5,000,000 cycles | 50% | 1.0× |
| Runner | 2,500,000 cycles | 25% | 1.0× |
| Timer | 2,000,000 cycles | 20% | 1.0× |
| System | 500,000 cycles | 5% | 1.0× |

The **Fee Multiplier** column scales the global cycle/cell basefee for transactions submitted in that lane: `lane_basefee = global_basefee × lane_fee_multiplier`. All lanes default to `1.0×` at genesis (no subsidy, no surcharge). The four multipliers are governance-tunable via CIP-12 **Tier 0** and stored at `0x09` under keys `system:lane_fee_multiplier:{system|timer|runner|user}`. Changing a multiplier does not change lane capacity; it only re-weights the per-lane fee curve relative to the global EIP-1559 basefee adjustment.

**2.2.4 Advanced Metering Challenges and Solutions**

Statically pricing high-level bytecode instructions is insufficient. To ensure full determinism, the VM must handle the dynamic nature of the Python language. The following specifications are mandatory:

1. **Dynamic Typing and Operation Surcharges:**  
   * **Problem:** The cost of a bytecode like BINARY_ADD varies depending on the operand types (integers, strings, lists).  
   * **Specification:** The protocol adopts a **base cost + dynamic surcharge** model. The static cost of a bytecode is its minimum base Cycle cost for execution. The VM must inspect the type and size of the operands at runtime and charge a corresponding surcharge. For example, for string or list concatenation, the surcharge must be proportional to their length.  
2. **Cost of Built-in Functions:**  
   * **Problem:** The cost of built-in functions (e.g., len(), sum(), max()) is directly related to their arguments.  
   * **Specification:** All permitted built-in functions must be treated as special host calls and have a well-defined, consensus-critical cost calculation function. For len(), the cost is fixed and low; for sum() or max(), the cost must be proportional to the number of elements iterated over.  
3. **C API Extensions:**  
   * **Problem:** Arbitrary C extensions are a major source of non-determinism and security vulnerabilities.  
   * **Specification:** **The protocol strictly forbids loading and executing arbitrary C extension modules.** Any functionality requiring high-performance implementation (e.g., cryptographic primitives) must be provided by the VM as deterministic, fully metered **host functions**, not through external C libraries.  
4. **Garbage Collection:**  
   * **Problem:** Standard garbage collection (especially generational GC and cycle detection) is inherently non-deterministic regarding when it triggers and how long it runs.  
   * **Specification:** **The VM's garbage collection mechanism must be deterministic.** The protocol recommends a combination of the following strategies:  
     * **Memory Allocation:** The cost of memory allocation operations (creating new objects) is metered via Cells.  
     * **Reference Counting:** The primary memory management is done through reference counting. The costs of these reference counting operations are factored into the Cycle cost of their respective bytecode instructions.  
     * **Cycle Detection:** During the execution of a single transaction, running a non-deterministic cycle detection algorithm that could cause long pauses is **forbidden**. Memory management must ensure that all memory is deterministically reclaimed by the end of the transaction.  
5. **Floating-Point Determinism:**  
   * **Problem:** Floating-point operations can yield minute, inconsistent results across different CPU architectures, operating systems, or compilers, which is fatal for a consensus system.  
   * **Specification:** **The protocol MUST enforce that all floating-point operations are executed via a deterministic, cross-platform software implementation.** Client implementations **MUST NOT** use their host machine's native FPU (Floating-Point Unit). All transcendental functions (e.g., trigonometry, logarithms) must come from a network-wide, version-locked deterministic math library.  
6. **Exception Handling Costs:**  
   * **Problem:** The operations for throwing and catching exceptions (try...except...finally) involve internal processes whose costs are not fixed and could be exploited for cheap attacks.  
   * **Specification:** The cost of exception handling must be explicitly metered. The raise statement, entering a try block, and the jump instructions for executing except / finally blocks must each have their own fixed base Cycle cost.  
7. **Prohibition of Just-In-Time (JIT) Compilation:**  
   * **Problem:** While JIT compilers can improve performance, their compilation timing, optimization paths, and resulting machine code are highly non-deterministic.  
   * **Specification:** To guarantee absolute determinism and predictability, **the protocol strictly forbids the use of any form of Just-In-Time compilation technology within the Actor VM.** The VM must execute bytecode in a pure interpretation mode.  
8. **Module Import System and Standard Library Whitelist:**  
   * **Problem:** Python's import mechanism can load arbitrary modules, including those that depend on the filesystem, network, or system calls. This breaks determinism and security.  
   * **Specification:**  
     * **The protocol MUST maintain a strict "allowed module whitelist".** Only modules on the whitelist can be imported by Actor code.  
     * The whitelist should include: core data structure modules (e.g., collections, itertools), math modules (deterministic implementation of math), deterministic hashlib, and protocol-specific host API modules (e.g., cowboy.messaging, cowboy.storage).  
     * Attempting to import a module not on the whitelist will result in an ImportError and consume a fixed **50 cycles** as a penalty.  
     * Module import cost: **100 cycles** (first import) + actual execution cost of module initialization. Modules are cached, and repeated imports within the same transaction cost **5 cycles**.  
9. **Large Integer Precision Limit:**  
   * **Problem:** Python supports arbitrary precision integer arithmetic. While powerful, malicious code can perform computational DoS attacks by creating astronomically large numbers (e.g., 2**100000000).  
   * **Specification:**  
     * **Integer bit length MUST NOT exceed 4096 bits** (approximately 1234 decimal digits).  
     * Any operation that produces a result exceeding this limit (e.g., pow(), factorial, large multiplication) will raise an OverflowError.  
     * Large integer operation Cycles cost must be proportional to bit length: `base cost + max(bitlen(a), bitlen(b)) / 64` cycles.  
10. **String Encoding Determinism:**  
    * **Problem:** The encode() and decode() operations on strings may have different handling for certain edge Unicode characters across different Python versions or platforms (e.g., replacement characters, error modes).  
    * **Specification:**  
      * The protocol only allows **UTF-8 encoding** for byte string and string conversion.  
      * The error handling mode for str.encode() and bytes.decode() must be fixed to **errors='strict'**, which will raise a UnicodeError on invalid characters rather than silently replacing them.  
      * Cost: 10 + len(input) cycles.  
11. **Coroutine and async/await Deterministic Scheduling:**  
    * **Problem:** The whitepaper mentions allowing "cooperative yields via async/await", but the scheduling order of async code may introduce non-determinism.  
    * **Specification:**  
      * **The protocol prohibits true concurrent execution.** All async/await code must execute in a single thread in **strictly deterministic order**.  
      * await operation scheduling follows a FIFO queue. When a coroutine awaits, control passes to the next ready coroutine in the queue.  
      * Use of asyncio.gather() or other concurrency primitives that may cause non-deterministic execution order is not allowed.  
12. **Object Serialization Determinism:**  
    * **Problem:** Passing data between Actors via messages and persisting state to storage require serialization of Python objects. If serialization is non-deterministic, the same object may produce different byte streams on different nodes.  
    * **Specification:**  
      * The protocol must use Canonical CBOR (RFC 8949, §4.2 deterministic encoding) — map keys sorted, shortest integer encoding, no indefinite-length containers. CIP-6 establishes Canonical CBOR as the authoritative protocol serialization standard.  
      * Dictionary keys must be **sorted lexicographically** before serialization.  
      * Floats must be serialized using the exact bit representation according to the IEEE 754 standard.  
      * Serialization cost: 20 + total_bytes cycles (20 is the base serialization overhead).

#### **2.3 Off-Chain Fee Model: The Runner Market**

It is critical to distinguish on-chain gas from off-chain job fees. The protocol does **not** calculate gas for Runner execution. Instead, it facilitates a free market.

* **Job Fee:** The payment_per_runner specified in CIP-2 is a **market-driven price in CBY**, not a gas calculation. Runners are free to ignore jobs they deem underpriced.  
* **Runner Cost Factors and Metering:** A Runner's operational cost determines its market price. The protocol does not enforce a cost model, but a mature Runner will typically combine **a priori estimation** (to decide whether to accept a job) and **post-mortem metering** (for precise profit calculation).  
  1. **A Priori Estimation (Job Decision):**  
     * **Based on Job Metadata:** A Runner's decision relies heavily on the result_schema and task_definition from CIP-2. The developer-provided expected_execution_ms, identification of the model ID (model_id), and analysis of the input data size are key estimation inputs.  
     * **Driven by Historical Data:** Runners should maintain a database of historical jobs. For a previously executed model_id or a similar task, a Runner can query the average or P95 resource consumption (CPU time, peak memory) as a basis for the current estimation.  
     * **Benchmarking:** For common public models (e.g., specific LLMs), a Runner can perform advance benchmarks on its standardized hardware to build an internal cost model (e.g., "The cost of generating 100 tokens with Llama3-8B is approximately X").  
  2. **Post-Mortem Metering (Cost Accounting):**  
     * **Utilizing Container Runtime APIs:** A Runner's orchestration service can obtain precise resource usage data via the container runtime API.  
     * **Computation Time:** Total execution duration can be obtained by recording the start and end timestamps of the container. For more granular CPU time, container monitoring tools or direct reads from the kernel's cgroup filesystem can be used.  
     * **Memory Usage:** Container monitoring tools can provide the peak memory usage (MAX USAGE) during the container's lifecycle. This is a key metric for determining memory costs.  
     * **Data Transfer:** The orchestration service must record inbound traffic from downloading models or data from the network (e.g., IPFS) and outbound traffic from making HTTP requests.  
* This "estimate-execute-meter" feedback loop allows a Runner to dynamically balance maximizing profit and minimizing risk, enabling it to remain competitive in the decentralized computation market.  
* **The TEE Premium:** When a job request sets tee_required=true, Runners that support TEE will only accept jobs with a significant price premium. This premium accounts for:  
  1. **Hardware Cost:** The requirement for specialized server hardware (e.g., Intel SGX or AMD SEV enabled).  
  2. **Performance Overhead:** TEE execution incurs a non-trivial performance penalty due to memory encryption and enclave transitions, increasing the required compute time.  
  3. **Confidentiality as a Service:** The Runner is charging for the high-value guarantee of data confidentiality, which is a premium feature.

#### **2.4 Dual Basefee Adjustment Mechanism**

To smooth short-term fee volatility and make them predictable in the long term, Cowboy implements an independent EIP-1559-style basefee adjustment mechanism for both the Cycles and Cells tracks. At its core is a negative feedback loop designed to keep the resource usage of each block stable around a preset target.

* **Core Principle:** The protocol sets an ideal "target usage" (T_c and T_b) for Cycles and Cells at 50% of block capacity. **Block cycle capacity: 20,000,000 cycles/block. Block cell capacity: 1,000,000 cells/block. Cycle target (T_c): 10,000,000 cycles/block (50% of capacity). Cell target (T_b): 500,000 cells/block (50% of capacity).**
  * If the previous block's actual usage U was **higher** than the target T, the current block's basefee will be adjusted **upwards** to curb demand.  
  * If the previous block's actual usage U was **lower** than the target T, the current block's basefee will be adjusted **downwards** to stimulate demand.  
* **Update Rule Explained:** Each block calculates the new basefee based on the parent block's usage via the following formula:  
  ```
  basefee_{x, new} = basefee_{x, old} * (1 + (U_x - T_x) / T_x / alpha)
  ```  
  Where:  
  * x: Represents c (Cycle) or b (Cell).  
  * U_x: Total usage of resource x in the parent block.  
  * T_x: The target usage for resource x.  
  * alpha: The learning rate denominator (or "elasticity multiplier"), which controls how quickly the basefee reacts to usage changes. A larger alpha (e.g., 8 in the whitepaper) means a smoother adjustment, preventing drastic fee oscillations.  
  * The resulting change is clamped to ±12.5% to ensure the per-block fee change is bounded.  
* **Example Calculation:**  
  * Assume T_c (cycle target) is 10,000,000.  
  * Parent block's actual usage U_c was 12,000,000 (20% over target).  
  * alpha is 8.  
  * The fee delta is (12M - 10M) / 10M / 8 = 0.2 / 8 = 0.025, or +2.5%.  
  * Therefore, the new basefee will be 2.5% higher than the old one.  
* **Fee Composition and Distribution:**  
* **User Transaction:** When submitting a transaction, a user specifies a `max_fee_per_*` and a `tip_per_*` for each resource.  
  * **Fee Burn:** After a transaction is included, its basefee portion (cycles_used * basefee_cycle + cells_used * basefee_cell) **MUST be 100% burned**. This exerts a constant deflationary pressure on the native CBY token.  
  * **Proposer Tip:** The portion paid to the block producer is the tip. The effective tip paid is min(tip_per_*, max_fee_per_* - basefee_*). This provides a direct economic incentive for block producers to include transactions and creates a priority "tip market".

### **3. Rationale**

* **Separation of Concerns:** By cleanly separating on-chain gas (Cycles/Cells) from off-chain market fees, the protocol avoids trying to price real-world, variable resources like electricity and hardware. The on-chain component remains a pure, deterministic system, while the off-chain component is an efficient free market.  
* **Bytecode-Level Cycle Metering:** This is the only robust method to ensure deterministic compute accounting. It naturally handles all control flow (loops, recursion) without special cases and is difficult to game, as all work is metered.  
* **Event-Based Cell Metering:** Data costs are not continuous like computation. Metering Cells only at I/O boundaries is more efficient and accurately reflects how data impacts the system (e.g., during state writes or network propagation).  
* **TEE as a Market Feature:** Making TEE a priced, optional feature allows users to pay for confidentiality only when they need it, rather than forcing the cost onto all users of the off-chain system.  
* **Fee Market Predictability and Efficiency (EIP-1559):** The EIP-1559-style mechanism is introduced to solve the inefficiencies of traditional first-price auction fee models. By algorithmically adjusting the base fee, it provides a clear "market price" for users, which greatly simplifies fee estimation and reduces average user wait times and transaction costs. Furthermore, the burning of the base fee creates a continuous deflationary pressure on the native CBY token, directly linking its value to the network's actual usage and benefiting the long-term health of the ecosystem.

### **4. Security Considerations**

* **Metering Consensus:** The bytecode-to-cycle cost table is a highly sensitive, consensus-critical parameter. Any change requires a coordinated hard fork. All clients MUST implement the exact same table.  
* **Infinite Loops:** The cycles_limit per transaction is the primary defense against infinite loops in Actor code, preventing them from halting the chain.  
* **Data Gas-Bombing:** The cells_limit per transaction, combined with max_return_bytes defined in CIP-2, prevents Actors or Runners from overwhelming the chain with excessively large data payloads that would incur high processing and storage costs for nodes.  
* **Host Function Metering:** Every host function exposed to the VM that reads, writes, or allocates data MUST be correctly instrumented with Cell metering. A missing metering call is a potential DoS vector and a critical security vulnerability.
