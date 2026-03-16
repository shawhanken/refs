# Node/Runner 代码与规格文档差距分析报告

**日期：** 2026-03-16
**分析范围：** `/workspace/node`、`/workspace/runner` 代码库
**参考文档：** `refs/cips/`（CIP-1 至 CIP-20）、`refs/202602/20260216_cowboy_whitepaper.md`

---

## 一、Runner 选择算法（CIP-2 VRF 不一致）

### 问题描述

**规格要求（CIP-2）：**
- VRF 种子：`Keccak256(block_hash || "cowboy-runner-select-v2:" || job_id || submitted_at_le8)`
- 质押权重：`stake_to_weight(s) = floor(log2(s / MIN_STAKE + 1)) + 1`（对数压缩，防 Sybil）
- 基于 Fisher-Yates VRF 的可验证随机选择

**实际代码：**
- **Node** (`execution/src/runner/dispatcher.rs:316-333`)：直接取 `job_id[0..8]` 作为 seed，用 `(seed + i) % candidates.len()` 轮转选择，无 VRF，无 block_hash，无质押权重
- **Runner** (`crates/runner-registry/src/registry.rs:359-391`)：用 HMAC-SHA256(vrf_seed, slot) 做伪随机选择，无质押权重，种子生成不符合 CIP-2 公式

### 技术解决方案

**Node 侧**（`execution/src/runner/dispatcher.rs`）：

将 `select_runner_committee_simple` 替换为符合规格的实现：

```rust
fn select_runner_committee_vrf(
    candidates: &[RunnerRegistration],
    job_spec: &JobSpec,
    block_hash: &[u8; 32],
) -> Vec<Address> {
    // 1. 计算 VRF 种子
    let mut buf = Vec::new();
    buf.extend_from_slice(block_hash);
    buf.extend_from_slice(b"cowboy-runner-select-v2:");
    buf.extend_from_slice(&job_spec.job_id);
    buf.extend_from_slice(&job_spec.submitted_at.to_le_bytes());
    let seed = keccak256(&buf);

    // 2. 计算每个候选 Runner 的质押权重
    let weights: Vec<u64> = candidates.iter().map(|r| {
        let s = r.stake.saturating_div(MIN_STAKE).saturating_add(1);
        // floor(log2(s)) + 1，最小为 1
        (u64::BITS - s.leading_zeros()) as u64
    }).collect();

    // 3. Fisher-Yates 加权随机选择（使用 seed 派生伪随机）
    vrf_weighted_select(candidates, &weights, required_count, &seed)
}
```

关键点：
- `block_hash` 需从 `execute_system_instruction` 的 `block_hash: &Digest` 参数透传至 dispatcher
- `submitted_at` 需在提交时确定，写入 job_spec 后再计算种子
- 权重选择可用轮盘赌算法（alias method）保证 O(n) 复杂度

**Runner 侧**（`crates/runner-registry/src/registry.rs`）：

`select_committee` 的 `vrf_seed` 参数改为 `block_hash: [u8; 32]`，在内部按 CIP-2 公式构造种子；同时在 `vrf_select_runners` 中加入 stake_to_weight 权重逻辑。

### 测试验收方案

**单元测试（`execution/src/runner/tests.rs` 或新建 `vrf_tests.rs`）：**

```rust
#[test]
fn test_vrf_seed_matches_cip2_spec() {
    let block_hash = [0xABu8; 32];
    let job_id = [0x01u8; 32];
    let submitted_at: u64 = 1000;

    let mut buf = Vec::new();
    buf.extend_from_slice(&block_hash);
    buf.extend_from_slice(b"cowboy-runner-select-v2:");
    buf.extend_from_slice(&job_id);
    buf.extend_from_slice(&submitted_at.to_le_bytes());
    let expected_seed = keccak256(&buf);

    let actual_seed = compute_vrf_seed(&block_hash, &job_id, submitted_at);
    assert_eq!(actual_seed, expected_seed);
}

#[test]
fn test_stake_weight_formula() {
    // floor(log2(s/MIN_STAKE + 1)) + 1
    // s = MIN_STAKE → weight = floor(log2(2)) + 1 = 2
    assert_eq!(stake_to_weight(MIN_STAKE, MIN_STAKE), 2);
    // s = 0 → weight = 1（最小值）
    assert_eq!(stake_to_weight(0, MIN_STAKE), 1);
    // s = 3*MIN_STAKE → floor(log2(4)) + 1 = 3
    assert_eq!(stake_to_weight(3 * MIN_STAKE, MIN_STAKE), 3);
}

#[test]
fn test_vrf_selection_is_deterministic() {
    let candidates = make_test_runners(10);
    let seed = [0x42u8; 32];
    let r1 = vrf_weighted_select(&candidates, 3, &seed);
    let r2 = vrf_weighted_select(&candidates, 3, &seed);
    assert_eq!(r1, r2, "相同种子必须产生相同选择结果");
}

#[test]
fn test_vrf_selection_different_seeds() {
    let candidates = make_test_runners(20);
    let seed_a = [0x01u8; 32];
    let seed_b = [0x02u8; 32];
    let r_a = vrf_weighted_select(&candidates, 3, &seed_a);
    let r_b = vrf_weighted_select(&candidates, 3, &seed_b);
    assert_ne!(r_a, r_b, "不同种子应产生不同选择结果（概率性）");
}

#[test]
fn test_high_stake_runner_selected_more_often() {
    // 统计 1000 次选择中，高质押 Runner 的入选频率显著高于低质押 Runner
    let mut low_stake = make_runner_with_stake(MIN_STAKE);
    let mut high_stake = make_runner_with_stake(100 * MIN_STAKE);
    let candidates = vec![low_stake, high_stake];
    let mut high_count = 0;
    for i in 0u32..1000 {
        let seed = keccak256(&i.to_le_bytes());
        if vrf_weighted_select(&candidates, 1, &seed)[0] == high_stake.address {
            high_count += 1;
        }
    }
    // 高质押 Runner 权重约为 log2(101)+1 ≈ 8，低质押为 2，期望占比约 80%
    assert!(high_count > 600, "高质押 Runner 入选频率应显著高于低质押，实际: {}", high_count);
}
```

**集成验收标准：**
- [ ] 给定固定 block_hash、job_id、submitted_at，选择结果与 CIP-2 公式手算一致
- [ ] 两个相同配置的节点对同一 Job 的 Runner 选择结果完全一致
- [ ] 更换 block_hash 后，选择结果以不低于 90% 的概率发生变化（随机性验证）
- [ ] 高质押（100x MIN_STAKE）Runner 的长期入选频率高于低质押 Runner

---

## 二、Node 与 Runner 之间的数据类型不一致

### 问题描述

两个代码库之间存在大量类型分歧，导致互操作性问题：

| 字段 | Node (`runner/src/types.rs`) | Runner (`runner-common/src/types.rs`) | CIP 规格 |
|------|-------------------------------|---------------------------------------|----------|
| `stake` | `u64` | `U256` | U256（以太坊大数） |
| `CallbackInfo` | `{ actor, handler, payload: Option<Vec<u8>> }` | `{ actor, handler, correlation_id: String, context: Vec<u8> }` | 含 context |
| `VerificationConfig` | 扁平：`{ mode, runners, threshold, checks, ... }` | 嵌套：`mode` 枚举内含 runners/threshold | 嵌套 |
| `Http.method` | `String` | `HttpMethod`（枚举） | 枚举 |
| `Http.extraction` | `Option<String>` | `Option<ExtractionConfig>`（结构体） | 结构体 |
| `FreshnessConfig` | `{ max_age_seconds, cache_control }` | `{ max_age_seconds, timestamp_field, reference(enum) }` | 含 reference |
| `RateCard` | 无 `mcp_call_base` 字段，价格为 `u64` | 有 `mcp_call_base: U256`，价格为 `U256` | U256 |
| `RunnerResult` | 无 `signature` 字段，`timestamp: u64` | 有 `signature: Signature`，`timestamp: DateTime<Utc>` | 含签名 |
| `VerifiedResult` | 无 `verification_mode` 字段 | 有 `verification_mode: VerificationMode` | 含 mode |
| `VerifierCheck` | 无 `NumericRange` 变体 | 有 `NumericRange { field, min, max }` | 含 NumericRange |
| `model_id` / `job_id` | `[u8; 32]`（字节数组） | `H256`（以太坊哈希类型） | H256 |

> 当前 runner-common 已加了自定义反序列化器（`model_hash_from_hex_or_array`、`u256_from_number_or_string`、`verification_config_from_chain`）来兼容 node 序列化格式，但这是技术债务，且仅覆盖了部分字段，存在反序列化时数据丢失风险。

### 技术解决方案

**根本方案：以 Node 的 `runner/src/types.rs` 为单一真相来源（Single Source of Truth），将其发布为独立 crate `cowboy-runner-types`，同时被 node 和 runner 两个工作区依赖。**

具体步骤：

1. **新建 `cowboy-runner-types` crate**（可作为 `node/runner/` 的子 crate 发布）：
   - 采用 Runner common 中的 `U256`/`H256` 类型（更接近 CIP 规格）
   - 合并两侧 `CallbackInfo`，统一为 `{ actor, handler, correlation_id, context }`
   - `VerificationConfig` 采用嵌套结构（mode 枚举内含 runners/threshold）
   - `RateCard` 补充 `mcp_call_base: U256` 字段
   - `RunnerResult` 补充 `signature: Signature` 和 `timestamp: u64`（秒级 Unix 时间戳）
   - `VerifierCheck` 补充 `NumericRange` 变体
   - `FreshnessConfig` 补充 `reference: FreshnessReference` 枚举

2. **Node 侧迁移**：
   - `node/runner/src/types.rs` 改为 re-export `cowboy-runner-types`
   - Node 内部的 stake 存储统一升级为 `u128`（用 u128 表示 U256 的实际使用范围，避免引入 ethereum-types 依赖）

3. **Runner 侧迁移**：
   - `crates/runner-common/src/types.rs` 改为依赖 `cowboy-runner-types`，删除自定义反序列化器
   - RPC 层的序列化格式以 JSON 为主，node 对外 API 统一输出驼峰字段（`snake_case` 到 `camelCase` 仅在 HTTP 边界转换）

### 测试验收方案

**单元测试（`runner-common/src/types_compat_tests.rs`，新建）：**

```rust
// 测试 Node 序列化 → Runner 反序列化的完整往返
#[test]
fn test_job_spec_roundtrip_node_to_runner() {
    let node_spec = node_types::JobSpec {
        job_id: [0x01u8; 32],
        job_type: node_types::JobType::Llm {
            model_id: [0u8; 32],
            prompt: "hello".into(),
            system_prompt: None,
            temperature: Some(0.7),
            max_tokens: 256,
            response_model: None,
        },
        // ...其余字段
    };
    let json = serde_json::to_string(&node_spec).unwrap();

    // Runner 侧反序列化
    let runner_spec: runner_common::types::JobSpec = serde_json::from_str(&json).unwrap();
    assert_eq!(hex::encode(node_spec.job_id), format!("{:?}", runner_spec.job_id));
    assert_eq!(node_spec.max_price as u128, runner_spec.max_price.as_u128());
}

#[test]
fn test_runner_result_has_signature_field() {
    // 确认 RunnerResult 包含 signature 字段，且非全零
    let result = make_signed_runner_result(&signing_key, &job_id);
    assert_ne!(result.signature.0, [0u8; 65], "签名不应为零");
}

#[test]
fn test_verification_config_nested_deserialization() {
    // Node 序列化的扁平格式能被 Runner 正确解析为嵌套结构
    let flat_json = r#"{"mode":"majorityvote","runners":3,"threshold":2,"tee_required":false,"dispute_window_blocks":10}"#;
    let cfg: runner_common::types::VerificationConfig = serde_json::from_str(flat_json).unwrap();
    match cfg.mode {
        VerificationMode::MajorityVote { runners, threshold, .. } => {
            assert_eq!(runners, 3);
            assert_eq!(threshold, 2);
        }
        _ => panic!("应解析为 MajorityVote"),
    }
}

#[test]
fn test_rate_card_has_mcp_call_base() {
    // 确认 RateCard 含 mcp_call_base 字段，且类型为 U256
    let card = RateCard {
        mcp_call_base: U256::from(100),
        // ...
    };
    assert_eq!(card.mcp_call_base, U256::from(100));
}
```

**集成验收标准：**
- [ ] Node 序列化的所有 `JobSpec` / `RunnerResult` / `VerificationConfig` JSON 均可被 Runner 反序列化，无字段丢失
- [ ] Runner 序列化的 `RunnerRegistration` 均可被 Node RPC 层正确解析
- [ ] 新建 `cowboy-runner-types` 后，两侧编译均无类型警告
- [ ] 现有集成测试（`node/chain/src/lib.rs` 中的 5 个场景）全部通过

---

## 三、Runner 候选过滤条件不完整（CIP-2）

### 问题描述

**规格要求（CIP-2）** 共 7 个过滤条件：Health、Reputation ≥ 50、Capability、TEE、Price、Concurrency、Entitlement

**Node 实际代码** (`execution/src/runner/dispatcher.rs:296-312`)：**只过滤 `health == Healthy`**，缺少：
- 能力类型（Capability/job_type）检查
- 最大并发数（Concurrency: `active_jobs < max_concurrent_jobs`）检查
- 价格可承受性（Price: `estimated_cost <= max_price`）检查
- Reputation ≥ 50 检查
- Entitlement / runner pool 检查

### 技术解决方案

在 `select_runner_committee_simple`（或其替代函数）中补充完整的过滤链：

```rust
fn filter_candidates(
    runners: Vec<RunnerRegistration>,
    job_spec: &JobSpec,
) -> Vec<RunnerRegistration> {
    runners.into_iter().filter(|r| {
        // 1. 健康状态
        r.health == HealthStatus::Healthy
        // 2. 最低声誉
        && r.reputation >= 50
        // 3. 能力匹配（job_type 字符串 key）
        && r.capabilities.job_types.contains(&job_type_key(&job_spec.job_type))
        // 4. TEE 要求
        && (!job_spec.verification.tee_required || r.capabilities.tee_support.is_some())
        // 5. 并发数限制
        && r.active_jobs < r.capabilities.max_concurrent_jobs
        // 6. 价格可承受：estimate_cost(r, job_spec) <= job_spec.max_price
        && estimate_cost(r, job_spec) <= job_spec.max_price
        // 7. Runner Pool（若 job_spec 含 required_runner_pool，见问题九）
        // && check_runner_pool(r, job_spec.required_runner_pool.as_deref())
    }).collect()
}
```

`estimate_cost` 根据 runner 的 `rate_card` 和 `bounds` 中的 `max_input_tokens`、`max_wall_time_seconds` 估算。

### 测试验收方案

**单元测试（`execution/src/runner/dispatcher_filter_tests.rs`）：**

```rust
#[tokio::test]
async fn test_unhealthy_runner_excluded() {
    let mut runners = vec![
        make_runner(|r| r.health = HealthStatus::Unhealthy),
        make_runner(|r| r.health = HealthStatus::Healthy),
    ];
    let result = filter_candidates(&runners, &default_llm_job());
    assert_eq!(result.len(), 1);
    assert_eq!(result[0].health, HealthStatus::Healthy);
}

#[tokio::test]
async fn test_low_reputation_runner_excluded() {
    let runners = vec![
        make_runner(|r| { r.health = HealthStatus::Healthy; r.reputation = 49; }),
        make_runner(|r| { r.health = HealthStatus::Healthy; r.reputation = 50; }),
        make_runner(|r| { r.health = HealthStatus::Healthy; r.reputation = 80; }),
    ];
    let result = filter_candidates(&runners, &default_llm_job());
    assert_eq!(result.len(), 2);
    assert!(result.iter().all(|r| r.reputation >= 50));
}

#[tokio::test]
async fn test_wrong_capability_excluded() {
    let http_job = make_job(JobType::Http { .. });
    let runners = vec![
        make_runner(|r| r.capabilities.job_types = vec!["llm".into()]),  // 不支持 http
        make_runner(|r| r.capabilities.job_types = vec!["http".into()]), // 支持 http
    ];
    let result = filter_candidates(&runners, &http_job);
    assert_eq!(result.len(), 1);
}

#[tokio::test]
async fn test_max_concurrent_jobs_respected() {
    let job = make_job_with_runners(1);
    let runners = vec![
        make_runner(|r| {
            r.active_jobs = 10;
            r.capabilities.max_concurrent_jobs = 10; // 已满
        }),
        make_runner(|r| {
            r.active_jobs = 5;
            r.capabilities.max_concurrent_jobs = 10; // 有余量
        }),
    ];
    let result = filter_candidates(&runners, &job);
    assert_eq!(result.len(), 1);
    assert_eq!(result[0].active_jobs, 5);
}

#[tokio::test]
async fn test_price_too_high_excluded() {
    let job = make_job_with_max_price(100); // max_price = 100
    let runners = vec![
        make_runner(|r| r.rate_card.llm_input_token = U256::from(200)), // 估算费用超出
        make_runner(|r| r.rate_card.llm_input_token = U256::from(1)),   // 价格合理
    ];
    let result = filter_candidates(&runners, &job);
    assert_eq!(result.len(), 1);
}
```

**集成验收标准：**
- [ ] 提交 LLM Job，仅有声明支持 "llm" capability 的 Healthy Runner 被选中
- [ ] 提交 MCP Job，声明 "llm" capability 的 Runner 不会被选中
- [ ] TEE 必需的 Job 只选中 `tee_support` 非 None 的 Runner
- [ ] 所有 7 个过滤条件各有至少 1 个失败情形的测试用例覆盖

---

## 四、超时重选机制（CIP-2）完全未实现

### 问题描述

**规格要求（CIP-2）：**
- 超时 Runner：`reputation -= TIMEOUT_PENALTY(5)`
- 重选种子：`Keccak256(original_seed || "retry:" || retry_count_le4)`
- 最多 `MAX_RETRIES = 3` 次，超过后 Job 失败并扣除 `SLASH_THRESHOLD` 声誉

**实际代码：**
- `system_instruction.rs:146-148`：`JobCancel` 返回 `UnsupportedInstruction`
- `system_instruction.rs:116-118`：`RunnerDeregister` 返回 `UnsupportedInstruction`
- 无任何超时重选逻辑，无声誉惩罚机制

### 技术解决方案

**需要新增的链上逻辑：**

1. **在 job_spec 中存储原始 VRF 种子和重试计数**：
   ```rust
   // 在 dispatcher 存储中为每个 job 额外保存：
   struct JobDispatchState {
       original_vrf_seed: [u8; 32],
       retry_count: u32,
       timeout_at_block: u64,
   }
   ```

2. **Block 处理尾端（End-of-Block）触发超时检查**：
   在 `ExecutionEngine::finalize_block`（或等价位置）中遍历所有 `Assigned` 状态且超时的 Job：
   ```rust
   async fn process_job_timeouts(&mut self, store: &mut S, block_height: u64) {
       let timed_out_jobs = get_jobs_where(store, |j, state| {
           j.status == JobStatus::Assigned
           && block_height > state.timeout_at_block
       });
       for (job_id, state) in timed_out_jobs {
           // 对超时 Runner 扣声誉
           for runner in get_assigned_runners(store, &job_id) {
               update_reputation(store, runner, -(TIMEOUT_PENALTY as i8));
           }
           if state.retry_count >= MAX_RETRIES {
               // 最终失败：对 Runner 执行 slash
               set_job_status(store, &job_id, JobStatus::Failed);
           } else {
               // 重选：派生新种子
               let mut buf = state.original_vrf_seed.to_vec();
               buf.extend_from_slice(b"retry:");
               buf.extend_from_slice(&(state.retry_count + 1).to_le_bytes());
               let new_seed = keccak256(&buf);
               let new_runners = select_by_seed(store, &job_spec, &new_seed, block_height);
               reassign_job(store, &job_id, new_runners, state.retry_count + 1, block_height);
           }
       }
   }
   ```

3. **实现 `RunnerDeregister` 和 `JobCancel` 指令**：
   - `RunnerDeregister`：将 Runner health 标记为 `Deregistered`，从活跃候选列表移除
   - `JobCancel`：将 Job 标记为 `Cancelled`，退款 submitter（若有锁定费用）

### 测试验收方案

**单元测试（`execution/src/runner/timeout_tests.rs`）：**

```rust
#[tokio::test]
async fn test_job_timeout_triggers_reputation_penalty() {
    let mut store = TestStore::new();
    let runner_addr = make_runner_address();
    register_runner(&mut store, runner_addr, 80 /*reputation*/);
    let job_id = submit_job(&mut store, 1 /*block*/, runner_addr);

    // 模拟超时：推进到 submitted_at + timeout_blocks + 1
    let timeout_block = 1 + 100 + 1;
    process_job_timeouts(&mut engine, &mut store, timeout_block).await;

    let runner = get_runner(&store, runner_addr);
    assert_eq!(runner.reputation, 75, "声誉应减少 TIMEOUT_PENALTY=5");
}

#[tokio::test]
async fn test_job_reselected_after_timeout_with_new_seed() {
    let mut store = TestStore::new();
    let runners = register_runners(&mut store, 5);
    let job_id = submit_job_to(&mut store, runners[0], 1);

    // 触发超时 + 重选
    process_job_timeouts(&mut engine, &mut store, 1 + 100 + 1).await;

    let new_runners = get_job_assigned_runners(&store, &job_id);
    // 重选后应换新 Runner（不一定，但大概率不同）
    let status = get_job_status(&store, &job_id);
    assert_eq!(status, JobStatus::Assigned, "重试 < MAX_RETRIES 时应重新 Assigned");
    // 验证重试计数递增
    let state = get_job_dispatch_state(&store, &job_id);
    assert_eq!(state.retry_count, 1);
}

#[tokio::test]
async fn test_job_fails_after_max_retries() {
    let mut store = TestStore::new();
    let runner = register_runner(&mut store, make_runner_address(), 80);
    let job_id = submit_job(&mut store, 1, runner);

    // 连续触发 MAX_RETRIES+1 次超时
    for i in 0..=3u64 {
        let timeout_block = 1 + (i + 1) * 101;
        process_job_timeouts(&mut engine, &mut store, timeout_block).await;
    }

    let status = get_job_status(&store, &job_id);
    assert_eq!(status, JobStatus::Failed, "超过 MAX_RETRIES 后 Job 应 Failed");
}

#[tokio::test]
async fn test_retry_vrf_seed_differs_from_original() {
    let original_seed = [0xAAu8; 32];
    let retry_seed = compute_retry_seed(&original_seed, 1);

    let mut buf = original_seed.to_vec();
    buf.extend_from_slice(b"retry:");
    buf.extend_from_slice(&1u32.to_le_bytes());
    let expected = keccak256(&buf);

    assert_eq!(retry_seed, expected);
    assert_ne!(retry_seed, original_seed);
}
```

**集成验收标准：**
- [ ] Job 超时后（`submitted_at + timeout_blocks < current_block`），被分配的 Runner 声誉 `-5`
- [ ] 重选时 VRF 种子不同于原始种子（可通过日志或存储状态验证）
- [ ] 第 4 次超时（`retry_count == MAX_RETRIES`）时 Job 状态变为 `Failed`
- [ ] `RunnerDeregister` 和 `JobCancel` 指令可正常执行，不再返回 `UnsupportedInstruction`

---

## 五、Commit-Reveal 聚合协议（CIP-2）完全未实现

### 问题描述

**规格要求（CIP-2）：**
1. 所有 M 个 Runner 先提交 `hash(result_bytes || runner_sig)`
2. 信誉最高的 Runner 作为 Aggregator，通过 HTTP 收集所有结果
3. Aggregator 在链上揭示（reveal）完整结果
4. 链上验证所有承诺与签名

**实际代码：**
- Node：直接提交结果到 Verifier，无 commit/reveal 流程
- Runner `crates/runner-consensus/src/consensus.rs`：`ConsensusClient` 为空结构体，`participate_vote` 和 `aggregate_results` 均有 TODO
- Runner `crates/runner-consensus/src/aggregation.rs`：聚合逻辑完全未实现

### 技术解决方案

**分两个阶段实现，先 EconomicBond/MajorityVote（简化版），后完整 Commit-Reveal：**

**阶段一（短期）：链上多结果直接提交 + 投票**

不引入 P2P，每个 Runner 独立向链上提交结果，链上 `Result Verifier` 在收齐 `threshold` 个后执行验证：

```rust
// Node: execution/src/runner/verifier.rs
impl ExecutionEngine {
    pub async fn handle_job_result_submit(...) {
        // 1. 验证 runner 是该 job 的受让人
        // 2. 存储结果（追加到 job_results 列表）
        // 3. 若结果数 >= threshold，执行链上验证
        if results.len() >= job_spec.verification.threshold as usize {
            let verified = verify_results_on_chain(&job_spec, &results)?;
            trigger_callback(store, &job_spec.callback, &verified, block_height);
        }
    }
}
```

**阶段二（完整 Commit-Reveal）：**

Runner 侧流程（`crates/runner-consensus/src/aggregation.rs`）：
```rust
pub async fn commit_phase(
    job_id: JobId,
    result: RunnerResult,
    signing_key: &SigningKey,
) -> CommitMessage {
    let result_bytes = canonical_serialize(&result);
    let runner_sig = sign_message(signing_key, &result_bytes);
    let commitment = keccak256(&[result_bytes.as_slice(), runner_sig.as_ref()].concat());
    CommitMessage { job_id, runner: signing_key.address(), commitment }
}

pub async fn reveal_phase_aggregator(
    job_id: JobId,
    all_results: Vec<(RunnerResult, Signature)>,
    chain_client: &dyn ChainClient,
) {
    // Aggregator 收集后批量 reveal
    chain_client.submit_reveal(job_id, all_results).await;
}
```

链上 `JobResultReveal` 新指令需要在 `system_instruction.rs` 中新增对应分支。

### 测试验收方案

**单元测试（`runner/crates/runner-consensus/tests/`）：**

```rust
#[test]
fn test_commit_message_format() {
    let result = make_test_runner_result();
    let signing_key = make_signing_key();

    let commit = commit_phase(result.job_id, result.clone(), &signing_key);

    // 验证承诺格式：keccak256(result_bytes || runner_sig)
    let result_bytes = canonical_serialize(&result);
    let runner_sig = sign_message(&signing_key, &result_bytes);
    let expected_commitment = keccak256(&[result_bytes.as_slice(), runner_sig.as_ref()].concat());

    assert_eq!(commit.commitment, expected_commitment);
    assert_eq!(commit.runner, signing_key.address());
}

#[test]
fn test_on_chain_verifier_accepts_valid_reveals() {
    let job_spec = make_job_spec(VerificationMode::MajorityVote { runners: 3, threshold: 2, .. });
    let results = (0..3).map(|i| {
        let key = make_signing_key_i(i);
        make_signed_result(&key, &job_spec.job_id)
    }).collect::<Vec<_>>();

    // 模拟链上验证
    let verified = verify_majority_vote(&job_spec, &results).unwrap();
    assert_eq!(verified.consensus_count, 3);
}

#[test]
fn test_on_chain_verifier_rejects_mismatched_commits() {
    let job_spec = make_job_spec(VerificationMode::MajorityVote { runners: 3, threshold: 2, .. });
    let mut results = make_valid_results(3, &job_spec.job_id);

    // 篡改其中一个结果
    results[2].data = serde_json::json!({"result": "tampered"});

    let verified = verify_majority_vote(&job_spec, &results);
    // 2-of-3 多数一致，应接受（少数派被识别为异常）
    assert!(verified.is_ok());
    assert_eq!(verified.unwrap().consensus_count, 2);
}

#[tokio::test]
async fn test_aggregator_collects_results_via_http() {
    // 启动 3 个 mock runner HTTP 服务器
    let servers = start_mock_runner_servers(3);
    let aggregator = AggregatorClient::new(reqwest::Client::new());
    let job_id = [0x01u8; 32];

    let results = aggregator.collect_results(
        job_id,
        &servers.endpoints(),
        Duration::from_secs(5),
    ).await;

    assert_eq!(results.len(), 3);
}
```

**阶段一验收标准（多结果直接链上提交）：**
- [ ] N 个 Runner 各自独立提交结果后，`threshold` 达到时触发 callback
- [ ] 链上 Verifier 能区分一致结果与异常结果
- [ ] 少于 `threshold` 的结果提交时，callback 不触发

**阶段二验收标准（完整 Commit-Reveal）：**
- [ ] Commit 阶段：链上存储每个 Runner 的承诺哈希
- [ ] Reveal 阶段：Aggregator 揭示的结果与承诺哈希一致（不一致则拒绝）
- [ ] Aggregator 超时后，其他 Runner 可独立 reveal（fallback 路径可用）

---

## 六、CIP-5 定时器机制实现不完整

### 问题描述

**规格要求（CIP-5）：**
- 两种类型：`HEIGHT`（按区块高度触发）和 `STATE_WATCH`（状态变更触发）
- 三层队列：Ring Buffer（短期 O(1)）→ Epoch Queue（中期）→ Sorted Set（长期 Merkle 化 BST）
- Gas 竞价代理（GBA）：`bid_fp: u128 (Q32.96)` 固定点数竞价
- 触发评分：`score = W_age * age_blocks + W_bid * bid_fp`
- Mailbox Entry `deliver_id = H(h, parent_state_root, timer_id, fire_seq)`

**实际代码** (`execution/src/pvm_host.rs:889-934`)：
- 只有 `schedule_timer(height, payload)` 和 `cancel_timer(timer_id)`
- 缺失：`bid_fp` 竞价参数、`STATE_WATCH` 类型、三层队列、评分机制

### 技术解决方案

**分步完善，保持向后兼容：**

**步骤 1：扩展 `schedule_timer` host API 签名**（`pvm_host.rs`）：
```rust
// 当前
fn schedule_timer(&mut self, height: u64, payload: &[u8]) -> HostResult<Bytes>

// 升级为
fn schedule_timer(
    &mut self,
    height: u64,
    payload: &[u8],
    gas_limit: u64,
    bid_fp: u128,  // Q32.96 fixed-point
) -> HostResult<Bytes>
```

**步骤 2：新增 `set_state_watch` host API**：
```rust
fn set_state_watch(
    &mut self,
    watch_keys: &[&[u8]],  // 监视的存储 key 前缀列表
    payload: &[u8],
    gas_limit: u64,
    bid_fp: u128,
) -> HostResult<Bytes>
```

**步骤 3：实现三层队列（Node 执行层）**：
- 新建 `cowboy-scheduler` crate（或在 execution 中新增 `scheduler/` 模块）
- **Tier 1 Ring Buffer**：`Vec<Option<TimerBucket>>`，固定大小（如 256 个 slot），每个 slot 对应一个区块，O(1) 入队/出队
- **Tier 2 Epoch Queue**：`HashMap<u64, Vec<TimerRef>>`，按 epoch 分桶，epoch 结束时重分配到 Tier 1
- **Tier 3 Sorted Set**：`BTreeMap<(due_height, timer_id), TimerMeta>`，长期定时器存储

**步骤 4：End-of-Block 执行**：
在每个区块处理结束后，从三层队列中取出到期定时器，按 `score = W_age * age + W_bid * bid_fp` 排序后投递到目标 Actor mailbox（受 `MAX_FIRES_PER_BLOCK` 限制）。

### 测试验收方案

**单元测试（`execution/src/tests/timer_tests.rs`）：**

```rust
#[tokio::test]
async fn test_schedule_timer_with_bid_fp() {
    let mut host = make_pvm_host();
    let timer_id = host.schedule_timer(
        100,           // due_height
        b"my_payload",
        50_000,        // gas_limit
        1u128 << 32,   // bid_fp = 1.0 in Q32.96
    ).unwrap();
    assert_eq!(timer_id.len(), 32);

    // 验证 bid_fp 被正确存储
    let stored = host.get_scheduled_timers();
    assert_eq!(stored[0].bid_fp, 1u128 << 32);
}

#[tokio::test]
async fn test_set_state_watch_triggers_on_key_change() {
    let mut store = TestStore::new();
    let actor = make_actor_address();

    // Actor 注册 STATE_WATCH
    set_state_watch(&mut store, actor, &[b"balance_key"], b"check_balance", 10_000, 0);

    // 修改被监视的 key
    store.set_storage(actor, b"balance_key", b"new_value");

    // End-of-Block 处理
    let fired = process_state_watch_timers(&mut store, current_block, &changed_keys);
    assert!(fired.iter().any(|f| f.target == actor));
}

#[tokio::test]
async fn test_tier1_timer_fires_at_correct_block() {
    let mut queue = TieredTimerQueue::new(100 /*base_block*/);
    queue.insert(TimerMeta { due_height: 105, actor: ADDR_A, bid_fp: 0, .. });
    queue.insert(TimerMeta { due_height: 110, actor: ADDR_B, bid_fp: 0, .. });

    let fired_at_105 = queue.drain_due(105);
    assert_eq!(fired_at_105.len(), 1);
    assert_eq!(fired_at_105[0].actor, ADDR_A);

    let fired_at_106 = queue.drain_due(106);
    assert_eq!(fired_at_106.len(), 0); // 尚未到期
}

#[tokio::test]
async fn test_higher_bid_timer_fires_first_at_budget_limit() {
    let mut queue = TieredTimerQueue::new(100);
    // 两个同 due_height 但不同 bid_fp 的定时器
    queue.insert(timer_with(101, 1u128 << 32, ADDR_A));  // bid = 1.0
    queue.insert(timer_with(101, 2u128 << 32, ADDR_B));  // bid = 2.0（更高）

    // 限制每块只触发 1 个
    let fired = queue.drain_due_with_budget(101, 1 /*MAX_FIRES_PER_BLOCK=1*/);
    assert_eq!(fired.len(), 1);
    assert_eq!(fired[0].actor, ADDR_B, "更高 bid 的定时器应优先触发");
}
```

**集成验收标准：**
- [ ] Actor 调用 `schedule_timer(height, payload, gas_limit, bid_fp)` 后，在指定 `height` 的区块中收到触发
- [ ] `set_state_watch` 在被监视 key 发生变化的区块末尾触发，未变化时不触发
- [ ] 三层队列：short-term（< 256 blocks）走 Ring Buffer，middle-term（< 16384 blocks）走 Epoch Queue，long-term 走 Sorted Set
- [ ] 每块最多触发 `MAX_FIRES_PER_BLOCK` 个定时器，更高 `bid_fp` 的定时器优先触发

---

## 七、Gas 成本数值与规格不符（CIP-3 / CIP-20）

### 问题描述

| 操作 | CIP 规格值 | Node 代码 (`execution/src/gas.rs`) | 偏差 |
|------|------------|-------------------------------------|------|
| `token_create` Cells 成本 | `len(name) + len(symbol) + 256` | 硬编码 `5,000` Cells | 不动态 |
| Transfer Hook 最大 Cycles | `50,000 Cycles`（CIP-20） | `500,000` | 超出 10 倍 |
| Storage KV 读取 | `10 Cycles`（CIP-3） | `storage_read_cycles: 50` | 5 倍偏高 |
| Storage KV 写入 | `50 Cycles`（CIP-3） | `storage_write_cycles: 10,000` | 200 倍偏高 |
| Mailbox send | `80 Cycles`（CIP-3） | `actor_message_send_cycles: 10,000` | 125 倍偏高 |
| Set/Cancel timer | `200 Cycles`（CIP-3） | 未在 `GasCosts` 中单独体现 | 缺失 |

### 技术解决方案

**`gas.rs` 修正方案：**

1. **`token_create` Cells 改为动态计算**（在 `token/core.rs` 调用处传入名称长度）：
   ```rust
   // token/core.rs 中
   let cells_cost = name.len() as u64 + symbol.len() as u64 + 256;
   gas_meters.cells.consume(cells_cost)?;
   ```
   `GasCosts` 中删除 `token_create_cells` 静态字段，改为计算常量 `TOKEN_CREATE_BASE_CELLS: u64 = 256`。

2. **`token_hook_max_cycles` 修正**：
   ```rust
   token_hook_max_cycles: 50_000,  // 从 500_000 改为 50_000
   ```

3. **PVM per-instruction 计量**（中长期）：
   CIP-3 中的 per-instruction Cycles 成本（算术=1，函数调用=10，kv读=10，kv写=50，发消息=80，设定时器=200）需在 PVM 解释器层实现，而非在 gas.rs 的事务级别。具体需要在 `pvm/vm/src/vm/` 中为各类字节码指令添加 metering 钩子。

4. **新增定时器 Gas 常量**：
   ```rust
   pub set_timer_cycles: u64,    // = 200
   pub cancel_timer_cycles: u64, // = 200（与 set 相同）
   ```

### 测试验收方案

**单元测试（`execution/src/gas_tests.rs`）：**

```rust
#[test]
fn test_token_create_cells_dynamic() {
    let name = "MyCoin";       // len = 6
    let symbol = "MC";         // len = 2
    // 期望 Cells = 6 + 2 + 256 = 264
    let expected_cells: u64 = 264;

    let mut gas = DualGasMeters::new(1_000_000, 1_000_000);
    charge_token_create_cells(&mut gas, name, symbol).unwrap();
    assert_eq!(gas.cells.used(), expected_cells);
}

#[test]
fn test_token_hook_max_cycles_is_50000() {
    let costs = GasCosts::default();
    assert_eq!(costs.token_hook_max_cycles, 50_000,
        "CIP-20 规定 Transfer Hook 最大 Cycles 为 50,000");
}

#[test]
fn test_storage_read_cycles_is_10() {
    let costs = GasCosts::default();
    assert_eq!(costs.storage_read_cycles, 10,
        "CIP-3 规定 Storage KV 读取为 10 Cycles");
}

#[test]
fn test_storage_write_cycles_is_50() {
    let costs = GasCosts::default();
    assert_eq!(costs.storage_write_cycles, 50,
        "CIP-3 规定 Storage KV 写入为 50 Cycles");
}

#[test]
fn test_mailbox_send_cycles_is_80() {
    let costs = GasCosts::default();
    assert_eq!(costs.actor_message_send_cycles, 80,
        "CIP-3 规定 Mailbox send 为 80 Cycles");
}

#[test]
fn test_set_cancel_timer_cycles_present() {
    let costs = GasCosts::default();
    assert_eq!(costs.set_timer_cycles, 200, "CIP-3 规定 set_timer 为 200 Cycles");
    assert_eq!(costs.cancel_timer_cycles, 200);
}
```

**集成验收标准：**
- [ ] 创建 name="LongTokenName"(14字节)、symbol="LTN"(3字节) 的 Token，实际消耗 Cells = 273
- [ ] Transfer Hook 超出 50,000 Cycles 后被终止，Token Transfer 不回滚（Hook 失败不影响转账）
- [ ] 所有 Gas 常量与 CIP-3/CIP-20 表格逐项对照无差异（可编写 `test_gas_table_matches_cip` 参数化测试）

---

## 八、EIP-1559 Basefee 调节机制（CIP-3）未实现

### 问题描述

**规格要求（CIP-3）：**
```
basefee_new = basefee_old * (1 + (U_x - T_x) / T_x / alpha)
```
每个区块对 Cycles 和 Cells 分别独立调节，变化幅度 ±12.5%，Basefee 全部燃烧（burn），Tip 归 proposer。

**实际代码：** 无任何 basefee 调节机制。`max_fee_per_cycle` 和 `max_fee_per_cell` 只是交易参数，无动态基础费用市场。

### 技术解决方案

**新增 `FeeState` 持久化结构并在每个区块末尾更新：**

```rust
// types/src/execution.rs 或新文件
pub struct FeeState {
    pub basefee_cycle: u64,  // 当前区块的 Cycles basefee（单位：CBY-wei/cycle）
    pub basefee_cell: u64,   // 当前区块的 Cells basefee
    pub last_cycle_usage: u64,
    pub last_cell_usage: u64,
}

impl FeeState {
    const TARGET_USAGE_RATIO: u64 = 50;  // 50% 为目标利用率
    const ALPHA: u64 = 8;                // 弹性系数
    const MAX_CHANGE_BPS: u64 = 1250;    // ±12.5%

    pub fn update(&mut self, cycle_usage: u64, cycle_capacity: u64,
                             cell_usage: u64, cell_capacity: u64) {
        self.basefee_cycle = adjust_basefee(
            self.basefee_cycle, cycle_usage, cycle_capacity / 2, Self::ALPHA, Self::MAX_CHANGE_BPS
        );
        self.basefee_cell = adjust_basefee(
            self.basefee_cell, cell_usage, cell_capacity / 2, Self::ALPHA, Self::MAX_CHANGE_BPS
        );
    }
}

fn adjust_basefee(base: u64, usage: u64, target: u64, alpha: u64, max_bps: u64) -> u64 {
    // base * (1 + (usage - target) / target / alpha)，限幅 ±max_bps/10000
    let delta_bps = ((usage as i128 - target as i128) * 10000)
        .checked_div(target as i128 * alpha as i128)
        .unwrap_or(0)
        .clamp(-(max_bps as i128), max_bps as i128);
    ((base as i128 * (10000 + delta_bps)) / 10000).max(1) as u64
}
```

**集成点：**
- `FeeState` 存储在 `cowboy-storage` 的 `BLOCKMETA` 命名空间（对应 CIP-4）
- `ExecutionEngine::finalize_block` 末尾调用 `fee_state.update(actual_usage...)`
- 交易验证时检查 `tx.max_fee_per_cycle >= fee_state.basefee_cycle`
- Basefee 部分（`basefee_cycle * cycles_used`）从发送方扣除后标记为 burnt（不计入任何余额）

### 测试验收方案

**单元测试（`execution/src/fee_tests.rs`，新建）：**

```rust
#[test]
fn test_basefee_increases_when_above_target() {
    let mut fee = FeeState { basefee_cycle: 1000, basefee_cell: 500, .. };
    // 利用率 80%，目标 50%，alpha=8
    // delta_bps = (80-50)/50/8 * 10000 = 750 bps → +7.5%，但限幅 12.5%
    fee.update(800, 1000, 500, 1000);
    // 1000 * (1 + 0.075) = 1075，在 ±12.5% 范围内
    assert!(fee.basefee_cycle > 1000 && fee.basefee_cycle <= 1125);
}

#[test]
fn test_basefee_decreases_when_below_target() {
    let mut fee = FeeState { basefee_cycle: 1000, basefee_cell: 500, .. };
    // 利用率 20%，低于目标 50%，basefee 应下降
    fee.update(200, 1000, 200, 1000);
    assert!(fee.basefee_cycle < 1000);
}

#[test]
fn test_basefee_change_clamped_at_12_5_percent() {
    let mut fee = FeeState { basefee_cycle: 1000, basefee_cell: 500, .. };
    // 极端情况：利用率 100%，变化应限幅在 +12.5%
    fee.update(1000, 1000, 1000, 1000);
    assert_eq!(fee.basefee_cycle, 1125, "最大涨幅应为 12.5%（1000 → 1125）");
}

#[test]
fn test_basefee_cycle_and_cell_independent() {
    let mut fee = FeeState { basefee_cycle: 1000, basefee_cell: 500, .. };
    // Cycles 高利用率，Cells 低利用率
    fee.update(900, 1000, 100, 1000);
    assert!(fee.basefee_cycle > 1000, "Cycles basefee 应上涨");
    assert!(fee.basefee_cell < 500, "Cells basefee 应下降");
}

#[test]
fn test_tx_rejected_when_max_fee_below_basefee() {
    let fee = FeeState { basefee_cycle: 2000, .. };
    let tx = make_tx(|t| t.max_fee_per_cycle = 1000); // 低于 basefee
    let result = validate_tx_fee(&tx, &fee);
    assert!(matches!(result, Err(ExecutionError::MaxFeeTooLow { .. })));
}

#[tokio::test]
async fn test_basefee_burned_not_credited() {
    let mut store = TestStore::new();
    let proposer = make_address();
    let sender = make_address_with_balance(1_000_000);

    // 发送一笔消耗 1000 cycles 的交易，basefee=100, tip=10
    let tx = make_tx_with_fee(1000, 100 /*max_fee*/, 10 /*tip*/);
    execute_tx(&mut engine, &mut store, &tx, 1000 /*block*/);

    // proposer 只收到 tip 部分（tip * cycles_used = 10 * 1000 = 10000）
    // basefee 部分（100 * 1000 = 100000）应被 burn，不进入 proposer 账户
    let proposer_balance = get_balance(&store, proposer);
    assert_eq!(proposer_balance, 10_000, "proposer 只收 tip，basefee 应被 burn");
}
```

**集成验收标准：**
- [ ] 连续 10 个区块满载（利用率 100%），basefee 每块涨幅精确为 12.5%
- [ ] 连续 10 个区块空载（利用率 0%），basefee 每块降幅精确为 12.5%
- [ ] `max_fee_per_cycle < basefee_cycle` 的交易被拒绝（进入 mempool 时或执行前）
- [ ] 执行后，proposer 账户余额增量 = `tip * cycles_used`；总供应量减少 = `basefee * cycles_used`（验证通缩）

---

## 九、JobSpec 缺少 `required_runner_pool` 字段（CIP-2）

### 问题描述

**规格要求（CIP-2）：**
```rust
required_runner_pool: Option<Vec<u8>>  // 可选 Runner 池限制（Entitlement 控制）
```

**实际代码：** Node 和 Runner 的 `JobSpec` 结构体均无此字段，Entitlement 对 Runner 池的访问控制无法实现。

### 技术解决方案

**两处均需添加字段：**

1. **Node** `runner/src/types.rs`：
   ```rust
   pub struct JobSpec {
       // ...现有字段...
       pub required_runner_pool: Option<Vec<u8>>,  // 新增
   }
   ```

2. **Runner** `crates/runner-common/src/types.rs`：
   ```rust
   pub struct JobSpec {
       // ...现有字段...
       pub required_runner_pool: Option<Vec<u8>>,  // 新增
   }
   ```

3. **Node dispatcher 过滤逻辑补充**（配合问题三的解决方案）：
   若 `required_runner_pool` 非空，则在候选过滤时查询 Entitlement Registry，验证 Runner 是否拥有对应 pool 的 `RunnerJoinPool(pool_id)` 授权：
   ```rust
   if let Some(pool_id) = &job_spec.required_runner_pool {
       // 查询 entitlement registry：runner 是否有 RunnerJoinPool(pool_id) 权限
       && entitlement_checker.has_pool_access(store, runner.address, pool_id).await
   }
   ```

### 测试验收方案

**单元测试（`execution/src/runner/dispatcher_pool_tests.rs`）：**

```rust
#[tokio::test]
async fn test_required_runner_pool_filters_candidates() {
    let pool_id = b"premium_pool".to_vec();
    let job = make_job_with_pool(Some(pool_id.clone()));

    let runners = vec![
        make_runner_in_pool("premium_pool"),  // 有 pool 授权
        make_runner_no_pool(),                // 无 pool 授权
        make_runner_in_pool("other_pool"),    // 不同 pool
    ];

    let result = filter_candidates(&runners, &job);
    assert_eq!(result.len(), 1);
    assert!(runner_has_pool_access(&result[0], &pool_id));
}

#[tokio::test]
async fn test_none_required_pool_allows_all_healthy_runners() {
    let job = make_job_with_pool(None); // 无 pool 限制
    let runners = vec![
        make_runner_in_pool("any_pool"),
        make_runner_no_pool(),
    ];
    // 两者都是 Healthy，均应通过
    let result = filter_candidates(&runners, &job);
    assert_eq!(result.len(), 2);
}

#[test]
fn test_job_spec_serialization_includes_pool_field() {
    let job = JobSpec {
        required_runner_pool: Some(b"my_pool".to_vec()),
        // ...其余字段
    };
    let json = serde_json::to_string(&job).unwrap();
    assert!(json.contains("required_runner_pool"));

    let decoded: JobSpec = serde_json::from_str(&json).unwrap();
    assert_eq!(decoded.required_runner_pool, Some(b"my_pool".to_vec()));
}
```

**集成验收标准：**
- [ ] 含 `required_runner_pool` 的 Job 只分配给拥有对应 pool Entitlement 的 Runner
- [ ] `required_runner_pool = None` 的 Job 不受 pool 限制（行为与原来一致）
- [ ] `JobSpec` 序列化/反序列化往返后 `required_runner_pool` 字段无损

---

## 十、Secrets Manager（0x0004）和 TEE Verifier（0x0005）完全未实现

### 问题描述

**规格要求（CIP-2）：**
- `0x0004 Secrets Manager`：加密密钥/配置存储，TEE 证明门控释放
- `0x0005 TEE Verifier`：验证 SGX/TDX/SEV 远程证明，维护可信公钥注册表

**实际代码：**
- Node：系统 Actor 地址已定义，`system_instruction.rs` 无对应指令处理
- Runner `crates/secrets-manager/src/manager.rs`：全部为占位符
- Runner `crates/tee-verifier/src/verifier.rs`：全部为占位符
- Runner `crates/runner-tee/`：`runtime.rs` 和 `attestation.rs` 完全未实现

### 技术解决方案

**TEE Verifier（优先于 Secrets Manager，是其前提）：**

**Node 侧**：在 `types/src/execution.rs` 中新增 SystemInstruction：
```rust
SystemInstruction::TeeRegisterKey {
    tee_type: TeeType,         // Sgx | Tdx | Sev
    attestation_report: Vec<u8>,
    public_key: [u8; 65],      // secp256k1 uncompressed
},
SystemInstruction::TeeVerifyAttestation {
    runner: Address,
    attestation: TeeAttestation,
},
```

**Runner 侧**（`crates/tee-verifier/src/verifier.rs`）：
- SGX：调用 `sgx-dcap-quoteverify` 库验证 DCAP Quote
- TDX：调用 Intel TDX 证明验证 API
- SEV：调用 AMD SEV-SNP attestation 验证
- 存储：可信 Runner 地址 → TEE 公钥映射，持久化到链上 Actor 存储

**Secrets Manager**：
```rust
// Runner: crates/secrets-manager/src/manager.rs
pub struct SecretEntry {
    encrypted_value: Vec<u8>,  // AES-256-GCM 加密，key 由 TEE 密封
    tee_policy: TeePolicy,     // 需要 TEE 证明才能访问
    created_by: Address,
    expires_at: Option<u64>,
}
```
- 加密方案：存储时用 Actor owner 的公钥（或 TEE 测量值）作为 AEAD key 材料
- 访问时：Runner 提供 TEE 证明 → TEE Verifier 验证 → Secrets Manager 解密后在 TEE 内返回

**近期可行的简化方案**（不依赖 TEE 硬件）：
- Secrets Manager 仅做链上加密存储，用存储所有者私钥加密（secp256k1 ECIES）
- TEE 验证字段标记为 `optional`，待真实 TEE 硬件环境就绪后升级

### 测试验收方案

**TEE Verifier 单元测试（`crates/tee-verifier/tests/`）：**

```rust
#[test]
fn test_tee_register_key_stores_in_registry() {
    let mut verifier = MockTeeVerifier::new();
    let key = TeePublicKey { address: RUNNER_ADDR, key: [0x01u8; 65], tee_type: TeeType::Sgx };
    verifier.register_key(key.clone()).unwrap();

    let stored = verifier.get_key(RUNNER_ADDR).unwrap();
    assert_eq!(stored.key, key.key);
}

#[test]
fn test_invalid_attestation_rejected() {
    let verifier = MockTeeVerifier::new();
    let bad_attestation = TeeAttestation {
        tee_type: TeeType::Sgx,
        attestation_data: vec![0xFF; 100], // 无效数据
        measurement_hash: H256::zero(),
        signature: vec![],
    };
    assert!(verifier.verify_attestation(bad_attestation).is_err());
}
```

**Secrets Manager 单元测试（`crates/secrets-manager/tests/`）：**

```rust
#[tokio::test]
async fn test_store_and_retrieve_secret() {
    let mut manager = SecretsManagerImpl::new_in_memory();
    let secret_id = "api_key_001".to_string();
    let secret_value = b"sk-super-secret-value".to_vec();

    manager.store_secret(secret_id.clone(), secret_value.clone()).await.unwrap();
    let retrieved = manager.get_secret(secret_id, None).await.unwrap();

    assert_eq!(retrieved, secret_value);
}

#[tokio::test]
async fn test_secret_access_denied_without_tee_attestation_when_required() {
    let mut manager = SecretsManagerImpl::new_with_tee_policy();
    manager.store_secret("key".into(), b"val".to_vec()).await.unwrap();

    // 无 TEE 证明时应拒绝
    let result = manager.get_secret("key".into(), None).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_secret_not_accessible_after_expiry() {
    let mut manager = SecretsManagerImpl::new_in_memory();
    manager.store_secret_with_expiry("key".into(), b"val".to_vec(), 100 /*expires at block 100*/).await.unwrap();

    // 区块 101 后访问，应过期
    let result = manager.get_secret_at_block("key".into(), None, 101).await;
    assert!(matches!(result, Err(SecretsError::Expired)));
}
```

**系统验收标准：**
- [ ] TEE Verifier 系统 Actor（0x0005）对应指令在 `system_instruction.rs` 中有处理分支
- [ ] Secrets Manager 系统 Actor（0x0004）的 store/get/update/delete 指令可正常执行
- [ ] 存储的 Secret 经加密后持久化，明文不出现在链上存储
- [ ] TEE 模式下（`tee_required=true`），无有效证明的访问请求被拒绝

---

## 十一、Runner 注册签名验证缺失（CIP-2）

### 问题描述

**规格要求（CIP-2）：** 注册时必须验证 Runner 的 secp256k1 签名

**实际代码：**
- Node `execution/src/runner/registry.rs:54`：`// TODO: Implement signature verification`
- Runner `crates/runner-registry/src/registry.rs:96`：`// TODO: implement signature verification`

### 技术解决方案

**Node 侧**（`execution/src/runner/registry.rs`）：

注册消息签名方案：对 `RunnerRegistration` 的规范化序列化（Canonical CBOR）做 keccak256，再用 Runner 私钥签名。

```rust
fn verify_runner_registration_signature(
    registration: &RunnerRegistration,
    signature: &[u8; 65],  // secp256k1 ECDSA, r(32) || s(32) || v(1)
) -> Result<Address, ExecutionError> {
    // 1. 规范化序列化注册信息
    let message = canonical_cbor_serialize(registration);
    let hash = keccak256(&message);

    // 2. 恢复签名者地址（ecrecover）
    let recovered = ecrecover(&hash, signature)
        .map_err(|_| ExecutionError::InvalidSignature)?;

    // 3. 验证签名者与注册地址一致
    if recovered != registration.address {
        return Err(ExecutionError::InvalidSignature);
    }
    Ok(recovered)
}
```

`cowboy_types` 中的 `keccak256` 和 ecrecover 已可用（基于 `k256` crate）。Runner 注册时在 `register()` 调用前先签名，将签名作为 `RunnerRegister` 指令的 `signature` 字段提交。

### 测试验收方案

**单元测试（`execution/src/runner/registry_sig_tests.rs`）：**

```rust
#[test]
fn test_valid_signature_accepted() {
    let signing_key = make_secp256k1_key();
    let address = derive_eth_address(&signing_key);
    let registration = make_runner_registration(address);

    // 用 Runner 私钥对注册信息签名
    let msg = canonical_cbor_serialize(&registration);
    let hash = keccak256(&msg);
    let sig = signing_key.sign_prehash(&hash);

    let result = verify_runner_registration_signature(&registration, &sig.to_bytes());
    assert!(result.is_ok());
    assert_eq!(result.unwrap(), address);
}

#[test]
fn test_wrong_key_signature_rejected() {
    let attacker_key = make_secp256k1_key();
    let victim_address = derive_eth_address(&make_secp256k1_key());
    let registration = make_runner_registration(victim_address);

    // 用攻击者私钥签名（地址不匹配）
    let msg = canonical_cbor_serialize(&registration);
    let hash = keccak256(&msg);
    let sig = attacker_key.sign_prehash(&hash);

    let result = verify_runner_registration_signature(&registration, &sig.to_bytes());
    assert!(matches!(result, Err(ExecutionError::InvalidSignature)));
}

#[test]
fn test_tampered_registration_rejected() {
    let signing_key = make_secp256k1_key();
    let address = derive_eth_address(&signing_key);
    let mut registration = make_runner_registration(address);

    // 签名后篡改质押量
    let msg = canonical_cbor_serialize(&registration);
    let hash = keccak256(&msg);
    let sig = signing_key.sign_prehash(&hash);
    registration.stake = U256::from(999_999); // 篡改

    let result = verify_runner_registration_signature(&registration, &sig.to_bytes());
    assert!(matches!(result, Err(ExecutionError::InvalidSignature)));
}

#[tokio::test]
async fn test_runner_node_signs_registration_on_startup() {
    // 集成测试：runner-node 启动时自动签名注册信息
    let key_manager = KeyManager::load_or_generate("./test_data").await.unwrap();
    let registration = build_default_registration(&key_manager);
    let sig = key_manager.sign_registration(&registration);

    let result = verify_runner_registration_signature(&registration, &sig.0);
    assert!(result.is_ok());
}
```

**集成验收标准：**
- [ ] 使用错误私钥签名的注册请求被节点拒绝，返回 `InvalidSignature` 错误
- [ ] 注册后再次注册（`AlreadyRegistered`）被拒绝
- [ ] Runner node 启动时产生的注册交易签名可通过链上验证

---

## 十二、最低质押量不一致

### 问题描述

| 位置 | 最低质押 |
|------|----------|
| Runner Node `crates/runner-node/src/registration.rs` | 50,000 CBY |
| Runner Registry `crates/runner-registry/src/registry.rs:99` | 10,000 CBY（10^21 wei） |

### 技术解决方案

**统一为链上常量，两处均引用同一定义：**

在 `cowboy-runner-types`（或 `runner-common`）中定义：
```rust
/// 最低质押量：10,000 CBY（单位：CBY-wei，1 CBY = 10^18 wei）
pub const MIN_STAKE_CBY_WEI: u128 = 10_000 * 10u128.pow(18);
```

- Runner node `registration.rs` 中的 `50_000 CBY` 判断改为引用 `MIN_STAKE_CBY_WEI`
- Runner registry `registry.rs:99` 中的 `10_000_000_000_000_000_000_000` 改为引用 `MIN_STAKE_CBY_WEI`
- Node `execution/src/runner/registry.rs` 中也引用同一常量

最终数值由 CIP 或治理机制决定，推荐以 10,000 CBY 为准（Runner registry 的版本与 CIP-2 更一致）。

### 测试验收方案

**单元测试（`execution/src/runner/registry_stake_tests.rs`）：**

```rust
#[test]
fn test_min_stake_constant_is_unified() {
    // 两处引用同一常量，编译时验证
    assert_eq!(
        cowboy_runner_types::MIN_STAKE_CBY_WEI,
        runner_common::MIN_STAKE_CBY_WEI,
        "node 和 runner 的最低质押常量必须相同"
    );
}

#[tokio::test]
async fn test_registration_below_min_stake_rejected() {
    let mut registry = make_registry();
    let reg = make_registration_with_stake(
        U256::from(MIN_STAKE_CBY_WEI) - U256::one() // 刚好低于最低质押
    );
    let result = registry.register_runner(reg, dummy_sig()).await;
    assert!(matches!(result, Err(RegistryError::InsufficientStake { .. })));
}

#[tokio::test]
async fn test_registration_at_min_stake_accepted() {
    let mut registry = make_registry();
    let reg = make_registration_with_stake(U256::from(MIN_STAKE_CBY_WEI));
    // 有效签名
    let sig = make_valid_sig(&reg);
    let result = registry.register_runner(reg, sig).await;
    assert!(result.is_ok());
}
```

**集成验收标准：**
- [ ] Node 端和 Runner 端编译后 `MIN_STAKE_CBY_WEI` 值完全一致（可通过 `/health` 端点或日志输出验证）
- [ ] 低于最低质押的注册请求在 node 和 runner 两侧均被拒绝

---

## 十三、Runner 结果签名缺失（CIP-2）

### 问题描述

**规格要求（CIP-2）：** Runner 必须对结果签名，链上验证签名有效性

**实际代码：**
- `crates/runner-http/src/executor.rs`：`// TODO: sign result` → 返回 `Signature::zero()`
- `crates/runner-llm/src/executor.rs`：`// TODO: sign result` → 返回 `Signature::zero()`
- `crates/runner-mcp/src/executor.rs`：`// TODO: sign result` → 返回 `Signature::zero()`
- Node 验证器（`execution/src/runner/verifier.rs`）未验证签名

### 技术解决方案

**Runner 侧**：在 `JobExecutor` trait 中添加签名步骤，或在 `runner-node/src/executor.rs` 的提交流程中统一处理：

```rust
// runner-node/src/executor.rs（提交前统一签名）
pub async fn sign_result(
    result: &mut RunnerResult,
    signing_key: &SigningKey,
) {
    // 对结果数据做规范化序列化后签名
    let result_bytes = canonical_serialize_result(result);
    let hash = keccak256(&result_bytes);
    result.signature = Signature(signing_key.sign(&hash).to_bytes());
}

fn canonical_serialize_result(result: &RunnerResult) -> Vec<u8> {
    // 对 job_id + runner + data + usage 的 CBOR 序列化
    // 不含 signature 字段本身
    canonical_cbor(&(result.job_id, result.runner, &result.data, &result.usage))
}
```

**Node 验证器侧**（`execution/src/runner/verifier.rs`）：
```rust
fn verify_result_signature(result: &RunnerResult) -> Result<(), ExecutionError> {
    let result_bytes = canonical_serialize_result_for_verify(result);
    let hash = keccak256(&result_bytes);
    let recovered = ecrecover(&hash, &result.signature.0)?;
    if recovered != result.runner {
        return Err(ExecutionError::InvalidSignature);
    }
    Ok(())
}
```

### 测试验收方案

**单元测试（`runner/crates/runner-common/tests/signature_tests.rs`）：**

```rust
#[test]
fn test_result_signature_is_nonzero() {
    let signing_key = make_signing_key();
    let mut result = make_test_result();
    sign_result(&mut result, &signing_key);

    assert_ne!(result.signature.0, [0u8; 65], "签名不应为全零占位符");
}

#[test]
fn test_result_signature_verifiable_by_runner_address() {
    let signing_key = make_signing_key();
    let runner_address = derive_eth_address(&signing_key);
    let mut result = make_test_result();
    result.runner = runner_address;
    sign_result(&mut result, &signing_key);

    // 验证签名恢复出的地址与 runner 地址一致
    let result_bytes = canonical_serialize_result_for_verify(&result);
    let hash = keccak256(&result_bytes);
    let recovered = ecrecover(&hash, &result.signature.0).unwrap();
    assert_eq!(recovered, runner_address);
}

#[test]
fn test_tampered_result_signature_fails_verification() {
    let signing_key = make_signing_key();
    let runner_address = derive_eth_address(&signing_key);
    let mut result = make_test_result();
    result.runner = runner_address;
    sign_result(&mut result, &signing_key);

    // 签名后篡改结果数据
    result.data = serde_json::json!({"answer": "tampered"});

    let result_bytes = canonical_serialize_result_for_verify(&result);
    let hash = keccak256(&result_bytes);
    let recovered = ecrecover(&hash, &result.signature.0).unwrap();
    assert_ne!(recovered, runner_address, "篡改后签名验证应失败");
}
```

**Node 验证器测试（`execution/src/runner/verifier_sig_tests.rs`）：**

```rust
#[tokio::test]
async fn test_node_verifier_rejects_unsigned_result() {
    let mut engine = make_engine();
    let mut store = TestStore::new();
    let job_id = [0x01u8; 32];
    let unsigned_result = RunnerResult {
        signature: [0u8; 65], // 零签名
        // ...
    };
    let result = engine.handle_job_result_submit(&mut store, &job_id, &unsigned_result, ..).await;
    assert!(matches!(result, Err(ExecutionError::InvalidSignature)));
}
```

**集成验收标准：**
- [ ] Runner 提交结果时 `signature` 字段非全零
- [ ] Node 链上 Verifier 对每个提交的结果执行 `ecrecover` 验证，不匹配则拒绝
- [ ] 端到端测试：LLM Job 完整流程（提交 → 执行 → 签名 → 链上验证 → callback 触发）通过

---

## 十四、Entitlement 系统未完整实现（CIP-2）

### 问题描述

**规格要求（CIP-2）：** 完整 RBAC，含约束条件强制执行（有效期、使用次数、限额、速率限制、委托深度限制）

**实际代码：**
- `execution/src/entitlement/grant.rs:27`：`// For Global, only system admin (TODO).`
- `execution/src/entitlement/grant.rs:111`：`// TODO: Check depth`（委托深度检查未实现）
- `system_instruction.rs` 中只有 Entitlement **写入**指令，无**检查**指令——Actor 调用前的权限强制检查入口未建立

### 技术解决方案

**分两层实现：**

**层一：补全 grant.rs 中的约束检查**：
```rust
fn enforce_constraints(
    entitlement: &Entitlement,
    current_block: u64,
    action: &Action,
    amount: Option<u64>,
) -> Result<(), ExecutionError> {
    let c = &entitlement.constraints;
    // 有效期
    if let Some(from) = c.valid_from { if current_block < from { return Err(NotYetValid); } }
    if let Some(until) = c.valid_until { if current_block > until { return Err(Expired); } }
    // 使用次数
    if c.used_count >= c.max_uses && c.max_uses != u64::MAX { return Err(ExceededUses); }
    // 单次限额
    if let (Some(max), Some(amt)) = (c.max_amount_per_use, amount) {
        if amt > max { return Err(ExceedsAmountLimit); }
    }
    // 委托深度（遍历父链）
    if entitlement.delegation_depth >= c.delegation_depth_max { return Err(ExceedsDelegationDepth); }
    Ok(())
}
```

**层二：在 Actor 指令执行前接入 Entitlement 检查**：

在 `execute_actor_instruction`（`execution/src/execution/actor_instruction.rs`）中，对 token 操作、消息发送等敏感操作，调用 `entitlement_checker.check(store, caller, scope, action)`：
```rust
// Actor 调用 token_transfer 前检查 TokenTransfer 授权
if let Some(hook) = entitlement_config {
    self.entitlement_checker.check(
        store,
        &caller_address,
        Scope::Token(token_id),
        Action::TokenTransfer,
        Some(amount),
        block_height,
    ).await?;
}
```

**Global scope 的系统管理员**可暂定为 genesis 配置中的指定地址列表，待治理合约就绪后迁移。

### 测试验收方案

**单元测试（`execution/src/entitlement/constraint_tests.rs`）：**

```rust
#[tokio::test]
async fn test_entitlement_expired_rejected() {
    let mut store = TestStore::new();
    grant_entitlement(&mut store, GRANTEE, valid_until: 100 /*block*/);

    // 区块 101 时检查，应已过期
    let result = check_entitlement(&store, GRANTEE, &Action::TokenTransfer, 101).await;
    assert!(matches!(result, Err(EntitlementError::Expired)));
}

#[tokio::test]
async fn test_entitlement_max_uses_enforced() {
    let mut store = TestStore::new();
    grant_entitlement(&mut store, GRANTEE, max_uses: 3);

    for _ in 0..3 {
        consume_entitlement(&mut store, GRANTEE, &Action::TokenTransfer, 1).await.unwrap();
    }
    // 第 4 次使用应超出限制
    let result = consume_entitlement(&mut store, GRANTEE, &Action::TokenTransfer, 1).await;
    assert!(matches!(result, Err(EntitlementError::ExceededUses)));
}

#[tokio::test]
async fn test_delegation_depth_limit() {
    let mut store = TestStore::new();
    // 创建一个最大深度为 2 的授权
    let base_id = grant_entitlement(&mut store, ADDR_A, delegation_depth_max: 2);
    // 一级委托
    let del1_id = delegate_entitlement(&mut store, ADDR_A, ADDR_B, base_id, 1).await.unwrap();
    // 二级委托
    let del2_id = delegate_entitlement(&mut store, ADDR_B, ADDR_C, del1_id, 2).await.unwrap();
    // 三级委托应失败
    let result = delegate_entitlement(&mut store, ADDR_C, ADDR_D, del2_id, 3).await;
    assert!(matches!(result, Err(EntitlementError::ExceedsDelegationDepth)));
}

#[tokio::test]
async fn test_global_scope_only_system_admin() {
    let mut store = TestStore::new();
    let non_admin = make_random_address();
    // 非系统管理员尝试 Global 授权
    let result = grant_global_entitlement(&mut store, non_admin, GRANTEE, &Action::TokenMint).await;
    assert!(matches!(result, Err(EntitlementError::NotSystemAdmin)));
}

#[tokio::test]
async fn test_token_transfer_blocked_without_entitlement() {
    // 集成测试：未授权的 Actor 调用 token_transfer 被拦截
    let mut store = TestStore::new();
    let unauthorized_caller = make_actor();
    let result = execute_actor_token_transfer(
        &mut engine,
        &mut store,
        unauthorized_caller,
        TOKEN_ID, RECIPIENT, 100,
        /*require_entitlement=*/ true
    ).await;
    assert!(matches!(result, Err(ExecutionError::EntitlementDenied)));
}
```

**集成验收标准：**
- [ ] `valid_until` 到期的 Entitlement 在期满区块后拒绝所有操作
- [ ] `max_uses` 耗尽的 Entitlement 拒绝继续使用
- [ ] 委托深度超过 `delegation_depth_max` 的委托操作被拒绝
- [ ] 无 `TokenTransfer` Entitlement 的 Actor 调用 token 操作时被拦截（前提：Actor 被配置为需要 Entitlement 检查）
- [ ] `Global` scope 的授权只有系统管理员地址可以发起

---

## 十五、CBOR 格式 JobSpec 解析不完整

### 问题描述

**实际代码** (`execution/src/runner/dispatcher.rs:92-110`)，Python SDK 发来的 CBOR 格式只处理了 `"llm"` job type：

```rust
match job_type_str.as_str() {
    "llm" => { ... }
    _ => return Err(ExecutionError::InvalidData),  // HTTP、MCP、Custom 均不支持
}
```

### 技术解决方案

在 `parse_job_spec` 的 CBOR 分支中补充 `"http"`、`"mcp"`、`"custom"` 的解析逻辑：

```rust
"http" => {
    let url = cbor_map_get_str(&kwargs, "url").unwrap_or_default();
    let method = cbor_map_get_str(&kwargs, "method").unwrap_or("GET".into());
    let headers = cbor_map_get_map_str(&kwargs, "headers").unwrap_or_default();
    let body = cbor_map_get_bytes(&kwargs, "body");
    JobType::Http { url, method, headers, body, extraction: None, freshness: None }
}
"mcp" => {
    let server = cbor_map_get_str(&kwargs, "server").unwrap_or_default();
    let tool_name = cbor_map_get_str(&kwargs, "tool_name").unwrap_or_default();
    let arguments = cbor_map_get_json(&kwargs, "arguments").unwrap_or(serde_json::Value::Null);
    let timeout = cbor_map_get_u64(&kwargs, "timeout_seconds");
    JobType::Mcp { server, tool_name, arguments, timeout_seconds: timeout }
}
"custom" => {
    let executor_hash = cbor_map_get_bytes32(&kwargs, "executor_hash").unwrap_or([0u8; 32]);
    let params = cbor_map_get_bytes(&kwargs, "params").unwrap_or_default();
    JobType::Custom { executor_hash, params }
}
```

同时建议为 Python SDK 的 CBOR 格式编写单元测试，保证与 SDK 的序列化格式对齐。

### 测试验收方案

**单元测试（`execution/src/runner/cbor_parse_tests.rs`）：**

```rust
fn make_cbor_job(job_type: &str, kwargs: Vec<(ciborium::Value, ciborium::Value)>) -> Vec<u8> {
    let mut map = vec![
        (ciborium::Value::Text("kind".into()), ciborium::Value::Text("runner_job".into())),
        (ciborium::Value::Text("job_type".into()), ciborium::Value::Text(job_type.into())),
        (ciborium::Value::Text("payload".into()), ciborium::Value::Map(vec![
            (ciborium::Value::Text("kwargs".into()), ciborium::Value::Map(kwargs)),
        ])),
        (ciborium::Value::Text("reply_handler".into()), ciborium::Value::Text("on_result".into())),
    ];
    let mut buf = Vec::new();
    ciborium::into_writer(&ciborium::Value::Map(map), &mut buf).unwrap();
    buf
}

#[test]
fn test_cbor_http_job_parsed_correctly() {
    let cbor = make_cbor_job("http", vec![
        (ciborium::Value::Text("url".into()), ciborium::Value::Text("https://api.example.com".into())),
        (ciborium::Value::Text("method".into()), ciborium::Value::Text("GET".into())),
    ]);
    let spec = parse_job_spec(&cbor, &SUBMITTER_ADDR).unwrap();
    match spec.job_type {
        JobType::Http { url, method, .. } => {
            assert_eq!(url, "https://api.example.com");
            assert_eq!(method, "GET");
        }
        _ => panic!("应解析为 Http 类型"),
    }
}

#[test]
fn test_cbor_mcp_job_parsed_correctly() {
    let args_json = serde_json::json!({"symbol": "BTC"});
    let cbor = make_cbor_job("mcp", vec![
        (ciborium::Value::Text("server".into()), ciborium::Value::Text("crypto-price".into())),
        (ciborium::Value::Text("tool_name".into()), ciborium::Value::Text("get-crypto-price".into())),
        (ciborium::Value::Text("arguments".into()), json_to_cbor(&args_json)),
    ]);
    let spec = parse_job_spec(&cbor, &SUBMITTER_ADDR).unwrap();
    match spec.job_type {
        JobType::Mcp { server, tool_name, .. } => {
            assert_eq!(server, "crypto-price");
            assert_eq!(tool_name, "get-crypto-price");
        }
        _ => panic!("应解析为 Mcp 类型"),
    }
}

#[test]
fn test_cbor_custom_job_parsed_correctly() {
    let executor_hash = [0xBEu8; 32];
    let cbor = make_cbor_job("custom", vec![
        (ciborium::Value::Text("executor_hash".into()), ciborium::Value::Bytes(executor_hash.to_vec())),
        (ciborium::Value::Text("params".into()), ciborium::Value::Bytes(b"custom_params".to_vec())),
    ]);
    let spec = parse_job_spec(&cbor, &SUBMITTER_ADDR).unwrap();
    match spec.job_type {
        JobType::Custom { executor_hash: eh, params } => {
            assert_eq!(eh, executor_hash);
            assert_eq!(params, b"custom_params");
        }
        _ => panic!("应解析为 Custom 类型"),
    }
}
```

**集成验收标准（Python SDK 端对端）：**
- [ ] Python SDK 调用 `runner.http("https://example.com")` 产生的 CBOR 数据可被 node 正确解析为 `JobType::Http`
- [ ] Python SDK 调用 `runner.mcp("crypto-price", "get-crypto-price", {...})` 可被解析为 `JobType::Mcp`
- [ ] 四种 job type 各有一个 Python SDK → chain → runner 的端到端烟雾测试

---

## 十六、Runner P2P 共识通信未实现

### 问题描述

**规格要求（CIP-2）：** N-of-M 模式下 Runner 之间需通过 P2P 网络协作共识

**实际代码** (`crates/runner-consensus/src/consensus.rs`)：`ConsensusClient` 是空结构体，所有方法返回占位符结果。

### 技术解决方案

**短期（不需要真正 P2P）：** 利用链作为协调层

Runner 不相互通信，各自独立向链提交结果。链上 Verifier 在收齐足够多的结果后执行验证。这适用于 `MajorityVote` 和 `StructuredMatch` 模式。

**中期（需要 Aggregator 收集）：** HTTP Pull 模式

Aggregator（信誉最高的 Runner）通过 HTTP 主动拉取其他 Runner 的结果：
```rust
// crates/runner-consensus/src/aggregation.rs
pub struct AggregatorClient {
    http_client: reqwest::Client,
}

impl AggregatorClient {
    pub async fn collect_results(
        &self,
        job_id: JobId,
        runner_endpoints: &[(Address, String)],  // (address, http_endpoint)
        timeout: Duration,
    ) -> Vec<(Address, RunnerResult)> {
        let futs = runner_endpoints.iter().map(|(addr, url)| {
            self.http_client
                .get(format!("{}/result/{}", url, hex::encode(job_id)))
                .timeout(timeout)
                .send()
        });
        // 并发拉取，忽略超时的 Runner
        futures::future::join_all(futs).await
            .into_iter().flatten().collect()
    }
}
```

Runner 节点需要暴露 `/result/{job_id}` HTTP 端点，在 `runner-node/src/node.rs` 中添加即可（无需真正 P2P）。

### 测试验收方案

**单元测试（`runner/crates/runner-consensus/tests/p2p_tests.rs`）：**

```rust
#[tokio::test]
async fn test_chain_as_coordinator_collects_n_results() {
    // 短期方案：3 个 Runner 各自独立向 mock 链提交结果
    let mut mock_chain = MockChainClient::new();
    let job_id = H256::random();

    for i in 0..3u8 {
        let key = make_signing_key_i(i as u32);
        let result = make_signed_result(&key, &job_id.into());
        mock_chain.submit_result(job_id, result).await.unwrap();
    }

    // 验证链上收到 3 个结果
    let results = mock_chain.get_results(job_id).await;
    assert_eq!(results.len(), 3);
}

#[tokio::test]
async fn test_aggregator_pulls_result_via_http() {
    // 启动一个 mock runner HTTP 服务，暴露 /result/{job_id}
    let mock_server = MockRunnerServer::start().await;
    let job_id = [0x42u8; 32];
    mock_server.set_result(job_id, make_test_result(job_id));

    let aggregator = AggregatorClient::new(reqwest::Client::new());
    let results = aggregator.collect_results(
        job_id,
        &[(mock_server.address(), mock_server.url())],
        Duration::from_secs(5),
    ).await;

    assert_eq!(results.len(), 1);
}

#[tokio::test]
async fn test_runner_node_exposes_result_endpoint() {
    // 集成测试：runner node 启动后可通过 /result/{job_id} 端点拉取结果
    let node = start_test_runner_node().await;
    let job_id = [0x01u8; 32];
    node.simulate_job_completion(job_id, make_test_result(job_id)).await;

    let resp = reqwest::get(format!("{}/result/{}", node.url(), hex::encode(job_id)))
        .await.unwrap();
    assert_eq!(resp.status(), 200);
    let result: RunnerResult = resp.json().await.unwrap();
    assert_eq!(result.job_id, H256::from(job_id));
}
```

**集成验收标准：**
- [ ] 短期方案：3 个独立 Runner 各自向链提交结果，链上 Verifier 在 threshold 达到时触发 callback
- [ ] 中期方案：Aggregator 成功通过 HTTP 从其他 Runner 拉取结果（模拟 2/3 Runner 响应成功）
- [ ] Aggregator 超时时（1/3 Runner 无响应），有超时机制而不会阻塞整个流程

---

## 十七、LLM Executor - Anthropic API 和本地模型未实现

### 问题描述

**规格要求（白皮书）：** Runner 支持多 LLM 提供商，包括 OpenAI、Anthropic 及开源本地模型

**实际代码：**
- `crates/runner-llm/src/api.rs`：`AnthropicClient::chat_completion()` 有 TODO 注释，无实际 API 调用
- `crates/runner-llm/src/local.rs`：`LocalLlmClient` 完全未实现

### 技术解决方案

**Anthropic Claude API**（`crates/runner-llm/src/api.rs`）：

```rust
impl AnthropicClient {
    pub async fn chat_completion(&self, req: ChatRequest) -> Result<ChatResponse> {
        let body = serde_json::json!({
            "model": &self.model,
            "max_tokens": req.max_tokens,
            "messages": [{"role": "user", "content": req.user_prompt}],
            "system": req.system_prompt,
        });
        let resp = self.client
            .post("https://api.anthropic.com/v1/messages")
            .header("x-api-key", &self.api_key)
            .header("anthropic-version", "2023-06-01")
            .json(&body)
            .send().await?
            .json::<serde_json::Value>().await?;
        // 解析 resp["content"][0]["text"]
        let text = resp["content"][0]["text"].as_str().unwrap_or("").to_string();
        Ok(ChatResponse { content: text, input_tokens: ..., output_tokens: ... })
    }
}
```

**本地模型**（`crates/runner-llm/src/local.rs`）：

通过兼容 OpenAI API 格式的本地端点（如 Ollama、llama.cpp server）实现，仅需将 `base_url` 指向本地服务：
```rust
pub struct LocalLlmClient {
    inner: OpenAIClient,  // 复用 OpenAI client，base_url 设为 http://localhost:11434/v1
}
```

Runner 配置中新增 `LOCAL_LLM_BASE_URL` 环境变量支持。

### 测试验收方案

**单元测试（`runner/crates/runner-llm/tests/`）：**

```rust
#[tokio::test]
async fn test_anthropic_client_chat_completion() {
    // 使用 wiremock 模拟 Anthropic API
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/messages"))
        .and(header("x-api-key", "test-key"))
        .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
            "content": [{"type": "text", "text": "Hello from Claude!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}
        })))
        .mount(&server).await;

    let client = AnthropicClient::new("test-key".into(), "claude-3-haiku-20240307".into());
    let resp = client.chat_completion(ChatRequest {
        user_prompt: "Hello".into(),
        system_prompt: None,
        max_tokens: 100,
        temperature: Some(0.7),
    }).await.unwrap();

    assert_eq!(resp.content, "Hello from Claude!");
    assert_eq!(resp.input_tokens, 10);
    assert_eq!(resp.output_tokens, 5);
}

#[tokio::test]
async fn test_local_llm_uses_openai_compatible_api() {
    // 本地模型服务器（Ollama 兼容 OpenAI API）
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/chat/completions"))
        .respond_with(ResponseTemplate::new(200).set_body_json(openai_response("Local response")))
        .mount(&server).await;

    std::env::set_var("LOCAL_LLM_BASE_URL", server.uri());
    let executor = LlmExecutor::new_with_local();
    let result = executor.execute(&make_llm_job("What is 1+1?")).await.unwrap();
    assert!(result.data["result"].as_str().unwrap().contains("Local response"));
}

#[test]
fn test_provider_selection_by_available_env_var() {
    std::env::set_var("ANTHROPIC_API_KEY", "sk-ant-test");
    std::env::remove_var("OPENAI_API_KEY");

    let executor = LlmExecutor::new();
    assert!(matches!(executor.provider, LlmProvider::Anthropic(_)));
}
```

**集成验收标准：**
- [ ] 设置 `ANTHROPIC_API_KEY` 后，LLM Job 使用 Anthropic API（通过日志中的 API host 确认）
- [ ] 设置 `LOCAL_LLM_BASE_URL` 后，请求发送到本地端点（Ollama/llama.cpp）
- [ ] 两种提供商的响应格式均能正确解析为 `RunnerResult.data`

---

## 十八、HTTP Executor - XPath/JSONPath 数据提取未实现

### 问题描述

**规格要求（CIP-2）：** HTTP JobType 支持 CSS Selector、XPath、JSONPath、Regex 四种提取方式

**实际代码** (`crates/runner-http/src/extractor.rs`)：CSS 选择器已实现，XPath/JSONPath/Freshness 均为 TODO。

### 技术解决方案

**依赖选型：**
- XPath：`sxd-xpath` crate（纯 Rust，无 C 依赖）
- JSONPath：`jsonpath-rust` crate
- Freshness 时间戳解析：`chrono` crate（已在 runner-common 中使用）

**XPath 实现**（`extractor.rs`）：
```rust
ExtractionMethod::XPath => {
    let package = sxd_document::parser::parse(&body_str)?;
    let document = package.as_document();
    let xpath = sxd_xpath::Factory::new().build(&selector)?.unwrap();
    let context = sxd_xpath::Context::new();
    let value = xpath.evaluate(&context, document.root())?;
    Ok(value.string())
}
```

**JSONPath 实现**：
```rust
ExtractionMethod::JsonPath => {
    let json: serde_json::Value = serde_json::from_str(&body_str)?;
    let result = jsonpath_rust::JsonPathFinder::from_str(&body_str, &selector)?
        .find_as_path();
    Ok(result.to_string())
}
```

**Freshness 检查**（`executor.rs`）：
```rust
if let Some(freshness) = &http_job.freshness {
    let age_seconds = match freshness.reference {
        FreshnessReference::Block => {
            // 用区块高度估算时间（block_height * 1s）
            (current_block - job_spec.submitted_at) as u64
        }
        FreshnessReference::Absolute => {
            fetch_time.elapsed().as_secs()
        }
    };
    if age_seconds > freshness.max_age_seconds {
        return Err(ExecutorError::DataStale { age_seconds, max: freshness.max_age_seconds });
    }
}
```

### 测试验收方案

**单元测试（`runner/crates/runner-http/tests/extractor_tests.rs`）：**

```rust
const HTML: &str = r#"<html><body>
  <div class="price">$42,000</div>
  <p id="desc">Bitcoin</p>
</body></html>"#;

const JSON: &str = r#"{"market": {"btc": {"price": 42000, "currency": "USD"}}}"#;

const XML: &str = r#"<?xml version="1.0"?>
<market><btc><price>42000</price></btc></market>"#;

#[test]
fn test_css_selector_extraction() {
    let result = extract(HTML, &ExtractionConfig {
        method: ExtractionMethod::CssSelector,
        selectors: [("price".into(), ".price".into())].into(),
        schema: dummy_schema(),
    }).unwrap();
    assert_eq!(result["price"], "$42,000");
}

#[test]
fn test_jsonpath_extraction() {
    let result = extract(JSON, &ExtractionConfig {
        method: ExtractionMethod::JsonPath,
        selectors: [("price".into(), "$.market.btc.price".into())].into(),
        schema: dummy_schema(),
    }).unwrap();
    assert_eq!(result["price"], 42000);
}

#[test]
fn test_xpath_extraction() {
    let result = extract(XML, &ExtractionConfig {
        method: ExtractionMethod::XPath,
        selectors: [("price".into(), "/market/btc/price/text()".into())].into(),
        schema: dummy_schema(),
    }).unwrap();
    assert_eq!(result["price"], "42000");
}

#[test]
fn test_regex_extraction() {
    let html = "<title>BTC Price: $42,000 USD</title>";
    let result = extract(html, &ExtractionConfig {
        method: ExtractionMethod::Regex,
        selectors: [("price".into(), r"\$([0-9,]+)".into())].into(),
        schema: dummy_schema(),
    }).unwrap();
    assert_eq!(result["price"], "42,000");
}

#[tokio::test]
async fn test_freshness_check_rejects_stale_data() {
    let executor = HttpExecutor::new();
    // Job 要求数据不超过 60 秒
    let job = make_http_job_with_freshness(FreshnessConfig {
        max_age_seconds: 60,
        reference: FreshnessReference::Submission,
        timestamp_field: None,
    });
    // 模拟 job 提交于 200 秒前
    let result = executor.execute_at_block(&job, current_block, submitted_block - 200).await;
    assert!(matches!(result, Err(ExecutorError::DataStale { .. })));
}
```

**集成验收标准：**
- [ ] 四种提取方式（CSS / XPath / JSONPath / Regex）各有测试用例通过
- [ ] Freshness 超时的 HTTP Job 返回 `DataStale` 错误，不提交到链上
- [ ] 提取失败（选择器未匹配）时返回明确的错误而非空字符串

---

## 十九、CIP-1 Actor 调度器（Tiered Queue）未在 Node 中实现

### 问题描述

**规格要求（CIP-1）：** 三层调度队列、Gas 竞价代理（GBA）、per-actor priority weights 指数衰减更新、饥饿保护机制

**实际代码：** Node 中无任何对应实现，仅有简单的 height-triggered 定时器。

### 技术解决方案

**CIP-1 的调度器实现是一个独立的子系统，建议新建 `cowboy-scheduler` crate：**

```
node/scheduler/
├── src/
│   ├── lib.rs
│   ├── timer_queue.rs    # 三层队列实现
│   ├── gba.rs            # Gas Bidding Agent 接口
│   ├── scorer.rs         # 评分与排序
│   └── globalbox.rs      # Global Fire Queue（跨块持久化队列）
```

**三层队列核心数据结构**：
```rust
pub struct TieredTimerQueue {
    // Tier 1：Ring Buffer，覆盖未来 N 个区块（N=256）
    tier1: Vec<Vec<TimerRef>>,   // indexed by (block_height % 256)
    tier1_base: u64,             // tier1[0] 对应的区块高度

    // Tier 2：Epoch Array，覆盖 E 个 epoch（E=64，每 epoch 256 块）
    tier2: Vec<Vec<TimerRef>>,   // indexed by epoch_index

    // Tier 3：Overflow Sorted Set（长期定时器）
    tier3: BTreeMap<(u64, [u8; 32]), TimerMeta>,  // key: (due_height, timer_id)
}
```

**End-of-Block 处理**：
1. 取出 Tier 1 当前 slot 的所有到期定时器
2. 按 `score = W_age * age_blocks + W_bid * bid_fp` 排序
3. 受 `MAX_FIRES_PER_BLOCK`（上限）和 `MAX_FIRES_PER_TARGET`（每 Actor 上限）约束，选取最高分者投递
4. 将 Tier 2/Tier 3 中到期的定时器迁移到 Tier 1

**GBA 接口**：Actor 在注册定时器时可提供一个 GBA 合约地址，每次到期前调用 GBA 获取当前愿意支付的 bid，实现动态竞价。

### 测试验收方案

**单元测试（`node/scheduler/src/tests.rs`，新建 crate 后添加）：**

```rust
#[test]
fn test_tier1_ring_buffer_o1_insert() {
    let mut queue = TieredTimerQueue::new(0 /*base_block*/);
    // 插入 255 个定时器（均在 Tier 1 范围内）
    for i in 1u64..=255 {
        queue.insert(make_timer(i /*due_height*/));
    }
    // 插入 256 个定时器（在 Tier 2 范围）
    queue.insert(make_timer(300));
    assert_eq!(queue.tier1_count(), 255);
    assert_eq!(queue.tier2_count(), 1);
}

#[test]
fn test_timer_migrates_tier2_to_tier1_at_epoch_boundary() {
    let mut queue = TieredTimerQueue::new(0);
    queue.insert(make_timer(512 /*Tier 2*/));

    // 推进到 epoch 边界（假设 epoch = 256 blocks）
    queue.advance_to_block(256);
    assert_eq!(queue.tier1_count(), 1, "Tier 2 中到期 timer 应迁移到 Tier 1");
}

#[tokio::test]
async fn test_gba_bid_updates_timer_priority() {
    // Actor 提供 GBA 合约，返回动态 bid_fp
    let mut store = TestStore::new();
    let actor = deploy_actor_with_gba(&mut store, /*gba returns bid=2.0*/);
    let timer_id = schedule_timer_with_gba(&mut store, actor, 100, b"payload");

    // 到期时 GBA 被调用，返回 bid_fp = 2.0
    let fired = process_timers_with_gba(&mut store, 100).await;
    assert_eq!(fired[0].bid_fp, 2u128 << 32, "GBA 提供的 bid 应更新到 MailboxEntry");
}

#[test]
fn test_starvation_protection_fires_old_timer() {
    let mut queue = TieredTimerQueue::new(0);
    // 低 bid 定时器，在区块 1 到期
    queue.insert(timer_with_bid(1, 0)); // bid = 0
    // 大量高 bid 定时器持续涌入
    for _ in 0..100 {
        queue.insert(timer_with_bid(2, u128::MAX)); // 极高 bid
    }
    // 即使高 bid 定时器很多，低 bid 且超期的定时器（age 很大）也应被触发
    let fired = queue.drain_due_with_budget(50, 5 /*MAX_FIRES*/);
    assert!(fired.iter().any(|t| t.bid_fp == 0), "饥饿保护：超期低 bid 定时器应被触发");
}
```

**集成验收标准：**
- [ ] 注册 1000 个定时器（不同到期高度），全部在正确区块触发，无遗漏
- [ ] `MAX_FIRES_PER_BLOCK` 设为 10 时，单块最多触发 10 个定时器（超出部分延迟）
- [ ] 同一区块有 100 个定时器到期时，高 `bid_fp` 的先触发
- [ ] 老化（age 大）的低 bid 定时器在饥饿保护阈值后被强制触发

---

## 二十、CIP-4 存储——双 VM 命名空间未确认实现

### 问题描述

**规格要求（CIP-4）：** 统一存储键格式 `0x1 || keccak(address) || vm_ns || slot_key32`，`vm_ns=0x00` 为 PyVM，`vm_ns=0x01` 为 EVM

**实际代码：** Node storage 层使用不同的抽象接口，未见 `vm_ns` 命名空间的显式处理。

### 技术解决方案

**需调查并补全 `cowboy-storage` crate 的键格式：**

1. **调查现状**：检查 `storage/src/` 中 `set_actor_storage` 和 `get_actor_storage` 的键构造逻辑，确认是否已包含 vm_ns 前缀。

2. **若未实现**，在 `storage/src/keys.rs`（或等价位置）统一定义：
   ```rust
   pub fn actor_storage_key(address: &Address, vm_ns: u8, slot_key: &[u8; 32]) -> Vec<u8> {
       let mut key = vec![0x01u8];                       // namespace prefix
       key.extend_from_slice(&keccak256(address.as_ref()));
       key.push(vm_ns);                                  // 0x00=PyVM, 0x01=EVM
       key.extend_from_slice(slot_key);
       key
   }
   ```

3. **迁移注意**：若线上数据已用不含 vm_ns 的旧格式存储，需要迁移脚本或在读取时做向后兼容（旧键无 vm_ns 字节则默认为 PyVM=0x00）。

4. **MPT 集成**：CIP-4 要求所有写操作经过 Merkle-Patricia Trie 以生成 `state_root`，需确认 `cowboy-storage` 是否已实现 MPT，或还是使用扁平 KV 存储（RocksDB/sled）。若未实现 MPT，这是较大的工程项，建议单独立项。

### 测试验收方案

**单元测试（`node/storage/src/key_format_tests.rs`）：**

```rust
#[test]
fn test_actor_storage_key_includes_vm_ns() {
    let address = Address::from_low_u64(0x1234);
    let slot = [0x01u8; 32];

    let pyvm_key = actor_storage_key(&address, VM_NS_PYVM, &slot);
    let evm_key  = actor_storage_key(&address, VM_NS_EVM,  &slot);

    // 前缀 0x01
    assert_eq!(pyvm_key[0], 0x01);
    // keccak(address) 部分（32字节）
    assert_eq!(&pyvm_key[1..33], keccak256(address.as_ref()).as_ref());
    // vm_ns 字节
    assert_eq!(pyvm_key[33], VM_NS_PYVM);
    // slot_key 部分
    assert_eq!(&pyvm_key[34..66], &slot);

    // PyVM 和 EVM 的 key 不同
    assert_ne!(pyvm_key, evm_key);
}

#[test]
fn test_pyvm_and_evm_storage_isolated() {
    // 同一地址的 PyVM 和 EVM 存储 slot 相互隔离
    let address = Address::from_low_u64(0x42);
    let slot = [0xAAu8; 32];

    let pyvm_key = actor_storage_key(&address, VM_NS_PYVM, &slot);
    let evm_key  = actor_storage_key(&address, VM_NS_EVM,  &slot);

    // 写入 PyVM 的值不影响 EVM
    let mut store = InMemoryStore::new();
    store.set(&pyvm_key, b"pyvm_value");
    assert!(store.get(&evm_key).is_none(), "EVM 命名空间应独立于 PyVM");
}

#[tokio::test]
async fn test_backward_compat_old_key_format() {
    // 测试旧格式（无 vm_ns 字节）的读取兼容性
    let address = Address::from_low_u64(0x42);
    let slot = [0xBBu8; 32];

    // 旧格式键（不含 vm_ns）
    let old_key = make_old_format_key(&address, &slot);
    let mut store = InMemoryStore::new();
    store.set(&old_key, b"legacy_value");

    // 新格式读取时，若未找到则回退到旧格式（向后兼容）
    let result = store.get_with_compat(&address, VM_NS_PYVM, &slot);
    assert_eq!(result, Some(b"legacy_value".to_vec()));
}

#[test]
fn test_state_root_changes_when_storage_written() {
    let mut store = TestStore::new();
    let state_root_before = store.compute_state_root();

    let address = Address::from_low_u64(0x01);
    store.set_actor_storage(&address, VM_NS_PYVM, &[0x01u8; 32], b"value");

    let state_root_after = store.compute_state_root();
    assert_ne!(state_root_before, state_root_after, "写入存储后 state_root 应变化");
}
```

**集成验收标准：**
- [ ] PyVM Actor 的存储操作不影响 EVM 命名空间（同地址同 slot 隔离验证）
- [ ] 存储键格式与 CIP-4 规定的 `0x1 || keccak(address) || vm_ns || slot_key32` 完全一致
- [ ] 区块执行后 `header.state_root` 与链上 MPT 计算结果一致（现有集成测试中已有验证）
- [ ] 旧格式数据（如已有生产数据）可通过兼容路径正常读取

---

## 优先级汇总

### 严重（影响正确性和安全性）
| # | 问题 | 解决方案要点 | 估计工作量 | 关键验收测试 |
|---|------|--------------|------------|--------------|
| 1 | Node/Runner 数据类型大量不一致 | 新建 `cowboy-runner-types` 共享 crate | 中（3-5天） | `test_runner_registration_node_runner_roundtrip` |
| 2 | VRF 选择算法不符合 CIP-2 规格 | 替换为 Keccak256 种子 + Fisher-Yates + 质押权重 | 小（1-2天） | `test_vrf_seed_matches_cip2_spec`、`test_stake_weight_is_log2_compressed` |
| 3 | Runner 结果签名为零 | 在提交流程中统一签名，验证器侧添加 ecrecover | 小（1天） | `test_runner_result_signature_valid`、`test_zero_signature_rejected` |
| 4 | Commit-Reveal 聚合协议未实现 | 先实现多结果直接链上提交投票，再迭代 Commit-Reveal | 大（1-2周） | `test_commit_reveal_full_flow`、`test_commit_reveal_slash_on_reveal_mismatch` |

### 高（功能缺失）
| # | 问题 | 解决方案要点 | 估计工作量 | 关键验收测试 |
|---|------|--------------|------------|--------------|
| 5 | 超时重选机制未实现 | End-of-Block 超时检查 + 声誉惩罚 + 重选逻辑 | 中（3-5天） | `test_job_timeout_triggers_reselection`、`test_timeout_reputation_penalty` |
| 6 | Secrets Manager 完全未实现 | 先实现 ECIES 加密存储，TEE 门控后续迭代 | 大（1周+） | `test_secret_store_and_retrieve_ecies`、`test_secret_access_unauthorized_rejected` |
| 7 | TEE Verifier 完全未实现 | 集成 DCAP 库，先支持 SGX，再扩展 TDX/SEV | 大（1周+） | `test_sgx_quote_valid_structure_accepted`、`test_tee_job_without_attestation_rejected` |
| 8 | CIP-5 定时器 bid_fp 和 STATE_WATCH 缺失 | 扩展 host API 签名，添加三层队列调度器 | 大（1-2周） | `test_height_timer_fires_at_exact_block`、`test_state_watch_triggers_on_storage_change` |
| 9 | Entitlement 权限检查未建立入口 | 补全 grant.rs 约束检查 + Actor 调用前置拦截 | 中（3-5天） | `test_entitlement_check_blocks_unauthorized`、`test_entitlement_grant_revoke_flow` |
| 10 | EIP-1559 Basefee 机制未实现 | 新增 FeeState + finalize_block 更新逻辑 | 中（3-5天） | `test_basefee_adjusts_with_congestion`、`test_basefee_floor_not_undershot` |
| 11 | Runner 候选过滤条件缺少 5 项 | 在 dispatcher 中补全完整过滤链 | 小（1天） | `test_runner_filter_chain_all_criteria`、`test_runner_filter_excludes_low_reputation` |

### 中（规格偏差）
| # | 问题 | 解决方案要点 | 估计工作量 | 关键验收测试 |
|---|------|--------------|------------|--------------|
| 12 | Gas 成本数值与规格不符 | 修正 gas.rs 常量 + token_create 改动态计算 | 小（0.5天） | `test_gas_constants_match_cip3_spec`、`test_token_create_cells_dynamic` |
| 13 | JobSpec 缺少 `required_runner_pool` 字段 | 两处结构体各加一个字段 + 过滤逻辑 | 小（0.5天） | `test_job_spec_required_runner_pool_filters`、`test_job_roundtrip_with_runner_pool` |
| 14 | CBOR 格式 JobSpec 只支持 LLM 类型 | 在 parse_job_spec 中补充 HTTP/MCP/Custom 分支 | 小（1天） | `test_parse_job_spec_cbor_http`、`test_parse_job_spec_cbor_mcp`、`test_parse_job_spec_cbor_custom` |
| 15 | 最低质押量不一致 | 提取为共享常量 `MIN_STAKE_CBY_WEI` | 小（0.5天） | `test_min_stake_constant_consistent`、`test_register_below_min_stake_rejected` |
| 16 | Runner 注册签名验证缺失 | 实现 ecrecover 注册验证 | 小（1天） | `test_runner_register_verifies_signature`、`test_runner_register_bad_sig_rejected` |

### 低（待完善）
| # | 问题 | 解决方案要点 | 估计工作量 | 关键验收测试 |
|---|------|--------------|------------|--------------|
| 17 | Anthropic API 和本地模型未实现 | 补全 Anthropic HTTP 调用；本地模型复用 OpenAI client | 小（1天） | `test_anthropic_llm_call_returns_result`、`test_local_model_inference_end_to_end` |
| 18 | HTTP XPath/JSONPath 提取未实现 | 引入 `sxd-xpath`、`jsonpath-rust` 并接入 extractor | 小（1-2天） | `test_http_jsonpath_extraction`、`test_http_xpath_extraction` |
| 19 | Runner P2P 共识通信未实现 | 短期：链作为协调层；中期：HTTP Pull Aggregator | 中（3-5天） | `test_result_aggregation_via_chain_fallback`、`test_multi_runner_majority_vote` |
| 20 | CIP-4 双 VM 存储命名空间隔离缺失 | 实现 `actor_storage_key` 含 `vm_ns` 字节的规格键格式 | 中（3-5天） | `test_pyvm_and_evm_storage_isolated`、`test_actor_storage_key_includes_vm_ns` |

---

> **说明：** 上表中"关键验收测试"列列出每个问题对应 `### 测试验收方案` 部分的核心测试函数名，可作为 PR 合并门控的最小测试集合。完整测试套件（含集成测试、端到端测试）详见各问题条目。
