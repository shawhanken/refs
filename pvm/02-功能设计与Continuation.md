# PVM 功能设计与 Continuation 机制

**最后更新**: 2026-01-24

---

## 📋 概述

本文档详细说明 PVM 的核心功能设计，特别是 Continuation 机制，包括 Actor↔Actor 与 Actor↔Runner 的 continuation 实现方案。

---

## 🎯 Continuation 设计

### SDK API 草案（Python 侧）

#### 调用原语
- `call(target: str, method: str, args: dict, cycles_limit: int) -> Any`
  - 同区块同步执行，返回值必须 CBOR-safe。
- `send(target: str, message: dict) -> None`
  - 异步投递至下一区块。

#### Continuation 相关
- `capture() -> Ctx`
  - 返回 dict-like 对象，仅允许写入 CBOR-safe 类型。
- `@runner.continuation(timeout_blocks: int = 0, guard_unchanged: list[str] = [])`
  - async 函数编译为 FSM；跨块执行。
- `@actor.continuation(timeout_blocks: int = 0, guard_unchanged: list[str] = [])`
  - Actor 间异步请求-响应。
- `ActorRef(address: str)`
  - `ActorRef.async_<method>(*args, **kwargs)` 编译为 send + resume。

#### Runner API
- `runner.llm(prompt: str, response_model=None, verification=None, timeout_blocks=0, tee_required=False)`
- `runner.http(url: str, method="GET", headers=None, body=None, timeout_blocks=0, retry_policy=None)`

#### 确定性异常
- `StateConflictError`（guard 失败）
- `ContinuationTimeoutError`
- `DeterministicValidationError`（Schema/CBOR 校验失败）
- `LoopBoundExceeded`

---

## 🔧 编译期约束（强制）

1. `await` 点数量上限（建议 8，最小版本可先 2）
2. 循环中 `await` 必须通过 `@bounded_loop(max_iterations=...)`
3. 禁止嵌套函数中 `await`
4. 禁止递归 `await`
5. `capture()` 必须显式声明跨 await 的变量
6. `guard_unchanged` 的 key 必须是 storage 的稳定 key

---

## 🔄 Continuation 编译形态（FSM）

### 原始 async 函数

```python
@runner.continuation
async def f(self, msg):
    ctx = capture()
    ctx.a = await runner.llm("step1")
    ctx.b = await runner.llm(f"step2: {ctx.a}")
    return ctx.b
```

### 编译后（示意）

```python
def f(self, msg):
    cid = _new_cid(self, "f")
    _save_cont(cid, state=0, ctx={}, guard=...)
    send(RUNNER, job=..., cid=cid, reply="f__resume")

def f__resume(self, reply):
    st = _load_cont(reply.cid)
    if st.state == 0:
        st.ctx["a"] = reply.result
        _save_cont(reply.cid, state=1, ctx=st.ctx, guard=st.guard)
        send(RUNNER, job=..., cid=reply.cid, reply="f__resume")
        return
    if st.state == 1:
        st.ctx["b"] = reply.result
        _delete_cont(reply.cid)
        return st.ctx["b"]
```

---

## 📦 CBOR Schema（消息与状态）

### Continuation State

```text
CBOR Map {
  "state": uint,
  "ctx": map<string, cbor_value>,
  "guard": map<string, bytes32>,
  "created_block": uint,
  "timeout_block": uint,
  "checksum": bytes32
}
```

### Runner Job

```text
CBOR Map {
  "kind": "runner_job",
  "job_type": "llm" | "http" | "mcp" | "custom",
  "payload": map,
  "cid": bytes32,
  "reply_to": bytes20,
  "reply_handler": string,
  "timeout_block": uint,
  "verification": map,
  "tee_required": bool
}
```

### Runner Result

```text
CBOR Map {
  "kind": "runner_result",
  "cid": bytes32,
  "status": "ok" | "error",
  "result": cbor_value,
  "proof": map
}
```

### Actor Async Call

```text
CBOR Map {
  "kind": "actor_async_call",
  "cid": bytes32,
  "method": string,
  "args": map,
  "reply_handler": string
}
```

---

## 🔒 Guard 机制

### Decorator Guard
`@runner.continuation(guard_unchanged=["k1","k2"])`
- 保存 `hash(cbor(storage["k1"]))`
- 恢复时重新计算，若不同抛 `StateConflictError`

### Object Guard
`self.storage.guard("balance")`
- 返回 `GuardedValue`，访问 `.value` 时触发校验

---

## 📝 capture() 允许的 CBOR-safe 类型

**白名单**:
- `None`, `bool`, `int`, `bytes`, `str`
- `list`（成员需 CBOR-safe）
- `dict`（key 必须为 `str`，value 必须 CBOR-safe）
- `SoftFloat`（软件浮点类型）
- `ordered_set`（需序列化为有序数组）

**禁止**:
- 函数/闭包/生成器
- 文件句柄、socket、线程对象
- 任意含非确定性内部状态的对象

---

## 🔄 Continuation 和 Checkpoint 功能

### 概述

PVM 支持在执行过程中保存和恢复程序状态，这对于长时间运行的程序、调试和需要暂停/恢复的场景非常有用。

### 功能特性

#### Checkpoint（检查点）
- 在执行过程中保存程序状态快照
- 状态包括：调用栈、局部变量、全局状态等
- 可以保存到存储中，供后续恢复使用

#### Resume（恢复）
- 从保存的检查点恢复执行
- 继续执行，就像从未中断过一样
- 支持多次恢复

### 使用方式

#### 1. 启用 Continuation

在 `ExecutionOptions` 中配置：

```rust
use pvm_runtime::{ExecutionOptions, ContinuationOptions};
use rustpython_vm::vm::ContinuationMode;

let options = ExecutionOptions {
    continuation: Some(ContinuationOptions {
        mode: ContinuationMode::Checkpoint,
        checkpoint_key: Some(b"actor_checkpoint".to_vec()),
        ..Default::default()
    }),
    ..Default::default()
};
```

#### 2. 保存 Checkpoint

当执行遇到检查点时，PVM 会自动保存状态到指定的 key：

```rust
// checkpoint_key 指定的存储 key
host.state_set(b"actor_checkpoint", &checkpoint_bytes)?;
```

#### 3. 恢复执行

从保存的检查点恢复：

```rust
let resume_bytes = host.state_get(b"actor_checkpoint")?
    .ok_or(HostError::NotFound)?;

let options = ExecutionOptions {
    continuation: Some(ContinuationOptions {
        mode: ContinuationMode::Checkpoint,
        resume_bytes: Some(resume_bytes),
        resume_key: Some(b"actor_checkpoint".to_vec()),
        ..Default::default()
    }),
    ..Default::default()
};
```

### ContinuationMode

#### Fsm（有限状态机模式）
- 适合大多数场景
- 支持完整的检查点/恢复功能
- 默认模式

#### Checkpoint（检查点模式）
- 运行时快照
- 适合长时间任务
- 需要更多存储空间

---

## 🎯 使用场景

1. **长时间运行的批处理任务**
   - 可以定期保存检查点
   - 如果中断，可以从检查点恢复

2. **复杂计算**
   - 分阶段执行
   - 每个阶段保存状态

3. **调试和开发**
   - 在特定点保存状态
   - 方便调试和测试

4. **Actor 间异步通信**
   - 跨块的消息传递
   - 异步请求-响应模式

5. **Runner 系统集成**
   - 链下计算任务
   - LLM 推理、HTTP 请求等

---

## 📚 示例

### 断点恢复演示

参考 `features-breakpoint-resume-demo.md` 了解详细的断点恢复演示。

### Runtime Chain Demo

参考 `examples-runtime-chain-demo.md` 了解如何在链上环境中使用 PVM Runtime。

---

## ⚠️ 实现状态

### 当前状态
- ✅ Checkpoint 模式：已实现基础功能
- ⚠️ FSM 模式：代码存在但默认未启用（需要手动设置 `pvm_fsm: true`）
- ❌ Runner 系统：只有接口框架，未完整实现
- ❌ Guard 机制：未实现

### 注意事项
- FSM 编译器需要显式启用才能使用
- Runner 系统仍在开发中
- 某些高级功能可能需要等待后续版本

---

## 🔗 相关文档

- **API 参考与使用指南** (`01-API参考与使用指南.md`) - API 详细说明
- **Checkpoint/Resume 实现指南** (`03-Checkpoint-Resume实现指南.md`) - 实现细节
- **编码规范与最佳实践** (`04-编码规范与最佳实践.md`) - 编码规范

---

**文档版本**: 1.0  
**最后更新**: 2026-01-24
