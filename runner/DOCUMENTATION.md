# Cowboy Runner 文档大全

本文档整合 Runner 项目根目录下所有使用与排错说明，便于查阅。

---

## 目录

1. [项目概述](#1-项目概述)
2. [快速开始](#2-快速开始)
3. [Runner 注册](#3-runner-注册)
4. [查询 Runner 与 RPC](#4-查询-runner-与-rpc)
5. [Job 提交与 job_id](#5-job-提交与-job_id)
6. [故障排除](#6-故障排除)
7. [历史修复说明（参考）](#7-历史修复说明参考)

---

## 1. 项目概述

### 架构

- **链上组件（System Actors）**：Runner Registry、Job Dispatcher、Result Verifier、Secrets Manager、TEE Verifier 等，负责注册、派单、验证。
- **链下组件**：Runner 节点（`runner-node`），执行 LLM、HTTP、MCP 等任务。

### 目录结构

```
runner/
├── crates/
│   ├── runner-common/     # 共享类型与工具
│   ├── runner-node/       # Runner 节点核心（key_manager, registration, node）
│   ├── runner-llm/        # LLM 执行器
│   ├── runner-http/       # HTTP 执行器
│   ├── runner-mcp/        # MCP 执行器
│   ├── chain-client/      # 与链通信
│   └── ...
├── data/                  # runner_key.json 等
├── scripts/               # 提交任务、获取 job_id、检查系统 Actor 等
└── DOCUMENTATION.md       # 本文档
```

### 设计原则

- 可验证性、模块化、安全、可观测。

---

## 2. 快速开始

### 启动 Runner 节点

```bash
cd runner
RUST_LOG=info cargo run
```

- 首次运行会在 `data/runner_key.json` 生成密钥；Runner 地址会打印在日志中。
- 自动注册目前为占位实现，**需用 CLI 手动注册**（见下文）。

### 前置条件

- 链节点（validator）已启动，RPC 默认 `http://localhost:4000`。
- 如需提交 Job，需先完成 Runner 注册。

---

## 3. Runner 注册

### 3.1 命令格式（重要）

`--rpc-url` 必须写在 **`runner` 子命令之后、子命令（如 `register`）之前**：

```bash
# ✅ 正确
cowboy runner --rpc-url http://localhost:4000 register --private-key <KEY> --stake 50000

# ❌ 错误（会报 unexpected argument '--rpc-url'）
cowboy runner register --rpc-url http://localhost:4000 --private-key <KEY> --stake 50000
```

### 3.2 基本注册流程

```bash
cd node/cli

# 使用默认 RPC (http://localhost:4000)
cargo run --bin cowboy runner register \
  --private-key ../../runner/data/runner_key.json \
  --stake 50000

# 指定 RPC
cargo run --bin cowboy runner --rpc-url http://localhost:4000 register \
  --private-key ../../runner/data/runner_key.json \
  --stake 50000
```

### 3.3 参数说明

| 参数 | 说明 |
|------|------|
| `--private-key` | 私钥文件：支持 `runner_key.json` 或 32 字节 hex 文件 |
| `--stake` | 质押 CBY 数量，链上最小约 50,000 CBY |
| `--rpc-url` | 链 RPC，默认 `http://localhost:4000` |
| `--nonce` | 0 表示自动查询当前 nonce |

### 3.4 注册数据约定（链上反序列化）

- **stake**：支持数字或字符串（链上已兼容）。
- **health**：必须为小写枚举值之一：`healthy`、`unhealthy`、`paused`、`deregistered`。  
  CLI 已使用 `"health": "healthy"`；若曾改为 `"Healthy"` 会导致 `InvalidData`。

### 3.5 验证注册

```bash
# 用 CLI
cowboy runner get --address 0x<你的公钥 64 位 hex>

# 用 curl
curl "http://localhost:4000/runner/0x<公钥>"
```

---

## 4. 查询 Runner 与 RPC

### 4.1 CLI 示例

```bash
# 查询单个 Runner（注意 --rpc-url 位置）
cowboy runner --rpc-url http://localhost:4000 get --address 0x<ADDRESS>

# 列出活跃 Runner
cowboy runner --rpc-url http://localhost:4000 list
```

### 4.2 RPC 端点（curl）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/runner/{address}` | GET | 查询 Runner 信息 |
| `/runner/{address}/jobs` | GET | 该 Runner 分配的任务 |
| `/runner/{address}/heartbeat` | POST | 心跳（一般由节点自动发） |
| `/runners/active` | GET | 所有活跃 Runner |

地址为 **32 字节 Ed25519 公钥**，十六进制 64 字符，可带或不带 `0x`。

### 4.3 常见错误

- **Connection refused**：用了错误端口；Runner/Job 相关请用 RPC（默认 4000），不要用 indexer（8080）。
- **Runner not found**：未注册或地址错误；先完成注册再查。
- **Runner Registry not initialized**：链上 Runner 系统 Actor 未初始化，需检查 genesis 与链节点版本（见故障排除）。

---

## 5. Job 提交与 job_id

### 5.1 job_id 来源

链在交易上链后生成：`job_id = SHA256(tx_hash || block_height)`。  
因此需先有 **交易哈希** 和 **该交易的 block_height**（从交易收据获取）。

### 5.2 用脚本获取 job_id（推荐）

```bash
# 提交任务（示例）
./scripts/submit_crypto_job.sh http://localhost:4000 <付款人公钥> BTC

# 记下输出的 Transaction hash，等待几秒后：
cd runner/scripts
python3 get_job_id.py http://localhost:4000 <tx_hash>
# 或
./get_job_id.sh http://localhost:4000 <tx_hash>
```

### 5.3 手动计算

1. 请求：`GET /transaction/<tx_hash>/receipt`，从响应取 `block_height`。
2. `job_id = SHA256(tx_hash_bytes || block_height.to_bytes(8, 'big'))`。
3. 用该 job_id 查询：`GET /job/<job_id>/status` 等。

### 5.4 Job 相关 RPC

- 提交：通过链上交易 `SystemInstruction::JobSubmit`。
- 状态：`/job/<job_id>/status`
- 结果：`/job/<job_id>/results`

---

## 6. 故障排除

### 6.1 注册交易报 InvalidData

- **现象**：`/transaction/<tx_hash>/receipt` 中 `"status": {"ExecutionError":"InvalidData"}`。
- **处理**：
  1. 看链节点（validator）日志，搜索 `Failed to deserialize RunnerRegistration`，会打印具体反序列化错误（如字段名、期望枚举值）。
  2. 常见原因：`health` 用了 `Healthy` 等非小写枚举；或其它字段类型/名称与链上不一致。按日志改 CLI 或链上反序列化逻辑。

### 6.2 Runner Registry / Job Dispatcher not initialized

- **现象**：查询 Runner 或 Job 时返回 “Runner Registry not initialized” 或 “Job Dispatcher not initialized”。
- **说明**：Runner 系统 Actor 应在 genesis 时初始化（见 `node/chain` 的 genesis 与 storage 初始化）。
- **处理**：
  1. 确认链版本与代码已包含 Runner 系统 Actor 的 genesis 初始化（如 `create_runner_system_actors` / `initialize_genesis_accounts` 中初始化 Actor）。
  2. 新链或可接受清空数据时：停链 → 清空链数据目录 → 用当前代码重新启动，让 genesis 重新执行。
  3. 检查脚本：`runner/scripts/check_system_actors.sh <rpc_url>`。
- **注意**：查询系统 Actor 时，地址为 **32 字节 Ed25519 公钥**（如由 `node/runner` 的 `print_system_actors` 输出），不是 20 字节地址。

### 6.3 修改链或 Runner 代码后不生效

- 链节点：重新 `cargo build`（或 `--release`）并**重启** validator。
- CLI：重新 `cargo build --bin cowboy` 后再执行注册。

### 6.4 账户余额 / 质押不足

- 注册会锁定质押；若报余额或质押相关错误，请确保账户余额 ≥ 质押 + gas，且质押满足链上最小要求（如 50,000 CBY）。

---

## 7. 历史修复说明（参考）

以下为历史上已修复问题的简要记录，便于排查类似现象时参考。

| 主题 | 要点 |
|------|------|
| **Stake 反序列化** | 链上已支持 stake 为数字或字符串；若仍报错，检查 CLI 发送的 JSON。 |
| **health 枚举** | 必须为小写：`healthy` / `unhealthy` / `paused` / `deregistered`。 |
| **--rpc-url 位置** | 必须写在 `cowboy runner` 与 `register`（或 `get`/`list`）之间。 |
| **Runner Address** | 使用 Ed25519 公钥（32 字节），由 KeyManager 持久化在 `data/runner_key.json`。 |
| **系统 Actor 地址** | 查询 `/actor/{address}` 时使用 32 字节公钥；可用 `node/runner` 的 `print_system_actors` 查看正确地址。 |
| **Job Dispatcher 存在但报未初始化** | 多为存储/读写视图不一致；确保 genesis 正确初始化并重启链。 |

---

## 相关文档与脚本

- **架构与流程**：`refs/runner/NODE_ACTOR_RUNNER_FLOW.md`
- **MCP 接入**：`refs/runner/MCP_INTEGRATION.md`、`refs/runner/QUICK_START_MCP.md`
- **脚本**：`scripts/submit_crypto_job.sh`、`scripts/get_job_id.py`、`scripts/check_system_actors.sh`
- **链节点**：validator 二进制来自 `node/chain`（包名 `cowboy-chain`），见 `node/chain/VALIDATOR_VS_COWBOY_CHAIN.md`

本文档替代原根目录下多份零散说明；若某处与代码不一致，以代码与链上行为为准。
