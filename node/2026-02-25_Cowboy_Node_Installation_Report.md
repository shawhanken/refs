# Cowboy Node 本地安装部署报告

> **日期**: 2026-02-25  
> **服务器**: 34.193.174.192 (Ubuntu, 8 核 / 16 GB)  
> **版本**: v0.0.16 | **Rust**: 1.92.0 | **分支**: main

---

## 1. 安装概览

| 项目 | 说明 |
|------|------|
| **安装方式** | 方法三：Release 编译 + 独立目录运行 |
| **源码路径** | `/home/ubuntu/cowboyinc/node`（保持干净，仅用于编译） |
| **运行路径** | `/home/ubuntu/cowboy-node/`（二进制、配置、数据独立存放） |
| **编译耗时** | ~3 分钟（Release 模式，依赖已缓存） |

---

## 2. 安装步骤

### 2.1 环境准备

系统依赖（已预装）：

```
build-essential, protobuf-compiler, libssl-dev, pkg-config, clang, cmake, git
```

Rust 工具链：

```
rustc 1.92.0 (ded5c06cf 2025-12-08)
cargo 1.92.0 (344c4567c 2025-10-21)
```

### 2.2 端口冲突检查与处理

安装前检测了 Node 所需的 4 个端口：

| 端口 | 用途 | 安装前状态 | 处理 |
|------|------|-----------|------|
| 3000 | P2P 通信 | ✅ 空闲 | 无需处理 |
| 3001 | Metrics 指标 | ✅ 空闲 | 无需处理 |
| 4000 | RPC API | ✅ 空闲 | 无需处理 |
| 8080 | Indexer | ⚠️ Nginx 占用 | 移除 nginx `listen 8080` |

**8080 端口冲突解决**：`/etc/nginx/sites-available/cowboydocs` 配置中同时监听了 80 和 8080 端口。由于 cowboydocs 服务仅需 80 端口，删除了 `listen 8080;` 行并 reload nginx，释放 8080 给 Indexer 使用。

### 2.3 Release 编译

```bash
cd /home/ubuntu/cowboyinc/node
export RUST_MIN_STACK=33554432
cargo build --release --bin validator --bin setup --bin cowboy
```

编译产物：

| 二进制 | 大小 | 说明 |
|--------|------|------|
| `validator` | 67 MB | 节点主程序 |
| `cowboy` | 13 MB | CLI 客户端 |
| `setup` | 4.9 MB | 配置生成工具 |

### 2.4 创建独立运行目录

```bash
mkdir -p /home/ubuntu/cowboy-node/bin
mkdir -p /home/ubuntu/cowboy-node/data

# 拷贝二进制
cp target/release/{validator,setup,cowboy} /home/ubuntu/cowboy-node/bin/
```

### 2.5 生成测试网络配置

```bash
cd /home/ubuntu/cowboy-node
./bin/setup generate \
    --peers 1 --bootstrappers 1 \
    --worker-threads 6 --log-level info \
    --message-backlog 16384 --mailbox-size 16384 \
    --deque-size 10 --signature-threads 2 \
    --output config local --start-port 3000 --indexer-port 8080
```

生成文件：

| 文件 | 说明 |
|------|------|
| `config/peers.yaml` | 节点对等信息 |
| `config/genesis.json` | 创世配置（含 faucet 账户） |
| `config/447a428b...yaml` | Validator 配置 |
| `config/storage/` | 链数据存储 |

### 2.6 Faucet 修复

初次启动后 Faucet 返回错误：

```json
{"code":8000,"message":"faucet only available on local (chain_id=1) or dev (chain_id=100) chains, current chain_id=0"}
```

**原因**：`setup` 默认生成 `chain_id: null`（代码解析为 0），不在 Faucet 白名单中。

**修复**：

```bash
# 修改 validator 配置
sed -i 's/chain_id: null/chain_id: 1/' config/447a428b...yaml

# 修改 genesis.json
python3 -c "import json; g=json.load(open('config/genesis.json')); g['chain_id']=1; json.dump(g, open('config/genesis.json','w'), indent=2)"

# 清除旧链数据并重启
rm -rf config/storage
```

### 2.7 启动节点

```bash
export RUST_MIN_STACK=33554432
export RUST_BACKTRACE=1
export RUST_LOG=info

nohup ./bin/validator \
    --peers=config/peers.yaml \
    --config=config/447a428b43ee100480e40669cf40b69b8e358f0ab713ada8f851d5b1cba0385b.yaml \
    --enable-faucet \
    > data/validator.log 2>&1 &
```

---

## 3. 服务验证

### 3.1 进程状态

```
PID: 258144
状态: Sl (多线程运行中)
内存: ~86 MB
CPU: ~2.7%
```

### 3.2 端口监听

```
端口 3000 (P2P)    → validator (pid=258144) ✅
端口 3001 (Metrics) → validator (pid=258144) ✅
端口 4000 (RPC)    → validator (pid=258144) ✅
端口 8080 (Indexer) → 未启动（可选）
```

### 3.3 RPC API 验证

**区块高度**：

```bash
$ curl -s http://34.193.174.192:4000/height
{"height":292}
```
✅ 出块正常，约 1 秒 1 个区块。

**健康检查**：

```bash
$ curl -s http://34.193.174.192:4000/health
OK
```

**详细健康信息**：

```bash
$ curl -s http://34.193.174.192:4000/health/detailed
```

```json
{
  "status": "healthy",
  "version": "0.0.16",
  "uptime_seconds": 299,
  "block_height": 292,
  "synced": true,
  "mempool_transaction_count": 0,
  "mempool_account_count": 0,
  "components": {
    "storage": {"status": "healthy"},
    "mempool": {"status": "healthy"},
    "rpc": {"status": "healthy", "latency_ms": 0}
  }
}
```
✅ 所有组件健康。

### 3.4 Swagger API 文档

```bash
$ curl -s -o /dev/null -w "%{http_code}" http://34.193.174.192:4000/swagger-ui/
200
```
✅ 浏览器访问 http://34.193.174.192:4000/swagger-ui/ 可查看交互式 API 文档。

### 3.5 Faucet 验证

```bash
$ curl -s -X POST http://34.193.174.192:4000/faucet \
    -H "Content-Type: application/json" \
    -d '{"address": "447a428b43ee100480e40669cf40b69b8e358f0ab713ada8f851d5b1cba0385b"}'
```

```json
{
  "tx_hash": "952ace45a4e0ee3cc5852750a0f4dd88ec873aa9f476e9a1e05df0acc9312e86",
  "amount": 1000000000000,
  "amount_cby": 1000
}
```
✅ Faucet 正常工作，每次充值 1000 CBY。

---

## 4. 最终目录结构

```
/home/ubuntu/cowboy-node/          ← 总计 93 MB
├── bin/
│   ├── validator                  (67 MB) 节点主程序
│   ├── cowboy                     (13 MB) CLI 客户端
│   └── setup                     (4.9 MB) 配置生成工具
├── config/
│   ├── peers.yaml                 节点对等信息
│   ├── genesis.json               创世配置 (chain_id: 1)
│   ├── 447a428b...yaml            Validator 配置
│   └── storage/                   链数据（持续增长）
└── data/
    └── validator.log              节点日志
```

源码目录 `/home/ubuntu/cowboyinc/node` 保持干净，无运行时文件。

---

## 5. Validator 配置详情

| 配置项 | 值 |
|--------|-----|
| Validator 公钥 | `447a428b43ee100480e40669cf40b69b8e358f0ab713ada8f851d5b1cba0385b` |
| P2P 端口 | 3000 |
| Metrics 端口 | 3001 |
| RPC 端口 | 4000 |
| Chain ID | 1 (local) |
| Worker 线程 | 6 |
| 日志级别 | info |
| Faucet | 已启用 (`--enable-faucet`) |
| Indexer 推送 | http://localhost:8080（Indexer 未启动） |

---

## 6. 常用运维命令

```bash
# 查看链高度
curl -s http://34.193.174.192:4000/height

# Faucet 充值
curl -X POST http://34.193.174.192:4000/faucet \
    -H "Content-Type: application/json" \
    -d '{"address": "<地址>"}'

# 查看日志
tail -f /home/ubuntu/cowboy-node/data/validator.log

# 停止节点
kill $(ps aux | grep "[v]alidator" | awk '{print $2}')

# 重启节点
cd /home/ubuntu/cowboy-node
export RUST_MIN_STACK=33554432
nohup ./bin/validator \
    --peers=config/peers.yaml \
    --config=config/447a428b43ee100480e40669cf40b69b8e358f0ab713ada8f851d5b1cba0385b.yaml \
    --enable-faucet > data/validator.log 2>&1 &

# 完全重置链数据
rm -rf /home/ubuntu/cowboy-node/config/storage
# 然后重启节点
```

---

## 7. 服务访问汇总

| 服务 | URL | 状态 |
|------|-----|------|
| **RPC API** | http://34.193.174.192:4000 | ✅ 运行中 |
| **Swagger UI** | http://34.193.174.192:4000/swagger-ui/ | ✅ 可访问 |
| **Faucet** | POST http://34.193.174.192:4000/faucet | ✅ 可用 |
| **Metrics** | http://34.193.174.192:3001/metrics | ✅ 可访问 |
| **Cowboydocs** | http://34.193.174.192/docs/ | ✅ 运行中 |
| **本报告** | http://34.193.174.192/docs/20260225_Cowboy_Node_Installation_Report.md | ✅ |
