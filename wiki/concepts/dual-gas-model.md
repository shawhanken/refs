---
type: concept
tags: [gas, economics, cip-3]
sources:
  - refs/cips/cip-3-fee-model.mdx
  - refs/economics/2026-02-23_cowboy_economics_comprehensive.md
  - refs/economics/2026-04-13_fee-audit-report.md
  - refs/analysis/2026-04-15_documentation_amendments.md
last_updated: 2026-04-15
status: authoritative
---

# 双计量 Gas 模型（Dual-Metered Gas）

Cowboy 分离**计算**与**数据**两种稀缺资源：

- **Cycles** — 计算工作量（指令、算术、比较、控制流）
- **Cells** — 数据量（calldata、return data、存储读写 bytes）

每块独立 EIP-1559 basefee 市场，互不干扰。

---

## 核心参数（代码权威，见 [[../parameters]]）

| 维度 | Cycles | Cells |
|---|---|---|
| Block Target | `20,000,000` | `4,000,000` |
| Basefee MIN | `10,000` | `10,000` |
| Basefee 公式 | 几何更新，ALPHA=96 | 同上（独立状态）|

> CIP-3 / 白皮书原写 10M/500K，已通过修正案 A-1、A-2 更正。

---

## 计费规则

| 操作 | Cycles | Cells |
|---|---|---|
| Transfer | 5,000 | 500 |
| Calldata | — | 1 cell/byte |
| Return data | — | 1 cell/byte |
| Storage Read | `STORAGE_READ_CYCLES` × read_count（PVM 后批扣）| — |
| Storage Write | — | 按 value 长度 cell/byte |
| PVM 指令 | 按 opcode cost table | — |
| Token hook | ≤ 50,000（**阶段 1 声明、阶段 2 才扣费** — G-1）| — |

---

## Gas Report 分类

`GasReport` 在执行结束时按类别输出 cycles 与 cells：
- Compute / Storage / Messaging / Calldata / Token / Runner / Timer
- 便于审计、计费、优化

源：`node/execution/src/gas.rs`

---

## 与用户交易的关系

用户交易须声明两个 gas limit：
- `cycles_limit` × `cycles_basefee + tip`
- `cells_limit` × `cells_basefee + tip`

两者独立检查；任一超限回滚。tip 分配规则见 [[settlement-slashing]]。

---

## 源文档冲突 / 漂移

| 项 | 旧值 | 代码 |
|---|---|---|
| BLOCK_CYCLES_TARGET | 10M | **20M** |
| BLOCK_CELLS_TARGET | 500K | **4M** |
| Transfer cycles | 21,000 | **5,000** |
| Transfer cells | 0 | **500** |
| Token hook 扣费 | 强制 50K | **阶段 1 未强制** |

详见 [[../drift]]。

---

## 相关
- [[basefee]] — 独立 basefee 更新公式
- [[../parameters]] — 常量权威表
- [[runner-verification]] — Runner 用 `RateCard` 独立计费
