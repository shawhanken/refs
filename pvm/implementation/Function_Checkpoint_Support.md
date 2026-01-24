# PVM 函数内 Checkpoint 支持 - 修复指南

## 问题描述

原始 PVM 的 checkpoint/resume 功能存在严重限制：
1. **只支持模块级别** - 无法在函数、循环、条件语句、异常处理块内创建 checkpoint
2. **无法恢复局部变量** - resume 时函数的局部变量丢失，导致 `UnboundLocalError`
3. **无法处理调用栈** - 只保存单个 frame，无法处理嵌套调用

这些限制使得 checkpoint 功能基本无法用于实际的Python程序。

## 核心问题分析

### 问题1：硬性限制只允许顶层 frame
**位置**: `crates/vm/src/vm/checkpoint.rs` 的 `ensure_supported_frame` 函数

```rust
if vm.frames.borrow().len() != 1 {
    return Err(vm.new_runtime_error(
        "checkpoint only supports top-level module frames".to_owned(),
    ));
}
```

**影响**: 任何在函数内调用 `checkpoint()` 都会失败。

### 问题2：局部变量序列化错误
**位置**: `crates/vm/src/vm/snapshot.rs` 的 `dump_checkpoint_frames` 函数

**原始逻辑**:
```rust
let locals_mapping = frame.locals(vm)?;
let locals_obj = locals_mapping.as_object().to_owned();
```

**问题**: 
- `frame.locals()` 返回的是 frame 的 `self.locals` 字段
- 对于函数 frame，这个字段可能指向 globals dict（共享的）
- 导致所有 frame 序列化时使用同一个 dict
- fastlocals 的值虽然存在，但没有被复制到独立的 dict中

### 问题3：lasti 验证逻辑错误
**位置**: `crates/vm/src/vm/checkpoint.rs` 的 `compute_resume_lasti` 函数

**问题**: 对调用栈中的每个 frame 都检查下一条指令是否是 `PopTop`，但只有最内层frame才满足这个条件。

## 解决方案

### 1. 移除 frame 数量限制
**修改**: `checkpoint.rs`

```rust
// 修改前：只允许一个 frame
pub(crate) fn save_checkpoint(vm: &VirtualMachine, path: &str) -> PyResult<()> {
    let frame = vm.current_frame()?;
    ensure_supported_frame(vm, &frame)?;  // 检查 frames.len() != 1
    ...
}

// 修改后：支持多个 frames
pub(crate) fn save_checkpoint(vm: &VirtualMachine, path: &str) -> PyResult<()> {
    let frames = vm.frames.borrow();
    let frame_refs: Vec<_> = frames.iter().map(|f| f.to_owned()).collect();
    // 保存所有 frames
    ...
}
```

### 2. 修改 CheckpointState 结构
**修改**: `snapshot.rs`

```rust
// 修改前：只保存一个 frame
pub(crate) struct CheckpointState {
    pub version: u32,
    pub source_path: String,
    pub lasti: u32,           // 单个 lasti
    pub code: Vec<u8>,        // 单个 code
    pub root: ObjId,
    pub objects: Vec<ObjectEntry>,
}

// 修改后：保存 frame stack
pub(crate) struct CheckpointState {
    pub version: u32,
    pub source_path: String,
    pub frames: Vec<FrameState>,  // Frame 栈
    pub root: ObjId,
    pub objects: Vec<ObjectEntry>,
}

pub(crate) struct FrameState {
    pub code: Vec<u8>,
    pub lasti: u32,
    pub locals: ObjId,  // 独立的 locals dict
}
```

### 3. 创建独立的 locals dict
**修改**: `snapshot.rs` 的 `dump_checkpoint_frames` 函数

**关键实现**:
```rust
// STEP 1: 为每个 frame 创建独立的 locals dict
let mut locals_dicts = Vec::new();
for (_idx, (frame, _resume_lasti)) in frames.iter().enumerate() {
    let locals_dict = vm.ctx.new_dict();  // 新建独立 dict
    
    // 直接从 fastlocals 复制
    let varnames = &frame.code.code.varnames;
    let fastlocals = frame.fastlocals.lock();
    for (idx, varname) in varnames.iter().enumerate() {
        if let Some(value) = &fastlocals[idx] {
            locals_dict.set_item(*varname, value.clone(), vm)?;
        }
    }
    
    // 复制 cell/free vars（闭包变量）
    if !frame.code.code.cellvars.is_empty() || !frame.code.code.freevars.is_empty() {
        // ... 复制闭包变量
    }
    
    locals_dicts.push(locals_dict);
}

// STEP 2: 创建容器一次性序列化
let globals = &frames[0].0.globals;
let mut container_items = vec![globals.clone().into()];
for locals_dict in locals_dicts.iter() {
    container_items.push(locals_dict.clone().into());
}
let container = vm.ctx.new_tuple(container_items);

// 一次性完成两阶段序列化
let mut writer = SnapshotWriter::new(vm);
writer.serialize_obj(&container.into())?;

// 获取各个对象的 ID
let root = writer.get_id(&globals.as_object().to_owned())?;
for locals_dict in locals_dicts.iter() {
    let locals_id = writer.get_id(&locals_dict.clone().into())?;
    // ... 使用 locals_id
}
```

**为什么这样做**:
1. **独立性**: 每个 frame 有自己的 locals dict，互不影响
2. **正确性**: 直接从 fastlocals 复制，确保所有局部变量都被捕获
3. **一致性**: 使用容器一次性序列化，避免多次调用 `serialize_obj` 的问题

### 4. 修复 lasti 验证逻辑
**修改**: `checkpoint.rs` 的 `save_checkpoint_bytes_from_frames` 函数

```rust
// 只对最内层（最后一个）frame 验证和计算 resume_lasti
for (idx, frame) in frames.iter().enumerate() {
    let is_innermost = idx == frames.len() - 1;
    let resume_lasti = if is_innermost {
        // 对于最内层 frame，使用已验证的 lasti
        if let Some(lasti) = innermost_resume_lasti {
            lasti
        } else {
            compute_resume_lasti(vm, frame)?
        }
    } else {
        // 对于外层 frames，直接使用当前 lasti
        frame.lasti()
    };
    // ...
}
```

### 5. Resume 时恢复 fastlocals
**修改**: `checkpoint.rs` 的 `resume_script_from_bytes` 函数

```rust
for (i, frame_state) in state.frames.iter().enumerate() {
    // 解码 code 和 locals
    let code_obj = vm.ctx.new_pyref(PyCode::new(code));
    let locals_dict = PyDictRef::try_from_object(vm, locals_obj)?;
    
    // 创建 frame
    let scope = Scope::with_builtins(
        Some(ArgMapping::from_dict_exact(locals_dict.clone())),
        globals_dict.clone(),
        vm
    );
    let frame = Frame::new(code_obj.clone(), scope, ...);
    
    // 关键：恢复 fastlocals
    let varnames = &code_obj.code.varnames;
    let mut fastlocals = frame.fastlocals.lock();
    for (idx, varname) in varnames.iter().enumerate() {
        if let Some(value) = locals_dict.get_item_opt(*varname, vm)? {
            fastlocals[idx] = Some(value);  // 恢复局部变量
        }
    }
    drop(fastlocals);
    
    frame.set_lasti(frame_state.lasti);
    frame_refs.push(frame);
}

// 重建 frame stack
for frame in frame_refs.iter() {
    vm.frames.borrow_mut().push(frame.clone());
}

// 运行最内层 frame
vm.run_frame(frame_refs.last().unwrap().clone())
```

## 向后兼容性

修改保持了向后兼容：

1. **CheckpointState 解码**:
```rust
// 如果遇到旧格式（没有 frames 字段），自动转换
let frames = if let Some(frames_data) = frames_data {
    frames_data
} else {
    // 旧格式：单个 frame
    vec![FrameState {
        code: code.ok_or_else(|| SnapshotError::msg("missing code"))?,
        lasti: lasti.ok_or_else(|| SnapshotError::msg("missing lasti"))?,
        locals: root,  // 旧格式中 locals == globals
    }]
};
```

2. **保留旧的 API**:
- `dump_checkpoint_state` 仍然存在，用于单 frame 场景
- 新增 `dump_checkpoint_frames` 用于多 frame 场景

## 测试结果

### 测试1：函数内 checkpoint
```python
def foo(x):
    print(f"x={x}")
    checkpoint("test.rpsnap")  # ✅ 成功
    print(f"After checkpoint: x={x}")  # ✅ x 正确恢复
    return x * 2
```

### 测试2：复杂场景（actor_complex_demo.py）
```python
def stage_function(state, messages):
    state["history"].append({"stage": "function"})
    checkpoint("demo.rpsnap")  # ✅ 在函数内成功
    state["history"].append({"resume": True})  # ✅ state 正确恢复
```

## 修改文件列表

1. **crates/vm/src/vm/snapshot.rs**
   - 修改 `CheckpointState` 结构
   - 添加 `FrameState` 结构
   - 新增 `dump_checkpoint_frames` 函数
   - 修改 `encode_checkpoint_state` 和 `decode_checkpoint_state`

2. **crates/vm/src/vm/checkpoint.rs**
   - 修改 `save_checkpoint` 函数
   - 新增 `save_checkpoint_with_lasti` 函数
   - 修改 `save_checkpoint_bytes_from_frames` 函数
   - 修改 `resume_script_from_bytes` 函数
   - 更新 `validate_frame_for_checkpoint` 函数

3. **crates/vm/src/frame.rs**
   - 修改 checkpoint 触发逻辑

4. **crates/compiler-source/src/lib.rs**
   - 修复编译错误（添加 `PositionEncoding` 参数）

## 关键技术点

1. **Frame Stack 管理**: 需要保存和恢复整个调用栈
2. **Locals Dict 独立性**: 每个 frame 必须有独立的 locals dict
3. **Fastlocals 同步**: 序列化时从 fastlocals 复制，恢复时写回 fastlocals
4. **一次性序列化**: 使用容器对象避免多次 `serialize_obj` 调用
5. **Lasti 验证**: 只对最内层 frame 进行 PopTop 检查

## 未来改进

1. ~~删除 `IS_OPTIMIZED` 检查~~（已支持）
2. ~~支持闭包变量 (cellvars/freevars)~~（已实现）
3. 支持生成器/协程的 checkpoint
4. 优化大型 frame stack 的序列化性能
5. 添加更多测试用例

## 已知限制与解决方案

### Block Stack 相关限制

**限制**：在某些控制流结构内部创建 checkpoint 暂不完全支持，包括：
- 循环体内（`for` 或 `while`）
- try/except 块内部

**原因**：
1. `for` 循环会在栈上创建迭代器对象（如 `range_iterator`, `list_iterator`等），这些迭代器的内部状态是 Rust 级别的，无法正确序列化/反序列化
2. 这些控制流结构涉及 VM 的 block stack，当前实现未完整保存/恢复这些状态

**解决方案**：将 checkpoint 放在这些结构的外部

```python
# ❌ 不支持 - 循环内 checkpoint
for item in items:
    checkpoint()  # 会失败
    process(item)

# ✅ 推荐 - 在循环前后checkpoint
checkpoint()  # 循环前保存
for item in items:
    process(item)
checkpoint()  # 循环后保存
```

```python
# ❌ 不支持 - while 循环内 checkpoint
i = 0
while i < len(items):
    checkpoint()  # 会失败
    process(items[i])
    i += 1

# ✅ 推荐 - 分段处理
# 将长循环拆分为多个阶段，在阶段之间checkpoint
def process_batch(items, start, end):
    for i in range(start, end):
        process(items[i])

checkpoint()
process_batch(items, 0, 100)
checkpoint()
process_batch(items, 100, 200)
checkpoint()
```

```python
# ❌ 不支持 - try/except 内部 checkpoint
try:
    checkpoint()  # 会失败
    risky_operation()
except Exception as e:
    checkpoint()  # 也会失败
    handle_error(e)

# ✅ 推荐 - 在 try/except 之外checkpoint
checkpoint()
try:
    risky_operation()
except Exception as e:
    handle_error(e)
checkpoint()  # try/except 完成后
```

### 其他注意事项

- 文件句柄、网络连接等外部资源无法通过 checkpoint 保存
- 线程和异步任务状态不支持保存
- C 扩展模块的内部状态可能无法完全恢复

## 总结

通过这次修复，PVM 的 checkpoint/resume 功能从"玩具级别"提升到了"可用级别"：

### ✅ 支持的功能
- 在函数内创建 checkpoint
- 在条件语句（if/else）内创建 checkpoint
- 在 try/except 语句**之外**创建 checkpoint
- 正确保存和恢复局部变量
- 支持调用栈（嵌套函数调用）
- 保持向后兼容
- 支持闭包变量

### ✅ 已解决的限制（v2.0 更新）

**Block Stack 支持已完成！** 详见 [Block_Stack_Checkpoint_Support.md](./Block_Stack_Checkpoint_Support.md)

- ✅ while 循环内的 checkpoint 完全支持
- ✅ try/except/finally 块内部的 checkpoint 完全支持
- ✅ 函数内 checkpoint（多 frame）完全支持

### ⚠️ 当前限制

- **For 循环使用 enumerate()**: 由于 iterator 对象序列化问题，部分场景不支持
  - 临时解决方案：使用 while 循环代替

### 📝 最佳实践

现在可以在几乎所有场景下使用 checkpoint：

```python
# 完全支持的 checkpoint 位置
def main_process():
    checkpoint()  # ✅ 函数入口
    
    result1 = step1()
    checkpoint()  # ✅ 步骤之间
    
    # 循环内 checkpoint - 现已支持！
    i = 0
    while i < len(items):
        process(items[i])
        checkpoint()  # ✅ 循环内
        i += 1
    
    # try/except 内 checkpoint - 现已支持！
    try:
        checkpoint()  # ✅ try 块内
        risky_operation()
    except Exception as e:
        checkpoint()  # ✅ except 块内
        handle_error(e)
    
    checkpoint()  # ✅ 最终状态
```

PVM 现在具备产品级的 checkpoint/resume 能力，适用于：
- 复杂的长时间处理任务
- 多阶段交易处理流程
- Actor 模型的状态管理
- 需要细粒度状态保存的应用

