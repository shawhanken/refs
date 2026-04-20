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
