# 测试完整性改进计划 — runner/

## Context

当前 runner 项目测试结构存在严重不均衡：
- `tests/` 目录下 60 个集成/回归测试主要覆盖**链上系统 Actor** (registry, dispatcher, verifier)
- 各 crate 内联单元测试仅 31 个，且集中在 crypto/ecvrf/bls_vrf 等密码学库
- **off-chain daemon 的核心逻辑几乎零覆盖**：runner-node、chain-client、runner-http、runner-llm 均无单元测试
- 现有 edge_cases.rs 中大量测试用 `let _ = result` 没有断言，形同虚设

目标：按优先级系统性补充单元测试、边界测试，并改善已有弱测试的断言质量。

---

## 当前覆盖摘要

| Crate | 测试函数 | 实际覆盖 |
|-------|---------|---------|
| runner-common/crypto.rs | 5 | 签名/哈希核心逻辑 ✅ |
| runner-registry/ecvrf.rs | 11 | VRF RFC 9381 ✅ |
| runner-consensus/threshold_bls_vrf.rs | 11 | BLS-VRF ✅ |
| runner-node/key_manager.rs | 1 | 仅 load-or-generate |
| runner-mcp/executor.rs | 1 | 仅构造 |
| **runner-node/node.rs** | **0** | **❌ 核心执行循环** |
| **chain-client/** | **0** | **❌ RPC 通信** |
| **runner-http/** | **0** | **❌ HTTP 执行 + 提取** |
| **runner-llm/** | **0** | **❌ LLM 执行** |
| **result-verifier/verifier.rs** | **0** | **❌ 所有验证模式** |
| **runner-common/types.rs** | **0** | **❌ 自定义反序列化** |
| **runner-common/executor.rs** | **0** | **❌ ExecutorRegistry** |

---

## 实施方案（按优先级）

### P1 — runner-common: 类型反序列化 & ExecutorRegistry

**文件**: `crates/runner-common/src/types.rs`, `crates/runner-common/src/executor.rs`

添加 `#[cfg(test)] mod tests` 内联块：

**types.rs**:
- `test_model_hash_from_hex_string` — 有效 hex `"0x" + 64 chars` 反序列化正确
- `test_model_hash_from_hex_invalid_length` — 非 32 字节 hex 返回错误
- `test_model_hash_from_array` — `[u8; 32]` 数组格式
- `test_u256_from_number` — JSON number 解析
- `test_u256_from_string` — 十六进制字符串 `"0x1A"`
- `test_verification_config_each_mode` — 对 6 种 VerificationMode 分别做 serde roundtrip（None, EconomicBond, MajorityVote, StructuredMatch, Deterministic, SemanticSimilarity）
- `test_signature_roundtrip` — 65 字节 hex 字符串 → Signature → 序列化回 hex
- `test_job_type_key_variants` — Llm/Http/Mcp/Custom 各自产生正确 key 字符串

**executor.rs**:
- `test_registry_register_and_get` — 注册后按 job_type 查询返回同一 executor
- `test_registry_unknown_type_returns_none` — 未注册类型返回 None
- `test_registry_overwrite` — 同 key 二次注册覆盖旧值

---

### P2 — runner-node: 核心逻辑

**文件**: `crates/runner-node/src/node.rs`

`needs_commit_reveal()` 是纯函数，无依赖，直接测：
- `test_commit_reveal_none_mode` → false
- `test_commit_reveal_economic_bond` → false（单 runner）
- `test_commit_reveal_majority_vote_single` → false（runners == 1）
- `test_commit_reveal_majority_vote_multi` → true（runners > 1）
- `test_commit_reveal_deterministic` → true
- `test_commit_reveal_semantic_similarity` → true

Commitment 哈希格式（CIP-2 C11），提取为可测函数：
- `test_commitment_hash_is_keccak256_of_result_address_salt` — 与手动 keccak256(result||address||salt) 比对
- `test_commitment_differs_by_salt` — 不同 salt → 不同 commitment
- `test_commitment_differs_by_result` — 不同 result → 不同 commitment

Job 去重逻辑（`submitted_job_ids` HashSet）：
- `test_deduplication_prevents_requeue` — 同一 job_id 第二次不入队

---

### P3 — runner-http: 数据提取

**文件**: `crates/runner-http/src/extractor.rs`

`DataExtractor` 各方法无外部依赖，纯内存解析：
- `test_extract_jsonpath_simple` — `{"key": "value"}` + selector `"key"` → `"value"`
- `test_extract_jsonpath_nested` — `{"a": {"b": "hello"}}` + `"a.b"` → `"hello"` （注：当前实现为简化版，按实际行为测）
- `test_extract_jsonpath_missing` — 不存在的 key → Err
- `test_extract_regex_capture_group` — 含捕获组的 pattern 返回第一个捕获
- `test_extract_regex_no_match` — 无匹配 → Err
- `test_extract_css_selector` — 简单 HTML 片段 + CSS selector → 文本内容
- `test_extract_css_no_match` → Err
- `test_extract_xpath_returns_unimplemented_error` — 当前占位实现

---

### P4 — runner-llm: 执行器逻辑

**文件**: `crates/runner-llm/src/executor.rs`

`select_execution_mode()` 和 `validate_*` 方法无 I/O：
- `test_select_mode_prefers_openai` — 两个 key 都有时选 OpenAI
- `test_select_mode_anthropic_fallback` — 仅有 Anthropic key 时选 Anthropic
- `test_select_mode_none_returns_error` — 无 key → Err
- `test_validate_bounds_zero_max_tokens` → Err
- `test_validate_bounds_valid` → Ok
- `test_validate_against_schema_valid_json` — 有效 JSON 通过
- `test_validate_against_schema_invalid_json` — 非 JSON 失败
- `test_estimate_cost_positive` — 返回值 > 0

---

### P5 — runner-http: Executor 边界 & Mock HTTP

**文件**: `crates/runner-http/src/executor.rs`

不需要网络的部分：
- `test_validate_bounds_zero_wall_time` → Err
- `test_validate_bounds_valid` → Ok
- `test_execute_wrong_job_type_llm` — 传入 LLM JobSpec → ExecutorError::InvalidJobType
- `test_estimate_cost_positive` — > 0

需要 Mock HTTP server 的部分（使用 `wiremock` 或 `httpmock`，需在 dev-dependencies 添加）：
- `test_execute_get_200` — mock server 返回 200 + body，验证 RunnerResult.data
- `test_execute_get_404` — mock server 返回 404 → Err
- `test_execute_post_with_body` — 验证 request body 被正确发送

---

### P6 — result-verifier: 验证模式

**文件**: `crates/result-verifier/src/verifier.rs`

所有验证模式均为纯函数（不依赖 I/O）：
- `test_verify_none_returns_first_result` — 单结果直接返回
- `test_verify_majority_vote_2_of_3_pass` — 2/3 匹配，threshold=0.5 → Ok
- `test_verify_majority_vote_threshold_not_met` — 1/3 匹配，threshold=0.5 → Err
- `test_verify_structured_match_fields_match` — 所有指定字段一致 → Ok
- `test_verify_structured_match_mismatch` → Err
- `test_verify_deterministic_identical` — 字节相同 → Ok
- `test_verify_deterministic_mismatch` — 字节不同 → Err
- `test_extract_field_dot_notation` — `"a.b.c"` 路径从嵌套 JSON 正确提取
- `test_extract_field_missing` → None/Err
- `test_cosine_similarity_identical_vectors` → 1.0
- `test_cosine_similarity_orthogonal` → 0.0

---

### P7 — chain-client: Mock HTTP RPC

**文件**: `crates/chain-client/src/client.rs`

需在 `chain-client/Cargo.toml` dev-dependencies 添加 `wiremock`（或复用 workspace 已有的 `mockall`）：
- `test_get_assigned_jobs_empty` — mock `/runner/{addr}/jobs` 返回 `[]`
- `test_get_assigned_jobs_returns_specs` — 返回一个 JobSpec
- `test_submit_result_success` — mock 接收 POST，验证请求 body 包含 job_id
- `test_heartbeat_success` — mock POST heartbeat endpoint
- `test_is_registered_true` — mock GET 返回 200
- `test_is_registered_false` — mock GET 返回 404 → false

---

### P8 — 改善现有弱测试断言

**文件**: `tests/regression/edge_cases.rs`, `tests/regression/error_handling.rs`

当前问题：`let _ = result` 无断言，形同虚设。逐一改造：
- `test_zero_stake_runner` — 添加 `assert!(result.is_ok())` 明确期望允许注册
- `test_very_large_job` — 验证 submit_job 是否成功，明确 u32::MAX bounds 的预期行为
- `test_register_runner_invalid_signature` — 当前行为：zero sig 被接受。添加断言说明这是已知 gap（TODO 注释），或根据实际实现判断是否应 reject
- `test_empty_result_data` — 验证 data 字段确实是 `{}`

---

## 关键文件路径

| 文件 | 改动类型 |
|------|---------|
| `crates/runner-common/src/types.rs` | 添加 `#[cfg(test)] mod tests` |
| `crates/runner-common/src/executor.rs` | 添加 `#[cfg(test)] mod tests` |
| `crates/runner-node/src/node.rs` | 添加 `#[cfg(test)] mod tests` |
| `crates/runner-http/src/extractor.rs` | 添加 `#[cfg(test)] mod tests` |
| `crates/runner-http/src/executor.rs` | 添加 `#[cfg(test)] mod tests` |
| `crates/runner-llm/src/executor.rs` | 添加 `#[cfg(test)] mod tests` |
| `crates/result-verifier/src/verifier.rs` | 添加 `#[cfg(test)] mod tests` |
| `crates/chain-client/src/client.rs` | 添加 `#[cfg(test)] mod tests` |
| `crates/chain-client/Cargo.toml` | 可能添加 `wiremock` dev-dep |
| `tests/regression/edge_cases.rs` | 修改已有测试添加断言 |
| `tests/regression/error_handling.rs` | 修改已有测试添加断言 |

---

## 验证方式

```bash
# 运行所有测试（含新增单元测试）
cd /home/ubuntu/workspace/runner
cargo test

# 运行指定 crate 测试
cargo test -p runner-common
cargo test -p runner-node
cargo test -p runner-http
cargo test -p runner-llm
cargo test -p result-verifier
cargo test -p chain-client

# 运行集成测试
cargo test --test integration_test -- --nocapture

# 查看覆盖率（可选，需 cargo-tarpaulin）
cargo tarpaulin --workspace --out Html
```

---

## 实施顺序建议

P1 → P2 → P3 → P4 → P6 → P8 → P5（需 mock HTTP）→ P7（需 mock HTTP）

P5/P7 需要确认是否引入 `wiremock` 依赖，可先做无网络的纯函数测试，network mock 部分后续补充。
