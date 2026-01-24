# PVM Checkpoint/Resume 实现指南

**最后更新**: 2026-01-24

---

## 📋 概述

本文档提供 PVM Checkpoint/Resume 功能的完整实现指南，包括函数级支持、Block Stack 支持、文件/Bytes API 等。

---

## 🔧 函数级 Checkpoint 支持

### 问题描述

原始 PVM 的 checkpoint/resume 功能存在严重限制：
1. **只支持模块级别** - 无法在函数、循环、条件语句、异常处理块内创建 checkpoint
2. **无法恢复局部变量** - resume 时函数的局部变量丢失，导致 `UnboundLocalError`
3. **无法处理调用栈** - 只保存单个 frame，无法处理嵌套调用

### 解决方案

#### 1. 移除 frame 数量限制

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

#### 2. 修改 CheckpointState 结构

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

// 修改后：支持多个 frames
pub(crate) struct CheckpointState {
    pub version: u32,
    pub frames: Vec<FrameState>,  // 多个 frames
    pub root: ObjId,
    pub objects: Vec<ObjectEntry>,
}
```

#### 3. 修复局部变量序列化

**问题**: `frame.locals()` 返回的可能是共享的 globals dict，导致所有 frame 序列化时使用同一个 dict。

**解决方案**: 为每个函数 frame 创建独立的 locals dict，复制 fastlocals 的值。

---

## 🔄 Block Stack Checkpoint/Resume 支持

### 问题背景

在实现函数级 checkpoint 支持后，发现程序在以下场景会出现问题：
1. **在 while 循环中设置 checkpoint**：恢复后会 panic，提示 "No more blocks to pop!"
2. **在 for 循环中设置 checkpoint**：恢复后会出现 iterator 相关错误
3. **在 try/except 块中设置 checkpoint**：恢复后异常无法被正确捕获

### 根本原因

RustPython VM 使用内部的 **Block Stack** 来管理控制流：
- **Loop blocks**: 管理 while/for 循环的 break/continue
- **TryExcept blocks**: 管理异常处理的跳转
- **Finally blocks**: 管理 finally 块的执行
- **ExceptHandler/FinallyHandler**: 管理异常处理器的状态

原始的 checkpoint 实现只保存了：
- Code object（字节码）
- Instruction pointer (lasti)
- Local variables
- Value stack

**缺失的关键部分**：
- ❌ Block stack（控制流栈）
- ❌ Block 中的 UnwindReason（返回/异常/break/continue）
- ❌ Exception references（异常对象）

### 解决方案

#### 核心数据结构

```rust
#[derive(Debug, Clone)]
pub(crate) struct BlockState {
    pub typ: BlockTypeState,
    pub level: usize,  // Stack level when block was pushed
}

#[derive(Debug, Clone)]
pub(crate) enum BlockTypeState {
    Loop,
    TryExcept { handler: u32 },  // Handler bytecode address
    Finally { handler: u32 },
    FinallyHandler { 
        reason: Option<UnwindReasonState>, 
        prev_exc: Option<ObjId>  // Previous exception
    },
    ExceptHandler { 
        prev_exc: Option<ObjId> 
    },
}

#[derive(Debug, Clone)]
pub(crate) enum UnwindReasonState {
    Returning { value: ObjId },      // Function return with value
    Raising { exception: ObjId },    // Exception being raised
    Break { target: u32 },           // Loop break to target
    Continue { target: u32 },        // Loop continue to target
}
```

#### FrameState 扩展

```rust
pub(crate) struct FrameState {
    pub code: Vec<u8>,           // Marshaled code object
    pub lasti: u32,              // Instruction pointer
    pub locals: ObjId,           // Local variables dict
    pub stack: Vec<ObjId>,       // Value stack
    pub blocks: Vec<BlockState>, // Block stack (NEW!)
}
```

---

## 💾 Checkpoint 文件模式 + Bytes API

### 设计目标

在保留原有文件快照模式的基础上，新增纯 bytes 形式的快照 API，便于链上存储与传输。

### 总体设计

- **保留文件模式**：`save_checkpoint`/`save_checkpoint_from_exec` 继续写入文件。
- **新增 bytes API**：`save_checkpoint_bytes`/`save_checkpoint_bytes_from_exec` 直接返回 `Vec<u8>`，并新增 `resume_script_from_bytes` 以 bytes 形式恢复。
- **快照格式**：自定义 Canonical CBOR，支持全对象图序列化（含循环引用），版本号升级为 `v3`。
- **代码对象来源**：恢复时使用快照内的 `marshal` 编码的 code bytes，而不是重新编译脚本。

### 数据结构

#### CheckpointState

```rust
pub(crate) struct CheckpointState {
    pub version: u32,
    pub source_path: String,
    pub lasti: u32,
    pub code: Vec<u8>,        // marshal 序列化后的 CodeObject
    pub root: ObjId,          // 全局 globals 的对象 id
    pub objects: Vec<ObjectEntry>,  // 对象表
}
```

#### ObjectEntry

```rust
pub(crate) struct ObjectEntry {
    pub tag: ObjTag,
    pub payload: ObjectPayload,
}
```

### CBOR 结构与确定性编码

- **CheckpointState**：CBOR map，字段按 canonical 顺序写出。
  - `version` `source_path` `lasti` `code` `root` `objects`
- **ObjectEntry**：CBOR array，形如 `[tag, payload]`。
- **Dict/Set/FrozenSet 的确定性排序**：
  - key 先编码为 tagged CBOR（`[tag, value]`），支持 `None/Bool/Int/Float/Str/Bytes/Tuple`；
  - 以 `(encoded_len, encoded_bytes)` 排序后再写入。

### 关键序列化策略

- **对象图 ID**：使用对象指针地址作为 key，先分配 `ObjId` 再序列化 payload，可处理循环引用。
- **键排序**：dict/set/frozenset 的 key 先使用 tagged CBOR 编码，再按 `(len, bytes)` 排序以保证确定性。
- **CodeObject**：使用 `marshal::serialize_code` 保存；恢复时用 `PyObjBag(&vm.ctx)` 还原 `CodeObject<Literal>`。

---

## 🔧 实现挑战

### Block Stack 实现挑战

#### 挑战 1：Block 类型多样性
- Loop、TryExcept、Finally、ExceptHandler、FinallyHandler 等不同类型
- 每种类型需要不同的序列化策略

#### 挑战 2：异常对象序列化
- 异常对象可能包含复杂的堆栈信息
- 需要正确保存和恢复异常状态

#### 挑战 3：UnwindReason 处理
- Return、Raise、Break、Continue 等不同原因
- 需要正确恢复控制流

### 解决方案

1. **统一的状态表示**：使用 `BlockTypeState` 枚举统一表示所有 block 类型
2. **对象引用管理**：使用 `ObjId` 管理对象引用，避免循环引用问题
3. **确定性序列化**：使用 Canonical CBOR 确保序列化结果一致

---

## 📝 使用约束（当前实现）

- 仅支持顶层模块帧；不支持嵌套帧与活动 block stack（**已修复**）
- 不支持 closures/freevars 与 optimized locals
- `checkpoint()` 必须作为单独语句使用，要求下一条 opcode 为 `PopTop`
- 快照仅覆盖 Python 对象图（无文件/网络/线程/外部句柄）

---

## 🔗 相关文档

- **API 参考与使用指南** (`01-API参考与使用指南.md`) - API 详细说明
- **功能设计与 Continuation** (`02-功能设计与Continuation.md`) - Continuation 机制
- **编码规范与最佳实践** (`04-编码规范与最佳实践.md`) - 编码规范

---

## ⚠️ 实现状态

### 已完成 ✅
- 函数级 Checkpoint 支持
- Block Stack 序列化支持
- Checkpoint File/Bytes API
- 循环和异常处理支持

### 待完善 ⏳
- Closures/freevars 支持
- Optimized locals 支持
- 更复杂的控制流场景

---

**文档版本**: 1.0  
**最后更新**: 2026-01-24
