# Wiki 内容索引

本文件列出 `refs/wiki/` 所有页面与一句话摘要。按类型组织。

**最后更新**: 2026-05-11（r2 alignment + 新 CIP-8 / 11 / 17 / 18 / 19 / 25；CIP-7 r2 解 0x06 drift；CIP-11 r1.1 锚定 effective_stake + 块时间 disclaimer）

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
| [parameters.md](parameters.md) | 全系统参数/常量权威表（cycles、cells、stake、timer 预算、SystemInstruction opcode 主分配表、SettlementConfig target_pool 枚举）|
| [drift.md](drift.md) | 文档-代码漂移看板 + v2 precondition gap |

---

## 🧠 概念页（concepts/）

跨文档综合的抽象主题。

| 页面 | 摘要 |
|---|---|
| [actor-model.md](concepts/actor-model.md) | Cowboy Actor 模型：Message、Actor、调度、隔离 |
| [continuation.md](concepts/continuation.md) | Actor↔Actor / Actor↔Runner 挂起-恢复机制、Checkpoint、FSM |
| [dual-gas-model.md](concepts/dual-gas-model.md) | Cycles（计算）+ Cells（数据）双计量、EIP-1559 基模型 |
| [basefee.md](concepts/basefee.md) | Basefee 几何更新公式、MIN/MAX、代码实测参数 + CIP-5 revised timer fee_payer 关联 |
| [speculative-execution.md](concepts/speculative-execution.md) | 块生命周期：propose/verify 投机执行 + report 提交 |
| [timer-mechanism.md](concepts/timer-mechanism.md) | Timer 调度模型（CIP-5 revised 2026-04-20：per-fire fee_payer + 三路退出 + LANE/GC 双预算）|
| [runner-verification.md](concepts/runner-verification.md) | 6 种 VerificationMode + CIP-2 v2 新增 DnsTxtRecordMatch / DnsCnameMatch、结算与仲裁窗口 |
| [settlement-slashing.md](concepts/settlement-slashing.md) | SettlementConfig 6-enum target_pool（MAIN/REGISTRY/GATEWAY_POOL/CONTAINER/REGISTRY_TLD_*）、Slashing 50/50 默认 |
| [vrf-runner-selection.md](concepts/vrf-runner-selection.md) | Fisher-Yates VRF + CIP-13 v2 effective_stake 修正、CIP-23 v2 measurement_binding 过滤 |
| [governance.md](concepts/governance.md) | CIP-12 双院治理、Tier 0-4 提案、Security Council、系统 Actor 升级（Draft）|
| [runner-delegation.md](concepts/runner-delegation.md) | CIP-13 v2 Runner Stake 委托：Tranche、分账、slash 级联、懒惰解绑、opcode 52-56（Draft）|
| [dns-addressable-actors.md](concepts/dns-addressable-actors.md) | CIP-14 v2 HTTP ingress：`ingress.http` entitlement、Read-only/Command 双路径、IngressDispatch 65/CompleteReceipt 66、ROUTE_REGISTRY=0x0C/GATEWAY_REGISTRY=0x0D/RECEIPT_REGISTRY=0x0E（Draft）|
| [public-asset-hosting.md](concepts/public-asset-hosting.md) | CIP-15 v2 Gateway 直服 CIP-9 public volume 静态资产；独立 ingress.static entitlement、route_manifest on-chain、`GET_MANIFEST` (AMEND 9-G)、CORS 优先级修正（Draft）|
| [custom-domains.md](concepts/custom-domains.md) | CIP-16 v2 `.cow` / `.cowboy` TLD + 外部 FQDN 绑定（MajorityVote DNS 验证 + ExternalDomainCallback opcode 67 + 双层 reverify fee + verified_fqdn 注入, Draft）|
| [tee-attestation.md](concepts/tee-attestation.md) | CIP-23 v2 CAE 复合证明 + 三层资格 chain + opcode 57-60 + 与 CIP-13 委托正交（Draft）|
| [mpp-session.md](concepts/mpp-session.md) | MPP Session：链上托管 + 链下累积 voucher + 链上结算；3 笔 tx 摊到 N 次 Runner 调用；提议 SESSION_ACTOR=0x0C / opcodes 52-57（**与 CIP-14 v2 / CIP-13 v2 / CIP-23 v2 冲突**, Research）|
| [payments.md](concepts/payments.md) | CIP-18 PaymentGate（`0x13`）：MPP（primary）+ x402（compat）双 wire；per-request / actor-funded / pass / epoch subscription 四种付款模型；入站 EVM bridge facilitator；`payment.gate` entitlement（Draft）|
| [mcp-ingress.md](concepts/mcp-ingress.md) | CIP-19 Gateway 边缘把每个 actor 暴露为 MCP server；`tools/list` 从 CIP-15 路由表派生；`tools/call` 复用 CIP-14 dispatch；付款经 JSON-RPC `_meta` + 错误码 -32402（Draft）|
| [cross-chain.md](concepts/cross-chain.md) | CIP-25 三层架构：L1 state anchoring（可换信任后端：runner committee / ZK / optimistic / native LC）+ L2 mailbox（exactly-once + 单调）+ L3 应用（bridge / lending / oracle / generic call），跨链流式经 send_stream 复用 CIP-7（Draft）|
| [verifiable-state-read.md](concepts/verifiable-state-read.md) | CIP-17 `GET /state/{actor}/{key}` 返回 KV + Merkle proof；CIP-15 v2.r2 Gateway 路由缓存 + CIP-19 `tools/list` 派生硬阻塞 RPC；与 `read_handler` 互补（Draft）|

---

## 🏗️ 实体页（entities/）

具体系统组件与对象。

| 页面 | 摘要 |
|---|---|
| [system-actors.md](entities/system-actors.md) | `0x01-0x0F` 系统 Actor 地址权威表（含 v2 提案 0x0C-0x0F precondition）|
| [runner-lifecycle.md](entities/runner-lifecycle.md) | Runner 从 register → 接单 → 结算 → 可能 slash 的全流程；含 CIP-13 v2 / CIP-23 v2 集成 |
| [pvm.md](entities/pvm.md) | Python VM：API、确定性约束、Checkpoint、黑名单 + CIP-14 v2 read_handler RPC 只读模式 |
| [node.md](entities/node.md) | 主链节点：chain/execution/storage/types/rpc 架构 |
| [plans-inventory.md](entities/plans-inventory.md) | `refs/plans/` 23 份工程实施计划清单（按主题分组、slug → 标题映射）|
| [gateway.md](entities/gateway.md) | Gateway 节点角色（第 4 个协议 role）：TLS/DNS/路由/静态 serving/速率限制（CIP-14 v2 / CIP-15 v2 Draft，地址 0x0D）|
| [route-registry.md](entities/route-registry.md) | 系统 Actor `0x0C`：FQDN 注册 + 三类命名空间 + Binding 状态机（CIP-14 v2 / CIP-16 v2 Draft）|

---

## 📚 Raw Sources 快速链接

按主题指向 raw 目录（`refs/wiki/` 外的原始文档）：

- [`refs/whitepaper/`](../whitepaper/) — 核心白皮书（受保护）+ WP v2 deltas
- [`refs/cips/`](../cips/) — CIP 规范（CIP-1 到 CIP-23）+ v2 alignment 系列（CIP-1/2/9/10/13/14/15/16/23 v2）
- [`refs/analysis/`](../analysis/) — 分析、会议、**修正案**（`2026-04-15_documentation_amendments.md` 为权威）
- [`refs/plans/`](../plans/) — 工程实施计划 / 评估（27 份，详见 [entities/plans-inventory.md](entities/plans-inventory.md)）
- [`refs/economics/`](../economics/) — 费用模型、Basefee、Tokenomics
- [`refs/node/`](../node/) — 节点专题
- [`refs/pvm/`](../pvm/) — PVM 专题
- [`refs/runner/`](../runner/) — Runner 专题
- [`refs/chain/`](../chain/) — 跨系统集成
- [`refs/devex/`](../devex/) — 开发者体验 / 客户反馈
- [`refs/common/`](../common/) — 基础设施工具

---

## 📖 阅读路径建议

**新人**: `concepts/actor-model.md` → `concepts/dual-gas-model.md` → `entities/system-actors.md` → `entities/pvm.md`

**开发 Runner**: `entities/runner-lifecycle.md` → `concepts/vrf-runner-selection.md` → `concepts/runner-verification.md` → `concepts/settlement-slashing.md` → `concepts/tee-attestation.md`

**审计经济**: `parameters.md` → `concepts/basefee.md` → `concepts/dual-gas-model.md` → `concepts/settlement-slashing.md`（target_pool enum） → `drift.md`

**HTTP Ingress / Web 应用**: `concepts/dns-addressable-actors.md` → `entities/gateway.md` → `entities/route-registry.md` → `concepts/public-asset-hosting.md` → `concepts/custom-domains.md` → `concepts/payments.md`（付款）→ `concepts/mcp-ingress.md`（agent 调用）

**跨链 / 桥**: `concepts/cross-chain.md` → `concepts/runner-verification.md`（committee 后端）→ `concepts/vrf-runner-selection.md`

**v2 协议落地路径**（实装前清单）: `drift.md` v2 precondition gap → `parameters.md` SystemInstruction Opcode 主分配表 → 相应 entity / concept 页

**排查冲突**: `drift.md` → `refs/analysis/2026-04-15_documentation_amendments.md`
