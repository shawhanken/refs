# Cowboy: 一个具有可验证链下计算功能的 Actor 模型 Layer-1

**状态** 内部审查草案  
**类型** 标准跟踪  
**类别** 核心  
**作者** Cowboy Foundation  
**创建日期** 2025-09-17  
**更新日期** 2025-12-14  
**许可证** CCO-1.0

## 摘要

我们正处于智能体时代。大语言模型（LLM）的进步释放了软件自主行动的新模式，但这些智能系统在经济上仍然受到束缚，被困在 API 和企业账户之后。加密技术提供了缺失的元素：无需许可、可编程的经济代理。Cowboy 是一个通用 Layer-1 区块链，旨在弥合这一差距，使 AI 智能体成为数字经济的原生公民。

Cowboy 将**基于 Python 的 Actor 模型执行环境**与**权益证明共识**和**可验证链下计算市场**相结合。Cowboy 上的智能合约是**Actor**：具有私有状态的 Python 程序、消息邮箱和用于自主调度的链原生定时器。对于 LLM 推理或网络请求等繁重任务，Cowboy 集成了一个去中心化的**Runner**网络，他们在可选择的信任模型下执行任务并证明结果：N-of-M 共识、TEE 和（在 V2 中）ZK 证明。

为确保公平和可预测的资源定价，Cowboy 引入了**双计量 Gas 模型**，将计算（**Cycles**）和数据（**Cells**）的定价分离为独立的、EIP-1559 风格的费用市场。安全性由**Simplex BFT 权益证明**提供，具有快速最终性和强制提议者轮换。通过将世界上最主流的 AI 编程语言 Python 直接引入链上，Cowboy 为下一代自主智能体提供了关键基础设施。

## 引言

### 问题：智能与代理之间的鸿沟

大多数可编程链从同步函数调用模型演化而来，将存储、计算和时序耦合到单个交易中。这种范式不适合现代自主系统的异步性和复杂性。此外，它迫使开发进入 Solidity 或 Rust 等新兴生态系统，疏远了绝大多数使用 Python 构建的 AI 和企业开发者。即使对于跨越这一鸿沟的团队，结果也是运营混乱：由云服务器、cron 作业、预言机和密钥管理服务组成的"弗兰肯斯坦怪物"，由脆弱的链下胶水粘合在一起。

关键的是，这些架构无法建立信任。当智能体做出决策时——重新平衡投资组合、执行交易——用户合理地想知道原因。它看到了什么数据？它是如何决定的？今天的方法无法在输入、执行和输出之间提供可验证的链接。没有这种信任基础，自主智能体仍然是玩具，而不是稳健经济的工具。

**解决方案：Cowboy**

Cowboy 将 Actor 模型引入区块链，为自主智能体提供原生统一平台。每个应用程序都是一组 Actor；每个 Actor 是一个具有确定性执行的 Python 程序、持久键值存储和邮箱。链传递消息和定时器，强制执行资源限制，并在区块中提交状态转换。对于无法或不应在链上运行的工作，Cowboy 暴露了一个原生市场，**Runner**在其中执行链下任务并发布可验证的结果。

本文档介绍了 Cowboy 的架构、状态转换函数、费用和验证的经济机制，以及初始参数集。

### Cowboy 的关键创新

通用链在处理数据密集型、延迟敏感的应用程序时遇到困难。Cowboy 通过四项关键创新使**Actor**和**可验证链下计算**成为原生功能：

*   ***确定性 Python Actor：** 一个沙箱化的 Python VM，具有邮箱消息传递、重入（深度限制）和对世界上最流行的编程语言的一流支持。
*   ***原生定时器和调度器：** 协议级机制，用于自主、定时执行，具有动态、上下文感知的 Gas 出价，消除了对外部 keeper 网络的需求。
*   ***可验证链下计算：** 链下任务（例如，LLM 推理、API 调用）的开放市场，具有可选择的信任模型，包括 N-of-M 共识、TEE 证明和（在 V2 中）ZK 证明。
*   ***双计量 Gas：** 计算（**Cycles**）和数据/存储（**Cells**）的独立定价和 EIP-1559 风格的费用市场，以确保公平和可预测的成本。

### 账户和状态

Cowboy 区分两种对象类型：

*   ***外部账户（EOA）：** 由私钥（secp256k1）控制。它们发起交易并持有 CBY 和其他资产的余额。
*   ***Actor：** 在 PVM（Python 虚拟机）中执行的自主 Python 程序。Actor 拥有存储、接收消息，并可以向其他 Actor 发送消息。

每个对象都有一个 20 字节的地址。Actor 地址从创建者地址、盐值和代码哈希以 CREATE2 风格计算。**世界状态**是一个映射：

`State : Address -> { balance, nonce, code_hash?, storage?, metadata }`

其中 Actor 存储是一个具有配额（默认 1 MiB）和租金的键值映射。系统 Actor 和预编译合约占据地址空间的保留前缀。

### 交易和消息传递

用户通过发送**交易**（使用 secp256k1 签名）与 Cowboy 交互，指定目标、有效载荷和资源限制：**cycles 限制**和**cells 限制**，以及每个的最大价格和提示价格。

Actor 通过发送**消息**与其他 Actor 交互。消息携带小有效载荷，可以转移价值，并可能触发进一步的消息。传递是**恰好一次**，Actor 可以调度**定时器**，在未来的区块高度插入消息。为避免通过爆炸式扇出进行拒绝服务攻击，Cowboy 限制任何交易（及其触发的级联）可以排队的消息数量。

**原生定时器和 Actor 调度器**

为了实现真正的自主性，Cowboy 提供了协议原生定时器和调度机制，消除了对外部 keeper 网络的需求。Actor 可以调度消息在未来的区块高度或按重复间隔发送给自己或其他 Actor。调度器设计为可扩展、经济合理且公平。

**可扩展设计：分层日历队列** 调度器使用多层**分层日历队列**来高效管理不同时间范围的定时器，而不会影响性能。此架构由三个级别组成：

*   ***第 1 层：区块环形缓冲区：** 用于即将到来的定时器的 O(1) 队列，组织为环形缓冲区，其中每个槽代表单个区块。这以最大效率处理近期调度。
*   ***第 2 层：Epoch 队列：** 用于在未来 Epoch 中调度的中期定时器队列。此队列中的定时器在每个新 Epoch 开始时批量高效迁移到区块环形缓冲区。
*   ***第 3 层：溢出排序集：** 用于超出 Epoch 队列范围的非常长期定时器的 Merkle 化二叉搜索树，确保协议可以处理任何未来日期的调度。

这种分层设计确保处理定时器的每区块工作保持恒定且小，无论调度的定时器总数如何。

**经济合理性：Gas 出价代理（GBA）** Cowboy 调度器的一个关键创新是**Gas 出价代理（GBA）**的概念。Actor 不是预支付固定的 Gas 费用，而是指定一个 GBA（这是另一个 Actor）在其定时器到期时动态出价执行。

当定时器准备执行时，协议对 Actor 的 GBA 执行只读调用，为其提供包含实时数据的丰富上下文对象，如网络拥塞（当前基础费用）、定时器的紧迫性（已延迟多少区块）和所有者的余额。GBA 使用此上下文返回竞争性的 Gas 出价。这为区块计算预算的专用部分创建了区块内拍卖，确保高优先级任务即使在网络流量高峰期也能执行。为确保简单的开发者体验，未指定 GBA 的 Actor 会收到网络默认值。

**公平性和活跃性** 由于出价过低或网络拥塞而未执行的定时器会自动推迟到下一个区块。为防止 Actor 永久被出价超过的"定时器饥饿"情况，协议跟踪 Actor 的调度历史。它使用具有指数衰减的加权优先级系统，为定时器被反复推迟的 Actor 提供小幅提升，确保最终执行并保持网络公平性。

**定时器速率限制和 DoS 防护** 定时器系统是拒绝服务攻击的潜在向量。对手可能尝试在单个区块高度调度数百万个定时器，压倒执行能力，或使用垃圾邮件填充定时器队列以排挤合法用户。Cowboy 采用多层防御：

**每 Actor 定时器限制**

每个 Actor 在任何时候最多限制为**1,024 个活动定时器**。此硬上限防止任何单个 Actor 垄断定时器队列。尝试超出此限制的调度必须回退。

**渐进式存款模型**

创建定时器需要**存款**，该存款随 Actor 的总活动定时器数量而扩展：

`deposit(n) = base_deposit × (1 + floor(n / 100))`

其中 n 是 Actor 的当前活动定时器数量，`base_deposit` 是可治理调整的参数（默认值：**10 CBY**）。这意味着：

*   *定时器 1-99：每个 10 CBY
*   *定时器 100-199：每个 20 CBY
*   *定时器 200-299：每个 30 CBY
*   ...依此类推

当定时器触发或取消时，存款**全额退还**。此模型允许具有少量定时器的合法 Actor 以低成本运营，同时使大规模定时器垃圾邮件在资本上变得昂贵。

### 同区块指数定价

为防止 Actor 在同一目标区块调度多个定时器的"定时器炸弹"攻击，当 Actor 在同一区块高度调度多个定时器时，应用**指数附加费**：

`surcharge(k) = base_cost × 2^max(0, k - 16)`

其中 k 是此 Actor 已为目标区块调度的定时器数量。任何给定区块的前 16 个定时器按基础费率收费。超过此范围：

*   *定时器 17：2× 基础成本
*   *定时器 18：4× 基础成本
*   *定时器 19：8× 基础成本
*   *定时器 32：65,536× 基础成本

这允许合法用例（例如，Actor 在同一区块调度少量相关定时器），同时使集中式定时器攻击在经济上不可行。

### 定时器队列基础费用

类似于 cycles 和 cells 的 EIP-1559 基础费用机制，Cowboy 维护一个**定时器基础费用**，根据全局定时器队列压力进行调整：

`timer_basefee_{i+1} = timer_basefee_i × (1 + clamp((Q - T) / (T × alpha), -delta, +delta))`

其中：

*   *Q = 当前总定时器队列深度（跨所有层）
*   *T = 目标队列深度（可治理调整，默认值：**100,000**）
*   *alpha = **8**，delta = **0.125**（与 cycle/cell 基础费用相同）

当定时器队列拥塞时，基础费用上升，使定时器创建更加昂贵并自然限制需求。定时器基础费用被**销毁**，使激励与网络健康保持一致。

### 每区块执行预算

每个区块为其计算预算的专用部分保留用于定时器执行：

*   ***定时器预算：** 区块 cycle 容量的 20%（默认值：**2,000,000 cycles**）
*   *定时器通过 GBA 拍卖竞争此预算
*   *剩余的 80% 可用于用户交易

这种分离确保定时器风暴不能完全排挤常规交易，反之亦然。

**攻击缓解摘要**

| 攻击向量 | 缓解措施 |
| :--- | :--- |
| 调度数百万个定时器 | 渐进式存款（资本锁定） |
| 跨多个 Actor 的 Sybil 攻击 | 每区块执行预算限制总工作量 |
| 定时器炸弹（多个定时器，一个区块） | 同区块指数附加费 |
| 提前填充队列 | 定时器基础费用随队列深度上升 |
| 永久出价超过所有人 | 对延迟定时器的反饥饿提升 |
| DoS 然后取消退款 | 存款仅在触发/取消后退还；附加费不退 |

*注意：同区块指数附加费是**费用**，不是存款——它被销毁，取消时不退还。这防止攻击者锁定区块容量然后取消以收回成本。*

## 异步执行和多区块语义

Actor 模型的基本属性是消息传递本质上是异步的。在 Cowboy 中，当 Actor 与链下 Runner 交互时，这种异步性变得特别重要，因为任务执行可能跨越多个区块。本节定义了执行语义和开发者必须遵循的编程模型。

### 单区块原子性保证

Cowboy 仅提供**单区块内的原子性**。当 Actor 的消息处理器执行时，该处理器内的所有状态读取、写入和出站消息都是原子的——它们要么全部提交，要么全部回退。但是，**没有跨区块原子性**。一旦处理器完成且区块被最终确定，后续处理器（由回复、定时器或新消息触发）在可能不同的世界状态下执行。

### 为什么不提供跨区块交易

考虑一个读取状态、调用 Runner 并希望在结果到达时继续执行的 Actor：

```
# 概念性的 - 不是 Cowboy 的工作方式
async def handle_trade(self, msg):
    price = self.storage.get("price") # 区块 N：读取 $100
    if price < 150:
        analysis = await runner.llm(...) # 暂停... Runner 执行...
        # 区块 N+5：在此处恢复
        # 但价格现在可能是 $200
        # 分支 (price < 150) 不再有效
        self.execute_buy(price) # 危险：过时的假设
```

此模式创建了根本性问题：

1.  **过时状态：** 在 yield 之前读取的值可能已更改。
2.  **无效控制流：** 基于 yield 前状态采取的分支可能不再合适。
3.  **可组合性爆炸：** 嵌套 yield 和 Actor 到 Actor 调用创建交错的树，其中每个路径依赖于可能无效的假设。
4.  **对抗性困扰：** 攻击者可以在 yield 点之间故意改变状态以利用过时的假设。

提供跨区块原子性需要全局锁（破坏并行性并创建死锁向量）或带有回退的推测执行（创建困扰机会和不可预测的成本）。Cowboy 明确拒绝这些方法。

**消息传递延续模型**

Cowboy 不使用隐式延续，而是对所有异步操作使用**显式消息传递**。当 Actor 需要执行链下任务时，它向 Runner 系统 Actor 发送消息，并在后续区块中作为单独消息接收结果：

```
from cowboy_sdk import actor, send, RUNNER

@actor
class TradingBot:

    def handle_trade(self, msg):
        """启动交易分析 - 区块 N"""
        price = self.storage.get("price")

        if price < 150:
            # 向 Runner 系统 Actor 发送任务请求
            # 包含稍后继续所需的所有上下文
            send(RUNNER, {
                "job_type": "llm",
                "prompt": f"分析 ${price} 的买入机会",
                "reply_to": self.address,
                "reply_handler": "handle_analysis_result",
                "context": {
                    "original_price": price,
                    "request_block": current_block()
                }
            })

    def handle_analysis_result(self, msg):
        """处理 Runner 结果 - 区块 N+K"""
        result = msg.result
        context = msg.context

        # 重新读取当前状态
        current_price = self.storage.get("price")

        # 在继续之前验证假设
        if current_price != context["original_price"]:
            # 价格已更改 - 中止或重新评估
            self.storage.set("last_abort_reason", "price_changed")
            return

        # 假设有效 - 继续执行操作
        if "bullish" in result.lower():
            self.execute_buy(current_price)
```

**设计原则**

此模型体现了几个重要原则：

1.  **无隐藏控制流**
    每个状态转换都由显式消息触发。没有隐式回调或挂起的协程。开发者可以通过跟踪消息来追踪执行。
2.  **Runner 只是另一个 Actor**
    Runner 系统不是特殊语法——它是一个接收任务请求并发送结果消息的系统 Actor。相同的消息传递模式适用于 Actor 到 Actor 通信、定时器回调和 Runner 结果。
    ```
    User TX -> Actor A -> [message] -> Runner System Actor -> [off-chain execution]
                                         ↓
    Actor A <- [result message] <- Runner System Actor
    ```
3.  **显式上下文捕获**
    延续中所需的任何状态必须显式包含在 context 字段中。这迫使开发者思考哪些数据跨越 yield 边界，并防止意外闭包过时的引用。
4.  **重新验证是强制性的**
    编程模型明确表示，当 `handle_analysis_result` 执行时，这是新区块中的新交易。开发者必须重新读取并验证任何状态假设。

**关联和消息排序**

协议提供用于关联请求和响应的基础设施：
*   **关联 ID：** 每个出站任务请求包含唯一的 `correlation_id`。Runner 系统 Actor 在响应消息中包含此 ID，允许 Actor 将响应与请求匹配。
*   **无排序保证：** 如果 Actor 发送多个 Runner 请求，响应可能以任何顺序到达。Actor 必须处理乱序传递。

**超时和故障处理**

异步操作可能静默失败——Runner 可能崩溃、可能发生网络分区，或者任务可能只是耗时过长。Actor 必须为任何依赖于外部响应的操作实现超时处理。推荐模式将关联跟踪与原生定时器相结合：

```
def handle_trade(self, msg):
    correlation_id = generate_id()

    # 存储待处理请求信息
    self.storage.set(f"pending:{correlation_id}", {
        "type": "trade_analysis",
        "submitted_block": current_block(),
        "context": {...}
    })

    # 发送任务请求
    send(RUNNER, {
        "correlation_id": correlation_id,
        "job_type": "llm", ... })

    # 调度超时 - 返回 timer_id 以便稍后取消
    timer_id = set_timer(
        height=current_block() + 100,
        handler="handle_timeout",
        data={"correlation_id": correlation_id}
    )
    # 存储 timer_id 以便在结果到达时取消
    self.storage.set(f"timer:{correlation_id}", timer_id)

def handle_analysis_result(self, msg):
    correlation_id = msg.correlation_id
    # 使用存储的 timer_id 取消超时定时器
    timer_id = self.storage.get(f"timer:{correlation_id}")
    if timer_id:
        cancel_timer(timer_id)
        self.storage.delete(f"timer:{correlation_id}")

    # 处理结果
    pending = self.storage.get(f"pending:{correlation_id}")
    if pending is None:
        return # 已超时或重复
    self.storage.delete(f"pending:{correlation_id}")

    # 继续处理...

def handle_timeout(self, msg):
    correlation_id = msg.correlation_id
    pending = self.storage.get(f"pending:{correlation_id}")
    if pending is None:
        return # 结果已到达

    # 清理
    self.storage.delete(f"pending:{correlation_id}")
    self.storage.delete(f"timer:{correlation_id}")

    # 处理超时 - 重试、中止或升级
    self.handle_job_failure(correlation_id, "timeout")
```

**关键点：**
*   存储 `set_timer()` 返回的 `timer_id`，以便在结果到达时可以取消。
*   在处理之前始终检查待处理请求——它可能已被超时清理。
*   在成功和超时路径中清理所有关联状态（待处理请求、定时器引用）。
*   考虑为瞬态故障实现指数退避重试逻辑。

**SDK 人体工程学**

虽然协议使用显式消息传递，但 SDK 提供了编译到此模式的符合人体工程学的辅助函数：

```
from cowboy_sdk import actor, runner

@actor
class TradingBot:

    @runner.continuation
    async def handle_trade(self, msg):
        price = self.storage.get("price")

        if price < 150:
            # SDK 辅助函数 - 编译为消息传递
            result = await runner.llm(
                prompt=f"分析 ${price} 的买入机会",
                context={"original_price": price}
            )

            # 开发者仍然验证 - SDK 不会隐藏这一点
            if self.storage.get("price") != result.context["original_price"]:
                return

            if "bullish" in result.output.lower():
                self.execute_buy(price)
```

`@runner.continuation` 装饰器将 async 函数转换为：
1.  发送消息并存储延续状态的请求处理器。
2.  检索延续状态并恢复执行的结果处理器。

这只是语法糖——底层执行模型仍然是具有单区块原子性的显式消息传递。

**与其他模型的比较**

| 模型 | 原子性 | 开发者负担 | 抗困扰性 |
| :--- | :--- | :--- | :--- |
| Ethereum（同步调用） | 单 TX | 低 | 高 |
| 跨区块锁 | 多区块 | 低 | 低（死锁、锁困扰） |
| 乐观 + 回退 | 多区块 | 中等 | 低（回退垃圾邮件） |
| Cowboy（消息传递） | 单区块 | 中等 | 高 |

Cowboy 的方法以一些开发者便利性换取可预测的执行语义和对对抗性操作的抵抗。

## Cowboy Actor VM (PVM)

**为什么选择 Python？**

Python 是 AI 的语言和现代软件的粘合剂。这是构建者已经生活的地方，拥有庞大的开发者基础和无可匹敌的工具和库生态系统。Cowboy 将这种熟悉性转化为生产力量：编写简单的 Python 脚本并部署负责任的、始终在线的 Actor，同时协议强制执行确定性和安全性。结果是从想法到发布的路径更短，可以构建的团队渠道更广。

### 执行环境和确定性保证

Actor 是在确定性沙箱内的 PVM 中执行的**Python 程序**。为了让网络达成共识，每个节点必须从相同代码产生完全相同的结果。本节指定了保证确定性的一套全面的共识关键规则。

#### 运行时环境

*   ***无 JIT 编译：** PVM 在纯解释模式下运行。禁止即时（JIT）编译，因为 JIT 优化是跨运行和平台非确定性的来源。
*   ***确定性内存管理：** 通过确定性引用计数管理内存。禁用循环垃圾收集器。当对象的引用计数达到零时立即释放对象，确保可预测的内存行为。
*   ***固定递归限制：** 递归限制必须设置为共识定义的常量（默认值：**256**）。堆栈深度强制执行与 cycle 计量集成。

#### 数值确定性

*   ***浮点运算：** 所有浮点运算必须使用跨平台、确定性的基于软件的数学库（softfloat），而不是主机的原生 FPU。这防止了不同 CPU 架构（x86 vs ARM，不同的 FPU 实现）之间的微变化。
*   ***整数算术：** Python 的任意精度整数是确定性的。没有溢出行为在不同平台之间变化。
*   ***Decimal 模块：** 如果 decimal 模块包含在白名单中，它必须使用固定舍入模式（ROUND_HALF_EVEN）和固定精度，在共识级别指定。
*   ***数学函数：** 超越函数（sin、cos、log、exp 等）必须使用 softfloat 库的确定性实现，而不是平台原生 libm。

#### 哈希种子和集合排序

Python 的默认哈希随机化（`PYTHONHASHSEED`）是非确定性的关键来源。PVM 强制执行：

*   ***固定哈希种子：** `PYTHONHASHSEED` 必须设置为共识定义的常量（0）。这确保 `hash()` 在所有节点上返回相同的值。
*   ***字典排序：** Python 3.7+ 保证 dict 的插入顺序迭代。这是确定性的且允许的。
*   ***集合替换：** 内置的 `set` 和 `frozenset` 类型即使使用固定哈希种子也具有非确定性迭代顺序（由于哈希冲突和表调整大小）。PVM 必须将 `set` 替换为 `ordered_set`，这是标准库提供的插入顺序集合实现。使用 `set` 语法的代码透明地接收 `ordered_set` 语义。
*   ***禁止哈希操作：** Actor 不得依赖 `hash()` 值用于任何持久化到存储或发送在消息中的内容，因为哈希值不能保证在 PVM 版本之间稳定。

**字符串和文本处理**

*   ***Unicode 规范化：** 所有字符串比较必须使用 NFC（规范分解，后跟规范组合）规范化。PVM 在接收时将所有输入字符串规范化为 NFC。
*   ***固定区域设置：** 区域设置必须固定为 C.UTF-8（POSIX）。依赖于区域设置的操作（排序、大小写转换）使用 Unicode 规则，而不是系统区域设置。
*   ***大小写折叠：** 不区分大小写的比较必须使用 Unicode 大小写折叠（`str.casefold()`），这是独立于区域设置的。
*   ***字符串驻留：** 用户代码中禁止对字符串进行身份比较（`is`）。PVM 可能引发警告或错误。使用相等性（`==`）进行字符串比较。
*   ***编码：** 所有字符串都是 UTF-8。其他编码必须通过 `encode()`/`decode()` 使用 `errors='strict'` 策略显式转换。

**序列化**

跨越信任边界的所有数据（存储、消息、Runner 任务参数）必须使用规范序列化格式：

*   ***格式：** CBOR（RFC 8949），具有核心确定性编码要求（第 4.2 节）。
*   ***规范规则：**
    *   映射键必须按其编码形式的字节字典序排序。
    *   整数必须使用最短编码。
    *   无不定长度数组或映射。
    *   浮点数必须编码为 64 位 IEEE 754（无 float16/float32 降级）。
    *   无重复映射键。
*   ***禁止：** pickle 模块被禁止。它是非确定性的、不安全的且依赖于版本的。
*   ***JSON：** 如果需要 JSON 用于人类可读输出，`json.dumps()` 必须使用 `sort_keys=True`、`separators=(',',':')` 和 `ensure_ascii=False`。
*   ***自定义类型：** 需要序列化的用户定义类必须实现 `__cowboy_serialize__()` 和 `__cowboy_deserialize__()` 协议方法。

**模块和依赖管理**

*   ***白名单导入：** Actor 只能从严格的、共识定义的白名单导入模块。每个模块固定到确切版本。
*   ***无 C 扩展：** C 扩展模块（numpy、pandas 等）被禁止。它们引入硬件相关行为、平台特定优化，并且难以审计确定性。
*   ***无动态导入：** `importlib`、`__import__()` 和动态模块加载被禁止。
*   ***初始白名单（v1）：**
    *   `collections`、`dataclasses`、`enum`、`functools`、`itertools`
    *   `json`（具有规范约束）、`re`、`struct`
    *   `math`（确定性实现）、`decimal`（固定精度）
    *   `typing`、`abc`
    *   `hashlib`（用于 keccak256、sha256）
    *   `cowboy_sdk`（Cowboy 标准库）
    其他模块可以在确定性审计后通过治理添加。

**异常处理**

*   ***异常类型：** 异常类型及其继承层次结构是确定性的。
*   ***异常消息：** 异常消息字符串可能在不同平台或 Python 版本之间变化。Actor 不得基于异常消息文本内容进行分支。
*   ***回溯：** 回溯对象在任何链上存储或消息传递之前被剥离。它们仅可用于本地调试。

**禁止的操作和模式**

以下操作被禁止，并在解析时或运行时引发 `DeterminismError`：

| 类别 | 禁止 |
| :--- | :--- |
| **系统** | `sys.exit()`、`os.environ`、`os.system()`、`subprocess.*` |
| **时间** | `time.time()`、`datetime.now()`、`time.sleep()` |
| **随机性** | `random.*`（改用 `cowboy_sdk.vrf`） |
| **网络** | `socket.*`、`urllib.*`、`http.*`、`requests.*` |
| **文件系统** | 除 `/tmp` 临时空间外的所有内容（256 KiB 限制，处理器后擦除） |
| **反射** | `eval()`、`exec()`、`compile()`、`globals()` 修改、模块上的 `setattr()` |
| **内省** | `sys._getframe()`、`inspect.currentframe()`、`gc.*` |
| **弱引用** | `weakref.*`（非确定性收集时序） |
| **线程** | `threading.*`、`multiprocessing.*`、`concurrent.*` |
| **身份** | 对字符串或数字的 `is` 比较（使用 `==`） |

**确定性测试**

参考 PVM 实现包括一个**确定性测试工具**，它：
1.  在多个平台（x86、ARM）和 Python 构建上执行 Actor 代码。
2.  比较所有输出、状态转换和 cycle 计数。
3.  将任何分歧标记为共识关键错误。

部署到主网的 Actor 应在开发期间使用此工具进行测试。

每个处理器调用接收固定数量的内存（默认 10 MiB），并以 cycles 和 cells 计量。

Actor 存储是持久的，并受**租金**约束。此机制保持全节点紧凑，并鼓励高效的数据生命周期策略。

### 新的安全模型

以太坊生态系统中绝大多数钱包黑客攻击是由于代码审计错误。虽然借鉴了过去十年以太坊、Solidity 和比特币的经验教训，但我们的新安全模型很简单：代码易于阅读。Python 的现有分析和审计工具，结合 Cowboy 的原生防护和装饰器，在防止链上攻击方面具有天然优势。

#### 存储和状态持久化

Cowboy 的存储架构设计用于可验证性、性能和跨 VM 兼容性。它建立在三层模型上：

1.  **账本：** 区块的仅追加日志，作为所有交易的顺序、历史真相来源。
2.  **Triedb：** 规范状态存储库，使用**Merkle-Patricia Trie (MPT)**，类似于以太坊，为每个区块生成可验证的 `state_root`。此层保存所有账户、代码和存储的权威状态。
3.  **辅助索引：** 可重建的、读取优化的表，用于交易哈希或事件主题等数据。这些索引派生自账本和 Triedb，允许快速查询，而无需成为共识关键状态根的一部分。

此设计确保与现有基于 MPT 的工具兼容，同时提供增强的查询性能。

**跨 VM 兼容性**

为了支持原生 Python VM (PVM) 和未来的 EVM 执行环境，状态 trie 设计为 VM 中立。

*   ***状态分离：** `vm_ns`（VM 命名空间）标志直接嵌入到存储键中。这允许同一地址的 PVM 和 EVM 存储槽共存而不冲突，使单个 Actor 地址可以在两个环境中都有状态。
*   ***跨 VM 调用：** 在协议级别定义了标准化 C-ABI（应用程序二进制接口）包装器。这允许存储层保持中立，同时实现 PVM 和 EVM 之间的无缝和可预测调用。

所有 Actor 存储都受**状态租金**约束，以 CBY 支付。此机制要求 Actor 为其占用的存储随时间付费，防止状态膨胀并鼓励高效的数据管理。如果未支付租金，存储可能在宽限期后被网络修剪。

**定价：Cycles 和 Cells**

以太坊引入了**gas**作为单个标量。Cowboy 将定价拆分为两个独立的计量器：

*   ***Cycles** 测量计算：Python 操作和主机调用（例如，send、set-timer、blob-commit）每个都有固定成本。Cycles 类似于**Erlang reductions**：限制处理器运行时间的离散步骤预算。
*   ***Cells** 测量字节：调用数据、返回数据、blob 和存储都消耗 cells。

每个区块使用熟悉的 EIP-1559 反馈循环调整两个基础费用（每个计量器一个）。用户为每个计量器指定最大价格和可选提示。基础费用被**销毁**，而提示支付给验证者。这种双模型使费用更加可预测和公平。

**链上计量**

为确保确定性执行，Cowboy 的链上资源消耗被精确计量：

*   ***Cycles：** 通过在字节码级别检测 Python VM 来计量计算工作。每条指令都有固定的 Cycle 成本，在共识关键成本表中定义。此方法确保所有计算路径，包括循环和函数调用，都被准确测量。
*   ***Cells：** 数据和存储工作在特定 I/O 边界计量。Cells（其中 1 Cell = 1 字节）用于交易有效载荷、返回数据、状态存储（`storage_set`）和 Actor 在执行期间使用的临时临时空间。

这种严格的、确定性的计量是对计算和基于状态的拒绝服务攻击的主要防御。

**链下费用模型** 区分链上 gas 和链下任务费用至关重要。协议**不**计算 Runner 执行的 gas。相反，它促进一个自由市场，Runner 在其中设定自己的价格。

Runner 的运营成本（CPU 时间、内存、数据传输）决定其在给定任务上的市场价格。Runner 可以自由忽略他们认为价格过低的任务。此模型允许对现实世界资源进行有效的价格发现，并适应广泛的计算任务，从简单的数据获取到密集的 AI 模型推理，而不会用非确定性和复杂的成本计算来负担链上共识。

### 链下计算：Runner 市场

许多应用程序需要访问网络数据、ML 推理或繁重的转换。任何 Actor 都可以发布带有价格和延迟目标的任务。**Runner**——质押 CBY 的链下工作者——接收任务、执行它们并发布结果。

此市场是**可验证的**：链在开发者选择的各种信任模型下接受结果。撒谎或错过截止日期的 Runner 面临被挑战和**削减**的风险。

**异步任务框架和 Runner 可靠性**

为确保链下计算不影响核心网络的稳定性，Cowboy 实现了完全异步和延迟任务框架。链下任务的生命周期与主交易流解耦：

1.  **任务提交：** Actor 通过调用调度器合约提交任务。提交定义任务、所需的 Runner 数量，以及指定预期输出格式和约束（例如，最大返回大小）的 `result_schema`。
2.  **Runner 选择和健康：** 使用可验证随机函数（VRF）隐式和确定性地为任务选择 Runner 委员会。此选择来自动态**活动 runner 列表**。要保留在此列表中，Runner 必须定期发送 `heartbeat()` 交易，确保任务仅分配给被证明在线和响应的节点。
3.  **执行和提交：** 选定的 Runner 执行任务。如果 Runner 选择不执行工作，它可以调用 `skip_task` 函数，显式和可验证地将责任传递给确定性序列中的下一个 Runner。结果提交到专用合约。
4.  **延迟回调：** 一旦收集到所需数量的结果，系统构建并签署一个_延迟交易_。此交易包含对原始 Actor 回调函数的调用，然后在未来区块中执行。

此延迟模型确保即使长时间运行的链下任务或网络延迟也不会阻塞链的主要执行。强制性的 `result_schema` 为 Runner 提供清晰度，而健康和跳过机制创建了一个健壮且自愈的链下工作者网络。

**Cowboy 的链下分层信任模型**

| 模式 | 信任级别 |
| :--- | :--- |
| **N-of-M 法定人数** | Runner 执行结果；运行时接受委员会的共识结果。 |
| **带争议的 N-of-M** | Runner 质押保证金；争议者可以在固定窗口内证明不正确的结果。 |
| **TEE 证明** | N-of-M 委员会或单个 runner 在可信执行环境中执行结果。 |
| **ZK 证明（v2）** | Runner 提供带有结果的 zk-SNARK 用于密码学验证。 |

Runner 和 Actor 通过其**Entitlements**匹配，这是一个用于策略和安全约束（例如，仅 TEE、数据驻留）的框架。

**Runner 资源核算和定价**

链下计算不能由协议直接计量——runner 在自己的硬件上在共识之外执行。本节指定 Cowboy 如何处理资源核算、价格发现和链下任务的支付。

**资源边界** 每个任务提交必须包含由 Actor 指定的显式资源边界：

```
job_spec = {
    "type": "llm",
    "model_id": "0x...",        # 注册的模型哈希
    "prompt": "...",
    "bounds": {
        "max_input_tokens": 4000,      # 最大输入大小
        "max_output_tokens": 2000,     # 最大输出大小
        "max_wall_time_seconds": 60,   # 最大执行时间
        "max_memory_mb": 512,          # 最大内存使用
        "max_retries": 2,              # 瞬态故障重试
        "max_price": 100_000_000       # 最大价格（CBY wei）
    },
    "trust_model": "n_of_m",
    "tee_required": false
}
```

边界服务于多个目的：
*   *成本上限：* Actor 在提交前知道其最大风险敞口。
*   *Runner 过滤：* Runner 可以评估他们是否能在边界内完成任务。
*   *超时强制执行：* 超过 `max_wall_time_seconds` 的任务被视为失败。
*   *DoS 防护：* 无边界任务在提交时被拒绝。

如果 runner 无法在指定边界内完成任务，任务失败。Runner 不会因未能完成不可能的任务而受到惩罚（见下面的支付和故障处理）。

**价格发现：发布价格与优先提示** Cowboy 使用结合发布价格和可选优先提示的混合定价模型：

**Runner 费率卡**

Runner 向 Runner 注册表发布费率卡，指定每个资源单位的价格：

```
rate_card = {
    "runner_address": "0x...",
    "rates": {
        "llm_input_token": 1000,      # 每个输入 token 的 CBY wei
        "llm_output_token": 3000,     # 每个输出 token 的 CBY wei
        "http_request": 50000,        # 每个 HTTP 请求的 CBY wei
        "compute_second": 10000,      # 每秒计算的 CBY wei
        ...
    },
    "supported_models": ["0x...", "0x..."],
    "min_job_value": 10000,           # 最小任务大小
    "max_job_value": 10_000_000_000,  # 最大任务大小
    "entitlements": ["tee_sgx", "region_us"]
}
```

费率卡存储在链上，可以由 runner 随时更新（受冷却期限制以防止操纵）。

**任务定价**

当 Actor 提交任务时，预期价格从 runner 的费率卡和任务的资源边界计算：

`expected_price = Σ(rate[resource] × bounds[resource])`

Actor 在提交时托管 `max_price`。实际支付为：

`actual_payment = min(reported_usage × rates, max_price)`

**优先提示**

对于时间敏感的任务，Actor 可以包含直接支付给 runner 的**提示**：

```
job_spec = {
    ...
    "max_price": 100_000_000,
    "tip": 10_000_000, # 优先提示，完成时支付
}
```

提示激励 runner 在高需求期间优先处理任务。提示在基于使用的费用之外支付。

**Runner 选择**

当提交任务时，协议：
1.  按 entitlements 过滤 runner（Actor 的要求 ⊆ runner 的能力）。
2.  按支持的模型过滤 runner。
3.  按价格过滤 runner（runner 的预期价格 ≤ Actor 的 `max_price`）。
4.  从符合条件的 runner 中通过 VRF 选择委员会。

这创建了一个竞争市场：费率较低和 entitlements 更好的 runner 更有可能被选中。

**资源报告的信任模型** Runner 在提交结果时报告其实际资源使用情况。协议使用**信任但验证**模型，具有逐步升级的保证级别：

**默认：基于声誉的信任**

对于大多数任务，协议信任 runner 报告的使用情况，但受以下约束：
1.  **声誉分数：** Runner 基于成功完成任务、争议失败和正常运行时间积累声誉。低声誉 runner 可能被排除在任务选择之外。
2.  **异常检测：** 如果报告的使用情况 >2× 预期使用情况（基于任务类型和历史数据），结果会自动标记以供审查。
3.  **欺诈削减：** 如果 runner 被证明误报了使用情况（通过挑战），他们被削减 30% 的质押。

**可选：TEE 证明计量**

对于高价值任务或需要更强保证时，Actor 可以设置 `tee_required: true`。在 TEE 模式下：
1.  Runner 在可信执行环境（SGX、TDX 或 SEV）内执行任务。
2.  TEE 测量实际资源消耗。
3.  Runner 随结果提交证明报告。
4. 协议根据已知良好的 TEE 测量验证证明。
5. 证明中报告的使用情况是权威的。

TEE 证明的任务要求溢价（runner 为 TEE 执行设定单独费率），但提供正确计量的密码学保证。

**证明验证**

TEE 证明由专用系统 Actor（`0x97` TEE 验证器）验证，它维护：
*   可信 TEE 签名密钥的注册表（通过治理更新）。
*   批准的 runner 软件的预期测量哈希。
*   受损密钥的撤销列表。

**支付和故障处理**

支付取决于任务的结果和任何故障的原因：

| 结果 | Runner 支付 | Actor 退款 | 理由 |
| :--- | :--- | :--- | :--- |
| **成功** | `min(reported_usage × rates, max_price) + tip` | `max_price - actual_payment` | 正常完成 |
| **Runner 故障**（超时、无效结果、崩溃） | 0 | 100% 托管 | Runner 未能执行 |
| **不可能的任务**（边界过紧） | 0 | 100% 托管 | Actor 设定了不切实际的边界 |
| **Actor 故障**（格式错误的输入） | 0 | 0 | Actor 提交了错误的任务 |
| **外部故障**（API 关闭、模型不可用） | 基于进度的按比例 | 托管余额 | 双方均无过错 |
| **超时（无过错）** | 最低费用（gas 成本回收） | 托管余额 | 网络延迟，无人有过错 |

**确定故障**

故障确定遵循以下规则：
1.  **Runner 故障：** Runner 接受了任务但未能在边界内交付有效结果。证据：超过超时、结果未能通过模式验证，或 N-of-M 法定人数显示不同结果。
2.  **不可能的任务：** Runner 证明任务无法在边界内完成。证据：多个 runner 报告相同的故障模式（例如，"输出在 50% 完成时超过 max_tokens"）。
3.  **Actor 故障：** 任务输入格式错误或违反协议规则。证据：输入的模式验证失败，或 runner 返回标准化错误代码。
4.  **外部故障：** 由于外部依赖导致的故障。证据：runner 提供外部故障证明（例如，HTTP 503 响应、API 速率限制）。

**按比例支付**

对于不可能的任务和外部故障，runner 基于可证明的进度获得部分支付：

`pro_rata_payment = (work_completed / total_work_estimate) × expected_price`

对于 LLM 任务，`work_completed` 以失败前生成的 token 数测量。对于 HTTP 任务，可以以完成的请求数测量。对于 MCP 任务，以完成的工具调用数测量。Runner 必须提供部分完成的证据（例如，部分输出、中间状态哈希）。

**争议解决** 任何一方都可以在挑战窗口（15 分钟）内挑战任务结果：

**Actor 挑战 runner（收费过高）：**
1.  Actor 发布 100 CBY 保证金。
2.  Actor 提供证据：基准数据、可比较的任务成本、统计分析。
3.  仲裁：如果报告的使用情况 >3σ 高于任务类型的预期，则假定 runner 收费过高。
4.  解决：Runner 被削减，Actor 退还差额 + 挑战者奖励。

**Runner 挑战 Actor（不公平的故障分配）：**
1.  Runner 发布 100 CBY 保证金。
2.  Runner 提供证据：执行日志、TEE 证明、外部故障证明。
3.  仲裁：根据故障标准审查证据。
4.  解决：如果 runner 被错误地归咎，则收到支付 + 保证金返还；Actor 失去争议保证金。

**第三方挑战（串通、欺诈）：**
1.  任何人都可以挑战可疑模式（例如，runner 和 Actor 在虚假任务上串通）。
2.  证据：链上分析、统计异常。
3.  解决：如果证明串通，双方都被削减，挑战者获得奖励。

**反游戏措施** 资源核算系统包括防止操纵的保护措施：
1.  **费率卡冷却：** Runner 每个 epoch（1 小时）最多只能更改一次费率。防止诱饵和转换。
2.  **最小任务价值：** Runner 可以设定最小任务价值以避免垃圾邮件。
3.  **声誉衰减：** 声誉分数随时间衰减，需要持续的良好行为。
4.  **Sybil 抵抗：** 新 runner 从零声誉和有限任务分配开始。建立声誉需要质押锁定时间。
5.  **价格区间：** 治理可以为任务类型设定可接受的价格范围。超出区间的 runner 被标记（不排除，但对 Actor 可见）。

**LLM 结果验证**

LLM 输出提出了独特的验证挑战：与确定性计算不同，相同的提示可以产生语义等价但字节不同的输出。本节定义 Cowboy 如何在本质上非确定性的结果上达成共识。

**非确定性输出的挑战** 对于确定性任务（例如，HTTP 获取、哈希计算），验证很简单——所有诚实的 runner 产生相同的输出。LLM 推理打破了这一假设：

```
提示："法国的首都是什么？"

Runner 1："法国的首都是巴黎。"
Runner 2："巴黎是法国的首都。"
Runner 3："法国的首都是巴黎。"
```

所有三个输出都是正确的，但没有一个字节对字节匹配。传统的 N-of-M 法定人数失败。即使使用相同的模型权重、`temperature=0` 和固定种子，跨硬件的浮点变化也可能产生不同的 token 序列。

对于主观任务（摘要、创意写作、推荐），问题加深——可能没有单一的"正确"答案。

**验证模式** Cowboy 提供适合不同任务类型的多种验证模式。Actor 根据其正确性要求和成本容忍度选择适当的模式：

| 模式 | Runner | 验证 | 挑战范围 | 成本 | 用例 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| none | 1 | 无 | 仅未交付 | 最低 | 原型设计、低风险 |
| economic_bond | 1 | 客观检查 | 客观故障 | 低 | 主观生成 |
| majority_vote | N-of-M | 字段值投票 | 客观故障 | 中等 | 分类 |
| structured_match | N-of-M | 验证器函数 | 客观故障 | 中等 | 结构化提取 |
| deterministic | N-of-M | 精确匹配 + TEE | 完全重现 | 高 | 关键确定性 |
| semantic_similarity | N-of-M | 嵌入阈值 | 客观故障 | 高 | 具有相似性的主观 |

任务规范中的模式选择：

```
job_spec = {
    "type": "llm",
    "model_id": "0x...",
    "prompt": "...",
    "verification": {
        "mode": "structured_match",
        "runners": 3,
        "threshold": 2, # 3 个中必须有 2 个同意
        "checks": [...]
    }
}
```

**验证模式详情**

**none 模式**
单个 runner，无验证。协议仅保证在边界内返回了结果。没有输出质量的挑战窗口。
```
"verification": {"mode": "none"}
```
用于：原型设计、内部逻辑、高容量低风险任务，其中速度比正确性保证更重要。

**economic_bond 模式**
单个 runner 发布保证金。输出仅受客观检查约束。Actor 接受主观风险。
```
"verification": {
    "mode": "economic_bond",
    "bond_multiplier": 2.0, # Runner 质押 2 倍任务价值
    "objective_checks": ["schema_valid", "min_length", "no_prompt_leak"]
}
```
用于：主观生成（摘要、创意写作），其中市场而非协议判断质量。主观输出较差的 runner 会随时间失去声誉，因为 Actor 避免使用它们。

**majority_vote 模式**
N-of-M runner 执行任务。指定字段必须达成多数共识。
```
"verification": {
    "mode": "majority_vote",
    "runners": 5,
    "threshold": 3,
    "vote_field": "classification" # 要投票的字段
}
```
当 ≥`threshold` 个 runner 为 `vote_field` 返回相同值时，结果被接受。其他字段（例如，推理）从任何同意的 runner 中获取。
用于：分类、情感分析、是/否决策、分类输出。

**structured_match 模式**
N-of-M runner 执行任务。使用 SDK 验证器函数在指定字段上比较结果。
```
"verification": {
    "mode": "structured_match",
    "runners": 3,
    "threshold": 2,
    "checks": [
        {"fn": "json_schema_valid", "schema": {...}},
        {"fn": "structured_match", "fields": ["entity_name", "entity_type"]},
        {"fn": "numeric_tolerance", "field": "confidence", "tolerance": 0.05}
    ]
}
```
用于：实体提取、数据解析、结构化问答、任何具有明确定义输出字段的任务。

**deterministic 模式**
N-of-M runner 使用固定配置执行。输出必须完全匹配。需要 TEE 证明。
```
"verification": {
    "mode": "deterministic",
    "runners": 3,
    "threshold": 3, # 全部必须匹配
    "tee_required": true,
    "inference_config": {
        "temperature": 0,
        "seed": 12345,
        "framework": "vllm@0.4.1"
    }
}
```
用于：需要可重现性的关键决策、审计跟踪、监管合规。

**semantic_similarity 模式**
N-of-M runner 执行任务。使用嵌入相似性比较输出。
```
"verification": {
    "mode": "semantic_similarity",
    "runners": 3,
    "threshold": 2,
    "similarity_threshold": 0.85,
    "embedding_model": "0x..." # 固定的嵌入模型
}
```
Runner 使用指定模型在本地计算嵌入。如果余弦相似性超过阈值，则认为结果匹配。至少 `threshold` 个 runner 必须形成匹配集群。

*信任假设：* 此模式的安全性取决于社区对指定嵌入模型的信任。受损或选择不当的嵌入模型可能将语义不同的输出映射到相似的向量，从而破坏验证。Actor 应使用协议批准集中的成熟、确定性嵌入模型。

用于：摘要、释义、翻译——语义等价性比确切措辞更重要的任务。

**SDK 验证器函数** SDK 为 `structured_match` 模式提供标准验证器函数库。这些与主任务一起在 runner 上执行：

| 函数 | 描述 | 参数 |
| :--- | :--- | :--- |
| `exact_match()` | 字节对字节相等 | — |
| `json_schema_valid(schema)` | 根据 JSON 模式验证 | `schema`: JSON Schema 对象 |
| `structured_match(fields)` | 指定字段必须匹配 | `fields`: 字段名列表 |
| `majority_vote(field)` | 字段值 >50% 同意 | `field`: 字段名 |
| `supermajority_vote(field, threshold)` | 字段值 >`threshold` 同意 | `field`、`threshold` |
| `numeric_tolerance(field, tolerance)` | 数字在 ±`tolerance` 内 | `field`、`tolerance` |
| `numeric_range(field, min, max)` | 数字在边界内 | `field`、`min`、`max` |
| `set_equality(field)` | 无序集合相等 | `field` |
| `contains_all(substrings)` | 输出包含必需字符串 | `substrings`: 列表 |
| `contains_none(substrings)` | 输出排除字符串 | `substrings`: 列表 |
| `regex_match(pattern)` | 输出匹配正则表达式 | `pattern` |
| `length_bounds(min, max)` | 输出长度在边界内 | `min`、`max` |
| `semantic_similarity(threshold)` | 嵌入余弦相似性 | `threshold` |
| `no_prompt_leak()` | 输出不包含系统提示 | — |
| `entropy_check(min_entropy)` | 输出不是重复/退化的 | `min_entropy` |

**自定义验证器函数**
Actor 可以将自定义验证器函数部署为 Actor。自定义验证器在 runner 提交后由协议调用：
```
"verification": {
    "mode": "structured_match",
    "checks": [
        {"fn": "json_schema_valid"},
        {"fn": "custom", "actor": "0x...", "method": "verify_output"}
    ]
}
```
自定义验证器 Actor 接收：
*   任务规范。
*   所有 runner 输出。
*   Runner 元数据（地址、证明）。
并返回：
*   `{valid: true, canonical_output: ...}` — 接受，带有可选规范输出。
*   `{valid: false, reason: ...}` — 拒绝所有输出。

自定义验证器执行消耗链上 cycles（由 Actor 支付）。这实现了特定领域的验证逻辑（例如，根据数据库检查 SQL 查询结果，验证代码编译）。

**客观故障标准** 无论验证模式如何，某些故障是客观可验证的，并导致 runner 削减：

| 故障 | 检测 | 惩罚 |
| :--- | :--- | :--- |
| 模式违反 | 输出未能通过声明的 JSON 模式 | 削减 10% |
| 超时 | 在 `max_wall_time` 内无结果 | 削减 5% |
| 空/垃圾输出 | 输出低于 `min_length` 或未能通过熵检查 | 削减 10% |
| 错误模型 | TEE 证明显示不同的模型哈希 | 削减 30% |
| 未交付 | Runner 接受了任务但从未提交 | 削减 20% |
| 提示注入泄漏 | 输出包含系统提示标记 | 削减 15% |

这些检查自动运行。无需挑战——协议检测并惩罚。

**主观正确性和市场** 对于主观输出（摘要、创意内容、推荐），Cowboy 明确**不**尝试定义"正确"。相反：
1.  **Actor 接受风险** 当选择 `economic_bond` 或 `none` 模式时。
2.  **声誉反映质量** — 收到较差输出的 Actor 停止使用该 runner。
3.  **竞争驱动质量** — 输出更好的 runner 获得更多任务。
4.  **透明度实现选择** — runner 统计（完成率、争议率、重复使用）是公开的。

此理念反映了一个关键设计原则：**协议保证执行完整性，而不是输出质量**。质量是市场结果。

**按模式的挑战范围**

| 模式 | 可挑战 | 所需证据 |
| :--- | :--- | :--- |
| none | 仅未交付 | 超时证明 |
| economic_bond | 客观故障 | 模式/熵/泄漏检查 |
| majority_vote | 客观故障 | 模式/熵/泄漏检查 |
| structured_match | 客观故障 | 模式/验证器检查 |
| deterministic | 完全重现 | 匹配配置 + 不同输出 |
| semantic_similarity | 客观故障 | 模式/熵/泄漏检查 |

对于确定性模式，挑战者可以通过提供重现证据来争议：确切配置 + 重新执行产生不同输出的证明。协议选择中立的 runner 进行验证。

**外部数据和预言机语义**

Cowboy Actor 经常需要访问外部数据：价格源、Web API、公共数据集和网页。与链上计算不同，外部数据本质上是可变的和非确定性的。本节定义 Cowboy 如何处理外部数据源的验证。

**非确定性来源** 外部数据获取可能因合法原因产生不同结果：

| 来源 | 示例 |
| :--- | :--- |
| 内容更改 | 在 runner 请求之间更新网站 |
| 地理变化 | 向不同地区提供不同内容 |
| 时间敏感性 | 价格、新闻每秒变化 |
| 速率限制 | 某些 runner 被限制，其他没有 |
| CDN 缓存 | 不同的边缘节点提供不同版本 |
| A/B 测试 | 站点向不同用户提供不同版本 |
| 动态渲染 | JS 渲染的内容因时序而变化 |

即使使用 N-of-M 法定人数，在几秒钟内访问相同 URL 的 runner 也可能收到不同的响应。协议必须定义"共识"对于可变数据的含义。

**数据源分类** 不同的外部数据源需要不同的验证策略：

| 类型 | 特征 | 验证策略 |
| :--- | :--- | :--- |
| 确定性 API | 版本化、稳定、结构化（区块链 RPC、静态文件） | 精确匹配 |
| 半稳定 API | 具有可变元数据的结构化（带时间戳的 REST API） | 结构化匹配，忽略元数据 |
| 时间序列数据 | 值随时间变化（价格源） | 中位数/多数，具有新鲜度边界 |
| Web 抓取 | 非结构化、高度可变（HTML 页面） | 基于提取的匹配 |
| 认证端点 | 需要凭据 | 单个 runner + TEE + 密钥管理 |

**新鲜度要求** Actor 指定数据新鲜度约束：
```
job_spec = {
    "type": "http",
    "url": "https://api.exchange.com/price/BTC",
    "freshness": {
        "max_age_seconds": 10,
        "timestamp_field": "$.data.timestamp",
        "reference": "block" # 或 "submission", "absolute"
    }
}
```
参考模式：
*   `block` — 数据时间戳必须在结果提交时区块时间戳的 `max_age_seconds` 内。
*   `submission` — 数据时间戳必须在任务提交时间的 `max_age_seconds` 内。
*   `absolute` — Actor 指定确切时间戳；数据必须来自该时间点（容差）。

Runner 必须：
1.  从源获取数据。
2.  从指定字段提取时间戳（如果未指定字段，则使用获取时间）。
3.  如果时间戳超出新鲜度窗口，则拒绝并重试。
4.  在结果证明中包含获取元数据。

**快照模式** 当多个 runner 获取可变数据时，协议必须选择规范结果。Actor 指定快照语义：
```
job_spec = {
    "type": "http",
    "url": "...",
    "snapshot": {
        "mode": "first_valid"
    }
}
```
可用模式：
*   `first_valid` — 第一个提交有效结果的 runner 设置规范快照。其他 runner 验证他们可以获得类似数据（在验证容差内），但第一个结果是权威的。最适合：Web 内容、API 响应，其中任何有效快照都可接受。
*   `median` — 对于数值数据，取所有 runner 结果的中位数。异常值（超出 `outlier_threshold`）被标记但不阻止共识。最适合：价格源、数值测量。
    ```
    "snapshot": {
        "mode": "median",
        "outlier_threshold": 0.02 # 标记距离中位数 >2% 的结果
    }
    ```
*   `majority` — 对于分类或结构化数据，接受多数 runner 返回的值。最适合：状态检查、布尔条件、分类 API 响应。
*   `latest` — 接受最新的有效结果（按时间戳）。当严格偏好更新数据时有用。最适合：快速变化的源，其中新近性胜过共识。

**基于提取的验证** 对于 Web 抓取和非结构化源，比较提取的数据而不是原始响应：

```
job_spec = {
    "type": "http_extract",
    "url": "https://disclosures.house.gov/...",
    "extraction": {
        "method": "css_selector", # 或 "xpath", "regex", "jsonpath"
        "selectors": {
            "representative": "div.member-name::text",
            "ticker": "td.asset-ticker::text",
            "transaction_type": "td.tx-type::text",
            "amount": "td.amount::text"
        },
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "representative": {"type": "string"},
                    "ticker": {"type": "string"},
                    "transaction_type": {"enum": ["buy", "sell"]},
                    "amount": {"type": "string"}
                }
            }
        }
    },
    "verification": {
        "mode": "structured_match",
        "runners": 3,
        "threshold": 2,
        "fields": ["[*].ticker", "[*].transaction_type"]
    }
}
```

Runner：
1.  获取 URL。
2.  将提取规则应用于原始响应。
3.  根据模式验证提取的数据。
4.  提交提取的数据（不是原始 HTML）。

验证比较 runner 之间的提取字段。原始响应差异（广告、时间戳、会话令牌）不会导致验证失败。

**域 Entitlements** HTTP 访问由 Entitlements 系统管理。Actor 声明他们需要访问的域，runner 宣传他们可以获取的域：

```
# Actor entitlement（在部署清单中）
"entitlements": {
    "http_domains": ["api.coingecko.com", "disclosures.house.gov"]
}

# Runner 能力
"capabilities": {
    "http_domains": ["*"] # 或特定列表
}
```

协议为常见用例提供精选域集：

| 域集 | 内容 |
| :--- | :--- |
| `price_feeds` | 主要交易所 API、CoinGecko 等 |
| `government_us` | SEC、国会、联邦公报 |
| `social_apis` | Twitter/X API、Reddit API（认证） |
| `blockchain_rpc` | 以太坊、比特币、主要 L2 RPC 端点 |

Actor 可以要求域集：
```
"entitlements": {
    "http_domain_set": "price_feeds"
}
```
不支持所需域的 runner 被排除在任务选择之外。

**源证明** Runner 提供数据来源的密码学证据：
```
result = {
    "data": {...},
    "attestation": {
        "fetch_timestamp": 1702500000,
        "url": "https://...",
        "http_status": 200,
        "response_hash": "0x...",      # 原始响应的哈希
        "tls_cert_fingerprint": "0x...", # 证明连接到真实服务器
        "response_headers": {
            "etag": "...",
            "cache-control": "...",
            "last-modified": "..."
        }
    }
}
```

证明启用：
*   事后审计数据源。
*   数据更改时的争议解决。
*   证明 runner 连接到真实服务器（不是 MITM）。

对于启用 TEE 的任务，证明由 TEE 飞地签名，提供硬件支持的证明。

**密钥管理** 认证 API 访问需要凭据处理。Cowboy 为安全的凭据存储提供专用密钥管理器系统 Actor（`0x08`）：

**架构：**
```
Actor Storage (encrypted) <- Actor writes secrets
↓
Secrets Manager (0x08)
↓
TEE Runner (decrypts in enclave)
↓
External API
```

存储密钥：
```
from cowboy_sdk import secrets

# Actor 存储 API 密钥（加密到授权的 runner）
secrets.store(
    key="broker_api_key",
    value="sk-...",
    access_policy={
        "runners": ["tee_required"],    # 仅 TEE runner
        "entitlements": ["region_us"],    # 仅基于美国的 runner
        "job_types": ["http"]            # 仅用于 HTTP 任务
    }
)
```

在任务中使用密钥：
```
job_spec = {
    "type": "http",
    "url": "https://api.broker.com/portfolio",
    "auth": {
        "type": "bearer",
        "secret_ref": "broker_api_key"  # 对存储密钥的引用
    },
    "verification": {
        "mode": "economic_bond",
        "tee_required": true
    }
}
```

工作原理：
1.  Actor 将密钥加密到密钥管理器的公钥。
2.  密钥存储在链上（加密），带有访问策略。
3.  当任务引用密钥时，协议验证 runner 满足访问策略。
4.  Runner 的 TEE 从密钥管理器请求密钥。
5.  密钥管理器验证 TEE 证明，将密钥加密到飞地释放。
6.  密钥仅在 TEE 内解密，永远不会暴露给 runner 操作员。

安全属性：
*   密钥永远不会以明文形式存储在链上。
*   Runner 操作员无法访问密钥（TEE 隔离）。
*   访问策略由协议强制执行。
*   支持密钥轮换（Actor 可以更新值）。
*   维护密钥访问的审计日志。

**限制：**
*   需要支持 TEE 的 runner（限制 runner 池）。
*   Actor 必须信任 TEE 实现。
*   密钥管理器是系统 Actor（由治理控制）。

**HTTP 任务的验证模式** HTTP 任务支持与 LLM 任务相同的验证模式，但针对外部数据进行了调整：

| 模式 | Runner | 快照 | 验证 |
| :--- | :--- | :--- | :--- |
| none | 1 | N/A | 仅未交付 |
| economic_bond | 1 | N/A | 模式 + 新鲜度 |
| majority | N-of-M | majority | 提取字段匹配 |
| median | N-of-M | median | 数值容差 |
| structured_match | N-of-M | first_valid | 验证器函数 |
| deterministic | N-of-M | Exact | 字节相等（仅静态源） |

**示例：价格源预言机**

```
job_spec = {
    "type": "http",
    "url": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
    "freshness": {
        "max_age_seconds": 30,
        "reference": "block"
    },
    "extraction": {
        "method": "jsonpath",
        "selectors": {
            "price": "$.bitcoin.usd"
        }
    },
    "snapshot": {
        "mode": "median",
        "outlier_threshold": 0.01
    },
    "verification": {
        "mode": "median",
        "runners": 5,
        "threshold": 3
    }
}
```

五个 runner 获取价格。中位数值被接受为规范。任何报告价格距离中位数 >1% 的 runner 被标记（潜在操纵或过时缓存）。

## 随机性

每个区块使用阈值 BLS VRF 从前一个法定人数证书派生随机信标。Actor 可以访问此功能以进行公平委员会采样、抽奖和游戏。

## 共识和网络

Cowboy 使用**Simplex 共识**，这是一种 BFT 协议，通过强制提议者轮换优化了简单性、快速最终性和 MEV 抵抗。

### 协议概述

**Simplex** 是一种流线型 BFT 协议，在保持简单设计和可证明活跃性的同时实现最优延迟。与具有稳定领导者的协议（PBFT）不同，Simplex 每个区块轮换提议者——这是减少 MEV 提取机会的故意选择。

**共识流程：**
1.  **提议：** 当前提议者（由 VRF 选择）广播区块提议。
2.  **投票：** 验证者对提议投票；投票被缓冲直到达到法定人数。
3.  **认证：** 达到 `2f+1` 票后，形成法定人数证书（QC）。
4.  **最终确定：** 来自下一轮的具有 QC 的区块是最终且不可逆的。

在**部分同步**下，协议保证安全性（没有冲突的区块被最终确定）始终成立，并在网络延迟有界时保证活跃性（进展）。

**关键参数：**
*   ***区块时间：** 目标约 1 秒。
*   ***最终性：** 正常条件下约 2 秒。
*   ***容错：** 容忍最多 `f < n/3` 个拜占庭验证者。

**缓冲签名验证：**
为了优化性能，Cowboy 缓冲传入的验证者签名，并在达到法定人数（`2f+1`）时执行批量验证，而不是单独验证每个签名。与急切验证相比，这减少了约 65% 的 CPU 开销。如果批量验证失败，二进制搜索识别违规签名，并阻止该对等节点。

### 验证者集合

验证者集合是**开放且无需许可的**。任何满足最小质押阈值的账户都可以注册为验证者：

**要求：**
*   质押 ≥ 最小 validator_stake（可治理调整）。
*   仅自质押（v1 中无委托）。
*   必须运行合规的验证者软件。
*   必须保持网络连接。

验证者数量**无固定上限**。BLS 签名聚合确保共识效率，无论集合大小如何。经济因素（奖励稀释、最小质押）提供自然边界。

**验证者生命周期：**
1.  **注册：** 质押 CBY，提交验证者公钥（BLS12-381）。
2.  **激活：** 验证者在下一个 epoch 边界变为活动状态。
3.  **运营：** 提议区块、投票、赚取奖励。
4.  **退出：** 发出解绑信号；质押在解绑期间被锁定。
5.  **提取：** 解绑期结束后，质押被返还。

**Epoch 和轮换**

**Epoch 结构：**
*   **Epoch 持续时间：** 3600 个区块（约 1 小时）。
*   **验证者集合更新：** 仅在 epoch 边界。
*   **提议者选择：** 每区块 VRF，按质押加权。

在每个 epoch 边界：
1.  在 epoch 期间注册的新验证者被激活。
2.  发出退出信号的验证者从活动集合中移除。
3.  应用削减惩罚。
4.  Epoch 随机种子从前一个 epoch 的最终 QC 派生。

**提议者轮换：** 每个区块的提议者通过 VRF 选择：
`proposer = VRF_select(epoch_seed, block_height, active_validators, stakes)`
选择概率与质押成正比，确保较大的质押者更频繁地提议（并赚取更多提示）。

**质押和奖励**

**质押：**
*   最小质押：可治理调整（例如，创世时 50,000 CBY）。
*   每个验证者无最大质押。
*   仅自绑定：委托推迟到 v2。

**奖励：** 区块奖励（来自通胀）按质押比例分配：
`validator_reward = (validator_stake / total_staked) × block_inflation_reward`
提议者还为其提议的区块接收交易提示。

**解绑：**
*   解绑期：**7 天**。
*   解绑期间，质押不计入共识。
*   解绑期间质押仍可被削减（对于后来发现的违规行为）。
*   解绑完成后，质押可提取。

**削减**

Cowboy 使用**保守的削减模型**，优先考虑验证者参与而非惩罚性处罚。大多数违规行为导致监禁（临时移除）而非质押销毁：

| 违规行为 | 检测 | 惩罚 |
| :--- | :--- | :--- |
| **双重签名** | 在同一高度为不同区块的两个有效签名 | 监禁 + 削减 1% 质押 |
| **提议者等值** | 同一槽的两个不同有效提议 | 监禁 + 削减 1% 质押 |
| **长时间停机** | 在 1000 个区块中缺失 >50% 的投票 | 监禁（无削减） |
| **无效区块提议** | 区块未能通过共识验证 | 监禁（无削减） |

**监禁：**
*   被监禁的验证者立即从活动集合中移除。
*   必须在监禁期（24 小时）后才能解除监禁。
*   解除监禁需要验证者的显式交易。
*   重复违规会指数级增加监禁持续时间。

**保守削减的理由：**
*   鼓励验证者参与（风险较低）。
*   防止因错误/配置错误导致的意外削减。
*   监禁仍然从共识中移除不良行为者。
*   严重违规（双重签名）仍然产生经济惩罚。

**视图更改和领导者故障**

如果当前提议者未能产生区块（崩溃、网络分区），协议执行**视图更改：**
1.  **超时：** 等待提议的验证者在 `block_time × 2` 后触发超时。
2.  **新视图：** 验证者广播他们看到的最高 QC。
3.  **领导者选举：** 下一个领导者由 VRF 确定（跳过失败的提议者）。
4.  **恢复：** 新领导者提议扩展最高 QC 的区块。

视图更改增加延迟但保持安全性。协议确保即使在领导者故障期间也不能最终确定冲突的区块。

**最终性和重组**

**最终性保证：** 一旦区块具有提交证书（CC），它就是**最终且不可逆的**。没有诚实的验证者会为冲突的区块投票。

**预最终性窗口：** 没有 CC 的区块理论上可能被回退（重组）。实际上，使用 1 秒区块和 2 轮提交，预最终性窗口约为 2 秒。

**Runner 对重组的处理：**
*   Runner 相对于链状态是**无状态的**。
*   任务引用区块高度，而不是区块哈希。
*   如果在最终性之前发生重组，受影响的任务可能需要重新提交。
*   Actor 应该设计处理器为**幂等的**（安全重放）。
*   对于关键任务，Actor 可以在考虑结果确认之前等待最终性。

**网络层**

**传输：** QUIC over TLS 1.3（必需）。

**Gossip 协议：**
*   交易：向所有对等节点洪泛。
*   区块：提议者广播；验证者中继。
*   投票：直接发送给提议者（减少 gossip 开销）。

**对等节点发现：** 基于 DHT，带有引导节点。

**消息认证：** 所有共识消息使用验证者的 BLS 密钥签名。

**专用通道**

区块空间被划分为具有保留容量的**专用通道**，确保自主 Actor 操作（定时器、runner 结果）不会被用户交易峰值排挤：

| 通道 | 保留容量 | 优先级 | 内容 |
| :--- | :--- | :--- | :--- |
| **系统** | 5% | 最高 | 验证者更新、治理、削减 |
| **定时器** | 20% | 高 | 调度的定时器执行 |
| **Runner** | 25% | 高 | Runner 任务结果和证明 |
| **用户** | 50% | 正常 | 用户发起的交易 |

**通道语义：**
*   每个通道都有自己的基础费用，根据通道利用率独立调整。
*   高优先级通道中未使用的容量向下级联到低优先级通道。
*   交易在提交时按类型标记；提议者不能重新分配通道。
*   如果通道已满，多余的交易等待下一个区块（不溢出到其他通道）。

**示例：** 具有基于定时器的调度重新平衡的 DeFi Actor 即使在用户交易激增期间也会可靠执行，因为定时器通道有 20% 的保留容量，用户交易无法消耗。

**MEV 防护**

Cowboy 采用多层方法来缓解 MEV，避免加密内存池的延迟成本，同时仍提供强有力的保证：

1.  **强制提议者轮换**
    Simplex 共识通过 VRF 每个区块轮换提议者。与具有稳定领导者的协议（一个验证者可能提议 10+ 个连续区块）不同，没有单个提议者观察跨多个区块的交易流。这从根本上限制了：
    *   跨区块 MEV 策略。
    *   区块构建者串通模式。
    *   提议者-搜索者关系。
2.  **基于 VRF 的交易排序**
    在每个区块内，提议者使用 VRF 确定性地排序交易：
    `order_key = VRF(proposer_key, tx_hash, block_height)`
    提议者在区块头中承诺此排序。验证者验证排序是否正确——任何偏差都会导致区块拒绝。这防止：
    *   提议者的战略交易放置。
    *   在有利位置插入提议者自己的交易。
    *   三明治攻击构建。
3.  **快速最终性窗口**
    使用约 1 秒区块和约 2 秒最终性：
    *   **观察窗口：** 攻击者从交易广播到区块包含的时间少于 1 秒。
    *   **重组风险：** 最终性后为零；需要重组的攻击是不可能的。
    *   **前置运行：** 考虑到严格的时间约束，极其困难。
4.  **通道隔离**
    专用通道防止一类 MEV 攻击，其中对手向内存池发送垃圾邮件以延迟受害者交易：
    *   定时器触发的交易无论用户通道拥塞如何都会执行。
    *   Runner 结果即使在活动峰值期间也能可靠发布。
    *   对手无法按通道类型选择性延迟交易。

**为什么不使用加密内存池**
提交-揭示方案（例如，阈值加密）为解密增加一个区块的延迟。考虑到 Cowboy 已经最小的 MEV 表面：
*   VRF 排序消除了提议者的自由裁量权。
*   轮换防止多区块观察。
*   快速最终性关闭了时间窗口。
*   通道分离防止拥塞攻击。
加密的边际收益不能证明延迟和复杂性成本。如果经验 MEV 数据证明有必要，可以重新审视此决定。

## 数据可用性、状态租金和存储

本节指定 Cowboy 如何管理链上数据、状态增长以及保持网络可持续的经济机制。

### 内联数据与 Blob

小输出（≤ 64 KiB）内联存储并使用 cells 支付。较大的工件必须存储为内容寻址的 blob（例如，IPFS），并在链上引用 multihash。

| 数据大小 | 存储方法 | 支付 |
| :--- | :--- | :--- |
| ≤ 64 KiB | 内联（链上） | Cells（一次性）+ 租金 |
| > 64 KiB | 外部 blob（IPFS、Arweave） | 仅哈希的 Cells |

### 状态租金模型

所有持久的 Actor 存储都受状态租金约束——占用全局状态 trie 空间的持续费用。租金创造经济压力以高效使用存储，并确保不活跃或废弃的 Actor 不会无限期地膨胀网络。

**基于市场的租金定价**

租金费率根据总网络状态大小动态调整，类似于 EIP-1559 费用调整：

`rent_rate_(i+1) = rent_rate_i × (1 + clamp((S - T) / (T × alpha), -delta, +delta))`

其中：
*   S = 当前总状态大小（所有 Actor 的字节数）。
*   T = 目标状态大小（可治理调整，例如 100 GB）。
*   alpha = 8，delta = 0.125（与 cycle/cell 基础费用相同）。

当状态增长超过目标时，租金上升，阻止新存储并激励清理。当状态缩小时，租金下降，使存储更便宜。

**每个 Actor 的租金计算：**

`epoch_rent = actor_storage_bytes × rent_rate_per_byte_per_epoch`

**租金支付选项** Actor 可以通过两种方式支付租金：

1.  **自动扣除（默认）**
    每个 epoch，租金从 Actor 的 CBY 余额中自动扣除：
    ```
    在 epoch 边界：
      if actor.balance >= epoch_rent:
        actor.balance -= epoch_rent
      else:
        enter_grace_period(actor)
    ```
2.  **预付费租金**
    Actor 可以提前存入租金以预测成本：
    ```
    from cowboy_sdk import rent

    # 预付 1000 个 epoch 的租金
    rent.prepay(epochs=1000)

    # 检查租金状态
    status = rent.status() # {paid_through_epoch: 15000, balance_epochs: 847}
    ```
    预付费租金不可退还，但提供成本确定性。
3.  **赞助租金**
    任何账户都可以代表任何 Actor 支付租金：
    `rent.sponsor(actor_address="0x...", epochs=100)`
    这为公共产品或关键基础设施启用"保持活动"服务。

**最小余额储备** 为防止 Actor 意外花费所有 CBY 并进入宽限期，每个 Actor 都有一个**最小余额储备**：

`minimum_reserve = estimated_annual_rent × reserve_multiplier`

其中 `reserve_multiplier` 是可治理调整的（默认值：0.1，即约 5 周的租金）。

储备：
*   不能用于交易或任务。
*   如果主余额不足，自动用于租金。
*   在宽限期开始之前提供缓冲。
*   仅在关闭 Actor 时可以提取。

**宽限期和驱逐**

当 Actor 无法支付租金（余额和储备耗尽，没有预付费 epoch 剩余）时，他们进入宽限期：

**时间线：**
```
Epoch N: 租金到期，资金不足 -> 宽限期开始
Epoch N+168: 宽限期结束（7 天）-> 警告期开始
Epoch N+240: 警告期结束（再 3 天）-> 符合驱逐条件
Epoch N+241: 存储被驱逐
```
从第一次错过支付到驱逐的总时间：10 天。

宽限期期间：
*   Actor 保持完全功能。
*   仍可以接收消息、执行处理器、修改存储。
*   Actor 被标记为"租金逾期"（链上可见）。
*   累积追赶费用（错过租金的 10%）。

警告期期间：
*   与宽限期相同。
*   Actor 被标记为"即将驱逐"。
*   发出事件以提醒依赖的 Actor。

**追赶费用：**
退出宽限期：`payment_required = missed_rent × 1.1`
这 10% 的惩罚阻止故意进入宽限期以推迟支付。

**驱逐机制**

发生驱逐时：

**被驱逐的内容：**
*   Actor 的存储（所有键值数据）。
*   与 Actor 关联的活动定时器。

**保留的内容：**
*   Actor 的代码（不可变，单独存储）。
*   Actor 的地址（保留，不能重用）。
*   Actor 的余额（如果有剩余）。
*   存储根哈希（用于潜在恢复）。

**驱逐过程：**
1.  存储根哈希记录在链上。
2.  所有存储键标记为删除。
3.  存储在下个 epoch 从活动状态 trie 中修剪。
4.  Actor 进入"休眠"状态。

**休眠 Actor：**
*   无法执行处理器（没有存储可读/写）。
*   仍可以接收 CBY 转账。
*   如果提供存储数据，可以恢复。

**存储恢复**

如果原始数据可用，可以恢复被驱逐的存储：

**要求：**
1.  原始存储数据（例如，来自备份、归档节点或第三方）。
2.  数据必须哈希到记录的存储根。
3.  支付所有欠租加上追赶费用。

**恢复过程：**
```
from cowboy_sdk import storage

# 任何拥有数据的人都可以恢复 Actor
storage.restore(
    actor_address="0x...",
    storage_data=original_data,  # 必须匹配记录的根哈希
    pay_from=sponsor_address    # 可以是 Actor 本身或赞助者
)
```

恢复成本：`restoration_cost = back_rent + (back_rent × 0.1) + current_epoch_rent`

此机制允许：
*   Actor 备份自己的存储并自行恢复。
*   第三方恢复重要的公共基础设施。
*   从意外租金失效中恢复。

*注意：如果没有人拥有原始数据，存储将永久丢失。Actor 应维护关键数据的链下备份。*

**账本增长和修剪**

**区块存储** 区块是仅追加的，永远不会从规范链中修剪：

*每年区块数据（估计）：*
~1 KB/区块 × 86,400 区块/天 × 365 天 ≈ 31 GB/年
这是全节点的最小存储要求。

**状态存储** 状态 trie 保存当前账户余额、Actor 代码和 Actor 存储：
*   全节点仅保留当前状态 trie。
*   历史状态（旧 trie 版本）可以在最终性后修剪。
*   状态大小受租金经济学限制——高租金阻止膨胀。

**归档节点** 归档节点为每个区块保留完整历史状态：
*   历史查询、索引、区块浏览器需要。
*   不需要参与共识。
*   可以重建任何历史状态。
*   为被驱逐的 Actor 启用存储恢复。

**节点类型**

| 节点类型 | 区块 | 当前状态 | 历史状态 | 存储估计（第 1 年） |
| :--- | :--- | :--- | :--- | :--- |
| 轻客户端 | 仅头 | Merkle 证明 | 无 | < 1 GB |
| 全节点 | 全部 | 是 | 已修剪 | ~50-100 GB |
| 归档节点 | 全部 | 是 | 全部 | ~500 GB+ |

**轻客户端**

轻客户端无需存储完整状态即可实现无需信任的验证：

**能力：**
*   验证区块头形成有效链。
*   通过 Merkle 证明验证交易包含。
*   通过针对状态根的 Merkle 证明验证状态查询。
*   提交交易。

**限制：**
*   没有全节点无法执行任意查询。
*   依赖全节点生成证明。

**用例：** 移动钱包、嵌入式设备、浏览器扩展。

**存储配额和保证金**

每个 Actor 都有一个基础存储配额，并可以使用保证金扩展：

| 配额层级 | 存储限制 | 要求 |
| :--- | :--- | :--- |
| 基础 | 1 MiB | 所有 Actor 的默认值 |
| 扩展 | 最多 8 MiB | 需要存储保证金 |

**存储保证金：**
`bond_required = (requested_quota - 1 MiB) × bond_rate_per_byte`

保证金：
*   在使用配额期间被锁定。
*   在配额减少时返还。
*   如果 Actor 被驱逐则没收（激励租金支付）。
*   对整个分配的配额（不仅仅是使用的存储）收取租金。

## 货币政策和费用

原生资产是**CBY**。Cowboy 以 10 亿 CBY 的创世供应量和递减的发行计划启动，以奖励验证者。

### 通胀计划

**发行率**（随时间递减）：
*   **第 1-2 年：** 年通胀 8%。
*   **第 3-4 年：** 年通胀 5%。
*   **第 5-6 年：** 年通胀 3%。
*   **第 7-10 年：** 年通胀 2%。
*   **第 10 年+：** 1% 终端通胀。

### 费用分配

*   **基础费用（Cycles 和 Cells）：** 100% 销毁。
*   **提示：** 支付给区块提议者。
*   **链下任务支付：** 流向 Runner，一小部分流向协议金库。

因为基础费用被销毁，如果链被大量使用，净供应量可能变得通缩。

### 治理和升级

早期治理由**基金会多重签名**执行，具有标准时间锁，逐步过渡到代币加权的链上治理。升级作为**热代码升级**发布，由治理协调。

### 应用程序

Cowboy 设计用于现实世界的自主工作负载。
*   **AI 智能体：** 调用 LLM 进行规划或检索的 Actor，具有可验证的转录和有限成本。例如，交易智能体可以抓取国会股票披露，使用 LLM 解析交易，并自主执行复制交易。
*   **DeFi 自动化：** 监控 ETH/BTC 池并根据与 7 天移动平均值的价格偏差自动重新平衡的智能体，所有这些都无需外部 keeper。
*   **游戏：** 具有 VRF 随机性的每 tick 逻辑；blob 资产存储在链下但在链上提交。
*   **预言机：** HTTP 委员会从允许列表域获取数据，具有提交-揭示和争议。

### 为什么是主权 L1

一个自然的问题出现了：为什么将 Cowboy 构建为主权 Layer-1 而不是以太坊 Layer-2（rollup），后者将继承以太坊的安全性和流动性？

**L2 约束**

以太坊 L2 主要有两种类型，都不符合 Cowboy 的要求：

**乐观 Rollup：**
*   欺诈证明窗口的 7 天提取延迟。
*   需要快速流动性访问的智能体将受到严重限制。
*   排序器中心化创建 MEV 和审查风险。

**ZK Rollup：**
*   要求执行在零知识电路中可证明。
*   Python 不适合电路；PVM 需要完全重新实现。
*   复杂 Actor 逻辑的证明成本将令人望而却步。
*   当前的 ZK-EVM 项目仅针对 EVM 就花费了数年时间和数十亿美元的资金。

两种方法都继承 EVM 执行约束或需要在其内构建，迫使 Cowboy 要么放弃 Python，要么构建完全独立的证明系统。

**为什么 L1 使 Cowboy 的设计成为可能**

| 能力 | L1（主权） | L2（Rollup） |
| :--- | :--- | :--- |
| **自定义 VM** | 原生 PVM with Python | 受限于 EVM 或自定义 ZK 电路 |
| **区块时间** | 完全控制（1 秒目标） | 受 L1 最终性限制以进行结算 |
| **共识** | 具有专用通道、VRF 排序的 Simplex | 继承排序器模型或以太坊约束 |
| **原生定时器** | 协议级别，gas 高效 | 需要外部 keeper 网络 |
| **Runner 集成** | 具有验证模式的深度协议集成 | 每个能力的单独预言机基础设施 |
| **升级路径** | 主权治理 | 取决于 rollup 框架和 L1 升级 |

**权衡**

主权性带来成本：
*   **桥接风险：** 跨链资产转移需要超出以太坊安全性的信任假设。
*   **流动性碎片化：** Cowboy 上的资产不能与以太坊 DeFi 原生组合。
*   **验证者引导：** 必须吸引足够的质押以获得经济安全性。

Cowboy 接受这些权衡，因为替代方案——将自主 Python 智能体强制进入 EVM 约束或等待 ZK-Python 基础设施多年——将损害核心价值主张。桥接设计（§16）通过验证者委员会、速率限制和未来的乐观回退路径来缓解跨链风险。

## 以太坊互操作性

互操作性是基础设计目标。相同的 secp256k1 密钥可以控制 Cowboy 账户和 EVM 地址，让智能体持有 ETH 和 ERC-20，桥接资产，并在由 entitlements 强制执行的严格策略保护下签署 EIP-1559 交易。规范桥接将携带资金和调用数据，而 Cowboy Actor 可以订阅以太坊事件以触发链上工作流。

## 状态转换函数

Cowboy 的核心是一个确定性的状态转换函数，它接受一个区块和输入状态并返回下一个状态。

设 σ 为全局状态，B 为具有交易 T_i、基础费用（bf_c, bf_b）和随机性 R 的区块。

1.  **头/提议者：** 由 Simplex 确定；R 从父 QC 派生。
2.  **执行交易（有序）：**
    *   验证签名、nonce 和余额。
    *   使用用户限制初始化计量器；收取内在 cells。
    *   分派到目标。Actor 可以发送消息（扇出 ≤ 1,024）、调度定时器并提交 blob；重入深度 ≤ 32。
    *   强制执行内存（10 MiB）、邮箱（≤ 1,000,000）和存储配额。
    *   扣除费用：`cycles_used*(bf_c+tip_c) + cells_used*(bf_b+tip_b)`；销毁基础费用。
3.  **传递定时器：** 在 height(B) 注入到期的定时器。
4.  **解析任务：** 处理承诺、揭示、挑战和支付。
5.  **调整基础费用：** 通过 EIP-1559 反馈更新（bf_c, bf_b）。
6.  **铸造奖励：** 将每区块通胀分配给验证者。

单个参考实现定义了 cycles 的规范计量表。

**术语**

*   **Actor：** 具有持久键/值状态和邮箱的 Python 程序。
*   **消息：** 传递给 Actor 处理器的数据报。
*   **Cycle：** 计量的链上计算单位。
*   **Cell：** 计量的字节单位（1 cell = 1 字节）。
*   **Runner：** 执行任务并返回证明结果的链下工作者。
*   **Entitlement：** 管理 Actor 或 Runner 能力的权限。
*   **Model：** 描述链下计算模型的摘要和元数据的注册表条目。

**规范性约定**

本文档使用 RFC 2119 中定义的 MUST/SHOULD/MAY。标记为**可治理调整**的参数可以通过链上治理更改（见 §11）。

## 1. 账户、地址和密钥

### 1.1 签名。
外部账户必须使用**secp256k1**（ECDSA），具有链 ID 分离。

### 1.2 Actor 地址派生（CREATE2 风格）。
新 Actor 地址必须是：`addr = last_20_bytes(keccak256(creator || salt || code_hash))`，其中 `code_hash = keccak256(python_source_bytes)`。

### 1.3 系统地址空间。
范围 `0x0000...0100` 保留用于**系统 Actor 和预编译合约**（见 §10）。

## 2. 交易类型和编码

### 2.1 类型化交易（EIP-1559 风格，双计量器）。
交易必须包括：`chain_id, nonce, to, value, cycles_limit, cells_limit, max_fee_per_cycle, max_fee_per_cell, tip_per_cycle, tip_per_cell, access_list?, payload, signature`。

### 2.2 有效性检查。
如果满足以下条件，节点必须拒绝交易：（a）限制超过最大值（§13.1），（b）余额不足，（c）签名无效，（d）访问列表无效，或（e）有效载荷解码失败。

### 2.3 费用核算。
设 bc, bb 为 cycles/cells 的区块基础费用。费用为：`fee = cycles_used * (bc + min(tip_per_cycle, max_fee_per_cycle - bc)) + cells_used * (bb + min(tip_per_cell, max_fee_per_cell - bb))`。未使用的限制必须按用户的 `max_fee * rates` 退还。

### 2.4 EBNF（信息性）。
```
Tx = Header Body Sig
Header = chain_id nonce to value cycles_limit cells_limit max_fee_per_cycle max_fee_per_cell tip_per_cycle tip_per_cell [access_list]
Body = payload
Sig = secp256k1_signature_recoverable
```

## 3. 执行模型（Actor）

### 3.1 运行时和确定性。
*   官方 SDK：**Python SDK**。运行时必须强制执行确定性：
    *   **允许的操作**：标准 Python 操作，文件 I/O 限制为 /tmp，通过 async/await 进行协作 yield。
    *   **禁止**：`sys.exit()`、random 模块（链 VRF 除外）、`time.time()`/`datetime.now()`、`os.environ` 访问、socket/网络操作、subprocess 调用、/tmp 外的路径遍历。
    *   **浮点**：允许；Cowboy 提供确定性数学库。
    *   **临时空间**：`/tmp` 必须是每次调用，上限为**256 KiB**（计入 cells_used），处理器后擦除。

### 3.2 内存和存储。
*   **每次调用内存限制：** **10 MiB** 堆内存。
*   **每个 Actor 持久存储配额：** **1 MiB**（可治理调整），具有**状态租金**（§4.4）。
*   **配额扩展：** Actor 可以发布**存储保证金**，最多**8 MiB** 总计；租金适用于完全分配的配额。

### 3.3 消息传递、重入、定时器。
*   **传递：** **恰好一次**。每个消息 ID 必须是 `keccak256(sender|nonce|msg_hash)` 并记录在每个 Actor 的去重集合中。
*   **邮箱：** 容量**1,000,000 项**；超出限制的排队必须回退。
*   **每交易扇出：** 交易（包括所有嵌套发送）不得排队超过**1,024**条消息。
*   **重入：** 允许；**递归/await 深度上限 = 32**。
*   **定时器（链原生）：** 提供以下定时器原语：
    *   `timer_id = set_timer(height, handler, data)` -- 为指定的区块高度调度一次性定时器。返回唯一的 timer_id。
    *   `timer_id = set_interval(every_n_blocks, handler, data)` -- 调度重复定时器。返回唯一的 timer_id。
    *   `cancel_timer(timer_id)` -- 按其 ID 取消待处理的定时器。如果成功，返回存款。
    *   定时器传递是**尽力而为**；执行取决于 GBA 拍卖（见定时器速率限制）。

### 3.4 随机性。
*   验证者必须为每个区块生成阈值 BLS VRF：`R_n = VRF_sk_epoch(QC_n-1))`。Actor 可以调用返回 `HKDF(R_n, label)` 的 API。

### 3.5 部分成本表（信息性）。
*   精确计量是共识关键的；实现者必须匹配参考成本表。

| 原语 | Cycles |
| :--- | :--- |
| Python 算术运算 | 1 |
| Python 函数调用 | 10 |
| 字典 get/set | 3 |
| 列表 append/access | 2 |
| 字符串操作（每字符） | 1 |
| host: 邮箱发送（每条消息，不包括有效载荷） | 80 |
| host: 定时器设置/取消 | 200 |
| host: blob 提交（每 KiB） | 40 |

*注意：Cells 计量字节（有效载荷、返回数据、内联 blob ≤ 64 KiB、/tmp）。*

## 4. 费用、计量和基础费用调整

### 4.1 计量器。
*   **Cycles：** Python 操作 + 主机调用的确定性步骤计数。
*   **Cells：** 调用数据、返回数据、内联 blob（≤ 64 KiB）和 /tmp 使用的字节。

### 4.2 双 EIP-1559 基础费用。
设 U_c, T_c 为 cycles 使用/目标；U_b, T_b 为 cells 使用/目标。弹性 E=2（硬上限 E\*T_\*），调整使用：
`basefee_x_i+1 = max(1, basefee_x_i) * (1 + clamp((U_x - T_x)/(T_x*alpha), -delta, +delta)))`
其中 x ∈ {cycle, cell}，alpha = 8，delta = 0.125。节点必须销毁 100% 的基础费用；提示支付给提议者/验证者。

### 4.3 目标（创世默认值）。
*   T_c（cycles 目标）：10,000,000 cycles（上限 20,000,000）。
*   T_b（cells 目标）：500,000 字节（上限 1,000,000）。

### 4.4 状态租金。
持久存储每个字节每个 epoch 产生租金，这是可治理调整的。如果 90 个 epoch 未支付，密钥可能在 30 个 epoch 宽限期后被修剪。

## 5. 链下计算

### 5.1 模型注册表。
`model_id = keccak256(weights|arch|tokenizer|license)` 必须唯一标识模型修订。发布是无需许可的，需要可退还的 1,000 CBY 存款。治理可以标记/禁止模型。

### 5.2 Runner 质押。
Runner 必须在 Runner 注册表中质押 `max(10,000 CBY, 1.5 × declared_max_job_value)`。

### 5.3 任务生命周期。
1.  **发布：** Actor 发布带有托管价格的任务。
2.  **分配：** 对于 HTTP 域，采样 M=5 的委员会；N=3 匹配揭示最终确定。LLM 任务可以使用委员会或单 runner。
3.  **提交：** Runner 返回 `commit = keccak256(output|salt)`。
4.  **揭示：** Runner 揭示 `{output, salt, proof?}`。
5.  **挑战：** 打开 15 分钟的挑战窗口，需要 100 CBY 保证金。
6.  **解决：** 证明的故障 = 活动质押的 30% 削减（70% 给挑战者，30% 销毁）。
7.  **支付：** 最终确定时，99% 的任务支付给 runner(s)，1% 给金库。

### 5.4 确定性和边界。
任务必须固定 `toolchain_digest` 和 `seed`。链上返回数据必须 ≤ 64 KiB。

### 5.5 TEE 选项。
任务可以设置 `tee_required=true`。有效证明必须匹配接受的策略。

## 6. 共识、随机性和网络

### 6.1 共识。
**Simplex BFT PoS；** 约 1 秒目标区块时间；**提交时最终性**（约 2 秒）。提议者使用 VRF 信标每个区块轮换（强制轮换以抵抗 MEV）。投票通过**BLS12-381**聚合，具有缓冲批量验证。

### 6.2 P2P 传输。
实现必须支持 QUIC over TLS 1.3。

### 6.3 专用通道。
区块空间被划分为具有保留容量的**专用通道**：

| 通道 | 保留容量 | 优先级 | 内容 |
| :--- | :--- | :--- | :--- |
| **系统** | 5% | 最高 | 验证者更新、治理、削减 |
| **定时器** | 20% | 高 | 调度的定时器执行 |
| **Runner** | 25% | 高 | Runner 任务结果和证明 |
| **用户** | 50% | 正常 | 用户发起的交易 |

通道保证：
*   定时器和 runner 通道防止用户交易垃圾邮件阻塞自主 Actor 执行。
*   高优先级通道中未使用的容量向下级联到低优先级通道。
*   每个通道都有独立的基础费用跟踪。

### 6.4 Gossip（内存池）。
具有**费用层级内 FIFO**的公共内存池。交易按通道类型标记。v1 中没有私有构建者或加密内存池——MEV 抵抗依赖于快速最终性和强制提议者轮换。

### 6.5 MEV 防护。
Cowboy 的 MEV 缓解策略结合了多种机制：

**强制提议者轮换：** Simplex 共识通过 VRF 每个区块轮换提议者。与稳定领导者协议不同，没有单个验证者可以观察跨多个区块的交易流，限制 MEV 提取窗口。

**基于 VRF 的交易排序：** 在每个区块内，交易按以下方式排序：`order_key = VRF(proposer_key, tx_hash, block_height)`。这种确定性但不可预测的排序防止提议者战略性地放置自己的交易。

**快速最终性：** 约 2 秒最终性（2 轮 Simplex）最小化以下窗口：
*   前置运行（有限的观察时间）。
*   三明治攻击（执行失败的高风险）。
*   时间强盗攻击（链永远不会在最终性后重组）。

**专用通道：** 为定时器和 runner 保留容量确保自主 Actor 无论用户内存池拥塞如何都能可靠执行。攻击者无法向用户通道发送垃圾邮件以延迟其他通道中的受害者交易。

**无加密内存池：** 提交-揭示方案增加延迟和复杂性。考虑到约 1 秒区块和约 2 秒最终性，观察窗口已经最小。VRF 排序 + 轮换 + 快速最终性的组合提供了足够的 MEV 抵抗，而无需加密的延迟成本。

## 7. 数据可用性和 Blob

### 7.1 内联上限。
内联 blob 上限是每个输出**64 KiB**。

### 7.2 外部 blob。
较大的数据必须**内容寻址**（例如，IPFS）。链上承诺必须是 multihash。

## 8. 经济学、通胀和费用

### 8.1 代码和供应。
CBY。创世供应**1,000,000,000 CBY**。

### 8.2 通胀。
使用递减的通胀计划来引导网络安全。
*   **第 1-2 年：** 年通胀 8%。
*   **第 3-4 年：** 年通胀 5%。
*   **第 5-6 年：** 年通胀 3%。
*   **第 7-10 年：** 年通胀 2%。
*   **第 10 年+：** 1% 终端通胀。

### 8.3 创世分配。
验证者**25%，** 金库**25%，** 生态系统**30%，** 投资者**20%**（标准归属）。

### 8.4 费用接收和分割。
基础费用：**100% 销毁**。提示：给提议者/验证者。链下任务支付：**99%** 给 runner，**1%** 给金库。

## 9. 系统 Actor 和预编译合约

*   ***0x01 消息传递：** 排队和扇出消息。
*   ***0x02 定时器：** 调度/取消定时器。
*   ***0x03 Oracle/Runner：** 管理链下任务。
*   ***0x04 Blob 存储：** 提交/检索 blob multihash。
*   ***0x05 签名工具：** secp/BLS/VRF 辅助函数。
*   ***0x06 EventListener：** 以太坊事件订阅（见 §16）。
*   ***0x07 TEE 验证器：** 根据可信测量验证 TEE 证明。
*   ***0x08 密钥管理器：** 用于 TEE runner 的安全凭据存储和访问控制。

## 10. 开发者体验（DX）

*   ***SDK：** 提供主要的 Python SDK（`cowboy-py`）。
*   ***本地开发：** 一套工具，包括单节点开发网（`cowboyd`）、runner 模拟器、水龙头和浏览器将可用。
*   ***最佳实践：** 通过 SDK 鼓励重入防护、能力范围处理器和幂等消息处理。

## 11. 治理和升级

*   ***模型：** 基金会**5-of-9 多重签名**在约 12 个月后逐步过渡到代币加权的链上治理。
*   ***时间锁：** 标准操作**7 天；** 紧急快速通道**6 小时。**
*   ***升级：** 由治理协调的**热代码升级**。

## 12. 安全考虑

### 12.1 DoS 限制（共识强制执行；可治理调整）。
*   `max_tx_size = 128 KiB`
*   `max_message_depth_per_tx = 32`
*   `per_actor_per_block_cycles = 1,000,000`（可突发）

### 12.2 Runner 安全性。
对等值或无效结果的削减。委员会缓解单 runner 故障。

### 12.3 重入。
允许但深度限制；标准库提供重入防护。

### 12.4 随机性偏差。
具有 epoch 密钥的阈值 BLS VRF；Actor 通过 HKDF 派生子随机性。

### 12.5 状态租金和驱逐。
防止状态膨胀；驱逐窗口保护活跃性。

## 13. 参数（创世默认值）

**执行：**
`memory_per_call = 10 MiB; storage_quota_per_actor = 1 MiB; reentrancy_depth = 32; fanout_per_tx = 1024.`

**费用：**
`T_c = 10,000,000 cycles; T_b = 500,000 bytes; alpha = 8; delta = 0.125.`

**共识：**
`minimum_validator_stake = governance-tunable; epoch = 3600 blocks (~1 h); block_time = 1 s; finality = ~2 s; unbonding_period = 7 days; jail_period = 24 h; double_sign_slash = 1%; consensus_protocol = Simplex BFT.`

**专用通道：**
`system_lane_capacity = 5%; timer_lane_capacity = 20%; runner_lane_capacity = 25%; user_lane_capacity = 50%.`

**链下：**
`committee M = 5; threshold N = 3; challenge_window = 15 min; challenge_bond = 100 CBY; runner_stake_floor = 10,000 CBY.`

**状态租金：**
`target_state_size = governance-tunable; grace_period = 168 epochs (7 days); warning_period = 72 epochs (3 days); catch_up_fee = 10%; reserve_multiplier = 0.1.`

**经济学：**
`supply = 1,000,000,000; inflation follows the schedule in §8.2; basefee_burn = 100%; job_fee_to_treasury = 1%.`

## 14. 与以太坊的差异

*   **执行：** Python Actor vs. EVM 合约。
*   **费用：** 双计量器（cycles/cells）vs. 单 gas 标量。
*   **定时器：** 原生定时器 vs. 外部 keeper。
*   **链下计算：** 原生可验证市场 vs. 外部预言机。
*   **状态：** 带驱逐的租金 vs. 无限存储。

## 15. Entitlements

声明性、可组合的权限系统管理 Actor 和 Runner 的能力。Entitlements 控制对网络、存储和执行参数等资源的访问，默认强制执行最小权限。系统在部署时、调度器中以及在 VM 系统调用门处强制执行。

### 15.1 目标
*   默认最小权限。
*   确定性强制执行。
*   声明性和可组合。
*   链上可审计。

### 15.2 对象和生命周期
*   **Actor Entitlements：** Actor 需要的权限。
*   **Runner Entitlements：** Runner 提供的能力。

### 15.3 规则
1.  必须：Actor 需要 entitlements；Runner 提供它们。
2.  必须：调度器仅在 `requires ⊆ provides` 时匹配。
3.  必须：如果缺少相应的 entitlement，系统调用失败。
4.  必须：子 Actor 仅继承标记为 `inheritable: true` 的 entitlements。

*（有关 entitlements 的完整列表，请参阅协议规范）。*

## 16. 以太坊互操作性

Cowboy 与以太坊的互操作性是主要设计目标，实现无缝资产转移和跨链通信。这是通过共享密码学原语、规范桥接和事件订阅机制的组合实现的。

### 16.1. 账户统一
*   Cowboy 外部账户（EOA）必须使用与以太坊相同的 `secp256k1` 椭圆曲线进行签名。这允许单个私钥控制两个网络上的账户，简化用户和智能体的密钥管理。
*   Actor 可以通过主机调用，针对给定的以太坊地址验证 EIP-712 签名的数据结构，使 Actor 能够验证来自以太坊用户的链下授权。

### 16.2. 规范桥接
部署在 Cowboy 和以太坊上的规范、最小信任桥接合约应促进资产和任意消息数据的转移。

**资产桥接：**
*   桥接必须支持在以太坊上锁定原生 ETH 和 ERC-20 代币，以在 Cowboy 上铸造相应的包装表示（wETH、wERC-20）。
*   相反，桥接必须支持在 Cowboy 上销毁包装资产以解锁以太坊上相应的原生资产。
*   桥接操作应由运行对方链轻客户端的验证者委员会保护，对恶意行为的链上安全保证金可削减。

**通用消息传递：**
*   桥接协议必须允许一条链上的交易触发对另一条链上指定接收者 Actor/合约的相应消息调用。
*   跨链消息的有效载荷必须包含在源链桥接合约的事件日志中，目标链的桥接验证者可以验证。

### 16.3. 事件订阅（以太坊到 Cowboy）
*   Cowboy Actor 可以订阅以太坊区块链上特定合约发出的事件日志。
*   Cowboy 上的系统 Actor `0x06 EventListener` 应管理这些订阅。此 Actor 依赖桥接验证者集合作为去中心化预言机，监控以太坊链以查找指定事件。
*   当订阅的事件被确认（即，在以太坊上最终确定）时，EventListener Actor 必须将消息排队到订阅的 Cowboy Actor，将事件的主题和数据作为消息有效载荷传递。
*   此订阅服务的成本应由 Actor 以 CBY 支付，涵盖预言机验证者在以太坊上产生的 gas 费用。

### 16.4. 策略和安全性
*   所有可供 Actor 使用的互操作性功能，如 `bridge_asset` 或 `subscribe_event`，必须由 Entitlements 系统（§15）管理。
*   Actor 的部署清单必须声明允许其交互的特定以太坊合约以及允许其桥接的资产类型，强制执行最小权限原则。

**规范结束。**

