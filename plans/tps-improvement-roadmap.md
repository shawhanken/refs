# Cowboy TPS 提升方案

## Context

当前 cowboy 链的实际 TPS 约为 50~150（取决于 actor 调用复杂度），理论上限 500 TPS。
制约因素已通过代码分析确认。本方案按投入产出比分四个 Tier，各 Tier 独立可交付，
从最小改动开始，逐步深入到架构层变更。

---

## Tier 1 — 参数调优（1~2天，立竿见影）

### T1-A: 提升区块交易上限

**文件**: `types/src/constants.rs:14`

```rust
// Before
pub const MAX_BLOCK_TRANSACTIONS: usize = 500;

// After
pub const MAX_BLOCK_TRANSACTIONS: usize = 2_000;
```

**受影响位置**（仅2处）:
- `chain/src/application.rs:282` — propose() 打包循环
- `chain/src/application.rs:400` — verify() 校验

**注意**: 需同步评估 P2P 消息大小上限 `MAX_P2P_MESSAGE_SIZE = 1_048_576`（1 MiB），
若平均 tx 大小 ~200B，2000 笔 = 400KB，在限制以内，无需调整。

---

### T1-B: 提升 Gas 目标和用户 Lane 占比

**文件**: `types/src/constants.rs:23-39`

```rust
// Before
pub const BLOCK_CYCLES_TARGET: u64 = 10_000_000;
pub const BLOCK_CELLS_TARGET:  u64 =    500_000;
pub const LANE_USER_CYCLES:   u64 =  5_000_000;  // 50%
pub const LANE_RUNNER_CYCLES: u64 =  2_500_000;  // 25%
pub const LANE_TIMER_CYCLES:  u64 =  2_000_000;  // 20%
pub const LANE_SYSTEM_CYCLES: u64 =    500_000;  //  5%

// After — 翻倍总量，用户 Lane 提至 60%
pub const BLOCK_CYCLES_TARGET: u64 = 20_000_000;
pub const BLOCK_CELLS_TARGET:  u64 =  1_000_000;
pub const LANE_USER_CYCLES:   u64 = 12_000_000;  // 60%
pub const LANE_RUNNER_CYCLES: u64 =  4_000_000;  // 20%
pub const LANE_TIMER_CYCLES:  u64 =  3_000_000;  // 15%
pub const LANE_SYSTEM_CYCLES: u64 =  1_000_000;  //  5%
```

**效果估算**: 结合 T1-A，轻量交易（10k cycles）理论上限 1200 TPS；
实际 actor 调用（50k cycles）上限约 240 TPS。

---

### T1-C: 并行化 QMDB 三阶段提交

**文件**: `storage/src/blockchain_storage.rs:261-310`

当前三个 DB 串行 commit，可用 `tokio::join!` 并行化。
注意：`merkleize()` 必须在各自的 pending 数据准备好后才能调用，
但 `apply_batch()` 和 `commit()` 三个 DB 之间互相独立。

```rust
pub async fn commit_batch(&mut self) -> Result<(), Error> {
    // 步骤 1：串行 merkleize（各 DB 数据独立，实际也可并行，但需 split &mut）
    let state_changeset = if !self.state_pending.is_empty() {
        let mut batch = self.state_db.new_batch();
        for (k, v) in self.state_pending.drain(..) { batch.write(k, v); }
        Some(batch.merkleize(None).await?.finalize())
    } else { None };

    let tx_index_changeset = if !self.tx_index_pending.is_empty() {
        let mut batch = self.tx_index.new_batch();
        for (k, v) in self.tx_index_pending.drain(..) { batch.write(k, v); }
        Some(batch.merkleize(None).await?.finalize())
    } else { None };

    let tx_receipts_changeset = if !self.tx_receipts_pending.is_empty() {
        let mut batch = self.tx_receipts.new_batch();
        for (k, v) in self.tx_receipts_pending.drain(..) { batch.write(k, v); }
        Some(batch.merkleize(None).await?.finalize())
    } else { None };

    // 步骤 2：并行 apply_batch
    let (r1, r2, r3) = tokio::join!(
        async {
            if let Some(cs) = state_changeset {
                self.state_db.apply_batch(cs).await
            } else { Ok(()) }
        },
        async {
            if let Some(cs) = tx_index_changeset {
                self.tx_index.apply_batch(cs).await
            } else { Ok(()) }
        },
        async {
            if let Some(cs) = tx_receipts_changeset {
                self.tx_receipts.apply_batch(cs).await
            } else { Ok(()) }
        }
    );
    r1?;
    r2.map_err(|e| { tracing::error!(...); e })?;
    r3.map_err(|e| { tracing::error!(...); e })?;

    // 步骤 3：并行 commit
    let (c1, c2, c3) = tokio::join!(
        self.state_db.commit(),
        self.tx_index.commit(),
        self.tx_receipts.commit()
    );
    c1?; c2?; c3?;

    self.batch_mode = false;
    Ok(())
}
```

**注意**: `blockchain_storage.rs` 的 `&mut self` 借用规则要求拆分字段引用，
可能需要使用裸字段指针或重构为内部 Arc，需要在实现时验证编译可行性。
若编译器拒绝 split borrow，可先仅并行 commit()，apply_batch() 保持串行。

---

## Tier 2 — PVM 编译缓存（3~5天，中等改动）

### T2-A: INT_GUARD_PREAMBLE 字节码缓存

**文件**: `pvm/crates/pvm-runtime/src/lib.rs`

当前每次 execute_tx_internal 都从字符串重新编译 `INT_GUARD_PREAMBLE` 和 `GUARD_SOURCE`。
可用 `once_cell::sync::OnceCell` 或 Rust 1.70+ `OnceLock` 缓存编译后的字节码对象。

```rust
// 全局缓存编译结果（字节码可跨 VM 实例共享，但 scope 不能共享）
static GUARD_BYTECODE: OnceLock<Arc<CodeObject>> = OnceLock::new();

fn get_guard_bytecode(vm: &VirtualMachine) -> PyResult<PyObjectRef> {
    // 仅在第一次调用时编译
    // 后续复用 bytecode，只需 vm.run_code_obj() 注入 scope
    ...
}
```

**实现约束**:
- RustPython 的 `CodeObject` 是否可跨 VM 实例共享，需要验证类型是否 `Send + Sync`
- 若不可跨 VM 共享（VM-local bytecode），可改为 per-thread 缓存（`thread_local!`）
- 此优化节省约 5~10% 执行时间（对 guard 编译代价的估算）

**文件**: `pvm/crates/pvm-runtime/src/lib.rs:469-480`
改动范围：在 `execute_tx_internal` 中将 `vm.compile(INT_GUARD_PREAMBLE, ...)` 替换为缓存查找。

---

### T2-B: 使区块参数可运行时配置

**目标**: 允许通过 CLI flags 或 `cowboy.toml` 调整 `max_block_transactions` 和 `min_block_interval`，
便于不同网络环境（devnet/testnet/mainnet）使用不同参数而无需重编译。

**新增结构体** (`chain/src/application.rs`):
```rust
#[derive(Debug, Clone)]
pub struct BlockConfig {
    pub max_block_transactions: usize,
    pub min_block_interval: Duration,
}

impl Default for BlockConfig {
    fn default() -> Self {
        Self {
            max_block_transactions: MAX_BLOCK_TRANSACTIONS,
            min_block_interval: Duration::from_secs(1),
        }
    }
}
```

**受影响文件**:
- `chain/src/application.rs` — 新增 `with_block_config()` 构造器；propose/verify 用 `self.block_config.max_block_transactions`
- `cli/` — 新增 `--max-block-transactions` 和 `--block-interval-ms` 参数解析
- `cowboy.toml` — 新增 `[block]` section

---

## Tier 3 — 并行事务执行（2~4周，架构改动）

### T3 设计概述

这是 TPS 提升最大的方向，但改动最大。核心思路：
**对无冲突的交易组进行并行执行，有冲突的回退到串行**。

### T3-A: 事务依赖图分析（静态阶段）

在 `speculative.rs` 的执行循环之前，对 block.transactions 做依赖分析：

```rust
struct TxDependencyGraph {
    // sender → tx indices（同一 sender 必须串行）
    sender_groups: HashMap<Address, Vec<usize>>,
    // 按 actor 分组（调用同一 actor 的 tx 存在潜在冲突）
    actor_groups: HashMap<Address, Vec<usize>>,
}

fn build_dependency_graph(transactions: &[Transaction]) -> Vec<Vec<usize>> {
    // 返回"并发批次"列表：每个批次内的 tx 可并行执行
    // 约束：
    // 1. 同一 sender 的 tx 必须在不同批次（nonce 顺序）
    // 2. 同一 actor 的 tx 放入同一批次或串行（保守策略）
    // 3. SystemActor (0x01~0x09) 调用必须串行
}
```

**保守分组策略**（初期实现，正确性优先）:
- 同 sender 的 tx 串行
- 不同 sender 且不调用相同 actor → 可并行
- 调用 Token Registry (0x04) 的 tx 串行（全局共享状态）

### T3-B: 状态访问层重构

当前 `StateStore` trait 全部使用 `&mut self`，无法并发访问。
需引入读写分离的访问层：

```rust
// 新增 trait（storage/src/traits.rs）
pub trait ParallelStateStore: StateStore {
    // 乐观读：获取快照（无锁，返回 Arc<snapshot>）
    fn snapshot(&self) -> Arc<StateSnapshot>;
    // 冲突检测：提交前验证快照未失效
    fn try_commit_batch(&mut self, changes: StateDelta, snapshot_version: u64)
        -> Result<(), ConflictError>;
}
```

**实现方案**（`storage/src/speculative.rs`）:
- 用 `Arc<RwLock<SpeculativeState>>` 替换当前 `&mut self` 状态
- 每个并行 tx 持有读锁快照，执行完后提交 diff
- 提交时检测版本冲突（类似 MVCC）

### T3-C: 并行执行调度器

```rust
// execution/src/execution/transaction.rs（新增方法）
pub async fn execute_transactions_parallel<S: ParallelStateStore>(
    &mut self,
    store: Arc<RwLock<S>>,
    batches: Vec<Vec<usize>>,      // 从 dependency graph 得到的并发批次
    transactions: &[Transaction],
    ...
) -> Result<Vec<ExecutionResult>, ExecutionError> {
    let mut all_results = vec![None; transactions.len()];

    for batch in batches {
        // 同批次内并行执行
        let futures: Vec<_> = batch.iter().map(|&idx| {
            let tx = &transactions[idx];
            let store_ref = Arc::clone(&store);
            tokio::spawn(async move {
                // 每个 tx 拿读快照执行，收集 StateDelta
                execute_tx_on_snapshot(store_ref, tx, ...).await
            })
        }).collect();

        let results = futures::future::join_all(futures).await;

        // 串行提交：检测冲突，冲突的 tx 回退到串行重新执行
        for (idx, result) in batch.iter().zip(results) {
            match result {
                Ok(Ok((delta, exec_result))) => {
                    store.write().try_commit_batch(delta, ...)?;
                    all_results[*idx] = Some(exec_result);
                }
                Ok(Err(ConflictError)) => {
                    // fallback: 串行重新执行该 tx
                    ...
                }
                ...
            }
        }
    }
    Ok(all_results.into_iter().flatten().collect())
}
```

**关键依赖（需新增 Cargo deps）**:
```toml
# execution/Cargo.toml
rayon = "1"
dashmap = "6"
```

### T3 实施顺序

1. 先实现依赖图分析（T3-A），但仍用串行执行 → 验证分组逻辑正确性
2. 实现 `ParallelStateStore` trait + MVCC 状态快照（T3-B）
3. 接入并行调度器（T3-C），先只并行不调用 actor 的纯转账 tx
4. 逐步扩展到 actor 调用，完善冲突检测

---

## Tier 4 — VM 级批量执行（4~8周，实验性）

> **注意**: PvmExecutor 本身是零大小类型（ZST），无需池化。
> 真正的瓶颈是每次 `execute_tx_internal` 创建新的 RustPython VirtualMachine 实例。
> 该层改动依赖对 pvm-runtime crate 的深度修改。

### T4-A: 单 VM 内批量执行

**思路**: 在一个 VM 实例内顺序执行多笔交易，利用 VM 热身状态（已加载 stdlib、guards）：

```rust
// pvm/crates/pvm-runtime/src/lib.rs（新增函数）
pub fn execute_batch_in_vm<F>(
    host_factory: F,
    transactions: &[TxPayload],
    options: &ExecutionOptions,
) -> Vec<ExecutionResult<...>>
where
    F: Fn(usize) -> Box<dyn HostApi>,  // per-tx host
{
    // 创建一次 VM
    let interpreter = build_interpreter(options);
    interpreter.enter(|vm| {
        // 注入 guards 一次
        setup_guards(vm, options)?;

        // 逐笔执行，每次只换 host 和 input/output 变量
        transactions.iter().enumerate().map(|(i, tx)| {
            let host = host_factory(i);
            execute_single_in_existing_vm(vm, host, tx)
        }).collect()
    })
}
```

**实现约束**:
- 必须确保 tx 之间的 Python 全局状态完全隔离（actor code 的全局变量泄漏风险）
- 每笔 tx 需要 `clone()` 主模块 scope 或重新初始化 globals
- 存在确定性风险，需要完整测试覆盖

### T4-B: 预热 VM 池（进程级）

**思路**: 维护一个预热好的 VM 进程池（worker pool），通过 IPC 通信分发执行任务：

```
[node process]  --（tx payload + host callbacks via IPC）-->  [pvm-worker-0]
                                                              [pvm-worker-1]
                                                              [pvm-worker-2]
```

每个 worker 保持一个热 VM 实例，只需注入 actor code 和 host callbacks。
适合高并发场景，但 IPC overhead 和 host callback 的跨进程传递代价需要仔细评估。

---

## 验证方法

### Tier 1 验证
```bash
# 运行 execution crate 所有测试
cd /home/ubuntu/workspace/node
cargo test -p cowboy-execution --all-features

# 运行 integration tests
cd examples/token && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
cd examples/multi_call && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
```

### Tier 2 验证
- `cargo test -p pvm-runtime` — 验证 PVM determinism tests 全部通过
- 在 devnet 上运行 1000 笔交易，比对 execution_hash 与修改前一致

### Tier 3 验证
- 单元测试：构造同 sender / 不同 sender / 冲突 actor 的 tx 组合，验证依赖图正确
- 集成测试：并行执行结果与串行执行结果的 state root 完全一致
- 压测：`cargo bench` 对比并行前后吞吐量

### Tier 4 验证
- 确定性测试：同一批 tx 在批量 VM 和单笔 VM 下的执行结果字节相同
- 边界测试：actor code 全局变量污染检测

---

## 关键文件清单

| 文件 | 改动 Tier |
|------|-----------|
| `types/src/constants.rs` | T1-A, T1-B |
| `storage/src/blockchain_storage.rs` | T1-C |
| `chain/src/application.rs` | T1-A, T2-B |
| `pvm/crates/pvm-runtime/src/lib.rs` | T2-A, T4-A |
| `execution/src/execution/transaction.rs` | T3-C |
| `storage/src/speculative.rs` | T3-B, T3-C |
| `storage/src/traits.rs` | T3-B |
| `execution/Cargo.toml` | T3-C |
| `cli/` | T2-B |

---

## 推荐执行顺序

```
Week 1:  T1-A + T1-B + T1-C  → devnet 部署，基准测试
Week 2:  T2-A + T2-B          → PVM 缓存 + 参数配置化
Week 3~6: T3-A → T3-B → T3-C → 并行执行（迭代交付）
Week 7+: T4（按需，实验性）
```

**预期 TPS 提升**:
- Tier 1 完成：100~400 TPS（主要受益于 Gas 上限提升）
- Tier 1+2 完成：~400 TPS（参数优化）
- Tier 1+2+3 完成：1000~3000 TPS（取决于冲突率，低冲突场景收益最大）
