# Propose() Cancellation Race: Actor TXs Lost + State Leaked

> **Status:** Fixed on `feat/cip-29-implementation` (this branch).
> **Affects:** chain proposal layer, surfaces with any actor tx whose
> speculative execution exceeds `min_block_interval` (≈ 1s).
> **Discovered:** while bringing up `node/bench`'s new CIP-29 `bench:events`
> module against a local validator.
> **Severity:** correctness (silent state divergence) + liveness (txs lost from
> mempool with no observable error).

## TL;DR

When a `propose()` future is dropped by the consensus framework (because
speculative execution took longer than `min_block_interval`), two things
went wrong:

1. **TX loss:** the transactions popped from mempool via `mempool.next()`
   were never returned. Subsequent proposes saw an empty mempool, finalized
   empty blocks, and the bench's `/transaction/{hash}/receipt` poll timed
   out — even though the bench's locally-computed tx hash was correct.
2. **State leak:** writes accumulated in `state_pending` by the cancelled
   speculative leaked into the *next* speculative's `cache_speculative_batch_with_report`,
   producing a cache for the next height whose contents had no
   corresponding tx in any finalized block. `apply_cached_batch` then
   committed those writes to durable storage, advancing account nonces
   and actor storage with no auditable tx behind them.

Symptom from the bench: every CIP-29 setup tx (`register_position`, LP deploy,
`subscribe_event`) timed out at the receipt-poll stage, despite chain state
silently advancing.

Two-layer patch, 121 lines:

- **L1** (storage): `begin_batch()` defensively clears `*_pending` so a
  cancelled prior batch's writes can't survive into the next.
- **L2** (chain): a `PoppedTxsRestoreGuard` wraps `propose()`'s popped txs
  and re-adds them to mempool on Drop; disarmed only on the `Some(block)`
  success return.

After patching: 4 consecutive actor txs (lending deploy, register_position,
LP deploy, LP setup) all land in blocks 27368–27371 of the test validator
— each one had previously been stuck indefinitely.

## Symptom

`node/bench/run_bench.sh --profile smoke` consistently fails at the 3rd
step (CIP-29 events scenarios). The bench logs:

```
[events] S1@N=1: deploying topology
[events] Deploying lending (stamp=1779193089353)...
[events] S1@N=1 failed: execute register_position timeout
[events] S1@N=8: deploying topology
[events] Deploying lending (stamp=1779193150147)...
[events] S1@N=8 failed: execute register_position timeout
... (4 more iterations of the same pattern)
```

The bench's `deployActorAndWait`-then-`executeActorAndWait` flow:
- `deploy lending` → bench polls `/transaction/{hash}/receipt`, **succeeds within ~600ms**.
- `executeActorAndWait('register_position')` → bench polls the same way, **times out after 60s**.

Yet inspecting the chain side reveals contradictions:

- The deployer's `/account/0x.../{nonce}` field has advanced (e.g. 170 → 171),
  consistent with a successful tx.
- The actor's storage has been mutated (the `register_position` handler
  wrote `pos:deadbeef... = 1000`).
- But `/block/N` for every block since the deploy shows `tx_count = 0` —
  no block contains the register_position tx.
- And `/transaction/{bench_hash}/receipt` returns 404 for the
  bench-computed tx hash.

State changed; no tx exists; receipt unfetchable.

## Reproduction

A minimal reproducer (extracted from `node/bench` and exercising only what
this bug touches):

```bash
cd node/bench
# Use the smoke profile of the patched bench harness, which deploys exactly
# 1 lending actor + 1 LP and tries to drive S1@N=1.
./run_bench.sh --profile smoke --keep-going
```

Or directly via a 60-line node script:

```typescript
// (see commit history in this branch for the full debug_actor_tx.ts)
// 1. Fund a fresh account via faucet.
// 2. Build + submit a DeployActor for the CIP-29 lending actor source
//    (cyclesLimit=1_000_000, cellsLimit=~600_000 — note these are large;
//    that matters, see "Root cause" below).
// 3. Poll /transaction/{bench_hash}/receipt — succeeds in ~200ms.
// 4. Build + submit ExecuteActor with handler='register_position',
//    nonce=deploy_nonce+1.
// 5. Poll /transaction/{bench_hash}/receipt — times out.
// 6. Meanwhile /account/0x... shows nonce += 1 after step 5.
```

## Root cause analysis

### Timeline (one real reproduction, validator log + bench output)

```
T0  = 11:50:41.473  Block 24598 proposed (tx_count=1, the deploy).
T0+ = 11:50:41.529  Block 24598 finalized. Lending actor now exists.
T1  = 11:50:42.495  ThreadId(35) — propose(24599) starts. Pops the
                    register_position tx from mempool. Begins speculative.
T1+ = 11:50:42.496  speculative.rs early-commits prev_heights — applies
                    block 24598's cached batch (500k cells of compiled
                    actor code → QMDB merkleize takes ~1.4s).
T2  = 11:50:43.975  Lending's register_position handler finally runs,
                    calls `runtime.set_state(b"pos:..." , threshold)`.
T2+ = 11:50:43.975  set_actor commit completes.
                    But the consensus framework has already moved on
                    (the propose was supposed to finish within
                    min_block_interval ≈ 1s; it's now T1+1.5s).
                    ThreadId(35)'s propose() future is *dropped*.
T3  = 11:50:43.979  ThreadId(31) — a fresh propose(24599) emits "proposed
                    block height=24599 tx_count=0 duration_ms=473".
                    This is a different thread, fresh propose call.
```

Block 24599's `transactions: Vec<Transaction>` is empty. But the previous
ThreadId(35)'s speculative had populated `self.state_pending` with the
register_position's writes — and never reached its `rollback_batch()`
because it was cancelled mid-flight.

When ThreadId(31)'s speculative starts:

```rust
// node/storage/src/speculative.rs:99-101
let stale: Vec<u64> = self.speculative_cache.keys()
    .filter(|h| **h >= current_height).cloned().collect();
for h in stale { self.speculative_cache.remove(&h); }
```

Removes any cache for height 24599 (in this case there is none, since
ThreadId(35) hadn't reached `cache_speculative_batch_with_report` yet).

Then `begin_batch()` is called:

```rust
// PRE-PATCH:
pub fn begin_batch(&mut self) -> Result<(), Error> {
    self.batch_mode = true;
    Ok(())
}
```

**It does NOT clear `self.state_pending`.** ThreadId(35)'s register_position
writes are still sitting there.

ThreadId(31) runs its per-tx loop — empty block, no work. Then:

```rust
// node/storage/src/speculative.rs:1370 (paraphrased)
self.cache_speculative_batch_with_report(
    block.height.get(),      // = 24599
    all_deferred_txs,
    block_table,
);
// inside the call:
//   speculative_cache.insert(24599, SpeculativeBatch {
//       state_pending: self.state_pending.clone(),  // <-- LEAKED writes
//       ...
//   });
self.rollback_batch();
```

Cache for 24599 now contains register_position's writes, *plus* whatever
empty-loop produced. When `apply_cached_batch_with_report(24599)` runs at
finalize time, these leaked writes commit to durable. Result: nonce ++
and pos:... = 1000 in actor storage, with no matching tx anywhere in the
chain.

Meanwhile the original register_position tx that ThreadId(35) had popped
is just *gone* — mempool.next() pops irreversibly, and the cancelled
future never restored it. The bench's `/transaction/{bench_hash}/receipt`
returns 404 because the chain never wrote a receipt under that hash (no
tx was finalized into a block under that hash; the leaked write went in
without one).

### Why does this surface now? CIP-29 + slow PVM

Pre-CIP-29, actor txs were rare in normal load. The race window is gated
by `min_block_interval` (≈ 1s) vs speculative execution time. Transfers
take <1ms speculatively → cancellation never fires. The race only
materializes when a single tx's speculative execution exceeds ~1s, which
happens reliably on this branch for actor instructions because:

- Python actor handlers cost ~50ms — but the first call against a
  newly-deployed actor needs QMDB to commit the deploy's `cells` writes
  (the compiled Python code, ~500k cells for the bench's lending actor),
  which merkleizes in ~1.4s.
- CIP-29's `emit_event` synchronously fires every subscribed handler
  inside the emitter's tx → an emit with N=32 subscribers is essentially
  33 actor invocations in series, easily exceeding 1s.

So CIP-29's design (correctly) pushes more work into speculative; the
race exposes the bug.

## The fix

### Layer 1 — `storage/src/blockchain_storage.rs::begin_batch()`

```rust
pub fn begin_batch(&mut self) -> Result<(), Error> {
    // Defensive: clear any leftover *_pending from a cancelled prior batch.
    //
    // The consensus engine can drop the propose() future mid-execution
    // (e.g., when an actor handler's speculative execution runs longer
    // than `min_block_interval` and the framework moves on to the next
    // round). When that happens, `execute_block_speculative` never
    // reaches its `rollback_batch()`, leaving partial writes in the
    // `*_pending` vecs. The next speculative — possibly proposing a
    // different (often empty) block — would then `cache_speculative_batch_with_report`
    // a snapshot of those leftover writes, and `apply_cached_batch_with_report`
    // would commit them at finalize-time, producing the divergence
    // "block has 0 txs but account state advanced".
    //
    // Clearing here makes begin_batch idempotent and self-healing: the
    // new batch only ever sees writes produced by this run.
    self.state_pending.clear();
    self.state_pending_map.clear();
    self.tx_index_pending.clear();
    self.tx_receipts_pending.clear();
    self.batch_mode = true;
    Ok(())
}
```

Stops state-leak path A: cancelled speculative writes can no longer be
absorbed by the *next* speculative's cache.

### Layer 2 — `chain/src/mempool.rs::PoppedTxsRestoreGuard` + `application.rs::propose()`

A RAII guard wraps the popped txs. On Drop (cancellation), it spawns a
detached tokio task that re-adds the txs to mempool. On the `Some(block)`
success path, the guard is explicitly `disarm()`-ed so Drop is a no-op.

```rust
// chain/src/mempool.rs (excerpt)
pub struct PoppedTxsRestoreGuard {
    mempool: Arc<Mutex<Mempool>>,
    txs: Vec<Transaction>,
    armed: bool,
}

impl PoppedTxsRestoreGuard {
    pub fn new(mempool: Arc<Mutex<Mempool>>, txs: Vec<Transaction>) -> Self {
        Self { mempool, txs, armed: true }
    }
    pub fn disarm(mut self) { self.armed = false; }
}

impl Drop for PoppedTxsRestoreGuard {
    fn drop(&mut self) {
        if !self.armed || self.txs.is_empty() { return; }
        let mempool = self.mempool.clone();
        let txs = std::mem::take(&mut self.txs);
        let n = txs.len();
        if tokio::runtime::Handle::try_current().is_ok() {
            tokio::spawn(async move {
                let mut mp = mempool.lock().await;
                let mut restored = 0;
                for tx in txs {
                    if mp.add(tx) { restored += 1; }
                }
                tracing::warn!(popped = n, restored,
                    "propose() cancelled; restored popped txs to mempool");
            });
        } else {
            tracing::warn!(popped = n,
                "propose() cancelled outside tokio runtime; popped txs lost");
        }
    }
}
```

```rust
// chain/src/application.rs::propose() (paraphrased)

// ... pop txs from mempool into `transactions` ...

// Arm the guard. If propose() is dropped before reaching the `Some(block)`
// return below, the guard restores popped txs to mempool on Drop.
let restore_guard = self.mempool.as_ref()
    .filter(|_| !transactions.is_empty())
    .map(|mp| PoppedTxsRestoreGuard::new(mp.clone(), transactions.clone()));

// ... speculative execution + Block::new ...

// Success path: the proposed block owns the popped txs. Disarm the guard.
if let Some(g) = restore_guard { g.disarm(); }
Some(block)
```

Stops liveness path B: txs no longer silently lost from mempool.

#### Why a Drop-guard rather than restructuring propose()?

Async cancellation in Rust drops futures at await points. The popped txs
are local data in propose()'s frame; we want them re-inserted whether or
not the caller awaits a "cleanup" branch. Drop is the only deterministic
hook. The detached tokio task is required because Drop is synchronous but
the mempool lock is async; the spawned task is best-effort and logs if it
can't run.

Alternative considered: add `peek_n()` / `take_specific(digests)` to
Mempool so propose() doesn't pop until success. Rejected for now —
larger API surface change, and the Drop-guard is enough to make the
behavior correct.

## Verification

### Tests (all green)

```
cargo test --release -p cowboy-storage --lib   → 392/392
cargo test --release -p cowboy-chain   --lib   → 115/115
cargo test --release -p cowboy-execution --lib → 763/763
```

### Live validator + bench

Patched validator on a fresh test directory, `node/bench/run_bench.sh --profile smoke`:

| Setup tx (in order) | Pre-patch | Post-patch | Where it landed |
|---|---|---|---|
| lending deploy | succeeds | succeeds | block 27368 |
| register_position | **timeout forever** | **succeeds** | block 27369 |
| LP deploy | (never reached) | **succeeds** | block 27370 |
| LP setup (`subscribe_event`) | (never reached) | **succeeds** | block 27371 |
| check_liquidation (emit) | (never reached) | times out† | — |

† still times out, but for a different reason: emit + sync-fire is heavier
than 60s on this PVM. That's an orthogonal performance issue (see
"Follow-ups" below), not a protocol bug.

Behavioral proof of the state-leak fix: during the post-patch events
phase, **49 actor txs committed to durable** (deployer nonce 212 → 261)
and `tx_count`-aggregated block transactions across the same range
*matches*. Pre-patch the equivalent count would have included
"phantom" nonce advances with no corresponding tx in any block.

### Patch surface

```
chain/src/application.rs          | 24 +++++++++++-
chain/src/mempool.rs              | 79 +++++++++++++++++++++++++++++++++++++++
storage/src/blockchain_storage.rs | 19 ++++++++++
 3 files changed, 120 insertions(+), 2 deletions(-)
```

No behavioral change to the happy path. Defensive clears are no-ops when
state is already clean.

## Follow-ups (out of this patch's scope)

1. **PVM/QMDB performance for actor txs.** Per-handler speculative cost
   is dominated by:
   - QMDB merkleize of the *previous* block's actor-code writes (first
     call after a deploy) — ~1.4s for the bench's lending actor.
   - CIP-29 sync-fire = serial actor invocations inside one emit tx —
     scales linearly with N subscribers.

   Two cheap wins worth considering:
   - Move QMDB merkleize off the speculative critical path (run in
     parallel with handler execution or defer until commit).
   - Pre-warm a per-actor compiled-code cache so the first call after
     deploy doesn't pay the compile + write cost in the same tx.

2. **Bench retry on cancellation.** With the propose-race fixed, bench
   timeouts now mean "this individual tx took too long for the chain to
   finalize within 60s," which is recoverable. `node/bench/src/cowboy/workloads/utils.ts::executeActorAndWait`
   could poll past 60s if the user's nonce is still advancing in the
   account (proof of forward progress), instead of giving up.

3. **Two-phase mempool API (peek/take_specific).** The Drop-guard is
   correct but spawns a detached task. A peek-then-commit API would
   avoid the spawn and make the cancellation handling synchronous,
   which is easier to reason about under load. Larger refactor; defer.

4. **Consensus propose timeout — explicit signal vs implicit cancel.**
   Right now the framework expresses "your propose took too long" by
   dropping the future. An explicit signal (Result<Option<Block>, Aborted>)
   would let the chain react with intent instead of relying on Drop
   semantics. This is a commonware-consensus change, not chain.

## References

- Commit on this branch implementing the two-layer fix.
- `/home/ubuntu/workspace/node/test/validator.log` (the trace lines
  quoted in "Root cause" above; thread IDs and timestamps from a real
  reproduction).
- `node/bench/run_bench.sh` — `--profile smoke` reproduces the issue
  (pre-patch: register_position timeouts; post-patch: setup txs land,
  events phase reaches check_liquidation).
- Related: `refs/cips/cip-29-on-chain-event-hooks-en.md` (the protocol
  that triggered this surface).
