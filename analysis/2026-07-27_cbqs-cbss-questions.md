# CBQS → CBSS Team: Release-Path Question List

**Context**: CBQS design §1.4.4 bullet 4 and §1.15 #2 list a "CBSS persistent-workload release path" as an extension requiring co-design with the CBSS team. The review (`2026-07-27_cbqs-design-review.md`, H2) found that CBQS v1's largest bespoke component (envelope fan-out) is the fallback for that gap — so the gap's existence had to be verified first.

**Verification result: the gap does not exist — it was designed, reviewed, merged, and then deleted by an unrelated PR.** See §0.1.

---

## 0 Summary

### 0.1 Key finding: CIP-24 §3.4.7 operator-principal release class was merged, then clobbered

| Fact | Evidence |
|---|---|
| CIP-24 §3.4.7 "operator-principal release class" merged into `cowboyinc/cowboy` main on 2026-07-12 | PR#227, merge commit `d8a5d44`, +219/−2 on `docs/cips/cip-24-secrets-manager.md`; Marshal review runs 548/550; fixup PR#228 also merged |
| The section was present at `d8a5d44` | `git show d8a5d44:docs/cips/cip-24-secrets-manager.md` → 11 occurrences of `3.4.7`, file is 1888 lines |
| **Current `origin/main` has no trace of it** | `git show origin/main:…` → `3.4.7` appears **0** times, `OperatorReleaseGrant` **0** times, file is 1738 lines |
| The deletion came from a Twilio example PR | pickaxe `git log -S OperatorReleaseGrant` matches exactly two commits: `d8a5d44` (added) and `5027a0c` (removed). `5027a0c` = PR#242 "feat(gallery): CIP-33 store-hireable Twilio two-way SMS actor…", which applied **+21/−226** to cip-24, and `5027a0c` is a descendant of `d8a5d44` → a stale-branch clobber, not an intentional revert |

**Collateral damage** (same commit):

- `cip-8-mpp-session.md` (−15): removed the 2026-07 spec↔code correction. **Current main therefore carries a claim known to be false** — line 435 still reads "MPP Session never claimed numeric opcodes", while the deleted correction stated explicitly "That is false in shipped code" (they are `SystemInstruction` variants with opcodes 52–57, per `cowboy-protocol-codec/src/instruction.rs`). This is an unrepaired live spec-drift regression.
- `cip-31-cbfs-rent-schedule.md` (−27/+20): reverted the fee split from 10/2/88 back to 10/1/89. A later PR#274 independently confirmed 10/1/89 as the deployed value → **no substantive damage** (the outcome is correct by coincidence).
- `cowboy-storage-whitepaper.md` (−2), `cowboy-design-decisions.md` (±1).

**The same class of incident has happened before**: `cc2ced0` "docs(cip-10): restore persistent workload specification" (PR#272, branch `jw/cip10-workload-spec-repair`) is a repair for the identical failure mode. This is not a one-off; it is a recurring defect in the docs repository.

### 0.2 The questions therefore change shape

Not "please add a persistent-workload release mode for us", but:

1. **Restoring §3.4.7 is a process problem, not a design problem** (Q1).
2. **Five distinct authorization paths have grown onto one committee**, two of which have no normative home in CIP-24 (§1). The real question is whether to generalize (Q3).
3. CBQS has two mutually exclusive integration routes, and the choice decides whether v1 needs an envelope subsystem at all (Q2 vs Q4). This is the only genuinely blocking decision.

---

## 1 Baseline: one committee, five authorization paths

Every path shares the same CBSS committee, the same `MPK`, the same shares and PSS. They differ only in **who may trigger a release, and on what evidence**.

| # | Path | Authorization evidence | Recipient | Normative home in CIP-24 | Implementation status |
|---|---|---|---|---|---|
| P1 | Actor / job-bound confidential release | `SecretPolicy.actors` ∩ manifest entitlement ∩ dispatcher job assignment ∩ anti-replay (§3.7) | The VRF-selected runner | §3.4.3 (main body) | Deployed on chain (`node/execution/src/cbss.rs`) |
| P2 | Time-lock release | Height gate only — **no ACL, no job binding, permissionless** | Any observer (public at the height) | §3.4.6 (2026-06-29 amendment, merged) | Reference implementation TBD |
| P3 | **Operator-principal release** | On-chain `OperatorReleaseGrant` plus a `K_auth` signature, **replacing** the job-assignment + manifest + ACL triple | The issuer's own standing off-chain service | **§3.4.7 — merged, then clobbered (see §0.1)** | Reference implementation not built (node `0x04` op 154/155) |
| P4 | CIP-7 per-epoch content-key seal | SKM (`0x0D`) on-chain `StreamAccess` plus `SealRequest`; **no ACL, no job binding, no manifest** | The recipient's registered account X25519 key (`AccountKeyRegistration`) | **Not recorded as a release mode in CIP-24** (mentioned only in the `MAX_IBE_AAD_BYTES` note, "CIP-7 AADs are variable-length") | **Implemented**: `cbss/crates/cbssd/src/cip7_content_key_seal.rs` (739 lines, with a pluggable `Cip7SealAuthorizer` trait performing an on-chain authorization query), `cbss-client/tests/cip7_vectors.rs`, `cbss-crypto/src/identity.rs`; node side in `stream_key_manager.rs` |
| P5 | CIP-9 volume-DEK seal at mount | node builds the `SealRequest`; hold-until-key-delivery | The assigned runner | Documented in §9.3 / §11, not as a standalone "release class" | Implemented |

**Observation**: P3 and P4 solve the same problem — **a standing, non-job-bound principal needs a confidential key** — yet each grew its own authorization evidence (a grant plus `K_auth` signature vs an SKM on-chain access record). P4 has even abstracted authorization into a trait (`Cip7SealAuthorizer::authorize`) without that being promoted to a normative concept. A sixth path grown by CBQS would be predictable duplication.

---

## 2 Questions for the CBSS team

Each carries **Blocking** (does it block a CBQS v1 scope decision) and **Why we ask** (which CBQS decision depends on it).

### Q1 Restoring §3.4.7 — who does it, through what process?

**Blocking: yes (as process, not design)**

The facts in §0.1: merged → overwritten by an unrelated PR → still unrestored. CBQS cannot build on a section that exists historically but not normatively.

- Who initiates the restore — the CBSS team (original authors), or do we open a restore PR following the PR#272 `jw/cip10-workload-spec-repair` precedent?
- Should the restore also resolve the governance fork left by PR#228? That fixup left two options for F1 (whether the in-body 1-byte arm discriminant must also be added to the runner-side `release_request_signing_bytes` / `release_id`): option (a) backward-compatible, option (b) explicit flag-day — deliberately left to the author. Does the restore PR carry that open item forward, or land option (a) first?
- **Incidentally**: the same commit also restored a known-false opcode claim to CIP-8 (§0.1). Out of CBSS scope, but part of the same incident — fix together?

### Q2 Can §3.4.7 serve the CBQS rotation authority directly?

**Blocking: yes**

The CBQS rotation authority is the stream owner's standing rotation workload, which needs the stream's root key to issue the next generation. That matches §3.4.7's motivation almost verbatim: "a standing off-chain service holding a long-lived signing key, neither a dispatcher-assigned runner nor a public tlock consumer".

- The §3.4.7 draft states that `OperatorReleaseGrant` is **same-account only** (`secret_id.account` MUST equal the grant issuer). The CBQS rotation workload is operated by the stream owner and reads the owner's own secret → **same account, constraint satisfied.** Is that reading correct?
- The three-key separation (`K_root` cold / `K_auth` warm / `K_sign` escrowed) maps onto CBQS with `K_sign` = the stream root (or per-generation) key. **But CBQS's usage differs from §3.4.7's original assumption**: §3.4.7 assumes `K_sign` is transiently reconstructed and immediately used to sign, whereas the CBQS rotation workload holds the root key long enough to perform N HPKE wraps. Is that usage still inside §3.4.7's threat model, or does it need an added clause?
- Revocation semantics: §3.4.7's revocation is a **future-release cut-off plus a bounded in-flight grace window**, not a retroactive seal. CBQS's member removal relies on "after the generation bump, a removed producer cannot write the new generation". Do the two conflict?

### Q3 Should the five authorization paths be generalized into one authorizer interface?

**Blocking: no (but it decides what shape of change CBQS submits)**

P4 already abstracts authorization in cbssd via `Cip7SealAuthorizer` (`authorize(seal_request_id, request) -> Cip7SealAuthorization`, with committee-epoch and release-key-scope checks and explicitly modeled chain-query failure).

- Is that trait an intentional general extension point, or CIP-7-specific?
- If general: should CBQS implement a `CbqsSealAuthorizer` (reading the CBQS stream record's generation and member set), or reuse P3's grant path?
- If generalization is wanted, would CIP-24 accept a section enumerating release-authorization classes, folding P1–P5 into one table? **As it stands, P4 has no normative home**, and anyone asking "who in total can trigger CBSS?" must read three CIPs plus the code.

### Q4 Can CBQS reuse P4 (CIP-7 content-key seal) directly and skip a new release mode entirely?

**Blocking: yes — this is the single largest question for CBQS v1 scope**

The CIP-7 comparison (`2026-07-27_cbqs-vs-cip7-comparison.md`, R2) recommends CBQS reuse `0x0D`'s `AccountKeyRegistration` as the member HPKE recipient identity. If the P4 release path is reused too, then:

- a 100-person room is 100 accounts each with one registered X25519 key, with fan-out carried by the CBSS committee (isomorphic to the 10,000-subscriber path CIP-7 already claims);
- **the CBQS envelope subsystem, companion key stream, per-member dual keys, and three-step rotation state machine all leave v1** (review H2 dissolves).

What we need the CBSS team to judge:

1. Can P4's authorization surface (`Cip7SealAuthorizer`) accept a non-SKM authorization source (a CBQS stream record plus generation), or is it hard-bound to `0x0D`'s `StreamAccess`?
2. P4's fan-out cost model is "one `WrappedContentKey` row per epoch plus one SealRequest per buyer per epoch". CBQS with 100 members per generation means 100 SealRequests per generation. Is that the same order of magnitude as CIP-7's 10,000-subscriber claim, or different? How do limits like `MAX_EPOCHS_PER_ACQUIRE = 256` map over?
3. P4 is subscriber-paid (the buyer pays and triggers the SealRequest); CBQS is owner-paid. In the implementation, are "who triggers" and "who pays" separable?

**The answers to these three decide whether CBQS v1 "reuses P4 and drops envelopes" or "goes through P3 and builds them".** Until then, §1.4.4 should not be implemented.

### Q5 Release latency and rotation SLO

**Blocking: no (but it decides whether acceptance can pass)**

CBQS's first acceptance test is a 100-person chat room where joins and leaves trigger rotation. Known numbers: CIP-7 reports "typically 4–5 blocks" end to end, bounded by `REQUEST_FRESHNESS_BLOCKS = 384`; CIP-24 §3.7 validates at **current head**, so an ACL permitted at the request block but revoked before submission causes receipt rejection (the proxy ate the work).

- What is the realistic latency distribution for one rotation (obtaining generation N+1) — p50 / p99?
- How should the urgency of member removal be reconciled with that latency — is there a recommended "cut authorization first, rotate keys second" sequence? (CBQS §1.4.4's three-step machine separates the authorization-generation bump from the encryption-generation bump for exactly this reason, but gives no latency budget.)
- Does frequent rotation collide with `MAX_RELEASES_PER_ACTOR_PER_HOUR` or `MAX_RELEASE_OVERDRAFT`? The CBQS rotation workload is not an actor — how do those quotas apply?

### Q6 CBSS degradation behavior

**Blocking: no**

CBQS §1.15 #2 asks this directly: "CBSS degradation behavior (cached keys? grace generations?)".

- When the committee is unavailable (fewer than t proxies responding), what is the correct CBQS posture — refuse new members but keep existing streams readable from cached keys, or fail closed?
- Is there an officially recommended grace semantics, or is this consumer-owned? (Compare CIP-34 sealed-bid: CIP-34 owns its own liveness fallback `AUCTION_GRACE`; CBSS provides none.)

### Q7 Committee epoch / reshare interaction with CBQS generations

**Blocking: no (but it is a consensus-safety class of risk)**

CBSS carries three epoch concepts — `committee_epoch`, `wrap_epoch`, `quorum_epoch` — with a hard single-epoch quorum rule (a cross-epoch Lagrange combine yields the wrong σ → `MixedEpochReceipts`). CIP-7 binds `committee_epoch` into `WrappedDek.aad` and requires `register_content_keys` to check it against the current epoch (else `COMMITTEE_EPOCH_MISMATCH`).

- Must a CBQS encryption-key generation bind `committee_epoch`? (It appears mandatory, otherwise a reshare renders already-published envelopes undecryptable.)
- What happens if a reshare lands between steps of the CBQS three-step rotation? CBQS claims "stopping between steps is safe", but if the N+1 obtained in step (1) is bound to the old `committee_epoch`, is it still decryptable after step (3)?
- P3's `release_id` originally omitted `serve_epoch`; PR#228's F2 fixed exactly that (nonce reuse across a reshare → collision with the old `quorum_epoch` → release stuck on `MixedEpochReceipts`). If CBQS goes through P3, does it hit the same trap?

### Q8 Does `MAX_ACL_ACTORS = 64` need to move?

**Blocking: no**

The review confirmed this is a §4.5 governance parameter and that the ACL is a runtime gate, not a cryptographic recipient list (`wrapped_dek` is O(1); ACL edits require no re-wrap). The CBQS design treats it as a structural wall, which is a misattribution.

- If CBQS goes through P3 or P4, `MAX_ACL_ACTORS` is not involved at all — correct? (Our reading: P3 replaces the ACL with a grant, P4 replaces it with the SKM access record; neither consumes ACL entries.)
- If some hybrid still needs the actor ACL, what is the real cost of raising 64 to 256 (storage, validation, gas)? We do **not** favor this route; we only want to confirm it is not the only one.

### Q9 `tee_required` and the threat-model boundary

**Blocking: no**

§3.4.7's stated limit: it removes plaintext at-rest storage and adds revocability, thresholding, and audit, but does **not** remove transient reconstruction (the key is in service memory at signing time) unless `tee_required` — which depends on the §9.5.1 `0x05` grant-scoped attestation companion, a cross-repo dependency not yet built.

- The CBQS rotation workload has the same posture (the root key is in memory during rotation). Should CBQS state this explicitly in its trust-posture section, or may it cite §3.4.7 §8.9?
- Will the `0x05` TEE companion's timeline become a CBQS dependency, or can CBQS ship non-TEE first?

---

## 3 Dependency matrix: which answer changes which CBQS decision

| Question | If answer A | If answer B |
|---|---|---|
| **Q4** (reuse P4?) | Reuse → **v1 drops the envelope subsystem, companion key stream, dual keys, and three-step rotation**; H2 dissolves and M1 closes; member keys move to the `0x0D` registry | Not reusable → go through P3, keep envelopes, but rewrite §1.4.4 as "rotation authorization via the §3.4.7 grant" rather than inventing an authorization surface |
| **Q2** (§3.4.7 applies?) | Applies → the CBQS/CBSS integration shrinks to "register one `OperatorReleaseGrant`", closing most of §1.15 #2 | Does not apply → only then is a genuinely new release mode needed, and it should be raised as a CIP-24 amendment rather than a CBQS-private mechanism |
| **Q1** (§3.4.7 restore) | CBSS team restores → we simply cite it | We restore → we open the restore PR carrying PR#228's F1 open item |
| **Q3** (generalize authorizer) | Generalize → CBQS submits a `CbqsSealAuthorizer` implementation | Do not → CBQS uses P3's grant and five coexisting paths remain |
| **Q5** (latency) | p99 acceptable → the 100-person acceptance test can run | Unacceptable → member removal needs "cut authorization first, rotate later", and CBQS must publish an explicit latency budget |
| **Q7** (epoch interaction) | Must bind `committee_epoch` → the CBQS generation definition gains a field | Not needed → status quo holds (we believe binding is mandatory; please confirm) |

**Suggested ordering**: Q4 → Q2 → Q1 is the critical path; the rest can run in parallel. One answer to Q4 determines whether an entire v1 subsystem is cut, which justifies a synchronous meeting rather than asynchronous round trips.

---

## 4 Appendix: a process problem surfaced by this verification (out of CBSS scope, but worth raising)

The `cowboyinc/cowboy` docs repository has seen at least two cases of "a stale branch overwriting a merged spec amendment":

- PR#242 (Twilio example) overwrote CIP-24 §3.4.7 (§0.1 above) and remains **unrepaired**; the same commit restored a known-false opcode claim to CIP-8.
- CIP-10 persistent workloads suffered the same loss and were repaired by PR#272 `jw/cip10-workload-spec-repair`.

Both were "an example/unrelated PR carrying a stale copy of a spec file". Suggested guardrails (any one materially reduces recurrence):

1. **CODEOWNERS**: require spec-owner approval for `docs/cips/**` and `docs/whitepaper/**`, and disallow example-directory changes from touching those paths.
2. **CI check**: flag any PR touching both `examples/**` and `docs/cips/**` and require explicit confirmation.
3. **Line-regression gate**: any PR reducing a `docs/cips/*.md` by more than N net lines must justify the deletion in its description (this one was −226 with no explanation).
4. **Require up-to-date branches** for `docs/**`: the root cause is merge rather than rebase.

This belongs to governance (CIP-12 / repository administration) rather than the CBSS team, but the incident only surfaced while verifying CBSS release paths, so it is recorded here.

---

_Verified by: Marshal cognitive loop. Primary sources: `cowboyinc/cowboy` origin/main (after `git fetch`), GitHub metadata for PR#227/#228/#242, `git log -S` pickaxe, `cbss/crates/cbssd/src/cip7_content_key_seal.rs`, `node/execution/src/stream_key_manager.rs`, and `refs/analysis/2026-07-06-cip24-operator-principal-release-amendment-draft.md`. Advisory only, non-blocking._
