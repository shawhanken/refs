# 借用检查器问题分析和解决方案

## 问题描述

在 `PvmExecutor::execute_handler` 中，存在借用检查器错误：

```
error[E0502]: cannot borrow `ctx.outgoing_messages` as immutable because it is also borrowed as mutable
```

## 根本原因

1. `execute_tx_with_options` 通过 `HostGuard::install` 将 `host` 安装到 thread-local 存储
2. `HostGuard` 使用 `PhantomData<&'a mut dyn HostApi>` 标记生命周期
3. 编译器认为 `ctx` 的借用会持续到 `HostGuard` 被 drop
4. 但实际上，`HostGuard` 在 `execute_tx_with_options` 返回时就会被 drop

## 当前尝试的解决方案

### 方案 1: 使用 RefCell（已实现）
- 将副作用字段改为 `RefCell<Vec<...>>`
- 问题：`RefCell::take()` 仍然需要不可变借用，与可变借用冲突

### 方案 2: 使用 unsafe（当前尝试）
- 使用 `unsafe` 块绕过借用检查器
- 问题：编译器仍然检测到借用冲突

## 推荐解决方案

### 方案 A: 重构副作用提取时机（推荐）

在 `CowboyHost` 中直接返回副作用，而不是在 `execute_handler` 中提取：

```rust
impl<'a, S: StateStore> CowboyHost<'a, S> {
    pub fn take_side_effects(self) -> ExecutionSideEffects {
        ExecutionSideEffects {
            outgoing_messages: self.ctx.outgoing_messages.take(),
            scheduled_timers: self.ctx.scheduled_timers.take(),
            cancelled_timers: self.ctx.cancelled_timers.take(),
            events: self.ctx.events.take(),
        }
    }
}
```

然后在 `execute_handler` 中：

```rust
let mut host = CowboyHost::new(ctx);
let output = execute_tx_with_options(&mut host, &actor_code, &input, &options)?;
let side_effects = host.take_side_effects();  // host is consumed here
```

### 方案 B: 修改 HostGuard 设计（需要修改 pvm-runtime）

修改 `HostGuard` 的实现，使其不持有生命周期标记，或者提供一个方法来释放借用。

### 方案 C: 使用 ManuallyDrop（临时方案）

使用 `ManuallyDrop` 来手动管理 host 的生命周期。

## 当前状态

- ✅ 已使用 RefCell 实现内部可变性
- ⚠️ 借用检查器仍然报错
- 📝 需要进一步重构或使用 unsafe

## 下一步

1. 尝试方案 A：重构副作用提取
2. 如果不行，考虑修改 pvm-runtime 的 HostGuard 设计
3. 最后选择：使用 unsafe（已添加安全注释）
