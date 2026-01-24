# Cowboy 项目参考文档索引

本目录包含 Cowboy 项目的所有参考文档，按主题分类整理。

## 📁 目录结构

```
refs/
├── whitepaper/          # 核心技术白皮书
├── pvm/                 # PVM (Python Virtual Machine) 相关文档
│   ├── api/            # API 参考文档
│   ├── features/       # 功能设计文档
│   ├── guidelines/     # 编码规范
│   ├── implementation/ # 实现细节文档
│   └── examples/       # 示例和演示
├── chain/              # Cowboy Chain 相关文档
│   ├── api/           # Chain API 实现文档
│   └── upgrade/       # 升级和集成文档
├── task-plans/         # 任务计划和路线图
└── common/             # 通用工具和指南
```

---

## 📘 核心技术白皮书（whitepaper/）

### 主要白皮书
- **`Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md`** ⭐⭐⭐  
  **核心技术白皮书（中文版）** - 所有技术决策的最高依据
- `Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_EN.md`  
  核心技术白皮书（英文版）

### SDK 人体工程学建议
- `Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute(Sugguestion-SDK Ergonomics)_v2.md`  
  SDK 人体工程学建议 v2（中文）
- `Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute(Sugguestion-SDK Ergonomics)_v3_EN.md`  
  SDK 人体工程学建议 v3（英文）

**说明**：核心技术白皮书定义了 Cowboy 的架构、Actor 模型、Continuation 机制、确定性执行要求、Dual Gas 模型等核心概念。任何技术决策如有冲突，以此文档为准。

---

## 🐍 PVM 相关文档（pvm/）

### API 参考（pvm/api/）
- `host-api-reference.md` - Host API 接口定义（HostApi trait, HostContext, HostError）
- `runtime-api-reference.md` - Runtime API 接口（execute_tx, ExecutionOptions, ContinuationOptions）

### 功能设计（pvm/features/）
- `PVM_Continuation_Design_CN.md` - Continuation 机制设计草案（Actor ↔ Actor, Actor ↔ Runner）
- `continuation-checkpoint.md` - Continuation 和 Checkpoint 功能文档
- `breakpoint-resume-demo.md` - 断点恢复演示

### 编码规范（pvm/guidelines/）
- `PVM_Coding_Guidelines.md` - PVM Python 代码规范（中文）
- `PVM_Coding_Guidelines_EN.md` - PVM Python 代码规范（英文）

### 实现细节（pvm/implementation/）

#### Checkpoint/Resume 实现
- `Function_Checkpoint_Support.md` - 函数级 Checkpoint 支持（修复指南）
- `Block_Stack_Checkpoint_Support.md` - Block Stack 序列化支持（循环和异常处理）
- `Checkpoint_Resume_Fix_Guide.md` - Checkpoint/Resume 修复指南
- `PVM_Checkpoint_File_Bytes_API_CN.md` - Checkpoint 文件模式 + Bytes API 设计

#### Block Stack 实现
- `Block_Stack_Implementation_Challenges.md` - Block Stack 实现挑战（中文）
- `Block_Stack_Implementation_Challenges_EN.md` - Block Stack 实现挑战（英文）

#### 链集成
- `PVM_CHAIN_INTEGRATION_CN.md` - PVM 与主链低耦合对接方案

#### 确定性和可行性
- `PVM_Determinism_Demo_Report_CN.md` - 确定性演示报告
- `PVM_Determinism_Implementation_Plan_CN.md` - 确定性实现计划
- `PVM_Feasibility_and_Roadmap_CN.md` - 可行性分析和路线图

#### Runner 实现
- `Runner_Implementation_Plan_CN.md` - Runner 实现计划

### 示例（pvm/examples/）
- `runtime-chain-demo.md` - PVM Runtime 链上演示

---

## ⛓️ Chain 相关文档（chain/）

### API 实现（chain/api/）
- `pvm-host-implementation.md` - Cowboy Chain 的 HostApi 实现文档

### 升级文档（chain/upgrade/）
- **`WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md`** ⭐ - 基于核心白皮书的后续工作方案（当前工作重点）
- `UPGRADE_ASSESSMENT.md` - PVM 子模块升级评估报告
- `UPGRADE_COMPLETE_SUMMARY.md` - PVM 升级完成总结
- `UPGRADE_STATUS.md` - 升级状态跟踪
- `BORROW_CHECKER_ISSUE.md` - 借用检查器问题分析和解决方案

---

## 📋 任务计划（task-plans/）

- `Cowboy_PVM_Task_Plan.md` - Cowboy SDK 开发任务清单（英文）
- `Cowboy_PVM_Task_Plan_CN.md` - Cowboy SDK 开发任务清单（中文）

**说明**：包含模块划分、时间表、风险评估等项目管理文档。

---

## 🛠️ 通用工具和指南（common/）

- `git-submodule-integration-guide.md` - Git 子模块集成指南
- `nginx-installation.md` - Nginx 安装指南
- `nginx-reverse-proxy-config.md` - Nginx 反向代理配置

---

## 📖 文档阅读建议

### 新手入门路径
1. **核心技术白皮书** (`whitepaper/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md`) - 理解 Cowboy 的核心理念
2. **PVM 编码规范** (`pvm/guidelines/PVM_Coding_Guidelines.md`) - 了解如何编写 PVM Python 代码
3. **Host API 参考** (`pvm/api/host-api-reference.md`) - 了解 PVM 与 Chain 的接口
4. **PVM 链集成方案** (`pvm/implementation/PVM_CHAIN_INTEGRATION_CN.md`) - 了解整体架构

### 开发者路径
1. **工作方案** (`chain/upgrade/WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md`) - 当前工作重点和后续计划
2. **Host API 实现** (`chain/api/pvm-host-implementation.md`) - CowboyHost 实现细节
3. **Runtime API 参考** (`pvm/api/runtime-api-reference.md`) - PVM Runtime 使用方法
4. **Continuation 设计** (`pvm/features/PVM_Continuation_Design_CN.md`) - Continuation 机制详解

### 功能实现路径
1. **Checkpoint 支持** (`pvm/implementation/Function_Checkpoint_Support.md`) - 函数级 Checkpoint 实现
2. **Block Stack 支持** (`pvm/implementation/Block_Stack_Checkpoint_Support.md`) - 复杂控制流支持
3. **Checkpoint API** (`pvm/implementation/PVM_Checkpoint_File_Bytes_API_CN.md`) - Checkpoint API 设计

### 项目管理路径
1. **任务计划** (`task-plans/Cowboy_PVM_Task_Plan_CN.md`) - 完整的任务清单和时间表
2. **升级评估** (`chain/upgrade/UPGRADE_ASSESSMENT.md`) - 升级需求和风险评估

---

## 🏷️ 文档标签说明

- ⭐⭐⭐ - 最高优先级，所有决策的依据
- ⭐ - 当前工作重点
- 🇨🇳 - 中文文档
- 🇬🇧 - 英文文档
- 📝 - 设计文档
- 🔧 - 实现指南
- 📊 - 规划文档

---

## 📝 文档命名约定

- `*_CN.md` - 中文文档
- `*_EN.md` - 英文文档
- `*_v2.md`, `*_v3.md` - 版本化文档
- `README.md` - 各子目录的索引文件

---

## 🔄 文档更新

本文档索引由系统自动生成和维护。如有文档缺失或分类错误，请提交 issue 或 PR。

**最后更新**: 2025-01-18
