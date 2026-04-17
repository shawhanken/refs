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
