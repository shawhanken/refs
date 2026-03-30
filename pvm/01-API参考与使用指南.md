> [!WARNING]
> **API 细节可能过时 (API Details May Be Outdated)**
> 本文档最后更新于 2026-01-24（v0.4.0）。此后 Host API 经历了多次更改，包括：
> gas 常量调整（MAILBOX_SEND_BASE_CYCLES 500→80 等）、`storage_get` Cycles 计费逻辑变更、
> 新增 `max_cycles` 限制参数等。请以 `node/execution/src/pvm_host.rs` 和 `node/execution/src/gas.rs` 为准。

# PVM API 参考与使用指南

**最后更新**: 2026-01-24
**版本**: 0.4.0

---

## 📚 概述

本文档提供 PVM (Python Virtual Machine) 的完整 API 参考和使用指南，包括 Host API、Runtime API 以及实际使用示例。

---

## 🔌 Host API 参考

### HostApi Trait

`HostApi` trait 定义了 PVM 执行环境与链交互的接口。

**位置**: `pvm/crates/pvm-host/src/lib.rs`

### Trait 定义

```rust
pub trait HostApi {
    // 状态管理
    fn state_get(&self, key: &[u8]) -> HostResult<Option<Bytes>>;
    fn state_set(&mut self, key: &[u8], value: &[u8]) -> HostResult<()>;
    fn state_delete(&mut self, key: &[u8]) -> HostResult<()>;

    // 事件
    fn emit_event(&mut self, topic: &str, data: &[u8]) -> HostResult<()>;

    // Gas 管理
    fn charge_gas(&mut self, amount: u64) -> HostResult<()>;
    fn gas_left(&self) -> u64;

    // 上下文
    fn context(&self) -> HostContext;
    fn randomness(&self, domain: &[u8]) -> HostResult<[u8; 32]>;

    // 消息和定时器
    fn send_message(&mut self, target: &[u8], payload: &[u8]) -> HostResult<()>;
    fn schedule_timer(&mut self, height: u64, payload: &[u8]) -> HostResult<Bytes>;
    fn cancel_timer(&mut self, timer_id: &[u8]) -> HostResult<()>;
}
```

### HostContext 结构体

```rust
#[derive(Clone, Debug)]
pub struct HostContext {
    pub block_height: u64,
    pub block_hash: [u8; 32],
    pub tx_hash: [u8; 32],
    pub sender: Bytes,
    pub timestamp_ms: u64,
    pub actor_addr: Bytes,
    pub msg_id: Bytes,
    pub nonce: u64,
}
```

### HostError 枚举

```rust
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum HostError {
    OutOfGas,
    InvalidInput,
    NotFound,
    StorageError,
    Forbidden,
    Internal,
}
```

---

## ⚙️ Runtime API 参考

### 执行函数

#### execute_tx

简单的执行函数，使用默认选项。

```rust
pub fn execute_tx(
    host: &mut dyn HostApi,
    code: &[u8],
    input: &[u8]
) -> Result<Bytes, HostError>
```

#### execute_tx_with_options

带选项的执行函数，支持更多配置。

```rust
pub fn execute_tx_with_options(
    host: &mut dyn HostApi,
    code: &[u8],
    input: &[u8],
    options: &ExecutionOptions,
) -> Result<Bytes, HostError>
```

### ExecutionOptions

执行选项配置结构体。

```rust
#[derive(Clone, Debug)]
pub struct ExecutionOptions {
    pub argv: Vec<String>,
    pub module_name: String,
    pub source_path: String,
    pub input_var: String,
    pub output_var: String,
    pub entrypoint: Option<String>,
    pub host_module_name: String,
    pub init_stdlib: bool,
    pub deterministic: bool,
    pub hash_seed: Option<u32>,
    pub determinism: Option<DeterminismOptions>,
    pub set_main_module: bool,
    pub continuation: Option<ContinuationOptions>,
}
```

### ContinuationOptions

Continuation 和 checkpoint 功能配置。

```rust
#[derive(Clone, Debug)]
pub struct ContinuationOptions {
    pub mode: ContinuationMode,
    pub resume_bytes: Option<Vec<u8>>,
    pub resume_key: Option<Vec<u8>>,
    pub checkpoint_key: Option<Vec<u8>>,
}
```

### ContinuationMode

```rust
pub enum ContinuationMode {
    Fsm,      // 有限状态机模式
    Checkpoint, // Checkpoint 模式
}
```

---

## 📖 使用示例

### 基本使用

```rust
use pvm_runtime::{execute_tx, ExecutionOptions};
use pvm_host::HostApi;

// 简单的执行
let output = execute_tx(&mut host, &code, &input)?;

// 带选项的执行
let options = ExecutionOptions {
    entrypoint: Some("handle_message".to_string()),
    deterministic: true,
    ..Default::default()
};
let output = execute_tx_with_options(&mut host, &code, &input, &options)?;
```

### Continuation 使用

```rust
use pvm_runtime::{ExecutionOptions, ContinuationOptions};
use rustpython_vm::vm::ContinuationMode;

// 启用 Continuation
let options = ExecutionOptions {
    continuation: Some(ContinuationOptions {
        mode: ContinuationMode::Checkpoint,
        checkpoint_key: Some(b"actor_checkpoint".to_vec()),
        ..Default::default()
    }),
    ..Default::default()
};

// 执行
let output = execute_tx_with_options(&mut host, &code, &input, &options)?;

// 恢复执行
let resume_bytes = host.state_get(b"actor_checkpoint")?
    .ok_or(HostError::NotFound)?;

let resume_options = ExecutionOptions {
    continuation: Some(ContinuationOptions {
        mode: ContinuationMode::Checkpoint,
        resume_bytes: Some(resume_bytes),
        resume_key: Some(b"actor_checkpoint".to_vec()),
        ..Default::default()
    }),
    ..Default::default()
};
```

### Python Actor 示例

```python
import pvm_host

def handle_message(msg):
    """处理消息的 Actor handler"""
    # 获取当前计数器
    counter_bytes = pvm_host.get_state(b"counter")
    if counter_bytes is None:
        counter = 0
    else:
        counter = int.from_bytes(counter_bytes, 'big')
    
    # 增加计数器
    counter += 1
    
    # 保存状态
    pvm_host.set_state(b"counter", counter.to_bytes(8, 'big'))
    
    # 发射事件
    pvm_host.emit_event("counter_updated", counter.to_bytes(8, 'big'))
    
    # 消耗 Gas
    pvm_host.charge_gas(1000)
    
    # 返回结果
    return f"Counter: {counter}, Input: {msg.decode()}".encode()
```

---

## 🔗 相关文档

- **功能设计与 Continuation** (`02-功能设计与Continuation.md`) - Continuation 机制详解
- **Checkpoint/Resume 实现指南** (`03-Checkpoint-Resume实现指南.md`) - 实现细节
- **编码规范与最佳实践** (`04-编码规范与最佳实践.md`) - 编码规范

---

**文档版本**: 1.0  
**最后更新**: 2026-01-24
