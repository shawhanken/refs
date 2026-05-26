---
type: concept
tags: [ingress, gateway, dns, routing, cip-14]
sources:
  - refs/cips/cip-14-dns-addressable-actors.md
last_updated: 2026-04-21
status: draft
---

# DNS-Addressable Actors (CIP-14 v2)

Ingress routing layer that makes Cowboy actors reachable over the public internet by HTTP. Core primitives: a new `ingress.http` entitlement, a Route Registry system actor at **`0x0D`** (CIP-14 v2.r2), a Gateway ingress role registered at **`0x0E`**, a Receipt Registry at **`0x0F`**, a canonical HTTP request/response envelope split across a **read-only path** (no consensus, via `read_handler` RPC) and a **command path** (state-mutating, system-mediated via `IngressDispatch` opcode 65).

> **v1 → v2 主要变更**：地址 `0x0011/0x0012` → `0x0D/E/F`（CIP-14 v2.r2 在 SESSION_ACTOR=`0x0C` 后单字节连续序列；r1 草案曾用 `0x0C/D/E`，因代码先 commit SESSION_ACTOR 而后移 +1）；`queryActor`（不存在）→ 新 spec 的 `read_handler` RPC；`_http/results/{id}` actor-KV → Receipt Registry `0x0F`；selector PVM 路由层保留提案撤销，改为 `ctx.sender` 检查；Gateway stake 与 operating balance 分离；`subdomain_policy` 默认改为 `OWNER_ONLY`；read-only trap 表补 `randomness`；费分配走 `system:registry_settlement_config` / `system:gateway_pool_config`（`UpdateSettlementConfig` opcode 40 + `target_pool` 枚举）。

---

## 核心四件套

| 组件 | 位置 | 职责 |
|---|---|---|
| `ingress.http` entitlement | Entitlement Registry (`0x07`)，作为新 entry 加入 | 声明 Actor 接受 HTTP 入口流量 + 参数（methods / sizes / `max_query_cycles` / `receipt_ttl_blocks`）|
| **Route Registry** | 系统 Actor `0x0D` | `name → actor_address` 映射；注册 / 续费 / 转让 / 反查 |
| **Gateway Registry** | 系统 Actor `0x0E` | Gateway 节点注册 + 心跳；命令路径 `dispatch()` 的系统中介 |
| **Receipt Registry** | 系统 Actor `0x0F` | HTTP 命令路径异步结果；单全局 prune 循环（不消耗 actor timer 预算）|

> **注**: 这四个 entitlement / 系统 actor entry 都是 v2 **precondition** —— 代码中尚未存在；激活前需在 `node/types/src/registry.rs` 加 entry + `node/runner/src/system_actors.rs` 加地址常量。详见 [[../entities/system-actors]]。

---

## Read-only vs Command（两条执行路径）

| 路径 | 方法 | 执行 | 一致性 | 延迟 | 计费 |
|---|---|---|---|---|---|
| **Read-only**（v1 称 query path）| `GET` / `HEAD` | Gateway 本地 `POST /actor/{address}/read_handler` RPC，PVM `read_only: bool = true` 对已提交状态执行；mutating syscall 全部 trap | 最终一致；`X-Cowboy-Block` 头返回块高 | < 100ms | Gateway operator 自吸收，Actor 不计费 |
| **Command** | `POST` / `PUT` / `PATCH` / `DELETE` | Gateway 用 operating account 签 TX，emit `IngressDispatch` (opcode 65)；`GATEWAY_REGISTRY=0x0E` 验 sender 是 active Gateway → 转发给目标 Actor；返回值由 `CompleteReceipt` (opcode 66) 写入 `0x0F` | 强一致（共识）| ~1s 块延迟 + 客户端轮询 `/_cowboy/requests/{id}` | Gateway operating account 付 gas（不动 stake）；可由 actor 用 `Action::UseOwnerBalance` 委派代付 |

**Read-only trap 表（CIP-14 v2 §5 + Part III §5.3）**: `state_set` / `state_delete` / `send_message` / `call_actor` / `schedule_timer*` / `cancel_timer` / `extend_timer` / `submit_job` / `token_transfer*` / `create_deferred_tx` / `upgrade_self` / `emit_event` / **`randomness`** —— 所有 mutating 或 non-deterministic syscall 立即 trap `ERR_READONLY_VIOLATION`。**不是** 默默丢弃，防止"read 与 command 分叉"的隐性 bug。`randomness` 在 v1 漏掉了，v2 补上 —— 否则两个 Gateway 在同一块高度可能因 RNG 给出不同响应。

---

## 规范性契约

- **Subdomain 优先命名**: `<name>.cowboy.network` 为 v1 命名空间；自定义 TLD 由 CIP-16 v2 扩展。
- **Sender 真实性 (v2 §6.2)**: Command 路径下 Actor 必须 `ctx.sender == GATEWAY_REGISTRY=0x0E`；SDK (CIP-6) `@http.handler` 装饰器默认附上检查，custom-bytecode actor 需显式包含。
  - **selector 保留撤销**：v2 早期草案曾提议 PVM 路由层把 `"http.request"` 设为系统保留 selector（任何非系统 sender → `ERR_RESERVED_SELECTOR`），后**撤销**（CIP-14 v2 §6.2 Note），原因：阻断了合法的 router actor 转发模式。改回 SDK-default sender 检查 —— `ctx.sender` 由协议消息路由器从 tx 签名者填入，不可被调用者代码伪造，handler 内部检查就足够。
- **保留路径**: `/_cowboy/*`（`/requests/{id}` / `/health` / `/info`）由 Gateway 拦截，Actor handler 禁占。
- **Subdomain 默认改为 `OWNER_ONLY`**（v1 默认 `ACTOR_MANAGED`）：避免任意子域 GET 都吃 actor `max_query_cycles` 的 DoS surface。
- **Router Actor 模式**: 推荐最佳实践 —— 用稳定的 router proxy 代理到可替换的实现 Actor。**`upgrade_self` syscall 同样可用**（需 `sys.upgrade` entitlement）；二选一，不混用。

---

## Receipt 模型（v2 §8）

替代 v1 SDK 约定的 actor-KV `_http/results/{request_id}` 模式。

为什么改：v1 让 actor 自己存 result + 注册 cleanup timer。任何热门 API actor 1k 个 pending request 即撞 `MAX_TIMERS_PER_ACTOR=1024`。

v2 设计：

- 系统 actor `RECEIPT_REGISTRY=0x0F` 集中存 `Receipt {request_id, target_actor, gateway, status, envelope, created_at, expires_at, private}`
- `IngressDispatch` 调用 actor handler 后，dispatcher 自动写 receipt
- LLM 等 async case 用 `complete_receipt(request_id, envelope)` opcode (66)，sender 必须 = `target_actor`
- `expires_at = created_at + receipt_ttl_blocks`（默认 3600，actor 可在 `ingress.http` 参数 `receipt_ttl_blocks` 调，上限 86400）
- **单一全局 prune 循环**按 `expires_at` 清理 —— actor timer 预算 0 消耗
- 客户端 `GET /_cowboy/requests/{id}` 通过 read_handler 读 `0x0F`，状态映射 200/202/404/410

---

## Gateway 作为新 Ingress 角色

CIP-10 明确 Runner 容器是 "egress only"；CIP-9 Relay Node 是哑分片存储。Gateway 填补了协议第一个 **ingress** 节点角色：

- TLS 终止（ACME）、DNS 解析（`*.cowboy.network` 的 anycast / geo-DNS）
- 维护全/剪枝状态用于本地 read_handler 执行
- 执行 entitlement 强制（`max_request_bytes` / `max_response_bytes` / `max_query_cycles`）
- 速率限制（`MAX_REQUESTS_PER_SECOND = 100` per actor per gateway）
- **Stake 与 operating balance 分离**：stake 锁在 `0x0E` 是 slashable 抵押；gas 用 operating account 付（参 WP-v2 Delta 1）

与 Runner / Validator / Relay Node 完全独立的 staking、健康、激励模型。单台物理节点可并行多角色。

**已知经济漏洞**: Gateway serving pool 按 `stake × uptime` 分配（`system:gateway_pool_config`），与请求量解耦 —— 短期可接受（鼓励节点上线），长期有 free-rider 风险，拟由后续 per-request 付费 CIP 解决。

---

## 与现有系统的关系

| 现有 | 与 CIP-14 v2 的关系 |
|---|---|
| CIP-2（Runner framework）| 共用 `submit_job` 异步框架（LLM 等 async response 走 `submit_job` + receipt）|
| CIP-3（双 gas）| `read_handler` PVM cycle 计量沿用 CIP-3；命令路径沿用 basefee + EIP-1559 tip |
| CIP-5 revised（Timer）| Receipt prune 是单 timer，replaces actor 千万级 cleanup timer |
| CIP-6 SDK | `@http.handler` 装饰器**MUST** 默认附加 `ctx.sender` 校验 + complete_receipt 帮助器 |
| CIP-9（Public volumes）| v1 仅 ingress 路由；公共资产 serving 分离至 [[public-asset-hosting]]（CIP-15 v2）|
| CIP-15 v2 | `ingress.static` 是独立 entitlement，与 `ingress.http` 共生（前者依赖后者）|
| CIP-16 v2 | 扩展 Route Registry 至 `.cow` / `.cowboy` TLD 与外部自定义域名 |

---

## 源文档冲突 / 漂移

- **新地址 `0x0D` / `0x0E` / `0x0F`** 在代码中尚未存在 —— v2 precondition；详见 [[../drift]]。
- **Entitlement registry 缺 `ingress.http`** —— `node/types/src/registry.rs:35-219` 当前 **15 entries**（实际数已修正）；激活 CIP-14 v2 需 + 1 entry。
- **opcode 65 / 66** 在 CIP-13 v2 §1 主表落锁；代码中尚未存在；同样是 precondition。

---

## 相关

- [[../entities/gateway]] — Gateway 节点角色实体页（`0x0E`）
- [[../entities/route-registry]] — Route Registry 实体页（`0x0D`）
- [[../entities/system-actors]] — `0x0D` / `0x0E` / `0x0F` 表条目
- [[public-asset-hosting]] — CIP-15 v2：静态资产从 CIP-9 volume 直服
- [[custom-domains]] — CIP-16 v2：`.cow` / `.cowboy` / 外部 FQDN
- [[../parameters]] — Route Registry / Gateway 参数段

## Sources

- `refs/cips/cip-14-dns-addressable-actors.md` — v2 spec（Draft, 2026-04-21）：read_handler RPC + IngressDispatch 65 + CompleteReceipt 66 + selector reservation 撤销 + stake/operating balance + receipt registry + target_pool enum + subdomain_policy 默认改 OWNER_ONLY
- `refs/cips/cip-14-dns-addressable-actors.md` (Part I) — v1 原文（2026-03-07）保留参考
- `refs/cips/cip-13-runner-delegation.md` §1 — opcode 主分配表
