# Developer Experience Situational Awareness — Review Comments

---

## 🇬🇧 English Version

### CLI

| Item | Status | Comment |
|------|--------|---------|
| `cowboy dev` | P0 | Thank you for including this — we fully agree that a local dev loop is important long-term. At this stage, however, our DevNet Node operates as a real networked environment with live consensus and P2P communication. Building a faithful local simulation would require significant effort and could introduce behavioral divergences that confuse developers. We'd suggest revisiting this topic for discussion at a more appropriate time once the node architecture stabilizes. |
| `cowboy test` | P0 | Similarly, without a local development environment in place, a local test runner isn't feasible yet. In the meantime, developers can test directly against the DevNet. We plan to address this when local development becomes viable. |
| `cowboy actor logs` | P0 | **Planned for implementation.** We'll add logging support in the Node, with logs written to the on-chain database. This approach naturally supports multi-node synchronization — any node can serve consistent log data. |
| `cowboy secrets` | P1 | This is a great idea and we'd love to support it in the future. It's not part of the current milestone scope, but we'll keep it on the roadmap. |
| `cowboy cost` | P1 | Agreed this would be very useful. It requires transaction simulation capability (similar to Solana's `simulateTransaction`), which is on our roadmap but not scoped for this phase. We'll prioritize it in an upcoming iteration. |

### Local Development (entire section)

| Item | Status | Comment |
|------|--------|---------|
| **All items** | P0 | We appreciate the thorough thinking here. After careful consideration, we believe Phase 1 is not the right time to implement local development. The Cowboy DevNet Node is a full-featured networked system with real consensus, P2P communication, and distributed Runner coordination. Creating a lightweight local PVM that faithfully replicates all of these behaviors is not practical at this stage and would risk introducing subtle divergences that could mislead developers. We recommend developers work directly on the public DevNet for now, and we'd suggest revisiting this topic for discussion at a more appropriate time in the future. |

### SDK

| Item | Status | Comment |
|------|--------|---------|
| Full type annotations + `.pyi` stubs | Partial | We have partial coverage in place and are actively expanding it as the SDK API stabilizes. Once we've accumulated enough real-world usage patterns and the API surface is well-defined, we'll ship complete stub files. |
| Ergonomic decorators (`@actor`, etc.) | Minimal | The core decorator infrastructure exists. We're intentionally holding off on expanding the decorator API until we have more example actors — this avoids premature abstraction that would require rework as patterns evolve. We fully plan to enrich this as the SDK matures. |
| PVM-safe helpers (vrf, time, math) | — | Great news — these are **already implemented** at the PVM level: VRF (deterministic randomness via chain beacon), time (block-height-based timestamps), and math (softfloat deterministic arithmetic with overflow protection). We'd be happy to provide concrete examples. Could you let us know what specific helper APIs you'd envision beyond what the PVM already provides? |
| Watchtower client | P1 | Not yet implemented. Watchtower is planned for a future milestone. We'll keep you updated on the timeline. |
| Correlation ID / timeout handling helpers | P1 | We'd love to get this right — could you share more about the specific use cases and developer workflows you have in mind for timeout handling? This will help us provide the most practical and useful helper utilities. |

### Testing

| Item | Status | Comment |
|------|--------|---------|
| SimulatedChain with in-memory PVM | P0 | We previously had a mock chain for this purpose, but given the rapid pace of Node development, maintaining two parallel environments became impractical. The simulated chain quickly fell out of sync with the real node. We plan to revisit this once the node architecture reaches a more stable state. |
| Block advancement and timer triggering | P0 | This is closely tied to the SimulatedChain — without a local simulation, we can't force-advance blocks on the public DevNet. We fully understand the value of this for developer debugging and will address it alongside local development tooling. |
| Runner mocking with conditional responses | P0 | Same consideration — mocking depends on the local simulation environment. As a workaround, developers can currently create a dedicated actor or runner on DevNet to generate test messages for integration testing. |
| State snapshot assertions | P0 | This feature is designed primarily for local testing scenarios. Without the SimulatedChain, snapshot-based assertions aren't applicable in the current architecture. We'll include this when local testing is implemented. |

### Error Messages

| Item | Status | Comment |
|------|--------|---------|
| Four-part error format | P0 | **We agree and plan to implement this.** The four-part format (what happened / why / suggested fix / docs link) is excellent for developer experience and retention. This is a high-value, achievable improvement. |
| Common error mapping table | P0 | **Planned for implementation.** We'll provide a comprehensive mapping covering forbidden imports, non-deterministic operations, and their PVM-safe alternatives. |

### Additional Work Completed (beyond this checklist)

| Item | Comment |
|------|---------|
| **Runner Distributed System** | We'd like to highlight that beyond the items in this checklist, we have built a comprehensive distributed Runner system. This includes: runner registration & discovery, a bid/quote mechanism, Dual-Metered Gas (Cycles + Cells) billing, result verification during chain replay, secure key management, inter-node data synchronization, and support for MCP/LLM/HTTP job execution. This is a production-grade distributed system — we'll be publishing a dedicated CIP to describe the architecture in detail. |
| **System Actors** | We've implemented a full suite of System Actors that are not reflected in this checklist, including: Timer system actor, Job Dispatcher, Result Parser, and Job Assignment actor. These are critical on-chain infrastructure components managing the full lifecycle of timers, runner jobs, and result processing. |
| **Additional CLI Commands** | Already implemented beyond the checklist: `cowboy runner get/list/register`, `cowboy job get/status/runners/results/verified/submit`, and `cowboy transfer`. |
| **SDK Infrastructure** | The Context Manager and JSON-RPC Client are fully implemented in the SDK. We've also developed a comprehensive set of RPC interfaces for querying deferred transactions, timer-generated jobs, and other on-chain state. |

---

## 🇨🇳 中文版本

### CLI

| 条目 | 状态 | 评论内容 |
|------|------|---------|
| `cowboy dev` | P0 | 感谢提出这一项——我们完全认同本地开发循环在长期来看非常重要。不过在当前阶段，我们的 DevNet Node 是一个具备真实共识和 P2P 通讯的网络环境，构建一个能忠实模拟这些行为的本地环境需要大量投入，且可能引入行为差异给开发者造成困惑。我们建议在节点架构稳定后的未来合适时间再来讨论这一功能。 |
| `cowboy test` | P0 | 同理，在本地开发环境尚未建立的情况下，本地测试运行器暂时不具备实现条件。目前开发者可以直接在 DevNet 上进行测试，待本地开发环境可行时我们会一并解决。 |
| `cowboy actor logs` | P0 | **计划实现。** 我们将在 Node 中增加日志功能，日志写入链上数据库，天然支持多节点同步——任何节点都能提供一致的日志数据。 |
| `cowboy secrets` | P1 | 这是个很好的想法，我们未来很希望支持。当前里程碑暂未纳入，但已记录在路线图中。 |
| `cowboy cost` | P1 | 认同这个功能非常有用。它需要交易模拟能力（类似 Solana 的 `simulateTransaction`），已在我们的规划中，但未纳入本阶段范围。会在后续迭代中优先考虑。 |

### Local Development（整个章节）

| 条目 | 状态 | 评论内容 |
|------|------|---------|
| **所有条目** | P0 | 感谢对本地开发环境的详细规划。经过仔细评估，我们认为 Phase 1 还不是实现本地开发的合适时机。Cowboy DevNet Node 是一个具备真实共识、P2P 通讯和分布式 Runner 协调能力的完整网络系统，在当前阶段构建一个能忠实复现所有这些行为的轻量本地 PVM 不太现实，且可能引入细微的行为差异误导开发者。建议开发者先在 Public DevNet 上直接开发，我们建议在未来合适的时间再来讨论本地开发工具。 |

### SDK

| 条目 | 状态 | 评论内容 |
|------|------|---------|
| Full type annotations + `.pyi` stubs | Partial | 已有部分覆盖，正在随着 SDK API 的稳定持续扩展。等积累了足够的实际使用模式、API 设计明确后，会提供完整的 stub 文件。 |
| Ergonomic decorators（`@actor` 等） | Minimal | 核心装饰器基础设施已经具备。我们有意等积累更多的 example actor 后再扩展装饰器 API，避免过早抽象导致后续变更时大量返工。随着 SDK 成熟，我们会全面丰富这部分。 |
| PVM-safe helpers (vrf, time, math) | — | 好消息——这些**已经在 PVM 层面实现了**：VRF（通过链信标的确定性随机数）、time（基于区块高度的时间戳）、math（softfloat 确定性算术，含溢出保护）。我们很乐意提供具体示例。请问您期望的具体 helper 是怎样的？是否有超出 PVM 已有能力的需求？ |
| Watchtower client | P1 | 尚未实现，Watchtower 计划在未来里程碑中实现，会及时同步进展。 |
| Correlation ID / timeout handling helpers | P1 | 我们希望把这个做好——能否分享一下您设想的具体使用场景和开发者工作流？这将帮助我们提供最实用的辅助工具。 |

### Testing

| 条目 | 状态 | 评论内容 |
|------|------|---------|
| SimulatedChain with in-memory PVM | P0 | 我们之前确实有一个用于此目的的 mock chain，但由于 Node 开发迭代极快，维护两套并行环境变得不太现实——模拟链很快就与真实节点脱节了。计划在节点架构进入更稳定状态后重新考虑。 |
| Block advancement and timer triggering | P0 | 这与 SimulatedChain 紧密关联——没有本地模拟环境，无法在 Public DevNet 上强制推进区块。我们完全理解这对开发者调试的价值，会在本地开发工具一并解决。 |
| Runner mocking with conditional responses | P0 | 同样的考量——Mock 功能依赖本地模拟环境。作为临时方案，开发者可以在 DevNet 上创建专用的 actor 或 runner 来生成测试消息进行集成测试。 |
| State snapshot assertions | P0 | 此功能主要为本地测试场景设计，在没有 SimulatedChain 的情况下暂不适用。待本地测试环境实现时一并提供。 |

### Error Messages

| 条目 | 状态 | 评论内容 |
|------|------|---------|
| Four-part error format | P0 | **认同并计划实现。** 四段式错误格式（发生了什么/为什么/建议做法/文档链接）对开发者体验和留存非常有价值，是一个高收益且可达成的改进。 |
| Common error mapping table | P0 | **计划实现。** 将提供全面的错误映射表，覆盖禁止的 import、非确定性操作及其 PVM 安全替代方案。 |

### 额外已完成的工作（清单之外）

| 条目 | 评论内容 |
|------|---------|
| **Runner 分布式系统** | 我们希望特别说明：在此清单之外，我们已构建了一套完整的分布式 Runner 系统，包括：Runner 注册与发现机制、竞价/报价系统、双重计量 Gas（Cycles + Cells）计费、链回放时的结果验证（Verify）、安全密钥管理、节点间数据同步与通讯、MCP/LLM/HTTP 作业执行支持。这是一个生产级的分布式系统，我们将发布专门的 CIP 文档来详细描述其架构。 |
| **System Actors** | 我们已实现了清单未涵盖的完整 System Actor 套件，包括：Timer system actor、Job Dispatcher（任务分发器）、Result Parser（结果解析器）、Job Assignment actor（任务分配器）。这些是管理链上 timer 生命周期、runner 作业和结果处理的核心基础设施组件。 |
| **额外 CLI 命令** | 清单之外已实现：`cowboy runner get/list/register`、`cowboy job get/status/runners/results/verified/submit`、`cowboy transfer`。 |
| **SDK 基础设施** | Context Manager 和 JSON-RPC Client 已在 SDK 中完整实现。此外还开发了一组完善的 RPC 接口，可查询 Deferred Transaction、Timer 产生的 Job 等链上状态。 |
