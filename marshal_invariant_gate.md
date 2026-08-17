# Marshal 不变量门禁 — Executor 阶段 & 全量不变量清单

> 来源:Marshal 知识库 `invariant_registry`(72 条 active/candidate-red/pending)+ `marshal_pack_cowboy`。
> 说明:门禁把「能写成确定性测试的属性」交给**执行阶段**跑真实测试,把「写不成测试的否定性/危险属性」交给**对抗 review 阶段**由 LLM 裁定。分界即 pack 的 `invariant_able`。

---

## 0. 先看这里(大白话)

- **不变量(invariant)**:一条「**永远都该成立**」的规则。例:「一笔交易的钱不会凭空多出来」「系统 actor 地址不重复」。
- **门禁(gate)**:每个 PR 合并前,Marshal **自动检查这些规则有没有被这次改动破坏**。破坏了就拦/升级。
- **executor(执行器)**:「**用什么方式检查这条规则**」——
  - 有些规则能写成**测试**(跑 `cargo test`/`pytest`,过了就是 pass);
  - 有些规则**写不成测试**(比如「没有时序泄漏」「CI 里没有把密钥暴露给 PR」),只能让 **AI 审查推理判断**。
- **阶段(stage)**:上面这两类检查发生在流程的**不同步骤**——测试类在「**执行阶段**」跑,审查类在「**对抗 review 阶段**」判。这就是本文第一节要讲的。
- **ratchet(棘轮)**:某个真 bug **漏过了审查、后来才被抓到**,就把它固化成一条**永久检查**,以后同类 bug 再也漏不过去。清单里绝大多数不变量都是这么来的(每条的「设置原因」里的 `esc-…` 就是当初那个 bug)。
- **`invariant_able`**:pack 给每条属性打的标记——**能不能写成确定性测试**。能 → 走执行阶段(测试);不能 → 走 review 阶段(AI 判)。**这是整套门禁最核心的分界。**

### pack(领域包)是什么

Marshal 分两层:

- **`marshal_core`(核心引擎)**:**领域无关**,只懂「怎么审」的通用流程(分级 → 不变量门禁 → 对抗 review → 棘轮),**不懂任何具体项目**。
- **pack(领域包)**:把「**某个具体项目的领域知识**」打包成一个**可插拔模块**,插到核心引擎上。Cowboy 的包就是 **`src/marshal_pack_cowboy/`**(目前唯一、也是第一个)。换个项目 → 换个 pack,核心引擎不动。就像同一台游戏机(core)换不同卡带(pack)。

**Cowboy pack 里装了什么(本文的一切都来自它):**

| pack 提供的 | 作用 |
|---|---|
| 风险分级规则 `classify` | 判这次改动是 high/mid tier(动了 `execution/engine`、`_root`、crypto 就升 high) |
| **不变量目录** `InvariantDef` | **本文那 72 条不变量就注册在 pack 里**,含 `invariant_able`、`executor_kind`、`run_command`、`spec_ref` |
| 安全危险点 `security_hazards` / `ci_security.py` | 第二阶段的 **`review-hazard`** 检测器(嗅 CI 密钥暴露等) |
| 规格解析 `spec_layers` | 把 CIP / 白皮书条款对到代码 |
| 审查视角 `review_plan` | 对抗 review 用哪些 lens |
| 概念登记 `concepts/` | 32 个概念页 + spec-vs-code 漂移板 |

> 所以下文说的「pack 标 `invariant_able`」「pack 自动嗅到危险味道」——**pack 就是这个 Cowboy 领域包**,是 Marshal 关于「Cowboy 该守哪些规则、哪些路径高危、哪些是安全危险点」的**全部领域知识来源**;核心引擎只是执行它。

---

## 一、Executor 种类与阶段

门禁的 executor 共 **6 种**(注册表实际使用),按执行方式分两大阶段:

### 阶段一 · 不变量门禁「执行阶段」(机械跑命令)
在**被审代码本身的干净 git worktree**(PR head / `origin/devnet`,绝不在落后的主工作树)跑 `run_command` → **exit 0 且至少跑到 1 个测试**才算 pass(否则记 degraded,防 `running 0 tests` 假阳性)。

| executor_kind | 数量 | 跑什么 | 备注 |
|---|--:|---|---|
| `test` | 41 | cargo `#[test]`(常用 substring filter 命中具体测试) | 机械 |
| `proptest` | 23 | cargo proptest(属性测试) | 机械 |
| `conformance-vector` | 2 | cargo test 回放**规格 conformance 向量** | 机械 |
| `pytest` | 2 | pytest(Marshal 自身的 Python 不变量) | 仅审查端跑(见下) |
| `command` | 0 | 通用 argv 命令 | reporter 支持,注册表当前 0 条 |

- **CI reporter**（`executor/reporter.py`，GitHub Action 跑的确定性路径）只认 `{proptest, test, conformance-vector, command}`，且对 cargo 三类做「≥1 test ran」校验(`_tests_ran`)。
- ⚠️ **`pytest` 不在 reporter 的 `_KNOWN_EXECUTOR_KINDS`** —— CI Action reporter 会标 `unsupported executor_kind` 跳过;pytest 不变量**只由 `/marshal` 审查端的 gate flow 跑**(它执行任意 `run_command`)。
- ⚠️ 退出 0 ≠ pass:`cargo test … -- --exact` 名字不匹配会 `running 0 tests` 且 exit 0 → 必须确认 `test result: ok. ≥1 passed`。

### 阶段二 · 对抗 review「裁定阶段」(不跑命令,LLM 裁定)
这类属性**写不成确定性测试**(pack 标 `invariant_able=False`),所以不跑命令,而是在 `/marshal` 主流程 **step-4 对抗 review** 里由审查者/LLM 裁定;确认的 HIGH → **escalate**(高危终审归人)。它分两种,**区别在于 pack 能不能「自动嗅到」它**:

**① `review-hazard`(危险点检测器 · 半自动)**
pack 里**有一个扫描器主动嗅探已知危险模式**(目前全是 `ci.*` CI 安全)。改动里一旦扫到 → **升 tier=high** + 把它的提示词**注入 review 的 security lens**;`spawned_check` 记成 `hazard:<id>`。**检测是机械的,裁定靠 review。**
- `ci.secret-exposed-to-untrusted-trigger` — 长期 `*_TOKEN` 暴露在 pull_request 可达的 job env(无 environment gate)
- `ci.unpinned-action-on-secret-pr-job` — 暴露 secret 的 PR job 用了未 pin 的 action

**② `review`(纯审查视角 · 全靠判断)**
**没有自动扫描器**,是一条常驻**审查视角**,要靠审查者读代码/读规格**推理**才能判定。
- `cbfs.existence_hiding_no_timing_leak` — 时序侧信道:你没法写「无时序泄漏」的 proptest,只能审查推理执行路径(auth 前不得查存在)
- `hazard:cip-unchanged-claim-drift` — 规格漂移:要**对比 CIP 与白皮书文本**,判断「声称未改」是否属实

> **一句话**:`review-hazard` = pack **能自动嗅到「危险味道」**,嗅到就升级 + 塞进安全审查;`review` = pack **嗅不到、只能靠人/LLM 逐个推理**的审查视角。

| executor_kind | 数量 | 有无自动扫描器 | 触发方式 |
|---|--:|---|---|
| `review-hazard` | 2 | **有**(嗅危险模式) | 扫到 → 升 tier + 注入 security lens |
| `review` | 2 | **无** | 常驻审查视角,靠推理判定 |

---

## 二、全量不变量清单(名称 · 中文解释 · 设置原因)

> 设置原因绝大多数是 **ratchet(逃逸棘轮)**:某个真 bug 漏过审查被抓后,写成永久检查。`esc-…` 即触发它的逃逸。少数 `hand` 为手写基座。

### 经济守恒(econ / 费用 / 铸币 / 结算)

| 名称 | 严重度 | executor | 中文解释 | 设置原因 |
|---|---|---|---|---|
| `econ.fee_conservation` | high | proptest | 一笔 tx 的费用 = burn+tip+退款,无凭空增减(CIP-3) | esc-2026-06-05:pack 注册 4 条 econ 高危却 proptest 空壳,给假保证 |
| `econ.tx_fee_conservation` | high | proptest | 单 tx 费用守恒(CIP-3) | 手写基座 |
| `econ.settlement_sum_100` | high | proptest | 结算三份(runner/burn/treasury)之和=100%(CIP-2) | esc-2026-06-02:econ 不变量 proptest 空壳 |
| `econ.escrow_non_negative` | high | proptest | 托管余额永不为负(CIP-2) | 手写基座 |
| `econ.timer_burn_conservation` | high | test | timer 触发的 burn 从 fee_payer 扣除后必须记入 `Address::ZERO` sink(CIP-3) | esc-20260605-timer-burn:扣了却没入 sink,资金无处记账 |
| `econ.deferred_fee_conservation` | high | proptest | 延迟 tx:`block_burn` 只能加实际收到的,不能加全额 deferred burn | esc-20260616-deferred-fee-mint:欠费仍加全额 burn → 凭空造钱 |
| `econ.fee_waterfall_alias_conservation` | high | proptest | fee-waterfall 各层账户与 sender/actor 快照别名时不得铸 CBY(CIP-28) | esc-20260727-gas-waterfall-alias-mint |
| `econ.registry_fee_conservation` | high | proptest | TLD 注册费扣全额则 burn 余额也要记(CIP-16) | esc-20260608-cip16-registry-fee-burn:只记 treasury 份,burn 蒸发 |
| `econ.governance_deposit_conservation` | medium | test | 治理押金没收要记入 `Address::ZERO` sink(CIP-12) | esc-20260608-cip12-governance-deposit:只标 settled 未入 sink |
| `econ.job_settles_at_most_once` | high | test | job 结算至多一次(终态守卫) | esc-20260616-job-double-settlement:重放 reveal 重跑整个结算 → 双花 |
| `econ.token_mint_requires_authority` | high | test | `token_mint` host op 必须检查 mint_authority(CIP-20) | esc-20260616-token-mint-no-authority:PVM 无授权即增发 |
| `econ.trading_post_settle_conservation` | high | proptest | trading-post 结算不得 pay-then-fail(CIP-33) | esc-20260614:先扣托管后做可失败减法 |
| `econ.aggregate_active_job_stake_bound` | high | test | `runner.active_jobs` 生产中要真增减,并发上限有效 | esc-20260616-active-jobs-dead-counter:只有测试写,上限成死读 |
| `cip16.tld_expiry_enforced` | medium | proptest | TLD 到期要真的 Active→Expired(CIP-16 §8.3) | esc-20260608-cip16-expiry-inert:`expires_at` 只写不执行 |
| `governance.passage_fail_closed` | high | test | 治理通过必须 fail-closed(CIP-12 §6.1/§6.2) | esc-20260608-cip12-governance-fail-open:snapshot_total==0 时恒 true |
| `governance.stake_weighted_quorum` | high | test | stake chamber 按 stake 加权而非地址计数(CIP-12 §6.2) | esc-20260608-cip12-stake-quorum |

### 状态 / 共识(state / consensus)

| 名称 | 严重度 | executor | 中文解释 | 设置原因 |
|---|---|---|---|---|
| `state.root_consistent_propose_verify_report` | high | proptest | Merkle root 在 propose/verify/report 三阶段一致(CIP-4) | esc-20260601-01:node 无 state/consensus 不变量家族 |
| `state.root_reflects_committed_set` | high | test(hand) | state root 反映已提交集(CIP-4) | esc-20260601-01 |
| `state.speculative_rollback_equivalent` | high | test(hand) | 投机执行回滚后等价于未执行(CIP-4) | esc-20260601-01 |
| `state.overlay_root_finalize_parity` | high | test *(candidate-red)* | 投机 overlay root 与扁平 finalize root 一致(CIP-4) | esc-20260624:Canyon 确定性停链(depth-3 tombstone 复活) |
| `state.timer_dispatch_wall_clock_independent` | high | test *(candidate-red)* | timer 派发不依赖墙钟(否则状态转移非确定)(COW-1272) | esc-20260605-timer-wallclock |
| `state.timer_list_height_bound` | high | test | 每高度 TimerList 写入要有上限(CIP-4) | esc-20260616:读端拒 >16384、写端无 per-height 上限 → 塞满单高度停链 |
| `state.mempool_no_stale_nonce_after_finality` | medium | proptest | finality 后 mempool 无陈旧 nonce(COW-2125) | esc-20260605-mempool-crossheight-floor |
| `consensus.logs_root_encoding_stable` | high | test | 事件→logs_root→receipt_root 编码稳定进共识(CIP-9 II) | esc-20260611:新增 ManifestCommitted 事件改变 receipt_root |
| `consensus.receipt_text_no_runtime_identity` | high | test | receipt 文本不得含运行时身份(堆指针) | esc-20260616:默认 `__repr__` 把 `0x..` 堆地址写进异常 → receipt_root 分叉 |

### 合约 / 编码 / 透传(contract / cross-repo)

| 名称 | 严重度 | executor | 中文解释 | 设置原因 |
|---|---|---|---|---|
| `contract.consensus_wire_frozen_vectors` | high | test | 共识 wire / 规范编码冻结向量(CIP-3) | esc-20260617:commonware rev bump 跨 consensus/codec/storage |
| `contract.message_codec_trailing_key_safe` | high | test | Message codec 对 QMDB Update 的 inline value+next_key 拆帧安全(CIP-1) | esc-20260609-message-codec-trailing-key |
| `contract.no_reentrancy_stale_state` | high | test | 跨 actor 重入 A→B→A 不得读到空/陈旧 cache(CIP-1) | esc-20260616-reentrancy-stale-state |
| `contract.structured_error_code_uniqueness` | high | test | 结构化错误码唯一(进 receipt) | esc-20260615:SecretAccessDenied=1703 与 LibCapExceeded 撞码 |
| `contract.sys_actor_addr_cross_namespace_unique` | high | test | 系统 actor 地址跨命名空间唯一(WP §9.1) | esc-20260630:0x14 加入无唯一性测试 |
| `contract.sys_actor_address_uniqueness` | high | test | 系统 actor 地址空间唯一(跨仓验证代码侧)(WP §9.1) | esc-20260629:spec 分配 0x14 未验证代码侧 |
| `contract.sys_opcode_uniqueness` | high | test | SystemInstruction opcode 唯一 | esc-20260608:CIP-12/CIP-16 重用 opcode 103-107 |
| `contract.sys_opcode_uniqueness_exhaustive` | high | test | opcode 唯一性测试必须穷举(不能只枚举 8 个硬编码)(CIP-13) | esc-20260619 |
| `contract.register_tld_label_codec_roundtrip` | high | conformance-vector | RegisterTldLabel 的 tx 编码 roundtrip(CIP-16 §8.2) | esc-20260608:codec 向量只覆盖 Transfer |
| `contract.tx_canonical_vectors_cover_actor_and_multisig` | medium *(pending)* | proptest | 规范 tx 字节向量要覆盖 actor+multisig(COW-1945) | esc-20260616:只冻结 Transfer(TV1/TV2) |
| `contract.upgrade_subset_param_drop_is_broadening` | high | test | 升级授权子集:丢约束参数=放宽(CIP-6) | esc-20260616:只遍历新 grant 参数 → 丢 max_bytes 误判兼容 |
| `contract.actor_intent_broadcast_diffs_capped` | medium | test | intent_broadcast 的 diff 数要有上限(CIP-34) | esc-20260701:in-memory 构造无 cap 绕过 wire rangecfg |
| `contract.cae_result_hash_matches_submitted_data` | high | proptest | CAE `result_hash` 匹配提交 data(embedding 前后一致)(CIP-23 §3.11) | esc-20260619:attest 在 embedding mutate data 前 |
| `contract.settle_rejects_cross_chain_intent` | high | proptest | `settle_bundle` 硬拒 `kind!=Settle`,跨链走 request_withdraw v2(CIP-34) | esc-20260704 |
| `contract.cbss_reshare_emitter_single_channel` | high | test | reshare 事件 3 个 tx-context emitter 都要迁到单一 channel(CIP-24 §3.6.2) | esc-20260701:漏了第 3 个 |
| `contract.gc_nonces_head_clamp` | high | proptest | GcNonces 的 `upto_block` 要 clamp 到 head(CIP-24 §3.4.6) | esc-20260701:`u64::MAX` 删未来 nonce |
| `contract.gc_nonces_receipt_freshness` | high | proptest | GcNonces 不得删 REQUEST_FRESHNESS 内在飞 release-receipt(CIP-24 §3.5) | esc-20260701:head-clamp 是 no-op |
| `contract.gc_nonces_tee_nonce_freshness` | high | proptest | GcNonces 不得删 MAX_QUOTE_AGE 内新鲜 TEE nonce,防重放(CIP-23 §3.8.3) | esc-20260701 |

### PVM / 确定性(pvm / determinism)

| 名称 | 严重度 | executor | 中文解释 | 设置原因 |
|---|---|---|---|---|
| `pvm.reflection_indirect_bypass_blocked` | high | test | 拦截间接反射(`e=eval;e()`、`getattr(__builtins__,'eval')`)(WP §3) | esc-20260610:只拒裸 eval/exec |
| `pvm.strict_simulation_allows_valid_code` | high | test | `--strict` 下合法 actor 码不得误拒(COW-366) | esc-20260605-pvm-ci-gap |
| `pvm.cold_determinism_stdlib_import_allowed` | high | test | 冷解释器确定性编译不得对 Mode::Exec 导入模块跑 FSM transform(WP §3 / COW-2229) | esc-20260611:误拒 stdlib `_collections_abc.py` |
| `pvm.blacklisted_module_blocked_even_if_precached` | high | test | 已在 `sys.modules` 的黑名单模块(`import os`)也要拦 | esc-20260616:import_inner 在检查前短路 sys.modules |
| `pvm.entrypoint_not_boundary_rejected` | high | test | 非法/空 entrypoint 要在执行边界拒(共识确定)(COW-158) | esc-20260609 |
| `pvm.int_precheck_no_prealloc_dos` | high | proptest | int 上限要**预检**(不能已分配后再查)防 DoS | esc-20260714:`2**1e9`/`factorial(1e6)` 先分配再查 |
| `determinism.handler_load_gas_independent_of_cache` | high *(candidate-red)* | test | handler-load gas 不依赖进程内 bytecode cache(否则跨验证者非确定)(CIP-26 §3.6 R13) | esc-2026-06-05-01 |

### 授权 / 安全 / 加密 / TEE / 钱包(auth / security / crypto / tee / wallet / ras)

| 名称 | 严重度 | executor | 中文解释 | 设置原因 |
|---|---|---|---|---|
| `cbfs.audit_get_shard_authenticated` | high | test | `audit_get_shard` 要认证,不能裸返 shard_bytes(CIP-9) | esc-20260616:请求无签名字段 |
| `cbfs.owner_cap_token_signature_verified` | high | test | OwnerCapToken 的 Ed25519 签名要验证 | esc-20260616:verify 函数零调用点 |
| `cbfs.placement_record_volume_bound_to_cap` | high | test | `PlacementRecord.volume_id` 要绑到 cap(CIP-9) | esc-20260616:授权时 volume_id=None |
| `cbfs.existence_hiding_no_timing_leak` | high | review | GetShard 存在性 oracle 要防时序泄漏(auth 前不得查存在)(COW-2311) | esc-20260618 |
| `cbss.none_policy_requires_same_account` | high | test | release policy `actors==None` 时要求 same-account(CIP-24 §3.1.5) | esc-20260616:恒返 Ok 省略同账户校验 |
| `crypto.cbss_ibe_roundtrip` | high | proptest | cbss-crypto IBE 加密 roundtrip 要有不变量覆盖(CIP-24) | cbss-crypto-no-invariant:仅 1 个 golden test |
| `cbss.threshold_any_t_recovers` | high | proptest | 任意 t-quorum 的部分签名 Lagrange 组合恢复同一 identity·secret,<t 必失败(CIP-24 释放正确性核心) | hand 基座(cbss onboarding);pack 早有验证 proptest,2026-08-17 seed 进 DB |
| `cbqs.at_least_once_safe_prefix_holds` | high | test | 非终态租约过期**不得**把消费组 safe-prefix 推过仍可重投的记录,否则静默丢消息(CIP-39 交付正确性核心) | hand 基座(cbqs onboarding);锚定已验证测试 `nonterminal_lease_expiry…`,2026-08-17 |
| `marshal.hazard_cbss_mpk_covers_kernel_mirrors` | high | pytest | CBSS IBE wrap key 要有 per-message ephemeral(否则可从链公钥+aad 重算)(CIP-24) | esc-20260611-cbss-ibe-no-ephemeral |
| `runner.cip9_aad_sensitive_to_release_key_material_hash` | high | conformance-vector | SealedDekPartial 的 HPKE AAD 要绑 `release_key_material_hash`(CIP-9) | esc-20260608:反序列化丢字段,HPKE-open 全失败 |
| `tee.chip_root_verify_deterministic` | high *(pending)* | proptest | chip-root SNARK verify 要确定(13 MUSTs / 0 不变量)(CIP-23 §3.8.4) | esc-20260616 |
| `tp.percall_settle_fail_closed_under_stub` | high | proptest | PerCall 结算在 stub validator 下要 fail-closed(CIP-33 / CIP-8) | esc-20260614:stub 无签名检查信任攻击者 |
| `wallet.message_sign_domain_separated` | high | test | 钱包 signMessage 要域分离,不盲签任意 32 字节 hash | esc-20260616-wallet-blind-signmessage:弹窗只显示 "Sign Message" |
| `spec.cip15.route_manifest_volume_entitlement` | high | test | route manifest 的 volume 要在 actor 的 static_volumes 内(CIP-15 v2 §6.8) | cow1293-sec-6-8 |
| `indexer.list_response_capped` | medium | test | indexer list 响应要真有 cap(测试非恒真)(COW-602/704) | esc-20260609:cap 测试恒真 |
| `cli.plaintext_remote_rpc_warning_funnel` | medium | proptest | 明文 RPC 警告要覆盖所有 `--rpc-url` 入口(COW-707) | esc-20260610:per-command flag 绕过单一 funnel |
| `cip7.ciphertext_access_not_entitlement_gated` | medium | test | 密文访问不得仅靠本地 sender-keyed entitlement cache(CIP-7 §5) | esc-20260608 |

### CI 安全(ci-security)—— 含 review-hazard 阶段二属性

| 名称 | 严重度 | executor | 中文解释 | 设置原因 |
|---|---|---|---|---|
| `ci.secret-exposed-to-untrusted-trigger` | high | **review-hazard** | 长期 `*_TOKEN` 不得暴露在 pull_request 可达 job 的 job-level env(无 environment gate) | esc-20260613:coverage.yml 暴露 CROSS_REPO_TOKEN |
| `ci.unpinned-action-on-secret-pr-job` | high | **review-hazard** | 暴露 secret 的 PR job 不得用未 pin 的 action(供应链) | esc-20260613:`taiki-e/install-action@nextest` 未 pin |
| `marshal.ci_threat_model_detects_pwn_request` | high | test | Marshal 的 CI 威胁模型要能识别 pwn-request 类误配 | esc-20260609:Marshal PASS 了 Almanax 抓到 3 个真误配的 PR |
| `marshal.classifier_flags_ci_workflows` | mid | test | 分类器要对 `.github/workflows` 有规则,不 mis-default 成 mid | esc-20260609:CI workflow 无分类规则 |

### 规格 / 宪法 / 治理漂移(conformance / spec / spec-governance)

| 名称 | 严重度 | executor | 中文解释 | 设置原因 |
|---|---|---|---|---|
| `conformance.system_actor_addrmap_consistent` | high | pytest | 系统 actor 地址表跨 CIP 一致(WP §9 / CIP-12 §1) | esc-20260605-wp-0x0d-addrmap:WP 把 0x0D 分给 Stream Key Manager 与 CIP-7/2/28 冲突 |
| `cip16.reserved_labels_rejected` | medium | proptest | 保留标签(api/dns/relay/node)要拒注册(CIP-16 §8.4) | esc-20260608:RESERVED_LABELS 漏了它们 |
| `hazard:cip-unchanged-claim-drift` | mid | **review** | CIP 声称「WP 未改」但实际改了分配模型 → 漂移(WP §8.3 vs CIP-36 §4.3/§11) | esc-20260717:CIP-36 §11 断言 §8.3 unchanged 而 §4.3 重定义 |

---

## 三、状态小计

> ⚠️ 本清单是 **DB `invariant_registry` 的快照**,不是 pack 全量目录 —— 两者的关系见下方「四、」。DB 是需求驱动的物化视图,数字会随「哪些不变量被真实 PR 行使过」变化。

- **DB 现有 83 条**(2026-08-17;编制时 72 → seed cbss/cbqs onboarding 基座 → `reconcile --apply` 补 6 条 catalog 滞后 → onboard cowboy-protocol/gateway/runner 三仓各 1 条基座)。按 status:`active` 78 · `candidate-red` 3 · `pending` 2。
- 按 executor:`test` 44 · `proptest` 26 · `conformance-vector` 7 · `pytest` 2 · `review` 2 · `review-hazard` 2。
- origin:`ratchet` 68(逃逸棘轮)· `hand` 15(手写基座:4 条 econ/state 种子 + cbss/cbqs/cowboy-protocol/gateway/runner onboarding + reconcile 补的 catalog 条目)。
- 严重度:`high` 71 · `medium` 9 · `mid` 3。
- 覆盖 repo:`node` 63 · `marshal` 7 · `cbfs` 5 · `runner` 3 · `cbss` 1 · `cbqs` 1 · `gateway` 1 · `cowboy-protocol` 1 · `wallet` 1。

---

## 四、为什么目录「最近不长」、新 repo 却是 0

这是最常见的误解:「Marshal 一直在审,为什么不变量表几乎不增长?尤其新接入的 cbqs 是 0?」

### 4.1 不变量从**棘轮**长出来,不从审计长出来

新不变量的**唯一常规来源**是棘轮(ratchet):一个**逃逸(escape)**——真漏过 review、事后才抓到的 bug——被人显式 `cli ratchet-open` 立案,才生成一条 `spawned_check`(见「二」里绝大多数 `origin=ratchet` 的行)。

日常 Marshal 审计(dashboard / sweep 深审)产出的是 **gate_run verdict + advisory 发现**,**不会自动变成不变量**。这一步是刻意的人工策展:要有人判定「这是一个真的、漏过去的缺口」才立案。所以:

- **「一直在审」≠「目录一直长」。** 两者是两条独立的线。
- **审到 ≠ 逃逸。** 棘轮只为「漏过、事后补」的 bug 立案。当场 escalate 拦下的问题**依定义不上棘轮**——这是健康信号,不是缺口。
- 目录停滞的正确解读:近期没有够格立案的逃逸(好),**或**有逃逸/发现但没人做 `ratchet-open`(流程缺口)。最新一条逃逸是 `esc-20260727`,之后一段时间没有新立案,故目录自然平。
- 另有 2 条逃逸**刻意留 open、不上棘轮**:`esc-20260610`(pytest 没进 CI —— 明写「留 open 直到 check 实作,以免造成 'running 0 tests' 的幽灵不变量」)、`esc-20260619`(Agent job 路径穿越 —— 校验尚未实作,没有能绿的 test 可锚)。**硬补会制造这套系统严防的幽灵不变量。**

### 4.2 DB `invariant_registry` 是**需求驱动**的镜像

dashboard 的「某 repo=0」多半不是「没规则」,而是**镜像滞后**。有两层:

- **权威 catalog = `marshal_pack_cowboy/pack.py`**(`_ECON/_STATE/_CBFS/_CBSS/_CBQS_INVARIANTS` 等 + `_REPO_HIGH_PREFIXES` 分类规则)。这是真正的「有哪些不变量」。
- **DB `invariant_registry`(dashboard `/api/invariants` 读它)只在真实 PR 经过 gate 时才 `register_invariant`**。所以 `cbfs` 有 4 条(被 PR 触发过),而 `cbss`/`cbqs` 的 proptest 锚长期显示 0 —— **pack 里有,只是没被任何 PR 行使过**。

要让某 repo 立刻在 dashboard 出现:`POST /plan` 一个合成事件走系统自己的登记路径(`register_invariant` 默认 `status=active, origin=hand`,正是 hand-seeded 基座语义),别 ad-hoc 写库。改了 `pack.py` 还**必须重启 uvicorn/worker**(它们启动时 import pack,否则 `/plan`、`/classify`、`/api/invariants` 全用旧逻辑)。

### 4.3 新 repo onboarding 的三件事(以 cbqs 为例,2026-08-17)

新接入的 repo 目录是空的,要**主动 onboard**,不能等它自己出第一个逃逸。cbqs 之前三缺,已在 marshal `main 92b5817` 补齐:

1. **加进 `_REPO_HIGH_PREFIXES`** —— 否则它的核心安全/正确性改动被分类器默认成 `mid`。cbqs 的交付正确性 / 签名 receipt-chain / StreamGrant 授权面(`receipt`/`authorization`/`standard_*`/`broker_state`/`storage`/`transport/chain`)现判 `high`。
2. **hand-seed 至少一条 baseline 不变量**,锚定**真实、已验证会绿**的测试(绝不凭空造 —— 否则就是 4.1 警告的幽灵不变量)。cbqs 用 `cbqs.at_least_once_safe_prefix_holds`(at-least-once:非终态租约过期不得推进 safe prefix)。
3. **加进 `pr_inbox._DEFAULT_REPOS`** —— 否则它的 PR 根本不进 Review Queue。

> cbss 情况相同(pack 早有已验证 proptest 锚,DB 长期 0),同法于 2026-08-17 seed。其余新 repo 接入照此三步。

**2026-08-17 批量 onboard 其余 cowboyinc code 仓**(每条 baseline 都锚定在 repo head **实测通过**的真实测试,`running 1 test; ok`,非幽灵):

| repo | 分类前缀(→high) | baseline 不变量 | 锚定测试 | 钉住的属性 |
|---|---|---|---|---|
| **cowboy-protocol** | `codec/` `types/` `cbss-crypto/` | `protocol.tx_canonical_bytes_identical_to_node`(conformance-vector) | `cowboy-protocol-codec` `golden_vectors_byte_identity` ⚠️需 `--features signing` | signing-preimage/hash/提交编码与 canyon node **字节相同**,drift=硬分叉 |
| **gateway** | `gateway-x402/` `gateway-server/src/{payment_state,chain_payments,x402,mpp}` `gateway-chain/` | `gateway.x402_no_double_serve_before_settle`(test) | `gateway-x402` `tests::reservation_blocks_concurrent_same_key` | serve-before-settle 双花守卫:同凭证并发 claim 被拒 |
| **runner** | `result-verifier/` `runner-consensus/` `canonical_result_parity` `job-dispatcher/` `runner-container/src/{sandbox,oci,runc}` `tee-verifier/`… | `runner.majority_vote_rejects_below_threshold`(test) | `result-verifier` `verifier::tests::test_majority_vote_threshold_not_met_fails` | N-of-M 门槛未达必须拒绝认证,不放行无共识的错误 off-chain 结果 |

⚠️ **cowboy-protocol 的 feature-flag 陷阱**:整个 golden 测试档是 `#![cfg(feature="signing")]`,`run_command` **必须**带 `--features signing`,否则 `cargo test` 跑 0 test 静默假绿。已固化进 run_command;若哪天 flag 失效变 0-test,执行器的「≥1 test ran」检查会把它当 `degraded` 暴露,而非误 PASS。

**JS 仓的边界(store-admin / wallet)**:两者已进 `_DEFAULT_REPOS`(PR 进 Review Queue),但**机械执行器只支持 cargo/pytest**,没有 JS 跑法,所以给不出会绿的 mechanical baseline。它们的覆盖只能靠 `review`/`review-hazard`(阶段二)或等 JS 执行器落地。故 `reconcile` 的 `coverage_gaps` 仍会诚实列出 `store-admin`(和 docs-only 的 `cowboy`)—— 这是如实报告,不是遗漏。

### 4.4 一键对账:`marshal reconcile-invariants`

4.3 里「pack 有、DB 没有」的滞后**不用手动逐条 seed**,一条命令对账所有被审计 repo:

```bash
# 只检查(dry-run,不写库):列出每个 repo 缺哪些、哪些 pending 被跳过、哪些 repo 零覆盖
marshal reconcile-invariants
# 入库:把缺的 non-pending catalog 不变量写进 DB(等同一次性模拟所有 PR 触发登记)
marshal reconcile-invariants --apply
# 最严格:先在各 repo checkout 真跑锚定测试,只 seed 会绿的(彻底防幽灵不变量)
marshal reconcile-invariants --apply --verify --workspace /home/ubuntu/workspace
```

输出 `counts:{added/present/pending/unverified}` + `coverage_gaps_no_invariant`(catalog **和** DB 都为 0 的 bound repo = 真空白,需人工 onboard;docs-only 的 cowboy 除外)。

**安全性**(为何 `--apply` 不违反 4.1):它只 seed `not pending` 的 catalog 条目,与「一个 PR 恰好碰到该路径时会自动登记的那条」**完全相同**,不比正常 gate 流程更危险。铁律:① pending 一律跳过(幽灵守卫);② DB 已有的绝不覆盖(保住 ratchet 的 `origin`/`escape_id`);③ origin 从 `escape_registry.spawned_check` 忠实反查(有对应 escape=ratchet+escape_id,否则 hand);④ `--verify` 是可选加固,真跑测试(exit 0 且 ≥1 passed)才 seed。

**注意**:这只补「catalog 有但没入库」的滞后,**不会凭空发明新不变量** —— 真正的新覆盖仍靠 4.1 的棘轮(逃逸→ratchet-open)或 4.3 的人工 onboarding。`coverage_gaps` 报告帮你定位后者的目标。

> 2026-08-17 首次 `--apply` 补了 6 条从未被 PR 触发的 catalog 不变量(5 条 contract/跨-repo + `cbfs.erasure_any_k_reconstructs`);DB 从 74 → 80。重跑幂等(0 added)。
