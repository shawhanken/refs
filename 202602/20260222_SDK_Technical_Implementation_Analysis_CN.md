# Cowboy SDK 技术实现路径分析

**日期**: 2026-02-22
**状态**: 分析报告
**范围**: CIP-6 SDK 规范 vs 现有代码实现对比，完整实现路径

---

## 一、总体架构概述

Cowboy SDK 的设计目标是在确定性 Python VM (PVM) 之上提供高级开发者抽象，隐藏底层的消息传递、Timer、Gas 计量等机制。SDK 分布在以下三层：

```
┌────────────────────────────────────────────────────┐
│  开发者代码层 (Developer Code)                      │
│  @actor, call(), send(), await runner.llm(), ...   │
├────────────────────────────────────────────────────┤
│  Python SDK 层 (pvm_sdk)                           │
│  actor.py, runner.py, continuation.py, verify.py   │
│  types.py, pvm_random.py, pvm_time.py, ...         │
├────────────────────────────────────────────────────┤
│  Host API 层 (pvm_host - Rust)                     │
│  send_message, get/set/delete_state, context,      │
│  randomness, runtime_config, emit_event, gas meter │
├────────────────────────────────────────────────────┤
│  PVM Runtime (Rust: pvm-runtime + RustPython)      │
│  确定性执行、Continuation (FSM/Checkpoint)、         │
│  SoftFloat、模块白名单、Gas 计量                     │
├────────────────────────────────────────────────────┤
│  链核心 (cowboy-chain)                              │
│  ExecutionEngine, BlockchainStorage, Consensus      │
└────────────────────────────────────────────────────┘
```

---

## 二、现有代码实现状态分析

### 2.1 Python SDK 层 (`node/pvm/Lib/pvm_sdk/`)

| 文件 | 功能 | 实现状态 | 完成度 |
|------|------|---------|--------|
| `__init__.py` | SDK 入口、模块导出 | ✅ 已实现 | 90% |
| `continuation.py` | Capture/序列化/Continuation 状态管理 | ✅ 基本实现 | 70% |
| `runner.py` | Runner 任务发送、Awaitable | ⚠️ 部分实现 | 40% |
| `actor.py` | ActorRef、Actor 间异步调用 | ⚠️ 骨架实现 | 20% |
| `verify.py` | 验证构建器 | ⚠️ 部分实现 | 30% |
| `types.py` | PVM 安全类型 | ⚠️ 存根实现 | 10% |
| `pvm_random.py` | 确定性随机数 | ✅ 完整实现 | 95% |
| `pvm_time.py` | 区块时间 | ✅ 已实现 | 90% |
| `pvm_sys.py` | 系统元数据 | ✅ 已实现 | 90% |
| `runtime.py` | 运行时模式检测 | ✅ 已实现 | 90% |

### 2.2 Rust Host API 层 (`node/chain/src/pvm_host.rs`)

已实现的 Host API 方法：

| 方法 | 功能 | CIP-6 需求覆盖 |
|------|------|---------------|
| `send_message(target, payload)` | 发送消息到目标 Actor | send() 的底层支撑 |
| `get_state(key)` | 读取 Actor 存储 | storage.get() |
| `set_state(key, value)` | 写入 Actor 存储 | storage.set() |
| `delete_state(key)` | 删除存储键 | Continuation 清理 |
| `context()` | 获取执行上下文 | block_height, sender, tx_hash 等 |
| `randomness(domain)` | VRF 确定性随机 | pvm_random 支撑 |
| `runtime_config()` | 运行时配置 | continuation_mode 检测 |
| `emit_event(topic, data)` | 发出事件 | 日志/审计 |
| `call_actor(target, method, args, cycles)` | 同步调用 Actor | call() 的底层支撑 |

**缺失的 Host API**:
- `set_timer()` / `cancel_timer()` — Timer 系统的 Host 调用
- `get_balance()` — 查询余额
- `transfer()` — 价值转移
- `get_code_hash()` — 查询 Actor 代码哈希

### 2.3 PVM Runtime 层

| 组件 | 实现状态 | 说明 |
|------|---------|------|
| RustPython VM | ✅ 完整 | 基于 RustPython fork，支持确定性执行 |
| SoftFloat | ✅ 已实现 | `vm/src/softfloat.rs`，56 个测试通过 |
| Continuation - Checkpoint 模式 | ✅ 已实现 | 运行时保存/恢复，可跨块 |
| Continuation - FSM 模式 | ⚠️ 骨架存在 | `codegen/src/pvm_fsm.rs` 存在，但编译器未完整 |
| 确定性子系统 | ✅ 已实现 | 模块白名单、固定哈希种子、无 JIT |
| Gas 计量 (Cycles) | ✅ 已实现 | 字节码级别计量 |
| Gas 计量 (Cells) | ✅ 已实现 | I/O 边界计量 |
| 模块白名单 | ✅ 已实现 | `determinism.rs` 管理 |

### 2.4 Runner 系统

| 组件 | 实现状态 | 说明 |
|------|---------|------|
| LLM 执行器 | ✅ 已实现 | OpenAI / Anthropic API |
| HTTP 执行器 | ✅ 已实现 | GET/POST/PUT 等 |
| MCP 执行器 | ✅ 已实现 | Model Context Protocol |
| 结果验证器 | ✅ 已实现 | 6 种验证模式 |
| Runner 注册表 | ✅ 已实现 | VRF 选择 |
| 任务分发器 | ✅ 已实现 | 链上 System Actor |
| TEE 验证器 | ⚠️ 框架实现 | 具体验证逻辑待完善 |

---

## 三、CIP-6 规范与现有代码的详细差距分析

### 3.1 调用原语 (Chapter 1)

#### `call()` — 同步调用 (T+0)

**CIP-6 规范要求**:
```python
balance = call(
    target="0x1111...",
    method="get_balance",
    args={"user": user},
    cycles_limit=5000
)
```

**当前实现状态**: ⚠️ 底层 Host API 存在 (`call_actor`)，但 Python 层无封装

**差距**:
- Python SDK 缺少 `call()` 顶层函数
- 缺少 `cycles_limit` 参数传递
- 缺少调用深度检查 (最大 32 层)
- 缺少返回值 CBOR 反序列化
- 缺少 `ActorRef` 语法糖 (如 `oracle.get_price("ETH")` 自动编译为 `call(...)`)

**实现路径**:
1. 在 `pvm_sdk/__init__.py` 导出 `call()` 函数
2. `call()` 内部调用 `pvm_host.call_actor(target, method, cbor_encode(args), cycles_limit)`
3. 返回值进行 CBOR 解码
4. `ActorRef.__getattr__` 通过 `__call__` 代理为 `call()` 调用

#### `send()` — 异步消息 (T+N)

**CIP-6 规范要求**:
```python
send(target="0x3333...", message={"action": "notify", "order_id": order_id})
```

**当前实现状态**: ⚠️ 底层 `pvm_host.send_message()` 存在，但 Python 层仅在 `runner.py` 内部使用

**差距**:
- 缺少 `send()` 顶层函数
- 当前 `send_message()` 接受原始 bytes payload，无自动序列化
- 缺少消息 ID 生成逻辑的 Python 封装
- 缺少扇出限制检查 (每交易最多 1024 条)

**实现路径**:
1. 在 `pvm_sdk/__init__.py` 导出 `send()` 函数
2. `send(target, message)` → `pvm_host.send_message(target, cbor_encode(message))`
3. 消息 ID 由 Host 层自动生成

#### `@reentrancy_guard` — 重入保护

**当前实现状态**: ❌ 未实现

**实现路径**:
1. 创建 `pvm_sdk/guards.py`
2. 装饰器在方法入口时通过 `pvm_host.get_state()` 检查锁状态
3. 锁键: `keccak256(method_name + caller_addr)`
4. 入口加锁、出口解锁（包括异常路径）

### 3.2 Continuation 机制 (Chapter 2)

#### `@runner.continuation` — FSM 编译

**CIP-6 规范要求**:
```python
@runner.continuation
async def example(self, msg):
    ctx = capture()
    ctx.a = await runner.llm("step1")
    ctx.b = await runner.llm(f"step2: {ctx.a}")
    return ctx.b
```
编译为显式 FSM 状态机。

**当前实现状态**:
- Checkpoint 模式 ✅: `_RunnerAwaitable.__await__` 通过 `rustpython_checkpoint.checkpoint_bytes()` 实现暂停/恢复
- FSM 模式 ⚠️: `runner.continuation` 装饰器是空壳 (直接返回原函数)，`pvm_fsm.rs` 有骨架但编译器不完整

**差距**:
- FSM 编译器 (`codegen/src/pvm_fsm.rs`) 需要完成 AST → 状态机转换
- 需要实现 `example__resume()` 自动生成
- 缺少 `await` 点计数限制 (最多 8 个)
- 缺少嵌套函数 await 的静态检查

**实现路径**（两条路线，可并行）:

**路线 A — Checkpoint 模式优先（当前可用）**:
1. 保持现有 `rustpython_checkpoint` 机制
2. 完善 `_RunnerAwaitable`，增加 `timeout_blocks`、`verification` 参数
3. 优点: 简单、已可用；缺点: 状态快照较大、恢复成本高

**路线 B — FSM 编译器（长期目标）**:
1. 完善 `codegen/src/pvm_fsm.rs`，实现 Python AST → FSM 代码变换
2. 在部署阶段（`compile_actor()`）执行转换
3. 每个 `await` 生成一个 `state_N` 分支
4. 优点: 状态精简、确定性强；缺点: 实现复杂度高

**推荐策略**: 短期以 Checkpoint 模式为生产可用基线，中期开发 FSM 编译器。

#### `capture()` — 显式状态捕获

**当前实现状态**: ✅ 基本实现

`Capture` 类已实现属性动态存取、序列化/反序列化：
```python
class Capture:
    def __getattr__(self, name): ...
    def __setattr__(self, name, value): ...
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, value) -> Capture: ...
```

**差距**:
- 缺少 CBOR 序列化（当前使用 JSON）
- 缺少类型安全检查（禁止闭包、函数引用、生成器）
- 缺少大小限制 (单个 Continuation 最大 64 KiB)

**实现路径**:
1. 将 `_encode_json` / `_decode_json` 替换为 CBOR 编码（使用 `cbor2` 或 Rust 侧 CBOR）
2. 在 `__setattr__` 中添加类型白名单检查
3. 在 `save_cont()` 中添加大小检查

#### `@bounded_loop` — 有界循环

**当前实现状态**: ❌ 未实现

**实现路径**:
1. 创建装饰器 `bounded_loop(max_iterations=N)`
2. 在编译/运行时注入迭代计数器
3. 超过上限抛出 `LoopBoundExceeded`
4. FSM 模式下，编译器据此生成固定数量的状态

#### `@actor.continuation` — Actor 间异步调用

**当前实现状态**: ⚠️ 骨架存在

`actor.py` 中的 `ActorRef.async_call()` 和 `_ActorAwaitable` 仅有框架，`__await__` 直接抛出 `RuntimeError`。

**实现路径**:
1. `async_call()` → 生成 correlation_id
2. 通过 `pvm_host.send_message()` 发送请求
3. 注册回调处理器
4. Checkpoint 模式下暂停等待
5. 收到响应时恢复执行

### 3.3 状态安全机制 (Chapter 3)

#### `guard_unchanged` — 装饰器级守卫

**当前实现状态**: ⚠️ 数据结构存在但未强制执行

`continuation.py` 的 `save_cont()` 接受 `guard_unchanged` 参数并序列化存储，但恢复时**未做校验**。

**差距**:
- `load_cont()` 不检查 guard 值是否变化
- 缺少 `keccak256(cbor(storage.get(key)))` 指纹计算
- 缺少 `StateConflictError` 异常类型

**实现路径**:
1. `save_cont()` 时，对每个 guard key 计算 `snapshot_hash = keccak256(cbor(storage.get(key)))`
2. 存入 continuation state 的 `guard_hashes` 字段
3. `load_cont()` / `resume` 时重新计算哈希，不一致则抛出 `StateConflictError`

#### `storage.guard()` — 对象级精细守卫

**当前实现状态**: ❌ 未实现

**实现路径**:
1. 创建 `GuardedValue` 类
2. `storage.guard(key)` 返回 `GuardedValue(key, snapshot_hash, value)`
3. 访问 `.value` 属性时自动验证当前哈希与快照一致
4. 不一致抛出 `StateConflictError`

### 3.4 异步工具 (Chapter 4)

#### `Retry` — 重试策略

**当前实现状态**: ❌ 未实现

**实现路径**:
```python
class Retry:
    def __init__(self, max_attempts, backoff="exponential"):
        self.max_attempts = max_attempts
        self.backoff = backoff
```
在 `_RunnerAwaitable` 中读取 retry_policy，失败时按退避序列重试。

#### `TaskGroup` — 结构化并发

**当前实现状态**: ❌ 未实现

**实现路径**:
1. 创建 `TaskGroup` 上下文管理器
2. `create_task()` 按顺序分配 nonce，发送任务到 Runner
3. 退出 `async with` 块时，等待所有任务完成
4. 结果按创建顺序排列（确定性保证）

### 3.5 类型系统 (Chapter 5)

#### `SoftFloat` — 软件浮点

**当前实现状态**: ⚠️ Python SDK 中仅为 `str` 包装

```python
class SoftFloat(str):
    def __new__(cls, value):
        return str.__new__(cls, str(value))
```

但 Rust PVM 层已实现真正的 SoftFloat（`vm/src/softfloat.rs`，56 个测试通过）。

**差距**: Python SDK 的 `SoftFloat` 没有实际算术能力，无法进行 `>`, `<`, `+`, `-` 等运算。

**实现路径**:
1. 方案 A: 在 Rust 侧通过 `pvm_host` 暴露 softfloat 运算，Python 侧调用
2. 方案 B: PVM 全局替换 Python 的 `float` 为 softfloat（RustPython 已支持）
3. 推荐方案 B: RustPython 的 softfloat 模块已完成，只需确保 SDK 层的 `SoftFloat` 类型与之正确对接

#### `CowboyModel` — PVM 安全数据模型

**当前实现状态**: ❌ 未实现

**实现路径**:
1. 基于 `dataclasses` (白名单模块) 实现轻量版数据模型
2. 字段验证: 禁止 `float`（强制 `SoftFloat`）、禁止 `set`（强制 `ordered_set`）
3. 提供 `schema()` 方法，生成 JSON Schema 用于 Runner 验证
4. CBOR 序列化/反序列化支持

#### `ordered_set` — 有序集合

**当前实现状态**: ❌ 未实现

**实现路径**:
1. PVM 层已有设计 — 将 `set` 透明替换为插入顺序集合
2. 可在 RustPython VM 层拦截 `set()` 构造，返回 `ordered_set`
3. 或在 SDK 层提供 `ordered_set` 类基于 `dict` 键集实现

#### `BlockHeight` — 语义化区块高度

**当前实现状态**: ❌ 未实现

**实现路径**: 简单的 `int` 子类加类型标注，主要用于 API 文档和 IDE 提示。

### 3.6 声明式验证构建器 (Chapter 6)

#### `Verify` — 验证器

**当前实现状态**: ⚠️ 部分实现

已实现:
- `Verify.builder()` ✅
- `.mode()`, `.runners()`, `.threshold()`, `.check()`, `.build()` ✅
- `Verify.json_schema_valid()` ✅
- `Verify.structured_match()` ✅
- `Verify.majority_vote()` ✅

未实现的检查器 (14 个):
| 检查器 | 状态 |
|--------|------|
| `exact_match()` | ❌ |
| `numeric_tolerance(field, tolerance)` | ❌ |
| `numeric_range(field, min, max)` | ❌ |
| `set_equality(field)` | ❌ |
| `contains_all(substrings)` | ❌ |
| `contains_none(substrings)` | ❌ |
| `regex_match(pattern)` | ❌ |
| `length_bounds(min, max)` | ❌ |
| `semantic_similarity(threshold)` | ❌ |
| `no_prompt_leak()` | ❌ |
| `entropy_check(min_entropy)` | ❌ |
| `custom(actor, method)` | ❌ |
| `supermajority_vote(field, threshold)` | ❌ |

**注意**: Runner 侧（Rust）的 `result-verifier` crate 已实现 6 种验证模式，SDK 需与之对齐。

**实现路径**: 每个检查器只需返回标准化的 dict 结构，由 Runner 侧实际执行检查。

### 3.7 序列化层

**CIP-6 要求**: 所有跨信任边界数据使用 Canonical CBOR (RFC 8949)

**当前实现**: continuation.py 使用 JSON (`json.dumps(sort_keys=True, separators=(',',':'))`)

**差距**: JSON 不满足 CBOR 规范要求。但 JSON 在当前阶段可用作过渡方案。

**实现路径**:
1. 短期: 保持 JSON (已有确定性 sort_keys 保证)
2. 中期: 引入 `cbor2` 库或 Rust 侧 CBOR 编码，通过 Host API 暴露
3. 所需 CBOR 规则:
   - 映射键字节字典序排序
   - 整数最短编码
   - 无不定长度数组/映射
   - 浮点数编码为 64 位 IEEE 754

---

## 四、Host API 缺失项分析

以下 Host API 是实现 CIP-6 完整 SDK 所必需但当前缺失的：

| Host API | 用途 | CIP-6 关联 | 优先级 |
|----------|------|-----------|--------|
| `call_actor(target, method, args, cycles)` | 同步调用 Actor | `call()` 原语 | P0 |
| `set_timer(height, handler, data)` | 设置定时器 | Timeout 机制 | P1 |
| `cancel_timer(timer_id)` | 取消定时器 | Timeout 清理 | P1 |
| `get_balance(address)` | 查询余额 | 状态查询 | P1 |
| `transfer(to, amount)` | 价值转移 | 原生转账 | P1 |
| `keccak256(data)` | 哈希计算 | guard 指纹 | P1 |
| `cbor_encode(value)` / `cbor_decode(data)` | CBOR 序列化 | 跨边界数据 | P2 |
| `current_block()` | 当前区块高度 | BlockHeight 类型 | P2 |
| `self_address()` | 当前 Actor 地址 | ActorRef 引用 | P1 |

> 注意: `call_actor` 在 Rust Host 层可能已部分实现（`pvm_host.rs` 中有调用 Actor 的逻辑），但需验证 Python 侧是否已暴露。

---

## 五、分阶段实现路线图

### Phase 0: 基础原语层（预计 2-3 周）

**目标**: 让 CIP-6 第一章的三种调用原语可用

| 任务 | 优先级 | 工作量估计 | 依赖 |
|------|--------|-----------|------|
| 实现 `call()` Python 封装 | P0 | 3 天 | Host API `call_actor` |
| 实现 `send()` Python 封装 | P0 | 2 天 | 已有 `send_message` |
| 完善 `ActorRef` 同步调用语法糖 | P0 | 2 天 | `call()` |
| 实现 `@actor` 装饰器 | P1 | 2 天 | 无 |
| 实现 `@reentrancy_guard` | P1 | 3 天 | `get_state`/`set_state` |
| 导出 `self.address`、`self.storage` 等 Actor 属性 | P1 | 2 天 | Host API |

**交付物**:
- `pvm_sdk/call.py` — `call()` 函数
- `pvm_sdk/send.py` — `send()` 函数
- `pvm_sdk/actor.py` — 增强的 `@actor` 装饰器和 `ActorRef`
- `pvm_sdk/guards.py` — `@reentrancy_guard`

### Phase 1: Continuation 增强（预计 3-4 周）

**目标**: 完善跨块异步机制

| 任务 | 优先级 | 工作量估计 | 依赖 |
|------|--------|-----------|------|
| 增强 `runner.llm/http` 的参数支持 | P0 | 3 天 | 无 |
| 实现 `timeout_blocks` 强制执行 | P0 | 5 天 | Timer Host API |
| 实现 `guard_unchanged` 校验逻辑 | P0 | 3 天 | `keccak256` Host API |
| 实现 `storage.guard()` 精细守卫 | P1 | 3 天 | guard 基础设施 |
| 实现 `@bounded_loop` | P1 | 3 天 | 无 |
| 实现 `capture()` 类型安全检查 | P1 | 2 天 | 无 |
| 实现 `capture()` 大小限制 (64 KiB) | P2 | 1 天 | 无 |
| 暴露 `runner.mcp()` | P1 | 2 天 | Runner MCP 执行器 |

**交付物**:
- `continuation.py` — 增强的 guard 校验和大小限制
- `runner.py` — 完整参数支持、timeout、mcp
- `guards.py` — `storage.guard()`, `GuardedValue`

### Phase 2: 类型系统与验证（预计 2-3 周）

**目标**: PVM 安全类型和完整验证器

| 任务 | 优先级 | 工作量估计 | 依赖 |
|------|--------|-----------|------|
| 对接 SoftFloat (PVM 层已有) | P0 | 3 天 | RustPython softfloat |
| 实现 `CowboyModel` | P1 | 5 天 | `dataclasses` |
| 实现 `ordered_set` | P1 | 3 天 | 无 |
| 补全 Verify 检查器 (14 个) | P0 | 5 天 | 无 |
| 实现 `Retry` 类 | P1 | 2 天 | 无 |
| 实现 `BlockHeight` 类型 | P2 | 1 天 | 无 |

**交付物**:
- `types.py` — 完整的 `SoftFloat`、`ordered_set`、`BlockHeight`
- `models.py` — `CowboyModel` 基类
- `verify.py` — 全部 17 个内置检查器
- `retry.py` — `Retry` 策略类

### Phase 3: 高级异步模式（预计 3-4 周）

**目标**: TaskGroup、Actor 间异步调用、FSM 编译器原型

| 任务 | 优先级 | 工作量估计 | 依赖 |
|------|--------|-----------|------|
| 实现 `TaskGroup` | P0 | 5 天 | Continuation 基础 |
| 实现 `@actor.continuation` 完整流程 | P0 | 5 天 | `send_message` |
| FSM 编译器原型 (`pvm_fsm.rs`) | P1 | 10 天 | RustPython codegen |
| 序列化迁移到 CBOR | P2 | 5 天 | `cbor2` 或 Host CBOR |
| 条件分支 await 支持 | P1 | 3 天 | FSM 编译器 |
| 循环 await + `@bounded_loop` FSM 支持 | P1 | 5 天 | FSM 编译器 |

**交付物**:
- `taskgroup.py` — `TaskGroup` 上下文管理器
- `actor.py` — 完整的 `@actor.continuation`
- `pvm_fsm.rs` — FSM 编译器原型

### Phase 4: 生产就绪化（预计 4-6 周）

| 任务 | 优先级 | 工作量估计 |
|------|--------|-----------|
| 完整的端到端集成测试 | P0 | 10 天 |
| 确定性测试套件（跨平台一致性验证） | P0 | 5 天 |
| 文档和开发者指南 | P0 | 5 天 |
| `cowboy_sdk` 包名统一（从 `pvm_sdk` 重命名） | P1 | 3 天 |
| 错误消息国际化和开发者友好化 | P2 | 3 天 |
| 性能基准测试 | P1 | 5 天 |

---

## 六、关键技术实现细节

### 6.1 `call()` 同步调用的实现方案

```
┌──────────┐     call(target, method, args)     ┌──────────┐
│ Actor A  │ ──────────────────────────────────> │ Actor B  │
│ (Python) │                                    │ (Python) │
│          │ <── return result (CBOR decoded) ── │          │
└────┬─────┘                                    └──────────┘
     │
     │ pvm_host.call_actor(target_bytes, method, cbor(args), cycles_limit)
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│ CowboyHost (Rust - pvm_host.rs)                          │
│ 1. 序列化参数                                             │
│ 2. 检查调用深度 (≤32)                                     │
│ 3. 扣除 cycles_limit                                     │
│ 4. 切换到目标 Actor 执行上下文                              │
│ 5. 执行 Actor B 的 method                                 │
│ 6. 收集返回值                                             │
│ 7. 退还未使用的 cycles                                    │
│ 8. 返回 CBOR 编码的结果 (或传播异常)                        │
└──────────────────────────────────────────────────────────┘
```

**Python SDK 层实现**:
```python
# pvm_sdk/call.py
import pvm_host
from .continuation import encode_payload, decode_payload

def call(target, method, args=None, cycles_limit=10000):
    if isinstance(target, str):
        target = bytes.fromhex(target.replace("0x", ""))
    payload = encode_payload(args or {})
    result_bytes = pvm_host.call_actor(target, method, payload, cycles_limit)
    if result_bytes is None:
        return None
    return decode_payload(result_bytes)
```

### 6.2 Continuation 状态机完整流程

```
Block N                          Block N+K
┌──────────────────┐             ┌──────────────────┐
│ hybrid_workflow() │             │ example__resume() │
│                  │             │                  │
│ 1. ctx.balance = │             │ 1. load_cont(cid)│
│    call(...)     │             │ 2. verify guards │
│ 2. save guard    │             │ 3. ctx = restore │
│    snapshot_hash │             │ 4. ctx.analysis  │
│ 3. save_cont(cid,│             │    = msg.result  │
│    state=0, ctx) │             │ 5. if recommend: │
│ 4. send(RUNNER,  │             │    call(trade)   │
│    job_spec)     │             │ 6. send(notify)  │
│ 5. return (挂起) │             │ 7. delete_cont() │
└──────────────────┘             └──────────────────┘
        │                                ▲
        │    Runner 链下执行               │
        ▼                                │
┌──────────────────┐             ┌──────────────────┐
│  Runner System   │────────────>│ 延迟交易回调       │
│  LLM/HTTP/MCP    │   result    │ handle_resume()  │
└──────────────────┘             └──────────────────┘
```

### 6.3 Guard 校验的实现方案

```python
# continuation.py 增强

def save_cont(cid, state, ctx, handler, timeout_blocks=0, guard_unchanged=None):
    # ... 现有逻辑 ...
    
    # 新增: 计算 guard 快照哈希
    guard_hashes = {}
    if guard_unchanged:
        for key in guard_unchanged:
            value = pvm_host.get_state(key.encode("utf-8"))
            if value is not None:
                guard_hashes[key] = hashlib.sha256(value).hexdigest()
            else:
                guard_hashes[key] = None
    
    payload["guard_hashes"] = guard_hashes
    pvm_host.set_state(_cont_key(cid), _encode_json(payload))


def verify_guards(cont_data):
    """恢复时验证 guard 状态未变"""
    guard_hashes = cont_data.get("guard_hashes", {})
    for key, expected_hash in guard_hashes.items():
        current_value = pvm_host.get_state(key.encode("utf-8"))
        if current_value is not None:
            current_hash = hashlib.sha256(current_value).hexdigest()
        else:
            current_hash = None
        if current_hash != expected_hash:
            raise StateConflictError(
                f"Guard violation: storage key '{key}' changed during continuation"
            )
```

### 6.4 TaskGroup 实现方案

```python
# pvm_sdk/taskgroup.py

class TaskGroup:
    def __init__(self):
        self._tasks = []
        self._nonce_base = None
    
    async def __aenter__(self):
        ctx = pvm_host.context()
        self._nonce_base = ctx.get("nonce", 0)
        return self
    
    async def __aexit__(self, *args):
        # 等待所有任务完成（通过 checkpoint 暂停）
        for task in self._tasks:
            if task.result is None:
                await task
    
    def create_task(self, awaitable):
        task = _TaskHandle(awaitable, len(self._tasks))
        self._tasks.append(task)
        return task


class _TaskHandle:
    def __init__(self, awaitable, index):
        self._awaitable = awaitable
        self._index = index
        self.result = None
    
    def __await__(self):
        self.result = yield from self._awaitable.__await__()
        return self.result
```

### 6.5 Verify 检查器完整实现

```python
# verify.py 补全

class Verify:
    # ... 已有方法 ...
    
    @staticmethod
    def exact_match():
        return {"kind": "exact_match"}
    
    @staticmethod
    def numeric_tolerance(field, tolerance):
        return {"kind": "numeric_tolerance", "field": field, "tolerance": str(tolerance)}
    
    @staticmethod
    def numeric_range(field, min_val, max_val):
        return {"kind": "numeric_range", "field": field, "min": min_val, "max": max_val}
    
    @staticmethod
    def set_equality(field):
        return {"kind": "set_equality", "field": field}
    
    @staticmethod
    def contains_all(substrings):
        return {"kind": "contains_all", "substrings": list(substrings)}
    
    @staticmethod
    def contains_none(substrings):
        return {"kind": "contains_none", "substrings": list(substrings)}
    
    @staticmethod
    def regex_match(pattern):
        return {"kind": "regex_match", "pattern": pattern}
    
    @staticmethod
    def length_bounds(min_len, max_len):
        return {"kind": "length_bounds", "min": min_len, "max": max_len}
    
    @staticmethod
    def semantic_similarity(threshold):
        return {"kind": "semantic_similarity", "threshold": str(threshold)}
    
    @staticmethod
    def no_prompt_leak():
        return {"kind": "no_prompt_leak"}
    
    @staticmethod
    def entropy_check(min_entropy):
        return {"kind": "entropy_check", "min_entropy": str(min_entropy)}
    
    @staticmethod
    def custom(actor, method):
        return {"kind": "custom", "actor": actor, "method": method}
    
    @staticmethod
    def supermajority_vote(field, threshold):
        return {"kind": "supermajority_vote", "field": field, "threshold": threshold}
```

---

## 七、白皮书与 SDK 规范一致性矩阵

| 白皮书章节 | CIP-6 对应 | 代码实现 | 一致性 |
|-----------|-----------|---------|--------|
| Actor 模型 (私有状态/邮箱) | Ch1 调用原语 | types/execution.rs: Actor 结构体 | ✅ 一致 |
| 消息传递 (恰好一次) | Ch1.4 send() | storage: enqueue_message + 去重 | ✅ 一致 |
| 重入 (深度限制 32) | Ch1.5 reentrancy | execution.rs: 深度计数 | ✅ 一致 |
| Continuation (FSM) | Ch2 编译策略 | pvm_fsm.rs (骨架) | ⚠️ 未完成 |
| Continuation (Checkpoint) | Ch2 (隐含) | rustpython_checkpoint | ✅ 已实现 |
| capture() | Ch2.2 状态捕获 | continuation.py: Capture | ✅ 基本一致 |
| guard | Ch3 状态安全 | save_cont() 参数存在 | ⚠️ 未强制执行 |
| Timeout (区块高度) | Ch4.1 | Timer Host API | ⚠️ 框架存在 |
| 确定性 Python VM | PVM 章节 | pvm-runtime + RustPython | ✅ 一致 |
| SoftFloat | PVM 数值确定性 | vm/softfloat.rs | ✅ Rust 层完成 |
| 固定哈希种子 | PVM 哈希排序 | determinism.rs | ✅ 一致 |
| CBOR 序列化 | 序列化章节 | 当前使用 JSON | ⚠️ 需迁移 |
| 模块白名单 | PVM 模块管理 | determinism.rs | ✅ 一致 |
| Runner 任务框架 | 链下计算 | runner 系统完整 | ✅ 一致 |
| 验证模式 (6 种) | Ch6 验证构建器 | result-verifier crate | ✅ Rust 层完成 |
| Runner VRF 选择 | Runner 选择 | ecvrf.rs, registry.rs | ✅ 一致 |
| 双 Gas (Cycles/Cells) | 费用章节 | execution.rs 双计量 | ✅ 一致 |
| Timer 系统 | 定时器章节 | storage: Timer + 索引 | ✅ 一致 |
| 专用通道 | 共识网络 | — | ❌ 未实现 |
| MEV 防护 (VRF 排序) | 共识 MEV | — | ❌ 未实现 |

---

## 八、风险和注意事项

### 8.1 包名统一
- **现状**: 代码中使用 `pvm_sdk`，CIP-6 文档使用 `cowboy_sdk`，白皮书 v2 使用 `cowboy_sdk`
- **建议**: 在 Phase 4 统一重命名为 `cowboy_sdk`，需更新所有 import 路径

### 8.2 序列化格式迁移
- **风险**: 从 JSON 迁移到 CBOR 是一个破坏性变更
- **缓解**: 在 CBOR 迁移时实现双模式（检测格式自动切换），设定弃用时间表

### 8.3 FSM vs Checkpoint 模式的选择
- **FSM 优势**: 状态更小、确定性更强、Gas 更可预测
- **Checkpoint 优势**: 实现简单、灵活性高、已可用
- **风险**: 两种模式并存增加维护复杂度
- **建议**: 短期 Checkpoint 为默认，FSM 作为优化路径，最终标准化为 FSM

### 8.4 向后兼容性
- 每个 Phase 的 API 变更需保持向后兼容
- 弃用的 API 至少保留一个版本周期
- 使用 `__version__` 标记 SDK 版本

### 8.5 安全考量
- `call()` 的 `cycles_limit` 必须由开发者显式指定，防止无限递归
- `capture()` 必须验证值类型，禁止序列化不安全对象（闭包、生成器）
- `guard_unchanged` 必须在所有恢复路径上强制执行，包括超时和错误路径

---

## 九、优先级矩阵总结

| 优先级 | 功能 | Phase | 工作量 |
|--------|------|-------|--------|
| **P0** | `call()` / `send()` 原语 | 0 | 5 天 |
| **P0** | `timeout_blocks` 强制执行 | 1 | 5 天 |
| **P0** | `guard_unchanged` 校验 | 1 | 3 天 |
| **P0** | Verify 检查器补全 | 2 | 5 天 |
| **P0** | `SoftFloat` 对接 | 2 | 3 天 |
| **P0** | `TaskGroup` | 3 | 5 天 |
| **P0** | `@actor.continuation` | 3 | 5 天 |
| **P0** | 端到端测试 | 4 | 10 天 |
| **P1** | `@actor` 装饰器 | 0 | 2 天 |
| **P1** | `@reentrancy_guard` | 0 | 3 天 |
| **P1** | `storage.guard()` | 1 | 3 天 |
| **P1** | `@bounded_loop` | 1 | 3 天 |
| **P1** | `CowboyModel` | 2 | 5 天 |
| **P1** | `ordered_set` | 2 | 3 天 |
| **P1** | `Retry` 类 | 2 | 2 天 |
| **P1** | FSM 编译器原型 | 3 | 10 天 |
| **P1** | 包名统一 (`cowboy_sdk`) | 4 | 3 天 |
| **P2** | CBOR 序列化迁移 | 3 | 5 天 |
| **P2** | `BlockHeight` 类型 | 2 | 1 天 |
| **P2** | `capture()` 大小限制 | 1 | 1 天 |

**总预估工作量**: 约 12-16 周（1 人全职）

---

## 十、模块文件结构设计（最终形态）

```
node/pvm/Lib/cowboy_sdk/          # 重命名后的 SDK
├── __init__.py                    # 顶层导出: call, send, actor, runner, capture, ...
├── call.py                        # call() 同步调用原语
├── send.py                        # send() 异步消息原语
├── actor.py                       # @actor 装饰器, ActorRef, @actor.continuation
├── runner.py                      # @runner.continuation, runner.llm/http/mcp
├── continuation.py                # Capture, save/load/delete_cont, CID 生成
├── guards.py                      # @reentrancy_guard, GuardedValue, storage.guard()
├── verify.py                      # Verify builder, 17 个内置检查器
├── retry.py                       # Retry 策略
├── taskgroup.py                   # TaskGroup 结构化并发
├── models.py                      # CowboyModel 数据模型基类
├── types.py                       # SoftFloat, ordered_set, BlockHeight
├── errors.py                      # StateConflictError, LoopBoundExceeded, ...
├── bounded_loop.py                # @bounded_loop 装饰器
├── runtime.py                     # 运行时模式检测
├── pvm_time.py                    # 确定性时间 (区块高度)
├── pvm_random.py                  # 确定性随机数 (VRF)
└── pvm_sys.py                     # 系统元数据
```

---

## 附录 A: 现有代码关键文件索引

| 文件路径 | 功能 | 行数 |
|----------|------|------|
| `node/pvm/Lib/pvm_sdk/__init__.py` | SDK 入口 | 24 |
| `node/pvm/Lib/pvm_sdk/continuation.py` | Continuation 状态管理 | 158 |
| `node/pvm/Lib/pvm_sdk/runner.py` | Runner 任务封装 | 82 |
| `node/pvm/Lib/pvm_sdk/actor.py` | Actor 引用和异步调用 | 28 |
| `node/pvm/Lib/pvm_sdk/verify.py` | 验证构建器 | 45 |
| `node/pvm/Lib/pvm_sdk/types.py` | PVM 类型 | 3 |
| `node/pvm/Lib/pvm_sdk/pvm_random.py` | 确定性随机 | 196 |
| `node/pvm/Lib/pvm_sdk/pvm_time.py` | 区块时间 | 9 |
| `node/pvm/Lib/pvm_sdk/pvm_sys.py` | 系统信息 | 6 |
| `node/pvm/Lib/pvm_sdk/runtime.py` | 运行时检测 | 6 |
| `node/chain/src/pvm_host.rs` | Host API 实现 | ~800 |
| `node/chain/src/pvm_executor.rs` | PVM 执行器 | ~300 |
| `node/chain/src/execution.rs` | 交易执行引擎 | ~1500 |
| `node/pvm/crates/pvm-runtime/src/` | PVM 核心运行时 | ~2000 |
| `node/pvm/crates/pvm-host/src/lib.rs` | Host API Trait | ~100 |
| `runner/crates/result-verifier/src/verifier.rs` | 结果验证器 | ~500 |
| `runner/crates/runner-common/src/types.rs` | Runner 公共类型 | ~400 |

## 附录 B: CIP-6 章节映射

| CIP-6 章节 | 本文对应章节 | 实现状态 |
|------------|------------|---------|
| Ch1: 调用原语 | §3.1 | ⚠️ 底层存在，SDK 层缺失 |
| Ch2: Continuation | §3.2 | ⚠️ Checkpoint 可用，FSM 未完成 |
| Ch3: 状态安全 | §3.3 | ⚠️ 数据结构存在，校验逻辑缺失 |
| Ch4: 异步工具 | §3.4 | ❌ Retry/TaskGroup 未实现 |
| Ch5: 类型系统 | §3.5 | ⚠️ SoftFloat Rust 层完成，SDK 层存根 |
| Ch6: 验证构建器 | §3.6 | ⚠️ 3/17 检查器已实现 |
| Ch7: 混合模式 | §6.1-6.5 | ❌ 需要所有组件就绪 |
| App A: PVM 兼容性 | §7 白皮书矩阵 | ✅ 大部分规则已在 PVM 层执行 |

---

*本文档基于 2026-02-22 的代码库状态生成。随着开发进展，各项状态可能更新。*
