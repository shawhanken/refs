# PVM 升级后续工作方案（基于核心技术白皮书）

## 文档依据

**核心技术白皮书**: `Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md`  
**评估日期**: 2025-01-XX  
**优先级**: 所有决策以核心技术白皮书为准

---

## 一、核心技术白皮书核心要求分析

### 1.1 Actor 模型执行语义

**核心原则**：
- ✅ **单块原子性**：每个消息处理器的执行是原子的（全部提交或全部回滚）
- ✅ **显式消息传递**：所有异步操作通过显式消息传递，不使用隐式协程
- ✅ **无跨块原子性**：不支持跨块的原子事务
- ✅ **消息去重**：消息传递保证 exactly-once 语义

**对当前实现的要求**：
1. `PvmExecutor` 必须确保单块内执行的原子性
2. 消息发送（`send_message`）必须记录到 `outgoing_messages`，在块提交时统一处理
3. 定时器调度（`schedule_timer`）必须在块提交时统一处理
4. 状态变更必须在块提交时统一提交或回滚

### 1.2 Continuation 机制要求

**白皮书要求**：
- ✅ **消息传递模型**：Continuation 通过显式消息传递实现，不是隐式协程
- ✅ **FSM 编译**：`@runner.continuation` 和 `@actor.continuation` 编译为状态机
- ✅ **Checkpoint 支持**：支持运行时 checkpoint/resume（用于长时间任务）
- ✅ **Context 捕获**：使用 `capture()` 显式捕获跨 await 的变量
- ✅ **Guard 机制**：支持 `guard_unchanged` 防止状态冲突

**对当前实现的要求**：
1. 必须支持 `ContinuationMode::Fsm`（编译期 FSM）
2. 必须支持 `ContinuationMode::Checkpoint`（运行时快照）
3. Continuation 状态必须存储在 actor storage 中（`__continuation:{cid}`）
4. 必须支持 `capture()` 机制和 CBOR 序列化

### 1.3 确定性执行要求

**白皮书要求**：
- ✅ **固定 Hash Seed**：`PYTHONHASHSEED = 0`
- ✅ **SoftFloat**：所有浮点运算使用软件浮点库
- ✅ **ordered_set**：替换内置 `set` 为 `ordered_set`
- ✅ **CBOR 序列化**：所有跨信任边界的数据使用 Canonical CBOR
- ✅ **禁止非确定性操作**：禁止 `time`, `random`, `pickle` 等

**对当前实现的要求**：
1. `ExecutionOptions` 必须设置 `deterministic: true`
2. 必须启用确定性运行时限制
3. 必须验证所有序列化使用 CBOR

### 1.4 Dual Gas 模型要求

**白皮书要求**：
- ✅ **Cycles**：计算资源计量（Python 操作、host 调用）
- ✅ **Cells**：数据/存储资源计量（calldata、返回值、存储）
- ✅ **独立计费**：Cycles 和 Cells 独立计费和定价

**对当前实现的要求**：
1. `CowboyHost` 必须正确映射 PVM 的单一 Gas 到双 Gas 系统
2. `charge_gas()` 应该消耗 Cycles
3. `state_set()` 应该消耗 Cells（基于 value 大小）
4. `emit_event()` 应该消耗 Cells（基于数据大小）

### 1.5 Runner 系统要求

**白皮书要求**：
- ✅ **异步任务框架**：Runner 执行是异步的，结果通过消息返回
- ✅ **验证模式**：支持多种验证模式（none, economic_bond, majority_vote, etc.）
- ✅ **超时处理**：必须支持超时和重试机制

**对当前实现的要求**：
1. Runner 请求通过 `send_message` 发送到 Runner 系统 Actor
2. Runner 结果通过消息返回，触发 continuation resume
3. 必须支持超时定时器机制

---

## 二、当前升级状态评估

### 2.1 ✅ 已完成的工作

1. **配置升级**
   - ✅ Rust version: 1.70.0 → 1.89.0
   - ✅ Edition: 2021 → 2024
   - ✅ 排除 pvm 子模块（避免 workspace 冲突）

2. **依赖集成**
   - ✅ 添加 `pvm-runtime` 依赖
   - ✅ `PvmExecutor` 已更新为使用 `pvm-runtime`

3. **HostApi 实现**
   - ✅ 所有必需方法已实现
   - ✅ `HostContext` 字段完整（包含 `actor_addr`, `msg_id`, `nonce`）

### 2.2 ⚠️ 需要解决的问题

1. **借用检查器错误**（阻塞）
   - **问题**：`execute_handler` 返回后无法访问 `pvm_ctx` 字段
   - **原因**：`execute_tx_with_options` 通过 `HostGuard` 持有 host 借用
   - **影响**：无法提取 `outgoing_messages`、`scheduled_timers` 等

2. **Continuation 支持不完整**
   - **问题**：当前 `continuation: None`，未启用 continuation
   - **需要**：根据白皮书要求支持 FSM 和 Checkpoint 模式

3. **消息和定时器处理**
   - **问题**：消息和定时器记录在 context 中，但未在块提交时处理
   - **需要**：确保符合单块原子性要求

### 2.3 📋 需要补充的功能

1. **Continuation 状态管理**
   - 支持 continuation 状态的存储和恢复
   - 支持 `capture()` 机制
   - 支持 Guard 机制

2. **确定性执行配置**
   - 确保所有执行使用确定性模式
   - 验证 SoftFloat 和 ordered_set 支持

3. **Runner 集成准备**
   - 准备 Runner 消息格式
   - 准备 continuation resume 处理

---

## 三、后续工作方案

### 阶段 1: 解决借用检查器问题（优先级：🔴 最高）

**目标**：修复编译错误，确保代码可以编译通过

**方案 A：重构代码结构**（推荐）
```rust
// 在 execute_handler 返回前提取所有需要的数据
pub async fn execute_handler<'a, S: StateStore>(
    &self,
    ctx: &'a mut PvmExecutionContext<'a, S>,
    payload: &[u8],
    handler: &str,
) -> Result<(Bytes, ExecutionSideEffects), HostError> {
    let actor_code = ctx.actor.code.clone();
    let input = payload.to_vec();
    
    // 执行前提取初始状态（如果需要）
    let initial_nonce = ctx.actor.nonce;
    
    // 执行 Python 代码
    let output = {
        let mut host = CowboyHost::new(ctx);
        execute_tx_with_options(&mut host, &actor_code, &input, &options)?
    };
    
    // 执行后提取副作用（此时 host 已释放）
    let side_effects = ExecutionSideEffects {
        outgoing_messages: std::mem::take(&mut ctx.outgoing_messages),
        scheduled_timers: std::mem::take(&mut ctx.scheduled_timers),
        cancelled_timers: std::mem::take(&mut ctx.cancelled_timers),
        events: std::mem::take(&mut ctx.events),
    };
    
    Ok((output, side_effects))
}
```

**方案 B：使用内部可变性**
- 将 `outgoing_messages` 等字段改为 `RefCell` 或 `Mutex`
- 允许在 host 借用期间修改

**推荐**：方案 A，更符合 Rust 所有权模型

### 阶段 2: 完善 Continuation 支持（优先级：🟠 高）

**目标**：根据白皮书要求实现完整的 Continuation 机制

#### 2.1 基础 Continuation 支持

1. **Continuation 状态存储**
   ```rust
   // 在 PvmExecutionContext 中添加
   pub continuation_states: HashMap<Vec<u8>, ContinuationState>,
   ```

2. **Continuation 模式配置**
   ```rust
   // 根据 actor 配置或消息类型选择模式
   let continuation = if should_use_checkpoint {
       Some(ContinuationOptions {
           mode: ContinuationMode::Checkpoint,
           checkpoint_key: Some(b"checkpoint".to_vec()),
           ..Default::default()
       })
   } else {
       Some(ContinuationOptions {
           mode: ContinuationMode::Fsm,
           ..Default::default()
       })
   };
   ```

3. **Continuation Resume 处理**
   ```rust
   // 在消息处理中检测 continuation resume
   if let Some(cid) = extract_continuation_id(&msg) {
       // 从 storage 加载 continuation 状态
       let state = load_continuation_state(&cid)?;
       // 使用 resume_bytes 恢复执行
       options.continuation.resume_bytes = Some(state.resume_bytes);
   }
   ```

#### 2.2 Guard 机制实现

1. **Decorator-level Guard**
   ```rust
   // 在 continuation 开始时保存 guard hash
   let guard_hash = compute_guard_hash(&guard_keys)?;
   // 在 resume 时验证
   if guard_hash != current_guard_hash {
       return Err(HostError::Forbidden); // StateConflictError
   }
   ```

2. **Object-level Guard**
   ```rust
   // 在 storage.guard() 中实现
   pub fn guard(&self, key: &[u8]) -> GuardedValue {
       let value = self.get(key)?;
       let hash = compute_hash(&value);
       GuardedValue { value, hash }
   }
   ```

### 阶段 3: 确保单块原子性（优先级：🟠 高）

**目标**：确保所有状态变更和副作用在块提交时统一处理

#### 3.1 执行流程重构

```rust
// 在 execution.rs 中
match execution_result {
    Ok((output, side_effects)) => {
        // 1. 提交存储变更（原子性）
        pvm_ctx.commit().await?;
        
        // 2. 处理副作用（在存储提交后）
        // 2.1 发送消息
        for (target, payload) in side_effects.outgoing_messages {
            enqueue_message(target, payload)?;
        }
        
        // 2.2 调度定时器
        for (height, payload, timer_id) in side_effects.scheduled_timers {
            schedule_timer(height, payload, timer_id)?;
        }
        
        // 2.3 取消定时器
        for timer_id in side_effects.cancelled_timers {
            cancel_timer(timer_id)?;
        }
        
        // 2.4 发射事件
        for (topic, data) in side_effects.events {
            emit_event(topic, data)?;
        }
        
        Ok(output)
    }
    Err(e) => {
        // 回滚所有变更
        pvm_ctx.rollback();
        Err(e)
    }
}
```

#### 3.2 消息去重机制

```rust
// 在消息队列中实现去重
pub struct MessageQueue {
    processed: HashSet<MessageId>,
    pending: VecDeque<Message>,
}

impl MessageQueue {
    pub fn enqueue(&mut self, msg: Message) -> Result<(), Error> {
        if self.processed.contains(&msg.id) {
            return Ok(()); // 已处理，忽略
        }
        self.pending.push_back(msg);
        Ok(())
    }
}
```

### 阶段 4: 确定性执行配置（优先级：🟡 中）

**目标**：确保所有执行符合白皮书确定性要求

#### 4.1 ExecutionOptions 配置

```rust
let options = ExecutionOptions {
    deterministic: true,  // 必须为 true
    determinism: Some(DeterminismOptions {
        enabled: true,
        hash_seed: Some(0),  // 固定 hash seed
        stdlib_whitelist: vec![...],
        stdlib_blacklist: vec!["time", "random", "pickle"],
        ..Default::default()
    }),
    ..Default::default()
};
```

#### 4.2 SoftFloat 和 ordered_set 验证

- 验证 PVM 是否已集成 SoftFloat
- 验证 `set` 是否自动替换为 `ordered_set`
- 添加测试用例验证确定性

### 阶段 5: Runner 集成准备（优先级：🟡 中）

**目标**：准备 Runner 系统的消息格式和处理逻辑

#### 5.1 Runner 消息格式

```rust
// 根据白皮书定义 Runner Job 格式
pub struct RunnerJob {
    pub kind: "runner_job",
    pub job_type: "llm" | "http" | "mcp" | "custom",
    pub payload: CborValue,
    pub cid: [u8; 32],
    pub reply_to: [u8; 20],
    pub reply_handler: String,
    pub timeout_block: u64,
    pub verification: CborValue,
    pub tee_required: bool,
}
```

#### 5.2 Runner Result 处理

```rust
// 在消息处理中检测 Runner 结果
if msg.kind == "runner_result" {
    let cid = msg.cid;
    // 加载 continuation 状态
    let state = load_continuation_state(&cid)?;
    // 恢复执行
    resume_continuation(state, msg.result)?;
}
```

---

## 四、实施优先级和时间表

### 立即执行（本周）

1. **解决借用检查器问题**
   - 重构 `execute_handler` 返回结构
   - 提取 `ExecutionSideEffects`
   - 验证编译通过

2. **完善单块原子性**
   - 重构执行流程
   - 确保存储提交和副作用处理的顺序
   - 添加回滚机制

### 短期计划（1-2周）

3. **基础 Continuation 支持**
   - 实现 continuation 状态存储
   - 支持 Checkpoint 模式
   - 支持 FSM 模式（如果编译器可用）

4. **消息和定时器处理**
   - 实现消息队列和去重
   - 实现定时器调度
   - 集成到块提交流程

### 中期计划（2-4周）

5. **Guard 机制**
   - 实现 decorator-level guard
   - 实现 object-level guard
   - 添加测试用例

6. **确定性执行验证**
   - 验证 SoftFloat 支持
   - 验证 ordered_set 支持
   - 添加确定性测试

### 长期计划（1-2月）

7. **Runner 集成**
   - 实现 Runner 消息格式
   - 实现 continuation resume 处理
   - 实现超时和重试机制

8. **完整测试和文档**
   - 端到端测试
   - 性能测试
   - 文档更新

---

## 五、关键技术决策

### 5.1 Continuation 模式选择

**根据白皮书**：
- **FSM 模式**：用于编译期转换的 async 函数（`@runner.continuation`）
- **Checkpoint 模式**：用于运行时快照（长时间任务）

**实现策略**：
- 默认使用 Checkpoint 模式（更灵活）
- 如果检测到 `@runner.continuation` 装饰器，使用 FSM 模式
- 允许通过配置强制指定模式

### 5.2 状态存储策略

**根据白皮书**：
- Continuation 状态存储在 actor storage：`__continuation:{cid}`
- Runner 结果存储在 actor storage：`__runner_result:{cid}`
- Checkpoint 可以存储在 actor storage 或通过 HostApi 传输

**实现策略**：
- 使用 `pvm_host.state_set/get` 存储 continuation 状态
- 状态大小限制：64 KiB per state
- 活跃状态数量限制：100 per actor

### 5.3 Gas 计量映射

**根据白皮书**：
- PVM 使用单一 Gas 模型
- Cowboy 使用双 Gas 模型（Cycles + Cells）

**实现策略**：
- `charge_gas()` → 消耗 Cycles
- `state_set()` → 消耗 Cells（基于 value 大小）
- `emit_event()` → 消耗 Cells（基于数据大小）
- `send_message()` → 消耗 Cycles（操作成本）+ Cells（payload 大小）

---

## 六、测试要求

### 6.1 单元测试

- [ ] `PvmExecutor.execute_handler` 测试
- [ ] `CowboyHost` 所有方法测试
- [ ] Continuation 状态存储/恢复测试
- [ ] Guard 机制测试
- [ ] 消息去重测试

### 6.2 集成测试

- [ ] 端到端 actor 执行测试
- [ ] Continuation resume 测试
- [ ] 多消息处理测试
- [ ] 定时器调度测试
- [ ] 单块原子性测试（成功和失败场景）

### 6.3 确定性测试

- [ ] 跨平台一致性测试（x86, ARM）
- [ ] Hash seed 固定性测试
- [ ] SoftFloat 确定性测试
- [ ] ordered_set 确定性测试
- [ ] CBOR 序列化确定性测试

---

## 七、风险评估和缓解

### 7.1 高风险项

1. **借用检查器问题**
   - **风险**：可能无法完全解决，需要重构
   - **缓解**：使用方案 A（提取副作用），如果不行考虑 unsafe（不推荐）

2. **Continuation 状态管理**
   - **风险**：状态序列化/反序列化可能有问题
   - **缓解**：充分测试，使用 CBOR 标准格式

### 7.2 中风险项

1. **单块原子性**
   - **风险**：副作用处理顺序可能有问题
   - **缓解**：严格按照白皮书要求，先提交存储，再处理副作用

2. **确定性执行**
   - **风险**：某些操作可能仍然非确定性
   - **缓解**：启用所有确定性选项，添加测试

---

## 八、参考文档索引

### 核心技术文档
- `refs/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md` - **核心技术白皮书（最高优先级）**

### PVM 相关文档
- `refs/PVM_Continuation_Design_CN.md` - Continuation 设计草案
- `refs/PVM_Checkpoint_File_Bytes_API_CN.md` - Checkpoint API 设计
- `refs/PVM_CHAIN_INTEGRATION_CN.md` - PVM 链集成方案
- `refs/Function_Checkpoint_Support.md` - 函数级 Checkpoint 支持
- `refs/Block_Stack_Checkpoint_Support.md` - Block Stack 支持

### 开发计划
- `refs/Cowboy_PVM_Task_Plan.md` - SDK 开发任务计划
- `refs/PVM_Coding_Guidelines.md` - PVM 编码规范

### API 参考
- `refs/pvm/api/host-api-reference.md` - Host API 参考
- `refs/pvm/api/runtime-api-reference.md` - Runtime API 参考
- `refs/chain/api/pvm-host-implementation.md` - Chain Host 实现参考

---

## 九、下一步行动

### 立即行动（今天）

1. ✅ 解决借用检查器问题
   - 创建 `ExecutionSideEffects` 结构
   - 重构 `execute_handler` 返回类型
   - 更新 `execution.rs` 中的调用代码

2. ✅ 验证编译通过
   - 运行 `cargo check`
   - 修复所有编译错误

### 本周完成

3. 完善单块原子性
4. 实现基础 Continuation 支持
5. 添加单元测试

### 下周计划

6. Guard 机制实现
7. 消息和定时器处理完善
8. 集成测试

---

## 十、总结

基于核心技术白皮书的分析，当前升级工作的关键点：

1. **必须解决借用检查器问题** - 这是阻塞性问题
2. **必须确保单块原子性** - 这是白皮书的核心要求
3. **必须支持 Continuation** - 这是 Actor 模型的关键特性
4. **必须确保确定性执行** - 这是共识的基础

所有实现必须严格遵循核心技术白皮书的要求，任何冲突以白皮书为准。
