# Cowboy Devnet 性能基准分析报告

**日期**: 2026-03-31
**工具**: `node/bench` (TypeScript) + `node/pvm/benches` (Cargo criterion)
**环境**: 本地 devnet，单节点

---

## 一、基准测试结果摘要

### 1.1 node/bench (bench:all)

| 指标 | 观测值 | 说明 |
|------|--------|------|
| 简单转账 TPS (peak) | 457 tx/block | 正常交易通过率 |
| 洪水测试错误数 | 140 笔 / 7263 笔 (~1.9%) | 见问题分析 §2.2 |
| Block 确认时间 P50 | ~2.1s | 周期性跳动 |
| Block 确认时间 P99 | ~5.8s | 见问题分析 §2.3 |
| 进程 RSS | 1.9 MB | 实际内存见 §2.4 |
| Disk IOPS | 1069 | 见问题分析 §2.5 |
| **数学 actor 部署** | **FAIL** (`InsufficientBalanceForGas`) | 见问题分析 §2.1 |

### 1.2 pvm/benches (Cargo criterion)

| 基准 | 基线耗时 | 备注 |
|------|---------|------|
| simple_transfer_exec | ~0.8 ms/tx | PVM 整体执行路径 |
| actor_dispatch | ~1.1 ms/tx | 含 actor 查找 + 调度 |
| complex_math_contract | ~3.2 ms/tx | 高计算密度 actor |
| `vm.compile()` 占比 | ~35–45% | 主要优化点（已修复，见 §3） |

---

## 二、问题分析

### 2.1 数学 actor 部署失败：`InsufficientBalanceForGas`

**现象**：bench:all 输出中数学 actor 部署交易报 `InsufficientBalanceForGas`，整个数学 actor 基准跳过。

**根因**：

Actor 部署 gas 成本由 CIP-3 §3.2 定义：

```
deploy_cycles = 50_000 + 100 * code_bytes
deploy_cells  = 10_000 + 200 * code_bytes
```

数学 actor 代码约 470 字节，估算：
- Cycles: 50,000 + 100×470 = 97,000 cycles
- Cells:  10,000 + 200×470 = 104,000 cells

以默认 basefee (cycles=1, cells=1) 计算手续费约 **201,000 单位**，加上转账金额本身。
而 `fund-accounts.ts` 默认每账户仅充值 **1,000,000 CBY**，在 bench 脚本消耗若干次 actor 调用后余额不足以覆盖 deploy 费用。

**修复**：将 `fund-accounts.ts` 默认充值额从 `1,000,000` 提升至 `50,000,000`（本次已改），保证单账户可安全执行数十次 deploy + 调用。

---

### 2.2 洪水测试错误率 1.9%（140/7263 笔）

**现象**：`bench:flood` 在 7263 笔交易中有 140 笔失败，错误集中在交易被拒绝（`InvalidNonce` 或 `InsufficientBalanceForGas`）。

**根因**：
- **Nonce 竞争**：bench 脚本并发度较高（30 in-flight），批量提交时本地 nonce 计数器超前，节点在拥塞时 reorder 可能导致 nonce 空洞。
- **Fee 估算偏差**：`maxFeePerCycle` 基于 basefee×2 估算；basefee 在洪水测试中随块动态上升（EIP-1559），部分早期提交的交易 maxFee 不足。

**评估**：1.9% 错误率属于可接受范围（devnet 无 mempool 补偿策略）。生产环境可通过 retry + 动态 maxFee 调整改善。

---

### 2.3 Block 确认时间抖动（P99 ~5.8s）

**现象**：P50≈2.1s，P99≈5.8s，偶现 6s+ 延迟，不符合目标 P99<3s。

**根因分析**：

1. **提交时机抖动**：bench 在提交交易后立即开始计时，而交易可能在当前块"关门"后 (block seal) 才进入 mempool，等下一块才确认，产生最多 +block_time 的延迟。
2. **Simplex BFT 广播延迟**（单节点 devnet 下忽略）：单节点直接 propose→commit，理论延迟极低。
3. **洪水期间 basefee 上升**：高 TPS 时 basefee 上升，部分交易被 mempool 延迟处理。

**建议**：从提交时刻改为 mempool 进入时刻（需 RPC 支持）作为延迟计时起点，以获得更精确的 P99 数据。

---

### 2.4 进程 RSS = 1.9 MB（看起来过低）

**现象**：bench 报告进程 RSS 仅 1.9 MB，与"Rust 区块链节点"的预期内存使用（数百 MB）相差悬殊。

**根因**：QMDB 使用 `mmap`（`MAP_SHARED`）映射数据库文件。Linux 将 mmap 页面计入 page cache，而不计入进程 `VmRSS`。`/proc/<pid>/status` 的 `VmRSS` 只统计进程私有映射页，因此读出来极低。

**实际内存**：通过 `smaps` 统计 `Pss`（按比例分摊共享页）或观察系统 `cached` 内存变化来获取真实值，预计远超 1.9 MB。

**评估**：该指标无效，bench 报告中 RSS 项需改用 `VmPSS`（或系统级 cache delta）。

---

### 2.5 Disk IOPS = 1069

**现象**：bench 期间磁盘 IOPS 约 1069，在洪水测试高峰期更高。

**根因分析**：

- QMDB（Quantum Merkle DB）采用 LSM-tree 结构，写入先到 WAL，再 compaction 到多层文件；write amplification 倍数通常为 5–30×。
- 每个 block commit 触发一次 QMDB flush，产生成批 WAL + manifest 写入。
- bench 测试环境（单机 SSD）下 1069 IOPS 尚在可控范围，但若 write amplification ×10，实际业务写入仅 ~100 ops，随 block rate 提高会线性增长。

**建议**：
1. 监控 QMDB compaction 线程 CPU 占用，评估写放大倍数。
2. 考虑提升 QMDB write buffer size，减少小 flush 频率。
3. 将 bench 磁盘基准指标改为 `wMB/s`（写带宽）而非 IOPS，更能反映瓶颈。

---

## 三、已完成优化：PVM 字节码编译缓存

基于 `cargo bench` 中 `vm.compile()` 占总 PVM 执行耗时 35–45% 的发现，本次会话实现了字节码编译缓存：

### 实现方式

**A. `INT_GUARD_PREAMBLE` 全局缓存**（`OnceLock<CodeObject>`）
- 每次执行都重新编译约 300 行 Python preamble，现改为全局单例，只编译一次
- 实现：`static PREAMBLE_CODE_OBJ: OnceLock<GenericCodeObject>` 在 `pvm-runtime/src/lib.rs`

**B. Actor 代码 LRU 缓存**（`BytecodeCache`）
- 缓存 key: `(source_bytes: Vec<u8>, pvm_fsm: bool)`
- 缓存值: `CodeObject<ConstantData>`（VM 无关，可跨 Interpreter 实例复用）
- Cache hit 时直接调用 `vm.ctx.new_code(cached.clone())`，跳过全量编译
- 容量: 256 条目（覆盖典型 devnet/testnet 的不同 actor 版本）
- 线程安全: `Mutex<LruCache<...>>`

### 修改文件

| 文件 | 变更 |
|------|------|
| `pvm/crates/pvm-runtime/src/cache.rs` | 新建 `BytecodeCache` 模块 |
| `pvm/crates/pvm-runtime/src/lib.rs` | `ExecutionOptions.bytecode_cache` 字段 + OnceLock preamble |
| `pvm/Cargo.toml` | 添加 `lru = "0.12"` workspace 依赖 |
| `pvm/crates/pvm-runtime/Cargo.toml` | 添加 `lru.workspace = true` |
| `execution/src/pvm_executor.rs` | `PvmExecutor` 持有 `Arc<BytecodeCache>` |

### 预期效果

| 场景 | 改进前 | 改进后 |
|------|--------|--------|
| 同一 actor 重复调用 | 每次 ~0.3–1ms 编译 | 跳过编译，仅 `ctx.new_code()` (<1µs) |
| INT_GUARD_PREAMBLE | 每次重编译 ~300 行 | 全局缓存，仅首次编译 |
| 预计延迟降低 | — | 热路径 10–40% |

### 测试结果

`cargo test -p cowboy-execution` 全量 130 tests 通过（含缓存改动后）。

---

## 四、已完成优化：PVM Interpreter 线程局部池化（热复用）

基于 `Interpreter` 初始化（分配所有内置类型、加载 stdlib、建立 string intern 表）是当前最高成本瓶颈的分析，实现了线程局部 Interpreter 池：

### 实现方式

**线程局部池（Thread-Local Pool）**（`pvm-runtime/src/interpreter_pool.rs`）
- 每个 OS 线程持有一个 `CachedInterpreter`（`thread_local!`）
- `InterpreterKey` 包含：`hash_seed`、`enable_softfloat`、`max_int_bits`、`determinism_enabled`、`init_stdlib`、`host_module_name`、`det_lists_hash`（whitelist/blacklist 的哈希）
- **Pool Hit**：`borrow_mut().take()` 取出 Interpreter（立即释放 borrow），`enter()` 直接在 owned 值上调用（避免 RefCell 再入），完成后放回池
- **Pool Miss / Key 不匹配**：创建新 Interpreter，enter() 后存入池
- `guard_installed` / `preamble_installed` 标志跟踪已安装状态，热路径跳过重复安装
- Checkpoint 模式 / `trace_imports=true`：不池化（always fresh）

### 关键安全设计：Take-and-Return

原方案持有 `Ref` borrow 贯穿整个 `enter()`，嵌套 actor 调用时 `RefCell already borrowed` panic。
最终方案：`borrow_mut().take()` 取走后立即释放 borrow；`enter()` 期间池槽为空；嵌套调用创建独立 Interpreter；`enter()` 完成后放回池。

### 修改文件

| 文件 | 变更 |
|------|------|
| `pvm/crates/pvm-runtime/src/interpreter_pool.rs` | 新建 `InterpreterKey`、`CachedInterpreter`、`POOL`、`det_lists_hash()` |
| `pvm/crates/pvm-runtime/src/lib.rs` | Take-and-Return 池逻辑 + `build_interpreter()` + `make_pool_key()` + `run_enter_body()` + `skip_preamble` 参数 |
| `pvm/benches/pvm_cowboy.rs` | 新增 `interpreter_warmstart` 基准（cold vs warm 对比） |

### 预期效果

| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| Actor 热调用（相同 settings） | Interpreter init + guard + preamble + 执行 | 仅 new_scope + 执行（跳过 init/guard/preamble） |
| 预计延迟降低 | 基准 | 热路径 **50–70%**（取决于 stdlib init 实际耗时） |

### 测试结果

`cargo test -p cowboy-execution` 全量 130 tests 通过（含嵌套 actor 调用回滚测试）。

---

## 五、后续优化建议（优先级排序）

| 优先级 | 项目 | 预计收益 | 风险 |
|--------|------|---------|------|
| P0 | 充值金额修复（已完成）| 解除 bench 阻塞 | 低 |
| P1 | 字节码缓存（已完成）| actor 热路径 10–40% | 低 |
| P2 | Interpreter 实例池化（已完成）| actor 热路径 50–70% | 低 |
| P3 | QMDB write buffer 调优 | 减少 flush IOPS | 低 |
| P4 | bench RSS 指标修复 | 数据准确性 | 低 |
| P5 | 洪水测试 retry 逻辑 | 降低错误率至 <0.5% | 低 |
| P6 | P99 延迟计时基点改进 | 更精确的延迟数据 | 低 |
