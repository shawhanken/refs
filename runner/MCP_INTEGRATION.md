# MCP Executor 集成指南

## 当前状态

MCP Executor 代码已经实现，但需要在 `runner/src/main.rs` 中集成。

## 集成步骤

### 方案一：硬编码配置（快速测试）

修改 `runner/src/main.rs`，添加以下代码：

```rust
//! Runner Node 主程序入口

use runner_node::{RunnerNode, RunnerConfig};
use chain_client::{ChainClient, HttpChainClient};
use runner_common::executor::{ExecutorRegistry, JobExecutor};
use runner_http::HttpExecutor;
use runner_llm::LlmExecutor;
use runner_mcp::{McpExecutor, McpServerConfig, McpTransportType, McpAuth};  // 新增
use std::sync::Arc;
use tracing::{info, error};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 初始化日志
    tracing_subscriber::fmt::init();
    
    info!("Starting Cowboy Runner Node");
    info!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    
    // 加载配置
    let mut config = RunnerConfig::default();
    
    // 从环境变量读取配置
    if let Ok(rpc_url) = std::env::var("CHAIN_RPC_URL") {
        config.chain_rpc_url = rpc_url;
        info!("Using custom RPC URL from environment");
    }
    
    info!("Chain RPC URL: {}", config.chain_rpc_url);
    info!("Runner Address: {:?}", config.address);
    info!("Max Concurrent Jobs: {}", config.max_concurrent_jobs);
    info!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    
    // 创建链客户端
    let chain_client: Arc<dyn ChainClient> = Arc::new(
        HttpChainClient::new(config.chain_rpc_url.clone())
    );
    
    // 创建执行器注册表
    let mut executors = ExecutorRegistry::new();
    
    // 注册 HTTP 执行器
    let http_executor = Box::new(HttpExecutor::new());
    let http_job_type = runner_common::types::JobType::Http {
        url: "".to_string(),
        method: runner_common::types::HttpMethod::GET,
        headers: std::collections::HashMap::new(),
        body: None,
        extraction: None,
        freshness: None,
    };
    executors.register_executor(&http_job_type, http_executor);
    
    // 注册 LLM 执行器（如果有 API key）
    let openai_key = std::env::var("OPENAI_API_KEY").ok();
    let anthropic_key = std::env::var("ANTHROPIC_API_KEY").ok();
    if openai_key.is_some() || anthropic_key.is_some() {
        let llm_executor = Box::new(LlmExecutor::new(openai_key, anthropic_key));
        let llm_job_type = runner_common::types::JobType::Llm {
            model_id: runner_common::types::ModelHash::zero(),
            prompt: "".to_string(),
            system_prompt: None,
            temperature: None,
            max_tokens: 0,
            response_model: None,
        };
        executors.register_executor(&llm_job_type, llm_executor);
    }
    
    // ========== 新增：注册 MCP 执行器 ==========
    // 配置 mcp-crypto-price 服务器
    let mcp_configs = vec![
        McpServerConfig {
            name: "crypto-price".to_string(),
            transport: McpTransportType::Stdio {
                command: "npx".to_string(),
                args: vec!["-y".to_string(), "mcp-crypto-price".to_string()],
            },
            endpoint: String::new(),
            auth: Some(McpAuth::None),
            timeout_seconds: 30,
            enabled: true,
        },
    ];
    
    let mcp_executor = Box::new(McpExecutor::new(mcp_configs));
    let mcp_job_type = runner_common::types::JobType::Mcp {
        server: "crypto-price".to_string(),
        tool_name: "get-crypto-price".to_string(),
        arguments: serde_json::json!({}),
        timeout_seconds: Some(30),
    };
    executors.register_executor(&mcp_job_type, mcp_executor);
    info!("MCP executor registered: crypto-price");
    // ==========================================
    
    let executors = Arc::new(executors);
    
    // 创建 Runner 节点
    let mut node = RunnerNode::new(
        config,
        chain_client,
        executors,
    );
    
    // 启动节点
    if let Err(e) = node.start().await {
        error!("Runner node error: {}", e);
        return Err(e.into());
    }
    
    Ok(())
}
```

### 方案二：从 YAML 文件加载配置（推荐）

如果需要从 YAML 文件加载配置，需要添加 `serde_yaml` 依赖：

1. 在 `runner/Cargo.toml` 中添加：

```toml
[dependencies]
# ... 其他依赖
serde_yaml = "0.9"
```

2. 创建配置加载函数：

```rust
use std::fs;
use std::path::Path;

fn load_mcp_configs<P: AsRef<Path>>(path: P) -> Result<Vec<McpServerConfig>, Box<dyn std::error::Error>> {
    let content = fs::read_to_string(path)?;
    let config: serde_yaml::Value = serde_yaml::from_str(&content)?;
    
    let mut configs = Vec::new();
    if let Some(servers) = config.get("mcp_servers").and_then(|v| v.as_sequence()) {
        for server in servers {
            // 解析配置...
            // 这里需要根据实际的 YAML 结构来解析
        }
    }
    
    Ok(configs)
}
```

## 测试 MCP 集成

### 1. 测试 npx 命令可用

```bash
# 确保 npx 可用
which npx
npx --version

# 测试 mcp-crypto-price
npx -y mcp-crypto-price
```

### 2. 启动 Runner Node

```bash
cd runner
RUST_LOG="info" cargo run
```

应该看到日志：
```
MCP executor registered: crypto-price
```

### 3. 提交测试任务

通过主链提交一个 MCP 任务（参考 `MCP_USAGE.md` 中的示例）。

## 注意事项

1. **npx 依赖**：确保系统已安装 Node.js 和 npm
2. **网络连接**：npx 需要下载包，确保网络畅通
3. **超时设置**：根据 MCP 服务器的响应时间调整 `timeout_seconds`
4. **环境变量**：如果使用 API Key，通过环境变量传递

## 故障排除

### 编译错误：找不到 McpExecutor

确保 `runner/Cargo.toml` 中包含：

```toml
[dependencies]
runner-mcp = { path = "crates/runner-mcp" }
```

### 运行时错误：npx 找不到

- 安装 Node.js：`curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs`
- 或使用系统包管理器安装

### MCP 服务器连接失败

- 检查日志中的详细错误信息
- 手动测试：`npx -y mcp-crypto-price`
- 检查网络连接
