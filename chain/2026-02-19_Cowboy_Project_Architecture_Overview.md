# Cowboy 项目 — 全景技术架构图

> **日期:** 2026-02-12  
> **涵盖仓库:**  
> - `cowboyinc/node` — 分支: `devnet`  
> - `cowboyinc/pvm` — 分支: `main`  
> - `cowboyinc/runner` — 分支: `main`  

---

## 1. 全景架构图

```
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                              COWBOY — ACTOR-MODEL LAYER-1 BLOCKCHAIN                        ║
║                              带可验证链下计算 (Verifiable Off-Chain Compute)                    ║
╠══════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                              ║
║   外部用户/开发者                                                                              ║
║   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐    ║
║   │  CLI 客户端     │  │ 区块浏览器      │  │  DApp 前端     │  │  Python 智能合约开发者   │    ║
║   │  (clap)        │  │ (Explorer)     │  │  (Web)         │  │  (Actor 编写)           │    ║
║   └───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └───────────┬────────────┘    ║
║           │                   │                   │                       │                  ║
║           └───────────────────┴───────────────────┴───────────────────────┘                  ║
║                                         │                                                    ║
║                                         ▼                                                    ║
║ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ ║
║ ┃                          RPC API 层 (Axum REST + OpenAPI/Swagger)                       ┃ ║
║ ┃                                                                                         ┃ ║
║ ┃  交易提交        账户查询       Actor 查询      区块查询       健康检查      Runner/Job 查询 ┃ ║
║ ┃  POST /submit   GET /account  GET /actor     GET /block    GET /health  GET /runners   ┃ ║
║ ┃  GET /tx/{hash}  GET /tx/receipt GET /actor/code GET /height  /detailed   GET /runner    ┃ ║
║ ┃  GET /mempool/tx                                             /ready      GET /job       ┃ ║
║ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ ║
║                                         │                                                    ║
║ ┌───────────────────────────────────────┼────────────────────────────────────────────────┐   ║
║ │                            NODE 核心层 (cowboyinc/node 仓库)                            │   ║
║ │                            分支: devnet                              │   ║
║ │                                                                                        │   ║
║ │  ┌─────────────────────────────────────────────────────────────────────────────────┐   │   ║
║ │  │                     共识层 — Simplex BFT (commonware 框架)                       │   │   ║
║ │  │                                                                                 │   │   ║
║ │  │  • BLS12-381 threshold 签名    • 2/3+ 多数达成终局性                               │   │   ║
║ │  │  • 1 秒出块间隔                 • leader_timeout = 1s, notarization_timeout = 2s   │   │   ║
║ │  │                                                                                 │   │   ║
║ │  └─────────────────────────────────────────────────────────────────────────────────┘   │   ║
║ │                                       │                                                │   ║
║ │                                       ▼                                                │   ║
║ │  ┌─────────────────────────────────────────────────────────────────────────────────┐   │   ║
║ │  │                 交易执行引擎 — 双Gas计量 (Cycles + Cells)                         │   │   ║
║ │  │                                                                                 │   │   ║
║ │  │  Cycles = 计算 Gas          Cells = 存储 Gas                                     │   │   ║
║ │  │  用户为每个维度独立设定限额与价格                                                    │   │   ║
║ │  │                                                                                 │   │   ║
║ │  │  ┌────────────── 系统指令 ──────────────────┐  ┌───── Actor 指令 ──────────────┐  │   │   ║
║ │  │  │ • CreateAccount      [创建账户]          │  │ • DeployActor  [部署合约]      │  │   │   ║
║ │  │  │ • Transfer           [原生转账]          │  │   ├─ CREATE2 确定性地址生成    │  │   │   ║
║ │  │  │ • RunnerRegister     [Runner 注册]       │  │   └─ SHA256(creator+salt+code_hash)│  │   │   ║
║ │  │  │ • RunnerUpdateRateCard[更新费率卡]       │  │ • ExecuteActor [执行合约]      │  │   │   ║
║ │  │  │ • RunnerHeartbeat    [Runner 心跳]       │  │   └─ 通过 PVM 执行 Python     │  │   │   ║
║ │  │  │ • RunnerDeregister   [Runner 注销]       │  │                              │  │   │   ║
║ │  │  │ • JobSubmit          [提交离链任务]       │  │ • Custom       [扩展指令]      │  │   │   ║
║ │  │  │ • JobResultSubmit    [提交离链结果]       │  │   └─ module + action + data  │  │   │   ║
║ │  │  │ • JobCancel          [取消离链任务]       │  │                              │  │   │   ║
║ │  │  └─────────────────────────────────────────┘  └──────────────────────────────┘  │   │   ║
║ │  └─────────────────────────────────────────────────────────────────────────────────┘   │   ║
║ │                         │                              │                               │   ║
║ │            ┌────────────┘                              └────────────┐                  │   ║
║ │            ▼                                                        ▼                  │   ║
║ │  ┌──────────────────────┐                                ┌─────────────────────────┐  │   ║
║ │  │ 延迟交易机制          │                                │  Actor 模型 (智能合约)    │  │   ║
║ │  │ (Deferred TX)        │                                │                         │  │   ║
║ │  │                      │                                │  每个 Actor 拥有:         │  │   ║
║ │  │ • 跨区块异步执行       │                                │  • code (Python 源码)    │  │   ║
║ │  │ • 父交易 Gas 池共享    │                                │  • storage (KV 存储)     │  │   ║
║ │  │ • 系统触发独立 Gas     │                                │  • mailbox (消息队列)    │  │   ║
║ │  │ • 支持回调链           │                                │  • balance (余额)        │  │   ║
║ │  └──────────────────────┘                                │  • nonce (序列号)        │  │   ║
║ │                                                          └────────────┬────────────┘  │   ║
║ │                                                                       │                │   ║
║ │  ┌─────────────────────────────────────────────────────────────────────┘                │   ║
║ │  │                                                                                     │   ║
║ │  ▼                                                                                     │   ║
║ │  ┌──── 5 个系统 Actor (创世时初始化, 确定性种子地址) ──────────────────────────────────┐  │   ║
║ │  │                                                                                    │  │   ║
║ │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                 │  │   ║
║ │  │  │ Runner Registry  │  │ Job Dispatcher   │  │ Result Verifier  │                 │  │   ║
║ │  │  │ (Seed: 0x01)     │  │ (Seed: 0x02)     │  │ (Seed: 0x03)     │                 │  │   ║
║ │  │  │                  │  │                  │  │                  │                 │  │   ║
║ │  │  │ • 注册/注销       │  │ • 任务分发       │  │ • 结果收集        │                 │  │   ║
║ │  │  │ • 质押 ≥50K CBY  │  │ • 委员会选择     │  │ • 多模式结果验证    │                 │  │   ║
║ │  │  │ • 心跳健康检查    │  │ • 任务队列管理   │  │ • 回调触发        │                 │  │   ║
║ │  │  │ • 费率卡管理      │  │ • 确定性分配     │  │ • 争议处理        │                 │  │   ║
║ │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘                 │  │   ║
║ │  │  ┌──────────────────┐  ┌──────────────────┐                                      │  │   ║
║ │  │  │ Secrets Manager  │  │ TEE Verifier     │  ← 预留模块 (Placeholder)              │  │   ║
║ │  │  │ (Seed: 0x04)     │  │ (Seed: 0x05)     │                                      │  │   ║
║ │  │  └──────────────────┘  └──────────────────┘                                      │  │   ║
║ │  └────────────────────────────────────────────────────────────────────────────────────┘  │   ║
║ │                                                                                        │   ║
║ │  ┌────────────────────────────────┐   ┌────────────────────────────────────────────┐   │   ║
║ │  │ mempool (交易池)               │   │ blockchain storage (区块链存储)              │   │   ║
║ │  │ • Round-Robin 公平调度         │   │ • Journal (持久化) + Buffer Pool (热缓存)    │   │ ║  ║
║ │  │ • 最大 32,768 笔待处理         │   │ • Buffer Pool: 8KB 页 / 1MB 容量            │   │   ║
║ │  │ • 每账户最大 16 笔             │   │                                            │   │   ║
║ │  └────────────────────────────────┘   └────────────────────────────────────────────┘   │   ║
║ │                                                                                        │   ║
║ │  ┌────────── 附带子模块 ──────────────────────────────────────────────────────────────┐ │ ║
║ │  │ • indexer (区块索引)     • inspector (诊断工具)   • 多个 Demo 示例                   │ │ ║
║ │  │ • client (共识客户端)                                                              │ │   ║
║ │  └────────────────────────────────────────────────────────────────────────────────────┘ │ ║  ║
║ └────────────────────────────────────────────────────────────────────────────────────────┘   ║
║                                         │                                                    ║
║ ════════════════════════════════ HostApi 边界 ══════════════════════════════════════════════ ║
║                                         │                                                    ║
║ ┌───────────────────────────────────────┼────────────────────────────────────────────────┐   ║
║ │                         PVM 层 (cowboyinc/pvm 仓库, 分支: main)                         │   ║
║ │                     Python Virtual Machine — 确定性 Python 3 解释器                     │   ║
║ │                                                                                        │   ║
║ │  ┌────────────────── pvm-runtime (核心执行引擎) ───────────────────────────────────┐   │   ║
║ │  │                                                                                │   │   ║
║ │  │  ┌──────────────────┐  ┌───────────────────┐  ┌───────────────────────────┐   │   │   ║
║ │  │  │ 确定性子系统       │  │ 导入守卫系统       │  │ 断点续执 (Checkpoint)      │   │   │   ║
║ │  │  │                  │  │                   │  │                           │   │   │   ║
║ │  │  │ • hash_seed 固定 │  │ • 白名单 (70 模块) │  │ • Checkpoint 模式          │   │   ║
║ │  │  │ • SoftFloat 软浮 │  │ • 黑名单 (23 模块) │  │   (快照/序列化)           │   │   ║
║ │  │  │   点 (跨平台一致) │  │ • 别名映射         │  │ • 跨区块恢复执行          │   │   ║
║ │  │  │ • Gas 计量集成    │  │ • 阻止 I/O & 网络  │  │ • VM 状态序列化/反序列化  │   │   ║
║ │  │  │ • 环境隔离        │  │ • 前缀匹配过滤     │  │                           │   │   ║│   ║
║ │  │  └──────────────────┘  └───────────────────┘  └───────────────────────────┘   │   │   ║
║ │  │                                                                                │   │   ║
║ │  │  ┌────────────── Python SDK 桥接 (pvm_host 模块) ────────────────────────┐     │   │   ║
║ │  │  │  状态管理:  get_state / set_state / delete_state                      │     │   │   ║
║ │  │  │  Gas:      charge_gas / gas_left                                     │     │   │   ║
║ │  │  │  事件:     emit_event                                                │     │   │   ║
║ │  │  │  消息:     send_message / schedule_timer / cancel_timer               │     │   │   ║
║ │  │  │  上下文:   context (block_height, block_hash, tx_hash,              │     │   ║
║ │  │  │             sender, timestamp_ms, actor_addr, msg_id, nonce)       │     │   ║│   ║
║ │  │  │  随机数:   randomness (确定性 PRNG)                                   │     │   │   ║
║ │  │  │  离链任务: submit_job                                                 │     │   │   ║
║ │  │  │  延迟交易: create_deferred_tx                                         │     │   ║
║ │  │  │                                                                      │     │   ║
║ │  │  │  pvm_sdk 模块 (高级 Python SDK):                                      │     │   ║
║ │  │  │    pvm_sdk.runtime / pvm_sdk.actor / pvm_sdk.runner                  │     │   ║
║ │  │  │    pvm_sdk.continuation / pvm_sdk.verify / pvm_sdk.types             │     │   ║
║ │  │  │    pvm_sdk.pvm_time / pvm_sdk.pvm_random / pvm_sdk.pvm_sys           │     │   ║
║ │  │  └──────────────────────────────────────────────────────────────────┘     │   ║│   ║
║ │  └────────────────────────────────────────────────────────────────────────────────┘   │   ║
║ │                                                                                        │   ║
║ │  ┌─── pvm-host (HostApi Trait, 13 个方法) ──┐  ┌─── pvm-simulator (文件系统后端) ──┐   │   ║
║ │  │  纯 Trait 定义, 零依赖                    │  │  FsHost 本地测试实现              │   │   ║
║ │  │  Node 的 CowboyHost 实现此 Trait          │  │  execute_tx_fs 本地执行           │   │   ║
║ │  └──────────────────────────────────────────┘  └──────────────────────────────────┘   │   ║
║ │                                                                                        │   ║
║ │  ┌─── 底层 VM: 修改版 RustPython ──────────────────────────────────────────────────┐   │   ║
║ │  │  compiler (编译器) → bytecode (字节码) → VM 执行器                               │   │   ║
║ │  │  stdlib (标准库) / SoftFloat (软浮点引擎) / Checkpoint (序列化引擎)               │   │   ║
║ │  │  21 个 Rust crate, 192+ 核心 VM 文件                                             │   │   ║
║ │  └──────────────────────────────────────────────────────────────────────────────────┘   │   ║
║ └────────────────────────────────────────────────────────────────────────────────────────┘   ║
║                                                                                              ║
║ ═════════════════════════ 链上 ↔ 链下 交互边界 ════════════════════════════════════════════ ║
║         (Runner 通过 REST API 轮询任务, 通过签名 REST 提交结果)                                ║
║                                                                                              ║
║ ┌────────────────────────────────────────────────────────────────────────────────────────┐   ║
║ │                       Runner 层 (cowboyinc/runner 仓库, 分支: main)                     │   ║
║ │                    链下执行节点 — 质押运营商运行, 执行链下计算任务                         │   ║
║ │                                                                                        │   ║
║ │  ┌────────────────── runner-node (节点编排) ──────────────────────────────────────┐    │   ║
║ │  │                                                                                │    │   ║
║ │  │  main.rs                                                                       │    │   ║
║ │  │    1. 加载配置 (环境变量)                                                        │    │   ║
║ │  │    2. KeyManager 加载/生成 Ed25519 密钥对                                        │    │   ║
║ │  │    3. HttpChainClient 连接链节点                                                 │    │   ║
║ │  │    4. RunnerRegistrar 注册 (质押 ≥50K CBY)                                       │    │   ║
║ │  │    5. 构建 ExecutorRegistry                                                      │    │   ║
║ │  │    6. RunnerNode::run() → 启动 3 个异步任务                                       │    │   ║
║ │  │                                                                                │    │   ║
║ │  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────────┐    │    │   ║
║ │  │  │ 任务监听器        │ │ 健康心跳          │ │ 任务执行器                    │    │    │   ║
║ │  │  │ (Job Listener)   │ │ (Heartbeat)      │ │ (Job Executor)              │    │    │   ║
║ │  │  │                  │ │                  │ │                              │    │    │   ║
║ │  │  │ 轮询 /runner/    │ │ 每 10s 发送心跳  │ │ max_concurrent_jobs 计数器   │    │    │   ║
║ │  │  │ {addr}/jobs      │ │ 保持 Healthy     │ │ (默认 10 并发)               │    │    │   ║
║ │  │  │ 指数退避重试 (3x)│ │ 状态             │ │ 已提交去重 (HashSet)         │    │    │   ║
║ │  │  │                  │ │                  │ │ 自动匹配 executor 类型       │    │    │   ║
║ │  │  └──────────────────┘ └──────────────────┘ └──────────────┬───────────────┘    │    │   ║
║ │  └────────────────────────────────────────────────────────────┘                    │    │   ║
║ │                                                    │                               │    │   ║
║ │  ┌─────────────────────────────────────────────────┼──────────────────────────┐    │   ║
║ │  │                   ExecutorRegistry (执行器注册表)                            │    │   ║
║ │  │                                                                             │    │   ║
║ │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │    │   ║
║ │  │  │  LLM Executor    │  │  HTTP Executor   │  │  MCP Executor            │  │    │   ║
║ │  │  │  (runner-llm)    │  │  (runner-http)   │  │  (runner-mcp)            │  │    │   ║
║ │  │  │                  │  │                  │  │                          │  │    │   ║
║ │  │  │ • OpenAI 客户端  │  │ • GET/POST/PUT/  │  │ • JSON-RPC over stdio   │  │    │   ║
║ │  │  │   (自定义 Base)  │  │   DELETE/PATCH.. │  │ • MCP 2024-11-05 协议   │  │    │   ║
║ │  │  │ • Anthropic 客户端│  │ • 数据提取:      │  │ • 连接池管理             │  │    │   ║
║ │  │  │ • 本地模型 (预留) │  │   CSS / JSONPath │  │ • 工具缓存              │  │    │   ║
║ │  │  │ • 结构化输出      │  │   / Regex        │  │ • 参数 Schema 校验      │  │    │   ║
║ │  │  │   (JSON Schema)  │  │ • 源证明          │  │ • 超时控制              │  │    │   ║
║ │  │  │ • Token 用量追踪 │  │   (Attestation)  │  │                          │  │    │   ║
║ │  │  └────────┬─────────┘  └────────┬─────────┘  └────────────┬─────────────┘  │    │   ║
║ │  └───────────┼────────────────────┼──────────────────────────┼────────────────┘    │   ║
║ │              ▼                    ▼                          ▼                      │   ║
║ │       ┌───────────┐        ┌───────────┐             ┌──────────────┐              │   ║
║ │       │ OpenAI    │        │  外部 Web  │             │  MCP Server  │              │   ║
║ │       │ Anthropic │        │  API 服务  │             │  (stdio 进程) │              │   ║
║ │       │ (或兼容API)│        │           │             │              │              │   ║
║ │       └───────────┘        └───────────┘             └──────────────┘              │   ║
║ │                                                                                    │   ║
║ │  ┌──── 公共基础 ───────────────────────────────────────────────────────────────┐   │   ║
║ │  │  runner-common:     共享类型 / JobExecutor Trait / Ed25519 加密 / 错误层级  │   │   ║
║ │  │  chain-client:      ChainClient Trait / HTTP 实现 / 签名 REST 提交协议     │   │   ║
║ │  │  runner-consensus:  N-of-M 共识客户端 / Runner 间结果聚合与通讯            │   │   ║
║ │  │  runner-registry:   Runner 注册 / 费率卡 / 健康检查 / 声誉系统             │   │   ║
║ │  │  job-dispatcher:    任务接收 / Runner 选择 / 任务队列 / 超时处理           │   │   ║
║ │  │  result-verifier:   多模式验证 (N-of-M / 结构化匹配 / 语义相似度)          │   │   ║
║ │  │  runner-tee:        TEE 运行时 / attestation 证明生成                      │   │   ║
║ │  │  secrets-manager:   安全密钥管理 / 支持 TEE 集成                           │   │   ║
║ │  │  tee-verifier:      TEE attestation 验证                                   │   │   ║
║ │  └────────────────────────────────────────────────────────────────────────────┘   │   ║
║ └────────────────────────────────────────────────────────────────────────────────────┘   ║
║                                                                                          ║
║ ┌────────── 已实现的 Demo 应用 ─────────────────────────────────────────────────────┐    ║
║ │                                                                                    │    ║
║ │  ┌───────────────────┐  ┌───────────────────────────────────┐                     │    ║
║ │  │ llm_chat          │  │ deferred_counter_demo             │                     │    ║
║ │  │ LLM 聊天          │  │ 延迟交易链式计数                    │                     │    ║
║ │  │ (Runner+AI推理)   │  │                                   │                     │    ║
║ │  └───────────────────┘  └───────────────────────────────────┘                     │    ║
║ └────────────────────────────────────────────────────────────────────────────────────┘    ║
║                                                                                          ║
╠══════════════════════════════════════════════════════════════════════════════════════════╣
║                                开发成果统计                                               ║
║                                                                                          ║
║  NODE 仓库 (8 个 Rust crate):                                                            ║
║    chain / cli / client / indexer / inspector / runner / storage / types                   ║
║                                                                                          ║
║  PVM 仓库 (21 个 Rust crate):                                                            ║
║    pvm-host / pvm-runtime / pvm-simulator + 修改版 RustPython (compiler, VM, stdlib ...)  ║
║                                                                                          ║
║  RUNNER 仓库 (13 个 Rust crate):                                                         ║
║    runner-node / runner-common / chain-client / runner-llm / runner-http / runner-mcp    ║
║    runner-consensus / runner-registry / job-dispatcher / result-verifier                 ║
║    runner-tee / secrets-manager / tee-verifier                                           ║
║                                                                                          ║
║  合计: 42 个 Rust crate, 覆盖 共识 → 执行 → VM → 链下计算 全链路                          ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. 模块交互数据流 (简化版)

```
用户 DApp                        Runner 运营商
    │                                │
    │  提交交易                       │  注册 + 质押 ≥ 50K CBY
    ▼                                ▼
┌────────┐  共识    ┌───────────────┐  REST API  ┌──────────┐
│  CLI   │────────▶│     NODE      │◄──────────▶│  RUNNER  │
│        │         │               │            │          │
└────────┘         │  执行引擎      │            │ 执行框架  │
                   │    │           │            │    │     │
                   │    ▼           │            │    ▼     │
                   │ ┌──────┐      │            │ ┌─────┐ │
                   │ │ PVM  │      │  HostApi   │ │ LLM │ │
                   │ │Python│      │            │ │HTTP │ │
                   │ │ VM   │      │            │ │ MCP │ │
                   │ └──────┘      │            │ └─────┘ │
                   │               │            │    │    │
                   │ 5个系统Actor:  │            │    ▼    │
                   │  Registry     │  链上验证   │ OpenAI  │
                   │  Dispatcher   │◄───结果───│ Web API │
                   │  Verifier     │  回调触发   │MCP Svr  │
                   │  SecretsMgr   │            │         │
                   │  TEEVerifier  │            │         │
                   └───────────────┘            └──────────┘

流程: 用户TX → 共识 → 执行引擎 → Actor(PVM) → submit_job
     → Job Dispatcher 分配 → Runner 轮询领取 → 执行(LLM/HTTP/MCP)
     → 签名结果提交 → Result Verifier 多数投票验证
     → 触发回调 (Deferred TX) → Actor 接收结果
```

---

## 3. 三大仓库核心能力速览

### NODE 仓库 (`devnet` 分支) — 8 个 Rust Crate

| # | Crate | 核心能力 |
|---|-------|---------|
| 1 | **cowboy-chain** | Simplex BFT 共识引擎、双Gas执行引擎 (Cycles+Cells)、9 个 SystemInstruction + 2 个 ActorInstruction + Custom、Actor 模型智能合约、5 个系统 Actor、延迟交易机制、交易处理与区块生产 |
| 2 | **cowboy-cli** | 命令行客户端 (clap)、交易提交、账户/Actor/区块查询、密钥管理 |
| 3 | **cowboy-client** | 共识客户端、节点间通信、BLS12-381 门限签名、消息广播 |
| 4 | **cowboy-indexer** | 区块索引服务、历史交易检索、链上数据查询优化 |
| 5 | **cowboy-inspector** | 诊断工具、链状态检查、调试辅助 |
| 6 | **cowboy-runner** | Runner 链上交互模块、注册/心跳/任务管理的链端逻辑 |
| 7 | **cowboy-storage** | 区块链存储引擎、Journal 持久化 + Buffer Pool 热缓存、8KB 页 / 1MB 容量 |
| 8 | **cowboy-types** | 共享类型定义、交易/区块/Actor/Account 数据结构、RPC API (Axum REST + OpenAPI/Swagger) |

### PVM 仓库 (`main` 分支) — 21 个 Rust Crate

| # | Crate | 核心能力 |
|---|-------|---------|
| 1 | **rustpython** | 顶层 Workspace 入口、可执行 Python 解释器 |
| 2 | **pvm-host** | HostApi Trait 定义 (13 个方法)、纯接口零依赖、Node 的 CowboyHost 实现此 Trait |
| 3 | **pvm-runtime** | 核心执行引擎、确定性子系统 (hash_seed固定)、Gas 计量集成、环境隔离 |
| 4 | **pvm-simulator** | 文件系统后端 (FsHost)、本地测试/模拟器实现、execute_tx_fs 本地执行 |
| 5 | **rustpython-compiler** | Python 源码编译器、AST 解析、字节码编译管线 |
| 6 | **rustpython-compiler-core** | 编译器核心数据结构、编译管线基础 |
| 7 | **rustpython-compiler-source** | 编译器源码管理、源码位置追踪 (已标记 DEPRECATED) |
| 8 | **rustpython-codegen** | Python 字节码代码生成器、将 AST 编译为字节码 |
| 9 | **rustpython-literal** | Python 字面量解析、数字/字符串字面量处理 |
| 10 | **rustpython-vm** | VM 执行器核心、字节码解释执行、对象系统、帧管理 |
| 11 | **rustpython-pylib** | Python 标准库 (纯 Python 部分)、内置模块 |
| 12 | **rustpython-stdlib** | 标准库 (Rust 实现部分)、性能关键模块 |
| 13 | **rustpython-common** | 公共工具库、共享数据结构与辅助函数 |
| 14 | **rustpython-derive** | 过程宏 (derive macros)、PyClass/PyModule 等宏定义 |
| 15 | **rustpython-derive-impl** | Derive 宏具体实现、Rust 语言扩展与宏逻辑 |
| 16 | **rustpython-doc** | 文档生成工具、API 文档 |
| 17 | **rustpython-sre_engine** | 正则表达式引擎 (SRE)、Python re 模块后端 |
| 18 | **rustpython-jit** | JIT 编译支持 (预留)、性能优化 |
| 19 | **rustpython-wtf8** | WTF-8 编码实现、宽松 UTF-8 字符串处理 |
| 20 | **rustpython-venvlauncher** | 轻量级 venv 启动器、虚拟环境管理 |
| 21 | **rustpython_wasm** | WebAssembly 编译目标、浏览器端 Python 解释器 |

### RUNNER 仓库 (`main` 分支) — 13 个 Rust Crate

| # | Crate | 核心能力 |
|---|-------|---------|
| 1 | **runner-node** | 节点编排、3 个异步任务 (Job Listener / Heartbeat / Job Executor)、max_concurrent_jobs 计数器 (默认 10 并发) |
| 2 | **runner-common** | 共享类型、JobExecutor Trait、Ed25519 加密、错误层级定义 |
| 3 | **chain-client** | ChainClient Trait、HTTP 实现、签名 REST 提交协议 |
| 4 | **runner-llm** | LLM Executor、OpenAI/Anthropic 客户端、结构化输出 (JSON Schema)、Token 用量追踪 |
| 5 | **runner-http** | HTTP Executor、GET/POST/PUT/DELETE/PATCH 请求、数据提取 (CSS/JSONPath/Regex)、源证明 (Attestation) |
| 6 | **runner-mcp** | MCP Executor、JSON-RPC over stdio、MCP 2024-11-05 协议、连接池管理、工具缓存、参数 Schema 校验 |
| 7 | **runner-consensus** | N-of-M 共识客户端、Runner 间结果聚合与通讯 |
| 8 | **runner-registry** | Runner 注册/注销、费率卡管理、健康检查心跳、声誉系统 |
| 9 | **job-dispatcher** | 任务接收与分发、Runner 选择、任务队列管理、超时处理、确定性分配 |
| 10 | **result-verifier** | 多模式结果验证 (N-of-M / 结构化匹配 / 语义相似度)、回调触发、争议处理 |
| 11 | **runner-tee** | TEE 运行时、隔离执行环境、attestation 证明生成 |
| 12 | **secrets-manager** | 安全密钥管理、TEE 集成支持 |
| 13 | **tee-verifier** | TEE attestation 验证、证明校验 |

> **合计: 42 个 Rust Crate**, 覆盖 共识 → 执行 → VM → 链下计算 全链路

---

## 4. 关键技术决策

| # | 决策 | 说明 |
|---|------|------|
| 1 | **Actor 模型** (非 EVM) | 每个智能合约是独立 Actor, 拥有状态/邮箱/余额, 通过消息通信 |
| 2 | **双 Gas 计量** (Cycles + Cells) | 计算与存储成本分离, 用户为每个维度独立定价 |
| 3 | **PVM (Python VM)** | 基于 RustPython 修改, 确定性 Python 执行, 降低开发者门槛 |
| 4 | **Runner 链下计算** | 质押运营商执行 LLM/HTTP/MCP 任务, 链上多模式验证 (N-of-M/结构化匹配/语义相似度), Runner 间共识聚合 |
| 5 | **延迟交易** | 跨区块异步执行, 共享父交易 Gas 池, 支持回调链 |
| 6 | **CREATE2 地址** | `SHA256(creator + salt + code_hash)`, 部署前可预测地址 |
| 7 | **Simplex BFT** | BLS12-381 门限签名, 1秒出块, 2/3+ 终局性, leader_timeout=1s, notarization_timeout=2s |
| 8 | **SoftFloat** | 纯软件浮点运算, ARM/x86/WASM 比特级一致 |
| 9 | **REST + OpenAPI** | 标准化 API, 内置 Swagger 文档, 数值错误码 |
| 10 | **Runner 共识** | N-of-M 共识客户端, Runner 间数据同步与结果聚合, 可扩展验证模式 |
| 11 | **声誉系统** | Runner 声誉评分, 费率卡管理, 健康检查心跳, 自动化信任管理 |
| 12 | **TEE 支持 (预留)** | TEE 运行时隔离执行, attestation 证明生成与验证, 密钥安全管理 |

---


