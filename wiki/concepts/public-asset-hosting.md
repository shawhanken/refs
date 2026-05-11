---
type: concept
tags: [ingress, gateway, static-assets, cip-15, cip-9, cors]
sources:
  - refs/cips/cip-15-public-asset-hosting-v2.md
  - refs/cips/cip-15-gateway-implementation.md
  - refs/cips/cip-14-dns-addressable-actors-v2.md
  - refs/cips/cip-9-runner-storage-v2.md
  - refs/cips/cip-18-payments.md
last_updated: 2026-05-11
status: draft
---

# Public Asset Hosting (CIP-15 v2)

Extends CIP-14 v2 so that Gateways serve static files (HTML/CSS/JS/images/fonts) directly from **CIP-9 public volumes**, bypassing the actor's `http.request` handler. Core primitive: a **route manifest** stored on-chain at `STORAGE_MANAGER (0x0A)` (per-actor) that declares which URL paths go static vs. dynamic.

> **v1 → v2 主要变更**：`ingress.static` 独立 entitlement（不再嵌套在 `ingress.http`，避免 `ParamValue` 不支持的嵌套 object 数组）；CBFS 命名 `Visibility::Public`（v1 错写 `PUBLIC_READ`）；route_manifest / cors_config 移到 `STORAGE_MANAGER` 下普通 ActorMessage（不是 SystemInstruction）；严格优先级 `min(dynamic_routes.priority) > max(static_routes.priority)` 在 `update_route_manifest` 验证时强制；`X-Cowboy-Manifest-Root` 与 `X-Cowboy-Block` 双版本头；CORS 优先级修正（dynamic 路径下 actor-set headers 优先）；状态映射对齐 CIP-9 既有 `ACTIVE/GRACE_PERIOD/DELETED/GARBAGE_COLLECTING`，**不引入** `DELINQUENT`；CBFS Merkle 直接复用（避免 Bitcoin-style padding 的 CVE 模式）。

---

## 为什么要有它

CIP-14 v2 下一切 HTTP 请求（包括 `GET /style.css`）都走 `read_handler` → Actor handler → PVM cycles。典型 Web 应用 80–95% 请求是不变的静态资产：浪费 Actor 的 `max_query_cycles` 预算与 Gateway 计算。CIP-15 v2 把这类请求完全从 Actor 路径抽离：

- **Zero PVM cycles**: Gateway 直读 volume / 本地缓存，Actor 永不被唤醒
- **Atomic deploy**: 路由规则与资产可分别原子更新（`update_route_manifest` 与 CIP-9 `commit_manifest` 独立）
- **CDN 级别表现**: Gateway 本地 LRU cache + ETag (`b3_<hex>`) + `Cache-Control`

---

## 核心机制

### 1. `ingress.static` entitlement（独立，非 `ingress.http` 子参数）

| 参数 | 默认 | 作用 |
|---|---|---|
| `static_volume_names: StrArray` | required（必填）| Gateway 可访问的 public volume 名列表（≤ 8）|
| `max_static_response_bytes: Uint` | 10 MiB | 单资产响应上限（协议 ceiling 100 MiB）|
| `max_cache_bytes_total: Uint` | 100 MiB | Gateway 缓存配额（advisory，operator 可调）|

**部署时校验**：每个 `volume_name` 必须是本账户的 `Visibility::Public` volume；CIP-9 §11.1 给出 `volume_id = keccak256(account_address || volume_name)`，部署时直接计算并查 `STORAGE_MANAGER`。

**共生约束**：`ingress.static` 只在与 `ingress.http` 同时声明时有意义，单声明 `ingress.static` 部署时拒绝。

### 2. 路由清单（on-chain，**不在 volume 内**）

存于 `STORAGE_MANAGER (0x0A)` 下，按 `actor_address` 索引。actor owner 通过 `update_route_manifest(actor_address, manifest_bytes)` 普通 ActorMessage（不是新 SystemInstruction）更新；handler 校验 `tx.sender == actor.owner`。

```
GET /api/users   → dynamic route (priority 100) → Actor handler
GET /assets/*    → static route  (priority 10)  → volume lookup
GET /about       → static route  (priority 0)   → SPA fallback → index.html
```

**严格优先级（v2 §4.3）**：`update_route_manifest` 校验时强制 `min(dynamic_routes.priority) > max(static_routes.priority)`，违反返回 `ERR_ROUTE_PRIORITY_INVERSION`。这把"dynamic 路径不会被 static fallback 静默吃掉"做成结构性保证而非best-effort。

### 3. Gateway → Relay Node fetch（CIP-9 v2 amendments）

1. 通过 `ManifestCommitted` 链上事件（**CIP-9 v2 §4 AMEND 9-H**）触发 eager invalidation；polling `MANIFEST_POLL_INTERVAL = 6` blocks 作为 floor
2. 调 Relay Node `GET_MANIFEST(volume_id)`（**CIP-9 v2 §2 AMEND 9-G**）一次拿全 manifest（不再是 K shard 重建）
3. 并发取 K 份 shard（含 `HEDGE_THRESHOLD_MS = 100ms` 的投机请求），Reed-Solomon 重建
4. 验证三级完整性（CBFS canonical Merkle = **power-of-2 padded BLAKE3 binary Merkle**，**非** RFC-6962（早先描述错），**非** Bitcoin-style duplicate-last-leaf；CIP-9 v2.r2 §3 pin 为 `cbfs/manifest/src/merkle.rs:32-66`，叶子 = `BLAKE3(bincode(ManifestEntry))`，缺时用 `ContentHash([0u8;32])` pad 到 2 的幂，再 bottom-up `BLAKE3(left||right)`）：
   - Manifest 对 on-chain `manifest_root`（BLAKE3 Merkle）
   - 每个 shard 对 `shard_hash`（BLAKE3）
   - 重建对象对 `content_hash`（BLAKE3）

### 4. 双版本号头（v2 §5.1）

静态响应**必返**两个头，避免 Gateway 把 `body @ manifest_root_N-1` 配上 `X-Cowboy-Block: N` 的版本错位：

```
X-Cowboy-Block:          <committed block height>
X-Cowboy-Manifest-Root:  <hex(manifest_root)>
X-Cowboy-Volume:         <volume_name>
X-Cowboy-Source:         "static" | "dynamic"
```

客户端可用 `X-Cowboy-Min-Block: N`（CIP-14 既有）+ `X-Cowboy-Manifest-Root: <hex>` 请求头双重 pin。

### 5. Storage 状态映射（v2 §5.3，复用 CIP-9 既有 status，**不引入新 `DELINQUENT`**）

| `StorageCommitment.status` | Gateway 行为 |
|---|---|
| `ACTIVE` | 正常返回 |
| `GRACE_PERIOD` | 正常返回 + advisory header `X-Cowboy-Storage-Status: grace` |
| `DELETED` | `503` + `X-Cowboy-Error: VOLUME_DELETED` |
| `GARBAGE_COLLECTING` | `410 Gone` + `X-Cowboy-Error: VOLUME_GC` |

`GRACE_PERIOD` 仍服务因为：CIP-9 既有窗口给 owner 补费的机会；abrupt 503 用户体验差。`GARBAGE_COLLECTING` 不可逆，必停。

### 6. CORS（v2 §7，优先级修正）

`cors_config` 同样存 `STORAGE_MANAGER` 下，actor owner 通过 `update_cors_config` ActorMessage 更新。

**Dynamic 路径优先级（v2 §7.3，反 v1 §9.4）**：
1. Actor handler 在 `HttpResponseEnvelope` 自带 `Access-Control-*` 头 → Gateway **原样透传**
2. 否则 → Gateway 应用 `cors_config` 规则
3. 否则 → 不加 CORS

**Static 路径**：Gateway 应用 `cors_config`；无配置时用宽松默认（`Allow-Origin: *`、`GET/HEAD/OPTIONS`）。

`OPTIONS` preflight 始终由 Gateway 直答，不浪费 cycle。

---

## 规范性影响

- **`ingress.static` 是新 entitlement entry**（precondition）：CIP-14 v2 加 `ingress.http`、CIP-15 v2 加 `ingress.static`、CIP-16 v2 加 `dns.attach_external` —— 三者均需在 `node/types/src/registry.rs::REGISTRY` 添加 entry 才能激活。
- **CIP-9 amendments**：CIP-15 v2 真实需要 `GET_MANIFEST` RPC（AMEND 9-G）+ `ManifestCommitted` 事件（AMEND 9-H）+ canonical manifest serialization pin to CBFS Merkle（AMEND § 9-3）。**早先轮次 v1 `alignment-conventions.md` 错把 `StorageCommitment` / `commit_manifest` / `volume_id = keccak256(...)` 也列为 amendment** —— 这些其实 CIP-9 §11.1/§12.2 已经有；CIP-9 v2 §9 errata 已修正。
- **路由 / CORS 是 ActorMessage，不是新 SystemInstruction**：用 STORAGE_MANAGER 既有 actor 的普通 message handler 即可，sender 检查由 handler 自管 —— 不消耗 opcode 空间。

---

## 经济模型

Gateway 按量读取 shard 但**不**向 Relay Node 付 per-read 费用；Relay Node 的带宽成本被卷入 CIP-9 按 epoch 的 storage fee（类似 CDN 源站模型）。Volume 拥有者停付 storage fee → CIP-9 状态机自然进入 `GRACE_PERIOD → GARBAGE_COLLECTING`，Gateway 按 §5.3 表自动停服，杜绝"免费 CDN externality"。

**Relay Node 侧防滥用**（非协议强制，节点本地策略）:
- Per-IP `MAX_SHARD_READS_PER_SECOND = 1000`（建议值）
- Per-volume 每 IP `= 500`（建议值）

未来工作：actor-funded bandwidth budget 按实际读取量补偿 Relay Node，需 per-read accounting — v1 不合算。

---

## 源文档冲突 / 漂移

- CIP-9 实际已有 `Visibility::Public` / `StorageCommitment` / `commit_manifest` / `volume_id = keccak256(...)`；早先 v2 草稿误判，已由 CIP-9 v2 §9 errata 修正
- 真实需要的 CIP-9 amendments 仅 4 项：`GET_MANIFEST` / `ManifestCommitted` 事件 / canonical Merkle pin / status → HTTP 映射表 —— 见 [[../drift]]
- CIP-9 §11.1 默认 1 block/sec 影响 `MANIFEST_POLL_INTERVAL` 折算；块时间变更需重算

---

## 实施 companion（CIP-15 Gateway Implementation）

`refs/cips/cip-15-gateway-implementation.md`（Living）是给 Gateway 实施者的 6-phase build order，非规范：

| Phase | 范围 | 依赖 |
|---|---|---|
| **P1** | Routes fetch + method-target dispatch | CIP-14 既有 |
| **P2** | Static volume serving (Volume targets) | CIP-9 `GET_MANIFEST` / `GET_SHARD` |
| **P3** | Runtime mutability (state_root re-poll) | P1 |
| **P4** | Payment gating (`pays = caller`) | **CIP-18** |
| **P5** | CORS / conditional requests / compression | P2 |
| **P6** | Hedging / parallel fetch / optimization | P2 |

**Phase 4 与 CIP-18 的 interlock**：companion §5 明确 CIP-18 未实装时建议 Gateway 路由含 `pays = "caller"` 时返回 `501 Not Implemented + X-Cowboy-Reason: cip18-required`，**禁止 Option B**（把 `caller` 路由暗暗当 `actor` 处理 —— 会让 actor 作者部署"声明付费实际免费"的端点，与文档分叉）。详见 [[payments]] / [[../drift]] V-16。

**Phase 1 实现里的两个 open question**（companion §9）：

- CIP-15 §8.12 `GET_STATE`（verifiable KV-with-proof read against Runner）—— companion 标注需 runtime team 确认是否已 expose；未存在则需 sibling CIP 落地
- Named-handler dispatch on CIP-14 query / command paths —— companion 标注需 runtime team 确认（既有非 HTTP 消息走的就是 named-handler，应已支持）

实现侧建议先 P1 替换"everything goes to `http.request`"为 verb-aware routing 端到端跑通，再上 P2 静态。

---

## 相关

- [[dns-addressable-actors]] — CIP-14 v2 基础 HTTP ingress
- [[payments]] — CIP-18 `pays = caller` 路径付款 wire 与 settle（Phase 4 依赖）
- [[mcp-ingress]] — CIP-19 把同一路由表当 MCP tools 列出
- [[../entities/gateway]] — Gateway 节点缓存 / fetch 协议
- [[../entities/system-actors]] — `0x0A` STORAGE_MANAGER / `0x13` PAYMENT_GATE
- [[../parameters]] — CIP-15 常量（`MAX_GATEWAY_CACHE_BYTES`, `MANIFEST_POLL_INTERVAL` 等）

## Sources

- `refs/cips/cip-15-public-asset-hosting-v2.md` — v2 spec（Draft, 2026-04-21）
- `refs/cips/cip-15-gateway-implementation.md` — 6-phase implementation handbook（Living, 2026-05-11）
- `refs/cips/cip-18-payments.md` §6.6 / §15 — `pays` 字段与 Gateway 付款 enforce
- `refs/cips/cip-9-runner-storage-v2.md` — v2 amendments（GET_MANIFEST §2 AMEND 9-G + ManifestCommitted §4 AMEND 9-H + canonical Merkle §3 + status mapping §5 + CIP-11 ref errata §10 + STORAGE_MANAGER 0x0A 落锁 §11）
- `refs/cips/cip-14-dns-addressable-actors-v2.md` — read_handler / IngressDispatch / target_pool enum 上下文
