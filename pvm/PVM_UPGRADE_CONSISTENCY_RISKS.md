# PVM 升级一致性风险分析

**文档版本**: 1.0  
**创建日期**: 2026-01-22  
**状态**: 风险评估  
**严重性**: 🔴 **致命**

---

## 📋 执行摘要

PVM 升级可能导致**严重的一致性风险**，威胁链的共识安全。本文档详细分析升级风险，并提供预防措施和升级策略。

### 核心风险

| 风险类型 | 发生概率 | 影响 | 严重性 |
|---------|---------|------|--------|
| **字节码格式变化** | 中 | 旧代码无法执行 | 🔴 致命 |
| **执行结果不一致** | 高 | 共识失败 | 🔴 致命 |
| **编译器行为变化** | 中 | 不同字节码 | ⚠️ 严重 |
| **VM 行为变化** | 中 | 执行结果不同 | ⚠️ 严重 |

---

## 🔴 第一部分：风险识别

### 1.1 字节码格式变化风险

#### 问题描述

PVM 升级可能导致字节码格式变化，使得旧代码无法在新版本上执行，或新代码无法在旧版本上执行。

#### 风险场景

**场景 1：编译器升级导致字节码格式变化**

```
PVM v0.1.3:
  Python 源代码 → 字节码格式 A

PVM v0.2.0（升级后）:
  Python 源代码 → 字节码格式 B（格式变化）
```

**影响**：
- ✅ 新部署的 Actor 使用新格式，可以执行
- 🔴 已部署的 Actor 使用旧格式，可能无法执行
- 🔴 如果字节码被序列化（Checkpoint），恢复时可能失败

**场景 2：PYC_MAGIC_NUMBER 变化**

```rust
// crates/vm/src/version.rs:134
pub const PYC_MAGIC_NUMBER: u16 = 3531;  // Python 3.13

// 如果升级到 Python 3.14，magic number 会变化
// 旧代码无法识别新格式
```

**影响**：
- 🔴 无法加载旧版本的 `.pyc` 文件（如果使用）
- 🔴 Checkpoint 恢复可能失败

#### 当前状态

**字节码格式版本控制**：
- ✅ 有 `PYC_MAGIC_NUMBER`（3531，对应 Python 3.13）
- 🔴 **没有 PVM 特定的版本标识**
- 🔴 **没有字节码格式版本检查**
- 🔴 **没有向后兼容机制**

### 1.2 执行结果不一致风险

#### 问题描述

不同版本的 PVM 执行相同的源代码可能产生不同的结果，导致共识失败。

#### 风险场景

**场景 1：编译器优化变化**

```
PVM v0.1.3:
  def add(a, b):
      return a + b
  # 编译为: LOAD_FAST a; LOAD_FAST b; BINARY_ADD

PVM v0.2.0（优化后）:
  def add(a, b):
      return a + b
  # 编译为: LOAD_FAST a; LOAD_FAST b; INPLACE_ADD（优化）
```

**影响**：
- ⚠️ 字节码不同，但执行结果相同（可接受）
- 🔴 如果优化引入 bug，执行结果可能不同（致命）

**场景 2：VM 执行逻辑变化**

```
PVM v0.1.3:
  dict.keys() 顺序：基于 hash seed

PVM v0.2.0（修复后）:
  dict.keys() 顺序：基于插入顺序（修复）
```

**影响**：
- 🔴 相同输入产生不同输出
- 🔴 共识失败
- 🔴 链分叉风险

**场景 3：浮点运算实现变化**

```
PVM v0.1.3:
  math.sin(0.1) = 0.09983341664682815（硬件浮点）

PVM v0.2.0（SoftFloat 集成后）:
  math.sin(0.1) = 0.09983341664682816（软件浮点，最后一位不同）
```

**影响**：
- 🔴 数值结果不同
- 🔴 金融合约计算错误
- 🔴 共识失败

### 1.3 编译器行为变化风险

#### 问题描述

编译器升级可能导致：
1. 相同源代码编译为不同字节码
2. 编译错误/警告的变化
3. 优化级别的变化

#### 风险场景

**场景 1：AST 解析变化**

```
PVM v0.1.3:
  f"{x}"  # 解析为 f-string

PVM v0.2.0:
  f"{x}"  # 解析错误（如果语法解析器变化）
```

**场景 2：字节码生成变化**

```
PVM v0.1.3:
  [x for x in range(10)]  # 生成 LIST_COMPREHENSION opcode

PVM v0.2.0:
  [x for x in range(10)]  # 生成不同的字节码序列
```

**影响**：
- ⚠️ 字节码不同但语义相同（可接受）
- 🔴 字节码不同且语义不同（致命）

### 1.4 VM 执行逻辑变化风险

#### 问题描述

VM 执行引擎升级可能导致相同字节码产生不同执行结果。

#### 风险场景

**场景 1：Gas 计量变化**

```
PVM v0.1.3:
  LOAD_FAST: 1 gas

PVM v0.2.0:
  LOAD_FAST: 2 gas（Gas 表更新）
```

**影响**：
- ⚠️ Gas 消耗不同，但执行结果相同（可接受，但需要统一）
- 🔴 如果 Gas 不足导致执行失败，结果不同（致命）

**场景 2：异常处理变化**

```
PVM v0.1.3:
  try:
      x = 1 / 0
  except ZeroDivisionError:
      return "error"
  # 返回 "error"

PVM v0.2.0（异常处理修复）:
  try:
      x = 1 / 0
  except ZeroDivisionError:
      return "error"
  # 可能抛出其他异常（如果修复引入 bug）
```

**影响**：
- 🔴 执行结果不同
- 🔴 共识失败

---

## 🔴 第二部分：实际案例分析

### 2.1 版本信息

**当前 PVM 版本**：
```toml
# Cargo.toml
[package.metadata.pvm]
version = "0.1.3"

# Python 版本
MAJOR = 3
MINOR = 13
MICRO = 0
RELEASELEVEL = "alpha"

# 字节码 Magic Number
PYC_MAGIC_NUMBER = 3531  # Python 3.13
```

### 2.2 潜在升级场景

#### 场景 A：Python 版本升级

```
当前: Python 3.13.0alpha
升级: Python 3.14.0

风险：
1. PYC_MAGIC_NUMBER 变化（3531 → 新值）
2. 新语法特性（可能改变 AST）
3. 标准库行为变化
4. 字节码格式可能变化
```

#### 场景 B：编译器优化升级

```
当前: 基础编译
升级: 添加优化器

风险：
1. 字节码序列变化
2. 执行路径变化
3. 可能引入优化 bug
```

#### 场景 C：VM 执行引擎升级

```
当前: 基础执行
升级: 性能优化、bug 修复

风险：
1. 执行结果可能变化
2. Gas 计量可能变化
3. 异常处理可能变化
```

---

## 🔴 第三部分：影响分析

### 3.1 对共识的影响

#### 最坏情况：链分叉

```
节点 A（PVM v0.1.3）:
  执行 Actor 代码 → 结果 R1

节点 B（PVM v0.2.0）:
  执行相同代码 → 结果 R2

R1 ≠ R2 → 共识失败 → 链分叉
```

#### 影响范围

| 影响类型 | 严重性 | 影响范围 |
|---------|--------|---------|
| **单节点不一致** | ⚠️ 中 | 该节点无法参与共识 |
| **部分节点不一致** | 🔴 致命 | 网络分裂，链分叉 |
| **全部节点不一致** | 🔴 致命 | 链完全停止 |

### 3.2 对已部署合约的影响

#### 风险 1：无法执行

```
已部署 Actor（使用 PVM v0.1.3 编译）:
  字节码格式 A

PVM 升级到 v0.2.0:
  无法识别格式 A → 执行失败
```

#### 风险 2：执行结果变化

```
已部署 Actor:
  def calculate():
      return math.sin(0.1)

PVM v0.1.3: 返回 0.09983341664682815
PVM v0.2.0: 返回 0.09983341664682816（SoftFloat）

→ 金融合约计算结果不同
→ 用户资金损失
```

### 3.3 对 Checkpoint/Resume 的影响

#### 风险：无法恢复

```
Checkpoint（PVM v0.1.3）:
  序列化的字节码格式 A

Resume（PVM v0.2.0）:
  无法反序列化格式 A → 恢复失败
```

---

## 🛡️ 第四部分：预防措施

### 4.1 版本标识机制

#### 4.1.1 字节码版本标识

**建议实现**：

```rust
// crates/compiler-core/src/bytecode.rs

#[derive(Debug, Clone)]
pub struct CodeObject<C: Constant = ConstantData> {
    // 添加版本标识
    pub pvm_version: u32,  // PVM 版本（如 0x00010003 = 0.1.3）
    pub bytecode_format_version: u16,  // 字节码格式版本
    
    pub instructions: CodeUnits,
    // ... 其他字段
}
```

**版本编码**：
```rust
// 版本编码格式：0xMMmmpp
// MM = Major (0-255)
// mm = Minor (0-255)  
// pp = Patch (0-255)

fn encode_version(major: u8, minor: u8, patch: u8) -> u32 {
    ((major as u32) << 16) | ((minor as u32) << 8) | (patch as u32)
}

// 示例：0.1.3 → 0x00010003
```

**版本检查**：

```rust
// crates/vm/src/vm/compile.rs

impl VirtualMachine {
    pub fn run_code_obj(&self, code: PyRef<PyCode>, scope: Scope) -> PyResult {
        // 检查版本兼容性
        if !self.is_bytecode_compatible(&code) {
            return Err(self.new_runtime_error(
                format!(
                    "Bytecode version mismatch: expected {}, got {}",
                    self.bytecode_format_version(),
                    code.bytecode_format_version
                )
            ));
        }
        
        // 执行...
    }
    
    fn is_bytecode_compatible(&self, code: &PyCode) -> bool {
        // 检查 PVM 版本兼容性
        if code.pvm_version > self.current_pvm_version() {
            return false;  // 字节码来自未来版本
        }
        
        // 检查字节码格式版本
        if code.bytecode_format_version != self.bytecode_format_version() {
            // 检查是否向后兼容
            return self.is_format_backward_compatible(
                code.bytecode_format_version,
                self.bytecode_format_version()
            );
        }
        
        true
    }
}
```

#### 4.1.2 PVM 版本检查

**建议实现**：

```rust
// crates/pvm-runtime/src/lib.rs

#[derive(Clone, Debug)]
pub struct Version {
    pub major: u8,
    pub minor: u8,
    pub patch: u8,
}

impl Version {
    pub fn new(major: u8, minor: u8, patch: u8) -> Self {
        Self { major, minor, patch }
    }
    
    pub fn from_u32(encoded: u32) -> Self {
        Self {
            major: ((encoded >> 16) & 0xFF) as u8,
            minor: ((encoded >> 8) & 0xFF) as u8,
            patch: (encoded & 0xFF) as u8,
        }
    }
    
    pub fn to_u32(&self) -> u32 {
        ((self.major as u32) << 16) | ((self.minor as u32) << 8) | (self.patch as u32)
    }
    
    pub fn is_compatible_with(&self, other: &Version) -> bool {
        // 主版本号必须相同
        if self.major != other.major {
            return false;
        }
        
        // 次版本号：新版本可以执行旧版本（向后兼容）
        if self.minor > other.minor {
            return true;
        }
        if self.minor < other.minor {
            return false;
        }
        
        // 补丁版本：新版本可以执行旧版本
        self.patch >= other.patch
    }
}

pub struct ExecutionOptions {
    // ... 现有字段
    
    /// 最小 PVM 版本要求
    pub min_pvm_version: Option<Version>,
    
    /// 最大 PVM 版本要求
    pub max_pvm_version: Option<Version>,
    
    /// 锁定 PVM 版本（执行时使用指定版本）
    pub locked_pvm_version: Option<Version>,
}

fn execute_tx_internal(...) -> Result<Bytes, HostError> {
    let current_version = get_current_pvm_version();
    
    // 检查最小版本要求
    if let Some(min_version) = options.min_pvm_version {
        if current_version < min_version {
            return Err(HostError::VersionMismatch(format!(
                "PVM version {} is too old, required: {}",
                current_version, min_version
            )));
        }
    }
    
    // 检查最大版本要求
    if let Some(max_version) = options.max_pvm_version {
        if current_version > max_version {
            return Err(HostError::VersionMismatch(format!(
                "PVM version {} is too new, required: {}",
                current_version, max_version
            )));
        }
    }
    
    // 如果指定了锁定版本，使用该版本执行
    let execution_version = options.locked_pvm_version
        .unwrap_or(current_version);
    
    // 执行...
}
```

### 4.2 确定性保证机制

#### 4.2.1 源代码哈希验证

**建议实现**：

```rust
// Actor 部署时
pub struct ActorState {
    pub address: Address,
    pub code: Vec<u8>,  // Python 源代码
    pub code_hash: H256,  // keccak256(code)
    pub pvm_version: Version,  // 部署时使用的 PVM 版本
    pub storage: HashMap<Bytes, Bytes>,
}

// 部署 Actor
fn deploy_actor(code: Vec<u8>) -> Result<Address> {
    let code_hash = keccak256(&code);
    let pvm_version = get_current_pvm_version();
    
    let actor = ActorState {
        address: compute_address(&code_hash),
        code,
        code_hash,
        pvm_version,
        storage: HashMap::new(),
    };
    
    // 存储到链上
    save_actor_state(&actor)?;
    
    Ok(actor.address)
}

// 执行时验证
fn execute_actor(actor: &ActorState, pvm_version: Version) -> Result<Bytes> {
    // 1. 验证源代码哈希
    let current_hash = keccak256(&actor.code);
    if current_hash != actor.code_hash {
        return Err(Error::CodeTampered);
    }
    
    // 2. 检查 PVM 版本兼容性
    if !is_version_compatible(actor.pvm_version, pvm_version) {
        return Err(Error::VersionMismatch(format!(
            "Actor deployed with PVM {}, current PVM {}",
            actor.pvm_version, pvm_version
        )));
    }
    
    // 3. 使用兼容的版本执行
    execute_with_pvm_version(&actor.code, pvm_version)
}
```

#### 4.2.2 执行结果哈希验证

**建议实现**：

```rust
// 执行前计算预期结果哈希（可选）
pub struct ExecutionContext {
    pub actor: Address,
    pub input: Vec<u8>,
    pub expected_result_hash: Option<H256>,  // 如果已知
}

// 执行
fn execute_with_verification(ctx: &ExecutionContext) -> Result<Bytes> {
    let result = execute_actor(ctx.actor, ctx.input)?;
    
    // 验证结果哈希（如果提供）
    if let Some(expected_hash) = ctx.expected_result_hash {
        let actual_hash = keccak256(&result);
        if actual_hash != expected_hash {
            // 警告：执行结果与预期不符
            log::warn!(
                "Result hash mismatch for actor {}: expected {}, got {}",
                ctx.actor, expected_hash, actual_hash
            );
            
            // 根据策略决定：拒绝交易或记录警告
            if STRICT_MODE {
                return Err(Error::ResultMismatch);
            }
        }
    }
    
    Ok(result)
}
```

### 4.3 多版本支持机制

#### 4.3.1 版本隔离执行

**建议实现**：

```rust
// crates/pvm-runtime/src/lib.rs

pub trait PvmExecutor: Send + Sync {
    fn execute(
        &self,
        code: &[u8],
        input: &[u8],
        options: &ExecutionOptions,
    ) -> Result<Bytes, HostError>;
    
    fn version(&self) -> Version;
}

pub struct PvmRuntime {
    // 支持多个 PVM 版本
    versions: HashMap<Version, Box<dyn PvmExecutor>>,
    default_version: Version,
}

impl PvmRuntime {
    pub fn new() -> Self {
        let mut versions = HashMap::new();
        let current_version = get_current_pvm_version();
        
        // 注册当前版本
        versions.insert(
            current_version.clone(),
            Box::new(CurrentPvmExecutor::new()),
        );
        
        Self {
            versions,
            default_version: current_version,
        }
    }
    
    pub fn register_version(
        &mut self,
        version: Version,
        executor: Box<dyn PvmExecutor>,
    ) {
        self.versions.insert(version, executor);
    }
    
    pub fn execute_with_version(
        &self,
        code: &[u8],
        input: &[u8],
        required_version: Version,
        options: &ExecutionOptions,
    ) -> Result<Bytes, HostError> {
        let executor = self.versions
            .get(&required_version)
            .ok_or_else(|| HostError::UnsupportedVersion(format!(
                "PVM version {} not available",
                required_version
            )))?;
        
        executor.execute(code, input, options)
    }
    
    pub fn execute(
        &self,
        code: &[u8],
        input: &[u8],
        options: &ExecutionOptions,
    ) -> Result<Bytes, HostError> {
        // 如果指定了锁定版本，使用该版本
        let version = options.locked_pvm_version
            .unwrap_or(self.default_version.clone());
        
        self.execute_with_version(code, input, version, options)
    }
}
```

#### 4.3.2 版本迁移策略

**建议实现**：

```rust
// 版本迁移
pub enum VersionMigration {
    /// 自动迁移（兼容）
    Auto,
    
    /// 需要手动迁移
    Manual {
        migration_script: Vec<u8>,
    },
    
    /// 不兼容，需要重新部署
    Incompatible {
        reason: String,
    },
}

pub struct VersionCompatibility {
    pub from_version: Version,
    pub to_version: Version,
    pub migration: VersionMigration,
    pub breaking_changes: Vec<String>,
}

fn check_migration(
    from_version: Version,
    to_version: Version,
) -> VersionCompatibility {
    // 检查版本兼容性
    if from_version.major == to_version.major {
        if from_version.minor <= to_version.minor {
            // 向后兼容
            VersionCompatibility {
                from_version,
                to_version,
                migration: VersionMigration::Auto,
                breaking_changes: vec![],
            }
        } else {
            // 需要降级（不支持）
            VersionCompatibility {
                from_version,
                to_version,
                migration: VersionMigration::Incompatible {
                    reason: "Cannot downgrade PVM version".to_string(),
                },
                breaking_changes: vec![],
            }
        }
    } else {
        // 主版本号不同，不兼容
        VersionCompatibility {
            from_version,
            to_version,
            migration: VersionMigration::Incompatible {
                reason: format!(
                    "Major version change: {} -> {}",
                    from_version.major, to_version.major
                ),
            },
            breaking_changes: get_breaking_changes(from_version, to_version),
        }
    }
}
```

### 4.4 测试和验证机制

#### 4.4.1 升级前测试

**建议流程**：

```rust
// tests/upgrade/compatibility.rs

#[test]
fn test_backward_compatibility() {
    // 1. 使用旧版本编译的测试用例
    let old_bytecode = load_test_bytecode("v0.1.3");
    
    // 2. 在新版本上执行
    let result = execute_bytecode(old_bytecode);
    
    // 3. 验证结果一致
    assert_eq!(result, expected_result);
}

#[test]
fn test_deterministic_execution() {
    // 1. 相同源代码在不同版本编译
    let source = "def main(): return 42";
    
    let v1_result = compile_and_execute(source, Version::new(0, 1, 3));
    let v2_result = compile_and_execute(source, Version::new(0, 2, 0));
    
    // 2. 验证执行结果相同
    assert_eq!(v1_result, v2_result);
}

#[test]
fn test_bytecode_compatibility() {
    // 测试字节码格式兼容性
    let test_cases = vec![
        ("simple_add", "def add(a, b): return a + b"),
        ("dict_ops", "def test(): d = {}; d['a'] = 1; return d"),
        ("float_ops", "def test(): return 1.0 + 2.0"),
    ];
    
    for (name, source) in test_cases {
        // 在多个版本上编译和执行
        let results: Vec<_> = SUPPORTED_VERSIONS
            .iter()
            .map(|version| compile_and_execute(source, version.clone()))
            .collect();
        
        // 验证所有版本结果一致
        let first_result = &results[0];
        for (idx, result) in results.iter().enumerate().skip(1) {
            assert_eq!(
                first_result, result,
                "Version mismatch for test case '{}'",
                name
            );
        }
    }
}
```

#### 4.4.2 跨版本回归测试

**建议实现**：

```rust
// tests/upgrade/regression.rs

#[test]
fn test_cross_version_regression() {
    let test_suite = load_regression_test_suite();
    
    for test_case in test_suite {
        // 在多个版本上执行
        let results: Vec<_> = SUPPORTED_VERSIONS
            .iter()
            .map(|version| {
                execute_with_version(
                    &test_case.source,
                    &test_case.input,
                    version.clone()
                )
            })
            .collect();
        
        // 验证所有版本结果一致
        let first_result = &results[0];
        for (idx, result) in results.iter().enumerate().skip(1) {
            assert_eq!(
                first_result, result,
                "Version mismatch for test case: {}",
                test_case.name
            );
        }
        
        // 验证结果与预期一致
        if let Some(expected) = &test_case.expected_output {
            assert_eq!(first_result, expected);
        }
    }
}

#[test]
fn test_gas_consumption_consistency() {
    // 测试 Gas 消耗在不同版本间的一致性
    let test_cases = load_gas_test_cases();
    
    for test_case in test_cases {
        let gas_consumptions: Vec<_> = SUPPORTED_VERSIONS
            .iter()
            .map(|version| {
                let mut host = MockHost::new(10000, default_context());
                execute_with_version(
                    &test_case.source,
                    &test_case.input,
                    version.clone()
                );
                host.gas_consumed()
            })
            .collect();
        
        // Gas 消耗应该相同（或允许小范围差异）
        let first_gas = gas_consumptions[0];
        for gas in &gas_consumptions[1..] {
            let diff = (*gas as i64 - first_gas as i64).abs();
            assert!(
                diff <= MAX_GAS_DIFF,
                "Gas consumption mismatch: {} vs {}",
                first_gas, gas
            );
        }
    }
}
```

---

## 🚨 第五部分：紧急应对措施

### 5.1 升级策略

#### 策略 1：强制同步升级（推荐）

**方案**：
- 所有节点必须在同一区块高度升级
- 升级前暂停链（graceful shutdown）
- 升级后验证所有节点版本一致

**实施步骤**：

```rust
// 1. 发布升级公告（提前 N 个区块）
fn announce_upgrade(target_block: BlockHeight, new_version: Version) {
    broadcast_upgrade_announcement(UpgradeAnnouncement {
        target_block,
        new_version,
        upgrade_hash: compute_upgrade_hash(new_version),
    });
}

// 2. 在目标区块暂停链
fn pause_chain_at_block(block_height: BlockHeight) {
    // 停止接受新交易
    // 等待所有待处理交易完成
    // 生成最终状态快照
}

// 3. 所有节点升级
fn upgrade_all_nodes(new_version: Version) {
    // 验证升级包完整性
    verify_upgrade_package(new_version)?;
    
    // 执行升级
    install_pvm_version(new_version)?;
    
    // 验证升级成功
    verify_pvm_version(new_version)?;
}

// 4. 恢复链运行
fn resume_chain() {
    // 验证所有节点版本一致
    verify_all_nodes_version()?;
    
    // 恢复接受交易
    resume_transaction_processing();
}
```

**优点**：
- ✅ 避免版本不一致
- ✅ 简单直接
- ✅ 风险可控

**缺点**：
- ⚠️ 需要链暂停
- ⚠️ 升级窗口期
- ⚠️ 需要协调所有节点

#### 策略 2：分阶段升级（风险较高）

**方案**：
- 允许不同节点在不同时间升级
- 通过版本检查拒绝不兼容的交易
- 使用版本隔离执行

**实施步骤**：

```rust
// 1. 启用新版本（但不强制）
fn enable_new_version(new_version: Version) {
    // 注册新版本执行器
    runtime.register_version(new_version, new_executor);
    
    // 设置版本兼容性规则
    set_version_compatibility_rules(new_version);
}

// 2. 节点可以逐步升级
fn upgrade_node_gradually(new_version: Version) {
    // 节点可以选择升级时间
    // 升级后可以执行新版本代码
    // 旧版本代码仍然可以执行
}

// 3. 版本检查
fn check_transaction_version(tx: &Transaction) -> Result<()> {
    if let Some(required_version) = tx.required_pvm_version {
        if !is_version_available(required_version) {
            return Err(Error::VersionNotAvailable);
        }
    }
    Ok(())
}
```

**优点**：
- ✅ 无需链暂停
- ✅ 渐进式升级
- ✅ 灵活性高

**缺点**：
- 🔴 风险高，容易出错
- 🔴 需要复杂的版本管理
- 🔴 可能出现版本不一致

#### 策略 3：版本锁定（最安全）

**方案**：
- Actor 部署时锁定 PVM 版本
- 执行时使用锁定的版本
- 支持多版本共存

**实施步骤**：

```rust
// 1. Actor 部署时锁定版本
fn deploy_actor_with_version(
    code: Vec<u8>,
    pvm_version: Option<Version>,
) -> Result<Address> {
    let version = pvm_version.unwrap_or_else(get_current_pvm_version);
    
    let actor = ActorState {
        code,
        pvm_version: version,  // 锁定版本
        // ...
    };
    
    deploy_actor(actor)
}

// 2. 执行时使用锁定版本
fn execute_actor(actor: &ActorState) -> Result<Bytes> {
    // 使用 Actor 锁定的版本执行
    runtime.execute_with_version(
        &actor.code,
        actor.pvm_version.clone()
    )
}
```

**优点**：
- ✅ 完全避免版本不一致
- ✅ 向后兼容
- ✅ 每个 Actor 独立版本

**缺点**：
- ⚠️ 需要维护多个 PVM 版本
- ⚠️ 资源消耗较大
- ⚠️ 管理复杂度高

### 5.2 回滚机制

#### 紧急回滚

```rust
// 如果升级导致问题，立即回滚

pub struct ChainState {
    // 记录当前使用的 PVM 版本
    pub active_pvm_version: Version,
    
    // 记录上一个稳定版本
    pub previous_stable_version: Version,
    
    // 版本历史
    pub version_history: Vec<VersionRecord>,
}

pub struct VersionRecord {
    pub version: Version,
    pub activated_at: BlockHeight,
    pub deactivated_at: Option<BlockHeight>,
    pub reason: String,
}

fn emergency_rollback(chain: &mut ChainState) -> Result<()> {
    // 1. 记录回滚原因
    log::error!("Emergency rollback triggered");
    
    // 2. 切换到上一个稳定版本
    let previous_version = chain.previous_stable_version.clone();
    chain.active_pvm_version = previous_version.clone();
    
    // 3. 更新版本历史
    chain.version_history.push(VersionRecord {
        version: previous_version.clone(),
        activated_at: get_current_block_height(),
        deactivated_at: None,
        reason: "Emergency rollback".to_string(),
    });
    
    // 4. 通知所有节点
    broadcast_version_change(previous_version.clone());
    
    // 5. 验证回滚成功
    verify_all_nodes_version(previous_version)?;
    
    // 6. 暂停链（如果需要）
    pause_chain_for_investigation();
    
    Ok(())
}

fn verify_all_nodes_version(version: Version) -> Result<()> {
    // 查询所有节点的版本
    let node_versions = query_all_node_versions();
    
    for (node_id, node_version) in node_versions {
        if node_version != version {
            return Err(Error::VersionMismatch(format!(
                "Node {} has version {}, expected {}",
                node_id, node_version, version
            )));
        }
    }
    
    Ok(())
}
```

---

## 📊 第六部分：风险评估矩阵

### 6.1 风险等级

| 风险 | 概率 | 影响 | 风险值 | 优先级 |
|------|------|------|--------|--------|
| **字节码格式变化** | 中 | 致命 | 🔴 高 | P0 |
| **执行结果不一致** | 高 | 致命 | 🔴 极高 | P0 |
| **编译器行为变化** | 中 | 严重 | ⚠️ 中高 | P1 |
| **VM 行为变化** | 中 | 严重 | ⚠️ 中高 | P1 |
| **Checkpoint 不兼容** | 低 | 严重 | 🟡 中 | P2 |
| **Gas 计量变化** | 中 | 严重 | ⚠️ 中高 | P1 |

### 6.2 缓解措施优先级

| 措施 | 成本 | 效果 | 优先级 | 工作量 |
|------|------|------|--------|--------|
| **版本标识机制** | 低 | 高 | P0 | 1 周 |
| **源代码哈希验证** | 低 | 高 | P0 | 3 天 |
| **跨版本测试** | 中 | 高 | P0 | 2 周 |
| **多版本支持** | 高 | 极高 | P1 | 4 周 |
| **版本迁移工具** | 中 | 中 | P2 | 2 周 |
| **升级流程文档** | 低 | 中 | P1 | 1 周 |

---

## 🎯 第七部分：建议的升级流程

### 7.1 升级前准备（1-2 周）

1. **完整测试**
   - [ ] 跨版本兼容性测试
   - [ ] 回归测试套件（所有现有测试）
   - [ ] 性能基准测试
   - [ ] 确定性验证测试
   - [ ] Gas 消耗一致性测试

2. **版本管理**
   - [ ] 确定新版本号（遵循语义化版本）
   - [ ] 更新版本标识（CodeObject）
   - [ ] 更新文档
   - [ ] 创建升级公告

3. **风险评估**
   - [ ] 识别破坏性变更（Breaking Changes）
   - [ ] 评估影响范围（哪些 Actor 受影响）
   - [ ] 制定回滚计划
   - [ ] 准备回滚脚本

4. **沟通和协调**
   - [ ] 提前通知所有节点运营商
   - [ ] 发布升级时间表
   - [ ] 准备升级文档和指南

### 7.2 升级执行（1 天）

1. **通知和准备**
   - [ ] 提前 N 个区块发布升级公告
   - [ ] 准备升级包（验证完整性）
   - [ ] 备份当前状态
   - [ ] 准备回滚包

2. **同步升级**
   - [ ] 在目标区块暂停链
   - [ ] 所有节点同时升级
   - [ ] 验证版本一致性
   - [ ] 执行冒烟测试

3. **验证**
   - [ ] 执行测试套件
   - [ ] 验证共识正常
   - [ ] 监控异常
   - [ ] 验证关键 Actor 执行正常

### 7.3 升级后监控（1 周）

1. **持续监控**
   - [ ] 监控共识状态（是否有分叉）
   - [ ] 监控执行错误（版本相关）
   - [ ] 收集性能指标
   - [ ] 监控 Gas 消耗变化

2. **问题处理**
   - [ ] 快速响应问题
   - [ ] 必要时回滚
   - [ ] 修复和补丁
   - [ ] 更新文档

---

## 📝 第八部分：具体实现建议

### 8.1 立即行动（P0，1-2 周）

#### 1. 实现版本标识

```rust
// crates/compiler-core/src/bytecode.rs

#[derive(Debug, Clone)]
pub struct CodeObject<C: Constant = ConstantData> {
    // 添加版本字段
    pub pvm_version: u32,  // PVM 版本（0x00010003 = 0.1.3）
    pub bytecode_format_version: u16,  // 字节码格式版本（从 1 开始）
    
    pub instructions: CodeUnits,
    // ... 其他字段
}

impl<C: Constant> CodeObject<C> {
    pub fn new_with_version(
        instructions: CodeUnits,
        pvm_version: u32,
        format_version: u16,
        // ... 其他参数
    ) -> Self {
        Self {
            pvm_version,
            bytecode_format_version: format_version,
            instructions,
            // ...
        }
    }
}
```

#### 2. 实现版本检查

```rust
// crates/vm/src/vm/mod.rs

impl VirtualMachine {
    pub fn run_code_obj(&self, code: PyRef<PyCode>, scope: Scope) -> PyResult {
        // 检查版本兼容性
        if let Err(e) = self.check_bytecode_compatibility(&code) {
            return Err(self.new_runtime_error(format!(
                "Bytecode version incompatibility: {}",
                e
            )));
        }
        
        // 执行...
    }
    
    fn check_bytecode_compatibility(&self, code: &PyCode) -> Result<(), String> {
        let current_version = self.get_pvm_version();
        let code_version = Version::from_u32(code.code.pvm_version);
        
        // 检查版本兼容性
        if !code_version.is_compatible_with(&current_version) {
            return Err(format!(
                "Code requires PVM {}, but current version is {}",
                code_version, current_version
            ));
        }
        
        // 检查字节码格式版本
        let current_format = self.get_bytecode_format_version();
        if code.code.bytecode_format_version != current_format {
            if !self.is_format_backward_compatible(
                code.code.bytecode_format_version,
                current_format
            ) {
                return Err(format!(
                    "Bytecode format version {} is not compatible with {}",
                    code.code.bytecode_format_version, current_format
                ));
            }
        }
        
        Ok(())
    }
}
```

#### 3. 建立测试套件

```rust
// tests/upgrade/version_compatibility.rs

#[test]
fn test_version_identifier() {
    let source = "def main(): return 42";
    let code = compile_with_version(source, Version::new(0, 1, 3));
    
    assert_eq!(code.pvm_version, 0x00010003);
    assert_eq!(code.bytecode_format_version, 1);
}

#[test]
fn test_cross_version_execution() {
    let test_cases = vec![
        ("simple", "def main(): return 1"),
        ("dict", "def main(): d = {}; d['a'] = 1; return d"),
        ("list", "def main(): return [1, 2, 3]"),
    ];
    
    for (name, source) in test_cases {
        let results: Vec<_> = vec![
            Version::new(0, 1, 3),
            Version::new(0, 2, 0),
        ]
        .iter()
        .map(|v| compile_and_execute(source, v.clone()))
        .collect();
        
        assert_eq!(results[0], results[1], "Mismatch for {}", name);
    }
}
```

### 8.2 短期行动（P1，1-2 个月）

#### 1. 多版本支持

```rust
// crates/pvm-runtime/src/version_manager.rs

pub struct VersionManager {
    executors: HashMap<Version, Box<dyn PvmExecutor>>,
    compatibility_matrix: CompatibilityMatrix,
}

impl VersionManager {
    pub fn execute_with_version(
        &self,
        code: &[u8],
        required_version: Version,
    ) -> Result<Bytes, HostError> {
        // 查找执行器
        let executor = self.executors
            .get(&required_version)
            .ok_or(HostError::UnsupportedVersion)?;
        
        executor.execute(code)
    }
    
    pub fn check_compatibility(
        &self,
        from_version: Version,
        to_version: Version,
    ) -> VersionCompatibility {
        self.compatibility_matrix.check(from_version, to_version)
    }
}
```

#### 2. 升级工具

```rust
// scripts/upgrade/upgrade_manager.rs

pub struct UpgradeManager {
    current_version: Version,
    target_version: Version,
}

impl UpgradeManager {
    pub fn prepare_upgrade(&self) -> Result<UpgradePackage> {
        // 1. 检查兼容性
        let compatibility = check_compatibility(
            self.current_version,
            self.target_version
        )?;
        
        // 2. 准备升级包
        let package = UpgradePackage {
            from_version: self.current_version.clone(),
            to_version: self.target_version.clone(),
            migration: compatibility.migration,
            breaking_changes: compatibility.breaking_changes,
            upgrade_script: generate_upgrade_script(&compatibility)?,
        };
        
        Ok(package)
    }
    
    pub fn execute_upgrade(&self, package: &UpgradePackage) -> Result<()> {
        // 1. 备份当前版本
        backup_current_version()?;
        
        // 2. 执行升级
        match &package.migration {
            VersionMigration::Auto => {
                install_new_version(&package.to_version)?;
            }
            VersionMigration::Manual { script } => {
                execute_migration_script(script)?;
            }
            VersionMigration::Incompatible { reason } => {
                return Err(Error::IncompatibleUpgrade(reason.clone()));
            }
        }
        
        // 3. 验证升级
        verify_upgrade(&package.to_version)?;
        
        Ok(())
    }
}
```

### 8.3 长期规划（P2，3-6 个月）

#### 1. 版本管理框架

```rust
// crates/pvm-version-manager/src/lib.rs

pub struct VersionManager {
    versions: HashMap<Version, VersionInfo>,
    compatibility_matrix: CompatibilityMatrix,
    migration_rules: HashMap<(Version, Version), MigrationRule>,
}

pub struct VersionInfo {
    pub version: Version,
    pub release_date: DateTime,
    pub breaking_changes: Vec<BreakingChange>,
    pub deprecations: Vec<Deprecation>,
    pub migration_guide: Option<String>,
}

pub struct CompatibilityMatrix {
    // 版本兼容性矩阵
    matrix: HashMap<(Version, Version), bool>,
}

impl CompatibilityMatrix {
    pub fn is_compatible(&self, from: Version, to: Version) -> bool {
        // 检查兼容性
        self.matrix.get(&(from, to)).copied().unwrap_or(false)
    }
}
```

---

## 🔚 总结

### 核心结论

1. **PVM 升级确实会产生不一致风险**，这是区块链系统的固有挑战
2. **风险等级：🔴 致命**，必须采取预防措施
3. **关键风险点**：
   - 字节码格式变化
   - 执行结果不一致
   - 版本不兼容

### 必须实现的机制

1. ✅ **版本标识**：字节码包含版本信息
2. ✅ **版本检查**：执行前验证版本兼容性
3. ✅ **测试套件**：跨版本兼容性测试
4. ✅ **升级流程**：标准化的升级流程
5. ✅ **回滚机制**：紧急回滚能力

### 建议

**立即行动**：
- 实现版本标识和检查机制
- 建立完整的测试套件
- 制定升级流程规范

**长期规划**：
- 支持多版本共存
- 建立版本管理框架
- 自动化测试和验证

**关键原则**：
- ✅ **确定性优先**：确保升级后执行结果一致
- ✅ **向后兼容**：尽可能保持向后兼容
- ✅ **可回滚**：必须有回滚机制
- ✅ **充分测试**：升级前必须充分测试

---

**文档维护**: 本文档应随 PVM 升级持续更新，记录每次升级的风险评估和应对措施。
