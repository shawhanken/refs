# Chain PVM Host 实现参考

## 实现位置

- `chain/src/pvm_host.rs` - HostApi 实现
- `chain/src/pvm_executor.rs` - PVM 执行器

## CowboyHost 实现

### 结构体

```rust
pub struct CowboyHost<'a, S: StateStore> {
    ctx: &'a mut PvmExecutionContext<'a, S>,
}
```

### HostApi 实现

所有必需的方法都已实现：

1. **状态管理**
   - `state_get()` - 从缓存读取
   - `state_set()` - 写入缓存并计费
   - `state_delete()` - 删除并计费

2. **事件**
   - `emit_event()` - 记录事件并计费

3. **Gas 管理**
   - `charge_gas()` - 消耗 cycles
   - `gas_left()` - 返回剩余 cycles

4. **上下文**
   - `context()` - 返回完整的 HostContext（包含 actor_addr, msg_id, nonce）
   - `randomness()` - 基于 block_hash 生成确定性随机数

5. **消息和定时器**
   - `send_message()` - 记录待发送消息
   - `schedule_timer()` - 生成定时器 ID 并记录
   - `cancel_timer()` - 记录待取消的定时器

## PvmExecutionContext

执行上下文，包含：

- Actor 数据和存储缓存
- 区块上下文（height, hash, timestamp）
- Gas 计量器
- 事件、消息、定时器列表
- Message ID 和 nonce

## 存储缓存机制

使用 `ActorStorageCache` 实现同步存储访问：

- 预加载 actor 存储
- 执行期间累积写入
- 提交时批量写入
- 支持回滚

## Gas 计量

使用双 Gas 系统：

- **Cycles**: 用于计算和操作
- **Cells**: 用于存储操作

PVM 的单一 Gas 模型映射到 cycles。

## 版本兼容性

- ✅ 完全兼容 PVM 0.4.0
- ✅ 所有必需方法已实现
- ✅ HostContext 字段完整
