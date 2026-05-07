---
type: concept
tags: [mpp, session, payments, runner, cip-2, cip-7, draft]
sources:
  - refs/runner/2026-04-28_MPP_Session_Research.md
  - refs/plans/2026-05-06_mpp_session_implementation.md
  - refs/cips/cip-2-offchain-compute.md
  - refs/cips/cip-7-simple-stream-protocol.md
  - refs/cips/cip-3-fee-model.md
last_updated: 2026-05-07
status: draft
---

# MPP Session（Machine Payment Protocol Session）

## 概述

MPP Session 是研究阶段的「链上托管 + 链下累积 voucher + 链上结算」支付通道模型，对接 Stripe/Tempo Labs 提交给 IETF 的 Machine Payment Protocol 草案。它把 N 次 Runner 微调用（典型 LLM token / HTTP API / MCP 调用）的链上开销从 N 笔 tx 摊到 **3 笔（Open / Settle / Finalize）**。研究文档 §7 给 Cowboy 的战略定位是 **"AI 工作负载的结算层"** —— Runner 调用绕过链路，付款跑在 Cowboy 上。

**当前状态**：研究文档（2026-04-28）+ 实施计划（2026-05-06）。**未起草 CIP**，**未实装**。研究/计划提议地址 `0x0C` 与 opcodes 52-57，与 CIP-14 v2 / CIP-13 v2 / CIP-23 v2 已分配段冲突（见 [[../drift]] V-11 / V-12）。

---

## 与 MPP 协议的对接

MPP 协议骨架（[paymentauth.org](https://paymentauth.org/)）分两种模式：

| 模式 | 适用 | 链上 tx |
|---|---|---|
| **Charge / 402** | 单次高价值调用 | 每次 1 笔 |
| **Session** | 高频微付费（LLM token / 流式 API） | Open + Settle + Finalize 3 笔 |

Cowboy 集成 Session 模式 —— 复用 wevm/mppx 客户端，仅替换 EIP-712 domain 为 `name="Cowboy MPP Session", version="1", chainId=<cowboy>, verifyingContract=SESSION_ACTOR`。这样同一 Agent 工具链既能在 Tempo 上跑 USDG，也能在 Cowboy 上跑 CBY。

---

## Session 生命周期

```
[*] --> Open (OpenSession + deposit)
Open --> Open (Deposit / Settle)
Open --> Closing (CloseSession by payer | expires_at | escrow exhausted)
Closing --> Closing (Settle within dispute window)
Closing --> Disputed (Slash by payer)
Closing --> Refunded (Finalize after DISPUTE_WINDOW_BLOCKS)
Disputed --> Settled / Slashed (CIP-2 commit-reveal 复用)
```

**4 个稳定状态**：`Open`（接受 voucher / Deposit / Settle）、`Closing`（dispute window 中）、`Settled` / `Refunded`（终态）。`Disputed` 是瞬态 —— 入口 `Slash`，出口走 CIP-2 既有共识（Result Verifier 0x03 + commit-reveal）。

---

## 链上：Session Actor（提案 `0x0C`）

研究文档 §5.3 / 计划 §3 提议新建 system actor，承载托管 + 结算 + 退款 + 仲裁入口 6 个 handler：

| Handler | Opcode 提案 | 行为 |
|---|---|---|
| `OpenSession` | 52 | 校验 runner registered、`max_amount > 0`；从 payer 扣 `max_amount` 入 escrow；写入 `Session{status: Open}` |
| `Deposit` | 53 | session.Open；payer 扣款 → escrow 加；`session.deposit += amount` |
| `Settle` | 54 | 校验 voucher 5 项（签名 / 单调 cumulative / 单调 nonce / `expires_at >= block` / `cumulative ≤ deposit`）→ 按 `SettlementConfig` 89/10/1 分账 → 更新 `session.spent` / `last_voucher_nonce` |
| `CloseSession` | 55 | 仅 payer；Open → Closing{closed_at: block_height} |
| `Finalize` | 56 | 任意人，`block_height >= closed_at + DISPUTE_WINDOW_BLOCKS=75`；剩余 `deposit - spent` 退还 payer；status → Refunded |
| `Slash` | 57 | PoC 阶段返回 `Unsupported`；二期接 CIP-2 既有 Verifier(0x03) 仲裁 |

**Storage layout**：以 `SESSION_ACTOR` 作 actor address，key = `b"session:" || session_id (32B)`，value = `bincode(Session)`。voucher 不入链存储。

⚠️ **地址 / opcode 冲突**：
- `0x0C` 在 CIP-14 v2 已分配给 `ROUTE_REGISTRY`（[[../entities/system-actors]]）
- Opcodes 52-56 在 CIP-13 v2 §1 主分配表已分配给 Runner 委托
- Opcode 57 在 CIP-23 v2 §4 已分配给 `VerifyCae`
- 研究文档/计划是研究阶段提案，**激活前需经治理选址重排**；详见 [[../drift]] V-11 / V-12 与 [[../parameters]] SystemInstruction Opcode 主分配表

---

## 链下：Voucher 与 Runner 端

**Voucher（EIP-712 类型化数据，145 bytes）**：

```rust
SessionVoucher {
    session_id: [u8; 32],
    cumulative_amount: u128,    // 自 Open 起累计；非增量
    nonce: u64,                  // 单调递增
    expires_at: u64,             // block height
    usage_digest: [u8; 32],      // keccak256(usage_log)
    signature: [u8; 65],         // secp256k1 (r,s,v)
}
```

**关键设计**：cumulative 而非 increment —— 最新一张完全覆盖旧的，断电重连不丢账。

**Runner 端**（计划 §4.4）：runner-node 新增 `session/` 模块 + axum HTTP server：
1. 监听链上 `SessionOpened` 事件 → 本地 `SessionManager` 缓存 `LocalSession`（`v_max` / `payer` / `deposit` / `expires_at`）
2. HTTP 入口（`POST /chat` / `/http` / `/mcp`）：
   - 缺 `Authorization: Payment` header → `402` + `WWW-Authenticate: Payment realm="cowboy", session_actor=0x0C, price_advert=...`
   - 校验 voucher 5 项 → `executors.get_executor(job_type).execute(&job_spec)` → `200 OK + Payment-Receipt`
3. Settlement scheduler：周期 / 阈值 / 临近过期 → `chain_client.submit_session_settle(id, v_max)`；session 关闭 → finalize
4. **执行器复用**：`runner-llm` / `runner-http` / `runner-mcp` 不变；只是不再从 chain 拉 `JobSpec`，改从 HTTP body 拉

---

## Settlement 分润（复用 CIP-3 SettlementConfig）

Settle 时刻按 governance actor `0x09` 中的 `SettlementConfig`（默认 89/10/1）分配 `increment = voucher.cumulative_amount - session.spent`：

| 接收方 | 占比 | 路径 |
|---|---|---|
| Runner | 89% | escrow → runner |
| Burn (`0x00`) | 10% | escrow → burn |
| Treasury (`0x08`) | 1% | escrow → treasury |

**完全复用** `verifier.rs:351-465` 的 settlement 实现 —— `Session.handle_session_settle` 调用同一 governance 读取 + 同一 payout 模板，governance 调整时 session 与单 Job 路径同步生效。详见 [[settlement-slashing]]。

---

## 与 CIP-2 / CIP-7 的关系

### vs CIP-2 Job-Submit

CIP-2 既有的「按 Job 单笔托管 → commit-reveal → 链上 settle」**不动**，作为 dispute 仲裁 fallback。Session 是叠加的 fast path：

| 维度 | CIP-2 单 Job | MPP Session |
|---|---|---|
| 链上 tx / N 次调用 | N | 3（Open + Settle + Finalize） |
| Verification | 默认 commit-reveal + N-of-M | 乐观 `ecrecover`，可选 dispute 走 CIP-2 |
| 适用 | 单次高价值（如审计、共识结果） | 高频微付费（LLM token、流式 API） |
| Stake | Runner 1.5× max_job_value | Runner 仍需注册 + stake；session 不直接绑 stake 倍数 |

仲裁路径**完全复用** `Result Verifier 0x03` + commit-reveal + slashing —— 没有引入新共识机制。

### vs CIP-7 Simple Stream

二者**正交**，可共存：

| 维度 | CIP-7 Stream | MPP Session |
|---|---|---|
| 计价 | 按时间段（epoch 续费） | 按消耗（cumulative voucher） |
| 资金 | epoch 提前付 | deposit 一次，voucher 累积扣 |
| Use case | 直播 / 订阅（Substack 风格） | LLM 推理 / API（OpenAI 风格） |

CIP-7 草案文本中 Stream Key Manager 占用 `0x06`，但代码已把 `0x06` 给 `DUAL_BASEFEE` —— CIP-7 与 MPP Session 都需要在 `0x0C+` 重新选址。

---

## 安全 / DoS 考量（研究文档 §5.7）

| 攻击 | 缓解 |
|---|---|
| Payer 不签 voucher 但持续请求 | Runner 侧拒 ≥1 笔未支付请求；强制每次带 voucher |
| Runner 收钱不干活 | dispute 路径 + Runner stake；payer 调 `CloseSession` 进入 dispute window |
| Voucher 重放 | nonce 单调；Settle 时校验 `voucher.nonce > session.last_voucher_nonce` |
| Payer 在 settle 前提走 deposit | Open 时立即被 SESSION_ACTOR 锁定 |
| 过期 voucher | Settle 时 `voucher.expires_at >= current_block`（block height 单位） |
| Runner DDoS | rate limit + 拒绝 `voucher_amount` 增量 < `min_increment` |
| Payer 私钥泄露 | session `max_amount` 上限封顶损失 |

---

## PoC 范围与待澄清（计划 §3.6 / §10）

**PoC 不做**：
- `handle_session_slash` 返回 `ExecutionError::Unsupported`，二期才接入 CIP-2 Verifier 仲裁
- 不接入 CIP-20 token 作 session 资产（`SessionAsset::Cip20` 留空壳）
- 不做跨链 session bridge

**待澄清**：
- **EIP-712 `domain.chainId`** 来源 —— 当前代码在哪定义？
- **`price_advert` 上链程度** —— 计划折中只存 `[u8; 32]` digest；产品如要求审计需扩为完整结构
- **`expires_at` 单位** —— 计划选 block height（与 `DISPUTE_WINDOW_BLOCKS` 同源）
- **Session ID 生成** —— 计划由 payer 在 Open 时提供 `keccak256(payer ‖ runner ‖ nonce ‖ block_height)`，链上仅校验 `!exists(session_id)`

---

## 相关
- [[../entities/system-actors]] —— SESSION_ACTOR 0x0C 与 ROUTE_REGISTRY 0x0C 冲突详情
- [[../parameters]] —— SystemInstruction Opcode 主分配表（含本提案 52-57 与 v2 系列冲突）
- [[runner-verification]] —— commit-reveal 仲裁 fallback 路径
- [[settlement-slashing]] —— SettlementConfig 89/10/1 共享
- [[../drift]] —— V-11 (`0x0C` 撞 ROUTE_REGISTRY) / V-12 (opcodes 52-57 撞 CIP-13/23 v2)

## 源文档冲突 / 漂移

研究/计划提议 `0x0C` + opcodes 52-57 全部撞已发布 v2 系列分配（CIP-14 v2 系统 actor / CIP-13 v2 opcode 主分配表 / CIP-23 v2 opcodes 57-60）。这是**研究阶段未对齐 v2 alignment round 6** —— 实施前必须重排到 free range（≥0x10 系统 actor / ≥68 opcode），并起 CIP 草案纳入主分配表。详见 [[../drift]] v2 precondition gap 段。

## Sources
- `refs/runner/2026-04-28_MPP_Session_Research.md` —— MPP 协议解读 + Cowboy Session Actor 设计 + dispute 路径 + 战略定位
- `refs/plans/2026-05-06_mpp_session_implementation.md` —— 研究文档 §5–§6 的工程任务表（types / handler / runner daemon / CLI / 示例 / 验收）
- `node/execution/src/runner/dispatcher.rs:678-708` —— 复用的 escrow 模板
- `node/execution/src/runner/verifier.rs:351-465` —— 复用的 settlement payout 模板
- `node/types/src/constants.rs:142-232` —— `DISPUTE_WINDOW_BLOCKS=75` 复用
- `refs/cips/cip-7-simple-stream-protocol.md` —— 正交对比（按时间 vs 按消耗）
