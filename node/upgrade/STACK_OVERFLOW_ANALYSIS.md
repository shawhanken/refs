# Stack Overflow 问题分析与解决方案

**问题日期**: 2026-01-19  
**发生位置**: validator 执行 actor instruction  
**错误类型**: `thread 'tokio-runtime-worker' has overflowed its stack`

---

## 一、问题现象

### 错误信息
```
2026-01-19T04:41:50.802250Z  INFO ThreadId(02) cowboy_chain::execution: chain/src/execution.rs:603: executing actor instruction

thread 'tokio-runtime-worker' (1506796) has overflowed its stack
fatal runtime error: stack overflow, aborting
Aborted (core dumped)
```

### 发生场景
1. Validator 启动正常
2. 加载配置和 peers 成功
3. 开始处理区块 621
4. 执行交易时
5. **执行 actor instruction 时发生栈溢出**

---

## 二、问题分析

### 根本原因
**PVM（Python Virtual Machine）执行 Python 代码时需要大量栈空间**

#### 技术细节
1. **RustPython 栈使用**
   - PVM 基于 RustPython 实现
   - Python 解释器执行时需要深度调用栈
   - Python 对象序列化/反序列化（snapshot）需要递归处理

2. **Tokio 默认栈大小**
   - 默认栈大小：2 MiB
   - PVM 执行复杂 actor 代码时可能超过此限制

3. **触发时机**
   - 执行 `ActorInstruction::ExecuteActor` 时
   - 调用 `pvm_executor.execute_handler()` 时
   - RustPython VM 执行 Python 代码时

### 类似问题历史
- ✅ 在之前的 `pvm_integration_test.rs` 中也遇到相同问题
- ✅ 当时的解决方案是删除该测试，仅通过单元测试验证功能
- ⚠️ 但在生产环境（validator）中必须解决此问题

---

## 三、解决方案

### 🎯 方案1：增加 Tokio Worker 线程栈大小（推荐）

#### 标准 Tokio 方式
```rust
use tokio::runtime::Builder;

let rt = Builder::new_multi_thread()
    .worker_threads(8)
    .thread_stack_size(16 * 1024 * 1024)   // 16 MiB
    .enable_all()
    .build()
    .unwrap();
```

#### 问题：validator 使用 commonware_runtime
当前代码使用：
```rust
// chain/src/bin/validator.rs:88-93
let cfg = tokio::Config::default()
    .with_tcp_nodelay(Some(true))
    .with_worker_threads(config.worker_threads)
    .with_storage_directory(PathBuf::from(config.directory))
    .with_catch_panics(false);
let executor = tokio::Runner::new(cfg);
```

**需要检查**：`commonware_runtime::tokio::Config` 是否支持栈大小配置

---

### 🎯 方案2：使用环境变量 RUST_MIN_STACK（最简单）

#### 实现方式
```bash
# 设置最小栈大小为 16 MiB
export RUST_MIN_STACK=16777216

# 运行 validator
cargo run --bin validator -- --peers=... --config=...
```

#### 优点
- ✅ 无需修改代码
- ✅ 立即生效
- ✅ 适用于所有线程

#### 缺点
- ⚠️ 影响所有线程，内存使用增加
- ⚠️ 需要在启动脚本中设置

#### 修改测试脚本
```bash
# /home/ubuntu/workspace/node/test2.sh
export RUST_MIN_STACK=16777216
RUST_BACKTRACE=1 cargo run --bin validator -- \
  --peers=/home/ubuntu/workspace/node/test2/peers.yaml \
  --config=/home/ubuntu/workspace/node/test2/8fd31606c3d46cbf24695dd4617b5d4ac1ee0f6a61c410d638b3151556b5dc21.yaml
```

---

### 🎯 方案3：在 PVM 执行时使用独立任务栈（精确控制）

#### 实现方式
在 `execute_actor_handler_impl` 中，使用 `tokio::task::Builder` spawn 一个带大栈的任务：

```rust
// chain/src/execution.rs
async fn execute_actor_handler_impl<S: StateStore>(
    &mut self,
    store: &mut S,
    // ... 其他参数
) -> Result<(), ExecutionError>
{
    // ... 准备工作

    // 在大栈任务中执行 PVM
    let result = tokio::task::Builder::new()
        .name("pvm-executor")
        .stack_size(16 * 1024 * 1024)  // 16 MiB
        .spawn(async move {
            // 执行 PVM handler
            pvm_executor.execute_handler(
                &pvm_ctx,
                &actor_obj.code_hash,
                handler,
                payload,
            ).await
        })
        .await
        .map_err(|e| ExecutionError::PvmError(format!("Task join error: {}", e)))?;

    // ... 处理结果
}
```

#### 优点
- ✅ 精确控制，只影响 PVM 执行任务
- ✅ 其他任务保持默认栈大小
- ✅ 更好的资源利用

#### 缺点
- ⚠️ 需要修改代码
- ⚠️ 增加任务调度开销
- ⚠️ 需要处理跨任务的数据传递（可能需要 `Arc<Mutex<>>`）

---

### 🎯 方案4：优化 PVM 代码减少栈使用（长期方案）

#### 可能的优化
1. **减少递归深度**
   - 检查 RustPython snapshot 代码
   - 考虑使用迭代替代递归

2. **Box 大型数据结构**
   - 将大型对象放在堆上而不是栈上

3. **延迟加载和流式处理**
   - 避免一次性加载大量数据到栈上

#### 评估
- ⚠️ 需要深入理解 RustPython 内部
- ⚠️ 可能需要修改 PVM 子模块
- ⚠️ 工作量大，风险高

---

## 四、推荐方案对比

| 方案 | 难度 | 风险 | 效果 | 推荐度 |
|-----|------|------|------|--------|
| **方案2：RUST_MIN_STACK** | ⭐ 简单 | ⭐ 低 | ⭐⭐⭐ 立即有效 | ⭐⭐⭐⭐⭐ |
| **方案1：Tokio 配置** | ⭐⭐ 中等 | ⭐⭐ 中 | ⭐⭐⭐ 专业 | ⭐⭐⭐⭐ |
| **方案3：独立任务栈** | ⭐⭐⭐ 复杂 | ⭐⭐⭐ 中高 | ⭐⭐⭐⭐ 精确 | ⭐⭐⭐ |
| **方案4：优化 PVM** | ⭐⭐⭐⭐⭐ 很难 | ⭐⭐⭐⭐ 高 | ⭐⭐⭐⭐⭐ 根本 | ⭐⭐ |

---

## 五、立即行动计划

### 第一步：快速验证（方案2）
```bash
# 修改 test2.sh
export RUST_MIN_STACK=16777216
RUST_BACKTRACE=1 cargo run --bin validator -- \
  --peers=/home/ubuntu/workspace/node/test2/peers.yaml \
  --config=/home/ubuntu/workspace/node/test2/8fd31606c3d46cbf24695dd4617b5d4ac1ee0f6a61c410d638b3151556b5dc21.yaml
```

**预期**：栈溢出问题解决，validator 正常运行

### 第二步：如果方案2不够，尝试更大栈
```bash
export RUST_MIN_STACK=33554432  # 32 MiB
```

### 第三步：如果需要精确控制，实现方案3
修改 `chain/src/execution.rs` 中的 `execute_actor_handler_impl`

### 第四步：长期优化（方案1）
研究 commonware_runtime 是否支持栈配置，或提交 PR 添加此功能

---

## 六、栈大小参考

### 常见栈大小
- Rust 默认主线程：8 MiB（Linux）
- Tokio 默认 worker：2 MiB
- **推荐 PVM 栈大小：16 MiB**
- 如果仍然不够：32 MiB

### 内存影响评估
假设配置：
- Worker 线程数：8
- 栈大小：16 MiB
- **总栈内存**：8 × 16 = 128 MiB

**评估**：对于区块链节点，128 MiB 栈内存是可接受的

---

## 七、验证方法

### 成功标志
```
✅ validator 启动
✅ 加载配置和 peers
✅ 开始处理区块
✅ 执行 actor instruction
✅ 完成交易执行
✅ 无栈溢出错误
```

### 监控指标
```bash
# 检查进程栈使用
cat /proc/<pid>/status | grep Stack

# 监控内存使用
top -p <pid>
```

---

## 八、相关文件

### 需要修改的文件
1. **立即修改**：`/home/ubuntu/workspace/node/test2.sh`
2. **可选修改**：`/home/ubuntu/workspace/node/chain/src/bin/validator.rs`
3. **高级修改**：`/home/ubuntu/workspace/node/chain/src/execution.rs`

### 相关代码位置
- PVM 执行入口：`chain/src/execution.rs:603`（executing actor instruction）
- PVM 执行函数：`chain/src/execution.rs:660`（execute_actor_handler_impl）
- Validator runtime：`chain/src/bin/validator.rs:88-93`

---

## 九、技术背景

### 为什么 PVM 需要大栈？

1. **Python 解释器特性**
   - Python 是动态类型语言
   - 对象创建和方法调用涉及大量栈帧

2. **RustPython 实现**
   - Rust 中实现 Python VM
   - 每个 Python 调用对应多个 Rust 调用
   - 栈使用倍增

3. **Snapshot/Checkpoint**
   - 需要序列化整个 VM 状态
   - 递归遍历对象图
   - 深度优先搜索需要栈空间

4. **异步执行**
   - Tokio 任务栈独立于主线程
   - 不能依赖操作系统的大栈

### 其他区块链的做法

- **以太坊 EVM**：基于栈的简单 VM，栈使用可预测
- **Solana SVM**：eBPF VM，有严格的执行限制
- **Cowboy PVM**：完整 Python VM，需要更多资源

---

## 十、结论

### 问题总结
- ✅ **根本原因明确**：PVM 执行 Python 代码需要大栈
- ✅ **不是代码 bug**：是资源配置问题
- ✅ **有成熟解决方案**：增加栈大小

### 推荐行动
1. **立即**：修改 `test2.sh`，添加 `RUST_MIN_STACK=16777216`
2. **短期**：验证 16 MiB 是否足够，必要时增加到 32 MiB
3. **中期**：研究 commonware_runtime 配置选项
4. **长期**：监控生产环境，考虑优化 PVM 栈使用

### 风险评估
- ✅ **低风险**：增加栈大小是标准做法
- ✅ **可逆**：随时可以调整
- ✅ **可测试**：本地验证后再部署

---

**文档创建时间**: 2026-01-19  
**下一步行动**: 修改 test2.sh 并重新测试
