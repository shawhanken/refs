---
type: entity
tags: [ingress, route-registry, system-actor, cip-14, cip-16]
sources:
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-16-custom-domains.md
last_updated: 2026-04-20
status: draft
---

# Route Registry（系统 Actor `0x0011`）

CIP-14 引入的 ingress 命名权威。维护 FQDN → actor 的规范映射；CIP-16 扩展到三类命名空间（`cowboy.network` / `.cow|.cowboy` / external FQDN）。

---

## 地址归属

`0x0011` 超出 System Actor 原表 `0x01-0x0B` 范围 —— CIP-14 首次使用双字节保留地址段。`0x0012` 同批新增用于 Gateway Registry。见 [[system-actors]]。

---

## Binding 结构（CIP-16 `DomainBinding`，CIP-14 `RouteRegistration` 的超集）

```
DomainBinding {
  fqdn:                string,         // 归一化 ASCII punycode
  actor_address:       Address,
  owner:               Address,
  namespace_kind:      u8,             // 0=COWBOY_NETWORK | 1=FIRST_PARTY_TLD | 2=EXTERNAL
  tld_kind:            u8?,            // 1=.cow | 2=.cowboy | null(EXTERNAL / cowboy.network)
  status:              u8,             // 0=ACTIVE | 1=PENDING | 2=SUSPENDED | 3=EXPIRED | 4=DETACHED
  subdomain_policy:    u8,             // 0=OWNER_ONLY | 1=ACTOR_MANAGED(default) | 2=OPEN
  registered_at:       BlockHeight,
  expires_at:          BlockHeight?,   // 协议自有命名必填；外部可选
  verified_at:         BlockHeight?,   // EXTERNAL only
  next_reverify_at:    BlockHeight?,   // EXTERNAL only
  dns_target:          string?,        // EXTERNAL only
  verification_nonce:  bytes32?,
  verification_method: u8?             // 0=NONE | 1=TXT_CHALLENGE
}
```

> **漂移警告**: CIP-14 §7.1 原始定义的 `RouteRegistration` 字段较少。CIP-16 `DomainBinding` 是演进后的权威；实现时需要把 CIP-14 字段以 `namespace_kind = 0 (COWBOY_NETWORK)` 填充迁移。

---

## Subdomain Policy

| Kind | 含义 |
|---|---|
| `0 OWNER_ONLY` | 仅 owner 可添加子域记录；标准场景 |
| `1 ACTOR_MANAGED`（默认）| Gateway 把完整 `Host` 传给 Actor；子域调度由 Actor 内部 `http.request` handler 处理 |
| `2 OPEN` | 任一持有 `ingress.http` 的 Actor 可在此名下注册子域；社区命名空间 |

**Query 路径限制**：ACTOR_MANAGED 子域只能由父 Actor 自己服务（query 下 `send_message` trap），跨 Actor 委派子域只在 command 路径可行。

---

## 方法表

### 协议自有命名（CIP-14）

| Method | Args | Returns | 语义 |
|---|---|---|---|
| `register` | `name`, `actor_address`, `duration_blocks` | `RouteRegistration` | 注册 `<name>.cowboy.network` |
| `renew` | `name`, `duration_blocks` | `RouteRegistration` | 续费（从现 `expires_at` 延长）|
| `transfer` | `name`, `new_owner` | `RouteRegistration` | 转让所有权 |
| `set_actor` | `name`, `actor_address` | `RouteRegistration` | 重新指向另一 Actor（≈ protocol-level upgrade）|
| `set_subdomain_policy` | `name`, `policy` | `RouteRegistration` | 调整 subdomain 策略 |
| `resolve` | `name` | `Address | null` | 正向解析 |
| `lookup` | `actor_address` | `[string]` | 反向：Actor → names |

### 首 party TLD 扩展（CIP-16）

| Method | 说明 |
|---|---|
| `register_tld_label(tld_kind, label, actor_address, duration_blocks)` | 注册 `label.cow` / `label.cowboy` |
| `renew_tld_label(fqdn, duration_blocks)` | 续费 |
| `transfer_tld_label(fqdn, new_owner)` | 转让 |
| `set_actor(fqdn, actor_address)` | 重新指向（复用 CIP-14 方法）|

### 外部域（CIP-16）

| Method | Caller | 说明 |
|---|---|---|
| `begin_attach_external(fqdn, actor_address)` | owner | 生成 `verification_nonce` + 挑战，状态 `PENDING` |
| `complete_attach_external(fqdn, verification_attestation)` | 系统（CIP-2 verifier 回调）| 验证通过 → `ACTIVE` |
| `reverify_external(fqdn)` | owner | 手动触发周期外重验 |
| `detach_external(fqdn)` | owner | 下架 |
| `suspend_external(fqdn, reason)` | 系统 | 验证失败或目标漂移 → `SUSPENDED` |

---

## 命名经济

**长度递减年费**（§7.5 CIP-14）:

| 长度 | 年费 |
|---|---|
| 3 chars | `PREMIUM_3_FEE`（治理设，最高）|
| 4 chars | `PREMIUM_4_FEE` |
| 5 chars | `PREMIUM_5_FEE` |
| 6+ chars | `BASE_FEE` |

**分配**: `REGISTRY_PROTOCOL_FEE_BPS = 1000 (10%)` 入国库；`GATEWAY_POOL_BPS = 2000 (20%)` 入 Gateway serving pool；余下 70% burn（通缩）。

**生命周期**: Expired → `NAME_GRACE_PERIOD ≈ 30d` 宽限期 → `NAME_AUCTION_DURATION ≈ 7d` 荷兰式递降拍卖 (10× 起拍线性降到 1×) → 重新可注册。

**保留名**（governance holds）: `www`, `api`, `dns`, `gateway`, `relay`, `node`, `cowboy`, `system`, `admin`，per-TLD 独立。

---

## 解析优先级（CIP-16 §7.3）

完全 FQDN 精确查找，不做跨命名空间 shadowing：

1. 精确 external 绑定
2. 精确 first-party TLD 绑定
3. 精确 `cowboy.network` 绑定
4. 父级 subtree → `subdomain_policy` 处理

---

## 相关

- [[gateway]] — Gateway 节点（解析消费者 + command 系统中介）
- [[system-actors]] — `0x0011` / `0x0012` 表位
- [[../concepts/dns-addressable-actors]] — CIP-14 总览
- [[../concepts/custom-domains]] — CIP-16 扩展

## Sources

- `refs/cips/cip-14-dns-addressable-actors.md` — Route Registry 原始定义（§7）
- `refs/cips/cip-16-custom-domains.md` — DomainBinding 扩展与三命名空间（§7）
