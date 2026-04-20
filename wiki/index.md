# Wiki 内容索引

本文件列出 `refs/wiki/` 所有页面与一句话摘要。按类型组织。

**最后更新**: 2026-04-20

---

## 📋 操作与元文档

| 页面 | 摘要 |
|---|---|
| [AGENTS.md](AGENTS.md) | Wiki 操作规约（Ingest/Query/Lint 工作流、页面格式、权威层级）|
| [index.md](index.md) | 本索引 |
| [log.md](log.md) | 时序变更日志（ingest / query / lint 记录）|

---

## 🎯 综合看板

| 页面 | 摘要 |
|---|---|
| [parameters.md](parameters.md) | 全系统参数/常量权威表（cycles、cells、stake、timer 预算等）|
| [drift.md](drift.md) | 文档-代码漂移看板（指向最新修正案）|

---

## 🧠 概念页（concepts/）

跨文档综合的抽象主题。

| 页面 | 摘要 |
|---|---|
| [actor-model.md](concepts/actor-model.md) | Cowboy Actor 模型：Message、Actor、调度、隔离 |
| [continuation.md](concepts/continuation.md) | Actor↔Actor / Actor↔Runner 挂起-恢复机制、Checkpoint、FSM |
| [dual-gas-model.md](concepts/dual-gas-model.md) | Cycles（计算）+ Cells（数据）双计量、EIP-1559 基模型 |
| [basefee.md](concepts/basefee.md) | Basefee 几何更新公式、MIN/MAX、代码实测参数 |
| [speculative-execution.md](concepts/speculative-execution.md) | 块生命周期：propose/verify 投机执行 + report 提交 |
| [timer-mechanism.md](concepts/timer-mechanism.md) | Timer 调度模型（GBA 已实现，EOB 未实现）、预算 |
| [runner-verification.md](concepts/runner-verification.md) | 6 种 VerificationMode、结算与仲裁窗口 |
| [settlement-slashing.md](concepts/settlement-slashing.md) | SettlementConfig 分成、Slashing 50/50 规则 |
| [vrf-runner-selection.md](concepts/vrf-runner-selection.md) | Fisher-Yates VRF + stake-weighted sortition 算法 |
| [governance.md](concepts/governance.md) | CIP-12 双院治理、Tier 0-4 提案、Security Council、系统 Actor 升级（Draft）|
| [runner-delegation.md](concepts/runner-delegation.md) | CIP-13 Runner Stake 委托：Tranche、分账、slash 级联、懒惰解绑（Draft）|
| [dns-addressable-actors.md](concepts/dns-addressable-actors.md) 🆕 | CIP-14 HTTP ingress：`ingress.http` entitlement、Query/Command 双路径、系统中介 dispatch（Draft）|
| [public-asset-hosting.md](concepts/public-asset-hosting.md) 🆕 | CIP-15 Gateway 直服 CIP-9 public volume 静态资产；路由清单、CORS、`GET_MANIFEST`（Draft）|
| [custom-domains.md](concepts/custom-domains.md) 🆕 | CIP-16 `.cow` / `.cowboy` TLD + 外部 FQDN 绑定（TXT 挑战 + ACME 委派 + 周期重验证, Draft）|
| [tee-attestation.md](concepts/tee-attestation.md) 🆕 | CIP-23 CAE 复合证明 + attestation-first 注册 + Deterministic 模式密码学强制（Draft）|

---

## 🏗️ 实体页（entities/）

具体系统组件与对象。

| 页面 | 摘要 |
|---|---|
| [system-actors.md](entities/system-actors.md) | 0x01-0x0B 系统 Actor 地址权威表 |
| [runner-lifecycle.md](entities/runner-lifecycle.md) | Runner 从 register → 接单 → 结算 → 可能 slash 的全流程 |
| [pvm.md](entities/pvm.md) | Python VM：API、确定性约束、Checkpoint、黑名单 |
| [node.md](entities/node.md) | 主链节点：chain/execution/storage/types/rpc 架构 |
| [plans-inventory.md](entities/plans-inventory.md) | `refs/plans/` 23 份工程实施计划清单（按主题分组、slug → 标题映射）|
| [gateway.md](entities/gateway.md) 🆕 | Gateway 节点角色（第 4 个协议 role）：TLS/DNS/路由/静态 serving/速率限制（CIP-14/15 Draft）|
| [route-registry.md](entities/route-registry.md) 🆕 | 系统 Actor `0x0011`：FQDN 注册 + 三类命名空间 + Binding 状态机（CIP-14/16 Draft）|

---

## 📚 Raw Sources 快速链接

按主题指向 raw 目录（`refs/wiki/` 外的原始文档）：

- [`refs/whitepaper/`](../whitepaper/) — 核心白皮书（受保护）
- [`refs/cips/`](../cips/) — CIP 规范（CIP-1 到 CIP-23，含 CIP-12/13/14/15/16/23 Draft）
- [`refs/analysis/`](../analysis/) — 分析、会议、**修正案**（`2026-04-15_documentation_amendments.md` 为权威）
- [`refs/plans/`](../plans/) — 工程实施计划 / 评估（22 份，详见 [entities/plans-inventory.md](entities/plans-inventory.md)）
- [`refs/economics/`](../economics/) — 费用模型、Basefee、Tokenomics
- [`refs/node/`](../node/) — 节点专题
- [`refs/pvm/`](../pvm/) — PVM 专题
- [`refs/runner/`](../runner/) — Runner 专题
- [`refs/chain/`](../chain/) — 跨系统集成
- [`refs/devex/`](../devex/) — 开发者体验 / 客户反馈
- [`refs/common/`](../common/) — 基础设施工具
- [`refs/_archive_/`](../_archive_/) — 归档历史

---

## 📖 阅读路径建议

**新人**: `concepts/actor-model.md` → `concepts/dual-gas-model.md` → `entities/system-actors.md` → `entities/pvm.md`

**开发 Runner**: `entities/runner-lifecycle.md` → `concepts/vrf-runner-selection.md` → `concepts/runner-verification.md` → `concepts/settlement-slashing.md` → `concepts/tee-attestation.md`

**审计经济**: `parameters.md` → `concepts/basefee.md` → `concepts/dual-gas-model.md` → `drift.md`

**HTTP Ingress / Web 应用**: `concepts/dns-addressable-actors.md` → `entities/gateway.md` → `entities/route-registry.md` → `concepts/public-asset-hosting.md` → `concepts/custom-domains.md`

**排查冲突**: `drift.md` → `refs/analysis/2026-04-15_documentation_amendments.md`
