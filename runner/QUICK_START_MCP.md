# 快速开始：使用 mcp-crypto-price 查询加密货币价格

## 前提条件

1. ✅ Runner Node 已启动（已集成 MCP executor）
2. ✅ 主链节点正在运行（默认端口 4000）
3. ✅ 已安装 Node.js 和 npm（用于运行 mcp-crypto-price）

## 方法一：使用 curl 直接提交任务（推荐用于测试）

### 1. 查询比特币当前价格

```bash
# 设置主链 RPC URL
RPC_URL="http://localhost:4000"

# 构建任务 JSON
JOB_JSON='{
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
}'

# 提交任务（需要通过 Transaction，这里只是示例格式）
# 实际提交需要使用 CLI 工具或创建 Transaction
```

### 2. 查询以太坊价格

```json
{
  "job_type": {
    "Mcp": {
      "server": "crypto-price",
      "tool_name": "get-crypto-price",
      "arguments": {
        "symbol": "ETH"
      },
      "timeout_seconds": 30
    }
  }
}
```

### 3. 获取市场分析

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

### 4. 查询历史价格（7天）

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

## 方法二：使用 CLI 工具提交任务

### 安装 CLI（如果还没有）

```bash
cd node/cli
cargo build --release
```

### 提交任务

```bash
# 设置私钥（用于签名交易）
export PRIVATE_KEY="0x你的私钥"

# 提交任务（需要实现 job submit 命令）
# ./target/release/cowboy-cli job submit \
#   --rpc-url http://localhost:4000 \
#   --job-spec job.json
```

## 方法三：使用 Python 脚本提交

创建 `submit_crypto_job.py`:

```python
#!/usr/bin/env python3
import requests
import json
import sys

RPC_URL = "http://localhost:4000"

def submit_job(symbol, tool_name="get-crypto-price", **kwargs):
    """提交加密货币查询任务"""
    
    job_spec = {
        "job_id": [0] * 32,  # 自动生成
        "job_type": {
            "Mcp": {
                "server": "crypto-price",
                "tool_name": tool_name,
                "arguments": {
                    "symbol": symbol,
                    **kwargs
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
    
    # 注意：实际提交需要通过 Transaction
    # 这里只是展示任务格式
    print("任务规格:")
    print(json.dumps(job_spec, indent=2))
    
    # TODO: 创建 Transaction 并提交到 /submit 端点
    return job_spec

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python submit_crypto_job.py <SYMBOL> [tool_name]")
        print("示例: python submit_crypto_job.py BTC")
        print("示例: python submit_crypto_job.py ETH get-market-analysis")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    tool_name = sys.argv[2] if len(sys.argv) > 2 else "get-crypto-price"
    
    submit_job(symbol, tool_name)
```

## 可用的工具和参数

### 1. get-crypto-price（获取当前价格）

**参数：**
- `symbol` (string, 必需): 加密货币符号，如 "BTC", "ETH"

**示例：**
```json
{
  "symbol": "BTC"
}
```

**返回：**
- 当前价格（USD）
- 24小时价格变化
- 交易量
- 市值
- 排名

### 2. get-market-analysis（市场分析）

**参数：**
- `symbol` (string, 必需): 加密货币符号

**示例：**
```json
{
  "symbol": "BTC"
}
```

**返回：**
- VWAP（成交量加权平均价）
- 前5大交易所
- 价格变化范围
- 交易量分布

### 3. get-historical-analysis（历史价格）

**参数：**
- `symbol` (string, 必需): 加密货币符号
- `days` (number, 可选): 天数（1-30，默认7）
- `interval` (string, 可选): 时间间隔（"5min", "15min", "1h", "4h", "1d"，默认"1h"）

**示例：**
```json
{
  "symbol": "BTC",
  "days": 7,
  "interval": "1h"
}
```

**返回：**
- 历史价格数据
- 最高/最低价
- 波动率指标
- 价格趋势分析

## 支持的加密货币符号

支持 CoinCap API 中的所有加密货币，常见符号：

- **BTC** - Bitcoin
- **ETH** - Ethereum  
- **BNB** - Binance Coin
- **SOL** - Solana
- **XRP** - Ripple
- **ADA** - Cardano
- **DOGE** - Dogecoin
- **DOT** - Polkadot
- **MATIC** - Polygon
- **AVAX** - Avalanche

## 查询任务状态

提交任务后，可以通过以下方式查询状态：

```bash
# 查询任务信息
curl http://localhost:4000/job/{job_id}

# 查询任务状态
curl http://localhost:4000/job/{job_id}/status

# 查询任务结果
curl http://localhost:4000/job/{job_id}/results

# 查询验证结果
curl http://localhost:4000/job/{job_id}/verified
```

## 查看 Runner Node 日志

Runner Node 执行任务时会在日志中显示：

```
INFO Executing MCP task: server=crypto-price, tool=get-crypto-price
INFO MCP tool call completed: server=crypto-price, tool=get-crypto-price, duration=234ms
```

## 故障排除

### 问题：Runner Node 没有接收到任务

**检查：**
1. Runner Node 是否已启动并注册到主链
2. Runner Node 是否正在轮询任务（查看日志）
3. 主链是否有活跃的 Runner

### 问题：MCP 服务器连接失败

**检查：**
1. Node.js 和 npm 是否已安装：`which npx`
2. 网络连接是否正常（npx 需要下载包）
3. 手动测试：`npx -y mcp-crypto-price`

### 问题：工具调用超时

**解决方案：**
- 增加 `timeout_seconds` 参数
- 检查网络连接
- 查看 Runner Node 日志了解详细错误

## 下一步

- 查看 `runner/MCP_USAGE.md` 了解详细使用说明
- 查看 `refs/runner/NODE_ACTOR_RUNNER_FLOW.md` 了解系统架构
- 添加更多 MCP 服务器（参考配置文件示例）
