# Cowboy 经济系统对齐评估与修复计划

## Context

用户指示：**以最新白皮书 (WP §17 — 自我声明权威) 和 CIPs 为最高权威**，经济系统实现必须与之高度一致。本计划对照权威文档对当前代码进行全面评估，并给出分级修复方案。

**权威层级**（已确认）：
1. **CIP-3** — Actor API 成本（WP §17.3 注明："in case of conflict, CIP-3 is normative"）
2. **WP §17** — 总体费用模型（§17.1 声明："This section is authoritative"）
3. 其他地方（§3.5、CIP 以外）均为非规范性参考

---

## 评估结果：当前状态

### ✅ 已正确实现（与 WP+CIP-3 一致）

| 项目 | 规格值 | 代码值 | 来源 |
|------|--------|--------|------|
| BLOCK_CYCLES_TARGET | 10,000,000 | 10,000,000 | WP §17.8 / CIP-3 §2.4 |
| BLOCK_CELLS_TARGET | 500,000 | 500,000 | WP §17.8 |
| Cycles 硬上限 | 20,000,000 | — (逻辑存在但未单独常量) | WP §4.3 |
| BASEFEE_ALPHA | 8 | 8 | WP §4.2 |
| BASEFEE_MAX_CHANGE_DENOM | 8 (±12.5%) | 8 | WP §4.2 |
| MIN_BASEFEE | 1 | 1 | WP §17.8 |
| EIP-1559 双轨公式 | ✓ | ✓ | WP §17.8 |
| 100% basefee 销毁 | ✓ | ✓ | WP §4.2 |
| Lane 预算 (5M+2.5M+2M+0.5M=10M) | ✓ | ✓ | WP §17.9 |
| send_message (mailbox) | 80 cycles | 80 | CIP-3 §2.2.1 |
| storage_read | 10 cycles | 10 | CIP-3 §2.2.1 |
| storage_write | 50 cycles | 50 | CIP-3 §2.2.1 |
| timer set/cancel | 200 cycles | 200 | CIP-3 §2.2.1 |
| token_transfer | 1,000/64 | 1,000/64 | WP §17.3 / CIP-20 |
| token_approve | 500/32 | 500/32 | WP §17.3 |
| token_mint | 1,000/64 | 1,000/64 | WP §17.3 |
| token_burn | 500/64 | 500/64 | WP §17.3 |
| token_hook_max | 50,000 cycles | 50,000 | WP §17.3 / CIP-20 §8.3 |
| asyncio.gather 禁止 | ✓ | ✓ | CIP-3 §2.2.3.11 |
| C API 黑名单 (ctypes/cffi) | ✓ | ✓ | CIP-3 §2.2.3.3 |
| UTF-8 only | ✓ | ✓ | CIP-3 §2.2.3.10 |
| 大整数 4096 位限制 (编译期) | ✓ (compile-time) | ✓ | CIP-3 §2.2.3.9 |

---

## ❌ 发现的差距（需修复）

### P0 — 共识关键常量错误

这些是 CIP-3/WP 明确规定的、共识关键的成本常量，当前代码值错误：

| 项目 | 规格值 | 当前代码值 | 偏差 | 文件 |
|------|--------|-----------|------|------|
| **secp256k1 verify** | **3,000 cycles** | 10,000 cycles | 3.3× 偏高 | `gas.rs:196` |
| **keccak256 公式** | **6 cycles/32 bytes** (无 base) | 500 base + 10/136 bytes | 完全不同 | `gas.rs:193-194`, `pvm_host.rs:926-927` |
| **BLS verify** | **8,000 cycles** | 未定义 | 缺失 | `gas.rs` |

> CIP-3 §2.2.1 明确列出这三项，WP §17.3 也明确写 `verify_signature() = 3,000 cycles`。

**keccak256 正确公式**：
```rust
// CIP-3: 6 cycles per 32 bytes
let keccak_cost = ((input_len as u64 + 31) / 32) * 6;
// 去掉 base 500，去掉 per-136-byte 分块计费
```

**pvm_host.rs 中 keccak256 的两处调用**（line 924-928 和 1027-1031）都需要同步修改。

---

### P1 — 成本公式偏差

| 项目 | 规格值 | 当前代码值 | 来源 |
|------|--------|-----------|------|
| **sha256 公式** | 100 cycles base + 1/byte (WP §17.3 `hash()`) | 500 base + 8/64bytes | WP §17.3 |
| **serialization** | 20 cycles base + 1/byte (CIP-3 §2.2.3.12) | 200 base + 2/byte | CIP-3 §2.2.3.12 |
| **emit_event cycles** | 500 cycles + 5 cycles/byte (WP §17.3) | **0 cycles（未充 cycles）** | WP §17.3 |
| **emit_event cells** | 0.5 cells/byte (WP §17.4) | 50 base + 1/byte | WP §17.4 |
| **token_create_cells** | 256 + name.len + symbol.len (WP §17.3) | 5,000 (flat) | WP §17.3 |

> `emit_event` 的修复：在 `pvm_host.rs:724` 的 `emit_event()` 实现中，需补充 cycles 充值（500 + 5×len），并修正 cells 公式（当前 50+len → 改为 (len+1)/2）。

---

### P2 — 缺失 Host API 实现

| 功能 | 规格要求 | 当前状态 | 来源 |
|------|---------|---------|------|
| **get_block_info** | 100 cycles | 未实现 | WP §17.3 |
| **Proposer tip 路由** | tip → validator tip_address | 当前烧到 Address::ZERO | WP §4.2 |
| **Block Cycles 上限强制** | 硬上限 20,000,000 | 常量未使用 | WP §17.8 |

---

### P3 — VM 级别 (需 PVM 改造，复杂，建议单独 milestone)

| 功能 | 规格要求 | 当前状态 | 来源 |
|------|---------|---------|------|
| 大整数运行时 OverflowError | Runtime 操作超 4096 位抛出错误 | 仅 compile-time 静态检查 | CIP-3 §2.2.3.9 |
| 大整数比例成本 | `base + max(bitlen(a),bitlen(b)) / 64` cycles | 未计费 | CIP-3 §2.2.3.9 |
| 模块 import 成本 | 100 cycles (首次) / 5 cycles (重复) | 未计费 | CIP-3 §2.2.3.8 |
| 动态类型附加成本 | 字符串/列表拼接按长度附加 | 未计费 | CIP-3 §2.2.3.1 |
| 异常处理成本 | try/raise/except/finally 各有固定 cycles | 未计费 | CIP-3 §2.2.3.6 |
| 浮点确定性 | 强制软件浮点 | 未强制 | CIP-3 §2.2.3.5 |

---

### P4 — 重大新功能（超出当前 scope）

| CIP | 功能 | 状态 |
|-----|------|------|
| WP §17.5 | State Rent (租金机制) | 未实现 |
| CIP-7 | Retention Contracts (链下存储 SLA) | 未实现 |
| CIP-21 | DEX & Liquidity Pools | 未实现 |
| CIP-22 | Continuous Clearing Auctions | 未实现 |

---

## 修复实施计划

### Phase A：P0 共识关键常量修复

**文件**：`/node/execution/src/gas.rs`, `/node/execution/src/pvm_host.rs`

**gas.rs 改动**：
```rust
// 1. secp256k1: 10_000 → 3_000
crypto_secp256k1_verify_cycles: 3_000,
pub const CRYPTO_SECP256K1_VERIFY_CYCLES: u64 = 3_000;

// 2. keccak256: 去掉 base，改为 6/32bytes
// 删除 crypto_keccak256_base_cycles 字段（或设为 0）
// 删除 crypto_keccak256_per_block_cycles 字段
// 新增：
pub const CRYPTO_KECCAK256_PER_32BYTES_CYCLES: u64 = 6;
pub fn keccak256_cycles(input_len: usize) -> u64 {
    ((input_len as u64 + 31) / 32) * CRYPTO_KECCAK256_PER_32BYTES_CYCLES
}

// 3. BLS 新增
pub crypto_bls_verify_cycles: u64,  // = 8_000
pub const CRYPTO_BLS_VERIFY_CYCLES: u64 = 8_000;
```

**pvm_host.rs 中 keccak256 充值逻辑（两处）**：
- `line ~926-927`：改用新公式
- `line ~1029-1031`：改用新公式

**测试**：更新 `gas.rs:tests` 中的 `test_gas_constants_match_cip_spec` 断言。

---

### Phase B：P1 公式修正

**文件**：`/node/execution/src/gas.rs`, `/node/execution/src/pvm_host.rs`

1. **SHA256 公式**（gas.rs + 未来 pvm_host.rs 接入时）：
   ```rust
   crypto_sha256_base_cycles: 100,       // WP §17.3 hash() base
   crypto_sha256_per_byte_cycles: 1,     // 改为 per-byte（原 per-64-byte-block）
   ```

2. **Serialization 公式**（gas.rs）：
   ```rust
   serialization_base_cycles: 20,        // CIP-3: 20
   serialization_per_byte_cycles: 1,     // CIP-3: 1/byte
   ```

3. **emit_event 修复**（pvm_host.rs line 724）：
   ```rust
   // 补充 cycles 充值
   let cycle_cost = 500u64 + (topic.len() as u64 + data.len() as u64) * 5;
   self.ctx.gas_meters.cycles.consume_tracked(cycle_cost, "emit_event", GasCategory::Messaging)?;
   // 修正 cells
   let cell_cost = (topic.len() as u64 + data.len() as u64 + 1) / 2;
   self.ctx.gas_meters.cells.consume_tracked(cell_cost, "emit_event", GasCategory::Messaging)?;
   ```

4. **token_create_cells 改为动态**（pvm_host.rs 中 token_create 实现）：
   基础 256 cells + name.len + symbol.len

---

### Phase C：P2 缺失功能

1. **get_block_info host function**：在 pvm_host.rs 新增 `get_block_info()` 实现，充值 100 cycles。

2. **Proposer tip 路由**（已有 TODO）：
   - `storage/src/process_block.rs` — 将 `tip` 路由到 block proposer 地址而非 Address::ZERO
   - 需要验证者注册表中的 `tip_address` 字段

3. **Block Cycles 上限常量声明**（basefee.rs）：
   ```rust
   pub const BLOCK_CYCLES_CAP: u64 = 20_000_000;  // WP §17.8
   pub const BLOCK_CELLS_CAP: u64  = 1_000_000;   // WP §17.8
   ```

---

## 关键文件路径

| 文件 | 作用 |
|------|------|
| `/node/execution/src/gas.rs` | 所有 gas 常量定义 + 计算函数 |
| `/node/execution/src/pvm_host.rs` | Host API 实现（keccak256, emit_event 等） |
| `/node/execution/src/basefee.rs` | Basefee 常量与更新逻辑 |
| `/node/execution/src/execution/transaction.rs` | 交易级费用计算 |
| `/node/storage/src/process_block.rs` | 区块级费用最终化 + tip 路由 |
| `/refs/cips/cip-3-fee-model.mdx` | 权威 Actor API 成本规格 |
| `/refs/202603/2026-03-21_cowboy-technical-whitepaper-revised.md` | WP §17（总权威） |

---

## 验证方法

1. **单元测试**：
   ```bash
   cd /home/ubuntu/workspace/node/execution
   cargo test gas::tests -- --nocapture
   cargo test basefee::tests -- --nocapture
   ```

2. **新增 SPEC 测试**（每项修复对应一个断言）：
   - `SPEC-GAS-SECP: assert_eq!(CRYPTO_SECP256K1_VERIFY_CYCLES, 3_000)`
   - `SPEC-GAS-KECCAK32: assert_eq!(keccak256_cycles(32), 6)`
   - `SPEC-GAS-KECCAK64: assert_eq!(keccak256_cycles(64), 12)`
   - `SPEC-GAS-BLS: assert_eq!(CRYPTO_BLS_VERIFY_CYCLES, 8_000)`
   - `SPEC-GAS-SER: assert_eq!(SERIALIZATION_BASE_CYCLES, 20)`

3. **集成测试**（修复完成后）：
   ```bash
   cd /node/examples/token && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
   cd /node/examples/multi_call && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test
   ```

---

## 注意事项

- **Phase A (P0) 优先**：secp256k1 和 keccak256 是共识关键值，必须率先修复
- keccak256 公式改动涉及 `pvm_host.rs` **两处调用点**，需同时修改（约 line 924 和 1027）
- sha256 的改动只需改 `gas.rs`（当前尚未在 pvm_host.rs 中实际调用，连接在后续 milestone）
- `serialization` 改动可能影响现有 test assertions，需逐一更新
- Phase C tip 路由是 TODO 功能，实现前需确认 validator tip_address 的来源
