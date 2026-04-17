# Plan: 提升 avg_confirmed 和 avg_submitted 指标

## Context

当前 bench 日志关键数字：

| 指标 | 当前值 | 瓶颈来源 |
|------|--------|----------|
| avg_confirmed (avg_tps) | 911 TPS | 系统 lane 容量 + 0-TPS 块事件 |
| avg_submitted | 933 TPS | 系统 lane 容量 |
| sustained_mid80 (confirmed/submitted) | 1200 / 1200 TPS | 硬上限 = 25M cycles / 20k cycles/tx = 1250 |
| 零 TPS 块事件 | 19 / 140 个桶 (13.6%) | 拖累 avg = 911 vs sustained = 1200 |

**根本原因**：每笔 transfer tx 消耗 `base_cycles(10,000) + transfer_cycles(10,000) = 20,000 cycles`。
系统 lane 预算 = `LANE_SYSTEM_CYCLES = 25,000,000`，因此每块最多容纳 `25M / 20k = 1,250 txs`。
bench 使用 1200 workers 已贴近上限。

**用户方向**：降低 transfer 费用（即 gas 常量），可直接提升单块 tx 容量，从而提升 avg TPS。

## 核心数学

| 方案 | base_cycles | transfer_cycles | 每 tx 总费 | 每块容量 | 理论 avg TPS | 提升 |
|------|------------|-----------------|-----------|---------|-------------|------|
| 当前 | 10,000 | 10,000 | **20,000** | 1,250 | ~1,200 | — |
| 保守 | 10,000 | 5,000 | **15,000** | 1,667 | ~1,600 | +33% |
| 激进 | 5,000 | 5,000 | **10,000** | 2,500 | ~2,400 | +100% |

选择**激进方案**（10,000 cycles/tx）：avg_confirmed 和 avg_submitted 均可翻倍，与用户"更明显"的期望一致。

## 改动范围（3 个文件）

### 1. `execution/src/gas.rs` — 降低 base 和 transfer 常量

**文件**: `execution/src/gas.rs:151-155`

```rust
// 当前
base_cycles: 10_000,
base_cells: 1_000,
...
transfer_cycles: 10_000,
transfer_cells: 1_000,

// 目标
base_cycles: 5_000,
base_cells: 500,
...
transfer_cycles: 5_000,
transfer_cells: 500,
```

注意：`base_cells` 和 `transfer_cells` 同比缩减，避免 cells lane 成为新瓶颈（cells lane budget = `BLOCK_CELLS_TARGET`）。

### 2. `bench/config_cowboy.json` — 增加 worker 数量

**文件**: `bench/config_cowboy.json`

```json
"concurrency": 2400,
"maxFloodWorkers": 2400,
"cyclesLimit": "20000",
```

- `maxFloodWorkers: 2400`：匹配新容量 25M / 10k = 2,500（保留 100 slot 余量）
- `cyclesLimit: "20000"`：收紧到 2× 实际使用量，减少余量浪费（不影响吞吐，但更严格）

### 3. `bench/src/cowboy/flood.ts` — 更新 SYSTEM_LANE_CAPACITY 注释/常量

**文件**: `bench/src/cowboy/flood.ts:37`

将 `SYSTEM_LANE_CAPACITY = 1200` 更新为 `2400`（及相关注释）。

注意：如果该常量是从节点常量动态推导的，则只需更新注释；如果是硬编码数字，需直接修改。

## 需要额外操作的前提

增加 `maxFloodWorkers` 到 2400 后，bench 需要有 **2400 个已充值账户**。
当前 cowboy-keys 目录可能只有 1200 个密钥。需要确认：
1. bench setup 流程是否能生成更多账户（`./scripts/run_build.sh` 或类似脚本）
2. faucet 是否能为新账户充值

如果无法立即准备 2400 账户，可先只修改 gas.rs，用 1200 workers 测试（此时每块仅用 12M cycles，不会提升 TPS，但验证 gas 修改无副作用）；然后再扩充账户数量完成完整测试。

## 测试验证

```bash
# 1. 跑单元测试确认 gas 常量无测试断言失败
cargo test -p cowboy-execution -- test_gas --nocapture

# 2. 重建节点
cargo build --workspace --release

# 3. 重启 devnet
./scripts/restart_validator.sh

# 4. 准备账户（如需扩充到 2400）
# 参考 bench 的 prefund/setup 流程

# 5. 跑 bench
cd bench && npx ts-node src/cowboy/bench.ts

# 期望结果：
# - avg_cycles_used_per_tx: 10000 (从 20000 降低)
# - sustained_mid80: ~2400 TPS (从 1200 翻倍)
# - avg_confirmed: ~2000+ TPS (从 911 大幅提升)
```

## 关键文件路径

- `execution/src/gas.rs:148-236` — GasCosts::default()，修改 base_cycles/transfer_cycles
- `bench/config_cowboy.json:11-13` — maxFloodWorkers/concurrency/cyclesLimit
- `bench/src/cowboy/flood.ts:37` — SYSTEM_LANE_CAPACITY 常量
- `types/src/constants.rs:48` — LANE_SYSTEM_CYCLES = 25_000_000（参考，不修改）
