# tx-canonical Encoding — Flag-Day Rollout Runbook

**Change:** node PR #742 (canonical transaction encoding + chain_id replay protection +
anti-malleability). This is a **consensus flag-day**: it changes the tx wire encoding, the
signing hash, `digest()`/`tx_root`, and admission. It CANNOT be merged/deployed in isolation —
deploying it to the existing devnet without the steps below breaks the chain (every old-format /
`chain_id:0` tx is rejected; old deferred-tx/mailbox state has incompatible digests).

**Strategy:** clean-break flag-day with a **devnet reset** (design decision D3 — devnet has no
live-mainnet tx history to preserve). All validators upgrade to the new binary at once, the
chain resets to a fresh genesis on the new format, and all tx producers (wallet/cli/SDK) emit
the new encoding from the same moment.

**Marshal verdict:** `needs_human` (run #203). Code is ready (4358 workspace tests, 6-round
audit, econ + state-root invariants green). What remains is human coordination.

---

## Prerequisites (all must be TRUE before the flag-day)

| # | Item | Owner | Status |
|---|------|-------|--------|
| P1 | node #742 reviewed + approved (consensus change + design audit) | node reviewers | ☐ |
| P2 | **Wallet byte-parity PR ready** — wallet (JS) reproduces the canonical encoding, passing its parity test vs `refs/common/tx-canonical-vectors.json` | wallet owner | ☐ (Plan B) |
| P3 | SDK (Python) client-side tx construction (if any) reproduces the canonical encoding vs the same fixture | SDK owner | ☐ (Plan B; may be N/A if SDK doesn't build/sign txs client-side) |
| P4 | **Genesis `chain_id` pinned** to a concrete devnet value (e.g. 1) in every config that will run — NOT `None` (a `None` chain_id hard-fails / rejects all txs in the new code) | genesis/devnet owner | ☐ (local-devnet `setup generate` already pins `Some(1)`; remote/default configs need it) |
| P5 | #743 (Message/Receipt strict decode) merged first OR included — it's behavior-preserving and can land earlier; recommended to merge before the flag-day to reduce #742's blast radius | node reviewers | ☐ (PR #743 open) |

> **P2 is the gating prerequisite.** Until the wallet emits the new encoding, the flag-day would
> reject every wallet-signed tx.

---

## Flag-day sequence (single coordinated window)

> Pick a low-activity window. Announce to validator operators + client teams. Have the rollback
> point (current devnet genesis + binaries) snapshotted.

1. **Freeze submissions** — pause client traffic to the devnet (or accept it'll be reset).
2. **Pin genesis `chain_id`** to the chosen devnet value (P4) in the new genesis config. (Activation step 0.)
3. **Merge node #742** to devnet (draft → ready → approve → merge). Build the release binary.
4. **Reset the devnet to a fresh genesis** on the new binary:
   - new genesis (new tx codec is the genesis code; pinned `chain_id`),
   - old deferred-tx / mailbox / receipt state does NOT carry (incompatible by design — this is why we reset, see design §0c-R3 / §7).
5. **Upgrade ALL validators simultaneously** to the new binary on the fresh chain. (A mixed-version
   set on the SAME chain would fork on tx encoding / digest — must be atomic.)
6. **Switch all tx producers at once** — wallet, cli, SDK, runner — to emit the canonical encoding +
   the node's `chain_id`. (node-side cli/runner are already migrated in #742; wallet/SDK land via P2/P3.)
7. **Smoke test** — a wallet transfer and a cli transfer on the new chain are admitted (`chain_id`
   matches) and execute; a deliberately wrong-`chain_id` tx is rejected with `E_TX_WRONG_CHAIN_ID`.
   Run the e2e examples (`examples/token/test_token_e2e.sh` etc.) — they drive the CLI.
8. **Unfreeze.**

---

## Rollback

Because it's a devnet reset, rollback = redeploy the previous binary + previous genesis snapshot
(taken before step 4). No on-chain migration to unwind. If P2/P3 (clients) aren't ready at the
window, **abort before step 3** (do not merge) — nothing is lost.

---

## Verification gates (must pass before declaring done)

- node #742: `cargo test --workspace` green; econ invariants 10/10; state-root invariants 3/3;
  TV1/TV2 conformance vectors frozen + unchanged.
- wallet/SDK: parity test reproduces `tv1_unsigned_hex` / `tv1_signing_hash` / `tv2_signed_hex`
  from `refs/common/tx-canonical-vectors.json`.
- Post-reset smoke: CLI transfer admitted + executed; wrong-chain_id rejected.

---

## Follow-ons (NOT blocking the flag-day; sequence after)

- **WP rewrite** (Plan C): §2 + Appendix A + the standalone line-198 MUST → describe the
  commonware-codec canonical form. Doc-only; do after #742 lands. (Highest Marshal tier — amends
  the whitepaper.)
- **A3/A4 trailing-tail version-gate** (`Message`/`TransactionReceipt` `has_remaining()` tails):
  a `Message` wire change requiring a format-version byte; fold into THIS flag-day's reset if
  done in time, else a later coordinated upgrade. See `refs/plans/2026-06-16_tx-canonical-followons-plan.md` Plan A.

---

## One-line summary for operators

> Don't merge #742 alone. Land #743 first; get the wallet/SDK byte-parity PRs ready; then in one
> window: pin genesis chain_id → merge #742 → reset devnet to new genesis → upgrade all validators →
> switch all clients → smoke-test. Rollback = redeploy old binary+genesis snapshot.
