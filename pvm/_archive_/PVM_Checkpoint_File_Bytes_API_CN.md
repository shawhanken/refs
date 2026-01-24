# PVM Checkpoint: 保留文件模式 + 新增 Bytes API（设计与实现说明）

## 目标与范围
- 目标：在保留原有文件快照模式的基础上，新增纯 bytes 形式的快照 API，便于链上存储与传输。
- 覆盖内容：设计选择、数据结构、序列化格式、恢复流程与代码改动点。

## 总体设计
- 保留文件模式：`save_checkpoint`/`save_checkpoint_from_exec` 继续写入文件。
- 新增 bytes API：`save_checkpoint_bytes`/`save_checkpoint_bytes_from_exec` 直接返回 `Vec<u8>`，并新增 `resume_script_from_bytes` 以 bytes 形式恢复。
- 快照格式：自定义 Canonical CBOR，支持全对象图序列化（含循环引用），版本号升级为 `v3`。
- 代码对象来源：恢复时使用快照内的 `marshal` 编码的 code bytes，而不是重新编译脚本。

## 使用约束（当前实现）
- 仅支持顶层模块帧；不支持嵌套帧与活动 block stack。
- 不支持 closures/freevars 与 optimized locals。
- `checkpoint()` 必须作为单独语句使用，要求下一条 opcode 为 `PopTop`。
- 快照仅覆盖 Python 对象图（无文件/网络/线程/外部句柄）。

## 数据结构（核心）

### CheckpointState
- `version: u32`
- `source_path: String`
- `lasti: u32`
- `code: Vec<u8>`（`rustpython_compiler_core::marshal` 序列化后的 CodeObject）
- `root: ObjId`（全局 globals 的对象 id）
- `objects: Vec<ObjectEntry>`（对象表）

### ObjectEntry
- `tag: ObjTag`
- `payload: ObjectPayload`

### ObjTag（CBOR 映射）
```
None=0, Bool=1, Int=2, Float=3, Str=4, Bytes=5,
List=6, Tuple=7, Dict=8, Set=9, FrozenSet=10,
Module=11, Function=12, Code=13, Type=14, BuiltinType=15,
Instance=16, Cell=17, BuiltinModule=18, BuiltinDict=19, BuiltinFunction=20
```

### ObjectPayload（关键变体）
- `Module { name, dict }`
- `BuiltinModule { name }`
- `BuiltinDict { name }`
- `Function(FunctionPayload)`
- `BuiltinFunction(BuiltinFunctionPayload)`
- `Type(TypePayload)`
- `BuiltinType { module, name }`
- `Instance(InstancePayload)`

### FunctionPayload
- `code, globals, defaults, kwdefaults, closure, name, qualname, annotations, module, doc, type_params`

### TypePayload
- `name, qualname, bases, dict, flags, basicsize, itemsize, member_count`

### InstancePayload
- `typ, state, new_args, new_kwargs`

### BuiltinFunctionPayload
- `name, module, self_obj`

## CBOR 结构与确定性编码
- CheckpointState：CBOR map，字段按 canonical 顺序写出。
  - `version` `source_path` `lasti` `code` `root` `objects`
- ObjectEntry：CBOR array，形如 `[tag, payload]`。
- payload 形态：
  - `None/Bool/Int/Float/Str/Bytes`：对应基础 CBOR 值（int 以十进制字符串存储）。
  - `List/Tuple/Set/FrozenSet`：CBOR array of `ObjId`。
  - `Dict`：CBOR array of `[key_id, value_id]`。
  - `Module/BuiltinModule/BuiltinDict/Function/BuiltinFunction/Type/BuiltinType/Instance`：CBOR map。
- Dict/Set/FrozenSet 的确定性排序：
  - key 先编码为 tagged CBOR（`[tag, value]`），支持 `None/Bool/Int/Float/Str/Bytes/Tuple`；
  - 以 `(encoded_len, encoded_bytes)` 排序后再写入。

## 关键序列化策略
- **对象图 ID**：使用对象指针地址作为 key，先分配 `ObjId` 再序列化 payload，可处理循环引用。
- **键排序**：dict/set/frozenset 的 key 先使用 tagged CBOR 编码，再按 `(len, bytes)` 排序以保证确定性。
- **支持键类型**：None/Bool/Int/Float/Str/Bytes/Tuple（递归）。
- **CodeObject**：使用 `marshal::serialize_code` 保存；恢复时用 `PyObjBag(&vm.ctx)` 还原 `CodeObject<Literal>`。
- **Function**：读取 `__code__/__globals__/__defaults__/__kwdefaults__/__closure__` 等，并在恢复时通过 `MakeFunctionFlags` 写回 defaults/kwdefaults/closure/annotations/type_params，再 set `__name__/__qualname__/__module__/__doc__`。
- **Type**：仅对 heap type 进行结构性恢复，记录 bases/dict/flags/slot sizes。恢复时使用 `PyType::new_heap`，再补 `__qualname__` 与包含 self 引用的属性。
  - 跳过属性：`getset/member/method/wrapper` descriptor（避免原生指针/slot 绑定失效）。
  - 含 self 的属性：在 `apply_deferred_type_attrs` 中二次设置。
- **BuiltinType**：仅保存 `(module, name)`，恢复时 `sys.modules[module].name`。
- **BuiltinModule/BuiltinDict**：不展开序列化，直接按 name 引用（目前 `builtins`/`sys`）。
- **BuiltinFunction**：
  - 绑定方法：保存 `self_obj + name`，恢复时 `getattr(self, name)`。
  - 普通内置函数：保存 `(module, name)`，恢复时 `getattr(module, name)`。
- **Instance**：
  - `__getnewargs_ex__`/`__getnewargs__` 生成构造参数；
  - 对 `classmethod`/`staticmethod`，使用 `__func__` 作为构造参数；
  - `__getstate__` 优先，否则取 `__dict__`。
  - 恢复：优先调用 `__new__` 构造实例；若 `__new__` 缺失或调用失败，则回退到 `object.__new__(typ)` 创建空实例；随后在统一的 `apply_instance_state` 阶段调用 `__setstate__` 或回填 `__dict__`（避免 `__init__` 产生副作用）。

## Bytes API 与文件模式 API

### 新增 bytes API
- `save_checkpoint_bytes(vm) -> Vec<u8>`
- `save_checkpoint_bytes_from_exec(vm, source_path, lasti, code, globals) -> Vec<u8>`
- `resume_script_from_bytes(vm, script_path, data)`

### 保留文件模式
- `save_checkpoint(vm, path)`：内部调用 `save_checkpoint_bytes_from_exec` 并 `fs::write`。
- `save_checkpoint_from_exec(vm, source_path, lasti, code, globals, path)`：同上。
- `resume_script_from_checkpoint(vm, script_path, checkpoint_path)`：`fs::read` 后调用 `resume_script_from_bytes`。

## 恢复流程摘要
1. 解码 CBOR → `CheckpointState`。
2. 反序列化对象表 → 先构建对象占位，再填充容器。
3. 对实例对象执行 `__setstate__` / `__dict__` 回填。
4. 通过 `root` 取得 globals dict。
5. `code` bytes → `CodeObject` → `PyCode`。
6. 创建 frame，并将 `lasti` 设为断点位置，执行 `run_frame`。

## 代码改动清单（文件级）
- `crates/vm/src/vm/snapshot.rs`
  - 新增完整对象图快照序列化/反序列化。
  - 定义 `CheckpointState`/`ObjTag`/`ObjectPayload` 等结构与 CBOR 编码。
  - 支持 builtin module/dict/function 的引用恢复。
  - 自定义 CBOR reader/writer，保证 canonical map/key 排序。
- `crates/vm/src/vm/checkpoint.rs`
  - 替换为 snapshot bytes 流程。
  - 增加 bytes API：`save_checkpoint_bytes*`、`resume_script_from_bytes`。
  - 保留文件模式并转为调用 bytes API。
  - 校验 `checkpoint()` 使用场景与栈状态。
- `crates/vm/src/frame.rs`
  - checkpoint 请求处理时传入 `code`，并写入 bytes（文件模式仍保留）。
  - `checkpoint_stack`/`restore_stack` 标注保留（`#[allow(dead_code)]`）。
- `crates/vm/src/vm/mod.rs`
  - 注册 `snapshot` 子模块。

## 约束与注意事项
- 目标环境不允许文件 IO 时，应只使用 bytes API。
- `__getstate__/__setstate__`、`__getnewargs_ex__`/`__getnewargs__` 需要由 Python 侧显式实现以保证自定义对象的正确恢复。
- 由于原生 descriptor（getset/member/method/wrapper）与 VM 内部 slot 绑定强相关，不参与序列化。
 - Builtin module/dict 仅按 name 引用；目前覆盖 `builtins`/`sys`。

## 与“保留文件模式 + 新增 bytes API”关联的关键点
- 文件模式未被移除，仅改为 bytes 底层实现（便于统一格式、降低分叉）。
- bytes API 是链上/沙箱环境的首选路径，可直接上链存储或通过 HostApi 传输。
- 新格式为 CBOR v3，向前不兼容旧的 marshal-dict 快照，恢复端必须匹配版本。
