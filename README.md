# Cowboy 项目参考文档索引

本目录包含 Cowboy 项目的所有参考文档，按**主题**分类整理。跨主题的综合分析、报告、会议纪要集中在 `analysis/`，由 LLM 维护的综合 wiki 位于 `wiki/`。

**最后更新**: 2026-09-21（有效性审计：`refs/cips/` 全部标注为过时快照、权威改指 `cowboy/docs/cips/`；索引与盘点对账；失效链接修复）

> ### ⚠️ 读之前先知道两件事
>
> 1. **CIP 规范的权威副本不在这里。** 权威、与代码对齐的 CIP 在 **`cowboy/docs/cips/`**。
>    `refs/cips/` 是 2026-03 ~ 2026-08 之间的快照镜像，**34 份全部已落后**（差距从 15 行到 2035 行不等），
>    且完全缺 CIP-27 / 30 / 33 / 34 / 36 / 40 / 41 / 42。每个档头都有 STALE SNAPSHOT 横幅标注具体差距。
>    保留它们只为历史追溯 —— **不要据此实作**。
> 2. **代码永远是最终权威。** 文档（含 `wiki/`、`whitepaper/`、任何 CIP）与代码冲突时以代码为准。
>    系统 actor 地址以 `node/runner/src/system_actors.rs` 的 `well_known_low_byte_assignments` pin 测试为准。

---

## 🧭 从哪里开始

- **快速定位概念 / 参数 / 冲突** → **[`wiki/`](wiki/index.md)**（LLM 综合层，权威参数与跨文档综合）
- **读规范原文** → **`cowboy/docs/cips/`**（权威）；`refs/cips/` 仅作历史快照，`whitepaper/`
- **读历史上下文** → `node/`、`pvm/`、`runner/`、`chain/`、`economics/` 等主题目录
- **追漂移 / 修正案** → [`analysis/2026-04-15_documentation_amendments.md`](analysis/2026-04-15_documentation_amendments.md) 或 [`wiki/drift.md`](wiki/drift.md)

---

## 📁 目录结构

```
refs/
├── wiki/         LLM 维护的综合知识库（概念/实体/参数/漂移/日志）
├── whitepaper/   核心技术白皮书（受保护，不改动）+ _archive_/ 历史版本
├── cips/         ⚠️ CIP 过时快照（权威在 cowboy/docs/cips/）+ ext_* 扩展分析
├── plans/        工程实施计划 / 评估 / 路径图（2026-04 ~ 2026-06，多已执行完）
├── chain/        跨系统集成与整体架构
├── node/         主链节点实现
├── pvm/          Python 虚拟机
├── runner/       链下执行系统
├── economics/    费用模型 / Basefee / Gas / Tokenomics
├── devex/        开发者体验与客户反馈
├── analysis/     跨主题分析、会议纪要、问题修复计划、修正案
├── common/       通用基础设施（nginx、CI/CD、git 子模块）
├── dev_support/  开发工具（MCP server、Actor 模板、SDK 手册）
├── meeting/      会议逐字稿 / 纪要 / Slack 频道存档
├── notion/       从 Notion 导入的设计评审材料（cowboy-vm-shared）
├── LLM_Wiki.md   LLM Wiki 模式说明（wiki/ 的设计蓝本）
├── cbqs-design.zh.md        CBQS（CIP-39 队列系统）设计中文稿
└── marshal_invariant_gate.md  Marshal 不变量门禁规约
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
- `concepts/` — 跨文档综合的抽象主题（20 页：actor-model、continuation、basefee、dual-gas-model、speculative-execution、timer-mechanism、runner-verification、settlement-slashing、vrf-runner-selection、governance、runner-delegation、dns-addressable-actors、public-asset-hosting、custom-domains、tee-attestation、mpp-session、payments、mcp-ingress、cross-chain、verifiable-state-read）
- `entities/` — 具体系统实体（7 页：system-actors、runner-lifecycle、pvm、node、plans-inventory、gateway、route-registry）

**权威层级**: 代码 > 修正案 > `cowboy/docs/cips/` 的 CIP > 白皮书 > 其它 raw（含 `refs/cips/` 快照与 `plans/`）。

> `wiki/` 各页的 `last_updated` 时间差异很大（2026-05 ~ 2026-08）。`entities/system-actors.md` 与
> `parameters.md` 在 2026-08-15 按代码 pin 测试重写过，是目前最可信的两页；其余页仍可能残留
> 2026-05 的 v2 spec 序列。以页内 frontmatter 的 `last_updated` 判断新鲜度。

---

## 📘 whitepaper/ — 核心技术白皮书

所有技术决策的最高设计依据，**请勿改动**。

**当前版本**（`whitepaper/` 根目录）：

- `cowboy-technical-whitepaper.md` ⭐⭐⭐ 核心技术白皮书
- `cowboy-storage-whitepaper.md` / `.pdf` — 存储白皮书（CIP-9 / CBFS）
- `cowboy-secrets-whitepaper.md` / `.pdf` — 机密白皮书（CIP-24 / CBSS）
- `cowboy-design-decisions.md` — 设计决策记录
- `changelog.md` — 白皮书修订日志
- `cowboy-whitepaper.pdf`、`header.tex` — 排版产物与 LaTeX 头

**历史版本**在 [`whitepaper/_archive_/`](whitepaper/_archive_/)：`Cowboy_An_Actor-Model_Layer1...CN/EN.md`、
`2026-03-21_cowboy-technical-whitepaper-revised(-v2).md`、SDK Ergonomics 建议 v2/v3、以及被上面各档取代的
storage / secrets / design-decisions 旧版。**归档内容不是权威** —— 只用于追溯。

> 归档版白皮书仍使用 "Steamtrain" 旧名；该组件现名 **CBFS**（`cbfs/` repo，CIP-9 RAS）。

---

## 📋 cips/ — CIP 快照（⚠️ 权威在 `cowboy/docs/cips/`）

> **这个目录里的 34 份 CIP 全部是过时快照。** 权威、与代码对齐的规范在 **`cowboy/docs/cips/`**。
> 每份档头的 STALE SNAPSHOT 横幅标注了本地副本日期、权威档日期与两者的差异行数。
> 保留原因：这些快照被 `refs/wiki/`、`refs/analysis/` 的历史结论大量引用，删掉会断掉追溯链。

**本地快照覆盖** CIP-1 ~ 26、28、29、31、39（含 CIP-28/29/39 的中文译本）。

**本地完全没有** CIP-27（Actor Fork）、CIP-30（Per-Actor Storage Root）、CIP-33（Actor Hiring）、
CIP-34（Cross-Chain Settlement / NEAR Intents）、CIP-36（Phased Launch cUSD）、CIP-40（EIP-712 / WalletConnect）、
CIP-41（Multi-Signer Auth）、CIP-42（statusz）—— 这些只在 `cowboy/docs/cips/` 有。

**`ext_*.md`** 是 refs 独有的扩展分析（不是 CIP 本身），没有 `cowboy/docs/` 对应档，因此未加横幅：
`ext_cip-2-9-10-runner-fee-chain`、`ext_cip-9-10-meeting-gap-analysis`、`ext_cip-9-runner-steamtrain-architecture`、
`ext_cip-29-sync-cap-analysis(-en)`。

**系统 actor 地址**：快照里的地址多半是错的（v2 spec 序列，代码最终落位整体后移）。
以代码为准，或看 [`wiki/entities/system-actors.md`](wiki/entities/system-actors.md)：
`0x0C` SESSION_ACTOR / `0x0D` STREAM_KEY_MANAGER / `0x0E` ROUTE_REGISTRY / `0x0F` GATEWAY_REGISTRY /
`0x10` RECEIPT_REGISTRY / `0x11` VALIDATOR_SET / `0x12` PAYMENT_GATE / `0x13` CONTAINER_REGISTRY /
`0x14` INTENT_SETTLEMENT / `0x16` BANK_ACTOR / `0x17` STREAM_REGISTRY / `0x18` PLATFORM_FEE /
`0x19` ROOM_AUTHORITY / `0x1D` EVENT_SUBSCRIPTION / `0x1E` TRADING_POST。

**快照内容一览**（⚠️ 描述的是 2026-05 的快照状态，地址与修订号均以 `cowboy/docs/cips/` 为准）：
- **CIP-7** — Simple Stream Protocol：Stream Key Manager。快照写 `0x12`，**代码是 `0x0D`**
- **CIP-8** — MPP Session（retroactive）：追认代码已实装的 SESSION_ACTOR `0x0C` + 6 handler + 链下 voucher
- **CIP-11** — Runner Connectivity and Push Job Delivery：QUIC 持久连接 + vote-piggyback presence bitmap + push 派单。快照是 r1.1/r1.2，权威档已前进 1251 diff 行
- **CIP-17** — Verifiable State Read RPC：`GET /state/{actor}/{key}` 返回 KV + Merkle proof
- **CIP-18** — Payments：MPP + x402 双 wire、4 付款模型。快照写 PaymentGate `0x11`，**代码是 `0x12`**
- **CIP-19** — Gateway MCP Ingress：actor-as-MCP-server，tools/list 派生自 CIP-15 路由表
- **CIP-25** — Cross-Chain Architecture：三层（state anchoring / mailbox / apps），可换信任后端

详见 [`wiki/parameters.md`](wiki/parameters.md) Opcode 主分配表与 [`wiki/entities/system-actors.md`](wiki/entities/system-actors.md)（两者 2026-08-15 已按代码校正）。

---

## 🗺️ plans/ — 工程实施计划

**31 份**工程实施计划 / 评估 / 路径图（最后一份 2026-06-16 入库）。逐份清单见
[`wiki/entities/plans-inventory.md`](wiki/entities/plans-inventory.md)。

**命名约定**：kebab-case slug 为主；2026-04 起新引入 `YYYY-MM-DD_<slug>.md` 日期前缀（用于跨多主题或紧密关联当日提案的计划，如 `2026-05-06_mpp_session_implementation.md`）。

**性质**：非规范性 raw source，且**多数已执行完毕或被放弃** —— 这是「当时打算做什么」的记录，不是待办清单。
权威顺序仍是 **代码 > 修正案 > `cowboy/docs/cips/` 的 CIP > 白皮书 > plans/**。

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

`pvm_bytecode_design/` — 字节码设计专题。

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

相关规范：`cowboy/docs/cips/cip-3-fee-model.md`（权威）。

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

> **129 份，下面只是选摘。** `analysis/` 的每一份都带 `YYYY-MM-DD_` 出生日前缀，是**当时的快照**：
> 结论、优先级、完成度百分比都只对那一天成立，不随代码更新。当作历史记录读，不要当作现状。
> 需要现状请看代码、`cowboy/docs/cips/`，或 `wiki/` 里 `last_updated` 较新的页。

- `2026-02-16_whitepaper_vs_code_comparison.md` / `_en.md` — 白皮书对标代码
- `2026-02-21_Internal_Meeting_Minutes.md` — 内部会议纪要
- `2026-03-03_gap_analysis_report.md` — 综合 gap 分析
- `2026-03-16_gap_analysis_economic_system.md` — 经济系统 gap（CIP-3/7/20/21/22）
- `2026-03-17_conflict_analysis.md` — 白皮书/CIP-2/代码冲突识别
- `2026-03-21_cowboy_issues_fix_plan.md` — 95 issues 修复计划
- `2026-03-31_bench_analysis_report.md` — Devnet 性能基准分析
- `2026-05-29_ai_velocity_quality_engineering_methodology_CN.md` — **方法论** AI 高速研发下的质量工程(三支柱:可执行不变量 / 风险分级 / 逃逸棘轮 + AI 对抗式 review + 运行时纵深防御)
- `2026-06-14_cip-33-trading-post-explainer.md` — **CIP-33 详解** Trading Post(actor 雇佣/分销/计费/解密垄断式版权保护)商业企图 + 机制 + 三张时序图(hire→分账→密钥发放→执行 / PerCall 结算 / 撤销失效)
- `2026-06-14_cip-33-rollout-coordination-checklist.md` — **CIP-33 上线 checklist** Marshal 四件套(cowboy#180 / node#700 / cbss#24 / runner#113)审计汇总:跨仓依赖图 + node#700 两个 latent HIGH(已上棘轮)+ 规格↔实现 MUST 缺口 + 原子上线顺序与上线前验证清单
- `2026-06-12_open-issues-easy-to-hard.md` — **未解决 issue 由易到难分档**(6 档 + Tier-0 排除项;含 9 次降噪/可行性重排更新、批量循环交付战报)
- `2026-06-14_feasibility-ranked.md` — **全量可行性重排**(619 条 PL/未指派,按「本地可实现+可验证」由易到难;程式化预分类 + 7 路 agent 逐条核验)。结论:真正现在可本地交付 ~26 条(F-0..F-3),其余 ~535 条卡共识/缺基建/绿地/他团队-非本地;含 B-2 建 harness 的高杠杆建议
- `2026-09-03_homestead_web_delivery_postmortem.md` / `.zh.md` — **Homestead 交付复盘**（CIP-39 v2 分支，移植→跑通→外壳→公网→性能→交付；26 个缺陷按**错误形状**分类，绝大多数在 806 个单元测试全绿时潜伏：镜像实现的测试 / 删专用机制≠删能力 / 协议级静默失败 / 测错了对象 / 悬崖而非斜坡；含耗时最久那个缺陷的完整诊断路径与三次「改完更糟」的记录，以及信任锚点 3.4 天硬期限的运维结论）

---

## 🛠️ common/ — 基础设施

- `2026-01-24_git-submodule-integration-guide.md`
- `2026-01-24_nginx-installation.md`
- `2026-01-24_nginx-reverse-proxy-config.md`
- `2026-02-18_cicd_deployment_plan_cn.md` / `_en.md`

---

## 📖 阅读路径建议

**新人入门**
1. `whitepaper/cowboy-technical-whitepaper.md` — 核心理念（中文旧版在 `whitepaper/_archive_/`）
2. `pvm/01-API参考与使用指南.md` — PVM API
3. `pvm/04-编码规范与最佳实践.md` — Python Actor 规范
4. `chain/2026-01-24_PVM_CHAIN_INTEGRATION_CN.md` — 整体架构

**开发者**
1. `node/01-项目概览与路线图.md`
2. `node/04-当前状态与行动项.md`
3. `node/02-实施与技术实现.md`
4. `pvm/02-功能设计与Continuation.md`

**经济/费用相关**
1. `cowboy/docs/cips/cip-3-fee-model.md`
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
5. **替代则删除**：文档被新版本完全替代时，删除旧版（git 历史保留追溯能力），并在 PR 中标注替代者。
   **例外：`refs/cips/`** —— 这些快照被 `wiki/` 与 `analysis/` 的历史结论大量引用，删掉会断掉追溯链，
   因此改为在档头加 STALE SNAPSHOT 横幅指向 `cowboy/docs/cips/`，正文一律不改写
   （改写会制造「已维护」的假象；见 [`wiki/drift.md`](wiki/drift.md) 2026-08-16 条）
6. **whitepaper/ 受保护**：不改动。历史版本进 `whitepaper/_archive_/`
7. **wiki/ 由 LLM 维护**：raw 文档新增/修订时按 [`wiki/AGENTS.md`](wiki/AGENTS.md) 的 Ingest 流程同步更新概念页 / 实体页 / 参数表 / 漂移看板 / 日志
8. **不要把 CIP 规范同步回 `refs/cips/`**：唯一权威是 `cowboy/docs/cips/`。复制一份回来只会在三个月后
   再漂移一次 —— 需要引用就直接指向 `cowboy/docs/cips/`
9. **索引与被索引者对账**：改动 `plans/`、`wiki/concepts/`、`wiki/entities/` 的档数时，同步更新
   本 README 与 [`wiki/entities/plans-inventory.md`](wiki/entities/plans-inventory.md) 的计数与清单
