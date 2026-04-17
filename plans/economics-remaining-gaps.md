# 计划：Cowboy 经济系统剩余缺口修复（econ-gaps）

## Context

上一期 econ-fixes 已完成 42 项经济系统检查中的 37 项（88%）。
本计划修复评估报告中识别的剩余 3 个可操作缺口（P1/P2 优先级）：

1. **dispute_window_blocks 无中央常量**（白皮书 §13 = 75 blocks，当前各处硬编码 10/100）
2. **Runner Slashing 缺失**（dishonest runner 仅扣信誉 -5，无质押扣款）
3. **Stake 1.5× max_job_value 动态检查缺失**（高价值作业 runner 质押不足保障）

P3（VM 字节码层大整数钩子）需 RustPython 深度改造，继续 defer，不在本计划内。

---

## 修复 A：dispute_window_blocks 中央常量（trivial）

### 问题
`VerificationConfig.dispute_window_blocks: u64` 字段存在，但无中央常量定义。
dispatcher.rs 测试硬编码 `10`，verifier.rs 测试硬编码 `100`，生产代码无默认约束。
白皮书 §13 明确要求 `dispute_window_blocks = 75`。

### 改动

**1. 添加常量** — `/node/types/src/constants.rs`（在 HEARTBEAT_TIMEOUT_BLOCKS 附近）
```rust
/// Dispute window for challenging settlement results (whitepaper §13).
pub const DISPUTE_WINDOW_BLOCKS: u64 = 75;
```

**2. 替换硬编码** — `/node/execution/src/runner/dispatcher.rs`
- 行 188：`dispute_window_blocks: 10` → `dispute_window_blocks: DISPUTE_WINDOW_BLOCKS`
- 行 1140：同上
- 行 1575：同上
- import 添加 `use cowboy_types::DISPUTE_WINDOW_BLOCKS;`

**3. 更新测试默认值** — `/node/execution/src/runner/verifier.rs`
- 行 687（make_job_spec）：`dispute_window_blocks: 100` → `dispute_window_blocks: DISPUTE_WINDOW_BLOCKS`

**4. 添加测试** — 在 `constants.rs` 或 `dispatcher.rs`：
```rust
#[test]
fn spec_dispute_window_75() {
    assert_eq!(DISPUTE_WINDOW_BLOCKS, 75);
}
```

---

## 修复 B：Stake 1.5× max_job_value 动态过滤（small）

### 问题
CIP-2 §4 要求 `stake ≥ max(10_000 CBY, 1.5 × declared_max_job_value)`。
当前 `registry.rs:65` 只检查 `stake ≥ MIN_STAKE_CBY_WEI`（固定 10K CBY）。
在 job 分配时 (`select_runner_committee_with_seed`) 也未检查 1.5× max_price 条件。

### 改动

**1. 添加常量** — `/node/runner/src/types.rs`（紧接 MIN_STAKE_CBY_WEI）
```rust
/// Stake multiplier numerator: runner stake must be ≥ max_job_value × 3/2 (i.e. 1.5×).
pub const STAKE_JOB_MULTIPLIER_NUM: u128 = 3;
pub const STAKE_JOB_MULTIPLIER_DENOM: u128 = 2;
```

**2. 注册时增加动态 stake 下限** — `/node/execution/src/runner/registry.rs`
在现有 `stake < MIN_STAKE_CBY_WEI` 检查后增加：
```rust
// CIP-2 §4: stake ≥ 1.5 × declared_max_job_value
let dynamic_min = (registration.rate_card.max_job_value as u128)
    .saturating_mul(STAKE_JOB_MULTIPLIER_NUM)
    .saturating_div(STAKE_JOB_MULTIPLIER_DENOM);
if (registration.stake as u128) < dynamic_min {
    return Err(ExecutionError::InsufficientStake {
        required: dynamic_min as u64,
        actual: registration.stake,
    });
}
```

**3. job 分配时过滤** — `/node/execution/src/runner/dispatcher.rs`
在 `select_runner_committee_with_seed()` 第 7 个 filter 后添加第 8 个 filter：
```rust
// Filter 8: Stake sufficiency for this job (CIP-2 §4: 1.5 × max_price)
if job_spec.max_price > 0 {
    let required = (job_spec.max_price as u128)
        .saturating_mul(STAKE_JOB_MULTIPLIER_NUM)
        .saturating_div(STAKE_JOB_MULTIPLIER_DENOM);
    if (runner.stake as u128) < required {
        return false;
    }
}
```

**4. 添加/更新错误变体** — `/node/execution/src/error.rs`
确认 `ExecutionError::InsufficientStake { required: u64, actual: u64 }` 存在（已有则不动）。

**5. 测试** — 在 `dispatcher.rs` 或 `registry.rs` tests：
- SPEC-B1：max_price=100, stake=149 → 过滤掉
- SPEC-B2：max_price=100, stake=150 → 通过
- SPEC-B3：max_price=0 → 不检查（通过）
- SPEC-B4：注册时 max_job_value=1000 CBY, stake=1499 → InsufficientStake

---

## 修复 C：Runner Slashing 质押扣款（medium）

### 问题
CIP-2 §8 / 白皮书 §12.2：proven dishonesty → stake slashing。
当前只有 `TIMEOUT_PENALTY=5` reputation 扣分（dispatcher.rs:23），无任何质押扣款。

### 设计决策（devnet 简化版）
白皮书要求 "challenge window → 挑战证明 → slash"，完整机制需 Challenge 指令（scope 过大）。
Devnet 简化：**settlement 时对 minority/dishonest runners 自动立即扣款**，无需链上挑战。
slash 金额 = `min(stake, job_spec.max_price)`（即作业最大报酬，足以覆盖损失）。
slash 款项路由：50% 发给 treasury（0x08），50% burn（Address::ZERO）。
若扣后 `stake < MIN_STAKE_CBY_WEI`，自动标记 runner 为 inactive（reputation=0）。

### 新增常量 — `/node/execution/src/runner/dispatcher.rs`（或 constants.rs）
```rust
/// Slash amount cap: dishonest runner loses at most the full job max_price.
/// Slash split: 50% treasury, 50% burn.
pub const SLASH_TREASURY_PERCENT: u64 = 50;
```

### 新增函数 — `/node/execution/src/runner/verifier.rs`
```rust
async fn slash_runner<S: StateStore>(
    store: &S,
    runner_addr: Address,
    slash_amount: u64,   // = min(runner.stake, job_spec.max_price)
    treasury_addr: Address,
) -> Result<(), ExecutionError>
```
逻辑：
1. 读取 RunnerRegistration
2. `actual_slash = slash_amount.min(registration.stake)`
3. `registration.stake -= actual_slash`
4. 若 `registration.stake < MIN_STAKE_CBY_WEI` → `registration.reputation = 0`（排除分配）
5. 写回 RunnerRegistration
6. `treasury_amount = actual_slash / 2`，`burn_amount = actual_slash - treasury_amount`
7. treasury(0x08) balance += treasury_amount；Address::ZERO balance += burn_amount

### 调用点 — `/node/execution/src/runner/verifier.rs` verify_results()

**MajorityVote 模式** （现有 lines 476-522）：
在确认 majority group 后，对 `all_runners - majority_runners` 的每个 address 调用 `slash_runner()`。

**Deterministic 模式** （现有 lines 596-624）：
对所有 result ≠ first_result 的 runner 调用 `slash_runner()`。

**其余模式（None/EconomicBond/StructuredMatch）**：不 slash。

### 关键文件
- `/node/execution/src/runner/verifier.rs` — 主逻辑（slash_runner + 调用点）
- `/node/execution/src/runner/registry.rs` — 确认 RunnerRegistration 读写辅助函数可复用
- `/node/runner/src/types.rs` — RunnerRegistration 结构（stake: u64, reputation: u8）
- `/node/types/src/constants.rs` — TREASURY_SYSTEM_ACTOR（0x08）已有

### 测试（在 verifier.rs）
- SPEC-SLASH-1：MajorityVote 2 of 3，minority runner stake 从 50K → max(50K - max_price, 0)
- SPEC-SLASH-2：stake < MIN_STAKE 后 reputation=0
- SPEC-SLASH-3：Deterministic 1 mismatch → slashed
- SPEC-SLASH-4：None 模式 → 无 slashing

---

## 实施顺序

```
修复 A（~30 min）  →  修复 B（~1h）  →  修复 C（~2h）
  独立，无依赖         独立，无依赖        依赖 A（DISPUTE_WINDOW_BLOCKS import）
```

所有改动在 `devnet` 分支进行。

---

## 关键文件汇总

| 文件 | 修复 |
|------|------|
| `/node/types/src/constants.rs` | A（新增 DISPUTE_WINDOW_BLOCKS） |
| `/node/execution/src/runner/dispatcher.rs` | A（替换硬编码）、B（过滤 filter 8） |
| `/node/execution/src/runner/verifier.rs` | A（测试默认值）、C（slash_runner + 调用） |
| `/node/execution/src/runner/registry.rs` | B（注册动态 stake 检查） |
| `/node/runner/src/types.rs` | B（新增 STAKE_JOB_MULTIPLIER 常量） |
| `/node/execution/src/error.rs` | B（确认 InsufficientStake 变体） |

---

## 验证

```bash
cd /home/ubuntu/workspace/node

# 全量测试（确保无回归）
cargo test -p cowboy-execution --lib 2>&1 | tail -5

# 专项测试
cargo test -p cowboy-execution spec_dispute_window    # Fix A
cargo test -p cowboy-execution spec_b                 # Fix B
cargo test -p cowboy-execution spec_slash             # Fix C
```

预期：新增约 10 个 SPEC-* 测试，全量测试数从 121 增至 ~131。
