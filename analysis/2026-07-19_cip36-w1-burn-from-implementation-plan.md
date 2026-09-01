# CIP-20 `burn_from` (CIP-36 W1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an immutable, opt-in per-token `burn_from_authority` and an authority-gated `TokenBurnFrom` system instruction that lets exactly that authority burn a third party's balance — the CIP-20 primitive CIP-36 §6.3 `settle_provider` (W3) will wrap for cUSD provider settlement.

**Architecture:** `burn_from` is **authority-gated, not allowance-based** — the caller must equal the token's `burn_from_authority` (mirror `handle_token_mint`'s authority check, *not* `transfer_from`'s allowance). The authority is set once at `TokenCreate`, immutable thereafter, default `None` (existing tokens gain no power). All validation happens **before any state write** because the speculative engine does not roll back partial writes on `Err` (the pay-then-fail conservation gap). The new handler takes an explicit `caller: &Address`, so W3's `settle_provider` handler can invoke it directly with `caller = BankActor` without a PVM host op.

**Tech Stack:** Rust. Two git repos: `cowboy-protocol` (wire codec) and `node` (execution + storage + indexer). commonware-codec positional wire format. QMDB-backed token storage, JSON-serialized `TokenMint`.

---

## Repos, branches, and ordering (READ FIRST)

This is a **cross-repo flag-day change**. `node` pins the codec by git rev: `node/types/Cargo.toml:41` → `cowboy-protocol-codec { git = "…/cowboy-protocol.git", rev = "e238deb76ca3e40cdde87c3b1f98fe39253bc5fc" }`.

- **`cowboy-protocol`** (codec) — has **no `devnet`** branch → PR base = **`main`**. Contains: opcode const, enum variant, encode/encode_size/decode, `TokenCreate` field addition.
- **`node`** — has `devnet` → PR base = **`devnet`** (currently checked out). Contains: handler, dispatch, exhaustive-match arms, events, gas, tests, and the **codec rev bump**.
- **Ordering at merge time:** codec PR merges first → take its merge SHA → bump `node/types/Cargo.toml` rev to that SHA → node PR.
- **During development** (so both sides compile together before the codec PR merges): add a local `[patch]` to `node/Cargo.toml` pointing the codec at the on-disk sibling. Remove it and bump the rev before finalizing (Task 9).

**Wire impact (decision B, 2026-07-19):** `TokenCreate` (opcode 10) is **NOT changed** — modifying it would break the COW-2360 canyon golden-vector hard gate (`tests/golden_vectors.rs` `multi_instruction`), a pinned cross-repo wire contract. Instead, `burn_from_authority` is set by a **separate, additive `TokenSetBurnFromAuthority` instruction (opcode 25)**, handler-enforced set-once (rejects if already `Some`, caller must be the token owner) — same immutability guarantee, zero change to any existing opcode's wire. Both new opcodes (`TokenBurnFrom` 24, `TokenSetBurnFromAuthority` 25) are net-new/additive, so **no golden-vector regeneration and no `wallet` change to `TokenCreate` are required.** (The earlier draft added the field to `TokenCreate`; superseded.)

**Branch name:** `feat/cow-XXXX-cip20-burn-from` in each repo (replace `XXXX` with the Linear key if one exists; otherwise use `feat/cip20-burn-from`).

**Per-repo discipline (from team rules):** run `cargo fmt --all` before every commit; keep `.cargo-target`/build dirs out of git.

---

## File Structure

**`cowboy-protocol` repo:**
- Modify `crates/cowboy-protocol-codec/src/instruction.rs` — opcode const (`SYS_TOKEN_BURN_FROM`), `TokenBurnFrom` variant, `burn_from_authority` field on `TokenCreate`, `sub_type()`, byte-encode, `encode_size`, decode.

**`node` repo:**
- Modify `token/src/types.rs` — `TokenMint.burn_from_authority` field + JSON codec.
- Modify `execution/src/token/events.rs` — `TOPIC_TOKEN_BURNED_FROM` + `encode_burn_from`.
- Modify `execution/src/token/core.rs` — set `burn_from_authority` in `handle_token_create`; add `handle_token_burn_from`.
- Modify `execution/src/execution/system_instruction.rs` — thread `burn_from_authority` through the `TokenCreate` dispatch; add `TokenBurnFrom` dispatch arm.
- Modify `execution/src/execution/cbss_pause_gate.rs` — add `TokenBurnFrom` to the pausable set.
- Modify `storage/src/speculative.rs` — add `TokenBurnFrom` to the exhaustive match.
- Modify `indexer/src/json.rs` — add `TokenBurnFrom` JSON arm.
- Modify `types/src/execution.rs` — codec rev bump (Cargo, actually) + mirror roundtrip tests.
- Modify `node/Cargo.toml` (dev only) — `[patch]` for local codec; and `node/types/Cargo.toml` — rev bump (Task 9).

**Design decisions locked (do not deviate without a reason):**
- Opcode `SYS_TOKEN_BURN_FROM = 24`; opcode `SYS_TOKEN_SET_BURN_FROM_AUTHORITY = 25` (both free slots in the token block 24–29; confirmed unused). **Neither touches `TokenCreate` (opcode 10) — the canyon golden vectors stay byte-identical.**
- `TokenBurnFrom { token_id: [u8;32], account: Address, amount: u128, reason: Vec<u8> }`; `reason` bounded `0..=256` bytes.
- `TokenSetBurnFromAuthority { token_id: [u8;32], authority: Address }` — set-once: handler rejects if `burn_from_authority` is already `Some`, and requires `caller == mint.owner`. `TokenCreate` leaves `burn_from_authority = None`.
- **Reuse** `token_burn_cycles` / `token_burn_cells` gas (YAGNI — no new gas field, no WP-pin-test churn).
- **No new entitlement `Action`** — the `burn_from_authority` field *is* the access control. (A CIP-28 card syscall-kind mapping, if ever needed, is W3, not here.)
- Event amount is **little-endian** to match the surrounding token event encoders (`encode_mint`/`encode_burn` use `to_le_bytes`).

---

## Task 1: Dev setup — local codec patch + branches

**Files:**
- Modify: `node/Cargo.toml` (add `[patch]`, dev-only — reverted in Task 9)

- [ ] **Step 1: Create the codec branch**

```bash
cd /home/ubuntu/workspace/cowboy-protocol
git fetch origin
git checkout main && git pull
git checkout -b feat/cip20-burn-from
```

- [ ] **Step 2: Create the node branch (base devnet)**

```bash
cd /home/ubuntu/workspace/node
git fetch origin
git checkout devnet && git pull
git checkout -b feat/cip20-burn-from
```

- [ ] **Step 3: Point node at the on-disk codec during development**

Append to `node/Cargo.toml` (workspace root, at the end):

```toml
[patch."https://github.com/cowboyinc/cowboy-protocol.git"]
cowboy-protocol-codec = { path = "../cowboy-protocol/crates/cowboy-protocol-codec" }
```

- [ ] **Step 4: Verify the patch resolves (baseline build, no changes yet)**

Run: `cd /home/ubuntu/workspace/node && cargo build -p cowboy-types 2>&1 | tail -5`
Expected: builds successfully, resolving `cowboy-protocol-codec` from the local path.

- [ ] **Step 5: Commit the dev patch (node)**

```bash
cd /home/ubuntu/workspace/node
cargo fmt --all
git add Cargo.toml
git commit -m "chore: dev-only local codec patch for burn_from work (revert before merge)"
```

---

## Task 2: `TokenMint.burn_from_authority` field + JSON codec

**Files:**
- Modify: `node/token/src/types.rs:50-64` (struct), `:66-82` (`TokenMintJson`), `:89-113` (serialize), `:115-158` (deserialize)
- Test: `node/token/src/types.rs` (existing `#[cfg(test)] mod tests`)

- [ ] **Step 1: Write the failing test**

Add to `mod tests` in `node/token/src/types.rs`:

```rust
#[test]
fn token_mint_roundtrip_burn_from_authority() {
    let addr = test_address(7);
    let mint = TokenMint {
        token_id: [9u8; 32],
        name: b"cUSD".to_vec(),
        symbol: b"CUSD".to_vec(),
        decimals: 6,
        total_supply: 1_000_000,
        max_supply: None,
        owner: test_address(1),
        mint_authority: test_address(2),
        freeze_authority: None,
        transfer_hook: Some(test_address(3)),
        burn_from_authority: Some(addr),
        metadata_uri: None,
        created_at: 42,
    };
    let json = serde_json::to_vec(&mint).expect("serialize");
    let restored: TokenMint = serde_json::from_slice(&json).expect("deserialize");
    assert_eq!(restored.burn_from_authority, Some(addr));

    // default / absent → None (back-compat with legacy JSON that lacks the field)
    let legacy = r#"{"token_id":"0000000000000000000000000000000000000000000000000000000000000000","name":"x","symbol":"x","decimals":0,"total_supply":"0","max_supply":null,"owner":"0x0000000000000000000000000000000000000001","mint_authority":"0x0000000000000000000000000000000000000001","freeze_authority":null,"transfer_hook":null,"metadata_uri":null,"created_at":0}"#;
    let restored_legacy: TokenMint = serde_json::from_slice(legacy.as_bytes()).expect("legacy");
    assert_eq!(restored_legacy.burn_from_authority, None);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/workspace/node && cargo test -p cowboy-token token_mint_roundtrip_burn_from_authority 2>&1 | tail -20`
Expected: FAIL to compile — `TokenMint` has no field `burn_from_authority`.

- [ ] **Step 3: Add the struct field**

In `node/token/src/types.rs`, add to `TokenMint` after `transfer_hook` (line 61):

```rust
    pub transfer_hook: Option<Address>,
    /// CIP-36 §11 (CIP-20 amend): set once at creation, immutable, default `None`.
    /// Only this address may call `burn_from` against holders of this token.
    pub burn_from_authority: Option<Address>,
    pub metadata_uri: Option<Vec<u8>>,
```

- [ ] **Step 4: Add the JSON helper field**

In `TokenMintJson` after `transfer_hook` (line 79):

```rust
    transfer_hook: Option<String>,
    #[serde(default)]
    burn_from_authority: Option<String>,
    metadata_uri: Option<String>,
```

(`#[serde(default)]` makes legacy JSON without the field decode to `None`.)

- [ ] **Step 5: Add to serialize**

In `impl Serialize`, after the `transfer_hook` line (line 107):

```rust
            transfer_hook: self.transfer_hook.as_ref().map(|a| a.to_checksum_hex()),
            burn_from_authority: self.burn_from_authority.as_ref().map(|a| a.to_checksum_hex()),
            metadata_uri: self.metadata_uri.as_ref().map(|u| hex::encode(u)),
```

- [ ] **Step 6: Add to deserialize**

In `impl Deserialize`, after the `transfer_hook` binding (line 138), add the parse:

```rust
        let transfer_hook = helper
            .transfer_hook
            .as_deref()
            .map(parse_address)
            .transpose()?;
        let burn_from_authority = helper
            .burn_from_authority
            .as_deref()
            .map(parse_address)
            .transpose()?;
```

And in the returned `Ok(TokenMint { … })` struct literal, add `burn_from_authority,` after `transfer_hook,` (line 154).

- [ ] **Step 7: Fix the other two struct literals in this file**

The two existing tests build `TokenMint { … }` literals (`token_mint_roundtrip_json` ~line 189, `token_mint_roundtrip_minimal` ~line 221). Add `burn_from_authority: None,` after their `transfer_hook: None,` lines so they compile.

- [ ] **Step 8: Run test to verify it passes**

Run: `cd /home/ubuntu/workspace/node && cargo test -p cowboy-token 2>&1 | tail -20`
Expected: PASS (all `cowboy-token` tests, including the new one).

- [ ] **Step 9: Commit**

```bash
cd /home/ubuntu/workspace/node
cargo fmt --all
git add token/src/types.rs
git commit -m "feat(cip20): add immutable burn_from_authority to TokenMint (CIP-36 W1)"
```

---

## Task 3: Codec — `TokenSetBurnFromAuthority` opcode 25 (set-once, additive)

> **Decision B (2026-07-19):** `TokenCreate` is NOT modified (that would break the COW-2360 canyon golden vectors). `burn_from_authority` is set by this separate, purely-additive instruction. Mirror `TokenBurnFrom` structurally (this is a net-new opcode, exactly like Task 4). Confirm opcode `25` is free (token block 24–29 all free per the codec map).

**Files:**
- Modify: `cowboy-protocol/crates/cowboy-protocol-codec/src/instruction.rs` — opcode const (near `SYS_TOKEN_BURN`), variant (near `TokenBurn`), `sub_type()`, byte-encode, `encode_size`, decode
- Test: same file's `#[cfg(test)]` roundtrip tests

- [ ] **Step 1: Write the failing test**

Add near the other token roundtrip tests (use whatever roundtrip helper / address constructor the neighbouring tests use — there may be no `roundtrip_instruction`; if so, mirror an existing token roundtrip test's exact form):

```rust
#[test]
fn test_instruction_system_token_set_burn_from_authority_roundtrip() {
    roundtrip_instruction(Instruction::System(Box::new(
        SystemInstruction::TokenSetBurnFromAuthority {
            token_id: [2u8; 32],
            authority: Address::from_low_u64(9),
        },
    )));
}

#[test]
fn test_token_set_burn_from_authority_opcode_is_25() {
    assert_eq!(
        SystemInstruction::TokenSetBurnFromAuthority {
            token_id: [0u8; 32],
            authority: Address::ZERO,
        }
        .sub_type(),
        SYS_TOKEN_SET_BURN_FROM_AUTHORITY
    );
    assert_eq!(SYS_TOKEN_SET_BURN_FROM_AUTHORITY, 25);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/workspace/cowboy-protocol && cargo test -p cowboy-protocol-codec set_burn_from_authority 2>&1 | tail -20`
Expected: FAIL to compile — no variant, no const.

- [ ] **Step 3: Add the opcode constant**

Near `SYS_TOKEN_BURN` / `SYS_TOKEN_BURN_FROM` (Task 4 adds 24):

```rust
/// CIP-36 §11: set the immutable burn_from_authority once (rejects if already set).
pub const SYS_TOKEN_SET_BURN_FROM_AUTHORITY: u8 = 25;
```

- [ ] **Step 4: Add the enum variant** (near `TokenBurn`):

```rust
    /// CIP-36 §11: set `burn_from_authority` for `token_id`. Handler-enforced
    /// set-once (rejects if already `Some`) and owner-only. Additive opcode —
    /// `TokenCreate` wire is unchanged.
    TokenSetBurnFromAuthority {
        token_id: [u8; 32],
        authority: Address,
    },
```

- [ ] **Step 5: Add the `sub_type()` arm**

```rust
            Self::TokenSetBurnFromAuthority { .. } => SYS_TOKEN_SET_BURN_FROM_AUTHORITY,
```

- [ ] **Step 6: Add the byte-encode arm** (mirror `TokenBurn`'s leading-opcode-byte convention):

```rust
                    SystemInstruction::TokenSetBurnFromAuthority { token_id, authority } => {
                        SYS_TOKEN_SET_BURN_FROM_AUTHORITY.write(writer);
                        token_id.write(writer);
                        authority.write(writer);
                    }
```

- [ ] **Step 7: Add the `encode_size` arm**:

```rust
                SystemInstruction::TokenSetBurnFromAuthority { token_id, authority } => {
                    token_id.encode_size() + authority.encode_size()
                }
```

(Match how the neighbouring `TokenBurn` size arm accounts for the leading opcode byte — do not diverge on the `+ 1`.)

- [ ] **Step 8: Add the decode arm**:

```rust
                    25 => Self::System(Box::new(SystemInstruction::TokenSetBurnFromAuthority {
                        token_id: <[u8; 32]>::read(reader)?,
                        authority: Address::read(reader)?,
                    })),
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd /home/ubuntu/workspace/cowboy-protocol && cargo test -p cowboy-protocol-codec 2>&1 | tail -20`
Expected: PASS (roundtrip + opcode assertion + full suite; `#[deny(unreachable_patterns)]` confirms 25 unique). The canyon golden-vector test (`--features signing`) is UNAFFECTED because `TokenCreate` did not change — sanity-check it: `cargo test -p cowboy-protocol-codec --features signing golden 2>&1 | tail -10` → PASS.

- [ ] **Step 10: Commit (codec repo)**

```bash
cd /home/ubuntu/workspace/cowboy-protocol
cargo fmt --all
git add crates/cowboy-protocol-codec/src/instruction.rs
git commit -m "feat(cip20): add TokenSetBurnFromAuthority system instruction, opcode 25 (CIP-36 W1)"
```

---

## Task 4: Codec — `TokenBurnFrom` opcode + variant + encode/decode

**Files:**
- Modify: `cowboy-protocol/crates/cowboy-protocol-codec/src/instruction.rs` — opcode const (~39), variant (~540 after `TokenBurn`), `sub_type()` (~1443), byte-encode (~2008), `encode_size` (~4671), decode (~3469)

- [ ] **Step 1: Write the failing test**

Add near the other token roundtrip tests:

```rust
#[test]
fn test_instruction_system_token_burn_from_roundtrip() {
    roundtrip_instruction(Instruction::System(Box::new(
        SystemInstruction::TokenBurnFrom {
            token_id: [2u8; 32],
            account: Address::from_low_u64(5),
            amount: 50,
            reason: b"settlement:abc123".to_vec(),
        },
    )));
}

#[test]
fn test_token_burn_from_opcode_is_24() {
    assert_eq!(
        SystemInstruction::TokenBurnFrom {
            token_id: [0u8; 32],
            account: Address::ZERO,
            amount: 0,
            reason: Vec::new(),
        }
        .sub_type(),
        SYS_TOKEN_BURN_FROM
    );
    assert_eq!(SYS_TOKEN_BURN_FROM, 24);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/workspace/cowboy-protocol && cargo test -p cowboy-protocol-codec token_burn_from 2>&1 | tail -20`
Expected: FAIL to compile — no `TokenBurnFrom` variant, no `SYS_TOKEN_BURN_FROM`.

- [ ] **Step 3: Add the opcode constant**

After `pub const SYS_TOKEN_BURN: u8 = 15;` (instruction.rs:39):

```rust
pub const SYS_TOKEN_BURN: u8 = 15;
/// CIP-36 §11: authority-gated burn of a third party's balance. Free slot in
/// the token block (10–23). Uniqueness enforced by `#[deny(unreachable_patterns)]`
/// on the `Read for Instruction` impl.
pub const SYS_TOKEN_BURN_FROM: u8 = 24;
```

- [ ] **Step 4: Add the enum variant**

After the `TokenBurn { token_id, amount }` variant (~540):

```rust
    TokenBurn {
        token_id: [u8; 32],
        amount: u128,
    },
    /// CIP-36 §6.3 / §11: burn `amount` from `account`, callable only by the
    /// token's `burn_from_authority`. `reason` (≤256 bytes) is carried into the
    /// emitted event / settlement idempotency key.
    TokenBurnFrom {
        token_id: [u8; 32],
        account: Address,
        amount: u128,
        reason: Vec<u8>,
    },
```

- [ ] **Step 5: Add the `sub_type()` arm**

After `Self::TokenBurn { .. } => SYS_TOKEN_BURN,` (~1443):

```rust
            Self::TokenBurn { .. } => SYS_TOKEN_BURN,
            Self::TokenBurnFrom { .. } => SYS_TOKEN_BURN_FROM,
```

- [ ] **Step 6: Add the byte-encode arm**

After the `SystemInstruction::TokenBurn { … }` write arm (~2008):

```rust
                    SystemInstruction::TokenBurnFrom {
                        token_id,
                        account,
                        amount,
                        reason,
                    } => {
                        SYS_TOKEN_BURN_FROM.write(writer);
                        token_id.write(writer);
                        account.write(writer);
                        amount.write(writer);
                        reason.write(writer);
                    }
```

- [ ] **Step 7: Add the `encode_size` arm**

After the `TokenBurn` size arm (~4671):

```rust
                SystemInstruction::TokenBurnFrom {
                    token_id,
                    account,
                    amount,
                    reason,
                } => {
                    token_id.encode_size()
                        + account.encode_size()
                        + amount.encode_size()
                        + reason.encode_size()
                }
```

(The opcode tag byte is accounted for by the surrounding impl exactly as it is for `TokenBurn` — match how the `TokenBurn` arm handles the leading byte; do not add or drop a `+ 1` differently from the neighbor.)

- [ ] **Step 8: Add the decode arm**

After the `15 => … TokenBurn …` arm (~3469):

```rust
                    24 => Self::System(Box::new(SystemInstruction::TokenBurnFrom {
                        token_id: <[u8; 32]>::read(reader)?,
                        account: Address::read(reader)?,
                        amount: u128::read(reader)?,
                        reason: Vec::<u8>::read_cfg(reader, &(RangeCfg::from(0..=256), ()))?,
                    })),
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd /home/ubuntu/workspace/cowboy-protocol && cargo test -p cowboy-protocol-codec 2>&1 | tail -20`
Expected: PASS (roundtrip + opcode assertion + whole codec suite; `#[deny(unreachable_patterns)]` confirms 24 is unique).

- [ ] **Step 10: Commit (codec repo)**

```bash
cd /home/ubuntu/workspace/cowboy-protocol
cargo fmt --all
git add crates/cowboy-protocol-codec/src/instruction.rs
git commit -m "feat(cip20): add TokenBurnFrom system instruction, opcode 24 (CIP-36 W1)"
```

---

## Task 5: Node event encoder — `encode_burn_from`

**Files:**
- Modify: `node/execution/src/token/events.rs:19` (topic), `:44-50` (after `encode_burn`)
- Test: `node/execution/src/token/events.rs` (add a `#[cfg(test)]` if none, else a unit test inline)

- [ ] **Step 1: Write the failing test**

Add to `node/execution/src/token/events.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encode_burn_from_layout() {
        let token_id = [1u8; 32];
        let authority = Address::from_low_u64(2);
        let account = Address::from_low_u64(3);
        let out = encode_burn_from(&token_id, &authority, &account, 7u128, b"r");
        // 32 + 20 + 20 + 16 + 1(reason) = 89
        assert_eq!(out.len(), 89);
        assert_eq!(&out[0..32], &token_id);
        assert_eq!(&out[32..52], authority.as_ref());
        assert_eq!(&out[52..72], account.as_ref());
        assert_eq!(&out[72..88], &7u128.to_le_bytes());
        assert_eq!(&out[88..89], b"r");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/workspace/node && cargo test -p cowboy-execution encode_burn_from_layout 2>&1 | tail -20`
Expected: FAIL to compile — `encode_burn_from` not found.

- [ ] **Step 3: Add topic + encoder**

Add the topic after `TOPIC_TOKEN_BURNED` (events.rs:15):

```rust
pub const TOPIC_TOKEN_BURNED: &str = "TokenBurned";
pub const TOPIC_TOKEN_BURNED_FROM: &str = "TokenBurnedFrom";
```

Add the encoder after `encode_burn` (events.rs:50):

```rust
/// `TokenBurnedFrom` (CIP-36 §6.3): token_id(32) + authority(20) + account(20)
/// + amount(16 LE) + reason(raw, trailing). Amount is LE to match the sibling
/// token encoders (`encode_mint`/`encode_burn`).
pub fn encode_burn_from(
    token_id: &[u8; 32],
    authority: &Address,
    account: &Address,
    amount: u128,
    reason: &[u8],
) -> Vec<u8> {
    let mut buf = Vec::with_capacity(88 + reason.len());
    buf.extend_from_slice(token_id);
    buf.extend_from_slice(authority.as_ref());
    buf.extend_from_slice(account.as_ref());
    buf.extend_from_slice(&amount.to_le_bytes());
    buf.extend_from_slice(reason);
    buf
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ubuntu/workspace/node && cargo test -p cowboy-execution encode_burn_from_layout 2>&1 | tail -20`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/workspace/node
cargo fmt --all
git add execution/src/token/events.rs
git commit -m "feat(cip20): add TokenBurnedFrom event encoder (CIP-36 W1)"
```

---

## Task 6: Node handlers — `handle_token_burn_from` + `handle_token_set_burn_from_authority`

**Files:**
- Modify: `node/execution/src/token/core.rs` — add `burn_from_authority: None` to the `handle_token_create` literal (~124); add `handle_token_set_burn_from_authority`; add `handle_token_burn_from` (after `handle_token_burn`, ~769)
- Test: `node/execution/src/token/core.rs` (existing `#[cfg(test)] mod tests`)

- [ ] **Step 1: Default `burn_from_authority` to `None` in `handle_token_create`**

`handle_token_create` gets **no new parameter** (decision B — the authority is set by a separate instruction, not at create). Just make the existing `TokenMint { … }` literal (~124) compile against the T2 struct field by adding `burn_from_authority: None,` after `transfer_hook: transfer_hook.cloned(),`:

```rust
            transfer_hook: transfer_hook.cloned(),
            burn_from_authority: None,
            metadata_uri: metadata_uri.map(|u| u.to_vec()),
```

- [ ] **Step 1b: Add `handle_token_set_burn_from_authority` (set-once, owner-only)**

Add near `handle_token_create`. Test-drive it first (add these to `mod tests`, mirroring an existing create/mint test's setup boilerplate):

```rust
#[tokio::test]
async fn set_burn_from_authority_owner_once_then_immutable() {
    // create a token (owner = tx.from = `owner`), burn_from_authority starts None.
    let owner = test_addr(0x1);
    let bank = test_addr(0xB);
    // … create token owned by `owner` …
    engine.handle_token_set_burn_from_authority(&mut store, &token_id, &bank, &owner).await.expect("first set");
    let mint = get_token_mint(&store, &token_id).await.unwrap().unwrap();
    assert_eq!(mint.burn_from_authority, Some(bank));
    // second set → rejected (immutable)
    let err = engine.handle_token_set_burn_from_authority(&mut store, &token_id, &owner, &owner).await.unwrap_err();
    assert!(matches!(err, ExecutionError::TokenUnauthorized) || matches!(err, ExecutionError::InvalidData));
}

#[tokio::test]
async fn set_burn_from_authority_non_owner_rejected() {
    let owner = test_addr(0x1);
    let attacker = test_addr(0xA);
    let bank = test_addr(0xB);
    // … create token owned by `owner` …
    let err = engine.handle_token_set_burn_from_authority(&mut store, &token_id, &bank, &attacker).await.unwrap_err();
    assert!(matches!(err, ExecutionError::TokenUnauthorized));
    let mint = get_token_mint(&store, &token_id).await.unwrap().unwrap();
    assert_eq!(mint.burn_from_authority, None, "no write on unauthorized set");
}
```

Then implement (place near `handle_token_burn`):

```rust
    /// CIP-36 §11: set the token's immutable `burn_from_authority` exactly once.
    /// Owner-only; rejects if already set (immutability). Check-then-apply.
    pub async fn handle_token_set_burn_from_authority<S: StateStore>(
        &mut self,
        store: &mut S,
        token_id: &[u8; 32],
        authority: &Address,
        caller: &Address,
        // NOTE: reuse an existing token-admin gas cost (e.g. self.gas_costs.token_mint_*),
        // matching how sibling admin ops charge; do not invent a new gas field.
    ) -> Result<(), ExecutionError> {
        let mut mint = get_token_mint(store, token_id)
            .await
            .map_err(ExecutionError::from_store)?
            .ok_or(ExecutionError::TokenNotFound)?;
        // Owner-only.
        if mint.owner != *caller {
            return Err(ExecutionError::TokenUnauthorized);
        }
        // Set-once: reject if already set (immutable).
        if mint.burn_from_authority.is_some() {
            return Err(ExecutionError::TokenUnauthorized);
        }
        mint.burn_from_authority = Some(*authority);
        put_token_mint(store, token_id, &mint)
            .await
            .map_err(ExecutionError::from_store)?;
        Ok(())
    }
```

Note the handler signature here omits `gas_meters` for brevity — **match the real signature convention of the sibling handlers in this file** (they all take `gas_meters: &mut DualGasMeters` and consume a cost first). Add `gas_meters` and a `gas_meters.cycles.consume(self.gas_costs.token_mint_cycles)?` / cells line at the top, mirroring `handle_token_mint`. Thread `gas_meters` through the test calls and the Task 7 dispatch accordingly.

- [ ] **Step 2: Write the failing test (handler behavior)**

Add to `mod tests` in `core.rs`. Use the existing test harness/helpers in that module (mirror an existing `handle_token_burn` or `handle_token_mint` test for store/engine setup — copy its setup boilerplate verbatim rather than inventing helpers):

```rust
#[tokio::test]
async fn burn_from_authorized_decrements_supply_and_balance() {
    // ARRANGE: create a token whose burn_from_authority = `bank`, mint `100` to `holder`.
    // (Copy the create+mint setup from an existing test in this module.)
    let bank = test_addr(0xB);
    let holder = test_addr(0xH);
    // … create token with burn_from_authority = Some(bank), mint 100 to holder …

    // ACT: bank burns 40 from holder.
    engine
        .handle_token_burn_from(&mut store, &token_id, &holder, 40, b"settle:1", &bank, &mut meters)
        .await
        .expect("authorized burn_from");

    // ASSERT: holder balance 60, total_supply reduced by 40, TokenBurnedFrom event emitted.
    let bal = read_balance(&store, &token_registry::balance_key(&holder, &token_id)).await.unwrap();
    assert_eq!(bal, 60);
    let mint = get_token_mint(&store, &token_id).await.unwrap().unwrap();
    assert_eq!(mint.total_supply, 60);
    assert!(engine.system_events.iter().any(|(t, _)| t == cip20_events::TOPIC_TOKEN_BURNED_FROM));
}

#[tokio::test]
async fn burn_from_wrong_caller_rejected_no_write() {
    // token burn_from_authority = Some(bank); attacker != bank tries to burn.
    let attacker = test_addr(0xA);
    let holder = test_addr(0xH);
    // … create with burn_from_authority = Some(bank), mint 100 to holder …
    let before = read_balance(&store, &token_registry::balance_key(&holder, &token_id)).await.unwrap();
    let err = engine
        .handle_token_burn_from(&mut store, &token_id, &holder, 40, b"x", &attacker, &mut meters)
        .await
        .unwrap_err();
    assert!(matches!(err, ExecutionError::TokenUnauthorized));
    let after = read_balance(&store, &token_registry::balance_key(&holder, &token_id)).await.unwrap();
    assert_eq!(before, after, "no balance change on unauthorized burn");
}

#[tokio::test]
async fn burn_from_none_authority_always_rejected() {
    // token created with burn_from_authority = None → nobody can burn_from, not even the owner.
    let owner = test_addr(0x1);
    let holder = test_addr(0xH);
    // … create with burn_from_authority = None, mint 100 to holder …
    let err = engine
        .handle_token_burn_from(&mut store, &token_id, &holder, 10, b"x", &owner, &mut meters)
        .await
        .unwrap_err();
    assert!(matches!(err, ExecutionError::TokenUnauthorized));
}

#[tokio::test]
async fn burn_from_insolvent_rejected_no_write() {
    // bank tries to burn 200 from holder who has 100 → reject, zero writes.
    let bank = test_addr(0xB);
    let holder = test_addr(0xH);
    // … create with burn_from_authority = Some(bank), mint 100 to holder …
    let mint_before = get_token_mint(&store, &token_id).await.unwrap().unwrap().total_supply;
    let err = engine
        .handle_token_burn_from(&mut store, &token_id, &holder, 200, b"x", &bank, &mut meters)
        .await
        .unwrap_err();
    assert!(matches!(err, ExecutionError::TokenInsufficientBalance));
    let mint_after = get_token_mint(&store, &token_id).await.unwrap().unwrap().total_supply;
    assert_eq!(mint_before, mint_after, "total_supply untouched on insolvent burn");
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/ubuntu/workspace/node && cargo test -p cowboy-execution burn_from 2>&1 | tail -20`
Expected: FAIL to compile — `handle_token_burn_from` not found.

- [ ] **Step 4: Implement the handler (check-then-apply)**

Add after `handle_token_burn` (core.rs ~769):

```rust
    /// CIP-36 §6.3 / §11: burn `amount` of `token_id` from `account`, authorized
    /// only by the token's immutable `burn_from_authority`. Validates authority,
    /// reason bound, and `amount <= balance(account)` (which also guarantees
    /// `amount <= total_supply`) BEFORE any write — the speculative engine does
    /// not roll back partial writes on `Err`, so a mid-handler trap would break
    /// supply/balance conservation. Reusable by W3 `settle_provider` with
    /// `caller = BankActor`.
    #[allow(clippy::too_many_arguments)]
    pub async fn handle_token_burn_from<S: StateStore>(
        &mut self,
        store: &mut S,
        token_id: &[u8; 32],
        account: &Address,
        amount: u128,
        reason: &[u8],
        caller: &Address,
        gas_meters: &mut DualGasMeters,
    ) -> Result<(), ExecutionError> {
        // Reuse the plain-burn gas schedule (same storage shape; one extra read).
        gas_meters.cycles.consume(self.gas_costs.token_burn_cycles)?;
        gas_meters.cells.consume(self.gas_costs.token_burn_cells)?;

        // ── validate (no writes past this block) ──────────────────────────────
        if amount == 0 {
            return Err(ExecutionError::InvalidData);
        }
        if reason.len() > 256 {
            return Err(ExecutionError::InvalidData);
        }

        let mut mint = get_token_mint(store, token_id)
            .await
            .map_err(ExecutionError::from_store)?
            .ok_or(ExecutionError::TokenNotFound)?;

        // Authority gate: default-None tokens can never be burn_from'd.
        if mint.burn_from_authority != Some(*caller) {
            return Err(ExecutionError::TokenUnauthorized);
        }

        let balance_key = token_registry::balance_key(account, token_id);
        let balance = read_balance(store, &balance_key)
            .await
            .map_err(ExecutionError::from_store)?;
        if balance < amount {
            return Err(ExecutionError::TokenInsufficientBalance);
        }

        // ── apply (all preconditions proven above) ────────────────────────────
        // balance <= total_supply always holds, so checked_sub cannot underflow;
        // use it anyway so any invariant break surfaces as an error, not a wrap.
        mint.total_supply = mint
            .total_supply
            .checked_sub(amount)
            .ok_or(ExecutionError::InvalidData)?;
        put_token_mint(store, token_id, &mint)
            .await
            .map_err(ExecutionError::from_store)?;
        write_balance(store, &balance_key, balance - amount)
            .await
            .map_err(ExecutionError::from_store)?;

        let authority = *caller;
        self.system_events.push((
            cip20_events::TOPIC_TOKEN_BURNED_FROM.to_string(),
            cip20_events::encode_burn_from(token_id, &authority, account, amount, reason),
        ));

        Ok(())
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/ubuntu/workspace/node && cargo test -p cowboy-execution burn_from 2>&1 | tail -30`
Expected: PASS (all four handler tests). If it fails to compile on the dispatch call site, do Task 7 Step 1 now, then re-run.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/workspace/node
cargo fmt --all
git add execution/src/token/core.rs
git commit -m "feat(cip20): handle_token_burn_from — authority-gated, check-then-apply (CIP-36 W1)"
```

---

## Task 7: Node dispatch + exhaustive-match arms

**Files:**
- Modify: `node/execution/src/execution/system_instruction.rs` — after the `TokenBurn` arm (~:511) add `TokenBurnFrom` AND `TokenSetBurnFromAuthority` dispatch arms. **The `TokenCreate` dispatch is UNCHANGED (decision B — no new field on `TokenCreate`).**
- Modify: `node/execution/src/execution/cbss_pause_gate.rs:85`
- Modify: `node/storage/src/speculative.rs:419`
- Modify: `node/indexer/src/json.rs:597`

- [ ] **Step 1: Add the two new dispatch arms**

After the `TokenBurn` arm (system_instruction.rs ~508-511) add both new opcodes. (Match the exact `gas_meters` threading of the sibling arms — `handle_token_burn_from` takes `gas_meters`; `handle_token_set_burn_from_authority` takes it too per Task 6.)

```rust
            cowboy_types::SystemInstruction::TokenBurn { token_id, amount } => self
                .handle_token_burn(store, token_id, *amount, &tx.from, gas_meters)
                .await
                .map(|_| None),
            cowboy_types::SystemInstruction::TokenBurnFrom {
                token_id,
                account,
                amount,
                reason,
            } => self
                .handle_token_burn_from(store, token_id, account, *amount, reason, &tx.from, gas_meters)
                .await
                .map(|_| None),
            cowboy_types::SystemInstruction::TokenSetBurnFromAuthority { token_id, authority } => self
                .handle_token_set_burn_from_authority(store, token_id, authority, &tx.from, gas_meters)
                .await
                .map(|_| None),
```

(No change to the `TokenCreate` arm — it keeps its existing 7-field destructure and call.)

- [ ] **Step 3: Write the failing routing test**

Add to the `system_instruction.rs` test module (mirror the existing TokenCreate routing test at ~9414 for setup):

```rust
#[tokio::test]
async fn token_burn_from_routes_to_handler() {
    // Create a token with burn_from_authority = tx.from (the bank EOA), mint to a holder,
    // then submit a TokenBurnFrom tx from the bank and assert the holder balance drops.
    // (Reuse the create/mint routing helpers already in this test module.)
    let inst = SystemInstruction::TokenBurnFrom {
        token_id,
        account: holder,
        amount: 30,
        reason: b"settle:1".to_vec(),
    };
    // … execute the instruction through the same path the TokenCreate routing test uses …
    // ASSERT holder balance decreased by 30.
}
```

- [ ] **Step 4: Add the pause-gate arms**

In `cbss_pause_gate.rs:85`, add BOTH new opcodes to the `|`-chain of pausable token instructions (right after `TokenBurn`):

```rust
            | SystemInstruction::TokenBurn { .. }
            | SystemInstruction::TokenBurnFrom { .. }
            | SystemInstruction::TokenSetBurnFromAuthority { .. }
```

- [ ] **Step 5: Add the speculative-storage arms**

In `speculative.rs:419`, add both alongside `TokenBurn`:

```rust
            | SystemInstruction::TokenBurn { .. }
            | SystemInstruction::TokenBurnFrom { .. }
            | SystemInstruction::TokenSetBurnFromAuthority { .. }
```

- [ ] **Step 6: Add the indexer JSON arms**

In `indexer/src/json.rs:597`, after the `TokenBurn` arm, add both (mirror its shape; `reason` as hex):

```rust
        SystemInstruction::TokenBurnFrom { token_id, account, amount, reason } => {
            json!({
                "type": "token_burn_from",
                "token_id": hex::encode(token_id),
                "account": account.to_checksum_hex(),
                "amount": amount.to_string(),
                "reason": hex::encode(reason),
            })
        }
        SystemInstruction::TokenSetBurnFromAuthority { token_id, authority } => {
            json!({
                "type": "token_set_burn_from_authority",
                "token_id": hex::encode(token_id),
                "authority": authority.to_checksum_hex(),
            })
        }
```

(Match the exact `json!`/field style of the neighboring `TokenBurn` arm — key casing, address formatting helper, and amount stringification. If the indexer match is non-exhaustive it will fail to compile until BOTH arms exist.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /home/ubuntu/workspace/node && cargo test -p cowboy-execution token_burn_from 2>&1 | tail -30`
Expected: PASS (routing test + handler tests).

- [ ] **Step 8: Commit**

```bash
cd /home/ubuntu/workspace/node
cargo fmt --all
git add execution/src/execution/system_instruction.rs execution/src/execution/cbss_pause_gate.rs storage/src/speculative.rs indexer/src/json.rs
git commit -m "feat(cip20): route TokenBurnFrom to handler; cover pause-gate/speculative/indexer (CIP-36 W1)"
```

---

## Task 8: Mirror node-side codec tests + full workspace green

**Files:**
- Modify: `node/types/src/execution.rs` — add `TokenBurnFrom` roundtrip + sub_type mirror tests (mirror `test_instruction_system_token_burn_roundtrip` at :3334 and the `sub_type` assertion at :4806)

- [ ] **Step 1: Add mirror tests in node/types**

```rust
#[test]
fn test_instruction_system_token_burn_from_roundtrip() {
    roundtrip_instruction(Instruction::System(Box::new(
        SystemInstruction::TokenBurnFrom {
            token_id: [2u8; 32],
            account: Address::from_low_u64(5),
            amount: 50,
            reason: b"settle:1".to_vec(),
        },
    )));
}
```

And in the `sub_type` test block (~4806), after the `TokenBurn` assertion:

```rust
    assert_eq!(
        SystemInstruction::TokenBurnFrom {
            token_id: [0u8; 32],
            account: Address::ZERO,
            amount: 0,
            reason: Vec::new(),
        }
        .sub_type(),
        SYS_TOKEN_BURN_FROM
    );
```

- [ ] **Step 2: Run the whole node test suite**

Run: `cd /home/ubuntu/workspace/node && cargo test --workspace 2>&1 | tail -30`
Expected: PASS. Watch specifically for exhaustive-match compile errors in any crate that matches `SystemInstruction` — if a crate fails to compile with a "non-exhaustive patterns" or "unreachable pattern" error, add the missing `TokenBurnFrom` arm there (the compiler names the file:line) and re-run.

- [ ] **Step 3: Clippy (matches the CI gate)**

Run: `cd /home/ubuntu/workspace/node && cargo clippy --workspace --all-targets 2>&1 | tail -30`
Expected: no warnings introduced by these changes.

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/workspace/node
cargo fmt --all
git add types/src/execution.rs
git commit -m "test(cip20): mirror TokenBurnFrom roundtrip + sub_type in node/types (CIP-36 W1)"
```

---

## Task 9: Cross-repo finalize — codec rev pin + downstream checks

**Files:**
- Modify: `node/Cargo.toml` (remove dev `[patch]`), `node/types/Cargo.toml:41` (bump rev)

- [ ] **Step 1: Push the codec branch and open its PR (base main)**

```bash
cd /home/ubuntu/workspace/cowboy-protocol
git push -u origin feat/cip20-burn-from
gh pr create --base main --title "CIP-20 burn_from: TokenBurnFrom opcode + burn_from_authority on TokenCreate" \
  --body "CIP-36 W1 codec half. Adds SYS_TOKEN_BURN_FROM=24, TokenBurnFrom variant, and an immutable burn_from_authority field on TokenCreate (wire change to opcode 10 — flag-day). Consumed by node PR (CIP-36 W1). Customer summary: enables an authority-gated burn primitive that cUSD provider settlement (CIP-36 §6.3) will wrap; no existing token gains any power (default None)."
```

- [ ] **Step 2: After the codec PR merges, capture its merge SHA**

```bash
cd /home/ubuntu/workspace/cowboy-protocol
git checkout main && git pull
git rev-parse HEAD    # ← this is the new rev to pin
```

- [ ] **Step 3: Remove the dev patch and bump the rev**

In `node/Cargo.toml`, delete the `[patch."https://github.com/cowboyinc/cowboy-protocol.git"]` block added in Task 1.
In `node/types/Cargo.toml:41`, replace `rev = "e238deb76ca3e40cdde87c3b1f98fe39253bc5fc"` with the SHA from Step 2.

- [ ] **Step 4: Verify node builds against the pinned (merged) codec**

Run: `cd /home/ubuntu/workspace/node && cargo build --workspace 2>&1 | tail -10 && cargo test --workspace 2>&1 | tail -15`
Expected: builds and tests pass against the real git-pinned codec (no local patch).

- [ ] **Step 5: Downstream wire-compat check — wallet**

Check whether the JS `wallet` encodes `TokenCreate` (it changed shape):

```bash
grep -rniE "TokenCreate|token_create|opcode.*10\b" /home/ubuntu/workspace/wallet/ | head
```

If `wallet` builds `TokenCreate` transactions, it MUST add the trailing tagged `burn_from_authority` field to stay byte-compatible, shipped on the same flag-day. If it does not encode `TokenCreate`, record "no wallet change needed for W1" in the PR description. (Either way, `TokenBurnFrom` is net-new and needs no retro wallet change.)

- [ ] **Step 6: Push node branch and open its PR (base devnet)**

```bash
cd /home/ubuntu/workspace/node
git add Cargo.toml types/Cargo.toml
cargo fmt --all
git commit -m "chore: pin merged cowboy-protocol codec rev for burn_from (CIP-36 W1)"
git push -u origin feat/cip20-burn-from
gh pr create --base devnet --title "CIP-20 burn_from (CIP-36 W1): authority-gated third-party burn" \
  --body "$(cat <<'EOF'
Implements the CIP-20 `burn_from` primitive that CIP-36 §6.3 requires (foundation for W2 settle_provider and W3 BankActor cUSD settlement).

**What:** immutable per-token `burn_from_authority` (set once at TokenCreate, default None) + `TokenBurnFrom` system instruction (opcode 24) callable only by that authority; check-then-apply (validates authority + solvency before any write, per the no-rollback engine); emits `TokenBurnedFrom`.

**Consensus / flag-day:** yes — new opcode + TokenCreate wire change + new event into logs/receipt root. Coordinate a single activation with the codec pin.

**Customer summary:** lets a designated authority (e.g. the bank/settlement actor) burn a token from a holder's account — the on-chain half of "settle provider revenue to fiat". Existing tokens are unaffected (authority defaults to None; nobody can burn_from them).
EOF
)"
```

- [ ] **Step 7: Post-push sanity**

```bash
gh pr view --json url,baseRefName,commits | tail
```
Expected: node PR base = `devnet`, codec PR base = `main`, both green in CI.

---

## Self-Review (completed against CIP-36 §6.3 / §11)

- **Spec coverage** — CIP-36 §11 CIP-20 amend: (a) immutable `burn_from_authority` default None → Task 2 (struct) + Task 3 (TokenCreate wire) + Task 6 Step 1 (set at create). (b) `burn_from(token, account, amount, reason)` validating authority + reason length + `amount ≤ balance(account)` before any mutation, then decrement balance **and** total_supply, emit `Burn{token,authority,account,amount,reason}` → Task 4 (opcode/variant) + Task 5 (event) + Task 6 Step 4 (handler). (c) callable only by the authority → Task 6 authority gate + tests. (d) idempotency/consumed-set lives in the CIP-28 `settle_provider` wrapper, **not** here → explicitly out of W1 scope (W3); the handler's reusable `caller` param is the seam.
- **Placeholder scan** — handler + all codec arms are complete code. The four handler tests and the routing test carry `// … reuse existing setup …` comments *inside test bodies only*, because the module's store/engine bootstrap helpers are private and must be copied verbatim from a neighboring test; the asserts and the ACT calls are fully spelled out. No product-code placeholders.
- **Type consistency** — `TokenBurnFrom { token_id, account, amount, reason }` field names identical across variant def (T4), sub_type (T4), encode (T4), decode (T4), dispatch (T7), handler call (T7). `handle_token_burn_from(store, token_id, account, amount, reason, caller, gas_meters)` signature identical between definition (T6) and call site (T7). `encode_burn_from(token_id, authority, account, amount, reason)` identical between events (T5) and handler (T6). Opcode `24` / `SYS_TOKEN_BURN_FROM` consistent across const (T4), encode, decode, assertion tests.

## Execution Handoff

Plan saved to `refs/analysis/2026-07-19_cip36-w1-burn-from-implementation-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks. Note the cross-repo ordering: Tasks 3–4 land in `cowboy-protocol`; Tasks 2,5–8 in `node` (compiling via the Task 1 local `[patch]`); Task 9 finalizes the rev pin.
2. **Inline Execution** — execute in this session with checkpoints.

Which approach?
