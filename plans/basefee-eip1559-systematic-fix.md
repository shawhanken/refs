# Cowboy EIP-1559 Basefee 系统化修复方案

## Context

2026-04-11 benchmark（`bench/cowboy-logs/cowboy-bench-2026-04-11T06-45-18-713Z.json`）暴露出 devnet basefee 机制在持续过载下完全失效：180s 的 flood 测试里，`cycle_basefee` 从 `1` 爬到峰值 `49` 后**单调衰减回 1** 并被钉住整整 100s，持续的 2200 tx/block 载荷完全无法把 basefee 推起来。结果：链对非正常 tx 没有任何有效节流，攻击载荷和正常载荷在 basefee 层被平等对待。

诊断出四个相互缠绕的根因（详见本文件 §"Root Causes"），外加代码和 WP/CIP-3 的常量不一致（RC5，归独立 PR）。本方案设计一个整合修复，目标：
- **目标均衡 TPS: 2000**（1500–2500 的中点）
- **区块间隔: 1000ms**
- **对非正常 tx 有效节流**：nonce-gap 洪水、under-priced tx、stale mempool tx 都能推动 basefee 上行
- **只修 basefee 相关链路**，WP/CIP-3 常量对齐留独立 PR
- **符合白皮书已有规则**：WP §2.2（pre-execution 拒绝）、§17.2（intrinsic cost）、§6.4（mempool 按 intrinsic cost 排序）、§4.2（EIP-1559 公式）

## Root Causes

| # | 根因 | 证据 |
|---|---|---|
| RC1 | `BASEFEE_ALPHA=DENOM=8` 是 Ethereum 12s 区块参数；Cowboy 1s 区块 → 每秒调节速率是 Ethereum 的 12× | `types/src/constants.rs:68,71` |
| RC2 | `basefee < DENOM=8` 时 `basefee*Δ/target/8` 整数截断为 0，`.max(1)` 地板让 ±1 对称更新主导，geometric 响应失效 | `basefee.rs:86-111`；实测 ramp 只有 +1.2/block |
| RC3 | 所有 pre-execution 失败路径返回 `(0, 0)` cycles → failed-tx 洪水在 basefee 看来是"空 block"→ basefee 反而下跌（违反 WP §17.2 intrinsic cost 精神） | `transaction.rs:81,94,102,126`；`speculative.rs:180,218` |
| RC4 | RPC 准入不检查 `max_fee_per_cycle ≥ current_basefee`（违反 WP §2.2 / §6.4），stale tx 积在 mempool，执行时以 0 cycles 被拒绝 | `rpc/src/handlers/chain.rs:92-270` |

**不在本 PR 范围**（归 RC5 / 独立 PR）：
- WP §4.3 `T_c=10M` / CIP-3 `T_c=10M` / 代码 `12.5M`（本 PR 进一步改为 `20M`，偏离 WP，需独立对齐）
- WP §17.2 Transfer intrinsic=21,000 cycles / 代码 `base+transfer=10,000`
- WP §17.9 `LANE_USER=5M (50%)` / 代码 `13.88M`
- CIP-5 timer budget 550k cycles / 代码 `LANE_TIMER=5.55M`

## Design Summary

四块整合修复：
1. **参数重校准**：采纳 Caleb 的"匹配 Ethereum per-second 变化率"思路，`ALPHA=DENOM=96`；但必须同时抬 `MIN_BASEFEE` 到 1e6，结构性消灭整数截断区
2. **算法清理**：删除 `update_one()` 里现已无用的 `.max(1)` 不对称地板
3. **失败 tx 账务（WP §17.2 spirit）**：admitted-but-failed tx 统计贡献 `base_cycles` 到 U_x，不扣账户
4. **Mempool 准入 + 驱逐（WP §2.2 / §6.4 mandate）**：把 `signature/nonce/balance/basefee-too-low` 检查前移到 mempool 准入

三块按依赖拆成 3 个 PR，避免单次改动过大。

---

## §1 参数最终值（`types/src/constants.rs`）

| 常量 | 行号 | 现值 | 新值 |
|---|---|---|---|
| `BASEFEE_ALPHA` | 68 | 8 | **96** |
| `BASEFEE_MAX_CHANGE_DENOM` | 71 | 8 | **96** |
| `MIN_BASEFEE` | 86 | 1 | **1_000_000** (1e6) |
| `INITIAL_CYCLE_BASEFEE` | 80 | 1e8 | **1_000_000_000** (1e9) |
| `INITIAL_CELL_BASEFEE` | 83 | 1e8 | **1_000_000_000** |
| `BLOCK_CYCLES_TARGET` | 42 | 12_500_000 | **20_000_000** |
| `BLOCK_CELLS_TARGET` | 45 | 2_500_000 | **4_000_000** |
| `LANE_USER_CYCLES` | 50 | 13_888_888 | **22_222_222** |
| `LANE_RUNNER_CYCLES` | 53 | 5_555_555 | **8_888_888** |
| `LANE_TIMER_CYCLES` | 56 | 5_555_557 | **8_888_890** |
| `LANE_SYSTEM_CYCLES` | 61 | 25_000_000 | **40_000_000** |

**不动**：`base_cycles=5000`, `transfer_cycles=5000`（`execution/src/gas.rs:151,155`）。

### 参数数学验证

**目标均衡 2000 TPS** 在 `transfer=10k cycles/tx` 下：2000 tx × 10k = 20M cycles = `BLOCK_CYCLES_TARGET` ✓

**2.5k TPS 过载**：`used/target=1.25`，`delta = basefee × 0.25/96 ≈ basefee × 0.26%` per block → 180s 累计 `(1.0026)^180 ≈ 1.60×`

**4k TPS 饱和（System lane 打满）**：`used/target=2`，`delta = basefee/96 ≈ 1.042%` per block（触发 cap）→ 180s 累计 `(1.01042)^180 ≈ 6.47×`

**Caleb 校准核对**：`(1 + 1/96)^12 = 1.1316`（对比 Ethereum 的 1.125，偏差 +0.6%，整除友好）

**空闲半衰期**：`ln(0.5)/ln(95/96) ≈ 66 blocks ≈ 66s`

**从 INITIAL 衰减到 MIN**：`log(1000)/log(96/95) ≈ 659 blocks ≈ 11 分钟`（vs 当前 ~150s 就衰到 1）

**截断区结构性消失**：`max_delta @ MIN = 1e6/96 ≈ 10_416 ≫ 1`；截断区 `[1, 96)` 整个被地板压在下面

**Genesis tx 成本**：transfer @ genesis = `10_000 × 1e9 = 1e13 attoCBY = 1e-5 CBY`（日常可忽略，但 burn 会计非零）

---

## §2 `update_one()` 算法清理（`execution/src/basefee.rs:86-111`）

**核心改动**：删除 `.max(1)` 的不对称地板（新的 `MIN_BASEFEE ≫ DENOM` 已结构性防止截断冻结）。

```rust
fn update_one(basefee: u128, used: u128, target: u128) -> u128 {
    if target == 0 { return basefee; }
    let max_delta = basefee / BASEFEE_MAX_CHANGE_DENOM;  // 不再 .max(1)

    let new_basefee = if used > target {
        let delta = (basefee.saturating_mul(used - target) / target / BASEFEE_ALPHA)
            .min(max_delta);
        basefee.saturating_add(delta)
    } else if used < target {
        let delta = (basefee.saturating_mul(target - used) / target / BASEFEE_ALPHA)
            .min(max_delta);
        basefee.saturating_sub(delta)
    } else {
        basefee
    };

    new_basefee.max(MIN_BASEFEE).min(MAX_BASEFEE)  // MIN_BASEFEE 是真正的下限
}
```

**编译期不变量**（`basefee.rs` 顶部）：
```rust
const _: () = assert!(
    MIN_BASEFEE >= (BASEFEE_MAX_CHANGE_DENOM as u128) * 100,
    "MIN_BASEFEE must dominate DENOM to avoid integer-truncation freeze"
);
```

**Migration clamp**（`basefee.rs:128` `DualBasefee::load_from_storage`）：
```rust
result.cycle_basefee = result.cycle_basefee.max(MIN_BASEFEE);
result.cell_basefee = result.cell_basefee.max(MIN_BASEFEE);
```
现有 devnet state（可能持有 `cycle_basefee=1`）在启动时一次性被抬到 `MIN_BASEFEE`。

**注释更新**（`basefee.rs:81-85`）：解释截断冻结由 `MIN_BASEFEE > DENOM` 结构性保证，不再依赖 delta floor。

---

## §3 失败 tx 账务（RC3，对齐 WP §17.2）

### 3.1 设计原则

WP §17.2：**每 tx 在 execution 开始前就要付 intrinsic cost**。我们采纳其 spirit 但不真实扣账户（"余额不足就是因为没钱"的循环 + 复杂度）：

- **Admitted-but-failed tx** 统计贡献 `gas_costs.base_cycles = 5000` 到 `U_x`（basefee 更新用）
- **不扣账户余额**，不改经济模型
- **不占 lane budget**（独立累加器，防 DoS）
- 真实 spam tax（从账户扣）留给后续经济设计 PR

### 3.2 `speculative.rs` 改动（`storage/src/speculative.rs:167-244`）

引入独立 spam 累加器和 base_cycles 读取：
```rust
let base_spam_cycles = executor.gas_costs().base_cycles;  // or 从 constants.rs 读
let mut lane_cycles: [u64; 4] = [0u64; 4];   // lane budget gating（只成功）
let mut successful_cycles: u64 = 0;           // basefee 的"真实"贡献
let mut failed_spam_cycles: u64 = 0;          // basefee 的 spam 贡献（不占 lane）

for tx in &block.transactions {
    // ... 原 lane budget 检查 ...
    if lane_cycles[lane_idx] >= lane_budgets[lane_idx] {
        // InsufficientLaneBudget 路径：贡献 spam，不占 lane
        failed_spam_cycles = failed_spam_cycles.saturating_add(base_spam_cycles);
        execution_results.push((0, 0, /* error */, vec![], vec![]));
        continue;
    }
    // 执行
    let result = match executor.execute_one_tx(...).await {
        Ok(r) => r,
        Err(_) => {
            // ExecutorError 路径
            failed_spam_cycles = failed_spam_cycles.saturating_add(base_spam_cycles);
            (0, 0, /* error */, vec![], vec![])
        }
    };
    if is_success(&result) {
        lane_cycles[lane_idx] = lane_cycles[lane_idx].saturating_add(result.0);
        successful_cycles = successful_cycles.saturating_add(result.0);
    } else {
        failed_spam_cycles = failed_spam_cycles.saturating_add(base_spam_cycles);
    }
    execution_results.push(result);
}

// Cap failed_spam 最多贡献 1× target，防止人为过度拉抬 basefee
let capped_spam = failed_spam_cycles.min(BLOCK_CYCLES_TARGET);
let total_cycles_used = successful_cycles.saturating_add(capped_spam);
```

**Cap 的选择**：`1× BLOCK_CYCLES_TARGET = 20M cycles`，相当于 4000 条失败 tx 的贡献上限。超过这个量时 basefee 已经处于 1× target 的水位，无需继续堆高。

### 3.3 `transaction.rs` 改动

`transaction.rs` 里的几个早退返回点（`:81, :94, :102, :126`）保持现状返回 `(0, 0, ...)`。**不在 transaction 层加 spam 计数**，完全由 `speculative.rs` 统一处理（通过 `is_success` 判断）。这样保持 `transaction.rs` 的纯净（它只算"真正消耗了什么"），`speculative.rs` 负责"block 层统计"。

### 3.4 `is_success` helper

需要一个判断 tx 执行结果是否成功的辅助函数。检查 `execution_results[i].2` 的 `ExecutionStatus`：
- `ExecutionStatus::Success` → true
- `ExecutionStatus::ExecutionError(_)` → false

位置：可以加在 `storage/src/types.rs` 或 `speculative.rs` 的局部 helper。

---

## §4 Mempool 准入 + 驱逐（RC4，对齐 WP §2.2 / §6.4）

### 4.1 准入检查（`rpc/src/handlers/chain.rs`）

**前置工作**：把 `rpc/src/handlers/runner.rs:32` 里的 `read_current_basefee(&state)` 抽到新文件 `rpc/src/handlers/util.rs`（避免 chain→runner 循环）。`runner.rs` 改用 util。

**位置**：tx submit handler 里，签名验证之后、nonce gate 之前（约 `:161` 之后）。

```rust
let (bf_cycle, bf_cell) = read_current_basefee(&state).await;

// 12.5% 安全边际：允许 tx 容忍 ~12 blocks 的满额 bump
let min_fee_cycle = bf_cycle.saturating_mul(9) / 8;
let min_fee_cell  = bf_cell.saturating_mul(9) / 8;

if tx.max_fee_per_cycle < min_fee_cycle || tx.max_fee_per_cell < min_fee_cell {
    metrics::counter!("rpc_rejected_basefee_too_low").increment(1);
    return Err(ApiError::basefee_too_low(bf_cycle, bf_cell));
}
```

**12.5% 边际的理由**：新参数下一块最大 bump `1/96 ≈ 1.042%`；12.5% 覆盖 `log(1.125)/log(1.01042) ≈ 12` blocks ≈ 12s 的缓冲。既不过度拒绝也不让 stale tx 漏进来。

**新错误类型**：`ApiError::basefee_too_low { current_cycle: u128, current_cell: u128 }`，返回 4xx + JSON body 包含当前 basefee（客户端可据此重签名）。

### 4.2 Mempool 驱逐

**位置**：每次 block finalize 后的 mempool 清理路径。需要在代码里搜 `mempool.report` / `mempool.retain` 的调用点确认（预计在 `chain/src/engine.rs` 或 `chain/src/application.rs` 的 report 回调里）。

**逻辑**：无安全边际的硬驱逐（只驱逐真正 unpayable 的 tx）：
```rust
mempool.retain(|tx| tx.max_fee_per_cycle >= current_basefee_cycle
               && tx.max_fee_per_cell  >= current_basefee_cell);
```

**不带边际的理由**：准入层的 12.5% 缓冲已经吸收正常波动；驱逐只处理硬失效的情况。避免在 threshold 附近反复 churn。

### 4.3 WP §2.2 mandate 的其他检查

WP §2.2 要求 mempool 在准入时就拒绝：
- `(a) limits exceed maxima` — cycles/cells limit 超过 block 上限 → 本 PR 加
- `(b) insufficient balance` — balance < max_total_cost → 本 PR 加
- `(c) signature invalid` — 已有
- `(d) access list invalid` — 本 PR 不涉及（access list 另一个系统）
- `(e) payload decoding fails` — 已有（JSON parse error）

(a) 和 (b) 的实现：准入 handler 里加两个检查：
```rust
// WP §2.2(a): limits vs block max
if tx.cycles_limit > LANE_SYSTEM_CYCLES || tx.cells_limit > BLOCK_CELLS_HARD_CAP {
    return Err(ApiError::limits_exceed_maxima(...));
}

// WP §2.2(b): balance sufficiency at max_fee
let sender = state.blockchain_storage.get_account(&tx.from).await?;
let max_cycles_cost = (tx.cycles_limit as u128).saturating_mul(tx.max_fee_per_cycle);
let max_cells_cost = (tx.cells_limit as u128).saturating_mul(tx.max_fee_per_cell);
let max_total_cost = max_cycles_cost.saturating_add(max_cells_cost);
if sender.map(|a| a.balance as u128).unwrap_or(0) < max_total_cost {
    return Err(ApiError::insufficient_balance_for_gas(...));
}
```

这样执行层 `transaction.rs:126` 的 `InsufficientBalanceForGas` 分支成为"不应到达"的 defensive 路径（但保留，因为 mempool→block 之间账户余额可能变化）。

---

## §5 测试计划

### 5.1 已有测试的修改（`execution/src/basefee.rs`）

| Test | 行 | 状态 | 改动 |
|---|---|---|---|
| `spec_h2_1` | 219 | **更新** | delta `basefee/8 → basefee/96`；初值改到 ≥ MIN_BASEFEE |
| `spec_h2_2` | 245 | **更新** | 对称 |
| `spec_h2_3` | 268 | 保留 |  |
| `spec_h2_4` | 278 | **更新** | cap `basefee/8 → basefee/96` |
| `spec_h2_5` | 299 | **更新** | 起始 basefee ≥ MIN_BASEFEE；断言 floor=1e6 |
| `spec_h2_6` | 312 | 保留 |  |
| `spec_h2_7` | 340 | 保留（常量跟着动） |  |
| `spec_h2_8` | 348 | 保留 |  |
| `spec_h2_9` | 365 | 保留 |  |
| `spec_h2_10` | 391 | 保留 |  |
| `spec_h2_11` | 462 | **重写** | sticky=7 已在 MIN_BASEFEE 之下；改为"在 MIN_BASEFEE 处不 freeze" |
| `spec_mg_1` | 419 | **更新** | 4× target=80M，System=40M |
| `spec_h4_1/2` | 430, 443 | 保留 |  |

### 5.2 新增测试

1. **`spec_h2_12_per_second_rate_matches_ethereum`**：12 轮满载更新，断言 `final/initial ∈ [1.11, 1.14]`
2. **`spec_h2_13_sustained_load_monotonic_ramp`**：180 blocks @ `used=2×target`，断言单调递增且 `end ≥ 6× start`
3. **`spec_h2_14_failed_tx_flood_drives_basefee`**：`speculative.rs` 级别 integration test，构造 2200 条 InvalidNonce / InsufficientBalance tx 的 block，验证：
   - `total_cycles_used = min(2200 × 5000, 20M) = 11M`（低于 cap，但超过 `target × 0.5`）
   - basefee 不再下跌（修复前是下跌）
4. **`spec_h2_15_idle_half_life_approx_66_blocks`**：从 `10 × MIN` 开始，66 empty blocks 后 basefee ≈ `5 × MIN` (±10%)
5. **`spec_h2_16_min_basefee_does_not_freeze`**：起始 basefee = MIN_BASEFEE，满载 block 验证能升，空 block 验证 stay at MIN_BASEFEE（不 underflow）
6. **`spec_h2_17_failed_tx_spam_cap`**：6000 失败 tx 的 block，验证 `total_cycles_used ≤ 2 × BLOCK_CYCLES_TARGET`（successful + capped spam）
7. **`rpc_rejects_under_priced_tx`**（`rpc/src/handlers/chain.rs` tests）：submit tx with max_fee < basefee*9/8；断言 4xx + metric 增加
8. **`rpc_rejects_balance_insufficient_for_gas`**：WP §2.2(b) 检查
9. **`rpc_rejects_limits_exceed_maxima`**：WP §2.2(a) 检查
10. **`mempool_evicts_under_priced_on_basefee_bump`**：insert tx at basefee B，bump basefee past tx max_fee，验证下次 report() 后 tx 被驱逐

### 5.3 其他测试扫荡

扫 `node/execution/src/execution/tests.rs` 和 `node/rpc/src/handlers/chain.rs` 的测试 fixture：grep `max_fee_per_cycle`，所有 `< 1.125e9` 的硬编码值全部 bump 到 `2_000_000_000`（2× new genesis，2 blocks 缓冲）。

同时 bench 客户端默认值：
- `node/bench/src/cowboy/bench.ts` — setup 时的初始 maxFeePerCycle
- `node/bench/src/cowboy/flood.ts` — 已经是动态 4× basefee，但检查初始 default

---

## §6 PR 拆分（按依赖顺序）

### PR-1 "basefee core recalibration"
**范围**：`constants.rs` 参数 + `basefee.rs` `update_one` + migration clamp + 全部 SPEC-H2 / SPEC-MG 测试更新 + 新增 `spec_h2_12/13/15/16`

**文件**：
- `node/types/src/constants.rs`
- `node/execution/src/basefee.rs`
- `node/execution/src/execution/tests.rs`（扫荡 max_fee_per_cycle）

**验收**：`cargo test -p cowboy-execution` 全过；基础 flood bench（180s）观察 basefee 在 2× target 下单调上升到 ≥ 6× 起点

### PR-2 "failed-tx spam accounting"
**依赖**：PR-1（新 basefee 参数决定 spam 能推到什么位置）

**范围**：`speculative.rs` 的 failed_spam_cycles 累加 + lane 分离 + cap + 新增 `spec_h2_14/17`

**文件**：
- `node/storage/src/speculative.rs`
- `node/storage/src/types.rs`（可能需要 `is_success` helper）
- `node/execution/src/execution/tests.rs`（可能添加 speculative-level 测试）

**验收**：`cargo test --workspace`；构造 nonce-gap flood 测试，验证 basefee 上升

### PR-3 "mempool pre-admission + eviction"
**依赖**：PR-1（basefee 值域确定后才好 reason about cutoff）

**范围**：WP §2.2 / §6.4 的前移检查 + 新 ApiError 类型 + mempool 驱逐 + 新增 `rpc_*` / `mempool_*` 测试

**文件**：
- `node/rpc/src/handlers/util.rs`（新文件，托管 `read_current_basefee`）
- `node/rpc/src/handlers/runner.rs`（改用 util）
- `node/rpc/src/handlers/chain.rs`（准入检查）
- `node/rpc/src/error.rs`（新 ApiError 变体）
- `node/chain/src/engine.rs` 或 `application.rs`（mempool 驱逐调用点，需搜确认）
- `node/chain/src/mempool/*.rs`（驱逐 helper）
- bench clients：`node/bench/src/cowboy/bench.ts` 默认 max_fee bump

**验收**：`cargo test --workspace`；完整 bench 跑一遍，验证 stale tx 被准入层挡住、nonce-gap 洪水被驱逐

---

## §7 风险与回滚

### 7.1 风险点

1. **现有 devnet state 持 `cycle_basefee=1`**：`load_from_storage` 的 clamp 在启动时一次性抬到 `MIN_BASEFEE=1e6`。非 consensus break，但建议配发 release note"devnet 建议清库"
2. **客户端硬编码 max_fee 过低**：SDK/bench 里 `max_fee=1` 这种会被 RPC 拒绝。PR-3 同批 bump 到 `2e9`
3. **Spam cap 的 tuning**：`failed_spam_cycles.min(BLOCK_CYCLES_TARGET)` 把失败 tx 贡献上限到 1× target。若未来观察到调整空间，可改为参数化
4. **Consensus safety**：参数改动是 consensus-critical，必须 hard-fork / 清库重启。`BASEFEE_STORAGE_KEY` 保持不变，schema 兼容
5. **测试脆弱性**：integration-style tests（H2-13 持续爬升）对精确 TPS 敏感，用 ±10% 相对 bound
6. **Mempool retain 性能**：每次 block finalize 都 filter 整个 mempool，对高 backlog 场景可能慢。若实测有问题，改为 lazy eviction（下次 `pull` 时过滤）

### 7.2 未处理（独立 tracking）

- **RC5 WP/CIP-3 常量对齐**：T_c、LANE_*、timer budget、Transfer intrinsic=21k。本 PR 反而让偏离更大（`T_c=20M`）。创建独立 issue "CIP-3 spec reconciliation" 跟踪
- **真实从账户扣 base_cycles 的 spam tax**：语义上更干净但撞上"余额不足就是因为没钱"的循环。留给后续经济设计讨论
- **WP §17.2 intrinsic=21k vs 代码 10k**：归 RC5

---

## §8 验收（End-to-End）

三个 PR 都 land 后，跑以下验证：

1. **单元测试**：`cargo test --workspace` 全过
2. **重跑 bench**（`cd node/bench && node bench-workflow.mjs` 或等效命令）：
   - 观察 180s sustained flood 下 `cycle_basefee` 时序：
     - t=0s: ≈ 1e9
     - t=30s: ≈ 1.3e9（+1% per block）
     - t=180s: ≥ 6e9
   - 停 submission 后 basefee 半衰期 ≈ 66s
   - 衰减到 `MIN_BASEFEE=1e6` 需 ~11 min
3. **Nonce-gap flood 验证**：构造一个专门发送 nonce-out-of-order tx 的客户端，180s 跑下来验证 basefee 被推上去（之前会下跌）
4. **RPC 准入验证**：`curl` 一条 `max_fee_per_cycle=1` 的 tx，期望 4xx + `basefee_too_low` 错误
5. **Mempool 驱逐验证**：先 submit 一批低 max_fee tx（当前 basefee 下合法），然后用高压 flood 把 basefee 推上去，观察前一批是否被驱逐（mempool size 下降）

---

## Critical Files Reference

| 文件 | 作用 | PR |
|---|---|---|
| `node/types/src/constants.rs` | basefee/lane 参数 | PR-1 |
| `node/execution/src/basefee.rs` | `update_one` + migration clamp + tests | PR-1 |
| `node/execution/src/execution/tests.rs` | tx fixture max_fee 扫荡 | PR-1 |
| `node/storage/src/speculative.rs` | failed_spam_cycles + lane 分离 + cap | PR-2 |
| `node/storage/src/types.rs` | `is_success` helper（可选） | PR-2 |
| `node/rpc/src/handlers/util.rs` | `read_current_basefee`（新文件） | PR-3 |
| `node/rpc/src/handlers/runner.rs` | 改用 util | PR-3 |
| `node/rpc/src/handlers/chain.rs` | WP §2.2 / §6.4 准入检查 | PR-3 |
| `node/rpc/src/error.rs` | 新 `ApiError` 变体 | PR-3 |
| `node/chain/src/engine.rs` 或 `application.rs` | mempool 驱逐调用点（需搜确认） | PR-3 |
| `node/chain/src/mempool/*.rs` | 驱逐 helper | PR-3 |
| `node/bench/src/cowboy/bench.ts` | 客户端默认 max_fee bump | PR-3 |

## References

- `/home/ubuntu/workspace/refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised.md`
  - §2.2 / §2.3（行 438-446）：pre-execution 拒绝规则
  - §4.2（行 521-525）：EIP-1559 公式
  - §6.4（行 601）：mempool intrinsic-cost 排序
  - §17.2（行 849-858）：intrinsic cost model
  - §17.8（行 952）：basefee 公式（authoritative）
- `/home/ubuntu/workspace/refs/cips/cip-3-fee-model.mdx`（§2.4 basefee update）
- `/home/ubuntu/workspace/refs/202603/20260317_conflict_analysis.md`（RC5 常量冲突记录）
- `/home/ubuntu/workspace/node/bench/cowboy-logs/cowboy-bench-2026-04-11T06-45-18-713Z.json`（基线 bench 数据）
