# 借用检查器问题 - 最终解决方案设计

## 问题根源

`HostGuard` 使用 `PhantomData<&'a mut dyn HostApi>` 标记生命周期，导致编译器认为对 `ctx` 的借用会持续到整个函数结束，即使 `HostGuard` 实际在 `execute_tx_with_options` 返回时就被 drop 了。

## 已尝试的方案

### ❌ 方案1: RefCell + unsafe
- 使用 `RefCell` 实现内部可变性
- 使用 `unsafe` 块绕过借用检查器
- 问题：编译器仍然认为借用持续存在

### ❌ 方案2: 在 execute_handler 中返回副作用
- 让 `execute_handler` 返回 `(Bytes, ExecutionSideEffects)`
- 问题：在 `execute_handler` 内部提取副作用时仍有借用冲突

### ❌ 方案3: 在 execution.rs 中提取副作用
- 在 `execute_handler` 返回后提取副作用
- 问题：编译器认为借用仍然持续

## ✅ 最终推荐方案：Rc<RefCell<>>

### 核心思路

将副作用字段改为 `Rc<RefCell<Vec<...>>>`，这样：
1. `PvmExecutionContext` 持有一个 `Rc` 引用
2. 可以在创建 context 时克隆 `Rc` 引用
3. 在 `execute_handler` 返回后，使用克隆的 `Rc` 引用提取副作用
4. 不需要直接访问被借用的 `ctx`

### 代码设计

```rust
// pvm_host.rs
pub struct PvmExecutionContext<'a, S: StateStore> {
    // ... 其他字段 ...
    
    // 使用 Rc<RefCell<>> 实现共享可变性
    pub events: std::rc::Rc<std::cell::RefCell<Vec<(String, Vec<u8>)>>>,
    pub outgoing_messages: std::rc::Rc<std::cell::RefCell<Vec<(Vec<u8>, Vec<u8>)>>>,
    pub scheduled_timers: std::rc::Rc<std::cell::RefCell<Vec<(u64, Vec<u8>, Vec<u8>)>>>,
    pub cancelled_timers: std::rc::Rc<std::cell::RefCell<Vec<Vec<u8>>>>,
}

impl<'a, S: StateStore> PvmExecutionContext<'a, S> {
    pub fn new(...) -> Self {
        Self {
            // ... 其他字段 ...
            events: std::rc::Rc::new(std::cell::RefCell::new(Vec::new())),
            outgoing_messages: std::rc::Rc::new(std::cell::RefCell::new(Vec::new())),
            scheduled_timers: std::rc::Rc::new(std::cell::RefCell::new(Vec::new())),
            cancelled_timers: std::rc::Rc::new(std::cell::RefCell::new(Vec::new())),
        }
    }
    
    /// 获取副作用的克隆引用（用于在 execute_handler 返回后提取）
    pub fn get_side_effects_refs(&self) -> (
        std::rc::Rc<std::cell::RefCell<Vec<(String, Vec<u8>)>>>,
        std::rc::Rc<std::cell::RefCell<Vec<(Vec<u8>, Vec<u8>)>>>,
        std::rc::Rc<std::cell::RefCell<Vec<(u64, Vec<u8>, Vec<u8>)>>>,
        std::rc::Rc<std::cell::RefCell<Vec<Vec<u8>>>>,
    ) {
        (
            self.events.clone(),
            self.outgoing_messages.clone(),
            self.scheduled_timers.clone(),
            self.cancelled_timers.clone(),
        )
    }
}
```

```rust
// execution.rs
// 在调用 execute_handler 之前，克隆副作用的 Rc 引用
let side_effects_refs = pvm_ctx.get_side_effects_refs();

// 执行 handler
let execution_result = self.pvm_executor.execute_handler(&mut pvm_ctx, payload, handler).await;

// 从克隆的引用中提取副作用（不需要访问被借用的 pvm_ctx）
let side_effects = ExecutionSideEffects {
    outgoing_messages: std::mem::take(&mut *side_effects_refs.1.borrow_mut()),
    scheduled_timers: std::mem::take(&mut *side_effects_refs.2.borrow_mut()),
    cancelled_timers: std::mem::take(&mut *side_effects_refs.3.borrow_mut()),
    events: std::mem::take(&mut *side_effects_refs.0.borrow_mut()),
};

// 处理结果
match execution_result {
    Ok(output) => {
        pvm_ctx.commit().await?;
        // 处理 side_effects...
    }
    Err(e) => {
        pvm_ctx.rollback();
        return Err(...);
    }
}
```

### 优点

1. **无需 unsafe**: 完全使用安全的 Rust 代码
2. **清晰的所有权**: Rc 明确表示共享所有权
3. **运行时开销小**: Rc 的引用计数开销很小
4. **符合 Rust 习惯**: 这是 Rust 中处理共享可变性的标准模式

### 缺点

1. 轻微的运行时开销（Rc 引用计数和 RefCell 运行时检查）
2. 代码稍微复杂一点（但更安全）

## 实施步骤

1. 修改 `PvmExecutionContext` 的字段类型为 `Rc<RefCell<>>`
2. 更新所有访问这些字段的代码（使用 `borrow_mut()`）
3. 在 `execution.rs` 中，在调用 `execute_handler` 前克隆 Rc 引用
4. 在 `execute_handler` 返回后，使用克隆的引用提取副作用
5. 测试编译和功能

## 预期结果

编译成功，无借用检查器错误，运行时行为正确。

## 备选方案

如果 Rc<RefCell<>> 方案仍有问题，可以考虑：
1. 使用 Arc<Mutex<>> 实现线程安全的共享可变性（但 async 环境中 Mutex 有限制）
2. 重构 pvm-runtime 的 HostGuard 设计（但需要修改上游代码）
3. 使用消息传递模式（将副作用通过返回值传递，而不是累积在 context 中）
