---
type: concept
tags: [timer, scheduler, cip-1, cip-5]
sources:
  - node/execution/src/pvm_host.rs
  - node/storage/src/speculative.rs
  - refs/cips/cip-1-actor-scheduler.mdx
  - refs/cips/cip-5-timers.md
  - refs/analysis/2026-04-15_documentation_amendments.md
last_updated: 2026-04-15
status: authoritative
---

# Timer 机制

Actor 通过 `schedule_timer(height, callback, gas)` host API 注册未来块高度触发的回调。实现为 **CIP-1 风格 GBA**：每个 timer 在目标块作为 deferred tx 由原 Actor 执行。

---

## API

```python
schedule_timer(
    target_height: int,       # 目标块高度
    callback: str,            # Actor 的 handler 方法名
    gas: int,                 # 预留 cycles（上限 550,000）
    payload: bytes,           # 传给 callback 的 CBOR 数据
)
```

调用时：
- 立即扣一笔注册费（cycles）
- 将 timer 记录写入 Actor 存储
- 不阻塞当前 handler

---

## 执行时机

**块内流程**（见 [[speculative-execution]]）：
```
execute user transactions   → L152-370
→ fire expired timers       → L373-475 (deferred tx)
```

**关键**: Transactions **先于** Timers 执行（与 CIP-1 原描述相反；详见 [[../drift]] E-1）。

---

## 预算约束

| 限制 | 值 | 源 |
|---|---|---|
| 块 timer cycles 预算 | `8,888,890` | `pvm_host.rs:1051-1097` |
| 单 timer cycles 上限 | `550,000` | 同上 |

超过块预算的过期 timer 延到下块继续执行（重新进入 deferred 队列，受 [[speculative-execution]] 的 `LANE_TIMER` 预算管理）。

---

## 两种模型对比

| 模型 | 出处 | 实现状态 |
|---|---|---|
| **CIP-1 GBA**（bidding-based priority）| CIP-1 | 简化实现（FIFO，无 bidding）|
| **CIP-5 Globalbox EOB**（end-of-block 统一触发）| CIP-5 | **未实现** |

当前代码路径对应 CIP-1 的简化版：FIFO 队列、单 gas 层级、块尾统一 fire。详见：
- `refs/cips/cip-1-actor-scheduler.mdx`（Phase 2 design）
- `refs/cips/cip-5-timers.md`（实际 FIFO 行为）

---

## 源文档冲突 / 漂移

- 执行顺序：CIP-1 错，代码对 → 修正案 E-1
- 调度模型：CIP-5 Globalbox 未实现 → 修正案 E-2

见 [[../drift]]。

---

## 相关
- [[actor-model]] — 同步/异步调度
- [[continuation]] — Timer 回调作为 Continuation resume 路径
- [[speculative-execution]] — 块内执行顺序
- [[../parameters]] — 预算常量
