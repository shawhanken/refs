# 混合字节码存储设计：兼顾一致性与可升级性

**文档版本**: 1.0  
**创建日期**: 2026-01-22  
**设计目标**: 结合 EVM 的字节码持久化优势与 PVM 的可升级性优势

---

## 📋 执行摘要

本文档提出一种**混合存储方案**，通过**版本化字节码持久化**实现：
- ✅ **EVM 级别的共识安全性**（持久化字节码确保一致性）
- ✅ **PVM 级别的可升级性**（源代码升级 + 字节码重新编译）
- ✅ **最佳实践**：结合两种方案的优势

### 核心设计

```
部署时：
  源代码 → 编译 → 字节码 → 存储（版本化）
  
执行时：
  优先使用存储的字节码（确保一致性）
  
升级时：
  新源代码 → 编译 → 新字节码 → 存储（新版本）
  旧字节码保留（向后兼容）
```

---

## 🎯 第一部分：设计目标

### 1.1 核心需求

| 需求 | EVM 方式 | PVM 方式 | 混合方案目标 |
|------|----------|----------|-------------|
| **共识安全性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **可升级性** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **执行性能** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **存储成本** | ⚠️ 高 | ✅ 低 | ⚠️ 中 |
| **版本管理** | ✅ 简单 | ⚠️ 复杂 | ⚠️ 中 |

### 1.2 设计原则

1. **字节码优先**：执行时优先使用存储的字节码
2. **版本隔离**：每个版本独立存储，互不干扰
3. **向后兼容**：旧版本字节码永久可用
4. **升级灵活**：支持源代码升级和字节码重新编译
5. **一致性保证**：相同版本的字节码执行结果完全一致

---

## 🏗️ 第二部分：架构设计

### 2.1 数据模型

#### Actor 状态结构

```rust
// crates/pvm-runtime/src/actor_state.rs

/// Actor 状态（链上存储）
pub struct ActorState {
    /// Actor 地址
    pub address: Address,
    
    /// 当前激活的版本
    pub active_version: VersionId,
    
    /// 源代码（用于升级）
    pub source_code: Option<Vec<u8>>,  // 可选，用于升级
    
    /// 版本化字节码存储
    pub bytecode_versions: HashMap<VersionId, BytecodeVersion>,
    
    /// 存储（键值对）
    pub storage: HashMap<Bytes, Bytes>,
    
    /// 元数据
    pub metadata: ActorMetadata,
}

/// 字节码版本
pub struct BytecodeVersion {
    /// 版本 ID（递增）
    pub version_id: VersionId,
    
    /// PVM 版本（编译时使用的 PVM 版本）
    pub pvm_version: Version,
    
    /// 字节码格式版本
    pub bytecode_format_version: u16,
    
    /// 序列化的字节码（marshal 格式）
    pub bytecode: Vec<u8>,
    
    /// 源代码哈希（用于验证）
    pub source_hash: H256,
    
    /// 字节码哈希（用于验证）
    pub bytecode_hash: H256,
    
    /// 创建时间（区块高度）
    pub created_at: BlockHeight,
    
    /// 是否已废弃
    pub deprecated: bool,
}

/// 版本 ID（递增整数）
pub type VersionId = u32;
```

### 2.2 存储布局

```
ActorState {
    address: 0x1234...,
    active_version: 2,
    
    // 源代码（可选，用于升级）
    source_code: Some(b"@actor\nclass MyActor: ..."),
    
    // 版本化字节码
    bytecode_versions: {
        1: BytecodeVersion {
            pvm_version: Version(0, 1, 3),
            bytecode_format_version: 1,
            bytecode: [0x12, 0x34, ...],  // 序列化的 CodeObject
            source_hash: 0xabcd...,
            bytecode_hash: 0xef01...,
            created_at: 1000,
            deprecated: true,  // v1 已废弃
        },
        2: BytecodeVersion {
            pvm_version: Version(0, 1, 3),
            bytecode_format_version: 1,
            bytecode: [0x56, 0x78, ...],  // 新版本的字节码
            source_hash: 0x2345...,
            bytecode_hash: 0x6789...,
            created_at: 2000,
            deprecated: false,  // v2 当前激活
        },
    },
    
    storage: {...},
}
```

### 2.3 执行流程

#### 正常执行（使用存储的字节码）

```rust
// crates/pvm-runtime/src/lib.rs

fn execute_actor(
    actor: &ActorState,
    input: &[u8],
    options: &ExecutionOptions,
) -> Result<Bytes, HostError> {
    // 1. 获取当前激活版本的字节码
    let bytecode_version = actor.bytecode_versions
        .get(&actor.active_version)
        .ok_or(HostError::VersionNotFound)?;
    
    // 2. 验证字节码完整性
    let computed_hash = keccak256(&bytecode_version.bytecode);
    if computed_hash != bytecode_version.bytecode_hash {
        return Err(HostError::BytecodeCorrupted);
    }
    
    // 3. 检查 PVM 版本兼容性
    let current_pvm_version = get_current_pvm_version();
    if !is_version_compatible(
        &bytecode_version.pvm_version,
        &current_pvm_version
    ) {
        return Err(HostError::VersionIncompatible(format!(
            "Bytecode requires PVM {}, current is {}",
            bytecode_version.pvm_version, current_pvm_version
        )));
    }
    
    // 4. 反序列化字节码
    let code_object = deserialize_bytecode(&bytecode_version.bytecode)?;
    
    // 5. 执行（无需编译，直接执行字节码）
    execute_code_object(code_object, input, options)
}
```

#### 升级流程（源代码 → 字节码）

```rust
// crates/pvm-runtime/src/lib.rs

fn upgrade_actor(
    actor: &mut ActorState,
    new_source_code: Vec<u8>,
    upgrade_authority: UpgradeAuthority,
) -> Result<VersionId, HostError> {
    // 1. 验证升级权限
    verify_upgrade_permission(actor, &upgrade_authority)?;
    
    // 2. 计算源代码哈希
    let source_hash = keccak256(&new_source_code);
    
    // 3. 编译源代码为字节码
    let code_object = compile_source(&new_source_code)?;
    
    // 4. 序列化字节码
    let bytecode = serialize_bytecode(&code_object)?;
    let bytecode_hash = keccak256(&bytecode);
    
    // 5. 创建新版本
    let new_version_id = actor.active_version + 1;
    let current_pvm_version = get_current_pvm_version();
    
    let new_version = BytecodeVersion {
        version_id: new_version_id,
        pvm_version: current_pvm_version,
        bytecode_format_version: get_bytecode_format_version(),
        bytecode,
        source_hash,
        bytecode_hash,
        created_at: get_current_block_height(),
        deprecated: false,
    };
    
    // 6. 存储新版本
    actor.bytecode_versions.insert(new_version_id, new_version);
    
    // 7. 更新激活版本
    actor.active_version = new_version_id;
    
    // 8. 可选：存储源代码（用于未来升级）
    if should_store_source_code() {
        actor.source_code = Some(new_source_code);
    }
    
    Ok(new_version_id)
}
```

---

## 🔒 第三部分：一致性保证机制

### 3.1 字节码锁定机制

#### 设计：版本锁定

每个 Actor 的每个版本在创建时**锁定**特定的 PVM 版本和字节码格式版本：

```rust
pub struct BytecodeVersion {
    // 锁定信息
    pub pvm_version: Version,           // 编译时使用的 PVM 版本
    pub bytecode_format_version: u16,    // 字节码格式版本
    
    // 字节码（不可变）
    pub bytecode: Vec<u8>,              // 序列化的 CodeObject
    
    // 验证信息
    pub source_hash: H256,              // 源代码哈希
    pub bytecode_hash: H256,            // 字节码哈希
}
```

#### 执行时验证

```rust
fn execute_with_consistency_check(
    bytecode_version: &BytecodeVersion,
    current_pvm: &Version,
) -> Result<(), HostError> {
    // 1. 检查 PVM 版本兼容性
    if !is_version_compatible(
        &bytecode_version.pvm_version,
        current_pvm
    ) {
        // 如果当前 PVM 版本更新，检查是否向后兼容
        if current_pvm > &bytecode_version.pvm_version {
            // 尝试使用旧版本 PVM 执行器
            return execute_with_legacy_pvm(bytecode_version);
        } else {
            return Err(HostError::VersionIncompatible);
        }
    }
    
    // 2. 验证字节码哈希
    let computed_hash = keccak256(&bytecode_version.bytecode);
    if computed_hash != bytecode_version.bytecode_hash {
        return Err(HostError::BytecodeCorrupted);
    }
    
    Ok(())
}
```

### 3.2 多版本支持

#### 设计：版本隔离执行

```rust
pub struct PvmRuntime {
    // 支持多个 PVM 版本
    pvm_executors: HashMap<Version, Box<dyn PvmExecutor>>,
}

impl PvmRuntime {
    fn execute_bytecode_version(
        &self,
        bytecode_version: &BytecodeVersion,
        input: &[u8],
    ) -> Result<Bytes, HostError> {
        // 1. 查找对应版本的执行器
        let executor = self.pvm_executors
            .get(&bytecode_version.pvm_version)
            .ok_or(HostError::UnsupportedVersion)?;
        
        // 2. 反序列化字节码
        let code_object = deserialize_bytecode(&bytecode_version.bytecode)?;
        
        // 3. 使用对应版本的执行器执行
        executor.execute_code_object(code_object, input)
    }
}
```

### 3.3 向后兼容性

#### 设计：旧版本字节码永久可用

```
Actor 升级流程：
1. 部署 v1（PVM 0.1.3）→ 存储字节码 v1
2. PVM 升级到 0.2.0
3. 升级 Actor → 编译新源代码 → 存储字节码 v2（PVM 0.2.0）
4. v1 字节码仍然保留，可以使用旧 PVM 执行
```

**优势**：
- ✅ 旧版本字节码永久可用
- ✅ 无需迁移用户
- ✅ 支持回滚到旧版本

---

## 🚀 第四部分：升级机制

### 4.1 升级策略

#### 策略 1：源代码升级（推荐）

```rust
// 升级时提供新源代码
fn upgrade_with_source(
    actor: &mut ActorState,
    new_source: Vec<u8>,
) -> Result<VersionId, HostError> {
    // 1. 编译新源代码
    let code_object = compile_source(&new_source)?;
    
    // 2. 创建新版本字节码
    let new_version = create_bytecode_version(code_object, new_source)?;
    
    // 3. 存储新版本
    actor.bytecode_versions.insert(new_version.version_id, new_version);
    actor.active_version = new_version.version_id;
    
    Ok(new_version.version_id)
}
```

#### 策略 2：直接字节码升级（高级）

```rust
// 直接提供新字节码（需要验证）
fn upgrade_with_bytecode(
    actor: &mut ActorState,
    new_bytecode: Vec<u8>,
    source_hash: H256,  // 用于验证
) -> Result<VersionId, HostError> {
    // 1. 验证字节码格式
    verify_bytecode_format(&new_bytecode)?;
    
    // 2. 可选：验证源代码哈希（如果提供了源代码）
    if let Some(source) = &actor.source_code {
        let computed_hash = keccak256(source);
        if computed_hash != source_hash {
            return Err(HostError::SourceHashMismatch);
        }
    }
    
    // 3. 创建新版本
    let new_version = BytecodeVersion {
        version_id: actor.active_version + 1,
        pvm_version: get_current_pvm_version(),
        bytecode_format_version: get_bytecode_format_version(),
        bytecode: new_bytecode,
        source_hash,
        bytecode_hash: keccak256(&new_bytecode),
        created_at: get_current_block_height(),
        deprecated: false,
    };
    
    // 4. 存储
    actor.bytecode_versions.insert(new_version.version_id, new_version);
    actor.active_version = new_version.version_id;
    
    Ok(new_version.version_id)
}
```

### 4.2 升级权限管理

#### 设计：灵活的权限模型

```rust
pub enum UpgradeAuthority {
    /// 所有者升级（单签名）
    Owner(Address),
    
    /// 多签升级（N-of-M）
    Multisig {
        threshold: u8,
        signers: Vec<Address>,
    },
    
    /// 治理升级（DAO 投票）
    Governance {
        proposal_id: u64,
        min_votes: u64,
    },
    
    /// 时间锁升级（延迟执行）
    Timelock {
        authority: Box<UpgradeAuthority>,
        delay: BlockHeight,
    },
}

fn verify_upgrade_permission(
    actor: &ActorState,
    authority: &UpgradeAuthority,
) -> Result<(), HostError> {
    match authority {
        UpgradeAuthority::Owner(owner) => {
            if actor.metadata.owner != *owner {
                return Err(HostError::Unauthorized);
            }
        }
        UpgradeAuthority::Multisig { threshold, signers } => {
            // 验证多签
            verify_multisig(threshold, signers)?;
        }
        UpgradeAuthority::Governance { proposal_id, min_votes } => {
            // 验证治理投票
            verify_governance_vote(proposal_id, min_votes)?;
        }
        UpgradeAuthority::Timelock { authority, delay } => {
            // 验证时间锁
            verify_timelock(authority, delay)?;
        }
    }
    Ok(())
}
```

### 4.3 升级验证

#### 设计：升级前验证

```rust
fn validate_upgrade(
    old_version: &BytecodeVersion,
    new_source: &[u8],
) -> Result<(), HostError> {
    // 1. 编译新源代码
    let new_code_object = compile_source(new_source)?;
    
    // 2. 检查破坏性变更（可选）
    if let Some(old_source) = get_old_source_code(old_version) {
        check_breaking_changes(old_source, new_source)?;
    }
    
    // 3. 执行测试套件（如果提供）
    if let Some(tests) = get_test_suite() {
        run_tests(new_code_object, tests)?;
    }
    
    Ok(())
}
```

---

## ⚡ 第五部分：性能优化

### 5.1 字节码缓存

#### 设计：执行时缓存

```rust
// 执行时缓存反序列化的字节码
pub struct BytecodeCache {
    cache: HashMap<(Address, VersionId), CodeObject>,
}

impl BytecodeCache {
    fn get_or_load(
        &mut self,
        actor: &ActorState,
        version_id: VersionId,
    ) -> Result<CodeObject, HostError> {
        let key = (actor.address, version_id);
        
        // 1. 检查缓存
        if let Some(code) = self.cache.get(&key) {
            return Ok(code.clone());
        }
        
        // 2. 从链上加载
        let bytecode_version = actor.bytecode_versions
            .get(&version_id)
            .ok_or(HostError::VersionNotFound)?;
        
        // 3. 反序列化
        let code = deserialize_bytecode(&bytecode_version.bytecode)?;
        
        // 4. 缓存
        self.cache.insert(key, code.clone());
        
        Ok(code)
    }
}
```

### 5.2 编译优化

#### 设计：升级时编译，执行时直接使用

```
传统 PVM（源代码存储）：
  每次执行：源代码 → 编译 → 执行
  开销：编译时间（1-10ms）

混合方案（字节码存储）：
  升级时：源代码 → 编译 → 存储字节码
  执行时：字节码 → 反序列化 → 执行
  开销：反序列化时间（<1ms，快 10 倍）
```

### 5.3 存储优化

#### 设计：可选源代码存储

```rust
pub struct ActorState {
    // 源代码（可选）
    // - 如果存储：可以升级，但存储成本高
    // - 如果不存储：无法升级，但存储成本低
    pub source_code: Option<Vec<u8>>,
    
    // 字节码（必须）
    pub bytecode_versions: HashMap<VersionId, BytecodeVersion>,
}

// 存储策略
pub enum SourceCodeStoragePolicy {
    /// 始终存储源代码（可升级）
    Always,
    
    /// 不存储源代码（不可升级，但节省存储）
    Never,
    
    /// 仅存储最新版本源代码（可升级最新版本）
    LatestOnly,
}
```

---

## 🔐 第六部分：安全性设计

### 6.1 字节码完整性验证

#### 设计：多重验证

```rust
fn verify_bytecode_integrity(
    bytecode_version: &BytecodeVersion,
) -> Result<(), HostError> {
    // 1. 验证字节码哈希
    let computed_hash = keccak256(&bytecode_version.bytecode);
    if computed_hash != bytecode_version.bytecode_hash {
        return Err(HostError::BytecodeCorrupted);
    }
    
    // 2. 验证字节码格式
    verify_bytecode_format(&bytecode_version.bytecode)?;
    
    // 3. 验证版本信息
    if bytecode_version.pvm_version.major == 0 {
        // 主版本 0 表示开发版本，需要额外验证
        verify_development_version(&bytecode_version)?;
    }
    
    Ok(())
}
```

### 6.2 升级安全机制

#### 设计：升级前检查

```rust
fn safe_upgrade(
    actor: &mut ActorState,
    new_source: Vec<u8>,
) -> Result<VersionId, HostError> {
    // 1. 验证升级权限
    verify_upgrade_permission(actor)?;
    
    // 2. 编译新源代码
    let new_code = compile_source(&new_source)?;
    
    // 3. 执行冒烟测试（如果提供）
    if let Some(smoke_tests) = get_smoke_tests() {
        run_smoke_tests(&new_code, smoke_tests)?;
    }
    
    // 4. 检查 Gas 消耗变化（警告）
    let old_gas = estimate_gas(&actor.bytecode_versions[&actor.active_version])?;
    let new_gas = estimate_gas(&new_code)?;
    if new_gas > old_gas * 2 {
        log::warn!("Gas consumption increased significantly");
    }
    
    // 5. 创建新版本
    let new_version = create_bytecode_version(new_code, new_source)?;
    
    // 6. 存储（但不立即激活）
    actor.bytecode_versions.insert(new_version.version_id, new_version);
    
    // 7. 返回新版本 ID（需要显式激活）
    Ok(new_version.version_id)
}

// 显式激活新版本（延迟激活）
fn activate_version(
    actor: &mut ActorState,
    version_id: VersionId,
) -> Result<(), HostError> {
    if !actor.bytecode_versions.contains_key(&version_id) {
        return Err(HostError::VersionNotFound);
    }
    
    // 可选：等待时间锁
    if let Some(timelock) = actor.metadata.upgrade_timelock {
        if get_current_block_height() < timelock {
            return Err(HostError::TimelockNotExpired);
        }
    }
    
    actor.active_version = version_id;
    Ok(())
}
```

---

## 📊 第七部分：对比分析

### 7.1 方案对比

| 特性 | EVM | PVM（源代码） | 混合方案 |
|------|-----|--------------|----------|
| **共识安全性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **可升级性** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **执行性能** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **存储成本** | ⚠️ 高 | ✅ 低 | ⚠️ 中 |
| **版本管理** | ✅ 简单 | ⚠️ 复杂 | ⚠️ 中 |
| **升级灵活性** | 🔴 无 | ✅ 高 | ✅ 高 |
| **向后兼容** | ✅ 是 | ⚠️ 需管理 | ✅ 是 |

### 7.2 适用场景

#### EVM 方式（纯字节码）

**适合**：
- 金融 DeFi 应用（需要极高安全性）
- 不需要升级的应用
- 对存储成本不敏感

#### PVM 方式（纯源代码）

**适合**：
- 快速迭代的应用
- 需要频繁升级的应用
- 对存储成本敏感

#### 混合方案

**适合**：
- **需要高安全性的可升级应用**（最佳选择）
- 企业级应用（需要升级 + 安全性）
- AI 智能体应用（需要升级 + 性能）

---

## 🎯 第八部分：实现建议

### 8.1 实现步骤

#### Phase 1：基础框架（2 周）

1. **数据结构设计**
   ```rust
   // 实现 ActorState, BytecodeVersion
   pub struct ActorState { ... }
   pub struct BytecodeVersion { ... }
   ```

2. **字节码序列化/反序列化**
   ```rust
   // 使用现有的 marshal 功能
   fn serialize_bytecode(code: &CodeObject) -> Vec<u8>
   fn deserialize_bytecode(bytes: &[u8]) -> CodeObject
   ```

3. **基础执行流程**
   ```rust
   // 从字节码执行，而非源代码
   fn execute_from_bytecode(bytecode: &[u8]) -> Result<Bytes>
   ```

#### Phase 2：版本管理（2 周）

1. **版本创建和存储**
   ```rust
   fn create_bytecode_version(source: &[u8]) -> BytecodeVersion
   fn store_bytecode_version(actor: &mut ActorState, version: BytecodeVersion)
   ```

2. **版本切换**
   ```rust
   fn switch_version(actor: &mut ActorState, version_id: VersionId)
   ```

3. **版本查询**
   ```rust
   fn get_version(actor: &ActorState, version_id: VersionId) -> Option<&BytecodeVersion>
   ```

#### Phase 3：升级机制（2 周）

1. **源代码升级**
   ```rust
   fn upgrade_with_source(actor: &mut ActorState, new_source: Vec<u8>) -> VersionId
   ```

2. **权限验证**
   ```rust
   fn verify_upgrade_permission(actor: &ActorState, authority: &UpgradeAuthority)
   ```

3. **升级验证**
   ```rust
   fn validate_upgrade(old_version: &BytecodeVersion, new_source: &[u8])
   ```

#### Phase 4：优化和测试（2 周）

1. **性能优化**
   - 字节码缓存
   - 反序列化优化

2. **测试覆盖**
   - 单元测试
   - 集成测试
   - 升级流程测试

### 8.2 代码示例

#### 完整实现示例

```rust
// crates/pvm-runtime/src/actor_state.rs

use std::collections::HashMap;
use sha3::{Keccak256, Digest};

pub struct ActorState {
    pub address: Address,
    pub active_version: VersionId,
    pub source_code: Option<Vec<u8>>,
    pub bytecode_versions: HashMap<VersionId, BytecodeVersion>,
    pub storage: HashMap<Bytes, Bytes>,
}

impl ActorState {
    /// 部署新 Actor
    pub fn deploy(
        address: Address,
        source_code: Vec<u8>,
    ) -> Result<Self, HostError> {
        // 1. 编译源代码
        let code_object = compile_source(&source_code)?;
        
        // 2. 序列化字节码
        let bytecode = serialize_bytecode(&code_object)?;
        
        // 3. 计算哈希
        let source_hash = Keccak256::digest(&source_code).into();
        let bytecode_hash = Keccak256::digest(&bytecode).into();
        
        // 4. 创建版本
        let version = BytecodeVersion {
            version_id: 1,
            pvm_version: get_current_pvm_version(),
            bytecode_format_version: get_bytecode_format_version(),
            bytecode,
            source_hash,
            bytecode_hash,
            created_at: get_current_block_height(),
            deprecated: false,
        };
        
        // 5. 创建 Actor 状态
        let mut versions = HashMap::new();
        versions.insert(1, version);
        
        Ok(Self {
            address,
            active_version: 1,
            source_code: Some(source_code),
            bytecode_versions: versions,
            storage: HashMap::new(),
        })
    }
    
    /// 执行 Actor
    pub fn execute(
        &self,
        input: &[u8],
        options: &ExecutionOptions,
    ) -> Result<Bytes, HostError> {
        // 1. 获取当前版本的字节码
        let version = self.bytecode_versions
            .get(&self.active_version)
            .ok_or(HostError::VersionNotFound)?;
        
        // 2. 验证字节码完整性
        let computed_hash = Keccak256::digest(&version.bytecode).into();
        if computed_hash != version.bytecode_hash {
            return Err(HostError::BytecodeCorrupted);
        }
        
        // 3. 检查版本兼容性
        let current_pvm = get_current_pvm_version();
        if !is_version_compatible(&version.pvm_version, &current_pvm) {
            // 使用旧版本 PVM 执行器
            return execute_with_legacy_pvm(version, input, options);
        }
        
        // 4. 反序列化字节码
        let code_object = deserialize_bytecode(&version.bytecode)?;
        
        // 5. 执行
        execute_code_object(code_object, input, options)
    }
    
    /// 升级 Actor
    pub fn upgrade(
        &mut self,
        new_source: Vec<u8>,
        authority: UpgradeAuthority,
    ) -> Result<VersionId, HostError> {
        // 1. 验证权限
        verify_upgrade_permission(self, &authority)?;
        
        // 2. 编译新源代码
        let code_object = compile_source(&new_source)?;
        
        // 3. 序列化字节码
        let bytecode = serialize_bytecode(&code_object)?;
        
        // 4. 计算哈希
        let source_hash = Keccak256::digest(&new_source).into();
        let bytecode_hash = Keccak256::digest(&bytecode).into();
        
        // 5. 创建新版本
        let new_version_id = self.active_version + 1;
        let new_version = BytecodeVersion {
            version_id: new_version_id,
            pvm_version: get_current_pvm_version(),
            bytecode_format_version: get_bytecode_format_version(),
            bytecode,
            source_hash,
            bytecode_hash,
            created_at: get_current_block_height(),
            deprecated: false,
        };
        
        // 6. 存储新版本
        self.bytecode_versions.insert(new_version_id, new_version);
        
        // 7. 更新激活版本
        self.active_version = new_version_id;
        
        // 8. 更新源代码（可选）
        if should_store_source_code() {
            self.source_code = Some(new_source);
        }
        
        Ok(new_version_id)
    }
}
```

---

## 🔚 第九部分：总结

### 9.1 核心优势

**混合方案结合了 EVM 和 PVM 的优势**：

1. ✅ **EVM 级别的共识安全性**
   - 持久化字节码确保一致性
   - 版本锁定机制
   - 字节码完整性验证

2. ✅ **PVM 级别的可升级性**
   - 源代码升级
   - 版本管理
   - 向后兼容

3. ✅ **最佳性能**
   - 执行时无需编译
   - 字节码缓存
   - 快速反序列化

### 9.2 适用场景

**混合方案最适合**：

- ✅ **需要高安全性的可升级应用**
- ✅ **企业级应用**（需要升级 + 安全性）
- ✅ **AI 智能体应用**（需要升级 + 性能）
- ✅ **金融应用**（需要安全性 + 可维护性）

### 9.3 实施建议

**推荐采用混合方案**，因为：

1. ✅ **兼顾一致性和可升级性**
2. ✅ **性能最优**（执行时无需编译）
3. ✅ **安全性高**（字节码完整性验证）
4. ✅ **灵活性好**（支持多种升级策略）

**实施优先级**：
- **P0**：基础框架（字节码存储 + 执行）
- **P1**：版本管理（多版本支持）
- **P2**：升级机制（源代码升级）
- **P3**：优化（缓存、性能）

---

**文档维护**: 本文档应随实现进展持续更新。
