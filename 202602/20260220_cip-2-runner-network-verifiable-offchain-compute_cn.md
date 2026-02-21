# CIP-2: Runner 网络 — 可验证链下计算市场

---

> **状态:** 草稿（基于代码实现修订）
> **类型:** Standards Track
> **类别:** Core
> **创建日期:** 2025-10-02
> **修订日期:** 2026-02-20
> **依赖:** CIP-1（延迟交易）

---

## 摘要

本提案定义了 **Runner 网络** — Cowboy 链的可验证异步链下计算市场。Runner 节点是**完全独立的链下服务**，通过 JSON-RPC 2.0 和 REST 协议与链上 System Actor 通信，执行 **LLM 推理、HTTP 请求、MCP（Model Context Protocol）工具调用** 以及自定义计算等链下任务（统称 "Job"）。

架构核心特征：

- **基于 VRF 的确定性 Runner 选择**（Keccak256 迭代哈希）
- **六种验证模式**，满足不同信任/成本权衡（None、EconomicBond、MajorityVote、StructuredMatch、Deterministic、SemanticSimilarity）
- **插件化执行器架构**，支持可扩展的任务类型
- **Ed25519 密码签名**，用于所有 Runner 与链的交互
- **RateCard 市场化定价**，配合声誉加权选择

---

## 动机

为了支持 AI/ML、大数据集、Web2 API 和智能体工具调用等高级用例，智能合约需要一个安全可靠的链下桥梁。本 CIP 提出了一种灵活的多模态方案，专为 Cowboy 链上 Python Actor 环境量身定制。

本框架使开发者能够：

1. **集成复杂逻辑：** 在链下运行 LLM 推理、HTTP 数据抓取、MCP 工具调用或自定义计算。
2. **选择信任模型：** 从六种验证模式中选择 — 从零验证（开发/测试）到确定性 TEE 证明 — 根据具体安全/成本需求。
3. **利用市场定价：** Runner 声明细粒度费率卡；开发者设定最大价格和优先小费；协议自动撮合。
4. **保持链上稳定：** 通过异步延迟回调（CIP-1）防止网络拥塞。
5. **实现可验证去中心化：** 利用 VRF 选择 + 多维过滤（能力、声誉、价格、TEE 支持）确保公平透明的 Runner 分配。

---

## 规范

### 1. 系统架构总览

框架由 **五个链上 System Actor** 和 **链下 Runner 网络** 组成：

```
┌──────────────────────────────────────────────────┐
│          Cowboy 链（链上 System Actors）           │
│                                                  │
│   Runner Registry ............ 0x00...0091       │
│   Job Dispatcher ............. 0x00...0092       │
│   Result Verifier ............ 0x00...0093       │
│   Secrets Manager ............ 0x00...0008       │
│   TEE Verifier ............... 0x00...0097       │
└─────────────────┬────────────────────────────────┘
                  │ JSON-RPC 2.0 / REST (HTTP)
                  │
┌─────────────────▼────────────────────────────────┐
│          Runner 网络（链下）                       │
│                                                  │
│   Runner 节点                                     │
│   ├── HTTP Executor                              │
│   ├── LLM Executor (OpenAI / Anthropic)          │
│   ├── MCP Executor (Stdio 传输)                   │
│   └── Custom Executor (V2)                       │
└──────────────────────────────────────────────────┘
```

**核心设计原则：** Runner 节点完全**独立**于 Node 和 PVM 进程，仅通过基于 HTTP 的 JSON-RPC 2.0 和 REST 端点与链交互。

---

### 2. 任务类型（Job Types）

每个链下任务定义为 `JobType` 枚举，系统当前支持四种类型：

#### 2.1 LLM 推理（`Llm`）

| 字段 | 类型 | 描述 |
|------|------|------|
| `model_id` | H256 | 模型哈希（32 字节） |
| `prompt` | String | 用户提示词 |
| `system_prompt` | Option\<String\> | 系统提示词（可选） |
| `temperature` | Option\<f64\> | 采样温度 |
| `max_tokens` | u32 | 最大输出 token 数 |
| `response_model` | Option\<JsonSchema\> | 结构化输出 schema（可选） |

#### 2.2 HTTP 请求（`Http`）

| 字段 | 类型 | 描述 |
|------|------|------|
| `url` | String | 目标 URL |
| `method` | HttpMethod | GET / POST / PUT / DELETE / PATCH / HEAD / OPTIONS |
| `headers` | HashMap\<String, String\> | HTTP 请求头 |
| `body` | Option\<Vec\<u8\>\> | 请求体 |
| `extraction` | Option\<ExtractionConfig\> | 数据提取方式（CssSelector / XPath / JsonPath / Regex） |
| `freshness` | Option\<FreshnessConfig\> | 新鲜度约束（Block / Submission / Absolute 参考点） |

#### 2.3 MCP 工具调用（`Mcp`）

| 字段 | 类型 | 描述 |
|------|------|------|
| `server` | String | MCP 服务器标识 |
| `tool_name` | String | 工具名称 |
| `arguments` | JSON Value | 工具参数 |
| `timeout_seconds` | Option\<u64\> | 执行超时 |

> **实现说明：** MCP 传输当前仅支持 **Stdio**。Http 和 WebSocket 传输类型在类型系统中已定义但尚未实现。

#### 2.4 自定义任务（`Custom`）

| 字段 | 类型 | 描述 |
|------|------|------|
| `executor_hash` | H256 | 自定义执行器标识 |
| `params` | Vec\<u8\> | 序列化参数 |

---

### 3. 任务规范（JobSpec）

每个提交到链上的任务包含以下规范：

| 字段 | 类型 | 描述 |
|------|------|------|
| `job_id` | H256 | 唯一任务标识（32 字节） |
| `job_type` | JobType | 上述四种任务类型之一 |
| `bounds` | ResourceBounds | 执行的资源限制 |
| `verification` | VerificationConfig | 验证模式和参数 |
| `max_price` | U256 | 提交者愿意支付的最高价格（CBY wei） |
| `tip` | U256 | 优先小费，用于更快被选中 |
| `timeout_blocks` | u64 | 超时区块高度 |
| `callback` | CallbackInfo | 回调 Actor 和处理方法信息 |
| `submitter` | PublicKey | 提交 Actor 的公钥（Ed25519，32 字节） |
| `submitted_at` | u64 | 提交时的区块高度 |

#### 3.1 资源限制（ResourceBounds）

| 字段 | 类型 | 描述 |
|------|------|------|
| `max_input_tokens` | u32 | 最大输入 token |
| `max_output_tokens` | u32 | 最大输出 token |
| `max_wall_time_seconds` | u64 | 最大执行时间 |
| `max_memory_mb` | u32 | 最大内存使用 |
| `max_retries` | u32 | 最大重试次数 |

#### 3.2 回调信息（CallbackInfo）

| 字段 | 类型 | 描述 |
|------|------|------|
| `actor` | PublicKey | 目标 Actor 地址（32 字节） |
| `handler` | String | 回调处理方法名 |
| `correlation_id` | String | 请求/响应关联 ID |
| `context` | Vec\<u8\> | 序列化的上下文数据 |

---

### 4. 验证系统

框架支持 **六种验证模式**，在成本、延迟和信任级别之间做出不同权衡：

#### 4.1 验证配置（VerificationConfig）

| 字段 | 类型 | 描述 |
|------|------|------|
| `mode` | VerificationMode | 以下六种模式之一 |
| `tee_required` | bool | 是否要求 TEE 证明 |
| `dispute_window_blocks` | u64 | 争议窗口（区块数） |

#### 4.2 验证模式

| 模式 | Runner 数 | 描述 |
|------|-----------|------|
| **None** | 1 | 无验证，直接接受第一个结果。*（仅限开发/测试）* |
| **EconomicBond** | 1 | 单 Runner 经济质押保证。可应用客观检查。*（客观检查：代码中为 TODO）* |
| **MajorityVote** | N（可配置） | N 个 Runner 独立执行；提取指定 `vote_field` 进行多数投票，需达到阈值。 |
| **StructuredMatch** | N（可配置） | N 个 Runner 执行；结果通过检查管线验证（JSON Schema 验证、字段匹配、数值容差、数值范围、字段级多数投票、自定义验证器 Actor）。 |
| **Deterministic** | N（可配置） | 所有结果必须字节一致。如设置 `tee_required`，则验证 TEE 证明。 |
| **SemanticSimilarity** | N（可配置） | 结果被嵌入为向量；计算余弦相似度；发现聚类；接受满足阈值的最大聚类。*（嵌入模型：占位实现，使用字符频率向量。TODO：集成真实嵌入模型。）* |

#### 4.3 StructuredMatch 检查类型

| 检查类型 | 描述 |
|----------|------|
| `JsonSchemaValid` | 根据 JSON Schema 验证结果 |
| `StructuredMatch` | 验证所有结果中指定字段值是否匹配 |
| `NumericTolerance` | 验证数值字段在容差范围内 |
| `NumericRange` | 验证数值字段在 [min, max] 范围内 |
| `MajorityVote` | 按字段的多数投票 |
| `Custom` | 调用链上自定义验证器 Actor *（代码中为 TODO）* |

#### 4.4 验证结果（VerifiedResult）

验证通过后产生 `VerifiedResult`：

| 字段 | 类型 | 描述 |
|------|------|------|
| `data` | JSON Value | 被接受的结果数据 |
| `consensus_count` | u32 | 达成一致的 Runner 数量 |
| `total_runners` | u32 | 提交结果的总 Runner 数量 |
| `verification_mode` | VerificationMode | 使用的验证模式 |

---

### 5. Runner 注册表（System Actor: `0x00...0091`）

管理 Runner 身份、质押、能力、费率卡、健康状态和声誉。

#### 5.1 Runner 注册信息

| 字段 | 类型 | 描述 |
|------|------|------|
| `address` | PublicKey | Runner 地址（Ed25519 公钥，32 字节） |
| `public_key` | PublicKey | Runner 公钥 |
| `stake` | U256 | 质押金额（CBY）。最低：10,000 CBY *（注册合约常量）* |
| `rate_card` | RateCard | 定价声明 |
| `capabilities` | RunnerCapabilities | 能力声明 |
| `health` | HealthStatus | 当前健康状态 |
| `registered_at` | u64 | 注册区块高度 |
| `last_heartbeat` | u64 | 最后心跳区块高度 |
| `reputation` | u8 | 声誉分数（0–100） |
| `active_jobs` | u32 | 当前活跃任务数 |

> **注意：** `main.rs` 在自动注册时使用 50,000 CBY 作为最低质押，而注册合约定义为 10,000 CBY。此差异存在于代码库中；权威值以链上注册合约常量（10,000 CBY）为准。

#### 5.2 费率卡（RateCard）

Runner 通过 `RateCard` 声明定价：

| 字段 | 类型 | 描述 |
|------|------|------|
| `llm_input_token` | U256 | 每 LLM 输入 token 价格（CBY wei） |
| `llm_output_token` | U256 | 每 LLM 输出 token 价格（CBY wei） |
| `http_request_base` | U256 | 每次 HTTP 请求基础价格 |
| `mcp_call_base` | U256 | 每次 MCP 工具调用基础价格 |
| `compute_second` | U256 | 每计算秒价格 |
| `memory_mb` | U256 | 每 MB 内存价格 |
| `supported_models` | Vec\<H256\> | 支持的 LLM 模型哈希 |
| `supported_mcp_servers` | Vec\<String\> | 支持的 MCP 服务器 |
| `min_job_value` | U256 | 接受的最低任务价值 |
| `max_job_value` | U256 | 接受的最高任务价值 |
| `cooldown_blocks` | u64 | 费率卡更新冷却期（区块数） |
| `last_updated` | u64 | 最后更新区块高度 |

#### 5.3 Runner 能力（RunnerCapabilities）

| 字段 | 类型 | 描述 |
|------|------|------|
| `job_types` | Vec\<String\> | 支持的任务类型标识：`"llm"`、`"http"`、`"mcp_{server}_{tool}"`、`"custom_0x..."` |
| `tee_support` | Option\<TeeType\> | TEE 类型（若支持）：`Sgx`、`Tdx` 或 `Sev` |
| `regions` | Vec\<String\> | 地理区域 |
| `http_domains` | Vec\<String\> | 可访问的 HTTP 域名（`"*"` 表示全部） |
| `max_concurrent_jobs` | u32 | 最大并发任务容量 |

#### 5.4 健康管理

Runner 健康状态基于 **心跳超时检查** 确定：

| 状态 | 描述 |
|------|------|
| `Healthy` | 在超时窗口内收到心跳 |
| `Unhealthy` | 超时窗口内未收到心跳（默认：**100 区块**） |
| `Paused` | Runner 主动暂停 |
| `Deregistered` | Runner 已取消注册 |

健康检查器比较 `current_block - last_heartbeat` 与 `heartbeat_timeout_blocks`。超过则标记为 `Unhealthy`，排除出任务分配。

#### 5.5 注册表接口

| 方法 | 描述 |
|------|------|
| `register_runner(registration, signature)` | 注册新 Runner。验证：签名、最低质押、费率卡、唯一性。 |
| `update_rate_card(runner, new_rate_card, current_block)` | 更新费率卡。强制冷却期。 |
| `heartbeat(runner, current_block)` | 存活信号。更新 `last_heartbeat` 并重新评估健康状态。 |
| `get_active_runners(filter, current_block)` | 多维过滤查询活跃 Runner。 |
| `select_committee(job_spec, vrf_seed, current_block)` | 通过 VRF 选择 Runner 委员会。 |
| `update_reputation(runner, delta)` | 调整声誉分数（限制在 0–100）。 |
| `get_runner(address)` | 查询单个 Runner 的注册信息。 |
| `deregister_runner(runner)` | 取消注册 Runner（设置健康状态为 `Deregistered`）。 |

---

### 6. 任务调度器（System Actor: `0x00...0092`）

负责接收任务提交、选择 Runner 委员会、分配任务和管理超时。

#### 6.1 核心工作流

```
 Actor 提交 Job
       │
       ▼
 ┌─────────────┐
 │ 验证 JobSpec │  检查：bounds ≠ 0、max_price > 0、timeout > 0
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │ 生成 VRF    │  seed = Keccak256(job_id ‖ current_block ‖ submitter)
 │ 种子        │
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │ 选择        │  多维过滤 + VRF 选择
 │ 委员会      │
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │ 入队 + 分配 │  将任务分配给选中的 Runner
 └──────┬──────┘
        │
        ▼
  JobStatus::Assigned
```

#### 6.2 任务状态生命周期

| 状态 | 描述 |
|------|------|
| `Pending` | 已提交，等待分配 |
| `Assigned { runners, assigned_at }` | 已分配给 Runner 委员会 |
| `Executing { runners, started_at }` | Runner 正在执行 |
| `Completed { result, completed_at }` | 验证通过，`VerifiedResult` 可用 |
| `Timeout { timeout_at }` | 在 `timeout_blocks` 内未提交结果 |
| `Failed { reason, failed_at }` | 执行或验证失败 |

> **注意：** 系统中不存在显式的 `skip_task` 机制。如果被选中的 Runner 未执行任务，任务将在 `timeout_blocks` 到期后转为 `Timeout` 状态。

#### 6.3 调度器接口

| 方法 | 描述 |
|------|------|
| `submit_job(job_spec, current_block)` | 提交任务，返回 `job_id`。 |
| `get_assigned_jobs(runner)` | 获取分配给某 Runner 的所有任务。 |
| `process_timeouts(current_block)` | 扫描并转换超时任务。 |
| `get_job_status(job_id)` | 查询任务状态。 |

---

### 7. 基于 VRF 的 Runner 选择

选择过程使用 **Keccak256 迭代哈希**，配合多维预过滤。

#### 7.1 预选过滤

在 VRF 选择前，候选 Runner 必须满足**所有**以下条件：

| 过滤器 | 条件 |
|--------|------|
| 健康状态 | `HealthStatus::Healthy`（心跳在超时窗口内） |
| 声誉 | `reputation ≥ 50`（最低阈值） |
| 任务类型 | Runner 的 `capabilities.job_types` 包含所需类型 |
| TEE | 如 `tee_required`，Runner 必须有 `tee_support` |
| 模型 | LLM 任务：`rate_card.supported_models` 包含请求的 `model_id` |
| 域名 | HTTP 任务：`capabilities.http_domains` 包含目标域名（或 `"*"`） |
| MCP 服务器 | MCP 任务：`rate_card.supported_mcp_servers` 包含该服务器（或 `"*"`） |
| 价格 | 预估成本 ≤ `job_spec.max_price` 且在 Runner 的 `[min_job_value, max_job_value]` 范围内 |
| 并发 | `active_jobs < max_concurrent_jobs` |

#### 7.2 VRF 选择算法

```
输入：candidates[], required_count, seed[32]

selected = []
used_indices = {}
current_seed = seed

while |selected| < required_count AND |used_indices| < |candidates|:
    hash = Keccak256(current_seed ‖ |selected|.to_le_bytes())
    index = u64_from_le_bytes(hash[0..8]) % |candidates|

    if index ∉ used_indices:
        selected.append(candidates[index].address)
        used_indices.add(index)

    current_seed = hash

return selected
```

#### 7.3 所需 Runner 数量

Runner 数量由 `VerificationMode` 决定：

| 模式 | 所需 Runner 数 |
|------|---------------|
| None | 1 |
| EconomicBond | 1 |
| MajorityVote | `runners` 字段 |
| StructuredMatch | `runners` 字段 |
| Deterministic | `runners` 字段 |
| SemanticSimilarity | `runners` 字段 |

---

### 8. 结果验证器（System Actor: `0x00...0093`）

接收 Runner 结果，根据任务的 `VerificationConfig` 执行验证，生成 `VerifiedResult`。

#### 8.1 验证器接口

| 方法 | 描述 |
|------|------|
| `submit_result(job_id, result)` | Runner 提交执行结果 |
| `verify_results(job_spec, results)` | 验证收集的结果并生成 `VerifiedResult` |

#### 8.2 Runner 结果结构

| 字段 | 类型 | 描述 |
|------|------|------|
| `runner` | PublicKey | Runner 地址 |
| `job_id` | H256 | 任务标识 |
| `data` | JSON Value | 结果数据 |
| `usage` | ResourceUsage | 实际资源消耗 |
| `tee_attestation` | Option\<TeeAttestation\> | TEE 证明（如适用） |
| `source_attestation` | Option\<SourceAttestation\> | HTTP 任务的来源证明 |
| `timestamp` | DateTime\<Utc\> | 执行时间戳 |
| `signature` | Signature | Ed25519 签名（64 字节） |

#### 8.3 资源使用量（ResourceUsage）

| 字段 | 类型 | 描述 |
|------|------|------|
| `input_tokens` | u32 | 实际输入 token 消耗 |
| `output_tokens` | u32 | 实际输出 token 消耗 |
| `wall_time_seconds` | u64 | 实际执行时间 |
| `memory_mb` | u32 | 实际内存使用 |

#### 8.4 来源证明（HTTP 任务的 SourceAttestation）

| 字段 | 类型 | 描述 |
|------|------|------|
| `fetch_timestamp` | DateTime\<Utc\> | 数据获取时间 |
| `url` | String | 来源 URL |
| `http_status` | u16 | HTTP 响应状态码 |
| `response_hash` | H256 | 原始响应哈希 |
| `tls_cert_fingerprint` | Option\<H256\> | TLS 证书指纹 |
| `response_headers` | HashMap\<String, String\> | 响应头 |

---

### 9. 密钥管理器（System Actor: `0x00...0008`）

为 Actor 安全存储和管理密钥，支持 TEE 门控访问控制。

#### 9.1 接口

| 方法 | 描述 |
|------|------|
| `store_secret(actor, key, value, access_policy)` | 存储加密密钥 |
| `get_secret(runner, actor, key, tee_attestation)` | 获取密钥（需要 TEE 证明才能解密） |
| `update_secret(actor, key, value)` | 更新现有密钥 |
| `delete_secret(actor, key)` | 删除密钥 |

#### 9.2 访问策略（AccessPolicy）

| 字段 | 类型 | 描述 |
|------|------|------|
| `runners` | Vec\<String\> | 允许的 Runner（如仅限 TEE Runner） |
| `entitlements` | Vec\<String\> | 所需权限 |
| `job_types` | Vec\<String\> | 允许的任务类型 |

> **实现状态：** Secrets Manager 的 trait 和数据结构已完整定义。实现目前包含占位逻辑（`TODO` 存根）。实际的加密存储和 TEE 验证检索尚未实现。

---

### 10. TEE 支持

#### 10.1 TEE 验证器（System Actor: `0x00...0097`）

验证 Runner 提交的 TEE 证明。支持三种 TEE 类型：

| TEE 类型 | 描述 |
|----------|------|
| `Sgx` | Intel SGX |
| `Tdx` | Intel TDX |
| `Sev` | AMD SEV |

#### 10.2 TEE 证明结构

| 字段 | 类型 | 描述 |
|------|------|------|
| `tee_type` | TeeType | SGX / TDX / SEV |
| `attestation_data` | Vec\<u8\> | 原始证明数据 |
| `measurement_hash` | H256 | 度量哈希 |
| `signature` | Vec\<u8\> | 证明签名 |

> **实现状态：** TEE Runtime（`execute_in_tee`）和 TEE Attestation Generator（`generate_attestation`）接口已定义，但两者均返回"未实现"错误。TEE 数据结构（`TeeAttestation`、`TeeType`）已完整定义并集成到验证管线中。

---

### 11. Runner 与链的通信

Runner 节点通过两种协议与链通信：

#### 11.1 REST API 端点

| 端点 | HTTP 方法 | 描述 |
|------|-----------|------|
| `/runner/{address}/jobs` | GET | 获取分配给此 Runner 的任务 |
| `/runner/{address}/heartbeat` | POST | 发送心跳 |
| `/runner/{address}/job_result_payload` | GET | 获取需签名的结果提交载荷 |
| `/runner/{address}/job_result` | POST | 提交签名后的结果 |
| `/height` | GET | 获取当前区块高度 |
| `/account/{address}` | GET | 获取账户信息（nonce 等） |

#### 11.2 结果提交流程

结果提交使用 **先签名后提交** 的模式，Ed25519 签名（通过 `ed25519-consensus`，与链的 `commonware` 验证兼容）：

```
1. Runner 序列化结果 → base64

2. GET /runner/{address}/job_result_payload
   ?job_id={job_id}&result_base64={result}&nonce={nonce}
   → 返回: { message_to_sign_base64: "..." }

3. Runner 用 Ed25519 私钥签名该消息

4. POST /runner/{address}/job_result
   Body: { job_id, result, result_base64, nonce, signature }
```

Nonce 管理确保防重放保护并支持并发提交。

#### 11.3 JSON-RPC 2.0 方法

用于直接调用 System Actor：

| 方法 | 目标 Actor | 描述 |
|------|-----------|------|
| `runner_registry_register` | Registry (0x91) | 注册 Runner |
| `runner_registry_update_rate_card` | Registry (0x91) | 更新费率卡 |
| `runner_registry_heartbeat` | Registry (0x91) | 心跳 |
| `runner_registry_get_runner` | Registry (0x91) | 查询 Runner 信息 |
| `job_dispatcher_submit_job` | Dispatcher (0x92) | 提交任务 |
| `job_dispatcher_get_assigned_jobs` | Dispatcher (0x92) | 获取分配的任务 |
| `job_dispatcher_get_job_status` | Dispatcher (0x92) | 获取任务状态 |
| `result_verifier_submit_result` | Verifier (0x93) | 提交结果 |
| `result_verifier_verify_results` | Verifier (0x93) | 验证结果 |
| `chain_getCurrentBlock` | — | 获取当前区块 |
| `chain_callActor` | — | 通用 Actor 调用 |

---

### 12. 执行器插件架构

Runner 节点使用插件式执行器系统。新的任务类型可在运行时注册。

#### 12.1 JobExecutor Trait

```rust
#[async_trait]
pub trait JobExecutor: Send + Sync {
    /// 执行任务并返回结果
    async fn execute(&self, job_spec: &JobSpec) -> Result<RunnerResult, ExecutorError>;

    /// 预估执行成本
    fn estimate_cost(&self, job_spec: &JobSpec) -> U256;

    /// 执行前验证资源限制
    fn validate_bounds(&self, job_spec: &JobSpec) -> Result<(), ExecutorError>;
}
```

#### 12.2 执行器注册表

执行器按 `JobType` 键注册并动态分发：

| 任务类型键 | 执行器 |
|-----------|--------|
| `"llm"` | LlmExecutor（OpenAI / Anthropic API；可通过 `OPENAI_API_BASE`、`LLM_MODEL` 配置） |
| `"http"` | HttpExecutor（完整 HTTP 方法支持、数据提取、新鲜度检查） |
| `"mcp_{server}_{tool}"` | McpExecutor（MCP 协议 over stdio；可配置服务器列表） |
| `"custom_{hash}"` | Custom executor（V2，预留给未来使用） |

---

### 13. Runner 节点生命周期

Runner 节点运行三个并发任务：

| 任务 | 间隔 | 描述 |
|------|------|------|
| **任务监听器** | 可配置轮询间隔 | 轮询 `GET /runner/{addr}/jobs` 获取新分配任务；失败时指数退避（最大 60s） |
| **健康检查器** | 可配置心跳间隔 | 定期发送 `POST /runner/{addr}/heartbeat` |
| **任务执行器** | 持续运行 | 从内部队列中取出任务；遵守 `max_concurrent_jobs` 限制；通过注册的执行器执行；提交结果到链 |

首次启动时，节点：
1. 加载或生成 **Ed25519 密钥对**（存储在 `data/runner_key.json`）
2. 连接到链 RPC
3. 检查注册状态；如未注册，则使用最低质押自动注册
4. 启动三个并发任务

---

## 设计理由

- **多维过滤 + VRF 选择：** 超越简单的基于列表的 VRF，选择过程按能力、声誉、价格、TEE 支持、域名访问和并发进行过滤，确保任务匹配到合格的 Runner。
- **六种验证模式：** 不同应用有不同信任需求。预言机需要确定性匹配；LLM 聊天机器人可能只需语义相似性；开发测试 Actor 可能完全不需要验证。
- **RateCard 市场：** 不同于固定支付模型，RateCard 系统创建竞争性市场，Runner 声明细粒度定价，开发者设定预算。
- **声誉系统：** 0–100 声誉分数与最低阈值（50）的任务准入机制，无需中心化审核即可实现有机质量过滤。
- **延迟交易（CIP-1）：** 回调作为延迟交易交付，防止链下计算延迟阻塞主链执行。
- **Ed25519 签名：** 使用 Ed25519（与链的 `commonware/ed25519-consensus` 对齐）进行所有 Runner 到链的交互，确保密码学完整性和通过 nonce 管理的防重放保护。

---

## 向后兼容性

本 CIP 完全向后兼容。它在规范地址引入新的 System Actor 和新的 RPC 端点，不会改变任何现有的核心协议规则或交易格式。

---

## 安全考虑

### VRF 篡改（Grinding）
攻击者可能试图影响 `job_id` 或 `submitted_at` 以获得有利的 VRF 种子。缓解措施包括：
- 种子包含**提交者地址**，使其与调用 Actor 绑定。
- Keccak256 迭代哈希使选择不可简单地依赖于组合输入。
- 区块生产是去中心化过程，精确时机控制困难。

### 活跃列表操纵
复杂攻击者可能试图操纵 Runner 池。防御措施包括：
- **最低质押**（10,000 CBY）提供经济威慑。
- **声誉阈值**（最低 50）阻止新注册或表现不佳的 Runner 接收任务。
- **多维能力过滤**确保只有真正合格的 Runner 被选中。
- **费率卡冷却期**防止快速价格操纵。

### 重放攻击
- 所有结果提交包含 **nonce**，通过原子比较交换管理，防止并发重放。
- 签名基于 **Ed25519**，绑定 Runner 的链上注册公钥。

### TEE 信任模型
- 设置 `tee_required` 时，Runner 必须在结果旁提供 TEE 证明。
- TEE 证明由链上 TEE Verifier (0x0097) 验证。
- 支持的 TEE 类型（SGX、TDX、SEV）在 Runner 能力中显式声明。

### 共谋
Runner 间的共谋仍是风险，主要通过以下方式缓解：
- VRF 选择的随机性使特定组合难以被持续选中。
- 验证模式中更高的 `runners` 数量和 `threshold` 值增加共谋成本。
- 声誉系统惩罚产生偏差结果的 Runner。

### 密钥泄露
- Secrets Manager (0x0008) 设计为通过 TEE 证明和访问策略门控密钥访问。
- 密钥应仅在 TEE enclave 内解密。

---

## 实现状态

| 组件 | 状态 |
|------|------|
| Runner 节点（生命周期、任务轮询、执行） | ✅ 已实现 |
| Runner 注册表（注册、心跳、健康、声誉） | ✅ 已实现 |
| 任务调度器（提交、VRF 选择、超时） | ✅ 已实现 |
| 结果验证器（None、MajorityVote、StructuredMatch、Deterministic 模式） | ✅ 已实现 |
| 结果验证器（SemanticSimilarity） | ⚠️ 占位嵌入模型（TODO：真实嵌入模型） |
| 结果验证器（EconomicBond 客观检查） | ⚠️ 占位（TODO） |
| 结果验证器（Custom 验证器 Actor 调用） | ⚠️ 占位（TODO） |
| LLM Executor（OpenAI / Anthropic） | ✅ 已实现 |
| HTTP Executor | ✅ 已实现 |
| MCP Executor（Stdio 传输） | ✅ 已实现 |
| MCP Executor（HTTP / WebSocket 传输） | ❌ 未实现 |
| Chain Client（REST + JSON-RPC） | ✅ 已实现 |
| Secrets Manager | ⚠️ 接口已定义，实现 TODO |
| TEE Runtime 与 Attestation | ⚠️ 接口已定义，实现 TODO |
| TEE Verifier（链上） | ⚠️ 接口已定义，实现 TODO |

---

## 参考

- **CIP-1:** 延迟交易
- **CIP-3:** 双计量 Gas
- **Runner 仓库：** `cowboyinc/runner`（Rust，13 个 crate）
- **链上 System Actor 地址：** Registry=0x91, Dispatcher=0x92, Verifier=0x93, Secrets=0x08, TEE Verifier=0x97
