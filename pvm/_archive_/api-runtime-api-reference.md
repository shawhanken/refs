# PVM Runtime API 参考

## 执行函数

### execute_tx

简单的执行函数，使用默认选项。

```rust
pub fn execute_tx(
    host: &mut dyn HostApi,
    code: &[u8],
    input: &[u8]
) -> Result<Bytes, HostError>
```

### execute_tx_with_options

带选项的执行函数，支持更多配置。

```rust
pub fn execute_tx_with_options(
    host: &mut dyn HostApi,
    code: &[u8],
    input: &[u8],
    options: &ExecutionOptions,
) -> Result<Bytes, HostError>
```

## ExecutionOptions

执行选项配置结构体。

```rust
#[derive(Clone, Debug)]
pub struct ExecutionOptions {
    pub argv: Vec<String>,
    pub module_name: String,
    pub source_path: String,
    pub input_var: String,
    pub output_var: String,
    pub entrypoint: Option<String>,
    pub host_module_name: String,
    pub init_stdlib: bool,
    pub deterministic: bool,
    pub hash_seed: Option<u32>,
    pub determinism: Option<DeterminismOptions>,
    pub set_main_module: bool,
    pub continuation: Option<ContinuationOptions>,
}
```

### 默认值

```rust
impl Default for ExecutionOptions {
    fn default() -> Self {
        Self {
            argv: Vec::new(),
            module_name: "__main__".to_owned(),
            source_path: "<pvm>".to_owned(),
            input_var: "__pvm_input__".to_owned(),
            output_var: "__pvm_output__".to_owned(),
            entrypoint: None,
            host_module_name: "pvm_host".to_owned(),
            init_stdlib: true,
            deterministic: false,
            hash_seed: None,
            determinism: None,
            set_main_module: true,
            continuation: Some(ContinuationOptions::default()),
        }
    }
}
```

## ContinuationOptions

Continuation 和 checkpoint 功能配置。

```rust
#[derive(Clone, Debug)]
pub struct ContinuationOptions {
    pub mode: ContinuationMode,
    pub resume_bytes: Option<Vec<u8>>,
    pub resume_key: Option<Vec<u8>>,
    pub checkpoint_key: Option<Vec<u8>>,
}
```

### ContinuationMode

```rust
pub enum ContinuationMode {
    Fsm,      // 有限状态机模式
    // 其他模式...
}
```

## RuntimeConfig

运行时配置。

```rust
#[derive(Clone, Copy, Debug)]
pub struct RuntimeConfig {
    pub continuation_mode: ContinuationMode,
}
```

## 使用示例

```rust
use pvm_runtime::{execute_tx_with_options, ExecutionOptions, ContinuationOptions};
use rustpython_vm::vm::ContinuationMode;

let mut host = CowboyHost::new(ctx);
let output = execute_tx_with_options(
    &mut host,
    &actor_code,
    &input_payload,
    &ExecutionOptions {
        entrypoint: Some("handler".to_string()),
        module_name: "actor".to_string(),
        deterministic: true,
        continuation: Some(ContinuationOptions {
            mode: ContinuationMode::Fsm,
            checkpoint_key: Some(b"checkpoint".to_vec()),
            ..Default::default()
        }),
        ..Default::default()
    }
)?;
```

## 版本信息

- **当前版本**: 0.4.0
- **最后更新**: 2025-01-XX
- **新功能**: Continuation/Checkpoint 支持
