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
| **F-0 close 候选** | 已实作,核验后即可关单(几乎零成本) | 10 |
| **F-1 真·易(S,≤1天)** | 本地可改可测的小活 | 9 |
| **F-2 真·中(M,数天)** | 本地可改可测,边界较大 | 7 |
| **F-3 example 跑验** | 目录+demo.sh 已在,跑本地 validator 验证/修回归 | 24 |
| — 下面全是"现在做不了" — | | |
| **B-1 SECURITY-HEAVY** | 本地可做但高危安全,需专注 PR | 3 |
| **B-2 INFRA-HARNESS** | 需先建测试/CI/沙箱/多节点 harness | ~13 |
| **B-3 SPEC/DESIGN-DECISION** | 需先裁规格/设计 | ~24 |
| **B-4 CONSENSUS** | 碰 state-root/genesis/receipt,需协调上线 | ~60 |
| **B-5 GREENFIELD** | 大型未起功能(IDE/前端 SDK/市场/新子系统) | ~60 |
| **B-6 OTHER-TEAM / 非本地 / CROSS-REPO** | CIP-2/3/4、gateway/console/builder/cowpilot/explorer/terraform 等不在本地 | ~95 |
| **B-7 epic(blocked/canceled/共识核心)** | CIP-22 blocked、CIP-10 canceled、WP-Consensus、CIP-23/25/30… | 见 §epic 表 |

---

## ✅ F-0 — close 候选(先核验再点名关单,最划算)

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

## ✅ F-1 — 真·易(S,≤1 天,本地可改可测)

| Issue | 仓 | 做什么 |
|---|---|---|
| COW-363 | node/cli | 补 `cowboy secrets list` 变体(set/policy/delete 已 ship) |
| COW-1063 | node/rpc | CBSS handler 404/410/409 分支测试(逻辑已在,扩 CbssTestStore fixture) |
| COW-231 | node | PvmHost host-call 调用 tracing(纯 observability,不碰共识) |
| COW-202 | node | 存储读写 access logging(纯 observability) |
| COW-399 | node/cli | `cowboy init` 输出加 `.cursorrules`(验证文件写出) |
| COW-499 | cowboy | 从 canonical SKILL.md 打包 per-platform AI-context adapters |
| COW-400 / COW-501 | cowboy | 生成 docs 根 `llms.txt`(两条近重复,建议合并) |
| COW-940 | cbfs | 裁定 PoD 频率/打分权重/clock-skew 并落为 cbfs 常量(skew 常量已在) |

## ✅ F-2 — 真·中(M,数天,本地可改可测)

| Issue | 仓 | 做什么 / 注意 |
|---|---|---|
| COW-105 | node | continuation resume-state 校验 + 测试 |
| COW-1329 | cowboy | 19-texas-holdem 写 README + 接入 test_examples_local.sh + 跑通 |
| COW-1347 | node | 保持 CLI/read 语义与 examples 兼容(本地 example sweep 验证) |
| COW-930 | cbfs | Cowboy-mode `cbfs mount` token-refresh 设计+实现(无共识/peer-fetch) |
| COW-496 | node | 错误信息改四段式 —— ⚠ 只动文案,**勿改错误码/字段语义**(进 receipt_root=共识) |
| COW-1893 | cbss(docs) | 定义 CIP-24 §5.3 canonical 错误词汇(规格文本;代码侧塌缩=共识,不在此) |
| COW-936 | cbfs | 给低覆盖包补测试(前提"零覆盖"已过时,价值有限,边界开放) |

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

**真正现在能本地交付的只有 ~26 条**(10 close 候选 + 9 易 + 7 中)外加 24 条 example 跑验;其余 ~535 条
被「共识 / 缺基建 / 绿地 / 他团队·非本地」四类挡住。建议拿取顺序:**F-0 → F-1 → F-2 → F-3**,然后才考虑
B-1(926 等安全,专注做)或先投资 B-2 的 harness(一次性解锁 CIP-17 测试、CBSS e2e、example CI 等一批)。
