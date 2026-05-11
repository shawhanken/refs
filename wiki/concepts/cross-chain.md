---
type: concept
tags: [cross-chain, bridge, anchoring, messaging, runners, cip-25, cip-2, cip-4, cip-7, draft]
sources:
  - refs/cips/cip-25-cross-chain-architecture.md
  - refs/cips/cip-2-offchain-compute-v2.md
  - refs/cips/cip-7-simple-stream-protocol.md
last_updated: 2026-05-11
status: draft
---

# Cross-Chain Architecture（CIP-25）

## 概述

CIP-25 把 Cowboy 跨链能力组织成**三个正交层**，每层一个责任、各自可替换、自下而上组合 —— 与 TCP/IP 的分层同构（L1 ≈ 数据包 + 完整性，L2 ≈ TCP 流，L3 ≈ HTTP/SMTP）。

| Layer | 名称 | 单一职责 |
|---|---|---|
| **L1** | Cross-Chain State Anchoring | 让 A 链的块承诺**可在 B 链验证** + Merkle-proof 原语；**不**搬值、**不**转发消息 |
| **L2** | Cross-Chain Messaging | Mailbox 抽象：(src, dst, sender, recipient, nonce, payload) 强序、exactly-once、双向、多链 |
| **L3** | Cross-Chain Applications | asset bridge / lending / oracle / generic call —— 都建在 L2 之上（或为 gas critical 直接 binding L1）|

**关键性质**：L2 不知道 L1 用哪种信任后端；L3 不必关心 L1 怎么实现。后端 swap 不损坏 L2/L3 不变量。

**当前状态**：Draft（2026-04-23）。架构层 spec，asset bridge 等 L3 应用各自留单独 CIP。

---

## Layer 1：State Anchoring

### 责任 / 非责任

**做**：发布 source 块的 `BlockCommitment{ tx_root, receipt_root, state_root?, parent_hash?, finalized_at }` 到 destination；验证发布的真实性；`verify_inclusion(chain, height, proof, leaf) → bool`。

**不做**：不知道承诺的语义（root 都是 bytes）/ 不解码 payload / 不搬值 / 不记 nonce / 不知"哪条链 peered"。

### 信任后端（pluggable，本 CIP 列 4 种）

| Backend | 假设 | 延迟 | 成本 |
|---|---|---|---|
| **Runner committee**（2-of-3 ECDSA，参考拓扑） | 多数 runner 诚实 | ~2 dst 块 | ECDSA verify + storage writes |
| **ZK light client**（未来） | 证明系统 soundness | 秒级 prove + 1 块 | verifier call |
| **Optimistic**（未来） | challenge window 内 ≥1 诚实 chal | challenge 期（小时-天）| 兜底重时 |
| **Native light client**（未来） | dst 能负担 src 共识验证 | 1 块 | 视实现 |

四个后端都产出同 shape 的 `BlockCommitment` → L2 对后端透明，**swap 不破坏 L2/L3 不变量**（B.3 composition theorem 推论）。

### 接口（dst 侧 `IChainAnchor`）

```solidity
isFinalized(chainId, height) -> bool
commitment(chainId, height)  -> (txRoot, receiptRoot, stateRoot)
verifyInclusion(chainId, height, root, leaf, siblings[], index) -> bool
```

src 侧 publish 路径与后端绑定。Runner-committee：VRF 选 N runners → 各自签
`keccak256("Anchor.v1" || src_chain || dst_anchor_addr || height || tx_root || receipt_root)` → dst 合约逐个 recover 到 threshold。

### 失效模式 → 解决方案（§1.6 全列）

| 失效 | 防御 |
|---|---|
| Runner 串谋伪造 | (1) 经济底（stake ≥ k × max_attestable_value，k=10）; (2) 自动 slashing（dissenters 列直接给 stake 模块）; (3) 7-day fraud-proof window; (4) 双后端 anchor（committee + ZK 同意才放）|
| Runner offline 拖延 | (1) liveness timeout 100 blocks → re-VRF; (2) reputation ledger 影响权重; (3) M=5 timeout → probation; (4) rescue bonus 从原 runner stake 扣 |
| Source-chain reorg | (1) Cowboy 确定性最终；(2) ETH min_confirmations=32（高 TVL 64）;（3) deep-reorg revocation set;（4) runner 本地监控 |
| Stale commitment 误用 | `finalized_at` 暴露 + app TTL（asset bridge 24h / oracle 5min / lending 15min / RPC 2min）+ timeout-and-cancel + 协议级 GC |
| L3 拿不到 Merkle proof | 3 路并存：客户端 RPC `/proof/tx/<hash>` / Runner 新 job type `generate_inclusion_proof` / 第三方 indexer |
| 多 dst 共消同一 commitment | Stage 1 per-chain tx → Stage 2 BLS 聚合（pairing 链）→ Stage 3 broadcast 单 tx fan-out；Solana 无 pairing → threshold ECDSA |

---

## Layer 2：Messaging（Mailbox）

```rust
struct CrossChainMessage {
    src_chain: u64, dst_chain: u64,
    sender: Address, recipient: Address,
    nonce: u64,             // 严格单调 per (src_chain, sender, dst_chain)
    payload: bytes,         // L2 不解码
    gas_limit: u64,
}
```

### 不变量（B.2）

| 不变量 | 说明 | 依赖 |
|---|---|---|
| L2-Authenticity | dispatch 成功 → 源链确有此 send | L1-Authenticity + L1-Inclusion |
| L2-Exactly-Once | 同 (src,sender,nonce) 最多 dispatch 一次 | `consumed[...]` write-once + L1-Monotonic-Finality |
| L2-Ordering | 同 (sender, dst) 严格单调 nonce；应用可选 enforce 连续性 | 源 mailbox atomic counter |
| L2-Integrity | 投递 payload 与 send payload 字节相同 | L1-Inclusion + 规范化 encoding |
| L2-Deployment-Isolation | 同 dst 链 sibling mailbox 不可互替 | 签名绑定 `address(this)` |

### Deliver 模板

```solidity
function deliver(msg, proof, index) {
    require(anchor.isFinalized(msg.src_chain, blockOf(msg)));
    require(anchor.verifyInclusion(msg.src_chain, blockOf(msg),
            anchor.commitment(...).txRoot, hash(msg), proof, index));
    require(!consumed[msg.src_chain][msg.sender][msg.nonce]);
    consumed[...] = true;
    IRecipient(msg.recipient).onCrossChainMessage(src, sender, payload);
}
```

### 扩展原语（§2.6）

| 需求 | 解 |
|---|---|
| **Gas 赞助** | `send(..., fee)` 源侧 prepay → 协议 20% / relayer 80% → 默认 runner-managed 投递 + 第三方套利 fallback + `bump_fee` / `reclaim_fee` |
| **Timeout / Cancel** | `expiry` 参数 + dst hard cutoff + src 等 `expiry + GRACE=1h` 后 `reclaim` + `on_timeout(msg_hash)` 回调 |
| **跨 sender 总序** | `send_stream(stream_id, ...)` 维护原子 per-stream seq；`stream_id = keccak256(dst ‖ recipient ‖ topic)`；dst `deliver_stream` enforce 连续性；多源场景委派 serializer chain |

### Watchtower (CIP-7) 跨链化

CIP-7 既有 intra-chain 有序流。把每条 Watchtower 消息同时 `send_stream` 跨链 → 得 **跨链流式数据 / AI inference / 直播**，无须 L2 改动。`stream_id = Watchtower 流 hash`。

---

## Layer 3：Applications

> **范围说明**：本 CIP 给四类应用的 payload skeleton + 失效引用，**不**完整规范任何一类；asset bridge / lending 等各自留独立 CIP。

| 类 | 描述 | Payload | 不变量 |
|---|---|---|---|
| **Asset Bridge** | Lock-mint / Burn-release | `(recipient, token_id, amount)` | L3-AssetBridge-Conservation: minted ≤ locked |
| **Lending / Collateral** | A 链抵押 / B 链借；**需双向 L2** | `(action, borrower, collateral_token, amount)` 双向各一 | total_borrowed ≤ collateral_value × LTV（应用本地 oracle）|
| **Oracle / Inference Relay** | 推 CIP-2 AI inference 结果到任意链；推荐用 `send_stream` | `(feed_id, value, source_ts, round_id)` | round_id 单调；TTL 强制 |
| **Generic Call** | `callCrossChain(dst, target, calldata, value)` | `(target, value, gas_limit, calldata)` | target.call 失败**不**回滚 L2 consumed（防无限重试） |

---

## 安全模型（§B）

### 三层 adversary

| L | 能力 | 保护资产 |
|---|---|---|
| L1 | 至多 (n-t-1) runner 串谋 / ZK 零参与 / optimistic 内有诚实 challenger | `BlockCommitment` authenticity + inclusion soundness |
| L2 | L1 能力 + 任意 `deliver` + 撤回消息 / 任意自己顺序 | exactly-once + 单调 + integrity + deployment isolation |
| L3 | L2 能力 + 任意应用输入 + 经济参数操纵 | 应用特有不变量 |

### Composition Theorem（informal）

L1-Authenticity + L1-Inclusion + 规范化 encoding ⇒ L2-Authenticity / Integrity；
L1-Monotonic-Finality + write-once consumed ⇒ L2-Exactly-Once；
源单调 nonce ⇒ L2-Ordering。
**Corollary**：L3 不变量 bottom out 到 L1 backend-agnostic 谓词 —— **swap L1 后端不损坏 L3 安全性**（前提是新后端满足 B.2 assuming clauses）。

### 攻击分类（15 项 → §B.4）

5 类：trust-model（committee 串谋 / ZK soundness break / optimistic 漏窗）、source-chain（reorg / 老 commitment / 拖延 finality）、messaging（replay / 部署间 replay / sig malleability / nonce skip）、delivery（grief / front-run claim / 跨 sender 序竞争 / gas grief）、application（oracle 老值 / 流动性榨干 / key rotation）。每项都有 §B.5 mechanism 索引。

### Defense-in-depth 模式（§B.6）

1. **Dual-backend anchor** —— committee + ZK 双 verify
2. **Timeout-with-cancel** —— 通用模式
3. **Rate-limited release** —— 应用每 epoch cap volume

TVL > governance-set 阈值（提案 $1M USD eq）**MUST** 采至少一种。

---

## Cowboy 的优势位

- **Runners (CIP-2)**：就绪的 stake-gated VRF 委员会
- **Merkle proofs (CIP-4)**：状态已 commit-verifiable，dst 无须重算
- **Timers (CIP-5)**：keeper-free per-block anchoring
- **Watchtower (CIP-7)**：intra-chain 流式原语 → 跨链流式（§2.5 + send_stream）即得，**通用桥无此能力**

---

## 性能信封（§A.6，order-of-magnitude）

| 后端 | 端到端延迟 | per-message gas（EVM dst）|
|---|---|---|
| Committee 2-of-3 | ~3 dst blocks 加 src finality | 200–300k gas（2 sig + 1 deliver） |
| ZK | proof time + 1 dst block | verifier call cost |
| BLS 聚合 (Stage 2) | 同 committee | per-message 降 60–70% at N ≥ 10 |

可比：LayerZero ~200–300k / Axelar ~250k / Wormhole ~200k。架构不偏离主流量级。

---

## 与现有 CIP 的关系

| CIP | 角色 |
|---|---|
| **CIP-2** | Runner committee = L1 后端 attestation 签名源 |
| **CIP-4** | 源状态本身就 commit-verifiable，L1 直接搬 root |
| **CIP-5** | Per-block anchoring 由 timer 触发，无 keeper bot 依赖 |
| **CIP-7** | Watchtower + send_stream = 跨链流式 |
| **CIP-20** | L3 asset bridge 的 reference 实现目标 |
| **CIP-21** | "swap-and-bridge" L3 模式 |

---

## 反向兼容

不修改 Cowboy L0（共识 / 出块 / state commitment）。新加 L1 anchor actor + L2 mailbox + L3 应用 contract；既有 actor / runner / RPC 不受影响。Tony 团队既有 Cowboy→ETH withdrawal bridge 可作 outbound 参考拓扑；CIP-25 的 L1 抽象 generalize 该模式到双向 + 多链。

---

## 已知空白

- 后端的具体 CIP（ZK / optimistic / native LC）各自独立；本 CIP 只给接口
- 跨链 atomic tx **不**承诺 —— lending 等需应用层时段-超额抵押缓解
- 三方对偶（A↔B via Cowboy）超出本 CIP 范围
- Key rotation 协议留独立 CIP（B.4.5）

---

## 相关

- [[runner-verification]] / [[vrf-runner-selection]] —— Runner committee 选择与共识
- [[settlement-slashing]] —— Committee dissenter slashing 路径
- [[../entities/runner-lifecycle]] —— Runner attestation 角色叠加
- [[../parameters]] —— 跨链常量（finalized_at / min_confirmations / TTL 默认 / GRACE / BLS pairing 列表）
- [`refs/cips/cip-25-cross-chain-architecture.md`] —— 完整 §A worked examples / §B security model

## Sources

- `refs/cips/cip-25-cross-chain-architecture.md` — Draft 2026-04-23；3-layer architecture + 4 backends + 4 L3 app skeletons + 15-attack taxonomy + composition theorem + defense-in-depth patterns
