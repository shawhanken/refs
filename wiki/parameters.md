---
type: parameter
tags: [constants, authoritative, cip-3, cip-5, cip-12, cip-13, cip-14, cip-15, cip-16, cip-18, cip-19, cip-23, cip-25]
sources:
  - node/types/src/constants.rs
  - node/types/src/execution.rs
  - node/execution/src/basefee.rs
  - node/execution/src/gas.rs
  - refs/analysis/2026-04-15_documentation_amendments.md
  - refs/cips/cip-3-fee-model.mdx
  - refs/cips/cip-2-offchain-compute.md
  - refs/cips/cip-5-timers.md
  - refs/cips/cip-7-simple-stream-protocol.md
  - refs/cips/cip-8-mpp-session.md
  - refs/cips/cip-9-runner-storage.md
  - refs/cips/cip-10-runner-containers.md
  - refs/cips/cip-11-runner-connectivity.md
  - refs/cips/cip-12-governance.md
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-15-public-asset-hosting.md
  - refs/cips/cip-16-custom-domains.md
  - refs/cips/cip-18-payments.md
  - refs/cips/cip-19-gateway-mcp-ingress.md
  - refs/cips/cip-23-tee-execution.md
  - refs/cips/cip-24-secrets-manager.md
  - refs/cips/cip-25-cross-chain-architecture.md
  - refs/cips/cip-28-cowboy-agent-banking.md
  - refs/cips/cip-29-on-chain-event-hooks-en.md
last_updated: 2026-05-26
status: authoritative
---

# 参数与常量权威表

**代码为准**。文档（CIP / 白皮书）与下表不一致时，以本表为准并同步 `drift.md` 记录。

---

## 块参数（Block Targets）

| 常量 | 值 | 源 |
|---|---|---|
| `BLOCK_CYCLES_TARGET` | `20,000,000` cycles | `node/types/src/constants.rs:46` |
| `BLOCK_CELLS_TARGET` | `4,000,000` cells | `node/types/src/constants.rs:50` |

> CIP-3 / 白皮书仍写 10M / 500K，已通过修正案 A-1、A-2 标注。

---

## Basefee（几何更新模型）

| 常量 | 值 | 源 |
|---|---|---|
| `ALPHA` | `96` | `node/execution/src/basefee.rs:99-119` |
| `DENOM` (clamp 分母) | `96` | 同上 |
| `MIN_BASEFEE` | `10,000` | 同上 |
| `MAX_BASEFEE` | `10²⁴` | 同上 |

**公式**: `Δ = basefee × |used − target| / target / ALPHA`，最终变化 clamp 到 `basefee / DENOM`。

> 白皮书 §4.2 用 `alpha=8, δ=12.5%`、§17.8 用简化线性，两版均过时。

---

## Gas 成本（选关键项）

| 操作 | Cycles | Cells | 源 |
|---|---|---|---|
| Transfer | `5,000` | `500` | `node/execution/src/gas.rs:163-164` |
| Storage Read | `STORAGE_READ_CYCLES`（per read，PVM 后扣）| — | `node/execution/src/pvm_host.rs`（`ActorStorageCache`）|
| Calldata（intrinsic）| — | `1 cell/byte` | CIP-3 对齐 |
| Return data | — | `1 cell/byte` | 同上 |
| Token hook 上限 | `50,000`（**阶段 1 声明，阶段 2 才扣费**）| — | CIP-20；见修正案 G-1 |

> 白皮书 §17.2 写 Transfer=21,000 cycles / 0 cells，两项皆错。

---

## Runner 经济参数

| 参数 | 值 | 含义 | 源 |
|---|---|---|---|
| 注册 floor | `10,000 CBY` | 链上 Registry 接受注册的硬性最低 | `node/execution/src/runner/registry.rs:65-80` |
| 工作经济门槛 | `50,000 CBY` | Runner 承接工作的保证（应用层）| `runner/2026-03-03_Entitlement.md:18` |
| `STAKE_JOB_MULTIPLIER_NUM/DENOM` | `3/2`（1.5×）| `stake >= max_job_value × 1.5` | `node/types/src/constants.rs` |
| `DISPUTE_WINDOW_BLOCKS` | `75` | 结果可被质疑的窗口 | `node/types/src/constants.rs` |
| Slashing 分配 | `50% treasury / 50% burn` | 被 slash 的 stake 分配 | `node/execution/src/runner/verifier.rs` |

> 白皮书 §5.2 (`1.5×max_job`) 与 §17.7 (`10×avg`) 冲突，代码采用前者。修正案 C。

---

## Actor 模型约束

| 参数 | 值 | 源 |
|---|---|---|
| `MAX_PENDING_DEFERRED_PER_ACTOR` | `64` | `node/types/src/constants.rs` |
| `DEFERRED_TX_MAX_AGE_BLOCKS` | `1,000` | 同上 |
| Max synchronous call depth | `32` | 执行引擎 |

---

## Timer（CIP-5 revised 2026-04-20，CIP-1 v2 alignment）

| 参数 | 值 / 默认 | 源 |
|---|---|---|
| `LANE_TIMER_CYCLES`（执行预算）| `8,888,890` | `node/execution/src/pvm_host.rs:1051-1097` / CIP-5 §6.5（旧名 `TIMER_PROCESSING_BUDGET_CYCLES` 已废）|
| `TIMER_GC_CYCLES`（GC lane 预算）| `5,000,000`（`TimerConfig.gc_cycles_per_block`）| CIP-5 §6.5 |
| 单 timer cycles 上限 | `550,000`（`TimerConfig.max_cycles_per_fire`）| CIP-5 §6.4 |
| 单 timer cells 上限 | `550,000`（`TimerConfig.max_cells_per_fire`）| CIP-5 §6.4 |
| `max_ttl_blocks` | 2,592,000（≈30d @ 1s）| CIP-5 §6.4 |
| `MAX_TIMERS_PER_ACTOR` | `1,024`（`TimerConfig.max_timers_per_actor`）| CIP-5 §6.4 |
| 块内顺序 | **Tx-then-Timer**（CIP-5 §5.1 native，已 codified）| `node/storage/src/speculative.rs:152-475` |
| Per-fire fee 模型 | `max_cost = gas_limit × cycle_basefee + max_cells × cell_basefee` 预扣 + 退还 | CIP-5 §6.3 |

**三路退出生命周期**（CIP-5 §5.4）: natural fire / TTL expiry / insufficient-funds self-destruct（emit `TimerCancelledInsufficientFunds`）。

**跨 CIP 持有者**: CIP-9 v2 §12 PoR (`fee_payer = STORAGE_MANAGER`)；CIP-16 v2 §5.10 reverify (`fee_payer = binding.owner` + 二线 `INSUFFICIENT_TIMER_FUEL`)；CIP-14 v2 §8 receipt prune（系统循环，不依赖单 timer per receipt）。

> CIP-5 v1 描述 timer "system-triggered, no fee" 已被 revised 2026-04-20 native 改为 fee_payer 模型。CIP-1 v1 描述"Timer 先于 Tx"已被 CIP-5 §5.1 改正。

---

## Address / 签名

| 维度 | 值 | 源 |
|---|---|---|
| Address 长度 | `20 bytes`（Ethereum-style）| `node/types/src/address.rs:8-12` |
| 签名算法 | `secp256k1 ECDSA`，65 bytes `r‖s‖v` | `node/types/src/signature.rs:9-18` |
| 派生 | `keccak256(secp256k1_pubkey_uncompressed[1..])[12..]` | 同上 |

> `node/2026-02-24_ADDRESS_MIGRATION_ETH_STYLE.md` 提案已采纳实施。

---

## 序列化

| 用途 | 格式 |
|---|---|
| 跨 Actor 消息、Continuation 状态 | **CBOR**（Canonical） |
| 历史：曾提及 MessagePack → 已统一为 CBOR |

---

## PVM 确定性约束

| 约束 | 值 |
|---|---|
| `INT_GUARD_PREAMBLE` 整数上限 | 4,096 bits（替换 `builtins.int` 为 `_GuardedInt`）|
| 静态整数字面量上限 | 1234 digits |
| 禁用模块 | `ctypes`, `_ctypes`, `cffi`, `_cffi_backend`, `asyncio.gather` |
| 源文件格式 | UTF-8 |

> 见 `node/execution/src/pvm_executor.rs::validate_actor_code()`。

---

## 治理（CIP-12 Draft，尚未实装）

均为初始默认值，全部可由 Tier 4 调整。

| 参数 | 默认 |
|---|---|
| Tier 0 押金 / Temp / Voting / Quorum / Approval / Val / Timelock | 1K CBY / 3d / 5d / 5% / >50% / >50% / 3d |
| Tier 1 | 5K / 3d / 5d / 10% / >50% / >50% / 5d |
| Tier 2 | 5K / 5d / 7d / 15% / >55% / >50% / 7d |
| Tier 3（系统 Actor 升级）| 25K / 7d / 7d / 15% / >60% / >50% / 7d + Fast-track |
| Tier 4（宪法）| 100K / 14d / 14d / 20% / >66% / >66% / 14d |
| Temp check 最小参与 / 通过率 | 1% of active stake / 33% |
| Voting 最小参与（extend 触发）| Validator 60% / Stake 为 quorum × 60% |
| `voting_extension_blocks` / `max_voting_extensions` | 1 天 / 3 |
| `max_system_actor_bytecode_size` | 512 KiB |
| Rollback window 下限 | 7 天 |
| Circuit-Break 初始期限 / Tier 3 续期 | 7 天 / 30 天 × cap 3 次（≈90d）→ 后续须 Tier 4 |
| Cancellation 审查窗口 / 阈值 | 90 天 / 3 次 |
| `execution_retry_blocks` | 1 天 |

**源**: `refs/cips/cip-12-governance.md` §5.2 / §6.5 / §7。

---

## Runner Stake 委托（CIP-13 v2 Draft，尚未实装）

均为 CIP-12 Tier 0 可调。

| 参数 | 默认 | 说明 |
|---|---|---|
| `UNBONDING_BLOCKS` | 7,200（≈24h）| 解绑冷却 |
| `DELEGATION_COOLDOWN_BLOCKS` | 600（≈2h）| `RunnerUpdateDelegationConfig` 节流 |
| `MIN_SELF_BOND_BPS` | 1,000（10%）| Runner 自质押占 effective_stake 下限 |
| `MAX_DELEGATORS_PER_RUNNER` | 200 | Runner 扇入上限 |
| `MAX_ACTIVE_TRANCHES_PER_DELEGATOR` | 8 | 单 delegator 对单 runner 的 Active Tranche 上限 |
| `MIN_DELEGATION_AMOUNT` | 1,000 CBY | 协议 floor |
| `CLAIM_MAX_TRANCHES` | 32 | 单次 claim Tranche 数上限 |
| `MAX_DELEGATION_SLASH_PER_EPOCH_BPS` | 500（5%）| Delegator 侧 slash 封顶 |
| `MIN_COMMISSION_BPS` / `MAX_COMMISSION_BPS` | 500 / 10000 | Commission 上下限 |
| `DELEGATION_EVENT_BATCH_THRESHOLD` | 20 | `DelegatorPayout` 批发阈值 |
| Opcodes | **52–56** | CIP-13 v2 §1 主分配表；v1 40-44 与 v1 草稿 44-48 均与代码冲突，已修正 |

**源**: `refs/cips/cip-13-runner-delegation.md` §1（opcode 主表）+ §4（参数）。

---

## DNS-Addressable Actors（CIP-14 v2.r2 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `ROUTE_REGISTRY_ADDRESS` | `0x0D` | v2.r2 后移；v1 草案 `0x0011` / v2.r1 草案 `0x0C` 均已废（`0x0C = SESSION_ACTOR` 已 commit）|
| `GATEWAY_REGISTRY_ADDRESS` | `0x0E` | v2.r2 后移；v1 草案 `0x0012` 已废 |
| `RECEIPT_REGISTRY_ADDRESS` | `0x0F` | v2.r2 后移（v2.r1 为 `0x0E`，因前两位后移 +1）|
| `MIN_NAME_LENGTH` / `MAX_NAME_LENGTH` | 3 / 64 | 名称长度约束 |
| `NAME_GRACE_PERIOD` | 2,592,000 blocks（≈30d @ 1 block/sec）| 过期后宽限期 |
| `NAME_AUCTION_DURATION` | 604,800 blocks（≈7d）| Dutch 拍卖释放窗口 |
| `BLOCKS_PER_YEAR` | 31,536,000 | 1 block/sec（WP-v2 §6.1 canonical；2026-05-26 起 CIP-11 / CIP-23 也对齐到 1s）|
| `MIN_GATEWAY_STAKE` | governance-set | Gateway 注册最低 stake |
| `MAX_GATEWAY_HEALTH` | 3,600 blocks（≈1h）| Heartbeat 重置值；每块 -1 |
| `GATEWAY_UNSTAKE_DELAY` | 604,800 blocks（≈7d）| 解绑延迟 |
| `MAX_REQUESTS_PER_SECOND` | 100 | Per actor per gateway |
| `MAX_CONCURRENT_CONNECTIONS` | 1,000 | Per actor per gateway |
| `RECEIPT_TTL_BLOCKS` / `RECEIPT_TTL_MAX` | 3,600 / 86,400 | 单一 receipt 默认 / 最大 TTL（actor 可在 `ingress.http` `receipt_ttl_blocks` 调）|
| `PROTOCOL_MAX_REQUEST_BYTES` | 10,485,760（10 MiB）| 协议 ceiling；Actor 可在 `ingress.http` params 中降低 |
| `PROTOCOL_MAX_RESPONSE_BYTES` | 10,485,760 | 同上 |
| `PROTOCOL_MAX_QUERY_CYCLES` | 100,000,000 | Read-path PVM cycles ceiling |
| Opcodes 65 / 66 | `IngressDispatch` / `CompleteReceipt` | CIP-13 v2 §1 主表 |

**费分配**：注册 / 续费费走 `system:registry_settlement_config`（target_pool: REGISTRY），Gateway pool 走 `system:gateway_pool_config`（target_pool: GATEWAY_POOL），均通过 `UpdateSettlementConfig` (opcode 40) 治理可调。CIP-14 v1 的 `REGISTRY_PROTOCOL_FEE_BPS=1000` / `GATEWAY_POOL_BPS=2000` 折算为 v2 默认 `burn 70 / treasury 15 / gateway_pool 15`。

**`ingress.http` 默认 params**: `allowlist_methods=["GET","HEAD","POST"]`, `max_request_bytes=1 MiB`, `max_response_bytes=1 MiB`, `max_query_cycles=10_000_000`, `receipt_ttl_blocks=3600`。

**Subdomain policy 默认**: `OWNER_ONLY`（v1 默认 `ACTOR_MANAGED` 已修正，避免 DoS）。

**源**: `refs/cips/cip-14-dns-addressable-actors.md` Part II §10（v2 常量），Part II §3 / §4 / §6 / §7 / §8（其他细节）。

---

## Public Asset Hosting（CIP-15 v2 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `MAX_STATIC_ROUTES` / `MAX_DYNAMIC_ROUTES` | 100 / 100 | route_manifest 条目上限 |
| `MAX_ROUTE_MANIFEST_SIZE` | 65,536 B | 路由清单 size cap |
| `MANIFEST_POLL_INTERVAL` | 6 blocks（≈6s）| 失效轮询周期 floor（与 `ManifestCommitted` 事件订阅互补）|
| `MAX_GATEWAY_CACHE_BYTES` | 10 GiB | 单 Gateway 对象 cache 总上限 |
| `DEFAULT_MAX_STATIC_RESPONSE_BYTES` | 10 MiB | 单资产响应默认上限 |
| `PROTOCOL_MAX_STATIC_RESPONSE_BYTES` | 100 MiB | Hard ceiling |
| `HEDGE_THRESHOLD_MS` | 100 ms | 投机并发 shard 请求阈值 |
| `MAX_CONCURRENT_SHARD_FETCHES` | 8 | 单对象重建最大并发 |
| `DEFAULT_CORS_MAX_AGE` | 86,400 s（24h）| `Access-Control-Max-Age` |
| `MAX_CORS_RULES` | 50 | cors_config 条目上限 |
| `ROUTE_PRIORITY_GAP` | 1 | `min(dynamic.priority) > max(static.priority)` 强制约束 |

**`ingress.static` 独立 entitlement params**（v2 §3，**不再嵌套在 ingress.http**）: `static_volume_names: StrArray (required, ≤ 8)`, `max_static_response_bytes: Uint (default 10 MiB)`, `max_cache_bytes_total: Uint (default 100 MiB advisory)`。

**Storage 状态 → HTTP 行为**（CIP-9 v2 §5；不引入 `DELINQUENT`）: ACTIVE = serve normal | GRACE_PERIOD = serve + advisory header | DELETED = 503 | GARBAGE_COLLECTING = 410。

**route_manifest / cors_config 存储**: 在 `STORAGE_MANAGER (0x0A)` 下按 `actor_address` 索引；通过普通 ActorMessage `update_route_manifest` / `update_cors_config` 更新（**不**消耗 SystemInstruction opcode）。

**源**: `refs/cips/cip-15-public-asset-hosting.md` Part II §3-§8 + `refs/cips/cip-9-runner-storage.md` §2-§5（GET_MANIFEST RPC、ManifestCommitted 事件、CBFS Merkle、status 映射）。

---

## Custom Domains & First-Party TLDs（CIP-16 v2 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `NAMESPACE_COWBOY_NETWORK / FIRST_PARTY_TLD / EXTERNAL` | 0 / 1 / 2 | namespace_kind 枚举 |
| `TLD_COW / TLD_COWBOY` | 1 / 2 | tld_kind 枚举 |
| `CHALLENGE_EXPIRY_BLOCKS` | 43,200（≈12h @ 1s）| TXT 挑战有效窗口 |
| `EXTERNAL_REVERIFY_INTERVAL` | 2,592,000（≈30d）| 周期重验证间隔 |
| `EXTERNAL_REVERIFY_GRACE_BLOCKS` | 86,400（≈1d）| Gateway overdue 二线兜底窗口 |
| `EXTERNAL_REVERIFY_FEE` | governance-set | v2 §5.8 新增；每次 reverify 从 binding owner 扣 |
| `EXPIRED_RETENTION_BLOCKS` | 7,776,000（≈90d）| EXPIRED binding auto-prune |
| `CANONICAL_EDGE_HOSTNAME` | `edge.cowboy.network` | anycast 默认；可选 SRV 模式（v2 §5.4）|
| `ACME_DELEGATION_ZONE` | `acme.cowboy.network` | DNS-01 委派 zone |
| `DNS_VERIFY_RUNNERS` | 3 | MajorityVote 共识 N |
| `DNS_VERIFY_THRESHOLD` | 2 | MajorityVote 通过阈值 |
| `DNS_VERIFY_MIN_RESOLVERS` | 3 | 每 runner 查的独立 resolver 数 |
| `DNS_VERIFIER_EXECUTOR_HASH` | governance-pinned | DNS verifier 二进制 hash |
| Opcode 67 | `ExternalDomainCallback` | CIP-13 v2 §1 主表；sender = RESULT_VERIFIER (0x03) |

**SUSPENDED 原因码**: `TXT_MISMATCH` / `CNAME_DRIFT` / `ACME_DELEGATION_MISSING` / `INSUFFICIENT_REVERIFY_FEE` / `INSUFFICIENT_TIMER_FUEL`（最后一项 v2 §5.10 新增，对应 CIP-5 timer self-destruct 兜底）。

**HTTP 状态映射**（v2 §7.2 修正 v1 错用 421）: PENDING/SUSPENDED → 503；EXPIRED/DETACHED → 404。

**源**: `refs/cips/cip-16-custom-domains.md` Part II §3-§10。

---

## TEE Execution（CIP-23 v2 Draft，尚未实装）

| 参数 | 默认 | 说明 |
|---|---|---|
| `MAX_QUOTE_AGE` | 75 blocks（≈75s @ 1s）| Quote 新鲜度窗口（CIP-23 r1 2026-05-26 从 150 blocks @ 500ms 重算到 75 @ 1s） |
| `BINDING_RENEWAL_PERIOD` | 604,800 blocks（≈7d @ 1s）| Measurement binding 续约（CIP-23 r1 2026-05-26 修正原 12,096 算术错误 / 500ms 假设） |
| `ROOT_UPDATE_DELAY` | 1 week | `UpdateCpuRoot` / `UpdateNrasRoot` 延迟生效 |
| `SEEN_NONCE_GC_WINDOW` | = `DISPUTE_WINDOW_BLOCKS` (75) | Nonce 回收与争议窗口对齐 |
| `MAX_CAE_ON_CHAIN_BYTES` | 64（仅 digest）| 完整 CAE 走 CIP-9 存 CID |
| Opcodes | **57–60** | `VerifyCae` / `UpdateCpuRoot` / `UpdateNrasRoot` / `GcNonces`（v2 §4，从 v1 §3.6.2 的 50-53 修正；v1 50-53 与代码 `SYS_EXTEND_TIMER=50` / `SYS_DEPLOY_CODE=51` 冲突）|
| `CANONICAL_TEE_TYPES` | `["sgx", "sev", "tdx"]` | ⚠️ v2 §2 要求追加 `"nitro"` (precondition)；详见 [[concepts/tee-attestation]] |

**`tee_type` → `VerificationMode` 资格映射**（v2 §2）: `tdx` / `sev` / `nitro` 全 mode 含 `Deterministic`；`sgx` 排除 `Deterministic`（legacy tier）。

**BillingAttestation 数据源**（v2 §5.1）: `tee_signature: Option<CompositeAttestation>` 是**每次 billing event 临时生成**，不缓存 measurement_binding 时的 quote。`freshness.nonce = keccak(billing_fields ‖ submission_block_hash)`。

**Gas 预算**: `VerifyCae` (TDX + NCC) ≈ 200k cycles + 64 cells，每块 `BLOCK_CYCLES_TARGET = 20M` 下可验 ~100 个 CAE。

**源**: `refs/cips/cip-23-tee-execution.md` Part II §1-§5。

---

## SystemInstruction Opcode 主分配表（2026-05-26 代码权威视角）

> **2026-05-26 重写**：原 wiki 表本节复用了 CIP-13 v2 §1 早期 "canonical master allocation"，但实际 `node/types/src/execution.rs` 与该表全面 drift。本节按 `node/types/src/execution.rs:591-699` 的 `SYS_*` 常量 + Decode dispatch 重写。CIP-13 §1 主表已同步重写。

**Live opcodes（在代码）：**

| Opcode | Name | Owning CIP | Status |
|---:|---|---|---|
| 0 | `CreateAccount` | core | ✅ in code |
| 1 | `Transfer` | core | ✅ in code |
| 2–5 | `RunnerRegister` / `UpdateRateCard` / `Heartbeat` / `Deregister` | CIP-2 | ✅ in code |
| 6–9 | `JobSubmit` / `JobResultSubmit` / `JobCancel` / `JobResultCommit` | CIP-2 | ✅ in code |
| 10–20 | Token ops (`TokenCreate`…`TokenTransferBatch`) | CIP-20 | ✅ in code |
| 21–29 | — | — | (free) |
| 30–35 | Entitlement ops (`Grant`/`Revoke`/`Delegate`/`CreateRole`/`AssignRole`/`RevokeRole`) | CIP-2 §7 | ✅ in code |
| 36–39 | — | — | (free) |
| 40 | `UpdateSettlementConfig` | CIP-2 / CIP-3 | ✅ in code |
| 41 | `FundActor` | core | ✅ in code |
| 42 | `KeyDelivery` | core | ✅ in code |
| 43 | `UpgradeActor` | CIP-12 §7 | ✅ in code |
| 44 | `UpdateBasefeeConfig` | CIP-3 | ✅ in code |
| 45–47 | `SubmitProposal` / `CastVote` / `ExecuteProposal` | CIP-12 | ✅ in code |
| 48–50 | `CancelTimer` / `UpdateTimerConfig` / `ExtendTimer` | CIP-5 | ✅ in code |
| 51 | `DeployCode` | core | ✅ in code |
| **52–57** | **`SessionOpen` / `SessionDeposit` / `SessionSettle` / `SessionClose` / `SessionFinalize` / `SessionSlash`** | **CIP-8 (MPP Session)** | **✅ in code** |
| 58–59 | — | — | (free) |
| **60–63** | **`RegisterTeeTrustedKey` / `RevokeTeeTrustedKey` / `SubmitTeeAttestation` / `RevokeTeeAttestation`** | **CIP-24 §3.3 (TEE Verifier support)** | **✅ in code** |
| 64–67 | — | — | (free) |
| **68–84** | **`SetSecret` … `ForcedDeregisterCbssProxy`** (17 slots) | **CIP-24 §3.3 (CBSS main)** | **✅ in code** |
| **85** | **`SubmitDrainRelayProposal`** | **CIP-9 §13.3** | **✅ in code** |
| **86** | **`SubmitAutoDrainPolicyProposal`** | **CIP-9 §13.4** | **✅ in code** |
| 87+ | — | — | (free; 给以下 spec-only 提案预留) |

**Aspirational allocations（spec-only，尚未实装；激活时必须重号到 ≥87）：**

| 原 claim | CIP | 现状 |
|---|---|---|
| 52–56 → CIP-13 delegation handlers | CIP-13 v2 §1 | 与 CIP-8 Session 撞号；必须重号 |
| 57–60 → CIP-23 v2 `VerifyCae` / `UpdateCpuRoot` / `UpdateNrasRoot` / `GcNonces` | CIP-23 v2 §4 | 与 CIP-8 SessionSlash (57) + CIP-24 TEE keys (60) 撞号 |
| 61–64 → CIP-10 v2 容器 ops | CIP-10 v2 §5 | 与 CIP-24 TEE keys (61-63) 撞号 |
| 65–67 → `IngressDispatch` / `CompleteReceipt` / `ExternalDomainCallback` | CIP-14 v2 §6.1 / §8 / CIP-16 v2 §5.6 | 64-67 当前 free；这一组可如期落地 |
| (TBD) → CIP-28 BankActor handlers | CIP-28 r1.1 | 未在 CIP-28 列出；预留 ≥87 |

**CIP-29（事件订阅）** 不消耗 SystemInstruction opcode：`pvm_host::call_actor` 拦截 `0x1D` 路由到 `event_sub_system_actor::dispatch_rpc`，所有 RPC 走 host-side 函数。

详见 [`refs/cips/cip-13-runner-delegation.md` §1](../cips/cip-13-runner-delegation.md) 主表与 [[entities/system-actors]]。

---

## SettlementConfig `target_pool` 枚举（CIP-14 v2 Part III §6 canonical）

`UpdateSettlementConfig` (opcode 40) 携带，sender 必须 `0x09`：

| Value | Pool | 来源 CIP | 存储 key |
|---:|---|---|---|
| 0 | `MAIN` | CIP-3（既有）| `system:settlement_config` |
| 1 | `REGISTRY` | CIP-14 v2 §4.5 | `system:registry_settlement_config` |
| 2 | `GATEWAY_POOL` | CIP-14 v2 §7.4 | `system:gateway_pool_config` |
| 3 | `CONTAINER` | CIP-10 v2 §2 | `system:container_settlement_config` |
| 4 | `REGISTRY_TLD_COW` | CIP-16 v2 §4 | `system:registry_tld_cow_config` |
| 5 | `REGISTRY_TLD_COWBOY` | CIP-16 v2 §4 | `system:registry_tld_cowboy_config` |
| 6+ | (reserved) | — | — |

handler MUST exhaustive switch；未知 → `ERR_UNKNOWN_POOL`。

---

## Payments（CIP-18 r2 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `PAYMENT_GATE_ADDRESS` | `0x11` | CIP-18 r2 (2026-05-11) 对齐 v2 主表（从 `0x0013` 后移）|
| `PROTOCOL_PAYMENT_FEE_BPS` | 500（5%）| `actor_fee / pass / subscription` 全部抽 |
| `MAX_PRICE_TABLE_ENTRIES` | 100 | 单 PaymentPolicy 价格规则上限 |
| `MAX_ACCEPTED_ASSETS` | 10 | 单 PaymentPolicy 支持 asset 上限 |
| `MIN_BUDGET_DEPOSIT` | governance-set | actor-funded 起跑线 |
| `DEFAULT_EPOCH_BLOCKS` | 86,400（≈1d @ 1s）| 默认 epoch 长度 |
| `MAX_EPOCH_BLOCKS` | 2,592,000（≈30d）| 单 epoch 上限 |
| `PASS_EXPIRY_BLOCKS` | 31,536,000（≈1y）| Prepaid pass 默认过期 |
| `MAX_PREPAID_CREDITS` | 1,000,000 | 单 pass 上限 credits |
| `CBY_ASSET_ADDRESS` | `0x0000...0000` | native CBY 标识 |
| `PAYMENT_POLICY_CACHE_TTL_BLOCKS` | 1 | Gateway 本地 policy 缓存 TTL（下一块生效）|
| `MIN_BRIDGE_CONFIRMATIONS_EVM` | 32 | governance-set per-chain；高 TVL 推 64 |
| `EVM_FINALITY_HEADROOM_BLOCKS` | 64 | challenge `valid_before` 须保留的 finality 余量 |
| `JSONRPC_PAYMENT_REQUIRED_CODE` | -32402 | MCP 路径下 402 等价错误码（见 CIP-19）|

**新 Entitlements**（[[drift]] V-15）：
- `payment.gate`（actor）：params `accepted_methods: ["cowboy","evm"]?` / `accepted_intents: ["charge","pass","subscription"]?` / `max_price_per_request: u256`；**前置**：actor 同时持 `ingress.http`
- `bridge.facilitate.evm`（runner，**deferred**）：params `chains: [u256]` / `min_confirmations: u32` / `facilitator_pubkey: bytes`

**子配置结构**（PaymentPolicy 内嵌）：
```
BudgetConfig { rate_limit_rps: u32, daily_cap: u256, fallback: "402"|"503", auto_refill: bool }
EpochConfig  { fee_per_epoch: u256, epoch_blocks: u32, min_purchase: u32, max_purchase: u32 }
PassConfig   { min_credits: u32, max_credits: u32, expiry_blocks: u64 }
AssetConfig  { asset: Address, network: string, method: string,
               intents: [string], x402_scheme: string?, decimals: u8, symbol: string }
```

**Wire 格式 fallback 链**（PaymentGate 评估顺序）：1) free → 2) active subscription → 3) valid pass → 4) actor budget → 5) per-request credential (MPP/x402) → 6) 402 challenge。

**Opcode**：无新 SystemInstruction（所有调用为 ActorMessage to `PAYMENT_GATE_ADDRESS = 0x11`）。

**源**: `refs/cips/cip-18-payments.md` §6-§22 + [[concepts/payments]]。

---

## MCP Ingress（CIP-19 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `MCP_PROTOCOL_VERSION` | `"2025-11-25"` | streamable HTTP transport spec pin |
| `MCP_SESSION_IDLE_TIMEOUT_SECONDS` | 600（10 min）| 闲置 session 回收 |
| `MAX_TOOL_INPUT_BYTES_DEFAULT` | 1,048,576（1 MiB）| 单 tools/call `arguments` 大小（governance default; `ingress.mcp.max_tool_input_bytes` 可调）|
| `MAX_TOOL_OUTPUT_BYTES` | 4,194,304（4 MiB）| Tool 响应硬上限，超 → 截断 + `isError: true` |
| `JSONRPC_PAYMENT_REQUIRED_CODE` | -32402 | 复用 CIP-18 §19 |
| `JSONRPC_INTERNAL_ERROR_CODE` | -32603 | HTTP 5xx 映射 |
| `JSONRPC_GATEWAY_DISPATCH_FAILED` | -32000 | 网络 / 超时 |
| `TOOLS_LIST_CHANGED_DEBOUNCE_MS` | 250 | `notifications/tools/list_changed` 节流 |

**新 Entitlement**：`ingress.mcp`（actor，**前置** `ingress.http`），params：

| 参数 | 类型 | 默认 |
|---|---|---|
| `server_name` | string? | `<actor>.cowboy.network` |
| `server_instructions` | string? | 空 |
| `tool_name_prefix` | string? | 空 |
| `exclude_routes` | [string]? | `[]` |
| `max_tool_input_bytes` | u32? | `MAX_TOOL_INPUT_BYTES_DEFAULT` |

**Tool name 规则**：`prefix + sanitize(route.target.name)`，`sanitize` 把非 `[a-zA-Z0-9_]` 替换为 `_`；保留前缀 `_cowboy_*`（v1 reserved only：`_cowboy_payment_quote` / `_cowboy_payment_subscribe` / `_cowboy_pass_purchase` / `_cowboy_health` / `_cowboy_info`）。

**Opcode**：无新 SystemInstruction（dispatch 复用 CIP-14 §8）。

**Endpoint**：`/_cowboy/mcp` —— 自 CIP-18 §17 已 reserved；本 CIP 定语义。

**源**: `refs/cips/cip-19-gateway-mcp-ingress.md` §7-§16 + [[concepts/mcp-ingress]]。

---

## Cross-Chain（CIP-25 Draft，尚未实装）

L1 / L2 / L3 三层架构常量。具体后端 / TVL 阈值 / TTL 由治理细化。

### L1（State Anchoring）

| 常量 | 值 / 默认 | 说明 |
|---|---|---|
| Runner committee threshold | 2-of-3（参考拓扑）| ECDSA；可由治理切其他后端 |
| 签名 domain 前缀 | `keccak256("Anchor.v1" \|\| src_chain \|\| dst_anchor_addr \|\| height \|\| roots)` | 防协议 / 版本 / dst 跨用 |
| Source-chain `min_confirmations` (ETH) | 32（高 TVL 64）| 反 reorg；Cowboy 源用确定性最终，无须此 |
| Stake economic floor `k` | k ≥ 10（建议）| `stake ≥ k × max_attestable_value` |
| Fraud-proof window | 7 days | dst 上 challenge 期；窗口内 L3 不释放资金 |
| `commitment_revoked` 阈值 | governance | deep-reorg 协议级撤销 |
| `MAX_TTL` (协议 GC) | 1 week | 老 commitment 自动清 |

### L2（Mailbox）

| 常量 | 值 / 默认 | 说明 |
|---|---|---|
| `expiry` (asset bridge default) | 24h（≈86,400 blocks @ 1s）| `send(...)` 默认；dst hard cutoff |
| `expiry` (oracle push) | 5 min | 推荐 TTL |
| `expiry` (lending) | 15 min | 推荐 TTL |
| `expiry` (one-shot RPC call) | 2 min | 推荐 TTL |
| `GRACE` (src reclaim 宽限) | 1h | `expiry + GRACE` 后允许 `reclaim` |
| `MAX_TIMEOUT` (bounty refund) | 7 days | 未投递 fee 回收上限 |
| `protocol_cut` / `relayer_bounty` | 20% / 80% | `send(..., fee)` 默认拆分 |

### L3 应用 TTL

| 应用 | 默认 TTL（依 `finalized_at`）|
|---|---|
| Asset bridge | 24h |
| Oracle push | 5 min |
| Lending | 15 min |
| One-shot RPC call | 2 min |

### 性能信封

| 后端 | 端到端延迟 | per-message gas（EVM dst）|
|---|---|---|
| Committee 2-of-3 | ~3 dst blocks 加 src finality | 200–300k gas（2 sig + 1 deliver）|
| BLS 聚合 (Stage 2) | 同 committee | per-message 降 60–70% at N ≥ 10 |

**新 SystemInstruction opcode**：无（按 CIP-25 §A.5 构造，所有交互均为 contract / actor message）。

**源**: `refs/cips/cip-25-cross-chain-architecture.md` §1.4–§3 + §A.6 + §B + [[concepts/cross-chain]]。

---

## Container Runtime（CIP-10 v2.r2 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `CONTAINER_REGISTRY_ADDRESS` | `0x10` | v2.r2 §1 落锁（从 v2.r1 `0x0F` 后移 +1）；v1 草案占位 `0x0...cowboy.containers` 已废 |
| `BILLING_DISPUTE_WINDOW` | 300 blocks（≈1h @ 12s）| 非 TEE billing 争议窗口 |
| Opcodes | 61–64 | 见主分配表 |

**费分配**: `system:container_settlement_config`（target_pool: CONTAINER）；默认 `runner 89 / treasury 1 / burn 10`，与 CIP-2 runner job 同。

**BillingAttestation TEE 路径**：`tee_signature: Option<CompositeAttestation>` 由 `0x0F` 调 `0x05::VerifyCae` (opcode 57) 校验。

**源**: `refs/cips/cip-10-runner-containers.md` Part II §1-§5。

---

## 变更记录
- **2026-05-11 (r2 sync)** — 地址段重排落地：发现代码已 commit `SESSION_ACTOR = 0x0C` (`system_actors.rs:35`)；CIP-14 / CIP-10 / CIP-15 / CIP-16 / CIP-18 各发 r2 修订把 v2 sequence 整体后移 +1（ROUTE 0x0D / GATEWAY 0x0E / RECEIPT 0x0F / CONTAINER 0x10 / PAYMENT_GATE 0x11）；CIP-9 v2 + CIP-15 v2 把 CBFS Merkle 描述从"RFC-6962-style"改正为"power-of-2 padded BLAKE3 binary Merkle"（按 `cbfs/manifest/src/merkle.rs:32-66`）。CIP-18 ↔ CIP-19 互列 Requires 而非 Companions。CIP-15 gateway-implementation 移除不存在的 §8.12 引用。
- **2026-05-11** 入库 CIP-18（Payments）/ CIP-19（Gateway MCP Ingress）/ CIP-25（Cross-Chain Architecture）/ CIP-15 gateway-implementation companion；新增 Payments / MCP Ingress / Cross-Chain 三参数段；PaymentGate 地址段对齐 gap 标 V-14（**r2 已解决**），新 entitlements (`payment.gate` / `ingress.mcp` / `bridge.facilitate.evm`) 标 V-15
- **2026-05-07** 在 SystemInstruction Opcode 主分配表段追加 MPP Session 研究/计划与 v2 主表 52-57 冲突告警；不改 v2 主表（v2 系列权威）
- **2026-04-21** 全 v2 系列对齐：opcode 重排（CIP-13 → 52-56；CIP-23 → 57-60；CIP-10 → 61-64；CIP-14 → 65/66；CIP-16 → 67）；新增 SettlementConfig target_pool 6 enum；CIP-14 系统 actor 收回到 0x0C/D/E + CIP-10 取 0x0F；CIP-5 revised 2026-04-20 timer fee_payer 模型；新增 SystemInstruction Opcode 主分配表与 Container Runtime 段
- **2026-04-20** 纳入 CIP-14 / CIP-15 / CIP-16 / CIP-23（全部 Draft）参数段；标注块时间假设不一致（1s vs 500ms）
- **2026-04-16** 纳入 CIP-12 / CIP-13（Draft）参数段，标明尚未实装；opcode 冲突标注至 drift
- **2026-04-15** 建立本表，以代码/修正案为权威基线
