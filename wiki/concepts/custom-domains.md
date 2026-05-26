---
type: concept
tags: [ingress, dns, tld, external-domain, cip-16]
sources:
  - refs/cips/cip-16-custom-domains.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-2-offchain-compute.md
last_updated: 2026-04-21
status: draft
---

# Custom Domains & First-Party TLDs (CIP-16 v2)

Extends CIP-14 v2's Route Registry (`0x0D`, v2.r2 spec-only) with two more naming classes: protocol-owned TLD names under `.cow` / `.cowboy`, and externally owned FQDNs like `api.example.com` attached via DNS-based control proof.

> **v1 → v2 主要变更**：DNS 验证模式从 `Deterministic`（错配，非 byte-identical）改为 `MajorityVote` + 两个新 `VerifierCheck` 变体（`DnsTxtRecordMatch` / `DnsCnameMatch`，CIP-2 v2 §2 AMEND 2-A/B 提供）；`complete_attach_external` 改用 `SystemInstruction::ExternalDomainCallback`（**opcode 67**），sender allowlist `RESULT_VERIFIER=0x03`；新增 `EXTERNAL_REVERIFY_FEE`（owner 付）+ CIP-5 timer `fee_payer = binding.owner` 的双层费用模型；显式 `RouteRegistration → DomainBinding` 迁移规则（默认值列表）；`SUSPENDED` 状态返回 `503`（v1 错用 `421`）；`verified_fqdn` 注入到 `HttpRequestEnvelope`（actor 信任此而非可伪造的 `host` header）；`CANONICAL_EDGE_HOSTNAME` 显式区分 anycast / SRV 模式。

---

## 三类命名空间并存

`namespace_kind` 字段区分（CIP-16 v2 §3.2）：

| Kind | 示例 | 治理 | 续费 |
|---|---|---|---|
| `0 = COWBOY_NETWORK` | `alice.cowboy.network` | CIP-14 v2 原生 | 必须 |
| `1 = FIRST_PARTY_TLD` | `alice.cow`, `app.alice.cowboy` | Cowboy 实体控制权威 DNS；`tld_kind ∈ {1=cow, 2=cowboy}` | 必须 |
| `2 = EXTERNAL` | `api.example.com` | 业主在自己的注册商；通过 TXT 挑战证明控制 | `expires_at` 可选；强制周期重验证 + 收 `EXTERNAL_REVERIFY_FEE` |

解析按**完整 FQDN 精确匹配**；不做跨命名空间 shadowing。

---

## 扩展的 DomainBinding（取代 CIP-14 §7.1 `RouteRegistration`）

CIP-16 v2 `DomainBinding` 是 CIP-14 `RouteRegistration` 的超集，加了命名空间类别、状态机、外部验证字段：

```
DomainBinding {
  fqdn, actor_address, owner, subdomain_policy,       // CIP-14 原有
  namespace_kind, tld_kind,                           // CIP-16 新增分类
  status ∈ {ACTIVE, PENDING, SUSPENDED, EXPIRED, DETACHED},
  registered_at, expires_at,
  verified_at, next_reverify_at,                      // 仅 EXTERNAL
  dns_target, verification_nonce, verification_method // 仅 EXTERNAL
}
```

**v2 schema 迁移规则（§3.1）**：CIP-14 v1 既有记录在升级时被**就地迁移**为 `DomainBinding`，默认值：

| 字段 | 默认值 |
|---|---|
| `namespace_kind` | `0 = COWBOY_NETWORK` |
| `tld_kind` | `0 = .cowboy.network` |
| `status` | `0 = ACTIVE` |
| `verified_at` / `next_reverify_at` / `dns_target` / `verification_nonce` | `null` |
| `verification_method` | `0 = NONE` |

`fqdn` 由旧 `name` 字段计算 `name || ".cowboy.network"`。一次性迁移。

---

## 外部域绑定流程（TXT 挑战 + 边缘目标 + ACME 委派）

三阶段：

1. **Begin** (`begin_attach_external(fqdn, actor)`)：caller 必须持 `dns.attach_external` entitlement；Route Registry 生成 `verification_nonce`，拼出挑战值 `cowboy:v1:<chain_id>:<fqdn>:<actor>:<nonce>`，状态置 `PENDING`，10s 内 emit verifier job。

2. **Prove**（链下 DNS 操作）:
   - 发布 `_cowboy-challenge.<fqdn> TXT "<challenge>"`
   - 指向边缘：`CNAME <fqdn> edge.cowboy.network`（apex 用 ALIAS/ANAME；anycast 默认，CIP-16 v2 §5.4 显式区分；可选 SRV 模式给非浏览器客户端）
   - 委派 ACME: `_acme-challenge.<fqdn> CNAME <token>.acme.cowboy.network`

3. **Complete**（CIP-2 multi-runner verifier）:
   ```
   JobSpec {
     job_type:      Custom { executor_hash: DNS_VERIFIER_EXECUTOR_HASH, params: ... }
     verification:  {
       mode:       MajorityVote                     // ← v1 错用 Deterministic
       runners:    3, threshold: 2,
       checks:     [
         DnsTxtRecordMatch { fqdn: "_cowboy-challenge."||fqdn, expected_value, min_resolvers: 3 },  // ← CIP-2 v2 §2 AMEND 2-A
         DnsCnameMatch     { fqdn, expected_target: CANONICAL_EDGE_HOSTNAME, min_resolvers: 3 },   // ← AMEND 2-B
       ],
     }
     callback:  {
       actor:    ROUTE_REGISTRY,                     // 0x0D (v2.r2)
       handler:  "_dns.callback",                    // → 协议 emit ExternalDomainCallback opcode 67
       ...
     }
   }
   ```
   - Verifier 各查 `min_resolvers ≥ 3` 个独立递归 resolver（操作员配置：1.1.1.1 / 8.8.8.8 / 9.9.9.9 / 208.67.222.222），strict majority pass
   - `RESULT_VERIFIER (0x03)` 聚合 → emit `ExternalDomainCallback` (opcode 67) → Route Registry 状态 `PENDING → ACTIVE`
   - **Sender allowlist**: `ExternalDomainCallback` opcode 67 sender 必须是 `0x03` —— 非伪造性由 system_instruction dispatcher 强制（不依赖 SDK 约定）

---

## Reverification 与 fee chain（v2 §5.7 / §5.8 / §5.10）

`next_reverify_at` 时触发 CIP-5 timer（一个 binding 一个 timer）执行 `_reverify_external(fqdn)`。

**两层 fee（v2 §5.10）**，缺一即降级：

| 费用 | 来源 | 触发 | 失败 → |
|---|---|---|---|
| `EXTERNAL_REVERIFY_FEE` | v2 §5.8 | 每次 reverify handler 第 1 步 | `status=SUSPENDED, reason=INSUFFICIENT_REVERIFY_FEE`（不派发 verifier job）|
| Reverify timer `max_cost` | CIP-5 revised §6.3 | 每个 reverify timer 即将 fire 前 | timer 自毁 (`TimerCancelledInsufficientFunds`) → 二线兜底 `INSUFFICIENT_TIMER_FUEL` |
| 验证 job runners 报酬 | CIP-2 §5 settlement | verifier job 提交结果 | 走标准 settlement |

Route Registry **MUST** 订阅 `TimerCancelledInsufficientFunds` 事件以触发 `INSUFFICIENT_TIMER_FUEL` SUSPENDED；`§7.1 current_block > next_reverify_at + EXTERNAL_REVERIFY_GRACE_BLOCKS` overdue 检查作为二线防御。

---

## Gateway 服务策略（v2 §7.2 修正状态码）

| status | HTTP 响应 |
|---|---|
| `PENDING` | `503 Service Unavailable` + `Retry-After: 60` |
| `SUSPENDED` | `503 Service Unavailable` + `X-Cowboy-Error: BINDING_SUSPENDED` |
| `EXPIRED` | `404 Not Found` |
| `DETACHED` | `404 Not Found` |

> **v1 错用 `421 Misdirected Request`**：HTTP/2 421 语义是"换 host 重试"，会让客户端去试别的 Gateway —— 这正是错的（其他 Gateway 也会拒）。v2 改为 503。

---

## verified_fqdn 注入（v2 §7.3）

`IngressDispatch` (opcode 65) 把这两个字段注入 `HttpRequestEnvelope`，actor handler 应该信任这俩而非客户端可控的 raw `host` header：

```
HttpRequestEnvelope {
  ...
  verified_fqdn:   string,         // GatewayRegistry 从 DomainBinding lookup 注入
  namespace_kind:  u8,             // 注入
}
```

多 binding actor（同时服务 `api.alice.cow` 和 `api.example.com`）按 `verified_fqdn` 分租户路由 —— 这是协议唯一证实的字段。

---

## 与其他 CIP 的耦合

| 依赖 | 角色 |
|---|---|
| CIP-14 v2 | Route Registry `0x0D` (v2.r2) & Gateway dispatch 基础不变；绑定记录结构扩展 |
| CIP-2 v2 | 外部验证作为 CIP-2 off-chain job（multi-verifier MajorityVote）+ 两个新 `VerifierCheck` 变体（v2 §2 AMEND 2-A/B）|
| CIP-5 revised | reverify timer + `fee_payer = binding.owner` 模型 + `TimerCancelledInsufficientFunds` 监听 |
| CIP-9 / CIP-15 | 不涉及；静态资产 serving 对外部域名同样适用，通过 CIP-14 → CIP-15 v2 延展 |
| CIP-23 v2 | DNS verifier executor 不必 TEE，但 CIP-23 提供的 measurement_binding 与 DNS verifier 可叠加（runner 同时是 TEE runner 与 DNS verifier）|

---

## 域经济 / 保留字段

- 首-party TLD 复用 CIP-14 长度递减年费模型；`.cow` / `.cowboy` 可独立定价 —— `target_pool: REGISTRY_TLD_COW` / `REGISTRY_TLD_COWBOY` 两个独立 SettlementConfig 变体（CIP-14 v2 Part III §6 enum 表）
- 保留名字（`www`, `api`, `dns`, `gateway`, `relay`, `node`, `admin`, `system`）per-TLD 独立治理
- 外部域 v1 **只支持完全 FQDN**；wildcard 延迟

---

## 显式中心化风险（v2 §10）

v2 加入这一章承认 v1 trust assumption：

- **ACME 控制平面** (`acme.cowboy.network`)：单点签发权威；compromise = 任何外部域可被错签证书。Mitigation: multi-sig over zone updates + CT 监控
- **Anycast edge** (`edge.cowboy.network`)：单 hostname 集中权威；anycast 分散流量但不分散控制
- **First-party TLD 运营** (`.cow` / `.cowboy`)：受 ICANN 根制约；不可信根除
- **DNS verifier executor** (`DNS_VERIFIER_EXECUTOR_HASH`)：governance pinned；compromised governance multisig 可换上"永远返 match"的 verifier

这些是 v1 与 ICANN 共存的固有 trade。Mitigation 操作层面（多签、透明日志），非协议层面。

---

## 限制与显式非目标

- 不定义 ICANN 申请 / 运营 `.cow` / `.cowboy` 的商业流程
- 不做代币化域名 RWA
- 不做 wildcard / Handshake / 替代 DNS 根
- Bring-your-own TLS 证书延迟；v1 只支持 Gateway-managed TLS via ACME DNS-01 delegation

---

## 源文档冲突 / 漂移

- CIP-14 v1 `RouteRegistration` 字段表与 CIP-16 v2 `DomainBinding` 不同 —— 后者是前者超集；§3.1 提供显式迁移规则
- v1 `Deterministic` DNS 模式错配；v2 改 `MajorityVote` + 新 verifier check（CIP-2 v2 AMEND 2-A/B）
- v1 `421` 错用；v2 改 `503`

---

## 相关

- [[dns-addressable-actors]] — CIP-14 v2 基础（Route Registry `0x0D` (v2.r2)、Gateway 路由、ingress.http）
- [[../entities/route-registry]] — 系统 Actor `0x0D` (v2.r2, spec-only)
- [[runner-verification]] — CIP-2 v2 新 verifier check
- [[tee-attestation]] — CIP-23 v2，DNS verifier 可叠加 TEE 但非必须
- [[timer-mechanism]] — CIP-5 revised fee_payer 模型（reverify timer 依赖）

## Sources

- `refs/cips/cip-16-custom-domains.md` — v2 spec（Draft, 2026-04-21）：MajorityVote + ExternalDomainCallback opcode 67 + DomainBinding 迁移 + EXTERNAL_REVERIFY_FEE + verified_fqdn 注入 + 503 修正 + anycast/SRV 显式 + 中心化风险
- `refs/cips/cip-2-offchain-compute.md` §2 — DnsTxtRecordMatch / DnsCnameMatch verifier check 定义（AMEND 2-A/B）
- `refs/cips/cip-14-dns-addressable-actors.md` — Route Registry `0x0D` (v2.r2) + IngressDispatch + verified_fqdn injection 上下文
- `refs/cips/cip-13-runner-delegation.md` §1 — opcode 主分配表（67 = ExternalDomainCallback）
