# Hyperliquid: Component Decomposition and Cowboy Platform Mapping

**Date:** 2026-08-25
**Status:** Technical analysis
**Accompanying material:** `settlement_window_model.py` (executable model for §9)

---

## 1. Scope and summary

This document answers three questions:

1. What components does Hyperliquid consist of?
2. For each, which Cowboy component can host it?
3. Which parts Cowboy cannot provide at all?

**Method.** Hyperliquid is decomposed into nineteen components (§2), each annotated with
the platform property it depends on — that property, not the component's function, is what
determines whether a substitute exists. Each is then mapped onto a named Cowboy component
with its governing CIP (§4). Gaps are stated with citations and severity (§6), and the one
quantitative question the architecture turns on is computed rather than estimated (§9).

### Summary of findings

**One premise does not port, and everything follows from that.** Hyperliquid's defining
decision is to make consensus fast enough that the order book lives inside it — every
order, cancel and fill is a transaction. Cowboy's block time and throughput are three
orders of magnitude away from supporting that (§3), and no roadmap item closes the gap.
The correct response is not to attempt it.

**The rest of Hyperliquid maps cleanly.** With matching moved off-chain into a Runner,
order-level data into CBFS, order flow onto CBQS, and settlement, custody and governance
retained on chain, sixteen of the nineteen components have a home today or a named build
path (§4). The resulting system distributes across CBFS, CBQS, CBSS, Runners and the PVM
as peers, with the PVM holding custody rather than the hot path.

**Three gaps are load-bearing** (§6):

| Gap | Severity | Consequence |
|---|---|---|
| No resident Runner service (CIP-10 §16.2) | **Blocking** | A matching engine is persistent by definition; the container runtime is ephemeral. Blocks every always-on service, not just this one |
| No protocol-layer price oracle (CIP-2 §v3) | **Blocking for perpetuals** | Mark price and funding arrive on a job round trip rather than per block. Spot is unaffected |
| Sequencer fairness is a trust assumption | **Disclose** | Order priority is asserted by a bonded operator, not proven by consensus. This is the one place the design is structurally weaker than Hyperliquid |

**Settlement is not the constraint anyone expects it to be.** Computed against the gas
model rather than the transaction-rate figure, per-block settlement sustains 884–7,386
fills/sec depending on encoding — one to two orders of magnitude above a large venue's
actual volume. The settlement window should be one block, and the parameter needs a
default rather than tuning (§9). Time to finality is dominated by the dispute window, not
by settlement.

---

## 2. Hyperliquid, decomposed

Nineteen components in six groups. The right-hand column is the operative one: it names
the property the component *depends on*, which determines whether a Cowboy component can
substitute for it.

> Hyperliquid details are drawn from public documentation and should be read as
> structure-accurate and order-of-magnitude accurate rather than as pinned figures. No
> conclusion below turns on a specific value; §3 is a three-orders-of-magnitude argument
> that survives being wrong by one.

### 2.1 Consensus and execution

| # | Component | Function | Depends on |
|---|-----------|----------|------------|
| 1 | **HyperBFT** | HotStuff-derived BFT consensus, purpose-built in Rust for order flow. Publicly cited at sub-second finality and ~10⁵ orders/sec. | Consensus itself being fast enough to serve as the matching engine's sequencer |
| 2 | **HyperCore** | The state machine: perpetuals and spot, order books, margin, liquidation, funding. Every order, cancel and fill **is a transaction**. | #1. Without it the design is not possible |
| 3 | **HyperEVM** | General-purpose EVM execution sharing the same consensus. Dual-block (small/fast, large/slow). Reads Core through precompiles, writes Core through CoreWriter. | Shared consensus with #2, making Core state synchronously readable |

### 2.2 Market mechanics

| # | Component | Function | Depends on |
|---|-----------|----------|------------|
| 4 | **CLOB / matching engine** | Price-time priority order book per market. | #1 for ordering; an in-memory book with continuous residency |
| 5 | **Margin engine** | Cross and isolated margin, leverage tiers, maintenance margin. | Synchronous reads of #4's fills |
| 6 | **Liquidation engine** | Detects margin breach and liquidates into the backstop. | Same-block reaction to a price move |
| 7 | **Funding rate** | Periodic perpetual funding from the mark-to-index premium. | #8 and a reliable clock |
| 8 | **Oracle** | Validators publish per-market spot prices, aggregated by weighted median into mark price and the funding index. | The validator set serving as the oracle committee — the oracle is *inside* consensus |

### 2.3 Liquidity and products

| # | Component | Function | Depends on |
|---|-----------|----------|------------|
| 9 | **HLP** | Protocol vault: community deposits fund market making and act as the liquidation backstop; PnL is shared pro rata. | Ordinary program logic plus #6 |
| 10 | **Vaults** | Leader-operated vaults with depositor profit share. | Ordinary program logic |
| 11 | **HIP-1** | Spot token standard with a Dutch auction for ticker deployment. | Ordinary program logic |
| 12 | **HIP-2 (Hyperliquidity)** | Automated on-chain liquidity strategy for spot markets. | Per-block execution without a keeper |
| 13 | **HIP-3** | Builder-deployed perpetual markets — permissionless market creation against a stake. | A staking and slashing registry |

### 2.4 Access and distribution

| # | Component | Function | Depends on |
|---|-----------|----------|------------|
| 14 | **API / WebSocket nodes** | Non-validating nodes serving book snapshots, fills and user state. | Following the chain cheaply |
| 15 | **Builder codes** | Front ends attach a code and receive a share of fees. | Fee-split accounting at settlement |
| 16 | **Front end** | The trading application. | #14 |

### 2.5 Assets and bridging

| # | Component | Function | Depends on |
|---|-----------|----------|------------|
| 17 | **USDC bridge** | Validator-signed bridge from Arbitrum with a dispute window. | The validator set serving as the bridge committee |
| 18 | **HYPE staking, delegation, assistance fund** | Validator economics and buyback. | Ordinary chain economics |

### 2.6 Data

| # | Component | Function | Depends on |
|---|-----------|----------|------------|
| 19 | **Historical / L4 data** | Order-level historical dumps and node data streams. | The chain already holding every order |

---

## 3. The architectural premise that does not port

Components #1 and #2 are a single design decision: *make consensus fast enough that the
order book can live inside it*. Everything distinctive about Hyperliquid descends from it.
It is also the one property Cowboy cannot reproduce, and the gap is structural rather than
a matter of tuning.

| | Hyperliquid | Cowboy |
|---|---|---|
| Block / slot time | Sub-second, purpose-built | **~1 s** (WP-v2 §6.1 / §13; CIP-11 r1.2 and CIP-23 r1 are both calibrated to it) |
| Unit of work | One order, cancel or fill = one transaction | One actor call ≈ 50k cycles |
| Observed throughput | ~10⁵ orders/sec (public claim) | **50–150 TPS measured, ~500 TPS theoretical ceiling**; devnet benchmark peak 457 tx/block (2026-03-31) |
| After the full throughput roadmap | — | 1,000–3,000 TPS, conflict-rate dependent |

Three orders of magnitude, and the roadmap's own best case closes less than one of them.
Reproducing HyperCore's on-chain matching is therefore out of scope by construction, not
by preference.

What follows is the architecture in §5: matching moves off-chain into a Runner, order-level
data into CBFS, order flow onto CBQS, and the chain retains what genuinely requires
consensus — ownership, fee schedules, and the authority to change them.

---

## 4. Component mapping

Three verdicts. **Have** = a Cowboy component covers it today at specification level.
**Buildable** = it maps onto an existing component with real, named work. **No home** = §6.

### 4.1 Have

| Hyperliquid component | Cowboy component | CIP | Note |
|---|---|---|---|
| #4 matching engine | **Runner** workload, off-chain | CIP-2 | Not PVM-hosted. Residency constraint in §6.1 |
| #19 L4 / historical data | **CBFS** volume, erasure-coded, `manifest_root` committed on chain | CIP-9 (v2.r2), CIP-31 | Append-only market data is close to CBFS's best case |
| Order flow in, fills out | **CBQS** stream, one lane per market | CIP-39 v2 | Ordered, at-least-once, replayable — the shape of an order-entry bus. Caveats in §6.4 and §6.5 |
| #14 API / WebSocket | **CBQS** push delivery, plus `GET_STATE` for verified reads | CIP-39, CIP-17 | CIP-17 lets a front end verify a balance against `state_root` rather than trusting a single Runner |
| #9 HLP, #10 vaults | **PVM actor** | CIP-20 | Custody, share accounting and PnL split — low frequency, high value. This is the PVM's correct role |
| #7 funding settlement | **CIP-5 timer** at a fixed height cadence | CIP-5 | Height-triggered, explicit `fee_payer`, self-terminating. No keeper dependency |
| #6 liquidation reaction | **CIP-29 event hooks** | CIP-29 | CIP-29's primary use case is pre-liquidation: subscribers receive a same-transaction synchronous reaction window before liquidation executes. Stronger than the equivalent elsewhere |
| #15 builder codes | `SettlementConfig` fee split at `0x09`, or PaymentGate | CIP-3, CIP-18 | `UpdateSettlementConfig` already carries a `target_pool` discriminant |
| #18 staking, delegation | Validator staking plus Runner delegation | CIP-13 | `effective_stake = registration.stake + delegation_totals.total_active` |
| Exchange-side secrets | **CBSS** | CIP-24 | Signing keys and third-party credentials released t-of-n at job time. Plaintext never on chain and never exposed to validators |
| Matcher integrity attestation | **CIP-23** composite attestation | CIP-23 | Optional; the substantive answer to matcher trust, bounded as described in §6.3 |

The resulting allocation puts CBFS, CBQS, CBSS, Runners and the PVM on equal footing, with
the PVM holding custody rather than the hot path.

### 4.2 Buildable, with the work named

| Hyperliquid component | Cowboy component | Work required |
|---|---|---|
| #5 margin engine | Split: hot margin check in the Runner, settled margin state in an actor | Netting design — the chain observes position deltas per settlement window rather than per fill. Sized in §9 |
| #2 HyperCore settlement state | Actor state plus CIP-20 balances | CIP-20 provides spot fungible tokens with `u128` amounts. Perpetual positions, leverage and maintenance margin are application-level actor code; no native primitive exists |
| #13 HIP-3 builder markets | Actor registry modelled on the Runner Registry | Stake formula and slashing conditions. `max(10,000 CBY, 1.5 × declared_max_job_value)` is a usable template |
| #11 HIP-1 ticker auction | Actor | Previously CIP-22's scope — see §7 |
| #12 HIP-2 automated liquidity | Actor plus CIP-5 timer | Previously CIP-21's scope — see §7 |
| #17 USDC bridge | CIP-25 L1 anchoring → L2 messaging → L3 bridge | CIP-25 specifies a three-layer architecture with pluggable trust backends; no backend is deployed |
| #3 HyperEVM | Not applicable | Cowboy's general-purpose execution layer is the PVM. There is no second execution environment to reconcile, which removes the entire class of Core-to-EVM synchronisation problems that precompiles and CoreWriter exist to solve. A simplification rather than a gap |

### 4.3 No home today

Components #1 and #8, and the residency property #4 depends on. See §6.

---

## 5. Reference architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  CHAIN  (consensus — governance & settlement plane)                 │
│                                                                     │
│   0x09 Governance ── fee schedule, market params, listing rules,    │
│                      SettlementConfig (builder-code split)          │
│   CIP-20 balances ── collateral custody, realised PnL               │
│   Vault actor     ── HLP / leader-vault share accounting  [PVM]     │
│   CIP-5 timer     ── funding settlement at a height cadence         │
│   CIP-29 hooks    ── pre-liquidation subscriber window              │
│   CBFS manifest_root ── commitment to the archived order log        │
│                                                                     │
│   ~1 s blocks. Observes settlement windows, never individual orders.│
└───────────────▲─────────────────────────────────┬───────────────────┘
      config,   │                                 │  settlement batch,
      grants,   │                                 │  margin deltas
      revocation│                                 ▼
┌───────────────┴─────────────────────────────────────────────────────┐
│  OFF-CHAIN  (data plane — serves while the chain is unreachable)    │
│                                                                     │
│   CBQS stream ── order entry in, fills + book deltas out            │
│      one lane per market; total order per stream = the sequencer    │
│                          │                                          │
│                          ▼                                          │
│   Runner ────── matching engine, in-memory book, hot margin check   │
│      CBSS releases its signing key t-of-n at start                  │
│      CIP-23 CAE attests the binary that is running                  │
│                          │                                          │
│                          ▼                                          │
│   CBFS volume ── append-only L4 order log, erasure-coded            │
│      root committed on chain each window ⇒ tamper-evident history   │
└─────────────────────────────────────────────────────────────────────┘
```

The chain does not sit in the order path. An order is accepted, matched and acknowledged
without an on-chain round trip; the chain learns of it subsequently, in aggregate, and
exercises authority through configuration and revocation rather than per-order approval.
This mirrors the decoupling CIP-39 v2 specifies for CBQS, applied one layer higher.

---

## 6. Capability gaps

Ordered by how hard each blocks. Each is cited.

### 6.1 No resident Runner service — **blocking**

> **Long-running services**: v1 containers are ephemeral (bounded by `max_duration_sec`).
> Persistent services (web servers, databases) that run indefinitely are a future CIP.
> CIP-5 timers can be used to re-dispatch periodic jobs.
> — CIP-10 §16.2, Explicitly Out of Scope

A matching engine is a persistent service by definition: it holds the book in memory and
must remain continuously resident. The CIP-2 / CIP-10 unit of work is a bounded job torn
down on completion. The suggested mitigation — re-dispatch on a timer — does not apply
here, since an exchange cannot rebuild its book from CBFS on every dispatch interval.

CIP-39's Background section describes Runners as executing "tasks and resident workloads"
outside consensus. That is not consistent with CIP-10 §16.2, and CIP-10 is the statement
matching the shipped container runtime. Establishing which is normative is a prerequisite
for this architecture — and, more broadly, for any always-on service on the platform.

### 6.2 No protocol-layer price oracle — **blocking for perpetuals**

> no consensus-layer oracle dependency is introduced in v3. A future CIP MAY re-peg once
> an oracle module exists.
> — CIP-2 v3

Hyperliquid's oracle (#8) sits inside consensus: validators publish, the protocol
aggregates. Cowboy has no equivalent module, and CIP-2 v3 declined to introduce one even
for its own stake floor. The available construction is a Runner job under
`VerificationMode::MajorityVote`, which delivers the mark price on a job round trip rather
than per block. Spot trading tolerates that; perpetual funding and liquidation thresholds
do not.

The only oracle-shaped native primitive on the platform is CIP-21's timer-driven TWAP,
which is affected by the retirement described in §7.

### 6.3 Sequencer fairness is a trust assumption, not a property — **disclosed**

Hyperliquid's answer to who determines order priority is that consensus does, and
manipulating it requires a stake-level attack. In this architecture, the party operating
the Runner observes order flow first. The available mitigations are all partial:

- `VerificationMode::Deterministic` requires a TEE **and** byte-identical results across
  Runners, which a latency-sensitive matcher will not produce;
- `MajorityVote` costs a round trip per decision;
- `EconomicBond` is a single trusted Runner backed by stake — the practical choice, but a
  bond rather than a proof.

CIP-23 composite attestation narrows this materially: it can prove *which binary* is
matching, though not that the binary observed orders in the sequence it reports.

**This is the one respect in which the architecture is structurally weaker than
Hyperliquid, and it should be represented as such rather than as an equivalent guarantee.**

### 6.4 CBQS providers carry no bond and cannot be reassigned — **blocking as specified**

> Out of scope, requiring a future CIP: […] provider reassignment, provider staking or
> slashing […]
> — CIP-39 §Goals

If a CBQS stream is the exchange's sequencer, its broker is a single unbonded party that
cannot be replaced without creating a new stream. For agent coordination — CBQS's design
target — this is a reasonable v2 scope decision. For order entry it is not. Either the
deferred CIP lands, or the matching Runner owns its own ingress and CBQS carries only
fan-out, at the cost of the per-market lane model.

### 6.5 At-least-once delivery; exactly-once is an explicit non-goal — **application work**

> Not goals: […] exactly-once application side effects […]
> — CIP-39 §Goals

A redelivered order must not become a second fill. This is standard idempotency-key work
at the application layer and is entirely tractable; it is recorded because it is
inexpensive when designed in and a correctness incident when discovered late.

Related: CBQS lanes share one stream's throughput, and a hot lane exerts back-pressure on
its siblings. A single market in disorderly conditions will degrade the others unless each
market is allocated its own stream.

### 6.6 No native perpetual or margin primitive — **expected, but must be costed**

CIP-20 provides spot fungible tokens with `u128` amounts and validation hooks. Positions,
leverage tiers, maintenance margin, funding accrual and socialised loss are all actor code
to be written. This is the normal division — Hyperliquid built the same logic into
HyperCore — but it should not be costed as already provided.

### 6.7 Sub-second user-visible finality — **partially recoverable**

Order acknowledgement is fast because it does not touch the chain. Settlement finality is
one block plus the settlement window plus the dispute window (§9.5). For a taker this is
comparable to a centralised venue; for any flow requiring finalised collateral before
acting it is not Hyperliquid-equivalent, and should be represented as a bounded window
rather than as parity.

---

## 7. Interaction with the CIP-21 / CIP-22 retirement

CIP-21 (DEX and Liquidity Pools) and CIP-22 (Continuous Clearing Auctions) are scheduled
for entry-point deactivation, with the implementation retained but unreachable. Two
consequences bear on this architecture; neither argues against the retirement.

1. **CIP-21's TWAP oracle is withdrawn with it.** CIP-21 §6.1 provides the platform's only
   oracle-shaped native primitive ("Native TWAP oracles via timers, no external keeper").
   Deactivating CIP-21 at the entry point makes §6.2 strictly worse, because the
   replacement architecture requires a mark price more than the AMM did. The oracle
   requirement should be explicitly reassigned rather than allowed to lapse with the CIP.
2. **HIP-1 and HIP-2 analogues lose their platform primitives.** CIP-22 supplied the
   continuous-clearing-auction machinery a ticker auction (#11) would use, and CIP-21 the
   automated-liquidity machinery HIP-2 (#12) would use. After deactivation both become
   ordinary actor code — acceptable, and arguably correct, but it moves them from
   *platform-provided* to *application-built* in any capability comparison.

The entry-point switch is the appropriate mechanism in both cases. Where a module has
broad internal coupling, gating its single entry point (registration, or listing) renders
the remainder unreachable without requiring removal.

---

## 8. Decisions required

Ordered by dependency.

1. **Resident Runner workloads** (§6.1). Nothing else in this document is deliverable until
   this is resolved, and it constrains far more than this use case. Is the CIP-39 / CIP-10
   inconsistency a specification defect or an undocumented capability?
2. **Ownership of the oracle requirement** (§6.2, §7.1) once CIP-21 is deactivated. A
   minimal `MajorityVote` price-feed job is a short build; a consensus-layer module is a
   CIP.
3. **Settlement encoding** (§9). The analysis is complete; what remains is adopting
   encoding B — positions represented as CIP-20 balances — or accepting the benchmark
   dependency that encoding A carries.
4. **CBQS as sequencer, or matcher-owned ingress** (§6.4). Determines whether the deferred
   provider-bond CIP is on the critical path.
5. **Representation of the trust model** (§6.3). The defensible claim is a
   Hyperliquid-shaped exchange with a bonded off-chain matcher and on-chain settlement,
   which is not the same claim as parity.

---

## 9. Settlement window sizing

The one quantity the architecture turns on. It is computable from the protocol's gas
constants, and the answer is that settlement should occur every block. Model and provenance
in the accompanying `settlement_window_model.py`.

All constants below are read from `node/types/src/constants.rs` and
`node/execution/src/gas.rs`.

### 9.1 What binds — cells, not cycles, and not transaction rate

The 50–150 TPS figure from §3 is the wrong instrument here. It counts *transactions*, and
a settlement batch covering 1,700 accounts is **one** transaction. The governing budget is
the per-block gas targets:

| Budget | Value | Nature |
|---|---|---|
| `BLOCK_CELLS_TARGET` | 4,000,000 / block | EIP-1559 target, no lane partition |
| `BLOCK_CYCLES_TARGET` | 20,000,000 / block | EIP-1559 target |
| `LANE_RUNNER_CYCLES` | 8,888,888 / block | **Hard cap** if settlement arrives as a job result |
| `LANE_USER_CYCLES` | 22,222,222 / block | **Hard cap** if the Runner submits it as a transaction |
| `MAX_BLOCK_TRANSACTIONS` | 5,000 | Not relevant — one transaction is sent |

The cell target is nominally soft. In steady state it is not. `BASEFEE_MAX_CHANGE_DENOM = 96`
means sustained above-target consumption compounds the basefee at +1.042% **per block**:

| Sustained above target for | Basefee multiplier |
|---|---|
| 1 minute | ×1.9 |
| 5 minutes | ×22.4 |
| 10 minutes | ×501.5 |

An exchange cannot operate above the cell target. **4M cells/block is a hard steady-state
budget**, of which only a fraction φ should be claimed — the chain has other users. φ = 0.5
is used below.

### 9.2 The encoding choice is worth 8.4×

How a settled account is represented determines nearly everything:

| | **A — position as actor state** | **B — position as a CIP-20 balance** |
|---|---|---|
| Settlement mechanism | PVM actor loop, one `storage_write` per account | Native `token_batch` system instruction |
| Cells / account | 64 calldata + **1,000 storage_write** + 64 transfer = **1,128** | 64 calldata + 64 transfer = **128** |
| Cycles / account | 3,700 | 1,500 |
| Accounts / block (φ = 0.5, USER lane) | **1,767** (cells-bound) | **14,771** (cycles-bound) |
| PVM interpretation | 1,767 interpreted loop iterations **per block** | None — the loop is native |

`storage_write_cells = 1_000` against `token_transfer_cells = 64` is a **15.6× penalty** for
touching actor state rather than platform token state. This is the largest single lever in
the design, and it points the same direction as the overall architecture: keep the PVM out
of the hot path. Encoding B is not a micro-optimisation — it eliminates the only component
whose wall-clock cost is unmeasured (§9.6).

### 9.3 Result: a one-block window

At W = 1 there is no netting to exploit — each fill touches two accounts, so chain load is
`2 × fills/sec`. Feasibility is a single division:

| Encoding / lane (φ = 0.5) | Accounts/block | Max sustained fills/sec | Fills/day |
|---|---|---|---|
| A — position-write, RUNNER or USER lane | 1,767 | **884** | 76,000,000 |
| B — token-only, RUNNER lane | 5,882 | **2,941** | 254,000,000 |
| B — token-only, USER lane | 14,771 | **7,386** | 638,000,000 |

For scale, a large perpetuals venue transacts on the order of 10⁶–10⁷ fills per day. **Even
encoding A exceeds that by an order of magnitude, at one-second settlement, using half the
block's cell budget.**

The netting analysis that motivates a longer window is therefore not engaged. Running it to
establish where it *would* engage — `B(W) = N·(1 − e^(−2FW/N))`, minimum feasible W:

| Active accounts | Fills/sec | Netting knee W\* | Min feasible W |
|---|---|---|---|
| 5,000 | 100 | 25 s | **1 block** |
| 5,000 | 5,000 | 0.5 s | **1 block** |
| 50,000 | 1,000 | 25 s | **1 block** |
| 50,000 | 5,000 | 5 s | **1 block** |
| 50,000 | 20,000 | 1.2 s | 4 blocks |

W leaves 1 only at 20,000 fills/sec — approximately 1.7 billion fills/day, not a scale
requiring design provision.

### 9.4 A one-block window is also risk-optimal, so no trade-off arises

The usual reason to lengthen a settlement window is throughput, which §9.3 removes.
Every other consideration points the same way:

- **In-flight exposure is linear in W.** If the matching Runner fails, W seconds of fills
  exist only in the CBQS stream and must be replayed. W = 1 minimises divergence between
  on-chain state and actual state.
- **Fixed cost per batch is negligible.** 6,564 cells and 65,500 cycles per settlement
  transaction — under 3% overhead on a 200-account batch, and it does not grow.
- **Netting yields nothing below the knee.** Below `N/(2F)` nearly every fill touches a
  fresh account, so a longer window batches the same number of entries and merely delays
  them.

The least expensive option and the safest option coincide. This parameter therefore
requires a default rather than tuning.

### 9.5 The dispute window, not the settlement window, governs finality

Time to final = settlement window + `DISPUTE_WINDOW_BLOCKS` (75):

| W | Time to final |
|---|---|
| 1 s | **76 s** |
| 15 s | 90 s |
| 60 s | 135 s |

At W = 1, **75 of the 76 seconds are the CIP-2 dispute window.** Reducing W from 60 to 1
recovers 59 seconds; the remaining 75 are not reachable by any settlement-window choice. If
76 seconds to finality is unacceptable for the product, the parameter to revisit is the
dispute window or the verification mode.

### 9.6 One quantity still requires measurement

The gas model charges 200 cycles for a `storage_write`, and this analysis assumed 2,000
cycles for an interpreted loop iteration. **Neither is a wall-clock measurement.** Encoding
A requires roughly 1,767 interpreted iterations and 1,767 `storage_set` host calls within a
single PVM invocation, every block, inside a one-second budget. The existing PVM benchmark
suite reports ~1.1 ms for `actor_dispatch` — a whole transaction including VM setup — which
does not characterise a tight 1,767-iteration host-call loop.

**Benchmark required before adopting encoding A:** one actor handler looping over
N ∈ {100, 500, 1000, 2000} entries, each performing one `storage_set`, measured end-to-end.
Pass condition: p99 below ~300 ms at N = 2000, leaving the remainder of the block available.

**Encoding B does not require this benchmark**, because `token_batch` executes natively.
That is the stronger argument for B, ahead of the 8.4× gas saving.

Two constraints on B to record now. `token_batch` **rejects hooked tokens**
(`TokenBatchHookedUnsupported`), so a collateral token carrying CIP-20 compliance hooks
cannot be batch-settled and would fall back to encoding A. And B's all-or-nothing contract
is enforced by simulating every leg before any write, which costs one balance read per
distinct account — inexpensive (`storage_read_cells = 0`) but not free in cycles.

### 9.7 Recommendation

1. **Settlement window = 1 block (1 s).** No netting, no batching delay, minimum in-flight
   exposure. Revisit only above ~7,000 fills/sec.
2. **Encode positions as CIP-20 balances (encoding B)** so settlement is a native
   `token_batch` rather than a PVM loop — 8.4× cheaper, and it removes the unmeasured
   wall-clock risk.
3. **Submit settlement as a user transaction** from the Runner's own account rather than as
   a job result: the USER lane provides 2.5× the cycles of the RUNNER lane, and under
   encoding B cycles are the binding constraint.
4. **Budget φ = 0.5 of the cell target** and alarm on sustained above-target consumption;
   §9.1 shows overrun becomes self-punishing within minutes.
5. **Address finality through the dispute window**, not the settlement window (§9.5).

---

## Appendix — coverage summary

| Group | Verdict |
|---|---|
| Consensus and execution (#1–3) | **Not ported, by construction.** HyperEVM is unnecessary; HyperBFT is out of reach; HyperCore is redistributed across Runner, CBQS, CBFS and the chain |
| Market mechanics (#4–8) | Matching, margin, liquidation and funding all have homes. **The oracle (#8) does not** |
| Liquidity and products (#9–13) | All application-level actor code. Loses the CIP-21 / CIP-22 primitives, but nothing structural |
| Access and distribution (#14–16) | Covered — CBQS push delivery with CIP-17 verified reads improves on a trusted API node |
| Assets and bridging (#17–18) | Staking covered; the bridge is CIP-25-shaped but undeployed |
| Data (#19) | **CBFS, cleanly.** The closest fit in the exercise |
