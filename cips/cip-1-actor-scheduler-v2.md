---
title: "CIP-1: Actor Message Scheduler (v2)"
description: Code-aligned v2 — clarifies CIP-1 vs CIP-5 status, codifies Tx-then-Timer ordering, unifies the future GBA + auction design
---

# CIP-1 v2

> **Versioning.** This is v2 of CIP-1. v1 is the canonical document `cip-1-actor-scheduler.md` (preserved verbatim as Part I). v2 = v1 + the alignment revision (Part II).
>
> **Conflict rule:** Part II is canonical wherever it contradicts Part I.
>
> **Summary of v2 changes**
>
> - Codifies **Tx-then-Timer** block ordering as the canonical rule (matches code; v1 §3 step 4 said "Timer-then-Tx" — wrong, already noted in v1 2026-04-15 amendment).
> - **Unifies** CIP-1's GBA contracts with CIP-5 §9's exponential-bias auction. They are NOT competing designs — GBA produces the bid; auction picks winners. Closes CIP-5 §9.9 open question.
> - Pins `TIMER_PROCESSING_BUDGET_CYCLES = 8_888_890` (current code value) as the unified constant for both v1's queue cap and v9's auction budget.
> - States migration rule: when the auction is activated, FIFO timers default to `bid = 0` and rely on bias accumulation.

---

## Part I — v1 Specification (verbatim from `cip-1-actor-scheduler.md`)


<Note>
  **Status:** Draft for Internal Review  
  **Type:** Standards Track  
  **Category:** Core  
  **Created:** 2025-10-01
</Note>

<Tip>
  This specification defines the chain‑native timer scheduler with a tiered queue and GBA‑based prioritization. It mirrors the CIP text verbatim; fees/metering align with CIP‑3.
</Tip>

<Warning>
  **Implementation Status: Phase 2 / Not Yet Implemented.** The tiered Calendar Queue and GBA-based priority model described here are a future protocol design. Current timer behavior (FIFO queue, single gas tier) is implemented as specified in **CIP-5**. This document is retained for roadmap reference.
</Warning>

<Warning>
  **修正案（2026-04-15）**: 本 CIP 描述的 "Timer-then-Transactions" 顺序与当前代码实现相反；代码实际为 **Transactions-then-Timers**（`node/storage/src/speculative.rs:152-475`）。块 timer 预算 `8,888,890` cycles，单 timer 上限 `550,000` cycles。详见 [`analysis/2026-04-15_documentation_amendments.md §五`](../analysis/2026-04-15_documentation_amendments.md)。
</Warning>

### **Cowboy Improvement Proposal (CIP-1): The Autonomous Actor Scheduler**

**Status:** Draft for internal review

**Type:** Standards Track

**Category:** Core

---

### **Abstract**

This document specifies the design of the **Autonomous Actor Scheduler**, the protocol-level mechanism responsible for implementing chain-native timers. It combines two key technologies: a **tiered Calendar Queue** for scalable, O(1) event scheduling, and an **autonomous gas bidding model** for execution. When a timer is due, the protocol queries a user-defined **Gas Bidding Agent (GBA)** contract, providing it with real-time block context. The GBA's returned bid determines the timer's priority within a dedicated processing budget for that block. This design enables truly autonomous actors that can dynamically respond to network congestion and weigh the urgency of their own scheduled tasks.

---

### **1. Motivation**

The Cowboy actor model's reliance on timers requires a scheduler that is not only scalable but also intelligent. Network conditions are dynamic, and the importance of a scheduled task can change based on external events. A fixed, pre-paid gas fee for a future transaction is insufficient. This design allows actors to make real-time, economically rational decisions about the cost of their own execution, ensuring that high-priority tasks can aggressively compete for block space when it matters most.

---

### **2. The Tiered Calendar Queue Design**

The Actor Scheduler state is part of the global consensus state (`σ`) and is organized into a three-tier structure to efficiently manage timers across different time horizons.

#### **2.1 Tier 1: The Block Ring Buffer**

This tier handles imminent timers scheduled for the near future.

* **Structure:** A fixed-size array (or "ring buffer") of buckets, where each bucket corresponds to a single block height. Let's call this size `RING_BUFFER_SIZE`.  
* **Function:** When an actor schedules a timer for block `H`, the message is placed into bucket `H % RING_BUFFER_SIZE`.  
* **Performance:** Enqueue and dequeue operations are `O(1)`, as the block producer only needs to access the single bucket corresponding to the current block height.

#### **2.2 Tier 2: The Epoch Queue**

This tier manages timers scheduled for the medium-term future, beyond the scope of the Ring Buffer.

* **Structure:** An array of buckets, where each bucket corresponds to a future epoch (e.g., one hour of blocks ).  
* **Function:** A timer scheduled for a block in epoch `E` is placed into the bucket for epoch `E`. At the beginning of each new epoch, a protocol-level maintenance operation redistributes all timers from that epoch's bucket into the appropriate slots in the Block Ring Buffer. This redistribution work is an amortized cost.

#### **2.3 Tier 3: The Overflow Sorted Set**

This tier is a catch-all for very long-term timers that fall outside the Epoch Queue's range.

* **Structure:** A Merkleized Balanced Binary Search Tree, ordered by block height.  
* **Function:** Timers scheduled far in the future are inserted here. During epoch maintenance, the protocol also checks this tree for any timers that now fall within the Epoch Queue's range and migrates them accordingly.

---

### **3. Integration with the State Transition Function**

The introduction of autonomous bidding modifies the state transition function to include a contextual query step.

Let σ be the global state, B a block with transactions T_i, basefees (bf_c, bf_b), and randomness R.

1. **Header/Proposer:** Determined by Simplex consensus and the previous QC.
2. **Epoch Maintenance (if applicable):** Redistribute timers from higher-tier queues into the Block Ring Buffer.
3. **Execute Transactions:** Process the ordered transaction set T_i. Actor calls to set_timeout now MUST include the address of the GBA that will manage the timer's future execution.
4. **Deliver Timers & Build Priority Queue (End-of-Block):**
   a. Access the timer bucket for height(B).
   b. For each due timer message, the block producer performs a read-only call to the owner actor's designated Gas Bidding Agent (GBA), invoking getGasBid(context). The context object is supplied by the protocol (see §4.2).
   c. The GBA returns a bid (max_fee_per_cycle, tip_per_cycle, etc.).
   d. The producer populates a temporary priority queue with all due timers, ordered by their effective tip.
5. **Execute Prioritized Timers (End-of-Block):**
   a. The producer executes timer-triggered messages from the front of the priority queue.
   b. Execution continues until either the queue is empty or the cumulative cycles used exceed the TIMER_PROCESSING_BUDGET_CYCLES for the block.
   c. Timers created within the current block's transactions MUST NOT execute in the same block, to avoid reentrancy and contextual ambiguity.
6. **Priority Weight for the next epoch:**
   a. For each actor with due timers, compute a normalized priority score S from: effective tip (post-GBA), execution outcome (success/defer), deadline lateness, and per-block budget consumption ratio.
   b. Update per-actor weight using exponential decay: weight' = (1 − λ) · weight + λ · S, where λ is governance-tunable (e.g., 0.2).
   c. Enforce bounds and fairness: clamp to [weight_min, weight_max]; apply a starvation floor for actors whose timers were repeatedly deferred; decay weights on inactivity.
   d. Application in next epoch: (1) break ties among equal effective tips; (2) apportion TIMER_PROCESSING_BUDGET_CYCLES slices per actor to smooth congestion while preserving price signals.
   e. Persistence & timing: persist weights in σ; recompute on epoch rollover; governance MAY reset or rescale weights when parameters change.
7. **Resolve Jobs, Adjust Basefees, Mint Rewards:** These steps proceed as previously defined.

---

### **4. Autonomous Bidding and Contextual Execution**

#### **4.1 Metering and Economics**

* **Scheduling Cost:** An actor pays a small, fixed cycle cost upfront to call set_timeout and place a timer in the queue.  
* **Execution Cost:** The fee for the eventual execution is determined by the GBA's dynamic bid. This fee is deducted from the owning actor's main balance at the time of execution. If the actor's balance is insufficient to cover the bid returned by its GBA, the timer execution fails for that block and is deferred.

#### **4.2 The Gas Bidding Agent (GBA) and Context**

Every actor that schedules a timer MUST specify a GBA contract responsible for pricing its execution. This GBA must implement a standard interface.

**Standard Interface:** function getGasBid(bytes calldata context) external view returns (TxFeeParams);

The protocol supplies the context object, which contains critical data for decision-making:

* trigger_block_height (u64): The block height the timer was originally scheduled for.  
* current_block_height (u64): The current block height, allowing calculation of delay.  
* basefee_cycle (u128): The current basefee for compute cycles.  
* basefee_cell (u128): The current basefee for storage/bytes.  
* last_block_cycle_usage (u64): The total cycles used in the previous block, as an indicator of congestion.  
* owner_actor_balance (u128): The current CBY balance of the actor that owns the timer.

This allows for sophisticated GBA logic, such as a DeFi liquidation actor whose GBA checks on-chain oracles within its getGasBid function and submits an extremely high bid if market volatility is high.

---

### **5. DoS Mitigation & Congestion Handling**

The combination of a fixed budget and competitive bidding creates a robust defense against DoS attacks.

* **Bounded Execution:** The TIMER_PROCESSING_BUDGET_CYCLES provides a hard cap on the resources consumed by timers in any given block, ensuring that regular user transactions are not crowded out.  
* **Economic Prioritization:** Instead of a simple FIFO queue, the system creates an **intra-block auction** for the timer budget. Timers deemed more important by their owners (and thus given higher bids by their GBAs) will execute first. Low-priority or "spam" timers will be priced out during periods of congestion.  
* **Best-Effort Delivery:** Timers that are not executed—either due to a low bid or the budget being exhausted—are automatically carried over to the next block's bucket. This ensures eventual execution and preserves liveness, while still allowing for market-based prioritization.

---

## Part II — v2 Revision (canonical; alignment with CIP-5 and code reality)

### 0. What this revision does

CIP-1 v1 specifies a **future** scheduler (tiered Calendar Queue + Gas Bidding Agent contracts) that is not implemented. CIP-5 §1–7 is the canonical spec for **currently implemented** behavior (FIFO at end-of-block, 550,000 cycles per timer, 8,888,890 cycles per block budget). CIP-5 §9 in turn specifies a **different** future auction design (exponential bias + VCG). This three-way mismatch is resolved here.

### 1. Block ordering: Tx-then-Timer (canonical)

The 2026-04-15 amendment in CIP-1 v1 already records that code is **Tx-then-Timer**, contradicting v1 §3 step 4. v2 codifies the canonical sequence per `node/storage/src/speculative.rs:152-475`:

1. Execute all user transactions (TX phase).
2. Fire timers whose `due_height == current_height` (FIFO within the height bucket per CIP-5 §5.1).
3. Process system-generated deferred transactions.

Any document still asserting Timer-then-Tx (v1 §3 step 4) is **superseded** by this rule.

### 2. Unified future design — GBA + Auction are complementary

CIP-1's GBA contracts and CIP-5 §9's auction mechanism do NOT compete. They are different layers of the same future system:

| Layer | Component | Source |
|---|---|---|
| **Bid generation** | Per-timer GBA contract returns `(bid, cycles_limit)` based on real-time context | CIP-1 v1 §4.2 |
| **Auction mechanism** | Sort timers by `(bid + Bias(n)) / cycles_limit`; greedy fill within `TIMER_PROCESSING_BUDGET_CYCLES`; VCG payment (or first-price fallback) | CIP-5 §9.2–9.5 |
| **Caps and fairness** | `MAX_FIRES_PER_BLOCK`, `MAX_FIRES_PER_ACTOR`, exponential bias prevents starvation | CIP-5 §9.4 + CIP-1 v1 §3 priority-weight |

In the unified future design:

- A timer's `bid` parameter is supplied by the actor's GBA contract (per CIP-1 v1 §4.2).
- The auction selects winners using `(bid + Bias(n)) / cycles_limit` (per CIP-5 §9.2).
- VCG is the target payment rule; first-price is the fallback (per CIP-5 §9.5).
- Carried-over (deferred) timers accumulate `Bias(n)` each block they remain unexecuted.

CIP-5 §9.9's "Open question — Interaction with CIP-1 GBA" is hereby **closed**: GBA is the bid source; the auction selects winners.

### 3. `TIMER_PROCESSING_BUDGET_CYCLES` (constant unification)

The future design uses one constant, not two. v2 names it `TIMER_PROCESSING_BUDGET_CYCLES` and pins its current code value as the v1 baseline:

| Source | Constant name | Default value |
|---|---|---|
| CIP-1 v1 §3 | `TIMER_PROCESSING_BUDGET_CYCLES` | (governance-tunable) |
| CIP-5 §9.4 | block timer budget | (governance-tunable) |
| Code today (`node/types/src/constants.rs`) | block timer budget | **`8,888,890`** |

These are the same parameter. Auction adoption will require governance review of this value.

### 4. Migration from FIFO to auction

When the future auction is activated, existing FIFO behavior MUST be preserved as a degenerate case:

- Timers scheduled without a `bid` (today, all of them) default to `bid = 0` and rely on bias accumulation.
- Timers scheduled without an explicit `cycles_limit` (today, all of them) default to the existing `550,000` cycle limit per fire (CIP-5 §5.2).
- The activation block is governance-determined; until then, CIP-5 §1–7 FIFO is canonical.

### 5. Opcode allocation

CIP-1 introduces no new system instruction opcodes. The future `schedule_timer` extension (`bid` + `cycles_limit` per CIP-5 §9.7) is a host-API change, not a `SystemInstruction` change. Existing `schedule_timer` / `schedule_timer_ex` / `cancel_timer` / `extend_timer` host syscalls (`node/execution/src/pvm_host.rs:1489-1652`) gain optional parameters.

### 6. Same-block prohibition (reaffirmed)

CIP-1 v1 §3 step 5c and CIP-5 §5.3 both state: timers created within the current block's transactions MUST NOT execute in the same block. v2 reaffirms this; it is consensus-critical (avoids reentrancy via timer scheduling).

### 7. Backwards compatibility

Strictly additive over CIP-5 v1. No syscall, opcode, or constant changes from current state. The future auction (CIP-5 §9) and GBA contracts (CIP-1) remain Phase 2 / Phase 3 work and require separate governance activation.

