# Marshal 评审 —— CIP-23 v3(TEE 执行与复合证明)

- **对象:** 分支 `docs/cip-23-v3`(`cowboy@dc0a64b0`)上的 `docs/cips/cip-23-tee-execution.md`
- **变更:** v3 合并重写,`+226 / −355`,单文件;supersede v1(2026-04-20)与 v2 对齐修订(2026-05-26)
- **流程:** B(规格层)+ 安全 lens。**目前是分支、尚无 PR** —— 本次为分支审阅。
- **判决:** 🟡 **NEEDS_HUMAN**(建议态;非降级)
- **Marshal run:** 185 · **日期:** 2026-06-16
- **抽取 requirement:** 17 条(13 MUST / 2 SHOULD / 2 MAY)

---

## 1. 执行摘要

CIP-23 v3 是一份质量高、安全意识强的重写:它解决了 v1/v2 的结构性问题,并对 2025-10 的 **TEE.Fail** 披露做出了正确响应。规格内部自洽,Marshal 抽查的每一条跨 CIP 引用都与当前 spec 树和 node 代码一手对上了。判 **NEEDS_HUMAN** 不是因为有缺陷,而是因为:这是一次重大的安全关键 CIP 设计变更(Draft,属治理/人审领域),其新增的规范性安全要求多为 spec-ahead-of-code、尚无不变量覆盖,且还有几处显式未定项(opcode 定号)需在实现期对齐。

Marshal 无法**硬阻断**合并,且当前无 PR 可评论;本文档即建议性记录 + 面向实现的检查清单。

---

## 2. v3 改了什么(对比 v1/v2)

| 方面 | v1/v2 | v3 |
|---|---|---|
| 验证哲学 | 单一 `Deterministic`,把机密与可复现混为一谈 | **拆分:** `TeeAttested`(机密、单副本、证明*即*验证) vs `Deterministic`(非机密、委员会逐字比对) —— §3.4 |
| 链上证明 | 手写 7 层 X.509/ECDSA 走链(`~120k` cycles,时间不确定) | **SNARK 压缩 DCAP 证明**;时间相关 collateral 变成快照锚定的电路输入 —— §3.8 |
| 信任根 | 单一芯片厂商根 | **多根 `chip_root ∧ operator_root`**(Proof-of-Cloud),应对 TEE.Fail —— §3.6 |
| `attest_digest` | `keccak(cae_cbor)`(循环 —— 含签名本身) | `keccak(D-CBOR(清空 service_sig 的 CAE))` —— §3.5 |
| `nonce` | `keccak(task_id ‖ req_hash ‖ submission_block_hash)`(纯公开可派生) | 增加链上 `randomness_beacon` 项 —— §3.5 |
| TCB 等级 | 不评估 | **TCB-level 策略步** → `TcbOutOfDate`;治理通过 `CollateralSnapshot` 拉黑某 microcode/TCB 等级 —— §3.8.4/§6 |
| 链上时间 | 近似墙钟 | **按区块高选取的治理锚定 `CollateralSnapshot`** —— 对所有验证者确定 —— §3.8.4 |
| SGX | legacy 档 | attested 模式**直接拒绝**(IAS/EPID EOL) —— §3.3 |

---

## 3. 安全分析(正向 —— 逐条读 spec 核过)

以下性质是 v3 成立的支柱,每条都是实打实的改进,而非套话:

1. **`attest_digest` 循环定义修复。** 对"清空 `service_sig` 的 CAE"取摘要,消除了不可能的自引用。正确。
2. **`nonce` 不可预测性。** 掺入链上 beacon 后,抽密钥攻击者无法预计算 —— 给定 TEE.Fail,这正是其明确动机。正确。
3. **多根信任。** `chip_root ∧ operator_root` 是对"物理访问 + root 可造出'伪造但根有效'的 quote"的正确结构性回应。威胁模型陈述诚实(芯片根**不**覆盖物理访问;operator 根是缓解;远程/软件攻击者仅凭芯片根即可覆盖)。
4. **`CollateralSnapshot` 带来的确定性。** 用按区块高选取、治理发布的快照(**而非墙钟**)来评估证书 `notAfter` / CRL `nextUpdate` / TCBInfo 日期 —— 这正是共识路径所需:每个验证者重放都得到同一判定。
5. **REPORTDATA 绑定。** `user_data = keccak(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)` 把 CPU/GPU/服务/任务交叉绑定;没有匹配的 GPU 报告和密钥,CPU quote 一文不值。
6. **重放 + 新鲜度。** `nonce` 对 `seen_nonces[job_id]` 在争议窗口内查重;`MAX_QUOTE_AGE = 75 blocks`;证书链可缓存,但 **quote** 每次事件必须新鲜。
7. **模式拆分可实现。** 机密(逐接收方加密)输出在不同 runner 间绝不会逐字相同,故无法委员会比对;v3 让 `TeeAttested` 走"证明即验证"(单副本),`Deterministic` 留给公开输出。

---

## 4. 跨 CIP 一致性核验(一手核对仓库)

| CIP-23 v3 中的断言 | 核验 | 结论 |
|---|---|---|
| `BLOCK_CYCLES_TARGET = 20,000,000`「per CIP-3 amendment」 | `cowboy/docs/cips/cip-3-fee-model.md:20` 记录为 `20,000,000`(由 10M 修订);node `execution/src/basefee.rs:88` 默认 `20_000_000` | ✅ 一致 |
| interim trusted-key 模型在 **opcode 60–63**,「已上线」 | `node/types/src/execution.rs`:`SYS_REGISTER_TEE_TRUSTED_KEY=60`、`SYS_REVOKE_TEE_TRUSTED_KEY=61`、`SYS_SUBMIT_TEE_ATTESTATION=62`、`SYS_REVOKE_TEE_ATTESTATION=63` | ✅ 准确 |
| 目标 opcode **65–67** 给 `VerifyCae`/`UpdateCollateral`/`GcNonces` | 当前空号(下一个已分配是 `SYS_ROTATE_COMMITTEE=74`);spec 标注为**非最终占位**,待对齐 CIP-13 主分配表 | ✅ 诚实;当前无碰撞(`contract.sys_opcode_uniqueness` 守卫兜底实现期碰撞) |
| interim `cbss.rs` 模型 = `operator_root`;SNARK `chip_root` = target/未实现 | 与已上线状态吻合(CBSS `validate_runner_tee_for_release` 消费签名-证明记录) | ✅ 实现状态如实 |
| 治理 | 属 CIP 修正案(非白皮书);带 changelog supersede v1/v2;amends CIP-2 §5.4/§9、CIP-10 §12.3 | ✅ 未发现静默宪法↔修正案冲突 |

> 注:加载的 `CLAUDE.md` 仍写 `BLOCK_CYCLES_TARGET = 10_000_000`,相对当前 CIP-3 spec 与 node 代码(20M)**已过时**。CIP-23 的断言是对的;CLAUDE.md 应另行更新。

---

## 5. 发现

- 🔵 **LOW —— target/capacity 命名漂移。** CIP-23 v3(§3.16 + gas 表)把 `BLOCK_CYCLES_TARGET = 20,000,000` 当作*目标(target)*,但 CIP-3 §241 把 `20,000,000` 定义为区块周期**容量(capacity)**、`10,000,000` 为**目标(T_c,容量的 50%)**。node 常量名为 `BLOCK_CYCLES_TARGET` 却存的是 20M 容量值。gas headroom 论断(「每块验证 100+ 个 CAE」)依赖到底指哪个数。这是 CIP-3/代码本身的命名问题,非 CIP-23 独有,但 v3 继承了该歧义 —— 建议在 CIP-3、node 常量、CIP-23 三处统一「target」与「capacity」术语。

无 medium/high 级发现。Marshal 起初开的两条一致性疑点(CIP-3 周期数、opcode 分配)经核验**均归为一致/诚实**。

---

## 6. 覆盖缺口 —— spec-ahead-of-code(Draft 正常,已标注)

仅 **P0(interim trusted-key 模型,opcode 60–63,CBSS `tee_required` gate)** 已上线。新增的规范性安全 MUST 暂无任何已注册不变量覆盖,因为其实现是路线图项(P1–P3):

- 伪造 quote 拒绝(SNARK chip-root)
- 重放拒绝(`seen_nonces`)
- REPORTDATA 绑定相等
- 多根接受(`chip_root ∧ operator_root`)
- TCB-level 策略(`TcbOutOfDate`)
- 新鲜度(`MAX_QUOTE_AGE`、binding 续期)
- 确定性 collateral 选取(无墙钟)

其中多数是**否定性 / 机密性 / 完整性**属性 —— 无法用功能性往返 proptest 验证(脆弱构造能过 happy-path)。它们在实现期需要 **review-lens 检查 + 定向对抗测试**。

---

## 7. P1 实现检查清单(随代码一并落地的 hazard + invariant)

chip-root SNARK 路径落地时,下列每项都应带一个测试/守卫。已标形状(`hazard` = review-lens 否定性属性;`invariant` = 可往返的正向属性)。

| # | 性质 | 形状 | 建议检查 |
|---|---|---|---|
| 1 | 伪造 quote(无有效厂商链)被**拒绝** | hazard | red-team 向量:伪造/篡改/错根 quote → `AttestFail`;断言无接受路径 |
| 2 | 争议窗口内重放的 `nonce` 被**拒绝** | invariant | proptest:同 `(job_id, nonce)` 第二次 `verify_cae` → `TaskReplayed` |
| 3 | `REPORTDATA != keccak(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)` 被**拒绝** | invariant | 对各字段变异做 proptest → `NonceBindingFail` |
| 4 | 过期 quote(`now − generated_at > MAX_QUOTE_AGE`)或超 `deadline` 被**拒绝** | invariant | 75 块边界 proptest → `TaskExpired` |
| 5 | 仅单根通过的 `TeeAttested` / `Deterministic+tee_required` 结果被**拒绝** | hazard | review-lens:断言接受必须 `chip_root ∧ operator_root`;有效芯片根 + 无效 operator 根向量 → `OperatorRootFail` |
| 6 | 不在治理允许集内的 TCB 等级被**拒绝** | invariant | TCBInfo 标记该等级不可接受的快照 → `TcbOutOfDate` |
| 7 | `verify_cae` 跨验证者**确定**(无墙钟)—— 同块 ⇒ 同判定 | invariant | 同区块高、两份 by-height 快照重放同 tx → 结果一致;断言路径内无 `SystemTime`/时钟读取 |
| 8 | SGX CAE 在 attested 模式被**拒绝** | invariant | `tee_type == sgx` → `UnsupportedTeeType` |
| 9 | `attest_digest` 对**清空 sig** 的 CAE 计算(所有消费者一致) | invariant | 往返:storage/secrets/billing 摘要相等;变异 `service_sig` 不改变 `attest_digest` |
| 10 | `nonce` 派生**包含 beacon**(纯公开可派生的 nonce 不合规) | hazard | runner quote 请求处做 review-lens;拒绝可由纯公开输入复现的 nonce |
| 11 | 新 TEE Verifier 错误码**唯一**且共识协调 | invariant | 一旦 `TeeVerifyError` 进入 receipt 路径,扩展 `contract.structured_error_code_uniqueness` 守卫(已开 `esc-20260615-...`)覆盖之 |
| 12 | 最终 opcode(65–67 占位)**不碰撞** | invariant | `contract.sys_opcode_uniqueness` 已守卫此项 —— 定号后确认绿 |

> 第 11 项挂到既有逃逸棘轮 `esc-20260615-structured-error-code-collision`,第 12 项挂到 `contract.sys_opcode_uniqueness`(源自 COW-1024)。两者都是本代码库的复发性 hazard 类。

---

## 8. 判决理由

判 **NEEDS_HUMAN**,因为:
1. 这是重大安全关键 CIP 设计变更 —— Draft、无 PR —— 属治理/人审领域;Marshal 不对宪法相邻的安全规格橡皮图章。
2. 新增规范性安全 MUST 多为 spec-ahead-of-code、无不变量覆盖(Draft 正常,但已用 §7 清单标注)。
3. 非最终 opcode 65–67 须在实现前对齐 CIP-13 主分配表。

规格本身写得规范、内部自洽,所有跨 CIP 引用均核对通过。剩余主要工作是 SNARK chip-root 实现、opcode 定号,以及走治理 sign-off。

---

*Generated by Marshal (risk-tiering + invariant gate + adversarial review). Advisory only.*
