---
type: entity
tags: [ingress, route-registry, system-actor, cip-14, cip-16]
sources:
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-16-custom-domains.md
last_updated: 2026-08-15 (地址 0x0D→0x0E 代码更正；前值 2026-05-26)
status: draft
---

# Route Registry（系统 Actor `0x0E`）

> **[2026-08-15 地址更正]** 本页原写 `0x0D`（旧 CIP v2.r2 spec 序列），**代码最终落位是 `0x0E`**（`0x0D` 被 CIP-7 STREAM_KEY_MANAGER 占用）。代码权威表见 [[system-actors]]。下文所有 `0x0D` 请读作 `0x0E`。

CIP-14 v2.r2 引入的 ingress 命名权威。维护 FQDN → actor 的规范映射；CIP-16 v2.r2 扩展到三类命名空间（`cowboy.network` / `.cow|.cowboy` / external FQDN）。

> **状态**：📋 spec-only —— `0x0D` 地址在 `node/runner/src/system_actors.rs` 尚未声明常量。激活时可选两种模式：扩 reserved band 到 `0x0D` + 注册 `Address` const，或采用 CIP-29 `0x1D` 那种 host-interception 模式。详见 [[system-actors]] §"两类激活模型"。

> **地址变迁**：CIP-14 v1 草案使用双字节 `0x0011`；v2.r1 收回到 `0x0C`；v2.r2 (2026-05-11) 让位给代码已实装的 `0x0C = SESSION_ACTOR` (CIP-8)，Route Registry 后移到 `0x0D`。配套：Gateway Registry `0x0E`、Receipt Registry `0x0F`、Container Registry `0x10`、Payment Gate `0x11`。详见 [[system-actors]]。

---

## Binding 结构（CIP-16 v2 `DomainBinding`，CIP-14 v2 `RouteRegistration` 的超集）

```
DomainBinding {
  fqdn:                string,         // 归一化 ASCII punycode
  actor_address:       Address,
  owner:               Address,
  namespace_kind:      u8,             // 0=COWBOY_NETWORK | 1=FIRST_PARTY_TLD | 2=EXTERNAL
  tld_kind:            u8?,            // 1=.cow | 2=.cowboy | null(EXTERNAL / cowboy.network)
  status:              u8,             // 0=ACTIVE | 1=PENDING | 2=SUSPENDED | 3=EXPIRED | 4=DETACHED
  subdomain_policy:    u8,             // 0=OWNER_ONLY (CIP-14 v2 默认) | 1=ACTOR_MANAGED | 2=OPEN
  registered_at:       BlockHeight,
  expires_at:          BlockHeight?,   // 协议自有命名必填；外部可选
  verified_at:         BlockHeight?,   // EXTERNAL only
  next_reverify_at:    BlockHeight?,   // EXTERNAL only
  dns_target:          string?,        // EXTERNAL only
  verification_nonce:  bytes32?,
  verification_method: u8?             // 0=NONE | 1=TXT_CHALLENGE
}
```

**v2 schema 迁移规则**（CIP-16 v2 §3.1）：CIP-14 v1 `RouteRegistration` 现有记录在升级时被**就地迁移**为 `DomainBinding`，默认值：`namespace_kind = 0`（COWBOY_NETWORK）、`tld_kind = 0`、`status = ACTIVE`、其他 EXTERNAL-only 字段 = `null`。`fqdn` 由旧 `name` 字段计算 `name || ".cowboy.network"`。一次性迁移，不删不动现有记录。

---

## Subdomain Policy

| Kind | 含义 |
|---|---|
| `0 OWNER_ONLY`（**CIP-14 v2 默认**）| 仅 owner 可添加子域记录；标准场景 |
| `1 ACTOR_MANAGED` | Gateway 把完整 `Host` 传给 Actor；子域调度由 Actor 内部 `http.request` handler 处理 |
| `2 OPEN` | 任一持有 `ingress.http` 的 Actor 可在此名下注册子域；社区命名空间 |

> **v1 → v2 默认变更**：CIP-14 v1 把 `ACTOR_MANAGED` 当默认；v2 §4.2 改为 `OWNER_ONLY`，原因是 `ACTOR_MANAGED` 默认会让任何子域 GET 都吃 actor 的 `max_query_cycles` 预算（潜在 DoS surface）。

**Read-only 路径限制**：ACTOR_MANAGED 子域只能由父 Actor 自己服务（read-only handler 模式下 `send_message` trap），跨 Actor 委派子域只在 command 路径可行。

---

## 方法表（均为 ActorMessage 到 `0x0D`，不是新 SystemInstruction）

### 协议自有命名（CIP-14 v2）

| Method | Args | Returns | 语义 |
|---|---|---|---|
| `register` | `name`, `actor_address`, `duration_blocks` | `DomainBinding` | 注册 `<name>.cowboy.network` |
| `renew` | `name`, `duration_blocks` | `DomainBinding` | 续费（从现 `expires_at` 延长）|
| `transfer` | `name`, `new_owner` | `DomainBinding` | 转让所有权 |
| `set_actor` | `name`, `actor_address` | `DomainBinding` | 重新指向另一 Actor（≈ protocol-level upgrade）|
| `set_subdomain_policy` | `name`, `policy` | `DomainBinding` | 调整 subdomain 策略 |
| `resolve` | `name` | `Address \| null` | 正向解析（read_handler RPC）|
| `lookup` | `actor_address` | `[string]` | 反向：Actor → names |

### 首-party TLD 扩展（CIP-16 v2 §4）

| Method | 说明 |
|---|---|
| `register_tld_label(tld_kind, label, actor_address, duration_blocks)` | 注册 `label.cow` / `label.cowboy` |
| `renew_tld_label(fqdn, duration_blocks)` | 续费 |
| `transfer_tld_label(fqdn, new_owner)` | 转让 |
| `set_actor(fqdn, actor_address)` | 重新指向（复用 CIP-14 方法）|

### 外部域（CIP-16 v2 §5）

| Method | Caller | 说明 |
|---|---|---|
| `begin_attach_external(fqdn, actor_address)` | owner | 生成 `verification_nonce` + 挑战，状态 `PENDING`；要求 `dns.attach_external` entitlement |
| `_dns.callback` (via opcode 67 `ExternalDomainCallback`) | **仅 `RESULT_VERIFIER=0x03`** | 系统中介；CIP-2 verifier `MajorityVote` 完成后回调；状态 `PENDING → ACTIVE` |
| `reverify_external(fqdn)` | owner | 手动触发周期外重验 |
| `detach_external(fqdn)` | owner | 下架 |
| `_suspend_external(fqdn, reason)` | 系统 | 验证失败 / 目标漂移 / `INSUFFICIENT_REVERIFY_FEE` / `INSUFFICIENT_TIMER_FUEL` → `SUSPENDED` |

> `ExternalDomainCallback` 是 v2 系列下唯一的新 SystemInstruction（**opcode 67**，CIP-13 v2 §1 主表）；其他 method 均为普通 ActorMessage。

---

## 命名经济

**长度递减年费**（CIP-14 §7.5 / CIP-16 v2 §4）:

| 长度 | 年费 |
|---|---|
| 3 chars | `PREMIUM_3_FEE`（治理设，最高）|
| 4 chars | `PREMIUM_4_FEE` |
| 5 chars | `PREMIUM_5_FEE` |
| 6+ chars | `BASE_FEE` |

**分配（CIP-14 v2 §4.5，走 SettlementConfig）**：注册 / 续费费在 `system:registry_settlement_config`（`target_pool: REGISTRY`，CIP-14 v2 Part III §6 enum 表）下分账；默认 `burn 70 / treasury 15 / gateway_pool 15`，由 `UpdateSettlementConfig` (opcode 40) 调整；TLD 可选独立配置 `target_pool: REGISTRY_TLD_COW` / `REGISTRY_TLD_COWBOY`。

**生命周期**: Expired → `NAME_GRACE_PERIOD ≈ 30d` 宽限期 → `NAME_AUCTION_DURATION ≈ 7d` 荷兰式递降拍卖 (10× 起拍线性降到 1×) → 重新可注册。

**保留名**（governance holds）: `www`, `api`, `dns`, `gateway`, `relay`, `node`, `cowboy`, `system`, `admin`，per-TLD 独立。

---

## 外部域绑定 fee chain（CIP-16 v2 §5.7 / §5.8 / §5.10）

外部 domain 维护对 owner 来说有 **三层费用**，缺一即降级：

| 费用 | 来源 | 触发 | 失败 → |
|---|---|---|---|
| `EXTERNAL_REVERIFY_FEE` | CIP-16 v2 §5.8 | 每次 reverify 触发 | `status=SUSPENDED, reason=INSUFFICIENT_REVERIFY_FEE`（不派发 verifier job）|
| Reverify timer `max_cost` | CIP-5 revised §6.3 | 每个 reverify timer 即将 fire 前 | timer 自毁 (`TimerCancelledInsufficientFunds`) → 二线兜底 `INSUFFICIENT_TIMER_FUEL` |
| 验证 job 共识 runners 报酬 | CIP-2 §5 settlement | verifier job 提交结果 | 走标准 settlement |

Route Registry 必须订阅 `TimerCancelledInsufficientFunds` 事件以触发二线 SUSPENDED 路径，避免 binding 永远卡在 ACTIVE 但实际无验证。

---

## 解析优先级（CIP-16 v2 §3.2）

完全 FQDN 精确查找；命名空间互不重叠（不做跨命名空间 shadowing）。

1. 精确 external 绑定
2. 精确 first-party TLD 绑定
3. 精确 `cowboy.network` 绑定
4. 父级 subtree → `subdomain_policy` 处理

---

## 相关

- [[gateway]] — Gateway 节点（解析消费者 + command 系统中介，地址 `0x0E`）
- [[system-actors]] — `0x0D` (Route) / `0x0E` (Gateway) / `0x0F` (Receipt) 三段 v2.r2 spec-only
- [[../concepts/dns-addressable-actors]] — CIP-14 总览
- [[../concepts/custom-domains]] — CIP-16 扩展

## Sources

- `refs/cips/cip-14-dns-addressable-actors.md` Part II §4 — Route Registry 定义 + 0x0D 地址（v2.r2）+ OWNER_ONLY 默认
- `refs/cips/cip-16-custom-domains.md` Part II — DomainBinding schema + 三命名空间 + 系统中介 callback (opcode 67) + reverify fee chain
- `refs/cips/cip-13-runner-delegation.md` §1 — opcode 主分配表（67 = `ExternalDomainCallback`）
