---
type: comparison
tags: [drift, consistency, audit]
sources:
  - refs/analysis/2026-04-15_documentation_amendments.md
last_updated: 2026-04-15
status: authoritative
---

# 文档-代码漂移看板

跟踪 `refs/` 中文档与 workspace 代码实际实现之间的不一致。

**权威文件**: [`refs/analysis/2026-04-15_documentation_amendments.md`](../analysis/2026-04-15_documentation_amendments.md) — 修正案正文与精确引用。

本页是 wiki 内的摘要看板，便于快速扫视和追踪状态。

---

## 当前活跃漂移（13 项，按严重性排序）

### 高严重性（6）

| ID | 主题 | 现状 |
|---|---|---|
| A-1 | `BLOCK_CYCLES_TARGET` 10M vs 20M | ✅ 修正案已发布；CIP-3 顶部 banner |
| A-2 | `BLOCK_CELLS_TARGET` 500K vs 4M | ✅ 同上 |
| A-3 | Basefee 公式（α=8 / 简化线性 / ALPHA=96）| ✅ 同上 |
| B | System Actor 地址表 0x01-0x0B | ✅ CIP-2 顶部 banner；workspace CLAUDE.md 待更新 |
| C | Runner stake 公式（1.5× vs 10×）| ✅ CIP-2 顶部 banner |
| E-1 | Timer 执行顺序（CIP-1 与代码相反）| ✅ CIP-1 顶部 banner |

### 中严重性（7）

| ID | 主题 | 现状 |
|---|---|---|
| A-4 | Transfer 成本（21K/0 → 5K/500）| ✅ CIP-3 顶部 banner |
| D | VerificationMode 4 → 6 variants | ✅ CIP-2 顶部 banner |
| E-2 | CIP-5 Globalbox EOB 未实现 | ✅ CIP-5 顶部 banner |
| F | Address ETH-style 已落地 | ✅ ADDRESS_MIGRATION 提案标 ✅已实施 |
| G-1 | Token hook 50K 为阶段 1 声明未扣费 | ✅ CIP-20 顶部 banner |
| G-2 | Runner stake 两层门槛（10K/50K）| ✅ Entitlement 顶部 banner |
| — | workspace `/home/ubuntu/workspace/CLAUDE.md` 常量 | ⚠️ 待更新（BLOCK_* 与 System Actor 地址）|

---

## 监控维度

在 lint 时扫描这些线索，发现新漂移时追加到修正案：

1. 代码常量变更（`node/types/src/constants.rs`、`execution/src/basefee.rs`、`execution/src/gas.rs`）
2. 新枚举 variant（`VerificationMode`、`SystemInstruction`、`ActorInstruction`）
3. CIP 修订（`refs/cips/` 中 `Revised:` 字段）
4. 白皮书更新（`refs/whitepaper/` — 受保护，只读对比）
5. 新 System Actor（`node/runner/src/system_actors.rs`）

---

## 更新流程

当发现新漂移：
1. 验证代码侧实际值
2. 追加条目到 `refs/analysis/2026-04-15_documentation_amendments.md`（或当月新修正案）
3. 在受影响的 CIP / raw source 顶部加 Warning banner 指向修正案
4. 本文件（`drift.md`）追加条目到对应严重性区
5. `wiki/log.md` append `## [YYYY-MM-DD] lint | <摘要>`
6. 相关 `wiki/parameters.md` / concept 页同步更新

---

## 相关
- [[parameters]] — 参数权威表（漂移修复后的结果在此）
- [`refs/analysis/2026-04-15_documentation_amendments.md`](../analysis/2026-04-15_documentation_amendments.md) — 修正案正文
