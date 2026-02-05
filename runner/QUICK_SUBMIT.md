# 快速提交 MCP 任务指南

## 方法一：使用 CLI（最简单）

### 1. 编译 CLI（如果还没有）

```bash
cd node/cli
cargo build --release
```

### 2. 创建任务 JSON 文件

```bash
cd runner/scripts
./create_job_json.sh BTC get-crypto-price job_btc.json
```

或手动创建 `job_btc.json`:

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
    "runners": 1,
    "mode": "HappyCase"
  }
}
```

### 3. 创建私钥文件

```bash
echo "0x你的私钥" > private_key.txt
```

或使用环境变量：

```bash
export COWBOY_PRIVATE_KEY="0x你的私钥"
```

### 4. 提交任务

```bash
# 使用私钥文件
cowboy job submit \
  --job-spec job_btc.json \
  --private-key private_key.txt \
  --rpc-url http://localhost:4000

# 或使用环境变量
cowboy job submit \
  --job-spec job_btc.json \
  --rpc-url http://localhost:4000
```

## 方法二：使用便捷脚本

```bash
cd runner/scripts
./submit_crypto_job.sh http://localhost:4000 0x你的私钥 BTC
```

脚本会自动：
1. 创建任务 JSON
2. 查找 cowboy CLI
3. 提交任务

## 查询任务状态

```bash
# 获取任务 ID（从提交响应中）
JOB_ID="0x..."

# 查询任务状态
cowboy job status --job-id $JOB_ID --rpc-url http://localhost:4000

# 查询任务结果
cowboy job results --job-id $JOB_ID --rpc-url http://localhost:4000

# 查询验证结果
cowboy job verified --job-id $JOB_ID --rpc-url http://localhost:4000
```

## 示例：查询不同加密货币

### 查询以太坊价格

```bash
./create_job_json.sh ETH get-crypto-price job_eth.json
cowboy job submit --job-spec job_eth.json --private-key private_key.txt --rpc-url http://localhost:4000
```

### 获取市场分析

```bash
./create_job_json.sh BTC get-market-analysis job_btc_analysis.json
cowboy job submit --job-spec job_btc_analysis.json --private-key private_key.txt --rpc-url http://localhost:4000
```

### 查询历史价格

```bash
./create_job_json.sh BTC get-historical-analysis job_btc_history.json
cowboy job submit --job-spec job_btc_history.json --private-key private_key.txt --rpc-url http://localhost:4000
```

## 故障排除

### CLI 未找到

```bash
# 编译 CLI
cd node/cli
cargo build --release

# 添加到 PATH 或使用完整路径
export PATH="$PATH:$(pwd)/target/release"
```

### 私钥格式错误

确保私钥是 32 字节的十六进制字符串（64 个字符），可以带或不带 `0x` 前缀。

### 账户 nonce 错误

如果遇到 nonce 错误，CLI 会自动查询当前 nonce。如果仍有问题，可以手动指定：

```bash
cowboy job submit \
  --job-spec job_btc.json \
  --private-key private_key.txt \
  --rpc-url http://localhost:4000 \
  --nonce 1
```

## 相关文档

- `runner/SUBMIT_JOB_GUIDE.md` - 完整提交指南
- `runner/QUICK_START_MCP.md` - 快速开始
- `runner/MCP_USAGE.md` - 详细使用说明
