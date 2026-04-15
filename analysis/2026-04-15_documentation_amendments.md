# 文档修正案 — 代码一致性对齐

**日期**: 2026-04-15  
**范围**: 基于 `node/` 与 `runner/` 两个 Rust workspace 的实际代码，修正 whitepaper / CIPs / 历史文档中与当前实现不一致的常量、公式、枚举和算法描述。  
**原则**:
- 本修正案不改写原文，原文保留以维护历史可追溯性
- 本修正案为**当前权威值**；冲突以本修正案（及源代码）为准
- `whitepaper/` 受保护，不修改；白皮书相关差异记录在本文档表格中
- 各受影响 CIP 顶部加指向本文档的指示条幅

---

## 一、经济学参数（CIP-3）

### A-1. BLOCK_CYCLES_TARGET

| 旧值 / 来源 | 修正值（代码权威）|
|---|---|
| CIP-3 §2.2、WP §4.3：`10,000,000 cycles/block` | **`20,000,000 cycles/block`** |

- **代码依据**: `node/types/src/constants.rs:46`
- **影响**: Basefee 反馈环平衡点、每块吞吐量上限、车道（lane）容量配比

### A-2. BLOCK_CELLS_TARGET

| 旧值 / 来源 | 修正值（代码权威）|
|---|---|
| CIP-3 §2.2、WP §4.3：`500,000 cells/block` | **`4,000,000 cells/block`** |

- **代码依据**: `node/types/src/constants.rs:50`
- **影响**: 存储计量、每块 cell 容量、payload 收费

### A-3. Basefee 更新公式

| 旧值 / 来源 | 修正值（代码权威）|
|---|---|
| WP §4.2：`max(1, bf × (1 + clamp((U−T)/(T×α), −δ, +δ)))`，α=8，δ=12.5% | **几何更新**：`Δ = basefee × |used−target| / target / ALPHA`；最终变化 clamp 到 `basefee / DENOM`；`ALPHA = 96`、`DENOM = 96`、`MIN_BASEFEE = 10,000`、`MAX_BASEFEE = 10²⁴` |
| WP §17.8：简化线性 `bf × (1 + δ × (U-T)/T)` | 不使用 |

- **代码依据**: `node/execution/src/basefee.rs:99-119`
- **与旧表述差异**: ALPHA 由 8 → 96（反馈更温和），MIN_BASEFEE 由 1 → 10,000

### A-4. Transfer 指令成本

| 维度 | 旧值（WP §17.2）| 修正值（代码权威）|
|---|---|---|
| Cycles | 21,000 | **5,000** |
| Cells | 0 | **500** |

- **代码依据**: `node/execution/src/gas.rs:163-164`

---

## 二、System Actor 地址表（CIP-2 / WP §9）

**旧表述分歧**：WP §9、CIP-2、workspace CLAUDE.md 三方对 `0x01/0x03/0x06` 的职能互相冲突。

**修正值（代码权威）** — `node/runner/src/system_actors.rs:13-33`：

| 地址 | 职能 |
|---|---|
| `0x01` | RUNNER_REGISTRY |
| `0x02` | JOB_DISPATCHER |
| `0x03` | RESULT_VERIFIER |
| `0x04` | SECRETS_MANAGER |
| `0x05` | TEE_VERIFIER |
| `0x06` | DUAL_BASEFEE |
| `0x07` | ENTITLEMENT_REGISTRY |
| `0x08` | TREASURY |
| `0x09` | GOVERNANCE |
| `0x0A` | STORAGE_MANAGER |
| `0x0B` | RELAY_REGISTRY |

**注**：workspace `/home/ubuntu/workspace/CLAUDE.md` 中列出的 `0x91-0x95` 已不在代码中；应以本表为准。

---

## 三、Runner 质押公式（CIP-2 §5 / WP §5.2、§17.7）

**旧表述分歧**：
- WP §5.2：`stake >= max(10,000 CBY, 1.5 × declared_max_job_value)`
- WP §17.7：`stake >= 10 × average_job_value`

**修正值（代码权威）** — `node/execution/src/runner/registry.rs:65-80`：

注册时需同时满足两条件：
1. `stake >= 10,000 CBY`（地板价）
2. `stake >= max_job_value × 3/2`（即 1.5 倍 `declared_max_job_value`）

**结论**: WP §5.2 正确，WP §17.7 过时。10× average_job_value 的表述不在代码中。

---

## 四、Runner VerificationMode（CIP-2 §5）

**旧表述**：WP §5 列 4 种模式（TEE Attestation / Majority Vote / ZK-Proof / Economic Bond）。

**修正值（代码权威）** — `node/runner/src/types.rs`：**6 种 variant**
1. `None` (0)
2. `EconomicBond` (1)
3. `MajorityVote` (2)
4. `StructuredMatch` (3)
5. `Deterministic` (4) — TEE 要求 + 字节级相同
6. `SemanticSimilarity` (5)

**ZK-Proof 模式尚未实现**；代码实际扩展增加了 `StructuredMatch` 与 `SemanticSimilarity`。

---

## 五、Timer 机制（CIP-1 / CIP-5）

### E-1. Timer 与交易的执行顺序

| 来源 | 表述 |
|---|---|
| CIP-1 | 先 Timer，后交易 |
| WP / CIP-5 | 先交易，后 Timer |

**修正值（代码权威）** — `node/storage/src/speculative.rs:152-475`：
- 块内流程：交易执行（L152-370）→ 同块内过期 Timer 作为 deferred tx 执行（L373-475）
- **结论**：CIP-1 表述错误；WP/CIP-5 表述正确；修正 CIP-1 的顺序描述

### E-2. Timer 调度模型（CIP-1 GBA vs CIP-5 Globalbox EOB）

**修正值（代码权威）** — `node/execution/src/pvm_host.rs:1051-1097`：
- 代码已实现 **CIP-1 风格 GBA 调度**：actor 通过 `schedule_timer` host API 注册未来 block height 的 timer，块尾 inline 作为 deferred tx 执行
- 块 timer 预算: **8,888,890 cycles**；单 timer 上限: **550,000 cycles**
- **CIP-5 Globalbox EOB timers 尚未实现**（见 workspace CLAUDE.md 明确标注）

---

## 六、Address 方案

**旧表述**：`node/2026-02-24_ADDRESS_MIGRATION_ETH_STYLE.md` 提案从 Ed25519 迁移到 Ethereum 风格，长期悬而未决。

**修正值（代码权威）**:
- `Address = [u8; 20]`（20 字节 ETH 风格）— `node/types/src/address.rs:8-12`
- 签名使用 **secp256k1 ECDSA**，65 字节（r‖s‖v）— `node/types/src/signature.rs:9-18`
- 派生：`keccak256(secp256k1_pubkey_uncompressed[1..])[12..]`

**结论**：迁移已完成。`ADDRESS_MIGRATION_ETH_STYLE` 提案可视为**已采纳并实施**。

---

## 六·补. Token Hook 计费（CIP-20）

**旧表述**：`cip-20-fungible-tokens.mdx` 定义 token hook 上限 `50,000 cycles`，语义为强制计费上限。

**修正值（代码权威）** — 参见 `economics/2026-04-13_fee-audit-report.md §相关章节`：
- `token_hook_max_cycles = 50,000` 已在常量中**声明**，但当前代码路径**尚未真正执行扣费/中断**（"declared but not enforced"）
- 属**阶段 1**（接口与上限定义），**阶段 2** 才接入实际扣费与 revert
- 因此当前 hook 超额执行**不会被中断**，但未来阶段 2 启用后会严格执行 50K 上限

**所涉文档**: `cips/cip-20-fungible-tokens.mdx`

---

## 六·补². Runner 最低 Stake 的两层门槛

**旧表述分歧**：
- `runner/2026-03-03_Entitlement.md` 硬编码 `MIN_STAKE = 50,000 CBY`
- 修正案 §三（C 项）：`stake >= 10,000 CBY`（注册 floor）

**澄清（非冲突，而是两层语义）**:

| 门槛 | 值 | 语义 | 适用场景 |
|---|---|---|---|
| **注册 floor** | `10,000 CBY` | 链上 Runner Registry 接受注册的硬性最低 | 注册时 `registry.rs` 检查 |
| **工作经济门槛** | `50,000 CBY` | Runner 被判定为可承接工作、进入候选池的经济保证 | 工作分发/Entitlement 授予/信誉系统场景 |

两者并存、不冲突。文档应在引用时明确属哪一层。

**所涉文档**: `runner/2026-03-03_Entitlement.md`、`cips/cip-2-offchain-compute.mdx`

---

## 六·补³. Runner 文档 API 漂移（2026-04-15 审计）

本节集中 H-1 / H-2 / H-3 / M-1 / M-4 / L-1/2/3。源文档主要为 `refs/runner/2026-02-05_DOCUMENTATION.md`、`SUBMIT_JOB_GUIDE.md`、`QUICK_SUBMIT.md`、`QUICK_START_MCP.md`。

### H-1. Runner 地址格式

**旧表述**：文档多处声明 Runner 地址为 "32 字节 Ed25519 公钥，十六进制 64 字符"；私钥亦描述为 32 字节。

**修正值（代码权威）**:
- Runner 地址 = `Address([u8; 20])`，Ethereum 风格，40 字符 hex（可选 `0x` 前缀）
- 由 secp256k1 公钥派生：`keccak256(pubkey_uncompressed[1..])[12..]`
- 私钥 = 32 字节 secp256k1 标量（hex 表达 64 字符，与原文描述巧合一致；但其语义是 secp256k1 scalar，非 Ed25519 seed）
- `runner_key.json` 格式未变，但内部是 secp256k1 密钥对

**源**: `runner/crates/runner-common/src/types.rs:74`、`node/types/src/address.rs:8-12`

### H-2. VerificationMode 枚举名

**旧表述**：Runner 提交示例 JSON 用 `"mode": "HappyCase"`。

**修正值**：代码中**无** `HappyCase` variant。合法值（`runner-common/src/types.rs:270-319`）：
- `"none"`
- `"economicbond"`
- `"majorityvote"`
- `"structuredmatch"`
- `"deterministic"`
- `"semanticsimilarity"`

（serde 反序列化支持小写）。历史推测：`HappyCase` 是早期草稿名称，代码改名未同步到文档。

### H-3. VerificationMode JSON Schema

**旧表述**：示例只写 `{"mode": "HappyCase"}`，无其它字段。

**修正值（代码权威字段）**:

```jsonc
// None - 单 runner 无验证
{"mode": "none"}

// EconomicBond
{
  "mode": "economicbond",
  "bond_multiplier": 3,        // u32，bond = max_job × N
  "objective_checks": [...]    // 可选 VerifierCheck[]
}

// MajorityVote / StructuredMatch / SemanticSimilarity
{
  "mode": "majorityvote",       // 或 structuredmatch / semanticsimilarity
  "runners": 3,                 // u8，N of M
  "threshold": 2,               // u8，>= threshold 通过
  "checks": [...]               // StructuredMatch / SemanticSimilarity 专用
}

// Deterministic
{
  "mode": "deterministic",
  "inference_config": {...}     // TEE attestation 配置
}
```

`VerifierCheck` variants（`runner-common/src/types.rs`）:
- `{"type": "NumericRange", "field": "x", "min": 0.0, "max": 1.0}`
- `{"type": "StringEqual", "field": "x", "value": "..."}`
- `{"type": "Custom", "actor_hex": "0x...", "method": "..."}`

### M-1. VerificationMode 字段级 schema 应补入 Runner 文档

`DOCUMENTATION.md` 仅列 variant 名，未给字段。用户需读源码。建议把 H-3 schema 补到 `DOCUMENTATION.md` 的 VerificationMode 小节。

### M-4. CallbackInfo.actor 地址格式

**旧表述**：`DOCUMENTATION.md` 提 `SystemInstruction::JobSubmit` 但未说明 callback actor 地址形态。

**修正值（代码权威）**:
```rust
CallbackInfo { actor: Address, method: String, ... }  // Address = [u8; 20]
```
Callback 必须是 20 字节 ETH 风格地址，与 Runner 地址同规格。

### L-1 / L-2 / L-3（低严重，待就地修复）
- L-1：Timer 块预算 `8,888,890 cycles`、单 timer `550,000 cycles`（`node/execution/src/pvm_host.rs:1051-1097`），Runner 文档若涉及 timer 回调应补
- L-2：默认端口：Chain RPC `4000`；examples 中 indexer 通常 `8080`
- L-3：`refs/pvm/01-API参考与使用指南.md` 过时警告应加链接 `node/execution/src/pvm_host.rs`、`node/execution/src/gas.rs`

---

## 七、修正案覆盖清单

| # | 修正条目 | 所涉文档 | 严重性 |
|---|---|---|---|
| A-1 | BLOCK_CYCLES_TARGET = 20M | cip-3, WP §4.3/§17, workspace CLAUDE.md | 高 |
| A-2 | BLOCK_CELLS_TARGET = 4M | cip-3, WP §4.3/§17, workspace CLAUDE.md | 高 |
| A-3 | Basefee 公式 ALPHA=96, MIN=10,000 | cip-3, WP §4.2/§17.8 | 高 |
| A-4 | Transfer 5,000 cycles / 500 cells | cip-3, WP §17.2 | 中 |
| B | System Actor 地址表 0x01-0x0B | cip-2, WP §9, workspace CLAUDE.md | 高 |
| C | Runner 质押 `max(10K, 1.5×max_job)` | cip-2, WP §5.2 采纳 / §17.7 作废 | 高 |
| D | VerificationMode 6 variants | cip-2, WP §5 | 中 |
| E-1 | Timer 先于交易 → 反之 | cip-1 修正 | 高 |
| E-2 | CIP-1 GBA 已实现，CIP-5 未 | cip-5 标记 Superseded | 中 |
| F | Address 20 字节 ETH，secp256k1 | `node/2026-02-24_ADDRESS_MIGRATION_ETH_STYLE.md` 标注已完成 | 中 |
| G-1 | Token hook 50K cycles 为阶段 1 声明、未强制扣费 | cip-20, economics/2026-04-13_fee-audit-report.md | 中 |
| G-2 | Runner stake 两层门槛（10K 注册 / 50K 工作经济） | cip-2, runner/2026-03-03_Entitlement.md | 中 |
| H-1 | Runner 地址 = 20 字节 ETH（非 32 字节 Ed25519）| runner/2026-02-05_DOCUMENTATION.md L146/207/229-230、SUBMIT_JOB_GUIDE.md、QUICK_SUBMIT.md | 高 |
| H-2 | VerificationMode `HappyCase` 不存在 | runner/2026-02-05_SUBMIT_JOB_GUIDE.md、QUICK_SUBMIT.md、QUICK_START_MCP.md | 高 |
| H-3 | MCP/Job 提交示例缺 mode 必需字段（runners/threshold/checks/inference_config）| 同上 runner/ 多份 | 高 |
| M-1 | VerificationMode 各 variant 字段级 schema 未记录 | runner/2026-02-05_DOCUMENTATION.md | 中 |
| M-4 | `CallbackInfo.actor` 地址格式未声明（20 字节 ETH）| runner/2026-02-05_DOCUMENTATION.md L184 | 中 |
| L-1 | Timer 预算 / 单 timer 上限未出现在 runner 文档 | runner/ 全部 | 低 |
| L-2 | RPC 端口默认表缺失（4000、8080）| runner/、node/ | 低 |
| L-3 | PVM Checkpoint API 过时警告缺权威源链接 | pvm/01-API参考与使用指南.md | 低 |

---

## 八、后续行动

1. ✅ 本修正案已发布
2. 待办：在受影响 CIP 顶部加指向本文档的指示条幅（`cip-1`、`cip-2`、`cip-3`、`cip-5`）
3. 待办：更新 workspace 根 `CLAUDE.md` 的常量与 System Actor 地址表
4. 待办：`node/2026-02-24_ADDRESS_MIGRATION_ETH_STYLE.md` 顶部加"已实施"标记
5. 建议：下次 whitepaper 修订时同步本修正案的权威值

**权威顺序**: 代码 > 本修正案 > CIP > whitepaper > 其它文档
