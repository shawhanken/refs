# COW-2733 — MajorityVote / StructuredMatch vs CIP-2 §9/§9.1: canonicalization triage

**Date:** 2026-07-29
**Spec:** CIP-2 §9 (verification modes table), §9.1 (StructuredMatch pipeline), §9.1.4 (why MajorityVote for non-deterministic ops); CIP-23 §3.5.1a/§3.5.2 + CIP-11 §12.6 (`canonical_result_cbor`, COW-2703).
**Follow-up to:** COW-2703 (canonical `result.data` preimage; merged, dormant behind `CANONICAL_RESULT_PREIMAGE_ACTIVATION_HEIGHT = u64::MAX`), which **deliberately scoped MajorityVote/StructuredMatch OUT** (§3.5.2 note references "a separate issue" = this one).
**Verdict:** the two modes **do need a canonical fingerprint** (reuse `canonical_result_cbor`), gated behind an activation height — plus MajorityVote has a second, independent §9 drift (it does not extract `vote_field`). Not a spec-amendment case: the spec is clear; the shipped code drifts.

## 1. What the spec says

- **§9 table — MajorityVote (N≥3):** "**Extract `vote_field`, majority wins with threshold.** Structurally correct mode for **non-deterministic** operations like DNS resolution (§9.1.4)." The wire type is `VerifierCheck::MajorityVote { field: String }` — a single field to vote on.
- **§9 table — StructuredMatch (N≥2):** a pipeline of checks (JsonSchema, field matching, tolerance, range, per-field majority). `VerifierCheck::StructuredMatch { fields: Vec<String> }`.
- **§9.1.4:** MajorityVote is *the* mode for non-deterministic external observations — the entire point is that runners' full outputs differ (timestamps, ordering, incidental fields) while the *voted quantity* agrees.
- **§9 Deterministic row (COW-2703):** at/above activation, the match keys on `canonical_result_cbor(result.data)` (integral-float-normalizing, sorted-keys, no-floats/`Nano`); a non-integral `binary64`/NaN/±Inf/over-cap form is INVALID (no canonical key), slashed only when the valid cohort reaches threshold.

## 2. What the code does (verifier.rs, `verify_results`)

- **MajorityVote (`:1411-1481`):** groups results by the **full** `serde_json::to_string(&result.data)` (`:1433`), takes the largest group as consensus, and **slashes every runner whose full-result string ≠ the winning string** (`:1460-1472`, `runners_to_slash`). It never reads the `field` from `MajorityVote { field }`.
- **StructuredMatch (`:1483-1598`):** `fingerprint_fn` (`:1552`) is `serde_json::to_string` of either the full data (no fields) or a sub-object of the named `fields`; groups by that, largest group wins. **`runners_to_slash = schema_slashed`** (`:1596`) — only JSON-schema violators are slashed; a fingerprint-minority runner is **not** slashed (it just fails to reach threshold).
- **Deterministic (`:1600+`):** already branches on `CANONICAL_RESULT_PREIMAGE_ACTIVATION_HEIGHT` and keys on `canonical_result_cbor` at/above it (COW-2703).

## 3. Findings

### F1 (HIGH) — MajorityVote non-canonical fingerprint wrongfully slashes honest runners
`serde_json::to_string(&serde_json::Value)` is deterministic in **key order** (serde_json's `Map` is BTreeMap-backed here — `preserve_order` is not enabled) but **not** in numeric representation: a runner emitting the integer `5` produces `Value::Number(5)` → `"5"`, while a runner emitting `5.0` produces `Value::Number(5.0)` → `"5.0"`. These are the **same logical value** but land in **different groups** → the minority representation is **slashed for Dissent** even though it agreed. `canonical_result_cbor` normalizes integral floats to ints (§3.5.1a), collapsing `5`/`5.0` to one key — which is exactly why COW-2703 introduced it for Deterministic. MajorityVote slashes on the mismatch, so the wrongful-slash is realized here (unlike StructuredMatch).

### F2 (HIGH) — MajorityVote votes on the FULL result, not `vote_field` (§9 non-conformance)
§9 says "Extract `vote_field`, majority wins". The code votes on the entire `result.data`, ignoring `MajorityVote { field }`. For the non-deterministic operations MajorityVote exists to serve (§9.1.4), the full outputs legitimately differ in incidental fields (timestamps, source ordering, latency) while the voted field agrees — so full-result voting produces **spurious disagreement**, either failing consensus (`ThresholdNotMet`) or, worse, slashing the honest runners whose incidental fields differ. The fix is to fingerprint on `canonical_result_cbor(result.data[field])` (the extracted field), not the whole object.

### F3 (MEDIUM) — StructuredMatch non-canonical fingerprint causes spurious `ThresholdNotMet` (no wrongful slash)
Same non-canonical `serde_json::to_string` in `fingerprint_fn`, but `runners_to_slash = schema_slashed` — fingerprint-minority runners are **not** slashed. So the impact is limited to **consensus/liveness**: two honest runners emitting `5` vs `5.0` for a matched field split the group, which can drop the largest cohort below threshold → the job wrongly fails `ThresholdNotMet` (no payout, no slash). Lower severity than F1/F2, but the same root cause and the same fix.

### Non-issue — key ordering
Because `serde_json`'s `Map` is BTreeMap-backed in this build (`preserve_order` absent from `Cargo.lock`), object key order is already canonical; the drift is purely numeric-representation + the F2 field-scoping. (If `preserve_order` were ever enabled, key order would become a fourth divergence — the canonical form removes that latent hazard too.)

## 4. Recommendation

**Canonicalize both fingerprints via `canonical_result_cbor`, gated behind an activation height — the same shape as COW-2703's Deterministic fix — and extract `vote_field` in MajorityVote.** Concretely, as a follow-up implementation PR:

1. **New dormant gate** (or reuse `CANONICAL_RESULT_PREIMAGE_ACTIVATION_HEIGHT` if governance wants a single flag-day for all quorum modes; a *separate* `QUORUM_CANONICAL_FINGERPRINT_ACTIVATION_HEIGHT` is cleaner if the reconciliation lands after 2703 activates). Below the height: verbatim `serde_json::to_string` (byte-identical to today). At/above:
   - **MajorityVote:** fingerprint = `canonical_result_cbor(result.data[field])` (extract `vote_field` first, F2); slash the canonical-minority. A `result.data` missing the field, or whose extracted form is INVALID (non-integral `binary64`/NaN/±Inf/over-cap, per §3.5.1a), has no canonical key → dispositioned by the existing threshold-gated slash exactly like Deterministic (no new predicate).
   - **StructuredMatch:** fingerprint = `canonical_result_cbor` of the named-fields sub-object (or full data when no fields). Grouping only (no new slash path).
2. **No-floats/`Nano` alignment:** consensus-reproducible voted values MUST be scaled-integer `Nano` (WP no-floats rule; the fingerprint pins serialization, not `f64` computation) — inherit the §3.5.2 INVALID handling verbatim.
3. **Determinism:** decide the canonical form once per `verify_results` call at its verification-block height (as Deterministic does), so all validators branch identically.
4. **Backfill:** replace the CIP-23 §3.5.2 amendment's "separate issue" placeholder and the design-spec placeholders with **COW-2733**, and note the MajorityVote `vote_field` extraction as a §9 conformance fix (not just a canonicalization).

**Why gated, not immediate:** changing the fingerprint changes grouping/slashing = consensus behavior. A staggered rollout with two fingerprint rules forks. The dormant gate makes the deploy byte-identical and the switch a coordinated flag-day — the discipline COW-2703 already established (and the one node#1175's `cae_final` skip-serialize learned the hard way).

**Governance touchpoint:** F2 (full-result → `vote_field`) is a *behavioral* change, not just serialization — a job that today passes MajorityVote only when full results agree will, post-fix, pass when the voted field agrees. That is the §9-conformant behavior and strictly more permissive (fewer spurious slashes), but it should be called out at the flag-day so operators know the semantics changed.

## 5. Anchors (verified 2026-07-29)

MajorityVote `verifier.rs:1411-1481` (fingerprint `:1433`, slash `:1460-1472`); StructuredMatch `:1483-1598` (`fingerprint_fn:1552`, `runners_to_slash: schema_slashed :1596`); Deterministic canonical branch `:1600+`. Canonical machinery: `cowboy_types::{canonical_result_cbor, canonical_result_cbor_no_floats, result_preimage, CanonicalResultError}` (`types/src/lib.rs:25`), gate `CANONICAL_RESULT_PREIMAGE_ACTIVATION_HEIGHT` (`constants.rs:797`). Wire types: `VerifierCheck::MajorityVote { field }`, `StructuredMatch { fields }`.
