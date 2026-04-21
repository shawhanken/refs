---
title: "CIP-1: Actor Message Scheduler (v2)"
description: Code-aligned v2 — aligns with CIP-5 revised 2026-04-20 (per-fire fee_payer model, three-path lifecycle, LANE_TIMER_CYCLES naming); unifies CIP-1 GBA with CIP-5 §9 auction
---

# CIP-1 v2

> **Versioning.** This is v2 of CIP-1. v1 is the canonical document `cip-1-actor-scheduler.md` (preserved verbatim as Part I). v2 = v1 + the alignment revision (Part II).
>
> **Conflict rule:** Part II is canonical wherever it contradicts Part I. Part II also realigns with CIP-5 (revised 2026-04-20).
>
> **Summary of v2 changes**
>
> - Aligns with CIP-5 (revised 2026-04-20) which now specifies **Tx-then-Timer** block ordering natively in §5.1. CIP-1 v1's 2026-04-15 amendment caveat is superseded — there is no discrepancy left to flag.
> - Recognises CIP-5 §6.3's **per-fire `fee_payer` model**: timers are NOT free. Each fire pre-charges `fee_payer` for `max_cost = gas_limit_per_fire × basefee + cells × basefee`, then refunds the unused portion. CIP-5 v1's "system-triggered, no fee charged" claim is superseded.
> - Recognises CIP-5 §5.4's **three-path lifecycle** (natural fire / TTL expiry / insufficient-funds self-destruct) plus explicit cancellation, and CIP-5 §6.5's **separation of `LANE_TIMER_CYCLES` (execution) from `TIMER_GC_CYCLES` (cleanup)** so a TTL-expiry storm cannot starve live timers.
> - **Unifies** CIP-1's GBA contracts with CIP-5 §9's exponential-bias auction. They are NOT competing designs: GBA produces the bid; the auction selects winners. The auction layer adds **priority** on top of the basefee — it does not replace the per-fire fee model. Closes CIP-5 §9.9 open question.
> - Renames v1's `TIMER_PROCESSING_BUDGET_CYCLES` → `LANE_TIMER_CYCLES` per CIP-5 §6.5.
> - Acknowledges new CIP-5 system instructions (`SYS_CANCEL_TIMER` / `SYS_UPDATE_TIMER_CONFIG` / `SYS_EXTEND_TIMER`) which are **already in code at opcodes 48 / 49 / 50** — no new allocation needed. (Earlier draft recommended 70–72; that was based on a stale opcode map and is withdrawn — see §6.)

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

## Part II — v2 Revision (canonical; alignment with CIP-5 revised 2026-04-20 + code reality)

### 0. What this revision does

CIP-1 v1 specifies a **future** scheduler (tiered Calendar Queue + Gas Bidding Agent contracts) that is not implemented. CIP-5 (revised 2026-04-20) is now the canonical spec for the **currently implemented** behavior:

- **Tx-then-Timer** block ordering (§5.1)
- FIFO timers within a height bucket (§5.1)
- **Per-fire `fee_payer` model** with pre-charge + refund (§6.3) — timers are NOT free
- **Three-path timer lifecycle** (§5.4): natural fire / TTL expiry / insufficient-funds self-destruct, plus actor-self and validator-set explicit cancellation
- `TimerConfig` (§6.4) governance-tunable; `LANE_TIMER_CYCLES` separated from `TIMER_GC_CYCLES` (§6.5)

CIP-5 §9 still describes a **future** auction (exponential bias + VCG). v2 unifies CIP-1's GBA with CIP-5 §9 as one future design (see §2 below).

### 1. Block ordering: Tx-then-Timer (canonical)

CIP-5 §5.1 (revised 2026-04-20) specifies Tx-then-Timer natively. The earlier 2026-04-15 amendment in CIP-1 v1 (which flagged the discrepancy) is **superseded** — there is no longer a discrepancy. Canonical sequence per CIP-5 §5.1:

1. Execute all user transactions (TX phase).
2. Query `get_timers_by_height(current_height)`; classify per CIP-5 §5.4 (TTL expired / insufficient funds → self-destruct under `TIMER_GC_CYCLES`; otherwise pre-charge `fee_payer` and enqueue).
3. Execute timer deferred transactions (FIFO) before engine and mailbox deferred transactions.

Any document still asserting Timer-then-Tx (CIP-1 v1 §3 step 4) is **superseded** by CIP-5 §5.1.

### 2. Unified future design — GBA + Auction are complementary

CIP-1's GBA contracts and CIP-5 §9's auction mechanism do NOT compete. They are different layers of the same future system:

| Layer | Component | Source |
|---|---|---|
| **Bid generation** | Per-timer GBA contract returns `(bid, gas_limit_per_fire)` based on real-time context | CIP-1 v1 §4.2 |
| **Auction mechanism** | Sort timers by `(bid + Bias(n)) / gas_limit_per_fire`; greedy fill within `LANE_TIMER_CYCLES`; VCG payment (or first-price fallback) | CIP-5 §9.2–9.5 |
| **Caps and fairness** | `MAX_FIRES_PER_BLOCK`, `MAX_FIRES_PER_ACTOR`, exponential bias prevents starvation | CIP-5 §9.4 |
| **Underlying basefee** | Per-fire `fee_payer` pre-charge / refund (auction-independent) | CIP-5 §6.3 |

In the unified future design:

- A timer's `bid` parameter is supplied by the actor's GBA contract (per CIP-1 v1 §4.2).
- The auction selects winners using `(bid + Bias(n)) / gas_limit_per_fire` (per CIP-5 §9.2).
- VCG is the target payment rule; first-price is the fallback (per CIP-5 §9.5).
- The auction layer rides ON TOP OF the per-fire fee model (§3 below) — bid is for **priority within the lane**, not for the basefee. Basefee is always paid per CIP-5 §6.3 regardless of auction state.

CIP-5 §9.9's "Open question — Interaction with CIP-1 GBA" is hereby **closed**: GBA produces the bid; the auction selects winners; basefee is independent.

### 3. Per-fire fee model (CIP-5 §6.3) — auction adds priority, not pricing

Even with the auction inactive (current state), every timer fire under CIP-5 §6.3 is a **paid execution**:

```
1. max_cost = gas_limit_per_fire × cycle_basefee + max_cells_per_fire × cell_basefee
2. If balance(fee_payer) < max_cost → insufficient-funds self-destruct (CIP-5 §5.4 path 2)
3. Otherwise: pre-charge max_cost from fee_payer, execute, refund unused
```

This is a fundamental change from CIP-5 v1's "Timer execution is system-triggered — no explicit basefee or tip is charged" claim (now superseded by CIP-5 revised 2026-04-20 §6.3). The future auction layer (CIP-5 §9) sits ATOP this fee model:

- The **bid** is the actor's stated maximum *priority budget*, paid into the auction clearing price (VCG or first-price). It is **separate** from `max_cost` (basefee).
- A timer with `bid = 0` and `Bias(n) = 0` may still fire if the lane is uncongested — it pays the basefee normally and uses no priority budget.
- Under congestion (lane full), only timers whose `(bid + Bias(n)) / gas_limit_per_fire` exceeds the marginal kicked-out timer make the cut. Losers carry over to the next block, accumulating bias.

Bid is a **layer above** basefee, not a replacement.

### 4. Lane budget naming: `LANE_TIMER_CYCLES` (per CIP-5 §6.5)

The future-design constant is named `LANE_TIMER_CYCLES` per CIP-5 §6.5. v1 §3 used `TIMER_PROCESSING_BUDGET_CYCLES`; v2 normalizes to the CIP-5 name and keeps GC cleanly separate:

| Source | Name | Default | Purpose |
|---|---|---|---|
| CIP-1 v1 §3 | `TIMER_PROCESSING_BUDGET_CYCLES` | (governance-tunable) | obsolete name |
| **CIP-5 §6.5** | **`LANE_TIMER_CYCLES`** | (governance-tunable; per `TimerConfig`) | **execution lane (path 1)** |
| **CIP-5 §6.5** | **`TIMER_GC_CYCLES`** | `TimerConfig.gc_cycles_per_block = 5_000_000` | **cleanup lane (paths 2 / 3)** |
| Code (`node/types/src/constants.rs`) | block timer execution budget | matches `LANE_TIMER_CYCLES` | implementation |

`LANE_TIMER_CYCLES` and `TIMER_GC_CYCLES` are independent budgets. The auction (CIP-5 §9.4) operates only on `LANE_TIMER_CYCLES`; GC (TTL expiry, insufficient-funds destruction) draws from `TIMER_GC_CYCLES` to prevent a resume-after-outage storm from starving live timer execution.

### 5. Migration from FIFO to auction

When the future auction is activated, existing FIFO behavior MUST be preserved as a degenerate case:

- Timers scheduled without a `bid` (today, all of them) default to `bid = 0` and rely on bias accumulation under the auction.
- Timers scheduled without an explicit `gas_limit_per_fire` (today, all of them) default to `TimerConfig.max_cycles_per_fire = 550_000` per CIP-5 §6.4.
- The per-fire **`fee_payer` model** (CIP-5 §6.3) is independent of the auction and is **already in effect today**. Auction activation does not change basefee economics.
- The activation block is governance-determined; until then, CIP-5 §1–7 FIFO is canonical.

### 6. New CIP-5 system instructions (no opcode collision)

CIP-5 (revised) §5.4 and §6.4 introduces three new `SystemInstruction` variants that did not exist in CIP-5 v1:

| Symbolic name | Sender | Purpose |
|---|---|---|
| `SYS_CANCEL_TIMER { timer_id }` | `system_deployers` | Validator-set emergency cancel of a misbehaving / abandoned timer |
| `SYS_EXTEND_TIMER { timer_id, new_expires_at }` | `system_deployers` | Emergency TTL extension when actor can no longer self-extend |
| `SYS_UPDATE_TIMER_CONFIG { config }` | `system_deployers` | Governance-tune `TimerConfig` (TTL / per-fire caps / GC budget) |

**These instructions are ALREADY in code** (`node/types/src/execution.rs:525-534`):

| Symbolic name | Opcode | Code line |
|---|---:|---|
| `SYS_CANCEL_TIMER` | **48** | `pub const SYS_CANCEL_TIMER: u8 = 48;` |
| `SYS_UPDATE_TIMER_CONFIG` | **49** | `pub const SYS_UPDATE_TIMER_CONFIG: u8 = 49;` |
| `SYS_EXTEND_TIMER` | **50** | `pub const SYS_EXTEND_TIMER: u8 = 50;` |

CIP-5 (revised 2026-04-20) §5.4 / §6.4 specify these instructions; the code constants pre-date the spec revision. **No new opcode allocation is needed** for CIP-5 timer ops. An earlier CIP-1 v2 draft incorrectly recommended slots 70–72 because it was based on a stale opcode map that did not yet show 44–51 as taken. The canonical master allocation table is in CIP-13 v2 §1.

CIP-1 itself introduces no new system instruction opcodes. The future `schedule_timer` extension (`bid` + `cycles_limit` per CIP-5 §9.7) is a host-API change, not a `SystemInstruction` change. Existing PVM host syscalls (`schedule_timer` / `schedule_timer_ex` / `cancel_timer` / `extend_timer` at `node/execution/src/pvm_host.rs:1489-1652`) gain optional parameters when the auction activates.

### 7. Same-block prohibition (reaffirmed)

CIP-1 v1 §3 step 5c and CIP-5 §5.3 both state: timers created within the current block's transactions MUST NOT execute in the same block. v2 reaffirms this; consensus-critical (avoids reentrancy via timer scheduling).

### 8. Migration impact of CIP-5 fee model

The CIP-5 revision (2026-04-20) introduces the per-fire fee model as a substantive change from CIP-5 v1. Pre-revision callers who assumed timers were free will hit `TimerCancelledInsufficientFunds` events on their first fire after activation. Migration:

- Each scheduling actor MUST fund either itself or a designated `fee_payer` with at least one `max_cost` reserve per pending timer.
- Long-running heartbeat actors SHOULD use `schedule_timer_ex` with explicit `fee_payer` (default `actor_self`) and monitor balance.
- The `TimerCancelledInsufficientFunds` event is the canonical signal that a timer self-destructed for funding reasons — actors / their watchtowers SHOULD subscribe.
- TTL-protected timers (`expires_at` set by `schedule_timer_ex`) auto-clean if abandoned; no manual cleanup needed.

### 9. Backwards compatibility

Strictly additive over CIP-5 (revised). No syscall, opcode, or constant changes are introduced by CIP-1 v2 itself. The future auction (CIP-5 §9) and GBA contracts (CIP-1) remain Phase 2 / Phase 3 work and require separate governance activation. The CIP-5 fee model (§3 above) is binding from CIP-5's revision activation; all existing v2 docs that schedule CIP-5 timers (notably CIP-9 v2 PoR challenges, CIP-16 v2 external-domain reverify) MUST specify a `fee_payer` and handle the insufficient-funds self-destruct case.

