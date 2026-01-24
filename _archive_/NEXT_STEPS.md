# 后续工作计划

## 当前状态

### ✅ 已完成
1. **配置升级**: Rust 1.89.0, Edition 2024
2. **依赖集成**: pvm-runtime 已集成
3. **HostApi 实现**: 所有方法已实现
4. **文档整理**: refs 目录已按主题分类整理

### ⚠️ 进行中
**借用检查器问题** - 正在使用 `Rc<RefCell<>>` 方案解决

### 📋 待完成
1. 解决编译错误（借用检查器）
2. 实现 Continuation 支持
3. 完善消息和定时器处理
4. 添加集成测试

## 借用检查器解决方案

### 已实施的方案
使用 `Rc<RefCell<>>` 实现共享可变性：
- `PvmExecutionContext` 的副作用字段改为 `Rc<RefCell<>>`
- 在 `execute_handler` 调用前克隆 Rc 引用
- 在 `execute_handler` 返回后使用克隆的引用提取副作用

### 需要完成的步骤
1. 修复所有使用 `pvm_ctx.actor.nonce` 的地方（提前提取）
2. 修复所有使用 `gas_meters.cycles/cells.used()` 的地方（提前提取或使用 unsafe）
3. 确保所有 `store` 的借用不冲突

### 预期效果
- 编译成功
- 无借用检查器错误
- 运行时行为正确

## 按核心技术白皮书的工作方案

### 阶段 1: 解决编译错误（当前）
**目标**: 代码可以编译通过  
**优先级**: 🔴 最高

**剩余工作**:
- 完成 `Rc<RefCell<>>` 方案的实施
- 修复所有借用冲突
- 验证编译成功

### 阶段 2: 完善单块原子性（1-2天）
**目标**: 确保符合白皮书的单块原子性要求  
**优先级**: 🟠 高

**工作内容**:
1. 验证存储提交在副作用处理之前
2. 验证失败时正确回滚
3. 添加单块原子性测试

### 阶段 3: Continuation 支持（3-5天）
**目标**: 实现基础 Continuation 功能  
**优先级**: 🟠 高

**工作内容**:
1. Continuation 状态存储（`__continuation:{cid}`）
2. Checkpoint 模式支持
3. FSM 模式支持（如果编译器可用）
4. Resume 处理逻辑

### 阶段 4: 消息和定时器（2-3天）
**目标**: 完善消息传递和定时器调度  
**优先级**: 🟡 中

**工作内容**:
1. 消息队列和去重
2. 定时器注册表
3. 超时处理
4. 与块提交流程集成

### 阶段 5: 确定性验证（1-2天）
**目标**: 验证确定性执行  
**优先级**: 🟡 中

**工作内容**:
1. 验证 SoftFloat 支持
2. 验证 ordered_set 支持
3. 添加确定性测试

### 阶段 6: Guard 机制（2-3天）
**目标**: 实现状态保护机制  
**优先级**: 🟡 中

**工作内容**:
1. Decorator-level guard
2. Object-level guard
3. 与 Continuation 集成

### 阶段 7: Runner 集成（3-5天）
**目标**: 准备 Runner 系统集成  
**优先级**: 🟢 低

**工作内容**:
1. Runner 消息格式
2. 验证模式支持
3. 超时和重试机制

## 参考文档

所有文档已整理到 `refs/` 目录：

### 核心文档
- `refs/whitepaper/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md` - 核心技术白皮书（最高优先级）
- `refs/chain/upgrade/WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md` - 详细工作方案
- `refs/chain/upgrade/BORROWCHECKER_SOLUTION_DESIGN.md` - 借用检查器解决方案设计

### PVM 文档
- `refs/pvm/api/host-api-reference.md` - Host API 参考
- `refs/pvm/api/runtime-api-reference.md` - Runtime API 参考
- `refs/pvm/features/PVM_Continuation_Design_CN.md` - Continuation 设计
- `refs/pvm/implementation/PVM_CHAIN_INTEGRATION_CN.md` - 链集成方案

### 任务计划
- `refs/task-plans/Cowboy_PVM_Task_Plan_CN.md` - SDK 开发任务计划

## 估算时间

- **阶段 1**: 1-2天
- **阶段 2**: 1-2天
- **阶段 3**: 3-5天
- **阶段 4**: 2-3天
- **阶段 5**: 1-2天
- **阶段 6**: 2-3天
- **阶段 7**: 3-5天

**总计**: 约 2-3 周

## 风险和缓解

### 高风险
- 借用检查器问题可能需要更深入的重构
- **缓解**: 已设计 `Rc<RefCell<>>` 方案，如不行可考虑修改 pvm-runtime

### 中风险
- Continuation 状态管理复杂
- **缓解**: 参考 PVM 的实现，使用标准 CBOR 格式

### 低风险
- 消息和定时器处理
- **缓解**: 按白皮书要求实现即可

## 成功标准

1. ✅ 代码编译成功（无错误）
2. ✅ 符合核心技术白皮书要求
3. ✅ 单块原子性验证通过
4. ✅ Continuation 基础功能可用
5. ✅ 集成测试通过
6. ✅ 确定性测试通过

---

**更新日期**: 2025-01-18  
**负责人**: AI Assistant  
**文档版本**: v1.0
