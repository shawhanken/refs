# Cowboy 文档与代码库一致性差异分析：经济系统

本报告概述了白皮书和一系列 CIP 中的技术设计规范与实际 `node` 和 `runner` 代码库实现之间的差异。分析重点主要集中在 Cowboy 的经济系统和相关的核心底层原语上。

---

## 1. CIP-3: 双重计费模型 (Dual-Metered Fee Model)

**状态：部分实现 (缺少动态费用市场)**

- **已实现**：交易结构 (`node/types/src/execution.rs`) 成功支持了双重量度的设计：包含了 `cycles_limit`, `cells_limit`, `max_fee_per_cycle`, 和 `max_fee_per_cell` 字段。
- **GAP - 缺少 EIP-1559 基础费引擎 (Basefee Engine)**: 共识和内存池逻辑中**完全没有**基于区块目标使用量动态调整 `basefee_cycle` 和 `basefee_cell` 的负反馈循环机制。代码中完全没有协议层燃烧的“基础费”与支付给提议者的“小费 (tip)”的概念。
- **GAP - 严格的确定性计量增强**: 尽管存在基础的计量，但尚不清楚 CIP-3 第 2.2.3 节中概述的严格确定性增强方案 (例如动态类型计算额外收费、浮点数软件层面确定性、白名单模块特定成本) 是否在 PVM 中得到了彻底执行。

## 2. CIP-7: 留存合约 (Retention Contracts / SLA-Backed Storage)

**状态：未实现**

- **GAP - 整体功能缺失**: 链下的数据高可用性机制整体缺失。代码库中没有 `RetentionPolicy`, `RetentionContract`, `BlobRef`, 或 `FeedUpdateEnvelope` 的结构定义。
- **GAP - Watchtower (瞭望塔) 审计缺失**: 代码库中完全缺乏负责测试存证的瞭望塔逻辑 (`AvailabilityAttestation`)，也没有关于采样 (RANGE 或 CHUNK_INDEX) 机制以及未按要求留存触发惩罚/扣减质押 (Slashing) 的实现代码。

## 3. CIP-20: 同质化代币 (Fungible Tokens)

**状态：已实现**

- **已实现**：平台原生的代币原语已经被良好集成。`TokenCreate`, `TokenMint`, `TokenTransfer`, `TokenTransferFrom`, `TokenApprove`, `TokenFreeze`, 以及 `TokenSetHook` 已完全定义在 `SystemInstruction` 枚举中，并在 `node/chain/src/token` 模块下被正确处理。

## 4. CIP-21: DEX 与流动性池 (Liquidity Pools)

**状态：未实现**

- **GAP - 平台级别数学辅助原语缺失**: 混合模型架构中描述的标准数学工具函数 (例如 `amm_get_amount_out` 以及 V3 版本需要的 tick 价格数学函数) 在系统原生底层并没有定义。
- **GAP - 标准流动性池缺失**: 代码中没有标准的 `V2Pool` （恒定乘积）或 `V3Pool` （集中流动性）等 Actor的定义代码，也没有用于部署它们的工厂合约。
- **GAP - 平台层路由功能缺失**: 标准的多跳网络路由原语 (`amm_swap_exact_in`, `amm_swap_exact_out`) 缺失。现阶段无法直接在网络底层执行复杂的 DEX 操作和清算路由。

## 5. CIP-22: 连续清算拍卖 (Continuous Clearing Auctions - CCAs)

**状态：未实现**

- **GAP - 整体功能缺失**: 基于公平价格发现的连续拍卖机制代码付之阙如。代码库中没有 `ContinuousClearingAuction` 相关系统级 actor，没有 `AuctionConfig` 配置，也没有用于每区块自动清算释放拍卖代币机制的定时回调。
- **GAP - 流动性播种机制缺失**: 设计中要求拍卖结束时系统原子的将募资所得直接转化为 V2 或 V3 池的流动性功能也无法运转，因为这也依赖于仍然缺失的 CIP-21 系统。

## 6. 链下市场经济 (Runners 市场)

**状态：部分实现**

- **已实现**：在分发任务模块（如 `runner-common` 和 `job-dispatcher`）中能看到 `tee_required` 等属性的定义。这说明链下市场至少有识别和派发需要特定（如 TEE 可信执行环境）高安全性硬件需求的基础。
- **GAP - 高级 Runner 资源计量**: 白皮书中强调了 Runner 需要进行“事后计量”(通过容器 cgroups API 抓取 CPU 时间，峰值内存占用情况等) 来进行市场化收费。当前的开源 `runner` 代码库虽然具备了跑任务的基础能力，但这套支持动态利润成本计算的高级资源经济核算系统似乎仍旧缺失。

---

### 结论

代表核心价值的基础设施模块 (如 CIP-20 的同质化代币) 及其双重资源上限参数已被成功加入架构中。然而，在白皮书和近期众多 CIP 提案中精心设计的、为链上系统提供强劲**市场动力**的模块（如动态调整基础费的EIP-1559机制、AMM、基于时间自动结清的公平拍卖、具有SLA特性的数据留存合约）依然存在着巨大的鸿沟，有待开发为真正的可执行代码。
