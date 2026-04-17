# Wiki Schema & Maintenance Protocol

本文是 `refs/wiki/` 的**操作规约**，规定 LLM Agent 如何读写 wiki。人类负责读、提问、提供 raw sources；Agent 负责写作、交叉引用、维护一致性。

---

## 三层架构

1. **Raw sources**（不可变）— LLM 只读
   - `refs/whitepaper/` — 白皮书（最高设计依据，受保护）
   - `refs/cips/` — 正式规范（living specs）
   - `refs/node/`、`refs/pvm/`、`refs/runner/`、`refs/chain/` — 各子系统历史与综合文档
   - `refs/economics/`、`refs/devex/`、`refs/common/` — 专题文档
   - `refs/analysis/` — 跨主题分析、修正案、会议纪要
   - `refs/plans/` — 工程实施计划 / 评估 / 路径图（随机 slug 命名；见 `wiki/entities/plans-inventory.md`）
   - `refs/_archive_/` — 归档（只读、不参与一致性检查）
   - 代码（真正权威）位于 workspace `node/`、`runner/`、`steamtrain/` workspace

2. **Wiki**（`refs/wiki/`）— LLM 全权维护
   - `index.md`、`log.md` — 索引与时序
   - `parameters.md` — 参数/常量权威表
   - `drift.md` — 文档-代码漂移看板
   - `concepts/` — 跨文档综合概念页
   - `entities/` — 系统实体页

3. **Schema**（本文件）

---

## 页面格式（所有 wiki 页通用）

```markdown
---
type: concept | entity | comparison | parameter
tags: [runner, consensus, ...]
sources: [refs/path/to/src1, refs/path/to/src2]
last_updated: YYYY-MM-DD
status: authoritative | draft | stale
---

# 标题

## 概述
一句话定义 + 2-3 句综合，面向读者直接理解。

## 正文
主要内容。章节分层视需要。引用代码时带路径 + 行号。

## 相关
- 链接到其他 wiki 页（[[concepts/xxx]] 风格）
- 链接到 raw sources（`refs/xxx.md §Y`）

## 源文档冲突 / 漂移
（如有）指向 `refs/analysis/2026-04-15_documentation_amendments.md` 条目。

## Sources
精确列出所引 raw source 路径 + 简述。
```

**约定**:
- 日期使用 `YYYY-MM-DD`
- 代码引用使用 `path/to/file.rs:LINE` 格式
- wiki 内交叉引用写相对路径（`../concepts/xxx.md`）或 `[[wiki-link]]` 风格（视工具）
- 权威顺序：**代码 > 修正案 (analysis/*amendments*) > CIP > 白皮书 > 其它 raw**
- `refs/plans/` 属"其它 raw"，非规范性；wiki 中引用计划必须说明其状态（提议 / 进行中 / 已落地）

---

## 操作：Ingest（新 raw source 进入）

当有新文档加入 `refs/` 任一 raw 目录，Agent 执行：

1. 读完新文档，与人类讨论关键要点
2. 判断是新增概念还是修订已有概念
3. **创建或更新** 相关 `wiki/concepts/` 或 `wiki/entities/` 页
4. 更新 `wiki/index.md` — 列出新 wiki 页（若有）
5. 若与已有 wiki 页矛盾：在该页 `## 源文档冲突` 章节标注，并考虑更新 `wiki/drift.md` 或 `refs/analysis/*amendments*.md`
6. 在 `wiki/log.md` 末尾 append：`## [YYYY-MM-DD] ingest | <source 标题>`，列出受影响 wiki 页

---

## 操作：Query（人类提问）

1. 先读 `wiki/index.md` 定位相关 concept/entity
2. 读相关 wiki 页
3. 必要时回溯 raw source（wiki 页 Sources 列表给出）
4. 回答附 wiki 页路径 + raw source 路径作为引用
5. 若产生有价值的新综合（比较、关联），**写回 wiki**：
   - 比较页 → `wiki/concepts/` 或 `wiki/entities/`
   - 在 `wiki/log.md` append `## [YYYY-MM-DD] query | <问题摘要>` + 产物

---

## 操作：Lint（周期健康检查）

Agent 定期执行（或人类触发）：

- **Stale**: 检查 `last_updated` 早于相关 raw source 最近修改；标记并更新
- **Orphan**: 没有任何 wiki 页引用的 wiki 页；评估是否删除
- **Contradiction**: wiki 页之间或与修正案不一致；更新并记录
- **Missing concept**: raw source 频繁提及但无对应 wiki 页；提议新建
- **Drift**: 代码与文档数值不一致；更新 `wiki/drift.md`、同步 `analysis/*amendments*.md`

每次 lint 在 `wiki/log.md` append `## [YYYY-MM-DD] lint | <摘要>`。

---

## 页面类型与命名

| 类型 | 目录 | 命名 |
|---|---|---|
| 概念（跨文档综合的抽象主题）| `wiki/concepts/` | `kebab-case.md`，如 `dual-gas-model.md` |
| 实体（具体系统组件/对象）| `wiki/entities/` | `kebab-case.md`，如 `system-actors.md` |
| 参数汇总 | `wiki/parameters.md` | 单页 |
| 漂移看板 | `wiki/drift.md` | 单页 |
| 索引 | `wiki/index.md` | 单页 |
| 时序日志 | `wiki/log.md` | 单页 |

**原则**: 宁少勿多。只当一个主题跨 3+ raw sources 或存在矛盾时建 wiki 页；否则让 raw sources 各自为战。

---

## 权威层级与冲突裁决

当 wiki 页综合了多个 raw sources 且它们不一致时：

1. **查代码** — 若代码存在实际实现，以代码为准
2. 查 `refs/analysis/2026-04-15_documentation_amendments.md` — 若已有修正案条目，以修正案为准
3. 查 CIP — 若代码/修正案都未明确，以 CIP 为准
4. 查白皮书
5. 其它 raw sources

wiki 页在引用时标注权威级别；不一致处在 `## 源文档冲突` 章节显式列出。

---

## 元数据示例（frontmatter）

```yaml
---
type: concept
tags: [consensus, economics, cip-3]
sources:
  - refs/cips/cip-3-fee-model.mdx
  - refs/economics/2026-04-13_fee-audit-report.md
  - refs/analysis/2026-04-15_documentation_amendments.md
last_updated: 2026-04-15
status: authoritative
---
```

---

## 工具提示

- wiki 是 git 仓库的一部分；每次 ingest/lint 产生独立 commit 便于追溯
- 检索可用 `grep` / ripgrep 直接扫描；后续可接入 qmd 或类似 local 搜索引擎
- `log.md` 的 `## [YYYY-MM-DD]` 前缀格式便于 `grep "^## \[" log.md | tail`

---

**本文件由 LLM + 人类共同演进**。当工作流或约定需调整时，先改本文件，再改 wiki。
