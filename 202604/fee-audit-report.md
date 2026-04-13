# Node 收费项目全盘审计报告

> 审计日期: 2026-04-13
> 审计范围: node/ 代码库 vs CIP 规范 (CIP-1, CIP-2, CIP-3, CIP-5, CIP-9, CIP-10, CIP-20)

---

## 一、已实现的收费项目

### 1. EIP-1559 双基础费 (Basefee)

| 项目 | 实现值 | 文件 |
|------|--------|------|
| 初始 cycle basefee | 100,000 attoCBY | `types/src/constants.rs` |
| 初始 cell basefee | 100,000 attoCBY | `types/src/constants.rs` |
| MIN_BASEFEE | 10,000 | `types/src/constants.rs` |
| MAX_BASEFEE | 1e24 | `types/src/constants.rs` |
| BLOCK_CYCLES_TARGET | 20,000,000 | `types/src/constants.rs` |
| BLOCK_CELLS_TARGET | 4,000,000 | `types/src/constants.rs` |
| Basefee 烧毁 | 100% burn | `execution/src/basefee.rs` |
| Proposer 小费 | min(tip, max_fee - basefee) | `execution/src/basefee.rs` |

### 2. 交易基础开销

| 项目 | Cycles | Cells | 文件 |
|------|--------|-------|------|
| 交易固有成本 | 5,000 | 500 | `execution/src/gas.rs` |
| Calldata (每字节) | — | 1 | `execution/src/gas.rs` |
| Return data (每字节) | — | 1 | `execution/src/gas.rs` |

### 3. 账户操作

| 项目 | Cycles | Cells |
|------|--------|-------|
| 创建账户 | 12,000 | 2,000 |
| 转账 | 5,000 | 500 |
| 设置余额 | 10,000 | 1,000 |

### 4. Actor 操作

| 项目 | Cycles | Cells |
|------|--------|-------|
| 部署 (基础) | 50,000 | 10,000 |
| 部署 (每字节) | 100 | 200 |
| 消息发送 | 10,000 | 1,000 |
| 消息处理 | 10,000 | 1,000 |

### 5. 存储操作

| 项目 | Cycles | Cells |
|------|--------|-------|
| KV 读取 | 10 | 0 |
| KV 写入 | 200 | 1,000 |

### 6. Host 函数调用

| 项目 | Cycles | Cells | 来源 |
|------|--------|-------|------|
| Mailbox 发送 | 80 (base) | payload.len() | `gas.rs:272`, CIP-3 |
| Schedule Timer | 200 | payload bytes | `gas.rs:273`, CIP-5 |
| Cancel Timer | 200 | 0 | `gas.rs:274`, CIP-5 |

### 7. Runner 系统

| 项目 | Cycles | Cells |
|------|--------|-------|
| 注册 | 50,000 | 5,000 |
| 更新 RateCard | 20,000 | 2,000 |
| 心跳 | 10,000 | 500 |
| 注销 | 20,000 | 1,000 |
| 提交任务 | 100,000 | 10,000 |
| 提交结果 | 50,000 | 5,000 |
| 结果确认 | 20,000 | 2,000 |
| 取消任务 | 20,000 | 1,000 |

Runner 经济惩罚:
- **罚没 (slashing)**: 50% treasury / 50% burn (`execution/src/runner/verifier.rs`)
- **超时惩罚**: reputation -5 (`execution/src/runner/dispatcher.rs`)
- **最低质押**: 10,000 CBY，动态要求 stake >= max_job_value × 1.5

### 8. CIP-20 Token 操作

| 项目 | Cycles | Cells |
|------|--------|-------|
| 创建 | 10,000 | 5,000 |
| 转账 | 1,000 | 64 |
| 授权转账 | 1,500 | 96 |
| 授权 (approve) | 500 | 32 |
| 铸造 | 1,000 | 64 |
| 销毁 | 500 | 64 |
| 管理操作 | 2,000 | 100 |
| 批量转账 (base) | 500 | — |
| 批量转账 (每笔) | 500 | — |
| Hook 执行上限 | 50,000 | — |

### 9. 密码学操作

| 项目 | Cycles |
|------|--------|
| SHA256 (base) | 500 |
| SHA256 (每64B block) | 8 |
| Keccak256 (每32B) | 6 |
| Ed25519 验证 | 5,000 |
| secp256k1 验证 | 10,000 |
| HKDF | 1,000 |

### 10. 内存 & 序列化

| 项目 | Cycles | Cells |
|------|--------|-------|
| 内存页分配 (64KB) | 100 | 1,000 |
| 大内存分配 (>4KB, 每字节) | — | 1 |
| 序列化 (base) | 20 | — |
| 序列化 (每字节) | 1 | — |
| 反序列化 (base) | 20 | — |
| 反序列化 (每字节) | 1 | — |

### 11. Entitlement 操作

| 项目 | Cycles | Cells |
|------|--------|-------|
| 授权 (grant) | 5,000 | 500 |
| 撤销 (revoke) | 2,000 | 100 |
| 委派 (delegate) | 5,000 | 300 |
| 检查 (check) | 500 | 50 |
| 角色操作 (role) | 10,000 | 1,000 |

### 12. 反垃圾机制

| 项目 | 值 | 说明 |
|------|-----|------|
| 失败交易垃圾惩罚 | 5,000 cycles | 预执行失败也计入 block cycles_used，推高 basefee |
| Gas Lane 限额 | User/Runner/Timer/System 分道 | 防止单类交易占满区块 |

### 13. 费用支付来源 (三方分摊)

执行顺序:
1. **Actor 自身余额** — 优先从 actor 余额扣除
2. **Actor 所有者余额** — 通过 UseOwnerBalance entitlement，从 owner 余额扣除剩余部分
3. **交易发送者余额** — 最后兜底，始终支付最终剩余

失败交易费用全部由发送者承担。系统触发的 timer 交易免费。

---

## 二、CIP/白皮书设计了但未实际收取的项目

### 1. Token 只读查询费 (CIP-20)

CIP-20 规定了以下只读查询操作的 Gas 费用，但代码中 `GasCosts` 没有对应字段，`pvm_host.rs` 中这些函数直接返回结果，未收费:

| 项目 | CIP-20 设计值 | 实际 |
|------|--------------|------|
| `token_allowance()` | 100 cycles / 0 cells | **未收** |
| `token_balance_of()` | 100 cycles / 0 cells | **未收** |
| `token_total_supply()` | 100 cycles / 0 cells | **未收** |
| `token_info()` | 200 cycles / 0 cells | **未收** |

### 2. Python 字节码逐指令计费 (CIP-3 S2.2.1)

CIP-3 设计了 PVM 字节码级别的精细计费:

| 项目 | CIP-3 设计值 | 实际 |
|------|-------------|------|
| 算术操作 (+, -, *, /, %) | 1 cycle/instruction | **未逐指令收取**，用 max_cycles 上限代替 |
| 函数调用 | 10 cycles/call | **未逐指令收取** |
| 字典 Get/Set | 3 cycles/op | **未逐指令收取** |
| 列表 Append/Access | 2 cycles/op | **未逐指令收取** |
| 字符串操作 (每字符) | 1 cycle/char | **未逐指令收取** |

> 当前实现使用 `max_cycles` 作为硬上限 (在 `pvm_executor.rs` 中)，PVM 内部按指令计数但不做逐操作的差异化计费。

### 3. 模块导入费 (CIP-3 S2.2.3)

| 项目 | CIP-3 设计值 | 实际 |
|------|-------------|------|
| 首次导入模块 | 100 cycles + 初始化开销 | **未实现** |
| 重复导入 (同 tx) | 5 cycles | **未实现** |
| 导入失败 (非白名单) | 50 cycles 惩罚 | **未实现** |

### 4. 大整数操作差异化计费 (CIP-3 S2.2.4.9)

| 项目 | CIP-3 设计值 | 实际 |
|------|-------------|------|
| 大整数运算 | base + max(bitlen(a), bitlen(b))/64 | **未实现**，只有静态的 `INT_GUARD_PREAMBLE` 限制 4096 位上限 |

### 5. 字符串编解码费 (CIP-3 S2.2.4.10)

| 项目 | CIP-3 设计值 | 实际 |
|------|-------------|------|
| UTF-8 encode/decode | 10 + len(input) cycles | **未实现** |

### 6. Blob/临时存储费 (CIP-3 S2.2.2)

| 项目 | CIP-3 设计值 | 实际 |
|------|-------------|------|
| `commit_blob()` (每 KiB) | 40 cycles | **未实现** (host API 不存在) |
| `/tmp` 临时空间写入 | data.len() cells | **未实现** (host API 不存在) |

### 7. 存储 Cell 精确计量 (CIP-3 S2.2.2)

| 项目 | CIP-3 设计值 | 实际 |
|------|-------------|------|
| `storage_set` cells | key.len() + value.len() | **未按实际大小收**，固定 1,000 cells/次 |

### 8. BLS 签名验证费 (CIP-3 S2.2.1)

| 项目 | CIP-3 设计值 | 实际 |
|------|-------------|------|
| BLS 签名验证 | 8,000 cycles | 测试常量存在，但 `GasCosts` 中**无对应字段** |

### 9. CIP-9 Runner 存储系统 (完全未实现)

| 项目 | CIP-9 设计值 | 实际 |
|------|-------------|------|
| Volume 创建 | 1,000 CBY + 5,000C/500b | **整个 Volume 系统未实现** |
| Volume 授权访问 | 3,000C / 150b | **未实现** |
| Volume 撤销访问 | 1,000C / 50b | **未实现** |
| Volume 锚定 Manifest | 1,000C / 32b | **未实现** |
| 存储费 (每 epoch/字节) | TBD CBY | **未实现** |
| Base Attachment Fee | 100 CBY/volume/job | **未实现** |
| Relay Node 最低质押 | TBD CBY | **未实现** |
| 存储费燃烧率 | 10% | **未实现** |

### 10. CIP-10 Runner 容器系统 (完全未实现)

| 项目 | CIP-10 设计值 | 实际 |
|------|-------------|------|
| CPU 计费 | millicores x seconds x rate | **未实现** |
| 内存计费 | MiB x seconds | **未实现** |
| GPU 计费 | TBD | **未实现** |
| 外部镜像拉取 | EGRESS_FEE_PER_BYTE | **未实现** |
| ContainerImageRegister | 10,000C / 200b | **未实现** |

### 11. 浮点数确定性计费 (CIP-3)

| 项目 | CIP-3 设计值 | 实际 |
|------|-------------|------|
| 确定性软件浮点运算 | 额外 cycles (vs 原生) | **未实现**，仅在 `pvm_executor.rs` 中做了浮点限制 |

### 12. Gas Lane 目标值偏差

| 项目 | CIP-3 设计值 | 实际实现值 | 倍数 |
|------|-------------|-----------|------|
| Block Cells Target | 500,000 | 4,000,000 | 8x |
| Block Cycles Target | 10,000,000 | 20,000,000 | 2x |
| 用户 Lane | 50% (5M) | 22,222,222 | ~4.4x |
| Runner Lane | 25% (2.5M) | 8,888,888 | ~3.6x |
| Timer Lane | 20% (2M) | 8,888,890 | ~4.4x |
| System Lane | 5% (500K) | 40,000,000 | 80x |

---

## 三、未实现项难点分析

### 3.1 Python 字节码逐指令差异化计费 (CIP-3 S2.2.1)

#### 当前现状

PVM 的 cycle 消耗采用**粗粒度、边界检查**模式：Python 字节码自由执行，仅当碰到 host 调用 (storage_get, send_message 等) 时才检查 gas。`frame.rs` 核心执行循环内没有任何计量 hook，Python 代码在两次 host 调用之间是"免费"运行的。`DeterminismOptions` 中 `enable_gas: bool` 字段已存在且设为 `true`，但从未接入实际逻辑。

#### 难点 1：性能开销 — 最大障碍

Python 字节码指令极轻量（一次加法 ~几纳秒），若在每条指令前插入计费：

```rust
// frame.rs 循环内，每条指令前
let cost = get_opcode_gas_cost(&op, arg);
host.charge_gas(cost)?;  // 跨越 VM→Host 边界
```

涉及：opcode→cost 查表、`used += cost` 累加 + `used > limit` 判断、trait dynamic dispatch 开销。字节码执行频率极高（一个简单 handler 可能跑几万条指令），per-instruction overhead 可能将 PVM 吞吐量降低 2-5x。

#### 难点 2：Opcode 成本表的正确性和完备性

RustPython 的 `bytecode::Instruction` 枚举有 100+ 种 opcode，同一 opcode 在不同类型上的实际复杂度差异巨大：

- `BinaryOp::Add` 作用于 int vs string vs list，实际开销差 10-100 倍
- `CallFunction` 调用内置 `len()` vs 用户定义函数，完全不同的执行路径
- `BuildList { size: 10000 }` 的 cost 依赖于参数 arg
- CIP-3 设计的"算术=1, 函数调用=10, 字典=3"是静态平均值，真正公平需要 runtime 类型感知计费

#### 难点 3：与现有 Host 计费的双重计费风险

当前 storage read/write、crypto 等费用在 host 函数入口收取。如果字节码层面再加 per-instruction 计费，一次 `storage_get()` 在字节码层面是 `CALL_FUNCTION` 收 10 cycles，同时 host 层面又收 `storage_read_cycles = 10`，需要仔细协调避免双重收费。

#### 难点 4：确定性保证

PVM 要求所有 validator 对同一交易消耗完全相同的 gas。per-instruction 计费本身是确定性的（同样的字节码 + 同样的输入 = 同样的指令序列），但 RustPython 版本升级可能改变内部实现（同一 Python 语句编译出不同字节码），增加了升级的脆弱性。

#### 难点 5：OutOfGas 中断的正确回滚

当前只在 host 边界检查，中断点都是安全的。若在任意指令间中断，需确保 VM 栈状态一致、gas exhaustion 异常能正确传播。`vm.check_signals()` 机制 (`frame.rs:659`) 理论上可行，但需验证所有 opcode handler 都能安全 bail out。

#### 可行工程方案

最务实的路径是 **VM 内部本地计数器 + 周期性同步**：

```rust
// frame.rs 循环内
loop {
    let op = instructions[idx];
    self.local_gas_used += OPCODE_COST_TABLE[op as usize];  // 纯本地，无跨边界
    if self.local_gas_used >= SYNC_THRESHOLD {               // 每 ~1000 cycles 同步一次
        vm.charge_gas(self.local_gas_used)?;                 // 此时才跨 host 边界
        self.local_gas_used = 0;
    }
    self.execute_instruction(op, arg, vm);
}
```

性能开销从"每条指令一次 host 调用"降到"每千 cycles 一次 host 调用"，精度损失可控（最多超用 ~1000 cycles 才检测到 out of gas）。

### 3.2 Token 只读查询费 (CIP-20)

#### 当前现状

`token_balance_of()`、`token_allowance()`、`token_total_supply()` 三个函数已在 `pvm_host.rs:1167-1211` 实现，但**完全不收 gas**。它们从预加载的 `token_state_cache`（独立于 actor 主存储的内存缓存）直接读取，不触发 `read_count` 递增，因此也不会产生间接的 `STORAGE_READ_CYCLES` 费用。`token_info()` 函数在代码中**完全不存在**。

#### 难度：低

- 只需在 `GasCosts` 中增加 4 个字段（`token_balance_of_cycles`、`token_allowance_cycles`、`token_total_supply_cycles`、`token_info_cycles`）
- 在 `pvm_host.rs` 对应函数入口处调用 `consume_tracked()` 即可
- `token_info()` 需要额外实现一个查询函数（读取 token 元数据：name、symbol、decimals、authority 等）
- **无架构风险**，纯粹是补充收费点

### 3.3 模块导入费 (CIP-3 S2.2.3)

#### 当前现状

Python `import` 走标准 RustPython 导入机制（`pvm/crates/vm/src/import.rs`），对 stdlib 和自定义模块（cbor2、pvm_host、cowboy_sdk）一视同仁。**无任何 gas 追踪**。预导入模块在解释器初始化时加载，也不计费。

#### 难点

1. **Hook 注入点不明确** — import 发生在 VM 内部的 `IMPORT_NAME` / `IMPORT_FROM` 字节码中，要计费需要在 RustPython 的 `import.rs` 中插入 host 回调，这意味着修改 VM 内核代码
2. **首次 vs 重复导入的区分** — CIP-3 设计首次 100 cycles、重复 5 cycles，需要 per-transaction 的模块导入缓存来跟踪"是否已导入过"
3. **与逐指令计费的重叠** — 如果未来实现了 per-instruction 计费，`IMPORT_NAME` 字节码本身已经会被收费。模块导入费是"额外"收取还是替代 instruction cost，需要设计决策
4. **白名单外导入的惩罚** — 当前非白名单模块导入直接 raise `ImportError`，要加 50 cycles 惩罚需要在 error 路径上也触发 gas 扣减

#### 难度：中

核心是对 RustPython import 机制的侵入式修改，以及 per-tx import 缓存的维护。

### 3.4 大整数差异化计费 (CIP-3 S2.2.4.9)

#### 当前现状

两层保护（`pvm_executor.rs`）：
1. **编译时验证**：`validate_actor_code()` 检查源码中 >1234 位的十进制整数字面量
2. **运行时守卫**：`INT_GUARD_PREAMBLE` 注入 `_GuardedInt` 类，在 `__add__`、`__mul__`、`__pow__`、`__lshift__` 等操作中检查是否超过 4096 位，超过则抛 `OverflowError`

当前模式是**硬拒绝**（超过就 panic），而非**按复杂度收费**。

#### 难点

1. **需要在 Python 层面拦截所有算术路径** — `_GuardedInt` 机制已经证明了这种 monkey-patching 方式的局限：原生 int 字面量绕过守卫（`2**10000` 在 bytecode 层面直接计算）。要可靠地按 bitlen 计费，需要在 VM 的 `PyInt` 运算实现中直接注入
2. **性能影响** — 每次 int 运算都要算 `bitlen(a)` 和 `bitlen(b)`，对高频小整数操作（循环计数器、索引等）造成不必要的开销
3. **与逐指令计费的关系** — 如果实现了 per-instruction 差异化计费，大整数操作的额外 cost 应该叠加在 `BinaryOp` 的 base cost 上，需要在两套系统间协调
4. **当前硬拒绝已够用** — 4096 位上限加 OverflowError 已经有效防止了 bigint DoS。差异化计费的增量安全收益有限

#### 难度：高

需要深入修改 RustPython 的 `PyInt` 类型实现，在每次算术运算中注入 bitlen 计算和 gas 扣减。收益不大，因为硬上限已足够防 DoS。

### 3.5 字符串编解码费 (CIP-3 S2.2.4.10)

#### 当前现状

字符串的 encode/decode 使用 Python 标准库内置行为（`str.encode()`、`bytes.decode()`），在 RustPython 的 `PyStr` / `PyBytes` 类型方法中实现。**不是 host 函数**，因此不经过 gas 计量。

#### 难点

1. **拦截点在 VM 内核** — `str.encode()` 和 `bytes.decode()` 是 RustPython 内置类型方法，不经过 host boundary。要计费需要在 `PyStr::encode()` 和 `PyBytes::decode()` 的 Rust 实现中注入 gas 回调
2. **与逐指令计费重叠** — 如果有了 per-instruction 计费，`CALL_METHOD` 指令已经会收取 base cost，额外的 per-byte 费需要通过 VM→host 回调叠加
3. **需要确定计费粒度** — CIP-3 设计 `10 + len(input)` cycles，但实际 UTF-8 encoding 复杂度与字符组成有关（ASCII vs multi-byte），固定 per-byte 可能不公平也可能过度收费

#### 难度：中

与模块导入费类似，核心是对 VM 内置类型方法的侵入式修改。

### 3.6 Blob/临时存储费 (CIP-3 S2.2.2)

#### 当前现状

`commit_blob()`、`put_blob()`、`/tmp` 临时空间相关 API 在整个代码库中**完全不存在**。Host API trait（`pvm-host/src/lib.rs`）中没有这些方法，actor 代码无法调用。

#### 难点

1. **需要设计全新的存储层** — Blob 存储语义与 KV 存储（`state_get`/`state_set`）不同：blob 是不可变的（commit 后不可修改），需要 content-addressing（按 hash 索引）
2. **`/tmp` 临时空间的生命周期管理** — 需要定义：临时数据在 tx 间是否持久？actor 间是否隔离？block 结束后是否自动清理？
3. **与 CIP-9 Volume 系统的边界** — CIP-9 设计了完整的持久化存储系统（Volume），blob/tmp 的定位需要与 Volume 系统明确区分
4. **底层 QMDB 支持** — 当前 `BlockchainStorage` 只支持 account→actor→KV 的树结构，blob 存储需要新的存储路径

#### 难度：高

不仅仅是"加计费"的问题，而是**整个 host API 和存储层都需要从头设计和实现**。

### 3.7 存储 Cell 精确计量 (CIP-3 S2.2.2)

#### 当前现状

`state_set()` 的 cell 收费已经**部分实现了按大小计费**：在 `pvm_host.rs:689-701` 中，cell cost = `key.len() + value.len()`（实际代码按字节数收取）。但 `GasCosts` 中 `storage_write_cells` 的默认值是固定的 1,000，用于非 host 路径（系统指令等）的存储写入。

#### 实际差距

经核实，**host 路径的 `state_set()` 已按 `key.len() + value.len()` 收取 cells**。真正的差距在于：
- 系统指令路径（`system_instruction.rs`、`runner/*.rs`）中的存储写入仍使用固定 `storage_write_cells = 1,000`
- 不同场景下写入的数据大小差异很大（runner 注册信息 vs 简单转账），但一律收 1,000 cells

#### 难度：低

系统指令路径中改为按实际序列化大小收取即可，技术上简单，但需要逐一审计每个系统指令的存储写入点。

### 3.8 BLS 签名验证费 (CIP-3 S2.2.1)

#### 当前现状

`gas.rs:272` 定义了常量 `CRYPTO_BLS_VERIFY_CYCLES = 8_000`，但：
- Host API trait 中**没有 `bls_verify()` 方法**
- PVM runtime 模块中没有暴露 BLS 验证函数
- Actor 代码无法调用 BLS 验证

#### 难度：中

需要：
1. 引入 BLS 密码学库（如 `blst`）
2. 在 `HostApi` trait 中添加 `bls_verify()` 方法
3. 在 `CowboyHost` 中实现并接入 gas 计费
4. 在 `pvm_host_module` 中暴露给 Python
5. 确保 BLS 实现的确定性（不同平台产生相同结果）

核心风险是 BLS 库的确定性保证和跨平台一致性。

### 3.9 CIP-9 Volume 存储系统 (完全未实现)

#### 当前现状

整个 Volume 系统在代码库中**零基础**：无系统 actor、无 system instruction opcode、无存储 key schema、无类型定义。

#### 需要构建的组件

1. **Storage Manager 系统 Actor (新 actor 地址)** — Volume 生命周期（创建、删除、转让）、StorageCommitment 记录管理、CapToken 签发/撤销/验证、存储托管管理
2. **Relay Registry 系统 Actor** — Relay Node 注册/心跳/健康衰减、分片放置记录、PoR 挑战跟踪、修复协调
3. **9 个新 System Instruction** — VolumeCreate (40)、VolumeGrantAccess (41)、VolumeRevokeAccess (42)、VolumeAnchorManifest (43)、VolumeDelete、VolumeTransferOwnership 等
4. **完整存储 Key Schema** — volume 元数据、CapToken 注册表、Relay Node 注册表、分片放置、撤销列表、存储托管余额
5. **链上计费基础设施** — per-epoch 存储费计量（独立于 Cycles/Cells）、托管锁定机制、attestation 结算

#### 难度：极高

- 预估 ~2000-2500 行核心代码 + ~1500 行测试
- 涉及 2 个全新系统 actor、6+ 个新指令、完整的链上状态机
- 链下数据平面（Steamtrain）是外部依赖，但链上控制平面的合约接口设计复杂
- **关键设计风险**：CapToken 前缀安全（三层防护中第二层依赖链下协调者）、Manifest 验证环路、托管账户不足时的服务中断策略

### 3.10 CIP-10 Runner 容器系统 (完全未实现)

#### 当前现状

与 CIP-9 同样**零基础**。

#### 需要构建的组件

1. **Container Registry 系统 Actor** — 基础镜像元数据存储、资源等级定义（small/medium/large/gpu-small/gpu-large）、镜像策略管理
2. **RuntimeConfig 类型扩展** — CIP-2 的 OffchainTask 需扩展 `volume_attachments`（CIP-9）和 `runtime_config`（镜像引用、资源限制、网络策略、环境变量）
3. **资源计费基础设施** — per-task 计算成本、BillingAttestation 验证（TEE 签名或争议）、争议窗口跟踪与解决、GPU 计费
4. **Runner 能力预过滤** — Runner Registry 需建立能力索引（GPU 型号、架构、内存层级、缓存镜像），VRF 选择需使用过滤后列表

#### 难度：极高

- 预估 ~1200-1500 行核心代码 + ~1000 行测试
- 与 CIP-9 深度耦合（Volume 挂载 + CapToken 分发 + DEK 加密传递）
- Job Dispatcher 需大幅扩展以支持容器任务的解析、能力过滤、组合托管
- **关键设计风险**：非 TEE runner 的计费自报告机制（争议解决回退到 max_cost）、GPU 供给稀缺时的 VRF 候选池问题

---

## 四、总结

| 类别 | 状态 |
|------|------|
| **已完整实现** | 双 Basefee (EIP-1559)、交易基础费、账户/Actor/存储/Runner/Token/Entitlement 的 Gas 计费、密码学操作、内存分配、序列化、反垃圾机制、Runner 罚没、Timer/Deferred 执行 |
| **设计了但未收** | Token 只读查询费、PVM 逐字节码指令差异化计费、模块导入费、大整数差异化计费、字符串编解码费、Blob/临时存储、存储 Cell 按实际大小计量、BLS 验证费字段 |
| **整个子系统未实现** | CIP-9 Volume 存储系统、CIP-10 容器计费系统 |
| **参数偏离设计** | Block Cycles/Cells Target 和各 Lane 容量均显著大于 CIP-3 规范值 |
