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

### A1 — Pay-then-fail expiry write — **ACCEPTED (benign under read-time-authoritative)**
`set_policy`/`freeze`/`bank_close_card`/`transfer_card_ownership` call `expire_card_if_due` *before* their auth/status checks (e.g. handlers.rs:914 before the `caller == owner` check at :918), and this engine has no per-tx rollback (see the pay-then-fail conservation note), so a rejected tx still commits the `status = Expired` write. Assessment: **benign**. The write is (a) deterministic — it only fires when `block_height ≥ expires_at`, a consensus quantity, so no fork; (b) *correct* — the card genuinely is expired; and (c) non-authoritative — read-time is the authority, so the materialization changing (or not) never alters an eligibility decision. It is a cosmetic side-effect of a failed tx, not a state corruption. **Optional cleanliness:** move the `expire_card_if_due` call after the `caller == owner` check on the write-paths (auth → materialize → status-check), so an unauthorized caller can't trigger the cache update. Dormant today; fold into the activation PR if desired. **Not a blocker.**

### A2 — Incomplete coverage (`set_default_card`, fiat-mint) — **ACCEPTED / partly a non-issue**
- **`set_default_card` (handlers.rs:775):** checks persisted `status == CardStatus::Active` (:794) but not read-time expiry, so a due-but-untouched card (persisted `Active`, past `expires_at`) is settable as default. **Impact: none functionally** — at charge time `card_is_eligible:475` rejects it read-time → the default falls through to actor-pays (§2.7). §5.3 lists set-as-default as *disallowed* for `Expired`, so this is a **hygiene** gap, not a fund/security one. Adding a read-time `expires_at` guard here is a **live** (ungated) consensus change of marginal value (the outcome is already actor-pays); **document as accepted**, or bundle a read-time guard into a future §5.3-hygiene PR if the spec-owner wants strict matrix conformance. Not activation-blocking.
- **Fiat-mint (`bank_mint_from_fiat_voucher:1723`):** minting tokens onto a card is a **Deposit**, and **§5.3's `Expired` row explicitly ALLOWS Deposit** ("Deposit / Renew / Withdraw"). So minting into a due card is *conformant*, not a violation — the advisory's "minted into — which §5.3's Expired row disallows" is imprecise; Deposit is allowed. **No change needed.** (Materializing `status = Expired` on the mint touch is optional observability, below.)

### A3 — No `CardExpired` event — **OPTIONAL (observability, not correctness)**
The lazy transition emits no system event, so indexers/wallets cannot observe expiry from the receipt root. Since read-time is authoritative, correctness does not need it. **If observability is required**, emit a `CardExpired { card_address, expired_at }` event at the `expire_card_if_due` materialization point (a receipt/logs-root change → consensus surface → gate it with the same `CARD_EXPIRY_TRANSITION_ACTIVATION_HEIGHT` flag-day). Recommend adding it *with* the activation PR (indexers will want expiry visibility once the transition is live), not before. **Spec-owner/product call on whether observability is required.**

### A4 — `Renew` interaction — **FUTURE (RenewCard not implemented)**
§5.3 allows `Renew` on an `Expired` card by the owner. `RenewCard` has no handler yet. **Constraint recorded for whoever implements it:** the renew handler must NOT call `expire_card_if_due` before its own logic (or must treat a due card as renewable), so lazy-expire-on-touch cannot block a legitimate renew of an expired card. No action now.

## Net

- **H2 decided: read-time-authoritative** (the code already does this in `card_is_eligible`); `expire_card_if_due` is a materialization cache. Needs a one-line §5.3 clarification from the spec-owner, no code change for correctness.
- **A1/A2 accepted** as benign/non-issues (read-time is the authority; Deposit-on-Expired is allowed). Optional cleanliness (A1 reorder, A2 set-default read-time guard) can ride the activation PR.
- **A3** (CardExpired event) recommended *with* activation if observability is wanted — gated consensus surface.
- **A4** recorded as a constraint for the future RenewCard handler.
- Nothing here is activation-blocking; the acceptance's "documented as accepted" is satisfied by this note.

## Anchors (verified 2026-07-29)
`card_is_eligible` read-time expiry: `handlers.rs:471,475`. `expire_card_if_due` (gated): `handlers.rs:878`; gate `CARD_EXPIRY_TRANSITION_ACTIVATION_HEIGHT` `constants.rs:833`; wired call sites `handlers.rs:914,959,1161,1234,1483,1557,1639`. `set_default_card` status check `handlers.rs:794`. Fiat-mint `bank_mint_from_fiat_voucher:1723`. §5.3 state matrix: `cip-28-cowboy-agent-banking.md:583-595` (Expired allows Deposit/Renew/Withdraw).
