---
title: "CIP-14: DNS-Addressable Actors"
description: Ingress routing for actors via DNS naming, a dedicated Gateway role, on-chain route registry, and canonical HTTP request/response envelope with explicit query and command paths
icon: globe
---

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
