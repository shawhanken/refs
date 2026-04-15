# Validator 静默停滞 — 根因分析报告

> **日期**: 2026-04-11  
> **严重等级**: Critical — 链永久停止出块  
> **受影响版本**: v0.0.24 (main `5f4e0d9`), devnet `ac45dbd`  
> **可复现性**: 100%，精确在 ~10,085 区块

---

## 1. 现象

单节点 validator 运行约 10,000 区块（~3 小时）后静默停止出块。进程存活，`/block/latest` 超时，无任何错误日志。唯一恢复方法是完整清除数据库后重启。

停滞后，文件描述符和 consensus journal 文件持续飙升（35 分钟内从 ~350 增长到 2,400+），表明共识层仍在推进 view 但无法出块。

## 2. 复现数据

我们在服务器上分别用 main 分支和 devnet 分支进行了两轮完整复现测试：

| 指标 | 客户报告 | main 分支复现 | devnet 复现 |
|------|---------|-------------|------------|
| 停滞区块高度 | ~10,100 | **10,086** | **10,085** |
| 运行时间 | ~3 小时 | 2h49m | 2h49m |
| 停滞前延迟 | — | 7ms | 6ms |
| 停滞后延迟 | 超时 | 超时 | 超时 |
| 进程存活 | 是 | 是 | 是 |
| 错误日志 | 无 | 无 | 无 |

### 监控时间线（main 分支）

```
12:42:08 | height=10086 | latency=7ms     | fd=345  | consensus=263  ← 最后正常
12:42:38 | height=TIMEOUT | latency=10003ms | fd=358  | consensus=283  ← 瞬间死锁
13:17:19 | height=TIMEOUT | latency=10003ms | fd=2419 | consensus=2345 ← 持续恶化
```

**关键特征**：从完全正常（7ms）到完全死亡（TIMEOUT）是**瞬间跳变**，没有任何渐进恶化的过渡期。这是死锁的典型特征，不是性能退化。

## 3. 根因分析

### 3.1 背景：receipt pruning 的引入

4月3日，bench 压测中发现 validator 内存以 15~40 MB/s 速率持续增长，原因是 QMDB 的 transaction receipt cache 累积（与此前已修复的内存泄漏不同，此次是因为链空跑时不可观察到该现象）。

为解决此问题，引入了 receipt pruning 机制：将超过 10,000 个区块历史的完整 transaction 数据精简为仅保留 `tx_hash`，实现分层式查询。该机制通过 `sync_storage` 闭包在 `report()` 中被周期性调用。

对应代码常量：
```rust
const SYNC_INTERVAL_BLOCKS: u64 = 100;    // 每 100 区块触发 sync
const KEEP_RECEIPTS_BLOCKS: u64 = 10_000;  // 保留最近 10,000 区块的 receipt
```

### 3.2 根因：双层死锁

问题的根因是**两层死锁叠加**，而 devnet 修复只解除了其中一层。

#### 第一层死锁：storage write lock + marshal.get_block()（devnet 已修复）

在 main 分支的 `prune_old_receipts_batch()` 中（`storage/src/process_block.rs`）：

```rust
// 调用路径: report() → sync_fn() → sync_storage 闭包
{
    let mut storage = storage.write().await;     // ← 持有 storage write lock
    storage.prune_old_receipts_batch(...)         // ← 内部调用 marshal.get_block()
        // marshal 的某些内部任务也需要 storage lock
        // → 互相等待 → 死锁
}
```

Devnet 修复将其拆分为三阶段（plan/fetch/delete），确保调用 `marshal.get_block()` 时不持有任何 storage lock。

#### 第二层死锁：marshal actor 自死锁（devnet 未修复）

即使释放了 storage lock，`marshal.get_block()` 仍然在 `report()` 的执行路径中被调用。而 `report()` 本身运行在 marshal actor 的事件循环中：

```rust
// application.rs — report() 方法
impl Reporter for Application {
    async fn report(&mut self, activity: Self::Activity) {
        // ...
        ack_rx.acknowledge();  // 释放共识 voter

        // sync_fn() 仍然是同步 await
        match sync_fn().await {  // ← 整个闭包在 marshal 事件循环内执行
            // sync_fn 内部 Phase 2 调用了 marshal.get_block()
            // 但 marshal 正忙于执行 report()，无法处理 get_block() 请求
            // → actor 自死锁
        }
    }
}
```

死锁形成过程：

```
┌──────────────────────────────────────────────────────────┐
│                marshal actor 事件循环                      │
│                                                          │
│  正在执行: report()                                       │
│    → sync_fn().await                                     │
│      → Phase 2: marshal.get_block(height)                │
│        → 向 marshal mailbox 发送 GetBlock 请求             │
│        → 等待 marshal 处理并返回结果                        │
│                                                          │
│  mailbox 队列: [GetBlock 请求等待处理]                      │
│  但 marshal 正忙于 report()，无法取出并处理新消息            │
│                                                          │
│  → get_block() 永远不会返回                                │
│  → report() 永远不会返回                                   │
│  → marshal 永久死锁                                       │
└──────────────────────────────────────────────────────────┘
```

这是经典的 **actor 自死锁**：一个 actor 在自己的消息处理函数中向自己发送了同步消息，但单线程事件循环无法在处理当前消息的同时处理新消息。

### 3.3 为什么精确在 ~10,100 区块触发？

`KEEP_RECEIPTS_BLOCKS = 10_000`。当区块高度 ≤ 10,000 时：

```rust
let prune_up_to = current_height.saturating_sub(10_000); // = 0
if self.receipt_prune_cursor >= prune_up_to {
    return Ok(0); // 直接返回，不执行任何操作
}
```

前 10,000 个区块，receipt pruning 逻辑**直接 return，不调用 `marshal.get_block()`**，因此不会触发死锁。

高度超过 10,000 后，首次进入循环调用 `marshal.get_block()` → **立即触发死锁**。触发时机 = 10,000 + `SYNC_INTERVAL_BLOCKS` 的对齐偏移 ≈ 10,085~10,100。

### 3.4 停滞后为什么 FD 和 consensus 文件飙升？

Marshal 死锁后：
- Consensus voter 仍在运行，需要从 marshal 获取 parent block 来 propose
- Marshal 无法响应 → propose 超时 → voter 推进到下一个 view
- 每次 view 推进在 `engine-consensus/` 目录写入新的 journal 文件
- 文件无限增长，直到耗尽文件描述符限制

### 3.5 为什么 `ack_rx.acknowledge()` 在 sync 之前调用不能解决问题？

代码注释（第 731-732 行）写道：

> *"Acknowledge consensus finalization before sync so that QMDB sync/prune latency never stalls the consensus loop."*

这个设计意图是：先通知 voter "区块已处理"，让它推进。但 `acknowledge()` 只释放了 **consensus voter**，没有释放 **marshal actor**。Marshal 仍然在等 `report()` 返回后才能处理下一条消息。

## 4. 两轮测试验证

### 测试环境

- 服务器: cowboy-003
- Runner: main 分支 `83b3e70`

### 测试一: main 分支（基准）

| 项目 | 值 |
|------|-----|
| Node commit | `5f4e0d9` (main) |
| 启动时间 | 09:53 Apr 11 |
| 停滞时间 | 12:42 Apr 11 |
| 停滞高度 | **10,086** |
| 结论 | 💀 死锁复现 |

### 测试二: devnet 分支（修复验证）

| 项目 | 值 |
|------|-----|
| Node commit | `ac45dbd` (devnet) |
| 启动时间 | 16:56 Apr 11 |
| 停滞时间 | 19:45 Apr 11 |
| 停滞高度 | **10,085** |
| 结论 | 💀 死锁仍在，修复无效 |

**结论**：devnet 的 receipt pruning 锁拆分修复只解除了第一层死锁（storage lock），第二层死锁（marshal actor 自死锁）仍然存在，问题完全没有改善。

## 5. 修复方向

根因明确后，有两个修复方向：

### 方案 A：将 `sync_fn()` spawn 到后台（推荐）

在 `report()` 中将整个 `sync_fn()` 用 `tokio::spawn` 移到后台执行，`report()` 在 `ack_rx.acknowledge()` 后立即返回：

```rust
// report() 中
ack_rx.acknowledge();

if height >= self.last_sync_height + SYNC_INTERVAL_BLOCKS {
    self.last_sync_height = height;
    let sync_fn = sync_fn.clone();
    tokio::spawn(async move {
        sync_fn().await;  // 在后台 tokio 任务中执行，不阻塞 marshal
    });
}
// report() 立即返回 → marshal 解除阻塞
```

**优点**：marshal 事件循环完全不受 sync 影响，彻底解决两层死锁。  
**代价**：sync 失败时 `height.dat` 可能滞后，下次重启多 replay 一些 journal（可接受）。

### 方案 B：将 `marshal.get_block()` 调用完全移出 `report()` 路径

将 receipt pruning 中需要的区块数据通过其他方式获取（如缓存 finalized block 的 tx_hash），避免在 `report()` 中调用 `marshal.get_block()`。

**优点**：不改变 sync 的同步语义。  
**缺点**：需要额外的缓存管理逻辑。

## 6. 总结

| 维度 | 结论 |
|------|------|
| **触发原因** | 4/3 为解决 bench 压测内存增长问题，引入了 receipt pruning 机制 |
| **根因** | 双层死锁：①持 storage lock 调 `marshal.get_block()`；②`report()` 在 marshal 事件循环中调 `marshal.get_block()`（actor 自死锁） |
| **触发时机** | 精确在 height > `KEEP_RECEIPTS_BLOCKS` (10,000) 后首次 sync 时 |
| **devnet 修复** | 只解了第一层死锁（释放 storage lock），第二层 actor 自死锁仍在 |
| **devnet 验证** | ❌ 仍在 10,085 区块死锁，修复无效 |
| **推荐修复** | 将 `sync_fn()` 用 `tokio::spawn` 移到后台执行 |
