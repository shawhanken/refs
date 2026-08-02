# Plan-Cost 报告 — CIP-36: Phased Launch (Testnet Credits CUSD & Mainnet Airdrop)

| | |
|---|---|
| **Plan** | `/home/ubuntu/workspace/cowboy/docs/cips/cip-36-phased-launch-cusd.md` |
| **Plan 版本** | Draft r3 / r1.4(Revised 2026-07-27) |
| **Domain pack** | `cowboy`(34 个概念) |
| **生成日期** | 2026-08-02 |
| **verdict** | **`cost-only`** — 这是成本画像,**不含 go/no-go 建议** |

> **本报告的诚实分离原则**
> - **确定性成本**(§1)由 `marshal_core.cli plan-cost` 计算,从真实概念树/锚点推出。
> - **plan → 概念映射**(§1 的 op 选择)与**工期估算**(§3)是 agent 的判断,可被质疑。
> - `hinted_cost` 是 agent 标注的、**可被玩弄**的部分,§2 逐项交叉核对。
> - Marshal 不知道你的预算、发布窗口和法务排期,**不替你决定值不值**。

---

## 0. 我怎么读这份 plan(范围判定)

CIP-36 自称 "minimal, constitution-preserving",并把自己对 CIP-18 / CIP-20 / CIP-28 的改动描述为
"amends … declared, opt-in / backward-compatible"。

**但代码现状是:**

- **CIP-18 PaymentGate 未实装。** 概念页 `payments.md` 记 `status=draft`、**零锚点**,drift V-15/V-16 明确
  `PAYMENT_GATE=0x11`、`payment.gate` entitlement、EVM bridge facilitator 均为 precondition,代码未实装。
- **CIP-28 BankActor 未激活。** CIP-36 §7 自己写 `BANK_ACTIVATION_HEIGHT` 是 `u64::MAX`。

**所以 "amend" 在实现层面大量是 "build"。** 这一点直接决定 §1 的数字怎么读(见 §2 的失真警告)。

本次计价范围 = **CIP-36 自身的 delta**。CIP-28 底座(Stripe 桥、卡、`MintFromFiatVoucher`、合规网关)
是 §13.1 声明的**发布依赖**,单独在 §3 列出,不计入 144。

---

## 1. 确定性成本(CLI 计算)

```
weighted_concept_cost   144
  ├─ grounded_cost       54   (redefine — 从真实概念树/锚点推出,不可 gaming)
  └─ hinted_cost         90   (add — agent 标注,占 63%,见 §2 交叉核对)
highest_tier_touched    high
blast_radius            mcp-ingress
impacted_repos          node
unknown_redefines       (无)
unknown_ops             (无)
```

### 1.1 Redefine — 被重定义的既有概念(grounded 54)

| 概念 | tier | 子树 | repos | 权重 | 判定依据 |
|---|---|---:|---:|---:|---|
| `economics` | high | 5 | 1 | **28** | §6.4 全网服务改为 USD 计价 / CUSD 计费,测试网无 CBY 结算、无 CBY/USD oracle。概念页称"所有链上稀缺资源定价与价值守恒都归此域",而 CUSD 的守恒是**托管的、链下审计的**(§6.3 mint conservation / §10 peg & reserve) |
| `system-actors` | high | 0 | 1 | **8** | §6.5 BankActor 落地 `0x16`。概念页当前只记已实装的 `0x01–0x0C` + 虚拟拦截 `0x1D`,并明确 `0x0D–0x13` 为 spec-only |
| `speculative-execution` | high | 0 | 1 | **8** | §6.2 / §6.3 反复以"引擎在 handler 返 `Err` 时**不**回滚部分写"为规范前提;概念页写的是"propose/verify 阶段执行进 WriteBuffer(可回滚)"。CIP-36 不修它,而是把 check-then-apply 定为规范 —— 等于把该属性钉死 |
| `consensus` | high | 0 | 1 | **8** | 两条独立依据:(a) §7 admission 是 mempool/RPC 策略,而 `chain/src/mempool.rs` 正是该概念的锚点;(b) §7 r1.4 preimage 是 CIP 自己标注的 **consensus change + flag-day**("每个节点 MUST 构造相同 preimage,否则两个合规节点对签名有效性不一致 —— 分叉") |
| `payments` | mid | 0 | **0** | **2** | CIP-18 escrow-hop + 任意多方分账 + check-then-apply。权重仅 2,**因为它零锚点**(spec-only)—— 见 §2 失真警告 |

### 1.2 Add — 新增概念(hinted 90,agent 标注)

| 概念 | importance | est_scope | 权重 | 内容 |
|---|---|---|---:|---|
| `agent-banking` | high | **large** | **36** | CIP-36 对 CIP-28 的 delta:`0x16` 激活、`IssuancePrincipalVoucher`(域标签 `\x02` 签名 preimage + golden vector + 跨 repo 一致性 + flag-day)、`settle_provider`(幂等 consumed-set + check-then-apply + 偿付前置)、M3.6 token-gas paymaster |
| `cusd` | high | medium | 12 | CIP-20 实例(peg / decimals 6 / mint 路径唯一)+ allowlist transfer hook;含 `card → owner` 跨 actor 读,要塞进 50,000 Cycles / 50,000 Cells 的 hook 预算(§13.8 未决) |
| `admission-control` | high | medium | 12 | funded fee-payer 解析(account / owner / card `fee_payer_override`)+ per-principal 区块配额 + canonical principal 键 + 读 parent-block state 保证确定性 + 可选 `admission_charge` |
| `launch-testnet` | high | medium | 12 | 双网络模型:独立 genesis、curated validator/runner、每个不变量从此需要"哪张网"限定词 |
| `mainnet-airdrop` | high | medium | 12 | 指标框架 + sybil/wash 抗性 + 快照规则 + WP §8.3 emission-model basis 的治理批准 |
| `burn-from-authority` | high | **small** | 4 | CIP-20 的窄增量:`burn_from_authority: Option<Address>`(创建时定死、不可变、默认 `None`)+ `burn_from` 带偿付前置 + `Burn` 事件 |
| `test-cby` | mid | small | 2 | 隐藏、充值时自动发放、不可转账、不跨链的测试网 gas 资产 |

### 1.3 波及面

- **`blast_radius` = `mcp-ingress`**(唯一一个,因为 `mcp-ingress.depends_on` 含 `payments`)。
- **`impacted_repos` = `node`**(单 repo)。
- 被触及的概念在 `depends_on` 图里大多是叶子,所以传递闭包很小 —— 但见 §2 的 `settlement-slashing` 开关。

---

## 2. 交叉核对(hinted 占 63%,本节最重要)

### 2.1 我的标注是否往小标了?

| 检查项 | 结论 |
|---|---|
| `agent-banking` 标 large | **往大标,不是往小标。** 但它只覆盖 CIP-36 自己的 delta,**不含** CIP-28 底座 —— 底座在 §3 单列 |
| `burn-from-authority` 标 small | **成立,但前提是名字诚实。** 我特意**没有**把它叫 `fungible-tokens` —— 若叫后者,small 就是典型谎标(CIP-20 是整个 `execution/token/` 子系统)。这里真正的增量确实只有一个 authority 字段 + 一个带前置检查的 burn |
| `cusd` / `admission-control` / `launch-testnet` / `mainnet-airdrop` 标 medium | 均为"新建一套机制但不重写既有子系统"的量级,medium 自洽 |

### 2.2 本次运行暴露的两个注册表缺口

1. **概念树里根本没有 CIP-20 / fungible-tokens 概念页。** 34 个概念中一个都没有。
   `burn_from` 本该是对它的 **redefine**(grounded,不可 gaming),现在只能记成 add(hinted)。
2. **`payments` 权重 = 2,是本次数字里最大的失真。**
   `grounded_cost` 按 `importance × (1 + 子树大小 + 锚点 repo 数)` 计算,而 CIP-18 **零锚点**。

> **结论(重要):这份 plan 里工作量最重的两块 —— PaymentGate 与 BankActor —— 恰恰因为"还没实装"
> 而在确定性成本里几乎不计权重。144 系统性**低估**实现成本、相对**高估**"扰动既有概念"的成本。
> 不要把 144 读成"比上一份 isolation register 的 96 贵 50%",两者的失真方向不同。**

### 2.3 最敏感的一格:`settlement-slashing` 按不按?

我**没有**把 `settlement-slashing` 记成 redefine,理由是 §3 / §11 明确把 runner 经济模型划为 non-goal:
链上 `SettlementConfig` tip 分账在测试网照跑(只是跑在没市场价值的 test-CBY 上),
真正有经济意义的 runner 付款走 CUSD / PaymentGate(§8"invisible to consensus")。

**但这一格可以合理地按下去,后果很大:**

| | 不含 `settlement-slashing`(本报告采用) | 含 `settlement-slashing` |
|---|---:|---:|
| `weighted_concept_cost` | 144 | **160** |
| `grounded_cost` | 54 | **70** |
| `highest_tier_touched` | high | **constitutional** |
| `blast_radius` 大小 | 1 | **10** |
| `blast_radius` 内容 | `mcp-ingress` | cross-chain, custom-domains, governance, mcp-ingress, mpp-session, runner-delegation, runner-lifecycle, runner-verification, tee-attestation, vrf-runner-selection |

**tier 从 high 跳到 constitutional,波及面从 1 涨到 10。这是全篇最敏感的判断,我按 CIP 自己的
scoping 选了"不含",但你可能不同意。**

### 2.4 我刻意没有触及的概念(以及理由)

| 概念 | 不触及的理由 |
|---|---|
| `basefee` / `gas` / `dual-gas-model` | §5 明说旧稿的 launch-mode gas 改动**已撤销**;测试网只是用自己的 genesis 参数,费用模型代码不变 |
| `governance` | CIP-36 **使用**治理流程批准 WP §8.3 basis(§13.2),但不新增任何 governance op,CIP-12 不动 |
| `runner-lifecycle` / `runner-verification` / `vrf-runner-selection` / `tee-attestation` | §9 / §11 明确 CIP-2 / CIP-23 不变;pool 被 curate 是运营决策不是协议变更 |
| `mpp-session` | CIP-8 / MPP session 在 CIP-36 全文未被提及 |
| `runner-delegation` | §11 CIP-13 "dormant",无变更 |

---

## 3. 工期估算(agent 判断,**不是 CLI 计算**)

**confidence: low。** 低于上一份 isolation register 的 low–medium,原因:

1. 两个最大件(PaymentGate / BankActor)是**从零建**而非改;
2. §13 有 **8 个未决项**,其中两项根本不是工程问题;
3. §13.8(hook 预算能否容纳 `card → owner` 跨 actor 读)可能直接推翻一条设计路径。

**相对排序比绝对数值可信。**

### 3.1 CIP-36 自身范围

| 工作项 | est_impl_days | 备注 |
|---|---:|---|
| CIP-18 PaymentGate(escrow-hop + 任意多方分账 + check-then-apply) | 20–35 | **不是 amend,是 build** —— `0x11` 未实装 |
| CIP-36 对 CIP-28 的 delta | 15–25 | voucher preimage + golden vector + 跨 repo codec 对齐 + `settle_provider` 幂等/偿付 + `0x16` 激活 + M3.6 paymaster |
| Admission control(§7) | 10–18 | mempool/RPC gate + `fee_payer_override` 解析 + parent-block state 读 + per-principal 配额 |
| Airdrop 指标框架 | 10–20 | 主要是链下分析 + 可复现快照;抗 wash 是设计难点而非代码难点 |
| Launch testnet genesis + 运维 | 10–20 | 独立 genesis、curated 验证者/runner、部署与监控 |
| 链下:Compliance Gateway + HSM + rotation-stable principal 派生 | 15–25 | §7 / §10 的 launch-security 控制 |
| CUSD token + transfer hook | 8–14 | 跨 actor 读能否塞进 50k/50k 是真实风险(§13.8) |
| CIP-20 `burn_from` + `burn_from_authority` | 4–7 | 含 solvency / no-underflow / 创建时不可变的测试 |
| test-CBY | 4–7 | genesis schedule + 自动发放 + 不可转账 + 客户端隐藏 |
| **小计** | **≈ 95–170 工程日** | 单人计;PaymentGate / BankActor / hook 三块互相咬合,并行度有限 |

### 3.2 范围外但发不了车就得算的

| 项 | 量 | 说明 |
|---|---|---|
| CIP-28 底座 | **+40–70 工程日** | Stripe 桥、卡、`MintFromFiatVoucher`、合规网关。§13.1 声明为发布依赖 —— **没有它 CIP-36 发不了** |
| §13.7 律师对 CUSD 定性签字 | 日历时间 | non-transferable / non-redeemable 定性的 counsel sign-off,列为 launch gate |
| §13.2 治理批准 WP §8.3 emission-model basis | 日历时间 | CIP 自己坚持这**必须**走治理流程,不能当作"自动不变" |

**这两项不吃工程日,但能卡住整条线。**

### 3.3 est_debt_weeks(技术债)

- **check-then-apply 是一笔常设债。** 因为引擎在 `Err` 时不回滚部分写,这套栈里**每一个新 handler**
  都必须人工核验"先验后写"。约 **0.5–1 周 / 新 handler,无限期**,直到引擎那个 gap 被结构性修掉。
- **r1.4 preimage flag-day** 留下永久的 golden-vector + 跨 repo 一致性维护义务。
- **双网络**:注册表里每个不变量现在都缺"哪张网"的限定词;补齐并保持同步是持续成本。
- **CUSD 托管储备对账**:属运营成本,不是工程债,但是持续的。

**粗估 2–4 周 / 季度的 carry**,只要"双网络 + 绕过 no-rollback"两条同时成立。

### 3.4 与上一份 plan-cost 的交叉点(值得知道)

> CIP-36 §6.2 / §6.3 选择**绕过**"引擎不回滚部分写"这个缺陷(用 check-then-apply 规范)。
> 而 `2026-07-31-untrusted-actor-isolation-gaps.pdf` 的 **B4 ticket(机检 store-write choke point)**
> 提议**修掉**同一个缺陷。
>
> **两份 plan 在同一个引擎缺陷上做了相反的决定。** 这不是 Marshal 替你选,但你应该知道它们撞在一起了:
> 若 B4 先落地,CIP-36 的 check-then-apply 规范就从"必需的规避"降级为"额外的稳健性";
> 若 CIP-36 先落地,B4 的重构就要动一批已经按 check-then-apply 写死的 handler。

---

## 4. 你自己要判断的四件事

1. **144 里有 90 是 agent 的提示(63%)。** 上一份是 50%。这份更依赖判断,因为它主要在**新增**概念
   而非扰动既有概念。
2. **`settlement-slashing` 那一格按不按**,决定 tier 是 `high` 还是 `constitutional`、波及面是 1 还是 10。
3. **`grounded_cost` 系统性低估这份 plan** —— 越是没实装的东西,确定性成本给的权重越低,而实现成本越高。
4. **两个发布闸不是工程问题**(律师定性、治理批准 WP §8.3 emission basis),但能卡住整条线。

---

## 附录 A — 复现命令

```bash
PY=/home/ubuntu/workspace/marshal/.venv/bin/python

# 概念树
$PY -m marshal_core.cli concept-tree \
  --domain-pack cowboy \
  --concepts-dir /home/ubuntu/workspace/marshal/src/marshal_pack_cowboy/concepts \
  --repo-root node=/home/ubuntu/workspace/node

# 成本(touches 见附录 B)
$PY -m marshal_core.cli plan-cost \
  --domain-pack cowboy \
  --concepts-dir /home/ubuntu/workspace/marshal/src/marshal_pack_cowboy/concepts \
  --repo-root node=/home/ubuntu/workspace/node \
  --touches /tmp/pc36-touches.json
```

## 附录 B — touches(本次映射的完整输入)

```json
[
  {"concept_id": "agent-banking",       "op": "add", "importance": "high", "est_scope": "large"},
  {"concept_id": "cusd",                "op": "add", "importance": "high", "est_scope": "medium"},
  {"concept_id": "admission-control",   "op": "add", "importance": "high", "est_scope": "medium"},
  {"concept_id": "launch-testnet",      "op": "add", "importance": "high", "est_scope": "medium"},
  {"concept_id": "mainnet-airdrop",     "op": "add", "importance": "high", "est_scope": "medium"},
  {"concept_id": "burn-from-authority", "op": "add", "importance": "high", "est_scope": "small"},
  {"concept_id": "test-cby",            "op": "add", "importance": "mid",  "est_scope": "small"},
  {"concept_id": "economics",             "op": "redefine"},
  {"concept_id": "payments",              "op": "redefine"},
  {"concept_id": "system-actors",         "op": "redefine"},
  {"concept_id": "speculative-execution", "op": "redefine"},
  {"concept_id": "consensus",             "op": "redefine"}
]
```

**§2.3 的变体**:在上表末尾追加 `{"concept_id": "settlement-slashing", "op": "redefine"}`
即可复现 160 / constitutional / 10-concept blast radius 的那一列。
