---
type: concept
tags: [ingress, gateway, static-assets, cip-15, cip-9, cors]
sources:
  - refs/cips/cip-15-public-asset-hosting.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-9-runner-storage.md
last_updated: 2026-04-20
status: draft
---

# Public Asset Hosting (CIP-15)

Extends CIP-14 so that Gateways serve static files (HTML/CSS/JS/images/fonts) directly from **CIP-9 public volumes**, bypassing the actor's `http.request` handler. Core primitive: a **route manifest** (`_meta/routes.json`) inside the volume declaring which URL paths go static vs. dynamic.

---

## 为什么要有它

CIP-14 下一切 HTTP 请求（包括 `GET /style.css`）都走 `queryActor` → Actor handler → PVM cycles。典型 Web 应用 80–95% 请求是不变的静态资产：浪费 Actor 的 `max_query_cycles` 预算与 Gateway 计算。CIP-15 把这类请求完全从 Actor 路径抽离：

- **Zero PVM cycles**: Gateway 直读 volume / 本地缓存，Actor 永不被唤醒
- **Atomic deploy**: 路由规则和资产一起在 `commit_manifest` 事务里原子切换
- **CDN 级别表现**: Gateway 本地 LRU cache + ETag (`b3_...`) + `Cache-Control`

---

## 核心机制

### 1. 路由清单（`_meta/routes.json`）

存在 CIP-9 public volume 根目录；priority + path_prefix 决定静/动归属。未匹配走 `default_behavior`。`/_cowboy/*` 永远由 Gateway 拦截，清单不可覆盖。

```
GET /api/users   → dynamic route (priority 100) → Actor handler
GET /assets/*    → static route  (priority 10)  → volume lookup
GET /about       → static route  (priority 0)   → SPA fallback → index.html
```

### 2. 实体扩展: `ingress.http` 新增参数

| 参数 | 默认 | 作用 |
|---|---|---|
| `static_volumes: [{volume_name, max_cache_bytes}]` | `[]`（禁用静态）| Gateway 可访问的 public volume 列表 |
| `max_static_response_bytes` | 10 MiB | 单资产响应上限（协议 ceiling 100 MiB）|

**部署时校验**: 每个 `volume_name` 必须是本账户的 `PUBLIC` volume（`volume_id = keccak256(account ‖ name)` 强绑定，防跨账户引用）。

### 3. Gateway → Relay Node fetch

1. 按 `StorageCommitment.manifest_root` 轮询失效（`MANIFEST_POLL_INTERVAL = 6` blocks ≈ 6s）
2. 调 Relay Node `GET_MANIFEST`（**CIP-9 新增 RPC**，见下）获取全量 ShardMap
3. 并发取 K 份 shard（含 `HEDGE_THRESHOLD_MS = 100ms` 的投机请求），Reed-Solomon 重建
4. 验证三级完整性：
   - Manifest 对 on-chain `manifest_root`（BLAKE3 Merkle）
   - 每个 shard 对 `shard_hash`（BLAKE3）
   - 重建对象对 `content_hash`（BLAKE3）

### 4. CORS

`_meta/cors.json` 声明规则；静态路径默认宽松（`Allow-Origin: *`、`GET/HEAD/OPTIONS`），匹配主流 CDN。动态路径**无**默认 CORS，由 Actor handler 自行返回（或清单显式配置）。Preflight `OPTIONS` 始终由 Gateway 直答，不浪费 query cycles。

---

## 规范性影响

- **`ingress.http` 扩展**: CIP-15 扩展而非新建 entitlement — 静态 serving 是 HTTP ingress 的一种模式，非独立能力。
- **CIP-9 amendment required**: CIP-9 §16.3 目前定义 3 个 Relay Node RPC（`PUT_SHARD` / `GET_SHARD` / `LIST_SHARDS`），CIP-15 要求追加 `GET_MANIFEST`。这是协议接口扩展，非 CIP-15 内部可完成。
- **Canonical manifest serialization**: CIP-15 §8.5 规定了 CBOR (RFC 8949 确定性编码) + 按 `object_path` UTF-8 字节排序 + 二叉 Merkle 的规范化形式，使 Gateway 能**不信任** Relay Node 地重算 `manifest_root`。CIP-9 现在的 `manifest_root` 描述未明确该序列化规则 —— 实现时必须对齐。

---

## 经济模型

Gateway 按量读取 shard 但**不**向 Relay Node 付 per-read 费用；Relay Node 的带宽成本被卷入 CIP-9 按 epoch 的 storage fee（类似 CDN 源站模型）。Volume 拥有者停付 storage fee → 自动 GC。

**Relay Node 侧防滥用**（非协议强制，节点本地策略）:
- Per-IP `MAX_SHARD_READS_PER_SECOND = 1000`（建议值）
- Per-volume 每 IP `= 500`（建议值）

未来工作：actor-funded bandwidth budget 按实际读取量补偿 Relay Node，需 per-read accounting — v1 不合算。

---

## 源文档冲突 / 漂移

- CIP-9 §16.3 缺 `GET_MANIFEST` → 已记入 [[../drift]]（条目 N-1）。
- CIP-9 `manifest_root` Merkle 计算规则（叶子序列化、奇数叶复制、哈希函数）未以规范力度描述，CIP-15 §8.5 是目前唯一的 normative 说明。
- `BLOCKS_PER_YEAR` 与块时间假设与 CIP-14 同源问题，不独立漂移。

---

## 相关

- [[dns-addressable-actors]] — CIP-14 基础 HTTP ingress
- [[../entities/gateway]] — Gateway 节点缓存 / fetch 协议
- [[../parameters]] — CIP-15 常量（`MAX_GATEWAY_CACHE_BYTES`, `MANIFEST_POLL_INTERVAL` 等）

## Sources

- `refs/cips/cip-15-public-asset-hosting.md` — 规范（Draft, 2026-03-07, Requires: CIP-9, CIP-14）
- `refs/cips/cip-9-runner-storage.md` — public volume 与 `manifest_root` 定义
