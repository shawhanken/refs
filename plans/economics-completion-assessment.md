# Cowboy 经济系统真实完成度评估报告

**基准**：CIP-1/2/3/4/20/21/22 + 技术白皮书（2026-03-21）
**评估范围**：node（`/home/ubuntu/workspace/node`） + runner（`/home/ubuntu/workspace/runner`）
**评估时间**：2026-03-28（已含本次 gas/fee 修复后的状态）

---

## 一、总体完成度（摘要）

| 子系统 | 完成度 | 状态 |
|--------|--------|------|
| CIP-3 双维 Gas 常量对齐 | 75% | ⚠️ 多项偏差 |
| CIP-3 Basefee 机制 | 70% | ⚠️ 持久化有缺口 |
| CIP-3 区块目标/Lane 分区 | 20% | ❌ Lane 未实现 |
| CIP-3 交易内在成本 | 80% | ⚠️ 存储写入 Cells 固定值 |
| CIP-2 Runner 注册/质押 | 45% | ❌ 注册阻塞，质押验证缺失 |
| CIP-2 Job 定价/Escrow | 65% | ⚠️ Escrow 已实现，结算不完整 |
| CIP-2 验证模式 | 60% | ⚠️ MajorityVote/Structured 可用，EconomicBond/TEE/Custom 未完成 |
| CIP-2 结算分配 | 55% | ⚠️ 89/10/1 分配逻辑存在，但 burn/tip 最终去向有缺口 |
| CIP-20 Token 系统 | 85% | ✅ 基本完整 |
| CIP-1 定时器经济 | 30% | ❌ GBA、存款模型、Lane 预算均未实现 |
| 状态租金系统 | 0% | ❌ 完全未实现 |
| 通胀/区块奖励 | 0% | ❌ 完全未实现 |

---

## 二、CIP-3 Fee Model 详细差距

### 2.1 Gas 常量偏差（已知错误 vs 规范）

| 常量 | 规范值 | 当前实现值 | 位置 | 严重性 |
|------|--------|-----------|------|--------|
| `MAILBOX_SEND_BASE_CYCLES` | 80 | **500** | `gas.rs:266` | MEDIUM |
| `SET_TIMER_BASE_CYCLES` | 200 | **1,000** | `gas.rs:267` | MEDIUM |
| `CANCEL_TIMER_CYCLES` | 200 | **500** | `gas.rs:268` | MEDIUM |
| `storage_write_cells` | `key.len()+val.len()` (动态) | **1,000**（固定） | `gas.rs:166` | HIGH |
| `entitlement_revoke_cells` | 100 | **200** | `gas.rs:222` | LOW |
| `entitlement_delegate_cells` | 300 | **500** | `gas.rs:224` | LOW |
| `storage_read_cells` | 0 | **50** | `gas.rs:164` | LOW |

**最严重**：`storage_write_cells` 应为动态（实际 key + value 字节数），当前固定 1,000 cells，
导致小写入过贵、大写入（>1KB）过便宜，与 CIP-3 §2.2.2 冲突。

### 2.2 区块目标与 Lane 分区

**规范（CIP-3 §2.4）**：
- 总 Cycle 目标 T_c = 10,000,000 cycles/block
- Lane 分区：System 5% / Timer 20% / Runner 25% / User 50%
- Cell 目标 T_b = 500,000 cells/block ✓

**当前实现**：
- `BLOCK_CYCLES_TARGET = 5_000_000`（`basefee.rs`）—— 仅为规范值 50%
- **完全没有 Lane 分区**：所有交易共享同一 Cycle 池
- 后果：Basefee 调节曲线基准偏差，利用率计算错误

### 2.3 Basefee 持久化（HIGH GAP）

**已实现**：
- `DualBasefee::update()` 计算正确（EIP-1559 公式 ✓）
- `set_basefee()` / `take_block_fees()` 在 engine 中可用
- `prepare_block_basefee()` / `finalize_block_basefee()` 在 `transaction_executor_impl.rs`

**缺口**：
- `process_block.rs` 中 **`TODO: burn/tip distribution`** 仍未实现
- 区块结束后 burn 金额（累积在 `block_burn: u128`）**没有被实际销毁**（写入 Address::ZERO）
- Tip 金额（`block_tip: u128`）**没有被转给提案者**
- Basefee 状态在重启后是否正确加载需验证

**文件**：`storage/src/process_block.rs`（`TODO` 注释处）

### 2.4 延迟交易（Deferred Tx）Basefee 验证

- `transaction.rs:43` 有 TODO：延迟交易不重新验证当前 basefee
- 若原始交易支付的 basefee < 执行块的 basefee，等于补贴了延迟执行

---

## 三、CIP-2 Off-chain Compute 详细差距

### 3.1 Runner 注册（node 端 ✓，runner 端 ❌）

**node 端实现（`execution/src/runner/registry.rs`）**：完整，含签名验证、最小质押检查

**runner 端（`runner/crates/runner-node/src/registration.rs`）**：
- `is_registered()` **硬编码返回 false**（line 25-27）
- 注册交易构建未完成，运行时报错退出（line 63）
- 无链上质押余额验证
- 运行时强制绕过，继续运行但未注册

### 3.2 Runner 选择器 MIN_STAKE 常量 Bug（runner 端）

**文件**：`runner/crates/job-dispatcher/src/selection.rs:211`
```rust
const MIN_STAKE_WEIGHT_BASE: u128 = 10_000_000_000_000_000_000_000; // 声称 10,000 CBY
// 实际：1e21，但正确值应为 10_000 × 10^18 = 1e22（差 10 倍！）
```
- 导致所有 runner 权重计算错误（几乎全部 weight = 0 或 1）
- VRF 选择退化为均匀随机，Sybil 抗性完全失效

### 3.3 结算与支付流程（最关键缺口）

**node 端已实现**：
- Escrow 锁定（`dispatcher.rs`：job_submit 时从 submitter 扣款到 dispatcher）✓
- 89/10/1 分配计算（`verifier.rs`）✓
- Runner 支付（`verifier.rs`：consensus_runners 各得 per_runner）✓
- Burn → Address::ZERO ✓
- Treasury → `SystemActorAddresses::treasury()` ✓

**runner 端缺口**：
- **无实际资费计算**：`ResourceUsage`（input_tokens/output_tokens/wall_time）被收集但**从不与 RateCard 做乘法得到实际费用**
- **无超额退款**：`actual_cost < max_price` 的情况从不退款给 submitter
- **无超时惩罚执行**：超时后 node 端扣 reputation，但无对应链上 slash

### 3.4 Commit-Reveal 协议完整性

**node 端（`verifier.rs`）**：
- C11 Commit 阶段：存储 `keccak256(commitment)`（但 commitment 字段含义混用）
- Reveal 阶段：验证 commitment hash 匹配 ✓
- 但：单 runner（Mode::None）**跳过 commit 阶段**，合理 ✓

**runner 端**：
- 提交 commitment（Phase 1）✓
- 提交 reveal（Phase 2）✓
- 但 salt 从不被 node 验证，commit-reveal 绑定不完整

### 3.5 验证模式完成度

| 模式 | node 端 | runner 端 | 差距 |
|------|---------|-----------|------|
| None | ✓ | ✓ | — |
| MajorityVote | ✓ | ✓ | — |
| StructuredMatch | ✓（字段比对）| ✓ | JSON Schema 验证仍是 TODO |
| EconomicBond | ❌ 无实现 | ❌ TODO | 完全缺失 |
| Deterministic | N/A | ⚠️ TEE TODO | — |
| SemanticSimilarity | ❌ 无实现 | ✓（embedding）| node 端不支持 |

### 3.6 Challenge 机制

- **规范**：15 分钟挑战窗口，100 CBY 保证金，Proven dishonesty → slash
- **实现**：`dispute_window_blocks` 字段存在于 `VerificationConfig` 类型中
- **实际**：**完全未实现**，无任何 challenge 处理逻辑

### 3.7 Runner 声誉更新

- 超时惩罚（-5）：node 端 `process_job_timeouts()` ✓
- 成功/失败后 reputation 更新：**未实现**（验证成功后不加分，验证失败不扣分）

---

## 四、CIP-1 定时器经济（大量缺失）

**已实现**：
- 基本定时器调度（`set_timer` / `cancel_timer` 主机函数）
- Max 1,024 timers per actor 限制（`MAX_TIMERS_PER_ACTOR`）
- 基本 gas 充值（`SET_TIMER_BASE_CYCLES`, `CANCEL_TIMER_CYCLES`）

**完全未实现**：
- **GBA（Gas Bidding Agent）**：定时器触发前调用 read-only handler 询价
- **定时器存款模型**：第 n 个定时器渐进押金，防止 DoS
- **Timer Lane 预算**（2M cycles/block）：无 Lane 分区
- **同块发射指数加价**（surge pricing）
- **Timer Basefee** 独立调节

---

## 五、状态租金系统（完全未实现）

规范（CIP-4 / 白皮书 §3.2）要求：
- 每个 Actor 1 MiB 基础存储配额
- 按 epoch 自动扣租金
- 宽限期 7 epoch → 警告期 3 epoch → 驱逐
- 存款累进

**当前状态**：完全没有任何租金代码，`storage/src/` 无相关逻辑。

---

## 六、通胀/区块奖励（完全未实现）

规范（白皮书 §8）：
- 年通胀 8%/6%/4%/3%/2%（逐年递减）
- 每 Epoch（3,600 blocks）按质押比例分配区块奖励
- Proposer bonus = 当前块所有 tips

**当前状态**：无任何通胀计算、无验证者奖励分配、tips 累积（`block_tip`）但不发放。

---

## 七、CIP-20 Token 系统（相对完整）

**已实现**（~85%）：
- 创建、转账、授权、mint/burn ✓
- Transfer hook 50k cycles cap ✓
- Reentrancy guard ✓
- Freeze/unfreeze/set hook ✓
- Batch transfer ✓

**缺口**：
- `token_info()` / `token_balance_of()` 等查询的 gas（100/200 cycles）是否收费未确认
- Hook 的 `max_cells` cap 仅有 cycles cap，cells cap 未独立实现
- Token Hook `on_transfer()` vs `can_transfer()` 接口规范对齐未验证

---

## 八、优先级排序（建议修复顺序）

### P0 — 阻塞性（影响基本运行）
1. **Burn/Tip 最终分配**：`process_block.rs` 的 TODO，块结束后真正销毁/转账
2. **Runner 注册解阻**：`runner/crates/runner-node/src/registration.rs` is_registered stub

### P1 — 经济模型正确性（影响 tokenomics）
3. **BLOCK_CYCLES_TARGET**：5M → 10M（与 CIP-3 对齐）
4. **storage_write_cells 动态化**：固定 1,000 → `key.len() + val.len()`
5. **MIN_STAKE_WEIGHT_BASE 修复**：runner 端 selection.rs 1e21 → 1e22
6. **Mailbox/Timer gas 常量对齐**：500/1000/500 → 80/200/200

### P2 — 功能完整性
7. **Gas Lane 分区**：System/Timer/Runner/User 独立 Cycle 池（重大架构）
8. **GBA 定时器支付模型**（CIP-1）
9. **EconomicBond 验证模式**
10. **Deferred Tx basefee 重验证**

### P3 — 长期/非阻塞
11. **状态租金系统**（CIP-4）
12. **通胀/区块奖励**（白皮书 §8）
13. **Challenge 机制**（CIP-2 §8.4）
14. **Runner ResourceUsage × RateCard 实际计费**
15. **超额退款逻辑**

---

## 九、关键文件速查

| 差距 | 文件路径 |
|------|---------|
| Burn/Tip 分配 TODO | `node/storage/src/process_block.rs` |
| Block Cycles Target | `node/execution/src/basefee.rs` |
| storage_write_cells | `node/execution/src/gas.rs:166` |
| Mailbox/Timer gas | `node/execution/src/gas.rs:266-268` |
| Runner 注册阻塞 | `runner/crates/runner-node/src/registration.rs:63` |
| MIN_STAKE bug | `runner/crates/job-dispatcher/src/selection.rs:211` |
| EconomicBond TODO | `runner/crates/result-verifier/src/verifier.rs:118` |
| Deferred basefee | `node/execution/src/execution/transaction.rs:43` |
| JSON Schema verify | `node/execution/src/runner/verifier.rs:518` |
