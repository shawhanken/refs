# 客户跟进策略与差异分析

> **日期**：2026-02-19  
> **背景**：前期沟通不畅，代码业务逻辑与客户期望存在差异。当前首要目标是建立理解与信任。  
> **参考文件**：  
> - 客户文档：[Devnet Milestone](https://www.notion.so/Devnet-Milestone-30ad57da9b1b80849489e9512be06667)  
> - 客户文档：[Developer Experience Situational Awareness](https://www.notion.so/Developer-Experience-Situational-Awareness-2ffd57da9b1b80c09f55f049ee51e430)  
> - 我方文档：[Cowboy Project Architecture Overview EN](file:///home/ubuntu/cowboydocs/20260219_Cowboy_Project_Architecture_Overview_EN.md)

---

## 一、核心判断

**客户真正关心的不是代码量，而是"用起来"**。

从 Devnet Milestone 和 DevEx 文档可以看出，客户的诉求核心是：**让外部开发者能够顺畅地在 Cowboy Devnet 上开发和部署 Actor**。他们列出的 P0 需求都围绕这个目标：CLI 工具链、SDK 文档、错误提示等。

根据 2/11 内部会议的定义：
- **Private Devnet（2月底～3月初）**：当前阶段，核心功能跑通，内部验证
- **Public Devnet（3月底目标）**：面向外部开发者开放，上线 Cowchat

我们已经完成了强大的底层基础设施（42 个 Rust crate，覆盖共识→执行→VM→链下计算全链路），但在**开发者体验层（DX Layer）**的建设上，与客户期望有明显差距。

---

## 二、Devnet Milestone 逐项对照

### Protocol 部分

| # | 客户需求 | 我方状态 | 差距 |
|---|---------|---------|------|
| 1 | Multi-node support w/simplex, leader election | ✅ 已实现 — Simplex BFT 共识，BLS12-381，1s 出块 | 无（核心已到位） |
| 2 | Public RPC/API | ✅ 已实现 — Axum REST + OpenAPI/Swagger，完整端点 | 需确认公网暴露策略 |
| 3 | Public testnet RPC endpoint (+ Status Page) | ⚠️ 部分 — Martin 已部署 validator-01.dev.cowboylabs.net，但无 Status Page | 缺 Status Page |
| 4 | Testnet faucet | ❌ 未实现 | 需新建 |
| 5 | CIP-(1-6) 核心协议支持 | ⚠️ 大部分已实现 — actors/runners/gas/storage/timers 核心逻辑已有，SDK 部分尚弱 | 需整理对照表 |
| 6 | CIP-7 (streaming) | ⚠️ Charles 已重写 CIP-7 文档，Tony 评论 "正在 review" | 需完成 review 并反馈 |
| 7 | CIP-20 (tokens) | ❌ 未实现 — Tony 已问 "CIP-21 在哪里？" | 需与客户确认 scope |
| 8 | Genesis + chain config freeze | ⚠️ 有 genesis 配置，但未 freeze | 需协调 |
| 9 | Basic chain monitoring + alerting | ❌ 未实现 | 需新建 |
| 10 | Snapshots + restore runbook | ❌ 未实现 | 需新建 |
| 11 | Incident runbook | ❌ 未实现 | 需新建 |

### Cowchat 部分

| # | 客户需求 | 我方状态 | 差距 |
|---|---------|---------|------|
| 1 | Simple v0 dashboard + public block explorer | ❌ 未实现（Explorer 仓库存在但非 Cowchat） | 需新建 |
| 2 | Network status panel | ❌ 未实现 | 需新建 |
| 3 | Builder with lightweight node UI to create actors | ❌ 未实现 | 需新建 |
| 4 | Wallet connect | ❌ 未实现 | 需新建 |
| 5 | Faucet request UI + response state | ❌ 未实现 | 需新建 |

### DevEx 部分（P0 优先级）

| # | 客户需求 | 我方状态 | 差距说明 |
|---|---------|---------|---------|
| 1 | `cowboy init` (项目脚手架) | ❌ 未实现 | CLI 目前只有 deploy/send/query |
| 2 | `cowboy dev` (本地开发服务器) | ❌ 未实现 — 但 pvm-simulator 可作为基础 | pvm-simulator 的 FsHost 已可本地执行，需包装成 CLI 命令 |
| 3 | `cowboy test` (测试框架) | ❌ 未实现 | 需新建 |
| 4 | `cowboy actor deploy` | ✅ 已实现 | Martin 已验证端到端部署 |
| 5 | `cowboy actor logs` | ❌ 未实现 | 需新建 |
| 6 | `cowboy inspect` | ⚠️ 部分 — inspector crate 存在 | 需包装为用户友好命令 |
| 7 | SDK 类型注解 + .pyi stubs | ⚠️ Partial — pvm_sdk 有基础模块 | 需补充完整类型 |
| 8 | 人性化装饰器 (`@actor`, `@timer` 等) | ⚠️ Minimal — 有基础实现 | 需增强 |
| 9 | 四段式错误提示格式 | ❌ 未实现 | 需新建 |
| 10 | 常见错误映射表 | ❌ 未实现 | 需新建 |
| 11 | Getting started guide | ❌ 未实现（仅有部署指南，非开发教程） | 需新建 |
| 12 | pvm_host API docs | ❌ 未实现 | 需新建 |
| 13 | Shell script 安装 / 预编译二进制分发 | ❌ 未实现 | 需新建 |
| 14 | AI Context (SKILL.md / .cursorrules / llms.txt) | ❌ 未实现 | P1，可后续跟进 |
| 15 | `cowboy wallet` create 命令 | ❌ 未实现 | Notion 要求，当前仅有 `wallet address` |
| 16 | Account balance/nonce/info 查询命令 | ⚠️ Stub — CLI 代码存在但输出 "not yet implemented" | 需对接 API 完成实现 |
| 17 | SDK on PyPI/npm | ❌ 未实现 | Notion 要求发布到包管理器 |

### 已实现但客户未列出的 CLI 命令

这些是**我们已有但客户文档中未特别提及的功能**，可以作为"超额交付"展示：

| 命令 | 状态 | 说明 |
|------|------|------|
| `cowboy wallet address` | ✅ Implemented | 查看钱包地址 |
| `cowboy runner get/list/register` | ✅ Implemented | Runner 管理 |
| `cowboy job get/status/runners/results/verified/submit` | ✅ Implemented | 任务生命周期管理 |
| `cowboy transfer` | ✅ Implemented | 原生转账 |
| `cowboy actor send` | ✅ Implemented | 发送消息 |
| `cowboy account balance/nonce/info` | ⚠️ Stub 存在 | CLI 代码有但输出 "not yet implemented"，需对接 API |

---

## 三、代码已实现功能全景图

> 以下全景图**完全基于代码库**绘制（node/devnet 分支、pvm/main 分支、runner/main 分支），不含任何 Notion 需求或虚构内容。

### 代码全景图（中文版）

```
┌─────────────────────────────────────────────────────────────────────────┐
│               已实现的代码功能全景 (基于 3 个仓库)                         │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │  CLI 命令层 (node/cli)                                               │ │
│ │                                                                      │ │
│ │  cowboy account balance │ nonce │ info                               │ │
│ │  cowboy transaction submit │ get │ status                            │ │
│ │  cowboy block by-height │ by-hash │ latest                          │ │
│ │  cowboy query blocks │ transactions                                  │ │
│ │  cowboy actor deploy │ execute │ get │ address                       │ │
│ │  cowboy runner get │ list │ register                                 │ │
│ │  cowboy job get │ status │ runners │ results │ verified │ submit     │ │
│ │  cowboy transfer (CBY 转账)                                          │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  REST API 层 (node/chain — Axum + OpenAPI/Swagger)                  │ │
│ │                                                                      │ │
│ │  /submit  /transaction/{hash}  /transaction/{hash}/receipt          │ │
│ │  /account/{addr}  /actor/{addr}  /actor/{addr}/code                 │ │
│ │  /block/{hash}  /height  /mempool/transaction/{hash}                │ │
│ │  /health  /health/detailed  /health/ready                           │ │
│ │  /runner/{addr}  /runner/{addr}/heartbeat  /runner/{addr}/jobs       │ │
│ │  /runners/active  /runner/{addr}/job_result  /runner/{addr}/job_result_payload │ │
│ │  /job/{id}  /job/{id}/status  /job/{id}/runners                     │ │
│ │  /job/{id}/results  /job/{id}/verified                              │ │
│ │  /swagger-ui (自动文档)                                              │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  共识 + 执行引擎 (node/chain)                                       │ │
│ │                                                                      │ │
│ │  Simplex BFT 共识 │ BLS12-381 签名 │ Random 选举                    │ │
│ │  双重 Gas 计量 (Cycles + Cells) │ Mempool                           │ │
│ │  Deferred TX (延迟交易) │ CREATE2 地址派生                           │ │
│ │  Genesis 配置 + 迁移 │ Block Storage (RocksDB)                      │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  System Actors (node/chain + node/runner)                            │ │
│ │                                                                      │ │
│ │  RunnerRegistry — Runner 注册/心跳/费率卡更新/活跃列表              │ │
│ │  JobDispatcher — Job 提交/委员会选择/Job 规格查询                    │ │
│ │  ResultVerifier — N-of-M 验证/结果收集/共识判定                     │ │
│ │  SecretsManager — 加密密钥管理                                       │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  PVM — 确定性 Python VM (pvm 仓库, 21 crates)                       │ │
│ │                                                                      │ │
│ │  确定性执行引擎 (vm) │ SoftFloat 浮点 │ Import Guard                │ │
│ │  Checkpoint / Snapshot │ Gas Metering │ JIT 编译                    │ │
│ │  Compiler (core + source + codegen) │ stdlib │ pylib                │ │
│ │  pvm-alto (本地独立执行环境)                                         │ │
│ │  pvm-host (Host Function 接口定义)                                   │ │
│ │  pvm-runtime (状态管理 + continuation + guard + determinism)         │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  Python SDK (pvm/Lib/pvm_sdk — 10 模块)                             │ │
│ │                                                                      │ │
│ │  actor.py │ runner.py │ continuation.py │ verify.py                 │ │
│ │  pvm_time.py │ pvm_random.py │ pvm_sys.py                          │ │
│ │  runtime.py │ types.py │ __init__.py                                │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  Runner 网络 (runner 仓库, 14 crates)                                │ │
│ │                                                                      │ │
│ │  3 执行器: runner-llm │ runner-http │ runner-mcp                    │ │
│ │  runner-node (主节点) │ runner-consensus (共识)                      │ │
│ │  chain-client │ job-dispatcher │ result-verifier                    │ │
│ │  runner-registry │ runner-common                                     │ │
│ │  secrets-manager │ tee-verifier │ runner-tee                        │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │  示例 Actor (node/chain/examples)                                    │ │
│ │                                                                      │ │
│ │  llm_chat (LLM 对话) │ candle_up_down (猜涨跌游戏)                 │ │
│ │  deferred_counter_demo │ deferred_tx_checkpoint_demo                │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Code-Implemented Panorama (English Version)

```
┌─────────────────────────────────────────────────────────────────────────┐
│            Implemented Code Panorama (across 3 repositories)            │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │  CLI Commands (node/cli)                                             │ │
│ │                                                                      │ │
│ │  cowboy account balance │ nonce │ info                               │ │
│ │  cowboy transaction submit │ get │ status                            │ │
│ │  cowboy block by-height │ by-hash │ latest                          │ │
│ │  cowboy query blocks │ transactions                                  │ │
│ │  cowboy actor deploy │ execute │ get │ address                       │ │
│ │  cowboy runner get │ list │ register                                 │ │
│ │  cowboy job get │ status │ runners │ results │ verified │ submit     │ │
│ │  cowboy transfer (CBY transfer)                                      │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  REST API Layer (node/chain — Axum + OpenAPI/Swagger)                │ │
│ │                                                                      │ │
│ │  /submit  /transaction/{hash}  /transaction/{hash}/receipt          │ │
│ │  /account/{addr}  /actor/{addr}  /actor/{addr}/code                 │ │
│ │  /block/{hash}  /height  /mempool/transaction/{hash}                │ │
│ │  /health  /health/detailed  /health/ready                           │ │
│ │  /runner/{addr}  /runner/{addr}/heartbeat  /runner/{addr}/jobs       │ │
│ │  /runners/active  /runner/{addr}/job_result  /runner/{addr}/job_result_payload │ │
│ │  /job/{id}  /job/{id}/status  /job/{id}/runners                     │ │
│ │  /job/{id}/results  /job/{id}/verified                              │ │
│ │  /swagger-ui (auto-generated docs)                                   │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  Consensus + Execution Engine (node/chain)                           │ │
│ │                                                                      │ │
│ │  Simplex BFT Consensus │ BLS12-381 Signatures │ Random Election     │ │
│ │  Dual Gas Metering (Cycles + Cells) │ Mempool                       │ │
│ │  Deferred Transactions │ CREATE2 Address Derivation                 │ │
│ │  Genesis Config + Migration │ Block Storage (RocksDB)               │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  System Actors (node/chain + node/runner)                            │ │
│ │                                                                      │ │
│ │  RunnerRegistry — register/heartbeat/rate card/active list          │ │
│ │  JobDispatcher — job submit/committee selection/spec query          │ │
│ │  ResultVerifier — N-of-M verification/result collection/consensus   │ │
│ │  SecretsManager — encrypted key management                          │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  PVM — Deterministic Python VM (pvm repo, 21 crates)                │ │
│ │                                                                      │ │
│ │  Deterministic Execution Engine (vm) │ SoftFloat │ Import Guard     │ │
│ │  Checkpoint / Snapshot │ Gas Metering │ JIT Compilation             │ │
│ │  Compiler (core + source + codegen) │ stdlib │ pylib                │ │
│ │  pvm-alto (standalone local execution environment)                   │ │
│ │  pvm-host (host function interface definitions)                      │ │
│ │  pvm-runtime (state mgmt + continuation + guard + determinism)      │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  Python SDK (pvm/Lib/pvm_sdk — 10 modules)                          │ │
│ │                                                                      │ │
│ │  actor.py │ runner.py │ continuation.py │ verify.py                 │ │
│ │  pvm_time.py │ pvm_random.py │ pvm_sys.py                          │ │
│ │  runtime.py │ types.py │ __init__.py                                │ │
│ └─────────────────────────────────┬───────────────────────────────────┘ │
│                                   │                                     │
│ ┌─────────────────────────────────┴───────────────────────────────────┐ │
│ │  Runner Network (runner repo, 14 crates)                             │ │
│ │                                                                      │ │
│ │  3 Executors: runner-llm │ runner-http │ runner-mcp                 │ │
│ │  runner-node (main node) │ runner-consensus                         │ │
│ │  chain-client │ job-dispatcher │ result-verifier                    │ │
│ │  runner-registry │ runner-common                                     │ │
│ │  secrets-manager │ tee-verifier │ runner-tee                        │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │  Example Actors (node/chain/examples)                                │ │
│ │                                                                      │ │
│ │  llm_chat (LLM conversation) │ candle_up_down (price guessing)     │ │
│ │  deferred_counter_demo │ deferred_tx_checkpoint_demo                │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```



### 三个里程碑时间线 / Three Milestone Timeline

> 根据 2026-02-11 + 2026-02-18 两次内部会议决定更新  
> 每项均标注来源：[Notion] = Devnet Milestone 文档 / [2/18] = 2月18日会议 / [2/11] = 2月11日会议

```
  2月19日(今天)          3月8日                   3月31日
     │                    │                        │
     ▼                    ▼                        ▼
 ════╪════════════════════╪════════════════════════╪════
     │   Phase 1          │    Phase 2             │
     │   Private Devnet   │    Public Devnet       │
     │   收尾交付          │    开发者体验 + UI      │
     │                    │                        │
     │  · CIP-7 反馈      │  · cowboy init         │
     │  · CIP-2 更新      │  · actor logs          │
     │  · 无POS告知客户   │  · SDK + decorators    │
     │  · ED25519调研     │  · SimulatedChain      │
     │  · Genesis冻结     │  · Error Messages      │
     │  · 架构可视化图    │  · Cowchat/Explorer    │
     │  · 白皮书差异Slack │  · Faucet/Status Page  │
 ════╪════════════════════╪════════════════════════╪════
     │                    │                        │
  证明没有延期        开发者能"较容易"       开发者能"很容易"
  展示超额交付        地部署 Actor          地从零部署 Actor
```

---

### Phase 1：Private Devnet 收尾（截止 3月8日）

> 目标：**证明 Private Devnet 没有延期** + 向客户展示超额交付 + **主动暴露关键技术差异**。  
> 开发者体验：内部团队可以部署 Actor，但外部开发者还需要指导。  
> 来源：每项标注 [Notion] / [2/18] / [2/11]

```
┌─────────────────────────────────────────────────────────────────────┐
│      Phase 1 交付物（Private Devnet 收尾，截止 3月8日）               │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │    Protocol & Infra + 客户沟通（本阶段重点）         🔨       │  │
│   │    ──────────────────────────────────────────                 │  │
│   │    🔨 交付：                                                  │  │
│   │       CIP-7 阅读理解 + 提出问题/意见发群里给 Tony    [2/18]  │  │
│   │       CIP-2 结合 Runner 代码更新一版（替代原CIP-8）  [2/18]  │  │
│   │       Genesis + chain config freeze（Devnet发布前冻结）[Notion]│ │
│   │       Snapshots + 恢复手册                           [Notion] │  │
│   │       Incident runbook（降级/停机/重启手册）         [Notion] │  │
│   │       CI/CD 测试指引文档                             [2/11]   │  │
│   │       SDK 状态说明（comment 解释 partial/minimal 的原因）[2/11]│ │
│   │       架构可视化图（非ASCII版，英文，供 Tony 给客户） [2/18]  │  │
│   │       白皮书 vs 代码差异对比 → Slack 发布（英文版）  [2/18]  │  │
│   │                                                              │  │
│   │    ⚠️ 必须主动告知客户的技术差异（2/18 会议明确）：            │  │
│   │       · Simplex 目前没有 POS — 仅 f+1 节点投票，无 Stake 权重 │  │
│   │         客户可能默认我们已完成完整共识，需主动说明              │  │
│   │       · ED25519 vs secp256k1 — 当前用 ED25519 (32位)，        │  │
│   │         白皮书写的是 secp256k1 (与ETH兼容)，需调研             │  │
│   │         是否能与以太坊结合，这是客户核心关注方向               │  │
│   │       · PVM-alto → SimulatedChain 命名修正（避免歧义）        │  │
│   │       · Demo 应用仅保留 llm_chat + deferred_counter_demo      │  │
│   │                                                              │  │
│   │    ✅ 已完成（向客户展示）：                                    │  │
│   │       Multi-node Simplex BFT 共识（无POS）           [Notion] │  │
│   │       Public RPC/API（Axum REST + OpenAPI/Swagger）  [Notion] │  │
│   │       Public testnet RPC endpoint                    [Notion] │  │
│   │       Testnet 节点部署（validator-01.dev.cowboylabs.net）[Notion]││
│   │       CIP 1-6 核心协议大部分实现                     [Notion] │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│ ═══════════════════  已完成的核心基础  ═══════════════════════════  │
│                              │                                      │
│   ┌──────────────────────────┴───────────────────────────────────┐  │
│   │    Core Infrastructure（42 Rust Crates）                ✅    │  │
│   │    ──────────────────────────────────────────                 │  │
│   │    NODE: 共识引擎 + 双Gas执行引擎 + Actor模型 + 5个系统Actor │  │
│   │          延迟TX + Mempool + 区块存储 + Indexer                │  │
│   │    PVM:  确定性Python VM + SoftFloat + Gas计量 +             │  │
│   │          Import Guard + Checkpoint + SDK Bridge               │  │
│   │    RUNNER: 3种执行器（LLM/HTTP/MCP）+ 分布式共识 +           │  │
│   │           N-of-M结果验证 + 注册/心跳/报价单 +                 │  │
│   │           TEE运行时 + 密钥管理 + 声誉系统                     │  │
│   │                                                              │  │
│   │    ★ 超额交付亮点（客户列表之外，代码库已验证）：              │  │
│   │       · 5个System Actor（Registry/Dispatcher/Verifier/       │  │
│   │         SecretsMgr/TEEVerifier）— 客户完全不知道              │  │
│   │       · Runner Verify 机制 — 主链回放时可验证历史结果          │  │
│   │       · Runner 分布式共识 — Runner间数据同步与结果聚合         │  │
│   │       · Deferred TX 机制 — 跨块异步执行 + 回调链               │  │
│   │       · Dual-Metered Gas（Cycles+Cells）                      │  │
│   │       · CREATE2 确定性地址                                     │  │
│   │       · Runner 报价单（Rate Card）机制                         │  │
│   └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 2：Public Devnet 建设（截止 3月31日）

> 目标：**让外部开发者能够较容易地在 Cowboy Devnet 上开发和部署 Actor**。  
> 重点：DX 体验提升 + UI 层建设 + **本地开发环境（基础版）**。  
> **2/18 会议重要变更**：SDK decorators 和本地开发环境从"不做"改为本阶段目标。

```
┌─────────────────────────────────────────────────────────────────────┐
│         Phase 2 交付物（Public Devnet，截止 3月31日）                 │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │    UI Layer（本阶段建设）                            🔨       │  │
│   │    ──────────────────────────────────────────                 │  │
│   │    🔨 交付：                                                  │  │
│   │       Cowchat Dashboard + Builder UI（创建 Actor） [Notion]   │  │
│   │       Block Explorer（基础版，含网络状态面板）      [Notion]   │  │
│   │       Testnet Faucet UI + 请求状态                  [Notion]   │  │
│   │       Status Page（节点状态监控）                    [Notion]   │  │
│   │       Wallet Connect（基础集成）                    [Notion]   │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│   ┌──────────────────────────┴───────────────────────────────────┐  │
│   │    Developer Experience Layer（本阶段重点）          🔨       │  │
│   │    ──────────────────────────────────────────                 │  │
│   │    🔨 交付：                                                  │  │
│   │       cowboy init（项目脚手架）                      [Notion+2/18确认]│
│   │       cowboy actor logs（日志写入链DB/indexer）      [Notion]  │  │
│   │       cowboy wallet create 命令                      [Notion]  │  │
│   │       Account balance/nonce/info 完成实现（当前stub）[Notion]  │  │
│   │       Error Messages 四段式格式（what/why/fix/link） [Notion]  │  │
│   │       常见错误映射表（PVM 内）                       [Notion]  │  │
│   │       SDK 封装 + decorators（@actor/@timer 等）      [Notion+2/18]│ │
│   │       SDK Full type annotations (PEP 484) + .pyi stubs[Notion+2/18]││
│   │       SDK on PyPI/npm 发布                           [Notion]  │  │
│   │       Getting Started 文档 + 示例 Actors             [Notion]  │  │
│   │       pvm_host API 文档                              [Notion]  │  │
│   │       SimulatedChain 本地开发环境（基础版）          [2/18新]  │  │
│   │         — Tony 确认下个里程碑加入，目标：让开发者可            │  │
│   │           本地调试 timer 等功能（快速产块模拟）                │  │
│   │       Core examples 编译通过（llm_chat + deferred_counter）   │  │
│   │                                                              │  │
│   │    ❓ 待讨论（根据资源决定）：                                  │  │
│   │       Shell script install / 预编译二进制分发        [Notion]  │  │
│   │       AI Context（SDK完成后再做）           [Notion+2/18确认]  │  │
│   │       POS 实现（Stake 权重投票）— 依赖 ED25519 调研结果[2/18] │  │
│   │                                                              │  │
│   │    ⏭️ 明确不做（来源标注）：                                    │  │
│   │       cowboy dev（完整版）/ cowboy test      [Notion列出,会议排除]││
│   │       Runner mocking / Block advancement    [DevEx文档,会议排除]│ │
│   │       State snapshot assertions             [DevEx文档,会议讨论]│ │
│   │       Determinism checking (cross-platform) [DevEx文档,会议讨论]│ │
│   └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│   ┌──────────────────────────┴───────────────────────────────────┐  │
│   │    Protocol & Infra（补充项）                                 │  │
│   │    ──────────────────────────────────────────                 │  │
│   │    🔨 交付：                                                  │  │
│   │       Testnet Faucet（水龙头 API）                  [Notion]  │  │
│   │       基础监控 + 告警（block lag/RPC错误率/peer数）  [Notion]  │  │
│   │       ED25519 → secp256k1 迁移（如调研确认需要）    [2/18]    │  │
│   └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 开发者体验渐进路线图 / Developer Experience Progressive Roadmap

| 时间节点 | 开发者能做什么 | 还不能做什么 |
|---|---|---|
| **现在（2月19日）** | 内部团队用 `cowboy actor deploy/send/query` 部署 Actor | 无脚手架、无文档、错误信息不友好、无本地调试、balance/nonce 命令未完成 |
| **Phase 1 后（3月8日）** | + CIP文档完善、架构可视化展示、白皮书差异透明化、Genesis config 冻结、Snapshots/Incident 手册就绪 | 无日志查看、无 init、无文档、无本地开发 |
| **Phase 2 后（3月31日）** | + cowboy init + actor logs + error messages + SDK decorators + SDK on PyPI + SimulatedChain本地调试 + wallet create + balance/nonce + 文档 + Cowchat + Explorer，**外部开发者可较容易从零部署 Actor** | 无完整 cowboy dev/test、无 POS（待定） |

### 两阶段对比总结 / Two-Phase Summary

| 层级 / Layer | Phase 1（3月8日） | Phase 2（3月31日） |
|---|---|---|
| **UI Layer** | — | 🔨 Cowchat+Builder/Explorer/Faucet/Status/Wallet |
| **DX Layer** | 🔨 SDK说明 | 🔨 init + logs + wallet + SDK + decorators + SimChain + docs + PyPI |
| **Protocol & Infra** | 🔨 CIP-7反馈/CIP-2更新/Genesis冻结/Snapshots/Incident手册 | 🔨 Faucet API + 监控 + ED25519迁移? |
| **Core Infrastructure** | ✅ 42 crates + 展示给客户 | ✅ 持续维护 |
| **超额交付亮点** | ✅ **7项**（代码库已验证，头版头条展示） | — |
| **⚠️ 技术风险告知** | ⚠️ 无POS + ED25519 + 白皮书差异 | ⚠️ POS实现 + ETH兼容方案 |

> **Phase 1 关键信息**：3月8日前完成 Private Devnet 收尾 + 向客户展示超额交付 + **主动透明化技术差异**（无POS、ED25519问题）。  
> **Phase 2 关键信息**：3月31日前完成 DX + UI 层建设 + **本地开发环境基础版**，让外部开发者能够较容易地从零部署 Actor。  
> **2/18 会议重大变更**：SDK decorators、SimulatedChain 本地开发环境从"不做"重新纳入 Phase 2 范围；CIP-8(新建) → CIP-2(更新)。  
> **已清理**：删除了无来源的"OpenClaw 集成支持"、"Actor 禁用工具"、"cowboy cost"、"cowboy secrets"；补充了 Notion 遗漏的 Genesis freeze、Incident runbook、wallet create、balance/nonce/info、SDK on PyPI。

## 四、客户跟进策略建议

### 策略一：先展示实力，再讨论差距（推荐）

**目标**：让客户理解我们已有的技术深度，然后一起对齐 DX 层的建设路径。

#### Step 1：发送架构全景图（本周）

将 `20260219_Cowboy_Project_Architecture_Overview_EN.md` 共享给客户，并附言：

> We've put together a comprehensive architecture overview of our current codebase covering all 42 Rust crates across the node, PVM, and runner repositories. We'd love to walk through this with you to make sure we're aligned on the protocol foundation before we focus on the developer experience layer.

**要点**：
- 让客户看到 42 个 Rust crate 的全景
- 让客户理解共识、执行引擎、PVM、Runner 的完整链路
- 证明核心协议基础是扎实的

#### Step 2：发送差异分析表（本周）

基于本文档的"第二节"差异分析，整理成客户可读的 Notion comment 或独立文档，诚实地展示：
- ✅ 已完成的：Protocol 核心、CLI 基础命令、Runner 全套
- ⚠️ 部分完成的：SDK、CIP review
- ❌ 未开始的：DX 工具链、UI、运维工具

**附言建议**：

> We've mapped our current implementation against the Devnet Milestone checklist. Our core protocol infrastructure is solid — consensus, execution engine, PVM, and runner network are all functional. The gap is primarily in the developer experience layer (CLI tooling, local dev environment, documentation). We'd like to propose a focused sprint plan to close these gaps.

#### Step 3：提出聚焦冲刺计划（本周内）

根据差距分析，提出一个 **2-3 周的聚焦冲刺计划**，专攻 Devnet Milestone 中的 P0 项：

| 周次 | 重点 | 交付物 |
|------|------|--------|
| Week 1 | CLI 增强 + Faucet | `cowboy init`, `cowboy dev`（基于 pvm-simulator）, Testnet Faucet |
| Week 2 | SDK + 文档 + 测试 | SDK 类型补全, Getting Started Guide, `cowboy test` 基础版 |
| Week 3 | 错误提示 + 运维 | 四段式错误格式, chain monitoring 基础, CIP-7 review 完成 |

#### Step 4：建立定期同步机制

- **每周二/四固定 30 分钟同步**（Tony + Martin）
- **每两周一次 demo**：向客户展示最新可用功能
- **GitHub Issues 作为唯一工作跟踪**：所有承诺的交付物创建 Issue，状态公开透明

### 策略二：应对 patrick 的产品/架构讨论

patrick 在 Slack 提出的 XMTP / Agent Token / Cowboy Gold / Runner 扩展等话题，建议这样处理：

1. **Slack 回复（本周）**：

> Thanks for the thoughtful prompts, Patrick. We've been discussing these internally. Quick responses:
> 
> - **XMTP**: Interesting for cross-ecosystem agent messaging. We think this fits well as a Runner executor type (similar to our existing HTTP/MCP executors). Not blocking for Devnet but worth scoping for v2.
> - **Agent Tokens / CIP-20**: We're reviewing this. Tony asked about CIP-21 definition — could you share more details?
> - **Cowboy Gold**: We like the free gas subsidy concept. This aligns with our faucet work for Devnet.
> - **Runner storage/sandboxing & Local Runner**: These are planned for DevNet v2 (as listed in the Devnet Milestone doc). Our current runner architecture is extensible enough to support this.
> - **AI NFTs**: Interesting but probably Phase 4. We can discuss in more detail at the next sync.
> 
> For the broader DX discussion, we've already left comments on the Developer Experience Situational Awareness doc in Notion. Please take a look.

2. **Developer Experience 文档**：已在 Notion 上回复了 comment，提醒 patrick 查看即可。

3. **Devnet Milestone 文档**：截图中已有 Tony 的评论（"Yep, we will be implementing those CIPs"、"We are reviewing the CIP-7"），需要**尽快补充更具体的时间线和分工**。

---

## 五、沟通话术要点

### 要传达的核心信息

1. **"基础设施非常扎实"**
   - 42 个 Rust crate，3 个仓库，覆盖全链路
   - 共识、执行引擎、PVM、Runner 已可端到端运行
   - Martin 已成功在 devnet 上部署 Actor 并运行

2. **"差距主要在开发者体验层"**
   - 核心 CLI 命令（init/dev/test/logs）是新功能，不是底层缺失
   - pvm-simulator 已为 `cowboy dev` 提供了技术基础
   - SDK 有骨架，需要补全类型和装饰器

3. **"我们有明确的冲刺计划"**
   - 不是泛泛的承诺，而是具体到周的交付计划
   - 每项有对应的 GitHub Issue
   - 定期 demo 证明进展

### 要避免的

- ❌ 不要说"我们一直在做底层，没时间做DX" → 这听起来像借口
- ❌ 不要拿代码量来证明工作量 → 客户关心的是可用性
- ❌ 不要对所有需求都说"会做" → 对 P2/P3 的需求明确说"后续阶段"
- ❌ 不要在 Slack 上长篇回复 → 用短回复 + 文档链接

---

## 六、下一步行动清单

- [ ] **今天**：将架构全景图（EN 版）整理成可共享的格式
- [ ] **今天**：在 Devnet Milestone Notion 文档上补充更具体的评论（带时间线）
- [ ] **本周**：回复 patrick 的 Slack 产品讨论（简短 + 指向 Notion）
- [ ] **本周**：创建 2-3 周冲刺计划，以 GitHub Issues 形式公开
- [ ] **本周**：交付 CI/CD 测试指引文档给 Martin
- [ ] **本周**：完成白皮书对照报告初稿
- [ ] **下周**：开始 DX 层 P0 功能开发
- [ ] **持续**：每周二/四固定同步，每两周 demo
