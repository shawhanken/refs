# Runner Economics & Delegation — Design Guide

> 设计文档，非完整实现方案。目标：为实现者提供清晰的结构性指引。

---

## 核心亮点：Compute as a Segmented Yield Primitive

Cowboy 不是又一条 PoS 链把委托做成"选个验证者分红"。它的区别在于：

**Runner 是异构的。** 每个 runner 有不同的硬件（GPU 型号）、能力（TEE、MCP）、支持的模型（Llama-405B vs GPT-4o），用 Entitlement 声明。Delegation 不是选一个同质化节点分润——你是在**下注一个具体的计算细分市场的需求曲线**。

这意味着：
- Runner A（TEE + H100 + Llama-405B）和 Runner B（CPU-only + 通用计算）的收益率由完全不同的需求端驱动
- 委托者的选择不是"谁佣金低"，而是"哪个计算细分市场有持续需求"
- 上层可以构建按 entitlement class 分池的流动质押产品（**协议不提供，是 actor-layer 的事**）

**数据底座**：协议在每次结算时强制 emit `JobSettled`（job_id, entitlement_class, total_settlement, runner_share, ...）和 `DelegatorPayout`（runner, delegator, amount）结构化事件。indexer 把它们聚合成 per-entitlement-class 的需求/收益率序列——上层产品（compute index、forward、ETF）的全部输入都来自这两个事件。没有结构化事件的 delegation 是没法做衍生品的。

**这不是共识分红，是计算市场的资本配置。**

---

## 1. Runner 收益模型

### 1.1 收入来源

Runner 的唯一收入来源是 **job settlement**。没有通胀出块奖励。

```
JobSpec.max_price + JobSpec.tip   ← 这里的 tip 不是链上交易 tip
    ├── 89% → 共识 runner 均分（governable via 0x09）
    ├── 10% → 销毁（Address::ZERO，通缩）
    └──  1% → 国库（0x08）
```

**两种 tip 必须分清**（很容易混淆）：

| Tip 类型 | 出处 | 流向 |
|---------|------|------|
| **链上交易 tip** | `Transaction.max_priority_fee_per_*` → `compute_tx_fees` | Block proposer / validator |
| **Job tip** | `JobSpec.tip` → `verifier.rs:349` `total_settlement` | 共识 runner（按 89/10/1 分账）|

提交一笔 job 的链上交易，submitter 既付 basefee（burn）+ priority fee（→proposer），又在 JobSpec 里设 max_price + tip（→runners）。两条独立的支付通路。

**双重通缩特性。** 一次 job 提交对 CBY 产生两次通缩压力：
- 链上交易付的 basefee → 100% burn（EIP-1559 标准）
- Job settlement 的 10% → burn

高频 compute 经济天然 deflationary——这是和 PoS 链通胀模型的本质区别。

**纯需求驱动。** Runner 不因"在线"而获得奖励，只因"完成了有人愿意付费的计算任务"而获得收入。闲置 runner 的持有成本为正（质押锁定 + 硬件折旧），倒逼资本向真实需求流动。

### 1.2 定价：Rate Card

每个 runner 自主声明多维价格：

| 维度 | 单位 | 说明 |
|------|------|------|
| `compute_second` | attoCBY/秒 | 通用计算 |
| `llm_input_token` | attoCBY/token | LLM 推理输入 |
| `llm_output_token` | attoCBY/token | LLM 推理输出 |
| `http_request_base` | attoCBY/请求 | HTTP 调用 |
| `mcp_call_base` | attoCBY/调用 | MCP 工具调用 |
| `memory_mb` | attoCBY/MB | 内存 |

Dispatcher 在选 runner 时用 `compute_second <= job.max_price` 做价格过滤。自由市场定价，不是协议定价。

### 1.3 引入 Delegation 后的分账

```
per_runner_share = runner_share_total / num_consensus_runners

effective_stake  = self_stake + delegated_active
delegator_pool   = per_runner_share × delegated_active / effective_stake

runner_commission       = delegator_pool × commission_bps / 10000
runner_payout           = (per_runner_share - delegator_pool) + runner_commission
delegator_distributable = delegator_pool - runner_commission
                        = delegator_pool × (10000 - commission_bps) / 10000

for each Active tranche T of this runner:
    T.delegator gets:  delegator_distributable × T.amount / delegated_active
```

**整数余数路由**（共识层细节，必须一致，否则节点 fork）：
- runner-vs-delegator 拆分的余数 → runner
- per-tranche 分配的余数 → 最小 `tranche_id` 的 Active tranche

**佣金 epoch 延迟生效。** Runner 调整 commission 时写 `pending_commission_bps + pending_effective_epoch = current_epoch + 1`，旧值在当前 epoch 的所有 settlement 中仍然权威。新 epoch 的第一次 settlement 懒提升 pending → current 并清空。委托者有整整一个 epoch 反应时间。

> Open question: CIP-13 的 "epoch" 定义留空。代码中已存在 `STORAGE_EPOCH_BLOCKS = 7200`（CIP-9 存储结算用，~1 hour）。建议复用同一 epoch 边界，避免引入第二个时钟。

---

## 2. 工作量衡量

### 2.1 链上 Gas：双计量 EIP-1559

Cowboy 的链上 gas 模型将 **计算** 和 **存储** 拆为两个独立维度，各自运行 EIP-1559 动态定价：

| 维度 | 单位 | Target | 最大单通道 | 说明 |
|------|------|--------|-----------|------|
| Cycles | attoCBY/cycle | 20M/block | 40M (System lane) | 计算消耗 |
| Cells | attoDBY/cell | 4M/block | — | 存储消耗 |

**EIP-1559 更新公式（每 block 独立应用于两个维度）：**

```
delta = basefee × |used - target| / target / 96
delta = min(delta, basefee / 96)    // 上限 ±1.042%/block
new_basefee = clamp(old ± delta, MIN_BASEFEE, MAX_BASEFEE)
```

ALPHA=96 的校准逻辑：Cowboy 是 1 秒出块。Ethereum 的 ALPHA=8 对应 12 秒出块，(1+1/8)^1 远大于 Ethereum 每秒的实际调整率。校准到 96 使得 `(1+1/96)^12 ≈ 1.13 ≈ Ethereum 的 12 秒周期调整幅度`。

**四通道隔离（Gas Lanes）：**

```
Block 硬上限 80M cycles = 4× target
├── System:  40M (50%)  — settlement、注册、治理
├── User:    22M (28%)  — 转账、actor 调用
├── Runner:   9M (11%)  — 结果提交、心跳
└── Timer:    9M (11%)  — 定时器触发
```

通道隔离确保 runner 操作不会被用户 spam 饿死，反之亦然。

### 2.2 链下工作量

Job 的链下计算工作量不由链上 gas 衡量。链上只看到 `max_price + tip` 和 `ResourceBounds`（wall time、内存、token 数量的上限）。实际执行发生在 runner 的物理机器上，链上验证的是**结果一致性**，不是执行过程。

**这是 Cowboy 与 Optimistic Rollup / zkVM 的范式差异：**

| 范式 | 验证方式 | 成本 | 信任假设 |
|------|---------|------|---------|
| Optimistic | fraud proof re-execution | 慢（挑战期）| 至少一个诚实挑战者 |
| zkVM | 零知识证明 | 证明生成贵 | 密码学 |
| **Cowboy** | 多 runner 经济共识 + 结构化字段比对 | 实时 | 大多数 runner 诚实 + 质押兜底 |

链上不重放计算、不验证 zk 证明。**惩罚（slash）的触发完全来自 runner 互相比对**——这是 verification mode 设计的根。

### 2.3 Liveness 是隐式工作量

除了"完成任务"这种显式工作，runner 必须维持的**在线状态**也被协议衡量并影响收入：

```
Heartbeat:    每 < 100 blocks 必须发一次 (HEARTBEAT_TIMEOUT_BLOCKS)
              漏发 → health: Healthy → Unhealthy → 不再被 VRF 选中

Reputation:   注册时 = 50；slash 后归零（如果 stake 跌破 MIN_STAKE）
              超时不交付一次 → -5 (TIMEOUT_PENALTY)
              连续 3 次 (MAX_JOB_RETRIES) 未交付 → 任务 Failed，剩余被重选
              reputation = 0 → 永久排除出选择池
```

**机会成本**才是真正的"liveness 罚款"——掉线期间无收入，质押锁定不变。这比硬性扣款更有效，且不需要复杂的 inflation reward 机制。

---

## 3. 质押与惩罚

### 3.1 质押要求

```
required_stake >= max(10,000 CBY, max_job_value × 1.5)
```

质押的本质：runner 在说"我的 max_job_value 是 X CBY"，协议要求它锁定 1.5X 作为担保。质押不是一个固定数字——它与 runner 愿意接的最大单笔任务价值挂钩。

引入 Delegation 后：
```
effective_stake = self_stake + delegated_active
max_job_value ≤ effective_stake / 1.5

约束：self_stake >= effective_stake × 10%（runner 必须有 skin in the game）
```

### 3.2 VRF 选中权重

```
weight(stake) = floor(log2(stake / min_stake + 1)) + 1
```

**log2 压缩是反集中的核心机制。** 10 万 CBY 质押的 runner 权重约 4，100 万 CBY 的权重约 7——只有 1.75 倍，不是 100 倍。这使得 mega-delegation 有递减收益，天然抑制垄断。

### 3.3 验证与惩罚触发

5 种验证模式决定何时触发 slash：

| 模式 | 适用场景 | Slash 条件 |
|------|---------|-----------|
| `None` | 单 runner，信任结果 | 不罚 |
| `EconomicBond` | 单 runner，质押担保 | 质押兜底，不主动罚 |
| `MajorityVote` | 多 runner，投票共识 | 少数派结果的 runner |
| `StructuredMatch` | 多 runner，JSON Schema 验证 | 不符合 schema 或少数派的 runner |
| `Deterministic` | TEE 环境，字节一致 | 结果不一致的 runner |

**多 runner 任务用 commit-reveal 两阶段：**
- Commit 窗口（timeout 的 60%）：提交 `keccak256(result ‖ runner_address ‖ salt)`
- Reveal 窗口（40%）：揭示原文，验证 hash 匹配

### 3.4 Slash 路由

```
slash_amount = min(requested_slash, runner.stake)  // 现有逻辑：capped at stake

罚没资金：50% → 国库，50% → 销毁
若罚后 stake < 10,000 CBY → reputation = 0 → 从选择池中移除
```

### 3.5 引入 Delegation 后的 Slash 级联

```
slash_runner_with_delegation(runner, amount, current_block):
    slashable_base = self_stake + Σ(T.amount for T if is_slashable(T, current_block))

    self_slash       = amount × self_stake / slashable_base    // 无上限，全额承担
    delegation_slash = amount × delegated_slashable / slashable_base
    delegation_slash = min(delegation_slash, per_epoch_cap)    // 委托者每 epoch 最多 5%

    for T in slashable_tranches:
        T_slash = floor(delegation_slash × T.amount / delegated_slashable)
        T.amount -= T_slash
        if T.amount == 0:
            delete T                                            // ← 必须，否则成孤儿
            decrement summary.active_tranche_count (if T was Active)
            if summary.active_tranche_count → 0:
                decrement DelegationTotals.delegator_count
                delete summary key
        if T was Active:
            DelegationTotals.total_active -= T_slash
            summary.active_amount -= T_slash
```

**设计要点：**
- **Self-stake 无上限罚没** — 运营者永远承担最重惩罚
- **委托者 per-epoch 5% 上限** — 被动资本有可预测的最大损失
- **Unbonding 中但未到期的 tranche 仍可被罚** — 防止 slash-and-run
- **到期后的 tranche 不可被罚** — `is_slashable` 是 `(status, claimable_at, current_block)` 的纯函数，无需状态转换
- **超出 cap 的部分不延期** — 不写跨 epoch 的"slash 债务"，避免攻击面；只 emit `DelegationSlashCapped` 事件让外部观察
- **整数 floor 一律向下** — 永远 under-slash，符合"never over-slash under ambiguity"原则

---

## 4. Delegation 机制

### 4.1 设计原则

**协议只做最小钩子。** 注册、分账、罚没级联、解绑——仅此四件事。池子、份额代币、收益产品是第三方 actor 的事。

**无状态转换队列。** 早期草案有 `unbonding_queue` + end-of-block pass，引入了溢出风险（block 预算不够时 tranche 会卡在 Unbonding 超过承诺时间）。最终设计移除了所有队列：claimable 和 slashable 都是 block height 的纯函数，在查询时计算，不需要任何定时任务。

### 4.2 Tranche 模型

每次 delegate/top-up 创建新 tranche（不修改已有 tranche），每个 tranche 是独立记账单元：

```
DelegationTranche {
    delegator, runner, tranche_id,
    amount,                          // 当前余额（罚没后会减少）
    status: Active | Unbonding,
    claimable_at: Option<block_height>  // Unbonding 时有值
}
```

**为什么不是 per-(runner, delegator) 单条记录？** 因为部分解绑会产生一个 Active 残余 + 一个 Unbonding 部分，两者有不同的金额、时间戳、slash 状态。Tranche 模型让所有记账天然正确。

### 4.3 五条指令

| 指令 | 发送者 | 核心逻辑 |
|------|--------|---------|
| `UpdateDelegationConfig` (40) | Runner | 开启委托、设佣金/上限/门槛；佣金 epoch 延迟 |
| `DelegateStake` (41) | Delegator | 锁 CBY → 新 Active tranche |
| `IncreaseDelegation` (42) | Delegator | 追加 → 新 Active tranche（跳过 delegator_count 检查）|
| `UndelegateStake` (43) | Delegator | FIFO 消耗 Active tranche → Unbonding，可 split |
| `ClaimUnbonded` (44) | Delegator | 到期 tranche → 取回 CBY，删除记录 |

### 4.4 缓存策略

避免每次 dispatch/settlement 迭代全部 tranche：

```
DelegationTotals (per runner):
    total_active: u64       // VRF 权重、max_job_value、settlement 分账都读这个
    delegator_count: u32    // 用于 MAX_DELEGATORS_PER_RUNNER 检查

DelegationDelegatorSummary (per runner×delegator):
    active_tranche_count: u32   // 用于 MAX_ACTIVE_TRANCHES_PER_DELEGATOR 检查
    active_amount: u64          // 用于 UndelegateStake 的 dust 检查
```

Slashable base 不缓存（依赖 block height，且 slash 路径本身就要遍历 tranche）。

### 4.5 Gas 上界分析

最差情况：200 delegators × 8 tranches = 1,600 tranches/runner。5 个共识 runner 的 settlement 写 8,000 次余额。System lane 预算 40M cycles，远超所需。

### 4.6 Runner 退出

`RunnerDeregister` 对所有 Active tranche 强制发起 Unbonding（写 `claimable_at = now + 7200 blocks`）。不需要委托者配合，不需要队列。委托者在到期后自行 claim。

---

## 架构总览

```
                    ┌─────────────────────────────────────────────┐
                    │              Job Submitter                   │
                    │  pays max_price + tip, declares entitlements │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │           Dispatcher (0x02)                  │
                    │  VRF select: weight = log2(eff_stake/min+1) │
                    │  filter: price, entitlement, health, stake  │
                    │  escrow: max_price + tip                    │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │         Off-chain Execution                  │
                    │  runners execute, commit-reveal results      │
                    └──────────────────┬──────────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────────┐
                    │         Verifier (0x03)                      │
                    │  consensus check (5 modes)                   │
                    │  settlement split: 89 / 10 / 1               │
                    │  ┌─────────────────────────────────────┐    │
                    │  │ With Delegation:                     │    │
                    │  │  runner_payout = self_portion         │    │
                    │  │                + commission           │    │
                    │  │  delegator_i   = pro_rata(tranche_i) │    │
                    │  └─────────────────────────────────────┘    │
                    │  slash: cascade to self + slashable tranches │
                    │  emit: JobSettled, DelegatorPayout (events)  │
                    └─────────────────────────────────────────────┘

              ┌──────────────┐          ┌──────────────┐
              │  EIP-1559    │          │  Entitlement  │
              │  Dual Basefee│          │  System       │
              │  (cycles +   │          │  (manifest    │
              │   cells,     │          │   gate →      │
              │   4 lanes)   │          │   runner      │
              │              │          │   matching →  │
              │  链上 gas     │          │   param check)│
              └──────────────┘          └──────────────┘

                    ┌─────────────────────────────────────────────┐
                    │     Third-party Actor Layer (aspirational)   │
                    │  消费 JobSettled / DelegatorPayout 事件:       │
                    │   • stCBY 流动质押池                           │
                    │   • per-entitlement compute index            │
                    │   • compute forward contracts                │
                    │   • fleet management vaults                  │
                    │  （协议不实现，存在的只是事件 + delegation 原语） │
                    └─────────────────────────────────────────────┘
```

---

## 关键设计约束速查

| 约束 | 值 | 来源 |
|------|-----|------|
| 最低质押 | 10,000 CBY | `runner/src/types.rs:8` |
| 质押/job 乘数 | 1.5× | `runner/src/types.rs:10-12` |
| 最低自身质押 | effective_stake × 10% | CIP-13 §4.2 |
| Settlement 分成 | 89/10/1 (可治理) | `verifier.rs:334-434` |
| Slash 路由 | 50% treasury + 50% burn | `verifier.rs:72-74` |
| 委托者 slash 上限 | 5%/epoch | CIP-13 §3.6 |
| 解绑期 | 7,200 blocks (~24h) | CIP-13 §4.1 |
| VRF 权重 | log2(stake/min+1)+1 | `dispatcher.rs:31-37` |
| 心跳超时 | 100 blocks | `constants.rs:188` |
| Max delegators/runner | 200 | CIP-13 §4.2 |
| Max tranches/delegator/runner | 8 | CIP-13 §4.2 |
| 最低佣金 | 5% (500 bps) | CIP-13 §4.4 |
| Basefee ALPHA | 96 (1s block 校准) | `constants.rs:78` |
| Block cycles target | 20M | `constants.rs:46` |
