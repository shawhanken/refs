---
title: "CIP-8: 可验证链下计算 Runner 协议"
description: 基于 Actor 架构的可验证链下计算市场协议，涵盖 Runner 注册与质押、任务分派与 VRF 委员会选择、多模式结果验证、插件化执行器体系、密钥管理与 TEE 可信执行、链上-链下 JSON-RPC 通信，以及 CBY 原生计价与支付
icon: cpu
---

<Note>
  **状态:** 草稿
  **类型:** Standards Track
  **类别:** Core
  **创建日期:** 2026-02-18
  **依赖:** CIP-2 (Off-Chain Compute), CIP-3 (Dual-Metered Gas)
</Note>

## 摘要

本 CIP 定义了 Cowboy 链的 **可验证链下计算 Runner 协议**。

Runner 系统是 Cowboy 链的核心创新，提供一个 **可验证的链下计算市场**。Runner 节点是完全独立的链下服务进程，通过 JSON-RPC 2.0 / REST 协议与链上系统 Actor 通信，执行 LLM 推理、HTTP 请求、MCP 工具调用等链下任务。链上组件负责 Runner 注册、任务分派、结果验证、密钥托管与 TEE 证明验证；链下 Runner 节点通过插件化执行器架构处理实际计算。

协议使用 **VRF 确定性委员会选择** 将任务分配给合格 Runner，并通过六种可配置验证模式对结果进行链上验证，确保计算可信度。所有费用以 `CBY` 原生代币计价和结算。

## 概述

CIP-8 标准化了以下内容：

- 五个链上系统 Actor：Runner Registry（`0x01`）、Job Dispatcher（`0x02`）、Result Verifier（`0x03`）、Secrets Manager（`0x04`）、TEE Verifier（`0x05`）
- Runner 注册、质押、心跳、声誉与费率卡的完整生命周期管理
- 四种内置任务类型：`Llm`、`Http`、`Mcp`、`Custom`
- 基于 VRF 的确定性 Runner 委员会选择算法
- 六种验证模式：`None`、`EconomicBond`、`MajorityVote`、`StructuredMatch`、`Deterministic`、`SemanticSimilarity`
- 任务规格（JobSpec）的规范定义，包括资源边界、回调信息、超时机制
- 链下 Runner 节点的任务监听、并发执行、结果提交的完整工作流
- 插件化执行器（Executor）注册与分派架构
- Ed25519 密钥管理与结果签名
- TEE 可信执行环境集成（SGX/TDX/SEV）
- Actor 级别的密钥托管与访问策略
- 通过 JSON-RPC 2.0 和 REST API 的链上-链下通信协议

## 动机

CIP-8 旨在解决以下需求：

- 智能合约需要访问链下计算资源（LLM 推理、外部 API 数据、工具调用等），但链上 VM 无法直接执行此类操作
- 链下计算结果需要经过验证才能被链上合约信任
- 不同应用场景对验证强度的要求不同，需要灵活的验证策略
- 计算市场需要公平、确定性的任务分配机制
- Runner 运营商需要明确的经济激励和声誉系统

## 设计目标

- 完全独立的链下执行：Runner 节点无需依赖 Node 或 PVM 即可运行
- 可验证性：多种信任模型支持（N-of-M 共识、TEE 证明、ZK V2）
- 可扩展性：插件化执行器架构，方便添加新任务类型
- 安全性：多层验证机制、Ed25519 签名、密钥托管、TEE 隔离
- 经济合理：基于质押的准入、声誉机制、费率卡定价、CBY 计价
- 确定性：VRF 委员会选择保证可重现、不可操纵

## 非目标

- 跨链计算桥接
- 通用 MapReduce 或批处理框架
- Runner 间的直接 P2P 状态同步（v1 通过链上协调）
- 链上存储计算中间过程
- 自定义计价代币（v1 仅支持 CBY）
- Runner 运行环境的标准化镜像（未来 CIP）
- 结果数据的永久链上存储

## 协议常量

- `MIN_STAKE_CBY = 50_000_000_000_000` (50,000 CBY，含精度因子)
- `MIN_REPUTATION = 50` (委员会选择最低声誉要求)
- `MAX_REPUTATION = 100`
- `DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 10`
- `DEFAULT_JOB_POLL_INTERVAL_SECONDS = 1`
- `DEFAULT_MAX_CONCURRENT_JOBS = 10`
- `DEFAULT_RPC_TIMEOUT_SECONDS = 30`
- `MAX_RPC_RETRIES = 3`
- `SIGNATURE_SCHEME = Ed25519`
- `PUBLIC_KEY_BYTES = 32`
- `SIGNATURE_BYTES = 64`

## 定义

- **Runner**：已注册并质押的链下计算节点，能够执行任务并提交经过签名的结果
- **Runner Registry**：链上系统 Actor，管理 Runner 注册、质押、健康状态与声誉
- **Job Dispatcher**：链上系统 Actor，接收任务提交、选择执行委员会、管理任务队列
- **Result Verifier**：链上系统 Actor，根据配置的验证模式对 Runner 提交的结果进行校验
- **Secrets Manager**：链上系统 Actor，托管 Actor 的加密密钥，仅在 TEE 环境中可解密
- **TEE Verifier**：链上系统 Actor，验证可信执行环境的远程证明
- **Executor**：链下执行插件，负责处理特定类型的任务（如 LLM、HTTP、MCP）
- **JobSpec**：任务规格，定义任务类型、资源边界、验证要求、回调信息
- **VRF 种子**：基于任务 ID、区块高度和提交者地址的确定性伪随机种子
- **委员会**：通过 VRF 选择的一组 Runner，共同执行同一任务以支持多方验证
- **Rate Card（费率卡）**：Runner 声明的单项服务定价，包含各类任务的费率
- **心跳**：Runner 定期向链上发送的存活信号

## 系统架构

### 平台架构

```
┌───────────────────────────────────────────────────┐
│              Cowboy Chain（链上层）                 │
│                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐│
│  │Runner Registry│  │Job Dispatcher│  │ Result   ││
│  │   (0x01)      │  │   (0x02)     │  │ Verifier ││
│  │              │  │              │  │  (0x03)  ││
│  └──────────────┘  └──────────────┘  └──────────┘│
│                                                   │
│  ┌──────────────┐  ┌──────────────┐              │
│  │   Secrets    │  │     TEE      │              │
│  │   Manager    │  │   Verifier   │              │
│  │   (0x04)     │  │   (0x05)     │              │
│  └──────────────┘  └──────────────┘              │
└────────────────────┬──────────────────────────────┘
                     │ JSON-RPC 2.0 / REST (HTTP)
                     │
┌────────────────────▼──────────────────────────────┐
│            Runner Network（链下层）                │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Runner   │  │  Runner   │  │  Runner   │  ...  │
│  │  Node A   │  │  Node B   │  │  Node C   │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │              │
│  ┌────▼──────────────▼──────────────▼────┐        │
│  │      Executor Plugin Registry         │        │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │        │
│  │  │ HTTP │ │ LLM  │ │ MCP  │ │Custom│ │        │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ │        │
│  └───────────────────────────────────────┘        │
└───────────────────────────────────────────────────┘
```

### 系统 Actor 地址

| 种子 | 系统 Actor |
|------|-----------|
| `0x01` | Runner Registry |
| `0x02` | Job Dispatcher |
| `0x03` | Result Verifier |
| `0x04` | Secrets Manager |
| `0x05` | TEE Verifier |

所有系统 Actor 在创世区块初始化时创建，地址由确定性种子派生。

## 数据类型

### 1. RunnerRegistration

字段：

- `address` (RunnerAddress)：Runner 地址（Ed25519 公钥，32 字节）
- `public_key` (PublicKey)：Runner 公钥（Ed25519，32 字节）
- `stake` (U256)：质押金额（CBY wei）
- `rate_card` (RateCard)：费率卡
- `capabilities` (RunnerCapabilities)：能力声明
- `health` (HealthStatus)：健康状态
- `registered_at` (BlockHeight)：注册区块高度
- `last_heartbeat` (BlockHeight)：最后心跳区块高度
- `reputation` (uint8)：声誉分（0–100）
- `active_jobs` (uint32)：当前活跃任务数

规则：

- `stake` 必须 ≥ `MIN_STAKE_CBY`
- `address` 必须是有效的 Ed25519 公钥
- 重复注册必须失败并返回 `ALREADY_REGISTERED`
- `rate_card` 必须通过定价合理性校验（`min_job_value ≤ max_job_value`，费率不全为零）
- `health` 初始值为 `Healthy`
- `reputation` 初始值由链确定

### 2. RateCard

字段：

- `llm_input_token` (U256)：LLM 输入 token 单价（CBY wei/token）
- `llm_output_token` (U256)：LLM 输出 token 单价
- `http_request_base` (U256)：HTTP 请求基础价格
- `mcp_call_base` (U256)：MCP 工具调用基础价格
- `compute_second` (U256)：计算时间单价（CBY wei/秒）
- `memory_mb` (U256)：内存单价（CBY wei/MB）
- `supported_models` (ModelHash[])：支持的 LLM 模型列表
- `supported_mcp_servers` (string[])：支持的 MCP 服务器列表
- `min_job_value` (U256)：最低任务价格
- `max_job_value` (U256)：最高任务价格
- `cooldown_blocks` (BlockHeight)：费率更新冷却期（区块数）
- `last_updated` (BlockHeight)：最后更新区块高度

规则：

- `min_job_value` 必须 ≤ `max_job_value`
- 费率不得全为零
- 更新费率卡必须遵守冷却期：距上次更新的区块间隔必须 ≥ `cooldown_blocks`

### 3. RunnerCapabilities

字段：

- `job_types` (string[])：支持的任务类型标识（`"llm"`、`"http"`、`"mcp_<server>_<tool>"`、`"custom_<hash>"`）
- `tee_support` (TeeType?)：支持的 TEE 类型（可选：`Sgx`、`Tdx`、`Sev`）
- `regions` (string[])：地域限制标签
- `http_domains` (string[])：允许访问的 HTTP 域名列表（`"*"` 表示不限制）
- `max_concurrent_jobs` (uint32)：最大并发任务数

### 4. JobType

`JobType` 使用标签化联合类型，`type` 字段标识具体类型：

#### 4.1 Llm

字段：

- `model_id` (ModelHash)：模型标识（32 字节哈希）
- `prompt` (string)：用户提示词
- `system_prompt` (string?)：系统提示词
- `temperature` (float64?)：温度参数
- `max_tokens` (uint32)：最大输出 token 数
- `response_model` (JsonSchema?)：结构化输出 JSON Schema

#### 4.2 Http

字段：

- `url` (string)：请求 URL
- `method` (HttpMethod)：`GET`、`POST`、`PUT`、`DELETE`、`PATCH`、`HEAD`、`OPTIONS`
- `headers` (map<string, string>)：请求头
- `body` (bytes?)：请求体
- `extraction` (ExtractionConfig?)：响应数据提取配置
- `freshness` (FreshnessConfig?)：数据新鲜度校验配置

#### 4.3 Mcp

字段：

- `server` (string)：MCP 服务器标识
- `tool_name` (string)：工具名称
- `arguments` (JSON)：工具参数
- `timeout_seconds` (uint64?)：超时秒数

#### 4.4 Custom

字段：

- `executor_hash` (H256)：自定义执行器哈希
- `params` (bytes)：参数

### 5. JobSpec

字段：

- `job_id` (JobId / H256)：任务 ID（`SHA256(tx_hash || block_height)`）
- `job_type` (JobType)：任务类型
- `bounds` (ResourceBounds)：资源边界
- `verification` (VerificationConfig)：验证配置
- `max_price` (U256)：最高价格（CBY wei）
- `tip` (U256)：优先费（CBY wei）
- `timeout_blocks` (BlockHeight)：超时区块数
- `callback` (CallbackInfo)：回调信息
- `submitter` (PublicKey)：提交者地址
- `submitted_at` (BlockHeight)：提交区块高度

规则：

- `bounds` 中至少一项边界值 > 0
- `max_price` > 0
- `timeout_blocks` > 0
- `job_id` 由链在交易上链后确定性生成

### 6. ResourceBounds

字段：

- `max_input_tokens` (uint32)：最大输入 token 数
- `max_output_tokens` (uint32)：最大输出 token 数
- `max_wall_time_seconds` (uint64)：最大执行时间（秒）
- `max_memory_mb` (uint32)：最大内存（MB）
- `max_retries` (uint32)：最大重试次数

### 7. VerificationConfig

字段：

- `mode` (VerificationMode)：验证模式
- `tee_required` (bool)：是否要求 TEE 证明
- `dispute_window_blocks` (BlockHeight)：争议窗口（区块数）

### 8. VerificationMode

`VerificationMode` 是枚举类型，定义了六种验证策略：

#### 8.1 None

无验证。接受第一个 Runner 的结果。仅用于开发和测试环境。

#### 8.2 EconomicBond

经济保证金模式。单个 Runner 执行，通过经济惩罚机制保障诚实行为。

字段：

- `bond_multiplier` (float64)：保证金倍数
- `objective_checks` (string[])：客观检查项列表

#### 8.3 MajorityVote

多数投票模式。多个 Runner 独立执行，对指定字段进行多数投票。

字段：

- `runners` (uint32)：Runner 数量
- `threshold` (uint32)：阈值（N-of-M 中的 N）
- `vote_field` (string)：投票字段（支持点分路径，如 `result.price`）

#### 8.4 StructuredMatch

结构化匹配模式。多个 Runner 独立执行，通过多维度结构化检查验证结果一致性。

字段：

- `runners` (uint32)：Runner 数量
- `threshold` (uint32)：阈值
- `checks` (VerifierCheck[])：检查项列表

VerifierCheck 支持的类型：

| 检查类型 | 描述 |
|---------|------|
| `JsonSchemaValid` | 结果必须符合指定 JSON Schema |
| `StructuredMatch` | 指定字段的值必须精确匹配 |
| `NumericTolerance` | 指定字段的数值差异必须 ≤ 容差 |
| `NumericRange` | 指定字段的数值必须在 [min, max] 范围内 |
| `MajorityVote` | 指定字段的值必须达到多数一致 |
| `Custom` | 调用自定义验证器 Actor 的指定方法 |

#### 8.5 Deterministic

确定性匹配模式。多个 Runner 的结果必须字节级一致。通常配合 TEE 使用。

字段：

- `runners` (uint32)：Runner 数量
- `threshold` (uint32)：阈值（通常等于 `runners`）
- `inference_config` (InferenceConfig)：推理配置（`temperature` 必须为 0）

#### 8.6 SemanticSimilarity

语义相似度模式。基于嵌入向量的余弦相似度对结果进行聚类，取最大聚簇作为共识结果。

字段：

- `runners` (uint32)：Runner 数量
- `threshold` (uint32)：阈值
- `similarity_threshold` (float64)：相似度阈值
- `embedding_model` (ModelHash)：嵌入模型

### 9. RunnerResult

字段：

- `runner` (RunnerAddress)：执行者地址
- `job_id` (JobId)：任务 ID
- `data` (JSON)：结果数据
- `usage` (ResourceUsage)：实际资源使用量
- `tee_attestation` (TeeAttestation?)：TEE 远程证明（可选）
- `source_attestation` (SourceAttestation?)：源站证明（HTTP 任务可选）
- `timestamp` (DateTime)：完成时间戳
- `signature` (Signature)：Ed25519 签名

### 10. SourceAttestation（HTTP 任务）

字段：

- `fetch_timestamp` (DateTime)：数据抓取时间
- `url` (string)：请求 URL
- `http_status` (uint16)：HTTP 状态码
- `response_hash` (H256)：响应体 SHA-256 哈希
- `tls_cert_fingerprint` (H256?)：TLS 证书指纹
- `response_headers` (map<string, string>)：响应头

### 11. CallbackInfo

字段：

- `actor` (PublicKey)：回调 Actor 地址
- `handler` (string)：回调方法名
- `correlation_id` (string)：关联 ID
- `context` (bytes)：上下文数据

### 12. JobStatus

任务生命周期状态：

| 状态 | 描述 |
|------|------|
| `Pending` | 已提交，等待分配 |
| `Assigned` | 已分配给 Runner 委员会 |
| `Executing` | 正在执行 |
| `Completed` | 已完成，携带验证后的结果 |
| `Timeout` | 超时 |
| `Failed` | 失败，携带失败原因 |

### 13. HealthStatus

| 状态 | 描述 |
|------|------|
| `Healthy` | 健康（心跳正常） |
| `Unhealthy` | 不健康（心跳超时） |
| `Paused` | 主动暂停 |
| `Deregistered` | 已注销 |

## Runner Registry（系统 Actor `0x01`）

Runner Registry 是 Runner 生命周期的唯一管理入口。

### 必要方法

#### `register_runner(registration, signature)`

行为：

1. 验证 Ed25519 签名
2. 检查质押金额 ≥ `MIN_STAKE_CBY`
3. 检查该地址尚未注册
4. 校验费率卡合法性
5. 持久化注册信息
6. 发出 `RunnerRegistered` 事件

#### `update_rate_card(runner, new_rate_card, current_block)`

行为：

1. 查询 Runner 注册信息
2. 检查费率更新冷却期
3. 校验新费率卡合法性
4. 更新并持久化
5. 发出 `RateCardUpdated` 事件

#### `heartbeat(runner, current_block)`

行为：

1. 更新 `last_heartbeat = current_block`
2. 由 HealthChecker 重新评估健康状态
3. 持久化更新

#### `get_active_runners(filter, current_block)`

行为：

1. 加载所有已注册 Runner
2. 按过滤条件筛选：健康状态、最低声誉、任务类型支持、TEE 要求、地域
3. 默认仅返回 `Healthy` 状态的 Runner
4. 返回筛选后的列表

#### `select_committee(job_spec, vrf_seed, current_block)`

行为：

1. 构建过滤条件（最低声誉 50、健康、任务类型匹配、TEE 要求）
2. 获取候选 Runner 列表
3. 根据验证模式确定所需 Runner 数量：
   - `None` / `EconomicBond` → 1
   - `MajorityVote` / `StructuredMatch` / `Deterministic` / `SemanticSimilarity` → `runners` 字段值
4. 候选数量不足时返回 `NOT_FOUND`
5. 使用 VRF 确定性选择算法选取指定数量的 Runner

#### `update_reputation(runner, delta)`

行为：

- 声誉分加减 `delta`，结果裁剪到 `[0, 100]` 范围

#### `deregister_runner(runner)`

行为：

- 设置 `health = Deregistered`
- 发出 `RunnerDeregistered` 事件

## Job Dispatcher（系统 Actor `0x02`）

Job Dispatcher 负责接收任务提交、分配任务、管理任务队列。

### 必要方法

#### `submit_job(job_spec, current_block)`

行为：

1. 校验 JobSpec 合法性（资源边界不全为零、`max_price > 0`、`timeout_blocks > 0`）
2. 生成 VRF 种子：`vrf_seed = Keccak256(job_id || current_block || submitter)`
3. 选择 Runner 委员会（通过 RunnerSelector）
4. 将任务入队
5. 为每个选中的 Runner 记录任务分配
6. 设置任务状态为 `Assigned`
7. 发出 `JobSubmitted` 事件
8. 返回 `job_id`

#### `get_assigned_jobs(runner)`

- 返回分配给指定 Runner 的待执行任务列表

#### `process_timeouts(current_block)`

- 扫描超时任务，更新状态为 `Timeout`
- 返回超时的任务 ID 列表

#### `get_job_status(job_id)`

- 返回指定任务的当前状态

### VRF 委员会选择算法

VRF 选择是确定性的，步骤如下：

1. 以 `vrf_seed` 为初始种子
2. 对候选 Runner 列表进行过滤（能力匹配、价格匹配、并发限额检查）
3. 循环选择：
   a. 计算 `hash = Keccak256(current_seed || selected_count)`
   b. 将 hash 前 8 字节转为 `uint64`，对候选数量取模得到索引
   c. 若该索引未被使用，则选中对应 Runner
   d. 将 `hash` 作为新种子继续
4. 直到选满所需数量或候选耗尽

能力匹配规则：

- 任务类型必须在 Runner 的 `capabilities.job_types` 中
- 若任务要求 TEE，Runner 必须声明 `tee_support`
- LLM 任务：`model_id` 必须在 Runner 的 `supported_models` 中
- HTTP 任务：URL 域名必须在 Runner 的 `http_domains` 中（`"*"` 匹配所有）
- MCP 任务：`server` 必须在 Runner 的 `supported_mcp_servers` 中（`"*"` 匹配所有）

价格匹配规则：

- Runner 根据费率卡估算的价格 ≤ 任务 `max_price`
- `max_price` ≥ Runner 的 `min_job_value`
- `max_price` ≤ Runner 的 `max_job_value`

## Result Verifier（系统 Actor `0x03`）

Result Verifier 对 Runner 提交的结果执行链上验证。

### 验证流程

#### `verify_results(job_spec, results)`

行为：

1. 检查收到的结果数量是否满足验证模式的最低要求
2. 根据 `job_spec.verification.mode` 分派到对应验证逻辑
3. 返回 `VerifiedResult` 或验证错误

#### None 模式

- 接受第一个结果

#### EconomicBond 模式

- 接受第一个结果
- 结果进入争议窗口，期间可被质疑

#### MajorityVote 模式

1. 从每个结果中提取 `vote_field` 指定的字段
2. 对提取值进行分组计数
3. 选择计数最高的值作为多数
4. 若多数计数 < `threshold`，返回 `THRESHOLD_NOT_MET`
5. 从多数组中选取第一个结果作为最终结果

#### StructuredMatch 模式

1. 按 `checks` 列表逐项验证：
   - `JsonSchemaValid`：所有结果必须符合 Schema
   - `StructuredMatch`：指定字段在所有结果间必须一致
   - `NumericTolerance`：数值字段的极差 ≤ 容差
   - `NumericRange`：所有结果的数值字段在指定范围内
   - `MajorityVote`：指定字段达到简单多数
   - `Custom`：调用自定义验证器 Actor
2. 所有检查通过后，返回第一个结果

#### Deterministic 模式

1. 检查所有结果的 JSON 序列化是否字节一致
2. 若有不一致，返回 `NON_DETERMINISTIC`
3. 若 `tee_required`，检查每个结果的 TEE 证明
4. 返回第一个结果

#### SemanticSimilarity 模式

1. 提取每个结果的文本内容
2. 计算嵌入向量
3. 构建余弦相似度矩阵
4. 以相似度阈值进行聚类
5. 取最大聚簇，检查大小 ≥ `threshold`
6. 返回聚簇中的第一个结果

## Secrets Manager（系统 Actor `0x04`）

Secrets Manager 托管 Actor 的加密密钥和敏感配置。

### 必要方法

#### `store_secret(actor, key, value, access_policy)`

- 加密存储密钥
- 访问策略定义允许的 Runner、权限要求、任务类型

#### `get_secret(runner, actor, key, tee_attestation?)`

- 验证 Runner 和 Actor 的访问权限
- 若指定 TEE 证明，验证远程证明有效性
- 仅在 TEE 环境中返回解密后的密钥

#### `update_secret(actor, key, value)` / `delete_secret(actor, key)`

- 仅 Actor 所有者可更新或删除

### AccessPolicy

字段：

- `runners` (string[])：允许的 Runner 标识
- `entitlements` (string[])：权限要求
- `job_types` (string[])：允许的任务类型

## TEE Verifier（系统 Actor `0x05`）

TEE Verifier 验证可信执行环境的远程证明。

### 支持的 TEE 类型

| 类型 | 描述 |
|------|------|
| `Sgx` | Intel SGX |
| `Tdx` | Intel TDX |
| `Sev` | AMD SEV |

### TeeAttestation

字段：

- `tee_type` (TeeType)：TEE 类型
- `attestation_data` (bytes)：远程证明数据
- `measurement_hash` (H256)：度量值哈希
- `signature` (bytes)：证明签名

## 链下 Runner 节点

Runner 节点是独立运行的链下进程。

### 启动流程

1. 初始化日志和配置
2. 加载或生成 Ed25519 密钥对（持久化到 `data/runner_key.json`）
3. 创建链客户端（`HttpChainClient`）
4. 检查是否已注册；若未注册，尝试自动注册（质押 50,000 CBY）
5. 注册执行器（HTTP、LLM、MCP 等）
6. 启动三个并发任务：
   - **任务监听器**：轮询链上获取分配给本 Runner 的任务
   - **健康检查器**：定期发送心跳
   - **任务执行器**：从本地队列取出任务并执行

### 任务监听器

- 以 `job_poll_interval_seconds` 为间隔轮询 `GET /runner/{address}/jobs`
- 过滤已提交结果的任务（避免重复执行）
- 新任务入本地队列
- 连接失败时指数退避重试（最大 60 秒）

### 健康检查器

- 以 `heartbeat_interval_seconds` 为间隔发送心跳
- 调用 `GET /height` 获取当前区块高度
- 调用 `POST /runner/{address}/heartbeat` 发送心跳
- 连接失败时记录并继续重试

### 任务执行器

- 检查并发限额（`max_concurrent_jobs`）
- 从本地队列取出任务
- 根据任务类型查找已注册的执行器
- 在独立 tokio 任务中执行
- 执行完成后通过链客户端提交结果
- 记录已提交的 `job_id` 避免重复执行

### 结果提交流程

Runner 通过两步 REST API 提交结果：

1. **获取签名负载**
   - `GET /runner/{address}/job_result_payload?job_id=&result_base64=&nonce=`
   - 返回 `message_to_sign_base64`：待签名的规范字节

2. **提交签名结果**
   - `POST /runner/{address}/job_result`
   - 请求体包含：`job_id`、`result`、`result_base64`、`nonce`、`signature`
   - 签名使用 `ed25519-consensus`（与链端一致）

### Nonce 管理

- Runner 维护本地 `last_submit_nonce`
- 每次提交前查询链上账户 nonce
- 使用 CAS（Compare-And-Swap）操作确保并发提交不冲突

## 执行器架构

### JobExecutor Trait

```rust
#[async_trait]
pub trait JobExecutor: Send + Sync {
    async fn execute(&self, job_spec: &JobSpec) -> Result<RunnerResult, ExecutorError>;
    fn estimate_cost(&self, job_spec: &JobSpec) -> U256;
    fn validate_bounds(&self, job_spec: &JobSpec) -> Result<(), ExecutorError>;
}
```

### ExecutorRegistry

- 基于 `HashMap<String, Box<dyn JobExecutor>>` 实现
- 注册时按任务类型键（`"llm"`、`"http"`、`"mcp_<server>_<tool>"`、`"custom_<hash>"`）分类
- 运行时根据 `JobType` 查找对应执行器

### 内置执行器

#### HTTP Executor

- 执行 HTTP 请求（GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS）
- 支持自定义请求头和请求体
- 可选数据提取（CSS Selector、XPath、JSONPath、Regex）
- 可选数据新鲜度校验（基于区块时间、提交时间或绝对时间戳）
- 可生成 SourceAttestation（含 TLS 证书指纹）

#### LLM Executor

- 支持 OpenAI 和 Anthropic API
- 可通过 `OPENAI_API_BASE` 配置自定义 API 端点（兼容本地模型）
- 可通过 `LLM_MODEL` 或 `OPENAI_MODEL` 配置模型选择
- 仅在设置了 API Key 时注册

#### MCP Executor

- 支持 Model Context Protocol (MCP) 工具调用
- 支持 Stdio 和 HTTP/SSE 两种传输模式
- 可连接多种 MCP 服务器（数据库、文件系统、浏览器等）
- 可配置超时和认证方式

## 链上-链下通信协议

### ChainClient Trait

```rust
#[async_trait]
pub trait ChainClient: Send + Sync {
    async fn get_assigned_jobs(&self, runner_address: RunnerAddress) -> Result<Vec<JobSpec>, ChainClientError>;
    async fn submit_result(&self, job_id: JobId, result: RunnerResult) -> Result<(), ChainClientError>;
    async fn register_runner(&self, registration: RunnerRegistration, signature: Signature) -> Result<(), ChainClientError>;
    async fn heartbeat(&self, runner_address: RunnerAddress, current_block: BlockHeight) -> Result<(), ChainClientError>;
    async fn get_current_block(&self) -> Result<BlockHeight, ChainClientError>;
}
```

### REST API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/height` | GET | 获取当前区块高度 |
| `/runner/{address}` | GET | 查询 Runner 信息 |
| `/runner/{address}/jobs` | GET | 获取分配给此 Runner 的任务 |
| `/runner/{address}/heartbeat` | POST | 心跳 |
| `/runner/{address}/job_result_payload` | GET | 获取结果签名负载 |
| `/runner/{address}/job_result` | POST | 提交签名后的结果 |
| `/runners/active` | GET | 所有活跃 Runner |
| `/job/{job_id}/status` | GET | 查询任务状态 |
| `/job/{job_id}/results` | GET | 查询任务结果 |
| `/account/{address}` | GET | 查询账户信息（nonce 等） |
| `/transaction/{tx_hash}/receipt` | GET | 查询交易回执 |

地址格式：**32 字节 Ed25519 公钥**，64 个十六进制字符，可带 `0x` 前缀。

### 重试与退避

- 所有 RPC 调用支持最多 `MAX_RPC_RETRIES` 次重试
- 退避策略：`100ms * 2^attempt`
- 超时：`DEFAULT_RPC_TIMEOUT_SECONDS`

## 密钥管理

### KeyManager

- 持久化存储密钥对到 `data/runner_key.json`
- 首次运行自动生成 Ed25519 密钥对
- 支持从十六进制或 JSON 文件加载

### 签名约定

- **签名方案**：Ed25519
- **链端签名库**：`ed25519-consensus`（与 commonware 一致）
- **Runner 签名库**：同样使用 `ed25519-consensus`，确保链上验签通过
- **Runner 地址**：Ed25519 公钥原始字节（32 字节），非以太坊风格 20 字节地址

## 事件

### `RunnerRegistered`

- `runner`（RunnerAddress）
- `stake`（U256）
- `registered_at`（BlockHeight）

### `RunnerDeregistered`

- `runner`（RunnerAddress）
- `block_height`（BlockHeight）

### `RateCardUpdated`

- `runner`（RunnerAddress）
- `block_height`（BlockHeight）

### `JobSubmitted`

- `job_id`（JobId）
- `job_type`（string）
- `runners`（RunnerAddress[]）
- `submitted_at`（BlockHeight）

### `JobCompleted`

- `job_id`（JobId）
- `verification_mode`（string）
- `consensus_count`（uint32）
- `completed_at`（BlockHeight）

### `JobTimeout`

- `job_id`（JobId）
- `timeout_at`（BlockHeight）

### `JobFailed`

- `job_id`（JobId）
- `reason`（string）
- `failed_at`（BlockHeight）

### `HeartbeatReceived`

- `runner`（RunnerAddress）
- `block_height`（BlockHeight）

### `ReputationUpdated`

- `runner`（RunnerAddress）
- `old_reputation`（uint8）
- `new_reputation`（uint8）

## 错误代码

### Registry 错误

- `ALREADY_REGISTERED` — Runner 已注册
- `NOT_FOUND` — Runner 未找到
- `INSUFFICIENT_STAKE` — 质押不足
- `INVALID_RATE_CARD` — 费率卡无效
- `RATE_CARD_COOLDOWN` — 费率更新冷却期未满
- `INVALID_SIGNATURE` — 签名无效
- `HEALTH_CHECK_FAILED` — 健康检查失败

### Dispatcher 错误

- `NO_AVAILABLE_RUNNERS` — 无可用 Runner
- `INSUFFICIENT_RUNNERS` — 可用 Runner 数量不足
- `JOB_NOT_FOUND` — 任务未找到
- `JOB_ALREADY_ASSIGNED` — 任务已分配
- `JOB_TIMEOUT` — 任务超时
- `INVALID_JOB_SPEC` — 任务规格无效
- `PRICE_MISMATCH` — 价格不匹配

### Verification 错误

- `INSUFFICIENT_RESULTS` — 结果数量不足
- `NO_CONSENSUS` — 未达成共识
- `THRESHOLD_NOT_MET` — 未达到阈值
- `SCHEMA_MISMATCH` — Schema 不匹配
- `FIELD_MISMATCH` — 字段不匹配
- `TOLERANCE_EXCEEDED` — 超出容差
- `NON_DETERMINISTIC` — 结果不确定
- `MISSING_TEE_ATTESTATION` — 缺少 TEE 证明
- `INVALID_TEE_ATTESTATION` — TEE 证明无效
- `SEMANTIC_SIMILARITY_LOW` — 语义相似度过低

### Executor 错误

- `UNSUPPORTED_JOB_TYPE` — 不支持的任务类型
- `RESOURCE_BOUNDS_EXCEEDED` — 超出资源边界
- `MODEL_NOT_FOUND` — 模型未找到
- `API_ERROR` — API 错误
- `NETWORK_ERROR` — 网络错误
- `EXTRACTION_FAILED` — 数据提取失败
- `FRESHNESS_CHECK_FAILED` — 新鲜度检查失败
- `TIMEOUT` — 超时
- `MCP_SERVER_NOT_FOUND` — MCP 服务器未找到
- `MCP_TOOL_NOT_FOUND` — MCP 工具未找到
- `MCP_CONNECTION_ERROR` — MCP 连接错误

### Chain Client 错误

- `CONNECTION_FAILED` — 连接失败
- `RPC_ERROR` — RPC 错误
- `INVALID_RESPONSE` — 响应无效
- `TIMEOUT` — 超时
- `AUTHENTICATION_FAILED` — 认证失败

错误映射：

- `register_runner`: `ALREADY_REGISTERED`, `INSUFFICIENT_STAKE`, `INVALID_RATE_CARD`, `INVALID_SIGNATURE`
- `update_rate_card`: `NOT_FOUND`, `RATE_CARD_COOLDOWN`, `INVALID_RATE_CARD`
- `heartbeat`: `NOT_FOUND`, `HEALTH_CHECK_FAILED`
- `submit_job`: `INVALID_JOB_SPEC`, `NO_AVAILABLE_RUNNERS`, `INSUFFICIENT_RUNNERS`, `PRICE_MISMATCH`
- `verify_results`: `INSUFFICIENT_RESULTS`, `NO_CONSENSUS`, `THRESHOLD_NOT_MET`, `SCHEMA_MISMATCH`, `NON_DETERMINISTIC`, `MISSING_TEE_ATTESTATION`
- `store_secret` / `get_secret`: `UNAUTHORIZED`, `NOT_FOUND`

## 安全考量

- Runner 提交的结果必须携带 Ed25519 签名，链上必须验证签名后才写入状态
- VRF 委员会选择必须是确定性的，不可被参与者操纵
- 资源边界（tokens、时间、内存）在执行前必须校验，执行器必须遵守
- TEE 证明必须在链上通过 TEE Verifier 验证才能接受
- Secrets Manager 中的密钥只能在经过验证的 TEE 环境中解密
- 心跳超时的 Runner 应被标记为 `Unhealthy`，不参与新的委员会选择
- 声誉系统应惩罚不诚实行为（提交错误结果、超时未响应）
- 链客户端应防止 nonce 重放攻击
- HTTP Executor 的域名白名单防止 SSRF 攻击
- 结果数据传输应使用 HTTPS
- 费率卡冷却期防止 Runner 在被选入委员会后快速提价

## 向后兼容性

本 CIP 可独立采纳。

现有集成的迁移路径：

1. 在创世区块初始化五个系统 Actor
2. Runner 运营商部署 Runner 节点并注册
3. 链上合约通过 `SystemInstruction::JobSubmit` 提交任务
4. Job Dispatcher 自动分配任务并通知 Runner
5. Runner 执行并提交签名结果
6. Result Verifier 验证结果并回调提交者

## 参考实现说明（非规范性）

- Runner 节点使用 Rust 实现，基于 tokio 异步运行时
- 工作空间包含 13 个 crate：`runner-common`、`runner-node`、`runner-llm`、`runner-http`、`runner-mcp`、`runner-tee`、`runner-consensus`、`chain-client`、`runner-registry`、`job-dispatcher`、`result-verifier`、`secrets-manager`、`tee-verifier`
- 执行器注册应在节点启动时完成，按 API Key 可用性条件注册
- 任务轮询与心跳应独立运行在不同 tokio 任务中
- 并发限额通过 `Mutex<u32>` 实现简单的信号量控制
- JSON-RPC 调用应支持指数退避重试
- 签名使用 `ed25519-consensus` crate 以兼容链端验签

## 设计原理

### 为什么采用链上系统 Actor 而非智能合约？

系统 Actor 在创世区块初始化，具有确定性地址和特权操作权限。Runner 注册、任务分派、结果验证属于平台核心基础设施，需要与共识层紧密集成。系统 Actor 可以直接访问区块高度、交易上下文和状态存储，性能开销远低于用户空间智能合约。

### 为什么使用 VRF 选择而非固定轮转？

VRF 确保委员会选择在给定种子下是确定性的、可验证的、且不可被任何单一参与者操纵。固定轮转会暴露可预测的分配模式，导致攻击者可以针对性地部署恶意 Runner。VRF 的随机性来源于任务 ID、区块高度和提交者地址，三者共同保证种子的不可预测性。

### 为什么需要六种验证模式？

不同应用场景对验证强度和成本的权衡不同：

- 调试和开发：`None` — 零成本、快速迭代
- 低价值查询：`EconomicBond` — 单 Runner 执行，经济保证金兜底
- 价格数据：`MajorityVote` — 多方独立查询，多数一致即可
- 金融数据：`StructuredMatch` — 多维度交叉验证
- 关键计算：`Deterministic` + TEE — 字节级一致 + 硬件证明
- 自然语言生成：`SemanticSimilarity` — 语义级一致性

### 为什么执行器采用插件架构？

每种任务类型的执行逻辑差异极大：LLM 需要 API 调用和 token 管理，HTTP 需要 TLS 和数据提取，MCP 需要进程间通信。插件架构使得添加新类型只需实现 `JobExecutor` trait 并注册，无需修改核心节点代码。这也允许 Runner 运营商根据自身资源选择性注册执行器。

### 为什么使用 Ed25519 而非 secp256k1？

Cowboy 链采用 Ed25519 作为原生签名方案。Ed25519 签名和验签性能优于 secp256k1，且密钥和签名长度更短（公钥 32 字节 vs 33 字节，签名 64 字节 vs 71 字节）。Runner 地址直接使用 Ed25519 公钥（32 字节），避免了以太坊风格地址的 Keccak 哈希截断。

## 开放问题

- 当前 VRF 选择使用简化的 Keccak 哈希链。是否应该迁移到标准 VRF 构造（如 EC-VRF）以获取可公开验证的证明？
- Runner 声誉算法的具体公式是否应在本 CIP 中规范化，还是留给治理过程？
- 是否应引入 Runner 质押分级，允许更高质押的 Runner 获取优先任务分配？
- Secrets Manager 的密钥加密方案是否应在本 CIP 中指定，还是留给独立的安全 CIP？
- 是否应为 `Custom` 任务类型定义标准的 WASM 执行器接口？
- 是否应支持任务取消机制（提交者在执行前撤回任务）？
- 结果数据是否应该有最大尺寸限制？
- 未来是否应引入 Runner 间的直接 P2P 通信用于共识聚合，以减少链上交互？
- 是否应为不同验证模式定义差异化的 Gas 消耗模型？
- 是否应允许 Runner 声明定向偏好（仅服务特定 Actor 的任务）？
