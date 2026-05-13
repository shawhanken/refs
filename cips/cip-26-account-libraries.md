---
title: "CIP-26: Account-Scoped Actor Libraries"
description: Per-account Python module publishing and import resolution. Actors deployed by an account may import that account's published libraries; the runtime silently pins each import to the library's code-hash at deploy time, so an immutable actor sees an immutable lib.
icon: package
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-05-04
  **Requires:** CIP-3 (Fee Model), CIP-6 (SDK), Atomic-init rollback (COW-870)
</Note>

## 1. Abstract

This proposal introduces **account-scoped actor libraries**: a per-account namespace of Python modules that the account's actors may `import` from. A library is published once (`cowboy lib publish`) and stored on chain under the publisher's account. When an actor is deployed, the runtime resolves the actor's import statements against the **deployer's** library namespace, silently pins each resolved name to the library's content hash, and records the pin set in the actor's metadata. At handler execution the PVM allowlist is extended with the pinned modules; lookup goes by hash, not by name, so the actor always sees the exact bytes that existed at deploy time even if the account later replaces the library.

Libraries are **strictly account-scoped**. An actor deployed by account `A` cannot import a library published by account `B`. This is intentional: actors are immutable and consequential, and the cost of accidentally pulling in unverified third-party code is severe. If a library should be reusable across accounts, the consumer publishes their own copy (or pins the upstream hash via the same publish flow against their own account).

## 2. Motivation

Today the PVM allowlist (`pvm-runtime/src/guard.rs::_is_allowed`) admits only the stdlib whitelist (`determinism.rs::default_whitelist`) plus `cowboy_sdk`. Any other import is rejected as `NonDeterministicError: module not allowed: <name>`. Multi-actor systems that share rules end up with one of two unsatisfying patterns:

1. **Inline-and-duplicate.** Copy the shared code into every actor file. The Texas Hold'em example notes this directly: *"hand evaluation inlined — PVM cannot import external modules"*. Drift, duplication, no single source of truth.
2. **Build-time bundling.** A relayer or Makefile concatenates the shared module into each actor before deploy. Works (some examples do this), but the deployed actor's code stops resembling its source, hash-pinning is per-deployer rather than per-library, and audit/review tooling has to reverse the bundle.

Neither pattern survives growth past a handful of small actors. Account-scoped libraries make the obvious thing work: write one `engine.py`, publish it once, import it from N actors.

### 2.1 Why account-scoped (not global)

A global library registry — anyone publishes, anyone imports, content-addressed — looks tempting. We reject it for two reasons:

1. **Trust.** An actor that imports `crypto_helpers` from a global namespace is one TOCTOU window away from importing whatever a stranger published under that name first. Hash-pinning at the deploy site mitigates this for the deploy itself, but the *human* writing the actor source is now responsible for verifying every dependency hash, which is a security review burden with very poor ergonomics. Account scoping makes "did I write or audit this code?" trivially answerable.
2. **Operational sovereignty.** With account scoping, each account controls its own dependency surface. With a global registry, a third party publishing buggy or malicious code under a popular name affects every consumer simultaneously.

Hash pinning at deploy time (§3.4) addresses the second-order risk that an account's own libraries change after the actor was deployed — the runtime always serves the bytes that existed at deploy time, regardless of subsequent `cowboy lib publish` calls.

### 2.2 Why immutability of actors makes this simple

Cowboy actors are immutable: no `upgrade_self` outside the `sys.upgrade` entitlement (very rare and gated), no in-place code rewrite. Combined with the COW-870 atomic-init rollback fix, this means an actor that ever runs handlers with library `L@hash_x` will always run with `L@hash_x`. There is no migration story for "the lib changed under me" because the actor's pin set is part of its immutable metadata.

If actor code were mutable, the design would have to deal with version negotiation, dual-pin-set transitions, lib-side compat guarantees, and a much larger spec surface.

---

## 3. Specification

### 3.1 Library data structure

```rust
struct ActorLibrary {
    publisher: Address,    // account that owns this library entry
    name: String,          // import name; max 64 bytes; must match Python identifier rules
    code_hash: Digest,     // keccak256 of code bytes; canonical id
    code_size: u64,        // bytes of `code` (cached for gas accounting)
    published_at: u64,     // block height of the publish
}
```

Library code blobs themselves live in the existing `StatePrefix::Code` table (CIP-9 Model A.4) — the same content-addressed, idempotent, garbage-free storage used for actor code. A library entry stores only the metadata + hash; the bytes are shared with any other actor or library that happens to have the same hash.

### 3.2 Storage layout

Two new state prefixes:

| Prefix | Key | Value |
|--------|-----|-------|
| `StatePrefix::Library` | `(publisher: Address, name: String)` | `ActorLibrary` |
| `StatePrefix::ActorLibPin` | `(actor: Address, name: String)` | `Digest` (the pinned `code_hash`) |

The `ActorLibPin` table is the actor's deploy-time-frozen view of its dependencies. Lookup at handler execution is `(self.address, import_name) → code_hash → code_bytes`. The library publisher's `Library` table can change freely (re-publish replaces); the actor's `ActorLibPin` table is write-once at deploy, read-only thereafter.

### 3.3 Publishing

A new instruction:

```rust
enum LibraryInstruction {
    PublishLibrary {
        name: String,
        code: Vec<u8>,
    },
}
```

Semantics:

1. Validate `name` matches the Python identifier regex `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$`.
2. Run `validate_actor_code(code)` (CIP-3 §2.4) — same determinism gate as actor code; bans `os.system`, `pickle`, `import time` at module top, large integer literals, etc.
3. Compute `code_hash = keccak256(code)`.
4. `set_code(code_hash, code)` — idempotent; shared blob storage.
5. Write `Library { publisher: sender, name, code_hash, code_size, published_at: block_height }` to `(sender, name)`. Replaces any prior entry under the same `(sender, name)`.

Gas: `lib_publish_base_cycles + per_byte_cycles * len(code)` — modeled on actor deploy. Cells: `len(code) * cells_per_byte_lib` if the code blob is new (cache miss), zero if the blob already existed (the `set_code` path is idempotent and free for repeats).

CLI:

```sh
cowboy lib publish --name engine --code ./engine.py
# → "Library published: name=engine code_hash=0xabcd... size=4321"
```

A `LibraryPublished` event is emitted: `{ publisher, name, code_hash, code_size }`.

### 3.4 Resolution and pinning at actor deploy

When `ActorInstruction::DeployActor` runs:

1. Existing flow validates the actor code, reserves the address, etc.
2. **New step**: scan the actor's source AST for top-level `import X` and `from X import ...` statements where `X` is not in the SDK / stdlib whitelist. Call this set the **candidate import set**.
3. For each name `X` in the candidate import set:
   - Look up `Library` at `(sender, X)`.
   - If absent → `Err(ExecutionError::UnresolvedImport { name: X })`. Deploy fails atomically (atomic-init rollback already covers the actor record per COW-870; the same rollback path applies here before any storage is committed).
   - If present → record `(actor_address, X) → library.code_hash` in the actor's pin set.
4. Persist the pin set as a sequence of writes to `ActorLibPin` in the same atomic deploy.
5. The pin set's total size is added to the actor's deploy gas cost (`cells_per_pin = 32` bytes for the hash + key overhead).

Once pinned, the actor's import map is immutable for the actor's lifetime.

The candidate import set is computed **statically from the source AST** (already parsed during `validate_actor_code`). Imports gated by runtime conditions (`if condition: import lazy_thing`) are not supported — the spec mandates the full set be discoverable from the AST. This is a deliberate restriction: dynamic imports defeat the audit story and complicate gas accounting.

Conditional imports inside SDK helpers (`from cowboy_sdk import ...`) are exempt from this restriction since they resolve to the trusted SDK.

### 3.5 Resolution at handler execution

When an actor handler runs, the PVM's import guard (`pvm-runtime/src/guard.rs`) is extended:

1. Before handler entry, the runtime reads the actor's pin set from `ActorLibPin` and pre-resolves each `code_hash → code_bytes` from the shared `Code` table.
2. For each pinned `(name, code_hash, code_bytes)`, the runtime executes `code_bytes` in a fresh module object, installs it as `sys.modules[name]`, and adds `name` to the import allowlist for this PVM context.
3. The handler runs. Any `import name` resolves to the pre-loaded module.
4. After the handler returns (success or failure), the per-context allowlist additions are discarded; the global allowlist stays untouched.

This mirrors how `cowboy_sdk` is already injected.

### 3.6 Gas

Three new metered points:

| Operation | Cycles | Cells |
|-----------|--------|-------|
| `PublishLibrary` | `100_000 + len(code) * 50` | `len(code)` if new blob, else 0 |
| Per-pin overhead at deploy | `1000` | `~64` (key + 32-byte hash) |
| Per-handler-call lib load | `len(code) * 5` | 0 |

The per-handler load cost is real — the lib's bytecode has to be re-executed to materialize the module each handler invocation, since the PVM does not retain Python state across calls. Caching the compiled bytecode form across calls (a follow-up optimization) would amortize this; out of scope for this CIP.

Aggressive limit: `MAX_LIBS_PER_ACTOR = 8`. Higher caps invite footguns around actor instantiation cost; eight is plenty for the patterns this CIP is designed for.

### 3.7 Replacing or removing a library

`cowboy lib publish --name X --code newer.py` overwrites the publisher's `(publisher, X)` entry with a new `code_hash`. **Existing actors that pinned the prior hash are unaffected** — their `ActorLibPin` entries continue to resolve the old `code_hash` from `StatePrefix::Code` (the old blob is reachable as long as any actor pins it; eligible for the same long-term GC story as any other code blob, currently never).

A separate `RemoveLibrary` instruction removes the metadata entry only — the underlying code blob persists for any actor still pinning it. Removal is purely a "stop offering this name to new deploys" operation.

### 3.8 Manifest interaction

Actors that import account libraries do not need to declare anything in their `ActorManifest`. The pin set is computed from source and recorded by the runtime. This keeps the manifest focused on entitlements (capabilities the actor wants from the host) rather than duplicating dependency information that the source already encodes.

Future revisions may add a manifest field listing expected pins for human review — purely informational, not enforced — but the canonical pin set always comes from the AST scan.

### 3.9 Determinism guarantees

A handler invocation against the same `(actor, block_state, payload)` always sees the same library code, because:

- The actor's `ActorLibPin` table is immutable post-deploy.
- The pinned `code_hash` resolves to a content-addressed blob in `StatePrefix::Code` that is written once and never mutated.
- Library code passes the same `validate_actor_code` checks as actor code, so it cannot introduce non-deterministic behavior the host would otherwise reject.

The only failure mode is if the underlying `Code` blob is somehow missing at handler time — currently impossible since `set_code` writes are durable and never deleted. If a future GC mechanism is introduced, the GC must check the union of `ActorLibPin.code_hash` (across all live actors) before reaping, the same way it would have to for actor code.

---

## 4. Worked example

Account `0xAlice` publishes a shared engine for her three game actors:

```sh
$ cowboy lib publish --name engine --code engine.py
Library published: publisher=0xAlice name=engine code_hash=0xabcd1234... size=4321
```

She deploys her three actors that import `engine`:

```python
# in world_actor.py:
from cowboy_sdk import actor, public, runtime
import engine

@actor
class World:
    def init(self, payload):
        runtime.emit_event("init", {"version": engine.VERSION})
```

```sh
$ cowboy actor deploy --code world_actor.py --salt $SALT \
    --init-handler init --init-payload '{}'
✓ Library imports resolved:
    engine → 0xabcd1234...
✓ Actor deployed: 0xWorld...
```

Later, Alice publishes `engine v2`:

```sh
$ cowboy lib publish --name engine --code engine_v2.py
Library published: code_hash=0xfeed5678... size=4520
```

The already-deployed `World` actor continues to resolve `engine → 0xabcd1234` (the v1 hash is in its pin set). Any *new* deploy from Alice resolves to v2.

Bob, working from account `0xBob`, tries to deploy an actor that imports `engine`:

```sh
$ cowboy actor deploy --code world_actor.py --salt $SALT --init-handler init
Error: deploy failed: UnresolvedImport { name: "engine" }
   no library named "engine" published under deployer account 0xBob
```

Bob has no `engine` library under his own account; Alice's is invisible to him. He must `cowboy lib publish --name engine --code <vetted_copy.py>` against his own account first.

---

## 5. Reference implementation

Code paths that change:

- `node/storage/src/state_key.rs` — add `StatePrefix::Library` and `StatePrefix::ActorLibPin`.
- `node/storage/src/traits.rs` — add `get_library`, `set_library`, `delete_library`, `get_actor_lib_pins`, `set_actor_lib_pin`.
- `node/storage/src/accounts.rs` — concrete impls of the above.
- `node/cowboy-types/src/instruction.rs` — `Instruction::Library(LibraryInstruction::{PublishLibrary, RemoveLibrary})`.
- `node/execution/src/execution/library_instruction.rs` — new file; instruction handler.
- `node/execution/src/execution/actor_instruction.rs::DeployActor` — add the AST scan + pin resolution step before atomic init.
- `node/pvm/crates/pvm-runtime/src/guard.rs` — extend `_is_allowed` and the `_pvm_import` hook to consult the per-context pin set.
- `node/pvm/crates/pvm-runtime/src/lib.rs` — pre-load pinned libraries into `sys.modules` before handler entry.
- `node/cli/src/commands.rs` — `cowboy lib publish | remove | list` subcommands.

Tests:

- Publish + import + handler call round-trip.
- Cross-account import is rejected.
- Pin survives library re-publish.
- Pin survives library removal (existing actors keep working; new deploys can't pick up the removed name).
- Atomic deploy rolls back on `UnresolvedImport` (extends the COW-870 regression test).
- Determinism: re-running the same handler at the same height with the same input returns identical state across nodes after a library re-publish.

---

## 6. Backwards compatibility

Pure addition. Existing actors don't have `ActorLibPin` rows; the import guard treats their pin set as empty, so behavior is unchanged. Existing deploys continue to be atomic with no extra cost.

---

## 7. Security considerations

### 7.1 Trust model

The trust boundary is the **deployer's account**. An actor implicitly trusts every library its deployer has published, because the deployer chose to deploy the actor knowing those libraries exist and what they contain. Cross-account imports are forbidden precisely so this boundary is unambiguous.

A compromised deployer key can publish malicious library updates, but those updates only affect *future* deploys from that account — already-deployed actors' pins are immutable. This bounds blast radius: an attacker who compromises Alice's key cannot retroactively poison her existing actors, only the next ones she (or the attacker) deploys.

### 7.2 Determinism attacks

The library code path goes through the same `validate_actor_code` checks as actor code, so it cannot reach `os.system`, `time.time()`, hardware FPU, or other non-deterministic primitives. Library authors can no more break consensus than actor authors can.

### 7.3 Storage exhaustion

Library blobs live in the same `StatePrefix::Code` table as actor code, which today never garbage-collects. The marginal cost of accepting a 1 MiB library blob is the same as accepting a 1 MiB actor blob. Gas pricing in §3.6 is set to make publishing realistic-sized libraries cheap and oversize libraries painful.

`MAX_LIBS_PER_ACTOR = 8` caps the per-handler load cost to a known maximum and prevents a deploy-time DoS against the import resolver.

### 7.4 Pin-set tampering

`ActorLibPin` is written exclusively by the chain runtime during `DeployActor`, and exclusively read during handler dispatch. There is no SDK API to mutate pins, and the storage prefix is excluded from `runtime.set_state` / `self.storage[]` (mirroring the existing `__OWNER__` / `__INITIALIZED__` reserved-key protections in CIP-6).

---

## 8. Out of scope

- **Cross-account imports.** Forbidden by design (§2.1). Not a future addition.
- **Bytecode caching across handler invocations.** Performance optimization; doesn't change semantics. Worth doing eventually since the per-call lib re-execution is real cost.
- **Lazy / conditional imports.** Disallowed by §3.4 because they break the AST-driven pin discovery. Could be revisited if a compelling use case emerges.
- **Library transitive dependencies.** A library that itself does `import other_lib` follows the same resolution path, but the `other_lib` must also be published under the same publisher account. Effectively this means library authors must publish their dependency closure under their own account — equivalent to vendoring. Spec'd separately if pain emerges.
- **Versioning / semver.** Not built in. Account holders can publish multiple distinct names (`engine_v1`, `engine_v2`) if they want explicit version pinning visible in actor source. The hash-pinning at deploy makes "what version did this actor pin?" trivially answerable from `ActorLibPin`.

---

## 9. Open questions

- Should `cowboy lib publish` accept a directory and bundle multiple files into a single library, or strictly single-file? Single-file is simpler and matches how almost all examples are structured today; multi-file can be added if anyone hits the friction.
- Should a library be allowed to import `cowboy_sdk`? Most utility libraries won't need it (pure rules), but some will (lib that emits events). Default: yes, allow `cowboy_sdk` imports from libraries on the same terms as actors. The handler-execution import map already covers it.
- `MAX_LIBS_PER_ACTOR = 8` is a guess. Empire's example would use 1; Texas Hold'em would use 1. If real usage demands more, raising the cap is a numeric change with no spec impact.
