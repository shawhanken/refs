---
type: entity
tags: [pvm, actor-code, determinism]
sources:
  - refs/pvm/01-API参考与使用指南.md
  - refs/pvm/02-功能设计与Continuation.md
  - refs/pvm/03-Checkpoint-Resume实现指南.md
  - refs/pvm/04-编码规范与最佳实践.md
  - refs/pvm/05-测试评估与升级.md
last_updated: 2026-04-15
status: authoritative
---

# PVM — Python Virtual Machine

Cowboy 的 Actor 执行环境：基于 RustPython 的确定性 Python 运行时。Actor 代码用 Python 编写，编译后由 PVM 执行。

**位置**: `/home/ubuntu/workspace/node/pvm/`（独立 Rust workspace，workspace-excluded）

**核心**: `pvm-host`（host API 绑定）+ `pvm-runtime`（Python 解释器）

---

## 执行入口

主链调用 `PvmExecutor::execute_handler()`：
1. 从 Actor 状态加载代码 + checkpoint（若有）
2. 注入 `INT_GUARD_PREAMBLE`（整数限 4,096 bits）
3. 执行 handler，强制 `max_cycles` 上限
4. 若命中 checkpoint → 保存 continuation 状态
5. 返回 `GasReport`（cycles + cells 分类统计）

**源**: `node/execution/src/pvm_executor.rs`、`node/execution/src/pvm_host.rs`

---

## Host API（Python → Rust）

- `state_get(key) / state_set(key, value)` — Actor 本地 KV 存储
- `send_message(addr, payload)` — 异步发消息
- `call_actor(addr, method, args)` — 同步跨 Actor 调用（最深 32 层）
- `submit_job(...)` — 发起链下计算（Runner）
- `schedule_timer(height, callback, gas)` — GBA timer 注册（[[../concepts/timer-mechanism]]）
- CIP-20 Token ops（mint / transfer / burn / freeze / permit / hook）

每个 host 调用扣 cycles（Compute）与 cells（Data），见 [[../parameters]]。

`ActorStorageCache` 追踪 read_count，PVM 执行结束后批量按 `STORAGE_READ_CYCLES` 补扣。

---

## 确定性约束

Actor 代码加载前 `validate_actor_code()` 检查：

| 约束 | 处理 |
|---|---|
| UTF-8 编码 | 非 UTF-8 拒绝 |
| `asyncio.gather` | 静态扫描拒绝（非确定性并发）|
| 静态整数字面量 > 1234 digits | 拒绝 |
| 导入黑名单 `ctypes/_ctypes/cffi/_cffi_backend` | 拒绝 |
| `INT_GUARD_PREAMBLE` 注入 | 替换 `builtins.int` 为 `_GuardedInt`（上限 4,096 bits）|

**已知限制**: 裸字面量 `2**10000` 在 VM 字节码路径绕过 guard；完整 VM 级强制推迟到后续版本。

---

## Continuation / Checkpoint

详见 [[../concepts/continuation]]。PVM 支持：
- 函数级 Checkpoint（F-checkpoint）
- Block Stack Checkpoint（try/finally/loop 嵌套保留）
- Checkpoint File/Bytes API

序列化：**CBOR Canonical**（不使用 pickle，避免任意代码执行）。

---

## 完成度状态

**自评**: 35-40%（见 `refs/pvm/05-测试评估与升级.md`、`2026-01-24_PVM_REAL_COMPLETENESS_ASSESSMENT.md`）

**测试**: ~124 个单元/集成测试（pvm 自身 workspace）

> ⚠ 上述数字记于 2026-01-24，头部 warning 明示"严重过时"。最新状态以 `refs/node/02-实施与技术实现.md` 及 `pvm/` 代码为准。

---

## SDK Alias

`cowboy_sdk` Python 包对 Host API 做 Python 化封装（类、装饰器），详见：
- `refs/pvm/2026-02-27_PVM_Runtime_Alias_Design_CN.md`
- `refs/cips/cip-6-sdk.md`

---

## 相关
- [[../concepts/actor-model]]
- [[../concepts/continuation]]
- [[../concepts/dual-gas-model]]
- [[node]]

## Sources
- `refs/pvm/01` - `05-*.md` — 5 篇综合文档
- `refs/pvm/2026-01-24_PVM_IMPLEMENTATION_PLAN.md`、`PVM_REAL_COMPLETENESS_ASSESSMENT.md`
- `refs/pvm/2026-01-27_SOFTFLOAT_PERFORMANCE.md` / `SOFTFLOAT_TESTING.md` — 确定性浮点
- `refs/pvm/2026-02-27_PVM_Runtime_Alias_Design_CN.md`
- `refs/pvm/2026-03-04_pvm-call-actor-session-upgrade-summary.md`
- workspace `node/pvm/crates/pvm-host/`、`pvm-runtime/`
- workspace `node/execution/src/pvm_executor.rs`、`pvm_host.rs`
