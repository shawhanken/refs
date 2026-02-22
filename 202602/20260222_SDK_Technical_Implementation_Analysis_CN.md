# Cowboy SDK (`cowboy_sdk`) 技术实现路径分析

**日期**: 2026-02-22
**版本**: v2 (修订版)
**状态**: 技术规划
**范围**: CIP-6 SDK 规范 vs 现有代码实现对比，完整实现路径
**原则**: 立足长远，消除隐患，不做短视妥协

---

## 零、修订说明

本版本（v2）相对于初版做出以下根本性修正：

| 初版决策 | 问题 | v2 修正 |
|---------|------|--------|
| 包名 `pvm_sdk`→`cowboy_sdk` 推迟到 Phase 4 | 每一天的延迟都在累积迁移债务 | **Phase 0 第一步**完成重命名 |
| 序列化"短期保持 JSON，中期迁 CBOR" | JSON 格式的存量 Continuation 状态在 CBOR 切换后不可读，造成链上数据断裂 | **从第一天起使用 CBOR**，通过 Host API 暴露 Rust 侧 CBOR 编解码 |
| "Checkpoint 为默认，FSM 作为优化路径" | Checkpoint 捕获整个 Python 执行栈，快照体积大、含运行时内部状态、跨版本不兼容 | **FSM 为唯一的链上生产路径**；Checkpoint 仅用于本地开发调试，不进入共识 |
| Guard 校验推迟到 Phase 1 | 没有 Guard 的 Continuation = 没有安全带的汽车；一旦有开发者基于无 Guard 的 SDK 部署合约，后续修补成为破坏性变更 | Guard 校验与 Continuation **同步交付**，不分离 |
| 安全机制 (`reentrancy_guard`, `bounded_loop`, `capture` 类型检查) 标为 P1/P2 | 安全机制不是"优化"，是基础设施；主网前缺少这些机制会导致真实攻击面 | 全部提升为 **P0**，与对应功能同步交付 |
| 确定性测试放在 Phase 4 | 非确定性 bug 越晚发现修复成本越高，可能导致链分叉 | **每个 Phase 自带确定性测试**，CI 强制执行 |
| 按水平层（原语层→Continuation→类型→异步→测试）切分 | 各层耦合紧密，横切导致半成品无法独立验证 | **按垂直切片**推进，每个 Phase 交付端到端可验证的完整功能 |
| SoftFloat 是 `str` 包装器 | `SoftFloat("0.5") > SoftFloat("0.3")` 做的是字符串比较，得到错误结果 `True`（"5" > "3" 恰好对但 "0.9" > "0.10" 就不对） | SoftFloat 必须对接 PVM 层的 softfloat 算术，或**直接使用 PVM 全局 float 替换** |

---

## 一、架构全景

### 1.1 四层架构

```
┌────────────────────────────────────────────────────────────────┐
│  开发者代码层 (Developer Code)                                  │
│  from cowboy_sdk import actor, call, send, runner, capture     │
│  @actor class MyAgent: ...                                     │
├────────────────────────────────────────────────────────────────┤
│  cowboy_sdk (Python)                                           │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐ │
│  │ call.py │ │ send.py │ │runner.py │ │actor.py│ │verify.py│ │
│  └─────────┘ └─────────┘ └──────────┘ └────────┘ └─────────┘ │
│  ┌──────────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐   │
│  │continuation  │ │ guards   │ │types   │ │ models       │   │
│  └──────────────┘ └──────────┘ └────────┘ └──────────────┘   │
├────────────────────────────────────────────────────────────────┤
│  pvm_host (Rust → Python 绑定)                                 │
│  send_message │ call_actor │ get/set/delete_state │ context   │
│  randomness │ emit_event │ cbor_encode/decode │ keccak256    │
│  set_timer │ cancel_timer │ self_address │ transfer           │
├────────────────────────────────────────────────────────────────┤
│  PVM Runtime (Rust: pvm-runtime + RustPython)                  │
│  确定性执行 │ FSM 编译器 │ SoftFloat │ 模块白名单 │ Gas 计量   │
├────────────────────────────────────────────────────────────────┤
│  链核心 (cowboy-chain)                                         │
│  ExecutionEngine │ BlockchainStorage │ Simplex BFT Consensus   │
└────────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计不变量

以下原则是架构级约束，贯穿所有 Phase，**任何实现决策不得违反**：

| # | 不变量 | 违反后果 |
|---|--------|---------|
| I-1 | 所有跨信任边界数据使用 **Canonical CBOR** (RFC 8949) | 链分叉 / 状态不一致 |
| I-2 | SDK 公共 API 名称空间统一为 **`cowboy_sdk`** | 生态碎片化 / 文档矛盾 |
| I-3 | Continuation 的链上生产模式为 **FSM**，状态以 CBOR 显式序列化 | 跨版本不兼容 / 状态膨胀 |
| I-4 | 所有安全机制（Guard、Reentrancy、BoundedLoop、TypeCheck）**与对应功能同步交付** | 攻击面暴露 |
| I-5 | 每个新增功能**自带确定性测试**，CI 跨平台验证 | 非确定性 bug 延迟爆发 |
| I-6 | 浮点运算**全局使用 SoftFloat**（PVM 层替换），SDK 不提供独立的 SoftFloat 类型包装 | 共识分歧 |
| I-7 | SDK 版本号遵循 **语义化版本 (SemVer)**，主网前标记为 `0.x`，公共 API 变更必须显式弃用 | API 断裂 |

---

## 二、现有代码实现状态

### 2.1 Python SDK 层 (`node/pvm/Lib/pvm_sdk/`)

> 注意：当前目录名为 `pvm_sdk`，Phase 0 将重命名为 `cowboy_sdk`。

| 文件 | 功能 | 实现状态 | 完成度 |
|------|------|---------|--------|
| `__init__.py` | SDK 入口、模块导出 | ✅ 已实现 | 90% |
| `continuation.py` | Capture/序列化/Continuation 状态管理 | ⚠️ 基本实现（JSON 序列化，Guard 未校验） | 50% |
| `runner.py` | Runner 任务发送、Awaitable | ⚠️ 部分实现（仅 Checkpoint 模式） | 35% |
| `actor.py` | ActorRef、Actor 间异步调用 | ⚠️ 骨架实现（await 直接抛异常） | 15% |
| `verify.py` | 验证构建器 | ⚠️ 部分实现（3/17 检查器） | 25% |
| `types.py` | PVM 安全类型 | ❌ 存根（`SoftFloat` 是 `str` 子类，无算术能力） | 5% |
| `pvm_random.py` | 确定性随机数 (VRF) | ✅ 完整实现 | 95% |
| `pvm_time.py` | 区块时间 | ✅ 已实现 | 90% |
| `pvm_sys.py` | 系统元数据 | ✅ 已实现 | 90% |
| `runtime.py` | 运行时模式检测 | ✅ 已实现 | 90% |

### 2.2 Rust Host API 层 (`node/chain/src/pvm_host.rs`)

**已暴露给 Python 的 Host API**：

| 方法 | 功能 | 状态 |
|------|------|------|
| `send_message(target, payload)` | 发送消息到目标 Actor | ✅ |
| `get_state(key)` | 读取 Actor 存储 | ✅ |
| `set_state(key, value)` | 写入 Actor 存储 | ✅ |
| `delete_state(key)` | 删除存储键 | ✅ |
| `context()` | 执行上下文 (block_height, sender, tx_hash 等) | ✅ |
| `randomness(domain)` | VRF 确定性随机 | ✅ |
| `runtime_config()` | 运行时配置 | ✅ |
| `emit_event(topic, data)` | 发出事件 | ✅ |
| `call_actor(target, method, args, cycles)` | 同步调用 Actor | ✅ (需验证 Python 绑定) |

**需新增的 Host API** (按 Phase 排列)：

| Host API | 用途 | 所属 Phase | 阻塞功能 |
|----------|------|-----------|---------|
| `cbor_encode(value) → bytes` | Canonical CBOR 编码 | Phase 0 | 所有序列化 |
| `cbor_decode(data) → value` | CBOR 解码 | Phase 0 | 所有反序列化 |
| `keccak256(data) → bytes` | 哈希计算 | Phase 0 | Guard 指纹 |
| `self_address() → bytes` | 当前 Actor 地址 | Phase 0 | ActorRef |
| `current_block() → int` | 当前区块高度 | Phase 0 | BlockHeight |
| `get_balance(addr) → int` | 查询余额 | Phase 1 | 状态查询 |
| `transfer(to, amount)` | 价值转移 | Phase 1 | 原生转账 |
| `set_timer(height, handler, data) → id` | 设置定时器 | Phase 1 | Timeout |
| `cancel_timer(timer_id)` | 取消定时器 | Phase 1 | Timeout 清理 |

### 2.3 PVM Runtime / Runner 系统状态

| 组件 | 状态 | 关键发现 |
|------|------|---------|
| RustPython VM + 确定性子系统 | ✅ 完整 | 模块白名单、固定哈希种子、无 JIT |
| SoftFloat (Rust) | ✅ 56 测试通过 | `vm/src/softfloat.rs`，可全局替换 Python float |
| Continuation - Checkpoint | ✅ 可用 | `rustpython_checkpoint`，仅适合开发调试 |
| Continuation - FSM 编译器 | ⚠️ 骨架 | `codegen/src/pvm_fsm.rs` 存在但不完整 |
| Gas 计量 (Cycles + Cells) | ✅ 完整 | 字节码级 + I/O 边界双计量 |
| Runner (LLM/HTTP/MCP) | ✅ 完整 | 链下执行 + 6 种验证模式 |
| VRF (3 层) | ✅ 33 测试通过 | HKDF + EC-VRF + Threshold-BLS |

---

## 三、差距分析：隐患识别

### 3.1 致命隐患（必须在主网前解决）

| # | 隐患 | 严重程度 | 说明 |
|---|------|---------|------|
| D-1 | **Guard 校验形同虚设** | 🔴 致命 | `save_cont()` 接受 `guard_unchanged` 参数并序列化，但 `load_cont()` 恢复时**完全不做校验**。这意味着跨块期间状态被篡改不会被发现，构成过时状态攻击面 |
| D-2 | **SoftFloat 是假的** | 🔴 致命 | `types.py` 中 `SoftFloat(str)` 没有算术能力。`SoftFloat("0.10") > SoftFloat("0.9")` 返回 `True`（字符串比较 "1" > "0"），这是共识分歧的定时炸弹 |
| D-3 | **序列化格式 (JSON) 违反协议** | 🔴 致命 | CIP-6 和白皮书明确要求 Canonical CBOR。JSON 的浮点精度损失、编码非规范性会导致跨节点状态哈希不一致 |
| D-4 | **Checkpoint 模式进入共识** | 🟡 高 | Checkpoint 快照包含 Python VM 内部状态（栈帧、字节码指针），跨 PVM 版本升级后无法正确恢复，造成链上冻结的 Continuation |
| D-5 | **无 capture() 类型检查** | 🟡 高 | 可以 `ctx.fn = lambda x: x` 捕获闭包，序列化时静默失败或产生非确定性 |
| D-6 | **包名分裂** | 🟡 高 | 代码 `pvm_sdk`，文档 `cowboy_sdk`，开发者无所适从；拖延越久迁移成本越大 |

### 3.2 功能性差距

| CIP-6 功能 | 现状 | 差距类型 |
|-----------|------|---------|
| `call()` 顶层函数 | ❌ 未暴露 | SDK 层缺失 |
| `send()` 顶层函数 | ❌ 未暴露 | SDK 层缺失 |
| `@actor` 装饰器 | ❌ | SDK 层缺失 |
| `@reentrancy_guard` | ❌ | 安全机制缺失 |
| `@bounded_loop` | ❌ | 安全机制缺失 |
| `@actor.continuation` | ⚠️ 骨架 (`__await__` 抛异常) | 功能不可用 |
| `storage.guard()` | ❌ | 安全机制缺失 |
| `Retry` 类 | ❌ | 异步工具缺失 |
| `TaskGroup` | ❌ | 异步工具缺失 |
| `CowboyModel` | ❌ | 类型系统缺失 |
| `ordered_set` | ❌ | 类型系统缺失 |
| `BlockHeight` | ❌ | 类型标注缺失 |
| Verify 检查器 | 3/17 已实现 | 14 个检查器缺失 |
| `runner.mcp()` | ❌ (Rust 侧已实现) | SDK 未暴露 |

---

## 四、CBOR 序列化策略（不变量 I-1）

### 4.1 为什么必须从第一天使用 CBOR

| 场景 | JSON 的问题 | CBOR 的解决 |
|------|-----------|------------|
| 浮点数 | `json.dumps(0.1)` → `"0.1"` 但 `0.1` 在 IEEE 754 中不可精确表示，不同 JSON 库可能序列化为不同精度 | CBOR 强制 64 位 IEEE 754 编码，字节确定 |
| 字节类型 | JSON 无原生 bytes 支持，当前用 `{"__bytes__": hex}` 包装 — 脆弱且非标准 | CBOR 原生 bytes 类型 (major type 2) |
| 映射键排序 | `json.dumps(sort_keys=True)` 按 Unicode 排序，但 CBOR 要求按编码后字节排序 — 两者结果可能不同 | Canonical CBOR 定义明确的键排序 |
| 整数编码 | JSON 所有数字统一文本表示 | CBOR 最短编码（共识关键） |
| 存量数据 | 若先用 JSON 再迁 CBOR，链上已有的 JSON 格式 Continuation 状态无法被 CBOR 解码器读取 | 无此问题 |

### 4.2 实现方案

**方案选择**: 通过 Rust Host API 暴露 CBOR 编解码，不在 Python 侧引入第三方库。

**理由**:
- Rust 侧已有 CBOR 依赖（`serde_cbor` 或类似），代码可复用
- 避免 Python 第三方库 (`cbor2`) 引入确定性风险
- Host API 调用走 Gas 计量，成本可控

**Host API 新增**:
```
pvm_host.cbor_encode(value: any) -> bytes    # Canonical CBOR 编码
pvm_host.cbor_decode(data: bytes) -> any     # CBOR 解码
```

**Python SDK 层**:
```python
# cowboy_sdk/codec.py
import pvm_host

def encode(value):
    return pvm_host.cbor_encode(value)

def decode(data):
    return pvm_host.cbor_decode(data)
```

**Canonical CBOR 规则** (Rust 实现必须严格遵循):
1. 映射键按编码后字节的字典序排序
2. 整数使用最短编码
3. 禁止不定长度数组或映射
4. 浮点数统一编码为 64 位 IEEE 754（禁止 float16/float32 降级）
5. 禁止重复映射键

---

## 五、SoftFloat 策略（不变量 I-6）

### 5.1 问题本质

CIP-6 附录 A 规则 3：**禁止 `float`，使用 `cowboy_sdk.types.SoftFloat`**。

但当前 `SoftFloat(str)` 只是字符串包装，无实际算术能力。而 Rust PVM 层 (`vm/src/softfloat.rs`) 已完成真正的软件浮点实现。

### 5.2 策略选择

| 方案 | 描述 | 优势 | 劣势 |
|------|------|------|------|
| A: SDK 层包装类 | Python `SoftFloat` 类实现所有算术，底层调用 Host API | 类型系统清晰 | 每次运算一次 Host 调用，性能差 |
| B: PVM 全局替换 | RustPython VM 层将 Python `float` 全局替换为 softfloat | 零侵入、性能最优 | 开发者不感知类型差异 |
| **C: B + SDK 类型标注** | PVM 层全局替换 float + SDK 提供 `SoftFloat` 类型标注用于文档和 Schema | 两全其美 | 需确保 PVM 层替换完整 |

**选择方案 C**。

**实现**:
1. PVM Runtime 确认 `float` 全局使用 softfloat 实现（已有 `vm/src/softfloat.rs`）
2. SDK 的 `SoftFloat` 变为类型标注（alias），不再是独立的算术类：

```python
# cowboy_sdk/types.py
SoftFloat = float  # PVM 中 float 已全局替换为 softfloat
```

3. `CowboyModel` 在 Schema 生成时将 `float` 字段标记为 SoftFloat 语义
4. 确定性测试验证: `float(0.1) + float(0.2)` 在 x86 和 ARM 上产生相同结果

---

## 六、FSM vs Checkpoint 策略（不变量 I-3）

### 6.1 两种模式对比

| 维度 | FSM (有限状态机) | Checkpoint (运行时快照) |
|------|----------------|----------------------|
| **状态大小** | 仅 `capture()` 声明的变量，精简 | 整个 Python 执行栈 + VM 内部状态，巨大 |
| **确定性** | 状态是显式 CBOR，完全确定 | 快照包含 VM 内部指针、栈帧，**跨 PVM 版本不兼容** |
| **Gas 可预测性** | 恢复成本固定（反序列化 capture） | 恢复成本不可预测（重建整个 VM 状态） |
| **审计性** | 状态可读、可检查 | 快照是不透明二进制 |
| **升级兼容性** | ✅ 只依赖 CBOR 格式和 handler 名称 | ❌ PVM 任何内部变化都可能导致恢复失败 |
| **实现难度** | 高（需 AST→FSM 编译器） | 低（已实现） |

### 6.2 决策

**FSM 是唯一进入链上共识的 Continuation 模式。** Checkpoint 仅用于以下非共识场景：
- 本地开发网 (`cowboyd`) 的快速原型验证
- 单元测试中的 mock 执行
- 开发者 IDE 的调试预览

**绝不允许 Checkpoint 快照写入链上存储或参与区块状态转换。**

### 6.3 FSM 编译策略

FSM 编译不需要完整的 Python AST 编译器。CIP-6 明确了严格的模式约束：
- 最多 8 个顺序 await
- 禁止嵌套函数 await
- 禁止递归 await
- 循环 await 必须使用 `@bounded_loop`

在这些约束下，FSM 编译可简化为**装饰器级别的代码重写**：

```
原始代码:
    @runner.continuation
    async def f(self, msg):
        ctx = capture()
        ctx.a = await runner.llm("step1")
        ctx.b = await runner.llm(f"step2: {ctx.a}")
        return ctx.b

编译输出:
    def f(self, msg):
        cid = new_cid(self, "f")
        save_cont(cid, state=0, ctx={}, handler="f__resume")
        _send_job("llm", cid, "f__resume", "step1")

    def f__resume(self, msg):
        cont = load_cont(msg.cid)
        verify_guards(cont)
        ctx = cont["ctx"]

        if cont["state"] == 0:
            ctx["a"] = msg.result
            save_cont(msg.cid, state=1, ctx=ctx, handler="f__resume")
            _send_job("llm", msg.cid, "f__resume", f"step2: {ctx['a']}")
        elif cont["state"] == 1:
            ctx["b"] = msg.result
            delete_cont(msg.cid)
            return ctx["b"]
```

**实现路径**（分两阶段）：

**阶段 A — Python 层代码重写器** (Phase 1):
- 使用 Python `ast` 模块解析 `@runner.continuation` 装饰的函数
- 在 SDK 导入阶段 (`import cowboy_sdk`) 或 Actor 部署阶段执行转换
- 验证约束 (await 数量 ≤ 8、无嵌套、无递归)
- 生成等价的同步函数 + `__resume` 处理器
- **优势**: 纯 Python 实现，无需修改 Rust 编译器
- **预估工作量**: 10-12 天

**阶段 B — Rust 层字节码优化** (Phase 3+):
- 将 Python 层编译器迁移到 `codegen/src/pvm_fsm.rs`
- 在字节码层面优化，减少运行时开销
- **预估工作量**: 15-20 天

---

## 七、分阶段实现路线图（垂直切片）

### 设计原则

每个 Phase 交付**端到端可验证的完整功能切片**，而非水平层。每个 Phase 包含：
- 功能实现
- 对应的安全机制
- 确定性测试
- API 文档

### Phase 0: 基础设施与重命名（2 周）

**目标**: 建立 `cowboy_sdk` 基础，使整个后续开发在正确的地基上进行。

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **重命名 `pvm_sdk` → `cowboy_sdk`** | 目录重命名、所有 import 更新、测试修正、PVM 模块白名单更新 | 3 天 |
| **新增 Host API: `cbor_encode`/`cbor_decode`** | Rust 侧实现 Canonical CBOR，暴露给 Python | 3 天 |
| **迁移 `continuation.py` 序列化到 CBOR** | `encode_payload`/`decode_payload` 切换为 CBOR；移除 JSON fallback | 2 天 |
| **新增 Host API: `keccak256`** | 用于 Guard 指纹计算 | 1 天 |
| **新增 Host API: `self_address`、`current_block`** | Actor 基础元数据 | 1 天 |
| **定义错误层次结构** | `CowboyError` 基类 + 所有异常类型 | 1 天 |
| **建立 SDK 版本号 (`0.1.0`)** | `__version__`、SemVer 策略文档 | 0.5 天 |
| **确定性测试基础设施** | CI 跨平台 (x86 + ARM) CBOR 编解码一致性测试 | 1.5 天 |

**交付物**:
```
node/pvm/Lib/cowboy_sdk/
├── __init__.py          # 版本号、顶层导出
├── codec.py             # CBOR 编解码 (基于 Host API)
├── errors.py            # CowboyError, StateConflictError, ...
├── continuation.py      # 迁移至 CBOR 序列化
├── runtime.py           # 运行时检测
├── pvm_time.py          # 区块时间
├── pvm_random.py        # 确定性随机
└── pvm_sys.py           # 系统元数据
```

**错误层次结构**:
```python
class CowboyError(Exception): pass

class DeterminismError(CowboyError): pass
class StateConflictError(CowboyError): pass
class ReentrancyError(CowboyError): pass
class LoopBoundExceeded(CowboyError): pass
class CaptureTypeError(CowboyError): pass
class ContinuationLimitError(CowboyError): pass
class CycleLimitExceeded(CowboyError): pass
class RunnerTimeoutError(CowboyError): pass
class RunnerValidationError(CowboyError): pass
class DeterministicValidationError(CowboyError): pass
```

**Phase 0 验收标准**:
- `from cowboy_sdk import capture` 可正常工作
- `cowboy_sdk.codec.encode({...})` 与 Rust 侧 CBOR 输出字节相同
- `continuation.save_cont()` → CBOR 存储 → `load_cont()` 往返一致
- CI 跨 x86/ARM 通过

---

### Phase 1: 调用原语 + 安全机制 + FSM（5 周）

**目标**: CIP-6 第 1-3 章完整实现，含所有安全机制。这是 SDK 的核心里程碑。

#### 1A: 同步调用 `call()` + 重入保护（1.5 周）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **实现 `call()`** | 封装 `pvm_host.call_actor`，参数 CBOR 编码，返回值 CBOR 解码 | 2 天 |
| **实现 `send()`** | 封装 `pvm_host.send_message`，参数 CBOR 编码 | 1 天 |
| **实现 `@actor` 装饰器** | Actor 类注册、`self.address`/`self.storage` 属性注入 | 2 天 |
| **实现 `ActorRef` 语法糖** | `oracle.get_price("ETH")` 自动编译为 `call(...)` | 1 天 |
| **实现 `@reentrancy_guard`** | 基于 `keccak256(method + caller)` 的存储级锁 | 2 天 |
| **`call()`/`send()` 确定性测试** | 跨 Actor 调用、异常传播、深度限制 (32) | 1.5 天 |

**`call()` 实现**:
```python
# cowboy_sdk/call.py
import pvm_host
from . import codec

def call(target, method, args=None, cycles_limit=10000):
    if isinstance(target, str):
        target = bytes.fromhex(target.replace("0x", ""))
    payload = codec.encode(args) if args is not None else b""
    result_bytes = pvm_host.call_actor(target, method, payload, cycles_limit)
    if result_bytes is None:
        return None
    return codec.decode(result_bytes)
```

**`@reentrancy_guard` 实现**:
```python
# cowboy_sdk/guards.py
import pvm_host
from .errors import ReentrancyError

def reentrancy_guard(func):
    lock_key = b"__reentrancy:" + func.__name__.encode("utf-8")
    def wrapper(self, *args, **kwargs):
        if pvm_host.get_state(lock_key) is not None:
            raise ReentrancyError(f"Reentrant call to {func.__name__}")
        pvm_host.set_state(lock_key, b"\x01")
        try:
            return func(self, *args, **kwargs)
        finally:
            pvm_host.delete_state(lock_key)
    wrapper.__name__ = func.__name__
    return wrapper
```

#### 1B: FSM Continuation + Guard 校验（2 周）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **Python AST FSM 编译器** | `@runner.continuation` 装饰器在导入时解析 async 函数 AST，重写为 FSM | 7 天 |
| **Guard 校验强制执行** | `save_cont()` 捕获 guard 哈希，`load_cont()` 验证一致性 | 2 天 |
| **`capture()` 类型白名单** | `__setattr__` 检查值类型，禁止闭包/生成器/函数引用 | 1 天 |
| **`capture()` 大小限制** | 单个 Continuation ≤ 64 KiB | 0.5 天 |
| **Continuation 数量限制** | 每 Actor ≤ 100 个活跃 Continuation | 0.5 天 |

**FSM 编译器核心逻辑** (Python `ast` 模块):
```python
# cowboy_sdk/_compiler.py
import ast

class FSMCompiler(ast.NodeVisitor):
    def __init__(self, func_source, func_name):
        self.states = []
        self.current_state = 0
        self.await_count = 0
        self.func_name = func_name

    def visit_Await(self, node):
        self.await_count += 1
        if self.await_count > 8:
            raise ContinuationLimitError(
                f"{self.func_name}: max 8 sequential awaits (found {self.await_count})"
            )
        self.states.append(node)
        self.current_state += 1

    def validate(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef,)) and node.name != self.func_name:
                raise ContinuationLimitError("await in nested functions is prohibited")
            if isinstance(node, ast.Yield):
                raise DeterminismError("yield is prohibited in continuation functions")
```

**Guard 校验**:
```python
# cowboy_sdk/continuation.py 中增强

def save_cont(cid, state, ctx, handler, timeout_blocks=0, guard_keys=None):
    # ... 序列化 ctx ...
    guard_hashes = {}
    if guard_keys:
        for key in guard_keys:
            raw = pvm_host.get_state(key.encode("utf-8") if isinstance(key, str) else key)
            guard_hashes[key] = pvm_host.keccak256(raw) if raw is not None else None
    payload = {
        "state": state,
        "ctx": ctx_serialized,
        "handler": handler,
        "timeout_block": pvm_host.current_block() + timeout_blocks if timeout_blocks else 0,
        "guard_hashes": guard_hashes,
        "checksum": None,  # 后续填充
    }
    encoded = codec.encode(payload)
    payload["checksum"] = pvm_host.keccak256(encoded)
    pvm_host.set_state(_cont_key(cid), codec.encode(payload))


def load_cont(cid):
    raw = pvm_host.get_state(_cont_key(cid))
    if raw is None:
        raise CowboyError("continuation state missing")
    data = codec.decode(raw)
    _verify_guards(data)
    _verify_timeout(data)
    return data


def _verify_guards(cont_data):
    for key, expected_hash in cont_data.get("guard_hashes", {}).items():
        raw = pvm_host.get_state(key.encode("utf-8") if isinstance(key, str) else key)
        actual_hash = pvm_host.keccak256(raw) if raw is not None else None
        if actual_hash != expected_hash:
            raise StateConflictError(
                f"Guard violation: storage key '{key}' was modified during continuation"
            )


def _verify_timeout(cont_data):
    timeout_block = cont_data.get("timeout_block", 0)
    if timeout_block and pvm_host.current_block() > timeout_block:
        raise RunnerTimeoutError(f"Continuation timed out at block {timeout_block}")
```

**`capture()` 类型白名单**:
```python
_ALLOWED_CAPTURE_TYPES = (bool, int, str, bytes, bytearray, float, type(None), list, dict, tuple)

class Capture:
    def __setattr__(self, name, value):
        _check_capture_type(value, name)
        data = object.__getattribute__(self, "_data")
        data[name] = value

def _check_capture_type(value, path=""):
    if isinstance(value, _ALLOWED_CAPTURE_TYPES):
        if isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                _check_capture_type(item, f"{path}[{i}]")
        elif isinstance(value, dict):
            for k, v in value.items():
                if not isinstance(k, (str, int)):
                    raise CaptureTypeError(f"dict key at {path} must be str or int, got {type(k)}")
                _check_capture_type(v, f"{path}.{k}")
        return
    raise CaptureTypeError(
        f"Cannot capture {type(value).__name__} at '{path}'. "
        f"Only {', '.join(t.__name__ for t in _ALLOWED_CAPTURE_TYPES)} are allowed."
    )
```

#### 1C: `storage.guard()` + `@bounded_loop`（1 周）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **`storage.guard(key)`** | `GuardedValue` 类，访问 `.value` 时自动验证 | 2 天 |
| **`@bounded_loop`** | 迭代计数注入，超限抛 `LoopBoundExceeded` | 2 天 |
| **集成测试** | Guard 冲突检测、循环中断、嵌套场景 | 1 天 |

#### 1D: Phase 1 确定性测试（0.5 周）

| 测试场景 | 验证内容 |
|---------|---------|
| 跨 Actor `call()` 链 (A→B→C) | 深度计数、异常传播、原子回滚 |
| Continuation FSM 完整流程 | save→resume→verify_guard→delete |
| Guard 冲突检测 | 挂起期间修改 guarded key，恢复时抛出 StateConflictError |
| Reentrancy 保护 | 循环调用触发 ReentrancyError |
| Capture 类型拒绝 | lambda、generator、file handle 等被拒绝 |
| 跨 x86/ARM | 所有以上测试在两种架构上结果一致 |

**Phase 1 验收标准**:
- CIP-6 第 1-3 章的所有代码示例可直接运行
- Guard 校验在所有恢复路径上强制执行
- FSM 编译器正确处理顺序、条件分支两种 await 模式
- 所有安全机制 (`reentrancy_guard`, `bounded_loop`, `capture` 类型检查) 可用

---

### Phase 2: 类型系统 + 验证器 + Timeout（3 周）

**目标**: CIP-6 第 4-6 章功能完整。

#### 2A: 类型系统（1 周）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **确认 PVM SoftFloat 全局替换** | 验证 RustPython 中 `float` 已全局使用 softfloat | 1 天 |
| **`SoftFloat` 类型标注** | SDK 中 `SoftFloat = float`，CowboyModel 使用 | 0.5 天 |
| **`ordered_set`** | RustPython VM 层 `set` → 插入顺序集合；SDK 暴露类型 | 2 天 |
| **`BlockHeight`** | `int` 语义子类，`__repr__` 显示 "block#N" | 0.5 天 |
| **`CowboyModel`** | 基于 `dataclasses`，`schema()` 生成 JSON Schema，CBOR 序列化 | 3 天 |
| **类型系统确定性测试** | SoftFloat 算术一致性 (x86 vs ARM)、ordered_set 迭代顺序 | 1 天 |

**`CowboyModel` 设计**:
```python
# cowboy_sdk/models.py
import dataclasses
from . import codec

class CowboyModel:
    def __init_subclass__(cls, **kwargs):
        dataclasses.dataclass(cls)
        _validate_fields(cls)

    def to_cbor(self):
        return codec.encode(dataclasses.asdict(self))

    @classmethod
    def from_cbor(cls, data):
        d = codec.decode(data)
        return cls(**d)

    @classmethod
    def schema(cls):
        fields = dataclasses.fields(cls)
        properties = {}
        for f in fields:
            properties[f.name] = _type_to_json_schema(f.type)
        return {
            "type": "object",
            "properties": properties,
            "required": [f.name for f in fields if f.default is dataclasses.MISSING],
        }

def _validate_fields(cls):
    for f in dataclasses.fields(cls):
        if f.type is set or f.type is frozenset:
            raise DeterminismError(
                f"Field '{f.name}' uses set type. Use ordered_set instead."
            )
```

#### 2B: 验证构建器补全（1 周）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **补全 14 个 Verify 检查器** | 每个返回标准化 dict，由 Runner 侧执行 | 3 天 |
| **与 Rust `result-verifier` 对齐验证** | 确保 SDK 生成的 check spec 与 Rust 验证器兼容 | 1 天 |
| **验证器集成测试** | 提交 job → Runner 验证 → 结果回调 | 1 天 |

完整检查器列表（17 个）:

```python
class Verify:
    @staticmethod
    def builder(): return VerifyBuilder()

    @staticmethod
    def exact_match():
        return {"kind": "exact_match"}

    @staticmethod
    def json_schema_valid(schema):
        return {"kind": "json_schema_valid", "schema": schema}

    @staticmethod
    def structured_match(fields):
        return {"kind": "structured_match", "fields": list(fields)}

    @staticmethod
    def majority_vote(field):
        return {"kind": "majority_vote", "field": field}

    @staticmethod
    def supermajority_vote(field, threshold):
        return {"kind": "supermajority_vote", "field": field, "threshold": threshold}

    @staticmethod
    def numeric_tolerance(field, tolerance):
        return {"kind": "numeric_tolerance", "field": field, "tolerance": tolerance}

    @staticmethod
    def numeric_range(field, min_val, max_val):
        return {"kind": "numeric_range", "field": field, "min": min_val, "max": max_val}

    @staticmethod
    def set_equality(field):
        return {"kind": "set_equality", "field": field}

    @staticmethod
    def contains_all(substrings):
        return {"kind": "contains_all", "substrings": list(substrings)}

    @staticmethod
    def contains_none(substrings):
        return {"kind": "contains_none", "substrings": list(substrings)}

    @staticmethod
    def regex_match(pattern):
        return {"kind": "regex_match", "pattern": pattern}

    @staticmethod
    def length_bounds(min_len, max_len):
        return {"kind": "length_bounds", "min": min_len, "max": max_len}

    @staticmethod
    def semantic_similarity(threshold):
        return {"kind": "semantic_similarity", "threshold": threshold}

    @staticmethod
    def no_prompt_leak():
        return {"kind": "no_prompt_leak"}

    @staticmethod
    def entropy_check(min_entropy):
        return {"kind": "entropy_check", "min_entropy": min_entropy}

    @staticmethod
    def custom(actor, method):
        return {"kind": "custom", "actor": actor, "method": method}
```

#### 2C: Timeout + Retry + Timer 集成（1 周）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **新增 Host API: `set_timer`/`cancel_timer`** | Rust 侧实现 | 2 天 |
| **`timeout_blocks` 强制执行** | Continuation 保存时注册超时 Timer，恢复时检查 | 2 天 |
| **`Retry` 类** | 退避策略，延迟序列为固定 [1, 2, 4, 8] 个区块 | 1 天 |

**Phase 2 验收标准**:
- CIP-6 第 4-6 章所有代码示例可运行
- `SoftFloat` 算术在 x86/ARM 上结果一致
- 全部 17 个 Verify 检查器与 Rust 侧验证器格式兼容
- Timeout 到期触发 `RunnerTimeoutError`

---

### Phase 3: 高级异步模式 + Actor Continuation（3 周）

**目标**: CIP-6 第 7 章混合模式完整可用。

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **`runner.mcp()` 暴露** | SDK 层添加 MCP awaitable，与 HTTP/LLM 同等地位 | 2 天 |
| **`TaskGroup` 结构化并发** | 确定性 nonce 分配、按创建顺序返回结果 | 5 天 |
| **`@actor.continuation`** | Actor 间异步请求-响应完整流程 | 5 天 |
| **FSM 编译器: 循环 await** | `@bounded_loop` 装饰的循环中 await 的 FSM 状态生成 | 3 天 |
| **FSM 编译器: try/except await** | 异常状态的序列化和恢复 | 2 天|
| **综合集成测试** | CIP-6 §7.1 完整示例端到端运行 | 3 天 |

**`TaskGroup` 确定性设计**:

```python
class TaskGroup:
    def __init__(self):
        self._tasks = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass  # FSM 编译器会将 TaskGroup 展开为多个并行 send + 聚合 resume

    def create_task(self, awaitable):
        task = _TaskHandle(awaitable, len(self._tasks))
        self._tasks.append(task)
        return task
```

**关键约束**: `TaskGroup` 内任务创建顺序决定 nonce，因此必须严格确定性。FSM 编译器将 `async with TaskGroup()` 展开为：
1. 为每个 `create_task()` 生成独立的 `send_job()`，nonce 按创建顺序分配
2. 生成聚合状态: 等待所有任务结果到达
3. 结果按任务创建顺序排列

**Phase 3 验收标准**:
- CIP-6 §7.1 `TradingAgent.hybrid_workflow` 完整运行
- `TaskGroup` 并行任务结果顺序确定
- `@actor.continuation` 跨 Actor 异步调用完整流程

---

### Phase 4: 生产加固（4 周）

| 任务 | 说明 | 工作量 |
|------|------|--------|
| **全量确定性测试套件** | 所有 SDK 功能的跨平台 (x86/ARM) 一致性 | 5 天 |
| **压力测试** | 100 个并发 Continuation、深度 32 call 链、1024 条 send 扇出 | 5 天 |
| **安全审计检查表** | PVM 兼容性铁律 (CIP-6 附录 A) 逐项验证 | 3 天 |
| **FSM 编译器迁移到 Rust** | `pvm_fsm.rs` 完整实现，替代 Python `ast` 编译器 | 10 天 |
| **开发者文档** | API 参考、教程、最佳实践、反模式指南 | 5 天 |
| **性能基准** | Gas 消耗报告 (call/send/continuation/guard 各操作的 cycles/cells 成本) | 2 天 |

---

## 八、模块文件结构（最终形态）

```
node/pvm/Lib/cowboy_sdk/
├── __init__.py            # 版本号 (0.x.y)、顶层导出
│                          # call, send, actor, runner, capture,
│                          # ActorRef, Verify, Retry, CowboyModel
│
├── codec.py               # CBOR 编解码 (委托 pvm_host)
├── errors.py              # 完整错误层次结构
│
├── call.py                # call() 同步调用原语
├── send.py                # send() 异步消息原语
│
├── actor.py               # @actor 装饰器
│                          # ActorRef (同步语法糖 + async_* 方法)
│                          # @actor.continuation
│
├── runner.py              # @runner.continuation
│                          # runner.llm() / runner.http() / runner.mcp()
│
├── continuation.py        # Capture 类、save/load/delete_cont
│                          # CID 生成、Guard 校验、Timeout 校验
│                          # 类型白名单、大小限制
│
├── guards.py              # @reentrancy_guard
│                          # GuardedValue, storage.guard()
│
├── bounded_loop.py        # @bounded_loop(max_iterations=N)
│
├── verify.py              # Verify.builder() + 17 个内置检查器
├── retry.py               # Retry(max_attempts, backoff)
├── taskgroup.py           # TaskGroup 结构化并发
│
├── models.py              # CowboyModel 基类 (schema/CBOR 支持)
├── types.py               # SoftFloat (= float), ordered_set, BlockHeight
│
├── _compiler.py           # FSM 编译器 (Python AST → 同步状态机)
│                          # 内部模块，不暴露给开发者
│
├── runtime.py             # 运行时模式检测
├── pvm_time.py            # 确定性时间 (区块高度)
├── pvm_random.py          # 确定性随机数 (VRF)
└── pvm_sys.py             # 系统元数据 (chain_id, pvm_version)
```

---

## 九、白皮书与 SDK 规范一致性矩阵

| 白皮书章节 | CIP-6 对应 | 代码实现 | 一致性 | 所属 Phase |
|-----------|-----------|---------|--------|-----------|
| Actor 模型 (私有状态/邮箱) | Ch1 调用原语 | types/execution.rs | ✅ | — |
| 消息传递 (恰好一次) | Ch1.4 send() | storage: enqueue + 去重 | ✅ | — |
| 重入 (深度限制 32) | Ch1.5 reentrancy | execution.rs | ✅ | — |
| call() 原语 | Ch1.3 | SDK 缺失 | ⚠️ → Phase 1 | 1A |
| send() 原语 | Ch1.4 | SDK 缺失 | ⚠️ → Phase 1 | 1A |
| @reentrancy_guard | Ch1.5 | 未实现 | ❌ → Phase 1 | 1A |
| Continuation (FSM) | Ch2 编译策略 | 骨架存在 | ⚠️ → Phase 1 | 1B |
| capture() | Ch2.2 | 已实现 (需加固) | ⚠️ → Phase 1 | 1B |
| Guard 校验 | Ch3 | 未强制执行 | 🔴 → Phase 1 | 1B |
| storage.guard() | Ch3.2 | 未实现 | ❌ → Phase 1 | 1C |
| @bounded_loop | Ch2.5 | 未实现 | ❌ → Phase 1 | 1C |
| SoftFloat | PVM 数值确定性 | Rust 层完成 | ✅ (SDK 需对接) | 2A |
| ordered_set | PVM 哈希排序 | 未实现 | ❌ → Phase 2 | 2A |
| CowboyModel | Ch5 | 未实现 | ❌ → Phase 2 | 2A |
| CBOR 序列化 | 序列化章节 | 使用 JSON | 🔴 → Phase 0 | 0 |
| 验证模式 (6 种) | Ch6 | Rust 层完成 | ✅ (SDK 需补全) | 2B |
| Verify 检查器 | Ch6.3 | 3/17 | ⚠️ → Phase 2 | 2B |
| Timeout (区块高度) | Ch4.1 | 框架存在 | ⚠️ → Phase 2 | 2C |
| Retry | Ch4.1 | 未实现 | ❌ → Phase 2 | 2C |
| TaskGroup | Ch4.2 | 未实现 | ❌ → Phase 3 | 3 |
| @actor.continuation | Ch2.7 | 骨架 (抛异常) | ⚠️ → Phase 3 | 3 |
| runner.mcp() | 链下计算 | Rust 已实现 | ⚠️ → Phase 3 | 3 |
| 混合模式示例 | Ch7 | 不可用 | ❌ → Phase 3 | 3 |
| 模块白名单 | PVM 模块管理 | determinism.rs | ✅ | — |
| 固定哈希种子 | PVM 哈希排序 | determinism.rs | ✅ | — |
| 双 Gas (Cycles/Cells) | 费用章节 | execution.rs | ✅ | — |
| Timer 系统 | 定时器章节 | storage: Timer | ✅ | — |
| Runner VRF 选择 | Runner 选择 | ecvrf.rs | ✅ | — |

---

## 十、版本策略与 API 稳定性

### 10.1 SemVer 策略

```
主网前: 0.x.y
  0.1.0 — Phase 0 完成 (基础设施 + CBOR)
  0.2.0 — Phase 1 完成 (调用原语 + FSM + Guard)
  0.3.0 — Phase 2 完成 (类型 + 验证 + Timeout)
  0.4.0 — Phase 3 完成 (TaskGroup + Actor Continuation)
  0.9.0 — Phase 4 完成 (生产加固)

主网: 1.0.0
  公共 API 冻结，后续只允许向后兼容变更
```

### 10.2 API 弃用策略

- `0.x` 阶段: 允许 minor 版本间破坏性变更，但必须在 CHANGELOG 中明确标注
- `1.0` 后: 弃用 API 至少保留**两个 minor 版本**后移除
- 弃用 API 通过 `warnings.warn("...", DeprecationWarning)` 提示
- PVM 模块白名单确保旧 `pvm_sdk` 名称在过渡期内仍可导入 (Phase 0 中设置别名)

### 10.3 `pvm_sdk` → `cowboy_sdk` 过渡

Phase 0 执行时：
1. 目录 `node/pvm/Lib/pvm_sdk/` → `node/pvm/Lib/cowboy_sdk/`
2. 在 `node/pvm/Lib/pvm_sdk/__init__.py` 保留兼容层:
   ```python
   import warnings
   warnings.warn("pvm_sdk is deprecated, use cowboy_sdk", DeprecationWarning, stacklevel=2)
   from cowboy_sdk import *
   ```
3. PVM 模块白名单同时允许 `pvm_sdk` 和 `cowboy_sdk`
4. 在 `0.3.0` 之后移除 `pvm_sdk` 兼容层

---

## 十一、Host API 缺失项汇总

### 按 Phase 排列

| Phase | Host API | Rust 层工作 | Python 绑定 | 阻塞的 SDK 功能 |
|-------|----------|-----------|------------|----------------|
| **0** | `cbor_encode(value)` | 实现 Canonical CBOR 编码器 | 暴露为 `pvm_host.cbor_encode` | 所有序列化 |
| **0** | `cbor_decode(data)` | 实现 CBOR 解码器 | 暴露为 `pvm_host.cbor_decode` | 所有反序列化 |
| **0** | `keccak256(data)` | 调用已有 hashlib | 暴露为 `pvm_host.keccak256` | Guard 指纹 |
| **0** | `self_address()` | 返回当前 Actor 地址 | 暴露为 `pvm_host.self_address` | ActorRef |
| **0** | `current_block()` | 返回区块高度 | 暴露为 `pvm_host.current_block` | BlockHeight |
| **1** | `call_actor(target, method, args, cycles)` | 验证已有实现，确认 Python 绑定 | 确认可用 | `call()` |
| **2** | `get_balance(addr)` | 读取账户余额 | 暴露 | 状态查询 |
| **2** | `transfer(to, amount)` | 扣减/增加余额 | 暴露 | 原生转账 |
| **2** | `set_timer(height, handler, data)` | 注册到 Timer 队列 | 暴露 | Timeout |
| **2** | `cancel_timer(timer_id)` | 从 Timer 队列移除 | 暴露 | Timeout 清理 |

---

## 十二、时间线总结

```
Phase 0 (2 周)     Phase 1 (5 周)         Phase 2 (3 周)      Phase 3 (3 周)    Phase 4 (4 周)
┌──────────┐  ┌──────────────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ 基础设施  │  │ 调用原语 + FSM +     │  │ 类型 + 验证 + │  │ TaskGroup +   │  │ Rust FSM +    │
│ 重命名    │→│ Guard + 安全机制     │→│ Timeout       │→│ Actor Cont.  │→│ 安全审计 +    │
│ CBOR      │  │ + 确定性测试         │  │ + 确定性测试   │  │ + 确定性测试   │  │ 文档 + 基准   │
└──────────┘  └──────────────────────┘  └───────────────┘  └───────────────┘  └───────────────┘
   v0.1.0          v0.2.0                   v0.3.0              v0.4.0             v0.9.0
```

**总计: 17 周 (1 人全职)**

| Phase | 周数 | 交付的 CIP-6 章节 | 版本 |
|-------|------|------------------|------|
| 0 | 2 | 基础设施 (无对应章节) | 0.1.0 |
| 1 | 5 | Ch1 调用原语 + Ch2 Continuation + Ch3 状态安全 | 0.2.0 |
| 2 | 3 | Ch4 异步工具 + Ch5 类型系统 + Ch6 验证构建器 | 0.3.0 |
| 3 | 3 | Ch7 混合模式 + Actor Continuation | 0.4.0 |
| 4 | 4 | 生产加固、Rust FSM、文档 | 0.9.0 |

---

## 附录 A: PVM 兼容性铁律验证检查表

| # | 规则 | SDK 层实施方案 | 验证方法 |
|---|------|-------------|---------|
| 1 | 禁止 `import time` | PVM 模块白名单拦截；SDK 提供 `pvm_time` | 白名单测试 |
| 2 | 禁止 `import random` | PVM 模块白名单拦截；SDK 提供 `pvm_random` | 白名单测试 |
| 3 | 禁止 `float`（硬件 FPU） | PVM 全局 softfloat 替换；SDK `SoftFloat = float` | 跨平台算术测试 |
| 4 | 禁止 `set()` | PVM VM 层 set → ordered_set；SDK 暴露 `ordered_set` | 迭代顺序测试 |
| 5 | 禁止 `pickle` | PVM 模块白名单拦截；SDK 使用 CBOR | 白名单测试 |
| 6 | `call()` 深度 ≤ 32 | Host API `call_actor` 内部计数 | 深度越界测试 |
| 7 | await 点 ≤ 8 | FSM 编译器静态检查 | 编译器拒绝测试 |
| 8 | 循环 await 需 `@bounded_loop` | FSM 编译器静态检查 | 编译器拒绝测试 |
| 9 | `capture()` 显式声明 | FSM 编译器强制要求 | 编译器拒绝测试 |
| 10 | `send()` 不可撤回 | SDK 文档 + Linter 警告 | 反模式检测测试 |

## 附录 B: 现有代码关键文件索引

| 文件路径 | 功能 | 行数 | Phase 中的角色 |
|----------|------|------|--------------|
| `node/pvm/Lib/pvm_sdk/__init__.py` | SDK 入口 | 24 | Phase 0: 重命名 |
| `node/pvm/Lib/pvm_sdk/continuation.py` | Continuation 状态 | 158 | Phase 0: CBOR 迁移; Phase 1: Guard 加固 |
| `node/pvm/Lib/pvm_sdk/runner.py` | Runner 封装 | 82 | Phase 1: FSM 重写 |
| `node/pvm/Lib/pvm_sdk/actor.py` | Actor 引用 | 28 | Phase 1: 完整实现; Phase 3: Continuation |
| `node/pvm/Lib/pvm_sdk/verify.py` | 验证构建器 | 45 | Phase 2: 补全 14 个检查器 |
| `node/pvm/Lib/pvm_sdk/types.py` | 类型定义 | 3 | Phase 2: SoftFloat + ordered_set |
| `node/pvm/Lib/pvm_sdk/pvm_random.py` | 确定性随机 | 196 | 稳定，无需变更 |
| `node/chain/src/pvm_host.rs` | Host API | ~800 | Phase 0-2: 新增 7+ 个 API |
| `node/chain/src/execution.rs` | 执行引擎 | ~1500 | 稳定，无需变更 |
| `node/pvm/crates/vm/src/softfloat.rs` | 软浮点 | ~500 | Phase 2: 验证全局替换 |
| `node/pvm/crates/codegen/src/pvm_fsm.rs` | FSM 骨架 | ~100 | Phase 4: Rust FSM 编译器 |
| `runner/crates/result-verifier/src/verifier.rs` | 结果验证 | ~500 | Phase 2: SDK Verify 对齐 |

---

*本文档基于 2026-02-22 的代码库状态生成。SDK 标准名称为 `cowboy_sdk`。*
