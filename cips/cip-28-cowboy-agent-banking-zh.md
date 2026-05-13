# CIP-28：Cowboy Agent Banking

- **状态**：Draft
- **日期**：2026-05-12
- **覆盖范围**：BankActor 系统 actor、卡数据模型、指令集、Gas 扣费路径、策略三件套、多银行 + 法币桥、Roadmap 与兼容性
- **不在范围**：链上 KYC、卡多 holder、协议级 paymaster 抽象、卡间内部转账原语

---

## 0. 摘要

把"持有 gas 资金 + 风控规则 + 合规手柄"从普通 actor 地址里解耦出来，做成第一公民的"银行账户"原语。新增系统 actor `BankActor (0x0D)`：

- **卡 = 一张物理银行卡的链上对应物**：确定性派生 20 字节地址，可持有多 token 余额（vault 模式），有过期/续卡、限额白名单、冻结、所有权迁移
- **agent = 持卡人**，但**owner = 监护人**（早期 = 用户，后期可移交给 agent 自己）；权责分离
- **gas 扣费第三条路径**：tx 的 `fee_payer_override` 指向卡地址即触发 BankActor 校验流，与现行 actor-pays / owner-pays 共存
- **合规边界唯一化**：Cowboy 链上其它一切（actor / token / session / cbss）不必合规，合规手柄集中在 BankActor + 各 bank operator + off-chain gateway
- **可融资叙事**："Agent 时代每个 agent 都需要 banking account；传统银行不支持；我们做"

7 节正文，定义到可直接进入 implementation plan 的颗粒度。

---

## 1. 架构总览 + 系统 actor 位置

### 1.1 定位

**Cowboy Agent Banking** 是一个新的系统 actor `BankActor`，地址 `0x0000…000D`。它承担四件事：

> **协议 / 银行 两层**：本 CIP 定义的"协议"是 Cowboy Agent Banking（= BankActor 原语 + 卡的派生地址规则）；其上 genesis 部署的第一家"银行"是 **Cowboy Banking**（`bank_id = 1`）。后者只是前者的第一个实例，类似 Visa（网络）vs Chase（发卡行）的关系。

1. 卡的全生命周期管理（发卡、续卡、销户、转移所有权）
2. 多 token 余额代理（卡地址即合法 token holder）
3. 风控（限额滚动窗口、receiver / syscall 白名单、冻结）
4. 法币桥铸入凭证验签（off-chain gateway 签的 FiatMintVoucher）

### 1.2 协议栈位置

```
┌─────────────────────────────────────────────────────────────┐
│  User Wallet / Agent Owner                                  │
│  (普通 EOA 或 multisig)                                     │
└────┬─────────────────────────┬──────────────────────────────┘
     │ IssueCard / Deposit     │ SetPolicy / TransferOwnership
     ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│  BankActor  (system actor, 0x0000…000D)                     │
│  ─────────────────────────────────────────                  │
│  · Card 状态 (multi-token vault + 策略 + 生命周期)          │
│  · Bank 注册表 (Cowboy Banking + 第三方 banks)              │
│  · 限额滚动窗口 (per-card)                                  │
│  · BankOperator 角色 → freeze / fiat-mint-voucher 验签      │
└────┬─────────────────────────┬──────────────────────────────┘
     │ ChargeGas (内部调用)    │ 关联读
     ▼                         ▼
┌────────────────────────┐   ┌──────────────────────────────┐
│  Transaction Engine    │   │  Actor (业务 agent)          │
│  fee_payer_override =  │   │  · 持有 default_card_addr    │
│      <card_address>    │   │    (BankActor 中存)          │
└────────────────────────┘   └──────────────────────────────┘
                                          ▲
┌─────────────────────────────────────────┴───────────────────┐
│  Off-chain Compliance Gateway  (Cowboy Banking 运营方)      │
│  · KYC / Stripe 入金 / 法币桥                               │
│  · 签发 FiatMintVoucher → BankActor.MintFromVoucher 验签    │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 与现有系统的关系

| 现有件 | 关系 |
|---|---|
| `fee_payer_override` | **新增 tx-level 字段** `tx.fee_payer_override: Option<Address>`。注意：现有的 `ScheduledTimer.fee_payer_override`（`pvm_executor.rs:24`，仅 timer 子系统使用）是同名但不同位置的字段；本 CIP 在 tx 顶层引入新字段，仅复用语义不复用 struct。Engine 解析 tx.fee_payer 时，若地址命中 BankActor card 派生集合，则把扣费走 BankActor handler 而非普通 debit |
| `SESSION_ACTOR (0x0C)` | **同构、独立**。Session 是单次 escrow + voucher 结算；Bank 是长期账户 + 策略，不复用 SessionActor |
| CBSS (CIP-24) | 借鉴其 namespacing 与 policy/version 状态分层风格（CIP-24 的滚动窗口实际是 proxy-local 限流，与 BankActor 的 on-chain 窗口语义不同） |
| Token (CIP-20) | 卡的多 Token 余额走 CIP-20 标准账本，卡地址即一个普通的 token holder |
| CIP-12 Governance | `RegisterBank` 等协议级动作走 CIP-12 治理提案（Tier 1 注册表写入；若需要升级 BankActor bytecode 则 Tier 3）；Cowboy Banking 的 `BankOperator` 默认绑定到 **Cowboy Banking operator 多签**（签名人组合由 CIP-12 治理指定，不是 CIP-12 §3.1 的 Cowboy Foundation——Foundation 在 CIP-12 中无协议权）；第三方 bank 在注册时自带各自 operator multisig |

### 1.4 角色与权责

| 角色 | 链上身份 | 能做 | 不能做 |
|---|---|---|---|
| **Card Holder Agent** | actor 地址 | 用卡付 gas（受策略约束） | 改卡规则、提现、冻结 |
| **Card Owner** | EOA 或 agent 自身 | 充值、SetPolicy、Renew、TransferOwnership、关闭卡 | 跨卡操作他人的卡 |
| **BankOperator**（每个 bank 一个） | multisig | Freeze / Unfreeze 自家 bank 下的单卡；签发 FiatMintVoucher | 改卡规则、动用户资金（freeze 只是禁用 charge，不没收资金） |
| **BankActor 协议层** | 0x0D | 校验所有 invariant；扣 gas；记录滚动窗口 | 任何权限都来自上面角色，无独立"协议作恶"路径 |
| **Off-chain Compliance Gateway** | 链下 | KYC、Stripe 收款、签 mint voucher | 无链上写权限，凭证上链由 BankOperator 多签验签 |

---

## 2. 数据模型 + 卡地址派生

### 2.1 顶层状态布局（BankActor 0x0D 的 storage）

沿用现行 system actor 的 `b"<tag>:"` ASCII 前缀风格（参 CBSS `b"secret:"`、SessionActor `b"session:"`、CIP-20 token `b"bal:"`）：

| Key pattern | Value | 用途 |
|---|---|---|
| `b"bank:" \|\| bank_id_be4` | `BankEntry` | 银行注册条目 |
| `b"bank_seq"` | `u32_be4` | 下一个 bank_id |
| `b"card:" \|\| card_addr_20` | `CardEntry` | 卡的全部状态（含策略、窗口） |
| `b"card_by_owner:" \|\| owner_20 \|\| bank_id_be4 \|\| idx_be4` | `card_addr_20` | owner 视角的卡列表索引 |
| `b"card_by_agent:" \|\| agent_20 \|\| bank_id_be4 \|\| idx_be4` | `card_addr_20` | agent 视角的卡列表索引 |
| `b"agent_default_card:" \|\| agent_20` | `card_addr_20` | agent 默认 gas 卡 |
| `b"issue_nonce:" \|\| bank_id_be4 \|\| owner_20 \|\| agent_20` | `u64_be8` | (bank, owner, agent) 三元组下下一张卡的派生 nonce |
| `b"voucher_used:" \|\| voucher_id_32` | `1` | 法币桥 FiatMintVoucher 防重放标记 |

Token 余额本身**不在 BankActor 存**：卡地址是普通 holder，余额由现行 CBY ledger / CIP-20 token actor 存。BankActor 只存"非余额"的卡元数据。

### 2.2 `BankEntry`

```rust
struct BankEntry {
    bank_id:           u32,
    name:              Vec<u8>,         // 1..=32 bytes, ASCII
    operator:          Address,         // multisig；可 freeze / 签 fiat mint voucher
    fiat_mint_signer:  Option<Address>, // 法币桥铸入的签名公钥；None = 该 bank 不支持法币桥
    status:            BankStatus,      // Active | Paused
    registered_at:     u64,             // block height
}

enum BankStatus { Active, Paused }
```

Cowboy Banking 在 genesis 写入 `bank_id = 1`，operator = **Cowboy Banking operator 多签**（签名人组合由 CIP-12 治理指定；与 CIP-12 §3.1 的 Cowboy Foundation 不同——Foundation 无协议权，不能持有 BankOperator 角色）。

### 2.3 `CardEntry`

```rust
struct CardEntry {
    // ── 身份 ─────────────────────────────────
    card_address:           Address,    // 与 key 一致，便于反查
    bank_id:                u32,
    owner:                  Address,    // 监护人 / 自己
    agent:                  Address,    // 这张卡服务的 actor
    issue_nonce:            u64,        // 派生地址用到的 nonce
    created_at:             u64,
    last_renewed_at:        u64,

    // ── 生命周期 ─────────────────────────────
    expires_at:             Option<u64>,// block height；None = 无限期（仅协议级用途，UI 不暴露）
    status:                 CardStatus, // Active | Frozen | Closed | Expired

    // ── 支付偏好 ─────────────────────────────
    gas_payment_token:      PayCurrency,// Native(CBY) | Token(token_actor_addr)

    // ── 策略 ─────────────────────────────────
    policy:                 CardPolicy,

    // ── 滚动窗口累计 ─────────────────────────
    window:                 SpendWindow,
}

enum CardStatus { Active, Frozen, Closed, Expired }
enum PayCurrency { Native, Token(Address) }
```

Day-1 限制：`gas_payment_token` 只能选 **Native CBY** 或 **官方稳定币 U**（在 genesis 配置中白名单的 token 地址）。其它 CIP-20 token 可入卡做储备/工资，不直接付 gas。

### 2.4 `CardPolicy`

```rust
struct CardPolicy {
    per_hour_cap:          Option<u128>,
    per_day_cap:           Option<u128>,
    per_month_cap:         Option<u128>,
    allowed_receivers:     Vec<Address>,    // ≤ 64，空 = 任意 receiver
    allowed_syscall_kinds: Vec<SyscallKind>,// ≤ 16，空 = 任意 syscall
    locked_after_transfer: bool,            // owner 移交后能否再 SetPolicy
}

enum SyscallKind {
    Send, DeployActor, PublishLibrary, Token, CrossChain,
    Session, Cbss, Custom(u16),
}
```

限额单位是 `gas_payment_token` 的 wei，不是 gas 单位。

### 2.5 `SpendWindow`

固定窗口（不是滑动），day-1 简化选项：

```rust
struct SpendWindow {
    hour_period_id:   u64,  // = block_height / BLOCKS_PER_HOUR
    hour_spent:       u128,
    day_period_id:    u64,
    day_spent:        u128,
    month_period_id:  u64,
    month_spent:      u128,
}
```

每次 charge：检查 period_id；若与存储不一致 → 清零累加器并更新 period_id；否则累加并校验 cap。

Roadmap：真滚动窗口（deque + 上限保护）放二期。

### 2.6 卡地址派生

```
DOMAIN = b"CowboyBankCard\x01"

card_address = keccak256(
        DOMAIN
     || bank_id_be4
     || owner_20
     || agent_20
     || issue_nonce_be8
)[12..32]
```

**关键设计取舍**：

- `agent` 进派生公式 → 卡天生绑死一个 agent；重新绑定 = 必须发新卡（与"一卡一身份证"一致）
- `owner` 进派生公式只做 salt → `TransferOwnership` 不改地址，仅改 `CardEntry.owner` 字段（避免转所有权后所有引用全失效）
- `issue_nonce` 让同一 (bank, owner, agent) 可产生任意多张卡（过期重发 → 新 nonce → 新地址）

### 2.7 默认卡解析

Engine 处理 tx 时，按下面顺序解析 `fee_payer`：

```
1. 若 tx 显式带 fee_payer_override:
     a. 若该地址命中 `b"card:" || addr` → 走 BankActor.charge_gas 路径
     b. 否则 → 普通 EOA 扣费（保留现行 owner-pays）
2. 否则若 tx.from 是 actor 地址 且 `b"agent_default_card:" || actor` 存在:
     → 用默认卡，走 BankActor.charge_gas
3. 否则 → 从 tx.from 自己余额扣（保留现行 actor-pays）
```

Day-1 向后兼容现有 owner-pays / actor-pays 行为；卡是叠加的第三条路径。

---

## 3. 指令集

`BankInstruction` enum，沿用 SessionActor 风格分派。

### 3.1 Owner 提交

| 指令 | 字段 | 关键校验 | 副作用 |
|---|---|---|---|
| `IssueCard` | `bank_id, agent, gas_payment_token, initial_policy, expires_at: Option<u64>` | bank Active；gas_payment_token ∈ {Native, 白名单稳定币}；policy 字段长度上限；caller = `tx.from` 即为 owner | 自增 `issue_nonce`；派生 `card_address`；写 `CardEntry` 及 owner/agent 索引 |
| `RenewCard` | `card_address, new_expires_at: Option<u64>` | caller == owner；status ∈ {Active, Expired}；new_expires_at > block_height（若有） | status → Active；更新 expires_at / last_renewed_at |
| `CloseCard` | `card_address, refund_to: Address` | caller == owner；status ≠ Closed；非默认卡 | 转出所有 token 余额；status → Closed；移除索引；清窗口 |
| `Deposit` | `card_address, token, amount` | bank.status == Active；card Active or Frozen（冻结仍可入金）；token ∈ {CBY, 合法 CIP-20} | token 从 caller 转给 `card_address` |
| `Withdraw` | `card_address, token, amount, to` | caller == owner；card status ≠ Frozen；余额足 | token 从 `card_address` 转给 `to` |
| `SetPolicy` | `card_address, new_policy` | caller == owner；若 `locked_after_transfer && owner == agent` → 拒绝；policy 长度上限 | 写入 `CardEntry.policy`（不重置窗口） |
| `TransferOwnership` | `card_address, new_owner, set_locked: bool` | caller == owner；new_owner ≠ 0x00 | `owner = new_owner`；若 `set_locked` 置 `locked_after_transfer = true` |

### 3.2 Agent 或 Owner 提交

| 指令 | 字段 | 校验 | 副作用 |
|---|---|---|---|
| `SetDefaultCard` | `agent, card_address: Option<Address>` | caller == agent **或** caller == card.owner；若 Some(addr)：card.agent == agent，status = Active | 写/删 `b"agent_default_card:" \|\| agent` |

双钥匙、后到覆盖。早期监护人能代设；agent 长大后自己也能切。

### 3.3 BankOperator 提交

| 指令 | 字段 | 校验 | 副作用 |
|---|---|---|---|
| `Freeze` | `card_address, reason: Vec<u8>≤256` | caller == bank.operator | status → Frozen；emit event 带 reason |
| `Unfreeze` | `card_address` | caller == bank.operator | status → Active 或 Expired（若已过期） |
| `PauseBank` | `bank_id, reason` | caller == bank.operator | bank.status → Paused；该 bank 下所有 charge / deposit / issue 停（withdraw 允许） |
| `UnpauseBank` | `bank_id` | caller == bank.operator | bank.status → Active |
| `MintFromFiatVoucher` | `voucher: FiatMintVoucher, signature: [u8;65]` | sig 由 `bank.fiat_mint_signer` 签出；voucher.bank_id 匹配；`voucher_id` 未在 `b"voucher_used:"`；`block_height ≤ expires_at_block`；bank.status == Active；card.status ≠ Closed | 给 `card_address` 的 token 余额 +amount；写 `b"voucher_used:" \|\| voucher_id`；emit `FiatMinted` |

```rust
struct FiatMintVoucher {
    bank_id:           u32,
    card_address:      Address,
    token:             PayCurrency,
    amount:            u128,
    voucher_id:        [u8; 32],   // 唯一；防重放主键
    expires_at_block:  u64,
    fiat_reference:    Vec<u8>,    // ≤ 64 bytes，例如 Stripe charge_id
}
// 签名域：keccak256("CowboyBankFiatMint\x01" || rlp(voucher))
```

`MintFromFiatVoucher` 任何人可广播，签名校验来自 `fiat_mint_signer`——把"是否上链"的钥匙交给用户。

### 3.4 Governance 提交（CIP-12 治理提案）

| 指令 | 字段 | 校验 | 副作用 |
|---|---|---|---|
| `RegisterBank` | `name, operator, fiat_mint_signer: Option<Address>` | caller 经 CIP-12 治理提案授权（Tier 1 注册表写入；若同时升级 BankActor bytecode 则 Tier 3）；name 1..=32 ASCII；operator ≠ 0x00 | 自增 `b"bank_seq"`；写 `b"bank:" \|\| id`；emit `BankRegistered` |
| `SetBankOperator` | `bank_id, new_operator` | caller == 当前 operator 或经 CIP-12 治理授权 | 切换 operator |
| `SetBankFiatMintSigner` | `bank_id, new_signer: Option<Address>` | caller == operator | 切换/移除法币桥签名 key |

### 3.5 Engine 内部调用（非 tx 指令，不可寻址）

| 内部函数 | 触发 | 行为 |
|---|---|---|
| `BankActor::charge_gas(card, receiver, syscall_kind, amount, height)` | Engine 在 tx fee settle 阶段、判定 fee_payer 是 card 地址时 | 走 §4 扣费流；失败回退到 OutOfFunds 等价分支 |

### 3.6 事件

```
CardIssued        { card, bank, owner, agent, expires_at }
CardRenewed       { card, new_expires_at }
CardClosed        { card, refund_to }
CardDeposited     { card, token, amount, from }
CardWithdrawn     { card, token, amount, to }
CardPolicySet     { card, hash_of_policy }
CardOwnerTransferred { card, old_owner, new_owner, locked }
CardDefaultSet    { agent, card }
CardFrozen        { card, reason }
CardUnfrozen      { card }
BankRegistered    { bank_id, name, operator }
BankPaused        { bank_id, reason }
FiatMinted        { card, token, amount, voucher_id, fiat_reference }
GasCharged        { card, tx_digest, receiver, syscall_kind, reserve_amount, actual_amount }
```

---

## 4. Gas 扣费路径

### 4.1 Engine fee-settle 分叉点

```
                    tx 进入 fee-settle
                            │
                ┌───────────┴──────────────┐
                │ 解析 fee_payer (按 §2.7) │
                └───────────┬──────────────┘
                            │
              fee_payer ∈ b"card:" ?
              ┌─────────────┴─────────────┐
            否│                          是│
              ▼                           ▼
   ┌─────────────────────┐    ┌──────────────────────────┐
   │ 现有 EOA 扣费路径   │    │ BankActor.charge_gas(...) │
   │ (owner-pays 或      │    │  →  §4.2 流水线           │
   │  actor-pays，原样)  │    └──────────────────────────┘
   └─────────────────────┘
```

判定"是 card"的代价：一次 `b"card:" || addr` 读。bloom filter 缓存进 roadmap。

### 4.2 BankActor.charge_gas 流水线

#### Phase 1：Pre-flight Reserve（block admission 时）

```
in: card_addr, tx,
    cycles_limit, cells_limit,                     // 来自 tx 的 dual-metered gas 上限
    cycle_basefee, cell_basefee,                   // CIP-3 §2.4 当前块的 dual-metered basefee
    receiver_addr, syscall_kind, block_height

1. card  = read CardEntry(card_addr)               // 不存在 → BankErr::CardNotFound
2. bank  = read BankEntry(card.bank_id)
3. 静态校验：
     bank.status == Active                         // 否则 BankErr::BankPaused
     card.status == Active                         // Frozen/Closed/Expired → 对应错误
     card.expires_at.map(|e| block_height < e).unwrap_or(true)
4. 策略校验：
     a. 若 card.policy.allowed_receivers 非空 → receiver_addr ∈ list
     b. 若 card.policy.allowed_syscall_kinds 非空 → syscall_kind ∈ list
5. CIP-3 dual-metered 预扣公式（单位：attoCBY）：
     reserve_cby = cycles_limit × cycle_basefee +
                   cells_limit  × cell_basefee
     reserve_amount = match card.gas_payment_token {
         Native    => reserve_cby,                 // 卡用 CBY 付：直接落账
         Token(U)  => convert_cby_to_u(reserve_cby, genesis_peg),  // 卡用稳定币 U 付：按 genesis 固定汇率换算（oracle 入 roadmap）
     }
6. 窗口滚动：
     roll_window(card.window, block_height)
7. 限额校验（对每一档 cap，单位 = card.gas_payment_token）：
     hour_spent  + reserve_amount ≤ per_hour_cap   (若 Some)
     day_spent   + reserve_amount ≤ per_day_cap
     month_spent + reserve_amount ≤ per_month_cap
     // 任一未过 → BankErr::CapExceeded { tier }
8. 余额校验：
     balance_of(card_addr, card.gas_payment_token) ≥ reserve_amount
9. 写入副作用：
     debit(card_addr, gas_payment_token, reserve_amount)
     window.hour_spent  += reserve_amount
     window.day_spent   += reserve_amount
     window.month_spent += reserve_amount
     persist CardEntry
10. 返回 ReservationToken {
        card_addr, reserve_amount, gas_payment_token,
        snapshot_cycle_basefee, snapshot_cell_basefee,   // 锁定本次的 dual-metered basefee，settle 时复用
        snapshot_period_ids,
    }
```

#### Phase 2：Post-execution Settle（handler 执行完）

```
in: ReservationToken, actual_cycles_used, actual_cells_used

1. CIP-3 dual-metered 结算（用 reservation 锁定的 basefee 快照，单位 attoCBY）:
     actual_cby    = actual_cycles_used × snapshot_cycle_basefee +
                     actual_cells_used  × snapshot_cell_basefee
     actual_amount = match gas_payment_token {
         Native    => actual_cby,
         Token(U)  => convert_cby_to_u(actual_cby, genesis_peg),
     }
2. refund        = reserve_amount - actual_amount
3. 若 refund > 0:
     credit(card_addr, gas_payment_token, refund)
     // 窗口退款只退到"当前 period"，跨期不回卷
     window.hour_spent  = window.hour_spent.saturating_sub(refund) …三档同样
     persist CardEntry
4. emit GasCharged { card, tx_digest, receiver, syscall_kind, reserve_amount, actual_amount }
```

> **异步纪律**（参 commit `90c3073` 教训）：BankActor handler 全程 `async fn` + `.await`（与 CBSS handler 同款，见 `execution/src/cbss.rs`）。`charge_gas` 在 PVM handler 调用栈中触发的 storage IO（读 `b"bank:"` / `b"card:"`）必须沿 async 路径返回；如需在 `!Send` 上下文 drive future，**复用 `execution::actor_instruction::block_on_local`，禁用 `futures::executor::block_on`** —— 后者在嵌套 executor 下会 panic（`EnterError`）。

### 4.3 Timer-deferred tx 的特殊性

现行 timer 在调度区块就预扣 `max_cost`，fire 时是"已付"。接入卡后：

| 时刻 | 限额累计 | 资金落账 |
|---|---|---|
| 调度该 timer 的区块 | 计入"调度时"那个 period 的 window 累加器 | `debit card` 预扣 `max_cost` |
| timer fire 的区块 | 不再次计入 | actual_cost 之外按 Phase 2 退款 |

**含义**：限额是"调度决策时刻"的限额——监护人能在月初就看到孩子预排的全部任务，不会等到月末暴雷。

### 4.4 边界场景

| 场景 | 处理 |
|---|---|
| Card 在 reserve 之后、settle 之前被 Freeze | tx 仍正常 settle；下一笔 reserve 即拒绝 |
| Card 在 reserve 之后过期（block 跨期） | tx 仍正常 settle；下一笔 reserve 拒绝 `CardExpired` |
| Reserve 与 settle 跨 period | refund 只回退到 settle 时所在 period；旧 period 不回卷（保守，可接受） |
| Reserve 之后被外部 Withdraw | 不可能；Withdraw 路径检查余额，reserve 已 debit |
| 同一区块内同卡多笔 charge | 顺序累加；语义清晰 |
| `gas_payment_token = U` 但 U 与 CBY 精度不一致 | genesis 写入协议固定汇率（day-1 = 1:1 或常量 peg）；oracle 接入进 roadmap |
| Reserve 后 SetPolicy 改严 | 用 reserve 时的 policy 快照 settle；下一笔用新 policy |
| FiatMintVoucher 在 reserve 之后到账 | 不影响当前 tx；下一笔 reserve 可见新余额 |

### 4.5 错误码

新增 `BankErr::*`，engine 顶层 ErrorMap 统一映射：

```
BankErr::CardNotFound          → reject: BankCardNotFound
BankErr::BankPaused            → reject: BankPaused
BankErr::CardFrozen            → reject: BankCardFrozen
BankErr::CardExpired           → reject: BankCardExpired
BankErr::CardClosed            → reject: BankCardClosed
BankErr::ReceiverNotInWhitelist→ reject: BankPolicyDenied
BankErr::SyscallNotAllowed     → reject: BankPolicyDenied
BankErr::CapExceeded{tier}     → reject: BankCapExceeded
BankErr::InsufficientCardBalance → reject: OutOfFunds (复用现行)
```

### 4.6 与 Receipts / Indexer

`GasCharged` 事件带 `tx_digest`，Indexer 可 join：每笔 tx → 1 条 `GasCharged`（若 fee_payer 是 card）。UI 流水视图 = 该 card 上所有事件按时间排序。

---

## 5. 策略三件套语义细化

### 5.1 限额（per-hour / per-day / per-month）

#### 单位与口径

- **单位 = `card.gas_payment_token` 的整数 wei**（不是 gas 单位）
- 三档**互相独立**，任一不过即拒；不强制单调
- `None` = 该档不设限

#### 窗口期常量（BankActor 编译期常量，governance 可换版）

| 常量 | day-1 取值 | 说明 |
|---|---|---|
| `BLOCKS_PER_HOUR` | `3_600 / target_block_secs` | 取整 |
| `BLOCKS_PER_DAY` | `86_400 / target_block_secs` | 取整 |
| `BLOCKS_PER_MONTH` | `BLOCKS_PER_DAY * 30` | 标定为 30 天，不按日历月 |

用 block 而不是 wall-clock 保证确定性。

#### Period-id

```rust
fn period_id(block_height: u64, blocks_per_tier: u64) -> u64 {
    block_height / blocks_per_tier
}
```

Reserve 时若 period_id 不一致：先清零累加器、更新 period_id，再检查 cap。Refund 写回当前 period；跨期旧 period 不回卷。

#### 拒付错误码精度

`BankErr::CapExceeded { tier: Hour | Day | Month, would_be: u128, cap: u128 }`——UI 能直接展示"本月上限 100 U，本笔会让总额到 103 U"。

### 5.2 白名单

两条独立白名单，**都必须通过**。

#### `allowed_receivers: Vec<Address>`

| 状态 | 行为 |
|---|---|
| `Vec::new()`（空） | 任意 receiver 都允许 |
| 非空 | tx 的"主接收方"必须 ∈ 集合，否则 `BankErr::ReceiverNotInWhitelist` |

主接收方定义：tx 的 `to` 字段；多指令 tx 是第一条指令的目标。系统 actor 也按地址匹配。

容量上限：≤ 64。需要更大白名单 → 鼓励切多张卡。

#### `allowed_syscall_kinds: Vec<SyscallKind>`

固定的"指令 → SyscallKind"映射表（BankActor 编译期常量）：

| 指令 | SyscallKind |
|---|---|
| `SystemInstruction::Send` / `Transfer` / `CallActor` | `Send` |
| `SystemInstruction::Token*` | `Token` |
| `ActorInstruction::DeployActor` | `DeployActor` |
| `LibraryInstruction::PublishLibrary` / `RemoveLibrary` | `PublishLibrary` |
| `SessionInstruction::*` | `Session` |
| `CbssInstruction::*` | `Cbss` |
| Cross-chain settlement | `CrossChain` |
| 其它 | `Custom(opcode_u16)` |

容量上限：≤ 16。

#### 多指令 tx

每一条指令的 (receiver, syscall_kind) 都要通过白名单；任一失败整个 tx 拒付。

#### 黑名单不进 day-1

白名单 + freeze 已覆盖合规故事；显式 deny list 是白名单反向，重复语义。

### 5.3 Freeze 权限与状态机

#### 谁能冻结

- **仅 `bank.operator`**（Cowboy Banking = Cowboy Banking operator 多签，签名人组合由 CIP-12 治理指定；第三方 = 各自 operator multisig）
- Owner 不能 freeze（用 `SetPolicy { caps = Some(0) }` 或 `CloseCard` 更直接）
- agent 不能 freeze

#### 状态转换矩阵

| 当前 status | 允许 | 不允许 |
|---|---|---|
| `Active` | 任何 | — |
| `Frozen` | Deposit / SetPolicy / Renew / TransferOwnership / 取消 default / Unfreeze (operator) | charge_gas / Withdraw / 设为 default |
| `Expired` | Deposit / Renew (owner) / **Withdraw**（owner，取回余额） | charge_gas / 设为 default |
| `Closed` | **Withdraw**（owner，残款逃生口）—— 接收 timer-deferred 退款落账后的残值 | charge_gas / Deposit / SetPolicy / Renew / TransferOwnership / 任何其它写操作 |

Frozen 时允许 Deposit——真实银行处理涉嫌交易的标准动作。

#### Reason 字段

`Freeze.reason: Vec<u8>` 上限 256 bytes，原样上链 + 进事件。

#### Unfreeze

仅 operator；若此时 `block_height ≥ expires_at` → 落到 `Expired`（owner 必须 Renew）。

### 5.4 `locked_after_transfer` 精确语义

```
若 CardEntry.policy.locked_after_transfer == true
  且 CardEntry.owner == CardEntry.agent      // 已经转给 agent 自己
则：
  SetPolicy 永远拒绝（BankErr::PolicyLocked）
  TransferOwnership 仍允许
  RenewCard 仍允许
```

含义：监护人移交前可以选择"我不希望孩子自己放宽风控"。一旦勾选 + 转移成功，agent 自己也改不了；只能新发卡。

### 5.5 Roadmap 注解

| 项 | day-1 | 未来 |
|---|---|---|
| 真滚动窗口 | 固定 period | deque + 上限保护 |
| 黑名单 | 不做 | 显式 deny list |
| 按 token 分档限额 | 单 token 维度 | 多 token 各自 cap |
| 白名单容量 | 64 / 16 硬上限 | 链外签名扩展白名单 |
| 日历月 | 30 天 block | indexer 视图层 |

---

## 6. 多银行 + Stripe 法币桥

### 6.1 多银行：注册与隔离

#### Cowboy Banking 在 genesis 落地

```
b"bank:" || 0x00000001 = BankEntry {
    bank_id:          1,
    name:             b"Cowboy Banking",
    operator:         <Cowboy Banking operator 多签 地址>,
    fiat_mint_signer: Some(<Cowboy Banking Gateway Signer>),
    status:           Active,
    registered_at:    0,
}
b"bank_seq" = 2
```

#### 第三方 bank 注册

走 `RegisterBank`，caller 必须经 CIP-12 治理提案授权（Tier 1 注册表写入；若同时升级 BankActor bytecode 则 Tier 3）。不允许任意第三方自助注册——挂 "Cowboy 链上银行牌照" 必须由治理放行。

#### 银行间状态隔离

第三方 bank 完全独立：
- 同一套 `BankInstruction`，`bank_id` 区分
- 第三方 operator 只能 freeze / 暂停自家 bank 下的卡
- 第三方 bank 出问题不影响 Cowboy Banking
- 跨 bank 资金转移 = 普通 token transfer + Deposit/Withdraw 序列

| 隔离维度 | 实现 |
|---|---|
| 资金 | 卡是独立地址，bank 不持有共池资金 |
| 权限 | operator multisig 一对一 |
| 合规暂停 | `PauseBank` 仅影响该 bank 下的卡 |
| 法币桥 | 各 bank 各自的 `fiat_mint_signer` |

#### 卡跨银行迁移：不支持

卡地址由 `bank_id` 进派生公式，改 bank 必须换地址。等同销户开新户：`CloseCard` → `IssueCard`。

### 6.2 法币桥

#### 链上 / 链下职责切分

```
┌───────────────────────────────────────────────────────────────┐
│  Off-chain（Gateway）                                         │
│  · KYC（PII 存合规库，不上链）                                │
│  · Stripe 收款 + chargeback 监控                              │
│  · 凭收款成功 → 签 FiatMintVoucher                            │
│  · 发 voucher 给用户钱包                                       │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│  User Wallet                                                  │
│  广播 tx: MintFromFiatVoucher { voucher, signature }          │
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌───────────────────────────────────────────────────────────────┐
│  BankActor (on-chain)                                         │
│  · 校验 sig = bank.fiat_mint_signer                           │
│  · 校验 voucher_id 未使用                                     │
│  · 校验 expires_at_block                                      │
│  · 校验 bank.status / card.status                             │
│  · credit(card_addr, voucher.token, voucher.amount)           │
│  · 写 b"voucher_used:" || voucher_id                          │
│  · emit FiatMinted                                            │
└───────────────────────────────────────────────────────────────┘
```

#### 信任假设

| 假设 | 影响 |
|---|---|
| Gateway signer key 不泄漏 | 泄漏即"印钞机"；支持 `SetBankFiatMintSigner` 轮换；governance 应急清表路径放 roadmap |
| Gateway 不会签虚假 voucher | KYC + Stripe 收款回执 + gateway 内部审计三方制衡 |
| Stripe chargeback 与链上 mint 时序错位 | gateway 必须延迟签 voucher 至 Stripe 风险窗口过 |
| 用户钱包不丢 voucher | gateway 凭收款 id 重签同样 voucher_id；链上只接受第一次 |

#### voucher 反伪造

- 签名域 `keccak256("CowboyBankFiatMint\x01" || rlp(voucher))`，含 bank_id
- `voucher_id` 32 字节，推荐 `hash(stripe_charge_id || chain_id || bank_id)`
- `expires_at_block` 建议签出后 24h 等价的 block 数
- `fiat_reference` 上链明文存 Stripe charge_id（或哈希），事后对账

#### 出金 roadmap

day-1 只设计入金。出金（链上余额 → 法币）合规更重，占位指令名 `BurnToFiatRequest`，放二期。

### 6.3 Stripe 集成点（off-chain 接口，仅 design）

```
POST /v1/cards/{card_addr}/topup/intent
  body: { amount_usd, return_url }
  resp: { stripe_checkout_url, intent_id }

GET /v1/topup/intents/{intent_id}
  resp: { status: pending|paid|refunded|expired,
          voucher?: FiatMintVoucher,
          signature?: hex }

POST /v1/topup/intents/{intent_id}/redeliver
```

链上侧零侵入：BankActor 只认 `fiat_mint_signer` 签名。

### 6.4 合规边界

```
┌─────────────────────────────────────────────────────────┐
│        合规域（KYC / 反洗钱 / 法币税务）                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│   仅在 BankActor 内 + 各 bank gateway 内                │
│                                                         │
│   · 入金 KYC：gateway                                   │
│   · 限额风控：BankActor.charge_gas                      │
│   · 冻结：BankActor.Freeze（operator 多签）             │
│   · 法币流水审计：FiatMinted + GasCharged 事件          │
└─────────────────────────────────────────────────────────┘
                          ▲
                   合规手柄上抓
                          │
┌─────────────────────────────────────────────────────────┐
│      其余 Cowboy 生态（actor、token、session、CBSS）   │
│      继承 BankActor 的合规结论：无需各自做 KYC          │
└─────────────────────────────────────────────────────────┘
```

一句话：**Cowboy 链上其它一切都不用合规，只要 banking 这一层合规，因为钱进出生态的唯一通道就是这层。**

---

## 7. Roadmap & 兼容性

### 7.1 与现有计费三条路径的关系

```
                          tx 进入 fee-settle
                                 │
                ┌────────────────┼─────────────────────┐
                ▼                ▼                     ▼
  ┌──────────────────┐ ┌────────────────────┐ ┌──────────────────────┐
  │ actor-pays       │ │ owner-pays         │ │ card-pays  (新)      │
  │ (default 行为)   │ │ (fee_payer_override│ │ (fee_payer_override  │
  │                  │ │  指向 EOA)         │ │  指向 card 派生地址) │
  │ tx.from 自己扣   │ │ 该 EOA 扣          │ │ BankActor.charge_gas │
  └──────────────────┘ └────────────────────┘ └──────────────────────┘
            ↑                    ↑                       ↑
            │                    │                       │
         保留      保留（既有 timer / owner 模式不动）   新增
```

三条路径共存。新功能选择性接入，无强制迁移。

### 7.2 引入顺序（落地阶段）

| 阶段 | 内容 | 演示卖点 |
|---|---|---|
| **M1 BankActor 骨架** | 0x0D 落位、genesis 写入 Cowboy Banking、`IssueCard` / `Deposit` / `Withdraw` / `CloseCard`、卡地址派生、`card_by_owner/agent` 索引 | "每个 agent 拥有自己的链上银行卡" |
| **M2 计费分叉点** | engine fee-settle 增 §4.1 分叉；`charge_gas` Phase 1+2；`SetDefaultCard`；timer-deferred 集成 | "用卡付 gas，余额可见可审计" |
| **M3 策略三件套** | `SetPolicy`、`SpendWindow`、白名单匹配、`Freeze`/`Unfreeze`、`PauseBank`、`locked_after_transfer` | "限额、白名单、冻结全到位" |
| **M4 法币桥** | `MintFromFiatVoucher`、voucher 防重放、`SetBankFiatMintSigner`、off-chain gateway 接 Stripe | "信用卡即可充值 gas" |
| **M5 多银行 + Owner 移交** | `RegisterBank`、`SetBankOperator`、第三方 bank 隔离、`TransferOwnership` | "Cowboy 是链上银行牌照系统" |

M1+M2 是最小可演示组合。

### 7.3 Feature gate

新增治理参数 `bank_activation_height: u64`：

- 低于该高度：BankActor 不存在，`fee_payer_override` 指向卡地址 → 视为普通 EOA 不存在 → OutOfFunds
- 高于该高度：BankActor 激活，§4.1 分叉上线，genesis 项写入 Cowboy Banking

testnet → mainnet 推送 height 可分别配置；回滚把 height 设到未来。

### 7.4 状态迁移影响

- 不动现有状态：actor / token / session / cbss / entitlement / storage 零侵入
- 只增不改：`b"bank:" / b"card:" / b"card_by_*:" / …` 都是新命名空间，与现有 system actor 的 storage key prefix 不冲突
- 现有的 `ScheduledTimer.fee_payer_override`（timer 子系统）字段不动；本 CIP 在 tx 顶层新增独立的 `tx.fee_payer_override: Option<Address>`，两者命名相同但位置独立，互不干扰

### 7.5 与既有 CIP 的交叉点

| CIP | 交叉点 | 处理 |
|---|---|---|
| CIP-3（dual-metered fee） | charge_gas 严格按 CIP-3 §2.4 dual-metered 公式 `cycles × cycle_basefee + cells × cell_basefee` | ReservationToken 必须锁定两条 basefee 的快照，settle 时复用以保证 refund 一致 |
| CIP-20（token） | 卡持有 CIP-20 余额 | 卡地址即合法 token holder |
| CIP-24（CBSS） | 状态布局风格 | 借鉴；不依赖 |
| CIP-12（治理） | `RegisterBank` 走 Tier 1 注册表写入；BankActor bytecode 升级走 Tier 3 system actor 升级 | Cowboy Banking BankOperator 的签名人组合由 CIP-12 治理决定（不复用 Foundation/Security Council，独立多签实例） |
| Session (0x0C) | 卡是长期账户，session 是单次 escrow | session_id 可入 `allowed_receivers` 白名单 |

### 7.6 Roadmap

| 项 | 来源 | 优先级 |
|---|---|---|
| 真滚动窗口 | §2.5 / §5.1 | P1 |
| 多 token 分档限额 | §5.5 | P1 |
| 法币出金 `BurnToFiatRequest` | §6.2.3 | P1 |
| Stripe gateway 实现 + KYC 后台 | §6.3 | P0（M4 必须有） |
| BankOperator 应急清表（signer 泄漏） | §6.2.1 | P2 |
| 显式 deny list | §5.2.4 | P3 |
| 跨 bank 卡迁移 | §6.1.4 | P3 |
| Per-token oracle 兑换支付 gas | §2.3 | P2 |
| Bloom filter 缓存 active card 集合 | §4.1 | P3 |

### 7.7 不进 day-1 的明确否决项

- ❌ 链上 KYC（PII 不上链）
- ❌ 卡支持多 holder agent（破坏"一卡一身份证"核心叙事）
- ❌ 协议级 paymaster 抽象（独立故事线）
- ❌ 卡之间内部转账原语（用普通 token transfer 即可）
- ❌ 用 SessionActor 复用做 banking（已在方案选择阶段排除）

### 7.8 风险与开放问题

1. **限额单位与 basefee 波动**：用户设的 cap 是 token 单位（CBY 或 U），但 `cycle_basefee` / `cell_basefee` 在 CIP-3 dual-metered EIP-1559 下各自波动。UI 上需要给用户看"按当前 dual-metered basefee 估算能跑多少笔 tx"
2. **Cowboy Banking operator 治理**：Cowboy Banking operator 多签初期由 Cowboy Labs 团队持有 → 投资人尽调"是否中心化银行"，narrative 需对齐"去中心化路径见 CIP-12 治理"（注意：与 CIP-12 §3.1 Cowboy Foundation 无关——Foundation 在 CIP-12 中无协议权）
3. **第三方 bank 上线的最小集合**：M5 落地需要至少一家第三方真上线才能讲完整故事，建议同期推进一家合作伙伴
4. **Stripe chargeback 与 voucher 已上链的时序**：gateway 内部参数（48h / 72h？），CIP 不定，但 review 时要在审查清单

---

## 附录 A：术语表

| 词 | 含义 |
|---|---|
| BankActor | 系统 actor，地址 0x0D，承担本 CIP 全部链上职责 |
| Bank | 在 BankActor 注册表中的一条 BankEntry，例如 Cowboy Banking / 第三方 |
| Card | 一张卡，链上由 CardEntry + 派生地址表示，对应实体世界一张银行卡 |
| Card Address | 由 (bank_id, owner, agent, issue_nonce) 通过 keccak256 派生的 20 字节地址 |
| Card Owner | 卡的规则控制者，早期是用户（监护人），后期可能是 agent 自己 |
| Card Holder Agent | 卡服务的 actor，即"用卡付 gas 的那个 agent" |
| BankOperator | 一家 bank 的运营方多签，能 freeze / pause / 签 fiat voucher |
| Vault 模式 | 卡的余额实际存在卡地址自己名下（不是 owner 钱包），like prepaid debit |
| FiatMintVoucher | gateway 签发的法币入金凭证，用户广播上链铸入卡余额 |

## 附录 B：与会议要点对照

| 会议原话（要点） | 本 CIP 对应章节 |
|---|---|
| "做一个 actor 的银行 / 给每个人开一个账户" | §1, §2, §3 |
| "可以接收 CBY，可以接收 U，可以接收很多 TOKEN" | §2.3 (gas_payment_token) + §3.1 (Deposit 任意 token) |
| "接 Stripe，法币也能当 Gas" | §6.2 法币桥 |
| "每个月最多花多少钱，每小时上限" | §5.1 限额三档 |
| "白名单：卡里有钱但只能去吃麦当劳、肯德基" | §5.2 allowed_receivers / allowed_syscall_kinds |
| "卡可以过期 / renew" | §3.1 RenewCard、§5.3 状态机 |
| "黑户：拉黑卡而不是拉黑整个人" | §3.3 Freeze、§5.3 状态机 |
| "一张卡只有一个 owner / agent" | §2.6 派生公式（agent 进 salt）+ §3.1 校验 |
| "早期 owner = 监护人，后期 agent 自己" | §3.1 TransferOwnership + §5.4 locked_after_transfer |
| "Cowboy Banking 之外可能有建设银行（第三方 bank）" | §6.1 多银行 |
| "默认从哪张卡扣，要有 default" | §2.7 + §3.2 SetDefaultCard |
| "Cowboy 整体不合规，banking 合规即可" | §6.4 合规边界 |

---

*文档止于此。准备进入 implementation plan 编写（CIP-28 落地分 M1–M5）。*
