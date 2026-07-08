# 可行性重排 — 由易到难(2026-06-14,Linear 实时全量)

**范围:** Linear COW 团队,state ∉ {completed, canceled},assignee ∈ {pavilionledger(PL), 未指派}。
- **2026-06-14 基线:619 条**(541 Backlog / 67 Todo / 6 In Review / 5 In Progress;502 未指派 / 117 PL)。
- **2026-06-17 实时复核:574 条**(525 Backlog / 43 Todo / 4 In Progress / 1 In Review / 1 Duplicate;486 未指派 / 88 PL)。净 **−45**(PL 117→88、未指派 502→486);见 §2026-06-17(实时复核)。
- **2026-06-19 实时复核:563 → 546 条**(本会话:#780/COW-95 + **#788/COW-1029** 均 merged→devnet 转 Done;关 4 张 stale 1405→Done、175/1306/1307→Canceled;3-agent sweep 后再清 **11 张已修批** 701/220/720/1002/119/1234/1266/1267/1374/1375/1642→Done)。累计本会话 **−17**(2 交付 + 15 关单);§2026-06-18 的整批 node 交付已 reconcile 为 Done + merged→devnet,见 §2026-06-19 三段。

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
| **B-1 SECURITY-HEAVY** | 926→#732、2274→#733、1057→#735;**2026-06-17 审计修复战役再清 12 条 MED/LOW + 7 HIGH 全闭环**(17 PR,见 §2026-06-17);剩余审计 2 簇仅残留(2306 限流/认证、pvm 2291/2293残留) | 清零→审计批 |
| **B-2 INFRA-HARNESS** | 需先建测试/CI/沙箱/多节点 harness;**2026-06-17 pvm CI 盲区收口**:test-pvm 去 -E filter 跑整个 pvm-runtime crate(node #758,本地 243 过、**CI 已绿**)→ 新 pvm 测试自动覆盖、堵 #366/#665 类盲区根源 | ~13 |
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

## 🔻 2026-06-17 — 五仓审计修复战役(17 PR;HIGH 池全清 + 12 条 MED/LOW)

把 2026-06-16 审计起的棘轮护栏**逐条实作修复**。一个会话交付 **17 个 PR**(跨 node/runner/cbss/cbfs),**7 条确认 HIGH(C1–C7)全部闭环**,外加 12 条 MED/LOW。每条走完整闭环:前提回 devnet/main tip 核实 → TDD + **实作原本"假绿"的棘轮 invariant 测试** → 全 workspace 0 失败 → 对抗式 review → `gate-record`(run 206–220)→ 英文 PR/Linear 评论 → In Review。

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

**MED/LOW(本战役 13 条):**
- cbfs **#53**(COW-2304:PutShard 不验 shard_id 派生 → 持卷 A cap 覆写卷 B 字节投毒;store 层卷绑定,**仅跨卷且字节真变才拒**)→ **Marshal PASS**(对抗 review 自审抓到首版会误杀内容定址 manifest-node dedup → 改 byte-change-gated;非共识、无 wire 改)。
- cbss **#30**(COW-2306:`read_frame` 按声明 len 全量预分配 → 未认证者 16MiB×256 流不发 body = 4GiB RSS 放大;改 64KiB 分块增量读、单超时)→ **Marshal PASS**(只做放大 primitive;per-IP 限流 + 客户端认证[CIP-24 app 层设计]留 follow-up;`CountingReader` 测断言单读 ≤ chunk;非共识)。
- cbss **#31**(COW-2310:无 epoch 的 round 消息按 scope+kind 查 HashMap → 同 scope 两未 finalize 仪式绑错;取拒重叠方案,`insert_new_ceremony` 拒同(scope,kind)异 epoch 在飞,5 个 insert 站全走)→ **Marshal PASS**(无 wire 改;liveness:内存态+链强制单活+重启清,supersede 否决因需清 3 张侧表;非共识)。
- node **#757**(COW-2292:socket/subprocess/select/signal/threading/ssl/inspect actor 可直接 import 上链零拦截[只 --strict linter];`validate_actor_code` 加 check#7 AST 拒,dotted-root 匹配)→ **needs_human**(共识 flag-day;**选 deploy-gate 非 runtime blacklist 因后者炸 SDK**——gate 只扫 actor 源、preamble 执行层单独注入,已核实 code_bytes=StatePrefix::Code;动态 __import__ 残留)。
- node **#759**(COW-2293 残留①:裸大整数字面量 `0xFFFF…`/`1_000…` 绕 #756 expr 检查+#3 源串扫;`validate_actor_code` 加 check#8 AST 扫所有 base 超 4096-bit 字面量,**源文本切片取位长**[ruff Int 无 bit_length]、整数算位长非 float、自审闭 `_` 分隔十进制姊妹绕过)→ **needs_human**(共识 flag-day)。
- cbss **#32**(COW-2306 残留:accept loop 无 per-source 限→单 peer 占满 256 全局槽饿死他人;加 per-IP 并发连接 cap=16,握手前 `incoming.refuse()`、RAII prune、**loopback 豁免**保本地多节点)→ **Marshal PASS**(非共识;残留客户端认证=CIP-24 设计裁定)。
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

**审计池剩余 2 簇 = 全非干净本地修**(已逐条核 premise;2293 的 node 侧 deploy-gate 部分已于 #756 拿下,留 pvm/ 运行时完整修;2304 已由 #53 拿下,完整密码学绑定留 follow-up):

| 剩余 | 为何非干净 |
|---|---|
| cbss **2306 残留** | 放大 primitive #30、per-IP 限流 #32 均已拿下;**仅剩客户端认证**(`with_no_client_auth`=CIP-24 app 层 auth 设计,需治理裁定才动) |
| pvm/ **2291** + 2293 残留② | 2291 确定性 `id()`/默认 `repr()`/身份 `hash()` 运行时身份面(隐式 f-string repr 静态拦不全)= pvm/ 运行时活;2293 残留② = 运行时**算术**产生大 int 的物化守卫(_GuardedInt,裸大**字面量①已由 #759 deploy-gate 拿下**)。(2292 import #757、2293 字面量 #759 均 deploy-gate 拿下;**pvm CI 盲区已由 #758 收口**→运行时修若做,pvm-runtime 测试自动进 CI 门禁) |

> 小结:**node 侧可乾净本地交付的审计票已耗尽**(#756 拿下 2293 的 node deploy-gate 部分后);HIGH 安全池全清;cbfs 2304 投毒已由 #53 store 层卷绑定拿下(Marshal PASS)。剩余 MED/LOW 均需协议/wire 改、设计裁定或 pvm/ 慢工,非"快速继续"。共识修复一律 needs_human 等协调 flag-day 上线(非共识已 PASS:#754 mempool、cbfs #53;#120 runner 已 merged)。

---

## 🔻 2026-06-17(实时复核)— 重新拉 Linear 全量,核对池缩水与新票

重新对 Linear COW 团队跑「state ∉ {completed,canceled} ∧ assignee ∈ {PL,未指派}」全量查询(非缓存),对照 6-14 基线核验。**结论:本文档的分档与"易档已空"判断仍成立;唯一实质变化是审计修复战役已 reconcile 到 Done,以及 7 条审计衍生新票入池(全落重档)。**

**① 池 619 → 574(净 −45)。** 6-14 以来 **96 条转 Done**(91 条 PL),即 §2026-06-15/16/17 三段记录的所有交付(F-0/1/2/3 verify+close、determinism harness、tx-canonical 主票 1942、五仓审计 HIGH C1–C7 + 12 条 MED/LOW)均已**关单为 Done**——不再是文档原文所述"In Review 待人工 merge"。下列审计票现状全部 **Done**(此前记 In Review/needs_human):
> 926 / 1057 / 1942 / 2274 / 2284 / 2286 / 2287 / 2288 / 2289 / 2290 / 2292 / 2293 / 2294 / 2295 / 2296 / 2297 / 2298 / 2299 / 2304 / 2305 / 2306 / 2307 / 2308 / 2309 / 2310。
> (即 §2026-06-17 收口表里 C4/C6/C7 + 全部 MED/LOW 行,均已落地关单。)

**② 当前池内"在途"仅 6 条**(In Progress / In Review / Duplicate),无一为本方可自动批的易活:
| Issue | 状态 | 归档 |
|---|---|---|
| COW-1058 / 1056 | In Progress | CBSS 链上态(B-4 共识) |
| COW-921 / 894 | In Progress / In Review | ManifestCommitted 链事件(B-4 共识/事件基建,他人在途) |
| COW-482 | In Progress | CLI epic(B-3 裸 epic) |
| COW-400 | Duplicate | of 501,待清(F-1 已记) |

**③ 7 条新票(全 2026-06-15/16 创建,均审计/follow-up 衍生),逐条归档——无新增 FEASIBLE-NOW:**
| 新票 | 摘要 | 归档 / 为何非易 |
|---|---|---|
| COW-2272 | [Indexer/Wallet] CIP-9 ManifestCommitted 解码器 follow-up(#2258/#728 后续) | **B-4 + B-6**:indexer 侧 decoder 阻塞于 producer 未上 devnet(node #681 系列);wallet JS 侧非本地 |
| COW-2283 | canyon-reset Ansible 一键重置(aws-infrastructure PR #957) | **B-6 非本地**:ansible/aws-infrastructure 仓不在工作区 |
| COW-2291 | [MED][node/pvm] `id()`/默认 `hash()`/`repr()` 身份面可观测→returned/stored 即 fork | ✅ **node PR #763 已 MERGED→devnet**(全闭 id+repr+hash;原 Marshal needs_human=共识 flag-day,gate run232):per-execution thread-local 重映射(`ExecObjectIdScope`);4 轮对抗 review 修 resume-reset 盲区+非-object repr+_thread repr+nested-call clobber;**hash 经专项调查+对抗 review 证安全**(checkpoint allowlist 拒 opaque 键、ABC/singledispatch miss→确定性重算同结果、迭代插入序、gas observe-only 在非-root sidecar);pvm-runtime 232 绿 |
| COW-2311 | [LOW][cbfs] `GetShard` 存在性预言机(ErrAuth vs ErrNotFound) | ✅ **已交付 cbfs PR #54**(base=main,Marshal pass):三处 present-but-unauthorized→ErrNotFound 对齐 GetPlacement;诚实标注**时序侧信道残留**(与参考 handler 同源、非本 diff 引入)留 follow-up |
| COW-2312 | [LOW][cbfs] 写路径无配额强制(`max_capacity_bytes` 仅 advisory) | ✅ **已交付 cbfs PR #54**(base=main,Marshal pass):`max_capacity_bytes` 接进 handler,store.put 前校验 `decision.max_bytes` + `used+incoming>cap`→ErrCapacity;镜像 peer-drain 路径;非共识 |
| COW-2313 | [LOW][wallet] 私钥明文存 `chrome.storage.local`(passkey 加密为 opt-in) | **B-3 设计裁定**(已回 wallet 代码核实+发 scoping 评论):无密码即无 KEK 来源,at-rest 加密对本地读威胁无效;真修需 ①passkey 设默认 或 ②加 password-based 解锁 UX——产品决策,**不硬上半成品** |
| COW-2314 | [LOW][node] `PayloadSign` 缺 chain-id/genesis→跨网重放 | ✅ **已被 #742 修(devnet)**:`Transaction::write` 首字段即 `chain_id`(进签名 hash),commit `48f76efe`(COW-1942)→ verify+close 候选,已发证据评论;待 flag-day 上线后关单 |

**④ 易档(F-0/F-1/F-2/F-3)复核:仍全空。** picker 范围内未出现任何新的"本地可改可测、非共识、纯加法"票;新入池 7 条全部落入 B-1 LOW(安全面,需谨慎)/ B-2 pvm 运行时 / B-3-B4 共识 / B-6 非本地。**自动 batch-loop fodder 仍为零**。唯一可专注做的 future 小批是 cbfs LOW 簇(2311/2312)——**2026-06-17 已专注交付 → cbfs PR #54**(TDD,Marshal pass,In Review);至此 cbfs LOW 簇清空,剩余审计残留(2306 客户端认证、pvm 2291/2293 运行时)均需设计裁定或 pvm/ 慢工。

> 复核记:96 条 Done 中 91 条 PL,印证三段战报已收口为 Done;池缩水主因即审计战役关单,而非新易票出现。分档结构无需重排。

---

## 🔻 2026-06-18 — CIP-20 token 新指令簇起手(B-4 line 281 的 1074)

审计池清空后,转向**本团队 owns 的 CIP-20 token 新指令**(B-4 token 簇 1074/1076/1798)。本日交付 **COW-1074**(ERC-20 approve race + EIP-2612 permit)两段:

- **node PR #764(MERGED → devnet)** part1:atomic `increase_allowance`/`decrease_allowance`(opcode 21/22)关经典 approve race(先 approve(0) 再 approve(N) 的中间态被抢花);镜像 `handle_token_approve`。**经验:新 `SystemInstruction` 必改 4 处 codec**(`write`/`read`/`encode_size`/`sub_type`),opcode 唯一性不变量在 `cowboy-types` crate。Marshal **needs_human**(共识 flag-day,run235)。
- **node PR #766(In Review,needs_human run241;branch `fix/cow-1074-token-permit`,未上 devnet)** part2:`token_permit`(opcode 23,EIP-2612 gasless approval)。对抗 review 当场抓到**系统性漏洞**:permit digest 原用 `tx.chain_id`(共识 `verify` + mempool 均不校验 = 攻击者可控,源 `ras.rs:68`)→ **已修=绑节点自身 chain_id**(`ExecutionEngine.with_chain_id`,genesis 经 `chain::engine`→`Application::with_mempool_and_storage`→engine 穿线;唯一生产构造点 `application.rs:405`,其余 373 个 `::new()` 全是测试)。**教训:execution 层勿信 `tx.chain_id` 做安全判断。**

**reconcile:COW-2291(node PR #763)已 MERGED → devnet**(§2026-06-17 实时复核 row ④ 原记 needs_human/in-flight;现核 devnet 已含 commit `b7951a5b`)。

→ **B-4 token 簇:1074 转「allowance(#764)已上 devnet + permit(#766)在途待 flag-day」**;1076(multicall)/1798(ICIP20)仍未起。无新增 FEASIBLE-NOW(CIP-20 新指令全为共识改动,需协调 flag-day)。

**COW-1748(CIP-17 缺键 exclusion proof)→ node PR #767(Marshal PASS,非共识 read-path)。** 易档空后挑「重」票实测发现的**反例**:并非所有 B-2/CIP 票都卡共识/harness——CIP-17 是 read-path,QMDB ordered/variable **原生**支持 exclusion proof(`exclusion_proof()`/`verify_exclusion_proof()`),故缺键 501→200+可验 exclusion proof 是「把现有能力穿过栈」的干净加法(storage `state_exclusion_proof` + `SerializableExclusionProof` + handler + additive 响应字段),非共识、向后兼容、本地可测(storage 层 self-verify proof against root)。**教训**:`VariableEncoding` 私有不可命名→方法内 match destructure 成 serializable;`dummy_marshal_mailbox` transmute 假 sender→full get_state handler 单测必 stall(无 CIP-17 handler 全路径测试,只 serde shape+storage self-verify)。→ **CIP-17 read-path 是本团队可干净交付的一类**,B-2/CIP 簇里 read-path/纯加法子项值得逐个甄别(别一刀切判 harness/共识)。

**COW-1232(WP §17.3 gas 一致性)→ node PR #769(Marshal PASS,test-only 非共识,部分交付)。** Documentation-labeled 票里唯一干净可做的:加 `spec_gas_wp_17_3_platform_token_costs` 钉 WP §17.3 Platform Token 表==`GasCosts::default()`(防 doc↔code 漂移)。已有测试盖了 §17.3 Actor API + crypto。**绝不改 gas.rs 常数(=共识),只加断言**。`token_create` cells 公式 / `token_balance_of` + WP 转 normative = whitepaper follow-up(issue 保持 open)。**经验**:gas 类「文档↔常数一致性」票是纯加断言测试(非共识、本地可测);docs-label 池其余多是设计裁定(1073/1144/1177/940)非可写文档。

**COW-2328 e2e 半 → node PR #770(Marshal PASS,真端到端验证 #767)。** 用户授权跑 e2e:worktree 建 #767 分支 → build release validator(3.5min)→ symlink target→.cargo-target → scripts/run_build.sh 生成 config → `start_all.sh --test`(纯链上不需 runner)→ `[8]` 缺键 `/state/0x..06/{absent}?prove=true` 真跑出 HTTP 200+value:null+absent:true+exclusion_proof(kind=span)+inclusion 省略,**23 passed/0 failed**。这是 live get_state exclusion handler arm 唯一对真节点覆盖。**注:#767 本会话 merge devnet(squash),stacked 分支 rebase --onto origin/devnet 后 PR base devnet。** 剩余半=proof-verifier 客户端验证(仍 open)。

**COW-2328 proof-verifier 半(option A)→ 撞大坑撤回。** 用户选 A(node 暴露 encoded operation + verifier)。实作后用闭环测试(生成真 proof 喂 proof-verifier)发现:**proof-verifier crate 的 MMR 重实现根本验不过真 commonware proof**(隔离测出 `verify_state_proof_json(op.encode(), …)=false`;现有测试全用 dummy bytes,从未对真 proof 验过)——**inclusion 也坏**。根因在 grafting MMR 重实现某处与 commonware 分歧,需专门 MMR 调试(独立大工程,宜单立票)。已 git reset 撤回未提交改动(不上未验证 verifier 码),COW-2328 评论 comment-6bc134ad 记录。**教训:proof-verifier 是潜在死功能;client-verify 必先修其 MMR。**

**COW-177(tx 协议版本字节,共识)→ node PR #776(Marshal needs_human=flag-day)。** 用户点名做共识票。Transaction 加前导 u8 版本字节(仿 ETH typed-tx envelope,升级杠杆)。**关键:做成 wire/协议常量而非 per-tx struct 字段** → 零构造器 churn,且自动进 signing hash(领头 codec=preimage)。重生成 tx_vectors + refs JSON mirror;全 `cargo test --workspace` 零 fallout(Transaction::sign 重派生);7/7 不变量含 contract.tx_encoding_roundtrip;对抗 review SOUND(签+decode 双守卫、无 serde 旁路)。flag-day:JS wallet 须同日加同字节(cf #742/wallet#14)。**经验:加共识 tx 字段优先做 wire 常量(零 struct churn);改 tx 编码必重生成冻结 vectors。**

**COW-1307 / 1306 gas-metering 前提驳倒(comment-only,荐 Cancel/re-scope)。** 从我 89 张 assigned 队列挑「乾净 code」时,gas 簇两张都是 stale/wrong-premise:
- **COW-1307(return-data Cell 未计量)** = stale:顶层 handler return-data 已计量(actor_instruction.rs:953-963,CIP-3 §2.2.2,return_data_cells_per_byte=1)+ sub-call 经 charge_return_data_cells(pvm_host 2238/2273,COW-965);return-data 已 gas-bounded。荐 Cancel。
- **COW-1306(secp256k1 verify opcode 未计费)** = wrong-premise:host 只暴露 `ed25519_verify`(已正确计费+测),**无 secp256k1 verify opcode**;`CRYPTO_SECP256K1_VERIFY_CYCLES=10_000` 定义但**从未 consume**;secp256k1 仅用于协议层 tx ecrecover(transaction.rs:80)非 actor op。真要做=加 secp256k1_verify host syscall(pvm/ ABI feature)非计费修复。荐 re-scope/Cancel。
- COW-1215(access-list stub)早被他人评论驳倒(Transaction 根本无 access_list 字段)。

**COW-117(/estimate_gas dual-gas 估算)→ node PR #782(Marshal PASS,非共识 read-only)。** 用户要「真·专案」,选了三类里最低风险的非共识 feature。`POST /estimate_gas` dry-run signed tx(begin_batch→execute_transactions→rollback_batch)返 cycles/cells+suggested limits,零状态变更。plumbing 关键:**rpc 已依赖 cowboy-execution 且无环**→handler 内构造一次性引擎(AppState 无 engine);绑 state.chain_id 对齐生产 permit。follow-up=unsigned(需滥用决定)/fee 估算/真 block context。**经验:RPC 执行 tx 先查 rpc→execution 依赖+环+AppState 有无 engine;begin_batch→execute→rollback_batch 是现成隔离原语。**

**WP §826 资源限制簇已完成 + COW-175 refute。** 本会话把 WP §826 的 per-actor/per-tx 资源 cap 簇基本做完:fanout_per_tx(#779)、storage_quota(#780)、quota 上限 8MiB(已存在 system_instruction.rs:3213)、mailbox_bytes(COW-2087 done)、reentrancy_depth=32(已存在);**只剩 memory_per_call 10MiB(COW-1239)= 深 pvm/(无分配计数器,需从零建,见前)**。COW-175(storage 实时追踪)= kv_bytes/kv_count 早已是→refute 荐 Cancel。COW-117(gas 估算 API)非共识但需把 ExecutionEngine 接进 RPC(AppState 只有 storage/mempool 无 engine)= 中型 plumbing 非单点。**单点乾净 cap 池至此耗尽。**

**COW-95(per-actor storage byte quota 1 MiB)→ node PR #780(Marshal needs_human 共识 flag-day,run259)。** 用户选做 feature+选(i)回填;深挖发现**回填不必要**——per-actor `kv_bytes` 计数器**早已存在**且增量维护(set_actor_storage)、进 state_root,对所有现存 actor 已准确(我先前「需先建追踪基建」结论是错的,漏看 kv_bytes)。故 collapse 成单点 check 挨着已有 `MAX_ACTOR_KV_COUNT` cap,复用 `Error::StorageFull`,check-before-mutate。系统 actor 豁免(COW-978);quota 拒绝=优雅失败 tx(transaction.rs:383 catch)非块中止;披露多 key mid-flush 部分持久化=同 kv_count cap(COW-700 class,非本 PR 引入)。**经验:审 cap/quota 先查是否已有进 state_root 的增量计数器(有就无需 backfill,类似 2088 复用既有 accumulator)。** 五仓投机引擎 commit-time 拒绝必确认 transaction.rs:383 catch 成 receipt status 非块中止。

**COW-2089(§3.3 dedup_window)→ 前提误诊纠正,发评论不改码(用户选项1)。** 用户选做 2089;深挖发现 **triage 误判**:`seen_messages` 是 per-block ephemeral(reset_block_state 每 block 清空,engine.rs:290),非跨 block LRU——500k 容量单 block 永不触及,LRU 逐出不发生;且 msg id 含 block_height(actor_instruction.rs:1108)→ reorg 后同消息得不同 id=自毁跨 block dedup。WP §3.3 真要求 = id `keccak256(sender‖nonce‖msg_hash)` + 持久化 per-actor dedup set(actor storage)+ window 保留/GC ≥10k blocks + gas。**真修=大型共识特性,与 COW-2090 重叠**,非票面「LRU→window」小改。发英文纠正+重新定范评论,荐重新分级+并 2090 走设计通道。**经验:审 dedup/投递 先查 dedup set 是 per-block 重置还是持久化 + id 是否含 block_height。** 不 rush exactly-once-delivery 这种最敏感共识机制。

**COW-2088(WP §3.3 per-tx fanout 1024 cap)→ node PR #779(Marshal needs_human 共識 flag-day,run258)。** 「收尾」后续 继续 重挖,发现 2088 是**真乾淨的 spec-mandated 安全修复**(纠正了「池已枯竭」结论):outgoing messages 有计数但从未强制 1024 上限=explosive-fanout DoS。修=`MAX_FANOUT_PER_TX` 常量 + `send_message` charge 前拒、**复用 payload-size guard 的 InvalidInput 路径**(安全 revert,不依赖 no-per-tx-rollback 引擎)。**关键结构事实**:嵌套 call_actor 共享同一 `ctx.outgoing_messages`(capture_call_snapshot 不存它)→ `.len()`=per-tx-including-nested 计数,单一 chokepoint。submit_job 走 send_message 故计入(一致);CIP-29 emit 用独立 Vec 不计入(符 §3.3)。无 pvm/ 改动。**经验:DoS cap 类共识修复优先单一 host chokepoint + 复用已存 Err 路径。**

**cip-audit-2026-05 stale-premise 三票驳倒 → 用户授权后已 Cancel(1818/1804/1945)。** 续做时甄别 CIP-20 簇,发现是**已修但票未关**的 false-premise 池:
- **COW-1818 / COW-1804(hook 50k Cycles/Cells cap "absent / no hooks")** — 实为已全实作+测:`TOKEN_HOOK_MAX_CYCLES/CELLS=50_000`(gas.rs:363-365)、`execute_handler(...,Some(cycles),Some(cells))` 子限额 enforce + `TokenHookGasExceeded/CellsExceeded` 错误(actor_instruction.rs:332-374)、conformance 测 `spec_cip20_cycles_1`+`spec_cip20_cells_1`(core.rs:2886);**2026-05-28 #534 已落**(在 cip-audit 快照后)。两票互为 dup。
- **COW-1945(TV1/TV2 vectors "未 pin"、CBOR map-form)** — 已被 #742+#177 满足:vectors 现 pin 在 `types/src/tx_vectors.rs`+`refs/common/tx-canonical-vectors.json`;"CBOR/array" 框架因 #742 改 commonware-codec 而**设计性过时**;残留仅 WP Appendix A 旧向量需 doc 更新(spec 层,另立)。
- **方法论收获**:cip-audit-2026-05 backlog(247 条)含大量「已修但票未关」的 stale-premise 票;甄别透镜=回 origin/devnet 核代码+测试+landing commit。**关单需用户授权**,故只发英文证据评论荐 Cancel。

**COW-1260(WP §8.2 通脹曲線,经济)→ node PR #778(Marshal PASS run257)。** 续做时考察通脹簇:**COW-1259(鑄幣/分配)真被卡**——active validator set 是共识层(Simplex)概念,execution/storage 层看不到(pre-COW-1028),无法按 stake 分配。**COW-1260(纯曲线)则干净**:WP §8.2 钉死 8/6/4/3/2% 排程 + 10% hard cap + ±2pp + security-floor,验收是纯确定性算式。落 `execution/src/inflation.rs` 纯函数模组(`base/effective_gross_inflation_bps`、`year_for_height`、`per_block_reward` saturating、`is_valid_adjustment` 护栏);12 unit+proptest。**ticket 明文允许 "Hardcode or store at 0x09" → 选 hardcode**;**模组未被任何执行路径消费 → 零共识面 → PASS 非 needs_human**(1259 接线才是 flag-day)。**关键经验:`BLOCKS_PER_YEAR=31_536_000` 回一手源核正——Explore agent 把 STORAGE_EPOCH_BLOCKS=7200 误标「2 blocks/sec」,WP §§342/608/663+constants.rs:498 均「~1 秒区块」,差一倍会让 reward 减半。** 印证 [[feedback_verify_primary_source]]。

**COW-2329 → 已修复 node PR #772(Marshal PASS,SOUND)。** rewrite proof-verifier mmr.rs 三函数镜像 commonware d77641a(mmr_root fold→concat、peak_digest_from_range 共享 rev-sibling 迭代器+descend-both-then-fill、reconstruct_grafted_root 双迭代器 front-peaks/back-siblings + byte-identical 边界检查);**cowboy-storage dev-dep proof-verifier 闭环矩阵**(真 inclusion proof 跨 12 key 数,valid 过/wrong-root 拒/tampered-element 拒=soundness)验证;对抗 review 逐行核 commonware=SOUND 无 false-accept。**解锁 COW-2328**(node encoded_operation + verify_exclusion_proof 可在 #772 上建)。follow-up:grafting layer(height 8)≥256 keys 覆盖(码未改)。

**COW-2329(原始发现):proof-verifier MMR 验不过真 proof。** 接 COW-2328 阻塞往下挖:**proof-verifier grafting MMR 重实现根本验不过真 commonware proof**(inclusion+exclusion 都坏,现有测试全 dummy bytes)。对照 commonware `mmr/proof.rs::reconstruct_peak_digests`+`hasher.rs` 精确定位:leaf/node hashing 匹配,但 root 用 **fold/prefix 模型** vs commonware **flat concat/双迭代器**(root=concat非fold、range外peaks各自从digests前端取非单prefix、siblings从后端rev)。comment-56901e62 是完整实现 spec。**未当场修**:结构性 rewrite+共识关键,必须多形态测试矩阵(跨叶数/peak配置)验,会话极长不 rush。诊断(最难部分)已完成。**教训:重实现共识验证只用 dummy 数据测=潜在死功能。**

**COW-2328 客户端 exclusion 验证 → 已交付 node PR #774(Marshal PASS,建在 #772 上)。** proof-verifier `verify_exclusion_proof`=span_contains+**绑 span 界到 MMR 认证 op**(重构 `0xD2||span_key||span_value||span_next_key`==encoded_operation+定长54-byte StateKey 防 byte-reslice)+委托 verify_state_proof。**3 轮对抗 review:R1 抓 span 界未绑(CRITICAL 可伪造 present 键 absent)、R2 抓 byte-reslice、R3 SOUND**;两伪造均负测。**关键教训:重写共识 verifier 必须多轮对抗 review——头两轮都抓到 critical false-accept,binding+定长 field 是修复核心。** CIP-17 §5.3 端到端闭环完成(#767 serve→#770 e2e→#772 MMR verifier→#774 client verify)。

**COW-2328(原始,授权):CIP-17 §5.3 客户端 exclusion-proof 验证 + e2e。** #767/#768 的 follow-up——node 已**服务** exclusion proof,但客户端**验证**(proof-verifier crate `verify_exclusion_proof` 须精确复制 QMDB `span_contains` 含 cyclic wrap + key 序 + Operation 编码)+ examples/proof e2e 缺键用例(真端到端验证 server+client 一致)未做。**为何独立成票**:proof-verifier 是独立 crate(自重实 MMR、不依赖 commonware qmdb),隔离下无真 proof 可测=假绿风险,须 e2e harness 才能可信交付。Improvement/severity:medium,CIP-17 project。

**COW-1754(CIP-17 §5.2 handler 集成测试)→ node PR #768(Marshal PASS,stacked on #767,非共识 test-infra)。** 续 #1748:根因=诊断出的 `dummy_marshal_mailbox` transmute 假 sender→`get_state` await marshal 时 runtime stall。修法=`BlockSource` trait seam + **AppState 加默认泛型参 B**(关键:现存 `AppState<E,M,T>` 30+ 引用+生产构造全不 ripple,只 `get_state` 泛型化),`EmptyBlockSource` 返 None 让 full handler 跑通;加 4 个 §5.2 集成测试+回填 #1748 handler-arm 测试。**经验**:RPC handler 要 await marshal 的单测=BlockSource seam+默认泛型参(零生产行为变更);这类「B-2 harness」票里也有非共识、可干净交付的 test-seam 子项。

**COW-2327(新建,授权):token_transfer_batch partial-failure 非原子已实证确认。** COW-1076 顺带发现,2026-06-18 写 probe(sender=100,batch[60→A,60→B] 第2笔失败)实跑出 `sender=40 A=60 B=0`=第1笔写入留存=非原子;CIP-20 §SDK「atomic」在无回滚引擎下不可实作。非供给守恒洞但违反原子契约。用户授权独立建票 **COW-2327**(Bug/severity:medium,CIP-20 project,含 repro+fix 设计分叉)。

**COW-1076 multicall:回代码核验 → 重归 B-3 设计裁定(非干净实作),已发英文设计评论不动码。** 三项发现:① 引擎**无 per-tx 回滚**(`execute_transaction` 把 handler Err 映射成状态但不还原 store 写入;`speculative.rs` 逐 tx 循环不丢弃失败 tx 写入);② 现有 `token_transfer_batch` 的「all-or-nothing」**已实证确认是 latent bug**(2026-06-18 写 probe test 跑出 `sender=40 A=60 B=0`:第1笔 commit、第2笔失败后第1笔写入留存=非原子;只 loop+`?` 无预校验余额;CIP-20 §SDK 宣称「atomic + hooks called for each」在无回滚引擎下**不可实作**)— 非供给守恒洞但违反原子契约,evidence+repro 已折进 COW-1076 评论,待裁定后另立工作项(未授权不建票);③ transfer 对 hooked token 调 `call_transfer_hook`→`call_actor` 可写任意状态,单纯快照 token keys 还原不足以保证原子;④ 规格**根本没有 `token_multicall`**(只有单 token transfer_batch)= 新共识指令 + 规格新增。两条实作路径:(A)保守=新 `TokenOp{Transfer,Mint,Burn}`+纯内存模拟全 op 校验再写(opcode 24,23 留给 permit #766),带 hook 的 token 在 multicall 原子拒绝;(B)通用=造引擎级快照/还原原语(可顺手修 transfer_batch,但大型共识关键超范围)。**结论:需设计裁定 + 大概率 CIP-20 规格修正(定义无回滚模型下 batch 原子语义),park 在 Backlog。**

---

## 🔻 2026-06-19(实时复核)— §2026-06-18 整批 node 交付已 reconcile 为 Done + merged→devnet

重新对 Linear COW 团队跑全量查询(`state ∉ {completed,canceled} ∧ assignee ∈ {PL,未指派}`,非缓存)+ 回 `origin/devnet` 逐 commit 核 merge 状态。**结论:§2026-06-18 记为"In Review / needs_human / 待 flag-day"的整批 node PR 已全部 merge 进 devnet 并关单 Done;分档结构无需重排,无新增 FEASIBLE-NOW。**

**① 池 574 → 563(净 −11)。** 这 −11 即 §2026-06-18 的交付批关单——下列 11 条现状全部 **Done**(此前记 In Review / needs_human / PASS-待-merge),`origin/devnet` 逐条核到 merge commit:

| Issue | PR(均已 merge→devnet) | commit |
|---|---|---|
| COW-2291(id/repr/hash 身份面) | #763 | `b7951a5b` |
| COW-1074(allowance part1 + permit part2) | #764 + **#766** | `9274c75b` / `8d80cd31` |
| COW-1748(CIP-17 缺键 exclusion proof) | #767 | `5bb58e47` |
| COW-1754(CIP-17 §5.2 handler 集成测试) | #768 | `10501ed6` |
| COW-1232(WP §17.3 gas 一致性断言) | #769 | `9a8bf238` |
| COW-2328(CIP-17 §5.3 客户端 exclusion 验证 + e2e) | #770 + #774 | `3ef10645` / `1130cc96` |
| COW-2329(proof-verifier MMR 修复 + grafting 覆盖) | #772 + **#775** | `bfc4318c` / `d2c29071` |
| COW-177(tx 协议版本字节) | #776 | `911171dc` |
| COW-1260(WP §8.2 通脹曲線) | #778 | `8f92999b` |
| COW-2088(per-tx fanout 1024 cap) | #779 | `162dc706` |
| COW-2331(async actor asyncio deploy 挂) | #781 | `984122d7` |
| COW-117(/estimate_gas dual-gas) | #782 | `9461a5b7` |

> 纠偏 §2026-06-18 两处过时描述:① **COW-1074 permit(#766)已 merge→devnet**(原记"In Review,未上 devnet");② **COW-2329 grafting-height 覆盖 follow-up 已补**(node **#775** `d2c29071`,原记"码未改"),proof-verifier 闭环彻底完成。tx 编码/版本字节簇(#742/#776)与各共识 PR 已落 devnet,flag-day 协调上线属运维侧,不再阻塞本档。

**② COW-95(per-actor storage byte quota)→ ✅ 已 merged→devnet(2026-06-19)。** node PR **#780** squash-merge 进 devnet(commit `d37fc5f7`,Linear **Done**)——共识变更,挨着既有 `MAX_ACTOR_KV_COUNT` cap 的单点 check、复用既有 `kv_bytes` accumulator(无 backfill),系统 actor 豁免、quota 拒绝=优雅失败 tx(详见 §2026-06-18)。合并前核验 `mergeStateStatus=CLEAN` + 含 #776 tx-version 等近期共识变更 ancestor。**至此 PL 名下零 open PR、零 in-flight。**

**③ 1804/1818/1945 确认 Canceled。** §2026-06-18 荐 Cancel 的 cip-audit stale-premise 三票已落 Canceled(用户授权后)。

**④ 仍 open 的 comment-only / 设计裁定票(无变化,均非易批):**
- **COW-1306 / COW-1307**(gas 计量前提驳倒)→ Backlog,荐 Cancel/re-scope(已发英文证据评论)。
- **COW-175**(storage 实时追踪)→ Todo,refute 荐 Cancel(kv_bytes/kv_count 早已是)。
- **COW-2089**(§3.3 dedup_window)→ Backlog,前提误诊已纠正、真修=大型共识特性与 2090 重叠。
- **COW-1076**(multicall)→ Backlog,B-3 设计裁定 + 大概率 CIP-20 规格修正。
- **COW-2327**(token_transfer_batch 非原子)→ Backlog,新建 bug 票(MED,CIP-20),待 1076 设计裁定一并处理。
- **COW-1239**(per-call heap 10MiB)/ **COW-1259**(validator reward minting)→ Backlog,前者深 pvm/(无分配计数器)、后者卡 validator-set 不可见(pre-COW-1028)。

**⑤ 其余 node open PR 全为他团队**(非 PL,不计入本档可行性池):CIP-11 WS 簇(#760/761/762/765/771/773)、CIP-23 v3 TEE(#784,配套 runner runner-tee 在途)、CIP-31 account-storage-reserve/rent 簇(#783/785/786,**新出现**)、CIP-24 inbound-verify(#729)、CIP-27 fork(#722)、CIP-33 Trading Post(#700)、ManifestCommitted 事件(#681,COW-921/894)。cbss/cbfs/runner/cowboy 自 2026-06-18 起的提交亦全为他团队(logan cbss codec、CIP-23 runner-tee、cowboy CIP-1 docs)。

**⑥ read-path / 纯加法甄别扫描(2026-06-19,确认 read-path 矿脉已近枯竭)。** 对 563 条开放池按 read-path/RPC/query/metric/trace/doc-consistency/test/proof 关键词圈出 83 条候选,逐条回 `origin/devnet` 核验。**结论:除 COW-1405 外无新 FEASIBLE-NOW**——83 条里其余全部确认为共识 / 绿地 / harness / 设计裁定:
> - **共识**(改 accept/reject 或 gas→receipt):963(per-bytecode 动态 surcharge=改 gas.rs 常数)、1373(JobSpec 正性校验=改 dispatch 接受面)、1920(sync-fire subscriber writeset commit 行为)、1230(epoch 边界处理顺序)、137(storage batch read 影响 read 计量)。
> - **绿地 / CIP 子系统**:1815(CIP-21 DEX query 方法)、1543(runner session chain-event subscriber)、1282(CIP-30 per-actor storage_root 端点,卡 CIP-30 共识 state-root)、CIP-23 TEE 簇(1098-1114/1301/1576/1577/1845/1847)、gateway CIP-19 簇(877/878/882/886/920/927)。
> - **设计裁定 / 非本地**:1256(CIP-4↔CIP-9 rent epoch 对齐,"decide policy")、1083(SDK allowance 分页,需 prefix-range RPC 不存在)、1347(CLI 兼容追踪伞,无具体交付)。
>
> **唯一产出:COW-1405(§5.4/CIP-17 缺键 exclusion proof)→ ✅ 已 Done(2026-06-19,用户授权)**——票面前提"stubbed to HTTP 501、只 wired inclusion"已被 COW-1748(#767)彻底解决:`origin/devnet:rpc/src/handlers/proof.rs:420-426` 现为缺键返 `200 + value:null + absent:true + exclusion_proof`(非 501),带 `spec_cip17_absent_key_response_shape_has_exclusion_proof` + live handler 测试。属 cip-audit-2026-05 stale-premise 同类(同 1818/1804/1945),已发英文证据评论关单。

**⑦ 三张已驗證 stale 票 → ✅ 已 Canceled(2026-06-19,用户授权,各发英文证据评论)。** §2026-06-18 荐 Cancel 的 gas 簇 + refute:
> - **COW-1306**(secp256k1 verify opcode 未计费)= wrong-premise:`CRYPTO_SECP256K1_VERIFY_CYCLES=10_000`(gas.rs:392)定义+测但**无 actor host syscall 消费**;host 只暴露 ed25519_verify,secp256k1 仅协议层 ecrecover(transaction.rs)→ 荐 Cancel。
> - **COW-1307**(return-data Cell 未计量)= stale:顶层 actor_instruction.rs:955 + sub-call pvm_host.rs:1641(2238/2273)均已计量,per_byte=1 → 荐 Cancel。
> - **COW-175**(storage 实时追踪)= refute:`kv_bytes` 增量追踪进 state_root(accounts.rs:222-234)早已是 → 荐 Cancel。

> 复核记:−11 全数对应 §2026-06-18 交付批关单,池缩水主因仍是本团队交付而非新易票出现。**易档(F-0/1/2/3)依旧全空;read-path 矿脉经 2026-06-19 全量扫描确认近枯竭(仅 1405 一条 close 候选);自动 batch-loop fodder 仍为零。** COW-95(#780)已 merged→devnet,**PL 名下现零 open PR / 零 in-flight**。往后仍纯靠用户逐个点名重票(B-3 设计 / B-4 共识 / B-5 绿地 / B-6 非本地)。

---

## 🔻 2026-06-19(续:易档空后逐个起手重票)— COW-1029 交付 + read-path/already-fixed 甄别

易档/审计池清空后,按用户指引从开放池**逐个点名挑重票起手**(非 batch-loop)。本轮规律:**重票里仍藏着"非共识、可乾净交付"的子项,和"已修但票未关"的 stale 票,必须回 `origin/devnet` 逐条核验才能分辨**(标题/票面前提系统性过时)。

**✅ COW-1029(Foundation/system-deployer 分离强制,CIP-12 §2)→ node PR #788 MERGED→devnet(`49ea9cd7`,Marshal PASS run 268)。**
- 从 CIP-12 governance 簇挑出的乾净 guard 票。新增 optional `foundation_addresses` genesis 字段 + 拒绝 Foundation 地址出现在 `system_deployers`,在 `validate()` **和**生产载入路径 `from_file` 双重强制。
- **scope 纠正**:票面假设"runtime tx update 时校验"是错的——`system_deployers` genesis-immutable(无 runtime 变更指令),守卫落 genesis 校验期。**默认空字段→对现存 genesis 零行为变更→非共识、向后兼容**(deterministic load-time check,不碰 state-transition/root)。
- TDD 4 测试 + chain 210 测试 + workspace build + fmt 全绿;Marshal 5/5 econ 不变量 PASS + 6 维对抗 review 无高危;CI CLEAN 后合并。**经验:tier=high(chain 路径)≠ 必然共识;genesis 载入校验是 chain 簇里可乾净非共识交付的一类(类比 CIP-17 read-path)。审 cap/quota/guard 票先查它守的状态是 genesis-immutable 还是 runtime-mutable——决定守卫落 validate() 还是 tx handler。**

**已修但票未关(verify+close 候选,回 devnet 实证)——`test_*_constant` 测试名常是"已修"信号:**
- **COW-701(M-16 unbounded spawned tasks,`chain/src/indexer.rs`)= 已修**:`MAX_CONCURRENT_UPLOADS=16` + `Arc<Semaphore>`(spawn 前 acquire permit 绑活跃数、满则 drop+warn)+ `UPLOAD_TIMEOUT=30s` per task,两常数有测试钉死;PR #296(`7c11b40b`)已落 devnet。ticket 仍 Todo → close 候选(待点名授权)。

**逐个甄别中确认非干净的重票(本轮)**:COW-1138(whitelist)=CIP-28 绿地(card 基建不存在);COW-1012(session chain-id)=跨仓 + 需先定 production 值;timer 1457/1458/1460=高危执行顺序语义;1373=dispatcher 接受面(共识);1241/1239=pvm/ 运行时。

> 小结:本轮乾净交付 **COW-1029(#788)** 一条;发现 **COW-701** 已修待关。重票池继续靠逐个点名 + 回 devnet 核验前提(别信票面)。

### 3-agent 全量 triage sweep(266 候选,回 origin/devnet 逐条核验)— 乾净池确认枯竭

为终结"逐个串行踩 stale/绿地票"的低效,派 3 个并行 agent 对 266 条 node-relevant 候选(已剔明显 gateway/builder/前端/CIP-2x 绿地)逐条回 `origin/devnet` 核验分类。**结论:乾净可实作池实质枯竭——剔除他团队 CIP(2/3/4)+ 共识 + 绿地后,只剩 COW-1407 一条 maybe;2026-06-19 验 feasibility 后亦否(前提错+设计裁定,见下)→ 乾净池归零。**

**① CLEAN 可实作(非共识、本地可测)——仅 2 条,且都有保留:**
- **COW-1407**(CIP-17 §8.2 batch-proof 跨 key 节点去重)→ **2026-06-19 验 feasibility = 前提错,退回(发英文 scoping 评论,保持 open)**。回权威 CIP-17 spec(`cowboy/docs/cips/cip-17-verifiable-state-read.md`):**根本无 §8.2 dedup 条款**(§8=Relationship to Other CIPs);combined-proof batch read 明列为 **v1 non-goal(§4)+ Future Work(§11)**,**无 normative wire format**。现有 `/proof/multi` 已返独立可验 per-key proof(超出 CIP-17 v1)。做 dedup 需 ①**设计** combined-proof 格式(未指定)②server dedup ③扩 proof-verifier 客户端重构每 key(COW-2329 那段易错 MMR 重构)= **设计裁定 + 中型 server+client 改,非 spec-conformance 缺口**。荐 re-scope 成设计票或标 Future Work。**=B-3 设计裁定,非乾净实作。**
- **COW-2268**(CIP-3 §2.2.2 doc 把 put_blob/file.write 改成真实 HostApi 名)= docs-only 乾净,但 **CIP-3 是他团队**(本团队回避令),**不取**。

**② ALREADY-FIXED(已修但票未关,verify+close 候选;均带 file:line 证据,抽查 220/1267/1374 命中):**
> COW-220(access_list 字段+bounds`types/src/execution.rs:97`/`constants.rs:33-34`)· COW-720(L-22 非原子 commit=已记录 accepted-risk`blockchain_storage.rs:714`)· COW-1002(paid-mode billing`stream_key_manager.rs:55/371`)· COW-119(snapshot 优化`pvm_host.rs:45`)· COW-1234(genesis 系统 actor 代码`genesis.rs:1697`测试)· COW-1261(Treasury 0x08 live)· COW-1266(genesis governance 参数`genesis.rs:622`)· COW-1267(Entitlement Registry 0x07`entitlement/`)· COW-1374(candidates_snapshot_root`dispatcher.rs:2986`)· COW-1375(VRF seed block_height`dispatcher.rs:1936`)· COW-1637/1640/1642(circuit-breaker handler`system_instruction.rs:997`)· COW-701(M-16 已修,见上)。
> **保留**(agent 标已修但需逐条深核才能关,勿批量关):1457/1458/1460(timer,核每个 §-item)、1254/1255(blob 定价,核 40-cycle 常数)、938(CIP-31 wiring 部分)、1228(STORAGE_EPOCH_BLOCKS 需对 spec)。
> **2026-06-19/20 深核 timer 簇(1457/1458/1460)结论**:实为 **CIP-5**(Globalbox EOB timers,非 CIP-1)。precharge→execute→refund roundtrip **已实作+测**(`spec_cip5_timer_precharge_refund_roundtrip`、`spec_timer_fire_one_refund_one_burn_one_event`;`speculative.rs:1338` Model B.3 atomic pre-charge=同块原子、非跨块预扣)。三票全都 hinge 在 **EOB 执行顺序**(inline-interleaved 逐 timer vs enqueued-deferred-set)是否偏离 CIP-5 设计文档——且 1458 的"cancel 退下次 fire 预扣"假设了 impl 不用的「跨块 next-fire 预扣」模型(impl 是同块原子 precharge/refund)。**= 共识关键顺序判定,须对权威 CIP-5 spec + 慎重分析,非快速 close/scope;不在低置信度下动共识 timer 码。** 1254/1255=CIP-3(他团队)、938/1228=CIP-31(他团队)→ 本团队不深做。

**③ HEAVY(余下绝大多数)**:共识(gas 计量 963/964/970/1397-1402、accept/reject 1372/1373/2113/2114/2152、receipt schema 1147、events CIP-29 1917-1924、tx-canonical 残留 spec 偏离 1934-1944)、绿地子系统(CIP-30 storage_root 1275-1284、CIP-10 容器、CIP-11 QUIC、CIP-15/16 routing、CIP-18 bank、CIP-19 MCP、CIP-25 跨链)、pvm/ 运行时(1199/1240/1241/62/94/105)、fast-sync 接线(1403/2100/2177)、需设计/值裁定(1012/1259/1265/1265)。

> **总结论(2026-06-19 sweep 后)**:**本团队可乾净非共识交付的票池已枯竭**(仅 COW-1407 一条 maybe)。开放池现状=已修待关批(需授权)+ 共识 flag-day 重票(逐个点名慎做)+ 绿地/他团队(做不了)。往后要么授权清"已修"批做 backlog hygiene,要么明确选一条共识重票协调 flag-day 上线。

**④ 已修批清单已落地(2026-06-19,用户授权)→ 11 票 Done、3 票 hold。** 关单前逐条回 devnet 复核(纪律:别只信 agent 的 already-fixed 断言):
> **Done(11,各发英文证据评论)**:COW-701/220/720/1002/119/1234/1266/1267/1374/1375/1642。
> **HOLD(3,复核发现实为 partial,发英文纠正评论保持 open)**:COW-1261(有 SubmitTreasuryProposal 提款路径但**无 TreasuryState 结构/inbound-flow 记账**)、COW-1637(circuit-breaker **无 body_ref**)、COW-1640(CircuitBreaker 只 Pause/Unpause,**无 RatifyExtend/Cancel**)。**教训:agent 的"core done"断言对带 §-子项的票要逐项核——本批 3/14 over-claim。**
> 池 557 → **546**(−11)。

---

## 🔻 2026-06-20 — 重票里再挖出一条乾净 client-path 交付(COW-2140 CLI 半)

易档/乾净池"枯竭"结论复核仍成立(实时拉 Linear:6-19 之后无新可行票,唯一全新 COW-2332=CI runner 宕机基建)。但**逐个回 devnet 核验 PL 名下 In Progress 票**时,发现 read/client-path 矿脉还没全枯——印证 [[CIP-17 read-path 是本团队可乾净交付的一类]] 的规律也适用于 CLI 客户端层。

**COW-2140(Actor Payload Ergonomics)→ node PR #789(Marshal PASS run271,非共识 client-only)。**
- **状态纠正**:票 In Progress 是因为只做了 NODE 半。NODE 半(`actor_read` 接受 payload/payload_text/payload_json)**早已 merged→devnet**(`0fbc2201`+`08e5c2c4`),文档此前未记。SDK/客户端半才是欠的活。
- **工作区内客户端面 = CLI**(`cowboy` pip SDK 不在工作区,COW-992)。给 `cowboy actor execute` 加 `--payload-text`(UTF-8)/`--payload-json`(JSON→canonical CBOR)两互斥 flag,挨着原 `--payload`(hex/`@file`,降为 Option)。抽纯 `resolve_actor_payload`(歧义/空拒绝 + 三形态解码);`@file` 留原 fs 守卫。
- **非共识**:解析在建 tx **之前**,签名字节不变。**byte-parity 核验**:JSON→CBOR 与 node `actor_read` 逐字节一致——无 `preserve_order`→`serde_json::Value` 走 BTreeMap(键有序),全工作区单一 serde_json 1.0.149+ciborium 0.2.2(特性统一保证两 crate 编码相同)。
- 单文件 +183/−30,无新依赖;7 新单测 + cli 全套 373 绿;workspace build OK;fmt clean。Marshal 5/5 econ 不变量绿 + 3 维对抗 review 零高危 → **PASS(非 needs_human,因纯 client 零共识面)**。
- **票不能整票闭合**:CLI 半干净交付,**SDK 半(pip `call_*`,COW-992 不在工作区)+ `Deploy --init-payload` CBOR 化 = follow-up**,已在 PR/issue 评论说明,票保持 In Progress。

> 经验:**审 PL 名下 In Progress 票别假设"零 in-flight"**——COW-2140 NODE 半已上 devnet 但票仍开,客户端半是可乾净交付的 client-path。read/client-path 矿脉(CIP-17、CLI ergonomics)比"全量 sweep"结论更耐挖,关键是回 devnet 核"半成"边界。

**verify+close 批(2026-06-20,用户授权)→ COW-2135/2136/2137 Done。** 顺 COW-2140 往上核**整个 job 归一化/编码工作流(COW-2132→2142)**,回 `origin/devnet` git 历史确认 **node 半全部已 merged**:`6939d305`(2137 shared fixtures,14 例覆盖 6 job 类型+defaults/overrides/DNS/base64/hex/errors+loading 测试)、`3bedcc0d`(2136 node-authoritative validation + structured `ValidationError{code,field,message}`)、`05e6656f`+`81b5857e`(2135 base64 字节编码,`ByteInput` 兼容 base64-或-legacy-int-array,`result_base64` 输出侧)。三票 = verify+close 候选(node 半落,SDK 半=pip 工作区外 COW-992),各发英文证据评论标 Done。**诚实残留**:agent `system_prompt_path`/`session_dir` 无 node 路径校验(与 2136"path-traversal authoritative"措辞矛盾),但 **inert**(`runner/src/main.rs:188/191` 设 None、不读 job 路径),补校验=共识接受面变更,已在评论标注不阻 node-side 关单。**经验:带 (NODE)+(SDK) 双段的票,node 半 merged 即 verify+close,SDK pip 半归 COW-992;§-子项票必逐项核(2135 输出侧 result_base64、2136 各 rule)别凭一个 commit over-claim。**

**3-agent verify+close sweep(2026-06-20,PL 剩余 44 开放票回 devnet 核)→ 仅 2 条可关,vein 确认见底。** 续清"已修待关"批:auto-mode 正确拦截未点名的关单(2314 首次被拦,印证 [[新建 Linear issue 需明确授权]] 同类纪律=关单也须点名),改逐条/批量点名授权。派 3 个 general-purpose agent 对 44 票(剔已办 4 张 + 2314)分组只读核验,结论:
- **可关(2,用户点名授权后 Done)**:**COW-2314**(chain_id 进签名 preimage,#742 `48f76efe`,`execution.rs:446` write 首字段;wallet 半 wallet#14 跟)+ **COW-1215**(access_list 现有字段+界限 codec+明文档为 advisory/reserved v1 恒 None,`197e0b03`;票验收的"if advisory then document"分支已满足;**无语义执行=故意,要 normative 另立共识票**)。
- **PARTIAL(安全/硬半已落、残留 pvm/共识,非关)**:2055(int() 算术守卫落、裸字面量残)、1248(共识 ptr-scrub+typed codes 落、path/timestamp 剥离残)、1894(VRF health-weight 落、sustained-window 升级残)、1243/993(部分 CI、非票面 E2E)、613/1937(chain_id 落、字面引用符号未动)。
- **OPEN-HEAVY(绝大多数)**:共识(2089 dedup/1457-1458 timer 内联无 refund/921 ManifestCommitted/1601 vote/2020 validator-slash)、pvm-runtime(62/94/105/1239/1240/1241/1365/1398)、CBSS(1056/1895)、gateway 非本地(877/896/897/894)、epic 空描述(482/492/495/433/435/751)。

**COW-1457(CIP-5 §5.1/Appendix-A timer 两阶段)→ 用户点名"重票开始干",已起手:premise 验证(真共识分歧)+ divergence 证明 + 设计锁定 + 测试落地。** 分支 `fix/cow-1457-timer-deferred-queue`(off devnet),worktree 有 plan.md。
- **premise HOLDS(真共识分歧,非 1458 那种 vacuous)**:CIP-5 §5.1+Appendix A 钉**两阶段**(classify+precharge **所有**due timer→enqueue deferred→再执行队列,在 engine/mailbox deferred 之前);impl 走 **inline-per-timer**(`speculative.rs:808/1366` 每 timer classify→precharge→execute→refund 同迭代)。timers-before-engine/mailbox **已满足**,分歧纯在 timer 集内 inline vs 两阶段。
- **divergence 实证**:两同块 due timer,FIFO-first A 的 handler 抽干 B 的 fee_payer → inline:B 自毁(fired_ok=1);spec:B 在 phase-1 已 precharge(A 跑前)→ B 照 fire(fired_ok=2)。测试 `cip5_5_1_due_timers_classified_before_handlers_execute`(+`DrainVictimExecutor`)**RED 1 vs 2**,已 commit `#[ignore]`(node `5c79a9c5`)。
- **核心设计张力 + 用户拍板**:两阶段与 **inline-timer-manifest 确定性机制**(wall-clock gate 在 admission 期按 handler 执行时间决定 manifest)根本不兼容(execute 移到 phase-2 后 wall-clock 在 phase-1 测不到时间)。**用户选:drop wall-clock admission gate,改由 gas budget + manifest cap 界(都确定性)→ 移除 wall-clock 非确定性源,manifest 全确定(改进)。**
- **✅ two-pass 重写已完成交付**(同会话续做):loop 拆 `ClassifiedTimer` 收集(pass1 classify+precharge+enqueue+remove)→ pass2 执行/refund/retry/burn/fairness;移除 wall-clock admission gate(改 manifest cap + gas budget reserve-by-limit);divergence 测试翻绿(both fire);wall-clock manifest 测试重写为 `cip5_admission_is_independent_of_handler_wall_clock_time`;**cowboy-storage 510 全绿 + execution econ 10/10 + 5/5 不变量 + workspace build + fmt**。3 commit(`5c79a9c5` test→`82579c6b` impl→`bc5ea283` fix)。
- **对抗 review 当场抓到并同环修(MED)**:reserve-by-limit 让 `timer_budget_remaining` 喂的 **timer EIP-1559 basefee 信号**从 actual 漂成 reserved(会静默抬高 timer basefee)→ 解耦:加独立 `timer_actual_cycles_used`(success t_cycles + failure TIMER_CYCLES_LIMIT penalty)喂 basefee,**逐字节复刻 pre-COW-1457 信号** → 把共识 blast 缩到只剩 timer 执行顺序本身。LOW(throughput 因 reserve-by-limit 降)= intended/disclosed。
- **Marshal run273 = needs_human**(tier high 共识 state-root,flag-day 协调上线,**非缺陷**;不变量 5/5、对抗 review 无残留高危)。**经验:reserve-by-limit 改 admission 必查那个 budget 计数器是否还被别的共识量(basefee 信号)消费——decouple 出独立 actual 累加器复刻旧信号是缩小 blast 的关键。**

**COW-1640(CIP-12 §7.7 circuit-breaker RatifyExtend)→ ✅ 实作完成,Marshal run274 needs_human(共识 flag-day)。** 用户「pick another heavy ticket」+「implement it now」。
- **premise 核验收窄**:§5.4 Circuit payload(Pause/Unpause/RatifyExtend/Cancel)里 **Pause/Unpause 已实作**(CircuitBreaker action 0/1)、**Cancel 已实作成独立指令 `CancelProposal`**(§7.8/COW-1020),**唯一真缺口=RatifyExtend(action 2)**;`PauseRecord.extension_count` 字段已在(只设 0 never inc)。
- **实作**:加 action 2 handler——GOVERNANCE 授权(Tier-3 提案经 0x09 执行)、`expires_at += PAUSE_EXTEND_BLOCKS`(新常数,spec 30d)、`extension_count += 1`、`>= PAUSE_TIER3_EXTENSION_CAP`(新常数,spec 3)拒绝逼 Tier-4、non-paused 拒、emit `governance.circuit.extended`。**无 wire/codec 改**(action 是 u8,值 2 本就可解码,无新 variant→无 opcode churn);tx-encoding roundtrip + opcode uniqueness 绿。
- **对抗 review 当场抓到并同环修**:RatifyExtend 漏 expiry 检查→会「复活」已 auto-revert 的过期 pause(违 §7.7 auto-revert)→加 `Council::pause_expired` 守卫 + 测试(commit `ff2d8474`)。
- 全绿:cowboy-execution 1458 + cowboy-types 526 + econ 5/5 + workspace build + fmt;分支 `fix/cow-1640-circuit-ratify-extend`,2 commit(`3de57539` feat + `ff2d8474` fix)。out-of-scope:§7.7 自动建 ratification 提案、Tier-4 PausePermanent、Cancel(已做)。**经验:加「新 action 值」到既有 u8-action 指令=零 codec churn(比加新 SystemInstruction variant 省 4 处 codec + opcode);审 pause/TTL 类必查是否有 expired 守卫别让 extend/renew 复活已 lapse 的记录。**

**COW-1894(CIP-24 CBSS §4.4 sustained-low-health 治理审查)→ ✅ 实作完成,Marshal run276 needs_human(共识 flag-day)。** 用户「pick another heavy ticket」+ fork A「implement now」。
- **premise 核验(回权威 CIP-24 §4.4)**:health-weight 衰减已实作;governance-review flag **触发时机错**——impl 在跨 floor 那刻**立即** flag,spec 要 `health<0.1` **持续** ≥ `GOVERNANCE_REVIEW_BLOCKS`(216,000≈30天)。
- **设计分叉(time-based 触发):用户选 Fork A event-driven**(ProxyHealth 加 `low_health_since_block`+`governance_review_flagged` 双 serde-default 字段;纯 helper `update_low_health_tracking` 管 clock/window/latch/recovery;接进 challenge-expiry 健康衰减路径)。新增 `CBSS_GOVERNANCE_REVIEW_HEALTH_BPS=1000`(spec 0.1,纠正 impl 误用 floor 500)+ `CBSS_GOVERNANCE_REVIEW_BLOCKS=216000`。score_bps 生产单调不增(无 recovery 路径,已核所有赋值点在 test)。
- **对抗 review 抓到 HIGH 并同环修(`86e45697`)**:**slash 路径**(单事件最多 -5000bps,是到达 health<0.1 的**主路径**)漏调 helper→被 slash 到极度退化的 proxy 可能永不 flag(§4.4 明列 slash 为健康信号)→ 把 helper+flag-write 接进 `handle_cbss_slash_proxy`,clock 锚到健康真正掉落时。2 LOW(sentinel-0 重载、reason 字串 misnomer)记录为 cosmetic。
- 全绿:cowboy-execution 1458 + cbss 111 + econ 5/5 + workspace + fmt;3 commit(`84660dbc` feat + `86e45697` fix)。backward-compat:双新字段 serde-default,旧记录解码为「未退化」。out-of-scope:实际自动**建** CIP-12 Tier-1 除名提案(现写 review flag record 供治理消费)、Fork-B sweep、slash-handler 集成测试。**经验:审 health/score 衰减类共识改动,必查**所有**降分路径(slash vs liveness)是否都驱动同一触发器——主降分路径漏接=漏 flag;serde 加字段必 #[serde(default)] 保旧记录解码 + 注意 re-store 后字节增长是 flag-day。**

**COW-1895(CIP-24 §3.6.2 auto-reshare)Part I → ✅ node PR #793(Marshal run277 needs_human)。** 用户「再挑」;**核出此票实为 2-PR 子系统**:Part I(committee-churn,event-driven,小)+ Part II(scheduled cadence,需新 per-block cursor sweep 镜像 rent sweep,大)。用户选先做 Part I。
- **Part I**:`healthy_committee_count`(registered+!suspended)+ `maybe_reshare_on_committee_churn`(scope healthy < threshold+`RESHARE_SAFETY_MARGIN` 才触发 reshare,gated 不像 deregister 无条件)接进 slash 路径(slash 加 block_hash 参数,从 dispatch 穿,仿 deregister)。
- **对抗 review 抓到 HIGH 并同环修(`b4ce701b`)**:churn 的 reshare 错误 `?`-传播会**中止 slash tx**→ 故障 proxy 变不可罚(对手可借此庇护同伙;且 slash 先存 suspended 比 deregister 更脆)→ 改 **best-effort**(错误是确定性共识态,吞掉全节点一致跳过,receipt_root 不分叉)。1 MEDIUM(churn 未计量 I/O,与 deregister 同形,accepted)。
- 全绿:cowboy-execution 1458 + cbss 111 + econ 10;2 commit(`165b119e` feat + `b4ce701b` fix)。**经验:把副作用(reshare)接进强制路径(slash)必设 best-effort——副作用失败不能中止主操作,尤其 accountability 类(slash);判定是否可吞错先看错误是否确定性共识态。Part II(cadence sweep)留 follow-up。**

**COW-1895 Part II(scheduled cadence sweep)→ ✅ 实为已在途 draft PR #794 + Marshal 抓出并修满 spec gap → ready。** start-issue-fix 核前提时发现:本文档「Part II 留 follow-up」**已过时**——Part II 早被实作成 draft PR #794(rksweep:<account> 可掃描索引 + `settle_cbss_reshare_epoch` cursor sweep 镜像 rent sweep,自足不依赖 Part I,CLEAN/MERGEABLE)。**跑 /marshal 794**:tier=high,8/8 不变量绿、Almanax 0、cursor exclusive 语义 SOUND;但对抗审抓到一条 **MEDIUM spec-conformance gap**(run280):权威 CIP-24 §3.6.2 line 855 明文 scheduled cadence「**for both AccountReleaseKey AND SecretReleaseKey**」,而 #794 只索引/掃 account → secret-specific override key(自带 last_reshare_block)永不被 cadence reshare,且零披露。**用户选「修满 §3.6.2」→ 同环修(commit `e1e2e03e`)**:统一沿用 `rksweep:` 索引,按 **value 长度判别**(20B=account 地址/60B=secret 身份 account‖key_hash‖version_be);secret index key=`rksweep:‖keccak256(identity)[..24]`=32B 保持 prefix-scannable(secret 全 record key 远超 32B 限);全部 SecretReleaseKey 生产写入(唯一站 cbss.rs:956 finalize/rotate handler)路由经新 `store_secret_release_key`。验证:reshare 10 测试(+3 新 secret)、cbss 115、cowboy-execution **1462 passed**、8/8 不变量、workspace build + fmt 全绿。Marshal run285 **needs_human(仅 flag-day,非缺陷)**,已贴英文评论 + **PR 移出 draft → ready**。**残留 LOW(已披露)**:rksweep 索引只在 create/reshare 写 → 升级前既有且从不 reshare 的记录无索引、不被 cadence 掃(两型同),in-place 升级需一次性 backfill,建 follow-up。**经验:① 「实作 follow-up」类票起手前必回 devnet/branch+PR 核是否已在途(本票险些重写已存在的 #794);② 审 sweep/index 类共识改动必回权威 spec 核「覆盖范围是否完整」(account-only vs both record types 是 §3.6.2 明文 MUST);③ 超长 record key 做可掃描索引=短 distinctive prefix + 截断 keccak,value 携完整身份供 point-load,按 value 长度多型共用一个索引前缀。**

**COW-1895 Part II(scheduled cadence sweep)→ ✅ index rework 完成,对抗 re-review SOUND,Marshal run279 needs_human(共识 flag-day)。** 用户「做 Part II 的 index rework」。CRITICAL(扫 40B hashed key=生产 no-op)已修:建可扫 `rksweep:<20B addr>`(28B≤32 verbatim)索引,经 `store_account_release_key` helper 在唯一生产 store 站(rotate handler 892)+ sweep re-store 维护;sweep 改扫 `rksweep:`→account→point-load record。**测试**:length-guard `reshare_sweep_index_key_is_prefix_scannable`(钉 index≤32 & record>32 的根因不变量)+ index-backed 功能测试。**对抗 re-review 7 面全 SOUND**(scannability/index 一致性/cursor/determinism/migration/secret-scope/tests);test 保真 caveat 已闭:除静态 length-guard 外,**已补真 BlockchainStorage e2e 测试**(`reshare_sweep_index_scannable_on_real_blockchain_storage`,commit `222454cf`)——实跑断言 28B `rksweep:` 索引在真 storage 可前缀扫(idx.len=1)、40B record key 被 hashed 不可扫(rec 空=原 no-op 的精确属性)、record 仍 point-loadable;**此测试能抓到原 no-op**(TestStore 抓不到)。begin_batch/commit_batch 包写入后再扫已提交态。已修 2 LOW doc nits。**migration**:升级前的 key 在下次 rotate 才入索引(churn Part I 覆盖紧急);**secret-specific scope 留 follow-up**(只扫 Account)。**secret-specific cadence follow-up 已 de-risk(供下次 focused 做)**:`SecretReleaseKey`(types/cbss.rs:1524)有 committee+last_reshare_block,需 cadence;`load_release_key_material` 已处理 SecretSpecific scope(cbss.rs:3373);**enumeration 设计已解**=60B 标识符(account+key_hash+version)塞不进 ≤32B 可扫 key→用 **hash-keyed 索引** `srksweep:<keccak(secret_id‖version)[..23]>`(=32B 可扫,O(1) add/remove,value=标识符);维护点=store(968 SecretSpecific 臂)+ **delete(519 cascade,与 Account 不同需删索引)**;sweep 加第二 cursor 扫 `srksweep:`→load secret-release-key→cadence→reshare(scope=SecretSpecific)+bump。distinct cycle(非 Account 镜像),且 secret-specific 是较少用路径(默认用 account committee,Account cadence 已覆盖常用)。3 commit(`ea8a6b2f` feat→`c5e61405` index fix→`82b4c771` docs)。cowboy-execution 1459+storage 509+econ 10 全绿。**经验(最高价值,已上记忆候选)**:**依赖 prefix-scan 枚举前必核 key 长度 ≤ ACTOR_STORAGE_SCANNABLE_MAX(32)——超过即 hashed 不可扫;TestStore 存 verbatim 不复制此边界 → 这类枚举 bug 单测假绿;修复用「可扫短 key 索引(record 仍 point-key)」+静态 length-guard 钉不变量。对抗 review 两次都拦在 ship 前(首次抓 no-op、re-review 确认修复 SOUND)。**

> ~~(原 BLOCK 记录已 reconcile 为上方 fixed)~~ Part II 早先 de-risk plan: 实作了完整 sweep(cursor+trait 方法 default no-op+speculative 接线+`settle_cbss_reshare_epoch`),单测绿、workspace 绿——**但独立对抗 review 抓到致命缺陷**:sweep 扫 `account_release_key:` 前缀(**40 字节** key=20 前缀+20 addr),而**生产 actor-storage key >32 字节走 hashed 模式不可扫**(`ACTOR_STORAGE_SCANNABLE_MAX=32`,`scan_actor_storage_paginated` 文档明言「Only verbatim ≤32B visible, hashed silently skipped」)→ **生产扫描恒空 → 排程 reshare 永不触发 = 静默 no-op**。单测假绿因 `TestStore` 存 verbatim 不复制 32B hash 边界。**根因**:「mirror rent sweep」是表面——rent 用 `scan_actors`(20B addr 专用索引)不是长 key 前缀扫;我验了 scan_actor_storage_paginated 存在但没验 32B 可扫阈值 vs 40B key。**rework**=建可扫短 key(≤32B,如 `rksweep:<20B addr>`=28B)release-key 索引,在 install/rotate 等 store 站维护;sweep 扫索引→accounts→load keys;**且必须加真 BlockchainStorage 测试**(TestStore 抓不到此类)。**经验(高价值):依赖 prefix-scan 枚举前,必先核 key 长度 ≤ ACTOR_STORAGE_SCANNABLE_MAX(32)——超过即 hashed 不可扫;TestStore 不复制此边界,这类枚举 bug 单测假绿,必须真 storage 测试。对抗 review 在 ship 前拦下了一个生产 no-op = 流程成功。** Part I(#793 churn)是 COW-1895 本会话的真交付;Part II cadence 待 index rework。

**COW-1058(CIP-24 §4.4 liveness 健康 attrition 上限,共识)→ ✅ node PR #795(Marshal run289 needs_human=flag-day,非缺陷)。** 「继续」续做时挑的 CBSS health 姊妹票(context 紧邻 1894/1895)。**前提 HOLDS**(行号漂移 1411→2123,缺口真实):`handle_cbss_expire_liveness_challenge` 每个过期 liveness challenge 固定扣 `score_bps -= 100`(magic literal)无上限 → 高频 challenger 可抽干 proxy health(=committee 选择权重)。**修**:ProxyHealth 加两 serde-default 字段(`attrition_epoch_start`/`attrition_loss_bps`,向后兼容旧记录解码为 0),纯 helper `apply_liveness_attrition_penalty` 滚动窗口 + 按剩余 `CBSS_MAX_HEALTH_LOSS_PER_EPOCH_BPS` budget clamp 每次扣减;抽出 magic 100→`CBSS_LIVENESS_HEALTH_PENALTY_BPS`;新窗口/cap 常数 demo-scale + governance-tunable。**关键 scope 判定:只 cap liveness attrition,slash 路径(`handle_cbss_slash_proxy`)保持 uncapped**——slash 是独立 accountability 信号必须能硬扣(呼应 1894 slash=健康信号),cap 不能庇护真作恶 proxy。**TDD**:先 stub 旧无 cap 行为→RED(总扣减超 cap)→实作 clamp→GREEN;测试用 serde round-trip 模拟跨 tx 存回/读回证累加器持久化(不只内存内)+ window-roll 恢复 attrition + 旧记录解码。验证:cowboy-execution **1459**、cowboy-types **526**、6/6 不变量(含 `contract.cbss_wire_round_trip`)、workspace build + fmt 全绿、Almanax 0。**flag-day 协调**:与在途 CIP-24 health PR(#793/#794/§4.4 sustained-low-health)同动 ProxyHealth + expire-liveness handler 区,serde-default 字段可共存但 rollout 须排序同上。**经验:① 审 health/score 衰减类共识修改必分清「攻击面 attrition」(该 cap)vs「accountability slash」(不该 cap)——别一刀切;② cap/quota 类要测的是跨 tx 持久化(serde round-trip)不只单次调用;③ 抽 magic literal 成具名常数顺手降未来漂移。**

**COW-1056(CIP-24 §5.3 release receipt collateral:serve_epoch 绑定 + 过期 set GC,共识)→ ✅ node PR #796(Marshal run290 needs_human=flag-day,非缺陷)。** 再「继续」挑的 CBSS 票。**两个耦合修复**(单文件 execution/src/cbss.rs,+223):**Part 1 epoch-rollover correctness bug**:`release_id`(3157)漏 `serve_epoch` → committee reshare 后同 `(account,version,actor,runner,job,nonce)` 撞到旧 `ReleaseReceiptSet`(其 `quorum_epoch != body.serve_epoch`,1124 行 reject)→ **reshare 后所有 receipt 被拒**;修=release_id keccak 加 serve_epoch(consensus-pinned 到 committee epoch、submit 时校验、非 attacker-malleable)→ receipt set 随 epoch 滚动。**Part 2 GC(无界增长,Part 1 令其更严重——每 epoch 新 set)**:set 从不 GC;新增定宽可扫 GC 索引 `rrg:<request_block(16hex)><keccak(rid)[..6]>`(=32B 镜像既有 `tng:` nonce 索引,value=receipt-set key),set 建立时(仅首 receipt)写入;**扩展既有 `handle_gc_nonces`**(permissionless/incremental/bounded 256/page)同时 drain `rrg:`——删 `request_block < upto_block` 的 set+索引(caller 选 upto_block≤now−FRESHNESS),emit `cbss.release_receipts.gc`。**关键设计:GC 索引按 request_block 分桶**(与 nonce GC 的 height 语义统一,共享 upto_block 阈值不冲突;避免按 expiry 分桶导致 nonce/receipt 的 upto_block 语义错配)。**最低 surface:复用既有 GC handler 不新增 SystemInstruction**(免 opcode + 4-codec churn)。**TDD**:既有 `submit_release_receipt_dedup_on_release_id` 测试**显式 bump serve_epoch 并断言 release_id 不变=编码了旧 bug**,更新为正确语义(同 epoch dedup/跨 epoch 滚动);新增 e2e GC(真 submit→确认 index→retain at `==`/prune at `>`)+ 静态 index-key 长度守卫(≤32 scannable)+ height round-trip。验证:cowboy-execution **1459**、**9/9 不变量**(econ+state-root+`contract.cbss_wire_round_trip`)、workspace build+fmt 全绿、Almanax 0。**classifier 误判 tier=mid**(单 cbss.rs 文件未触发 high-risk-path 启发式)→ Marshal 覆写为 consensus needs_human(release_id derivation 改 storage key + 新事件进 receipt_root)。**flag-day 残留 LOW(已披露)**:pre-upgrade set 无 `rrg:` 索引不被 GC(一次性清理或容忍 bounded backlog);跨界 in-flight liveness challenge 重算不同 release_id(短 drain)。与 #793/#794/#795 同 CBSS 区须排序上线。**经验:① classifier tier 仅启发式,共识判断(改 derivation/发事件→state-root/receipt_root)必人工覆写别盲信 mid;② 改核心 identifier(release_id)derivation 必查所有 call site(6 处都传 body 故单点)+ 既有测试是否编码了旧 bug(本票 dedup 测试即是);③ 时间桶 GC 索引复用既有 handler+统一 height 语义=最低 surface;④ 加可扫描索引必加静态长度守卫(≤32)钉不变量(TestStore 不复现边界)。**

**(以下为已 push 的 Part I + 早先 de-risk 记录,保留)** Part II 原 de-risk plan: worktree `fix/cow-1895-part2-reshare-sweep`(off devnet)+ `plan.md` 已备。**关键已解(实作机械化)**:① 枚举=`scan_actor_storage_paginated(CBSS_SYSTEM_ACTOR, b"account_release_key:", cursor, batch)`(升序 lex cursor 扫);② 无 mock churn=新 trait 方法仿 `settle_rent_epoch` 设 **default no-op**,只真 ExecutionEngine override;③ reshare 触发复用 Part I best-effort 模式;④ 结构=镜像 rent sweep(cursor load→scan→per-key cadence check `now-last_reshare_block>=RESHARE_INTERVAL_BLOCKS`→触发+bump→advance cursor→speculative:804 接线)。**watch-item**:sweep 需 `block_hash`(选委员种子),但 rent hook 只收 height→新 trait 方法+call site 须穿 block_hash。**经验:新 per-block sweep 别从零想枚举——先查 StateStore 有无 scan_actor_storage_paginated + 目标数据是否在某 system actor storage 带公共前缀(release-key 在 CBSS_SYSTEM_ACTOR 下 `account_release_key:` 前缀);trait 方法设 default no-op 免 mock churn。**

> **总结(2026-06-20 sweep 后)**:PL 名下乾净 node 池实证枯竭——44 票仅 2 可关(且 1215 borderline),其余全 PARTIAL/重。本会话累计:实交付 COW-2140 CLI(#789)+ 关 6 张已修(2135/2136/2137/2314/1215 + 此前)。**往后纯靠点名重票(共识 flag-day / pvm 慢工 / 设计裁定)或他团队/绿地(做不了)。** 关单一律须用户点名(auto-mode 强制)。

**COW-1458(CIP-5 §5.4 timer cancel 退款)→ 严格核验=非 bug,发英文证据评论 + Canceled(用户点名)。** 用户点名 timer 共识票收尾,**遵守"不在低置信度动共识 timer 码"**先回权威 CIP-5 + devnet impl 核 premise:§5.4 "IF fire-time self-destruct check 已为 next fire 预扣 max_cost,cancel 退未用部分" 是**条件句,条件 vacuously false**——impl 走 §6.3 **同块原子 precharge/refund**(`speculative.rs:1206` 检查 `balance<max_cost` 自毁**不扣款**、`:1353-1355` 过检后才 precharge、`:1386-1406` Model B.3 同块退 `precharge−actual_cost`),**无 next-fire/跨块预扣**(re-arm 也不预扣);fee_payer 仅 fire-time 扣(§6.1)。故 `CancelTimer`(`system_instruction.rs:2490`)/`ExtendTimer`(`:2591`)只 remove/re-TTL 无退款逻辑=**正确**(schedule↔fire 间零 fee_payer 占用,无 outstanding debit 可退;cancel 撞 fire 不可能[precharge+refund 原子]、fire 后 idempotent no-op)。**premise 真但描述非 bug**,同 COW-2089/1306/1307 模式。荐 CIP-5 §5.4 措辞澄清(spec 层 follow-up,他途)。**经验:timer/计费类共识票必先回权威 CIP-5 + 核 §6.3 同块原子 vs 跨块预扣模型;impl 用同块原子→所有"next-fire 预扣/退款"票多半 premise vacuous。** 印证 [[pvm_fsm 冷编译误拒 stdlib]] 同源纪律(审共识先核执行层真实模型)。

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
- **tx/derivation**:~~1212(chain_id 签名)~~ → node PR #742(tx-canonical 簇,已 merge→devnet);~~177(tx version)~~ → **node PR #776 MERGED→devnet**(`911171dc`,Done);1944/1935/1934 仍未起
- **token 新指令**:~~1074(allowance+permit)~~ → **node PR #764 + #766 均 MERGED→devnet**(allowance `9274c75b` + permit `8d80cd31`,**Done**);1076(multicall,B-3 设计裁定)/1798(ICIP20) 仍未起;新衍生 bug 2327(transfer_batch 非原子,Backlog)
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

> **2026-06-19 终态(实时复核后)**:§2026-06-18 的整批 node 交付(**12 PR / 11 issue**:COW-2291/1074/1748/1754/1232/2328/2329/177/1260/2088/2331/117)已**全部 merge→devnet 并关单 Done**;含 §2026-06-18 原记"In Review/未上 devnet"的 permit(#766)与新补的 proof-verifier grafting 覆盖(#775)。池 **574→563(reconcile −11)→558(COW-95 交付 + 4 张 stale 清帐 −5)**。**COW-95(node #780)本会话已 merged→devnet(`d37fc5f7`),PL 名下现零 open PR / 零 in-flight。** read-path 全量扫描确认矿脉近枯竭(仅 COW-1405 一条 close 候选,已 Done)。1804/1818/1945 + 本会话 175/1306/1307 已 Canceled。易档(F-0/1/2/3)仍全空、自动 batch-loop fodder 仍为零;其余 node open PR(CIP-11/23/24/27/31/33)全为他团队。详见 §2026-06-19。
>
> **2026-06-18 增补**:审计池清空后转 CIP-20 token 新指令——COW-1074 allowance(node **#764**)+ permit(**#766**)起手 B-4 token 簇;COW-2291(**#763**)上 devnet。详见 §2026-06-18。
>
> **2026-06-17 终态(实时复核后)**:易档(F-0/1/2/3)早已清空;6-16 五仓审计起的 **7 条 HIGH(C1–C7)+ 12 条 MED/LOW 已全部修复并关单 Done**(见 §2026-06-17 + §2026-06-17(实时复核);原"In Review 待人工 merge"已 reconcile 为 Done)。**池 619→574(−45);6-14 以来 96 条 Done(91 PL)**;新入池 7 条全为审计衍生,落 B-1 LOW / B-2 pvm 运行时 / B-3-B4 共识 / B-6 非本地——**无新增 FEASIBLE-NOW**。cbfs 2304 投毒(#53)、cbss 2306 预分配放大(#30)、cbss 2310 重叠仪式(#31)、node 2292 actor I/O import gate(#757)均已拿下(前三 Marshal PASS,#757 needs_human=共识 flag-day)。审计池仅剩残留:cbss 2306 的 per-IP 限流/客户端认证、pvm 2291(id/repr/hash 身份面,运行时)+ 2293 残留(运行时 int 物化守卫)—— 全需协议/wire 改、设计裁定或 pvm/ CI 盲区。共识修复一律 needs_human 等 flag-day。

~~真正现在能本地交付的只有 ~26 条(10 close + 9 易 + 7 中)外加 24 example~~ —— **2026-06-15 修正:这个估计仍偏乐观。** 实测后 F-0/F-1/F-2 三个易档全部清空或核实为非干净:本轮真正干净交付的只有 **3 条代码批**(COW-202/231/363,2 个 PR 已 merge)+ **2 条原生关闭**(COW-400/501)。F-0 已无可关。

**剩下的全是"重"票**,无一为自动 batch-loop fodder:
- **F-3 example**(24):本地可跑但偏集成(需 release 二进制 + validator),留作专门一轮;
- **B-1 安全专注 PR**(3,如 COW-926 `/ras/` 签名信封全验证)——高危,一处错=绕过,必须单独专注做;
- **B-2 先建 harness**(~13)——一次性解锁 CIP-17 handler 测试 / CBSS e2e / example CI 一批,投资回报最高;
- **B-3 设计裁定 / B-4 共识协调上线(~60)/ B-5 绿地 / B-6 非本地** —— 需人拍板或协调上线。

**推荐下一步**:① 就此收尾;或 ② 先投 B-2 一个 harness(把"没法本地测"的根因解决,为后续批量铺路);或 ③ 点一个具体 B-1/B-4 重票专注做。教训重申:档位务必在真上手前逐条回代码验"验收能否本地跑通",别信"标题+轻核"。

---

## 🔻 2026-06-20(续)— Marshal 残留发现回溯维修(自己 PR 的审计结果不能只披露不修)

用户要求复盘 shawhanken 名下所有未合并 node PR 的 Marshal 审计结果,判断是否需进一步维修加固或开票。**结论:不需新开票(残留发现要么已建 COW-2333/2334,要么是我自己 draft PR 内的已知发现);真正该做的是把"披露但未修"的发现就地修掉——尤其 #792/#793 是未合并 draft,带已知缺陷上 flag-day 不合理(#793 甚至是 no-op feature)。** 三条全修:

- **#792(COW-1894)MEDIUM 参数错 12×** → commit `3178261c`:`CBSS_GOVERNANCE_REVIEW_BLOCKS` 216_000(~2.5天)→ 2_592_000(30天@1s 区块,对齐 §4.4 + constants.rs:107-110 的「1s 区块」一手源)。测试引符号非字面量,行为随值缩放。
- **#793(COW-2334)HIGH dead-feature** → commit `67b06ff5`:committee-churn auto-reshare 在生产默认(n=5,t=4,margin=1)恒 no-op——emission 需 `max(t,vss.len())=n=5` healthy signers 但 churn gate 在 healthy≤4 触发。**回权威 CIP-24 spec 核 PSS reshare 密码学上只需 t 个旧 signers**(t-of-n,release「any t proxies」;n 个 vss_commitments 是公开验证资料非参与计数)→ `old_signer_count = threshold`。新增默认参数 churn 测试(证实真 fire,旧测试用 contrived threshold 掩盖);2 个既有 reshare-event 测试更新为 t-based 断言。**此修同时纠正所有 reshare 路径(owner-request/deregister/cadence)为选 t 个旧 signers=密码学充分最小值。**
- **COW-2333(pre-existing,MEDIUM)poison-timer 无限重试** → **新 PR #797**(Marshal run291 needs_human):retry 路径用 `age=current_height-timer.height` 界定,但 retry 重设 `height=current_height+1` → 下块 age 恒~0 → `MAX_TIMER_RETRY_BLOCKS=3` 永不达 → 毒 timer 每块烧 timer-lane budget 无限重试。**根因:height 是排程键必须前进,age-from-height 从根本无法计数重试**。修=Timer 加持久化 `retry_count`(**codec v5,向后兼容**:v3/v4 blob 解码 retry_count=0,无需 wipe;读接受 v3..=v5)+ retry 时递增、达 cap dead-letter;决策抽成纯函式 `timer_retry_action`(仿既有 `carry_forward_action`)。**~21 个 Timer 建构点 churn**(用「末欄 max_priority_fee_per_cycle 后接 `}`」的精确启发式脚本批量插 `retry_count: 0`,避开 Transaction 的同名字段——后者后接 max_priority_fee_per_cell 非末欄)。测试:retry_action 有界证明(驱动至终止,回归本质=不终止)+ v5/v3/v4 codec round-trip + codec-version 断言改 5。storage 511 + execution 1457 全绿,8/8 不变量。**⚠️ 与在途 #790(COW-1457 两阶段 timer 重写)纠缠**:#790 保留同一 bug,须先合 #797 再 rebase #790(或 #790 吸收 retry_count)。

> **方法论 / 经验沉淀**:① **自己 Marshal run 披露的发现不能只挂评论不修**——尤其未合并 draft 带 HIGH(no-op feature)/MEDIUM(12× 参数)上 flag-day 不合理;复盘自己的 PR 审计结果是必要环节。② 改共识 signer-count/参数前必回**权威 spec**核密码学/语义最小值(t-of-n→t 不是 n)。③ 加结构体字段触发大量建构点 churn 时,用「唯一末欄 + 后接 `}`」启发式脚本批量插入(同名字段属不同结构体时靠末欄位置区分),compiler 兜底剩余多行 value 站点。④ pre-existing bug 若与在途重写 PR 纠缠,修在 devnet + 明确标注 rebase 顺序。⑤ 把 inline 共识决策抽成纯函式(`timer_retry_action`/`carry_forward_action`)= 可单元测 + RED 证明(本例 RED=非终止)。
