# Stack Overflow 问题修复总结

**修复日期**: 2026-01-19  
**问题**: PVM 执行时栈溢出  
**解决方案**: 增加线程栈大小到 16 MiB

---

## 📋 问题总结

### 错误现象
```
thread 'tokio-runtime-worker' has overflowed its stack
fatal runtime error: stack overflow, aborting
```

### 发生位置
- **文件**: `chain/src/execution.rs:603`
- **函数**: `execute_actor_handler_impl`
- **场景**: 执行 actor instruction 时调用 PVM

### 根本原因
**PVM（基于 RustPython）执行 Python 代码需要大量栈空间**

原因细节：
1. Python 解释器的递归调用
2. 对象序列化/反序列化（snapshot）的深度遍历
3. Tokio worker 线程默认栈大小（2 MiB）不足

---

## ✅ 解决方案

### 采用方案：环境变量 RUST_MIN_STACK

**原因**：
- ✅ 实现最简单，无需修改代码
- ✅ 立即生效
- ✅ 风险最低

### 修改内容

**文件**: `/home/ubuntu/workspace/node/test2.sh`

**修改前**:
```bash
RUST_BACKTRACE=1 cargo run --bin validator -- --peers=/home/ubuntu/workspace/node/test2/peers.yaml --config=/home/ubuntu/workspace/node/test2/8fd31606c3d46cbf24695dd4617b5d4ac1ee0f6a61c410d638b3151556b5dc21.yaml
```

**修改后**:
```bash
#!/bin/bash

# 设置栈大小为 16 MiB (16 * 1024 * 1024 = 16777216)
# 解决 PVM 执行时的 stack overflow 问题
export RUST_MIN_STACK=16777216

# 运行 validator
RUST_BACKTRACE=1 cargo run --bin validator -- --peers=/home/ubuntu/workspace/node/test2/peers.yaml --config=/home/ubuntu/workspace/node/test2/8fd31606c3d46cbf24695dd4617b5d4ac1ee0f6a61c410d638b3151556b5dc21.yaml
```

### 关键参数
```bash
RUST_MIN_STACK=16777216  # 16 MiB = 16 * 1024 * 1024 字节
```

---

## 🔍 技术细节

### 栈大小对比
| 环境 | 默认栈大小 | 修改后栈大小 |
|-----|-----------|------------|
| Rust 主线程 | 8 MiB | 16 MiB |
| Tokio worker | 2 MiB | 16 MiB |
| **增加倍数** | - | **8x** |

### 内存影响评估
假设 validator 配置：
- Worker 线程数：4-8 个
- 栈大小：16 MiB/线程
- **总栈内存**：64-128 MiB

**结论**：内存开销可接受，远小于 JVM 或其他区块链节点

---

## 🎯 其他可选方案（未采用）

### 方案1：修改 Tokio Runtime 配置
```rust
// 如果 commonware_runtime 支持
let cfg = tokio::Config::default()
    .with_thread_stack_size(16 * 1024 * 1024)  // 假设有此方法
    .with_worker_threads(config.worker_threads);
```

**未采用原因**：
- ⚠️ commonware_runtime 可能不支持此配置
- ⚠️ 需要修改代码和测试

### 方案2：使用独立任务栈
```rust
tokio::task::Builder::new()
    .stack_size(16 * 1024 * 1024)
    .spawn(async move {
        // PVM execution
    })
```

**未采用原因**：
- ⚠️ 需要大量代码重构
- ⚠️ 增加任务调度开销
- ⚠️ 数据传递复杂

### 方案3：优化 PVM 代码
优化 RustPython snapshot 逻辑，减少栈使用

**未采用原因**：
- ⚠️ 工作量巨大
- ⚠️ 需要深入理解 RustPython 内部
- ⚠️ 可能影响功能正确性

---

## 📊 验证方法

### 测试步骤
```bash
# 1. 确保脚本可执行
chmod +x /home/ubuntu/workspace/node/test2.sh

# 2. 运行测试
./test2.sh

# 3. 观察日志
# 应该看到：
# - validator 启动成功
# - 加载配置和 peers
# - 处理区块
# - 执行 actor instruction
# - 无 stack overflow 错误
```

### 成功标志
```
✅ 2026-01-19T04:41:50.801725Z  INFO cowboy_chain::execution: executing transactions
✅ 2026-01-19T04:41:50.802250Z  INFO cowboy_chain::execution: executing actor instruction
✅ (继续执行，无崩溃)
```

### 如果仍然失败
```bash
# 增加到 32 MiB
export RUST_MIN_STACK=33554432
```

---

## 📝 后续建议

### 短期（当前版本）
- ✅ **已完成**：修改 test2.sh 添加 RUST_MIN_STACK
- ⏳ **待验证**：运行测试确认问题解决
- ⏳ **待文档**：在部署文档中说明此配置要求

### 中期（下一个版本）
- 📌 研究 commonware_runtime 是否支持栈大小配置
- 📌 如果支持，在代码中直接配置（更专业）
- 📌 添加运行时检测，如果栈不足给出友好提示

### 长期（优化）
- 📌 Profile PVM 执行，确定栈使用热点
- 📌 与 RustPython 社区合作，优化栈使用
- 📌 考虑使用 JIT 或其他优化技术

---

## 🔗 相关文档

- `STACK_OVERFLOW_ANALYSIS.md` - 详细的技术分析
- `IMPLEMENTATION_SUMMARY.md` - PVM 集成实施总结
- `TEST_REPORT.md` - 测试报告
- `INTEGRATION_VERIFICATION.md` - 集成验证报告

---

## 📚 技术背景

### 为什么 PVM 比其他 VM 需要更多栈？

| VM 类型 | 栈使用 | 原因 |
|---------|--------|------|
| **以太坊 EVM** | 低 | 简单的基于栈的 VM，指令固定 |
| **Solana SVM** | 低 | eBPF VM，有严格的执行限制 |
| **WASM** | 中 | 线性内存模型，栈使用可预测 |
| **Cowboy PVM** | 高 | 完整 Python VM，动态类型，递归多 |

### RustPython 栈使用特点
1. **动态类型系统**：每个操作都需要类型检查和转换
2. **垃圾回收**：对象图遍历
3. **异常处理**：栈展开
4. **Snapshot 序列化**：深度优先遍历对象图

---

## ⚠️ 重要提醒

### 生产环境部署
在生产环境部署时，务必：

1. **设置环境变量**
```bash
export RUST_MIN_STACK=16777216
```

2. **systemd 服务配置**
```ini
[Service]
Environment="RUST_MIN_STACK=16777216"
ExecStart=/path/to/validator --config=...
```

3. **Docker 配置**
```dockerfile
ENV RUST_MIN_STACK=16777216
```

4. **监控栈使用**
```bash
# 定期检查
cat /proc/<pid>/status | grep Stack
```

---

## ✅ 修复状态

| 项目 | 状态 | 说明 |
|-----|------|------|
| **问题识别** | ✅ 完成 | 明确是 PVM 栈溢出 |
| **根因分析** | ✅ 完成 | 详细技术分析 |
| **解决方案** | ✅ 完成 | 修改 test2.sh |
| **文档编写** | ✅ 完成 | 本文档 |
| **验证测试** | ⏳ 待进行 | 需要运行 test2.sh |
| **生产部署** | ⏳ 待进行 | 更新部署脚本 |

---

**总结**: 通过设置 `RUST_MIN_STACK=16777216`，将线程栈大小从默认的 2 MiB 增加到 16 MiB，解决 PVM 执行时的栈溢出问题。这是一个成熟、低风险的解决方案，已被广泛应用于需要大栈的 Rust 应用中。

**下一步**: 运行 `./test2.sh` 验证修复效果。
