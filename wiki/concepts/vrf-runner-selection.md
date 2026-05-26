---
type: concept
tags: [vrf, selection, algorithm, cip-2, cip-13, cip-23]
sources:
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-23-tee-execution.md
  - refs/runner/2026-03-05_deterministic_runner_selection.md
  - refs/runner/2026-03-05_deterministic_runner_selection_en.md
last_updated: 2026-04-21
status: authoritative
---

# VRF + Stake-Weighted Runner 选择

Job Dispatcher（`0x02`）用确定性但不可预测的算法从注册 Runner 池中选 N 个候选。算法要抗 Sybil、抗关联攻击、结果可审计。

---

## 输入

- `job_id: Hash`
- `prev_block_hash: Hash`（作为 VRF seed）
- Runner Pool: `Vec<{ address, stake, verification_modes, reputation }>`
- 参数：
  - `N` — 需选出的 Runner 数（Job 声明）
  - Job 类型约束（VerificationMode 兼容性、RateCard 匹配）

---

## 算法：Fisher-Yates VRF + Stake-weighted Sortition

**步骤**:

1. **Pool 过滤**: 保留满足 Job 要求的 Runner（能力、stake ≥ 1.5× max_job_value、VerificationMode 支持、未冷冻）

2. **Stake 权重计算**（每个候选）:
   ```
   weight(r) = floor(log₂(effective_stake_r / MIN_STAKE + 1)) + 1
   ```
   对数化避免巨鲸垄断；所有合格 Runner 权重 ≥ 1。

   **CIP-13 v2 §2 显式 amend CIP-2 §5.4**：基数从 `registration.stake` 改为 `effective_stake = registration.stake + delegation_totals.total_active`。委托质押直接计入 VRF 权重。`log₂` 压缩仍生效，限制极端集中。

3. **VRF seed**: `seed = VRF(prev_block_hash ‖ job_id ‖ epoch)`

4. **Fisher-Yates 洗牌**:
   - 对 Pool 按权重扩展（每 Runner 重复 `weight(r)` 次）形成扩展列表
   - 用 seed 驱动 Fisher-Yates shuffle
   - 从洗牌后列表中依次抽前 N 个**不同** Runner

5. **Commit**: 选中结果写链、Runner 通过 RPC 拉任务。

---

## 为什么 Fisher-Yates 而非 Ring Buffer？

2026-03-05 修订替换了旧的 ring-buffer VRF：
- Ring buffer 下相邻 Job 的 Runner 高度相关（可被预测）
- Fisher-Yates + 独立 seed 每次 Job 均为独立洗牌，减少关联

详见 `refs/runner/2026-03-05_deterministic_runner_selection.md`。

---

## Timeout & Re-selection

- 被选中 Runner 若在期限内未提交结果 → timeout
- 调度器重新运行算法（`seed = VRF(... ‖ nonce)` nonce++）
- 移除原 Runner 从候选池（本 Job 内），降低其信誉
- **无 `skip_task` 机制**（2026-03-05 废除）

---

## CIP-23 v2 TEE 资格过滤（amend CIP-2 §5.4 step 4）

`tee_required = true` 的 job：dispatcher 候选池预过滤改用 `MeasurementBinding.status == Active && expires_at > submission_block`（不再用自报 `runner.capabilities.tee_support` 布尔）。**TEE 资格是分类能力检查（categorical），与 stake 无关** —— 即低自质押 + 高委托的 runner 仍可作 TEE runner（资格独立、权重靠委托）。详见 [[tee-attestation]] §3。

---

## 审计

所有 VRF 输入可链上复现：
- `prev_block_hash` ← 链上
- `job_id` ← 交易
- VRF 证明与选中结果一同存 receipt

任何验证者可独立复算并质疑。

---

## 相关
- [[../entities/runner-lifecycle]] — Phase 2 流程位置
- [[../entities/system-actors]] — 0x02 JOB_DISPATCHER
- [[runner-verification]] — 下游处理
- [[../parameters]] — MIN_STAKE 等
