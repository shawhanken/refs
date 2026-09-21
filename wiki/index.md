# Wiki 内容索引

本文件列出 `refs/wiki/` 所有页面与一句话摘要。按类型组织。

**最后更新**: 2026-09-21（有效性审计：修正本索引与各页的矛盾摘要；标注 `refs/cips/` 为过时快照。**注意各页新鲜度不一** —— `parameters.md` / `entities/system-actors.md` 已于 2026-08-15 按代码 pin 测试重写，其余 concept 页多数仍停在 2026-05-26，摘要里的地址可能已失效，以页内 `last_updated` 为准）

> ⚠️ **CIP 规范的权威副本是 `cowboy/docs/cips/`，不是 `refs/cips/`。** 后者 34 份全部是过时快照（档头有 STALE SNAPSHOT 横幅）。ingest / 裁决规范时读 `cowboy/docs/cips/`。

<details><summary>上一版说明（2026-05-26）</summary>

（spec ↔ code 大对齐：CIP-13 §1 master opcode 表按 `node/types/src/execution.rs` 现状重写；CIP-29 `EVENT_SUBSCRIPTION_SYSTEM_ACTOR = 0x1D` 写入 spec；CIP-28 BankActor 0x0D → 0x13；CIP-24 TEE keys 60-63 与代码一致；CIP-9 §13 补 DrainRelay / AutoDrainPolicy spec；块时间统一到 1s（CIP-11 r1.2 + CIP-23 r1）；WP-v2 §13 加状态列；drift.md C-1/C-2/C-3/C-4 已收口）

</details>

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
| [dns-addressable-actors.md](concepts/dns-addressable-actors.md) | CIP-14 v2 HTTP ingress：`ingress.http` entitlement、Read-only/Command 双路径、IngressDispatch 65/CompleteReceipt 66、ROUTE_REGISTRY=0x0E/GATEWAY_REGISTRY=0x0F/RECEIPT_REGISTRY=0x10（代码落位，见 entities/system-actors）|
| [public-asset-hosting.md](concepts/public-asset-hosting.md) | CIP-15 v2 Gateway 直服 CIP-9 public volume 静态资产；独立 ingress.static entitlement、route_manifest on-chain、`GET_MANIFEST` (AMEND 9-G)、CORS 优先级修正（Draft）|
| [custom-domains.md](concepts/custom-domains.md) | CIP-16 v2 `.cow` / `.cowboy` TLD + 外部 FQDN 绑定（MajorityVote DNS 验证 + ExternalDomainCallback opcode 67 + 双层 reverify fee + verified_fqdn 注入, Draft）|
| [tee-attestation.md](concepts/tee-attestation.md) | CIP-23 v2 CAE 复合证明 + 三层资格 chain + opcode 57-60 + 与 CIP-13 委托正交（Draft）|
| [mpp-session.md](concepts/mpp-session.md) | MPP Session：链上托管 + 链下累积 voucher + 链上结算；3 笔 tx 摊到 N 次 Runner 调用；提议 SESSION_ACTOR=0x0C / opcodes 52-57（**与 CIP-14 v2 / CIP-13 v2 / CIP-23 v2 冲突**, Research）|
| [payments.md](concepts/payments.md) | CIP-18 PaymentGate（代码 **`0x12`**；页内若仍写 `0x13`/`0x11` 是旧 spec 序列）：MPP（primary）+ x402（compat）双 wire；per-request / actor-funded / pass / epoch subscription 四种付款模型；入站 EVM bridge facilitator；`payment.gate` entitlement（Draft）|
| [mcp-ingress.md](concepts/mcp-ingress.md) | CIP-19 Gateway 边缘把每个 actor 暴露为 MCP server；`tools/list` 从 CIP-15 路由表派生；`tools/call` 复用 CIP-14 dispatch；付款经 JSON-RPC `_meta` + 错误码 -32402（Draft）|
| [cross-chain.md](concepts/cross-chain.md) | CIP-25 三层架构：L1 state anchoring（可换信任后端：runner committee / ZK / optimistic / native LC）+ L2 mailbox（exactly-once + 单调）+ L3 应用（bridge / lending / oracle / generic call），跨链流式经 send_stream 复用 CIP-7（Draft）|
| [verifiable-state-read.md](concepts/verifiable-state-read.md) | CIP-17 `GET /state/{actor}/{key}` 返回 KV + Merkle proof；CIP-15 v2.r2 Gateway 路由缓存 + CIP-19 `tools/list` 派生硬阻塞 RPC；与 `read_handler` 互补（Draft）|

---

## 🏗️ 实体页（entities/）

具体系统组件与对象。

| 页面 | 摘要 |
|---|---|
| [system-actors.md](entities/system-actors.md) | **（2026-08-15 按代码 pin 测试重写，本 wiki 最可信的地址来源）** `0x01–0x1E` 全部已声明常量，不再有 spec-only 段：`0x0D` STREAM_KEY_MANAGER / `0x0E` ROUTE / `0x0F` GATEWAY / `0x10` RECEIPT / `0x11` VALIDATOR_SET / `0x12` PAYMENT_GATE / `0x13` CONTAINER / `0x16` BANK_ACTOR / `0x1D` EVENT_SUBSCRIPTION（虚拟）/ `0x1E` TRADING_POST |
| [runner-lifecycle.md](entities/runner-lifecycle.md) | Runner 从 register → 接单 → 结算 → 可能 slash 的全流程；含 CIP-13 v2 / CIP-23 v2 集成 |
| [pvm.md](entities/pvm.md) | Python VM：API、确定性约束、Checkpoint、黑名单 + CIP-14 v2 read_handler RPC 只读模式 |
| [node.md](entities/node.md) | 主链节点：chain/execution/storage/types/rpc 架构 |
| [plans-inventory.md](entities/plans-inventory.md) | `refs/plans/` 31 份工程实施计划清单（按主题分组、slug → 标题映射）|
| [gateway.md](entities/gateway.md) | Gateway 节点角色（第 4 个协议 role）：TLS/DNS/路由/静态 serving/速率限制（CIP-14 / CIP-15 Draft；Gateway Registry 代码落位 **`0x0F`** —— 页内写 `0x0E` 是旧 spec 序列）|
| [route-registry.md](entities/route-registry.md) | 系统 Actor 代码落位 **`0x0E`**（页内写 `0x0D` 是旧 spec 序列，`0x0D` 实为 STREAM_KEY_MANAGER）：FQDN 注册 + 三类命名空间 + Binding 状态机（CIP-14 v2.r2 / CIP-16 v2.r2 Draft）|

---

## 📚 Raw Sources 快速链接

按主题指向 raw 目录（`refs/wiki/` 外的原始文档）：

- [`refs/whitepaper/`](../whitepaper/) — 核心白皮书（受保护）；历史版本在 [`_archive_/`](../whitepaper/_archive_/)，**不是权威**
- **`cowboy/docs/cips/` — CIP 规范（唯一权威，CIP-1 ~ 42）**
- [`refs/cips/`](../cips/) — ⚠️ 过时快照（CIP-1~26/28/29/31/39，档头有 STALE SNAPSHOT 横幅）+ `ext_*` 扩展分析。**不要用于裁决规范**；`*-v2.md` 独立档已并入同名档，不再存在
- [`refs/analysis/`](../analysis/) — 分析、会议、**修正案** + **代码实现进度审计**
  - 修正案权威：`2026-04-15_documentation_amendments.md`
  - CIP 完成度 audit 系列（**均为当日快照，最新一份也已数月**）：`2026-05-15` → `2026-05-26` → `2026-05-27_CN` →
    `2026-05-28_CN` → [`2026-05-29_CIP_WP_AUDIT_CN.md`](../analysis/2026-05-29_CIP_WP_AUDIT_CN.md)（最后一份完成度 audit）；
    更晚的跨 CIP 盘点是 [`2026-07-09_cips-wp-deep-audit.md`](../analysis/2026-07-09_cips-wp-deep-audit.md) 与
    [`20260913_CIP_Launch_Priority_Ranking_CN.md`](../analysis/20260913_CIP_Launch_Priority_Ranking_CN.md)（上线优先级，非完成度）
- [`refs/plans/`](../plans/) — 工程实施计划 / 评估（31 份，多已执行完或放弃；详见 [entities/plans-inventory.md](entities/plans-inventory.md)）
- [`refs/economics/`](../economics/) — 费用模型、Basefee、Tokenomics
- [`refs/node/`](../node/) — 节点专题
- [`refs/pvm/`](../pvm/) — PVM 专题
- [`refs/runner/`](../runner/) — Runner 专题
- [`refs/chain/`](../chain/) — 跨系统集成
- [`refs/devex/`](../devex/) — 开发者体验 / 客户反馈
- [`refs/common/`](../common/) — 基础设施工具
- [`refs/meeting/`](../meeting/) — 会议逐字稿 / 纪要 / Slack 存档
- [`refs/notion/`](../notion/) — Notion 导入的设计评审材料（cowboy-vm-shared）

---

## 📖 阅读路径建议

**新人**: `concepts/actor-model.md` → `concepts/dual-gas-model.md` → `entities/system-actors.md` → `entities/pvm.md`

**开发 Runner**: `entities/runner-lifecycle.md` → `concepts/vrf-runner-selection.md` → `concepts/runner-verification.md` → `concepts/settlement-slashing.md` → `concepts/tee-attestation.md`

**审计经济**: `parameters.md` → `concepts/basefee.md` → `concepts/dual-gas-model.md` → `concepts/settlement-slashing.md`（target_pool enum） → `drift.md`

**HTTP Ingress / Web 应用**: `concepts/dns-addressable-actors.md` → `entities/gateway.md` → `entities/route-registry.md` → `concepts/public-asset-hosting.md` → `concepts/custom-domains.md` → `concepts/payments.md`（付款）→ `concepts/mcp-ingress.md`（agent 调用）

**跨链 / 桥**: `concepts/cross-chain.md` → `concepts/runner-verification.md`（committee 后端）→ `concepts/vrf-runner-selection.md`

**v2 协议落地路径**（实装前清单）: `drift.md` v2 precondition gap → `parameters.md` SystemInstruction Opcode 主分配表 → 相应 entity / concept 页

**排查冲突**: `drift.md` → `refs/analysis/2026-04-15_documentation_amendments.md`
