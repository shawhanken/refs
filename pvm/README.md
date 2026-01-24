# PVM 相关文档

本目录包含 Python Virtual Machine (PVM) 的所有相关文档。

## 目录结构

```
pvm/
├── api/                    # API 参考文档
├── features/               # 功能文档
├── implementation/         # 实现指南
├── examples/               # 示例和演示
└── guidelines/             # 编码规范和最佳实践
```

## 文档分类

### api/ - API 参考文档

- `host-api-reference.md` - Host API 参考
  - `HostApi` trait 定义
  - `HostContext` 结构
  - `HostError` 枚举

- `runtime-api-reference.md` - Runtime API 参考
  - `execute_tx` 函数
  - `ExecutionOptions` 配置
  - `ContinuationOptions` 配置

### features/ - 功能文档

- `continuation-checkpoint.md` - Continuation 和 Checkpoint 功能说明
- `breakpoint-resume-demo.md` - 断点恢复演示

### implementation/ - 实现指南

- `checkpoint-file-bytes-api.md` - Checkpoint File/Bytes API 设计与实现
- `function-checkpoint-support.md` - 函数级 Checkpoint 支持修复指南
- `block-stack-checkpoint-support.md` - Block Stack Checkpoint 支持实现指南
- `chain-integration.md` - PVM 与主链低耦合对接方案
- `continuation-design.md` - Continuation 设计草案

### examples/ - 示例和演示

- `runtime-chain-demo.md` - Runtime Chain 集成演示

### guidelines/ - 编码规范

- `coding-guidelines.md` - PVM Python 代码规范与最佳实践（中文）
- `coding-guidelines-en.md` - PVM Coding Guidelines (English)

## 快速导航

### 开始使用 PVM
1. 阅读 `api/host-api-reference.md` 了解 Host API
2. 阅读 `api/runtime-api-reference.md` 了解 Runtime API
3. 查看 `examples/runtime-chain-demo.md` 了解集成示例

### 实现 Checkpoint 功能
1. 阅读 `features/continuation-checkpoint.md` 了解功能
2. 参考 `implementation/checkpoint-file-bytes-api.md` 了解实现
3. 查看 `implementation/function-checkpoint-support.md` 了解函数级支持

### 编写 PVM 代码
1. 阅读 `guidelines/coding-guidelines.md` 了解编码规范
2. 参考 `features/continuation-checkpoint.md` 了解 Continuation 使用
