# Cowboy Node & Runner 实现差距分析报告

**日期:** 2026-03-03
**参考文档:**
- `refs/cips/cip-6-sdk.md` (CIP-6: Python SDK & Actor API)
- `refs/202602/20260216_cowboy_whitepaper.md` (Cowboy 技术白皮书)
- 代码库: `node/chain`, `node/pvm`, `runner`

## 1. 执行摘要

本报告指出了当前代码库实现与 CIP-6 和 Cowboy 白皮书设计规范之间的差异。

**核心发现:** **同步调用原语 (`call`)**，作为 CIP-6 中 Actor 模型的基础组件，在底层的 Rust Host API 和 PVM Runtime 中 **完全缺失**，导致 Python SDK 中的 `call()` 函数无法正常工作。

其他功能如 `send()` (异步消息)、原生定时器 (Native Timers) 和代币标准 (CIP-20) 的宿主函数已实现。

## 2. 详细差距分析

### 2.1. 同步调用原语 (`call`) - **严重缺失**

*   **规范 (CIP-6)**: 定义 `call(target, method, args, cycles_limit)` 为 T+0 同步原子执行原语。允许一个 Actor 在同一交易中调用另一个 Actor 的方法，共享调用栈和回滚上下文。
*   **Python SDK (`node/pvm/Lib/cowboy_sdk/call.py`)**: 实现了试图调用 `pvm_host.call_actor(...)` 的 `call()` 函数。
*   **Rust 实现**:
    *   **Host API (`node/chain/src/pvm_host.rs`)**: `HostApi` trait 和 `CowboyHost` 结构体 **未实现** `call_actor` 或任何等效的同步调用方法。
    *   **PVM Runtime (`node/pvm/crates/pvm-runtime/src/module.rs`)**: 暴露给 Python 的 `pvm_host` 模块 **未导出** `call_actor` 函数。
*   **影响**: 任何在 Python SDK 中使用 `call()` 的尝试都会导致运行时 `AttributeError` 或类似错误。这阻碍了任何原子多 Actor 交互（如原子交换、同步查询）的开发。

### 2.2. 异步消息原语 (`send`) - **已实现**

*   **规范 (CIP-6)**: 定义 `send(target, payload)` 为 T+N "发后即忘" (fire-and-forget) 的异步消息原语。
*   **Python SDK (`node/pvm/Lib/cowboy_sdk/send.py`)**: 调用 `pvm_host.send_message(...)`。
*   **Rust 实现**:
    *   `CowboyHost::send_message` 在 `node/chain/src/pvm_host.rs` 中已实现。
    *   它将消息排队到 `outgoing_messages` 以便稍后处理。
    *   已在 `pvm-runtime` 中正确暴露。
*   **状态**: 符合规范。

### 2.3. Await Continuation & Runner 集成 - **部分实现**

*   **规范 (CIP-6)**: 描述 `await continuation` 用于 Actor-to-Actor 和 Runner 交互，依赖 FSM (有限状态机) 编译来处理挂起和恢复，而不阻塞链。
*   **Python SDK**:
    *   `cowboy_sdk.runner` 和 `cowboy_sdk.continuation` 提供了 FSM 编译 (`_compiler.compile_continuation`) 的装饰器和逻辑。
    *   然而，`cowboy_sdk.runner` 包含用于 `checkpoint` 模式的回退逻辑 (使用 `rustpython_checkpoint`)，这表明 FSM 实现可能是过渡性的，或者运行时同时支持这两种模式。
*   **Rust 实现**:
    *   `CowboyHost::submit_job` 已实现，用于向 `Job Dispatcher` 发送作业。
    *   `CowboyHost::create_deferred_tx` 已实现，允许自我延续 (self-continuation)。
*   **观察**: 核心机制 (FSM 编译器 + `submit_job`/`deferred_tx`) 似乎已就位，但 `runner.py` 中某些路径对 `checkpoint` 的依赖需要验证。

### 2.4. 代币标准 (CIP-20) - **已实现**

*   **规范**: 白皮书和代码库注释提到 "Phase 2" 代币注册表支持。
*   **Rust 实现**: `CowboyHost` 实现了一套全面的代币宿主函数:
    *   `token_create`, `token_transfer`, `token_transfer_from`, `token_approve`
    *   `token_balance_of`, `token_allowance`, `token_total_supply`
    *   `token_mint`, `token_burn`
*   **Python SDK**: 这些已在 `pvm-runtime` 中暴露，并可能封装在 `cowboy_sdk.token` 模块中（未详细检查，但宿主支持已存在）。
*   **状态**: 已实现。

### 2.5. 原生定时器 (Native Timers) - **已实现**

*   **规范 (白皮书)**: 用于自我调度的原生定时器。
*   **Rust 实现**: `CowboyHost::schedule_timer` 和 `cancel_timer` 已实现并暴露。
*   **状态**: 已实现。

### 2.6. Runner 地址对齐

*   **Python SDK**: `Address.JOB_DISPATCHER` 定义为 `0x00...02`。
*   **Rust 实现**: `CowboyHost::submit_job` 发送到 `SystemActorAddresses::job_dispatcher()`。(基于标准系统 Actor 地址分配，假定匹配 `0x02`)。
*   **状态**: 可能对齐 (需要验证 `runner-common` 中的 `SystemActorAddresses` 定义)。

## 3. 建议与行动项

1.  **实现 `call_actor` (高优先级)**:
    *   在 `pvm_host` crate 的 `HostApi` trait 中扩展 `call_actor`。
    *   在 `CowboyHost` (node/chain) 中实现 `call_actor`。这比较复杂，因为它需要在同一交易上下文中处理递归 PVM 执行或重入 VM 架构。
    *   在 `pvm-runtime` 的 `module.rs` 中暴露 `call_actor`。

2.  **验证 FSM 编译器**:
    *   确保 `cowboy_sdk` 中的 `_compiler.py` 功能完备，并且生产链不依赖已弃用的 `checkpoint` 模式。

3.  **文档更新**:
    *   如果由于架构限制无法立即实现 `call()`，请更新 CIP-6 以反映其缺失或替代方案（例如，全部使用 `await`）。

4.  **测试**:
    *   创建一个专门使用 `call()` 的测试用例，以确认故障并在实现后验证修复。
