这是一个很好的架构设计问题。我先让入理深有代解现与码中限、权户、Gas账 相关的机制，然后给出一个完整的 Entitlement 机制设计方案。

          
基于对代码库的深入分析，以下是 Entitlement 机制的完整设计方案。

---

# Cowboy Entitlement 机制设计方案

## 1. 现状分析：为什么需要 Entitlement？

通过分析现有代码，当前系统的权限控制是**分散且硬编码**的：

| 现有机制 | 位置 | 局限性 |
|---------|------|--------|
| Token Owner 检查 | [token/admin.rs](file:///home/ubuntu/workspace/node/chain/src/token/admin.rs#L33-L34) `mint.owner != *caller` | 仅限 Token 操作，不可扩展 |
| Freeze Authority | [token/admin.rs](file:///home/ubuntu/workspace/node/chain/src/token/admin.rs#L32) `mint.freeze_authority` | 单一角色，不支持委托 |
| Runner 最低质押 | [runner/registry.rs](file:///home/ubuntu/workspace/node/chain/src/runner/registry.rs#L19) `MIN_STAKE = 50_000_000_000_000` | 硬编码常量，无法动态调整 |
| 交易签名验证 | [execution.rs](file:///home/ubuntu/workspace/node/chain/src/execution.rs#L367) `tx.verify()` | 仅验证身份，不验证权限 |
| 多签支持 | [types/execution.rs](file:///home/ubuntu/workspace/node/types/src/execution.rs#L84) `additional_signers` | 仅用于签名，无角色语义 |

**核心问题**：没有统一的权限抽象层，每个子系统各自实现权限检查，无法支持细粒度的访问控制、权限委托、时间限制等高级场景。

---

## 2. Entitlement 机制总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Entitlement Layer                             │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Entitlement  │  │ Entitlement  │  │   Entitlement         │ │
│  │ Registry     │  │ Checker      │  │   System Actor        │ │
│  │ (存储层)     │  │ (执行层拦截) │  │   (0x0...04)          │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘ │
│         │                 │                       │             │
│  ┌──────▼─────────────────▼───────────────────────▼──────────┐ │
│  │                  Entitlement Types                         │ │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │
│  │  │  Role   │ │Capability│ │ Policy   │ │  Delegation  │  │ │
│  │  │ (角色)  │ │ (能力)   │ │ (策略)   │ │  (委托)      │  │ │
│  │  └─────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │                    │                      │
    ┌────▼────┐         ┌────▼────┐            ┌────▼────┐
    │  Token  │         │ Runner  │            │  Actor  │
    │ System  │         │ System  │            │ System  │
    └─────────┘         └─────────┘            └─────────┘
```

---

## 3. 核心数据结构设计

### 3.1 Entitlement 类型定义

建议放在 `types/src/entitlement.rs`：

```rust
/// 权限标识符：keccak256(scope || action)
pub type EntitlementId = [u8; 32];

/// 权限范围 — 定义权限作用的资源边界
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Scope {
    /// 全局权限（链级别）
    Global,
    /// 针对特定 Actor
    Actor(Address),
    /// 针对特定 Token
    Token([u8; 32]),
    /// 针对特定 Runner
    Runner(Address),
    /// 自定义命名空间
    Namespace(Vec<u8>),
}

/// 权限动作 — 定义可以执行的操作
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Action {
    // ── 通用动作 ──
    All,                    // 通配符
    Read,
    Write,
    Execute,
    Admin,

    // ── Token 动作 ──
    TokenTransfer,
    TokenMint,
    TokenBurn,
    TokenFreeze,
    TokenSetHook,
    TokenTransferOwnership,

    // ── Actor 动作 ──
    ActorDeploy,
    ActorSendMessage,
    ActorExecuteHandler(Vec<u8>),  // 特定 handler 名称

    // ── Runner 动作 ──
    RunnerRegister,
    RunnerSubmitJob,
    RunnerSubmitResult,

    // ── 系统动作 ──
    SystemTransfer,
    SystemCreateAccount,

    // ── 自定义动作 ──
    Custom(Vec<u8>),
}

/// 权限约束 — 限制权限的使用条件
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Constraints {
    /// 生效起始区块高度
    pub valid_from: Option<u64>,
    /// 过期区块高度
    pub valid_until: Option<u64>,
    /// 最大使用次数（0 = 无限）
    pub max_uses: u64,
    /// 已使用次数
    pub used_count: u64,
    /// 单次操作金额上限（CBY wei）
    pub max_amount_per_use: Option<u64>,
    /// 累计金额上限
    pub max_total_amount: Option<u64>,
    /// 已累计金额
    pub total_amount_used: u64,
    /// 每 N 个区块的速率限制
    pub rate_limit: Option<RateLimit>,
    /// 是否可再委托
    pub delegatable: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RateLimit {
    pub max_calls: u32,
    pub per_blocks: u64,
    pub current_window_start: u64,
    pub current_window_count: u32,
}

/// 单条 Entitlement 记录
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Entitlement {
    /// 唯一标识
    pub id: EntitlementId,
    /// 授权者
    pub grantor: Address,
    /// 被授权者
    pub grantee: Address,
    /// 权限范围
    pub scope: Scope,
    /// 允许的动作列表
    pub actions: Vec<Action>,
    /// 约束条件
    pub constraints: Constraints,
    /// 创建区块高度
    pub created_at: u64,
    /// 委托链（追溯授权来源）
    pub delegation_chain: Vec<Address>,
}

/// Entitlement 操作指令
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum EntitlementInstruction {
    /// 授予权限
    Grant {
        grantee: Address,
        scope: Scope,
        actions: Vec<Action>,
        constraints: Constraints,
    },
    /// 撤销权限
    Revoke {
        entitlement_id: EntitlementId,
    },
    /// 委托权限（将自己拥有的权限转授给他人）
    Delegate {
        entitlement_id: EntitlementId,
        delegatee: Address,
        constraints: Constraints,  // 必须是原权限约束的子集
    },
    /// 批量授予
    BatchGrant {
        grants: Vec<(Address, Scope, Vec<Action>, Constraints)>,
    },
    /// 创建角色（命名权限集合）
    CreateRole {
        name: Vec<u8>,
        entitlements: Vec<(Scope, Vec<Action>, Constraints)>,
    },
    /// 将角色分配给地址
    AssignRole {
        role_id: [u8; 32],
        assignee: Address,
    },
    /// 撤销角色
    RevokeRole {
        role_id: [u8; 32],
        assignee: Address,
    },
}
```

### 3.2 存储键设计

建议放在 `token/src/storage_keys.rs` 旁边新增 `entitlement` 模块，或在 `runner/src/storage_keys.rs` 中统一管理：

```rust
pub mod entitlement_registry {
    use cowboy_types::Address;

    /// 单条 entitlement: "ent:{id}" -> Entitlement JSON
    pub fn entitlement_key(id: &[u8; 32]) -> Vec<u8> {
        let mut k = b"ent:".to_vec();
        k.extend_from_slice(id);
        k
    }

    /// 某地址被授予的所有 entitlement ID 列表: "grantee:{addr}" -> Vec<hex>
    pub fn grantee_index_key(grantee: &Address) -> Vec<u8> {
        let mut k = b"grantee:".to_vec();
        k.extend_from_slice(grantee.as_ref());
        k
    }

    /// 某地址授出的所有 entitlement ID 列表: "grantor:{addr}" -> Vec<hex>
    pub fn grantor_index_key(grantor: &Address) -> Vec<u8> {
        let mut k = b"grantor:".to_vec();
        k.extend_from_slice(grantor.as_ref());
        k
    }

    /// 角色定义: "role:{id}" -> Role JSON
    pub fn role_key(id: &[u8; 32]) -> Vec<u8> {
        let mut k = b"role:".to_vec();
        k.extend_from_slice(id);
        k
    }

    /// 地址的角色列表: "roles:{addr}" -> Vec<role_id hex>
    pub fn address_roles_key(addr: &Address) -> Vec<u8> {
        let mut k = b"roles:".to_vec();
        k.extend_from_slice(addr.as_ref());
        k
    }

    /// 快速查询缓存: "check:{grantee}:{scope_hash}:{action_hash}" -> bool
    pub fn check_cache_key(grantee: &Address, scope: &[u8], action: &[u8]) -> Vec<u8> {
        let mut k = b"check:".to_vec();
        k.extend_from_slice(grantee.as_ref());
        k.push(b':');
        k.extend_from_slice(scope);
        k.push(b':');
        k.extend_from_slice(action);
        k
    }
}
```

---

## 4. 系统 Actor 设计

### 4.1 Entitlement Registry Actor

与现有的 Token Registry (`0x0...03`) 和 Runner Registry (`0x0...01`) 模式一致，新增 **Entitlement Registry** 系统 Actor：

```rust
// 在 runner/src/lib.rs 的 SystemActorAddresses 中新增
impl SystemActorAddresses {
    pub fn runner_registry() -> Address { Address::from_low_u64(1) }
    pub fn job_dispatcher() -> Address { Address::from_low_u64(2) }
    pub fn result_verifier() -> Address { Address::from_low_u64(3) }
    // 新增 ↓
    pub fn entitlement_registry() -> Address { Address::from_low_u64(4) }
}
```

在 [genesis.rs](file:///home/ubuntu/workspace/node/chain/src/genesis.rs) 的 `create_runner_system_actors()` 中初始化：

```rust
// 创世时初始化 Entitlement Registry Actor
let entitlement_registry = Actor {
    address: SystemActorAddresses::entitlement_registry(),
    code_hash: Digest::default(),
    code: Vec::new(),
    storage: HashMap::new(),
    mailbox: VecDeque::new(),
    balance: 0,
    nonce: 0,
};
```

---

## 5. 执行层集成

### 5.1 在 ExecutionEngine 中添加 Entitlement Checker

核心思路：在 [execution.rs](file:///home/ubuntu/workspace/node/chain/src/execution.rs) 的 `execute_transaction()` 中，**在执行具体指令之前**插入权限检查：

```rust
// execution.rs 中新增
impl ExecutionEngine {
    /// 检查调用者是否拥有执行某操作的权限
    async fn check_entitlement<S: StateStore>(
        &self,
        store: &S,
        caller: &Address,
        scope: &Scope,
        action: &Action,
        block_height: u64,
        amount: Option<u64>,
    ) -> Result<Option<EntitlementId>, ExecutionError> {
        let registry_address = SystemActorAddresses::entitlement_registry();
        let registry = match store.get_actor(&registry_address).await {
            Ok(Some(r)) => r,
            _ => return Ok(None), // Registry 不存在时默认放行（向后兼容）
        };

        let grantee_key = entitlement_registry::grantee_index_key(caller);
        let entitlement_ids: Vec<String> = registry.storage
            .get(&grantee_key)
            .and_then(|v| serde_json::from_slice(v).ok())
            .unwrap_or_default();

        for id_hex in &entitlement_ids {
            let id_bytes = hex::decode(id_hex).unwrap_or_default();
            if id_bytes.len() != 32 { continue; }
            let mut id = [0u8; 32];
            id.copy_from_slice(&id_bytes);

            let ent_key = entitlement_registry::entitlement_key(&id);
            if let Some(ent_bytes) = registry.storage.get(&ent_key) {
                if let Ok(ent) = serde_json::from_slice::<Entitlement>(ent_bytes) {
                    if self.matches_entitlement(&ent, scope, action, block_height, amount) {
                        return Ok(Some(ent.id));
                    }
                }
            }
        }
        Ok(None)
    }

    fn matches_entitlement(
        &self,
        ent: &Entitlement,
        scope: &Scope,
        action: &Action,
        block_height: u64,
        amount: Option<u64>,
    ) -> bool {
        // 1. 检查范围匹配
        if ent.scope != Scope::Global && ent.scope != *scope {
            return false;
        }
        // 2. 检查动作匹配
        if !ent.actions.contains(&Action::All) && !ent.actions.contains(action) {
            return false;
        }
        // 3. 检查时间约束
        if let Some(from) = ent.constraints.valid_from {
            if block_height < from { return false; }
        }
        if let Some(until) = ent.constraints.valid_until {
            if block_height > until { return false; }
        }
        // 4. 检查使用次数
        if ent.constraints.max_uses > 0 && ent.constraints.used_count >= ent.constraints.max_uses {
            return false;
        }
        // 5. 检查金额限制
        if let (Some(max), Some(amt)) = (ent.constraints.max_amount_per_use, amount) {
            if amt > max { return false; }
        }
        if let (Some(max_total), Some(amt)) = (ent.constraints.max_total_amount, amount) {
            if ent.constraints.total_amount_used + amt > max_total { return false; }
        }
        true
    }
}
```

### 5.2 指令扩展

在 [types/execution.rs](file:///home/ubuntu/workspace/node/types/src/execution.rs) 的 `SystemInstruction` 枚举中新增：

```rust
pub enum SystemInstruction {
    // ... 现有指令 ...

    // ── Entitlement 指令 (编号 30-39) ──
    EntitlementGrant {
        grantee: Address,
        scope: Vec<u8>,      // CBOR-encoded Scope
        actions: Vec<u8>,     // CBOR-encoded Vec<Action>
        constraints: Vec<u8>, // CBOR-encoded Constraints
    },
    EntitlementRevoke {
        entitlement_id: [u8; 32],
    },
    EntitlementDelegate {
        entitlement_id: [u8; 32],
        delegatee: Address,
        constraints: Vec<u8>,
    },
    EntitlementCreateRole {
        name: Vec<u8>,
        entitlements: Vec<u8>, // CBOR-encoded
    },
    EntitlementAssignRole {
        role_id: [u8; 32],
        assignee: Address,
    },
    EntitlementRevokeRole {
        role_id: [u8; 32],
        assignee: Address,
    },
}
```

### 5.3 Gas 成本

在 [GasCosts](file:///home/ubuntu/workspace/node/chain/src/execution.rs#L100) 中新增：

```rust
pub struct GasCosts {
    // ... 现有字段 ...

    // Entitlement 操作
    pub entitlement_grant_cycles: u64,    // 5_000
    pub entitlement_grant_cells: u64,     // 500
    pub entitlement_revoke_cycles: u64,   // 2_000
    pub entitlement_revoke_cells: u64,    // 100
    pub entitlement_delegate_cycles: u64, // 3_000
    pub entitlement_delegate_cells: u64,  // 300
    pub entitlement_check_cycles: u64,    // 500 (每次权限检查)
    pub entitlement_check_cells: u64,     // 0
    pub entitlement_role_cycles: u64,     // 5_000
    pub entitlement_role_cells: u64,      // 500
}
```

---

## 6. 与现有子系统的集成

### 6.1 Token 系统集成

改造 [token/admin.rs](file:///home/ubuntu/workspace/node/chain/src/token/admin.rs) 中的硬编码权限检查：

```rust
// 改造前（当前代码）:
match &mint.freeze_authority {
    Some(fa) if fa == caller => {}
    _ => return Err(ExecutionError::TokenUnauthorized),
}

// 改造后（Entitlement 集成）:
let is_freeze_authority = match &mint.freeze_authority {
    Some(fa) if fa == caller => true,
    _ => false,
};
if !is_freeze_authority {
    // 回退到 Entitlement 检查
    let scope = Scope::Token(*token_id);
    let action = Action::TokenFreeze;
    let has_entitlement = self.check_entitlement(
        store, caller, &scope, &action, block_height, None
    ).await?;
    if has_entitlement.is_none() {
        return Err(ExecutionError::TokenUnauthorized);
    }
}
```

### 6.2 Runner 系统集成

改造 [runner/registry.rs](file:///home/ubuntu/workspace/node/chain/src/runner/registry.rs) 中的质押检查：

```rust
// 改造后：支持通过 Entitlement 降低质押门槛
let effective_min_stake = {
    let scope = Scope::Global;
    let action = Action::RunnerRegister;
    if self.check_entitlement(store, &tx.from, &scope, &action, block_height, None)
        .await?.is_some()
    {
        MIN_STAKE / 2  // 持有 Entitlement 的地址享受 50% 质押折扣
    } else {
        MIN_STAKE
    }
};
```

### 6.3 Actor 系统集成

在 Actor 执行前检查调用权限：

```rust
// 在 execute_actor_handler_impl 中
let scope = Scope::Actor(actor.clone());
let action = Action::ActorExecuteHandler(handler.as_bytes().to_vec());
// 如果 Actor 设置了 entitlement_required 标志，则强制检查
if actor_data.requires_entitlement {
    let has_entitlement = self.check_entitlement(
        store, sender, &scope, &action, block_height, None
    ).await?;
    if has_entitlement.is_none() {
        return Err(ExecutionError::Forbidden);
    }
}
```

### 6.4 PVM SDK 集成

在 [cowboy_sdk/runtime.py](file:///home/ubuntu/workspace/node/pvm/Lib/cowboy_sdk/runtime.py) 中暴露 Entitlement API：

```python
def check_entitlement(grantee: bytes, scope: bytes, action: bytes) -> bool:
    """Check if address has entitlement for scope+action."""
    return pvm_host.check_entitlement(grantee, scope, action)

def grant_entitlement(grantee: bytes, scope: bytes, actions: list, constraints: dict) -> bytes:
    """Grant entitlement (requires caller to be owner/admin of scope)."""
    return pvm_host.grant_entitlement(grantee, scope, actions, constraints)

def revoke_entitlement(entitlement_id: bytes) -> None:
    """Revoke an entitlement (only grantor can revoke)."""
    pvm_host.revoke_entitlement(entitlement_id)
```

---

## 7. 文件变更清单

| 操作 | 文件 | 变更内容 |
|------|------|---------|
| **新增** | `types/src/entitlement.rs` | Entitlement 核心类型定义 |
| **修改** | `types/src/lib.rs` | 导出 entitlement 模块 |
| **修改** | `types/src/execution.rs` | SystemInstruction 新增 Entitlement 指令 (30-39) |
| **新增** | `chain/src/entitlement/mod.rs` | Entitlement 执行逻辑入口 |
| **新增** | `chain/src/entitlement/grant.rs` | Grant/Revoke/Delegate 实现 |
| **新增** | `chain/src/entitlement/checker.rs` | 权限检查逻辑 |
| **新增** | `chain/src/entitlement/role.rs` | 角色管理 |
| **修改** | `chain/src/execution.rs` | 集成 Entitlement Checker + Gas 成本 |
| **修改** | `chain/src/token/admin.rs` | 回退到 Entitlement 检查 |
| **修改** | `chain/src/runner/registry.rs` | 支持 Entitlement 调整质押门槛 |
| **修改** | `chain/src/genesis.rs` | 创世初始化 Entitlement Registry Actor |
| **修改** | `chain/src/rpc.rs` | 新增 `/entitlement/{id}`, `/entitlements/{address}` 端点 |
| **修改** | `chain/src/pvm_host.rs` | 新增 Host API: check/grant/revoke entitlement |
| **修改** | `runner/src/lib.rs` | SystemActorAddresses 新增 `entitlement_registry()` |
| **新增** | `runner/src/storage_keys.rs` 或独立模块 | Entitlement 存储键 |
| **修改** | `pvm/Lib/cowboy_sdk/runtime.py` | 暴露 Entitlement Python API |
| **修改** | `pvm/crates/pvm-host/src/lib.rs` | HostApi trait 新增 entitlement 方法 |
| **修改** | `cli/src/commands.rs` | 新增 `cowboy entitlement` 子命令 |

---

## 8. 典型使用场景

### 场景 1：Token 管理员委托

```
Alice (Token Owner)
  │
  ├── Grant(Bob, Scope::Token(T1), [TokenMint, TokenFreeze], {valid_until: 100000})
  │     → Bob 可以在区块 100000 前铸造和冻结 T1 代币
  │
  └── Grant(Carol, Scope::Token(T1), [TokenTransfer], {max_amount_per_use: 1000})
        → Carol 每次最多转 1000 个 T1 代币
```

### 场景 2：Actor 访问控制

```python
# Python Actor 代码
def handle_message(payload):
    sender = runtime.get_sender()
    # 检查调用者是否有执行权限
    if not runtime.check_entitlement(sender, b"my_actor", b"premium_feature"):
        return b"unauthorized"
    # 执行高级功能...
```

### 场景 3：Runner 白名单

```
Governance
  │
  └── Grant(TrustedRunner, Scope::Global, [RunnerRegister], {
        max_uses: 0,           // 无限次
        delegatable: false,    // 不可再委托
      })
      → TrustedRunner 可以以更低质押注册
```

### 场景 4：时间锁定的权限

```
DAO Multisig
  │
  └── Grant(Executor, Scope::Global, [SystemTransfer], {
        valid_from: block_height + 7200,  // 2 小时后生效（~7200 blocks）
        valid_until: block_height + 14400, // 4 小时后过期
        max_total_amount: 1_000_000,       // 总额上限
      })
```

---

## 9. 向后兼容性

设计遵循以下原则确保向后兼容：

1. **默认放行**：如果 Entitlement Registry Actor 不存在（旧链），所有权限检查返回 `Ok(None)`，不影响现有逻辑
2. **回退机制**：现有的 `owner == caller` 检查保留为第一优先级，Entitlement 作为第二优先级回退
3. **指令编号隔离**：Entitlement 指令使用 30-39 编号段，不与现有 0-20 冲突
4. **创世迁移**：通过 `genesis_migrate` 工具为现有链添加 Entitlement Registry Actor

---

## 10. 安全考量

| 风险 | 缓解措施 |
|------|---------|
| 权限膨胀 | 每地址最多 256 条 Entitlement；角色最多 64 个 |
| 委托链过长 | `delegation_chain` 最大深度 5 |
| 存储膨胀 | Entitlement 创建消耗较高 Cells Gas (500+) |
| 过期清理 | 过期 Entitlement 在被查询时惰性删除 |
| 权限提升 | Delegate 的约束必须是原权限约束的**严格子集** |
| 重放攻击 | Entitlement ID 包含 grantor + nonce，全局唯一 |

---

这个设计方案的核心优势在于：**不破坏现有架构**，通过系统 Actor 模式（与 Token Registry、Runner Registry 一致）引入统一的权限抽象层，同时支持从简单的 owner 检查到复杂的 RBAC + 委托链的渐进式采用。

需要我进一步细化某个部分的实现细节，或者直接开始编码实现吗？
        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          
设计方案已完成。总结一下关键设计决策：

1. **采用系统 Actor 模式**（`0x0...04`），与现有的 Token Registry、Runner Registry 架构风格完全一致，降低认知负担
2. **三层权限模型**：Scope（作用域）× Action（动作）× Constraints（约束），覆盖从简单到复杂的所有场景
3. **向后兼容**：现有的 `owner == caller` 硬编码检查保留为第一优先级，Entitlement 作为回退扩展
4. **PVM 原生支持**：通过 Host API 暴露给 Python Actor，让智能合约可以自主管理细粒度权限

如果你想进一步讨论某个部分的细节，或者直接开始实现，随时告诉我。