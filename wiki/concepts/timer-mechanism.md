---
type: concept
tags: [timer, scheduler, cip-1, cip-5]
sources:
  - node/execution/src/pvm_host.rs
  - node/storage/src/speculative.rs
  - node/types/src/execution.rs
  - refs/cips/cip-5-timers.md
  - refs/cips/cip-1-actor-scheduler-v2.md
  - refs/cips/cip-1-actor-scheduler.md
last_updated: 2026-04-21
status: authoritative
---

# Timer 机制

Actor 通过 `schedule_timer(height, payload)` / `schedule_timer_ex(...)` host API 注册未来块高度触发的回调。CIP-5 已于 **2026-04-20 revision** 升级到一个**收费的、有 TTL 的、有 fee_payer 显式指定的**模型；CIP-1 v2 把"未来 GBA 拍卖"作为附加层定位。

> **CIP-5 revision 主要变化**：每次 fire 不再免费 —— 引入 `fee_payer` 预扣 + 退还（§6.3）；三路退出生命周期（natural fire / TTL expiry / insufficient-funds self-destruct，§5.4）；`LANE_TIMER_CYCLES` 与 `TIMER_GC_CYCLES` 双预算分离（§6.5）；`TimerConfig` 治理（§6.4）；新增 `SYS_CANCEL_TIMER` (48) / `SYS_UPDATE_TIMER_CONFIG` (49) / `SYS_EXTEND_TIMER` (50) 三个 SystemInstruction（已在代码中）。CIP-1 v2 对应同步更新：撤销 70-72 opcode 推荐（这些已在代码 48-50）；统一未来设计 = GBA 出价 + auction 选 winners + 永远走 fee_payer basefee。

---

## API（CIP-5 revision）

```python
# 简单模式（fee_payer 默认 actor 自己；gas_limit 默认 TimerConfig.max_cycles_per_fire = 550_000）
schedule_timer(
    target_height: int,       # 目标块高度 (> 当前)
    payload: bytes,           # 传给 callback 的 payload
) -> timer_id

# 完整模式
schedule_timer_ex(
    target_height: int,
    payload: bytes,
    fee_payer: Address?,       # 默认 = actor self；不能指向第三方（拒绝）
    gas_limit_per_fire: int?,  # 默认 TimerConfig.max_cycles_per_fire
    expires_at: int?,          # TTL；默认 current + TimerConfig.max_ttl_blocks (= 30d @ 1s)
) -> timer_id

# 取消 / 延长
cancel_timer(timer_id) -> None      # actor 自己持
extend_timer(timer_id, new_expires_at) -> None
```

调用立即扣 200 cycles + payload cells（**注册费**，从 tx_sender 付，**不是** timer.fee_payer），写入 timer 索引。

---

## 三路退出生命周期（CIP-5 §5.4）

每个 timer 必经其中之一：

1. **Natural fire** (§5.2/§6.3)：`height` 到达，`fee_payer` 余额够 `max_cost`，handler 跑（成功或 revert）；timer 移除
2. **Insufficient-funds self-destruct** (§5.4 path 2)：fire 时 `balance(fee_payer) < max_cost`，timer 不执行直接销毁；emit `TimerCancelledInsufficientFunds { timer_id, fee_payer, required, available }`，走 GC 预算（不占执行 lane）
3. **TTL expiry** (§5.4 path 3)：fire 时 `current_height > expires_at`，timer 不执行直接销毁；emit `TimerExpired { timer_id, expires_at, current_height }`，同样走 GC 预算
4. **Explicit cancellation**：actor 自己 `cancel_timer`，或 validator-set 通过 `SYS_CANCEL_TIMER` (opcode 48)，或通过 `SYS_EXTEND_TIMER` (opcode 50) 延 TTL

---

## 执行时机

**块内流程**（CIP-5 §5.1，**Tx-then-Timer** 已 codified）:
```
1. 执行所有用户 transactions (TX 阶段)
2. 取 get_timers_by_height(current); 按 §5.4 分类 (TTL expired / 余额不足 → 自毁；其他 → 预扣 + 入队)
3. 执行 deferred timer txs (FIFO within height bucket)
```

**关键**: Transactions **先于** Timers 执行 —— CIP-5 v1 / CIP-1 v1 §3 step 4 描述的 "Timer-then-Tx" 已被 CIP-5 revision §5.1 显式改为 "Tx-then-Timer"。CIP-1 v1 的 2026-04-15 amendment caveat 已被 CIP-5 native 化，不再是 amendment。

---

## Per-fire fee 模型（CIP-5 §6.3 —— 关键变化）

```
1. max_cost = gas_limit_per_fire × cycle_basefee
            + max_cells_per_fire × cell_basefee
2. if balance(fee_payer) < max_cost:
       → insufficient-funds self-destruct (path 2)，无任何执行
3. 否则 pre-charge max_cost from fee_payer
4. 执行 handler under budget
   - 成功：writeset commit
   - revert：writeset 丢弃；gas 仍计费（同普通 tx）
5. refund: actual_cost = actual_cycles × basefee + actual_cells × basefee
   credit(fee_payer, max_cost - actual_cost)
6. basefee 部分 burn；tip（如有）→ proposer
7. timer 移除
```

**这是 v1 → v2 的根本变化**：v1 称 timer "system-triggered, no explicit basefee or tip is charged"；revision 后明确**timer 不再免费**，需 `fee_payer` 显式有钱。

---

## 双预算（CIP-5 §6.5）

| 预算 | 默认 / 来源 | 作用 |
|---|---|---|
| `LANE_TIMER_CYCLES` | `8,888,890` cycles (`node/types/src/constants.rs`) | 执行 lane（path 1）；超额 timer 延到下块（带 bias 累积）|
| `TIMER_GC_CYCLES` | `TimerConfig.gc_cycles_per_block = 5_000_000` | GC lane（path 2 / 3）；隔离 expiry storm，不让其挤掉 live timer |

> CIP-1 v1 §3 命名 `TIMER_PROCESSING_BUDGET_CYCLES` 在 CIP-1 v2 §4 改名为 `LANE_TIMER_CYCLES` 与 CIP-5 §6.5 对齐。

---

## 新增 SystemInstruction（已在代码中）

| Opcode | 名称 | Sender | 作用 |
|---:|---|---|---|
| **48** | `SYS_CANCEL_TIMER { timer_id }` | `system_deployers` | 验证集 emergency cancel |
| **49** | `SYS_UPDATE_TIMER_CONFIG { config }` | `system_deployers` | 调 `TimerConfig` (TTL / per-fire caps / GC 预算) |
| **50** | `SYS_EXTEND_TIMER { timer_id, new_expires_at }` | `system_deployers` | Emergency 延 TTL（actor 失能时备援）|

**重要**：CIP-1 v2 §6 早先草稿曾推荐 70-72 给这三个，**已撤销** —— 这些指令已在代码 `node/types/src/execution.rs:525-534` 实装为 48/49/50，**不需要新 opcode 分配**。

---

## TimerConfig（治理可调，CIP-5 §6.4）

存于 `state:actor:0x06:kv:system:timer_config`（复用 BASEFEE_SYSTEM_ACTOR）：

```rust
struct TimerConfig {
    max_ttl_blocks:       u64,   // 默认 2_592_000 (~30d @ 1s)
    max_cycles_per_fire:  u64,   // 默认 550_000
    max_cells_per_fire:   u64,   // 默认 550_000
    max_timers_per_actor: u32,   // 默认 1_024
    gc_cycles_per_block:  u64,   // 默认 5_000_000
}
```

通过 `SYS_UPDATE_TIMER_CONFIG` (opcode 49) 治理修改；emit `timer_config.updated`。

---

## 跨 CIP timer fee_payer 约定

CIP-5 revision 后，所有用 timer 的 v2 协议必须显式说明 `fee_payer`：

| 用户 | fee_payer | 余额不足时 |
|---|---|---|
| CIP-9 v2 §12 PoR challenge timer | `STORAGE_MANAGER (0x0A)`（从 `POR_CHALLENGE_FEE_SHARE` 池补给）| Storage Manager 订阅 `TimerCancelledInsufficientFunds` → emit `PorChallengePaused`，挑战暂停到池补充 |
| CIP-16 v2 §5.10 reverify timer | `binding.owner` | Route Registry 订阅 `TimerCancelledInsufficientFunds` → 把 binding 转 `SUSPENDED, reason=INSUFFICIENT_TIMER_FUEL`（区别于 `INSUFFICIENT_REVERIFY_FEE`）|
| CIP-14 v2 §8 receipt prune | RECEIPT_REGISTRY 自管（系统循环，不依赖单 timer per receipt）| N/A (单全局 prune 循环) |

---

## 未来：GBA + Auction（CIP-1 v2 §2 unified design）

CIP-1 v1 的 GBA bidding agent 与 CIP-5 §9 的 auction 不是竞争，而是同一未来设计的两层：

| 层 | 组件 | 来源 |
|---|---|---|
| Bid 生成 | per-timer GBA contract 返回 `(bid, gas_limit_per_fire)` | CIP-1 v1 §4.2 |
| Auction 选 winner | 排序 `(bid + Bias(n)) / gas_limit_per_fire`；greedy fill 到 `LANE_TIMER_CYCLES`；VCG 或 first-price | CIP-5 §9.2-9.5 |
| Caps & fairness | `MAX_FIRES_PER_BLOCK` / `MAX_FIRES_PER_ACTOR` / 指数 bias 防饿死 | CIP-5 §9.4 |
| 底层 basefee | per-fire `fee_payer` 预扣 / 退还（auction-independent，已在 CIP-5 §6.3 生效）| CIP-5 §6.3 |

**Bid 是优先级层，basefee 永远独立支付**。CIP-5 §9.9 "Open question — Interaction with CIP-1 GBA" 由 CIP-1 v2 §2 显式关闭：GBA 出价；auction 选 winners；basefee 独立。

未来激活时降级 case：现有 timer 默认 `bid = 0` + 依赖 bias 累积排队。

---

## 源文档冲突 / 漂移

- 块内顺序：CIP-5 §5.1 revision 已 native 化 Tx-then-Timer；v1 / CIP-1 v1 §3 step 4 反向描述被 supersede
- CIP-1 v1 §3 `TIMER_PROCESSING_BUDGET_CYCLES` → CIP-1 v2 §4 / CIP-5 §6.5 改名 `LANE_TIMER_CYCLES`（值不变）
- CIP-1 v2 §6 早期草稿推荐 opcode 70-72 给 `SYS_CANCEL_TIMER` 等，**已撤销** —— 这三个指令已在代码 48-50

---

## 相关

- [[actor-model]] — 同步/异步调度
- [[continuation]] — Timer 回调作为 Continuation resume 路径
- [[speculative-execution]] — 块内执行顺序
- [[basefee]] — fee_payer 模型与 basefee 的关系
- [[../parameters]] — 预算常量
- [[../drift]] — Tx-then-Timer 修订状态

## Sources

- `refs/cips/cip-5-timers.md` — revised 2026-04-20（fee_payer §6.3、三路退出 §5.4、双预算 §6.5、TimerConfig §6.4）
- `refs/cips/cip-1-actor-scheduler-v2.md` — v2 alignment（Tx-then-Timer codified、撤销 70-72 推荐、unified GBA + auction）
- `refs/cips/cip-1-actor-scheduler.md` — v1 原文保留参考
- `node/execution/src/pvm_host.rs:1489-1652` — schedule_timer / schedule_timer_ex / extend_timer / cancel_timer 实装
- `node/types/src/execution.rs:525-534` — opcodes 48/49/50 已实装
- `node/storage/src/speculative.rs:152-475` — 块生命周期 Tx-then-Timer
