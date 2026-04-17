# Plan: Structured PVM Error Messages (What / Why / Fix / Docs)

## Context

Today, PVM-related errors surface to users as opaque strings:
- `TransactionReceipt.status = ExecutionStatus::ExecutionError(String)` is filled via `format!("{:?}", err)` (Debug output) in `execution/src/execution/transaction.rs:87,100,115,135,276`.
- `HostError` (`pvm/crates/pvm-host/src/lib.rs:18-27`) is a bare 8-variant enum — numeric codes exist but no message, no remediation hint.
- Python SDK exceptions in `cowboy_sdk/errors.py` (~20 classes) all collapse to `HostError::Internal` through `map_exception()` at `pvm/crates/pvm-runtime/src/lib.rs:798-867`.
- Static validation (`pvm_executor.rs::validate_actor_code`, lines 56-123) already cites CIP-3 §2.4 in some reasons but the wrapper loses that structure.

Goal: every PVM-related failure reaches the client as a machine-readable record with `{ code, category, what, why, fix, docs_url, context }`, in English, with a placeholder docs URL constant and a single source of truth for error codes.

Chosen shape (confirmed with user):
- Scope: all 4 layers (static / runtime-host / Python SDK mapping / receipt format)
- Output: structured fields (breaking schema change, no dual-track)
- Docs: `DOCS_BASE = "https://docs.cowboy.dev/errors/"` constant + `<slug>` suffix
- Language: English

## Critical files

| Path | Role |
|---|---|
| `node/storage/src/types.rs:337-397` | `ExecutionStatus` enum + codec — receipt schema change lives here |
| `node/storage/src/lib.rs` | re-export `StructuredError` + registry |
| `node/execution/src/error.rs:57` | `PvmError(String)` becomes structured |
| `node/execution/src/execution/transaction.rs:87,100,115,135,276` | `format!("{:?}", e)` call sites replaced |
| `node/execution/src/pvm_executor.rs:56-123` | static validation errors flow unchanged; conversion at boundary |
| `node/execution/src/pvm_host.rs` | `HostError` return sites unchanged; enrichment at executor boundary |
| `node/pvm/crates/pvm-host/src/lib.rs:18-99` | `HostError` left alone (compact code preserved) |
| `node/pvm/crates/pvm-runtime/src/lib.rs:798-867` | `map_exception` extended to return `PyHostFault` (HostError + optional rich attrs) |
| `node/cowboy_sdk/errors.py` | annotate each exception with `HOST_ERROR_CODE` / `ERROR_SLUG` / `why` / `fix` |

## New files

- `node/storage/src/structured_error.rs` — `StructuredError` struct with `{ code: u32, category: &'static str, slug: String, what: String, why: Option<String>, fix: Option<String>, docs_url: String, context: BTreeMap<String,String> }`; serde + `commonware_codec::{Write,Read,EncodeSize}`.
- `node/storage/src/error_codes.rs` — `DOCS_BASE` const; `ErrorSpec { code, slug, category, fix, cip }`; `fn spec(code) -> Option<&ErrorSpec>`; `fn docs_url(code) -> String`. Code ranges:
  - `E1100-E1199` static PVM validation
  - `E1200-E1299` runtime / host API (E1201..E1208 = HostError codes 1..8)
  - `E1300-E1399` entitlements
  - `E1400-E1499` CIP-20 tokens
  - `E1500-E1599` timers / deferred
  - `E1600-E1699` runner / consensus / job
  - `E1000-E1099` tx pre-checks (signature, nonce, basefee, balance)
  - `E1900-E1999` internal
- `node/execution/src/structured_error_map.rs` — `IntoStructured` trait + `impl` for `ExecutionError` and `HostError`. Pull `what` from thiserror `Display`, `why/fix/docs_url` from registry, `context` from variant fields (e.g., `InvalidNonce{expected,actual}` → context map).

## Placement decision

`storage` crate is a dependency of `execution`, not the other way around. Therefore `StructuredError` and the registry live in `storage`. Trait impls that need `ExecutionError` live in `execution`.

## Implementation phases (each leaves the tree green)

**Phase 1 — Foundation (no behavior change)**
1. Create `storage/src/error_codes.rs` + `storage/src/structured_error.rs`; export from `storage/src/lib.rs`.
2. Unit tests: codec round-trip; every registered slug is unique; `docs_url()` shape.

**Phase 2 — Conversion layer**
3. Create `execution/src/structured_error_map.rs` with `IntoStructured for ExecutionError` + `for HostError`. Registry rows added for every variant.
4. Tests: exhaustive variant coverage (failure to add a row = compile error via `#[deny(non_exhaustive)]` style match).

**Phase 3 — Receipt switch (only breaking commit)**
5. `storage/src/types.rs:337` — `ExecutionStatus::ExecutionError(String)` → `ExecutionError(StructuredError)`. Update `Write/Read/EncodeSize` (lines 343-397).
6. Patch all 5 call sites in `execution/src/execution/transaction.rs` to use `err.into_structured()` instead of `format!("{:?}", err)`; grep for any other `ExecutionError(format!` sites and fix.
7. Patch RPC/indexer consumers: `node/rpc/src/**`, `node/indexer/src/**` — serde handles JSON automatically, but `match ExecutionStatus::ExecutionError(s)` destructuring must be updated.
8. Repair broken tests in `execution/src/execution/tests.rs`, receipt golden-hash tests in `storage/src/merkle_utils.rs`, and any indexer JSON snapshots.

**Phase 4 — PVM runtime enrichment**
9. `execution/src/error.rs:57` — `PvmError(String)` → `PvmError { host_code: u32, slug: Option<String>, py_exc_type: String, py_msg: String, why: Option<String>, fix: Option<String> }`.
10. `pvm/crates/pvm-runtime/src/lib.rs:798-867` — introduce `PyHostFault { host: HostError, slug, what, why, fix }`. Extend `host_error_from_exception` (lines 849-866) to read optional `slug`/`why`/`fix`/`what` attributes off the Python exception before falling back to `HostError` defaults. Update the single caller of `map_exception`.
11. Executor boundary (`execution/src/pvm_executor.rs`): when catching `PyHostFault`, construct `ExecutionError::PvmError { .. }` with fields plumbed. `IntoStructured` prefers Python-supplied fields over registry defaults.

**Phase 5 — Python SDK annotation**
12. `cowboy_sdk/errors.py` — add `HOST_ERROR_CODE: int`, `ERROR_SLUG: str`, `why: str`, `fix: str` class attributes to every `CowboyError` subclass. Map each to one of the 8 HostError codes + a precise slug in the E1xxx registry.
13. Integration test under `pvm/crates/pvm-runtime/tests/` or `execution/src/execution/tests.rs`: Python actor raises `InsufficientBalance`, receipt shows full structured fields.

**Phase 6 — Registry doc stubs**
14. Generate `docs/errors/<slug>.md` stubs (one per registered code) or a single `docs/errors/index.md`. Add a registry test asserting every code has a stub entry (can start empty; prevents drift). Not required to be hosted at `DOCS_BASE` yet — constant is a placeholder per user direction.

## Reused infrastructure

- `thiserror` Display on `ExecutionError` (already present, currently bypassed by `format!("{:?}")`) — becomes the `what` field.
- `HostError::code()`/`from_code()` — already stable numeric codes; reused as the low byte of the E12xx range.
- Existing CIP-3 §2.4 citations in `pvm_executor.rs:71-76,98-103` — lifted into registry `cip` field, no text rewrite.
- `commonware_codec::{Write,Read,EncodeSize}` — same codec style as the existing `ExecutionStatus` impl.
- `serde` derives on types in `storage/src/types.rs` — RPC/indexer JSON serialization is automatic.

## Verification

Per-phase unit tests (see above). End-to-end run after Phase 5:

```bash
# Build + start local validator
cd /home/ubuntu/workspace/node
./scripts/run_build.sh
./scripts/start_validator.sh

# Trigger each error class and inspect receipt JSON via RPC
# 1. Bad signature  → E1001 expected
# 2. Insufficient balance for gas  → E1004
# 3. Deploy actor with `import time` (non-determinism)  → E11xx
# 4. Actor calls `state_set` without storage.kv entitlement  → E1301 (MissingEntitlement)
# 5. Python actor `raise InsufficientBalance(...)`  → E14xx with SDK-authored why/fix

cargo test --workspace
cargo test -p cowboy-execution -- structured_error
cargo test -p cowboy-storage -- error_codes
```

Pass criteria: every triggered receipt JSON contains `{code, category, slug, what, why, fix, docs_url, context}`; `docs_url` is `https://docs.cowboy.dev/errors/E1xxx`; no `format!("{:?}", ...)` remains in error-packing paths (grep check in CI).

## Out of scope / follow-ups

- Hosting real docs at `DOCS_BASE` — content generation is a separate task.
- i18n — user chose English-only for now.
- Backwards-compat dual-track — user explicitly chose structured-only; Phase 3 is a breaking change for any external consumer parsing the old `ExecutionError(String)` shape.
- `HostError` itself stays compact (not extended with `String` fields) to avoid allocations in the pvm workspace hot path; enrichment happens at the execution boundary only.
