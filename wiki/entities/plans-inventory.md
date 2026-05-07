---
type: entity
tags: [plans, inventory, engineering, roadmap]
sources:
  - refs/plans/
last_updated: 2026-05-07
status: authoritative
---

# Plans 目录清单（refs/plans/）

`refs/plans/` 是工程实施计划的 raw 数据源。每个文件以 **语义化 kebab-case** 命名，内容是一份面向具体改动的行动方案 / 评估 / 路径图。

**定位**：
- 计划文件 **不是权威规范**；权威顺序仍是 **代码 > 修正案 > CIP > 白皮书**
- 计划记录"打算做什么 / 为什么 / 代价"，状态各异（已完成 / 进行中 / 提议 / 评估）

本清单按主题分组。

---

## 经济 / 费用 / Basefee（7）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [economics-alignment-plan](../../plans/economics-alignment-plan.md) | 经济系统对齐评估与修复计划 | 以 WP §17 + CIP-3 为最高权威，对代码做分级偏差评估 |
| [economics-completion-assessment](../../plans/economics-completion-assessment.md) | 经济系统真实完成度评估报告（2026-03-28） | CIP-3 / 双 gas / basefee / Lane 分区 / token / slashing 子系统完成度打分 |
| [economics-remaining-gaps](../../plans/economics-remaining-gaps.md) | 经济系统剩余缺口修复（econ-gaps） | `dispute_window_blocks` 常量化、Runner 质押 slash、1.5× stake 动态检查 |
| [runner-economics-and-delegation-cip13](../../plans/runner-economics-and-delegation-cip13.md) 🆕 | Runner Economics & Delegation — Design Guide | CIP-13 配套设计指南：Compute as Segmented Yield、89/10/1 分账、双类型 tip 辨析、双重通缩、tranche 模型、slash 级联 |
| [basefee-eip1559-systematic-fix](../../plans/basefee-eip1559-systematic-fix.md) | EIP-1559 Basefee 系统化修复方案 | 2026-04-11 bench 暴露 basefee 失效，四根因整合修复（目标 2000 TPS）|
| [basefee-constants-lower](../../plans/basefee-constants-lower.md) | 降低 basefee 常量修复高额 transfer 费用 | `MIN_BASEFEE` / `INITIAL_*_BASEFEE` 对齐 9 位小数精度，降 100× |
| [pvm-bytecode-gas-feasibility](../../plans/pvm-bytecode-gas-feasibility.md) | 评估实施 CIP-3 §2.2.1 逐字节码 gas 的可行性 | 细粒度 PVM 字节码计费的波及面与独立性评估（非实施计划）|

## 性能 / TPS / 出块（6）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [tps-improvement-roadmap](../../plans/tps-improvement-roadmap.md) | Cowboy TPS 提升方案 | 四 Tier 路线图，从参数调优到架构层变更 |
| [tps-avg-throughput-improvement](../../plans/tps-avg-throughput-improvement.md) | 提升 avg_confirmed / avg_submitted 指标 | 系统 lane 容量 + 0-TPS 块事件瓶颈分析与扩容 |
| [block-time-500ms-to-1000ms](../../plans/block-time-500ms-to-1000ms.md) | 出块时间 500ms → 1000ms | 应用层 `min_block_interval` + 共识层 `LEADER_TIMEOUT` 同步调整 |
| [block-time-change-scope](../../plans/block-time-change-scope.md) | 500ms → 1000ms 改动涉及面（已完成） | 记录 commit `f0bc514` 已落地的范围评估 |
| [transfer-lifecycle-profiling](../../plans/transfer-lifecycle-profiling.md) | Transfer 交易全生命周期埋点 | 从 RPC 提交到上链确认的阶段拆解与性能埋点方案 |
| [receipt-pruning-periodic](../../plans/receipt-pruning-periodic.md) | Direction B：周期性 receipt pruning | `SYNC_INTERVAL_BLOCKS` 批量清理历史 receipt，防 RSS 无上限增长 |

## 可靠性 / 事故修复（1）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [validator-10100-stall-fix](../../plans/validator-10100-stall-fix.md) | Validator 10100 停滞彻底修复方案 | 复盘 `871783e` 引入的 receipt prune 死锁，设计运行时无锁方案 |

## Bench / 可观测性（2）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [bench-basefee-tracking](../../plans/bench-basefee-tracking.md) | 为 `bench:all` 增加 basefee 变动追踪 | 洪水期 per-second 采样 + per-block 采样 + 报告汇总 |
| [bench-flood-errors-diagnostics](../../plans/bench-flood-errors-diagnostics.md) | 修复洪水测试错误 + Bench 报告诊断增强 | 191 笔错误根因归于 RPC 100 req/s 限速；errorBreakdown + block_samples |

## PVM（1）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [pvm-structured-errors](../../plans/pvm-structured-errors.md) | Structured PVM Error Messages | 统一 `{code, category, what, why, fix, docs_url, context}` 错误 schema |

## 钱包（2）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [wallet-ui-dark-theme](../../plans/wallet-ui-dark-theme.md) | Wallet UI 深色 AI 主题重设计 | Phantom 级别质感 + 赛博朋克 AI 风格的色板与组件重写 |
| [wallet-passkey-protection](../../plans/wallet-passkey-protection.md) | Passkey 保护层（路径 B） | WebAuthn PRF 扩展派生密钥 → AES-GCM 加密本地私钥 |

## 治理（1）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [governance-7phase-roadmap](../../plans/governance-7phase-roadmap.md) | 社区治理可行性与七阶段路径图（中英） | CIP-12 + OZ Governor / OP / Polkadot / Cosmos / Beanstalk 经验落地 |

## 文档 / 测试 / 待办（4）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [runner-test-coverage-plan](../../plans/runner-test-coverage-plan.md) | runner/ 测试完整性改进计划 | off-chain daemon 零覆盖的补救；弱断言 edge_cases 收尾 |
| [node-readme-update-plan](../../plans/node-readme-update-plan.md) | 更新 node/ READMEs（devnet 分支） | 对照代码修正 7 处过时常量与新特性文档 |
| [github-issues-batch-plan](../../plans/github-issues-batch-plan.md) | GitHub Issues 分类与批量实施计划 | 95 个未关 Issue 按模块聚合分批的优先级方案 |
| [2026-04-30_rust-fmt-cleanup-node-cbfs](../../plans/2026-04-30_rust-fmt-cleanup-node-cbfs.md) 🆕 | Rust 格式化清理（node + cbfs） | 跨 workspace 全量 `cargo fmt` 落地策略 + devnet CI 触发 |

## CIP / 跨子系统集成（3）

| 文件 | 标题 | 摘要 |
|---|---|---|
| [cowboy-tee-execution-design](../../plans/cowboy-tee-execution-design.md) | Cowboy TEE Execution 设计文档（CIP-23） | CIP-23 Draft 配套实施设计 §12 代码改造清单 + §13 4-phase 路线图 |
| [2026-04-22_cip-wp-gap-assessment-and-priorities](../../plans/2026-04-22_cip-wp-gap-assessment-and-priorities.md) 🆕 | CIP / Whitepaper Gap 评估与优先级 | 跨 CIP 与 WP v2 的差距盘点 + 优先级排序 |
| [2026-05-06_mpp_session_implementation](../../plans/2026-05-06_mpp_session_implementation.md) 🆕 | MPP Session 集成实施方案 | 把 `refs/runner/2026-04-28_MPP_Session_Research.md` 第 §5–§6 设计转化为可执行任务表（PoC 2-3 周）；详见 [[../concepts/mpp-session]] |

---

## 命名约定

- **kebab-case.md**，全英文
- **前缀即主题域**：`economics-*` / `basefee-*` / `tps-*` / `block-time-*` / `bench-*` / `wallet-*` / `pvm-*` / `runner-*` / `node-*` / `validator-*` / `governance-*` / `receipt-*` / `transfer-*` / `github-*`
- **名称表意**，方便在 grep / CLI / 引用中一眼识别
- **CIP 关联**：若计划紧跟某 CIP，用 `-cipNN` 后缀（如 `runner-economics-and-delegation-cip13.md`）
- **日期前缀**（2026-04 起新引入）：跨多主题或紧密关联当日提案的计划允许 `YYYY-MM-DD_<slug>.md`（如 `2026-05-06_mpp_session_implementation.md`）；slug 内允许 `_` 也允许 `-`，但单一计划内保持一致

## 使用指引

- **引用计划**：wiki 其他页可写 `refs/plans/<name>.md`，并标明计划是否已落地（若未知，默认视为提议/草案）
- **与 drift.md 关系**：计划中若涉及代码-文档不一致，应在 [drift.md](../drift.md) 看板有对应条目；仅存在计划文件 **不足以认定漂移已处理**
- **与 CIP 关系**：治理计划引用 CIP-12；fee 计划引用 CIP-3；计划是 CIP 的"工程接地"，不反向替代规范

## 相关

- [AGENTS.md](../AGENTS.md) — wiki 操作规约
- [index.md](../index.md) — wiki 总索引
- [drift.md](../drift.md) — 文档-代码漂移看板

## Sources

- `refs/plans/` 目录下 27 份 markdown 文件（2026-05-07 盘点；新增日期前缀的 CIP/Gap 类计划：`cowboy-tee-execution-design.md` / `2026-04-22_cip-wp-gap-assessment-and-priorities.md` / `2026-04-30_rust-fmt-cleanup-node-cbfs.md` / `2026-05-06_mpp_session_implementation.md`）
