# Cowboy Actor Vibe Coding Blueprint
## Claude Code + MCP Server 方案

**版本**: 1.0 | **日期**: 2026-03-09

---

## 一、愿景

> **任何一个会 Python 的开发者，无需了解区块链底层，用自然语言描述需求，10 分钟内把一个链上 AI Actor 部署到 Cowboy Devnet。**

Vibe Coding 是一种人机协同开发范式：开发者描述意图，AI 生成代码，工具链自动执行——部署、测试、修复形成闭环，无需人工介入每一步。
Cowboy Actor 开发的特殊之处在于 PVM 确定性约束（禁止 `import time/random`，FSM 编译，`capture()` 机制），这些知识正是 AI 助理最容易产生幻觉的地方。
本方案通过 **CLAUDE.md（知识注入）+ MCP Server（工具赋能）** 填平这个鸿沟。

---

## 二、架构全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                          开发者侧（本地）                              │
│                                                                       │
│  ┌─────────────────┐         ┌──────────────────────────────────┐    │
│  │   开发者浏览器   │         │         Claude Code              │    │
│  │  / 文本编辑器   │◄───────►│  (AI 编辑器，读取本地文件系统)    │    │
│  └─────────────────┘         └──────────────┬───────────────────┘    │
│                                              │ MCP stdio transport    │
│                                             ▼                         │
│                              ┌──────────────────────────────────┐    │
│                              │     cowboy_mcp_server.py          │    │
│                              │  ┌────────┐  ┌────────────────┐ │    │
│                              │  │validate│  │  sdk_docs      │ │    │
│                              │  ├────────┤  ├────────────────┤ │    │
│                              │  │deploy  │  │  status        │ │    │
│                              │  ├────────┤  ├────────────────┤ │    │
│                              │  │call    │  │  logs          │ │    │
│                              │  ├────────┤  └────────────────┘ │    │
│                              │  │query   │                      │    │
│                              │  └───┬────┘                      │    │
│                              └──────┼────────────────────────────┘    │
│                                     │ HTTP                             │
└─────────────────────────────────────┼───────────────────────────────┘
                                       │
               ┌───────────────────────┼─────────────────────────┐
               │            Cowboy Chain（远端）                   │
               │                       │                           │
               │         ┌─────────────▼──────────────┐           │
               │         │     cowboy CLI binary        │           │
               │         │  (secp256k1 签名 + 广播)     │           │
               │         └─────────────┬──────────────┘           │
               │                       │                           │
               │         ┌─────────────▼──────────────┐           │
               │         │     Devnet RPC / Indexer     │           │
               │         │  :4000  GET/POST endpoints   │           │
               │         └─────────────┬──────────────┘           │
               │                       │                           │
               │    ┌──────────────────┼──────────────────┐       │
               │    │                  │                   │       │
               │  ┌─▼──────┐    ┌─────▼────┐    ┌────────▼─┐    │
               │  │Validator│    │  Runner  │    │  Indexer │    │
               │  │  (PVM)  │    │(LLM/HTTP)│    │ (状态查询)│    │
               │  └─────────┘    └──────────┘    └──────────┘    │
               └──────────────────────────────────────────────────┘
```

---

## 三、知识注入层：CLAUDE.md

Claude Code 在项目目录启动时**自动读取** `CLAUDE.md`，将内容合并进系统提示。
这是让 AI 具备 Cowboy 领域知识的**零成本机制**，无需改动 Claude Code 本身。

```
CLAUDE.md 内容分层：

Layer 1 — PVM 铁律（10条不可违反的规则）
  ✗ import time  → ✓ from cowboy_sdk import pvm_time
  ✗ import random → ✓ from cowboy_sdk import pvm_random
  ✗ set()        → ✓ ordered_set
  ✗ >8 await     → ✓ 拆分函数
  ✗ await无capture → ✓ ctx = capture() BEFORE await
  ... 共10条

Layer 2 — Actor 结构模板
  @actor class + 模块级入口函数 + __resume 暴露方式

Layer 3 — 常用 API 速查
  self.storage, runtime.*, runner.*, capture()

Layer 4 — 部署命令参考
  cowboy actor deploy / execute 命令格式
```

**效果**：Claude Code 生成的代码自动符合 PVM 确定性规则，无需开发者记忆约束。

---

## 四、工具赋能层：MCP Server

MCP Server 将 Cowboy 操作封装为 Claude Code 可直接调用的 **7 个工具**，实现自主 DevOps 循环：

```
cowboy_sdk_docs(topic)          ← 查询 SDK 文档（16个主题）
        │
        ▼
cowboy_validate(code_path)      ← 语法检查 + PVM 规则 lint
        │
        ├── ❌ 有错误 → Claude 自动修复代码
        │
        ▼ ✅ 通过
cowboy_deploy(code_path, salt)  ← 签名 + 广播 → 返回 actor 地址
        │
        ▼
cowboy_call(addr, handler, payload)   ← 写操作（init/transfer/chat）
        │
cowboy_query(addr, handler, payload)  ← 读操作（get_status/get_balance）
        │
cowboy_status(addr)             ← storage 全量 dump（CBOR 自动解码）
        │
cowboy_logs(addr, limit)        ← 链上 event 日志
```

CLI 探测顺序（无需 Rust）：
```
COWBOY_CLI_PATH env → PATH 中的 cowboy 二进制 → cargo run（本地开发者回退）
```

---

## 五、开发者侧文件结构

```
my-actor/
├── CLAUDE.md                    ← AI 知识注入（项目级规则，Claude Code 自动读取）
├── .mcp.json                    ← MCP Server 配置（Claude Code 自动加载）
├── cowboy_mcp_server.py         ← MCP Server 主程序
├── .cowboy/
│   ├── key                      ← secp256k1 私钥（gitignore!）
│   └── config.json              ← { "rpc_url": "http://..." }
├── cowboy.toml                  ← 项目配置
└── actors/
    ├── voting/
    │   └── main.py              ← Actor 代码（纯 Python）
    └── token/
        └── main.py
```

---

## 六、完整 Vibe Coding 循环

### 场景：开发者想要一个 LLM 驱动的链上分析师 Actor

```
开发者：
"创建一个分析师Actor，用户输入一段股票描述，
Actor 调用 LLM 分析风险等级（high/medium/low），
结果存链上，并触发链上事件。"

──── 以下由 Claude Code 自主完成 ────

Step 1: 查文档
  cowboy_sdk_docs("continuation")   # 学习 @runner.continuation 用法
  cowboy_sdk_docs("rules")          # 确认 PVM 约束

Step 2: 生成代码
  [写入 actors/analyst/main.py]
  - @actor class AnalystActor
  - @runner.continuation async def analyze(self, payload)
  - ctx = capture(); ctx.query = ...
  - result = await runner.llm(prompt)
  - self.storage[f"risk:{chat_id}"] = result
  - runtime.emit_event("analysis.done", {...})
  - 模块级入口函数 + analyze__resume

Step 3: 验证
  cowboy_validate("actors/analyst/main.py")
  → "⚠️ Line 23: missing runtime.charge_gas()"
  [自动修复]
  cowboy_validate("actors/analyst/main.py")
  → "✅ All checks passed"

Step 4: 部署
  cowboy_deploy("actors/analyst/main.py")
  → "✅ Deployed! Actor: 0xA1b2...C3d4"

Step 5: 初始化
  cowboy_call("0xA1b2...C3d4", "init", '{}')
  → "✅ ok: initialized"

Step 6: 功能测试
  cowboy_call("0xA1b2...C3d4", "analyze",
    '{"description": "Tesla Q4 earnings miss by 15%"}')
  → "✅ Called analyze on 0xA1b2..."
  # （LLM job 已提交，等待 Runner 回调）

Step 7: 验证结果（几个区块后）
  cowboy_query("0xA1b2...C3d4", "get_risk", '{"id": 0}')
  → '{"risk": "high", "reason": "earnings miss significant"}'

  cowboy_status("0xA1b2...C3d4")
  → risk:0           = {"risk": "high", "reason": "..."}
     analysis_count  = 1
     owner           = "0xabc..."

  cowboy_logs("0xA1b2...C3d4", 5)
  → [block#1234] analysis.done: {"id": 0, "risk": "high"}

──── 开发者获得结果 ────

开发者：
"很好，现在给它加上访问频率限制，
每个地址每小时只能调用3次。"

──── Claude 继续修改、验证、重新部署 ────
```

---

## 七、远程开发者安装路径

```
5步，10分钟，零Rust，零本地链：

1. pip install cowboy-sdk
   └── 获得 cowboy_sdk Python 包

2. curl .../cowboy-linux-x86_64 -o cowboy && chmod +x cowboy
   └── 获得签名/广播 CLI 工具

3. cowboy init dev
   └── 自动创建钱包 + 写 .cowboy/config.json + 领水龙头资金

4. 下载 CLAUDE.md 和 cowboy_mcp_server.py
   写 .mcp.json，填入 RPC_URL

5. claude code .
   └── 开始 Vibe Coding
```

---

## 八、平台侧需要提供的基础设施

| 基础设施 | 当前状态 | 说明 |
|---------|---------|------|
| Devnet RPC (`validator-01.dev.cowboylabs.net:4000`) | ✅ 已有 | 对外开放 |
| Faucet (`POST /faucet`) | ✅ 已有 | `cowboy init dev` 自动调用 |
| `cowboy_sdk` PyPI 包 | 🔜 待发布 | `pip install cowboy-sdk` |
| `cowboy` CLI 预编译二进制 | 🔜 待发布 | Linux/macOS GitHub Releases |
| `CLAUDE.md` 公开下载 URL | 🔜 待配置 | GitHub raw 链接 |
| `cowboy_mcp_server.py` 公开下载 URL | 🔜 待配置 | GitHub raw 链接 |

---

## 九、设计原则回顾

**1. 知识在边界注入，不在 LLM 训练**
CLAUDE.md 是运行时注入，无需 fine-tune，可随 SDK 版本同步更新。

**2. 工具闭环，不依赖人工中转**
MCP Server 让 AI 自主完成 validate → deploy → call → verify，开发者只需描述 What，不需要操心 How。

**3. 零基础设施假设**
远程开发者不需要 Rust、不需要 Docker、不需要本地链节点。
SDK 是纯 Python，CLI 是单文件二进制，RPC 在云端。

**4. 错误在 AI 侧消化，不透传给开发者**
`cowboy_validate` 把 PVM 违规转化为 AI 可读的修复提示，
而不是让开发者看 cryptic VM execution failure。

**5. 模板降低幻觉空间**
`simple_actor.py` / `llm_actor.py` / `token_actor.py` 三个模板
给 AI 提供有约束的起点，减少从空白生成导致的错误。

---

## 十、文件索引

| 文件 | 用途 |
|------|------|
| `refs/dev_support/cowboy_sdk_developer_manual.md` | 完整 SDK 参考手册（16章） |
| `refs/dev_support/remote_developer_guide.md` | 远程开发者 10 分钟上手指南 |
| `refs/dev_support/vibe_coding_guide.md` | Vibe Coding 使用方法 + 示例 prompt |
| `refs/dev_support/mcp_server_guide.md` | MCP Server 配置与工具说明 |
| `refs/dev_support/cowboy_mcp_server.py` | MCP Server 主程序 |
| `refs/dev_support/templates/simple_actor.py` | 最小 Actor 模板 |
| `refs/dev_support/templates/llm_actor.py` | LLM 对话 Actor 模板 |
| `refs/dev_support/templates/token_actor.py` | CIP-20 Token Actor 模板 |
| `refs/dev_support/templates/deploy.sh` | 通用部署脚本 |
| `CLAUDE.md`（workspace 根） | Claude Code AI 规则注入 |
