# Cowboy 平台代码完成度审计报告（2026-05-26）

**审计日期**：2026-05-26
**前次基线**：[`2026-05-15_CIP_IMPLEMENTATION_AUDIT_CN.md`](./2026-05-15_CIP_IMPLEMENTATION_AUDIT_CN.md)（11 天前并行 9 代理审计）
**审计范围**：
- **白皮书**：`refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md` (v2.r2)
- **CIP 文档**：`refs/cips/` 30 篇（cip-1 到 cip-31，含 cip-15-gateway-implementation；cip-27/30 未起草）
- **代码**：[`cowboyinc/node`](https://github.com/cowboyinc/node)、[`cowboyinc/runner`](https://github.com/cowboyinc/runner)、[`cowboyinc/cbss`](https://github.com/cowboyinc/cbss)、[`cowboyinc/cbfs`](https://github.com/cowboyinc/cbfs) 四个仓库的 `main` 分支

**审计方法**：以 5/15 audit 为 baseline，叠加 2026-05-26 spec ↔ code 大对齐过程中对各代码仓的探针发现（详见 `wiki/log.md` 5/26 enhance/lint 条目）+ 本会话 6 个并行子代理对 30 篇 CIP × 4 仓代码的逐项 grep。状态有变更的 CIP 给出精确证据；状态不变的复用 5/15 audit 结论并标注 "5/15 audit baseline"。

**标记图例**：✅ ≥85% / 🟢 60-85% / 🟡 25-60% / 🟠 5-25% / ❌ <5% / ⚠️ 存在偏差

---

## 目录

- [零、白皮书架构基线（WP v2.r2）](#零白皮书架构基线wp-v2r2)
- [一、自 5/15 audit 的关键变化](#一自-515-audit-的关键变化)
- [二、总览矩阵（2026-05-26 现状）](#二总览矩阵2026-05-26-现状)
- [三、按 CIP 详细分析](#三按-cip-详细分析)
  - [3.1 Actor 与计算层（CIP-1/2/6）](#31-actor-与计算层cip-126)
  - [3.2 存储与文件系统（CIP-4/9/31）](#32-存储与文件系统cip-4931)
  - [3.3 Runner 系统（CIP-10/11/13）](#33-runner-系统cip-101113)
  - [3.4 网络与会话（CIP-7/8/15/19）](#34-网络与会话cip-781519)
  - [3.5 寻址与治理（CIP-5/12/14/16/17）](#35-寻址与治理cip-51214161-7)
  - [3.6 金融与代币（CIP-3/18/20/21/22/26/28）](#36-金融与代币cip-31820212226-28)
  - [3.7 高级特性（CIP-23/24/25/29）](#37-高级特性cip-232425-29)
- [四、横切发现](#四横切发现)
- [五、Node 仓代码资产盘点](#五node-仓代码资产盘点)
- [六、风险与优先级建议](#六风险与优先级建议)
- [七、白皮书创世参数 vs 代码逐项核对](#七白皮书创世参数-vs-代码逐项核对)
- [八、白皮书 Part II 九个 Delta 实现状态](#八白皮书-part-ii-九个-delta-实现状态)
- [九、与 5/15 audit 不变项](#九与-515-audit-不变项)
- [十、结语](#十结语)

---

## 零、白皮书架构基线（WP v2.r2）

白皮书 `2026-03-21_cowboy-technical-whitepaper-revised-v2.md` 是顶层规范文档，分三部分：

| 部分 | 内容 | 状态 |
|---|---|---|
| **Part I** | v1 原文（17 章 + 附录 A），含 §9 系统 actor 表、§13 创世参数表、§17 完整费用模型 | 当前规范（canonical） |
| **Part II** | 9 个 Delta（CIP-14/15/16 对齐练习涌现的前瞻提案） | 提案，部分已采纳 |
| **Part III** | WP vs CIP 一致性审计简报 | 一次性审计，非规范 |

**冲突规则**：Part I 当前权威；Part II 一旦采纳即覆盖 Part I 对应部分；Delta 6（§9 系统 actor 表修正）已在 v2.r2 纳入。

### 0.1 WP 描述的核心架构

WP **Abstract** + **Architectural Overview** 明确平台四大支柱：

1. **Deterministic Python Actors** — 确定性 PVM（Python 3.11.8）、reentrancy ≤32、内存 10 MiB、模块白名单
2. **Native Timers & Scheduler** — 分层日历队列 + GBA + 同块惩罚 + per-actor 上限 1,024
3. **Verifiable Off-Chain Compute** — Runner 市场、VRF 选举、commit-reveal、6 种验证模式
4. **Dual-Metered Gas** — Cycles + Cells 独立 EIP-1559 市场

### 0.2 WP §9 系统 Actor 表 vs 代码（含 5/26 新增 0x1D）

| 地址 | WP §9 (v2.r2 修订后) | 代码实际 | 状态 |
|---|---|---|---|
| 0x01 | Runner Registry | `RUNNER_REGISTRY` | ✅ 一致 |
| 0x02 | Job Dispatcher | `JOB_DISPATCHER` | ✅ 一致 |
| 0x03 | Result Verifier | `RESULT_VERIFIER` | ✅ 一致 |
| 0x04 | Secrets Manager (CBSS) | `SECRETS_MANAGER` | ✅ 一致（CIP-24 落地） |
| 0x05 | TEE Verifier | `TEE_VERIFIER` | ✅ 一致 |
| 0x06 | DualBasefee | `BASEFEE_SYSTEM_ACTOR` | ✅ 一致 |
| 0x07 | Entitlement Registry | `ENTITLEMENT_REGISTRY` | ✅ 一致 |
| 0x08 | Treasury | `TREASURY` | ✅ 一致 |
| 0x09 | Governance | `GOVERNANCE_SYSTEM_ACTOR` | ✅ 一致 |
| **0x0A** | **Storage Manager (CIP-9)** | **`STORAGE_MANAGER`** | ✅ 一致（Delta 6 修正） |
| 0x0B | Relay Registry (CIP-9) | `RELAY_REGISTRY` | ✅ 一致 |
| 0x0C | Session Actor (CIP-8) | `SESSION_ACTOR` | ✅ 一致 |
| 0x0D | Route Registry (CIP-14 v2) | 未分配 | ❌ 未实现 |
| 0x0E | Gateway Registry (CIP-14 v2) | 未分配 | ❌ 未实现 |
| 0x0F | Receipt Registry (CIP-14 v2) | 未分配 | ❌ 未实现 |
| 0x10 | Container Registry (CIP-10 v2) | 未分配 | ❌ 未实现 |
| 0x11 | Payment Gate (CIP-18 r2) | 未分配 | ❌ 未实现 |
| 0x12 | Stream Key Manager (CIP-7 r2) | 未分配 | ❌ 未实现 |
| 0x13 | Bank Actor (CIP-28) | 未分配 | ❌ 未实现 |
| **0x1D** | **Event Subscription (CIP-29，host-intercepted virtual)** | **`EVENT_SUBSCRIPTION_SYSTEM_ACTOR`** | ✅ **5/26 新增**（`constants.rs:156`） |

**5/26 关键变化**：
- `0x1D` 是协议引入的**新激活模式**——虚拟 system actor，不在 `0x01-0x0F` 保留段，由 `pvm_host::call_actor:1867-1881` 拦截路由。
- CIP-28 BankActor 从 `0x0D → 0x13`（让位 CIP-14 v2 Route Registry，5/26 drift.md C-1 收口）。
- CIP-29 EVENT_SUB 从声明的 `0x0A`（与 CIP-9 撞号）改为 `0x1D`（5/26 drift.md C-2 收口）。

### 0.3 WP §5.1a vs §5.1b — 已部署 vs 目标设计

WP §5.1 显式区分两层：

- **§5.1a（已部署）**：CIP-5 FIFO + 同高度 FIFO 桶 + per-fire `fee_payer` + `LANE_TIMER_CYCLES=2,000,000`（20% of block per CIP-3 §2.2.3）+ `TIMER_GC_CYCLES` 独立 GC lane + per-actor 1,024 上限 + 同块禁止
- **§5.1b（目标）**：CIP-1 v3 EIP-1559 timer-lane basefee + `priority_tip` + per-actor 公平权重 `W(actor) ∈ [1,2]` + 250k auction-phase cycle cap + `priority_tier_hint` SDK 枚举

**审计观察**：代码处于 §5.1a 状态，§5.1b **目标全空**（详见 §3.1）。但 §5.1a 也有一项偏差：WP 说 `LANE_TIMER_CYCLES = 2,000,000`（20% × 10M target），**代码值 `8,888,890`**——见 §七详细核对。

### 0.4 WP 直接锁定的现实

WP 文本本身（与 v2.r2 元数据）多次承认现状：

- "**CIP-9 manifest anchoring (deferred)**" — §12.2 / §17.6
- "**CIP-10 image allowlists**" — §12.2（依赖未实现的 Container Registry）
- "**ZK-Proof (v2)**" — §5 表与 §5.3，明确为 v2 未来
- "**delegation deferred to v2**" — §6 验证器集
- "**no encrypted mempool**" — §6.4 / §6.5
- "**EventListener (CIP-7, deferred)**" — §16.3

---

## 一、自 5/15 audit 的关键变化

11 天内 6 个 CIP 状态有显著变化，主要由 CBSS 大规模落地和 CIP-29 框架实装驱动：

| CIP | 5/15 状态 | 5/26 状态 | 触发证据 |
|---|---|---|---|
| **CIP-24（CBSS）** | (未列入 5/15 audit) | 🟢 **~80%** | 代码大规模落地：`node/` 中 11,600 行（`execution/src/cbss.rs:7738` + `types/src/cbss.rs:1906` + `rpc/src/handlers/cbss.rs:1956`）+ 独立 `cbss/` workspace 29,448 行（cbssd / cbss-crypto / cbss-client / cbss-types）；**21 个 SystemInstruction handlers 全在代码**（60-63 TEE keys + 68-84 CBSS main，`node/types/src/execution.rs:653-681`）；BLS12-381 阈值 IBE / DKG / proxy registry / release receipt 全栈在 |
| **CIP-29（事件钩子）** | ❌ <5% | 🟢 **~55%** | `node/types/src/constants.rs:156` `EVENT_SUBSCRIPTION_SYSTEM_ACTOR = 0x1D`；三文件 914 行：`storage/src/event_subs.rs` (410) + `execution/src/execution/event_fire.rs` (151) + `execution/src/execution/event_sub_system_actor.rs` (353)；3 read RPCs (`get_rank` / `get_topic_orderbook` / `get_min_bid_for_rank`) 在 `pvm_host::call_actor:1867-1881` 拦截路由；`EmitOrigin` DeferredTx metadata tag + `MAX_TOPIC_BYTES=64` / `MAX_EVENT_PAYLOAD_BYTES=4096` / `ASYNC_FIRES_PER_DEFER_TX=64` 常量；StatePrefix 改用 `EVENT_SUB=0x0E` / `EVENT_SUB_INDEX_VALUE=0x0F`（解开与 CIP-26 的撞号）；spec 端 §2.6 由本次审计同步对齐到 `0x1D` |
| **CIP-9** | 🟡 70% | 🟢 73% | §13 AMEND 9-J 补完：`SubmitDrainRelayProposal`(85) / `SubmitAutoDrainPolicyProposal`(86) 已在代码（`node/execution/src/execution/system_instruction.rs:747-905`），本次审计把 spec 与代码完全对齐 |
| **CIP-12** | demo 级 | 🟡 30% | `ProposalPayloadKind` 从 1 个 `UpdateBasefeeConfig` 扩到 3 个（+`DrainRelay` + `UpdateAutoDrainPolicy`，`node/runner/src/types.rs:835`）；`SubmitDrainRelayProposal`(85) / `SubmitAutoDrainPolicyProposal`(86) 通用 `ExecuteProposal`(47) 路径在 |
| **CIP-23** | 🟡 ~25% | 🟡 ~30% | TEE Verifier 支持 opcodes 60-63 已入代码（`SYS_REGISTER_TEE_TRUSTED_KEY` 等，由 CIP-24 §3.3 推动落地；CIP-23 v2 复用）；但 CAE 复合证明 / 证书链 / nonce 重放保护 / dispatcher 改用 MeasurementBinding 过滤仍缺 |
| **CIP-8** | ✅ ~90% | ✅ ~92% | 6 opcodes 52-57 全在代码确认（`SYS_SESSION_OPEN`…`SYS_SESSION_SLASH`）；**Slash 仍 stub**（`node/execution/src/runner/session.rs:371-380` 返回 `UnsupportedInstruction`，等 verifier-arbitration milestone）|

其余 24 个 CIP 状态未变（详见 §九）。

---

## 二、总览矩阵（2026-05-26 现状）

### 2.1 实现度状态分布

| 状态 | 个数 | CIPs |
|---|---:|---|
| ✅ ≥85% | 6 | CIP-2 / CIP-5 / CIP-6 / CIP-8 / CIP-20 / CIP-26 |
| 🟢 60-85% | 7 | CIP-3 / CIP-4 / CIP-9 / CIP-17 / CIP-24 / CIP-25 / CIP-29 |
| 🟡 25-60% | 2 | CIP-12 / CIP-23 |
| 🟠 5-25% | 5 | CIP-1 / CIP-7 / CIP-14 / CIP-15 / CIP-31 |
| ❌ <5% | 9 | CIP-10 / CIP-11 / CIP-13 / CIP-16 / CIP-18 / CIP-19 / CIP-21 / CIP-22 / CIP-28 |

### 2.2 全 CIP 详细矩阵

| CIP | 主题 | 进度 | 关键代码资产 / 缺口 |
|---|---|---|---|
| **CIP-1** | Actor 调度器 v3（EIP-1559 timer lane） | 🟠 ~5% | 仍仅 CIP-5 FIFO 基线；v3 分层日历队列 + GBA + 公平权重全无 |
| **CIP-2** | 链下可验证计算 v1 | ✅ ~85% | 核心骨架完整（RUNNER_REGISTRY / JOB_DISPATCHER / RESULT_VERIFIER + VRF + commit-reveal + 6 modes）；v2 DNS check / v3 机制改革缺失 |
| **CIP-3** | Cycles+Cells 双计量费模型 | 🟢 70% | EIP-1559 双计量完备（`basefee.rs`）；**lane multiplier 全无**；lane 预算与规范偏差 4 倍 |
| **CIP-4** | 链上状态存储 | 🟢 75% | QMDB + Merkle 证明完整；**§12 状态租金完全缺失**；StatePrefix 布局与规范偏差 |
| **CIP-5** | 原生定时器（revised） | ✅ ~93% | Model B 端到端完整；**carry-forward bug 已知**（`speculative.rs:751`） |
| **CIP-6** | Python SDK / Actor API | ✅ ~95% | 全表面：三种调用原语 / FSM 编译器 / Continuation；本会话已把 CIP-6 spec 同步到 "In-PVM Actor SDK (cowboy_sdk)" 新框架 |
| **CIP-7** | 简单流协议 r2 | 🟠 ~10% | 仅一个 Python demo；`0x12 STREAM_KEY_MANAGER` 系统 actor 全无；spec r2 已修 v1 `0x06` 冲突 |
| **CIP-8** | MPP Session（追溯定档） | ✅ ~92% | 6 opcodes 52-57 全在代码；链上 `SESSION_ACTOR=0x0C` + 链下 voucher 库（`runner-common/voucher.rs`）+ EIP-712 domain；**仅 `handle_session_slash` 是 `UnsupportedInstruction` stub**（`session.rs:371-380`），等 CIP-2 dispute arbitration milestone |
| **CIP-9** | Runner Storage / CBFS | 🟢 73% | 数据面齐全（StorageCommitment / CapToken / Relay 调度）；**§13 DrainRelay / AutoDrainPolicy 治理面新对齐**（opcodes 85/86）；GET_MANIFEST RPC 仍缺、ManifestCommitted 事件未发、PoR 经济未完全挂 |
| **CIP-10** | Runner Containers (OCI) | ❌ 0% | 完全未实现：无 OCI / cgroups / GPU / 网络策略 / Container Registry 0x10 |
| **CIP-11** | Runner QUIC Push 连通 | ❌ 0% | 完全未实现：无 QUIC 通道 / presence bitmap / MRU 黏性 |
| **CIP-12** | 链上治理 | 🟡 30% | demo `SubmitProposal/CastVote/ExecuteProposal` 在；**3 种 `ProposalPayloadKind` 落地**（含 CIP-9 §13 两条）；无双院 / Tier / Security Council / fast-track |
| **CIP-13** | Runner 质押委托 v2 | ❌ 0% | 仍未实现；**opcode 52-56 历史 claim 与代码 CIP-8 Session 52-57 撞号**（本会话 spec 已标 TBD ≥87） |
| **CIP-14** | DNS Addressable Actor v2 | 🟠 ~5% | 仅 `POST /actor/read` 命中只读语义；无 `0x0D` Route / `0x0E` Gateway / `0x0F` Receipt Registry；无 IngressDispatch (65) / CompleteReceipt (66) |
| **CIP-15** | Gateway 实现 + 公开资产 v2 | 🟠 ~10% | 仅 CBFS Visibility::Public 底；无 Gateway HTTP serving；无 route_manifest / cors_config 链上配置 |
| **CIP-16** | 自定义域名 / TLD v2 | ❌ 0% | 完全未实现 |
| **CIP-17** | 可验证状态读 RPC | 🟢 80% | `/proof/storage/*` 等齐全；端点路径 / `block_hash` / `absent` 字段与 spec 有差异 |
| **CIP-18** | Payments (PaymentGate `0x11`) r2 | ❌ 0% | 完全未实现（2026-05-11 r2 刚定稿，地址段 `0x0013→0x11` 重排） |
| **CIP-19** | Gateway MCP Ingress | ❌ 0% | 依赖 CIP-14/15/18 全无；`runner-mcp` 是外向客户端，方向相反 |
| **CIP-20** | 同质化代币 | ✅ ~85% | 核心齐全；`on_transfer` 后置钩子缺失、事件未发射、hook cells 上限未挂 |
| **CIP-21** | DEX / 流动性池 | ❌ 0% | 完全未实现 |
| **CIP-22** | 连续清算拍卖 | ❌ 0% | 完全未实现 |
| **CIP-23** | TEE Execution | 🟡 ~30% | 签名验签骨架 + TEE Verifier 支持 opcodes 60-63 在代码（由 CIP-24 §3.3 推动落地）；CAE 复合证明 / 证书链 / nonce 重放保护 / dispatcher MeasurementBinding 过滤仍缺 |
| **CIP-24** | Cowboy Secret Service (CBSS) | 🟢 **~80%** | **代码已大规模落地**：21 个 SystemInstruction handlers（60-63 TEE keys + 68-84 CBSS main）；BLS12-381 阈值 IBE / DKG ceremony / proxy registry / release receipt / liveness challenge / reshare / forced deregister 全在；独立 `cbssd` 守护进程 + cbss-crypto / cbss-client / cbss-types 工作区。**仅** Intel DCAP/TDX 与 AMD SEV-SNP 全证书链 vendor collateral 校验留到 v1.1 pre-mainnet milestone |
| **CIP-25** | 跨链架构 | 🟢 ~60% | Cowboy↔Ethereum demo 桥可用；欺诈证明 stub / 无 ZK / 无 optimistic / 无 native LC / 无多链 |
| **CIP-26** | 账户作用域库 | ✅ ~95% | 全表面 + 端到端示例；**最成熟的 CIP 之一** |
| **CIP-28** | Agent Banking (BankActor) | ❌ 0% | 仅 HTML mock-up（2026-05-12 定稿，本会话 r1.1 把地址 `0x0D` → `0x13`） |
| **CIP-29** | 链上事件钩子 | 🟢 **~55%** | `EVENT_SUBSCRIPTION_SYSTEM_ACTOR=0x1D` 虚拟 actor + Phase 1 sync fire + Phase 2 bid-sorted async fire 框架；3 read RPCs；emit_event + EmitOrigin DeferredTx metadata；StatePrefix 已避开与 CIP-26 撞号。**主要缺口**：bid orderbook 持久化深度 / 异步 fire path 完整测试 / Phase 3 跨块 fire 链 |
| **CIP-31** | CBFS 租金表 | 🟠 ~10% | 三方分账缺失 / 挑战债券缺失 / 罚没表缺失；费率值差 10× |

---

## 三、按 CIP 详细分析

### 3.1 Actor 与计算层（CIP-1/2/6）

#### CIP-1 v3 — Actor 调度器

**核心结论**：v1 分层日历队列、v3 EIP-1559 timer-lane 基础费、每 actor 公平权重均**完全未实现**。代码处于 CIP-5 FIFO 基线状态（这是规范允许的预激活态）。

| 要求 | 状态 | 证据 |
|---|---|---|
| Tx-then-Timer 块排序 | ✅ | `node/storage/src/speculative.rs:204-302` |
| 三路径生命周期（自然/TTL/破产自毁） | ✅ | `speculative.rs:626-728` |
| 系统指令 48/49/50（Cancel/UpdateConfig/Extend） | ✅ | `types/src/execution.rs:539,543,548` |
| `LANE_TIMER_CYCLES` 执行 lane | ✅ | `constants.rs:61` = 8,888,890 |
| **Carry-forward**（被跳过 timer 应进下一区块） | ❌ | `speculative.rs:751` 跳过后未重新索引——已知 bug |
| **分层日历队列（Ring/Epoch/Overflow）** | ❌ | `storage/src/timers.rs` 仅 flat per-height map |
| **GBA / `getGasBid(context)`** | ❌ | 无代码 |
| **EIP-1559 timer-lane basefee** | ❌ | `basefee.rs:37-74` 仅有 `cycle_basefee` + `cell_basefee` |
| **`max_fee_per_cycle` 在 schedule_timer** | ❌ | `pvm_host.rs:1606-1725` 签名无费率字段 |
| **公平权重 `W(actor) ∈ [1,2]`** | ❌ | 无 `FAIRNESS_WINDOW_BLOCKS` 计算 |
| **`priority_tier_hint` 枚举** | ❌ | SDK 中不存在 |

#### CIP-2 — 链下可验证计算

**核心结论**：v1 主干完整；v2/v3 改革多项未实现。5/15 baseline 不变。

✅ 已实现：
- 系统 actor `0x01-0x07` + 扩展 `0x08`(Treasury) / `0x09`(Governance) / `0x0A`(StorageManager) / `0x0B`(RelayRegistry) / `0x0C`(Session)
- `JobSpec` schema（`runner-common/types.rs:101-117`）
- Fisher-Yates VRF 种子 = `Keccak256(block_hash || "cowboy-runner-select-v2:" || job_id || submitted_at_le8)`（`dispatcher.rs:1095-1108`）
- 候选按地址字节升序（`dispatcher.rs:1266`）
- 对数权重 `stake_to_weight`（`dispatcher.rs:64-72`）
- 7 阶段候选过滤（健康/声誉≥50/能力/TEE/价格/并发/池权益），实际还多了 probation、attachments、stake×1.5
- 重试种子 = `Keccak256(original_seed || "retry:" || retry_count_le4)`（`dispatcher.rs:1429-1437`）
- Commit-reveal 流程（`verifier.rs:35-200`），commit 截止于 `submitted_at + 0.6 * timeout_blocks`
- 6 种 VerificationMode（`runner-common/types.rs:325-383`）
- Entitlement Registry 类型与指令 30-35（`types/src/entitlement.rs`、`types/src/execution.rs:517-522`）
- TEE Verifier 与 CBSS Secrets Manager 系统 actor（`execution/src/cbss.rs:1106-1500+`）

❌ 缺失：
- v2 DNS 校验变体（`DnsTxtRecordMatch` / `DnsCnameMatch`）
- v3 `CrashAttestation` 机制
- v3 `SlashDistribution { burn_bps, submitter_bps, treasury_bps }` schema
- v3 聚合者奖励 `aggregator_bonus_bps = 150`
- v3 自适应 HHI 决定的 committee 规模
- v3 VRF 权重 `w = stake × sqrt(reputation)`（当前用 `stake_to_weight × completion_rate / REPUTATION_WEIGHT_SCALE`）
- v3 固定语义相似度模型 `0x09/system:cip2:semantic_similarity_embedding_model`

#### CIP-6 — Python SDK

**核心结论**：本审计中**最完整**的 CIP（~95%）。本会话已把 CIP-6 spec 同步到 "In-PVM Actor SDK (cowboy_sdk)" 新框架命名。

✅ 全部实现（位于 `node/pvm/Lib/cowboy_sdk/`）：
- 三种调用原语：`call()` / `send()` / `await runner.*`（`call.py:17`、`send.py:18`、`runner.py:80`）
- `ActorRef` 语法糖
- `@reentrancy_guard`、`@runner.continuation`、`@actor.continuation`
- FSM-AST 编译器（`_compiler.py:64`）静态强制 ≤8 awaits、禁嵌套 await、禁递归 await
- `capture()` 显式状态捕获
- 限制精确匹配规范：`_MAX_CONT_SIZE=64*1024`、`_MAX_CONT_COUNT=100`、await 上限 = 8
- `guard_unchanged=[...]` 装饰器级守卫
- `storage.guard(key)` 返回 `GuardedValue`
- `Retry` 指数退避
- `TaskGroup` 结构化并发（`taskgroup.py:108`）
- `CowboyModel` 确定性类型栈
- `SoftFloat`、`ordered_set`、`BlockHeight`
- `Verify` builder + 16 内置校验器（含 `no_prompt_leak`、`entropy_check`）
- `@pure`、`@deferred`、`@public`、`@callable_by(OWNER|SELF)`

❌ 缺：
- `priority_tier_hint` 枚举（依赖 CIP-1 v3，未实现）
- CLI 版本漂移（自报 v0.1.1 / 0.0.24，实际 0.0.29）

---

### 3.2 存储与文件系统（CIP-4/9/31）

#### CIP-4 — 链上状态存储

✅ 已实现：
- 54-byte 固定键（`state_key.rs:22`）
- QMDB 三层 Ledger/State/Aux 管道（`chain/src/application.rs:619-689`）
- 投机缓存上限 8（`blockchain_storage.rs:44`）
- Merkle 证明全 RPC：`/proof/account`、`/proof/actor`、`/proof/storage`、`/proof/tx`、`/proof/receipt`、`/proof/multi`（`rpc/src/handlers/proof.rs`）
- 独立 `cowboy-proof-verifier` crate
- 参数：`MAX_TIMERS_PER_ACTOR=1024`、`MAX_PENDING_DEFERRED_PER_ACTOR=64` 等

🟡 与规范偏差：
- 路由键 **20 字节**而非规范 21（后缀 33 而非 32）
- 前缀枚举从 `0x01` 起而非 `0x00`：`Account=0x01`、`Actor=0x02`、`ActorStorage=0x03`、… `SystemState=0x0A`
- 增加生产前缀：`Code=0x0F`、`ActorMailboxHead=0x10`、`Library=0x14`、`TxReturnData=0x16`、`PublishRootDedup=0x17`
- **5/26 新增**：`EVENT_SUB=0x0E`、`EVENT_SUB_INDEX_VALUE=0x0F`（CIP-29 落地，避开 CIP-26 的 `Library=0x14` / `ActorLibPin=0x15`）

❌ **严重缺失**：
- **§12 状态租金完全未实现**——无 `rent_debt`、`grace_threshold`、`rent_rate`、`account_size_bytes`、`rent_catchup_bps`、`system:cip4:rent_*` 治理键

#### CIP-9 — Runner Storage / CBFS

**架构图**（`cbfs/`）：
- `cbfs/types/` — 1604 LOC，规范类型
- `cbfs/store/` — Sled blob store
- `cbfs/placement/` — Sled placement CAS
- `cbfs/manifest/` — Merkle 构建
- `cbfs/erasure/` — Reed-Solomon GF(8)
- `cbfs/crypto/` — AES-256-GCM、DEK wrap/unwrap、BLAKE3
- `cbfs/transport/` — QUIC + TLS + protocol framing
- `cbfs/fuse/` — POSIX FUSE 挂载
- `cbfs/sdk/` — `Volume::create/open` 等 SDK
- `cbfs/cli/`、`cbfs/node/`、`cbfs/hooks/`、`cbfs/cowboy-ras/`、`cbfs/auth/`

✅ 已实现：
- `0x0A STORAGE_MANAGER`、`0x0B RELAY_REGISTRY`
- `StorageCommitment` schema（含生产字段 `paid_until_epoch`、`escrow_balance`）
- 4 状态机 `ACTIVE → GRACE_PERIOD → DELETED → GARBAGE_COLLECTING`
- `Visibility::Public/Private`
- Reed-Solomon K∈[2..16], M∈[1..8]，默认 4/6
- AES-256-GCM 客户端加密 + 12 字节 Nonce
- BLAKE3 + power-of-2 padded Merkle（精确匹配 v2.r2 §3）
- Operation 枚举：PutShard、GetShard、DeleteShard、ProveShard、GetPlacement、PutPlacement、ReplicatePlacement、Ping 等
- 自主 2 阶段 shard repair（`cbfs/node/src/repair.rs:130-275`）
- Orphan shard GC
- FUSE 挂载 + 5 秒 push/pull 同步守护进程
- 两级 commit（Steamtrain + on-chain `commit_manifest_v2`）
- Volume create / undelete / commit_manifest_v2 端点
- 库不是 sidecar 架构（`runner-storage` 直接嵌入 `cbfs_sdk`、`cbfs_fuse`、`cbfs_transport`）
- **5/26 新增**：§13 AMEND 9-J `SubmitDrainRelayProposal`(85) / `SubmitAutoDrainPolicyProposal`(86) 治理面在代码（`node/execution/src/execution/system_instruction.rs:747-905`）

❌ 缺失：
- **AMEND 9-G `GET_MANIFEST` RPC**——Operation 枚举无此变体
- **AMEND 9-H `ManifestCommitted` 链事件**——从未发射
- **PoR 挑战平面**——`shard_inclusion_proof` 硬编码空（`cbfs/node/src/handler.rs:793`），无链上 PoR timer、verifier、`POR_CHALLENGE_INTERVAL`/`POR_MISS_PENALTY`/`POR_RESPONSE_WINDOW` 常量
- **`transfer_volume`**
- **卷容量/账户配额限制**（`MAX_VOLUMES_PER_ACCOUNT=256`、`MAX_VOLUME_SIZE=100GiB` 未编码）
- **`VOLUME_CREATION_FEE` / `BASE_ATTACHMENT_FEE`** 费用常量
- **`STORAGE_GRACE_EPOCHS = 2`**（规范 86,400，10× 偏差）
- **HKDF + `wrapping_key_hash`** 路径（生产用 `sealed_runner_keys` 替代）

#### CIP-31 — CBFS 租金表

**核心结论**：本域**最不完整**的规范。5/15 baseline 不变。

| 要求 | 状态 | 证据 |
|---|---|---|
| `STORAGE_FEE_PER_BYTE_PER_EPOCH = 10` nano-CBY | ❌ | 实际值 = 1（10× 偏差），`cowboy-ras/src/lib.rs:25` |
| `TRANSFER_FEE_PER_BYTE = 1` | ❌ | 常量不存在 |
| **10/2/88 三方分账** | ❌ | 仅两方（10/90），`split_storage_fee` 返回 `(burned, relay_rewards)` |
| **Pro-rata 权重 `shard_count × shard_age`** | ❌ | 无 `MAX_SHARD_AGE_FOR_WEIGHTING` |
| `MIN_RELAY_STAKE = 5,000 CBY` | ❌ | 不存在 |
| **`RELAY_CHALLENGE_BOND = 10 CBY`** | ❌ | 完全缺失 |
| `POR_CHALLENGE_FEE` / `CHALLENGER_BOUNTY` | ❌ | 不存在 |
| **罚没表**（`POR_MISS_PENALTY=50` 等） | ❌ | 全无 |
| Storage Manager `0x0A` / Relay Registry `0x0B` | ✅ | `cbfs/cowboy-ras/src/system_actors.rs:11-18` |

---

### 3.3 Runner 系统（CIP-10/11/13）

#### Runner 工作区 crate 地图（`runner/crates/`）

- `runner-node` — 主二进制；`start_job_listener` 轮询循环
- `runner-common` — 共享类型（`JobSpec`、`JobAssignment`、`RunnerResult`）、ECDSA 签名、voucher 序列化
- `chain-client` — 链 REST 客户端
- `runner-llm`、`runner-http`、`runner-mcp`、`runner-agent` — Job 执行器
- `runner-tee` — TEE 见证生成
- `runner-storage` — CIP-9 卷编排
- `runner-registry`、`job-dispatcher`、`result-verifier`、`tee-verifier` — 系统 actor 处理器的链下 Rust 副本（测试用）
- `runner-consensus` — N-of-M 聚合 + BLS VRF 桩

#### CIP-10 — 容器运行时

**核心结论**：**完全 0% 实现**。5/15 baseline 不变。

❌ 全部缺失：
- OCI 镜像格式 / 摘要锁定
- `RuntimeConfig` 字段在 JobSpec
- 容器创建（cgroups v2、命名空间、overlayfs）—— `JobType` 仅 Llm/Http/Mcp/Custom/PublishChainRoot/Agent
- FUSE 挂载到 `/mnt/volumes/*`（当前直接挂在 host 文件系统）
- `ResourceLimits`（CPU 毫核、scratch disk、GPU）—— 当前 `ResourceBounds` 仅 LLM 相关
- 资源类（`small`/`medium`/`large`/`gpu-*`）
- Runner 能力广告（GPU 设备、缓存基镜像）
- GPU 透传（NVIDIA/ROCm）
- `NetworkPolicy`（NONE/ALLOWLIST）
- 容器生命周期（pull → create → mount → exec → teardown）
- `Container Registry` 系统 actor `0x10`
- 操作码 61-64（**5/26 新冲突**：这些 opcodes 现已被 CIP-24 §3.3 TEE keys 占用，CIP-10 v2 激活时需重号至 ≥87）
- `BillingAttestation` with `cgroup_digest`

> 注：`runner-agent` 中的 "Sandbox" 仅为文件路径预检（`fs_tools.rs:66`），非 OS 级隔离。

#### CIP-11 — Runner 连通与推送

**核心结论**：**完全 0% 实现**。当前用 5 秒 HTTP 轮询 + 链上心跳。5/15 baseline 不变。

❌ 全部缺失：
- 连通子集函数 `Sub(R, t)`
- QUIC 控制 + 作业流（`quinn` 仅被 cbfs-transport 用于存储 shard 抓取）
- `Hello`/`HelloAck` 握手
- `HeartbeatPing`/`Pong`、`BackpressureSignal`、`CapabilityDelta` 帧
- 投票携带的 presence bitmap
- presence filter 在调度器（当前过滤器链无此项）
- MRU 权重乘数
- 推送式 `JobAssignment`
- `JobAck`/`JobProgress`/`JobResult`/`JobCancel` 帧

#### CIP-13 — Runner 质押委托 v2

**核心结论**：**完全 0% 实现**，且**有 opcode 冲突**。

❌ 全部缺失：
- `DelegationConfig` 字段
- `DelegationTranche`/`TrancheStatus`/`DelegationTotals` 类型
- 操作码 52-56 `RunnerUpdateDelegationConfig` 等
- `effective_stake` 在 VRF
- 委托者按比例分账

⚠️ **冲突**（5/26 已 spec 端修复）：
- v1 spec 声称 52-56 给委托，**但代码 52-57 已被 MPP Session 使用**（`SYS_SESSION_OPEN=52` … `SYS_SESSION_SLASH=57`）
- 本会话 spec 已把 CIP-13 v2 §1 master opcode 表标 TBD ≥87（drift.md C-3 收口）

#### Runner 费用链分析（CIP-2/9/10 横切）

三条独立费用流：
- **Flow 1（Runner 作业支付，CIP-2）**：✅ 实现（默认 89/10/1 split）
- **Flow 2（存储租金，CIP-9）**：❌ 无 epoch 扣费循环
- **Flow 3（容器计算，CIP-10）**：❌ 完全缺失

---

### 3.4 网络与会话（CIP-7/8/15/19）

#### CIP-7 — 简单流协议 r2

**核心结论**：仅有非规范的 Python demo（`/node/cli/actors/stream_actor.py`），实现粗粒度 publish/subscribe。5/15 baseline 不变。

❌ 全部缺失：
- 规范化 `StreamMessage`（13 字段，CBOR + ed25519）
- 环形缓冲区（`head_sequence`、`floor_sequence`、`DEFAULT_RING_BUFFER_CAPACITY=10_000`）
- JSON Filter DSL
- **`0x12 STREAM_KEY_MANAGER`** 系统 actor
- `stream_encrypt`/`stream_decrypt`/`acquire_epoch_access`/`register_account_key` HostApi
- `PaidStreamConfig`/`Entitlement`/`AccountKeyRegistration`/`KeyAccessReceipt` 类型
- XChaCha20-Poly1305（`NONCE_BYTES=24`, `TAG_BYTES=16`）
- CBY epoch 计费 + `EpochAccessPurchased` 事件
- 9 个事件（`StreamMessagePublished` 等）

#### CIP-8 — MPP Session

**核心结论**：本审计**最完整**之一（~92%，5/26 由 ~90% 微升）。

✅ 已实现：
- `SESSION_ACTOR=0x0C`（`system_actors.rs:35`）
- 存储布局 `b"session:" || session_id`
- `Session`、`SessionAsset::Cby`、`SessionVoucher`（含 65 字节签名）
- EIP-712 域 `"Cowboy MPP Session" v1`（`types/src/session_eip712.rs`）
- **6 opcodes 52-57 全在代码确认**：`SYS_SESSION_OPEN/DEPOSIT/SETTLE/CLOSE/FINALIZE/SLASH`
- 6 个处理器：`OpenSession`/`Deposit`/`Settle`/`CloseSession`/`Finalize`/`Slash`（最后一个返回 `Unsupported`，符合 §8.6）
- 5 项 voucher 校验（session_id、状态窗口、过期、nonce 递增、cumulative 上限）
- 89/10/1 settlement split 复用 CIP-2 SettlementConfig
- `DISPUTE_WINDOW_BLOCKS=75`
- 链下 voucher 库（`runner-common/src/voucher.rs`）含 EIP-712 域和 sign/recover
- 3 个工作 demo（`examples/mpp_session/`、`llm_session/`、`session_chain_e2e/`）

🟡 小偏差：
- `SessionStatus::Slashed{...}` 变体缺失
- 存储用 `serde_json` 而非规范的 bincode
- **Slash 仍是 stub**（`node/execution/src/runner/session.rs:371-380` 返回 `UnsupportedInstruction`）——等 CIP-2 dispute arbitration milestone

#### CIP-15 — Gateway 实现 + 公开资产

**核心结论**：Gateway HTTP 服务**完全不存在**。5/15 baseline 不变。

❌ 缺失：
- Gateway HTTP server crate
- `ROUTE_REGISTRY (0x0D)`、`GATEWAY_REGISTRY (0x0E)`、`RECEIPT_REGISTRY (0x0F)`
- `ingress.http`、`ingress.static`、`ingress.mcp`、`dns.attach_external` entitlements
- 链上路由清单 + `update_route_manifest` 处理器
- `_meta/routes.json` / `_meta/cors.json` 等
- `/_cowboy/*` 保留路径拦截
- 每卷元数据缓存、对象 LRU、对冲并行 shard 抓取
- `PaymentGate (0x11)`

✅ 仅有的相邻代码：
- CBFS Visibility::Public + commit_manifest_v2
- BLAKE3 power-of-2 padded Merkle（`cbfs/manifest/src/merkle.rs:24-68`）
- `POST /actor/read` 读处理器原语（`rpc/handlers/actor.rs:39`）

#### CIP-19 — Gateway MCP Ingress

**核心结论**：**完全 0% 实现**。两个 MCP 命名工件方向都错：
- `runner-mcp` 是 MCP **客户端**（CIP-2 执行器后端，外向）
- `monorepo/mcp` 是第三方 Commonware 文档 MCP 服务器

---

### 3.5 寻址与治理（CIP-5/12/14/16/17）

#### CIP-5 — 原生定时器

**核心结论**：~93% 完整。5/15 baseline 不变。

✅ 全部实现：
- `Timer` 结构（8 字段 Model-B schema）
- 存储 + per-height 索引（FIFO）
- `MAX_TIMERS_PER_ACTOR=1024` 上限
- Timer ID = `keccak256(actor‖height_be‖payload‖nonce_be)`
- 5 个 PVM syscall：`schedule_timer`、`schedule_timer_ex`、`extend_timer`、`cancel_timer` + ownership 检查
- `fee_payer` 校验（拒绝 ZERO、系统带 `0x01..0x0F`、第三方限制）
- EOB FIFO 分派 + 三路径分类
- Pre-charge `max_cost` 到 `fee_payer`，按实际 cost 退款
- TTL/破产自毁事件发射
- Deferred-tx 构造（origin = zero hash）
- `LANE_TIMER_CYCLES` + `TIMER_GC_CYCLES` 双 lane
- 治理可调 `TimerConfig`
- 操作码 48/49/50（`SYS_CANCEL_TIMER/UPDATE_TIMER_CONFIG/EXTEND_TIMER`）

❌ 缺失：
- §9 未来 EIP-1559 timer auction（依赖 CIP-1 v3，未实现）

⚠️ **已知 bug**（`speculative.rs:751`）：超 lane 预算的 timer 用 `continue` 跳过但 `height` 字段未更新，`get_timers_by_height` 严格匹配 height 故下一区块永不再选中——**超预算 timer 永久丢失**。

#### CIP-12 — 治理

**核心结论**：仅 demo 级。代码自承"Simplified vs. CIP-12"（`runner/src/types.rs:819,856`）。5/26 略升至 30%：

✅ 已实现：
- `0x09 GOVERNANCE_SYSTEM_ACTOR`
- 操作码 45-47（`SUBMIT_PROPOSAL/CAST_VOTE/EXECUTE_PROPOSAL`）
- Proposal 存储 + RPC（`/governance/proposals` 等）
- **3 种载荷**（5/26 由 1 扩到 3）：`UpdateBasefeeConfig`、`DrainRelay`、`UpdateAutoDrainPolicy`
- 操作码 85/86 `SubmitDrainRelayProposal/SubmitAutoDrainPolicyProposal` 通用 `ExecuteProposal`(47) 路径在
- Smoke 测试（`examples/governance/smoke-voting.mjs`）

❌ 全部缺失：
- 双院投票（stake 院 + validator 院）
- Tier 0-4 分层
- 温度检查
- 时间锁
- 7-of-9 安全理事会（cancel / fast-track / circuit-break）
- 系统 actor 升级流程（`SystemActorUpgrade`、rollback_slot、pending_upgrades）
- `MetaGovernance` 载荷
- 提案押金（refund vs burn）
- 投票延期机制
- `TreasuryDisbursement` / `RegistryUpdate` 载荷

#### CIP-14 — DNS 可寻址 Actor

**核心结论**：本规范的链上面**完全未实现**。5/15 baseline 不变。

✅ 仅有的相邻代码：
- `POST /actor/read` 端点（`rpc/src/rpc.rs:228`），执行 `read_only=true` 处理器
- PVM 只读模式 + 完整的 syscall trap 表（`pvm_host.rs` `deny_if_read_only`）

❌ 缺失：
- `ROUTE_REGISTRY (0x0D)` / `GATEWAY_REGISTRY (0x0E)` / `RECEIPT_REGISTRY (0x0F)`
- `RouteRegistration` schema
- `ingress.http` entitlement
- `IngressDispatch` 操作码
- `read_handler` RPC 命名（当前路径不同）
- 域名长度分级注册费 + 宽限期 + 荷兰式拍卖
- 网关心跳/分派 API

#### CIP-16 — 自定义域名

**核心结论**：**完全 0% 实现**。唯一相邻的是预先存在的 `VerificationMode::MajorityVote`（CIP-2 用），其他全无。

#### CIP-17 — 可验证状态读

**核心结论**：**功能上完整但接口名不同**。5/15 baseline 不变。

🟡 已实现但名称/格式与规范差异：
- 端点：`/proof/storage/{addr}/{key}` 而非 `/state/{addr}/{key_hex}`
- 证明：QMDB MMR（BLAKE3）而非 MPT siblings（keccak）
- 响应缺 `block_hash` 和 `absent` 字段
- 无 `prove=false` 查询参数
- ✅ `/proof/multi` 批量读已实现（规范列为未来工作）

---

### 3.6 金融与代币（CIP-3/18/20/21/22/26/28）

#### CIP-3 — 双计量费模型

✅ 已实现：
- Cycle 计量 + Cell 计量
- 4 执行 lane：User/Runner/Timer/System
- EIP-1559 更新公式（`basefee.rs:223-264`，`ALPHA=96`, `DENOM=96`, `MIN_BASEFEE=10_000`, `MAX_BASEFEE=1e24`）
- Genesis + 持久化（`BASEFEE_SYSTEM_ACTOR=0x06`）
- Tx 费组成：burn（basefee）+ proposer tip
- 治理可调 `BasefeeConfig`

🟡 偏差：
- Lane 预算量级 vs 规范（5M/2.5M/2M/0.5M）→ 代码 22M/8.9M/8.9M/40M，约 4× 缩放（自承调校）
- **执行 lane 费率倍增器（§2.2.3）完全缺失**——无 `lane_fee_multiplier` 治理键
- Transfer 基本成本采用 2026-04-15 amendment（5000 cycles / 500 cells），非原 CIP-3 的 21k

#### CIP-18 — 支付（PaymentGate 0x11）

**核心结论**：**完全 0% 实现**（CIP 2026-05-11 r2 刚定稿）。5/15 baseline 不变。

❌ 全部缺失：
- `PAYMENT_GATE_ADDRESS = 0x11`
- `PaymentPolicy`/`PaymentIntent`/`PaymentBinding` 类型
- MPP wire format（`WWW-Authenticate: Payment`、`Payment-Receipt` 等）
- x402 wire format（`PAYMENT-REQUIRED`、`PAYMENT-SIGNATURE` 等）
- 4 种支付模型（per-request、actor-funded、prepaid pass、epoch subscription）
- 入站 EVM bridge facilitator（`bridge.facilitate.evm` entitlement）
- MCP gating（`-32402` JSON-RPC、`_meta.payment-authorization`）
- OpenAPI 发现 `/_cowboy/payment/openapi.json`

> 注：`examples/bridge/` 是出站 CBY→ETH 桥（成熟），但入站 facilitator 缺失。

#### CIP-20 — 同质化代币

**核心结论**：~85% 完整。5/15 baseline 不变。

✅ 已实现：
- `TokenMint` 数据结构（`token/src/types.rs:50-64`），`u128` amount 类型（符合 2026-03-27 amendment）
- Token Registry 系统 actor
- 存储布局：mints/balances/allowances/frozen
- 全部 7 个操作：`token_create`、`token_transfer`、`token_transfer_from`、`token_approve`、`token_mint`、`token_burn`、`token_transfer_batch`
- 行政操作：`token_freeze_account`、`token_unfreeze_account`、`token_set_hook`、`token_transfer_ownership`
- `can_transfer` 预钩子 + 50k cycles 上限
- Reentrancy guard（`TokenHookReentrancy` 错误）
- `MAX_SUPPLY` 检查
- E2E 示例（`examples/token/`）

❌ 缺：
- **`on_transfer` 后置钩子**（规范要求 pre + post）
- **标准化事件发射**（`TokenTransfer`、`TokenApproval`、`TokenMint`、`TokenBurn`、`TokenFrozen` 等全无 `emit_event` 调用）——阻塞 indexer 与合规
- **Hook cells 上限**（Phase 2 工作）

#### CIP-21 — DEX 与流动性池

**核心结论**：**完全 0% 实现**。5/15 baseline 不变。

❌ 全部缺失：
- `amm_get_amount_out` 平台原语
- `amm_get_amount_in`、`amm_quote`
- `amm_tick_to_sqrt_price`（Q64.96）
- `amm_swap_exact_in`/`amm_swap_exact_out`
- V2 恒积池 actor
- V3 集中流动性池 actor
- 工厂 `create_v2_pool` / `create_v3_pool`
- 标准费率档（1/5/30/100 bps）
- 原生 TWAP 预言机
- MEV 保护钩子

#### CIP-22 — 连续清算拍卖

**核心结论**：**完全 0% 实现**。依赖 CIP-21（也未实现）。

#### CIP-26 — 账户作用域库

**核心结论**：本审计**最完整**之一（~95%）。5/15 baseline 不变。

✅ 全部实现：
- `ActorLibrary` 结构
- `StatePrefix::Library=0x14`、`ActorLibPin=0x15`
- `LibraryInstruction::PublishLibrary`、`RemoveLibrary`
- 处理器（`execution/src/execution/library_instruction.rs:54-120`）
- 名称校验正则 `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$`
- 代码大小上限 `MAX_LIBRARY_CODE_BYTES=131_072`
- AST 扫描（`rustpython_compiler::extract_top_level_imports`）
- 标准库 + SDK 白名单过滤
- 跨账户 import 拒绝（`UnresolvedImport`）
- `MAX_LIBS_PER_ACTOR=8`、`MAX_TOTAL_LIB_BYTES=131_072`
- Pin 在发布者重新发布后仍不变
- 部署前预加载到 `sys.modules`
- CLI `cowboy lib publish/remove/list`
- 端到端示例 `examples/cip26_account_libraries/start_all.sh --test`

❓ 待验：
- `LibraryPublished` 事件发射
- 每次调用加载 gas（`len(code) × 5` cycles）

#### CIP-28 — Agent Banking

**核心结论**：**仅 HTML mock-up**。CIP 2026-05-12 定稿，本会话 r1.1 把地址 `0x0D → 0x13`（drift.md C-1 收口）。

❌ 全部缺失：
- `BankActor` 系统 actor `0x13`（**5/26 已重号**，原 `0x0D` 让位 CIP-14 Route Registry）
- `BankEntry`/`CardEntry`/`CardPolicy`/`SpendWindow` 类型
- 卡片地址派生 `keccak256(DOMAIN ‖ bank_id ‖ owner ‖ agent ‖ nonce)[12..32]`
- 15+ `BankInstruction` 变体
- 第三种 gas 扣费路径（`tx.fee_payer_override` → BankActor.charge_gas）
- 限额（per_hour/day/month）
- 白名单（`allowed_receivers`、`allowed_syscall_kinds`）
- `FiatMintVoucher` 签名校验 + `voucher_used` 重放表
- 治理添加多 bank 流程
- 预审 + 后置结算管道
- `bank_activation_height` 特性门

🟡 仅有：
- UI mock：`examples/cip28_agent_banking/index.html`（2606 行中文 HTML）

---

### 3.7 高级特性（CIP-23/24/25/29）

#### CIP-23 — TEE 执行

**核心结论**：~30%（5/26 由 25% 微升）。签名验签骨架在，规范要求的复合证明全无。

✅ 已实现：
- `TEE_VERIFIER=0x05` 已分配
- `sec.tee_required` entitlement
- `CANONICAL_TEE_TYPES` 包含 `nitro`
- TEE attestation 处理器（`cbss.rs:1106-1287`）：`register_tee_trusted_key`、`submit_tee_attestation`、`revoke_tee_attestation`
- **TEE Verifier 支持 opcodes 60-63 在代码**（`SYS_REGISTER_TEE_TRUSTED_KEY` 等，由 CIP-24 §3.3 推动落地；CIP-23 v2 复用）
- 链下 `tee-verifier` crate（P-256/P-384 签名验签 + 域前缀 `cowboy/tee-verifier/ecdsa-attestation/v1`）
- Result Verifier 拒绝缺 `tee_required` 的 Deterministic 结果

❌ 关键缺失：
- **`CompositeAttestation`** 复合包络（CPU+GPU+ServiceSig+Freshness）——只有平的 `TeeAttestation`
- **`0x05::VerifyCae`** 验证管道——无 nonce/seen-nonces、无 freshness deadline、无 GPU/NCC/NRAS、无 `REPORTDATA = keccak(nonce ‖ pubkey ‖ gpu_measurement)`
- **证书链验证**——非 DCAP / NRAS / VCEK / Nitro 根链，仅 trusted-key 白名单
- **`MeasurementBinding`** 在 Runner Registry——当前 `RunnerCapabilities` 仍只有 `tee_support: Option<String>`
- **调度器仍用废弃布尔过滤**（`dispatcher.rs:1186`）——规范明确禁用
- **Result Verifier 不调用 VerifyCae**——`result-verifier/src/verifier.rs:291` 字面 `// TODO: verify TEE attestation`
- **Secrets Manager `0x04` 未 TEE 门控**
- **`BillingAttestation` 字段**（CIP-10 联动）
- **`tee_call` SDK helper**
- **`MeasurementBinding` 续期**（604,800 blocks）
- **操作码漂移**：实现于 60-63，v1 规范 50-53，v2 规范 57-60，**与两个都冲突**

#### CIP-24 — Cowboy Secret Service (CBSS)

**核心结论**：**5/26 最大变化项**——从未列入 5/15 audit 到 🟢 **~80%**。最复杂的单一子系统。

✅ 已大规模落地（41,000+ 行代码）：
- **node 内**：`execution/src/cbss.rs` (7,738 行) + `types/src/cbss.rs` (1,906 行) + `rpc/src/handlers/cbss.rs` (1,956 行) = **11,600 行**
- **独立 workspace** (`cbss/`)：cbssd / cbss-crypto / cbss-client / cbss-types = **29,448 行**
- **21 个 SystemInstruction handlers 全在代码**（`node/types/src/execution.rs:653-681`）：
  - **60-63** TEE keys（`SYS_REGISTER_TEE_TRUSTED_KEY`、`SYS_SUBMIT_TEE_ATTESTATION`、`SYS_REVOKE_TEE_ATTESTATION`、`SYS_REGISTER_PROXY_TEE_KEY`）
  - **68-84** CBSS main（17 个）：`SetSecret`、`UpdateSecretMeta`、`DeleteSecret`、`RotateSecretEpoch`、`AccessSecret`、`SetReleasePolicy`、`SubmitReleaseReceipt`、`CompleteDkg`、`SubmitDkgShare`、`StartReshare`、`SubmitReshareShare`、`CompleteReshare`、`SubmitLivenessProof`、`RegisterCbssProxy`、`DeregisterCbssProxy`、`UpdateProxyConfig`、`ForcedDeregisterCbssProxy`
- **密码学库**（`cbss-crypto`）：BLS12-381 阈值 IBE + DKG ceremony + proxy registry + release receipt + liveness challenge + reshare + forced deregister 全栈
- **独立守护进程** `cbssd` + cbss-client 客户端 + cbss-types 类型定义

❌ 仅剩：
- Intel DCAP/TDX 全证书链 vendor collateral 校验
- AMD SEV-SNP 全证书链 vendor collateral 校验
- 这两项留到 **v1.1 pre-mainnet milestone**

#### CIP-25 — 跨链架构

**核心结论**：~60% 完整，本审计中**唯一有完整跨链 demo** 的 CIP。5/15 baseline 不变。

✅ 已实现：
- **L1**：`IChainAnchor` 接口（`bridge/contracts/src/IChainAnchor.sol`）
- **L1**：`CowboyLightClient.sol`（2-of-3 ECDSA 委员会，`Anchor.v1` 域前缀）
- **L1**：`Anchor_C`（Ethereum-roots anchor，`bridge/anchor_c.py`）
- **L1**：`JobType::PublishChainRoot`（`runner/src/types.rs:260-266`）
- **L2**：`Mailbox_C` + `Mailbox_E.sol`（`send`/`deliver` + exactly-once + payload-hash 绑定）
- **L2**：源端预付费 + `reclaim_fee` + `bump_fee`
- **L2**：`on_timeout` L3 callback
- **L3**：资产桥（lock-mint + burn-release）`AssetLock` + `AssetMint` + `WCBY` + `bridge_actor.py`
- 14+ E2E 测试脚本（`test_bridge_e2e.sh`、`test_reverse_e2e.sh`、`test_fraud_window_e2e.sh` 等）

🟡 / ❌ 缺：
- `BlockCommitment` 仅 `(txRoot, receiptRoot)`，缺 `state_root`/`parent_hash`/`finalized_at`
- **欺诈证明是 stub**——`FraudWindow.sol::_verifyFraudEvidence` 接受任何非空 evidence
- **委员会异议罚没**未挂端到端
- **`commitment_revoked` 重组原语**缺失
- **`send_stream` / `deliver_stream`** 跨链流缺失
- **ZK / optimistic / 原生轻客户端**后端缺失
- **BLS / 阈值-ECDSA 聚合**缺失
- **多链支持**：仅 Cowboy↔Ethereum；`ChainKind` 仅支持 `COWBOY=0`、`ETHEREUM=1`
- **L3 通用跨链调用分派器**缺失

#### CIP-29 — 链上事件钩子

**核心结论**：**5/26 第二大变化项**——从 ❌ <5% 到 🟢 **~55%**。11 天内实装完整 Phase 1 + Phase 2 框架。

✅ 已实现：
- **`EVENT_SUBSCRIPTION_SYSTEM_ACTOR=0x1D`** 虚拟 actor（`node/types/src/constants.rs:156`）
- **三文件 914 行**：
  - `storage/src/event_subs.rs` (410 行)：订阅持久化、orderbook、索引
  - `execution/src/execution/event_fire.rs` (151 行)：Phase 1 sync fire + Phase 2 async fire 框架
  - `execution/src/execution/event_sub_system_actor.rs` (353 行)：subscription handlers
- **3 read RPCs**（`pvm_host::call_actor:1867-1881` 拦截路由）：
  - `get_rank(topic, subscriber)`
  - `get_topic_orderbook(topic)`
  - `get_min_bid_for_rank(topic, rank)`
- **`emit_event` host API** + `EmitOrigin` DeferredTx metadata tag
- **协议常量**：`MAX_TOPIC_BYTES=64`、`MAX_EVENT_PAYLOAD_BYTES=4096`、`ASYNC_FIRES_PER_DEFER_TX=64`
- **StatePrefix 解撞号**：改用 `EVENT_SUB=0x0E` / `EVENT_SUB_INDEX_VALUE=0x0F`（避开 CIP-26 的 `Library=0x14` / `ActorLibPin=0x15`）
- spec 端 §2.6 由本次审计同步对齐到 `0x1D`（drift.md C-2 收口）

❌ 主要缺口：
- bid orderbook 持久化深度（当前仅前 K 项）
- 异步 fire path 完整测试覆盖
- Phase 3 跨块 fire 链（overflow 至下一区块继续 fire）
- SDK `@emit` / `@on_event` 装饰器

---

## 四、横切发现

### 4.1 系统 Actor 地址空间（2026-05-26 现状）

代码空间分三段：

```
0x01..=0x0C  (12 个，部署型 in code)         RUNNER_REGISTRY 起到 SESSION_ACTOR
0x1D          (1 个，host-intercepted virtual) EVENT_SUBSCRIPTION_SYSTEM_ACTOR
0x0D..=0x13  (7 个，spec-only)               Route/Gateway/Receipt/Container/PaymentGate/StreamKey/Bank
```

保留段 `0x01..=0x0F` 在 `pvm_host.rs:1961, 4291` 禁止 actor 部署 / 禁作 `fee_payer_override`；`0x1D` 在保留段外用 host-interception 模式。这是新的协议级模式区分（详见 [`refs/wiki/entities/system-actors.md`](../wiki/entities/system-actors.md) §"两类激活模型"）。

| 地址 | 拟分配 | 来自 | 状态 |
|---|---|---|---|
| `0x0D` | ROUTE_REGISTRY | CIP-14 v2 | 未分配 |
| `0x0E` | GATEWAY_REGISTRY | CIP-14 v2 | 未分配 |
| `0x0F` | RECEIPT_REGISTRY | CIP-14 v2 | 未分配 |
| `0x10` | CONTAINER_REGISTRY | CIP-10 v2 | 未分配 |
| `0x11` | PAYMENT_GATE | CIP-18 r2 | 未分配 |
| `0x12` | STREAM_KEY_MANAGER | CIP-7 r2 | 未分配 |
| `0x13` | BANK_ACTOR | CIP-28 r1.1 | 未分配（5/26 由 0x0D 重号） |
| `0x1D` | EVENT_SUBSCRIPTION | CIP-29 | ✅ **代码已落** |

### 4.2 SystemInstruction Opcode 实际分配（`node/types/src/execution.rs:591-699`）

| 段 | 用途 | CIP | 状态 |
|---|---|---|---|
| 0-9 | 基础 + Runner Registry + Job Dispatch | CIP-2 | ✅ in code |
| 10-20 | Token 操作 | CIP-20 | ✅ in code |
| 21-29 | (reserved) | — | (free) |
| 30-35 | Entitlement | CIP-2 §7 | ✅ in code |
| 36-39 | (reserved) | — | (free) |
| 40-51 | Settlement / Fund / Key / Upgrade / Basefee / Proposal / Timer / DeployCode | CIP-2/3/5/12 | ✅ in code |
| **52-57** | **MPP Session** (Open/Deposit/Settle/Close/Finalize/Slash) | **CIP-8** | **✅ in code** |
| 58-59 | (free) | — | (free) |
| **60-63** | **TEE Verifier 支持** (RegisterTeeTrustedKey/Revoke/Submit/Revoke) | **CIP-24 §3.3** | **✅ in code** |
| 64-67 | (free) | — | (free)；CIP-14 v2 / CIP-16 v2 期望落 65-67 |
| **68-84** | **CBSS 主分配** (SetSecret…ForcedDeregisterCbssProxy 17 个) | **CIP-24 §3.3** | **✅ in code** |
| **85-86** | **CIP-9 §13** (SubmitDrainRelayProposal/SubmitAutoDrainPolicyProposal) | **CIP-9 §13** | **✅ in code** |
| 87+ | (free) | — | 给 CIP-13 / CIP-23 v2 / CIP-10 v2 / CIP-28 等未实装 v2 提案 |

**v2 提案占用 52-67 的早期声明全部与代码冲突**（CIP-13 52-56 撞 Session；CIP-23 57-60 撞 Session+TEE keys；CIP-10 61-64 撞 TEE keys）。**激活时必须重号到 ≥87**。本审计已把 CIP-13 v2 §1 master table 重写为代码权威视角。

### 4.3 跨 CIP 一致性已收口项（drift.md C-1/C-2/C-3/C-4 + L-5）

- C-1 ✅ CIP-28 BankActor `0x0D → 0x13`（让位 CIP-14 v2.r2 ROUTE_REGISTRY）
- C-2 ✅ CIP-29 spec `0x0A → 0x1D`（对齐代码权威）
- C-3 ✅ CIP-13 v2 §1 master opcode 表按代码权威视角重写
- C-4 ✅ CIP-9 §13 新增 AMEND 9-J 规范 DrainRelay / AutoDrainPolicy
- L-5 ✅ 块时间统一到 1s（CIP-11 r1.2 + CIP-23 r1 同步 rescale）

### 4.4 StatePrefix 命名空间（5/26 解撞号）

CIP-29 实装时采用 `EVENT_SUB=0x0E` / `EVENT_SUB_INDEX_VALUE=0x0F`，避开 CIP-26 的 `Library=0x14` / `ActorLibPin=0x15`。`node/storage/src/state_key.rs:85-92` 注释块记录历史冲突（`PublishRootDedup` 从 `0x14` → `0x16` → `0x17`）。

### 4.5 Entitlement Registry 漂移

`node/types/src/registry.rs` 测试 `registry_has_exactly_15_entries` 锁定 15 项。**缺失**（且不止于此）：
- `ingress.http`、`ingress.static`、`ingress.mcp`（CIP-14、15、19）
- `dns.attach_external`（CIP-16）
- `payment.gate`（CIP-18）
- `bridge.subscribe_event`（CIP-29，5/26 待补）

### 4.6 实现超出规范的部分（也需文档化）

- `JobType::Agent`、`JobType::PublishChainRoot`（CIP-2 v1 未列）
- `Action::UseOwnerBalance`（entitlement.rs:103）
- `Code=0x0F`、`Library=0x14`、`ActorLibPin=0x15`、`EVENT_SUB=0x0E`、`EVENT_SUB_INDEX_VALUE=0x0F` 等生产前缀（CIP-4 未列）
- Treasury `0x08`、Governance `0x09`、`0x1D EVENT_SUBSCRIPTION` 等系统 actor 扩展

---

## 五、Node 仓代码资产盘点

### 5.1 工作区主要 crate 成熟度

| Crate | LOC（src） | 测试数 | 成熟度 |
|---|---:|---:|---|
| execution | ~32,000（含 cbss.rs +7,738） | **747+** | 成熟（最活跃） |
| rpc | ~19,500（含 cbss handlers +1,956） | 560 | 成熟 |
| storage | ~17,500（含 event_subs.rs +410） | 370 | 成熟 |
| types | ~14,100（含 cbss.rs +1,906） | 355 | 成熟 |
| chain | ~7,800 | 109 | 成熟 |
| client | ~4,300 | 142 | 成熟 |
| cli | 较大 | 183 | 功能性（**8 个 TODO 占位**） |
| proof-verifier | 小 | 110 | 功能性 |
| indexer | 小 | 136 | 功能性 |
| validator | 二进制 | 0 | 成熟（编排） |
| inspector | 495 | **0** | WIP（自标 ALPHA） |
| dev_runner | 小 | 0 | 功能性 |
| runner / ras / token | 类型 crate | 47/27/11 | 功能性 |

**5/26 新增独立工作区**：
- `cbss/` — 29,448 行（cbssd 守护 + cbss-crypto + cbss-client + cbss-types）

**测试总计**：~3,000+ 个 `#[test]`（5/15 ~2,977 → 5/26 +CBSS 测试）。

### 5.2 大文件与单点复杂度

- **`execution/src/cbss.rs` — 7,738 LOC（CIP-24 CBSS / DKG，5/26 最大单文件）**
- `types/src/execution.rs` — 6,445 LOC（操作码表）
- `rpc/handlers/ras.rs` — 6,841 LOC（CIP-9 RAS RPC）
- `execution/src/execution/tests.rs` — 7,503 LOC（测试集）
- `execution/src/pvm_host.rs` — 3,691 LOC（host API）
- `rpc/handlers/runner.rs` — 3,510 LOC（runner RPC）
- `storage/src/speculative.rs` — 2,722 LOC（含 timer 调度 bug）

### 5.3 21+ 个示例应用

| 类别 | 示例 |
|---|---|
| **成熟**（含 E2E 测试） | `bridge`、`entitlements`、`multi_call`、`multisig-safe`、`token`、`proof`、`timers_demo`、`cip26_account_libraries` |
| **功能性** | `llm_chat`、`llm_session`、`llm_session_web`、`mpp_session`、`session_chain_e2e`、`governance`、`runner_dashboard`、`indexer_test`、`poison_tx_test`、`restart_test`、`ring-demo`、`passkey-wallet` |
| **stub/WIP** | `cip28_agent_banking`（仅 HTML mock） |

### 5.4 显著 TODO 集中点

| 位置 | 数量 | 备注 |
|---|---:|---|
| cli/src/commands.rs | 8 | 余额、nonce、账户信息、提交、状态、区块范围查询——用户可见 CLI 动词的占位实现 |
| examples | 7 | 主要在 Solidity 测试脚本 |
| execution | 3 | 测试相关或小错误类型 |
| chain | 2 | `application.rs:114, 577` 测试用 min block interval |
| pvm-runtime | 1 | 上游 fork |
| **result-verifier** | 1 | **`verifier.rs:291`：`// TODO: verify TEE attestation`**（CIP-23 关键缺口）|

### 5.5 CIP 在 Rust 代码中出现频次

从 `chain/`、`execution/`、`rpc/`、`runner/`、`ras/`、`token/`、`storage/`、`types/`、`client/`、`cli/`、`validator/`、`cbss/`：

**5/26 更新**：CIP-24 (300+ 新增) · CIP-29 (45+ 新增) · CIP-3 (80) · CIP-9 (64+) · CIP-25 (64) · CIP-26 (47) · CIP-20 (45) · CIP-2 (36) · CIP-5 (11) · CIP-12 (4) · CIP-6 (1) · CIP-4 (1)

注：CIP-1/7/8/10/11/13/14/15/16/17/18/19/21/22/23/28/31 等在代码注释中较少出现，与其实现度对应。

---

## 六、风险与优先级建议

### 6.1 最紧迫的代码-规范偏差（应立即处理）

1. **CIP-1 carry-forward bug**（`speculative.rs:751`）——超预算 timer 永久丢失，**正确性问题**
2. **CIP-23 调度器仍用废弃布尔过滤**（`dispatcher.rs:1186`）——规范明确点名的**安全反模式**仍在生产
3. **CIP-23 Result Verifier 不调用 VerifyCae**（`result-verifier/src/verifier.rs:291`）——`// TODO: verify TEE attestation` 字面 TODO，**Deterministic 模式实际未验签**
4. **CIP-9 PoR `shard_inclusion_proof` 硬编码空**（`cbfs/node/src/handler.rs:793`）——**PoR 在密码学层面未生效**
5. **CIP-31 储存费率差 10×**——经济参数应通过治理修正
6. **CIP-8 Slash 仍是 stub**（`session.rs:371-380`）——返回 `UnsupportedInstruction`，等 CIP-2 dispute arbitration milestone

### 6.2 大的结构性缺口（按依赖排序）

1. **CIP-4 §12 状态租金**——完全未实现，链上状态膨胀无遏制
2. **系统 Actor 地址空间 `0x0D-0x13`**——阻塞 CIP-10/14/15/18/28
3. **Gateway HTTP edge**——阻塞 CIP-14/15/16/18/19 整个 ingress 栈
4. **CIP-10 容器运行时**——runner 当前为进程内执行，所有沙盒/计费/GPU 工作待启动
5. **CIP-11 QUIC 推送**——仍依赖 5 秒轮询作业
6. **CIP-12 双院治理**——当前 demo 级，所有 Tier 0-4、安全理事会、时间锁待建
7. **CIP-21/22 DeFi 栈**——全空白
8. **CIP-13 Delegation v2**——opcode 已 spec 端标 TBD ≥87，实装待启动

### 6.3 P0（最高 ROI 收尾，1-3 周）

| 项 | 工作量 | 收益 |
|---|---|---|
| **CIP-8 Slash 接通 CIP-2 verifier-arbitration** | 中（依赖 CIP-2 dispute milestone）| CIP-8 ✅ 100% |
| **CIP-3 lane multiplier 落代码** | 小（单文件） | CIP-3 →  ✅ 85%；解 lane 预算 4× 偏差 |
| **CIP-9 GET_MANIFEST RPC + ManifestCommitted event** | 中（CBFS 接 RPC） | CIP-9 → ✅ 90%；解锁 CIP-15 整族 |
| **CIP-29 Phase 2 异步 fire 完整化 + bid orderbook 持久化** | 中（事件子系统已有基础） | CIP-29 → ✅ 85% |
| **CIP-1 carry-forward bug 修复** | 小（`speculative.rs:751` reindex） | 阻断 timer 永久丢失 |
| **CIP-23 移除废弃布尔过滤 + Result Verifier 接 VerifyCae** | 中 | 解除已知安全反模式 |
| **CIP-17 接口对齐**（补 `block_hash`、`absent`、`prove` 字段） | 小 | CIP-17 → ✅ 95% |
| **CIP-20 事件 + `on_transfer` + hook cells 上限** | 中 | CIP-20 → ✅ 95%；解锁 indexer / 合规 |
| **CIP-26 事件 + per-call 加载 gas** | 小 | CIP-26 → ✅ 100% |

### 6.4 P1（v2 系列激活前置，1-2 月）

| 项 | 工作量 | 解锁 |
|---|---|---|
| **CIP-13 delegation handlers 重号到 ≥87 + 实装** | 大 | CIP-13 Runner 委托 + 解锁 v2 经济模型 |
| **CIP-23 v2 CAE 流水线 + 证书链 + nonce GC** | 大 | CIP-23 → 🟢 60%；解锁 Deterministic 模式真正可用 |
| **CIP-14 v2 RouteRegistry/GatewayRegistry/ReceiptRegistry 落 0x0D-0x0F** | 大 | CIP-14/15/16/18/19 整族 |
| **CIP-12 双院治理 + Tier + Security Council** | 大 | CIP-12 → 🟢 70%；解锁治理可用性 |
| **CIP-24 Intel DCAP/TDX + AMD SEV-SNP 全证书链** | 中 | CIP-24 → ✅ 95%；v1.1 pre-mainnet ready |

### 6.5 P2（中型功能族，2-4 月）

- **CIP-15 v2 + Gateway HTTP serving + CORS / route_manifest 链上配置** —— CIP-15 整族
- **CIP-18 PaymentGate `0x11`** —— 整族 spec-only，需 CIP-14/15 底
- **CIP-10 OCI 容器运行时** —— 需 OCI / cgroups / GPU 接入
- **CIP-19 MCP Ingress** —— 反转 `runner-mcp` 方向 + Gateway 集成
- **CIP-4 §12 状态租金**——全表实现 + 治理键 + eviction loop

### 6.6 P3（生态扩展，4 月+）

CIP-7 流加密 / CIP-11 QUIC push / CIP-21 DEX / CIP-22 拍卖 / CIP-28 BankActor / CIP-31 完整租金分账

### 6.7 治理建议

1. **建立单一权威的系统 actor / 操作码 / StatePrefix 分配表**——当前 drift.md 已收口主要冲突，应制度化为持续维护文档
2. **CIP 文档与代码漂移定期同步**——已存在的 `<Warning>` 块（CIP-3、CIP-20）应制度化
3. **将 `node/docs/spikes/cip-code-audit.md` 提升为持续维护文档**
4. **采纳 WP Part II 9 个 Delta**——其中 Delta 6 已在 v2.r2 落地，其余应继续推进

---

## 七、白皮书创世参数 vs 代码逐项核对

WP §13 + §17 锁定的创世参数，逐项与代码对照：

### 7.1 执行（Execution）

| WP 参数 | WP 值 | 代码值 | 状态 | 证据 |
|---|---|---|---|---|
| `memory_per_call` | 10 MiB | 10 MiB | ✅ | `types/src/constants.rs` |
| `storage_quota_per_actor` | 1 MiB（最大 8 MiB） | 同 | ✅ | 同上 |
| `reentrancy_depth` | 32 | 32 | ✅ | 同上 |
| `fanout_per_tx` | 1024 | 1024 | ✅ | 同上 |
| `mailbox_capacity_bytes` | 1,000,000 | 1,000,000 | ✅ | 同上 |
| `dedup_window` | 10,000 blocks | 10,000 | ✅ | 同上 |
| `/tmp` 上限 | 256 KiB | — | ❓ | 未单独核对 |
| 递归限制 | 256 | — | ❓ | RustPython 默认 |
| `PYTHONHASHSEED` | 0 | — | ❓ | 未直接验证 |
| `MAX_TIMERS_PER_ACTOR` | 1,024（§5.1a） | 1,024 | ✅ | `constants.rs:184` |

### 7.2 双计量费率（Dual Basefee）— §4.2 / §17.8

| WP 参数 | WP 值 | 代码值 | 状态 | 备注 |
|---|---|---|---|---|
| **`T_c`（cycles target）** | **10,000,000** | **20,000,000** | ⚠️ **偏差** | `constants.rs:46` `BLOCK_CYCLES_TARGET=20_000_000`（2026-04-15 amendment） |
| `cycles cap` | 20,000,000 | — | ❓ | 实现以 target 形式 |
| **`T_b`（cells target）** | **500,000** | **4,000,000** | ⚠️ **偏差 8×** | `constants.rs:50` `BLOCK_CELLS_TARGET=4_000_000` |
| `cells cap` | 1,000,000 | — | ❓ | 同上 |
| **`α`（BASEFEE_ALPHA）** | **8** | **96** | ⚠️ **偏差 12×** | `constants.rs:78-108` `BASEFEE_ALPHA=96` |
| **`δ`（max change）** | **0.125 (12.5%)** | **1/96** | ⚠️ **偏差** | `BASEFEE_MAX_CHANGE_DENOM=96`（≈ 1.04%/block，更平滑） |
| `MIN_BASEFEE` | 1 | 10,000 | ⚠️ **偏差** | `MIN_BASEFEE=10_000`（满足 `MIN ≥ DENOM×100` 的 const-assert） |
| basefee burn | 100% | 100% | ✅ | `basefee.rs:201-206` |

> **解读**：α/δ 的偏差并非 bug——代码采用更平滑的市场更新参数（每块最多 ~1% 变化），但 **WP 文本未更新**。如执行 WP，应在 WP 中将 α=96 等加入或在 CIP-3 amendment 中正式锁定。

### 7.3 共识（Consensus）— §13

| WP 参数 | WP 值 | 代码值 | 状态 |
|---|---|---|---|
| `block_time` | 1 s | 1 s | ✅（5/26 统一 L-5）|
| `finality` | ~2 s | ~2 s | ✅ |
| `epoch` | 3600 blocks (~1h) | 3600 | ✅ |
| `unbonding_period` | 7 days | 7 days | ✅ |
| `jail_period` | 24 h | 24 h | ✅ |
| `double_sign_slash` | 1% | 1% | ✅ |
| 共识协议 | Simplex BFT | Simplex BFT | ✅ |
| 验证器集 | self-stake only（delegation v2 deferred） | self-stake only | ✅ |

### 7.4 专用 Lane — §6.3 / §17.9

| Lane | WP 预留容量 | WP 周期预算 | 代码值 | 状态 |
|---|---|---|---|---|
| **System** | 5% | 500,000 cycles | 40,000,000 | ⚠️ 80× 偏差 |
| **Timer** | 20% | 2,000,000 | 8,888,890 | ⚠️ 4.4× 偏差 |
| **Runner** | 25% | 2,500,000 | 8,888,888 | ⚠️ 3.6× 偏差 |
| **User** | 50% | 5,000,000 | 22,222,222 | ⚠️ 4.4× 偏差 |
| 各 lane 费率乘数 | 1.0× | **lane_fee_multiplier 缺失** | ❌ | **无 `lane_fee_multiplier` 符号** |

> **解读**：所有 lane 预算 vs WP 偏移 ≥3.6×（System 偏差 80× 最大，但与 WP 一致——WP 的 0.5M 显然过小，代码 40M 接近合理值）。**这是 WP 与代码间的最大数值漂移**。代码本身 `constants.rs:44-45` 已自承 WP §4.3 偏离。

### 7.5 链下计算（Off-chain）— §13

| WP 参数 | WP 值 | 代码状态 | 备注 |
|---|---|---|---|
| 委员会 `M`/`N` (v1 fixed) | 5/3 | 5/3 ✅ | 静态默认值匹配 |
| 委员会 `M`/`N` (v3 adaptive) | `M = clip(ceil(2·log₂(N_active) / max(HHI, 0.01)), 3, 9)` | ❌ | HHI 自适应未实现 |
| `challenge_window` | 15 min | ✅ | `verifier.rs:27` doc |
| `challenge_bond` | 100 CBY | ✅ | 已实现 |
| `runner_stake_floor` | 10,000 CBY | ✅ | `dispatcher.rs:1218-1226` |
| `dispute_window_blocks` | 75 | ✅ | `constants.rs:235` |
| `reputation_half_life_blocks` | 1,209,600 (~14 天 @1s) | 🟡 | 事件账本声誉系统在，14 天半衰期 EMA 未明确证据 |
| `aggregator_eligibility_percentile` | 50 (p50) | ❌ | 不存在 |
| **`aggregator_bonus_bps`** | **150 (1.5%)** | ❌ | **无聚合者奖励路径** |
| `non_reveal_slash_bps` | 2500 (25%) | ❌ | 无 |
| `slash_distribution.{burn_bps, submitter_bps, treasury_bps}` | (10000, 0, 0) | ❌ | 无 `SlashDistribution` 结构 |
| 验证模式总数 | 6 | 6 | ✅ |

### 7.6 状态租金（State Rent）— §13 / §17.5（规范 CIP-4 §12）

| WP 参数 | WP 值 | 代码状态 |
|---|---|---|
| `target_state_size` | governance-tunable | ❌ |
| `grace_period` | 7 rent-epochs | ❌ |
| `warning_period` | 3 rent-epochs | ❌ |
| `catch_up_fee` / `rent_catchup_bps` | 10% / 1000 | ❌ |
| `reserve_multiplier` | 0.1 (5 weeks 等价) | ❌ |
| `rent_rate` | 0.001 CBY/byte/year | ❌ |
| `rent_epoch_length` | 86,400 blocks (~1天) | ❌ |
| `eviction_threshold_epochs` | 10 | ❌ |
| `grace_threshold` | 10,240 bytes (10 KB) | ❌ |
| 整个状态租金子系统 | (链上扣费 + 宽限 + eviction + 恢复) | ❌ |

> **§17.5 是 WP 中最完整的具体子系统规范之一，但代码 100% 未实现。** 同时 WP 自身有「CBY-denominated 监测条款」要求 Foundation 每月公布 USD 价值——这部分链下流程也未启动。

### 7.7 经济（Economics）— §8 / §13

| WP 参数 | WP 值 | 代码/链上 |
|---|---|---|
| `supply` 总发行量 | 1,000,000,000 CBY | ✅ |
| `company_reserve` | 66.67% | (genesis 配置) |
| 通胀计划 | 8%/6%/4%/3%/2% | ❓ 未核对生产代码 |
| `basefee burn` | 100% | ✅ |
| `runner_fee_burn` | 10% | ✅ |
| `job_fee_to_treasury` | 1% | ✅ |
| `runner_payout` | 89% | ✅ |
| Slashed stake → burn | 100% | ✅（HOLD path） |

### 7.8 数据可用性 — §7

| WP 参数 | WP 值 | 代码 |
|---|---|---|
| `Inline blob cap` | 64 KiB | ✅ |
| 链上 commitment | multihash | ✅ |

### 7.9 关键 WP 锁定但代码不一致的项目（一句话总结）

- **`T_c` 10M vs 代码 20M**（target）
- **`T_b` 500K vs 代码 4M**（target，8× 偏差）
- **`α=8` vs 代码 96**（12× 偏差）
- **`δ=0.125` vs 代码 1/96**（更平滑）
- **Lane 预算** WP 与代码全线 ≥3.6× 偏差
- **Lane fee multiplier** WP 明确 1.0× 各 lane，代码无该符号
- **State Rent** WP §17.5 全表代码 0% 实现
- **Aggregator bonus 1.5%** WP §13 + §8.4 写死，代码未实现
- **System actor 0x1D** WP §9 缺，代码新增（CIP-29 host-intercepted virtual 激活模型）

---

## 八、白皮书 Part II 九个 Delta 实现状态

Part II 是 v2 提案的 9 个 Delta（前瞻性，Delta 6 已采纳进 WP v2.r2 主体；其余仍为提案）。

| Delta | 主题 | 状态 | 备注 |
|:---:|---|---|---|
| **1** | Gateway stake / operating balance 分离 | ❌ 0% | CIP-14 v2 待激活 |
| **2** | 路由 CORS 优先级 + Read-only handler 协议原语 | 🟡 — Runner 侧分离已隐式；PVM read-only + trap 表实装但端点路径未对齐 | CIP-15 v2 / CIP-14 v2 待激活 |
| **3** | 延迟结果存储模式（`RECEIPT_REGISTRY` 共享 pruning loop） | ❌ 0% | `0x0F` 未分配，CIP-14 v2 §8 |
| **4** | TEE 三层 chain（系统保留选择器 + CAE）| 🟡 25% → 30% | CIP-23 签名验签骨架在；CAE / 证书链 / nonce 仍缺；TEE keys ops 60-63 由 CIP-24 推动落地 |
| **5** | STORAGE_MANAGER 持有 actor 配置（route_manifest / cors_config）| ❌ 0% | CIP-15 v2 §4.1 待激活 |
| **6** | §9 表修正 + v2 地址段（0x0A = STORAGE_MANAGER）| ✅ **已纳入 v2.r2** | 本会话已加状态列 + 新增 `0x1D` 行 |
| **7** | Payments（PaymentGate `0x11`、MPP+x402、4 模型）| ❌ 0% | CIP-18 r2 待激活 |
| **8** | MCP Ingress（actor 即 MCP server）| ❌ 0% | CIP-19 待激活，需 CIP-14/15/18 底 |
| **9** | Cross-Chain L1+L2+L3 | 🟢 60% | CIP-25 Cowboy↔Ethereum demo 桥可用，runner-committee backend 已部署 |

### 8.1 Delta 实施进度分组

- **已落地**：Delta 6（v2.r2 已采纳）、Delta 9（CIP-25 ~60%）
- **部分落地**：Delta 2（PVM read-only）、Delta 4（CIP-23 签名验签 + TEE keys ops）
- **完全未实施**：Delta 1、3、5、7、8

### 8.2 Delta 7-8（支付 + MCP）— 平台货币化基础

Delta 7（PaymentGate）和 Delta 8（MCP Ingress）共同构成"actor 货币化"的核心架构层。WP v1 完全没有这两层；Delta 7-8 是为了让 Cowboy 平台对接 AI agent 经济而新增的方向。

**当前阻塞**：Delta 7 依赖 `0x11`、Delta 8 依赖 Gateway（CIP-14/15）+ Delta 7。整条链路代码 0%。

### 8.3 Delta 9 — 跨链架构与 §16 的张力

WP §16.2 明确："Cowboy 依赖第三方桥基础设施 ... 协议不实现自身的桥验证器集"。但 CIP-25（+ Delta 9）提出 **runner-attested committee** 作为 L1 后端，事实上**就是一个协议级的桥验证器集**（虽然复用 CIP-2 的 Runner Registry）。

Delta 9 的修订方案：**WP §16.2 的"无协议验证器集"应窄读为"无单一强制桥验证器集"**；CIP-25 的 `IChainAnchor` 允许第三方与 Cowboy-runner backend 共存。

代码已经实施 runner-committee 路径（`examples/bridge/` 完整 Cowboy↔Ethereum，已含 `JobType::PublishChainRoot`、Anchor_C、`CowboyLightClient.sol`、L2 Mailbox、L3 资产桥），事实优先于文档；WP 需采纳 Delta 9 来消除自相矛盾。

---

## 九、与 5/15 audit 不变项

下列 CIP 的状态自 5/15 audit 起没有显著变化，本审计沿用：

- **未变 ❌ 0%**：CIP-10 / CIP-11 / CIP-13 / CIP-16 / CIP-18 / CIP-19 / CIP-21 / CIP-22 / CIP-28
- **未变 🟠 5-25%**：CIP-1 / CIP-7 / CIP-14 / CIP-15 / CIP-31
- **未变 🟢/✅**：CIP-2 / CIP-3 / CIP-4 / CIP-5 / CIP-6 / CIP-17 / CIP-20 / CIP-25 / CIP-26

详细分析请回溯 [`2026-05-15_CIP_IMPLEMENTATION_AUDIT_CN.md`](./2026-05-15_CIP_IMPLEMENTATION_AUDIT_CN.md) §二、§三、§六。

---

## 十、结语

代码库整体处于**主干能力完整、外围生态待铺开、密码学基础设施大幅推进**的阶段。5/26 相对 5/15 最显著的两个意外：

### 10.1 两大突破性进展

1. **CIP-24（CBSS）从未列入 5/15 audit 到 5/26 ~80%** —— 41,000+ 行代码（node 11.6K + cbss workspace 29.4K），是当前最复杂的单一子系统之一。21 handlers 全实装，独立守护进程 `cbssd` + 完整密码学库（BLS12-381 阈值 IBE + DKG + proxy registry + release receipt + liveness + reshare + forced deregister）。仅留 Intel DCAP/TDX 与 AMD SEV-SNP 全证书链校验到 pre-mainnet milestone。

2. **CIP-29 从 <5% 到 55%** —— Event Hooks 在 11 天内实装了完整 Phase 1 + Phase 2 框架。`0x1D` 虚拟 actor + 3 read RPCs + sync/async fire + EmitOrigin DeferredTx pattern 都在代码。引入了协议级的新激活模式（host-intercepted virtual actor），与传统的部署型 system actor（`0x01-0x0F`）并存。

### 10.2 整体趋势

- ✅/🟢 等级 CIP 数从 12 个增至 13 个（CIP-29 升级 + CIP-24 进入榜单）
- ❌ 等级 CIP 数 9 个持平（变化项移走 + 新挑战项进来）
- 平均完成度从 ~40% 升至 ~45%

### 10.3 已成熟（生产级）

CIP-2（链下计算）、CIP-5（定时器）、CIP-6（SDK）、CIP-8（MPP Session，仅 Slash stub）、CIP-20（代币）、CIP-25（跨链桥 demo）、CIP-26（账户库）。

这些 CIP 均有完整实现 + 测试覆盖 + 端到端示例，且与 WP Part I 描述吻合。

### 10.4 接近完工（🟢，建议收尾）

CIP-3（费模型——lane multiplier 缺）、CIP-4（状态租金 §12 缺）、CIP-9（PoR 经济缺）、CIP-17（接口名差异）、CIP-24（仅 vendor collateral）、CIP-29（异步 fire 完整化）。

### 10.5 完全空白或仅 demo

CIP-1 v3、CIP-7、CIP-10、CIP-11、CIP-13、CIP-14、CIP-15、CIP-16、CIP-18、CIP-19、CIP-21、CIP-22、CIP-28、CIP-31，以及 CIP-12 的双院/理事会层、WP Part II Delta 3/5/7/8。

### 10.6 三层（WP / CIP / 代码）漂移管理

本审计已建立稳定的工作流：

- `wiki/drift.md` 跟踪进行中漂移（C-1 ~ C-4 + L-5 本期已收口）
- `refs/cips/cip-13-runner-delegation.md` §1 作为代码权威 opcode master table
- `refs/wiki/entities/system-actors.md` 作为代码权威系统 actor 表
- 每轮跨 CIP 修订后追加 `wiki/log.md` 时序日志

**1. WP ↔ 代码漂移**：α=8/96、Lane 预算 ≥3.6×、`T_b` 8× 偏差、State Rent 100% 未实现、Lane fee multiplier 符号缺失、`0x1D` virtual actor 模式 WP 未列。

**2. WP ↔ CIP 漂移**：Delta 6 已落地（§9 表修正）；Delta 9 与 §16.2 张力待 WP 正式采纳。

**3. CIP ↔ 代码漂移**（5/26 已收口）：CIP-28 0x0D→0x13、CIP-29 0x0A→0x1D、CIP-13 v2 opcode 标 TBD ≥87、CIP-9 §13 AMEND 9-J 补完。

### 10.7 下次审计建议

4-6 周后做下一轮 baseline，重点核：
- **CIP-13 v2** 实装进展（opcode 重号到 ≥87 后落地）
- **CIP-23 v2** CAE 流水线 + 证书链
- **CIP-14 v2** RouteRegistry/GatewayRegistry/ReceiptRegistry 落 `0x0D-0x0F`
- **CIP-24** Intel DCAP/TDX + AMD SEV-SNP 全证书链 vendor collateral

---

**报告完**
