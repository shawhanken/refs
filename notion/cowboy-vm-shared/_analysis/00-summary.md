# 00 — 执行摘要 / Executive Summary

> 这是 `refs/notion/cowboy-vm-shared/_analysis/` 的入口文档。本目录对外
> 部评审 (Vending Machine, 2026-04 至 2026-05) 提出的所有 ~70 个条目，
> 与现行 CIPs 和白皮书 v2 (`refs/whitepaper/2026-03-21_cowboy-technical-
> whitepaper-revised-v2.md`) 进行了一一对比分析。**本轮仅产出分析，不
> 修改任何 CIP / 白皮书。** 编辑动作留给下一轮 user-approved pass。
>
> **首要约束（无新增冲突）**：任何后续修订都不得引入新的 CIP↔CIP 或
> CIP↔WP 分歧。所有推荐的改动都已经过共一致性审计，结果落在
> [`_index/consistency-and-ordering.md`](./_index/consistency-and-ordering.md)
> 中。该文件枚举了：
> (i) 现存的 10 处 latent drift (D1–D10) 及解决策略；
> (ii) 推荐改动新引入的每一条 cross-document 引用，按出端点列出 co-change；
> (iii) 9 个"原子化 landing 批次" (B0–B8)，每批内部自洽，批与批之间不引入
> 中间漂移；
> (iv) 5 项政策决策的条件分支，每个分支都保证语料库自洽；
> (v) 20 条 pre-merge `rg` 验证清单。
>
> **任何修订必须以批次 (Batch) 为单位原子落地——禁止部分应用**。

---

## 一、统计概览

| 维度 | 数字 |
|---|---|
| 评审条目总数 | ~70 (P1: 25, P2: ~22, P3: ~8) |
| 已 actionable (有明确 CIP/WP 修订路径) | ~52 |
| 已 resolved (现行规范已修复 / 已 supersede) | 4 (#18 / #51 / #33 / #44) |
| 已 dropped (条目本身不再适用 / 误识别) | 4 (#40 / #63 — `unbonding_blocks` 数学错误不存在; #58 局部claims) |
| 需要 simulation / Phase-5 数据 | ~6 (`c` 系数, `X_safety` 校准, EMA value-weighting, adaptive committee 冲击, 碎片化 attack 量级, slashing-to-EV 比率) |
| 政策决策 (decision register) | 5 主项 + 2 子项 |
| 新建议的 CIP (本轮起草) | **3**: CIP-30 (Validator 罚没曲线), CIP-31 (CBFS 租金表), CIP-32 (罚没反转流程) |
| 新建议的 CIP (deferred / optional) | 3: CIP-33 (Lane V, defer), CIP-34 (Emission Curves, optional), CIP-35 (Bridge Selection, conditional on 决策 ③) |
| 已有 CIP 实质性改动 | **CIP-1 (rewrite), CIP-2 (multiple), CIP-13 (multiple)** + 小幅: CIP-3, CIP-4, CIP-5 (sunset §9), CIP-9, CIP-12 |
| 白皮书章节改动 | ~28 行变更 (4 editorial, 9 low, 9 medium, 6 high) |

---

## 二、Top-10 推荐改动 (按优先级)

1. **CIP-30 新建 — 验证者 BFT 罚没曲线与证据模型**
   以 Polkadot quadratic 曲线 `p_self(x, n) = clip(1%, (3x/n)², 1)` 配合
   `X_safety = 10` bug-cap 替换现行 WP §11.3 平 1% 罚没。同步引入四类
   Simplex 证据枚举 (notarization / finality-dummy / conflicting finalize /
   proposer equivocation) 与 hysteresis 抵押带 `S_in/S_low/S_out/S_max =
   0.50/0.40/0.33/5.0%`。**为何最优**: 平 1% 把诚实失误和卡特尔等价对待；
   quadratic 曲线是唯一经 Polkadot 主网验证过、能结构性区分 honest fault 与
   cartel 的设计。1% floor 保留最坏情况威慑。Distribution 条款 (95/5
   burn/submitter) 受决策 ① 门控。

2. **CIP-2 实质性修订 — Runner 市场核心修复**
   一次性修复评审中 7 个最大缺口: adaptive committee `M = clip(ceil(2·log₂(N)
   /HHI), 3, 9)`, VRF weight `s · sqrt(r)`, 新 §6A EMA 信誉 (14 天 half-life
   = 1,209,600 块, 重新校正自评审错误的 "5s slots ≈ 250k 块"), eligibility
   aggregator (≥ p50 + uniform random), aggregator bonus = 1.5% gross, 新
   §8.5 非披露默认 slash (单次 `CrashAttestation` 豁免), §9 embedding 模型
   pinning. **为何最优**: 七项缺口结构关联紧密，单次修订 atomic 落地比
   分批改动维护成本低。

3. **CIP-1 实质性重写 — Timer + GBA 全面 EIP-1559 化**
   废弃 first-price + exponential-bias auction，改为 EIP-1559 timer basefee +
   priority tip + per-actor fairness weight (W ∈ [1, 2] over 1000-block 窗口)。
   默认 GBA 仅需两行 (`max_fee = 2 × basefee`, `max_priority = previous_block
   _p50`)，自动闭合 Gap G7。**为何最优**: first-price 在 repeated knapsack
   场景下结构性不稳定; EIP-1559 复用了 EVM 六年的成熟模式; 失效出价攻击
   面 (#13) 在 EIP-1559 下结构性消失。CIP-5 §9 同步删除，避免双源真相。

4. **决策 ① 解锁: 修订 WP §8.4 C7 "Slashed stake 100% Burned"**
   现行 100% burn 阻塞 CIP-30 §"Distribution" (建议 95/5 burn/submitter)、
   CIP-2 §8.5 (建议 50/30/20 challenger/burn/treasury) 和 CIP-13 v2 已
   存在的 `SettlementConfig.slash_*_percent` (latent drift)。**为何最优**:
   不修订则三个下游修改全部阻塞; 修订后罚没流程才能有第三方监控的经济
   激励。这是本分析中最高 stakes 的单一政策决策。

5. **CIP-31 新建 — CBFS 租金表**
   填充 CIP-9 §14 中所有 `TBD` (`STORAGE_FEE_PER_BYTE_PER_EPOCH`,
   `TRANSFER_FEE_PER_BYTE`, `MIN_RELAY_STAKE`, `POR_*_PENALTY`,
   `RELAY_EVICTION_PENALTY`) 并新增 `RELAY_CHALLENGE_BOND`。同时把
   §10.4 的 10/2/88 split (burn/挑战池/Relay-pro-rata) 配上权重公式
   `(shard_count × shard_age_in_epochs)`，并解决 §14 注释中 12s 区块假设
   bug。**为何最优**: 经济常数与数据面分离 (CIP-9 owns 数据, CIP-31
   owns 数字), 治理调参不需要 touch CIP-9 protocol surface。

6. **WP §8.2 同步到 Chad 3 年滑行 4 → 3 → 2 + 通胀立场表态**
   评审 (item #3) 引用 Chad Q6 "我今天就改白皮书"，但承诺未落地；
   §8.2 仍是 4 年 8/6→4/3→2。同步引入 `validator_apr_target = 4-6%`,
   `security_floor_staked_ratio = 33%`, `security_floor_boost_bps = 200`,
   `security_floor_persistence_blocks = 2_592_000`，并把 "净通缩" 残余
   表述改为 "net slightly inflationary, burn is counterweight"。**为何最优**:
   无 validator APR 目标，运营商无法做 build-vs-rent 决策；无 security
   floor 参数，PoS 安全性下行无自动护栏。

7. **CIP-32 新建 — 罚没反转流程**
   `Payload::ReviewSlash` 自动在 `x ≥ X_safety` 时由 `0x09` 开启 (前置
   Tier-4 闸门); `Payload::EvidenceInvalidityAppeal` 提供加密学唯一的事后
   反转通道，杜绝 "every slash gets bailed out" 的 Polkadot 历史失败模式。
   **为何最优**: 把 "bug 还是攻击" 的判定从治理裁量转为机制规则; 切分
   出 pre-application auto-review (bug 路径) 与 post-application cryptographic
   appeal (无可裁量), 既保留 recoverability 又防止 cartel 罚没被讨价还价。

8. **CIP-13 §6.1 v2 — Runner Delegator 25% 治理票权**
   只在 Tier-2 标签为 `runner-marketplace-parameter` 的提案上生效，其他
   提案保持 0 票权。直接由 delegator 投票 (不被 runner 继承)。需配套
   CIP-12 §6.X 引入 proposal-tag schema。**为何最优**: delegator 承担 CIP-13
   §3.6 罚没风险但目前无政治声音 — 合法性问题。25% 在足够 meaningful
   和不淹没 validator 之间是合理折衷。Scope 限定避免影响 consensus-layer
   治理。

9. **CIP-3 + WP §6/§17.9/§13 — Lane fee multiplier 钉死 1.0× 与 MEV 范围
   显式化**
   现行三处文档都引用 "per-lane 倍数"，但无人指明数值。一次性补全
   `Fee Multiplier` 列并钉 1.0× ∀ lanes (Tier-0 可调)。同时把 WP §6.5 的
   一行 MEV 免责扩展为三类 `Out of scope` (单块 proposer censorship + private
   orderflow + JIT MEV against predictable actor logic)。**为何最优**: 推迟
   把 Timer 0.8× subsidy 等政策动作; 透明化 MEV 限制 (Cowboy 的 actor 模型
   使 JIT 是可预期威胁); 一次 batch edit 覆盖 5 个文档位置。

10. **小幅 / 编辑性收尾 — 9 项**
    包括 WP §2.2 broken `(§13.1)` → `(§12.1)`; WP §3.3 dangling `§Timer
    Rate Limiting` → `§5.1`; WP §4.4 N+10 wording 收紧到 "after 10 rent-
    epochs"; WP §5.1 "256 vs 1024 timers" silent drift 修正; CIP-9 §14
    block-time 12s→1s 重算; CIP-12 §3.1 vs WP §8.4 1% auto-feed 矛盾; etc.
    **为何最优**: 这些都是 1-行修订，但累积起来是评审项目 quality bar
    的 "可信度地基"; 一并随主修订批次落地最经济。

---

## 三、决策清单 Decision Register (5 项 + 2 子项)

| # | 决策 | 影响 | 默认建议 |
|---|---|---|---|
| ① | 是否打破白皮书 §8.4 "100% burn" 硬承诺 C7，改为 95/5 (validator 侧) + 50/30/20 (runner 侧)？ | 阻塞 **CIP-30 §"Distribution"** 与 **CIP-2 §8.5 distribution clause**；同时反映 CIP-13 v2 已存在的 `SettlementConfig.slash_*_percent` (latent drift) | **推荐: amend** — 理由: 解锁第三方监控经济激励 (validator-side 5% submitter share); runner-side 50/30/20 让挑战者经济模型存在; 不修订则 CIP-13 任何非-100%-burn 配置都会与 WP 矛盾 |
| ② | Security Council 是否加条件性 sunset (CIP-12 §3.2)？若是，`N` (validator 数) 与 `V` (USD-pegged 抵押额) 阈值各是多少？ | CIP-12 §3.2 + WP §11 修订 | **推荐: amend** — `N = 50` active validators, `V = $50M` USD at oracle TWAP, `sunset_epoch_length = 1 year`. 排序: Cancellation → Fast-track → Circuit-breaker pause |
| ③ | Bridge 选型: (a) 核心团队预选 + retirement hatch + TVL 上限; (b) launch 时禁用 EVM bridging, 主网后治理推选; (c) 维持完全治理委托 (现状) | WP §16.2 + 可能新 CIP-35 | **推荐: option (b) — launch disabled** — 现状 (c) 是 worst-of-both-worlds (第一个大投票同时承担最大安全决策); (a) 让核心团队挑赢家、风险集中；(b) 推迟决策到治理就绪 |
| ④ | Runner stake floor: USD-pegged via 7d TWAP 还是维持 CBY-denominated + 治理监控？ | CIP-2 §5, WP §13, WP §17.10; 共识关键路径上的预言机依赖 | **推荐: 暂维持 CBY-denominated** — 共识层预言机依赖太重; 即使 10× CBY 价波动，1 MiB 租金仍只有 `~$10/MiB/yr`，治理 30-90 天调整窗口足够。等专门 oracle CIP 成熟再升级 |
| ⑤ | WP §8.2 通胀曲线: 保持 4 年滑行 8/6→4/3→2 还是同步 Chad Q6 的 3 年 4→3→2？ | WP §8.2 + §13 economics block | **推荐: 同步到 4→3→2** — Chad Q6 已经明确表态; cleaner 故事; 保留 10% gross 硬上限给紧急 security floor 升压留余地 |
| ⑤b | WP §8.4 "Runner job payments 1% Treasury" 是否移除 (Chad Q4 已口头接受)？ | WP §8.4 + CIP-2 `SettlementConfig` 默认值 | **推荐: Path A — 移除，重定向到 burn** (`90% runner / 10% burn / 0% treasury`，10% 实际变成 `runner_fee_burn` 而非 11%) — 与 CIP-12 §3.1 "Foundation 只在治理通过时收到资金" 框架一致 |
| ⑤c | CIP-13 §4.4 `MAX_COMMISSION_BPS` 是否从 10000 (100%) 收紧到 3000 (30%)？ | CIP-13 §4.4 (Tier-2 治理调用, 非 spec 修订) | **推荐: 暂不收紧** — 缺乏实证 race-to-bottom 数据; 待主网运营有真实 delegator-runner 协商数据后再 Tier-2 调整 |

---

## 四、本轮新发现的"评审遗漏"

外部评审者未捕捉到、但在本分析中浮现的隐性问题:

1. **CIP-13 v2 `SettlementConfig.slash_*_percent` 已经允许治理调整罚没分配**，与 WP §8.4 C7 "100% burn" 硬承诺处于 latent drift — 任何非-100%-burn 配置都会让链上配置与白皮书静默矛盾。(01-slashing.md #36)
2. **评审的 "14 天 half-life ≈ 250k 块 at 5s slots" 算术错误** — Cowboy 是 1s 块，14 天 = **1,209,600 块**。所有引用此 half-life 的下游推荐 (CIP-2 §6A EMA, `JAIL_DURATION_BLOCKS`, HHI smoothing 等) 都依赖正确数字。(03-runner-marketplace.md)
3. **评审 "commission 无上限" claim 已 STALE** — CIP-13 v2 §4.4 早就 pin 了 `MIN_COMMISSION_BPS = 500, MAX_COMMISSION_BPS = 10000`. 评审建议的 30% 上限不是 spec gap 而是 Tier-2 治理调整问题。(03-runner-marketplace.md #33)
4. **CIP-9 §14 参数注释假设 "12s 区块" 但链运行 1s 块** — `POR_CHALLENGE_INTERVAL = 600`, `POR_RESPONSE_WINDOW = 50`, `STORAGE_GRACE_EPOCHS = 7,200`, `RELAY_UNSTAKE_DELAY = 7,200`, `ORPHAN_SHARD_TTL = 7,200` 五个常数的时间含义都错。NEW 发现。(07-state-rent-cbfs.md)
5. **CIP-12 §3.1 ("Foundation 仅在治理通过时收到资金") 与 WP §8.4 1% 自动 feed 直接矛盾** — 1% to treasury 不经过任何治理提案，违反 CIP-12 框架。NEW 发现。(05-tokenomics-inflation.md §F)
6. **WP §5.1 timer-per-actor cap = 256 vs CIP-5 §6.4 = 1,024 silent drift** — 评审者未发现; 只在重写 §5.1 时浮现。NEW 发现。(02-timer-gba.md #60)
7. **WP §3.3 dangling "(see §Timer Rate Limiting)" 引用不存在的章节** — 评审 #69 提到 §5.1 same-block prohibition 问题，但漏报这条更严重的 broken xref。NEW 发现。(02-timer-gba.md #69)
8. **评审 §11.3 / §25.3 / §11.5 / §25.5 / §16.2 / §13 / §27 等章节编号系统性引用 pre-v2 排版** — 一致漂移 across 评审者四个文档; meta-finding 提示下一轮编辑全 grep `§[2-9][0-9]\.` 以清理任何残余前-v2 引用。(08-doc-fixes.md "Notes for the next editorial pass")

---

## 五、目录索引

| 文件 | 主题 | 行数 | 主要 CIP/WP 触及面 |
|---|---|---|---|
| [01-slashing.md](./01-slashing.md) | 验证者 + Runner 罚没 | 289 | CIP-30 (new), CIP-32 (new), CIP-2 §6A/§8.5, CIP-13, WP §8.4/§11.3/§13 |
| [02-timer-gba.md](./02-timer-gba.md) | Timer + GBA 拍卖 | 154 | CIP-1 (rewrite), CIP-5 (sunset §9), WP §5.1 |
| [03-runner-marketplace.md](./03-runner-marketplace.md) | Runner 市场 / 验证 / 委托 | 324 | CIP-2, CIP-13, WP §7/§8.4/§13 |
| [04-fee-model-and-lanes.md](./04-fee-model-and-lanes.md) | 费率模型 + Lane 倍数 + MEV | 183 | CIP-3 §2.2.3/§6.5, WP §6/§6.5/§17.9/§13 |
| [05-tokenomics-inflation.md](./05-tokenomics-inflation.md) | 通胀 / 国库 / 发行曲线 | 226 | WP §8.2/§8.3/§8.4/§13, CIP-2 SettlementConfig, CIP-12 §3.1 |
| [06-governance.md](./06-governance.md) | 治理 / Council / Bridge | 166 | CIP-12, CIP-13 §6.1, CIP-25, WP §11/§16.2 |
| [07-state-rent-cbfs.md](./07-state-rent-cbfs.md) | 状态租金 + CBFS Relay | 151 | CIP-4 v2, CIP-9 §14, CIP-31 (new), WP §4.4/§17.5/§17.6 |
| [08-doc-fixes.md](./08-doc-fixes.md) | 文档漂移 / 交叉引用 | 159 | WP §2.2/§3.3 editorial |
| [09-new-cips-proposed.md](./09-new-cips-proposed.md) | 新 CIP & 改动汇总 | (synthesis) | All |
| [_index/cip-impact-matrix.md](./_index/cip-impact-matrix.md) | CIP × 改动类型矩阵 | (synthesis) | All CIPs |
| [_index/wp-impact-matrix.md](./_index/wp-impact-matrix.md) | WP § × 改动矩阵 | (synthesis) | All WP § touched |
| [_index/consistency-and-ordering.md](./_index/consistency-and-ordering.md) | 共一致性 + 原子化批次 + 决策分支 + 验证清单 | (synthesis) | **首要约束的执行文件** |

---

## 六、后续步骤 (Next Steps)

1. **由 Cowboy 团队 (连同 Foundation, 对 ① / ③ 而言) 就决策清单 5 主项 + 2
   子项做出政策判断。** 决策 ① 是阻塞最多下游 CIPs 的一项; 决策 ③ 是
   最高 stakes 的安全选型决策。
2. **根据决策结果，按 [`_index/consistency-and-ordering.md`](./_index/consistency-and-ordering.md) §C 中定义的 9 个 atomic landing batches 分批落地**。每批内部 drift-free, 批与批之间不引入中间漂移:
   - **B0** (无门控 / 编辑性): WP §2.2 / §3.3 / §4.4 xref + 措辞修正, WP §11 D3 残留 sunset 行删除, CIP-9 §14 block-time 修正 (统一 12s→1s)。
   - **B1** (CIP-30 + CIP-32 + WP §11.3/§11.4/§13 共识块): 不含 Distribution 条款。
   - **B1.D1** (Decision #1 门控): WP §8.4 C7 + 三处 distribution 默认值同步落地。
   - **B2** (CIP-1 rewrite + CIP-5 §9 删除 + WP §5.1 拆分)。
   - **B3** (CIP-2 多处修订 + WP §7/§8.4/§13): 与 B1 + B1.D1 耦合。
   - **B4** (CIP-3 lane multipliers + MEV 范围): 5 处 WP/CIP lane-multiplier 引用一次性收敛到 1.0×。
   - **B5** (WP §8.2/§8.3/§8.4/§13 tokenomics 块): Decision #5 + #5b 门控。
   - **B6** (CIP-31 + CIP-9 + WP §17.6 CBFS 经济): Decision #4 路径 a。
   - **B7** (CIP-12 + WP §11 + §16.2 治理/Council/Bridge): Decision #2 + #3 门控。
   - **B8** (CIP-4 v2 rent 迁移 + WP §17.5/§17.10): Decision #4 收尾。
3. **政策性变更 (C7, Council sunset, Bridge 选型) 需要走 Tier-3/Tier-4 治理
   流程才能落地**，不应静悄悄改写。Foundation pre-clearance 在编辑动作
   之前完成。
4. **simulation-pending 条目进入 Phase-5 仿真清单**:
   - `c` 曲线系数扫描 `c ∈ {3, 4, 5, 6}` against Cowboy validator 组成
   - `X_safety = 10` against bug-event frequency distribution
   - EMA reputation 是否 value-weight (Bittensor bond-clipping 借鉴)
   - Adaptive committee 在大批量 runner 出场时的冲击
   - Per-actor fairness weight 在 fragmentation attack (一个 dev 100 actor 实例) 下的失效阈值
   - Slashing-to-extractable-value 比率校准 (Concept C VAR feed 触发条件)

---

## Appendix A — English glossary of key proposals

For quick quoting into CIP drafts and external communication:

1. **CIP-30 (NEW) — Validator BFT Slashing Curve & Evidence Model.** Replaces flat 1% slash with `p_self(x, n) = clip(1%, (3x/n)², 1)` curve. Enumerates four Simplex evidence types (notarization equivocation, finality-dummy equivocation, conflicting finalize, proposer equivocation). Adds hysteresis stake bands `S_in/S_low/S_out/S_max = 0.50/0.40/0.33/5.0% of staked CBY`. Bug-correlation safety cap `X_safety = 10` triggers Tier-4 `ReviewSlash` via CIP-32. 95% burn / 5% submitter distribution (gated on decision #1).

2. **CIP-2 multi-amendment.** Adaptive committee `M = clip(ceil(2·log₂(N_active)/HHI), 3, 9)` with `N = ceil(2M/3)`; VRF weight `w = stake · sqrt(reputation)`; new §6A EMA reputation with **14-day half-life = 1,209,600 blocks** (at 1 s); jail-exit floor `r = max(0.1 × network_median, 50)`; new §8.5 non-reveal = proven dishonesty with single `CrashAttestation` exemption (default 50 blocks); aggregator eligibility ≥ p50 + VRF-uniform; aggregator bonus 1.5% of gross funded from runner share; SemanticSimilarity embedding pinned at `0x09:system:executor_registry:embedding_default` (Tier-3 changes).

3. **CIP-1 rewrite.** Replaces first-price + exponential-bias auction with EIP-1559 timer basefee + priority tip + per-actor fairness weight `W ∈ [1, 2]` over 1000-block window. Default GBA inline: `max_fee = 2 × basefee`, `max_priority = previous_block_p50_priority_tip`. Per-timer cap 250k cycles (auction-phase only). Timer-lane multiplier 1.0×. SDK `priority_tier_hint ∈ {economy, standard, fast, urgent}` mapping to `{0.8×, 1.0×, 1.5×, 2.5×}`.

4. **WP §8.4 C7 amendment (decision #1).** Replace flat "100% burn" with: 95/5 burn/submitter (validator side); 50/30/20 challenger/burn/treasury (runner side). Foundation pre-clearance required.

5. **CIP-31 (NEW) — CBFS Rent Schedule.** Owns concrete CBY values for `STORAGE_FEE_PER_BYTE_PER_EPOCH`, `TRANSFER_FEE_PER_BYTE`, `MIN_STORAGE_BALANCE`, `MIN_RELAY_STAKE`, `POR_MISS_PENALTY`, `POR_FRAUD_PENALTY`, `RELAY_EVICTION_PENALTY`, new `RELAY_CHALLENGE_BOND`. Split 10% burn / 2% challenge-pool / 88% Relay-pro-rata by `(shard_count × shard_age_in_epochs)`.

6. **WP §8.2 inflation glidepath update (decision #5).** Replace 4-year `8%/6% → 4%/3% → 2%` with 3-year `4% → 3% → 2%` to match Chad Q6. Add `validator_apr_target = 4–6%` (inflation-adjusted), `security_floor_staked_ratio = 33%`, `security_floor_boost_bps = 200`, `security_floor_persistence_blocks = 2,592,000` (30 days at 1 s).

7. **CIP-32 (NEW) — Slashing Reversal Flow.** Auto-`ReviewSlash` opened by `0x09` when correlation window closes with `x ≥ X_safety`; 21-day review window; outcomes Affirm / Reverse / Partial. Cryptographic-only `EvidenceInvalidityAppeal` for post-application reversal. Delegator compensation on Reverse credits principal + accrued rewards across slashable tranches per CIP-13 §3.6.

8. **CIP-13 §6.1 v2 delegator vote.** Runner-delegated CBY carries 25% pro-rata weight on Tier-2 proposals tagged `runner-marketplace-parameter` only; zero weight elsewhere. Voted directly by delegator. Requires co-amendment of CIP-12 §6.X for proposal-tag schema.

9. **CIP-3 §2.2.3 + WP §6 / §17.9 / §13 lane multiplier pinning.** Pin all four lane multipliers (System / Timer / Runner / User) at `1.0×` at genesis; mark Tier-0 governance-tunable. Reject the 0.8× Timer subsidy as a Concept-B holdover.

10. **WP §6.5 MEV Out-of-scope expansion.** Append explicit subsection enumerating: (a) single-block proposer inclusion/censorship; (b) private orderflow MEV; (c) JIT MEV against predictable actor logic. Point developers at SDK-layer mitigations (commit-reveal, slippage caps, order-flow auctions in actor logic).
