# Cowboy 开发进展与 DevEx 反馈

**日期**：2026年2月19日

---

## 一、我们过去在做什么

过去一个半月，我们团队全力聚焦在 Cowboy 主链（Node）、PVM 和 Runner 网络的核心开发上。基于 Python 的 PVM 和跨区块执行 transaction 的技术方案在市面上没有先例，所有的研发都是从零开始。目前三个核心模块都已经打下了比较扎实的基础，在底层技术开发过程中为了功能的完整性，我们也实现了一些额外的功能（延迟交易、CREATE2 地址派生、N-of-M 结果验证、TEE 支持等）。并且实现了两个 DEMO 来验证代码的有效性。

实际上，**开发者编写一个 Python Actor → 部署到 Devnet → 调用执行 → 查询结果**这个核心业务流程，我们的开发团队在内部已经反复实现和测试过，整个流程是跑通的，没有问题。我们的 CLI 已经实现了 `actor deploy`、`actor execute`、`account balance/nonce/info`、`transaction get/status` 等完整链路，RPC API 也提供了 25+ 个端点覆盖所有链上操作。

但对于外部的第三方开发者来说，目前还缺少一个好的界面、工具和操作路径来引导他们顺畅地完成这个流程。所以我们接下来的重点工作，就是**怎样用好的交互方式，让第三方开发者能够快速了解 Cowboy、并顺利完成这个核心业务流程**——包括 `cowboy init` 生成项目模板、SDK 装饰器简化代码编写、友好的错误提示辅助调试、入门文档引导上手等。

我们已经把目前已实现的全部功能整理成了一份**架构概览文档**，供大家参考。

---

## 二、DevEx 需求清单逐项反馈

我们仔细 review 了 Slack 里的每一条消息，以及 Notion 上的 Devnet Milestone、Developer Experience 规划文档和所有产品讨论。我们把已实现的功能和需求逐个进行了对照，以下是针对 Devnet Milestone 中 DevEx 清单的逐项反馈。

> **说明**：以下反馈中的优先级判断和时间安排都是我们基于当前理解给出的初步建议，**完全可以一起商量调整**。如果有任何我们理解不准确或者遗漏的地方，也请随时指出，我们及时修正。

### CLI

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 1 | Shell script to install from GitHub | 📋 待确认 | 需要确认分发方式和目标平台 |
| 2 | Pre-built CLI binary distribution | 📋 待确认 | 需要确认分发渠道（GitHub Release？Homebrew？） |
| 3 | `cowboy init`（脚手架 + 模板） | 🔜 计划开发 | 我们评估后认为可以实现，将支持项目模板生成 |
| 4 | `cowboy dev`（本地开发服务器） | ⏸️ 下个里程碑 | 本地开发环境涉及模拟链的维护，目前链的迭代速度很快，维护两套环境成本较高。我们计划在下个里程碑中以 SimulatedChain 的方式提供本地开发能力 |
| 5 | `cowboy test`（模拟 PVM 测试） | ⏸️ 下个里程碑 | 与本地开发环境关联，需要 SimulatedChain 作为基础，计划下个里程碑实现 |
| 6 | `cowboy actor deploy` | ✅ 已实现 | 支持部署 Python Actor 到 Devnet，包含 CREATE2 地址派生、gas 配置等 |
| 7 | `cowboy actor logs` | 🔜 计划开发 | 我们评估后认为可以实现，日志将存储在链的数据库中，CLI 通过 RPC 查询 |
| 8 | `cowboy wallet` create | 📋 待确认 | Devnet Milestone 中有列出，想确认一下具体需要支持哪些钱包功能？ |
| 9 | Account balance/nonce/info | ✅ 已实现 | CLI 已支持 `account balance`、`account nonce`、`account info` 三个命令 |

### SDK

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 10 | Full type annotations (PEP 484) + `.pyi` stubs | 🔜 计划开发 | PVM 底层已有 pvm_sdk 模块（actor、runner、continuation 等 10 个模块），需要补充完整的类型标注和 .pyi stubs |
| 11 | Ergonomic decorators (`@actor`, `@runner.continuation`, `@timer`) | 🔜 计划开发 | PVM 底层逻辑已支持这些功能，目前 Actor 代码中以硬编码方式实现，需要封装为装饰器形式呈现在 SDK 中 |

### Error Messages

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 12 | Four-part error format (what, why, fix, link) | 🔜 计划开发 | 认同这个方向，也有助于我们自身的调试效率 |
| 13 | Common error mapping table in PVM | 🔜 计划开发 | 目前有部分错误映射，需要扩充覆盖更多常见场景 |

### AI Context

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 14 | Skills for Claude/Codex/OpenClaw | ⏸️ SDK 完成后 | 我们认为这个想法非常好，但内部评估后认为应该在 SDK 定型之后再开发，否则 SDK 变动时 Skills 也需要反复修改 |
| 15 | `.cursorrules` in `cowboy init` output | ⏸️ SDK 完成后 | 同上，依赖 SDK 稳定 |
| 16 | `llms.txt` at docs domain root | ⏸️ SDK 完成后 | 同上 |

### 其他

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 17 | Initial getting started guide + example actors | 🔜 部分就绪 | 目前有 2 个可运行的 Demo（llm_chat、deferred_counter_demo），入门指南需要新编写，想确认一下期望的深度和格式 |
| 18 | pvm_host API docs | 📋 待确认 | 需要确认文档的目标受众和覆盖范围 |
| 19 | SDK on PyPI/npm | 📋 待确认 | SDK 封装完成后可以发布，需要确认包名和版本策略 |
| 20 | Core examples compile | ⚠️ 部分就绪 | 目前保留 llm_chat 和 deferred_counter_demo 两个核心示例 |

### 状态图例

| 符号 | 含义 |
|------|------|
| ✅ | 已实现 — 当前代码库中已可使用 |
| 🔜 | 计划开发 — 评估可行，将进行开发 |
| ⏸️ | 延期 — 推迟至下个里程碑或等待前置依赖 |
| 📋 | 待确认 — 需要你们的输入来明确范围或需求 |
| ⚠️ | 部分就绪 — 已有部分工作，需要补充完善 |

---

## 三、需要讨论的技术问题

在 review 的过程中，我们发现有一些技术层面的问题需要和大家一起讨论确认：

- **签名方案**：白皮书中指定使用 secp256k1（与以太坊兼容），目前我们的实现使用的是 ED25519。如果以太坊兼容性是一个硬性要求，我们需要评估迁移方案。

- **功能优先级**：部分需求之间存在依赖关系（例如 AI Context 依赖 SDK 稳定），想和大家确认一下整体的优先级排序。


---

## 四、关于使用场景的探讨

最后，我们想跟大家探讨一下 Devnet 第一个版本上线后的核心使用场景。

根据我们对 Slack 讨论内容和 Notion 文档的理解，我们判断目前的核心场景是：

> **让一个开发者能够在最短的时间内，从零开始搭建开发环境，并成功部署和调用一个 Actor 到 Devnet 上。**

也就是一个完整的 **安装 → 初始化 → 编写 → 部署 → 交互** 的端到端流程。

好消息是，这个流程我们的开发团队在内部已经反复跑通和验证过了——编写 Actor、部署、调用、查询结果，整条链路没有问题。我们接下来要解决的核心问题是：**怎样把这个已经验证过的能力，用好的工具、界面和操作路径呈现给第三方开发者**，让他们也能快速上手、顺畅完成整个流程。这就是我们下一阶段 DevEx 工作的核心方向。

如果这个理解是准确的，我们就会围绕这个场景来针对性地安排开发优先级，确保每一个环节都能顺畅地跑通。

同时我们也很想了解，除了这个场景之外，还有没有其他你们特别关注的使用场景或商业目标？比如：

- 是否有特定类型的 Actor 需要优先支持？（如量化交易、oracle、AI agent 等）
- 是否需要优先支持某些外部集成？（如钱包对接、OpenClaw 集成等）
- Devnet 上线后的早期用户定位是什么？（内部测试？投资人演示？开发者公测？）

了解这些场景能帮助我们更精准地对齐开发方向，围绕真正有价值的场景来安排优先级。

---

期待大家的反馈！
