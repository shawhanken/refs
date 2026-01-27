# Runner 系统文档

## 📋 概述

Runner 系统是 Cowboy 链的核心创新，提供**可验证的链下计算市场**。Runner 节点是完全独立运行的链下服务，通过 JSON-RPC 2.0 协议与链上 System Actors 通信，执行 LLM 推理、HTTP 请求、MCP 工具调用等链下任务。

### 核心特性

- ✅ **独立性**：Runner 节点完全独立运行，不依赖 Node 或 PVM
- ✅ **可扩展性**：插件化执行器架构，易于添加新任务类型
- ✅ **可靠性**：完整的错误处理和重试机制
- ✅ **安全性**：多层验证机制，支持 TEE
- ✅ **可观测性**：完整的日志和监控接口

### 系统架构

```
┌─────────────────────────────────────────┐
│      Cowboy Chain (On-Chain)            │
│  - Runner Registry (0x91)               │
│  - Job Dispatcher (0x92)                │
│  - Result Verifier (0x93)                │
└──────────────┬──────────────────────────┘
               │ JSON-RPC 2.0 (HTTP)
               │
┌──────────────▼──────────────────────────┐
│      Runner Network (Off-Chain)          │
│  - Runner Node                           │
│  - HTTP Executor                         │
│  - LLM Executor                          │
└─────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 编译项目

```bash
cargo build --release
```

### 2. 配置环境变量（可选）

```bash
# 链节点 RPC URL（默认：http://localhost:4000）
export CHAIN_RPC_URL=http://localhost:4000

# LLM API 密钥（可选）
export OPENAI_API_KEY=your_key
export ANTHROPIC_API_KEY=your_key
```

### 3. 运行 Runner 节点

```bash
# 使用默认配置
cargo run --bin runner-node

# 或使用自定义日志级别
RUST_LOG=info cargo run --bin runner-node
```

### 4. 验证运行状态

启动后，你会看到类似输出：

```
INFO runner_node: Starting Cowboy Runner Node
INFO runner_node: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INFO runner_node: Chain RPC URL: http://localhost:4000
INFO runner_node: Runner Address: 0x0000000000000000000000000000000000000000
INFO runner_node: Max Concurrent Jobs: 10
INFO runner_node: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INFO runner_node::node: Testing connection to chain node...
INFO runner_node::node: ✅ Successfully connected to chain node at block 12345
INFO runner_node::node: 🚀 Runner node is now running. Waiting for jobs...
```

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CHAIN_RPC_URL` | 链节点 RPC 端点 | `http://localhost:4000` |
| `OPENAI_API_KEY` | OpenAI API 密钥 | - |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | - |
| `RUST_LOG` | 日志级别 | `info` |

### 配置参数

Runner 节点支持以下配置（通过代码配置）：

- `heartbeat_interval_seconds`：心跳间隔（默认：10 秒）
- `job_poll_interval_seconds`：任务轮询间隔（默认：1 秒）
- `max_concurrent_jobs`：最大并发任务数（默认：10）

## 📖 使用指南

### 任务类型

#### HTTP 任务

HTTP 执行器支持：
- HTTP 方法：GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS
- 自定义 HTTP 头
- 数据提取：CSS 选择器、XPath、JSONPath、正则表达式
- 新鲜度检查
- 源证明生成（TLS 证书指纹、响应哈希等）

#### LLM 任务

LLM 执行器支持：
- **OpenAI API**：GPT-3.5、GPT-4 等模型
- **Anthropic API**：Claude 系列模型
- 资源计量：输入/输出 tokens、执行时间
- 响应格式验证：JSON Schema 验证

### 验证模式

Runner 系统支持 6 种验证模式：

1. **None**：无验证（仅开发/测试）
2. **Economic Bond**：经济担保模式
3. **Majority Vote**：多数投票（N-of-M）
4. **Structured Match**：结构化匹配（JSON Schema、字段匹配）
5. **Deterministic**：确定性验证（需要 TEE）
6. **Semantic Similarity**：语义相似度验证

### 工作流程

1. **Runner 注册**：Runner 启动时注册到链上 Runner Registry
2. **任务轮询**：Runner 定期轮询 Job Dispatcher 获取分配的任务
3. **任务执行**：Runner 使用相应的执行器执行任务
4. **结果提交**：Runner 将结果提交到 Result Verifier
5. **结果验证**：链上验证结果并回调原始 Actor

## 🔌 API 参考

### Chain Client API

#### `get_assigned_jobs`

获取分配给指定 Runner 的任务列表。

```rust
async fn get_assigned_jobs(
    &self,
    runner_address: RunnerAddress,
) -> Result<Vec<JobSpec>, ChainClientError>;
```

#### `submit_result`

提交任务执行结果。

```rust
async fn submit_result(
    &self,
    job_id: JobId,
    result: RunnerResult,
) -> Result<(), ChainClientError>;
```

#### `register_runner`

注册 Runner 到链上。

```rust
async fn register_runner(
    &self,
    registration: RunnerRegistration,
    signature: Signature,
) -> Result<(), ChainClientError>;
```

#### `heartbeat`

发送心跳以保持 Runner 健康状态。

```rust
async fn heartbeat(
    &self,
    runner_address: RunnerAddress,
    current_block: BlockHeight,
) -> Result<(), ChainClientError>;
```

### System Actor 地址

| Actor | 地址 | 职责 |
|-------|------|------|
| Runner Registry | `0x0000...0091` | Runner 注册、健康检查 |
| Job Dispatcher | `0x0000...0092` | 任务分发、Runner 选择 |
| Result Verifier | `0x0000...0093` | 结果验证、共识聚合 |
| Secrets Manager | `0x0000...0008` | 密钥管理 |
| TEE Verifier | `0x0000...0097` | TEE 证明验证 |

## 🔧 故障排除

### 连接问题

#### 错误：`Connection refused (os error 111)`

**原因**：链节点未运行或端口不正确

**解决方案**：
1. 确认链节点正在运行
2. 检查 RPC URL：`echo $CHAIN_RPC_URL`
3. 测试连接：`curl http://localhost:4000`
4. Runner 会自动重试，等待链节点启动

#### 错误：`HTTP error: 404 Not Found`

**原因**：能连接到服务器，但 RPC 端点不存在

**解决方案**：
- 确认链节点已实现 `chain_callActor` RPC 方法
- 检查 System Actors 是否已部署

### 任务执行失败

检查清单：
- ✅ Runner 是否已注册
- ✅ 任务类型是否支持
- ✅ 资源边界是否合理
- ✅ API 密钥是否有效（LLM 任务）

### 日志控制

```bash
# 显示所有日志（默认）
RUST_LOG=info cargo run --bin runner-node

# 只显示错误和警告
RUST_LOG=warn cargo run --bin runner-node

# 显示详细调试信息
RUST_LOG=debug cargo run --bin runner-node
```

## 📊 实现状态

### ✅ 已完成功能

- [x] RPC 通信协议（JSON-RPC 2.0）
- [x] 任务分发和调度
- [x] 结果验证（6 种模式）
- [x] HTTP 执行器
- [x] LLM 执行器（OpenAI、Anthropic）
- [x] 健康检查和心跳
- [x] 错误处理和重试（指数退避）
- [x] 智能日志控制

### 🔄 待链节点集成

- [ ] 实际注册到链上
- [ ] 接收真实任务
- [ ] 提交结果到链上
- [ ] 与 System Actors 交互

### 🚧 未来增强

- [ ] 本地模型支持（ONNX、llama.cpp）
- [ ] TEE 集成（SGX、TDX、SEV）
- [ ] P2P 网络通信
- [ ] 结果缓存机制
- [ ] 监控仪表板

## 🏗️ 项目结构

```
runner/
├── Cargo.toml                    # 工作空间配置
├── src/main.rs                   # 主程序入口
├── crates/
│   ├── runner-common/            # 共享类型和工具
│   ├── runner-registry/          # Runner 注册表（链上）
│   ├── job-dispatcher/           # 任务分发器（链上）
│   ├── result-verifier/          # 结果验证器（链上）
│   ├── secrets-manager/          # 密钥管理器（链上）
│   ├── tee-verifier/             # TEE 验证器（链上）
│   ├── chain-client/             # 链客户端
│   ├── runner-node/              # Runner 节点核心
│   ├── runner-http/              # HTTP 执行器
│   ├── runner-llm/               # LLM 执行器
│   ├── runner-tee/               # TEE 运行时
│   └── runner-consensus/         # 共识客户端
└── docs/                         # 文档
```

## 🎯 性能优化

### 已实现优化

- ✅ **异步架构**：使用 Tokio 异步运行时
- ✅ **连接池**：HTTP 客户端复用连接
- ✅ **指数退避**：智能重试机制
- ✅ **资源限制**：最大并发任务数控制

### 优化建议

- 增加最大并发任务数（根据硬件调整）
- 调整心跳和轮询间隔（平衡响应性和资源使用）
- 启用结果缓存（未来功能）

## 📚 参考文档

- `refs/runner/RUNNER_SYSTEM_DESIGN.md` - 详细设计文档
- `refs/whitepaper/` - Cowboy 白皮书

## 🔗 Chain 与 Runner 集成

### 通信机制

Chain 与 Runner 通过 **JSON-RPC 2.0** 协议通信：

- **协议**：JSON-RPC 2.0 over HTTP
- **端点**：Chain Node 的 RPC 端口（默认 4000）
- **调用方式**：Runner 主动轮询链上 System Actors

### 集成流程

1. **Runner 注册**：Runner 启动时注册到 Runner Registry
2. **任务分发**：Actor 提交任务 → Job Dispatcher 分发 → Runner 轮询获取
3. **任务执行**：Runner 执行任务（完全独立，不依赖链）
4. **结果提交**：Runner 提交结果 → Result Verifier 验证 → 回调 Actor

### Chain 端需要实现

- [ ] System Actors（Runner Registry、Job Dispatcher、Result Verifier）
- [ ] RPC 端点（`chain_callActor` 方法）
- [ ] 任务分配逻辑

详细集成说明请参考设计文档。

---

**最后更新**：2026-01-24  
**状态**：✅ Runner 系统已完全实现，等待链节点集成
