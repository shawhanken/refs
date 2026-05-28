# Cowboy P0 Bug 清理套餐实施计划(2026-05-27)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 集中清理 2026-05-27 审计报告 §5.2 中的旧 P0 缺口,排除其他团队负责的 CIP-2/3/4,聚焦本团队 5 个修复项(CIP-1 / CIP-23 双修 / CIP-8 / CIP-20 三件套 / CIP-26 双件套)。

**Architecture:** 每项 = spec 引用 + 当前代码状态 + 失败测试草案 + 修复路径 + 验证命令。每项独立可合并,各自一个 PR。修改面集中在 `node/execution/src/{runner,token,execution}/`、`node/storage/src/speculative.rs`、`runner/crates/result-verifier/src/verifier.rs`。

**Tech Stack:** Rust(node + runner workspace),`cargo test -p <crate>` 验证,Python actor demos 走 `examples/*/start_all.sh --test` 做端到端 smoke。

**基线 commit:**
- node: `ce25ce9b`(devnet)
- runner: `29b31c2`(devnet)

---

## 总览(按优先级)

| # | 修复项 | CIP | 严重度 | 范围 | 关键文件 |
|---|---|---|---|---|---|
| 1 | result-verifier TEE 验签 TODO | CIP-23 §3.6 | **高**(Deterministic 模式实际未验) | runner 单 crate | `runner/crates/result-verifier/src/verifier.rs:291` |
| 2 | dispatcher 废弃布尔过滤 | CIP-23 §3.4 | **高**(安全反模式) | node 单 crate | `node/execution/src/runner/dispatcher.rs:1654` |
| 3 | timer carry-forward 永久丢失 | CIP-5 §6 / CIP-1 v3 | **高**(状态正确性) | node 单 crate | `node/storage/src/speculative.rs:743-751` |
| 4 | MPP Session Slash 接通 | CIP-8 §slash | 中 | node 单 crate | `node/execution/src/runner/session.rs:371-386` |
| 5 | CIP-20 on_transfer post-hook | CIP-20 §Transfers step 6 | 中 | node 单 crate | `node/execution/src/token/core.rs:155, 250` |
| 6 | CIP-20 emit_event | CIP-20 §Events | 中 | node 单 crate | `node/execution/src/token/core.rs / admin.rs` |
| 7 | CIP-20 hook cells 50k cap | CIP-20 §Hook Constraints | 中 | node 单 crate | `node/execution/src/gas.rs` + `actor_instruction.rs:308` |
| 8 | CIP-26 LibraryPublished event | CIP-26 §3.3 | 低 | node 单 crate | `node/execution/src/execution/library_instruction.rs` |
| 9 | CIP-26 冷调用 gas 分层 | CIP-26 §3.6 | 低 | node 单 crate | `node/execution/src/execution/actor_instruction.rs:791-800` |

**预估工作量:** 9 个修复项,每项 0.5-1.5 天,总计约 7-10 工作日,可拆 5 个 PR 提交。

---

## Task 1: CIP-23 Result Verifier TEE 验签接通

**Files:**
- Modify: `runner/crates/result-verifier/src/verifier.rs:287-296`
- Add(可选): `runner/crates/result-verifier/src/verifier.rs` 新增 `verify_tee_attestation()` 内部函数
- Test: `runner/crates/result-verifier/src/verifier.rs`(同文件 #[cfg(test)] mod)

### Spec(CIP-23 §3.6 / CIP-24 §3.3)

```
Deterministic 模式 + tee_required=true 时:
- 所有结果必须 byte-identical(已实装)
- 每个结果的 tee_attestation 必须通过 tee-verifier crate 验签
- 验签失败 → VerificationError::InvalidTeeAttestation
- 任一结果缺 attestation → VerificationError::MissingTeeAttestation(已实装)
```

**域前缀:** `cowboy/tee-verifier/ecdsa-attestation/v1`(已在 `runner/crates/tee-verifier/src/verifier.rs:13` 定义)

### 当前代码

`runner/crates/result-verifier/src/verifier.rs:287-296`:

```rust
// 2. Verify TEE attestation (if required)
if job_spec.verification.tee_required {
    for result in &results {
        if let Some(attestation) = &result.tee_attestation {
            // TODO: verify TEE attestation
        } else {
            return Err(VerificationError::MissingTeeAttestation);
        }
    }
}
```

`if let Some(attestation) = ... { /* TODO */ }` — 字面 TODO,attestation 完全未校验。

### TDD 草案

- [ ] **Step 1.1: 在 `verifier.rs` 末尾的 tests 模块加失败测试**

```rust
#[cfg(test)]
mod tests_tee_verify {
    use super::*;
    use runner_common::types::{JobSpec, RunnerResult, TeeAttestation, VerificationConfig};

    fn make_deterministic_spec_tee_required() -> JobSpec {
        let mut spec = JobSpec::default();
        spec.verification = VerificationConfig {
            mode: VerificationMode::Deterministic,
            tee_required: true,
            ..Default::default()
        };
        spec
    }

    fn make_result_with_attestation(data: serde_json::Value, attestation_bytes: Vec<u8>) -> RunnerResult {
        RunnerResult {
            data,
            tee_attestation: Some(TeeAttestation {
                tee_type: "sgx".to_string(),
                quote: attestation_bytes,
                ..Default::default()
            }),
            ..Default::default()
        }
    }

    #[tokio::test]
    async fn deterministic_with_invalid_attestation_must_reject() {
        let verifier = ResultVerifier::default();
        let spec = make_deterministic_spec_tee_required();
        // 两个 byte-identical 结果, 但 attestation 是垃圾字节
        let r1 = make_result_with_attestation(serde_json::json!({"x":1}), vec![0xFF; 64]);
        let r2 = make_result_with_attestation(serde_json::json!({"x":1}), vec![0xFF; 64]);

        let res = verifier.verify_deterministic(&spec, vec![r1, r2], 2).await;
        assert!(matches!(res, Err(VerificationError::InvalidTeeAttestation { .. })),
                "expected InvalidTeeAttestation, got {:?}", res);
    }

    #[tokio::test]
    async fn deterministic_with_valid_attestation_must_accept() {
        // 使用 tee-verifier crate 生成一份真实的 ECDSA-签名 attestation
        let (signer_priv, signer_pub) = test_helpers::gen_attester_keypair();
        let payload = serde_json::json!({"x": 1});
        let payload_bytes = serde_json::to_vec(&payload).unwrap();
        let quote = test_helpers::sign_attestation(&signer_priv, &payload_bytes);

        let verifier = ResultVerifier::with_trusted_attester(signer_pub);
        let spec = make_deterministic_spec_tee_required();
        let r1 = make_result_with_attestation(payload.clone(), quote.clone());
        let r2 = make_result_with_attestation(payload.clone(), quote);

        let res = verifier.verify_deterministic(&spec, vec![r1, r2], 2).await;
        assert!(res.is_ok(), "expected Ok with valid attestation, got {:?}", res);
    }
}
```

- [ ] **Step 1.2: 运行测试确认失败**

```bash
cd /home/ubuntu/workspace/runner && cargo test -p result-verifier deterministic_with_invalid_attestation_must_reject -- --nocapture
```
Expected: FAIL with `InvalidTeeAttestation` 不在 `VerificationError` 枚举中,或 verify_deterministic 返回 Ok 而非 Err。

- [ ] **Step 1.3: 在 `runner-common/src/types.rs` 的 `VerificationError` 增加 variant**

```rust
#[error("invalid TEE attestation: {reason}")]
InvalidTeeAttestation { reason: String },
```

- [ ] **Step 1.4: 在 `verifier.rs` 替换 TODO,接入 tee-verifier crate**

```rust
// 2. Verify TEE attestation (if required)
if job_spec.verification.tee_required {
    use tee_verifier::{TeeAttestationVerifier, AttestationError};
    let tee_verifier = self.tee_verifier.as_ref()
        .ok_or(VerificationError::InvalidTeeAttestation {
            reason: "no TEE verifier configured but tee_required=true".to_string(),
        })?;
    for result in &results {
        let attestation = result.tee_attestation.as_ref()
            .ok_or(VerificationError::MissingTeeAttestation)?;
        // 绑定 attestation 到 result.data 的 hash, 防止重放跨 result
        let payload_bytes = serde_json::to_vec(&result.data)
            .map_err(|e| VerificationError::InvalidTeeAttestation {
                reason: format!("payload encode: {}", e),
            })?;
        tee_verifier.verify(&attestation.tee_type, &attestation.quote, &payload_bytes)
            .map_err(|e: AttestationError| VerificationError::InvalidTeeAttestation {
                reason: e.to_string(),
            })?;
    }
}
```

- [ ] **Step 1.5: 在 `ResultVerifier` struct 加 `tee_verifier: Option<Arc<dyn TeeAttestationVerifier + Send + Sync>>`**

并提供 `with_trusted_attester()` 构造器,默认 `None` 时 tee_required=true 直接失败,保持向后兼容(`tee_required=false` 的路径不变)。

- [ ] **Step 1.6: 运行测试确认通过 + 全 crate 测试**

```bash
cd /home/ubuntu/workspace/runner && cargo test -p result-verifier
```
Expected: 两个新测试 PASS,其他测试不退步。

- [ ] **Step 1.7: 提交**

```bash
git commit -m "fix(cip-23): wire result-verifier TEE attestation check

Previously verify_deterministic accepted any tee_attestation as long as it
was Some(_). Now invokes tee-verifier crate with domain prefix
'cowboy/tee-verifier/ecdsa-attestation/v1' and rejects on signature failure.

Closes audit P0 (2026-05-27 §5.2)"
```

---

## Task 2: CIP-23 Dispatcher 废弃布尔过滤改 capability 字段

**Files:**
- Modify: `node/execution/src/runner/dispatcher.rs:1653-1656`
- Modify(关联): `node/runner/src/types.rs`(JobSpec.verification.required_tee_type 字段已有/补加)
- Test: `node/execution/src/runner/dispatcher.rs`(同文件 #[cfg(test)] 加 SPEC-CIP23-DISP-1/2)

### Spec(CIP-23 §3.4 + CIP-2 v2 Filter 4)

```
当 job 要求 TEE 时:
- 不再用 "runner.capabilities.tee_support.is_none()" 这种"有没有"二元判断
- 改为按 job_spec.verification.required_tee_type(如 "sgx" / "tdx")
  在 runner.capabilities.tee_support 数组里精确匹配
- 若 required_tee_type 为 None → 仅当 runner.capabilities.tee_support 非空时通过
```

### 当前代码

`node/execution/src/runner/dispatcher.rs:1653-1656`:

```rust
// Filter 4: TEE requirement — if job requires TEE, runner must support it
if job_spec.verification.tee_required && runner.capabilities.tee_support.is_none() {
    return false;
}
```

`tee_support.is_none()` 是布尔语义 — 一个支持 SGX 的 runner 会被一个要求 TDX 的 job 接受,反之亦然。

### TDD 草案

- [ ] **Step 2.1: 加失败测试**

`node/execution/src/runner/dispatcher.rs` 测试模块尾部:

```rust
#[tokio::test]
async fn spec_cip23_disp_1_sgx_runner_rejected_for_tdx_job() {
    let mut store = MockStore::new();
    let runner = test_runner_with_tee(vec!["sgx".to_string()]);
    register_runner(&mut store, &runner).await;

    let mut job = test_job_basic();
    job.verification.tee_required = true;
    job.verification.required_tee_type = Some("tdx".to_string());

    let dispatcher = JobDispatcher::default();
    let candidates = dispatcher
        .select_runner_committee(&mut store, &job, &[], 100, None)
        .await
        .unwrap();
    assert!(candidates.is_empty(),
            "expected SGX runner to be rejected for TDX job, got {:?}", candidates);
}

#[tokio::test]
async fn spec_cip23_disp_2_sgx_runner_accepted_for_sgx_job() {
    let mut store = MockStore::new();
    let runner = test_runner_with_tee(vec!["sgx".to_string()]);
    register_runner(&mut store, &runner).await;

    let mut job = test_job_basic();
    job.verification.tee_required = true;
    job.verification.required_tee_type = Some("sgx".to_string());

    let dispatcher = JobDispatcher::default();
    let candidates = dispatcher
        .select_runner_committee(&mut store, &job, &[], 100, None)
        .await
        .unwrap();
    assert!(!candidates.is_empty(),
            "expected SGX runner to be selected for SGX job, got empty");
}
```

- [ ] **Step 2.2: 运行确认失败**

```bash
cd /home/ubuntu/workspace/node && cargo test -p cowboy-execution spec_cip23_disp -- --nocapture
```
Expected: FAIL — `required_tee_type` 字段不存在或不被使用。

- [ ] **Step 2.3: 在 `node/runner/src/types.rs::VerificationConfig` 加字段**

```rust
#[serde(default, skip_serializing_if = "Option::is_none")]
pub required_tee_type: Option<String>,
```

- [ ] **Step 2.4: 替换 Filter 4**

```rust
// Filter 4: TEE requirement — capability-aware (CIP-23 §3.4)
if job_spec.verification.tee_required {
    let runner_tees = &runner.capabilities.tee_support; // Vec<String>
    if runner_tees.is_empty() {
        return false;
    }
    if let Some(required) = &job_spec.verification.required_tee_type
        && !runner_tees.iter().any(|t| t == required)
    {
        return false;
    }
}
```

注:如 `tee_support` 当前是 `Option<Vec<String>>`,需要先在 runner registry 端展平为 `Vec<String>`(默认空),或保留 Option 仅调整匹配逻辑;依实际类型选其一。

- [ ] **Step 2.5: 运行测试 + 全 crate 测试**

```bash
cargo test -p cowboy-execution spec_cip23_disp
cargo test -p cowboy-execution  # 确保未破其他 dispatcher 测试
```

- [ ] **Step 2.6: 提交**

```bash
git commit -m "fix(cip-23): dispatcher TEE filter uses required_tee_type, not is_none()

Was rejecting on 'tee_support.is_none()' which would accept an SGX runner
for a TDX job. Now matches required_tee_type against tee_support array
per CIP-23 §3.4."
```

---

## Task 3: CIP-1/CIP-5 Timer Carry-Forward 永久丢失修复

**Files:**
- Modify: `node/storage/src/speculative.rs:738-752`
- Test: `node/storage/src/speculative.rs`(同文件 #[cfg(test)] 加 SPEC-CIP5-CF-1/2)

### Spec(CIP-5 §6 + 审计 §4.3)

```
Timer carry-forward 规则:
- 当 block timer 预算不足以容纳 timer 时, timer 应保留至下一个 block
  并再次尝试(允许多个 block 后被处理)
- 但: 一个超大 timer (gas_limit_per_fire > TIMER_CYCLES_LIMIT_PER_BLOCK)
  永远塞不进任何 block, 必须有上限或 dead-letter 处理
- 当前代码的 bug: 这样的 timer 在 line 751 的 `continue` 后永久卡住,
  既不被执行也不被删除, 占据 timer 队列并每个 block 都跑一遍跳过逻辑
```

### 当前代码

`node/storage/src/speculative.rs:738-752`:

```rust
// M-F: Skip timers that exceed the remaining block timer budget.
let effective_cycles_limit = timer.gas_limit_per_fire.min(TIMER_CYCLES_LIMIT);
if effective_cycles_limit > timer_budget_remaining {
    warn!(
        timer_id = hex::encode(&timer.timer_id),
        required = effective_cycles_limit,
        remaining = timer_budget_remaining,
        "Timer skipped: exceeds block timer budget; preserved for next block"
    );
    timers_skipped_block_budget = timers_skipped_block_budget.saturating_add(1);
    continue; // Timer is NOT removed — preserved for next block
}
```

**问题诊断:**
- `effective_cycles_limit = timer.gas_limit_per_fire.min(TIMER_CYCLES_LIMIT)`
- 假设 `TIMER_CYCLES_LIMIT = 1_000_000`, 一个 timer 的 `gas_limit_per_fire = 5_000_000`
  → `effective_cycles_limit = 1_000_000`
- 若 `timer_budget_remaining = 500_000`(block 已用了一半), 该 timer skip
- 但下个 block `timer_budget_remaining` 重置, timer 又会跑同样的检查
- 关键 bug:如果 `effective_cycles_limit == TIMER_CYCLES_LIMIT` 且 `TIMER_CYCLES_LIMIT > TIMER_BLOCK_BUDGET_INITIAL` (理论极端),timer 永不可执行
- 即使非极端,若同一 block 排在前面的 timer 总是吃光预算,该 timer 也可能数百块都跑不上(线头阻塞)

### 修复策略(三选一,建议选 B)

- **A.** 仅在 `effective_cycles_limit > BLOCK_TIMER_BUDGET_INITIAL` 时丢弃 + 触发 dead-letter 事件
- **B.** 累计 skip 次数,达到 `TIMER_MAX_CARRY_FORWARD = 256` 后强制丢弃 + emit `timer.dead_letter` 事件
- **C.** 改头插法 + drop 后续低优先级 timer(复杂)

**推荐 B**(最小语义破坏 + 解决线头阻塞)。

### TDD 草案

- [ ] **Step 3.1: 加失败测试**

```rust
#[tokio::test]
async fn spec_cip5_cf_1_oversize_timer_dead_letters_after_max_carry() {
    let mut store = make_test_store().await;
    // 注册一个 gas_limit_per_fire 超过任何 block 都装不下的 timer
    let timer = Timer {
        timer_id: [1u8; 32].to_vec(),
        gas_limit_per_fire: TIMER_CYCLES_LIMIT, // 永远 == effective_limit
        max_cells_per_fire: TIMER_CELLS_LIMIT,
        ..test_timer_basic()
    };
    store_timer(&mut store, &timer).await;

    // 模拟 256+1 个 block 中 timer_budget_remaining 为 0
    for h in 1..=(TIMER_MAX_CARRY_FORWARD + 1) {
        process_block_with_zero_timer_budget(&mut store, h).await;
    }

    // timer 应已被 dead-letter 移除
    assert!(get_timer(&store, &timer.timer_id).await.is_none(),
            "expected oversize timer to be dead-lettered after {} skips",
            TIMER_MAX_CARRY_FORWARD);
    // 且最后一个 block 应有 timer.dead_letter 事件
    let events = get_actor_events_for_block(&store, TIMER_MAX_CARRY_FORWARD + 1).await;
    assert!(events.iter().any(|e| e.topic == "timer.dead_letter"),
            "expected timer.dead_letter event, got {:?}",
            events.iter().map(|e| &e.topic).collect::<Vec<_>>());
}

#[tokio::test]
async fn spec_cip5_cf_2_normal_carry_under_threshold_preserves_timer() {
    let mut store = make_test_store().await;
    let timer = test_timer_basic();
    store_timer(&mut store, &timer).await;

    // 跑 10 个零预算 block, timer 仍应在
    for h in 1..=10 {
        process_block_with_zero_timer_budget(&mut store, h).await;
    }
    assert!(get_timer(&store, &timer.timer_id).await.is_some());
}
```

- [ ] **Step 3.2: 运行测试确认失败**

```bash
cd /home/ubuntu/workspace/node && cargo test -p cowboy-storage spec_cip5_cf -- --nocapture
```
Expected: FAIL — `skip_count` 字段不存在,timer 不会被 dead-letter。

- [ ] **Step 3.3: 在 `cowboy_types::Timer` 加 `skip_count: u32`(serde default 0)**

`types/src/timer.rs`:

```rust
#[serde(default)]
pub skip_count: u32,
```

`types/src/constants.rs`:

```rust
/// CIP-5 carry-forward 上限。超过后 timer 进入 dead-letter 并发事件。
pub const TIMER_MAX_CARRY_FORWARD: u32 = 256;
```

- [ ] **Step 3.4: 替换 speculative.rs:738-752**

```rust
let effective_cycles_limit = timer.gas_limit_per_fire.min(TIMER_CYCLES_LIMIT);
if effective_cycles_limit > timer_budget_remaining {
    let skip_count = timer.skip_count.saturating_add(1);
    if skip_count >= TIMER_MAX_CARRY_FORWARD {
        // Dead-letter: 该 timer 累计跳过太多次, 几乎确认装不进任何 block,
        // 永久丢弃并发事件给链下索引器。
        let mut event_data = Vec::with_capacity(timer.timer_id.len() + 8);
        event_data.extend_from_slice(&timer.timer_id);
        event_data.extend_from_slice(&skip_count.to_le_bytes());
        let event = ActorEvent {
            block_height: current_height,
            tx_hash: Sha256Digest([0u8; 32]),
            topic: "timer.dead_letter".to_string(),
            data: event_data,
        };
        let _ = self.append_actor_events(timer.actor_address, vec![event]).await;
        self.remove_timer(&timer.timer_id).await?;
        warn!(
            timer_id = hex::encode(&timer.timer_id),
            skip_count,
            "Timer dead-lettered: exceeded TIMER_MAX_CARRY_FORWARD"
        );
        timers_dead_lettered = timers_dead_lettered.saturating_add(1);
        continue;
    }
    // 正常 carry-forward: 持久化新 skip_count
    let mut updated_timer = timer.clone();
    updated_timer.skip_count = skip_count;
    self.set_timer(&updated_timer).await?;
    warn!(
        timer_id = hex::encode(&timer.timer_id),
        required = effective_cycles_limit,
        remaining = timer_budget_remaining,
        skip_count,
        "Timer skipped: exceeds block timer budget; preserved for next block"
    );
    timers_skipped_block_budget = timers_skipped_block_budget.saturating_add(1);
    continue;
}
```

- [ ] **Step 3.5: 当 timer 成功执行时,重置 skip_count = 0**(避免长生 timer 累计)

在 line 793 附近的 `executor.execute_transactions(...)` 的 `Ok(_)` 分支中,timer 即将被删除/重新调度时不需要重置,因为成功 fire 后 timer 通常被 remove 或 reschedule。仅 reschedule 路径需要在新 timer 上设 `skip_count = 0`(查 reschedule_timer 代码,如已是 fresh Timer 则无需改)。

- [ ] **Step 3.6: 验证**

```bash
cd /home/ubuntu/workspace/node && cargo test -p cowboy-storage spec_cip5_cf
cargo test -p cowboy-storage  # 全 crate
cargo test -p cowboy-execution  # 跨 crate 不退步
```

- [ ] **Step 3.7: e2e smoke**

```bash
cd /home/ubuntu/workspace/node/examples/multi_call && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
```
Expected: 端到端 ok,timer 路径未被破坏。

- [ ] **Step 3.8: 提交**

```bash
git commit -m "fix(cip-5): dead-letter timers that exceed block budget for 256 blocks

Previously timers with gas_limit_per_fire too large to fit in a single
block were preserved indefinitely via 'continue', occupying queue space
and re-running the skip logic every block (head-of-line block).

Now tracks Timer.skip_count and emits a 'timer.dead_letter' event after
TIMER_MAX_CARRY_FORWARD=256 skips, freeing the slot."
```

---

## Task 4: CIP-8 MPP Session Slash 接通 verifier-arbitration

**Files:**
- Modify: `node/execution/src/runner/session.rs:371-386`
- Add(可能): `node/execution/src/runner/session.rs` 新增 `verify_session_dispute()` helper
- Test: `node/execution/src/runner/session.rs`(同文件 #[cfg(test)] 加 SPEC-CIP8-SLASH-1/2)

### Spec(CIP-8 §slash + CIP-2 verifier-arbitration)

```
Slash 流程(双签反例):
- evidence: SessionDispute{ msg_a: SignedFrame, msg_b: SignedFrame }
- 两帧 session_id 相同, sequence_number 相同, 但 payload_hash 不同
- 两帧均由同一 runner key 签名 (commit-reveal 阶段已暴露 pubkey)
- 验证通过 → 没收 runner stake 的 SLASH_PERCENT_OF_STAKE (默认 30%),
  转入 GOVERNANCE_SYSTEM_ACTOR (50% burn / 50% treasury 复用 CIP-2 路由)
- 关闭 session 为 SessionStatus::Slashed { evidence_hash }
```

### 当前代码

`node/execution/src/runner/session.rs:371-386`:

```rust
/// `Slash`: deferred to the verifier-arbitration milestone.
pub async fn handle_session_slash<S: StateStore>(
    &self,
    _store: &mut S,
    _tx: &Transaction,
    session_id: [u8; 32],
    _evidence: SessionDispute,
    block_height: u64,
) -> Result<(), ExecutionError> {
    warn!(
        block_height,
        session_id = %hex::encode(session_id),
        "session.slash invoked but commit-reveal arbitration path is not yet wired"
    );
    Err(ExecutionError::UnsupportedInstruction)
}
```

直接返回 `UnsupportedInstruction`,Slash opcode 形同虚设。

### TDD 草案

- [ ] **Step 4.1: 加失败测试**

```rust
#[tokio::test]
async fn spec_cip8_slash_1_valid_double_sign_triggers_slash() {
    let mut store = make_test_store().await;
    let (runner_addr, runner_priv) = make_runner_keypair();
    register_runner_with_stake(&mut store, runner_addr, 100_000).await;
    let session = open_session(&mut store, runner_addr).await;

    // 同 session, 同 sequence_number=42, 但 payload 不同的两帧
    let frame_a = sign_frame(&runner_priv, session.session_id, 42, b"payload_a");
    let frame_b = sign_frame(&runner_priv, session.session_id, 42, b"payload_b");
    let evidence = SessionDispute { msg_a: frame_a, msg_b: frame_b };

    let engine = ExecutionEngine::default();
    let mut tx = test_tx();
    let mut sender_account = Account::default();
    engine
        .handle_session_slash(&mut store, &tx, &mut sender_account,
                              session.session_id, evidence, 100)
        .await
        .expect("valid double-sign evidence should produce slash");

    // 验证 stake 被扣
    let runner_after = get_runner(&store, runner_addr).await.unwrap();
    assert_eq!(runner_after.stake, 70_000, "30% slash expected (default SLASH_PERCENT_OF_STAKE)");
    // 验证 session 被关
    let session_after = load_session(&store, &session.session_id).await.unwrap();
    assert!(matches!(session_after.status, SessionStatus::Slashed { .. }));
}

#[tokio::test]
async fn spec_cip8_slash_2_invalid_evidence_rejected_no_state_change() {
    let mut store = make_test_store().await;
    let (runner_addr, runner_priv) = make_runner_keypair();
    register_runner_with_stake(&mut store, runner_addr, 100_000).await;
    let session = open_session(&mut store, runner_addr).await;

    // sequence_number 不同 -> 非双签
    let frame_a = sign_frame(&runner_priv, session.session_id, 42, b"x");
    let frame_b = sign_frame(&runner_priv, session.session_id, 43, b"y");
    let evidence = SessionDispute { msg_a: frame_a, msg_b: frame_b };

    let engine = ExecutionEngine::default();
    let res = engine.handle_session_slash(
        &mut store, &test_tx(), &mut Account::default(),
        session.session_id, evidence, 100).await;
    assert!(matches!(res, Err(ExecutionError::InvalidData) | Err(ExecutionError::SlashEvidenceInvalid)));

    // stake 未变
    let runner_after = get_runner(&store, runner_addr).await.unwrap();
    assert_eq!(runner_after.stake, 100_000);
}
```

- [ ] **Step 4.2: 运行测试确认失败**

```bash
cd /home/ubuntu/workspace/node && cargo test -p cowboy-execution spec_cip8_slash -- --nocapture
```
Expected: FAIL — `UnsupportedInstruction` 返回。

- [ ] **Step 4.3: 在 `error.rs` 加 `ExecutionError::SlashEvidenceInvalid`**

- [ ] **Step 4.4: 实装 handle_session_slash**

```rust
pub async fn handle_session_slash<S: StateStore>(
    &self,
    store: &mut S,
    tx: &Transaction,
    sender_account: &mut Account,
    session_id: [u8; 32],
    evidence: SessionDispute,
    block_height: u64,
) -> Result<(), ExecutionError> {
    let session = load_session(store, &session_id).await?;
    // 1. 双签校验
    if evidence.msg_a.session_id != session_id || evidence.msg_b.session_id != session_id {
        return Err(ExecutionError::SlashEvidenceInvalid);
    }
    if evidence.msg_a.sequence_number != evidence.msg_b.sequence_number {
        return Err(ExecutionError::SlashEvidenceInvalid);
    }
    if evidence.msg_a.payload_hash == evidence.msg_b.payload_hash {
        return Err(ExecutionError::SlashEvidenceInvalid);
    }
    // 2. 两帧均由 session.runner 的 key 签名 (EIP-712 domain "Cowboy MPP Session" v1)
    let expected_signer = session.runner;
    verify_session_frame_signature(&evidence.msg_a, &expected_signer)
        .map_err(|_| ExecutionError::SlashEvidenceInvalid)?;
    verify_session_frame_signature(&evidence.msg_b, &expected_signer)
        .map_err(|_| ExecutionError::SlashEvidenceInvalid)?;
    // 3. 没收 stake
    let mut runner = get_runner(store, &session.runner).await?
        .ok_or(ExecutionError::InvalidData)?;
    let slash_amount = (runner.stake as u128)
        .saturating_mul(SLASH_PERCENT_OF_STAKE_NUM)
        .saturating_div(SLASH_PERCENT_OF_STAKE_DENOM) as u64;
    runner.stake = runner.stake.saturating_sub(slash_amount);
    if runner.stake < MIN_STAKE {
        runner.reputation = ReputationScore::zero();
    }
    set_runner(store, &session.runner, &runner).await?;
    // 4. 50/50 治理路由 (复用 slash_runner 工具或直接拆分)
    distribute_slashed_funds(store, slash_amount).await?;
    // 5. 关 session
    let evidence_hash = keccak256(&serde_json::to_vec(&evidence).unwrap_or_default());
    let mut updated_session = session.clone();
    updated_session.status = SessionStatus::Slashed { evidence_hash };
    store_session(store, &updated_session).await?;
    info!(
        block_height,
        session_id = %hex::encode(session_id),
        slashed = slash_amount,
        "session.slashed"
    );
    Ok(())
}
```

- [ ] **Step 4.5: 在 `types/src/session.rs` 加 `SessionStatus::Slashed { evidence_hash: [u8;32] }`**

- [ ] **Step 4.6: 验证**

```bash
cargo test -p cowboy-execution spec_cip8_slash
cargo test -p cowboy-execution  # 不退步
cd examples/multi_call && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
```

- [ ] **Step 4.7: 提交**

```bash
git commit -m "feat(cip-8): wire session slash with double-sign evidence verification

handle_session_slash now verifies SessionDispute evidence (matching
session_id + sequence_number, divergent payload_hash, both EIP-712-signed
by session runner), confiscates SLASH_PERCENT_OF_STAKE (30%), routes
50/50 burn/treasury, and closes session as Slashed{evidence_hash}."
```

---

## Task 5: CIP-20 on_transfer post-hook 调用

**Files:**
- Modify: `node/execution/src/token/core.rs:155, 250`(在 balance 更新成功后追加 on_transfer 调用)
- Modify: `node/execution/src/execution/actor_instruction.rs`(`call_transfer_hook` 增 `handler_name: &str` 参数,默认 "can_transfer",新增 "on_transfer")
- Test: `node/execution/src/token/core.rs`(同文件 #[cfg(test)] 加 SPEC-CIP20-HOOK-1)

### Spec(CIP-20 §Transfers step 6 + §Hook Constraints)

```
token_transfer flow:
  4. If transfer_hook set: call can_transfer(), revert if false   ← 已实装
  5. Debit caller, credit recipient                                 ← 已实装
  6. If transfer_hook set: call on_transfer()                       ← ❌ 未实装
  7. Emit TokenTransfer event                                       ← ❌ 见 Task 6

on_transfer MUST NOT revert (failures are logged but ignored)
on_transfer 与 can_transfer 共享 token_hook_max_cycles 上限
```

### 当前代码

`node/execution/src/token/core.rs:155`(transfer)和:250(transfer_from):pre-hook `can_transfer` 已接,balance 写完后直接 `Ok(())` 返回,缺 step 6。

### TDD 草案

- [ ] **Step 5.1: 加失败测试**

```rust
#[tokio::test]
async fn spec_cip20_hook_1_on_transfer_called_after_balance_update() {
    let mut store = make_test_store().await;
    // 部署一个 hook actor 它在 on_transfer 时 emit 一个 marker event
    let hook_addr = deploy_marker_hook(&mut store).await;
    let token_id = create_token_with_hook(&mut store, hook_addr).await;
    let (sender, receiver) = (test_addr(0x10), test_addr(0x20));
    mint_to(&mut store, &token_id, &sender, 1000).await;

    let mut engine = ExecutionEngine::default();
    let mut meters = DualGasMeters::with_unlimited();
    engine.handle_token_transfer(
        &mut store, &token_id, &sender, &receiver, 100,
        &mut meters, 1, &Digest::default(), 0, Digest::default(),
    ).await.unwrap();

    // 验证 on_transfer 跑过(hook 应留下 marker)
    let events = get_actor_events(&store, hook_addr).await;
    assert!(events.iter().any(|e| e.topic == "marker.on_transfer"),
            "expected on_transfer marker event from hook, got {:?}",
            events.iter().map(|e| &e.topic).collect::<Vec<_>>());
}

#[tokio::test]
async fn spec_cip20_hook_2_on_transfer_failure_does_not_revert_transfer() {
    let mut store = make_test_store().await;
    let hook_addr = deploy_reverting_hook(&mut store).await;  // on_transfer 故意 panic
    let token_id = create_token_with_hook(&mut store, hook_addr).await;
    let (sender, receiver) = (test_addr(0x10), test_addr(0x20));
    mint_to(&mut store, &token_id, &sender, 1000).await;

    let mut engine = ExecutionEngine::default();
    let mut meters = DualGasMeters::with_unlimited();
    let res = engine.handle_token_transfer(
        &mut store, &token_id, &sender, &receiver, 100,
        &mut meters, 1, &Digest::default(), 0, Digest::default(),
    ).await;
    assert!(res.is_ok(), "on_transfer failure must NOT revert transfer per CIP-20");
    assert_eq!(read_balance_sync(&store, &token_id, &receiver).await, 100);
}
```

- [ ] **Step 5.2: 运行测试确认失败**

```bash
cd /home/ubuntu/workspace/node && cargo test -p cowboy-execution spec_cip20_hook -- --nocapture
```

- [ ] **Step 5.3: 在 `actor_instruction.rs::call_transfer_hook` 增 handler_name 参数**

```rust
pub(crate) async fn call_transfer_hook<S>(
    &mut self,
    store: &mut S,
    hook_address: &Address,
    handler_name: &str,  // ← new
    token_id: &[u8; 32],
    ...
) -> Result<bool, ExecutionError>
{
    ...
    let result = self.pvm_executor.execute_handler(
        &mut pvm_ctx,
        &payload,
        handler_name,  // ← was hardcoded "can_transfer"
        ...
    );
    ...
}
```

- [ ] **Step 5.4: 在 `token/core.rs:155` 处 balance 更新后追加 post-hook**

```rust
write_balance(store, &to_balance_key, to_balance + amount).await?;

// CIP-20 §Transfers step 6: 调用 on_transfer (best-effort)
if let Some(hook) = &mint.transfer_hook {
    self.active_hook_tokens.insert(*token_id);
    let _ = self.call_transfer_hook(
        store, hook, "on_transfer",
        token_id, sender, to, amount,
        gas_meters, block_height, block_hash, timestamp_ms, tx_hash,
    ).await;  // intentionally ignore result per spec "failures are logged but ignored"
    self.active_hook_tokens.remove(token_id);
}

Ok(())
```

`transfer_from` 路径同样追加。注:on_transfer 也走 token_hook_max_cycles 上限。

- [ ] **Step 5.5: 验证 + 提交**

```bash
cargo test -p cowboy-execution spec_cip20_hook
cd examples/token && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
```

```bash
git commit -m "feat(cip-20): invoke on_transfer post-hook after balance updates

Step 6 of CIP-20 §Transfers was missing. Now token_transfer and
token_transfer_from both call hook.on_transfer() after writing balances.
Per spec, on_transfer failures are logged but do NOT revert the transfer.
The same TOKEN_HOOK_MAX_CYCLES cap applies."
```

---

## Task 6: CIP-20 emit_event 全套

**Files:**
- Modify: `node/execution/src/token/core.rs`(transfer/transfer_from/mint/burn/approve)
- Modify: `node/execution/src/token/admin.rs`(set_hook/transfer_ownership/freeze/thaw)
- Test: `node/execution/src/token/core.rs / admin.rs`(SPEC-CIP20-EVT-*)

### Spec(CIP-20 §Events 438-449)

```
TokenTransfer(token_id, from, to, amount)
TokenMinted(token_id, to, amount)
TokenBurned(token_id, from, amount)
TokenApproval(token_id, owner, spender, amount)
TokenHookUpdated(token_id, old_hook, new_hook)
TokenOwnershipTransferred(token_id, old_owner, new_owner)
TokenFrozen(token_id, account)
TokenThawed(token_id, account)
```

事件格式约定(与 timer.cancelled_insufficient_funds 一致):`ActorEvent { topic, data: bincode-encoded fields }`。`emitter` 用 token_registry actor 地址。

### 当前代码

`grep emit_event execution/src/token/` 返回空 — 整个 token 模块零事件。

### TDD 草案

- [ ] **Step 6.1: 加失败测试(一个综合用例)**

```rust
#[tokio::test]
async fn spec_cip20_evt_1_transfer_emits_token_transfer_event() {
    let mut store = make_test_store().await;
    let token_id = create_token_no_hook(&mut store).await;
    let (sender, receiver) = (test_addr(0x10), test_addr(0x20));
    mint_to(&mut store, &token_id, &sender, 1000).await;

    let mut engine = ExecutionEngine::default();
    let mut meters = DualGasMeters::with_unlimited();
    engine.handle_token_transfer(
        &mut store, &token_id, &sender, &receiver, 100,
        &mut meters, 1, &Digest::default(), 0, Digest::default(),
    ).await.unwrap();

    let token_actor = token_registry_address();
    let events = get_actor_events(&store, token_actor).await;
    let tt = events.iter().find(|e| e.topic == "TokenTransfer")
        .expect("expected TokenTransfer event");
    let decoded = decode_token_transfer_event(&tt.data);
    assert_eq!(decoded.token_id, token_id);
    assert_eq!(decoded.from, sender);
    assert_eq!(decoded.to, receiver);
    assert_eq!(decoded.amount, 100);
}

#[tokio::test]
async fn spec_cip20_evt_2_mint_emits_token_minted() { ... }

#[tokio::test]
async fn spec_cip20_evt_3_set_hook_emits_token_hook_updated() { ... }
```

- [ ] **Step 6.2: 运行确认失败**

```bash
cargo test -p cowboy-execution spec_cip20_evt -- --nocapture
```

- [ ] **Step 6.3: 定义事件编码 helpers**

`node/execution/src/token/events.rs` (新建):

```rust
//! CIP-20 §Events: 标准事件编码。

use cowboy_types::Address;

pub const TOPIC_TOKEN_TRANSFER: &str = "TokenTransfer";
pub const TOPIC_TOKEN_MINTED: &str = "TokenMinted";
pub const TOPIC_TOKEN_BURNED: &str = "TokenBurned";
pub const TOPIC_TOKEN_APPROVAL: &str = "TokenApproval";
pub const TOPIC_TOKEN_HOOK_UPDATED: &str = "TokenHookUpdated";
pub const TOPIC_TOKEN_OWNERSHIP_TRANSFERRED: &str = "TokenOwnershipTransferred";
pub const TOPIC_TOKEN_FROZEN: &str = "TokenFrozen";
pub const TOPIC_TOKEN_THAWED: &str = "TokenThawed";

pub fn encode_transfer_event(
    token_id: &[u8; 32],
    from: &Address,
    to: &Address,
    amount: u128,
) -> Vec<u8> {
    // 32(token) + 20(from) + 20(to) + 16(amount LE) = 88 bytes
    let mut buf = Vec::with_capacity(88);
    buf.extend_from_slice(token_id);
    buf.extend_from_slice(from.as_ref());
    buf.extend_from_slice(to.as_ref());
    buf.extend_from_slice(&amount.to_le_bytes());
    buf
}

pub fn encode_mint_burn_event(
    token_id: &[u8; 32],
    party: &Address,
    amount: u128,
) -> Vec<u8> {
    let mut buf = Vec::with_capacity(68);
    buf.extend_from_slice(token_id);
    buf.extend_from_slice(party.as_ref());
    buf.extend_from_slice(&amount.to_le_bytes());
    buf
}

// ... 其他编码 helpers
```

- [ ] **Step 6.4: 在每个 token 操作中调用 `append_actor_events`**

`token/core.rs::handle_token_transfer` 在 `Ok(())` 前:

```rust
let event = ActorEvent {
    block_height,
    tx_hash,
    topic: TOPIC_TOKEN_TRANSFER.to_string(),
    data: encode_transfer_event(token_id, sender, to, amount),
};
let _ = store
    .append_actor_events(token_registry_address(), vec![event])
    .await;
```

mint/burn/approve/set_hook/transfer_ownership/freeze/thaw 类似。

- [ ] **Step 6.5: 验证 + 提交**

```bash
cargo test -p cowboy-execution spec_cip20_evt
cargo test -p cowboy-execution  # 全 crate
cd examples/token && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
```

```bash
git commit -m "feat(cip-20): emit standardized events from all token operations

Adds TokenTransfer/Minted/Burned/Approval/HookUpdated/OwnershipTransferred/
Frozen/Thawed events at the token_registry actor address. Event payloads
are length-prefixed binary (token_id || addr || u128 LE amount), matching
the timer.cancelled_insufficient_funds encoding convention."
```

---

## Task 7: CIP-20 Hook Cells 上限(50_000 cap)

**Files:**
- Modify: `node/execution/src/gas.rs`(加 `token_hook_max_cells`)
- Modify: `node/execution/src/pvm_executor.rs`(`execute_handler` 增 `max_cells` 入参 + sub-limit push/restore)
- Modify: `node/execution/src/execution/actor_instruction.rs:308-316`(call_transfer_hook 传入 max_cells)
- Test: `node/execution/src/token/core.rs`(SPEC-CIP20-CELLS-1)

### Spec(CIP-20 §Hook Constraints line 176)

```
Hook calls capped at 50,000 Cycles and 50,000 Cells; exceeded = transfer fails
```

当前代码只有 `token_hook_max_cycles: 50_000`,**cells 上限未声明也未强制**。

### TDD 草案

- [ ] **Step 7.1: 加失败测试**

```rust
#[tokio::test]
async fn spec_cip20_cells_1_hook_exceeding_50k_cells_reverts_transfer() {
    let mut store = make_test_store().await;
    // 部署一个 hook 它在 can_transfer 中 state_set 大量 bytes 触发 cells 超限
    let hook_addr = deploy_cells_heavy_hook(&mut store).await;  // 故意写 60_000 字节
    let token_id = create_token_with_hook(&mut store, hook_addr).await;
    let (sender, receiver) = (test_addr(0x10), test_addr(0x20));
    mint_to(&mut store, &token_id, &sender, 1000).await;

    let mut engine = ExecutionEngine::default();
    let mut meters = DualGasMeters::with_unlimited();
    let res = engine.handle_token_transfer(
        &mut store, &token_id, &sender, &receiver, 100,
        &mut meters, 1, &Digest::default(), 0, Digest::default(),
    ).await;
    assert!(matches!(res, Err(ExecutionError::TokenHookCellsExceeded { .. })),
            "expected TokenHookCellsExceeded, got {:?}", res);
    // balance 未变(transfer 失败)
    assert_eq!(read_balance_sync(&store, &token_id, &sender).await, 1000);
}
```

- [ ] **Step 7.2: 在 `gas.rs` 加常量**

```rust
pub const TOKEN_HOOK_MAX_CELLS: u64 = 50_000;
// ... GasCosts 结构:
pub token_hook_max_cells: u64,
// ... default:
token_hook_max_cells: TOKEN_HOOK_MAX_CELLS,
```

- [ ] **Step 7.3: 在 `pvm_executor::execute_handler` 增 `max_cells: Option<u64>` 入参**

仿照已有的 `max_cycles` push/restore pattern:

```rust
let prev_cells_limit = max_cells.map(|cap| ctx.gas_meters.cells.push_sub_limit(cap));
// ... PVM execute ...
if let Some(prev) = prev_cells_limit {
    ctx.gas_meters.cells.restore_limit(prev);
}
```

- [ ] **Step 7.4: 在 `actor_instruction.rs:308-316` 传入 max_cells**

```rust
let result = self.pvm_executor.execute_handler(
    &mut pvm_ctx,
    &payload,
    handler_name,
    Some(self.gas_costs.token_hook_max_cycles),
    Some(self.gas_costs.token_hook_max_cells),  // ← new
    Vec::new(),
    [0u8; 20],
);
```

- [ ] **Step 7.5: 加 `ExecutionError::TokenHookCellsExceeded { used, cap }` 与 `TokenHookGasExceeded` 对称**

- [ ] **Step 7.6: 验证 + 提交**

---

## Task 8: CIP-26 LibraryPublished 事件

**Files:**
- Modify: `node/execution/src/execution/library_instruction.rs::execute_publish_library`
- Test: `node/execution/src/execution/library_instruction.rs` 同文件 #[cfg(test)] 加 SPEC-CIP26-EVT-1

### Spec(CIP-26 §3.3 line 104)

```
A LibraryPublished event is emitted: { publisher, name, code_hash, code_size }
```

### 当前代码

`library_instruction.rs` 整个文件无 `append_actor_events` / `emit_event` 调用。

### TDD 草案

- [ ] **Step 8.1: 加失败测试**

```rust
#[tokio::test]
async fn spec_cip26_evt_1_publish_library_emits_event() {
    let mut store = make_test_store().await;
    let publisher = test_addr(0x10);
    let name = b"engine".to_vec();
    let code = b"def hello(): pass\n".to_vec();
    let code_hash = keccak256(&code);
    let mut meters = DualGasMeters::with_unlimited();

    execute_publish_library(&mut store, &publisher, name.clone(), code.clone(), 100, &mut meters)
        .await
        .unwrap();

    // 事件应在 publisher 地址下(spec 未硬性规定 emitter,选 publisher 与 LibraryPublished 主体一致)
    let events = get_actor_events(&store, publisher).await;
    let lib_event = events.iter().find(|e| e.topic == "LibraryPublished")
        .expect("expected LibraryPublished event");
    let decoded = decode_library_published(&lib_event.data);
    assert_eq!(decoded.publisher, publisher);
    assert_eq!(decoded.name, name);
    assert_eq!(decoded.code_hash, code_hash);
    assert_eq!(decoded.code_size, code.len() as u64);
}
```

- [ ] **Step 8.2: 实装**

`library_instruction.rs` 在 publish 成功后 append 事件:

```rust
let event_data = {
    let mut buf = Vec::with_capacity(20 + 1 + name.len() + 32 + 8);
    buf.extend_from_slice(sender.as_ref());
    buf.push(name.len() as u8);          // name length prefix
    buf.extend_from_slice(&name);
    buf.extend_from_slice(code_hash.as_ref());
    buf.extend_from_slice(&(code.len() as u64).to_le_bytes());
    buf
};
let event = ActorEvent {
    block_height,
    tx_hash: Digest::default(),
    topic: "LibraryPublished".to_string(),
    data: event_data,
};
store.append_actor_events(*sender, vec![event]).await
    .map_err(|e| ExecutionError::StoreError(Box::new(e)))?;
```

- [ ] **Step 8.3: 验证 + 提交**

---

## Task 9: CIP-26 冷调用 gas 分层

**Files:**
- Modify: `node/execution/src/execution/actor_instruction.rs:791-800`
- Modify(可能): `node/execution/src/pvm_executor.rs`(暴露 cache hit/miss 信息)
- Test: `node/execution/src/execution/actor_instruction.rs` 同文件 #[cfg(test)] 加 SPEC-CIP26-COLD-1

### Spec(CIP-26 §3.6 line 144)

```
| Per-handler-call lib load | len(code) * 5 cycles cached / cold tier |
```

代码现状:`LIB_HANDLER_LOAD_PER_BYTE_CYCLES = 1`(cached row)与 `LIB_HANDLER_LOAD_COLD_PER_BYTE_CYCLES = 53`(cold row)两个常量并存,但 actor_instruction.rs:798 始终按 cached(=1)收费。冷首调用应按 53 收费,触发后续 cached。

### 当前代码

```rust
let pin_total_bytes: u64 = pinned_libs.iter().map(|p| p.code.len() as u64).sum();
if pin_total_bytes > 0 {
    gas_meters.cycles.consume(
        pin_total_bytes.saturating_mul(crate::gas::LIB_HANDLER_LOAD_PER_BYTE_CYCLES),
    )?;
}
```

`LIB_HANDLER_LOAD_COLD_PER_BYTE_CYCLES` **从未被引用**(grep 仅在 gas.rs 中定义)。

### TDD 草案

- [ ] **Step 9.1: 加失败测试**

```rust
#[tokio::test]
async fn spec_cip26_cold_1_first_call_charges_cold_subsequent_charges_cached() {
    let mut store = make_test_store().await;
    let publisher = test_addr(0x10);
    let lib_code = vec![0u8; 1000];  // 1000-byte library
    publish_library(&mut store, &publisher, b"engine", lib_code.clone()).await;
    let actor = deploy_actor_importing("engine", &mut store, &publisher).await;

    // 第一次调用 - 应按 cold (53 cycles/byte) 收
    let mut meters_1 = DualGasMeters::with_unlimited();
    call_actor_handler(&mut store, &actor, "noop", &mut meters_1).await.unwrap();
    let cycles_1 = meters_1.cycles.consumed();
    assert!(cycles_1 >= 1000 * 53,
            "first call should charge cold rate: got {} cycles, need >= {}",
            cycles_1, 1000 * 53);

    // 第二次调用同 actor handler - 应按 cached (1 cycle/byte) 收
    let mut meters_2 = DualGasMeters::with_unlimited();
    call_actor_handler(&mut store, &actor, "noop", &mut meters_2).await.unwrap();
    let cycles_2 = meters_2.cycles.consumed();
    let lib_overhead_2 = cycles_2 - baseline_actor_overhead();
    assert!(lib_overhead_2 < 1000 * 53 / 10,
            "second call should be cached, overhead {} expected << {}",
            lib_overhead_2, 1000 * 53);
}
```

- [ ] **Step 9.2: 检查 PvmExecutor::bytecode_cache 是否暴露命中信息**

如 `BytecodeCache::contains_key(code_hash) -> bool` 不存在则加上。

- [ ] **Step 9.3: 替换 actor_instruction.rs:791-800**

```rust
let mut cold_bytes: u64 = 0;
let mut cached_bytes: u64 = 0;
for pin in &pinned_libs {
    let code_hash = keccak256(&pin.code);
    if self.pvm_executor.bytecode_cache_contains(&code_hash) {
        cached_bytes = cached_bytes.saturating_add(pin.code.len() as u64);
    } else {
        cold_bytes = cold_bytes.saturating_add(pin.code.len() as u64);
    }
}
if cold_bytes > 0 {
    gas_meters.cycles.consume(
        cold_bytes.saturating_mul(crate::gas::LIB_HANDLER_LOAD_COLD_PER_BYTE_CYCLES),
    )?;
}
if cached_bytes > 0 {
    gas_meters.cycles.consume(
        cached_bytes.saturating_mul(crate::gas::LIB_HANDLER_LOAD_PER_BYTE_CYCLES),
    )?;
}
```

- [ ] **Step 9.4: 验证 + 提交**

```bash
cargo test -p cowboy-execution spec_cip26_cold
```

```bash
git commit -m "fix(cip-26): apply cold-call gas tier on first library load

LIB_HANDLER_LOAD_COLD_PER_BYTE_CYCLES (53) was defined but never used:
all library loads were charged at the cached rate (1 cycle/byte).
Now consults bytecode_cache and charges 53 cycles/byte on cache miss,
1 cycle/byte on hit."
```

---

## 提交策略

每个 Task 单独 PR(若多 Task 同文件冲突可合并 PR),按下表节奏:

| PR 顺序 | 含 Task | 范围 | 建议合并节点 |
|---|---|---|---|
| 1 | Task 1 (CIP-23 verifier) | runner | 独立 |
| 2 | Task 2 (CIP-23 dispatcher) | node | 独立 |
| 3 | Task 3 (CIP-1/5 carry-forward) | node | 独立 |
| 4 | Task 4 (CIP-8 slash) | node | 独立 |
| 5 | Task 5+6+7 (CIP-20 三件套) | node | 合并:三个 token 修复改同文件 |
| 6 | Task 8+9 (CIP-26 双件套) | node | 合并:同 library_instruction / actor_instruction 区 |

---

## 验证总览

```bash
# 单 Task 验证(每个 Task 文末已列出)

# 全套清理后回归
cd /home/ubuntu/workspace/runner && cargo test
cd /home/ubuntu/workspace/node && cargo test --workspace
cd /home/ubuntu/workspace/node/examples/token && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
cd /home/ubuntu/workspace/node/examples/multi_call && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
cd /home/ubuntu/workspace/node/examples/llm_chat && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
```

Expected: 全 crate 测试通过(已知例外: `cowboy-chain::tests::test_backfill` 是 public 分支既有 stack overflow,非本计划引入);3 个 e2e demo 跑通。

---

## 已知约束 / 不在范围

- **CIP-2/3/4**:其他团队负责(见 `[[project-team-scope]]` 记忆),本计划不触碰
- **CIP-9 GET_MANIFEST RPC**:审计 P0 中型工作量,放下一轮
- **CIP-17 接口对齐**(`/proof/*` → `/state/*` + 补 `block_hash`/`absent`):审计 P0,单独计划
- **CIP-23 v2 CAE 流水线**:P1,需等本套 Task 1/2 合并后再推
- **CIP-29 Phase 2 异步 fire 与 orderbook 持久化**:P0 中尚未变,单独评估

---

**计划完**
