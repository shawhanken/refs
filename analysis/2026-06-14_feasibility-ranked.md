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
| **B-1 SECURITY-HEAVY** | 926→#732、2274→#733、1057→#735;**2026-06-17 审计修复战役再清 10 条 MED/LOW + 7 HIGH 全闭环**(15 PR,见 §2026-06-17);剩余审计 3 簇仅残留(2306 限流/认证、2310、pvm) | 清零→审计批 |
| **B-2 INFRA-HARNESS** | 需先建测试/CI/沙箱/多节点 harness | ~13 |
| **B-3 SPEC/DESIGN-DECISION** | 需先裁规格/设计(tx 编码簇 8 条 2026-06-16 攻坚中→node #742 等,待 flag-day) | ~24 |
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

## 🔻 2026-06-15(续)— F-3 跑验 + B-2/B-1 攻坚(同会话延长)

清完易档后继续往"重"票推进,又攻下三块:

**F-3 example 全 24 条清空(GLM runner 解锁)。** 起本地 validator + 实跑 28 个 example harness:10 纯链上直接绿;17 因"无 runner"挂。用户提供 GLM(智谱)key → `cargo build --release --bin runner-node` + faucet 注资 + CLI 注册(stake 10k)+ daemon(`OPENAI_API_BASE=open.bigmodel.cn` `LLM_MODEL=glm-4-flash`,付费模型余额不足只 flash 可用)→ 13 个 runner-gated 转绿 verify+close;唯一真 bug = **18-ring(COW-1327)**:SDK 现强制 deny-by-default,handler 缺 `@public` → cowboy PR **#186 merged**。10+13 verify+close(COW-1310…1340 等),F-3 = 0 剩。

**B-2:PVM determinism 测试线全激活(两 PR)。**
- **COW-1244 → node #730 merged**:determinism.rs 全 `#[ignore]` 的根因不是"stdlib 缺",是 **thread-local 解释器池跨测试重初始化污染**(hash_seed 类单跑过/合跑 panic)——`rusty_fork_test!`(每测试 fork 独立进程)修好。这也是反复咬人的 PVM warm-pool 测试顺序雷根因。
- **COW-2273 → node #731 merged**:剩余 import 测试(json/math)失败 **不是 bundle 缺 C-ext**(我先误判、本文档原描述也错),三档诊断锁定:`import math` 无 determinism=Ok,`deterministic(None)`=Forbidden,`actor_execution()`=Ok → 测试用了**过窄配置**,改用生产 `actor_execution()` → 全绿。**教训:PVM determinism 测试必用 actor_execution()。**
- **COW-993(continuation E2E)= 续体雷区**(checkpoint save 工作,但 resume 挂 Err(Internal)+测试代码畸形)→ 退回 Backlog 附笔记,非干净 playbook 能解。

**B-1 安全:COW-926 /ras/ 签名信封验证 MVP → node #732 merged(Marshal needs_human)。** 纠偏:**服务端验证在 node/rpc(非 cbfs;cbfs 只签名)**;现状只验 cert 不验请求信封→captured 头可重放篡改请求。新增 `verify_request_envelope`(Ed25519 请求签名 + ±30s 窗 + 60s nonce 重放 cache),接 2 个 GET owner 端点,3 验收单测证实。POST mutations + revocation = follow-up **COW-2274**。

**follow-up 子票:** COW-2272(wallet 解码器)、COW-2274(/ras/ POST + revocation);COW-2273 已闭。

**本会话累计:7 PR 全 merged(node #726/#727/#728/#730/#731/#732 + cowboy #186)。** 易档(F-0/1/2/3)清空 + B-2 harness 一块(determinism)+ B-1 安全起步(926 MVP)。剩 B-4 共识(~60)/ B-2 其余 harness(CBSS/cbfs 跨仓、continuation 雷区)/ B-3/B-5/B-6 仍需逐个慎做。

## 🔻 2026-06-15(再续)— B-1 安全两票(易档已空,逐个点名做)

易档确认彻底耗尽(picker 只返回 CIP-28 绿地+共识簇,护栏拒绝)。按用户指引继续挑 B-1 安全票,交付 2 个(均 **In Review,等人工 merge**;Marshal 判 needs_human ≠ 代码缺陷,皆共识/跨仓需协调上线):

- **COW-2274 → node PR #733**(926 follow-up):`/ras/` 控制面**签名信封 + 链上吊销**。8 端点(6 POST + 2 GET)raw-body `Bytes` 在 JSON 解析前验签(canonical 含 `Keccak256(body)`);`is_delegation_revoked` + `verify_authenticated_envelope_checked` 补齐 926 推迟的 "cert not revoked"。**加固轮**:再接 cbss-rewrap/mount-allowlist 2 POST + 2 GET 改 `OriginalUri`(主路由零回归)。顺手修 2 个 ras.rs 源扫描 guard 误报 bug(`ras_usage_report` 扫到 EOF、整文件 consensus-write 扫描误伤测试)。不变量 6/6、Almanax 0、对抗 review 无 high/crit、`cargo test --workspace` 绿。**needs_human 因**:信封无条件强制,cbfs 客户端须先签 POST 信封否则 401(延续 #732 的 GET rollout)。
- **COW-1057 → node PR #735**(CIP-24 CBSS):`DkgCeremonyRecord` 让 DKG sabotage 在 `ExpireDkgPending` 后仍可 slash(verifier 回退持久化记录;rotate 删、expire 留)。不变量 6/6(含 cbss wire round-trip + econ)、Almanax 0、`cargo test --workspace` 绿。对抗 review **6/7 维干净**,一条 **MEDIUM**:`(scope,epoch)` 记录在 expire→重发同 scope 时被覆盖→首个 ceremony 的恶意 dealer 重新逃逸——**非回归**(严格优于原状)、**非误罚**(签名绑定委员会);已在代码内注明。**全 fix** 需 evidence wire 带 per-ceremony id(跨仓 node+runner/cbss,follow-up,因 auto-mode 拒建票未单独立票,折进 PR/issue 评论)。**needs_human 因**:新持久化态 + slashing 可达性=共识变更,需协调上线 + 人裁 clobber 限制是否可接受。

**本会话(再续)累计:node #733 + #735(各含加固/注记提交),均 In Review 待人工 merge。** B-1 安全票最后一条 **COW-1051** 回代码核实后**退回 Backlog + 写 scoping 评论**:链上现状=只对治理预注册可信公钥验 quote 签名,**零厂商凭据验证**;runner-tee 944 行是自生成 key 的模拟。COW-1051=从零造共识关键 TEE 验证器(无 x509/dcap 依赖、须确定性 block-time X.509、缺真实 Intel/AMD 测试向量、**需先做 CIP-24 §3.8 设计裁定=实为 B-3**、CIP-23/24 跨团队多周活)。**不硬上半成品/合成向量**(安全验证器假绿比不做更糟)。**B-1 安全档至此全部处理完毕,自动 batch-loop fodder 彻底清零**——往后纯靠用户逐个点名重票(B-4 共识/B-3 设计/B-5 绿地/B-6 非本地)。

> 运维记:本环境 SSH(22)push github 卡死 → 改 `gh auth setup-git` + HTTPS push。auto-mode 拒绝未经明确请求的新建 Linear issue → follow-up 折进现有评论。

---

## 🔻 2026-06-16 — B-3 tx 编码簇攻坚 + 五仓全量审计 + CIP-24/23 联审

易档早已空,本日全在"重"票:一次裁掉了一整个 **B-3 簇**、把审计护栏铺进五仓、并联审两条 CIP。

**B-3 tx 规范化编码簇 → 三仓 flag-day 在途(原列 B-3 的整簇 + B-4 的 1212 一并消化)。**
- **node PR #742(OPEN, draft)**:`COW-1942` 主票,折入原 B-3 簇 **1945/1943/1941/1937/1215/1753** + 原 B-4 **1212(chain_id 签名)**。serde-CBOR → commonware-codec 规范编码 + `chain_id` 防重放 + 反 malleability + 冻结测试向量;11 commit、6 轮审计、subagent-driven;最终全息 review 抓到 per-task 漏的 **CLI chain_id CRITICAL**;workspace 4358 测试绿。Marshal **needs_human**(共识 flag-day,待协调上线)。
- **node PR #743(MERGED)**:严格 `Message`/`Receipt` codec 解码(state-root 反 malleability,B7),配合 #742 收紧 wire。
- **wallet PR #14(OPEN)**:钱包换 commonware-codec(Plan B),对 node #742 `tx_vectors.rs` 三方逐字节核对全中;Marshal **pass**。潜伏 LOW:`additional_signers` 缺 20B 地址(v1 恒 `[]` 休眠)。部署前须对 #742 合并 commit 重核。
- **cowboy PR #191(OPEN)**:白皮书 §2 + Appendix A 落同一字节契约(Plan C)。
- → **B-3 tx 簇(1945/1942/1943/1941/1937/1215/1753)+ B-4 的 1212 从"未决"转"在途待 flag-day"**,见下表已划线。

**五仓全量代码审计(9 并行 agent 对抗审)→ 7 条确认 HIGH/CRITICAL(均现网),已起棘轮护栏并落地。** 报告 `refs/analysis/2026-06-16_*`。确认项:C1 pvm `import os` 绕沙箱(CRITICAL,探针复核)/ C2 cbfs `owner_signature` 零校验 / C3 重复结算 / C4 延迟费铸造 / C5 CBSS None 跨账户外泄 / C6 `active_jobs` 死读 / C7 receipt 指针分叉。已转 Linear 票 + 合入 ratchet 回归门禁:
- node **#739 MERGED**(COW-2284,blacklisted module 即便预缓存也须拦 = C1)、**#741 MERGED**(COW-2286,job 至多结算一次 = C3 双花 escrow drain)、**#740 MERGED**(COW-2288 CBSS None-policy + COW-2303 upgrade param-drop = C5)、**#738 MERGED**(COW-2297 `token_mint` 须校验 `mint_authority` = C4 类)。

**其他本地 merged:** node **#737**(COW-2277 storage epoch 边界 O(history) CPU grind 修复)、**#728**(COW-2258 indexer session/cip29 receipt 事件结构化解码器)、runner **#117**(COW-2278 job-result nonce 撞 heartbeat 修复)。

**CIP 联审(review-only,非可行性交付):**
- **CIP-24 inbound-verify 三仓**:cowboy **#185** + node **#729** Marshal needs_human / runner **#116** pass。node #729 抓到 **1703 错误码冲突**(`SecretAccessDenied` ↔ `LibCapExceeded`)→ 棘轮 `esc-20260615`;runner #116 安全过硬但 release-failure 误当终态(liveness MEDIUM)。三仓须协同上线。
- **CIP-23 v3 TEE**:cowboy PR **#188**,Marshal needs_human;两疑似矛盾(§3.2 地址/opcodes)回代码核对均驳回;棘轮 `esc-20260616-cip23-chip-root-determinism` 占坑。

> 小结:本日无"易档新增交付"(易档确已空);进展全在 B-3 簇协调推进 + 审计护栏铺设 + CIP 联审。tx 编码簇、CIP-24、CIP-23 三组均 needs_human / flag-day,等人工协调上线。

---

## 🔻 2026-06-17 — 五仓审计修复战役(15 PR;HIGH 池全清 + 10 条 MED/LOW)

把 2026-06-16 审计起的棘轮护栏**逐条实作修复**。一个会话交付 **15 个 PR**(跨 node/runner/cbss/cbfs),**7 条确认 HIGH(C1–C7)全部闭环**,外加 10 条 MED/LOW。每条走完整闭环:前提回 devnet/main tip 核实 → TDD + **实作原本"假绿"的棘轮 invariant 测试** → 全 workspace 0 失败 → 对抗式 review → `gate-record`(run 206–218)→ 英文 PR/Linear 评论 → In Review。

**HIGH(C1–C7)收口表:**

| 发现 | 交付 | Marshal |
|---|---|---|
| C1 pvm `import os` 绕沙箱 | node #739(ratchet,早先 merged) | — |
| C2 cbfs `owner_signature` 零校验 | COW-2285 Done(早先) | — |
| C3 runner 重复结算 | node #741(早先 merged) | — |
| **C4 延迟费铸进 burn sink** | **node #749** | needs_human |
| C5 CBSS None 跨账户外泄 | node #740(早先 merged) | — |
| **C6 `active_jobs` 死计数 + 聚合质押** | **node #747** | needs_human |
| **C7 heap 指针进 `receipt_root` fork** | **node #752** | needs_human |

**MED/LOW(本战役 11 条):**
- cbfs **#53**(COW-2304:PutShard 不验 shard_id 派生 → 持卷 A cap 覆写卷 B 字节投毒;store 层卷绑定,**仅跨卷且字节真变才拒**)→ **Marshal PASS**(对抗 review 自审抓到首版会误杀内容定址 manifest-node dedup → 改 byte-change-gated;非共识、无 wire 改)。
- cbss **#30**(COW-2306:`read_frame` 按声明 len 全量预分配 → 未认证者 16MiB×256 流不发 body = 4GiB RSS 放大;改 64KiB 分块增量读、单超时)→ **Marshal PASS**(只做放大 primitive;per-IP 限流 + 客户端认证[CIP-24 app 层设计]留 follow-up;`CountingReader` 测断言单读 ≤ chunk;非共识)。
- runner **#120**(COW-2295/2296:secret 进日志脱敏 + SSRF guard + 禁跟随重定向)→ **MERGED**(对抗 review 当场抓到我自己 PR 里的 redirect 绕过并同环修)。
- node **#750**(COW-2298:per-height timer list 无界 → 永久 halt DoS;写前 cap + 拒绝须 recoverable)→ needs_human。
- node **#751**(COW-2299:跨 actor 重入 root → 陈旧读/丢写;`active_call_actors` 集中守卫,call_actor + emit sync-fire 两路)→ needs_human(对抗 review 抓到 emit 同源后门)。
- node **#753**(COW-2294:token-hook cap 漏 storage-read gas → 结算移到 `restore_limit` 前)→ needs_human。
- node **#754**(COW-2308/2309:mempool 延迟队列加 count cap + 防饿死 user tx)→ **Marshal PASS**(非共识:`next()` 只在 propose,不在 verify)。
- node **#755**(COW-2307:block `extra_data` 排除出 digest → wire malleability;**仅非空才** length-prefixed fold = 向后兼容空块、无硬分叉)→ needs_human。
- cbss **#29**(COW-2305:PartialSign 无 replay 防护;bounded `ServedRequests` dedup,reject-before-authorize + insert-on-success)→ needs_human(reject vs 幂等 re-serve 的 retry/liveness 权衡留人裁)。
- node **#756**(COW-2293:`2**20000`/`1<<20000` 常量折叠绕 4096-bit 守卫;validate_actor_code 加 AST 检查,**整数 ilog2 上界**判位长——自审抓到初版 float `log2` 跨 libm 末位差会 fork deploy gate 并改回整数)→ needs_human。残留裸大 hex 字面量 + 完整修=pvm/ 运行时守卫。
- node **#748**:清掉 devnet tip 上误提交的 COW-951 旧 `plan.md`。

**对抗式 review 当场抓到并同环修的真 bug**:① COW-2289 cancel 路径漏清 in-flight 索引(永久 over-count);② COW-2299 CIP-29 emit sync-fire 与 call_actor 同源的重入后门(只守 call_actor 会让棘轮假绿)。

**经验沉淀**(已入记忆,可复用):halt 修复必须确保拒绝本身 recoverable(否则把 halt 搬家);共识文本脱敏选共识边界而非 pvm/(node CI 不跑 pvm/ workspace = 盲区);mempool 改动先确认 `next()` 不在 verify = 非共识;econ 守恒用代数 proptest 别驱动全 PVM;向后兼容 fold 用"仅非空才 append";审切帧/重入查**所有** snapshot substrate 调用点;审 active 棘轮 invariant 必核 `location_test` 真存在(否则 `running 0 tests` 假绿);cbss/cbfs base = **main**(非 devnet);cbss e2e 从 worktree 必挂(硬编码 `../../../node`);Clone 结构体加守卫字段用 `Arc<Mutex<>>`。

**审计池剩余 3 簇 = 全非干净本地修**(已逐条核 premise;2293 的 node 侧 deploy-gate 部分已于 #756 拿下,留 pvm/ 运行时完整修;2304 已由 #53 拿下,完整密码学绑定留 follow-up):

| 剩余 | 为何非干净 |
|---|---|
| cbss **2306 残留** | 放大 primitive 已由 #30 拿下;**per-IP 限流**(transport 建设)+ **客户端认证**(CIP-24 app 层设计,需裁定)留 follow-up |
| cbss **2310**(LOW) | round 消息不带 `epoch` → 修需加字段(wire + flag-day),或"拒重叠 start"语义不明(恐坏 reshare) |
| pvm/ **2291/2292** + 2293 残留 | 确定性 `id()`/沙箱模块需 attribute 级隔离;2293 完整修=运行时 int 物化守卫(裸大 hex 字面量)= pvm/ CI 盲区 |

> 小结:**node 侧可乾净本地交付的审计票已耗尽**(#756 拿下 2293 的 node deploy-gate 部分后);HIGH 安全池全清;cbfs 2304 投毒已由 #53 store 层卷绑定拿下(Marshal PASS)。剩余 MED/LOW 均需协议/wire 改、设计裁定或 pvm/ 慢工,非"快速继续"。共识修复一律 needs_human 等协调 flag-day 上线(非共识已 PASS:#754 mempool、cbfs #53;#120 runner 已 merged)。

---

## ✅ F-0 — close 候选 ✅ 已全部消化(2026-06-15:无可关)

> 现状:7 已 Done(69/387/46/1305/1751/914/928)· 474/475 他人 In Review · 2099 = CIP-9 epic 伞。**已无 verify+close 余量。**

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

> **进度(2026-06-15):B-1 全部处理完。** 926 MVP→#732 merged;follow-up 2274→#733、1057→#735(In Review,Marshal needs_human,等人工 merge);1051 回代码核实=共识关键 TEE 验证器从零造、需设计裁定+真实向量 → **退回 Backlog + scoping 评论**(详见下表)。

| Issue | 仓 | 状态 / 为何高危 |
|---|---|---|
| COW-926 | node/rpc | ✅ MVP **#732 merged**(服务端验证在 node/rpc,非 cbfs);follow-up COW-2274 |
| COW-2274 | node/rpc | ✅ **PR #733**(In Review):`/ras/` POST 信封 + 吊销,8 端点;需人裁 cbfs 客户端 rollout 排序 |
| COW-1057 | node/cbss | ✅ **PR #735**(In Review):DkgCeremonyRecord 让 sabotage 在 expire 后仍可 slash;共识相关 + MEDIUM clobber 限制待人裁 |
| COW-1051 | node/execution + cbss/runner-tee | ⛔ **退回 Backlog + scoping 评论**:链上现状只验治理预注册公钥=零厂商凭据;从零造共识关键 DCAP/VLEK 验证器(无 x509/dcap 依赖、须确定性 block-time、缺真实 Intel/AMD 向量、**需先 CIP-24 §3.8 设计裁定=实为 B-3**、CIP-23/24 跨团队多周)。不硬上半成品 |

## ✗ B-2 — INFRA-HARNESS(需先建不存在的测试/CI/沙箱基建)

- **真 marshal Actor harness**(解锁 CIP-17 handler 测试):COW-1754、COW-1748
- **live PVM sandbox CI**:COW-993;**full-stdlib bundle / 跨平台 CI**:COW-1244、COW-1243
- **spawned 真-validator + cbssd 多节点 harness**(CBSS):COW-1050、COW-1052、COW-1054、COW-1053
- **runner↔cbfs 多进程 e2e**(git-dep 边界):COW-937;**relayer 发布管线/S3/OIDC**:COW-2205
- **Docker example harness**(绿地):COW-1344;**blob 生命周期测试依赖未实现 blob 基建**:COW-1258

## ✗ B-3 — SPEC / DESIGN-DECISION(需先裁规格或设计)

- ~~**tx 编码 array-vs-map 未决**(连带一簇):COW-1945/1942/1943/1941/1937/1215/1753~~ → **2026-06-16 攻坚中**:整簇折入 node PR **#742**(canonical commonware-codec + replay/malleability)+ #743(MERGED)+ wallet #14 + cowboy #191;Marshal needs_human,共识 flag-day 待协调上线
- **裸 epic 无描述**(范围未定):COW-482(CLI)/492(SDK)/495/498(AI Context)
- **升级/迁移模型未设计**:COW-428/429/437/438
- **本地 dev 配置格式未定**:COW-373(cowboy.yaml/toml)
- **genesis 参数漂移需裁定**:COW-2266;**CIP-4↔CIP-9 rent-epoch 对齐**:COW-1256;**checkpoint 序列化格式**:COW-62;**entitlements 规格层**:COW-765;**bridge CIP 撰写**:COW-1073

## ✗ B-4 — CONSENSUS(碰 state-root/genesis/receipt,需协调上线;约 60 条)

代表簇:
- **CBFS 链上 RAS**(`node/execution/src/ras.rs`):2113/2114/2152/2184/921/894/927/929/938/1544/1545/1546;**PoR**:2112/917/918/919/2183
- **Economics/Genesis**:1259/1260/1261/1265/1266/1267/2019/2020/2021
- **tx/derivation**:~~1212(chain_id 签名)~~ → **2026-06-16 折入 node PR #742**(tx-canonical 簇,待 flag-day);177(tx version)/1944/1935/1934
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

> **2026-06-17 终态**:易档(F-0/1/2/3)早已清空;6-16 五仓审计起的 **7 条 HIGH(C1–C7)+ 10 条 MED/LOW 已全部修复交付**(15 PR,见 §2026-06-17 段;runner #120 已 merged、其余 In Review)。**node 侧可乾净本地交付的审计票至此耗尽**;cbfs 2304 投毒(#53)、cbss 2306 预分配放大(#30)均已干净拿下(Marshal PASS)。审计池仅剩残留:cbss 2306 的 per-IP 限流/客户端认证、cbss 2310、pvm 2291・2293・2292 —— 全需协议/wire 改、设计裁定或 pvm/ CI 盲区。共识修复一律 needs_human 等 flag-day。

~~真正现在能本地交付的只有 ~26 条(10 close + 9 易 + 7 中)外加 24 example~~ —— **2026-06-15 修正:这个估计仍偏乐观。** 实测后 F-0/F-1/F-2 三个易档全部清空或核实为非干净:本轮真正干净交付的只有 **3 条代码批**(COW-202/231/363,2 个 PR 已 merge)+ **2 条原生关闭**(COW-400/501)。F-0 已无可关。

**剩下的全是"重"票**,无一为自动 batch-loop fodder:
- **F-3 example**(24):本地可跑但偏集成(需 release 二进制 + validator),留作专门一轮;
- **B-1 安全专注 PR**(3,如 COW-926 `/ras/` 签名信封全验证)——高危,一处错=绕过,必须单独专注做;
- **B-2 先建 harness**(~13)——一次性解锁 CIP-17 handler 测试 / CBSS e2e / example CI 一批,投资回报最高;
- **B-3 设计裁定 / B-4 共识协调上线(~60)/ B-5 绿地 / B-6 非本地** —— 需人拍板或协调上线。

**推荐下一步**:① 就此收尾;或 ② 先投 B-2 一个 harness(把"没法本地测"的根因解决,为后续批量铺路);或 ③ 点一个具体 B-1/B-4 重票专注做。教训重申:档位务必在真上手前逐条回代码验"验收能否本地跑通",别信"标题+轻核"。
