> [!WARNING]
> **主要 Gap 已修复 (Primary Gap Resolved)**
> 本报告撰写于 2026-03-03，其核心发现已不再成立：
>
> - **§2.1 Synchronous Call Primitive**（被标为 "CRITICAL GAP"）：`call_actor` 已在
>   `node/execution/src/pvm_host.rs` 中完整实现，包含 `sync_called_actors` 跨 Actor 状态追踪、
>   `ActorCallSnapshot` 回滚机制、同步调用深度计数器，完全支持 T+0 原子嵌套调用。
>
> 其余内容（如具体测试建议）仅供参考，以实际代码为准。

# Cowboy Node & Runner Implementation Gap Analysis Report

**Date:** 2026-03-03
**References:**
- `refs/cips/cip-6-sdk.md` (CIP-6: Python SDK & Actor API)
- `refs/202602/20260216_cowboy_whitepaper.md` (Cowboy Technical Whitepaper)
- Codebase: `node/chain`, `node/pvm`, `runner`

## 1. Executive Summary

This report identifies discrepancies between the current codebase implementation and the design specifications outlined in CIP-6 and the Cowboy Whitepaper.

**Key Finding:** The **Synchronous Call Primitive (`call`)**, a fundamental component of the Actor Model described in CIP-6, is **completely missing** from the underlying Rust Host API and PVM Runtime, rendering the `call()` function in the Python SDK non-functional.

Other features such as `send()` (asynchronous messaging), Native Timers, and Token Standard (CIP-20) host functions are implemented.

## 2. Detailed Gap Analysis

### 2.1. Synchronous Call Primitive (`call`) - **CRITICAL GAP**

*   **Specification (CIP-6)**: Defines `call(target, method, args, cycles_limit)` as a T+0 synchronous, atomic execution primitive. It allows an actor to invoke a method on another actor within the same transaction, sharing the call stack and rollback context.
*   **Python SDK (`node/pvm/Lib/cowboy_sdk/call.py`)**: Implements the `call()` function which attempts to invoke `pvm_host.call_actor(...)`.
*   **Rust Implementation**:
    *   **Host API (`node/chain/src/pvm_host.rs`)**: The `HostApi` trait and `CowboyHost` struct **do not implement** `call_actor` or any equivalent synchronous call method.
    *   **PVM Runtime (`node/pvm/crates/pvm-runtime/src/module.rs`)**: The `pvm_host` module exposed to Python **does not export** a `call_actor` function.
*   **Impact**: Any attempt to use `call()` in the Python SDK will result in a runtime `AttributeError` or similar failure. This blocks the development of any atomic multi-actor interactions (e.g., atomic swaps, synchronous queries).

### 2.2. Asynchronous Message Primitive (`send`) - **IMPLEMENTED**

*   **Specification (CIP-6)**: Defines `send(target, payload)` as a T+N fire-and-forget asynchronous message primitive.
*   **Python SDK (`node/pvm/Lib/cowboy_sdk/send.py`)**: Calls `pvm_host.send_message(...)`.
*   **Rust Implementation**:
    *   `CowboyHost::send_message` is implemented in `node/chain/src/pvm_host.rs`.
    *   It queues messages in `outgoing_messages` for later processing.
    *   It is correctly exposed to Python in `pvm-runtime`.
*   **Status**: Aligned with specification.

### 2.3. Await Continuation & Runner Integration - **PARTIALLY IMPLEMENTED**

*   **Specification (CIP-6)**: Describes `await continuation` for Actor-to-Actor and Runner interactions, relying on FSM (Finite State Machine) compilation to handle suspension and resumption without blocking the chain.
*   **Python SDK**:
    *   `cowboy_sdk.runner` and `cowboy_sdk.continuation` provide the decorators and logic for FSM compilation (`_compiler.compile_continuation`).
    *   However, `cowboy_sdk.runner` also contains fallback logic for `checkpoint` mode (using `rustpython_checkpoint`), which suggests the FSM implementation might be transitional or the runtime supports both modes.
*   **Rust Implementation**:
    *   `CowboyHost::submit_job` is implemented to send jobs to the `Job Dispatcher`.
    *   `CowboyHost::create_deferred_tx` is implemented to allow self-continuation.
*   **Observation**: The core mechanisms (FSM compiler + `submit_job`/`deferred_tx`) seem to be in place, but the reliance on `checkpoint` in `runner.py` for some paths warrants verification.

### 2.4. Token Standard (CIP-20) - **IMPLEMENTED**

*   **Specification**: The Whitepaper and codebase comments refer to "Phase 2" Token Registry support.
*   **Rust Implementation**: `CowboyHost` implements a comprehensive set of token host functions:
    *   `token_create`, `token_transfer`, `token_transfer_from`, `token_approve`
    *   `token_balance_of`, `token_allowance`, `token_total_supply`
    *   `token_mint`, `token_burn`
*   **Python SDK**: These are exposed in `pvm-runtime` and likely wrapped in a `cowboy_sdk.token` module (not checked in detail, but host support is present).
*   **Status**: Implemented.

### 2.5. Native Timers - **IMPLEMENTED**

*   **Specification (Whitepaper)**: Native timers for self-scheduling.
*   **Rust Implementation**: `CowboyHost::schedule_timer` and `cancel_timer` are implemented and exposed.
*   **Status**: Implemented.

### 2.6. Runner Address Alignment

*   **Python SDK**: `Address.JOB_DISPATCHER` is defined as `0x00...02`.
*   **Rust Implementation**: `CowboyHost::submit_job` sends to `SystemActorAddresses::job_dispatcher()`. (Assumed to match `0x02` based on standard system actor address assignment).
*   **Status**: Likely aligned (requires verifying `SystemActorAddresses` definition in `runner-common`).

## 3. Recommendations & Action Items

1.  **Implement `call_actor` (High Priority)**:
    *   Extend `HostApi` trait in `pvm_host` crate to include `call_actor`.
    *   Implement `call_actor` in `CowboyHost` (node/chain). This is complex as it requires recursive PVM execution or a re-entrant VM architecture to handle the synchronous call stack within the same transaction context.
    *   Expose `call_actor` in `pvm-runtime`'s `module.rs`.

2.  **Verify FSM Compiler**:
    *   Ensure the `_compiler.py` in `cowboy_sdk` is fully functional and does not rely on the deprecated `checkpoint` mode for production chains.

3.  **Documentation Update**:
    *   If `call()` cannot be implemented immediately due to architectural constraints, update CIP-6 to reflect its absence or alternative (e.g., using `await` for everything).

4.  **Testing**:
    *   Create a test case that specifically uses `call()` to confirm the failure and verify the fix once implemented.
