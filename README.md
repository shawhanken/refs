# Cowboy 项目参考文档索引

本目录包含 Cowboy 项目的所有参考文档，按主题分类整理。

## 📋 文档分类原则

文档按以下类别进行分类，请确保文档放置在正确的目录中：

1. **chain/** - Cowboy 各系统整体集成相关文档
   - 系统间集成方案
   - 整体架构设计
   - 跨系统协作文档

2. **pvm/** - 虚拟机相关文档
   - PVM 核心功能
   - Python 解释器实现
   - PVM 内部机制

3. **runner/** - 链下执行系统相关文档
   - Runner 系统设计
   - 链下计算市场
   - Runner 实现计划

4. **common/** - 通用文档
   - 工具使用指南
   - 通用配置文档
   - 开发环境设置

5. **whitepaper/** - 白皮书（特殊且重要，不要有任何改动）
   - 核心技术白皮书
   - 架构设计文档

6. **node/** - 主链节点相关文档
   - 节点实现细节
   - 节点升级文档
   - 节点 API 文档

7. **task-plans/** - 工作计划
   - 任务清单
   - 项目路线图
   - 开发计划

## 📁 目录结构

```
refs/
├── whitepaper/          # 核心技术白皮书（特殊，不要改动）
├── pvm/                 # PVM (Python Virtual Machine) 相关文档（所有文件扁平化）
├── chain/              # Cowboy 各系统整体集成相关文档（所有文件扁平化）
├── node/               # 主链节点相关文档（所有文件扁平化）
├── runner/             # 链下执行系统相关文档
├── task-plans/         # 任务计划和路线图
└── common/             # 通用工具和指南
```

**注意**：所有分类目录中的文件都已扁平化到一级，不再使用子目录，便于人类阅读。

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

**文档数量**: 5 篇综合文档（已整合 23 个旧文档）

### 综合文档

1. **01-API参考与使用指南.md** ⭐⭐⭐⭐⭐
   - Host API 和 Runtime API 完整参考
   - 基本使用示例
   - Continuation 使用示例
   - Python Actor 示例

2. **02-功能设计与Continuation.md** ⭐⭐⭐⭐
   - Continuation 设计草案（Actor↔Actor, Actor↔Runner）
   - SDK API 说明
   - 编译期约束
   - FSM 编译形态
   - CBOR Schema
   - Guard 机制

3. **03-Checkpoint-Resume实现指南.md** ⭐⭐⭐⭐
   - 函数级 Checkpoint 支持
   - Block Stack 支持
   - Checkpoint File/Bytes API
   - 实现挑战和解决方案

4. **04-编码规范与最佳实践.md** ⭐⭐⭐⭐⭐
   - 支持的 Python 特性
   - 限制和禁止的操作
   - Checkpoint 使用规范
   - 确定性执行要求
   - 常见错误和陷阱
   - 最佳实践

5. **05-测试评估与升级.md** ⭐⭐⭐
   - 测试覆盖率报告（124 个测试）
   - 真实完成度评估（35-40%）
   - 升级安全防护方案
   - 可行性分析与路线图

**说明**：所有文档已整合为 5 篇综合文档，便于阅读和维护。旧文档已归档到 `_archive_/` 目录。

---

## ⛓️ Chain 相关文档（chain/）

### 集成方案
- `PVM_CHAIN_INTEGRATION_CN.md` - PVM 与主链低耦合对接方案

### 升级和工作计划
- **`WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md`** ⭐ - 基于核心白皮书的后续工作方案（当前工作重点）

**说明**：chain 目录包含 Cowboy 各系统整体集成相关的文档，包括集成方案和工作计划。

---

## 🏃 Runner 相关文档（runner/）

- `RUNNER_SYSTEM_DESIGN.md` - Runner 系统设计文档
- `Runner_Implementation_Plan_CN.md` - Runner 实现计划

**说明**：Runner 系统是链下执行系统，提供可验证的链下计算市场。

---

## 📋 任务计划（task-plans/）

- `Cowboy_PVM_Task_Plan.md` - Cowboy SDK 开发任务清单（英文）
- `Cowboy_PVM_Task_Plan_CN.md` - Cowboy SDK 开发任务清单（中文）

**说明**：包含模块划分、时间表、风险评估等项目管理文档。

---

## 🖥️ Node 相关文档（node/）

**文档数量**: 5 篇综合文档（已整合 15 个旧文档）

### 综合文档

1. **01-项目概览与路线图.md** ⭐⭐⭐⭐⭐
   - 项目整体规划和评估
   - 2026 年路线图
   - 真实完成度分析（8% vs 15%）
   - 技术挑战评估
   - 里程碑时间表

2. **02-实施与技术实现.md** ⭐⭐⭐⭐
   - 详细实施总结（阶段1-4）
   - 技术问题解决方案（借用检查器、Stack Overflow）
   - API 实现（CowboyHost、PvmExecutionContext）
   - 架构图
   - 技术债务说明

3. **03-测试与验证.md** ⭐⭐⭐⭐
   - 测试执行总结（14 个新测试）
   - 新增测试详情
   - PVM 子模块集成验证
   - Stack Overflow 修复验证
   - Checkpoint 模式演示
   - 测试覆盖率

4. **04-当前状态与行动项.md** ⭐⭐⭐⭐⭐
   - 当前项目状态
   - 立即行动项（今天）
   - 本周计划
   - 本月目标
   - Phase 2 目标清单
   - 下一步计划
   - 已知问题
   - 项目指标

**说明**：所有文档已整合为 5 篇综合文档，便于阅读和维护。旧文档已归档到 `_archive_/` 目录。

---

## 🛠️ 通用工具和指南（common/）

- `git-submodule-integration-guide.md` - Git 子模块集成指南
- `nginx-installation.md` - Nginx 安装指南
- `nginx-reverse-proxy-config.md` - Nginx 反向代理配置

---

## 📖 文档阅读建议

### 新手入门路径
1. **核心技术白皮书** (`whitepaper/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md`) - 理解 Cowboy 的核心理念
2. **PVM API 参考** (`pvm/01-API参考与使用指南.md`) - 了解 PVM API 和使用方法
3. **PVM 编码规范** (`pvm/04-编码规范与最佳实践.md`) - 了解如何编写 PVM Python 代码
4. **PVM 链集成方案** (`chain/PVM_CHAIN_INTEGRATION_CN.md`) - 了解整体架构

### 开发者路径
1. **项目概览** (`node/01-项目概览与路线图.md`) - 整体规划和评估
2. **当前行动项** (`node/04-当前状态与行动项.md`) - 当前工作重点和下一步计划
3. **实施与技术实现** (`node/02-实施与技术实现.md`) - 详细实施总结和技术细节
4. **Continuation 设计** (`pvm/02-功能设计与Continuation.md`) - Continuation 机制详解

### 功能实现路径
1. **Checkpoint 实现指南** (`pvm/03-Checkpoint-Resume实现指南.md`) - Checkpoint/Resume 完整实现指南
2. **功能设计** (`pvm/02-功能设计与Continuation.md`) - Continuation 和功能设计
3. **测试与验证** (`node/03-测试与验证.md`) - 测试报告和验证结果

### 项目管理路径
1. **任务计划** (`task-plans/Cowboy_PVM_Task_Plan_CN.md`) - 完整的任务清单和时间表
2. **工作方案** (`chain/WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md`) - 基于白皮书的后续工作方案
3. **项目概览** (`node/01-项目概览与路线图.md`) - 项目整体规划和路线图
4. **测试评估** (`pvm/05-测试评估与升级.md`) - 测试覆盖率和完成度评估

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

## 🔄 文档更新与维护

### 文档整合说明

为了便于阅读和维护，已将以下目录的文档整合为综合文档：

- **node/** - 15 个文档整合为 5 篇综合文档
- **pvm/** - 23 个文档整合为 5 篇综合文档

所有旧文档已归档到各目录的 `_archive_/` 子目录，仅供参考。

### 文档更新原则

1. **保持综合文档最新**：定期更新综合文档，确保信息准确
2. **归档旧版本**：重要变更时，将旧版本归档
3. **统一命名**：使用 `01-`, `02-` 等前缀便于排序
4. **扁平化结构**：所有文件扁平化到一级，不使用子目录

### 提交更新

如有文档缺失或分类错误，请提交 issue 或 PR。

**最后更新**: 2026-01-24  
**文档整合完成**: 
- ✅ 所有分类目录中的文件已扁平化到一级，不再使用子目录
- ✅ node 目录：15 个文档整合为 5 篇综合文档
- ✅ pvm 目录：23 个文档整合为 5 篇综合文档
- ✅ 旧文档已归档到各目录的 `_archive_/` 子目录
