# Checkpoint 模式下的 Deferred Transaction 演示方案

**设计日期**: 2026-01-19  
**目标**: 完整演示 Continuation Checkpoint + Deferred Transaction 的协作

---

## 一、核心概念

### 1.1 场景描述

**业务场景**: 一个长时间运行的任务（例如：批量处理数据）

**流程**:
```
Block N:
  1. 用户发送交易 → Actor 开始处理
  2. Actor 执行到某个检查点
  3. 保存 Checkpoint 状态到 storage
  4. 创建 Deferred Transaction
  5. 返回（当前块完成）

Block N+1:
  6. Deferred Transaction 被包含
  7. Actor 从 Checkpoint 恢复
  8. 继续处理剩余任务
  9. 完成或创建下一个 Checkpoint
```

### 1.2 技术要点

**Checkpoint 模式**:
- 状态存储在 `__continuation:{message_id}`
- 包含：VM 状态、局部变量、执行位置

**Deferred Transaction**:
- 使用 origin_tx_hash 关联原始交易
- 共享原始交易的剩余 Gas
- 在下一个块自动执行

**协作**:
- Checkpoint 保存执行状态
- Deferred Transaction 触发恢复
- 两者结合实现跨块的长任务

---

## 二、实现方案

### 2.1 Actor 代码设计

**Python Actor**: `batch_processor.py`

```python
"""
Batch Processor Actor - 演示 Checkpoint + Deferred Transaction

功能：
- 处理大量数据（模拟长时间任务）
- 在检查点保存状态
- 通过 Deferred Transaction 恢复
"""

def handler_init(ctx, input):
    """初始化：设置批次大小和总数据量"""
    total_items = int.from_bytes(input[:8], 'big')
    batch_size = int.from_bytes(input[8:16], 'big')
    
    ctx.state[b'config:total_items'] = total_items.to_bytes(8, 'big')
    ctx.state[b'config:batch_size'] = batch_size.to_bytes(8, 'big')
    ctx.state[b'progress:processed'] = (0).to_bytes(8, 'big')
    
    return b"initialized"


def handler_process_batch(ctx, input):
    """
    处理批次：演示 Checkpoint + Deferred Transaction
    
    流程：
    1. 读取当前进度
    2. 处理一个批次
    3. 更新进度
    4. 如果还有剩余，创建 Deferred Transaction
    """
    # 读取配置和进度
    total_items = int.from_bytes(ctx.state.get(b'config:total_items', b'\x00' * 8), 'big')
    batch_size = int.from_bytes(ctx.state.get(b'config:batch_size', b'\x00' * 8), 'big')
    processed = int.from_bytes(ctx.state.get(b'progress:processed', b'\x00' * 8), 'big')
    
    # 计算本次处理范围
    start_idx = processed
    end_idx = min(processed + batch_size, total_items)
    
    # 模拟处理（消耗 gas）
    result = []
    for i in range(start_idx, end_idx):
        # 模拟处理一个项目
        item_result = process_item(i)
        result.append(item_result)
        
        # 消耗 gas（模拟计算）
        ctx.charge_gas(100)
    
    # 更新进度
    new_processed = end_idx
    ctx.state[b'progress:processed'] = new_processed.to_bytes(8, 'big')
    
    # 保存结果
    result_key = f'result:batch_{processed // batch_size}'.encode()
    ctx.state[result_key] = b','.join([str(r).encode() for r in result])
    
    # 检查是否完成
    if new_processed >= total_items:
        # 全部完成
        ctx.state[b'status'] = b'completed'
        return f"completed: processed {new_processed}/{total_items}".encode()
    else:
        # 还有剩余，创建 Deferred Transaction
        # 注意：这里我们通过 Host API 创建 deferred tx
        # 实际实现中，这应该通过 ctx.create_deferred_tx() 或类似方法
        
        # 保存 checkpoint 状态（PVM 会自动处理）
        # 状态已经通过 continuation 机制保存
        
        # 返回信息，指示需要继续
        return f"checkpoint: processed {new_processed}/{total_items}, deferred tx created".encode()


def handler_resume_from_checkpoint(ctx, input):
    """
    从 Checkpoint 恢复执行
    
    这个 handler 会被 Deferred Transaction 调用
    PVM 会自动从 __continuation:{message_id} 恢复状态
    """
    # 读取进度
    processed = int.from_bytes(ctx.state.get(b'progress:processed', b'\x00' * 8), 'big')
    total_items = int.from_bytes(ctx.state.get(b'config:total_items', b'\x00' * 8), 'big')
    
    # 继续处理（调用 process_batch）
    return handler_process_batch(ctx, input)


def process_item(item_id):
    """模拟处理单个项目"""
    # 简单的计算（实际可能是复杂的数据处理）
    return item_id * 2
```

### 2.2 Host API 扩展

**需要添加**: `create_deferred_tx` 方法

```rust
// chain/src/pvm_host.rs

impl<'a, S: StateStore> HostApi for CowboyHost<'a, S> {
    // ... 现有方法 ...
    
    /// Create a deferred transaction to continue execution in next block
    /// This is called from Python code: ctx.create_deferred_tx(handler, payload)
    fn create_deferred_tx(&mut self, handler: &str, payload: &[u8]) -> HostResult<()> {
        // 记录到 side effects，在块提交时创建 deferred tx
        // 注意：这需要修改 PvmExecutionContext 来支持
        // 当前实现中，deferred tx 是通过 send_message 创建的
        
        // 临时方案：通过 send_message 机制
        // 发送一个特殊的消息给自己，在下一个块触发 resume
        let resume_payload = format!("resume:{}", handler).into_bytes();
        self.send_message(
            &self.ctx.actor_address.as_ref().to_vec(),
            &resume_payload
        )?;
        
        Ok(())
    }
}
```

**更好的方案**: 直接在 PvmExecutionContext 中支持

```rust
// chain/src/pvm_host.rs

pub struct PvmExecutionContext<'a, S: StateStore> {
    // ... 现有字段 ...
    
    /// Deferred transactions to create: Vec<(handler, payload)>
    pub deferred_tx_requests: Arc<Mutex<Vec<(String, Vec<u8>)>>>,
}

impl<'a, S: StateStore> PvmExecutionContext<'a, S> {
    // ... 现有方法 ...
    
    pub fn request_deferred_tx(&mut self, handler: String, payload: Vec<u8>) {
        self.deferred_tx_requests.lock().unwrap().push((handler, payload));
    }
}
```

### 2.3 执行流程修改

**在 `execute_actor_handler_impl` 中处理 deferred tx 请求**:

```rust
// chain/src/execution.rs

async fn execute_actor_handler_impl<S: StateStore>(
    &mut self,
    // ... 参数 ...
) -> Result<(), ExecutionError> {
    // ... 现有代码 ...
    
    // 执行 PVM handler
    let exec_result = {
        let pvm_ctx_ptr: *mut PvmExecutionContext<'_, S> = &mut pvm_ctx;
        self.pvm_executor.execute_handler(
            unsafe { &mut *pvm_ctx_ptr },
            payload,
            handler,
        ).await
    };
    
    match exec_result {
        Ok((output, state_snapshot)) => {
            // 提取 side effects
            let events = side_effects_refs.events.lock().unwrap().clone();
            let messages = side_effects_refs.outgoing_messages.lock().unwrap().clone();
            
            // 检查是否有 deferred tx 请求
            let deferred_requests = pvm_ctx.deferred_tx_requests.lock().unwrap().clone();
            
            // 如果有 deferred tx 请求，创建它们
            for (handler, payload) in deferred_requests {
                // 计算剩余 gas
                let remaining_cycles = gas_meters.cycles.remaining();
                let remaining_cells = gas_meters.cells.remaining();
                
                // 创建 deferred transaction
                const DEFERRED_CYCLES_LIMIT: u64 = 100_000;
                const DEFERRED_CELLS_LIMIT: u64 = 100_000;
                
                if remaining_cycles >= DEFERRED_CYCLES_LIMIT && 
                   remaining_cells >= DEFERRED_CELLS_LIMIT {
                    let deferred_instruction = cowboy_types::Instruction::Actor(
                        cowboy_types::ActorInstruction::ExecuteActor {
                            actor: actor_address_clone.clone(),
                            handler: handler.clone(),
                            payload: payload.clone(),
                        }
                    );
                    
                    let deferred_tx = Transaction::create_deferred(
                        origin_tx_hash,
                        remaining_cycles,
                        remaining_cells,
                        deferred_instruction,
                        DEFERRED_CYCLES_LIMIT,
                        DEFERRED_CELLS_LIMIT,
                    );
                    
                    let deferred_tx_hash = deferred_tx.digest();
                    deferred_tx_hashes.push(deferred_tx_hash);
                    self.pending_deferred_txs.insert(deferred_tx_hash, deferred_tx);
                }
            }
            
            // 提交状态
            // ... 现有代码 ...
        }
        Err((error, state_snapshot)) => {
            // 回滚
            // ... 现有代码 ...
        }
    }
}
```

---

## 三、完整演示流程

### 3.1 部署 Actor

**交易 1**: Deploy Actor
```rust
let deploy_tx = Transaction::sign(
    &private_key,
    nonce: 0,
    Instruction::Actor(ActorInstruction::DeployActor {
        code: batch_processor_code.as_bytes().to_vec(),
        salt: vec![0u8; 32],
    }),
    cycles_limit: 1_000_000,
    cells_limit: 1_000_000,
    max_fee_per_cycle: 1,
    max_fee_per_cell: 1,
);
```

### 3.2 初始化任务

**交易 2**: Initialize
```rust
let init_payload = {
    let mut payload = Vec::new();
    payload.extend_from_slice(&(1000u64).to_be_bytes());  // total_items
    payload.extend_from_slice(&(100u64).to_be_bytes());   // batch_size
    payload
};

let init_tx = Transaction::sign(
    &private_key,
    nonce: 1,
    Instruction::Actor(ActorInstruction::ExecuteActor {
        actor: actor_address,
        handler: "init".to_string(),
        payload: init_payload,
    }),
    cycles_limit: 500_000,
    cells_limit: 500_000,
    max_fee_per_cycle: 1,
    max_fee_per_cell: 1,
);
```

**执行结果**:
- `state[config:total_items] = 1000`
- `state[config:batch_size] = 100`
- `state[progress:processed] = 0`

### 3.3 开始处理（创建 Checkpoint）

**交易 3**: Process First Batch
```rust
let process_tx = Transaction::sign(
    &private_key,
    nonce: 2,
    Instruction::Actor(ActorInstruction::ExecuteActor {
        actor: actor_address,
        handler: "process_batch".to_string(),
        payload: vec![],  // 空 payload，从 state 读取配置
    }),
    cycles_limit: 500_000,
    cells_limit: 500_000,
    max_fee_per_cycle: 1,
    max_fee_per_cell: 1,
);
```

**执行流程**:
1. 读取 `state[config:total_items] = 1000`
2. 读取 `state[config:batch_size] = 100`
3. 读取 `state[progress:processed] = 0`
4. 处理 items 0-99（消耗 gas）
5. 更新 `state[progress:processed] = 100`
6. 保存 `state[result:batch_0] = "0,2,4,...,198"`
7. **创建 Checkpoint**（PVM 自动保存到 `__continuation:{message_id}`）
8. **创建 Deferred Transaction**（调用 `resume_from_checkpoint` handler）
9. 返回：`"checkpoint: processed 100/1000, deferred tx created"`

**Block N 结果**:
- ✅ 处理了 100 个项目
- ✅ Checkpoint 状态已保存
- ✅ Deferred Transaction 已创建（在 pending_deferred_txs）

### 3.4 恢复执行（Deferred Transaction）

**Block N+1**: Deferred Transaction 自动执行

**执行流程**:
1. **Deferred Transaction 被包含在块中**
   - `origin_tx_hash` = 交易 3 的 hash
   - `handler` = "resume_from_checkpoint"
   - `payload` = 空或包含恢复信息

2. **PVM 检测到 Continuation**
   - 从 `__continuation:{message_id}` 加载状态
   - 恢复 VM 状态、局部变量、执行位置

3. **继续执行**
   - 调用 `handler_resume_from_checkpoint`
   - 读取 `state[progress:processed] = 100`
   - 处理 items 100-199
   - 更新 `state[progress:processed] = 200`
   - 如果还有剩余，创建下一个 Deferred Transaction

**Block N+1 结果**:
- ✅ 从 Checkpoint 恢复成功
- ✅ 处理了下一个 100 个项目
- ✅ 创建了下一个 Deferred Transaction（如果还有剩余）

### 3.5 完成

**Block N+10**: 最后一个批次

**执行流程**:
1. 处理 items 900-999
2. 更新 `state[progress:processed] = 1000`
3. 设置 `state[status] = "completed"`
4. **不再创建 Deferred Transaction**
5. 返回：`"completed: processed 1000/1000"`

---

## 四、关键技术细节

### 4.1 Checkpoint 状态存储

**存储键格式**:
```
__continuation:{message_id}
```

**message_id 计算**:
```rust
// chain/src/execution.rs
let tx_hash = {
    let mut hasher = Sha256::new();
    hasher.update(&tx.nonce.to_be_bytes());
    hasher.update(tx.public.as_ref());
    hasher.update(payload);
    hasher.finalize()
};
```

**状态内容**（由 PVM 管理）:
- VM 执行状态
- 局部变量（通过 capture()）
- 执行位置（lasti, stack, blocks）

### 4.2 Deferred Transaction 创建

**时机**:
- 在 `execute_actor_handler_impl` 中
- 在执行成功后
- 当 Actor 请求时（通过 Host API）

**Gas 分配**:
```rust
// 从原始交易的剩余 gas 中分配
let remaining_cycles = gas_meters.cycles.remaining();
let remaining_cells = gas_meters.cells.remaining();

// 创建 deferred tx，使用部分剩余 gas
const DEFERRED_CYCLES_LIMIT: u64 = 100_000;
const DEFERRED_CELLS_LIMIT: u64 = 100_000;

let deferred_tx = Transaction::create_deferred(
    origin_tx_hash,
    remaining_cycles,
    remaining_cells,
    instruction,
    DEFERRED_CYCLES_LIMIT,
    DEFERRED_CELLS_LIMIT,
);
```

### 4.3 Continuation Resume

**检测**:
```rust
// chain/src/pvm_executor.rs

// 检查是否是 continuation resume
let continuation_key = if tx_is_deferred {
    // Deferred tx 使用相同的 message_id（从 origin_tx_hash 派生）
    Some(format!("__continuation:{}", hex::encode(&origin_tx_hash)))
} else {
    None
};
```

**恢复**:
```rust
// PVM 自动处理
options.continuation = Some(ContinuationOptions {
    mode: ContinuationMode::Checkpoint,
    checkpoint_key: continuation_key.clone(),
    resume_key: continuation_key.clone(),
});
```

---

## 五、实现步骤

### Phase 1: 基础支持（1-2 天）

**任务**:
1. ✅ 验证当前 Checkpoint 实现
2. ✅ 验证当前 Deferred Transaction 实现
3. ⏳ 添加 `create_deferred_tx` Host API
4. ⏳ 修改 `execute_actor_handler_impl` 处理 deferred tx 请求

**代码修改**:
- `chain/src/pvm_host.rs`: 添加 `create_deferred_tx` 方法
- `chain/src/pvm_host.rs`: 添加 `deferred_tx_requests` 字段
- `chain/src/execution.rs`: 处理 deferred tx 请求

### Phase 2: Python Actor（1 天）

**任务**:
1. 编写 `batch_processor.py`
2. 实现 `handler_init`
3. 实现 `handler_process_batch`
4. 实现 `handler_resume_from_checkpoint`

### Phase 3: 集成测试（1-2 天）

**任务**:
1. 编写端到端测试
2. 验证 Checkpoint 保存
3. 验证 Deferred Transaction 创建
4. 验证 Continuation Resume
5. 验证多块执行

**测试场景**:
```rust
#[test]
fn test_checkpoint_deferred_tx_flow() {
    // 1. 部署 Actor
    // 2. 初始化（1000 items, batch_size=100）
    // 3. 执行第一个批次
    //    - 验证 Checkpoint 创建
    //    - 验证 Deferred Transaction 创建
    // 4. 执行 Deferred Transaction
    //    - 验证从 Checkpoint 恢复
    //    - 验证继续处理
    // 5. 重复直到完成
    //    - 验证所有 1000 个项目都被处理
}
```

### Phase 4: 文档和示例（1 天）

**任务**:
1. 编写使用文档
2. 创建示例代码
3. 录制演示视频（可选）

---

## 六、潜在问题和解决方案

### 6.1 Checkpoint 状态过大

**问题**: 如果 VM 状态很大，存储成本高

**解决方案**:
- 只保存必要的状态（通过 capture() 显式指定）
- 压缩状态数据
- 限制 Checkpoint 大小

### 6.2 Gas 耗尽

**问题**: 如果原始交易的 gas 不足，无法创建 deferred tx

**解决方案**:
- 在创建 deferred tx 前检查剩余 gas
- 如果不足，返回错误或部分完成状态
- 允许用户补充 gas（未来功能）

### 6.3 状态冲突

**问题**: 如果多个 deferred tx 同时修改同一状态

**解决方案**:
- 使用 Guard 机制（未来）
- 当前：确保 deferred tx 顺序执行
- 使用 actor nonce 或消息队列

### 6.4 恢复失败

**问题**: 如果 Checkpoint 状态损坏或丢失

**解决方案**:
- 验证 Checkpoint 完整性
- 提供错误恢复机制
- 允许重新开始（如果可能）

---

## 七、演示脚本

### 7.1 完整演示流程

```bash
#!/bin/bash

# 1. 启动 validator
./test2.sh &

# 2. 部署 Actor
cargo run --bin cli -- deploy-actor \
    --code batch_processor.py \
    --salt 00000000000000000000000000000000

# 3. 初始化
cargo run --bin cli -- execute-actor \
    --actor <actor_address> \
    --handler init \
    --payload "1000,100"  # total_items, batch_size

# 4. 开始处理（会创建 Checkpoint 和 Deferred Tx）
cargo run --bin cli -- execute-actor \
    --actor <actor_address> \
    --handler process_batch \
    --payload ""

# 5. 等待下一个块（Deferred Tx 自动执行）

# 6. 查询状态
cargo run --bin cli -- query-state \
    --actor <actor_address> \
    --key "progress:processed"

# 7. 重复步骤 4-6 直到完成
```

### 7.2 验证检查点

```bash
# 检查 Checkpoint 状态
cargo run --bin cli -- query-state \
    --actor <actor_address> \
    --key "__continuation:<message_id>"

# 检查 Deferred Transaction
cargo run --bin cli -- list-deferred-txs \
    --origin-tx-hash <tx_hash>
```

---

## 八、成功标准

### 功能验证

- [ ] ✅ Actor 可以创建 Checkpoint
- [ ] ✅ Checkpoint 状态正确保存
- [ ] ✅ Deferred Transaction 正确创建
- [ ] ✅ Deferred Transaction 在下一个块执行
- [ ] ✅ 从 Checkpoint 正确恢复
- [ ] ✅ 继续执行剩余任务
- [ ] ✅ 多块执行完成整个任务

### 性能验证

- [ ] ✅ Checkpoint 创建时间 < 100ms
- [ ] ✅ Checkpoint 恢复时间 < 100ms
- [ ] ✅ 状态存储大小合理（< 1MB per checkpoint）

### 正确性验证

- [ ] ✅ 所有数据都被处理
- [ ] ✅ 状态一致性
- [ ] ✅ Gas 计费正确
- [ ] ✅ 错误处理正确

---

## 九、后续优化

### 9.1 性能优化

- 增量 Checkpoint（只保存变化）
- 压缩 Checkpoint 数据
- 并行处理多个批次

### 9.2 功能增强

- 支持多个 Checkpoint（嵌套 continuation）
- 支持 Checkpoint 合并
- 支持 Checkpoint 回滚

### 9.3 开发者体验

- 更好的错误信息
- Checkpoint 可视化工具
- 调试支持

---

## 十、总结

这个演示将展示：
1. ✅ **Checkpoint 模式的实际应用**
2. ✅ **Deferred Transaction 的自动执行**
3. ✅ **跨块的长任务处理**
4. ✅ **状态持久化和恢复**

**关键价值**:
- 证明 Cowboy 可以处理长时间运行的任务
- 展示 Continuation 机制的实际用途
- 为 Runner 系统奠定基础

**时间估算**: 3-5 天（包括测试和文档）

**优先级**: 高（这是核心功能的重要演示）

---

**文档版本**: 1.0  
**设计者**: Cursor AI  
**审查**: 待技术团队审查
