# Econ invariant gate — correction + the one real gap (esc-2026-06-05-econ-invariants-missing)

## What actually happened (correction)

During the Marshal gate of PR node#589 I ran `cargo test … econ_invariants::…`
in `/home/ubuntu/workspace/node`, whose **main worktree was checked out on the
stale branch `feat/cow-977-state-invariant-skeleton`** — predating the landing
of `execution/src/econ_invariants.rs` (PR #564). So all four registered econ
invariants reported `running 0 tests` and I called the gate *degraded / pack
drift for all four*. **That was wrong** — an artifact of the stale checkout, not
real drift. Marshal's "降级不谎报" rule cuts both ways: don't over-claim drift
either.

Re-running on `origin/devnet` (which already contains #589's merge):

| invariant | on devnet |
|---|---|
| `econ.fee_conservation`   | ✅ 1 passed (real proptest, PR #564) |
| `econ.settlement_sum_100` | ✅ 1 passed (real proptest, PR #564) |
| `econ.escrow_non_negative`| ✅ 1 passed (real proptest, PR #564) |
| `econ.tx_fee_conservation`| ❌ `running 0 tests` — **genuinely never implemented** |

So only **one** of the four was real pack drift. `econ_invariants.rs`'s own
module docstring even says it supplies *three* bodies; the pack registers a
*fourth* (`econ.tx_fee_conservation`) that no body ever matched.

## The fix (implemented on `feat/econ-invariants-skeleton`)

`econ.tx_fee_conservation` is a genuinely distinct CIP-3 property from the
settlement-split `econ.fee_conservation`: it pins the **per-tx** sender-side
accounting (`total_fee = burn + proposer_tip`, no third bucket, per-unit charge
≤ offered `max_fee`). It is roundtrippable, so it gets a real proptest driving
the production `DualBasefee::compute_tx_fees` — not a stub:

- `execution/src/econ_invariants.rs` — added `econ_tx_fee_conservation` proptest
  + module-doc bullet + `use crate::basefee::DualBasefee;`.

All four now pass on the branch:
```
econ_fee_conservation:    test result: ok. 1 passed
econ_settlement_sum_100:  test result: ok. 1 passed
econ_escrow_non_negative: test result: ok. 1 passed
econ_tx_fee_conservation: test result: ok. 1 passed   <-- new, real
```

## Ratchet status

`esc-2026-06-05-econ-invariants-missing` (spawned_check `econ.fee_conservation`):
the underlying obligation — every registered `econ.*` invariant has a real,
runnable body — is now satisfied. Lesson captured: **run invariant gates against
the PR's actual base (devnet), not whatever the main worktree happens to be on**;
a stale checkout produces the same `running 0 tests` signature as real drift.
