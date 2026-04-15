---
type: concept
tags: [basefee, eip-1559, economics]
sources:
  - node/execution/src/basefee.rs
  - refs/cips/cip-3-fee-model.mdx
  - refs/economics/2026-04-12_Basefee_Throttle_Analysis
  - refs/economics/2026-04-13_fee-audit-report.md
  - refs/analysis/2026-04-15_documentation_amendments.md
last_updated: 2026-04-15
status: authoritative
---

# Basefee 更新公式

Cowboy 对 Cycles 和 Cells 各维护独立 basefee，每块按几何更新规则调整。状态持久化在 System Actor `0x06`（DUAL_BASEFEE）。

---

## 公式（代码权威）

```text
Δ = basefee × |used − target| / target / ALPHA
Δ = min(Δ, basefee / DENOM)   # clamp

if used > target:
    basefee_new = basefee + Δ
else:
    basefee_new = basefee − Δ

basefee_new = max(MIN_BASEFEE, min(MAX_BASEFEE, basefee_new))
```

**参数（`node/execution/src/basefee.rs:99-119`）**:
- `ALPHA = 96`（反馈平滑系数）
- `DENOM = 96`（单步最大变化比率分母）
- `MIN_BASEFEE = 10,000`
- `MAX_BASEFEE = 10²⁴`

---

## 特性

- **温和反馈**: ALPHA=96 比白皮书原设计（α=8）温和 12 倍，避免剧烈波动
- **双向 clamp**: 单步变化不超过 `basefee / DENOM`，上下界硬边界
- **独立市场**: Cycles 与 Cells 各一套状态，互不影响

---

## 生命周期（`storage/src/process_block.rs`）

```
load → prepare_block_basefee → execute block → finalize_block_basefee → persist
```

1. **prepare**: 从 `0x06` 读上块 basefee
2. **execute**: 交易按 `basefee + tip` 计费
3. **finalize**: 根据块 cycles/cells 实用量计算下块 basefee
4. **persist**: 写回 `0x06`

---

## Tip 分配

用户交易 tip 的去向按 `SettlementConfig`（`0x09` 治理）：`runner / burn / treasury`。详见 [[settlement-slashing]]。

Basefee 本身 **100% burn**（EIP-1559 经典做法）。

---

## 源文档冲突 / 漂移

| 项 | 旧 | 代码 |
|---|---|---|
| WP §4.2 α=8, δ=12.5% + clamp | 过时 | ALPHA=96 |
| WP §17.8 简化线性 | 错误 | 不使用 |
| MIN_BASEFEE = 1 | 过时 | 10,000 |

见 [[../drift]] 条目 A-3。

---

## 相关
- [[dual-gas-model]] — 双计量上下文
- [[../entities/system-actors]] — 0x06 DUAL_BASEFEE
- [[../parameters]]
- `refs/economics/2026-04-12_Basefee_Throttle_Analysis/` — 节流分析
- `refs/economics/2026-04-12_Devnet_Basefee_Economics/` — Devnet 实测
