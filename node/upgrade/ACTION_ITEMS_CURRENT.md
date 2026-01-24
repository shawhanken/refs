# 当前行动项清单

**更新日期**: 2026-01-19  
**状态**: Phase 2 - 验证与调试  
**紧急程度**: ⏰ 高

---

## 🎯 立即行动 (今天)

### Action 1: 运行 Validator ⏰ 最高优先级

**目标**: 验证 validator 能否正常运行并执行 actor

**步骤**:
```bash
# 1. 确保 test2.sh 可执行
cd /home/ubuntu/workspace/node
chmod +x test2.sh

# 2. 运行 validator
./test2.sh

# 3. 观察日志输出
# 预期看到：
# - validator 启动
# - 加载配置和 peers
# - 处理区块
# - 执行 actor instruction
# - deploy actor 或 execute actor handler

# 4. 如果仍然 stack overflow
# 尝试更大的栈：
# 编辑 test2.sh，修改为：
export RUST_MIN_STACK=33554432  # 32 MiB
```

**预期结果**:
- ✅ Validator 启动成功
- ✅ 无 stack overflow 错误
- ✅ 能够执行到 "executing actor instruction"
- ✅ 看到详细的 gas 计费日志

**如果失败**:
- 收集完整日志
- 识别错误类型
- 更新 RUST_MIN_STACK 或修复代码

**时间**: 1-2 小时

---

### Action 2: 分析执行日志 ⏰ 高优先级

**目标**: 理解 validator 的执行流程和 gas 计费

**关注的日志**:

#### Deploy Actor 流程
```
✓ 应该看到：
  info!("deploying actor")
  info!("deploy cycles: {}", deploy_cycles)
  info!("deploy cells: {}", deploy_cells)
  info!("deploy cycles result: {:?}", result)
  info!("actor address: {:?}", &actor_address)
  info!("actor created: {:?}", actor)
  info!("actor set")

✗ 不应该看到：
  warn!("out of cycles: {:?}", e)
  warn!("out of cells: {:?}", e)
  warn!("actor already exists: {:?}", &actor_address)
```

#### Execute Actor 流程
```
✓ 应该看到：
  info!("executing actor handler")
  info!("Executing handler: {} with payload: {}", handler, hex)
  info!("Code: {}, Input: {}", _code, hex)
  info!("Continuation key: {:?}", continuation_key)
  info!("Getting state: {}", key.len())
  info!("Setting state: {} {}", key.len(), value.len())
  info!("Charging gas: {}", amount)
  info!("Gas left: {}", remaining)
```

**分析任务**:
1. **Deploy Cycles/Cells**
   - [ ] 记录 deploy cycles 数值
   - [ ] 记录 deploy cells 数值
   - [ ] 验证是否合理（大致等于 code.len() * 倍数）

2. **Execute Gas**
   - [ ] 记录每次 "Charging gas" 的数值
   - [ ] 统计 "Getting state" 和 "Setting state" 次数
   - [ ] 验证 "Gas left" 递减是否正常

3. **错误识别**
   - [ ] 查找任何 warn! 或 error! 日志
   - [ ] 识别异常退出
   - [ ] 记录崩溃信息

**时间**: 1-2 小时

---

## 📋 本周行动 (1/19 - 1/25)

### Action 3: Bug 修复与调整 ⏰

**基于日志分析的发现**:

#### 如果 Out of Cycles
```rust
// 调整 execution.rs 中的 cycles 计算
// 或增加 transaction 的 cycles_limit

// 当前：
let deploy_cycles = code.len() * gas_costs.actor_deploy_cycles_per_byte;

// 可能需要：
let deploy_cycles = code.len() * (gas_costs.actor_deploy_cycles_per_byte / 10);
// 或者在测试中增加 cycles_limit
```

#### 如果 Out of Cells
```rust
// 类似调整 cells 计算
```

#### 如果 PVM 执行失败
```rust
// 检查：
// 1. Python 代码是否有语法错误
// 2. PVM 沙箱限制是否过严
// 3. Determinism 配置是否正确
```

**时间**: 2-3 天

---

### Action 4: 创建测试 Actor ⏰

**目标**: 创建简单的测试 actor 验证功能

**测试 Actor 1: Hello World**
```python
# hello_actor.py
def handler_hello(ctx, input):
    """最简单的 actor"""
    return b"Hello, World!"
```

**测试 Actor 2: State Test**
```python
# state_actor.py
def handler_set(ctx, input):
    """测试 state set"""
    ctx.state[b"key"] = input
    return b"ok"

def handler_get(ctx, input):
    """测试 state get"""
    return ctx.state.get(b"key", b"not found")
```

**测试 Actor 3: Event Test**
```python
# event_actor.py
def handler_emit(ctx, input):
    """测试 event emit"""
    ctx.emit("test_event", input)
    return b"emitted"
```

**测试 Actor 4: Gas Test**
```python
# gas_actor.py
def handler_consume_gas(ctx, input):
    """测试 gas 消耗"""
    for i in range(1000):
        _ = i * i  # 消耗 cycles
    ctx.state[b"counter"] = str(i).encode()  # 消耗 cells
    return b"done"
```

**部署与测试**:
```bash
# 1. 编译 actor bytecode (如果需要)
# 2. 创建 deploy transaction
# 3. 发送 deploy transaction
# 4. 创建 execute transaction
# 5. 发送 execute transaction
# 6. 验证结果
```

**时间**: 2 天

---

### Action 5: 性能 Baseline 测试 ⏰

**目标**: 建立性能基准数据

**测试场景**:

#### Scenario 1: Simple Actor TPS
```
Actor: hello_actor (最简单)
测试: 连续发送 N 个交易
测量: TPS (transactions per second)
目标: > 100 TPS
```

#### Scenario 2: State Actor Latency
```
Actor: state_actor (带状态)
测试: 单笔交易延迟
测量: 从发送到确认的时间
目标: < 500ms
```

#### Scenario 3: Complex Actor Resource
```
Actor: gas_actor (消耗资源)
测试: 内存和 CPU 使用
测量: validator 进程资源
目标: < 500MB 内存，< 80% CPU
```

**工具**:
```bash
# TPS 测试
# 使用 wrk 或自定义脚本

# 延迟测试
# 记录每笔交易的时间戳

# 资源测试
htop
# 或
vmstat 1

# 内存监控
cat /proc/$(pidof validator)/status | grep VmRSS
```

**时间**: 2-3 天

---

## 📅 下周行动 (1/26 - 1/31)

### Action 6: 代码清理 ⏳

**目标**: 清理调试代码，准备 code review

**清理任务**:

#### 1. 日志清理
```rust
// 决定保留哪些日志
// 建议：
// - 关键流程保留 info!
// - 详细数据改为 debug!
// - 移除调试用的 info!

// 保留：
info!("executing actor instruction");
info!("deploying actor");

// 改为 debug!：
debug!("deploy cycles: {}", deploy_cycles);
debug!("actor address: {:?}", &actor_address);
debug!("Getting state: {}", key.len());

// 移除：
// info!("Current thread: {:?}", ...)  // 纯调试
```

#### 2. 注释清理
```rust
// 移除临时注释
//parse actor code as utf-8
let _code = std::str::from_utf8(actor_code.as_slice()).unwrap();

// 改为：
// 如果真的需要这个代码，添加正式注释
// 否则删除
```

#### 3. Unused 清理
```bash
cargo fix --lib -p cowboy-chain
# 修复 unused imports 和 variables
```

**时间**: 1-2 天

---

### Action 7: 文档更新 ⏳

**目标**: 更新文档反映最新状态

**更新列表**:

#### 1. README.md
```markdown
# 添加：
- PVM 集成说明
- 最小栈大小要求 (RUST_MIN_STACK=16777216)
- 快速开始指南
```

#### 2. IMPLEMENTATION_SUMMARY.md
```markdown
# 更新：
- Phase 2 验证结果
- 性能 baseline 数据
- 已知问题列表
```

#### 3. 新建 DEPLOYMENT_GUIDE.md
```markdown
# 包含：
- 系统要求
- 安装步骤
- 配置说明
- 运行验证
- 故障排查
```

**时间**: 1 天

---

### Action 8: Code Review 准备 ⏳

**目标**: 准备代码审查材料

**审查材料**:

#### 1. 变更总结
```
文件列表：
- chain/src/execution.rs: ✅ 关键变更，需仔细审查
- chain/src/pvm_host.rs: ✅ 关键变更，需仔细审查
- chain/src/pvm_executor.rs: ✅ 关键变更
- chain/src/mempool.rs: ✅ 测试修复
- chain/src/lib.rs: ✅ Runtime guard
- pvm/crates/pvm-runtime/src/lib.rs: ✅ API 导出
- test2.sh: ✅ 栈配置
```

#### 2. 审查清单
```
核心问题：
- [ ] Unsafe 代码的安全性
- [ ] Arc<Mutex<>> 的正确使用
- [ ] Gas 计费的准确性
- [ ] Error handling 完整性
- [ ] 测试覆盖度
- [ ] 文档完整性

白皮书对齐：
- [ ] 单块原子性
- [ ] 消息去重
- [ ] Continuation 支持
- [ ] 确定性执行
- [ ] Dual Gas 计费
```

#### 3. 风险评估
```
高风险区域：
1. execution.rs 中的 unsafe 指针
2. pvm_host.rs 中的 gas 计费逻辑
3. Arc<Mutex<>> 的锁竞争

缓解措施：
1. 详细注释和文档
2. 单元测试覆盖
3. 运行时验证
```

**时间**: 1 天

---

## ⚡ 快速参考

### 常用命令

```bash
# 编译检查
cargo check

# 运行测试
cargo test --lib --package cowboy-chain pvm
cargo test --lib --package cowboy-chain mempool

# 运行 validator
./test2.sh

# 查看进程资源
ps aux | grep validator
top -p $(pidof validator)

# 查看日志
# (在 test2.sh 输出中)

# 清理调试符号
cargo clean
cargo build --release
```

### 调试技巧

```bash
# 如果 stack overflow
export RUST_MIN_STACK=33554432  # 增加到 32 MiB

# 如果编译慢
cargo build -j 1  # 单线程编译，节省内存

# 如果测试超时
cargo test -- --test-threads=1  # 单线程测试

# 查看详细日志
RUST_LOG=debug ./test2.sh

# 查看栈使用
cat /proc/$(pidof validator)/status | grep Stack
```

### 重要文件路径

```
代码：
- /home/ubuntu/workspace/node/chain/src/execution.rs
- /home/ubuntu/workspace/node/chain/src/pvm_host.rs
- /home/ubuntu/workspace/node/chain/src/pvm_executor.rs

配置：
- /home/ubuntu/workspace/node/test2.sh
- /home/ubuntu/workspace/node/test2/genesis.json
- /home/ubuntu/workspace/node/test2/peers.yaml

文档：
- /home/ubuntu/workspace/node/refs/chain/upgrade/*.md
```

---

## 📊 进度跟踪

### Phase 2 完成度

```
Action 1: Validator 运行    [ ] 0%   ⏰ 今天
Action 2: 日志分析          [ ] 0%   ⏰ 今天
Action 3: Bug 修复          [ ] 0%   ⏰ 本周
Action 4: 测试 Actor        [ ] 0%   ⏰ 本周
Action 5: 性能 Baseline     [ ] 0%   ⏰ 本周
Action 6: 代码清理          [ ] 0%   ⏳ 下周
Action 7: 文档更新          [ ] 0%   ⏳ 下周
Action 8: Code Review 准备  [ ] 0%   ⏳ 下周

总体 Phase 2: ░░░░░░░░░░ 0%
```

### 时间分配（本周）

```
周一 (1/19): Action 1-2  ⏰ Validator 运行与日志分析
周二 (1/20): Action 2-3  ⏰ 日志分析与 Bug 修复  
周三 (1/21): Action 3    ⏰ Bug 修复继续
周四 (1/22): Action 4    ⏰ 测试 Actor 创建
周五 (1/23): Action 4-5  ⏰ Actor 测试与性能测试
周末 (1/24-25): Action 5 休息或继续性能测试
```

---

## ✅ 成功标准

### Phase 2 完成标志

- [x] ✅ Validator 能够启动并运行
- [ ] ✅ 能够部署测试 actor
- [ ] ✅ 能够执行 actor handler
- [ ] ✅ Gas 计费正常工作
- [ ] ✅ 状态持久化正常
- [ ] ✅ 无 runtime 错误或崩溃
- [ ] ✅ 性能达到 baseline
- [ ] ✅ 代码已清理
- [ ] ✅ 文档已更新
- [ ] ✅ 准备好 code review

### 可以进入 Phase 3 的条件

- ✅ 所有 Phase 2 action 完成
- ✅ Validator 稳定运行 24 小时
- ✅ 至少 3 个测试 actor 通过
- ✅ 性能 baseline 数据收集完成
- ✅ 代码审查通过

---

## 🚨 风险提示

### 如果 Validator 无法运行

**可能原因**:
1. Stack overflow 仍然发生 → 增加 RUST_MIN_STACK
2. PVM 执行错误 → 检查 Python 代码
3. Gas 不足 → 调整 gas 参数
4. Storage 错误 → 检查数据库

**应对**:
- 收集完整日志
- 在 ACTION_ITEMS_CURRENT.md 中记录问题
- 更新 RUST_MIN_STACK 或修复代码
- 向团队求助

### 如果性能不达标

**应对**:
- 记录性能数据
- Profile 找出瓶颈
- 考虑优化（但不阻塞 Phase 2 完成）
- 将优化任务移到 Phase 3 或并行任务

### 如果时间不够

**优先级**:
1. ⏰ **必须**: Action 1-2 (Validator 运行和日志分析)
2. ⏰ **重要**: Action 3 (Bug 修复)
3. ⏳ **可选**: Action 4-5 (测试 Actor 和性能)
4. ⏳ **推迟**: Action 6-8 (清理和文档)

---

**清单版本**: 1.0  
**创建时间**: 2026-01-19  
**负责人**: 开发团队  
**审查频率**: 每天更新进度
