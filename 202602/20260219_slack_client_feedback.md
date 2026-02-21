# Slack 客户反馈草稿

> 以下为发送给客户的 Slack 消息草稿，分为主消息和跟帖。

---

## 主消息

Hi team 👋

跟大家同步一下我们的进展、对 DevEx 需求清单的逐项反馈，以及一些我们希望一起讨论的问题。

---

### 一、我们过去在做什么

过去一个半月，我们团队全力聚焦在 Cowboy 主链（Node）、PVM 和 Runner 网络的核心开发上。基于 Python 的 PVM 和跨区块执行 transaction 的技术方案在市面上没有先例，所有的研发都是从零开始。目前三个核心模块都已经打下了比较扎实的基础，在底层技术开发过程中为了功能的完整性，我们也实现了一些额外的功能（延迟交易、CREATE2 地址派生、N-of-M 结果验证、TEE 支持等）。并且实现了两个 DEMO 来验证代码的有效性。

实际上，**开发者编写一个 Python Actor → 部署到 Devnet → 调用执行 → 查询结果**这个核心业务流程，我们的开发团队在内部已经反复实现和测试过，整个流程是跑通的，没有问题。我们的 CLI 已经实现了 `actor deploy`、`actor execute`、`account balance/nonce/info`、`transaction get/status` 等完整链路，RPC API 也提供了 25+ 个端点覆盖所有链上操作。但对于外部的第三方开发者来说，目前还缺少一个好的界面、工具和操作路径来引导他们顺畅地完成这个流程。所以我们接下来的重点工作，就是**怎样用好的交互方式，让第三方开发者能够快速了解 Cowboy、并顺利完成这个核心业务流程**——包括 `cowboy init` 生成项目模板、SDK 装饰器简化代码编写、友好的错误提示辅助调试、入门文档引导上手等。

我们已经把目前已实现的全部功能整理成了一份架构概览文档（见附件），供大家参考。

---

### 二、DevEx 需求清单逐项反馈

我们仔细 review 了 Slack 里的每一条消息，以及 Notion 上的 Devnet Milestone、Developer Experience 规划文档和所有产品讨论。我们把已实现的功能和需求逐个进行了对照，以下是针对 Devnet Milestone 中 DevEx 清单的逐项反馈。

以下反馈中的优先级判断和时间安排都是我们基于当前理解给出的初步建议，**完全可以一起商量调整**。如果有任何我们理解不准确或者遗漏的地方，也请随时指出，我们及时修正 🙏

#### CLI

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 1 | Shell script to install from GitHub | 📋 待确认 | 需要确认分发方式和目标平台 |
| 2 | Pre-built CLI binary distribution | 📋 待确认 | 需要确认分发渠道（GitHub Release？Homebrew？） |
| 3 | `cowboy init` (scaffolding with templates) | 🔜 计划开发 | 我们评估后认为可以实现，将支持项目模板生成 |
| 4 | `cowboy dev` (local development server) | ⏸️ 下个里程碑 | 本地开发环境涉及模拟链的维护，目前链的迭代速度很快，维护两套环境成本较高。我们计划在下个里程碑中以 SimulatedChain 的方式提供本地开发能力 |
| 5 | `cowboy test` (testing against simulated PVM) | ⏸️ 下个里程碑 | 与本地开发环境关联，需要 SimulatedChain 作为基础，计划下个里程碑实现 |
| 6 | `cowboy actor deploy` | ✅ 已实现 | 支持部署 Python Actor 到 Devnet，包含 CREATE2 地址派生、gas 配置等 |
| 7 | `cowboy actor logs` | 🔜 计划开发 | 我们评估后认为可以实现，日志将存储在链的数据库中，CLI 通过 RPC 查询 |
| 8 | `cowboy wallet` create | 📋 待确认 | Devnet Milestone 中有列出，想确认一下具体需要支持哪些钱包功能？ |
| 9 | Account balance/nonce/info | ✅ 已实现 | CLI 已支持 `account balance`、`account nonce`、`account info` 三个命令 |

#### SDK

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 10 | Full type annotations (PEP 484) + `.pyi` stubs | 🔜 计划开发 | PVM 底层已有 pvm_sdk 模块（actor、runner、continuation 等 10 个模块），需要补充完整的类型标注和 .pyi stubs |
| 11 | Ergonomic decorators (`@actor`, `@runner.continuation`, `@timer`) | 🔜 计划开发 | PVM 底层逻辑已支持这些功能，目前 Actor 代码中以硬编码方式实现，需要封装为装饰器形式呈现在 SDK 中 |

#### Error Messages

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 12 | Four-part error format (what, why, fix, link) | 🔜 计划开发 | 认同这个方向，也有助于我们自身的调试效率 |
| 13 | Common error mapping table in PVM | 🔜 计划开发 | 目前有部分错误映射，需要扩充覆盖更多常见场景 |

#### AI Context

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 14 | Skills for Claude/Codex/OpenClaw | ⏸️ SDK 完成后 | 我们认为这个想法非常好，但内部评估后认为应该在 SDK 定型之后再开发，否则 SDK 变动时 Skills 也需要反复修改 |
| 15 | `.cursorrules` in `cowboy init` output | ⏸️ SDK 完成后 | 同上，依赖 SDK 稳定 |
| 16 | `llms.txt` at docs domain root | ⏸️ SDK 完成后 | 同上 |

#### 其他

| # | 需求 | 状态 | 说明 |
|---|------|------|------|
| 17 | Initial getting started guide + example actors | 🔜 部分就绪 | 目前有 2 个可运行的 Demo（llm_chat、deferred_counter_demo），入门指南需要新编写，想确认一下期望的深度和格式 |
| 18 | pvm_host API docs | 📋 待确认 | 需要确认文档的目标受众和覆盖范围 |
| 19 | SDK on PyPI/npm | 📋 待确认 | SDK 封装完成后可以发布，需要确认包名和版本策略 |
| 20 | Core examples compile | ⚠️ 部分就绪 | 目前保留 llm_chat 和 deferred_counter_demo 两个核心示例 |

---

### 三、一些需要讨论的技术问题

在 review 的过程中，我们发现有一些技术层面的问题需要和大家一起讨论确认：

- **签名方案**：白皮书中指定使用 secp256k1（与以太坊兼容），目前我们的实现使用的是 ED25519。如果以太坊兼容性是一个硬性要求，我们需要评估迁移方案
- **功能优先级**：部分需求之间存在依赖关系（例如 AI Context 依赖 SDK 稳定），想和大家确认一下整体的优先级排序
- **白皮书与当前实现的差异**：我们整理了一份白皮书和现有代码的对比分析，有一些差异点需要共同确认方向是否正确

我们会把详细的问题清单整理好后发到 Slack，到时候请大家帮忙确认和讨论。

---

### 四、关于使用场景的探讨

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

期待大家的反馈！🙏

---

## 跟帖附件

**跟帖 1**：📊 已实现代码功能全景图（贴全景图）

**跟帖 2**：📎 架构概览文档（附 Architecture Overview 文件）

**跟帖 3**：📋 白皮书 vs 代码对比分析（后续发出）

---
---

# Slack Client Feedback Draft (English Version)

> The following is the English version of the Slack message draft, consisting of a main message and thread replies.

---

## Main Message

Hi team 👋

Here's an update on our progress, item-by-item feedback on the DevEx requirements list, and some topics we'd like to discuss together.

---

### 1. What We've Been Working On

Over the past six weeks, our team has been fully focused on the core development of the Cowboy chain (Node), PVM, and Runner network. The Python-based PVM and cross-block transaction execution approach have no precedent in the market — everything was built from scratch. All three core modules now have a solid foundation, and during the development process we also implemented several additional features for completeness (deferred transactions, CREATE2 address derivation, N-of-M result verification, TEE support, etc.). We also built two working demos to validate the code's effectiveness.

In fact, the core business flow of **a developer writing a Python Actor → deploying it to Devnet → executing calls → querying results** has already been repeatedly implemented and tested internally by our development team — the entire pipeline works end-to-end without issues. Our CLI already supports `actor deploy`, `actor execute`, `account balance/nonce/info`, `transaction get/status` and other complete workflows, and our RPC API provides 25+ endpoints covering all on-chain operations. However, for external third-party developers, there is currently a lack of good interfaces, tools, and guided pathways to help them complete this flow smoothly. So our next priority is **how to present this proven capability to third-party developers through great tooling and interaction design** — including `cowboy init` for project scaffolding, SDK decorators to simplify code writing, friendly error messages for debugging, and getting-started documentation for onboarding.

We've compiled all currently implemented features into an Architecture Overview document (see attachment) for your reference.

---

### 2. Item-by-Item Feedback on the DevEx Requirements List

We've carefully reviewed every message in Slack, as well as the Devnet Milestone, Developer Experience planning documents, and all product discussions on Notion. We've cross-referenced each requirement against our current implementation, and below is our item-by-item feedback on the DevEx checklist in the Devnet Milestone.

Please note that the priority assessments and timelines below are our initial recommendations based on our current understanding — **they are absolutely open for discussion and adjustment**. If there's anything we've misunderstood or overlooked, please don't hesitate to let us know and we'll correct it right away 🙏

#### CLI

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 1 | Shell script to install from GitHub | 📋 To Confirm | Need to confirm distribution method and target platforms |
| 2 | Pre-built CLI binary distribution | 📋 To Confirm | Need to confirm distribution channel (GitHub Release? Homebrew?) |
| 3 | `cowboy init` (scaffolding with templates) | 🔜 Planned | We've assessed this and believe it's feasible — will support project template generation |
| 4 | `cowboy dev` (local development server) | ⏸️ Next Milestone | Local dev environment requires maintaining a simulated chain. Given the fast iteration pace of our chain, maintaining two environments is costly. We plan to provide local dev capability via SimulatedChain in the next milestone |
| 5 | `cowboy test` (testing against simulated PVM) | ⏸️ Next Milestone | Depends on the local dev environment; requires SimulatedChain as a foundation. Planned for next milestone |
| 6 | `cowboy actor deploy` | ✅ Implemented | Supports deploying Python Actors to Devnet, including CREATE2 address derivation, gas configuration, etc. |
| 7 | `cowboy actor logs` | 🔜 Planned | We've assessed this and believe it's feasible. Logs will be stored in the chain's database, queried via RPC through CLI |
| 8 | `cowboy wallet` create | 📋 To Confirm | Listed in the Devnet Milestone — could you clarify what specific wallet features are needed? |
| 9 | Account balance/nonce/info | ✅ Implemented | CLI already supports `account balance`, `account nonce`, and `account info` commands |

#### SDK

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 10 | Full type annotations (PEP 484) + `.pyi` stubs | 🔜 Planned | PVM already has pvm_sdk modules (actor, runner, continuation, etc. — 10 modules). Need to add complete type annotations and .pyi stubs |
| 11 | Ergonomic decorators (`@actor`, `@runner.continuation`, `@timer`) | 🔜 Planned | PVM's underlying logic already supports these features. Currently implemented via hardcoding in Actor code — need to wrap as decorators in the SDK |

#### Error Messages

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 12 | Four-part error format (what, why, fix, link) | 🔜 Planned | We agree with this direction — it will also improve our own debugging efficiency |
| 13 | Common error mapping table in PVM | 🔜 Planned | Partial error mapping exists; needs expansion to cover more common scenarios |

#### AI Context

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 14 | Skills for Claude/Codex/OpenClaw | ⏸️ After SDK | We think this is a great idea, but after internal assessment we believe it should be developed after the SDK is finalized — otherwise Skills would need repeated updates as the SDK changes |
| 15 | `.cursorrules` in `cowboy init` output | ⏸️ After SDK | Same as above — depends on SDK stability |
| 16 | `llms.txt` at docs domain root | ⏸️ After SDK | Same as above |

#### Other

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 17 | Initial getting started guide + example actors | 🔜 Partially Ready | We currently have 2 working demos (llm_chat, deferred_counter_demo). The getting started guide needs to be written — could you share your expectations on depth and format? |
| 18 | pvm_host API docs | 📋 To Confirm | Need to confirm the target audience and scope of the documentation |
| 19 | SDK on PyPI/npm | 📋 To Confirm | Can be published once SDK packaging is complete — need to confirm package name and versioning strategy |
| 20 | Core examples compile | ⚠️ Partially Ready | Currently maintaining llm_chat and deferred_counter_demo as the two core examples |

---

### 3. Technical Questions for Discussion

During our review, we identified several technical questions that need to be discussed and confirmed together:

- **Signature scheme**: The whitepaper specifies secp256k1 (Ethereum-compatible), but our current implementation uses ED25519. If Ethereum compatibility is a hard requirement, we need to evaluate a migration plan
- **Feature prioritization**: Some requirements have dependencies (e.g., AI Context depends on a stable SDK). We'd like to confirm the overall priority ordering with the team
- **Whitepaper vs. current implementation differences**: We've prepared a comparison analysis between the whitepaper and our existing code. There are some discrepancies that we need to jointly confirm whether the direction is correct

We'll compile a detailed list of questions and post them in Slack for everyone to review and discuss.

---

### 4. Discussion on Target Use Cases

Lastly, we'd like to explore the core use case for the first version of Devnet after it goes live.

Based on our review of Slack discussions and Notion documents, we believe the current core use case is:

> **Enable a developer to set up their development environment from scratch in the shortest time possible, and successfully deploy and interact with an Actor on Devnet.**

In other words, a complete **Install → Initialize → Write → Deploy → Interact** end-to-end flow.

The good news is that our development team has already repeatedly run and validated this flow internally — writing an Actor, deploying it, calling it, querying results — the entire pipeline works without issues. The core question we need to solve next is: **how to present this proven capability to third-party developers through great tools, interfaces, and guided pathways**, so they can also get started quickly and complete the flow smoothly. This is the core direction of our DevEx work in the next phase.

If this understanding is accurate, we'll prioritize development around this use case to ensure every step of the flow works seamlessly.

We'd also love to learn whether there are other use cases or business goals you're particularly focused on beyond this. For example:
- Are there specific types of Actors that need priority support? (e.g., quantitative trading, oracle, AI agent, etc.)
- Are there external integrations that should be prioritized? (e.g., wallet integration, OpenClaw integration, etc.)
- What is the target audience for Devnet after launch? (Internal testing? Investor demos? Developer public beta?)

Understanding these scenarios will help us align our development direction more precisely and prioritize around the use cases that truly matter.

Looking forward to your feedback! 🙏

---

## Thread Attachments

**Thread 1**: 📊 Implemented Code Panorama (attach panorama diagram)

**Thread 2**: 📎 Architecture Overview document (attach Architecture Overview file)

**Thread 3**: 📋 Whitepaper vs. Code comparison analysis (to follow)

