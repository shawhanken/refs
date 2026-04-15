# Cowboy：技术白皮书

| 字段 | 值 |
|-------|----------|
| 状态 | 内部审查草案 |
| 类型 | 标准跟踪 |
| 分类 | 核心 |
| 作者 | Cowboy 基金会 |
| 创建日期 | 2025‑09‑17 |
| 更新日期 | 2026‑02‑15 |
| 许可证 | CC0‑1.0 |

注：本文档提供 Cowboy 的完整技术规范。有关架构设计原理和设计决策，请参阅《设计决策概述》。

## 1.1 摘要

Cowboy 是一条通用第一层区块链，将基于 Python 的 Actor 模型执行环境与权益证明共识以及可验证链下计算市场相结合。Cowboy 上的智能合约即 Actor：具备私有状态、消息邮箱和链原生定时器（用于自主调度）的 Python 程序。对于 LLM 推理或 Web 请求等重计算任务，Cowboy 集成了去中心化的 Runner 网络，在可选信任模型（N-of-M 共识、TEE 以及 V2 版本的 ZK 证明）下执行作业并证明结果。

Cowboy 引入了双计量 Gas 模型，将计算定价（Cycle）和数据定价（Cell）分离为独立的 EIP‑1559 风格费用市场。安全性由 Simplex BFT 共识与权益证明提供，支持快速最终性和强制出块者轮换。

本文档规定了 Cowboy 的完整技术架构、状态转换函数、经济机制、共识协议及所有实现参数。

## 1.2 引言

Cowboy 旨在通过提供针对异步、基于 Python 的应用优化的原生区块链执行环境来赋能自主代理。本文档为实现者、审计员和协议开发者提供完整的技术规范。

以太坊赋予了我们可编程货币，但其执行模型在本质上是被动的——智能合约处于惰性状态，直到被外部控制的系统调用。Cowboy 引入了一种新的执行单元：Actor，一个不朽的、有状态的程序，能够自我调度到未来、为自身的区块空间出价，并在无人干预的情况下无限期运行。以太坊上无论多少 Keeper 网络或 Cron 作业基础设施都无法提供自主、自资助、自调度程序的一等原语。这种新模型需要一种新协议。

Cowboy 进一步创新，采用 Python 作为其执行语言，取代现有链所需的领域特定语言（以太坊上的 Solidity、Solana 上的 Rust）。Python 在 AI 和通用开发中的普及降低了人类开发者和 AI 编程代理的准入门槛，这些代理生成 Python 的可靠性已超过小众智能合约语言。

有关架构设计原理和设计决策，请参阅《设计决策概述》。

## 1.3 架构概述

本节为描述性且非约束性内容。规范性要求见 §§1–17。

### 1.3.1 术语

- Actor（执行体）：具有持久化键值状态和邮箱的 Python 程序。
- Message（消息）：传递给 Actor 处理程序的数据报。
- Cycle（计算周期）：链上计算的计量单位。
- Cell（数据单元）：字节计量单位（1 Cell = 1 字节）。
- Runner（运行者）：执行作业并返回经过证明的结果的链下工作节点。
- Entitlement（权限）：管理 Actor 或 Runner 能力的许可。
- GBA（Gas 竞价代理）：代表另一个 Actor 动态竞价定时器执行的 Actor。

### 1.3.2 核心特性

Cowboy 实现了四项核心技术特性：

- **确定性 Python Actor。** Cowboy 上的智能合约即 Actor：具有私有状态、异步消息邮箱和链原生定时器的 Python 程序。Actor 在沙箱化的 Python 虚拟机（PVM）中执行，锁定于 Python 3.11.8，具备确定性浮点运算（softfloat）、禁用 GC、固定哈希种子和白名单模块集。重入深度上限为 32；单次调用内存上限为 10 MiB。

- **原生定时器与调度器。** Actor 通过 set_timer 和 set_interval 调度自身未来执行，无需外部 Keeper 基础设施。调度器使用分层日历队列和 GBA（Gas 竞价代理）机制，在出块时动态竞价定时器执行。反 DoS 措施包括递进式押金、指数级同块附加费、每 Actor 定时器上限和动态定时器基础费。

- **可验证链下计算。** 去中心化的 Runner 市场在链下执行作业（LLM 推理、HTTP 请求、自定义计算）。Runner 质押 CBY 并通过 VRF 被选中。结果在开发者选择的信任模型下验证：N‑of‑M 法定人数、经济保证金、TEE 证明、结构化匹配、语义相似度或（V2）ZK 证明。提交‑揭示协议配合 15 分钟挑战窗口和罚没机制确保诚实行为。

- **双计量 Gas。** 两个独立的费用市场分别为计算（Cycle）和数据（Cell）定价。每个计量器使用随需求动态调整的基础费，基础费被销毁；小费归出块者。这防止了计算密集型和存储密集型工作负载之间的交叉补贴。

### 1.3.3 与以太坊的差异

| 方面 | 以太坊 | Cowboy |
|--------|----------|--------|
| 执行 | EVM 字节码（Solidity） | 沙箱化 PVM 中的 Python Actor |
| 费用 | 单一 Gas 标量 | 双计量器（Cycle + Cell） |
| 调度 | 需要外部 Keeper | 带 GBA 拍卖的原生定时器 |
| 链下计算 | 外部预言机 | 可验证的 Runner 市场 |
| 状态管理 | 无限期存储 | 带驱逐和恢复的租金机制 |

## 1.4 账户与状态

Cowboy 区分两种对象类型：

- **外部账户（EOA）：** 由私钥控制。它们发起交易并持有 CBY 和其他资产余额。密钥管理未来可通过 Passkey 或其他 WebAuthn 兼容机制进行抽象。

- **Actor（执行体）：** 在 PVM 中执行的自主 Python 程序。Actor 拥有存储空间，接收消息，并可向其他 Actor 发送消息。

每个对象具有 20 字节地址。Actor 地址以 CREATE2 方式从创建者地址、盐值和代码哈希计算得出。世界状态的映射为：

State : Address → { balance, nonce, code_hash?, storage?, metadata }

其中 Actor 存储为键值映射，受配额和租金约束。系统 Actor 和预编译合约占据地址空间的保留前缀（0x0000…0100）。

## 1.5 交易与消息传递

用户通过发送签名交易与 Cowboy 交互，交易指定目标地址、有效载荷和资源限制：Cycle 限制和 Cell 限制，以及每种的最高价格和小费。

Actor 通过发送消息与其他 Actor 交互。消息携带有效载荷，可转移价值，并可触发后续消息。最终性后保证恰好一次投递；最终性前为至少一次投递，可能被回滚。处理程序必须（MUST）是幂等的。Actor 可调度定时器在未来区块高度插入消息。为避免通过爆炸性扇出进行拒绝服务攻击，一笔交易（包括所有嵌套发送）必须不能（MUST NOT）入队超过 1,024 条消息。

### 1.5.1 原生定时器与 Actor 调度器

Cowboy 提供协议原生定时器，消除了对外部 Keeper 网络的需求。Actor 将消息调度到自身或其他 Actor 在未来的区块高度或循环间隔执行。

### 分层日历队列

调度器使用三层结构管理不同时间跨度的定时器，确保每块恒定开销：

- **第 1 层——区块环形缓冲区：** 即将到来的定时器，每块一个槽位。O(1) 入队/出队。
- **第 2 层——纪元队列：** 中期定时器，在纪元边界批量迁移到第 1 层。O(1) 摊销。
- **第 3 层——溢出排序集：** 长期定时器，存储在 Merkle 化二叉搜索树中。O(log n)。

### Gas 竞价代理（GBA）

Actor 不必预付固定 Gas 费用，而是可以指定一个 GBA——另一个代表其动态竞价定时器执行的 Actor。未指定 GBA 的 Actor 会获得协议提供的默认代理，该代理采用保守竞价策略。当定时器到期时，协议对 GBA 执行只读调用，上下文包含当前基础费、定时器紧急度（延迟了多少个区块）和所有者余额。GBA 返回竞争性出价，在块内为定时器通道的计算预算创建拍卖。

### 公平性与活性

延迟的定时器获得带指数衰减的加权优先级提升，防止高出价 Actor 的永久饥饿。

**DoS 防护。多层保护定时器系统：**

| 攻击向量 | 缓解措施 |
|---------|---------|
| 调度数百万定时器 | 递进式押金：deposit(n) = base_deposit × (1 + floor(n / 100)) |
| 跨多个 Actor 的 Sybil 攻击 | 每块执行预算限制总定时器工作量（区块 Cycle 的 20%） |
| 定时器炸弹（同一块大量定时器） | 指数级同块附加费：surcharge(k) = base_cost × 2^max(0, k - 16) |
| 提前大量填充队列 | 队列深度超过目标时定时器基础费自动上升 |
| 永久性超额竞价 | 延迟定时器的反饥饿提升 |
| DoS 后取消以获得退款 | 附加费被销毁，取消时不退还 |

每 Actor 定时器限制：256 个活跃定时器。定时器触发或取消时退还押金。

## 1.6 异步执行与多块语义

### 1.6.1 单块原子性

Cowboy 仅在单一区块内提供原子性。处理程序内的所有状态读取、写入和出站消息是原子的——它们要么全部提交，要么全部回滚。没有跨块原子性。处理程序完成且区块最终化后，后续处理程序在可能不同的世界状态中执行。

### 1.6.2 为何不支持跨块交易

跨块原子性要么需要全局锁（破坏并发性并创建死锁向量），要么需要带回滚的推测性执行（创建恶意攻击机会和不可预测的成本）。Cowboy 明确拒绝这两种方法。

跨块暂停执行的根本问题在于：(1) 过期状态——yield 之前读取的值可能已更改；(2) 无效控制流——基于 yield 前状态所做的分支可能不再适用；(3) 可组合性爆炸——嵌套 yield 创建交叉执行路径，每条路径依赖于已失效的假设；(4) 对抗性恶意攻击——攻击者可在 yield 点之间修改状态。

### 1.6.3 消息传递续延模型

Cowboy 不使用隐式续延，而是对所有异步操作使用显式消息传递。当 Actor 分发链下作业时，结果作为单独消息在后续区块中到达。Actor 必须在回调处理程序中重新读取和重新验证任何状态假设。

此模型要求显式上下文捕获——续延中所需的任何状态都必须包含在出站消息中。关联 ID 使响应与请求匹配成为可能。如果 Actor 发送多个请求，响应可能以任意顺序到达。

Actor 必须（MUST）为依赖外部响应的操作实现超时处理。推荐模式是将关联跟踪与原生定时器结合：在每个出站请求旁调度超时定时器，响应到达时取消该定时器。

| 模型 | 原子性 | 开发者负担 | 恶意攻击抵抗 |
|------|--------|-----------|------------|
| 以太坊（同步调用） | 单笔交易 | 低 | 高 |
| 跨块锁 | 多块 | 低 | 低（死锁、锁恶意攻击） |
| 乐观 + 回滚 | 多块 | 中 | 低（回滚垃圾攻击） |
| Cowboy（消息传递） | 单块 | 中 | 高 |

## 1.7 Cowboy Actor 虚拟机（PVM）

Cowboy 使用 Python 作为其执行语言。PVM 在锁定于 Python 3.11.8 的确定性沙箱中执行 Python 字节码，通过限制确保所有节点产生相同结果。

### 1.7.1 确定性保证

**运行时环境：**

- 无 JIT 编译——仅纯解释模式。
- 通过引用计数进行确定性内存管理。循环垃圾回收器被禁用；创建引用循环必须（MUST）抛出 DeterminismError。
- 固定递归限制：256（与 Cycle 计量集成）。

**数值确定性：**

- 所有浮点运算使用跨平台软件数学库（softfloat），而非主机 FPU。
- 超越函数（sin、cos、log、exp 等）使用确定性 softfloat 实现。
- 如果使用 decimal 模块，必须（MUST）使用固定舍入模式（ROUND_HALF_EVEN）和固定精度。

**集合排序：**

- PYTHONHASHSEED 固定为 0。
- dict 迭代按插入顺序（Python 3.7+ 保证确定性）。
- 内置 set 和 frozenset 被 cowboy_sdk.collections 中的 ordered_set 替换（对用户代码透明）。

**序列化：**

- 所有跨越信任边界的数据必须（MUST）使用规范 CBOR（RFC 8949, §4.2）：排序的映射键、最短整数编码、无无限长度容器、仅 64 位浮点数。
- pickle 被禁止。JSON 输出必须（MUST）使用 sort_keys=True、separators=(',', ':')。

**模块白名单（v1）：**

collections、dataclasses、enum、functools、itertools、json、re、struct、math、decimal、typing、abc、hashlib、cowboy_sdk。不允许 C 扩展。不允许动态导入。其他模块可通过治理在确定性审计后添加。

**禁止的操作：**

| 类别 | 禁止内容 |
|------|---------|
| 系统 | sys.exit()、os.environ、os.system()、subprocess.* |
| 时间 | time.time()、datetime.now()、time.sleep() |
| 随机性 | random.*（使用 cowboy_sdk.vrf 替代） |
| 网络 | socket.*、urllib.*、http.*、requests.* |
| 文件系统 | 除 /tmp 临时空间（256 KiB 限制，处理程序执行后清除）外全部禁止 |
| 反射 | eval()、exec()、compile()、globals() 修改 |
| 内省 | sys._getframe()、inspect.currentframe()、gc.* |
| 弱引用 | weakref.*（非确定性回收时序） |
| 线程 | threading.*、multiprocessing.*、concurrent.* |
| 身份比较 | 字符串或数字上的 is 比较（使用 ==） |

### 1.7.2 存储与状态持久化

存储架构使用三层模型：

1. **账本（Ledger）：** 仅追加的区块日志——顺序的、历史的真相来源。
2. **Triedb：** Merkle‑Patricia Trie，为每个区块生成可验证的 state_root，保存所有账户、代码和存储状态。
3. **辅助索引：** 可重建的、读优化的表，用于交易哈希、事件主题等。不属于共识关键状态根的一部分。

跨虚拟机兼容性。存储键中的 vm_ns（VM 命名空间）标志允许 PVM 和未来 EVM 存储在同一地址下共存而无冲突。标准化的 C‑ABI 包装器实现跨 VM 调用。

所有 Actor 存储都受状态租金约束（见 §4.4 及下文数据可用性部分）。

## 1.8 定价：Cycle 与 Cell

以太坊使用单一 Gas 标量。Cowboy 将定价分为两个独立计量器：

- **Cycle** 计量计算：Python 操作和宿主调用各有固定成本，定义在共识关键成本表中。Cycle 类似于 Erlang 的归约操作——限制处理程序执行的离散步骤预算。
- **Cell** 计量字节：调用数据、返回数据、Blob 和存储写入都消耗 Cell（1 Cell = 1 字节）。

每个区块根据需求动态调整两个基础费（每个计量器一个）。用户为每个计量器指定最高价格和可选小费。基础费被销毁；小费归出块者。

协议不计量链下 Runner 执行。Runner 在自由市场中设定自己的价格，Actor 在提交时托管 CBY。这将确定性的链上计量与非确定性的链下资源定价分离。

## 1.9 链下计算：Runner 市场

Actor 可将计算任务——LLM 推理、HTTP 请求、重型转换——外包给去中心化的 Runner 网络，Runner 需质押 CBY。市场是可验证的：链在开发者选择的信任模型下接受结果，不诚实的 Runner 面临罚没风险。

**作业生命周期：**

1. **发布：** Actor 提交作业，附带托管价格、资源限制和信任模型。
2. **分配：** 通过 VRF 从合格（已质押、健康）的 Runner 中选择 M 个 Runner 组成委员会。
3. **提交：** Runner 返回 commit = keccak256(output || salt)。
4. **揭示：** Runner 揭示 {output, salt, proof?}。
5. **挑战：** 开放 15 分钟挑战窗口；挑战者需发布 100 CBY 保证金。
6. **解决：** 经证实的不诚实行为触发罚没；运营故障仅导致声誉惩罚。
7. **支付：** 最终确定时，99% 的作业支付给 Runner，1% 归国库。

**信任模型：**

| 模式 | 信任级别 |
|------|---------|
| N‑of‑M 法定人数 | 委员会执行；运行时接受共识结果 |
| N‑of‑M 带争议 | Runner 质押保证金；争议者可在固定窗口内证明错误结果 |
| TEE 证明 | 在可信执行环境中执行；链上验证证明 |
| ZK 证明（v2） | Runner 提供 zk‑SNARK 进行密码学验证 |

Runner 和 Actor 通过权限（Entitlements）匹配——一个声明式权限框架，管理 TEE 要求、数据驻留和支持模型等能力（见 §15）。

### 1.9.1 Runner 资源核算

每个作业提交都包含明确的资源限制（最大 Token 数、最大执行时间、最大内存、最大价格）。Runner 向链上注册表发布费率卡。作业定价遵循：actual_payment = min(reported_usage × rates, max_price)。小费在高需求时激励优先处理。

Runner 报告的用量默认受信任，受声誉评分和异常检测约束（>2× 预期用量触发自动审查）。对于更强的保证，Actor 可要求 TEE 证明的计量。经证实的不诚实行为（如伪造结果、虚报用量）通过挑战机制受到质押罚没；运营故障（超时、崩溃）仅导致声誉惩罚。

**支付与故障处理：**

| 结果 | Runner 支付 | Actor 退款 |
|------|-----------|-----------|
| 成功 | min(reported_usage × rates, max_price) + 小费 | max_price - actual_payment |
| Runner 故障（超时、无效结果、崩溃） | 0 | 100% 托管金 |
| 不可能的作业（限制过紧） | 按进度比例支付 | 剩余托管金 |
| Actor 故障（格式错误的输入） | 最低费用（Gas 成本补偿） | 剩余托管金 |
| 外部故障（API 宕机、模型不可用） | 按进度比例支付 | 剩余托管金 |

### 1.9.2 LLM 结果验证

LLM 输出本质上是非确定性的——相同提示可能产生语义等价但字节不同的输出。Cowboy 提供多种验证模式：

| 模式 | Runner 数量 | 验证方式 | 范围 | 用例 |
|------|------------|---------|------|------|
| none | 1 | 无 | 仅未投递 | 原型开发、低风险 |
| economic_bond | 1 | 客观检查 | 客观故障 | 主观生成 |
| majority_vote | N‑of‑M | 字段值投票 | 客观故障 | 分类 |
| structured_match | N‑of‑M | 验证函数 | 客观故障 | 结构化提取 |
| deterministic | N‑of‑M | 精确匹配 + TEE | 完全复现 | 关键确定性任务 |
| semantic_similarity | N‑of‑M | 嵌入阈值 | 客观故障 | 带相似度的主观任务 |

这些模式提供经济保证而非密码学正确性，除非明确要求 TEE 或 ZK 验证。协议保证执行完整性，而非输出质量——质量是市场结果。

**客观故障标准（自动检测，无需挑战）：**

| 故障 | 检测 | 后果 |
|------|------|------|
| Schema 违规 | 输出未通过声明的 JSON Schema | 声誉惩罚，不支付 |
| 超时 | 在 max_wall_time 内无结果 | 声誉惩罚，不支付 |
| 空/垃圾输出 | 输出低于 min_length 或未通过熵检查 | 声誉惩罚，不支付 |
| 未投递 | Runner 接受作业但从未提交 | 声誉惩罚，不支付 |
| 错误模型 | TEE 证明显示不同模型哈希 | 罚没（证实的不诚实） |
| 提示注入泄露 | 输出包含系统提示标记 | 声誉惩罚，不支付 |

仅经证实的不诚实行为（伪造结果、TEE 证明显示错误模型）触发质押罚没。运营故障降低 Runner 的声誉分数，影响未来作业选择，但不销毁质押。

### 1.9.3 外部数据与预言机语义

Actor 经常需要外部数据：价格馈送、Web API、公共数据集。外部数据本质上是可变的和非确定性的。不同来源需要不同的验证策略：

| 来源类型 | 特征 | 验证策略 |
|---------|------|---------|
| 确定性 API | 版本化、稳定、结构化（区块链 RPC、静态文件） | 精确匹配 |
| 半稳定 API | 结构化但元数据可变（REST API） | 结构化匹配，忽略元数据 |
| 时间序列数据 | 值随时间变化（价格馈送） | 中位数/多数，带新鲜度限制 |
| 网页抓取 | 非结构化、高度可变（HTML 页面） | 基于提取的匹配 |
| 认证端点 | 需要凭证 | 单 Runner + TEE |

### 新鲜度
Actor 通过引用模式（block、submission 或 absolute）和 max_age_seconds 参数指定新鲜度约束。

### 快照模式
当多个 Runner 获取可变数据时，协议通过以下方式之一选择规范结果：first_valid（第一个 Runner 的结果为权威）、median（数值数据）、majority（分类数据）或 latest（按时间戳最新）。

### 基于提取的验证
对于网页抓取，Runner 应用提取规则（CSS 选择器、XPath、JSONPath、正则表达式）并提交提取的数据而非原始 HTML。验证比较提取的字段，忽略无关的页面差异。

HTTP 访问受权限系统管理。Actor 声明所需域名；Runner 公布支持的域名。协议提供精选域名集（price_feeds、government_us、social_apis、blockchain_rpc）。

## 1.10 随机性

每个区块使用阈值 BLS VRF 从前一个法定人数证书推导随机信标。Actor 通过 HKDF(R_n, label) 访问子随机数，用于公正的委员会抽样、抽奖和游戏。

## 1.11 共识与网络

Cowboy 使用 Simplex BFT 配合权益证明。关键参数：约 1 秒出块、约 2 秒最终性、可容忍 f < n/3 拜占庭验证者。

**共识流程：**

1. **提案：** 当前出块者（通过按质押加权的 VRF 选出）广播区块。
2. **投票：** 验证者投票；签名在法定人数（2f+1）时进行缓冲批量验证。
3. **认证：** 从 2f+1 票形成法定人数证书（QC）。
4. **最终化：** 当区块的直接子块拥有 QC 时，该区块即最终确定（两链提交）。

在部分同步情况下，协议在所有时间保证安全性，在网络延迟有界时保证活性。如果出块者失败，验证者执行视图切换：广播其最高 QC，下一个 VRF 选出的领导者基于最高 QC 区块提案。

### 1.11.1 验证者集

验证者集是开放的、无许可的。要求：质押 ≥ minimum_validator_stake（治理可调）、仅自质押（v1 无委托）、合规验证者软件。验证者数量无协议上限。

生命周期：注册（质押 CBY，提交 BLS12‑381 密钥）→ 激活（下一纪元边界）→ 运行（提案、投票、获取奖励）→ 退出（发出解绑信号）→ 提取（7 天解绑期后）。

纪元：3600 块（约 1 小时）。验证者集更新、罚没惩罚和纪元随机数推导在纪元边界发生。

### 1.11.2 质押与奖励

区块奖励（来自通胀）按质押比例分配。出块者额外获得交易小费。质押仅限自绑定；委托推迟至 v2。

### 1.11.3 罚没

Cowboy 使用保守的罚没模型——大多数违规导致监禁（临时移除）而非质押销毁：

| 违规 | 惩罚 |
|------|------|
| 双签 | 监禁 + 罚没 1% 质押 |
| 出块者模棱两可 | 监禁 + 罚没 1% 质押 |
| 长时间宕机（>1000 块中 >50% 的投票缺席） | 监禁（不罚没） |
| 无效区块提案 | 监禁（不罚没） |

被监禁的验证者必须等待 24 小时才能解除监禁。重复违规以指数方式增加监禁时间。

### 1.11.4 网络层

传输：QUIC over TLS 1.3（必需）。Gossip：交易泛洪到所有对等节点；区块由验证者中继；投票直接发送给出块者。对等发现：基于 DHT，配合引导节点。

### 1.11.5 专用通道

区块空间被划分为具有保留容量的专用通道：

| 通道 | 保留容量 | 内容 |
|------|---------|------|
| 系统 | 5% | 验证者更新、治理、罚没 |
| 定时器 | 20% | 计划的定时器执行 |
| Runner | 25% | Runner 作业结果和证明 |
| 用户 | 50% | 用户发起的交易 |

高优先级通道中未使用的容量级联到低优先级通道。交易在提交时按类型标记；出块者不能重新分配通道。每个通道有独立的费用乘数，应用于全局基础费。

### 1.11.6 MEV 缓解

Cowboy 通过四种机制缓解 MEV：(1) 通过 VRF 强制每块出块者轮换防止多块观察；(2) 基于 VRF 的块内交易排序防止策略性放置；(3) 约 2 秒最终性最小化观察窗口；(4) 通道隔离防止拥塞攻击延迟受害者交易。不使用加密内存池——鉴于已经极小的 MEV 表面，边际收益不足以证明增加的延迟成本。这不能防止出块者的包含/审查或私人订单流 MEV。

## 1.12 数据可用性、状态租金与存储

### 1.12.1 内联数据 vs. Blob

小输出（≤ 64 KiB）以内联方式存储并以 Cell 支付。较大的工件必须（MUST）作为内容寻址的 Blob（例如 IPFS）存储，链上引用 multihash。

### 1.12.2 状态租金

所有持久化 Actor 存储都受状态租金约束——占用全局状态 Trie 空间的持续费用。租金费率根据网络状态总大小动态调整：

rent_rate_{i+1} = rent_rate_i × (1 + clamp((S - T) / (T × alpha), -delta, +delta))

其中 S 为当前总状态大小，T 为目标（治理可调），alpha = 8，delta = 0.125。

租金从 Actor 余额中每租金纪元（默认：1 天）自动扣除。Actor 也可预付租金以确定成本，任何账户可代替任何 Actor 赞助租金。每个 Actor 维持最低余额储备（约 5 周租金）作为进入宽限期前的缓冲。

### 1.12.3 宽限期与驱逐

当 Actor 无法支付租金（余额、储备和预付纪元耗尽）时：

- **宽限期（7 个租金纪元）：** Actor 保持完全功能；标记为"租金逾期"；补缴费用累积（欠租金的 10%）。
- **警告期（3 个租金纪元）：** Actor 标记为"即将驱逐"；发出事件通知依赖的 Actor。
- **驱逐（第 N+11 个租金纪元）：** Actor 存储和活跃定时器被修剪。代码、地址、余额和存储根哈希被保留。Actor 进入"休眠"状态。

被驱逐的存储可由任何人通过提供原始数据（对照记录的根哈希验证）并支付欠租加补缴费用来恢复。

### 1.12.4 存储配额

每个 Actor 有 1 MiB 的基础存储配额，可通过存储保证金扩展至最多 8 MiB。保证金在配额使用期间锁定，减少时退还，Actor 被驱逐时没收。租金适用于全部已分配配额。

## 1.13 状态转换函数

状态转换函数接收一个区块和一个输入状态，返回下一个状态。设 σ 为全局状态，B 为包含交易 T_i、基础费 (bf_c, bf_b) 和随机数 R 的区块。

1. **区块头/出块者：** 由 Simplex 确定；R 从父 QC 推导。
2. **执行交易：** 按通道选择，然后 VRF 排序。对于每笔交易：验证签名、nonce 和余额；初始化计量器；分派到目标（扇出 ≤ 1,024，重入深度 ≤ 32）；强制内存（10 MiB）、邮箱（≤ 1,000,000 字节）和存储配额；扣除费用并销毁基础费。
3. **投递定时器：** 在 height(B) 注入到期定时器。
4. **解决作业：** 处理提交、揭示、挑战和支付。
5. **调整基础费：** 根据区块利用率更新 (bf_c, bf_b)。
6. **铸造奖励：** 向验证者分配每块通胀。

### 规范性约定

本文档使用RFC 2119 中定义的 MUST/SHOULD/MAY。标记为"治理可调"的参数可通过链上治理更改（见 §11）。

## 1. 账户、地址与密钥

### 1.1 签名

外部账户必须（MUST）使用带 chain‑id 分离的 secp256k1（ECDSA）。

### 1.2 Actor 地址推导（CREATE2 风格）

新 Actor 地址必须（MUST）为：addr = last_20_bytes(keccak256(creator || salt || code_hash))，其中 code_hash = keccak256(python_source_bytes)。

python_source_bytes 必须（MUST）规范化为 UTF‑8、NFC 规范化、LF 换行符且无 BOM。规范字节即为被哈希和存储的内容。

### 1.3 系统地址空间

范围 0x0000…0100 保留用于系统 Actor 和预编译合约（见 §10）。

## 2. 交易类型与编码

### 2.1 类型化交易（EIP‑1559 风格，双计量器）

交易必须（MUST）包含：chain_id、nonce、to、value、cycles_limit、cells_limit、max_fee_per_cycle、max_fee_per_cell、tip_per_cycle、tip_per_cell、access_list?、payload、signature。

### 2.2 有效性检查

节点必须（MUST）在以下情况拒绝交易：(a) 限制超过最大值（§13.1）；(b) 余额不足；(c) 签名无效；(d) 访问列表无效；(e) 有效载荷解码失败。

### 2.3 费用核算

设 bc、bb 为 Cycle/Cell 的区块基础费。费用为：fee = cycles_used × (bc + min(tip_per_cycle, max_fee_per_cycle - bc)) + cells_used × (bb + min(tip_per_cell, max_fee_per_cell - bb))。未使用的限制必须（MUST）按用户的 max_fee_* 费率退还。

### 2.4 EBNF（参考性）

Tx = Header Body Sig Header = chain_id nonce to value cycles_limit cells_limit max_fee_per_cycle max_fee_per_cell tip_per_cycle tip_per_cell [access_list] Body = payload Sig = secp256k1_signature_recoverable

### 2.5 编码（规范性）

交易必须（MUST）编码为规范 CBOR（RFC 8949，确定性编码）数组，字段顺序固定：

Tx = [chain_id, nonce, to, value, cycles_limit, cells_limit, max_fee_per_cycle, max_fee_per_cell, tip_per_cycle, tip_per_cell, access_list, payload, signature]

- to 为 20 字节地址或 null（用于 Actor 创建）。
- access_list 为 null 或 [address, storage_keys[]] 对的列表。
- signature = [y_parity, r, s]，其中 y_parity ∈ {0,1}，r 和 s 为 32 字节大端字节串。
- 签名哈希必须（MUST）为 keccak256(CBOR(Tx_without_signature))，其中 Tx_without_signature 为 signature 字段设为 null 的相同数组。

## 3. 执行模型（Actor）

### 3.1 运行时与确定性

- 官方 SDK：Python SDK。运行时必须（MUST）强制确定性：

  - 允许的操作：标准 Python 操作，文件 I/O 限于 /tmp；async/await 仅为语法糖，不会跨块暂停。
  - 禁止：sys.exit()、random 模块（链 VRF 除外）、time.time()/datetime.now()、os.environ 访问、socket/网络操作、subprocess 调用、/tmp 外的路径遍历。
  - 浮点数：允许；Cowboy 提供确定性数学库。
  - 临时空间：/tmp 必须（MUST）为每次调用独立，上限 256 KiB（计入 cells_used），处理程序执行后清除。

### 3.2 内存与存储

- 单次调用内存限制：10 MiB 堆内存。
- 每 Actor 持久化存储配额：1 MiB（治理可调），带状态租金（§4.4）。
- 配额扩展：Actor 可发布存储保证金，总计最多 8 MiB；租金适用于全部已分配配额。

### 3.3 消息传递、重入、定时器

- **投递：** 最终性后恰好一次（最终性前：至少一次）。每条消息 ID 必须（MUST）为 keccak256(sender||nonce||msg_hash)，记录在每 Actor 去重集中（计入 Actor 存储或单独的计量邮箱存储）。去重条目必须（MUST）在最终性后至少保留 dedup_window。
- **邮箱：** 容量 1,000,000 字节（或等效 Cell 计量限制）；超出限制的入队必须（MUST）回滚。
- **每笔交易扇出：** 一笔交易（包括所有嵌套发送）必须不能（MUST NOT）入队超过 1,024 条消息。
- **重入：** 仅在单一区块内允许；没有跨块的同步调用/返回。递归/await 深度上限 = 32。
- **定时器（链原生）：** 提供以下定时器原语：
  - timer_id = set_timer(height, handler, data) — 为指定区块高度调度单次定时器。返回唯一 timer_id。
  - timer_id = set_interval(every_n_blocks, handler, data) — 调度循环定时器。返回唯一 timer_id。
  - cancel_timer(timer_id) — 通过 ID 取消待执行定时器。成功时返回押金。
  - 定时器投递为尽最大努力；执行取决于 GBA 拍卖（见 §定时器速率限制）。

### 3.4 随机性

- 验证者必须（MUST）每块生成阈值 BLS VRF：R_n = VRF_sk_epoch(QC_{n-1})。Actor 可调用 API 获取 HKDF(R_n, label)。

### 3.5 部分成本表（参考性）

- 精确计量是共识关键的；实现者必须（MUST）匹配参考成本表。

| 原语 | Cycle |
|------|-------|
| Python 算术操作 | 1 |
| Python 函数调用 | 10 |
| 字典 get/set | 3 |
| 列表 append/access | 2 |
| 字符串操作（每字符） | 1 |
| host：邮箱发送（每消息不含载荷） | 80 |
| host：定时器 set/cancel | 200 |
| host：Blob 提交（每 KiB） | 40 |

注：Cell 计量字节（载荷、返回数据、内联 Blob ≤ 64 KiB、/tmp）。

## 4. 费用、计量与基础费调整

### 4.1 计量器

- **Cycle：** Python 操作 + 宿主调用的确定性步骤计数。
- **Cell：** 调用数据、返回数据、内联 Blob（≤ 64 KiB）和 /tmp 使用的字节数。

### 4.2 双 EIP‑1559 基础费

设 U_c、T_c 为 Cycle 使用量/目标；U_b、T_b 为 Cell 使用量/目标。弹性系数 E=2（硬上限 E*T_*），调整公式为：

basefee_{x,i+1} = max(1, basefee_{x,i} * (1 + clamp((U_x - T_x)/(T_x*alpha), -delta, +delta)))

其中 x ∈ {cycle, cell}，alpha = 8，delta = 0.125。节点必须（MUST）销毁 100% 基础费；小费归出块者/验证者。

### 4.3 目标值（创世默认）

- T_c（Cycle 目标）：10,000,000 Cycle（上限 20,000,000）。
- T_b（Cell 目标）：500,000 字节（上限 1,000,000）。

### 4.4 状态租金

持久化存储按每字节每租金纪元收取租金，可通过治理调整。如果 7 个租金纪元未付，开始驱逐警告；10 个租金纪元后可被驱逐。

## 5. 链下计算

### 5.1 模型注册表

model_id = keccak256(weights||arch||tokenizer||license) 必须（MUST）唯一标识模型修订版本。发布无需许可，需可退还的 1,000 CBY 押金。治理可标记/禁止模型。

### 5.2 Runner 质押

Runner 必须（MUST）在 Runner 注册表中质押 max(10,000 CBY, 1.5 × declared_max_job_value)。

### 5.3 作业生命周期

1. **发布：** Actor 发布作业并托管价格。
2. **分配：** 对于 HTTP 域名，从 M=5 个委员会中采样；N=3 匹配揭示完成最终化。LLM 作业可使用委员会或单 Runner。
3. **提交：** Runner 返回 commit = keccak256(output||salt)。
4. **揭示：** Runner 揭示 {output, salt, proof?}。
5. **挑战：** 开放 15 分钟挑战窗口，需 100 CBY 保证金。
6. **解决：** 经证实的不诚实 ⇒ 通过挑战机制罚没质押。运营故障（超时、崩溃）仅导致声誉惩罚。
7. **支付：** 最终确定时，99% 作业支付给 Runner，1% 归国库。

### 5.4 确定性与限制

作业必须（MUST）锁定 toolchain_digest 和 seed。链上返回数据必须（MUST）≤ 64 KiB。

### 5.5 TEE 选项

作业可设置 tee_required=true。有效证明必须（MUST）匹配已接受的策略。

## 6. 共识、随机性与网络

### 6.1 共识

Simplex BFT PoS；目标出块时间 ~1 秒；提交最终性（~2 秒）。出块者使用 VRF 信标每块轮换（强制轮换以抗 MEV）。投票通过 BLS12‑381 缓冲批量验证聚合。

消息类型（规范性）：PROPOSE、VOTE、NEW_VIEW。

法定人数证书（QC）：QC = {block_hash, height, round, aggregated_signature, signer_bitmap}，其中 aggregated_signature 为 BLS12‑381 对 block_hash || height || round 域的签名。

VRF：每个区块头必须（MUST）包含出块者对当前高度的 VRF 输出和证明；验证者必须（MUST）对照纪元种子验证。

最终性规则：当区块 B_h 的直接子块拥有 QC 时，B_h 即最终确定（两链提交）。具体来说，如果 QC(B_{h+1}) 存在且 B_h 是 B_{h+1} 的父块，则 B_h 已最终化。实现可以同时公开"提交"和"已最终化"状态。

视图切换：超时时，验证者广播包含其已知最高 QC 的 NEW_VIEW。下一个出块者必须（MUST）基于最高 QC 区块构建。

### 6.2 P2P 传输

实现必须（MUST）支持 QUIC over TLS 1.3。

### 6.3 专用通道

区块空间被划分为具有保留容量的专用通道：

| 通道 | 保留容量 | 优先级 | 内容 |
|------|---------|--------|------|
| 系统 | 5% | 最高 | 验证者更新、治理、罚没 |
| 定时器 | 20% | 高 | 计划的定时器执行 |
| Runner | 25% | 高 | Runner 作业结果和证明 |
| 用户 | 50% | 普通 | 用户交易 |

通道保证：

- 定时器和 Runner 通道防止用户交易垃圾攻击阻止自主 Actor 执行
- 高优先级通道中未使用的容量溢出到低优先级通道
- 每个通道有独立的费用乘数，应用于全局 Cycle/Cell 基础费

### 6.4 Gossip（内存池）

公共内存池按有效费用优先排序。在每个通道内，出块者按最高有效费用选择交易直至通道容量（平局通过 tx_hash 决定），然后在选定集合内应用 VRF 排序。对于排序，effective_fee 使用固有成本计算：effective_fee = intrinsic_cycles × min(max_fee_per_cycle, basefee_cycle + tip_per_cycle) + intrinsic_cells × min(max_fee_per_cell, basefee_cell + tip_per_cell)。交易按通道类型标记。v1 无私有构建者或加密内存池——MEV 抵抗依赖快速最终性和强制出块者轮换。

### 6.5 MEV 缓解（有局限性）

Cowboy 的 MEV 缓解策略结合多种机制：

**强制出块者轮换：** Simplex 共识通过 VRF 每块轮换出块者。与稳定领导者协议不同，没有单个验证者能跨多个区块观察交易流，限制 MEV 提取窗口。

**基于 VRF 的交易排序：** 在每个区块内，交易按以下方式排序：

order_key = VRF(proposer_key, tx_hash, block_height)

这种确定性但不可预测的排序防止出块者策略性放置自己的交易。

注：这不能防止出块者的包含/审查或私人订单流 MEV。

**快速最终性：** ~2 秒最终性（2 个 Simplex 轮次）最小化以下窗口：

- 抢跑交易（有限的观察时间）
- 三明治攻击（执行失败风险高）
- 时间盗贼攻击（链在最终性后永不重组）

**专用通道：** 定时器和 Runner 的保留容量确保自主 Actor 可靠执行，不受用户内存池拥塞影响。攻击者无法通过垃圾攻击用户通道来延迟其他通道中的受害者交易。

**无加密内存池：** Commit‑reveal 方案增加延迟和复杂性。鉴于 ~1 秒出块和 ~2 秒最终性，观察窗口已经极小。VRF 排序 + 轮换 + 快速最终性的组合提供了足够的 MEV 抵抗，无需加密带来的延迟成本。

## 7. 数据可用性与 Blob

### 7.1 内联上限

每个输出的内联 Blob 上限为 64 KiB。

### 7.2 外部 Blob

更大数据必须（MUST）采用内容寻址存储（如 IPFS）。链上承诺必须（MUST）为 multihash。

## 8. 经济、通胀与费用

### 8.1 代币与供应量

CBY。创世供应量 1,000,000,000 CBY。

### 8.2 通胀

使用递减通胀计划引导网络安全：

- 第 1-2 年：年通胀率 8%
- 第 3-4 年：年通胀率 5%
- 第 5-6 年：年通胀率 3%
- 第 7-10 年：年通胀率 2%
- 第 10 年以后：终端通胀率 1%

### 8.3 创世分配

验证者 25%，国库 25%，生态系统 30%，投资者 20%（标准锁定期）。

### 8.4 费用去向与分配

基础费：100% 销毁。小费：归出块者/验证者。链下作业支付：99% 归 Runner，1% 归国库。

## 9. 系统 Actor 与预编译合约

- 0x01 消息传递：入队和扇出消息。
- 0x02 定时器：调度/取消定时器。
- 0x03 预言机/Runner：管理链下作业。
- 0x04 Blob 存储：提交/检索 Blob multihash。
- 0x05 签名工具：secp/BLS/VRF 辅助函数。
- 0x06 EventListener：以太坊事件订阅（见 §16）。
- 0x07 TEE 验证器：对照可信度量验证 TEE 证明。
- 0x08 密钥管理器：为 TEE Runner 提供安全凭证存储和访问控制。

## 10. 开发者体验（DX）

- **SDK：** 提供主要的 Python SDK（cowboy-py）。
- **本地开发：** 一套工具包括单节点开发网（cowboyd）、Runner 模拟器、水龙头和浏览器。
- **最佳实践：** 通过 SDK 鼓励重入保护、能力范围句柄和幂等消息处理。

## 11. 治理与升级

- **模式：** 基金会 5‑of‑9 多签在约 12 个月后过渡到代币加权的链上治理。
- **时间锁：** 标准操作 7 天；紧急快速通道 6 小时。
- **升级：** 由治理协调的热代码升级。

## 12. 安全注意事项

### 12.1 DoS 限制（共识强制执行；治理可调）

- max_tx_size = 128 KiB
- max_message_depth_per_tx = 32
- per_actor_per_block_cycles = 1,000,000（可突发）

### 12.2 Runner 安全

经证实的不诚实（伪造结果、错误模型）触发罚没。运营故障仅导致声誉惩罚。委员会缓解单 Runner 故障。

### 12.3 重入

允许但深度受限；标准库提供重入保护。

### 12.4 随机性偏差

使用纪元密钥的阈值 BLS VRF；Actor 通过 HKDF 推导子随机数。

### 12.5 状态租金与驱逐

防止状态膨胀；驱逐窗口保护活性。

## 13. 参数（创世默认值）

**执行：**

memory_per_call = 10 MiB；storage_quota_per_actor = 1 MiB；reentrancy_depth = 32；fanout_per_tx = 1024；mailbox_capacity_bytes = 1,000,000；dedup_window = 10,000 块。

**费用：**

T_c = 10,000,000 Cycle；T_b = 500,000 字节；alpha = 8；delta = 0.125。

**共识：**

minimum_validator_stake = 治理可调；epoch = 3600 块（~1 小时）；block_time = 1 秒；finality = ~2 秒；unbonding_period = 7 天；jail_period = 24 小时；double_sign_slash = 1%；consensus_protocol = Simplex BFT。

**专用通道：**

system_lane_capacity = 5%；timer_lane_capacity = 20%；runner_lane_capacity = 25%；user_lane_capacity = 50%。

**链下：**

committee M = 5；threshold N = 3；challenge_window = 15 分钟；challenge_bond = 100 CBY；runner_stake_floor = 10,000 CBY。

**状态租金：**

target_state_size = 治理可调；grace_period = 7 租金纪元；warning_period = 3 租金纪元；catch_up_fee = 10%；reserve_multiplier = 0.1。

**经济：**

supply = 1,000,000,000；通胀遵循 §8.2 的计划；basefee burn = 100%；作业费归国库 = 1%。

## 14. 与以太坊的差异

- 执行：Python Actor vs. EVM 合约。
- 费用：双计量器（Cycle/Cell）vs. 单一 Gas 标量。
- 定时器：原生定时器 vs. 外部 Keeper。
- 链下计算：原生可验证市场 vs. 外部预言机。
- 状态：带驱逐的租金 vs. 无限期存储。

## 15. 权限系统（Entitlements）

一种声明式、可组合的权限系统管理 Actor 和 Runner 的能力。权限控制对网络、存储和执行参数等资源的访问，默认执行最小权限原则。系统在部署时、由调度器和在 VM 系统调用门处强制执行。

### 15.1 目标

- 默认最小权限。
- 确定性强制执行。
- 声明式且可组合。
- 链上可审计。

### 15.2 对象与生命周期

- **Actor 权限：** Actor 所需的权限。
- **Runner 权限：** Runner 提供的能力。

### 15.3 规则

1. 必须（MUST）：Actor 需要权限；Runner 提供权限。
2. 必须（MUST）：调度器仅在 requires ⊆ provides 时匹配。
3. 必须（MUST）：如果缺少相应权限，系统调用失败。
4. 必须（MUST）：子 Actor 仅继承标记为 inheritable:true 的权限。

（完整权限列表见《权限规范》。）

## 16. 以太坊互操作性

Cowboy 与以太坊的互操作性是主要设计目标，实现无缝资产转移和跨链通信。这通过共享密码学原语、规范桥和事件订阅机制的组合来实现。

### 16.1 账户统一

- Cowboy 外部账户（EOA）必须（MUST）使用与以太坊相同的 secp256k1 椭圆曲线签名。这允许单一私钥控制两个网络上的账户，简化用户和代理的密钥管理。
- Actor 可通过宿主调用验证针对给定以太坊地址的 EIP‑712 签名数据结构，使 Actor 能够验证来自以太坊用户的链下授权。

### 16.2 桥基础设施

Cowboy 依赖第三方桥基础设施进行 Cowboy 和以太坊之间的资产转移和跨链消息传递。

要求：

- 桥必须（MUST）支持在以太坊上锁定原生 ETH 和 ERC‑20 代币以在 Cowboy 上铸造对应的包装表示（wETH、wERC‑20），以及反向的销毁解锁流程。
- 桥必须（MUST）支持通用消息传递：一条链上的交易触发对另一条链上指定接收者的消息调用。
- 桥的选择和集成由治理决定。协议不实现自己的桥验证者集。

### 16.3 事件订阅（以太坊到 Cowboy）

- Cowboy Actor 可订阅以太坊区块链上特定合约发出的事件日志。
- Cowboy 上的系统 Actor 0x06 EventListener 管理这些订阅。该 Actor 依赖桥验证者集充当去中心化预言机，监控以太坊链上的指定事件。
- 当订阅事件被确认（即在以太坊上最终化）时，EventListener Actor 必须（MUST）向订阅的 Cowboy Actor 入队消息，将事件的主题和数据作为消息载荷投递。
- 此订阅服务的费用由 Actor 以 CBY 支付，涵盖预言机验证者在以太坊上产生的 Gas 费用。

### 16.4 策略与安全

- Actor 可用的所有互操作功能（如 bridge_asset 或 subscribe_event）必须（MUST）受权限系统（§15）管理。
- Actor 的部署清单必须（MUST）声明其被允许交互的特定以太坊合约以及被允许桥接的资产类型，执行最小权限原则。

## 17. 费用模型规范

本节具有权威性；其他地方的任何冲突值均为非规范性的。

### 17.1 概述

Cowboy 使用双计量费用系统：

| 计量器 | 单位 | 用途 |
|--------|------|------|
| Cycle | 计算单位 | CPU 时间、操作码执行、Actor API 调用 |
| Cell | 数据单位（字节） | 存储写入、调用数据、带宽 |

两个计量器使用独立的 EIP‑1559 风格基础费调整。费用以 CBY 支付。

三个成本域：1. 链上执行——交易处理消耗的 Cycle；2. 链上存储——状态写入消耗的 Cell + 持续状态租金；3. 链下服务——直接向 Runner（LLM 推理）和提供商（Blob 存储）支付 CBY。

### 17.2 交易固有成本

每笔交易在执行开始前支付基础成本：

| 交易类型 | 基础 Cycle | 基础 Cell | 备注 |
|---------|-----------|----------|------|
| Transfer | 21,000 | 0 | EOA 到 EOA 价值转移 |
| Deploy | 100,000 | code_size | Actor 部署 |
| ActorMessage | 21,000 | calldata_size | 方法调用 |
| LlmRequest | 10,000 | prompt_size | 链下推理请求 |
| TimerSchedule | 5,000 | 64 | 调度未来执行 |

### 17.3 执行成本（Cycle）

#### 操作码成本
Python 操作码成本由实现定义，不由协议指定。运行时必须（MUST）确保所有验证者的确定性 Cycle 消耗。

#### Actor API 成本

| 操作 | 基础成本 | 可变成本 |
|------|---------|---------|
| send_message() | 1,000 Cycle | — |
| storage_read() | 500 Cycle | +1 Cycle/字节读取 |
| storage_write() | 5,000 Cycle | +10 Cycle/字节写入 |
| hash() | 100 Cycle | +1 Cycle/字节哈希 |
| verify_signature() | 3,000 Cycle | — |
| get_block_info() | 100 Cycle | — |
| emit_event() | 500 Cycle | +5 Cycle/字节 |

#### 平台代币成本（CIP‑20）

| 操作 | Cycle | Cell |
|------|-------|------|
| token_transfer() | 1,000 | 64 |
| token_transfer_from() | 1,500 | 96 |
| token_approve() | 500 | 32 |
| token_balance_of() | 100 | 0 |
| token_mint() | 1,000 | 64 |
| token_burn() | 500 | 64 |
| token_create() | 10,000 | 256 + name + symbol |

验证钩子每次转移最多增加 50,000 Cycle（有上限）。

### 17.4 链上存储成本（Cell）

| 操作 | Cell 成本 |
|------|----------|
| 状态写入 | 1 Cell/字节写入 |
| 状态读取 | 0.01 Cell/字节（带宽计量） |
| 调用数据 | 1 Cell/字节交易数据 |
| 事件发射 | 0.5 Cell/字节事件数据 |

### 17.5 状态租金

超过宽免阈值的账户支付持续租金：

rent_per_rent_epoch = max(0, account_size - grace_threshold) × rent_rate

参数：
- grace_threshold = 10,240 字节（10 KB）
- rent_rate = 0.001 CBY/字节/年（治理可调）
- rent_epoch_length = 1 天
- eviction_threshold = 10 个租金纪元未付租金

宽限期行为：
- ≤10 KB 的账户：不收取租金
- >10 KB 的账户：仅对超出部分收取租金
- 未付租金作为债务累积在账户上
- 累积 10 个租金纪元的债务后驱逐（状态归档到 Blob 存储，偿还债务后可恢复）

### 17.6 链下 Blob 存储（CIP‑7）

大数据（图片、数据集、AI 推理轨迹）使用保留合约：

| 成本组件 | 收费方式 |
|---------|---------|
| BlobRef 存储 | 链上约 64 字节 → Cell 成本 + 状态租金 |
| 提供商支付 | 通过托管直接向提供商支付 CBY（市场价格） |

Blob 存储不按 Cell 计量。提供商支付为链下协商的直接 CBY 转账。详见 CIP‑7 完整规范，包括：保留策略和 SLA、提供商质押和可用性承诺、观察者审计和挑战机制、支付计划和罚没条件。

### 17.7 链下计算（Runner 市场）

LLM 推理不按 Gas 计量。Runner 在竞争性市场中运营：

| 方面 | 规范 |
|------|------|
| 定价 | Runner 发布报价（每 Token、每模型的 CBY） |
| 选择 | 用户在 LlmRequest 中指定 max_price；通过拍卖或直接选择匹配 |
| 结算 | 验证结果交付后支付 CBY |
| 抵押 | runner_stake >= 10 × average_job_value |
| 验证 | 证明 + 随机重新执行挑战 |

协议不指定 LLM 定价——这由用户和 Runner 之间的市场动态决定。

### 17.8 费用调整（EIP‑1559 风格）

Cycle 和 Cell 均使用独立的基础费调整：

next_basefee = basefee × (1 + δ × (usage - target) / target)

**Cycle 参数：**

| 参数 | 值 |
|------|---|
| 目标 | 10,000,000 Cycle/块 |
| 上限 | 20,000,000 Cycle/块 |
| δ（delta） | 0.125（最大变化 12.5%） |
| α（平滑因子） | 8 块 |

**Cell 参数：**

| 参数 | 值 |
|------|---|
| 目标 | 500,000 字节/块 |
| 上限 | 1,000,000 字节/块 |
| δ（delta） | 0.125（最大变化 12.5%） |
| α（平滑因子） | 8 块 |

基础费销毁：100% 的基础费收入被销毁，产生与网络使用量成正比的通缩压力。

### 17.9 保留容量（执行通道）

区块空间被划分以保证关键交易类型的执行：

| 通道 | Cycle 预算 | 百分比 | 用途 |
|------|-----------|--------|------|
| 定时器 | 2,000,000 | 20% | 计划的 Actor 执行 |
| Runner | 2,500,000 | 25% | LLM 结果回调 |
| 系统 | 500,000 | 5% | 治理、升级 |
| 用户 | 5,000,000 | 50% | 常规交易 |

通道行为：
- 保留通道中未使用的容量溢出到用户通道
- 用户通道不能从保留通道借用
- 定时器通道在其保留容量内拥有最高优先级；执行仍受 GBA 竞价和每块限制约束

### 17.10 费用估算

钱包和应用应当（SHOULD）按以下方式估算费用：

```python
def estimate_fee(tx):
    intrinsic_cycles = INTRINSIC_COSTS[tx.type]
    intrinsic_cells = len(tx.calldata)

    # 通过模拟或启发式估算执行成本
    execution_cycles = simulate_execution(tx)
    execution_cells = estimate_storage_writes(tx)

    total_cycles = intrinsic_cycles + execution_cycles
    total_cells = intrinsic_cells + execution_cells

    # 应用当前基础费
    cycle_fee = total_cycles * cycle_basefee
    cell_fee = total_cells * cell_basefee

    # 添加优先级小费
    priority_fee = (total_cycles * tip_per_cycle) + (total_cells * tip_per_cell)

    return cycle_fee + cell_fee + priority_fee
```

## 附录 A. 交易编码测试向量（参考性）

这些向量指定规范 CBOR 编码。十六进制为小写，无 0x 前缀。

**向量 1：未签名转账（signature = null）**

字段：

- chain_id=1
- nonce=0
- to=0x1111111111111111111111111111111111111111
- value=1
- cycles_limit=21000
- cells_limit=0
- max_fee_per_cycle=10
- max_fee_per_cell=2
- tip_per_cycle=1
- tip_per_cell=0
- access_list=null
- payload=0x（空字节）
- signature=null

CBOR 十六进制：

8d010054111111111111111111111111111111111111111101195208000a020100f640f6

签名哈希为 keccak256(CBOR(Tx_without_signature))，其中 signature 字段为 null（如上）。

**向量 2：已签名转账**

与向量 1 相同字段，附加：

- signature=[y_parity=0, r=0x01*32, s=0x02*32]

CBOR 十六进制：

8d010054111111111111111111111111111111111111111101195208000a020100f6408300582001010101010101

### 规范结束。
