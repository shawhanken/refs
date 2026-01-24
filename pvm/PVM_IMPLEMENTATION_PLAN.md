# PVM 下一步实施方案

**制定日期**: 2026-01-24  
**依据文档**: 
- Cowboy 核心技术白皮书
- PVM 真实完成度评估报告（35-40%）
- EVM vs PVM 架构对比分析
- 功能设计与 Continuation 机制文档

---

## 📊 执行摘要

### 当前状态（基于源代码审查）
- **真实完成度**: 35-40%
- **核心基础**: 96.8%（Python解释器、Checkpoint/Resume、HostApi）
- **确定性执行**: 50.0%（致命缺陷：SoftFloat缺失、ordered_set缺失）
- **Continuation**: 62.5%（FSM编译器代码存在但默认未启用）
- **Runner系统**: 85%（✅ 链下Runner节点完整实现，✅ 执行器完整，✅ 验证系统完整，⚠️ 待链上集成）
- **高级特性**: 30.0%（大部分缺失）

### 源代码验证的关键发现
1. **SoftFloat**: `Lib/pvm_sdk/types.py` 只是字符串包装，`crates/vm/src/builtins/float.rs` 使用硬件浮点
2. **ordered_set**: 完全未实现，`crates/vm/src/builtins/set.rs` 使用不确定的哈希表
3. **FSM编译器**: `CompileOpts::default()` 中 `pvm_fsm: false`，需要根据 `continuation_mode` 启用
4. **Guard机制**: `Lib/pvm_sdk/continuation.py` 中只有数据存储，`load_cont()` 无验证逻辑
5. **Dual Gas**: `HostApi` trait 只有单一 `charge_gas()`，无 Cycles/Cells 分离
6. **Runner系统**: ✅ **链下Runner系统已完整实现**（独立代码库 `runner/`），包括：
   - ✅ Runner Node 核心框架（任务监听、执行调度、健康检查）
   - ✅ Chain Client（完整的 JSON-RPC 2.0 通信协议）
   - ✅ HTTP Executor（完整实现，支持数据提取、源证明）
   - ✅ LLM Executor（OpenAI、Anthropic 支持）
   - ✅ Result Verifier（6种验证模式全部实现）
   - ✅ Runner Registry、Job Dispatcher、Result Verifier（链上组件接口）
   - ⚠️ **待完成**：链上 System Actors 集成（需要 Chain 端实现）

### 关键差距
1. 🔴 **致命风险**: SoftFloat缺失 → 跨架构共识失败
2. ✅ **Runner系统**: 链下部分已完成（85%），⚠️ **待链上集成** → 需要 Chain 端实现 System Actors
3. 🔴 **易用性差**: FSM编译器未启用 → 开发者体验差
4. ⚠️ **确定性风险**: ordered_set缺失 → 集合迭代顺序不确定

### 目标完成度
- **6个月后**: 90%（所有P0/P1任务完成）
- **里程碑**: M1(4周) → M2(6周) → M3(16周) → M4(20周) → M5(24周)

---

## 🎯 第一阶段：致命风险修复（0-4周）

### 优先级：🔴 P0 - 必须立即完成

#### 1.1 SoftFloat 集成（3-4周）

**问题描述**：
- 当前使用硬件浮点运算，x86和ARM结果可能不同
- 可能导致共识失败和链分叉
- 白皮书要求：所有浮点运算必须使用软件浮点库

**实施方案**：

**当前状态**：
- `Lib/pvm_sdk/types.py` 中 `SoftFloat` 只是字符串包装类，不是真正的实现
- `crates/pvm-runtime/src/determinism.rs` 中有 `enable_softfloat: bool` 字段，但默认是 `false`
- `crates/vm/src/builtins/float.rs` 中所有浮点运算直接使用硬件浮点（`f64`）
- `crates/vm/src/builtins/float.rs:392-423` 中 `AsNumber` trait 的实现直接使用 `a + b`, `a - b` 等硬件运算

**步骤1：依赖集成（1周）**
```toml
# crates/vm/Cargo.toml
[dependencies]
softfloat-wrapper = "0.3"
# 或使用 berkeley-softfloat-rs
```

**步骤2：VM集成（1-2周）**
```rust
// crates/vm/src/builtins/float.rs
use softfloat_wrapper::*;

// 需要修改 PyFloat::number_op 和 AsNumber trait 的实现
impl AsNumber for PyFloat {
    fn as_number() -> &'static PyNumberMethods {
        static AS_NUMBER: PyNumberMethods = PyNumberMethods {
            // 需要将所有硬件浮点运算替换为 SoftFloat
            add: Some(|a, b, vm| PyFloat::number_op(a, b, |a, b, _vm| {
                let a_sf = f64_to_softfloat(a);
                let b_sf = f64_to_softfloat(b);
                softfloat_to_f64(softfloat_add(a_sf, b_sf))
            }, vm)),
            // ... 其他运算类似
        };
        &AS_NUMBER
    }
}
```

**步骤3：数学库替换（1周）**
```rust
// crates/stdlib/src/math.rs
// 需要替换所有 math 模块函数使用 SoftFloat
// 当前实现直接使用 libm，需要改为 SoftFloat
pub fn sin(x: f64) -> f64 {
    softfloat_sin(f64_to_softfloat(x))
}
```

**步骤4：启用配置（1天）**
```rust
// crates/pvm-runtime/src/determinism.rs
impl Default for DeterminismOptions {
    fn default() -> Self {
        Self {
            enable_softfloat: true,  // ⚠️ 修改默认值
            // ...
        }
    }
}
```

**步骤4：测试验证（1周）**
- 跨平台一致性测试（x86_64, ARM64, RISC-V）
- 性能基准测试
- 回归测试

**验收标准**：
- ✅ 所有浮点运算使用SoftFloat
- ✅ 跨平台测试通过（位级一致性）
- ✅ 性能影响 < 20%
- ✅ 所有现有测试通过

**工作量**: 3-4周（1人）

---

#### 1.2 ordered_set 实现（1-2周）

**问题描述**：
- Python的`set`迭代顺序不确定
- 白皮书要求：提供`ordered_set`类型替代内置`set`

**实施方案**：

**当前状态**：
- 完全没有实现
- `crates/vm/src/builtins/set.rs` 中使用的是 `dict_inner::Dict<()>`，基于哈希表，迭代顺序不确定
- `PySetInner::iter()` 返回的迭代器顺序依赖于哈希表内部结构

**步骤1：实现ordered_set类型（1周）**
```rust
// crates/vm/src/builtins/ordered_set.rs
use indexmap::IndexSet;

#[pyclass(module = false, name = "ordered_set")]
pub struct PyOrderedSet {
    items: IndexSet<PyObjectRef>,
}

impl PyOrderedSet {
    pub fn new() -> Self {
        Self {
            items: IndexSet::new(),
        }
    }
    
    pub fn add(&mut self, item: PyObjectRef) {
        self.items.insert(item);
    }
    
    pub fn iter(&self) -> impl Iterator<Item = &PyObjectRef> {
        self.items.iter()
    }
}
```

**步骤2：替换内置set（3天）**
```rust
// crates/vm/src/builtins/set.rs
// 选项A：在编译期将 `set` 语法替换为 `ordered_set`
// 选项B：修改 PySet 内部实现，使用 IndexSet 而不是 Dict
// 推荐选项B，因为不需要修改Python语法
pub type SetContentType = IndexSet<PyObjectRef>;  // 替换 dict_inner::Dict<()>
```

**步骤3：CBOR序列化支持（2天）**
```rust
// ordered_set 序列化为有序数组
impl CborSerialize for PyOrderedSet {
    fn serialize(&self) -> Vec<u8> {
        // 按插入顺序序列化
    }
}
```

**步骤4：测试验证（2天）**
- 迭代顺序确定性测试
- 序列化一致性测试

**验收标准**：
- ✅ `set`自动替换为`ordered_set`
- ✅ 迭代顺序确定性
- ✅ 序列化结果一致
- ✅ 性能影响 < 10%

**工作量**: 1-2周（1人）

---

#### 1.3 FSM 编译器启用（1-2周）

**问题描述**：
- FSM编译器代码完整（500+行），但默认未启用
- 开发者必须手动设置`pvm_fsm: true`
- 白皮书要求：`@runner.continuation`自动编译为状态机

**实施方案**：

**当前状态**：
- `crates/codegen/src/compile.rs:124` 中 `CompileOpts` 的 `pvm_fsm` 字段默认是 `false`
- `crates/vm/src/vm/mod.rs:527` 中 `compile_opts()` 方法根据 `continuation_mode` 设置 `pvm_fsm`：
  ```rust
  pvm_fsm: matches!(
      self.state.config.settings.continuation_mode,
      Some(setting::ContinuationMode::Fsm)
  )
  ```
- 默认情况下 `continuation_mode` 是 `None`，所以 `pvm_fsm` 默认是 `false`

**步骤1：修改默认配置（1天）**
```rust
// 选项A：修改 CompileOpts 默认值
// crates/codegen/src/compile.rs
impl Default for CompileOpts {
    fn default() -> Self {
        Self {
            pvm_fsm: true,  // ⚠️ 修改默认值
            optimize: 2,
        }
    }
}

// 选项B：修改 VM 的 compile_opts() 方法（推荐）
// crates/vm/src/vm/mod.rs
pub fn compile_opts(&self) -> crate::compiler::CompileOpts {
    crate::compiler::CompileOpts {
        optimize: self.state.config.settings.optimize,
        pvm_fsm: true,  // ⚠️ 默认启用，除非显式禁用
    }
}
```

**步骤2：链上集成启用（2天）**
```rust
// 如果使用选项B，链上代码不需要修改
// 如果使用选项A，需要在链上显式设置
// chain/src/execution.rs
let compile_opts = CompileOpts {
    pvm_fsm: true,  // 显式启用（如果使用选项A）
    optimize: 2,
};
```

**步骤3：完整测试（1周）**
- 端到端FSM编译测试
- Continuation resume测试
- 性能基准测试

**验收标准**：
- ✅ FSM编译器默认启用
- ✅ `@runner.continuation`自动转换
- ✅ 所有continuation测试通过
- ✅ 性能影响可接受

**工作量**: 1-2周（1人）

---

### 第一阶段里程碑：M1 - 确定性修复完成（4周）

**标志**：
- ✅ SoftFloat集成完成
- ✅ ordered_set实现完成
- ✅ FSM编译器默认启用

**完成度提升**: 35-40% → **50%**

---

## 🚀 第二阶段：Runner系统实现（4-16周）

### 优先级：🔴 P0 - 核心创新

### ✅ 当前实现状态（2026-01-24更新）

**链下Runner系统已完成（85%）**：

#### ✅ 已完成组件

1. **✅ Runner Node 核心框架** (`crates/runner-node/`)
   - ✅ 任务监听循环（轮询链上任务）
   - ✅ 任务执行调度
   - ✅ 健康检查和心跳机制
   - ✅ 执行器注册表
   - ✅ 启动时连接测试和智能日志

2. **✅ Chain Client** (`crates/chain-client/`)
   - ✅ 完整的 JSON-RPC 2.0 协议实现
   - ✅ System Actor 地址和方法定义
   - ✅ 带重试机制的 RPC 调用
   - ✅ 超时和错误处理
   - ✅ 任务获取、结果提交、注册、心跳接口

3. **✅ HTTP Executor** (`crates/runner-http/`)
   - ✅ HTTP 请求执行（GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS）
   - ✅ 数据提取（CSS 选择器、XPath、JSONPath、正则表达式）
   - ✅ 源证明生成（TLS 证书指纹、响应哈希）
   - ✅ 新鲜度检查框架

4. **✅ LLM Executor** (`crates/runner-llm/`)
   - ✅ OpenAI API 集成（GPT-3.5、GPT-4 等）
   - ✅ Anthropic API 集成（Claude 系列）
   - ✅ 资源计量（输入/输出 tokens、执行时间）
   - ✅ 响应格式验证框架
   - ⚠️ 本地模型支持（接口已定义，待实现）

5. **✅ Result Verifier** (`crates/result-verifier/`)
   - ✅ None 模式
   - ✅ Economic Bond 模式
   - ✅ Majority Vote 模式（N-of-M 投票）
   - ✅ Structured Match 模式（JSON Schema、字段匹配、数值容差）
   - ✅ Deterministic 模式（精确匹配 + TEE）
   - ✅ Semantic Similarity 模式（嵌入向量相似度）

6. **✅ 链上组件接口**（已实现，待 Chain 端集成）
   - ✅ Runner Registry (`crates/runner-registry/`) - Runner 注册、费率卡、健康检查、VRF 选择
   - ✅ Job Dispatcher (`crates/job-dispatcher/`) - 任务分发、Runner 选择、任务队列
   - ✅ Result Verifier (`crates/result-verifier/`) - 结果验证和共识聚合
   - ✅ Secrets Manager (`crates/secrets-manager/`) - 密钥管理接口
   - ✅ TEE Verifier (`crates/tee-verifier/`) - TEE 证明验证接口

7. **✅ 其他组件**
   - ✅ Runner Consensus (`crates/runner-consensus/`) - N-of-M 共识客户端框架
   - ✅ TEE Runtime (`crates/runner-tee/`) - TEE 运行时接口
   - ✅ Runner Common (`crates/runner-common/`) - 共享类型、错误、加密工具

#### ⚠️ 待完成工作

1. **链上 System Actors 集成**（需要 Chain 端实现）
   - [ ] 实现 `chain_callActor` RPC 方法
   - [ ] 部署 Runner Registry System Actor
   - [ ] 部署 Job Dispatcher System Actor
   - [ ] 部署 Result Verifier System Actor
   - [ ] 实现任务路由和结果回调机制

2. **Runner 端增强**（可选）
   - [ ] 本地模型支持（ONNX、llama.cpp）
   - [ ] TEE 环境集成（SGX、TDX、SEV）
   - [ ] P2P 网络通信
   - [ ] 结果缓存机制

#### 2.1 Runner执行器基础 ✅ **已完成**

**实现状态**：
- ✅ Runner Node 守护进程框架已实现
- ✅ 任务执行框架已实现（ExecutorRegistry + JobExecutor trait）
- ✅ LLM 执行器已实现（OpenAI、Anthropic）
- ✅ HTTP 执行器已实现（完整功能）

**实际代码位置**：
- `crates/runner-node/src/node.rs` - Runner Node 核心
- `crates/runner-node/src/config.rs` - 配置管理
- `crates/runner-llm/src/executor.rs` - LLM 执行器
- `crates/runner-http/src/executor.rs` - HTTP 执行器
- `crates/runner-common/src/executor.rs` - 执行器抽象

**验收标准**：
- ✅ Runner守护进程可以启动
- ✅ 可以监听链上任务（轮询机制）
- ✅ LLM任务可以执行
- ✅ HTTP任务可以执行
- ✅ 结果可以提交回链（接口已实现）

**工作量**: ~~4-5周（2人）~~ ✅ **已完成**

---

#### 2.2 验证和共识模块 ✅ **已完成**

**实现状态**：
- ✅ Result Verifier 完整实现（6种验证模式）
- ✅ N-of-M 投票机制已实现
- ✅ 验证器函数库已实现（JSON Schema、字段匹配、数值容差等）
- ✅ TEE 验证接口已定义（`crates/tee-verifier/`）

**实际代码位置**：
- `crates/result-verifier/src/verifier.rs` - 验证逻辑实现
- `crates/result-verifier/src/modes.rs` - 验证模式定义
- `crates/tee-verifier/src/verifier.rs` - TEE 验证接口
- `crates/runner-consensus/src/` - 共识客户端框架

**已实现的验证模式**：
1. ✅ **None** - 无验证
2. ✅ **Economic Bond** - 经济担保
3. ✅ **Majority Vote** - 多数投票（N-of-M）
4. ✅ **Structured Match** - 结构化匹配（JSON Schema、字段匹配、数值容差）
5. ✅ **Deterministic** - 确定性验证（精确匹配 + TEE）
6. ✅ **Semantic Similarity** - 语义相似度（嵌入向量相似度计算）

**验收标准**：
- ✅ N-of-M投票机制工作
- ✅ 所有验证模式支持
- ✅ TEE验证接口已定义（待 TEE 环境集成）
- ⚠️ 争议解决机制（框架已定义，待完善）

**工作量**: ~~3-4周（2人）~~ ✅ **已完成**

---

#### 2.3 Chain集成 ⚠️ **待Chain端实现**

**问题描述**：
- Runner任务需要路由到Runner网络
- Runner结果需要路由回Actor
- 需要超时和重试机制

**Runner端已完成**：
- ✅ Chain Client 完整实现（`crates/chain-client/`）
- ✅ RPC 通信协议完整（JSON-RPC 2.0）
- ✅ System Actor 地址和方法定义
- ✅ 任务获取、结果提交、注册、心跳接口

**Chain端待实现**：

**步骤1：Runner注册表**（需要Chain端实现）
```rust
// chain/src/runner_registry.rs
// 可以使用 runner-registry crate 的实现作为参考
pub struct RunnerRegistry {
    runners: HashMap<RunnerId, RunnerInfo>,
}

impl RunnerRegistry {
    pub fn select_runners(&self, job: &RunnerJob) -> Vec<RunnerId> {
        // 1. 按entitlements过滤
        // 2. 按价格过滤
        // 3. VRF选择委员会
        // 参考：crates/runner-registry/src/registry.rs
    }
}
```

**步骤2：任务路由**（需要Chain端实现）
```rust
// chain/src/runner_router.rs
pub struct RunnerRouter {
    registry: RunnerRegistry,
    job_queue: JobQueue,
}

impl RunnerRouter {
    pub async fn route_job(&self, job: RunnerJob) -> Result<()> {
        // 1. 选择runners（使用 Runner Registry）
        // 2. 将任务分配给选中的runners（更新任务状态）
        // 3. Runner通过轮询获取任务（已实现）
        // 4. Runner提交结果（已实现）
        // 5. 验证和共识（使用 Result Verifier）
        // 6. 路由结果回Actor（通过消息）
    }
}
```

**步骤3：结果路由和Resume**（需要Chain端实现）
```rust
// chain/src/execution.rs
pub async fn handle_runner_result(&self, result: RunnerResult) -> Result<()> {
    // 1. 验证结果（使用 Result Verifier）
    // 2. 加载continuation状态
    // 3. Resume continuation
    // 4. 执行resume handler
}
```

**步骤4：超时和重试**（需要Chain端实现）
```rust
// chain/src/runner_timeout.rs
pub struct RunnerTimeout {
    pending_jobs: HashMap<JobId, PendingJob>,
}

impl RunnerTimeout {
    pub async fn handle_timeout(&self, job_id: JobId) -> Result<()> {
        // 1. 标记任务超时
        // 2. 触发Actor超时handler
        // 3. 清理状态
    }
}
```

**验收标准**：
- [ ] Runner注册和管理工作（Chain端）
- [ ] 任务路由工作（Chain端）
- [ ] 结果路由回Actor工作（Chain端）
- [ ] 超时机制工作（Chain端）
- [ ] Continuation resume工作（Chain端）
- ✅ Runner端接口已完整实现

**工作量**: ~~3-4周（2人）~~ ⚠️ **待Chain端实现**（Runner端已完成）

---

### 第二阶段里程碑：M3 - Runner Alpha ✅ **链下部分已完成**

**标志**：
- ✅ Runner执行器可用（已完成）
- ✅ LLM/HTTP基础可用（已完成）
- ✅ 验证和共识完成（已完成）
- ⚠️ Chain集成待实现（需要Chain端实现System Actors）

**完成度提升**: 50% → **65%**（链下Runner系统完成，待Chain集成后达到70%）

**说明**：
- Runner系统链下部分（85%）已完整实现，包括所有执行器、验证系统、RPC通信
- 待Chain端实现System Actors和任务路由机制后，Runner系统即可完全可用
- Runner端代码已准备好与Chain集成，只需Chain端实现对应的RPC端点

---

## 🛡️ 第三阶段：核心功能完善（16-20周）

### 优先级：⚠️ P1 - 重要但可延后

#### 3.1 Guard机制实现（2-3周）

**问题描述**：
- 当前只有数据存储，无验证逻辑
- 白皮书要求：`guard_unchanged`防止状态冲突

**实施方案**：

**当前状态**：
- `Lib/pvm_sdk/continuation.py:119-134` 中 `save_cont()` 函数保存了 `guard_unchanged` 数据
- `Lib/pvm_sdk/continuation.py:137-146` 中 `load_cont()` 函数只是返回数据，**没有验证逻辑**
- `crates/pvm-runtime/src/guard.rs` 文件实际上是 `determinism.rs` 的内容（导入错误），不是真正的guard机制

**步骤1：实现Guard验证逻辑（1周）**
```rust
// 新建文件：crates/pvm-runtime/src/guard_validator.rs
use crate::host::HostApi;
use sha2::{Sha256, Digest};

pub struct GuardValidator;

impl GuardValidator {
    pub fn snapshot(host: &dyn HostApi, keys: &[&[u8]]) -> Result<HashMap<Vec<u8>, [u8; 32]>, HostError> {
        let mut hashes = HashMap::new();
        for key in keys {
            let value = host.state_get(key)?
                .unwrap_or_default();
            let hash = Self::hash_value(&value);
            hashes.insert(key.to_vec(), hash);
        }
        Ok(hashes)
    }
    
    pub fn verify(
        host: &dyn HostApi,
        saved_hashes: &HashMap<Vec<u8>, [u8; 32]>
    ) -> Result<(), HostError> {
        for (key, saved_hash) in saved_hashes {
            let current_value = host.state_get(key)?
                .unwrap_or_default();
            let current_hash = Self::hash_value(&current_value);
            
            if current_hash != *saved_hash {
                return Err(HostError::Forbidden);  // StateConflictError
            }
        }
        Ok(())
    }
    
    fn hash_value(value: &[u8]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(value);
        hasher.finalize().into()
    }
}
```

**步骤2：集成到Continuation（1周）**
```python
# Lib/pvm_sdk/continuation.py
def load_cont(cid):
    raw = pvm_host.get_state(_cont_key(cid))
    if raw is None:
        raise RuntimeError("continuation state missing")
    data = _decode_json(raw)
    ctx = _decode_value(data.get("ctx") or {})
    data["ctx"] = Capture.from_dict(ctx)
    
    # ⚠️ 新增：验证 guard_unchanged
    if "guard_unchanged" in data:
        guard_keys = data["guard_unchanged"]
        if guard_keys:
            # 调用 Rust 端的验证逻辑
            if not pvm_host.verify_guard(guard_keys, data.get("guard_hashes")):
                raise StateConflictError("guard values changed")
    
    return data
```

**步骤2：Object-level Guard（1周）**
```rust
// Lib/pvm_sdk/storage.py
class GuardedValue:
    def __init__(self, value, hash):
        self._value = value
        self._hash = hash
    
    @property
    def value(self):
        # 访问时触发验证
        if self._hash != compute_hash(self._value):
            raise StateConflictError()
        return self._value
```

**步骤3：集成到Continuation（1周）**
```rust
// 在continuation save时snapshot
// 在continuation resume时verify
```

**验收标准**：
- ✅ Decorator guard工作（在 `load_cont` 时验证）
- ✅ Object guard工作（可选，如果实现）
- ✅ StateConflictError抛出（映射到 `HostError::Forbidden`）
- ✅ 所有测试通过

**工作量**: 2-3周（1人）

**注意**：需要修改 `Lib/pvm_sdk/continuation.py` 中的 `load_cont()` 函数，添加验证逻辑。如果使用Rust实现验证，需要在 `pvm_host` 模块中添加 `verify_guard()` 函数。

---

#### 3.2 Dual Gas模型实现（2-3周）

**问题描述**：
- 当前只有单一Gas模型
- 白皮书要求：Cycles（计算）+ Cells（数据）独立计费

**实施方案**：

**当前状态**：
- `crates/pvm-host/src/lib.rs:100-101` 中 `HostApi` trait 只有单一的 `charge_gas()` 和 `gas_left()`
- `crates/pvm-alto/src/lib.rs:92-102` 中实现也是单一Gas模型
- 没有分离的 Cycles 和 Cells 计量

**步骤1：扩展HostApi trait（3天）**
```rust
// crates/pvm-host/src/lib.rs
pub trait HostApi {
    // 保留原有方法以保持兼容性
    fn charge_gas(&mut self, amount: u64) -> HostResult<()>;
    fn gas_left(&self) -> u64;
    
    // 新增双Gas方法
    fn charge_cycles(&mut self, amount: u64) -> HostResult<()>;
    fn charge_cells(&mut self, amount: u64) -> HostResult<()>;
    fn cycles_left(&self) -> u64;
    fn cells_left(&self) -> u64;
}
```

**步骤2：实现DualGasMeter（1周）**
```rust
// crates/pvm-host/src/gas.rs
pub struct DualGasMeter {
    cycles: u64,
    cells: u64,
    cycles_limit: u64,
    cells_limit: u64,
}

impl DualGasMeter {
    pub fn new(cycles_limit: u64, cells_limit: u64) -> Self {
        Self {
            cycles: cycles_limit,
            cells: cells_limit,
            cycles_limit,
            cells_limit,
        }
    }
    
    pub fn charge_cycles(&mut self, amount: u64) -> Result<(), HostError> {
        if amount > self.cycles {
            return Err(HostError::OutOfGas);
        }
        self.cycles -= amount;
        Ok(())
    }
    
    pub fn charge_cells(&mut self, amount: u64) -> Result<(), HostError> {
        if amount > self.cells {
            return Err(HostError::OutOfGas);
        }
        self.cells -= amount;
        Ok(())
    }
}
```

**步骤3：HostApi实现映射（1周）**
```rust
// crates/pvm-host/src/lib.rs 的实现
impl HostApi for CowboyHost {
    // 兼容性：charge_gas 映射到 charge_cycles
    fn charge_gas(&mut self, amount: u64) -> HostResult<()> {
        self.charge_cycles(amount)
    }
    
    fn gas_left(&self) -> u64 {
        self.cycles_left()  // 返回 cycles 作为兼容
    }
    
    // 新方法
    fn charge_cycles(&mut self, amount: u64) -> HostResult<()> {
        self.dual_gas.charge_cycles(amount)
    }
    
    fn charge_cells(&mut self, amount: u64) -> HostResult<()> {
        self.dual_gas.charge_cells(amount)
    }
    
    fn state_set(&mut self, key: &[u8], value: &[u8]) -> HostResult<()> {
        // 存储操作 → Cells
        let cells = value.len() as u64;
        self.charge_cells(cells)?;
        // ... 实际存储
    }
}
```

**步骤3：EIP-1559费用市场（1周）**
```rust
// chain/src/fee_market.rs
pub struct FeeMarket {
    cycles_basefee: u64,
    cells_basefee: u64,
}

impl FeeMarket {
    pub fn adjust_basefee(&mut self, usage: &GasUsage) {
        // EIP-1559调整逻辑
        self.cycles_basefee = adjust(self.cycles_basefee, usage.cycles);
        self.cells_basefee = adjust(self.cells_basefee, usage.cells);
    }
}
```

**验收标准**：
- ✅ Cycles和Cells独立计量
- ✅ EIP-1559费用市场工作
- ✅ 所有操作正确计费
- ✅ 测试通过

**工作量**: 2-3周（1人）

---

### 第三阶段里程碑：M4 - Runner Beta（20周）

**标志**：
- ✅ Guard机制完成
- ✅ Dual Gas模型完成
- ✅ 所有P1任务完成

**完成度提升**: 70% → **80%**

---

## 🎨 第四阶段：高级特性（20-24周）

### 优先级：🟡 P2 - 可延后

#### 4.1 Timer协议调度（3-4周）

**问题描述**：
- 当前只有基础API，无协议级调度
- 白皮书要求：分层日历队列、Gas出价代理、速率限制

**实施方案**：
- 实现分层日历队列
- 实现Gas出价代理（GBA）
- 实现定时器速率限制
- 实现DoS防护

**工作量**: 3-4周（2人）

---

#### 4.2 Actor async调用（2-3周）

**问题描述**：
- 当前不支持Actor间异步调用
- 白皮书要求：`ActorRef.async_<method>()`支持

**实施方案**：
- 实现ActorRef类型
- 实现async方法调用
- 实现消息路由和resume

**工作量**: 2-3周（1人）

---

### 第四阶段里程碑：M5 - 生产就绪（24周）

**标志**：
- ✅ 所有P0/P1任务完成
- ✅ 安全审计通过
- ✅ 完整测试和文档

**完成度提升**: 80% → **90%**

---

## 📅 时间线和资源分配

### 并行化策略

**第一批（并行，0-4周）**：
- SoftFloat集成（4周，1人）
- ordered_set实现（2周，1人）
- FSM编译器启用（2周，1人）

**第二批（并行，4-16周）**：
- ✅ Runner执行器（已完成，链下部分85%）
- ⚠️ Chain集成（待Chain端实现，4周，2人）
- Guard验证逻辑（3周，1人）
- Dual Gas模型（3周，1人）

**第三批（并行，16-20周）**：
- Timer协议调度（4周，2人）
- Actor async调用（3周，1人）

**第四批（20-24周）**：
- 完整测试和文档（4周，2人）

### 总时间线

```
周次    任务
─────────────────────────────────────
0-4     第一阶段：致命风险修复
4-16    第二阶段：Runner系统实现
16-20   第三阶段：核心功能完善
20-24   第四阶段：高级特性 + 测试
─────────────────────────────────────
总计：24周（6个月）
```

### 资源需求

| 阶段 | 人员 | 持续时间 | 总人周 | 说明 |
|------|------|---------|--------|------|
| 第一阶段 | 3人 | 4周 | 12人周 | 致命风险修复 |
| 第二阶段 | 4人 | 12周 | 32人周 | ✅ Runner链下部分已完成（-16人周），⚠️ Chain集成待实现（+4周） |
| 第三阶段 | 2人 | 4周 | 8人周 | 核心功能完善 |
| 第四阶段 | 3人 | 4周 | 12人周 | 高级特性 |
| **总计** | - | 24周 | **64人周** | Runner链下部分已完成，节省16人周 |

---

## 🎯 关键里程碑

| 里程碑 | 时间 | 标志 | 完成度 |
|--------|------|------|--------|
| **M1: 确定性修复** | 4周 | SoftFloat、ordered_set完成 | 50% |
| **M2: FSM可用** | 6周 | FSM默认启用，测试通过 | 55% |
| **M3: Runner Alpha** | 16周 | ✅ 链下部分已完成，⚠️ 待Chain集成 | 65%（链下85%，待Chain集成后70%） |
| **M4: Runner Beta** | 20周 | 验证和共识完成 | 80% |
| **M5: 生产就绪** | 24周 | 所有P0/P1完成，审计通过 | 90% |

---

## ⚠️ 风险评估和缓解

### 高风险项

1. **SoftFloat性能影响**
   - **风险**: 性能下降 > 50%
   - **缓解**: 性能基准测试，必要时优化

2. **Runner系统复杂度**
   - **风险**: ~~开发时间超期~~ ✅ **已缓解**：链下Runner系统已完成（85%）
   - **剩余风险**: Chain端集成复杂度
   - **缓解**: Runner端接口已完整，Chain端只需实现System Actors和RPC端点

3. **共识安全性**
   - **风险**: 升级导致共识失败
   - **缓解**: 完整测试，渐进式升级，快速回滚

### 中风险项

1. **FSM编译器兼容性**
   - **风险**: 现有代码不兼容
   - **缓解**: 特性开关，向后兼容

2. **Guard机制性能**
   - **风险**: 状态检查开销大
   - **缓解**: 优化哈希计算，缓存结果

---

## 📋 验收标准

### 每个阶段验收

1. **代码审查**: 所有代码经过peer review
2. **测试覆盖**: 单元测试覆盖率 ≥ 80%
3. **集成测试**: 所有集成测试通过
4. **性能测试**: 性能影响在可接受范围内
5. **文档更新**: 相关文档已更新

### 最终验收

1. **功能完整性**: 所有P0/P1功能实现
2. **测试完整性**: 测试覆盖率 ≥ 80%
3. **安全审计**: 通过第三方安全审计
4. **文档完整性**: 所有文档更新完成
5. **性能基准**: 性能指标达标

---

## 🔗 相关文档

- **核心技术白皮书**: `whitepaper/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md`
- **真实完成度评估**: `pvm/PVM_REAL_COMPLETENESS_ASSESSMENT.md`
- **功能设计文档**: `pvm/02-功能设计与Continuation.md`
- **测试评估文档**: `pvm/05-测试评估与升级.md`
- **架构对比分析**: `pvm/EVM_VS_PVM_ARCHITECTURAL_COMPARISON.md`

---

## 📝 总结

本实施方案基于Cowboy核心技术白皮书和当前PVM真实完成度评估，制定了6个月的详细开发计划。关键要点：

1. **立即行动**: 修复致命风险（SoftFloat、ordered_set）
2. **核心创新**: 实现Runner系统（核心价值主张）
3. **渐进式**: 分阶段、小步快跑、及时验证
4. **质量保证**: 测试驱动、代码审查、安全审计

**预计6个月后，PVM完成度从35-40%提升到90%，达到生产就绪状态。**

---

---

## 📝 文档修正说明

**修正日期**: 2026-01-24  
**修正原因**: 基于源代码审查，修正实施方案中的偏差

### 主要修正内容

1. **SoftFloat实现状态**：
   - ✅ 确认 `Lib/pvm_sdk/types.py` 只是字符串包装
   - ✅ 确认 `crates/vm/src/builtins/float.rs` 使用硬件浮点
   - ✅ 添加了 `enable_softfloat` 配置启用步骤

2. **ordered_set实现状态**：
   - ✅ 确认完全未实现
   - ✅ 确认 `crates/vm/src/builtins/set.rs` 使用不确定的哈希表
   - ✅ 修正了实现方案，建议修改 `PySet` 内部实现

3. **FSM编译器默认配置**：
   - ✅ 确认 `CompileOpts::default()` 中 `pvm_fsm: false`
   - ✅ 确认 `vm.compile_opts()` 根据 `continuation_mode` 设置
   - ✅ 提供了两种启用方案（修改默认值 vs 修改VM方法）

4. **Guard机制实现状态**：
   - ✅ 确认 `crates/pvm-runtime/src/guard.rs` 实际是确定性执行代码
   - ✅ 确认 `Lib/pvm_sdk/continuation.py` 中只有数据存储，无验证逻辑
   - ✅ 修正了实现方案，需要在 `load_cont()` 中添加验证

5. **Dual Gas模型状态**：
   - ✅ 确认 `HostApi` trait 只有单一 `charge_gas()`
   - ✅ 修正了实现方案，需要扩展 trait 并保持向后兼容

6. **Runner系统实现状态**（2026-01-24重大更新）：
   - ✅ **链下Runner系统已完整实现**（独立代码库 `runner/`，完成度85%）
   - ✅ Runner Node 核心框架已实现（`crates/runner-node/`）
   - ✅ Chain Client 完整实现（JSON-RPC 2.0 协议，`crates/chain-client/`）
   - ✅ HTTP Executor 完整实现（数据提取、源证明，`crates/runner-http/`）
   - ✅ LLM Executor 完整实现（OpenAI、Anthropic，`crates/runner-llm/`）
   - ✅ Result Verifier 完整实现（6种验证模式，`crates/result-verifier/`）
   - ✅ 链上组件接口已实现（Runner Registry、Job Dispatcher、Result Verifier）
   - ⚠️ **待完成**：Chain端System Actors集成（需要Chain端实现RPC端点和任务路由）

### 源代码审查方法

- 使用 `codebase_search` 查找关键实现
- 使用 `grep` 查找相关代码位置
- 直接读取关键文件验证实现状态
- 对比白皮书要求确认差距

---

**文档版本**: 1.2  
**制定日期**: 2026-01-24  
**修正日期**: 2026-01-24  
**更新日期**: 2026-01-24（Runner系统实现状态更新）  
**维护者**: PVM开发团队

### 更新说明（2026-01-24）

**Runner系统实现状态重大更新**：

1. **完成度更新**：从 5% 提升到 **85%**（链下部分）
2. **已完成组件**：
   - ✅ Runner Node 核心框架
   - ✅ Chain Client（完整 RPC 协议）
   - ✅ HTTP Executor（完整实现）
   - ✅ LLM Executor（OpenAI、Anthropic）
   - ✅ Result Verifier（6种验证模式）
   - ✅ 链上组件接口（Runner Registry、Job Dispatcher、Result Verifier）

3. **待完成工作**：
   - ⚠️ Chain端System Actors集成（需要Chain端实现RPC端点和任务路由）

4. **工作量调整**：
   - 第二阶段：从 48人周 减少到 32人周（节省16人周）
   - 总工作量：从 80人周 减少到 64人周

5. **里程碑状态**：
   - M3（Runner Alpha）：链下部分已完成，待Chain集成后达到70%完成度
