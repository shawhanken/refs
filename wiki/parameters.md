---
type: parameter
tags: [constants, authoritative, cip-3, cip-5, cip-12, cip-13, cip-14, cip-15, cip-16, cip-23]
sources:
  - node/types/src/constants.rs
  - node/types/src/execution.rs
  - node/execution/src/basefee.rs
  - node/execution/src/gas.rs
  - refs/analysis/2026-04-15_documentation_amendments.md
  - refs/cips/cip-3-fee-model.mdx
  - refs/cips/cip-2-offchain-compute-v2.md
  - refs/cips/cip-5-timers.md
  - refs/cips/cip-12-governance.md
  - refs/cips/cip-13-runner-delegation-v2.md
  - refs/cips/cip-14-dns-addressable-actors-v2.md
  - refs/cips/cip-15-public-asset-hosting-v2.md
  - refs/cips/cip-16-custom-domains-v2.md
  - refs/cips/cip-23-tee-execution-v2.md
last_updated: 2026-04-21
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

**源**: `refs/cips/cip-13-runner-delegation-v2.md` §1（opcode 主表）+ §4（参数）。

---

## DNS-Addressable Actors（CIP-14 v2 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `ROUTE_REGISTRY_ADDRESS` | `0x0C` | v2 收回；v1 草案 `0x0011` 已废 |
| `GATEWAY_REGISTRY_ADDRESS` | `0x0D` | v2 收回；v1 草案 `0x0012` 已废 |
| `RECEIPT_REGISTRY_ADDRESS` | `0x0E` | v2 新增（替代 v1 `_http/results/{id}` actor-KV 模式）|
| `MIN_NAME_LENGTH` / `MAX_NAME_LENGTH` | 3 / 64 | 名称长度约束 |
| `NAME_GRACE_PERIOD` | 2,592,000 blocks（≈30d @ 1 block/sec）| 过期后宽限期 |
| `NAME_AUCTION_DURATION` | 604,800 blocks（≈7d）| Dutch 拍卖释放窗口 |
| `BLOCKS_PER_YEAR` | 31,536,000 | ⚠️ 假设 1 block/sec；CIP-23 用 500ms 假设，见 [[drift]] |
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

**源**: `refs/cips/cip-14-dns-addressable-actors-v2.md` Part II §10（v2 常量），Part II §3 / §4 / §6 / §7 / §8（其他细节）。

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

**源**: `refs/cips/cip-15-public-asset-hosting-v2.md` Part II §3-§8 + `refs/cips/cip-9-runner-storage-v2.md` §2-§5（GET_MANIFEST RPC、ManifestCommitted 事件、CBFS Merkle、status 映射）。

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

**源**: `refs/cips/cip-16-custom-domains-v2.md` Part II §3-§10。

---

## TEE Execution（CIP-23 v2 Draft，尚未实装）

| 参数 | 默认 | 说明 |
|---|---|---|
| `MAX_QUOTE_AGE` | 150 blocks（≈75s @ 500ms；≈150s @ 1s）| Quote 新鲜度窗口 |
| `BINDING_RENEWAL_PERIOD` | 12,096 blocks（≈7d @ 500ms）| Measurement binding 续约 |
| `ROOT_UPDATE_DELAY` | 1 week | `UpdateCpuRoot` / `UpdateNrasRoot` 延迟生效 |
| `SEEN_NONCE_GC_WINDOW` | = `DISPUTE_WINDOW_BLOCKS` (75) | Nonce 回收与争议窗口对齐 |
| `MAX_CAE_ON_CHAIN_BYTES` | 64（仅 digest）| 完整 CAE 走 CIP-9 存 CID |
| Opcodes | **57–60** | `VerifyCae` / `UpdateCpuRoot` / `UpdateNrasRoot` / `GcNonces`（v2 §4，从 v1 §3.6.2 的 50-53 修正；v1 50-53 与代码 `SYS_EXTEND_TIMER=50` / `SYS_DEPLOY_CODE=51` 冲突）|
| `CANONICAL_TEE_TYPES` | `["sgx", "sev", "tdx"]` | ⚠️ v2 §2 要求追加 `"nitro"` (precondition)；详见 [[concepts/tee-attestation]] |

**`tee_type` → `VerificationMode` 资格映射**（v2 §2）: `tdx` / `sev` / `nitro` 全 mode 含 `Deterministic`；`sgx` 排除 `Deterministic`（legacy tier）。

**BillingAttestation 数据源**（v2 §5.1）: `tee_signature: Option<CompositeAttestation>` 是**每次 billing event 临时生成**，不缓存 measurement_binding 时的 quote。`freshness.nonce = keccak(billing_fields ‖ submission_block_hash)`。

**Gas 预算**: `VerifyCae` (TDX + NCC) ≈ 200k cycles + 64 cells，每块 `BLOCK_CYCLES_TARGET = 20M` 下可验 ~100 个 CAE。

**源**: `refs/cips/cip-23-tee-execution-v2.md` Part II §1-§5。

---

## SystemInstruction Opcode 主分配表（CIP-13 v2 §1 canonical）

| Opcode | Name | Source |
|---:|---|---|
| 0–9 | basic + Runner registry + Job dispatch | code |
| 10–20 | Token operations (incl. batch) | code |
| 21–29 | (reserved) | — |
| 30–35 | Entitlement operations | code |
| 36–39 | (reserved) | — |
| **40** | `UpdateSettlementConfig` | code (CIP-3) |
| 41 | `FundActor` | code |
| 42 | `KeyDelivery` | code |
| 43 | `UpgradeActor` | code |
| 44 | `UpdateBasefeeConfig` | code (CIP-3) |
| 45 | `SubmitProposal` | code (CIP-12 占位) |
| 46 | `CastVote` | code |
| 47 | `ExecuteProposal` | code |
| **48** | `CancelTimer` | code (CIP-5 §5.4) |
| **49** | `UpdateTimerConfig` | code (CIP-5 §6.4) |
| **50** | `ExtendTimer` | code (CIP-5 §5.4) |
| 51 | `DeployCode` | code |
| **52–56** | CIP-13 v2 委托：`RunnerUpdateDelegationConfig` / `RunnerDelegateStake` / `RunnerIncreaseDelegation` / `RunnerUndelegateStake` / `RunnerClaimUnbonded` | CIP-13 v2 §1 |
| **57–60** | CIP-23 v2 TEE：`VerifyCae` / `UpdateCpuRoot` / `UpdateNrasRoot` / `GcNonces` | CIP-23 v2 §4 |
| **61–64** | CIP-10 v2 容器：`RegisterBaseImage` / `DeregisterBaseImage` / `RegisterResourceClass` / `DeregisterResourceClass` | CIP-10 v2 §5 |
| **65** | `IngressDispatch` | CIP-14 v2 §6.1 |
| **66** | `CompleteReceipt` | CIP-14 v2 §8 |
| **67** | `ExternalDomainCallback` | CIP-16 v2 §5.6 |
| 68–69 | (reserved) | — |
| 70+ | (reserved for future CIPs) | — |

代码现状 0–51 已分配。v2 系列 52–67 是 precondition。

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

## Container Runtime（CIP-10 v2 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `CONTAINER_REGISTRY_ADDRESS` | `0x0F` | v2 §1 落锁；v1 草案占位 `0x0...cowboy.containers` 已废 |
| `BILLING_DISPUTE_WINDOW` | 300 blocks（≈1h @ 12s）| 非 TEE billing 争议窗口 |
| Opcodes | 61–64 | 见主分配表 |

**费分配**: `system:container_settlement_config`（target_pool: CONTAINER）；默认 `runner 89 / treasury 1 / burn 10`，与 CIP-2 runner job 同。

**BillingAttestation TEE 路径**：`tee_signature: Option<CompositeAttestation>` 由 `0x0F` 调 `0x05::VerifyCae` (opcode 57) 校验。

**源**: `refs/cips/cip-10-runner-containers-v2.md` Part II §1-§5。

---

## 变更记录
- **2026-04-21** 全 v2 系列对齐：opcode 重排（CIP-13 → 52-56；CIP-23 → 57-60；CIP-10 → 61-64；CIP-14 → 65/66；CIP-16 → 67）；新增 SettlementConfig target_pool 6 enum；CIP-14 系统 actor 收回到 0x0C/D/E + CIP-10 取 0x0F；CIP-5 revised 2026-04-20 timer fee_payer 模型；新增 SystemInstruction Opcode 主分配表与 Container Runtime 段
- **2026-04-20** 纳入 CIP-14 / CIP-15 / CIP-16 / CIP-23（全部 Draft）参数段；标注块时间假设不一致（1s vs 500ms）
- **2026-04-16** 纳入 CIP-12 / CIP-13（Draft）参数段，标明尚未实装；opcode 冲突标注至 drift
- **2026-04-15** 建立本表，以代码/修正案为权威基线
