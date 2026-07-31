# Spec decision needed — CIP-2 §6.2 non-reveal vs early settlement (COW-2552)

**Owner:** CIP-2 §6.2 spec owner · **Raised by:** node COW-2552 / PR #1190 · **Status:** blocks the fix; code is HOLD
**One-line:** When a job settles on `threshold` reveals *before* other committers' reveal windows close, is a
committer who was thereby prevented from revealing a **slashable non-reveal**, or **protected**?

---

## The decision (answer one)

- **(1) Protected** — a committer foreclosed by early settlement is NOT a non-reveal and must not be slashed.
- **(2) Slashable** — reaching settlement without your reveal stored makes you a non-reveal, foreclosed or not.

Your answer selects the implementation (below) and is the *only* thing blocking COW-2552.

## Why it can't be left implicit (the bug it produced)

The as-built classifier runs **only at settlement** and is terminal + one-shot (COW-2286). It cannot tell a
*foreclosed-honest* committer from a *refused* one, because early settlement rejects late reveals
(`JobAlreadyComplete`) and **stores no result for either**. Concrete, at defaults
(`reveal_window_blocks = 60`, `crash_exemption_blocks = 50`, `non_reveal_slash_bps = 2500`):

- **The honest are slashed.** On an M=3 / threshold=2 job where all three honest runners reveal, settlement
  fires on the **2nd** stored reveal; the **3rd** runner's reveal is rejected, so it looks identical to a
  non-revealer → slashed **25% of stake + reputation reset**, on essentially *every* such job. A min-stake
  runner (10,000 → 7,500 CBY) drops below the floor and is ejected from selection.
- **The honest can't defend.** The `CrashAttestation` exemption is anchored at `commit_block` and is *shorter*
  (50) than the reveal window (60), so a runner that commits early has its exemption expire **before reveals
  even open**.
- **The actual attacker walks.** `SubmitCrashAttestation` has no terminality gate: the §6.2 attacker commits
  garbage at the last legal block, watches the job settle, and files the attestation *afterward* → treated as
  operational failure → ~0 penalty, repeatable.

So under interpretation (2) as currently coded, the mechanism **slashes the honest majority and lets the
attacker escape** — the inverse of §6.2's intent. This is why the answer must be explicit.

## The two implementations

| | **Option A — defer + distinguish** (answer = 2, done right) | **Option B — settle after windows close** (answer = 1) |
|---|---|---|
| Idea | Keep early settlement; defer classification to window-close, but record the settlement height and treat foreclosed committers differently from refusers. | A multi-runner job does not *finalize* settlement until every committer's reveal window has closed; classify in one pass then. No foreclosure ever occurs. |
| Extra work | Persist settlement height in the deferral record; reject `CrashAttestation` with `submitted_at_block ≥ settlement_height`; enforce `crash_exemption_blocks ≥ reveal_window_blocks`; keep stake bonded until the deferral drains (COW-2552 HIGH-3). | Delay the terminal settlement transition by up to the reveal window; classify all non-revealers together. |
| Cost | Complex; several interacting guards; still slashes a genuinely-late honest runner who simply missed the window. | Adds up to ~`reveal_window_blocks` (~60 blocks / ~1 min at 1s) of settlement latency to multi-runner jobs; touches the settlement-timing contract. |
| Kills the honest-slash? | Only if the spec says foreclosed-honest are protected *and* the code distinguishes them — i.e. it converges toward B's guarantee anyway. | Yes, by construction — nobody is ever foreclosed. |
| Kills the attacker escape? | Only with the added attestation-terminality gate. | The attacker who never reveals is still classified at window-close (unchanged from §6.2 intent). |

## Recommendation

**Answer (1) Protected → implement Option B.** Rationale: the failure that started this is *honest runners
being slashed for losing a reveal race they never agreed to run*. Option B removes foreclosure at the source,
so no honest committer is ever mis-slashed and the §6.2 attacker (who genuinely never reveals) is still caught
at window-close. Option A can only reach the same safety by adding enough guards that it effectively
reconstructs B's "no foreclosure" guarantee, at higher complexity and with a residual honest-slash edge.

The one thing Option B needs your sign-off on: **is it acceptable for a multi-runner job to finalize settlement
only after the reveal window closes** (≤ ~1 min added latency), rather than on the `threshold`-th reveal?

## What happens on each answer
- **(1) / Option B** → I implement the window-close settlement gate (dormant flag-day, byte-identical until
  activation) and drop the deferral-index approach.
- **(2) / Option A** → I implement the full guard set above (dormant) — larger, and please confirm you accept
  that a genuinely-late-but-honest runner is slashed.
- **No answer** → COW-2552 stays HOLD; the current #1190 is not merged (its deferral approach mis-slashes the
  honest under interpretation 2 and is unnecessary under 1).
