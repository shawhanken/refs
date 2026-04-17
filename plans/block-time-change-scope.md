# 评估：出块时间 500ms → 1000ms 的改动涉及面

## 结论先行

**此改动已在当前分支完成。** commit `f0bc514`（"Update performance parameters and sleep durations for improved stability"，2026-04-03）已将出块时间从 500ms 改为 1000ms。

---

## 已改动的范围（commit f0bc514）

### 1. 核心出块间隔 — `chain/src/application.rs`

| 位置 | 改动 |
|------|------|
| `Application::new()` L134 | `min_block_interval: Duration::from_millis(500)` → `1000` |
| `Application::with_mempool()` L155 | 同上 |
| `Application::with_mempool_and_storage()` L267 | 同上 |

`min_block_interval` 是提案者在上一个区块之后等待的最短时间，直接决定出块速率（2 blocks/s → 1 block/s）。

---

### 2. 时间戳容忍窗口 — `types/src/constants.rs`

| 常量 | 改动 | 含义 |
|------|------|------|
| `SYNCHRONY_BOUND` | 500 → 1000 ms | 区块时间戳相对当前时间可超前的最大值 |
| 注释（TPS） | 2500 TPS at 500ms → 1250 TPS at 1000ms | 最大 TPS 天花板减半 |

`SYNCHRONY_BOUND` 应与 `min_block_interval` 保持同量级，否则时间戳校验会误拒合法区块。

---

### 3. 共识超时参数 — `validator/src/main.rs`

| 常量 | 旧值 | 新值 | 含义 |
|------|------|------|------|
| `LEADER_TIMEOUT` | 500 ms | 1000 ms | 等待 leader 提案的超时 |
| `CERTIFICATION_TIMEOUT` | 1 s | 2 s | 等待认证完成的超时 |

这两个值需要与出块间隔匹配：`LEADER_TIMEOUT ≥ min_block_interval`，否则 leader 在出块前就会被判超时。

---

### 4. 测试时序 — `chain/src/lib.rs`

recovery 压力测试的所有时间窗口等比例翻倍：
- 随机重启间隔：1100–2000 ms → 2200–4000 ms
- 测试中使用的 `leader_timeout`: 250 ms → 500 ms
- 测试中使用的 `certification_timeout`: 500 ms → 1000 ms

注释也同步更新，保持比例关系说明的一致性。

---

### 5. Bench 脚本 / Examples 脚本

- `bench/src/cowboy/blocks.ts` — 轮询间隔 500ms → 1000ms
- `bench/src/fund-accounts.ts` — BLOCK_MS 默认值更新
- 多个 `examples/*/start_all.sh` — sleep 时长翻倍（3s→6s，10s→20s 等）

---

## 间接影响（依赖出块时间的"块数"常量）

这些常量未改，但其对应的实际时间因出块时间翻倍而翻倍：

| 常量 | 值 | 500ms 时 | 1000ms 时 |
|------|----|---------|---------|
| `HEARTBEAT_TIMEOUT_BLOCKS` = 100 | types/src/constants.rs | ~50 s | ~100 s |
| `DISPUTE_WINDOW_BLOCKS` = 75 | types/src/constants.rs | ~37.5 s | ~75 s |
| `DEFERRED_TX_MAX_AGE_BLOCKS` = 1000 | types/src/constants.rs | ~500 s | ~1000 s |
| `SYNC_INTERVAL_BLOCKS` = 1000 | chain/src/application.rs | ~500 s | ~1000 s |

其中 `HEARTBEAT_TIMEOUT_BLOCKS` 的注释已预先写为 "approximately 100 seconds, assuming 1 second per block"，与新配置完全对齐。其余常量的注释未特别说明时间假设，无需修改。

---

## 主要影响摘要

| 维度 | 影响 |
|------|------|
| 出块速率 | 2 blocks/s → 1 block/s |
| 最大 TPS 天花板 | 2500 → 1250（系统 lane 25M cycles ÷ 20k cycles/transfer ÷ 1s） |
| 单轮共识总时限 | LEADER(1s) + CERT(2s) = 3s（原 1.5s） |
| 最终性延迟（理论） | ~2 s → ~4 s |
| Runner 心跳超时 | ~50 s → ~100 s（块数不变，时间翻倍） |
| 争议窗口 | ~37.5 s → ~75 s |
| DB 同步周期 | ~500 s → ~1000 s（I/O 压力降低） |

---

## 未改动但值得关注的地方

1. **`DISPUTE_WINDOW_BLOCKS`**：时间由 ~37.5s 延长到 ~75s，这是有益的（runner 有更多时间提交结果），但若业务上有明确的 dispute 时间 SLA 需确认。
2. **`HEARTBEAT_TIMEOUT_BLOCKS`**：时间由 ~50s 延长到 ~100s，注释已对齐，但运营上需注意 runner 故障检测变慢。
3. **`README.md`**："~1 second block time with ~2 second finality" 文档已预先描述 1s 出块，与当前配置一致。

---

## 结论

改动涉及 **13 个文件**，覆盖：
- 出块间隔（核心）
- 共识超时（与出块间隔强耦合，必须同步调整）
- 时间戳校验窗口（安全约束，需与出块时间同量级）
- 测试时序（等比例缩放）
- 运维脚本轮询间隔

**此次 commit f0bc514 已完整覆盖所有必要改动，无遗漏。**
