# CIP-28 amendment proposal — poison-default actor DoS

**Status:** draft for team review · **Date:** 2026-07-27 · **Source:** Marshal deep review of node#1142 / node#1134 (H1)

## Problem

An attacker can permanently, unrecoverably brick any **deployed (keyless) actor** `V` for the cost of two dust transactions, once the CIP-28 bank surface is active:

1. `BankIssueCard { agent: V, policy: <deny-all / cap 0>, … }` — issuance is **permissionless in `agent`** (§3.1: "caller = tx.from becomes the owner"; `agent` is a free field). No money moves; `V` never consents. Card address is offline-computable.
2. `BankSetDefaultCard { agent: V, card_address: Some(poison) }` — §3.2 authorizes **`caller == card.owner`** (the attacker) to set the agent's default, with **no pre-existing-default precondition** ("guardian sets it on the agent's behalf early on").

From then on every top-level `ExecuteActor { actor: V }` from **any** sender resolves `V`'s default card (§2.7 step 2), the charge fails (deny-policy / cap), and per §2.7 / §3.5 / §4.5 / §5.2 the **entire tx is rejected** (`BankPolicyDenied` / `BankCapExceeded`). `V` cannot recover: `SetDefaultCard`'s only authorized principals are `caller == agent` (a keyless contract can never sign) and `caller == card.owner` (the attacker). Only the bank operator can `freeze` the card — after which the attacker repoints to a fresh one (bounded by `MAX_CARDS_PER_AGENT_BANK`, but frozen cards never free their slot).

## Why there is no spec-compliant *code* fix

The DoS is the composition of three individually-spec'd behaviors; closing it in code alone breaks one of them:

| Candidate local fix | Violates |
|---|---|
| Forbid non-agent first-set in `SetDefaultCard` | **§3.2** (owner may set the agent's default; no precondition) — and disables the *keyless-actor default-card* feature that §2.7 targets |
| A2 admission gate falls through to actor-pays instead of rejecting | **§2.7 / §3.5 / §4.5 / §5.2** (a present card that can't fund → *reject the tx*) |

So the fix must be a **spec amendment**.

## Proposed amendment (options, for team decision)

**A. Bind agent consent to card→default eligibility (recommended).**
A card may be set as an agent's default by a non-agent caller **only if the agent consented to the (agent, card/owner) relationship** — i.e. only a **consented op-212 card** whose issuance-principal preimage **binds `agent`**. Requires:
- CIP-36 §7: add `agent` to the `IssuancePrincipalVoucher` preimage (currently covers `bank_id/issuance_principal/owner_or_agent/nonce/expires_at`, **not** `agent`) — so a gateway voucher authorizes a *specific* agent, and an attacker can't reuse a self-voucher to name an arbitrary victim.
- CIP-28 §3.2: a non-agent `SetDefaultCard` first-set requires `card.issuance_principal != 0` (consented). Agent-self first-set and re-point-among-owned (F1(b)) unchanged.
- Preserves guardian onboarding (guardians use the consented path) and keyless-actor default cards; closes the permissionless-op-200 DoS. **Flag-day** (preimage = consensus).

**B. Make §2.7 fall through instead of reject when the default card can't fund.**
Amend §2.7 / §4.5 so a present-but-ineligible default card yields `card_paid = 0` and the actor/sender waterfall covers gas (as the *settle* path already does today — the implementation is in fact internally inconsistent: A2 rejects, settle falls through). Closes the DoS (poison default = "doesn't fund", not "bricks") but changes fee semantics: a sender/relayer that expected card-only funding now pays. Needs an explicit `fee_payer_override`/"card-only" opt-in (already a noted future milestone) to recover the strict semantic.

**C. Amend §3.2 to require agent-initiated first-set.**
Bless the reverted node#1142 behavior in spec: only the agent establishes its first default; a co-owner may re-point among cards it owns. Simplest, but sacrifices guardian bootstrap of a keyless agent — needs a separate keyless-onboarding mechanism (overlaps A).

## Recommendation

**A** (agent-bound consent) is the most faithful to CIP-28's guardian/keyless-actor model and closes the DoS at its root (permissionless agent-naming). It is a flag-day (preimage change) and should ride the same activation coordination as the rest of CIP-28. Until it ships, the DoS is reachable at activation — weigh against the CIP-34 demo actor on devnet.

## Not fixed by this amendment

The `MAX_CARDS_PER_AGENT_BANK` agent-slot-exhaustion griefing (an attacker naming a victim as agent to fill its slots) denies only the *card-funded-gas feature*, not execution; consider a per-(agent) issuance-consent gate under option A.
