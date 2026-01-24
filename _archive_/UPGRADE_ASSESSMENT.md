# PVM 子模块升级评估报告

## 执行时间
评估日期：2025-01-XX

## 一、PVM 子模块更新概览

### 1.1 版本信息
- **当前 PVM 版本**: v0.1.3-4-gb28d4d5 (commit: b28d4d5)
- **PVM 工作区版本**: 0.4.0
- **主要更新内容**:
  - 添加 continuation 和 checkpoint 功能
  - 增强确定性执行选项
  - 更新 Cargo.toml 配置（版本、edition、rust-version）

### 1.2 关键配置变化

| 配置项 | PVM 新值 | Node 当前值 | 兼容性 |
|--------|---------|------------|--------|
| Rust Edition | 2024 | 2021 | ⚠️ **不兼容** |
| Rust Version | 1.89.0 | 1.70.0 | ✅ 系统已满足 (1.92.0) |
| Version | 0.4.0 | 0.0.16 | ✅ 兼容 |

## 二、API 变化分析

### 2.1 HostApi Trait
✅ **无破坏性变化**
- `HostApi` trait 定义保持不变
- 所有必需方法已实现：`send_message`, `schedule_timer`, `cancel_timer`
- `HostContext` 结构体字段完整（包含 `actor_addr`, `msg_id`, `nonce`）

### 2.2 pvm-runtime API
✅ **向后兼容**
- `execute_tx()` 函数签名未变
- `execute_tx_with_options()` 函数签名未变
- `ExecutionOptions` 新增可选字段 `continuation`，默认值兼容

### 2.3 新增功能
🆕 **可选新功能**
- `ContinuationOptions`: 支持 checkpoint/resume
- `RuntimeConfig`: 运行时配置
- `DeterminismOptions`: 增强的确定性选项

## 三、需要升级的项目

### 3.1 🔴 必须升级（阻塞性问题）

#### 1. Rust Edition 不兼容
**问题**: PVM 使用 Rust edition 2024，但 Node 项目使用 2021

**影响**: 
- 虽然子模块可以独立编译，但可能导致：
  - 某些新语法特性无法使用
  - 潜在的编译警告
  - 未来兼容性问题

**建议**:
```toml
# Cargo.toml
[workspace.package]
edition = "2024"  # 从 "2021" 升级
```

**风险评估**: 
- ⚠️ 中等风险：需要测试所有代码是否兼容 2024 edition
- 建议先在小范围测试，确认无问题后再全局升级

#### 2. Rust Version 要求
**当前状态**: ✅ 系统 Rust 版本 1.92.0 已满足 PVM 要求的 1.89.0

**建议**: 更新 `Cargo.toml` 中的 `rust-version` 以反映实际要求
```toml
[workspace.package]
rust-version = "1.89.0"  # 从 "1.70.0" 升级
```

### 3.2 🟡 建议升级（功能增强）

#### 1. 集成 pvm-runtime
**当前状态**: Node 项目已准备好集成 `pvm-runtime`，但尚未实际使用

**建议**: 
- 在 `chain/Cargo.toml` 中添加 `pvm-runtime` 依赖
- 更新 `chain/src/pvm_executor.rs` 中的 TODO 代码
- 启用 continuation 和 checkpoint 功能（可选）

**示例代码更新**:
```rust
// chain/Cargo.toml
pvm-runtime = { path = "../pvm/crates/pvm-runtime" }

// chain/src/pvm_executor.rs
use pvm_runtime::{execute_tx_with_options, ExecutionOptions, ContinuationOptions};
use rustpython_vm::vm::ContinuationMode;

pub async fn execute_handler<S: StateStore>(
    &self,
    ctx: &mut PvmExecutionContext<'_, S>,
    payload: &[u8],
    handler: &str,
) -> Result<Bytes, HostError> {
    use pvm_runtime::{execute_tx_with_options, ExecutionOptions};
    let mut host = CowboyHost::new(ctx);
    let input = payload.to_vec();
    let output = execute_tx_with_options(
        &mut host,
        &ctx.actor.code,
        &input,
        &ExecutionOptions {
            entrypoint: Some(handler.to_string()),
            module_name: "actor".to_string(),
            input_var: "__pvm_input__".to_string(),
            output_var: "__pvm_output__".to_string(),
            deterministic: true,
            continuation: Some(ContinuationOptions {
                mode: ContinuationMode::Fsm,
                checkpoint_key: Some(b"checkpoint".to_vec()),
                ..Default::default()
            }),
            ..Default::default()
        }
    )?;
    Ok(output)
}
```

#### 2. 利用新功能
**Continuation/Checkpoint 功能**:
- 支持长时间运行的 actor 执行
- 支持状态快照和恢复
- 适合需要暂停/恢复的场景

**使用场景**:
- 长时间运行的批处理任务
- 需要中断和恢复的复杂计算
- 调试和开发时的状态保存

### 3.3 🟢 可选升级（优化）

#### 1. 更新依赖版本号
虽然不影响功能，但建议保持版本号一致性：
```toml
[workspace.package]
version = "0.0.17"  # 或保持当前版本
```

#### 2. 代码清理
- 移除未使用的导入
- 更新注释和文档
- 添加新功能的测试用例

## 四、升级步骤建议

### 阶段 1: 基础兼容性升级（必须）
1. ✅ 更新 `rust-version` 到 1.89.0
2. ⚠️ 评估并升级 `edition` 到 2024（需要充分测试）
3. ✅ 验证现有代码编译通过
4. ✅ 运行现有测试套件

### 阶段 2: 功能集成（建议）
1. 添加 `pvm-runtime` 依赖
2. 更新 `PvmExecutor` 实现
3. 添加 continuation 支持（可选）
4. 更新示例代码

### 阶段 3: 测试和验证（必须）
1. 运行所有单元测试
2. 运行集成测试
3. 测试示例代码
4. 性能测试（如果有）

## 五、风险评估

### 5.1 高风险项
- ⚠️ **Rust Edition 升级**: 需要全面测试，可能有隐藏的兼容性问题

### 5.2 中风险项
- 🟡 **pvm-runtime 集成**: 需要充分测试执行逻辑
- 🟡 **Continuation 功能**: 新功能，需要验证正确性

### 5.3 低风险项
- 🟢 **版本号更新**: 纯配置变更
- 🟢 **依赖更新**: 向后兼容

## 六、测试清单

### 6.1 编译测试
- [ ] 所有 crate 编译通过
- [ ] 无编译警告（或可接受的警告）
- [ ] 示例代码编译通过

### 6.2 功能测试
- [ ] PVM executor 基本功能
- [ ] Actor 执行流程
- [ ] 存储操作
- [ ] 事件发射
- [ ] 消息发送
- [ ] 定时器调度

### 6.3 集成测试
- [ ] 端到端 actor 部署和执行
- [ ] 多 actor 交互
- [ ] 状态持久化
- [ ] Gas 计量

### 6.4 新功能测试（如果启用）
- [ ] Continuation 功能
- [ ] Checkpoint 保存和恢复
- [ ] 确定性执行

## 七、总结和建议

### 7.1 立即行动项
1. ✅ **更新 rust-version**: 从 1.70.0 升级到 1.89.0（低风险）
2. ⚠️ **评估 edition 升级**: 从 2021 升级到 2024（需要测试）

### 7.2 短期计划（1-2周）
1. 集成 `pvm-runtime` 并启用实际 Python 执行
2. 更新 `PvmExecutor` 实现
3. 添加基本测试覆盖

### 7.3 长期计划（1-2月）
1. 启用 continuation/checkpoint 功能
2. 优化执行性能
3. 添加更多示例和文档

### 7.4 注意事项
- ⚠️ Edition 升级需要谨慎，建议先在开发分支测试
- ✅ 当前 API 兼容，可以逐步迁移
- 📝 建议保持 PVM 子模块更新到最新稳定版本

## 八、参考资源

- PVM 更新日志: `pvm/` 目录下的 git log
- PVM README: `pvm/README.md`
- PVM 示例: `pvm/examples/`
- Continuation 文档: `pvm/crates/pvm-runtime/src/continuation.rs`
