---
type: concept
tags: [ingress, gateway, dns, routing, cip-14]
sources:
  - refs/cips/cip-14-dns-addressable-actors.md
last_updated: 2026-04-20
status: draft
---

# DNS-Addressable Actors (CIP-14)

Ingress routing layer that makes Cowboy actors reachable over the public internet by HTTP. Core primitives: a new `ingress.http` entitlement, a Route Registry system actor, a Gateway ingress role, and a canonical HTTP request/response envelope split across a **query path** (read-only, no consensus) and **command path** (state-mutating, consensus-required).

---

## 核心三件套

| 组件 | 位置 | 职责 |
|---|---|---|
| `ingress.http` entitlement | Entitlement Registry (`0x07`) | 声明 Actor 接受 HTTP 入口流量 + 参数（methods / sizes / `max_query_cycles`）|
| **Route Registry** | 系统 Actor `0x0011`（新地址）| `name → actor_address` 映射；注册 / 续费 / 转让 / 反查 |
| **Gateway Registry** | 系统 Actor `0x0012`（新地址）| Gateway 节点注册 + 心跳；命令路径 `dispatch()` 的系统中介 |

> **注**: `0x0011` / `0x0012` 超出了原 System Actor 表 `0x01-0x0B` 的范围。见 [[../entities/system-actors]]。

---

## Query vs Command（两条执行路径）

| 路径 | 方法 | 执行 | 一致性 | 延迟 | 计费 |
|---|---|---|---|---|---|
| **Query** | `GET` / `HEAD` | Gateway 本地节点 `queryActor` RPC，PVM 在已提交状态上只读执行 | 最终一致；`X-Cowboy-Block` 头返回块高 | < 100ms | Gateway 自吸收，Actor 不计费 |
| **Command** | `POST` / `PUT` / `PATCH` / `DELETE` | Gateway 以自身签名交易通过 `GatewayRegistry.dispatch()` 系统中介提交；Actor `http.request` handler 在共识中执行 | 强一致（共识）| ~1s 块延迟 + 客户端轮询 `/_cowboy/requests/{id}` | Gateway 用 stake 付费，自 serving pool 回收 |

**Query 路径副作用强制 trap**: Actor 在 query 期间调用 `send_message` / `set_storage` / `submit_task` 等 12 类 syscall 立即 trap `ERR_QUERY_NO_SIDE_EFFECTS`（§8.3.1 normative list）。**不是** 默默丢弃，防止"query 与 command 分叉"的隐性 bug。

---

## 规范性契约

- **Subdomain 优先命名**: `<name>.cowboy.network` 为 v1 命名空间；自定义 TLD 延迟至 CIP-16。
- **系统中介 dispatch**: Command 路径下 Actor 收到的 `ctx.sender == GATEWAY_REGISTRY_ADDRESS (0x0012)`。SDK（CIP-6）的 `@http.handler` 装饰器必须默认校验该字段，防伪造的 `http.request` 消息。
- **保留路径**: `/_cowboy/*`（`/requests/{id}` / `/health` / `/info`）由 Gateway 拦截，Actor handler 禁占。
- **Router Actor 模式**: 推荐最佳实践 —— 用稳定的 router proxy 代理到可替换的实现 Actor，避免 `set_actor` 重新指向造成短暂不可用。非协议强制。

---

## Gateway 作为新 Ingress 角色

CIP-10 明确 Runner 容器是 "egress only"；CIP-9 Relay Node 是哑分片存储。Gateway 填补了协议第一个 **ingress** 节点角色：

- TLS 终止（ACME）、DNS 解析（`*.cowboy.network` 的 anycast / geo-DNS）
- 维护全/剪枝状态用于本地 query
- 执行 entitlement 强制（`max_request_bytes` / `max_response_bytes` / `max_query_cycles`）
- 速率限制（`MAX_REQUESTS_PER_SECOND = 100` per actor per gateway）

与 Runner / Validator / Relay Node 完全独立的 staking、健康、激励模型。单台物理节点可并行多角色。

**已知经济漏洞**: Gateway serving pool 按 `stake × uptime` 分配，与请求量解耦 —— 短期可接受（鼓励节点上线），长期有 free-rider 风险，拟由后续 per-request 付费 CIP 解决。

---

## 与现有系统的关系

| 现有 | 与 CIP-14 的关系 |
|---|---|
| CIP-2（Runner framework）| Query 路径调用的 `queryActor` RPC 来自 Milestone 2 §5.2；非 CIP，外部规范引用 |
| CIP-3（双 gas）| Query 路径沿用 PVM cycle 计量；命令路径沿用 basefee + 交易费 |
| CIP-9（Public volumes）| v1 仅 ingress 路由；公共资产 serving 分离至 [[public-asset-hosting]]（CIP-15）|
| CIP-6 SDK | `@http.handler` 装饰器 **MUST** 默认附加 `ctx.sender` 校验 + command 结果存储帮助器 |
| CIP-16 | 扩展 Route Registry 至 `.cow` / `.cowboy` TLD 与外部自定义域名 |

---

## 源文档冲突 / 漂移

- **新地址 `0x0011` / `0x0012`** 超出 wiki `entities/system-actors.md` 原列 `0x01-0x0B`；已在实体页增列。
- CIP-14 §8.3 引用 "Milestone 2 §5.2 `queryActor`" —— 非 CIP 命名规范文档，若其签名演进 Gateway 必须跟进。
- CIP-14 §7.5 `BLOCKS_PER_YEAR = 31,536,000` 假设 1 block/sec；若实际块时间变更（见 `refs/plans/block-time-*`），`NAME_GRACE_PERIOD` / `NAME_AUCTION_DURATION` 折算需重算。

---

## 相关

- [[../entities/gateway]] — Gateway 节点角色实体页
- [[../entities/system-actors]] — `0x0011` / `0x0012` 表条目
- [[public-asset-hosting]] — CIP-15：静态资产从 CIP-9 volume 直服
- [[custom-domains]] — CIP-16：`.cow` / `.cowboy` / 外部 FQDN
- [[../parameters]] — Route Registry / Gateway 参数段

## Sources

- `refs/cips/cip-14-dns-addressable-actors.md` — 规范（Draft, 2026-03-07, Requires: CIP-2, CIP-3）
