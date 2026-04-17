# 计划：出块时间从 500ms 改为 1000ms

## Context

当前出块时间约 500ms，由两层机制共同控制：应用层的 `min_block_interval` 节流阀，以及共识层的 `LEADER_TIMEOUT`（leader 提案超时）。两者都设为 500ms，形成每 ~500ms 一个 block 的节奏。

`types/src/constants.rs` 中 `HEARTBEAT_TIMEOUT_BLOCKS = 100` 的注释已写明 "assuming 1 second per block"，说明协议常量本来就是按 1000ms 出块设计的。本次改动是将实际出块时间恢复到设计值。

---

## 改动清单（按优先级）

### 一、核心协议 — 必须改（影响出块行为）

| 文件 | 行号 | 当前值 | 改为 | 说明 |
|------|------|--------|------|------|
| `validator/src/main.rs` | 38 | `LEADER_TIMEOUT = 500ms` | `1000ms` | leader 提案超时，直接决定出块节奏 |
| `validator/src/main.rs` | 39 | `CERTIFICATION_TIMEOUT = 1s` | `2s` | 认证阶段超时，保持 2× leader_timeout 的比例 |
| `chain/src/application.rs` | 134 | `min_block_interval = 500ms` | `1000ms` | Application::new() 中的应用层节流 |
| `chain/src/application.rs` | 155 | `min_block_interval = 500ms` | `1000ms` | Application::with_mempool() |
| `chain/src/application.rs` | 267 | `min_block_interval = 500ms` | `1000ms` | Application::with_mempool_and_storage() |
| `types/src/constants.rs` | 21 | `SYNCHRONY_BOUND = 500` (ms) | `1000` | 时间戳未来允许漂移量，应与出块间隔对齐 |

### 二、测试正确性 — 必须改（否则 unclean-shutdown 测试逻辑破坏）

`chain/src/lib.rs` 中的 restart 压力测试，其注释明确说明：恢复超时 (leader + cert) 必须小于最短重启间隔。

| 文件 | 行号 | 当前值 | 改为 | 说明 |
|------|------|--------|------|------|
| `chain/src/lib.rs` | 861 | `leader_timeout = 250ms` | `500ms` | 保持 0.5× block_time 的比例 |
| `chain/src/lib.rs` | 862 | `certification_timeout = 500ms` | `1000ms` | 保持 1× block_time 的比例 |
| `chain/src/lib.rs` | 954 | 重启窗口 `1_100..2_000ms` | `2_200..4_000ms` | 必须大于总恢复时间(500+1000=1500ms) |
| `chain/src/lib.rs` | 855–860 | 注释中的数值 | 同步更新为新数值 | 维持注释与代码一致 |

### 三、注释精度更新 — 必须改（否则注释产生误导）

| 文件 | 行号 | 当前注释 | 改为 |
|------|------|----------|------|
| `chain/src/application.rs` | 60 | `"At ~2 blocks/sec, 1000 blocks ≈ sync every ~500 seconds"` | `"At ~1 block/sec, 1000 blocks ≈ sync every ~1000 seconds"` |
| `types/src/constants.rs` | 47 | `"2500 TPS at 500ms blocks"` | `"1250 TPS at 1000ms blocks"` |

### 四、Bench 配置 — 应该改（否则基准测试采样频率失准）

| 文件 | 字段 | 当前值 | 改为 | 说明 |
|------|------|--------|------|------|
| `bench/config_cowboy.json` | `blockPollIntervalMs` | `500` | `1000` | 保持每个 block 轮询一次 |

### 五、Bench 源码 — 应该改（硬编码值与新 block time 不匹配）

| 文件 | 行号 | 当前值 | 改为 | 说明 |
|------|------|--------|------|------|
| `bench/src/cowboy/blocks.ts` | 65 | `sleep(500)` | `sleep(1000)` | 暖身重试轮询间隔，应对齐 block time |
| `bench/src/cowboy/blocks.ts` | 124 | 告警阈值 `> 1200` ms | `> 2000` ms | 超时警告阈值，原值是 500ms × 2.4，新值取 1000ms × 2 |

### 六、脚本默认值 — 应该改（等待 tx 确认的默认秒数是基于 2 blocks/s 估算的）

| 文件 | 行号 | 变量 | 当前默认值 | 改为 | 说明 |
|------|------|------|-----------|------|------|
| `scripts/register_runner.sh` | 50 | `WAIT_TX` | `40`s | `80`s | 等待 funding tx 上链（约 40 blocks → 仍为 40 blocks） |
| `scripts/register_runner.sh` | 51 | `WAIT_REG` | `30`s | `60`s | 等待注册 tx 上链 |

### 七、Bench 工具 — 建议改（--block-ms 默认值）

| 文件 | 位置 | 当前值 | 改为 | 说明 |
|------|------|--------|------|------|
| `bench/src/fund-accounts.ts` | `--block-ms` 默认参数 | `500` | `1000` | fund-accounts 轮询确认间隔 |

### 八、示例脚本 — 建议改（E2E 脚本 sleep 值基于 2 blocks/s 假设）

`examples/token/start_all.sh`、`examples/multi_call/start_all.sh`、`examples/llm_chat/start_all.sh` 中的 `sleep 1/2/3/10` 等待 tx 确认的 sleep，整体按 2× 放大（`sleep 2/4/6/20`）。

---

## 不需要改的值（附原因）

| 常量/字段 | 当前值 | 原因 |
|-----------|--------|------|
| `NULLIFY_RETRY = 10s` | validator/main.rs:40 | 绝对时钟值，与 block time 无关 |
| `FETCH_TIMEOUT = 2s` | validator/main.rs:43 | 网络 RPC 超时，与 block time 无关 |
| `ACTIVITY_TIMEOUT = ViewDelta(256)` | validator/main.rs:41 | 以 view 为单位；1s×256=256s，设计合理 |
| `SKIP_TIMEOUT = ViewDelta(32)` | validator/main.rs:42 | 同上；1s×32=32s |
| `HEARTBEAT_TIMEOUT_BLOCKS = 100` | constants.rs:136 | 注释已写 "assuming 1 second per block"，改后恰好正确 |
| `DISPUTE_WINDOW_BLOCKS = 75` | constants.rs:139 | 语义为 75 个 block 的争议窗口，改后 = 75s（加强保护） |
| `DEFERRED_TX_MAX_AGE_BLOCKS = 1000` | constants.rs:129 | 语义为 1000 个 block，超时变长无负面影响 |
| `blockMonitorDurationSecs = 300` | bench/config_cowboy.json | 秒为单位，不受影响 |
| `floodDurationSecs = 90` | bench/config_cowboy.json | 秒为单位，不受影响 |
| `submissionIntervalMs = 200` | bench/config_cowboy.json | 发送速率控制，与 block time 无关 |
| `latencyTimeoutMs = 10000` | bench/config_cowboy.json | 10s 绝对超时，仍合理 |

---

## 验证方法

```bash
# 1. 编译确认无报错
cd /home/ubuntu/workspace/node
cargo build --workspace

# 2. 跑全量测试（重点关注 chain crate 的 unclean-shutdown 测试）
cargo test --workspace

# 3. 单独跑共识测试
cargo test -p cowboy-chain

# 4. 启动本地 devnet，观察实际出块间隔
./scripts/run_build.sh
./scripts/start_validator.sh
# 观察日志中 block height 的推进速度，应为 ~1 block/s

# 5. 可选：跑 bench 验证 blockPollIntervalMs 对齐
cd bench && npm run bench:all
```
