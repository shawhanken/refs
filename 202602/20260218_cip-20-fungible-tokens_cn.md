# CIP-20：同质化代币标准

> 平台原生同质化代币，支持可选验证钩子

> **状态：** 草案
> **类型：** 标准跟踪
> **类别：** 核心
> **创建日期：** 2025-11-14
> **更新日期：** 2026-01-18

## 摘要

CIP-20 定义了 Cowboy 的原生同质化代币标准。代币是一等运行时原语——而非 Actor 合约——从而实现最大效率，同时通过可选的**验证钩子**支持暂停、黑名单和合规控制等机构需求。

核心设计选择：
- **平台原生**：代币由运行时管理，而非由单个 Actor 管理
- **验证钩子**：可选的 Actor，可以阻止转账（用于暂停/黑名单/KYC）
- **无修改钩子**：钩子不能更改金额（平台层面无转账手续费）
- **Solana 级别效率**：比基于 Actor 的代币便宜 50-100 倍

对于需要自定义转账逻辑的代币（转账手续费、弹性供应），请使用 CIP-20 Actor 接口实现为 Actor。

---

## 动机

标准化的同质化代币接口对生态系统增长至关重要。每个钱包、DEX 和应用程序都需要以可预测的方式与代币交互。

### 为什么选择平台原生？

将代币实现为 Actor（如以太坊的 ERC-20）存在显著缺陷：

| 关注点 | Actor 代币 | 平台代币 |
|--------|-----------|---------|
| 转账成本 | ~50,000 Cycles | ~1,000 Cycles |
| 批量 100 笔转账 | ~5,000,000 Cycles | ~50,000 Cycles |
| 余额查询 | ~10,000 Cycles | ~100 Cycles |
| 实现方式 | 每个代币冗余实现 | 单一审计运行时 |
| 存储 | Actor KV 开销 | 优化布局 |

Solana 的 SPL Token 程序证明了平台原生代币可以实现 50-100 倍的性能提升。

### 为什么需要验证钩子？

机构代币（稳定币、证券、RWA）需要合规控制：
- **暂停**：在安全事件期间停止所有转账
- **黑名单**：阻止受制裁地址（OFAC 合规）
- **KYC**：限制转账仅限已验证地址
- **冻结**：锁定个别账户

验证钩子提供这些控制而不牺牲效率。钩子可以阻止转账但不能修改金额——保持运行时简单且可预测。

---

## 规范

### 代币数据结构

#### TokenMint（代币铸造记录）

每种代币类型都有一个存储在运行时中的铸造记录：

```python
@dataclass
class TokenMint:
    # 身份标识
    token_id: bytes32           # keccak256(creator || symbol || nonce)
    name: str                   # 例如 "USD Coin"
    symbol: str                 # 例如 "USDC"
    decimals: u8                # 0-18，通常为 6 或 18

    # 供应量
    total_supply: u256          # 当前流通供应量
    max_supply: u256 | None     # 可选上限（None = 无限制）

    # 权限
    owner: address              # 可更新权限和钩子
    mint_authority: address     # 可铸造新代币
    freeze_authority: address | None  # 可冻结个别账户

    # 验证钩子（可选）
    transfer_hook: address | None  # 实现 ITransferHook 的 Actor

    # 元数据
    metadata_uri: str | None    # 链下元数据（logo、描述）
    created_at: u64             # 区块时间戳
```

#### TokenAccount（代币账户）

每个持有者在每种代币下都有一个代币账户：

```python
@dataclass
class TokenAccount:
    owner: address              # 账户持有者
    token_id: bytes32           # 哪种代币
    balance: u256               # 当前余额
    frozen: bool                # 是否被 freeze_authority 冻结？
```

授权额度单独存储：

```python
@dataclass
class TokenAllowance:
    owner: address
    spender: address
    token_id: bytes32
    amount: u256
```

---

### 验证钩子接口

代币可选地指定 `transfer_hook`——一个验证转账的 Actor。钩子接口：

```python
class ITransferHook:
    def can_transfer(
        self,
        token_id: bytes32,
        from_addr: address,
        to_addr: address,
        amount: u256
    ) -> bool:
        """
        在每次转账（包括 transferFrom）之前调用。

        返回值：
            True  - 允许转账
            False - 阻止转账（交易回滚）

        必须是确定性的且具有合理的 Gas 效率。
        不得产生影响转账结果的副作用。
        """
        pass

    def on_transfer(
        self,
        token_id: bytes32,
        from_addr: address,
        to_addr: address,
        amount: u256
    ) -> None:
        """
        在每次成功转账后调用。

        用途：记录日志、分析、更新外部状态。
        不得回滚（失败会被记录但忽略）。
        """
        pass
```

#### 钩子约束

- **不能修改金额**：钩子只验证，不转换
- **不能添加转账**：不能通过钩子实现转账手续费
- **Gas 限制**：钩子调用上限为 50,000 Cycles；超出则转账失败
- **失败 = 回滚**：如果 `can_transfer` 返回 False，转账回滚
- **无递归**：钩子不能触发同一代币的转账

#### 示例：USDC 合规钩子

```python
class USDCComplianceHook(Actor):
    """Circle 的 USDC 合规控制"""

    def init(self, admin: address):
        self.admin = admin
        self.paused = False
        self.blocklist: set[address] = set()

    def can_transfer(self, token_id, from_addr, to_addr, amount) -> bool:
        # 全局暂停检查
        if self.paused:
            return False

        # OFAC 黑名单检查
        if from_addr in self.blocklist:
            return False
        if to_addr in self.blocklist:
            return False

        return True

    def on_transfer(self, token_id, from_addr, to_addr, amount):
        # 发出合规事件用于审计
        emit_event("ComplianceTransfer", {
            "token": token_id,
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "timestamp": block.timestamp
        })

    # 管理员功能
    def pause(self):
        require(msg.sender == self.admin, "unauthorized")
        self.paused = True
        emit_event("Paused", {})

    def unpause(self):
        require(msg.sender == self.admin, "unauthorized")
        self.paused = False
        emit_event("Unpaused", {})

    def add_to_blocklist(self, addr: address):
        require(msg.sender == self.admin, "unauthorized")
        self.blocklist.add(addr)
        emit_event("Blocklisted", {"address": addr})

    def remove_from_blocklist(self, addr: address):
        require(msg.sender == self.admin, "unauthorized")
        self.blocklist.discard(addr)
        emit_event("Unblocklisted", {"address": addr})
```

---

### 宿主函数

Cowboy 运行时为代币操作暴露以下原生函数：

#### 代币创建

```python
def token_create(
    name: str,
    symbol: str,
    decimals: u8,
    initial_supply: u256,
    max_supply: u256 | None = None,
    transfer_hook: address | None = None,
    metadata_uri: str | None = None
) -> bytes32:
    """
    创建新的平台代币。

    调用者将成为 owner、mint_authority 和 freeze_authority。
    初始供应量将铸造给调用者。

    成本：10,000 Cycles + (len(name) + len(symbol) + 256) Cells

    返回：token_id
    """
```

#### 转账

```python
def token_transfer(
    token_id: bytes32,
    to: address,
    amount: u256
) -> bool:
    """
    从调用者向接收者转账代币。

    流程：
    1. 检查调用者余额 >= 金额
    2. 检查调用者账户未冻结
    3. 检查接收者账户未冻结
    4. 如果设置了 transfer_hook：调用 can_transfer()，返回 false 则回滚
    5. 扣除调用者余额，增加接收者余额
    6. 如果设置了 transfer_hook：调用 on_transfer()
    7. 发出 TokenTransfer 事件

    成本：1,000 Cycles + 64 Cells（+ 钩子成本，如已设置）
    """

def token_transfer_from(
    token_id: bytes32,
    from_addr: address,
    to: address,
    amount: u256
) -> bool:
    """
    使用授权额度机制转账。

    要求：调用者拥有来自 from_addr 的授权额度 >= 金额

    成本：1,500 Cycles + 96 Cells（+ 钩子成本，如已设置）
    """

def token_transfer_batch(
    transfers: list[tuple[bytes32, address, u256]]
) -> bool:
    """
    原子性批量转账。

    所有转账要么全部成功，要么全部回滚。
    每笔转账都会调用钩子。

    成本：500 + (500 * len(transfers)) Cycles
    """
```

#### 授权

```python
def token_approve(
    token_id: bytes32,
    spender: address,
    amount: u256
) -> bool:
    """
    授权 spender 代表调用者转账最多 amount 的代币。

    覆盖现有授权额度。

    成本：500 Cycles + 32 Cells
    """

def token_allowance(
    token_id: bytes32,
    owner: address,
    spender: address
) -> u256:
    """
    查询当前授权额度。

    成本：100 Cycles
    """
```

#### 查询

```python
def token_balance_of(
    token_id: bytes32,
    owner: address
) -> u256:
    """
    查询代币余额。

    成本：100 Cycles
    """

def token_total_supply(token_id: bytes32) -> u256:
    """查询总供应量。成本：100 Cycles"""

def token_info(token_id: bytes32) -> TokenMint:
    """查询代币元数据。成本：200 Cycles"""
```

#### 铸造与销毁

```python
def token_mint(
    token_id: bytes32,
    to: address,
    amount: u256
) -> bool:
    """
    铸造新代币。

    要求：调用者 == mint_authority
    回滚条件：超出 max_supply

    成本：1,000 Cycles + 64 Cells
    """

def token_burn(
    token_id: bytes32,
    amount: u256
) -> bool:
    """
    销毁调用者余额中的代币。

    成本：500 Cycles + 64 Cells
    """
```

#### 管理

```python
def token_freeze_account(
    token_id: bytes32,
    account: address
) -> bool:
    """
    冻结账户（阻止所有转账）。

    要求：调用者 == freeze_authority
    """

def token_unfreeze_account(
    token_id: bytes32,
    account: address
) -> bool:
    """
    解冻账户。

    要求：调用者 == freeze_authority
    """

def token_set_hook(
    token_id: bytes32,
    hook: address | None
) -> bool:
    """
    更新转账验证钩子。

    要求：调用者 == owner
    """

def token_transfer_ownership(
    token_id: bytes32,
    new_owner: address
) -> bool:
    """
    转移代币所有权。

    要求：调用者 == owner
    """
```

---

### 事件

平台代币发出标准化事件：

```python
TokenTransfer(token_id: bytes32, from: address, to: address, amount: u256)
TokenApproval(token_id: bytes32, owner: address, spender: address, amount: u256)
TokenMint(token_id: bytes32, to: address, amount: u256)
TokenBurn(token_id: bytes32, from: address, amount: u256)
TokenFrozen(token_id: bytes32, account: address)
TokenUnfrozen(token_id: bytes32, account: address)
TokenHookUpdated(token_id: bytes32, old_hook: address | None, new_hook: address | None)
```

---

### 存储布局

平台代币存储在专用的运行时状态区域：

```
运行时状态树：
├── accounts/
│   └── {address}/
│       └── balance (CBY)
├── actors/
│   └── {actor_address}/
│       └── code, storage
└── tokens/                      ← 平台代币状态
    ├── mints/
    │   └── {token_id} → TokenMint
    ├── balances/
    │   └── {owner}/{token_id} → u256
    ├── allowances/
    │   └── {owner}/{spender}/{token_id} → u256
    └── frozen/
        └── {token_id}/{account} → bool
```

---

## Actor 代币接口

对于需要自定义转账逻辑的代币（转账手续费、弹性供应、复杂归属），请实现为 Actor。Actor 代币应实现此接口以确保生态系统兼容性：

```python
class ICIP20Actor:
    """基于 Actor 的代币标准接口"""

    # 元数据（可选但推荐）
    def name(self) -> str: ...
    def symbol(self) -> str: ...
    def decimals(self) -> u8: ...

    # 核心接口（必需）
    def total_supply(self) -> u256: ...
    def balance_of(self, owner: address) -> u256: ...
    def transfer(self, to: address, amount: u256) -> bool: ...
    def approve(self, spender: address, amount: u256) -> bool: ...
    def allowance(self, owner: address, spender: address) -> u256: ...
    def transfer_from(self, from_addr: address, to: address, amount: u256) -> bool: ...
```

Actor 代币必须发出与平台代币格式匹配的 `Transfer` 和 `Approval` 事件。

### 何时使用 Actor 代币

| 用例 | 平台代币 | Actor 代币 |
|------|---------|-----------|
| 稳定币（USDC、USDT） | ✅ 推荐 | — |
| 包装资产（WETH、WBTC） | ✅ 推荐 | — |
| 实用代币 | ✅ 推荐 | — |
| 可暂停/黑名单代币 | ✅ 使用钩子 | — |
| 转账手续费 | — | ✅ 必需 |
| 弹性供应（stETH） | — | ✅ 必需 |
| 自定义余额逻辑 | — | ✅ 必需 |
| 带委托的治理 | — | ✅ 必需 |

---

## SDK 使用

Cowboy SDK 提供 Python 风格的封装：

```python
from cowboy_sdk import Token

# 创建简单代币
my_token = Token.create(
    name="My Token",
    symbol="MTK",
    decimals=18,
    initial_supply=1_000_000 * 10**18
)

# 创建带钩子的合规稳定币
compliance_hook = deploy(USDCComplianceHook, admin=CIRCLE_ADMIN)

usdc = Token.create(
    name="USD Coin",
    symbol="USDC",
    decimals=6,
    initial_supply=0,  # Circle 按需铸造
    transfer_hook=compliance_hook.address
)

# 转账
Token.transfer(my_token, recipient, 1000 * 10**18)

# 批量转账（高效！）
Token.transfer_batch([
    (usdc, alice, 100 * 10**6),
    (usdc, bob, 200 * 10**6),
    (usdc, charlie, 300 * 10**6),
])

# 查询余额
balance = Token.balance_of(usdc, alice)

# 授权和代理转账
Token.approve(usdc, dex_address, 1000 * 10**6)
# DEX 现在可以调用 Token.transfer_from(usdc, alice, recipient, amount)
```

---

## 安全考虑

### 授权竞态条件

`approve` 函数存在已知的竞态条件（继承自 ERC-20）。如果 Alice 授权 Bob 100，然后更改为 50，Bob 可以抢先交易花费 100 + 50。

**缓解措施**：使用 `increase_allowance` / `decrease_allowance` 模式（本 CIP 未规定，但建议 SDK 实现）。

### 钩子安全

- **Gas 限制**：钩子上限为 50,000 Cycles 以防止 DoS 攻击
- **无重入**：钩子不能触发同一代币的转账
- **确定性**：钩子必须是确定性的；非确定性钩子会破坏共识
- **升级**：更改钩子地址会影响所有未来转账；对关键代币使用时间锁

### 冻结权限

`freeze_authority` 是一项强大的权限。对于去中心化代币，请考虑：
- 设置 `freeze_authority = None`（不可冻结）
- 使用多签或治理合约作为冻结权限
- 对冻结操作实施时间锁延迟

### 整数处理

Python 整数具有任意精度，可防止溢出。但是：
- 实现必须在转账前检查 `balance >= amount`
- 实现必须在代理转账前检查 `allowance >= amount`
- 实现必须在铸造前检查 `total_supply + amount <= max_supply`

---

## 设计原理

### 为什么不采用双模式？

CIP-20 的早期草案提出了两种并行的代币标准（平台和 Actor）。该方案被否决，原因如下：

1. **生态系统碎片化**：每个工具都必须支持两种类型
2. **开发者困惑**：我应该使用哪种模式？
3. **可组合性摩擦**：在一个协议中混合代币类型

当前设计提供了一个覆盖 95% 以上用例的单一平台代币标准，Actor 代币作为自定义逻辑的显式逃生舱口。

### 为什么只做验证钩子？

可以修改转账金额的钩子（如 Uniswap V4）增加了复杂性：
- 不可预测的最终金额
- 复杂的 Gas 估算
- 潜在的隐藏费用

仅验证钩子更简单：
- 转账成功或失败，没有意外
- Gas 可预测（钩子成本有上限）
- 覆盖机构需求（暂停、黑名单、KYC）

需要修改金额的代币（转账手续费）使用 Actor 代币。

### 为什么不兼容 EVM？

Cowboy 是一条 Python 优先的链。真正的 ERC-20 兼容性需要运行 EVM 字节码，增加显著的复杂性。CIP-20 提供了：
- 对以太坊开发者友好的方法命名
- 相似的心智模型（余额、授权、事件）
- 用于将 Cowboy 代币包装为以太坊上 ERC-20 的规范桥（单独的 CIP）

---

## 向后兼容性

这是一个全新标准。没有向后兼容性问题。

---

## 参考实现

平台代币的 Rust 实现请参见 `cowboy-core/src/runtime/tokens.rs`。

Python SDK 封装请参见 `sdk/python/cowboy_sdk/token.py`。
