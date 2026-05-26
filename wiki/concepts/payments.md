---
type: concept
tags: [payments, mpp, x402, gateway, paymentgate, cip-18, cip-14, cip-3, cip-20, draft]
sources:
  - refs/cips/cip-18-payments.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-15-public-asset-hosting.md
  - refs/cips/cip-19-gateway-mcp-ingress.md
  - refs/cips/cip-3-fee-model.md
  - refs/cips/cip-20-fungible-tokens.md
last_updated: 2026-05-11
status: draft
---

# Payments（CIP-18）

## 概述

CIP-18 为 DNS-Addressable Actors（CIP-14）补上**外部付款入口**：在 Gateway 边缘强制付款 / 在链上 `PaymentGate` 系统 actor 统一结算 / 四种付款模型（per-request、actor-funded、prepaid pass、epoch subscription）/ 两种 wire 格式并行（**MPP 主，x402 兼容**）/ 多资产（CBY + CIP-20 + 经 EVM 桥接 facilitator 引入的稳定币）。**当前状态**：Draft（2026-03-08 创建，2026-04-28 更新），未实装。

**两层模型**：

```
Presentation:  MPP (Authorization: Payment)  +  x402 (PAYMENT-SIGNATURE)
                            ↓ normalize ↓
Settlement:    PaymentIntent { method, intent, payer, recipient, asset, amount, binding }
                            ↓
                    PaymentGate (0x11)
```

一份 PaymentPolicy → 两种 wire 同时生效；PaymentGate 内部只看 PaymentIntent，不关心 wire 来源。

---

## PaymentGate（系统 Actor `0x11`，CIP-18 r2）

新系统 actor，genesis 部署，只由协议升级动。承载：PaymentPolicy 表 / 预算 / Pass / Subscription / nonce table / fee 分配。

> **地址段（CIP-18 r2，2026-05-11）**：原 CIP-18 §22 sequential-allocation 引用了 CIP-14 v1 老编号 `0x0011/0x0012` 并续到 `0x0013`；r2 修正为 v2 主表当前的单字节序列 —— `0x0C = SESSION_ACTOR`（code）/ `0x0D = ROUTE_REGISTRY`（CIP-14 v2.r2）/ `0x0E = GATEWAY_REGISTRY`/ `0x0F = RECEIPT_REGISTRY`/ `0x10 = CONTAINER_REGISTRY`（CIP-10 v2.r2）/ **`0x11 = PAYMENT_GATE`**。

### Handler API

| Method | 调用者 | 说明 |
|---|---|---|
| `set_policy(PaymentPolicy)` | actor owner | 创建 / 更新策略 |
| `get_policy(actor)` | 任意 | 公开读取 |
| `deposit_budget(actor, amount)` | 任意 | 注入 actor-funded 预算 |
| `withdraw_budget(actor, amount)` | actor owner | 收回预算 |
| `purchase_pass(actor, credits, beneficiary)` | 任意 | 一次买 N 笔通行证；从 caller 扣 `credits × per_request_price` |
| `purchase_epoch(actor, epochs, beneficiary, payer)` | 任意 | 时段订阅；幂等 rolling window（复用 CIP-7 模型）|
| `verify_payment(intent)` | Gateway | 不实际结算地校验 |
| `settle_payment(intent)` | Gateway | 原子转账 + 消耗 nonce |
| `deduct_budget(actor, amount, request_id)` | Gateway | 扣 actor-funded |
| `credit_inbound(BridgeEvidence)` | bridge facilitator runner | inbound EVM credit |

PaymentPolicy 含 `price_table: [PriceRule]`（path_pattern × methods × model × amount × asset，≤ `MAX_PRICE_TABLE_ENTRIES=100`），`accepted_assets: [AssetConfig]`（声明 MPP method + intents + x402 scheme + decimals/symbol，≤ `MAX_ACCEPTED_ASSETS=10`），以及 budget/epoch/pass 三个可选子配置。

---

## 四种付款模型

| 模型 | 触发 | 行为 |
|---|---|---|
| **per-request**（client-paid，baseline）| `pays = "caller"` + 客户端带 Authorization | Gateway 401-then-pay 流程：先 402 challenge → 客户端构 credential 重试 → Gateway verify + settle → 200 + Receipt |
| **actor-funded** | `default_mode = "actor_funded"` 且 actor 已 `deposit_budget` | Gateway 校验余额 + rate limit + daily cap → 调 `deduct_budget` → 直接分发；预算耗尽按 `BudgetConfig.fallback` 退到 `402`（client-paid）或 `503` |
| **prepaid pass** | 客户端持 `pass_id`（MPP `intent="pass"` 或 x402 `cowboy:pass`）| Gateway 校验 `pass_id` 存在 + 剩余 credits + 签名 → 扣 1 credit → 分发；过期 = `PASS_EXPIRY_BLOCKS=31_536_000` (~1y) |
| **epoch subscription** | 客户端有效 entitlement（先前 `purchase_epoch`）| Gateway 直接放行，无需 challenge；可选 `intent="subscription"` 校验或续约 |

**Hybrid fallback chain**（PaymentGate 评估顺序，先满足者赢）：
1. 端点 free（无规则匹配 / `default_mode="free"`）
2. 活跃 subscription 覆盖
3. 合法 pass + credits 剩余
4. actor budget 有余额 + rate-limit 头寸
5. 合法 per-request credential（MPP 或 x402）
6. → 返回 402 challenge（advertise 剩余可付模型）

---

## 双 Wire 格式

### MPP（primary）

Spec：IETF `draft-ryan-httpauth-payment`（Stripe + Tempo）。HTTP Authentication scheme name = `Payment`。

**402 challenge**：

```
WWW-Authenticate: Payment id="<hmac-binding>",
    realm="<actor>.cowboy.network",
    method="cowboy", intent="charge",
    expires="...", request="<base64url(JCS-JSON)>",
    digest="sha-256=:...:"
PAYMENT-REQUIRED: <base64(x402 schema)>   ; 并发放 x402 兼容
```

**Credential**：`Authorization: Payment <base64url(JSON{ challenge, source: did:cowboy:..., payload })>`

**Receipt**：`Payment-Receipt: ...` + `PAYMENT-RESPONSE: ...`（两种 wire 同发）

**Methods**：`cowboy` (native CBY + CIP-20) / `evm` (Permit2 + EIP-3009，需 facilitator) / `tempo` (保留)

**Intents**：`charge`（通用） / `pass` / `subscription`（Cowboy 域内 net-new）

**Binding**：`id = HMAC-SHA256(gateway_secret, realm|method|intent|request|expires|digest|opaque)`，by-Gateway，settle 时由 PaymentGate 校链上状态而非 binding。

### x402（compatibility）

Spec：Coinbase 已在 Base agent ecosystem 运行的 `PAYMENT-REQUIRED` / `PAYMENT-SIGNATURE` / `PAYMENT-RESPONSE` 头惯例。每个 402 同时发 MPP + x402 两份 challenge；客户端用任一格式重试，Gateway 接受第一个 validate 通过的，**绝不双扣**。

**Schemes**：`cowboy:exact` / `exact` (EVM) / `cowboy:pass` / `cowboy:epoch` —— 都映射回同一个 PaymentIntent。

---

## 入站 EVM 桥接 Facilitator（§12，**实现 deferred**）

`method="evm"` 路径需要新 runner 角色 + 新 entitlement `bridge.facilitate.evm`：watch EVM 链（Base/ETH/...）观察 EIP-3009 / Permit2 transfer → 校 nonce 与 Cowboy 上 PaymentGate 等值的 payment authorization → 提交 `credit_inbound(BridgeEvidence)` → PaymentGate mint/transfer 镜像 CIP-20 asset 并消耗 nonce。

`BridgeEvidence` 含 `chain_id / tx_hash / block_number / block_hash / log_index / payer / cowboy_payer / recipient / asset_evm / asset_cowboy / amount / nonce / confirmations / facilitator_sig`。`MIN_BRIDGE_CONFIRMATIONS_EVM=32`，`EVM_FINALITY_HEADROOM_BLOCKS=64`。

**与现有 Cowboy → ETH withdrawal bridge 对称**（Tony 团队既有 `CowboyLightClient.sol` / `CBYBridge.sol`）：runner host 可共用，entitlement 独立。

---

## 收入分配（§18）

```
per-request:
    total = actor_fee + protocol_fee + gateway_recovery
    protocol_fee     = floor(actor_fee × PROTOCOL_PAYMENT_FEE_BPS / 10_000)   ; 默认 500 = 5%
    gateway_recovery = command-path gas only; 0 for query path

pass / subscription:
    total = credits × per_request_price 或 epochs × fee_per_epoch
    protocol_fee     = floor(total × PROTOCOL_PAYMENT_FEE_BPS / 10_000)
    actor_receives   = total - protocol_fee
```

actor-funded 同样收 protocol_fee，但 actor 自己付。

---

## Discovery（OpenAPI + MPP `x-payment-info`）

Gateway 自动在 `/_cowboy/payment/openapi.json` 暴露 actor 的 OpenAPI 3.1 文档，paths 下 `x-payment-info` 标注每端点的 method / intent / amount / asset / currency。任何 MPP-aware agent（之前没听过 Cowboy）扫一眼就能调用。

---

## 与 CIP-14 / CIP-15 / CIP-19 的关系

| 现有 | 与 CIP-18 的关系 |
|---|---|
| CIP-14 v2 | 付款前提：必须先有 `ingress.http` entitlement；Gateway 在 CIP-14 §8 dispatch 前注入 payment check |
| CIP-15 v2 | Route schema 里 `pays = "actor"` / `"caller"` 字段 —— `caller` 即触发 CIP-18 流程；`gateway-implementation` companion §5 描述渐进激活 |
| CIP-19 | MCP 路径下付款拷贝走 JSON-RPC `_meta.payment-authorization`（CIP-18 §13），错误码 `-32402` |
| CIP-3 | 命令路径仍走 basefee + EIP-1559 tip；payment 是叠加在 gas 之上的「内容费」|
| CIP-7 | epoch subscription 直接复用 CIP-7 rolling-window 模型 + 幂等续约 |
| CIP-20 | accepted_assets 可声明 CIP-20 fungible tokens，包括桥接稳定币 |
| MPP Session ([[mpp-session]]) | MPP 协议的 `intent="charge"` 单笔模型由 CIP-18 覆盖；Session 模式（高频微付）仍是后续 CIP 工作，可与 CIP-18 PaymentGate 共存 |

---

## 新增 Entitlement

| ID | 持有者 | 说明 |
|---|---|---|
| `payment.gate` | Actor | 启用 PaymentGate；params 含 `accepted_methods` / `accepted_intents` / `max_price_per_request`；**前置**：actor 必须同时持 `ingress.http` |
| `bridge.facilitate.evm` | Runner | EVM 桥 facilitator；params 含 `chains` / `min_confirmations` / `facilitator_pubkey`；deferred |

两者均为新条目，需加入 `node/types/src/registry.rs::REGISTRY`（[[../drift]] V-15）。

---

## 关键常量

详见 [[../parameters]] §Payments。

| 常量 | 值 |
|---|---|
| `PAYMENT_GATE_ADDRESS` | `0x11`（CIP-18 r2 已对齐 v2 主表）|
| `PROTOCOL_PAYMENT_FEE_BPS` | 500（5%）|
| `MAX_PRICE_TABLE_ENTRIES` / `MAX_ACCEPTED_ASSETS` | 100 / 10 |
| `MAX_EPOCH_BLOCKS` / `DEFAULT_EPOCH_BLOCKS` | 2_592_000（~30d） / 86_400（~1d）|
| `PASS_EXPIRY_BLOCKS` / `MAX_PREPAID_CREDITS` | 31_536_000（~1y） / 1_000_000 |
| `PAYMENT_POLICY_CACHE_TTL_BLOCKS` | 1 |
| `MIN_BRIDGE_CONFIRMATIONS_EVM` / `EVM_FINALITY_HEADROOM_BLOCKS` | 32 / 64 |
| `JSONRPC_PAYMENT_REQUIRED_CODE` | `-32402` |

---

## 安全要点

- **Replay**：authorization `nonce` + `request_hash` + `valid_before/after` block-height 三重 bound；inbound bridge 共用同一 nonce 表防止 EVM-side 二次 claim
- **Cross-Gateway double-spend**：PaymentGate 原子消耗 nonce；并发 verify 但只有一家能 settle，输家自吸收 gas（动力学激励本地正确校验）
- **Cross-wire double-pay**：同一请求带 MPP + x402 双 header，Gateway settle 一次
- **HMAC binding**：客户端无法篡改请求体、recipient、amount 仍复用 `id`
- **Price manipulation**：Policy 变更下一块生效；single block 内 challenge-then-retry 价格不变
- **Bridge facilitator compromise**：多 runner quorum + 注册 facilitator key set + confirmations + governance 治理（同 withdrawal bridge）

---

## 反向兼容

完全 additive：不持 `payment.gate` 的 actor 不受影响；现有 CIP-14 通量保持 free / Gateway-subsidized。`/_cowboy/payment/*` 与 `/_cowboy/mcp` 不冲突现有 reserved paths。CIP-18 上一稿（2026-03-08 x402-only）未生产使用，不保留迁移路径。

---

## 相关

- [[dns-addressable-actors]] — CIP-14 v2 HTTP ingress 基础
- [[public-asset-hosting]] — CIP-15 v2 路由 `pays` 字段
- [[mcp-ingress]] — CIP-19 MCP 路径下的付款集成
- [[mpp-session]] — MPP 协议 Session 模式（与 charge 正交）
- [[../entities/system-actors]] — PaymentGate `0x11` / `0x10`
- [[../parameters]] — Payments 常量段

## Sources

- `refs/cips/cip-18-payments.md` — Draft 2026-03-08 / Updated 2026-04-28；MPP + x402 + PaymentGate + 4 models + EVM bridge + 24 sections
- `refs/cips/cip-15-gateway-implementation.md` §5 — `pays = caller` 在 Phase 4 渐进激活
- `refs/cips/cip-19-gateway-mcp-ingress.md` §12 — JSON-RPC `_meta.payment-authorization` 透传
