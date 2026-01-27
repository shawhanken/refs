# PVM 升级改造安全防护方案

**制定日期**：2026-01-22  
**目标**：确保 PVM 升级改造过程中不影响已与 chain 整合的功能  
**策略**：预防为主 + 全面测试 + 渐进式升级

---

## 📋 执行摘要

### 核心原则

1. **向后兼容优先**：所有改动必须保持 API 兼容性
2. **渐进式升级**：分阶段、小步快跑、及时验证
3. **测试驱动**：先写测试，再改代码
4. **快速回滚**：每个阶段都有回滚方案

### 关键指标

| 指标 | 当前状态 | 目标状态 | 差距 |
|------|---------|---------|------|
| **单元测试覆盖率** | ~30% | ≥80% | +50% |
| **集成测试覆盖** | ~40% | ≥70% | +30% |
| **回归测试套件** | 14 个测试 | 100+ 个测试 | +86 个 |
| **端到端测试** | 示例代码 | 自动化 E2E | 新建 |
| **性能基准测试** | 无 | 完整基准 | 新建 |

---

## 🎯 第一部分：风险评估与预防措施

### 1.1 已整合功能清单

根据 `PROJECT_STATUS_COMPREHENSIVE.md`，以下功能已与 chain 成功整合：

#### ✅ **核心功能**（必须保护）

| 功能 | 集成位置 | 风险等级 | 保护措施 |
|------|---------|---------|---------|
| **PVM 执行引擎** | `chain/src/execution.rs` | 🔴 高 | 完整回归测试 |
| **HostApi 接口** | `chain/src/pvm_host.rs` | 🔴 高 | API 兼容性测试 |
| **单块原子性** | `chain/src/execution.rs` | 🔴 高 | 原子性测试套件 |
| **消息传递** | `PvmExecutionContext` | 🔴 高 | 消息流测试 |
| **Continuation (Checkpoint)** | `chain/src/pvm_executor.rs` | 🔴 高 | Continuation 测试套件 |
| **确定性执行** | `DeterminismOptions` | 🔴 高 | 确定性验证测试 |
| **状态管理** | `CowboyHost` | 🔴 高 | 状态一致性测试 |
| **副作用收集** | `ExecutionSideEffects` | 🔴 高 | 副作用测试 |

#### ⚠️ **依赖功能**（需要验证）

| 功能 | 依赖关系 | 风险等级 | 保护措施 |
|------|---------|---------|---------|
| **Arc<Mutex<>> 重构** | 所有异步执行 | ⚠️ 中 | 并发测试 |
| **Tokio Runtime** | 集成测试 | ⚠️ 中 | Runtime 环境测试 |
| **Stack size 配置** | 长时间执行 | ⚠️ 中 | 压力测试 |

### 1.2 升级改造风险矩阵

#### **高风险改造**（需要特别防护）

| 改造项 | 影响范围 | 风险 | 防护措施 |
|--------|---------|------|---------|
| **SoftFloat 集成** | 所有浮点运算 | 🔴 极高 | 1. ✅ 配置开关（已实现）<br>2. ✅ 完整回归测试（50+ 单元测试，集成测试，回归测试）<br>3. ✅ 性能对比（基准测试）<br>4. ✅ 跨平台一致性测试（x86_64, ARM64）<br>5. ✅ 位级确定性验证 |
| **ordered_set 实现** | set 相关代码 | 🔴 高 | 1. 新类型，不替换现有<br>2. 迁移工具<br>3. 兼容性测试 |
| **FSM 编译器启用** | 编译流程 | 🔴 高 | 1. 配置开关<br>2. 向后兼容<br>3. 渐进式启用 |
| **Runner 系统** | 消息路由 | 🔴 高 | 1. 新模块，不修改现有<br>2. 接口隔离<br>3. 集成测试 |
| **Guard 验证** | Continuation | ⚠️ 中 | 1. 可选功能<br>2. 默认关闭<br>3. 迁移路径 |
| **Dual Gas** | HostApi | ⚠️ 中 | 1. 扩展接口，不破坏现有<br>2. 默认单 Gas<br>3. 配置开关 |

### 1.3 预防措施清单

#### **措施 1：特性开关（Feature Flags）**

**目标**：所有新功能通过特性开关控制，默认关闭

**实现**：
```rust
// Cargo.toml
[features]
default = []
softfloat = ["softfloat-wrapper"]
ordered_set = []
fsm_compiler = []
runner_system = []
guard_validation = []
dual_gas = []

// 代码中使用
#[cfg(feature = "softfloat")]
use softfloat_wrapper::*;

#[cfg(not(feature = "softfloat"))]
// 使用硬件浮点（现有实现）
```

**好处**：
- ✅ 新功能不影响现有代码
- ✅ 可以逐步启用和测试
- ✅ 出问题可以快速关闭

#### **措施 2：API 版本化**

**目标**：保持现有 API 不变，新功能通过新 API 提供

**实现**：
```rust
// 现有 API（保持不变）
pub trait HostApi {
    fn charge_gas(&mut self, amount: u64) -> HostResult<()>;
}

// 新 API（扩展，不破坏现有）
pub trait HostApiV2: HostApi {
    fn charge_cycles(&mut self, amount: u64) -> HostResult<()>;
    fn charge_cells(&mut self, amount: u64) -> HostResult<()>;
}

// 实现时提供默认实现（向后兼容）
impl<T: HostApi> HostApiV2 for T {
    fn charge_cycles(&mut self, amount: u64) -> HostResult<()> {
        self.charge_gas(amount)  // 默认映射到旧 API
    }
    fn charge_cells(&mut self, amount: u64) -> HostResult<()> {
        Ok(())  // 默认不收费
    }
}
```

#### **措施 3：配置隔离**

**目标**：新功能通过配置启用，不影响默认行为

**实现**：
```rust
// 现有配置（保持不变）
pub struct ExecutionOptions {
    pub deterministic: bool,
    pub continuation: Option<ContinuationOptions>,
    // ...
}

// 扩展配置（可选）
pub struct ExecutionOptions {
    // ... 现有字段
    #[serde(default)]
    pub enable_softfloat: bool,  // 默认 false
    #[serde(default)]
    pub enable_ordered_set: bool,  // 默认 false
    #[serde(default)]
    pub enable_fsm: bool,  // 默认 false（但建议改为 true）
    #[serde(default)]
    pub enable_guard_validation: bool,  // 默认 false
}
```

#### **措施 4：代码隔离**

**目标**：新功能在新模块中实现，最小化对现有代码的修改

**目录结构**：
```
crates/
├── vm/src/
│   ├── builtins/
│   │   ├── float.rs          # 现有（不改动）
│   │   └── softfloat.rs      # 新建（新功能）
│   ├── builtins/
│   │   ├── set.rs             # 现有（不改动）
│   │   └── ordered_set.rs     # 新建（新功能）
│   └── ...
├── runner/                    # 新建模块
│   └── src/
│       ├── executor.rs
│       ├── llm.rs
│       └── http.rs
└── ...
```

#### **措施 5：渐进式迁移路径**

**目标**：提供清晰的迁移路径，不强制一次性升级

**示例：ordered_set 迁移**：
```python
# 阶段 1：提供新类型（不强制使用）
from pvm_sdk import OrderedSet

# 阶段 2：警告但不阻止使用 set
import warnings
warnings.warn("set iteration order is non-deterministic, use OrderedSet")

# 阶段 3：可选强制（通过配置）
# deterministic_mode.require_ordered_set = True

# 阶段 4：默认使用（未来版本）
```

---

## 🧪 第二部分：测试策略

### 2.1 测试金字塔

```
                    ┌─────────────┐
                    │   E2E Tests │  10% (10-15 个)
                    │  (端到端)    │
                    └─────────────┘
                  ┌───────────────────┐
                  │ Integration Tests │  20% (20-30 个)
                  │   (集成测试)      │
                  └───────────────────┘
                ┌─────────────────────────┐
                │    Unit Tests           │  70% (70-100 个)
                │    (单元测试)            │
                └─────────────────────────┘
```

### 2.2 单元测试策略

#### **目标覆盖率：≥80%**

#### **测试范围**

| 模块 | 当前测试 | 目标测试 | 新增测试 |
|------|---------|---------|---------|
| **pvm-runtime** | 0 | 30+ | +30 |
| **pvm-host** | 0 | 20+ | +20 |
| **vm/checkpoint** | 部分 | 15+ | +10 |
| **vm/snapshot** | 部分 | 15+ | +10 |
| **determinism** | 0 | 10+ | +10 |
| **continuation** | 0 | 10+ | +10 |
| **总计** | ~14 | 100+ | +90 |

#### **测试类型**

**1. 功能测试**：
```rust
// tests/unit/softfloat.rs
#[cfg(test)]
mod tests {
    use rustpython_vm::softfloat;
    
    // === 基本运算测试 ===
    
    #[test]
    fn test_softfloat_addition() {
        let result = softfloat::add(1.5, 2.3);
        assert!((result - 3.8).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_subtraction() {
        let result = softfloat::subtract(5.0, 2.5);
        assert!((result - 2.5).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_multiplication() {
        let result = softfloat::multiply(2.5, 4.0);
        assert!((result - 10.0).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_division() {
        let result = softfloat::divide(10.0, 2.5);
        assert!((result - 4.0).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_negate() {
        let result = softfloat::negate(5.0);
        assert!((result - (-5.0)).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_abs() {
        assert!((softfloat::abs(-5.0) - 5.0).abs() < 1e-10);
        assert!((softfloat::abs(5.0) - 5.0).abs() < 1e-10);
        assert!((softfloat::abs(0.0) - 0.0).abs() < 1e-10);
    }
    
    // === 数学函数测试 ===
    
    #[test]
    fn test_softfloat_sqrt() {
        let result = softfloat::sqrt(4.0);
        assert!((result - 2.0).abs() < 1e-10);
        
        let result = softfloat::sqrt(2.0);
        let expected = 2.0_f64.sqrt();
        assert!((result - expected).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_exp() {
        let result = softfloat::exp(1.0);
        let expected = std::f64::consts::E;
        assert!((result - expected).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_ln() {
        let result = softfloat::ln(std::f64::consts::E);
        assert!((result - 1.0).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_sin() {
        let result = softfloat::sin(0.0);
        assert!((result - 0.0).abs() < 1e-10);
        
        let result = softfloat::sin(std::f64::consts::PI / 2.0);
        assert!((result - 1.0).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_cos() {
        let result = softfloat::cos(0.0);
        assert!((result - 1.0).abs() < 1e-10);
        
        let result = softfloat::cos(std::f64::consts::PI / 2.0);
        assert!(result.abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_tan() {
        let result = softfloat::tan(0.0);
        assert!((result - 0.0).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_asin() {
        let result = softfloat::asin(0.0);
        assert!((result - 0.0).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_acos() {
        let result = softfloat::acos(1.0);
        assert!((result - 0.0).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_atan() {
        let result = softfloat::atan(0.0);
        assert!((result - 0.0).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_atan2() {
        let result = softfloat::atan2(0.0, 1.0);
        assert!((result - 0.0).abs() < 1e-10);
    }
    
    // === 取整函数测试 ===
    
    #[test]
    fn test_softfloat_floor() {
        assert_eq!(softfloat::floor(3.7), 3.0);
        assert_eq!(softfloat::floor(-3.7), -4.0);
        assert_eq!(softfloat::floor(3.0), 3.0);
    }
    
    #[test]
    fn test_softfloat_ceil() {
        assert_eq!(softfloat::ceil(3.2), 4.0);
        assert_eq!(softfloat::ceil(-3.2), -3.0);
        assert_eq!(softfloat::ceil(3.0), 3.0);
    }
    
    #[test]
    fn test_softfloat_trunc() {
        assert_eq!(softfloat::trunc(3.7), 3.0);
        assert_eq!(softfloat::trunc(-3.7), -3.0);
    }
    
    #[test]
    fn test_softfloat_round() {
        assert_eq!(softfloat::round(3.5), 4.0);
        assert_eq!(softfloat::round(3.4), 3.0);
        assert_eq!(softfloat::round(-3.5), -4.0);
    }
    
    // === 特殊运算测试 ===
    
    #[test]
    fn test_softfloat_modulo() {
        let result = softfloat::modulo(10.0, 3.0);
        assert!((result - 1.0).abs() < 1e-10);
        
        let result = softfloat::modulo(-10.0, 3.0);
        assert!((result - (-1.0)).abs() < 1e-10);
    }
    
    #[test]
    fn test_softfloat_floor_div() {
        let result = softfloat::floor_div(10.0, 3.0);
        assert_eq!(result, 3.0);
        
        let result = softfloat::floor_div(-10.0, 3.0);
        assert_eq!(result, -4.0);
    }
    
    #[test]
    fn test_softfloat_pow() {
        let result = softfloat::pow(2.0, 3.0);
        assert!((result - 8.0).abs() < 1e-10);
        
        let result = softfloat::pow(4.0, 0.5);
        assert!((result - 2.0).abs() < 1e-10);
    }
    
    // === 边界值测试 ===
    
    #[test]
    fn test_softfloat_zero() {
        assert_eq!(softfloat::add(0.0, 0.0), 0.0);
        assert_eq!(softfloat::multiply(0.0, 5.0), 0.0);
        assert_eq!(softfloat::divide(0.0, 5.0), 0.0);
    }
    
    #[test]
    fn test_softfloat_infinity() {
        let inf = f64::INFINITY;
        let result = softfloat::add(inf, 1.0);
        assert!(result.is_infinite());
        
        let result = softfloat::multiply(inf, 2.0);
        assert!(result.is_infinite());
    }
    
    #[test]
    fn test_softfloat_nan() {
        let nan = f64::NAN;
        let result = softfloat::add(nan, 1.0);
        assert!(result.is_nan());
    }
    
    #[test]
    fn test_softfloat_very_small() {
        let small = 1e-300;
        let result = softfloat::multiply(small, 2.0);
        assert!(result > 0.0);
    }
    
    #[test]
    fn test_softfloat_very_large() {
        let large = 1e300;
        let result = softfloat::multiply(large, 2.0);
        assert!(result.is_infinite() || result > large);
    }
    
    // === 确定性测试（位级一致性）===
    
    #[test]
    fn test_softfloat_determinism_basic_ops() {
        // 相同输入应该产生位级相同的结果
        let a = 1.23456789012345;
        let b = 9.87654321098765;
        
        let add1 = softfloat::add(a, b);
        let add2 = softfloat::add(a, b);
        assert_eq!(add1.to_bits(), add2.to_bits());
        
        let mul1 = softfloat::multiply(a, b);
        let mul2 = softfloat::multiply(a, b);
        assert_eq!(mul1.to_bits(), mul2.to_bits());
    }
    
    #[test]
    fn test_softfloat_determinism_math_funcs() {
        // 数学函数应该产生位级相同的结果
        let x = 0.123456789;
        
        let sin1 = softfloat::sin(x);
        let sin2 = softfloat::sin(x);
        assert_eq!(sin1.to_bits(), sin2.to_bits());
        
        let sqrt1 = softfloat::sqrt(x);
        let sqrt2 = softfloat::sqrt(x);
        assert_eq!(sqrt1.to_bits(), sqrt2.to_bits());
    }
    
    // === 精度测试 ===
    
    #[test]
    fn test_softfloat_precision() {
        // 测试高精度计算
        let a = 0.1;
        let b = 0.2;
        let result = softfloat::add(a, b);
        // 应该避免浮点精度问题
        assert!((result - 0.3).abs() < 1e-15);
    }
    
    // === 属性测试（使用 proptest）===
    
    #[cfg(feature = "proptest")]
    mod proptest_tests {
        use super::*;
        use proptest::prelude::*;
        
        proptest! {
            #[test]
            fn test_softfloat_commutative_add(a in -1000.0f64..1000.0, b in -1000.0f64..1000.0) {
                let result1 = softfloat::add(a, b);
                let result2 = softfloat::add(b, a);
                // 允许小的浮点误差
                prop_assert!((result1 - result2).abs() < 1e-10);
            }
            
            #[test]
            fn test_softfloat_associative_add(
                a in -100.0f64..100.0,
                b in -100.0f64..100.0,
                c in -100.0f64..100.0
            ) {
                let result1 = softfloat::add(softfloat::add(a, b), c);
                let result2 = softfloat::add(a, softfloat::add(b, c));
                prop_assert!((result1 - result2).abs() < 1e-9);
            }
            
            #[test]
            fn test_softfloat_distributive(
                a in -100.0f64..100.0,
                b in -100.0f64..100.0,
                c in -100.0f64..100.0
            ) {
                let result1 = softfloat::multiply(a, softfloat::add(b, c));
                let result2 = softfloat::add(
                    softfloat::multiply(a, b),
                    softfloat::multiply(a, c)
                );
                prop_assert!((result1 - result2).abs() < 1e-9);
            }
        }
    }
}
```

**2. 边界测试**：
```rust
#[test]
fn test_checkpoint_empty_state() {
    let vm = create_vm();
    let checkpoint = vm.save_checkpoint().unwrap();
    assert!(!checkpoint.is_empty());
}

#[test]
fn test_checkpoint_large_state() {
    let vm = create_vm_with_large_state(10_000_000);  // 10MB
    let checkpoint = vm.save_checkpoint().unwrap();
    assert!(checkpoint.len() > 1_000_000);
}
```

**3. 错误处理测试**：
```rust
#[test]
fn test_continuation_invalid_cid() {
    let result = load_continuation(&[0u8; 32]);
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), ContinuationError::NotFound));
}

#[test]
fn test_gas_exhaustion() {
    let mut host = create_host_with_gas(100);
    let result = execute_with_gas(&mut host, 200);
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), HostError::GasExhausted));
}
```

**4. 并发测试**：
```rust
#[tokio::test]
async fn test_concurrent_state_access() {
    let host = Arc::new(Mutex::new(create_host()));
    let mut handles = vec![];
    
    for i in 0..10 {
        let host_clone = host.clone();
        handles.push(tokio::spawn(async move {
            let mut h = host_clone.lock().await;
            h.state_set(&format!("key_{}", i), &[i as u8]).unwrap();
        }));
    }
    
    futures::future::join_all(handles).await;
    
    let h = host.lock().await;
    for i in 0..10 {
        let value = h.state_get(&format!("key_{}", i)).unwrap();
        assert_eq!(value, Some(vec![i as u8]));
    }
}
```

**5. 性能测试**：
```rust
#[test]
fn test_checkpoint_performance() {
    let vm = create_vm();
    let start = std::time::Instant::now();
    let checkpoint = vm.save_checkpoint().unwrap();
    let duration = start.elapsed();
    
    // 10MB 状态应该在 100ms 内完成
    assert!(duration.as_millis() < 100);
}
```

#### **测试工具和框架**

```toml
# Cargo.toml
[dev-dependencies]
tokio-test = "0.4"
proptest = "1.4"  # 属性测试
criterion = "0.5"  # 性能基准
mockall = "0.13"  # Mock 对象
```

**属性测试示例**：
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_softfloat_commutative(a in -1000.0f64..1000.0, b in -1000.0f64..1000.0) {
        let fa = SoftFloat::from(a);
        let fb = SoftFloat::from(b);
        prop_assert_eq!(fa + fb, fb + fa);  // 交换律
    }
}
```

### 2.3 集成测试策略

#### **目标：20-30 个集成测试**

#### **测试场景**

**1. Chain 集成测试**（最重要）：
```rust
// tests/integration/chain_execution.rs
#[tokio::test]
async fn test_chain_execution_basic() {
    let executor = create_chain_executor();
    let contract = load_contract("examples/pvm_runtime_chain_demo/contract.py");
    let input = b"hello";
    
    let result = executor.execute(contract, input).await.unwrap();
    assert_eq!(result.output, b"hello");
    assert_eq!(result.events.len(), 0);
}

#[tokio::test]
async fn test_chain_execution_with_state() {
    let executor = create_chain_executor();
    let contract = load_contract("examples/pvm_runtime_chain_demo/contract.py");
    
    // 第一次执行：设置状态
    let input1 = b"set:key1:value1";
    executor.execute(contract.clone(), input1).await.unwrap();
    
    // 第二次执行：读取状态
    let input2 = b"get:key1";
    let result = executor.execute(contract, input2).await.unwrap();
    assert_eq!(result.output, b"value1");
}

#[tokio::test]
async fn test_chain_execution_atomicity() {
    let executor = create_chain_executor();
    let contract = load_contract("examples/pvm_runtime_chain_demo/contract.py");
    
    // 执行会失败的操作
    let input = b"fail";
    let result = executor.execute(contract, input).await;
    assert!(result.is_err());
    
    // 验证状态未改变
    let state = executor.get_state("key1").unwrap();
    assert_eq!(state, None);
}
```

**2. Continuation 集成测试**：
```rust
#[tokio::test]
async fn test_continuation_checkpoint_resume() {
    let executor = create_chain_executor();
    let contract = load_contract("examples/pvm_runtime_chain_demo/checkpoint_demo.py");
    
    // 第一次执行：创建 checkpoint
    let input1 = b"checkpoint";
    let result1 = executor.execute(contract.clone(), input1).await.unwrap();
    assert!(result1.checkpoint.is_some());
    
    // 第二次执行：resume
    let input2 = b"resume";
    let result2 = executor.execute_with_resume(
        contract,
        input2,
        result1.checkpoint.unwrap()
    ).await.unwrap();
    
    assert_eq!(result2.output, b"resumed");
}
```

**3. 确定性集成测试**：
```rust
#[test]
fn test_deterministic_execution() {
    let contract = load_contract("examples/pvm_runtime_chain_demo/determinism_demo.py");
    let input = b"hello";
    
    // 执行多次，结果应该完全相同
    let results: Vec<_> = (0..10).map(|_| {
        let executor = create_chain_executor();
        executor.execute(contract.clone(), input).unwrap().output
    }).collect();
    
    // 所有结果应该相同
    let first = &results[0];
    for result in &results[1..] {
        assert_eq!(result, first);
    }
}

// === SoftFloat 集成测试 ===

#[tokio::test]
async fn test_softfloat_integration_basic_math() {
    let contract = r#"
def main(input):
    import math
    a = 1.5
    b = 2.3
    result = a + b
    return str(result).encode('ascii')
"#;
    
    let executor = create_executor_with_softfloat_enabled();
    let result = executor.execute(contract, b"").await.unwrap();
    assert_eq!(result.output, b"3.8");
}

#[tokio::test]
async fn test_softfloat_integration_math_module() {
    let contract = r#"
def main(input):
    import math
    result = math.sqrt(4.0)
    return str(result).encode('ascii')
"#;
    
    let executor = create_executor_with_softfloat();
    let result = executor.execute(contract, b"").await.unwrap();
    assert_eq!(result.output, b"2.0");
}

#[tokio::test]
async fn test_softfloat_integration_cross_platform() {
    // 在不同架构上执行相同的浮点运算，结果应该位级相同
    let contract = r#"
def main(input):
    import math
    result = math.sin(0.1)
    # 返回结果的十六进制表示以确保位级一致性
    import struct
    return struct.pack('>d', result)
"#;
    
    let executor1 = create_executor_with_softfloat();
    let result1 = executor1.execute(contract, b"").await.unwrap();
    
    // 在另一个"架构"上执行（模拟）
    let executor2 = create_executor_with_softfloat();
    let result2 = executor2.execute(contract, b"").await.unwrap();
    
    // 结果应该位级相同
    assert_eq!(result1.output, result2.output);
}

#[tokio::test]
async fn test_softfloat_integration_float_operations() {
    let contract = r#"
def main(input):
    a = 0.1
    b = 0.2
    result = a + b
    # 测试浮点精度
    return str(result == 0.3).encode('ascii')
"#;
    
    let executor = create_executor_with_softfloat();
    let result = executor.execute(contract, b"").await.unwrap();
    // SoftFloat 应该提供更好的精度控制
    assert_eq!(result.output, b"True");
}

#[tokio::test]
async fn test_softfloat_integration_complex_calculation() {
    let contract = r#"
def main(input):
    import math
    # 复杂的浮点计算
    x = 1.23456789012345
    y = math.sqrt(x)
    z = math.sin(y)
    w = math.exp(z)
    result = math.log(w)
    return str(result).encode('ascii')
"#;
    
    let executor = create_executor_with_softfloat();
    let result = executor.execute(contract, b"").await.unwrap();
    // 验证计算正确性
    assert!(!result.output.is_empty());
}

#[tokio::test]
async fn test_softfloat_integration_deterministic_across_runs() {
    let contract = r#"
def main(input):
    import math
    import random
    # 即使使用随机数，浮点运算结果应该确定
    random.seed(42)
    x = random.random()
    result = math.sqrt(x) + math.sin(x)
    return struct.pack('>d', result)
"#;
    
    let results: Vec<_> = (0..5).map(|_| {
        let executor = create_executor_with_softfloat();
        executor.execute(contract, b"").block_on().unwrap().output
    }).collect();
    
    // 所有执行结果应该完全相同（位级）
    let first = &results[0];
    for result in &results[1..] {
        assert_eq!(result, first);
    }
}
```

**4. 消息传递集成测试**：
```rust
#[tokio::test]
async fn test_message_flow() {
    let executor = create_chain_executor();
    let contract = load_contract("examples/pvm_actor_transfer_demo/contract.py");
    
    let input = b"transfer:alice:bob:100";
    let result = executor.execute(contract, input).await.unwrap();
    
    // 验证消息已发送
    assert_eq!(result.outgoing_messages.len(), 1);
    assert_eq!(result.outgoing_messages[0].target, b"bob");
}
```

**5. 副作用收集测试**：
```rust
#[tokio::test]
async fn test_side_effects_collection() {
    let executor = create_chain_executor();
    let contract = load_contract("examples/pvm_runtime_chain_demo/contract.py");
    
    let input = b"emit:test:data";
    let result = executor.execute(contract, input).await.unwrap();
    
    assert_eq!(result.events.len(), 1);
    assert_eq!(result.events[0].topic, "test");
    assert_eq!(result.events[0].data, b"data");
}
```

### 2.4 回归测试套件

#### **目标：100+ 个回归测试**

#### **测试分类**

**1. 已整合功能回归测试**（最高优先级）：

```rust
// tests/regression/chain_integration.rs

/// 测试：单块原子性（已有功能）
#[tokio::test]
async fn regression_test_atomicity() {
    // 使用真实的 chain 执行器
    // 验证：失败时状态回滚
}

/// 测试：消息传递（已有功能）
#[tokio::test]
async fn regression_test_message_passing() {
    // 验证：消息正确发送和接收
}

/// 测试：Continuation Checkpoint（已有功能）
#[tokio::test]
async fn regression_test_continuation_checkpoint() {
    // 验证：checkpoint 和 resume 正常工作
}

/// 测试：确定性执行（已有功能）
#[test]
fn regression_test_determinism() {
    // 验证：多次执行结果相同
}

/// 测试：HostApi 接口（已有功能）
#[tokio::test]
async fn regression_test_host_api() {
    // 验证：所有 HostApi 方法正常工作
}

/// 测试：状态管理（已有功能）
#[tokio::test]
async fn regression_test_state_management() {
    // 验证：状态读写正确
}

/// 测试：副作用收集（已有功能）
#[tokio::test]
async fn regression_test_side_effects() {
    // 验证：Events、Messages、Timers 正确收集
}

/// 测试：Arc<Mutex<>> 并发（已有功能）
#[tokio::test]
async fn regression_test_concurrent_access() {
    // 验证：并发访问不会导致死锁或数据竞争
}

// === SoftFloat 回归测试 ===

/// 回归测试：启用 SoftFloat 后，现有浮点运算仍然正确
#[tokio::test]
async fn regression_test_softfloat_backward_compatibility() {
    let contract = r#"
def main(input):
    # 使用基本的浮点运算
    a = 1.5
    b = 2.5
    result = a + b
    return str(result).encode('ascii')
"#;
    
    // 使用硬件浮点（默认）
    let executor_hw = create_executor_with_softfloat_disabled();
    let result_hw = executor_hw.execute(contract, b"").await.unwrap();
    
    // 使用 SoftFloat
    let executor_sf = create_executor_with_softfloat_enabled();
    let result_sf = executor_sf.execute(contract, b"").await.unwrap();
    
    // 结果应该数值上相等（允许小的精度差异）
    let hw_value: f64 = std::str::from_utf8(&result_hw.output).unwrap().parse().unwrap();
    let sf_value: f64 = std::str::from_utf8(&result_sf.output).unwrap().parse().unwrap();
    assert!((hw_value - sf_value).abs() < 1e-10);
}

/// 回归测试：SoftFloat 不影响整数运算
#[tokio::test]
async fn regression_test_softfloat_integer_operations() {
    let contract = r#"
def main(input):
    a = 10
    b = 20
    result = a + b
    return str(result).encode('ascii')
"#;
    
    let executor = create_executor_with_softfloat_enabled();
    let result = executor.execute(contract, b"").await.unwrap();
    assert_eq!(result.output, b"30");
}

/// 回归测试：SoftFloat 配置开关正常工作
#[tokio::test]
async fn regression_test_softfloat_feature_flag() {
    let contract = r#"
def main(input):
    import math
    result = math.sqrt(4.0)
    return str(result).encode('ascii')
"#;
    
    // 测试可以动态启用/禁用
    let mut executor = create_executor();
    
    // 禁用 SoftFloat
    executor.set_softfloat_enabled(false);
    let result1 = executor.execute(contract, b"").await.unwrap();
    
    // 启用 SoftFloat
    executor.set_softfloat_enabled(true);
    let result2 = executor.execute(contract, b"").await.unwrap();
    
    // 两种模式都应该工作
    assert_eq!(result1.output, b"2.0");
    assert_eq!(result2.output, b"2.0");
}

/// 回归测试：SoftFloat 性能不影响基本功能
#[tokio::test]
async fn regression_test_softfloat_performance_acceptable() {
    let contract = r#"
def main(input):
    import math
    # 执行大量浮点运算
    total = 0.0
    for i in range(1000):
        total += math.sin(i * 0.01)
    return str(total).encode('ascii')
"#;
    
    let executor = create_executor_with_softfloat_enabled();
    let start = std::time::Instant::now();
    let result = executor.execute(contract, b"").await.unwrap();
    let duration = start.elapsed();
    
    // 应该在合理时间内完成（例如 < 1 秒）
    assert!(duration.as_secs() < 1);
    assert!(!result.output.is_empty());
}

/// 回归测试：SoftFloat 与 Checkpoint 兼容
#[tokio::test]
async fn regression_test_softfloat_with_checkpoint() {
    let contract = r#"
def main(input):
    import math
    from pvm_sdk.continuation import save_cont
    
    x = math.sqrt(2.0)
    save_cont("test", {"value": x})
    return str(x).encode('ascii')
"#;
    
    let executor = create_executor_with_softfloat_enabled();
    let result1 = executor.execute(contract, b"").await.unwrap();
    
    // Resume 后结果应该一致
    let resume_contract = r#"
def main(input):
    from pvm_sdk.continuation import load_cont
    data = load_cont("test")
    return str(data["ctx"]["value"]).encode('ascii')
"#;
    
    let result2 = executor.resume(resume_contract, result1.checkpoint.unwrap()).await.unwrap();
    assert_eq!(result1.output, result2.output);
}
```

**2. 示例代码回归测试**：

```rust
// tests/regression/examples.rs

/// 测试：pvm_runtime_chain_demo
#[tokio::test]
async fn regression_test_runtime_chain_demo() {
    let contract = include_str!("../../examples/pvm_runtime_chain_demo/contract.py");
    let executor = create_chain_executor();
    
    // 测试所有示例场景
    let scenarios = vec![
        ("hello", b"hello"),
        ("set:key:value", b"set:key:value"),
        ("get:key", b"get:key"),
    ];
    
    for (name, input) in scenarios {
        let result = executor.execute(contract, input).await;
        assert!(result.is_ok(), "Scenario {} failed", name);
    }
}

/// 测试：pvm_dex_demo
#[tokio::test]
async fn regression_test_dex_demo() {
    // ...
}

/// 测试：pvm_actor_transfer_demo
#[tokio::test]
async fn regression_test_actor_transfer_demo() {
    // ...
}

/// 测试：breakpoint_resume_demo
#[test]
fn regression_test_breakpoint_resume() {
    // ...
}
```

**3. 边界情况回归测试**：

```rust
// tests/regression/edge_cases.rs

/// 测试：空输入
#[tokio::test]
async fn regression_test_empty_input() {
    // ...
}

/// 测试：超大状态
#[tokio::test]
async fn regression_test_large_state() {
    // ...
}

/// 测试：深度递归
#[tokio::test]
async fn regression_test_deep_recursion() {
    // ...
}

/// 测试：Gas 耗尽
#[tokio::test]
async fn regression_test_gas_exhaustion() {
    // ...
}

/// 测试：并发执行
#[tokio::test]
async fn regression_test_concurrent_execution() {
    // ...
}
```

**4. 性能回归测试**：

```rust
// tests/regression/performance.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn regression_benchmark_checkpoint(c: &mut Criterion) {
    let vm = create_vm_with_state(1_000_000);  // 1MB state
    
    c.bench_function("checkpoint_save", |b| {
        b.iter(|| {
            black_box(vm.save_checkpoint().unwrap());
        });
    });
}

fn regression_benchmark_execution(c: &mut Criterion) {
    let executor = create_chain_executor();
    let contract = load_contract("examples/pvm_runtime_chain_demo/contract.py");
    
    c.bench_function("chain_execution", |b| {
        b.iter(|| {
            black_box(executor.execute(contract.clone(), b"hello").await.unwrap());
        });
    });
}

// === SoftFloat 性能基准测试 ===

fn benchmark_softfloat_vs_hardware(c: &mut Criterion) {
    let mut group = c.benchmark_group("float_operations");
    
    // 基本运算性能对比
    group.bench_function("add_hardware", |b| {
        b.iter(|| {
            let a = 1.5;
            let b = 2.3;
            black_box(a + b);
        });
    });
    
    group.bench_function("add_softfloat", |b| {
        b.iter(|| {
            black_box(rustpython_vm::softfloat::add(1.5, 2.3));
        });
    });
    
    // 数学函数性能对比
    group.bench_function("sqrt_hardware", |b| {
        b.iter(|| {
            black_box(4.0_f64.sqrt());
        });
    });
    
    group.bench_function("sqrt_softfloat", |b| {
        b.iter(|| {
            black_box(rustpython_vm::softfloat::sqrt(4.0));
        });
    });
    
    group.bench_function("sin_hardware", |b| {
        b.iter(|| {
            black_box(0.5_f64.sin());
        });
    });
    
    group.bench_function("sin_softfloat", |b| {
        b.iter(|| {
            black_box(rustpython_vm::softfloat::sin(0.5));
        });
    });
    
    group.finish();
}

fn benchmark_python_float_operations(c: &mut Criterion) {
    let contract = r#"
def main(input):
    import math
    total = 0.0
    for i in range(1000):
        total += math.sin(i * 0.01) * math.sqrt(i)
    return str(total).encode('ascii')
"#;
    
    let mut group = c.benchmark_group("python_float_ops");
    
    group.bench_function("with_hardware_float", |b| {
        let executor = create_executor_with_softfloat_disabled();
        b.iter(|| {
            black_box(executor.execute(contract, b"").block_on().unwrap());
        });
    });
    
    group.bench_function("with_softfloat", |b| {
        let executor = create_executor_with_softfloat_enabled();
        b.iter(|| {
            black_box(executor.execute(contract, b"").block_on().unwrap());
        });
    });
    
    group.finish();
}

criterion_group!(
    benches,
    regression_benchmark_checkpoint,
    regression_benchmark_execution,
    benchmark_softfloat_vs_hardware,
    benchmark_python_float_operations
);
criterion_main!(benches);
```

### 2.5 端到端测试（E2E）

#### **目标：10-15 个 E2E 测试**

#### **测试场景**

**1. 完整业务流程测试**：

```rust
// tests/e2e/business_flows.rs

/// E2E 测试：完整的 DEX 交易流程
#[tokio::test]
async fn e2e_dex_trading_flow() {
    // 1. 初始化 DEX
    // 2. 添加流动性
    // 3. 执行交易
    // 4. 验证状态
    // 5. 验证事件
}

/// E2E 测试：Actor 转账流程
#[tokio::test]
async fn e2e_actor_transfer_flow() {
    // 1. 创建 Actor
    // 2. 转账
    // 3. 验证余额
    // 4. 验证消息
}

/// E2E 测试：Continuation 完整流程
#[tokio::test]
async fn e2e_continuation_flow() {
    // 1. 创建 Continuation
    // 2. Checkpoint
    // 3. Resume
    // 4. 完成
    // 5. 验证结果
}
```

**2. 跨模块集成测试**：

```rust
// tests/e2e/cross_module.rs

/// E2E 测试：PVM + Chain + Storage
#[tokio::test]
async fn e2e_pvm_chain_storage() {
    // 测试 PVM 执行 → Chain 处理 → Storage 持久化
}

/// E2E 测试：PVM + Runner + Verification
#[tokio::test]
async fn e2e_pvm_runner_verification() {
    // 测试 PVM 调用 Runner → Runner 执行 → 验证结果
}
```

### 2.6 测试基础设施

#### **测试工具链**

```toml
# Cargo.toml
[dev-dependencies]
# 基础测试
tokio = { version = "1.35", features = ["full", "test-util"] }
tokio-test = "0.4"

# 属性测试
proptest = "1.4"

# 性能基准
criterion = { version = "0.5", features = ["html_reports"] }

# Mock
mockall = "0.13"

# 测试工具
tempfile = "3.8"
serial_test = "3.0"  # 串行化测试（避免资源竞争）

# 覆盖率
cargo-llvm-cov = "0.5"
```

#### **测试配置**

```toml
# .cargo/config.toml
[test]
# 测试超时
timeout = 300  # 5 分钟

# 并行测试数量
jobs = 4
```

#### **CI/CD 集成**

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run unit tests
        run: cargo test --lib -- --test-threads=4
  
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: cargo test --test '*' -- --test-threads=1
  
  regression-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v3
      - name: Run regression tests
        run: cargo test --test regression
  
  softfloat-cross-platform:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        target: [x86_64-unknown-linux-gnu, aarch64-unknown-linux-gnu]
    steps:
      - uses: actions/checkout@v3
      - name: Install cross-compilation toolchain
        run: |
          rustup target add ${{ matrix.target }}
      - name: Run SoftFloat cross-platform tests
        run: |
          cargo test --target ${{ matrix.target }} --package rustpython-vm --lib softfloat
      - name: Verify bit-level consistency
        run: |
          # 运行确定性测试，验证位级一致性
          cargo test --target ${{ matrix.target }} --package rustpython-vm --lib softfloat::tests::test_softfloat_determinism
  
  coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Generate coverage
        run: |
          cargo llvm-cov --locked --lcov --output-path lcov.info
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./lcov.info
```

---

## 🔄 第三部分：渐进式升级流程

### 3.1 升级阶段划分

#### **阶段 0：准备阶段**（1-2 周）

**目标**：建立测试基础设施

**任务清单**：
- [ ] 设置测试框架和工具
- [ ] 编写现有功能的回归测试（100+ 个）
- [ ] 建立 CI/CD 测试流水线
- [ ] 性能基准测试基线
- [ ] 代码覆盖率基线（当前 ~30%）

**验收标准**：
- ✅ 所有现有功能都有回归测试
- ✅ CI/CD 自动运行所有测试
- ✅ 测试覆盖率 ≥30%

#### **阶段 1：SoftFloat 集成**（3-4 周）

**目标**：集成软件浮点，不影响现有功能

**实施步骤**：

**Week 1-2：实现和单元测试**
- [x] 集成纯 Rust SoftFloat 库（`softfloat` crate）
- [x] 实现 SoftFloat 包装模块（`crates/vm/src/softfloat.rs`）
- [x] 集成到浮点运算（`float.rs`）和数学库（`math.rs`）
- [x] 在 Settings 中添加 `enable_softfloat` 配置
- [ ] 编写单元测试（50+ 个，包括基本运算、数学函数、边界值、确定性测试）
- [ ] 性能基准测试（与硬件浮点对比）

**Week 3：集成测试和跨平台验证**
- [ ] 在测试环境中启用 SoftFloat
- [ ] 运行完整回归测试套件
- [ ] 验证不影响现有功能（向后兼容性测试）
- [ ] 性能对比测试（目标：<2x 硬件浮点）
- [ ] **跨平台一致性测试**（x86_64, ARM64, RISC-V）
  - [ ] 位级一致性验证
  - [ ] 相同输入产生相同输出（位级）
- [ ] **数学函数完整性测试**
  - [ ] 所有 math 模块函数测试
  - [ ] 三角函数、双曲函数、对数函数等

**Week 4：渐进式启用和文档**
- [x] 在 `DeterminismOptions` 中添加配置（默认启用）
- [x] 在 `pvm-runtime` 中集成配置传递
- [ ] 在 chain 中添加配置开关（如果需要）
- [ ] 默认启用（确定性执行时），可选禁用
- [ ] 监控生产环境（如果启用）
- [ ] 文档更新
  - [ ] SoftFloat 使用说明
  - [ ] 性能影响说明
  - [ ] 配置选项说明

**回滚方案**：
- 通过配置开关关闭
- 如果出现问题，立即回滚到硬件浮点

#### **阶段 2：ordered_set 实现**（1-2 周）

**目标**：提供 ordered_set 类型，不替换现有 set

**实施步骤**：

**Week 1：实现**
- [ ] 实现 `OrderedSet` 类型
- [ ] 编写单元测试（20+ 个）
- [ ] 提供迁移工具

**Week 2：集成和测试**
- [ ] 在 SDK 中暴露 `OrderedSet`
- [ ] 运行回归测试
- [ ] 更新文档

**回滚方案**：
- 新类型，不影响现有代码
- 如果出现问题，只需移除新类型

#### **阶段 3：FSM 编译器启用**（1-2 周）

**目标**：默认启用 FSM 编译器

**实施步骤**：

**Week 1：测试和验证**
- [ ] 编写 FSM 编译器的完整测试（20+ 个）
- [ ] 在测试环境中启用
- [ ] 运行完整回归测试
- [ ] 性能测试

**Week 2：渐进式启用**
- [ ] 修改默认配置（`pvm_fsm: true`）
- [ ] 在 chain 中启用
- [ ] 监控执行情况
- [ ] 文档更新

**回滚方案**：
- 通过配置开关关闭
- 如果出现问题，立即回滚到 `pvm_fsm: false`

#### **阶段 4：Runner 系统**（10-12 周）

**目标**：实现 Runner 执行器，不影响现有消息传递

**实施步骤**：

**Week 1-4：Runner 执行器**
- [ ] 实现 Runner 守护进程
- [ ] 实现任务队列
- [ ] 编写单元测试（30+ 个）

**Week 5-7：LLM/HTTP 集成**
- [ ] 集成 LLM API
- [ ] 实现 HTTP 客户端
- [ ] 编写集成测试（20+ 个）

**Week 8-10：验证和共识**
- [ ] 实现 N-of-M 投票
- [ ] 实现结果聚合
- [ ] 编写测试（15+ 个）

**Week 11-12：Chain 集成**
- [ ] 集成到 chain
- [ ] 运行完整回归测试
- [ ] 端到端测试

**回滚方案**：
- 新模块，不影响现有消息传递
- 如果出现问题，可以禁用 Runner 功能

#### **阶段 5：Guard 验证**（2-3 周）

**目标**：实现 Guard 验证逻辑

**实施步骤**：

**Week 1-2：实现**
- [ ] 实现 Guard 验证逻辑
- [ ] 编写单元测试（20+ 个）
- [ ] 编写集成测试（10+ 个）

**Week 3：集成和测试**
- [ ] 在 chain 中集成（默认关闭）
- [ ] 运行回归测试
- [ ] 性能测试

**回滚方案**：
- 默认关闭，可选启用
- 如果出现问题，立即关闭

### 3.2 每个阶段的检查清单

#### **阶段开始前**

- [ ] 所有回归测试通过（100%）
- [ ] 代码覆盖率 ≥ 目标值
- [ ] 性能基准测试基线已建立
- [ ] 回滚方案已准备

#### **阶段进行中**

- [ ] 每日运行完整测试套件
- [ ] 代码覆盖率持续监控
- [ ] 性能基准测试持续监控
- [ ] 代码审查完成

#### **阶段结束时**

- [ ] 所有新功能测试通过
- [ ] 所有回归测试通过
- [ ] 代码覆盖率 ≥ 目标值
- [ ] 性能无回归
- [ ] 文档已更新
- [ ] 回滚方案已验证

### 3.3 升级决策流程

```
新功能开发
    │
    ├─> 编写测试（先写测试）
    │
    ├─> 实现功能（特性开关控制）
    │
    ├─> 单元测试通过？
    │   ├─ 否 ─> 修复 ─> 重新测试
    │   └─ 是 ─> 继续
    │
    ├─> 集成测试通过？
    │   ├─ 否 ─> 修复 ─> 重新测试
    │   └─ 是 ─> 继续
    │
    ├─> 回归测试通过？（100%）
    │   ├─ 否 ─> 修复 ─> 重新测试
    │   └─ 是 ─> 继续
    │
    ├─> 性能测试通过？
    │   ├─ 否 ─> 优化 ─> 重新测试
    │   └─ 是 ─> 继续
    │
    ├─> 代码审查通过？
    │   ├─ 否 ─> 修改 ─> 重新审查
    │   └─ 是 ─> 继续
    │
    └─> 合并到主分支
        │
        ├─> 监控生产环境（如果启用）
        │
        └─> 出现问题？
            ├─ 是 ─> 立即回滚
            └─ 否 ─> 完成
```

---

## 📊 第四部分：监控和告警

### 4.1 测试覆盖率监控

#### **目标覆盖率**

| 模块 | 当前 | 目标 | 关键路径目标 |
|------|------|------|------------|
| **pvm-runtime** | ~20% | 80% | 90% |
| **pvm-host** | ~15% | 80% | 90% |
| **vm/checkpoint** | ~40% | 85% | 95% |
| **vm/snapshot** | ~30% | 85% | 95% |
| **determinism** | ~10% | 80% | 90% |
| **continuation** | ~20% | 80% | 90% |
| **总体** | ~30% | 80% | 85% |

#### **覆盖率工具**

```bash
# 生成覆盖率报告
cargo llvm-cov --locked --lcov --output-path lcov.info

# 查看覆盖率
cargo llvm-cov --locked --summary-only

# CI 中检查覆盖率
cargo llvm-cov --locked --lcov --output-path lcov.info --fail-under-lines 80
```

#### **覆盖率门禁**

```yaml
# .github/workflows/coverage.yml
- name: Check coverage
  run: |
    cargo llvm-cov --locked --lcov --output-path lcov.info --fail-under-lines 80
    # 如果覆盖率低于 80%，CI 失败
```

### 4.2 性能监控

#### **性能基准测试**

```rust
// benches/performance.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn benchmark_checkpoint(c: &mut Criterion) {
    let vm = create_vm_with_state(1_000_000);
    
    c.bench_function("checkpoint_save_1mb", |b| {
        b.iter(|| {
            black_box(vm.save_checkpoint().unwrap());
        });
    });
}

criterion_group!(benches, benchmark_checkpoint);
criterion_main!(benches);
```

#### **性能回归检测**

```yaml
# .github/workflows/benchmark.yml
- name: Run benchmarks
  run: cargo bench
  
- name: Compare with baseline
  run: |
    # 与基线对比，如果性能下降 >5%，告警
    cargo bench -- --baseline main
```

#### **性能指标**

| 指标 | 当前基线 | 目标 | 告警阈值 |
|------|---------|------|---------|
| **Checkpoint 保存（1MB）** | 50ms | <100ms | >150ms |
| **Checkpoint 恢复（1MB）** | 60ms | <120ms | >180ms |
| **Chain 执行（简单合约）** | 10ms | <20ms | >30ms |
| **Chain 执行（复杂合约）** | 100ms | <200ms | >300ms |
| **SoftFloat 基本运算** | - | <2x 硬件浮点 | >3x 硬件浮点 |
| **SoftFloat 数学函数** | - | <2x 硬件浮点 | >3x 硬件浮点 |
| **Python 浮点运算（启用 SoftFloat）** | - | <2x 硬件浮点 | >3x 硬件浮点 |

### 4.3 回归测试监控

#### **测试通过率**

```yaml
# CI 配置
- name: Run all tests
  run: |
    cargo test --all
    # 如果任何测试失败，CI 失败
```

#### **测试执行时间**

```yaml
# 监控测试执行时间
- name: Test timing
  run: |
    cargo test --all -- --nocapture --test-threads=1 2>&1 | tee test_timing.log
    # 如果总时间 >30 分钟，告警
```

### 4.4 生产环境监控（如果适用）

#### **关键指标**

| 指标 | 监控方式 | 告警阈值 |
|------|---------|---------|
| **执行失败率** | 日志分析 | >1% |
| **执行时间 P99** | 指标收集 | >500ms |
| **内存使用** | 指标收集 | >2GB |
| **Checkpoint 失败率** | 日志分析 | >0.1% |

---

## 🚨 第五部分：回滚机制

### 5.1 回滚策略

#### **策略 1：配置开关回滚**（最快）

**适用场景**：新功能通过配置控制

**步骤**：
1. 修改配置，关闭新功能
2. 重启服务
3. 验证系统恢复正常

**时间**：< 5 分钟

#### **策略 2：代码回滚**（标准）

**适用场景**：代码问题

**步骤**：
1. 回滚到上一个稳定版本
2. 重新部署
3. 验证系统恢复正常

**时间**：< 15 分钟

#### **策略 3：数据库回滚**（最严重）

**适用场景**：数据损坏

**步骤**：
1. 恢复数据库备份
2. 回滚代码
3. 验证数据一致性

**时间**：< 1 小时

### 5.2 回滚检查清单

#### **回滚前**

- [ ] 确认问题影响范围
- [ ] 通知相关团队
- [ ] 准备回滚方案
- [ ] 备份当前状态

#### **回滚中**

- [ ] 执行回滚操作
- [ ] 监控系统状态
- [ ] 验证功能恢复

#### **回滚后**

- [ ] 确认系统稳定
- [ ] 分析问题原因
- [ ] 制定修复方案
- [ ] 更新文档

---

## 📝 第六部分：实施计划

### 6.1 时间线

| 阶段 | 时间 | 任务 | 负责人 |
|------|------|------|--------|
| **准备阶段** | Week 1-2 | 测试基础设施 | 测试团队 |
| **SoftFloat** | Week 3-6 | 集成和测试 | 核心团队 |
| **ordered_set** | Week 7-8 | 实现和测试 | 核心团队 |
| **FSM 启用** | Week 9-10 | 启用和验证 | 核心团队 |
| **Runner 系统** | Week 11-22 | 完整实现 | Runner 团队 |
| **Guard 验证** | Week 23-25 | 实现和测试 | 核心团队 |
| **测试完善** | 持续 | 提高覆盖率 | 测试团队 |

### 6.2 资源需求

#### **人员配置**

| 角色 | 人数 | 职责 |
|------|------|------|
| **核心开发** | 2-3 人 | 功能实现 |
| **测试工程师** | 2 人 | 测试编写和维护 |
| **Runner 开发** | 2-3 人 | Runner 系统实现 |
| **DevOps** | 1 人 | CI/CD 和监控 |

#### **工具和基础设施**

- [ ] CI/CD 平台（GitHub Actions / GitLab CI）
- [ ] 测试覆盖率工具（cargo-llvm-cov）
- [ ] 性能基准测试工具（criterion）
- [ ] 监控和告警系统
- [ ] 测试环境（多架构：x86、ARM）

### 6.3 里程碑

| 里程碑 | 时间 | 验收标准 |
|--------|------|---------|
| **M1: 测试基础设施** | Week 2 | 覆盖率 ≥30%，回归测试 100+ |
| **M2: SoftFloat 完成** | Week 6 | 集成完成，测试通过，可选启用 |
| **M3: ordered_set 完成** | Week 8 | 实现完成，测试通过 |
| **M4: FSM 启用** | Week 10 | 默认启用，测试通过 |
| **M5: Runner Alpha** | Week 16 | 基础功能可用 |
| **M6: Runner Beta** | Week 22 | 完整功能，测试通过 |
| **M7: Guard 完成** | Week 25 | 实现完成，测试通过 |
| **M8: 测试完善** | Week 26 | 覆盖率 ≥80% |

---

## 📚 第七部分：最佳实践

### 7.1 代码审查检查清单

#### **功能审查**

- [ ] 功能符合需求
- [ ] 代码逻辑正确
- [ ] 错误处理完善
- [ ] 边界情况处理

#### **测试审查**

- [ ] 单元测试覆盖关键路径
- [ ] 集成测试覆盖主要场景
- [ ] 回归测试通过
- [ ] 性能测试通过

#### **兼容性审查**

- [ ] API 向后兼容
- [ ] 配置向后兼容
- [ ] 数据格式向后兼容
- [ ] 不影响现有功能

#### **安全审查**

- [ ] 无安全漏洞
- [ ] 输入验证
- [ ] 资源限制
- [ ] 错误信息不泄露敏感信息

### 7.2 测试编写最佳实践

#### **单元测试**

```rust
// ✅ 好的实践
#[test]
fn test_function_with_clear_name() {
    // Arrange: 准备测试数据
    let input = create_test_input();
    
    // Act: 执行被测试的功能
    let result = function_under_test(input);
    
    // Assert: 验证结果
    assert_eq!(result, expected_output);
}

// ❌ 不好的实践
#[test]
fn test1() {  // 名称不清晰
    let r = f(i);  // 变量名不清晰
    assert!(r);  // 断言不明确
}
```

#### **集成测试**

```rust
// ✅ 好的实践：清晰的测试场景
#[tokio::test]
async fn test_chain_execution_with_state_persistence() {
    // 场景描述：验证状态在多次执行间持久化
    
    let executor = create_test_executor();
    let contract = load_test_contract();
    
    // 第一次执行：设置状态
    executor.execute(contract.clone(), b"set:key:value").await.unwrap();
    
    // 第二次执行：读取状态
    let result = executor.execute(contract, b"get:key").await.unwrap();
    assert_eq!(result.output, b"value");
}
```

#### **回归测试**

```rust
// ✅ 好的实践：测试已有功能的稳定性
#[tokio::test]
async fn regression_test_existing_feature_unchanged() {
    // 这个测试确保已有功能在升级后仍然工作
    // 如果这个测试失败，说明升级破坏了已有功能
    
    let executor = create_executor_with_existing_config();
    let result = executor.execute_existing_workflow().await;
    assert!(result.is_ok(), "Existing feature broken by upgrade");
}
```

### 7.3 文档更新要求

#### **代码变更时**

- [ ] 更新 API 文档
- [ ] 更新配置文档
- [ ] 更新迁移指南（如果有）
- [ ] 更新示例代码

#### **新功能时**

- [ ] 功能说明文档
- [ ] 使用示例
- [ ] 测试用例说明
- [ ] 性能特性说明

---

## ✅ 第八部分：验收标准

### 8.1 整体验收标准

#### **测试覆盖率**

- [ ] 单元测试覆盖率 ≥80%
- [ ] 关键路径覆盖率 ≥90%
- [ ] 集成测试覆盖率 ≥70%
- [ ] 回归测试 100+ 个

#### **测试通过率**

- [ ] 所有单元测试通过（100%）
- [ ] 所有集成测试通过（100%）
- [ ] 所有回归测试通过（100%）
- [ ] 所有端到端测试通过（100%）

#### **性能标准**

- [ ] 无性能回归（与基线对比）
- [ ] 关键路径性能达标
- [ ] 内存使用正常

#### **兼容性标准**

- [ ] 所有已有功能正常工作
- [ ] API 向后兼容
- [ ] 配置向后兼容
- [ ] 数据格式向后兼容

### 8.2 每个功能的验收标准

#### **SoftFloat**

- [ ] **单元测试 50+ 个，全部通过**
  - [ ] 基本运算测试（add, subtract, multiply, divide, negate, abs）- 10+ 个
  - [ ] 数学函数测试（sqrt, exp, ln, sin, cos, tan, asin, acos, atan, atan2）- 15+ 个
  - [ ] 双曲函数测试（sinh, cosh, tanh, asinh, acosh, atanh）- 6+ 个
  - [ ] 取整函数测试（floor, ceil, trunc, round）- 4+ 个
  - [ ] 特殊运算测试（modulo, floor_div, pow）- 5+ 个
  - [ ] 边界值测试（0, inf, nan, 极小值, 极大值）- 5+ 个
  - [ ] 确定性测试（位级一致性）- 3+ 个
  - [ ] 精度测试 - 2+ 个
  - [ ] 属性测试（proptest）- 3+ 个

- [ ] **跨架构测试通过**（x86_64, ARM64, RISC-V）
  - [ ] 位级一致性验证（相同输入产生相同位模式）
  - [ ] 在不同架构上运行相同测试，结果位级相同
  - [ ] CI/CD 中配置多架构测试环境

- [ ] **性能测试通过**（<2x 硬件浮点）
  - [ ] 基本运算性能基准（add, multiply, divide）
  - [ ] 数学函数性能基准（sqrt, sin, cos, exp, ln）
  - [ ] 完整 Python 程序性能基准
  - [ ] 性能报告生成

- [ ] **集成测试通过**
  - [ ] SoftFloat 与 Python float 类型集成
  - [ ] SoftFloat 与 math 模块集成
  - [ ] SoftFloat 与 Checkpoint/Resume 兼容
  - [ ] SoftFloat 配置开关正常工作

- [ ] **回归测试通过**
  - [ ] 启用 SoftFloat 后，现有浮点运算仍然正确
  - [ ] 不影响整数运算
  - [ ] 配置开关正常工作
  - [ ] 性能可接受

- [ ] **向后兼容性**
  - [x] 默认启用（确定性执行时）
  - [ ] 可通过配置禁用
  - [ ] 不影响现有功能
  - [ ] API 向后兼容

- [ ] **文档完善**
  - [ ] SoftFloat 使用说明
  - [ ] 性能影响说明
  - [ ] 配置选项说明
  - [ ] 迁移指南（如果需要）

#### **ordered_set**

- [ ] 单元测试 20+ 个，全部通过
- [ ] 与现有 set 兼容
- [ ] 性能测试通过
- [ ] 回归测试通过

#### **FSM 编译器**

- [ ] 单元测试 20+ 个，全部通过
- [ ] 集成测试通过
- [ ] 默认启用，不影响现有功能
- [ ] 性能测试通过
- [ ] 回归测试通过

#### **Runner 系统**

- [ ] 单元测试 30+ 个，全部通过
- [ ] 集成测试 20+ 个，全部通过
- [ ] 端到端测试通过
- [ ] 性能测试通过
- [ ] 不影响现有消息传递

#### **Guard 验证**

- [ ] 单元测试 20+ 个，全部通过
- [ ] 集成测试 10+ 个，全部通过
- [ ] 默认关闭，可选启用
- [ ] 性能测试通过
- [ ] 回归测试通过

---

## 📋 总结

### 核心原则

1. **预防为主**：通过特性开关、API 版本化、配置隔离等方式，最小化对现有功能的影响
2. **测试驱动**：先写测试，再改代码；高覆盖率保证质量
3. **渐进式升级**：分阶段、小步快跑、及时验证
4. **快速回滚**：每个阶段都有回滚方案

### 关键指标

- **测试覆盖率**：30% → 80%
- **回归测试**：14 个 → 100+ 个
- **集成测试**：部分 → 20-30 个
- **端到端测试**：示例代码 → 10-15 个自动化测试

### 时间线

- **准备阶段**：2 周
- **核心功能升级**：20-24 周
- **测试完善**：持续进行

### 成功标准

- ✅ 所有已有功能正常工作
- ✅ 测试覆盖率 ≥80%
- ✅ 所有测试通过
- ✅ 无性能回归
- ✅ 向后兼容

---

## 📝 附录：SoftFloat 集成测试详细计划

### A.1 SoftFloat 集成状态（2026-01-24 更新）

#### ✅ **已完成**

1. **实现完成**
   - ✅ 集成纯 Rust `softfloat` crate（无 C 依赖）
   - ✅ 创建 SoftFloat 包装模块（`crates/vm/src/softfloat.rs`）
   - ✅ 集成到浮点运算（`crates/vm/src/builtins/float.rs`）
   - ✅ 集成到数学库（`crates/stdlib/src/math.rs`）
   - ✅ 在 Settings 中添加 `enable_softfloat` 配置
   - ✅ 在 DeterminismOptions 中默认启用（确定性执行时）

2. **配置完成**
   - ✅ 配置开关实现（可通过 `enable_softfloat` 控制）
   - ✅ 默认启用（确定性执行时）
   - ✅ 向后兼容（不影响现有功能）

#### ⏳ **待完成测试**

1. **单元测试**（50+ 个）
   - [ ] 基本运算测试（10+ 个）
   - [ ] 数学函数测试（15+ 个）
   - [ ] 双曲函数测试（6+ 个）
   - [ ] 取整函数测试（4+ 个）
   - [ ] 特殊运算测试（5+ 个）
   - [ ] 边界值测试（5+ 个）
   - [ ] 确定性测试（3+ 个）
   - [ ] 精度测试（2+ 个）
   - [ ] 属性测试（proptest，3+ 个）

2. **集成测试**（10+ 个）
   - [ ] SoftFloat 与 Python float 类型集成
   - [ ] SoftFloat 与 math 模块集成
   - [ ] 跨平台一致性测试
   - [ ] 复杂计算测试
   - [ ] 确定性执行测试

3. **回归测试**（5+ 个）
   - [ ] 向后兼容性测试
   - [ ] 整数运算不受影响测试
   - [ ] 配置开关测试
   - [ ] 性能可接受性测试
   - [ ] Checkpoint 兼容性测试

4. **性能基准测试**
   - [ ] 基本运算性能对比
   - [ ] 数学函数性能对比
   - [ ] Python 程序性能对比
   - [ ] 性能报告生成

5. **跨平台测试**
   - [ ] x86_64 平台测试
   - [ ] ARM64 平台测试
   - [ ] 位级一致性验证

### A.2 测试文件结构

```
tests/
├── unit/
│   └── softfloat.rs              # SoftFloat 单元测试（50+ 个）
├── integration/
│   ├── softfloat_basic.rs        # 基本集成测试
│   ├── softfloat_math.rs         # 数学模块集成测试
│   └── softfloat_determinism.rs  # 确定性测试
├── regression/
│   └── softfloat_compatibility.rs # 向后兼容性回归测试
└── benchmarks/
    └── softfloat_performance.rs   # 性能基准测试
```

### A.3 测试执行计划

#### **阶段 1：单元测试**（Week 1-2）
- 编写所有单元测试
- 确保所有测试通过
- 代码覆盖率 ≥90%（softfloat 模块）

#### **阶段 2：集成测试**（Week 3）
- 编写集成测试
- 验证与 Python 的集成
- 验证跨平台一致性

#### **阶段 3：回归测试**（Week 3）
- 编写回归测试
- 验证向后兼容性
- 验证性能可接受性

#### **阶段 4：性能基准**（Week 3-4）
- 建立性能基线
- 持续监控性能
- 生成性能报告

#### **阶段 5：跨平台验证**（Week 4）
- 在多架构上运行测试
- 验证位级一致性
- 更新 CI/CD 配置

### A.4 测试验收标准

#### **单元测试**
- ✅ 所有 50+ 个测试通过
- ✅ 代码覆盖率 ≥90%
- ✅ 边界值测试完整
- ✅ 确定性测试通过

#### **集成测试**
- ✅ 所有 10+ 个测试通过
- ✅ Python 集成正常
- ✅ math 模块集成正常
- ✅ 跨平台一致性验证通过

#### **回归测试**
- ✅ 所有 5+ 个测试通过
- ✅ 向后兼容性验证通过
- ✅ 性能可接受（<2x 硬件浮点）

#### **性能基准**
- ✅ 性能报告生成
- ✅ 性能指标达标
- ✅ 无性能回归

#### **跨平台测试**
- ✅ 多架构测试通过
- ✅ 位级一致性验证通过
- ✅ CI/CD 集成完成

---

*本方案将根据实际情况持续更新和完善。*  
*最后更新：2026-01-24（添加 SoftFloat 详细测试计划）*
