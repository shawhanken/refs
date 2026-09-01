# COW-1012 — Bind CIP-8 session vouchers to the real chain_id (launch-prep security)

**Owner:** CIP-8 / CIP-9 spec owner + runner/cbfs · **Status:** launch-blocker (before a 2nd Cowboy chain);
**not** live-exploitable on today's single-chain devnet. **One decision needed** (§5).

---

## 1. The gap

The CIP-8 session voucher's EIP-712 domain hardcodes `chain_id`:

```rust
// execution/src/runner/session.rs:33, :641
pub const COWBOY_SESSION_CHAIN_ID: u64 = 1;
pub fn voucher_eip712_digest(v) { domain_separator(COWBOY_SESSION_CHAIN_ID, SESSION_ACTOR) ... }
```

`1` is a placeholder decoupled from the node's real chain_id (genesis is configurable — `1` on default
devnet, `4242` elsewhere; `chain/src/lib.rs:695`). Combined with `session_id` being **caller-supplied**
(`handle_session_open(session_id: [u8;32], …)`, not chain-derived), a payer who opens the **same session_id on
two Cowboy chains** produces vouchers with **identical EIP-712 digests** — so a voucher signed against chain A's
escrow verifies and **settles against chain B's escrow**, draining funds the payer authorized only once. The
`chainId` field in EIP-712 exists precisely to prevent this; hardcoding it defeats the protection.

**Severity:** MEDIUM (cross-chain replay of payment authorizations). **Not reachable on a single chain** — it
arms only once a second Cowboy chain (testnet + mainnet) exists, which is why it is a launch-blocker rather
than a live bug.

## 2. Why it isn't a one-line const change — the conflict

The **same** `COWBOY_SESSION_CHAIN_ID` is **deliberately** reused as the CIP-9 volume-DEK canonical identity,
which must stay **chain-portable**:

> `rpc/handlers/cbss.rs:832-838` — "CIP-9 volume-DEK identities bind to the **canonical session chain id, NOT
> the local validator chain id** … Emitting `state.chain_id` here made every CIP-9 wrap undecryptable on any
> chain whose id != COWBOY_SESSION_CHAIN_ID (the runner's `ibe_decrypt` fails with `AadMismatch`)."

So one constant serves two **opposite** requirements:
- **Session vouchers** → must **bind to the real chain** (anti-replay).
- **CIP-9 volume-DEK wraps** → must be **chain-independent** (portable wraps).

Changing the constant to `self.chain_id` fixes sessions but **breaks every CIP-9 wrap**. They must be separated.

## 3. Solution — split the two uses

1. **Audit every `COWBOY_SESSION_CHAIN_ID` use** and classify: session-voucher vs CIP-9-wrap.
   Known: session-voucher = `session.rs:641` (voucher digest). CIP-9-wrap = `cbss.rs:840`, the dispatcher
   release path (`dispatcher.rs:375/1404/1432`), `pvm_host.rs:2279/4287` — verify each.
2. **CIP-9-wrap uses** → keep a dedicated, explicitly-portable constant (rename to e.g.
   `CIP9_WRAP_CANONICAL_CHAIN_ID = 1`, documented as intentionally chain-independent). No behavior change.
3. **Session-voucher use** → thread the node's real `self.chain_id` into `voucher_eip712_digest(v, chain_id)`.
   The on-chain `Settle` handler passes `self.chain_id`; the digest now binds the voucher to the chain it was
   opened on.

## 4. Cross-repo coordination (the off-chain half)

`voucher_eip712_digest` is a shared `pub fn` that the off-chain **runner-common** signer imports (via
`cowboy-types`). The signer must sign with the **same** chain_id the on-chain verifier uses, so it needs the
chain's real chain_id at signing time. **Design decision (the one thing to settle):** where does the off-chain
signer get the chain_id?
- **(a)** The node returns it in the `OpenSession` receipt / a `/chain_id` RPC the signer already calls — **recommended** (single source of truth, no drift).
- **(b)** Static per-environment config on the runner — simpler but drifts if misconfigured.

The cbfs CLI likewise reads the CIP-9 canonical id — that stays on the portable constant, unaffected.

## 5. The decision needed
**Approve (3) + (4a):** bind session vouchers to `self.chain_id`, keep CIP-9 wraps on a dedicated portable
constant, and have the off-chain signer read the chain_id from the node. Any objection is almost certainly a
CIP-9-wrap portability concern — which this design explicitly preserves.

## 6. Consensus gating & rollout
Changing the voucher digest changes which vouchers verify → dormant flag-day
(`SESSION_VOUCHER_CHAINID_BIND_ACTIVATION_HEIGHT`). **On devnet it is byte-identical even when activated**,
because devnet `chain_id == 1 == COWBOY_SESSION_CHAIN_ID` — the digest is unchanged. Divergence occurs only on
a chain whose id ≠ 1, i.e. exactly the multi-chain future this protects. A new chain enables it from genesis;
the off-chain signers for that chain sign with its id. Land dormant now; the flag is effectively a
new-chain-genesis switch, not a devnet state change.

## 7. Test plan
- A voucher signed for `chain_id = A` fails `Settle` on a node with `chain_id = B ≠ A` (cross-chain replay
  rejected) once bound; passes on `A`.
- Same session_id on two chain_ids yields **distinct** digests (the replay that motivates this).
- CIP-9 volume-DEK wrap round-trips unchanged across chains (portable constant untouched) — no `AadMismatch`.
- Devnet (`chain_id = 1`): digest byte-identical to today, activated or not.

## 8. Recommendation
Land the split dormant as launch-prep before any second Cowboy chain. It is a real anti-replay hardening, the
only subtlety is the CIP-9-wrap entanglement (resolved by separating the constants), and the off-chain
chain_id source (4a) is the single design call to confirm.
