---
type: concept
tags: [ingress, dns, tld, external-domain, cip-16]
sources:
  - refs/cips/cip-16-custom-domains.md
  - refs/cips/cip-14-dns-addressable-actors.md
last_updated: 2026-04-20
status: draft
---

# Custom Domains & First-Party TLDs (CIP-16)

Extends CIP-14's Route Registry with two more naming classes: protocol-owned TLD names under `.cow` / `.cowboy`, and externally owned FQDNs like `api.example.com` attached via DNS-based control proof.

---

## 三类命名空间并存

`namespace_kind` 字段区分：

| Kind | 示例 | 治理 | 续费 |
|---|---|---|---|
| `0 = COWBOY_NETWORK` | `alice.cowboy.network` | CIP-14 原生 | 必须 |
| `1 = FIRST_PARTY_TLD` | `alice.cow`, `app.alice.cowboy` | Cowboy 实体控制权威 DNS；`tld_kind ∈ {1=cow, 2=cowboy}` | 必须 |
| `2 = EXTERNAL` | `api.example.com` | 业主在自己的注册商；通过 TXT 挑战证明控制 | 可选 `expires_at`；强制周期重验证 |

解析按**完整 FQDN 精确匹配**；不做跨命名空间 shadowing。

---

## 扩展的 DomainBinding（取代 CIP-14 §7.1 `RouteRegistration`）

CIP-16 的 `DomainBinding` 是 CIP-14 `RouteRegistration` 的超集，加了命名空间类别、状态机、外部验证字段：

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

> **实现注意**: CIP-14 的 `RouteRegistration` 字段子集向 `DomainBinding` 迁移是一次 schema 演进，现有 `*.cowboy.network` 绑定需就地填充 `namespace_kind = 0`。

---

## 外部域绑定流程（TXT 挑战 + 边缘目标 + ACME 委派）

三阶段：

1. **Begin** (`begin_attach_external(fqdn, actor)`)：Route Registry 生成 `verification_nonce`，拼出挑战值 `cowboy:v1:<chain_id>:<fqdn>:<actor>:<nonce>`，状态置 `PENDING`。
2. **Prove**（链下 DNS 操作）:
   - 发布 `_cowboy-challenge.<fqdn> TXT "<challenge>"`
   - 指向边缘：`CNAME <fqdn> edge.cowboy.network`（apex 用 ALIAS/ANAME）
   - 委派 ACME: `_acme-challenge.<fqdn> CNAME <token>.acme.cowboy.network`
3. **Complete**（CIP-2 runner 作为 verifier）: TEE-gated CIP-2 job 校验三项 → 回调 `complete_attach_external` → 状态 `ACTIVE`。

**Reverification**: `next_reverify_at` 时触发 CIP-5 timer；验证失败降为 `SUSPENDED`，Gateway 必须停止服务（HTTP `421` 或 `503`）；owner 修复后再次验证回到 `ACTIVE`。

---

## 与其他 CIP 的耦合

| 依赖 | 角色 |
|---|---|
| CIP-14 | Route Registry & Gateway dispatch 基础不变；绑定记录结构扩展 |
| CIP-2 | 外部验证作为 CIP-2 off-chain job（multi-verifier） |
| CIP-5 | `next_reverify_at` 定期触发用 timer（EOB 语义，或 GBA 替代）|
| CIP-9 / CIP-15 | 不涉及；静态资产 serving 对外部域名同样适用，通过 CIP-14 → CIP-15 延展 |

---

## 域经济 / 保留字段

- 首party TLD 复用 CIP-14 长度递减年费模型；`.cow` / `.cowboy` 可独立定价。
- 保留名字（`www`, `api`, `dns`, `gateway`, `relay`, `node`, `admin`, `system`）per-TLD 独立治理。
- 外部域 v1 **只支持完全 FQDN**；wildcard 延迟。

---

## 限制与显式非目标

- 不定义 ICANN 申请 / 运营 `.cow` / `.cowboy` 的商业流程（默认已拿下）。
- 不做代币化域名 RWA。
- 不做 wildcard / Handshake / 替代 DNS 根。
- Bring-your-own TLS 证书延迟；v1 只支持 Gateway-managed TLS via ACME DNS-01 delegation。

---

## 源文档冲突 / 漂移

- CIP-14 `RouteRegistration` 字段表与 CIP-16 `DomainBinding` 不同 —— 后者是前者超集；CIP-14 未来修订时应合并文本。暂记入 drift 监控。
- CIP-16 外部验证假设 CIP-2 TEE 模式可用（CIP-23 Deterministic + CAE）；在 CIP-23 活化前只能靠 `EconomicBond` Runner 验证。

---

## 相关

- [[dns-addressable-actors]] — CIP-14 基础（Route Registry、Gateway 路由、ingress.http）
- [[../entities/route-registry]] — 系统 Actor `0x0011`
- [[tee-attestation]] — CIP-23，外部验证用的 TEE Runner 模式

## Sources

- `refs/cips/cip-16-custom-domains.md` — 规范（Draft, 2026-03-08, Requires: CIP-14, CIP-2, CIP-3, CIP-5）
- `refs/cips/cip-14-dns-addressable-actors.md` — 基础 Route Registry & Gateway
