# PVM Host API 参考

## HostApi Trait

`HostApi` trait 定义了 PVM 执行环境与链交互的接口。

### 位置
`pvm/crates/pvm-host/src/lib.rs`

### Trait 定义

```rust
pub trait HostApi {
    // 状态管理
    fn state_get(&self, key: &[u8]) -> HostResult<Option<Bytes>>;
    fn state_set(&mut self, key: &[u8], value: &[u8]) -> HostResult<()>;
    fn state_delete(&mut self, key: &[u8]) -> HostResult<()>;

    // 事件
    fn emit_event(&mut self, topic: &str, data: &[u8]) -> HostResult<()>;

    // Gas 管理
    fn charge_gas(&mut self, amount: u64) -> HostResult<()>;
    fn gas_left(&self) -> u64;

    // 上下文
    fn context(&self) -> HostContext;
    fn randomness(&self, domain: &[u8]) -> HostResult<[u8; 32]>;

    // 消息和定时器
    fn send_message(&mut self, target: &[u8], payload: &[u8]) -> HostResult<()>;
    fn schedule_timer(&mut self, height: u64, payload: &[u8]) -> HostResult<Bytes>;
    fn cancel_timer(&mut self, timer_id: &[u8]) -> HostResult<()>;
}
```

## HostContext 结构体

```rust
#[derive(Clone, Debug)]
pub struct HostContext {
    pub block_height: u64,
    pub block_hash: [u8; 32],
    pub tx_hash: [u8; 32],
    pub sender: Bytes,
    pub timestamp_ms: u64,
    pub actor_addr: Bytes,
    pub msg_id: Bytes,
    pub nonce: u64,
}
```

## HostError 枚举

```rust
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum HostError {
    OutOfGas,
    InvalidInput,
    NotFound,
    StorageError,
    Forbidden,
    Internal,
}
```

## 版本信息

- **当前版本**: 0.4.0
- **最后更新**: 2025-01-XX
- **兼容性**: 向后兼容，无破坏性变化
