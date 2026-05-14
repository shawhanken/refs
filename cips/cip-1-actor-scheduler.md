---
title: "CIP-1: Actor Message Scheduler (v3)"
description: v3 — replaces the first-price + exponential-bias auction (Part I / Part II §2) with an EIP-1559 timer basefee + priority tip + per-actor fairness weight; default GBA specified inline; CIP-5 retains the canonical current-implementation FIFO until v3 activation
---

# CIP-1 v3

> **Versioning.** This is v3 of CIP-1. v1 is preserved verbatim as Part I; v2 (the CIP-5-alignment revision) as Part II; v3 (this revision, the EIP-1559 hybrid target design) is Part III.
>
> **Conflict rule:** Part III is canonical wherever it contradicts Part I or Part II §§2–3. Part II §§1, 4–9 (block ordering, lane naming, opcode mapping, CIP-5 fee-model alignment, migration impact, backwards compat) remain canonical — v3 does not change them. CIP-5 §§1–8 remain canonical for the currently-implemented FIFO behaviour until v3 activates.
>
> **Summary of v3 changes**
>
> - **Replaces the first-price-per-cycle + exponential-bias auction** (Part I §3 step 4–5 + §5; Part II §2 unified design + §3 priority semantics) with an **EIP-1559 timer-lane basefee + priority tip** mechanism on top of CIP-3's dual-meter basefee. Rationale: first-price-per-cycle is structurally unstable in repeated knapsack settings (well-documented literature), and the EIP-1559 design reuses six years of EVM mainnet patterns. The `bid: int` parameter on `schedule_timer` (Part II §2 / CIP-5 §9.7) is dropped; replaced by `(max_fee_per_cycle, max_priority_fee_per_cycle)` per Part III §3.
> - **Replaces the per-timer exponential bias `e^(nλ)`** (Part I §3 step 6; CIP-5 §9.2) with a **per-actor fairness weight `W(actor) ∈ [1, 2]`** computed over a 1,000-block rolling window. Bias-on-deferred-timer was retrospective and gameable via timer-spam; per-actor weight is preventive and cannot be amplified by re-scheduling.
> - **Closes Gap G7 (default GBA bidding strategy unspecified)** by spelling the default GBA inline (~2 lines) in Part III §5: `max_fee_per_cycle = 2 × current_basefee`, `max_priority_fee_per_cycle = previous_block_p50_priority_tip`.
> - **Adds per-timer cycle cap** `MAX_CYCLES_PER_FIRE_AUCTION_PHASE = 250,000` (= 12.5% of `LANE_TIMER_CYCLES`) to prevent any single timer from monopolising the lane. CIP-5 §6.4's `max_cycles_per_fire = 550_000` remains in force during the FIFO phase; the tighter 250k cap activates with v3.
> - **Pins Timer-lane fee multiplier at 1.0×** (per CIP-3 §2.2.3 amendment in batch B4): no subsidy at launch. Tier-0 tunable.
> - **Closes CIP-5 §9 open questions** by either resolving them (G7 default GBA → spec'd; "Interaction with CIP-1 GBA" → see §2 below) or evaporating them (`λ` calibration → no longer relevant; VCG revenue gap → not applicable; reserve price → replaced by `MIN_BASEFEE` per CIP-3).
> - **CIP-5 §9 is REMOVED** as a co-change in the same batch as v3 activation; CIP-5 retains §§1–8 (current FIFO + per-fire `fee_payer`) until v3 ships.
>
> **What v3 does NOT change**
>
> - **Block ordering:** Tx-then-Timer remains canonical (Part II §1 / CIP-5 §5.1).
> - **Per-fire `fee_payer` model:** CIP-5 §6.3 remains binding. The EIP-1559 priority tip is *additional* to the per-fire `max_cost` pre-charge, not a replacement.
> - **Three-path lifecycle:** natural fire / TTL expiry / insufficient-funds self-destruct (CIP-5 §5.4) is unchanged.
> - **Lane separation:** `LANE_TIMER_CYCLES` (execution) vs `TIMER_GC_CYCLES` (cleanup) (CIP-5 §6.5) is unchanged.
> - **System instruction opcodes** (`SYS_CANCEL_TIMER = 48`, `SYS_UPDATE_TIMER_CONFIG = 49`, `SYS_EXTEND_TIMER = 50`) are unchanged.
> - **Same-block prohibition** (CIP-5 §5.3) remains in force.
>
> **Summary of v2 changes (retained for historical context)**
>
> - Aligns with CIP-5 (revised 2026-04-20) which now specifies **Tx-then-Timer** block ordering natively in §5.1. CIP-1 v1's 2026-04-15 amendment caveat is superseded — there is no discrepancy left to flag.
> - Recognises CIP-5 §6.3's **per-fire `fee_payer` model**: timers are NOT free. Each fire pre-charges `fee_payer` for `max_cost = gas_limit_per_fire × basefee + cells × basefee`, then refunds the unused portion. CIP-5 v1's "system-triggered, no fee charged" claim is superseded.
> - Recognises CIP-5 §5.4's **three-path lifecycle** (natural fire / TTL expiry / insufficient-funds self-destruct) plus explicit cancellation, and CIP-5 §6.5's **separation of `LANE_TIMER_CYCLES` (execution) from `TIMER_GC_CYCLES` (cleanup)** so a TTL-expiry storm cannot starve live timers.
> - Unified CIP-1's GBA contracts with CIP-5 §9's exponential-bias auction (Part II §2). **Superseded by Part III** — the auction layer is replaced; GBA contracts remain a useful concept and are reframed in Part III §5.
> - Renames v1's `TIMER_PROCESSING_BUDGET_CYCLES` → `LANE_TIMER_CYCLES` per CIP-5 §6.5.
> - Acknowledges new CIP-5 system instructions (`SYS_CANCEL_TIMER` / `SYS_UPDATE_TIMER_CONFIG` / `SYS_EXTEND_TIMER`) which are **already in code at opcodes 48 / 49 / 50** — no new allocation needed. (Earlier draft recommended 70–72; that was based on a stale opcode map and is withdrawn — see Part II §6.)

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

---

## Part III — v3 Revision (canonical; EIP-1559 timer hybrid target design)

### 0. What this revision does

v3 replaces the first-price-per-cycle auction + exponential-bias mechanism (Part I §3 step 4–5 + §5; Part II §2 + §3; CIP-5 §9) with an **EIP-1559 timer-lane basefee + priority tip** mechanism augmented by a **per-actor fairness weight `W(actor) ∈ [1, 2]`** over a rolling 1,000-block window. Default GBA bidding strategy is specified inline (closing Gap G7 from the 2026-04-05 design review).

The replacement preserves Part II's invariants — Tx-then-Timer block ordering, per-fire `fee_payer` pre-charge + refund, three-path lifecycle, lane separation, and same-block prohibition — and supersedes CIP-5 §9 (removed in the same activation batch).

### 1. Why EIP-1559 over first-price auction

Three structural advantages, all observable today on Ethereum mainnet:

1. **First-price-per-cycle is unstable in repeated knapsack settings.** Bidders best-respond by underbidding the prior round's clearing price, leading to oscillation and revenue collapse when actors are *programmatic* (CIP-1 v1 §1's "autonomous actors" cannot easily run a complex bidding strategy, much less converge a Nash equilibrium against other agents). EIP-1559 eliminates the strategic-bidding component entirely: the basefee is deterministic from the prior block's utilisation, and the priority tip is a simple price-discovery channel for ordering within the lane.
2. **Default GBA collapses to ~2 lines.** Under first-price + exponential bias the default GBA's optimal strategy is open-ended (Gap G7); under EIP-1559 it reduces to `max_fee = 2 × basefee`, `max_priority_fee = previous_block_p50_tip` — analogous to MetaMask's default estimator on EVM. Removes the centralisation pressure flagged in [03-runner-marketplace.md §-cross-ref item #23] where conservative defaults would systematically deprioritise unsophisticated actors.
3. **Invalid-bid attack class disappears structurally.** Part II inherited an open question on what happens when a GBA returns an invalid or maliciously-high bid (Gap G7 / review item #13). Under EIP-1559 there is no `bid` field: `max_priority_fee_per_cycle` is bounded by `max_fee_per_cycle − basefee` (lossy clamping is structural), and the per-fire `max_cost` pre-charge (CIP-5 §6.3) already caps the worst-case debit per fire. No drain attack survives.

### 2. Mechanism

When the v3 auction phase is active, end-of-block timer execution proceeds:

1. **Collect.** Take the timer bucket for `current_block_height` after Tx-phase completion (Part II §1 / CIP-5 §5.1). Apply lifecycle classification per CIP-5 §5.4 (TTL expiry / insufficient-funds → GC lane).
2. **Compute lane basefee.** The Timer-lane basefee adjusts per block using EIP-1559 dynamics over the prior block's timer-lane utilisation:
   ```
   utilisation_{H} = cycles_consumed_in_lane_{H} / LANE_TIMER_CYCLES        // ∈ [0, 1]
   basefee_{H+1}   = basefee_{H} × (1 + clip((utilisation_{H} − 0.5) / 0.5, −0.125, +0.125))
   ```
   - Target utilisation: 0.5 (50%) of the 2,000,000-cycle Timer lane.
   - Max basefee adjustment per block: ±12.5%.
   - 100% of the basefee is **burned** (consistent with CIP-3 §2.4 and WP §6 "100% basefee burn"); the lane basefee is *additional to* the cycle basefee charged under CIP-3 — implementations track the two separately to preserve per-lane burn telemetry. Per-lane fee multiplier is pinned at `1.0×` (CIP-3 §2.2.3 + WP §6 / §17.9; no subsidy at launch).
3. **Compute priority for each due timer:**
   ```
   priority_per_cycle = min(max_priority_fee_per_cycle, max_fee_per_cycle − basefee_lane)
   effective_priority = priority_per_cycle × W(actor)
   ```
   Where `W(actor) ∈ [1, 2]` is the per-actor fairness weight (§4 below).
4. **Sort and select.** Order due timers by `effective_priority` descending; tie-break by `(timer_id, schedule_block)`. Greedily fill `LANE_TIMER_CYCLES` budget. Each selected timer is gated by `cycles_consumed_so_far + gas_limit_per_fire ≤ LANE_TIMER_CYCLES − cycles_already_used` AND `gas_limit_per_fire ≤ MAX_CYCLES_PER_FIRE_AUCTION_PHASE` (250k by default; §6 below). Timers exceeding the per-timer cap are deferred without an attempt.
5. **Settle.** For each selected timer:
   - Pre-charge `fee_payer` as per CIP-5 §6.3:
     ```
     max_cost = gas_limit_per_fire × (basefee_cycle + priority_per_cycle) + max_cells × basefee_cell
     ```
     (i.e. the `max_cost` formula gains a priority-tip term; cycle basefee + cell basefee per CIP-3 unchanged).
   - Execute handler. On normal return refund unused cycles × `(basefee_cycle + priority_per_cycle)`. Tip portion goes to the **block proposer** (consistent with CIP-3 §2.4 tips routing).
   - On insufficient funds at any step → CIP-5 §5.4 path 2 (self-destruct without firing).
6. **Defer.** Timers not selected remain in the bucket; on the next block they fall through the same flow with the same `W(actor)`. The 1,000-block fairness window naturally raises `W(actor)` for actors whose timers are repeatedly deferred (§4 below).
7. **Update fairness counters.** Increment per-actor `recent_executions[actor] += 1` for every timer fired; the 1,000-block rolling decay is applied at the start of the next EOB step (§4).

### 3. Schedule-timer API extension

The CIP-5 §4.1 / §9.7 `schedule_timer` host API gains two parameters under v3 (replacing the `bid: int = 0` parameter that v2 inherited from CIP-5 §9.7):

```python
timer_id = pvm_host.schedule_timer(
    height: int,
    payload: bytes,
    fee_payer: bytes = None,                    # as CIP-5 §4.1
    gas_limit: int = None,                      # as CIP-5 §4.1
    expires_at: int = None,                     # as CIP-5 §4.1
    max_fee_per_cycle: int = None,              # NEW v3: defaults to default-GBA value (§5)
    max_priority_fee_per_cycle: int = None,     # NEW v3: defaults to default-GBA value (§5)
)
```

Validation at scheduling time:

- `max_fee_per_cycle ≥ current_lane_basefee` → else `TimerRejectedBelowBasefee` (immediate failure; nothing escrowed).
- `max_priority_fee_per_cycle ≤ max_fee_per_cycle − current_lane_basefee` → else clamp at schedule time and emit `TimerPriorityClampedAtSchedule(stated, clamped)` for observability.
- No new escrow: under EIP-1559 there is no bid to escrow. The per-fire `max_cost` (CIP-5 §6.3) is pre-charged at execution time only, not at scheduling. This eliminates the cancellation-refund accounting that CIP-5 §9.7 v1 required for the `bid` field.

`bid` from the prior CIP-5 §9.7 surface is **withdrawn** under v3. Old callers passing `bid = 0` (i.e. all current callers) continue to work — `bid` is silently accepted and ignored during a one-release deprecation window, then rejected with `TimerArgDeprecated`.

### 4. Per-actor fairness weight `W(actor)`

Replaces Part I §3 step 6 ("per-actor priority weight via exponential decay") and CIP-5 §9.2 ("exponential bias on deferred timers"). The shift from per-*timer* exponential bias to per-*actor* weight is the central anti-monopolisation change of v3.

**Formula:**

```
recent_executions[actor]  = sum of timer fires by `actor` over the most recent 1,000 blocks
network_median            = median of recent_executions across actors with ≥1 fire in window
                            (or 0 if no actor has fired in the window)
ratio[actor]              = recent_executions[actor] / max(1, network_median)
W(actor)                  = clip(2 − ratio[actor], 1, 2)
```

- An actor at or below the network median (`ratio ≤ 1`) gets `W = 2` (maximum boost). An actor at 2× the median or above (`ratio ≥ 2`) gets `W = 1` (no boost). Linear interpolation in between.
- Window length `FAIRNESS_WINDOW_BLOCKS = 1_000` (~16.7 min at 1s blocks), Tier-2 governance-tunable. Stored at `0x09` under `system:cip1:fairness_window_blocks`.
- `ratio` is **clipped** to `[0, 2]` before subtraction, so a brand-new actor with zero recent fires gets `W = 2` rather than infinity.

**State.** Each `actor` carries a 1,000-element ring buffer of fire-counts per block in the Actor Scheduler state. Memory cost: ~8 KiB per actively-firing actor. Eviction: actors with zero fires in the entire 1,000-block window are pruned from the fairness map (next fire re-creates a fresh entry).

**Mutability of formula structure.** Tier-2 (governance changes the inclusion ordering, which affects fee revenue distribution). The numeric `FAIRNESS_WINDOW_BLOCKS` and the `[1, 2]` clip bounds are Tier-0.

**Known limitations (Phase-5 simulation deferred):**

1. **Fragmentation attack.** A sophisticated developer can deploy 100 actor instances and treat each as a separate "quiet" actor to bypass per-actor weight. Mitigation candidate: per-deployer weight (using actor-creation trace) instead of per-actor — requires deeper actor metadata than CIP-2 currently exposes. Phase-5 simulation MUST size the attack magnitude before v3 ships; if material, per-deployer weight is added in v3.r2.
2. **Median moves under shock.** When a large runner enters/exits and shifts the network median sharply, incumbents are briefly disadvantaged for ~1,000 blocks. EMA-smoothing the median (analogous to the HHI smoothing in CIP-2 §5 amend) is a candidate v3.r2 addition.

### 5. Default GBA (closes Gap G7)

GBA contracts as described in Part I §4.2 remain a useful abstraction for actors that need dynamic, context-sensitive bidding (DeFi liquidation actors, oracle-pushers, MEV-aware schedulers). v3 specifies the **protocol-default GBA** that the runtime supplies when an actor doesn't provide one.

**Default GBA — normative:**

```python
def getGasBid(context: GBAContext) -> TxFeeParams:
    # context fields per Part I §4.2 (unchanged):
    #   trigger_block_height, current_block_height,
    #   basefee_cycle, basefee_cell, basefee_lane_timer,
    #   last_block_cycle_usage,
    #   previous_block_p50_priority_tip_per_cycle,
    #   owner_actor_balance
    return TxFeeParams(
        max_fee_per_cycle           = 2 * context.basefee_lane_timer,
        max_priority_fee_per_cycle  = context.previous_block_p50_priority_tip_per_cycle,
        # cell side: defaults to CIP-3 basefee_cell with no priority (timers are cycle-bound)
        max_fee_per_cell            = context.basefee_cell,
        max_priority_fee_per_cell   = 0,
    )
```

- `2 × basefee` headroom absorbs up to ~5 blocks of basefee growth at the ±12.5% per-block clamp (`1.125^5 ≈ 1.80`) before hitting the cap — sufficient for normal congestion swings.
- `p50 priority tip` is the prior-block median priority fee paid by *fired* timers; falls back to `0` if no timers fired in the prior block (avoids an undefined estimator on cold start).
- The `basefee_lane_timer` context field is **new in v3** — added to `GBAContext` so default and custom GBAs can compute their bid against the lane-specific basefee rather than the global cycle basefee.

**SDK convenience: `priority_tier_hint`.** The `cowboy-py` SDK MAY expose a high-level enum for callers who don't want to construct a GBA:

```python
class PriorityTier(Enum):
    ECONOMY  = "economy"   # multiplier 0.8× on max_priority_fee_per_cycle
    STANDARD = "standard"  # multiplier 1.0× (default)
    FAST     = "fast"      # multiplier 1.5×
    URGENT   = "urgent"    # multiplier 2.5×

cowboy.schedule_timer(..., priority_tier_hint=PriorityTier.FAST)
# expands to: max_priority_fee_per_cycle = 1.5 × p50_priority_tip
```

These four multipliers (0.8 / 1.0 / 1.5 / 2.5) are stored at `0x09` under
`system:cip1:priority_tier_multipliers.{economy,standard,fast,urgent}` and are **Tier-0 governance-tunable** (consistent with the lane fee multipliers in CIP-3 §2.2.3 — both are multiplicative scalars on fee components, neither redirects revenue across recipient classes). CIP-12 §5.1 Tier 0 scope already references "any `governance-tunable` parameter (see genesis defaults and CIP-1/3/5/9/10)"; the priority-tier multipliers are picked up automatically by that clause, and CIP-12 §5.1's reference list is extended in the same activation batch to include **CIP-31** for completeness.

### 6. Per-timer cycle cap during auction phase

```
MAX_CYCLES_PER_FIRE_AUCTION_PHASE = 250_000
```

= 12.5% of `LANE_TIMER_CYCLES = 2,000,000`. A single timer cannot consume more than 1/8th of the lane. CIP-5 §6.4's `max_cycles_per_fire = 550_000` remains in force during the FIFO phase (when there is no per-block scarcity competition); the tighter 250k cap activates with v3 to prevent single-timer monopolisation in the auction phase.

Actors with handlers that legitimately need >250k cycles can split the work across multiple timer fires; the same-block prohibition (CIP-5 §5.3) prevents tail-end re-fires from compounding in a single block.

**Mutability.** Tier-0, key `system:cip1:max_cycles_per_fire_auction_phase`.

### 7. Migration from FIFO (CIP-5 §§3–8) to v3 hybrid

Activation is a single governance proposal (Tier-3 by analogy with CIP-3 basefee curve changes; bicameral). At activation block `H_v3`:

| Subsystem | Pre-`H_v3` | Post-`H_v3` |
|---|---|---|
| Inclusion order within bucket | FIFO by insertion | Sort by `effective_priority` (§2 step 4) |
| `bid` field | Accepted, ignored (v2) | Rejected: `TimerArgDeprecated` |
| Timer-lane basefee | Equal to global cycle basefee | EIP-1559 dynamics over prior-block lane utilisation |
| Default GBA | "Bids conservatively" (Part II §5; underspecified) | Normative two-line estimator (§5 above) |
| Per-timer cap | `max_cycles_per_fire = 550_000` (CIP-5 §6.4) | `MAX_CYCLES_PER_FIRE_AUCTION_PHASE = 250_000` |
| Fairness | None | `W(actor) ∈ [1, 2]`, 1,000-block window |

**Already-scheduled timers at `H_v3`:** stay in their buckets; gain `W(actor) = 2` (max boost) by default (zero recent fires in the freshly-initialised window); compete on `effective_priority` from `H_v3 + 1` onward.

**Caller migration:** existing callers (`schedule_timer(height, payload)` with no fee fields) continue to work — they receive the default-GBA estimator under the hood. Callers that previously passed `bid` get a one-release deprecation warning, then a hard error.

### 8. Open questions deferred to Phase-5 simulation

- **`FAIRNESS_WINDOW_BLOCKS`** calibration. 1,000 blocks (~16.7 min) is the launch default; longer windows smooth more but lag more on actor identity changes.
- **Per-deployer vs per-actor weight** (fragmentation-attack threat magnitude, §4 limitation 1).
- **Median EMA-smoothing** (§4 limitation 2) — whether to ship in v3.r2 or wait for empirical shock evidence.
- **Priority-tier multipliers** {0.8, 1.0, 1.5, 2.5} — empirical tuning against actual congestion patterns.
- **Lane fee multiplier** — pinned at 1.0× at launch (CIP-3 §2.2.3); Phase-5 simulation MAY recommend a 0.8× Timer-lane subsidy if the lane is structurally under-utilised post-mainnet.

### 9. v3 backwards compatibility

- **CIP-5 §§1–8** unchanged for both FIFO and auction phases. **CIP-5 §9 is removed** in the v3 activation batch — its functionality is replaced by this Part III + the per-actor fairness weight.
- **System instruction opcodes 48 / 49 / 50** unchanged.
- **Per-fire `fee_payer` model (CIP-5 §6.3)** unchanged. The EIP-1559 priority tip extends the `max_cost` formula but does not change the pre-charge / refund mechanics.
- **Block ordering** Tx-then-Timer (Part II §1 / CIP-5 §5.1) unchanged.
- **Same-block prohibition** (CIP-5 §5.3) unchanged.
- **Existing callers** of `schedule_timer(height, payload)` work without source change — they get the default GBA estimator implicitly.
- **Callers passing `bid`** receive one release of deprecation warning, then hard error. v2 documentation that references `bid` (CIP-9 v2 §12 PoR challenge timer, CIP-16 v2 reverify) MUST be updated in the v3 activation batch to drop the `bid` field.

### 10. Decision-register dependencies

This Part III has **no Decision-Register gates** — every parameter and design choice in v3 is either a Tier-0 governance-tunable default or a structural recommendation. The activation block `H_v3` is itself a Tier-3 governance proposal; that is the only policy lever required.

(Cross-ref: WP §5.1 is split into 5.1a "Currently Implemented (CIP-5 FIFO)" and 5.1b "Target Design (CIP-1 v3 EIP-1559 hybrid)" in the same activation batch; CIP-12 §5.2 Tier-2 list gains `priority_tier_multipliers`.)
