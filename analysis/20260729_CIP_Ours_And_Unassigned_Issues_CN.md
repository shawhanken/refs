# CIP 当期可推进 · 我方与尚未指派的 Issue 清单

- **数据时点：2026 年 07 月 29 日 16:00（北京时间）**
- 数据源：Linear GraphQL API
- 配套 HTML 报告：`webreport/20260729_CIP_Open_Issues_List_CN.html`

范围是「当期可推进」这一组里负责人为我方（pavilionledger）以及尚未指派负责人的 Issue，共 147 条。已经扣除外部条件未具备、暂缓至 11 月发币之后这两组，客户团队名下的不在此列。按 CIP 分布：CIP-2 4 · CIP-3 1 · CIP-4 3 · CIP-5 2 · CIP-6 2 · CIP-7 3 · CIP-8 4 · CIP-9 19 · CIP-10 7 · CIP-11 9 · CIP-14 16 · CIP-15 1 · CIP-16 19 · CIP-18 1 · CIP-19 10 · CIP-20 4 · CIP-23 5 · CIP-24 2 · CIP-25 7 · CIP-28 16 · CIP-29 6 · CIP-30 6。

---

## 2026-07-30 更新（本地 triage + 交付 overlay，非 Linear 快照）

> 下表是在上面 07-29 Linear 快照基础上，经代码/规格核对与交付后的**当前实况**。快照本体保留未改；此节为 overlay。

### 已交付 / 进行中的 PR（node，base=devnet）

| Issue | CIP | PR | 状态 | 说明 |
|---|---|---|---|---|
| COW-2609 | CIP-9 | **#1187** | 加固后待 merge（CI 跑中） | write-relayer 错误可诊断：node-拒-tx（HTTP 200 `reverted`）转发 chain revert_reason→`422 tx_reverted`，408→`202 pending`，429→`upstream_busy`；保 no-leak。**off-chain 零共识** |
| COW-2828 | CIP-9 | **#1188** | ✅ MERGED | per-gate reject 指标 `ras_rejections_total{endpoint,reason}`；纯 RPC 观测、零共识；almanax LOW 已 resolve（`/metrics` LocalOperational） |
| COW-2114 | CIP-9 | **#1189** | ✅ MERGED | finalize 授权改「当前 owner」非 `staged_by`（CIP-9 §7.3.1，dormant flag-day）；修 sub-agent 自 finalize/former-owner/deleted-vol 三洞 |
| COW-2554 | CIP-11 | #1185 | ✅ MERGED（早批） | 删 first-assignment JobTimeoutRecord（dormant） |
| COW-2553 | CIP-11 | #1186 | ✅ MERGED（早批） | timeout 退款排除 tip（dormant） |
| COW-2177 | CIP-4 | #1181 | ✅ MERGED（早批） | fast-sync bench ≥10×；同时揭出并修 pruned-peer 生产 hang |
| COW-1621 | CIP-11 | #1180 | ✅ MERGED（早批） | §14 phase-config（dormant，poll_disabled→410） |

### 判「已完成 / close 候选」（代码核对，前提陈旧）

| Issue | CIP | 结论 |
|---|---|---|
| COW-2109 | CIP-2 | **已完成**——`SlashDistribution` schema + challenger payout(`submitter_amount`) + submission sum 校验(`system_instruction.rs:2803-2808` 拒 sum≠10000) 全在；唯「activate 50/30/20」违 WP §8.4 C7、属治理 value-flip 故意 defer。**建议关 Done** |
| COW-2827/927/2152/2831/2833/2830/2663 | CIP-9 | 早批 triage 判已 shipped / close 候选（storage-capable committee filter / PoR endpoint / validate_relay_deltas / cbfs·runner·cbss 各项 / FUSE zero-root #111） |

### 判「spec-deferred / 大 build / 低优」（本轮不做，附理由）

| Issue | CIP | 结论 |
|---|---|---|
| COW-962 | CIP-2 | **spec-deferred**——CIP-2 §738 明写 objective-failure challenge-window semantics **out-of-scope for CIP-2**（WP §9.2 target semantics 未定），不可现建 |
| COW-1399 | CIP-3 | **真缺口但 LOW**——§2.2.4.8 import cycle 费(100/5/50)完全未实作(`guard.rs::_pvm_import` 零计费；PVM 无 per-bytecode 计量)；但主 DoS 面是更大的无计量纯计算洞，且修复=共识 PVM+dormant+真机测试。**shelve，排在 metering 工作后**（计划见 scratchpad `cow-1399-import-penalty-plan.md`） |
| CIP-14 全簇(1663-1681) | CIP-14 | **大 net-new build**——L1 ingress plumbing 基本 ABSENT：`IngressDispatch`(op65)/`complete_receipt`(op66)/`ExternalDomainCallback`(op67) 三 opcode 都不存在；`GATEWAY_REGISTRY`(0x0F)/`RECEIPT_REGISTRY`(0x10) 只有地址常量零 handler。需另立多-PR campaign |
| CIP-16 全簇(1705-1724) | CIP-16 | **first-party TLD Route Registry(0x0E,op103/105/106) 已 BUILT+dispatched**（`execution/src/runner/domain.rs`，`ingress.http` entitlement 已强制）；**external domain DNS 生命周期 UNBUILT**（`execute_dns_job`/`maybe_enable_dns_capability` 是死代码，producer `begin_attach_external` 缺失——单接执行器会点亮无源路径，**别做**）。地址注：ROUTE=0x0E/GATEWAY=0x0F/RECEIPT=0x10 是故意（0x0D 撞 CIP-7，已 reconcile），非 bug |
| CIP-19 全簇(1761-1788) | CIP-19 | MCP ingress 实质**已建但在 gateway 仓**（`/_cowboy/mcp`、`ingress.mcp` gate、tools→envelope 翻译），非 node scope |

### 深审结论（无 active bug，记录以免重扫）

- **governance enact 校验一致性审计**：全 24 个 `ProposalPayloadKind` 的 payload 不变量都在 submission 或 enactment 被校验，无可绕过旁路；generic `SubmitProposal` 是 basefee-specific 非任意 payload；TreasuryDisbursement 在 enactment 由 treasury 余额上界守好。**路径健全**。
- **UpgradeSystemActor（CIP-12 §7）**：`new_code_hash` 提交/enactment 都不校验可解析——但 runtime **零消费**该 version record（系统 actor 跑 native Rust，dispatcher code-swap「not yet on-chain」，cip-12:315），故 dangling hash **今日无 brick、无 bug**。**前瞻前提**：将来接线 code-swap 时须同批加 on-chain hash-resolvability 闸。另 spec 不一致：§7.2.1 pausable allowlist 含 `0x1D` 但 §7 line 129 说 virtual actor 不 bytecode-swap（待 spec owner）。详见 `refs/analysis/2026-07-30-cip12-s7-system-actor-upgrade-notes.md`。

**本轮教训**：成熟 backlog 的剩余「Backlog」多为 stale-done / 大 build / spec-blocked；单票 probing 低产。真 bug（如 COW-2114 live spec-violation）来自定向 spec-vs-code 不变量审计，非逐票扫。

---

## 2026-07-31 更新（续 overlay：CIP-11/8/29 triage + 交付 + Linear routing）

### 交付 / PR 状态（node，base=devnet）

| Issue | CIP | PR | 状态 | 说明 |
|---|---|---|---|---|
| COW-2609 | CIP-9 | #1187 | ✅ MERGED | write-relayer 可诊断（加固后：转发 chain revert_reason→422、408→202 pending） |
| COW-2828 | CIP-9 | #1188 | ✅ MERGED | per-gate reject 指标 |
| COW-2114 | CIP-9 | #1189 | ✅ MERGED | finalize owner-authority（dormant） |
| **COW-1150** | CIP-29 | **#1193** | 新开 | subscribe_event 加 `events.subscribe` entitlement 门禁（dormant coarse-gate）；**activation 前置=生态迁移**（现存 subscriber 须重部署带上 entitlement） |
| **COW-2552** | CIP-11 | ~~#1190~~ | **CLOSED** | defer-then-slash 深审判**殺好人放壞人**（HIGH-1 forecloses honest reveal-race loser→误 slash）；完整解方(C1 结算后接受+验证遲到揭示以区分)会碰 COW-2286 escrow-terminality guard、为中低 griefing 不成比例；**判 low-severity，reputation-only 上限，不实作** |

### Triage 结论（本地 + Linear 直读核实）

- **CIP-8 session 簇**：**COW-1012（pin session chain_id）= 真 replay gap 但 launch-gated + 设计冲突**——voucher EIP-712 chain_id 硬编码=1、与真 chain_id 解耦 + caller-supplied session_id → 跨链 voucher 重放;但同常量被 CIP-9 volume-DEK 故意用作**跨链 portable** 身份（cbss.rs:832-838），不能简单改值，须**拆分两用途**。单链 devnet 不可利用；第二条链前必修。cross-repo + dormant。design note: `2026-07-31-cow1012-session-chainid-binding.md`。其余：COW-1013(dispute 路径 spec=future work)、COW-1542(feature)、COW-1543(runner infra)。
- **CIP-29 事件订阅簇**（Linear 直读）：**COW-1922/1923 = Done**（close 候选，关前 spot-check）；**COW-1150 已交付 #1193**；COW-1917(EmitResult 未 surface=改 SDK-in-binary 契约=共识面,大)、COW-1147(receipt causality=改 receipt_root)、COW-1152(schema 校验 opt-in)皆共识面 feature work。

### Linear routing（用 team API key,仅贴 comment 未改状态）
COW-2552 / COW-1012 / COW-1150 均已贴 decision-ready comment（英文,指向 refs 分析檔）。COW-2114 已 Done、其 CIP-9 spec follow-up 在 PR#1189,无需 route。

### 深审沉淀（本轮新教训）
- **审「分类/惩罚」机制必问「无辜者与作恶者能否区分」**（COW-2552:foreclosed-honest 与 refused 同形,都不存 result→defer-then-slash 错杀多数派）。
- **修低 severity 别碰资金守恒关键路径**（COW-2552 碰 COW-2286 escrow-terminality）；**「完整/尽善尽美」方案也要深审——过度工程本身是缺陷**。
- **审「订阅/注册/共用常量」**：subscribe 只收费不鉴权(COW-1150)；一个 chain_id 常量同时要「绑链」与「跨链 portable」目标相反(COW-1012)。
- **pvm_host 层 dormant-gate**：给 PvmExecutionContext 加字段 + engine post-new 设（不改 async new 签名）。

## 我方负责 · 44 条

| Issue | CIP 项目 | 状态 | 标题 |
|---|---|---|---|
| [COW-1377](https://linear.app/cowboy-labs/issue/COW-1377/8-aggregator-collects-result-bytes-via-direct-http-push) | CIP-2 | Backlog | §8 'Aggregator collects result_bytes via direct HTTP push' + |
| [COW-1308](https://linear.app/cowboy-labs/issue/COW-1308/examples-cip-2-v3-end-to-end-economic-e2e-example-and-case-study) | CIP-2 | Todo | [Examples] CIP-2 v3 end-to-end economic e2e example and case study |
| [COW-962](https://linear.app/cowboy-labs/issue/COW-962/node-dispute-window-on-chain-challenge-evidence-re-verification) | CIP-2 | Todo | [Node] Dispute window: on-chain challenge / evidence / re-verification handler |
| [COW-2177](https://linear.app/cowboy-labs/issue/COW-2177/node-benchmark-fast-sync-bootstrap-speedup-vs-genesis-replay-10x-cow) | CIP-4 | Backlog | [Node] Benchmark fast-sync bootstrap speedup vs genesis replay (>10x, COW-977 acceptance) |
| [COW-1406](https://linear.app/cowboy-labs/issue/COW-1406/73-auxiliary-index-fullincremental-rebuild-from-ledger-routine) | CIP-4 | Backlog | §7.3 Auxiliary-index full/incremental rebuild-from-ledger routine |
| [COW-1274](https://linear.app/cowboy-labs/issue/COW-1274/architectural-decouple-timer-execution-from-proposes-critical-path) | CIP-5 | Todo | Architectural: decouple timer execution from propose's critical path |
| [COW-986](https://linear.app/cowboy-labs/issue/COW-986/docs-cip-9-12-example-actor-calling-schedule-timer-exfee-payerstorage) | CIP-5 | In Progress | [Docs] CIP-9 §12 example: actor calling schedule_timer_ex(fee_payer=STORAGE_MANAGER, ...) |
| [COW-2824](https://linear.app/cowboy-labs/issue/COW-2824/sdk-guard-verification-is-inert-for-every-compiled-fsm-actor-guard) | CIP-6 | Backlog | [SDK] Guard verification is inert for every compiled FSM actor — guard_keys never reaches save_cont |
| [COW-1005](https://linear.app/cowboy-labs/issue/COW-1005/node-deterministic-stream-event-emission) | CIP-7 | Backlog | [Node] Deterministic stream event emission |
| [COW-1003](https://linear.app/cowboy-labs/issue/COW-1003/nodesdk-optional-cip-2-ingestion-config-timer-task-submission) | CIP-7 | Backlog | [Node/SDK] Optional CIP-2 ingestion config: timer → task submission → transform → encrypt → publish |
| [COW-997](https://linear.app/cowboy-labs/issue/COW-997/nodesdk-filter-dsl-depth-4-16-predicates-validation-compilation) | CIP-7 | Backlog | [Node/SDK] Filter DSL (depth ≤4, ≤16 predicates) — validation + compilation + evaluation |
| [COW-1543](https://linear.app/cowboy-labs/issue/COW-1543/45-runner-session-bootstrap-relies-on-a-poc-sessionobserve-http-push) | CIP-8 | Backlog | §4/§5 Runner session bootstrap relies on a PoC /session/observe HTTP push |
| [COW-2834](https://linear.app/cowboy-labs/issue/COW-2834/cbfsrunner-enforce-cip-9-1214-volume-access-modes-rowo-blocks-cow-937) | CIP-9 | Backlog | [CBFS/Runner] Enforce CIP-9 §12.1.4 volume access modes (RO/WO) — blocks COW-937 |
| [COW-2833](https://linear.app/cowboy-labs/issue/COW-2833/cbfs-long-lived-write-cap-tokens-for-large-streaming-writes) | CIP-9 | Backlog | [CBFS] Long-lived write cap tokens for large streaming writes |
| [COW-2832](https://linear.app/cowboy-labs/issue/COW-2832/noderunner-runnervalidator-version-and-tx-format-compatibility) | CIP-9 | Backlog | [Node/Runner] Runner↔validator version & tx-format compatibility negotiation |
| [COW-2831](https://linear.app/cowboy-labs/issue/COW-2831/cbfs-zero-config-cbfs-client-full-chain-discovery-bootstrap) | CIP-9 | Backlog | [CBFS] Zero-config CBFS client — full chain-discovery bootstrap |
| [COW-2830](https://linear.app/cowboy-labs/issue/COW-2830/cbssrunner-cip-9-92-sealed-dek-read-path-cbss-endpoint-discovery-for) | CIP-9 | Backlog | [CBSS/Runner] CIP-9 §9.2 — sealed-DEK read path + CBSS endpoint discovery for encrypted volumes |
| [COW-2829](https://linear.app/cowboy-labs/issue/COW-2829/specnode-cip-9-7-elevate-volume-access-to-first-class-access-classes) | CIP-9 | Backlog | [Spec/Node] CIP-9 §7 — elevate volume access to first-class access classes |
| [COW-2828](https://linear.app/cowboy-labs/issue/COW-2828/node-cip-9-821-dispatch-eligibility-diagnostics-structured-per-gate) | CIP-9 | Backlog | [Node] CIP-9 §8.2.1 — dispatch-eligibility diagnostics (structured per-gate exclusion telemetry) |
| [COW-2827](https://linear.app/cowboy-labs/issue/COW-2827/node-cip-9-421821-storage-capable-committee-filter) | CIP-9 | Backlog | [Node] CIP-9 §4.2.1/§8.2.1 — storage-capable committee filter + InsufficientStorageCapableRunners |
| [COW-2663](https://linear.app/cowboy-labs/issue/COW-2663/cbfs-fuse-manifest-refresh-computes-zero-root-after-rw-state-sync) | CIP-9 | In Progress | CBFS FUSE manifest refresh computes zero root after RW state sync |
| [COW-2113](https://linear.app/cowboy-labs/issue/COW-2113/node-public-volume-commit-prefix-confinement-check) | CIP-9 | Todo | [Node] Public-volume commit prefix-confinement check |
| [COW-2099](https://linear.app/cowboy-labs/issue/COW-2099/cip-9-rewrite-epic-triage-grounded-findings-from-mesa-bring-up-cip-9) | CIP-9 | Backlog | [CIP-9] Rewrite epic: triage grounded findings from mesa bring-up (cip-9-rewrite-ideas.md) |
| [COW-937](https://linear.app/cowboy-labs/issue/COW-937/runner-add-cip-9-integration-tests-manifest-round-trip-access-modes) | CIP-9 | Backlog | [Runner] Add CIP-9 integration tests (manifest round-trip, access modes, cache stress) |
| [COW-927](https://linear.app/cowboy-labs/issue/COW-927/node-post-raschallenge-endpoint-chain-state-challenge-records) | CIP-9 | Backlog | [Node] POST /ras/challenge endpoint + chain-state challenge records |
| [COW-2615](https://linear.app/cowboy-labs/issue/COW-2615/runner-unify-the-two-runner-node-mains-root-pkg-vs-cratesrunner-node) | CIP-10 | Done | runner: unify the two runner-node mains (root pkg vs crates/runner-node) |
| [COW-2504](https://linear.app/cowboy-labs/issue/COW-2504/cip-10-tee-signed-billingattestation-cip-23-compositeattestation) | CIP-10 | Done | CIP-10: TEE-signed BillingAttestation (CIP-23 CompositeAttestation) |
| [COW-2555](https://linear.app/cowboy-labs/issue/COW-2555/node-identify-the-1-in-6-flaky-cowboy-execution-test-seen-during-the) | CIP-11 | Canceled | [node] Identify the 1-in-6 flaky cowboy-execution test seen during the COW-2532 gate |
| [COW-1621](https://linear.app/cowboy-labs/issue/COW-1621/14-three-phase-migration-shadow-hot-path-sunset-gated-by) | CIP-11 | Backlog | §14 Three-phase migration (Shadow / Hot Path / Sunset) gated by |
| [COW-1609](https://linear.app/cowboy-labs/issue/COW-1609/94-result-verifier-write-path) | CIP-11 | Done | §9.4 Result Verifier write path |
| [COW-1608](https://linear.app/cowboy-labs/issue/COW-1608/94-new-dispatcher-state) | CIP-11 | Done | §9.4 New dispatcher state |
| [COW-2826](https://linear.app/cowboy-labs/issue/COW-2826/nodespec-cip-20-on-chain-allowancespender-secondary-index-re-scope-of) | CIP-20 | Backlog | [Node/Spec] CIP-20 on-chain allowance/spender secondary index (re-scope of COW-1083) |
| [COW-1082](https://linear.app/cowboy-labs/issue/COW-1082/explorer-token-balance-transfer-history-ui) | CIP-20 | Backlog | [Explorer] Token balance + transfer history UI |
| [COW-1073](https://linear.app/cowboy-labs/issue/COW-1073/spec-bridge-lock-and-mint-cip-for-eth-cowboy-l1-blocking-dollarcowboy) | CIP-20 | Backlog | [Spec] Bridge / lock-and-mint CIP for ETH ↔ Cowboy L1 (blocking $COWBOY Aug 2026 launch) |
| [COW-1103](https://linear.app/cowboy-labs/issue/COW-1103/node-attestation-first-runner-registration-registry-0x05verifycae) | CIP-23 | Backlog | [Node] Attestation-first runner registration (registry → 0x05::VerifyCae cross-call) |
| [COW-1901](https://linear.app/cowboy-labs/issue/COW-1901/2526-cross-chain-streaming) | CIP-25 | Todo | §2.5/§2.6 Cross-chain streaming |
| [COW-1899](https://linear.app/cowboy-labs/issue/COW-1899/16-multi-destination-cost-reduction) | CIP-25 | Backlog | §1.6 Multi-destination cost reduction |
| [COW-1897](https://linear.app/cowboy-labs/issue/COW-1897/14a5-optimistic-backend-with-challenger-bondsincentives) | CIP-25 | Todo | §1.4/§A.5 Optimistic backend with challenger bonds/incentives |
| [COW-1896](https://linear.app/cowboy-labs/issue/COW-1896/1415a5-zk-light-client-backend) | CIP-25 | Todo | §1.4/§1.5/§A.5 ZK light-client backend |
| [COW-1923](https://linear.app/cowboy-labs/issue/COW-1923/63-p1-e-emitter-actor-upgrade-redeployment-semantics-for-existing) | CIP-29 | Backlog | §6.3 P1-E emitter actor upgrade / redeployment semantics for existing |
| [COW-1922](https://linear.app/cowboy-labs/issue/COW-1922/23-zombie-subscription-bidregistration-fee-handling-on-reap-not) | CIP-29 | Backlog | §2.3 zombie subscription bid/REGISTRATION_FEE handling on reap not |
| [COW-1917](https://linear.app/cowboy-labs/issue/COW-1917/2124-emitresult-return-value-not-surfaced) | CIP-29 | Backlog | §2.1/§2.4 EmitResult return value NOT surfaced |
| [COW-1283](https://linear.app/cowboy-labs/issue/COW-1283/node-migration-policy-pick-wipe-devnettestnet-vs-online-any-future) | CIP-30 | Backlog | [Node] Migration policy: pick wipe (devnet/testnet) vs online (any future mainnet) + implementation |
| [COW-1277](https://linear.app/cowboy-labs/issue/COW-1277/node-state-set-state-delete-recompute-storage-root-in-cross-call-write) | CIP-30 | Backlog | [Node] state_set / state_delete recompute storage_root in cross-call write-set |

## 尚未指派 · 103 条

| Issue | CIP 项目 | 状态 | 标题 |
|---|---|---|---|
| [COW-2109](https://linear.app/cowboy-labs/issue/COW-2109/activate-503020-slash-split-wire-challenger-payout-fix-the-split-value) | CIP-2 | Backlog | Activate 50/30/20 slash split + wire challenger payout + fix the split-value inconsistency |
| [COW-1399](https://linear.app/cowboy-labs/issue/COW-1399/2248-import-penalty-cycle-costs-not-charged) | CIP-3 | Backlog | §2.2.4.8 Import penalty cycle costs not charged |
| [COW-2100](https://linear.app/cowboy-labs/issue/COW-2100/node-wire-fast-sync-into-bootstrap-10-bench-cow-977-follow-up) | CIP-4 | Backlog | [Node] Wire fast-sync into bootstrap + ≥10× bench (COW-977 follow-up) |
| [COW-987](https://linear.app/cowboy-labs/issue/COW-987/sdk-actor-side-runtimemountvolume-id-access-mode-for-cbfs-workflows) | CIP-6 | Backlog | [SDK] Actor-side runtime.mount(volume_id, access_mode) for CBFS workflows |
| [COW-1542](https://linear.app/cowboy-labs/issue/COW-1542/6416-sessionassetcip20-token-escrow-path) | CIP-8 | Backlog | §6.4/§16 SessionAsset::Cip20 token-escrow path |
| [COW-1013](https://linear.app/cowboy-labs/issue/COW-1013/code-when-slash-milestone-activates-extend-disputed-with-opened-at-u64) | CIP-8 | Backlog | [Code] When Slash milestone activates, extend Disputed with opened_at: u64 |
| [COW-1012](https://linear.app/cowboy-labs/issue/COW-1012/noderunner-pin-production-cowboy-session-chain-id) | CIP-8 | Backlog | [Node/Runner] Pin production COWBOY_SESSION_CHAIN_ID |
| [COW-2623](https://linear.app/cowboy-labs/issue/COW-2623/cow-918-follow-up-batchpipeline-por-response-submission-to-restore) | CIP-9 | Backlog | COW-918 follow-up: batch/pipeline PoR response submission to restore open-challenge cap |
| [COW-2609](https://linear.app/cowboy-labs/issue/COW-2609/ras-write-relayer-flattens-every-failure-to-400-errorrequest-failed) | CIP-9 | Backlog | RAS write-relayer flattens every failure to 400 {"error":"request failed"} — undiagnosable from the client |
| [COW-2184](https://linear.app/cowboy-labs/issue/COW-2184/cbfs-full-relay-rewards-distribution-pro-rata-by-shard-count-x-age) | CIP-9 | Backlog | CBFS: full relay rewards distribution (pro-rata by shard count x age) |
| [COW-2152](https://linear.app/cowboy-labs/issue/COW-2152/node-validate-per-relay-effective-deltas-at-commit-caller-trust-blast) | CIP-9 | Backlog | [Node] Validate per_relay_effective_deltas at commit (caller-trust blast radius) |
| [COW-2114](https://linear.app/cowboy-labs/issue/COW-2114/node-private-volume-staged-commit-finalize-authority-dek-holder) | CIP-9 | Backlog | [Node] Private-volume staged-commit finalize authority (DEK-holder) |
| [COW-1546](https://linear.app/cowboy-labs/issue/COW-1546/92-v2-secrets-manager-direct-sealed-dek-fetch-path-replacing) | CIP-9 | Backlog | §9.2 (v2) Secrets-Manager direct sealed-DEK fetch path replacing |
| [COW-2509](https://linear.app/cowboy-labs/issue/COW-2509/cip-10-dev-container-interactive-mode-exploratory) | CIP-10 | Backlog | CIP-10: dev-container / interactive mode (exploratory) |
| [COW-2507](https://linear.app/cowboy-labs/issue/COW-2507/cip-10-networked-containers-egress-accountingbilling) | CIP-10 | Backlog | CIP-10: networked containers + egress accounting/billing |
| [COW-2506](https://linear.app/cowboy-labs/issue/COW-2506/cip-10-gpu-billing-scheduling) | CIP-10 | Backlog | CIP-10: GPU billing + scheduling |
| [COW-1578](https://linear.app/cowboy-labs/issue/COW-1578/13-parameter-set-max-cpu-millicores) | CIP-10 | Backlog | §13 parameter set (MAX_CPU_MILLICORES |
| [COW-1575](https://linear.app/cowboy-labs/issue/COW-1575/122-image-pull-egress-fees-pull-cost-size-egress-fee-per-byte) | CIP-10 | Backlog | §12.2 image-pull egress fees (pull_cost = size * EGRESS_FEE_PER_BYTE |
| [COW-2554](https://linear.app/cowboy-labs/issue/COW-2554/node-delete-first-assignment-jobtimeoutrecords-at-settlement-state) | CIP-11 | Backlog | [node] Delete first-assignment JobTimeoutRecords at settlement (state-growth cleanup) |
| [COW-2553](https://linear.app/cowboy-labs/issue/COW-2553/node-incentive-design-exclude-the-tip-from-timeout-exhaustion-refunds) | CIP-11 | Backlog | [node] Incentive design: exclude the tip from timeout-exhaustion refunds so griefing is never gas-free |
| [COW-2552](https://linear.app/cowboy-labs/issue/COW-2552/node-62-settlement-classifier-misses-committed-not-revealed-stallers) | CIP-11 | Backlog | [node] §6.2 settlement classifier misses committed-not-revealed stallers when settlement lands inside their reveal window |
| [COW-2538](https://linear.app/cowboy-labs/issue/COW-2538/nodespecs-ack-timeout-early-112-re-selection-single-validator-cip-11) | CIP-11 | Backlog | [node+specs] ACK-timeout → early §11.2 re-selection (single-validator) + CIP-11 erratum — DECISION-GATED |
| [COW-1620](https://linear.app/cowboy-labs/issue/COW-1620/13-cip-11-system-constants-minmax-subset) | CIP-11 | Backlog | §13 CIP-11 system constants (MIN/MAX_SUBSET |
| [COW-1681](https://linear.app/cowboy-labs/issue/COW-1681/8691-96-gateway-node-role) | CIP-14 | Backlog | §8.6/§9.1-9.6 Gateway node role |
| [COW-1680](https://linear.app/cowboy-labs/issue/COW-1680/8182-orig-httprequestenvelope-httpresponseenvelope-canonical) | CIP-14 | Backlog | §8.1/§8.2 (orig) HttpRequestEnvelope / HttpResponseEnvelope canonical |
| [COW-1679](https://linear.app/cowboy-labs/issue/COW-1679/84-receipt-privacy-private-flag) | CIP-14 | Backlog | §8.4 receipt privacy (private flag |
| [COW-1678](https://linear.app/cowboy-labs/issue/COW-1678/8364-command-path-async-flow) | CIP-14 | Backlog | §8.3/§6.4 command-path async flow |
| [COW-1677](https://linear.app/cowboy-labs/issue/COW-1677/82-complete-receipt-system-call-opcode-66-registry-wide-ttl-pruning) | CIP-14 | Backlog | §8.2 complete_receipt system call (opcode 66) + registry-wide TTL pruning |
| [COW-1676](https://linear.app/cowboy-labs/issue/COW-1676/810-receipt-registry-0x0f-system-actor-receipt-record) | CIP-14 | Backlog | §8/§10 RECEIPT_REGISTRY (0x0F) system actor + Receipt record |
| [COW-1675](https://linear.app/cowboy-labs/issue/COW-1675/7494-gateway-serving-fee-pool) | CIP-14 | Backlog | §7.4/§9.4 gateway serving-fee pool |
| [COW-1674](https://linear.app/cowboy-labs/issue/COW-1674/63-gateway-gas) | CIP-14 | Backlog | §6.3 gateway gas |
| [COW-1673](https://linear.app/cowboy-labs/issue/COW-1673/6162-system-mediated-httprequest) | CIP-14 | Backlog | §6.1/§6.2 system-mediated http.request |
| [COW-1672](https://linear.app/cowboy-labs/issue/COW-1672/61-systeminstructioningressdispatch-opcode-65-command-path) | CIP-14 | Backlog | §6.1 SystemInstruction::IngressDispatch (opcode 65) command-path |
| [COW-1671](https://linear.app/cowboy-labs/issue/COW-1671/7292-gateway-lifecycle) | CIP-14 | Backlog | §7.2/§9.2 gateway lifecycle |
| [COW-1670](https://linear.app/cowboy-labs/issue/COW-1670/792-gateway-registry-0x0e-system-actor-gatewayprofile) | CIP-14 | Backlog | §7/§9.2 GATEWAY_REGISTRY (0x0E) system actor + GatewayProfile |
| [COW-1669](https://linear.app/cowboy-labs/issue/COW-1669/4777-route-registry-api) | CIP-14 | Backlog | §4.7/§7.7 Route Registry API |
| [COW-1668](https://linear.app/cowboy-labs/issue/COW-1668/4676-renewal-extend-from-current-expiry) | CIP-14 | Backlog | §4.6/§7.6 renewal (extend from current expiry) |
| [COW-1666](https://linear.app/cowboy-labs/issue/COW-1666/4575-registration-economics) | CIP-14 | Backlog | §4.5/§7.5 registration economics |
| [COW-1663](https://linear.app/cowboy-labs/issue/COW-1663/4272-naming-hierarchy-subdomain-policy-owner-only-default) | CIP-14 | Backlog | §4.2/§7.2 naming hierarchy + subdomain_policy (OWNER_ONLY default / |
| [COW-2178](https://linear.app/cowboy-labs/issue/COW-2178/node-land-on-chain-ingresshttp-static-volumes-binding-prereq-for-cip) | CIP-15 | Backlog | [Node] Land on-chain ingress.http + static_volumes binding (prereq for CIP-15 §6.8 route-volume enforcement) |
| [COW-1724](https://linear.app/cowboy-labs/issue/COW-1724/11-security-considerations-reverification-mandatory) | CIP-16 | Backlog | §11 security considerations (reverification mandatory |
| [COW-1723](https://linear.app/cowboy-labs/issue/COW-1723/128-external-constants-challenge-expiry-blocks) | CIP-16 | Backlog | §12/§8 external constants CHALLENGE_EXPIRY_BLOCKS |
| [COW-1722](https://linear.app/cowboy-labs/issue/COW-1722/10374-first-party-tld-dns-authority-serving-from-route-registry) | CIP-16 | Backlog | §10.3/§7.4 first-party TLD DNS authority serving from Route Registry |
| [COW-1721](https://linear.app/cowboy-labs/issue/COW-1721/73-verified-fqdn-namespace-kind-injection-into-httprequestenvelope-by) | CIP-16 | Backlog | §7.3 verified_fqdn + namespace_kind injection into HttpRequestEnvelope by |
| [COW-1720](https://linear.app/cowboy-labs/issue/COW-1720/107-gateway-resolution-and-serving-policy-active-only) | CIP-16 | Backlog | §10/§7 Gateway resolution & serving policy (ACTIVE-only |
| [COW-1719](https://linear.app/cowboy-labs/issue/COW-1719/9555-acme-dns-01-delegation-acme-challenge-cname) | CIP-16 | Backlog | §9.5/§5.5 ACME DNS-01 delegation (_acme-challenge CNAME → |
| [COW-1718](https://linear.app/cowboy-labs/issue/COW-1718/9454-canonical-edge-hostname-anycast-default) | CIP-16 | Backlog | §9.4/§5.4 CANONICAL_EDGE_HOSTNAME (anycast default |
| [COW-1716](https://linear.app/cowboy-labs/issue/COW-1716/510-reverify-timer-fee-payerowner-timercancelledinsufficientfunds) | CIP-16 | Backlog | §5.10 reverify timer fee_payer=owner + TimerCancelledInsufficientFunds |
| [COW-1715](https://linear.app/cowboy-labs/issue/COW-1715/58-external-reverify-fee-charged-from-owner-per-firing) | CIP-16 | Backlog | §5.8 EXTERNAL_REVERIFY_FEE charged from owner per firing |
| [COW-1714](https://linear.app/cowboy-labs/issue/COW-1714/57510-reverification-flow) | CIP-16 | Backlog | §5.7/§5.10 reverification flow |
| [COW-1713](https://linear.app/cowboy-labs/issue/COW-1713/maybe-enable-dns-capability-boot-time-self-check-not-production-wired) | CIP-16 | Backlog | maybe_enable_dns_capability boot-time self-check NOT production-wired |
| [COW-1712](https://linear.app/cowboy-labs/issue/COW-1712/execute-dns-job-not-production-wired-into-runner-worker-loop) | CIP-16 | Backlog | execute_dns_job NOT production-wired into runner worker loop |
| [COW-1711](https://linear.app/cowboy-labs/issue/COW-1711/53-begin-attach-external-enqueuing-a-dns-verification-jobspec-into) | CIP-16 | Backlog | §5.3 begin_attach_external enqueuing a DNS-verification JobSpec into |
| [COW-1710](https://linear.app/cowboy-labs/issue/COW-1710/56-suspendbinding-failure-path-opcode-0x03-allowlist-for) | CIP-16 | Backlog | §5.6 SuspendBinding failure-path opcode (0x03 allowlist) for |
| [COW-1709](https://linear.app/cowboy-labs/issue/COW-1709/569-systeminstructionexternaldomaincallback-opcode-67-with) | CIP-16 | Backlog | §5.6/§9 SystemInstruction::ExternalDomainCallback opcode 67 with |
| [COW-1708](https://linear.app/cowboy-labs/issue/COW-1708/52part-iii-23-dnsattach-external-entitlement-registry-entry) | CIP-16 | Backlog | §5.2/§Part-III-§2.3 dns.attach_external entitlement registry entry |
| [COW-1707](https://linear.app/cowboy-labs/issue/COW-1707/92-reverify-external-detach-external-suspend-external-methods) | CIP-16 | Backlog | §9.2 reverify_external / detach_external / suspend_external methods |
| [COW-1706](https://linear.app/cowboy-labs/issue/COW-1706/9256-complete-attach-external-system-mediated-callback) | CIP-16 | Backlog | §9.2/§5.6 complete_attach_external system-mediated callback |
| [COW-1705](https://linear.app/cowboy-labs/issue/COW-1705/9252-begin-attach-external-nonce-gen) | CIP-16 | Backlog | §9.2/§5.2 begin_attach_external (nonce gen |
| [COW-1184](https://linear.app/cowboy-labs/issue/COW-1184/noderunner-evm-bridge-facilitator-bridgefacilitateevm-entitlement) | CIP-18 | Backlog | [Node/Runner] EVM bridge facilitator: bridge.facilitate.evm entitlement + BridgeEvidence + credit_inbound |
| [COW-1788](https://linear.app/cowboy-labs/issue/COW-1788/143-per-actor-tool-list-cache-keyed-by-actor) | CIP-19 | Backlog | §14.3 Per-actor tool-list cache keyed by (actor |
| [COW-1781](https://linear.app/cowboy-labs/issue/COW-1781/115-error-mapping) | CIP-19 | Backlog | §11.5 Error mapping |
| [COW-1780](https://linear.app/cowboy-labs/issue/COW-1780/114-response-mapping-httpresponseenvelopemcp-contentiserror-meta) | CIP-19 | Backlog | §11.4 Response mapping HttpResponseEnvelope→MCP content[]/isError/_meta |
| [COW-1779](https://linear.app/cowboy-labs/issue/COW-1779/113-dispatch) | CIP-19 | Backlog | §11.3 Dispatch |
| [COW-1778](https://linear.app/cowboy-labs/issue/COW-1778/112-translation-to-synthetic-httprequestenvelope-path-param) | CIP-19 | Backlog | §11.2 Translation to synthetic HttpRequestEnvelope (path param substitution |
| [COW-1777](https://linear.app/cowboy-labs/issue/COW-1777/111-toolscall-request-handling-name) | CIP-19 | Backlog | §11.1 tools/call request handling (name |
| [COW-1774](https://linear.app/cowboy-labs/issue/COW-1774/103-input-schema-derivation-from-path-params-openapi-doc) | CIP-19 | Backlog | §10.3 Input schema derivation from path params + OpenAPI doc |
| [COW-1766](https://linear.app/cowboy-labs/issue/COW-1766/8-endpoint-intercepted-before-route-resolution-gateway-pre-routing) | CIP-19 | Backlog | §8 Endpoint intercepted before route resolution (Gateway pre-routing) |
| [COW-1764](https://linear.app/cowboy-labs/issue/COW-1764/8-mcp-endpoint-at-cowboymcp-over-streamable-http-transport-postget) | CIP-19 | Backlog | §8 MCP endpoint at /_cowboy/mcp over streamable HTTP transport (POST/GET) |
| [COW-1761](https://linear.app/cowboy-labs/issue/COW-1761/7-ingressmcp-entitlement-id-with-params-server-name) | CIP-19 | Backlog | §7 `ingress.mcp` entitlement id with params (server_name |
| [COW-1798](https://linear.app/cowboy-labs/issue/COW-1798/icip20actor-actor-token-interface-actor-based-tokens-fee-on-transfer) | CIP-20 | Backlog | ICIP20Actor actor-token interface / actor-based tokens (fee-on-transfer |
| [COW-1850](https://linear.app/cowboy-labs/issue/COW-1850/v2-3-cip-13-delegation-interaction-effective-stake-vrf-weight-vs) | CIP-23 | Backlog | v2 §3 CIP-13 delegation interaction (effective_stake VRF weight vs |
| [COW-1846](https://linear.app/cowboy-labs/issue/COW-1846/35-on-chain-storage-strategy) | CIP-23 | Backlog | §3.5 On-chain storage strategy |
| [COW-1845](https://linear.app/cowboy-labs/issue/COW-1845/365-verifycae-gas-budget-200k-cycles-cert-chain-120k-etc-not) | CIP-23 | Backlog | §3.6.5 VerifyCae gas budget (200k cycles / cert-chain 120k etc.) not |
| [COW-1301](https://linear.app/cowboy-labs/issue/COW-1301/noderunner-billingattestation-cae-freshness-audit-per-event-generation) | CIP-23 | Backlog | [Node/Runner] BillingAttestation CAE freshness audit: per-event generation, no cached reuse |
| [COW-2842](https://linear.app/cowboy-labs/issue/COW-2842/cbss-real-validator-spawned-e2e-receipt-teeattestation-liveness) | CIP-24 | Backlog | [CBSS] Real-validator spawned e2e: Receipt + TeeAttestation + Liveness scenarios (COW-1054 follow-up) |
| [COW-2671](https://linear.app/cowboy-labs/issue/COW-2671/add-authenticated-evidence-for-cbss-threshold-wide-withholding) | CIP-24 | Backlog | Add authenticated evidence for CBSS threshold-wide withholding |
| [COW-1900](https://linear.app/cowboy-labs/issue/COW-1900/13-state-root-parent-hash-commitment-fields) | CIP-25 | Backlog | §1.3 state_root / parent_hash commitment fields |
| [COW-1122](https://linear.app/cowboy-labs/issue/COW-1122/runner-runner-job-type-generate-inclusion-proof-third-party-proof) | CIP-25 | Todo | [Runner] Runner job type `generate_inclusion_proof` (third-party proof service) |
| [COW-1115](https://linear.app/cowboy-labs/issue/COW-1115/node-fraud-proof-window-slashing-for-runner-committee-backend) | CIP-25 | Backlog | [Node] Fraud-proof window + slashing for runner-committee backend |
| [COW-1916](https://linear.app/cowboy-labs/issue/COW-1916/73-feature-gate-governance-parameter-bank-activation-height) | CIP-28 | Backlog | §7.3 Feature gate governance parameter bank_activation_height |
| [COW-1914](https://linear.app/cowboy-labs/issue/COW-1914/61-cowboy-banking-genesis-bank-entry-bank-id1) | CIP-28 | Backlog | §6.1 Cowboy Banking genesis bank entry (bank_id=1 |
| [COW-1913](https://linear.app/cowboy-labs/issue/COW-1913/54-locked-after-transfer-precise-semantics-owneragent-andand-locked) | CIP-28 | Backlog | §5.4 locked_after_transfer precise semantics (owner==agent && locked → |
| [COW-1912](https://linear.app/cowboy-labs/issue/COW-1912/46-gascharged-receipts-with-tx-digest-for-indexer-join-card-statement) | CIP-28 | Backlog | §4.6 GasCharged receipts with tx_digest for Indexer join / card-statement |
| [COW-1911](https://linear.app/cowboy-labs/issue/COW-1911/45-bankerr-error-family-engine-errormap-cardnotfound) | CIP-28 | Backlog | §4.5 BankErr error family + engine ErrorMap (CardNotFound |
| [COW-1909](https://linear.app/cowboy-labs/issue/COW-1909/42-async-discipline-using-block-on-local-for-send-futures-in-charge) | CIP-28 | Backlog | §4.2 Async discipline using block_on_local for !Send futures in charge_gas |
| [COW-1904](https://linear.app/cowboy-labs/issue/COW-1904/2741-fee-payer-resolution-fork-card-address-lookup) | CIP-28 | Backlog | §2.7/§4.1 fee_payer resolution fork (card-address lookup → |
| [COW-1902](https://linear.app/cowboy-labs/issue/COW-1902/13-new-tx-level-field-txfee-payer-override) | CIP-28 | Backlog | §1.3 New tx-level field tx.fee_payer_override |
| [COW-1144](https://linear.app/cowboy-labs/issue/COW-1144/decision-moola-bankactor-semantics-can-a-card-pay-gas-in-moola) | CIP-28 | Backlog | [Decision] MOOLA ↔ BankActor semantics: can a card pay gas in MOOLA? |
| [COW-1143](https://linear.app/cowboy-labs/issue/COW-1143/node-cip-12-governance-integration-for-registerbank-34) | CIP-28 | Backlog | [Node] CIP-12 governance integration for RegisterBank (§3.4) |
| [COW-1142](https://linear.app/cowboy-labs/issue/COW-1142/node-fiatmintvoucher-signature-verification-replay-protection-33-62) | CIP-28 | Backlog | [Node] FiatMintVoucher signature verification + replay protection (§3.3, §6.2) |
| [COW-1139](https://linear.app/cowboy-labs/issue/COW-1139/node-emit-nine-event-types-cardissued-carddeposited-cardwithdrawn) | CIP-28 | Backlog | [Node] Emit nine event types (CardIssued, CardDeposited, CardWithdrawn, GasCharged, Frozen, Unfrozen, PolicyUpdated, OwnershipTransferred, BankRegistered) (§3.6) |
| [COW-1138](https://linear.app/cowboy-labs/issue/COW-1138/node-whitelist-enforcement-allowed-receivers-allowed-syscall-kinds) | CIP-28 | Backlog | [Node] Whitelist enforcement: allowed_receivers + allowed_syscall_kinds |
| [COW-1137](https://linear.app/cowboy-labs/issue/COW-1137/node-spendwindow-rolling-window-enforcement-hourly-daily-monthly-m1) | CIP-28 | Backlog | [Node] SpendWindow rolling-window enforcement (hourly / daily / monthly, M1 fixed-window) |
| [COW-1136](https://linear.app/cowboy-labs/issue/COW-1136/node-charge-gas-pipeline-phase-1-reservation-phase-2-settlement-42) | CIP-28 | Backlog | [Node] charge_gas pipeline: Phase 1 reservation + Phase 2 settlement (§4.2) |
| [COW-1135](https://linear.app/cowboy-labs/issue/COW-1135/node-card-address-derivation-keccak256-domain-26) | CIP-28 | Backlog | [Node] Card address derivation: keccak256 domain (§2.6) |
| [COW-1152](https://linear.app/cowboy-labs/issue/COW-1152/nodesdk-payload-schema-validation-at-emit-subscribe-time) | CIP-29 | Backlog | [Node/SDK] Payload schema validation at emit + subscribe time |
| [COW-1150](https://linear.app/cowboy-labs/issue/COW-1150/node-manifest-entitlement-gating-for-event-subscription-prevent) | CIP-29 | Backlog | [Node] Manifest entitlement gating for event subscription (prevent untrusted spam) |
| [COW-1147](https://linear.app/cowboy-labs/issue/COW-1147/node-receipt-schema-triggered-by-emit-field-for-async-causality) | CIP-29 | Backlog | [Node] Receipt schema: triggered_by_emit field for async causality correlation |
| [COW-1285](https://linear.app/cowboy-labs/issue/COW-1285/tooling-pre-image-table-for-hashed-long-keys-debugger-explorer) | CIP-30 | Backlog | [Tooling] Pre-image table for hashed long keys (debugger / explorer enumeration) |
| [COW-1282](https://linear.app/cowboy-labs/issue/COW-1282/noderpc-expose-per-actor-proof-endpoint-get-actorstorage-root-opens) | CIP-30 | Backlog | [Node/RPC] Expose per-actor proof endpoint: `GET Actor.storage_root` + opens against subtree |
| [COW-1281](https://linear.app/cowboy-labs/issue/COW-1281/node-fork-o1-clone-childstorage-root-parentstorage-root-replaces) | CIP-30 | Backlog | [Node] fork() O(1) clone: child.storage_root = parent.storage_root (replaces enumeration stopgap) |
| [COW-1280](https://linear.app/cowboy-labs/issue/COW-1280/node-gas-formula-for-trie-updates-deterministic-bounded-cost-per-state) | CIP-30 | Backlog | [Node] Gas formula for trie updates: deterministic, bounded cost per state_set / state_delete |
