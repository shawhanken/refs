# Cowboy 文档冲突分析与解决方案

| 字段 | 内容 |
|------|------|
| 版本 | v2.0 |
| 日期 | 2026-03-17 |
| 白皮书基线 | `refs/202602/20260221_cowboy-technical-whitepaper.md` |
| CIP 范围 | `refs/cips/cip-1, 2, 3, 4, 5, 6, 7, 10, 20, 21, 22` |
| 代码基线 | `/node/execution/src/gas.rs`, `basefee.rs`, `pvm_executor.rs`, `/node/storage/src/process_block.rs`, `/node/runner/src/types.rs` |

---

## 概述

对新版白皮书（2026-02-21）与所有 CIP 及当前代码实现进行逐节交叉核查，共发现 **10 个冲突点**，另含 **3 个白皮书内部自相矛盾**。按严重程度分三级：

- **P0（阻塞）**：若不解决，代码行为与规范根本不符，或规范本身无法实现
- **P1（重要）**：功能模型存在歧义，不同团队会做出不兼容的实现决策
- **P2（改进）**：规范表述不一致，但当前实现已隐式选择了某一方，风险可控

### 冲突汇总表

| # | 冲突点 | 级别 | 需改代码 | 需改文档 |
|---|-------|------|---------|---------|
| 1 | 系统 Actor 地址分配（WP §9 vs CIP-2 vs 代码） | P0 | ✓ | ✓ |
| 2 | Gas 成本表（WP §17.3 "权威" vs CIP-3 vs 代码） | P0 | — | ✓ |
| 3 | Timer 执行时机（CIP-1 先于 TX vs WP/CIP-5/代码 后于 TX） | P0 | — | ✓ |
| 4 | 两套 Timer 机制并存（CIP-1 GBA vs CIP-5 Globalbox） | P0 | — | ✓ |
| 5 | Basefee 目标值（WP 10M cycles vs 代码 5M） | P1 | ✓ | — |
| 6 | Basefee 计算公式（WP §4.2 含 alpha/clamp vs §17.8 简化版） | P1 | — | ✓ |
| 7 | Runner 质押公式（WP §5.2: 1.5× vs §17.7: 10× vs 代码: 仅地板价） | P1 | — | ✓ |
| 8 | Runner 结果提交协议（WP 15min 挑战窗口 vs CIP-2 Aggregator 模型） | P1 | — | ✓ |
| 9 | 序列化格式（CIP-3 MessagePack vs WP §2.5 / CIP-6 CBOR） | P2 | — | ✓ |
| 10 | 存储驱逐时机（WP §17.5 10 rent-epoch vs 正文 N+11 off-by-one） | P2 | — | ✓ |

**代码改动总计：仅 2 处**（冲突 #1 地址重分配，冲突 #5 常量修正）
**文档改动：9 处**（需明确哪份文档为权威）

---

## 冲突 #1 — 系统 Actor 地址分配（P0）

### 问题描述

新版白皮书 §9 和 CIP-2 对系统 Actor 地址的分配存在冲突，而代码使用了一个规范中完全未定义的地址：

| 地址 | WP §9（2026-02-21） | CIP-2 规范表 | 当前代码 |
|------|-------------------|-------------|---------|
| 0x01 | Messaging（消息路由） | Runner Registry（注册/质押/健康/声誉） | `SystemActorAddresses::runner_registry()` |
| 0x02 | Timers（定时器） | Job Dispatcher（提交/VRF 选择/生命周期） | — |
| 0x03 | Oracle/Runner（离链作业） | Result Verifier（commit-reveal 聚合/验证/回调） | — |
| 0x04 | Blob Store（大对象存储） | Secrets Manager（加密凭证存储/TEE 访问） | — |
| 0x05 | Signer Utils（签名工具） | TEE Verifier（远程证明验证） | — |
| 0x06 | EventListener（以太坊事件订阅） | **Reserved（预留未分配）** | **`BASEFEE_SYSTEM_ACTOR`**（代码自造，WP 分配给 EventListener，CIP-2 预留） |
| 0x07 | TEE Verifier（可信执行验证） | Entitlement Registry（Runner Pool RBAC） | — |
| 0x08 | Secrets Manager（密钥管理） | —（CIP-2 仅定义到 0x07） | — |

**核心矛盾：**
1. WP §9 中 0x01=Messaging，CIP-2 中 0x01=Runner Registry — 完全相反，功能毫不相关
2. WP §9 中 0x03=Oracle/Runner，CIP-2 中 0x03=Result Verifier（功能名称相近但不同）；0x04=Blob Store vs 0x04=Secrets Manager（完全不同）
3. WP §9 中 0x06=EventListener，CIP-2 中 0x06=Reserved，代码中 0x06=BASEFEE_SYSTEM_ACTOR — 三方均不一致，且 Basefee 系统 Actor 在任何规范中都没有明确地址
4. WP §9 中 0x07=TEE Verifier，CIP-2 中 0x07=Entitlement Registry — 功能完全不同
5. WP §9 定义了 8 个 Actor（到 0x08），CIP-2 只定义到 0x07（缺少 Secrets Manager 地址）

### 影响

- 不同实现团队无法互操作（地址 0x01 注册完全不同的逻辑）
- Basefee 状态持久化于 0x06，而规范将 0x06 分配给 EventListener，存在潜在存储污染
- CIP-2 关于 Runner Registry 的所有地址引用都可能是错的

### 最佳方案

统一制定一份主权威系统 Actor 地址表（建议新增 CIP-0 或在 WP §9 标注为唯一权威），**明确 Basefee 系统 Actor 地址**（建议 0x09 或增设 0x00 为协议保留）：

```
0x01 — Messaging（消息路由）
0x02 — Timers（定时器调度）
0x03 — Runner/Oracle（离链作业）
0x04 — Blob Store（大对象存储）
0x05 — Signer Utils（签名工具）
0x06 — EventListener（以太坊事件订阅）
0x07 — TEE Verifier（可信执行验证）
0x08 — Secrets Manager（密钥管理）
0x09 — Basefee（双计量基础费用状态）  ← 新增
```

并修正 CIP-2 地址表与 WP 一致。

### 最小代价方案（相对当前代码）

1. **代码改动（1 处）**：`/node/storage/src/process_block.rs`
   ```rust
   // 将 BASEFEE_SYSTEM_ACTOR 从 0x06 改为 0x09（或 WP 选定的空闲地址）
   const BASEFEE_SYSTEM_ACTOR: Address = Address::from_low_u64(0x09);
   ```
2. **文档改动**：在 WP §9 添加 0x09 = DualBasefee；在 CIP-2 的 System Actor 表中添加指向 WP §9 的引用注释，不改变 CIP-2 功能内容。
3. **不改变** CIP-2 中 Runner Registry 地址（Runner 系统目前代码就用 `runner_registry()` 函数，需确认该函数的实际地址值与哪个规范一致）。

---

## 冲突 #2 — Gas 成本表（P0）

### 问题描述

白皮书声明 §17 为"权威"，但 §17.3 的 Actor API 成本与 CIP-3 和代码实现相差 **12–100 倍**：

| 操作 | WP §3.5（信息性） | WP §17.3（**声称权威**） | CIP-3（权威） | 代码（gas.rs） |
|------|-----------------|----------------------|-------------|--------------|
| mailbox send | 80 cycles | 1,000 cycles | 80 cycles | 80 cycles |
| storage_read | 未列出 | 500 cycles + 1/byte | 10 cycles | 10 cycles |
| storage_write | 未列出 | 5,000 cycles + 10/byte | 50 cycles | 50 cycles |
| timer set/cancel | 200 cycles | 未独立列出（由 §17.2 定义 5,000 cycles 交易本征成本） | 200 cycles | 200 cycles |
| token_transfer | 未列出 | 1,000 cycles / 64 cells | 1,000 cycles / 64 cells | 1,000 / 64 ✓ |
| token_mint | 未列出 | 1,000 cycles / 64 cells | 1,000 cycles / 64 cells | 1,000 / 64 ✓ |
| token_approve | 未列出 | 500 cycles / 32 cells | 500 cycles / 32 cells | 500 / 32 ✓ |

**注意**：WP §17.2 还定义了"交易本征成本"（交易级开销，非 host call 级开销），两层成本都存在，不同文档有时混淆两者：

| 交易类型 | 本征 Cycles | 本征 Cells |
|---------|------------|-----------|
| Transfer | 21,000 | 0 |
| Deploy | 100,000 | code_size |
| ActorMessage | 21,000 | calldata_size |
| TimerSchedule | 5,000 | 64 |

### 影响

- WP §17.3 若被视为权威，需将代码中 mailbox send 从 80 改为 1,000（12.5 倍），storage_write 从 50 改为 5,000 + 10/byte（100 倍），会彻底破坏所有现有测试和 Actor 的 gas 估算
- CIP-3 与代码一致，若视 CIP-3 为权威，则 WP §17.3 数值为笔误

### 最佳方案

宣布 **CIP-3 为 gas 成本的唯一权威**。修改 WP §17.3 中 Actor API 成本表，替换为 CIP-3 的值，并在 WP §17 开头加注："具体 gas 数值以各 CIP 为准，本节仅提供参考性示例。" 区分"交易本征成本"（WP §17.2 正确）和"host call 成本"（CIP-3 正确）。

### 最小代价方案（相对当前代码）

**零代码改动**。代码已与 CIP-3 对齐。
仅需：修改 WP §17.3 的 Actor API 成本表数值，加注 "CIP-3 is normative"。

---

## 冲突 #3 — Timer 执行时机（P0）

### 问题描述

CIP-1 规定 Timer 在交易之前执行，与 WP、CIP-5 和代码实现相反：

| 文档/代码 | Block 执行顺序 |
|---------|--------------|
| WP（新版）§State Transition | Execute Transactions **→** Deliver Timers → Resolve Jobs |
| CIP-5 | Execute Transactions **→** EOB Timer Delivery |
| 代码（process_block.rs） | Step 5: Execute transactions **→** Step 9: Fetch expired timers |
| **CIP-1** | **Deliver Timers → Execute Transactions** ← 与所有其他来源冲突 |

### 影响

- CIP-1 如被作为实现依据，将导致 Timer 回调可在同 block 的用户交易之前执行，影响 MEV 模型和确定性顺序
- 当前代码已按 WP 顺序实现（Timer 在 TX 之后），CIP-1 是孤立的异常

### 最佳方案

修订 CIP-1 §State Transition Function，将 Timer 执行位置调整为"Execute Transactions 之后"，与 WP 和 CIP-5 一致。

### 最小代价方案（相对当前代码）

**零代码改动**。只需修改 CIP-1 的状态转换函数说明（约 1 段文字）。

---

## 冲突 #4 — 两套 Timer 机制并存（P0）

### 问题描述

CIP-1 和 CIP-5 描述了两种**架构不兼容**的 Timer 机制，且均处于 Draft 状态：

| 维度 | CIP-1（GBA 模型） | CIP-5（Globalbox 模型） | WP（新版）|
|------|-----------------|----------------------|---------|
| 调度原语 | `set_timer(height, handler, data)` | `set_timer(delay, handler, data)` + 状态变更触发 | `set_timer(height, handler, data)` |
| 执行驱动 | GBA（竞价代理）决定是否执行 | 协议保证 EOB（块末）执行 | GBA 竞价（§3.3） |
| 优先级 | GBA 出价排序 | 老化权重打分（aging score） | 未明确 |
| 跨 block 一致性 | 无，GBA 可能不出价 | Globalbox 持久化保证 | 最佳努力（best-effort） |
| 取消逻辑 | `cancel_timer(id)` 退还押金 | 与 GBA 解绑，按 ID 取消 | `cancel_timer(id)` |
| 状态触发 | 不支持 | 支持（状态变更自动触发定时器） | 不支持 |
| 代码实现情况 | 部分实现（calendar queue 结构） | 未实现 | — |

### 影响

- 两个 CIP 均无法同时成立，必须选一个废弃或合并
- Actor SDK（CIP-6）引用 `set_timer` 语义，但未说明遵循哪个 CIP
- 实现团队无法同时满足两个规范

### 最佳方案

**明确废弃 CIP-5**，以 CIP-1（与 WP 一致）为权威 Timer 机制。或将 CIP-5 中 EOB 保证交付、状态触发 Timer 等优秀特性合并进 CIP-1 v2，并更新状态为 Superseded。

### 最小代价方案（相对当前代码）

**零代码改动**。在 CIP-5 文档头部添加：
```
Status: Superseded by CIP-1
```
在 CIP-1 中可选择性合并 EOB 保证和老化权重描述。

---

## 冲突 #5 — Basefee 目标值（P1）

### 问题描述

白皮书与代码实现对 Cycles 目标值有 **2 倍**差异：

| 参数 | WP §4.3 | WP §13（参数表） | WP §17.9 | 代码（basefee.rs） |
|------|---------|----------------|---------|-----------------|
| T_c（每块 Cycles 目标） | 10,000,000 | 10,000,000 | 10,000,000（lane 分配基数） | **5,000,000** |
| T_b（每块 Cells 目标） | 500,000 | 500,000 | 500,000 | 500,000 ✓ |
| 硬上限（Cycles） | 20,000,000 | — | — | 未实现 |

WP §17.9 还基于 T_c=10M 给出了四车道的绝对 Cycle 预算：

| 车道 | Cycles 预算 | 百分比 |
|------|------------|-------|
| User | 5,000,000 | 50% |
| Runner | 2,500,000 | 25% |
| Timer | 2,000,000 | 20% |
| System | 500,000 | 5% |

若代码使用 T_c=5M，Timer 车道实际只有 1M cycles，与 WP 描述的 2M 不符。

### 影响

- EIP-1559 基础费调节速率与 WP 设计不符（basefee 在低负载时下降更慢，高负载时上涨更快）
- 车道容量配比（Timer 20%）在绝对数值上不匹配

### 最佳方案

将代码改为与 WP 一致：T_c = 10,000,000。如果 devnet 出于性能考虑需要较低目标，在 WP §13 "Devnet Defaults" 下单独列出，主网参数保持 10M。

### 最小代价方案（相对当前代码）

**代码改动（1 处）**，`/node/execution/src/basefee.rs`：
```rust
// 改动前
pub const BLOCK_CYCLES_TARGET: u64 = 5_000_000;
// 改动后
pub const BLOCK_CYCLES_TARGET: u64 = 10_000_000;
```
如需保留 devnet 行为，在同文件添加：
```rust
/// Devnet override for faster feedback (not used in mainnet)
pub const DEVNET_BLOCK_CYCLES_TARGET: u64 = 5_000_000;
```

---

## 冲突 #6 — Basefee 计算公式（P1 — WP 内部矛盾）

### 问题描述

新版白皮书在两个章节给出了**数学上不同**的 basefee 调整公式：

**WP §4.2（规范性 canonical 描述）：**
```
basefee_{x,i+1} = max(1, basefee_{x,i} × (1 + clamp((U_x - T_x) / (T_x × alpha), -delta, +delta)))
```
参数：alpha = 8，delta = 0.125（12.5%），包含 alpha 平滑因子和 clamp 截断

**WP §17.8（§17 被声明为权威）：**
```
next_basefee = basefee × (1 + δ × (usage - target) / target)
```
该公式**省略了 alpha 除法**和 **clamp 截断**，只在文字说明中提到"最大变化 12.5%"

两个公式在相同输入下会产生不同结果（当 deviation 超过 ±12.5% 时差异最大）。

| 维度 | §4.2 | §17.8 |
|------|------|-------|
| alpha 平滑 | ÷ 8（平滑波动） | 无 |
| 截断机制 | clamp(·, -δ, +δ) 硬截断 | 依赖 δ 线性（不截断） |
| 极端负载下行为 | 最多 ±12.5%/block | 可超过 ±12.5% |
| 代码实现（basefee.rs） | **与 §4.2 一致**（BASEFEE_ALPHA=8, BASEFEE_MAX_CHANGE_DENOM=8） | — |

### 影响

- §17 被声称为权威，但 §17.8 的公式数学上比 §4.2 宽松（无截断保护），在极端负载下 basefee 可以剧烈波动
- 审计方或实现方读 §17.8 会得到与代码不同的公式

### 最佳方案

统一两个公式，以 §4.2 的含 alpha + clamp 版本为准（因为代码已实现此版本）。修改 §17.8 为：

```
basefee_{x,i+1} = max(MIN_BASEFEE, basefee_{x,i} × (1 + clamp((U_x - T_x) / (T_x × α), -δ, +δ)))
其中 α = 8（BASEFEE_ALPHA），δ = 0.125（BASEFEE_MAX_CHANGE_DENOM = 8）
```

### 最小代价方案（相对当前代码）

**零代码改动**。只修改 WP §17.8 的公式，使其与 §4.2 和代码一致。

---

## 冲突 #7 — Runner 质押公式（P1 — WP 内部矛盾）

### 问题描述

白皮书在三处给出了互相矛盾的 Runner 最低质押要求：

| 章节 | 公式 |
|------|------|
| WP §5.2（规范性描述） | `stake >= max(10,000 CBY, 1.5 × declared_max_job_value)` |
| WP §13（协议参数表） | `runner_stake_floor = 10,000 CBY`（仅地板价，无倍数） |
| WP §17.7（**§17 声称权威**） | `stake >= 10 × average_job_value` |
| 代码（runner/src/types.rs） | `MIN_STAKE_CBY_WEI = 10,000 × 10^18`（仅地板价） |

三个公式问题：
- §5.2 vs §17.7：参考值不同（declared_max 声明最大值 vs average 平均值），倍数不同（1.5× vs 10×）
- §13 和代码只有地板价，没有与 job_value 挂钩的动态要求
- §17.7 的 10× average 难以链上验证（average 如何计算？over what window？）

### 影响

- Runner 注册合约逻辑不明确
- 若执行 §17.7（10× average），质押要求可能比 §5.2（1.5× declared_max）高出数倍

### 最佳方案

在 WP §5.2 / §17.7 选一个统一公式并声明权威，建议采用 §5.2 版本（链上可验证，declared_max 在注册时已知）：
```
runner_stake >= max(10,000 CBY, 1.5 × declared_max_job_value)
```
删除或修订 §17.7，使其与 §5.2 一致。

### 最小代价方案（相对当前代码）

**零代码改动**（代码目前仅检查地板价，为 devnet 合理简化）。
只修改 WP §17.7 使其与 §5.2 表述一致。若要在 testnet 前实现完整质押检查，可在代码中加：
```rust
// 额外校验：stake >= 1.5 × declared_max_job_value（CBY wei）
```

---

## 冲突 #8 — Runner 结果提交协议（P1）

### 问题描述

WP 和 CIP-2 对 Runner 结果提交流程的描述存在结构性差异：

| 维度 | WP §5.3 | CIP-2 |
|------|---------|-------|
| 流程模型 | 点对点 commit-reveal | Aggregator 角色负责收集和聚合 |
| 挑战窗口 | **15 分钟**，任何人可发起挑战 | 未明确挑战窗口时长 |
| 挑战保证金 | **100 CBY** | 未明确 |
| Aggregator 角色 | 未定义 | 核心角色（收集 commit/reveal，触发验证） |
| 验证模式 | `none/economic_bond/majority_vote/structured_match/deterministic/semantic_similarity` | 相同 6 种 |
| Payout 比例 | 89% runner / 10% burn / 1% treasury | 未明确 |
| 代码实现 | 无挑战窗口，无 Aggregator | `VerificationMode` 实现 `None/MajorityVote/StructuredMatch` |

### 影响

- 实现时不清楚是否需要实现 15 分钟挑战窗口
- Aggregator 角色是 CIP-2 的核心，但 WP 没有定义其系统 Actor 地址和职责边界
- 代码目前省略了挑战机制，属于 devnet 简化，但不符合任何规范的生产要求

### 最佳方案

以 WP §5.3 为权威，更新 CIP-2 补全以下内容：
- 明确挑战窗口 = 15 分钟（900 个块 @1s/block）
- 明确挑战保证金 = 100 CBY
- 定义 Aggregator 在 WP §9 系统 Actor 表中的地址（如 0x03 = Oracle/Runner 即已涵盖）
- Payout 比例写入 CIP-2

### 最小代价方案（相对当前代码）

**零代码改动**（挑战机制属 post-devnet 功能）。
只需在 CIP-2 中引用 WP §5.3 的 15 分钟/100 CBY 数值，并说明 Aggregator = 0x03 系统 Actor。

---

## 冲突 #9 — 序列化格式（P2）

### 问题描述

CIP-3 提到了与 WP 不一致的序列化格式：

| 文档 | 序列化格式 |
|------|----------|
| WP §2.5（规范性） | **Canonical CBOR**（RFC 8949 §4.2 确定性编码） |
| WP §附录A | CBOR 测试向量 |
| CIP-6 | **Canonical CBOR**，明确声明"**superseding generic 'MessagePack or protocol-specific binary' from CIP-3**" |
| CIP-10 | CBOR（贯穿全文） |
| CIP-3 | "MessagePack or protocol-specific binary format" ← 被 CIP-6 显式覆盖 |
| 代码（pvm_executor.rs） | CBOR（`cbor2` 在允许 stdlib 列表中） |

> **注**：CIP-6 已明确宣告覆盖 CIP-3 的 MessagePack 表述，此冲突在 CIP 层面实际上已有隐式解决（以 CBOR 为准），但 CIP-3 原文尚未修订，仍可能误导读者。

### 影响

- CIP-3 中"MessagePack"表述会导致读者迷惑，pvm 中序列化到底用哪种
- 如果 Actor 代码使用 `msgpack` 而非 `cbor2`，与跨链验证和交易签名哈希可能不兼容

### 最佳方案

修改 CIP-3 中"MessagePack or protocol-specific"为"Canonical CBOR (RFC 8949)"，与 WP §2.5 和 CIP-6 保持一致。

### 最小代价方案（相对当前代码）

**零代码改动**。只修改 CIP-3 中的一处表述。

---

## 冲突 #10 — 存储驱逐时机（P2 — WP 内部矛盾）

### 问题描述

白皮书在三处对驱逐时机的描述存在 off-by-one 不一致：

| 来源 | 描述 |
|------|------|
| WP §4.4 | "eviction eligible after **10 rent-epochs**" |
| WP §17.5（权威） | "eviction after **10 rent-epochs** of accumulated debt" |
| WP 正文（架构章节） | "Eviction at rent-epoch **N+11**"（7 宽限期 + 3 警告期 + 1 触发 = 11） |

7+3=10 个 rent-epoch 的欠租 → 触发应在第 11 个，但 §17.5 说"10 个 rent-epoch 后"，差 1 个 epoch。

### 影响

影响较小，仅影响 Actor 余额耗尽时的精确存活周期。

### 最佳方案

统一为 §17.5 的表述（"10 个 rent-epoch 欠租后驱逐"），将正文架构章节的"N+11"改为"N+10"。或反之，均可，只需三处一致。

### 最小代价方案（相对当前代码）

**零代码改动**（存储驱逐当前未实现）。只修改 WP 两处中的某一处文字，使三处数字一致。

---

## 附录 A — 白皮书内部矛盾汇总

> 以上冲突 #6、#7、#10 是白皮书自身内部矛盾，此处单独汇总：

| 矛盾 | 章节 | 描述 |
|------|------|------|
| Gas: mailbox send | §3.5 vs §17.3 | 80 cycles vs 1,000 cycles |
| Basefee 公式 | §4.2 vs §17.8 | 含 alpha+clamp vs 简化线性公式 |
| Runner 质押公式 | §5.2 vs §17.7 | 1.5× declared_max vs 10× average |
| 驱逐时机 | §4.4 / §17.5 vs 正文 | 10 rent-epoch vs N+11（off-by-one） |

**建议**：在白皮书前言添加"§17 中的所有数值均覆盖前文对应章节"的统一声明，并将前文（§3.5、§4.2 等）中与 §17 冲突的信息标注为"见 §17 权威版本"或直接删除。

---

## 附录 B — 各文档冲突出处映射

| 文档 | 冲突涉及 |
|------|---------|
| WP §9 | 冲突 #1（系统 Actor 地址） |
| WP §3.5 vs §17.3 | 冲突 #2（Gas 成本），附录 A |
| WP §4.2 vs §17.8 | 冲突 #6（Basefee 公式），附录 A |
| WP §4.3 / §13 / §17.9 | 冲突 #5（Cycles 目标） |
| WP §4.4 / §17.5 vs 正文 | 冲突 #10（驱逐时机），附录 A |
| WP §5.2 vs §17.7 | 冲突 #7（质押公式），附录 A |
| WP §5.3 | 冲突 #8（Runner 结果协议） |
| CIP-1 | 冲突 #3（Timer 执行时机），冲突 #4（双 Timer 机制） |
| CIP-2 | 冲突 #1（地址表），冲突 #8（Aggregator 模型） |
| CIP-3 | 冲突 #2（Gas 数值），冲突 #9（序列化） |
| CIP-5 | 冲突 #4（双 Timer 机制） |
| 代码 process_block.rs | 冲突 #1（BASEFEE 0x06），冲突 #3（Timer 顺序 ✓） |
| 代码 basefee.rs | 冲突 #5（5M vs 10M），冲突 #6（公式 ✓） |
| 代码 gas.rs | 冲突 #2（CIP-3 aligned ✓） |

---

## 附录 C — 已确认一致区域（无冲突）

以下技术维度在 WP 与各 CIP 及代码中**高度一致**：

| 维度 | 一致情况 |
|------|---------|
| EIP-1559 双计量（Cycles + Cells） | WP §4 ≡ CIP-3 §2 ≡ 代码 |
| Basefee alpha=8, delta=12.5% | WP §4.2 ≡ CIP-3 §2.4 ≡ 代码 BASEFEE_ALPHA=8 |
| CIP-20 Token 成本表 | WP §17.3 ≡ CIP-20 ≡ 代码 token_* 常量 |
| Token hook gas 上限 50,000 cycles | WP（implied） ≡ CIP-20 ≡ 代码 TOKEN_HOOK_MAX_CYCLES=50_000 |
| PVM 确定性约束（asyncio.gather ban, hash_seed=0） | WP §2.4 ≡ CIP-3 §2.4 ≡ 代码 validate_actor_code |
| 三层存储架构（Ledger+MPT+Aux） | WP §1.7 ≡ CIP-4 |
| CBOR 序列化（主体） | WP §2.5 ≡ CIP-6 ≡ 代码（cbor2 in whitelist） |
| Cells 目标 T_b = 500,000 | WP §4.3 ≡ 代码 BLOCK_CELLS_TARGET=500_000 |
| 验证模式 6 种 | WP §5 ≡ CIP-2 ≡ 代码 VerificationMode |
| Runner 结果签名字段（可选） | CIP-2 ≡ 代码 RunnerResult.signature: Option<[u8;65]> |
| Timer 车道 20% block capacity | WP §17.9 ≡ CIP-22 ≡ 代码 |
| Python 版本 3.11.8 固定 | WP ≡ 代码 |
| Simplex BFT ~1s block / ~2s finality | WP ≡ 共识层一致 |
