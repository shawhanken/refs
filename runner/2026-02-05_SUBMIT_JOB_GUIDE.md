# 提交 MCP 任务完整指南

## 快速开始

### 方法一：使用 Shell 脚本（最简单）

```bash
cd runner
./scripts/submit_crypto_job.sh http://localhost:4000 0x你的私钥 BTC
```

### 方法二：使用 Python 脚本

```bash
cd runner
python3 scripts/submit_crypto_job.py http://localhost:4000 0x你的私钥 BTC
```

### 方法三：使用 Rust CLI（需要编译）

```bash
# 编译 CLI
cd node/cli
cargo build --release

# 提交任务（需要实现 job submit 命令）
./target/release/cowboy-cli job submit \
  --rpc-url http://localhost:4000 \
  --private-key 0x... \
  --job-spec job.json
```

## 任务格式

### 查询比特币当前价格

```json
{
  "job_id": [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
  "job_type": {
    "Mcp": {
      "server": "crypto-price",
      "tool_name": "get-crypto-price",
      "arguments": {
        "symbol": "BTC"
      },
      "timeout_seconds": 30
    }
  },
  "reward": 100,
  "deadline": 1000,
  "verification": {
    "mode": "none"
  }
}
```

> **修正案（2026-04-15 H-2/H-3）**：原文 `"mode": "HappyCase"` 在当前代码中不存在。合法值：`none` / `economicbond` / `majorityvote` / `structuredmatch` / `deterministic` / `semanticsimilarity`。多 Runner 验证模式还需 `runners` + `threshold` 字段。详见 [`refs/analysis/2026-04-15_documentation_amendments.md §六·补³`](../analysis/2026-04-15_documentation_amendments.md)。

### 获取市场分析

```json
{
  "job_type": {
    "Mcp": {
      "server": "crypto-price",
      "tool_name": "get-market-analysis",
      "arguments": {
        "symbol": "BTC"
      },
      "timeout_seconds": 30
    }
  }
}
```

### 查询历史价格

```json
{
  "job_type": {
    "Mcp": {
      "server": "crypto-price",
      "tool_name": "get-historical-analysis",
      "arguments": {
        "symbol": "BTC",
        "days": 7,
        "interval": "1h"
      },
      "timeout_seconds": 60
    }
  }
}
```

## 完整流程

### 1. 准备环境

```bash
# 确保主链节点运行
# 确保 Runner Node 运行
cd runner && RUST_LOG=info cargo run
```

### 2. 创建任务 JSON 文件

创建 `job_btc.json`:

```json
{
  "job_id": [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
  "job_type": {
    "Mcp": {
      "server": "crypto-price",
      "tool_name": "get-crypto-price",
      "arguments": {
        "symbol": "BTC"
      },
      "timeout_seconds": 30
    }
  },
  "reward": 100,
  "deadline": 1000,
  "verification": {
    "mode": "none"
  }
}
```

> **修正案（2026-04-15 H-2）**：原文 `HappyCase` 已更正；见上方第一处说明。

### 3. 创建 Transaction 并提交

任务需要通过 `SystemInstruction::JobSubmit` Transaction 提交。

**Transaction 结构：**
```rust
Transaction {
    public: PublicKey,  // 提交者公钥
    nonce: u64,        // 账户 nonce
    instruction: Instruction::System(SystemInstruction::JobSubmit {
        job_spec: Vec<u8>,  // JobSpec JSON 序列化后的字节
    }),
    signature: Signature,
    cycles_limit: u64,
    cells_limit: u64,
    max_fee_per_cycle: u64,
    max_fee_per_cell: u64,
}
```

### 4. 提交到主链

```bash
# 使用 curl 提交 Transaction（需要先序列化）
curl -X POST http://localhost:4000/submit \
  -H "Content-Type: application/octet-stream" \
  --data-binary @transaction.bin
```

### 5. 查询任务状态

```bash
# 查询任务信息
JOB_ID="0x..."  # 从提交响应中获取
curl http://localhost:4000/job/$JOB_ID

# 查询任务状态
curl http://localhost:4000/job/$JOB_ID/status

# 查询任务结果
curl http://localhost:4000/job/$JOB_ID/results

# 查询验证结果
curl http://localhost:4000/job/$JOB_ID/verified
```

## 使用 Rust 客户端提交（推荐）

参考 `runner/examples/submit_mcp_job.rs` 中的完整示例。

编译和运行：

```bash
cd runner
cargo run --example submit_mcp_job -- \
  http://localhost:4000 \
  0x你的私钥 \
  BTC \
  get-crypto-price
```

## 常见问题

### Q: 如何获取私钥？

A: 私钥是 32 字节的十六进制字符串（64 个字符），可以：
- 从钱包导出
- 使用测试私钥（仅用于开发）
- 生成新密钥对

### Q: 任务提交后多久执行？

A: Runner Node 会定期轮询任务（默认每秒），提交后通常在几秒内开始执行。

### Q: 如何查看 Runner Node 日志？

A: Runner Node 启动时会显示日志，执行任务时会输出：
```
INFO Executing MCP task: server=crypto-price, tool=get-crypto-price
```

### Q: 任务执行失败怎么办？

A: 检查：
1. Runner Node 是否正常运行
2. mcp-crypto-price 是否可用（`npx -y mcp-crypto-price`）
3. 网络连接是否正常
4. 查看 Runner Node 日志了解详细错误

## 相关文档

- `runner/QUICK_START_MCP.md` - 快速开始指南
- `runner/MCP_USAGE.md` - 详细使用说明
- `refs/runner/NODE_ACTOR_RUNNER_FLOW.md` - 系统架构文档
