---
title: "CIP-6: In-PVM Actor SDK (cowboy_sdk)"
description: Normative specification of the cowboy_sdk Python package — actor lifecycle, handler permissions, runtime syscalls, ownership model, and CLI surface for Cowboy actor development
icon: code
---

<Note>
  **Status:** Draft<br/>
  **Type:** Standards Track<br/>
  **Category:** SDK<br/>
  **Created:** 2025-10-20<br/>
  **Revised:** 2026-05-19 (split SDK layers; add permissions §7, ownership §12.10, deployment-semantics fix §6.3, handler-signature clarification §2.3, compatibility matrix §2.4)<br/>
  **Requires:** CIP-1 (Actor Message Scheduler), CIP-2 (Off-Chain Compute), CIP-3 (Fee Model), CIP-5 (Timers)<br/>
</Note>

## 1. Abstract

This CIP specifies **`cowboy_sdk`**, the Python SDK embedded in the Cowboy PVM and imported by actor code executing on-chain. It is normative for the PVM's actor model, call primitives, handler permissions, continuation semantics, type system, verification builder, error hierarchy, ownership runtime, and the `cowboy` CLI surface.

There are two Python-facing layers for Cowboy development. **This CIP is normative for `cowboy_sdk` only.** The standalone installable package (`cowboy-sdk`, imported as `cowboy`) is described in §2 and is non-normative for this CIP.

Any Cowboy node that runs Python actors MUST expose the module layout and syscalls defined here. Any CLI that names itself `cowboy` SHOULD implement the subcommands in §16 with compatible flag semantics.

Key properties:

- **Deterministic by construction.** Non-deterministic Python primitives (wall-clock time, hardware FPU, unseeded randomness, filesystem, network, `set()`, `pickle`) are trapped or replaced by SDK equivalents.
- **Two-dimensional metering.** Every syscall is metered in Cycles (compute) or Cells (state IO) per CIP-3.
- **Handler-mode purity.** Every actor method declares whether it may issue async side effects (`@pure` vs `@deferred`); the runtime enforces this distinction.
- **Deny-by-default access control.** Handlers are unreachable from external callers unless explicitly decorated with `@public` or `@callable_by(...)`.
- **Continuations compiled at decoration time.** `async` methods decorated with `@runner.continuation` or `@actor.continuation` are lowered to a finite-state machine at class-load time, not dynamically at runtime.
- **Entitlements gate all external-effect syscalls.** Entitlements are declared in a deploy-time manifest and enforced at the Host API boundary.

---

## 2. SDK Layers

There are two Python-facing packages for Cowboy development. They are distinct and serve different purposes.

### 2.1 `cowboy_sdk` — In-PVM Actor SDK (this CIP)

| | |
|---|---|
| **Repo** | `node/pvm/Lib/cowboy_sdk/` |
| **Import** | `from cowboy_sdk import actor, runtime, ...` |
| **Where it runs** | Inside the PVM when actor code executes on-chain or in a local PVM sandbox |
| **Version** | 0.1.1, Python ≥ 3.11 |

Actor code that will run on-chain imports from `cowboy_sdk`. This is the package this CIP specifies.

### 2.2 `cowboy` — Standalone Developer SDK

| | |
|---|---|
| **Repo** | `python-sdk/` (PyPI: `cowboy-sdk`) |
| **Import** | `from cowboy import actor, CowboyClient, runtime, ...` |
| **Where it runs** | Off-chain, in developer environments and CI |
| **Version** | 0.1.0, Python ≥ 3.10 |

The standalone package provides:

- **Actor authoring helpers** — `@actor`, `@public`, `@callable_by`, `@pure`, `@deferred`, `@init_handler`, `OWNER`, `SELF`, local `runtime` stubs for unit testing
- **Source generation** — `actor_instance.to_source()` emits deployable Python source that imports from `cowboy_sdk`
- **Chain client** — `CowboyClient`, `AsyncCowboyClient` for RPC queries and transactions
- **Deployment** — `client.deploy_actor(code, salt, init_handler, ...)`, `client.execute_actor(...)`
- **Wallets and signing** — `Wallet`, `generate_private_key`, `sign_payload`
- **Jobs** — `JobSpec`, `client.submit_job()`
- **CBSS** — secrets management helpers

The `cowboy` local SDK mirrors enough of the `cowboy_sdk` actor authoring API to write and unit-test actors locally. It does not implement continuations, `ActorRef`, `runner`, `Verify`, `CowboyModel`, `SoftFloat`, `ordered_set`, `BlockHeight`, or storage raw/guard helpers. Actors that use those features must be tested against a live PVM sandbox.

### 2.3 Handler Signature Difference

The most important practical difference for actor authors:

| Layer | Handler signature | Payload |
|---|---|---|
| **`cowboy_sdk`** (PVM) | `def handler(self, msg)` — single positional arg | Whatever the host delivers; no mandatory pre-decode at the Python layer |
| **`cowboy`** (standalone) | `def handler(self, payload: bytes)` — enforced by `validate_for_deployment` | Raw CBOR bytes; author decodes (e.g. `cbor2.loads(payload)`) |

`to_source()` generates module-level wrappers with the `payload: bytes` signature. Actors deployed via `to_source()` therefore receive raw CBOR bytes on-chain; decoding is the author's responsibility. CBOR encode/decode is a wire-format concern for `call()`, `send()`, and storage — see §9 and §11.5.

### 2.4 Compatibility Matrix

| Feature | `cowboy_sdk` (PVM) | `cowboy` (standalone) |
|---|:---:|:---:|
| Import name | `cowboy_sdk` | `cowboy` |
| Execution environment | On-chain PVM | Local / CI |
| `@actor` decorator | ✓ | ✓ |
| `self.address` injection | ✓ | — |
| `self.storage` injection | ✓ | ✓ (in-memory) |
| `Storage.get_raw()` / `set_raw()` | ✓ | — |
| `Storage.guard()` / `GuardedValue` | ✓ | — |
| `@public` / `@callable_by` / `OWNER` / `SELF` | ✓ | ✓ |
| `@init_handler` | — | ✓ |
| Handler signature | `(self, msg)` | `(self, payload: bytes)` |
| `call()` / `send()` top-level | ✓ | — |
| `runtime.call_actor()` / `runtime.send_message()` | ✓ | ✓ (stubs) |
| `ActorRef` | ✓ | — |
| `runner` / `capture` / continuations | ✓ | — |
| `Verify` / `VerifyBuilder` | ✓ | — |
| `CowboyModel` / `SoftFloat` / `ordered_set` | ✓ | — |
| `runtime` ownership helpers | ✓ | ✓ (stubs) |
| `runtime.configure()` / `reset()` (test helpers) | — | ✓ |
| `routes` / `Pays` / `mount` (CIP-15) | ✓ | ✓ |
| `CowboyClient` / `Wallet` / `JobSpec` | — | ✓ |

---

## 3. Motivation

Python is the surface that actor authors touch most often. For the protocol to be interoperable across implementations and for actors to remain portable across node versions, the SDK contract must be stable and normatively specified — not left as implementation-defined.

A prior revision of this CIP was drafted before significant SDK consolidation landed (handler-mode purity, runtime module, error-code hierarchy, CREATE2 address derivation, entitlement manifest format, permissions system). This revision rebuilds against the shipping code and clarifies the two-package architecture so that the spec tracks implementation reality.

Subsequent revisions will extend the SDK for CIP-9 volume mounts (currently runner-side only) and CIP-7 / CIP-17 streaming helpers. Both are noted as gaps in §19.

---

## 4. Definitions

- **Actor**: A Python class whose public methods are invocable handlers. Identified by a 20-byte address.
- **Handler**: A public method of an Actor. Accepts the payload the host delivers; returns a CBOR-encodable value or raises.
- **Handler mode**: A per-method property, either `pure` (default) or `deferred`. Pure handlers MUST NOT issue async side effects.
- **Permission**: A per-method access control tag (`@public`, `@callable_by`, or absent). Absent means deny-by-default from external callers.
- **Syscall**: A call from the PVM into the Host API (implemented in Rust) to perform a privileged operation. The SDK wraps syscalls.
- **Continuation**: A compiled FSM representation of an `async def` handler that `await`s a runner job or an async actor call. State survives block boundaries.
- **Manifest**: A JSON document declaring the entitlements a deployed actor requests. Attached to the deploy transaction.
- **PVM**: The Python Virtual Machine executing actor bytecode under determinism constraints (CIP-3 §4).

---

## 5. SDK Module Layout

The canonical package is `cowboy_sdk`, shipped with the PVM at `node/pvm/Lib/cowboy_sdk/`. Version 0.1.1 targets Python ≥ 3.11.

**Required actor-facing API** — every symbol below MUST be importable from the `cowboy_sdk` package root. An implementation MUST NOT remove, rename, or change the semantics of any of these:

| Category | Exports |
|---|---|
| **Actor core** | `actor`, `ActorRef`, `derive_actor_address` |
| **Handler modes** | `pure`, `deferred` |
| **Permissions** | `public`, `callable_by`, `OWNER`, `SELF` |
| **Call primitives** | `call`, `send` |
| **Continuations** | `capture`, `Capture`, `bounded_loop` |
| **Security guards** | `reentrancy_guard`, `storage_guard`, `GuardedValue`, `GuardSet` |
| **Runner integration** | `runner` (module), `Retry`, `TaskGroup` |
| **Types** | `Address`, `BlockHeight`, `SoftFloat`, `ordered_set`, `CowboyModel` |
| **Verification** | `Verify` |
| **Runtime surface** | `runtime` (module) |
| **Errors** | See §15 |

**Currently exported helpers and extension surfaces** — present in the shipping implementation but not mandated by this CIP. An implementation MAY omit or rename these; actor authors SHOULD prefer the required API above:

| Category | Exports | Notes |
|---|---|---|
| **HTTP routes (CIP-15)** | `routes` (module), `Pays`, `mount` | Defined by CIP-15, not CIP-6 |
| **Continuation internals** | `save_cont`, `load_cont`, `delete_cont` | FSM plumbing; use `capture()` instead |
| **Guard helpers** | `BoundedRange`, `check_iteration` | Implementation conveniences for `bounded_loop` |
| **Verification builder** | `VerifyBuilder` | Returned by `Verify.builder()`; rarely imported directly |

Private submodules (`cowboy_sdk.codec`, `cowboy_sdk.pvm_sys`, `cowboy_sdk.pvm_time`, `cowboy_sdk.pvm_random`) are implementation details and SHOULD NOT be imported by actor code. They MAY be imported by SDK extensions that understand the PVM boundary.

---

## 6. Actor Model

### 6.1 Declaration

An Actor is a Python class decorated with `@actor`. The examples below use `cowboy_sdk` import style (on-chain). The standalone `cowboy` package uses the same decorator names but requires `(self, payload: bytes)` handler signatures — see §2.3.

```python
from cowboy_sdk import actor, public, callable_by, pure, deferred, OWNER, runtime

@actor
class Counter:
    def init(self, payload):
        runtime.assume_ownership_if_unowned()
        self.storage["count"] = 0

    @pure
    @public
    def get_count(self, payload) -> int:
        return self.storage.get("count", 0)

    @deferred
    @public
    def increment(self, payload) -> int:
        self.storage["count"] = (self.storage.get("count") or 0) + 1
        return self.storage["count"]

    @callable_by(OWNER)
    def reset(self, payload) -> None:
        self.storage["count"] = 0
```

The `@actor` decorator:

1. Injects `self.address` (read-only `Address`, the actor's own 20-byte address). **`cowboy_sdk` only** — the standalone `cowboy` SDK does not inject `self.address`.
2. Injects `self.storage` (a dict-like proxy over actor private state — see §6.5).
3. Wraps every public method in permission enforcement (deny-by-default; see §7) and handler-mode enforcement (see §8).
4. Scans for `@runner.continuation` and `@actor.continuation` methods and installs the corresponding `__resume` callbacks. **`cowboy_sdk` only.**
5. Registers the class as the handler entry point for the deployed actor.

The decorator form is canonical. Whether a bare class named `Actor` is accepted without the decorator depends on the PVM loader's module-scanning logic, which is non-normative at this layer; actor authors SHOULD always use `@actor`.

### 6.2 Address Derivation

Actor addresses are derived via Ethereum-style CREATE2:

```
address = keccak256(0xff || deployer_address || salt || code_hash)[12:]
```

- `deployer_address`: 20 bytes, the sender of the deploy transaction.
- `salt`: 32 bytes, caller-supplied (zero-padded if shorter).
- `code_hash`: 32-byte hash of the actor source. The CLI's `cowboy actor address` is authoritative for the exact hash algorithm used.
- Output: 20-byte `Address`.

`derive_actor_address(deployer, salt, code_hash)` computes this locally. The CLI helper `cowboy actor address` computes it without submitting a transaction (§16).

### 6.3 Deployment

**Wire fields (`DeployActor` transaction):**

| Field | Wire type | Notes |
|---|---|---|
| `code` | `bytes` | UTF-8 Python source |
| `salt` | `bytes` (≤ 32) | zero-padded to 32 bytes for CREATE2 |
| `init_handler` | `Option<string>` | handler to invoke atomically; absent = no init call |
| `init_payload` | `Option<bytes>` | payload passed to `init_handler`; absent = no payload |
| `manifest` | `Option<bytes>` | commonware-codec-encoded `ActorManifest`; CLI accepts `--manifest-json <file.json>` (JSON) and converts |

**CLI defaults (applied by `cowboy actor deploy` before building the transaction):**

| Flag | Default when omitted |
|---|---|
| `--init-handler` | `"init"` |
| `--init-payload` | `"{}"` (UTF-8 string) |

Atomic initialization:

- By default the CLI calls `"init"` atomically in the same transaction as the deploy, with `sender` set to the deployer's address.
- Pass `--no-init` to deploy without an init call (only safe for actors that do not rely on `init` for ownership bootstrapping).
- Pass `--init-handler <name>` to name a different handler.
- Pass `--init-payload <json-string | @file>` to supply a custom payload.

The entire `DeployActor` transaction reverts if `init_handler` raises.

The deployment receipt carries the derived actor address.

**Note on `__init__`:** Previous revisions of this CIP described deployment as invoking `__init__` with constructor args. This is incorrect. `__init__` may be used for local Python class initialization (without args), but the deploy-time initializer is always a handler named via `init_handler`, not the Python constructor.

### 6.4 Message Handler Dispatch

A message to an actor carries a `method_name` (UTF-8 string) and `payload` (raw bytes). Dispatch:

1. The PVM loads the actor class and state.
2. `method_name` is looked up; unknown methods raise `AttributeError` — converted to `ActorCallError`.
3. The handler runs under its declared permission (§7) and handler mode (§8).
4. Return value is CBOR-encoded and returned to the caller (for `call()`) or discarded (for `send()`).

Actors deployed via `to_source()` receive `payload` as raw CBOR bytes in each module-level wrapper. The author is responsible for decoding (e.g. `cbor2.loads(payload)`).

The reserved handler `on_timer(msg)` receives timer fires (CIP-5). Additional reserved handlers MAY be introduced by future CIPs.

### 6.5 Storage

Actor state is a private key-value store scoped to the actor's address. Access is exclusively through `self.storage`:

```python
self.storage[key] = value        # CBOR-encode value, write
value = self.storage[key]        # read, CBOR-decode; None if absent
del self.storage[key]            # delete
key in self.storage              # membership test
value = self.storage.get(key, default)
```

Raw-bytes escape hatches (**`cowboy_sdk` only**):

```python
self.storage.set_raw(key, data)  # data: bytes, stored verbatim
data = self.storage.get_raw(key) # returns bytes | None
```

Guard-based state snapshot for continuations (**`cowboy_sdk` only**):

```python
balance = self.storage.guard("balance")  # returns GuardedValue; see §10.3
```

Keys MUST be UTF-8 strings. Values of `self.storage[key]` MUST be CBOR-encodable per §11.5.

Storage writes and reads are metered in Cells per CIP-3. Cross-actor storage access is prohibited; actor B cannot read actor A's storage directly — it must call a method on A.

A small set of dunder-style keys (`__OWNER__`, `__INITIALIZED__`) is reserved by the SDK. All access methods raise `ValueError` for those keys; use the sanctioned runtime APIs instead (see §12.10).

---

## 7. Handler Permissions

Access control is **deny-by-default**: a non-underscore-prefixed handler with no permission decorator is unreachable from external callers. This applies in both `cowboy_sdk` and the standalone `cowboy` package.

### 7.1 Decorators

| Decorator | Who may call |
|---|---|
| `@public` | Any caller |
| `@callable_by(addr, ...)` | Listed 20-byte addresses (bytes, hex string, or `Address` object) |
| `@callable_by(OWNER)` | The actor's registered owner (see §12.10) |
| `@callable_by(SELF)` | Intra-actor calls only (see §7.3) |
| *(none)* | External callers denied; intra-actor calls always pass |

```python
from cowboy_sdk import actor, public, callable_by, OWNER, SELF, runtime

@actor
class Vault:
    def init(self, payload):
        runtime.assume_ownership_if_unowned()

    @public
    def balance_of(self, payload):
        return self._compute_balance()        # calls underscore helper — no perm check

    @callable_by(OWNER)
    def withdraw(self, payload):
        ...

    @callable_by(b"\xaa" * 20, b"\xbb" * 20)
    def admin_pause(self, payload):
        ...

    def _compute_balance(self):
        ...    # underscore prefix — not wrapped, no permission check at all
```

### 7.2 Internal Helpers

**Convention: name internal helpers with a leading underscore.** The `@actor` wrap pass skips underscore-prefixed names unless they carry an explicit `@public` / `@callable_by` tag, so `self._helper(payload)` runs without a permission check. A non-underscore method without a permission decorator is still treated as a handler and will raise `PermissionDeniedError` when reached from an external caller.

### 7.3 `@callable_by(SELF)` Semantics

`SELF` resolves via `caller == self.address` — i.e., the host has actively set `sender` to the actor's own address. This fires for timer self-fires and explicit self-submission flows. It does **not** fire for ordinary `self.method()` calls inside a handler, because `runtime.get_sender()` returns the outermost caller address (the EOA or upstream actor), not the executing actor's address.

### 7.4 `init` Bootstrap Window

A handler named `init` is implicitly callable by anyone while the actor has not yet recorded successful initialization (the `__INITIALIZED__` reserved slot is unset). The SDK sets this flag automatically after `init` returns without raising. After that, `init` follows the same deny-by-default rules as every other handler.

The deploy machinery runs `init` in the same transaction as the deploy with `sender = deployer`, eliminating the front-run window.

---

## 8. Handler Modes

Every handler runs under one of two modes, declared via decorator:

| Mode | Decorator | Async side effects allowed? |
|---|---|:---:|
| **Pure** (default) | `@pure` (implicit) | No |
| **Deferred** | `@deferred` | Yes |

A **pure** handler MUST NOT issue any operation that produces an async effect: `send()`, `runtime.schedule_timer()`, `runtime.submit_job()`, emitting callbacks. Synchronous `call()` and local computation are allowed. Any prohibited operation inside a pure handler raises `PurityViolationError`.

A **deferred** handler MAY issue any SDK operation subject to entitlement gates.

```python
from cowboy_sdk import actor, public, deferred, send

@actor
class Example:
    @public
    def balance_of(self, payload) -> int:          # @pure by default
        addr = payload.get("addr") if isinstance(payload, dict) else payload
        return self.storage.get(f"bal:{addr}", 0)

    @deferred
    @public
    def transfer(self, payload) -> None:
        to = payload["to"]
        amount = payload["amount"]
        self.storage[f"bal:sender"] -= amount
        self.storage[f"bal:{to}"] = self.storage.get(f"bal:{to}", 0) + amount
        send(to, {"kind": "received", "amount": amount})   # async side effect
```

The split exists because pure handlers are safe targets for read-only RPCs (CIP-14 query path, external introspection tools); the runtime can execute them without the overhead of a deferred effect queue. The enforcement is a runtime check at the Host API boundary, not a static check.

---

## 9. Call Primitives

Three primitives for inter-actor and off-chain interaction:

| Primitive | Timing | Return value | Atomic with caller? | Typical use |
|---|---|:---:|:---:|---|
| `call()` | same transaction (T+0) | yes | yes (shared rollback) | atomic cross-actor operations, reads |
| `send()` | next block (T+1) | no | no (fire-and-forget) | notifications, triggering downstream work |
| `await runner.<op>` | T+K, after off-chain execution | yes (resume value) | no | LLM, HTTP, MCP tool calls |
| `await ActorRef.async_*` | T+K, after target actor responds | yes | no | actor-to-actor async request/response |

**Standalone `cowboy` SDK note:** Top-level `call()` and `send()` are not exported by the standalone package. For local tests use `runtime.call_actor(target, method, payload, cycles_limit)` and `runtime.send_message(target, payload)` respectively.

### 9.1 `call()` — Synchronous Cross-Actor Call

```python
from cowboy_sdk import call

result = call(
    target="0x1111...",
    method="get_balance",
    args={"user": "0xABCD..."},
    cycles_limit=5000,
)
```

Arguments:
- `target`: 20-byte address, as `Address`, hex string, or raw bytes.
- `method`: UTF-8 handler name on the target.
- `args`: CBOR-encodable dict of keyword arguments, or list of positional arguments.
- `cycles_limit`: explicit cycle budget for the callee. Defaults to `100_000` if omitted; passing it explicitly is recommended for precise metering.

Semantics:
- Executes in the same transaction. Shared read-write set with the caller.
- Callee exceptions propagate — uncaught, they roll back the entire transaction.
- Call depth is capped at 32. Exceeding this raises `CallDepthExceeded`.
- Return value is CBOR-decoded and returned to the caller.

The `ActorRef` wrapper provides syntactic sugar:

```python
from cowboy_sdk import ActorRef

oracle = ActorRef("0x4444...", cycles_limit=5000)
price = oracle.get_price("ETH")     # lowers to call("0x4444...", "get_price", ["ETH"])
```

### 9.2 `send()` — Fire-and-Forget Message

```python
from cowboy_sdk import send

send(
    target="0x3333...",
    payload={"event": "order_created", "order_id": "abc"},
)
```

Semantics:
- Enqueues a message for delivery at the start of the next block.
- No return value; `send()` returns immediately.
- Irrevocable: once a transaction commits, its sent messages are delivered even if later logic would want to cancel them.
- Allowed only from `@deferred` handlers.

Authors SHOULD structure handlers so that all fallible synchronous calls complete before issuing `send()`. Raising after a `send()` does not unsend the message.

### 9.3 `await runner.<op>` — Runner Continuation

Decorated `async def` methods can `await` off-chain operations. **`cowboy_sdk` (PVM) only** — not available in the standalone `cowboy` package.

```python
from cowboy_sdk import runner, capture

@runner.continuation
async def analyze(self, msg):
    ctx = capture()
    ctx.summary = await runner.llm(
        prompt=f"Summarize: {msg['text']}",
        max_tokens=200,
    )
    self.storage["last_summary"] = ctx.summary
```

The decorator lowers the function into an FSM at class-load time (§10). Available awaitables under `runner`:

| Awaitable | Purpose | Required entitlement |
|---|---|---|
| `runner.llm(prompt, ...)` | LLM inference | `oracle.llm` |
| `runner.http(url, method, ...)` | HTTP request | `http.fetch` |
| `runner.mcp(server, tool, args)` | MCP tool call | varies by tool |

### 9.4 `await ActorRef.async_*` — Actor Continuation

Actor-to-actor async calls use the `@actor.continuation` decorator. **`cowboy_sdk` (PVM) only.**

```python
from cowboy_sdk import actor, ActorRef, capture

@actor
class Aggregator:
    @actor.continuation(timeout_blocks=100)
    async def collect(self, assets: list[str]) -> dict:
        ctx = capture()
        ctx.results = {}
        for asset in assets[:5]:
            ctx.results[asset] = await ActorRef("0x4444...").async_get_price(asset)
        return ctx.results
```

Semantics:
- Each `await ActorRef.async_<method>(...)` is lowered to `send(target, {...})` plus a state save.
- The target's handler is invoked in a future block; when it completes, it delivers a callback message that resumes the caller's continuation.
- Requires both caller and callee to be `@deferred`.

---

## 10. Continuations

All continuation features in this section are **`cowboy_sdk` (PVM) only**.

### 10.1 FSM Compilation

Both `@runner.continuation` and `@actor.continuation` compile at class-load time into a pair of functions:

- `<name>`: the initial handler; starts the FSM, persists state 0, issues the first async effect, returns.
- `<name>__resume`: the resume handler; called by the runtime on callback delivery, loads state, advances the FSM, issues the next async effect (or returns final value).

The generated code is never observed by actor authors. Its shape is non-normative.

### 10.2 `capture()` — Explicit Local State

Local variables that must survive an `await` MUST be attached to a `capture()` object:

```python
ctx = capture()
ctx.first = await runner.llm("...")       # first-await state
ctx.second = await runner.http("...")     # second-await state
return ctx.first + ctx.second
```

Captured values MUST be of CBOR-encodable types (see §11.5). Attempting to capture a closure, generator, file handle, thread, or custom object raises `CaptureTypeError` at the `await` point.

Continuation state is stored at key `__continuation:<correlation_id>` within the actor's own storage. Limits:

| Constant | Value | Meaning |
|---|---:|---|
| `CONTINUATION_MAX_SIZE` | 64 KiB | per-continuation serialized state |
| `CONTINUATION_MAX_COUNT` | 100 | active continuations per actor |

Exceeding either limit raises `ContinuationSizeLimitError` or `ContinuationCountLimitError`.

### 10.3 Guards

Continuations can assert that specific storage keys were not modified during the async wait:

Method A — decorator-level:
```python
@runner.continuation(guard_unchanged=["price", "config"])
async def act_on_price(self, msg):
    decision = await runner.llm(f"Given price {self.storage['price']}, ...")
    # On resume: if storage["price"] or storage["config"] was modified by any
    # intervening transaction, raise StateConflictError BEFORE running the body.
    ...
```

Method B — object-level via `GuardedValue`:
```python
balance = self.storage.guard("balance")          # GuardedValue
result = await runner.llm("...")
new_balance = balance.value - 100                # raises StateConflictError if changed
self.storage["balance"] = new_balance
```

Guard fingerprints are `keccak256(cbor(value_at_snapshot))`. The fingerprint is stored in the continuation state and re-checked on resume.

### 10.4 Bounded Loops

`await` inside a Python loop requires an explicit upper bound:

```python
from cowboy_sdk import bounded_loop, capture

@runner.continuation
async def fan_out(self, items: list):
    ctx = capture()
    ctx.results = []

    @bounded_loop(max_iterations=10)
    async def run():
        for item in items[:10]:
            ctx.results.append(await runner.process(item))

    await run()
```

A `bounded_loop` with `max_iterations = N` generates `N` FSM states at compile time. Exceeding `N` at runtime raises `LoopBoundExceeded`. Unbounded iteration with `await` is rejected at class-load time.

### 10.5 Sequential Await Limit

A single continuation function MAY contain at most **8 sequential await points** (not counting awaits inside `bounded_loop`). This is a compile-time limit; violations are rejected at class-load. Authors needing more should split into multiple continuations.

---

## 11. Type System

The SDK replaces or constrains Python built-ins whose semantics are non-deterministic or ambiguous across platforms.

**All types in this section are `cowboy_sdk` (PVM) only** unless otherwise noted. The standalone `cowboy` package exports `Address` as two separate forms (a Pydantic hex-string model for chain interactions, and a 20-byte stub for local actor testing) but does not export `BlockHeight`, `SoftFloat`, `ordered_set`, or `CowboyModel`.

### 11.1 `Address`

20-byte Ethereum-compatible address.

```python
from cowboy_sdk import Address

a = Address.from_hex("0x7a3B6E...F92E")
b = Address(raw_bytes_20)
a.to_hex()       # checksummed (EIP-55)
a.to_bytes()     # 20-byte payload
Address.ZERO     # sentinel
Address.JOB_DISPATCHER   # 0x0000…0002
```

### 11.2 `BlockHeight`

Semantic `int` wrapper for block heights. Identity-equal to `int` at the bytecode level; useful for type annotations.

### 11.3 `SoftFloat`, `ordered_set`

- `SoftFloat` is a software-floating-point type. Native Python `float` depends on the hardware FPU and is non-deterministic across platforms; authors MUST use `SoftFloat` instead. The SDK may alias `SoftFloat = float` when running under a PVM that enforces softfloat at the instruction layer; authors SHOULD still annotate with `SoftFloat` for clarity.
- `ordered_set` is a dict-backed set with deterministic insertion-order iteration. Python's built-in `set()` is prohibited in actor code.

### 11.4 `CowboyModel`

A dataclass-like base class for structured data. Feature set:

- Deterministic serialization via `to_cbor()` and `from_cbor(bytes)`.
- JSON Schema export via `schema()` (for use with `Verify`).
- Field validation on construction.
- Forbids `set` / `frozenset` fields (non-deterministic iteration).
- Forbids `float` fields (requires `SoftFloat`).

```python
from cowboy_sdk import CowboyModel, SoftFloat

class Trade(CowboyModel):
    asset: str
    size: int
    price: SoftFloat
```

### 11.5 CBOR Codec

The SDK uses Canonical CBOR (RFC 8949 §4.2) everywhere encoding crosses a determinism boundary: storage values, message payloads, continuation state, call arguments, return values. Requirements:

- Map keys sorted by byte-lexicographic order.
- No duplicate keys.
- Floats encoded as IEEE 754 double (when unavoidable).
- Integers encoded in the shortest form.

`cowboy_sdk.codec.encode(v) -> bytes` and `.decode(b) -> value` are the canonical entry points.

---

## 12. Runtime Module

`cowboy_sdk.runtime` exposes the Host API. Actor code SHOULD prefer the higher-level primitives in `cowboy_sdk` (call, send, storage proxy); `runtime` is for cases where fine-grained control is needed (e.g., system actors, upgrade flows).

The standalone `cowboy` package provides a **partial** local stub of `runtime`. It covers context access (`get_sender`, `get_actor_address`, `get_block_height`, `get_timestamp_ms`), events, `send_message` / `call_actor`, low-level state no-ops, ownership helpers, and test utilities (`configure`, `reset`, `get_captured_events`, `get_captured_messages`). It does **not** implement token operations, timers, `upgrade_self`, `submit_job`, `keccak256`, `randomness`, `charge_gas`, or `scan_state_prefix` — those functions exist only in the on-chain `cowboy_sdk.runtime`.

### 12.1 Context

| Function | Returns | Notes |
|---|---|---|
| `runtime.get_sender()` | `bytes` (20) | Caller of the current handler |
| `runtime.get_actor_address()` | `bytes` (20) | This actor's address |
| `runtime.get_block_height()` | `int` | Current block height |
| `runtime.get_timestamp_ms()` | `int` | Block timestamp, milliseconds since epoch |

These are the ONLY authorized sources of time and identity. `time.time()`, `datetime.now()`, and similar are trapped.

### 12.2 State

Lower-level state access paralleling `self.storage`:

```python
runtime.get_state(key: bytes) -> bytes | None
runtime.set_state(key: bytes, value: bytes) -> None
runtime.delete_state(key: bytes) -> None
```

`set_state` and `delete_state` refuse writes to reserved keys (`__OWNER__`, `__INITIALIZED__`). See §12.10.

### 12.3 Events

```python
runtime.emit_event(name: str, payload: dict | bytes | str) -> None
```

Emits a log entry visible in the transaction receipt. Metered in Cells per CIP-3.

### 12.4 Tokens (CIP-20)

The standard CIP-20 interface is exposed as runtime operations:

```python
runtime.token_create(name, symbol, decimals, initial_supply, max_supply, transfer_hook, metadata_uri) -> token_id
runtime.token_transfer(token_id, to, amount)
runtime.token_approve(token_id, spender, amount)
runtime.token_transfer_from(token_id, from_addr, to, amount)
runtime.token_mint(token_id, to, amount)
runtime.token_burn(token_id, amount)
runtime.token_balance_of(token_id, account) -> int | None
runtime.token_allowance(token_id, owner, spender) -> int | None
runtime.token_total_supply(token_id) -> int | None
```

Each requires the corresponding entitlement (`token.create`, `token.transfer`, etc.).

### 12.5 Timers (CIP-5)

```python
runtime.schedule_timer(fire_at_block: int, payload: bytes) -> timer_id: bytes
runtime.schedule_timer_ex(height, payload, fee_payer, gas_limit, expires_at) -> timer_id: bytes
runtime.extend_timer(timer_id: bytes, new_expires_at: int) -> None
runtime.cancel_timer(timer_id: bytes) -> None
```

At `fire_at_block`, the scheduler delivers `payload` to the actor's `on_timer` handler. Requires `timer.schedule` entitlement. `schedule_timer_ex` allows overriding fee payer, gas limit, and expiry per CIP-5 §4.1.

### 12.6 Jobs (CIP-2)

```python
runtime.submit_job(payload: bytes) -> None
```

Low-level entry used by `@runner.continuation`; actor authors SHOULD prefer the continuation form.

### 12.7 Upgrades

```python
runtime.upgrade_self(new_code: bytes, new_manifest: bytes | None = None) -> None
```

Replaces the running actor's code and optionally its entitlement manifest. The new manifest MUST be a subset of the current manifest (no privilege escalation); violation raises at the Host boundary. Requires `sys.upgrade` entitlement.

### 12.8 Crypto

```python
runtime.keccak256(data: bytes) -> bytes                 # 32-byte hash
runtime.randomness(domain: bytes) -> bytes              # deterministic VRF output
```

`randomness()` produces deterministic per-block VRF output keyed by `domain`. This is the only authorized source of randomness; `random.random()` and `secrets` are trapped.

### 12.9 Metering

```python
runtime.charge_gas(amount: int) -> None
```

Explicitly consumes Cycles. Useful for implementations that want to front-load gas accounting for complex operations. Most actors do not need this; metering happens automatically at syscall boundaries.

### 12.10 Ownership

The ownership model tracks a single privileged address in the reserved `__OWNER__` storage slot. User code cannot read or write this slot via `self.storage[]` — the proxy raises `ValueError` for reserved keys. Use the runtime APIs:

```python
runtime.get_owner() -> bytes              # current owner (20 bytes), or b'' if unset
runtime.transfer_ownership(new_owner: bytes) -> None
runtime.renounce_ownership() -> None      # sets owner to zero address; irrevocable
runtime.assume_ownership_if_unowned() -> bytes   # first-caller-wins bootstrap
runtime.is_initialized() -> bool          # True after init returns successfully
```

Canonical bootstrap pattern:

```python
def init(self, payload):
    runtime.assume_ownership_if_unowned()   # deployer becomes owner atomically
```

**Transfer rules:**
- If no owner is set, any caller may set it (bootstrap window — safe only inside `init`).
- Once set, only the current owner or an intra-actor call may transfer.
- Passing the zero address to `transfer_ownership` raises `ValueError`; use `renounce_ownership()` explicitly.

`@callable_by(OWNER)` handlers become permanently unreachable after `renounce_ownership()`.

**Reserved storage keys:**

| Key | Managed by |
|---|---|
| `__OWNER__` | `runtime.transfer_ownership`, `runtime.renounce_ownership`, `runtime.assume_ownership_if_unowned` |
| `__INITIALIZED__` | Set automatically by the SDK after `init` returns without raising |

The standalone `cowboy` package provides stub implementations of all ownership functions backed by module-level state. Call `runtime.reset()` between tests to clear ownership and initialization state.

### 12.11 State Prefix Scan

```python
runtime.scan_state_prefix(prefix: bytes, limit: int = 100) -> list[tuple[bytes, bytes]]
```

Returns up to `limit` `(key, value)` pairs whose user-key starts with `prefix`, in ascending key order. Only verbatim-mode keys (≤ 32 bytes) are visible. `limit` is clamped to 1000 by the host.

---

## 13. Verification Builder

`Verify` produces CIP-2 verification configurations using a fluent chain. **`cowboy_sdk` (PVM) only.**

```python
from cowboy_sdk import Verify, runner

await runner.llm(
    prompt="Analyze market...",
    response_model=MarketAnalysis,
    verification=Verify.builder()
        .mode("consensus")
        .runners(5)
        .threshold(3)
        .check(Verify.json_schema_valid(MarketAnalysis.schema()))
        .check(Verify.numeric_tolerance("score", 0.05))
        .check(Verify.no_prompt_leak())
        .build(),
)
```

`VerifyBuilder.mode()` validates against the following set and raises `ValueError` on unknown values:

| Mode | Semantics |
|---|---|
| `none` | No verification; first runner result is used directly |
| `consensus` | Multiple runners execute; majority result wins |
| `deterministic` | All runners must return exactly the same result |
| `tee` | Trusted Execution Environment verification |
| `zk` | Zero-knowledge proof verification |
| `optimistic` | Optimistic verification; challengeable within a dispute window |

Checks are appended in the order `.check()` is called and passed to the Rust result-verifier in that order.

Built-in checkers:

| Checker | Purpose |
|---|---|
| `Verify.exact_match()` | Byte-for-byte equality across runners |
| `Verify.json_schema_valid(schema)` | Output conforms to JSON Schema |
| `Verify.structured_match(fields)` | Named fields match across runners |
| `Verify.majority_vote(field, threshold)` | Field value meets consensus threshold (default 0.5) |
| `Verify.supermajority_vote(field, threshold)` | Field value meets supermajority threshold (default 0.67) |
| `Verify.numeric_tolerance(field, tolerance)` | Field within ±tolerance |
| `Verify.numeric_range(field, min_val, max_val)` | Field within bounds |
| `Verify.set_equality(field)` | Unordered set equality |
| `Verify.contains_all(substrings)` | Output contains required strings |
| `Verify.contains_none(substrings)` | Output excludes strings |
| `Verify.regex_match(pattern)` | Regex match |
| `Verify.length_bounds(min_len, max_len)` | Output length within bounds |
| `Verify.semantic_similarity(reference, threshold)` | Embedding cosine similarity ≥ threshold |
| `Verify.no_prompt_leak()` | Output does not echo the system prompt |
| `Verify.entropy_check(min_entropy)` | Output is not degenerate/repetitive |
| `Verify.custom(name, **kwargs)` | Named custom rule registered in the Rust result-verifier |
| `Verify.custom_actor(actor_address, method, args)` | Delegates verification to an on-chain actor |

Additional supplemental checkers (`not_empty`, `contains`, `length_limit`, `http_status`, `response_time`, `signature_valid`, `tee_attestation`, `deterministic_output`, `field_exists`, `format_check`) are exported by the implementation but are not mandated by this CIP.

---

## 14. Entitlements

### 14.1 Manifest Format

A manifest accompanies every deploy and upgrade. JSON shape:

```json
{
  "entitlements": [
    {"id": "econ.hold_balance"},
    {"id": "econ.transfer", "params": {"max_amount": "1000000000", "max_per_block": "10000"}},
    {"id": "http.fetch", "params": {"allowlist_domains": ["api.example.com"], "max_requests": 100}},
    {"id": "oracle.llm", "params": {"max_tokens": 4096, "max_requests": 50}}
  ]
}
```

Rules:

- `id` values MUST appear in the Entitlement Registry (`types/src/registry.rs`).
- The `entitlements` array MUST be lexicographically sorted by `id`; a chain MUST reject deploy transactions with an unsorted manifest.
- `params` contents are entitlement-specific and validated at deploy time against the registry's `ParamSchema`.
- An upgrade's manifest MUST be a subset (in both ids and param-bound strength) of the prior manifest.

### 14.2 Runtime Enforcement

Entitlements are enforced at the Host API boundary, not in SDK Python:

1. Actor invokes an SDK function.
2. SDK issues the corresponding syscall.
3. Host checks the actor's manifest for the required entitlement.
4. If absent: Host returns `HostError::MissingEntitlement` → SDK raises the corresponding error.
5. If present but quota-exceeded or param-restricted: Host returns the appropriate error.

Actor authors do not check entitlements in Python; they rely on the runtime to enforce.

### 14.3 Entitlement Registry (Informative Summary)

| ID | Gates | Params |
|---|---|---|
| `econ.hold_balance` | CBY balance storage | — |
| `econ.transfer` | Native CBY balance transfers (host-level; no direct Python SDK function) | `max_amount`, `max_per_block` |
| `exec.spawn` | child actor deploy | `max_children` |
| `http.fetch` | `runner.http()` | `allowlist_domains`, `max_requests` |
| `oracle.llm` | `runner.llm()` | `max_tokens`, `max_requests` |
| `secrets.read` | `runner.http(..., secrets=[...])`, `runner.mcp(...)`, `runner.llm(...)` | `keys` |
| `storage.kv` | `self.storage.set_raw` beyond quota | `max_bytes` |
| `sys.upgrade` | `runtime.upgrade_self()` | — |
| `timer.schedule` | `runtime.schedule_timer()` | — |
| `token.create`, `token.transfer`, `token.mint`, `token.burn` | corresponding `runtime.token_*` | varies |
| `bridge.asset`, `bridge.subscribe_event` | CIP-19 bridge primitives | varies |
| `accel.gpu` | GPU runner selection | `min_vram_gb` |
| `sec.data_residency` | geofenced execution | (attested) |

CIP-2 §7 is the normative source.

---

## 15. Error Hierarchy

All SDK exceptions derive from `cowboy_sdk.CowboyError`. Each exception exposes:

- `HOST_ERROR_CODE: int` — Host API error code (1–8)
- `ERROR_SLUG: str` — short identifier, format `E1xxx`
- `.why: str` — human explanation
- `.fix: str` — suggested remediation

Categories:

Multiple exception classes may share a slug; the slug identifies the error category, not the specific class.

| Class | Slug | When |
|---|---|---|
| `DeterminismError` | E1101 | Non-deterministic operation attempted |
| `CycleLimitExceeded` | E1201 | Cycles budget exhausted |
| `LoopBoundExceeded` | E1201 | `bounded_loop` iterated past declared max |
| `RunnerTimeoutError` | E1201 | `timeout_blocks` expired |
| `CaptureTypeError` | E1202 | Captured value is not CBOR-encodable |
| `ContinuationLimitError` | E1202 | Continuation structural constraint violated (>8 awaits, nested await, recursive await) |
| `AddressError` | E1202 | Invalid `Address` construction |
| `ContinuationNotFoundError` | E1203 | Resume with unknown correlation id |
| `CallDepthExceeded` | E1205 | Call stack depth > 32 |
| `ReentrancyError` | E1205 | `@reentrancy_guard` tripped |
| `PurityViolationError` | E1205 | Async side effect from `@pure` handler |
| `StateConflictError` | E1206 | Guard snapshot mismatch on resume |
| `ContinuationCorruptedError` | E1206 | State integrity check failed |
| `ActorCallError` | E1206 | Callee raised or returned invalid payload |
| `ContinuationSizeLimitError` | E1208 | Serialized state > 64 KiB |
| `ContinuationCountLimitError` | E1208 | > 100 active continuations |
| `CodecError` | E1213 | CBOR encode/decode failure |
| `ActorNotFoundError` | E1220 | Target address is not a deployed actor |
| `PermissionDeniedError` | E1230 | Caller not authorized for this handler |
| `RunnerValidationError` | E1604 | Runner result failed `Verify` chain |
| `DeterministicValidationError` | E1610 | Runners returned divergent results under deterministic verification |

Exceptions are CBOR-encoded into the transaction receipt; clients use `ERROR_SLUG` for programmatic handling.

The standalone `cowboy` package also exports client-side exceptions (`TransactionFailed`, `RpcError`, `AccountNotFound`, `NonceMismatch`, etc.) that are not part of this CIP.

---

## 16. CLI

The canonical CLI is `cowboy`, implemented in `node/cli/`. Commands relevant to actor development:

### 16.1 Project bootstrap

```
cowboy init <network>                     # network: local | dev | summit
cowboy wallet create [--output FILE]
cowboy wallet create-mnemonic
```

Persists config at `.cowboy/config.json` (RPC URL, sender key, nonce cache).

### 16.2 Actor lifecycle

```
cowboy actor new <name>                   # scaffold actors/<name>/main.py
cowboy actor deploy
    --code <file.py>
    --salt <hex>
    [--manifest-json <file.json>]
    [--no-init]                           # skip atomic init entirely
    [--init-handler <name>]               # default: "init"
    [--init-payload <json-string | @file>]  # default: "{}"
    [--cycles-limit N] [--cells-limit N]
cowboy actor address
    --code <file.py>
    --creator <addr>
    --salt <hex>                          # compute CREATE2 address locally
cowboy actor execute
    --actor <addr>
    --handler <name>
    --payload <hex | @file>
cowboy actor get --address <addr>
cowboy actor logs --address <addr>
```

Fund and upgrade are top-level system commands (not subcommands of `actor`):

```
cowboy fund-actor --actor <addr> --amount <cby>
cowboy upgrade-actor
    --actor <addr>
    --code <new.py>
    [--manifest-json <new.json>]          # requires sys.upgrade entitlement
```

### 16.3 Ecosystem

```
cowboy account balance [--address <addr>]
cowboy token create --name N --symbol S --decimals D --initial-supply X [--max-supply Y]
cowboy token transfer --token-id T --to <addr> --amount A
cowboy runner list
cowboy runner register --stake <amount>
cowboy job submit --job-spec <file.json>
cowboy watchtower init
cowboy watchtower new feed --name N [--description D]
cowboy watchtower feed <id> publish --data <json>
```

### 16.4 Conformance

Any implementation MAY extend the CLI with additional commands. Renaming any command in this section is a breaking change and requires a CIP revision.

---

## 17. PVM Determinism Rules

Actor code MUST conform to the following rules. Violations are detected at class-load time where statically decidable; otherwise they raise `DeterminismError` at runtime.

| # | Rule | Replacement |
|---|---|---|
| 1 | No `import time`, `datetime.now()` | `runtime.get_block_height()`, `runtime.get_timestamp_ms()` |
| 2 | No `import random`, no `secrets` | `runtime.randomness(domain)` |
| 3 | No hardware `float` in actor state, message payloads, or CBOR | `SoftFloat` |
| 4 | No `set()` / `frozenset()` | `ordered_set` |
| 5 | No `pickle` | CBOR (`cowboy_sdk.codec`) |
| 6 | Call depth ≤ 32; pass `cycles_limit` explicitly for precise metering (default: `100_000`) | — |
| 7 | ≤ 8 sequential awaits per continuation | split into multiple continuations |
| 8 | `await` in loops requires `@bounded_loop(max_iterations=N)` | — |
| 9 | `capture()` required for locals spanning an `await` | — |
| 10 | `send()` and other async side effects prohibited from `@pure` handlers | mark handler `@deferred` |
| 11 | No filesystem, network, or subprocess access | `runner.http`, `runtime.*`, entitlement-gated |

---

## 18. Reference Implementation

Canonical implementation:

- **In-PVM SDK (`cowboy_sdk`):** `node/pvm/Lib/cowboy_sdk/` (version 0.1.1)
- **Host API:** `node/execution/src/pvm_host.rs`
- **CLI:** `node/cli/` (binary `cowboy`)
- **Standalone developer SDK (`cowboy`):** `python-sdk/` (PyPI: `cowboy-sdk`, version 0.1.0)
- **Examples:** `cowboy/examples/01-tokens`, `cowboy/examples/08-audio-transcription`, `cowboy/examples/09-image-generation`, `cowboy/examples/13-dao-copilot`, `cowboy/examples/14-compliance`, `cowboy/examples/18-ring-demo`

---

## 19. Open Questions / Gaps

1. **CIP-9 volume mounts from the SDK.** Today, CBFS volumes are a runner-side concern. An actor-side API for `mount(volume_id, access_mode)` is not yet defined. Needed for first-class storage-attached actor workflows.
2. **CIP-7 / CIP-17 stream helpers.** `cowboy watchtower` exists at the CLI level and as a system-actor pattern, but there is no actor-side `@on_stream(stream_id)` decorator or `stream_publish()` helper. Authors currently manage this via raw `call()` / `send()`.
3. **Checkpoint mode deprecation.** `runtime.is_checkpoint_mode()` exists for local development but is marked for removal once FSM mode is production-stable across all targets.
4. **Reentrancy semantics on `call()` cycles.** `@reentrancy_guard` is defined, but its key derivation (`keccak256(method_name ‖ caller_addr)`) may over-collide in contract-factory patterns. A CIP-6.1 revision may add an explicit `key` argument.
5. **Address scheme forward compatibility.** `Address` is fixed at 20 bytes (Ethereum-compatible). A future migration to a larger scheme would break the type; no migration path is specified here.
6. **Static loop-bound detection.** The compiler rejects unbounded `await`-in-loop at class-load, but edge cases (awaits inside comprehensions, awaits in helper functions called from loops) are under-specified. A future revision should enumerate accepted and rejected shapes.
7. **Entitlement manifest upgrade semantics.** "Subset" is defined informally; the registry needs an `is_tighter_than` operator per entitlement, currently implemented ad-hoc.
8. **Standalone `cowboy` SDK coverage gaps.** The standalone package does not yet mirror `runner`, `capture`, `ActorRef`, `Verify`, `CowboyModel`, `SoftFloat`, `ordered_set`, `BlockHeight`, or `Storage.get_raw()` / `set_raw()` / `guard()`. Actors that use those features must be tested against a live PVM sandbox.
