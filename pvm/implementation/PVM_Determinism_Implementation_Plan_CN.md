# PVM 确定性实施清单（超详细版）

目标：在不大幅破坏现有 RustPython/PVM 结构的前提下，实现区块链可共识确定性的执行环境。开发者继续使用 `float`，系统内部使用 SoftFloat；stdlib 严格白名单；gas 采用 opcode 级低侵入模型。

本文提供：
- 明确定义的确定性边界与不变量
- 文件级、函数级改动清单
- SoftFloat、stdlib 白名单、gas 的具体实现步骤
- 错误处理、版本锁定、测试与验收标准

---

## 0. 术语与约定

- 确定性：同一 `code/input/host_state/host_context` 多次执行，输出、事件与状态必须一致。
- Host API：`crates/pvm-host/src/lib.rs` 中 `HostApi` 作为唯一外部输入通道。
- Runtime：`crates/pvm-runtime`，负责初始化 VM、注入 `pvm_host` 模块。
- VM：`crates/vm`，RustPython 内核。

---

## 1. 确定性不变量（必须满足）

### 1.1 允许影响结果的输入
只允许以下输入影响执行结果：
- 合约 `code`（字节序列）
- 交易 `input`（字节序列）
- Host 状态读写（`state_get/set/delete`）
- `HostContext`（区块高度、哈希、tx、sender、timestamp）
- `randomness(domain)`（链上确定性随机源，必须可验证）

### 1.2 禁止来源
以下来源必须不可见或不可影响结果：
- 系统时间、随机数、环境变量、文件系统、网络、进程/线程
- 不受控 `sys.path`、用户 site-packages
- 非确定性浮点、哈希、对象地址

### 1.3 输出不变量
执行结果必须满足：
- 输出 bytes、事件列表、状态写入序列一致
- checkpoint bytes 对同一输入严格一致
- out-of-gas 与异常路径的错误码一致

### 1.4 版本锁定不变量
必须在执行前检查：
- `pvm_version`、`chain_id`、`stdlib_hash` 一致
- 版本不一致直接拒绝执行

---

## 2. 架构现状与插入点

### 2.1 关键文件
- Host API: `crates/pvm-host/src/lib.rs`
- Runtime: `crates/pvm-runtime/src/lib.rs`, `crates/pvm-runtime/src/module.rs`
- VM 核心: `crates/vm/src/frame.rs`, `crates/vm/src/builtins/float.rs`
- Checkpoint: `crates/vm/src/vm/checkpoint.rs`, `crates/vm/src/vm/snapshot.rs`

### 2.2 现有确定性能力
- `ExecutionOptions.deterministic` 已存在但仅设置部分 `Settings`
- Checkpoint bytes + Canonical CBOR 已实现
- `pvm_host` 模块作为唯一链交互入口

### 2.3 仍缺失
- stdlib 白名单与 import guard
- SoftFloat 与 `hash(float)` 确定性
- opcode 级 gas 计量
- 版本锁定与一致性测试体系

---

## 3. Runtime 确定性 Profile（强制设置）

### 3.1 新增配置结构
文件：`crates/pvm-runtime/src/determinism.rs`
```rust
pub struct DeterminismOptions {
    pub enabled: bool,
    pub hash_seed: u32,
    pub stdlib_whitelist: Vec<String>,
    pub stdlib_blacklist: Vec<String>,
    pub stdlib_hash: String,
    pub enable_softfloat: bool,
    pub enable_gas: bool,
}
```

### 3.2 `ExecutionOptions` 扩展
文件：`crates/pvm-runtime/src/lib.rs`
- 添加字段：
```rust
pub struct ExecutionOptions {
    ...
    pub determinism: Option<DeterminismOptions>,
}
```
- 保留原 `deterministic: bool`，内部转换为 `DeterminismOptions` 以兼容旧调用。

### 3.3 Runtime 初始化步骤
文件：`crates/pvm-runtime/src/lib.rs`
- 当 `determinism.enabled = true` 时：
```rust
settings.hash_seed = Some(opts.hash_seed);
settings.ignore_environment = true;
settings.import_site = false;
settings.user_site_directory = false;
settings.isolated = true;
settings.safe_path = true;
settings.install_signal_handlers = false;
```
- 固定 `sys.path` 为受控路径，避免外部注入。
- 初始化顺序：
  1. install import guard
  2. install stdlib replacements
  3. install builtins guard
  4. install gas meter (if enabled)

### 3.4 Determinism 运行时 Hook
文件：`crates/pvm-runtime/src/guard.rs`
提供安装函数：
- `install_import_guard(vm, whitelist, blacklist)`
- `install_builtins_guard(vm)`：覆盖 `open`, `execfile`, `__import__` 入口
- `install_sys_guard(vm)`：隐藏 `sys.path`, `sys.modules` 中不安全字段

### 3.5 确定性错误类型与映射
新增错误类型（Python 侧）：
- `DeterministicValidationError`：非法模块/非法 IO/非法类型
- `OutOfGasError`：gas 耗尽
- `NonDeterministicError`：访问被禁 API

映射规则（Rust 侧）：
- `DeterministicValidationError` -> `HostError::InvalidInput`
- `OutOfGasError` -> `HostError::OutOfGas`
- `NonDeterministicError` -> `HostError::Forbidden`

实现落点：
- `crates/pvm-runtime/src/module.rs` 中新增异常类型或通过 `vm.ctx.new_exception_type`
- `crates/pvm-runtime/src/lib.rs` 的 `map_exception` 识别并映射

### 3.6 内置函数的确定性限制
必须限制或替换以下内置：
- `id()`：确定性模式直接抛 `NonDeterministicError`
- `hash()`：在 SoftFloat 下返回基于 bit 模式的稳定值
- `repr()`：对 `float` 与 `bytes` 使用固定格式

实现落点：
- `crates/pvm-runtime/src/guard.rs` 覆盖 `builtins.id`
- `crates/vm/src/builtins/hash.rs` 修改 `float` 哈希


---

## 4. stdlib 白名单与导入隔离

### 4.1 白名单（首版建议）
允许模块列表：
- 语言基础：`builtins`, `types`, `collections`, `collections.abc`, `enum`, `dataclasses`
- 语法辅助：`typing`, `functools`, `itertools`, `operator`, `re`, `string`
- 算术：`math`(softfloat 子集)
- 编码序列化：`json`, `base64`, `binascii`, `struct`(显式大小端), `hashlib`, `hmac`
- 数据结构：`heapq`, `bisect`

### 4.2 黑名单（首版建议）
禁止模块列表：
- 非确定性/系统：`time`, `datetime`, `random`, `secrets`, `uuid`, `os`, `sys`, `socket`, `ssl`
- 执行环境相关：`subprocess`, `ctypes`, `threading`, `multiprocessing`, `signal`, `select`, `asyncio`
- 文件/路径：`pathlib`, `glob`, `tempfile`, `shutil`, `zipfile`
- 调试/反射：`inspect`, `traceback`（避免泄漏路径/环境）

### 4.3 替代模块
新增文件：`Lib/pvm_sdk/pvm_time.py`
- `time.time()` -> `pvm_host.context().timestamp_ms / 1000.0`
- `time.time_ns()` -> `timestamp_ms * 1_000_000`

新增文件：`Lib/pvm_sdk/pvm_random.py`
- `random()` -> `pvm_host.randomness(domain=b"random")` 映射到 float
- `randbytes(n)` -> 扩展 `randomness` domain + counter

新增文件：`Lib/pvm_sdk/pvm_sys.py`
- 仅暴露 `chain_id`, `pvm_version`, `stdlib_hash`

### 4.3.1 pvm_random 实现细节
推荐策略：
- 以 `domain = b"random" + counter.to_le_bytes()` 生成随机块
- 将 32 字节输出转换为 SoftFloat：
  - 取高 53 位作为 mantissa
  - 指数固定为 0，映射到 [0,1)
  - 严格避免使用硬件 `f64`


### 4.4 Import Guard 实现
文件：`crates/pvm-runtime/src/guard.rs`
- 实现 Rust 层的 `MetaPathFinder`：
```python
class ImportGuard:
    def find_spec(fullname, path, target):
        if fullname in whitelist:
            return None
        raise ImportError("module not allowed")
```
- 安装到 `sys.meta_path` 的最前端。
- 对 `pvm_time/pvm_random/pvm_sys` 做显式映射。

### 4.5 禁止 `open` 与文件 IO
文件：`crates/pvm-runtime/src/guard.rs`
- 覆盖 `builtins.open`，抛 `DeterministicValidationError`
- `io.open` 映射到同样的禁止函数

### 4.6 白名单模块细化与约束
为了避免隐式 IO 与环境依赖，对部分白名单模块增加约束：
- `json`：仅允许 `json.loads/dumps`，禁止 file-like 参数
- `struct`：仅允许显式大小端格式（禁止 `@` 本地字节序）
- `hashlib`：禁止 `hashlib.pbkdf2_hmac` 中的随机 salt 生成
- `typing`/`inspect`：不允许读取源码路径（确定性模式禁止 `inspect`)

实现策略：
- 对允许模块的危险函数在 `pvm_runtime` 中打补丁
- 对禁止参数类型（file-like）进行运行时检查

### 4.7 stdlib_hash 计算方法
`stdlib_hash` 需要稳定可重现：
- 输入：白名单模块名列表 + 版本号 + 相关源码摘要
- 推荐算法：`sha256( sorted(modules) + version + per_file_hash )`
- file hash：对 `Lib/` 下对应模块源码按字节 hash


---

## 5. SoftFloat 透明替换（核心）

### 5.1 SoftFloat 类型选择
建议使用 `softfloat` 或自研 IEEE754 软件实现，保持以下 API：
```rust
pub struct SoftF64 { bits: u64 }
impl SoftF64 {
    pub fn from_bits(bits: u64) -> Self;
    pub fn to_bits(self) -> u64;
    pub fn add(self, rhs: Self) -> Self;
    pub fn sub(self, rhs: Self) -> Self;
    pub fn mul(self, rhs: Self) -> Self;
    pub fn div(self, rhs: Self) -> Self;
    pub fn rem(self, rhs: Self) -> Self;
    pub fn sqrt(self) -> Self;
}
```

### 5.2 PyFloat 改造
文件：`crates/vm/src/builtins/float.rs`
- 替换内部字段：
```rust
pub struct PyFloat {
    value: SoftF64, // when feature "pvm-softfloat"
}
```
- `Add/Sub/Mul/Div/Mod/Pow` 使用 SoftFloat 运算
- `__eq__/__lt__` 等比较使用 SoftFloat 比较规则
- `float.__hash__` 使用 `SoftF64::to_bits()` 生成稳定 hash

### 5.2.1 必须覆盖的 float 方法清单
需要逐一确认以下方法不再触达硬件 `f64`：
- 构造与转换：`__new__`, `__float__`, `__int__`, `__bool__`
- 算术：`__add__`, `__sub__`, `__mul__`, `__truediv__`, `__floordiv__`,
  `__mod__`, `__pow__`, `__neg__`, `__pos__`, `__abs__`
- 比较：`__eq__`, `__lt__`, `__le__`, `__gt__`, `__ge__`
- 其他：`as_integer_ratio`, `is_integer`, `hex`, `fromhex`, `__round__`

### 5.2.2 特殊值处理规范
- NaN：比较总为 False（除 `!=`），`repr` 固定为 `nan`
- Inf：`repr` 固定为 `inf` 或 `-inf`
- -0.0：保持符号位，`repr` 输出 `-0.0`

### 5.2.3 解析与字面量来源
RustPython parser 会将 float literal 解析为 `f64`：
- 需要在 bytecode/constant 层重新转换为 SoftF64
- 推荐方案：保存原始字符串并在运行时用 SoftFloat parse
- 如果成本过高，允许使用确定性 float parser 输出 `f64` 后转 bits


### 5.3 字面量与解析
- Python 浮点字面量解析：
  - 解析字符串 -> SoftF64
  - 使用确定性 decimal->binary 算法，不使用平台 `libm`

### 5.4 格式化与输出
- `repr/str/format` 使用位模式输出
- `float.hex()` 使用 SoftFloat 位模式重建
- NaN/Inf 的文本输出必须稳定（固定大小写和符号）

### 5.5 math 模块支持
文件：`crates/vm/src/stdlib/math.rs`
- 首版建议支持：
  - `fabs`, `floor`, `ceil`, `trunc`
  - `sqrt`, `pow`, `exp`, `log`
  - `isfinite`, `isinf`, `isnan`
- 对未实现函数抛 `DeterministicValidationError`

### 5.5.1 math 函数分级
必须实现（v1）：
- `sqrt`, `pow`, `exp`, `log`, `fabs`, `floor`, `ceil`, `trunc`
建议延后（v2）：
- `sin`, `cos`, `tan`, `atan2`
不建议支持（v1）：
- `frexp`, `ldexp`（涉及位级转换，需 softfloat 支持）


### 5.6 complex 策略
- 低侵入版本：确定性模式下禁用 `complex`（抛异常）
- 高级版本：实现 `SoftComplex`

---

## 6. opcode 级 Gas 计量（低侵入实现）

### 6.1 GasMeter 接口
新增文件：`crates/vm/src/vm/gas.rs`
```rust
pub trait GasMeter {
    fn charge(&self, amount: u64) -> PyResult<()>;
    fn left(&self) -> u64;
}
```

### 6.2 VM 挂载 GasMeter
文件：`crates/vm/src/vm/mod.rs`
- 在 `VirtualMachine` 中加入 `gas_meter: Option<Arc<dyn GasMeter>>`
- 提供 `vm.set_gas_meter(...)`

### 6.3 opcode 执行计费
文件：`crates/vm/src/frame.rs`
- 在 opcode dispatch 循环入口：
```rust
if let Some(gas) = vm.gas_meter() {
    gas.charge(cost_for(opcode))?;
}
```
- `cost_for(opcode)`：
  - 默认 1
  - `CALL_*` +10
  - `BUILD_LIST/DICT/SET` +len
  - `IMPORT_*` +20

### 6.4 Host API 计费
- `pvm_host` 调用由 Host 侧计费（链实现可按读写字节计费）
- VM 侧仅保证 opcode 计费

### 6.5 OutOfGas 错误映射
文件：`crates/pvm-runtime/src/lib.rs`
- `map_exception` 识别 `OutOfGasError` -> `HostError::OutOfGas`

### 6.6 Gas 计费细则（初版表）
默认成本表（示意）：
- LOAD/STORE/UNARY/BINARY op: 1
- COMPARE op: 1
- JUMP/BRANCH: 1
- CALL/PREPARE_CALL: 10
- BUILD_LIST/DICT/SET: 1 + len
- IMPORT_*: 20
- FORMAT_*: 5

动态成本：
- `pvm_host.state_get`：按 key/返回值字节数加计
- `pvm_host.state_set`：按 key/value 字节数加计
- `emit_event`：按 topic/data 字节数加计

### 6.7 递归与栈限制
建议加入执行限制：
- 递归深度固定上限（例如 128）
- 调用深度上限（例如 32）
- 每个 frame 的最大 stack size 限制


---

## 7. Checkpoint/Resume 版本锁定

### 7.1 Checkpoint 元信息扩展
文件：`crates/vm/src/vm/snapshot.rs`
- 在 `CheckpointState` 中添加：
```rust
pub pvm_version: String
pub stdlib_hash: String
pub code_hash: [u8; 32]
```

### 7.1.1 code_hash 计算规则
- 对 `code` 字节做 `sha256`
- 对脚本路径不参与 hash（避免路径差异）
- 执行前比较当前 code 的 hash 与 checkpoint 内值

### 7.3 HostContext 扩展
文件：`crates/pvm-host/src/lib.rs`
建议新增字段：
```rust
pub struct HostContext {
    pub chain_id: u64,
    pub pvm_version: u32,
    pub stdlib_hash: [u8; 32],
    ...
}
```


### 7.2 Resume 校验
文件：`crates/vm/src/vm/checkpoint.rs`
- 读取 checkpoint 后检查：
  - `pvm_version` 是否匹配当前 runtime
  - `stdlib_hash` 是否一致
  - `code_hash` 是否匹配当前 code

---

## 8. Determinism 测试与验收

### 8.1 功能测试
- SoftFloat 运算一致性
- math 子集输出一致性
- 黑名单模块禁止导入
- `open`/IO 禁止

### 8.2 确定性回放
- 相同输入执行 N 次，输出/事件/状态/ checkpoint bytes 完全一致
- 跨平台对比测试（Linux/macOS/Windows）

### 8.3 Gas 测试
- 低 gas 限制触发 OutOfGas
- 不同 opcode 计费正确

---

## 9. 具体文件级实施清单（操作项）

### Runtime
- [ ] `crates/pvm-runtime/src/determinism.rs` 新增
- [ ] `crates/pvm-runtime/src/lib.rs` 扩展 ExecutionOptions
- [ ] `crates/pvm-runtime/src/guard.rs` 新增 import/builtins/sys guard

### VM
- [ ] `crates/vm/src/builtins/float.rs` SoftFloat 替换
- [ ] `crates/vm/src/stdlib/math.rs` softfloat 子集
- [ ] `crates/vm/src/vm/gas.rs` GasMeter trait
- [ ] `crates/vm/src/frame.rs` opcode 计费
- [ ] `crates/vm/src/vm/checkpoint.rs` 元信息校验
- [ ] `crates/vm/src/vm/snapshot.rs` checkpoint meta

### Lib
- [ ] `Lib/pvm_sdk/pvm_time.py`
- [ ] `Lib/pvm_sdk/pvm_random.py`
- [ ] `Lib/pvm_sdk/pvm_sys.py`

---

## 10. 验收标准（Definition of Done）

1) 相同输入在不同机器上输出一致
2) 所有非确定性模块导入被拒绝
3) SoftFloat 运算通过黄金测试
4) opcode gas 可用且不会影响正常执行
5) checkpoint/resume 版本一致性校验通过

---

## 11. 交付顺序建议

### 阶段 A（2-3 周）
- import guard + 白名单
- deterministic runtime settings
- opcode 计费基本版

### 阶段 B（3-5 周）
- SoftFloat 核心替换
- math 子集
- hash(float) 稳定

### 阶段 C（可选）
- SoftComplex
- 更细化 gas 表

---

## Appendix A. f64 使用点审计清单（需逐项确认）

以下是 `crates/vm/src` 中出现 `f64` 的主要类别（摘自代码扫描）：

### A.1 VM 核心必须改造
- `crates/vm/src/builtins/float.rs`：核心 float 逻辑
- `crates/vm/src/vm/context.rs`：`new_float` 创建入口
- `crates/vm/src/function/number.rs`：数值转换与参数解析
- `crates/vm/src/vm/snapshot.rs`：checkpoint 中 float 序列化

### A.2 可通过禁用模块绕过
- `crates/vm/src/stdlib/time.rs`
- `crates/vm/src/stdlib/os.rs`
- `crates/vm/src/stdlib/signal.rs`
- `crates/vm/src/stdlib/thread.rs`
- `crates/vm/src/stdlib/ctypes/*`

### A.3 解析层需确认
- `crates/vm/src/stdlib/ast/constant.rs`：Float 常量承载
- `crates/vm/src/stdlib/marshal.rs`：marshal/反序列化 float

处理策略：
- VM 核心与解析层必须改造为 SoftFloat
- 被禁模块可不改，但需确保 import guard 生效

---

## Appendix B. 白名单模块分级表（建议）

### B.1 无条件允许（纯确定性）
- `builtins`, `types`, `enum`, `collections`, `collections.abc`
- `operator`, `functools`, `itertools`

### B.2 允许但需限制参数
- `json`：禁止 file-like 参数
- `struct`：禁止 `@` 本地字节序
- `hashlib`：禁止隐式随机 salt

### B.3 禁止
- 所有 IO/系统/网络/并发模块
- `inspect`, `traceback`, `sys` 原生接口

---

## Appendix C. 扩展 gas 成本表（建议版）

此表可作为 chain 参数注入，避免 hardcode：

- `LOAD_*` / `STORE_*`: 1
- `UNARY_*`: 1
- `BINARY_*`: 1
- `COMPARE_*`: 1
- `CALL_*`: 10
- `BUILD_LIST`: 1 + len
- `BUILD_TUPLE`: 1 + len
- `BUILD_DICT`: 1 + 2*len
- `BUILD_SET`: 1 + len
- `IMPORT_*`: 20
- `FORMAT_VALUE`: 5

动态成本：
- `pvm_host.state_get`: 5 + key_len + value_len
- `pvm_host.state_set`: 10 + key_len + value_len
- `emit_event`: 5 + topic_len + data_len
