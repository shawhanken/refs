# SoftFloat 测试文档

**最后更新**：2026-01-24  
**版本**：1.0

## 📋 概述

本文档描述了 SoftFloat 集成的完整测试策略，包括单元测试、集成测试、回归测试、属性测试和性能基准测试。

## 🧪 测试类型

### 1. 单元测试

**位置**：`crates/vm/src/softfloat.rs` (模块内 `#[cfg(test)]`)

**数量**：38 个测试

**覆盖范围**：
- ✅ 基本运算（6个）：add, subtract, multiply, divide, negate, abs
- ✅ 数学函数（10个）：sqrt, exp, ln, sin, cos, tan, asin, acos, atan, atan2
- ✅ 双曲函数（6个）：sinh, cosh, tanh, asinh, acosh, atanh
- ✅ 取整函数（4个）：floor, ceil, trunc, round
- ✅ 特殊运算（3个）：modulo, floor_div, pow
- ✅ 边界值（5个）：zero, infinity, nan, very_small, very_large
- ✅ 确定性（2个）：determinism_basic_ops, determinism_math_funcs
- ✅ 精度（2个）：precision, precision_accumulation

**运行命令**：
```bash
cargo test --package rustpython-vm --lib softfloat::tests
```

**预期结果**：38 个测试全部通过

### 2. 回归测试

**位置**：`crates/pvm-runtime/tests/regression/softfloat.rs`

**数量**：6 个测试（2 个通过，4 个标记为 `#[ignore]`，需要 stdlib）

**测试列表**：
1. ✅ `regression_test_softfloat_backward_compatibility` - 向后兼容性
2. ✅ `regression_test_softfloat_integer_operations` - 整数运算不受影响
3. ⏸️ `regression_test_softfloat_feature_flag` - 功能开关（需要 stdlib）
4. ⏸️ `regression_test_softfloat_performance_acceptable` - 性能可接受性（需要 stdlib）
5. ⏸️ `regression_test_softfloat_with_checkpoint` - Checkpoint 兼容性（需要 stdlib）
6. ⏸️ `regression_test_softfloat_determinism` - 确定性执行（需要 stdlib）

**运行命令**：
```bash
# 运行所有回归测试
cargo test --package pvm-runtime --test lib regression::softfloat

# 运行被忽略的测试（需要 stdlib）
cargo test --package pvm-runtime --test lib regression::softfloat -- --ignored
```

### 3. 集成测试

**位置**：`crates/pvm-runtime/tests/integration/softfloat.rs`

**数量**：8 个测试（1 个通过，7 个标记为 `#[ignore]`，需要 stdlib）

**测试列表**：
1. ✅ `integration_test_softfloat_basic_math` - 基本数学运算集成
2. ⏸️ `integration_test_softfloat_math_module` - math 模块集成
3. ⏸️ `integration_test_softfloat_cross_platform` - 跨平台一致性
4. ✅ `integration_test_softfloat_float_precision` - 浮点精度
5. ⏸️ `integration_test_softfloat_complex_calculation` - 复杂计算
6. ⏸️ `integration_test_softfloat_deterministic_across_runs` - 确定性执行
7. ⏸️ `integration_test_softfloat_math_functions` - 各种数学函数
8. ⏸️ `integration_test_softfloat_edge_cases` - 边界值处理

**运行命令**：
```bash
cargo test --package pvm-runtime --test lib integration::softfloat
```

### 4. 属性测试

**位置**：`crates/pvm-runtime/tests/regression/softfloat_proptest.rs`

**数量**：19 个属性测试

**测试属性**：
- ✅ 加法交换律和结合律
- ✅ 乘法交换律
- ✅ 零和一的特殊值
- ✅ 取反和绝对值性质
- ✅ 平方根性质
- ✅ 指数和对数性质
- ✅ 取整函数性质
- ✅ 确定性验证
- ✅ 模运算性质

**运行命令**：
```bash
cargo test --package pvm-runtime --test lib regression::softfloat_proptest
```

**预期结果**：19 个测试全部通过

### 5. 性能基准测试

**位置**：`crates/vm/benches/softfloat.rs`

**基准测试组**：
1. **基本运算** (`softfloat_basic_ops`)
   - hardware_add vs softfloat_add
   - hardware_multiply vs softfloat_multiply
   - hardware_divide vs softfloat_divide

2. **数学函数** (`softfloat_math_funcs`)
   - hardware_sqrt vs softfloat_sqrt
   - hardware_sin vs softfloat_sin
   - hardware_exp vs softfloat_exp
   - hardware_ln vs softfloat_ln

3. **取整函数** (`softfloat_rounding`)
   - hardware_floor vs softfloat_floor
   - hardware_ceil vs softfloat_ceil

4. **复杂计算** (`softfloat_complex`)
   - hardware_complex vs softfloat_complex

5. **累积运算** (`softfloat_accumulation`)
   - hardware_accumulate vs softfloat_accumulate

**运行命令**：
```bash
# 运行所有基准测试
cargo bench --package rustpython-vm --bench softfloat

# 运行特定基准测试组
cargo bench --package rustpython-vm --bench softfloat softfloat_basic_ops
```

**性能目标**：SoftFloat 操作应不超过硬件浮点操作的 2 倍时间

## 🌍 跨平台测试

**工作流文件**：`.github/workflows/softfloat-cross-platform.yml`

**支持的架构**：
- x86_64-unknown-linux-gnu
- aarch64-unknown-linux-gnu

**测试内容**：
- 单元测试跨平台一致性
- 属性测试跨平台一致性
- 位级一致性验证

**触发条件**：
- 修改 SoftFloat 相关文件时自动触发
- 手动触发（workflow_dispatch）

## 📊 测试统计

| 测试类型 | 数量 | 通过 | 失败 | 忽略 | 状态 |
|---------|------|------|------|------|------|
| 单元测试 | 38 | 38 | 0 | 0 | ✅ |
| 回归测试 | 6 | 2 | 0 | 4 | ✅ |
| 集成测试 | 8 | 1 | 0 | 7 | ✅ |
| 属性测试 | 19 | 19 | 0 | 0 | ✅ |
| 性能基准 | 5 组 | - | - | - | ✅ |
| **总计** | **76+** | **60** | **0** | **11** | **✅** |

## 🚀 CI/CD 集成

### GitHub Actions 工作流

1. **主 CI 工作流** (`.github/workflows/ci.yml`)
   - 构建测试
   - 运行所有 SoftFloat 测试
   - 性能基准测试（仅 main/master 分支）

2. **跨平台测试工作流** (`.github/workflows/softfloat-cross-platform.yml`)
   - 多架构测试
   - 位级一致性验证

### 运行测试

```bash
# 本地运行所有测试
cargo test --package rustpython-vm --lib softfloat::tests
cargo test --package pvm-runtime --test lib regression::softfloat
cargo test --package pvm-runtime --test lib regression::softfloat_proptest
cargo test --package pvm-runtime --test lib integration::softfloat

# 运行性能基准测试
cargo bench --package rustpython-vm --bench softfloat

# 运行被忽略的测试（需要 stdlib）
cargo test --package pvm-runtime --test lib regression::softfloat -- --ignored
cargo test --package pvm-runtime --test lib integration::softfloat -- --ignored
```

## 📈 性能监控

性能基准测试结果存储在 `target/criterion/` 目录中，包含：
- HTML 报告
- 性能对比数据
- 历史趋势

**性能目标**：
- 基本运算：< 2x 硬件浮点
- 数学函数：< 3x 硬件浮点
- 复杂计算：< 2.5x 硬件浮点

## 🔍 故障排查

### 常见问题

1. **属性测试失败**
   - 检查是否包含 NaN 或无穷大值
   - 使用 `prop_assume!` 过滤无效输入

2. **跨平台测试失败**
   - 验证位级一致性
   - 检查架构特定的浮点行为

3. **性能基准测试超时**
   - 减少迭代次数
   - 使用 `--quick` 模式

## 📝 维护指南

### 添加新测试

1. **单元测试**：在 `crates/vm/src/softfloat.rs` 的 `#[cfg(test)]` 模块中添加
2. **回归测试**：在 `crates/pvm-runtime/tests/regression/softfloat.rs` 中添加
3. **集成测试**：在 `crates/pvm-runtime/tests/integration/softfloat.rs` 中添加
4. **属性测试**：在 `crates/pvm-runtime/tests/regression/softfloat_proptest.rs` 中添加
5. **性能基准**：在 `crates/vm/benches/softfloat.rs` 中添加

### 更新测试

- 定期运行所有测试确保通过
- 更新性能基准基线
- 检查跨平台一致性

## 📚 相关文档

- [PVM 实现计划](../refs/pvm/2026-01-24_PVM_IMPLEMENTATION_PLAN.md)
- [SoftFloat 源码](../crates/vm/src/softfloat.rs)

---

*本文档将随着测试的完善持续更新。*
