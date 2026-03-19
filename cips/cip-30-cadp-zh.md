---
title: "CIP-10: Cowboy AI 开发副驾 (CADP)"
description: 一个自治的、原生基于 AI 的开发基础设施规范，通过 MCP 实现 Actor 的构建、验证与部署
icon: bot
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Developer Infrastructure
</Note>

## 1. 摘要 (Abstract)

本提案定义了 **Cowboy AI 开发副驾 (Cowboy AI Development Co-pilot, CADP)** —— 一个协议级别的规范，旨在为远程 Cowboy Actor 开发者提供一个原生基于 AI 的基础设施。通过 CADP，开发者只需通过与 Claude Code 等 AI 模型进行自然语言交互，即可完成链上 Actor 的编写、验证、模拟、部署及监控。

CADP 通过 **模型上下文协议 (MCP)** 标准化了 AI 编程助手与 Cowboy 链之间的接口，建立了一座双向桥梁。它一方面通过 `CLAUDE.md` 为 AI 提供确定性的 Cowboy 领域知识，另一方面通过 MCP Server 为 AI 赋予安全合规的链上操作权限。其终极目标是彻底消除隐式依赖，让开发者不再需要手动应对底层的工具链和 PVM 约束。

---

## 2. 动机 (Motivation)

Cowboy Actor 系统的独特设计带来了较高的学习门槛：

1. **极其严格的 PVM 确定性约束**：开发者必须掌握约 10 条铁律（如禁止 `import time`、禁止 `import random`、禁止 `set()`、禁止硬件浮点数运算、在每一个 `await` 之前必须显式 `capture()` 等）。任何一条违规都会导致生成的 Actor 默默在执行中偏离共识。
2. **FSM 编译模型**：所有异步操作（如 LLM 推理、HTTP 请求、跨 Actor 调用）都必须被显式表达为有限状态机 (FSM) —— 这与传统 Python 的 async/await 模式截然不同。
3. **陌生的部署工具链**：发布上链需要熟悉 CBOR 编码、secp256k1 密钥管理、`cowboy-cli` 命令行交互以及 Gas（Cycles/Cells）的预估。
4. **远程开发者缺乏本地环境**：大部分生态贡献者并不会在本地运行验证者节点，也不会去安装庞大的 Rust 工具链或拉取完整的 Node 源码。

如果不对这些障碍进行干预，仅仅有极少数深度研究过 Cowboy 源代码的开发者才能编写 Actor。

**CADP 的提出旨在彻底解决这一问题**。它将 AI 转化为拥有 Cowboy 专业知识的专家，并将 MCP Server 作为连接“AI意图”与“链上现实”的执行层。

---

## 3. 目标与非目标 (Goals & Non-Goals)

### 目标

- G-1: 让一名只有 Python 环境和文本编辑器的远程开发者，在 AI 的引导下，能在 10 分钟内完成一个完整 Actor 的开发部署。
- G-2: CADP 工具链必须在代码触达链之前，强制执行所有 PVM 确定性规则 —— 不合规的代码将被直接拦截，不可部署。
- G-3: 赋能 AI 实现闭环的开发迭代：编写 → 验证 → 模拟执行 → 部署上链 → 链上测试 → 状态观测 → 自主修复。
- G-4: CADP 必须支持 Actor 从初次部署到多版本平滑升级的完整生命周期。
- G-5: 所有 CADP 工具都必须是确定性和幂等的 —— 在相同上下文下使用相同参数调用，总能产生相同的预期行为。

### 非目标

- NG-1: CADP 不会修改底层 PVM 的执行引擎，它纯粹在开发工具层工作。
- NG-2: CADP 无法且无意替代链上的 Gas 计费或严格的智能合约安全审计。
- NG-3: CADP 不指定某个具体的 AI 模型 —— 设计为模型无关，可与任何支持 MCP 的客户端集成。

---

## 4. 系统架构 (System Architecture)

```
┌──────────────────────────────────────────────────────────────┐
│                    Developer's Machine                        │
│                                                               │
│   Developer (自然语言意图)                                     │
│          │                                                    │
│          ▼                                                    │
│   ┌─────────────────────────────────────────────────┐       │
│   │              Claude Code / AI Client             │       │
│   │                                                   │       │
│   │  ┌─── CLAUDE.md ──────────────────────────────┐ │       │
│   │  │  Layer 1: PVM 铁律 (10 项边界不变性)           │ │       │
│   │  │  Layer 2: SDK API 快速参考手册                │ │       │
│   │  │  Layer 3: Actor 标准代码结构模板              │ │       │
│   │  │  Layer 4: 部署命令行速记指南                  │ │       │
│   │  └────────────────────────────────────────────┘ │       │
│   └─────────────────────────┬───────────────────────┘       │
│                              │ MCP stdio 传输协议              │
│                              ▼                               │
│   ┌──────────────────────────────────────────────────┐      │
│   │           cowboy_mcp_server (CADP Server)         │      │
│   │                                                   │      │
│   │  TIER 1: 知识支持层                              │      │
│   │    cowboy_sdk_docs  cowboy_pvm_rules              │      │
│   │                                                   │      │
│   │  TIER 2: 严格验证层                              │      │
│   │    cowboy_validate  cowboy_simulate               │      │
│   │                                                   │      │
│   │  TIER 3: 链上执行层                              │      │
│   │    cowboy_deploy  cowboy_call  cowboy_query       │      │
│   │                                                   │      │
│   │  TIER 4: 语义观测层                              │      │
│   │    cowboy_status  cowboy_logs  cowboy_trace       │      │
│   │                                                   │      │
│   │  TIER 5: 生命周期层                              │      │
│   │    cowboy_faucet  cowboy_upgrade  cowboy_diff     │      │
│   └─────────────────────────┬────────────────────────┘      │
└─────────────────────────────┼────────────────────────────────┘
                              │ HTTP / cowboy-cli binary
                    ┌─────────▼──────────────────┐
                    │    Cowboy Chain (Remote)    │
                    │                             │
                    │  Devnet RPC :4000           │
                    │  ├── POST /submit           │
                    │  ├── GET /actor/{addr}      │
                    │  ├── GET /block/{height}    │
                    │  ├── GET /logs/{addr}       │
                    │  └── POST /faucet           │
                    │                             │
                    │  PVM Validator              │
                    │  Runner (LLM/HTTP/MCP)      │
                    └─────────────────────────────┘
```

---

## 5. CADP MCP 工具规范 (CADP MCP Tool Specification)

CADP 定义了分布在 5 个层级（Tier）的 **15 个标准 MCP 工具**。这些工具通过 stdio 与 AI 代理通信，供其随时主动调用。

### Tier 1 — 知识支持层 (Knowledge Layer)

为 AI 随时注入必需的 Cowboy 专属知识。

#### `cowboy_sdk_docs`

提供对 `cowboy_sdk` 主要模块的详细指南。

```
输入:  { "topic": string }  // 比如 "continuation", "storage", "rules"
输出: 该主题下以 Markdown 格式编写的最佳实践文档
```

#### `cowboy_pvm_rules`

返回权威的 PVM 确定性约束列表。包含由于违反规则造成的失效案例和正确写法对照。AI 可以以此为自查清单，避免编写由于底层不兼容而无法执行的代码。

```
输入:  {}
输出: Array [{ rule_id, description, violation_example, correct_example, severity }]
```

---

### Tier 2 — 严格验证层 (Verification Layer)

负责阻挡非确定性和格式损坏的代码上链。

#### `cowboy_validate`

对 Actor 源码执行多阶段的静态审计，防止不合规逻辑：

1. **Syntax Check**：保证基本的 Python 语法无误。
2. **AST-level PVM Rule Enforcement**：解析抽象语法树（AST），检测非法的 `import` 语句、裸露的 `set()` 哈希结构、未处于 `capture()` 和 `@runner.continuation` 作用域内的 `await` 生命周期断裂风险等。
3. **入口完整性验证**：确认文件暴露了底层约定的调度入口（如 `init`, `<handler>`, `<handler>__resume`, `on_runner_result`）。
4. **Storage Schema 分析**：为版本升级提供基于现状的键值推断。

```
输入:  { "code_path": string }
输出: {
  "passed": bool,
  "syntax_errors": [...],
  "pvm_violations": [{ "line": int, "rule_id": string, "message": string }],
  "missing_entrypoints": [...],
  "warnings": [...]
}
```

#### `cowboy_simulate`

**(开发模式下最强的生产工具)**。允许代码**在提交部署前**，在一个位于本地的纯 Python PVM Mock 沙盒下被虚拟执行，输出包含 Storage 变更追踪在内的仿真报告，杜绝在链上调试代码的昂贵成本。

```
输入: {
  "code_path": string,
  "calls": [ { "handler": string, "payload": object, "sender": string? } ]
}
输出: {
  "success": bool,
  "storage_after": { key: decoded_value },
  "events_emitted": [...],
  "estimated_gas": int,
  "execution_trace": string,   // 人类可读的调试路径
  "error": string?
}
```

---

### Tier 3 — 链上执行层 (Execution Layer)

#### `cowboy_deploy`

将经历过验证的 Actor 正式部署到区块链。系统向 `cowboy` 命令行转发开发者本地签名的交易。

```
输入:  { "code_path": string, "salt": string?, "cycles_limit": int?, "cells_limit": int? }
输出: { "actor_address": string, "tx_hash": string, "block_height": int, "gas_used": int }
```

#### `cowboy_call`

发送带有签名并可能导致链上状态突变（Write）的 Actor Handler 调用交易。

```
输入:  { "actor_address": string, "handler": string, "payload": object, "cycles_limit": int? }
输出: { "success": bool, "result": decoded_value, "events": [...], "error": string? }
```

#### `cowboy_query`

发送轻量的状态观测查询动作（Read-only）。调用方式相当于一次 `--dry-run` 交易而不实际执行共识突变，因此不耗散 Gas 余额且速度更快。

```
输入:  { "actor_address": string, "handler": string, "payload": object }
输出: { "result": decoded_value }
```

---

### Tier 4 — 语义观测层 (Observability Layer)

#### `cowboy_status`

拉取该 Actor 最新区块的数据全集。所有的 CBOR 十六进制结构在这里被转化为结构化、强类型的具象表达，为 AI 展现清晰、透明的合约存储剖面。

```
输入:  { "actor_address": string }
输出: {
  "address": string,
  "balance": string,
  "storage": { key: { "raw_hex": string, "decoded": decoded_value, "type": string } }
}
```

#### `cowboy_logs`

从链上索引最新抛出的 Event 日志，支持条件过滤，附加完整的上下文元数据。

```
输入:  { "actor_address": string, "limit": int?, "from_block": int? }
输出: { "events": [{ "block": int, "name": string, "args": object, "tx_hash": string }] }
```

#### `cowboy_trace`

**(全新的底层透视能力)**。获取指定交易（失败或成功）最细粒度的 PVM 字节码流水执行路径。它让遇到 Revert 操作的 AI 能够自行诊断：“原来在某行溢出了 SoftFloat 边界”。

```
输入:  { "tx_hash": string }
输出: {
  "status": "success" | "reverted",
  "revert_reason": string?,
  "revert_at_line": int?,
  "gas_breakdown": { phase: cost },
  "storage_delta": { key: { before, after } }
}
```

---

### Tier 5 — 生命周期层 (Lifecycle Layer)

#### `cowboy_faucet`

环境准备工具：负责检查工作区钱包内是否有足够余额发起交易；在匮乏时自主联络该链的官方 Faucet 发起资金申领，实现“开发者 0 准备开发起步”。

#### `cowboy_upgrade`

对于已存在的 Actor 发起规范的升级变更：内部自动检查和比对不同版本的 Storage Schema。

#### `cowboy_diff`

**(新设计)** 静态差异比对工具，防范新逻辑在部署后因强类型解构不对称，让之前所存留下的历史数据失效。包含类型突变报警和迁移建议生成。

#### `cowboy_wallet` 与 `cowboy_actor_index`

管理当前的开发者身份，并在 Indexer 帮助下记录所有部署过的 Actor 实例与交互踪迹，为 AI 代理创造工作区记忆。

---

## 6. 上下文注入: CLAUDE.md

静态环境的灵魂工程。无论 CADP Server 何时被唤醒，`CLAUDE.md` 永远会确保 Claude Code 的系统 Prompt 提前被植入关键的 Cowboy Context。这种**零延迟、零网络请求成本**的架构让每一次对话从开始就建立在 PVM 的法则认知之上。

它必须包含且不仅限于 8 项内容（包括 10 项不可动摇的底层边界条件、API 纲要及代码骨架等）。

---

## 7. 完全自治开发闭环系统图示 (The Autonomous Development Loop)

在这个完整版配置中，Actor 的创建周期将被缩减到难以想象的程度：

```
开发者: "写一个拥有投票和提案功能的 Actor。达到 10 票就算通过。"

─────── 如下步骤均由 AI 全局推演不加打断地自动进行 ───────

1. 学习领域知识 -> cowboy_sdk_docs("actor与存储") / cowboy_pvm_rules()
2. 执行智能生成 -> AI 本地写出 main.py
3. 本地审计修复 -> cowboy_validate("main.py") 报错 -> AI 分析问题 -> 修改代码通过检验
4. mock 逻辑推演 -> cowboy_simulate 执行 3 种用户流验证逻辑结果，计算 Gas
5. 发起智能部署 -> 发水龙头申请 -> 执行 cowboy_deploy 获取回执
6. 执行实例化初始化业务层调用
7. 实勘验收调用并获取状态记录
8. 生成部署日志报告

─────── 当对话再次弹出时，一个验证完整无暇的成品应用已在链上 ───────
```

---

## 8. 安全规范与红线防范机制 (Security Considerations)

1. **涉密内容拦截（Private Key Handling）**：MCP Server 只通过环境变量从 `.cowboy/key` 获取密钥操作权限，禁止暴露至任何 StdOut 输出。
2. **熔断与用量管控（AI-Initiated Transaction Limits）**：配置硬顶如 `MAX_DEPLOYS_PER_SESSION = 10` 和 `MIN_BALANCE_THRESHOLD_CBY`。防止 AI 代理由于思维短路对测试网络和本地钱包账户的恶意消耗。
3. **前置屏障门禁（Code Validation Gate）**：`cowboy_deploy` 指令在内部执行时**绝对捆绑前置了 `cowboy_validate` 组件的执行要求**，不通过不准上链。这是不可妥协的防线配置。

---

## 9. 部署指南与环境对照 (Configuration Reference)

仅需要为 Remote 开发者完成少于 `5 分钟`的准备工作：

```bash
# 获取 SDK
pip install cowboy-sdk mcp

# 获取 Node 二进制环境 (不再依赖 Rust 发行版即可完成链交互与验签)
curl -L https://github.com/cowboylabs/cowboy/releases/latest/download/cowboy-linux-x86_64 -o ~/.local/bin/cowboy

# 获取 CADP
curl -L https://raw.githubusercontent.com/cowboylabs/cowboy/main/refs/dev_support/cowboy_mcp_server.py -o cowboy_mcp_server.py
curl -L https://..."..." -o CLAUDE.md
```

所有的设定通过 `mcp.json` 的 ENV 结构声明向外开放（支持 `RPC_URL`, `COWBOY_WORKSPACE`, `MAX_DEPLOYS_PER_SESSION` 等高度的配置弹性）。

---

## 10. 实施进展 (Implementation Phases)

* **Phase 1 (Foundation):** (✓已完成) SDK 打包完善、基本 CLI 调用和基于正则的 `cowboy_validate`，基本打通链路。 
* **Phase 2 (Verification Power):** (即将上线) 投入 `cowboy_simulate` 与 AST级别的复杂安全检测引擎，防灾级别加强。
* **Phase 3 ~ 4:** (远景规划) 全息追踪能力 `cowboy_trace` 和针对开发者易用性的自动补水发币等生命周期建设。
