# Cowboy 项目参考文档索引

本目录包含 Cowboy 项目的所有参考文档，按**主题**分类整理。跨主题的综合分析、报告、会议纪要集中在 `analysis/`，由 LLM 维护的综合 wiki 位于 `wiki/`。

**最后更新**: 2026-05-11（r2 alignment + 新 CIP-8 / 11 / 17 / 18 / 19 / 25 入库）

---

## 🧭 从哪里开始

- **快速定位概念 / 参数 / 冲突** → **[`wiki/`](wiki/index.md)**（LLM 综合层，权威参数与跨文档综合）
- **读规范原文** → `cips/`、`whitepaper/`
- **读历史上下文** → `node/`、`pvm/`、`runner/`、`chain/`、`economics/` 等主题目录
- **追漂移 / 修正案** → [`analysis/2026-04-15_documentation_amendments.md`](analysis/2026-04-15_documentation_amendments.md) 或 [`wiki/drift.md`](wiki/drift.md)

---

## 📁 目录结构

```
refs/
├── wiki/         LLM 维护的综合知识库（概念/实体/参数/漂移/日志）
├── whitepaper/   核心技术白皮书（受保护，不改动）+ WP v2 deltas
├── cips/         CIP 规范（living specs，含 v2 alignment 系列）
├── plans/        🆕 工程实施计划 / 评估 / 路径图（2026-04-17 入库）
├── chain/        跨系统集成与整体架构
├── node/         主链节点实现
├── pvm/          Python 虚拟机
├── runner/       链下执行系统
├── economics/    费用模型 / Basefee / Gas / Tokenomics
├── devex/        开发者体验与客户反馈
├── analysis/     跨主题分析、会议纪要、问题修复计划、修正案
├── common/       通用基础设施（nginx、CI/CD、git 子模块）
├── dev_support/  开发工具（MCP server、模板）
├── _archive_/    被替代或过时的历史文档
└── LLM_Wiki.md   LLM Wiki 模式说明（wiki/ 的设计蓝本）
```

---

## 📝 文件命名约定

- **`YYYY-MM-DD_`** 日期前缀：文档的首次提交/撰写日期（稳定不变）
- **`0X-`** 排序前缀（如 `01-`, `02-`）：综合文档的阅读顺序
- **`cip-N-xxx`**：CIP 规范，以编号为身份
- 无前缀：`README.md`、`CLAUDE.md` 等固定名称文件

---

## 🧠 wiki/ — LLM 维护的综合知识库

**设计**: 参照 [`LLM_Wiki.md`](LLM_Wiki.md) 的模式，由 LLM 从 raw sources 综合、交叉引用、持续维护。

**入口**:
- [`wiki/index.md`](wiki/index.md) — 内容索引
- [`wiki/AGENTS.md`](wiki/AGENTS.md) — 操作规约（Ingest/Query/Lint 工作流）
- [`wiki/parameters.md`](wiki/parameters.md) — 参数常量权威表（代码为准）
- [`wiki/drift.md`](wiki/drift.md) — 文档-代码漂移看板
- [`wiki/log.md`](wiki/log.md) — 变更时序日志

**页面分类**:
- `concepts/` — 跨文档综合的抽象主题（15 页：actor-model、continuation、basefee、timer-mechanism、runner-verification、settlement-slashing、vrf-runner-selection、governance、runner-delegation、dns-addressable-actors、public-asset-hosting、custom-domains、tee-attestation、mpp-session 等）
- `entities/` — 具体系统实体（7 页：system-actors、runner-lifecycle、pvm、node、plans-inventory、gateway、route-registry）

**权威层级**: 代码 > 修正案 > CIP > 白皮书 > 其它 raw（含 plans/）。

---

## 📘 whitepaper/ — 核心技术白皮书

所有技术决策的最高依据，**请勿改动**。

- `Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md` ⭐⭐⭐ 最新中文版
- `Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_EN.md` 最新英文版
- `2026-03-21_cowboy-technical-whitepaper-revised.md` 3 月修订版
- `*(Suggestion-SDK Ergonomics)*_v2/v3_EN.md` SDK 人体工程学建议

---

## 📋 cips/ — Cowboy Improvement Proposals

CIP-1 到 CIP-25（Actor 调度、链下计算、费用模型、Tokens、存储、Timer (r2)、SDK、MPP Session、Runner 容器、**Runner Connectivity (r1.1)**、治理、Runner Delegation、DNS-Addressable Actors、Public Asset Hosting、Custom Domains、**Verifiable State Read RPC**、Payments、MCP Ingress、Fungible Tokens、Liquidity Pools、Continuous Auctions、TEE Execution、Cross-Chain）。

**v2 alignment 系列**（2026-04-21 round 6 + 2026-05-11 r2 重排）：CIP-1 / 2 / 9 / 10 / 13 / 14 / 15 / 16 / 23 各发布 `*-v2.md` alignment 文件；2026-05-11 r2 修订把系统 actor 地址段后移 +1 为 `SESSION_ACTOR=0x0C`（代码已 commit）让位，最终序列：`0x0C` SESSION_ACTOR / `0x0D` ROUTE_REGISTRY / `0x0E` GATEWAY_REGISTRY / `0x0F` RECEIPT_REGISTRY / `0x10` CONTAINER_REGISTRY / `0x11` PAYMENT_GATE。SystemInstruction opcode 主分配表（CIP-13 v2 §1, 52-67）保持不动。

**新 CIPs**（2026-05 起新增）：
- **CIP-7**（r2）— Simple Stream Protocol：Stream Key Manager 系统 actor 从 `0x06` 重排到 `0x12`（解与 DUAL_BASEFEE 长期 drift）
- **CIP-8** —— MPP Session（retroactive）：追认代码已实装的 SESSION_ACTOR `0x0C` + 6 handler + 链下 voucher
- **CIP-11**（r1.1）— Runner Connectivity and Push Job Delivery：QUIC 持久连接 + vote-piggyback presence bitmap + push 派单（替代轮询）；锚定 CIP-13 v2 `effective_stake`；块时间 disclaimer
- **CIP-17** —— Verifiable State Read RPC：`GET /state/{actor}/{key}` 返回 KV + Merkle proof
- **CIP-18**（r2）— Payments：PaymentGate `0x11`，MPP+x402 双 wire，4 付款模型
- **CIP-19**（r2）— Gateway MCP Ingress：actor-as-MCP-server，tools/list 派生自 CIP-15 路由表
- **CIP-25**（r1.1）— Cross-Chain Architecture：三层（state anchoring / mailbox / apps），可换信任后端

详见 [`wiki/parameters.md`](wiki/parameters.md) Opcode 主分配表与 [`wiki/entities/system-actors.md`](wiki/entities/system-actors.md)。

---

## 🗺️ plans/ — 工程实施计划

27 份工程实施计划 / 评估 / 路径图（2026-04-17 入库 22 份；2026-04-20 起新增 5 份）。详见 [`wiki/entities/plans-inventory.md`](wiki/entities/plans-inventory.md)。

**主题分组**：经济/费用/Basefee（7）、性能/TPS/出块（6）、可靠性（1）、Bench/可观测性（2）、PVM（1）、钱包（2）、治理（1）、文档/测试/待办（4）、CIP/跨子系统集成（3）。

**命名约定**：kebab-case slug 为主；2026-04 起新引入 `YYYY-MM-DD_<slug>.md` 日期前缀（用于跨多主题或紧密关联当日提案的计划，如 `2026-05-06_mpp_session_implementation.md`）。

**性质**：非规范性 raw source，权威顺序仍是 **代码 > 修正案 > CIP > 白皮书 > plans/**。

---

## ⛓️ chain/ — 整体架构与集成

- `2026-01-24_PVM_CHAIN_INTEGRATION_CN.md` — PVM 与主链低耦合对接方案
- `2026-01-24_WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md` ⭐ 白皮书评审后的工作方案
- `2026-02-19_Cowboy_Project_Architecture_Overview.md` / `_EN.md` — 技术架构全景图
- `2026-04-02_简单交易全链路性能与可观测性方案.md` — 全链路性能与观测设计
- `2026-04-10_cowboy-tempo-ecosystem-blueprint.md` — 生态蓝图

---

## 🖥️ node/ — 主链节点

**综合文档**（优先阅读）：
- `01-项目概览与路线图.md` ⭐⭐⭐
- `02-实施与技术实现.md`
- `03-测试与验证.md`
- `04-当前状态与行动项.md` ⭐⭐⭐

**历史/专题**：
- `2026-02-05_VALIDATOR_VS_COWBOY_CHAIN.md`
- `2026-02-21_SoftFloat_VRF_Implementation_Report_CN/EN.md` — SoftFloat/VRF 实现报告
- `2026-02-22_Validator日志中常见WARN说明.md`
- `2026-02-22_如何获得actor列表.md`
- `2026-02-24_ADDRESS_MIGRATION_ETH_STYLE.md` — 地址迁移方案
- `2026-02-25_Account_CLI_Dev_Task_Brief.md`
- `2026-02-25_Cowboy_Node_Build_Install_Guide.md`
- `2026-02-25_Cowboy_Node_Installation_Report.md`
- `2026-04-11_Validator_Stall_Root_Cause_Analysis.md`

`_archive_/` — 已整合到综合文档的旧文档。

---

## 🐍 pvm/ — Python 虚拟机

**综合文档**（优先阅读）：
- `01-API参考与使用指南.md` ⭐⭐⭐⭐⭐
- `02-功能设计与Continuation.md`
- `03-Checkpoint-Resume实现指南.md`
- `04-编码规范与最佳实践.md` ⭐⭐⭐⭐⭐
- `05-测试评估与升级.md`

**历史/专题**：
- `2026-01-24_PVM_IMPLEMENTATION_PLAN.md`
- `2026-01-24_PVM_REAL_COMPLETENESS_ASSESSMENT.md`
- `2026-01-27_SOFTFLOAT_PERFORMANCE.md` / `_TESTING.md`
- `2026-02-27_PVM_Runtime_Alias_Design_CN.md` — SDK alias 设计
- `2026-03-04_pvm-call-actor-session-upgrade-summary.md` — 跨 Actor 调用链路改造

`_archive_/` — 旧文档；`pvm_bytecode_design/` — 字节码设计专题。

---

## 🏃 runner/ — 链下执行系统

- `2026-01-24_Runner_Implementation_Plan_CN.md`
- `2026-01-27_NODE_ACTOR_RUNNER_FLOW.md`
- `2026-01-27_README_CN.md` / `2026-01-27_TESTS_README_CN.md`
- `2026-01-29_MCP_INTEGRATION.md` / `MCP_USAGE.md`
- `2026-02-05_DOCUMENTATION.md` — Runner 详细文档
- `2026-02-05_QUICK_START_MCP.md` / `QUICK_SUBMIT.md` / `SUBMIT_JOB_GUIDE.md`
- `2026-02-26_Runner_Graceful_Shutdown_Plan_CN/EN.md`
- `2026-03-03_Entitlement.md` — 权限机制
- `2026-03-05_deterministic_runner_selection.md` / `_en.md` — 确定性选择算法
- `2026-04-28_MPP_Session_Research.md` — MPP（Machine Payment Protocol）Session 模式集成研究（详见 [`wiki/concepts/mpp-session.md`](wiki/concepts/mpp-session.md)）

---

## 💰 economics/ — 费用模型与经济学

- `2026-02-22_actor_economics_faq.md` — Actor 经济学 FAQ
- `2026-02-22_timer_basefee_analysis.md` — Timer Basefee 分析
- `2026-02-23_cowboy_economics_comprehensive.md` — 经济学综合指南
- `2026-04-12_Basefee_Throttle_Analysis/` — Basefee 节流分析（中/英/原文）
- `2026-04-12_Devnet_Basefee_Economics/` — Devnet Basefee 经济学（中/英）
- `2026-04-13_fee-audit-report.md` ⭐ 费用审计报告（进行中）

相关规范：`cips/cip-3-fee-model.mdx`。

---

## 🧑‍💻 devex/ — 开发者体验与客户反馈

- `2026-02-18_Developer_Experience_Situational_Awareness.md` — DevEx 态势
- `2026-02-18_devex_review_comments.md`
- `2026-02-19_Cowboy_DevEx_Feedback_CN/EN.md`
- `2026-02-19_client_alignment_analysis.md` / `_CN.md`
- `2026-02-19_client_followup_strategy.md`
- `2026-02-19_slack_client_feedback.md`
- `2026-02-21_DevEx_Communication_Draft_CN/EN.md`
- `2026-02-22_Customer_Requirements_Fulfillment_Summary.md`
- `2026-02-22_SDK_Technical_Implementation_Analysis_CN.md`

---

## 🔍 analysis/ — 跨主题分析与规划

- `2026-02-16_whitepaper_vs_code_comparison.md` / `_en.md` — 白皮书对标代码
- `2026-02-21_Internal_Meeting_Minutes.md` — 内部会议纪要
- `2026-03-03_gap_analysis_report.md` — 综合 gap 分析
- `2026-03-16_gap_analysis_economic_system.md` — 经济系统 gap（CIP-3/7/20/21/22）
- `2026-03-17_conflict_analysis.md` — 白皮书/CIP-2/代码冲突识别
- `2026-03-21_cowboy_issues_fix_plan.md` — 95 issues 修复计划
- `2026-03-31_bench_analysis_report.md` — Devnet 性能基准分析

---

## 🛠️ common/ — 基础设施

- `2026-01-24_git-submodule-integration-guide.md`
- `2026-01-24_nginx-installation.md`
- `2026-01-24_nginx-reverse-proxy-config.md`
- `2026-02-18_cicd_deployment_plan_cn.md` / `_en.md`

---

## 🗄️ _archive_/ — 归档

已被新版文档替代或内容完全过时的历史文档。仅供追溯参考。

- `_archive_/202602/` — 2 月白皮书草稿及被替代的清单
- 根 `_archive_/*.md` — 早期升级评估、集成测试状态等

---

## 📖 阅读路径建议

**新人入门**
1. `whitepaper/*_CN.md` — 核心理念
2. `pvm/01-API参考与使用指南.md` — PVM API
3. `pvm/04-编码规范与最佳实践.md` — Python Actor 规范
4. `chain/2026-01-24_PVM_CHAIN_INTEGRATION_CN.md` — 整体架构

**开发者**
1. `node/01-项目概览与路线图.md`
2. `node/04-当前状态与行动项.md`
3. `node/02-实施与技术实现.md`
4. `pvm/02-功能设计与Continuation.md`

**经济/费用相关**
1. `cips/cip-3-fee-model.mdx`
2. `economics/2026-04-13_fee-audit-report.md`
3. `economics/2026-02-23_cowboy_economics_comprehensive.md`

**项目管理**
1. `chain/2026-01-24_WORK_PLAN_AFTER_WHITEPAPER_REVIEW.md`
2. `analysis/2026-03-21_cowboy_issues_fix_plan.md`
3. `node/01-项目概览与路线图.md`

---

## 🔄 维护原则

1. **主题归位**：新文档按主题（node/pvm/runner/chain/economics/devex/common）放入对应目录
2. **跨主题放 analysis/**：涉及多个子系统的综合分析、gap 报告、会议纪要进 `analysis/`
3. **工程计划放 plans/**：可执行的实施方案 / 评估 / 路径图进 `plans/`（与 `analysis/` 区分：plans 偏「打算做什么」，analysis 偏「现状是什么」）
4. **日期前缀**：新文档以 `YYYY-MM-DD_` 为前缀，日期为首次提交日（出生日，不随修订变更）
5. **替代则归档**：文档被新版本完全替代时，移入 `_archive_/` 并在 PR 中标注替代者
6. **whitepaper/ 受保护**：不改动
7. **wiki/ 由 LLM 维护**：raw 文档新增/修订时按 [`wiki/AGENTS.md`](wiki/AGENTS.md) 的 Ingest 流程同步更新概念页 / 实体页 / 参数表 / 漂移看板 / 日志
