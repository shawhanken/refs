# node/bench Enhancement Plan for CIP-29 + Broader Performance Coverage

> 中文版见文末 [中文版方案](#中文版方案)。
>
> **Implementation status (updated 2026-05-19):**
> - **B0–B5 landed** on `feat/cip-29-implementation` (typecheck clean; not yet runtime-verified against a validator).
> - **B6 partially landed**: bench-side `cip29_metrics` reader wired into the
>   report (forward-compat); node-side counter instrumentation deferred to a
>   separate PR because threading `Arc<TxLifecycleMetrics>` into `pvm_host.rs`
>   execution paths and `event_fire.rs` requires touching several layers.
>   The bench's `cip29_metrics` block stays absent until the node patch lands.
> - **`defer_tx_user` workload dropped**: the current node exposes no user-facing
>   `defer_transaction` host API; the only outside-driven path that produces
>   defer txs is CIP-29's `emit_event`, already covered by `event_async_drain`
>   (B3). `defer_tx_user` would be a duplicate.
> - **Per-lane cycle telemetry**: no per-lane Prometheus counters exist
>   (`render_lane_table` in `node/rpc/src/metrics.rs` only logs to tracing).
>   `mixed_lane`'s report notes direct operators to the validator log's
>   `block_metrics_table` for lane breakdown. Real Prometheus gauges deferred
>   to a follow-up PR alongside B6.

## Context

`feat/cip-29-implementation` ships CIP-29 (on-chain event hooks) Phases 1–3:
host APIs, the bidding system actor, defer-tx async overflow, SDK decorators,
and a working `lending + 3 LPs` demo under `node/examples/cip29_liquidation/`.

The current bench harness at `node/bench/` evaluates the node on five axes —
`flood` (pure-transfer TPS), `latency` (P99 finality), `blocks` (block time),
`vm` (one math actor wall-clock), `resources` (CPU/RSS/IO). It has **no
coverage of CIP-29 primitives** and several broader gaps that limit how
comprehensively it can rate node performance:

- The only workload is point-to-point CBY transfers in the System lane.
  User-lane actor calls, runner jobs, timers, and defer-tx are not exercised.
- There is no scenario that exercises the PVM snapshot/rollback path — the
  exact mechanism CIP-29 sync fires rely on, and CIP-3's stress vector.
- No mixed-workload mode; lane isolation under contention is untested.
- The report schema is flat — adding CIP-29 metrics today would require
  schema churn.

Goal: make `node/bench/` (a) capable of measuring CIP-29 behavior end-to-end
from outside the node, and (b) substantially more representative of real
node workloads so its KPIs reflect what production tx mixes will see.

## Findings — current observable surface (verified against this branch)

### CIP-29 implementation that bench can reach

| Surface | Path | Notes |
|---|---|---|
| Protocol constants | `node/types/src/constants.rs:215-249` | `MAX_SUBSCRIBERS_PER_TOPIC=512`, `MAX_SYNC_FIRES_PER_TOPIC=64`, `MAX_EMITS_PER_TX=16`, `MAX_SYNC_FIRE_PER_TX=256`, `MAX_EVENT_PAYLOAD_BYTES=4096`, `ASYNC_FIRES_PER_DEFER_TX=64`, etc. |
| Storage prefixes | `node/storage/src/state_key.rs` | `EventSub=0x18`, `EventSubIndex=0x19` (note: differs from spec §2.2's 0x14/0x15) |
| System actor | `node/execution/src/execution/event_sub_system_actor.rs` | At address **`0x1D`** (spec §2.6 says `0x0A`); handlers `get_rank`, `get_topic_orderbook`, `get_min_bid_for_rank`, `update_bid`, `topup_subscription` |
| Async fire dispatch | `node/execution/src/execution/event_fire.rs` | Async batches ride existing defer-tx channel; `EVENT_FIRE_METADATA_TAG=0xE1` envelope; emits `cip29.async_fire` events from defer tx receipts |
| Sync fire emission | `node/execution/src/pvm_host.rs` (emit_event) | Emits `cip29.sync_fire` events in emitter tx receipt's `events` list |
| Receipt linkage | `node/storage/src/types.rs:654-703` (`TransactionReceipt`) | Parent emit tx has `deferred_tx_hashes: Vec<Sha256Digest>`; spec §3.2's `triggered_by_emit` is **not** materialized as a receipt field — must be reconstructed via parent→child traversal |
| RPC for sub state | `node/rpc/src/handlers/cbss.rs:1205-1255` | All `get_event_sub*` handlers are **stubs returning empty** — bench cannot read sub records via RPC directly |
| Indexer | `node/indexer/src/lib.rs:269-313` | EventSub methods are stubs; CIP-29 events are still indexed in the generic `actor_events` table and reachable via `/actor/{addr}/logs` |
| Prometheus | `node/rpc/src/metrics.rs` | No CIP-29 counters/histograms exported |
| Phase 3 demo | `node/examples/cip29_liquidation/{lending_protocol,liquidity_provider}.py + start_all.sh` | Working liquidation flow; parametrizable seed for bench scenarios |

### Bench-side surface (verified)

- `node/bench/src/cowboy/client.ts` — has `submitRaw`, `waitFinalized`, `getReceipt`, `getBlock`, `getBasefee`, `getNodeMetrics`, `getAccount`, `getHeight`. Receipts expose `events: [string, string][]` and `deferred_tx_hashes: string[]`.
- `node/bench/src/cowboy/tx.ts` — already has `buildTransferTx`, `buildActorDeployTx`, `buildActorExecuteTx`, `deriveActorAddress`. Sufficient for actor workloads.
- `node/bench/src/cowboy/flood.ts` — `SYSTEM_LANE_CAPACITY=2400` is hardcoded for transfer; the worker model is reusable, the cap and tx-builder are the only workload-coupled pieces.
- Report schema in `node/bench/src/cowboy/types.ts` (`BenchmarkReport`) is flat — fits an additive `events?: EventBenchReport` subsection without churn.

### General coverage gaps (not CIP-29 specific)

1. **No actor-call workload** — `flood` only sends `SystemInstruction::Transfer`. User-lane utilization, PVM warmup, ActorStorageCache thrash, batch-charged storage-read cycles, and `STORAGE_READ_CYCLES` are untouched. Direct relevance to CIP-29: sync fires *are* User-lane actor calls.
2. **No defer-tx workload** — the cross-block path (`defer transaction`) that CIP-29's async segment reuses is not exercised. No bench measures defer admission, H+1 carryover, lane-budget bleed.
3. **No PVM snapshot stress** — sync-fire fan-out is essentially "K serial snapshot/restore cycles inside one tx". CIP-29 §6.4 explicitly asks for this measurement before raising `MAX_SYNC_FIRES_PER_TOPIC` from 64→128→256.
4. **No mixed-workload / lane-contention mode** — saturating User + System + Timer lanes concurrently is the only way to validate lane isolation under stress.
5. **No state-growth probe** — repeated deploys and storage-write floods are not measured; QMDB merkleization cost under load is invisible.
6. **VM bench is degenerate** — one math actor, no cross-actor `call()`, no `send()`, no nested calls. Doesn't reflect real actor behavior.
7. **Basefee feedback** is sampled but never *driven* on the User/Timer lanes — only on System (via transfer flood). Cross-lane basefee tuning (CIP-3 §2.4) is untested.

## Proposed Approach — two parallel tracks, one shared scaffolding upgrade

### Shared upgrade — workload abstraction (Track 0, prerequisite)

Replace `flood.ts`'s hardcoded `buildTransferTx` with a `Workload` interface so
the worker model can be reused across workload types without forking the file:

```ts
// node/bench/src/cowboy/workloads/types.ts (new)
interface Workload {
    name: string;
    laneHint: 'system' | 'user' | 'timer' | 'mixed';
    laneCycleBudget: number;       // for capacity sizing
    /** Per-tx cycles estimate for inferring worker cap (lane_budget / per_tx_cycles). */
    perTxCyclesEstimate: number;
    buildTx(ctx: WorkloadContext): { raw: Uint8Array; hash: string };
    /** Called once after setup; deploys helper actors etc. Returns context shared by buildTx. */
    setup?(client: CowboyClient, keystore: Keystore, cfg: CowboyConfig): Promise<unknown>;
}
```

Then `runFloodTest` takes a `workload: Workload` parameter; the existing
transfer flood becomes `workloads/transfer.ts`. New workloads compose by
implementing `buildTx`. **No behavior change** to current `bench:flood`.

Files touched: `flood.ts` (parametrize), new `workloads/` subdir, `bench.ts`
(dispatch new subcommands), `types.ts` (no-op signature widening).

### Track A — CIP-29 bench coverage

Add **one new bench module** `events.ts` (analogous to `vm_path.ts`) plus four
**new Workload implementations** that plug into the shared scaffolding.

#### A.1 New module `events.ts` — CIP-29 scenario bench

`npm run bench:events config_cowboy.json` runs a sequence of self-contained
scenarios. Each scenario reuses the demo pattern (`lending_protocol.py` +
`liquidity_provider.py`) but is driven from TypeScript:

| Scenario | What it varies | Primary KPI |
|---|---|---|
| **S1: sync-only fan-out** | N subscribers ∈ {1, 8, 32, 64} all at `bid=0` | Per-fan-out wall ms, sync-fire count from receipt events |
| **S2: sync + async split** | N=200, top-64 bidders fire sync, 136 fall to async | Sync fan-out time vs H+1 async fire latency; defer-tx batching count (expect 3 defer txs of 64+64+8) |
| **S3: payload-size sweep** | payload ∈ {64, 512, 2048, 4096} B at N=32 | Cells charged to emitter; emit cycles/byte regression check |
| **S4: failure isolation** | M of N subscribers raise; verify others still fire | Failure isolation success rate (target 100%); cycles refunded vs consumed |
| **S5: bid market churn** | N=64, repeated `update_bid` calls, monitor rank changes | Burn rate (cycles burned per bid update); reorder cost |
| **S6: emit cap probes** | Push 1 tx to `MAX_EMITS_PER_TX=16` and total sync fires to `MAX_SYNC_FIRE_PER_TX=256` | Verify protocol rejection at cap+1; cycles consumed inside cap |
| **S7: zombie reap** | Pre-drain subs to <`MIN_FIRE_COST=5000`, then emit; observe reaping in next emit | Reaped sub count from sync-fire events; cells refunded to subscribers |

How each scenario observes results (since `/event_sub*` RPCs are stubs):

- **Sync fires**: parse the emitter tx receipt's `events` for `cip29.sync_fire` topic. Each entry's data payload encodes `(sub_id, status, cycles_used)` — read from `event_fire.rs` / `pvm_host.rs` exactly which encoding.
- **Async fires**: walk `parent_receipt.deferred_tx_hashes`, fetch each defer tx receipt, parse `cip29.async_fire` events (subscriber addr + sub_id, 53 bytes per spec).
- **Orderbook reads**: deploy a small `bench_event_probe.py` helper actor that wraps `runtime.call(EVENT_SUBSCRIPTION_SYSTEM_ACTOR, ...)` and returns the result; query it via `POST /actor/read` (read-only, no tx). This is the same pattern `start_all.sh` uses with `read_handler_field`.

New TypeScript files:
- `bench/src/cowboy/events.ts` — scenario driver
- `bench/src/cowboy/cip29_actors.ts` — embedded Python actor sources (lending, LP, probe — copy/adapt from the demo)
- `bench/src/cowboy/cip29_helpers.ts` — derive sub_id (keccak256 of emitter‖subscriber‖topic‖sub_height, see `node/storage/src/event_subs.rs`), parse fire-event payloads

#### A.2 New Workloads for `flood`

| Workload | What it does |
|---|---|
| `event_emit_flood` | Deploys 1 emitter + 32 LPs (all `bid=0`, sync-segment-fits); flood calls `check_liquidation` so every emit fires 32 handlers in the User lane. Measures sustained TPS under sync fan-out. |
| `event_async_drain` | Deploys 1 emitter + 200 LPs; flood emits at a slow rate but every emit creates 3 defer txs. Measures H+1 defer-tx admission and how the System lane absorbs async overflow under repeated emission. |

Run via `npm run bench:flood -- --workload event_emit_flood`.

#### A.3 Targeted snapshot stress (CIP-29 §6.4 prereq)

Standalone test `bench:snapshot-cost`: emits one tx with N sync subscribers at
N ∈ {1, 16, 32, 64, 128 (config override), 256 (config override)}, holding
handler cycles approximately constant; reports per-fire wall-time and the
critical-path tx wall-time. This is the data §6.4 says governance needs
before raising `MAX_SYNC_FIRES_PER_TOPIC`.

### Track B — General performance coverage (CIP-29-adjacent but independently valuable)

#### B.1 New Workloads (use shared scaffolding from Track 0)

| Workload | What it does | Why |
|---|---|---|
| `transfer` | Existing System-lane transfer (current `flood` behavior) | Backwards-compat default |
| `actor_call_user` | Deploys a "noop" actor (single state_get + state_set); flood invokes it | Stresses User lane, PVM warmup, ActorStorageCache, batch-charged storage reads |
| `actor_chain` | Actor A calls Actor B calls Actor C (3-hop synchronous `call()`) | Stresses `max_call_depth=32`, cross-actor dispatch — the same machinery CIP-29 sync fires use |
| `defer_tx_user` | Submits txs that schedule a `defer transaction` for H+k | Measures defer-tx admission gate, H+k overflow behavior |
| `mixed_lane` | Mix transfer + actor_call_user + defer_tx_user weighted N:M:K | Tests lane-isolation under contention; expected to show each lane independently saturating |
| `state_growth` | Sustained `state_set` writes of variable byte sizes | Stresses QMDB merkleization, cells-basefee feedback, ActorKvBytes quota |
| `deploy_burst` | Burst of N actor deploys (variable code sizes) | Captures deploy-path cost (compile, install, code-storage write) |

Each workload exposes its own `--workload <name>` flag, runs through the existing
flood worker pool, and produces the same flood report fields plus its own
workload-specific sub-section.

#### B.2 Report schema additions (`types.ts`)

Add three additive subsections (no breaking change):

```ts
events?: {
  scenarios: Array<{
    name: string;
    workload: string;
    n_subs_total: number;
    n_subs_sync: number;
    n_subs_async: number;
    payload_bytes: number;
    emit_count: number;
    emit_wall_ms_p50: number;
    emit_wall_ms_p99: number;
    sync_fires_observed: number;
    async_fires_observed: number;
    defer_txs_produced: number;
    cells_billed_to_emitter: number;
    cycles_burned_via_bid: number;
    failure_isolation_ok: boolean;          // S4
    rejected_at_cap: boolean | null;        // S6
    notes: string[];
  }>;
};

snapshot_cost?: {
  per_fire_us: Array<{ n_subs: number; p50_us: number; p99_us: number }>;
  emit_wall_ms: Array<{ n_subs: number; p50_ms: number; p99_ms: number }>;
};

workload?: {
  name: string;                              // which Workload ran
  lane: 'system' | 'user' | 'timer' | 'mixed';
  per_tx_cycles_observed_p50: number;        // from receipts
  per_tx_cells_observed_p50: number;
  lane_basefee_change_pct: number | null;    // narrower than basefee_summary
};
```

`flood_test.workload` already exists as a string — extend `report.ts` to
populate `workload` subsection from receipt cycles/cells aggregation.

#### B.3 Config additions (`config_cowboy.json`)

Append optional fields; current behavior unchanged when absent:

```jsonc
"workload": "transfer",                  // existing default
"eventScenarios": ["S1","S2","S3","S4","S5","S6","S7"],  // bench:events filter
"eventBidDistribution": "zero|uniform|exponential",
"eventPayloadSizesBytes": [64, 512, 2048, 4096],
"snapshotCostNSubs": [1, 16, 32, 64],    // 128/256 require const override
"mixedLaneWeights": { "transfer": 50, "actor_call_user": 40, "defer_tx_user": 10 }
```

### Track C — Node-side observability (small but high-leverage)

Adding three Prometheus counters in `node/rpc/src/metrics.rs` would let the
bench correlate scenarios with internal state instead of inferring from
receipts. **Out of bench scope** but recommended; if approved, bench reads
them via existing `client.getNodeMetrics()`:

- `cip29_emits_total` (counter, labels: `result=ok|rejected_cap|rejected_payload|rejected_depth`)
- `cip29_fires_total` (counter, labels: `mode=sync|async`, `status=ok|err|zombie`)
- `cip29_subscribers_gauge` (gauge per emitter — too high-cardinality at scale; alternative: single global gauge plus a per-topic histogram bucket)

This is the only Track that requires non-bench code changes. Implementable
later — bench works without it via receipt parsing.

## Phased Delivery

Aligned with CIP-29's own Phase 1/2/3 boundaries so each bench phase ships
alongside the protocol capability it measures.

| Phase | Bench deliverable | Depends on | Effort |
|---|---|---|---|
| **B0** | Track 0 workload abstraction; `transfer` workload extracted; **no behavior change** | — | 0.5–1 day |
| **B1** | Track B Workloads: `actor_call_user`, `actor_chain`, `state_growth`, `deploy_burst`; corresponding report subsection | CIP-29 Phase 1 (registry) — no, this is general | 2–3 days |
| **B2** | Track A: `events.ts` scenarios S1, S3, S4 (sync-only); `event_emit_flood` workload | CIP-29 Phase 2 ✅ already in branch | 2–3 days |
| **B3** | Track A: S2, S6, S7 (async + caps); `event_async_drain` workload; `snapshot-cost` standalone | CIP-29 Phase 2 ✅ | 2 days |
| **B4** | Track B: `defer_tx_user`, `mixed_lane` workloads; lane-isolation report | — | 2 days |
| **B5** (optional) | Track A: S5 (bid market) + bidding orderbook helper actor | Phase 3 SDK ✅ in branch | 1 day |
| **B6** (optional) | Track C node metrics + bench wiring | needs node PR | 1 day |

B0 must land first since every other phase depends on the parametrized
workload interface. B1 and B2 are independent and parallelizable.

## Critical files to modify

| File | Phase | Change |
|---|---|---|
| `node/bench/src/cowboy/flood.ts` | B0 | Parametrize on `Workload`; extract transfer hardcoding to `workloads/transfer.ts` |
| `node/bench/src/cowboy/workloads/types.ts` | B0 | **new** — `Workload` interface |
| `node/bench/src/cowboy/workloads/transfer.ts` | B0 | **new** — extracted current behavior |
| `node/bench/src/cowboy/workloads/actor_call_user.ts` | B1 | **new** |
| `node/bench/src/cowboy/workloads/actor_chain.ts` | B1 | **new** |
| `node/bench/src/cowboy/workloads/state_growth.ts` | B1 | **new** |
| `node/bench/src/cowboy/workloads/deploy_burst.ts` | B1 | **new** |
| `node/bench/src/cowboy/workloads/event_emit_flood.ts` | B2 | **new** |
| `node/bench/src/cowboy/workloads/event_async_drain.ts` | B3 | **new** |
| `node/bench/src/cowboy/workloads/defer_tx_user.ts` | B4 | **new** |
| `node/bench/src/cowboy/workloads/mixed_lane.ts` | B4 | **new** |
| `node/bench/src/cowboy/events.ts` | B2/B3/B5 | **new** — scenario driver |
| `node/bench/src/cowboy/cip29_actors.ts` | B2 | **new** — embedded Python sources, copy/adapt from `node/examples/cip29_liquidation/` |
| `node/bench/src/cowboy/cip29_helpers.ts` | B2 | **new** — sub_id derivation, fire-event payload parser |
| `node/bench/src/cowboy/bench.ts` | B0–B5 | Dispatch new subcommands `events`, `snapshot-cost`; pass `--workload` flag through |
| `node/bench/src/cowboy/types.ts` | B0–B4 | Additive `events`, `snapshot_cost`, `workload` report subsections |
| `node/bench/src/cowboy/report.ts` | B0–B4 | Aggregate the new subsections; print summary tables |
| `node/bench/config_cowboy.json` | B0+ | Append optional workload/eventScenarios fields |
| `node/bench/package.json` | B0+ | Add `bench:events`, `bench:snapshot-cost` scripts |
| `node/bench/README.md` | B0+ | Document new commands |

### Reusable utilities already in the repo

- Subscription record codec — `node/storage/src/event_subs.rs` (read for sub_id format)
- Phase 3 actor sources — `node/examples/cip29_liquidation/lending_protocol.py` + `liquidity_provider.py` (copy into `cip29_actors.ts` as constants)
- `start_all.sh`'s `read_handler_field` pattern via `POST /actor/read` — for reading helper-actor return bytes from bench
- Existing `buildActorDeployTx` / `buildActorExecuteTx` in `node/bench/src/cowboy/tx.ts` — covers all needed tx kinds
- `LatencyTracker` and `ErrorCounter` in `metrics.ts` — reusable
- `nodeMetricsSnapshot` plumbing in `flood.ts` — extends naturally to new workloads

## Verification

End-to-end checks per phase, all runnable locally against `start_validator.sh`:

**B0** (transfer extracted to workload, no behavior change):
- `npm run bench:flood` baseline output matches pre-change report on key fields (`peak_tps`, `sustained_confirmed_tps_mid80`, `total_confirmed`). Diff JSON reports.

**B1** (new general workloads):
- `npm run bench:flood -- --workload actor_call_user` runs ≥120s; receipts show non-zero `cycles_used` per tx; flood report's `workload` subsection populated.
- `npm run bench:flood -- --workload state_growth` shows cells-basefee rising over the run (cross-checks CIP-3 §2.4).

**B2/B3** (CIP-29 scenarios):
- `npm run bench:events` produces a report whose `events.scenarios` array has entries for S1/S2/S3/S4/S6/S7.
- S1@N=64: `sync_fires_observed == 64`, `async_fires_observed == 0`, `defer_txs_produced == 0`.
- S2@N=200: `sync_fires_observed == 64`, `async_fires_observed == 136`, `defer_txs_produced == 3`.
- S4: `failure_isolation_ok == true` despite half the LPs raising.
- S6: emitter tx submitted with `MAX_EMITS_PER_TX+1=17` emits returns `rejected_at_cap=true`.
- Cross-check: each async-fire receipt's parent tx hash is reachable via `parent_receipt.deferred_tx_hashes` ← back-pointer integrity.

**Snapshot-cost** (B3):
- `npm run bench:snapshot-cost` writes a `snapshot_cost.per_fire_us` curve with at least N ∈ {1, 16, 32, 64}; emit wall time should scale roughly linearly with N for fixed handler cost — establishes the CIP-29 §6.4 baseline.

**B4** (defer + mixed):
- `--workload mixed_lane` with weights 50/40/10: each lane's per-block cycle usage observable from `nodeMetricsSnapshot`; no lane starves the others (lane-isolation invariant).

**Reports**: open the generated `cowboy-bench-*.json`, confirm additive
sections appear and existing fields are byte-identical to pre-change runs
for the `transfer` workload.

## Out of scope (explicitly)

- Multi-validator stress: bench drives a single local validator. Distributed scenarios are deferred.
- Indexer query path: bench will keep parsing receipts directly until `node/indexer/src/lib.rs:269-313` stubs are replaced.
- Cross-chain / bridge benchmarks.
- WindTunnel multi-chain comparison code under `node/bench/test/`, `node/bench/scripts/visualize.mjs` (the dashboard layer is unchanged; new fields appear in raw JSON for now).

---

## 中文版方案

# node/bench 增强方案 — CIP-29 + 更全面的性能评估

> 文件位置说明：Plan 模式只允许编辑本文件。原始请求要求方案放在
> `/home/ubuntu/workspace/refs/plans/` 下。批准后请将此文件另存为
> 例如 `/home/ubuntu/workspace/refs/plans/2026-05-19_bench-cip29-and-perf-coverage.md`。

## 背景

`feat/cip-29-implementation` 分支已交付 CIP-29（链上事件钩子）Phase 1–3：
host API、竞价系统 Actor、defer-tx 异步溢出通道、SDK 装饰器，
以及一个可跑通的 `lending + 3 LP` 演示（`node/examples/cip29_liquidation/`）。

当前 `node/bench/` 共有 5 个维度的评估模块：`flood`（纯转账 TPS）、
`latency`（P99 最终确认）、`blocks`（出块时间）、`vm`（一个 math actor 的
墙钟）、`resources`（CPU/RSS/IO）。它**完全没有 CIP-29 相关覆盖**，
而且作为综合性能评估存在若干基础短板，限制了它对 cowboy node 的真实代表性：

- 唯一的负载是 System lane 的点对点 CBY 转账。User lane actor 调用、
  Runner job、Timer、defer-tx 全部未覆盖。
- 没有任何场景触发 PVM 的 snapshot/rollback——而这恰恰是 CIP-29 同步
  fire 的核心机制，也是 CIP-3 着重的压测向量。
- 没有混合负载模式；contention 下 lane 隔离性未验证。
- 报告结构是扁平的——现在补 CIP-29 字段会引起 schema 抖动。

目标：让 `node/bench/` 同时具备 (a) 从节点外端到端度量 CIP-29 行为
的能力，(b) 对真实生产 tx 组合更具代表性的负载覆盖，KPI 更能反映
线上情况。

## 调研结论 —— bench 当前可触达的可观测面（基于本分支已核对）

### CIP-29 实现侧可被 bench 利用的接口

| 接口 | 路径 | 备注 |
|---|---|---|
| 协议常量 | `node/types/src/constants.rs:215-249` | `MAX_SUBSCRIBERS_PER_TOPIC=512`、`MAX_SYNC_FIRES_PER_TOPIC=64`、`MAX_EMITS_PER_TX=16`、`MAX_SYNC_FIRE_PER_TX=256`、`MAX_EVENT_PAYLOAD_BYTES=4096`、`ASYNC_FIRES_PER_DEFER_TX=64` 等 |
| 存储前缀 | `node/storage/src/state_key.rs` | `EventSub=0x18`、`EventSubIndex=0x19`（**与 CIP 文档 §2.2 的 0x14/0x15 不一致**） |
| 系统 Actor | `node/execution/src/execution/event_sub_system_actor.rs` | 地址实际是 **`0x1D`**（**CIP §2.6 文档为 `0x0A`**）；handler：`get_rank`、`get_topic_orderbook`、`get_min_bid_for_rank`、`update_bid`、`topup_subscription` |
| 异步 fire 派发 | `node/execution/src/execution/event_fire.rs` | 异步段复用现有 defer-tx 通道；`EVENT_FIRE_METADATA_TAG=0xE1` 信封；defer tx 回执包含 `cip29.async_fire` 事件 |
| 同步 fire 触发 | `node/execution/src/pvm_host.rs`（emit_event） | 在 emitter tx 回执的 `events` 列表中写入 `cip29.sync_fire` 事件 |
| 回执因果 | `node/storage/src/types.rs:654-703`（`TransactionReceipt`） | 父 emit tx 含 `deferred_tx_hashes: Vec<Sha256Digest>`；**CIP §3.2 的 `triggered_by_emit` 字段未物化**——需通过父→子回溯重建 |
| 订阅状态 RPC | `node/rpc/src/handlers/cbss.rs:1205-1255` | 所有 `get_event_sub*` handler 都是**返回空的桩**——bench 不能直接通过 RPC 读订阅记录 |
| Indexer | `node/indexer/src/lib.rs:269-313` | EventSub 方法是桩；但 CIP-29 事件本身会进入通用 `actor_events` 表，可通过 `/actor/{addr}/logs` 查询 |
| Prometheus | `node/rpc/src/metrics.rs` | 无 CIP-29 相关计数器或直方图 |
| Phase 3 演示 | `node/examples/cip29_liquidation/{lending_protocol,liquidity_provider}.py + start_all.sh` | 可工作的清算流程；可作为 bench 场景的参数化种子 |

### bench 现状（已核对）

- `node/bench/src/cowboy/client.ts` — 已有 `submitRaw`、`waitFinalized`、`getReceipt`、`getBlock`、`getBasefee`、`getNodeMetrics`、`getAccount`、`getHeight`。回执暴露 `events: [string, string][]` 和 `deferred_tx_hashes: string[]`。
- `node/bench/src/cowboy/tx.ts` — 已有 `buildTransferTx`、`buildActorDeployTx`、`buildActorExecuteTx`、`deriveActorAddress`，对 actor 负载够用。
- `node/bench/src/cowboy/flood.ts` — `SYSTEM_LANE_CAPACITY=2400` 硬编码到转账上；worker 模型可复用，与负载耦合的只有这条上限和 tx builder。
- `node/bench/src/cowboy/types.ts` 的 `BenchmarkReport` 是扁平结构 —— 加 `events?: EventBenchReport` 这种增量子段不会破坏既有字段。

### 与 CIP-29 无关但同样存在的覆盖缺口

1. **没有 actor 调用类负载** —— `flood` 只发 `SystemInstruction::Transfer`。User lane 占用、PVM 预热、ActorStorageCache 抖动、批量结算的存储读 cycle、`STORAGE_READ_CYCLES` 全没碰到。这与 CIP-29 直接相关：同步 fire 本身就是 User lane 上的 actor 调用。
2. **没有 defer-tx 负载** —— CIP-29 异步段复用的跨块路径（defer transaction）从未压过：admission 门控、H+1 携带溢出、lane 预算渗漏等都看不到。
3. **没有 PVM snapshot 压测** —— 同步 fan-out 本质是"一次 tx 内 K 次顺序 snapshot/restore"。CIP-29 §6.4 明确要求在把 `MAX_SYNC_FIRES_PER_TOPIC` 从 64→128→256 提升前先有这条数据。
4. **没有混合负载 / lane 竞争模式** —— 同时打满 User+System+Timer 才能验证 lane 隔离性。
5. **没有状态膨胀探针** —— 连续 deploy、连续 storage write 没有度量；QMDB merkleize 在负载下的开销不可见。
6. **VM bench 太单薄** —— 一个 math actor，无跨 actor `call()`、无 `send()`、无嵌套调用，不代表真实 actor 行为。
7. **basefee 反馈**采样了但**没在 User/Timer lane 主动驱动**——只在 System lane（转账 flood）驱动。CIP-3 §2.4 的跨 lane basefee 调节未验证。

## 方案 —— 两条并行 Track + 一处共享脚手架升级

### 共享升级 — Workload 抽象（Track 0，前置）

把 `flood.ts` 里硬编码的 `buildTransferTx` 替换为 `Workload` 接口，使
worker 模型可在不同负载类型间复用而不需要 fork 文件：

```ts
// node/bench/src/cowboy/workloads/types.ts （新文件）
interface Workload {
    name: string;
    laneHint: 'system' | 'user' | 'timer' | 'mixed';
    laneCycleBudget: number;       // 用于推算 worker 上限
    /** 每 tx 大致 cycles 数，用来推 worker cap = lane_budget / per_tx_cycles。 */
    perTxCyclesEstimate: number;
    buildTx(ctx: WorkloadContext): { raw: Uint8Array; hash: string };
    /** 在 setup 之后调用一次，部署辅助 actor 等；返回值会作为 buildTx 的上下文。 */
    setup?(client: CowboyClient, keystore: Keystore, cfg: CowboyConfig): Promise<unknown>;
}
```

`runFloodTest` 接收 `workload: Workload`；现在的转账 flood 提取为
`workloads/transfer.ts`。新负载只需实现 `buildTx`。**对现有
`bench:flood` 行为零影响**。

涉及文件：`flood.ts`（参数化）、新增 `workloads/` 子目录、`bench.ts`
（路由新子命令）、`types.ts`（签名扩宽，no-op）。

### Track A — CIP-29 覆盖

新增一个 bench 模块 `events.ts`（仿照 `vm_path.ts`），并提供 4 个
插入共享脚手架的新 **Workload** 实现。

#### A.1 新模块 `events.ts` —— CIP-29 场景化 bench

`npm run bench:events config_cowboy.json` 跑一组自包含场景。每个场景
复用演示拓扑（`lending_protocol.py` + `liquidity_provider.py`），但从
TypeScript 端驱动：

| 场景 | 变量 | 主 KPI |
|---|---|---|
| **S1: 纯同步 fan-out** | 订阅者数 N ∈ {1, 8, 32, 64}，所有 `bid=0` | 单次 fan-out 墙钟 ms、回执中的同步 fire 计数 |
| **S2: 同步+异步拆分** | N=200，前 64 名投标者走同步，剩 136 进异步 | 同步 fan-out 时延 vs H+1 异步 fire 时延；defer-tx 批次数（应为 3：64+64+8） |
| **S3: 载荷大小扫描** | N=32 时 payload ∈ {64, 512, 2048, 4096} 字节 | 计入 emitter 的 cells；emit cycles/byte 回归检查 |
| **S4: 失败隔离** | N 个订阅者中 M 个抛错，验证其余照常 fire | 失败隔离成功率（目标 100%）；refund vs consumed |
| **S5: 竞价市场抖动** | N=64，重复 `update_bid`，监测排名变化 | 单次 bid bump 的销毁速率；重排成本 |
| **S6: emit 上限探测** | 单 tx 中触发 `MAX_EMITS_PER_TX=16` 和总 sync fire `MAX_SYNC_FIRE_PER_TX=256` | 协议在 cap+1 拒绝；cap 之内的 cycles 消耗 |
| **S7: 僵尸订阅回收** | 先把 sub 的 `gas_remaining` 耗到 `<MIN_FIRE_COST=5000`，再触发 emit | 同步 fire 事件中的回收数；返还给 subscriber 的 cells |

由于 `/event_sub*` 是桩，每个场景的观测路径：

- **同步 fire**：解析 emitter tx 回执 `events` 中的 `cip29.sync_fire`。数据 payload 编码为 `(sub_id, status, cycles_used)`——按 `event_fire.rs` / `pvm_host.rs` 实际编码读取。
- **异步 fire**：沿 `parent_receipt.deferred_tx_hashes` 取每个 defer tx 回执，解析其中 `cip29.async_fire` 事件（per CIP §3.2 是 subscriber 地址 + sub_id 共 53 字节）。
- **Orderbook 读**：部署一个小 `bench_event_probe.py` 助手 actor，包装 `runtime.call(EVENT_SUBSCRIPTION_SYSTEM_ACTOR, ...)` 并把结果返回；通过 `POST /actor/read`（只读，无 tx）查询——和 `start_all.sh` 里 `read_handler_field` 一样的模式。

新增 TypeScript 文件：
- `bench/src/cowboy/events.ts` —— 场景驱动器
- `bench/src/cowboy/cip29_actors.ts` —— 内嵌 Python actor 源（lending、LP、probe，从演示移植）
- `bench/src/cowboy/cip29_helpers.ts` —— `sub_id` 推导（按 `node/storage/src/event_subs.rs` 中 keccak256(emitter‖subscriber‖topic‖sub_height)）、fire 事件 payload 解析

#### A.2 给 `flood` 加的 CIP-29 Workload

| Workload | 行为 |
|---|---|
| `event_emit_flood` | 部署 1 个 emitter + 32 个 LP（全部 `bid=0`，可装进同步段）；flood 持续调 `check_liquidation`，每次 emit 在 User lane 触发 32 个 handler。度量在同步 fan-out 下的可持续 TPS。 |
| `event_async_drain` | 部署 1 个 emitter + 200 个 LP；emit 速率较低但每次产生 3 条 defer tx。度量 H+1 defer-tx admission 和 System lane 在重复 emit 下吸收异步溢出的能力。 |

调用：`npm run bench:flood -- --workload event_emit_flood`。

#### A.3 Snapshot 成本专项压测（CIP-29 §6.4 前置数据）

新增独立命令 `bench:snapshot-cost`：单 tx emit，订阅者数 N ∈ {1, 16, 32, 64, 128（需常量覆盖）, 256（需常量覆盖）}，handler 单次 cycles 大致恒定；输出每个 fire 的墙钟和关键路径 tx 墙钟。这是 §6.4 中治理决策升级 `MAX_SYNC_FIRES_PER_TOPIC` 之前所需的实测数据。

### Track B — 通用性能覆盖（与 CIP-29 相关但独立价值）

#### B.1 新 Workload（基于 Track 0 脚手架）

| Workload | 行为 | 目的 |
|---|---|---|
| `transfer` | 既有 System lane 转账（当前 `flood` 行为） | 向后兼容默认 |
| `actor_call_user` | 部署 noop actor（一次 state_get + state_set）；flood 调用它 | 压 User lane、PVM 预热、ActorStorageCache、批量结算的存储读 |
| `actor_chain` | A → B → C 三跳同步 `call()` | 压 `max_call_depth=32`、跨 actor 派发 —— 与 CIP-29 同步 fire 用同一套机制 |
| `defer_tx_user` | 提交带 `defer transaction` 的 tx 调度到 H+k | 度量 defer-tx admission、H+k 溢出 |
| `mixed_lane` | 按 N:M:K 权重混合 transfer + actor_call_user + defer_tx_user | 验证 contention 下的 lane 隔离性 |
| `state_growth` | 持续写不同大小的 `state_set` | 压 QMDB merkleize、cells basefee、`ActorKvBytes` 配额 |
| `deploy_burst` | 一波 N 次 actor deploy（变 code 大小） | 度量部署路径成本（编译、安装、代码存储写） |

每个 workload 暴露 `--workload <name>`，沿用现有 flood worker 池，输出
现有 flood 字段 + 自身的 workload 子段。

#### B.2 报告 Schema 增量（`types.ts`）

加 3 个增量子段（不破坏字段）：

```ts
events?: {
  scenarios: Array<{
    name: string;
    workload: string;
    n_subs_total: number;
    n_subs_sync: number;
    n_subs_async: number;
    payload_bytes: number;
    emit_count: number;
    emit_wall_ms_p50: number;
    emit_wall_ms_p99: number;
    sync_fires_observed: number;
    async_fires_observed: number;
    defer_txs_produced: number;
    cells_billed_to_emitter: number;
    cycles_burned_via_bid: number;
    failure_isolation_ok: boolean;          // S4
    rejected_at_cap: boolean | null;        // S6
    notes: string[];
  }>;
};

snapshot_cost?: {
  per_fire_us: Array<{ n_subs: number; p50_us: number; p99_us: number }>;
  emit_wall_ms: Array<{ n_subs: number; p50_ms: number; p99_ms: number }>;
};

workload?: {
  name: string;                              // 实际跑的 Workload
  lane: 'system' | 'user' | 'timer' | 'mixed';
  per_tx_cycles_observed_p50: number;        // 取自回执
  per_tx_cells_observed_p50: number;
  lane_basefee_change_pct: number | null;    // 比 basefee_summary 更窄
};
```

`flood_test.workload` 已有 string 字段——扩展 `report.ts` 用回执的
cycles/cells 聚合填充 `workload` 子段。

#### B.3 配置增量（`config_cowboy.json`）

追加可选字段；不填时行为不变：

```jsonc
"workload": "transfer",                  // 既有默认
"eventScenarios": ["S1","S2","S3","S4","S5","S6","S7"],  // bench:events 过滤
"eventBidDistribution": "zero|uniform|exponential",
"eventPayloadSizesBytes": [64, 512, 2048, 4096],
"snapshotCostNSubs": [1, 16, 32, 64],    // 128/256 需常量覆盖
"mixedLaneWeights": { "transfer": 50, "actor_call_user": 40, "defer_tx_user": 10 }
```

### Track C — 节点侧可观测性（小但收益高）

在 `node/rpc/src/metrics.rs` 加 3 个 Prometheus 计数器即可让 bench 把
场景与节点内部状态对齐，不必再从回执反推。**不在 bench 范围**，
但建议同步推进；若批准，bench 通过现有 `client.getNodeMetrics()` 读取：

- `cip29_emits_total`（counter，labels：`result=ok|rejected_cap|rejected_payload|rejected_depth`）
- `cip29_fires_total`（counter，labels：`mode=sync|async`、`status=ok|err|zombie`）
- `cip29_subscribers_gauge`（gauge per emitter —— 规模化后可能高基数；备选：单一全局 gauge 加一条 per-topic histogram bucket）

这是唯一需要改 bench 外代码的 Track。即便不做，bench 也能通过回执解析独立工作。

## 分期交付

阶段边界与 CIP-29 自身的 Phase 1/2/3 对齐，确保每个 bench 阶段与
对应协议能力同时落地。

| 阶段 | bench 交付物 | 依赖 | 工作量 |
|---|---|---|---|
| **B0** | Track 0 Workload 抽象；`transfer` 提取为 workload；**行为零变化** | — | 0.5–1 天 |
| **B1** | Track B Workload：`actor_call_user`、`actor_chain`、`state_growth`、`deploy_burst`；相应报告子段 | 通用，与 CIP-29 Phase 1 无关 | 2–3 天 |
| **B2** | Track A：`events.ts` 场景 S1、S3、S4（纯同步）；`event_emit_flood` Workload | CIP-29 Phase 2 ✅ 已在分支 | 2–3 天 |
| **B3** | Track A：S2、S6、S7（异步 + cap）；`event_async_drain` Workload；`snapshot-cost` 独立命令 | CIP-29 Phase 2 ✅ | 2 天 |
| **B4** | Track B：`defer_tx_user`、`mixed_lane` Workload；lane 隔离性报告 | — | 2 天 |
| **B5**（可选） | Track A：S5（竞价市场）+ orderbook 助手 actor | Phase 3 SDK ✅ 在分支 | 1 天 |
| **B6**（可选） | Track C 节点指标 + bench 接线 | 需要 node PR | 1 天 |

B0 必须先落地，因为其他阶段都依赖参数化 Workload 接口。B1 与 B2 互不依赖，可并行。

## 关键修改文件清单

| 文件 | 阶段 | 修改 |
|---|---|---|
| `node/bench/src/cowboy/flood.ts` | B0 | 参数化 `Workload`；把转账硬编码提取到 `workloads/transfer.ts` |
| `node/bench/src/cowboy/workloads/types.ts` | B0 | **新增** —— `Workload` 接口 |
| `node/bench/src/cowboy/workloads/transfer.ts` | B0 | **新增** —— 提取当前行为 |
| `node/bench/src/cowboy/workloads/actor_call_user.ts` | B1 | **新增** |
| `node/bench/src/cowboy/workloads/actor_chain.ts` | B1 | **新增** |
| `node/bench/src/cowboy/workloads/state_growth.ts` | B1 | **新增** |
| `node/bench/src/cowboy/workloads/deploy_burst.ts` | B1 | **新增** |
| `node/bench/src/cowboy/workloads/event_emit_flood.ts` | B2 | **新增** |
| `node/bench/src/cowboy/workloads/event_async_drain.ts` | B3 | **新增** |
| `node/bench/src/cowboy/workloads/defer_tx_user.ts` | B4 | **新增** |
| `node/bench/src/cowboy/workloads/mixed_lane.ts` | B4 | **新增** |
| `node/bench/src/cowboy/events.ts` | B2/B3/B5 | **新增** —— 场景驱动器 |
| `node/bench/src/cowboy/cip29_actors.ts` | B2 | **新增** —— 内嵌 Python actor 源，从 `node/examples/cip29_liquidation/` 移植 |
| `node/bench/src/cowboy/cip29_helpers.ts` | B2 | **新增** —— sub_id 推导、fire 事件 payload 解析 |
| `node/bench/src/cowboy/bench.ts` | B0–B5 | 路由新子命令 `events`、`snapshot-cost`；透传 `--workload` |
| `node/bench/src/cowboy/types.ts` | B0–B4 | 增量加 `events`、`snapshot_cost`、`workload` 报告子段 |
| `node/bench/src/cowboy/report.ts` | B0–B4 | 聚合新子段；输出摘要表 |
| `node/bench/config_cowboy.json` | B0+ | 追加可选 workload/eventScenarios 字段 |
| `node/bench/package.json` | B0+ | 加 `bench:events`、`bench:snapshot-cost` 脚本 |
| `node/bench/README.md` | B0+ | 文档化新命令 |

### 已存在可复用的工具

- 订阅记录编解码 —— `node/storage/src/event_subs.rs`（用于 sub_id 推导）
- Phase 3 actor 源 —— `node/examples/cip29_liquidation/lending_protocol.py` + `liquidity_provider.py`（拷贝到 `cip29_actors.ts` 作为常量）
- `start_all.sh` 中通过 `POST /actor/read` 读 handler 返回字节的模式（`read_handler_field`）
- `node/bench/src/cowboy/tx.ts` 已有 `buildActorDeployTx` / `buildActorExecuteTx`，覆盖所有所需 tx 类型
- `metrics.ts` 里的 `LatencyTracker`、`ErrorCounter`（可复用）
- `flood.ts` 中的 `nodeMetricsSnapshot` 管线，可自然扩展到新 workload

## 验证方法

每个阶段都可在本地用 `start_validator.sh` 跑通：

**B0**（转账提取为 workload，行为不变）：
- `npm run bench:flood` 基线输出在 `peak_tps`、`sustained_confirmed_tps_mid80`、`total_confirmed` 等关键字段上与修改前一致。Diff 报告 JSON。

**B1**（新通用 workload）：
- `npm run bench:flood -- --workload actor_call_user` 跑 ≥120s；回执显示每 tx 非零 `cycles_used`；报告 `workload` 子段非空。
- `npm run bench:flood -- --workload state_growth` 应观察到 cells basefee 上升（与 CIP-3 §2.4 交叉验证）。

**B2/B3**（CIP-29 场景）：
- `npm run bench:events` 产出含 `events.scenarios` 数组的报告，包含 S1/S2/S3/S4/S6/S7。
- S1@N=64：`sync_fires_observed == 64`、`async_fires_observed == 0`、`defer_txs_produced == 0`。
- S2@N=200：`sync_fires_observed == 64`、`async_fires_observed == 136`、`defer_txs_produced == 3`。
- S4：一半 LP 抛错时 `failure_isolation_ok == true`。
- S6：单 tx 发起 `MAX_EMITS_PER_TX+1=17` 次 emit 时 `rejected_at_cap=true`。
- 交叉验证：每个异步 fire 回执可通过 `parent_receipt.deferred_tx_hashes` 回溯到父 tx — 父→子完整性。

**Snapshot-cost**（B3）：
- `npm run bench:snapshot-cost` 写出 `snapshot_cost.per_fire_us` 曲线，至少覆盖 N ∈ {1, 16, 32, 64}；固定 handler 成本下 emit 墙钟应随 N 近似线性 —— 这是 CIP-29 §6.4 的基线数据。

**B4**（defer + 混合）：
- `--workload mixed_lane`，权重 50/40/10：通过 `nodeMetricsSnapshot` 观察各 lane 每块 cycle 占用；没有任何 lane 饿死其他 lane（lane 隔离不变量）。

**报告**：打开生成的 `cowboy-bench-*.json`，确认新子段已出现；对 `transfer` workload，既有字段与改造前逐字节一致。

## 明确不在范围

- 多验证者压测：bench 驱动单节点本地验证者，分布式场景留后续。
- Indexer 查询路径：在 `node/indexer/src/lib.rs:269-313` 桩被替换前，bench 持续直接解析回执。
- 跨链 / 桥 benchmark。
- WindTunnel 多链对比的 `node/bench/test/`、`node/bench/scripts/visualize.mjs`（仪表板层不变；新字段先以 raw JSON 出现）。

