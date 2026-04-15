---
type: entity
tags: [runner, lifecycle, cip-2]
sources:
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/runner/2026-01-27_NODE_ACTOR_RUNNER_FLOW.md
  - refs/runner/2026-01-27_README_CN.md
  - refs/runner/2026-02-05_DOCUMENTATION.md
  - refs/runner/2026-03-03_Entitlement.md
  - refs/runner/2026-03-05_deterministic_runner_selection.md
last_updated: 2026-04-15
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
- 若 `Deterministic`：TEE attestation + 字节级相同

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

详见 [[../concepts/settlement-slashing]]。

---

## 阶段 7（异常）：Slashing

触发条件：
- `Deterministic` 模式下字节不匹配
- `MajorityVote` 中的少数派
- TEE attestation 失败
- Dispute 被判定有效

规则：
- 50% 入 TREASURY（0x08），50% burn
- 若 stake 降至 `MIN_STAKE` 以下 → 设 `reputation = 0`（冻结接单）
- `slash_runner()` in `node/execution/src/runner/verifier.rs`

---

## 相关
- [[system-actors]] — 涉及的系统 Actor（0x01/0x02/0x03/0x08/0x09）
- [[../concepts/vrf-runner-selection]]
- [[../concepts/runner-verification]]
- [[../concepts/settlement-slashing]]
- [[../parameters]] — 所有具体常量

## Sources
- `refs/cips/cip-2-offchain-compute.mdx` — 框架规范（2026-03-09 修订版）
- `refs/runner/2026-01-27_NODE_ACTOR_RUNNER_FLOW.md` — 流程图
- `refs/runner/2026-02-05_DOCUMENTATION.md` — 实现详述
- `refs/runner/2026-03-05_deterministic_runner_selection.md` — 选择算法
- `refs/runner/2026-03-03_Entitlement.md` — 权限体系
- workspace `node/execution/src/runner/registry.rs`、`dispatcher.rs`、`verifier.rs`
- workspace `runner/` — off-chain 守护进程
