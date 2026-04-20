---
type: parameter
tags: [constants, authoritative, cip-3, cip-12, cip-13, cip-14, cip-15, cip-16, cip-23]
sources:
  - node/types/src/constants.rs
  - node/execution/src/basefee.rs
  - node/execution/src/gas.rs
  - refs/analysis/2026-04-15_documentation_amendments.md
  - refs/cips/cip-3-fee-model.mdx
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/cips/cip-12-governance.md
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-15-public-asset-hosting.md
  - refs/cips/cip-16-custom-domains.md
  - refs/cips/cip-23-tee-execution.md
last_updated: 2026-04-20
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

## Timer（GBA 模型，CIP-1 风格）

| 参数 | 值 | 源 |
|---|---|---|
| 块 timer cycles 预算 | `8,888,890` | `node/execution/src/pvm_host.rs:1051-1097` |
| 单 timer cycles 上限 | `550,000` | 同上 |
| 执行时机 | Transactions → Timers（块尾）| `node/storage/src/speculative.rs:152-475` |

> CIP-1 描述"Timer 先于 Tx"，与代码相反；修正案 E-1。CIP-5 Globalbox EOB 未实现。

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

## Runner Stake 委托（CIP-13 Draft，尚未实装）

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
| 草案 opcode | 40–44 | ⚠️ **与现有 40–43 冲突**；见 [[drift]] |

**源**: `refs/cips/cip-13-runner-delegation.md` §4 / §3.3。

---

## DNS-Addressable Actors（CIP-14 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `ROUTE_REGISTRY_ADDRESS` | `0x0011` | 新 System Actor 地址段（见 [[entities/system-actors]]） |
| `GATEWAY_REGISTRY_ADDRESS` | `0x0012` | 同上 |
| `MIN_NAME_LENGTH` / `MAX_NAME_LENGTH` | 3 / 64 | 名称长度约束 |
| `NAME_GRACE_PERIOD` | 2,592,000 blocks（≈30d @ 1 block/sec）| 过期后宽限期 |
| `NAME_AUCTION_DURATION` | 604,800 blocks（≈7d）| Dutch 拍卖释放窗口 |
| `BLOCKS_PER_YEAR` | 31,536,000 | ⚠️ 假设 1 block/sec；CIP-23 用 500ms 假设，见 [[drift]] |
| `REGISTRY_PROTOCOL_FEE_BPS` | 1,000（10%）| 注册费入国库比例 |
| `GATEWAY_POOL_BPS` | 2,000（20%）| 注册费入 Gateway serving pool 比例（余下 70% burn）|
| `MIN_GATEWAY_STAKE` | governance-set | Gateway 注册最低 stake |
| `MAX_GATEWAY_HEALTH` | 3,600 blocks（≈1h）| Heartbeat 重置值；每块 -1 |
| `GATEWAY_UNSTAKE_DELAY` | 604,800 blocks（≈7d）| 解绑延迟 |
| `MAX_REQUESTS_PER_SECOND` | 100 | Per actor per gateway |
| `MAX_CONCURRENT_CONNECTIONS` | 1,000 | Per actor per gateway |
| `RESULT_TTL_BLOCKS` | 3,600（≈1h）| Command-path 结果在 Actor 存储中的默认 TTL |
| `PROTOCOL_MAX_REQUEST_BYTES` | 10,485,760（10 MiB）| 协议 ceiling；Actor 可在 `ingress.http` params 中降低 |
| `PROTOCOL_MAX_RESPONSE_BYTES` | 10,485,760 | 同上 |
| `PROTOCOL_MAX_QUERY_CYCLES` | 100,000,000 | Query-path PVM cycles ceiling |

**`ingress.http` 默认 params**: `allowlist_methods=["GET","HEAD","POST"]`, `max_request_bytes=1 MiB`, `max_response_bytes=1 MiB`, `max_query_cycles=10_000_000`。

**源**: `refs/cips/cip-14-dns-addressable-actors.md` §10。

---

## Public Asset Hosting（CIP-15 Draft，尚未实装）

| 常量 | 值 | 说明 |
|---|---|---|
| `MAX_STATIC_ROUTES` / `MAX_DYNAMIC_ROUTES` | 100 / 100 | `_meta/routes.json` 条目上限 |
| `MAX_ROUTE_MANIFEST_SIZE` | 65,536 B | 路由清单 size cap |
| `MANIFEST_POLL_INTERVAL` | 6 blocks（≈6s）| 失效轮询周期 |
| `METADATA_CACHE_TTL` | 60 s | `_meta/*` 缓存 TTL |
| `MAX_GATEWAY_CACHE_BYTES` | 10 GiB | 单 Gateway 对象 cache 总上限 |
| `DEFAULT_MAX_CACHE_PER_VOLUME` | 100 MiB | Entitlement 未声明时默认 |
| `DEFAULT_MAX_STATIC_RESPONSE_BYTES` | 10 MiB | 单资产响应默认上限 |
| `PROTOCOL_MAX_STATIC_RESPONSE_BYTES` | 100 MiB | Hard ceiling |
| `HEDGE_THRESHOLD_MS` | 100 ms | 投机并发 shard 请求阈值 |
| `MAX_CONCURRENT_SHARD_FETCHES` | 8 | 单对象重建最大并发 |
| `DEFAULT_CORS_MAX_AGE` | 86,400 s（24h）| `Access-Control-Max-Age` |
| `MAX_CORS_RULES` | 50 | `_meta/cors.json` 条目上限 |

**ingress.http 新增 params**: `static_volumes: [{volume_name, max_cache_bytes}]`（默认 `[]`）, `max_static_response_bytes`（默认 10 MiB）。

**源**: `refs/cips/cip-15-public-asset-hosting.md` §10。

---

## Custom Domains & First-Party TLDs（CIP-16 Draft，尚未实装）

| 常量 | 值 |
|---|---|
| `NAMESPACE_COWBOY_NETWORK / FIRST_PARTY_TLD / EXTERNAL` | 0 / 1 / 2 |
| `TLD_COW / TLD_COWBOY` | 1 / 2 |
| `CHALLENGE_EXPIRY_BLOCKS` | 43,200（≈12h @ 1s）|
| `EXTERNAL_REVERIFY_INTERVAL` | 2,592,000（≈30d）|
| `CANONICAL_EDGE_HOSTNAME` | `edge.cowboy.network` |
| `ACME_DELEGATION_ZONE` | `acme.cowboy.network` |

**源**: `refs/cips/cip-16-custom-domains.md` §12。

---

## TEE Execution（CIP-23 Draft，尚未实装）

| 参数 | 默认 | 说明 |
|---|---|---|
| `MAX_QUOTE_AGE` | 150 blocks（≈75s @ 500ms；≈150s @ 1s）| Quote 新鲜度窗口 |
| `BINDING_RENEWAL_PERIOD` | 12,096 blocks（≈7d @ 500ms）| Measurement binding 续约 |
| `ROOT_UPDATE_DELAY` | 1 week | `UpdateCpuRoot` / `UpdateNrasRoot` 延迟生效 |
| `SEEN_NONCE_GC_WINDOW` | = `DISPUTE_WINDOW_BLOCKS` (75) | Nonce 回收与争议窗口对齐 |
| `MAX_CAE_ON_CHAIN_BYTES` | 64（仅 digest）| 完整 CAE 走 CIP-9 存 CID |
| 新 opcodes | 50–53 | `VerifyCae` / `UpdateCpuRoot` / `UpdateNrasRoot` / `GcNonces`；与 CIP-13 Draft 40–44 不冲突 |

**Gas 预算**: `VerifyCae` (TDX + NCC) ≈ 200k cycles + 64 cells，每块 `BLOCK_CYCLES_TARGET = 20M` 下可验 ~100 个 CAE。

**源**: `refs/cips/cip-23-tee-execution.md` §3.13、§3.6.5。

---

## 变更记录
- **2026-04-20** 纳入 CIP-14 / CIP-15 / CIP-16 / CIP-23（全部 Draft）参数段；标注块时间假设不一致（1s vs 500ms）。
- **2026-04-16** 纳入 CIP-12 / CIP-13（Draft）参数段，标明尚未实装；opcode 冲突标注至 drift。
- **2026-04-15** 建立本表，以代码/修正案为权威基线。
