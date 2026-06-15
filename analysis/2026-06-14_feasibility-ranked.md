# 可行性重排 — 由易到难(2026-06-14,Linear 实时全量)

**范围:** Linear COW 团队,state ∉ {completed, canceled},assignee ∈ {pavilionledger(PL), 未指派} —
共 **619 条**(541 Backlog / 67 Todo / 6 In Review / 5 In Progress;502 未指派 / 117 PL)。

**方法:** 程式化预分类(348 条明显的他团队/绿地/共识/canceled epic 按专案层级定档)+ **7 路并行 agent
对其余 271 条逐条回代码核验**,判据 = 「**验收能否在本地仓库实现 AND 本地验证**」。这是对 6 月初降噪
(靠标题+轻量检查、系统性高估了本地可完成性)的纠偏复评。

**判据四问**(任一为"是"即非 FEASIBLE-NOW):① 验收需不存在的 harness/CI/沙箱/多节点? ② 改动碰共识/genesis/receipt_root? ③ 单节点/单仓是否缺所需数据/依赖? ④ 卡他团队(CIP-2/3/4)/非本地/需先做规格或设计决策?

---

## 头部结论

真正"现在能做且能本地验证"的票很少;开放池绝大多数被**共识、缺基建、绿地、他团队/非本地**四类挡住。
排序优先级(从最划算到最难):

| 档 | 含义 | 条数(约) |
|---|---|---|
| **F-0 close 候选** | ~~已实作,核验后即可关单~~ → **2026-06-15 已全部消化(0 剩)** | 10→0 |
| **F-1 真·易(S,≤1天)** | ~~本地可改可测的小活~~ → **已清空**(202/231/363 交付merge、400/501 关闭) | 9→0 |
| **F-2 真·中(M,数天)** | ~~本地可改可测~~ → **实测全非干净**(共识/设计/集成/已覆盖) | 7→0 |
| **F-3 example 跑验** | 目录+demo.sh 已在,跑本地 validator 验证/修回归(**未跑,留专门一轮**) | 24 |
| — 下面全是"现在做不了" — | | |
| **B-1 SECURITY-HEAVY** | 本地可做但高危安全,需专注 PR | 3 |
| **B-2 INFRA-HARNESS** | 需先建测试/CI/沙箱/多节点 harness | ~13 |
| **B-3 SPEC/DESIGN-DECISION** | 需先裁规格/设计 | ~24 |
| **B-4 CONSENSUS** | 碰 state-root/genesis/receipt,需协调上线 | ~60 |
| **B-5 GREENFIELD** | 大型未起功能(IDE/前端 SDK/市场/新子系统) | ~60 |
| **B-6 OTHER-TEAM / 非本地 / CROSS-REPO** | CIP-2/3/4、gateway/console/builder/cowpilot/explorer/terraform 等不在本地 | ~95 |
| **B-7 epic(blocked/canceled/共识核心)** | CIP-22 blocked、CIP-10 canceled、WP-Consensus、CIP-23/25/30… | 见 §epic 表 |

---

## 🔻 2026-06-15 实测进度与纠偏(batch-issue-loop 跑过 F-0/F-1/F-2 后)

**实测结论:易档(F-0 / F-1 / F-2)到此全部清空或核实为非干净池。** 真上手逐条回代码后,F-1/F-2 与 6 月初一样仍系统性高估——"标题+轻核"定的档位经不起"验收能否本地跑通"的对抗式核验。

**已交付 / 已关(本轮)**
- **COW-202 + COW-231**(结构化 `pvm::host` tracing)→ node PR **#726 merged** → Done。
- **COW-363**(`cowboy secrets list` 只读 RPC `GET /cbss/secrets/{account}` + CLI)→ node PR **#727 merged** → Done。原标 F-1,实为"缺按-account 枚举后端"的 F-2,按点名升级实现。
- **COW-501 → Done**、**COW-400 → Duplicate**:WebFetch 实测 `https://docs.cowboy.inc/llms.txt` + `/llms-full.txt` 均 Mintlify 原生解析、发布时自动再生 → 零代码。

**F-0 已无可关**:69/387/46/1305/1751/914/928 已 Done;474/475 他人 In Review;2099 是 CIP-9 epic 伞(非 close 候选)。

**F-2 七条全非干净**(见下表逐条纠偏)。**F-3 example** 未跑(集成 flavor:需 release 二进制 + 本地 validator,偏 flaky;留作专门一轮)。

**往后只剩"重"票**(非自动 batch-loop fodder,需逐个慎做/要人拍板):B-1 安全专注 PR(926 等)、B-4 共识协调上线(~60)、B-2 先建 harness、B-3 设计裁定、B-5 绿地、B-6 非本地。

---

## ✅ F-0 — close 候选 ✅ 已全部消化(2026-06-15:无可关)

> 现状:7 已 Done(69/387/46/1305/1751/914/928)· 474/475 他人 In Review · 2099 = CIP-9 epic 伞。**已无 verify+close 余量。**

| Issue | 仓 | 证据 / 理由 |
|---|---|---|

| Issue | 仓 | 证据 / 理由 |
|---|---|---|
| COW-69 | node | `storage/src/timers.rs` 稀疏绝对高度索引已实现 CIP-1 §2.1 Tier-1 O(1) ring buffer |
| COW-474 | cowboy | `docs/operations/snapshots-and-restore.mdx` 已写(In Review) |
| COW-475 | cowboy | `docs/operations/incident-response.mdx` 已写(In Review) |
| COW-2099 | — | CIP-9 rewrite 三角 umbrella;子票已拆出 |
| COW-914 | cbfs | put-many commit 事件丢失已由 PR #22 修复(merged) |
| COW-928 | cbfs | OwnerCapTokenV1 mint+decode 已实现;"panic stub"在 #[test] 内 |
| COW-1305 | node | CIP-17 `/state/*`+block_hash+absent-200+prove? 默认已在 proof.rs |
| COW-1751 | node | CIP-17 proof 字段形状已按 §5.2/§7 impl-pinned 接受 |
| COW-46 | node | `@bounded_loop` 已随 SDK 发布(FSM await-bound) |
| COW-387 | node | errors.py 已带 HOST_ERROR_CODE/ERROR_SLUG 映射表 |

> 注:批量标 Done 需用户点名授权;每条建议关单前回代码再确认一次。

## ✅ F-1 — 真·易(S,≤1 天)✅ 已清空(2026-06-15)

> 真·干净本地批只有 202/231/363,均已交付+merge;400/501 原生关闭;其余早先排除。

| Issue | 仓 | 状态 / 做什么 |
|---|---|---|
| COW-202 | node | ✅ **Done**(PR #726):存储读写 → 结构化 `pvm::host` trace |
| COW-231 | node | ✅ **Done**(PR #726):host-call → 结构化 `pvm::host` trace |
| COW-363 | node/cli | ✅ **Done**(PR #727):`secrets list` 只读 RPC+CLI(实为 F-2:缺枚举后端) |
| COW-400 | cowboy | ✅ **Duplicate**(of 501) |
| COW-501 | cowboy | ✅ **Done**:`llms.txt`/`llms-full.txt` 实测 Mintlify 原生托管,零代码 |
| COW-1063 | node/rpc | 他人在途(PR #725,In Review) |
| COW-399 | node/cli | 早先 **Canceled** |
| COW-499 | cowboy | 早先 **In Review**(他人) |
| COW-940 | cbfs | ✗ 非干净:三问里两问需 devnet 遥测/漂移**实测数据** → 实为 B-3 设计裁定 |

## ⚠️ F-2 — 真·中(M,数天)❌ 2026-06-15 实测:七条全非干净,无一为自动 batch 批

> 逐条回代码后,F-2 全部落入 共识 / 设计裁定 / 集成 / 已被覆盖,**没有"纯加法、单测可验、非共识"的干净批**。

| Issue | 仓 | 实测纠偏 |
|---|---|---|
| COW-105 | node | ✗ **共识风险**:续体 resume-state 校验走 PVM 执行层,改校验可能动 accept/reject;验收模糊;续体本就是雷区(COW-824/2229)|
| COW-930 | cbfs | ✗ **设计裁定+绿地味**:描述开头即"decide before implementing,三选一架构",且翻转一个"by design 故意 defer"的特性 |
| COW-1329 | cowboy | ✗ **集成**:example 跑验,需 release 二进制+validator;归 F-3 |
| COW-1347 | node | ✗ **"Project:" 追踪伞**,无具体可交付 |
| COW-496 | node | ✗ **大概率已被 COW-386 覆盖**(devnet tip = `COW-386 enforce four-part error format across all error classes`);且错误文案进 receipt_root=共识风险 |
| COW-1893 | cbss(docs) | ✗ 规格文本裁定(词汇定义),非代码批 |
| COW-936 | cbfs | ✗ 价值有限(前提"零覆盖"已过时),边界开放 |

## ✅ F-3 — example 跑验(S;目录+demo.sh 已在 `cowboy/examples/`,接入 test_examples_local.sh)

工作 = 跑本地 validator 实测 + 修回归(非从零写)。已核验为纯 in-PVM/链上、**不需外部 LLM key**:

COW-1310/1311/1312/1315/1316/1317/1318/1319/1320/1321/1322/1323/1324/1325/1326/1327/1328/1331/1332/1333/1334/1335/1339/1340(共 24)。

> CI 全绿还依赖 Docker example harness(COW-1344,见 B-2)。

---

## ✗ B-1 — SECURITY-HEAVY(本地可做,但高危,需专注 PR,不可趁乱)

| Issue | 仓 | 为何高危 |
|---|---|---|
| COW-926 | cbfs | `/ras/` 全端点签名信封验证(cert+envelope sig、±30s、nonce LRU、aud/chain/network、revoked/expired、scope);一处写错=绕过 |
| COW-1057 | cbss | DKG sabotage 证据 + 持久化 DkgCeremonyRecord + post-rotate slashing |
| COW-1051 | cbss | DCAP/VLEK 厂商证书链 + CRL/TCB 校验(大密码学面) |

## ✗ B-2 — INFRA-HARNESS(需先建不存在的测试/CI/沙箱基建)

- **真 marshal Actor harness**(解锁 CIP-17 handler 测试):COW-1754、COW-1748
- **live PVM sandbox CI**:COW-993;**full-stdlib bundle / 跨平台 CI**:COW-1244、COW-1243
- **spawned 真-validator + cbssd 多节点 harness**(CBSS):COW-1050、COW-1052、COW-1054、COW-1053
- **runner↔cbfs 多进程 e2e**(git-dep 边界):COW-937;**relayer 发布管线/S3/OIDC**:COW-2205
- **Docker example harness**(绿地):COW-1344;**blob 生命周期测试依赖未实现 blob 基建**:COW-1258

## ✗ B-3 — SPEC / DESIGN-DECISION(需先裁规格或设计)

- **tx 编码 array-vs-map 未决**(连带一簇):COW-1945/1942/1943/1941/1937/1215/1753
- **裸 epic 无描述**(范围未定):COW-482(CLI)/492(SDK)/495/498(AI Context)
- **升级/迁移模型未设计**:COW-428/429/437/438
- **本地 dev 配置格式未定**:COW-373(cowboy.yaml/toml)
- **genesis 参数漂移需裁定**:COW-2266;**CIP-4↔CIP-9 rent-epoch 对齐**:COW-1256;**checkpoint 序列化格式**:COW-62;**entitlements 规格层**:COW-765;**bridge CIP 撰写**:COW-1073

## ✗ B-4 — CONSENSUS(碰 state-root/genesis/receipt,需协调上线;约 60 条)

代表簇:
- **CBFS 链上 RAS**(`node/execution/src/ras.rs`):2113/2114/2152/2184/921/894/927/929/938/1544/1545/1546;**PoR**:2112/917/918/919/2183
- **Economics/Genesis**:1259/1260/1261/1265/1266/1267/2019/2020/2021
- **tx/derivation**:1212(chain_id 签名)/177(tx version)/1944/1935/1934
- **token 新指令**:1074(permit)/1076(multicall)/1798(ICIP20)
- **timer**:1457/1458/1460;**governance**:1028/1029/1012;**session escrow**:1542
- **PVM 执行语义**(改 accept/reject 或 gas→receipt):94/119/137/1239/1240/1241/1248/1249/1255/2054/2055
- **CBSS 链上态**:1056/1058/1894/1895;**事件基建**:2235/2178

## ✗ B-5 — GREENFIELD(大型未起;约 60 条)

- **前端/工具绿地**:Frontend JS SDK(432-436)、IDE/VS Code(390/391/395/396/398/421/445)、模板库(403-407)、playground/explorer/marketplace/registry(439-444)、CLI 新子系统(414/415/418/420)、可观测 UI(423-426)
- **CIP 子系统绿地**(见 §epic):CIP-28 银行、CIP-14 DNS、CIP-23 TEE、CIP-25 跨链、CIP-19 MCP、CIP-18 支付、CIP-16 域名、CIP-30 storage-root、CIP-11 连接、CIP-7 watchtower
- **本仓绿地**:987(runtime.mount host API)、988(@on_stream,blocked CIP-7)、1543(链事件订阅)、1637/1640/1642(CIP-12 circuit-breaker)、1365

## ✗ B-6 — OTHER-TEAM / 非本地 / CROSS-REPO(约 95 条,本地工作区做不了)

- **他团队 CIP-2/3/4**:CIP-2(10)、CIP-3(14,含 117/1254/1255/2268/2269)、CIP-4(11)
- **gateway 仓不在本地**:877/878/879/882-903/883/886/924/2186(整簇)
- **ops/infra 仓**:508/513/514/515/462/473/427/751
- **console / cowpilot / wallet / explorer / indexer / lasso 等独立产品**:823/525/526/527/1082/2258/2231/2172/416/419/401/986
- **Builder 产品(全部 11 条,代码不在工作区)**:2207-2216/2257
- **standalone cowboy pip 包不在工作区**:992;**registry-proto 跨语言**:2115

## ✗ B-7 — epic / blocked / canceled(项目层级,按 epic 规划)

| 项目 | 条数 | 根因 |
|---|---|---|
| CIP-22 连续清算拍卖 | 39 | **Blocked on CIP-21** |
| CIP-11 Runner 连接/推送 | 33 | 绿地协议(QUIC/presence) |
| CIP-19 Gateway MCP | 30 | 绿地 gateway |
| CIP-28 Agent Banking | 27 | 绿地子系统 |
| CIP-14 DNS-Addressable | 21 | 绿地子系统 |
| CIP-10 容器运行时 | 21 | **已 Canceled** |
| WP-Consensus/P2P/随机 | 20 | 共识核心 |
| CIP-23 TEE/CAE | 20 | 绿地子系统 |
| CIP-18 Payments | 20 | 绿地子系统 |
| CIP-16 自定义域名 | 20 | 绿地 + 跨仓 |
| CIP-21 DEX/流动性池 | 18 | 绿地 examples |
| CIP-25 跨链 | 17 | 绿地子系统 |
| CIP-29 事件钩子 | 12 | 共识/子系统 |
| CIP-30 Per-Actor Storage Root | 10 | 共识 state-root |
| CIP-7 Watchtower | 5 | 绿地协议 |

---

## 一句话

~~真正现在能本地交付的只有 ~26 条(10 close + 9 易 + 7 中)外加 24 example~~ —— **2026-06-15 修正:这个估计仍偏乐观。** 实测后 F-0/F-1/F-2 三个易档全部清空或核实为非干净:本轮真正干净交付的只有 **3 条代码批**(COW-202/231/363,2 个 PR 已 merge)+ **2 条原生关闭**(COW-400/501)。F-0 已无可关。

**剩下的全是"重"票**,无一为自动 batch-loop fodder:
- **F-3 example**(24):本地可跑但偏集成(需 release 二进制 + validator),留作专门一轮;
- **B-1 安全专注 PR**(3,如 COW-926 `/ras/` 签名信封全验证)——高危,一处错=绕过,必须单独专注做;
- **B-2 先建 harness**(~13)——一次性解锁 CIP-17 handler 测试 / CBSS e2e / example CI 一批,投资回报最高;
- **B-3 设计裁定 / B-4 共识协调上线(~60)/ B-5 绿地 / B-6 非本地** —— 需人拍板或协调上线。

**推荐下一步**:① 就此收尾;或 ② 先投 B-2 一个 harness(把"没法本地测"的根因解决,为后续批量铺路);或 ③ 点一个具体 B-1/B-4 重票专注做。教训重申:档位务必在真上手前逐条回代码验"验收能否本地跑通",别信"标题+轻核"。
