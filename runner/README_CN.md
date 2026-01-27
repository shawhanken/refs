# Cowboy Runner System

Runner 系统是 Cowboy 链的核心创新，提供**可验证的链下计算市场**。

## 架构概述

Runner 系统由两部分组成：

1. **链上组件（System Actors）**：运行在链上，管理 Runner 注册、任务分发、结果验证等
2. **链下组件（Runner Executor）**：独立的 Runner 节点，执行 LLM、HTTP、MCP 等链下任务

## 项目结构

```
runner/
├── crates/
│   ├── runner-common/          # 共享类型和工具
│   ├── runner-registry/        # Runner 注册表（链上 System Actor）
│   ├── job-dispatcher/         # 任务分发器（链上 System Actor）
│   ├── result-verifier/        # 结果验证器（链上 System Actor）
│   ├── secrets-manager/        # 密钥管理器（链上 System Actor）
│   ├── tee-verifier/           # TEE 证明验证器（链上 System Actor）
│   ├── chain-client/           # 链客户端（Runner 与链通信）
│   ├── runner-node/            # Runner 节点核心
│   ├── runner-llm/            # LLM 执行器
│   ├── runner-http/           # HTTP 执行器
│   ├── runner-tee/            # TEE 运行时
│   └── runner-consensus/      # 共识客户端（N-of-M）
└── Cargo.toml
```

## 核心特性

1. **可验证性**: 支持多种信任模型（N-of-M、TEE、ZK V2）
2. **开放性**: 自由市场定价，Runner 自主报价
3. **可靠性**: 健康检查、故障转移、争议解决
4. **扩展性**: 支持多种任务类型（LLM、HTTP、MCP、自定义）
5. **安全性**: 密钥管理、访问控制、防攻击机制

## 设计原则

- **立足长远**: 设计考虑未来扩展，不短视应付
- **模块化**: 组件独立，易于测试和维护
- **安全性**: 多层安全机制
- **可观测性**: 完整的监控和日志

## 开发状态

当前处于实现阶段，按照设计文档分阶段实现。

详见 `refs/runner/RUNNER_SYSTEM_DESIGN.md`
