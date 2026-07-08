# COW-137 — Storage batch-read optimization: design + CIP draft (2026-06-22)

**Issue:** COW-137 "[PvmHost] Add storage batch read optimization — batch pre-fetch potentially needed storage keys."

**Status:** design. Verified against `origin/devnet`. **Bottom line: the only consensus-safe form is a new `state_get_many` syscall (Design A); speculative prefetch (Design B) is rejected; and the ROI is modest given QMDB's characteristics — recommend profiling before committing to the flag-day.**

---

## 1. Current single-key read path (verified)

`CowboyHost::state_get(&self, key)` (`execution/src/pvm_host.rs:1904`):
1. `read_count.fetch_add(1)` (atomic; `&self` host method).
2. Resolve: in-tx writeset → `sync_called_storage_copies` → `block_on_store_future(store.get_actor_storage(actor, key))` (a single synchronous DB read).
3. `read_bytes.fetch_add(value.len())`.

After the handler returns, `pvm_executor::execute_handler` batch-charges `read_count × STORAGE_READ_CYCLES` (100 cyc/read, `execution/src/gas.rs`) + `read_bytes` cells.

**Consensus boundary:** the **charged read count** feeds `STORAGE_READ_CYCLES`, which is consensus-enforced gas (unlike the Phase-2a observe-only per-instruction counter). So any change to *how many reads are charged* is a consensus change.

The `StateStore` trait (`storage/src/traits.rs:133`) and QMDB (`storage/src/db.rs`) expose only single-key `get_actor_storage` — **there is no native multi-get**; a "batch" still resolves to N single QMDB gets.

## 2. Why this is not a drop-in optimization

The host receives keys **one at a time** from the PVM (`state_get(k1)`, then `state_get(k2)`, …) — it cannot coalesce them without the actor expressing batch intent or the host guessing future reads. The two ways to get batch intent:

### Design A — `state_get_many` syscall (consensus-safe)
A new `HostApi` method + a new PVM syscall/opcode + an SDK helper (`self.storage.get_many([k1, k2, …])`).
- **Gas:** charge exactly `N × STORAGE_READ_CYCLES` + `Σ value_bytes` cells — identical to N single `state_get`s. `read_count += N`. This keeps the *charged* accounting unchanged → **consensus-neutral in gas**, but the new opcode is itself a consensus addition (flag-day; a v-bumped node must understand it).
- **Benefit:** fewer PVM↔host FFI boundary crossings and one batched resolution loop; lets the actor declare "I need these N keys."
- **Determinism:** results MUST be returned in the request order; the resolution loop is the same writeset→copies→DB order per key, so it is deterministic.

### Design B — speculative prefetch (rejected)
Host heuristically prefetches "potentially needed" keys. Rejected: (1) the host cannot know which keys an actor will read; (2) prefetched-but-unused reads raise the read-accounting question (charge them? then gas changes; don't? then the prefetch is unmetered work) — either way a **consensus risk**. Not pursued.

## 3. The ROI caveat (the decisive finding)

QMDB has **no native multi-get** and its reads are **synchronous and fast** (authenticated in-memory-backed KV, not a remote/disk round-trip per key). So `state_get_many`'s benefit is limited to:
- Fewer PVM↔host FFI crossings (one syscall vs N).
- One batched gas-charge / resolution loop.

It does **not** reduce the number of QMDB gets, and there is no I/O-overlap win (reads aren't I/O-bound). Against that modest benefit, the cost is high: a new consensus opcode + SDK surface + a CIP + a flag-day rollout + actor-code changes to adopt it.

**Recommendation:** do **not** implement speculatively. First profile a read-heavy actor to measure the actual `state_get` FFI/dispatch overhead. If it is a measured bottleneck, implement Design A via the CIP below. Otherwise defer — the optimization is unlikely to pay for its flag-day.

## 4. CIP draft — `state_get_many` syscall (only if profiling justifies it)

**Summary.** Add a batched storage read syscall to the PVM host API and the SDK, charged identically to N single reads.

- **HostApi** (`pvm/crates/pvm-host/src/lib.rs:297`): add
  `fn state_get_many(&self, keys: &[&[u8]]) -> HostResult<Vec<Option<Bytes>>>;`
  Default impl loops `state_get` (so existing impls/tests keep working); `CowboyHost` overrides it to do one resolution pass with a single `read_count += keys.len()` and accumulate `read_bytes`.
- **Opcode / syscall:** a new PVM syscall number (consensus). An un-upgraded node must reject code that uses it — gate via the block/tx version lever already in place (COW-123 #810 / COW-177).
- **Gas (normative):** `cycles += keys.len() × STORAGE_READ_CYCLES`; `cells += Σ len(value_i)`. Exactly equal to issuing the keys one at a time — **no gas advantage**, only fewer crossings.
- **Determinism:** return values in `keys` order; duplicate keys resolve independently (each charged). Empty `keys` → empty result, `read_count += 0`.
- **Bound:** cap `keys.len()` (e.g. ≤ 256) to keep a single syscall's cost bounded; over-cap → `InvalidInput`.
- **SDK:** `self.storage.get_many([...]) -> [Option<bytes>]` (`cowboy_sdk`), CBOR-decoding each like the single-key proxy.

**Storage layer:** optionally add `StateStore::get_actor_storage_many(actor, keys)` that loops `get_actor_storage` (no QMDB change) — purely to keep the host code tidy; it provides no DB-level speedup.

## 5. Test / rollout plan

- **Gas-equivalence test** (the consensus-critical one): `state_get_many([k1,k2,k3])` charges the same total cycles/cells as three `state_get`s — assert via the gas meter.
- **Determinism:** two runs return byte-identical ordered results; duplicate-key + absent-key cases.
- **Version gating:** code using the new opcode is rejected by a node that doesn't understand the version (flag-day lever).
- **Rollout:** consensus flag-day (new opcode) — rides the COW-2265 consensus-delta bundle for mainnet; devnet resets.

## 6. Recommendation

Keep COW-137 **Todo**. The honest engineering call: this is a **measure-first** optimization. The consensus-safe design is `state_get_many` (Design A), specified above, but its benefit is FFI-crossing reduction only (QMDB has no multi-get, reads aren't I/O-bound), so it should not incur a flag-day until profiling shows `state_get` dispatch is a real bottleneck for a read-heavy workload. Design B (prefetch) is rejected as consensus-unsafe.
