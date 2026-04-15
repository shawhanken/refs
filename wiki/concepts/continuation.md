---
type: concept
tags: [continuation, checkpoint, fsm]
sources:
  - refs/pvm/02-功能设计与Continuation.md
  - refs/pvm/03-Checkpoint-Resume实现指南.md
  - refs/pvm/04-编码规范与最佳实践.md
last_updated: 2026-04-15
status: authoritative
---

# Continuation 机制

当 Actor 发起**异步操作**（跨 Actor 调用、Runner 任务、Timer）时，Python 函数需"挂起"并在结果回来后"恢复"。Cowboy 用 **Continuation**（基于 Checkpoint）实现。

---

## 两类场景

1. **Actor ↔ Actor**: 同步 `call_actor` 立即返回（在调用栈内）。异步场景用 `send_message` + handler 模式，或显式 checkpoint。
2. **Actor ↔ Runner**: `submit_job` 返回 handle，actor 挂起到 checkpoint；Runner 结果回来后作为 deferred tx 触发 resume。

---

## Checkpoint 层次

| 级别 | 粒度 |
|---|---|
| **Function-level (F-checkpoint)** | 在函数的特定指令位置保存局部变量 + 指令指针 |
| **Block Stack** | 保留 `try/finally/loop` 嵌套上下文，恢复后异常处理仍正确 |

API:
- `save_checkpoint(state_dict)` / `load_checkpoint()`
- File-based: Checkpoint 序列化到 Actor 存储的保留 key

---

## FSM 编译形态

SDK 可将异步 Python 代码编译为显式状态机（每 `await` 边界作为 state 转移）。Compile-time 约束：
- 所有 await 点必须是已知跨 Actor / Runner / Timer 调用
- 非 deterministic branching（随机、系统调用）禁用

---

## 序列化

Continuation state 使用 **CBOR Canonical**。避免 pickle（任意代码执行风险）。

Schema 定义在 `cip-6-sdk.md` 和 `refs/pvm/02-功能设计与Continuation.md`。

---

## Guard 机制

Checkpoint 恢复时校验：
- Actor code hash 未变（否则 checkpoint 无效，需迁移）
- Continuation 年龄不超过上限（避免 zombie）

---

## 相关
- [[../entities/pvm]] — 执行环境支持
- [[actor-model]] — 消息驱动基础
- [[timer-mechanism]] — Timer resume 路径

## Sources
- `refs/pvm/02-功能设计与Continuation.md`
- `refs/pvm/03-Checkpoint-Resume实现指南.md`
- `refs/pvm/04-编码规范与最佳实践.md` §Checkpoint 使用规范
- `refs/cips/cip-6-sdk.md` — SDK 层 Continuation API
