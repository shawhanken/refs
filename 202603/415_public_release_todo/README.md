# Cowboy Devnet 上线准备工作区

**创建日期：** 2026-03-16  
**目标：** 2026-04-15 Devnet Release  

## 📁 文档结构

```
cowboy-devnet/
├── README.md                                  # 本文件：工作区导航
├── 00_master_implementation_plan.md            # 总实施计划（综合三套文档的完整方案）
├── 01_security_fixes.md                       # Almanax.ai 安全问题修复方案
├── 02_spec_alignment_fixes.md                 # 白皮书/CIP 规格差异修复方案
├── 03_meeting_action_items.md                 # 会议纪要中提出的需求与任务
├── 04_test_strategy.md                        # 统一测试策略（单元/集成/安全/CI）
├── 05_milestone_schedule.md                   # 里程碑日程安排（至 4.15 上线）
├── source/                                    # 原始参考文档副本
│   ├── meeting_20260316.txt                   # 会议纪要原文
│   ├── almanax_report_20260316.md             # Almanax.ai 安全扫描报告
│   └── gap_analysis_20260316.md               # 规格差距分析报告
└── tracking/                                  # 进度追踪
    └── progress_tracker.md                    # 各项任务完成状态追踪
```

## 📋 文档说明

| 文档 | 用途 | 受众 |
|------|------|------|
| `00_master_implementation_plan.md` | **核心文档**：综合所有来源的全面实施计划 | PM、Tech Lead、开发团队 |
| `01_security_fixes.md` | Almanax.ai 47 个安全问题的逐项修复方案 | 开发团队、安全审计 |
| `02_spec_alignment_fixes.md` | 20 项规格差距的技术方案（来自 gap analysis） | 开发团队、架构师 |
| `03_meeting_action_items.md` | 会议中 Tony/团队提出的明确需求 | PM、开发团队 |
| `04_test_strategy.md` | 测试分层策略：开发测试 + 上线测试 + CI | QA、开发团队 |
| `05_milestone_schedule.md` | 按周排列的里程碑计划 | PM、客户 |
| `tracking/progress_tracker.md` | 实时进度追踪清单 | PM、Tech Lead |

## 🔗 关联仓库

- **Node**: `cowboyinc/node` (Rust)
- **Runner**: `cowboyinc/runner` (Rust)
- **CIP 规格**: `refs/cips/CIP-1` 至 `CIP-20`
- **白皮书**: `refs/202602/20260216_cowboy_whitepaper.md`
