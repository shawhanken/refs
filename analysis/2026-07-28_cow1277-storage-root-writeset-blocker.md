# COW-1277 — `state_set`/`state_delete` storage-root maintenance: design + blocker

**Date:** 2026-07-28
**Spec:** CIP-30 §3.3 (storage syscall semantics), §3.2 (trie scheme), §5.2 (address-independence), §7/§8 (GC, security)
**Depends on / relates to:** COW-1276 (root computation — delivered, node #1167), COW-1284 (conformance — delivered, #1167), COW-1283 (migration policy), CIP-3 §3.3 (gas), COW-1275 (`Actor.storage_root` field + codec v7, merged)

## 1. Scope

COW-1277 asks that every state-write host syscall (`state_set`, `state_delete`, and wrappers) update the calling actor's storage trie and recompute `Actor.storage_root` in the cross-call write-set, committing on tx-commit and rolling back on revert via the existing snapshot machinery. Acceptance: a write inside a call that later reverts leaves `storage_root` unchanged; committed writes change it deterministically.

The pure root computation this depends on now exists: `cowboy_types::storage_root::compute_storage_root` (COW-1276, #1167), conformance-pinned to the §3.7 vectors.

## 2. Why the obvious "recompute from the physical image" approach is wrong

The tempting dormant implementation is: at commit, for each written actor, read its full `(key, value)` set from the store and call `compute_storage_root`. Gate it at `STORAGE_ROOT_ACTIVATION_HEIGHT = u64::MAX` so it is byte-identical below activation (exactly the MRU pattern). **This does not work, and would be a latent fork-on-activation bug**, for one concrete reason:

**The physical store discards long-key preimages.** `StateKey::actor_storage_slot_for_key` (`node/storage/src/state_key.rs:196`) stores keys ≤ 32 B verbatim, but keys > 32 B as `keccak256(key)[..32] || 0xFF` — the preimage is gone (`ActorStorageRawEntry.user_key: Option<Vec<u8>>` is `None` for hashed rows; `copy_actor_storage` can return the value but not the user key). CIP-30 §3.2 requires the preimage twice over:

- `path(key) = BLAKE3(key)` — needs the preimage to locate the leaf.
- `leaf(key, value) = BLAKE3(0x00 || u64_be(len(key)) || key || value)` — commits to the preimage **and** its exact length.

So for any actor that has *ever* stored a key longer than 32 bytes, its correct CIP-30 root **cannot be reconstructed from the physical store image**. A from-scratch recompute would either skip those rows (wrong root) or hash the truncated slot (wrong root). Since the root folds into `state_root`, a wrong root is a chain fork the moment the scheme activates. Landing this dormant would bury a fork trigger behind a height flip that a future engineer would trust.

This is not a surprise to the spec — §2.2(a) notes the copy "reaches hashed long keys (>32 bytes)", §3.2 says the leaf commits to the preimage precisely so "an implementation that stores `(key, value)` in the leaf record can enumerate every entry (including keys longer than 32 bytes)", and §8 requires an online migration to "traverse every key, including hashed long keys" with "a complete keyspace iterator at migration time". The current store satisfies none of that.

## 3. The correct design (and what it entails)

The root must be maintained **incrementally, at write time**, when `state_set(key, value)` still has the preimage as a syscall argument (`pvm_host.rs:2448`). That means a **persistent (immutable-node) per-actor SMT**:

- Each `state_set`/`state_delete` walks the actor's trie along `BLAKE3(key)`, writes new nodes, and stages the new root on `self.ctx.actor.storage_root`. The staged root rides the existing write-set: `sync_called_actors` already carries the full callee `Actor` (`pvm_host.rs:2213`), and `rollback` (`pvm_host.rs:1303`) already discards it — so commit/rollback semantics come for free, satisfying the COW-1277 acceptance criteria without new snapshot plumbing. The primary actor's root is staged before its `set_actor` at `pvm_host.rs:1207`.
- Nodes live in a content-addressed node store (keyed by node hash), giving the structural sharing that makes `child.storage_root = parent.storage_root` an O(1) `fork()` (§3.4) and copy-on-write divergence.

This is the representation §3.2/§5.2 describe — and it drags in exactly the two ratifications the spec gates activation on:

1. **§7 node garbage-collection (unsettled).** Immutable nodes are never overwritten, so churny writes leave permanent orphans. §8 is explicit: an adversary can inflate persistent state cheaply unless a reclamation strategy (refcounting / versioned pruning / archival compaction) is in place *before* activation, with a cost model consistent with the gas below. The node-store representation cannot be finalized before this is chosen, because the choice constrains the node layout.
2. **CIP-3 §3.3 gas formula (unratified).** Each write touches up to depth-256 nodes; the per-update cost must be deterministic and bounded before the scheme is consensus-live on any network with untrusted callers. The gas formula also shapes the write path (what is counted, when), so wiring it first means re-touching the hot path when the formula lands.

3. **§4 / COW-1283 migration policy.** Devnet can take the §4.1 coordinated wipe (re-genesis with the scheme active from genesis — no in-place migration, no preimage-recovery problem because every actor is built with real roots from the start). A network that cannot wipe needs §4.2 online migration, which requires the complete-keyspace iterator + preimage retention of §8. This is a governance decision (COW-1283), not an engineering one.

## 4. Recommendation

- **Do not land a dormant from-scratch recompute.** It is known-incorrect for long keys and would encode a fork trigger behind an activation flip.
- **Sequence COW-1277 behind:** (a) COW-1283 migration decision (wipe vs online), (b) CIP-3 §3.3 gas ratification, (c) §7 node-GC strategy. On a wipe-devnet decision, the incremental persistent-node SMT can be built and activated from genesis, sidestepping preimage recovery entirely.
- **Delivered now (COW-1276/1284, #1167):** the conformance-pinned root computation, which is the reference every future validator cross-tests against and the primitive the incremental SMT will reuse for its golden vectors.

## 5. Anchors (node, at time of writing)

- Root computation: `types/src/storage_root.rs` (COW-1276), `EMPTY_STORAGE_ROOT` + recursion guard `types/src/constants.rs:956,1266`.
- Long-key preimage loss: `storage/src/state_key.rs:196-207`; `storage/src/traits.rs:16-21` (`ActorStorageRawEntry.user_key: Option`).
- Write path: `execution/src/pvm_host.rs` — `state_set` 2448, `state_delete` 2675, `ActorStorageCache` 63, write-set staging `commit_cross_call_result` 2199, commit 1146 (`set_actor` 1207/1236), rollback 1303.
- Full-image enumeration (values, not long keys): `storage/src/accounts.rs:735` `copy_actor_storage`.
- Activation-gate template: `MRU_ACTIVATION_HEIGHT` `types/src/constants.rs:842`, `mru_reads_active` `execution/src/runner/dispatcher.rs:4412`; `block_height` is available at the write path as `self.ctx.block_height` (`pvm_host.rs:840`).
