# Validator 10100 停滞 —— 根因确认与彻底修复方案

## Context

**问题**：单节点 validator 在约 10,100 区块处 100% 可复现静默停滞。进程存活，consensus 仍在推进 view，但无法再产出任何区块。

**历史**：
- 4 月 3 日 commit `871783e` 为解决 bench 压测时的内存增长问题，引入 `prune_old_receipts_batch`，在 `report()` 中周期触发。
- 我之前在 `performance_optimize` 和 `devnet` 都做过"三阶段 receipt pruning"修复，把 `marshal.get_block()` 挪出 storage 写锁。
- 该修复**在 devnet 实测中仍然停在 10,085**（用户另找 Claude Opus 做的分析报告在 `/home/ubuntu/workspace/refs/202604/20260411_Validator_Stall_Root_Cause_Analysis.md`，也在当前 `test/validator.log` 里再次确认：最后 `applied cached batch height=10100 @ 09:24:31`，30 秒后一条 `finalized block upload timed out`，之后完全静默）。

**目标**：一次性彻底解决这个死锁，不留第二层；修复要在 deterministic test runtime 和生产 tokio runtime 上都能跑。

---

## RCA 报告评估：**值得借鉴，核心论断 100% 正确**

报告声称两层死锁叠加，devnet 只解了第一层。**我亲自追溯源代码（两路 Explore agent + 本地 Read）对每一条都做了独立验证**，结论如下：

| RCA 断言 | 我的验证 | 结果 |
|---------|---------|------|
| `Application::report()` 运行在 marshal actor 的 select_loop 内，内联 `.await` | `~/.cargo/registry/.../commonware-consensus-2026.3.0/src/marshal/core/actor.rs:1232-1234` 中 `try_dispatch_blocks()` 里就是 `application.report(Update::Block(..., ack)).await` 直接内联，调用点在 actor 的 `select_loop!` 第 404 行（启动）和第 482 行（`pending_acks.current()` arm）。没有 spawn。 | ✅ 证实 |
| `marshal.get_block()` 是通过 mailbox 发 `Message::GetBlock` 消息给同一个 actor 的 | `marshal/core/mailbox.rs:165-177` 实现就是 `self.sender.request(\|response\| Message::GetBlock { identifier, response }).await`；接收处理在 `actor.rs:586-607` 同一个 `select_loop!` 的 `mailbox.recv()` arm。 | ✅ 证实 |
| 因此 `report()` 里同步 `await` `marshal.get_block()` 会 actor 自死锁 | 两者都在同一个任务的同一个 `select_loop!` 里。当任务被 `try_dispatch_blocks().await` 阻塞时，它自己的 mailbox 不会被 poll，`Message::GetBlock` 的 oneshot 永远收不到响应。经典单线程 actor 自死锁。 | ✅ 证实 |
| `KEEP_RECEIPTS_BLOCKS=10_000` 解释了为什么刚好卡在 ~10,100 | `chain/src/application.rs:62,64,66`：`SYNC_INTERVAL_BLOCKS=100`、`KEEP_RECEIPTS_BLOCKS=10_000`、`RECEIPT_PRUNE_BATCH=200`。height ≤ 10_000 时 `prune_up_to = 0`，cursor(0) ≥ 0 立即返回，不触发 get_block；首次超过 10_000 后的 `SYNC_INTERVAL_BLOCKS` 对齐点才进入 fetch 循环 → 首次触发死锁。 | ✅ 证实 |
| devnet 的三阶段拆分只解了第一层（storage write lock），第二层 actor 自死锁仍在 | 三阶段拆分确实释放了 storage 锁，但 Phase 2 的 `marshal.get_block().await` 依旧在 `sync_fn` 里、依旧在 `report()` 的 `.await` 链上、依旧在 marshal actor 的 event loop 里。停滞点完全重现。 | ✅ 证实 |
| `ack_rx.acknowledge()` 只释放 consensus voter，不释放 marshal | 代码注释就是这么写的（`application.rs:777-779`："Acknowledge consensus finalization before sync so that QMDB sync/prune latency never stalls the consensus loop"）—— 它关心的是 voter，不是 marshal actor。 | ✅ 证实 |

**额外观察**（日志对应）：
- 停滞后 marshal 挂起 → consensus voter 继续推进 view → 每次 view 推进 → `engine-consensus/` 新写 journal 文件 → fd 和磁盘飙升。RCA 报告提到的 "fd 35 分钟内从 350→2400"、日志里最后出现的 `view=670228` 都吻合这条链路。

**RCA 报告的两个方案评估**：
- **方案 A（spawn `sync_fn` 到后台）** —— 根治：彻底让 marshal actor 不再 blocked on sync。推荐。*但报告里写的 `tokio::spawn` 在 deterministic 测试 runtime 下会 panic*（`commonware_runtime::deterministic::Runner` 不是 tokio），需要用 commonware 的 `Spawner` trait。
- **方案 B（把 marshal.get_block 挪出 sync 路径）** —— 也能解这一具体死锁，但不治本：`report()` 里任何未来的慢操作（QMDB sync 本身可能慢、prune_all 可能慢）都仍然会阻塞 marshal actor。

**我的选择：方案 A + 用 commonware Spawner 重写，保留 devnet 的三阶段 pruning**。理由：
1. 三阶段 pruning 独立正确、有独立价值（防止 storage-lock ABBA），没理由回退。
2. 把整个 `sync_fn` 异步化才是真正把 `report()` 从 marshal 热路径上切走，以后加任何 sync-side 工作（pruning、compaction、cold state migration）都不会再复发。
3. commonware Spawner 是本仓库现有模式（`chain/src/indexer.rs` 的 `Pusher` 已经这么做），兼容 deterministic 测试 runtime。

---

## 彻底修复方案

### 设计

在 `Application::with_mempool_and_storage` 构造时，spawn **一个** 长期运行的 sync-worker 后台任务，通过一个容量为 1 的 bounded mpsc channel 接收 `report()` 发来的 height 触发信号：

```
report() [marshal actor loop]        sync-worker [independent task]
  │                                    │
  │  ack_rx.acknowledge()              │  loop {
  │                                    │    let height = rx.recv().await?;
  │  if due_for_sync {                 │    // 整个 sync_storage 闭包体
  │    sync_tx.try_send(height):       │    //   sync_all + prune_all +
  │      Ok  → last_sync_height=H      │    //   三阶段 receipt prune
  │      Full → skip, 下块再试         │    //   （Phase 2 安全调 get_block）
  │    }                               │    write_height(height)
  │  }                                 │  }
  │  return  ← ★ 立即返回              │
  ▼                                    ▼
```

**关键设计点**：

1. **Channel 容量 = 1**：任一时刻最多一个 sync 排队。如果 worker 还在跑上一轮，`try_send` 返回 `Full`，`report()` 就直接跳过（不阻塞），下一个 block 再试。完美匹配 "best-effort periodic sync" 的语义。

2. **`last_sync_height` 只在 send 成功时推进**：如果上次 send 失败（worker 忙），下一个 block 会重试，不会跳过整整 100 个区块的间隔。

3. **`height.dat` 写入搬到 worker 里**：原本在 `report()` sync 成功后同步写，现在由 worker 在 sync 成功后写。语义保持不变（都是 sync 完成后才写）。

4. **Spawner trait 用现有的 `commonware_runtime::Spawner`**：在 `with_mempool_and_storage` 的 `E` 约束上加 `+ Spawner + Clone`。engine.rs:186 的 E 本身已经满足（`... + Spawner + ...`），所以调用点无需改。

5. **三阶段 receipt pruning 保持不变**：同样的 `plan → marshal fetch → short write commit` 结构，但这次是在 worker 任务里跑。worker 本身**不是** marshal actor，所以 Phase 2 的 `marshal.get_block().await` 是一个普通跨任务消息，mailbox 可以正常 drain，不会自死锁。

6. **channel 类型用 `tokio::sync::mpsc::channel::<u64>(1)`**：tokio 的 channel 不依赖 tokio runtime（只用 waker），在 deterministic runtime 里也能跑。本文件已经 `use tokio::sync::Mutex`，所以加个 mpsc 不会引入新依赖。

### 文件改动

**1. `chain/src/application.rs`**

(a) 新 import / use（顶部）：
```rust
use commonware_runtime::Spawner; // 加到现有 commonware_runtime 的 use 中
use tokio::sync::mpsc;
```

(b) 替换字段 `sync_storage: Option<SyncStorageFn>` → `sync_tx: Option<mpsc::Sender<u64>>`。删除 `SyncStorageFn` 类型别名（只有一个使用点）。

(c) 修改 `with_mempool_and_storage` 签名（第 174 行）：
```rust
pub fn with_mempool_and_storage<
    E: Storage + Clock + Metrics + BufferPooler + Spawner + Clone,
>(
    context: &E,   // 去掉下划线，开始真正使用
    mempool: Arc<Mutex<Mempool>>,
    storage: Arc<tokio::sync::RwLock<BlockchainStorage<E>>>,
    height_file_path: Option<PathBuf>,
    tx_metrics: Arc<TxLifecycleMetrics>,
) -> Self
```

(d) 在构造体内、替换原有 `sync_storage` 闭包（现在的第 244-315 行）为：
  - 建一个 `(sync_tx, mut sync_rx) = mpsc::channel::<u64>(1);`
  - 把现有 closure body（sync_all + prune_all + 三阶段 receipt prune）封装成一个本地 `async` 块或 inner async fn，捕获 `storage.clone()` 和 `height_file_path.clone()`。
  - 通过 `context.with_label("sync_worker").spawn(move |_ctx| async move { while let Some(height) = sync_rx.recv().await { ... do sync body ...; if Ok, write height.dat } })` 启动 worker。
  - 存 `sync_tx` 到 `Self { sync_tx: Some(sync_tx), ... }`。

(e) 修改 `report()`（第 785-811 行）为非阻塞 dispatch：
```rust
let height = block.height.get();
if let Some(sync_tx) = &self.sync_tx {
    if height >= self.last_sync_height + SYNC_INTERVAL_BLOCKS {
        match sync_tx.try_send(height) {
            Ok(()) => {
                self.last_sync_height = height;
            }
            Err(mpsc::error::TrySendError::Full(_)) => {
                // sync-worker 仍在处理上一轮，下块再试
                warn!(
                    height,
                    "sync worker busy; deferring periodic sync to next block"
                );
            }
            Err(mpsc::error::TrySendError::Closed(_)) => {
                error!(
                    height,
                    "sync worker channel closed; periodic sync permanently disabled"
                );
            }
        }
    }
}
// height.dat 写入不再在 report 里；已移入 worker。
```

(f) `Application::new` / `with_mempool` 里把 `sync_storage: None` 改成 `sync_tx: None`，其它无变化。

**2. `storage/src/process_block.rs`** —— 用户决定保留 `prune_old_receipts_batch`（修复后该方法将完全无 caller）：
- 在现有 `DEADLOCK WARNING` doc 之上加 `#[deprecated(note = "...")]` 属性，编译期就提醒任何未来的调用者去看 application.rs 的三阶段 worker pattern。
- 不删除函数体（避免本次改动过大、避免影响其它人未提交的本地分支），但通过 `#[allow(deprecated)]` 让现有的 prune_batch_range / prune_receipts 单元测试还能跑。

**3. 没有其它文件需要改动**。`engine.rs` 的 `E` 已经有 `Spawner`，无需动。测试、CLI、RPC 都不直接构造 Application。

**4. 范围：仅 devnet 分支**（用户决定）。修复在 devnet 上验证有效后，再单独考虑 backport 到 main 和 performance_optimize。

### 正确性论证（逐条对应死锁链）

| 死锁环节 | 修复前 | 修复后 |
|---------|--------|--------|
| marshal actor loop 被 `report()` 占用 | `application.report().await` 内联执行整个 sync，marshal 无法 drain mailbox | `report()` 里 sync 只是一个 `try_send` 非阻塞调用，立即返回；marshal loop 立即回到 `select_loop!` 处理下一条消息 |
| `marshal.get_block()` 是给 marshal 自己发消息 | 发送成功但 oneshot 永不 fulfill | worker 是独立任务，发送后 marshal loop 自由处理 `Message::GetBlock`，正常返回 |
| storage write lock + marshal 的 ABBA | devnet 的三阶段拆分已解决 | 三阶段仍保留在 worker 里，继续生效 |
| 多次并发 sync 争 storage lock | — | channel 容量 1 保证任一时刻至多一个 sync 在跑；不会并发 |
| sync 失败后 retry 语义 | 失败时 `last_sync_height` 不推进，下块重试 | try_send 失败时 `last_sync_height` 不推进，下块重试；worker 内部 sync 失败时只 warn，由下次触发自然恢复 |
| `height.dat` 与 QMDB sync 的 lock-step | sync 完才写 | 同样：worker 内 sync 成功后才写 |

### 关键风险与应对

1. **生命周期/取消**：sync-worker 是 spawned 的，engine 停机时如何让它退出？
   - 当 Application 被 drop，`sync_tx` 随之 drop；worker 里 `sync_rx.recv().await` 返回 `None`，while 循环退出，任务自然结束。干净。

2. **worker panic**：如果 worker 里某次 sync panic，channel 的 receive 端会 drop，后续 `try_send` 返回 `Closed` → `report()` 里 `error!` 日志，sync 永久禁用但 consensus 不受影响。可接受，且会被监控看见。

3. **deterministic 测试兼容性**：
   - `tokio::sync::mpsc` 只用 waker，不需要 tokio runtime。
   - `commonware_runtime::Spawner::spawn` 在 deterministic runtime 下就是把 future 放到 runtime 的任务列表。
   - 现有 `indexer.rs` 的 `Pusher` 已经在同一个代码库、同一套测试里用这个 pattern 跑过，可以照搬。

4. **高度推进导致 worker 背压**：如果 sync 真的非常慢（比如 prune_all 在大库上要 > 100s），worker 会持续 busy，report() 的每次 `try_send` 都会 Full，sync 就不断跳过。这比现在（卡死）好得多；如果 sync 持续背压，可以通过日志看到 "sync worker busy" 频率。

5. **三阶段 pruning 里 Phase 3 把 write lock 和 marshal 的交互**：worker 调用 `storage.write().await` 和 `marshal.get_block().await` 的顺序和 devnet 版完全一致（Phase 1 短 read lock → Phase 2 无锁 get_block → Phase 3 短 write lock），不会退化。

### 为什么不采用其他方案

- **把 `marshal.get_block()` 完全挪出 sync 路径**（缓存 tx_hashes 到 application 侧）：
  - 需要新的持久化/重建机制（重启后缓存空，第一次 sync 又拉不到数据），复杂度高。
  - 不能解决 report() 里其它慢操作的未来风险。
- **用 `tokio::spawn` 直接 spawn sync**：测试 runtime 是 deterministic，不是 tokio，`tokio::spawn` 会 panic。RCA 报告里的样例代码是简化版，不能直接用。
- **把 `try_dispatch_blocks` 本身 spawn 出去**：需要改 commonware-consensus 源码，不可行（是第三方 crate）。

---

## 要修改的关键文件

| 文件 | 行号范围 | 改动 |
|------|---------|------|
| `chain/src/application.rs` | 1-28 | 加 `use commonware_runtime::Spawner;` 和 `use tokio::sync::mpsc;` |
| `chain/src/application.rs` | 50-56 | 删除 `SyncStorageFn` 类型别名 |
| `chain/src/application.rs` | 77-78 | 字段 `sync_storage: Option<SyncStorageFn>` → `sync_tx: Option<mpsc::Sender<u64>>` |
| `chain/src/application.rs` | 128-168 | `new()` / `with_mempool()` 里的 `sync_storage: None` → `sync_tx: None` |
| `chain/src/application.rs` | 170-180 | `with_mempool_and_storage` 签名加 `+ Spawner + Clone`，`_context` → `context` |
| `chain/src/application.rs` | 244-315 | 用 channel + spawned worker 替换现有 `sync_storage` closure 的构造 |
| `chain/src/application.rs` | 270-287 | 构造体字段初始化改用 `sync_tx` |
| `chain/src/application.rs` | 785-811 | `report()` 里的 `sync_fn().await` match 替换为 `try_send` 非阻塞 dispatch |
| `storage/src/process_block.rs` | 116-130 | **保持不变**（`DEADLOCK WARNING` 文档 + 现有 `prune_old_receipts_batch` 方法，现在是 dead code，先不删） |

**可复用的现有设施**：
- `commonware_runtime::Spawner` trait 和 `context.with_label("label").spawn(move |ctx| async move { ... })` pattern —— 见 `chain/src/indexer.rs:395-426` (`Pusher::handle` 用这个 spawn notarized_block upload)。
- `height_recovery::write_height(path, height)` —— 见 `chain/src/application.rs:795`，worker 内直接复用。
- `tokio::sync::mpsc::channel` —— 已被 `tokio::sync::Mutex` 带进 namespace (`application.rs:27`)。

---

## 验证计划

### 单元/组件测试

1. `cargo check -p cowboy-chain` —— 编译干净通过。
2. `cargo test -p cowboy-storage --lib -- prune` —— 13 个 prune 相关测试全过（三阶段 receipt prune 的纯算术 helper）。
3. `cargo test -p cowboy-chain --lib` —— 包括 `tests::test_backfill`、`tests::test_unclean_shutdown`、`tests::test_good_links`、`tests::test_bad_links`、`tests::test_200`；重点关注这些在 deterministic runtime 上跑的 end-to-end 共识测试——它们会调用 `Application::report()` 很多次，如果 worker spawn 或 channel 语义有问题会立刻暴露。

### 端到端复现验证

4. 彻底清 test/ 数据重启单节点：
   ```bash
   cd /home/ubuntu/workspace/node
   ./scripts/run_build.sh        # 重新构建 + 生成 genesis
   ./scripts/start_validator.sh
   ```
5. 跑到至少 11,000 区块高度（保证跨过首次 `prune_up_to > 0` 的 sync 周期）。
6. 监控脚本（用户已有）应看到：
   - `height` 持续推进，**不会**卡在 10,100 附近。
   - `fd` 和 `engine-consensus/` 目录文件数稳定，不再无限膨胀。
   - 日志里定期出现 `pruned old receipts and indices pruned_count=...`（sync-worker 在工作）。
   - 偶尔可能出现 `sync worker busy; deferring periodic sync to next block`（正常背压），但不应连续出现超过 1-2 次。

### 专项检查

7. `grep 'periodic storage sync failed' test/validator.log` —— 不应有。
8. `grep 'sync worker channel closed' test/validator.log` —— 绝对不应有（这表示 worker 崩了）。
9. `ps -o pid,vsz,rss,cmd -p $(pgrep validator)` 长跑一小时 —— RSS 应稳定（三阶段 prune 正常工作），不会像之前 fd/consensus 那样暴涨。
10. 另找第二台机器重复第 4-6 步，独立复现成功 → 最终确认。

### 异地并行测试建议

用户之前提到在另一台服务器同样卡 10,100。修复上线后建议：
- 在主机 A 跑 main+fix，跑到 12,000+ 高度；
- 同时在主机 B 跑 devnet+fix（两分支都应打上同样的修复），跑到 12,000+ 高度；
- 两台都不再停滞，才宣告彻底解决。

---

## 交付约束（用户明确要求）

- 按 CLAUDE.md：commit message 不加 AI 署名。
- 改动要真正彻底解决（不像上次只修了表层），并且不引入新 bug。
- 用户对前次修复感到失望；这次方案必须在我执行前说明清楚，得到用户确认。

**状态**：等待用户批准 exit plan 并开始实施。
