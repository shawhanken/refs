---
type: entity
tags: [node, architecture, consensus]
sources:
  - refs/node/01-项目概览与路线图.md
  - refs/node/02-实施与技术实现.md
  - refs/chain/2026-01-24_PVM_CHAIN_INTEGRATION_CN.md
  - /home/ubuntu/workspace/CLAUDE.md
last_updated: 2026-04-15
status: authoritative
---

# Cowboy Node — 主链节点架构

**位置**: `/home/ubuntu/workspace/node/`（独立 Rust workspace）

**共识**: Simplex BFT（`Application` trait: propose/verify/report 三阶段）

---

## Crate 依赖（bottom → top）

```
types  →  storage  →  execution  →  chain  →  validator (binary)
                     ↑
              runner / token / rpc / client
              pvm/crates/pvm-host + pvm-runtime
```

---

## 核心 Crate

| Crate | 职责 |
|---|---|
| `types` | `Transaction`、`Block`、`Instruction`（System / Actor）、`Account`、`Actor`、`Message`；全部协议级常量 |
| `storage` | `BlockchainStorage`（QMDB 后端）、投机执行、Merkle root、gas lane 分区、burn/tip 分配 |
| `execution` | `ExecutionEngine`（执行入口）、basefee 管理、gas 计量、per-instruction handlers |
| `chain` | `Engine` 协调器、`Application`（BFT callbacks）、`Mempool`（per-account nonce 队列）|
| `rpc` | axum HTTP；限速 100 req/s，faucet 5 req/min（默认禁用）|

---

## 块生命周期

```
propose / verify:  begin_batch → execute_txs → fire timers → sweep deferred
                    → compute roots → cache → rollback
report:             apply_cached_batch（持久化）→ deferred TXs 回 mempool
```

见 [[../concepts/speculative-execution]]。

---

## Gas Lane 分区

投机执行中，每笔交易按类别分到独立 lane：
- `LANE_USER` — 普通用户交易
- `LANE_RUNNER` — Runner 结果提交
- `LANE_TIMER` — Timer deferred tx
- `LANE_SYSTEM` — 系统 actor 操作

每 lane 有独立的 gas 预算与基线，避免 priority inversion。

---

## 关键模块

- **`execution/engine.rs`** — 顶层执行器、basefee 字段
- **`execution/transaction.rs`** — per-tx 分派、basefee 校验、gas 扣费、burn/tip
- **`execution/pvm_host.rs`** — `CowboyHost`：host API 实现；`ActorStorageCache` 追踪 read
- **`execution/pvm_executor.rs`** — `PvmExecutor::execute_handler()`，enforce max_cycles
- **`execution/basefee.rs`** — EIP-1559 双 basefee；公式见 [[../concepts/basefee]]
- **`execution/gas.rs`** — `GasCosts`、`DualGasMeters`、`GasReport`（分类统计）
- **`execution/runner/`** — `dispatcher.rs`、`verifier.rs`、`registry.rs`
- **`execution/token/`** — CIP-20 实现
- **`storage/speculative.rs`** — 批量执行、burn/tip 分配、lane 分区
- **`storage/process_block.rs`** — basefee 生命周期（prepare / finalize / persist）

---

## 实体关联

| 实体 | 本页章节 | Wiki 链接 |
|---|---|---|
| 系统 Actor | — | [[system-actors]] |
| Runner | `execution/runner/` | [[runner-lifecycle]] |
| PVM | `pvm/` + `execution/pvm_*.rs` | [[pvm]] |

---

## Sources
- `refs/node/01-项目概览与路线图.md`、`02-实施与技术实现.md`
- `refs/node/03-测试与验证.md`、`04-当前状态与行动项.md`
- `refs/node/2026-02-05_VALIDATOR_VS_COWBOY_CHAIN.md`
- `refs/chain/2026-01-24_PVM_CHAIN_INTEGRATION_CN.md`
- `refs/chain/2026-01-24_WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md`
- workspace `node/CLAUDE.md`（crate 级 AI 指南）
