---
type: entity
tags: [gateway, ingress, node-role, cip-14, cip-15]
sources:
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-15-public-asset-hosting.md
  - refs/cips/cip-16-custom-domains.md
last_updated: 2026-04-20
status: draft
---

# Gateway 节点角色

CIP-14 引入的**第一个** ingress 节点角色，与 Runner / Validator / Relay Node 并列的 4 个独立协议角色之一。单物理节点可并行多角色；协议层每个角色独立 staking、心跳、激励。

---

## 职责

| 类别 | 做 | 不做 |
|---|---|---|
| TLS & DNS | 终止 TLS（ACME DNS-01）；响应 `*.cowboy.network` 解析 | 不做 anycast / geo-DNS 的网络层选路（由 BGP/权威 DNS 配置）|
| 路由 | 查 Route Registry (`0x0011`) 把 `name → actor_address`；区分 query / command 路径 | 不参与共识 |
| 执行 | Query 路径：本地 `queryActor` 跑 Actor handler，PVM 沙箱 + `max_query_cycles` cap | 不跑 CIP-2 off-chain 任务（Runner 职能）|
| 提交 | Command 路径：签名 TX → `GatewayRegistry.dispatch()` (`0x0012`) → 目标 Actor | 不存 CIP-9 shard（Relay Node 职能）|
| Entitlement 强制 | `max_request_bytes` / `max_response_bytes` / `max_query_cycles` / `allowlist_methods` | 不在 PVM 内强制（Gateway 侧预检）|
| 静态 serving (CIP-15) | `GET_MANIFEST` + 并行 shard fetch + Reed-Solomon 重建 + 本地 LRU cache + ETag/Cache-Control | 不做源对象变换（压缩可选；裁剪/重编码延迟到 future CIP）|
| 速率限制 | `MAX_REQUESTS_PER_SECOND = 100` per actor per gateway；`MAX_CONCURRENT_CONNECTIONS = 1000` | Per-Gateway 独立，未协调跨 Gateway（已知漏洞 12.6）|

---

## 生命周期（Gateway Registry `0x0012`）

```
Register → Stake ≥ MIN_GATEWAY_STAKE (governance-set)
         → Declare { endpoint, http_port }
         → health = MAX_GATEWAY_HEALTH (3,600 blocks ≈ 1h)
         → 每块 health -= 1；Heartbeat 重置
Inactive → health == 0  → 踢出 active list
Unstake  → 等 GATEWAY_UNSTAKE_DELAY (604,800 blocks ≈ 7d)
```

**调度方法**:

| Method | Caller | 作用 |
|---|---|---|
| `register_gateway(endpoint, http_port)` | 任意（需 stake）| 注册 |
| `heartbeat()` | 已注册 Gateway | 健康重置 |
| `unstake()` | 已注册 | 进入解绑 |
| `dispatch(target, envelope)` | **仅已注册且 active** 的 Gateway | 系统中介 command 分派；非授权 caller 回 `ERR_UNAUTHORIZED_GATEWAY` |
| `is_active_gateway(address)` | 任意 | 查询 |

**非伪造性**: Actor 在 command 路径收到的 `ctx.sender == GATEWAY_REGISTRY_ADDRESS (0x0012)` —— 系统中介路径而非直接 ActorMessage，使得外部账户无法伪造 `method: "http.request"` 消息。SDK (CIP-6) `@http.handler` 装饰器**必须**默认附上这个 sender 校验。

---

## 激励

**Serving fee pool**（CIP-14 §9.4）由域名注册 / 续费费池按 `GATEWAY_POOL_BPS = 2000 (20%)` 抽入，按 `stake × uptime_blocks` 每 epoch 分配给 active Gateway。

**已知漏洞**: 与请求量解耦 —— Gateway 空载也能按 stake 领。v1 接受此 free-rider 风险换取简洁；follow-on CIP 用 per-request 付费修复。

---

## 缓存架构（CIP-15 §8.2）

**两层缓存**:

1. **Metadata Cache**（每活跃 volume 常驻）:
   - `route_manifest` / `content_type_map` / `cache_config` / `volume_manifest`
   - 通过轮询 on-chain `StorageCommitment.manifest_root`（`MANIFEST_POLL_INTERVAL = 6 blocks`）发现变更
2. **Object Cache**（LRU + frequency-weighted）:
   - 每 volume `max_cache_bytes` 上限（entitlement 声明）
   - 全局 `MAX_GATEWAY_CACHE_BYTES = 10 GiB`
   - Key = `(volume_id, object_path)`；值附 `content_hash` 作 ETag

**完整性三层校验**:
1. Manifest 对 on-chain `manifest_root`（BLAKE3 Merkle）
2. Shard 对 `shard_hash`（BLAKE3）
3. 重建对象对 `content_hash`（BLAKE3）

---

## 相关

- [[system-actors]] — `0x0011` Route Registry / `0x0012` Gateway Registry
- [[route-registry]] — `0x0011` 实体页
- [[../concepts/dns-addressable-actors]] — CIP-14 基础
- [[../concepts/public-asset-hosting]] — CIP-15 静态 serving
- [[../concepts/custom-domains]] — CIP-16 外部 FQDN
- [[../parameters]] — Gateway / Route Registry 常量段

## Sources

- `refs/cips/cip-14-dns-addressable-actors.md` — Gateway 角色 §9 定义
- `refs/cips/cip-15-public-asset-hosting.md` — 静态 serving / Relay Node fetch 协议
- `refs/cips/cip-16-custom-domains.md` — 外部域 serving 策略
