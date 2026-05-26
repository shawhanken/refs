# 链上事件钩子（On-chain Event Hooks）提案

## 一、动机

### 1.1 当前缺口

以太坊的 "事件" 在合约语义上只是日志写入——所有真正的订阅与响应必须发生在 off-chain（indexer、relayer、bot）。这意味着任何"基于事件触发的链上响应"都需要至少一个 off-chain 中介，引入信任与延迟。

我们已有的原语：

- `call()`：同步、原子、定向——调用方完全决定被调用方
- `send()`：异步、定向、跨块投递——单点对单点
- `defer transaction`：未来块或显式触发——延迟执行
- `timer`：系统调度的定时触发

这套原语**缺少一种"多订阅者、同 tx 同步触发、订阅者失败不影响触发方"的事件原语**——对应 EVM 中常用的 `try { external.call(...) } catch { ... }` 模式。

### 1.2 旗舰用例：抢清算（pre-liquidation）

DeFi 借贷协议中典型的级联：

1. 用户 A 用 ETH 抵押借出稳定币
2. 链上某笔 swap 把 ETH 价格压到 A 的清算线以下
3. 清算逻辑被触发，A 的抵押品进入清算流程
4. 流动性提供方 B/C/D 之前订阅了 "A 触发清算" 这个事件
5. **B/C/D 必须在该笔 swap tx 内、清算执行之前**拿到一次响应窗口——否则就被清算人先一步吃掉差价

这件事在以太坊上做不到链上原生：B/C/D 只能跑 off-chain bot 监听 mempool / pending logs，再以 MEV 形式抢提交。这恰好是我们能切的差异化：**把订阅与响应做成链上同 tx 内同步原语**。

更广义的同类用例：

- 价格预言机更新 → 多个依赖该价格的合约同 tx 重新评估状态
- DAO 投票通过 → 多个执行模块同 tx 同步落地
- NFT mint → 多个市场/索引合约同 tx 反映库存

### 1.3 设计原则

- **同 tx 同步**：钩子在 emit 调用栈内同步执行完毕，emitter 拿回控制权时所有订阅者已运行
- **失败隔离**：单个订阅者失败（panic / OOG / revert）不影响 emitter 也不影响其他订阅者
- **复用而非重建**：底层走既有 cross-actor call 路径，复用 PVM snapshot、QMDB 单库存储、cycle/cell 计费
- **不动跨块不变量**：propose/verify 共享路径、tx_root ↔ receipt 一对一映射、basefee 反馈、admission gate、lane 隔离全部保持不变

## 二、提案

### 2.1 核心抽象

引入下列协议级原语：

```python
# emitter 侧
rt.emit_event(topic: bytes, payload: bytes) -> EmitResult
    # payload 长度受 MAX_EVENT_PAYLOAD_BYTES 限制（默认 4096），超出直接报错
    # payload bytes 按 1 cell/byte 计入 emitter cells（与 calldata 计费一致）
    # EmitResult 包含本块内同步 fire 的结果列表 + 溢出排队到 H+1 的 sub_id 列表
    # 排序：按 bid 降序，前 MAX_SYNC_FIRES_PER_TOPIC 名同步 fire，其余拆成多条 system defer tx

rt.force_unsubscribe_event(sub_id: SubscriptionId) -> ()
    # 仅 emitter 自己可调用；用于驱逐
    # gas_remaining 与已占 cells 全额退还给订阅者（emitter 一分不出、一分不收）
    # bid 已沉没、不退（见 §2.6）

# subscriber 侧
rt.subscribe_event(
    emitter: ActorAddr,
    topic: bytes,
    handler: str,
    gas_prepaid: u64,
    bid: u64 = 0,                        # 竞价金额，决定排名；0 表示纯先到先得（落到所有 bid 之后）
) -> SubscriptionId
    # 订阅者一次性扣四笔：
    #   - SUBSCRIPTION_REGISTRATION_FEE  cycles  （写入算力，不退）
    #   - delta cells                            （EventSub 记录 + 索引条目增量；unsubscribe / reap 时全额退）
    #   - gas_prepaid                    cycles  （fire 预付池，剩余可在 unsubscribe 时退）
    #   - bid                            cycles  （已沉没，不退；记入订阅记录的 bid 字段）

rt.update_bid(sub_id: SubscriptionId, additional_bid: u64) -> u64
    # 仅订阅者本人可调用；追加 bid（不能下调）；返回新的累计 bid
    # 立即生效，重新排序到 (emitter, topic) 的有序索引中
    # 注意：对于已在当前 tx 内 emit 时锁定排名的异步段，update_bid 不影响该次 emit 的 fire 顺序——
    #       新 bid 只对该订阅在后续 emit 中的排名生效（见 §2.3 异步段顺序锁定）

rt.topup_subscription(sub_id: SubscriptionId, additional_gas: u64) -> u64
    # 任何账户都可为订阅充值 gas_remaining；返回 top-up 后的新余额
    # 充值不退、不影响 bid 与 REGISTRATION_FEE；用于让长期订阅在 gas_remaining 耗尽前续命
    # 充值方支付 additional_gas cycles 进入订阅预付池

rt.unsubscribe_event(sub_id: SubscriptionId) -> u64
    # 仅订阅者本人可调用；返回退还的 gas_remaining
    # 同时退还订阅占用的 cells；SUBSCRIPTION_REGISTRATION_FEE 与 bid 不退
```

订阅者注册时**预存订阅 gas budget**（存在订阅记录里，与 timer 的 pre-fund 模式一致），可选附带 `bid` 作为优先权出价。`emit_event` 执行时由 PVM host 按 bid 降序读取订阅索引：

- **前 `MAX_SYNC_FIRES_PER_TOPIC` 名（默认 64）**：在 emitter 调用栈内同步 fire，每个订阅者用 snapshot 包一层，失败回滚订阅者状态、保留 emitter 状态、继续下一个。
- **第 K+1 名及以后**：自动 fork 成 `defer transaction`，在 `H+1` 块按相同 bid 顺序异步 fire（走现有 defer 子系统，不新增执行通道）。

这构成 **同 tx 同步 + 跨块异步** 的分层执行模型——总订阅者上限提到 `MAX_SUBSCRIBERS_PER_TOPIC = 512`，付得起 bid 的拿到清算抢权的同步窗口，其余订阅者通过下一块异步 fire 仍能拿到通知。

**退出路径**有三种，区别对待：

| 路径 | 触发者 | cycles (gas_remaining) | bid | cells |
|---|---|---|---|---|
| 订阅者主动 unsubscribe | 订阅者本人 | 全额退；`REGISTRATION_FEE` 不退 | **不退（沉没）** | 全额退订阅者 |
| `gas_remaining` 耗尽自动失效 | 协议（lazy GC，见 §2.3） | 无余额可退 | 不退（已沉没） | 全额退订阅者（不归 reaper） |
| emitter 强制移除 | emitter 合约 | 全额退订阅者；emitter 不得分得 | 不退；emitter 不得分得 | 全额退订阅者；emitter 不得分得 |

**核心非对称设计**：cycles 类成本（`REGISTRATION_FEE` 与 `bid`）一次性沉没——前者遏制 register/unregister churn，后者防止"抢拍位次 → 立刻退订 → 免费占位"攻击；`gas_remaining`（实际 fire 预算）按使用扣、剩余可退；cells（存储）是可恢复占用，清理时全额返还订阅者。emitter 在所有路径下都不出 cells、也不收任何 cycles——`EventSub` / `EventSubIndex` 走自有 prefix，订阅成本与 emitter 完全解耦，bid 流向 burn pool 而非 emitter（杜绝 emitter 通过竞价市场抽租）。

### 2.2 数据结构

#### 存储底座

所有状态走单 QMDB，统一 54 字节定长 key：`[1B prefix][20B address][33B slot]`（参 `storage/src/state_key.rs`）。已有 prefix 编到 `0x13`，下一个可用是 `0x14`。

订阅清单需要支持两种查询路径：

1. **emit 时**：`(emitter, topic) → 订阅者有序列表`（决定 fire 顺序）
2. **subscribe / unsubscribe / 扣 gas 时**：`sub_id → 单条订阅记录`（直接定位、原地更新 `gas_remaining`）

#### 新增 StatePrefix

仿照既有的 `Timer`(`0x05`) + `TimerIndex`(`0x06`) 双 prefix 模式，新增两个：

```
StatePrefix::EventSub      = 0x14    // 单条订阅记录（按 sub_id 直接定位）
StatePrefix::EventSubIndex = 0x15    // (emitter, topic) → 订阅者有序索引
```

**订阅记录**（按 `sub_id` 直接定位）：

```
key   = 0x14 || sub_id (33B)
value = ActorEventSubscription {
    emitter_addr:  Address,
    topic:         BoundedBytes<64>,
    subscriber:    Address,
    handler_name:  BoundedString,
    gas_prepaid:   u64,                  // 注册时预付的总配额
    gas_remaining: u64,                  // 当前剩余；耗尽即失效
    bid:           u64,                  // 累计 bid（不可下调，update_bid 只能 +）；已沉没，决定排名
    sub_height:    BlockHeight,
}
```

**订阅索引**（按 `(emitter, topic)` 一次性拿到所有订阅者，按 fire 顺序排）：

```
key   = 0x15 || keccak256(emitter_addr || topic)[..33]
value = Vec<(bid_inv: u64, sub_height: u64, sub_id: SubscriptionId)>
    // bid_inv = u64::MAX - bid，保证高 bid 排在前
    // 排序键：(bid_inv, sub_height, sub_id) 字典序
    //   ⇒ bid 高者优先；同 bid 按时间顺序；时间相同按 sub_id 决断
```

#### 设计要点

- **顺序确定性**：索引 value 按 `(bid_inv, sub_height, sub_id)` 字典序排——决定 fire 顺序，跨节点完全一致，避免共识分歧；竞价市场化排名同时保留确定性
- **bid 即写即排**：`update_bid` 立即重新插入索引；订阅者随时可加价抢占更高名次，所有节点同步可见
- **emit 路径开销可控**：value 分两层（索引 + 记录），让一次索引 lookup 不顺带读爆所有完整记录；emit 时走 "1 次 index lookup → 取前 K → N 次 sub record lookup" 的两段式
- **merkle 化天然由 QMDB 提供**——所有 `0x14*` / `0x15*` 都进 state_root，跟 `Code` / `Actor` 等同等待遇
- **不占用 emitter 的 actor storage 配额**——`ActorKvCount` / `ActorKvBytes`（`0x12` / `0x13`）只追踪 emitter 自己写入的 KV，订阅记录是协议级数据，不污染用户合约配额

### 2.3 执行模型

`emit_event` 在 PVM host 层的伪代码：

```rust
fn emit_event(&mut self, topic: &[u8], payload: &[u8]) -> HostResult<EmitResult> {
    // 1. payload 长度 + cap 检查：本 tx 已 emit 次数、本 tx 总同步 fire 数、扇出层数
    require!(payload.len() <= MAX_EVENT_PAYLOAD_BYTES);    // 4096 字节上限
    self.charge_emitter_cells(payload.len() as u64)?;      // 1 cell/byte 计入 emitter
    self.check_emit_caps(topic)?;

    // 2. 读取订阅索引（已按 (bid_inv, sub_height, sub_id) 排序）
    let sub_ids = self.load_sub_index(self.current_actor(), topic)?;

    // 3. 分层：前 K 同步、其余进入异步队列（顺序在此刻即锁定）
    let k = MAX_SYNC_FIRES_PER_TOPIC.min(sub_ids.len());
    let (sync_subs, async_subs) = sub_ids.split_at(k);

    let mut sync_results = Vec::with_capacity(k);
    let mut deferred_subs = Vec::new();
    let mut zombies = Vec::new();

    // --- 同步段：前 K 名在 emitter 调用栈内 fire ---
    for sid in sync_subs {
        let sub = self.load_sub_record(*sid)?;

        // 3a. lazy GC：gas_remaining 不够 fire 一次最低成本就跳过 + 标记 zombie
        if sub.gas_remaining < MIN_FIRE_COST {
            zombies.push(*sid);
            sync_results.push(EmitOutcome::SkippedExpired(*sid));
            continue;
        }

        // 3b. snapshot：订阅者状态 + 全局快照
        let snapshot = self.pvm.snapshot();

        // 3c. 用 sub.gas_remaining 作为本次 call 的预算上限
        //     实际消耗的 cycles/cells 不算在 emitter 头上
        let r = self.call_actor_with_isolated_gas(
            sub.subscriber,
            &sub.handler_name,
            payload,
            sub.gas_remaining,
        );

        match r {
            Ok(res) => {
                self.deduct_subscription_budget(*sid, res.gas_used)?;
                sync_results.push(EmitOutcome::Ok(res));
            }
            Err(e) => {
                // 3d. 失败：回滚 snapshot；emitter 状态不受影响
                self.pvm.rollback(snapshot);
                self.deduct_subscription_budget(*sid, e.gas_consumed)?;
                sync_results.push(EmitOutcome::Err(e));
            }
        }
    }

    // --- 异步段：把溢出 sub_ids 拆成多条 system defer tx，全部入 H+1 队列 ---
    //
    // **顺序锁定**：async_subs 的顺序在此 emit 时已固定（基于 emit 当下的 (bid_inv, sub_height, sub_id) 排序）。
    // 即使订阅者在 H 块到 H+1 块之间调用 update_bid 加价，也不会改变当次 emit 的异步段 fire 顺序——
    // 新 bid 仅对**下一次 emit** 的排名生效。这是为了与同步段"emit 时确定"语义对齐，
    // 杜绝"先 emit 后加价插队当次 emit 的异步段"套利。
    //
    // **拆分策略**：每条 system defer tx 最多承载 ASYNC_FIRES_PER_DEFER_TX = 64 个 sub。
    // 448 个溢出 sub 拆成 ⌈448/64⌉ = 7 条 defer tx，全部目标 H+1；
    // H+1 块如总 cycle budget 不够，由既有 defer admission gate 自然顺延到 H+2/H+3。
    let emit_id = self.next_emit_id_in_tx();          // tx 内第几次 emit，receipt 因果用
    for chunk in async_subs.chunks(ASYNC_FIRES_PER_DEFER_TX) {
        self.enqueue_event_defer_tx(EmitOrigin {
            emitter:      self.current_actor(),
            topic:        topic.to_vec(),
            payload:      payload.to_vec(),
            sub_ids:      chunk.to_vec(),
            origin_block: self.current_block(),
            origin_tx:    self.current_tx_hash(),
            emit_id,
        }, self.current_block() + ASYNC_FIRE_DEFERRAL_BLOCKS)?;
    }
    deferred_subs.extend_from_slice(async_subs);

    // --- zombie 清理：从索引列表里移除，订阅记录本身也删除 ---
    //     被释放的 cells 退还给订阅者本人（不归 emitter / reaper）
    if !zombies.is_empty() {
        self.trim_sub_index(self.current_actor(), topic, &zombies)?;
        for sid in &zombies {
            let sub = self.load_sub_record(*sid)?;
            self.credit_cells(sub.subscriber, self.compute_freed_cells(&sub))?;
            self.delete_sub_record(*sid)?;
        }
    }

    Ok(EmitResult {
        sync_outcomes: sync_results,
        deferred_subs,                  // 调用方可观测哪些 sub_id 排队到 H+1
        emit_id,                        // tx 内第几次 emit，便于在 receipt 中关联
    })
}
```

H+1 块异步段的处理共用 `call_actor_with_isolated_gas` + snapshot 路径，唯一差别是入口由系统级 defer tx 触发，每条 system defer tx 产生独立 receipt 并带 `triggered_by_emit = EmitOrigin {..}` 字段——外部 light client / indexer 通过该字段把 H+1 块的 async receipt 关联回 H 块的原 emit（见 §3.2 receipt schema 扩展）。

`unsubscribe_event` / `force_unsubscribe_event` 共享下面的内部路径：

```rust
fn remove_subscription(&mut self, sid: SubscriptionId, caller: Address) -> HostResult<u64> {
    let sub = self.load_sub_record(sid)?;

    // 权限：订阅者本人 (unsubscribe) 或对应 emitter (force_unsubscribe)
    require!(caller == sub.subscriber || caller == sub.emitter_addr);

    // 1. 退还剩余 gas（cycles）给订阅者
    //    REGISTRATION_FEE 与 bid 已在 subscribe / update_bid 时即时 burn，
    //    sub.bid 字段只用于排序信号，此处不再处理。
    let cycles_refund = sub.gas_remaining;
    self.credit_balance(sub.subscriber, cycles_refund)?;

    // 2. 计算解除 storage 占用的 cells delta（记录删除 + 索引条目移除）
    //    并把这部分 cells 全额退还订阅者，无论调用者是谁
    let cells_freed = self.compute_freed_cells(&sub);
    self.credit_cells(sub.subscriber, cells_freed)?;

    self.trim_sub_index(sub.emitter_addr, &sub.topic, &[sid])?;
    self.delete_sub_record(sid)?;
    Ok(cycles_refund)
}
```

`subscribe_event` 与 `update_bid` 内部对 bid 的处理：

```rust
fn apply_bid(&mut self, subscriber: Address, sid: SubscriptionId, bid_delta: u64) -> HostResult<()> {
    require!(bid_delta > 0);                               // 不允许 0 增量调用（无操作）
    self.debit_balance(subscriber, bid_delta)?;            // 立即从订阅者账户扣
    self.burn_cycles(bid_delta)?;                          // 转入 burn pool（与 EIP-1559 basefee 同走向）
    self.bump_sub_bid(sid, bid_delta)?;                    // 累加到 sub.bid 并重排索引
    Ok(())
}
```

关键点：

- **snapshot/rollback 复用 PVM 既有机制**（`pvm/crates/vm/src/vm/snapshot.rs`），不是从零做
- **gas 隔离**：每个订阅者用自己预付的 `gas_remaining` 作为执行预算，不消耗 emitter 的 cycles/cells——这是失败隔离能成立的前提，否则恶意订阅者可靠耗尽 emitter gas 让 emitter tx OOG
- **call 复用**：底层走的是现有 cross-actor call 路径，不新增执行子系统
- **defer 复用**：溢出段直接复用现有 `defer transaction` 通道（见 §3.2）——不引入"事件异步 lane"等新执行通道
- **顺序确定**：订阅索引按 `(bid_inv, sub_height, sub_id)` 字典序——所有 validator 按同一顺序遍历同步段、异步段也按同顺序入队 defer 队列，避免共识分歧
- **bid 不流向 emitter**：bid 在 subscribe / update_bid 时立即 burn，订阅记录里的 `bid` 字段只是排序信号——emitter 拿不到任何竞价收益，杜绝 emitter 通过"操控订阅市场抽租"的攻击面
- **lazy cleanup**：zombie 订阅在下一次 emit 同步段触达时被自动清理，无需独立 GC 子系统；异步段的 zombie 同样在 H+1 defer fire 时被清理
- **退款不流向 emitter**：无论 unsubscribe 还是 force_unsubscribe，剩余 gas / cells 一律回到订阅者账户，避免 emitter 通过"诱导订阅 → 强制移除"做欺诈

### 2.4 装饰器与显式 API（SDK 侧）

SDK 提供**两种** emit 写法，二者底层都落到 §2.1 的 `rt.emit_event` host API：

**形态 A：`@emit` 装饰器（return-only 简单版本）**

适合"函数结束后通知"的简单语义——绑定 return 触发，一次函数最多一个事件：

```python
@emit("liquidation_imminent")
def maybe_liquidate(self, position_id):
    if self.below_threshold(position_id):
        return ("trigger", position_id)              # 装饰器自动 emit("liquidation_imminent", ...)
    return ("noop", None)                            # 同样会 emit，payload 为 ("noop", None)
```

**形态 B：`ctx.emit` 显式 API（任意位置、任意次数、任意分支）**

适合复杂业务流的"过程式事件"——在函数体任意位置直接触发，可在分支中触发，可在循环内多次触发：

```python
def settle_batch(self, ctx, orders):
    for order in orders:
        result = self.try_match(order)

        if result.matched:
            # 触发 #1：成功撮合，分支内 emit
            ctx.emit("order_matched", {"id": order.id, "price": result.price})
        elif result.expired:
            # 触发 #2：过期作废，不同 topic
            ctx.emit("order_expired", {"id": order.id})
        # 未匹配也未过期 → 不触发任何事件，函数继续

    # 触发 #3：批次结束的汇总，与上面 N 次循环触发并存
    ctx.emit("batch_settled", {"count": len(orders)})
    return ("ok", len(orders))
```

`ctx.emit` 直接调用 `rt.emit_event`，**单函数内可触发任意多个事件**（受 §2.5 的 `MAX_EMITS_PER_TX` 总量约束），**支持任意控制流**。

**subscriber 侧装饰器**（含 bid 参数）：

```python
@on_event(
    emitter="0xLENDING_PROTOCOL",
    topic="liquidation_imminent",
    gas=500_000,
    bid=100_000,                                     # 出 10 万 cycles 抢同步窗口位次
)
def on_liquidation(self, position_id):
    self.bid_for_collateral(position_id)
```

装饰器是 SDK 糖——形态 A、形态 B、subscriber 装饰器全都基于 §2.1 的 host API。这意味着 host API 与装饰器**可以解耦发布**：Phase 1/2 落地 host API 后，业务方完全可以直接用 `rt.emit_event` / `ctx.emit` 编写 actor，装饰器作为 Phase 3 的 DX 优化迭代上线。

### 2.5 协议常量

为防止广度攻击和共识分歧，下列参数必须由协议常量定义、所有 validator 用同一公式应用：

| 参数 | 建议初值 | 作用 |
|---|---|---|
| `MAX_SUBSCRIBERS_PER_TOPIC` | **512** | 单 emitter+topic 最多订阅者数（同步段 + 异步段合计） |
| `MAX_SYNC_FIRES_PER_TOPIC` | **64**（首发保守值，governance 可调；建议上限 **256**）| 单次 emit 在 emitter 调用栈内同步 fire 的上限（按 bid 降序取前 K）。受三类约束：lane cycle budget、validator 时延、snapshot/rollback 攻击面，详见 §6.4 与 [ext_cip-29-sync-cap-analysis](./ext_cip-29-sync-cap-analysis.md) |
| `MAX_EMITS_PER_TX` | 16 | 单笔 tx 内最多 emit 调用次数 |
| `MAX_SYNC_FIRE_PER_TX` | 256 | 单笔 tx 内**同步**总 fire 次数上限（emit × sync_subs）——异步段不计入 |
| `MAX_EVENT_PAYLOAD_BYTES` | 4,096 | 单次 emit 的 payload 字节上限；超出 emit 失败；payload 按 1 cell/byte 计入 emitter cells |
| `ASYNC_FIRES_PER_DEFER_TX` | 64 | 每条 system defer tx 承载的异步 sub 数上限；溢出按此值拆分多条 defer tx，与 `MAX_SYNC_FIRES_PER_TOPIC` 对齐 |
| `MAX_EVENT_DEPTH` | 4 | emit 嵌套深度（emit 内的 handler 又 emit 别的 topic）——**与 PVM `max_call_depth = 32` 是独立计数器**：K 个 sibling handler 串行 snapshot/rollback，不互相嵌套、不挤占 call depth |
| `EMIT_SAME_TOPIC_REENTRY` | `false` | 同一 emit 调用栈内禁止再 emit 同 topic |
| `MIN_SUBSCRIPTION_GAS_PREPAID` | 50,000 cycles | 订阅最低预付（防止 dust 订阅刷注册表） |
| `SUBSCRIPTION_REGISTRATION_FEE` | 10,000 cycles | subscribe 时一次性扣写入算力，**不退**；阻止 register/unregister churn |
| `SUBSCRIPTION_CELL_COST` | 按 storage 增量实测（典型 ≈ 9 cells） | subscribe 时按 `EventSub` 记录 + 索引条目实际增量收 cells；unsubscribe / reap 时全额退还订阅者 |
| `MIN_BID` | 0 | bid 下限——允许零出价，零出价按 `sub_height` 时间序排（落到所有正 bid 之后）|
| `MIN_FIRE_COST` | 5,000 cycles | emit 时若订阅 `gas_remaining` 低于此值则 skip + 标记 zombie 清理 |
| `ASYNC_FIRE_DEFERRAL_BLOCKS` | 1 | 溢出订阅者 fork 成 defer transaction 的延迟块数（H+1）|

这些参数和现有 `TimerConfig` 的模式一致，可由 governance 调整。**`MAX_SYNC_FIRES_PER_TOPIC` 首发 64 是保守选择**：在典型 handler 成本下让 emitter 仍保留 ≥80% lane budget 做自身逻辑；测试网获取真实 handler 成本分布后，governance 可逐步上调至 128 / 256（详细论证与上调判据见 §6.4 与 [ext_cip-29-sync-cap-analysis](./ext_cip-29-sync-cap-analysis.md)）。256 是经过权衡的实质上限——再往上 emitter tx 会失去做其他事的能力。

### 2.6 竞价 System Actor

新分配一个独立的系统 actor，专门承担订阅者竞价市场的查询与操作。**选择独立地址而非挂在 `0x09 (Governance)` 之下**：`0x09` 已承担 `SettlementConfig` 等治理职责，叠加竞价市场会让其职责膨胀且与 settlement 的"系统级稳定参数"语义错位——竞价是高频用户行为，必须独立。

```rust
// node/types/src/constants.rs:156（2026-05-26 起代码已实装）
EVENT_SUBSCRIPTION_SYSTEM_ACTOR = Address::from_low_u64(0x1D)
```

> **地址决定理由。** `0x1D` 位于保留系统 actor 段 `0x01..=0x0F` **之外**（保留段在 `pvm_host.rs` 中对 actor 部署和 `fee_payer_override` 做拦截）。对 `0x1D` 的调用由 `pvm_host::call_actor` 截获并路由到 `execution::event_sub_system_actor::dispatch_rpc`——该地址不部署 actor 代码，是一个 host 托管的"虚拟"系统 actor。本 CIP 早期草案声称 `0x0A`，与代码里的 `STORAGE_MANAGER (CIP-9)` 撞址；`0x1D` 是已激活的最终值。

#### 提供的端点

| 方法 | 类型 | 语义 |
|---|---|---|
| `get_rank(sub_id) -> u32` | 只读 | 返回该订阅**针对未来 emit** 的当前排名（0-indexed）；rank < `MAX_SYNC_FIRES_PER_TOPIC` 说明**下一次** emit 会被同步 fire。**注意**：不反映已经被 emit 锁定、正在 H+1 排队的异步 fire 位次（见 §2.3 异步段顺序锁定）|
| `get_topic_orderbook(emitter, topic, limit) -> Vec<OrderbookEntry>` | 只读 | 返回前 `limit` 名的 `(sub_id, subscriber, bid)` 元组——竞价市场针对**下一次** emit 的可见行情 |
| `get_min_bid_for_rank(emitter, topic, target_rank) -> u64` | 只读 | 返回挤进 `target_rank` 排名所需的最小 bid（= 该位次现持有者的 bid + 1）；订阅者据此报价 |
| `update_bid(sub_id, additional_bid) -> u64` | 写 | 仅订阅者本人可调用；追加 bid（不可下调），立即 burn 并重排索引；返回新的累计 bid。**对已锁定排名的 emit 无效**——新 bid 仅影响**后续 emit** |
| `topup_subscription(sub_id, additional_gas) -> u64` | 写 | 任何账户可为订阅充值 `gas_remaining`；返回 top-up 后余额 |

`update_bid` 也可直接作为 host API 暴露（见 §2.1），通过 system actor 调用是 SDK 友好封装——`@on_event` 装饰器的运行时升级 API 也走这条路径。

#### 与既有 unsubscribe / force_unsubscribe 的兼容性复核

引入竞价后，三条退出路径与 §2.1 的设计**完全兼容**——bid 在 subscribe / update_bid 时立即沉没（burn），订阅记录里的 `bid` 字段只是排序信号，退出路径无需对 bid 做任何额外处理：

| 路径 | 与 bid 的交互 |
|---|---|
| 订阅者主动 unsubscribe | bid 已 burn——不退；行为与"竞价前"对订阅者的财务承诺无差别 |
| `gas_remaining` 耗尽自动失效 | bid 已 burn——无需处理；reaper 仅清理索引和记录 |
| emitter 强制移除 | bid 已 burn——emitter 同样拿不到任何份额；杜绝"emitter 诱导高 bid 订阅后强制驱逐套利"的攻击 |

老王 + 说话人 3 复核建议关注的潜在冲突点（**确认无冲突**）：

- ✅ 索引排序键变更（`(sub_height, sub_id)` → `(bid_inv, sub_height, sub_id)`）：unsubscribe 仍按 `sub_id` 单点删除，与索引排序方式解耦
- ✅ `update_bid` 引入"中途位次变动"：所有 validator 同步重排，确定性不破；订阅者可观测自己的 rank 是否被挤出同步窗口
- ✅ 退订时机：unsubscribe 可在任意 rank 下调用，不要求"必须先退出竞价"——简化用户操作
- ✅ 异步段已锁定的 emit：unsubscribe 仍按 `sub_id` 单点删除；正在排队的 system defer tx 在 H+1 fire 时会发现 `sub_id` 已删，跳过该位置（与 zombie 处理同路径）—— `gas_remaining` 与 cells 已在 unsubscribe 时退还，不重复扣

#### 用户感知 / 参与

订阅者完整可观测竞价市场：

1. 调用 `get_topic_orderbook` 看到对方出价与位次
2. 调用 `get_min_bid_for_rank(target_rank=63)` 看到挤进同步窗口的门槛
3. 调用 `update_bid` 加价抢入同步段，或保留低 bid 接受异步段（H+1）的 fire 时序
4. 调用 `get_rank` 监控自己的位次变动

这构成完整的事件订阅二级市场——竞价、查价、加价、观察的所有原语在 actor 代码内可编程组合，业务方可在合约层封装自动竞价策略。

## 三、为什么这条路安全

事件钩子是 `call()` 的派生（同 tx、同步、状态可隔离），不是 `send()` 或 `defer transaction` 的派生。两者带来的协议风险面完全不同。

| 子系统 | 同 tx 钩子机制（同步段）| 跨块钩子机制（异步段）|
|---|---|---|
| propose / verify 共享路径 | **不变**——hook 在 user tx 执行栈内，propose/verify 单遍走完即可 | **不变**——H+1 块的 system defer tx 走与一般 defer tx 同一路径 |
| tx_root ↔ receipt 一对一映射 | **不变**——同步 fire 是 tx 内部 cross-actor call，不产生独立 receipt | **不变**——每条 system defer tx 产生独立 receipt，属 H+1 块的 tx_root |
| bridge / IBC inclusion proof | **不变** | **轻度扩展**——receipt 新增 `triggered_by_emit` 字段标识跨块因果（详见 §3.2）；不破坏 inclusion proof 结构 |
| admission gate | **不变**——所有同步触发都在 user tx 内，user tx 本身已过 admission | **不变**——system defer tx 走与一般 defer tx 同一 admission；H+1 块超 budget 自然顺延 |
| basefee 反馈环 | **不变**——hook 消耗的 gas 来自订阅者预付池，但**计入本块 block-level cycle consumption**（CIP-3 §2.4），推动 basefee 反馈 | **不变**——异步段 fire 消耗的 cycles 计入 H+1 块的 cycle consumption |
| lane 预算（User/Runner/Timer/System） | hook gas 走订阅预付池但占用 User lane budget | system defer tx 走 System lane（与一般 defer tx 同列）|

唯一新增的协议级 spec 项目是：

- §2.2 的订阅表存储模型（一张新的 merkleized 表）
- §2.3 的 emit/snapshot/rollback 调用语义
- §2.5 的协议常量

这三项都属于 **storage + host API 层** 的局部改造，不触动跨块不变量。

### 3.1 与既有机制的复用关系

| 既有机制 | 在本提案中的作用 |
|---|---|
| PVM `snapshot.rs` | 订阅者执行失败时的回滚机制（直接复用） |
| Cross-actor `call()` | hook fire 的底层调用路径（同步段 + 异步段共用） |
| QMDB 单库 + StateKey 编码 | 新增 `EventSub` / `EventSubIndex` 两个 prefix 直接挂在既有 QMDB 上（参 §2.2） |
| Timer pre-fund 模式 | 订阅 gas 预付模式的参考实现 |
| Cycle / cell 计费 | hook 执行的计费（计入订阅者预付池） |
| **`defer transaction` 子系统** | **异步段（rank ≥ K）溢出订阅者的执行通道——不新增"事件异步 lane"** |
| **EIP-1559 basefee burn 通道** | **bid 与 `REGISTRATION_FEE` 的沉没目的地，与 basefee 同路径，避免新增 burn 子系统** |

**没有从零设计的子系统**。

### 3.2 与 `defer transaction` 的关系

事件钩子原语**同步段**与 `defer transaction` 仍是两条并行原语，但**异步段（rank ≥ `MAX_SYNC_FIRES_PER_TOPIC`）的溢出订阅者通过 `defer transaction` 复用同一执行通道**——形成同步 + 异步的协同结构：

| 维度 | `defer transaction`（独立用例） | event hook 同步段（rank < K） | event hook 异步段（rank ≥ K）|
|---|---|---|---|
| 执行块 | 未来某块 | 当前块、当前 tx | H+1 块（由 `ASYNC_FIRE_DEFERRAL_BLOCKS` 决定）|
| 触发方式 | 高度触发或显式调度 | emit 调用栈内 | emit 时由 host 自动 enqueue 一条系统 defer tx |
| 失败影响 | 独立 receipt，独立 commit | snapshot 回滚，不出 receipt | 独立 receipt（与一般 defer tx 一致）|
| 适用场景 | 用户自调度的异步任务、定时任务 | 同步事件订阅（清算抢权等必须同 tx）| 通知、统计、慢路径预警等可容忍 1 块延迟的事件 |
| 计费来源 | 调度方 | 订阅者 `gas_remaining` | 订阅者 `gas_remaining` |

**对 `defer transaction` 现有实现的影响**：仅新增一种 "系统 defer tx" 触发源（由 emit 内部 enqueue），其余调度 / admission / 执行路径**完全不变**。系统 defer tx 携带 `EmitOrigin` 元组：

```rust
struct EmitOrigin {
    emitter:      Address,
    topic:        BoundedBytes<64>,
    payload:      BoundedBytes<MAX_EVENT_PAYLOAD_BYTES>,
    sub_ids:      Vec<SubscriptionId>,         // ≤ ASYNC_FIRES_PER_DEFER_TX = 64
    origin_block: BlockHeight,                  // 原 emit 所在块
    origin_tx:    H256,                         // 原 emit 所在 tx hash
    emit_id:      u32,                          // tx 内第几次 emit（同 tx 多次 emit 区分）
}
```

在 H+1 块由协议解包、对每个 sub_id 走与同步段相同的 `call_actor_with_isolated_gas` + snapshot 路径。

**Receipt schema 扩展**：每条由 emit 异步段引发的 system defer tx 的 receipt 必须携带：

```rust
struct AsyncEmitReceipt {
    // ... 一般 receipt 字段（gas_used、events、status 等） ...
    triggered_by_emit: Option<EmitOriginRef>,  // 仅 system event defer tx 设置；其他 defer tx 为 None
}

struct EmitOriginRef {
    origin_block:  BlockHeight,
    origin_tx:     H256,
    emit_id:       u32,
}
```

外部 light client / indexer 通过 `triggered_by_emit` 把 H+1 块的 async receipt 关联回 H 块的原 emit。**关键不变量**：

- `triggered_by_emit` 只是 receipt 字段，不破坏 tx_root ↔ receipt 的一对一映射
- inclusion proof 结构不变（H+1 receipt 仍然属于 H+1 块的 tx_root）
- 关联关系是单向、可观测的（receipt → 原 emit），不需要 H 块的 tx_root 携带反向指针

## 四、风险与缓解

| 风险 | 缓解措施 |
|---|---|
| **广度扇出攻击**：恶意 emitter 累积大量订阅者 → 单笔 emit 让 tx 巨慢 | §2.5 的 `MAX_SYNC_FIRES_PER_TOPIC` + `MAX_SYNC_FIRE_PER_TX` 双重 cap 锁死同步段开销；溢出段走 defer 受 admission gate 二次限流 |
| **重入死循环**：handler 内再 emit 形成 A→B→A 循环 | `MAX_EVENT_DEPTH = 4` + `EMIT_SAME_TOPIC_REENTRY = false` |
| **订阅 spam**：恶意订阅者注册大量 dust 订阅刷 emitter 索引列表 | `MIN_SUBSCRIPTION_GAS_PREPAID` 下限（保证每条订阅有最小预付）+ `MAX_SUBSCRIBERS_PER_TOPIC = 512` 索引列表上限；订阅记录走自有 prefix，不消耗 emitter 的 actor storage 配额；**竞价机制天然抗 spam**——同步段位次受 bid 排序保护，spam 订阅只能落在异步段尾部，对头部订阅者无影响 |
| **Gas 责任不清**：emit 本身遍历 + snapshot 的开销谁付 | emit 调用本身按 "读取订阅表 + N×snapshot" 的模型计费，由 emitter 承担；fire 内部消耗由订阅者预付池承担——边界明确 |
| **订阅顺序被操纵**：通过非市场化手段抢占 fire 优先权 | 顺序固定为 `(bid_inv, sub_height, sub_id)` 字典序，公开可观测；订阅者通过 bid 竞价取得同步段位次（与拍卖逻辑一致），同 bid 时仍按时间序——既市场化又留时间维度做 tie-break |
| **静默失败语义不清** | `EmitResult` 返回每个订阅者的 outcome，emitter 可显式检查；同时 receipt 的 events 字段记录所有 fire 结果（成功 + 失败 + gas 消耗），可观测可审计 |
| **订阅过期不可见**：订阅者预付耗尽后无声失效 | 订阅表暴露查询 API；订阅者可读取自己的 `gas_remaining` 并主动 top-up |
| **register/unregister churn**：高频 subscribe + 立即 unsubscribe 白嫖存储抖动 | `SUBSCRIPTION_REGISTRATION_FEE` 在 subscribe 时一次性扣、unsubscribe 不退——把存储写入开销前置收齐，churn 越频繁攻击者亏损越大 |
| **emitter 通过强制移除收割 gas** | `force_unsubscribe_event` 路径硬性规定 `gas_remaining` 与 cells 都退给订阅者、不流向 emitter；emitter 没有任何可分得的份额 |
| **emitter 被强制承担订阅者的 cells 占用 → 经济性 spam**：恶意订阅者批量挂载到 emitter 上 → 把 emitter 的 storage 配额吃光 | `EventSub` / `EventSubIndex` 走自有 prefix，**全程不计入 emitter 的 `ActorKvCount` / `ActorKvBytes` 配额**；cells 由订阅者全额承担 → 协议级原语相对于"emitter 自建订阅表"方案的核心优势 |
| **抢拍位次 → 立刻 unsubscribe 退款套利**：恶意订阅者出高 bid 抢同步窗口、emit 触发前一刻退订把钱拿回 | bid 在 `subscribe` / `update_bid` 时**立即 burn**（与 EIP-1559 basefee 同走向），订阅记录里 `bid` 字段只是排序信号；`unsubscribe` / `force_unsubscribe` 路径下 bid 一律不退 → 抢拍即沉没，套利不成立 |
| **溢出订阅者滞后 fire 不可见**：rank ≥ K 的订阅者下一块才 fire、订阅者不知道自己掉到了异步段 | (1) `EmitResult.deferred_subs` 在同步段 emit 即可被 emitter / 调用方观测；(2) `EVENT_SUBSCRIPTION_SYSTEM_ACTOR.get_rank(sub_id)` 任意时刻可查；(3) 订阅者可通过 `update_bid` 加价主动挤回同步段 → 滞后是订阅者**可观测、可干预**的状态，不构成隐式失败 |
| **竞价市场被 emitter 操控抽租**：emitter 通过控制订阅市场获取竞价收益 | bid 直入 burn pool，**emitter 拿不到任何份额**；emitter 也无 `update_bid` 权限干涉订阅者 → 竞价收益不外溢，没有可操控的对手方 |
| **bid 通胀 / cycle 通缩失衡**：高频竞价 burn 过多 cycles，影响 token 经济 | bid 走与 EIP-1559 basefee 同一 burn 通道，统计入既有 burn 监控；初期可通过 governance 调整 `MIN_BID` 与 `update_bid` 的最小步长缓解 |
| **超大 payload 攻击**：emitter 发起 1MB payload 让每个 sync sub 都接收数据拷贝、撑爆 lane | `MAX_EVENT_PAYLOAD_BYTES = 4096` 硬上限；超出 emit 调用即失败；payload 按 1 cell/byte 计入 emitter cells，让 emitter 自己承担数据扩散成本 |
| **emit 后加价插队当次异步段**：订阅者在 emit 之后、H+1 fire 之前调用 update_bid 试图挤回前列 | 异步段顺序在 emit 时即锁定（§2.3）——新 bid 仅对后续 emit 有效；当次异步段 fire 顺序固定，validator 严格按锁定顺序执行 |
| **异步段累积 OOM**：单 emit 产生 448 个溢出 sub × N 个 emit 在同块发生 → H+1 块巨量 fire | 异步段按 `ASYNC_FIRES_PER_DEFER_TX = 64` 拆多条 defer tx；超 H+1 block budget 的部分由现有 defer admission gate 自然顺延到 H+2/H+3；不存在新增的"事件队列爆炸"路径 |
| **emit 与 call 嵌套耗尽栈**：emit 内 handler 又 cross-actor call，多层嵌套耗尽 PVM call stack | `MAX_EVENT_DEPTH = 4` 与 PVM `max_call_depth = 32` 是独立计数器；K 个 sibling handler 串行执行不互相嵌套；最坏情况 4×8 = 32 仍在 PVM 边界内 |

## 五、实施路径

### 5.1 分阶段交付

| Phase | 交付物 | 工程量 | 验证产物 |
|---|---|---|---|
| **Phase 0**：纯 SDK 原型 | actor 库提供 `@hookable` 装饰器，底层用现有 `call()` + actor 侧 try/except，订阅表存在 emitter 自己的 actor storage | 1–2 周 | 用真实清算业务跑通；如业务侧够用，Phase 1+ 可延后或缩减 |
| **Phase 1**：协议级订阅注册表 + `subscribe_event` host API | 全局订阅表存储模型、注册/注销 host API、订阅记录的 merkle 化 | 4–6 周 | 测试网 actor 可注册订阅；查询订阅表可在合约内完成 |
| **Phase 2**：`emit_event` host API + snapshot/rollback 集成 | `emit_event` 实现、PVM snapshot 与遍历调用、failure isolation 测试 | 4–6 周 | 端到端：emitter→fire 多个订阅者→单订阅者失败不影响整体 |
| **Phase 3**：SDK 装饰器 + 文档 + 案例 | Python `@emit` / `@on_event` 装饰器、清算 demo、开发者文档 | 2–3 周 | 装饰器形态下的完整清算场景 |

### 5.2 顺序逻辑

- **Phase 0 是低成本探针**：很多事件订阅场景靠"订阅者主动 register-with-emitter + emitter 显式 call subscribers"的纯 SDK 模式可能就够。Phase 0 用最小代价探明这一点，避免 Phase 1+ 完成后才发现实际业务用不上协议级支持。
- **Phase 1 与 Phase 2 顺序不可换**：没有订阅表，emit 无处可读。
- **Phase 3 是 DX 糖**：装饰器是 SDK 层概念，不发布也不影响协议功能；可以先用 host API 直接调用，装饰器作为开发者体验优化迭代发布。

## 六、待定决策

P0（动工前必须解决）已在 §2.1 / §2.3 / §2.5 / §2.6 / §3.2 落地：

- ✅ **异步段顺序锁定**：emit 时即固定（§2.3）
- ✅ **receipt 因果关系**：`triggered_by_emit` 字段（§3.2）
- ✅ **defer tx 拆分**：`ASYNC_FIRES_PER_DEFER_TX = 64`（§2.5）
- ✅ **payload 上限**：`MAX_EVENT_PAYLOAD_BYTES = 4096`，emitter 按 1 cell/byte 付（§2.5）
- ✅ **depth 计数器独立**：`MAX_EVENT_DEPTH` 与 PVM `max_call_depth` 解耦（§2.5）
- ✅ **gas top-up**：`rt.topup_subscription`（§2.1）

以下事项仍需在动工前的客户复核会上对齐：

### 6.1 协议常量初值

§2.5 的 cap 初值需要业务验证：

- `MAX_SUBSCRIBERS_PER_TOPIC = 512` 对预期的"长尾通知 + 头部抢权"分层是否足够
- `MAX_SYNC_FIRE_PER_TX = 256` 是否覆盖典型的多事件级联场景
- `MIN_SUBSCRIPTION_GAS_PREPAID = 50,000` 是否过高/过低
- `ASYNC_FIRE_DEFERRAL_BLOCKS = 1` 是否合理（业务侧愿意接受 1 块的异步延迟，还是希望可配置更长以摊薄 H+1 块压力）

这些参数 governance 可调，但首发版本的初值会影响早期开发者体验。

### 6.2 装饰器命名

`@emit` / `@on_event` 是直接的命名；也可考虑：

- `@event` / `@subscribe`
- `@publishes` / `@listens`
- 或与现有 SDK 风格更贴的其他形态

如果对装饰器形态有偏好，欢迎在 Phase 3 启动前提出。

### 6.3 P1 / P2 / P3 遗留事项

下列在 Phase 1 / Phase 2 实现规范 freeze 前需要逐条决策。短描述如下，详细分析另见后续扩展文档：

#### P1（影响实现复杂度）

| # | 议题 | 倾向 |
|---|---|---|
| P1-A | `SubscriptionId` 生成规则（counter / hash / 随机？）| 倾向 `keccak256(emitter‖subscriber‖topic‖sub_height)[..33]`——确定性、抗碰撞、便于跨节点比对 |
| P1-B | `MIN_BID_STEP`（防 1-cycle 微调刷链）+ `MAX_CUMULATIVE_BID`（防 u64 溢出）| 倾向 `MIN_BID_STEP = 1000`、`MAX_CUMULATIVE_BID = u64::MAX / 2` 软上限 |
| P1-C | `force_unsubscribe_event` 的触发约束（emitter 是否可任意调用）| 倾向"任意调用合法但 emitter 链上承诺受限"——通过 actor manifest 可选声明"承诺不强制驱逐" |
| P1-D | handler 函数签名标准（`handler(payload)` vs `handler(emitter, topic, payload)`）| 倾向后者——便于一个 handler 服务多 topic |
| P1-E | emitter actor 升级 / 重部署对已有订阅的语义 | 与 CIP-1 联合定义；初步倾向"升级保留订阅，新代码生效；删除 actor 视为对所有订阅的 force_unsubscribe" |

#### P2（经济模型 / DX）

| # | 议题 | 倾向 |
|---|---|---|
| P2-A | bid 价格发现的连续性（防出价竞赛尖刺）| Phase 0 / Phase 1 测试网观察后再决策；可能引入二价拍卖或 MIN_BID_STEP 平滑 |
| P2-B | `REGISTRATION_FEE = 10,000` cycles 的经济校准 | 测试网数据驱动调整 |
| P2-C | Phase 0 → Phase 1 数据迁移 | 倾向"不迁移"——Phase 0 是探针，Phase 1 上线时所有订阅重新注册 |
| P2-D | Topic 字符规则（`MAX_TOPIC_BYTES`、是否要求 UTF-8）| 倾向 `MAX_TOPIC_BYTES = 64`、不强制 UTF-8（保留二进制 topic）|
| P2-E | `update_bid` 批量重排（同块多次 update_bid 合并）| 倾向"不批量、每次立即重排"——简单、可观测；高频重排成本由 bid burn 自然限流 |

#### P3（实现 / 测试 / 跨子系统）

| # | 议题 | 触发时机 |
|---|---|---|
| P3-A | Snapshot 子系统"宽兄弟节点"压测 | Phase 2 启动时 |
| P3-B | CIP-3 basefee 反馈系数在 cap=128/256 下复核 | Phase B/C 上调前 |
| P3-C | 跨 topic MEV 套利模型分析 | Phase 3 之后 |

### 6.4 扇出上限的设计边界与应用层逃逸阀

`MAX_SYNC_FIRES_PER_TOPIC = 64` **不是写死的物理铁壁，而是首发的保守选择**。完整论证见独立扩展文档 [ext_cip-29-sync-cap-analysis](./ext_cip-29-sync-cap-analysis.md)，这里给出执行摘要。

按 User lane 22M cycles 预算估算，一次满载同步 emit 的开销：

| 项 | 单次成本 | × 64 subs |
|---|---|---|
| 索引读取 | ~1K | 1K |
| `EventSub` 记录读取 | ~500 | 32K |
| snapshot 创建 | ~1K | 64K |
| handler 调用 overhead | ~5K | 320K |
| handler 业务逻辑（典型） | ~50K | 3.2M |
| gas 扣减写入 | ~500 | 32K |
| **合计** | | **~3.6M cycles**（占 lane ~16%）|

不同 cap 下的 lane 占用：

| 同步 cap | 满载 cycles | 占 lane 比例 | 留给 emitter 自身的预算 | 评价 |
|---|---|---|---|---|
| 64（首发）| 3.6M | 16% | 18.4M | 充足、保守 |
| 128 | 7.2M | 33% | 14.8M | 仍够 emitter 做大量本职工作 |
| 256（建议实质上限）| 14.3M | 65% | 7.7M | 紧张但可行 |
| 500 | 28M | **127%** | **−6M，单 tx 必 OOG** | 协议硬上限破产 |

**500 在典型 handler 成本下直接超 User lane 22M 硬上限**——这是协议级 cap，不能突破。256 是"emitter tx 仍能做其他事"的实质边界，再往上就让原语退化成"只为 emit 而存在"。

#### 同步段 vs defer 段：边际成本不对称

| | 同步段每加 1 sub | 异步段（defer）每加 1 sub |
|---|---|---|
| 占谁的预算 | emitter tx 自己的 User lane（22M）| H+1 块整体 block budget |
| validator 时延 | propose/verify 关键路径上串行执行 | 独立 tx，并行于其他用户 tx |
| 失败放大面 | emitter tx 的 snapshot/rollback 链路 | 独立 receipt，互不影响 |
| basefee 反馈 | 推高当前块 cycle 反馈 | 推高 H+1 块反馈，分摊 |

这是为什么"溢出走 defer"成立、但"同步段无限拉大"不成立——两类 sub 不等价。

#### 上调路径（governance 决策）

首发 64 保守落地后，依据测试网数据分阶段上调：

| 阶段 | 触发条件 | 目标 cap |
|---|---|---|
| Phase A（首发）| — | **64** |
| Phase B | 测试网平均 handler cycles < 30K，且 propose/verify p99 延迟 < 50ms 额外开销 | 128 |
| Phase C | Phase B 稳定运行 1 个月，无 snapshot 子系统边界案例 | 256（实质上限）|

**为什么 256 后不再可调**：再上调会让单 emit 占 lane 比例超 65%，emitter 在同一 tx 内做其他事的能力急剧下降；同时 propose/verify 串行延迟超 8× 放大（相对 64），共识延迟敏感。

#### 分层模型如何回应"500+ 订阅者"的需求

直接拉高同步 cap 不可行，但通过 §2.3 的**分层执行模型**仍能服务"理论 500+ 订阅者"的业务场景：

- `MAX_SUBSCRIBERS_PER_TOPIC = 512`（总注册上限）
- `MAX_SYNC_FIRES_PER_TOPIC = 64`（同步段算术硬约束）
- 第 65~512 名由 host 自动 fork 成一条 `defer transaction`，在 H+1 块走相同的 fire 路径
- 排序按 bid 降序——**付得起的拿同步窗口（抢清算）、付不起或不关心时序的接受 1 块延迟（通知）**，市场自然分层

这个设计让同一个事件同时服务两类业务：

| 业务类型 | rank | 延迟 | 典型用例 |
|---|---|---|---|
| 清算抢权 / 价格抢算 | 0 ~ 63 | 同 tx 同步 | 必须同 tx，付高 bid 进入 |
| 通知 / 统计 / 慢路径 | 64 ~ 511 | H+1 异步 | 容忍 1 块延迟，零 bid 即可 |

#### 业务侧仍可主动分流的逃逸阀

即便有了分层，三条业务侧分流手段仍然有用：

**1. Topic 分桶**

把单一大 topic 拆成多个细分 topic，订阅者按需挂载：

- 不要用：`emit("liquidation")` ← 8000 个订阅者挤同一 topic 即使分层也会让异步段堆积
- 用：`emit(f"liquidation:tier_{tier}")` 按风险等级、`emit(f"liquidation:asset_{asset}")` 按资产

订阅者按业务相关性精准订阅，自然分流；多数情况单桶 < 64 就够同步全 fire。

**2. Relay 模式（多级扇出）**

emitter 只把 64 个 "relay actor" 注册为同步订阅者；每个 relay 自己再有 64 个同步订阅者：

- 第一层（emitter → relays）走同步 emit，保留同 tx 语义
- 第二层（relay → end subscribers）也走同步 emit
- 容量：64 × 64 = 4096 终端订阅者均同 tx 同步可达（仍受 lane cycle budget 约束，需配套 topic 分桶降低 handler 业务逻辑成本）

**3. 主动选择异步（零 bid 或低 bid）**

对不需要同 tx 反应的订阅者（通知、统计、慢路径预警），主动以 `bid=0` 注册——天然落入异步段，不与抢权者争位次。

#### 协议级"扩同步段"路径的拒绝理由

考虑过的几条 protocol-level 路径，全部 reject：

| 方案 | 拒绝理由 |
|---|---|
| 单 emit 自动跨多块拆分**整个事件**（含同步段） | 破坏"同 tx 同步"语义——这是这个原语存在的理由本身。分层模型只把溢出段异步化，同步段仍保留同 tx 语义 |
| `MAX_SYNC_FIRES_PER_TOPIC` 提到 500+ | 典型 handler 成本下直接超 User lane 22M 上限（500×56K = 28M）；即便极轻 handler 装得下，单 emit 也占满 ¼ 块 cycle target，basefee 反馈剧烈；并且 validator 串行 fire 时延物理上 8× 放大 |
| 单 emit 自适应 cap（按 gas_remaining 总和动态分割同步/异步段） | 订阅者无法预知自己是否同步 fire；共识复杂度上升；恶意订阅者可注册 dust gas_remaining 挤进同步段 |
| 索引分片（shard by hash） | 64 subs × 49 字节 ≈ 3.1 KB 单 blob，QMDB 完全 hold 得住；分片只是把简单结构搞复杂 |
| 同步段轮转 fire（每块换一批 64） | 破坏"高 bid 必同步"的契约——订阅者无法依赖这个原语来抢清算窗口 |
