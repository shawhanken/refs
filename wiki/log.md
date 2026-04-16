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
