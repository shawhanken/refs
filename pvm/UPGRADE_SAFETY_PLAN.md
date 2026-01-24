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
| **SoftFloat 集成** | 所有浮点运算 | 🔴 极高 | 1. 特性开关<br>2. 完整回归测试<br>3. 性能对比 |
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
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_softfloat_addition() {
        let a = SoftFloat::from(1.5);
        let b = SoftFloat::from(2.3);
        let result = a + b;
        assert_eq!(result, SoftFloat::from(3.8));
    }
    
    #[test]
    fn test_softfloat_determinism() {
        // 在不同架构上应该产生相同结果
        let result = SoftFloat::sin(0.1);
        assert_eq!(result.to_bits(), 0x3d9eb851);  // 位级相同
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

criterion_group!(benches, regression_benchmark_checkpoint, regression_benchmark_execution);
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
- [ ] 集成 Berkeley SoftFloat 库
- [ ] 实现 `SoftFloat` 类型
- [ ] 编写单元测试（30+ 个）
- [ ] 性能基准测试

**Week 3：集成测试**
- [ ] 在测试环境中启用 SoftFloat
- [ ] 运行完整回归测试套件
- [ ] 验证不影响现有功能
- [ ] 性能对比测试

**Week 4：渐进式启用**
- [ ] 在 chain 中添加配置开关
- [ ] 默认关闭，可选启用
- [ ] 监控生产环境（如果启用）
- [ ] 文档更新

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

- [ ] 单元测试 30+ 个，全部通过
- [ ] 跨架构测试通过（x86、ARM）
- [ ] 性能测试通过（<2x 硬件浮点）
- [ ] 回归测试通过
- [ ] 可选启用，不影响现有功能

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

*本方案将根据实际情况持续更新和完善。*
