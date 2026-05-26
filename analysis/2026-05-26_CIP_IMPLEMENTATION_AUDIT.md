# Cowboy 平台代码完成度审计报告（2026-05-26）

**审计日期**：2026-05-26
**前次基线**：[`2026-05-15_CIP_IMPLEMENTATION_AUDIT.md`](./2026-05-15_CIP_IMPLEMENTATION_AUDIT.md)（11 天前并行 9 代理审计）
**审计范围**：
- **白皮书**：`refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md` (v2.r2)
- **CIP 文档**：`refs/cips/` 30 篇（cip-1 到 cip-31，含 cip-15-gateway-implementation；cip-27/30 未起草）
- **代码**：`node/` + `runner/` + `cbss/` + `cbfs/`

**审计方法**：以 5/15 audit 为 baseline，叠加 2026-05-26 spec ↔ code 大对齐过程中对各代码仓的探针发现（详见 `wiki/log.md` 5/26 enhance/lint 条目）。状态有变更的 CIP 给出精确证据；状态不变的复用 5/15 audit 结论并标注 "5/15 audit baseline"。

**标记**：✅ ≥85% / 🟢 60-85% / 🟡 25-60% / 🟠 5-25% / ❌ <5%

---

## 一、自 5/15 audit 的关键变化

| CIP | 5/15 状态 | 5/26 状态 | 触发证据 |
|---|---|---|---|
| **CIP-24（CBSS）** | (未列入 5/15 audit) | 🟢 **~80%** | 代码大规模落地：`node/` 中 11,600 行（`execution/src/cbss.rs:7738` + `types/src/cbss.rs:1906` + `rpc/src/handlers/cbss.rs:1956`）+ 独立 `cbss/` workspace 29,448 行（cbssd / cbss-crypto / cbss-client / cbss-types）；**21 个 SystemInstruction handlers 全在代码**（60-63 TEE keys + 68-84 CBSS main，`node/types/src/execution.rs:653-681`）；BLS12-381 阈值 IBE / DKG / proxy registry / release receipt 全栈在 |
| **CIP-29（事件钩子）** | ❌ <5% | 🟢 **~55%** | `node/types/src/constants.rs:156` `EVENT_SUBSCRIPTION_SYSTEM_ACTOR = 0x1D`；三文件 914 行：`storage/src/event_subs.rs` (410) + `execution/src/execution/event_fire.rs` (151) + `execution/src/execution/event_sub_system_actor.rs` (353)；3 read RPCs (`get_rank` / `get_topic_orderbook` / `get_min_bid_for_rank`) 在 `pvm_host::call_actor:1867-1881` 拦截路由；`EmitOrigin` DeferredTx metadata tag + `MAX_TOPIC_BYTES=64` / `MAX_EVENT_PAYLOAD_BYTES=4096` / `ASYNC_FIRES_PER_DEFER_TX=64` 常量；StatePrefix 改用 `EVENT_SUB=0x0E` / `EVENT_SUB_INDEX_VALUE=0x0F`（解开与 CIP-26 的撞号）；spec 端 §2.6 由本次审计同步对齐到 `0x1D` |
| **CIP-9** | 🟡 70% | 🟢 73% | §13 AMEND 9-J 补完：`SubmitDrainRelayProposal`(85) / `SubmitAutoDrainPolicyProposal`(86) 已在代码（`node/execution/src/execution/system_instruction.rs:747-905`），本次审计把 spec 与代码完全对齐 |
| **CIP-12** | demo 级 | 🟡 30% | `ProposalPayloadKind` 从 1 个 `UpdateBasefeeConfig` 扩到 3 个（+`DrainRelay` + `UpdateAutoDrainPolicy`，`node/runner/src/types.rs:835`）；`SubmitDrainRelayProposal`(85) / `SubmitAutoDrainPolicyProposal`(86) 通用 `ExecuteProposal`(47) 路径在 |
| **CIP-23** | 🟡 ~25% | 🟡 ~30% | TEE Verifier 支持 opcodes 60-63 已入代码（`SYS_REGISTER_TEE_TRUSTED_KEY` 等，由 CIP-24 §3.3 推动落地；CIP-23 v2 复用）；但 CAE 复合证明 / 证书链 / nonce 重放保护 / dispatcher 改用 MeasurementBinding 过滤仍缺 |
| **CIP-8** | ✅ ~90% | ✅ ~92% | 6 opcodes 52-57 全在代码确认（`SYS_SESSION_OPEN`…`SYS_SESSION_SLASH`）；**Slash 仍 stub**（`node/execution/src/runner/session.rs:371-380` 返回 `UnsupportedInstruction`，等 verifier-arbitration milestone）|

其余 24 个 CIP 状态未变（详见下表）。

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
| **CIP-1** | Actor 调度器 v3 (EIP-1559 timer lane) | 🟠 ~5% | 仍仅 CIP-5 FIFO；v3 分层日历 + GBA + 公平权重全无 |
| **CIP-2** | 链下可验证计算 v1 | ✅ ~85% | 核心骨架完整（RUNNER_REGISTRY / JOB_DISPATCHER / RESULT_VERIFIER + VRF + commit-reveal + 6 modes）；v2 DNS check / v3 机制改革缺失 |
| **CIP-3** | Cycles+Cells 双计量费模型 | 🟢 70% | EIP-1559 双计量完备（`basefee.rs`）；lane multiplier 全无；lane 预算与规范偏差 4 倍 |
| **CIP-4** | 链上状态存储 | 🟢 75% | QMDB + Merkle 证明完整；§12 状态租金完全缺失；StatePrefix 布局与规范偏差 |
| **CIP-5** | 原生定时器 (revised) | ✅ ~93% | Model B 端到端完整；carry-forward bug 已知（`speculative.rs:751`） |
| **CIP-6** | Python SDK / Actor API | ✅ ~95% | 全表面：三种调用原语 / FSM 编译器 / Continuation；本会话已把 CIP-6 spec 同步到 "In-PVM Actor SDK (cowboy_sdk)" 新框架 |
| **CIP-7** | 简单流协议 r2 | 🟠 ~10% | 仅一个 Python demo；`0x12 STREAM_KEY_MANAGER` 系统 actor 全无；spec r2 已修 v1 `0x06` 冲突 |
| **CIP-8** | MPP Session (追溯定档) | ✅ ~92% | 6 opcodes 52-57 全在代码；链上 `SESSION_ACTOR=0x0C` + 链下 voucher 库（`runner-common/voucher.rs`）+ EIP-712 domain；**仅 `handle_session_slash` 是 `UnsupportedInstruction` stub** (`session.rs:371-380`)，等 CIP-2 dispute arbitration milestone |
| **CIP-9** | Runner Storage / CBFS | 🟢 73% | 数据面齐全（StorageCommitment / CapToken / Relay 调度）；**§13 DrainRelay / AutoDrainPolicy 治理面新对齐** (opcodes 85/86)；GET_MANIFEST RPC 仍缺、ManifestCommitted 事件未发、PoR 经济未完全挂 |
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

## 三、白皮书 v2.r2 进度

### 3.1 核心架构（Part I §1-§17）

| 章节 | 进度 | 说明 |
|---|---|---|
| Abstract / Architectural Overview | 🟢 ~75% | 四大支柱有代码（Actor / Timer / Off-chain compute / Dual gas） |
| §1 Actor 模型 | ✅ ~85% | 确定性 PVM / 消息驱动 / Mailbox 全在；部分 PVM 限制（大整数 VM-level 拦截）仅 preamble 级 |
| §2 Native Timer | ✅ ~93% | CIP-5 revised Model B 端到端完整 |
| §3-§5 Off-chain Compute | ✅ ~85% | Runner 市场 + VRF + commit-reveal + 6 modes（CIP-2） |
| §6 Consensus | ✅ ~90% | Simplex BFT + BLS12-381 + ~1s block time（本审计统一到 1s） |
| §9 系统 Actor 表 | 🟢 ~62% | 13/20 槽实装（`0x01-0x0C` 部署 + `0x1D` 虚拟）；`0x0D-0x13` spec-only；v1 `0x0A` 错配已由 Delta 6 修正 |
| §13 创世参数表 | 🟡 ~50% | basefee / cycle target / cells target 在代码；不少经济参数 placeholder |
| §17 完整费用模型 | 🟢 ~80% | EIP-1559 双计量 / 89/10/1 分账 / 销毁 / Treasury 全在；lane multiplier 缺失 |

### 3.2 Part II 九个 Delta

| Delta | 主题 | 状态 | 备注 |
|---|---|---|---|
| Delta 1 | Gateway stake / operating balance 分离 | ❌ 0% | CIP-14 v2 待激活 |
| Delta 2 | 路由 CORS 优先级 | ❌ 0% | CIP-15 v2 待激活 |
| Delta 3 | Container Registry `0x10` | ❌ 0% | CIP-10 v2 待激活 |
| Delta 4 | TEE 三层 chain | 🟡 25% | CIP-23 签名验签骨架在；CAE 仍缺 |
| Delta 5 | STORAGE_MANAGER 配置位 | ❌ 0% | CIP-15 v2 §4.1 待激活 |
| Delta 6 | §9 表修正 + v2 地址段 | ✅ 已纳入 v2.r2 | 本会话已加状态列 + 新增 `0x1D` 行 |
| Delta 7 | Payments（PaymentGate `0x11`） | ❌ 0% | CIP-18 r2 待激活 |
| Delta 8 | MCP Ingress | ❌ 0% | CIP-19 待激活 |
| Delta 9 | Cross-Chain L1+L2+L3 | 🟢 60% | CIP-25 Ethereum demo 桥可用 |

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

---

## 五、优先级建议

### 5.1 P0（最高 ROI 收尾，1-3 周）

| 项 | 工作量 | 收益 |
|---|---|---|
| **CIP-8 Slash 接通 CIP-2 verifier-arbitration** | 中（依赖 CIP-2 dispute milestone）| CIP-8 ✅ 100% |
| **CIP-3 lane multiplier 落代码** | 小（单文件） | CIP-3 →  ✅ 85%；解 lane 预算 4× 偏差 |
| **CIP-9 GET_MANIFEST RPC + ManifestCommitted event** | 中（CBFS 接 RPC） | CIP-9 → ✅ 90%；解锁 CIP-15 整族 |
| **CIP-29 Phase 2 异步 fire 完整化 + bid orderbook 持久化** | 中（事件子系统已有基础） | CIP-29 → ✅ 85% |

### 5.2 P1（v2 系列激活前置，1-2 月）

| 项 | 工作量 | 解锁 |
|---|---|---|
| **CIP-13 delegation handlers 重号到 ≥87 + 实装** | 大 | CIP-13 Runner 委托 + 解锁 v2 经济模型 |
| **CIP-23 v2 CAE 流水线 + 证书链 + nonce GC** | 大 | CIP-23 → 🟢 60%；解锁 Deterministic 模式真正可用 |
| **CIP-14 v2 RouteRegistry/GatewayRegistry/ReceiptRegistry 落 0x0D-0x0F** | 大 | CIP-14/15/16/18/19 整族 |
| **CIP-12 双院治理 + Tier + Security Council** | 大 | CIP-12 → 🟢 70%；解锁治理可用性 |

### 5.3 P2（中型功能族，2-4 月）

- **CIP-15 v2 + Gateway HTTP serving + CORS / route_manifest 链上配置** —— CIP-15 整族
- **CIP-18 PaymentGate `0x11`** —— 整族 spec-only，需 CIP-14/15 底
- **CIP-10 OCI 容器运行时** —— 需 OCI / cgroups / GPU 接入
- **CIP-19 MCP Ingress** —— 反转 `runner-mcp` 方向 + Gateway 集成

### 5.4 P3（生态扩展，4 月+）

CIP-7 流加密 / CIP-11 QUIC push / CIP-21 DEX / CIP-22 拍卖 / CIP-28 BankActor / CIP-31 完整租金分账

---

## 六、与 5/15 audit 不变项

下列 CIP 的状态自 5/15 audit 起没有显著变化，本审计沿用：

- **未变 ❌ 0%**：CIP-10 / CIP-11 / CIP-13 / CIP-16 / CIP-18 / CIP-19 / CIP-21 / CIP-22 / CIP-28
- **未变 🟠 5-25%**：CIP-1 / CIP-7 / CIP-14 / CIP-15 / CIP-31
- **未变 🟢/✅**：CIP-2 / CIP-3 / CIP-4 / CIP-5 / CIP-6 / CIP-17 / CIP-20 / CIP-25 / CIP-26

详细分析请回溯 [`2026-05-15_CIP_IMPLEMENTATION_AUDIT.md`](./2026-05-15_CIP_IMPLEMENTATION_AUDIT.md) §二、§三、§六。

---

## 七、结语

**最显著的两个意外**：
1. **CIP-24（CBSS）从未列入 5/15 audit 到 5/26 ~80%** —— 41,000+ 行代码（node 11.6K + cbss workspace 29.4K），是当前最复杂的单一子系统之一。21 handlers 全实装，独立守护进程 `cbssd` + 完整密码学库。仅留 Intel DCAP/TDX 与 AMD SEV-SNP 全证书链校验到 pre-mainnet milestone。
2. **CIP-29 从 <5% 到 55%** —— Event Hooks 在 11 天内实装了完整 Phase 1 + Phase 2 框架。`0x1D` 虚拟 actor + 3 read RPCs + sync/async fire + EmitOrigin DeferredTx pattern 都在代码。

**整体趋势**：
- ✅/🟢 等级 CIP 数从 12 个增至 13 个（CIP-29 升级 + CIP-24 进入榜单）
- ❌ 等级 CIP 数从 9 个减至 9 个（持平；变化项移走 + 新挑战项进来）
- 平均完成度从 ~40% 升至 ~45%

**Spec ↔ code 双向漂移管理**已建立稳定的工作流：
- `wiki/drift.md` 跟踪进行中漂移
- `refs/cips/cip-13-runner-delegation.md` §1 作为代码权威 opcode master table
- `refs/wiki/entities/system-actors.md` 作为代码权威系统 actor 表
- 每轮跨 CIP 修订后追加 `wiki/log.md` 时序日志

**下次审计建议**：4-6 周后做下一轮 baseline，重点核 CIP-13 / CIP-23 v2 / CIP-14 v2 三大未激活提案的进展。

---

**附**：本审计的逐项探针证据在 `wiki/log.md` 5/26 的 lint+ingest 与 enhance 两条目中追溯。
