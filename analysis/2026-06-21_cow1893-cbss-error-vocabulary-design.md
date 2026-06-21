# COW-1893 — CIP-24 §5.3 canonical error vocabulary for CBSS chain handlers

**Repo:** node · **Status:** design approved · **Date:** 2026-06-21 · **Consensus:** Part B yes (receipt_root, flag-day); Part A no · **Delivery:** multi-PR; this spec covers **PR1**.

## Problem

CIP-24 §5.3 defines a canonical error vocabulary (~30 named errors) that "implementations MUST use ... SDK / runner / proxy / chain handlers all map their failure modes to this set." The CBSS chain handlers in `node/execution/src/cbss.rs` instead collapse nearly all named failures into the generic `ExecutionError::InvalidData` (~217 occurrences). A failed tx's `StructuredError` (including its error code) enters `logs_root → receipt_root`, so callers/indexers cannot distinguish failure modes, and the on-chain receipt does not carry the canonical code.

## Goal (whole ticket)

Every named CBSS failure mode returns its §5.3 canonical error with a distinct structured error code (E17xx, the CIP-24 range). Delivered across multiple PRs to bound the consensus blast (each handler-site change alters the receipt code for that failure → flag-day).

## Key structural insight (drives the increment slicing)

- Adding an `ExecutionError` variant, registering its `ErrorSpec` code, adding its doc line, and mapping it in `structured_error_map.rs` are **purely additive and non-consensus** — until a handler actually *returns* the variant, no receipt changes.
- Only changing a handler site from `Err(ExecutionError::InvalidData)` to `Err(ExecutionError::<Named>)` is **consensus** (the failed tx's receipt code changes → receipt_root → flag-day).

So PR1 reserves the **entire** vocabulary up front (non-consensus) and wires only **one** handler family (the release/receipt path) as the first, bounded consensus increment.

## PR1 scope

### Part A — reserve the full §5.3 vocabulary (non-consensus, may land independently)

1. **`execution/src/error.rs`** — add an `ExecutionError` variant for each §5.3 name not already present. New (~27): `SecretNotFound`, `SecretVersionDeleted`, `SecretPending`, `SecretAccessDenied`, `SecretRequiresTEE`, `SecretQuotaExceeded`, `SecretCommitteeUnavailable`, `SecretDkgInProgress`, `MissingAccountReleaseKey`, `WrapEpochMismatch`, `AadMismatch`, `UnsupportedWrappedDekVersion`, `RecipientMismatch`, `StaleRequestBlock`, `StaleChallenge`, `StaleCommitteeEpoch`, `ReshareGraceCapacity`, `InvalidRunnerSignature`, `InvalidProxySignature`, `InvalidPartialReencrypt`, `ReceiptAlreadyRecorded`, `ReceiptOrderingInvalid`, `QuorumAlreadyReached`, `MixedEpochReceipts`, `LivenessChallengeAlreadyOpen`, `ChallengePremature`, `CiphertextCorrupted`. Reuse any that already exist (`EpochMismatch`, `ActorAccountInsufficient` — to be reconciled exactly at implementation against `error.rs`; a substring hit is not proof of an exact variant). All new variants are unit structs (no payload) unless an existing sibling carries context; keep them payload-free for PR1 (the `what`/`why` strings carry detail).
2. **`storage/src/error_codes.rs`** — register one `ErrorSpec { code, slug: "E17xx", description, fix }` per new error, in a **contiguous block starting at the first free E17xx code**. The start code MUST be chosen as `max(highest code registered in error_codes.rs, highest E17xx referenced in structured_error_map.rs) + 1` — i.e. reconcile **both** files (the 1703-collision class came from checking only one). Descriptions/fixes are lifted from the §5.3 comments.
3. **`docs/errors/README.md`** — add a line per new slug. (`error_codes.rs` has a test asserting every registered slug appears in this file; CI fails otherwise.)
4. **`execution/src/structured_error_map.rs`** — map each new `ExecutionError::<Named>` → its E17xx code (`=> (code, vec![])`).

Part A changes no handler behavior: `cargo test` green, no receipt changes.

### Part B — wire the release/receipt path (the only consensus change in PR1)

In `execution/src/cbss.rs`, the release/receipt handlers — primarily `handle_cbss_submit_release_receipt`, plus the directly-associated release validation (`load_release_key_view` epoch checks) it calls — replace each *specific* `Err(ExecutionError::InvalidData)` with the §5.3 error its guard denotes. Mapping (verify each against the §5.3 comment + the guard condition at the site):

| Guard at the site | §5.3 error |
|---|---|
| `committee_epoch_at_serve != body.serve_epoch` (quorum_epoch init from serve_epoch) | `MixedEpochReceipts` |
| `release_key.epoch != body.serve_epoch` (proxy view ≠ runner-pinned) | `EpochMismatch` |
| `committee_epoch_at_serve` neither current nor in retained prior epochs | `StaleCommitteeEpoch` |
| `body.request_block` outside `REQUEST_FRESHNESS_BLOCKS` window | `StaleRequestBlock` |
| `served_at_block < request_block` or `> submission_block` | `ReceiptOrderingInvalid` |
| `(release_id, proxy_id)` already in `release_receipt` set | `ReceiptAlreadyRecorded` |
| set already has `threshold` entries | `QuorumAlreadyReached` |
| `recipient ≠ SecretVersion.recipient` | `RecipientMismatch` |
| proxy_sig fails verification | `InvalidProxySignature` |
| BLS pairing / partial malformed | `InvalidPartialReencrypt` |
| actor release debt past `−MAX_RELEASE_OVERDRAFT` | `ActorAccountInsufficient` |

Sites in this handler that are *not* one of these named conditions (e.g. malformed decode, missing SecretVersion record on a path the §5.3 table doesn't name) keep `InvalidData` — do not force a named error where the spec has none.

## Faithful-mapping method (correctness discipline)

This is a wide change where a wrong mapping is a silent consensus bug. For PR1 Part B, each converted site is justified inline (a one-line comment citing the §5.3 name) and covered by a test that drives that exact invalid input and asserts the specific resulting code. Do **not** batch-replace; convert and test one guard at a time.

## Components / boundaries

- `error.rs` (variant definitions) ← `structured_error_map.rs` (variant→code) ← `error_codes.rs` (code registry + docs gate). These three move together for each error.
- `cbss.rs` handlers consume the variants. PR1 touches only the release/receipt family.

## Error handling

No new error *paths* — this reclassifies existing failures. The release/receipt handler's control flow (which inputs are rejected) is unchanged; only the *code* attached to the rejection changes.

## Testing

- Part A: `error_codes.rs` slug/docs consistency test passes; a round-trip test that each new code resolves via `spec(code)` and `spec_by_slug(slug)`.
- Part B: per converted site, a handler test feeding the matching invalid input and asserting the returned `StructuredError.code` equals the expected E17xx (replacing any prior assertion that it was the generic `InvalidData` code).
- Existing CBSS handler tests updated where they asserted the generic code for a now-named site.
- econ + state-root invariants unchanged (error-only change): run the standard set.

## Consensus / flag-day

Part B changes the receipt code for failed release-receipt txs → `receipt_root` → consensus flag-day (Marshal `needs_human`). Part A is non-consensus. The §5.3 codes are also consumed by SDK/runner/proxy (cross-repo), but PR1 only adds the chain-side codes (additive); cross-repo adoption is separate.

## Out of scope (PR1) — follow-up PRs

Wiring the remaining §5.3 categories to their handlers, one bounded consensus PR each (codes already reserved in PR1, so these are pure handler-site rewires + tests):
- setup-time: `WrapEpochMismatch` / `AadMismatch` / `UnsupportedWrappedDekVersion` / `RecipientMismatch` / `MissingAccountReleaseKey` (SetSecret/FinalizeSecretVersion).
- lookup/state: `SecretNotFound` / `SecretVersionDeleted` / `SecretPending` / `SecretAccessDenied` / `SecretRequiresTEE` / `SecretQuotaExceeded` / `SecretCommitteeUnavailable` / `SecretDkgInProgress`.
- signature/proof, liveness (`LivenessChallengeAlreadyOpen` / `ChallengePremature` / `StaleChallenge`), reshare (`ReshareGraceCapacity`), decryption (`CiphertextCorrupted`, runner-side).

## Verification gate

`cargo build --workspace`; `cargo test -p cowboy-execution` + `-p cowboy-types` + `-p cowboy-storage`; `cargo clippy --workspace --all-targets` (node CI flags); the consensus invariant set (econ ×4, state-root ×3, timer_burn) green; Marshal gate. Base `devnet`.
