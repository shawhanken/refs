# PVM 升级状态

## 已完成的升级

### ✅ 1. 配置升级
- [x] 更新 `rust-version` 从 1.70.0 到 1.89.0
- [x] 更新 `edition` 从 2021 到 2024
- [x] 在根 `Cargo.toml` 中排除 `pvm` 子模块（避免 workspace 冲突）

### ✅ 2. 依赖添加
- [x] 在 `chain/Cargo.toml` 中添加 `pvm-runtime` 依赖

### ✅ 3. 代码更新
- [x] 更新 `PvmExecutor` 实现以使用 `pvm-runtime`
- [x] 添加必要的导入和类型

## 当前问题

### ⚠️ 编译错误：借用检查器问题

**错误类型**: `E0499` 和 `E0503` - 借用冲突

**问题描述**:
`execute_tx_with_options` 通过 `HostGuard::install` 将 host 安装到 thread-local 存储中，这导致编译器认为 host 的借用会持续到函数返回。但实际上，当 `execute_tx_with_options` 返回时，`HostGuard` 应该已经被 drop，从而释放借用。

**错误位置**:
- `chain/src/execution.rs:684-696` - 在 `execute_handler` 返回后访问 `pvm_ctx` 的字段

**可能的解决方案**:

1. **使用显式作用域**（已尝试，但可能不够）:
   ```rust
   let output = {
       let mut host = CowboyHost::new(ctx);
       execute_tx_with_options(&mut host, &actor_code, &input, &options)?
   };
   ```

2. **重构代码结构**:
   - 在 `execute_handler` 返回之前提取所有需要的数据
   - 或者改变 `PvmExecutionContext` 的设计，避免长期借用

3. **使用 `unsafe` 代码**（不推荐）:
   - 仅在确认安全的情况下使用

4. **等待 Rust 编译器改进**:
   - 这可能是一个已知的借用检查器限制

## 下一步行动

1. **解决借用检查器问题**
   - 尝试不同的代码结构
   - 考虑重构 `PvmExecutionContext` 的设计

2. **测试**
   - 一旦编译通过，运行所有测试
   - 验证 PVM 执行功能

3. **文档更新**
   - 更新相关文档以反映新功能
   - 添加 continuation/checkpoint 使用示例

## 参考文件

- 升级评估报告: `refs/chain/UPGRADE_ASSESSMENT.md`
- PVM Host API 参考: `refs/pvm/api/host-api-reference.md`
- PVM Runtime API 参考: `refs/pvm/api/runtime-api-reference.md`
- Chain PVM Host 实现: `refs/chain/api/pvm-host-implementation.md`
