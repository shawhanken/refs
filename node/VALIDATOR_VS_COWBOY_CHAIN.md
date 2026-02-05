# `cowboy-chain` vs `validator` 的区别

## 总结

- **`cowboy-chain`** = Rust **包（crate）名称**
- **`validator`** = 编译后的**二进制可执行文件名称**

它们是同一个东西，只是在不同上下文中的不同名称。

## 详细说明

### 1. `cowboy-chain` - 包名称

`cowboy-chain` 是 Rust 包的名称，定义在 `node/chain/Cargo.toml` 中：

```toml
[package]
name = "cowboy-chain"
version.workspace = true
```

**用途**：
- 在 Rust 代码中作为依赖引用：`use cowboy_chain::...`
- 在 `Cargo.toml` 中作为依赖：`cowboy-chain = { path = "../chain" }`
- 文档和 API 引用

### 2. `validator` - 二进制文件名称

`validator` 是编译后的可执行文件名称，也定义在 `node/chain/Cargo.toml` 中：

```toml
[[bin]]
name = "validator"
path = "src/bin/validator.rs"
```

**用途**：
- 编译后的二进制文件：`target/debug/validator` 或 `target/release/validator`
- 命令行执行：`./validator --config ...`
- 部署和运行

## 编译和使用

### 编译

```bash
# 编译 debug 版本
cd node/chain
cargo build --bin validator

# 编译 release 版本
cargo build --release --bin validator
```

编译后的二进制文件位于：
- Debug: `node/target/debug/validator`
- Release: `node/target/release/validator`

### 运行

```bash
# 使用编译后的二进制文件
./target/release/validator --config test/config.yaml --peers test/peers.yaml

# 或者直接使用 cargo run
cargo run --bin validator -- --config test/config.yaml --peers test/peers.yaml
```

## 为什么有两个名称？

这是 Rust 项目的标准做法：

1. **包名称** (`cowboy-chain`)：
   - 用于代码组织和依赖管理
   - 遵循 Rust 命名约定（kebab-case）
   - 在代码中引用时使用下划线：`cowboy_chain`

2. **二进制名称** (`validator`)：
   - 用于命令行工具
   - 更简洁、易记
   - 反映实际功能（验证节点）

## 其他二进制文件

`cowboy-chain` 包还包含另一个二进制文件：

```toml
[[bin]]
name = "setup"
path = "src/bin/setup.rs"
```

用于设置和初始化验证节点网络。

## 总结

- ✅ **使用 `validator`** 来运行链节点（这是正确的）
- ✅ **使用 `cowboy-chain`** 来引用 Rust 包
- ✅ 两者指向同一个项目，只是在不同上下文中的不同名称

## 相关文件

- `node/chain/Cargo.toml` - 包和二进制定义
- `node/chain/src/bin/validator.rs` - validator 二进制入口
- `node/chain/src/lib.rs` - cowboy-chain 库入口
