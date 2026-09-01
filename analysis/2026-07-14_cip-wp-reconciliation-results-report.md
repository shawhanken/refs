# CIP 与白皮书 — 全量规格对齐工作成果报告

> **一句话成果**：完成一轮 **39 份规格文档全量对齐上链代码**的工程——**312 条确认发现全部处置、15 条 HIGH 全数闭环、13 个 PR 落地、系统 actor 地址表零残留**。规格与代码之间"照原文实作就会分叉"的系统性风险被系统性消除。
>
> _2026-07-14。本报告是 `2026-07-09_cips-wp-deep-audit.md` 深度审计报告的成果汇总。数字、PR 号、常量、地址均已回一手源与实际 merged 状态核实。_

---

## 1. 背景与目标

Cowboy 的协议规格（34 份 CIP + 5 份白皮书）在长期迭代中**与上链代码系统性脱节**：常量、opcode 编号、系统 actor 地址、record schema、费用计价单位、error 语义，在 CIP/白皮书与 `node/runner/cbfs/cbss` 之间**全线对不上**。

这不是文风问题，而是**共识级风险**：

> **照数份规格原文独立实作出的 client 会使链分叉。**

目标就是把全部 CIP 与白皮书**逐条拉回**与部署代码一致——该修规格的修规格、该修代码的修代码、该留团队决策的标清楚，让"读规格实作"这件事重新变得安全。

---

## 2. 工作规模 —— 用数字说话

这轮工作的**繁琐与艰巨性**，先用体量说明：

| 维度 | 数字 |
|---|---|
| 审计文档 | **39 份**（34 CIP + 5 白皮书） |
| 确认发现 | **312 条**（HIGH 15 · MEDIUM 170 · LOW 124 · INFO 3） |
| 按维度 | 规格↔代码漂移 **123** · 一致性 71 · 完整性 87 · 安全 31 |
| 执行体量 | 两趟工作流 · **~1,211 个子代理** · **~44.8M token** |
| 质量把关 | 每条发现经**双视角对抗验证**（健全性 + 代码落地，两者都确认才算数） |
| 对抗阶段丢弃 | **134 条**候选被反驳（含 63 条 HIGH 层） |
| 需人工裁定 | **50 条**验证者意见分歧，逐条回一手源破验 |

每一条"确认发现"背后，都是一次**规格原文 ↔ 上链代码逐字比对**；每一次修正，都要保证不引入新的分叉面。312 条不是清单，是 312 次这样的往返。

---

## 3. 关键成果

### 3.1 15 条 HIGH 全数闭环（含真 live 代码 bug）
不止改文档——其中有**真正会出问题的上链代码缺陷**，已 TDD 修复并通过门禁：
- **CIP-13 `MIN_SELF_BOND_BPS`**：定义了却零强制（零自有资本 runner 可指挥无上限委托）→ 补齐委托 handler 校验。
- **CIP-5 超预算 timer**：carry-forward 后其实丢失，永不重放 → 修 rebucket 到下一区块。
- **CIP-3 4096-bit 整数守卫**：Python preamble 可绕过 → 落到 **VM 层（Rust）强制**，覆盖所有增长运算 + 构造路径，并补上"pre-check 防 pre-allocation DoS"。
- **CIP-23 `UpdateCollateral`**：未强制 `ROOT_UPDATE_DELAY`，治理可即时换 collateral → 补 604,800 区块延迟门。

### 3.2 §3 主漂移群全数处理
把最高价值的漂移群逐子系统抽取权威表后成批修正：**CIP-4 state-layout**（key-prefix/编码/mailbox 模型，light-client fork-class 最高值）· **CIP-24 CBSS**（多值 12× 漂移 + RotateCommittee 跨实作签名不相容 + 缺 opcode body）· **CIP-12 治理** · **CIP-16 域名** · **CIP-2 off-chain compute** · **三份白皮书**常量整表对齐。

### 3.3 §4 长尾 127 条清完
`23 CIP + 3 WP` 的 LOW/INFO 长尾——opcode 表、error 码表、dead-ref、单位/命名、未记录约束——**一趟并行清完**。

### 3.4 系统 actor 地址表 reconciliation（零残留）
发现规格"权威地址表"与部署代码**系统性错位**：规格写 `0x11`=Container / `0x13`=BankActor，代码实为 **`0x11`=VALIDATOR_SET** / **`0x13`=CONTAINER_REGISTRY**，且 VALIDATOR_SET 整个不在表内。级联修正 WP §9.1 锚表 + CIP-10/14/16/18/34，并**将未上链的 BankActor 重分配到 `0x16`**（`0x15` 留给已 penciled 的 EventListener）。权威源 `node/runner/src/system_actors.rs`（21 地址零碰撞、143 opcode 编译期保证）；沉淀 CI 检查器 `check_alloc.py` 防复发。

### 3.5 附带 code fix
CIP-7 示例 actor 打错 SKM 地址（`0x12`→`0x0D`），会调用错误的系统 actor → 已修。

---

## 4. 为什么这件事繁琐且艰巨 —— 工程难点

真正的难度不在"改字"，而在**每一条都要在正确的地方、用正确的值、且不能引入新分叉**。核心难点：

- **逐条回一手源核实，不能信审计结论。** 这是最耗人的部分。审计的 base 会陈旧，导致 **STALE-AUDIT 占比很高**——大量"发现"其实**早已被修、或规格本就正确、或机制根本没上链**。要安全地把它们丢弃，必须逐条回当前 devnet 源码重验。整份 CIP-7 被驳回、CIP-11 三/四条被驳回、CIP-17 则相反（整份是部署前草稿，全条都是真漂移）——**不逐条核，就会白改或漏改**。

- **真漂移常挂错 CIP。** 例：审计把"log2 VRF 权重"挂在 CIP-2，实际 CIP-2 早已正确、漂移在 **CIP-13**。核漂移要"顺藤摸瓜"找到真正 stale 的那份规格。

- **经济值会移动，不能硬追。** 储存费拆分在代码里从 88/2 又改回 89/1；硬把规格追着改只会来回打架。正解是**标 errata + coordination flag，留治理定**——判断"哪些该改、哪些该留"本身就是工作量。

- **light-client fork-class，精度要求极高。** schema 差一个字段、地址错一位、编码单位不同，独立 client 就分叉。CIP-9 的 `RelayNodeProfile` 差 12+ 个字段、3 处类型——照旧规格反序列化必失败。这类必须**抽 Rust struct 原文整块替换**，容不得手抖。

- **地址表系统性错位，牵一发动全身。** `0x11/0x13` 一处碰撞，牵动 6+ 份 CIP 级联修 + 白皮书锚表 + BankActor 重分配，还要照"部署者胜/最低号胜"的分配规则逐条判定方向。

- **多批 stacked PR + rebase 编排。** 长尾分三批递交，`#259` 叠在 `#257/#258` 上；两者合并后要 `git rebase --onto origin/main` 把 `#259` 收成"只含 §4"的干净 diff——期间还撞上**并发的 `#261` 改同一张白皮书表**的真实冲突，需要精确解冲突、取更权威的一方。

- **边界纪律。** 有明确的**回避令**（CIP-10 一度不碰，后经一次性授权才破例修其地址）；owner / 治理决策**不替裁**，只把选项和推荐写清楚。守住边界，本身也是纪律成本。

---

## 5. 方法学沉淀（可复用，把"逐条人工"变成"可并行、可复现"）

这轮工作沉淀出一套可复用的方法，是能在如此体量下收敛的关键：

- **四分类**：每条发现回当前 devnet 抽 ground truth 后分为 —— **LIVE-DRIFT**（值/描述错，改规格对齐代码）/ **NOT-IMPL**（机制未上链，加 callout 标注、保留设计）/ **STALE-AUDIT**（审计误报，核后略）/ **DECISION-VALUE**（经济/密码/跨 CIP 决策值，标 errata、不替裁）。
- **一 agent / CIP 抽全权威表**：同子系统多条漂移，派一个代理抽全 prefix/常量/struct 权威表，比逐条跑更省、更不易误报。
- **verify-primary-source**：引用任何事实前，回代码或权威 spec 核对，不信二手或旧检出。
- **确定性 CI 化**：opcode/地址碰撞这类，不跑代理，直接从权威源生成表、CI diff 每份规格的宣称（`check_alloc.py`），把"防复发"固化成 gate。

---

## 6. 交付清单

**全部 docs-only 或 TDD 代码修，无行为回退。**

| 批次 | PR | 范围 | 状态 |
|---|---|---|---|
| 主 campaign（规格） | cowboy **#239 / #240** | 10 条 HIGH 规格修 + fee-split amendment | ✅ MERGED |
| 主 campaign（代码） | node **#1004 / #1005 / #1006** | H-1 self-bond 强制 + H-11 timer rebucket + 覆盖测试 | ✅ MERGED |
| 主 campaign（代码） | node **#1008 / #1009** | 4096-bit 整数守卫（VM 层完整强制） | ✅ MERGED |
| 主 campaign（代码） | node **#1011** | CIP-23 UpdateCollateral 延迟门 | ✅ MERGED |
| §3 主漂移群 | cowboy **#247/#248/#249/#250/#251/#252/#243/#241** | CIP-4/24/12/16/2 + 三 WP + §5/§6/§9 | ✅ MERGED |
| 长尾 batch1 | cowboy **#257** | CIP-1/9/11/23/26 + WP | ✅ MERGED |
| 长尾 batch2 | cowboy **#258** | CIP-5/6/14/17/19/20/21/22/25/29 | ✅ MERGED |
| 长尾 batch3 | cowboy **#259** | §4 长尾 127 条（23 CIP + 3 WP）+ BankActor 0x16 + WP §9.1 | ✅ MERGED |
| 地址勘误 | cowboy **#260** | CIP-10 Container 0x11→0x13 | ✅ MERGED |
| 代码 fix | node **#1028** | CIP-7 SKM 地址 0x12→0x0D | ✅ MERGED |
| 收尾 | cowboy **#263** | CIP-24 stale cross-ref 清理 | 🟡 OPEN |

> 前期主 campaign 与长尾 campaign 合计 **20+ 个 PR 已并入 `main`/`devnet`**；仅剩 `#263` 一个小清理 PR 待合。

---

## 7. 残留与团队待决（不替裁）

- **团队 decision（仍 OPEN）**：**#236**（CIP-30 O(1) fork vs CIP-27 sealed 排除不可调和）、**#238**（CIP-24 `MIN_PROXY_STAKE` 规格 10k vs 代码 1k）、**#253**（CIP-31 fee split 10/2/88↔10/1/89，经济值）。`#237` 已 closed。每条都附了方案文档与推荐项，留治理/owner 定夺。
- **极少 LOW 长尾**：changelog 历史条目、secrets-WP §1.8 域分隔符补全、bond-framing errata——价值最低，交团队 spec-cleanup。

---

## 8. 结论

一轮把**全部 39 份协议规格拉回与上链代码一致**的系统工程：312 条发现全数处置、15 条 HIGH（含真 live 代码 bug）全闭环、系统 actor 地址表零残留、并沉淀出可复用的四分类方法与 CI 防复发检查器。"照规格原文实作会让链分叉"的系统性风险，已从"全线对不上"收敛到"仅剩三条待治理定的经济/密码决策"。
