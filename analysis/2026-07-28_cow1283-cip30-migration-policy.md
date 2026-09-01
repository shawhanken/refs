# COW-1283 — CIP-30 migration policy: wipe (devnet/testnet) vs online (mainnet)

**Date:** 2026-07-28
**Spec:** CIP-30 §4 (migration), §7 (open question: migration policy), §8.2 (migration correctness)
**Relates to:** COW-1275 (codec v7, merged), COW-1276/1284 (root computation + conformance, node #1167), COW-1277 (write-set root maintenance — blocked, see companion note)
**Nature:** governance decision — this note **scopes and recommends**; ratification of the §7 normative answer is governance's.

## 1. The choice (CIP-30 §4)

CIP-30 changes the on-chain layout of `Actor` (new `storage_root` field) and of actor storage (per-actor subtrees). §4 offers two migration paths and requires an implementation to pick one and document it:

- **Decision A — coordinated wipe (§4.1):** bump the actor codec version (reject old blobs at load), reset the chain, re-bootstrap. The spec calls this "the simplest path on a network with no installed user base… acceptable for devnets and testnets, and Cowboy's general convention for codec changes today."
- **Decision B — online migration (§4.2):** at the upgrade height, build each actor's trie from its current flat KV, write the root to `Actor.storage_root`, and route subsequent reads/writes through the new subtree. Amortizable over a window, but MUST be deterministic and (per §8.2) MUST traverse every key including hashed long keys.

## 2. Recommendation

**Decision A (coordinated wipe) for devnet and every testnet; defer the Decision B normative answer to mainnet.**

Rationale:
- Cowboy is pre-mainnet with no installed user base to preserve; §4.1 is explicitly the intended path for exactly this posture, and codec-version-bump-then-wipe is already the standing convention.
- Decision A is **already implemented** (see §3) — no further code is required for devnet.
- Decision B carries a hard prerequisite the current node does not satisfy (long-key preimage retention, §4 below); building it now, before it is needed, would be speculative work against an unratified gas formula (CIP-3 §3.3) and an unsettled node-GC strategy (§7).

This is consistent with COW-1277's sequencing (companion note): on a wipe-devnet decision, the per-actor SMT can be built and activated **from genesis**, so every actor carries a real root from block 0 and there is no in-place migration and no preimage-recovery problem at all.

## 3. Decision A is already shipped

The wipe path requires exactly one enforcement point — reject pre-CIP-30 actor blobs at load so a chain carrying them cannot start, forcing a clean re-genesis. That is in place:

- `node/types/src/execution.rs:890` — `Actor::read` rejects any `version != ACTOR_CODEC_VERSION` (=7, COW-1275) with `"unsupported codec version — pre-CIP-30 actor blob (storage_root cutover); state migration required"`. There is no defaulting decoder: a pre-v7 blob is a hard load error, not a silently up-converted record (which would corrupt `state_root`, since a non-empty actor's real root is not `EMPTY_STORAGE_ROOT`).
- Genesis seeds every fresh `Actor` with `storage_root: EMPTY_STORAGE_ROOT` (`execution.rs` genesis paths), so a re-bootstrapped devnet is v7-clean from block 0.

**Operative devnet procedure:** cut the release with the codec-v7 node, wipe state, re-genesis. No data-preserving migration step; the codec guard is the whole mechanism. This satisfies COW-1283's acceptance ("devnet upgrade succeeds with the chosen path").

> Note: codec v7 shipped with COW-1275, so devnet **already** rejects pre-v7 blobs today. The remaining CIP-30 activation work (real root computation in the write path, COW-1277) is separately gated on gas/GC and is dormant regardless of migration policy — the wipe decision does not itself turn the scheme on.

## 4. What Decision B requires, for when mainnet needs it

Recorded so the mainnet answer is not written from scratch. An online migration (§4.2) that builds roots from the flat KV MUST (per §8.2) traverse **every** key, including hashed long keys — and here the current store has a gap:

- Keys > 32 bytes are stored hashed (`node/storage/src/state_key.rs:196` → `keccak256(key)[..32] || 0xFF`) with the **preimage discarded** (`ActorStorageRawEntry.user_key: None`). CIP-30 §3.2's `leaf`/`path` need the preimage, so the correct root cannot be built from the stored image for any actor that ever wrote a long key.

Therefore Decision B is not just "iterate the KV at height H"; it requires **retaining long-key preimages** (either store keys verbatim, or persist a preimage side-table, or maintain the SMT incrementally from the CIP-30 activation height forward so migration only covers pre-activation verbatim rows). The state DB must also expose a complete-keyspace iterator at migration time (§8.2) even though runtime enumeration deliberately does not. These are the same constraints that block COW-1277's from-scratch approach (companion note) — Decision B and the COW-1277 write path share the persistent-node representation and its §7 GC.

## 5. Ask of governance

Ratify §7's migration-policy open question as: **Decision A (coordinated wipe) for devnet/testnet (already implemented); Decision B (online migration) normative answer deferred to the mainnet track, with the §4-above preimage-retention + complete-keyspace-iterator requirements as its acceptance preconditions.** No code change is requested for devnet; this note documents the shipped path and the deferred one.
