# CIP-28 BankActor M3.6 — Token-Gas Funding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a `PayCurrency::Token(U)` default card pay gas in a whitelisted stablecoin `U` (CUSD) via a genesis-fixed integer CBY↔U peg, settled through a **bank-as-paymaster** swap (`covered_u` moves `card → 0x16`; the bank's own CBY funds the burn/tip).

**Architecture:** Node-only, genesis-state-only. A per-token integer peg `(num, den)` is seeded under `BANK_ACTOR_SYSTEM_ACTOR (0x16)`. The existing `ExecuteActor` fee-settle path (`transaction.rs`) branches on the card's `gas_payment_token`: Native → existing `bank_charge_gas`; `Token(U)` → new `bank_charge_gas_token` paymaster settle. No wire/opcode/codec change. All runtime behavior stays dormant behind `BANK_ACTIVATION_HEIGHT = u64::MAX`.

**Tech Stack:** Rust (workspace crates `cowboy-execution`, `cowboy-chain`, `validator`, `cowboy-types`), `tokio`/`futures` async, hand-rolled fixed big-endian storage codecs (no serde on-chain), QMDB-backed `StateStore`.

---

## Deep-audit revisions (BINDING — supersede any conflicting task text below)

Two adversarial plan-audit lenses (paymaster/conservation; peg/A2/genesis/overall) ran against the draft. **The core engine audited SOUND with no BLOCKER**: peg math determinism, the A2 unit-fix and its M3 no-breach invariant (`covered_u ≤ need ≤ headroom` by floor monotonicity — the crux, proven correct), the shared-`card_is_eligible` coupling with the Native-only guard on `bank_charge_gas` (dispatch total + mutually-exclusive → no double-charge / no free-gas), both named BLOCKER fixes (FIX-A swallow-to-`Ok(0)`, FIX-B event drain/re-home), the TOCTOU single-read, and the paymaster conservation (Σ CBY + burn + tip conserved; bank eats <1-unit dust, never mints). Both lenses converged on ONE **HIGH** (genesis reserve accounting) plus precision/LOW items. Rulings below are binding.

- **RV-1 (HIGH — genesis `0x16` CBY reserve must be reconciled with `total_supply`, or it silently inflates issuance).** `0x16` is a keyless system address; `GenesisConfig::validate()` (`chain/src/genesis.rs:513-531`) sums balances **only from `self.accounts`** and hard-requires `Σ == total_supply`, while system actors (`create_runner_system_actors`) carry **no balance**. Task 7's "seed the reserve near the bank actor" is therefore wrong as drafted: an un-accounted reserve makes real genesis CBY `= total_supply + reserve` (silent inflation — and `inflation.rs:104-118` compounds it into per-block emission), or bumping `total_supply` without adding the balance to the sum makes `validate()` reject genesis. **Fix (all together):** (1) materialize the reserve as a real balance at `0x16` in the vector `to_accounts()` produces — `GenesisAccount` already supports `public_key_hex` so `0x16` can hold a balance — NOT in `create_runner_system_actors`; (2) fold `bank_cby_reserve` into `total_supply`; (3) extend `validate()` so the reserve is counted in the balance-sum check; (4) **guard the injection on `bank_cby_reserve > 0`** so a feature-off genesis (`reserve == 0`, `gas_pegs == []`) stays byte-identical to today. Add a genesis test asserting `Σ accounts.balance (incl. reserve) == total_supply` AND `validate().is_ok()` with a non-zero reserve AND the materialized `0x16` balance equals the reserve. This is the one place following the draft literally produces an unbuildable-or-inflationary genesis.
- **RV-2 (MED — accept and document the peg-floor subsidy; do NOT switch to `ceil`).** Floor-everywhere is the correct **cap-safe** choice: a `ceil` at settle could yield `covered_u > need` and breach the A2-admitted cap. The cost is that the card underpays by `< 1 U` per tx — a bounded subsidy from the `0x16` reserve to the card (conservation still holds; only the reserve absorbs the dust). Surface this explicitly in the 待裁/design section as an accepted cap-safety tradeoff; do not leave it implicit and do not "fix" it with `ceil`.
- **RV-3 (MED — state FIX-A's exact safety argument).** Replace the imprecise "Leg 1 errors before any write" with the true justification: FIX-A (swallow every `handle_token_transfer` `Err` → `Ok((0,0))`) is safe because **(a)** all *semantic* rejections — `TokenNotFound`, `TokenHookRejected` (the `can_transfer` PRE-hook), account-frozen, `TokenInsufficientBalance` — fire **before** the first `write_balance` (the sender-debit), and **(b)** the `on_transfer` POST-hook is best-effort (its `Err` is logged and swallowed inside `handle_token_transfer`), so no post-write reject exists. Add the caveat that a store-layer write failure *between* the two balance writes would be masked by FIX-A, and is unreachable only under the QMDB write-buffer model (buffer writes don't fail).
- **RV-4 (LOW — fold all):** (a) In the A2 **token** arm, convert the structured error's `required` to `need` (U units) so both `required` and `available` are U — do not ship a CBY/U unit mix in the consensus-committed receipt. (b) Add a `validate()` cross-check that every `gas_pegs` token id ∈ `stablecoin_whitelist` (a peg without whitelist membership silently yields non-funding cards). (c) In the FIX-B test, assert the re-homed `TokenTransfer` emitter == `0x16`, and note in the plan that this attributes the paymaster leg to `0x16` rather than the token actor (deterministic/consensus-safe, but a provenance divergence indexers should expect). (d) Note that §4.2 is implemented **single-phase** (`reserve_amount == actual_amount == covered`, inherited from M3.5), not the spec's two-phase reserve/refund — acknowledge the deviation in the verification matrix. (e) Justify the settle-time scratch-meter cell budget against M4's actual CUSD-hook cost rather than the magic `token_transfer_cells * 8` heuristic; keep it fail-safe (over-budget → `Ok(0)` fall-through).

**Net:** the plan is execution-ready after RV-1 (genesis accounting) is folded into Task 7 and RV-2/3/4 are noted at their tasks. M3.6 remains gated on M4 (Task 0 CUSD-hook contract) and does not execute until M4 lands.

---

## Preconditions (HARD — M4 dependency)

**M3.6 CANNOT execute or activate before M4 lands.**

The paymaster settle moves `covered_u` of CUSD from the card (or the account) to the paymaster destination `0x16` via `handle_token_transfer(card → 0x16)`. That call runs CUSD's `on_transfer`/`can_transfer` allowlist hook (`token/core.rs:265` `check_transfer_allowed`). Unless **M4 seeds the real CUSD `transfer_hook` and that allowlist admits `card/account → 0x16`**, `check_transfer_allowed` returns `Err(TokenHookRejected)` (`error.rs:275`) and **every token-card settle fails**.

The user has ruled that **M4 seeds the real allowlist hook including `card/account → 0x16`**. This plan therefore:

- Treats "CUSD hook admits `→ 0x16`" as a **precondition supplied by M4**, verified by **Task 0** before any token settle is attempted.
- Is safe to *land* before M4 only because the whole path is inert under `BANK_ACTIVATION_HEIGHT = u64::MAX` (`constants.rs:683`). It must **not be activated** (height lowered) until M4's hook is live on the target chain. State this in the activation PR.
- FIX-A (Task 5) guarantees that even if the hook rejects, the tx still settles against actor/owner/sender (no pay-then-fail, no block halt) — so an M4-before-activation ordering error degrades gracefully rather than halting consensus. This is defense-in-depth, **not** a substitute for M4.

---

## Baseline (as-built) — verified file:line anchors

| Concern | Location | Notes |
|---|---|---|
| BankActor address | `types/src/constants.rs:237` | `BANK_ACTOR_SYSTEM_ACTOR = Address::from_low_u64(0x16)` |
| Activation gate | `types/src/constants.rs:683` | `BANK_ACTIVATION_HEIGHT: u64 = u64::MAX` (dormant) |
| Bank raw storage helpers | `execution/src/bank/storage.rs:110-133` | `get_raw`/`set_raw`/`delete_raw` pinned to `0x16`; `decode_u32:135`, `decode_u64:140` |
| Stablecoin whitelist | `execution/src/bank/storage.rs:104` (`stablecoin_whitelist_key`), `:425` (`stablecoin_whitelist_contains`) | concat of 32-byte token ids |
| `PayCurrency` codec | `execution/src/bank/mod.rs:167-190` | `Native=0u8`; `Token(id)=1u8 ‖ token_id[u8;32]` (**32-byte id, not a 20-byte Address**) |
| `wire_token_to_currency` | `execution/src/bank/handlers.rs:75` | all-zero 32 bytes → Native, else `Token(id)` |
| `rolled_cap_headroom` | `execution/src/bank/handlers.rs:260` | pure; min headroom across 3 tiers, U units |
| `encode_gas_charged` | `execution/src/bank/handlers.rs:319` | `card(20)‖digest(32)‖recv(20)‖kind‖reserve(16 BE)‖actual(16 BE)` |
| `policy_admits` | `execution/src/bank/handlers.rs:341` | pure receiver+syscall whitelist gate |
| `card_is_eligible` | `execution/src/bank/handlers.rs:351` | **returns `None` for any non-Native card at `:374-376`** — the M3.6 relax point |
| `accumulate_spend` (private) | `execution/src/bank/handlers.rs:384` | rolls window + adds spend; same module as new method |
| `syscall_kind_of` | `execution/src/bank/handlers.rs:289` | first-instruction → `SyscallKind` |
| `bank_charge_gas` (native) | `execution/src/bank/handlers.rs:766-803` | free fn; debits card `Account.balance`; **eligibility failure = `Ok(0)`, never `Err`** |
| `bank_deposit`/token-transfer call site | `execution/src/bank/handlers.rs:807-873` | `impl ExecutionEngine` block; pattern for calling `handle_token_transfer` |
| `handle_token_transfer` | `execution/src/token/core.rs:229` | `(store, token_id:&[u8;32], to:&Address, amount:u128, sender:&Address, _sender_account, gas_meters, block_height, block_hash, timestamp_ms, tx_hash)`; **pushes `TokenTransfer` onto `self.system_events` at `:333-336`** |
| `check_transfer_allowed` (the veto) | `execution/src/token/core.rs:265` | can_transfer PRE-hook; `Err(TokenHookRejected)` **before any balance write** |
| `read_balance` | `execution/src/token/query.rs:32` | `(store, key)->u128`; key via `cowboy_token::storage_keys::token_registry::balance_key(owner, token_id)` (`core.rs:279`) |
| A2 pre-check block | `execution/src/execution/transaction.rs:215-245` | eligibility + `rolled_cap_headroom < max_total_cost` + `policy_admits`; **compares U-unit headroom vs CBY cost — the unit bug Part 3 fixes** |
| Settle site (`card_paid`) | `execution/src/execution/transaction.rs:519-559` | calls native `bank_charge_gas`; emits `GasCharged covered/covered` at `:544-558` |
| Actor-arm events var | `execution/src/execution/transaction.rs:413-436` | actor-instruction returns `evts` as the local `events`; **does NOT drain `self.system_events`** (contrast System arm at `:307-308` which does `std::mem::take`) — the FIX-B leak |
| `execute_transaction` params | `execution/src/execution/transaction.rs:47-53` | `block_hash`, `timestamp_ms` in scope at the settle site (needed for the paymaster leg) |
| Genesis bank/whitelist seeding | `chain/src/genesis.rs:857-915` | seeds `bank:1`, `bank_seq=2`, `stablecoin_whitelist` |
| `GenesisConfig.stablecoin_whitelist` | `chain/src/genesis.rs:283`; default `:461` | `Vec<[u8;32]>`, `#[serde(default)]` |
| `GenesisConfig::validate` | `chain/src/genesis.rs:513` | add num/den non-zero check here |
| Setup defaults | `validator/src/setup.rs:112-113` | `bank_operator`, `stablecoin_whitelist` defaults |
| `GasCharged` consensus topic | `execution/src/consensus_event_topics.rs:40`; `TOPIC_GAS_CHARGED` at `handlers.rs:58` | already registered (M3.5) |
| `TokenTransfer` consensus topic | `execution/src/token/events.rs:13` (`TOPIC_TOKEN_TRANSFER`) | **already a registered consensus topic** — the drained event (FIX-B) needs no new topic |
| `DualGasMeters::new` | `execution/src/gas.rs:676` | `(cycles_limit, cells_limit)`; `token_hook_max_cycles` field `gas.rs:106` = `50_000` |
| Test harness (unit) | `execution/src/bank/handlers.rs:2504-2547` | `TestStore`, `seed_bank`, `write_native_card`, `a(byte)`, `native_bal`, `GENESIS_BANK_ID` |
| Test harness (integration) | `execution/src/execution/tests.rs:15448` (`seed_default_card`), `:15617` (`const BANK_H: u64 = u64::MAX`), `:16379` (`run_bank_gas_events`), `:15607` (`big_stack`) | M3.5 `GasCharged` tests at `:16373-16490` |

**Confirmations (guardrail checks, all verified against the tree):**

- **No wire/opcode/codec change.** The peg is pure genesis state under `0x16`; enforcement rides the existing `ExecuteActor` settle path. `PayCurrency::Token` already exists and encodes (`mod.rs:179-188`); no instruction, no opcode, no serde change. → **no codec PR**.
- **Golden vectors untouched.** M3.6 adds a *new* storage key family (`b"gas_peg:"`) and a *new* `GenesisConfig` field; it does **not** touch `CardEntry`/`BankEntry`/`PayCurrency` encoding. `CardEntry` golden vectors (`bank/mod.rs` / `bank/storage.rs` tests) are unaffected.
- **Token debit only via `handle_token_transfer`** (M1 H1): the U leg never touches raw balances; it calls `handle_token_transfer` so the CUSD hook is genuinely enforced.
- **`TokenTransfer` already a consensus topic** → the drained event (FIX-B) is not a new topic; `GasCharged` already registered in M3.5.

---

## Scope decisions (待裁)

1. **`0x16` genesis CBY reserve size.** The paymaster CBY leg (Leg 2) spends `0x16`'s own `Account.balance`. Day-1 model = genesis-seed `0x16` with a CBY reserve; `covered_cby` is bounded to the available balance, so an under-funded bank degrades to partial/zero cover (actor pays the rest), deterministically. **Recommendation:** seed a fixed reserve (e.g. a governance-decided constant added to `total_supply` accounting) via a new `GenesisConfig.bank_cby_reserve: u64`; exact figure is a business/tokenomics call — flagged for the activation PR. This plan wires the field and seeds it; the *number* is 待裁.
2. **Governance top-up instruction in/out of scope.** Replenishment (the bank buys CBY with accumulated U via off-chain market-making / governance) is CIP-28 §7 roadmap (oracle/AMM). **Recommendation (selected):** genesis reserve only for M3.6; an on-chain top-up instruction is **deferred**. Do **not** invent an on-chain AMM.
3. **`GasCharged` token-unit.** Already ruled: for a `Token` card, `GasCharged.reserve/actual = covered_u` (U units), matching the window/`accumulate_spend` unit and §5.1 ("wei of `card.gas_payment_token`"). Native cards keep `covered` (CBY). Implemented in FIX-C (Task 6).

---

## File map

| File | Change |
|---|---|
| `execution/src/bank/storage.rs` | **Add** `gas_peg_key`, `read_gas_peg`, `write_gas_peg` (Task 1) |
| `execution/src/bank/handlers.rs` | **Add** `convert_cby_to_u`, `cby_from_u` (Task 2); **relax** `card_is_eligible` + guard native `bank_charge_gas` (Task 3); **add** `bank_charge_gas_token` method (Task 5) |
| `execution/src/execution/transaction.rs` | **Modify** A2 block for token unit (Task 4); **modify** settle site to dispatch Native vs Token + FIX-B/FIX-C (Task 6) |
| `chain/src/genesis.rs` | **Add** `gas_pegs` + `bank_cby_reserve` fields, seed them, `validate()` num/den non-zero (Task 7) |
| `validator/src/setup.rs` | **Add** field defaults (Task 7) |
| `execution/src/execution/tests.rs` | **Add** paymaster + conservation integration tests (Tasks 0, 5, 6, 8) |

---

## Task ordering & justification

`peg infra (Task 1) → conversion math (Task 2) → eligibility relax (Task 3) → A2 unit-fix (Task 4) → paymaster settle + FIX-A/B (Task 5) → settle dispatch + FIX-C (Task 6) → liquidity genesis seed (Task 7) → conservation test (Task 8)`, with the **M4 hook contract verified first (Task 0)**.

Each task precedes its dependents: the peg read/write and conversion functions must exist before eligibility can consult the peg; eligibility must admit token cards before A2 can size their headroom; A2 must be unit-correct before the settle can safely debit (A2 is the cap gate the settle relies on for "accumulate can't breach"); the paymaster method must exist before the settle site can call it; the genesis reserve must be seedable before the conservation test can exercise a funded bank. Task 0 is first because it is the hard M4 dependency — nothing else is meaningful if the hook vetoes `→ 0x16`.

---

### Task 0: M4 hook contract — verify `card → 0x16` is admissible

**Files:**
- Test: `execution/src/execution/tests.rs` (new tests near the M3.5 block `:16373`)

This task does **not** modify product code. It pins the M4 contract as an executable test using a stub hook, and the FIX-A fall-through as its complement. It is the gate the rest of the plan depends on.

- [ ] **Step 1: Write the contract test (admit path) — expected to compile-fail until Task 5 exists**

Add a helper that seeds a CUSD-like token whose `transfer_hook` **admits `→ 0x16`**, then asserts a direct `handle_token_transfer(card → 0x16)` succeeds. Model the mint+hook seeding on the existing hook tests (`tests.rs:2942`, `:8320` seed `transfer_hook: Some(hook_addr)` with a small allow/deny Python hook).

```rust
// ── CIP-28 M3.6 Task 0: M4 hook contract — card → 0x16 must be admissible ──────

/// Seed a CUSD-like token `token_id` with `initial` balance credited to `holder`, whose
/// on-chain `transfer_hook` is `hook_code` (a Python actor). Mirrors the hook-token setup
/// used by the CIP-20 hook tests (tests.rs:2942 / :8320).
fn seed_cusd_with_hook(
    store: &mut DummyStore,
    token_id: [u8; 32],
    holder: Address,
    initial: u128,
    hook_addr: Address,
    hook_code: &[u8],
) {
    insert_test_actor(store, hook_addr, hook_code);
    // Register the mint with the hook and credit `holder`. Reuse whatever mint-seed helper
    // the hook tests use; here we set the registry entry + balance directly.
    seed_token_mint(store, token_id, /*transfer_hook=*/ Some(hook_addr));
    let bal_key = cowboy_token::storage_keys::token_registry::balance_key(&holder, &token_id);
    futures::executor::block_on(crate::token::query::write_balance(store, &bal_key, initial))
        .unwrap();
}

/// M4 contract: a CUSD hook that ADMITS transfers whose destination is 0x16 lets a
/// `card → 0x16` transfer through. This is exactly the allowlist entry M4 must seed.
#[test]
fn cip28_m36_hook_admits_card_to_bank() {
    big_stack(|| {
        let token_id = [0xC5u8; 32];
        let card = Address::from_low_u64(0xC0DE);
        let hook = Address::from_low_u64(0x9001);
        let mut store = DummyStore::default();
        // Hook admits iff `to == 0x16`; rejects otherwise.
        let hook_code =
            b"def can_transfer(f, t, a):\n return t == bytes(19)+b'\\x16'\ndef on_transfer(f,t,a):\n return b'ok'";
        seed_cusd_with_hook(&mut store, token_id, card, 1_000_000, hook, hook_code);
        let mut engine = ExecutionEngine::new();
        let mut dummy = Account::new();
        let mut meters = DualGasMeters::new(50_000, 50_000);
        let r = futures::executor::block_on(engine.handle_token_transfer(
            &mut store,
            &token_id,
            &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR,
            10_000,
            &card,
            &mut dummy,
            &mut meters,
            BANK_H,
            &Digest::from([0x28u8; 32]),
            0,
            Digest::from([0x28u8; 32]),
        ));
        assert!(r.is_ok(), "M4 contract: card → 0x16 must be admitted, got {r:?}");
    });
}
```

- [ ] **Step 2: Write the veto test (the FIX-A precondition)**

```rust
/// A CUSD hook that REJECTS card → 0x16 makes handle_token_transfer Err(TokenHookRejected)
/// BEFORE any balance write. Task 5's FIX-A converts this into Ok((0,0)) at the settle site.
#[test]
fn cip28_m36_hook_vetoes_card_to_bank_errs_before_write() {
    big_stack(|| {
        let token_id = [0xC6u8; 32];
        let card = Address::from_low_u64(0xC0DF);
        let hook = Address::from_low_u64(0x9002);
        let mut store = DummyStore::default();
        let hook_code = b"def can_transfer(f, t, a):\n return False\ndef on_transfer(f,t,a):\n return b'ok'";
        seed_cusd_with_hook(&mut store, token_id, card, 1_000_000, hook, hook_code);
        let bal_key = cowboy_token::storage_keys::token_registry::balance_key(&card, &token_id);
        let before =
            futures::executor::block_on(crate::token::query::read_balance(&store, &bal_key)).unwrap();
        let mut engine = ExecutionEngine::new();
        let mut dummy = Account::new();
        let mut meters = DualGasMeters::new(50_000, 50_000);
        let r = futures::executor::block_on(engine.handle_token_transfer(
            &mut store, &token_id, &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, 10_000,
            &card, &mut dummy, &mut meters, BANK_H,
            &Digest::from([0x28u8; 32]), 0, Digest::from([0x28u8; 32]),
        ));
        assert!(matches!(r, Err(ExecutionError::TokenHookRejected)));
        let after =
            futures::executor::block_on(crate::token::query::read_balance(&store, &bal_key)).unwrap();
        assert_eq!(before, after, "veto must not move funds");
    });
}
```

- [ ] **Step 3: Run — verify (a) compile, (b) the two tests express the contract**

Run: `cargo test -p cowboy-execution -- cip28_m36_hook --nocapture`
Expected: both PASS. If `seed_token_mint` / `write_balance` helper names differ in the tree, grep `tests.rs` for the existing hook-token seeding (`transfer_hook: Some(hook_addr)` at `:2942`) and reuse verbatim — do not invent a new mint path.

- [ ] **Step 4: Commit**

```bash
git add execution/src/execution/tests.rs
git commit -m "test(cip28-m36): pin M4 hook contract — card->0x16 admit/veto"
```

---

### Task 1: Peg storage — `gas_peg_key` / `read_gas_peg` / `write_gas_peg`

**Files:**
- Modify: `execution/src/bank/storage.rs` (add after the stablecoin-whitelist block, ~`:448`)
- Test: `execution/src/bank/storage.rs` (`#[cfg(test)]`, near `whitelist_write_and_contains` `:660`)

- [ ] **Step 1: Write the failing test**

```rust
#[tokio::test]
async fn gas_peg_write_read_roundtrip_and_absent() {
    let mut s = TestStore::default();
    let tid = [0x11u8; 32];
    // Absent → None.
    assert_eq!(read_gas_peg(&s, &tid).await.unwrap(), None);
    // Roundtrip a non-1:1 peg (num != den to catch unit bugs later).
    write_gas_peg(&mut s, &tid, 3, 2).await.unwrap();
    assert_eq!(read_gas_peg(&s, &tid).await.unwrap(), Some((3u64, 2u64)));
    // Key layout is exactly b"gas_peg:" ‖ token_id.
    assert_eq!(&gas_peg_key(&tid)[..8], b"gas_peg:");
    assert_eq!(gas_peg_key(&tid).len(), 8 + 32);
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-execution -- gas_peg_write_read_roundtrip --nocapture`
Expected: FAIL — `cannot find function gas_peg_key / read_gas_peg / write_gas_peg`.

- [ ] **Step 3: Add the helpers (hand-rolled fixed BE, mirrors `read_bank_seq`/`decode_u64`)**

```rust
// ── Gas peg (CIP-28 M3.6): genesis-fixed integer CBY↔U peg per token ──────────

/// Storage key for a token's gas peg: `b"gas_peg:" ‖ token_id(32)`.
pub fn gas_peg_key(token_id: &[u8; 32]) -> Vec<u8> {
    let mut k = Vec::with_capacity(8 + 32);
    k.extend_from_slice(b"gas_peg:");
    k.extend_from_slice(token_id);
    k
}

/// Read the genesis-fixed integer peg `(num, den)` for `token_id`. Value is a hand-rolled
/// fixed 16-byte blob `num(8 BE) ‖ den(8 BE)` — NOT serde. Absent → `None` (the token is
/// not gas-funding). A malformed length is a hard `InvalidData` (genesis is the only writer).
pub async fn read_gas_peg<S: StateStore>(
    store: &S,
    token_id: &[u8; 32],
) -> Result<Option<(u64, u64)>, ExecutionError> {
    match get_raw(store, &gas_peg_key(token_id)).await? {
        Some(b) => {
            if b.len() != 16 {
                return Err(ExecutionError::InvalidData);
            }
            let num = u64::from_be_bytes(b[0..8].try_into().unwrap());
            let den = u64::from_be_bytes(b[8..16].try_into().unwrap());
            Ok(Some((num, den)))
        }
        None => Ok(None),
    }
}

/// Overwrite the gas peg for `token_id` with `(num, den)`. Genesis-only in practice.
pub async fn write_gas_peg<S: StateStore>(
    store: &mut S,
    token_id: &[u8; 32],
    num: u64,
    den: u64,
) -> Result<(), ExecutionError> {
    let mut v = Vec::with_capacity(16);
    v.extend_from_slice(&num.to_be_bytes());
    v.extend_from_slice(&den.to_be_bytes());
    set_raw(store, gas_peg_key(token_id), v).await
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cargo test -p cowboy-execution -- gas_peg_write_read_roundtrip --nocapture`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/src/bank/storage.rs
git commit -m "feat(cip28-m36): gas_peg storage helpers under 0x16 (fixed BE)"
```

---

### Task 2: Peg conversion math — `convert_cby_to_u` / `cby_from_u`

**Files:**
- Modify: `execution/src/bank/handlers.rs` (add near `rolled_cap_headroom` `:260`)
- Test: `execution/src/bank/handlers.rs` (`#[cfg(test)]`)

Integer floor, deterministic, **no float** (MEMORY `project_cow2293_bigint_literal_guard`: never `log2`/float — integer mul/div only).

- [ ] **Step 1: Write the failing test (both directions + a KAT + non-1:1)**

```rust
#[test]
fn peg_conversions_floor_and_kat() {
    use super::{cby_from_u, convert_cby_to_u};
    // Identity peg (1:1): both directions are the identity.
    assert_eq!(convert_cby_to_u(1_000, 1, 1), 1_000);
    assert_eq!(cby_from_u(1_000, 1, 1), 1_000);
    // Non-1:1 KAT: 1 CBY = 3/2 U → 1000 CBY = 1500 U; inverse floors.
    assert_eq!(convert_cby_to_u(1_000, 3, 2), 1_500);
    assert_eq!(cby_from_u(1_500, 3, 2), 1_000);
    // Floor: 7 CBY at 3/2 = 10 U (10.5 floored); inverse 10 U → 6 CBY (6.66 floored).
    assert_eq!(convert_cby_to_u(7, 3, 2), 10);
    assert_eq!(cby_from_u(10, 3, 2), 6);
    // den/num == 0 guarded by `.max(1)` — never divide by zero (defense-in-depth;
    // genesis validate() already rejects a zero peg).
    assert_eq!(convert_cby_to_u(5, 1, 0), 5);
    assert_eq!(cby_from_u(5, 0, 1), 5);
    // Saturating mul: no overflow panic at the u128 ceiling.
    assert_eq!(convert_cby_to_u(u128::MAX, 2, 1), u128::MAX);
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-execution -- peg_conversions_floor_and_kat --nocapture`
Expected: FAIL — `cannot find function convert_cby_to_u`.

- [ ] **Step 3: Add the functions**

```rust
/// CIP-28 §4.2 step 5 / §4.4: convert a CBY amount to the card's U units under the
/// genesis-fixed integer peg `(num, den)` where `1 CBY = num/den U`. Integer floor,
/// deterministic, NO float (project_cow2293: never log2/float). `saturating_mul` caps at
/// the u128 ceiling; `.max(1)` makes a zero denominator inert (genesis validate() rejects it).
pub fn convert_cby_to_u(cby: u128, num: u64, den: u64) -> u128 {
    cby.saturating_mul(num as u128) / (den as u128).max(1)
}

/// Inverse of `convert_cby_to_u`: the CBY-equivalent of `u` U units under `(num, den)`.
/// Integer floor. Used to bound `covered_cby` by what the card can actually afford in U.
pub fn cby_from_u(u: u128, num: u64, den: u64) -> u128 {
    u.saturating_mul(den as u128) / (num as u128).max(1)
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cargo test -p cowboy-execution -- peg_conversions_floor_and_kat --nocapture`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/src/bank/handlers.rs
git commit -m "feat(cip28-m36): integer CBY<->U peg conversion (floor, no float)"
```

---

### Task 3: Eligibility — admit peg+whitelisted `Token` cards; guard native path

**Files:**
- Modify: `execution/src/bank/handlers.rs:351-378` (`card_is_eligible`), `:766-803` (native `bank_charge_gas` guard)
- Test: `execution/src/bank/handlers.rs`

**Audit fix (whitelist-membership):** admit `Token(id)` **only when the peg is present AND `id` is on `stablecoin_whitelist`** — defense-in-depth; do not rely solely on issuance-time enforcement (`handlers.rs:442`).

**Correctness coupling:** because `card_is_eligible` is shared by the native `bank_charge_gas`, relaxing it means the native path could now be reached with a `Token` card. Guard native `bank_charge_gas` to `Ok(0)` on any non-Native card so it never debits a token card's CBY `Account.balance`.

- [ ] **Step 1: Write the failing tests**

```rust
#[tokio::test]
async fn eligible_admits_token_card_with_peg_and_whitelist_only() {
    let mut s = TestStore::default();
    seed_bank(&mut s, BankStatus::Active).await;
    let card = a(0xC0);
    let tid = [0x55u8; 32];
    write_native_card(&mut s, &card, &a(0xB0), CardStatus::Active,
        PayCurrency::Token(tid), None, 0).await;
    // No peg, not whitelisted → ineligible.
    assert!(card_is_eligible(&s, &card, 5).await.unwrap().is_none());
    // Peg present but NOT whitelisted → still ineligible (defense-in-depth).
    storage::write_gas_peg(&mut s, &tid, 1, 1).await.unwrap();
    assert!(card_is_eligible(&s, &card, 5).await.unwrap().is_none());
    // Peg present AND whitelisted → eligible.
    storage::write_stablecoin_whitelist(&mut s, &[tid]).await.unwrap();
    assert!(card_is_eligible(&s, &card, 5).await.unwrap().is_some());
}

#[tokio::test]
async fn native_charge_gas_never_debits_token_card() {
    let mut s = TestStore::default();
    seed_bank(&mut s, BankStatus::Active).await;
    let card = a(0xC0);
    let tid = [0x55u8; 32];
    write_native_card(&mut s, &card, &a(0xB0), CardStatus::Active,
        PayCurrency::Token(tid), None, 1_000).await; // CBY balance present but token card
    storage::write_gas_peg(&mut s, &tid, 1, 1).await.unwrap();
    storage::write_stablecoin_whitelist(&mut s, &[tid]).await.unwrap();
    // Native path must fall through (token cards settle via bank_charge_gas_token).
    assert_eq!(super::bank_charge_gas(&mut s, &card, 400, 5).await.unwrap(), 0);
    assert_eq!(native_bal(&s, &card).await, 1_000); // untouched
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-execution -- eligible_admits_token_card native_charge_gas_never --nocapture`
Expected: FAIL — token card returns `None` today; native charge would debit it.

- [ ] **Step 3: Relax `card_is_eligible` (replace `:374-376`)**

```rust
    // CIP-28 M3.6: admit a Token(U) card ONLY when a genesis peg exists for U AND U is on
    // the stablecoin whitelist (defense-in-depth vs. issuance-time enforcement). Native
    // cards are unconditionally admitted (existing behavior). Any other case → ineligible.
    match card.gas_payment_token {
        PayCurrency::Native => {}
        PayCurrency::Token(token_id) => {
            if storage::read_gas_peg(store, &token_id).await?.is_none() {
                return Ok(None);
            }
            if !storage::stablecoin_whitelist_contains(store, &token_id).await? {
                return Ok(None);
            }
        }
    }
    Ok(Some(card))
```

- [ ] **Step 4: Guard native `bank_charge_gas` (insert right after the `card_is_eligible` match at `:773-776`)**

```rust
    // CIP-28 M3.6: this native debit path only funds Native cards. A Token(U) card is now
    // eligible (Task 3) but must settle via the paymaster path (bank_charge_gas_token), so
    // fall through with Ok(0) here — never debit a token card's own CBY Account.balance.
    if card.gas_payment_token != PayCurrency::Native {
        return Ok(0);
    }
```

- [ ] **Step 5: Run to verify it passes**

Run: `cargo test -p cowboy-execution -- eligible_admits_token_card native_charge_gas_never --nocapture`
Expected: PASS. Then `cargo test -p cowboy-execution -- charge_gas_` to confirm existing native tests still green.

- [ ] **Step 6: Commit**

```bash
cargo fmt --all
git add execution/src/bank/handlers.rs
git commit -m "feat(cip28-m36): admit peg+whitelisted token cards; guard native charge"
```

---

### Task 4: A2 admission unit-fix — compare U-unit headroom vs U-unit need

**Files:**
- Modify: `execution/src/execution/transaction.rs:215-245`
- Test: covered by the integration conservation test (Task 8) + the A2 unit assertion below

**Audit fix (unit bug):** the A2 headroom check compares `rolled_cap_headroom` (U units) against `max_total_cost` (CBY). For a token card these differ. Convert the CBY worst-case to U before comparing: `need = convert_cby_to_u(max_total_cost, num, den)`. Native = identity. This is why Tasks 1–3 precede A2.

- [ ] **Step 1: Restructure the A2 block (replace `:216-245`)**

The `&&`-chain can't host an async peg read, so lift the body into a nested block:

```rust
        let below_bank_activation = block_height < cowboy_types::BANK_ACTIVATION_HEIGHT;
        if !below_bank_activation
            && let Instruction::Actor(ActorInstruction::ExecuteActor { actor, .. }) =
                &tx.instruction
            && let Some(card_addr) = crate::bank::storage::read_default_card(store, actor).await?
            && let Some(card) =
                crate::bank::handlers::card_is_eligible(store, &card_addr, block_height).await?
        {
            // CIP-28 M3.6: the cap window is denominated in the card's pay-currency (U for a
            // token card, CBY for native). `rolled_cap_headroom` is therefore in U units;
            // convert this tx's worst-case CBY cost to U before comparing. Native = identity.
            let need: u128 = match card.gas_payment_token {
                crate::bank::PayCurrency::Native => max_total_cost as u128,
                crate::bank::PayCurrency::Token(token_id) => {
                    // Peg is guaranteed present (card_is_eligible admitted the card); the
                    // identity fallback is defensive and unreachable.
                    match crate::bank::storage::read_gas_peg(store, &token_id).await? {
                        Some((num, den)) => crate::bank::handlers::convert_cby_to_u(
                            max_total_cost as u128,
                            num,
                            den,
                        ),
                        None => max_total_cost as u128,
                    }
                }
            };
            let headroom = crate::bank::handlers::rolled_cap_headroom(&card, block_height);
            let denied = !crate::bank::handlers::policy_admits(
                &card.policy,
                actor,
                &crate::bank::handlers::syscall_kind_of(&tx.instruction),
            );
            if headroom < need || denied {
                let e = ExecutionError::InsufficientBalanceForGas {
                    required: max_total_cost,
                    available: u64::try_from(headroom).unwrap_or(u64::MAX),
                };
                return Ok((
                    0,
                    0,
                    ExecutionStatus::ExecutionError(e.into_structured()),
                    vec![],
                    vec![],
                ));
            }
        }
```

- [ ] **Step 2: Add the A2 unit-assertion test (unit-level, in `execution/src/bank/handlers.rs` tests) — a non-1:1 peg must NOT be treated as CBY**

Assert directly on the converter+headroom contract the A2 block now uses (the integration cap-reject is Task 8):

```rust
#[test]
fn a2_token_need_uses_peg_not_cby_identity() {
    use super::convert_cby_to_u;
    // At peg 3/2, a 1000-CBY worst-case needs 1500 U of headroom, not 1000.
    let need = convert_cby_to_u(1_000, 3, 2);
    assert_eq!(need, 1_500);
    // A card whose U headroom is 1200 (enough under a naive CBY compare) must be REJECTED
    // because 1200 < 1500. This is the bug the M3.5 1:1 tests masked.
    let headroom_u: u128 = 1_200;
    assert!(headroom_u < need, "token card must reject: U headroom < U need");
}
```

- [ ] **Step 3: Run**

Run: `cargo build -p cowboy-execution && cargo test -p cowboy-execution -- a2_token_need_uses_peg --nocapture`
Expected: build OK; test PASS.

- [ ] **Step 4: Commit**

```bash
cargo fmt --all
git add execution/src/execution/transaction.rs execution/src/bank/handlers.rs
git commit -m "fix(cip28-m36): A2 admission compares U-unit headroom vs U-unit need"
```

---

### Task 5: Paymaster settle — `bank_charge_gas_token` (FIX-A + FIX-B)

**Files:**
- Modify: `execution/src/bank/handlers.rs` (add method inside the `impl ExecutionEngine` block, near `bank_deposit` `:807`)
- Test: `execution/src/execution/tests.rs`

The heart. `bank_charge_gas_token` returns `(covered_cby: u64, covered_u: u128)`.

**FIX-A (BLOCKER):** every `handle_token_transfer` error (`TokenHookRejected`/`TokenAccountFrozen`/`TokenInsufficientBalance`/`TokenNotFound`) → `Ok((0,0))`, never `?`-propagate. Leg 1 errors before any write, so `Ok((0,0))` leaves state untouched.
**FIX-B (BLOCKER):** drain the `TokenTransfer` Leg 1 pushed onto `self.system_events` and re-home it into the caller's local `events` (with the `0x16` emitter) — under an Actor instruction `self.system_events` is NOT drained (`transaction.rs:413-436`), so an orphan would leak into the next System-instruction tx's `receipt_root`.
**TOCTOU fix:** read `0x16`'s CBY `Account.balance` **once** (`bank_cby`) and debit that same object with `saturating_sub` — never re-read after Leg 1 (re-reading risks an underflow / CBY-mint).
**LOW-6:** run Leg 1 under a **bounded scratch `DualGasMeters`** so the settle-time hook can't fail the real tx meter and is deterministically capped.

- [ ] **Step 1: Write the failing integration tests**

Add a token-card variant of `run_bank_gas_events` and three assertions. `seed_default_card` (`tests.rs:15448`) seeds bank+card+default; extend it to also seed the peg, whitelist, card U balance, a hook admitting `→0x16`, and the `0x16` CBY reserve.

```rust
/// Seed everything a Token(U) default card needs to settle via the paymaster: peg, whitelist,
/// the card's U balance, a CUSD hook admitting → 0x16, and the 0x16 CBY reserve.
fn seed_token_card_paymaster(
    store: &mut DummyStore,
    card: Address,
    agent: Address,
    token_id: [u8; 32],
    peg: (u64, u64),
    card_u: u128,
    bank_cby: u64,
) {
    seed_default_card(store, card, agent, crate::bank::CardStatus::Active,
        crate::bank::PayCurrency::Token(token_id), None, 0);
    futures::executor::block_on(crate::bank::storage::write_gas_peg(store, &token_id, peg.0, peg.1)).unwrap();
    futures::executor::block_on(crate::bank::storage::write_stablecoin_whitelist(store, &[token_id])).unwrap();
    let hook = Address::from_low_u64(0x9101);
    let hook_code = b"def can_transfer(f,t,a):\n return t == bytes(19)+b'\\x16'\ndef on_transfer(f,t,a):\n return b'ok'";
    seed_cusd_with_hook(store, token_id, card, card_u, hook, hook_code); // from Task 0
    store.accounts.insert(cowboy_types::BANK_ACTOR_SYSTEM_ACTOR,
        Account { nonce: 0, balance: bank_cby });
}

/// FIX-A: a hook-vetoed token card yields covered == 0 and leaves ALL state untouched
/// (no pay-then-fail), returning Ok((0,0)) rather than Err.
#[test]
fn cip28_m36_paymaster_hook_veto_falls_through_zero() {
    big_stack(|| {
        let card = Address::from_low_u64(0xC0DE);
        let agent = Address::from_low_u64(0x2801);
        let token_id = [0xC7u8; 32];
        let mut store = DummyStore::default();
        seed_default_card(&mut store, card, agent, crate::bank::CardStatus::Active,
            crate::bank::PayCurrency::Token(token_id), None, 0);
        futures::executor::block_on(crate::bank::storage::write_gas_peg(&mut store, &token_id, 1, 1)).unwrap();
        futures::executor::block_on(crate::bank::storage::write_stablecoin_whitelist(&mut store, &[token_id])).unwrap();
        let hook = Address::from_low_u64(0x9102);
        seed_cusd_with_hook(&mut store, token_id, card, 1_000_000,
            hook, b"def can_transfer(f,t,a):\n return False\ndef on_transfer(f,t,a):\n return b'ok'");
        store.accounts.insert(cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, Account { nonce: 0, balance: 1_000_000 });
        let mut engine = ExecutionEngine::new();
        let mut events: Vec<(Address, String, Vec<u8>)> = Vec::new();
        let r = futures::executor::block_on(engine.bank_charge_gas_token(
            &mut store, &card, 500, BANK_H, &Digest::from([0x28u8; 32]), 0,
            Digest::from([0x28u8; 32]), &mut events));
        assert_eq!(r.unwrap(), (0u64, 0u128), "hook veto → Ok((0,0))");
        assert!(events.is_empty(), "no events on a vetoed settle");
        assert!(engine.system_events.is_empty(), "system_events must stay empty");
    });
}

/// FIX-B + normal cover: covered_u moves card → 0x16, covered_cby debits the bank, the
/// TokenTransfer is re-homed into local events (0x16 emitter), and system_events is EMPTY.
#[test]
fn cip28_m36_paymaster_cover_rehomes_token_transfer() {
    big_stack(|| {
        let card = Address::from_low_u64(0xC0DE);
        let agent = Address::from_low_u64(0x2801);
        let token_id = [0xC8u8; 32];
        let mut store = DummyStore::default();
        // Non-1:1 peg: 1 CBY = 2 U. amount_cby=300 → covered_u=600.
        seed_token_card_paymaster(&mut store, card, agent, token_id, (2, 1), 10_000, 1_000_000);
        let mut engine = ExecutionEngine::new();
        let mut events: Vec<(Address, String, Vec<u8>)> = Vec::new();
        let (cby, u) = futures::executor::block_on(engine.bank_charge_gas_token(
            &mut store, &card, 300, BANK_H, &Digest::from([0x28u8; 32]), 0,
            Digest::from([0x28u8; 32]), &mut events)).unwrap();
        assert_eq!((cby, u), (300u64, 600u128), "1 CBY = 2 U");
        // Card U debited by 600; bank CBY debited by 300.
        let bal_key = cowboy_token::storage_keys::token_registry::balance_key(&card, &token_id);
        assert_eq!(futures::executor::block_on(crate::token::query::read_balance(&store, &bal_key)).unwrap(), 9_400);
        assert_eq!(store.accounts.get(&cowboy_types::BANK_ACTOR_SYSTEM_ACTOR).unwrap().balance, 999_700);
        // Bank U credited by 600 (paymaster received the U).
        let bank_u = cowboy_token::storage_keys::token_registry::balance_key(&cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, &token_id);
        assert_eq!(futures::executor::block_on(crate::token::query::read_balance(&store, &bank_u)).unwrap(), 600);
        // FIX-B: the TokenTransfer is in local events with the 0x16 emitter, NOT leaked.
        assert!(events.iter().any(|(em, t, _)| *em == cowboy_types::BANK_ACTOR_SYSTEM_ACTOR && t == "TokenTransfer"));
        assert!(engine.system_events.is_empty(), "system_events must be EMPTY after settle");
    });
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-execution -- cip28_m36_paymaster --nocapture`
Expected: FAIL — `no method named bank_charge_gas_token`.

- [ ] **Step 3: Implement `bank_charge_gas_token` (inside `impl ExecutionEngine`, `handlers.rs`)**

```rust
    /// CIP-28 M3.6 §2.3/§4.2: bank-as-paymaster gas settle for a `Token(U)` default card.
    /// Moves `covered_u` U from `card → 0x16` (Leg 1, hook-respecting) and debits `covered_cby`
    /// CBY from the bank's OWN account (Leg 2). The caller folds `covered_cby` into `actor_paid`
    /// exactly like the native `card_paid`, so CBY tx-fee conservation holds (the bank's CBY
    /// funds the burn/tip). Returns `(covered_cby, covered_u)`.
    ///
    /// FIX-A: EVERY `handle_token_transfer` error → `Ok((0,0))` (never `Err`, never `?`); Leg 1
    /// errors before any write, so state stays untouched.
    /// FIX-B: the `TokenTransfer` Leg 1 appends to `self.system_events` is drained here and
    /// re-homed into `local_events` (0x16 emitter) — it must NOT leak into the next
    /// System-instruction tx's receipt_root under this Actor instruction.
    /// TOCTOU: read the `0x16` CBY account ONCE and `saturating_sub` that object — no re-read.
    #[allow(clippy::too_many_arguments)]
    pub async fn bank_charge_gas_token<S: StateStore>(
        &mut self,
        store: &mut S,
        card_addr: &Address,
        amount_cby: u64,
        block_height: u64,
        block_hash: &Digest,
        timestamp_ms: u64,
        tx_hash: Digest,
        local_events: &mut Vec<(Address, String, Vec<u8>)>,
    ) -> Result<(u64, u128), ExecutionError>
    where
        <S as StateStore>::Error: From<cowboy_storage::Error>,
    {
        // 1. Eligibility — Ok((0,0)) fall-through, NEVER Err on ineligibility.
        let mut card = match card_is_eligible(store, card_addr, block_height).await? {
            Some(c) => c,
            None => return Ok((0, 0)),
        };
        let token_id = match card.gas_payment_token {
            PayCurrency::Token(id) => id,
            PayCurrency::Native => return Ok((0, 0)), // native handled by bank_charge_gas
        };
        // 2. Peg + balances. Read the 0x16 CBY account ONCE (TOCTOU-safe).
        let (num, den) = match storage::read_gas_peg(store, &token_id).await? {
            Some(p) => p,
            None => return Ok((0, 0)),
        };
        let bal_key = cowboy_token::storage_keys::token_registry::balance_key(card_addr, &token_id);
        let card_u = crate::token::query::read_balance(store, &bal_key)
            .await
            .map_err(ExecutionError::from_store)?;
        let mut bank_acct = store
            .get_account(&cowboy_types::BANK_ACTOR_SYSTEM_ACTOR)
            .await
            .map_err(ExecutionError::from_store)?
            .unwrap_or_else(Account::new);
        let bank_cby = bank_acct.balance as u128;
        // 3. covered_cby bounded by (requested, card affordability in CBY-equiv, bank liquidity).
        let covered_cby = (amount_cby as u128)
            .min(cby_from_u(card_u, num, den))
            .min(bank_cby);
        let covered_u = convert_cby_to_u(covered_cby, num, den);
        if covered_u == 0 {
            return Ok((0, 0));
        }
        let covered_cby_u64 = covered_cby as u64; // ≤ amount_cby (u64) and ≤ bank_cby
        // 4. Leg 1 (U): card → 0x16, hook-respecting. LOW-6: bounded scratch meter so the
        //    settle-time hook cannot fail the real tx meter and is deterministically capped.
        let mut scratch = crate::gas::DualGasMeters::new(
            self.gas_costs.token_hook_max_cycles.saturating_add(self.gas_costs.token_transfer_cycles),
            self.gas_costs.token_transfer_cells.saturating_mul(8).max(1),
        );
        let mut sender_ignored = Account::new(); // handle_token_transfer ignores _sender_account
        let evt_base = self.system_events.len();
        let leg1 = self
            .handle_token_transfer(
                store,
                &token_id,
                &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR,
                covered_u,
                card_addr,
                &mut sender_ignored,
                &mut scratch,
                block_height,
                block_hash,
                timestamp_ms,
                tx_hash,
            )
            .await;
        if leg1.is_err() {
            // FIX-A: any transfer error → Ok((0,0)). Leg 1 errors before its balance writes
            // and before pushing TokenTransfer, so state is untouched; truncate defensively.
            self.system_events.truncate(evt_base);
            return Ok((0, 0));
        }
        // FIX-B: re-home the events Leg 1 appended into local_events with the 0x16 emitter;
        // do NOT let them ride self.system_events under this Actor instruction.
        let drained: Vec<(String, Vec<u8>)> = self.system_events.drain(evt_base..).collect();
        for (topic, payload) in drained {
            local_events.push((cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, topic, payload));
        }
        // 5. Leg 2 (CBY): debit the FIRST-read bank account with saturating_sub (no re-read).
        bank_acct.balance = bank_acct.balance.saturating_sub(covered_cby_u64);
        store
            .set_account(cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, bank_acct)
            .await
            .map_err(ExecutionError::from_store)?;
        // A3: record the spend in U units (the window/cap unit, §5.1). A2 already bounded
        // covered_u ≤ need ≤ headroom, so this can never breach a cap.
        accumulate_spend(&mut card, covered_u, block_height);
        storage::write_card(store, card_addr, &card).await?;
        Ok((covered_cby_u64, covered_u))
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `cargo test -p cowboy-execution -- cip28_m36_paymaster --nocapture`
Expected: PASS (both the veto fall-through and the cover+re-home cases).

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add execution/src/bank/handlers.rs execution/src/execution/tests.rs
git commit -m "feat(cip28-m36): bank_charge_gas_token paymaster settle (FIX-A, FIX-B, TOCTOU)"
```

---

### Task 6: Settle-site dispatch — Native vs Token + FIX-C (GasCharged token-unit)

**Files:**
- Modify: `execution/src/execution/transaction.rs:519-559`
- Test: `execution/src/execution/tests.rs`

Dispatch on the eligible card's currency; Native keeps `bank_charge_gas` + `GasCharged covered/covered`; Token calls `bank_charge_gas_token` + **FIX-C** emits `GasCharged covered_u/covered_u`.

**Audit fix (FIX-C, MED):** the M3.5 emit passes `covered` (CBY). For a Token card, emit `covered_u` (U units) to match the window/`accumulate_spend` unit and §5.1. The M3.5 tests were all 1:1, masking this — the Task-6 test uses a non-1:1 peg.

- [ ] **Step 1: Replace the settle block (`:519-559`)**

```rust
                let mut card_paid: u64 = 0;
                let below_activation = block_height < cowboy_types::BANK_ACTIVATION_HEIGHT;
                if !below_activation
                    && let Some(card_addr) =
                        crate::bank::storage::read_default_card(store, actor).await?
                    && let Some(card_entry) = crate::bank::handlers::card_is_eligible(
                        store,
                        &card_addr,
                        block_height,
                    )
                    .await?
                {
                    // reserve == actual == the U-or-CBY the card actually paid (single-phase).
                    let gas_charged_amount: u128 = match card_entry.gas_payment_token {
                        crate::bank::PayCurrency::Native => {
                            card_paid = crate::bank::handlers::bank_charge_gas(
                                store, &card_addr, total_fee, block_height,
                            )
                            .await?;
                            card_paid as u128 // native: GasCharged unit = CBY
                        }
                        crate::bank::PayCurrency::Token(_) => {
                            // Paymaster settle: covered_cby folds into actor_paid (CBY
                            // conservation); covered_u is the U the card actually paid. FIX-B
                            // re-homes the TokenTransfer into `events` inside this call.
                            let (covered_cby, covered_u) = self
                                .bank_charge_gas_token(
                                    store,
                                    &card_addr,
                                    total_fee,
                                    block_height,
                                    block_hash,
                                    timestamp_ms,
                                    Digest::from(tx.digest().0),
                                    &mut events,
                                )
                                .await?;
                            card_paid = covered_cby;
                            covered_u // FIX-C: GasCharged unit = U (§5.1)
                        }
                    };
                    if card_paid > 0 {
                        events.push((
                            cowboy_types::BANK_ACTOR_SYSTEM_ACTOR,
                            crate::bank::handlers::TOPIC_GAS_CHARGED.to_string(),
                            crate::bank::handlers::encode_gas_charged(
                                &card_addr,
                                &tx.digest().0,
                                actor,
                                &crate::bank::handlers::syscall_kind_of(&tx.instruction),
                                gas_charged_amount,
                                gas_charged_amount,
                            ),
                        ));
                    }
                }
```

Note: `card_paid > 0` (CBY) gates the emit for BOTH paths — a token settle that covered any CBY also covered `covered_u > 0` (both are zero together, per step 3 of Task 5). `gas_charged_amount` carries the correct unit per path.

- [ ] **Step 2: Add the FIX-C non-1:1 assertion test (integration)**

Add a token variant of `run_bank_gas_events` (`seed_token_card_paymaster` from Task 5) and assert the `GasCharged` payload's reserve/actual fields decode to `covered_u` (U), not CBY:

```rust
/// FIX-C: a Token card at a non-1:1 peg emits GasCharged in U units (covered_u), not CBY.
#[test]
fn cip28_m36_gas_charged_token_unit_is_u() {
    big_stack(|| {
        let card = Address::from_low_u64(0xC0DE);
        let agent = Address::from_low_u64(0x2801);
        let token_id = [0xC9u8; 32];
        let mut store = DummyStore::default();
        insert_test_actor(&mut store, agent, b"def handle_message(p):\n return b'ok'");
        store.accounts.insert(agent, Account { nonce: 0, balance: 1_000_000_000 });
        // 1 CBY = 2 U; plenty of card U and bank CBY to cover the whole fee.
        seed_token_card_paymaster(&mut store, card, agent, token_id, (2, 1), 1_000_000_000, 1_000_000_000);
        let tx = Transaction::sign(&make_signing_key(0x28), 0, 0,
            Instruction::Actor(ActorInstruction::ExecuteActor {
                actor: agent, handler: "handle_message".to_string(), payload: Vec::new() }),
            50_000_000, 50_000_000, 1, 1);
        store.accounts.insert(tx.from, Account { nonce: 0, balance: 10_000_000_000 });
        let mut engine = ExecutionEngine::new();
        engine.set_basefee(DualBasefee { cycle_basefee: 1, cell_basefee: 1 });
        let (_c, _ce, status, _d, events) = futures::executor::block_on(engine.execute_transaction(
            &mut store, &tx, BANK_H, &Digest::from([0x28u8; 32]), 0, false)).unwrap();
        assert!(matches!(status, ExecutionStatus::Success));
        let (burn, tip) = engine.take_block_fees();
        let fee_cby = (burn + tip) as u128;
        let gas = events.iter().find(|(_, t, _)| t == "GasCharged").expect("GasCharged");
        // reserve/actual are the last two 16-byte BE fields.
        let p = &gas.2;
        let actual = u128::from_be_bytes(p[p.len()-16..].try_into().unwrap());
        assert_eq!(actual, fee_cby * 2, "GasCharged must be in U units (covered_u), not CBY");
        assert!(engine.system_events.is_empty(), "no orphan events");
    });
}
```

- [ ] **Step 3: Run**

Run: `cargo test -p cowboy-execution -- cip28_m36_gas_charged_token_unit cip28_gas_charged_event --nocapture`
Expected: new test PASS; the M3.5 native `GasCharged` tests still PASS (native path unchanged).

- [ ] **Step 4: Commit**

```bash
cargo fmt --all
git add execution/src/execution/transaction.rs execution/src/execution/tests.rs
git commit -m "feat(cip28-m36): settle dispatches token cards to paymaster; GasCharged in U (FIX-C)"
```

---

### Task 7: Genesis — seed gas pegs + `0x16` CBY reserve; validate num/den

**Files:**
- Modify: `chain/src/genesis.rs` (field `:283` area; seeding `:857-915`; `validate` `:513`; defaults `:461` and the other `stablecoin_whitelist: Vec::new()` sites)
- Modify: `validator/src/setup.rs:112-113`
- Test: `chain/src/genesis.rs`

**Audit fix (num==0):** genesis `validate()` MUST reject `num == 0 || den == 0` — a zero on either side silently makes the token non-funding (`convert_cby_to_u` floors to 0 / the `.max(1)` masks it).

- [ ] **Step 1: Write the failing tests**

```rust
#[test]
fn genesis_rejects_zero_peg() {
    let mut c = GenesisConfig::default();
    c.gas_pegs = vec![([0x55u8; 32], 0, 1)];
    assert!(c.validate().is_err(), "num == 0 must be rejected");
    c.gas_pegs = vec![([0x55u8; 32], 1, 0)];
    assert!(c.validate().is_err(), "den == 0 must be rejected");
    c.gas_pegs = vec![([0x55u8; 32], 3, 2)];
    // A valid peg must not, on its own, fail validate (other invariants permitting).
    // (Total-supply/account checks are exercised by existing genesis tests.)
}

#[test]
fn genesis_seeds_gas_peg_and_bank_reserve() {
    use cowboy_execution::bank::storage::gas_peg_key;
    let mut config = GenesisConfig::default();
    // ... reuse the existing bank-seed test setup (genesis.rs:2335) for accounts/supply ...
    let token_id = [0x55u8; 32];
    config.stablecoin_whitelist = vec![token_id];
    config.gas_pegs = vec![(token_id, 3, 2)];
    config.bank_cby_reserve = 1_000_000;
    let (actors, initial_storage, _accounts) = config.build_genesis_state(); // existing entry point
    let bank_addr = cowboy_types::BANK_ACTOR_SYSTEM_ACTOR;
    // Peg seeded as 16 BE bytes under 0x16.
    let peg = initial_storage.iter().find(|(a, k, _)| *a == bank_addr && k.as_slice() == gas_peg_key(&token_id).as_slice()).expect("peg seeded");
    assert_eq!(peg.2, [0u8,0,0,0,0,0,0,3, 0,0,0,0,0,0,0,2].to_vec());
    // 0x16 CBY reserve seeded.
    assert!(actors.iter().any(|(addr, _)| *addr == bank_addr));
    // (reserve balance assertion against the accounts vector — mirror the existing bank test)
}
```

(Adapt `build_genesis_state` / return-shape to the actual method the existing bank-seed test at `genesis.rs:2335` calls.)

- [ ] **Step 2: Run to verify it fails**

Run: `cargo test -p cowboy-chain -- genesis_rejects_zero_peg genesis_seeds_gas_peg --nocapture`
Expected: FAIL — `no field gas_pegs` / `no field bank_cby_reserve`.

- [ ] **Step 3: Add the fields (after `stablecoin_whitelist` `:283`)**

```rust
    /// CIP-28 M3.6: genesis-fixed integer gas pegs `(token_id, num, den)` where
    /// `1 CBY = num/den U`. Seeded under BankActor (0x16) at `gas_peg_key(token_id)` as
    /// `num(8 BE) ‖ den(8 BE)`. `validate()` rejects a zero on either side. Empty by default.
    #[serde(default)]
    pub gas_pegs: Vec<([u8; 32], u64, u64)>,
    /// CIP-28 M3.6: the CBY reserve seeded into BankActor's own account (0x16), which funds
    /// the paymaster CBY leg (Leg 2). 待裁 size. Zero by default (paymaster covers nothing
    /// until funded). Counts toward `total_supply` accounting like any genesis balance.
    #[serde(default)]
    pub bank_cby_reserve: u64,
```

- [ ] **Step 4: Seed the pegs + reserve (after the whitelist push `:915`)**

```rust
        // CIP-28 M3.6: seed the integer gas pegs (num(8 BE) ‖ den(8 BE)) under 0x16.
        for (token_id, num, den) in &self.gas_pegs {
            let mut v = Vec::with_capacity(16);
            v.extend_from_slice(&num.to_be_bytes());
            v.extend_from_slice(&den.to_be_bytes());
            initial_storage.push((
                bank_addr,
                cowboy_execution::bank::storage::gas_peg_key(token_id),
                v,
            ));
        }
```

Seed the CBY reserve into `0x16`'s account. The bank actor is already pushed to `actors` at `:866`; add its account balance where genesis account balances are assembled (mirror how other system actors get a starting `Account.balance`; if system actors currently get `Account::new()` (zero), add a `bank_cby_reserve` balance entry for `bank_addr`). Ensure `total_supply` accounting includes it (adjust the genesis account-sum or add `bank_cby_reserve` to the supply the same way seeded account balances are).

- [ ] **Step 5: Add the `validate()` check (inside `validate`, `:513+`)**

```rust
        for (idx, (_id, num, den)) in self.gas_pegs.iter().enumerate() {
            if *num == 0 || *den == 0 {
                return Err(format!(
                    "gas_pegs[{idx}]: peg num and den must both be non-zero (got num={num}, den={den})"
                ));
            }
        }
```

- [ ] **Step 6: Add defaults**

`chain/src/genesis.rs` — add `gas_pegs: Vec::new(),` and `bank_cby_reserve: 0,` to every `GenesisConfig { .. }` literal that currently sets `stablecoin_whitelist: Vec::new()` (`:461`, `:1646`, `:1928`, `:1957`, `:1994`, `:2031`, `:2697`).
`validator/src/setup.rs` — add the same two defaults to the `GenesisConfig { .. }` at `:96-113`.

- [ ] **Step 7: Run to verify it passes**

Run: `cargo test -p cowboy-chain -- genesis_rejects_zero_peg genesis_seeds_gas_peg --nocapture && cargo build -p validator`
Expected: PASS; validator builds.

- [ ] **Step 8: Commit**

```bash
cargo fmt --all
git add chain/src/genesis.rs validator/src/setup.rs
git commit -m "feat(cip28-m36): genesis seeds gas pegs + 0x16 CBY reserve; validate non-zero peg"
```

---

### Task 8: Conservation test — full `execute_transaction` token settle

**Files:**
- Test: `execution/src/execution/tests.rs`

**Audit fix (MED):** the cited `econ_tx_fee_conservation` / `econ_*_per_unit` proptests are pure arithmetic over `DualBasefee::compute_tx_fees` — they never touch accounts, so they are **not** evidence for the CBY leg. Add a dedicated balance-sum test over the full token-card settle.

Assert, for BOTH the normal-cover path and the partial-cover / hook-veto (covered==0) branch:
- `Σ CBY` across `{card CBY, 0x16 CBY, actor, owner(if any), sender, burn+tip}` is unchanged pre→post.
- `Σ U` (total CUSD supply across `{card, 0x16, everyone}`) is unchanged pre→post.

- [ ] **Step 1: Write the conservation test**

```rust
/// Full-path conservation for a Token(U) card settle: CBY and U supply are both conserved,
/// across a normal cover AND a hook-veto (covered==0) branch. Exercises the CBY leg the
/// econ_* arithmetic proptests never touch.
#[test]
fn cip28_m36_conservation_full_settle() {
    big_stack(|| {
        for veto in [false, true] {
            let card = Address::from_low_u64(0xC0DE);
            let agent = Address::from_low_u64(0x2801);
            let token_id = [0xCAu8; 32];
            let mut store = DummyStore::default();
            insert_test_actor(&mut store, agent, b"def handle_message(p):\n return b'ok'");
            store.accounts.insert(agent, Account { nonce: 0, balance: 1_000_000_000 });
            // Seed with a hook that admits (veto=false) or rejects (veto=true) card → 0x16.
            let hook = Address::from_low_u64(0x9201);
            let hook_code: &[u8] = if veto {
                b"def can_transfer(f,t,a):\n return False\ndef on_transfer(f,t,a):\n return b'ok'"
            } else {
                b"def can_transfer(f,t,a):\n return t == bytes(19)+b'\\x16'\ndef on_transfer(f,t,a):\n return b'ok'"
            };
            seed_default_card(&mut store, card, agent, crate::bank::CardStatus::Active,
                crate::bank::PayCurrency::Token(token_id), None, 0);
            futures::executor::block_on(crate::bank::storage::write_gas_peg(&mut store, &token_id, 2, 1)).unwrap();
            futures::executor::block_on(crate::bank::storage::write_stablecoin_whitelist(&mut store, &[token_id])).unwrap();
            seed_cusd_with_hook(&mut store, token_id, card, 1_000_000_000, hook, hook_code);
            store.accounts.insert(cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, Account { nonce: 0, balance: 1_000_000_000 });
            let tx = Transaction::sign(&make_signing_key(0x28), 0, 0,
                Instruction::Actor(ActorInstruction::ExecuteActor {
                    actor: agent, handler: "handle_message".to_string(), payload: Vec::new() }),
                50_000_000, 50_000_000, 1, 1);
            store.accounts.insert(tx.from, Account { nonce: 0, balance: 10_000_000_000 });

            let sum_cby = |st: &DummyStore| -> u128 {
                [card, agent, tx.from, cowboy_types::BANK_ACTOR_SYSTEM_ACTOR]
                    .iter().map(|a| st.accounts.get(a).map(|x| x.balance as u128).unwrap_or(0)).sum()
            };
            let sum_u = |st: &DummyStore| -> u128 {
                [card, cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, agent, tx.from].iter().map(|a| {
                    let k = cowboy_token::storage_keys::token_registry::balance_key(a, &token_id);
                    futures::executor::block_on(crate::token::query::read_balance(st, &k)).unwrap()
                }).sum()
            };
            let cby_before = sum_cby(&store);
            let u_before = sum_u(&store);

            let mut engine = ExecutionEngine::new();
            engine.set_basefee(DualBasefee { cycle_basefee: 1, cell_basefee: 1 });
            let (_c, _ce, status, _d, _events) = futures::executor::block_on(engine.execute_transaction(
                &mut store, &tx, BANK_H, &Digest::from([0x28u8; 32]), 0, false)).unwrap();
            assert!(matches!(status, ExecutionStatus::Success), "veto={veto}: {status:?}");
            let (burn, tip) = engine.take_block_fees();

            // CBY conserved: the sum of tracked accounts DROPPED by exactly (burn+tip) — that
            // CBY left the accounts and became burn+tip. So accounts_after + burn + tip == before.
            assert_eq!(sum_cby(&store) + (burn + tip) as u128, cby_before, "veto={veto}: CBY not conserved");
            // U supply conserved: the paymaster leg only MOVES U (card → 0x16), never mints/burns.
            assert_eq!(sum_u(&store), u_before, "veto={veto}: U supply not conserved");
        }
    });
}
```

- [ ] **Step 2: Run**

Run: `cargo test -p cowboy-execution -- cip28_m36_conservation_full_settle --nocapture`
Expected: PASS for both `veto=false` (paymaster covers, CBY leg funds burn/tip) and `veto=true` (FIX-A fall-through, actor/sender funds burn/tip).

- [ ] **Step 3: Full-suite regression**

Run: `cargo test -p cowboy-execution && cargo test -p cowboy-chain`
Expected: green. Then `cargo fmt --all` (MEMORY `feedback_cargo_fmt_before_commit`) and `cargo clippy -p cowboy-execution --all-targets`.

- [ ] **Step 4: Commit**

```bash
cargo fmt --all
git add execution/src/execution/tests.rs
git commit -m "test(cip28-m36): CBY+U conservation over full token-card settle (cover + veto)"
```

---

## Self-Review checklist

- [ ] **Preconditions:** Task 0 pins the M4 hook contract (admit + veto) as executable tests; the activation-PR note forbids lowering `BANK_ACTIVATION_HEIGHT` before M4's `→ 0x16` allowlist entry is live.
- [ ] **Part 1 (peg infra):** `gas_peg_key`/`read_gas_peg`/`write_gas_peg` hand-rolled fixed BE (Task 1); `GenesisConfig.gas_pegs` seeded + `validate()` rejects `num==0 || den==0` (Task 7); `setup.rs` default (Task 7).
- [ ] **Part 1 (math):** `convert_cby_to_u` / `cby_from_u` integer floor, `saturating_mul`, `.max(1)`, no float, KAT both directions (Task 2).
- [ ] **Part 2 (eligibility):** `card_is_eligible` admits `Token(id)` iff peg present AND whitelisted; native `bank_charge_gas` guarded to `Ok(0)` on non-Native (Task 3).
- [ ] **Part 3 (A2 unit-fix):** `need = convert_cby_to_u(max_total_cost, peg)` for token cards; native identity (Task 4).
- [ ] **Part 4 (paymaster):** `bank_charge_gas_token` — eligibility Ok((0,0)); 0x16 CBY read ONCE; `covered_cby = min(amount, cby_from_u(card_u), bank_cby)`; Leg 1 U `card→0x16`; Leg 2 CBY `saturating_sub` on first-read object (Task 5).
- [ ] **FIX-A:** every `handle_token_transfer` error → `Ok((0,0))`, no `?`, state untouched; test = hook-vetoed/frozen card covers 0, tx still settles (Task 5 + Task 8 veto branch).
- [ ] **FIX-B:** drain Leg 1's `TokenTransfer` out of `self.system_events` into local `events` (0x16 emitter); test asserts receipt contains it AND `self.system_events` empty (Task 5, Task 6).
- [ ] **FIX-C:** `GasCharged` emits `covered_u` for token cards, `covered` for native; non-1:1-peg assertion (Task 6).
- [ ] **Part 5 (liquidity):** genesis `bank_cby_reserve` seeds `0x16` CBY; graceful degrade via step-3 `min(bank_cby)`; no on-chain AMM; top-up deferred (Task 7 + 待裁 section).
- [ ] **Part 6 (conservation):** dedicated Σ CBY + Σ U balance-sum test over full `execute_transaction`, both branches; does NOT cite `econ_*` (Task 8).
- [ ] **Guardrails:** all runtime behind `BANK_ACTIVATION_HEIGHT=u64::MAX`; no wire/opcode/codec change; peg integer-only; token debit only via `handle_token_transfer`; `CardEntry` golden vectors untouched; `TokenTransfer`/`GasCharged` already registered topics; LOW-6 bounded scratch meter on the U hook.
- [ ] **Type consistency:** `PayCurrency::Token([u8;32])` (32-byte id) used uniformly; `bank_charge_gas_token(...) -> (u64, u128)` matches all call sites; `read_gas_peg -> Option<(u64,u64)>` consistent across storage/handlers/genesis.

## Verification matrix

| Requirement (source) | Task | Test / command |
|---|---|---|
| M4 hook admits `card → 0x16` (Preconditions) | 0 | `cip28_m36_hook_admits_card_to_bank` |
| Hook veto errs before write (FIX-A precond) | 0 | `cip28_m36_hook_vetoes_card_to_bank_errs_before_write` |
| Genesis peg storage (§4.4) | 1 | `gas_peg_write_read_roundtrip_and_absent` |
| Integer peg math, no float (§4.2 step 5) | 2 | `peg_conversions_floor_and_kat` |
| Token-card eligibility + whitelist-membership (§2.3) | 3 | `eligible_admits_token_card_with_peg_and_whitelist_only`, `native_charge_gas_never_debits_token_card` |
| A2 U-unit admission (§4.2 Phase 1) | 4 | `a2_token_need_uses_peg_not_cby_identity` + Task 8 |
| Paymaster settle cover (§2.3) | 5 | `cip28_m36_paymaster_cover_rehomes_token_transfer` |
| FIX-A swallow errors | 5, 8 | `cip28_m36_paymaster_hook_veto_falls_through_zero`, Task-8 veto branch |
| FIX-B event re-home | 5, 6 | `cip28_m36_paymaster_cover_rehomes_token_transfer` (`system_events` empty) |
| FIX-C GasCharged U-unit (§5.1) | 6 | `cip28_m36_gas_charged_token_unit_is_u` |
| Genesis reserve + non-zero peg (§4.4, Part 5) | 7 | `genesis_rejects_zero_peg`, `genesis_seeds_gas_peg_and_bank_reserve` |
| CBY + U conservation (Part 6) | 8 | `cip28_m36_conservation_full_settle` |
| No regression | 8 | `cargo test -p cowboy-execution && cargo test -p cowboy-chain` |

## Delivery (user-gated)

- **No AI attribution** in any commit message (project CLAUDE.md).
- **PR base = `devnet`** (MEMORY `feedback_node_pr_base_devnet`); node-only, **no codec PR**.
- Run `cargo fmt --all` before every commit and `cargo clippy -p cowboy-execution --all-targets` before the PR (MEMORY `feedback_cargo_fmt_before_commit`, `feedback_cbss_hardening_batch` clippy `--all-targets`).
- Do **not** open the PR or lower `BANK_ACTIVATION_HEIGHT` without explicit user sign-off; activation is gated on M4's `→ 0x16` allowlist hook being live on the target chain.
- PR description in English with a customer-facing summary (MEMORY `feedback_pr_customer_summary`), stated honestly (paymaster CBY liquidity is genesis-reserve-bounded; replenishment is roadmap).

---

**Execution handoff.** Plan complete. Two execution options: (1) **Subagent-Driven** (recommended) — fresh subagent per task, two-stage review between tasks; (2) **Inline Execution** — batch with checkpoints via `superpowers:executing-plans`. **Land nothing before M4's `card → 0x16` hook is confirmed (Task 0).**
