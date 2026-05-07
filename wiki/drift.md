---
type: comparison
tags: [drift, consistency, audit]
sources:
  - refs/analysis/2026-04-15_documentation_amendments.md
  - refs/cips/cip-13-runner-delegation-v2.md
  - refs/cips/cip-14-dns-addressable-actors-v2.md
  - refs/cips/cip-15-public-asset-hosting-v2.md
  - refs/cips/cip-16-custom-domains-v2.md
  - refs/cips/cip-23-tee-execution-v2.md
  - refs/cips/cip-9-runner-storage-v2.md
  - refs/cips/cip-10-runner-containers-v2.md
  - refs/runner/2026-04-28_MPP_Session_Research.md
  - refs/plans/2026-05-06_mpp_session_implementation.md
last_updated: 2026-05-07
status: authoritative
---

# 文档-代码漂移看板

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
| L-5 | 块时间假设不一致（CIP-14 1s / CIP-23 500ms）| ⚠️ 与 `refs/plans/block-time-500ms-to-1000ms.md` 耦合 |

---

## v2 系列引入的 precondition gap（v2 spec 已就位，等待代码跟进）

这些不是文档与文档之间的漂移，而是**v2 spec 与代码的 gap** —— v2 文档已显式标为 precondition，代码尚未跟进。激活相应 v2 协议前需在代码侧补齐。

### 高严重性（4）

| ID | 主题 | 状态 |
|---|---|---|
| **V-1** | System actor `0x0C` / `0x0D` / `0x0E` (CIP-14 v2) / `0x0F` (CIP-10 v2) 在 `node/runner/src/system_actors.rs` 尚未存在 | ⚠️ v2 协议 precondition；激活前需 4 个 const + 同步 workspace CLAUDE.md |
| **V-2** | Entitlement registry 缺 `ingress.http` (CIP-14 v2) / `ingress.static` (CIP-15 v2) / `dns.attach_external` (CIP-16 v2) | ⚠️ `node/types/src/registry.rs:208` 当前 14 entries；需变 17 entries 才能激活 |
| **V-3** | Opcodes 52–67 (CIP-13/14/15/16/23 v2) 在 `node/types/src/execution.rs` 尚未存在 | ⚠️ 代码 0–51 已分配；52+ 是 v2 主分配表的 free range；激活前补 16 个 const + Encode/Decode 实现 |
| **V-4** | Receipt Registry (`0x0E`) 单全局 prune 循环未在 storage layer 实装 | ⚠️ CIP-14 v2 §8 spec；替代 v1 SDK-conventional `_http/results/{id}` 模式 |

### 中严重性（4）

| ID | 主题 | 状态 |
|---|---|---|
| **V-5** | WP §9 line 704 `0x0A = Container Image Registry` 与代码 `STORAGE_MANAGER (CIP-9)` 冲突 | ⚠️ WP-v2 Part II Delta 6 提议修正：0x0A 归 STORAGE_MANAGER，0x0F 归 Container Registry |
| **V-6** | `CANONICAL_TEE_TYPES` 缺 `nitro`（`registry.rs:211` 当前 `["sgx", "sev", "tdx"]`）| ⚠️ CIP-23 v2 §2 precondition；一行代码改动 |
| **V-7** | CIP-23 Part I §3.6.2 仍说 opcodes 50-53 | ⚠️ 设计内（Part I 原文逐字）；Part II §4 已显式 supersede 到 57-60；阅读时按冲突规则取 Part II |
| **V-8** | CIP-5 timer per-fire fee_payer 模型 (`max_cost` 预扣 + 退还) 是否已在代码实装 | ⚠️ CIP-5 revised 2026-04-20 spec 明确；代码侧需核 `pvm_host.rs` 的 schedule_timer_ex 是否已含 fee_payer 字段；如未实装是 V-8 工作项 |

### 低严重性（2）

| ID | 主题 | 状态 |
|---|---|---|
| **V-9** | SettlementConfig `target_pool` 6 enum 变体在代码中尚未存在 | ⚠️ CIP-14 v2 Part III §6 canonical；需扩 `UpdateSettlementConfig` schema 加 discriminant |
| **V-10** | `EXTERNAL_REVERIFY_FEE` 治理 governance-set 默认值未拍板 | ⚠️ CIP-16 v2 §5.8 留 governance-set；激活前需治理选定数值 |

---

## MPP Session 研究 / 计划与 v2 主表冲突（2026-05-07 新增）

`refs/runner/2026-04-28_MPP_Session_Research.md` + `refs/plans/2026-05-06_mpp_session_implementation.md` 是研究 / PoC 实施阶段的提案，未走 v2 alignment round 6。其提议的地址 / opcode 与 v2 主表全段冲突，激活前必须重排。

| ID | 主题 | 状态 |
|---|---|---|
| **V-11** | MPP Session 提议 `SESSION_ACTOR = 0x0C` 撞 CIP-14 v2 `ROUTE_REGISTRY = 0x0C` | ⚠️ 研究 2026-04-28 + 计划 2026-05-06 提议；**实施前必须改地址**（建议 ≥`0x10`）+ 起 CIP 草案纳入主表 |
| **V-12** | MPP Session 提议 opcodes 52-57（OpenSession / Deposit / Settle / Close / Finalize / Slash）撞 CIP-13 v2 (52-56) + CIP-23 v2 (57) | ⚠️ 同上；建议 PoC 阶段使用临时本地常量，正式合并前重排到 ≥68 |
| **V-13** | EIP-712 `domain.chainId` 来源未明 | ⚠️ 计划 §10 待澄清；查 `node/types/src/constants.rs` 或 validator 配置；激活前需选定来源 |

---

## 监控维度

在 lint 时扫描这些线索，发现新漂移时追加到修正案：

1. 代码常量变更（`node/types/src/constants.rs`、`execution.rs`、`basefee.rs`、`gas.rs`）
2. 新枚举 variant（`VerificationMode`、`SystemInstruction`、`ActorInstruction`）
3. CIP 修订（`refs/cips/` 中 `Revised:` 字段，含 v2 系列 alignment 文档）
4. 白皮书更新（`refs/whitepaper/` — 受保护，只读对比）
5. 新 System Actor（`node/runner/src/system_actors.rs`）
6. 新 SystemInstruction opcode（`node/types/src/execution.rs:482-541`）—— 任何新增需对照本表 V-3

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
