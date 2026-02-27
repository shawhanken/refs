# Cowboy Node 编译安装启动指南

> **仓库**: [cowboyinc/node](https://github.com/cowboyinc/node) (main 分支)  
> **版本**: v0.0.16 | **Rust 最低版本**: 1.89.0 | **更新日期**: 2026-02-25

---

## 1. 项目概述

Cowboy Node 是一个基于 Actor 模型的 Layer-1 区块链节点。代码仓库采用 Cargo Workspace 结构，包含以下模块：

| 模块 | 说明 | 产出二进制 |
|------|------|-----------|
| `chain` | 区块链核心（共识、引擎、RPC） | `validator`、`setup`、`genesis_migrate` |
| `cli` | 命令行客户端 | `cowboy` |
| `client` | Rust SDK 客户端库 | — (库) |
| `indexer` | 区块数据索引服务 | `indexer` |
| `inspector` | 链上活动检查工具 | — |
| `runner` | Runner 集成模块 | — |
| `storage` | 存储层抽象 | — |
| `types` | 公共类型定义 | — |
| `pvm` | PVM（RustPython 虚拟机 fork） | `pvm` (独立编译) |

---

## 2. 系统要求

### 2.1 硬件要求

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核+ |
| 内存 | 8 GB | 16 GB+ |
| 磁盘 | 50 GB SSD | 100 GB+ SSD |

### 2.2 操作系统

- **Ubuntu 22.04 / 24.04 LTS** (推荐)
- 其他 Linux 发行版亦可（需自行适配包管理器）

---

## 3. 环境准备

### 3.1 安装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    protobuf-compiler \
    libssl-dev \
    pkg-config \
    clang \
    cmake \
    git
```

> **说明**: `protobuf-compiler` 用于编译 Protobuf 定义；`clang` 和 `cmake` 是部分 crate 的 C/C++ 编译依赖。

### 3.2 安装 Rust 工具链

```bash
# 安装 rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# 加载环境变量
source "$HOME/.cargo/env"

# 安装指定版本 (仓库要求 >= 1.89.0，CI 使用 1.92.0)
rustup install 1.92.0
rustup default 1.92.0

# 验证
rustc --version   # 应输出 >= 1.89.0
cargo --version
```

---

## 4. 获取代码

```bash
# 克隆仓库
git clone git@github.com:cowboyinc/node.git
cd node

# 确认在 main 分支
git checkout main
git pull origin main
```

> **PVM 子目录**: `pvm/` 目录内嵌的是 RustPython 的定制版本（PVM），它在 `Cargo.toml` 中通过 `exclude = ["pvm"]` 排除在主 workspace 之外，但 `chain` crate 通过 `path` 依赖引用了 `pvm/crates/pvm-host` 和 `pvm/crates/pvm-runtime`，因此整个 `pvm/` 目录必须存在。

---

## 5. 编译

### 5.1 Debug 构建（开发调试用）

```bash
# 编译全部 workspace 成员
cargo build

# 只编译四个主要二进制
cargo build --bin validator --bin setup --bin indexer --bin cowboy
```

### 5.2 Release 构建（生产部署用）

```bash
cargo build --release --bin validator --bin setup --bin indexer --bin cowboy
```

> **编译时间**: Release 首次编译约 15–30 分钟（取决于机器配置）。  
> **产物位置**: `target/release/` 目录下的 `validator`、`setup`、`indexer`、`cowboy` 四个二进制文件。

### 5.3 编译配置说明

根据 `Cargo.toml` 的 profile 配置：

```toml
[profile.release]
overflow-checks = true   # 生产环境开启溢出检查，牺牲少量性能确保安全
lto = "thin"             # PVM 启用 thin LTO 优化

[env]
RUST_MIN_STACK = "16777216"  # 16 MB 最小线程栈（Cargo 级别设置）
```

---

## 6. 配置与启动

### 6.1 生成测试网络配置

使用 `setup` 工具生成本地测试所需的 peers 和 validator 配置文件：

```bash
# 清除旧数据
rm -rf test

# 生成单节点本地测试配置
cargo run --bin setup -- generate \
    --peers 1 \
    --bootstrappers 1 \
    --worker-threads 6 \
    --log-level info \
    --message-backlog 16384 \
    --mailbox-size 16384 \
    --deque-size 10 \
    --signature-threads 2 \
    --output test \
    local \
    --start-port 3000 \
    --indexer-port 8080
```

执行完成后会在 `test/` 目录下生成：
- `peers.yaml` — 节点网络对等信息
- `genesis.json` — 创世配置（包含初始账户余额分配、faucet 账户）
- `<validator_pubkey>.yaml` — Validator 配置文件（以公钥命名）
- `storage/` — 链数据存储目录

**端口说明**：
- P2P 端口从 `--start-port` 开始（每节点占 2 个端口：P2P + Metrics）
- RPC 端口固定为 **4000**（硬编码在 setup 中）
- Indexer 端口由 `--indexer-port` 指定（上例为 8080）

### 6.2 启动 Validator 节点

#### 方法一：直接 cargo run

```bash
# 设置环境变量
export RUST_BACKTRACE=1
export RUST_LOG=info
export RUST_MIN_STACK=33554432   # 32 MB，PVM 执行必需

# 启动 (替换为实际的配置文件名)
cargo run --bin validator -- \
    --peers=test/peers.yaml \
    --config=test/<validator_pubkey>.yaml \
    --enable-faucet   # 推荐：本地开发时启用水龙头
```

#### 方法二：使用 start_validator.sh

> ⚠️ **注意**: 脚本内默认路径为 `/home/ubuntu/workspace/node`，使用前必须修改 `NODE_DIR` 和 `CONFIG_FILE` 变量指向你的实际路径。

```bash
# 编辑脚本内的路径
vim start_validator.sh   # 修改 NODE_DIR 和 CONFIG_FILE

# 前台运行
./start_validator.sh --foreground

# 或后台运行（日志写入 test/validator.log）
./start_validator.sh
```

#### 方法三：Release 二进制直接运行

```bash
export RUST_MIN_STACK=33554432

./target/release/validator \
    --peers=test/peers.yaml \
    --config=test/<validator_pubkey>.yaml \
    --enable-faucet   # 可选：启用水龙头端点（仅限本地/开发链）
```

### 6.3 重要环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RUST_MIN_STACK` | `33554432` (32 MB) | **必须设置**。PVM (RustPython) 递归执行需要大栈空间，否则会 stack overflow |
| `RUST_LOG` | `info` | 日志级别，支持模块级别设置如 `cowboy_chain=debug,commonware_consensus=info` |
| `RUST_BACKTRACE` | `1` | 崩溃时打印完整堆栈 |
| `ENABLE_FAUCET` | 未设置 | 设为 `1` 可启用 faucet 端点（仅限开发链） |

### 6.4 启动 Indexer（可选）

如果 `setup` 时指定了 `--indexer-port`，需要单独启动 Indexer 服务。`setup` 完成后会输出启动命令：

```bash
cargo run --bin indexer -- --port 8080 --identity <identity_key>
```

> `<identity_key>` 由 `setup` 命令输出，格式为 BLS12-381 公钥。

---

## 7. 验证节点运行

### 7.1 检查进程

```bash
ps aux | grep validator | grep -v grep
```

### 7.2 检查 RPC 端口

```bash
# 默认 RPC 端口为 4000
curl -s http://localhost:4000/height
```

### 7.3 Swagger API 文档

节点启动后自带交互式 API 文档，浏览器访问：

```
http://localhost:4000/swagger-ui
```

可查看和测试全部 API 端点（交易、区块、账户、Actor、Runner、Job 等）。

### 7.4 查看日志

```bash
# 如果后台运行
tail -f test/validator.log

# 过滤关键日志
tail -f test/validator.log | grep -E 'INFO|WARN|ERROR'
```

### 7.5 使用 Faucet 获取测试 CBY

如果启动时加了 `--enable-faucet`，可以给账户充值测试代币（每次 1000 CBY）：

```bash
curl -X POST http://localhost:4000/faucet \
    -H "Content-Type: application/json" \
    -d '{"address": "<你的公钥地址 hex>"}'
```

> Faucet 仅在 chain_id 为 local (1) 或 dev (100) 时可用。

---

## 8. CLI 客户端使用

`cowboy` CLI 用于与节点交互：

```bash
# 编译 CLI
cargo build --release --bin cowboy

# 示例命令
./target/release/cowboy --indexer-url http://localhost:4000 account balance --address <地址>
./target/release/cowboy --indexer-url http://localhost:4000 account nonce --address <地址>
./target/release/cowboy --indexer-url http://localhost:4000 account info --address <地址>
```

### 8.2 端到端：部署一个 Actor

节点启动后，可以直接运行内置的 Demo 验证完整流程：

```bash
# 运行 pvm_chain_demo（自动创建账户 → 部署 Actor → 调用 → 查询状态）
CHAIN_URL=http://localhost:4000 cargo run --example pvm_chain_demo
```

或使用 CLI 手动部署：

```bash
# 1. 先通过 faucet 给账户充值
curl -X POST http://localhost:4000/faucet \
    -H "Content-Type: application/json" \
    -d '{"address": "<你的地址>"}'

# 2. 部署 Actor
./target/release/cowboy --indexer-url http://localhost:4000 \
    actor deploy \
    --code my_actor.py \
    --salt 0x$(openssl rand -hex 16) \
    --cycles-limit 10000000 \
    --cells-limit 10000000
```

更多示例参见 `chain/examples/` 目录（`deferred_counter_demo`、`llm_chat` 等）。

---

## 9. CI/CD 流程

GitHub Actions Pipeline（`.github/workflows/pipeline.yml`）定义了以下自动化流程：

```
push to main
    │
    ├── Test → Build Binaries → Upload to S3 → Deploy to Dev (ASG Refresh)
    │
push to feature/* / fix/* / hotfix/*
    │
    └── Test → Create Ephemeral Environment
    
delete branch
    │
    └── Destroy Ephemeral Environment
```

**CI 构建命令**:
```bash
cargo build --release --bin validator --bin setup --bin indexer --bin cowboy
```

**CI 系统依赖**:
```bash
sudo apt-get install -y protobuf-compiler libssl-dev pkg-config clang cmake
```

---

## 10. 常见问题

### Q: 编译时报 stack overflow

**A**: 设置环境变量：
```bash
export RUST_MIN_STACK=33554432
```
这是 PVM (RustPython) 虚拟机需要的大线程栈空间（32 MB）。

### Q: 编译报 protobuf 相关错误

**A**: 确保安装了 `protobuf-compiler`：
```bash
sudo apt-get install -y protobuf-compiler
```

### Q: Validator 启动后崩溃

**A**: 检查以下几点：
1. `RUST_MIN_STACK` 是否设置为 `33554432`
2. `peers.yaml` 和 validator 配置文件是否存在
3. 查看日志文件获取具体错误信息

### Q: 如何重置链数据

**A**: 清除 `test/` 下的数据库和日志文件：
```bash
rm -rf test/*.db test/*.log test/storage
```

---

## 11. 附录：项目目录结构

```
node/
├── Cargo.toml              # Workspace 根配置
├── Cargo.lock              # 依赖锁定文件
├── chain/                  # 区块链核心（validator, setup, genesis_migrate）
│   ├── src/
│   │   ├── bin/
│   │   │   ├── validator.rs    # Validator 节点入口
│   │   │   ├── setup.rs        # 配置生成工具入口
│   │   │   └── genesis_migrate.rs
│   │   └── ...
│   └── examples/           # 示例 Actor 应用
├── cli/                    # CLI 客户端 (cowboy)
│   └── src/
│       ├── main.rs
│       ├── commands.rs
│       └── config.rs
├── client/                 # Rust SDK 客户端库
├── indexer/                # 索引服务
├── inspector/              # 检查工具
├── runner/                 # Runner 集成
├── storage/                # 存储抽象层
├── types/                  # 公共类型
├── pvm/                    # PVM (RustPython fork)
│   ├── crates/
│   │   ├── pvm-host/       # PVM 宿主接口（chain 依赖）
│   │   └── pvm-runtime/    # PVM 运行时（chain 依赖）
│   └── Lib/                # Python 标准库
├── run_build.sh            # 快速构建脚本
├── start_validator.sh      # Validator 启动脚本
├── restart_validator.sh    # Validator 重启脚本
└── diagnose_runner.sh      # Runner 诊断脚本
```
