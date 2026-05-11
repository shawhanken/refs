---
type: comparison
tags: [drift, consistency, audit]
sources:
  - refs/analysis/2026-04-15_documentation_amendments.md
  - refs/cips/cip-13-runner-delegation-v2.md
  - refs/cips/cip-14-dns-addressable-actors-v2.md
  - refs/cips/cip-15-public-asset-hosting-v2.md
  - refs/cips/cip-15-gateway-implementation.md
  - refs/cips/cip-16-custom-domains-v2.md
  - refs/cips/cip-18-payments.md
  - refs/cips/cip-19-gateway-mcp-ingress.md
  - refs/cips/cip-23-tee-execution-v2.md
  - refs/cips/cip-25-cross-chain-architecture.md
  - refs/cips/cip-9-runner-storage-v2.md
  - refs/cips/cip-10-runner-containers-v2.md
  - refs/runner/2026-04-28_MPP_Session_Research.md
  - refs/plans/2026-05-06_mpp_session_implementation.md
last_updated: 2026-05-11 (r2 sync)
status: authoritative
---

# 文档-代码漂移看板

> **2026-05-11 r2 sync + 后续补 CIP** — 第一轮跨 CIP 文档 v2.r2 修订完成（CIP-9 / CIP-10 / CIP-14 / CIP-15 / CIP-16 / CIP-18 / CIP-19 / CIP-15-gateway-implementation / WP-v2 全部 r2）。第二轮起草两份新 CIP 收口剩余文档空白：
>
> - **CIP-8 (MPP Session, retroactive)** — 追认代码已实装的 SESSION_ACTOR=0x0C + 六 handler + 链下 voucher；关闭 V-11 / V-12，部分关闭 V-13
> - **CIP-17 (Verifiable State Read RPC)** — 起草 `GET_STATE` spec，关闭 V-17
> - **WP-v2 r2 加 Delta 7/8/9** — Payments (CIP-18 r2) / MCP Ingress (CIP-19) / Cross-Chain (CIP-25)，收口"白皮书空白"
> - **CIP-25 r1.1** — 加 §1.4 governance scope 段，与 WP-v2 §16.2 third-party-bridge 路线统一
> - **CIP-7 → r2 (2026-05-11，第三轮审计追加)** — Stream Key Manager system actor 地址 `0x06` → `0x12`，解 CIP-7-vs-代码 `DUAL_BASEFEE = 0x06` 长期 drift。WP-v2 Delta 6 表 + CIP-14/15/16 v2.r2 Part III §1 表 + wiki/entities/system-actors.md 同步追加 `0x12` 行；内部 storage prefix `0x6` 不变（与系统 actor 地址不同命名空间，加澄清注）
>
> 当前已收口的文档-vs-文档冲突合计：V-1 / V-11 / V-12 / V-14 / V-17 + CIP-7 全部 ✅；Merkle 描述、CIP-18↔19 互引、CIP-15 §8.12 引用错位全部就位。代码未实装项（precondition gaps V-2 / V-3 / V-4 / V-6 / V-8 / V-9 / V-10 / V-13 / V-15 / V-16）保持等待，按用户指令"代码不动"原则只调整 spec。

跟踪 `refs/` 中文档与 workspace 代码实际实现之间的不一致。

**权威文件**: [`refs/analysis/2026-04-15_documentation_amendments.md`](../analysis/2026-04-15_documentation_amendments.md) — 修正案正文与精确引用。

本页是 wiki 内的摘要看板，便于快速扫视和追踪状态。

---

## v2 对齐之后状态（2026-04-21 round 6）

CIP v2 系列（CIP-1 / 2 / 9 / 10 / 13 / 14 / 15 / 16 / 23 + WP v2）发布后，v1 漂移条目大量收敛或被显式 supersede。下表区分**已收口**、**仍活跃**、**v2 引入的 precondition gap**。

---

## 已收口（v2 对齐解决；保留为审计痕迹）

| ID | 主题 | v2 解决方式 |
|---|---|---|
| **I-1** | CIP-13 opcode 40–44 与代码 40–43 冲突 | ✅ **CIP-13 v2 §1 主分配表收口**：opcode 重排到 52–56；早期 v2 草案的 44–48 也被发现冲突（代码 44–51 全占），最终落 52+ free range |
| **N-1** | CIP-15 要求 CIP-9 新增 `GET_MANIFEST` Relay RPC | ✅ **CIP-9 v2 §2 AMEND 9-G 显式列出** + CIP-15 v2 §6.1 引用；早期 v2 草稿误把 `StorageCommitment`/`commit_manifest` 也列为 amendment（实为 CIP-9 §11.1/§12.2 已有），由 CIP-9 v2 §9 errata 修正 |
| **N-2** | CIP-15 §8.5 manifest Merkle 算法 vs CIP-9 无 normative 描述 | ✅ **CIP-9 v2 §3 pin 为 `cbfs/manifest/src/merkle.rs`**（RFC-6962-style，**非** Bitcoin-style duplicate-last-leaf）；CIP-15 v2 §6.2 引用而非重新定义 |
| **TEE-1** | CIP-23 amends CIP-2 §5.4/§9 但 CIP-2 源文未并入 | ✅ **CIP-23 v2 §3.8/§3.9 仍为 amendment 形式**（CIP-2 source 未改），但 **CIP-2 v2 §2 配套加入 DnsTxtRecordMatch / DnsCnameMatch verifier check**（AMEND 2-A/B），三层 chain（manifest entitlement / job spec / measurement_binding）由 CIP-23 v2 §1 显式说明 |
| **L-6** | CIP-14 `RouteRegistration` vs CIP-16 `DomainBinding` schema 差异 | ✅ **CIP-16 v2 §3.1 给出显式迁移规则**：legacy records 默认 `namespace_kind=COWBOY_NETWORK, status=ACTIVE` 等，一次性 schema upgrade |

---

## 仍活跃漂移

### 高严重性（5）

| ID | 主题 | 现状 |
|---|---|---|
| A-1 | `BLOCK_CYCLES_TARGET` 10M vs 20M | ✅ 修正案已发布；CIP-3 顶部 banner |
| A-2 | `BLOCK_CELLS_TARGET` 500K vs 4M | ✅ 同上 |
| A-3 | Basefee 公式（α=8 / 简化线性 / ALPHA=96）| ✅ 同上 |
| B | System Actor 地址表 0x01-0x0B | ✅ CIP-2 顶部 banner；workspace CLAUDE.md 待更新 |
| C | Runner stake 公式（1.5× vs 10×）| ✅ CIP-2 顶部 banner |

### 中严重性（9）

| ID | 主题 | 现状 |
|---|---|---|
| A-4 | Transfer 成本（21K/0 → 5K/500）| ✅ CIP-3 顶部 banner |
| D | VerificationMode 4 → 6 variants | ✅ CIP-2 顶部 banner |
| E-1 | Timer 块内顺序 Tx-then-Timer | ✅ **CIP-5 revised §5.1 已 native 化**；CIP-1 v1 §3 step 4 反向描述被 supersede；不再需要 amendment caveat |
| E-2 | CIP-5 Globalbox EOB 未实现 | ✅ CIP-5 顶部 banner（v9 auction 仍 future） |
| F | Address ETH-style 已落地 | ✅ ADDRESS_MIGRATION 提案标 ✅已实施 |
| G-1 | Token hook 50K 为阶段 1 声明未扣费 | ✅ CIP-20 顶部 banner |
| G-2 | Runner stake 两层门槛（10K/50K）| ✅ Entitlement 顶部 banner；DOCUMENTATION.md 3 处已修 |
| H-1/H-2/H-3 | Runner 文档 API 漂移 | ✅ runner/DOCUMENTATION.md 4 处已修 |
| M-1 / M-4 | VerificationMode schema / CallbackInfo.actor 格式 | ✅ 修正案 §六·补³ 补齐 |

### 低严重性（5）

| ID | 主题 | 现状 |
|---|---|---|
| L-1 | Timer 预算未在 runner 文档说明 | 修正案记录 |
| L-2 | 默认端口表缺失（RPC 4000 / indexer 8080）| 修正案记录 |
| L-3 | pvm/01 过时警告缺权威源链接 | 修正案记录 |
| L-4 | CIP-12 `SystemActorUpgrade` Payload vs opcode 43 `UpgradeActor` 关系未明确 | ⚠️ 实现阶段裁决 |
| L-5 | 块时间假设不一致（CIP-14 v1 = 1s / CIP-23 v2 = 500ms / **CIP-11 r1.1 = 5s**）| ⚠️ 三方 spec 假设不同；与 `refs/plans/block-time-500ms-to-1000ms.md` 耦合。**CIP-11 r1.1 (2026-05-11)** §13 已加块时间 disclaimer：wall-clock 数值（~12h / ~21min / ~85min）权威，raw block counts 是导出；governance 激活前需按实际块时间 rescale|

---

## v2 系列引入的 precondition gap（v2 spec 已就位，等待代码跟进）

这些不是文档与文档之间的漂移，而是**v2 spec 与代码的 gap** —— v2 文档已显式标为 precondition，代码尚未跟进。激活相应 v2 协议前需在代码侧补齐。

### 高严重性（4）

| ID | 主题 | 状态 |
|---|---|---|
| **V-1** | System actor `0x0D` / `0x0E` / `0x0F` (CIP-14 v2.r2) / `0x10` (CIP-10 v2.r2) / `0x11` (CIP-18 r2) 在 `node/runner/src/system_actors.rs` 尚未存在 | ⚠️ v2 协议 precondition；激活前需 5 个 const + 同步 workspace CLAUDE.md。**2026-05-11 r2 重排已落 doc**：代码已实装到 `0x0C = SESSION_ACTOR`；v2 CIP 系列后移 +1 到 `0x0D-0x11` |
| **V-2** | Entitlement registry 缺 `ingress.http` (CIP-14 v2) / `ingress.static` (CIP-15 v2) / `dns.attach_external` (CIP-16 v2) | ⚠️ `node/types/src/registry.rs:35-219` 实际 **15 entries**（之前 wiki 写 14 错）；需变 18 entries 才能激活；与 V-15 合并计累计需 +6 entries（加 `ingress.mcp` / `payment.gate` / `bridge.facilitate.evm`）|
| **V-3** | Opcodes 52–67 (CIP-13/14/15/16/23 v2) 在 `node/types/src/execution.rs` 尚未存在 | ⚠️ 代码 0–51 已分配；52+ 是 v2 主分配表的 free range；激活前补 16 个 const + Encode/Decode 实现 |
| **V-4** | Receipt Registry (`0x0F`，r2 后移) 单全局 prune 循环未在 storage layer 实装 | ⚠️ CIP-14 v2.r2 §8 spec；替代 v1 SDK-conventional `_http/results/{id}` 模式 |

### 中严重性（4）

| ID | 主题 | 状态 |
|---|---|---|
| **V-5** | WP §9 line 704 `0x0A = Container Image Registry` 与代码 `STORAGE_MANAGER (CIP-9)` 冲突 | ⚠️ WP-v2.r2 §13 / Delta 6 修正：0x0A 归 STORAGE_MANAGER，**0x10** 归 Container Registry（CIP-10 v2.r2 后移）|
| **V-6** | `CANONICAL_TEE_TYPES` 缺 `nitro`（`registry.rs:211` 当前 `["sgx", "sev", "tdx"]`）| ⚠️ CIP-23 v2 §2 precondition；一行代码改动 |
| **V-7** | CIP-23 Part I §3.6.2 仍说 opcodes 50-53 | ⚠️ 设计内（Part I 原文逐字）；Part II §4 已显式 supersede 到 57-60；阅读时按冲突规则取 Part II |
| **V-8** | CIP-5 timer per-fire fee_payer 模型 (`max_cost` 预扣 + 退还) 是否已在代码实装 | ⚠️ CIP-5 revised 2026-04-20 spec 明确；代码侧需核 `pvm_host.rs` 的 schedule_timer_ex 是否已含 fee_payer 字段；如未实装是 V-8 工作项 |

### 低严重性（2）

| ID | 主题 | 状态 |
|---|---|---|
| **V-9** | SettlementConfig `target_pool` 6 enum 变体在代码中尚未存在 | ⚠️ CIP-14 v2 Part III §6 canonical；需扩 `UpdateSettlementConfig` schema 加 discriminant |
| **V-10** | `EXTERNAL_REVERIFY_FEE` 治理 governance-set 默认值未拍板 | ⚠️ CIP-16 v2 §5.8 留 governance-set；激活前需治理选定数值 |

---

## CIP-18 / CIP-19 入库引入的 precondition gap（2026-05-11 新增）

CIP-18 (Payments) + CIP-19 (Gateway MCP Ingress) 是 Draft，spec 已自洽；代码尚未跟进，且 CIP-18 §22 地址段沿用 CIP-14 v1 numbering，需在主表对齐前澄清。

### 高严重性（2）

| ID | 主题 | 状态 |
|---|---|---|
| **V-14** ✅ | CIP-18 PaymentGate 地址段对齐 v2 主表 | **已收口** (2026-05-11 r2)：CIP-18 r2 把 `PAYMENT_GATE_ADDRESS` 从 `0x0013` 后移到 `0x11`，§22 rationale 同步重写。CIP-14 v2.r2 / CIP-10 v2.r2 / CIP-15 v2.r2 / CIP-16 v2.r2 / WP-v2.r2 一起完成 +1 后移以为 `SESSION_ACTOR = 0x0C`（code）让位 |
| **V-15** | Entitlement registry 缺 `payment.gate` (CIP-18) / `ingress.mcp` (CIP-19) / `bridge.facilitate.evm` (CIP-18 deferred) | ⚠️ `node/types/src/registry.rs:35-219` 当前 **15 entries**（之前 wiki 误写 14）；CIP-14/15/16 v2 已要 +3（V-2）；CIP-18/19 再 +3 → 共 +6 entries → 目标 21 entries 才能激活整套 ingress + payment 协议栈 |

### 中严重性（2）

| ID | 主题 | 状态 |
|---|---|---|
| **V-16** | CIP-15 `pays = "caller"` 字段依赖 CIP-18 PaymentGate | ⚠️ CIP-15 gateway-implementation §5 Phase 4 描述 — CIP-18 未实装时建议 Gateway 返回 `501 Not Implemented` + `X-Cowboy-Reason: cip18-required`；CIP-15 v2 schema 已含 `pays` 字段（precondition），但实装 Phase 4 必须等 CIP-18 落地 |
| **V-17** ✅ | CIP-19 `tools/list` + CIP-15 v2.r2 routes 缓存依赖 `GET_STATE` RPC | **已收口** (2026-05-11 CIP-17)：起草 CIP-17 (Verifiable State Read RPC)，单 KV + Merkle proof，实现 < 200 行。CIP-15 gateway-implementation r2 §2.2 / §9 open-question 1 + CIP-19 §10.1 step 1 现都指向 CIP-17 |

---

## MPP Session（2026-05-07 提出，2026-05-11 r2 重新框定）

`refs/runner/2026-04-28_MPP_Session_Research.md` + `refs/plans/2026-05-06_mpp_session_implementation.md` 当时被定为"研究/PoC 提案"。**审计代码发现**：`node/runner/src/system_actors.rs:35` `SESSION_ACTOR = 0x0C` + `node/types/src/session.rs` / `session_eip712.rs` / `node/execution/src/runner/session.rs` / `runner/crates/runner-common/src/voucher.rs` 全栈已 commit。**代码先到先得**，因此 r2 选择让 CIP-14 v2 / CIP-10 v2 / CIP-18 整体后移 +1，而非要求 MPP Session 改地址。

| ID | 主题 | 状态 |
|---|---|---|
| **V-11** ✅ | MPP Session `SESSION_ACTOR = 0x0C` 与 CIP-14 v2 ROUTE_REGISTRY = 0x0C 冲突 | **已收口** (2026-05-11 r2)：代码已实装 `0x0C = SESSION_ACTOR`；CIP-14 v2.r2 接受并后移 ROUTE_REGISTRY 到 `0x0D`。后续 follow-up：起 CIP 草案（暂称 CIP-2X）把 SESSION_ACTOR 正式纳入主表 |
| **V-12** ✅ | MPP Session 提议 opcodes 52-57 与 CIP-13 v2 / CIP-23 v2 numeric 段冲突 | **已收口** (2026-05-11 CIP-8)：代码 `node/types/src/execution.rs` SystemInstruction 是 Rust enum，MPP Session handlers 是 ActorMessage to SESSION_ACTOR + 字符串 selector（`session.open` / `.deposit` / `.settle` / `.close` / `.finalize` / `.slash`），**不占用 numeric opcode 空间**。CIP-8 §12 给完整说明。如未来 SystemInstruction 引入 numeric 映射，MPP Session 占 ≥68 free range |
| **V-13** | EIP-712 `domain.chainId` 来源 | ⚠️ PoC：`runner/crates/runner-common/src/voucher.rs:28` `COWBOY_SESSION_CHAIN_ID = 1`；激活 mainnet 前需选定来源（CIP-8 §13 给激活规则；待 `node/types/src/constants.rs` 落 `CHAIN_ID` 常量 / 或起 sibling CIP "Cowboy network identifier"）|

---

## 监控维度

在 lint 时扫描这些线索，发现新漂移时追加到修正案：

1. 代码常量变更（`node/types/src/constants.rs`、`execution.rs`、`basefee.rs`、`gas.rs`）
2. 新枚举 variant（`VerificationMode`、`SystemInstruction`、`ActorInstruction`）
3. CIP 修订（`refs/cips/` 中 `Revised:` 字段，含 v2 系列 alignment 文档）
4. 白皮书更新（`refs/whitepaper/` — 受保护，只读对比）
5. 新 System Actor（`node/runner/src/system_actors.rs`）
6. 新 SystemInstruction opcode（`node/types/src/execution.rs:482-541`）—— 任何新增需对照本表 V-3
7. 新 Entitlement registry entry（`node/types/src/registry.rs:208`）—— v2/CIP-18/19 累计 +6 待加

---

## 更新流程

当发现新漂移：
1. 验证代码侧实际值
2. 追加条目到 `refs/analysis/2026-04-15_documentation_amendments.md`（或当月新修正案）
3. 在受影响的 CIP / raw source 顶部加 Warning banner 指向修正案
4. 本文件（`drift.md`）追加条目到对应严重性区
5. `wiki/log.md` append `## [YYYY-MM-DD] lint | <摘要>`
6. 相关 `wiki/parameters.md` / concept 页同步更新

---

## 相关
- [[parameters]] — 参数权威表（漂移修复后的结果在此）
- [[entities/system-actors]] — 0x01-0x0F 地址权威
- [`refs/analysis/2026-04-15_documentation_amendments.md`](../analysis/2026-04-15_documentation_amendments.md) — 修正案正文
