---
type: entity
tags: [gateway, ingress, node-role, cip-14, cip-15]
sources:
  - refs/cips/cip-14-dns-addressable-actors-v2.md
  - refs/cips/cip-15-public-asset-hosting-v2.md
  - refs/cips/cip-16-custom-domains-v2.md
last_updated: 2026-04-21
status: draft
---

# Gateway 节点角色

CIP-14 v2 引入的**第一个** ingress 节点角色，与 Runner / Validator / Relay Node 并列的 4 个独立协议角色之一。单物理节点可并行多角色；协议层每个角色独立 staking、心跳、激励。

> **地址变更（v1 → v2）**：CIP-14 v1 把 Gateway Registry 放在 `0x0012`；v2 §1 Preconditions 收回到 `0x0D`（紧跟代码现有 `0x01`–`0x0B` 序列）。

---

## 职责

| 类别 | 做 | 不做 |
|---|---|---|
| TLS & DNS | 终止 TLS（ACME DNS-01）；响应 `*.cowboy.network` 解析 | 不做 anycast / geo-DNS 的网络层选路（由 BGP/权威 DNS 配置）|
| 路由 | 查 Route Registry (`0x0C`) 把 `name → actor_address`；区分 query / command 路径 | 不参与共识 |
| Read-only 执行 | Query 路径：本地节点 `read_handler` RPC（CIP-14 v2 §5 + Part III §5）跑 Actor handler，PVM 在已提交状态上只读、所有 mutating syscall trap | 不跑 CIP-2 off-chain 任务（Runner 职能）|
| 提交 | Command 路径：签名 TX → `IngressDispatch` (opcode 65) → `GATEWAY_REGISTRY=0x0D` 验证 sender 是 active Gateway → 转发到目标 Actor | 不存 CIP-9 shard（Relay Node 职能）|
| Entitlement 强制 | `max_request_bytes` / `max_response_bytes` / `max_query_cycles` / `allowlist_methods` | 不在 PVM 内强制（Gateway 侧预检）|
| 静态 serving (CIP-15 v2) | `GET_MANIFEST` (CIP-9 AMEND 9-G) + 并行 shard fetch + Reed-Solomon 重建 + 本地 LRU cache + ETag/Cache-Control | 不做源对象变换（压缩可选；裁剪/重编码延迟到 future CIP）|
| 速率限制 | `MAX_REQUESTS_PER_SECOND = 100` per actor per gateway；`MAX_CONCURRENT_CONNECTIONS = 1000` | Per-Gateway 独立，未协调跨 Gateway（已知漏洞 12.6）|

> **v1 名词变更**：CIP-14 v1 §8.3 引用了一个 hypothetical `queryActor` RPC（声称来自 "Milestone 2 §5.2"），代码中并不存在。CIP-14 v2 §5 + Part III §5 改为 spec 一个具体的 `read_handler` RPC（POST `/actor/{address}/read_handler`）+ PVM `read_only: bool` 模式 + 显式 trap 表（包含 `randomness`，v1 漏掉了）。

---

## 生命周期（Gateway Registry `0x0D`）

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
| `dispatch(target, envelope)` | **仅已注册且 active** 的 Gateway，emit 后由系统转 `IngressDispatch` (opcode 65) | Command 分派；非授权回 `ERR_UNAUTHORIZED_GATEWAY` |
| `is_active_gateway(address)` | 任意 | 查询 |

**Sender 真实性 (v2 修订)**：Actor 在 command 路径收到 `http.request` 消息时 **MUST** 验证 `ctx.sender == GATEWAY_REGISTRY=0x0D`，SDK (CIP-6) `@http.handler` 装饰器默认附此检查。

> **v2 selector 设计修订**：CIP-14 v2 早期草案曾提议 PVM 路由层把 `"http.request"` 设为系统保留 selector（任何非系统 sender 用此 selector 发消息 → `ERR_RESERVED_SELECTOR`）。该提案在 CIP-14 v2 §6.2 Note 被**撤销**，因为它阻断了合法的 router actor 转发模式。改为依赖 `ctx.sender` 检查 —— 由协议消息路由器从 tx 签名者填入，不可被调用者代码伪造。

**Stake vs operating balance**（CIP-14 v2 §6.3 / WP-v2 Delta 1）：Gateway 的 stake 锁在 `0x0D` 中是 slashable 抵押；gas 由 Gateway 的 operating account 单独支付。两者**禁止混用**。Actor 想替 Gateway 付费时用现成的 `Action::UseOwnerBalance` 委派（`node/types/src/entitlement.rs:94`）。

---

## Receipt Registry `0x0E`（Command 路径异步结果）

CIP-14 v2 §8 引入。Command 路径 Gateway 返回 `202 Accepted` + `X-Cowboy-Request-Id`；客户端轮询 `/_cowboy/requests/{id}` 拿结果。

**为什么不复用 actor KV**：v1 §8.4 让 Actor 在自己的 KV 存 `_http/results/{request_id}` + 每个 request 一个 cleanup timer —— 热门 actor 1k 个 pending request 即撞 `MAX_TIMERS_PER_ACTOR=1024`。v2 把 receipts 移到 `0x0E`，单一全局 prune 循环按 `expires_at` 清理；actor timer 预算不被消耗。`receipt_ttl_blocks` 是 `ingress.http` 的可选参数（默认 3600，上限 86400）。

`CompleteReceipt` 是 **opcode 66**（CIP-13 v2 §1 主表），sender 必须是 receipt 的 `target_actor`。

---

## 激励（serving fee pool）

**Serving fee pool**（CIP-14 v2 §7.4）由域名注册 / 续费费池按 `target_pool: GATEWAY_POOL` 抽 ~15-20%（治理可调），按 `weight_stake × stake + weight_uptime × uptime_blocks` 每 epoch 分给 active Gateway。配置存 `system:gateway_pool_config` （`UpdateSettlementConfig` opcode 40 + `target_pool: GATEWAY_POOL` 更新）。

**已知漏洞**: 与请求量解耦 —— Gateway 空载也能按 stake 领。v1 接受此 free-rider 风险换取简洁；follow-on CIP 用 per-request 付费修复。

---

## 缓存架构（CIP-15 v2 §6 + CIP-9 v2 §2 + CIP-9 v2 §4）

**两层缓存**:

1. **Metadata Cache**（每活跃 volume 常驻）:
   - `route_manifest` / `cors_config` 现存于 `STORAGE_MANAGER (0x0A)`，不是 volume 内（CIP-15 v2 §4.1 / §7.1）
   - `volume_manifest` 从 Relay Node `GET_MANIFEST` (CIP-9 v2 §2 AMEND 9-G) 拉取
   - 通过订阅 `ManifestCommitted` 链上事件（CIP-9 v2 §4 AMEND 9-H）触发 eager 失效；polling `MANIFEST_POLL_INTERVAL = 6 blocks` 作为 floor
2. **Object Cache**（LRU + frequency-weighted）:
   - 全局 `MAX_GATEWAY_CACHE_BYTES = 10 GiB`（每 Gateway operator 自行）
   - Key = `(volume_id, object_path)`；值附 `content_hash` 作 ETag (`b3_<hex>` BLAKE3)

**完整性三层校验**（CBFS 规范化 Merkle，**非** Bitcoin-style duplicate-last-leaf —— 见 CIP-9 v2 §3）:
1. Manifest 对 on-chain `manifest_root`（BLAKE3 Merkle）
2. Shard 对 `shard_hash`（BLAKE3）
3. 重建对象对 `content_hash`（BLAKE3）

**版本号双轨**（CIP-15 v2 §5.1）: 静态响应同时返回 `X-Cowboy-Block: <height>` 与 `X-Cowboy-Manifest-Root: <hex>` 两个版本头，避免 Gateway 把 `body @ manifest_root_N-1` 配上 `X-Cowboy-Block: N` 造成的"看似同步实则错位"。

**Storage 状态映射**（CIP-9 v2 §5）:

| `StorageCommitment.status` | Gateway HTTP 响应 |
|---|---|
| `ACTIVE` | 正常返回 |
| `GRACE_PERIOD` | 返回 + 加 advisory header `X-Cowboy-Storage-Status: grace` |
| `DELETED` | `503` + `X-Cowboy-Error: VOLUME_DELETED` |
| `GARBAGE_COLLECTING` | `410 Gone` + `X-Cowboy-Error: VOLUME_GC` |

> **CORS 优先级修订**（CIP-15 v2 §7.3）: 动态路径下 actor handler 自己设置的 `Access-Control-*` 头优先；`cors_config` 仅在 actor 没设时 fallback。CIP-15 v1 曾说反过来，已修正。

---

## 相关

- [[system-actors]] — `0x0C` Route Registry / `0x0D` Gateway Registry / `0x0E` Receipt Registry
- [[route-registry]] — `0x0C` 实体页
- [[../concepts/dns-addressable-actors]] — CIP-14 v2 基础
- [[../concepts/public-asset-hosting]] — CIP-15 v2 静态 serving
- [[../concepts/custom-domains]] — CIP-16 v2 外部 FQDN
- [[../parameters]] — Gateway / Route Registry 常量段

## Sources

- `refs/cips/cip-14-dns-addressable-actors-v2.md` — Gateway 角色 §7 + read_handler RPC §5 + IngressDispatch §6.1 + Receipt Registry §8 + sender authenticity §6.2 + target_pool 枚举 Part III §6
- `refs/cips/cip-15-public-asset-hosting-v2.md` — 静态 serving / Storage 状态映射 / CORS 优先级修订 / X-Cowboy-Manifest-Root 双版本头
- `refs/cips/cip-16-custom-domains-v2.md` — 外部域 serving 策略
- `refs/cips/cip-9-runner-storage-v2.md` — `GET_MANIFEST` (AMEND 9-G) + `ManifestCommitted` 事件 (AMEND 9-H) + Status 映射 §5
- `refs/cips/cip-13-runner-delegation-v2.md` §1 — opcode 主分配表（65 IngressDispatch / 66 CompleteReceipt）
