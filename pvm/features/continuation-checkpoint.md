# Continuation 和 Checkpoint 功能

## 概述

PVM 支持在执行过程中保存和恢复程序状态，这对于长时间运行的程序、调试和需要暂停/恢复的场景非常有用。

## 功能特性

### Checkpoint（检查点）
- 在执行过程中保存程序状态快照
- 状态包括：调用栈、局部变量、全局状态等
- 可以保存到存储中，供后续恢复使用

### Resume（恢复）
- 从保存的检查点恢复执行
- 继续执行，就像从未中断过一样
- 支持多次恢复

## 使用方式

### 1. 启用 Continuation

在 `ExecutionOptions` 中配置：

```rust
use pvm_runtime::{ExecutionOptions, ContinuationOptions};
use rustpython_vm::vm::ContinuationMode;

let options = ExecutionOptions {
    continuation: Some(ContinuationOptions {
        mode: ContinuationMode::Fsm,
        checkpoint_key: Some(b"actor_checkpoint".to_vec()),
        ..Default::default()
    }),
    ..Default::default()
};
```

### 2. 保存 Checkpoint

当执行遇到检查点时，PVM 会自动保存状态到指定的 key：

```rust
// checkpoint_key 指定的存储 key
host.state_set(b"actor_checkpoint", &checkpoint_bytes)?;
```

### 3. 恢复执行

从保存的检查点恢复：

```rust
let resume_bytes = host.state_get(b"actor_checkpoint")?
    .ok_or(HostError::NotFound)?;

let options = ExecutionOptions {
    continuation: Some(ContinuationOptions {
        mode: ContinuationMode::Fsm,
        resume_bytes: Some(resume_bytes),
        resume_key: Some(b"actor_checkpoint".to_vec()),
        ..Default::default()
    }),
    ..Default::default()
};
```

## ContinuationMode

### Fsm（有限状态机模式）
- 适合大多数场景
- 支持完整的检查点/恢复功能
- 默认模式

## 使用场景

1. **长时间运行的批处理任务**
   - 可以定期保存检查点
   - 如果中断，可以从检查点恢复

2. **复杂计算**
   - 需要中断和恢复的复杂计算
   - 避免重复计算

3. **调试和开发**
   - 保存执行状态用于调试
   - 快速恢复测试场景

4. **资源受限环境**
   - 在资源受限时可以暂停
   - 资源可用时恢复执行

## 注意事项

1. **存储成本**: Checkpoint 数据可能较大，需要考虑存储成本
2. **性能影响**: 保存检查点会有一定的性能开销
3. **兼容性**: 检查点格式可能随版本变化，需要版本管理
4. **安全性**: 检查点包含程序状态，需要适当的安全措施

## 示例

参考 `pvm/examples/breakpoint_resume_demo/` 目录下的示例代码。
