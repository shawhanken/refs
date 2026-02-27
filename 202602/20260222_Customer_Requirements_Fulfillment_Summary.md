# 客户需求 vs 我方满足情况 汇总表

> 数据来源：4份会议记录（2/11 x2, 2/18, 2/21）+ Slack devnet-eng 频道近12天消息

---

## 一、CLI 工具

| # | 客户需求 | 优先级 | 我方状态 | 备注 |
|---|---------|--------|---------|------|
| 1 | `cowboy init` (脚手架模板) | P0 | ❌ 未实现 | 依赖 SDK 完成后才能做；需调用 SDK |
| 2 | `cowboy dev` (本地开发服务器) | P0 | ❌ 不做 | 会议决议：Phase1 不做 |
| 3 | `cowboy test` (本地测试) | P0 | ❌ 不做 | 会议决议：Phase1 不做 |
| 4 | `cowboy actor logs` (查看日志) | P0 | 🟡 可做 | 可写入链上数据库；需内部对齐 log 存储方案 |
| 5 | `cowboy secrets` (密钥管理) | - | ❌ 无 | 当前无此功能 |
| 6 | `cowboy cost` (交易成本估算) | - | ❌ 未实现 | 计划中但未在此阶段实现；模拟 transaction 费用机制尚无 |
| 7 | CLI 部署 Actor | P0 | ✅ 已实现 | 命令行部署 Actor 完全可用 |

---

## 二、SDK & 开发体验

| # | 客户需求 | 优先级 | 我方状态 | 备注 |
|---|---------|--------|---------|------|
| 8 | Full type annotations (PEP 484) + .pyi stubs | P0 | 🟡 部分 | PVM 底层支持，但 SDK 层未封装暴露 |
| 9 | Ergonomic decorators (@actor, @runner.continuation, @timer) | P0 | 🟡 最小化 | PVM 底层逻辑已支持，但未以装饰器形式呈现；当前为"伪实现"——语义层面可用但底层不真正执行约束 |
| 10 | PVM-safe helpers (vrf, time, math) | P0 | ✅ 已实现 | time、VRF、math（防溢出）均已实现 |
| 11 | Watchtower client | P0 | ❌ 无 | 未实现 |
| 12 | Correlation ID & timeout handling helpers | P0 | ❓ 待确认 | 需问客户具体需求 |
| 13 | SDK 整体封装 | 关键 | ❌ 未完成 | PVM 未定型 + 状态机（FSM）未实现前做 SDK 有风险；但客户强烈要求，已决定推进 |

---

## 三、本地开发环境 (Local Development)

| # | 客户需求 | 优先级 | 我方状态 | 备注 |
|---|---------|--------|---------|------|
| 14 | SimulatedChain with in-memory PVM | P0 | ❌ 不做 | 之前有但集成 NODE 后未维护；链迭代太快无法维护两套 |
| 15 | Block advancement & timer triggering | P0 | ❌ 不做 | 依赖 SimulatedChain，当前无法在公共 DevNet 上强制推进区块 |
| 16 | Runner mocking with conditional responses | P0 | ❌ 无 | 无此功能 |
| 17 | State snapshot assertions | P0 | ❌ 不做 | 属本地 testing 需求，当前无本地环境 |
| 18 | Determinism checking (cross-platform) | - | ❓ 待讨论 | 留到后续确认 |
| 19 | 本地调试环境（含 timer 快速触发等） | 下一里程碑 | ❌ 计划中 | 会议决议：**下个里程碑**实现；老严负责梳理本地开发特性 |

---

## 四、错误处理 & AI Context

| # | 客户需求 | 优先级 | 我方状态 | 备注 |
|---|---------|--------|---------|------|
| 20 | Error Messages — 四段式格式 (what, why, fix, link) | P0 | 🟡 部分有 | 有一部分，需增强；也便于我方调试 |
| 21 | Common error mapping table in PVM | P0 | 🟡 部分有 | 需补充 |
| 22 | AI Context — Skills for Claude/Codex/OpenClaw | - | ❌ 未做 | 需 SDK 完成后再开发，目前偏早 |
| 23 | `.cursorrules` in `cowboy init` output | - | ❌ 未做 | 同上 |
| 24 | `llms.txt` at docs domain root | - | ❌ 未做 | 同上 |

---

## 五、DevEx (开发者体验产品)

| # | 客户需求 | 优先级 | 我方状态 | 备注 |
|---|---------|--------|---------|------|
| 25 | DevEx 产品设计方案 | 核心 | ❌ 客户无方案 | 客户未给出具体产品设计；我方需主动设计并与客户确认 |
| 26 | DevEx CLI 用户旅程（6步） | 核心 | 🟡 已提出 | Slack 2/21：我方已提出 DevEx 用户旅程图，Patrick 初步认可 |
| 27 | Cowchat 用户旅程（6步） | 核心 | 🟡 已提出 | 同上：非技术用户通过自然语言部署 Actor |
| 28 | 开发者调试工具（查看 Runner 状态、Actor 状态、transaction 进度） | 高 | ❌ 无产品化工具 | 我方内部通过看日志调试，外部开发者无法使用；需产品化 |
| 29 | Public DevNet 上线 (3月) | 核心 | 🟡 进行中 | 客户最重要里程碑；当前为 Private DevNet |

---

## 六、CIP 文档 & 协议

| # | 客户需求/议题 | 我方状态 | 备注 |
|---|-------------|---------|------|
| 30 | CIP-2: Runner Network 更新 | 🟡 进行中 | 决定基于 GitHub 现有 CIP-2 出对照版，而非另起文档 |
| 31 | CIP-7: Simple Stream Protocol | ❓ 待理解 | 客户提出设计，我方尚未完全理解；需在 CIP 中提问确认意图 |
| 32 | CIP-20: Fungible Token Standard | ❓ 待讨论 | 客户要求优先级前提；尚无定论；需写 System Actor 实现 |
| 33 | CIP-6: Python SDK & Actor API | 参考 | 我方之前写的 SDK 规范，包含约14-15个装饰器定义 |

---

## 七、链核心 & 白皮书一致性

| # | 议题 | 我方状态 | 备注 |
|---|-----|---------|------|
| 34 | ED25519 → secp256k1 地址方案 | ⚠️ 重大差异 | 白皮书要求 secp256k1（以太坊兼容），我方用 ED25519；改动涉及三个系统（NODE/PVM/Runner）全面改造，工作量巨大 |
| 35 | Proof of Stake 机制 | ⚠️ 缺失 | 当前 SimpleX 无 POS（仅 2f+1 节点投票），需加入基于 stake 权重的投票 |
| 36 | 以太坊 EVM 兼容性 | ⚠️ 关键方向 | 客户高度关注；所有不兼容的地方都需逐步修正 |
| 37 | 扇出率限制 (fan-out 1024) | 🟡 待加 | 机制已知，约束条件未加入 |
| 38 | 内存限制 (每实例) | ⚠️ 风险 | 客户要求加限制，但实际 Python actor 内存可能远超限额，难以保证 |
| 39 | 白皮书差异对比文档 | ✅ 已有 | 英文版已准备，通过 Slack 发给客户 |

---

## 八、我方已实现但客户未列出的亮点

| # | 功能 | 状态 | 备注 |
|---|-----|------|------|
| 40 | Runner 完整分布式架构 | ✅ 已实现 | Runner 本质上是另一条链：数据同步、通讯、Key Manager 安全管理、verify 回放验证均已实现 |
| 41 | System Actors (timer / dispatcher / job / result) | ✅ 已实现 | 系统级 Actor 全套完成，客户不知晓 |
| 42 | Dual-Metered Gas (Cycles + Cells) | ✅ 已实现 | 参照以太坊 + Solana 方式 |
| 43 | Runner 注册机制 & 报价单 | ✅ 已实现 | Runner 向 NODE 的注册和报价功能 |
| 44 | Deferred Transaction (跨区块延迟交易) | ✅ 已实现 | 核心功能，已跑通 |
| 45 | LLM Chat Demo | ✅ 已实现 | 有界面，可演示 |
| 46 | Deferred Counter Demo | ✅ 已实现 | 保留的两个 demo 之一 |
| 47 | 自定义 Actor 部署 & 运行 | ✅ 已实现 | Python 编写 + 命令行部署完全可用（语法较原始） |
| 48 | RPC 接口层 | ✅ 已实现 | 一组 RPC 接口可查询 deferred transaction、timer job 等 |

---

## 九、代码 & 架构调整

| # | 事项 | 状态 | 备注 |
|---|------|------|------|
| 49 | PVM 合并入 NODE 仓库 (不再作为子模块) | ✅ 已完成 | 2/21 Slack 确认已合并到 devnet 分支 |
| 50 | PVM Alto → 改名为 Simulate Chain | 🟡 待改 | 避免与 Commonware 产生歧义 |
| 51 | Demo 精简（只保留 LLM Chat + Deferred Counter） | 🟡 待清理 | 其他 demo 代码可能已失效，需移除 |
| 52 | 架构图（清晰英文版） | 🟡 待出 | 需提供非 ASCII 的清晰架构图给客户 |
| 53 | Martin 的 PR 协调 | ✅ 已处理 | PR#170 已合并；已沟通未来开发在独立仓库进行 |

---

## 十、沟通 & 流程

| # | 事项 | 状态 | 备注 |
|---|------|------|------|
| 54 | 加强 Slack / Notion 沟通频次 | 🟡 进行中 | 覃谊主导沟通，Tony 旁观指导 |
| 55 | 确认客户 DevEx 产品设计设想 | 🟡 待确认 | 需主动问客户 DevEx 具体设想和发行计划 |
| 56 | 确认客户公共 DevNet 的"ready"标准 | 🟡 已提问 | Slack 2/20 已向客户提问，Patrick 分享了 Notion Devnet Milestone |
| 57 | Martin 独立仓库开发约定 | ✅ 已沟通 | Slack 2/21-2/22 已明确：Martin 在独立 repo 开发，我方维护自有分支 |
| 58 | 周期性同步会议 | 🟡 待定 | 提议 weekly sync 但未最终确认 |

---

## 状态图例

| 符号 | 含义 |
|------|------|
| ✅ | 已完成/已实现 |
| 🟡 | 部分完成/进行中/计划中 |
| ❌ | 未实现/决定不做 |
| ❓ | 待确认/待讨论 |
| ⚠️ | 存在重大差异或风险 |
