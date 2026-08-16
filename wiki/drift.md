---
type: comparison
tags: [drift, consistency, audit]
sources:
  - refs/analysis/2026-04-15_documentation_amendments.md
  - refs/analysis/2026-05-15_CIP_IMPLEMENTATION_AUDIT.md
  - refs/analysis/2026-05-26_CIP_IMPLEMENTATION_AUDIT.md
  - refs/cips/cip-9-runner-storage.md
  - refs/cips/cip-10-runner-containers.md
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-15-public-asset-hosting.md
  - refs/cips/cip-15-gateway-implementation.md
  - refs/cips/cip-16-custom-domains.md
  - refs/cips/cip-18-payments.md
  - refs/cips/cip-19-gateway-mcp-ingress.md
  - refs/cips/cip-23-tee-execution.md
  - refs/cips/cip-24-secrets-manager.md
  - refs/cips/cip-25-cross-chain-architecture.md
  - refs/cips/cip-28-cowboy-agent-banking.md
  - refs/cips/cip-29-on-chain-event-hooks-en.md
  - refs/runner/2026-04-28_MPP_Session_Research.md
  - refs/plans/2026-05-06_mpp_session_implementation.md
last_updated: 2026-08-15 (系统 actor 地址段按代码 pin 测试整段校正，见顶部 banner；前值 2026-05-26 v2.r2 audit)
status: authoritative
---

# 文档-代码漂移看板

> **2026-08-15 系统 actor 地址段代码校正** — 发现整个 wiki 的系统 actor 地址表落后于代码：wiki 忠实镜像 2026-05-11 CIP v2.r2 spec 序列，但**代码最终落位整体后移**——`0x0D` 被 CIP-7 `STREAM_KEY_MANAGER` 占用、`0x11` 被 CIP-11 `VALIDATOR_SET` 占用，导致 `ROUTE_REGISTRY 0x0D→0x0E` / `GATEWAY 0x0E→0x0F` / `RECEIPT 0x0F→0x10` / `PAYMENT_GATE 0x11→0x12` / `CONTAINER 0x10→0x13`；另 spec 未记的 `INTENT_SETTLEMENT 0x14` / `BANK_ACTOR 0x16` / `STREAM_REGISTRY 0x17` / `TRADING_POST 0x1E` 已在代码。**权威来源 = `runner/src/system_actors.rs` 的 `well_known_low_byte_assignments` pin 测试**。已校正：`wiki/entities/system-actors.md`（全表重写）、`wiki/parameters.md`、`wiki/concepts/payments.md`、`wiki/concepts/public-asset-hosting.md`、`wiki/concepts/{dns-addressable-actors,custom-domains,verifiable-state-read}.md`、`wiki/entities/{gateway,route-registry}.md`、`wiki/index.md`。
>
> **2026-08-16 续查 CIP 规格正文** — 结论反转:**权威规格 `cowboy/docs/cips/` 已全部与代码对齐**（CIP-7 SKM=`0x0D`、CIP-14 ROUTE=`0x0E`/GATEWAY=`0x0F`、CIP-18 PaymentGate=`0x12`、CIP-10 Container=`0x13`、CIP-28 BankActor=`0x16` r1.2）。落后的是 **`refs/cips/` 这份镜像快照**（不止地址——CIP-7 差 ~860 行、CIP-10 ~376、CIP-28 落后一个修订 r1.1 vs r1.2）。因整份是过时快照而非仅地址错，已给 `refs/cips/{cip-7,cip-10,cip-14,cip-16,cip-18,cip-28,cip-28-zh}.md` 顶部加 **STALE SNAPSHOT 横幅**指向 `cowboy/docs/` 权威版 + 标注正确地址，未逐行改写正文（避免制造虚假「已维护」表象）。**残余（未改，刻意保留）**：受保护白皮书仍用 "Steamtrain" 旧名（已在 CIP-9 顶部加 Steamtrain→CBFS 术语注）；`refs/cips/` 正文的其它内容陈旧以横幅告知，权威在 `cowboy/docs/`。

> **2026-05-26 implementation audit** — 新一轮 CIP + WP 代码完成度审计已完成（见 [`refs/analysis/2026-05-26_CIP_IMPLEMENTATION_AUDIT.md`](../analysis/2026-05-26_CIP_IMPLEMENTATION_AUDIT.md)，作为新 baseline 取代 5/15 audit）。**最显著两项进展**：CIP-24（CBSS）从未列入 audit → 🟢 ~80%（41K 行代码 + 21 handlers）；CIP-29（事件钩子）从 ❌ <5% → 🟢 ~55%（`0x1D` 虚拟 actor + Phase 1/2 框架）。整体平均完成度 ~40% → ~45%。

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
| **C-1 (2026-05-26)** | CIP-28 BankActor `0x0D` ↔ CIP-14 v2.r2 `ROUTE_REGISTRY = 0x0D` 双占 | ✅ **CIP-28 r1.1 把 BankActor 移到 `0x13`**（CIP-7 r2 `STREAM_KEY_MANAGER = 0x12` 之后首个空位，仍属 spec-only 段）；WP-v2 §13 系统 actor 表同步加状态列；CIP-12 / CIP-2 范围声明改为"代码 0x01-0x0C + 虚拟 0x1D + spec 0x0D-0x13"三段式 |
| **C-2 (2026-05-26)** | CIP-29 spec §2.6 声称 `EVENT_SUBSCRIPTION_SYSTEM_ACTOR = 0x0A` ↔ 代码实际 `0x1D`（且 `0x0A` 在代码里是 `STORAGE_MANAGER`）| ✅ **CIP-29 中英版本 §2.6 同步代码权威 `0x1D`**（`node/types/src/constants.rs:156`），并加 host-interception pattern 说明：`0x1D` 是虚拟系统 actor，由 `pvm_host::call_actor` 拦截路由到 `event_sub_system_actor::dispatch_rpc`，不部署 actor 代码 |
| **C-3 (2026-05-26)** | CIP-13 v2 §1 master opcode 表与代码完全 drift（master 表声称 52-56=CIP-13 delegation / 57-60=CIP-23 / 61-64=CIP-10 v2 容器，**代码里 52-57=CIP-8 Session / 60-63=CIP-24 TEE keys / 85-86=CIP-9 DrainRelay**）| ✅ **CIP-13 v2 §1 主表整体重写为代码权威视角**：明确标出已在代码的所有 SYS_* opcode（0-51 / 52-57 Session / 60-63 TEE keys / 68-84 CBSS / 85-86 DrainRelay），把 CIP-13 / CIP-23 v2 / CIP-10 v2 / CIP-14 v2 / CIP-28 等未实装的 v2 提案统一列入"aspirational allocations, pending renumber to ≥87"段；CIP-24 §3.3 末段恢复成"60-63 in code"|
| **C-4 (2026-05-26)** | "Code ahead of spec"：代码已实装 `SubmitDrainRelayProposal=85` / `SubmitAutoDrainPolicyProposal=86`（治理-触发的 relay 排水 + 自动排水策略），但 CIP-9 文档无对应规范 | ✅ **CIP-9 Part II 新增 §13 (AMEND 9-J)**：§13.2 列出 `ProposalPayloadKind` 扩展；§13.3 / §13.4 分别规范两条指令的 wire 格式、前置条件、submit-time effect、execute-time effect（通过 `ExecuteProposal=47` 路由）；§13.4 完整列出 `AutoDrainPolicyConfig` 10 个字段语义 + 5 条 validator 规则；§13.5 标出与 CIP-12 / CIP-13 / CIP-9 §5.7 / CIP-31 的 cross-reference |

---

## 仍活跃漂移

### 高严重性（5）

| ID | 主题 | 现状 |
|---|---|---|
| A-1 | `BLOCK_CYCLES_TARGET` 10M vs 20M | ✅ 修正案已发布；CIP-3 顶部 banner |
| A-2 | `BLOCK_CELLS_TARGET` 500K vs 4M | ✅ 同上 |
| A-3 | Basefee 公式（α=8 / 简化线性 / ALPHA=96）| ✅ 同上 |
| B | System Actor 地址表 0x01-0x0B | ✅ CIP-2 顶部 banner（2026-05-26 扩至 `0x01-0x13`，同步 CIP-12 / WP-v2 §13）；workspace CLAUDE.md 待更新 |
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
| L-5 | 块时间假设不一致（CIP-14 v1 = 1 s / CIP-23 v2 = 500 ms / CIP-11 r1.1 = 5 s）| ✅ **2026-05-26 全部统一到 1 s** — CIP-11 r1.2 §13 常量按 ×5 rescale 并移除 5 s disclaimer；CIP-23 r1 §3.13 块数按 ×0.5 rescale（`MAX_QUOTE_AGE` 150→75 blocks ≈75 s @ 1 s；`BINDING_RENEWAL_PERIOD` 7 天 = 604,800 blocks @ 1 s，原 12,096 ≈ 7 days @ 500 ms 已勘正为算术错误）；CIP-14 v1 / WP-v2 §6.1 本就为 1 s 无需改 |

---

## v2 系列引入的 precondition gap（v2 spec 已就位，等待代码跟进）

这些不是文档与文档之间的漂移，而是**v2 spec 与代码的 gap** —— v2 文档已显式标为 precondition，代码尚未跟进。激活相应 v2 协议前需在代码侧补齐。

### 高严重性（4）

| ID | 主题 | 状态 |
|---|---|---|
| **V-1** | System actor `0x0D` / `0x0E` / `0x0F` (CIP-14 v2.r2) / `0x10` (CIP-10 v2.r2) / `0x11` (CIP-18 r2) / `0x12` (CIP-7 r2) / `0x13` (CIP-28 r1.1) 在 `node/runner/src/system_actors.rs` 尚未存在 | ⚠️ v2 协议 precondition；激活前需 7 个 const + 同步 workspace CLAUDE.md，**或**采用 CIP-29 `0x1D` 那种 `pvm_host::call_actor` 拦截模式。代码已实装：`0x01-0x0C` 部署型 + `0x1D = EVENT_SUBSCRIPTION_SYSTEM_ACTOR`（虚拟，`node/types/src/constants.rs:156`）|
| **V-2** | Entitlement registry 缺 `ingress.http` (CIP-14 v2) / `ingress.static` (CIP-15 v2) / `dns.attach_external` (CIP-16 v2) | ⚠️ `node/types/src/registry.rs:35-219` 实际 **15 entries**（之前 wiki 写 14 错）；需变 18 entries 才能激活；与 V-15 合并计累计需 +6 entries（加 `ingress.mcp` / `payment.gate` / `bridge.facilitate.evm`）|
| **V-3** | CIP-13 v2 delegation handlers / CIP-23 v2 attestation handlers (`VerifyCae` 等) / CIP-10 v2 容器治理 / CIP-14 v2 `IngressDispatch` / CIP-16 v2 `ExternalDomainCallback` 等在 `node/types/src/execution.rs` 尚未存在 | ⚠️ **2026-05-26 复核**：代码已实装 0-51（core） + **52-57 CIP-8 Session** + **60-63 CIP-24 TEE keys** + **68-84 CIP-24 主分配** + **85-86 CIP-9 DrainRelay**。原 master table 把 52-67 全划给上述 v2 提案是 spec 单方面 wishful，与代码实际占用冲突；激活时这批未实装提案必须改到 ≥ 87 free range。CIP-13 §1 主表已重写为代码权威视角并明确列出 aspirational allocations |
| **V-4** | Receipt Registry (`0x0F`，r2 后移) 单全局 prune 循环未在 storage layer 实装 | ⚠️ CIP-14 v2.r2 §8 spec；替代 v1 SDK-conventional `_http/results/{id}` 模式 |

### 中严重性（4）

| ID | 主题 | 状态 |
|---|---|---|
| **V-5** | WP §9 line 704 `0x0A = Container Image Registry` 与代码 `STORAGE_MANAGER (CIP-9)` 冲突 | ⚠️ WP-v2.r2 §13 / Delta 6 修正：0x0A 归 STORAGE_MANAGER，**0x10** 归 Container Registry（CIP-10 v2.r2 后移）|
| **V-6** | `CANONICAL_TEE_TYPES` 缺 `nitro`（`registry.rs:211` 当前 `["sgx", "sev", "tdx"]`）| ⚠️ CIP-23 v2 §2 precondition；一行代码改动 |
| **V-7** | CIP-23 Part I §3.6.2 仍说 opcodes 50-53；Part II §4 把它改为 57-60 也仍与代码冲突 | ⚠️ **2026-05-26 复核**：代码 57 = `SessionSlash`（CIP-8），60-63 = `RegisterTeeTrustedKey` 等（CIP-24 TEE keys）。CIP-23 v2 自己的 `VerifyCae` / `UpdateCpuRoot` / `UpdateNrasRoot` / `GcNonces` 一概**未实装**，激活时需重新落到 ≥ 87 free range（与 V-3 合并跟踪）|
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
