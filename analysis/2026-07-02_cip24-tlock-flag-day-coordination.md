# CIP-24 §3.4.6 Time-Lock Release — Flag-Day Coordination Checklist

> **⚠️ Partially superseded (2026-07-02 later same day):** the §0 readiness table below predates the reveal/consumer landing. Since then #882 (152/153), #888 (154/155), and #904 (156) all merged to `devnet` — the reveal consumer now **exists and is safe** (grace/refund fallback), so the "no consumer" block no longer holds and the tlock opcodes are folded into one atomic v1 SEALED flag-day. See **`2026-07-02_cip34-v1-sealed-flag-day-coordination.md`** for the current, consolidated plan. The mechanism/rollback/rollout guidance below (§1–§8) remains valid as the tlock slice of that upgrade.

Date: 2026-07-02
Owner: (pavilionledger / release coordinator)
Scope: coordinated activation of the CIP-24 time-lock release mode.

## 0. Readiness status (2026-07-02) — NOT yet flag-day-ready

Two of the readiness gates in §5 were investigated and are **not met**. Activating opcodes 152/153 now is *safe* (dormant, no half-built consumer to mis-wire) but **functionally inert** — nothing would sign or consume. The on-chain handlers (#882/#883) are the **first slice** of a larger stack whose remaining slices do not exist yet.

| Gate | Status | Evidence |
|---|---|---|
| On-chain tlock handlers (#882 + #883) | ✅ complete, verified | node branch `feat/cip-24-tlock-release-handlers` @ `b409d942`; 3 independent review rounds |
| **Off-chain committee signing** (cbss-crypto / runner) | ❌ **absent** | No `cbss/tlock/v1` identity, no request-watcher, no `SubmitTlockRelease` submitter. Only reusable primitives (`threshold::partial_sign = identity·share`, `hash_to_curve`) exist. `cbss/crates/cbss-crypto/src/identity.rs:4-6` (ibe domains only), `threshold.rs:18-34`. → **no committee would sign; requests sit uncollected.** |
| **CIP-34 SEALED consumer** (reveal → combine σ → decrypt bid → settle) | ❌ **absent everywhere** | Not on devnet (settlement.rs is OPEN-mode only; live CIP-34 opcodes are 146–151). On the unmerged `feat/cip-34-sealed-auction-handlers` branch the reveal slice is explicitly deferred: `settlement.rs:605 "reveal is a separate permissionless tx (built next)"`. |
| **Committed CIP-34 spec** | ❌ **none** | `cowboy/docs/cips/` has no `cip-34*`; CIP-34 exists only as planning docs. (CIP-24 §3.4.6 *is* committed via #212.) |

**Recommendation given readiness:** do **not** schedule the flag-day yet. Either (i) hold #882/#883 until the off-chain signing + CIP-34 reveal consumer slices land and flag-day the whole stack together; or (ii) if there is value in locking the consensus surface early, merge #882/#883 to devnet behind a **gov-param activation height set in the future** (option B in §4) and treat it as inert until the other slices ship. Option (i) is simpler and avoids a live-but-inert consensus surface.

## 1. What activates together — one atomic consensus upgrade

| PR | Repo | Consensus surface | Merge target |
|---|---|---|---|
| **#882** | node | opcodes **152/153** decode-reject → decode+dispatch; error codes **E1739–E1745** → `receipt_root`; `cbss.tlock.*` events → `logs_root`→`receipt_root`; 2 new gas constants; codec rev `fc8b8567` → `a09efb01` (adds the tlock `*Args` + opcodes) | devnet |
| **#883** | node | GcNonces **per-pass floors**: changes the deletion set (`state_root`) and the `*.gc` event payloads (`receipt_root`) on an **already-live** instruction | stacked on #882 branch |
| **#218** | cowboy | §5.3 error-table rows for the tlock failures — **docs only, no consensus** | main |

## 2. Why ONE flag-day, not three

- **#883 modifies a live instruction.** `GcNonces` has been live since CIP-23 v3 (#784, no activation gate). Its per-pass clamp changes consensus behavior the moment a node runs it — independent of tlock. It cannot lead or lag #882.
- **#882's opcodes 152/153** move from decode-reject to dispatch. A node with #882 dispatches them; a node without rejects them. The first tlock tx after a partial rollout → **state/receipt-root fork**.
- Therefore **all validators must switch at the same block.** #218 carries no consensus but should land in the same window for spec↔impl consistency.

## 3. Merge order (dependency graph)

1. Review + approve **#883** and merge it into **#882's branch** (`feat/cip-24-tlock-release-handlers`) — it is already based there. Do **not** merge #883 to devnet on its own (its base is the feature branch, and its GcNonces change only ships as part of this upgrade).
2. Merge the combined branch (**#882 incl. #883**) → **devnet**.
3. Merge **#218** → **cowboy `main`** (same window).

## 4. Activation mechanism — DECISION NEEDED

The chain already has precedents for gated activation:
- **Gov-param activation height** — e.g. `cip1.auction.activation_height` (storage/speculative.rs). All nodes read the same on-chain height and switch deterministically.
- **Delayed activation** — `activation_delay_blocks` / `activated_at_block` (DKG path, system_instruction.rs).

Neither #882 nor #883 currently implements an activation gate — both take effect immediately on binary deploy. Options:

- **(A) Devnet coordinated redeploy.** Schedule a maintenance window; all validators upgrade in lockstep. Simplest for devnet; a straggler forks until it upgrades. Acceptable for devnet.
- **(B) Gov-param activation height** (follow the `cip1.auction` precedent) gating **both** the opcode 152/153 dispatch **and** the GcNonces per-pass clamp behind a single on-chain height. Cleaner; deterministic switch; flip-off rollback. Required posture for the mainnet track.

**Recommendation:** ship on devnet via **(A)** with a scheduled window; **before mainnet**, wrap the whole set in **(B)**. If (B) is chosen now, it is a small additional change to both #882 (opcode dispatch guard) and #883 (clamp guard) — call it out before merge.

## 5. Pre-flag-day gates (all must pass)

- [~] #883 approved + merged into #882 branch; combined-branch CI green. **Verified locally on `b409d942`**: `cargo fmt --all --check` clean, `cargo build --workspace` green, `cbss::tests` 140/0, clippy clean. Still pending: PR approval + merge, and CI `test-pvm` on the branch push event.
- [ ] cowboy-protocol codec rev `a09efb01` tagged and reproducibly pinned.
- [ ] `sys_opcode_uniqueness` green on the combined branch. **152/153 are provisional** (§3.3) — reconcile against CIP-34's own unpinned `Intent*` settlement opcodes at impl time so the two amendments don't collide.
- [ ] 3 `gc_nonces_*` proptests + 5 econ invariants + `timer_burn` green (all currently green on `b409d942`).
- [x] **Consumer readiness (CIP-34 v1 SEALED FSM).** ❌ **NOT READY** (see §0). The reveal/consumer slice exists nowhere; there is no committed CIP-34 spec. Activating 152/153 is safe (registerable-but-unused) but there is no consumer to serve.
- [x] **Committee/runner readiness (cbss-crypto).** ❌ **NOT READY** (see §0). No off-chain tlock identity / watcher / submit path — no committee would sign. Missing work is integration glue, not novel crypto.
- [ ] All validator operators notified; upgrade window scheduled.

## 6. Rollout steps

1. Announce flag-day height **H** (option A) / choose the gov-param `…tlock.activation_height = H` (option B).
2. Distribute the combined node binary.
3. Validators upgrade before **H** (A) / set the activation param (B).
4. Merge #218 → cowboy `main`.

## 7. Post-activation verification (on devnet)

- [ ] End-to-end: `RegisterTlockRelease` + `t × SubmitTlockRelease` reaches threshold → emits `cbss.tlock.released`; a reader Lagrange-combines `σ = MSK · I_tlock` off-chain.
- [ ] Premature `SubmitTlockRelease` (head < target_height) → `TlockNotYetReleasable`.
- [ ] **#883 security check:** `GcNonces{ upto_block = u64::MAX }` does **not** delete (a) an unexpired tlock request, (b) a fresh seen-nonce (< 75 blocks old), (c) a fresh receipt set (< 384 blocks old) — and **does** prune genuinely expired ones.
- [ ] No `state_root` / `receipt_root` divergence across validators around **H**.
- [ ] E1739–E1745 surface correctly in failed-tx receipts.

## 8. Rollback / abort

- **Pre-H:** abort by not upgrading — no state touched.
- **Post-H divergence (option A):** hard fork point → coordinated downgrade + rewind to pre-H (devnet-acceptable). This is the argument for option (B): a gov-param gate lets you flip activation off without a rewind.
- **#883 clamp cannot be reverted alone** — reverting re-opens the tee-nonce replay + release-receipt censorship holes. Roll the whole set back together.

## Reference

- Spec: CIP-24 §3.4.6 (merged via cowboy #212, `0c5eefd`), §3.3 opcode allocation, §3.5 instruction defs, §4.5 `TLOCK_*` params.
- Code: node #882 (handlers) + #883 (GcNonces per-pass floors, head `b409d942`).
- Ratchets: `contract.gc_nonces_head_clamp`, `contract.gc_nonces_tee_nonce_freshness`, `contract.gc_nonces_receipt_freshness`.
