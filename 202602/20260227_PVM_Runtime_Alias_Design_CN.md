# PVM Host 封装与 `cowboy_sdk.runtime` 设计方案

> **状态**: 草稿  
> **作者**: Cowboy 核心团队  
> **创建日期**: 2026-02-27  
> **适用范围**: PVM Host API、`cowboy_sdk`、示例合约 (`node/examples/llm_chat*`)

---

## 1. 背景与问题

当前链上 Actor 直接通过 Python 模块 `pvm_host` 访问 PVM 宿主接口：

- 状态读写: `pvm_host.get_state/set_state`
- 执行上下文: `pvm_host.context()`
- gas 计费: `pvm_host.charge_gas(...)`
- 事件与消息: `pvm_host.emit_event(...)` / `pvm_host.send_message(...)` / `pvm_host.submit_job(...)`

问题：

- 对普通合约开发者来说，`pvm_host` 命名抽象且偏底层，不易理解其职责边界。
- 业务代码直接依赖 Host API，未来 PVM / Host 演进时，迁移成本高。
- `cowboy_sdk` 已经提供了较高层的抽象（`@actor`、`self.storage`、continuation、`CowboyModel` 等），但 Host 能力没有统一通过 SDK 暴露。

目标：

- 让**绝大多数业务合约不再直接 import `pvm_host`**，而是通过 `cowboy_sdk` 访问链上运行时。
- 保留 `pvm_host` 作为底层实现与高级用法的“逃生口”，但不鼓励在业务层直接依赖。

---

## 2. 设计目标

- **语义清晰**: 通过 `cowboy_sdk.runtime` 这一入口，表达“当前链上执行环境 / 运行时”的概念。
- **向后兼容**: 现有使用 `pvm_host` 的合约在过渡期内仍然可用；新代码与示例优先使用 `runtime`。
- **可演进**: Host API 未来新增字段或调整行为时，可以在 `runtime` 层统一适配，尽量避免破坏业务合约。
- **职责收口**: 除极少数桥接模块外，`cowboy_sdk` 内部也逐步从直接 import `pvm_host` 迁移到通过 `runtime` 访问运行时。

---

## 3. 模块分层与命名

### 3.1 底层: `pvm_host`

- 职责: PVM 宿主接口的真实实现，直接由链与虚拟机提供。
- 能力示例:
  - `get_state(key: bytes) -> bytes | None`
  - `set_state(key: bytes, value: bytes) -> None`
  - `context() -> dict`
  - `charge_gas(amount: int) -> None`
  - `emit_event(name: str, payload: bytes) -> None`
  - `send_message(target: bytes, payload: bytes) -> None`
  - `submit_job(payload: bytes) -> None`
  - `current_block() -> int`（若存在）
  - `self_address() -> bytes`（若存在）
- 面向对象: 仅限
  - PVM 自身实现
  - `cowboy_sdk` 内部桥接层
  - 测试与高级调试场景

### 3.2 中间层: `cowboy_sdk.runtime`

- 职责: 对 Host API 做语义化与稳定化包装，是**业务合约访问运行时的推荐入口**。
- 命名语义: `runtime` = “当前链上执行环境 / 运行时”，避免 `host` 和 “远程主机” 等歧义。
- 与现有 `cowboy_sdk.runtime` 功能合并：
  - 保留原有运行时模式检测 (`mode()/is_production()/is_checkpoint_mode()` 等)；
  - 新增 Host API 封装函数。

### 3.3 上层: 业务合约与高级抽象

- 通过 `cowboy_sdk` 顶层 API 使用:
  - `@actor`、`self.storage`
  - continuation (`@runner.continuation`, `capture`)
  - `CowboyModel` / `SoftFloat` / `Verify` / `guards` 等
- 与运行时交互统一通过 `runtime`:

```python
from cowboy_sdk import actor, runtime
```

---

## 4. `cowboy_sdk.runtime` API 设计

### 4.1 保留的运行时模式检测

保持现有接口不变：

- `runtime.mode() -> str` : `"fsm" | "checkpoint" | "local"`
- `runtime.is_production() -> bool`
- `runtime.is_development() -> bool`
- `runtime.is_checkpoint_mode() -> bool`
- `runtime.require_fsm() -> None`
- `runtime.get_pvm_version() -> str`
- `runtime.get_chain_id() -> int`

这些用于区分链上 FSM 生产模式、本地开发模式与 checkpoint 调试模式。

### 4.2 新增 Host API 封装（第一阶段）

统一从 `pvm_host` 读取上下文与链信息：

- **执行上下文**
  - `runtime.context() -> dict`
    - 直接转发 `pvm_host.context()`。
  - `runtime.get_sender() -> bytes`
    - 优先从 `context()['sender']` 返回 20 字节地址（保持与现有 `pvm_sys` 约定一致）。
  - `runtime.get_actor_address() -> bytes`
    - 若存在 `pvm_host.self_address()` 则优先使用，否则回退到 `context()['actor_addr']`。
  - `runtime.get_tx_hash() -> bytes`
  - `runtime.get_block_height() -> int`
  - `runtime.get_timestamp_ms() -> int`

- **gas 计费**
  - `runtime.charge_gas(amount: int) -> None`
    - 简单转发 `pvm_host.charge_gas(amount)`，保留错误语义。

- **事件**
  - `runtime.emit_event(name: str, payload: bytes | str | dict) -> None`
    - 若传入 `dict` 或 `str`，在内部统一做 `json.dumps(...).encode("utf-8")`，减少样板代码。
    - 若传入 `bytes`，则直接转发。

- **状态访问（逃生口）**
  - `runtime.get_state(key: bytes) -> bytes | None`
  - `runtime.set_state(key: bytes, value: bytes) -> None`
  - 说明文档中强调：**业务代码优先使用 `self.storage` / `CowboyModel`，这里仅用于特殊场景或迁移过渡。**

- **消息与 Runner Job（按现有 Host 能力暴露）**
  - `runtime.send_message(target: bytes, payload: bytes) -> None`
  - `runtime.submit_job(payload: bytes) -> None`

> 备注：以上函数的精确签名以现有 `pvm_host` 实现为准，本方案只定义职责与封装原则。

---

## 5. 代码迁移策略

### 5.1 SDK 内部

第一阶段（本次改动）：

- 在 `cowboy_sdk.runtime` 中新增对 `pvm_host` 的封装实现；
- 将以下模块的运行时访问逐步改为通过 `runtime`：
  - `cowboy_sdk.pvm_time`（时间与区块高度）；
  - 未来可以考虑在合适时机调整 `pvm_sys` 等模块。

第二阶段（后续迭代）：

- 评估 `cowboy_sdk` 其他子模块中对 `pvm_host` 的直接引用（如 `_compiler.py` 内部代码生成），在不影响性能与可读性的前提下，通过 `runtime` 做统一封装或保持最小直连。

### 5.2 示例合约与文档

本次改动重点覆盖示例：

- `node/examples/llm_chat/llm_actor.py`
  - 将 `import pvm_host` 替换为 `from cowboy_sdk import runtime`；
  - 所有 `pvm_host.charge_gas/context/emit_event/submit_job` 等调用替换为 `runtime` 对应函数；
  - 保持状态读写逻辑不变（仍然使用 `get_state/set_state` + 手工 JSON），作为“低层风格”示例。

- `node/examples/llm_chat2/llm_actor2.py`
  - 将 `import pvm_host` 替换为 `from cowboy_sdk import runtime`；
  - 使用 `runtime.charge_gas/context/emit_event` 等 API；
  - 继续展示基于 `@actor` + `self.storage` + `CowboyModel` 的“高层风格”写法。

文档与说明：

- 在示例顶部文档字符串中增加一句：
  - “本示例通过 `cowboy_sdk.runtime` 访问链上运行时，不直接 import `pvm_host`。”
- 在 SDK 文档中，将 `runtime` 作为推荐入口展示，并弱化对 `pvm_host` 的直接说明。

---

## 6. 兼容性与风险评估

- **向后兼容**
  - 现有 `pvm_host` 模块保持不变；
  - 旧合约中 `import pvm_host` 仍然可用；
  - 新增的 `cowboy_sdk.runtime` 仅作为封装与推荐入口，不更改底层行为。

- **行为一致性**
  - 所有 `runtime` API 在第一阶段只是简单转发或带轻量编码处理（如 `emit_event` 的 JSON 编码），不改变 Host 语义；
  - 对事件 payload 的自动 JSON 编码会在函数文档中明确说明，以避免误用。

- **演进空间**
  - 未来可以在 `runtime` 中：
    - 对 sender/actor_addr/tx_hash 等返回值增加类型封装（如返回 `Address` 类型）；
    - 增加额外的安全检查（例如对 gas 数量、payload 大小做上限约束），作为可选守卫；
    - 引入统计与调试钩子，而不污染业务代码。

---

## 7. 落地计划

1. **实现阶段**
   - 扩展 `cowboy_sdk.runtime`，加入 Host API 封装；
   - 更新 `pvm_time` 等内部模块使用 `runtime`。
2. **示例迁移**
   - 修改 `llm_chat/llm_actor.py` 与 `llm_chat2/llm_actor2.py`，统一通过 `runtime` 访问运行时；
   - 检查并更新相关 README / 注释说明。
3. **文档与标准化**
   - 在开发文档中增加 “推荐：使用 `cowboy_sdk.runtime` 而非 `pvm_host`” 的章节；
   - 在新模板/脚手架中默认使用 `runtime`。
4. **后续迭代（可选）**
   - 逐步审查 `cowboy_sdk` 内其他直连 `pvm_host` 的位置，评估是否需要通过 `runtime` 收口；
   - 根据主网反馈与合约生态情况，考虑是否在未来版本中弱化或隐藏 `pvm_host` 的公共文档曝光度。

