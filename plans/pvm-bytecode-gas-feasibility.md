# 评估：实施 fee-audit-report.md 3.1 章节的可行性、波及面与风险

## Context

CIP-3 §2.2.1 设计了 PVM 逐字节码指令差异化 gas 计费（算术=1 cycle、函数调用=10 cycles、字典 Get/Set=3 cycles、mailbox send=80 cycles 等）。当前 PVM 使用**粗粒度边界检查**模式：字节码自由执行，仅在 host 调用时收费，`max_cycles` 作为硬上限兜底。`DeterminismOptions.enable_gas` 字段虽已定义（`pvm/crates/pvm-runtime/src/determinism.rs:9`），但**从未接入 Frame 执行循环**（与 `max_int_bits` 同为已知 TODO，见 determinism.rs:13-20 注释）。

本文评估 3.1 章节的实施可行性、改动波及面、独立性，以及会牵扯出的新问题。**不是实施计划**，目的是为后续决策提供依据。

---

## 一、可行性评估：技术上可行，中等难度

### 已具备的基础设施

| 能力 | 位置 | 说明 |
|------|------|------|
| 明确的 hook 点 | `pvm/crates/vm/src/frame.rs:439` | `Frame::run()` 循环中 `execute_instruction()` 调用处 |
| host 调用通道 | `pvm/crates/pvm-runtime/src/host.rs:43` `with_host()` | thread-local Cell，无锁，~10-20ns 开销 |
| `charge_gas()` Python 绑定 | `pvm/crates/pvm-runtime/src/module.rs:69` | 已实现，可被 Rust 侧直接复用 |
| Frame 栈自动隔离 | `vm/mod.rs:69` `frames: RefCell<Vec<FrameRef>>` | 函数调用进入新 Frame，递归天然支持 |
| Opcode 数量可控 | `pvm/crates/compiler-core/src/bytecode.rs` | 128 个指令变体，可维护的成本表 |
| 确定性保证 | `DeterminismOptions` 白名单/黑名单、`PYTHONHASHSEED=0`、softfloat | 无浮点/随机/时间依赖，per-instr 计数天然确定 |

### 核心工程任务

1. **成本表模块**（新增 ~300-500 行）：`OPCODE_COST: [u64; 128]` 或 match 表达式，按 opcode 索引返回 base cost
2. **Frame 循环 hook**（修改 ~20 行）：在 `frame.rs:439` 后插入 gas 累加与溢出检查
3. **Frame 结构扩展**（修改 ~10 行）：`FrameState` 增加 `gas_used: u64` 或改为传入外部计数器
4. **激活 `enable_gas`**：在 `pvm_executor.rs` 的 `DeterminismOptions` 构造中设为 true 并接入到 Frame

**核心代码量估计**：~200-300 行新增/修改（不含成本表标定和测试）

---

## 二、修改波及面

### 2.1 代码改动（内核层）

| 文件 | 改动 | 复杂度 |
|------|------|--------|
| `pvm/crates/vm/src/frame.rs` | Frame::run() 循环注入 hook；FrameState 增加字段 | 低 |
| `pvm/crates/pvm-runtime/src/determinism.rs` | enable_gas 激活链路 | 低 |
| `pvm/crates/pvm-runtime/src/module.rs` | 可能需新增 opcode cost 查询 | 低 |
| `pvm/crates/compiler-core/src/bytecode.rs` | 新增 opcode cost 表（或独立模块） | 中 |
| `execution/src/pvm_executor.rs` | DeterminismOptions 构造中传 enable_gas: true | 低 |

### 2.2 参数重新标定（经济层）— **波及面最广**

这是比代码改动更大的工作量。Per-instruction gas 引入后，所有相对于"总 cycles"校准过的参数都要重新测量：

| 常量 | 位置 | 当前值 | 风险等级 |
|------|------|--------|---------|
| `BLOCK_CYCLES_TARGET` | `types/src/constants.rs:46` | 20M | 🔴 EIP-1559 basefee 调节敏感性变化，影响整个手续费市场 |
| `LANE_USER/RUNNER/TIMER/SYSTEM_CYCLES` | `types/src/constants.rs` | 22M/8.9M/8.9M/40M | 🔴 Lane 容量需重新设定，否则用户 tx 频繁 OOG |
| `TIMER_CYCLES_LIMIT` | `types/src/constants.rs:148` | 550,000 | 🟡 timer handler 若超支会中断定时任务 |
| `DEFERRED_CYCLES_LIMIT` | `types/src/constants.rs:162` | 100,000 | 🟡 原本可执行的 deferred tx 可能全部失败 |
| `token_hook_max_cycles` | `execution/src/gas.rs` | 50,000 | 🟡 token transfer hook 的 50k 预算可能容纳不下 |
| `BASE_CYCLES_SPAM_PENALTY` | `types/src/constants.rs` | 5,000 | 🟢 有自动一致性测试保护（gas.rs:668-672） |

### 2.3 测试影响

- 精确值断言：`execution/src/execution/tests.rs` 约 **6 处** `assert_eq!(cycles, N)` 型断言需更新
- 范围断言：10+ 处 `assert!(cycles > N)` 大多容错强，只需调整上下界
- Benchmark 基线：`pvm/benches/` **目前零 cycle 基线**，需从头建立 per-tx cycle 分布曲线

### 2.4 Receipt / 共识层（🔴 最高风险）

`storage/src/types.rs:681-682` 确认：`cycles_used` 通过 RLP 编码进入 `TransactionReceipt`：

```rust
rlp::encode_u64(self.cycles_used),
rlp::encode_u64(self.cells_used),
```

→ 进入 `receipt_root` → 进入 `block_digest` → **共识敏感字段**

**这意味着**：任何两个 validator 对同一 tx 计算出的 cycles_used 必须**逐位相同**。per-instruction 计费一旦实施，opcode 成本表就成为**协议参数**。

---

## 三、独立性评估：**不独立**，会牵扯整个 gas 经济

### 3.1 技术独立性（低）

这项修改本身的代码改动是局部的（PVM 内核 + pvm_executor），但**副作用辐射整个链**：

- 相同 actor 代码，执行前后 `cycles_used` 会**系统性改变**（通常是数倍增加）
- 所有已校准的预算（token hook 50k、timer 550k、deferred 100k、block target 20M）都需要重测
- EIP-1559 basefee 调节算法依赖 `cycles_used / target` 比率，target 调整不当会导致 basefee 失控

### 3.2 生态独立性（低）

- **链下 Runner 计费**（CIP-2）：Runner 的 job 成本估算如果基于 gas 预估，也会受影响
- **Actor 开发者体验**：现有 actor 代码在升级后可能突然 OutOfGas，需要广播迁移指南
- **钱包/UI 估费**：RPC `estimate_gas` 返回值口径变化，前端需联动更新

### 3.3 时序依赖

不能作为普通功能 PR 合入，**必须是 hard fork**：
- 成本表在 genesis 或 hard fork 块之后生效
- 旧 validator 重放历史块时仍需使用旧规则（没有 per-instr 计费）
- 需要区块高度 gating 逻辑

---

## 四、会牵扯出的新问题

### 4.1 双重计费的语义协调

Host 函数（如 `state_set`）在字节码层面是 `CALL_FUNCTION`：
- 字节码层面：`CALL_FUNCTION` = ~10 cycles（设计值）
- Host 层面：`state_set` 已收 200 cycles（base）+ `(key.len()+value.len())` cells

必须明确：两种 cost 是**叠加**还是**替换**？如果叠加，当前所有 host 操作的成本需要**向下调整**（扣除被重复收取的字节码部分）以保持总 cost 平衡。

### 4.2 Storage-read 批处理与 per-instr gas 的混合陷阱

`pvm_executor.rs:350-362` 当前将 `storage_read_cycles` 后验批量扣费：

```rust
// Success 路径执行完成后，才批量扣 reads * 10 cycles
if reads * 10 > remaining_budget { return OutOfGas }
```

引入 per-instr 计费后，执行期间已持续扣费。会出现新的语义陷阱：
- 执行看似完成返回 Success
- 后验批扣触发 OutOfGas
- 造成 Success → Fail 的非预期状态转换

需要**预先扣费**或**改为执行期间即时扣**。

### 4.3 RustPython 版本锁死

Python 编译器不同版本产生不同 bytecode 序列（如 3.11→3.12 引入 `PUSH_NULL`、去除 `PRECALL`）。同一 `a + b` 可能编译为不同指令序列 → 不同 cycles_used → **共识失败**。

后果：
- RustPython 升级必须走 hard fork 流程
- 当前的 `bytecode_cache`（存储编译后的 bytecode）必须与 RustPython 版本强绑定
- 任何 compiler optimization（常量折叠、peephole 优化）都成为协议变更

### 4.4 成本表的"公平性"永远无法完美

静态 opcode cost 无法区分：
- `BINARY_OP::Add` 作用于 `int` vs `str` vs `list`（后两者 O(n)）
- `CALL_FUNCTION` 调用 `len()` 内置 vs 用户函数（后者进入新 Frame）
- `BUILD_LIST(size=10000)` vs `BUILD_LIST(size=2)`（但后者的 arg 可用于加权）

**即使实施 per-instr 计费，也只是"更精细的近似"**，不能根本解决差异化问题。要做真正公平需要运行时类型感知计费，那是另一个量级的工程。

### 4.5 Checkpoint / Continuation 的序列化兼容

`frame.rs:486` 的 `maybe_checkpoint_request` 机制会序列化 Frame 状态到 continuation。引入 `gas_used` 字段后：
- Checkpoint 格式变更 → 向后兼容处理
- 跨区块恢复的 continuation 必须保留 gas 进度
- 否则 resume 时 gas 计算错乱

### 4.6 调试与可观测性退化

当前 OutOfGas 发生点集中在 host 函数边界，错误信息明确（"storage_write 超支"）。per-instr 计费后，OutOfGas 可能发生在任意字节码位置：
- 错误信息变模糊（"执行第 N 条 BINARY_OP 时 gas 耗尽"）
- Actor 开发者难以定位高成本热点
- 需要额外的 gas trace/profile 工具支持

### 4.7 Token Hook 50k 预算的兼容性

当前 `token_hook_max_cycles = 50,000` 按"host 操作 cost"校准。per-instr 引入后，token hook 的 Python 逻辑本身可能消耗数千 cycles，加上 host 调用的 ~1000-2000 cycles，可能**逼近或超过 50k**。需要：
- 重测所有示例 token hook 的 cycle 消耗
- 如果接近上限，可能需上调至 100k-200k
- 这又会影响 CIP-20 的 DoS 防护假设

---

## 五、总体判断

### 5.1 可行性：✅ 技术可行
所有前置条件（hook 点、host 通道、Frame 栈、确定性）都已具备。核心代码改动 <500 行。

### 5.2 独立性：❌ 不独立
属于**协议级变更**，牵扯整个 gas 经济、所有参数标定、共识规则、RustPython 版本管理。

### 5.3 主要风险
1. **共识确定性**（最高）：任何不确定性来源都会导致链分叉
2. **参数重标定**：6+ 个常量需要数据驱动地重新校准，需 testnet 长期运行
3. **RustPython 版本锁死**：升级路径被绑死到 hard fork
4. **双重计费协调**：host 操作成本需系统性重新设计

### 5.4 建议

**短期（不建议实施）**：
- 当前 `max_cycles` 硬上限 + host 函数边界计费的组合已经**有效防止 DoS**
- CIP-3 设计的精细计费的增量安全收益**有限**（主要是公平性而非安全性）
- 性能损耗（0.3%-3%）虽可接受，但标定和迁移成本高昂

**中期（若决定实施）**：
分三阶段：
1. **Phase 1 - 基础设施**：建立 benchmark 基线（pvm/benches 增加 cycle 断言）、编写确定性跨节点测试
2. **Phase 2 - 测试网实验**：激活 `enable_gas`，在 testnet 运行 2-4 周收集真实 cycle 分布
3. **Phase 3 - 硬分叉上线**：基于实测数据重新标定 6 个常量、发布 hard fork 规范、迁移指南

**必备前置项**：
- 共识确定性测试（两个独立 executor 对同一 tx 产出逐位相同 cycles_used）
- 成本表版本化（成本表哈希上链，不兼容变更需 hard fork）
- RustPython 版本锁死策略（bytecode_cache 与 compiler version 绑定）

---

## 关键文件引用

| 路径 | 作用 |
|------|------|
| `pvm/crates/vm/src/frame.rs:425-573` | Frame::run() 主循环，hook 注入点 |
| `pvm/crates/pvm-runtime/src/determinism.rs:9` | `enable_gas` 字段定义（当前未接入） |
| `pvm/crates/pvm-runtime/src/host.rs:43` | `with_host()` thread-local 访问 |
| `pvm/crates/pvm-runtime/src/module.rs:69-77` | `charge_gas()` / `gas_left()` Python 绑定 |
| `pvm/crates/compiler-core/src/bytecode.rs` | 128 个 opcode 定义（成本表基础） |
| `execution/src/pvm_executor.rs:173-382` | `execute_handler()`，`max_cycles` sub-limit 应用点 |
| `execution/src/gas.rs:668-672` | base_cycles vs SPAM_PENALTY 一致性测试 |
| `types/src/constants.rs:46,148,162` | 需重标定的块/timer/deferred 常量 |
| `storage/src/types.rs:681-682` | Receipt RLP 编码（共识敏感点） |
| `storage/src/merkle_utils.rs:29-37` | receipt_root 计算 |

## 验证方式（若决定实施）

1. **单元测试**：每个 opcode 的 cost 断言（`assert_eq!(exec_single_op(op), expected_cost)`）
2. **确定性测试**：同一 actor code 在两个 executor 实例中产出相同 cycles_used
3. **回归测试**：`cargo test --workspace` 全通过，所有 `assert!(cycles > N)` 断言调整后重新通过
4. **基准测试**：`cargo bench -p pvm` 记录前后对比，性能退化 < 5%
5. **端到端**：`examples/token`、`examples/multi_call`、`examples/llm_chat` 在新规则下全部可执行
6. **测试网**：2-4 周运行，收集 per-tx cycle 分布，验证 basefee 平稳
