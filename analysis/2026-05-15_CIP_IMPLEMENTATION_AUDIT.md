# Cowboy 平台代码完成度审计报告

**审计日期**：2026-05-15
**审计范围**：
- **白皮书**：`/home/ubuntu/workspace/refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md`（v2.r2，1530 行；Part I v1 + Part II 9 个 Delta + Part III 对齐审计）
- **CIP 文档**：`/home/ubuntu/workspace/refs/cips/`（35+ 篇）
- **实现代码**：`/home/ubuntu/workspace/node/`、`/home/ubuntu/workspace/runner/`、`/home/ubuntu/workspace/cbfs/`、`/home/ubuntu/workspace/node/examples/`

**审计方法**：白皮书作为顶层架构基线 → 9 个并行代理按功能域同时核对 CIP 规范与代码 → 三方一致性比对。逐项 grep + Read，附 `file:line` 证据。
**标记图例**：✅ 已实现 / 🟡 部分实现 / ❌ 未实现 / ❓ 未找到 / ⚠️ 存在偏差

---

## 目录

- [零、白皮书架构基线（WP v2.r2）](#零白皮书架构基线wp-v2r2)
- [一、总览矩阵](#一总览矩阵)
- [二、按 CIP 详细分析](#二按-cip-详细分析)
  - [2.1 Actor 与计算层（CIP-1/2/6）](#21-actor-与计算层cip-126)
  - [2.2 存储与文件系统（CIP-4/9/31）](#22-存储与文件系统cip-4931)
  - [2.3 Runner 系统（CIP-10/11/13）](#23-runner-系统cip-101113)
  - [2.4 网络与会话（CIP-7/8/15/19）](#24-网络与会话cip-781519)
  - [2.5 寻址与治理（CIP-5/12/14/16/17）](#25-寻址与治理cip-51214161-7)
  - [2.6 金融与代币（CIP-3/18/20/21/22/26/28）](#26-金融与代币cip-31820212226-28)
  - [2.7 高级特性（CIP-23/25/29）](#27-高级特性cip-232529)
- [三、横切发现](#三横切发现)
- [四、Node 仓代码资产盘点](#四node-仓代码资产盘点)
- [五、风险与优先级建议](#五风险与优先级建议)
- [六、白皮书创世参数 vs 代码逐项核对](#六白皮书创世参数-vs-代码逐项核对)
- [七、白皮书 Part II 九个 Delta 实现状态](#七白皮书-part-ii-九个-delta-实现状态)
- [八、结语](#八结语)

---

## 零、白皮书架构基线（WP v2.r2）

白皮书 `2026-03-21_cowboy-technical-whitepaper-revised-v2.md` 是顶层规范文档，分三部分：

| 部分 | 内容 | 状态 |
|---|---|---|
| **Part I** | v1 原文（17 章 + 附录 A），含 §9 系统 actor 表、§13 创世参数表、§17 完整费用模型 | 当前规范（canonical） |
| **Part II** | 9 个 Delta（CIP-14/15/16 对齐练习涌现的前瞻提案） | 提案，未采纳 |
| **Part III** | WP vs CIP 一致性审计简报 | 一次性审计，非规范 |

**冲突规则**：Part I 当前权威；Part II 一旦采纳即覆盖 Part I 对应部分；§9 系统 actor 分配规则：「如本白皮书与 CIP-2 冲突，以 CIP-2 为准」。Delta 6 进一步扩展到「如与任何已部署 CIP 冲突，以部署 CIP 为准」。

### 0.1 WP 描述的核心架构

WP **Abstract** + **Architectural Overview** 明确平台四大支柱：

1. **Deterministic Python Actors** — 确定性 PVM（Python 3.11.8）、reentrancy ≤32、内存 10 MiB、模块白名单
2. **Native Timers & Scheduler** — 分层日历队列 + GBA + 同块惩罚 + per-actor 上限 1,024
3. **Verifiable Off-Chain Compute** — Runner 市场、VRF 选举、commit-reveal、6 种验证模式
4. **Dual-Metered Gas** — Cycles + Cells 独立 EIP-1559 市场

### 0.2 WP §9 系统 Actor 表 vs 代码 vs Delta 6

WP §9 的 v1 文本与代码存在多处漂移，Delta 6 提出更正：

| 地址 | WP §9 (v1) 声称 | 代码实际 | Delta 6 修正 | 状态 |
|---|---|---|---|---|
| 0x01 | Runner Registry | `RUNNER_REGISTRY` | Runner Registry | ✅ 一致 |
| 0x02 | Job Dispatcher | `JOB_DISPATCHER` | Job Dispatcher | ✅ 一致 |
| 0x03 | Result Verifier | `RESULT_VERIFIER` | Result Verifier | ✅ 一致 |
| 0x04 | Secrets Manager | `SECRETS_MANAGER` | Secrets Manager | ✅ 一致 |
| 0x05 | TEE Verifier | `TEE_VERIFIER` | TEE Verifier | ✅ 一致 |
| 0x06 | DualBasefee | `BASEFEE_SYSTEM_ACTOR` | DualBasefee | ✅ 一致 |
| 0x07 | Entitlement Registry | `ENTITLEMENT_REGISTRY` | Entitlement Registry | ✅ 一致 |
| 0x08 | Treasury | `TREASURY` | Treasury | ✅ 一致 |
| 0x09 | Governance | `GOVERNANCE_SYSTEM_ACTOR` | Governance | ✅ 一致 |
| **0x0A** | **Container Image Registry** | **`STORAGE_MANAGER`** | **Storage Manager (CIP-9)** | ⚠️ **WP §9 v1 错误，Delta 6 修正** |
| 0x0B | (未列) | `RELAY_REGISTRY` | Relay Registry (CIP-9) | ⚠️ WP §9 v1 缺失 |
| 0x0C | (未列) | `SESSION_ACTOR` | Session Actor (CIP-8 追溯) | ⚠️ WP §9 v1 缺失 |
| 0x0D | (未列) | 未分配 | Route Registry (CIP-14 v2.r2) | ❌ 未实现 |
| 0x0E | (未列) | 未分配 | Gateway Registry (CIP-14 v2.r2) | ❌ 未实现 |
| 0x0F | (未列) | 未分配 | Receipt Registry (CIP-14 v2.r2) | ❌ 未实现 |
| 0x10 | (未列) | 未分配 | Container Registry (CIP-10 v2.r2) | ❌ 未实现 |
| 0x11 | (未列) | 未分配 | Payment Gate (CIP-18 r2) | ❌ 未实现 |
| 0x12 | (未列) | 未分配 | Stream Key Manager (CIP-7 r2) | ❌ 未实现 |

**关键发现**：WP §9 自己的 v1 文本就与代码不符（`0x0A` 应为 Storage Manager 而非 Container Image Registry），Delta 6 已识别并提出修正。WP §9 末尾确实有冲突规则脚注，但仅覆盖 CIP-2；Delta 6 扩展到 CIP-9 / CIP-10 等。

### 0.3 WP §5.1a vs §5.1b — 已部署 vs 目标设计

WP §5.1 显式区分两层：

- **§5.1a（已部署）**：CIP-5 FIFO + 同高度 FIFO 桶 + per-fire `fee_payer` + `LANE_TIMER_CYCLES=2,000,000`（20% of block per CIP-3 §2.2.3）+ `TIMER_GC_CYCLES` 独立 GC lane + per-actor 1,024 上限 + 同块禁止
- **§5.1b（目标）**：CIP-1 v3 EIP-1559 timer-lane basefee + `priority_tip` + per-actor 公平权重 `W(actor) ∈ [1,2]` + 250k auction-phase cycle cap + `priority_tier_hint` SDK 枚举

**审计观察**：代码处于 §5.1a 状态，§5.1b **目标全空**（详见本报告 §2.1）。但 §5.1a 也有一项偏差：WP 说 `LANE_TIMER_CYCLES = 2,000,000`（20% × 10M target），**代码值 `8,888,890`**——见 §六详细核对。

### 0.4 WP 直接锁定的现实

WP 文本本身（与 v2.r2 元数据）多次承认现状：

- "**CIP-9 manifest anchoring (deferred)**" — §12.2 / §17.6
- "**CIP-10 image allowlists**" — §12.2（依赖未实现的 Container Registry）
- "**ZK-Proof (v2)**" — §5 表与 §5.3，明确为 v2 未来
- "**delegation deferred to v2**" — §6 验证器集
- "**no encrypted mempool**" — §6.4 / §6.5
- "**EventListener (CIP-7, deferred; address TBD — 0x08 currently Treasury)**" — §16.3



| CIP | 主题 | 完成度 | 状态摘要 |
|---|---|---:|---|
| **CIP-1** | Actor 调度器 v3（EIP-1559 timer lane） | ~5% | 仅有 CIP-5 FIFO 基线；v3 分层日历队列、GBA、公平权重全无 |
| **CIP-2** | 链下可验证计算 v1 | ~85% | 核心骨架完整；v2 DNS 校验、v3 机制改革缺失 |
| **CIP-3** | Cycles+Cells 双计量费模型 | 🟡 70% | EIP-1559 基础完备；**执行 lane 费率倍增器全无**；lane 预算与规范偏差 4 倍 |
| **CIP-4** | 链上状态存储 | 🟡 75% | QMDB + Merkle 证明完整；**§12 状态租金完全缺失**；前缀布局与规范偏差 |
| **CIP-5** | 原生定时器 | ✅ ~93% | Model B 端到端完整；**carry-forward bug 已知**（`speculative.rs:751`） |
| **CIP-6** | Python SDK 与 Actor API | ✅ ~95% | 全表面实现：三种调用原语、FSM 编译器、连续函数、限制全对齐 |
| **CIP-7** | 简单流协议 r2 | ❌ ~10% | 仅一个 Python demo；`0x12 Stream Key Manager` 全无 |
| **CIP-8** | MPP Session（追溯定档） | ✅ ~90% | 完整 happy path，链上 0x0C + 链下 voucher 库 + 3 个 demo；仅 Slash 延后 |
| **CIP-9** | Runner Storage / CBFS | 🟡 70% | 数据面齐全；**GET_MANIFEST RPC 缺失、ManifestCommitted 事件未发、PoR 经济未挂** |
| **CIP-10** | Runner 容器运行时 | ❌ 0% | 完全未实现：无 OCI、cgroups、GPU、网络策略、Container Registry |
| **CIP-11** | Runner QUIC 推送连通 | ❌ 0% | 完全未实现：无 QUIC 通道、无 presence bitmap、无 MRU 黏性 |
| **CIP-12** | 链上治理 | 🟡 demo 级 | 仅简化 `SubmitProposal/CastVote/ExecuteProposal`；**无双院、无层级、无安全理事会** |
| **CIP-13** | Runner 质押委托 v2 | ❌ 0% | 完全未实现；**且 opcode 52-56 与 MPP Session 冲突** |
| **CIP-14** | DNS 可寻址 Actor | ❌ ~5% | 仅 `POST /actor/read` 命中只读语义；**无 Route/Gateway/Receipt Registry** |
| **CIP-15** | Gateway 实现 + 公开资产 | ❌ ~10% | 仅 CBFS 基底 + Visibility::Public；**无 Gateway HTTP 服务** |
| **CIP-16** | 自定义域名 | ❌ 0% | 完全未实现 |
| **CIP-17** | 可验证状态读 | 🟡 80% | `/proof/storage/*` 等齐全；**端点路径、`block_hash`、`absent` 字段差异** |
| **CIP-18** | 支付（PaymentGate 0x11） | ❌ 0% | 完全未实现（2026-05-11 刚定稿） |
| **CIP-19** | Gateway MCP Ingress | ❌ 0% | 依赖 CIP-14/15/18 全无；`runner-mcp` 是外向客户端，方向错 |
| **CIP-20** | 同质化代币 | 🟡 85% | 核心齐全；**`on_transfer` 后置钩子缺失、事件未发射、hook cells 上限未挂** |
| **CIP-21** | DEX 与流动性池 | ❌ 0% | 完全未实现：无 AMM 原语、无池 actor、无路由器 |
| **CIP-22** | 连续清算拍卖 | ❌ 0% | 完全未实现 |
| **CIP-23** | TEE 执行 | 🟡 ~25% | 签名验签骨架在；**无 CAE、无证书链、无 nonce 重放保护、调度器仍用废弃布尔过滤** |
| **CIP-25** | 跨链架构 | ✅ ~60% | Cowboy↔Ethereum demo 桥可用；**欺诈证明是 stub、无 ZK/optimistic 后端、无多链** |
| **CIP-26** | 账户作用域库 | ✅ ~95% | 全表面 + 端到端示例；**最成熟的 CIP 之一** |
| **CIP-28** | Agent Banking | ❌ 0% | 仅 HTML mock-up（2026-05-12 刚定稿） |
| **CIP-29** | 链上事件钩子 | ❌ <5% | 仅 fire-and-forget emit_event；**且声明的 StatePrefix 0x14/0x15 已被 CIP-26 占用、0x0A 已被 CIP-9 占用** |
| **CIP-31** | CBFS 租金表 | ❌ ~10% | 三方分账缺失、挑战债券缺失、罚没表缺失；费率值差 10× |

---

## 二、按 CIP 详细分析

### 2.1 Actor 与计算层（CIP-1/2/6）

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

**核心结论**：v1 主干完整；v2/v3 改革多项未实现。

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

**核心结论**：本审计中**最完整**的 CIP（~95%）。

✅ 全部实现（位于 `/home/ubuntu/workspace/node/pvm/Lib/cowboy_sdk/`）：
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

### 2.2 存储与文件系统（CIP-4/9/31）

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
- `SeenMessageIds (0x0A)`、`ActorCode (0x02)` 缺失

❌ **严重缺失**：
- **§12 状态租金完全未实现**——无 `rent_debt`、`grace_threshold`、`rent_rate`、`account_size_bytes`、`rent_catchup_bps`、`system:cip4:rent_*` 治理键

#### CIP-9 — Runner Storage / CBFS

**架构图**（`/home/ubuntu/workspace/cbfs/`）：
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

**核心结论**：本域**最不完整**的规范。

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

### 2.3 Runner 系统（CIP-10/11/13）

#### Runner 工作区 crate 地图（`/home/ubuntu/workspace/runner/crates/`）

- `runner-node` — 主二进制；`start_job_listener` 轮询循环
- `runner-common` — 共享类型（`JobSpec`、`JobAssignment`、`RunnerResult`）、ECDSA 签名、voucher 序列化
- `chain-client` — 链 REST 客户端
- `runner-llm`、`runner-http`、`runner-mcp`、`runner-agent` — Job 执行器
- `runner-tee` — TEE 见证生成
- `runner-storage` — CIP-9 卷编排
- `runner-registry`、`job-dispatcher`、`result-verifier`、`tee-verifier` — 系统 actor 处理器的链下 Rust 副本（测试用）
- `runner-consensus` — N-of-M 聚合 + BLS VRF 桩

#### CIP-10 — 容器运行时

**核心结论**：**完全 0% 实现**。

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
- 操作码 61-64
- `BillingAttestation` with `cgroup_digest`

> 注：`runner-agent` 中的 "Sandbox" 仅为文件路径预检（`fs_tools.rs:66`），非 OS 级隔离。

#### CIP-11 — Runner 连通与推送

**核心结论**：**完全 0% 实现**。当前用 5 秒 HTTP 轮询 + 链上心跳。

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

⚠️ **冲突**：CIP-13 v2 §1 主分配表声称 52-56 给委托，**但代码中 52-57 已被 MPP Session 使用**（`SYS_SESSION_OPEN=52` … `SYS_SESSION_SLASH=57`，`node/types/src/execution.rs:587-598`）。

#### ext_cip-2-9-10 — Runner 费用链分析

三条独立费用流：
- **Flow 1（Runner 作业支付，CIP-2）**：✅ 实现（默认 89/10/1 split）
- **Flow 2（存储租金，CIP-9）**：❌ 无 epoch 扣费循环
- **Flow 3（容器计算，CIP-10）**：❌ 完全缺失

---

### 2.4 网络与会话（CIP-7/8/15/19）

#### CIP-7 — 简单流协议 r2

**核心结论**：仅有非规范的 Python demo（`/node/cli/actors/stream_actor.py`），实现粗粒度 publish/subscribe。

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

**核心结论**：本审计**最完整**（~90%）。

✅ 已实现：
- `SESSION_ACTOR=0x0C`（`system_actors.rs:35`）
- 存储布局 `b"session:" || session_id`
- `Session`、`SessionAsset::Cby`、`SessionVoucher`（含 65 字节签名）
- EIP-712 域 `"Cowboy MPP Session" v1`（`types/src/session_eip712.rs`）
- 6 个处理器：`OpenSession`/`Deposit`/`Settle`/`CloseSession`/`Finalize`/`Slash`（最后一个返回 `Unsupported`，符合 §8.6）
- 5 项 voucher 校验（session_id、状态窗口、过期、nonce 递增、cumulative 上限）
- 89/10/1 settlement split 复用 CIP-2 SettlementConfig
- `DISPUTE_WINDOW_BLOCKS=75`
- 链下 voucher 库（`runner-common/src/voucher.rs`）含 EIP-712 域和 sign/recover
- 3 个工作 demo（`examples/mpp_session/`、`llm_session/`、`session_chain_e2e/`）

🟡 小偏差：
- `SessionStatus::Slashed{...}` 变体缺失
- 存储用 `serde_json` 而非规范的 bincode
- CIP §12 文档说"非数字操作码"，但代码实际使用 `52..=57`（文档过时）

#### CIP-15 — Gateway 实现 + 公开资产

**核心结论**：Gateway HTTP 服务**完全不存在**。

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

### 2.5 寻址与治理（CIP-5/12/14/16/17）

#### CIP-5 — 原生定时器

**核心结论**：~93% 完整。

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

**核心结论**：仅 demo 级。代码自承"Simplified vs. CIP-12"（`runner/src/types.rs:819,856`）。

✅ 已实现：
- `0x09 GOVERNANCE_SYSTEM_ACTOR`
- 操作码 45-47（`SUBMIT_PROPOSAL/CAST_VOTE/EXECUTE_PROPOSAL`）
- Proposal 存储 + RPC（`/governance/proposals` 等）
- 3 种载荷：`UpdateBasefeeConfig`、`DrainRelay`、`UpdateAutoDrainPolicy`
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

**核心结论**：本规范的链上面**完全未实现**。

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

**核心结论**：**功能上完整但接口名不同**。

🟡 已实现但名称/格式与规范差异：
- 端点：`/proof/storage/{addr}/{key}` 而非 `/state/{addr}/{key_hex}`
- 证明：QMDB MMR（BLAKE3）而非 MPT siblings（keccak）
- 响应缺 `block_hash` 和 `absent` 字段
- 无 `prove=false` 查询参数
- ✅ `/proof/multi` 批量读已实现（规范列为未来工作）

---

### 2.6 金融与代币（CIP-3/18/20/21/22/26/28）

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

**核心结论**：**完全 0% 实现**（CIP 2026-05-11 刚定稿）。

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

**核心结论**：~85% 完整。

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

**核心结论**：**完全 0% 实现**。

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

**核心结论**：本审计**最完整**之一（~95%）。

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

**核心结论**：**仅 HTML mock-up**。CIP 2026-05-12 刚定稿。

❌ 全部缺失：
- `BankActor` 系统 actor `0x0D`
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

### 2.7 高级特性（CIP-23/25/29）

#### CIP-23 — TEE 执行

**核心结论**：~25% 完整。签名验签骨架在，规范要求的复合证明全无。

✅ 已实现：
- `TEE_VERIFIER=0x05` 已分配
- `sec.tee_required` entitlement
- `CANONICAL_TEE_TYPES` 包含 `nitro`
- TEE attestation 处理器（`cbss.rs:1106-1287`）：`register_tee_trusted_key`、`submit_tee_attestation`、`revoke_tee_attestation`
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
- **`MeasurementBinding` 续期**
- **操作码漂移**：实现于 60-63，v1 规范 50-53，v2 规范 57-60，**与两个都冲突**

#### CIP-25 — 跨链架构

**核心结论**：~60% 完整，本审计中**唯一有完整跨链 demo** 的 CIP。

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

**核心结论**：**预 Phase 0**（<5%）。

✅ 仅有：
- `rt.emit_event(topic, data)` fire-and-forget（`pvm_host.rs:1399-1416`）——这是规范要扩展/替换的旧原语

❌ 全部缺失：
- `rt.subscribe_event`、`rt.unsubscribe_event`、`rt.force_unsubscribe_event` host API
- `rt.update_bid`、`rt.topup_subscription`
- `ActorEventSubscription` 记录 schema
- 快照/回滚的每订阅者失败隔离
- 分层执行模型（top-K 同步 + overflow 至 defer）
- 投标系统 actor
- `get_rank`/`get_topic_orderbook`/`get_min_bid_for_rank` 读方法
- 异步段 defer txs + `triggered_by_emit: EmitOriginRef` receipt 扩展
- 协议常量（`MAX_SUBSCRIBERS_PER_TOPIC=512` 等）
- SDK `@emit` / `@on_event` 装饰器

⚠️ **命名空间冲突**：
- 声明的 `StatePrefix=0x14`/`0x15` **已被 CIP-26**（`Library`/`ActorLibPin`）占用
- 声明的系统 actor `0x0A` **已被 CIP-9**（`STORAGE_MANAGER`）占用
- 实现前 CIP-29 需重新编号

---

## 三、横切发现

### 3.1 系统 Actor 地址空间未及时扩展

`node/runner/src/system_actors.rs:11-71` 仅分配 `0x01..=0x0C`，停在 `SESSION_ACTOR`。**未分配的 CIP 槽位**：

| 地址 | 拟分配 | 来自 | 状态 |
|---|---|---|---|
| `0x0D` | ROUTE_REGISTRY | CIP-14 v2 | 未分配 |
| `0x0D` | BANK_ACTOR | CIP-28 | 未分配 |
| `0x0E` | GATEWAY_REGISTRY | CIP-14 v2 | 未分配 |
| `0x0F` | RECEIPT_REGISTRY | CIP-14 v2 | 未分配 |
| `0x10` | CONTAINER_REGISTRY | CIP-10 v2 | 未分配 |
| `0x11` | PAYMENT_GATE | CIP-18 r2 | 未分配 |
| `0x12` | STREAM_KEY_MANAGER | CIP-7 r2 | 未分配 |

`0x0D` 出现**双重声明**（CIP-14 与 CIP-28），需协调。

### 3.2 操作码空间冲突

| 规范要求 | 实际占用 | 状态 |
|---|---|---|
| CIP-13 v2: 52-56 委托 | 52-57 MPP Session | **冲突**（需调整 CIP-13） |
| CIP-23 v2: 57-60 TEE | 60-63 TEE | **偏移 3** |
| ext_cip-2-9-10: 40 VolumeCreate | 40 `UpdateSettlementConfig` | **文档与代码不一致** |

### 3.3 StatePrefix 命名空间冲突

CIP-29 声明的 `EventSub=0x14`、`EventSubIndex=0x15` 已被 CIP-26 的 `Library`/`ActorLibPin` 占用。`node/storage/src/state_key.rs:85-92` 注释块已记录过类似的历史冲突（`PublishRootDedup` 从 `0x14` → `0x16` → `0x17`）。

### 3.4 Entitlement Registry 漂移

`node/types/src/registry.rs` 测试 `registry_has_exactly_15_entries` 锁定 15 项。**缺失**（且不止于此）：
- `ingress.http`、`ingress.static`、`ingress.mcp`（CIP-14、15、19）
- `dns.attach_external`（CIP-16）
- `payment.gate`（CIP-18）
- `bridge.subscribe_event`（CIP-29）

### 3.5 自身存在的审计文档

代码仓中已有 `node/docs/spikes/cip-code-audit.md`，团队正在做内部交叉审计。本报告与之多处吻合：
- CIP-1 carry-forward bug（line 121）
- CIP-9 PoR 缺口（line 405-406）
- CIP-15b "~10%"（line 52）
- CIP-31 储存费率差 10×（line 1280, 1288）

### 3.6 实现超出规范的部分（也需文档化）

- `JobType::Agent`、`JobType::PublishChainRoot`（CIP-2 v1 未列）
- `Action::UseOwnerBalance`（entitlement.rs:103）
- `Code=0x0F`、`Library=0x14`、`ActorLibPin=0x15` 等生产前缀（CIP-4 未列）
- Treasury `0x08`、Governance `0x09` 等系统 actor 扩展

---

## 四、Node 仓代码资产盘点

### 4.1 工作区主要 crate 成熟度

| Crate | LOC（src） | 测试数 | 成熟度 |
|---|---:|---:|---|
| execution | ~32,000 | **747** | 成熟（最活跃） |
| rpc | ~19,500 | 560 | 成熟 |
| storage | ~17,500 | 370 | 成熟 |
| types | ~14,100 | 355 | 成熟 |
| chain | ~7,800 | 109 | 成熟 |
| client | ~4,300 | 142 | 成熟 |
| cli | 较大 | 183 | 功能性（**8 个 TODO 占位**） |
| proof-verifier | 小 | 110 | 功能性 |
| indexer | 小 | 136 | 功能性 |
| validator | 二进制 | 0 | 成熟（编排） |
| inspector | 495 | **0** | WIP（自标 ALPHA） |
| dev_runner | 小 | 0 | 功能性 |
| runner / ras / token | 类型 crate | 47/27/11 | 功能性 |

**测试总计**：~2,977 个 `#[test]`，118 个 `#[cfg(test)]` 模块。

### 4.2 大文件与单点复杂度

- `execution/src/cbss.rs` — 270 KB, 7,305 LOC（CBSS / DKG）
- `types/src/execution.rs` — 6,445 LOC（操作码表）
- `rpc/handlers/ras.rs` — 6,841 LOC（CIP-9 RAS RPC）
- `execution/src/execution/tests.rs` — 7,503 LOC（测试集）
- `execution/src/pvm_host.rs` — 3,691 LOC（host API）
- `rpc/handlers/runner.rs` — 3,510 LOC（runner RPC）
- `storage/src/speculative.rs` — 2,722 LOC（含 timer 调度 bug）

### 4.3 21 个示例应用

| 类别 | 示例 |
|---|---|
| **成熟**（含 E2E 测试） | `bridge`、`entitlements`、`multi_call`、`multisig-safe`、`token`、`proof`、`timers_demo`、`cip26_account_libraries` |
| **功能性** | `llm_chat`、`llm_session`、`llm_session_web`、`mpp_session`、`session_chain_e2e`、`governance`、`runner_dashboard`、`indexer_test`、`poison_tx_test`、`restart_test`、`ring-demo`、`passkey-wallet` |
| **stub/WIP** | `cip28_agent_banking`（仅 HTML mock） |

### 4.4 显著 TODO 集中点

| 位置 | 数量 | 备注 |
|---|---:|---|
| cli/src/commands.rs | 8 | 余额、nonce、账户信息、提交、状态、区块范围查询——用户可见 CLI 动词的占位实现 |
| examples | 7 | 主要在 Solidity 测试脚本 |
| execution | 3 | 测试相关或小错误类型 |
| chain | 2 | `application.rs:114, 577` 测试用 min block interval |
| pvm-runtime | 1 | 上游 fork |

### 4.5 CIP 在 Rust 代码中出现频次

从 `chain/`、`execution/`、`rpc/`、`runner/`、`ras/`、`token/`、`storage/`、`types/`、`client/`、`cli/`、`validator/`：

CIP-3 (80) · CIP-9 (64) · CIP-25 (64) · CIP-26 (47) · CIP-20 (45) · CIP-2 (36) · CIP-24 (18) · CIP-5 (11) · CIP-12 (4) · CIP-6 (1) · CIP-4 (1)

注：CIP-1/7/8/10/11/13/14/15/16/17/18/19/21/22/23/27/28/29/30/31 等在代码注释中较少出现，与其实现度对应。

---

## 五、风险与优先级建议

### 5.1 最紧迫的代码-规范偏差（应立即处理）

1. **CIP-1 carry-forward bug**（`speculative.rs:751`）——超预算 timer 永久丢失，**正确性问题**
2. **CIP-23 调度器仍用废弃布尔过滤**（`dispatcher.rs:1186`）——规范明确点名的**安全反模式**仍在生产
3. **CIP-9 PoR `shard_inclusion_proof` 硬编码空**（`cbfs/node/src/handler.rs:793`）——**PoR 在密码学层面未生效**
4. **CIP-31 储存费率差 10×**——经济参数应通过治理修正
5. **CIP-29 命名空间冲突**——实现前必须重新编号

### 5.2 大的结构性缺口（按依赖排序）

1. **CIP-4 §12 状态租金**——完全未实现，链上状态膨胀无遏制
2. **系统 Actor 地址空间 `0x0D-0x12`**——阻塞 CIP-10/14/15/18/28
3. **Gateway HTTP edge**——阻塞 CIP-14/15/16/18/19 整个 ingress 栈
4. **CIP-10 容器运行时**——runner 当前为进程内执行，所有沙盒/计费/GPU 工作待启动
5. **CIP-11 QUIC 推送**——仍依赖 5 秒轮询作业
6. **CIP-12 双院治理**——当前 demo 级，所有 Tier 0-4、安全理事会、时间锁待建
7. **CIP-21/22 DeFi 栈**——全空白

### 5.3 接近完工，建议收尾

1. **CIP-8 Slash 处理器**——仅剩 Slash 待补，否则 ~90%
2. **CIP-17 接口对齐**——仅需补 `block_hash`、`absent`、`prove` 字段
3. **CIP-20 事件 + on_transfer + hook cells**——阻塞 indexer 与合规
4. **CIP-26 事件 + per-call 加载 gas**——收尾即 100%

### 5.4 治理建议

1. **建立单一权威的系统 actor / 操作码 / StatePrefix 分配表**——当前 CIP-13、CIP-23、CIP-29 都存在与现行代码或其他 CIP 的冲突
2. **CIP 文档与代码漂移定期同步**——已存在的 `<Warning>` 块（CIP-3、CIP-20）应制度化
3. **将 `node/docs/spikes/cip-code-audit.md` 提升为持续维护文档**
4. **采纳 WP Part II 9 个 Delta**——这些 Delta 已在 CIP-14/15/16 v2 中事实采用，但 WP 本身仍是 v1 + Part II 提案形态

---

## 六、白皮书创世参数 vs 代码逐项核对

WP §13 + §17 锁定的创世参数，逐项与代码对照：

### 6.1 执行（Execution）

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

### 6.2 双计量费率（Dual Basefee）— §4.2 / §17.8

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

### 6.3 共识（Consensus）— §13

| WP 参数 | WP 值 | 代码值 | 状态 |
|---|---|---|---|
| `block_time` | 1 s | 1 s | ✅ |
| `finality` | ~2 s | ~2 s | ✅ |
| `epoch` | 3600 blocks (~1h) | 3600 | ✅ |
| `unbonding_period` | 7 days | 7 days | ✅ |
| `jail_period` | 24 h | 24 h | ✅ |
| `double_sign_slash` | 1% | 1% | ✅ |
| 共识协议 | Simplex BFT | Simplex BFT | ✅ |
| 验证器集 | self-stake only（delegation v2 deferred） | self-stake only | ✅ |

### 6.4 专用 Lane — §6.3 / §17.9

| Lane | WP 预留容量 | WP 周期预算 | 代码值 | 状态 |
|---|---|---|---|---|
| **System** | 5% | 500,000 cycles | 40,000,000 | ⚠️ 80× 偏差 |
| **Timer** | 20% | 2,000,000 | 8,888,890 | ⚠️ 4.4× 偏差 |
| **Runner** | 25% | 2,500,000 | 8,888,888 | ⚠️ 3.6× 偏差 |
| **User** | 50% | 5,000,000 | 22,222,222 | ⚠️ 4.4× 偏差 |
| 各 lane 费率乘数 | 1.0× | **lane_fee_multiplier 缺失** | ❌ | **无 `lane_fee_multiplier` 符号** |

> **解读**：所有 lane 预算 vs WP 偏移 ≥3.6×（System 偏差 80× 最大，但与 WP 一致——WP 的 0.5M 显然过小，代码 40M 接近合理值）。**这是 WP 与代码间的最大数值漂移**。代码本身 `constants.rs:44-45` 已自承 WP §4.3 偏离。

### 6.5 链下计算（Off-chain）— §13

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

### 6.6 状态租金（State Rent）— §13 / §17.5（规范 CIP-4 §12）

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

### 6.7 经济（Economics）— §8 / §13

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

### 6.8 数据可用性 — §7

| WP 参数 | WP 值 | 代码 |
|---|---|---|
| `Inline blob cap` | 64 KiB | ✅ |
| 链上 commitment | multihash | ✅ |

### 6.9 关键 WP 锁定但代码不一致的项目（一句话总结）

- **`T_c` 10M vs 代码 20M**（target）
- **`T_b` 500K vs 代码 4M**（target，8× 偏差）
- **`α=8` vs 代码 96**（12× 偏差）
- **`δ=0.125` vs 代码 1/96**（更平滑）
- **Lane 预算** WP 与代码全线 ≥3.6× 偏差
- **Lane fee multiplier** WP 明确 1.0× 各 lane，代码无该符号
- **State Rent** WP §17.5 全表代码 0% 实现
- **Aggregator bonus 1.5%** WP §13 + §8.4 写死，代码未实现
- **System actor 0x0A** WP §9 v1 错指 Container Image Registry，代码与 Delta 6 修正一致

---

## 七、白皮书 Part II 九个 Delta 实现状态

Part II 是 v2 提案的 9 个 Delta（前瞻性，未采纳进 WP 主体）。每个 Delta 都已在 CIP-14/15/16/18/19/25 等 v2 文档中事实采用，但 WP 自身仍是 v1 + 提案形态。

| Delta | 提议 WP 章节 | 概要 | 依赖 CIP | 代码实现状态 |
|:---:|---|---|---|---|
| **1** | §17.x | Stake vs 操作余额分离 | CIP-14 v2 §6.3 | 🟡 — Runner Registry 已隐式分离；Gateway/Relay 未实现（依赖 CIP-14） |
| **2** | §6.x | Read-only handler 作为协议原语（含完整 trap 列表）| CIP-14 v2 §5 | 🟡 — `POST /actor/read` 实现读模式与 trap 表，但端点路径不对齐 CIP-14 |
| **3** | §9.x | 延迟结果存储模式（`RECEIPT_REGISTRY` 共享 pruning loop）| CIP-14 v2 §8 | ❌ — `0x0F` 未分配 |
| **4** | §6.y | 系统保留选择器（`http.request`、`_dns.callback`）| CIP-14 v2 §6.2 + CIP-16 v2 §5.6 | ❌ — 无 selector reservation 机制 |
| **5** | §9.y | `STORAGE_MANAGER` 持有 actor 配置（route_manifest / cors_config）| CIP-15 v2 §4.1 / §7.1 | ❌ — 仅 `update_route_manifest` 概念，无实现 |
| **6** | §9 修订 | 系统 actor 分配表修正（0x0A = STORAGE_MANAGER，不是 Container Image Registry）| CIP-9 / CIP-10 v2 | 🟡 — 代码已经是 STORAGE_MANAGER；WP §9 v1 文本仍错，需采纳 Delta 6 修正 |
| **7** | §17.y | 支付层（PaymentGate `0x11`、4 种模式、MPP+x402）| CIP-18 r2 | ❌ — 0% 实现 |
| **8** | §6.z | MCP Ingress（actor 即 MCP server）| CIP-19 + CIP-15 v2.r2 + CIP-18 | ❌ — 0% 实现 |
| **9** | §16.z | 跨链架构（L1/L2/L3 三层 + 4 种 L1 backends）| CIP-25 | ✅ ~60% — Cowboy↔ETH 桥已可工作，runner-committee backend 已部署 |

### 7.1 Delta 实施进度分组

- **已落地（部分）**：Delta 1（runner 侧）、Delta 2（PVM read-only）、Delta 6（代码 0x0A 早已 STORAGE_MANAGER）、Delta 9（CIP-25 runner-committee 桥可工作）
- **完全未实施**：Delta 3、4、5、7、8

### 7.2 Delta 6 — 紧迫的文档级修正

**WP §9 v1 文本仍声称 0x0A = Container Image Registry**，但代码、CIP-9、CIP-10 v2 均已迁移：

- 代码：`0x0A = STORAGE_MANAGER`（CIP-9）
- CIP-10 v2.r2：Container Registry 改至 `0x10`
- CIP-14 v2.r2：Route/Gateway/Receipt = `0x0D/0x0E/0x0F`
- CIP-18 r2：PaymentGate = `0x11`

WP 应在下一版本采纳 Delta 6 修订表。

### 7.3 Delta 7-8（支付 + MCP）— 平台货币化基础

Delta 7（PaymentGate）和 Delta 8（MCP Ingress）共同构成"actor 货币化"的核心架构层。WP v1 完全没有这两层；Delta 7-8 是为了让 Cowboy 平台对接 AI agent 经济而新增的方向。

**当前阻塞**：Delta 7 依赖 `0x11`、Delta 8 依赖 Gateway（CIP-14/15）+ Delta 7。整条链路代码 0%。

### 7.4 Delta 9 — 跨链架构与 §16 的张力

WP §16.2 明确："Cowboy 依赖第三方桥基础设施 ... 协议不实现自身的桥验证器集"。但 CIP-25（+ Delta 9）提出 **runner-attested committee** 作为 L1 后端，事实上**就是一个协议级的桥验证器集**（虽然复用 CIP-2 的 Runner Registry）。

Delta 9 的修订方案：**WP §16.2 的"无协议验证器集"应窄读为"无单一强制桥验证器集"**；CIP-25 的 `IChainAnchor` 允许第三方与 Cowboy-runner backend 共存。

代码已经实施 runner-committee 路径（`examples/bridge/` 完整 Cowboy↔Ethereum，已含 `JobType::PublishChainRoot`、Anchor_C、`CowboyLightClient.sol`、L2 Mailbox、L3 资产桥），事实优先于文档；WP 需采纳 Delta 9 来消除自相矛盾。

---

## 八、结语

代码库整体处于**主干能力完整、外围生态待铺开**的阶段。白皮书层面亦呈"v1 已定型、v2 提案仍在 Part II 阶段"的状态。

### 8.1 已成熟

CIP-2（链下计算）、CIP-5（定时器）、CIP-6（SDK）、CIP-8（MPP Session）、CIP-20（代币）、CIP-25（跨链桥 demo）、CIP-26（账户库）。

这些 CIP 均有完整实现 + 测试覆盖 + 端到端示例，且与 WP Part I 描述吻合。

### 8.2 核心架构齐全但有明显短板

CIP-3（费模型——lane multiplier 缺；α/δ 与 WP 偏离）、CIP-4（状态租金 WP §17.5 完整规范但代码 0%）、CIP-9（PoR 经济缺）、CIP-17（接口名差异）。

### 8.3 完全空白或仅 demo

CIP-1 v3、CIP-7、CIP-10、CIP-11、CIP-13、CIP-14、CIP-15、CIP-16、CIP-18、CIP-19、CIP-21、CIP-22、CIP-28、CIP-29、CIP-31，以及 CIP-12 的双院/理事会层、WP Part II Delta 3/4/5/7/8。

### 8.4 三层（WP / CIP / 代码）漂移

本审计揭示三个层次的同步问题：

1. **WP ↔ 代码漂移**：α=8/96、Lane 预算 ≥3.6×、`T_b` 8× 偏差、State Rent 100% 未实现、Lane fee multiplier 符号缺失
2. **WP ↔ CIP 漂移**：WP §9 v1 错指 0x0A = Container Image Registry（Delta 6 已识别）；WP §16.2 无桥验证器集与 CIP-25 runner-committee 张力（Delta 9 已修订）；WP §10 SDK 版本 vs CIP-6
3. **CIP ↔ 代码漂移**：CIP-13 v2 操作码 52-56 与 MPP Session 冲突；CIP-23 v2 操作码 57-60 与代码 60-63 错位；CIP-29 StatePrefix 0x14/0x15 + 系统 actor 0x0A 与 CIP-26/CIP-9 冲突

### 8.5 最高优先级跨域风险

**系统 actor 地址空间和操作码空间未集中规划**，已出现多处冲突：
- CIP-13 委托操作码 vs MPP Session
- CIP-23 TEE 操作码偏移
- CIP-29 命名空间被 CIP-26/CIP-9 占用

WP Delta 6 已修订系统 actor 表至 `0x12`，应作为单一权威分配表落地。

### 8.6 平台演进路径建议

按依赖与优先级，下一阶段重点：

**P0（正确性与安全）**：修复 CIP-1 carry-forward bug、补 CIP-9 PoR 密码学绑定、移除 CIP-23 废弃布尔过滤。

**P1（基础设施收尾）**：CIP-8 Slash、CIP-17 接口对齐、CIP-20 事件与 on_transfer、CIP-26 事件与加载 gas、CIP-3 lane multiplier。

**P2（系统 actor 与 ingress 栈）**：扩展地址空间到 `0x12`，实现 CIP-14 Route Registry + CIP-15 Gateway HTTP edge + CIP-18 PaymentGate（解锁 CIP-16、19）。

**P3（运行时改造）**：CIP-10 容器（OCI + cgroups + GPU + 网络策略）+ CIP-11 QUIC 推送+ CIP-13 委托（连同操作码协调）。

**P4（高级功能）**：CIP-23 复合证明 + CIP-29 事件订阅子系统 + CIP-31 经济参数 + CIP-12 双院治理。

**P5（DeFi / 生态）**：CIP-21 AMM + CIP-22 拍卖 + CIP-28 Agent Banking + CIP-7 付费流。

---

**报告完**

> 本报告基于 2026-05-15 时点的代码状态与白皮书 v2.r2（2026-05-11 更新）。引用的 `file:line` 在该时点准确，后续重构可能改变。
> 白皮书引用：`refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md`（Part I v1 / Part II 9 个 Delta / Part III 对齐审计简报）。
> 完整证据链与 8 个并行代理的原始输出可向审计人索取。
