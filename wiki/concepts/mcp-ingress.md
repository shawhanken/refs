---
type: concept
tags: [mcp, ingress, gateway, jsonrpc, agents, cip-19, cip-14, cip-15, cip-18, draft]
sources:
  - refs/cips/cip-19-gateway-mcp-ingress.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-15-public-asset-hosting.md
  - refs/cips/cip-18-payments.md
last_updated: 2026-05-11
status: draft
---

# Gateway MCP Ingress（CIP-19）

## 概述

CIP-19 让每个 CIP-14 actor **自动成为 MCP（Model Context Protocol）server**：Gateway 在 `https://<actor>.cowboy.network/_cowboy/mcp` 端点 terminate MCP streamable HTTP (spec `2025-11-25`)；`tools/list` 从 CIP-15 路由表自动派生（每个 Method-target route 即一个 tool）；`tools/call` 翻译为 CIP-14 既有 query/command dispatch；付款 gating 复用 CIP-18 wire 格式（错误码 `-32402` + credentials in `_meta`）。**Actor handler 代码完全不变** —— 它依旧看到 `HttpRequestEnvelope`，不知道自己被 MCP 调用。

**当前状态**：Draft（2026-04-28）。v1 范围明确不做：MCP resources / prompts / streaming results / server-initiated sampling / 工具名自定义。

---

## 为什么 Gateway-terminated，而非 runner-terminated

| 设计 | 优 | 劣 |
|---|---|---|
| **Gateway terminate**（本 CIP） | 复用既有 DNS-addressable 边缘；付款只在一处实现；actor 自动成 MCP 而无需第二张声明表 | Gateway 需多一份 MCP 实现 |
| Runner terminate（反方案） | actor 显式声明工具集 | 把 runner 推到公网；CIP-18 付款逻辑要复制；CIP-14 架构假设作废 |

选 Gateway 路线。`tools/list` 与 CIP-18 OpenAPI 文档**同源**（CIP-15 路由表），HTTP 与 MCP 视图永远不漂移。

---

## `ingress.mcp` Entitlement（**新**）

```
EntitlementGrant {
    id: "ingress.mcp",
    params: {
        "server_name":            string?,   // overrides default
        "server_instructions":    string?,   // shown in initialize.result.instructions
        "tool_name_prefix":       string?,   // namespace, e.g. "myapp_"
        "exclude_routes":         [string]?, // method names not to expose
        "max_tool_input_bytes":   u32?       // governance default if omitted
    }
}
```

**前置**：actor 必须同时持 `ingress.http`（CIP-14）。
**组合**：与 `payment.gate`（CIP-18）共存时，路由的 `pays = "caller"` 字段自动迁移到 MCP 路径 —— 走 §12 付款流。
**注册**：新条目，需加入 entitlement registry（[[../drift]] V-15）。

---

## MCP 端点契约

| 维度 | 值 |
|---|---|
| URL | `https://<actor>.cowboy.network/_cowboy/mcp` |
| Transport | MCP streamable HTTP (替代旧 HTTP+SSE) |
| Protocol version pin | `2025-11-25` |
| Methods | `POST`（请求） + `GET`（可选 SSE 流） + `DELETE`（结束 session） |
| Session header | `Mcp-Session-Id`（initialize 时颁发） |
| Idle timeout | `MCP_SESSION_IDLE_TIMEOUT_SECONDS = 600` |
| Reserved | 不参与 CIP-15 路由 resolve；Gateway 直拦 |

`initialize` 响应只 advertise `capabilities.tools.listChanged: true`（不 advertise resources / prompts / sampling）。

---

## `tools/list`：从 CIP-15 路由表派生

1. 读 actor 在 `__cowboy/routes` 的路由表（走 CIP-15 §8.12 Gateway→Runner fetch）
2. 过滤：`target.kind == "method"` + `enabled` + 不在 `exclude_routes`
3. 按 `target.name` 分组 —— 每个唯一 method name 出一个 tool
4. 校验组内 schema 兼容（path 参数 + body）；不兼容 → 整组丢弃 + warning
5. 构 `Tool { name, description, inputSchema, _meta.cowboy{verb, path, pays, price} }`

**Tool name**：`tool_name = prefix + sanitize(route.target.name)`，`sanitize` 把非 `[a-zA-Z0-9_]` 替换为 `_`（典型 `users.get` → `users_get`）。

**保留 prefix**：`_cowboy_*` —— 系统工具命名空间（`_cowboy_payment_quote` / `_cowboy_payment_subscribe` / `_cowboy_pass_purchase` / `_cowboy_health` / `_cowboy_info`，v1 仅保留，未实装）。

**`tools/list_changed` 通知**：路由 state_root 变化时通过 SSE 流推（`TOOLS_LIST_CHANGED_DEBOUNCE_MS = 250`）。Cache key = `(actor, routes_state_root)`，复用 CIP-14 §10 块级失效。

---

## `tools/call`：Dispatch 契约

请求示例：

```json
{
  "method": "tools/call",
  "params": {
    "name": "users_get",
    "arguments": { "user_id": "abc123", "verbose": "true" },
    "_meta": { "payment-authorization": "<base64url-mpp>" }   // optional
  }
}
```

Gateway 翻译为合成 `HttpRequestEnvelope`：

- `verb` ← route.verb（`ANY` 默认按 `POST`）
- `path` ← 用 `arguments` 替换 `{param}`（URL-encoded，防 `..` / 多余 `/` 注入）
- `query` ← `arguments` 中按 OpenAPI 划分的部分
- `body` ← 其余 args 按 OpenAPI 序列化（默认 JSON）
- `headers` ← 合成最小集（`content-type` / `accept` / `X-Cowboy-Mcp-Session-Id`）

**Dispatch**：复用 CIP-14 §8 —— 安全动词（`GET`/`HEAD`）走 `read_handler`（无共识），其它走 `GatewayRegistry.dispatch()`（命令路径 + 共识）。

**响应映射**：
- `Content-Type: application/json` → 单 `text` content + `structuredContent` 平行字段
- `text/*` → `text` content
- `image/*` / `application/octet-stream` → `image` / `resource` content
- 超过 `MAX_TOOL_OUTPUT_BYTES = 4 MiB` → 截断 + `isError: true` + `_meta.cowboy.truncated`
- HTTP 5xx → JSON-RPC `code = -32603`
- HTTP 4xx (非 402) → `result.isError = true`，正常响应帧
- 网络 / 超时 → JSON-RPC `code = -32000`

---

## 付款（复用 CIP-18 §13）

`pays = "actor"`（CIP-15 默认）：无需 credential，Gateway 用 actor 热钱包付。

`pays = "caller"` 无 credential：

```json
{ "error": {
  "code": -32402, "message": "Payment Required",
  "data": {
    "challenges": [ { "id":"...", "realm":"...", "method":"cowboy", "intent":"charge",
                      "expires":"...", "request":"<base64url(JCS-JSON)>" } ],
    "x402_compat": { "accepts": [ ... ] }
  }
}}
```

`pays = "caller"` 带 credential（`_meta.payment-authorization` = base64url MPP credential）：normalize → PaymentIntent → PaymentGate verify + settle → dispatch → receipt 进 `result._meta.payment-receipt`。`intent="pass"` / `"subscription"` 与 `"charge"` 共享 `_meta` 字段，按 CIP-18 §7.5 fallback chain 评估。

详见 [[payments]]。

---

## 关键常量

详见 [[../parameters]] §MCP Ingress。

| 常量 | 值 |
|---|---|
| `MCP_PROTOCOL_VERSION` | `"2025-11-25"` |
| `MCP_SESSION_IDLE_TIMEOUT_SECONDS` | 600（10 min）|
| `MAX_TOOL_INPUT_BYTES_DEFAULT` | 1 MiB |
| `MAX_TOOL_OUTPUT_BYTES` | 4 MiB |
| `JSONRPC_PAYMENT_REQUIRED_CODE` | -32402 |
| `JSONRPC_INTERNAL_ERROR_CODE` | -32603 |
| `JSONRPC_GATEWAY_DISPATCH_FAILED` | -32000 |
| `TOOLS_LIST_CHANGED_DEBOUNCE_MS` | 250 |

---

## 与 v1 Cowboy 的关系

| 现有 | 与 CIP-19 |
|---|---|
| CIP-14 v2 | dispatch 路径完全复用；CIP-19 只加 Gateway 前 transport 层 |
| CIP-15 v2 | 路由表是 tool list 唯一来源；CIP-15 implementation 草案中 P1 即放置 tool name 字段 |
| CIP-18 | 付款字段 + 错误码 + receipt 三件套照搬 |
| `runner-mcp` crate | **完全无关** —— 这是 actor **消费**外部 MCP server，与本 CIP（actor **作为** server）正交 |
| CIP-6 SDK | 不需要 actor 端改动；SDK 仍只看 `@http.handler` |

---

## 安全要点

- **Tool name collision**：保留 `_cowboy_*` 前缀拦截 actor 冒充系统工具；冲突路由从 list drop + warning
- **Path-param injection**：参数 URL-encode 才插 `route.path`，杜绝 `..` / 多余 `/`
- **Payment replay over MCP**：复用 CIP-18 nonce，提交同一 credential 跨 HTTP+MCP 只 settle 一次
- **Session hijacking**：`Mcp-Session-Id` 与 TLS 终端绑；跨 TLS endpoint 直接拒
- **Tool input size**：`MAX_TOOL_INPUT_BYTES` 在 dispatch 前 bound
- **Schema mismatch DoS**：低优先级路由想方设法注入 schema 冲突 → 整组 deterministically drop，不污染 `tools/list`
- **Server-initiated requests disabled**：v1 不 advertise `sampling`/`notifications`，恶意客户端无法诱导回调

---

## 反向兼容

完全 additive。无 `ingress.mcp` 的 actor 不暴露 MCP 端点；有的话只要 CIP-15 路由表已就位即生效（零代码改动）。`/_cowboy/mcp` reserved path 自 CIP-18 §17 已保留；本 CIP 给它定语义而非新增。

---

## 相关

- [[dns-addressable-actors]] — CIP-14 v2 HTTP ingress 基础
- [[public-asset-hosting]] — CIP-15 v2 路由表（tool 来源）
- [[payments]] — CIP-18 付款 wire 格式与 PaymentGate
- [[../entities/gateway]] — Gateway 担任 MCP terminator
- [[../parameters]] — MCP Ingress 常量段

## Sources

- `refs/cips/cip-19-gateway-mcp-ingress.md` — Draft 2026-04-28；20 sections（entitlement / endpoint / initialize / tools/list / tools/call / payment / security / rationale / future / backwards-compat）
- `refs/cips/cip-18-payments.md` §13 — MCP JSON-RPC 付款 transport
- `refs/cips/cip-15-public-asset-hosting.md` §6 / §8.12 — routes table + Gateway-Runner state fetch
