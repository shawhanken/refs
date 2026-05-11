---
type: concept
tags: [rpc, merkle, light-client, gateway, cip-17, cip-15, cip-19, cip-4, draft]
sources:
  - refs/cips/cip-17-verifiable-state-read.md
  - refs/cips/cip-15-public-asset-hosting-v2.md
  - refs/cips/cip-15-gateway-implementation.md
  - refs/cips/cip-19-gateway-mcp-ingress.md
  - refs/cips/cip-4-storage.md
  - refs/cips/cip-25-cross-chain-architecture.md
last_updated: 2026-05-11
status: draft
---

# Verifiable State Read RPC（GET_STATE，CIP-17）

## 概述

CIP-17 加一条 RPC：`GET /state/{actor_address}/{key_hex}` 返回 `(value, merkle_proof, state_root, block_height)`。客户端本地验证 Merkle 证明再信任 value。**这是 CIP-15 v2.r2 Gateway 路由缓存 + CIP-19 `tools/list` 派生的唯一硬阻塞 RPC**。

### 与 `read_handler` 的关系

| 维度 | `read_handler`（CIP-14 v2.r2 §5）| `GET_STATE`（CIP-17）|
|---|---|---|
| 用途 | 调用 actor 的 PVM read-only 处理器 | 读 actor 原始 KV + Merkle 证明 |
| 触发 | `GET /api/users/{id}` 等动态路径 | `__cowboy/routes` 缓存拉取等基础设施读 |
| PVM cycles | 消耗（计入 `max_query_cycles`）| 0（无 PVM 调用）|
| 信任模型 | 信任执行 RPC 的节点（next-block consistency）| 通过 Merkle 证明 + state_root 验证，零额外信任 |

二者互补，都是 v2.r2 ingress 协议栈缺失但需要的部件。

---

## 接口

```http
GET /state/{actor_address}/{key_hex}?prove=true
```

响应：

```json
{
  "actor_address":  "0x0000…000D",
  "key":            "0x...",
  "value":          "0x..." | null,
  "state_root":     "0x...",
  "block_height":   12345678,
  "block_hash":     "0x...",
  "proof": {
    "siblings":     ["0x..."],
    "leaf_hash":    "0x...",
    "path_nibbles": [0, 5, 12]
  },
  "absent":         false
}
```

- 不存在的 key 不返 404，而是 200 + `value: null` + `absent: true` + 排除证明
- `prove=false` 退化为既有 `/actors/{address}/storage` 行为（仅 value）

详见 CIP-17 §5。

---

## 主要消费者

| CIP | 调用点 |
|---|---|
| **CIP-15 v2.r2 §6** | Gateway 每 actor 维护 `Routes` 缓存；通过 `GET_STATE` 拉 `__cowboy/routes`，proof 校通过才更新缓存 |
| **CIP-15 gateway-implementation r2 §2.2** | Phase 1 routes resolver 唯一阻塞 RPC |
| **CIP-19 §10.1 step 1** | MCP `tools/list` 从同一 `__cowboy/routes` 表派生 |
| **CIP-25 §1.4 native light client backend (future)** | 跨链 light client 直接消费这种 leaf 证明 |
| **Off-chain indexer / 审计工具** | 任何想 "本地验证、零信任" 读链上 KV 的客户端 |

---

## 实现规模

CIP-17 §7 估计 < 200 行（含测试）。复用 `cbfs`/`node` 已有 MPT trie 原语（CIP-4），只是把 proof 暴露到 RPC 层。无新共识、无新存储、无新 PVM syscall。

实现路径：
1. `node/rpc/src/rpc.rs:168-213` 加一条 `GET /state/{actor}/{key}` route
2. `node/storage` 暴露 `kv_get_with_proof(actor, key) → (value, MerkleProof)`
3. `node/types/src/rpc.rs`（或等价）加响应 struct

---

## 待解决项（CIP-17 §3 / §5.3 已标注）

- **`at_block: u64` 历史读** — 跨链 light client（CIP-25 §1.4）需要；v1 仅返当前块
- **Batch reads** — 多 `(actor, key)` 一并返；v1 单 key
- **Subscribe API** — WebSocket 推；现 v1 仅 pull
- **Bundled account-trie proof** — §5.3 标注的现知不足：v1 只给 actor's storage trie proof，client 需另外验 account-trie 中 `actor.state_root` 字段；v2 一次给两段
- **CIP-25 跨链扩展** — L1 anchor 通过 L2 mailbox 携带 `GET_STATE` 类证明到目标链；属 CIP-25 后续工作

---

## 相关

- [[dns-addressable-actors]] — CIP-14 v2.r2 `read_handler` 是兄弟 RPC
- [[public-asset-hosting]] — CIP-15 v2.r2 Gateway 主消费者
- [[mcp-ingress]] — CIP-19 `tools/list` 派生
- [[cross-chain]] — CIP-25 native light client 后端 future 消费者
- [[../entities/system-actors]] — Route Registry `0x0D` 是 Gateway 第一个 `GET_STATE` 目标
- [[../parameters]] — 暂无单独参数段；CIP-17 v1 无新常量

## Sources

- `refs/cips/cip-17-verifiable-state-read.md` — Draft（2026-05-11）；12 sections
- `refs/cips/cip-15-gateway-implementation.md` r2 §2.2 — 标 CIP-17 立项需求
- `node/rpc/src/rpc.rs:168-213` — 既有未验证 state RPC（CIP-17 在此基础上加 proof）
