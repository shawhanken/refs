# Wiki 变更日志

append-only 时序记录。格式：`## [YYYY-MM-DD] <type> | <摘要>`，`type ∈ {ingest, query, lint, bootstrap}`。

扫描历史：`grep "^## \[" log.md | tail -20`

---

## [2026-04-15] bootstrap | 建立 wiki 骨架

基于 `refs/LLM_Wiki.md` 的 LLM Wiki 模式为 `refs/` 建立知识库体系。

**创建**:
- `wiki/AGENTS.md` — 操作规约（Ingest/Query/Lint）
- `wiki/index.md`、`wiki/log.md`、`wiki/parameters.md`、`wiki/drift.md`
- 9 个 `wiki/concepts/` 页面
- 4 个 `wiki/entities/` 页面

**初始化数据源**:
- `refs/whitepaper/` — 核心白皮书
- `refs/cips/` — CIP-1 到 CIP-22
- `refs/analysis/2026-04-15_documentation_amendments.md` — 修正案（权威裁决）
- workspace `/home/ubuntu/workspace/CLAUDE.md` — 代码路径与常量参考

**权威层级确立**: 代码 > 修正案 > CIP > 白皮书 > 其它 raw。

---

## [2026-04-16] ingest | CIP-12 治理 & CIP-13 Runner Stake 委托（Draft）

入库来源：
- `refs/cips/cip-12-governance.md` — 双院治理 + Security Council + 系统 Actor 升级（Draft, 2026-04-09）
- `refs/cips/cip-13-runner-delegation.md` — Runner Stake 委托（Draft, 2026-04-12，`Requires: CIP-12`）

**新建 wiki 页**:
- `wiki/concepts/governance.md`（status: draft）
- `wiki/concepts/runner-delegation.md`（status: draft）

**更新 wiki 页**:
- `wiki/entities/system-actors.md` — `0x09` 扩至完整治理职能；`0x01` 增注委托扩展；`0x03` 增注分账/级联
- `wiki/entities/runner-lifecycle.md` — 新增 Phase 1b（接受委托）；Phase 6 / Phase 7 加入委托分账与 slash 级联
- `wiki/concepts/settlement-slashing.md` — 新增委托扩展小节；相关页链接到 runner-delegation / governance
- `wiki/parameters.md` — 新增 CIP-12 治理参数段、CIP-13 委托参数段，均标明 Draft 未实装
- `wiki/drift.md` — 追加高严 **I-1**（CIP-13 opcode 40–44 与现有 SystemInstruction 40–43 冲突）、低严 **L-4**（CIP-12 `SystemActorUpgrade` 负载与现 opcode 43 `UpgradeActor` 关系未明）
- `wiki/index.md` — 列入 2 个新概念页

**权威层级标注**：两份 CIP 均为 Draft，协议尚未实装；wiki 新页 `status: draft`，参数段显式标"尚未实装"；代码侧 `0x09` 当前仅承载 `SettlementConfig`。

---

## [2026-04-15] lint | 全文档-代码漂移审计（第 2 轮）

范围：`refs/runner/`、`refs/pvm/`、`refs/chain/`、`refs/node/` 等 raw 文档对照 workspace `node/` 与 `runner/` 代码。

**发现新漂移 10 项**（超出修正案初版 13 项）：
- **H-1**: Runner 地址格式（文档 Ed25519 32B → 代码 ETH 20B）
- **H-2**: VerificationMode `HappyCase` 不存在
- **H-3**: MCP/Job 示例缺 mode 必需字段
- **M-1**: VerificationMode 字段级 schema 未记录
- **M-4**: CallbackInfo.actor 地址格式未声明
- **L-1/L-2/L-3**: Timer 预算、端口、Checkpoint 警告源链接

**修复动作**:
- 追加修正案 §六·补³（Runner 文档 API 漂移）含完整 VerificationMode JSON schema
- 修正案覆盖清单表从 13 项增至 21 项
- 就地修复 `refs/runner/2026-02-05_DOCUMENTATION.md`（4 处）、`SUBMIT_JOB_GUIDE.md`（2 处）、`QUICK_SUBMIT.md`（1 处）、`QUICK_START_MCP.md`（2 处）
- 更新 `wiki/drift.md` 漂移表

**一致性良好的类别**:
- Runner CLI 命令格式
- CIP-9 Runner Storage 设计
- Job Type（LLM/HTTP/MCP/Custom）枚举

---

## [2026-04-17] ingest | `refs/plans/` 工程实施计划目录（22 份）

新增 raw 数据源目录 `refs/plans/`，含 22 份工程计划 / 评估 / 路径图文件（cute-name slug 命名，如 `ancient-enchanting-marble.md`）。内容主题覆盖经济/basefee、TPS/出块、receipt pruning、validator 10100 停滞、PVM 错误、钱包 UI + Passkey、社区治理、bench 观测、文档/测试/Issue 批量治理。

**性质判定**：计划文件属"其它 raw"，**非规范性**；权威顺序仍是 代码 > 修正案 > CIP > 白皮书 > 其它。

**新建 wiki 页**:
- `wiki/entities/plans-inventory.md`（status: authoritative）—— slug → 标题/主题/摘要映射；按 8 个主题分组：经济(6) / 性能(6) / 可靠性(1) / Bench(2) / PVM(1) / 钱包(2) / 治理(1) / 文档-测试-待办(3)

**更新 wiki 页**:
- `wiki/AGENTS.md` —— "三层架构 §1 Raw sources" 列入 `refs/plans/`；权威顺序段补注"引用计划须标明状态"
- `wiki/index.md` —— `entities/` 段加入 `plans-inventory.md`；"Raw Sources 快速链接"段加入 `refs/plans/`；顶部 `最后更新` → 2026-04-17

**未触发**:
- 未新增 drift 条目（计划本身不等于漂移；计划已记录的代码-文档不一致若未在 `drift.md`，需人类后续触发定向审计）
- 未修改 `parameters.md`（计划中出现的数值均为提案态，未进入权威参数表）
- 未修改现有 concept 页（计划中引用的概念均已有页；不重复综合）

---

## [2026-04-17] maintenance | `refs/plans/` 文件重命名（cute-slug → 语义 kebab-case）

22 个计划文件从 cute-name slug（如 `ancient-enchanting-marble.md`、`moonlit-gathering-locket.md`）统一改为语义化 kebab-case。

**命名前缀**（按主题域）: `economics-*` / `basefee-*` / `tps-*` / `block-time-*` / `bench-*` / `wallet-*` / `pvm-*` / `runner-*` / `node-*` / `validator-*` / `governance-*` / `receipt-*` / `transfer-*` / `github-*`。

**对照表**（便于历史追溯）:

| 旧 slug | 新命名 |
|---|---|
| ancient-enchanting-marble | runner-test-coverage-plan |
| distributed-floating-simon | node-readme-update-plan |
| encapsulated-leaping-cloud | receipt-pruning-periodic |
| enchanted-sparking-dolphin | wallet-ui-dark-theme |
| flickering-wishing-riddle | tps-improvement-roadmap |
| glimmering-hugging-rossum | economics-alignment-plan |
| glimmering-swinging-lark | validator-10100-stall-fix |
| graceful-hugging-aho | pvm-structured-errors |
| graceful-tickling-stonebraker | wallet-passkey-protection |
| hazy-inventing-locket | bench-basefee-tracking |
| inherited-jingling-emerson | economics-remaining-gaps |
| keen-cuddling-twilight | pvm-bytecode-gas-feasibility |
| linear-fluttering-moonbeam | bench-flood-errors-diagnostics |
| misty-sleeping-music | basefee-constants-lower |
| moonlit-gathering-locket | governance-7phase-roadmap |
| purring-splashing-globe | economics-completion-assessment |
| rustling-mapping-sundae | basefee-eip1559-systematic-fix |
| serene-nibbling-toucan | block-time-500ms-to-1000ms |
| sharded-toasting-aurora | tps-avg-throughput-improvement |
| synchronous-orbiting-backus | block-time-change-scope |
| ticklish-dancing-lecun | transfer-lifecycle-profiling |
| twinkling-strolling-token | github-issues-batch-plan |

**连带更新**:
- `wiki/entities/plans-inventory.md` —— 全部链接与命名约定段更新
- `plans/` 目录仍未进 git（首次加入时将直接以新名入库，旧名不留痕）

---

## [2026-04-17] ingest | `refs/plans/runner-economics-and-delegation-cip13.md`（CIP-13 设计指南）

新增单份设计指南，内容上是 CIP-13 的**框架性解读 + 超越规范文本的经济学框架**。明确自标"设计文档，非完整实现方案"。

**超越 CIP-13 的新内容**：
- "Compute as a Segmented Yield Primitive" —— 委托不是同质化节点分红，而是下注 entitlement class 划分的计算细分市场需求曲线
- `JobSettled` + `DelegatorPayout` 结构化事件作为上层 compute index / forward / ETF 的 indexer 输入底座
- 两种 tip 辨析（`Transaction.max_priority_fee_*` → proposer vs `JobSpec.tip` → runners）
- 双重通缩：basefee burn + settlement 10% burn
- 架构总览（全链路 ASCII 图）
- 与 Optimistic Rollup / zkVM 的范式对比

**更新 wiki 页**:
- `wiki/concepts/runner-delegation.md` —— 新增 §"核心框架：Compute as a Segmented Yield Primitive" 章节；frontmatter 追加 plan 作为 source；Sources 段补充；`last_updated → 2026-04-17`
- `wiki/entities/plans-inventory.md` —— 经济分组从 6 项增至 7 项，列入此 plan；Sources 段更新为 23 份；命名约定段追加 ⚠️ 例外（括号不符 kebab-case，建议改为 `runner-economics-and-delegation-cip13.md`）

**未触发**:
- 未改 `drift.md`（此 plan 本身不带新漂移；既有 I-1 / L-4 仍为准）
- 未改 `parameters.md`（plan 列的默认值均与 CIP-13 §4 一致，已在参数表中）
- 未改 `settlement-slashing.md` / `runner-lifecycle.md`（plan 的分账与 slash 叙述是重述 CIP-13，已在 runner-delegation 概念页承接）

**命名修正**：原始上传文件名 `runner-economics-and-delegation(CIP13).md` 含括号，已同日改为 `runner-economics-and-delegation-cip13.md` 以对齐 kebab-case 约定；`plans-inventory.md` 命名约定段补充 `-cipNN` 后缀惯例。

---

## [2026-04-20] ingest | CIP-14 / CIP-15 / CIP-16（HTTP Ingress 三件套）+ CIP-23（TEE Execution, Draft）

入库来源（6 份新文档）：

- `refs/cips/cip-14-dns-addressable-actors.md` — DNS-Addressable Actors（Draft, 2026-03-07, Requires: CIP-2/CIP-3）
- `refs/cips/cip-15-public-asset-hosting.md` — Public Asset Hosting（Draft, 2026-03-07, Requires: CIP-9/CIP-14）
- `refs/cips/cip-16-custom-domains.md` — Custom Domains & First-Party TLDs（Draft, 2026-03-08, Requires: CIP-14/CIP-2/CIP-3/CIP-5）
- `refs/cips/cip-23-tee-execution.md` — TEE Execution & Composite Attestation（Draft, 2026-04-20, Requires: CIP-2/CIP-3/CIP-10）
- `refs/cips/cip-23-tee-execution-zh.md` — CIP-23 中文镜像（同日）
- `refs/plans/cowboy-tee-execution-design.md` — CIP-23 实施设计（Draft, 2026-04-20；§12 代码改造清单 + §13 4-phase 路线图）

**新建 wiki 页（6 个）**:

- `wiki/concepts/dns-addressable-actors.md`（status: draft）—— CIP-14 综合：`ingress.http` / Route Registry / Gateway 角色 / Query vs Command 双路径 / 系统中介 dispatch
- `wiki/concepts/public-asset-hosting.md`（status: draft）—— CIP-15 综合：路由清单、`ingress.http` 扩展 params、Gateway↔Relay fetch 协议、CORS 默认
- `wiki/concepts/custom-domains.md`（status: draft）—— CIP-16 综合：三类命名空间、`DomainBinding` 超集、TXT 挑战 + ACME 委派、周期重验证状态机
- `wiki/concepts/tee-attestation.md`（status: draft）—— CIP-23 综合：CAE v1 结构、7 步验证流水线、attestation-first 注册、Deterministic 密码学强制、SGX 降级为 legacy
- `wiki/entities/gateway.md`（status: draft）—— Gateway 节点角色（第 4 个协议 role）：职责 / 生命周期 / `dispatch()` 系统中介 / 激励 / 缓存架构
- `wiki/entities/route-registry.md`（status: draft）—— 系统 Actor `0x0011`：Binding 结构演进、三命名空间方法表、长度递减年费 + Dutch 拍卖释放

**更新 wiki 页（5 个）**:

- `wiki/entities/system-actors.md` —— 表格新增 `0x0011 ROUTE_REGISTRY` / `0x0012 GATEWAY_REGISTRY`；`0x05 TEE_VERIFIER` 补规范描述（CIP-23 Draft：CAE 验证流水线、opcodes 50–53）；`0x09 GOVERNANCE` 增注 TEE 根证书治理
- `wiki/concepts/runner-verification.md` —— Deterministic 模式行补 CIP-23 强制说明；新增 "CIP-23 扩展" 章节概述 Dispatcher 过滤改写、Result Verifier 逐条 CAE 校验、SGX legacy
- `wiki/entities/runner-lifecycle.md` —— 阶段 1a 新增（TEE Runner attestation-first 注册）；阶段 4 / 阶段 7 补 CIP-23 CAE 验证与 9 类错误码
- `wiki/parameters.md` —— 追加 4 个新参数段：CIP-14 Route Registry / CIP-15 Public Asset Hosting / CIP-16 Custom Domains / CIP-23 TEE Execution；全部标 "Draft, 尚未实装"
- `wiki/drift.md` —— 活跃漂移从 21 项升至 25 项，追加：
  - **N-1** 高严：CIP-15 要求 CIP-9 新增 `GET_MANIFEST` Relay Node RPC
  - **N-2** 高严：CIP-15 §8.5 规范化 manifest serialization / `manifest_root` Merkle，CIP-9 无 normative 描述
  - **TEE-1** 高严：CIP-23 amend CIP-2 §5.4/§9 但 CIP-2 源文未并入
  - **L-5** 低严：块时间假设不一致（CIP-14 的 1s vs CIP-23 的 500ms）
  - **L-6** 低严：CIP-14 `RouteRegistration` vs CIP-16 `DomainBinding` schema 差异

**一致性审查要点（未成为独立 drift 条目，但已在新 wiki 页标注）**:

- CIP-14 §8.3 引用 "Milestone 2 §5.2 `queryActor`" —— 非 CIP 命名规范，Gateway 必须跟踪其签名演进
- CIP-14 §6.1 引用 "Entitlements Specification §10" 禁止未注册 entitlement —— `ingress.http` adoption 需要对应 spec 同步修订（文档中 inline 提醒）
- CIP-23 §3.2 明确 supersede `CLAUDE.md` / `node/types/README.md` 中 `0x91-0x95` 老地址列表 —— 已与 drift B 合并叙述，不重复记录
- CIP-23 新 opcodes 50–53 与 CIP-13 Draft 40–44 无冲突（CIP-13 冲突是既有 I-1 项）

**权威层级标注**: 全部 6 份文档为 Draft，协议未实装；wiki 新页 `status: draft`；参数段显式标"尚未实装"；代码侧 `0x05` 仍是占位桩，`0x0011` / `0x0012` 尚无常量。

---

## [2026-04-21] alignment | v2 系列全面对齐（round 6）

跨多轮迭代完成 v1 → v2 alignment：CIP-1 / CIP-2 / CIP-9 / CIP-10 / CIP-13 / CIP-14 / CIP-15 / CIP-16 / CIP-23 各发布 v2 alignment 文件 + WP v2；多轮审计揭示并解决以下根本冲突。

**核心改动概览**：

1. **System actor 地址段重排**（CIP-14 v2 / CIP-10 v2）：v1 草案的 `0x0011` / `0x0012` → v2 收回到紧跟代码序列的 `0x0C` (ROUTE_REGISTRY) / `0x0D` (GATEWAY_REGISTRY) / `0x0E` (RECEIPT_REGISTRY) / `0x0F` (CONTAINER_REGISTRY)。WP §9 line 704 错配 `0x0A = Container Image Registry` 由 WP-v2 Delta 6 修正（0x0A 实际归 STORAGE_MANAGER per CIP-9）。

2. **SystemInstruction opcode 全面重排**：审计发现代码 `node/types/src/execution.rs:482-541` 已分配 0–51（含 CIP-5 revision 引入的 SYS_CANCEL_TIMER=48 / SYS_UPDATE_TIMER_CONFIG=49 / SYS_EXTEND_TIMER=50 / SYS_DEPLOY_CODE=51）。v1 / 早期 v2 草案的 opcode 分配（CIP-13 40-44 → 44-48；CIP-23 50-53；CIP-1 v2 草案 70-72）全部冲突。**CIP-13 v2 §1 落地为全 v2 系列的 canonical master allocation table**，重排为：CIP-13 = 52-56；CIP-23 = 57-60；CIP-10 = 61-64；CIP-14 = 65 (`IngressDispatch`) / 66 (`CompleteReceipt`)；CIP-16 = 67 (`ExternalDomainCallback`)。CIP-1 v2 §6 撤销 70-72 推荐（这些 timer ops 已在代码 48-50）。

3. **CIP-5 revision 集成**（2026-04-20 重大改动）：timer 不再免费 —— per-fire `fee_payer` 预扣 + 退还（§6.3）；三路退出生命周期（natural fire / TTL expiry / insufficient-funds self-destruct，§5.4）；`LANE_TIMER_CYCLES` 与 `TIMER_GC_CYCLES` 双预算分离（§6.5）；`TimerConfig` 治理可调（§6.4）；Tx-then-Timer 块内顺序 native 化（§5.1，结束 v1 amendment caveat）。CIP-9 v2 §12 / CIP-16 v2 §5.10 各自指定 `fee_payer` 与余额不足兜底事件订阅。

4. **Selector reservation 提案撤销**：CIP-14 v2 §6.2 早期草案提议 PVM 路由层把 `"http.request"` 设为系统保留 selector，**撤销**因阻断 router actor 转发模式；改回 SDK-default `ctx.sender == GATEWAY_REGISTRY=0x0D` 检查（`ctx.sender` 由协议消息路由器从 tx 签名者填入，handler 内部检查即足够）。

5. **DNS 验证模式修正**（CIP-2 v2 + CIP-16 v2）：CIP-16 v1 §9.6 错用 `VerificationMode::Deterministic`（要求 byte-identical + TEE，不适合非确定性 DNS）；v2 改用 `MajorityVote` + 两个新 `VerifierCheck` 变体（`DnsTxtRecordMatch` / `DnsCnameMatch` per CIP-2 v2 §2 AMEND 2-A/B），N-of-M runner 各查 ≥3 独立 DNS resolver 多数决。CIP-16 v2 §5.6 `ExternalDomainCallback` (opcode 67) 由 `RESULT_VERIFIER (0x03)` 系统中介强制，非 SDK 约定。

6. **CIP-9 amendment 修正**（CIP-9 v2）：v2 早期草稿误把 `StorageCommitment` / `commit_manifest` / `volume_id = keccak256(...)` 列为 amendment（实为 CIP-9 §11.1/§12.2 已有），CIP-9 v2 §9 errata 修正。真实需要的 amendment 仅 4 项：`GET_MANIFEST` Relay RPC（AMEND 9-G）+ `ManifestCommitted` 链上事件（AMEND 9-H）+ canonical Merkle pin to CBFS RFC-6962-style（§3）+ status → HTTP 行为映射表（§5）。CIP-15 v2 据此重写。

7. **DomainBinding 迁移规则**（CIP-16 v2 §3.1）：v1 `RouteRegistration` 升级为 `DomainBinding` 时按显式默认值（`namespace_kind=COWBOY_NETWORK, status=ACTIVE` 等）一次性 schema upgrade，结束 L-6 漂移。

8. **SettlementConfig target_pool 6-enum 表**（CIP-14 v2 Part III §6 canonical）：CIP-3 既有的 `UpdateSettlementConfig` (opcode 40) 加 `target_pool` discriminant；MAIN / REGISTRY / GATEWAY_POOL / CONTAINER / REGISTRY_TLD_COW / REGISTRY_TLD_COWBOY 六个变体集中在该表，handler MUST exhaustive switch。

9. **CIP-23 v2 三层 chain 与 BillingAttestation 数据源**：`sec.tee_required` entitlement / `VerificationConfig.tee_required` 字段 / `MeasurementBinding` 三层独立校验，分布在 deploy / submit / register/renew 三个生命周期时刻。`tee_signature: Option<CompositeAttestation>` **每次 billing event 临时生成**（v2 §5.1），不缓存 measurement_binding 时的 quote。`nitro` 待加入 `CANONICAL_TEE_TYPES`（precondition）。

10. **CIP-13 v2 ↔ CIP-23 v2 正交**：TEE 资格是 categorical capability check（`MeasurementBinding.status`），与 stake 来源无关。委托质押增加 VRF 权重但不授予 / 取消 TEE 资格。

**入库 / 修订的 v2 文档（10 份）**：
- `refs/cips/cip-1-actor-scheduler-v2.md`
- `refs/cips/cip-2-offchain-compute-v2.md`
- `refs/cips/cip-9-runner-storage-v2.md`
- `refs/cips/cip-10-runner-containers-v2.md`
- `refs/cips/cip-13-runner-delegation-v2.md`
- `refs/cips/cip-14-dns-addressable-actors-v2.md`
- `refs/cips/cip-15-public-asset-hosting-v2.md`
- `refs/cips/cip-16-custom-domains-v2.md`
- `refs/cips/cip-23-tee-execution-v2.md`
- `refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md`（含 6 个 deltas + alignment brief）

**更新 wiki 页（19 份）**：
- entities: system-actors / route-registry / gateway / runner-lifecycle / pvm
- concepts: dns-addressable-actors / public-asset-hosting / custom-domains / runner-delegation / tee-attestation / timer-mechanism / runner-verification / governance / settlement-slashing / basefee / vrf-runner-selection
- 综合: parameters / drift / index / log（本条目）

**drift.md 重大变化**：
- 已收口（5 项）：I-1（CIP-13 opcode 冲突）/ N-1（GET_MANIFEST）/ N-2（manifest serialization）/ TEE-1（CIP-23 amend CIP-2 配套补 CIP-2 v2）/ L-6（RouteRegistration → DomainBinding 迁移规则）
- 仍活跃漂移移到独立段
- 新增 v2 precondition gap 段（10 条 V-* 条目）：跟踪 v2 spec 已就位但代码尚未跟进的项；包含 system actor 0x0C-0x0F 缺常量、registry 缺 3 entries、opcodes 52-67 缺、Receipt Registry prune loop 未实装、WP §9 0x0A 错配、`nitro` 待加入 CANONICAL_TEE_TYPES、`target_pool` enum 待扩展等

**parameters.md 重大变化**：
- Timer 段全面重写（CIP-5 revised + 双预算 + fee_payer 模型）
- 新增 SystemInstruction Opcode 主分配表段（canonical CIP-13 v2 §1 全 v2 系列权威）
- 新增 SettlementConfig target_pool 枚举段（canonical CIP-14 v2 Part III §6）
- 新增 Container Runtime (CIP-10 v2) 段
- CIP-13 / 14 / 15 / 16 / 23 各段重写（地址 / opcode / entitlement / 费分配等）

**权威层级标注**: v2 系列文档全部为 Draft；spec 已自洽对齐；代码尚未实装的项明确列在 `drift.md` v2 precondition gap 段。激活前需按 V-1 → V-10 顺序补齐代码侧。

---

## [2026-05-11] ingest | CIP-18 Payments + CIP-19 Gateway MCP Ingress + CIP-25 Cross-Chain Architecture + CIP-15 Gateway Implementation companion

入库来源（4 份新文档，全部 2026-05-11 commit）：

- `refs/cips/cip-18-payments.md` — Payments (Draft 2026-03-08 / Updated 2026-04-28)：HTTP-native 付款；MPP（primary, IETF `draft-ryan-httpauth-payment`）+ x402（Coinbase 兼容）双 wire 并行 normalize 为 PaymentIntent；PaymentGate 系统 actor `0x0013`（地址段对齐 gap, V-14）；4 个付款模型（per-request / actor-funded / prepaid pass / epoch subscription）；入站 EVM bridge facilitator（runner 新 entitlement `bridge.facilitate.evm`）；24 sections
- `refs/cips/cip-19-gateway-mcp-ingress.md` — Gateway MCP Ingress (Draft 2026-04-28)：让每个 CIP-14 actor 自动成为 MCP server，Gateway 在 `/_cowboy/mcp` (MCP 2025-11-25 streamable HTTP) terminate；`tools/list` 从 CIP-15 路由表派生；`tools/call` 翻译为 CIP-14 既有 dispatch；付款经 JSON-RPC `_meta` + 错误码 -32402；新 entitlement `ingress.mcp`
- `refs/cips/cip-25-cross-chain-architecture.md` — Cross-Chain Architecture (Draft 2026-04-23)：三层正交架构 L1（state anchoring，pluggable 4 后端：runner committee / ZK / optimistic / native LC）/ L2（Mailbox，exactly-once + 单调）/ L3（bridge / lending / oracle / generic call）；§A worked examples + §B 安全模型（15 攻击 taxonomy + composition theorem + defense-in-depth）；与 Tony 团队既有 ETH withdrawal bridge 对称
- `refs/cips/cip-15-gateway-implementation.md` — companion implementation handbook (Living document)：CIP-15 v2 Gateway 端 6-phase 实施 build order（P1 routes resolve + method dispatch / P2 静态 volume / P3 runtime mutability / P4 `pays=caller` 经 CIP-18 / P5 CORS+conditional / P6 优化）

**新建 wiki 页（3 个）**：

- `wiki/concepts/payments.md`（status: draft）— PaymentGate / MPP-vs-x402 双 wire / 4 模型 / 入站 bridge / 收入分配 / `payment.gate` entitlement / 与 CIP-14/15/19/Session 的关系 / 安全要点
- `wiki/concepts/mcp-ingress.md`（status: draft）— `ingress.mcp` entitlement / `/_cowboy/mcp` 端点契约 / `tools/list` 派生算法 / `tools/call` dispatch 翻译 / 付款集成 / 保留 `_cowboy_*` tool name 前缀 / 安全要点
- `wiki/concepts/cross-chain.md`（status: draft）— 三层架构 / 4 信任后端 / Mailbox 不变量与 deliver 模板 / 4 类 L3 应用 payload skeleton / 性能信封 / 安全模型与 defense-in-depth

**更新 wiki 页（6 个）**：

- `wiki/entities/system-actors.md` — 表格新增 `0x13 PAYMENT_GATE`（CIP-18 Draft）；§"PaymentGate" 详细职责段；冲突段 §6 标注 CIP-18 §22 沿用 v1 numbering vs v2 单字节序列对齐；Sources 段补 CIP-18 §8 / §22
- `wiki/parameters.md` — 新增 3 大段：Payments（含 13 个常量 + 2 entitlement + 4 子配置结构 + fallback 链）/ MCP Ingress（含 8 常量 + entitlement params + tool name 规则）/ Cross-Chain（L1 / L2 / L3 各分段 + 性能信封）；变更记录加 2026-05-11
- `wiki/drift.md` — 新增 "CIP-18 / CIP-19 入库引入的 precondition gap" 段：V-14（PaymentGate `0x13` 段对齐 gap）/ V-15（entitlement registry +3 新 entries）/ V-16（CIP-15 `pays=caller` 依赖 CIP-18）/ V-17（CIP-19 `tools/list` 依赖 CIP-15 v2 + GET_STATE）；监控维度加 entitlement registry 行
- `wiki/index.md` — concepts 段加 payments / mcp-ingress / cross-chain 三页；阅读路径加跨链分支；HTTP ingress 分支扩到 payments → mcp-ingress；最后更新顶栏
- `wiki/concepts/public-asset-hosting.md` — 头部 v2 变更段引用 gateway-implementation companion；与 CIP-18 `pays=caller` 字段交互 callout
- `wiki/concepts/mpp-session.md` — "与 CIP-2 / CIP-7 关系" 段后追加 vs CIP-18 段（charge intent 由 CIP-18 落地；Session 仍是后续 CIP 工作）

**未触发**：

- 未改 `wiki/entities/gateway.md`（Gateway 既有 entity 已含 ingress 角色叙述；CIP-18 边缘 enforce + CIP-19 MCP terminate 加在 concepts 层，gateway entity 暂不增章节，待 V-14 选址落定后回写）
- 未改 `wiki/entities/runner-lifecycle.md`（CIP-25 runner committee attestation 是 CIP-2 既有职责的同构应用；待 V-14/V-15 落地或独立 L1 后端 CIP 草案出 → 再加 §"跨链 attestation 角色"）
- 未改 `wiki/concepts/runner-verification.md`（CIP-25 L1 committee 用既有 VerificationMode 模型，无新 variant 需求）

**冲突摘要（drift V-14 / V-15 / V-16 / V-17）**：

- **V-14**：CIP-18 §22 PaymentGate `0x0013` 续 CIP-14 v1 (`0x0011`/`0x0012`)；v2 主表 CIP-10 v2 已取 `0x0F`，PaymentGate 应落 `0x10`
- **V-15**：entitlement registry 累计需 +6 entries（CIP-14/15/16 v2 各 1 + CIP-18/19 共 3）
- **V-16**：CIP-15 v2 schema 有 `pays` 字段但 `caller` 路径 enforce 需 CIP-18 实装
- **V-17**：CIP-19 `tools/list` 需 CIP-15 §8.12 `GET_STATE` RPC 已就位

**权威层级标注**：CIP-18 / CIP-19 / CIP-25 全部 Draft，未实装；wiki 新页 `status: draft`；参数段显式标"尚未实装"；激活路径列在 drift V-14 → V-17。

---

## [2026-05-07] ingest | MPP Session 研究 + 实施计划

入库来源：

- `refs/runner/2026-04-28_MPP_Session_Research.md` — 研究草稿，把 Stripe + Tempo Labs 提交 IETF 的 Machine Payment Protocol（MPP）的 session 模式嫁接到 Cowboy；提议新增 `Session Actor 0x0C` 承载链上托管 / 累积结算 / 退款 / 仲裁入口；voucher 用 EIP-712 签累积金额；执行器复用 `runner-llm` / `runner-http` / `runner-mcp`；分润复用 `SettlementConfig` 89/10/1。研究阶段重要文档微调（行号刷新到 2026-05-06：`verifier.rs` settlement 段 332-465 → 351-465；`VerificationMode` 五变体 → 六变体含 `SemanticSimilarity`；`registry.rs` 起点行号补全；`dispatcher.rs:830-910` → `830-903`）。
- `refs/plans/2026-05-06_mpp_session_implementation.md`（新文件） — 把研究文档 §5–§6 转成可执行任务表：6 个新 opcode（52-57）、新 `node/types/src/session.rs`、新 `node/execution/src/runner/session.rs`、新 `runner/crates/runner-node/src/session/`、CLI `cowboy session` 子命令、`examples/llm_session/`；10 个 SPEC-SES-* 单元测试；6-8 个 runner integration 测试；端到端验收 3 笔链上 tx + 89/10/1 比例验证；PoC 2-3 周；§7 后续工作（CIP 草案、CIP-2 dispute 实装、CIP-20 token 资产、TEE 增强、跨链 bridge）。

**新建 wiki 页（1 个）**：

- `wiki/concepts/mpp-session.md`（status: draft） — Cowboy MPP Session 综合：与 MPP 协议对接（charge vs session）、Session 生命周期 4 状态机、链上 6 handler 表、链下 voucher / Runner 端、Settlement 复用 89/10/1、与 CIP-2 / CIP-7 关系、安全 / DoS 缓解、PoC 范围与待澄清

**更新 wiki 页（5 个）**：

- `wiki/entities/system-actors.md` — 新增 "Session Actor（提案 0x0C）" 小节；冲突段 §5 标注与 ROUTE_REGISTRY 撞地址；Sources 段补研究/计划路径
- `wiki/parameters.md` — SystemInstruction Opcode 主分配表后追加冲突告警；变更记录加 2026-05-07
- `wiki/drift.md` — 新增 "MPP Session 研究 / 计划与 v2 主表冲突" 段（V-11 / V-12 / V-13）；source 列表补两份新文档
- `wiki/entities/plans-inventory.md` — 新增 "CIP / 跨子系统集成（3）" 分组（含 cowboy-tee-execution-design / 2026-04-22 gap-assessment / 2026-05-06 mpp_session）；"文档/测试/待办" 增 1 项 (`2026-04-30_rust-fmt-cleanup-node-cbfs`)；命名约定补"日期前缀允许"惯例；总数 23 → 27
- `wiki/index.md` — concepts 段加入 mpp-session；plans 数量 22 → 27；"最后更新" 顶栏

**冲突摘要（drift V-11 / V-12 / V-13）**：

研究 / 计划是研究阶段提案，**未走 v2 alignment round 6**：
- `0x0C` SESSION_ACTOR 撞 CIP-14 v2 ROUTE_REGISTRY
- opcodes 52-57 撞 CIP-13 v2 (52-56) + CIP-23 v2 (57)
- EIP-712 `domain.chainId` 来源未明（计划 §10 待澄清）

**未触发**：
- 未改 `parameters.md` 的 v2 opcode 主表（v2 系列权威）
- 未改 `entities/runner-lifecycle.md`（MPP session 是叠加 fast path，CIP-2 lifecycle 不变；如果二期 dispute 落地，再加 §"MPP Session dispute 路径"）
- 未改 `concepts/runner-verification.md`（session 默认乐观 `ecrecover`，仲裁路径完全复用 CIP-2 commit-reveal，无新增 VerificationMode）

**权威层级标注**: 研究 / 计划全部为 Draft / Research / PoC；激活路径需经 CIP 草案（计划 §9 列出 `cip-2x-mpp-session.md`） + 治理 + 主分配表对齐才能合并到 v2 主表。

---

## [2026-05-11] alignment | r2 跨 CIP 修订收口已知冲突（doc-only，代码不动）

代码 ground-truth 审计发现 `node/runner/src/system_actors.rs:35` 已 commit `SESSION_ACTOR = 0x0C`（含 `node/types/src/session.rs` / `session_eip712.rs` / `node/execution/src/runner/session.rs` / `runner/crates/runner-common/src/voucher.rs` 全栈）；`cbfs/manifest/src/merkle.rs:32-66` 是 power-of-2 padded BLAKE3，不是 RFC-6962；`node/types/src/registry.rs:35-219` 实际 15 entries（不是 14）；`node/types/src/execution.rs` SystemInstruction 是 Rust enum 没有 numeric opcodes 抽象。

按"代码先到先得 + 不动代码"原则，对以下 CIP / WP 文档发 r2 修订：

**地址段后移 +1**（为 `SESSION_ACTOR = 0x0C` 让位）：
- **CIP-14 v2 → v2.r2** — ROUTE 0x0C → 0x0D / GATEWAY 0x0D → 0x0E / RECEIPT 0x0E → 0x0F；Part II + Part III §1 表 + 散落引用全部更新；标题加版本号
- **CIP-10 v2 → v2.r2** — CONTAINER 0x0F → 0x10；Part II §1 + 表更新
- **CIP-15 v2 → v2.r2** — Part III §1 表更新；地址段联动 + Merkle 描述（见下）
- **CIP-16 v2 → v2.r2** — Part II 散落 ROUTE 0x0C → 0x0D + GATEWAY 0x0D → 0x0E
- **CIP-18 → r2** — PAYMENT_GATE 0x0013 → 0x11；§22 sequential-allocation rationale 重写（剔除错引 CIP-7 0x0006 + CIP-14 v1 0x0011/0x0012）；§1 / §8 / §17 / §19 全部更新
- **WP-v2 → v2.r2** — §13 / Delta 6 系统 actor 表更新；散落 GATEWAY_REGISTRY=0x0D → 0x0E、RECEIPT_REGISTRY=0x0E → 0x0F

**CBFS Merkle 描述修正**：
- **CIP-9 v2 → v2.r2** — Part II §3 / 顶部 changelog 改"power-of-2 padded BLAKE3 binary Merkle"，附 `cbfs/manifest/src/merkle.rs:32-66` 详细 algorithm
- **CIP-15 v2 → v2.r2** — Part II 同步改 + 顶部 changelog

**互引标签修正**：
- **CIP-18 → r2** — Companions: CIP-19 → **Requires: CIP-19**
- **CIP-19 → r2** — Companions: CIP-18 → **Requires: CIP-18**

**Open question 引用错位**：
- **CIP-15 gateway-implementation → r2** — §2.2 从"CIP-15 §8.12"（不存在）改为"未规范、未实装；建议起 sibling CIP / 扩 CIP-14 v2.r2 Part II §5"；§9 open-questions 同步；§13 / Part I 标题引用从 "CIP-18: Payment Gating" → "CIP-18: Payments"

**wiki 同步**：
- `wiki/entities/system-actors.md` — 表格全面重写（含 `0x0C = SESSION_ACTOR` 行，`0x0D–0x11` v2.r2 提案行）；冲突段重新框定
- `wiki/parameters.md` — DNS-Addressable / Container / Payments / Cross-Chain / MCP Ingress 各段地址更新；变更记录加 r2
- `wiki/drift.md` — V-1 / V-11 / V-14 标 ✅ resolved；V-2 / V-15 修正 baseline 14→15 entries；顶部加 r2 sync 旗帜；MPP Session 段重新框定（"代码先到先得"）
- `wiki/concepts/dns-addressable-actors.md` — 全文 0x0C/D/E → 0x0D/E/F
- `wiki/concepts/payments.md` — 顶部"地址段 gap"段落改为"已解决"叙述；PAYMENT_GATE 0x0013 → 0x11
- `wiki/concepts/public-asset-hosting.md` — Merkle 描述改正
- `wiki/concepts/mcp-ingress.md` + `wiki/entities/gateway.md` + `wiki/entities/route-registry.md` — 地址段联动

**未触动（按用户指令）**：
- 代码（`node/` / `runner/` / `cbfs/`）— 任何修改
- CIP-1 v2 / CIP-2 v2 / CIP-13 v2 / CIP-23 v2 — 未引用 0x0C-0x11 段
- CIP-25 / CIP-15-gateway-implementation 跨链 / runner-committee 设计冲突（CIP-25 §1.4 vs WP-v2 §16.2 第三方桥路线）— 这是 spec 之间的设计方向选择，不是文档-代码 ground-truth 冲突；保留待治理决策

**仍待解决（未在本轮 r2 修订内）**：
- entitlement registry +6 entries 实装（V-2 + V-15）
- `read_handler` RPC（CIP-14 v2.r2 §5）+ `GET_STATE` RPC（CIP-15 gateway-impl r2 §2.2 标 open）
- 系统 actor const 5 个（V-1 仍待）
- timer fee_payer field（V-8 仍待）
- VerificationMode `DnsTxtRecordMatch` / `DnsCnameMatch`（CIP-2 v2 §2 仍待）
- CIP-25 跨链 L1 anchor / L2 mailbox 整套未实装（设计 spec）
- WP / WP-v2 加 Payments + MCP Ingress Delta（之前识别为白皮书空白）

---

## [2026-05-11] ingest+amend | 第二轮收口：CIP-8 (MPP Session retroactive) / CIP-17 (GET_STATE) / WP-v2 r2 Delta 7-9 / CIP-25 r1.1

**新建 CIP（2 份）**：

- **`refs/cips/cip-8-mpp-session.md`**（Draft，2026-05-11，retroactive）— 追认代码已实装的 MPP Session 协议。SESSION_ACTOR `0x0C`（`system_actors.rs:35`）；6 handler（`handle_session_open` / `_deposit` / `_settle` / `_close` / `_finalize` / `_slash` per `node/execution/src/runner/session.rs`）；on-chain Session 结构 / off-chain SessionVoucher / EIP-712 domain（`node/types/src/session*.rs`）；链下 voucher 库（`runner/crates/runner-common/src/voucher.rs`）。18 sections 含 §3 retroactive 说明、§12 opcode-vs-enum 澄清（关闭 V-12）、§13 EIP-712 chainId 激活规则（部分关闭 V-13）、§11 dispute 路径（PoC `Slash` 返 Unsupported，二期接 CIP-2 Result Verifier）

- **`refs/cips/cip-17-verifiable-state-read.md`**（Draft，2026-05-11）— 起草 `GET /state/{actor}/{key}` RPC，返回 `(value, merkle_proof, state_root, block_height)`，客户端本地验证。复用 CIP-4 既有 MPT trie 原语；估实现 < 200 行。12 sections。**关闭 V-17**（CIP-15 v2.r2 Gateway routes-table fetch + CIP-19 `tools/list` derivation 的唯一硬阻塞 RPC）。CIP-15-gateway-implementation r2 §2.2 + §9 / CIP-19 §10.1 step 1 同步指向 CIP-17

**WP-v2 → v2.r2 + 3 新 Delta**：

- **Delta 7**（§17.y）—— Payment Layer（CIP-18 r2）：PaymentGate `0x11` + 4 付款模型 + MPP/x402 双 wire + EVM bridge facilitator
- **Delta 8**（§6.z）—— MCP Ingress（CIP-19）：actor-as-MCP-server 经 Gateway，tools/list 派生自 CIP-15 routes
- **Delta 9**（§16.z）—— Cross-Chain Architecture（CIP-25）：三层架构 + 接口契约 vs §16.2 governance 分工的明文澄清
- §6 Summary table 扩到 9 Delta；frontmatter "Summary of proposed deltas" 同步更新

**CIP-25 → r1.1**（小修订）：

- 加 §1.4 governance scope 段：CIP-25 标准化 `IChainAnchor` **interface contract**；具体后端部署由 **WP-v2 §16.2** 治理决定。明文化与 WP §16.2 "no protocol validator set" 框架的一致性。frontmatter 加 revision history

**Wiki 同步**：

- **`wiki/concepts/mpp-session.md`** — 状态从"研究阶段"改为"代码已实装 + CIP-8 已起草（retroactive）"；frontmatter 加 CIP-8 + 代码源；V-11/V-12 标 ✅，V-13 标 PoC chainId 待澄清
- **`wiki/concepts/verifiable-state-read.md`** —— 新建概念页，标 CIP-17；说明 vs `read_handler` 互补；主消费者表 + 实现路径 + 待解决项
- **`wiki/index.md`** —— concepts 段加 `verifiable-state-read`；顶部"最后更新"含 r2 + 后续补 CIP
- **`wiki/drift.md`** —— V-12 标 ✅（CIP-8 §12 给说明）；V-13 状态从"未明"改"PoC + 激活规则已在 CIP-8 §13"；V-17 标 ✅（CIP-17 起草）；顶部 r2 sync 段扩到包含第二轮补 CIP；累计已收口 V-* = V-1 / V-11 / V-12 / V-14 / V-17

**仍待解决（已无文档侧动作可做，全部是代码侧 precondition）**：

- entitlement registry +6 entries (V-2 + V-15) — `node/types/src/registry.rs:35-219` 加 6 行
- 系统 actor const 5 个 (V-1) — `node/runner/src/system_actors.rs` 加 5 行 + 同步 workspace `CLAUDE.md`
- `read_handler` RPC + `GET_STATE` RPC 实装 — `node/rpc/src/rpc.rs` 加 2 routes + storage backend method
- `target_pool` enum 实装 (V-9) — `node/runner/src/types.rs` SettlementConfig discriminant
- timer `fee_payer` field 实装 (V-8) — `node/execution/src/timer_config.rs`
- VerificationMode `DnsTxtRecordMatch` / `DnsCnameMatch` 实装 — `node/runner/src/types.rs`
- CIP-25 L1 anchor + L2 mailbox 整套实装 — 新 actor / contract 工作
- `EXTERNAL_REVERIFY_FEE` 治理选定数值 (V-10)
- 各 CIP `0x06` Stream Key Manager (CIP-7 v1) 与代码 `DUAL_BASEFEE = 0x06` 的根冲突 —— 需 CIP-7 v2 / v3 修文档（**未在本轮触动**，待 CIP-7 团队负责人发版）

**权威层级标注**: CIP-8 / CIP-17 / WP-v2 Delta 7-9 全部 Draft；激活路径全部经治理（CIP-12）+ 代码 PR + 跨子系统集成。

---

## [2026-05-11] amend | 第三轮审计 — CIP-7 r2 + WP-v2 Delta 6 微修

第三轮跨 CIP / CIP-vs-WP / CIP-vs-代码冲突全面审计完成。除既知精确度，agent 报告全部段（地址段对齐 / Merkle 描述 / CIP-18-19 互引 / CIP-8 内部一致性 / CIP-17 引用 / SystemInstruction enum / VerificationMode / TimerConfig / SettlementConfig / CBFS Merkle）全部 CLEAN。**剩 2 项可修文档侧 + 1 项可澄清**：

**Fix 1 — CIP-7 r2 bump（解长期 drift）**

- 现状：`refs/cips/cip-7-simple-stream-protocol.md` v1 line 136 仍写 `0x06 = Stream Key Manager`，与代码 `node/runner/src/system_actors.rs:23` `DUAL_BASEFEE = 0x06` 冲突。CIP-7 自 2026-02-17 起未发 v2，长期 drift。
- 修：CIP-7 → r2 frontmatter + revision history banner；§4 system actor 表 `0x06` 改 `0x12`（v2.r2 序列下一空位，在 CIP-18 r2 `0x11` 之后）；表整体扩展到 `0x01-0x12`；内部 storage prefix `0x6` 保留 + 加 r2 namespace 澄清注（系统 actor 地址 vs 单 actor 内部 storage 命名空间正交，不冲突）

**Fix 2 — WP-v2 Delta 6 表微修**

- 现状：`0x0C` 行字段写 "code (Draft CIP TBD)"；CIP-8 (MPP Session retroactive) 已起草。
- 修：改 "code (Draft CIP TBD)" → "CIP-8 (retroactive)"
- 同步追加 `0x12 = Stream Key Manager (CIP-7 r2)` 行

**Fix 3（自动联动）— CIP-14 v2.r2 / CIP-15 v2.r2 / CIP-16 v2.r2 Part III §1 表**

- 三个 Part III 系统 actor 表追加 `0x12 = STREAM_KEY_MANAGER` 行
- CIP-18 r2 §22 rationale 段：把"CIP-7's `0x06` 是另一码事独立 drift"改为"CIP-7 r2 已解决，移到 `0x12`"

**Fix 4（联动）— wiki/entities/system-actors.md**

- 表格追加 `0x12` 行；脚注"源"字段加 CIP-7 r2

**CIP-4 storage key prefix 0x0C / 0x0D 视觉冲突（澄清，未修）**

- `refs/cips/cip-4-storage.md` line 99-100 用 `0x0C` / `0x0D` 作 storage key prefix（namespace 内字节，不是系统 actor 地址）；视觉上与 v2.r2 系统 actor `0x0C SESSION_ACTOR` / `0x0D ROUTE_REGISTRY` 撞符号
- 实际不冲突 —— 系统 actor 地址是 20-byte 全局 address trie key；storage key prefix 是单 actor 内部 trie 内的 1-byte namespace
- 类比 CIP-7 r2 storage prefix `0x6` 的解释：同样命名空间正交
- 不修：CIP-4 是 1-byte namespace 习惯，迁移成本高；视觉混淆可由后续编辑澄清

**剩余 11 项纯代码 precondition 状态不变**：V-2 / V-3 / V-4 / V-6 / V-8 / V-9 / V-10 / V-13 / V-15 / V-16 + 5 个 system actor const + GET_STATE RPC 实装。全部需代码 PR。

**第三轮 audit 已找完所有文档侧可修内容；无遗漏**。

---

## [2026-05-11] amend | 第四轮审计 — CIP-11 入库 + r1.1 修订

用户新增 `refs/cips/cip-11-runner-connectivity.md`（Runner Connectivity and Push Job Delivery；Created 2026-04-14；**预 v2 alignment round 6**）。第四轮跨 CIP 审计发现 3 项 CIP-11 相关冲突，全部为文档侧可修：

**Finding 1 — CIP-11 §9.3 weight 基数与 CIP-13 v2 §3 不一致**

- CIP-11 v0.2 §9.3 algorithm（line 397 / 404）：`stake_to_weight(candidate[i].stake, MIN_STAKE_CBY_WEI)`
- CIP-13 v2 §3 (Updated 2026-04-21)：normative VRF / Fisher-Yates 权重必须用 `effective_stake = registration.stake + delegation_totals.total_active`
- CIP-11 §9.3 prose（line 415）实际描述了 "effective stake on iteration 0" —— 内部 algorithm vs prose 已有不一致
- **修**：CIP-11 → r1.1，§9.3 algorithm 改为 `base[i] = stake_to_weight(effective_stake(candidate[i]), MIN_STAKE_CBY_WEI)`；frontmatter `Requires` 加 CIP-13 v2

**Finding 2 — 块时间假设 5s vs CIP-14 / CIP-23**

- CIP-11 §13 系统常量全部按 "5 s blocks" 标注（`SUBSET_EPOCH_BLOCKS = 8192 ~12h`, `STALE_HEARTBEAT_BLOCKS = 1024 ~85min`, `MRU_TTL_BLOCKS = 256 ~21min`）
- 既有 drift L-5 只列 CIP-14 v1 (1s) / CIP-23 v2 (500ms) 不一致；现 CIP-11 加入第三种 5s
- **修**：CIP-11 r1.1 §13 加块时间 disclaimer：wall-clock 数值（~12h / ~21min / ~85min）权威；raw block counts 是导出；governance 激活前需 rescale；drift L-5 扩展加 CIP-11

**Finding 3 — README + wiki/index 未列 CIP-11**

- CIP-11 自 2026-04-14 在 raw cips 目录但 README / wiki/index 未列入
- **修**：README §"📋 cips/" + "新 CIPs" 段加 CIP-11；wiki/index 顶部"最后更新"日期同步

**新 CIP-11 验证（无新冲突点）**

- 不引入新 system actor、新 SystemInstruction opcode、新 entitlement
- 引用现有 `Runner Registry (0x01)` / `Job Dispatcher (0x02)` / `Result Verifier (0x03)` —— 与 v2.r2 系统 actor 主表无冲突
- 唯一新增链上状态：`mru_key(submitter, job_kind)` 加入 `0x02` Job Dispatcher 的现有 storage map（不需新 key prefix 命名空间）
- §7.1 / §12.3 扩展 vote 消息加 `vote_presence_bitmap` —— 经 grep 全 spec 无其他 CIP 声称扩展 vote 消息，无冲突
- §10 push-dispatch / §11 失败处理 / §14 三阶段 migration —— 完全在 CIP-2 既有框架内增量

**新 CIP-11 内部一致性问题（除 Finding 1/2 外）**

- §10.6 / §11 dispatch 失败分类与 CIP-2 §6 timeout-based re-selection 兼容；不引入新 slashing
- §15 安全考量：MRU 在 iteration 0 偏置 + cap MULTIPLIER=4 + 仅 iteration 0 生效 —— 与 CIP-13 v2 effective_stake 模型组合下，效果是 "delegated runner 同时享受 effective_stake × 4 优势 on iteration 0"。这是合理的级联（delegated runner 已经因为 stake 增加在 base weight 上有优势），不需要额外限制
- §14 phase 1 shadow / phase 2 hot-path / phase 3 sunset migration 完整闭环

**与新 v2.r2 CIPs 关系**

- vs CIP-8 (MPP Session)：session 模式调用走 off-chain HTTP，不经 CIP-11 push 路径；正交
- vs CIP-18 (Payments)：CIP-11 是 runner 调度优化，不涉付款；正交
- vs CIP-19 (MCP Ingress)：MCP 经 Gateway → runner，runner 端调度仍走 CIP-11；CIP-11 是 CIP-19 hot-path 性能保障
- vs CIP-25 (Cross-Chain)：CIP-25 §1.4 runner-committee 后端依赖 runner 选举 + dispatch，CIP-11 优化二者 latency；正交

**wiki 修订**

- `wiki/drift.md` L-5 扩展加 CIP-11 5s 信息
- `README.md` —— CIP 列表 "1 到 17" → "1 到 25"；新 CIPs 段加 CIP-11 r1.1 + CIP-7 r2
- `wiki/index.md` 顶部"最后更新"刷新

**未触动**

- 代码（按用户指令"代码不动"）
- wiki/entities/runner-lifecycle.md —— CIP-11 是 dispatch 路径优化，不改 runner 生命周期阶段，无需新建 concept page；如未来 push-delivery 实装可加一段 "CIP-11 Push Path"
- 未新建 `wiki/concepts/runner-connectivity.md` —— CIP-11 单 CIP 自包含，wiki 综合层暂不需要专门页面（参 [[runner-verification]] / [[vrf-runner-selection]] / [[runner-delegation]] 仅在 spec 跨 3+ 文档时建页的规则）

**第四轮 audit 完结。文档侧可修问题全部 ✅。剩余 11 项纯代码 precondition 状态不变**。

---
