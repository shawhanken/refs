# PR #412 Review — `cbd/actor-perms`: Consolidated Findings

**Branch:** `cbd/actor-perms`
**Reviewed:** 2026-04-29
**Scope:** SDK-level handler permissions (`@public` / `@callable_by`), runtime-managed owner slot, reserved-key guard, init bootstrap window.
**Commits in scope:**
- 48ac4cf — feat(sdk): add @public and @callable_by handler permission decorators
- 55f3521 — feat(sdk)!: deny-by-default permissions; runtime-managed owner
- 16b1d8c — refactor(sdk)!: __OWNER__ key + implicit init bootstrap exemption
- d8efcb0 — fix(sdk): address almanax security findings on PR #412

---

The deny-by-default permission model and the runtime-managed owner slot are a clear improvement over the underscore-prefix-as-privacy convention. The d8efcb0 follow-ups close most of the obvious holes flagged by the almanax scan, and all 615 SDK tests pass. Before merging, the following issues are worth addressing — two with a real attack surface, two documentation/semantics inconsistencies, and three minor cleanups.

## HIGH

### 1. `runtime._set_state_unchecked` is a publicly reachable escape hatch

**Location:** [`pvm/Lib/cowboy_sdk/runtime.py:260`](../../node/pvm/Lib/cowboy_sdk/runtime.py)

```python
def _set_state_unchecked(key, value):
    _host().set_state(key, value)
```

The leading underscore is a convention; Python does not enforce it as private. d8efcb0 closed the `runtime.set_state(reserved_key, …)` path, but the same owner-takeover primitive remains reachable in two ways:

- **Through the SDK escape hatch** — any handler that forwards caller-controlled input into `_set_state_unchecked(key, value)` will overwrite `__OWNER__` exactly as the patched `set_state` would have. The almanax `entitlements_actor.touch_storage` finding gets re-introduced the moment a developer reaches for the "unchecked" variant.
- **Through `pvm_host` directly** — `import pvm_host; pvm_host.set_state(b"__OWNER__", attacker)` skips the SDK entirely. `pvm_host_module` is in the determinism whitelist (see `pvm_executor.rs::stdlib_whitelist`), so any actor can import it.

The current guard is fool-proofing, not malice-proofing. To make the "external caller cannot land an attacker-controlled `__OWNER__`" claim actually hold, the reserved-key check has to live in the Rust host (`pvm_host.rs::set_state` / `delete_state`), not in the Python shim above it.

**Suggested fix:** add a `RESERVED_KEYS` rejection inside `CowboyHost::set_state` and `delete_state`, returning `HostError::InvalidInput`. Drop `_set_state_unchecked` and route the SDK's legitimate writers (`transfer_ownership`, `assume_ownership_if_unowned`, the init lock) through a dedicated host syscall the host can identify, not a key-prefix bypass.

### 2. Owner front-running for actors deployed without `init_handler`

**Location:** [`execution/src/execution/actor_instruction.rs:283`](../../node/execution/src/execution/actor_instruction.rs)

H6 atomic init takes `init_handler: Option<&str>`. When the deployer omits it, the actor goes live with `__INITIALIZED__` unset and no owner. The next transaction can call `init()` — the SDK's bootstrap window lets it through unconditionally — invoke `assume_ownership_if_unowned()`, and become permanent owner.

d8efcb0 finding #4 acknowledges this and resolves it as "documentation only". That was reasonable when the SDK had no owner concept; it is no longer reasonable now that this PR makes ownership the basis for `@callable_by(OWNER)`, `request_upgrade`, and the entitlements actor's upgrade path. The PR introduces a new attack surface, so it should also introduce a guardrail.

**Suggested fix:**

- Have `cowboy actor deploy` default to `--init-handler init` when an `init` symbol is present in the source.
- Reject deploys that lack an `init_handler` but whose code references owner-gated APIs (`@callable_by(OWNER)`, `runtime.assume_ownership_if_unowned`, `runtime.transfer_ownership`). A static scan in the CLI is enough — fail loudly at deploy time, not silently in production.
- Long-term, a `deployer` field on `Actor` (set by the host at deploy, immutable thereafter) would let `runtime.get_owner()` fall back to the deployer cryptographically and retire the bootstrap-on-first-call ceremony. 55f3521 already flags this as the proper resolution; the chain-format change can land in a follow-up.

## MEDIUM

### 3. The "intra-actor bypass" docstring in `permissions.py` is misleading

**Location:** [`pvm/Lib/cowboy_sdk/permissions.py:15`](../../node/pvm/Lib/cowboy_sdk/permissions.py)

> "Intra-actor calls (caller == self.address) are ALWAYS allowed regardless of the handler's declaration. This mirrors EVM's `this.method()` semantics and keeps helper-method composition working without ceremony."

The bypass condition in `_check_call_permission` is `runtime.get_sender() == self.address`. For ordinary Python `self.helper(p)` calls inside a handler, `get_sender()` returns the **outermost caller** (the EOA or the upstream actor) — not `self.address`. The bypass therefore does **not** fire for in-language method calls.

What actually keeps helper composition working is the unrelated underscore-prefix rule in [`actor.py:210`](../../node/pvm/Lib/cowboy_sdk/actor.py): `_helper`-style names are skipped by the wrap pass and never go through the permission check at all. This is a real silent breaking change — any actor that today has a non-underscore, non-decorated helper method (`def compute(self, p): …`) called from another handler will start raising `PermissionDeniedError` once it is invoked from a cross-actor context.

**Suggested fix:** rewrite the docstring to describe the actual mechanism — "underscore-prefixed methods are not wrapped; non-underscore handlers must declare `@public` or `@callable_by(...)`" — and add a short migration note in the PR description so downstream actors with non-underscore helpers know to rename them or add `@callable_by(SELF)` (and that `SELF` only protects against external callers, not against helpers reached from a cross-actor context).

### 4. `errors.py` guidance not updated to match the refactor

**Location:** [`pvm/Lib/cowboy_sdk/errors.py:225`](../../node/pvm/Lib/cowboy_sdk/errors.py)

`PermissionDeniedError.fix` still reads:

> "set the actor's owner via class-level OWNER or storage['owner']"

This is exactly the path 55f3521 removed. A developer hitting this error will be sent down a dead end — `self.OWNER_ADDR` and `self.storage["owner"]` no longer participate in owner resolution.

**Suggested fix:** replace the message with the runtime-managed path:

> "Mark the handler `@public` to expose it to all callers, or extend `@callable_by(...)` to include the caller's address. For owner-restricted handlers, set the actor's owner via `runtime.transfer_ownership(new_owner)` or `runtime.assume_ownership_if_unowned()` (typically from `init`)."

## LOW

### 5. `mock_host.py` `reset()` has misaligned indentation

**Location:** [`pvm/Lib/cowboy_sdk/mock_host.py:49-53`](../../node/pvm/Lib/cowboy_sdk/mock_host.py)

```python
    _context = {
        'tx_hash': b'\xab' * 32,
        # Default sender is the actor's own address so handlers look like
    # intra-actor calls and bypass permission checks (deny-by-default in the
    # permissions layer)...
    'sender': b'\x22' * 20,
        'actor_addr': b'\x22' * 20,
```

Functionally fine (Python dict literals are whitespace-insensitive), but the comment block and the `'sender'` key sit at column 5 while the rest of the dict is at column 9. Introduced in 16b1d8c; trivial to fix.

### 6. Owner = zero address is silently treated as "set"

**Location:** [`pvm/Lib/cowboy_sdk/runtime.py:282`](../../node/pvm/Lib/cowboy_sdk/runtime.py)

`get_owner()` returns `b""` for "unset" and any 20-byte value for "set". `bool(b"\x00" * 20)` is `True`, so `transfer_ownership(b"\x00" * 20)` silently renounces ownership without raising — `assume_ownership_if_unowned()` will not fire afterwards (owner is "set"), and `@callable_by(OWNER)` becomes permanently unreachable.

This is sometimes intentional (renounce-ownership pattern), but the API gives no signal. Consider rejecting the zero address explicitly in `transfer_ownership`, or providing a separate `runtime.renounce_ownership()` so the intent is auditable on-chain.

### 7. `_dispatch_message`'s underscore defense rarely fires in production

**Location:** [`pvm/Lib/cowboy_sdk/actor.py:329`](../../node/pvm/Lib/cowboy_sdk/actor.py)

The Rust host calls module-level functions by name (`scope.globals.get_item_opt(entrypoint, …)` in `pvm-runtime/src/lib.rs`), not `actor._dispatch`. Most actors define explicit per-handler module-level wrappers (`def init(p): return _get().init(p)`) and never route through `_dispatch_message`, so the underscore-name rejection added in d8efcb0 is effectively only exercised by `ActorRef.call(...)` paths.

This is not a bug — the wrap-pass guard at [`actor.py:210`](../../node/pvm/Lib/cowboy_sdk/actor.py) is the actual defense, and `_dispatch_message`'s check is a legitimate defense-in-depth layer. But the d8efcb0 commit message reads as if it stacks two independent protections; in practice the second layer is dormant on the host call path. Worth clarifying in the commit message / SECURITY.md so future reviewers don't overestimate coverage.

---

## Summary

| # | Severity | What | Where to fix |
|---|----------|------|--------------|
| 1 | HIGH | Reserved-key guard bypassable via `_set_state_unchecked` and direct `pvm_host` | Move guard into Rust host |
| 2 | HIGH | Owner front-running when `init_handler` is omitted at deploy | CLI default + deploy-time static check; long-term `deployer` field on Actor |
| 3 | MEDIUM | "Intra-actor bypass" doc misrepresents how helper composition actually works | Rewrite docstring; flag the breaking change for non-underscore helpers |
| 4 | MEDIUM | `PermissionDeniedError.fix` references the removed owner API | Update the string in `errors.py` |
| 5 | LOW | `mock_host.py` `reset()` indentation | One-line cleanup |
| 6 | LOW | `transfer_ownership(0x00…)` silently renounces | Reject zero address or expose explicit `renounce_ownership()` |
| 7 | LOW | `_dispatch_message` defense rarely on the host call path | Clarify in commit / SECURITY.md |

#1 and #2 are blockers — they undermine guarantees the PR explicitly makes. #3 is also worth blocking on, because the docstring as-is will mislead downstream actor authors during migration. #4–#7 can land in the same fix commit.
