# 客户对齐分析：弥合开发与期望之间的差距

> **日期**：2026-02-19
> **目的**：综合所有来源材料，明确团队当前开发成果与客户期望之间的具体差距，并提出切实可行的弥合方案。
> **分析材料**：
> - Slack：`devnet_eng.md`、`Charles_DePue_patrick_Tony.md`
> - Notion：Devnet Milestone、Developer Experience Situational Awareness、Deployment Strategy
> - 会议纪要：3次内部会议（2/11 和 2/18）
> - 白皮书：`20260216_cowboy_whitepaper.md`
> - 已有策略文档：`20260219_client_followup_strategy.md`

---

## 摘要

**核心错位是架构层面的**：团队在深层基础设施上投入了大量精力（42 个 Rust crate，涵盖共识、执行、VM 和链下计算），而客户的优先级集中在**面向开发者的表层**——CLI 工具链、SDK 完善、文档、本地开发环境和 UI 面板。

双方的视角都有其合理性。团队优先构建了困难的基础组件（正确的工程顺序）。客户需要可见的、可用的工具来引导外部开发者（正确的市场顺序）。差距不在于工作缺失——而在于**工作被投入到了哪个层级**。

此外，白皮书与实际实现之间存在**三个关键技术差异**，必须在客户自行发现之前主动向其披露。

---

## 一、认知差距——为何存在

### 团队已构建的内容（自下而上）

来自三个代码仓库（node、pvm、runner）的成果：

| 层级 | 状态 | 详情 |
|------|------|------|
| **共识引擎** | ✅ 已完成 | Simplex BFT，BLS12-381 签名，1秒出块，多节点支持 |
| **执行引擎** | ✅ 已完成 | 双重 Gas 计量（Cycles + Cells），延迟交易，内存池，区块存储 |
| **Actor 模型** | ✅ 已完成 | 5 个系统 Actor（Registry、Dispatcher、Verifier、SecretsMgr、TEEVerifier），CREATE2 地址 |
| **PVM** | ✅ 已完成 | 确定性 Python VM，SoftFloat，Gas 计量，导入守卫，检查点 |
| **Runner 网络** | ✅ 已完成 | 3 种执行器类型（LLM/HTTP/MCP），分布式共识，N-of-M 验证，TEE 运行时，报价单 |
| **RPC/API** | ✅ 已完成 | Axum REST + OpenAPI/Swagger，完整端点覆盖 |
| **CLI（基础版）** | ✅ 部分完成 | deploy、send、query、runner 管理、job 生命周期、transfer |

### 客户的期望（自上而下）

来自 Devnet Milestone 和 DevEx Situational Awareness 文档：

| 层级 | 客户优先级 | 当前状态 |
|------|-----------|---------|
| **CLI 工具链**（`init`、`dev`、`test`、`logs`） | P0 | ❌ 未实现 |
| **SDK**（类型stubs、装饰器、PyPI/npm） | P0 | ⚠️ 仅有最小骨架 |
| **错误体验**（四段式格式、错误映射表） | P0 | ❌ 未实现 |
| **文档**（Getting Started、API 文档） | P0 | ❌ 未实现 |
| **本地开发环境** | P0→P1 | ❌ 未实现（pvm-simulator 可作为基础） |
| **水龙头** | P0 | ❌ 未实现 |
| **Cowchat/浏览器/状态页** | P0 | ❌ 未实现 |
| **Wallet Connect** | 已列出 | ❌ 未实现 |

### 可视化差距

```
客户关注点                               团队关注点
──────────                              ──────────

  ┌─────────────────────┐
  │  UI 层               │ ← 客户期望已有          ← 团队：❌ 未开始
  │  (Cowchat, 浏览器)   │
  ├─────────────────────┤
  │  DX 层               │ ← 客户最高优先级        ← 团队：⚠️ 最小化
  │  (CLI, SDK, 文档)    │
  ├─────────────────────┤
  │  基础设施层           │ ← 客户默认已完成        ← 团队：⚠️ 部分完成
  │  (水龙头, 监控)       │
  ╞═════════════════════╡
  │  核心协议层           │ ← 客户看不到的          ← 团队：✅ 深度投入
  │  (42 个 Rust Crates) │
  └─────────────────────┘
```

**关键洞察**：客户的 Devnet Milestone 文档列出了 11 项协议需求、5 项 Cowchat 需求和 17+ 项 DevEx 需求。团队在协议核心方面覆盖率较高，但在 Cowchat 和 DevEx 工具方面几乎为零——而这些占客户清单项目数的**约 65%**。

---

## 二、按客户文档的详细差距分析

### 2.1 Devnet Milestone — 协议部分（11 项）

| # | 客户需求 | 状态 | 差距 |
|---|---------|------|------|
| 1 | 多节点支持 w/ Simplex，leader 选举 | ✅ 完成 | 无 |
| 2 | 公开 RPC/API | ✅ 完成 | 需确认公网暴露策略 |
| 3 | 公开测试网 RPC 端点 + 状态页 | ⚠️ 部分完成 | RPC 端点已部署（`validator-01.dev.cowboylabs.net`），**无状态页** |
| 4 | 测试网水龙头 | ❌ | 需新建 |
| 5 | CIP 1-6 核心协议 | ⚠️ 大部分完成 | SDK 表面需完善 |
| 6 | CIP-7（流式传输） | ⚠️ 审核中 | Charles 已重写文档；Tony 正在审核 |
| 7 | CIP-20（代币） | ❌ | Tony 问了"CIP-21 在哪里？"——范围不明 |
| 8 | Genesis + 链配置冻结 | ⚠️ | 配置存在但未冻结 |
| 9 | 基础链监控 + 告警 | ❌ | 需新建 |
| 10 | 快照 + 恢复手册 | ❌ | 需新建文档/工具 |
| 11 | 事故响应手册 | ❌ | 需新建文档 |

**协议得分**：2/11 完全完成，4/11 部分完成，5/11 未开始

### 2.2 Devnet Milestone — Cowchat 部分（5 项）

| # | 客户需求 | 状态 |
|---|---------|------|
| 1 | 简单 v0 面板 + 公开区块浏览器 | ❌ |
| 2 | 网络状态面板 | ❌ |
| 3 | 带轻量节点 UI 的 Actor 构建器 | ❌ |
| 4 | Wallet Connect | ❌ |
| 5 | 水龙头请求 UI + 响应状态 | ❌ |

**Cowchat 得分**：0/5 完成

### 2.3 开发者体验 — P0 优先级项（17 项）

| # | 客户需求 | 状态 | 备注 |
|---|---------|------|------|
| 1 | `cowboy init`（项目脚手架） | ❌ | CLI 目前只有 deploy/send/query |
| 2 | `cowboy dev`（本地开发服务器） | ❌ | pvm-simulator 可作为基础 |
| 3 | `cowboy test` | ❌ | |
| 4 | `cowboy actor deploy` | ✅ | Martin 已验证端到端部署 |
| 5 | `cowboy actor logs` | ❌ | |
| 6 | `cowboy inspect` | ⚠️ | inspector crate 已存在；需要封装为 CLI 命令 |
| 7 | SDK 类型注解 + .pyi stubs | ⚠️ | pvm_sdk 有基础模块 |
| 8 | 人性化装饰器（`@actor`、`@timer`） | ⚠️ | 有基础实现 |
| 9 | 四段式错误格式 | ❌ | |
| 10 | 常见错误映射表 | ❌ | |
| 11 | Getting Started 指南 | ❌ | 仅有部署指南，非开发教程 |
| 12 | pvm_host API 文档 | ❌ | |
| 13 | Shell 脚本安装 / 预编译二进制分发 | ❌ | |
| 14 | AI Context（SKILL.md、.cursorrules） | ❌ | P1，可后续跟进 |
| 15 | `cowboy wallet create` | ❌ | 目前仅有 `wallet address` |
| 16 | 账户 balance/nonce/info 查询 | ⚠️ | CLI 代码存在但输出 "not yet implemented" |
| 17 | SDK 发布到 PyPI/npm | ❌ | |

**DevEx P0 得分**：1/17 完全完成，4/17 部分完成，12/17 未开始

### 2.4 汇总差距得分

```
                    完成       部分完成     未开始      总计
协议:                2           4           5          11
Cowchat:             0           0           5           5
DevEx P0:            1           4          12          17
─────────────────────────────────────────────────────────────
总计:                3           8          22          33
                   (9%)       (24%)       (67%)
```

**客户列出的 67% 的项目尚未开始。**

---

## 三、关键技术差异（必须主动披露）

这些差异来自白皮书与会议讨论及代码分析的交叉比对。**三项差异必须在客户自行发现之前主动沟通。**

### 3.1 无权益证明（PoS）

| 方面 | 白皮书描述 | 当前实现 |
|------|----------|---------|
| 共识机制 | "Simplex BFT 共识配合权益证明" | Simplex BFT，f+1 投票，**无质押权重** |
| 验证者选择 | 质押权重选择 | 等权重——所有验证者投票权相同 |
| 影响 | 客户可能默认 PoS 已上线 | 必须说明此功能尚未实现 |

**来源**：会议 3（2/18），关于 PoS 缺失的详细讨论。

### 3.2 签名方案不匹配（ED25519 vs secp256k1）

| 方面 | 白皮书描述 | 当前实现 |
|------|----------|---------|
| 签名方案 | secp256k1（兼容以太坊） | ED25519（32字节，不兼容 ETH） |
| 地址格式 | "Cowboy 采用以太坊的 20 字节地址模型" | 基于 ED25519 的地址 |
| 影响 | **以太坊钱包兼容性被破坏**——MetaMask、wagmi 等无法使用 |

**来源**：会议 3（2/18），团队指出这是"客户方向的核心关注点"。需研究迁移是否可行。

### 3.3 白皮书 vs 代码功能差距

| 白皮书功能 | 代码状态 | 备注 |
|-----------|---------|------|
| 状态租金和驱逐机制 | ❌ 未实现 | 白皮书 §State Rent 中提及 |
| 质押委托/惩罚 | ❌ 未实现 | 依赖 PoS 实现 |
| 同质化代币标准（CIP-20） | ❌ 未实现 | 客户正在询问 |
| 存储定价模型（Cells） | ⚠️ 部分完成 | Cycles 计量可用，Cells 待定 |

---

## 四、未报告的优势（超出客户期望）

以下是**未在客户里程碑文档中列出**但已实现的功能，应作为增值亮点展示：

| 功能 | 代码仓库 | 重要性 |
|------|---------|--------|
| 5 个系统 Actor | node | Registry、Dispatcher、Verifier、SecretsMgr、TEEVerifier——客户完全不知 |
| Runner 验证机制 | runner | 链上回放验证链下结果 |
| Runner 分布式共识 | runner | 跨 Runner 数据同步与结果聚合 |
| 延迟交易机制 | node | 跨区块异步执行 + 回调链 |
| 双重 Gas 计量（Cycles + Cells） | node | 比典型的单一 Gas 模型更精细 |
| CREATE2 确定性地址 | node | 可预测的 Actor 部署地址 |
| Runner 报价单（Rate Card） | runner | 链下计算的定价/报价机制 |
| Runner CLI 命令 | CLI | `runner get/list/register`，`job get/status/runners/results/verified/submit` |
| Transfer 命令 | CLI | 原生代币转账 |

---

## 五、错位的根本原因

基于会议纪要和 Slack 分析，归纳出五个根本原因：

1. **规划视角不同**：团队自下而上工作（协议 → DX），客户自上而下规划（DX → 协议）。双方都没有核实对方的假设是否成立。

2. **文档缺失**：团队构建了大量基础设施，但缺乏相应的客户可见文档。除非主动告知，客户无法知道已有什么成果。

3. **Public vs Private Devnet 混淆**：客户期望 Public Devnet；团队一直在构建 Private Devnet。2/11 会议定义了 Private Devnet（2-3月）→ Public Devnet（3月底），但此时间线未明确传达给客户。

4. **规划文档质量问题**：团队认为客户的规划文档"仓促编写"（会议 2），导致轻视态度而非主动参与。与此同时，客户将沉默解读为缺乏进展。

5. **沟通渠道碎片化**：工作分散在 Google Sheets、Notion、Slack 和 GitHub 上追踪，没有唯一的信息源。Tony 在 Slack 上明确询问缺失的 CIP，但未获得清晰回应。

---

## 六、建议行动计划

### 立即行动（本周）

| # | 行动 | 建议负责人 | 目的 |
|---|------|----------|------|
| 1 | 向客户发送架构全景图（英文版） | 团队负责人 | 展示基础设施深度；呈现 42 个 crate 和完整的共识→执行→VM→Runner 链路 |
| 2 | 在 Slack 发布白皮书 vs 代码差异分析（英文版） | 技术负责人 | 主动披露 PoS 缺失、ED25519 问题、状态租金缺口 |
| 3 | 就 CIP-7 审核向 Tony 回复实质性反馈 | Charles/Tony 联络人 | 展示参与度；CIP-7 "审核中"状态已拖延太久 |
| 4 | 在 Slack 回复 Patrick 的产品创意（简短回复 + 文档链接） | PM | 确认 XMTP、Agent Tokens、Cowboy Gold；延迟详细讨论至文档 |
| 5 | 冻结 Devnet 的 Genesis + 链配置 | 基础设施 | 快速成果；客户期望此项 |

### 短期行动（Phase 1：Private Devnet 收尾，截止 3月8日）

| # | 行动 | 详情 |
|---|------|------|
| 1 | CIP-2 更新（纳入 Runner 概念） | 2/18 会议决定：更新 CIP-2 而非新建 CIP-8 |
| 2 | 编写快照 + 恢复手册 | 运维文档 |
| 3 | 编写事故响应手册 | 运维文档 |
| 4 | 创建 CI/CD 测试指引文档 | 供 Martin 使用；部署验证 |
| 5 | 添加 SDK 状态说明注释 | 在代码注释中解释为什么是 partial/minimal |
| 6 | 交付架构可视化图（非 ASCII 版，专业呈现） | 供 Tony 分享给更广泛的客户团队 |
| 7 | 完成 ED25519 → secp256k1 可行性调研 | 确定是否需要/可行迁移 |

### 中期行动（Phase 2：Public Devnet，截止 3月31日）

**DX 层（最高优先级）**：
- `cowboy init`（项目脚手架）
- `cowboy actor logs`（从链 DB/indexer 获取日志）
- `cowboy wallet create`
- 完成 `account balance/nonce/info` 实现（当前为 stub）
- 错误消息：四段式格式（what/why/fix/link）
- 常见错误映射表
- SDK 完整类型注解（PEP 484）+ .pyi stubs
- SDK 装饰器（`@actor`、`@timer` 等）
- SDK 发布到 PyPI/npm
- Getting Started 文档 + 示例 Actor
- pvm_host API 文档
- SimulatedChain 本地开发环境（基础版）——**根据 2/18 会议新增**

**UI 层**：
- Cowchat Dashboard + Builder UI
- 区块浏览器（基础版，含网络状态面板）
- 测试网水龙头 UI + 请求状态
- 状态页
- Wallet Connect（基础集成）

**协议/基础设施**：
- 测试网水龙头 API
- 基础监控 + 告警（出块延迟、RPC 错误率、节点对等数量）
- ED25519 → secp256k1 迁移（如调研确认需要）

### 明确延期（不在 Phase 1 或 Phase 2 范围内）

根据会议讨论，以下**不在当前两个阶段范围内**：
- `cowboy dev`（完整版）/ `cowboy test`
- Runner mocking / Block advancement
- 状态快照断言
- 确定性检查（跨平台）
- PoS 实现（取决于 ED25519 调研结果）
- AI Context 文件（SKILL.md、.cursorrules）——在 SDK 完成后

---

## 七、沟通策略

### 需传达的关键信息

1. **"基础设施非常扎实"**——42 个 Rust crate，共识→执行→VM→Runner 全链路可运行，Martin 已在 devnet 上端到端部署 Actor。

2. **"差距在开发者体验层，而非协议层"**——`init`/`dev`/`test`/`logs` 等 CLI 命令是新的表面功能，而非核心功能缺失。pvm-simulator 已为 `cowboy dev` 提供技术基础。

3. **"我们有具体的冲刺计划和每周交付物"**——不是笼统的承诺，而是具体到每项都有 GitHub Issue 和定期 Demo。

4. **"我们在主动披露技术差异"**——PoS、签名方案、白皮书差距。透明建立信任。

### 应当避免的

- ❌ 不要说"我们一直在做底层的难活"——听起来像借口
- ❌ 不要用代码量作为进度指标——客户关心的是可用性
- ❌ 不要对所有需求都说"会做"——对 P2/P3 的需求明确说明"后续阶段"并附理由
- ❌ 不要在 Slack 上长篇大论——简短回复 + 文档链接

### 建议沟通节奏

- **每周两次同步**（周二/周四，30 分钟）与 Tony + Martin
- **双周 Demo**：向客户展示最新可用功能
- **GitHub Issues 作为唯一信息源**：全部承诺的交付物公开跟踪

---

## 八、风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 客户看到 67% "未开始"而失去信心 | 高 | 高 | 以架构全景图 + 隐藏优势引领；将 DX 定位为"增量"而非"缺失" |
| ED25519→secp256k1 迁移不可行 | 中 | 关键 | 立即研究；尽早告知客户约束条件 |
| Phase 2 范围过载（DX + UI + 基础设施压缩在 3 周内） | 高 | 中 | DX 优先于 UI；Cowchat/Explorer 可延后 |
| 客户在阶段中途变更范围（Patrick 的新想法） | 中 | 中 | 确认想法；明确延迟至后续阶段 |
| 团队因追赶冲刺而过劳 | 中 | 高 | 合理规划范围；不要承诺所有需求 |

---

## 附录：来源交叉索引

| 发现 | 来源 |
|------|------|
| Public vs Private Devnet 时间线 | 会议 1（2/11），DevEx 文档 |
| PoS 缺失 | 会议 3（2/18），白皮书 §共识 |
| ED25519 vs secp256k1 | 会议 3（2/18），白皮书 §账户管理 |
| 客户低估 Runner 复杂度 | 会议 2（2/18），白皮书 §Runners |
| 客户规划文档"仓促编写" | 会议 2（2/18） |
| Tony 询问 CIP-21 | Slack：Charles_DePue_patrick_Tony.md |
| Martin devnet 部署验证 | Slack：devnet_eng.md |
| SimulatedChain 纳入 Phase 2 范围 | 会议 3（2/18）—— Tony 确认 |
| CIP-8 → CIP-2 更新决定 | 会议 2（2/18） |
| Demo 应用缩减至 llm_chat + deferred_counter_demo | 会议 2（2/18） |
