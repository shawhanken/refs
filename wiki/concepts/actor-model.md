---
type: concept
tags: [actor, messaging, fundamentals]
sources:
  - refs/whitepaper/Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md
  - refs/cips/cip-1-actor-scheduler.mdx
  - refs/pvm/02-功能设计与Continuation.md
last_updated: 2026-04-15
status: authoritative
---

# Actor 模型

Cowboy 的核心计算抽象：每个链上合约是一个 **Actor**，独立状态 + 独立代码（PVM Python）+ 独立邮箱。Actor 之间**只通过消息通信**，没有共享内存。

---

## 三要素

1. **Address**（20 字节 ETH-style）— 唯一身份，见 [[../parameters]]
2. **Code**（Python bytecode）— 执行在 [[../entities/pvm]]
3. **Storage** — Actor 本地 KV（`state_get / state_set` host API）

---

## 消息模型

两种调用方式：

- `send_message(addr, payload)` — **异步**，目标 Actor 下一次被调度时处理
- `call_actor(addr, method, args)` — **同步**，立即递归执行目标 Actor handler，返回值（最深 32 层调用）

异步消息进入目标 Actor 的 mailbox，由调度器决定何时消费。

---

## 调度与执行

每块内：
1. 交易执行（用户显式调用 / 消息递送）
2. 过期 Timer 以 deferred tx 形式执行（[[timer-mechanism]]）
3. 深度同步调用不超过 32 层，溢出回滚

详见 [[speculative-execution]]。

---

## 确定性

- Actor 代码必须通过 `validate_actor_code()`（[[../entities/pvm]]）
- 跨 Actor 消息按固定顺序处理，避免 race
- 消息内容 **CBOR Canonical** 序列化（见 [[../parameters]]）

---

## 与 CIP-1 Actor Scheduler 的关系

CIP-1 描述**高层**调度策略（tiered calendar queue + GBA bidding），当前实现为 FIFO 简化版（CIP-5 记录实际行为）。Timer 调度是 CIP-1 风格的 GBA，见 [[timer-mechanism]]。

---

## 源文档冲突
无已知冲突。CIP-1 的 "Timer-then-Tx" 顺序与代码 "Tx-then-Timer" 相反；已在 [[../drift]] 条目 E-1 标注。

---

## 相关
- [[../entities/pvm]] — 执行环境
- [[continuation]] — Actor 之间跨块协作
- [[timer-mechanism]] — 定时调度
- [[speculative-execution]] — 块级执行
