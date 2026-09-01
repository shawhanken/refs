# Decision proposal — CBSS `MIN_PROXY_STAKE` (spec 10,000 vs code 1,000)

**Issue:** cowboyinc/cowboy#238 (audit HIGH H-14) · **Status:** open, needs decision · **Class:** security + economics parameter (governance) — *this doc recommends, it does not decide.* · **Related:** COW-2497 (committee sizing).

## The discrepancy

- **Spec:** CIP-24 / Cowboy Secrets whitepaper §13 specify `MIN_PROXY_STAKE = 10,000` token units — the stake a CBSS proxy must post to join a release committee.
- **Code (devnet, verified 2026-07-12):** `node/types/src/constants.rs:677` → `pub const CBSS_MIN_PROXY_STAKE: u64 = 1_000;` — **10× lower**.

Two problems, not one:
1. **Magnitude (security):** a 10× lower stake is a 10× weaker economic deterrent against a faulty/Sybil proxy. Slashing 5% of a min-stake proxy costs the attacker `50` (at 1,000) vs `500` (at 10,000). Committee integrity in a threshold-IBE scheme rests on the cost of accumulating enough colluding/faulty proxies to reach the threshold; a cheaper proxy directly lowers that attack cost.
2. **Unit basis (correctness):** the spec says "token units"; the code constant is a bare `u64 = 1_000` with no documented scale (wei vs whole-CBY). The two may not even denote the same quantity — this must be pinned regardless of which magnitude is chosen.

## Why it matters (threat model)

CBSS is the trust root for secret release (CIP-24) and, transitively, for CBFS private-volume DEK wrapping (see audit H-15) and CIP-34 sealed-bid auctions. A committee compromised by cheaply-staked Sybil proxies can release secrets out of policy or withhold liveness. `MIN_PROXY_STAKE` is one of the two levers (the other being committee size/threshold — COW-2497) that price a committee-capture attack. They should be chosen together.

## Options

### (a) Raise the code constant to 10,000 (match the spec threat model) — **recommended, pending sign-off**
Set `CBSS_MIN_PROXY_STAKE` to the spec's 10,000 (in the correct, documented unit), keeping code and spec aligned on the stronger deterrent.
- ✅ Restores the intended Sybil cost; aligns with the published threat model.
- ✅ Simplest to reason about — spec is authoritative for a security parameter unless there is a deliberate reason to weaken it.
- ⚠️ **Flag-day** (changes an on-chain admission threshold); coordinate with a proxy-set migration if any live proxy is staked between 1,000 and 10,000.

### (b) Lower the spec to 1,000 (ratify the shipped value)
If `1,000` was an intentional devnet-easing value, amend CIP-24/WP §13 to 1,000 and document the rationale (e.g. bootstrap-phase accessibility) and the unit basis.
- ✅ No code/flag-day change; documents reality.
- ❌ Bakes a 10× weaker deterrent into the normative threat model. Only acceptable if committee size/threshold (COW-2497) independently carries the security budget and that trade is explicit.

### (c) Re-derive the value from committee-sizing analysis (COW-2497)
Treat `MIN_PROXY_STAKE` and committee `(n, threshold)` as one joint security-budget problem; pick a stake that, together with the ratified committee sizing, meets a stated capture-cost target.
- ✅ Most principled; avoids setting the two levers in isolation.
- ⚠️ More work; needs the COW-2497 outcome first. Good if the team wants a defensible number rather than "match the spec."

## Recommendation

**Option (a)** as the default — a security parameter should not silently ship 10× below its published value; raise the code to the spec's 10,000. **But** gate the final number on the COW-2497 committee-sizing work (option (c) sensibility): if that analysis lands a different joint optimum, take it and update *both* spec and code to match. Either way, **the unit basis MUST be pinned** (wei vs whole-CBY) in the same change, with a constant/assertion test so spec and code cannot drift again.

Do **not** silently keep 1,000 without a documented rationale — that is the one outcome the audit flags as unacceptable (a normative MUST weakened 10× with no record).

## Decision owners
Security + economics (jointly), coordinated with COW-2497. Flag-day if the on-chain threshold changes.

---
*Generated as an audit follow-up recommendation (2026-07-12). Advisory only — security/economics owners decide.*
