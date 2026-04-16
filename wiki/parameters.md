---
type: parameter
tags: [constants, authoritative, cip-3, cip-12, cip-13]
sources:
  - node/types/src/constants.rs
  - node/execution/src/basefee.rs
  - node/execution/src/gas.rs
  - refs/analysis/2026-04-15_documentation_amendments.md
  - refs/cips/cip-3-fee-model.mdx
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/cips/cip-12-governance.md
  - refs/cips/cip-13-runner-delegation.md
last_updated: 2026-04-16
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

## 变更记录
- **2026-04-16** 纳入 CIP-12 / CIP-13（Draft）参数段，标明尚未实装；opcode 冲突标注至 drift。
- **2026-04-15** 建立本表，以代码/修正案为权威基线。
