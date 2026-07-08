# COW-979 — Historical State Query (snapshot-height slice) Design — 2026-06-22

**Issue:** COW-979 "[Node] Historical state queries (proof-of-historical-state for light clients)" — `GET /state/at/{height}/actor/{addr}/key/{key}` → `(value, proof, state_root)`.

**Scope decided:** the **snapshot-height-only** slice (not full archive mode). Non-consensus, read-path only.

**Status:** design (implementation is moderate-large + DoS-sensitive; this design must be agreed before coding).

---

## 1. Feasibility (verified against `origin/devnet`)

The snapshot slice is **architecturally feasible with no QMDB or proof-format changes**:

- The state DB (`storage/src/db.rs:38` `UnifiedStateDb = CurrentVariableDb<…Blake3…>`) has **no as-of/versioned read** — `state_proof()` / `key_value_proof()` (`blockchain_storage.rs:956-979`) read only the *current* root. So you cannot query a past height against the live DB.
- BUT the operations back to the latest snapshot are **retained** (`capped_state_prune_loc`, `state_sync.rs:119-132` pins the prune floor to `snapshot.op_count`).
- `sync_state()` (`state_sync.rs:252-290`) **reconstructs a `UnifiedStateDb` from those ops** and asserts the rebuilt root equals `snapshot.canonical_root`.
- The reconstructed DB's `state_proof()` then yields a CIP-17 proof that **verifies against `snapshot.canonical_root`** — the proof verifier (`proof-verifier/src/mmr.rs:510-523`) checks against *any* passed-in root, no changes needed.
- `SnapshotCheckpoint` (`state_sync.rs:105-111`) already stores `height`, `ops_root`, `canonical_root`, `range_start`, `op_count`.

**So the data + primitives exist. What's missing is a query layer.**

## 2. The pitfall — naive per-query rebuild is a DoS

`sync_state()` replays **all** ops in `[range_start..op_count]` — up to `SNAPSHOT_INTERVAL_BLOCKS = 100_000` blocks of operations — to materialize the DB. Doing that **per request** would take seconds–minutes and is a trivial DoS vector. A naive `GET /state/at/...` handler that calls `sync_state()` on every request **must not ship** (it would fail security review).

## 3. Safe architecture

**Lazily materialize once, cache one snapshot DB at a time.**

- A `SnapshotQueryCache` holds at most **one** materialized `UnifiedStateDb`, keyed by `snapshot.height`.
- First query for the current snapshot height → run `sync_state()` once, cache the DB.
- Subsequent queries → hit the cached DB (`state_proof()` is fast).
- When the snapshot advances (every 100k blocks, `record_snapshot_checkpoint`) → the cached height no longer matches `latest_snapshot().height`; drop + rebuild lazily on the next query.
- Only the **latest** snapshot height is queryable; any other height → `404` (`snapshot height not retained`). This bounds the cache to one DB and the rebuild cost to once per 100k blocks (amortized).
- Reuse the existing `state_sync_limiter` (100 req/s/IP) for rate-limiting; optionally guard the first-touch rebuild with a single-flight lock so concurrent first-requests don't trigger N rebuilds.

### Missing production piece: a local Resolver
`sync_state` needs a `Resolver<Op = StateOp, …>` that serves the retained ops. Today the only impls (`StorageResolver`, `CodecResolver`, `state_sync.rs:316/409`) are under `#[cfg(test)]`. A **production local resolver** is required that serves ops from the local state DB's retained range — mirror the `/state/operations` server path (`rpc/src/handlers/chain.rs:1977+`), which already reads local ops with MMR proofs, wrapped behind the `Resolver` trait.

## 4. API contract

```
GET /state/at/{height}/actor/{addr}/key/{key_hex}
  200 → { value, proof, canonical_root, snapshot_height }   (height == latest snapshot)
  404 → height is not the latest retained snapshot, or no snapshot recorded yet
  400 → malformed addr/key
  rate-limited via state_sync_limiter
```
Reuse `StateReadResponse` (`rpc/src/responses.rs`) + the CIP-17 proof shape (`storage/src/proof_types.rs`). The light client verifies `proof` against `canonical_root`, and obtains `canonical_root` for `snapshot_height` from the block header at that height (already in the chain).

## 5. Components to build

1. **`LocalOpsResolver`** (storage) — production `Resolver` serving `[range_start..op_count]` from the local DB (promote the test-resolver pattern; reuse `/state/operations` read path).
2. **`SnapshotQueryCache`** (storage) — single-entry cache of a materialized `UnifiedStateDb`, keyed by snapshot height; single-flight rebuild.
3. **`BlockchainStorage::state_at_latest_snapshot(actor, key) -> (value, proof, canonical_root, height)`** — resolve `latest_snapshot()`, ensure cache is materialized for it, `state_proof()` on the cached DB.
4. **RPC handler** `GET /state/at/{height}/actor/{addr}/key/{key}` — validate height == latest snapshot, delegate, rate-limit.

## 6. Test plan

- Storage: seed a DB, advance past one snapshot boundary, materialize via the cache, assert `state_proof()` for a known key verifies against `snapshot.canonical_root` (extend the `state_sync_roundtrip` pattern, `state_sync.rs:341-386`).
- Cache: two queries → one rebuild (assert rebuild count); snapshot advance → rebuild on next query.
- RPC: non-latest height → 404; latest → 200 with a proof a `proof-verifier` round-trip accepts.
- Negative: absent key → CIP-17 exclusion proof against `canonical_root`.

## 7. Effort / risk

- **Non-consensus** (read path), but **moderate-large** (storage DB lifecycle + a new production resolver), and **DoS-sensitive** (the cache is mandatory, not optional).
- pvm/ unaffected. CIP-4 (cross-team owns the fee/state-rent model; included per the roadmap decision) — coordinate the CIP-4 light-client contract.
- Recommend implementing in this order: LocalOpsResolver (+ test) → SnapshotQueryCache (+ rebuild-count test) → storage method → RPC handler. Each step is independently testable.

## 8. Recommendation

Implement the cached version above. Do **not** ship a per-query rebuild. If a first PR is wanted smaller, land #1–#3 (storage primitives + cache, fully tested) without the public RPC route, then the RPC handler as a follow-up — this keeps each PR reviewable and the DoS-avoidance verifiable in isolation.
