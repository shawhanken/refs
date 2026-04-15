# PVM 跨 Actor 调用链路会话改造汇总（2026-03）

## 1. 背景与目标

本次会话围绕 `chain/src/pvm_host.rs`、`chain/src/pvm_executor.rs`、`chain/src/execution.rs` 的调用链路稳定性与可维护性持续改造，核心目标：

- 修复嵌套跨 Actor 调用时的执行器嵌套问题与栈风险；
- 确保失败路径回滚语义正确；
- 将 `call_actor` 从“混合业务+恢复细节”重构为“以编排为主”的结构；
- 在不改变业务语义前提下，逐步抽离重复逻辑为 helper / guard。

---

## 2. 关键问题与根因

### 2.1 执行器嵌套冲突

现象：

- 嵌套调用测试中出现 `cannot execute LocalPool executor from within another executor: EnterError`；
- 某些场景曾触发栈溢出。

根因：

- 旧路径中同步 Host API 内部通过 `block_on` 驱动异步逻辑，存在执行器重入风险；
- `call_actor` 逻辑分支多、恢复点分散，错误分支容易放大复杂度。

### 2.2 可维护性问题

`call_actor` 早期存在以下问题：

- 自调用/跨调用分支重复执行样板；
- 上下文切换与恢复散落在主流程；
- depth 与 cycles 子限额恢复需要手工维护；
- 入参校验、地址解析等细节混在主流程中。

---

## 3. 改造与升级清单

### 3.1 执行模型调整

- `PvmExecutor::execute_handler` 由 `async fn` 调整为同步函数；
- `execution.rs` 对应调用点移除 `.await`，调用链路与同步 Host 保持一致；
- `pvm_host.rs` 内对 Actor 查询改为统一同步桥接执行。

收益：

- 消除执行器嵌套进入风险；
- 降低 Host API 内部异步耦合。

### 3.2 测试路径恢复与稳定化

- 恢复并启用嵌套回滚测试；
- 移除测试内临时 `run_async` 包装，统一采用明确执行路径；
- 为深调用测试提供更稳定执行环境（避免测试线程栈不足导致误报）。

收益：

- 嵌套失败回滚路径可重复验证；
- 关键回归测试可稳定通过。

### 3.3 同步桥接收口

- 新增统一同步桥接能力（复用 runtime），避免每次查询重复构建 runtime；
- 新增 `get_actor_for_call` 收口“先查 sync cache，再查 store，再映射错误”的逻辑。

收益：

- 降低重复代码与运行时开销；
- 错误语义集中，后续改动更安全。

### 3.4 `call_actor` 渐进重构（重点）

本次会话持续做了多轮结构化重构，最终将主流程收敛为编排层：

1. **执行样板收口**
   - 新增 `execute_current_handler`，统一 handler 执行与错误映射。

2. **上下文切换收口**
   - 新增 `ActorCallSnapshot`；
   - 新增 `capture_call_snapshot` / `switch_to_callee` / `restore_call_snapshot`。

3. **作用域守卫收口**
   - 新增 `CallScopeGuard`；
   - 统一管理 `call_depth` 与 cycles 子限额 push/restore，消除手工早退恢复。

4. **跨调用提交收口**
   - 新增 `commit_cross_call_result`；
   - 成功时统一执行 `apply_to_actor + sync_called_actors`。

5. **入参与解析收口**
   - 新增 `validate_call_actor_inputs`；
   - 新增 `parse_call_target`。

6. **分支模板合并**
   - 自调用/跨调用统一为“可选切换 -> 单次执行 -> 可选提交/恢复”的模板。

收益：

- 主流程明显变短；
- 状态恢复点减少，异常路径更清晰；
- 语义保持不变但可读性、可维护性显著提升。

---

## 4. 语义保持说明

改造后保持以下行为不变：

- `target` 非 20 字节或 `method` 为空仍返回 `InvalidInput`；
- 调用深度超过上限仍返回 `Forbidden`；
- 跨调用找不到 Actor 仍返回 `NotFound`；
- 跨调用 store 异常仍映射 `StorageError`；
- 跨调用失败不提交 callee 缓存变更；
- 跨调用成功才提交 callee 变更并写入 `sync_called_actors`；
- 调用结束后 depth 与 cycles 子限额恢复。

---

## 5. 验证与结果

会话期间多轮执行并重复验证以下命令，结果稳定：

- `cargo test -p cowboy-chain test_execute_actor_nested_call_failure_rolls_back_both_actors` ✅
- `cargo test -p cowboy-chain test_execute_actor_failure_rolls_back_actor_and_sender_state` ✅
- `cargo test -p cowboy-chain test_execute_system_transfer_success_updates_balances_and_nonce` ✅
- `cargo check -p cowboy-chain` ✅

静态检查现状：

- `cargo clippy -p cowboy-chain --no-deps` 存在仓库既有问题（非本次引入）：
  - `chain/src/genesis_migration.rs:33`

---

## 6. 会话产出总结

本次并非一次性大改，而是“可运行 -> 可验证 -> 可维护”的连续迭代重构：

- 先修稳定性（执行器重入与回滚测试）；
- 再收口同步桥接与执行入口；
- 再收口上下文切换、作用域恢复、提交逻辑、入参解析；
- 最终使 `call_actor` 从复杂状态机式代码演化为清晰编排层代码。

该改造路径可作为后续 Host 侧复杂函数重构模板复用。
