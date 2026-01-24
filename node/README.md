# Chain 集成相关文档

本目录包含 Chain 集成相关的所有文档。

## 目录结构

```
chain/
├── api/                    # Chain API 参考
├── integration/            # 集成指南
└── upgrade/                # 升级相关文档
```

## 文档分类

### api/ - Chain API 参考

- `pvm-host-implementation.md` - Chain 侧 PVM Host 实现参考
  - `CowboyHost` 实现
  - `PvmExecutionContext` 结构
  - Host API 映射

### integration/ - 集成指南

（待添加集成指南文档）

### upgrade/ - 升级相关文档

- `UPGRADE_ASSESSMENT.md` - PVM 子模块升级评估报告
  - 版本变化分析
  - API 兼容性检查
  - 必要升级项

- `UPGRADE_STATUS.md` - 升级状态报告
  - 已完成任务
  - 进行中任务
  - 待完成任务

- `UPGRADE_COMPLETE_SUMMARY.md` - 升级完成总结
  - 已完成工作
  - 当前状态
  - 后续计划

- `WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md` - 基于白皮书的后续工作方案
  - 白皮书要求分析
  - 实施优先级
  - 详细工作计划

- `BORROW_CHECKER_ISSUE.md` - 借用检查器问题分析
  - 问题描述
  - 根本原因
  - 解决方案

## 快速导航

### 集成 PVM 到 Chain
1. 阅读 `api/pvm-host-implementation.md` 了解实现方式
2. 参考 `upgrade/WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md` 了解架构要求

### 升级 PVM
1. 查看 `upgrade/UPGRADE_ASSESSMENT.md` 了解升级需求
2. 参考 `upgrade/WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md` 了解详细计划
3. 查看 `upgrade/UPGRADE_COMPLETE_SUMMARY.md` 了解当前状态
