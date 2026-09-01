# CIP-28 BankActor M4 — Fiat Issuance & Settlement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the CIP-28 fiat bridge (mint from `FiatMintVoucher`), CIP-36 provider settlement (`settle_provider`), and gateway-signed agent-consent for card issuance (`IssuancePrincipalVoucher`), all supply-conserving through CIP-20 mint/burn accounting, seeded exercisable at a re-genesis.

**Architecture:** M4 is a **re-genesis milestone** (fiat signer + CUSD seeded at genesis; devnet re-genesis'd exactly as M1/M2/M3 were). That makes a breaking wire-shape change to opcode 200 `BankIssueCard` acceptable. Two new BankActor opcodes (210 `MintFromFiatVoucher`, 211 `settle_provider`) are added; opcode 200's wire shape is extended with a compliance-gateway-signed voucher. All value movement routes through the existing CIP-20 `handle_token_mint` / `handle_token_burn_from` accounting (never a raw balance write), so `total_supply` stays conserved. Signature verification is deterministic secp256k1 recovery over `keccak256(domain ‖ canonical fixed-layout preimage)`, mirroring the existing runner-registration verifier and the BankActor hand-rolled BE codec. New event topics feed `receipt_root` (flag-day) and are registered in the consensus-topic guard.

**Tech Stack:** Rust. Two repos: **`cowboy-protocol`** (wire codec — `crates/cowboy-protocol-codec/src/instruction.rs`, commonware-codec `Read`/`Write`/`EncodeSize`, golden round-trip vectors) and **`node`** (execution, storage, chain, genesis, validator; pins the codec by git rev). secp256k1 via `k256`, keccak via `Keccak256`/`cowboy_types::keccak256`.

---

## Deep-audit revisions (BINDING — supersede any conflicting task text below)

Three adversarial plan-audit lenses (opcode-200 gating/decode-fork; mint/burn/voucher; settle/finalize/overall) ran against the draft. The codec-additive mechanics, authorization, cross-repo finalize (re-pin to merged-main sha), and supply-conserving mint/burn all audited **SOUND**. The rulings below fix one **BLOCK**, two **HIGH**, and several MED/LOW defects. **They override the "Architecture" paragraph above and Scope decision §1.**

- **RV-1 (BLOCK → the top structural change). Do NOT reshape opcode 200. Add an additive, gated opcode 212 `BankIssueCardV2` instead.** Reshaping a live, decodable, ungated opcode (200 has been on-chain since M1) is a decode-fork of the exact M1 A4 class: old-code and new-code nodes both decode 200 but differently → divergent `state_root`, and **no gate can protect it** (the `do_verify` wholesale-reject only works for *additive* opcodes a legacy node cannot decode). The "re-genesis absorbs it" claim is unsafe — the node PR bases on the *running* `devnet` branch and nothing couples the merge to a coordinated network wipe; per the #934 doctrine, in-place rolling upgrades are the normal landing mode. **Ruling:** freeze opcode 200's wire (no re-pin of its golden); introduce **opcode 212 `BankIssueCardV2`** = the M1 `BankIssueCard` fields **plus** `IssuancePrincipalVoucher` + `signature:[u8;65]`; make 212 the consented issue path. Gate 212 in `tx_is_bank_v2` (~application.rs:2519) + `block_has_bank_v2_tx` + `do_verify` + propose-exclusion + the RC8 test, using the `x < HEIGHT` form (never `>= MAX` — clippy `absurd_extreme_comparisons`). **Keep `BANK_ACTIVATION_HEIGHT = u64::MAX` at merge (land-gated-off, #934 doctrine); activation is a SEPARATE, explicitly user-authorized flag-day release that edits the constant — NOT a plan step, and NOT "= 0 via re-genesis" (the gate reads a compile-time const, not a `GenesisConfig` field).** Opcode 200 remains a live legacy un-consented path; the DoS it enabled is already bounded by `MAX_CARDS_PER_AGENT_BANK = 64` + swap-remove slot reclaim (M3), and 200 is slated for deprecation at the activation flag-day (a future gate rule). This ruling also **dissolves the opcode-200-reshape compile breaks** (indexer `json.rs:893`, `speculative.rs:3328`, `bank_pause_gate.rs:83`) the draft never enumerated — since 200 is untouched.
- **RV-2 (HIGH — bind the consent voucher to the owner). `BankIssueCardV2`'s `IssuancePrincipalVoucher` MUST bind `sender` (= tx.from = the card owner), not only the agent.** The draft verifies `owner_or_agent == agent` + gateway signature + `(bank,agent,nonce)` replay, but nothing ties the voucher to the submitting owner — so an adversary copies a broadcast, unspent voucher and wraps it in their **own** `IssueCardV2` (owner=attacker, agent=victim): the check passes, the victim's `(bank,agent,nonce)` triple is burned (griefing the victim's real issuance), and a card the attacker owns is minted carrying the victim's compliance `issuance_principal` (polluting the §7 admission quota). **Fix:** verify `voucher.owner_or_agent == sender` (§7's funder-identity intent) and **include `sender` in the nonce replay key**; bind the agent too if the agent-DoS dimension must also hold.
- **RV-3 (HIGH — seed CUSD with a real transfer hook, and admit the paymaster destination). Do NOT seed CUSD with `transfer_hook: None`.** CIP-36 §6.1/§6.2 make CUSD transfer-restricted (spend-only) its defining property; `None` mints a freely-P2P-transferable USD token on devnet, breaking the compliance perimeter and the wash/sybil premise. **Fix:** seed an allowlist `transfer_hook` at genesis permitting `card ↔ owner`, `card → PaymentGate`, **and `card/account → 0x16` (the paymaster destination)** — the last is what unblocks **M3.5's descoped token-gas funding (now M3.6)**, so design the two together. If a full hook is genuinely out of M4 scope, the fallback is to explicitly mark M4 CUSD dev-only/valueless and record the deviation — but seeding the hook is recommended (it is the point of CUSD and it unblocks M3.6). **RULED (2026-07-20, user): seed the real allowlist hook** (`card↔owner` / `card→PaymentGate` / `card/account→0x16`); do NOT ship `transfer_hook: None`. Task 6 must build the hook, and it is a hard dependency for M3.6 token-gas.
- **RV-4 (HIGH-adjacent — unified marker-first write ordering; supersedes both "burn-first" and the unconditional-mark note).** Apply the CLAUDE.md "validate ALL preconditions before the first state write" rule to **every** dedup'd mutation (settle_provider Task 14, consent Task 8, fiat-mint Task 11): (1) check all business preconditions via **infallible reads first** — dedup-key unused, signature valid, **solvency `amount ≤ balance(provider)`**, cap/slot checks; (2) then perform writes **marker-first** (write `settlement_used:` / `voucher_nonce_used:` / `voucher_used:` BEFORE the burn/issue/mint). With all business failures pre-checked, the only residual failure is storage I/O, and marker-first guarantees an I/O failure between the two writes **strands** (safe, non-repeatable) rather than allowing a retry to **double-burn/double-mint/double-issue**. This replaces the draft's "burn-first-then-mark" (Task 14 — retry double-burn hole) and its unconditional `mark_issuance_nonce_used` (Task 8 — over-marks on a failed issue; also make it `?`-short-circuit under the marker-first order).
- **RV-5 (MED — decouple the consent signer from `fiat_mint_signer`).** The draft verifies the consent voucher against `bank.fiat_mint_signer`; CIP-28 §2.2 defines `fiat_mint_signer = None` as "no fiat bridge," so under the draft a non-fiat bank **cannot issue any card**. **Fix:** verify the `IssuancePrincipalVoucher` against the **bank operator key** (recommended, simplest — operator is the bank's on-chain authority) or a dedicated `BankEntry.issuance_signer` field, NOT `fiat_mint_signer`. Keep `fiat_mint_signer` solely for `MintFromFiatVoucher`.
- **RV-6 (MED — make the conservation invariant test the real handlers).** Task 16 drives the bare `handle_token_mint`/`handle_token_burn_from` primitives — already covered by `econ_token_supply_conservation`, so it proves nothing about the M4 wiring. **Fix:** drive opcodes **210 then 211 end-to-end through dispatch** (`bank_mint_from_fiat_voucher` → `bank_settle_provider`) and assert `Σ CUSD balances == total_supply` before/after, catching a raw-write, wrong-`caller`, or missing-`mark_*` in the actual handlers.
- **RV-7 (LOW/doc — fold in).** (a) Task 11 dispatch sample must pass `sender` as the `caller` arg to match Task 14's 6-arg signature. (b) Give the `voucher_nonce_used:` consent-replay helpers their own full TDD task (parallel to the `voucher_used:` Task 9), not just a blockquote note. (c) Document that `settle_provider` reads `read_bank(store, 1)` — a single-bank (bank_id=1) limitation until multi-bank (M5); consider carrying `bank_id` on the 211 wire for forward-compat. (d) Publish the canonical **BE fixed-layout preimage vector** as the normative off-chain gateway contract (both voucher types) and flag a **CIP-28 §3.3 amendment** (spec says `rlp(voucher)`; implementation uses canonical BE) as a docs follow-up — otherwise the Stripe gateway and the chain will disagree on the signing preimage at flag-day.

**Confirmed sound (keep as-is):** codec additive arms + golden vectors for 210/211 (RV-1 removes the 200 re-pin); supply-conserving mint via `caller = 0x16` plain-param (0x16 never signs; `handle_token_create` always sets `mint_authority = tx.from`, so no user can mint a 0x16-authority token — strong defense-in-depth); domain separation (`CowboyBankFiatMint\x01` vs `CowboyBankIssuancePrincipal\x01`); operator authorization read from stored `BankEntry` (not spoofable); no pause-gate mis-bucketing (wildcard-free `matches!` allowlist); cross-repo finalize sequence with re-pin to the **merged-main** sha (both `types/Cargo.toml` + `ras/Cargo.toml`, codec+types crates, Cargo.lock committed, user-gated).

---

## Spec sources (verified)

M4 is governed by **two CIPs**; every task below flags which one is authoritative. Line anchors verified 2026-07-20 against `/home/ubuntu/workspace/cowboy/docs/cips/`.

| Feature | Authoritative spec | Anchor |
|---|---|---|
| `MintFromFiatVoucher` instruction, `FiatMintVoucher` struct, signing domain `keccak256("CowboyBankFiatMint\x01" ‖ rlp(voucher))`, `FiatMinted` event | **CIP-28** §3.3 (instruction table), §3.6 (events), §2.1 (`voucher_used:` state key) | `cip-28-cowboy-agent-banking.md:269` (table), `:107` (state key), `:300-317` (events) |
| Fiat bridge mint path (CUSD 1:1, `mint_authority = BankActor 0x16`) | **CIP-36** §6.1, §6.3 | `cip-36-phased-launch-cusd.md:103`, `:133-141` |
| `settle_provider(provider, n, settlement_id)` — idempotent, check-then-apply, consumed-set, `burn_from` wrap | **CIP-36** §6.3 | `cip-36-phased-launch-cusd.md:135-141`, §11 CIP-28 row `:194` |
| `IssuancePrincipalVoucher { bank_id, issuance_principal, owner_or_agent, nonce, expiry }` gateway-signed consent for `IssueCard`; writes the immutable `issuance_principal` | **CIP-36** §7 | `cip-36-phased-launch-cusd.md:158` |
| CUSD `burn_from_authority = BankActor`, opt-in per-token, immutable, default `None` | **CIP-36** §11 (CIP-20 amended row) | `cip-36-phased-launch-cusd.md:193` |
| BankActor address `0x16` | **CIP-28** r1.2 / WP §9.1 (referenced by CIP-36 §6.5) | `cip-36-phased-launch-cusd.md:149` |

> **The split, restated:** `FiatMintVoucher`/`MintFromFiatVoucher`/`FiatMinted`/`voucher_used:` are **CIP-28** vocabulary; the fact that the minted token is CUSD with `mint_authority = 0x16` and 1:1 fiat backing is **CIP-36**. `settle_provider` and `IssuancePrincipalVoucher` are **CIP-36** — CIP-28 §3.3 does *not* define them. Where CIP-36 leaves a wire schema, consumed-set key, or opcode number unspecified (`settle_provider`), this plan **specifies** it and marks it "author-specified, not spec" (see Scope decisions §3).

---

## Baseline (as-built)

All paths absolute-relative to the repo they live in.

**cowboy-protocol** (`crates/cowboy-protocol-codec/src/instruction.rs`, codec pinned in node at rev `a42c72d`):
- `pub const SYS_BANK_ISSUE_CARD: u8 = 200;` … `SYS_BANK_UNPAUSE_BANK: u8 = 209;` — `:367-376`. 210/211 are the next free contiguous slots.
- `enum SystemInstruction` bank variants `BankIssueCard { bank_id, agent, gas_payment_token, initial_policy, expires_at }` … `BankUnpauseBank` — `:523-568`.
- `enum PayCurrency { Native, Token([u8;32]) }` with `Write`/`Read`/`EncodeSize` — `:405-445`.
- Enum→opcode map `Self::BankIssueCard { .. } => SYS_BANK_ISSUE_CARD` — `:1564-1573`.
- `Write` arm for `BankIssueCard` — `:2009-2028`.
- `Read` arm `200 => …` — `:3666-3679`; `209 => …` ends the bank block `:3718`.
- `encode_size` arm for `BankIssueCard` — `:4988-5001`.
- Golden round-trip helper `pg_round_trip(inst, opcode)` — `:6538-6549`; bank goldens `:6716-6775` (`bank_opcodes_are_200_203`, `bank_issue_card_native_some_expiry_round_trips_at_200`, …).

**node** (`/home/ubuntu/workspace/node`):
- `bank::issue_card` free fn — `execution/src/bank/handlers.rs:359`; writes `CardEntry.issuance_principal: [0u8; 32]` unconditionally at `:407`; per-`(agent,bank)` cap `MAX_CARDS_PER_AGENT_BANK = 64` at `handlers.rs:40`, enforced `:394` (M3 hard-reject).
- `CardEntry` struct + fixed-layout `encode`/`decode` — `execution/src/bank/mod.rs:407-478`; `issuance_principal: [u8;32]` field at `:413`, encoded at `:431`, decoded at `:454`.
- `BankEntry.fiat_mint_signer: Option<Address>` — `execution/src/bank/mod.rs:361`.
- Hand-rolled BE codec helpers (`push_opt_u64`, `u32be`, `take`, `push_opt_addr`, `read_opt_addr`) — `execution/src/bank/mod.rs:40-90`; `derive_card_address` (keccak over `CARD_DERIVATION_DOMAIN ‖ …`) — `:495-507`; `CARD_DERIVATION_DOMAIN = b"CowboyBankCard\x01"` at `:16`.
- Bank storage keys — `execution/src/bank/storage.rs:30-105` (`bank_key`, `card_key`, `issue_nonce_key`, `stablecoin_whitelist_key`, …). **No `voucher_used:` or `settlement_used:` key exists yet.**
- Bank dispatch (system instr → handlers) — `execution/src/execution/system_instruction.rs:4956-5075`; `BankIssueCard` bridges wire `PayCurrency`→`bank::PayCurrency` and calls `bank::issue_card(...)` at `:4985`; `BankDeposit`/`BankWithdraw` are **methods on `self`** (`self.bank_deposit(...)`, `:5003`) so they can reach `self.handle_token_*`.
- CIP-20 mint — `execution/src/token/core.rs:716 handle_token_mint`: checks `mint.mint_authority == *caller`, `MAX_TOKEN_SUPPLY` guard, `total_supply.checked_add(amount)`; emits `TokenMinted`.
- CIP-20 burn-from — `execution/src/token/core.rs:840 handle_token_burn_from`: check-then-apply; requires `mint.burn_from_authority == Some(caller)`, `balance >= amount`, `total_supply.checked_sub(amount)`; emits `TokenBurnedFrom`. `reason` carries the settlement id (≤ `MAX_BURN_REASON_LEN`).
- `TokenMint` persisted as `serde_json` at `token_registry::mint_key(token_id)` under `token_registry_address()` — `execution/src/token/query.rs:60-83` (`get_token_mint`/`put_token_mint`); fields incl. `mint_authority`, `burn_from_authority`, `total_supply`, `max_supply` (`token/core.rs:120-135`). Public `handle_token_create` derives `token_id = keccak256(tx.from ‖ symbol ‖ nonce)` and **never** sets `burn_from_authority` (`core.rs:105-131`).
- secp256k1 recover pattern — `execution/src/runner/registry.rs:565-600 verify_runner_registration_signature` (Keccak256 prehash, `K256Signature::from_bytes`, `RecoveryId::from_byte`, `VerifyingKey::recover_from_prehash`, `Address::from_verifying_key`).
- Event topics — `execution/src/bank/handlers.rs:44-54` (`TOPIC_CARD_ISSUED` … `TOPIC_BANK_UNPAUSED`); consensus registry `execution/src/consensus_event_topics.rs` `KNOWN_CONSENSUS_EVENT_TOPICS` (guard test `consensus_event_topics_are_registered` scans `const TOPIC_*: &str = "…"` and inline `events.push(("literal", …))`).
- Event attribution — `storage/src/speculative.rs:427-437 system_event_emitter` Bank* arm returns `BANK_ACTOR_SYSTEM_ACTOR` for all ten current Bank ops.
- Activation gate — `chain/src/application.rs:2519 tx_is_bank_v2` (currently opcodes 204-209), `block_has_bank_v2_tx :2537`, `do_verify` uses `height < BANK_ACTIVATION_HEIGHT && block_has_bank_v2_tx`; RC8 test `bank_m3_opcodes_205_to_209_gated_below_activation :2665`. `BANK_ACTIVATION_HEIGHT: u64 = u64::MAX` — `types/src/constants.rs:683` (doc comment says "204 … through 209").
- Council-pause admission gate — `execution/src/execution/bank_pause_gate.rs` `system_instruction_targets_bank` (all ten bank ops) + `assert_bank_not_paused_for_instruction`.
- Genesis — `chain/src/genesis.rs`: `GenesisConfig` struct `:214` (`bank_operator :276`, `stablecoin_whitelist :283`); bank1 seeded with `fiat_mint_signer: None` at `:887-899` (the `None` is `:891`); stablecoin whitelist concat write `:900-914`. `validator/src/setup.rs:96` builds `GenesisConfig` (`bank_operator: Address::ZERO :112`, `stablecoin_whitelist: Vec::new() :113`).
- Supply-conservation invariant — `execution/src/econ_invariants.rs:632 econ_token_supply_conservation` (proptest: Σ balances == `total_supply` after every op).
- `BANK_ACTOR_SYSTEM_ACTOR: Address = 0x16` — `types/src/constants.rs:237`.

---

## Scope decisions (待裁 / to-be-ruled)

1. **F1(a) consent mechanism — how to bind an authorized `issuance_principal` to `IssueCard`.**
   - **(d) RECOMMENDED — fold `IssuancePrincipalVoucher` into opcode 200 `BankIssueCard`.** Spec-backed (CIP-36 §7 mandates a signed voucher on `IssueCard`). Closes the DoS (an attacker cannot name a victim as `agent` without a gateway-signed voucher binding `owner_or_agent`) **and** wires the immutable `issuance_principal` (today hard-coded `[0u8;32]`, `handlers.rs:407`) in one change. It **breaks opcode 200's wire shape** → not additive. **Re-genesis absorbs the break** (no legacy 200 txs survive a fresh genesis), so the only cost is re-pinning 200's golden vector. This is clean *because* M4 re-genesis's; on an in-place chain it would be unacceptable.
   - (a) New additive opcode 212 `BankIssueCardV2` carrying the voucher; keeps 200 frozen but leaves **two issue paths** (200 with `[0u8;32]` principal + no consent, 212 with consent) — the un-consented path stays a live DoS unless 200 is also gated off, which re-genesis would do anyway. More surface, no benefit under re-genesis.
   - (c) A lighter non-spec per-agent opt-in flag (agent pre-authorizes being named): no wire change, but **does not wire `issuance_principal`** (CIP-36 §7's sybil hinge) and diverges from spec. Rejected.
   - **Ruling: (d).** Modify 200; re-pin its golden.

2. **`fiat_mint_signer` provisioning / rotation.**
   - **RECOMMENDED — genesis-seed a devnet signer, defer live rotation to M5.** Seed `bank1.fiat_mint_signer = Some(<devnet gateway addr>)` at genesis so Parts A/B are exercisable; the CIP-28 §3.4 `SetBankFiatMintSigner` rotation op (new opcode) is out of M4 scope.
   - Alternative: pull `SetBankFiatMintSigner` into M4 for live rotation. Rejected for M4 — not on the fiat-issuance critical path; adds a codec opcode + governance-auth handler with no launch-blocking need. Track for M5.

3. **`settle_provider` wire schema, consumed-set key, opcode — author-specified (design, not spec).** Both CIPs are silent on the exact wire. This plan fixes: opcode **211** `SYS_BANK_SETTLE_PROVIDER`; wire `{ provider: Address, amount: u128, settlement_id: [u8;32] }`; consumed-set key `b"settlement_used:" ‖ settlement_id`. Flagged as design; if a later CIP-36 revision pins a different schema, this is the item to reconcile.

4. **CUSD `token_id` derivation + genesis seeding.** CUSD is minted only by the fiat bridge, so its `token_id` cannot come from a user `handle_token_create` (`keccak(from‖symbol‖nonce)`). **Author-specified:** fix a genesis constant `CUSD_TOKEN_ID: [u8;32] = keccak256(b"cowboy/cusd/v1")` in `types/src/constants.rs`; seed a `TokenMint` at `mint_key(CUSD_TOKEN_ID)` with `mint_authority = 0x16`, `burn_from_authority = Some(0x16)`, `decimals = 6`, `total_supply = 0`, `max_supply = None`; add `CUSD_TOKEN_ID` to the stablecoin whitelist. Vouchers reference it as `PayCurrency::Token(CUSD_TOKEN_ID)`. **Guardrail:** the mint handler does *not* trust `voucher.token` blindly — it calls `handle_token_mint` **as caller `0x16`**, which rejects (`TokenUnauthorized`) any token whose `mint_authority` is not `0x16`. Since only CUSD is seeded with `mint_authority = 0x16`, no other token is fiat-mintable even if a voucher names it. Flagged as design.

---

## Consensus / conservation guardrails (bake into every relevant task)

- **Mint is supply-conserving** only via `handle_token_mint` (`total_supply.checked_add`, `MAX_TOKEN_SUPPLY` guard, `mint_authority` check). **Burn** only via `handle_token_burn_from` (`total_supply.checked_sub`, `balance >= amount` precondition). **Never** `write_balance` directly (MEMORY M1 H1 pay-then-fail / mint-from-nothing). Invoke both **as caller `0x16`**.
- **Check-then-apply.** The speculative engine does **not** roll back partial writes on `Err` (MEMORY: no per-tx rollback → pay-then-fail). Every handler validates **all** preconditions (signature, replay key, expiry, bank/card status, solvency) **before** the first state write, and records the replay/consumed key **and** performs the mint/burn atomically after all checks pass. For `settle_provider`, an already-consumed `settlement_id` is an **idempotent Ok no-op that emits nothing** (never a re-burn, never an `Err` that would strand a partial write).
- **Deterministic signature verify.** secp256k1 recovery over `keccak256(DOMAIN ‖ canonical fixed-layout BE preimage)`, compared to the on-chain signer address. Use the hand-rolled BE encoding in `bank/mod.rs` (NOT serde/RLP) so the preimage is byte-fixed; add a golden preimage vector. Replay via `voucher_used:` / `settlement_used:` keys + nonce/expiry.
- **New event topics feed `receipt_root` (flag-day).** `FiatMinted`, `ProviderSettled` MUST be registered in `KNOWN_CONSENSUS_EVENT_TOPICS` or the guard test fails; emitter attribution routes to `0x16` via the existing `speculative.rs` Bank* arm.
- **New/changed opcodes → codec additive tail + goldens.** 210/211 are additive enum variants; 200's re-shape re-pins its golden. Node pins codec by git rev (`types/Cargo.toml:39` + `ras/Cargo.toml:23,30` — same rev). Every opcode → `tx_is_bank_v2` gate + `do_verify` block-level + RC8 test. Use `x < HEIGHT`, **never** `>= MAX` (clippy `absurd_extreme_comparisons`, MEMORY).
- **Commit messages: NO AI attribution** (no `Co-Authored-By: Claude…`, `node/CLAUDE.md` rule).

---

## File Structure

**Repo 1 — `cowboy-protocol` (wire codec, landed & merged first):**
- Modify `crates/cowboy-protocol-codec/src/instruction.rs`:
  - New opcode consts `SYS_BANK_MINT_FROM_FIAT_VOUCHER = 210`, `SYS_BANK_SETTLE_PROVIDER = 211`.
  - New codec structs `FiatMintVoucher`, `IssuancePrincipalVoucher` (`Read`/`Write`/`EncodeSize`).
  - Re-shape `SystemInstruction::BankIssueCard` (add `voucher: IssuancePrincipalVoucher`, `voucher_signature: [u8;65]`).
  - New variants `BankMintFromFiatVoucher { voucher, signature }`, `BankSettleProvider { provider, amount, settlement_id }`.
  - Enum→opcode map, `Write`, `Read`, `encode_size` arms for all three.
  - Golden round-trip vectors (re-pin 200; add 210, 211).

**Repo 2 — `node` (execution/storage/chain/genesis, pins the merged codec rev):**
- `types/Cargo.toml`, `ras/Cargo.toml` — bump codec `rev` to the merged main sha.
- `types/src/constants.rs` — `CUSD_TOKEN_ID`, `FIAT_MINT_DOMAIN`, `ISSUANCE_PRINCIPAL_DOMAIN`; update `BANK_ACTIVATION_HEIGHT` doc comment.
- `execution/src/bank/mod.rs` — voucher structs + canonical BE preimage encoders + `FiatMintVoucher`/`IssuancePrincipalVoucher` verify helpers; `TOPIC_FIAT_MINTED`, `TOPIC_PROVIDER_SETTLED` (or in `handlers.rs`).
- `execution/src/bank/storage.rs` — `voucher_used_key`/`settlement_used_key` + `read_*`/`write_*` helpers.
- `execution/src/bank/handlers.rs` — thread `issuance_principal` into `issue_card`; keep events.
- `execution/src/execution/system_instruction.rs` — dispatch: verify voucher in `BankIssueCard`; new `self.bank_mint_from_fiat_voucher(...)` and `self.bank_settle_provider(...)` methods (methods, so they reach `self.handle_token_mint`/`self.handle_token_burn_from`).
- `execution/src/consensus_event_topics.rs` — register `FiatMinted`, `ProviderSettled`.
- `storage/src/speculative.rs` — add the two new instrs to the Bank* emitter arm.
- `execution/src/execution/bank_pause_gate.rs` — add the two new instrs to `system_instruction_targets_bank`.
- `chain/src/application.rs` — `tx_is_bank_v2` + RC8 test gate opcodes 210/211.
- `chain/src/genesis.rs` — `GenesisConfig` fields (`fiat_mint_signer`, `cusd`), seed CUSD `TokenMint` + signer + whitelist.
- `validator/src/setup.rs` — populate the new `GenesisConfig` fields for devnet.
- `execution/src/econ_invariants.rs` — mint+burn round-trip conservation test.

---

## Task ordering (and why)

1. **Codec first (Tasks 1-4)** — 210/211 + re-shaped 200 + goldens, landed & merged to `cowboy-protocol` main. The node cannot compile a handler for an instruction its pinned codec cannot decode. Mirrors M1/M2/M3's two-repo flow (codec branch merges, then node re-pins the merged sha).
2. **Node re-pin + provisioning (Tasks 5-6)** — bump the codec rev; then Part D (genesis CUSD + signer). Provisioning lands **before** the handlers because the handlers' tests need a bank with a `fiat_mint_signer` and a CUSD `TokenMint` with `mint_authority = 0x16` to exercise mint/burn. Genesis has no behavioral coupling to the handlers, so it is safe to build first.
3. **Part A consent (Tasks 7-8)** — the `issue_card` voucher path + dispatch verify. Independent of B/C; unblocks the DoS fix.
4. **Part B mint (Tasks 9-11)** — `voucher_used:` storage, `FiatMintVoucher` verify, the mint handler + event + gate + attribution.
5. **Part C settle (Tasks 12-14)** — `settlement_used:` storage, the settle handler + event + gate + attribution.
6. **Cross-cutting (Tasks 15-17)** — gates (`tx_is_bank_v2`/RC8), conservation invariant test, full-suite verification.

---

# PART 1 — cowboy-protocol (wire codec)

Work in `/home/ubuntu/workspace/cowboy-protocol` on a branch off `main`.

- [ ] **Task 0: Branch**

```bash
cd /home/ubuntu/workspace/cowboy-protocol
git fetch origin
git checkout -b feat/cip28-m4-fiat-vouchers origin/main
```

---

### Task 1: Opcode constants + voucher codec structs

**Files:**
- Modify: `crates/cowboy-protocol-codec/src/instruction.rs:367-376` (add 210/211), and the `PayCurrency` block region `:405-445` (add the two structs nearby).

- [ ] **Step 1: Write the failing test** (append near the existing bank goldens, ~`:6720`)

```rust
#[test]
fn bank_m4_opcodes_are_210_211() {
    assert_eq!(SYS_BANK_MINT_FROM_FIAT_VOUCHER, 210);
    assert_eq!(SYS_BANK_SETTLE_PROVIDER, 211);
}

#[test]
fn fiat_mint_voucher_struct_round_trips() {
    use commonware_codec::{Encode, Decode};
    let v = FiatMintVoucher {
        bank_id: 1,
        card_address: Address::from_bytes([0xCA; 20]),
        token: PayCurrency::Token([0x7C; 32]),
        amount: 1_000_000u128,
        voucher_id: [0x11; 32],
        expires_at_block: 42,
        fiat_reference: vec![0xEF; 20],
    };
    let bytes = v.encode();
    assert_eq!(bytes.len(), v.encode_size());
    assert_eq!(FiatMintVoucher::decode(&bytes[..]).unwrap(), v);
}

#[test]
fn issuance_principal_voucher_struct_round_trips() {
    use commonware_codec::{Encode, Decode};
    let v = IssuancePrincipalVoucher {
        bank_id: 3,
        issuance_principal: [0x22; 32],
        owner_or_agent: Address::from_bytes([0xB0; 20]),
        nonce: 7,
        expires_at_block: 99,
    };
    let bytes = v.encode();
    assert_eq!(bytes.len(), v.encode_size());
    assert_eq!(IssuancePrincipalVoucher::decode(&bytes[..]).unwrap(), v);
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-protocol-codec bank_m4_opcodes_are_210_211 fiat_mint_voucher_struct_round_trips issuance_principal_voucher_struct_round_trips`
Expected: FAIL — `cannot find value SYS_BANK_MINT_FROM_FIAT_VOUCHER` / `cannot find type FiatMintVoucher`.

- [ ] **Step 3: Add the constants** (after `:376`)

```rust
/// CIP-28 §3.3 fiat bridge (mint CUSD from a compliance-gateway-signed voucher).
pub const SYS_BANK_MINT_FROM_FIAT_VOUCHER: u8 = 210;
/// CIP-36 §6.3 provider settlement (gateway-authorized `burn_from` of CUSD).
pub const SYS_BANK_SETTLE_PROVIDER: u8 = 211;
```

- [ ] **Step 4: Add the codec structs** (after the `PayCurrency` `EncodeSize` impl, ~`:445`)

```rust
/// CIP-28 §3.3 `FiatMintVoucher`. The compliance gateway signs
/// `keccak256("CowboyBankFiatMint\x01" ‖ <node canonical preimage>)`; this codec
/// only transports the fields — the node reconstructs the canonical preimage.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FiatMintVoucher {
    pub bank_id: u32,
    pub card_address: Address,
    pub token: PayCurrency,
    pub amount: u128,
    pub voucher_id: [u8; 32],
    pub expires_at_block: u64,
    pub fiat_reference: Vec<u8>, // ≤ 64 bytes; enforced at decode
}

impl Write for FiatMintVoucher {
    fn write(&self, w: &mut impl BufMut) {
        self.bank_id.write(w);
        self.card_address.write(w);
        self.token.write(w);
        self.amount.write(w);
        self.voucher_id.write(w);
        self.expires_at_block.write(w);
        self.fiat_reference.write(w);
    }
}
impl Read for FiatMintVoucher {
    type Cfg = ();
    fn read_cfg(r: &mut impl Buf, _: &Self::Cfg) -> Result<Self, Error> {
        Ok(Self {
            bank_id: u32::read(r)?,
            card_address: Address::read(r)?,
            token: PayCurrency::read(r)?,
            amount: u128::read(r)?,
            voucher_id: <[u8; 32]>::read(r)?,
            expires_at_block: u64::read(r)?,
            fiat_reference: Vec::<u8>::read_cfg(r, &(RangeCfg::from(0..=64), ()))?,
        })
    }
}
impl EncodeSize for FiatMintVoucher {
    fn encode_size(&self) -> usize {
        self.bank_id.encode_size()
            + self.card_address.encode_size()
            + self.token.encode_size()
            + self.amount.encode_size()
            + self.voucher_id.encode_size()
            + self.expires_at_block.encode_size()
            + self.fiat_reference.encode_size()
    }
}

/// CIP-36 §7 `IssuancePrincipalVoucher` — gateway-signed consent binding the
/// immutable `issuance_principal` to an authorized `owner_or_agent`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IssuancePrincipalVoucher {
    pub bank_id: u32,
    pub issuance_principal: [u8; 32],
    pub owner_or_agent: Address,
    pub nonce: u64,
    pub expires_at_block: u64,
}

impl Write for IssuancePrincipalVoucher {
    fn write(&self, w: &mut impl BufMut) {
        self.bank_id.write(w);
        self.issuance_principal.write(w);
        self.owner_or_agent.write(w);
        self.nonce.write(w);
        self.expires_at_block.write(w);
    }
}
impl Read for IssuancePrincipalVoucher {
    type Cfg = ();
    fn read_cfg(r: &mut impl Buf, _: &Self::Cfg) -> Result<Self, Error> {
        Ok(Self {
            bank_id: u32::read(r)?,
            issuance_principal: <[u8; 32]>::read(r)?,
            owner_or_agent: Address::read(r)?,
            nonce: u64::read(r)?,
            expires_at_block: u64::read(r)?,
        })
    }
}
impl EncodeSize for IssuancePrincipalVoucher {
    fn encode_size(&self) -> usize {
        self.bank_id.encode_size()
            + self.issuance_principal.encode_size()
            + self.owner_or_agent.encode_size()
            + self.nonce.encode_size()
            + self.expires_at_block.encode_size()
    }
}
```

> Confirm the `Read`/`Write`/`BufMut`/`Buf`/`RangeCfg`/`Error` imports already in scope at the top of the file cover these (they are used by `PayCurrency` and the `Vec<u8>` reads above). If `Read`/`Decode`/`Encode` need a `use`, mirror the existing `PayCurrency` impl block.

- [ ] **Step 5: Run — verify pass**

Run: `cargo test -p cowboy-protocol-codec bank_m4_opcodes fiat_mint_voucher_struct issuance_principal_voucher_struct`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add crates/cowboy-protocol-codec/src/instruction.rs
git commit -m "codec: add CIP-28 M4 opcodes 210/211 + FiatMintVoucher/IssuancePrincipalVoucher structs"
```

---

### Task 2: Re-shape `BankIssueCard` (opcode 200) to carry the consent voucher

**Files:**
- Modify: `crates/cowboy-protocol-codec/src/instruction.rs` — enum def `:524`, Write `:2009`, Read `:3666`, encode_size `:4988`, existing goldens `:6728` & `:6748`.

- [ ] **Step 1: Update the existing golden tests to the new shape** (edit `:6728-6775`)

```rust
#[test]
fn bank_issue_card_native_some_expiry_round_trips_at_200() {
    pg_round_trip(
        Instruction::System(Box::new(SystemInstruction::BankIssueCard {
            bank_id: 7u32,
            agent: Address::from_bytes([0xA1; 20]),
            gas_payment_token: PayCurrency::Native,
            initial_policy: vec![0xAB; 96],
            expires_at: Some(1_700_000_000u64),
            voucher: IssuancePrincipalVoucher {
                bank_id: 7,
                issuance_principal: [0x5A; 32],
                owner_or_agent: Address::from_bytes([0xA1; 20]),
                nonce: 1,
                expires_at_block: 1_700_000_000,
            },
            voucher_signature: [0x9; 65],
        })),
        SYS_BANK_ISSUE_CARD,
    );
}

#[test]
fn bank_issue_card_token_none_expiry_round_trips_at_200() {
    pg_round_trip(
        Instruction::System(Box::new(SystemInstruction::BankIssueCard {
            bank_id: 0u32,
            agent: Address::from_bytes([0xA2; 20]),
            gas_payment_token: PayCurrency::Token([0x7C; 32]),
            initial_policy: Vec::new(),
            expires_at: None,
            voucher: IssuancePrincipalVoucher {
                bank_id: 0,
                issuance_principal: [0u8; 32],
                owner_or_agent: Address::from_bytes([0xA2; 20]),
                nonce: 0,
                expires_at_block: 0,
            },
            voucher_signature: [0u8; 65],
        })),
        SYS_BANK_ISSUE_CARD,
    );
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-protocol-codec bank_issue_card`
Expected: FAIL — `BankIssueCard` has no field `voucher`.

- [ ] **Step 3: Extend the enum variant** (`:524`)

```rust
    BankIssueCard {
        bank_id: u32,
        agent: Address,
        gas_payment_token: PayCurrency,
        initial_policy: Vec<u8>,
        expires_at: Option<u64>,
        // CIP-36 §7: gateway-signed consent binding the immutable issuance_principal.
        voucher: IssuancePrincipalVoucher,
        voucher_signature: [u8; 65],
    },
```

- [ ] **Step 4: Extend the `Write` arm** (`:2009`, after the `expires_at` match)

```rust
                    SystemInstruction::BankIssueCard {
                        bank_id,
                        agent,
                        gas_payment_token,
                        initial_policy,
                        expires_at,
                        voucher,
                        voucher_signature,
                    } => {
                        SYS_BANK_ISSUE_CARD.write(writer);
                        bank_id.write(writer);
                        agent.write(writer);
                        gas_payment_token.write(writer);
                        initial_policy.write(writer);
                        match expires_at {
                            None => 0u8.write(writer),
                            Some(v) => {
                                1u8.write(writer);
                                v.write(writer);
                            }
                        }
                        voucher.write(writer);
                        voucher_signature.write(writer);
                    }
```

- [ ] **Step 5: Extend the `Read` arm** (`:3666`)

```rust
                    200 => Self::System(Box::new(SystemInstruction::BankIssueCard {
                        bank_id: u32::read(reader)?,
                        agent: Address::read(reader)?,
                        gas_payment_token: PayCurrency::read(reader)?,
                        initial_policy: Vec::<u8>::read_cfg(
                            reader,
                            &(RangeCfg::from(0..=8192), ()),
                        )?,
                        expires_at: match u8::read(reader)? {
                            0 => None,
                            1 => Some(u64::read(reader)?),
                            _ => return Err(Error::InvalidEnum(200)),
                        },
                        voucher: IssuancePrincipalVoucher::read(reader)?,
                        voucher_signature: <[u8; 65]>::read(reader)?,
                    })),
```

- [ ] **Step 6: Extend the `encode_size` arm** (`:4988`)

```rust
                        SystemInstruction::BankIssueCard {
                            bank_id,
                            agent,
                            gas_payment_token,
                            initial_policy,
                            expires_at,
                            voucher,
                            voucher_signature,
                        } => {
                            bank_id.encode_size()
                                + agent.encode_size()
                                + gas_payment_token.encode_size()
                                + initial_policy.encode_size()
                                + 1
                                + expires_at.map(|v| v.encode_size()).unwrap_or(0)
                                + voucher.encode_size()
                                + voucher_signature.encode_size()
                        }
```

- [ ] **Step 7: Run — verify pass**

Run: `cargo test -p cowboy-protocol-codec bank_issue_card`
Expected: PASS (both goldens).

- [ ] **Step 8: Commit**

```bash
git add crates/cowboy-protocol-codec/src/instruction.rs
git commit -m "codec: fold IssuancePrincipalVoucher into BankIssueCard (opcode 200) — re-genesis breaking change, golden re-pinned"
```

---

### Task 3: Add `BankMintFromFiatVoucher` (210) + `BankSettleProvider` (211) variants

**Files:**
- Modify: `crates/cowboy-protocol-codec/src/instruction.rs` — enum `:568` (after `BankUnpauseBank`), map `:1573`, Write, Read `:3718`, encode_size `:5001`, goldens.

- [ ] **Step 1: Write the failing goldens** (near `:6775`)

```rust
#[test]
fn bank_mint_from_fiat_voucher_round_trips_at_210() {
    pg_round_trip(
        Instruction::System(Box::new(SystemInstruction::BankMintFromFiatVoucher {
            voucher: FiatMintVoucher {
                bank_id: 1,
                card_address: Address::from_bytes([0xCA; 20]),
                token: PayCurrency::Token([0x7C; 32]),
                amount: 5_000_000u128,
                voucher_id: [0x33; 32],
                expires_at_block: 1_000,
                fiat_reference: b"ch_stripe_abc".to_vec(),
            },
            signature: [0x7; 65],
        })),
        SYS_BANK_MINT_FROM_FIAT_VOUCHER,
    );
}

#[test]
fn bank_settle_provider_round_trips_at_211() {
    pg_round_trip(
        Instruction::System(Box::new(SystemInstruction::BankSettleProvider {
            provider: Address::from_bytes([0xDD; 20]),
            amount: 250_000u128,
            settlement_id: [0x44; 32],
        })),
        SYS_BANK_SETTLE_PROVIDER,
    );
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-protocol-codec bank_mint_from_fiat_voucher bank_settle_provider`
Expected: FAIL — no variant `BankMintFromFiatVoucher`.

- [ ] **Step 3: Add variants** (after `BankUnpauseBank { bank_id: u32 },` at `:568`)

```rust
    BankMintFromFiatVoucher {
        voucher: FiatMintVoucher,
        signature: [u8; 65],
    },
    BankSettleProvider {
        provider: Address,
        amount: u128,
        settlement_id: [u8; 32],
    },
```

- [ ] **Step 4: Add enum→opcode map entries** (after `:1573`)

```rust
            Self::BankMintFromFiatVoucher { .. } => SYS_BANK_MINT_FROM_FIAT_VOUCHER,
            Self::BankSettleProvider { .. } => SYS_BANK_SETTLE_PROVIDER,
```

- [ ] **Step 5: Add `Write` arms** (after the `BankUnpauseBank` write arm)

```rust
                    SystemInstruction::BankMintFromFiatVoucher { voucher, signature } => {
                        SYS_BANK_MINT_FROM_FIAT_VOUCHER.write(writer);
                        voucher.write(writer);
                        signature.write(writer);
                    }
                    SystemInstruction::BankSettleProvider {
                        provider,
                        amount,
                        settlement_id,
                    } => {
                        SYS_BANK_SETTLE_PROVIDER.write(writer);
                        provider.write(writer);
                        amount.write(writer);
                        settlement_id.write(writer);
                    }
```

- [ ] **Step 6: Add `Read` arms** (after `209 => …` at `:3718`)

```rust
                    210 => Self::System(Box::new(SystemInstruction::BankMintFromFiatVoucher {
                        voucher: FiatMintVoucher::read(reader)?,
                        signature: <[u8; 65]>::read(reader)?,
                    })),
                    211 => Self::System(Box::new(SystemInstruction::BankSettleProvider {
                        provider: Address::read(reader)?,
                        amount: u128::read(reader)?,
                        settlement_id: <[u8; 32]>::read(reader)?,
                    })),
```

- [ ] **Step 7: Add `encode_size` arms** (after the `BankUnpauseBank` size arm)

```rust
                        SystemInstruction::BankMintFromFiatVoucher { voucher, signature } => {
                            voucher.encode_size() + signature.encode_size()
                        }
                        SystemInstruction::BankSettleProvider {
                            provider,
                            amount,
                            settlement_id,
                        } => {
                            provider.encode_size() + amount.encode_size() + settlement_id.encode_size()
                        }
```

- [ ] **Step 8: Run — verify pass + full codec suite**

Run: `cargo test -p cowboy-protocol-codec`
Expected: PASS (all, incl. the two new goldens; the `sys_opcode_uniqueness`-style guards stay green since 210/211 are unique).

- [ ] **Step 9: Commit**

```bash
git add crates/cowboy-protocol-codec/src/instruction.rs
git commit -m "codec: add BankMintFromFiatVoucher (210) + BankSettleProvider (211) instructions with goldens"
```

---

### Task 4: cowboy-protocol PR (user-gated finalize — do NOT push without authorization)

- [ ] **Step 1: Run the full codec workspace green**

Run: `cargo fmt --all && cargo test -p cowboy-protocol-codec && cargo clippy -p cowboy-protocol-codec --all-targets -- -D warnings`
Expected: all green.

- [ ] **Step 2: Push + open PR** (only after the user authorizes)

```bash
git push -u origin feat/cip28-m4-fiat-vouchers
gh pr create --base main --title "CIP-28 M4: fiat-mint + settle-provider + consent-voucher opcodes" \
  --body "Adds opcodes 210 (MintFromFiatVoucher) / 211 (settle_provider); folds IssuancePrincipalVoucher into opcode 200 (re-genesis breaking change; golden re-pinned). Node re-pins this rev after merge."
```

- [ ] **Step 3: After merge, record the merged main sha** — the node re-pins to the **merged main sha, NOT the feature-branch sha** (squash-merge rewrites the commit; MEMORY squash re-pin lesson). Get it:

```bash
git fetch origin && git rev-parse origin/main
```

---

# PART 2 — node (execution / storage / chain / genesis)

Work in `/home/ubuntu/workspace/node` on a branch off `devnet`.

- [ ] **Task 5 preamble: Branch**

```bash
cd /home/ubuntu/workspace/node
git fetch origin
git checkout -b feat/cip28-m4-fiat-issuance origin/devnet
```

---

### Task 5: Re-pin the codec rev

**Files:**
- Modify: `types/Cargo.toml:39` & `:42`; `ras/Cargo.toml:23` & `:30`.

- [ ] **Step 1: Bump all four `rev = "a42c72d"` occurrences to the merged main sha** (call it `<MAIN_SHA>`)

```bash
cd /home/ubuntu/workspace/node
sed -i 's/rev = "a42c72d"/rev = "<MAIN_SHA>"/' types/Cargo.toml ras/Cargo.toml
```

- [ ] **Step 2: Verify the node still builds against the new codec**

Run: `cargo build -p cowboy-types -p cowboy-ras`
Expected: compiles; `Cargo.lock` updates to `<MAIN_SHA>`.

- [ ] **Step 3: Commit**

```bash
git add types/Cargo.toml ras/Cargo.toml Cargo.lock
git commit -m "deps: re-pin cowboy-protocol codec to <MAIN_SHA> (CIP-28 M4 opcodes 210/211 + reshaped 200)"
```

---

### Task 6 (Part D): Provision CUSD + fiat signer at genesis

**Files:**
- Modify: `types/src/constants.rs` (new consts); `chain/src/genesis.rs:214` (`GenesisConfig`), `:887-914` (seed); `validator/src/setup.rs:96-113`.
- Test: `chain/src/genesis.rs` tests module (~`:2335`).

- [ ] **Step 1: Add constants** to `types/src/constants.rs`

```rust
/// CIP-36 §6.1 / §4 (Scope decision 4): the genesis-fixed CUSD token id. CUSD is
/// mint-authority-gated to the BankActor (0x16) and is the only fiat-mintable token.
/// Author-specified (no user `token_create` derivation applies to a genesis token).
pub const CUSD_TOKEN_ID: [u8; 32] = keccak256_const(b"cowboy/cusd/v1");
```

> If a `const`-evaluable keccak is unavailable, instead hard-code the 32-byte digest of `b"cowboy/cusd/v1"` as a byte literal with a comment giving the preimage, and add a test asserting `keccak256(b"cowboy/cusd/v1") == CUSD_TOKEN_ID`. Prefer the literal to avoid a const-fn keccak dependency.

- [ ] **Step 2: Add `GenesisConfig` fields** (`chain/src/genesis.rs:214` struct, near `bank_operator`/`stablecoin_whitelist`)

```rust
    /// CIP-28 §2.2 / §3.3: the devnet compliance-gateway key that signs
    /// FiatMintVouchers. `None` = the genesis bank does not support the fiat bridge.
    pub bank_fiat_mint_signer: Option<cowboy_types::Address>,
    /// CIP-36 §6.1 (Scope decision 4): when true, seed the CUSD TokenMint
    /// (mint_authority = burn_from_authority = 0x16) and whitelist CUSD_TOKEN_ID.
    pub seed_cusd: bool,
```

Add defaults in every `GenesisConfig { … }` literal in the file's tests (`bank_fiat_mint_signer: None, seed_cusd: false` at each of `:461`, `:1646`, `:1928`, `:1957`, `:1994`, `:2031`, `:2697`).

- [ ] **Step 3: Wire the seed** — replace `fiat_mint_signer: None,` at `genesis.rs:891` with `fiat_mint_signer: self.bank_fiat_mint_signer,` and, after the stablecoin-whitelist write (`:914`), seed CUSD:

```rust
        if self.seed_cusd {
            let cusd = cowboy_token::TokenMint {
                token_id: cowboy_types::constants::CUSD_TOKEN_ID,
                name: b"Cowboy USD".to_vec(),
                symbol: b"CUSD".to_vec(),
                decimals: 6,
                total_supply: 0,
                max_supply: None,
                owner: cowboy_types::BANK_ACTOR_SYSTEM_ACTOR,
                mint_authority: cowboy_types::BANK_ACTOR_SYSTEM_ACTOR,
                freeze_authority: Some(cowboy_types::BANK_ACTOR_SYSTEM_ACTOR),
                burn_from_authority: Some(cowboy_types::BANK_ACTOR_SYSTEM_ACTOR),
                transfer_hook: None, // CIP-36 §6.2 hook policy is a later item; card-resident CUSD spends via PaymentGate
                metadata_uri: None,
                created_at: 0,
            };
            let registry_addr = cowboy_execution::token::token_registry_address();
            initial_storage.push((
                registry_addr,
                cowboy_execution::token::mint_key(&cowboy_types::constants::CUSD_TOKEN_ID),
                serde_json::to_vec(&cusd).expect("TokenMint serialization is infallible"),
            ));
        }
```

> Confirm the exact re-export paths for `token_registry_address` / `mint_key` (in `execution/src/token/query.rs` they call `token_registry::mint_key`; expose a `pub use` if not already public). Match the whitelist write pattern already at `:900-914` — and add `CUSD_TOKEN_ID` to `self.stablecoin_whitelist` in `setup.rs` (next step) so the concat write includes it.

- [ ] **Step 4: Populate for devnet** in `validator/src/setup.rs:96-113`

```rust
        bank_operator: /* existing devnet operator addr, or a fixed devnet key */,
        stablecoin_whitelist: vec![cowboy_types::constants::CUSD_TOKEN_ID],
        bank_fiat_mint_signer: Some(/* devnet gateway addr, e.g. derived from a fixed devnet key */),
        seed_cusd: true,
```

- [ ] **Step 5: Write the seed test** (in `genesis.rs` tests, ~`:2335`)

```rust
#[test]
fn genesis_seeds_cusd_mint_and_fiat_signer() {
    use cowboy_execution::bank::storage::bank_key;
    let mut config = GenesisConfig::default_for_test(); // whatever the module uses
    config.seed_cusd = true;
    config.bank_fiat_mint_signer = Some(cowboy_types::Address::from_low_u64(0xF1A7));
    config.stablecoin_whitelist = vec![cowboy_types::constants::CUSD_TOKEN_ID];
    let (_, initial_storage, ..) = config.build(); // match the real build() return shape

    // CUSD mint present with mint_authority == burn_from_authority == 0x16.
    let registry = cowboy_execution::token::token_registry_address();
    let mint_bytes = initial_storage.iter()
        .find(|(a, k, _)| *a == registry
            && k.as_slice() == cowboy_execution::token::mint_key(&cowboy_types::constants::CUSD_TOKEN_ID).as_slice())
        .map(|(_, _, v)| v).expect("CUSD mint seeded");
    let mint: cowboy_token::TokenMint = serde_json::from_slice(mint_bytes).unwrap();
    assert_eq!(mint.mint_authority, cowboy_types::BANK_ACTOR_SYSTEM_ACTOR);
    assert_eq!(mint.burn_from_authority, Some(cowboy_types::BANK_ACTOR_SYSTEM_ACTOR));
    assert_eq!(mint.total_supply, 0);

    // bank1.fiat_mint_signer is Some.
    let bank_addr = cowboy_types::BANK_ACTOR_SYSTEM_ACTOR;
    let bank_bytes = initial_storage.iter()
        .find(|(a, k, _)| *a == bank_addr && k.as_slice() == bank_key(1).as_slice())
        .map(|(_, _, v)| v).expect("bank1 seeded");
    let bank = cowboy_execution::bank::BankEntry::decode(bank_bytes).unwrap();
    assert!(bank.fiat_mint_signer.is_some());
}
```

> Adapt `default_for_test()` / `build()` / the storage-tuple shape to the actual test harness at `genesis.rs:2335` (which already inspects `stablecoin_whitelist_key` writes, `:2374`) — reuse its exact idiom.

- [ ] **Step 6: Run — verify pass**

Run: `cargo test -p cowboy-chain genesis_seeds_cusd_mint_and_fiat_signer -- --nocapture`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cargo fmt --all
git add types/src/constants.rs chain/src/genesis.rs validator/src/setup.rs
git commit -m "genesis: seed CUSD TokenMint (mint_authority=0x16) + devnet fiat_mint_signer (CIP-36 §6.1, CIP-28 §2.2)"
```

---

### Task 7 (Part A): Consent — verify helper + `issue_card` writes the signed principal

**Files:**
- Modify: `execution/src/bank/mod.rs` (voucher struct alias + preimage encoder + verify helper; `ISSUANCE_PRINCIPAL_DOMAIN`).
- Modify: `execution/src/bank/handlers.rs:359` (`issue_card` signature + `:407` principal write).
- Test: `execution/src/bank/mod.rs` tests module.

- [ ] **Step 1: Write the failing verify test** (in `bank/mod.rs` tests, ~`:509`)

```rust
#[test]
fn issuance_principal_voucher_verify_roundtrip_and_tamper() {
    use k256::ecdsa::SigningKey;
    let sk = SigningKey::from_bytes(&[0x11u8; 32].into()).unwrap();
    let signer = Address::from_verifying_key(sk.verifying_key());
    let v = IssuancePrincipalVoucherFields {
        bank_id: 1,
        issuance_principal: [0x5A; 32],
        owner_or_agent: addr(0xB0),
        nonce: 1,
        expires_at_block: 100,
    };
    let hash = issuance_principal_preimage_hash(&v);
    let (sig, rid) = sk.sign_prehash_recoverable(&hash).unwrap();
    let mut sig65 = [0u8; 65];
    sig65[..64].copy_from_slice(&sig.to_bytes());
    sig65[64] = rid.to_byte();
    // Correct signer verifies.
    assert!(verify_issuance_principal_voucher(&v, &sig65, &signer).is_ok());
    // A tampered principal fails to recover to the signer.
    let mut bad = v.clone();
    bad.issuance_principal = [0xFF; 32];
    assert!(verify_issuance_principal_voucher(&bad, &sig65, &signer).is_err());
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-execution issuance_principal_voucher_verify_roundtrip_and_tamper`
Expected: FAIL — items not found.

- [ ] **Step 3: Add domain, fields alias, preimage encoder, verify helper** to `bank/mod.rs`

```rust
/// CIP-36 §7 signing domain for the IssuancePrincipalVoucher.
pub const ISSUANCE_PRINCIPAL_DOMAIN: &[u8] = b"CowboyBankIssuancePrincipal\x01";

/// Node-side mirror of the codec `IssuancePrincipalVoucher` fields (the codec type
/// lives in cowboy-protocol; this is the execution-layer copy the handler receives).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IssuancePrincipalVoucherFields {
    pub bank_id: u32,
    pub issuance_principal: [u8; 32],
    pub owner_or_agent: Address,
    pub nonce: u64,
    pub expires_at_block: u64,
}

/// Canonical fixed-layout BE preimage (NOT serde/RLP), then keccak256 with the domain.
pub fn issuance_principal_preimage_hash(v: &IssuancePrincipalVoucherFields) -> [u8; 32] {
    let mut buf = Vec::with_capacity(ISSUANCE_PRINCIPAL_DOMAIN.len() + 4 + 32 + 20 + 8 + 8);
    buf.extend_from_slice(ISSUANCE_PRINCIPAL_DOMAIN);
    buf.extend_from_slice(&v.bank_id.to_be_bytes());
    buf.extend_from_slice(&v.issuance_principal);
    buf.extend_from_slice(v.owner_or_agent.as_ref());
    buf.extend_from_slice(&v.nonce.to_be_bytes());
    buf.extend_from_slice(&v.expires_at_block.to_be_bytes());
    keccak256(&buf)
}

/// Recover the signer from a 65-byte `r||s||v` signature over the preimage hash and
/// compare to `expected_signer`. Mirrors registry.rs::verify_runner_registration_signature.
pub fn verify_issuance_principal_voucher(
    v: &IssuancePrincipalVoucherFields,
    signature: &[u8; 65],
    expected_signer: &Address,
) -> Result<(), ExecutionError> {
    let hash = issuance_principal_preimage_hash(v);
    recover_and_check(&hash, signature, expected_signer)
}

/// Shared secp256k1 recover-and-compare (also used by the fiat-mint verify).
pub(crate) fn recover_and_check(
    hash: &[u8; 32],
    signature: &[u8; 65],
    expected: &Address,
) -> Result<(), ExecutionError> {
    use k256::ecdsa::{RecoveryId, Signature as K256Signature, VerifyingKey};
    let sig_bytes: &[u8; 64] = signature[..64]
        .try_into()
        .map_err(|_| ExecutionError::InvalidSignature)?;
    let recid = RecoveryId::from_byte(signature[64]).ok_or(ExecutionError::InvalidSignature)?;
    let k = K256Signature::from_bytes(sig_bytes.into()).map_err(|_| ExecutionError::InvalidSignature)?;
    let vk = VerifyingKey::recover_from_prehash(hash, &k, recid)
        .map_err(|_| ExecutionError::InvalidSignature)?;
    if Address::from_verifying_key(&vk) != *expected {
        return Err(ExecutionError::InvalidSignature);
    }
    Ok(())
}
```

> Confirm `keccak256`, `Address`, `ExecutionError`, `Address::from_verifying_key` are imported at the top of `bank/mod.rs` (they are used by `derive_card_address`). Add `use` lines if not.

- [ ] **Step 4: Run — verify pass**

Run: `cargo test -p cowboy-execution issuance_principal_voucher_verify_roundtrip_and_tamper`
Expected: PASS.

- [ ] **Step 5: Thread `issuance_principal` into `issue_card`** — change the signature at `handlers.rs:359` to accept `issuance_principal: [u8; 32]` (new param) and replace `issuance_principal: [0u8; 32],` at `:407` with `issuance_principal,`. (Signature verification + nonce/expiry checks happen in the dispatch layer, Task 8, so the free fn stays pure state.) Update the existing `issue_card` unit tests in `handlers.rs` (e.g. `:1121`) to pass a principal (use `[0u8;32]` where they don't care).

- [ ] **Step 6: Run — verify handler tests pass**

Run: `cargo test -p cowboy-execution bank::handlers`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cargo fmt --all
git add execution/src/bank/mod.rs execution/src/bank/handlers.rs
git commit -m "bank: add IssuancePrincipalVoucher verify (CIP-36 §7) + thread issuance_principal into issue_card"
```

---

### Task 8 (Part A): Dispatch — verify the consent voucher before `issue_card`

**Files:**
- Modify: `execution/src/execution/system_instruction.rs:4971-4998` (the `BankIssueCard` dispatch arm).

- [ ] **Step 1: Write the failing integration test** (in `execution/src/execution/tests.rs` — mirror an existing bank issue test)

```rust
#[tokio::test]
async fn issue_card_rejects_unsigned_voucher_but_accepts_gateway_signed() {
    // Seed a bank with fiat_mint_signer = <gateway>. Build a BankIssueCard whose
    // voucher.owner_or_agent = victim, signed by the gateway → card issued with the
    // signed issuance_principal. Same tx with a wrong-key signature → InvalidSignature,
    // no card written, victim's (agent,bank) slot untouched.
    // (Fill in with the harness used by the existing issue_card execution tests.)
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-execution issue_card_rejects_unsigned_voucher`
Expected: FAIL (voucher not yet verified in dispatch).

- [ ] **Step 3: Verify in the dispatch arm** (`system_instruction.rs:4971`)

```rust
                    cowboy_types::SystemInstruction::BankIssueCard {
                        bank_id,
                        agent,
                        gas_payment_token,
                        initial_policy,
                        expires_at,
                        voucher,
                        voucher_signature,
                    } => {
                        // CIP-36 §7: the voucher must be gateway-signed and bind an
                        // authorized owner_or_agent, and match the named bank/agent.
                        let bank = crate::bank::storage::read_bank(store, *bank_id)
                            .await?
                            .ok_or(ExecutionError::InvalidData)?;
                        let signer = bank.fiat_mint_signer.ok_or(ExecutionError::InvalidData)?;
                        if voucher.bank_id != *bank_id || voucher.owner_or_agent != *agent {
                            return Err(ExecutionError::InvalidData);
                        }
                        if block_height > voucher.expires_at_block {
                            return Err(ExecutionError::InvalidData);
                        }
                        let vf = crate::bank::IssuancePrincipalVoucherFields {
                            bank_id: voucher.bank_id,
                            issuance_principal: voucher.issuance_principal,
                            owner_or_agent: voucher.owner_or_agent,
                            nonce: voucher.nonce,
                            expires_at_block: voucher.expires_at_block,
                        };
                        crate::bank::verify_issuance_principal_voucher(&vf, voucher_signature, &signer)?;
                        // Replay: the (bank, agent, nonce) triple is single-use.
                        crate::bank::storage::assert_issuance_nonce_unused(store, *bank_id, agent, voucher.nonce).await?;
                        let cur = match gas_payment_token {
                            cowboy_types::PayCurrency::Native => crate::bank::PayCurrency::Native,
                            cowboy_types::PayCurrency::Token(a) => crate::bank::PayCurrency::Token(*a),
                        };
                        let out = bank::issue_card(
                            store, &mut self.system_events, *bank_id, agent, cur,
                            initial_policy, *expires_at, sender, block_height,
                            voucher.issuance_principal,
                        ).await.map(|_| None);
                        crate::bank::storage::mark_issuance_nonce_used(store, *bank_id, agent, voucher.nonce).await?;
                        out
                    }
```

> Add `voucher_nonce_used:` read/write helpers in `bank/storage.rs` (key `b"voucher_nonce_used:" ‖ bank_id_be4 ‖ agent_20 ‖ nonce_be8`). This is the §7 nonce replay protection distinct from the card `issue_nonce` (which is the derivation counter). Keep the check-then-apply ordering (assert before issue, mark after) — a failed `issue_card` returns `Err` before `mark_*`, so no consumed nonce is stranded.

- [ ] **Step 4: Run — verify pass**

Run: `cargo test -p cowboy-execution issue_card_rejects_unsigned_voucher`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add execution/src/execution/system_instruction.rs execution/src/bank/storage.rs
git commit -m "bank: enforce gateway-signed consent voucher on IssueCard dispatch (CIP-36 §7) — closes agent-slot DoS"
```

---

### Task 9 (Part B): `voucher_used:` storage helpers

**Files:**
- Modify: `execution/src/bank/storage.rs` (after `:105`).
- Test: `bank/storage.rs` tests (~`:464`).

- [ ] **Step 1: Write the failing test**

```rust
#[tokio::test]
async fn voucher_used_marker_roundtrip() {
    let mut s = TestStore::default();
    let vid = [0x33u8; 32];
    assert!(!is_voucher_used(&s, &vid).await.unwrap());
    mark_voucher_used(&mut s, &vid).await.unwrap();
    assert!(is_voucher_used(&s, &vid).await.unwrap());
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-execution voucher_used_marker_roundtrip`
Expected: FAIL — items not found.

- [ ] **Step 3: Implement** (CIP-28 §2.1 key `b"voucher_used:" ‖ voucher_id_32`)

```rust
pub fn voucher_used_key(voucher_id: &[u8; 32]) -> Vec<u8> {
    let mut k = b"voucher_used:".to_vec();
    k.extend_from_slice(voucher_id);
    k
}

pub async fn is_voucher_used<S: StateStore>(store: &S, voucher_id: &[u8; 32]) -> Result<bool, ExecutionError>
where <S as StateStore>::Error: std::error::Error + Send + Sync + 'static {
    Ok(store
        .get_actor_storage(&cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, &voucher_used_key(voucher_id))
        .await
        .map_err(ExecutionError::from_store)?
        .is_some())
}

pub async fn mark_voucher_used<S: StateStore>(store: &mut S, voucher_id: &[u8; 32]) -> Result<(), ExecutionError>
where <S as StateStore>::Error: std::error::Error + Send + Sync + 'static {
    store
        .set_actor_storage(&cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, voucher_used_key(voucher_id), vec![1u8])
        .await
        .map_err(ExecutionError::from_store)
}
```

> Match the exact `store.get_actor_storage`/`set_actor_storage` + error-mapping idiom already used by the neighboring `read_bank`/`stablecoin_whitelist_contains` in this file (adapt if they use a different `StateStore` accessor signature).

- [ ] **Step 4: Run — verify pass**

Run: `cargo test -p cowboy-execution voucher_used_marker_roundtrip`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add execution/src/bank/storage.rs
git commit -m "bank: add voucher_used: replay-marker helpers (CIP-28 §2.1)"
```

---

### Task 10 (Part B): `FiatMintVoucher` verify helper + `FiatMinted` event/topic

**Files:**
- Modify: `execution/src/bank/mod.rs` (fields alias + preimage + verify); `execution/src/bank/handlers.rs:44-54` (topic const + encoder); `execution/src/consensus_event_topics.rs`.

- [ ] **Step 1: Write the failing tests**

```rust
// bank/mod.rs tests
#[test]
fn fiat_mint_voucher_verify_roundtrip_and_tamper() {
    use k256::ecdsa::SigningKey;
    let sk = SigningKey::from_bytes(&[0x22u8; 32].into()).unwrap();
    let signer = Address::from_verifying_key(sk.verifying_key());
    let v = FiatMintVoucherFields {
        bank_id: 1, card_address: addr(0xCA), token_id: [0x7C; 32],
        amount: 5_000_000, voucher_id: [0x33; 32], expires_at_block: 1000,
        fiat_reference: b"ch_abc".to_vec(),
    };
    let hash = fiat_mint_preimage_hash(&v);
    let (sig, rid) = sk.sign_prehash_recoverable(&hash).unwrap();
    let mut s = [0u8; 65]; s[..64].copy_from_slice(&sig.to_bytes()); s[64] = rid.to_byte();
    assert!(verify_fiat_mint_voucher(&v, &s, &signer).is_ok());
    let mut bad = v.clone(); bad.amount = 9_999_999;
    assert!(verify_fiat_mint_voucher(&bad, &s, &signer).is_err());
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-execution fiat_mint_voucher_verify_roundtrip_and_tamper`
Expected: FAIL.

- [ ] **Step 3: Implement in `bank/mod.rs`** (domain per CIP-28 §3.3; canonical fixed-layout, NOT RLP — the spec text says `rlp(voucher)` but the M-series banks all use the hand-rolled BE codec; **flag: we substitute the canonical BE preimage for RLP and pin it with a golden**, keeping one codec family across BankActor)

```rust
/// CIP-28 §3.3 signing domain. NOTE: the spec writes `rlp(voucher)`; M4 uses the
/// BankActor's canonical fixed-layout BE preimage (same family as BankEntry/CardEntry
/// and the card-derivation domain) instead of RLP, pinned by a golden vector.
pub const FIAT_MINT_DOMAIN: &[u8] = b"CowboyBankFiatMint\x01";

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FiatMintVoucherFields {
    pub bank_id: u32,
    pub card_address: Address,
    pub token_id: [u8; 32],
    pub amount: u128,
    pub voucher_id: [u8; 32],
    pub expires_at_block: u64,
    pub fiat_reference: Vec<u8>,
}

pub fn fiat_mint_preimage_hash(v: &FiatMintVoucherFields) -> [u8; 32] {
    let mut buf = Vec::with_capacity(FIAT_MINT_DOMAIN.len() + 4 + 20 + 32 + 16 + 32 + 8 + 2 + v.fiat_reference.len());
    buf.extend_from_slice(FIAT_MINT_DOMAIN);
    buf.extend_from_slice(&v.bank_id.to_be_bytes());
    buf.extend_from_slice(v.card_address.as_ref());
    buf.extend_from_slice(&v.token_id);
    buf.extend_from_slice(&v.amount.to_be_bytes());
    buf.extend_from_slice(&v.voucher_id);
    buf.extend_from_slice(&v.expires_at_block.to_be_bytes());
    // length-prefix the variable-length reference so it can't be shifted into an
    // adjacent field (canonicity).
    buf.extend_from_slice(&(v.fiat_reference.len() as u16).to_be_bytes());
    buf.extend_from_slice(&v.fiat_reference);
    keccak256(&buf)
}

pub fn verify_fiat_mint_voucher(
    v: &FiatMintVoucherFields, signature: &[u8; 65], expected_signer: &Address,
) -> Result<(), ExecutionError> {
    recover_and_check(&fiat_mint_preimage_hash(v), signature, expected_signer)
}
```

- [ ] **Step 4: Add a golden preimage vector** (bank/mod.rs tests) — assert `fiat_mint_preimage_hash(&FIXED)` equals a hard-coded 32-byte digest, so the preimage layout can never silently change (flag-day protection).

- [ ] **Step 5: Add the topic const + encoder** to `handlers.rs` (near `:44`)

```rust
pub const TOPIC_FIAT_MINTED: &str = "FiatMinted";

/// CIP-28 §3.6: FiatMinted { card, token, amount, voucher_id, fiat_reference }.
pub fn encode_fiat_minted(card: &Address, token_id: &[u8; 32], amount: u128, voucher_id: &[u8; 32], fiat_reference: &[u8]) -> Vec<u8> {
    let mut v = Vec::new();
    v.extend_from_slice(card.as_ref());
    v.extend_from_slice(token_id);
    v.extend_from_slice(&amount.to_be_bytes());
    v.extend_from_slice(voucher_id);
    v.extend_from_slice(&(fiat_reference.len() as u16).to_be_bytes());
    v.extend_from_slice(fiat_reference);
    v
}
```

- [ ] **Step 6: Register the topic** — add `"FiatMinted"` to `KNOWN_CONSENSUS_EVENT_TOPICS` in `consensus_event_topics.rs` (alphabetical within the CIP-28 block, after `"CardWithdrawn"` / before the CBSS block; keep the list sorted so the dedup assertion holds).

- [ ] **Step 7: Run — verify verify-helper + topic-guard pass**

Run: `cargo test -p cowboy-execution fiat_mint_voucher_verify consensus_event_topics_are_registered`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
cargo fmt --all
git add execution/src/bank/mod.rs execution/src/bank/handlers.rs execution/src/consensus_event_topics.rs
git commit -m "bank: FiatMintVoucher verify (CIP-28 §3.3) + FiatMinted event/topic registered (flag-day)"
```

---

### Task 11 (Part B): `bank_mint_from_fiat_voucher` handler + dispatch + emitter attribution

**Files:**
- Modify: `execution/src/execution/system_instruction.rs` (new method + dispatch arm — as a `self` method so it can call `self.handle_token_mint`).
- Modify: `storage/src/speculative.rs:427-437` (emitter arm).

- [ ] **Step 1: Write the failing end-to-end test** (`execution/src/execution/tests.rs`)

```rust
#[tokio::test]
async fn fiat_mint_credits_cusd_conserving_supply_and_blocks_replay() {
    // Seed CUSD (mint_authority=0x16) + bank1 (fiat_mint_signer=gateway) + an Active card.
    // Sign a FiatMintVoucher(amount=1_000_000) with the gateway key; dispatch opcode 210:
    //   - card CUSD balance == 1_000_000, TokenMint.total_supply == 1_000_000 (checked_add path)
    //   - a FiatMinted event attributed to 0x16 is emitted
    //   - re-dispatching the SAME voucher_id → Err (voucher_used), balance/supply unchanged
    //   - a voucher naming a non-0x16-authority token → TokenUnauthorized (guardrail)
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-execution fiat_mint_credits_cusd_conserving_supply`
Expected: FAIL — no `BankMintFromFiatVoucher` dispatch.

- [ ] **Step 3: Add the dispatch arm** (in the bank match, alongside the others). Because 210 rides a Bank* system instruction, add it to the outer `matches!(...)` classifier at `system_instruction.rs:4956` too.

```rust
                    cowboy_types::SystemInstruction::BankMintFromFiatVoucher { voucher, signature } => self
                        .bank_mint_from_fiat_voucher(store, voucher, signature, gas_meters, block_height)
                        .await
                        .map(|_| None),
                    cowboy_types::SystemInstruction::BankSettleProvider { provider, amount, settlement_id } => self
                        .bank_settle_provider(store, provider, *amount, settlement_id, gas_meters)
                        .await
                        .map(|_| None),
```

- [ ] **Step 4: Implement `bank_mint_from_fiat_voucher`** (a `self` method near `bank_deposit`, so `self.handle_token_mint` and `self.system_events` are reachable)

```rust
/// CIP-28 §3.3 + CIP-36 §6.1/§6.3. Check-then-apply (no rollback on Err):
/// validate signature + replay + expiry + bank/card status BEFORE any write, then
/// mint via the CIP-20 accounting AS the BankActor (0x16) and record voucher_used.
async fn bank_mint_from_fiat_voucher<S: StateStore>(
    &mut self,
    store: &mut S,
    voucher: &cowboy_protocol_codec::FiatMintVoucher,
    signature: &[u8; 65],
    gas_meters: &mut DualGasMeters,
    block_height: u64,
) -> Result<(), ExecutionError>
where <S as StateStore>::Error: std::error::Error + Send + Sync + 'static {
    // ── validate (all reads, no writes) ──
    let bank = crate::bank::storage::read_bank(store, voucher.bank_id).await?
        .ok_or(ExecutionError::InvalidData)?;
    if bank.status != crate::bank::BankStatus::Active {
        return Err(ExecutionError::InvalidData);
    }
    let signer = bank.fiat_mint_signer.ok_or(ExecutionError::InvalidData)?;
    if block_height > voucher.expires_at_block {
        return Err(ExecutionError::InvalidData);
    }
    if crate::bank::storage::is_voucher_used(store, &voucher.voucher_id).await? {
        return Err(ExecutionError::InvalidData); // replay
    }
    let card = crate::bank::storage::read_card(store, &voucher.card_address).await?
        .ok_or(ExecutionError::InvalidData)?;
    if card.status == crate::bank::CardStatus::Closed {
        return Err(ExecutionError::InvalidData);
    }
    let token_id = match voucher.token {
        cowboy_types::PayCurrency::Token(id) => id,
        cowboy_types::PayCurrency::Native => return Err(ExecutionError::InvalidData), // fiat mint is CUSD only
    };
    let vf = crate::bank::FiatMintVoucherFields {
        bank_id: voucher.bank_id, card_address: voucher.card_address, token_id,
        amount: voucher.amount, voucher_id: voucher.voucher_id,
        expires_at_block: voucher.expires_at_block, fiat_reference: voucher.fiat_reference.clone(),
    };
    crate::bank::verify_fiat_mint_voucher(&vf, signature, &signer)?;

    // ── apply: mint through CIP-20 accounting as 0x16 (total_supply.checked_add,
    //    MAX_TOKEN_SUPPLY, mint_authority==0x16 all enforced there) ──
    self.handle_token_mint(
        store, &token_id, &voucher.card_address, voucher.amount,
        &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, gas_meters,
    ).await?;
    crate::bank::storage::mark_voucher_used(store, &voucher.voucher_id).await?;
    self.system_events.push((
        crate::bank::handlers::TOPIC_FIAT_MINTED.to_string(),
        crate::bank::handlers::encode_fiat_minted(
            &voucher.card_address, &token_id, voucher.amount, &voucher.voucher_id, &voucher.fiat_reference,
        ),
    ));
    Ok(())
}
```

> `handle_token_mint` emits its own `TokenMinted` event (already registered) in addition to `FiatMinted`; both are correct (the CIP-20 mint receipt + the CIP-28 bridge receipt). Confirm `read_card`/`CardStatus`/`BankStatus` are the actual public paths.

- [ ] **Step 5: Add emitter attribution** — in `speculative.rs:427-437`, add the two new variants to the Bank* arm:

```rust
            SystemInstruction::BankIssueCard { .. }
            // … existing ten …
            | SystemInstruction::BankUnpauseBank { .. }
            | SystemInstruction::BankMintFromFiatVoucher { .. }
            | SystemInstruction::BankSettleProvider { .. } => Some(BANK_ACTOR_SYSTEM_ACTOR),
```

- [ ] **Step 6: Run — verify pass**

Run: `cargo test -p cowboy-execution fiat_mint_credits_cusd_conserving_supply -- --nocapture`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cargo fmt --all
git add execution/src/execution/system_instruction.rs storage/src/speculative.rs
git commit -m "bank: MintFromFiatVoucher handler — supply-conserving CUSD mint via CIP-20 as 0x16 (CIP-28 §3.3 / CIP-36 §6.1)"
```

---

### Task 12 (Part C): `settlement_used:` storage helpers

**Files:**
- Modify: `execution/src/bank/storage.rs`.

- [ ] **Step 1: Write the failing test**

```rust
#[tokio::test]
async fn settlement_used_marker_roundtrip() {
    let mut s = TestStore::default();
    let sid = [0x44u8; 32];
    assert!(!is_settlement_used(&s, &sid).await.unwrap());
    mark_settlement_used(&mut s, &sid).await.unwrap();
    assert!(is_settlement_used(&s, &sid).await.unwrap());
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-execution settlement_used_marker_roundtrip`
Expected: FAIL.

- [ ] **Step 3: Implement** (author-specified key `b"settlement_used:" ‖ settlement_id_32`, mirroring `voucher_used_key`)

```rust
pub fn settlement_used_key(settlement_id: &[u8; 32]) -> Vec<u8> {
    let mut k = b"settlement_used:".to_vec();
    k.extend_from_slice(settlement_id);
    k
}
// is_settlement_used / mark_settlement_used: byte-for-byte the voucher_used pair,
// substituting settlement_used_key.
```

- [ ] **Step 4: Run — verify pass**

Run: `cargo test -p cowboy-execution settlement_used_marker_roundtrip`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add execution/src/bank/storage.rs
git commit -m "bank: add settlement_used: consumed-set helpers (CIP-36 §6.3, author-specified key)"
```

---

### Task 13 (Part C): `ProviderSettled` event/topic

**Files:**
- Modify: `execution/src/bank/handlers.rs`; `execution/src/consensus_event_topics.rs`.

- [ ] **Step 1: Add the topic const + encoder** (`handlers.rs`, near `:44`)

```rust
pub const TOPIC_PROVIDER_SETTLED: &str = "ProviderSettled";

/// CIP-36 §6.3: ProviderSettled { provider, amount, settlement_id }.
pub fn encode_provider_settled(provider: &Address, amount: u128, settlement_id: &[u8; 32]) -> Vec<u8> {
    let mut v = Vec::with_capacity(20 + 16 + 32);
    v.extend_from_slice(provider.as_ref());
    v.extend_from_slice(&amount.to_be_bytes());
    v.extend_from_slice(settlement_id);
    v
}
```

- [ ] **Step 2: Register** — add `"ProviderSettled"` to `KNOWN_CONSENSUS_EVENT_TOPICS` (sorted, after `"ManifestCommitted"` / before `"SessionClosing"`, or wherever alphabetical order places it).

- [ ] **Step 3: Run — verify the topic guard**

Run: `cargo test -p cowboy-execution consensus_event_topics_are_registered`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
cargo fmt --all
git add execution/src/bank/handlers.rs execution/src/consensus_event_topics.rs
git commit -m "bank: ProviderSettled event/topic registered (CIP-36 §6.3, flag-day)"
```

---

### Task 14 (Part C): `bank_settle_provider` handler + dispatch

**Files:**
- Modify: `execution/src/execution/system_instruction.rs` (the dispatch arm was added in Task 11 Step 3; add the method).

- [ ] **Step 1: Write the failing end-to-end test** (`tests.rs`)

```rust
#[tokio::test]
async fn settle_provider_burns_cusd_check_then_apply_idempotent() {
    // Seed CUSD (burn_from_authority=0x16) + a provider with balance 1_000_000.
    // Caller = bank operator. Dispatch opcode 211 { provider, amount:400_000, settlement_id }:
    //   - provider balance 600_000, total_supply -= 400_000 (checked_sub), ProviderSettled@0x16
    //   - re-dispatch SAME settlement_id → Ok NO-OP, NO event, balance/supply unchanged (idempotent)
    //   - amount 700_000 on the now-600_000 balance, fresh settlement_id → Err insolvent, no write
    //   - caller != operator → Unauthorized, no write
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-execution settle_provider_burns_cusd_check_then_apply_idempotent`
Expected: FAIL.

- [ ] **Step 3: Implement `bank_settle_provider`** (a `self` method; `caller`/`sender` is the tx signer — thread it in from dispatch)

```rust
/// CIP-36 §6.3. Idempotent, check-then-apply, gateway-authorized. An already-consumed
/// settlement_id is an Ok no-op (emits nothing). Burns via CIP-20 burn_from as 0x16.
async fn bank_settle_provider<S: StateStore>(
    &mut self,
    store: &mut S,
    provider: &Address,
    amount: u128,
    settlement_id: &[u8; 32],
    caller: &Address,             // = tx.from; thread from dispatch (`sender`)
    gas_meters: &mut DualGasMeters,
) -> Result<(), ExecutionError>
where <S as StateStore>::Error: std::error::Error + Send + Sync + 'static {
    // Authorization: caller MUST be bank 1's operator (the compliance-gateway authority).
    let bank = crate::bank::storage::read_bank(store, 1).await?.ok_or(ExecutionError::InvalidData)?;
    if *caller != bank.operator {
        return Err(ExecutionError::Unauthorized);
    }
    // Idempotent replay: already-consumed → Ok no-op, emit nothing, no re-burn.
    if crate::bank::storage::is_settlement_used(store, settlement_id).await? {
        return Ok(());
    }
    // Apply: record consumed + burn exactly `amount` CUSD from provider, settlement_id in reason.
    // burn_from validates burn_from_authority==0x16 and balance>=amount BEFORE mutating
    // (check-then-apply), so record-then-burn cannot strand a consumed id with no burn:
    // if the burn Errs (insolvent), we must NOT have recorded — so burn FIRST, then record.
    self.handle_token_burn_from(
        store, &cowboy_types::constants::CUSD_TOKEN_ID, provider, amount,
        settlement_id, &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, gas_meters,
    ).await?;
    crate::bank::storage::mark_settlement_used(store, settlement_id).await?;
    self.system_events.push((
        crate::bank::handlers::TOPIC_PROVIDER_SETTLED.to_string(),
        crate::bank::handlers::encode_provider_settled(provider, amount, settlement_id),
    ));
    Ok(())
}
```

> **Ordering subtlety (bake in):** CIP-36 §6.3 says "record-then-burn would strand a consumed id if the burn traps." Under the no-rollback engine, the safe order is **burn first (it is itself check-then-apply and writes nothing on the insolvent path), then mark consumed** — so an insolvent settle records nothing, and a successful burn is always paired with the consumed marker. Update the dispatch arm (Task 11 Step 3) to pass `sender` as `caller`.

- [ ] **Step 4: Run — verify pass**

Run: `cargo test -p cowboy-execution settle_provider_burns_cusd_check_then_apply_idempotent -- --nocapture`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add execution/src/execution/system_instruction.rs
git commit -m "bank: settle_provider handler — idempotent gateway-authorized CUSD burn_from as 0x16 (CIP-36 §6.3)"
```

---

### Task 15: Activation gate + pause gate for opcodes 210/211

**Files:**
- Modify: `chain/src/application.rs:2519` (`tx_is_bank_v2`), `:2665` (RC8 test); `execution/src/execution/bank_pause_gate.rs`; `types/src/constants.rs:660-683` (doc comment).

- [ ] **Step 1: Extend the RC8 test** (`application.rs`, add a case in / alongside `bank_m3_opcodes_205_to_209_gated_below_activation`)

```rust
#[test]
fn bank_m4_opcodes_210_211_gated_below_activation() {
    let sk = test_key(1);
    let mk = |inst: SystemInstruction| Transaction::sign(&sk, 0, 0, Instruction::System(Box::new(inst)), 50_000, 50_000, 1, 1);
    let mint = mk(SystemInstruction::BankMintFromFiatVoucher {
        voucher: /* minimal FiatMintVoucher */,
        signature: [0u8; 65],
    });
    let settle = mk(SystemInstruction::BankSettleProvider {
        provider: Address::from_low_u64(0xDD), amount: 1, settlement_id: [0u8; 32],
    });
    assert!(tx_is_bank_v2(&mint), "210 must be gated");
    assert!(tx_is_bank_v2(&settle), "211 must be gated");
    let rejected = |h: u64, txs: &[Transaction]| h < cowboy_types::BANK_ACTIVATION_HEIGHT && block_has_bank_v2_tx(txs);
    assert!(rejected(1, &[mint.clone()]));
    assert!(rejected(1, &[settle.clone()]));
    assert!(!rejected(cowboy_types::BANK_ACTIVATION_HEIGHT, &[mint]));
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-chain bank_m4_opcodes_210_211_gated_below_activation`
Expected: FAIL — variants not matched by `tx_is_bank_v2`.

- [ ] **Step 3: Extend `tx_is_bank_v2`** (`:2521`)

```rust
        cowboy_types::Instruction::System(inner) => matches!(
            **inner,
            cowboy_types::SystemInstruction::BankSetDefaultCard { .. }
                | cowboy_types::SystemInstruction::BankSetPolicy { .. }
                | cowboy_types::SystemInstruction::BankFreeze { .. }
                | cowboy_types::SystemInstruction::BankUnfreeze { .. }
                | cowboy_types::SystemInstruction::BankPauseBank { .. }
                | cowboy_types::SystemInstruction::BankUnpauseBank { .. }
                | cowboy_types::SystemInstruction::BankMintFromFiatVoucher { .. }
                | cowboy_types::SystemInstruction::BankSettleProvider { .. }
        ),
```

> **Opcode 200 decision (Scope §1):** the reshaped `BankIssueCard` stays **out** of `tx_is_bank_v2`. 200-203 were never gated (they were live at the M1 re-genesis), and M4 re-genesis's again with `BANK_ACTIVATION_HEIGHT = 0`, so a legacy node never coexists with the reshaped 200 on the same chain. Gating 200 now would only matter on an in-place upgrade, which M4 explicitly is not. Document this in the `tx_is_bank_v2` doc comment.

- [ ] **Step 4: Add both instrs to the pause-gate classifier** (`bank_pause_gate.rs` `system_instruction_targets_bank`)

```rust
        SystemInstruction::BankUnpauseBank { .. }
            | SystemInstruction::BankMintFromFiatVoucher { .. }
            | SystemInstruction::BankSettleProvider { .. }
```

> **Pause semantics (Scope note):** the Council actor-pause of `0x16` halts **all** bank entry points including `withdraw`, so both 210 and 211 belong in this classifier (defense-in-depth). Separately, the **per-bank** `bank.status == Paused` (PauseBank) is enforced inside the handlers: `MintFromFiatVoucher` requires `bank.status == Active` (Task 11, per CIP-28 §3.3), while `settle_provider` does **not** check `bank.status` — it mirrors `withdraw`, which §3.3 keeps allowed under a per-bank pause (settlement is an operator wind-down action).

- [ ] **Step 5: Update the `BANK_ACTIVATION_HEIGHT` doc comment** (`constants.rs:672`) — change "opcodes 204 `BankSetDefaultCard` through 209 `BankUnpauseBank`" to "opcodes 204-209 (M2/M3) plus 210 `BankMintFromFiatVoucher` / 211 `settle_provider` (M4)".

- [ ] **Step 6: Run — verify pass**

Run: `cargo test -p cowboy-chain bank_m4_opcodes_210_211_gated && cargo test -p cowboy-execution bank_pause_gate`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cargo fmt --all
git add chain/src/application.rs execution/src/execution/bank_pause_gate.rs types/src/constants.rs
git commit -m "bank: gate opcodes 210/211 in tx_is_bank_v2 + Council-pause classifier (CIP-28 M4)"
```

---

### Task 16: Mint→burn supply-conservation invariant

**Files:**
- Modify: `execution/src/econ_invariants.rs` (near `econ_token_supply_conservation`, `:632`).

- [ ] **Step 1: Write the failing test**

```rust
#[tokio::test]
async fn econ_fiat_mint_then_settle_round_trips_supply() {
    // Seed CUSD (mint_authority=burn_from_authority=0x16, total_supply=0).
    // mint 1_000_000 to a card (as 0x16) → total_supply == 1_000_000, Σ balances == supply.
    // burn_from 400_000 from the card (as 0x16, reason=settlement_id) → total_supply == 600_000,
    // Σ balances == supply. Assert conservation holds after each op — never a raw write.
    let token_id = cowboy_types::constants::CUSD_TOKEN_ID;
    let mut store = TestStore::default();
    seed_cusd_token(&mut store, token_id); // mint/burn authority = 0x16, supply 0
    let mut engine = ExecutionEngine::new();
    let mut gas = DualGasMeters::new(10_000_000, 10_000_000);
    let card = tok_addr(1);
    engine.handle_token_mint(&mut store, &token_id, &card, 1_000_000, &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, &mut gas).await.unwrap();
    assert_supply_conserved(&store, &token_id).await.unwrap();
    engine.handle_token_burn_from(&mut store, &token_id, &card, 400_000, &[0x44u8;32], &cowboy_types::BANK_ACTOR_SYSTEM_ACTOR, &mut gas).await.unwrap();
    assert_supply_conserved(&store, &token_id).await.unwrap();
    let supply = get_token_mint(&store, &token_id).await.unwrap().unwrap().total_supply;
    assert_eq!(supply, 600_000);
}
```

- [ ] **Step 2: Run — verify it fails**

Run: `cargo test -p cowboy-execution econ_fiat_mint_then_settle_round_trips_supply`
Expected: FAIL until `seed_cusd_token` helper is added (mirror `seed_conservation_token` at `econ_invariants.rs` but set both authorities to `0x16`).

- [ ] **Step 3: Add the `seed_cusd_token` helper** (mirror `seed_conservation_token`, set `mint_authority` and `burn_from_authority` to `BANK_ACTOR_SYSTEM_ACTOR`).

- [ ] **Step 4: Run — verify pass**

Run: `cargo test -p cowboy-execution econ_fiat_mint_then_settle_round_trips_supply econ_token_supply_conservation`
Expected: PASS (both — the existing proptest stays green).

- [ ] **Step 5: Commit**

```bash
cargo fmt --all
git add execution/src/econ_invariants.rs
git commit -m "test: fiat mint+settle round-trips CUSD total_supply (conservation, CIP-36 §6.3)"
```

---

### Task 17: Full-suite verification

- [ ] **Step 1: Format + clippy + workspace tests**

Run:
```bash
cd /home/ubuntu/workspace/node
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```
Expected: all green. Specifically confirm `consensus_event_topics_are_registered`, `econ_token_supply_conservation`, `sys_opcode_uniqueness` (codec), and every `bank_*` test pass.

- [ ] **Step 2: Devnet smoke (re-genesis)**

Run: `./scripts/run_build.sh` then start a validator; confirm genesis seeds CUSD + `fiat_mint_signer` and a signed `MintFromFiatVoucher` mints CUSD to a card (via CLI or an example). If an `examples/` flow exists for banking, run it with `--test`.

- [ ] **Step 3: Commit any smoke-fix follow-ups** (none expected).

---

## Cross-repo finalize (user-gated — no push without authorization)

Mirrors M1/M2/M3.

1. **cowboy-protocol first.** Push `feat/cip28-m4-fiat-vouchers`; open PR base `main`; land it. **Squash re-pin lesson:** after merge, re-pin the node to the **merged `origin/main` sha** (`git rev-parse origin/main`), NOT the feature-branch sha — squash rewrites history, and pinning the dead branch sha builds a codec that never reaches main.
2. **node second.** With the codec merged, ensure Task 5's `rev` is the merged main sha (re-run `sed` if the sha differs from the placeholder), `cargo build` to refresh `Cargo.lock`, then push `feat/cip28-m4-fiat-issuance`; open PR **base `devnet`** (repo has a `devnet` branch → base is `devnet`, per MEMORY `feedback_node_pr_base_devnet`).
3. **PR customer summary** (English PR body, per MEMORY): state plainly what M4 adds (fiat mint, provider settlement, gateway-signed card consent), that it is a re-genesis milestone (breaking opcode-200 wire change absorbed by re-genesis), the flag-day event topics, and that supply is conserved through CIP-20 accounting. Do not overstate (CUSD transfer-hook policy §6.2 and `SetBankFiatMintSigner` rotation are explicitly deferred).
4. Do not push or open either PR until the user authorizes.

---

## Self-Review

**Spec coverage** (each requirement → task):
- CIP-28 §3.3 `MintFromFiatVoucher` + `FiatMintVoucher` + signing domain → Tasks 1, 3 (codec), 10, 11.
- CIP-28 §2.1 `voucher_used:` key → Task 9.
- CIP-28 §3.6 `FiatMinted` event → Task 10.
- CIP-36 §6.1 CUSD `mint_authority = 0x16`, 1:1 mint → Tasks 6, 11.
- CIP-36 §6.3 `settle_provider` idempotent check-then-apply + consumed-set + `burn_from` wrap → Tasks 3, 12, 13, 14.
- CIP-36 §7 `IssuancePrincipalVoucher` consent, immutable `issuance_principal`, nonce/expiry replay → Tasks 1, 2 (codec), 7, 8.
- CIP-36 §11 CUSD `burn_from_authority = 0x16` opt-in → Task 6 (genesis seed).
- Supply conservation (CIP-3/CIP-20) → all mint/burn via `handle_token_*`; Task 16.
- Activation + pause gating + flag-day → Tasks 13, 15; topic registration Tasks 10, 13.
- Provisioning exercisable → Task 6.

**Placeholder scan:** the only intentionally-abbreviated bodies are the three end-to-end `tests.rs` tests (Tasks 8, 11, 14) and the RC8 minimal `FiatMintVoucher` literal — each states exactly what to assert and which existing harness to mirror, because the concrete seed helpers differ per test module. All handler/codec/storage code is complete.

**Type consistency:** `FiatMintVoucher`/`IssuancePrincipalVoucher` (codec wire types) vs `FiatMintVoucherFields`/`IssuancePrincipalVoucherFields` (node preimage types) are deliberately distinct — the codec type lives in `cowboy-protocol`, the node reconstructs the preimage struct. `verify_fiat_mint_voucher`, `verify_issuance_principal_voucher`, `recover_and_check`, `voucher_used_key`/`settlement_used_key`, `TOPIC_FIAT_MINTED`/`TOPIC_PROVIDER_SETTLED`, `bank_mint_from_fiat_voucher`/`bank_settle_provider` are used with identical names throughout. `handle_token_mint(store, token_id, to, amount, caller, gas_meters)` and `handle_token_burn_from(store, token_id, from, amount, reason, caller, gas_meters)` match the baseline signatures at `token/core.rs:716`/`:840`.

## Verification matrix (test per spec requirement)

| Spec requirement | Test | Task |
|---|---|---|
| Opcodes 210/211 fixed; voucher structs round-trip | `bank_m4_opcodes_are_210_211`, `*_struct_round_trips` | 1 |
| Reshaped 200 round-trips | `bank_issue_card_*_round_trips_at_200` | 2 |
| 210/211 wire round-trip | `bank_mint_from_fiat_voucher_round_trips_at_210`, `bank_settle_provider_round_trips_at_211` | 3 |
| Genesis seeds CUSD (auth 0x16) + signer | `genesis_seeds_cusd_mint_and_fiat_signer` | 6 |
| Consent voucher verify + tamper reject | `issuance_principal_voucher_verify_roundtrip_and_tamper` | 7 |
| IssueCard rejects unsigned, accepts signed; DoS closed | `issue_card_rejects_unsigned_voucher_but_accepts_gateway_signed` | 8 |
| `voucher_used:` replay marker | `voucher_used_marker_roundtrip` | 9 |
| Fiat voucher verify + canonical preimage golden | `fiat_mint_voucher_verify_roundtrip_and_tamper` + golden | 10 |
| Fiat mint conserves supply, blocks replay, guards non-0x16 token | `fiat_mint_credits_cusd_conserving_supply_and_blocks_replay` | 11 |
| `settlement_used:` consumed-set | `settlement_used_marker_roundtrip` | 12 |
| Topics registered (flag-day) | `consensus_event_topics_are_registered` | 10, 13 |
| Settle idempotent check-then-apply + auth | `settle_provider_burns_cusd_check_then_apply_idempotent` | 14 |
| 210/211 activation-gated | `bank_m4_opcodes_210_211_gated_below_activation` | 15 |
| Council-pause halts 210/211 | `bank_pause_gate` (extended classifier) | 15 |
| Mint+burn round-trips total_supply | `econ_fiat_mint_then_settle_round_trips_supply` + `econ_token_supply_conservation` | 16 |

---

**Plan complete. Two execution options:**
1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks (REQUIRED SUB-SKILL: superpowers:subagent-driven-development).
2. **Inline Execution** — batch execution with checkpoints (REQUIRED SUB-SKILL: superpowers:executing-plans).
