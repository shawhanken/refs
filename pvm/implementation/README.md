# 参考文档目录结构

本目录包含 Cowboy Node 项目的所有参考文档，按类别组织。

## 目录结构

```
refs/
├── README.md                          # 本文件 - 目录说明
├── whitepaper/                       # 核心技术白皮书
│   ├── Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md
│   ├── Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_EN.md
│   └── ...
├── pvm/                              # PVM (Python Virtual Machine) 相关文档
│   ├── api/                          # PVM API 参考文档
│   ├── features/                     # PVM 功能文档
│   ├── implementation/                # PVM 实现指南
│   ├── examples/                     # PVM 示例和演示
│   └── guidelines/                   # PVM 编码规范和最佳实践
├── chain/                            # Chain 集成相关文档
│   ├── api/                          # Chain API 参考
│   ├── integration/                  # Chain 集成指南
│   └── upgrade/                      # 升级相关文档
├── common/                           # 通用工具和配置文档
│   └── ...
└── task-plans/                       # 任务计划和路线图
    └── ...
```

## 文档分类说明

### 1. whitepaper/ - 核心技术白皮书

**优先级**: 🔴 最高 - 所有技术决策以此为准

包含 Cowboy 项目的核心技术白皮书，定义了：
- Actor 模型执行语义
- Continuation 机制
- 确定性执行要求
- Dual Gas 模型
- Runner 系统

**重要**: 所有技术实现必须严格遵循白皮书要求。

### 2. pvm/ - PVM 相关文档

#### pvm/api/ - API 参考文档
- `host-api-reference.md` - Host API 参考（HostApi trait、HostContext、HostError）
- `runtime-api-reference.md` - Runtime API 参考（execute_tx、ExecutionOptions、ContinuationOptions）

#### pvm/features/ - 功能文档
- `continuation-checkpoint.md` - Continuation 和 Checkpoint 功能说明
- `breakpoint-resume-demo.md` - 断点恢复演示文档

#### pvm/implementation/ - 实现指南
- `checkpoint-file-bytes-api.md` - Checkpoint File/Bytes API 设计与实现
- `function-checkpoint-support.md` - 函数级 Checkpoint 支持修复指南
- `block-stack-checkpoint-support.md` - Block Stack Checkpoint 支持实现指南
- `chain-integration.md` - PVM 与主链低耦合对接方案

#### pvm/examples/ - 示例和演示
- `runtime-chain-demo.md` - Runtime Chain 集成演示

#### pvm/guidelines/ - 编码规范
- `coding-guidelines.md` - PVM Python 代码规范与最佳实践
- `coding-guidelines-en.md` - PVM Coding Guidelines (English)

### 3. chain/ - Chain 集成相关文档

#### chain/api/ - Chain API 参考
- `pvm-host-implementation.md` - Chain 侧 PVM Host 实现参考

#### chain/integration/ - 集成指南
- （待添加）

#### chain/upgrade/ - 升级相关文档
- `UPGRADE_ASSESSMENT.md` - PVM 子模块升级评估报告
- `UPGRADE_STATUS.md` - 升级状态报告
- `UPGRADE_COMPLETE_SUMMARY.md` - 升级完成总结
- `WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md` - 基于白皮书的后续工作方案
- `BORROW_CHECKER_ISSUE.md` - 借用检查器问题分析

### 4. common/ - 通用工具和配置文档

包含通用工具、配置和最佳实践文档：
- `git-submodule-integration-guide.md` - Git 子模块集成指南
- `nginx-installation.md` - Nginx 安装指南
- `nginx-reverse-proxy-config.md` - Nginx 反向代理配置

### 5. task-plans/ - 任务计划和路线图

包含项目任务计划和开发路线图：
- `Cowboy_PVM_Task_Plan.md` - Cowboy SDK 开发任务计划
- `Cowboy_PVM_Task_Plan_CN.md` - Cowboy SDK 开发任务计划（中文）

## 文档命名规范

1. **中文文档**: 使用中文文件名，如 `PVM_Continuation_Design_CN.md`
2. **英文文档**: 使用英文文件名，如 `PVM_Coding_Guidelines_EN.md`
3. **版本标记**: 使用 `_v2`, `_v3` 等后缀标记版本
4. **类型标记**: 使用 `_CN`, `_EN` 等后缀标记语言

## 文档优先级

1. **🔴 最高优先级**: `whitepaper/` - 核心技术白皮书
2. **🟠 高优先级**: `pvm/api/`, `chain/api/` - API 参考文档
3. **🟡 中优先级**: `pvm/features/`, `chain/integration/` - 功能文档和集成指南
4. **🟢 低优先级**: `common/`, `task-plans/` - 通用文档和计划

## 快速导航

### 开始开发
1. 阅读 `whitepaper/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md`
2. 查看 `pvm/api/host-api-reference.md` 和 `pvm/api/runtime-api-reference.md`
3. 参考 `chain/api/pvm-host-implementation.md` 了解集成方式

### 实现 Continuation
1. 阅读 `pvm/features/continuation-checkpoint.md`
2. 参考 `pvm/implementation/checkpoint-file-bytes-api.md`
3. 查看 `pvm/examples/runtime-chain-demo.md`

### 升级 PVM
1. 查看 `chain/upgrade/UPGRADE_ASSESSMENT.md`
2. 参考 `chain/upgrade/WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md`
3. 查看 `chain/upgrade/UPGRADE_COMPLETE_SUMMARY.md` 了解当前状态

## 更新日志

- 2025-01-XX: 初始目录结构整理
