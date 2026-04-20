---
type: entity
tags: [runner, lifecycle, cip-2, cip-13, cip-23]
sources:
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-23-tee-execution.md
  - refs/runner/2026-01-27_NODE_ACTOR_RUNNER_FLOW.md
  - refs/runner/2026-01-27_README_CN.md
  - refs/runner/2026-02-05_DOCUMENTATION.md
  - refs/runner/2026-03-03_Entitlement.md
  - refs/runner/2026-03-05_deterministic_runner_selection.md
last_updated: 2026-04-20
status: authoritative
---

# Runner 生命周期

Runner 是 Cowboy 链下计算市场的执行节点。本页综述 Runner 从注册到接单、执行、结算、可能 slash 的全流程。

---

## 阶段 1：Registration

```
runner register --stake <N CBY> --verification-modes [None|MajorityVote|...]
```

- **硬性 floor**: `stake >= 10,000 CBY`（代码检查，见 [[../parameters]]）
- **经济门槛**: 接单前应满足 `stake >= 50,000 CBY`（应用层惯例，见 [[Entitlement]]）
- **1.5× 规则**: 每个活跃 Job 占用 `max_job_value × 1.5` 的 stake，避免超卖
- Runner 在 `RateCard` 声明支持的执行类型（LLM / HTTP / MCP）、单位成本

**所在地**: System Actor `0x01`（RUNNER_REGISTRY），见 [[system-actors]]

### 阶段 1a（TEE Runner 专用，CIP-23 Draft）：attestation-first 注册

希望承接 `VerificationMode::Deterministic + tee_required` 的 Runner 必须在注册时附上 `initial_cae`（CPU + 可选 GPU）。Registry 跨 actor 调 `0x05::VerifyCae`（`user_data = keccak(runner_addr ‖ registration_block_hash)`），通过后写入 `MeasurementBinding { cpu_tee_type, allowed_cpu_measurements, allowed_gpu_measurements, service_pubkey, bound_at, expires_at, status }`。

- 失败 → 拒绝注册，stake 未动
- `status ∈ {Active, Deprecated, Revoked}`；`BINDING_RENEWAL_PERIOD ≈ 7d` 后须续约
- Dispatcher 从此**不再**依赖 `runner.capabilities.tee_support` 布尔（弃用）
- SGX = legacy，只能接 `EconomicBond`

详见 [[../concepts/tee-attestation]]。

### 阶段 1b（可选，CIP-13 Draft）：接受委托

Runner 可通过 `RunnerUpdateDelegationConfig` 打开 `DelegationConfig { accept_delegation, commission_bps, max_delegated_stake, min_delegation }`。打开后：

- **有效质押** = 自质押 + 委托 Active 总额；VRF 权重与最大 Job 价值均基于此
- **自质押下限** = `max(10,000 CBY, effective_stake × MIN_SELF_BOND_BPS / 10000)`（默认 10%）
- Commission 改动下一 epoch 生效；其他字段立即生效
- 详见 [[../concepts/runner-delegation]]

---

## 阶段 2：Job Discovery & Assignment

客户 `submit_job` → `0x02`（JOB_DISPATCHER）托管 bond → VRF 选择 Runner。

**算法**: Fisher-Yates shuffle + stake-weighted sortition，seed = VRF(prev_block_hash ‖ job_id)。

详见 [[../concepts/vrf-runner-selection]]。

被选中的 Runner 通过 RPC 轮询拉到任务；超时未提交结果则 timeout → 重新分发（无需 `skip_task`）。

---

## 阶段 3：Off-chain Execution

Runner 守护进程（workspace `runner/`）：
- 拉到 Job → 分发给对应执行器（`runner-llm` / `runner-http` / `runner-mcp`）
- 执行、收集结果、签名（secp256k1 65 字节）
- 按 Job 声明的 `ResultSchema` 构造 `RunnerResult`

**关键类型**:
- `RateCard` — 单位成本、支持的 MCP server
- `RunnerResult` — 结果 JSON + 可选签名 `[u8; 65]`
- `VerifierCheck` — 验证方式描述

---

## 阶段 4：Result Submission & Verification

Runner 提交结果到 `0x03`（RESULT_VERIFIER）：
- 按 Job 声明的 `VerificationMode` 分支验证（[[../concepts/runner-verification]]）
- 若 `MajorityVote` / `StructuredMatch`：等待 N-of-M 结果 commit-reveal 后聚合
- 若 `Deterministic`：TEE attestation + 字节级相同（**CIP-23 Draft**：强制调 `0x05::VerifyCae` 逐条验 CAE；任一失败整 Job 失败）

---

## 阶段 5：Dispute Window

- 结果写入后进入 `DISPUTE_WINDOW_BLOCKS = 75` 块窗口
- 任何人可提 dispute 附新证据，触发重新验证
- 窗口过后结算才最终化

---

## 阶段 6：Settlement

由 `0x03` 调度：
- `SettlementConfig` 由 `0x09`（GOVERNANCE）存 `{runner_percent, burn_percent, treasury_percent}`
- 分成：runner 得报酬、burn 销毁、treasury 入国库
- 默认值由 `UpdateSettlementConfig`（opcode 40）变更，仅 `0x09` 有权
- **若接受委托（CIP-13 Draft）**：`per_runner_share` 按 `delegator_pool = share × total_active / effective_stake` 拆分，扣 `commission_bps` 后按 Tranche `amount` 比例发给各 Delegator；发事件 `JobSettled` + `DelegatorPayout`（≥20 delegator 时批发）

详见 [[../concepts/settlement-slashing]] 与 [[../concepts/runner-delegation]]。

---

## 阶段 7（异常）：Slashing

触发条件：
- `Deterministic` 模式下字节不匹配
- `MajorityVote` 中的少数派
- TEE attestation 失败（CIP-23 Draft：`AttestFail` / `RegistryMismatch` / `NonceBindingFail` 等 9 类错误码之一）
- Dispute 被判定有效

规则：
- 50% 入 TREASURY（0x08），50% burn
- 若 stake 降至 `MIN_STAKE` 以下 → 设 `reputation = 0`（冻结接单）
- `slash_runner()` in `node/execution/src/runner/verifier.rs`
- **若接受委托（CIP-13 Draft）**：Slash 按 `self_stake + Σ slashable_tranches` 比例分摊；自质押不受封顶，Delegator 侧受 `MAX_DELEGATION_SLASH_PER_EPOCH_BPS`（默认 500 bps）per-epoch 限制；**Unbonding 中但 `now < claimable_at` 的 Tranche 仍可 slash**（防 slash-and-run）

---

## 相关
- [[system-actors]] — 涉及的系统 Actor（0x01/0x02/0x03/0x08/0x09）
- [[../concepts/vrf-runner-selection]]
- [[../concepts/runner-verification]]
- [[../concepts/settlement-slashing]]
- [[../concepts/runner-delegation]] — CIP-13 Stake 委托（Draft）
- [[../concepts/tee-attestation]] — CIP-23 CAE + attestation-first（Draft）
- [[../parameters]] — 所有具体常量

## Sources
- `refs/cips/cip-2-offchain-compute.mdx` — 框架规范（2026-03-09 修订版）
- `refs/cips/cip-13-runner-delegation.md` — Stake 委托规范（Draft, 2026-04-12）
- `refs/runner/2026-01-27_NODE_ACTOR_RUNNER_FLOW.md` — 流程图
- `refs/runner/2026-02-05_DOCUMENTATION.md` — 实现详述
- `refs/runner/2026-03-05_deterministic_runner_selection.md` — 选择算法
- `refs/runner/2026-03-03_Entitlement.md` — 权限体系
- workspace `node/execution/src/runner/registry.rs`、`dispatcher.rs`、`verifier.rs`
- workspace `runner/` — off-chain 守护进程
