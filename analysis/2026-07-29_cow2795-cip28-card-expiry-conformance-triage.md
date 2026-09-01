# COW-2795 — CIP-28 §5.3 lazy card-expiry conformance triage

**Date:** 2026-07-29
**Spec:** CIP-28 §5.3 (card status / expiry), state-transition matrix.
**Code:** node#1133 (`expire_card_if_due`, COW-1140), dormant behind `CARD_EXPIRY_TRANSITION_ACTIVATION_HEIGHT = u64::MAX`.
**Acceptance:** a §5.3 decision on **H2** (read-time vs persisted-write), and each advisory either implemented or explicitly documented as accepted, before the activation flag-day.
**Nature:** spec-owner decision + conformance triage — this note **decides H2 from the code's existing behavior** and dispositions each advisory. Recommends a small §5.3 clarification, no code change required for correctness (all items dormant / already covered).

## H2 — read-time vs persisted-write: **the code already commits to read-time-authoritative**

The question was whether §5.3's read-time model or node#1133's persisted `status = Expired` write is the intended representation. The critical path answers it: **`card_is_eligible` (handlers.rs:455) — the gas-funding gate — already computes expiry at read time, ungated:**

```rust
// handlers.rs:471,475
if card.status != CardStatus::Active { return Ok(None); }
// An expiry at/before the current height makes the card ineligible; absent = unbounded.
if !card.expires_at.map(|e| block_height < e).unwrap_or(true) { return Ok(None); }
```

So a card past `expires_at` is **ineligible for gas funding regardless of its persisted status**, at every reachable height, with no activation gate. Read-time expiry is therefore *already* the authority for the only path where expiry has a fund consequence (charge → §2.7 actor-pays fall-through). The `expire_card_if_due` persisted write (COW-1140) is a **best-effort materialization** layered on top — it makes the committed `status` catch up on card-touch for indexer/observability convenience; it is **not** the source of truth.

**Decision / recommendation:** ratify **read-time eligibility as authoritative**; treat `expire_card_if_due` as a non-authoritative materialization. This is the code's existing commitment, not a new design. §5.3 should be clarified with one sentence: "a system may materialize `status = Expired` on card-touch as a cache, but every eligibility/authorization gate MUST compute expiry from `block_height ≥ expires_at`, which is authoritative." No `status = Expired` *system edge* needs to be added to the normative matrix — the matrix already models expiry as read-time; the materialization is an implementation detail. (Spec-owner ratifies the one-line clarification.)

## Advisory dispositions (each documented-as-accepted or scoped)

### A1 — Write-then-`Err` expiry materialization vs per-tx rollback — **CORRECTED; = COW-2849; benign IFF read-time-authoritative (H2)**

> **Correction (2026-07-29):** an earlier draft of this note said the engine "has no per-tx rollback" and called this benign. That premise was **wrong** and is retracted. **Per-tx state atomicity is live** (node#1169 / COW-2810): a System instruction returning `Err` rolls back **all** of that tx's store writes (`execution/src/execution/transaction.rs:483,502` `rollback_to_savepoint`), charging only nonce+gas. So a failed tx does **not** keep the `status = Expired` write — it **reverts** it. This is tracked as **COW-2849** and framed there as a **COW-1140 activation-blocker**.

`set_policy` (:912-926), `freeze` (:957-970), `bank_close_card` (:1634-1667), `transfer_card_ownership` (:1159-1182), and the post-expiry failure paths in deposit (:1230) / withdraw (:1479) call `expire_card_if_due` *before* their own status/auth checks, on the (pre-#1169) contract that the `Active→Expired` materialization commits even if the enclosing op is later rejected. #1169's rollback now reverts that write on `Err`.

**Whether this blocks activation depends entirely on the H2 decision:**
- **Under read-time-authoritative (this note's recommendation): benign.** The materialization is a non-authoritative cache; read-time (`card_is_eligible:475`) is the source of truth and is unaffected by whether the cache commits. And the in-tx handlers re-run `expire_card_if_due` every time, so their *own* status-based rejections are still correct in-tx (the handler sees `Expired` in the speculative store and returns `Err` *before* the rollback discards the write — the rejection stands; only the persisted cache fails to update). So a lapsed card is still rejected by `set_policy`/`charge`, and COW-2849's "activation-blocker" is dissolved rather than fixed — no write-then-`Err` workaround needed. The only residual is a **stale persisted `status`** read by handlers that do *not* re-materialize (`set_default_card`, indexers) — covered by A2/A3.
- **Under persisted-write-authoritative: COW-2849 is a real activation-blocker** and its fix is required — make each expiry transition survive `Err` (return `Ok`-with-status like `ExecuteProposal`'s defeated-proposal finalization at `system_instruction.rs:4126`, or commit the expiry outside the rejected op), plus a real-STF regression test (mock storage's `savepoint`/`rollback_to_savepoint` are no-ops, so the existing tests can't see it).

**This is the strongest argument for the read-time-authoritative H2 decision:** it makes the persisted materialization a pure cache, so #1169's rollback reverting it is harmless — removing COW-2849 as a blocker instead of adding a write-then-`Err` special case that fights the STF's own atomicity contract. **Recommendation: adopt read-time-authoritative (H2) and close COW-2849 as "not required under read-time-authoritative" — or, if the spec-owner insists on persisted-status authority, implement COW-2849's fix before lowering `CARD_EXPIRY_TRANSITION_ACTIVATION_HEIGHT`.** Dormant today either way (`u64::MAX`), so no live regression; this is an activation-gating decision.

### A2 — Incomplete coverage (`set_default_card`, fiat-mint) — **ACCEPTED / partly a non-issue**
- **`set_default_card` (handlers.rs:775):** checks persisted `status == CardStatus::Active` (:794) but not read-time expiry, so a due-but-untouched card (persisted `Active`, past `expires_at`) is settable as default. **Impact: none functionally** — at charge time `card_is_eligible:475` rejects it read-time → the default falls through to actor-pays (§2.7). §5.3 lists set-as-default as *disallowed* for `Expired`, so this is a **hygiene** gap, not a fund/security one. Adding a read-time `expires_at` guard here is a **live** (ungated) consensus change of marginal value (the outcome is already actor-pays); **document as accepted**, or bundle a read-time guard into a future §5.3-hygiene PR if the spec-owner wants strict matrix conformance. Not activation-blocking.
- **Fiat-mint (`bank_mint_from_fiat_voucher:1723`):** minting tokens onto a card is a **Deposit**, and **§5.3's `Expired` row explicitly ALLOWS Deposit** ("Deposit / Renew / Withdraw"). So minting into a due card is *conformant*, not a violation — the advisory's "minted into — which §5.3's Expired row disallows" is imprecise; Deposit is allowed. **No change needed.** (Materializing `status = Expired` on the mint touch is optional observability, below.)

### A3 — No `CardExpired` event — **OPTIONAL (observability, not correctness)**
The lazy transition emits no system event, so indexers/wallets cannot observe expiry from the receipt root. Since read-time is authoritative, correctness does not need it. **If observability is required**, emit a `CardExpired { card_address, expired_at }` event at the `expire_card_if_due` materialization point (a receipt/logs-root change → consensus surface → gate it with the same `CARD_EXPIRY_TRANSITION_ACTIVATION_HEIGHT` flag-day). Recommend adding it *with* the activation PR (indexers will want expiry visibility once the transition is live), not before. **Spec-owner/product call on whether observability is required.**

### A4 — `Renew` interaction — **FUTURE (RenewCard not implemented)**
§5.3 allows `Renew` on an `Expired` card by the owner. `RenewCard` has no handler yet. **Constraint recorded for whoever implements it:** the renew handler must NOT call `expire_card_if_due` before its own logic (or must treat a due card as renewable), so lazy-expire-on-touch cannot block a legitimate renew of an expired card. No action now.

## Net

- **H2 recommended: read-time-authoritative** (the code already does this in `card_is_eligible:475`); `expire_card_if_due` is a materialization cache. Needs a one-line §5.3 clarification from the spec-owner; no code change for correctness.
- **A1 = COW-2849 (activation-gating), disposition hinges on H2.** Per-tx atomicity (#1169) reverts the expiry write on `Err`. Under read-time-authoritative this is **benign** and COW-2849 is *dissolved* (close as "not required"); under persisted-write-authoritative COW-2849's write-survives-`Err` fix + real-STF test are a **required activation-blocker**. This is the decisive reason to pick read-time-authoritative — it removes the blocker rather than special-casing the STF's atomicity contract.
- **A2 accepted** as benign/non-issues (read-time is the authority; Deposit-on-Expired is allowed). Optional: a read-time `expires_at` guard on `set_default_card` for strict matrix hygiene (live change, marginal value).
- **A3** (CardExpired event) recommended *with* activation if observability is wanted — gated consensus surface.
- **A4** recorded as a constraint for the future RenewCard handler.
- Nothing here is activation-blocking; the acceptance's "documented as accepted" is satisfied by this note.

## Anchors (verified 2026-07-29)
`card_is_eligible` read-time expiry: `handlers.rs:471,475`. `expire_card_if_due` (gated): `handlers.rs:878`; gate `CARD_EXPIRY_TRANSITION_ACTIVATION_HEIGHT` `constants.rs:833`; wired call sites `handlers.rs:914,959,1161,1234,1483,1557,1639`. `set_default_card` status check `handlers.rs:794`. Fiat-mint `bank_mint_from_fiat_voucher:1723`. §5.3 state matrix: `cip-28-cowboy-agent-banking.md:583-595` (Expired allows Deposit/Renew/Withdraw).
