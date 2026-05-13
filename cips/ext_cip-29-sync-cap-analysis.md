# ext_cip-29: 同步 Fire 上限的设计权衡分析

> 本文是 [CIP-29: 链上事件钩子](./cip-29-on-chain-event-hooks.md) 的扩展分析文档，专门论证 `MAX_SYNC_FIRES_PER_TOPIC` 的取值依据。CIP-29 §2.5 / §6.4 引用本文。

## 背景

CIP-29 引入"分层执行模型"：单次 `emit_event` 按订阅者 bid 降序取前 K 名在 emitter 调用栈内**同步 fire**，其余订阅者自动 fork 成 `defer transaction` 在下一块**异步 fire**。这里的 K 就是 `MAX_SYNC_FIRES_PER_TOPIC`。

客户复核时提出一个直接的问题：

> 既然你已经接受"超过上限走 defer"的设计，为什么不让同步 cap 直接拉到 500，超过 500 才走 defer？

这个问题的本质是：**同步 sub 和 defer sub 是否是等价的"扩容单位"**？如果等价，就该把同步段拉到能容纳大部分业务的程度；如果不等价，就要分析两者的边际成本差异、找到合理切分点。

本文给出完整论证。结论先说：**两者不等价；64 是首发保守值，256 是实质上限，500 不可行。**

## 一、核心不对称：同步 sub vs defer sub 的边际成本

同步段每加 1 个订阅者与异步段每加 1 个订阅者，吃的不是同一份预算：

| | 同步段每加 1 sub | 异步段（defer）每加 1 sub |
|---|---|---|
| **占谁的 cycle 预算** | emitter tx 自己的 User lane（22M）| H+1 块整体 block budget（10M target，可超）|
| **occupies whose time** | propose/verify 关键路径串行执行（共识延迟敏感）| 独立 tx，与其他用户 tx 并行调度 |
| **失败影响半径** | 落入 emitter tx 的 snapshot/rollback 链路 | 独立 receipt，与其他 sub 互不影响 |
| **basefee 反馈** | 推高当前块 cycle consumption，本块 basefee 涨 | 推高 H+1 块 consumption，下一块涨 |
| **占用空间** | propose/verify 期间 validator 内存 + PVM 状态 | defer 队列条目（轻量）|
| **可观测性** | 在 emitter 调用栈里产生即时 `EmitResult` | 独立 receipt 异步产生 |

**关键观察**：同步 sub 是把负载 "压" 到 emitter 自己的 tx 里；defer sub 是把负载 "摊" 到整个系统的未来块。前者每加一个都直接侵蚀 emitter 在同一笔 tx 内做其他事的能力；后者不影响 emitter 本身。

这就是为什么客户的"500 同步 + 超过 500 走 defer"听起来对称、实际不对称——把同步段拉到 500 的代价是 emitter tx 本身做不成事，而不是"系统总负载多一点"。

## 二、算术上限：500 同步必 OOG

按 CIP-29 §6.4 的成本估算，一个满载同步 sub 的开销约 56K cycles：

| 成本项 | 单 sub | 备注 |
|---|---|---|
| 索引读取 | ~1K | 整 emit 只读一次，分摊到首个 sub |
| `EventSub` 记录读取 | ~500 | 每 sub 一次 |
| snapshot 创建 | ~1K | 每 sub 一次 |
| handler 调用 overhead | ~5K | cross-actor call 的固定开销 |
| handler 业务逻辑（典型）| ~50K | 业务而定，10K（极轻）~ 200K（复杂）|
| gas 扣减写入 | ~500 | 更新 `gas_remaining` 字段 |
| **合计** | **~56K cycles** | |

User lane 总预算 22M cycles。把同步 cap 摆到不同档位看 lane 占用：

| 同步 cap | × 56K（典型）| × 10K（极轻 handler）| 占 lane 比例（典型）| 留给 emitter 自身的预算 | 评价 |
|---|---|---|---|---|---|
| 64（首发）| **3.6M** | 0.64M | **16%** | 18.4M | 充足、保守 |
| 128 | 7.2M | 1.3M | 33% | 14.8M | emitter 仍够用 |
| 256（建议实质上限）| 14.3M | 2.6M | 65% | 7.7M | 紧张但可行 |
| **500** | **28M** | 5M | **127%** | **−6M，单 tx 必 OOG** | **协议硬上限破产** |
| 512 | 28.7M | 5.1M | 130% | 同上 | 同上 |

**500 在典型 handler 成本下直接超 User lane 22M**——这是 CIP-3 §2.4 锁定的协议硬上限，不是 spec 选择。即便假设业务方承诺 handler 极轻（10K cycles 量级），500 sub 仍占 5M / 22M ≈ 23% lane，意味着：

- 单 tx 占 ¼ 块的 cycle target（`BLOCK_CYCLES_TARGET = 10M`）
- basefee 反馈环（EIP-1559）会立即把 emit 这条路径的费用推高
- 同 tx 内做其他事（多次 emit、emitter 自身业务）几乎不可能

所以 500 同步**在算术上不可行**，无论 handler 成本怎么算。

## 三、Validator 时延：非 cycle 计量的物理约束

cycle 计费只反映 PVM 内的虚拟成本，**不反映 validator 的真实 CPU/IO 时间**。同步 fire 的物理时间由这些组成（cycle 之外）：

1. **PVM 调度切换**：每个 cross-actor call 需要保存当前栈、加载目标 actor 代码、设置参数、清理寄存器
2. **snapshot 物化**：QMDB 写入缓冲区 + PVM 解释器状态快照
3. **rollback 物化**（失败时）：丢弃缓冲区 + 还原解释器状态
4. **storage 读取**：每个 sub 至少触发一次 storage trie 路径下探

这些操作在当前 PVM 实现（pvm/crates/pvm-runtime）的实测下，每个 sub 大约引入 **0.05–0.2 ms** 的物理时间（不含 handler 自身业务逻辑）。看不同 cap 的最坏物理时延：

| 同步 cap | 物理时延（最坏估算）| 占 1 秒出块时间比例 |
|---|---|---|
| 64 | 3–13 ms | 0.3–1.3% |
| 128 | 6–26 ms | 0.6–2.6% |
| 256 | 13–51 ms | 1.3–5.1% |
| 500 | 25–100 ms | **2.5–10%** |

**Propose/verify 都是共识关键路径**——每多 1 ms 都直接拉长出块时间。500 同步在最坏情况下可吃掉 10% 的出块预算，且这部分**完全无法用 cycle 计费来调节**（它不是 PVM 内的虚拟工作，是 validator 自己的 CPU/IO）。

注意这个约束是**乘性叠加**到 cycle 约束之上的——即便 cycle 算得过去（极轻 handler），物理时间也未必撑得住。

## 四、失败放大与攻击面

每个同步 sub 都需要 snapshot create → 调用 handler → 成功 commit 或失败 rollback。这条路径中：

- **snapshot 子系统**是 PVM 的关键安全组件。当前实现（`pvm/crates/vm/src/vm/snapshot.rs`）针对"嵌套深度 ≤ 32 的 call 链"调优，**不是**针对"500 个兄弟节点串行 snapshot/rollback"调优
- **rollback 边界 case**：每个 rollback 都涉及缓冲区清理、解释器状态还原、storage cache invalidation；500 个并列的 rollback 候选意味着边界 case 测试面比 64 时大 8×
- **恶意 handler 探测**：500 个独立的 handler 入口意味着攻击者有 500 个机会去探测 PVM 的边界 case（int 溢出、深度递归、内存压力等已知通过 INT_GUARD_PREAMBLE / blacklisted imports / 1234-digit cap 等多层防御，但每个入口都是测试面）

256 之内时，安全边际仍然在我们当前测试覆盖能保证的范围；上到 500 需要专门对 snapshot 子系统做"宽兄弟节点"压力测试，且没有明确的业务需求驱动这种额外工程投入。

## 五、64 是怎么选出来的

把上面三个约束摆在一起看 64：

| 约束 | 64 同步段下的位置 |
|---|---|
| **lane budget**（22M）| 占 16%，emitter 仍有 84% 做本职 |
| **物理时延**（出块 1s）| 最坏 13ms / 0.3–1.3%，几乎不可见 |
| **snapshot 攻击面**| 当前实现充分调优过的 size 量级 |
| **业务覆盖**（清算抢权的典型订阅者数）| 实证经验上 10–50 个高价值玩家，64 留有富裕 |

**64 是这四个约束的最严格者下方留出安全裕度的产物**——不是算术铁壁，也不是随便拍的。

## 六、上调路径

64 是首发的保守值，**不应写死**。建议交给 governance 按测试网数据驱动分阶段上调：

| 阶段 | 触发条件 | `MAX_SYNC_FIRES_PER_TOPIC` |
|---|---|---|
| **Phase A（首发）** | — | 64 |
| **Phase B** | 测试网数据：平均 handler cycles < 30K **且** propose/verify 在 emit 满载时 p99 延迟额外开销 < 50ms | 128 |
| **Phase C** | Phase B 稳定运行 ≥ 1 个月、无 snapshot 子系统边界案例、basefee 在满载 emit 后行为符合 EIP-1559 模型预期 | 256（实质上限）|

**为什么 256 是实质上限**：

- lane budget 占用 65% 是 "emitter 还能做事" 与 "emitter 完全被 emit 占用" 之间的边界
- 再上调到 384 / 512，emitter tx 在典型 handler 成本下就只能做 emit 这一件事——原语退化为"事件广播专用 tx"，失去与其他业务逻辑混合的能力
- 物理时延在 256 时已占出块 1–5%，再翻倍即逼近 10%，逼近共识延迟敏感边界

**governance 调整建议保留可逆性**：如果上调到 128 后实际数据不达预期（handler 平均成本超 30K、p99 延迟超阈值），governance 应能回调到 64。CIP-12 的 governance 框架已支持参数热更新。

## 七、客户的"500 同步"诉求如何被业务层满足

客户的真实需求是"挂得下 500+ 订阅者"，而非"500 个全部同步"。这个需求在当前分层模型下**已经被满足**：

- `MAX_SUBSCRIBERS_PER_TOPIC = 512`：总挂载上限确实 500+
- `MAX_SYNC_FIRES_PER_TOPIC = 64`（可调至 256）：同步段付 bid 拿位次
- 第 K+1 名及以后自动走 defer，H+1 异步 fire

业务层进一步分流的三条逃逸阀（CIP-29 §6.4）：

1. **Topic 分桶**：`emit("liquidation:tier_1")` / `emit("liquidation:asset_eth")` 把大 topic 拆细分流
2. **Relay 模式**：64 × 64 = 4096 终端订阅者均同步可达
3. **主动选择异步**：以 `bid=0` 注册，落入异步段，不与抢权者争位次

**结合 Phase B/C 上调到 256**，分桶后单桶可达 256 同步、Relay 模式下可达 256 × 256 = 65536 终端订阅者同步可达——绝大多数业务场景"500+ 订阅者"的诉求被充分覆盖。

## 八、结论

| 问题 | 答案 |
|---|---|
| 64 是算术硬约束吗？ | 不是。64 是 lane budget / validator 时延 / snapshot 攻击面 / 业务实证四类约束下的**保守首发值** |
| 256 可以做到吗？ | 可以，但需要测试网数据驱动的 governance 上调，且 256 是**实质上限**（占 lane 65%）|
| 500 可以做到吗？ | **不可以**。典型 handler 成本下 28M > 22M lane budget，直接 OOG；即便极轻 handler，basefee 反馈剧烈、物理时延占出块 10%、snapshot 攻击面 8× 放大都是不可接受的代价 |
| "超过 500 走 defer" 是否对称？ | 不对称。同步 sub 吃 emitter tx 的 lane budget；defer sub 吃未来块的整体 budget。两者**边际成本不等价**，所以同步段不能与 defer 段简单互换 |

CIP-29 应把 `MAX_SYNC_FIRES_PER_TOPIC` 的语义定为"**首发 64，governance 可上调至 256；500 不在可行域内**"，并把上调路径与判据明确写入规范。

---

## 附录 A：成本估算的数据来源

| 项 | 来源 |
|---|---|
| User lane 22M cycles | `node/execution/src/basefee.rs` 中的 lane 划分 + `BLOCK_CYCLES_TARGET = 10_000_000` |
| handler cycles 50K（典型）| 实测 token 标准 actor 的 transfer handler 在 3 万 ~ 8 万 cycles，取中位 50K |
| handler cycles 10K（极轻）| 实测仅做状态读 + 单字段更新的 handler |
| snapshot create/rollback ~1K | PVM 基准测试 `pvm/benches/pvm_cowboy.rs::interpreter_warmstart`（参考记忆中的 P2 性能优化）|
| 物理时延 0.05–0.2 ms / sub | pvm-runtime 在 PVM Performance Campaign（2026-03-31）的实测样本 |

## 附录 B：与 CIP-3 dual basefee 的关系

`MAX_SYNC_FIRES_PER_TOPIC` 上调会同步影响 CIP-3 的 EIP-1559 basefee 反馈环——更大同步段意味着满载 emit 时单 tx 消耗的 cycles 更高、推高本块 cycle consumption、触发 basefee 上涨。这本身是 CIP-3 设计内的市场机制，但**反馈强度与 cap 大小成正比**。Governance 在 Phase B/C 上调前应验证 basefee 反馈在新 cap 下的行为仍符合预期斜率（CIP-3 §2.4 给定）。

## 附录 C：与 Phase 0 SDK 原型的兼容性

CIP-29 §5.1 的 Phase 0（纯 SDK 原型，订阅表存在 emitter 自己的 actor storage）**不受 `MAX_SYNC_FIRES_PER_TOPIC` 约束**——Phase 0 的同步 cap 由 emitter 合约自己决定，可以挂任意多个订阅者。本文的所有论证只适用于 Phase 1+ 的协议级原语。Phase 0 用真实业务跑通后再决定 Phase 1+ 的具体 cap 取值，这也是上调路径的额外数据来源。
