> [!WARNING]
> **已弃用 (Superseded)**  
> 本文件为 2026-02-20 修订版草稿，已被 **2026-03-05 修订版**取代。  
> 权威版本：[`refs/cips/cip-2-offchain-compute.mdx`](../cips/cip-2-offchain-compute.mdx)  
>  
> **主要变更（旧→新）：**
> - VRF 选择：环形索引 → **Fisher-Yates VRF + 质押加权**（修复相关性攻击漏洞）
> - VRF seed：Dispatcher 私钥 → **HMAC(block_hash, job_id)**（去中心化）
> - `skip_task` 接口 → **超时自动重选**（激励对齐）
> - 结果提交：全员上链 → **commit-reveal + 委托聚合器**（降低 Gas，防结果抄袭）
> - 新增：`required_runner_pool` 字段（Entitlement Pool 准入控制）

# CIP-2: Runner Network — Verifiable Off-Chain Compute Marketplace (Draft, Superseded)

---

> **Status:** Draft (Revised based on code implementation)
> **Type:** Standards Track
> **Category:** Core
> **Created:** 2025-10-02
> **Revised:** 2026-02-20
> **Dependencies:** CIP-1 (Deferred Transactions)

---

## Abstract

This proposal defines the **Runner Network** — a verifiable, asynchronous off-chain compute marketplace for the Cowboy chain. Runner nodes are **fully independent off-chain services** that communicate with on-chain System Actors via JSON-RPC 2.0 and REST protocols, executing off-chain tasks ("Jobs") such as **LLM inference, HTTP requests, MCP (Model Context Protocol) tool calls**, and custom computations.

The architecture is built on:

- **VRF-based deterministic runner selection** (Keccak256 iterative hashing)
- **Six verification modes** for different trust/cost tradeoffs (None, EconomicBond, MajorityVote, StructuredMatch, Deterministic, SemanticSimilarity)
- **Plugin-based executor architecture** for extensible task types
- **Ed25519 cryptographic signing** for all runner-to-chain interactions
- **RateCard-based marketplace pricing** with reputation-weighted selection

---

## Motivation

To unlock advanced use cases involving AI/ML, large datasets, Web2 APIs, and agentic tool calling, smart contracts need a secure and reliable bridge to the off-chain world. This CIP proposes a flexible and multi-modal approach, tailored for Cowboy's on-chain Python Actor environment.

This framework empowers developers to:

1. **Integrate Complex Logic:** Run LLM inferences, HTTP data fetching, MCP tool calls, or custom computations off-chain.
2. **Choose Their Trust Model:** Select from six verification modes — from zero verification (dev/test) to deterministic TEE-backed proofs — based on their specific security/cost requirements.
3. **Leverage Marketplace Pricing:** Runners declare fine-grained rate cards; developers set max price and priority tips; the protocol matches them automatically.
4. **Preserve On-chain Stability:** Utilize asynchronous deferred callbacks (per CIP-1) to prevent network congestion.
5. **Achieve Verifiable Decentralization:** Leverage VRF-based selection with multi-dimensional filtering (capability, reputation, price, TEE support) to ensure fair and transparent runner assignment.

---

## Specification

### 1. System Architecture Overview

The framework consists of **five on-chain System Actors** and the **off-chain Runner network**:

```
┌──────────────────────────────────────────────────┐
│          Cowboy Chain (On-Chain System Actors)    │
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
│          Runner Network (Off-Chain)              │
│                                                  │
│   Runner Node                                    │
│   ├── HTTP Executor                              │
│   ├── LLM Executor (OpenAI / Anthropic)          │
│   ├── MCP Executor (Stdio transport)             │
│   └── Custom Executor (V2)                       │
└──────────────────────────────────────────────────┘
```

**Key Design Principle:** Runner nodes are completely **independent** of the Node and PVM processes. They interact with the chain solely through HTTP-based JSON-RPC 2.0 and REST endpoints.

---

### 2. Job Types

Every off-chain task is defined as a `JobType` enum. The system currently supports four types:

#### 2.1 LLM Inference (`Llm`)

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | H256 | Model hash (32 bytes) |
| `prompt` | String | User prompt |
| `system_prompt` | Option\<String\> | System prompt (optional) |
| `temperature` | Option\<f64\> | Sampling temperature |
| `max_tokens` | u32 | Max output tokens |
| `response_model` | Option\<JsonSchema\> | Structured output schema (optional) |

#### 2.2 HTTP Request (`Http`)

| Field | Type | Description |
|-------|------|-------------|
| `url` | String | Target URL |
| `method` | HttpMethod | GET / POST / PUT / DELETE / PATCH / HEAD / OPTIONS |
| `headers` | HashMap\<String, String\> | HTTP headers |
| `body` | Option\<Vec\<u8\>\> | Request body |
| `extraction` | Option\<ExtractionConfig\> | Data extraction (CssSelector / XPath / JsonPath / Regex) |
| `freshness` | Option\<FreshnessConfig\> | Freshness constraints (Block / Submission / Absolute reference) |

#### 2.3 MCP Tool Call (`Mcp`)

| Field | Type | Description |
|-------|------|-------------|
| `server` | String | MCP server identifier |
| `tool_name` | String | Tool name |
| `arguments` | JSON Value | Tool arguments |
| `timeout_seconds` | Option\<u64\> | Execution timeout |

> **Implementation Note:** MCP transport currently supports **Stdio** only. Http and WebSocket transport types are defined in the type system but not yet implemented.

#### 2.4 Custom Task (`Custom`)

| Field | Type | Description |
|-------|------|-------------|
| `executor_hash` | H256 | Custom executor identifier |
| `params` | Vec\<u8\> | Serialized parameters |

---

### 3. Job Specification (`JobSpec`)

Every job submitted to the chain contains the following specification:

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | H256 | Unique job identifier (32 bytes) |
| `job_type` | JobType | One of the four job types above |
| `bounds` | ResourceBounds | Resource limits for execution |
| `verification` | VerificationConfig | Verification mode and parameters |
| `max_price` | U256 | Maximum price the submitter will pay (CBY wei) |
| `tip` | U256 | Priority tip for faster selection |
| `timeout_blocks` | u64 | Timeout in block heights |
| `callback` | CallbackInfo | Callback Actor and handler info |
| `submitter` | PublicKey | Submitting Actor's public key (Ed25519, 32 bytes) |
| `submitted_at` | u64 | Block height at submission |

#### 3.1 Resource Bounds

| Field | Type | Description |
|-------|------|-------------|
| `max_input_tokens` | u32 | Max input tokens |
| `max_output_tokens` | u32 | Max output tokens |
| `max_wall_time_seconds` | u64 | Max execution wall time |
| `max_memory_mb` | u32 | Max memory usage |
| `max_retries` | u32 | Max retry attempts |

#### 3.2 Callback Info

| Field | Type | Description |
|-------|------|-------------|
| `actor` | PublicKey | Target Actor address (32 bytes) |
| `handler` | String | Callback handler method name |
| `correlation_id` | String | Correlation ID for request/response matching |
| `context` | Vec\<u8\> | Serialized context data |

---

### 4. Verification System

The framework supports **six verification modes**, each trading off cost, latency, and trust level:

#### 4.1 Verification Config

| Field | Type | Description |
|-------|------|-------------|
| `mode` | VerificationMode | One of the six modes below |
| `tee_required` | bool | Whether TEE attestation is required |
| `dispute_window_blocks` | u64 | Dispute window in blocks |

#### 4.2 Verification Modes

| Mode | Runners | Description |
|------|---------|-------------|
| **None** | 1 | No verification. First result accepted directly. *(Dev/test only)* |
| **EconomicBond** | 1 | Single runner with economic stake bond. Objective checks can be applied. *(Objective checks: TODO in implementation)* |
| **MajorityVote** | N (configurable) | N runners execute independently; a specified `vote_field` is extracted and majority-voted with a threshold. |
| **StructuredMatch** | N (configurable) | N runners execute; results are validated against a pipeline of checks (JSON Schema, field matching, numeric tolerance, numeric range, majority vote per field, custom verifier Actor). |
| **Deterministic** | N (configurable) | All results must be byte-identical. If `tee_required`, TEE attestation is verified. |
| **SemanticSimilarity** | N (configurable) | Results are embedded into vectors; cosine similarity is computed; clusters are found; the largest cluster meeting the threshold is accepted. *(Embedding model: placeholder implementation, uses character frequency vectors. TODO: integrate real embedding model.)* |

#### 4.3 StructuredMatch Check Types

| Check Type | Description |
|------------|-------------|
| `JsonSchemaValid` | Validates result against a JSON Schema |
| `StructuredMatch` | Verifies specified field values match across all results |
| `NumericTolerance` | Verifies numeric field values are within a tolerance range |
| `NumericRange` | Verifies numeric field values fall within [min, max] |
| `MajorityVote` | Per-field majority vote |
| `Custom` | Calls a custom verifier Actor on-chain *(TODO in implementation)* |

#### 4.4 Verified Result

After verification succeeds, a `VerifiedResult` is produced:

| Field | Type | Description |
|-------|------|-------------|
| `data` | JSON Value | The accepted result data |
| `consensus_count` | u32 | Number of runners that agreed |
| `total_runners` | u32 | Total runners that submitted results |
| `verification_mode` | VerificationMode | The mode used for verification |

---

### 5. Runner Registry (System Actor: `0x00...0091`)

Manages runner identity, staking, capabilities, rate cards, health status, and reputation.

#### 5.1 Runner Registration

| Field | Type | Description |
|-------|------|-------------|
| `address` | PublicKey | Runner address (Ed25519 public key, 32 bytes) |
| `public_key` | PublicKey | Runner public key |
| `stake` | U256 | Staked amount (CBY). Minimum: 10,000 CBY *(per registry contract)*  |
| `rate_card` | RateCard | Pricing declaration |
| `capabilities` | RunnerCapabilities | Capability declaration |
| `health` | HealthStatus | Current health status |
| `registered_at` | u64 | Registration block height |
| `last_heartbeat` | u64 | Last heartbeat block height |
| `reputation` | u8 | Reputation score (0–100) |
| `active_jobs` | u32 | Currently active job count |

> **Note:** `main.rs` uses 50,000 CBY as minimum stake for auto-registration, while the registry contract defines 10,000 CBY. This discrepancy exists in the codebase; the authoritative value is the on-chain registry constant (10,000 CBY).

#### 5.2 Rate Card

Runners declare their pricing via a `RateCard`:

| Field | Type | Description |
|-------|------|-------------|
| `llm_input_token` | U256 | Price per LLM input token (CBY wei) |
| `llm_output_token` | U256 | Price per LLM output token (CBY wei) |
| `http_request_base` | U256 | Base price per HTTP request |
| `mcp_call_base` | U256 | Base price per MCP tool call |
| `compute_second` | U256 | Price per compute second |
| `memory_mb` | U256 | Price per MB of memory |
| `supported_models` | Vec\<H256\> | Supported LLM model hashes |
| `supported_mcp_servers` | Vec\<String\> | Supported MCP servers |
| `min_job_value` | U256 | Minimum job value accepted |
| `max_job_value` | U256 | Maximum job value accepted |
| `cooldown_blocks` | u64 | Blocks to wait between rate card updates |
| `last_updated` | u64 | Last update block height |

#### 5.3 Runner Capabilities

| Field | Type | Description |
|-------|------|-------------|
| `job_types` | Vec\<String\> | Supported job type identifiers: `"llm"`, `"http"`, `"mcp_{server}_{tool}"`, `"custom_0x..."` |
| `tee_support` | Option\<TeeType\> | TEE type if supported: `Sgx`, `Tdx`, or `Sev` |
| `regions` | Vec\<String\> | Geographic regions |
| `http_domains` | Vec\<String\> | Accessible HTTP domains (`"*"` for all) |
| `max_concurrent_jobs` | u32 | Maximum concurrent job capacity |

#### 5.4 Health Management

Runner health is determined by **heartbeat-based timeout checking**:

| Status | Description |
|--------|-------------|
| `Healthy` | Heartbeat received within the timeout window |
| `Unhealthy` | Heartbeat not received within timeout (default: **100 blocks**) |
| `Paused` | Runner has actively paused itself |
| `Deregistered` | Runner has been deregistered |

The health checker compares `current_block - last_heartbeat` against `heartbeat_timeout_blocks`. If exceeded, the runner is marked `Unhealthy` and excluded from job assignment.

#### 5.5 Registry Interface

| Method | Description |
|--------|-------------|
| `register_runner(registration, signature)` | Register a new runner. Validates: signature, minimum stake, rate card, uniqueness. |
| `update_rate_card(runner, new_rate_card, current_block)` | Update rate card. Enforces cooldown period. |
| `heartbeat(runner, current_block)` | Signal liveness. Updates `last_heartbeat` and re-evaluates health. |
| `get_active_runners(filter, current_block)` | Query active runners with multi-dimensional filtering. |
| `select_committee(job_spec, vrf_seed, current_block)` | Select runner committee via VRF. |
| `update_reputation(runner, delta)` | Adjust reputation score (clamped to 0–100). |
| `get_runner(address)` | Query single runner's registration info. |
| `deregister_runner(runner)` | Deregister a runner (sets health to `Deregistered`). |

---

### 6. Job Dispatcher (System Actor: `0x00...0092`)

Responsible for receiving job submissions, selecting runner committees, assigning jobs, and managing timeouts.

#### 6.1 Core Workflow

```
 Actor submits Job
       │
       ▼
 ┌─────────────┐
 │ Validate     │  Check: bounds ≠ 0, max_price > 0, timeout > 0
 │ JobSpec      │
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │ Generate VRF │  seed = Keccak256(job_id ‖ current_block ‖ submitter)
 │ Seed         │
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │ Select       │  Multi-dimensional filtering + VRF selection
 │ Committee    │
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │ Enqueue +    │  Assign job to selected runners
 │ Assign       │
 └──────┬──────┘
        │
        ▼
  JobStatus::Assigned
```

#### 6.2 Job Status Lifecycle

| Status | Description |
|--------|-------------|
| `Pending` | Submitted, awaiting assignment |
| `Assigned { runners, assigned_at }` | Assigned to runner committee |
| `Executing { runners, started_at }` | Runners are executing |
| `Completed { result, completed_at }` | Verification passed, `VerifiedResult` available |
| `Timeout { timeout_at }` | No results submitted within `timeout_blocks` |
| `Failed { reason, failed_at }` | Execution or verification failed |

> **Note:** There is no explicit `skip_task` mechanism. If a selected runner does not execute, the job will transition to `Timeout` status after `timeout_blocks` have elapsed.

#### 6.3 Dispatcher Interface

| Method | Description |
|--------|-------------|
| `submit_job(job_spec, current_block)` | Submit a job. Returns `job_id`. |
| `get_assigned_jobs(runner)` | Get all jobs assigned to a runner. |
| `process_timeouts(current_block)` | Scan and transition timed-out jobs. |
| `get_job_status(job_id)` | Query job status. |

---

### 7. VRF-Based Runner Selection

The selection process uses **Keccak256 iterative hashing** with multi-dimensional pre-filtering.

#### 7.1 Pre-Selection Filtering

Before VRF selection, candidates must satisfy **all** of the following:

| Filter | Criteria |
|--------|----------|
| Health | `HealthStatus::Healthy` (heartbeat within timeout) |
| Reputation | `reputation ≥ 50` (minimum threshold) |
| Job Type | Runner's `capabilities.job_types` contains the required type |
| TEE | If `tee_required`, runner must have `tee_support` |
| Model | For LLM jobs: `rate_card.supported_models` contains the requested `model_id` |
| Domain | For HTTP jobs: `capabilities.http_domains` contains the target domain (or `"*"`) |
| MCP Server | For MCP jobs: `rate_card.supported_mcp_servers` contains the server (or `"*"`) |
| Price | Estimated cost ≤ `job_spec.max_price` AND within runner's `[min_job_value, max_job_value]` |
| Concurrency | `active_jobs < max_concurrent_jobs` |

#### 7.2 VRF Selection Algorithm

```
Input: candidates[], required_count, seed[32]

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

#### 7.3 Required Runner Count

The number of runners is determined by the `VerificationMode`:

| Mode | Required Runners |
|------|-----------------|
| None | 1 |
| EconomicBond | 1 |
| MajorityVote | `runners` field |
| StructuredMatch | `runners` field |
| Deterministic | `runners` field |
| SemanticSimilarity | `runners` field |

---

### 8. Result Verifier (System Actor: `0x00...0093`)

Receives runner results, performs verification according to the job's `VerificationConfig`, and produces a `VerifiedResult`.

#### 8.1 Verifier Interface

| Method | Description |
|--------|-------------|
| `submit_result(job_id, result)` | Runner submits execution result |
| `verify_results(job_spec, results)` | Verify collected results and produce `VerifiedResult` |

#### 8.2 Runner Result Structure

| Field | Type | Description |
|-------|------|-------------|
| `runner` | PublicKey | Runner's address |
| `job_id` | H256 | Job identifier |
| `data` | JSON Value | Result data |
| `usage` | ResourceUsage | Actual resource consumption |
| `tee_attestation` | Option\<TeeAttestation\> | TEE attestation (if applicable) |
| `source_attestation` | Option\<SourceAttestation\> | Source attestation for HTTP jobs |
| `timestamp` | DateTime\<Utc\> | Execution timestamp |
| `signature` | Signature | Ed25519 signature (64 bytes) |

#### 8.3 Resource Usage

| Field | Type | Description |
|-------|------|-------------|
| `input_tokens` | u32 | Actual input tokens consumed |
| `output_tokens` | u32 | Actual output tokens consumed |
| `wall_time_seconds` | u64 | Actual wall time |
| `memory_mb` | u32 | Actual memory usage |

#### 8.4 Source Attestation (HTTP Jobs)

| Field | Type | Description |
|-------|------|-------------|
| `fetch_timestamp` | DateTime\<Utc\> | When the data was fetched |
| `url` | String | Source URL |
| `http_status` | u16 | HTTP response status code |
| `response_hash` | H256 | Hash of the raw response |
| `tls_cert_fingerprint` | Option\<H256\> | TLS certificate fingerprint |
| `response_headers` | HashMap\<String, String\> | Response headers |

---

### 9. Secrets Manager (System Actor: `0x00...0008`)

Securely stores and manages secrets for Actors, with TEE-gated access control.

#### 9.1 Interface

| Method | Description |
|--------|-------------|
| `store_secret(actor, key, value, access_policy)` | Store an encrypted secret |
| `get_secret(runner, actor, key, tee_attestation)` | Retrieve a secret (requires TEE attestation for decryption) |
| `update_secret(actor, key, value)` | Update an existing secret |
| `delete_secret(actor, key)` | Delete a secret |

#### 9.2 Access Policy

| Field | Type | Description |
|-------|------|-------------|
| `runners` | Vec\<String\> | Allowed runners (e.g., TEE-capable runners only) |
| `entitlements` | Vec\<String\> | Required entitlements |
| `job_types` | Vec\<String\> | Allowed job types |

> **Implementation Status:** The Secrets Manager trait and data structures are fully defined. The implementation currently contains placeholder logic (`TODO` stubs). Actual encrypted storage and TEE-verified retrieval are not yet implemented.

---

### 10. TEE Support

#### 10.1 TEE Verifier (System Actor: `0x00...0097`)

Verifies TEE attestations submitted by runners. Supports three TEE types:

| TEE Type | Description |
|----------|-------------|
| `Sgx` | Intel SGX |
| `Tdx` | Intel TDX |
| `Sev` | AMD SEV |

#### 10.2 TEE Attestation Structure

| Field | Type | Description |
|-------|------|-------------|
| `tee_type` | TeeType | SGX / TDX / SEV |
| `attestation_data` | Vec\<u8\> | Raw attestation data |
| `measurement_hash` | H256 | Measurement hash |
| `signature` | Vec\<u8\> | Attestation signature |

> **Implementation Status:** The TEE Runtime (`execute_in_tee`) and TEE Attestation Generator (`generate_attestation`) interfaces are defined, but both return `"not yet implemented"` errors. TEE data structures (`TeeAttestation`, `TeeType`) are fully defined and integrated into the verification pipeline.

---

### 11. Runner-to-Chain Communication

Runner nodes communicate with the chain via two protocols:

#### 11.1 REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/runner/{address}/jobs` | GET | Get jobs assigned to this runner |
| `/runner/{address}/heartbeat` | POST | Send heartbeat |
| `/runner/{address}/job_result_payload` | GET | Get the payload to sign for result submission |
| `/runner/{address}/job_result` | POST | Submit signed result |
| `/height` | GET | Get current block height |
| `/account/{address}` | GET | Get account info (nonce, etc.) |

#### 11.2 Result Submission Flow

Result submission uses a **sign-then-submit** pattern with Ed25519 signatures (via `ed25519-consensus`, compatible with the chain's `commonware` verification):

```
1. Runner serializes result → base64

2. GET /runner/{address}/job_result_payload
   ?job_id={job_id}&result_base64={result}&nonce={nonce}
   → Returns: { message_to_sign_base64: "..." }

3. Runner signs the message with Ed25519 private key

4. POST /runner/{address}/job_result
   Body: { job_id, result, result_base64, nonce, signature }
```

Nonce management ensures replay protection and supports concurrent submissions.

#### 11.3 JSON-RPC 2.0 Methods

For direct System Actor calls:

| Method | Target Actor | Description |
|--------|-------------|-------------|
| `runner_registry_register` | Registry (0x91) | Register runner |
| `runner_registry_update_rate_card` | Registry (0x91) | Update rate card |
| `runner_registry_heartbeat` | Registry (0x91) | Heartbeat |
| `runner_registry_get_runner` | Registry (0x91) | Query runner info |
| `job_dispatcher_submit_job` | Dispatcher (0x92) | Submit job |
| `job_dispatcher_get_assigned_jobs` | Dispatcher (0x92) | Get assigned jobs |
| `job_dispatcher_get_job_status` | Dispatcher (0x92) | Get job status |
| `result_verifier_submit_result` | Verifier (0x93) | Submit result |
| `result_verifier_verify_results` | Verifier (0x93) | Verify results |
| `chain_getCurrentBlock` | — | Get current block |
| `chain_callActor` | — | Generic Actor call |

---

### 12. Executor Plugin Architecture

Runner nodes use a plugin-based executor system. New task types can be registered at runtime.

#### 12.1 JobExecutor Trait

```rust
#[async_trait]
pub trait JobExecutor: Send + Sync {
    /// Execute a job and return the result
    async fn execute(&self, job_spec: &JobSpec) -> Result<RunnerResult, ExecutorError>;

    /// Estimate execution cost
    fn estimate_cost(&self, job_spec: &JobSpec) -> U256;

    /// Validate resource bounds before execution
    fn validate_bounds(&self, job_spec: &JobSpec) -> Result<(), ExecutorError>;
}
```

#### 12.2 Executor Registry

Executors are registered by `JobType` key and dispatched dynamically:

| Job Type Key | Executor |
|-------------|----------|
| `"llm"` | LlmExecutor (OpenAI / Anthropic APIs; configurable via `OPENAI_API_BASE`, `LLM_MODEL`) |
| `"http"` | HttpExecutor (full HTTP method support, data extraction, freshness checking) |
| `"mcp_{server}_{tool}"` | McpExecutor (MCP protocol over stdio; configurable server list) |
| `"custom_{hash}"` | Custom executor (V2, reserved for future use) |

---

### 13. Runner Node Lifecycle

A Runner node runs three concurrent tasks:

| Task | Interval | Description |
|------|----------|-------------|
| **Job Listener** | Configurable polling interval | Polls `GET /runner/{addr}/jobs` for new assignments; exponential backoff on failures (max 60s) |
| **Health Checker** | Configurable heartbeat interval | Sends `POST /runner/{addr}/heartbeat` at regular intervals |
| **Job Executor** | Continuous | Pops jobs from internal queue; respects `max_concurrent_jobs` limit; executes via registered executor; submits result to chain |

On first startup, the node:
1. Loads or generates an **Ed25519 keypair** (stored in `data/runner_key.json`)
2. Connects to the chain RPC
3. Checks registration status; if unregistered, attempts auto-registration with minimum stake
4. Starts the three concurrent tasks

---

## Rationale

- **VRF-based Selection with Multi-Dimensional Filtering:** Beyond simple list-based VRF, the selection process filters by capability, reputation, price, TEE support, domain access, and concurrency, ensuring tasks are matched to qualified runners.
- **Six Verification Modes:** Different applications have different trust requirements. A price oracle needs deterministic matching; an LLM-powered chatbot may only need semantic similarity; a dev/test Actor may need no verification at all.
- **RateCard Marketplace:** Rather than a fixed payment model, the RateCard system creates a competitive marketplace where runners declare fine-grained pricing and developers set budgets.
- **Reputation System:** The 0–100 reputation score with a minimum threshold (50) for job eligibility creates an organic quality filter without centralized curation.
- **Deferred Transactions (CIP-1):** Callbacks are delivered as deferred transactions, preventing off-chain compute latency from blocking the main chain execution.
- **Ed25519 Signatures:** Using Ed25519 (aligned with chain's `commonware/ed25519-consensus`) for all runner-to-chain interactions ensures cryptographic integrity and replay protection via nonce management.

---

## Backwards Compatibility

This CIP is fully backwards compatible. It introduces new System Actors at canonical addresses and new RPC endpoints without altering any existing core protocol rules or transaction formats.

---

## Security Considerations

### VRF Grinding
An attacker could try to influence `job_id` or `submitted_at` to get a favorable VRF seed. This is mitigated by:
- The seed includes the **submitter's address**, making it specific to the calling Actor.
- The Keccak256 iterative hashing makes the selection non-trivially dependent on the combined inputs.
- Block production is a decentralized process, making precise timing difficult.

### Active List Manipulation
A sophisticated attacker could try to manipulate the runner pool. Defenses include:
- **Minimum stake** (10,000 CBY) provides economic deterrence.
- **Reputation threshold** (min 50) prevents newly registered or poorly performing runners from receiving jobs.
- **Multi-dimensional capability filtering** ensures only genuinely qualified runners are selected.
- **Rate card cooldown** prevents rapid price manipulation.

### Replay Attacks
- All result submissions include a **nonce** managed with atomic compare-and-swap to prevent concurrent replay.
- Signatures are **Ed25519** based, tied to the runner's on-chain registered public key.

### TEE Trust Model
- When `tee_required` is set, runners must provide TEE attestation alongside results.
- TEE attestation is verified by the on-chain TEE Verifier (0x0097).
- Supported TEE types (SGX, TDX, SEV) are explicitly declared in runner capabilities.

### Collusion
Collusion among runners remains a risk, primarily mitigated by:
- VRF selection randomness makes it difficult for a specific set to be selected together consistently.
- Higher `runners` count and `threshold` values in verification modes increase collusion cost.
- The reputation system penalizes runners that produce divergent results.

### Secrets Leakage
- The Secrets Manager (0x0008) is designed to gate secret access via TEE attestation and access policies.
- Secrets should only be decrypted inside TEE enclaves.

---

## Implementation Status

| Component | Status |
|-----------|--------|
| Runner Node (lifecycle, job polling, execution) | ✅ Implemented |
| Runner Registry (registration, heartbeat, health, reputation) | ✅ Implemented |
| Job Dispatcher (submission, VRF selection, timeout) | ✅ Implemented |
| Result Verifier (None, MajorityVote, StructuredMatch, Deterministic modes) | ✅ Implemented |
| Result Verifier (SemanticSimilarity) | ⚠️ Placeholder embedding (TODO: real embedding model) |
| Result Verifier (EconomicBond objective checks) | ⚠️ Placeholder (TODO) |
| Result Verifier (Custom verifier Actor call) | ⚠️ Placeholder (TODO) |
| LLM Executor (OpenAI / Anthropic) | ✅ Implemented |
| HTTP Executor | ✅ Implemented |
| MCP Executor (Stdio transport) | ✅ Implemented |
| MCP Executor (HTTP / WebSocket transport) | ❌ Not implemented |
| Chain Client (REST + JSON-RPC) | ✅ Implemented |
| Secrets Manager | ⚠️ Interface defined, implementation TODO |
| TEE Runtime & Attestation | ⚠️ Interface defined, implementation TODO |
| TEE Verifier (on-chain) | ⚠️ Interface defined, implementation TODO |

---

## References

- **CIP-1:** Deferred Transactions
- **CIP-3:** Dual-Metered Gas
- **Runner Repository:** `cowboyinc/runner` (Rust, 13 crates)
- **On-Chain System Actor Addresses:** Registry=0x91, Dispatcher=0x92, Verifier=0x93, Secrets=0x08, TEE Verifier=0x97
