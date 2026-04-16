---
type: concept
tags: [runner, delegation, staking, cip-13, draft]
sources:
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-2-offchain-compute.mdx
  - node/runner/src/system_actors.rs
  - node/execution/src/runner/dispatcher.rs
  - node/execution/src/runner/verifier.rs
last_updated: 2026-04-16
status: draft
---

# Runner Stake 委托（CIP-13）

CBY 持有人可将代币**锁定委托**给某 Runner，提升其有效质押（VRF 权重与最大 Job 价值），换取 Runner 配置的 89% 结算分成的一部分。协议只实现**最小 hook**（注册、分账、slash 级联、解绑）；流动性质押池、收益代币、舰队管理金库等由三方 Actor 在此之上构建。

**状态**：CIP-13 为 Draft（2026-04-12 创建），`Requires: CIP-12`；本页随之为 draft；协议尚未实现。opcode 40–44 与现有 SystemInstruction 40–43 **冲突**（CIP-13 中有 TODO）。

---

## 动机

白皮书 §1.9 / §5 要求 Runner 自持 `max(10,000 CBY, 1.5 × max_job_value)`。这把**资本供应**与**算力运营**绑定在同一账户：最好的 GPU 运营方未必有大额 CBY；非 Runner 的 CBY 持有人无法获得算力市场收益。CIP-13 解耦二者。

| 链 | 协议层 | 生态层 |
|---|---|---|
| Ethereum | Validator 委托 / beacon rewards | Lido、Rocket Pool、Pendle、EigenLayer |
| Solana | Validator 委托 / stake accounts | Jito、Marinade、Sanctum |
| Cowboy（CIP-13）| Runner 委托 / 分账 | 液态质押池、stCBY、收益产品 |

---

## 核心数据结构

### DelegationConfig（挂在 `RunnerRegistration`）

```
DelegationConfig {
    accept_delegation:            bool
    commission_bps:               u16        // 当前分成
    pending_commission_bps:       Option<u16>
    pending_effective_epoch:      u64
    max_delegated_stake:          u64        // 0 = 不限
    min_delegation:               u64
    last_updated:                 u64        // DELEGATION_COOLDOWN_BLOCKS 节流基点
}
```

**Commission 变更延迟一个 epoch 生效**：更新时写 `pending_commission_bps`、`pending_effective_epoch = current_epoch + 1`。当前 epoch 内的结算仍用旧值。下一个 epoch 的**首次结算**懒惰提升：`pending → commission_bps`、清 `pending`（函数 `effective_commission_for_epoch` 幂等）。

其他字段（`max_delegated_stake` / `min_delegation` / `accept_delegation`）**立即生效**（只 gate 未来交易）。

### DelegationTranche（分片记账单元）

```
DelegationTranche {
    delegator, runner, tranche_id,
    amount,
    created_at,
    status: Active | Unbonding,
    claimable_at: Option<u64>   // Unbonding 时填；到达此块停止可 slash 且可 claim
}
```

**派生谓词**（无持久化 `Claimable` 状态）：

```
is_slashable(T, now) := T.status == Active
                       OR (T.status == Unbonding AND now < T.claimable_at)
is_claimable(T, now) := T.status == Unbonding AND now >= T.claimable_at
```

每次 top-up 总是**新建**一个 Tranche（已有的不改），这样金额、时间戳、状态始终各归各。

### 缓存聚合

- `DelegationDelegatorSummary {active_tranche_count, active_amount}` — 支撑 O(1) 前置检查（`MAX_ACTIVE_TRANCHES_PER_DELEGATOR`、是否为新 delegator）
- `DelegationTotals {total_active, delegator_count}` — Runner 级，用于 VRF 权重与最大 Job 价值；Unbonding 金额不缓存，按需扫描
- **不缓存** `total_slashable`（依赖 `current_block`，维护成本高于计算成本；slashing 本就要遍历 Tranche）

存储键均在 `0x01 RUNNER_REGISTRY` 下，无新子系统。

---

## 有效质押与衍生量

```
effective_stake = registration.stake + delegation_totals.total_active
```

- **VRF 权重**：`floor(log2(effective_stake / MIN_STAKE + 1)) + 1` —— **log2 压缩**降低极端集中收益。
- **最大 Job 价值**：`effective_stake × 2 / 3`（即 `/1.5`，对齐 `STAKE_JOB_MULTIPLIER`）。
- **最小自质押**：`self_stake >= max(MIN_STAKE_CBY_WEI, effective_stake × MIN_SELF_BOND_BPS / 10000)`；默认 `MIN_SELF_BOND_BPS = 1000`（10%），保证 Runner 始终有切身利益。

---

## 新增 SystemInstruction（5 个）

| 指令 | 草案 opcode | 发起方 | 说明 |
|---|---|---|---|
| `RunnerUpdateDelegationConfig` | 40* | Runner | 开启/调整 DelegationConfig |
| `RunnerDelegateStake` | 41* | Delegator | 首次委托或追加时建新 Active Tranche |
| `RunnerIncreaseDelegation` | 42* | Delegator | 已有 Active Tranche 的追加（省去 `MAX_DELEGATORS_PER_RUNNER` 检查）|
| `RunnerUndelegateStake` | 43* | Delegator | 按 FIFO 从 Active 抽出 `amount`，转 Unbonding |
| `RunnerClaimUnbonded` | 44* | Delegator | 到期提取（显式列 `tranche_ids`，`len <= CLAIM_MAX_TRANCHES = 32`）|

**\* opcode 冲突**：40–43 在 `node/types/src/execution.rs:1281-1294` 已被 `UpdateSettlementConfig / FundActor / KeyDelivery / UpgradeActor` 占用。CIP-13 已加 TODO，实现前必须重排（推荐 44–48 或下一段空位）。

**Redelegation（原子转委托）刻意不实现**：需要双重责任记账（源 Runner slash 窗口结束前与目标 Runner 同时可 slash），复杂度过高。v1 只能 undelegate → 等 24h → delegate。

---

## 结算分账（修改 `0x03 RESULT_VERIFIER`）

对每个共识 Runner：

```
per_runner_share = runner_share_total / num_consensus_runners

R_effective = self_stake + total_active
C_bps       = effective_commission_for_epoch(R, current_epoch)

delegator_pool    = per_runner_share × total_active / R_effective
runner_commission = delegator_pool × C_bps / 10000
runner_payout     = per_runner_share - delegator_pool + runner_commission

distributable = delegator_pool - runner_commission
for each Active tranche T:
    credit(T.delegator, distributable × T.amount / total_active)
```

**整数舍入**：runner/delegator 切分余数归 Runner；Tranche 分发余数归 `tranche_id` 最小的 Active Tranche。总额严格等于 `runner_share_total`。

**Gas**：最坏 `M_runners × T_tranches` 次余额写（默认上限 200×8 = 1,600 / runner，5 个共识 Runner ≈ 8,000 次写，远低于 `LANE_SYSTEM_CYCLES = 25,000,000`）。

**事件**：`JobSettled`（1 个/Job）+ `DelegatorPayout`（1/delegator，`> DELEGATION_EVENT_BATCH_THRESHOLD = 20` 时批发）。

---

## Slash 级联（修改 `slash_runner()`）

```
slashable = Active tranches ∪ {Unbonding | now < claimable_at}
base      = self_stake + Σ slashable.amount

self_slash       = floor(requested × self_stake / base)   // 自质押永不受 cap
delegation_slash = min(requested - self_slash,
                       delegated_slashable × MAX_DELEGATION_SLASH_PER_EPOCH_BPS / 10000
                       - epoch_slashed_so_far)

for T in slashable:
    T.amount -= floor(delegation_slash × T.amount / delegated_slashable)

路由：50% Treasury / 50% Burn（与自质押 slash 相同）
```

关键点：

- **Unbonding 也进 slashable 基底**，只要 `now < claimable_at` — 防止 slash-and-run。
- **基底懒算**：每次遍历时现场求和，没有 `total_slashable` 缓存（依赖当前块号，维护成本高且本来就要遍历）。
- **Per-epoch cap 只限 Delegator 侧**（默认 500 bps = 5%/epoch）。超出的差额**不延迟到未来 epoch**，emit `DelegationSlashCapped` 了事；这是主动选择，避免跨 epoch 级联放大。
- **Floor 舍入总是下偏**（"never over-slash under ambiguity"）。

---

## Unbonding 成熟模型（§3.8 关键设计）

**没有**全局 `unbonding_queue` / 区块末 sweep。`claimable_at` 就是权威切换点：

- 到 `claimable_at` 之前：可 slash、不能 claim
- 到达 `claimable_at`：不能再 slash、可 claim
- 翻转在块边界**隐式原子发生**，无预算耗尽风险

早期草案曾用调度 sweep 把 Unbonding 转 Claimable，但若单块预算不够就会让某些 Tranche 在广告的 `claimable_at` 之后仍可被 slash — 已删除该设计。

Runner `RunnerDeregister` 对所有 Active Tranche **强制启动 Unbonding**，同时在 `RunnerRegistration` 上写 `self_stake_unbonding_claimable_at`。任何环节都不入队。

---

## 参数（均为 CIP-12 Tier 0 可调）

| 参数 | 默认 | 用途 |
|---|---|---|
| `UNBONDING_BLOCKS` | 7,200（≈24h @12s）| 解绑冷却 |
| `DELEGATION_COOLDOWN_BLOCKS` | 600（≈2h）| `RunnerUpdateDelegationConfig` 节流 |
| `MIN_SELF_BOND_BPS` | 1000（10%）| Runner 自质押占有效质押下限 |
| `MAX_DELEGATORS_PER_RUNNER` | 200 | 限 Runner 侧扇入 |
| `MAX_ACTIVE_TRANCHES_PER_DELEGATOR` | 8 | 限单 delegator 分片数 |
| `MIN_DELEGATION_AMOUNT` | 1,000 CBY | 协议 floor（Runner 可再提高）|
| `CLAIM_MAX_TRANCHES` | 32 | 单次 claim 可列 Tranche 数 |
| `MAX_DELEGATION_SLASH_PER_EPOCH_BPS` | 500（5%）| Delegator 侧 slash 封顶 |
| `MIN_COMMISSION_BPS` / `MAX_COMMISSION_BPS` | 500 / 10000 | Commission 上下限 |
| `DELEGATION_EVENT_BATCH_THRESHOLD` | 20 | 超过则 `DelegatorPayout` 批发 |

---

## 治理投票权（v1：零）

CIP-12 §6.2 定义 Stake 院权重为**质押给 Validator 的 CBY**。Runner 委托不属于 Validator 质押，也不属于未质押，v1 归入**第三类：零投票权**。CBY 持有人想同时获得治理声音与算力收益，需分仓。未来 CIP 可能扩展 CIP-12 赋予 Runner-delegated CBY 投票权（由 delegator 直投，不由 Runner 继承）。

---

## 与现有代码对照

| 规范要素 | 代码现状 |
|---|---|
| `RunnerRegistration` | ✅ 已有；需加 `delegation_config: Option<DelegationConfig>` 字段 |
| VRF 权重基数 | ✅ 已用 `registration.stake`；CIP-13 要求改为 `effective_stake` |
| `slash_runner()` | ✅ 已有（50/50 treasury/burn）；需加 tranche 级联与 per-epoch cap |
| 结算分账 | ✅ 现为 `per_runner / consensus_count`；需加 `delegator_pool` 切分 |
| `RunnerDeregister` | ❌ 当前 `UnsupportedInstruction`，CIP-13 要求实装 force-unbond |
| Tranche 存储键族 | ❌ 新增在 `0x01` 下 |
| Opcode 40–44 占用 | ⚠️ **冲突**，见 [[../drift]] |

---

## 相关

- [[governance]] — 所有参数均为 Tier 0 可调；委托 CBY 在 v1 无投票权
- [[../entities/runner-lifecycle]] — 新增委托阶段与强制解绑
- [[../entities/system-actors]] — `0x01`（Registry）、`0x03`（Verifier slash 级联）
- [[settlement-slashing]] — 分账与 slash 规则延伸
- [[vrf-runner-selection]] — 权重基数改为 `effective_stake`
- [[../parameters]] — 常量汇总（已纳入 CIP-13 段）

## 源文档冲突 / 漂移

- **CIP-13 opcode 40–44 与 `node/types/src/execution.rs:1281-1294` 现有 opcode 40 `UpdateSettlementConfig` / 41 `FundActor` / 42 `KeyDelivery` / 43 `UpgradeActor` 冲突**。CIP-13 已加 TODO，实现前需重排。[[../drift]] 已记录。
- CIP-13 §9.5 明确不实装原子 Redelegation，需外部流动质押池平滑 24h 等待。

## Sources

- `refs/cips/cip-13-runner-delegation.md` — 全文规范（Draft, 2026-04-12）
- `refs/cips/cip-2-offchain-compute.mdx` — 当前 Runner 框架与自质押基线
- `node/runner/src/system_actors.rs:13-21` — `0x01`–`0x05` 地址
- `node/execution/src/runner/{registry,dispatcher,verifier}.rs` — 实装位置（需改动）
- `node/types/src/execution.rs:1281-1294` — opcode 40–43 现有占用
