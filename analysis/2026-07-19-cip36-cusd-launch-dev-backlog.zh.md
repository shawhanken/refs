# CIP-36 分阶段上线（cUSD）待研发清单

- **日期**: 2026-07-19
- **范围**: CIP-36 分阶段上线 / 测试网信用（cUSD）+ 主网空投，连同其关联依赖 CIP-18（Payments）、CIP-20（Fungible Tokens）、CIP-28（Agent Banking）
- **权威来源**: `cowboy/docs/cips/cip-36-phased-launch-cusd.md`、`cip-18-payments.md`、`cip-28-cowboy-agent-banking.md`
- **方法**: spec 逐条对照当前代码基线（node/ 4 路并行探查 2026-07-19）
- **一句话结论**: CIP-36 自身几乎不新增机制，其重量全压在它 amends 的三个 CIP 上。其中 PaymentGate 已有 M1、CIP-20 transfer hook 已全做；但 `burn_from` 与整个 CIP-28 BankActor 基本为零。

---

## 一、基线对照（spec ↔ 代码现况）

| 依赖 | Spec 要求 | 代码现况 | 缺口 |
|---|---|---|---|
| **PaymentGate 0x12** (CIP-18) | 结算层 | **M1 已落地**：policy/budget/pass/epoch/verify/settle 全在 `execution/src/payment_gate/`，genesis 即活 | 单收款人直转、只有 5% protocol fee、单资产、无 escrow-hop、无 `credit_inbound`/bridge |
| **CIP-20 transfer hook** | `can_transfer(4-arg)` + 50k/50k 预算 | **全落地**（`token/core.rs:179`，含重入防护、双计量子预算） | 无 |
| **CIP-20 `burn_from`** | 第三方烧 + 不可变 `burn_from_authority` | **完全没有**。只有 self-burn、burn 无任何授权门 | 整个原语 + 字段 |
| **CIP-20 mint authority** | 系统 actor 当 mint 权威 | 机制上可行（`mint_authority` 是普通 Address，比对调用者） | 无「不可变/系统 actor」语义层 |
| **BankActor** (CIP-28) | 0x16、卡模型、指令集、charge_gas、fiat voucher | **spec-only**（仅 UI demo + timer sponsor 原语 COW-1141）；`0x16` 在码中未分配 | 几乎全部 |
| **tx `fee_payer_override`** | tx 顶层字段 | **无**（只有 `ScheduledTimer.fee_payer_override`，是 timer 子系统）；canonical tx 在 `cowboy-protocol-codec` | 跨仓 codec 加字段 |
| **admission 反 spam** | funded gate + per-principal quota | nonce mempool + rate-limit + 自付 gas 检查有；**funded gate / per-principal quota 无** | 两个门 |
| **test-CBY / testnet gas** | 隐藏 gas token、资助即发放、genesis gas schedule | 只有手动 faucet；`MIN_BASEFEE=10_000` 是**编译期常量**、非 genesis 参数；genesis 无 gas/fee 字段 | 全新概念 |
| **issuance_principal** | 签名 voucher 盖在卡上 | **零** | 全新 |
| **Compliance Gateway / Stripe / 空投指标** | 链下 | **零**（audit-bot/cowpilot 均无关） | 全新链下服务 |

标记说明：🔴=共识/flag-day（执行层，须协调上线）　🟡=链下/客户端（非共识）　🟢=治理/法务门　⛓️=跨仓 codec

---

## 二、待研发清单（按工作流 + 依赖排序）

### W1 · CIP-20 `burn_from` 原语（**一切的地基，优先做**）🔴
1. `TokenMint` 加**不可变** `burn_from_authority: Option<Address>`，建立时定死、default `None`（`token/src/types.rs`，含 codec round-trip 三处）⛓️
2. `burn_from(token, account, amount, reason)` handler：**先验**（authority + reason 长度 + `amount ≤ balance(account)`，同时保证 `amount ≤ total_supply`）**再原子扣**（balance + total_supply），emit `Burn{token,authority,account,amount,reason}`。务必 check-then-apply（引擎不回滚部分写入的 pay-then-fail 守恒洞）
3. 新 `SystemInstruction` opcode（取下一个空号）+ 4 处 codec + 授权检查
4. 回归测试：insolvent 拒绝零写入、underflow 不可能、非授权者拒绝、default-None token 无此权能

### W2 · CIP-18 PaymentGate 扩充（cUSD 计费路径）🔴
5. **多资产**：`PaymentPolicy` 从单 `asset` 扩为 accepted-asset 集（把 cUSD 加进去），settle 校验改集合成员
6. **escrow-hop + 任意多方 payout**：payer → PG → N 个收款人（runner + aggregator + protocol/gateway）。现况是 `debit(payer)→credit(treasury)` 单收款人直转 — 需改成经 PG 托管再分账
7. **check-then-apply 全 or 无**：所有 leg（payer 偿付力、每个收款人、split 加总=托管额）**先全验再写**（同 W1，引擎不 revert）
8. 回归：分账守恒、任一 leg 失败零状态变更、cUSD hook 允许 `→PG` / `PG→any`

### W3 · CIP-28 BankActor（最大工作量，CIP-36 只需其子集但无法绕过）🔴
> CIP-36 需要 CIP-28 的 M1（卡）+ M4（fiat bridge）+ issuance_principal，M3 policy triad 与 M5 multi-bank 对 launch 非必须但 spec 绑在一起。

9. **BankActor 落位 `0x16`**：`system_actors.rs` 加 `BANK_ACTOR=0x16`（码中现空）、加入 `ALL` 注册表与 pausable 集、`pvm_host` reserved band 覆盖。**决定启动机制**（reserved-band 常量 vs `call_actor` 拦截，CIP-29 0x1D 模式）— CIP-36 §13 item1，留 CIP-28 activation PR
10. **卡资料模型**：`CardEntry`/`BankEntry`/`CardPolicy`/`SpendWindow` + 卡地址推导（keccak `CowboyBankCard\x01 ‖ bank_id ‖ owner ‖ agent ‖ nonce`）+ 索引键空间
11. **指令集**（新 `BankInstruction` + 各自 opcode ⛓️）：M1 `IssueCard`/`Deposit`/`Withdraw`/`CloseCard`/`SetDefaultCard`；M4 `MintFromFiatVoucher`（voucher 防重放 `voucher_used:` 集）+ `SetBankFiatMintSigner`；(M3/M5) `SetPolicy`/`Freeze`/`Unfreeze`/`PauseBank`/`RegisterBank`/`TransferOwnership`
12. **tx 顶层 `fee_payer_override: Option<Address>`**：在 `cowboy-protocol-codec` 的 `Transaction` 加字段（⛓️ 跨仓，wallet 须同步 byte-兼容）+ fee-settle fork point（§2.7 解析顺序）+ `BankActor.charge_gas` Phase1 reserve / Phase2 settle（沿用 CIP-3 双计量、snapshot 双 basefee；用 `block_on_local` 不用 `futures::block_on`）
13. **`bank_activation_height` 治理参数** + 高度闸（below=当 missing EOA→OutOfFunds，byte-identical 零 fork）
14. **cUSD token 实例**：genesis 或部署脚本建 cUSD（decimals=6、`mint_authority`=BankActor、`burn_from_authority`=BankActor、`transfer_hook`=allowlist），写 §6.2 hook 逻辑（`card/account→PG`、`PG→any`、`BANK→card`、`card↔owner`）
15. **`settle_provider(provider, n, settlement_id)`**：gateway-authorized、idempotent、check-then-apply，wrap `burn_from`（依赖 W1），consumed-set 在此 wrapper

### W4 · Admission 反 spam（testnet 为 operator-run，属 mempool/RPC 政策，**非共识**）🟡
16. **funded-account gate**：fee-payer 解析后校验 cUSD 余额 ≥ `min_funded_balance`（default $0.50）；解析失败一律**拒绝**不当 allowlisted（`rpc/handlers/chain.rs` admission）
17. **per-principal 区块配额** `max_admissions_per_principal_per_block`（default ~8），键为 **canonical principal**（EOA=地址；卡=不可变 `issuance_principal`）
18. **issuance_principal 读取**：admission 读链上已签 principal（读 parent-block state 保持确定性）
19. 可选 `admission_charge`（default 0）计量后备（§13 item4）

### W5 · test-CBY 与 testnet gas schedule 🔴(genesis) / 🟡(grant)
20. **MIN_BASEFEE 参数化**：把编译期 `MIN_BASEFEE=10_000` 常量改为 network/genesis 可设（`GenesisConfig` 加 gas/basefee 区块，seed `BasefeeConfig`）— 让 testnet 跑自己的排程
21. **test-CBY「隐藏 gas token」**：可用既有 CBY 走 CIP-3 gas path（spec 明说**不加** `launch_mode`/zero-basefee 共识改动），关键是 grant 与客户端隐藏，非新代币机制
22. **资助即自动发放**：cUSD 入金时 BankActor 给该账户足量 test-CBY（grant sizing §13 item3，链下/系统 tx 皆可，须反 spam）

### W6 · 链下 Compliance Gateway（全新服务）🟡🟢
23. **Stripe 接入 + FiatMintVoucher 签发**：结算过 chargeback 窗后签 voucher → `MintFromFiatVoucher`（§6.3 endpoints）
24. **issuance_principal 推导**：`HMAC(gateway_secret, "cowboy/issuance-principal/v1" ‖ compliance_id)`，**rotation-stable**（HSM/持久 registry），签 `IssuancePrincipalVoucher{bank_id,issuance_principal,owner_or_agent,nonce,expiry}`
25. **settlement_id 签发**：gateway-assigned unique（`HMAC(gateway_secret, payable_ref)`），对账链下 fiat payable
26. **Gateway 金钥托管**（§13 item6）：HSM、rotation policy、异常 principal 签发监控（单点被攻破=印钞机/多 principal，属 launch-security 非共识保证）

### W7 · Mainnet 空投框架 🟢
27. **可复现指标管线**：cUSD spend / verified job volume / uptime，快照规则、发布前公开
28. **反 sybil/wash**：排除 self-dealing round-trip（同 `issuance_principal`）、抵御 two-identity split（加权 *verified* job output > gross spend、per-principal 上限）
29. **治理批准**（§13 item2）：WP §8.3 Community/Airdrops 的 **eligibility basis** 从「2 drops」改为 testnet 指标 — supply/bucket size 不变但 basis 须经 genesis-parameter/治理程序批准（**不可当作「unchanged」**）

### W8 · 客户端 UX 🟡
30. Dashboard/CLI/desktop **不显示 test-CBY 余额**、不要求使用者管理 gas
31. **funded-account 入金流**：USD→cUSD、卡余额、statement 检视（join `GasCharged`/`FiatMinted` 事件）

### W9 · Companion（informative，独立交付）🟡
32. **Harness demos**：finance/trading harness、API-key manager、GPU-procurement router、search 入口（MCP/CLI）
33. **Proof-of-traceability**：强化 runner 结果溯源（独立 PR，§8/§12 引用）

### W10 · 门槛 / 开放项（非代码但阻挡 launch）🟢
34. **法务**：cUSD「非 stablecoin、不可转不可赎 prepaid credit」定性 counsel sign-off（§13 item7，launch gate）
35. **cUSD hook 跨 actor 读**：确认 `card→owner` 解析可塞进 50k/50k hook 预算；塞不下则砍 `card↔owner` 流（cUSD stays card-resident）（§13 item8）
36. **cUSD provider payout rails**：第三方 provider 上线前的 fiat/USDC 结算 spec（§13 item5，需自己的 spec）

---

## 三、关键路径与提醒

- **依赖链**：W1 (`burn_from`) → 挡住 W2 `settle_provider`、W3 cUSD 建立、W15。**先做 W1**。BankActor (W3 #9–14) 挡住 issuance_principal / fiat mint / 卡 gas，是第二关键路径。
- **flag-day 群**：W1/W2/W3/W5#20 都是执行层或持久化 config schema 变更 → 混版 fork class，须协调统一上线高度。tx 加 `fee_payer_override` 与新 `BankInstruction` opcode 是跨仓 codec（node + `cowboy-protocol-codec` + wallet 同日）。
- **spec 已宣称「零共识新增」的地方要守住**：CIP-36 刻意**不加** governance op、不加 `launch_phase` register、不加 zero-basefee 共识改动、不改 mainnet tokenomics。实作时若发现需要动这些，就是偏离 spec，得回头。
- **admission 是 testnet mempool 政策非共识**（operator-run），这让 W4 可以较轻量落地、不上棘轮；但 funded gate/quota 必读 **parent-block state** 保确定性。
- **CIP-21/22 out of scope**、CIP-13 dormant、CIP-2/3/23 unchanged — 别在这批动它们。
</content>
</invoke>
