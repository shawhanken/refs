---
title: "CIP-20: Fungible Token Standard"
description: Platform-native fungible tokens with optional validation hooks
icon: coins
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2025-11-14
  **Updated:** 2026-01-18
</Note>

<Warning>
  **Type Update (2026-03-27):** Token amounts use `u128` in the implementation (not `u256` as originally specified). u128 supports up to ~3.4 × 10³⁸, sufficient for any reasonable token economy with 18 decimal places. u128 executes in two native CPU instructions vs. software emulation for u256.
</Warning>

<Warning>
  **修正案（2026-04-15）**: `token_hook_max_cycles = 50,000` 为**阶段 1** 声明，当前代码 **尚未真正扣费与中断**（"declared but not enforced"），阶段 2 才接入。详见 [`analysis/2026-04-15_documentation_amendments.md §六·补`](../analysis/2026-04-15_documentation_amendments.md)。
</Warning>

<Tip>
  **CBY Relationship:** CBY is the protocol-layer native currency and is NOT a CIP-20 token. CIP-20 manages user-created fungible tokens.
</Tip>

## Abstract

CIP-20 defines Cowboy's native fungible token standard. Tokens are first-class runtime primitives—not actor contracts—enabling maximum efficiency while supporting institutional requirements like pause, blacklist, and compliance controls through optional **validation hooks**.

Key design choices:
- **Platform-native**: Tokens managed by runtime, not individual actors
- **Validation hooks**: Optional actor that can block transfers (for pause/blacklist/KYC)
- **No modification hooks**: Hooks cannot change amounts (no fee-on-transfer at platform level)
- **Solana-level efficiency**: 50-100x cheaper than actor-based tokens

For tokens requiring custom transfer logic (fee-on-transfer, rebasing), implement as an actor using the CIP-20 actor interface.

---

## Motivation

A standard fungible token interface is critical for ecosystem growth. Every wallet, DEX, and application needs to interact with tokens predictably.

### Why Platform-Native?

Implementing tokens as actors (like Ethereum's ERC-20) has significant drawbacks:

| Concern | Actor Tokens | Platform Tokens |
|---------|--------------|-----------------|
| Transfer cost | ~50,000 Cycles | ~1,000 Cycles |
| Batch 100 transfers | ~5,000,000 Cycles | ~50,000 Cycles |
| Balance query | ~10,000 Cycles | ~100 Cycles |
| Implementation | Redundant per token | Single audited runtime |
| Storage | Actor KV overhead | Optimized layout |

Solana's SPL Token program demonstrates that platform-native tokens achieve 50-100x better performance.

### Why Validation Hooks?

Institutional tokens (stablecoins, securities, RWAs) require compliance controls:
- **Pause**: Halt all transfers during security incidents
- **Blacklist**: Block sanctioned addresses (OFAC compliance)
- **KYC**: Restrict transfers to verified addresses
- **Freeze**: Lock individual accounts

Validation hooks provide these controls without sacrificing efficiency. The hook can block a transfer but cannot modify amounts—keeping the runtime simple and predictable.

---

## Specification

### Token Data Structures

#### TokenMint

Each token type has a mint record stored in the runtime:

```python
@dataclass
class TokenMint:
    # Identity
    token_id: bytes32           # keccak256(creator || symbol || nonce)
    name: str                   # e.g., "USD Coin"
    symbol: str                 # e.g., "USDC"
    decimals: u8                # 0-18, typically 6 or 18

    # Supply
    total_supply: u256          # Current circulating supply
    max_supply: u256 | None     # Optional cap (None = unlimited)

    # Authorities
    owner: address              # Can update authorities and hook
    mint_authority: address     # Can mint new tokens
    freeze_authority: address | None  # Can freeze individual accounts

    # Validation hook (optional)
    transfer_hook: address | None  # Actor implementing ITransferHook

    # Metadata
    metadata_uri: str | None    # Off-chain metadata (logo, description)
    created_at: u64             # Block timestamp
```

#### TokenAccount

Each holder has a token account per token:

```python
@dataclass
class TokenAccount:
    owner: address              # Account holder
    token_id: bytes32           # Which token
    balance: u256               # Current balance
    frozen: bool                # Frozen by freeze_authority?
```

Allowances are stored separately:

```python
@dataclass
class TokenAllowance:
    owner: address
    spender: address
    token_id: bytes32
    amount: u256
```

---

### Validation Hook Interface

Tokens MAY specify a `transfer_hook`—an actor that validates transfers. The hook interface:

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
        Called before every transfer (including transferFrom).

        Returns:
            True  - Allow the transfer
            False - Block the transfer (transaction reverts)

        MUST be deterministic and reasonably gas-efficient.
        MUST NOT have side effects that affect transfer outcome.
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
        Called after every successful transfer.

        Use for: logging, analytics, updating external state.
        MUST NOT revert (failures are logged but ignored).
        """
        pass
```

#### Hook Constraints

- **Cannot modify amounts**: Hooks validate, they don't transform
- **Cannot add transfers**: No fee-on-transfer via hooks
- **Gas limit**: Hook calls capped at 50,000 Cycles and 50,000 Cells; exceeded = transfer fails
- **Failure = revert**: If `can_transfer` returns False, transfer reverts
- **No recursion**: Hooks cannot trigger transfers of the same token

#### Example: USDC Compliance Hook

```python
class USDCComplianceHook(Actor):
    """Circle's compliance controls for USDC"""

    def init(self, admin: address):
        self.admin = admin
        self.paused = False
        self.blocklist: set[address] = set()

    def can_transfer(self, token_id, from_addr, to_addr, amount) -> bool:
        # Global pause check
        if self.paused:
            return False

        # OFAC blocklist check
        if from_addr in self.blocklist:
            return False
        if to_addr in self.blocklist:
            return False

        return True

    def on_transfer(self, token_id, from_addr, to_addr, amount):
        # Emit compliance event for auditing
        emit_event("ComplianceTransfer", {
            "token": token_id,
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "timestamp": block.timestamp
        })

    # Admin functions
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

### Host Functions

The Cowboy runtime exposes these native functions for token operations:

#### Token Creation

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
    Create a new platform token.

    The caller becomes owner, mint_authority, and freeze_authority.
    Initial supply is minted to the caller.

    Cost: 10,000 Cycles + (len(name) + len(symbol) + 256) Cells

    Returns: token_id
    """
```

#### Transfers

```python
def token_transfer(
    token_id: bytes32,
    to: address,
    amount: u256
) -> bool:
    """
    Transfer tokens from caller to recipient.

    Flow:
    1. Check caller balance >= amount
    2. Check caller account not frozen
    3. Check recipient account not frozen
    4. If transfer_hook set: call can_transfer(), revert if false
    5. Debit caller, credit recipient
    6. If transfer_hook set: call on_transfer()
    7. Emit TokenTransfer event

    Cost: 1,000 Cycles + 64 Cells (+ hook cost if set)
    """

def token_transfer_from(
    token_id: bytes32,
    from_addr: address,
    to: address,
    amount: u256
) -> bool:
    """
    Transfer using allowance mechanism.

    Requires: caller has allowance from from_addr >= amount

    Cost: 1,500 Cycles + 96 Cells (+ hook cost if set)
    """

def token_transfer_batch(
    transfers: list[tuple[bytes32, address, u256]]
) -> bool:
    """
    Batch multiple transfers atomically.

    All transfers succeed or all revert.
    Hooks are called for each transfer.

    Cost: 500 + (500 * len(transfers)) Cycles
    """
```

#### Approvals

```python
def token_approve(
    token_id: bytes32,
    spender: address,
    amount: u256
) -> bool:
    """
    Approve spender to transfer up to amount on caller's behalf.

    Overwrites existing allowance.

    Cost: 500 Cycles + 32 Cells
    """

def token_allowance(
    token_id: bytes32,
    owner: address,
    spender: address
) -> u256:
    """
    Query current allowance.

    Cost: 100 Cycles
    """
```

#### Queries

```python
def token_balance_of(
    token_id: bytes32,
    owner: address
) -> u256:
    """
    Query token balance.

    Cost: 100 Cycles
    """

def token_total_supply(token_id: bytes32) -> u256:
    """Query total supply. Cost: 100 Cycles"""

def token_info(token_id: bytes32) -> TokenMint:
    """Query token metadata. Cost: 200 Cycles"""
```

#### Minting and Burning

```python
def token_mint(
    token_id: bytes32,
    to: address,
    amount: u256
) -> bool:
    """
    Mint new tokens.

    Requires: caller == mint_authority
    Reverts if: would exceed max_supply

    Cost: 1,000 Cycles + 64 Cells
    """

def token_burn(
    token_id: bytes32,
    amount: u256
) -> bool:
    """
    Burn tokens from caller's balance.

    Cost: 500 Cycles + 64 Cells
    """
```

#### Administration

```python
def token_freeze_account(
    token_id: bytes32,
    account: address
) -> bool:
    """
    Freeze an account (block all transfers).

    Requires: caller == freeze_authority
    """

def token_unfreeze_account(
    token_id: bytes32,
    account: address
) -> bool:
    """
    Unfreeze an account.

    Requires: caller == freeze_authority
    """

def token_set_hook(
    token_id: bytes32,
    hook: address | None
) -> bool:
    """
    Update the transfer validation hook.

    Requires: caller == owner
    """

def token_transfer_ownership(
    token_id: bytes32,
    new_owner: address
) -> bool:
    """
    Transfer token ownership.

    Requires: caller == owner
    """
```

---

### Events

Platform tokens emit standardized events:

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

### Storage Layout

Platform tokens are stored in a dedicated runtime state section:

```
Runtime State Tree:
├── accounts/
│   └── {address}/
│       └── balance (CBY)
├── actors/
│   └── {actor_address}/
│       └── code, storage
└── tokens/                      ← Platform token state
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

## Actor Token Interface

For tokens requiring custom transfer logic (fee-on-transfer, rebasing, complex vesting), implement as an actor. Actor tokens SHOULD implement this interface for ecosystem compatibility:

```python
class ICIP20Actor:
    """Standard interface for actor-based tokens"""

    # Metadata (optional but recommended)
    def name(self) -> str: ...
    def symbol(self) -> str: ...
    def decimals(self) -> u8: ...

    # Core interface (required)
    def total_supply(self) -> u256: ...
    def balance_of(self, owner: address) -> u256: ...
    def transfer(self, to: address, amount: u256) -> bool: ...
    def approve(self, spender: address, amount: u256) -> bool: ...
    def allowance(self, owner: address, spender: address) -> u256: ...
    def transfer_from(self, from_addr: address, to: address, amount: u256) -> bool: ...
```

Actor tokens MUST emit `Transfer` and `Approval` events matching the platform token format.

### When to Use Actor Tokens

| Use Case | Platform Token | Actor Token |
|----------|----------------|-------------|
| Stablecoins (USDC, USDT) | ✅ Recommended | — |
| Wrapped assets (WETH, WBTC) | ✅ Recommended | — |
| Utility tokens | ✅ Recommended | — |
| Pausable/blacklist tokens | ✅ Use hooks | — |
| Fee-on-transfer | — | ✅ Required |
| Rebasing (stETH) | — | ✅ Required |
| Custom balance logic | — | ✅ Required |
| Governance with delegation | — | ✅ Required |

---

## SDK Usage

The Cowboy SDK provides a Pythonic wrapper:

```python
from cowboy_sdk import Token

# Create a simple token
my_token = Token.create(
    name="My Token",
    symbol="MTK",
    decimals=18,
    initial_supply=1_000_000 * 10**18
)

# Create a compliant stablecoin with hooks
compliance_hook = deploy(USDCComplianceHook, admin=CIRCLE_ADMIN)

usdc = Token.create(
    name="USD Coin",
    symbol="USDC",
    decimals=6,
    initial_supply=0,  # Circle mints on demand
    transfer_hook=compliance_hook.address
)

# Transfer
Token.transfer(my_token, recipient, 1000 * 10**18)

# Batch transfer (efficient!)
Token.transfer_batch([
    (usdc, alice, 100 * 10**6),
    (usdc, bob, 200 * 10**6),
    (usdc, charlie, 300 * 10**6),
])

# Check balance
balance = Token.balance_of(usdc, alice)

# Approve and transferFrom
Token.approve(usdc, dex_address, 1000 * 10**6)
# DEX can now call Token.transfer_from(usdc, alice, recipient, amount)
```

---

## Security Considerations

### Approval Race Condition

The `approve` function has a known race condition (inherited from ERC-20). If Alice approves Bob for 100, then changes to 50, Bob can front-run and spend 100 + 50.

**Mitigation**: Use `increase_allowance` / `decrease_allowance` patterns (not specified in this CIP but recommended for SDK).

### Hook Security

- **Gas limits**: Hooks are capped at 50,000 Cycles and 50,000 Cells to prevent DoS
- **No reentrancy**: Hooks cannot trigger transfers of the same token
- **Determinism**: Hooks MUST be deterministic; non-deterministic hooks break consensus
- **Upgrades**: Changing the hook address affects all future transfers; use timelocks for critical tokens

### Freeze Authority

The `freeze_authority` is a powerful privilege. For decentralized tokens, consider:
- Setting `freeze_authority = None` (no freezing)
- Using a multisig or governance contract as freeze authority
- Implementing timelock delays for freeze operations

### Integer Handling

Python integers have arbitrary precision, preventing overflow. However:
- Implementations MUST check `balance >= amount` before transfers
- Implementations MUST check `allowance >= amount` before transferFrom
- Implementations MUST check `total_supply + amount <= max_supply` before minting

---

## Rationale

### Why Not Dual-Mode?

Earlier drafts of CIP-20 proposed two parallel token standards (platform and actor). This was rejected because:

1. **Ecosystem fragmentation**: Every tool must support both types
2. **Developer confusion**: Which mode should I use?
3. **Composability friction**: Mixing token types in one protocol

The current design provides a single platform token standard covering 95%+ of use cases, with actor tokens as an explicit escape hatch for custom logic.

### Why Validation-Only Hooks?

Hooks that can modify transfer amounts (like Uniswap V4) add complexity:
- Unpredictable final amounts
- Complex gas estimation
- Potential for hidden fees

Validation-only hooks are simpler:
- Transfer succeeds or fails, no surprises
- Gas is predictable (hook cost is bounded)
- Covers institutional requirements (pause, blacklist, KYC)

Tokens needing amount modification (fee-on-transfer) use actor tokens.

### Why Not EVM Compatibility?

Cowboy is a Python-first chain. True ERC-20 compatibility would require running EVM bytecode, adding significant complexity. Instead, CIP-20 provides:
- Familiar method names for Ethereum developers
- Similar mental model (balances, allowances, events)
- Canonical bridge for wrapping Cowboy tokens as ERC-20s on Ethereum (separate CIP)

---

## Backwards Compatibility

This is a new standard. No backwards compatibility concerns.

---

## Reference Implementation

See `cowboy-core/src/runtime/tokens.rs` for the Rust implementation of platform tokens.

See `sdk/python/cowboy_sdk/token.py` for the Python SDK wrapper.
