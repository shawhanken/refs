# ext_cip-29: Design Trade-off Analysis for the Synchronous Fire Cap

> This is an extension analysis document for [CIP-29: On-chain Event Hooks](./cip-29-on-chain-event-hooks-en.md), dedicated to justifying the chosen value of `MAX_SYNC_FIRES_PER_TOPIC`. CIP-29 §2.5 / §6.4 reference this document.

## Background

CIP-29 introduces a "tiered execution model": a single `emit_event` takes the top K subscribers by descending bid and **fires them synchronously** inside the emitter call stack; the remaining subscribers are automatically forked into `defer transaction`s and **fired asynchronously** in the next block. That K is `MAX_SYNC_FIRES_PER_TOPIC`.

During customer review, a direct question was raised:

> Since you have already accepted the "overflow goes to defer" design, why not raise the sync cap straight to 500, and only spill to defer above 500?

The essence of this question is: **are a sync sub and a defer sub equivalent "capacity units"?** If they are equivalent, the sync segment should be stretched to fit most business workloads; if they are not, we have to analyze the marginal-cost asymmetry between them and find a reasonable cut point.

This document gives the complete argument. The conclusion up front: **they are not equivalent; 64 is the conservative launch value, 256 is the practical ceiling, and 500 is infeasible.**

## 1. The Core Asymmetry: sync sub vs defer sub marginal cost

Adding one more subscriber to the sync segment and adding one more to the async segment do not draw on the same budget:

| | Sync segment, +1 sub | Async segment (defer), +1 sub |
|---|---|---|
| **Whose cycle budget is consumed** | The emitter tx's own User lane (22M) | H+1 block's overall block budget (10M target, can exceed) |
| **Whose time is occupied** | Serial execution on the propose/verify critical path (consensus-latency sensitive) | Independent tx, scheduled in parallel with other user txs |
| **Failure blast radius** | Falls inside the emitter tx's snapshot/rollback chain | Independent receipt, no cross-sub interaction |
| **basefee feedback** | Pushes up the current block's cycle consumption; this block's basefee rises | Pushes up H+1 block's consumption; next block rises |
| **Space occupied** | Validator memory + PVM state during propose/verify | Defer queue entry (lightweight) |
| **Observability** | Immediate `EmitResult` produced inside the emitter call stack | Independent receipt produced asynchronously |

**Key observation**: a sync sub "compresses" load into the emitter's own tx; a defer sub "spreads" load over the system's future blocks. Each additional sync sub directly erodes the emitter's ability to do other things in the same tx; each additional defer sub does not affect the emitter itself.

This is why the customer's "500 sync + spill to defer above 500" sounds symmetric but is actually asymmetric — paying the price of stretching the sync segment to 500 means the emitter tx itself can no longer get any work done, not that "the system has a bit more total load".

## 2. Arithmetic Ceiling: 500 sync subs must OOG

Per the cost estimate in CIP-29 §6.4, a fully-loaded sync sub costs about 56K cycles:

| Cost item | Per sub | Note |
|---|---|---|
| Index read | ~1K | Once per emit, amortized to the first sub |
| `EventSub` record read | ~500 | Once per sub |
| snapshot creation | ~1K | Once per sub |
| handler invocation overhead | ~5K | Fixed overhead of a cross-actor call |
| handler business logic (typical) | ~50K | Workload-dependent, 10K (very light) ~ 200K (complex) |
| gas-deduction write | ~500 | Updates the `gas_remaining` field |
| **Total** | **~56K cycles** | |

The User lane total budget is 22M cycles. Looking at the lane share at different sync-cap settings:

| Sync cap | × 56K (typical) | × 10K (very light handler) | Lane share (typical) | Budget left for emitter itself | Verdict |
|---|---|---|---|---|---|
| 64 (launch) | **3.6M** | 0.64M | **16%** | 18.4M | Ample, conservative |
| 128 | 7.2M | 1.3M | 33% | 14.8M | Emitter still has room |
| 256 (recommended practical ceiling) | 14.3M | 2.6M | 65% | 7.7M | Tight but feasible |
| **500** | **28M** | 5M | **127%** | **−6M, single tx must OOG** | **Bankrupt against the protocol hard ceiling** |
| 512 | 28.7M | 5.1M | 130% | Same as above | Same as above |

**At typical handler cost, 500 directly exceeds the 22M User lane** — this is the protocol hard ceiling locked in by CIP-3 §2.4, not a spec choice. Even assuming the application promises a very light handler (10K cycles), 500 subs still occupy 5M / 22M ≈ 23% of the lane, meaning:

- A single tx eats ¼ of the block cycle target (`BLOCK_CYCLES_TARGET = 10M`)
- The basefee feedback loop (EIP-1559) immediately pushes up fees along the emit path
- Doing anything else inside the same tx (multiple emits, the emitter's own business) becomes nearly impossible

So 500 sync **is arithmetically infeasible**, regardless of how handler cost is computed.

## 3. Validator Latency: a non-cycle physical constraint

Cycle metering only reflects the virtual cost inside the PVM; it **does not reflect the validator's actual CPU/IO time**. The physical time of a sync fire is composed of (in addition to cycles):

1. **PVM scheduling switch**: every cross-actor call must save the current stack, load the target actor code, set up parameters, and clean registers
2. **snapshot materialization**: QMDB write-buffer + PVM interpreter state snapshot
3. **rollback materialization** (on failure): discard buffer + restore interpreter state
4. **storage reads**: each sub triggers at least one storage trie path traversal

Measured against the current PVM implementation (pvm/crates/pvm-runtime), these operations introduce roughly **0.05–0.2 ms** of physical time per sub (excluding the handler's own business logic). Looking at the worst-case physical latency at different cap values:

| Sync cap | Physical latency (worst-case estimate) | Share of 1s block time |
|---|---|---|
| 64 | 3–13 ms | 0.3–1.3% |
| 128 | 6–26 ms | 0.6–2.6% |
| 256 | 13–51 ms | 1.3–5.1% |
| 500 | 25–100 ms | **2.5–10%** |

**Both propose and verify lie on the consensus critical path** — every additional 1 ms directly stretches block time. In the worst case, 500 sync subs can consume 10% of the block budget, and this portion **cannot be regulated by cycle metering at all** (it is not virtual work inside the PVM; it is the validator's own CPU/IO).

Note this constraint is **multiplicatively stacked** on top of the cycle constraint — even if the cycle math works out (very light handler), physical time may not.

## 4. Failure Amplification and Attack Surface

Every sync sub requires snapshot create → call handler → commit on success or rollback on failure. Along this path:

- The **snapshot subsystem** is a critical security component of the PVM. The current implementation (`pvm/crates/vm/src/vm/snapshot.rs`) is tuned for "call chains with nesting depth ≤ 32", **not** for "500 sibling nodes performing serial snapshot/rollback"
- **rollback edge cases**: every rollback involves buffer cleanup, interpreter state restoration, and storage cache invalidation; 500 parallel rollback candidates means the edge-case test surface is 8× larger than at 64
- **Malicious handler probing**: 500 independent handler entry points means the attacker has 500 chances to probe PVM edge cases (int overflow, deep recursion, memory pressure — all already defended by multiple layers such as INT_GUARD_PREAMBLE / blacklisted imports / the 1234-digit cap, but each entry point is still a piece of test surface)

Up to 256, the safety margin remains within what our current test coverage can guarantee; going to 500 requires dedicated "wide sibling" stress testing of the snapshot subsystem, and there is no clear business demand driving that extra engineering investment.

## 5. How 64 Was Picked

Laying the three constraints above against 64:

| Constraint | 64's standing in the sync segment |
|---|---|
| **lane budget** (22M) | 16% used; emitter still has 84% for its own job |
| **Physical latency** (1s block) | Worst case 13ms / 0.3–1.3%, almost invisible |
| **snapshot attack surface** | Size magnitude the current implementation is well-tuned for |
| **Business coverage** (typical subscriber count for liquidation race) | Empirical experience: 10–50 high-value players; 64 leaves slack |

**64 is the product of leaving a safety margin under the strictest of these four constraints** — not an arithmetic wall, nor an arbitrary pick.

## 6. Upgrade Path

64 is the conservative launch value; it **should not be hard-coded**. The recommendation is to delegate to governance, with phased increases driven by testnet data:

| Phase | Trigger | `MAX_SYNC_FIRES_PER_TOPIC` |
|---|---|---|
| **Phase A (launch)** | — | 64 |
| **Phase B** | Testnet data: average handler cycles < 30K **and** propose/verify p99 additional latency under fully-loaded emit < 50ms | 128 |
| **Phase C** | Phase B stable for ≥ 1 month, no snapshot-subsystem edge cases, basefee behavior under fully-loaded emit conforms to EIP-1559 model expectations | 256 (practical ceiling) |

**Why 256 is the practical ceiling**:

- 65% lane-budget occupation is the boundary between "emitter can still do work" and "emitter is fully consumed by emit"
- Going further to 384 / 512, the emitter tx can only do emit under typical handler cost — the primitive degrades into an "event-broadcast-only tx", losing the ability to mix with other business logic
- Physical latency at 256 already accounts for 1–5% of a block; doubling again pushes toward 10%, near the consensus-latency-sensitive boundary

**Governance adjustment should preserve reversibility**: if after raising to 128 the actual data falls short (average handler cost exceeds 30K, p99 latency exceeds the threshold), governance should be able to revert to 64. The CIP-12 governance framework already supports hot parameter updates.

## 7. How the customer's "500 sync" demand is satisfied at the application layer

The customer's real need is "support 500+ subscribers", not "all 500 sync". This need **is already met** under the current tiered model:

- `MAX_SUBSCRIBERS_PER_TOPIC = 512`: the total mount cap is indeed 500+
- `MAX_SYNC_FIRES_PER_TOPIC = 64` (adjustable up to 256): bidding pays for rank in the sync segment
- Rank K+1 onward auto-defers, fires asynchronously at H+1

Three further escape valves at the application layer (CIP-29 §6.4):

1. **Topic bucketing**: `emit("liquidation:tier_1")` / `emit("liquidation:asset_eth")` splits a large topic into finer-grained ones
2. **Relay pattern**: 64 × 64 = 4096 end subscribers reachable synchronously
3. **Opt-in async**: register with `bid=0` to land in the async segment, avoiding the race for rank

**Combined with the Phase B/C raise to 256**, a single bucket after bucketing can reach 256 sync, and the Relay pattern can reach 256 × 256 = 65536 end subscribers synchronously — the "500+ subscribers" demand of nearly all business scenarios is amply covered.

## 8. Conclusion

| Question | Answer |
|---|---|
| Is 64 an arithmetic hard constraint? | No. 64 is the **conservative launch value** under the four constraints of lane budget / validator latency / snapshot attack surface / empirical business need |
| Is 256 achievable? | Yes, but it requires a governance raise driven by testnet data, and 256 is the **practical ceiling** (65% lane occupation) |
| Is 500 achievable? | **No**. Under typical handler cost, 28M > 22M lane budget — immediate OOG. Even with very light handlers, the basefee feedback would be violent, physical latency would consume 10% of block time, and the snapshot attack surface would be amplified 8× — all unacceptable costs |
| Is "spill to defer above 500" symmetric? | Not symmetric. Sync subs eat the emitter tx's lane budget; defer subs eat future blocks' overall budget. The **marginal costs are not equivalent**, so the sync segment and the defer segment cannot be simply swapped |

CIP-29 should define the semantics of `MAX_SYNC_FIRES_PER_TOPIC` as "**launch at 64, governance can raise to 256; 500 is outside the feasible region**", and write the upgrade path and criteria explicitly into the specification.

---

## Appendix A: Sources for the Cost Estimates

| Item | Source |
|---|---|
| User lane 22M cycles | The lane split in `node/execution/src/basefee.rs` + `BLOCK_CYCLES_TARGET = 10_000_000` |
| handler cycles 50K (typical) | Measured: the standard token actor's transfer handler is 30K ~ 80K cycles; median taken as 50K |
| handler cycles 10K (very light) | Measured: handlers doing only state read + single-field update |
| snapshot create/rollback ~1K | PVM benchmark `pvm/benches/pvm_cowboy.rs::interpreter_warmstart` (cf. the P2 perf-optimization in memory) |
| Physical latency 0.05–0.2 ms / sub | Measured samples from pvm-runtime during the PVM Performance Campaign (2026-03-31) |

## Appendix B: Relationship to CIP-3 Dual Basefee

Raising `MAX_SYNC_FIRES_PER_TOPIC` synchronously affects CIP-3's EIP-1559 basefee feedback loop — a larger sync segment means a single tx under fully-loaded emit consumes more cycles, pushing up this block's cycle consumption and triggering a basefee rise. This is in itself the intended market mechanism within CIP-3 design, but **the feedback strength is proportional to the cap size**. Before Phase B/C raises, governance should verify that basefee feedback behavior under the new cap still matches the expected slope (given in CIP-3 §2.4).

## Appendix C: Compatibility with the Phase 0 SDK Prototype

Phase 0 of CIP-29 §5.1 (pure SDK prototype, subscription table stored in the emitter's own actor storage) **is not constrained by `MAX_SYNC_FIRES_PER_TOPIC`** — the sync cap in Phase 0 is decided by the emitter contract itself and can mount arbitrarily many subscribers. All arguments in this document apply only to Phase 1+ protocol-level primitives. Validating Phase 0 against real workloads first and then deciding the concrete cap value for Phase 1+ is itself an additional data source for the upgrade path.
