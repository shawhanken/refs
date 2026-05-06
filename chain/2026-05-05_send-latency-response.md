# 关于 Same-Block Tail Delivery 提案的回复

> 回应 Charles DePue 的 *Same-Block Tail Delivery for `send()`* 提案。

Charles，感谢详尽的提案——开发者侧 1-block 延迟带来的体验问题是真实的，我们也认同当前的稳态不够好。在确定方向之前，我们花了一些时间把几个关键数据先算清楚：tail delivery 在不同负载下能拿到多少延迟收益、与当前哪些子系统会形成冲突、会引入哪些新的攻击面，以及是否存在更轻的方案可以拿到同样或大部分收益。下面按这个顺序展开。

## 一、延迟收益的实际数学

### 现状基线

- `min_block_interval = 1000 ms`（`chain/src/application.rs:175`，硬编码）
- 单笔 `send` 的最佳/最差延迟（user tx 进 mempool → 接收方 handler 触发）：

  | 场景 | 延迟 |
  |---|---|
  | 最佳（user tx 几乎卡到下一个块边界提交） | **~500 ms** |
  | 平均 | **~750 ms** |
  | 最差（user tx 刚错过当前块） | **~1000 ms** |

### 三个方案对比

| 方案 | 最佳 | 平均 | 高负载（队列满） | TPS 影响 | 工程成本 |
|---|---|---|---|---|---|
| **A. 现状（1000ms 块）** | 500 ms | 750 ms | 1000 ms | 基线 | 0 |
| **B. 块时间降到 500ms** | **250 ms** | **375 ms** | **500 ms** | **×2** | 改三处常量 + 测试网验证 |
| **C. Tail delivery（保持 1000ms 块）** | ~0 ms | 受 tail budget 限制 | 退化为 next-block ≈ 1000 ms | 持平或略降（tail 占预算） | 多月工程 + spec + 审计 |

**关键观察：**

1. **方案 C 只在链空闲时严格优于方案 B**。一旦负载推高到 tail 队列满，drain 时遇到 budget 不够，剩余 tail 消息回滚到下一块——这是你的提案里明确写的 fallback。**这种场景下方案 C 的延迟和现状（方案 A）一致**。
2. **方案 B 是无条件优于方案 A 的**：最佳/平均/最差三种场景都减半，且 **TPS 同步翻倍**——所有用户操作都受益，不止 `send`。
3. **方案 B vs 方案 C 在最佳场景下的差距是 ~250 ms**，这是 tail delivery 在最理想情况下能拿到的额外收益。

### 实测可承受性（方案 B）

- 当前空块 finalize：近期实测 **~4 ms**（`validator.log` 五次连续采样：3194 / 4038 / 4146 / 4143 / 4118 µs）
- propose + execute + finalize 整条链路相对 1000 ms 间隔有 **~250×** 的余量
- commonware-consensus 设计上支持亚秒级 round；500 ms 是个我们想先在测试网上跑出稳定数据之后再正式落地的目标，但目前的实测说明链路本身有充裕余量

## 二、与现有子系统的冲突

实现 tail delivery 会触动以下子系统当前所依赖的不变量：

### 1. Propose ↔ Verify 的对称性

我们当前 propose 和 verify **共用同一个 `execute_block_speculative` 函数**（见 `storage/src/speculative.rs` 文件头注释）。每个 block 单遍走完，state_root / receipt_root 计算完毕。这是单诚实验证人 BFT 的安全基础。

引入 tail delivery 后：
- propose 必须**先执行 user txs，看 tail 队列里产生了什么**，再 drain tail，再算 root。
- verify 同样必须重现这个两阶段过程，并按完全一致的顺序 drain。
- 任何 spec 层面 drain policy 的歧义（顺序、截断点、partial budget）都会让 validators 算出不同的 root → **共识停摆**。

这不是"加一个阶段"——是改变了 propose / verify 的执行模型契约。

### 2. `tx_root` 与 receipt 的对应关系

当前：
```
tx_root  = MerkleRoot(block.transactions)    ← header 上的承诺
receipt  = 1 per tx in block.transactions
externally: receipt → receipt_root → header  ← bridge / IBC 证明依赖此闭环
```

引入 tail delivery 后：
- 实际执行的工作 = `block.transactions ∪ tail_fired_this_block`
- tx_root 只承诺 user txs，**receipt 数量比 tx_root 承诺的多**
- bridge `Mailbox_E.deliver` 的 receipt-inclusion proof（`Mailbox_E.sol:118-120`，已经部署到 Sepolia）依赖一对一的 tx ↔ receipt 映射——这个映射现在断了
- 修复方式：要么在 header 加 `tail_root` 字段（**外部 breaking change**，所有已经集成的 light client / IBC 协议方都要升级），要么放弃 tx_root 承诺所有执行（**减弱了 light client 的安全模型**）

### 3. 块内 transaction index ↔ receipt index 映射

当前 `block.transactions[i]` ↔ `receipts[i]` 是连续 1:1 映射。Indexer、block explorer、bridge proof 解码、SDK 全部依赖这条假设。

tail delivery 之后，receipts 数组多出来一段不在 `block.transactions` 里的 entry——所有这些下游消费者**一次性**都要适配。

### 4. Mempool admission gate 的统一性

当前**所有进 block 的 tx——包括 deferred——都经过同一组检查**（`rpc/src/handlers/chain.rs::submit_transaction`，admission 检查段在 line 239 起）：
- nonce ≥ next（基于 storage + mempool 双向看）
- max_fee ≥ basefee × 9/8（12.5% 安全边距，line 298 检查 + line 308 拒绝日志；这个边距是 RC4 修过的 fee market bug 的修复）
- balance ≥ max-gas（line 397-403：`max_total_cost = cycles_limit × max_fee + cells_limit × max_fee`，sender_balance 不够直接拒）
- lane 预算 ≤ `LANE_SYSTEM_CYCLES`（line 253）
- digest 去重（`mempool.rs:206-208`）

tail delivery 在 executor 内部合成消息，**完全不经过这些检查**。每条都得在 executor 里重新实现一遍——这是把同一组检查放到两处实现，正是 RC4 那次 bug 的形态。

### 5. basefee 反馈环

basefee 调整公式根据每个 block 的 `total_cycles_used` vs `BLOCK_CYCLES_TARGET` 算 EIP-1559 风格的乘数。

tail delivery 让每个 block **倾向于把剩余 budget 都填满**（drain 到下一笔不够 budget 才停）。结果：
- 一个本来"半空"的 block 因 drain 一堆 tail 被记成"满载"
- basefee 持续被推高，本应回落的时候回不下来
- 攻击者可以利用这一点（见 §三.3）

### 6. Lane 预算分配

当前 4 lane（User=22M / Runner=8.8M / Timer=8.8M / System=40M cycles）独立预算。tail 必须落到某条 lane：
- 单独切第 5 lane → 同块 user txs 可用预算被压缩，**等于以削减 user-tx 容量为代价换 send 的延迟优化**
- 与 User lane 共用 → tail 可饿死 user txs（反之亦然），且 sender 无法预测自己的 send 这块 fire 还是 roll over

### 影响清单

破坏的子系统：propose/verify 共享路径、tx_root 协议、bridge proof（已部署）、indexer/explorer SDK、admission gate、basefee 反馈、lane 隔离。

**这不是"在协议上加一个 phase"——是同时撼动 6 个相互正交的子系统**。

## 三、新增的攻击面

### 1. 广度型 fanout 攻击

提案虽然禁止 recursion（"one generation per block"），但**没禁止单层广度**。一个 actor 可以在 handler 里写：

```python
def handler(payload):
    for i in range(1024):
        rt.send(targets[i], payload)
```

虽然只有"一代"，但这一代里有 1024 个分支同块 fire——block 实际执行工作量被一笔 user tx 撑爆。

要堵住这个，必须在 spec 加 per-origin/per-target/per-block 三组 cap。**这些 cap 数值必须 spec 明确写、所有 validator 按同一公式应用**——否则触发 §二.1 列的共识停摆风险。

### 2. Admission bypass

由于 tail 不经过 `submit_transaction`：
- 一笔 user tx 可以在执行中调用其它 actor，让那些 actor 触发自己的 deferred——这些 deferred **没有自己的 nonce 检查、没有自己的 fee 检查、没有 dedup**
- sender 的 nonce 只在最初的 user tx 提交时被验过；执行链中每一跳的 actor 都没有"独立的、可验证的"链上身份
- 等于把 fee market 的执行单元从 tx 降到 actor handler，但 actor handler 没有相应的 fee 隔离机制

### 3. basefee griefing

利用 §二.5 的反馈环：

```
攻击者发送一笔廉价的 user tx → 执行中触发大量 tail
→ 这个 block 满载 → basefee 上涨
→ 正常用户在下个 block 的 fee 门槛被抬高
→ 攻击者被挤掉的成本远低于他造成的 basefee 上涨
```

这是经济攻击，不是 DoS，但会让 fee market 持续偏离均衡。

### 4. 中途 OOG 的语义二义性

tail 在执行中跑，basefee 是**当前 block 的 basefee**——可能比原 user tx 提交时的 basefee 高。边界 case：

```
user tx 提交时锁了刚好够的 max_fee
user tx 跑完，basefee 因这个 block 的负载被推高
tail 现在按新 basefee 跑不起 → OOG 中断
```

要么"tail 用 user tx 提交时的 basefee 价"（不公平、可被通胀利用），要么"中途 OOG 把 user tx 一并 revert"（破坏 send 不影响 sender 的核心承诺）。两个选项都有问题。

### 5. tail 队列溢出 → "send 成功但消息丢失"

最痛苦的语义：
- sender 的 user tx 已成功 commit，receipt 已发出
- 但 tail 队列满，sender 的 deferred 被丢
- sender **认为 send 成功**（receipt 显示 OK），接收方**永远收不到**
- 当前模型不存在这种状态——deferred 进 mempool，受同一套准入和淘汰规则管理，sender 状态可观测

修这个语义要么把 send 失败信号回写到 sender 的 receipt（破坏 send 是 fire-and-forget 的承诺），要么承认这是 best-effort（破坏开发者预期）。

### 6. Receipt index 漂移

`block.transactions[i] ↔ receipts[i]` 这个假设被打破后：
- 任何依赖该映射的索引/证明工具，如果攻击者构造特定的 tail 顺序，可能触发解码错误
- 不一定是 critical 攻击面，但是新增了一类 indexer/explorer 必须面对的恶意输入

### 攻击面总结

| 风险 | 当前模型 | tail delivery 后 |
|---|---|---|
| 广度 fanout | 受 admission lane budget 限制 | 必须 spec 层加 cap，每条 cap 都是潜在共识分歧点 |
| Admission bypass | 不存在（统一 gate） | tail 全部绕过 |
| basefee griefing | 受 mempool admission 约束 | 攻击成本低于受害成本 |
| OOG 语义 | 无（每笔独立 admission） | 破坏 sender 隔离 |
| 队列溢出 | mempool 统一管理，可观测 | "send 成功但丢失"的不可见失败 |

## 四、替代方案：在 §一 表里方案 B 之外的两条改进

### 方案 B + 系统调度的事件原语

我们注意到你提案最后一段画的模型：

```
call   = 同步、原子、定向
send   = 异步、定向
timer  = 未来高度
event  = topic fanout
```

这个最终形态我们认同。问题在 event 这条**该不该构建在用户级 send 之上**。我们建议走 **timer 的同款模型**：

- Timer 当前在 `speculative.rs:526` 起的 block 内循环里，user tx 跑完后系统调度 fire 过期的 timer。这是一个**已经被验证、被 verify 节点确定性复现**的 same-block tail 模式。
- 把同样的机制扩展到**事件原语**（topic fanout）：subscriber actor 在 block N 的 user-tx 之后、由协议（不是用户 tx）调度 fire，受预算约束。

为什么这条不踩 §二/§三 的雷：
- **schedule 在执行前已经在 storage 里**（subscription 是事先注册的，跟 timer 一样），verify 节点不需要"先执行 user tx 再发现要 fire 谁"
- **触发源是协议，不是用户 send**——admission bypass 不适用，broadcast fanout 由订阅关系上限自然约束
- **basefee 和 lane 模型不变**——event 走自己的预算，跟 user lane 隔离，跟 timer 同等待遇

这能解决 "events should be fast" 的开发者诉求，**而不需要改 user `send()` 的语义**。

### `call()` 用于真正延迟敏感的同步路径

如果开发者要"零延迟、有返回值的 cross-actor"——`call()` 已经是对的工具。把延迟敏感工作引导到 `call`，把 `send` 留作最终一致性原语，正好对应你自己画的矩阵。

## 五、建议的推进顺序

下面这个顺序的逻辑是：每一步都在**工程风险尽可能小、对外部集成方影响尽可能小**的前提下，把延迟收益逐步交付。每一步之间留出测量窗口，决定要不要继续下一步。

1. **第一步：把 `min_block_interval` 降到 500 ms**（方案 B）。改 `chain/src/application.rs` 中三处构造路径上的默认值（建议同时抽出 const 集中管理）+ 测试网验证。
   - 拿到 50% 的延迟下降（500ms→250ms 最佳，1000ms→500ms 最差）
   - TPS 同步翻倍
   - §二 的所有不变量原样保留
   - 风险面：在你们实际负载下的稳定性观察

2. **第二步：引入系统调度的事件原语**，仿照 timer 的 block-内 tail 模型。
   - 解决 "events should be fast" 这条最广泛的开发者痛点
   - 不触动 user `send()` 语义、不破坏 §二 的子系统对接

3. **第三步（条件触发）：可量化的 gating metric**——第一步+第二步上线 30 天后，如果开发者关于 send 延迟的反馈率没有下降至少 50%，**自动启动 user-emitted tail delivery 的 spec RFC**。这是一个明确的、可观测的触发条件，而不是开放式的"再说"。

这个顺序的核心理由：**第一步在最小工程/外部影响下，已经拿到了你提案最理想情况下 ~50% 的延迟收益**；第二步覆盖大多数真实的事件原语用例；如果一二步之后量化 gap 仍然存在，第三步的 spec RFC 是直接展开的——那时候 §二 列出来的 6 个子系统已经有时间安排改造排期，外部集成方也有提前量做适配。
