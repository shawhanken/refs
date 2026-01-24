# Runner 实施方案（基于现有代码与 refs）

本文将现状、目标语义、双方案实施路径、文件改动清单与接口草案整理成可落地的 Runner 实施方案，便于与现有 PVM 代码对齐推进。

---

## 现状梳理

- Host API 仅提供状态读写/事件/计费/上下文/随机数，尚无消息与定时器接口。  
  参考：`crates/pvm-host/src/lib.rs`、`crates/pvm-runtime/src/module.rs`
- 运行时执行入口是“单笔 TX 同步执行”，暂无跨块/异步语义。  
  参考：`crates/pvm-runtime/src/lib.rs`、`examples/pvm_runtime_chain_demo/main.rs`
- VM 已具备多帧 + block stack 的 checkpoint/resume 与 canonical CBOR 编码。  
  参考：`crates/vm/src/vm/checkpoint.rs`、`crates/vm/src/vm/snapshot.rs`
- Python 侧 SDK 仅包含 time/random/sys 的确定性 shim，缺少 actor/runner/continuation。  
  参考：`Lib/pvm_sdk`、`crates/pylib/Lib/pvm_sdk`

---

## Runner 目标语义（refs 基线）

- Continuation/FSM、capture/guard/timeout、CBOR schema：  
  `refs/PVM_Continuation_Design_CN.md`
- Runner 作为系统 Actor、消息与超时处理语义：  
  `refs/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_EN.md`
- SDK ergonomics（runner.llm/http、Verify.builder、TaskGroup、Timeout）：  
  `refs/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute(Sugguestion-SDK Ergonomics)_v2.md`
- RunnerRegistry/Dispatcher、VRF 选择、lane 等链侧设计：  
  `refs/Cowboy改造方案.md`
- 任务拆解与依赖：  
  `refs/Cowboy_PVM_Task_Plan_CN.md`

---

## 双方案概览

- 方案 A（Checkpoint/Resume）：允许用 VM 级 checkpoint/resume 承接 runner await，粗粒度但落地快。
- 方案 B（FSM 编译方案）：编译期改写 async 为 FSM，显式 continuation，语义清晰且更接近生产。

Runner 系统在链侧（已确认）。

### 共存与互斥原则

- 两套机制可以同时保留，但同一执行只能选择其一。
- FSM 模式下：仅允许 `@runner.continuation` / `@actor.continuation` 驱动的 await。
- Checkpoint 模式下：允许在运行期触发 VM 快照，但禁止 FSM 改写。
- 必须有显式开关（编译期或运行时配置），避免双重持久化。
- 状态存储需命名空间隔离（如 `__continuation:{cid}` vs `__checkpoint:{id}`）。

### 开关设计（具体化）

#### 编译期开关（建议）

- Cargo feature:
  - `pvm_fsm`：启用 AST/FSM 编译 pass。
  - `pvm_checkpoint`：启用运行期 checkpoint 承接 await 的钩子与 SDK。
- 两个 feature 可同时编译，但必须在运行时选择一种模式。

#### 运行时开关（建议）

参考 `DeterminismOptions` 的做法，新增 `ContinuationOptions`（建议放在 `crates/pvm-runtime/src/continuation.rs`），并挂到 `ExecutionOptions`：

```rust
pub enum ContinuationMode {
    Fsm,
    Checkpoint,
}

pub struct ContinuationOptions {
    pub mode: ContinuationMode,
    pub resume_bytes: Option<Vec<u8>>,
    pub resume_key: Option<Vec<u8>>,
    pub checkpoint_key: Option<Vec<u8>>,
}

pub struct ExecutionOptions {
    // ...
    pub continuation: Option<ContinuationOptions>,
}
```

- `ContinuationMode::Fsm`（默认）：
  - 启用编译期 FSM pass。
  - 禁止裸 `await runner.*`（必须装饰器）。
- `ContinuationMode::Checkpoint`：
  - 禁用 FSM pass。
  - `await runner.*` 触发 VM 快照并退出。

#### SDK 行为开关（建议）

避免把运行模式塞进 `HostContext`，单独提供运行时配置接口：

```python
# pvm_host.runtime_config() -> dict
# {"continuation_mode": "fsm" | "checkpoint"}
def mode() -> str:
    return pvm_host.runtime_config().get("continuation_mode", "fsm")
```

- `mode == "fsm"`：启用 `@runner.continuation` / `@actor.continuation` 装饰器逻辑。
- `mode == "checkpoint"`：`runner.llm/http` 返回 awaitable，触发 checkpoint。

#### 存储命名空间（建议）

- FSM continuation：`__continuation:{cid}`
- Checkpoint 快照：`__checkpoint:{tx_hash}` 或 `__checkpoint:{cid}`

#### 默认值与配置来源（建议）

- 默认模式：`ContinuationMode::Fsm`。
- 链侧/嵌入式调用：由 `ExecutionOptions.continuation` 显式传入。
- 本地 CLI（pvm binary / demo runner）可增加参数覆盖默认值：
  - `--continuation=fsm|checkpoint`
  - `--resume-bytes <hex>`（checkpoint 模式）
  - `--resume-key <hex>` / `--checkpoint-key <hex>`

#### CLI 参数建议（对齐现有结构）

- `src/settings.rs` 增加解析：
  - `--continuation fsm|checkpoint`
  - `--resume-bytes <hex>`（仅 checkpoint）
  - `--resume-key <hex>`（仅 checkpoint）
  - `--checkpoint-key <hex>`（仅 checkpoint）
- CLI 转换为 `ExecutionOptions.continuation`，交给 `pvm-runtime`。

#### CLI 参数到 ExecutionOptions 映射表

| CLI 参数 | ExecutionOptions 字段 | 说明 |
| --- | --- | --- |
| `--continuation fsm` | `continuation.mode = Fsm` | 默认模式 |
| `--continuation checkpoint` | `continuation.mode = Checkpoint` | 启用 checkpoint |
| `--resume-bytes <hex>` | `continuation.resume_bytes` | 直接传入快照 bytes |
| `--resume-key <hex>` | `continuation.resume_key` | 从 host state 读取快照 |
| `--checkpoint-key <hex>` | `continuation.checkpoint_key` | 写入快照的存储 key |

#### 本地验证（FSM/Checkpoint）

- 位置：`examples/pvm_runtime_chain_demo/`
- Demo 脚本：
  - `fsm_demo.py`
  - `checkpoint_demo.py`
- 一键运行脚本：
  - `run_fsm_demo.sh`
  - `run_checkpoint_demo.sh`
- macOS 依赖：
  - `DYLD_LIBRARY_PATH` 需包含 `libffi` 与 `libiconv`（脚本已处理）
- 期望结果：
  - FSM：`output_hex=73746172746564`（start）与 `output_hex=646f6e65`（ok）
  - Checkpoint：恢复后 `step=after`、`result={'result': 'ok'}` 写入 state
- 实际验证结果（手动运行）：
  - FSM：`output_hex=73746172746564`（start）、`output_hex=646f6e65`（ok），`tmp/pvm_state/66736d5f726573756c74` 为 `ok`
  - Checkpoint：`tmp/pvm_state/73746570` 为 `after`，`tmp/pvm_state/726573756c74` 为 `{'result': 'ok'}`

### 执行语义补充（两方案共用）

- `await` 是“跨块挂起”，不是同步阻塞；当前执行会结束，结果在后续 TX 回来后再恢复。
- 恢复时必须重新验证关键假设（如 guard），不存在跨块原子性。

---

## 方案 A：Checkpoint/Resume 承接 await

### 核心思路

- 在 `await runner.*` 位置触发 VM 级 checkpoint，写出快照后结束本次执行。
- Runner 结果到达时，下一笔 TX 使用快照恢复执行，继续从 await 之后运行。
- 状态为“全量 VM 快照”，无需编译期 FSM 改写。
  - 这里的“无需编译期 FSM 改写”指不需要在编译器里把 async 改写成 `f`/`f__resume`。
  - 局部变量/调用栈/块栈由快照完整保存，恢复时自动回放。

### 文件改动清单（方案 A）

- `crates/pvm-host/src/lib.rs`
  - 新增消息/计时接口：
    - `send_message`
    - `schedule_timer`
    - `cancel_timer`
  - `HostContext` 增加 `actor_addr`/`msg_id`/`nonce`。
- `crates/pvm-runtime/src/module.rs`
  - 暴露 Python API：
    - `pvm_host.send_message(...)`
    - `pvm_host.schedule_timer(...)`
    - `pvm_host.cancel_timer(...)`
- `crates/pvm-runtime/src/lib.rs`
  - 执行入口支持 `resume_bytes` / `resume_key` / `checkpoint_key`。  
    参考：`refs/PVM_CHAIN_INTEGRATION_CN.md`
- `crates/vm/src/stdlib/rustpython_checkpoint.rs`
  - 增加 bytes API（或透传到 runtime），避免链上文件 I/O。
- `crates/vm/src/vm/checkpoint.rs`
  - 扩展 bytes API，允许从 host state 读取/写入快照。
- `Lib/pvm_sdk` 与 `crates/pylib/Lib/pvm_sdk`
  - 新增 `runner.py`：发送 Runner 任务 + 触发 checkpoint。
  - 新增 `continuation.py`：关联 id、超时与状态 key 规则。

### 优点与限制

- 优点：MVP 快速落地、无需编译器改造。
- 限制：快照体量大、状态耦合 VM 格式、并发 await 成本高。

---

## 方案 B：FSM 编译方案（推荐路线）

### 核心思路

- 编译期把 `async` 函数改写为 FSM（`f` + `f__resume`）。
- 每个 `await` 变成“发送任务 + 保存 continuation state + return”。
- 状态为“显式 ctx + guard + 元数据”，CBOR 序列化，体积可控。

### 文件改动清单（方案 B）

- `crates/pvm-host/src/lib.rs`
  - 新增消息/计时接口：
    - `send_message`
    - `schedule_timer`
    - `cancel_timer`
  - `HostContext` 增加 `actor_addr`/`msg_id`/`nonce`。
- `crates/pvm-runtime/src/module.rs`
  - 暴露 Python API：
    - `pvm_host.send_message(...)`
    - `pvm_host.schedule_timer(...)`
    - `pvm_host.cancel_timer(...)`
- `crates/codegen/src/compile.rs`
  - 插入 AST pass 或引入独立 `pvm-compiler`：
    - `@runner.continuation` / `@actor.continuation` 改写为 FSM。
    - 约束规则：await 计数、bounded_loop、禁止嵌套/递归 await。
- `crates/pvm-cbor`（新）
  - 抽离 canonical CBOR 编码，供 continuation state 与消息使用。
- `Lib/pvm_sdk` 与 `crates/pylib/Lib/pvm_sdk`
  - 新增 `actor.py`/`runner.py`/`continuation.py`/`verify.py`/`types.py`。
  - `capture()`、`guard_unchanged`、`@bounded_loop` 等规则落地。

### 优点与限制

- 优点：语义清晰、状态小、并发友好、生产可维护性高。
- 限制：编译器改造成本高。

### 语义约束补充（FSM 方案）

#### 当前 FSM pass 实现约束（V0）

- 仅支持 `async def` + 单一 `@runner.continuation` / `@actor.continuation` 装饰器。
- 函数体必须以 `ctx = capture()` 开头（允许 docstring 作为第一行）。
- 仅允许 `ctx.<name> = await runner.<job>(...)` 与 `return`。
- 不支持 `if/for/while/try/with`、嵌套 await、多装饰器与复杂参数。
- `timeout_blocks` / `guard_unchanged` 仅写入 continuation state，未自动校验。

#### 全局变量

- 全局变量不会自动跨块持久化，仅 `capture()` 中的 ctx 会被保存。
- 跨块持久状态应写入 storage（`pvm_host.state_*`），而不是依赖 module global。
- 需要跨 await 使用的全局值：
  - 推荐：写入 storage，恢复时重新读取；
  - 可选：在 await 前写入 `ctx`（必须 CBOR-safe）。
- 若担心跨块被修改，使用 `guard_unchanged` 校验。

#### await 在循环体中

- 计划支持：必须使用 `@bounded_loop(max_iterations=...)`。
- 编译器将循环拆成 FSM 状态，循环索引与中间结果写入 `ctx`。
- 当前 V0 pass 未实现循环 lowering，需手动拆分或改用 checkpoint 模式。

#### await 在 try/except 中

- 计划支持：try/except 分支编译为 FSM 状态。
- 仅允许确定性异常分支（如 `RunnerTimeoutError`、`RunnerValidationError`）。
- 当前 V0 pass 未实现 try/except lowering，需改写为显式状态或拆分函数。

#### capture 负担与减负策略

- 编译期自动提示（严格模式）：
  - 编译器做活性分析，凡是 `await` 后仍被使用的变量必须进入 `ctx`。
  - 若未 capture，编译报错并列出变量清单。
- 自动 capture（原型模式）：
  - 允许 `@runner.continuation(auto_capture=True)` 或 `capture(auto=True)`。
  - 编译器自动把跨 await 变量改写为 `ctx.<name>`。
  - 若变量不可 CBOR 序列化，仍报错。
- 长期推荐：
  - 持久状态写入 storage。
  - 仅将必要中间值放入 `ctx`。
- 当前 V0 pass 未实现活性分析与 auto_capture，需要手动写入 `ctx`。

#### FSM 执行过程摘要

- 初次调用 `f`：生成 `cid`，保存 `state=0` 与 `ctx`，发送任务后返回。
- 回调进入 `f__resume`：读取 `state/ctx`，执行下一段逻辑，必要时更新 `state` 再次发送任务。
- 全流程由状态机驱动，不保留原 VM 栈。

#### 变量恢复规则

- 只有写入 `ctx` 的变量会跨块保留。
- 未 capture 的局部变量在 resume 时丢失，若仍被使用应编译期报错。
- 全局变量不作为跨块持久化机制，推荐写入 storage 或显式写入 `ctx`。

#### await 的语法位置限制

- `await` 必须在 `async def` 内部。
- PVM 仅允许在 `@runner.continuation` / `@actor.continuation` 的 async 函数中使用 `await`。
- 顶层 `await` 或普通函数内 `await` 视为编译期错误。

#### `@actor.continuation` 含义

- 标记 Actor 内部的 async handler 也需要编译为 FSM。
- 恢复入口为 `<handler>__resume`，由系统 Actor/消息回调触发并传入 `cid/result`。

#### 循环与重算成本

- 循环中的 `await` 使用单一状态 + `ctx` 索引重复执行，不会生成 100 个状态。
- 两次 `await` 之间的重算必须在单笔执行预算内完成。
- 对重算较重的循环，建议分块执行或下沉到 Runner。
- 该成本模型适用于后续 loop lowering；V0 pass 需先手动拆分循环。

---

## 按层落地（两方案共用）

### 1) 协议与序列化

- 定义结构：
  - `ContinuationState`
  - `RunnerJob`
  - `RunnerResult`
  - `ActorAsyncCall`
- 对照 `refs/PVM_Continuation_Design_CN.md`，保证键排序与类型白名单一致。

### 2) Host API 扩展

- 新增消息/计时接口与扩展 `HostContext`。
- Python 侧通过 `pvm_host` 模块暴露统一接口。

### 3) Runner 系统 Actor（链侧）

- 按 `refs/Cowboy改造方案.md` 实现：
  - RunnerRegistry
  - RunnerDispatcher
  - Runner 选择/支付/惩罚
  - lanes 保留容量
- PVM 侧仅通过 `send/call` 与系统 Actor 通信，保持低耦合。

### 4) 结果验证优先级（首版）

第一版以“最接近生产系统”为目标，建议：
- `structured_match` 为主（覆盖 schema + 字段检查）
- `majority_vote` 作为子集/降级
- `none` 仅用于本地调试

### 5) Storage 机制约定

- Storage 是 Host 提供的 KV：`bytes -> bytes`（见 `pvm_host.state_*`）。
- 数据编码由合约侧负责，推荐使用 canonical CBOR（避免非确定性）。
- Key 建议带命名空间前缀（如 `b"escrow_state_v1"` 或 `b"__continuation:{cid}"`）。
- Gas 计费可由 Host 在 `state_get/set` 时扣费，或由合约显式调用 `charge_gas()`。
- Demo 中使用文件系统作为 KV（见 `crates/pvm-alto/src/lib.rs`）。

---

## 里程碑（建议）

- M1：Host API + SDK 基础 + mock runner（仅 `runner.llm/http`，无验证）。
- M2：Continuation（方案 A: checkpoint 承接；方案 B: FSM 编译）+ 状态存储 + timeout/guard。
- M3：Verify.builder + JSON schema 校验 + RunnerValidationError。
- M4：Runner 系统 Actor 与 registry/dispatch/lanes/结算（链侧）。
- M5：TEE/ZK、挑战窗口与经济惩罚扩展。

---

## 接口草案（关键部分）

### Host API（Rust）

```rust
pub trait HostApi {
    fn state_get(&self, key: &[u8]) -> HostResult<Option<Bytes>>;
    fn state_set(&mut self, key: &[u8], value: &[u8]) -> HostResult<()>;
    fn state_delete(&mut self, key: &[u8]) -> HostResult<()>;

    fn emit_event(&mut self, topic: &str, data: &[u8]) -> HostResult<()>;

    fn charge_gas(&mut self, amount: u64) -> HostResult<()>;
    fn gas_left(&self) -> u64;

    fn context(&self) -> HostContext;
    fn randomness(&self, domain: &[u8]) -> HostResult<[u8; 32]>;

    // new
    fn send_message(&mut self, target: &[u8], payload: &[u8]) -> HostResult<()>;
    fn schedule_timer(&mut self, height: u64, payload: &[u8]) -> HostResult<Bytes>;
    fn cancel_timer(&mut self, timer_id: &[u8]) -> HostResult<()>;
}
```

### HostContext（Rust）

```rust
pub struct HostContext {
    pub block_height: u64,
    pub block_hash: [u8; 32],
    pub tx_hash: [u8; 32],
    pub sender: Bytes,
    pub timestamp_ms: u64,
    // new
    pub actor_addr: Bytes,
    pub msg_id: Bytes,
    pub nonce: u64,
}
```

### pvm_host 运行时配置（Python）

```python
# 由 pvm-runtime 注入，来自 ExecutionOptions.continuation
def runtime_config() -> dict:
    return {
        "continuation_mode": "fsm" or "checkpoint"
    }
```

### Python SDK（示意）

```python
from pvm_sdk import runner, capture

@runner.continuation(timeout_blocks=50)
async def analyze(self, msg):
    ctx = capture()
    ctx.step1 = await runner.http("https://api.example.com/data")
    ctx.step2 = await runner.llm(f"Analyze: {ctx.step1}")
    return ctx.step2
```

### Runner Job / Result（CBOR）

```text
RunnerJob {
  kind: "runner_job",
  job_type: "llm" | "http" | "custom",
  payload: map,
  cid: bytes32,
  reply_to: bytes20,
  reply_handler: string,
  timeout_block: uint,
  verification: map,
  tee_required: bool
}

RunnerResult {
  kind: "runner_result",
  cid: bytes32,
  status: "ok" | "error",
  result: cbor_value,
  proof: map
}
```

---

## 关键决策（已确认）

1. 两套独立方案同时保留：Checkpoint/Resume 方案与 FSM 编译方案。
2. Runner 系统在链侧。
3. 首版验证模式优先级以“最接近生产系统”为目标（建议 structured_match 为主）。
