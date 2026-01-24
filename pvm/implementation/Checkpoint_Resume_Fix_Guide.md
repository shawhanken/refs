# PVM Checkpoint/Resume 功能修复指南

> 本文档记录了 PVM (Python Virtual Machine) checkpoint/resume 功能从段错误到完全可用的完整修复过程，包含技术细节、解决方案和未来参考。

## 📋 目录

1. [问题描述](#问题描述)
2. [核心概念](#核心概念)
3. [问题根因分析](#问题根因分析)
4. [解决方案](#解决方案)
5. [技术细节](#技术细节)
6. [修改文件清单](#修改文件清单)
7. [测试验证](#测试验证)
8. [未来优化建议](#未来优化建议)

---

## 问题描述

### 初始症状

```bash
$ pvm --resume examples/breakpoint_resume_demo/demo.rpsnap examples/breakpoint_resume_demo/demo.py
# 结果：段错误 (Segmentation fault - exit code 139)
```

### 错误演进

1. **初期错误**：`ValueError: checkpoint restore failed: Message("closure invalid")`
   - 问题：闭包对象的 ObjId 被覆盖
   
2. **中期错误**：`ValueError: checkpoint restore failed: Message("cycle detected while restoring object 11")`
   - 问题：循环引用导致无限递归
   
3. **后期错误**：各种类型映射和模块查找失败
   - 问题：Python 2/3 兼容性、类型名称不匹配

---

## 核心概念

### 1. Python 对象图序列化

Python 对象之间通过引用形成复杂的对象图，包含：
- **直接引用**：对象 A 直接持有对象 B 的引用
- **循环引用**：对象 A 引用 B，B 又引用 A
- **共享引用**：多个对象引用同一个对象

### 2. 两阶段序列化/反序列化

为了正确处理对象图中的循环引用和共享引用，必须采用两阶段策略：

**序列化阶段**：
- **Phase 1 (assign_ids_phase)**：遍历对象图，为每个对象分配唯一 ID
- **Phase 2 (build_payloads_phase)**：基于已分配的 ID，构建对象的实际数据

**反序列化阶段**：
- **Phase 1 (restore_entry)**：创建对象的"骨架"（使用临时/默认值）
- **Phase 2 (fill_container)**：填充对象的实际内容（使用真实引用）

### 3. ObjId 系统

- `ObjId` 是 `u32` 类型的唯一标识符
- 每个被序列化的对象都必须有唯一的 ObjId
- 在恢复时，通过 ObjId 引用其他对象，避免重复恢复

### 4. 特殊对象类型

某些 Python 对象类型由于其特殊性，无法或不应该被序列化：
- **临时对象**：迭代器、生成器
- **系统对象**：弱引用、方法绑定
- **不可重建**：某些 C 扩展对象

---

## 问题根因分析

### 1. 单阶段序列化的缺陷

**原始实现**：在构建 payload 的同时分配 ID

```rust
// 错误示例
fn build_payload(&mut self, obj: &PyObjectRef) -> Result<ObjectPayload, Error> {
    match obj_tag {
        ObjTag::Type => {
            // 在这里创建新对象（如 attributes dict）
            let attrs_dict = create_attrs_dict();  // 新对象！
            let dict_id = self.get_or_assign_id(&attrs_dict)?; // 问题：ID 顺序被打乱
            // ...
        }
    }
}
```

**问题**：
1. 动态创建的对象（如类型的 `__dict__`）没有预先分配 ID
2. ID 分配顺序不确定，导致后续引用失效
3. 循环引用无法正确处理

### 2. 循环引用导致的无限递归

```rust
// Type A 引用 Type B
// Type B 引用 Type A
fn restore_type(type_obj) {
    for base in type_obj.bases {
        let base = self.get_obj(base_id)?;  // 递归！
        // 如果 base 又引用回当前类型，导致无限递归
    }
}
```

### 3. 类型系统不匹配

Python 内置类型在不同模块中的名称不一致：
- `builtins.code` 实际是 `types.CodeType`
- `thread` 模块在 Python 3 中是 `_thread`
- `builtins.weakref` 实际在 `weakref` 模块中

---

## 解决方案

### 方案架构

```
序列化流程：
┌─────────────────┐
│ Phase 1:        │
│ assign_ids      │  → 遍历对象图，分配所有 ObjId
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Phase 2:        │
│ build_payloads  │  → 构建实际数据（引用已分配的 ID）
│                 │
└─────────────────┘

反序列化流程：
┌─────────────────┐
│ Phase 1:        │
│ restore_entry   │  → 创建对象骨架（临时数据）
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Phase 2:        │
│ fill_container  │  → 填充真实内容（使用 get_obj 获取引用）
│                 │
└─────────────────┘
```

### 关键策略

#### 1. 缓存动态创建的对象

```rust
pub struct SnapshotWriter<'vm> {
    vm: &'vm VirtualMachine,
    id_map: HashMap<usize, ObjId>,
    // 缓存 Phase 1 中创建的临时对象
    type_attr_dicts: HashMap<ObjId, PyDictRef>,      // Type 的 __dict__
    instance_data: HashMap<ObjId, InstanceData>,     // Instance 的 state
    // ...
}

impl SnapshotWriter {
    fn assign_ids_phase(&mut self, obj: &PyObjectRef) -> Result<(), Error> {
        match tag {
            ObjTag::Type => {
                // 提前创建并缓存 attributes dict
                let attrs_dict = get_type_attrs_dict(obj);
                self.type_attr_dicts.insert(id, attrs_dict.clone());
                self.assign_ids_phase(&attrs_dict.into())?;  // 递归访问
            }
        }
    }
}
```

#### 2. 两阶段 Type 对象恢复

```rust
// Phase 1: restore_entry - 创建 Type 对象
ObjectPayload::Type(payload) => {
    // 使用临时 bases（避免循环引用）
    let temp_bases = vec![self.vm.ctx.types.object_type.to_owned()];
    let empty_attrs = PyAttributes::default();  // 空 attributes
    
    let typ = PyType::new_heap(
        payload.name.as_str(),
        temp_bases,      // 临时！
        empty_attrs,     // 临时！
        slots,
        metatype,
        &self.vm.ctx,
    )?;
    typ_obj
}

// Phase 2: fill_container - 填充真实数据
ObjectPayload::Type(payload) => {
    let typ = obj.downcast_ref::<PyType>()?;
    
    // 填充真实的 bases
    if !payload.bases.is_empty() {
        let bases = payload.bases.iter()
            .map(|id| self.get_obj(*id)?.downcast::<PyType>())
            .collect::<Result<Vec<_>, _>>()?;
        *typ.bases.write() = bases;
    }
    
    // 填充真实的 attributes
    let attrs = build_type_attributes(self, payload.dict, idx)?;
    for (key, value) in attrs.iter() {
        typ.attributes.write().insert(key.clone(), value.clone());
    }
}
```

#### 3. 类型映射表

```rust
fn lookup_module(vm: &VirtualMachine, name: &str) -> Result<PyObjectRef, Error> {
    // 模块名映射
    let actual_name = match name {
        "thread" => "_thread",
        "_os" => "posix",
        _ => name,
    };
    // ...
}

fn restore_builtin_type(module: &str, name: &str) -> Result<PyObjectRef, Error> {
    // 类型名映射
    let (actual_module, actual_name) = match (module, name) {
        ("thread", "lock") => ("_thread", "LockType"),
        ("builtins", "code") => ("types", "CodeType"),
        ("builtins", "weakref") => ("weakref", "ref"),
        ("builtins", "cell") => ("types", "CellType"),
        ("builtins", "method") => ("types", "MethodType"),
        ("builtins", "NoneType") => ("types", "NoneType"),
        // ... 更多映射
        _ => (module, name),
    };
    // ...
}
```

#### 4. 不可恢复对象处理

```rust
// 检测不可恢复的类型
if type_name == "weakref" 
    || type_name == "weakproxy" 
    || type_name == "method"
    || type_name == "slice"
    || type_name.ends_with("_iterator")
    || type_name.ends_with("_descriptor")
    || type_name.ends_with("-wrapper")
    || type_name.starts_with("dict_")  // dict_keys, dict_values
    || type_name == "generator"
    || type_name == "coroutine"
{
    // 使用 None 或占位符替代
    return Ok(self.vm.ctx.none());
}
```

---

## 技术细节

### 1. 递归深度限制

为防止栈溢出，设置最大递归深度：

```rust
const MAX_DEPTH: usize = 100_000;

fn assign_ids_phase(&mut self, obj: &PyObjectRef) -> Result<(), Error> {
    if self.depth > MAX_DEPTH {
        return Err(SnapshotError::msg(
            format!("Recursion depth exceeded at {} objects", self.id_map.len())
        ));
    }
    self.depth += 1;
    // ... 处理对象
    self.depth -= 1;
    Ok(())
}
```

### 2. _Feature 类的特殊处理

Python 的 `__future__` 模块中的 `_Feature` 类在调用 `__getstate__` 时会挂起：

```rust
fn get_state(&mut self, obj: &PyObjectRef) -> Result<Option<PyObjectRef>, Error> {
    let class = obj.class();
    
    // 特殊处理 _Feature 类
    if class.name() == "_Feature" {
        // 跳过 __getstate__，使用 __dict__ 或 None
        return Ok(obj.dict().map(|d| d.into()));
    }
    
    // 正常处理其他类
    if let Some(getstate) = vm.get_attribute_opt(obj.clone(), "__getstate__")? {
        let state = getstate.call((), vm)?;
        return Ok(Some(state));
    }
    
    Ok(obj.dict().map(|d| d.into()))
}
```

### 3. BuiltinFunction 的 __self__ 处理

内置方法的 `__self__` 属性需要在 Phase 1 访问：

```rust
fn visit_children(&mut self, obj: &PyObjectRef, tag: ObjTag) -> Result<(), Error> {
    match tag {
        ObjTag::BuiltinFunction => {
            // 访问 __self__ 属性（如果存在）
            if let Ok(self_obj) = obj.get_attr("__self__", self.vm) {
                self.assign_ids_phase(&self_obj)?;
            }
        }
        // ...
    }
}
```

### 4. 状态恢复的 None 处理

某些对象的 state 可能是 None：

```rust
fn apply_instance_state(&mut self, idx: usize) -> Result<(), Error> {
    let state = self.get_obj(state_id)?;
    
    // state 可能是 None
    if self.vm.is_none(&state) {
        return Ok(());
    }
    
    // 尝试调用 __setstate__
    if let Some(setstate) = self.vm.get_attribute_opt(instance.clone(), "__setstate__")? {
        setstate.call((state,), self.vm)?;
        return Ok(());
    }
    
    // 否则，直接更新 __dict__
    if let Some(dict) = instance.dict() {
        let state_dict = PyDictRef::try_from_object(self.vm, state)?;
        for (key, value) in &state_dict {
            dict.set_item(&*key, value, self.vm)?;
        }
    }
    
    Ok(())
}
```

---

## 修改文件清单

### 1. `crates/compiler-source/src/lib.rs`

**修改原因**：修复编译错误

```rust
// 添加导入
pub use ruff_source_file::{LineIndex, OneIndexed as LineNumber, PositionEncoding, SourceLocation};

// 修改方法调用
pub fn source_location(&self, offset: TextSize) -> SourceLocation {
    self.index.source_location(offset, self.text, PositionEncoding::Utf8)
}
```

### 2. `crates/vm/src/vm/snapshot.rs` (主要修改)

**修改内容**：

#### A. 数据结构扩展

```rust
pub struct SnapshotWriter<'vm> {
    // 原有字段...
    
    // 新增缓存
    type_attr_dicts: HashMap<ObjId, PyDictRef>,
    instance_data: HashMap<ObjId, InstanceData>,
    depth: usize,
}

struct InstanceData {
    new_args: Option<PyObjectRef>,
    new_kwargs: Option<PyObjectRef>,
    state: Option<PyObjectRef>,
}
```

#### B. 序列化流程重构

```rust
// 原：单次遍历
fn serialize_obj(obj: &PyObjectRef) -> Result<Vec<ObjectEntry>, Error> {
    let mut entries = Vec::new();
    visit_and_build(obj, &mut entries)?;  // 同时分配 ID 和构建 payload
    Ok(entries)
}

// 新：两阶段
fn serialize_obj(obj: &PyObjectRef) -> Result<Vec<ObjectEntry>, Error> {
    // Phase 1: 分配所有 ID
    self.assign_ids_phase(obj)?;
    
    // Phase 2: 构建所有 payload
    let entries = self.build_payloads_phase()?;
    
    Ok(entries)
}
```

#### C. Type 对象处理

- `restore_entry` 中创建空 Type
- `fill_container` 中填充 bases 和 attributes

#### D. 类型映射

添加 20+ 类型映射规则：
- 模块映射：`thread` → `_thread`，`_os` → `posix`
- 类型映射：`builtins.code` → `types.CodeType` 等
- 特殊函数：`builtins.maketrans` → `str.maketrans`

#### E. 不可恢复对象

识别并替换不可恢复的对象类型

**修改行数**：约 500+ 行修改/新增

### 3. 删除的临时文件

- `test_closure.py`
- `test_simple.py`
- `test_print.py`
- `test_resume_simple.py`

---

## 测试验证

### 1. 基础功能测试

```bash
# 测试脚本
$ cat > test_resume.py << 'EOF'
import rustpython_checkpoint as rpc
import os

x = 42
y = [1, 2, 3]
print(f"Before checkpoint: x={x}, y={y}")

CHECKPOINT_PATH = "test_resume.rpsnap"
rpc.checkpoint(CHECKPOINT_PATH)

print("=== RESUMED ===")
print(f"After resume: x={x}, y={y}")

if os.path.exists(CHECKPOINT_PATH):
    os.remove(CHECKPOINT_PATH)
    print("Checkpoint file removed")
EOF

# 运行测试
$ pvm test_resume.py
$ pvm --resume test_resume.rpsnap test_resume.py

# 预期输出
=== RESUMED ===
After resume: x=42, y=[1, 2, 3]
Checkpoint file removed
```

### 2. 复杂场景测试

```bash
# Demo 示例（包含多次 checkpoint）
$ pvm examples/breakpoint_resume_demo/demo.py
# 第一次运行，创建 checkpoint #1

$ pvm --resume examples/breakpoint_resume_demo/demo.rpsnap examples/breakpoint_resume_demo/demo.py
# 从 checkpoint #1 恢复，创建 checkpoint #2

$ pvm --resume examples/breakpoint_resume_demo/demo.rpsnap examples/breakpoint_resume_demo/demo.py
# 从 checkpoint #2 恢复，完成执行
```

### 3. 验证点

- ✅ 变量状态正确恢复
- ✅ 执行流程从 checkpoint 后继续
- ✅ 无段错误或内存泄漏
- ✅ Checkpoint 文件正确清理
- ✅ 支持多次 checkpoint/resume 循环

---

## 未来优化建议

### 1. 性能优化

**当前问题**：
- 对象图遍历需要两次完整遍历
- 递归深度可能限制处理超大对象图

**优化方向**：
```rust
// 使用迭代而非递归
fn assign_ids_iterative(&mut self, root: &PyObjectRef) {
    let mut stack = vec![root.clone()];
    while let Some(obj) = stack.pop() {
        if self.has_id(&obj) {
            continue;
        }
        let id = self.assign_id(&obj);
        // 将子对象压入栈
        stack.extend(self.get_children(&obj));
    }
}

// 并行处理独立的对象子图
use rayon::prelude::*;
fn serialize_parallel(&mut self) {
    self.object_groups.par_iter()
        .map(|group| self.serialize_group(group))
        .collect()
}
```

### 2. 类型系统完善

**当前问题**：
- 硬编码的类型映射表
- 新类型需要手动添加映射

**优化方向**：
```rust
// 自动检测和映射
fn auto_resolve_type(module: &str, name: &str, vm: &VirtualMachine) -> Option<PyObjectRef> {
    // 1. 尝试原始模块
    if let Ok(obj) = try_get_type(vm, module, name) {
        return Some(obj);
    }
    
    // 2. 查询类型注册表
    if let Some(mapping) = TYPE_REGISTRY.get(&(module, name)) {
        return try_get_type(vm, mapping.0, mapping.1).ok();
    }
    
    // 3. 尝试常见的替代模块
    for alt_module in ["types", "builtins", "collections.abc"] {
        if let Ok(obj) = try_get_type(vm, alt_module, name) {
            // 自动学习并缓存这个映射
            TYPE_REGISTRY.insert((module.to_string(), name.to_string()), 
                               (alt_module.to_string(), name.to_string()));
            return Some(obj);
        }
    }
    
    None
}
```

### 3. 错误恢复机制

**当前问题**：
- 恢复失败会导致整个过程失败
- 某些对象丢失可能是可接受的

**优化方向**：
```rust
pub struct RestoreOptions {
    pub ignore_missing_types: bool,
    pub replace_invalid_with_none: bool,
    pub continue_on_error: bool,
}

fn restore_with_options(&mut self, opts: &RestoreOptions) -> Result<RestoreReport, Error> {
    let mut report = RestoreReport::new();
    
    for (idx, entry) in self.entries.iter().enumerate() {
        match self.restore_entry(idx) {
            Ok(_) => report.success += 1,
            Err(e) if opts.continue_on_error => {
                report.errors.push((idx, e));
                self.objects[idx] = Some(self.vm.ctx.none());  // 使用占位符
            }
            Err(e) => return Err(e),
        }
    }
    
    Ok(report)
}
```

### 4. 增量 Checkpoint

**优化目标**：减少 checkpoint 文件大小和创建时间

```rust
pub struct IncrementalCheckpoint {
    base_snapshot: SnapshotFile,
    delta: Vec<ObjectDelta>,
}

struct ObjectDelta {
    obj_id: ObjId,
    changes: Vec<FieldChange>,
}

// 只序列化自上次 checkpoint 以来改变的对象
fn create_delta_checkpoint(&mut self, prev: &SnapshotFile) -> IncrementalCheckpoint {
    let mut delta = Vec::new();
    
    for obj in &self.tracked_objects {
        if has_changed(obj, prev) {
            delta.push(compute_delta(obj, prev));
        }
    }
    
    IncrementalCheckpoint {
        base_snapshot: prev.clone(),
        delta,
    }
}
```

### 5. 调试和诊断工具

```rust
// Checkpoint 文件分析工具
pub fn analyze_checkpoint(path: &Path) -> CheckpointReport {
    CheckpointReport {
        total_objects: usize,
        object_type_distribution: HashMap<String, usize>,
        largest_objects: Vec<(ObjId, String, usize)>,
        circular_references: Vec<Vec<ObjId>>,
        problematic_types: Vec<String>,
    }
}

// 可视化对象图
pub fn visualize_object_graph(snapshot: &Snapshot) -> String {
    // 生成 DOT 格式的图
    // 可用 Graphviz 渲染
}
```

---

## 经验总结

### 关键教训

1. **循环引用处理是核心**
   - 必须采用两阶段策略
   - 不能在构建过程中动态分配 ID

2. **类型系统复杂度被低估**
   - Python 类型在不同版本、不同模块中的差异
   - 需要完善的映射机制

3. **某些对象不应该被序列化**
   - 识别临时对象、系统对象
   - 提供合理的占位符策略

4. **充分的调试信息至关重要**
   - 在开发阶段保留详细的 DEBUG 输出
   - 便于快速定位问题

### 开发建议

1. **渐进式测试**
   - 从简单对象开始（int, str, list）
   - 逐步增加复杂度（closure, class, module）
   - 最后测试边界情况

2. **使用测试用例驱动**
   - 为每个发现的问题创建最小复现用例
   - 保留测试用例用于回归测试

3. **代码审查重点**
   - 检查所有 ID 分配的时机
   - 确认对象图遍历的完整性
   - 验证循环引用的处理

---

## 参考资料

### 相关文档

- [PVM Checkpoint 文件格式规范](./PVM_Checkpoint_File_Bytes_API_CN.md)
- [从源仓库同步代码](./Sync from source repo.md)

### 相关代码

- `crates/vm/src/vm/snapshot.rs` - 核心序列化/反序列化逻辑
- `crates/vm/src/vm/checkpoint.rs` - Checkpoint 文件 I/O
- `crates/vm/src/stdlib/rustpython_checkpoint.rs` - Python API
- `crates/vm/src/frame.rs` - Checkpoint 触发逻辑

### 外部参考

- Python pickle 模块实现
- RustPython 对象系统文档
- CBOR 序列化规范

---

**文档版本**：1.0  
**创建日期**：2024-12-30  
**最后更新**：2024-12-30  
**维护者**：PVM 开发团队

