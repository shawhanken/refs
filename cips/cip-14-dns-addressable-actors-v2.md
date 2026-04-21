---
title: "CIP-14: DNS-Addressable Actors (v2)"
description: Code-aligned v2 — real PVM syscalls, real RPC primitives, real address space, real entitlement registry / settlement plumbing
---

# CIP-14 v2

> **Versioning.** This is v2 of CIP-14. v1 is the canonical document `cip-14-dns-addressable-actors.md` (preserved verbatim as Part I). v2 = v1 + the alignment revision (Part II) + the cross-cutting conventions (Part III).
>
> **Conflict rule:** Part II is canonical wherever it contradicts Part I. Part III defines shared conventions referenced by Part II.
>
> **Summary of v2 changes**
>
> - **`queryActor` → `read_handler` RPC + PVM read-only mode.** v1 referenced a hypothetical "Milestone 2 §5.2 `queryActor`" that does not exist in `node/rpc/src/rpc.rs`. v2 specifies a concrete RPC and PVM mode flag with an exhaustive trapped-syscall table.
> - **System actor renumbering** `0x0011` / `0x0012` → `0x0C` / `0x0D` / `0x0E` (continues the existing `0x01..0x0B` sequence).
> - **System-reserved selector for `"http.request"`.** v1 placed authenticity in SDK `ctx.sender` checks; v2 makes it a protocol invariant via PVM router rejection of non-system senders.
> - **Receipt registry replaces `_http/results/{request_id}` actor-KV pattern.** Avoids exhausting `MAX_TIMERS_PER_ACTOR=1024` per actor.
> - **Stake vs. operating balance separation.** Gateway stake stays locked collateral; gas comes from the operating account. Actor-funded ingress uses existing `Action::UseOwnerBalance`.
> - **Real syscall names.** Trap table uses `state_set` / `schedule_timer` / `token_transfer` / `submit_job` (not `set_storage` / `set_timeout` / `transfer` / `submit_task`). Adds `randomness` to the trap list — v1 missed it.
> - **Default `subdomain_policy = OWNER_ONLY`** (was `ACTOR_MANAGED`) to prevent accidental subdomain DoS.
> - **Settlement reuse.** Name registration and Gateway pool fees route through `system:registry_settlement_config` and `system:gateway_pool_config` under `GOVERNANCE_SYSTEM_ACTOR=0x09` via the existing `UpdateSettlementConfig` opcode.

---

## Part I — v1 Specification (verbatim from `cip-14-dns-addressable-actors.md`)


<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-03-07
  **Requires:** CIP-2 (Off-Chain Compute), CIP-3 (Dual-Metered Gas)
</Note>

## 1. Abstract

This proposal defines **DNS-Addressable Actors** — a system for assigning human-readable domain names to Cowboy actors and routing internet HTTP traffic to them through a dedicated Gateway network. The core primitive is an **ingress entitlement** (`ingress.http`) that allows an actor to receive inbound HTTP requests, and an **on-chain Route Registry** that maps domain names to actor addresses.

This CIP specifies:

- The `ingress.http` entitlement grant and its parameter schema.
- A Route Registry system actor that maps names to actor addresses.
- A canonical HTTP request/response envelope for actor message handlers.
- An explicit **query path** (read-only, no consensus) using the `queryActor` RPC primitive, distinct from the **command path** (state-mutating, consensus-required).
- A Gateway role — a dedicated ingress node type that bridges HTTP to actor messaging.
- Subdomain-first naming under `cowboy.network`.

This CIP intentionally defers the following to future CIPs:

- Public asset hosting via CIP-9 (`PUBLIC_READ` volumes).
- CIP-7 stream bridging to SSE/WebSocket (see CIP-17).
- Payment gating via x402 or other protocols.
- Custom domain binding and first-party TLD support (see CIP-16).

---

## 2. Motivation

Cowboy actors are autonomous programs with persistent state, message handlers, timers, LLM inference, and off-chain compute. Today they are only reachable through blockchain transactions. This confines their utility to on-chain interactions and makes them invisible to the broader internet.

Existing blockchain naming systems (ENS, Handshake, Unstoppable Domains) resolve names to passive addresses or content hashes. They do not route traffic to running programs. Cowboy actors are fundamentally different — they are **active endpoints** that can handle requests, not just receive tokens. Making them DNS-addressable creates a new class of internet service:

1. **AI agents with web presence**: An LLM-powered actor with its own API and identity — no hosting provider, no cloud account.
2. **Verifiable APIs**: Anyone can audit the code behind a DNS-addressable actor because the actor code is on-chain and deterministic.
3. **Self-sovereign web services**: The actor *is* the server. It persists without infrastructure management, scales through the protocol, and bills natively.
4. **Autonomous economic agents**: An actor can earn revenue from its API, use that to fund its own compute, and operate indefinitely without human intervention.

---

## 3. Design Goals

- Introduce HTTP ingress without changing actor execution semantics.
- Respect the existing async actor messaging model — no synchronous assumptions.
- Use the existing `queryActor` RPC primitive for fast, read-only requests.
- Use standard `ActorMessage` transactions for state-mutating requests.
- Define Gateways as a first-class ingress role, separate from Runners and Relay Nodes.
- Model the entitlement using the canonical `EntitlementGrant` format (dotted string ID with params).
- Keep the scope tight: ingress routing only. Defer asset hosting, stream bridging, payment, and custom domains to follow-on CIPs.

## 4. Non-goals

- Replacing native actor-to-actor messaging. HTTP is the **external** ingress protocol. Internal actor composition MUST use `send_message`.
- Synchronous off-chain compute within HTTP handlers. LLM inference and HTTP egress remain asynchronous (CIP-2 submit-task + deferred callback).
- Public static asset hosting (future CIP extending CIP-9).
- Real-time stream bridging (future CIP bridging CIP-7 to SSE/WebSocket).
- Payment gating (future CIP integrating x402 or similar).
- Custom TLDs or alternative DNS roots.

---

## 5. Definitions

- **Gateway**: A network node that terminates TLS, resolves actor names, and bridges HTTP requests to the actor message protocol. Gateways are a dedicated ingress role, distinct from Runners, Validators, and Relay Nodes.
- **Route Registry**: A system actor that maintains the authoritative mapping from domain names to actor addresses.
- **Query path**: Read-only request execution via `queryActor` — the actor handler runs against committed state without creating a transaction or requiring consensus.
- **Command path**: State-mutating request execution via a standard `ActorMessage` transaction that goes through consensus.

---

## 6. The `ingress.http` Entitlement

### 6.1 Entitlement Grant

Following the canonical entitlement model (§9 of the Entitlements Specification), `ingress.http` is a new entry in the normative entitlement registry.

> **Amendment required:** The Entitlements Specification §9 states *"Any entitlement not listed here is invalid"* (§10). Adoption of this CIP MUST add a new §9.x **Ingress** section to the Entitlements Specification containing the `ingress.http` row below. Until that amendment lands, `ingress.http` is not a valid entitlement and actors declaring it will be rejected at deployment.

| ID | Description | Inheritable | Attested | Quota | Params |
| --- | --- | :---: | :---: | :---: | --- |
| `ingress.http` | Actor may receive inbound HTTP requests via Gateway. | ❌ | ❌ | ✅ | `allowlist_methods`, `max_request_bytes`, `max_response_bytes`, `max_query_cycles` |

### 6.2 Parameter Schema

| Param | Type | Description | Default |
| --- | --- | --- | --- |
| `allowlist_methods` | `array<string>` | HTTP methods the actor accepts. `*` permits all. | `["GET", "HEAD", "POST"]` |
| `max_request_bytes` | `u64` | Maximum request body size in bytes. | `1_048_576` (1 MiB) |
| `max_response_bytes` | `u64` | Maximum response body size in bytes. | `1_048_576` (1 MiB) |
| `max_query_cycles` | `u64` | Maximum PVM cycles per query-path request. | `10_000_000` |

### 6.3 Example Actor Manifest

```json
{
  "entitlements": [
    {"id": "ingress.http", "params": {
      "allowlist_methods": ["GET", "HEAD", "POST"],
      "max_request_bytes": 1048576,
      "max_response_bytes": 1048576,
      "max_query_cycles": 10000000
    }},
    {"id": "storage.kv", "params": {"max_bytes": 10485760}},
    {"id": "econ.hold_balance"},
    {"id": "econ.transfer"}
  ]
}
```

### 6.4 Enforcement

- **Deployment-time**: The deployment transaction is rejected if `ingress.http` params are invalid (unknown methods, zero-value quotas).
- **VM syscall gate**: Not applicable — `ingress.http` is enforced at the Gateway and Route Registry, not within the PVM.
- **Gateway enforcement**: Gateways MUST reject requests to actors without `ingress.http`. Gateways MUST enforce `max_request_bytes` and `max_response_bytes`. On the query path, Gateways MUST enforce `max_query_cycles`.

---

## 7. Route Registry

### 7.1 System Actor

The Route Registry is a system actor at reserved address `0x0011`. It maintains the authoritative mapping:

```
name → RouteRegistration
```

```
RouteRegistration {
  actor_address:     Address,       // the actor this name resolves to
  owner:             Address,       // the account that owns this registration
  registered_at:     BlockHeight,
  expires_at:        BlockHeight,
  subdomain_policy:  u8,            // 0 = OWNER_ONLY, 1 = ACTOR_MANAGED (default), 2 = OPEN
}
```

### 7.2 Naming Hierarchy

Actors register names under `cowboy.network`:

```
<name>.cowboy.network                     → top-level actor name
<sub>.<name>.cowboy.network               → subdomain of the actor
<deep>.<sub>.<name>.cowboy.network        → nested subdomain
```

**Subdomain ownership**: When an actor registers `myagent`, it owns the entire subtree `*.myagent.cowboy.network`. Subdomain resolution depends on the `subdomain_policy`:

- `OWNER_ONLY` (0): Only the registration owner can add subdomain records that map to other actors.
- `ACTOR_MANAGED` (1, default): The actor handles all subdomain routing internally via its `http.request` handler. The full `Host` header is passed to the actor.
- `OPEN` (2): Any actor with `ingress.http` can register subdomains under this name (community namespaces).

### 7.3 Name Constraints

- Names are lowercase alphanumeric with hyphens: `[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]`.
- Minimum 3 characters, maximum 64 characters.
- Names MUST NOT start or end with a hyphen.
- Reserved names (`www`, `api`, `dns`, `gateway`, `relay`, `node`, `cowboy`, `system`, `admin`) are held by governance.

### 7.4 Registration

```python
# Actor or owner calls the Route Registry system actor
send_message(ROUTE_REGISTRY, "register", {
    "name": "myagent",
    "actor_address": self_address(),
    "duration_blocks": 31_536_000,  # ~1 year at 1 block/sec
})
```

**Requirements:**

1. Caller is the actor or the actor's deployer account.
2. Target actor has the `ingress.http` entitlement.
3. Name is not already registered (or has expired past grace + auction).
4. Registration fee is paid in `CBY`.

### 7.5 Registration Economics

Registration uses a **fee schedule** based on name length to discourage squatting:

| Name Length | Annual Fee (CBY) |
|:-----------:|:----------------:|
| 3 characters | `PREMIUM_3_FEE` (governance-set, high) |
| 4 characters | `PREMIUM_4_FEE` |
| 5 characters | `PREMIUM_5_FEE` |
| 6+ characters | `BASE_FEE` |

Fees are split:

```
registration_fee = annual_fee * (duration_blocks / BLOCKS_PER_YEAR)
protocol_share   = registration_fee * REGISTRY_PROTOCOL_FEE_BPS / 10_000
burn_share       = registration_fee - protocol_share
```

The burn share is burned (deflationary). The protocol share goes to the protocol treasury.

### 7.6 Renewal and Expiry

- Names can be renewed at any time by paying the fee for an additional period.
- Renewal extends `expires_at` from the current expiry (not from the current block), preventing gaps.
- After expiry, a **grace period** of `NAME_GRACE_PERIOD` blocks (default: 2,592,000, ~30 days) allows the owner to renew at the standard rate.
- After the grace period, the name enters a **release auction** — a descending-price Dutch auction starting at `10x` the annual fee and declining linearly to `1x` over `NAME_AUCTION_DURATION` blocks (default: 604,800, ~7 days). This prevents sniping at the exact expiry block.

### 7.7 Route Registry API

The Route Registry system actor exposes the following message handlers:

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `register` | `name`, `actor_address`, `duration_blocks` | `RouteRegistration` | Register a new name |
| `renew` | `name`, `duration_blocks` | `RouteRegistration` | Extend an existing registration |
| `transfer` | `name`, `new_owner` | `RouteRegistration` | Transfer ownership |
| `set_actor` | `name`, `actor_address` | `RouteRegistration` | Point name to a different actor |
| `set_subdomain_policy` | `name`, `policy` | `RouteRegistration` | Change subdomain policy |
| `resolve` | `name` | `Address \| null` | Resolve name to actor address |
| `lookup` | `actor_address` | `[string]` | Reverse lookup: actor → names |

### 7.8 Router Actor Pattern (Recommended)

Because actor code and entitlements are immutable after deployment, binding a domain name directly to an application actor creates an upgradeability constraint: deploying a new version of the application requires calling `set_actor(name, new_address)` (§7.7) to re-point the name, which is a manual operation that can cause brief unavailability.

The **router actor pattern** is a recommended best practice for production actors that expect to evolve. A router actor is a thin, stable proxy:

```python
@actor.handler("http.request")
def handle_http(ctx, envelope):
    # Read the current implementation actor from storage
    impl = storage.get("current_impl")
    if envelope["method"] in ("GET", "HEAD"):
        # Query path: read from the implementation actor's storage directly
        # (requires the router to share storage or proxy via convention)
        return storage.get("cached_response/" + envelope["path"])
    else:
        # Command path: forward to the implementation actor
        ctx.send_message(impl, "http.request", envelope)
        return {"status": 202, "body": "forwarded"}

@actor.handler("set_implementation")
def set_impl(ctx, args):
    assert ctx.sender == storage.get("owner")
    storage.set("current_impl", args["address"])
```

The router actor's code never changes. The owner updates the implementation by sending a `set_implementation` message. This avoids calling `set_actor` on the Route Registry and provides atomic switchover.

> **Not mandated:** This pattern is a recommendation, not a protocol requirement. Simple actors that do not expect to change can bind names directly. The Route Registry's `set_actor` method (§7.7) remains the protocol-level migration mechanism for all actors.

---

## 8. Request Execution

### 8.1 Canonical HTTP Request Envelope

When a Gateway receives an HTTP request for a registered actor, it translates it into a canonical message envelope:

```
HttpRequestEnvelope {
  method:       string,           // HTTP method (uppercase): GET, POST, etc.
  path:         string,           // URL path (no query string, no fragment)
  query:        map<string, array<string>>, // parsed query parameters (repeated keys → array)
  headers:      map<string, array<string>>, // HTTP headers (lowercase keys; repeated headers → array)
  body:         bytes | null,     // request body (POST/PUT/PATCH only)
  host:         string,           // full Host header (for subdomain routing)
  request_id:   string,           // unique request ID (UUID v4, gateway-generated)
}
```

### 8.2 Canonical HTTP Response Envelope

Actors return responses in a canonical envelope:

```
HttpResponseEnvelope {
  status:       u16,              // HTTP status code (100-599)
  headers:      map<string, array<string>>, // response headers (repeated headers → array)
  body:         bytes | null,     // response body
}
```

### 8.3 Query Path (Read-Only, No Consensus)

For `GET` and `HEAD` requests, the Gateway uses the `queryActor` RPC primitive to execute the actor's handler **locally** against the latest committed state. This does not create a transaction and does not go through consensus.

**Execution model:**

1. Gateway calls `queryActor(actor_address, [], "http.request", envelope)` against its local node. (See **Milestone 2 §5.2** for the canonical `queryActor` signature. This CIP passes `"http.request"` as the `selector` argument and the serialized `HttpRequestEnvelope` as the payload. If the Milestone 2 signature evolves, Gateways MUST track that evolution.)
2. The PVM executes the actor's `http.request` selector with the request envelope as input.
3. Execution is **pure**: the handler may read from storage (`get_storage`) but **any side-effecting syscall traps immediately** with `ERR_QUERY_NO_SIDE_EFFECTS` (see §8.3.1 for the exhaustive permitted/trapped syscall tables). Side effects are not silently discarded — the handler *cannot attempt* them.
4. The handler returns an `HttpResponseEnvelope`.
5. Gateway translates the envelope to an HTTP response and returns it to the client.

#### 8.3.1 Query-Path Execution Contract (Normative)

This section fully specifies the execution semantics for query-path requests. This contract is self-contained within CIP-14 and does not depend on external specifications for its normative force.

**Permitted syscalls (MUST allow):**

The PVM MUST allow the following syscalls during query-path execution. These are read-only operations that do not modify actor state, consensus state, or any external observable.

| Syscall | Behavior on query path | Notes |
|---------|----------------------|-------|
| `get_storage(key)` | Returns current value for key from committed state, or `null` if key does not exist. | No trap on missing key. Reads from `storage.kv` volumes only. |
| `self_address()` | Returns the actor's own address. | |
| `block_height()` | Returns the committed block height against which the query executes. | |
| `block_timestamp()` | Returns the timestamp of the committed block. | |
| `caller()` | Returns `null` (no caller on query path — no transaction context). | |
| `entitlement_params(id)` | Returns the actor's own entitlement parameters for the given ID. | Read-only introspection. |

**Trapped syscalls (MUST trap with `ERR_QUERY_NO_SIDE_EFFECTS`):**

The PVM MUST trap — not silently discard, not no-op — on any attempt to invoke the following syscalls. The trap MUST be immediate and MUST abort handler execution with error code `ERR_QUERY_NO_SIDE_EFFECTS`. This is a stronger guarantee than "writes are discarded": the handler cannot *attempt* side effects, preventing actors from behaving differently on query vs. command paths unintentionally.

| Syscall | Why trapped |
|---------|-------------|
| `send_message(target, method, args)` | Would mutate another actor's mailbox. |
| `set_storage(key, value)` | Would mutate the actor's own persistent state. |
| `delete_storage(key)` | Would mutate the actor's own persistent state. |
| `set_timeout(delay, handler, args)` | Would schedule a future execution (side effect on the timer queue). |
| `set_interval(period, handler, args)` | Would schedule recurring execution. |
| `clear_timeout(id)` | Would modify the timer queue. |
| `clear_interval(id)` | Would modify the timer queue. |
| `transfer(target, amount)` | Would mutate token balances. |
| `submit_task(task)` | Would schedule off-chain compute (CIP-2). |
| `create_volume(params)` | Would mutate CIP-9 storage state. |
| `delete_volume(id)` | Would mutate CIP-9 storage state. |
| `emit_event(topic, data)` | Would append to the event log. |

> **Exhaustiveness:** Any syscall not listed in the "Permitted" table above MUST be trapped. New syscalls added to the PVM in future protocol versions default to trapped on the query path unless a future CIP explicitly adds them to the permitted list.

**Cycle cap enforcement:**

- The Gateway MUST enforce the actor's `max_query_cycles` parameter (from the `ingress.http` entitlement).
- Cycle counting uses the same PVM metering as CIP-3 transactional execution.
- If the handler exceeds `max_query_cycles`, the PVM MUST abort execution with `ERR_QUERY_CYCLE_LIMIT`.
- The Gateway MUST NOT charge the actor — query-path execution has no fee. The Gateway absorbs the compute cost.

**Return value format:**

- On success: the handler MUST return a serialized `HttpResponseEnvelope` (§8.2). If the return value does not deserialize to a valid `HttpResponseEnvelope`, the Gateway MUST return HTTP `502 Bad Gateway`.
- On trap (`ERR_QUERY_NO_SIDE_EFFECTS`): the Gateway MUST return HTTP `500 Internal Server Error` with `X-Cowboy-Error: QUERY_SIDE_EFFECT_TRAP`.
- On cycle limit exceeded (`ERR_QUERY_CYCLE_LIMIT`): the Gateway MUST return HTTP `422 Unprocessable Content` with `X-Cowboy-Error: QUERY_CYCLE_LIMIT`.
- On handler panic / unhandled exception: the Gateway MUST return HTTP `500 Internal Server Error` with `X-Cowboy-Error: HANDLER_PANIC`.

**Determinism:**

Query-path execution is deterministic: given the same committed state root, the same `HttpRequestEnvelope` input MUST produce the same `HttpResponseEnvelope` output on every Gateway. This follows from PVM determinism (no network, no filesystem, no randomness, fixed hash seed — CIP-3 §4). Clients can verify query-path responses by re-executing against the same state root on their own node.

**Metering:**

Query-path execution is metered (PVM cycles per CIP-3) to bound Gateway resource consumption. The actor is **not charged** — there is no transaction. The Gateway enforces the actor's `max_query_cycles` parameter. Requests exceeding this limit receive HTTP `422 Unprocessable Content` with an `X-Cowboy-Error: QUERY_CYCLE_LIMIT` header. (422 is used instead of 503 because the failure is actor-scoped — the actor's handler exceeded its declared cycle budget — not a Gateway infrastructure issue.)

**Consistency:**

Query-path responses reflect the state as of the Gateway's latest committed block. There is no guarantee of linearizability across multiple Gateway nodes — two concurrent reads to different Gateways may reflect different block heights. The Gateway MUST include the block height in the response:

```
X-Cowboy-Block: 1234567
```

Clients requiring strict consistency MUST use the command path or include `X-Cowboy-Min-Block` in requests. Gateways MUST reject requests with `X-Cowboy-Min-Block` higher than their current committed height with HTTP `503`.

### 8.4 Command Path (Consensus Required)

For `POST`, `PUT`, `PATCH`, and `DELETE` requests, the Gateway submits a **system-mediated ingress call** through the GatewayRegistry system actor (`0x0012`):

```
Transaction::ActorMessage {
  from:       GATEWAY_ADDRESS,          // Gateway's registered on-chain address
  to:         GATEWAY_REGISTRY_ADDRESS, // 0x0012
  message:    Message {
    method:   "dispatch",
    args:     DispatchArgs {
      target:   actor_address,
      envelope: HttpRequestEnvelope { ... }
    }
  },
  fee:        computed_fee,
  nonce:      gateway_nonce,
  signature:  gateway_signature,
}
```

**System-mediated dispatch:** The `GatewayRegistry.dispatch()` method:

1. **Verifies** that `msg.sender` is a registered, active Gateway (health > 0, stake ≥ `MIN_GATEWAY_STAKE`).
2. **Verifies** that the target actor has the `ingress.http` entitlement.
3. **Forwards** the `HttpRequestEnvelope` to the target actor as a `Message { method: "http.request", args: envelope }` with `ctx.sender` set to `GATEWAY_REGISTRY_ADDRESS` (`0x0012`).
4. If the sender is not a registered Gateway, the dispatch reverts with `ERR_UNAUTHORIZED_GATEWAY`.

This ensures that actors receiving `http.request` messages on the command path can trust that the message originated from a verified Gateway — the system actor mediates all ingress. Actors verify authenticity by checking `ctx.sender == GATEWAY_REGISTRY_ADDRESS` rather than maintaining their own Gateway allowlist.

> **Non-spoofable ingress:** Unlike a plain `ActorMessage`, the system-mediated path prevents arbitrary on-chain accounts from sending `http.request` messages directly to actors. The GatewayRegistry acts as a trusted intermediary, analogous to how the Route Registry mediates name resolution. Direct `ActorMessage` with `method: "http.request"` from non-system senders will have `ctx.sender != GATEWAY_REGISTRY_ADDRESS` and actors MUST reject them.

**Gas payment:** The Gateway pays the transaction fee from its own staked balance. Gateways recover this cost through the serving fee pool (§9.4). Future CIPs may introduce mechanisms for actors or end-users to pre-fund command-path gas (e.g., actor-deposited serving budgets, x402 per-request payment). Until then, Gateways bear the cost and SHOULD enforce rate limits (§9.5) to bound their exposure.

**Response delivery:**

Command-path requests are **asynchronous**. The Gateway returns HTTP `202 Accepted` immediately:

```
HTTP/1.1 202 Accepted
X-Cowboy-Request-Id: abc-123
X-Cowboy-Block: 1234567
```

The client retrieves the result by polling:

```
GET myagent.cowboy.network/_cowboy/requests/abc-123
```

This is a query-path request. The actor stores command-path results in a well-known storage key (`_http/results/{request_id}`) and the Gateway reads it via `queryActor`:

- `200 OK` with the stored `HttpResponseEnvelope` → the command has been executed.
- `202 Accepted` → the transaction is still pending.
- `404 Not Found` → no such request ID.
- `410 Gone` → result expired and was cleaned up.

**Result storage lifecycle:**

Actors are responsible for storing and expiring command-path results. The SDK (CIP-6) MUST provide a helper that automatically stores results at `_http/results/{request_id}` and sets a cleanup timer (default: `RESULT_TTL_BLOCKS`, see §10). Actors MAY override the default TTL. Actors that do not use the SDK helper MUST store results in the same well-known key format to ensure Gateway polling interop:

```python
from cowboy_sdk import http

@http.command("/api/submit")
def handle_submit(ctx, req):
    # Process the command
    data = json.loads(req.body)
    storage.set("submissions/" + data["id"], data)

    # Return response — SDK stores it at _http/results/{request_id}
    return http.Response(201, body=json.dumps({"id": data["id"]}))
```

### 8.5 Actor Handler Convention

Actors implement the `http.request` selector. On the command path, `ctx.sender` is `GATEWAY_REGISTRY_ADDRESS` (`0x0012`) because all ingress is system-mediated via `GatewayRegistry.dispatch()` (§8.4). On the query path, `ctx.sender` is `null` (no transaction context).

```python
from cowboy_sdk import actor, storage
import json

GATEWAY_REGISTRY = "0x0012"

@actor.handler("http.request")
def handle_http(ctx, envelope):
    # On the command path, verify the message came through GatewayRegistry
    if ctx.sender is not None and ctx.sender != GATEWAY_REGISTRY:
        return {"status": 403, "body": "unauthorized: not dispatched via GatewayRegistry"}

    method = envelope["method"]
    path   = envelope["path"]
    host   = envelope["host"]

    # Query-path handler (GET)
    if path == "/api/profile" and method == "GET":
        profile = storage.get("profile")
        return {
            "status": 200,
            "headers": {"content-type": ["application/json"]},
            "body": json.dumps(profile)
        }

    # Command-path handler (POST) — may mutate state
    if path == "/api/profile" and method == "POST":
        data = json.loads(envelope["body"])
        storage.set("profile", data)
        return {
            "status": 200,
            "headers": {"content-type": ["application/json"]},
            "body": json.dumps({"updated": True})
        }

    return {"status": 404, "body": "not found"}
```

> **SDK default:** The SDK (CIP-6) `@http.handler` decorator MUST include the `ctx.sender` verification by default. Actors using the raw `@actor.handler("http.request")` form (as shown above) MUST include the check manually.

**Important**: Handlers MUST NOT assume synchronous off-chain compute. LLM inference, HTTP egress, and other CIP-2 operations are asynchronous. An actor needing LLM output in an HTTP response MUST:

1. On the command path: submit a CIP-2 task, return `202 Accepted`, and store the result when the deferred callback fires.
2. On the query path: read pre-computed results from storage. The query handler cannot trigger off-chain compute.

```python
@actor.handler("http.request")
def handle_http(ctx, envelope):
    if envelope["path"] == "/api/ask" and envelope["method"] == "POST":
        question = json.loads(envelope["body"])["question"]
        request_id = envelope["request_id"]

        # Submit async LLM task — result arrives via deferred callback
        ctx.submit_task(
            task_type="llm_inference",
            request={"prompt": question},
            callback="on_llm_result",
            callback_context={"request_id": request_id}
        )

        # Return 202 — client polls _cowboy/requests/{request_id}
        return {"status": 202, "body": json.dumps({"request_id": request_id})}

@actor.handler("on_llm_result")
def handle_llm_result(ctx, result):
    request_id = ctx.callback_context["request_id"]
    storage.set("_http/results/" + request_id, json.dumps({
        "status": 200,
        "headers": {"content-type": ["application/json"]},
        "body": json.dumps({"answer": result["output"]})
    }))
```

### 8.6 Reserved Paths (`/_cowboy/*`)

The path prefix `/_cowboy/` is reserved for protocol-level endpoints. Gateways MUST intercept these paths **before** dispatching to the actor's `http.request` handler. Actors MUST NOT define handlers that overlap with `/_cowboy/*`.

| Path | Method | Description |
|------|--------|-------------|
| `/_cowboy/requests/{request_id}` | GET | Poll for command-path result (§8.4). |
| `/_cowboy/health` | GET | Gateway health check (returns 200 if the Gateway is operational). |
| `/_cowboy/info` | GET | Actor metadata: address, entitlement params, block height. |

Future CIPs may define additional `/_cowboy/*` endpoints. Actors receiving a request with a `/_cowboy/` path prefix via the `http.request` handler indicates a Gateway implementation bug.

### 8.7 Subdomain Routing Limitations

When an actor uses `ACTOR_MANAGED` subdomain policy (§7.2), all subdomain traffic is routed to the parent actor's `http.request` handler with the full `Host` header. The actor handles subdomain dispatch internally.

**Query-path limitation:** On the query path, subdomain routing is purely internal to the actor handler — the Gateway resolves the top-level name and passes the full `Host` to the actor. This means subdomain delegation to *other* actors is only possible on the command path (where the actor can use `send_message` to forward the request). On the query path, the actor handler must serve all subdomains itself from its own storage.

---

## 9. Gateway Specification

### 9.1 Gateway as a Distinct Ingress Role

A Gateway is a **dedicated ingress node** in the Cowboy network. It is a separate role from Runners (egress-only compute, CIP-10), Validators (consensus), and Relay Nodes (storage, CIP-9).

**Rationale:** Runner containers are explicitly egress-only ("No ingress: Containers cannot listen on ports or accept incoming connections" — CIP-10 §network policies). Relay Nodes are dumb shard storage. Neither role is suited for TLS termination, HTTP routing, or actor query execution. Gateways fill a new operational niche.

**Gateway responsibilities:**

- Participate in DNS resolution for `*.cowboy.network` (authoritative DNS or integration with external DNS).
- Terminate TLS (including certificate management via ACME).
- Maintain a full or pruned copy of committed state (to execute query-path requests locally).
- Route HTTP requests: resolve names via the Route Registry, dispatch to query or command path.
- Submit command-path transactions to the mempool.
- Enforce entitlement parameters (`max_request_bytes`, `max_response_bytes`, `max_query_cycles`).
- Enforce rate limits.

**What Gateways do NOT do:**

- Store CIP-9 shards (that is the Relay Node role).
- Execute CIP-2 off-chain tasks (that is the Runner role).
- Participate in consensus (that is the Validator role).

A single physical node MAY operate as multiple roles simultaneously (e.g., Gateway + Relay Node + Validator), but the protocol treats each role independently.

### 9.2 Gateway Registry

The Gateway Registry is a system actor at reserved address `0x0012`. It manages Gateway registration, staking, and health.

```
GatewayProfile {
  address:          Address,
  stake_amount:     u256,           // CBY staked
  endpoint:         string,         // public endpoint (IP or hostname)
  http_port:        u16,            // port for HTTPS traffic
  last_heartbeat:   BlockHeight,
  health:           u16,            // decays per block, reset on heartbeat
  registered_at:    BlockHeight,
}
```

**Lifecycle:**

- **Register**: Gateway stakes `MIN_GATEWAY_STAKE` CBY and calls `register_gateway(endpoint, http_port)`.
- **Heartbeat**: Gateway calls `heartbeat()` periodically. Health resets to `MAX_GATEWAY_HEALTH` (default: 3,600, ~1 hour at 1 block/sec). Health decays by 1 per block.
- **Removal**: If health reaches 0, the Gateway is removed from the active list.
- **Unstake**: A Gateway may unstake after `GATEWAY_UNSTAKE_DELAY` blocks, provided it is no longer in the active list.

**Gateway Registry API:**

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `register_gateway` | `endpoint`, `http_port` | `GatewayProfile` | Register a new Gateway (requires `MIN_GATEWAY_STAKE`). |
| `heartbeat` | *(none)* | `void` | Reset health to `MAX_GATEWAY_HEALTH`. |
| `unstake` | *(none)* | `void` | Begin unstaking (after `GATEWAY_UNSTAKE_DELAY`). |
| `dispatch` | `target: Address`, `envelope: HttpRequestEnvelope` | `void` | Forward an HTTP request to a target actor. Caller MUST be a registered, active Gateway. Reverts `ERR_UNAUTHORIZED_GATEWAY` otherwise. |
| `is_active_gateway` | `address: Address` | `bool` | Check if an address is a registered, active Gateway. |

### 9.3 Gateway Selection

When a client resolves `*.cowboy.network`, DNS returns the IP addresses of active Gateway nodes. Selection is handled at the DNS level:

- **Anycast**: All Gateways advertise the same IP prefix via BGP. Network routing selects the nearest Gateway.
- **Geo-DNS** (alternative): The authoritative DNS server returns Gateway IPs based on the client's resolver location.

Any Gateway can serve any actor. Gateways are stateless with respect to HTTP routing — they resolve names from the Route Registry and execute queries against their local committed state.

### 9.4 Gateway Incentives

Gateways earn from a **serving fee pool** funded by a portion of name registration and renewal fees:

```
gateway_pool_share = registration_fee * GATEWAY_POOL_BPS / 10_000
```

The serving fee pool is distributed to active Gateways proportional to `stake_amount × uptime_blocks` per epoch. This provides a baseline revenue stream independent of individual request volume.

Future CIPs may introduce per-request payment models (e.g., actor-funded serving budgets, x402 integration).

**Known limitation — incentive misalignment:** Under the serving-fee-pool model, Gateway revenue is proportional to stake × uptime, not request volume. A Gateway that serves millions of requests per epoch earns the same as one that serves zero (assuming equal stake and uptime). This is intentional for the initial deployment — it ensures Gateways are incentivized to *exist* and *stay online* without introducing per-request metering complexity. However, at scale this creates a free-rider problem: Gateways could idle and still earn. A per-request payment model in a follow-on CIP is the expected long-term resolution.

### 9.5 Rate Limiting

Gateways enforce rate limits to prevent abuse:

| Limit | Default | Scope |
|-------|---------|-------|
| `MAX_REQUESTS_PER_SECOND` | 100 | Per actor per Gateway |
| `MAX_CONCURRENT_CONNECTIONS` | 1,000 | Per actor per Gateway |
| `MAX_QUERY_CYCLES` | Per actor entitlement | Per request |
| `MAX_REQUEST_BYTES` | Per actor entitlement | Per request body |
| `MAX_RESPONSE_BYTES` | Per actor entitlement | Per response body |

Actors declare their own limits in their `ingress.http` entitlement params. Gateways enforce the **minimum** of the actor's declared limit and the protocol-wide maximum.

### 9.6 Gateway Authentication

Command-path ingress is **system-mediated**: Gateways call `GatewayRegistry.dispatch()` (§8.4), which verifies the caller is a registered, active Gateway before forwarding the request to the target actor. The actor receives the message with `ctx.sender == GATEWAY_REGISTRY_ADDRESS` (`0x0012`), providing a protocol-level authenticity guarantee without requiring actors to maintain their own Gateway allowlists.

```python
# On the command path, ctx.sender is always the GatewayRegistry system actor
assert ctx.sender == GATEWAY_REGISTRY_ADDRESS  # 0x0012
```

Actors MUST reject `http.request` messages where `ctx.sender != GATEWAY_REGISTRY_ADDRESS` — such messages were not dispatched through the GatewayRegistry and may be spoofed.

On the query path, there is no on-chain transaction, so no Gateway signature. The trust model for query-path responses is equivalent to any RPC node — the client trusts the Gateway to faithfully execute the query. Clients requiring stronger guarantees can run their own node and query directly.

---

## 10. Protocol Constants

```
// Route Registry
ROUTE_REGISTRY_ADDRESS          = 0x0011
GATEWAY_REGISTRY_ADDRESS        = 0x0012
MIN_NAME_LENGTH                 = 3
MAX_NAME_LENGTH                 = 64
NAME_GRACE_PERIOD               = 2_592_000        // ~30 days at 1 block/sec
NAME_AUCTION_DURATION           = 604_800           // ~7 days
BLOCKS_PER_YEAR                 = 31_536_000        // ~365.25 days at 1 block/sec
REGISTRY_PROTOCOL_FEE_BPS       = 1_000             // 10%
GATEWAY_POOL_BPS                = 2_000             // 20% of registration fees to gateway pool

// Gateway
MIN_GATEWAY_STAKE               = <governance-set>
MAX_GATEWAY_HEALTH              = 3_600             // blocks (~1 hour at 1 block/sec)
GATEWAY_UNSTAKE_DELAY           = 604_800           // ~7 days
MAX_REQUESTS_PER_SECOND         = 100               // per actor per gateway
MAX_CONCURRENT_CONNECTIONS      = 1_000             // per actor per gateway

// Command path
RESULT_TTL_BLOCKS               = 3_600             // ~1 hour; actors may override

// Protocol-wide ingress limits (ceilings — actors may set lower)
PROTOCOL_MAX_REQUEST_BYTES      = 10_485_760        // 10 MiB
PROTOCOL_MAX_RESPONSE_BYTES     = 10_485_760        // 10 MiB
PROTOCOL_MAX_QUERY_CYCLES       = 100_000_000       // 100M cycles
```

---

## 11. Rationale

### 11.1 Why Subdomains of `cowboy.network`

A custom TLD (`.cow`, `.cowboy`) would require ICANN accreditation or Handshake integration — significant cost and complexity that would delay the core feature. Subdomains of a standard domain:

- Work today with existing DNS infrastructure and all browsers/resolvers.
- Require no client-side changes.
- Can coexist with a future TLD if one is acquired.
- Follow D3's lesson: DNS compliance first, sovereignty later.

### 11.2 Why Query/Command Split

Without the query/command split, every HTTP request would require a full consensus round (~1 second). This makes simple page loads unacceptably slow. The query path — using the existing `queryActor` RPC primitive — enables sub-100ms responses for `GET` requests by executing against committed state.

The tradeoff is weaker consistency: concurrent reads to different Gateways may reflect slightly different block heights. For most web use cases (reading data, serving pages), this is acceptable. The `X-Cowboy-Min-Block` header provides an opt-in consistency mechanism.

### 11.3 Why `queryActor` (Not "Run the Normal Handler")

Milestone 2 defines `queryActor` as a read-only RPC primitive alongside `invokeActor` (transactional). CIP-14 reuses the `queryActor` RPC shape but defines its own normative execution contract (§8.3.1) — Milestone 2 provides the call signature, while CIP-14 specifies the exhaustive permitted/trapped syscall tables, cycle cap semantics, return value format, and determinism guarantees. Using `queryActor` means:

- The RPC shape is already defined and supported by existing node infrastructure.
- The PVM can enforce side-effect restrictions at the syscall gate per the CIP-14 execution contract (§8.3.1).
- No new execution mode is needed — we reuse existing infrastructure with CIP-14-defined semantics.
- Actors using the same handler for query and command paths get automatic enforcement: side-effecting calls trap immediately on the query path, not silently succeed-then-discard.

### 11.4 Why Gateways Are a Separate Role

CIP-10 explicitly states that Runner containers have "no ingress" — they cannot listen on ports or accept incoming connections. Relay Nodes (CIP-9) are dumb shard storage. Neither role is architecturally suited for TLS termination, HTTP routing, DNS resolution, or actor query execution.

Gateways are the first **ingress** role in the Cowboy network. Operational overlap (a single machine running Gateway + Relay Node + Validator) is fine, but the protocol must treat them as distinct roles with independent staking, health, and incentive models.

### 11.5 Why `ingress.http` (Not a Rust Enum)

The Entitlements Specification defines entitlements as dotted string grants with optional parameters — not as Rust enum variants. `ingress.http` follows this model:

- It fits the existing `EntitlementGrant` schema and CDDL serialization.
- Parameters (`allowlist_methods`, `max_query_cycles`, etc.) use established parameter types.
- It can be extended with additional params in future protocol versions without changing the data model.
- Scheduler matching and enforcement follow the same rules as all other entitlements.

### 11.6 Why Defer CIP-9 Public Assets, CIP-7 Streams, x402, Custom Domains

Each of these is a substantial feature with its own design surface:

- **CIP-9 public assets** require Gateway-side route manifests and static serving logic on top of the `PUBLIC_READ` volume mode already specified in CIP-9 §7.6.
- **CIP-7 stream bridging** is specified by CIP-17 and defines SSE/WebSocket delivery, Gateway-local paid-stream sessions, and wrapped epoch-key retrieval for local client decryption.
- **x402 payment** requires payment verification, serving budget accounting, and integration with an external protocol.
- **Custom domains** require TXT record challenges, ACME certificate management, and periodic reverification.

Each is valuable. None is required for the core primitive — internet-addressable actors — to work. Shipping them incrementally reduces specification risk and allows each to be evaluated independently.

---

## 12. Security Considerations

### 12.1 Query Path Isolation

Query-path execution MUST be fully isolated. A malicious actor handler MUST NOT be able to:

- **Modify state**: Side-effecting syscalls trap with `ERR_QUERY_NO_SIDE_EFFECTS`.
- **Affect other actors**: Execution is sandboxed per CIP-3 PVM guarantees.
- **Consume unbounded resources**: `max_query_cycles` is enforced per-request.
- **Exfiltrate data via side channels**: The PVM is deterministic (no network, no timing, fixed hash seed).

### 12.2 Gateway Misbehavior

Gateways could serve stale state, fabricate responses, or drop requests. Mitigations:

- **Stale state detection**: `X-Cowboy-Block` response header and `X-Cowboy-Min-Block` request header allow clients to detect and reject stale responses.
- **Response verification**: For high-value queries, clients can re-execute the actor handler against their own node's committed state and compare results (deterministic PVM ensures identical output for the same state root).
- **Stake slashing**: Gateways that are provably misbehaving (e.g., signed a command-path transaction but did not submit it) are slashable.

### 12.3 Name Squatting

The tiered pricing model (§7.5) and Dutch auction release mechanism (§7.6) make squatting economically unfavorable:

- Short, premium names have high annual fees.
- Ongoing fees prevent indefinite warehousing.
- The Dutch auction on expiry prevents sniping.

### 12.4 DoS via Command Path

An attacker could flood an actor with command-path requests. Mitigations:

- **Rate limiting**: Gateways enforce per-actor request limits (§9.5).
- **Fee markets**: High load increases the basefee (CIP-3 EIP-1559 mechanism), making spam progressively more expensive.
- **Future: x402 pricing**: A follow-on CIP can add per-request payment requirements for command-path endpoints.

### 12.5 Ingress Authenticity

On the command path, ingress is **system-mediated** through `GatewayRegistry.dispatch()` (§8.4). The GatewayRegistry system actor verifies that the caller is a registered, active Gateway before forwarding the request. Actors receive `ctx.sender == GATEWAY_REGISTRY_ADDRESS` (`0x0012`), providing a protocol-level guarantee that the request originated from a verified Gateway. This eliminates the spoofability of earlier designs where actors received plain `ActorMessage` with `method: "http.request"` from the Gateway's address directly — in that model, any on-chain account could send a fake `http.request` message.

**Residual risk:** An actor that does not check `ctx.sender == GATEWAY_REGISTRY_ADDRESS` would process any `ActorMessage` with `method: "http.request"`, including those sent by arbitrary accounts. The SDK (CIP-6) MUST include the sender check by default in its HTTP handler decorator, so that actors using the SDK are protected without explicit validation.

On the query path, there is no `ctx.sender` (no transaction). The handler runs in a read-only sandbox, so spoofing has no persistent effects.

### 12.6 Cross-Gateway Rate Limit Bypass

Per-actor rate limits (§9.5) are enforced **per Gateway**. An attacker routing requests through N different Gateways can achieve N× the intended rate limit. Mitigations:

- The command path naturally rate-limits via fee markets (CIP-3 EIP-1559 basefee increases under load).
- The query path is the exposure surface. Gateways are stateless with respect to each other, so coordinated rate limiting requires an off-chain protocol (not specified here).
- For high-value actors, the `max_query_cycles` entitlement parameter provides a per-request computation cap that applies regardless of how many Gateways are involved.
- Future CIPs may introduce on-chain rate limiting (e.g., per-actor query budgets that decay per-block).

### 12.7 TLS and Trust

Gateways terminate TLS. The client trusts the Gateway to faithfully relay the actor's response — the same trust model as CDNs (Cloudflare, Fastly). Future CIPs may define response-signing mechanisms for end-to-end verification.

---

## 13. Future Work

The following are explicitly deferred and anticipated as follow-on CIPs:

| Item | Scope | Status |
|------|-------|--------|
| **Public Asset Hosting** | Route manifest for static vs. dynamic paths; Gateway serving static assets from CIP-9 public volumes. | `PUBLIC_READ` volumes are specified in CIP-9 §7.6. Gateway-side route manifests and static serving are deferred to a follow-on CIP. |
| **CIP-16 (Custom Domains and First-Party TLDs)** | TXT record challenge via CIP-2 runner; canonical edge targeting; ACME certificate management; periodic reverification; `.cow` / `.cowboy` support. | Specified by CIP-16. |
| **CIP-17 (Stream Bridge)** | CIP-7 stream -> SSE/WebSocket bridging; Gateway-local paid-stream sessions; wrapped epoch-key retrieval for local client decryption. | Specified by CIP-17. |
| **Payment Gating** | x402 integration for per-request or per-epoch payment; serving budgets; gateway-absorbed mode. | Deferred to a follow-on CIP. |
| **Gateway ↔ Relay Serving** | Protocol for Gateways to fetch `PUBLIC_READ` shard data from Relay Nodes for static asset serving. Includes shard discovery, caching, and CDN-layer optimizations. | Depends on CIP-9 `PUBLIC_READ` (§7.6). Deferred to the Public Asset Hosting CIP. |
| **CORS** | Configurable CORS headers (origins, methods, credentials) for DNS-addressable actors. Actors should be able to declare allowed origins in their manifest or handler. | Deferred to a follow-on CIP. |
| **Protocol Receipt Primitive** | Replace SDK-conventional command result polling (`_http/results/{request_id}`) with a protocol-level transaction receipt/result mechanism. Results would be stored by the execution layer (not the actor) and queryable via a standard RPC method, removing the actor's storage burden and eliminating the dependency on SDK helpers for result lifecycle. | Deferred to a follow-on CIP. Current v1 uses actor-managed storage with SDK MUST-level helpers (§8.4). |

---

## 14. Backwards Compatibility

This CIP introduces new functionality and does not modify existing behavior:

- `ingress.http` is a new entry in the normative entitlement registry. Existing actors and entitlements are unaffected.
- The Route Registry is a new system actor at a previously unused reserved address (`0x0011`).
- The Gateway Registry is a new system actor at a previously unused reserved address (`0x0012`). Its `dispatch()` method provides system-mediated ingress — a new capability that does not affect existing actor messaging.
- The `queryActor` RPC is an existing primitive (Milestone 2 §5.2). This CIP standardizes its use for HTTP query-path execution and provides a full normative execution contract (§8.3.1) but does not change its underlying semantics.
- Actors without `ingress.http` are unaffected — they cannot register names and will not receive HTTP traffic.
- The Gateway role is additive. Existing Runners, Validators, and Relay Nodes are unaffected.

---

## Part II — v2 Revision (canonical; verbatim from former `cip-14-aligned.md`)


<Note>
  **Status:** Draft (alignment revision; non-modifying companion to `cip-14-dns-addressable-actors.md`)
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-04-21
  **Companion to:** `cip-14-dns-addressable-actors.md`
  **Reads with:** Part III of this document
</Note>

## 0. What this document is

A revised, code-aligned draft of CIP-14. **It does not replace the original — read both.** Where the original cites mechanisms that don't exist in `node/`, `runner/`, or `cbfs/` today (e.g. `queryActor`, syscall names like `set_storage` / `set_timeout` / `transfer`), this document substitutes the actual primitive. Where the original under-specifies a security boundary (sender authenticity, randomness on read paths, gateway gas payment vs. stake), this document tightens it. Cross-cutting conventions live in Part III of this document and are referenced rather than restated.

---

## 1. Preconditions

| Amendment | Source | Description |
|-----------|--------|-------------|
| §2.1 | Part III of this document | Add `ingress.http` to `node/types/src/registry.rs::REGISTRY` |
| §5 | Part III of this document | Read-only handler RPC + PVM read-only mode |
| §1 | Part III of this document | Reserve system addresses `0x0C` (ROUTE_REGISTRY), `0x0D` (GATEWAY_REGISTRY), `0x0E` (RECEIPT_REGISTRY) |
| §6 | Part III of this document | Add `system:registry_settlement_config` and `system:gateway_pool_config` under `GOVERNANCE_SYSTEM_ACTOR=0x09` |

If any precondition is unmet, the corresponding section of this CIP does not apply.

---

## 2. Scope

Functionally identical to original §1, with three substitutions:

- The "query path" is implemented via the new `read_handler` RPC + PVM read-only mode defined in Part III of this document §5, not via a hypothetical `queryActor`.
- Command-path results are stored in `RECEIPT_REGISTRY=0x0E`, not in actor KV with per-request cleanup timers.
- Static-asset hosting is deferred to CIP-15-aligned (separate `ingress.static` entitlement).

---

## 3. The `ingress.http` entitlement

### 3.1 Registry entry

See Part III of this document §2.1. Differences from the original CIP-14 §6.1:

- `quota: false` (the manifest has no on-chain quota accumulation; `max_*` params are per-request **limits**).
- All four params are optional; absence implies the protocol defaults below.
- An additional optional param `receipt_ttl_blocks` lets the actor override the default receipt TTL (§8).

### 3.2 Defaults and ceilings

| Param | Default | Hard ceiling |
|---|---|---|
| `allowlist_methods` | `["GET", "HEAD", "POST"]` | none |
| `max_request_bytes` | `1_048_576` | `PROTOCOL_MAX_REQUEST_BYTES = 10_485_760` |
| `max_response_bytes` | `1_048_576` | `PROTOCOL_MAX_RESPONSE_BYTES = 10_485_760` |
| `max_query_cycles` | `10_000_000` | `PROTOCOL_MAX_QUERY_CYCLES = 100_000_000` |
| `receipt_ttl_blocks` | `RECEIPT_TTL_BLOCKS = 3_600` | `RECEIPT_TTL_MAX = 86_400` |

The Gateway enforces `min(actor_param, hard_ceiling)`. The deploy-time validator (`manifest_validate.rs`) rejects unknown methods, zero-value caps, and any param exceeding its hard ceiling.

### 3.3 Enforcement points

- **Deploy-time** (`manifest_validate.rs`): param shape and bounds check.
- **Gateway**: rejects requests to actors lacking `ingress.http`; enforces request/response size; sets `max_cycles` on read-handler RPC calls and on command-path system instructions.

---

## 4. Route Registry (`0x0C`)

### 4.1 Record

```
RouteRegistration {
  name:             string,                 // canonical lowercase, ≤ 64 bytes
  fqdn:             string,                 // computed: name || ".cowboy.network"
  actor_address:    Address,
  owner:            Address,
  registered_at:    BlockHeight,
  expires_at:       BlockHeight,
  subdomain_policy: u8,                     // 0 = OWNER_ONLY (default), 1 = ACTOR_MANAGED, 2 = OPEN
}
```

Storage layout: keyed by canonical `name`; reverse index `actor_address → [name]` maintained on write.

### 4.2 Naming hierarchy

Same hierarchy as original §7.2. **Default subdomain policy changed to `OWNER_ONLY`.**

Rationale: under `ACTOR_MANAGED`, every subdomain GET routes to the parent actor's `http.request` handler and consumes `max_query_cycles`. Combined with §8.7-original (subdomain delegation only on the command path), `ACTOR_MANAGED` as a default turns every subdomain crawl into PVM cycle consumption against the parent actor. Defaulting to `OWNER_ONLY` is safe; opting into `ACTOR_MANAGED` is an informed choice.

### 4.3 Naming constraints

Unchanged from original §7.3 (lowercase alphanumeric + hyphen, 3–64 chars, reserved labels held by governance).

### 4.4 Registration

Same shape as original §7.4. The caller authorization check uses the existing `Action::ActorExecuteHandler(b"register")` model (`node/types/src/entitlement.rs:85`) when the registration is delegated; otherwise the actor itself or its deployer.

### 4.5 Economics (uses existing settlement plumbing)

Annual fee schedule unchanged from original §7.5. The fee split is **not** computed locally in CIP-14; it is read from `system:registry_settlement_config` at `GOVERNANCE_SYSTEM_ACTOR=0x09` (see Part III of this document §6). The default config is:

```
RegistrySettlementConfig {
  burn_percent:     7000,   // 70%
  treasury_percent: 1500,   // 15%
  gateway_percent:  1500,   // 15%  → flows into the gateway pool (§7.4)
}
```

Updates use the existing `UpdateSettlementConfig` opcode with a new `target_pool: REGISTRY` discriminant. No new opcode, no duplicated key paths, no parallel burn/treasury machinery.

### 4.6 Renewal, expiry, auction

Unchanged from original §7.6 (renewal extends from current expiry; grace period; descending Dutch auction on release).

### 4.7 Route Registry API

Same methods as original §7.7. `resolve` and `lookup` execute via the read-handler RPC (no transaction needed) — they read `STATE_GET` against the canonical key.

### 4.8 Two upgrade paths (clarification)

The original §7.8 describes a "router proxy" pattern that hinges on actor immutability. The aligned draft documents both real upgrade paths:

1. **Router proxy** (original §7.8) — never call `set_actor`; route through a stable proxy whose code never changes.
2. **`upgrade_self` syscall** — `node/execution/src/pvm_host.rs:1765`, gated by `sys.upgrade` entitlement. Replaces the actor's `code_hash` in place; storage and address persist.

Pick one per actor. The router pattern is recommended when ABI churn is expected (storage layout migrations); `upgrade_self` is recommended when only handler logic changes. Mixing both within one actor is not supported.

---

## 5. Read-only handler execution (replaces "query path")

The aligned spec uses Part III of this document §5 verbatim. Gateway flow for `GET` / `HEAD`:

1. Resolve `fqdn → actor_address` via `STATE_GET` against `ROUTE_REGISTRY`.
2. Call `POST /actor/{address}/read_handler` with selector `"http.request"` and the serialized `HttpRequestEnvelope` as `payload`. Pass the actor's `max_query_cycles` as `max_cycles`.
3. Node executes via PVM read-only mode. Trapped syscalls — `state_set`, `state_delete`, `send_message`, `call_actor`, `schedule_timer*`, `cancel_timer`, `submit_job`, `token_transfer*`, `create_deferred_tx`, `upgrade_self`, `emit_event`, `randomness` — are listed in Part III of this document §5.3.
4. Response: deserialize as `HttpResponseEnvelope`. If invalid, Gateway returns `502 Bad Gateway` with `X-Cowboy-Error: INVALID_RESPONSE`.
5. Set `X-Cowboy-Block: <block_height>` on the outgoing response.

### 5.1 Error mapping

| Trap / condition | HTTP | `X-Cowboy-Error` |
|---|---|---|
| `ERR_READONLY_VIOLATION` | 500 | `READ_ONLY_VIOLATION` |
| `ERR_QUERY_CYCLE_LIMIT` | 422 | `QUERY_CYCLE_LIMIT` |
| handler panic / unhandled exception | 500 | `HANDLER_PANIC` |
| return value not a valid envelope | 502 | `INVALID_RESPONSE` |
| `min_block` > current committed | 503 | `MIN_BLOCK_NOT_REACHED` |

### 5.2 Consistency

Same as original §8.3 final paragraph. `X-Cowboy-Block` reflects the committed height the read executed against. Clients requiring a floor send `X-Cowboy-Min-Block: N`; if the Gateway's committed height < N, response is `503` with `X-Cowboy-Error: MIN_BLOCK_NOT_REACHED`.

### 5.3 Determinism (corrected)

Two Gateways executing the same `read_handler` request against the same `block_height` MUST return byte-identical bodies. This holds because:

- Read-only PVM execution is pure (no `randomness`, no `emit_event`, no time/network/filesystem).
- `HostContext` ambient values (`block_height`, `block_timestamp`, `self_address`) are committed-state quantities.
- Storage reads return the committed state at the height observed.

The original CIP-14 §11.3 omitted `randomness` from the trapped list, which would have allowed two Gateways to produce different responses for the same height. The aligned draft fixes this in Part III of this document §5.3.

---

## 6. Command path (system-mediated)

### 6.1 `IngressDispatch` system instruction

A new `SystemInstruction` opcode `IngressDispatch` carries:

```
IngressDispatch {
  target:        Address,
  envelope:      HttpRequestEnvelope,
  request_id:    bytes16,
}
```

Sender allowlist: only `GATEWAY_REGISTRY=0x0D`. Dispatch flow (idiom matches the existing `BASEFEE_SYSTEM_ACTOR=0x06` sender check in `node/execution/src/system_instruction.rs`):

1. Verify `tx.sender` is a registered active Gateway via `GATEWAY_REGISTRY.is_active_gateway`.
2. Verify `target` declares `ingress.http`.
3. Verify envelope size ≤ `target`'s `max_request_bytes`.
4. Synthesise an internal `ActorMessage` to `target.http_request` with `ctx.sender = GATEWAY_REGISTRY=0x0D`.
5. After the actor handler returns (or traps), write the result to `RECEIPT_REGISTRY` (§8).

### 6.2 Selector reservation (corrects original §8.5)

The PVM message router treats `"http.request"` as a system-reserved selector: any `send_message` / `call_actor` from a non-system address using this selector is rejected at routing time with `ERR_RESERVED_SELECTOR`. This means an actor receiving an `http.request` message **necessarily** sees `ctx.sender == GATEWAY_REGISTRY=0x0D`.

The original §8.5 placed this guarantee in SDK convention (`@http.handler` decorator includes the `ctx.sender` check by default). That works for SDK users but is unenforceable against custom-PVM-bytecode actors. Selector reservation makes the property a protocol invariant.

### 6.3 Gas payment (separates stake from fees)

The Gateway operating account pays gas as ordinary `tx.from`. Stake (held in `GATEWAY_REGISTRY` per §7.2) is **not** drawn down for fees; it remains lockable collateral subject to slashing.

For actor-funded ingress, the actor grants `Action::UseOwnerBalance` (`node/types/src/entitlement.rs:94`) to the Gateway operating account. The transaction-level fee-payer logic then debits the actor's account instead of the Gateway's. Original §8.4 conflated stake with fee balance; this aligned version uses the existing `UseOwnerBalance` machinery.

### 6.4 Async response

Gateway returns `202 Accepted` immediately:

```
HTTP/1.1 202 Accepted
X-Cowboy-Request-Id: <uuid>
X-Cowboy-Block: <height>
```

Client polls `/_cowboy/requests/{request_id}` (Gateway-intercepted reserved path; served from `RECEIPT_REGISTRY` — see §8.3).

---

## 7. Gateway role

### 7.1 Distinct ingress role

Same as original §9.1. Gateways are a fourth node class alongside Validators, Runners (CIP-2), and Relay Nodes (CIP-9). A single physical machine MAY host multiple roles; the protocol treats each role independently.

### 7.2 GatewayRegistry (`0x0D`)

```
GatewayProfile {
  address:           Address,                     // operating account (also pays gas)
  stake_amount:      u128,
  endpoint:          string,
  http_port:         u16,
  last_heartbeat:    BlockHeight,
  health:            u16,                          // decays per block, reset on heartbeat
  registered_at:     BlockHeight,
}
```

Lifecycle and methods reuse the `RUNNER_REGISTRY` template (`node/runner/src/types.rs`): `register_gateway`, `heartbeat`, `unstake`, `dispatch`, `is_active_gateway`. The aligned draft does not invent new staking semantics.

### 7.3 Selection

Same as original §9.3 (anycast or geo-DNS at the resolver layer; Gateways are stateless w.r.t. routing).

### 7.4 Incentives (uses existing settlement plumbing)

Read from `system:gateway_pool_config` at `0x09`:

```
GatewayPoolConfig {
  weight_stake:   u32,     // basis points; default 5000
  weight_uptime:  u32,     // basis points; default 5000
}
```

Each epoch, the pool (funded by §4.5 `gateway_percent` slice of registration / renewal fees) is distributed to active Gateways pro-rata to:

```
gateway_share = pool * (weight_stake * stake + weight_uptime * uptime_blocks) / Σ(...)
```

Updated via `UpdateSettlementConfig{target_pool=GATEWAY_POOL}`.

**Known limitation (carried from original §9.4):** revenue is uncoupled from request volume. A Gateway that idles still earns. The aligned draft does not fix this — it remains a v1 trade for simplicity. A per-request payment model is future work.

### 7.5 Rate limits, response envelope, reserved paths

Unchanged from original §9.5, §8.1–8.2, §8.6.

---

## 8. Receipt Registry (`0x0E`)

Replaces the original §8.4 SDK-conventional `_http/results/{request_id}` mechanism. Original would exhaust `MAX_TIMERS_PER_ACTOR=1024` on any popular actor (one cleanup timer per pending request).

### 8.1 Record

```
Receipt {
  request_id:    bytes16,                   // UUID v4 from envelope
  target_actor:  Address,
  gateway:       Address,                   // the dispatching Gateway operating account
  status:        u8,                         // 0 = PENDING, 1 = COMPLETED, 2 = FAILED
  envelope:      HttpResponseEnvelope?,     // populated on completion
  created_at:    BlockHeight,
  expires_at:    BlockHeight,                // = created_at + receipt_ttl_blocks
  private:       bool,                       // see §8.4
}
```

### 8.2 Storage and lifecycle

- **Written by the system instruction dispatcher**, not by actor code. After `IngressDispatch` invokes the actor handler:
  - Successful return → `complete_receipt(request_id, envelope)` opcode (sender = current handler context, verified to equal `target_actor`).
  - Handler panic / cycle limit → dispatcher writes `status = FAILED` directly with no envelope.
- **TTL**: `receipt_ttl_blocks` is read from the actor's `ingress.http` entitlement (default `RECEIPT_TTL_BLOCKS = 3_600`, max `RECEIPT_TTL_MAX = 86_400`).
- **Pruning**: a single registry-wide pruning loop scans `expires_at` per block. Per-actor timer budget is **not** consumed.
- **Fee**: receipt write is one extra cell (charged via the dual-cell meter from CIP-3) folded into the command-path tx fee. No separate billing event.

### 8.3 Read API

`GET /_cowboy/requests/{request_id}` is a Gateway-intercepted reserved path (CIP-14 §8.6). Gateway reads via the read-handler RPC against `0x0E`, selector `get_receipt`. Status mapping:

| Receipt state | HTTP response |
|---|---|
| `PENDING` | `202 Accepted` (no body) |
| `COMPLETED` | `200 OK` + stored envelope |
| `FAILED` | `500 Internal Server Error` + `X-Cowboy-Error: HANDLER_FAILED` |
| absent (expired or never created) | `410 Gone` if past `expires_at`; else `404 Not Found` |

### 8.4 Privacy

Receipts are dispatching-Gateway-readable + target-actor-readable by default. To restrict reads (sensitive responses), the actor sets the `private: bool = true` flag in the `HttpResponseEnvelope`. The registry then refuses reads whose caller is not the original `gateway` field of the receipt — preventing other Gateways from polling the result.

### 8.5 Async LLM example (corrected for new receipt model)

```python
from cowboy_sdk import actor, http, jobs

@http.handler("POST", "/api/ask")
def handle_ask(ctx, envelope):
    question = json.loads(envelope.body)["question"]

    ctx.submit_job(
        job_type    = "llm",
        params      = {"prompt": question, "max_tokens": 256},
        callback    = "_on_llm",
        context     = envelope.request_id,        # opaque to scheduler
    )

    # 202 Accepted + Receipt PENDING; client polls /_cowboy/requests/<id>
    return http.Response(202, body='{"status": "pending"}')

@actor.handler("_on_llm")
def on_llm(ctx, result):
    request_id = ctx.callback_context
    ctx.complete_receipt(request_id, http.Response(
        200,
        headers={"content-type": ["application/json"]},
        body=json.dumps({"answer": result["output"]}),
    ))
```

`complete_receipt` is a new SDK convenience that emits the `complete_receipt` system call against `RECEIPT_REGISTRY=0x0E`. The registry verifies `ctx.sender` equals the receipt's `target_actor`.

---

## 9. Actor handler convention

Because `"http.request"` is a system-reserved selector (§6.2), any `ActorMessage` carrying that method **necessarily** came from `GATEWAY_REGISTRY=0x0D`. The original §8.5 SDK guard (`assert ctx.sender == GATEWAY_REGISTRY`) becomes belt-and-suspenders rather than load-bearing.

```python
from cowboy_sdk import http
import json

@http.handler(methods=["GET", "POST"])
def handle(ctx, envelope):
    if envelope.method == "GET" and envelope.path == "/api/profile":
        return http.Response(200,
            headers={"content-type": ["application/json"]},
            body=json.dumps(ctx.storage.get("profile") or {}))

    if envelope.method == "POST" and envelope.path == "/api/profile":
        ctx.storage.set("profile", json.loads(envelope.body))
        return http.Response(200, body='{"updated": true}')

    return http.Response(404, body='not found')
```

Handlers MUST NOT assume synchronous off-chain compute; LLM / HTTP egress remain async via `submit_job` + callback (§8.5).

---

## 10. Constants

```
ROUTE_REGISTRY_ADDRESS              = 0x0C
GATEWAY_REGISTRY_ADDRESS            = 0x0D
RECEIPT_REGISTRY_ADDRESS            = 0x0E

MIN_NAME_LENGTH                     = 3
MAX_NAME_LENGTH                     = 64
NAME_GRACE_PERIOD                   = 2_592_000           // ~30 days
NAME_AUCTION_DURATION               = 604_800             // ~7 days
BLOCKS_PER_YEAR                     = 31_536_000          // ~1 year

MIN_GATEWAY_STAKE                   = <governance-set>
MAX_GATEWAY_HEALTH                  = 3_600               // ~1 hour
GATEWAY_UNSTAKE_DELAY               = 604_800             // ~7 days
MAX_REQUESTS_PER_SECOND             = 100                 // per actor per Gateway
MAX_CONCURRENT_CONNECTIONS          = 1_000               // per actor per Gateway

RECEIPT_TTL_BLOCKS                  = 3_600               // ~1 hour default
RECEIPT_TTL_MAX                     = 86_400              // ~1 day ceiling

PROTOCOL_MAX_REQUEST_BYTES          = 10_485_760          // 10 MiB
PROTOCOL_MAX_RESPONSE_BYTES         = 10_485_760          // 10 MiB
PROTOCOL_MAX_QUERY_CYCLES           = 100_000_000         // 100M cycles
```

`ROUTE_REGISTRY` / `GATEWAY_REGISTRY` / `RECEIPT_REGISTRY` continue the existing `0x01..0x0B` low-byte sequence (Part III of this document §1).

---

## 11. Security delta vs. original

| Threat | Original mitigation | Aligned mitigation |
|---|---|---|
| Spoofed `http.request` from arbitrary on-chain account | SDK `ctx.sender` check (defeated by custom-PVM actors) | Selector `"http.request"` is system-reserved at the PVM router (§6.2); SDK check is redundant |
| Read-path side-effect leak | Trap list using imaginary syscall names (`set_storage`, `set_timeout`, ...) | Real syscall names in Part III of this document §5.3, including the `randomness` trap the original missed |
| Per-request cleanup timers exhausting `MAX_TIMERS_PER_ACTOR=1024` | Not addressed | Receipts owned by `RECEIPT_REGISTRY`; single registry-wide pruning loop (§8.2) |
| Subdomain DoS via `ACTOR_MANAGED` default | Not addressed | Default `subdomain_policy = OWNER_ONLY` (§4.2) |
| Gateway stake conflated with gas balance | Implicit in original §8.4 | Stake is locked collateral; Gateway operating account pays gas; `UseOwnerBalance` enables actor-funded ingress (§6.3) |
| Two Gateways diverging on same `block_height` due to `randomness` | Not addressed | `randomness` trapped on read path (§5.3 + Part III of this document §5.3) |

---

## 12. Backwards compatibility

Additive over the running codebase:

- New entries in `REGISTRY` (Part III of this document §2.1).
- New system actors at unused addresses `0x0C` / `0x0D` / `0x0E`.
- New `SystemInstruction::IngressDispatch` and `complete_receipt` opcodes.
- New `read_handler` RPC + PVM `read_only: bool` mode flag.
- New `target_pool` discriminant on `UpdateSettlementConfig`.

No existing actor manifest, system actor, RPC route, or PVM syscall is modified. Actors without `ingress.http` are unaffected — they cannot register names and will not receive HTTP traffic.

---

## 13. Future work (unchanged from original §13 except)

| Item | Status |
|------|--------|
| Public Asset Hosting (CIP-15) | Specified by `cip-15-public-asset-hosting-v2.md` (Part II) |
| Custom Domains and First-Party TLDs (CIP-16) | Specified by `cip-16-custom-domains-v2.md` (Part II) |
| Stream Bridge (CIP-17) | Out of scope |
| Payment Gating (x402 etc.) | Deferred |
| Per-request Gateway revenue | Deferred (carried-over §7.4 limitation) |
| CORS in dynamic responses | Specified by `cip-15-public-asset-hosting-v2.md` (Part II) §7.3 (precedence reversed: actor-set headers win) |

---

## Part III — Cross-Cutting Conventions (verbatim from former `alignment-conventions.md`)

# Alignment Conventions for CIP-14 / CIP-15 / CIP-16

**Status:** Draft alignment companion (non-modifying)
**Created:** 2026-04-21
**Scope:** Cross-cutting conventions used by Part II of this document, `cip-15-public-asset-hosting-v2.md` (Part II), `cip-16-custom-domains-v2.md` (Part II). Anything that would otherwise be repeated across all three drafts lives here.

This document also enumerates upstream amendments these aligned drafts assume in CIP-2, CIP-3, CIP-5, CIP-9, and the normative entitlement registry — without modifying those source documents. Each `AMEND` item is a precondition: implementing CIP-14/15/16 requires the corresponding amendment to land first.

---

## 1. System actor address allocation

The current low-byte sequence (`node/types/src/constants.rs`, `node/runner/src/system_actors.rs:11-33`) ends at `0x0B` (`RELAY_REGISTRY`). The aligned drafts continue the same dense sequence rather than jumping into the `0x10`+ range used by the original CIP-14 (`0x0011`, `0x0012`).

| Address | Name | Source |
|--------:|------|--------|
| `0x01` | `RUNNER_REGISTRY` | existing |
| `0x02` | `JOB_DISPATCHER` | existing |
| `0x03` | `RESULT_VERIFIER` | existing |
| `0x04` | `SECRETS_MANAGER` | existing |
| `0x05` | `TEE_VERIFIER` | existing |
| `0x06` | `BASEFEE_SYSTEM_ACTOR` (alias `DUAL_BASEFEE`) | existing |
| `0x07` | `ENTITLEMENT_REGISTRY` | existing |
| `0x08` | `TREASURY` | existing |
| `0x09` | `GOVERNANCE_SYSTEM_ACTOR` | existing |
| `0x0A` | `STORAGE_MANAGER` (CIP-9) | existing |
| `0x0B` | `RELAY_REGISTRY` (CIP-9) | existing |
| `0x0C` | `ROUTE_REGISTRY` (CIP-14-aligned §4) | new |
| `0x0D` | `GATEWAY_REGISTRY` (CIP-14-aligned §7) | new |
| `0x0E` | `RECEIPT_REGISTRY` (CIP-14-aligned §8) | new |

Rationale: keeping the sequence dense matches `system_actors.rs` convention and avoids the appearance of a reserved block. Original CIP-14 numbers (`0x0011` / `0x0012`) are renumbered to `0x0C` / `0x0D`.

---

## 2. Entitlement registry amendments (entitlement spec §9)

Adopting the aligned drafts requires three new entries in `node/types/src/registry.rs::REGISTRY`. The registry is lexicographically sorted (enforced by `registry_is_sorted_lexicographically`); insert at the indicated positions.

### 2.1 `ingress.http` (CIP-14)

```rust
RegistryEntry {
    id: "ingress.http",
    inheritable: false,
    attested: false,
    quota: false,
    params: &[
        ParamSchema { name: "allowlist_methods",     param_type: ParamType::StrArray, required: false },
        ParamSchema { name: "max_request_bytes",     param_type: ParamType::Uint,     required: false },
        ParamSchema { name: "max_response_bytes",    param_type: ParamType::Uint,     required: false },
        ParamSchema { name: "max_query_cycles",      param_type: ParamType::Uint,     required: false },
        ParamSchema { name: "receipt_ttl_blocks",    param_type: ParamType::Uint,     required: false },
    ],
},
```

Insertion position: between `http.fetch` and `oracle.llm`.

`quota: false` is intentional and differs from the original CIP-14 §6.1 table. The manifest has no on-chain quota accumulation mechanism: every `max_*` value is a per-request **limit**, not a cumulative quota. The flag matches reality.

### 2.2 `ingress.static` (CIP-15)

```rust
RegistryEntry {
    id: "ingress.static",
    inheritable: false,
    attested: false,
    quota: false,
    params: &[
        ParamSchema { name: "static_volume_names",       param_type: ParamType::StrArray, required: true  },
        ParamSchema { name: "max_static_response_bytes", param_type: ParamType::Uint,     required: false },
        ParamSchema { name: "max_cache_bytes_total",     param_type: ParamType::Uint,     required: false },
    ],
},
```

Insertion position: immediately after `ingress.http`.

This is a **separate** entitlement, not an extension of `ingress.http`. The original CIP-15 §7.1 nests `array<StaticVolumeBinding>` (object array) inside `ingress.http.params.static_volumes` — but `ParamValue` (`node/types/src/manifest.rs:29-34`) only supports `Uint` / `Str` / `StrArray` / `AddressArray`. There is no `Object` variant and adding one would touch manifest serialization, signature digests, and codec round-trip tests for every existing actor.

`static_volume_names: StrArray` lists volume names by ordinal; per-volume cache budgets collapse to a single `max_cache_bytes_total` (Gateway operators may apply local LRU splits — not protocol-enforced).

### 2.3 `dns.attach_external` (CIP-16)

```rust
RegistryEntry {
    id: "dns.attach_external",
    inheritable: false,
    attested: false,
    quota: false,
    params: &[
        ParamSchema { name: "max_bindings", param_type: ParamType::Uint, required: false },
    ],
},
```

Insertion position: between `bridge.subscribe_event` and `econ.hold_balance`.

Required so an actor can be the *target* of `begin_attach_external`. First-party TLD and `cowboy.network` registrations remain governed only by `ingress.http`.

### 2.4 Test update

`registry_has_exactly_14_entries` (`node/types/src/registry.rs:241`) becomes `_has_exactly_17_entries`.

---

## 3. ParamValue limits (binding for spec authors)

`ParamValue` only supports four shapes (`node/types/src/manifest.rs:29-34`). The aligned drafts conform to this without proposing a `ParamValue::Object` variant, because that change would force a coordinated schema migration of every deployed manifest.

**Allowed:**
- a scalar `Uint` (≤ `u64`)
- a single `Str` (≤ 256 bytes)
- a `StrArray` (≤ 64 entries × 256 bytes)
- an `AddressArray` (≤ 64 addresses)

**Disallowed in entitlement params (workaround patterns):**
- nested objects → flatten to multiple entitlements, or two parallel `StrArray`s pairing by index
- booleans → use `Uint` with `0`/`1`
- arrays of structs → use parallel arrays
- maps → store JSON in a `Str` (deploy-time validation cannot recurse into the JSON)

If a parameter does not fit these shapes, the aligned drafts move it out of the manifest entirely (typically into a `STORAGE_MANAGER` record or a separate system-actor table that the actor owner updates by transaction).

---

## 4. System-mediated handler invocation pattern

Several flows in CIP-14-aligned and CIP-16-aligned require an actor to trust that a specific selector was invoked **only** by a specific system actor (e.g. `GATEWAY_REGISTRY=0x0D`, `RESULT_VERIFIER=0x03`). The aligned drafts implement this in the system-instruction dispatcher (`node/execution/src/system_instruction.rs`) rather than relying on SDK-side `ctx.sender` checks.

The pattern (matches the existing `BASEFEE_SYSTEM_ACTOR=0x06` idiom for `UpdateBasefee`):

1. Define a new `SystemInstruction` opcode (e.g. `IngressDispatch`, `ExternalDomainCallback`) carrying `(target_actor, selector, payload)`.
2. The dispatch handler enforces a sender allowlist: only the named system actor address may emit the opcode.
3. The dispatcher synthesises an internal `ActorMessage` whose `ctx.sender` is set to the system actor address. Ordinary `send_message` / `call_actor` from arbitrary accounts cannot reproduce this.
4. The PVM message router additionally **reserves** the corresponding selectors (e.g. `"http.request"`, `"_dns.callback"`). Non-system attempts to send a reserved selector are rejected at routing time with `ERR_RESERVED_SELECTOR`.

This makes ingress / verifier authenticity a protocol property, not an SDK convention.

---

## 5. Read-only handler execution (replaces "queryActor")

CIP-14-aligned introduces a new RPC and a corresponding PVM mode. The current node RPC layer (`node/rpc/src/rpc.rs:140-210`) has no read-only handler invocation today — only REST committed-state reads (`/actor/{addr}/storage`, etc.). The original CIP-14 cites a "Milestone 2 §5.2 `queryActor` primitive" that is not present in the codebase.

### 5.1 RPC

```
POST /actor/{address}/read_handler
{
  "selector":   string,        // method name, e.g. "http.request"
  "payload":    base64,        // serialized arguments
  "max_cycles": u64?,          // overrides actor entitlement up to PROTOCOL_MAX_QUERY_CYCLES
  "min_block":  u64?           // optional consistency floor
}
→ {
  "block_height": u64,
  "result":       base64,      // handler return bytes
  "cycles_used":  u64
}
```

### 5.2 PVM mode

`PvmExecutor::execute_handler` gains a `read_only: bool` argument. When true, the host:

- Returns from `state_get` / `state_scan_prefix` as today.
- Traps on every mutating syscall — see §5.3 for the exhaustive table.
- Returns `Address::ZERO` for `caller` and `None` for `ctx.sender` (no transaction context).

Implementable with one new `HostContext` flag plus per-syscall guard clauses.

### 5.3 Permitted vs. trapped syscalls (definitive table)

Names match `node/execution/src/pvm_host.rs` exactly. This table supersedes the original CIP-14 §8.3.1, which used several syscall names that do not exist in the host (e.g. `set_storage`, `set_timeout`, `transfer`, `create_volume`, `entitlement_params`).

| Syscall | Read-only | Notes |
|---|---|---|
| `state_get` | ✅ permitted | committed state read |
| `state_scan_prefix` | ✅ permitted | committed state read |
| `state_set` | ❌ trapped | mutates own KV |
| `state_delete` | ❌ trapped | mutates own KV |
| `send_message` | ❌ trapped | mutates target mailbox |
| `call_actor` | ❌ trapped | synchronous cross-actor call |
| `schedule_timer` | ❌ trapped | mutates timer queue |
| `schedule_timer_ex` | ❌ trapped | mutates timer queue |
| `extend_timer` | ❌ trapped | mutates timer queue |
| `cancel_timer` | ❌ trapped | mutates timer queue |
| `submit_job` | ❌ trapped | dispatches off-chain task |
| `token_transfer` | ❌ trapped | mutates token balances |
| `token_transfer_from` | ❌ trapped | mutates token balances |
| `create_deferred_tx` | ❌ trapped | mutates deferred tx pool |
| `upgrade_self` | ❌ trapped | replaces actor code |
| `emit_event` | ❌ trapped | appends to event log |
| `randomness` | ❌ trapped | host RNG is consensus-derived; no consensus context on read path |

Ambient context syscalls (`block_height`, `block_timestamp`, `self_address`) are permitted; they read fields from `HostContext` rather than calling the host trait.

Trap code: `ERR_READONLY_VIOLATION` (new). Gateway maps to HTTP `500` with `X-Cowboy-Error: READ_ONLY_VIOLATION`.

The `randomness` trap fixes a bug in the original CIP-14 §11.3 determinism argument — `randomness` is exposed at `pvm_host.rs:1372` and would have allowed read-path divergence between Gateways without this trap.

---

## 6. Settlement / fee distribution reuse

CIP-3 routes burn / treasury / runner-tip splits through `SettlementConfig` stored at `GOVERNANCE_SYSTEM_ACTOR=0x09` under key `system:settlement_config`, updatable via `UpdateSettlementConfig` (opcode 40, sender must be `0x09` per `system_instruction.rs`).

The aligned drafts add **two parallel configs** under the same governance actor (no new system actor required):

- `system:registry_settlement_config` — splits for name registration / renewal fees (CIP-14-aligned §4.5, CIP-16-aligned §4)
- `system:gateway_pool_config` — splits for the Gateway serving fee pool (CIP-14-aligned §7.4)

Both updated via the existing `UpdateSettlementConfig` opcode with a new `target_pool` discriminant (one new enum variant; not a new opcode). This avoids forking burn/treasury routing across multiple ad-hoc paths.

---

## 7. CIP-9 amendments (precondition for CIP-15-aligned)

> **Errata note.** An earlier revision of this section (v1) listed AMEND 9-A through 9-E claiming that `StorageCommitment`, `commit_manifest`, the `volume_id = keccak256(...)` formula, and `Visibility::Public` were missing. They are NOT missing — they are all in CIP-9 today. The corrected, smaller delta list is below; details are in `cip-9-runner-storage-v2.md` (Part II).

CIP-9 already provides the bulk of what CIP-15-aligned needs:

- `StorageCommitment` with `volume_id`, `owner`, `visibility`, `manifest_root`, `status` (CIP-9 §11.1).
- `commit_manifest(cap_token, manifest_root)` system instruction (CIP-9 §12.2).
- `volume_id = keccak256(account_address || volume_name)` (CIP-9 §11.1).
- `Visibility::Public` model for unauthenticated reads via shard metadata (CIP-9 §7.6.3) — note: original CIP-15 used `PUBLIC_READ`; the canonical CIP-9 / CBFS name is `Visibility::Public`.
- Volume status state machine `ACTIVE → GRACE_PERIOD → DELETED → GARBAGE_COLLECTING` (CIP-9 §13).

The remaining genuine gaps are detailed in `cip-9-runner-storage-v2.md` (Part II). Summary:

- **AMEND 9-G** — `GET_MANIFEST` Relay Node RPC (`cip-9-runner-storage-v2.md` (Part II) §2). Direct manifest fetch in one round trip without per-shard reconstruction; required for low-latency Gateway operation against `Visibility::Public` volumes.
- **AMEND 9-H** — `ManifestCommitted` chain event (`cip-9-runner-storage-v2.md` (Part II) §4). Powers Gateway eager cache invalidation; polling remains as a floor.
- **Pin canonical manifest serialization** to `cbfs/manifest/src/merkle.rs` (`cip-9-runner-storage-v2.md` (Part II) §3). Reuses existing CBFS bincode + RFC-6962-style Merkle (avoids the Bitcoin-style duplicate-last-leaf shape).
- **Gateway serving authority** mapped from existing CIP-9 statuses (`cip-9-runner-storage-v2.md` (Part II) §5). Uses existing `ACTIVE` / `GRACE_PERIOD` / `DELETED` / `GARBAGE_COLLECTING` rather than introducing a new `DELINQUENT` status.

(Sequence numbers AMEND 9-A through 9-E are deliberately retired to avoid confusion with the v1 list. AMEND 9-F is unallocated. New CIP-9 amendments resume at AMEND 9-G.)

If the AMEND 9-G / 9-H items have not landed, CIP-15-aligned can still be partially deployed by falling back to indirect manifest fetch (`GET_SHARD` against `__manifest__`) and time-based polling — at the cost of higher per-request latency and slower invalidation.

---

## 8. CIP-2 amendments (precondition for CIP-16-aligned)

The current `runner/src/types.rs::VerifierCheck` enum has no DNS primitive (`runner/src/types.rs:177-201`). CIP-16-aligned uses CIP-2 multi-runner verification with `VerificationMode::MajorityVote` (already implemented per `runner/src/types.rs:215`) and two new check variants:

- **AMEND 2-A** — Add `VerifierCheck::DnsTxtRecordMatch { fqdn: String, expected_value: String, min_resolvers: u32 }`. Verifier runners resolve `fqdn` via `min_resolvers` independent recursive resolvers (operator-configured public list) and report match / mismatch.
- **AMEND 2-B** — Add `VerifierCheck::DnsCnameMatch { fqdn: String, expected_target: String, min_resolvers: u32 }`. Used to check the canonical-edge CNAME.
- **AMEND 2-C** — `JobType::Custom { executor_hash, params }` already exists (`runner/src/types.rs:146-149`). CIP-16-aligned uses it for the verification job; `executor_hash` references a built-in DNS-verification executor whose hash is governance-pinned (`DNS_VERIFIER_EXECUTOR_HASH`).

The original CIP-16 §9.6 prescribes `VerificationMode::Deterministic`, which (per `node/runner/src/types.rs:217` semantics and CLAUDE.md) requires TEE + byte-identical comparison. DNS resolution is not byte-identical across resolvers / cache states; `MajorityVote` is the structurally correct mode.

---

## 9. CIP-5 amendments

None required. The aligned drafts use existing `schedule_timer`, `schedule_timer_ex`, `extend_timer`, `cancel_timer` syscalls without changes. The hard ceiling `MAX_TIMERS_PER_ACTOR=1024` (`node/types/src/constants.rs`) is treated as a constraint that motivates §10 below.

---

## 10. Receipt model (replaces SDK-conventional `_http/results/{request_id}`)

The original CIP-14 §8.4 stores command-path results in actor KV at `_http/results/{request_id}` and registers a per-request cleanup timer. With `MAX_TIMERS_PER_ACTOR = 1024`, a popular API actor exhausts its timer budget within ~1k pending requests.

CIP-14-aligned defines a `RECEIPT_REGISTRY=0x0E` system actor that owns receipt storage and lifetime. See Part II of this document §8 for the full schema. Two key properties:

- Receipts are written by the `IngressDispatch` system instruction post-handler-return, not by actor code. Actors do not consume their own KV or timer budget for receipt management.
- A single registry-wide pruning loop expires receipts via TTL, replacing per-request timers. One timer slot total, not one per pending request.

---

## 11. Whitepaper alignment

These aligned drafts respect every WP principle exercised by CIP-14/15/16. The companion the WP v2 Part III enumerates the principles and the specific clauses that uphold them, including three places where the aligned drafts knowingly bend WP framing (Gateway as a fourth node class, receipt registry as a new state surface, ACME / TLD centralization at v1).
