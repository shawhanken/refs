# MCP 服务器使用指南

## 快速开始：使用 mcp-crypto-price

### 1. 安装 mcp-crypto-price

mcp-crypto-price 可以通过 `npx` 直接运行，无需本地安装：

```bash
# 测试是否可用
npx -y mcp-crypto-price
```

### 2. 配置 Runner

编辑 `runner/config/mcp-servers.yaml` 文件：

```yaml
mcp_servers:
  - name: "crypto-price"
    transport:
      type: "Stdio"
      command: "npx"
      args: ["-y", "mcp-crypto-price"]
    endpoint: ""
    auth:
      type: "None"
    timeout_seconds: 30
    enabled: true
```

### 3. 启动 Runner Node

```bash
cd runner
RUST_LOG="info" cargo run
```

### 4. 提交 MCP 任务

#### 查询比特币当前价格

```json
{
  "job_id": "crypto-btc-001",
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
  "deadline": 1000
}
```

#### 获取以太坊市场分析

```json
{
  "job_id": "crypto-eth-analysis",
  "job_type": {
    "Mcp": {
      "server": "crypto-price",
      "tool_name": "get-market-analysis",
      "arguments": {
        "symbol": "ETH"
      },
      "timeout_seconds": 30
    }
  },
  "reward": 150,
  "deadline": 1000
}
```

#### 查询比特币 7 天历史价格

```json
{
  "job_id": "crypto-btc-history",
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
  },
  "reward": 200,
  "deadline": 1000
}
```

## 可用的工具

mcp-crypto-price 提供以下工具：

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `get-crypto-price` | 获取当前价格和 24h 统计 | `symbol` (如 "BTC", "ETH") |
| `get-market-analysis` | 市场分析（交易所、VWAP 等） | `symbol` |
| `get-historical-analysis` | 历史价格分析（最多 30 天） | `symbol`, `days`, `interval` |

## 支持的加密货币符号

支持 CoinCap API 中的所有加密货币，常见符号：

- BTC (Bitcoin)
- ETH (Ethereum)
- BNB (Binance Coin)
- SOL (Solana)
- XRP (Ripple)
- ADA (Cardano)
- DOGE (Dogecoin)
- DOT (Polkadot)
- MATIC (Polygon)
- AVAX (Avalanche)

## 可选：配置 API Key

如果需要更高的速率限制，可以配置 CoinCap API Key：

1. 从 [pro.coincap.io/dashboard](https://pro.coincap.io/dashboard) 获取 API Key
2. 设置环境变量：

```bash
export COINCAP_API_KEY="your-api-key-here"
```

3. 更新配置文件（如果需要从环境变量读取）：

```yaml
mcp_servers:
  - name: "crypto-price"
    transport:
      type: "Stdio"
      command: "npx"
      args: ["-y", "mcp-crypto-price"]
    endpoint: ""
    env:
      COINCAP_API_KEY: "${COINCAP_API_KEY}"
    auth:
      type: "None"
    timeout_seconds: 30
    enabled: true
```

## 测试 MCP 服务器

### 使用 MCP Inspector 测试

```bash
# 安装 MCP Inspector
npm install -g @modelcontextprotocol/inspector

# 测试 mcp-crypto-price
npx @modelcontextprotocol/inspector npx -y mcp-crypto-price
```

### 手动测试工具调用

```bash
# 启动服务器（stdio 模式）
npx -y mcp-crypto-price

# 然后通过 stdin 发送 JSON-RPC 请求：
# {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
```

## 故障排除

### 问题：npx 找不到 mcp-crypto-price

**解决方案**：
- 确保已安装 Node.js 和 npm
- 检查网络连接（npx 需要下载包）
- 尝试手动安装：`npm install -g mcp-crypto-price`

### 问题：连接超时

**解决方案**：
- 增加 `timeout_seconds` 配置
- 检查网络连接
- 查看 Runner 日志了解详细错误

### 问题：工具调用失败

**解决方案**：
- 检查工具名称是否正确（区分大小写）
- 验证参数格式是否符合工具要求
- 查看 MCP 服务器日志

## 添加其他 MCP 服务器

参考 `runner/config/mcp-servers.yaml` 中的配置格式，可以添加其他 MCP 服务器：

```yaml
mcp_servers:
  - name: "weather"
    transport:
      type: "Stdio"
      command: "/path/to/venv/bin/python"
      args: ["/path/to/weather-mcp/server.py"]
    endpoint: ""
    auth:
      type: "None"
    timeout_seconds: 30
    enabled: true
```

## 相关文档

- [MCP 服务接入指南](../refs/runner/NODE_ACTOR_RUNNER_FLOW.md#mcp-服务接入指南)
- [mcp-crypto-price GitHub](https://github.com/truss44/mcp-crypto-price)
- [CoinCap API 文档](https://docs.coincap.io/)
