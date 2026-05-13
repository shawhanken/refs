# CIP-28: Cowboy Agent Banking

- **Status**: Draft
- **Date**: 2026-05-12
- **In scope**: BankActor system actor, card data model, instruction set, gas charge path, the policy triad (limits / whitelist / freeze), multi-bank + fiat bridge, roadmap & compatibility
- **Out of scope**: On-chain KYC, multi-holder cards, protocol-level paymaster abstraction, card-to-card transfer primitives, **UI design** (delivered separately — see `examples/cip28_agent_banking/index.html`)

---

## 0. Summary

Decouple "gas funds + risk controls + compliance handle" from regular actor addresses, and lift them into a first-class **banking account** primitive. A new system actor `BankActor (0x0D)`:

- **Card = on-chain counterpart of a physical bank card**: deterministically derived 20-byte address, holds multi-token balances (vault model), supports expiry/renew, spending limits, whitelist, freeze, ownership transfer.
- **agent = cardholder**, **owner = guardian** (initially a user; later may transfer to the agent itself). Separation of duty.
- **Third gas-charge path**: when a tx's `fee_payer_override` points at a card address, the BankActor validation pipeline kicks in — coexists with the current actor-pays / owner-pays paths.
- **Single compliance perimeter**: nothing else in the Cowboy ecosystem (actor / token / session / cbss) needs to be compliant — the compliance handle lives inside BankActor + each bank's operator + off-chain gateway.
- **Funding narrative**: "Every agent in the Agent era needs a banking account; traditional banks don't support that; we do."

Seven main sections, scoped tightly enough to drop straight into an implementation plan.

---

## 1. Architecture Overview & System Actor Position

### 1.1 Positioning

**Cowboy Agent Banking** is a new system actor `BankActor` at address `0x0000…000D`. It carries four responsibilities:

> **Protocol / Bank — two layers**: this CIP defines the **protocol** Cowboy Agent Banking (= the BankActor primitive + card derivation rules); the **first bank** deployed on top of it at genesis is **Cowboy Banking** (`bank_id = 1`). The latter is just the first instance of the former — analogous to Visa (network) vs. Chase (issuer).

1. Card lifecycle (issue / renew / close / transfer ownership)
2. Multi-token balance custody (card address is itself a token holder)
3. Risk controls (rolling-period spending limits, receiver / syscall whitelist, freeze)
4. Fiat-bridge mint voucher verification (FiatMintVoucher signed by the off-chain gateway)

### 1.2 Position in the protocol stack

```
┌─────────────────────────────────────────────────────────────┐
│  User Wallet / Agent Owner                                  │
│  (regular EOA or multisig)                                  │
└────┬─────────────────────────┬──────────────────────────────┘
     │ IssueCard / Deposit     │ SetPolicy / TransferOwnership
     ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│  BankActor  (system actor, 0x0000…000D)                     │
│  ─────────────────────────────────────────                  │
│  · Card state (multi-token vault + policy + lifecycle)      │
│  · Bank registry (Cowboy Banking + third-party banks)       │
│  · Per-card rolling spending window                         │
│  · BankOperator role → freeze / fiat-mint-voucher verify    │
└────┬─────────────────────────┬──────────────────────────────┘
     │ ChargeGas (internal)    │ read-only lookups
     ▼                         ▼
┌────────────────────────┐   ┌──────────────────────────────┐
│  Transaction Engine    │   │  Actor (the agent)           │
│  fee_payer_override =  │   │  · holds default_card_addr   │
│      <card_address>    │   │    (stored in BankActor)     │
└────────────────────────┘   └──────────────────────────────┘
                                          ▲
┌─────────────────────────────────────────┴───────────────────┐
│  Off-chain Compliance Gateway  (Cowboy Banking operator)    │
│  · KYC / Stripe top-ups / fiat bridge                       │
│  · Issues FiatMintVoucher → BankActor.MintFromVoucher verify│
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Relation to existing systems

| Existing piece | Relation |
|---|---|
| `fee_payer_override` | **New tx-level field** `tx.fee_payer_override: Option<Address>`. Note: the existing `ScheduledTimer.fee_payer_override` (`pvm_executor.rs:24`, timer subsystem only) is a same-named but distinct field; this CIP introduces a new field at the tx top level that reuses the semantic but not the struct location. When the engine resolves `tx.fee_payer`, if the address hits a BankActor card derivation, charging is routed through the BankActor handler instead of the plain debit path |
| `SESSION_ACTOR (0x0C)` | **Isomorphic, independent**. Session is a one-shot escrow + voucher settlement; Bank is a long-lived account + policy. SessionActor is not reused |
| CBSS (CIP-24) | Borrows its namespacing + policy/version state layering style (CBSS's actual rolling-window is a proxy-local rate limiter, semantically different from BankActor's on-chain windows) |
| Token (CIP-20) | A card holds CIP-20 balances using the standard ledger — the card address is just a normal token holder |
| CIP-12 Governance | `RegisterBank` and other protocol-level actions go through CIP-12 governance proposals (Tier 1 registry write; Tier 3 if a BankActor bytecode upgrade is also needed). Cowboy Banking's `BankOperator` is bound by default to a **Cowboy Banking operator multisig** (signer set determined by CIP-12 governance — not the Cowboy Foundation from CIP-12 §3.1; the Foundation has no protocol authority). Third-party banks bring their own operator multisig at registration time |

### 1.4 Roles & authorities

| Role | On-chain identity | Can do | Cannot do |
|---|---|---|---|
| **Card Holder Agent** | actor address | Spend gas via the card (subject to policy) | Modify rules, withdraw, freeze |
| **Card Owner** | EOA or the agent itself | Deposit, SetPolicy, Renew, TransferOwnership, close the card | Touch other people's cards |
| **BankOperator** (one per bank) | multisig | Freeze / Unfreeze cards under its bank; sign FiatMintVoucher | Modify card rules, seize funds (freeze only disables charges, doesn't confiscate) |
| **BankActor protocol layer** | 0x0D | Enforce invariants; charge gas; record rolling windows | No independent power — every privileged action originates from one of the roles above |
| **Off-chain Compliance Gateway** | off-chain | KYC, Stripe collection, sign mint vouchers | No on-chain write rights; on-chain redemption requires BankOperator-recognized signature |

---

## 2. Data Model & Card Address Derivation

### 2.1 Top-level state layout (under BankActor 0x0D)

Following the `b"<tag>:"` ASCII prefix style used by other system actors (CBSS uses `b"secret:"`, SessionActor uses `b"session:"`, CIP-20 token uses `b"bal:"`):

| Key pattern | Value | Purpose |
|---|---|---|
| `b"bank:" \|\| bank_id_be4` | `BankEntry` | Bank registry entry |
| `b"bank_seq"` | `u32_be4` | Next bank_id |
| `b"card:" \|\| card_addr_20` | `CardEntry` | Full card state (policy, window) |
| `b"card_by_owner:" \|\| owner_20 \|\| bank_id_be4 \|\| idx_be4` | `card_addr_20` | Owner-side card list index |
| `b"card_by_agent:" \|\| agent_20 \|\| bank_id_be4 \|\| idx_be4` | `card_addr_20` | Agent-side card list index |
| `b"agent_default_card:" \|\| agent_20` | `card_addr_20` | Agent's default gas card |
| `b"issue_nonce:" \|\| bank_id_be4 \|\| owner_20 \|\| agent_20` | `u64_be8` | Next derivation nonce for the (bank, owner, agent) triple |
| `b"voucher_used:" \|\| voucher_id_32` | `1` | FiatMintVoucher replay-protection marker |

Token balances themselves are **not stored in BankActor** — the card address is a plain token holder; balances live in the existing CBY ledger / CIP-20 token actor. BankActor only stores non-balance card metadata.

### 2.2 `BankEntry`

```rust
struct BankEntry {
    bank_id:           u32,
    name:              Vec<u8>,         // 1..=32 bytes, ASCII
    operator:          Address,         // multisig; can freeze / sign FiatMintVoucher
    fiat_mint_signer:  Option<Address>, // signing key for fiat mint; None = bank does not support fiat bridge
    status:            BankStatus,      // Active | Paused
    registered_at:     u64,             // block height
}

enum BankStatus { Active, Paused }
```

Cowboy Banking is written at genesis with `bank_id = 1`, operator = Cowboy Banking operator multisig (signer set determined by CIP-12 governance).

### 2.3 `CardEntry`

```rust
struct CardEntry {
    // ── Identity ──────────────────────────────
    card_address:           Address,    // identical to the key, for reverse lookup
    bank_id:                u32,
    owner:                  Address,    // guardian / the agent itself
    agent:                  Address,    // the actor this card serves
    issue_nonce:            u64,        // nonce used in derivation
    created_at:             u64,
    last_renewed_at:        u64,

    // ── Lifecycle ─────────────────────────────
    expires_at:             Option<u64>,// block height; None = no expiry (protocol-level escape hatch, not exposed in UI)
    status:                 CardStatus, // Active | Frozen | Closed | Expired

    // ── Payment preference ────────────────────
    gas_payment_token:      PayCurrency,// Native(CBY) | Token(token_actor_addr)

    // ── Policy ────────────────────────────────
    policy:                 CardPolicy,

    // ── Rolling spending window ───────────────
    window:                 SpendWindow,
}

enum CardStatus { Active, Frozen, Closed, Expired }
enum PayCurrency { Native, Token(Address) }
```

Day-1 constraint: `gas_payment_token` may only be **Native CBY** or **the official stablecoin U** (a whitelist of token addresses configured in genesis). Other CIP-20 tokens may sit on the card as reserves / payroll, but cannot directly pay gas.

### 2.4 `CardPolicy`

```rust
struct CardPolicy {
    per_hour_cap:          Option<u128>,
    per_day_cap:           Option<u128>,
    per_month_cap:         Option<u128>,
    allowed_receivers:     Vec<Address>,    // ≤ 64, empty = any receiver
    allowed_syscall_kinds: Vec<SyscallKind>,// ≤ 16, empty = any syscall
    locked_after_transfer: bool,            // can the owner still SetPolicy after the card is handed over?
}

enum SyscallKind {
    Send, DeployActor, PublishLibrary, Token, CrossChain,
    Session, Cbss, Custom(u16),
}
```

Cap unit is `gas_payment_token` wei, not gas units.

### 2.5 `SpendWindow`

Fixed-window (not sliding) for day-1 simplicity:

```rust
struct SpendWindow {
    hour_period_id:   u64,  // = block_height / BLOCKS_PER_HOUR
    hour_spent:       u128,
    day_period_id:    u64,
    day_spent:        u128,
    month_period_id:  u64,
    month_spent:      u128,
}
```

On each charge: check the period_id; if it doesn't match what's stored → reset the accumulator and bump the period_id; otherwise accumulate and check against the cap.

Roadmap: true sliding windows (deque + upper bound) deferred to v2.

### 2.6 Card address derivation

```
DOMAIN = b"CowboyBankCard\x01"

card_address = keccak256(
        DOMAIN
     || bank_id_be4
     || owner_20
     || agent_20
     || issue_nonce_be8
)[12..32]
```

**Key design tradeoffs**:

- `agent` is in the derivation formula → a card is intrinsically bound to one agent; re-binding = must issue a new card (matches the "one card, one identity" mental model).
- `owner` is in the derivation formula but acts only as salt → `TransferOwnership` **does not change the address**, only `CardEntry.owner` (otherwise transferring ownership would invalidate every reference to the card — UX disaster).
- `issue_nonce` lets the same (bank, owner, agent) tuple yield arbitrarily many cards (expiry → re-issue → new nonce → new address).

### 2.7 Default card resolution

When the engine processes a tx, it resolves `fee_payer` in this order:

```
1. If tx carries an explicit fee_payer_override:
     a. If the address hits `b"card:" || addr` → take the BankActor.charge_gas path
     b. Otherwise → plain EOA charge (preserves the current owner-pays behavior)
2. Else if tx.from is an actor address and `b"agent_default_card:" || actor` exists:
     → use the default card via BankActor.charge_gas
3. Otherwise → debit tx.from's own balance (preserves the current actor-pays behavior)
```

Day-1 is backward-compatible with the existing owner-pays / actor-pays paths; cards are layered as a third path.

---

## 3. Instruction Set

`BankInstruction` enum, dispatched in the style of SessionActor.

### 3.1 Owner-submitted

| Instruction | Fields | Key validation | Side effects |
|---|---|---|---|
| `IssueCard` | `bank_id, agent, gas_payment_token, initial_policy, expires_at: Option<u64>` | bank Active; gas_payment_token ∈ {Native, whitelisted stable}; policy field bounds; caller = `tx.from` (becomes the owner) | bump `issue_nonce`; derive `card_address`; write `CardEntry` and owner/agent indices |
| `RenewCard` | `card_address, new_expires_at: Option<u64>` | caller == owner; status ∈ {Active, Expired}; new_expires_at > block_height (if Some) | status → Active; update expires_at / last_renewed_at |
| `CloseCard` | `card_address, refund_to: Address` | caller == owner; status ≠ Closed; not the default card | transfer all token balances out; status → Closed; remove indices; clear window |
| `Deposit` | `card_address, token, amount` | bank.status == Active; card Active or Frozen (frozen card can still receive deposits); token ∈ {CBY, valid CIP-20} | token moves from caller to `card_address` |
| `Withdraw` | `card_address, token, amount, to` | caller == owner; card status ≠ Frozen; balance sufficient | token moves from `card_address` to `to` |
| `SetPolicy` | `card_address, new_policy` | caller == owner; if `locked_after_transfer && owner == agent` → reject; policy field bounds | overwrite `CardEntry.policy` (window untouched) |
| `TransferOwnership` | `card_address, new_owner, set_locked: bool` | caller == owner; new_owner ≠ 0x00 | `owner = new_owner`; if `set_locked`, set `locked_after_transfer = true` |

### 3.2 Agent-or-Owner submitted

| Instruction | Fields | Validation | Side effects |
|---|---|---|---|
| `SetDefaultCard` | `agent, card_address: Option<Address>` | caller == agent **or** caller == card.owner; if Some(addr): card.agent == agent and status = Active | write/delete `b"agent_default_card:" \|\| agent` |

Two-key model, last-writer-wins. Lets the guardian set it on the agent's behalf early on; lets the agent switch it later once grown.

### 3.3 BankOperator submitted (the compliance handle)

| Instruction | Fields | Validation | Side effects |
|---|---|---|---|
| `Freeze` | `card_address, reason: Vec<u8>≤256` | caller == bank.operator | status → Frozen; emit event with reason |
| `Unfreeze` | `card_address` | caller == bank.operator | status → Active (or Expired if already past expires_at) |
| `PauseBank` | `bank_id, reason` | caller == bank.operator | bank.status → Paused; all charge / deposit / issue under this bank stop (withdraw still allowed) |
| `UnpauseBank` | `bank_id` | caller == bank.operator | bank.status → Active |
| `MintFromFiatVoucher` | `voucher: FiatMintVoucher, signature: [u8;65]` | signature from `bank.fiat_mint_signer`; voucher.bank_id matches; `voucher_id` not in `b"voucher_used:"`; `block_height ≤ expires_at_block`; bank.status == Active; card.status ≠ Closed | credit `card_address` with `+amount` in `voucher.token`; write `b"voucher_used:" \|\| voucher_id`; emit `FiatMinted` |

```rust
struct FiatMintVoucher {
    bank_id:           u32,
    card_address:      Address,
    token:             PayCurrency,
    amount:            u128,
    voucher_id:        [u8; 32],   // unique; replay-protection primary key
    expires_at_block:  u64,
    fiat_reference:    Vec<u8>,    // ≤ 64 bytes, e.g. Stripe charge_id
}
// signing domain: keccak256("CowboyBankFiatMint\x01" || rlp(voucher))
```

`MintFromFiatVoucher` is broadcast-by-anyone; the signature must come from `fiat_mint_signer`. That puts the "when does it land on chain" key in the user's hands.

### 3.4 Governance submitted (CIP-12 governance proposal)

| Instruction | Fields | Validation | Side effects |
|---|---|---|---|
| `RegisterBank` | `name, operator, fiat_mint_signer: Option<Address>` | caller authorized via CIP-12 governance proposal (Tier 1 registry write; Tier 3 if also upgrading BankActor bytecode); name 1..=32 ASCII; operator ≠ 0x00 | bump `b"bank_seq"`; write `b"bank:" \|\| id`; emit `BankRegistered` |
| `SetBankOperator` | `bank_id, new_operator` | caller == current operator, or authorized via CIP-12 governance | rotate operator |
| `SetBankFiatMintSigner` | `bank_id, new_signer: Option<Address>` | caller == operator | rotate / remove the fiat-mint signing key |

### 3.5 Engine internal call (not a tx instruction, not addressable)

| Internal function | Trigger | Behavior |
|---|---|---|
| `BankActor::charge_gas(card, receiver, syscall_kind, amount, height)` | Engine, during tx fee-settle, when fee_payer is determined to be a card address | Run the §4 pipeline; on failure, fall back to an OutOfFunds-equivalent reject |

### 3.6 Events

```
CardIssued        { card, bank, owner, agent, expires_at }
CardRenewed       { card, new_expires_at }
CardClosed        { card, refund_to }
CardDeposited     { card, token, amount, from }
CardWithdrawn     { card, token, amount, to }
CardPolicySet     { card, hash_of_policy }
CardOwnerTransferred { card, old_owner, new_owner, locked }
CardDefaultSet    { agent, card }
CardFrozen        { card, reason }
CardUnfrozen      { card }
BankRegistered    { bank_id, name, operator }
BankPaused        { bank_id, reason }
FiatMinted        { card, token, amount, voucher_id, fiat_reference }
GasCharged        { card, tx_digest, receiver, syscall_kind, reserve_amount, actual_amount }
```

---

## 4. Gas Charge Path

### 4.1 Engine fee-settle fork point

```
                    tx enters fee-settle
                            │
                ┌───────────┴────────────────┐
                │ Resolve fee_payer (§2.7)   │
                └───────────┬────────────────┘
                            │
                fee_payer ∈ b"card:" ?
              ┌─────────────┴─────────────┐
            no│                         yes│
              ▼                            ▼
   ┌─────────────────────┐    ┌──────────────────────────┐
   │ Existing EOA path   │    │ BankActor.charge_gas(...) │
   │ (owner-pays or      │    │   → §4.2 pipeline         │
   │  actor-pays, intact)│    └──────────────────────────┘
   └─────────────────────┘
```

Cost of "is this a card?": one `b"card:" || addr` lookup. Bloom-filter caching is on the roadmap.

### 4.2 BankActor.charge_gas pipeline

#### Phase 1 — Pre-flight Reserve (at block admission)

```
in: card_addr, tx,
    cycles_limit, cells_limit,                      // dual-metered gas limits from the tx
    cycle_basefee, cell_basefee,                    // dual-metered basefee at the current block (CIP-3 §2.4)
    receiver_addr, syscall_kind, block_height

1. card  = read CardEntry(card_addr)                // missing → BankErr::CardNotFound
2. bank  = read BankEntry(card.bank_id)
3. Static checks:
     bank.status == Active                          // else BankErr::BankPaused
     card.status == Active                          // Frozen/Closed/Expired → corresponding error
     card.expires_at.map(|e| block_height < e).unwrap_or(true)
4. Policy checks:
     a. if card.policy.allowed_receivers non-empty → receiver_addr ∈ list
     b. if card.policy.allowed_syscall_kinds non-empty → syscall_kind ∈ list
5. CIP-3 dual-metered reservation formula (unit: attoCBY):
     reserve_cby = cycles_limit × cycle_basefee +
                   cells_limit  × cell_basefee
     reserve_amount = match card.gas_payment_token {
         Native    => reserve_cby,                  // CBY card: store directly
         Token(U)  => convert_cby_to_u(reserve_cby, genesis_peg),  // U-stable card: convert via genesis-fixed peg (oracle on roadmap)
     }
6. Window roll-over:
     roll_window(card.window, block_height)
7. Cap checks (each tier; unit = card.gas_payment_token):
     hour_spent  + reserve_amount ≤ per_hour_cap   (if Some)
     day_spent   + reserve_amount ≤ per_day_cap
     month_spent + reserve_amount ≤ per_month_cap
     // any failure → BankErr::CapExceeded { tier }
8. Balance check:
     balance_of(card_addr, card.gas_payment_token) ≥ reserve_amount
9. Apply side effects:
     debit(card_addr, gas_payment_token, reserve_amount)
     window.hour_spent  += reserve_amount
     window.day_spent   += reserve_amount
     window.month_spent += reserve_amount
     persist CardEntry
10. Return ReservationToken {
        card_addr, reserve_amount, gas_payment_token,
        snapshot_cycle_basefee, snapshot_cell_basefee,   // freeze both basefees; reused at settle for refund consistency
        snapshot_period_ids,
    }
```

#### Phase 2 — Post-execution Settle (after handler returns)

```
in: ReservationToken, actual_cycles_used, actual_cells_used

1. CIP-3 dual-metered settlement (use the basefees snapshotted at reservation; unit attoCBY):
     actual_cby    = actual_cycles_used × snapshot_cycle_basefee +
                     actual_cells_used  × snapshot_cell_basefee
     actual_amount = match gas_payment_token {
         Native    => actual_cby,
         Token(U)  => convert_cby_to_u(actual_cby, genesis_peg),
     }
2. refund        = reserve_amount - actual_amount
3. if refund > 0:
     credit(card_addr, gas_payment_token, refund)
     // window refund credits back to the current period only; cross-period drift is not reclaimed
     window.hour_spent  = window.hour_spent.saturating_sub(refund) … same for the three tiers
     persist CardEntry
4. emit GasCharged { card, tx_digest, receiver, syscall_kind, reserve_amount, actual_amount }
```

> **Async discipline** (per the lesson from commit `90c3073`): BankActor handlers stay `async fn` + `.await` throughout (same as CBSS handlers in `execution/src/cbss.rs`). Storage IO triggered from a PVM handler call stack inside `charge_gas` (reads on `b"bank:"` / `b"card:"`) must return via the async path; when a `!Send` future must be driven, **reuse `execution::actor_instruction::block_on_local`, do not use `futures::executor::block_on`** — the latter panics under nested executors (`EnterError`).

### 4.3 Timer-deferred tx specifics

Today: timers pre-charge `max_cost` from `fee_payer_override` at scheduling time; at firing time the tx is "already paid". With cards involved:

| Moment | Caps accounting | Settlement |
|---|---|---|
| Block where the timer is scheduled | Add `max_cost` to the window of "schedule time" | `debit card` for `max_cost` upfront |
| Block where the timer fires | Don't account again | Refund the excess per §4.2 Phase 2 |

**Implication**: limits are anchored to the **scheduling moment**, not the firing moment. The guardian can see "the kid is queueing up tasks again" at the start of the month — no surprise at month-end.

### 4.4 Edge cases

| Scenario | Handling |
|---|---|
| Card frozen after reserve but before settle | The current tx still settles (already pre-charged); the next reserve is rejected |
| Card expires after reserve but before settle (block crosses expiry) | The current tx still settles; the next reserve fails with `CardExpired` |
| Reserve and settle straddle a period boundary | Refund credits only the "current" period accumulator at settle time; the prior period's inflated count is not reclaimed (conservative, acceptable) |
| Card is `Withdraw`'d externally after reserve | Cannot happen; Withdraw checks balance, and the reserve has already debited |
| Multiple charges on the same card in the same block | Sequential accumulation; the last reserve sees the cumulative state after prior reserves — semantics are clear |
| `gas_payment_token = U` with different precision than CBY | Genesis writes the protocol-fixed peg (day-1: 1:1 or a constant); oracle integration deferred to roadmap |
| `SetPolicy` tightens after reserve | Settle uses the policy snapshot at reserve time; the next reserve uses the new policy |
| FiatMintVoucher arrives after reserve | Doesn't affect the current tx; the next reserve sees the new balance |

### 4.5 Error codes

New `BankErr::*` family; the engine's top-level ErrorMap maps them uniformly:

```
BankErr::CardNotFound          → reject: BankCardNotFound
BankErr::BankPaused            → reject: BankPaused
BankErr::CardFrozen            → reject: BankCardFrozen
BankErr::CardExpired           → reject: BankCardExpired
BankErr::CardClosed            → reject: BankCardClosed
BankErr::ReceiverNotInWhitelist→ reject: BankPolicyDenied
BankErr::SyscallNotAllowed     → reject: BankPolicyDenied
BankErr::CapExceeded{tier}     → reject: BankCapExceeded
BankErr::InsufficientCardBalance → reject: OutOfFunds (reuses the current code)
```

### 4.6 Receipts & Indexer

`GasCharged` events carry `tx_digest`, so the Indexer can join: each tx → 1 `GasCharged` event (if fee_payer is a card). The UI's "card statement" view = all events on that card, sorted by time.

---

## 5. Policy Triad: Semantics in Detail

### 5.1 Limits (per-hour / per-day / per-month)

#### Unit & meaning

- **Unit = wei of `card.gas_payment_token`** (not gas units)
- The three tiers are **independent**; any failing tier rejects the charge. Monotonicity is not enforced.
- `None` = no cap on that tier

#### Window constants (compile-time constants in BankActor, governance-tunable)

| Constant | Day-1 value | Note |
|---|---|---|
| `BLOCKS_PER_HOUR` | `3_600 / target_block_secs` | rounded |
| `BLOCKS_PER_DAY` | `86_400 / target_block_secs` | rounded |
| `BLOCKS_PER_MONTH` | `BLOCKS_PER_DAY * 30` | calibrated as 30 days, not calendar months |

Block-based instead of wall-clock for determinism.

#### Period-id

```rust
fn period_id(block_height: u64, blocks_per_tier: u64) -> u64 {
    block_height / blocks_per_tier
}
```

At reserve time, if the stored period_id mismatches: clear the accumulator, bump period_id, then check the cap. Refunds credit the current period; cross-period drift is not reclaimed.

#### Cap-rejection error precision

`BankErr::CapExceeded { tier: Hour | Day | Month, would_be: u128, cap: u128 }` — the UI can directly render "Monthly cap is 100 U; this tx would push the total to 103 U".

### 5.2 Whitelist

Two independent whitelists; **both must pass**.

#### `allowed_receivers: Vec<Address>`

| State | Behavior |
|---|---|
| `Vec::new()` (empty) | any receiver allowed |
| non-empty | the "primary receiver" of the tx must ∈ set; else `BankErr::ReceiverNotInWhitelist` |

Primary receiver = tx's `to` field; for multi-instruction txs, the target of the first instruction. System actors match by address as well.

Capacity cap: ≤ 64. Larger sets → encourage splitting into multiple cards.

#### `allowed_syscall_kinds: Vec<SyscallKind>`

A fixed instruction → SyscallKind mapping (BankActor compile-time constant):

| Instruction | SyscallKind |
|---|---|
| `SystemInstruction::Send` / `Transfer` / `CallActor` | `Send` |
| `SystemInstruction::Token*` | `Token` |
| `ActorInstruction::DeployActor` | `DeployActor` |
| `LibraryInstruction::PublishLibrary` / `RemoveLibrary` | `PublishLibrary` |
| `SessionInstruction::*` | `Session` |
| `CbssInstruction::*` | `Cbss` |
| Cross-chain settlement | `CrossChain` |
| Other | `Custom(opcode_u16)` |

Capacity cap: ≤ 16.

#### Multi-instruction txs

For each instruction the (receiver, syscall_kind) pair must pass; any failure rejects the entire tx.

#### Blacklist not in day-1

The whitelist + freeze combination already covers the compliance story; an explicit deny-list is semantically redundant.

### 5.3 Freeze authority & state machine

#### Who can freeze

- **Only `bank.operator`** (Cowboy Banking = Cowboy Banking operator multisig; third-party = their own multisig)
- The owner cannot freeze (use `SetPolicy { caps = Some(0) }` or `CloseCard` instead)
- The agent cannot freeze

#### State transition matrix

| Current status | Allowed | Disallowed |
|---|---|---|
| `Active` | anything | — |
| `Frozen` | Deposit / SetPolicy / Renew / TransferOwnership / unset-default / Unfreeze (operator) | charge_gas / Withdraw / set-as-default |
| `Expired` | Deposit / Renew (owner) / **Withdraw** (owner, get balance back) | charge_gas / set-as-default |
| `Closed` | **Withdraw** (owner, residual rescue) — receives leftovers from timer-deferred refunds | charge_gas / Deposit / SetPolicy / Renew / TransferOwnership / any other write |

`Frozen` permits Deposit — matches a real bank's behavior when investigating a suspicious transaction.

#### Reason field

`Freeze.reason: Vec<u8>` capped at 256 bytes, recorded on chain + included in the event.

#### Unfreeze

Operator only; if `block_height ≥ expires_at` at unfreeze, the card lands in `Expired` (owner must Renew).

### 5.4 `locked_after_transfer` precise semantics

```
if CardEntry.policy.locked_after_transfer == true
   && CardEntry.owner == CardEntry.agent      // already handed over to the agent itself
then:
   SetPolicy always rejected (BankErr::PolicyLocked)
   TransferOwnership still allowed
   RenewCard still allowed
```

Meaning: before handing over, the guardian can tick "I don't want the kid to relax the limits". Once ticked + transfer is complete, the agent cannot SetPolicy either — only issuing a new card works.

### 5.5 Roadmap notes

| Item | Day-1 | Future |
|---|---|---|
| True sliding window | Fixed-period | deque + upper bound |
| Blacklist | Not done | explicit deny list |
| Per-token tiered caps | Single token dimension | per-token caps |
| Whitelist capacity | 64 / 16 hard caps | off-chain signed whitelist extension |
| Calendar months | 30-day block count | indexer-layer presentation |

---

## 6. Multi-Bank + Stripe Fiat Bridge

### 6.1 Multi-bank: registration & isolation

#### Cowboy Banking at genesis

```
b"bank:" || 0x00000001 = BankEntry {
    bank_id:          1,
    name:             b"Cowboy Banking",
    operator:         <Cowboy Banking operator multisig address>,
    fiat_mint_signer: Some(<Cowboy Banking Gateway Signer>),
    status:           Active,
    registered_at:    0,
}
b"bank_seq" = 2
```

#### Third-party bank registration

Via `RegisterBank`. Caller must be authorized via CIP-12 governance. Self-service registration by arbitrary third parties is **not allowed** — hanging the "Cowboy on-chain bank charter" requires governance approval.

#### Inter-bank state isolation

A third-party bank is fully isolated after registration:
- Same `BankInstruction` set, distinguished by `bank_id`
- Third-party operator can only freeze / pause cards under its own bank
- Trouble at one third-party bank does not affect Cowboy Banking
- Cross-bank fund movement = ordinary token transfer + Deposit/Withdraw sequence — no dedicated instruction

| Isolation dimension | Implementation |
|---|---|
| Funds | Each card is an independent address; banks do not hold pooled funds |
| Authority | One-to-one operator multisig |
| Compliance pause | `PauseBank` affects only that bank's cards |
| Fiat bridge | Each bank has its own `fiat_mint_signer`; they don't recognize each other |

#### Cross-bank card migration: not supported

The card address has `bank_id` in its derivation formula; changing banks would change the address. Treated as "close then reopen": `CloseCard` → `IssueCard`.

### 6.2 Fiat bridge

#### On-chain / off-chain responsibility split

```
┌───────────────────────────────────────────────────────────────┐
│  Off-chain (Gateway)                                          │
│  · KYC (PII held in compliance DB, not on chain)              │
│  · Stripe collection + chargeback monitoring                  │
│  · On payment success → sign FiatMintVoucher                  │
│  · Deliver voucher to the user's wallet                       │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│  User Wallet                                                  │
│  Broadcast tx: MintFromFiatVoucher { voucher, signature }     │
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌───────────────────────────────────────────────────────────────┐
│  BankActor (on-chain)                                         │
│  · Verify signature against bank.fiat_mint_signer             │
│  · Check voucher_id not yet used                              │
│  · Check expires_at_block                                     │
│  · Check bank.status / card.status                            │
│  · credit(card_addr, voucher.token, voucher.amount)           │
│  · Write b"voucher_used:" || voucher_id                       │
│  · emit FiatMinted                                            │
└───────────────────────────────────────────────────────────────┘
```

#### Trust assumptions

| Assumption | Impact |
|---|---|
| Gateway signer key not leaked | Leaked = money printer; rotation via `SetBankFiatMintSigner`; governance-driven emergency table flush is roadmap |
| Gateway will not sign forged vouchers | Triangulated by KYC + Stripe receipts + gateway internal audit |
| Stripe chargeback vs. on-chain mint timing | Gateway must delay signing until the Stripe risk window has elapsed |
| User does not lose the voucher | Gateway can re-sign the same voucher_id given the original receipt; chain accepts only the first |

#### Voucher anti-forgery

- Signing domain `keccak256("CowboyBankFiatMint\x01" || rlp(voucher))`, includes bank_id
- `voucher_id` 32 bytes; recommended `hash(stripe_charge_id || chain_id || bank_id)`
- `expires_at_block` recommended ~24 hours of block-equivalent
- `fiat_reference` stores the Stripe charge_id (or its hash) on chain for audit reconciliation

#### Off-ramp roadmap

Day-1 designs the on-ramp only. Off-ramp (on-chain balance → fiat) is heavier on compliance — placeholder instruction name `BurnToFiatRequest`, deferred to v2.

### 6.3 Stripe integration (off-chain interface, design only)

```
POST /v1/cards/{card_addr}/topup/intent
  body: { amount_usd, return_url }
  resp: { stripe_checkout_url, intent_id }

GET /v1/topup/intents/{intent_id}
  resp: { status: pending|paid|refunded|expired,
          voucher?: FiatMintVoucher,
          signature?: hex }

POST /v1/topup/intents/{intent_id}/redeliver
```

Zero invasion on the on-chain side: BankActor only recognizes the `fiat_mint_signer` signature.

### 6.4 Compliance perimeter

```
┌─────────────────────────────────────────────────────────┐
│  Compliance domain (KYC / AML / fiat tax)               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  Lives only inside BankActor + each bank's gateway      │
│                                                         │
│  · Deposit KYC: gateway                                 │
│  · Limit-based risk: BankActor.charge_gas               │
│  · Freeze: BankActor.Freeze (operator multisig)         │
│  · Fiat audit trail: FiatMinted + GasCharged events     │
└─────────────────────────────────────────────────────────┘
                          ▲
                Compliance handle attaches here
                          │
┌─────────────────────────────────────────────────────────┐
│  Rest of the Cowboy ecosystem                           │
│  (actor / token / session / cbss)                       │
│  Inherits BankActor's compliance conclusion: no need to │
│  KYC anywhere else                                      │
└─────────────────────────────────────────────────────────┘
```

In one sentence: **everything else on Cowboy doesn't need to be compliant — only the banking layer does, because banking is the sole entry/exit for money in and out of the ecosystem.**

---

## 7. Roadmap & Compatibility

### 7.1 Relation to the three existing charge paths

```
                          tx enters fee-settle
                                 │
                ┌────────────────┼─────────────────────┐
                ▼                ▼                     ▼
  ┌──────────────────┐ ┌────────────────────┐ ┌──────────────────────┐
  │ actor-pays       │ │ owner-pays         │ │ card-pays  (new)     │
  │ (default)        │ │ (fee_payer_override│ │ (fee_payer_override  │
  │                  │ │  points at EOA)    │ │  points at card addr)│
  │ tx.from is debited│ │ EOA is debited     │ │ BankActor.charge_gas │
  └──────────────────┘ └────────────────────┘ └──────────────────────┘
            ↑                    ↑                       ↑
            │                    │                       │
        preserved   preserved (existing timer / owner)   added
```

All three coexist. New functionality is opt-in; no forced migration.

### 7.2 Rollout milestones

| Stage | Contents | Demo highlight |
|---|---|---|
| **M1 BankActor skeleton** | 0x0D placement; genesis-write Cowboy Banking; `IssueCard` / `Deposit` / `Withdraw` / `CloseCard`; card address derivation; `card_by_owner/agent` indices | "Every agent has its own on-chain bank card" |
| **M2 Charge fork point** | Engine fee-settle adds the §4.1 fork; `charge_gas` Phase 1+2; `SetDefaultCard`; timer-deferred integration | "Pay gas with a card — balance is visible and auditable" |
| **M3 Policy triad** | `SetPolicy`; `SpendWindow`; whitelist match; `Freeze`/`Unfreeze`; `PauseBank`; `locked_after_transfer` | "Limits, whitelist, freeze — all in place" |
| **M4 Fiat bridge** | `MintFromFiatVoucher`; voucher replay protection; `SetBankFiatMintSigner`; off-chain gateway + Stripe | "Top up gas with a credit card" |
| **M5 Multi-bank + ownership transfer** | `RegisterBank`; `SetBankOperator`; third-party bank isolation; `TransferOwnership` | "Cowboy is the on-chain bank charter system" |

M1+M2 is the minimal demoable combination.

### 7.3 Feature gate

New governance parameter `bank_activation_height: u64`:

- Below this height: BankActor does not exist; `fee_payer_override` pointing at a card address → treated as a missing EOA → OutOfFunds
- Above this height: BankActor is active; the §4.1 fork goes live; the genesis Cowboy Banking entry is materialized

Testnet → mainnet can configure the height independently; rolling back is just setting the height into the future.

### 7.4 State migration impact

- Existing state untouched: actor / token / session / cbss / entitlement / storage are zero-invasion
- Only additions, no edits: `b"bank:" / b"card:" / b"card_by_*:" / …` are all new namespaces, no collision with existing system actors
- The existing `ScheduledTimer.fee_payer_override` (timer subsystem) is left alone; this CIP introduces a separate `tx.fee_payer_override: Option<Address>` at the tx top level — same name, different location, no interference

### 7.5 Cross-references with existing CIPs

| CIP | Touch point | Treatment |
|---|---|---|
| CIP-3 (dual-metered fee) | charge_gas strictly follows the CIP-3 §2.4 dual-metered formula `cycles × cycle_basefee + cells × cell_basefee` | ReservationToken must snapshot both basefees so that settle/refund stays consistent |
| CIP-20 (token) | A card holds CIP-20 balances | A card address is a valid token holder |
| CIP-24 (CBSS) | State layout style | Borrowed; no dependency |
| CIP-12 (governance) | `RegisterBank` is a Tier 1 registry write; BankActor bytecode upgrades are Tier 3 system-actor upgrades | Cowboy Banking BankOperator's signer set is decided by CIP-12 governance (not Foundation/Security Council; a separately specified multisig instance) |
| Session (0x0C) | A card is a long-lived account; a session is a one-shot escrow | A session_id can be added to `allowed_receivers` to let a card pay session settlements only |

### 7.6 Roadmap

| Item | Source | Priority |
|---|---|---|
| True sliding window | §2.5 / §5.1 | P1 |
| Per-token tiered caps | §5.5 | P1 |
| Off-ramp `BurnToFiatRequest` | §6.2.3 | P1 |
| Stripe gateway implementation + KYC backend | §6.3 | P0 (mandatory for M4 launch) |
| BankOperator emergency table flush (signer leak) | §6.2.1 | P2 |
| Explicit deny list | §5.2.4 | P3 |
| Cross-bank card migration | §6.1.4 | P3 |
| Per-token oracle conversion for paying gas | §2.3 | P2 |
| Bloom-filter cache for the active card set | §4.1 | P3 |

### 7.7 Day-1 hard-noes

- ❌ On-chain KYC (PII stays off chain)
- ❌ Cards with multiple holder agents (breaks the "one card, one identity" narrative)
- ❌ Protocol-level paymaster abstraction (separate storyline)
- ❌ Card-to-card transfer primitives (plain token transfers suffice)
- ❌ Reusing SessionActor for banking (already ruled out at proposal selection)

### 7.8 Risks & open questions

1. **Cap units vs basefee volatility**: the user sets caps in token units (CBY or U), but `cycle_basefee` / `cell_basefee` each move independently under CIP-3 dual-metered EIP-1559. The UI needs to show "how many tx you can run at the current dual-metered basefee".
2. **Cowboy Banking operator governance**: the Cowboy Banking operator multisig is held by Cowboy Labs in the early phase → "is this a centralized bank?" will come up in investor diligence; the narrative should land on "decentralization roadmap — see CIP-12 governance" (note: this is **not** the same as Cowboy Foundation from CIP-12 §3.1 — Foundation has zero protocol authority).
3. **The minimum set for third-party banks at M5**: a complete story needs at least one third-party bank actually live by M5; the recommendation is to line up a partner in parallel.
4. **Stripe chargeback vs. on-chain voucher timing**: gateway-internal parameter (48h / 72h?), not specified by this CIP, but should appear on the review checklist.

---

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| BankActor | The system actor at 0x0D that carries every on-chain responsibility defined in this CIP |
| Bank | A registry entry inside BankActor — e.g. Cowboy Banking, or a third-party bank |
| Card | One card; on chain represented as a CardEntry + derived address; analogous to a physical bank card |
| Card Address | The 20-byte address derived from (bank_id, owner, agent, issue_nonce) via keccak256 |
| Card Owner | The card's rule-controller — initially the user (guardian); potentially the agent itself later |
| Card Holder Agent | The actor the card serves — i.e. "the agent that pays gas using this card" |
| BankOperator | A bank's operating multisig; can freeze / pause / sign fiat vouchers |
| Vault model | Card balances are held under the card's own address (not the owner's wallet) — like a prepaid debit card |
| FiatMintVoucher | The fiat-deposit receipt signed by the gateway; the user broadcasts it on chain to mint card balance |

## Appendix B — Mapping to meeting points

| Meeting quote (paraphrased) | CIP section |
|---|---|
| "Build an actor bank / open an account for each agent" | §1, §2, §3 |
| "Can accept CBY, U, and many tokens" | §2.3 (gas_payment_token) + §3.1 (Deposit any token) |
| "Hook up Stripe so fiat can pay gas" | §6.2 fiat bridge |
| "Max spend per month, hourly cap" | §5.1 three-tier limits |
| "Whitelist: card has money but can only be spent at McDonald's / KFC" | §5.2 allowed_receivers / allowed_syscall_kinds |
| "Cards can expire / renew" | §3.1 RenewCard, §5.3 state machine |
| "Blacklist the card, not the whole person" | §3.3 Freeze, §5.3 state machine |
| "One card, one owner / agent" | §2.6 derivation (agent as salt) + §3.1 validation |
| "Early: owner = guardian; later: agent itself" | §3.1 TransferOwnership + §5.4 locked_after_transfer |
| "Cowboy Banking plus possibly other banks (CCB-like)" | §6.1 multi-bank |
| "Need a default card to pay from" | §2.7 + §3.2 SetDefaultCard |
| "Cowboy as a whole need not be compliant — banking suffices" | §6.4 compliance perimeter |

---

*End of document. Ready to enter the implementation-plan phase (CIP-28 landing in M1–M5 stages).*
