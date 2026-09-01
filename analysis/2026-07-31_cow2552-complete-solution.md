# COW-2552 — Complete solution: correct non-reveal accountability under early settlement

**Scope:** resolves the original COW-2552 gap AND every issue surfaced by the #1190 deep review, with no
honest-runner harm and no spec-owner decision required. Consensus-facing → dormant flag-day.

---

## 1. Problem inventory (everything this must solve)

| # | Problem | Source |
|---|---------|--------|
| P0 | A committer who commits but never reveals escapes the §6.2 non-reveal slash when the job **early-settles** on `threshold` reveals (the job is `Completed`, so no path re-classifies it). | COW-2552 |
| P1 | Any deferred-then-slash fix **slashes honest reveal-race losers**: on M=3/threshold=2, settlement fires on the 2nd reveal; the 3rd honest runner's reveal is rejected (`JobAlreadyComplete`), stored nowhere, and is indistinguishable from a non-revealer → slashed 25% + reputation reset. | #1190 HIGH-1a |
| P2 | The honest committer usually **cannot defend**: `CrashAttestation` is anchored at `commit_block` and `crash_exemption_blocks (50) < reveal_window_blocks (60)`, so the exemption can expire before reveals even open. | #1190 HIGH-1b |
| P3 | The real attacker **buys an exemption after the fact**: `SubmitCrashAttestation` has no terminality/settlement gate, so the attacker watches settlement then files it → lenient branch → ~0 penalty. `submitted_at_block` is persisted but never read. | #1190 HIGH-1c/d |
| P4 | The deferred slash is **evadable**: the straggler's `last_update_block` is never stamped at settlement, so the COW-2116 deregister cooldown (`if last_settlement > 0`) is skipped and a sybil deregisters + refunds 100% stake during the gap. | #1190 HIGH-3 |
| P5 | Window-boundary: a deferral at `classify_at == settlement_block` lands in a bucket the pre-tx sweep already passed → lost. | #1190 HIGH-2 (already fixed: `+1`) |
| P6 | Catch-up sweep stamps a past height → cooldown can be born expired. | #1190 advisory (already fixed: `current_block_height`) |
| P7 | Index hygiene: `put_nonreveal_deferral_index` not in `JOB_TRIO_WRITERS`; unbounded per-bucket vector; corrupt row never deleted. | Almanax + Marshal advisories |

## 2. Root cause (one sentence)

**Early settlement discards within-window reveals**, so an honest race-loser and a genuine non-revealer both
end with "no stored reveal" — the classifier cannot tell them apart, and every downstream defect (P1–P4) is a
consequence of trying to punish an indistinguishable population.

## 3. Design principle — decouple three concerns currently fused at settlement

| Concern | Timing | Change |
|---|---|---|
| **Outcome + payout** | on `threshold` reveals (early) | UNCHANGED — keeps latency low, escrow settle-once intact |
| **Reveal accountability** | throughout the reveal window | NEW — keep accepting & recording within-window reveals after settlement, validated against the settled outcome, without re-paying |
| **Non-reveal classification** | at window-close | DEFERRED — only here is honest-vs-attacker finally decidable |

This dissolves the spec question: because an honest committer's valid within-window reveal is **recorded**, it
is never mistaken for a non-reveal, so no honest runner is ever slashed — regardless of who won the reveal
race. §6.2's existing intent (slash genuine non-revealers) is then implemented correctly and needs no new
ruling.

## 4. Components

### C1 — Accept & record within-window reveals after settlement (resolves P1 root)
Split the COW-2286 terminality guard. On a reveal for a terminal job:
- If the sender **already revealed** or is **past their reveal window** → reject as today.
- Else (within window, first reveal) → **validate** it: commitment-match **and** verify the result against the
  settled outcome for the job's mode (MajorityVote: matches the settled majority; Deterministic: byte-match;
  etc.). Write a lightweight **reveal record** `reveal_seen:{job}:{runner} = {valid|invalid}`. Do **NOT**
  re-run settlement/payout (no escrow touch, no `all_results` mutation). Return `Ok` (accepted, non-settling).

This is the linchpin: it captures exactly the honest race-loser's reveal that P1 was destroying, and it grades
it (valid vs invalid) so a garbage-committer who reveals late still can't launder itself into "honest".

### C2 — Defer classification to window-close (my #1190 mechanism, already built + hardened)
The deferral index + the `process_job_timeouts` sweep at `commit_block + reveal_window_blocks + 1` (P5 fix)
stamping `current_block_height` (P6 fix). Persist the **settlement height** in each deferral record (needed by
C3). At window-close, classify each deferred committer by the `reveal_seen` marker:
- `valid` reveal recorded → **fulfilled** → no penalty (the honest race-loser, correctly exonerated).
- `invalid` reveal recorded → **invalid-reveal** penalty (§6.2/§11 — a dissenter/garbage revealer).
- no reveal + `CrashAttestation` honored (see C3) → operational failure (reputation only).
- no reveal, no honored attestation → **proven non-reveal** → §6.2 slash + reputation reset.

### C3 — Make the CrashAttestation exemption fair AND un-gameable (resolves P2, P3)
- **Reachable (P2):** enforce `crash_exemption_blocks >= reveal_window_blocks` at the
  `SubmitNonRevealConfigProposal` handler (sum/bound validation, mirroring the settlement-config precedent), so
  a crash anywhere in the window can still be attested.
- **Un-gameable (P3):** at classification, honor an attestation only if
  `attestation.submitted_at_block < settlement_height` (now read the persisted `submitted_at_block` against the
  settlement height from C2). A crasher files before observing settlement (they know they crashed immediately);
  an attacker who waits for settlement to decide files after → not honored → slashed.

### C4 — Bond the stake until the deferral drains (resolves P4)
At settlement, when a committer is deferred, stamp `registration.last_update_block = settlement_height` so the
COW-2116 deregister cooldown arms and the sybil cannot deregister + refund during the gap. (Alternatively keep
the job in `runner_jobs` for deferred committers; the stamp is the smaller change.)

### C5 — Hygiene (resolves P7)
- Enroll `put_nonreveal_deferral_index` in `JOB_TRIO_WRITERS` (0x02 writer).
- Per-bucket cap on the deferral vector (bounded by committee-size × jobs-settling-per-height); `log` any
  truncation (never silently drop accountability). Guards the mid-flight `reveal_window_blocks`-change merge.
- Consume/delete a corrupt or empty bucket row (reorder the delete before the empty early-return).

## 5. Which findings each component closes

P0 → C2. P1 → **C1** (+C2 classify). P2 → C3a. P3 → C3b. P4 → C4. P5/P6 → already done. P7 → C5.
Spec question → **dissolved by C1** (no honest runner is ever foreclosed-then-slashed).

## 6. Consensus safety & phasing

All behavior changes (C1–C4) are one dormant flag-day (`CIP2_NONREVEAL_DEFERRAL_ACTIVATION_HEIGHT`,
byte-identical below activation). C5 hygiene is non-consensus or rides the same gate. Suggested phasing:
- **Phase 1 (land dormant):** C1+C2+C3+C4+C5 behind the flag. Byte-identical today.
- **Phase 2 (activate):** coordinated flag-day once C1's post-settlement verification is load-tested on devnet.

## 7. Test plan (all mutation-verified; real settlement flow, not seeded indices)

1. Honest race-loser: M=3/threshold=2, all three reveal; the foreclosed 3rd is recorded `valid` → **not**
   slashed at window-close. (Directly pins P1.)
2. Pure non-revealer: commits, never reveals, no attestation → slashed at window-close.
3. Late garbage revealer: commits garbage, reveals it post-settlement → recorded `invalid` → invalid-reveal
   penalty, not the free pass.
4. Attestation anti-game: attacker files `CrashAttestation` after settlement → not honored (`submitted_at_block
   >= settlement_height`) → slashed. Honest crash filed before settlement → honored.
5. Deregister evasion: deferred committer attempts deregister during the gap → blocked by the armed cooldown.
6. Dormancy: below activation every path is byte-identical (existing spec_t7 unchanged).

## 8. Honest cost / severity note (for the go/no-go)

This is a **substantial** consensus change (post-settlement reveal verification, a reveal-record store, a
settlement-height field, two new governance validations, the deferral sweep, bonding, hygiene). The gap it
closes (P0) is **modest griefing**: the attacker earns no reward, the job still succeeds via threshold, and the
only harm is a non-performing runner retaining selection weight + diluting redundancy.

Recommendation: this is the correct, complete design and it removes the spec bottleneck — but it should be
**severity-gated**. Land it if commit-and-never-reveal griefing is a real concern for launch; otherwise the
same reasoning says the lighter path (close COW-2552 low-severity, keep the reputation EMA as the only soft
signal) is defensible. Either way, **#1190's Option A must not be merged** — its defer-then-slash slashes the
honest and is superseded here by C1.
