# CIP-36 Phased Launch (cUSD) — Development Backlog

- **Date**: 2026-07-19
- **Scope**: CIP-36 Phased Launch / Testnet Credits (cUSD) + Mainnet Airdrop, together with its dependencies CIP-18 (Payments), CIP-20 (Fungible Tokens), CIP-28 (Agent Banking)
- **Source of truth**: `cowboy/docs/cips/cip-36-phased-launch-cusd.md`, `cip-18-payments.md`, `cip-28-cowboy-agent-banking.md`
- **Method**: spec cross-checked line-by-line against the current code baseline (4 parallel node/ probes, 2026-07-19)
- **One-line conclusion**: CIP-36 adds almost no new mechanism of its own; its weight lands entirely on the three CIPs it amends. Of those, PaymentGate already has M1 and the CIP-20 transfer hook is fully built — but `burn_from` and the entire CIP-28 BankActor are essentially at zero.

---

## 1. Baseline (spec ↔ current code)

| Dependency | Spec requires | Current code | Gap |
|---|---|---|---|
| **PaymentGate 0x12** (CIP-18) | Settlement layer | **M1 landed**: policy/budget/pass/epoch/verify/settle all in `execution/src/payment_gate/`, live from genesis | single-recipient direct transfer; only 5% protocol fee; single asset; no escrow-hop; no `credit_inbound`/bridge |
| **CIP-20 transfer hook** | `can_transfer(4-arg)` + 50k/50k budget | **Fully landed** (`token/core.rs:179`, incl. reentrancy guard, dual-metered sub-budget) | none |
| **CIP-20 `burn_from`** | third-party burn + immutable `burn_from_authority` | **Absent entirely**. Only self-burn; burn has no authority gate | whole primitive + field |
| **CIP-20 mint authority** | system actor as mint authority | mechanically works (`mint_authority` is a plain Address compared to the caller) | no "immutable / system-actor" semantic layer |
| **BankActor** (CIP-28) | 0x16, card model, instruction set, charge_gas, fiat voucher | **spec-only** (UI demo + timer-sponsor primitive COW-1141 only); `0x16` unassigned in code | nearly all of it |
| **tx `fee_payer_override`** | tx top-level field | **absent** (only `ScheduledTimer.fee_payer_override`, a timer subsystem field); canonical tx lives in `cowboy-protocol-codec` | cross-repo codec field |
| **admission anti-spam** | funded gate + per-principal quota | nonce mempool + rate-limit + can-pay-own-gas check present; **funded gate / per-principal quota absent** | two gates |
| **test-CBY / testnet gas** | hidden gas token, auto-grant on funding, genesis gas schedule | manual faucet only; `MIN_BASEFEE=10_000` is a **compile-time const**, not a genesis param; genesis has no gas/fee fields | new concept |
| **issuance_principal** | signed voucher stamped on card | **zero** | new |
| **Compliance Gateway / Stripe / airdrop metrics** | off-chain | **zero** (audit-bot/cowpilot unrelated) | new off-chain services |

Legend: 🔴 = consensus / flag-day (execution layer, coordinated rollout) · 🟡 = off-chain / client (non-consensus) · 🟢 = governance / legal gate · ⛓️ = cross-repo codec

---

## 2. Development backlog (by workstream + dependency order)

### W1 · CIP-20 `burn_from` primitive (**foundation for everything — do first**) 🔴
1. Add **immutable** `burn_from_authority: Option<Address>` to `TokenMint`, fixed at creation, default `None` (`token/src/types.rs`, incl. three codec round-trip sites) ⛓️
2. `burn_from(token, account, amount, reason)` handler: **validate first** (authority + reason length + `amount ≤ balance(account)`, which also guarantees `amount ≤ total_supply`), **then atomically decrement** (balance + total_supply), emit `Burn{token,authority,account,amount,reason}`. Must be check-then-apply (the engine does not roll back partial writes — the pay-then-fail conservation gap)
3. New `SystemInstruction` opcode (next free slot) + 4 codec sites + authority check
4. Regression tests: insolvent rejects with zero writes, underflow impossible, non-authority rejected, default-None token has no such power

### W2 · CIP-18 PaymentGate extension (cUSD billing path) 🔴
5. **Multi-asset**: extend `PaymentPolicy` from a single `asset` to an accepted-asset set (add cUSD); settle validates set membership
6. **Escrow-hop + arbitrary multi-party payout**: payer → PG → N recipients (runner + aggregator + protocol/gateway). Current is `debit(payer)→credit(treasury)` single-recipient direct transfer — must become escrow-through-PG then split
7. **Check-then-apply all-or-nothing**: all legs (payer solvency, each recipient, split sums to escrowed amount) **validated before any write** (same as W1, engine does not revert)
8. Regression: split conservation, any leg failure → zero state change, cUSD hook permits `→PG` / `PG→any`

### W3 · CIP-28 BankActor (largest effort; CIP-36 needs only a subset but cannot bypass it) 🔴
> CIP-36 needs CIP-28's M1 (cards) + M4 (fiat bridge) + issuance_principal. M3 policy triad and M5 multi-bank are not strictly required for launch but are bundled in the spec.

9. **Land BankActor at `0x16`**: add `BANK_ACTOR=0x16` to `system_actors.rs` (currently free), register in the `ALL` table and the pausable set, cover it in the `pvm_host` reserved band. **Decide the activation mechanism** (reserved-band constant vs `call_actor` interception, the CIP-29 0x1D pattern) — CIP-36 §13 item 1, left to the CIP-28 activation PR
10. **Card data model**: `CardEntry`/`BankEntry`/`CardPolicy`/`SpendWindow` + card-address derivation (keccak `CowboyBankCard\x01 ‖ bank_id ‖ owner ‖ agent ‖ nonce`) + index key-space
11. **Instruction set** (new `BankInstruction` + per-op opcodes ⛓️): M1 `IssueCard`/`Deposit`/`Withdraw`/`CloseCard`/`SetDefaultCard`; M4 `MintFromFiatVoucher` (replay-protection `voucher_used:` set) + `SetBankFiatMintSigner`; (M3/M5) `SetPolicy`/`Freeze`/`Unfreeze`/`PauseBank`/`RegisterBank`/`TransferOwnership`
12. **tx top-level `fee_payer_override: Option<Address>`**: add the field to `Transaction` in `cowboy-protocol-codec` (⛓️ cross-repo; wallet must stay byte-compatible) + the fee-settle fork point (§2.7 resolution order) + `BankActor.charge_gas` Phase 1 reserve / Phase 2 settle (follow CIP-3 dual-metering, snapshot both basefees; use `block_on_local`, not `futures::block_on`)
13. **`bank_activation_height` governance parameter** + height gate (below = treat as missing EOA → OutOfFunds, byte-identical zero fork)
14. **cUSD token instance**: create cUSD at genesis or via a deploy script (decimals=6, `mint_authority`=BankActor, `burn_from_authority`=BankActor, `transfer_hook`=allowlist), write the §6.2 hook logic (`card/account→PG`, `PG→any`, `BANK→card`, `card↔owner`)
15. **`settle_provider(provider, n, settlement_id)`**: gateway-authorized, idempotent, check-then-apply, wraps `burn_from` (depends on W1), consumed-set lives in this wrapper

### W4 · Admission anti-spam (testnet is operator-run, so this is mempool/RPC policy — **non-consensus**) 🟡
16. **Funded-account gate**: after fee-payer resolution, check cUSD balance ≥ `min_funded_balance` (default $0.50); a resolution failure is always **rejected**, never treated as allowlisted (`rpc/handlers/chain.rs` admission)
17. **Per-principal per-block quota** `max_admissions_per_principal_per_block` (default ~8), keyed by **canonical principal** (EOA = address; card = immutable `issuance_principal`)
18. **issuance_principal read**: admission reads the signed on-chain principal (reads parent-block state to stay deterministic)
19. Optional `admission_charge` (default 0) metered backstop (§13 item 4)

### W5 · test-CBY and the testnet gas schedule 🔴 (genesis) / 🟡 (grant)
20. **Parameterize MIN_BASEFEE**: turn the compile-time `MIN_BASEFEE=10_000` const into a network/genesis-settable value (add a gas/basefee block to `GenesisConfig`, seed `BasefeeConfig`) — so the testnet can run its own schedule
21. **test-CBY "hidden gas token"**: can reuse existing CBY on the CIP-3 gas path (the spec explicitly **does not add** a `launch_mode`/zero-basefee consensus change) — the essence is the grant + client hiding, not a new token mechanism
22. **Auto-grant on funding**: when cUSD is deposited, BankActor grants that account enough test-CBY (grant sizing §13 item 3; off-chain or system tx; must stay anti-spam)

### W6 · Off-chain Compliance Gateway (new service) 🟡🟢
23. **Stripe integration + FiatMintVoucher issuance**: sign the voucher after the chargeback window has settled → `MintFromFiatVoucher` (§6.3 endpoints)
24. **issuance_principal derivation**: `HMAC(gateway_secret, "cowboy/issuance-principal/v1" ‖ compliance_id)`, **rotation-stable** (HSM / persistent registry), signs `IssuancePrincipalVoucher{bank_id,issuance_principal,owner_or_agent,nonce,expiry}`
25. **settlement_id issuance**: gateway-assigned unique (`HMAC(gateway_secret, payable_ref)`), reconciled against the off-chain fiat payable
26. **Gateway key custody** (§13 item 6): HSM, rotation policy, monitoring for anomalous principal issuance (a single compromised key = money printer / multiplied principals; this is a launch-security control, not a consensus guarantee)

### W7 · Mainnet airdrop framework 🟢
27. **Reproducible metrics pipeline**: cUSD spend / verified job volume / uptime, snapshot rule, published before distribution
28. **Sybil/wash resistance**: exclude self-dealing round-trips (same `issuance_principal`), defend against the two-identity split (weight *verified* job output over gross spend, cap per-principal contribution)
29. **Governance ratification** (§13 item 2): setting the WP §8.3 Community/Airdrops **eligibility basis** from "2 drops" to testnet metrics — supply/bucket size unchanged, but the basis MUST be ratified through the genesis-parameter / governance process (**must not be asserted as "unchanged"**)

### W8 · Client UX 🟡
30. Dashboard/CLI/desktop **never display a test-CBY balance**, never ask the user to manage gas
31. **Funded-account funding flow**: USD→cUSD, card balance, statement view (join `GasCharged`/`FiatMinted` events)

### W9 · Companion deliverables (informative, delivered separately) 🟡
32. **Harness demos**: finance/trading harness, API-key manager, GPU-procurement router, search entry point (MCP/CLI)
33. **Proof-of-traceability**: strengthen runner result provenance (separate PR, referenced by §8/§12)

### W10 · Gates / open items (not code, but launch-blocking) 🟢
34. **Legal**: counsel sign-off on the cUSD "not a stablecoin, non-transferable, non-redeemable prepaid credit" characterization (§13 item 7, launch gate)
35. **cUSD hook cross-actor read**: confirm the `card→owner` resolution fits the 50k/50k hook budget; if not, drop the `card↔owner` flow (cUSD stays card-resident) (§13 item 8)
36. **cUSD provider payout rails**: fiat/USDC settlement spec required before third-party providers onboard (§13 item 5, needs its own spec)

---

## 3. Critical path and notes

- **Dependency chain**: W1 (`burn_from`) → blocks W2 `settle_provider`, W3 cUSD creation, and W15. **Do W1 first.** BankActor (W3 #9–14) blocks issuance_principal / fiat mint / card gas — the second critical path.
- **flag-day cluster**: W1/W2/W3/W5#20 are all execution-layer or persistent config-schema changes → mixed-version fork class; coordinate a single activation height. Adding `fee_payer_override` to tx and new `BankInstruction` opcodes is cross-repo codec (node + `cowboy-protocol-codec` + wallet, same day).
- **Hold the "zero new consensus" claims**: CIP-36 deliberately **adds no** governance op, **no** `launch_phase` register, **no** zero-basefee consensus change, and **changes no** mainnet tokenomics. If implementation reveals you need to touch these, you have deviated from the spec — back up.
- **Admission is testnet mempool policy, non-consensus** (operator-run), which lets W4 land relatively lightly and off the ratchet; but the funded gate/quota MUST read **parent-block state** to stay deterministic.
- **CIP-21/22 out of scope**, CIP-13 dormant, CIP-2/3/23 unchanged — do not touch them in this batch.
</content>
