# Transfer 交易全生命周期性能分析与埋点方案

## Context

分析 cowboy node 中一笔简单 Transfer 交易从提交到上链确认的完整路径，识别各阶段性能瓶颈，并设计可量化的埋点方案，为后续性能优化提供数据依据。

---

## 一、Transfer 交易完整生命周期

### 阶段 0：客户端提交（RPC 层）

**入口：** `POST /submit` → `rpc/src/handlers/chain.rs:90 submit_transaction()`

```
客户端 HTTP POST /submit (CBOR 编码)
  ↓
[验证流水线]
  1. 请求体大小检查 (> 512 KB 拒绝)
  2. CBOR 解码
  3. 批量大小检查 (> 50 txs 拒绝)
  4. 拒绝 deferred 类型交易
  5. 签名验证 tx.verify() — secp256k1 ecrecover
  6. Nonce 预检 → storage.read().get_account() — I/O 读
  ↓
mempool.lock().add(tx) — 获取 Mutex
  ↓
返回 SubmitResponse {added, skipped, hashes}
```

**关键文件：**
- `rpc/src/handlers/chain.rs:90-204` — 主处理器
- `rpc/src/state.rs:15-32` — AppState (storage RwLock + mempool Mutex 共享)

---

### 阶段 1：Mempool 入池

**入口：** `chain/src/mempool.rs:150 Mempool::add()`

```
add(tx):
  1. 超额驱逐 (若 len >= 32768，按 score 驱逐低优先级)
  2. 重复检查 (digest 查找)
  3. 零地址过滤
  4. 字节大小检查 (全局 <= 32 MB)
  5. BTreeMap 按 nonce 插入 (per-account)
  6. Per-account 积压上限 (默认 32 条)
  7. 更新 Prometheus gauges (transactions, accounts)
```

**评分函数：** `tx_score() = fee_per_byte × age` — 决定 `next()` 的出块优先级

---

### 阶段 2：PROPOSE 阶段（Leader 节点）

**入口：** `chain/src/application.rs:358 propose()`

```
1. 等待 min_block_interval (500ms) — AsyncMutex<last_block_time>
2. mempool.lock().await — 出队最多 1000 条交易
3. WRITE LOCK: storage.execute_block_speculative(temp_block)
   │
   ├─ begin_batch() — 设置 batch_mode = true
   ├─ reset_block_state() — 清空 seen_messages/deferred_gas_pools 等
   ├─ 计算 tx_root (Merkle 哈希)
   ├─ 索引每笔 tx (set_tx_location)
   ├─ 加载 basefee (I/O 读 BASEFEE_STORAGE_KEY)
   │
   ├─ 【核心循环】逐笔执行交易 (最多 1000 笔)
   │  └─ execute_one_tx() [transaction.rs:18]
   │     ├─ secp256k1 签名验证 (ecrecover)
   │     ├─ get_account(sender) — I/O 读
   │     ├─ nonce/basefee/余额校验
   │     ├─ 计算 calldata intrinsic gas
   │     ├─ dispatch → handle_system_instruction → Transfer
   │     │  ├─ consume gas (cycles + cells)
   │     │  ├─ 校验 sender 余额
   │     │  ├─ get_account(receiver) — I/O 读
   │     │  ├─ 更新双方余额
   │     │  └─ set_account(receiver) — I/O 写 (buffer)
   │     ├─ 计算并累积 burn/tip
   │     └─ set_account(sender) — I/O 写 (buffer)
   │
   ├─ 更新 basefee (EIP-1559 公式)
   ├─ burn 分发 (Address::ZERO) + tip 分发 (proposer)
   ├─ Timer 执行 (M-F inline)
   ├─ 生成 receipts (逐笔)
   ├─ 处理 deferred tx (持久化 + 清理)
   │
   ├─ speculative_state_root() → merkleize() — **最耗时操作**
   │  └─ Blake3 MMR 计算所有 state_pending 变更
   ├─ 计算 receipt_root
   ├─ cache_speculative_batch() — 克隆所有 pending writes 到内存
   └─ rollback_batch() — 丢弃 pending，DB 不变

4. 缓存 roots 到 last_propose_cache
5. 更新 last_block_time
6. 记录 propose_duration_ms 指标
```

---

### 阶段 3：VERIFY 阶段（所有验证节点）

**入口：** `chain/src/application.rs:498 verify()`

```
1. 获取 block + parent (ancestry stream)
2. 时间戳合法性校验
3. verify_transaction_signatures() — O(tx_count) × secp256k1 (application.rs:722)
4. 验证 tx_root (便宜)
5. Leader 快速路径检查：
   ├─ 若自己是 proposer 且 execution_hash 匹配 cached
   └─ 直接比对 state_root/receipt_root → 跳过重新执行！
6. 非 leader 或 cache miss：
   └─ WRITE LOCK: storage.execute_block_speculative() — 完整重放
7. 比对 state_root + receipt_root
8. 通过则投 notarize 票
```

---

### 阶段 4：REPORT 阶段（确认上链）

**入口：** `chain/src/application.rs:650 report()`

```
1. WRITE LOCK: storage.apply_cached_batch(height)
   ├─ 从 speculative_cache 取回 pending writes
   ├─ begin_batch()
   └─ commit_batch() — 【三阶段顺序提交】
      ├─ Phase 1: state_db.merkleize() + apply_batch() + commit() — I/O critical
      ├─ Phase 2: tx_index.merkleize() + apply_batch() + commit() — I/O auxiliary
      └─ Phase 3: tx_receipts.merkleize() + apply_batch() + commit() — I/O auxiliary

2. 将 deferred txs 追加回 mempool
3. mempool.lock() → cleanup 已确认发送者的旧 nonce

4. 每 100 块触发 sync + prune：
   ├─ READ LOCK: sync_all() → join3(state_db.sync, tx_index.sync, tx_receipts.sync) — 磁盘 flush
   └─ WRITE LOCK: prune_all() → 逐个 prune (顺序) — 磁盘 I/O
```

**至此交易正式上链，状态持久化，可查询。**

---

## 二、性能瓶颈分析

### 瓶颈排名（按严重程度）

| 优先级 | 瓶颈 | 位置 | 类型 | 当前耗时估计 |
|--------|------|------|------|-------------|
| P0 | **逐笔串行执行** | `speculative.rs:180-182` | CPU + I/O | 随 tx_count 线性增长 |
| P0 | **状态 Merkle 化** | `speculative.rs:581` | CPU + I/O | 所有变更 key 的 Blake3 MMR |
| P1 | **签名验证 (1000 txs)** | `application.rs:534` | CPU | secp256k1 ecrecover × 1000 |
| P1 | **三阶段 QMDB 顺序提交** | `blockchain_storage.rs:286-341` | I/O | 3次串行磁盘写入 |
| P2 | **每笔 tx 多次 I/O** | `transaction.rs + system_instruction.rs` | I/O | get/set × 2~4 per tx |
| P2 | **storage RwLock 争用** | `application.rs` | 锁竞争 | propose 阻塞 verify |
| P3 | **每 100 块 sync+prune** | `blockchain_storage.rs:352-410` | I/O 尖峰 | 周期性卡顿 |
| P3 | **Timer 内联执行** | `speculative.rs:260-373` | CPU + I/O | 依赖 timer 数量 |
| P4 | **Mempool 全局 Mutex** | `application.rs:385` | 锁 | 持续时间短，影响小 |

### 关键路径分析

**一笔 Transfer 的单笔执行开销（`execute_one_tx`）：**
1. `secp256k1 ecrecover` ≈ 50-200μs
2. `get_account(sender)` — 存储读，取决于 QMDB 缓存命中
3. `get_account(receiver)` — 存储读
4. `set_account(sender)` + `set_account(receiver)` — buffer 写（廉价）
5. Gas 计量（廉价）

**每出一个 1000 txs 的 Transfer 块的总瓶颈：**
- 执行循环：~1000 × (ecrecover + 2 I/O reads) = 主要延迟
- Merkle 化：与 state_pending 大小成正比（1000 笔 Transfer = ~2000 个账户变更）
- 两者之和若超过 500ms（min_block_interval），就会开始影响出块频率

---

## 三、埋点方案设计

### 设计原则
- 使用已有的 `prometheus-client` + `context.with_label()` 模式
- 关键路径使用 `Instant::now()` 计时，通过 `Gauge` (ms 级) 暴露
- 高频小操作使用 `Counter` 累计而非每次计时（避免 overhead）
- 与现有 `propose_duration_ms` / `verify_duration_ms` 体系保持一致

---

### 埋点 1：RPC 提交层

**文件：** `rpc/src/handlers/chain.rs`

| 指标名 | 类型 | 含义 | 实现位置 |
|--------|------|------|---------|
| `rpc_submit_total` | Counter | 收到的提交请求总数 | handler 入口 |
| `rpc_submit_txs_added` | Counter | 成功入池的 tx 总数 | `added_count` 累加 |
| `rpc_submit_txs_skipped` | Counter | 跳过（nonce/重复）的 tx 总数 | `skipped_count` 累加 |
| `rpc_signature_verify_duration_ms` | Gauge | 签名验证耗时 | 包裹签名验证循环 |
| `rpc_nonce_check_duration_ms` | Gauge | nonce 预检 I/O 耗时 | 包裹 `get_account` |
| `rpc_submit_duration_ms` | Gauge | 整个 submit handler 耗时 | handler 入口/出口 |

---

### 埋点 2：Mempool 层

**文件：** `chain/src/mempool.rs`（已有 transactions/accounts gauge，补充以下）

| 指标名 | 类型 | 含义 | 实现位置 |
|--------|------|------|---------|
| `mempool_add_duration_us` | Gauge | 单次 add() 耗时（微秒） | `add()` 入口/出口 |
| `mempool_evictions_total` | Counter | 因满员触发的驱逐次数 | 驱逐分支 `mempool.rs:152` |
| `mempool_next_duration_us` | Gauge | `next()` 选取耗时 | `next()` 出队路径 |

---

### 埋点 3：Propose 阶段细分

**文件：** `chain/src/application.rs` + `storage/src/speculative.rs`

这是最重要的一组埋点，需要细粒度拆分：

| 指标名 | 类型 | 含义 | 实现位置 |
|--------|------|------|---------|
| `propose_mempool_dequeue_duration_ms` | Gauge | mempool 出队耗时 | `propose()` 中 mempool.lock() 前后 |
| `propose_execute_total_duration_ms` | Gauge | 整个 execute_block_speculative 耗时 | 已有 propose_duration_ms 是总时，需拆分 |
| `propose_tx_execution_duration_ms` | Gauge | 纯 tx 执行循环耗时（不含 merkle） | `speculative.rs` 循环前后 |
| `propose_tx_count` | Gauge | 实际执行 tx 数（已有 last_proposed_tx_count） | 确认已有 |
| `propose_merkle_duration_ms` | Gauge | **状态 Merkle 化耗时** | `speculative.rs:581` 前后 |
| `propose_receipt_gen_duration_ms` | Gauge | Receipt 生成耗时 | `speculative.rs:375-453` 前后 |
| `propose_timer_execution_duration_ms` | Gauge | Timer 执行耗时 | `speculative.rs:260-373` 前后 |
| `propose_deferred_processing_duration_ms` | Gauge | Deferred tx 处理耗时 | `speculative.rs:455-578` 前后 |
| `propose_cache_batch_duration_ms` | Gauge | cache_speculative_batch 耗时 | `speculative.rs:589` 前后 |
| `propose_state_pending_entries` | Gauge | merkle 化时 state_pending 条目数 | merkle 化前记录 |

---

### 埋点 4：单笔 TX 执行细分

**文件：** `execution/src/execution/transaction.rs` + `system_instruction.rs`

> 注意：这些是高频路径，用 Counter 累积而非 Gauge 记录每次。用 Histogram（bucket）更理想，但现有模式是 Gauge。建议用 `AtomicU64` 累积总时间，再计算平均值暴露。

| 指标名 | 类型 | 含义 | 实现位置 |
|--------|------|------|---------|
| `tx_sig_verify_total_us` | Counter（累积 μs） | 所有 tx 签名验证总耗时 | `transaction.rs:64` 前后 |
| `tx_storage_read_total_us` | Counter（累积 μs） | 所有 get_account 总耗时 | 包裹每次 get_account |
| `tx_storage_write_total_us` | Counter（累积 μs） | 所有 set_account 总耗时 | 包裹每次 set_account |
| `tx_executed_total` | Counter | 执行成功的 tx 总数（含历史） | execute_transaction 成功路径 |
| `tx_failed_total` | Counter | 执行失败的 tx 总数 | execute_transaction 失败路径 |
| `tx_transfers_total` | Counter | Transfer 指令执行次数 | `system_instruction.rs:70` |
| `tx_gas_cycles_used_total` | Counter（累积） | 所有 tx 消耗的 cycles 总量 | cycles_used 累加 |
| `tx_gas_cells_used_total` | Counter（累积） | 所有 tx 消耗的 cells 总量 | cells_used 累加 |

---

### 埋点 5：Verify 阶段

**文件：** `chain/src/application.rs`（已有 verify_duration_ms，补充以下）

| 指标名 | 类型 | 含义 | 实现位置 |
|--------|------|------|---------|
| `verify_sig_check_duration_ms` | Gauge | 批量签名验证耗时 | `application.rs:534` 前后 |
| `verify_leader_fastpath_hits` | Counter | 命中 leader 缓存快路径次数 | 快路径分支 `application.rs:569` |
| `verify_full_execution_count` | Counter | 触发完整重执行次数 | 完整执行分支 `application.rs:599` |
| `verify_execution_duration_ms` | Gauge | 完整重执行耗时（非 leader） | 完整执行路径前后 |

---

### 埋点 6：Report / 上链确认阶段

**文件：** `chain/src/application.rs` + `storage/src/blockchain_storage.rs`

| 指标名 | 类型 | 含义 | 实现位置 |
|--------|------|------|---------|
| `report_apply_cached_batch_duration_ms` | Gauge | apply_cached_batch 总耗时 | `application.rs:663` 前后 |
| `commit_state_db_duration_ms` | Gauge | state_db 三步提交耗时 | `blockchain_storage.rs:289-297` 前后 |
| `commit_tx_index_duration_ms` | Gauge | tx_index 提交耗时 | `blockchain_storage.rs:303-318` 前后 |
| `commit_tx_receipts_duration_ms` | Gauge | tx_receipts 提交耗时 | `blockchain_storage.rs:323-336` 前后 |
| `report_mempool_cleanup_duration_ms` | Gauge | mempool 清理耗时 | `application.rs:679` 前后 |
| `sync_duration_ms` | Gauge | 已有，确认在 blockchain_storage.rs:367 |
| `prune_duration_ms` | Gauge | 已有，确认在 blockchain_storage.rs:402 |
| `blocks_finalized_total` | Counter | 已最终确认的块总数 | `report()` 成功路径 |

---

### 埋点 7：端到端延迟（最关键）

在 RPC 提交时打上 `submission_timestamp`，在 report 确认时计算端到端延迟：

| 指标名 | 类型 | 含义 | 备注 |
|--------|------|------|------|
| `tx_e2e_confirm_latency_ms` | Gauge（滑动最近值） | 最近一笔 tx 从提交到上链的延迟 | 需要跨 RPC→mempool→report 追踪 |
| `block_e2e_latency_ms` | Gauge | 从 propose 开始到 report 完成的块延迟 | propose_start 到 report 完成 |

> 实现方式：在 mempool 入队时记录 `enqueue_time`（存 HashMap<Digest, Instant>），在 report 扫描已确认 txs 时计算差值并更新 Gauge。

---

## 四、具体优化建议（基于埋点数据）

待埋点数据收集后，优先考虑以下优化方向：

| 优化方向 | 预期收益 | 依赖埋点数据 |
|----------|---------|------------|
| 签名验证并行化 (rayon) | Verify 阶段提速 ~10x | `verify_sig_check_duration_ms` |
| 状态读缓存（LRU on get_account） | 减少 I/O，提升执行速度 | `tx_storage_read_total_us` |
| Merkle 增量更新（只更新变更子树） | 减少 merkle_duration | `propose_merkle_duration_ms` |
| QMDB 三 DB 并行提交 | 减少 commit 延迟约 2/3 | `commit_*_duration_ms` 对比 |
| 批量 nonce 检查（RPC 层减少锁） | 提升 submit 吞吐 | `rpc_submit_duration_ms` |
| storage RwLock → propose/verify 流水线 | 减少 verify 等待 propose | `verify_full_execution_count` + 锁等待时间 |

---

## 五、关键文件路径索引

| 阶段 | 文件 | 关键函数 |
|------|------|---------|
| RPC 提交 | `rpc/src/handlers/chain.rs:90` | `submit_transaction()` |
| Mempool | `chain/src/mempool.rs:150` | `Mempool::add()`, `Mempool::next()` |
| Propose | `chain/src/application.rs:358` | `propose()` |
| 推测执行 | `storage/src/speculative.rs:67` | `execute_block_speculative()` |
| 单笔执行 | `execution/src/execution/transaction.rs:18` | `execute_transaction()` |
| Transfer | `execution/src/execution/system_instruction.rs:70` | Transfer match arm |
| Verify | `chain/src/application.rs:498` | `verify()` |
| Report/确认 | `chain/src/application.rs:650` | `report()` |
| 三阶段提交 | `storage/src/blockchain_storage.rs:286` | `commit_batch()` |
| 已有指标 | `chain/src/application.rs:92` | `propose_duration_ms`, `verify_duration_ms` |

---

## 六、验证方式

1. **单元测试中验证指标注册：** 在 `chain/src/application.rs` 的测试中断言所有新指标已注册到 Prometheus registry
2. **集成测试：** 使用 `examples/token` 跑 `./start_all.sh --test`，通过 `GET /metrics` 观察各阶段耗时
3. **基准测试：** 构造 1000 笔 Transfer，测量 propose_duration_ms 各子指标，确认 merkle 化比例
4. **压力测试：** 持续提交 Transfer，观察 `tx_e2e_confirm_latency_ms` 稳定性和 `sync_duration_ms` 周期性尖峰

---

## 注意事项

- 本方案**不修改任何逻辑**，仅增加观测能力
- 高频路径（每笔 tx）避免使用 `Mutex` 保护的计时器，优先 `AtomicU64`
- 现有 `propose_duration_ms` 是总时，新增的细分指标应与其加和一致，方便交叉验证
- Gauge 存最近值，Counter 累积历史，按需选择
