---
title: "CIP-15: Gateway Implementation Guide (r2)"
description: A build order and concrete implementation plan for shipping CIP-15 (verb-aware HTTP routing with per-route payment) on the Cowboy Gateway
icon: hammer
---

<Note>
  **Companion to:** [CIP-15 v2: Public Asset Hosting](./cip-15-public-asset-hosting-v2). This is not a normative CIP; it is an implementation handbook.
  **Audience:** Gateway implementers
  **Status:** Living document
  **Updated:** 2026-05-11 (r2)
</Note>

> **Revision history**
>
> - **r2 (2026-05-11)** — §2.2 reference to a non-existent CIP-15 §8.12 replaced with concrete pointer to CIP-14 v2.r2 Part II §5 (`read_handler` RPC) and §9 open-question item promoted: the `GET_STATE`-style verifiable KV-read RPC required by §2.3 is **not yet specified by any CIP and not yet present in `node/rpc/src/rpc.rs`**. Implementers must coordinate with the runtime team or start a sibling CIP. §9 open-questions list updated. Title in §13 corrected to "CIP-18: Payments" (was "CIP-18: Payment Gating", which was the file's earlier title).
> - **r1 (initial)** — 6-phase build order published.

This document is a build order. The CIP describes *what* the system does; this describes *what to write*, in what order, and what to test. Read alongside [CIP-14 v2: DNS-Addressable Actors](./cip-14-dns-addressable-actors-v2) and [CIP-18: Payments](./cip-18-payments).

---

## 0. Mental model

The Gateway is a stateless HTTP server with two caches:

```
                                          ┌─ per-volume metadata cache (CIP-15 §8.2)
                          ┌─ caches  ◄────┤  keyed: volume_id
                          │                └─ object cache (LRU, bounded)
       HTTP request ──►   GW ──┐
                          │    └─► state-read RPC (Runners)
                          │        manifest+shard RPCs (Relay Nodes)
                          │
                          └─ per-actor routes cache (CIP-15 §8.2)
                             keyed: actor_address
```

For every incoming request the Gateway:

1. Resolves the actor from the host header (CIP-14 Route Registry — already implemented).
2. Looks up the cached `Routes` for that actor.
3. Picks a `(verb, path)` winner (CIP-15 §6.6).
4. Dispatches: serve from a CBFS volume (static), or invoke a named handler via existing CIP-14 RPC (dynamic). Optionally gates on payment per CIP-18.

Everything else — caching, fetching, verifying — is plumbing around those four steps.

---

## 1. Build order

Implement in this order. Each phase is independently shippable.

| Phase | Scope | Depends on |
|---|---|---|
| **P1** | Routes fetch + method-target dispatch | CIP-14 (existing) |
| **P2** | Static volume serving (Volume targets) | CIP-9 GET_MANIFEST/GET_SHARD |
| **P3** | Runtime mutability (state_root re-poll) | P1 |
| **P4** | Payment gating (`pays = caller`) | CIP-18 |
| **P5** | CORS, conditional requests, compression | P2 |
| **P6** | Hedging, parallel fetch, optimization | P2 |

P1 alone replaces the current "everything goes to `http.request`" CIP-14 behavior with verb-aware routing. Worth shipping that first and proving the core loop end-to-end before tackling static.

---

## 2. Phase 1 — Routes fetch + method dispatch

### 2.1 New types

```
RoutesValue   = CBOR-encoded `Routes` (CIP-15 §6.2)
RoutesCache   = LRU<actor_address, ActorRoutesCache>
ActorRoutesCache {
  routes:               Routes,
  state_root:           bytes32,
  last_verified_block:  BlockHeight,
}
```

### 2.2 New RPC: `GET_STATE`

**Status (r2): not yet specified by any CIP, not yet implemented.** The previous draft of this section pointed to a "CIP-15 §8.12" that does not exist in CIP-15 v2. Inspection of `node/rpc/src/rpc.rs:168-213` confirms the routes today are only:

- `/actor/{address}` — committed-state read of actor code + storage + manifest (no Merkle proof)
- `/actors/{address}/storage` — paginated KV read (no Merkle proof)
- read-only handler invocation: `read_handler` per CIP-14 v2.r2 Part II §5 (also not yet implemented)

What the Gateway needs is a verifiable single-KV read against a Runner:

```
GET_STATE(actor_address, key) -> {
    value: bytes,
    proof: MerkleProof,   // path from `key/value` to actor state_root
    state_root: bytes32,
    block_height: u64,
}
```

Before writing the Gateway side:

- Coordinate with the runtime team. Either start a sibling CIP (e.g. an extension to CIP-14 v2 or a fresh `CIP-15.1 / CIP-17: Verifiable State Read`), or get `GET_STATE` added to the CIP-14 v2 Part II §5 read-handler RPC family. It is cheap — a single Merkle path proof against the actor's state root, leveraging the same MPT primitives CIP-4 describes.
- Track this as a hard precondition for shipping Phase 1.

Until `GET_STATE` lands, you can prototype with an unverified read against a trusted Runner — but do NOT ship without the proof check. The whole security model rests on it.

### 2.3 Routes fetch loop

```
for each actor with active traffic:
  every MANIFEST_POLL_INTERVAL blocks:
    on_chain_root = chain.get_account(actor).state_root
    if on_chain_root == cache[actor].state_root:
      continue                       # nothing changed
    resp = runner.GET_STATE(actor, "__cowboy/routes")
    if not verify_merkle_proof(resp.value, resp.proof, on_chain_root):
      try another runner; if all fail, log warning, keep stale cache
      continue
    routes = cbor.decode(resp.value)
    if not validate(routes):         # CIP-15 §6.8
      log warning; fall back to all-CIP-14 dispatch
      continue
    cache[actor] = ActorRoutesCache(routes, on_chain_root, current_block)
```

Notes:

- The poll interval is shared with the volume `manifest_root` poll — one polling task can refresh both anchors per actor.
- Empty value (actor never wrote `__cowboy/routes`) → not an error. Cache an empty Routes; dispatch falls back to CIP-14 unchanged. Existing actors continue to work.
- Failures are sticky in the worst sense: if validation fails, the previously-cached table stays in use. That's the safe behavior.

### 2.4 The resolver

This is the function that gets called on every request:

```python
def resolve(actor, verb, path) -> Resolution:
    # 1. Reserved
    if path.startswith("/_cowboy/"):
        return Resolution.cowboy_intercepted()

    # 2. Cached routes (or empty)
    routes = cache[actor].routes if actor in cache else None
    if routes is None or len(routes.routes) == 0:
        return Resolution.cip14_fallback()  # dispatch to http.request handler

    # 3. Filter enabled, match (verb, path)
    candidates = [r for r in routes.routes
                  if r.enabled
                  and (r.verb == verb or r.verb == "ANY")
                  and path_matches(r.path, path)]

    if not candidates:
        return Resolution.not_found_404()

    # 4. Tie-break: priority desc, longest concrete prefix, non-ANY verb, Method > Volume
    winner = max(candidates, key=lambda r: (
        r.priority,
        concrete_prefix_length(r.path),
        0 if r.verb == "ANY" else 1,
        0 if r.target.kind == "volume" else 1,
    ))

    return Resolution.route(winner, extract_path_params(winner.path, path))
```

Path matching: support literal segments, `{name}` (single segment, captured), and `*name` / `*` (zero+ segments, captured if named).

### 2.5 Dispatch — Method target, `pays = actor`

This is the "easy" path for P1: it reuses CIP-14 dispatch end-to-end. The only change is the handler name comes from the matched route, not always `"http.request"`:

```python
def dispatch_method(actor, route, request, path_params):
    envelope = HttpRequestEnvelope(
        method=request.method,
        path=request.path,
        path_params=path_params,           # populated by the Gateway resolver
        query=request.query,
        headers=request.headers,
        body=request.body,
        host=request.host,
        request_id=request.request_id,
    )

    if request.method in ("GET", "HEAD"):
        return runner.read_handler(actor, route.target.name, envelope)   # CIP-14 query path
    else:
        return runner.send_command(actor, route.target.name, envelope)   # CIP-14 command path
```

The runner-side change required: handlers used to receive everything on `http.request`. Now the Gateway sends to `route.target.name`. Confirm with the runtime team that named-handler dispatch on the CIP-14 query and command paths is supported. (It already should be — that's how non-HTTP message handlers work.)

### 2.6 Tests for P1

Unit:

- Resolver: every branch in CIP-15 §6.6 — priority ties, longest-prefix ties, ANY vs concrete verb, Method-vs-Volume tie, empty routes table, reserved paths.
- Validation: malformed CBOR, oversized table, unknown volume, missing price for `caller`, invalid status codes, reserved path prefix.
- Path matching: literals, `{id}`, `*rest`, edge cases (trailing slashes, empty segments, encoded chars).

Integration:

- Deploy a sample actor with two routes: `GET /a → method_a`, `POST /b → method_b`.
- `curl GET /a` → handler `method_a` runs.
- `curl POST /b` → handler `method_b` runs.
- `curl GET /unknown` → 404.
- Mutate the routes table at runtime, wait one poll interval, verify dispatch follows the new table.
- Have the actor return zero routes; verify CIP-14 fallback (everything hits `http.request`).

End-to-end:

- One real actor, one Gateway, one Runner. Run the resolver under load (e.g., `wrk -t4 -c100 -d30s http://actor.cowboy.network/api/foo`). Watch for cache miss thrashing if the poll interval is wrong.

---

## 3. Phase 2 — Static volume serving (Volume targets)

The static-asset serving path is independent of the routes-resolver — once a `Volume` target wins resolution, the Gateway's job is just to fetch and serve the object.

### 3.1 Components

- Per-volume metadata cache (CIP-15 §8.2 Layer 1a): manifest, content_types, cache_config, cors_config.
- Object cache (Layer 2): bounded LRU, keyed by `(volume_id, object_path)`.
- `manifest_root` polling for invalidation (CIP-15 §8.3).
- `GET_MANIFEST` + `GET_SHARD` RPCs (CIP-15 §8.4).
- Reed-Solomon reconstruction + BLAKE3 integrity chain (CIP-15 §8.5–§8.6).
- Hedged parallel fetch (CIP-15 §8.7).

### 3.2 Volume-target dispatch

```python
def dispatch_volume(actor, route, request):
    if request.method not in ("GET", "HEAD"):
        return Response(status=405, body="Method Not Allowed")

    volume_path = resolve_volume_path(route.target, request.path)  # CIP-15 §6.7
    obj = get_object(route.target.volume_name, volume_path)        # cache or fetch
    if obj is None:
        if route.target.fallback:
            obj = get_object(route.target.volume_name, route.target.fallback)
            if obj is None:
                return Response(status=404)
            return serve(obj, status=route.target.fallback_status)
        return Response(status=404)

    return serve(obj, status=200)
```

`get_object` is the existing P2 plumbing — cache check, manifest lookup, parallel shard fetch, RS reconstruct, integrity verify. No changes needed there.

### 3.3 Tests for P2

- Volume mount serves from the right `volume_name` and applies `strip_prefix` / `volume_path_prefix` correctly.
- Fallback path (SPA case): `GET /about` with no `about` object → serves `index.html` with status 200.
- 404 fallback: `GET /missing.png` with no fallback configured → 404.
- 405 on `POST /assets/foo.png` (volume route, non-GET).
- Integrity chain: corrupted shard → fetch from another node and verify; if all corrupt → 502.

---

## 4. Phase 3 — Runtime mutability

This is mostly free once P1 is in. The poll loop already detects state_root changes and reloads. Two extra concerns:

### 4.1 Rate-limit enforcement

The runtime — not the Gateway — enforces `MIN_ROUTES_UPDATE_INTERVAL_BLOCKS`. The Gateway only sees the result (the next valid state_root). But the Gateway should:

- Log routes-table churn (rate of state_root changes per actor) for ops visibility.
- Treat rapid back-to-back updates as expected noise; don't add Gateway-side rate limits.

### 4.2 Validation-rejected updates

If an actor writes a malformed routes value:

- Validation fails (§6.8).
- The Gateway logs a warning, **keeps the previously-cached table**, and continues serving from it.
- Next poll: if the actor fixes it, replace. If not, keep serving stale.

This is fail-closed — the Gateway never silently degrades to "no routes" because of a bad write.

### 4.3 SDK helpers vs wholesale rewrites

The Gateway doesn't distinguish: any write that advances the state_root and changes `__cowboy/routes` is just "a new table." The narrow mutators (§6.9) are an SDK convenience. From the Gateway's perspective they're all the same.

---

## 5. Phase 4 — `pays = caller` (CIP-18)

CIP-18 may not be ready when this CIP ships. That's fine: the schema lands now, enforcement waits. Two options:

**Option A: Accept the schema, reject the requests.** If a route has `pays = "caller"` and CIP-18 isn't implemented, the Gateway returns `501 Not Implemented` with `X-Cowboy-Reason: cip18-required`. Document this clearly so actor authors don't ship paid endpoints expecting them to work.

**Option B: Validate-only.** The Gateway accepts schemas with `pays = "caller"` but treats them as if they were `pays = "actor"` until CIP-18 lands. This is more forgiving but lets actors ship endpoints that quietly behave differently than declared. **Don't do this.**

Once CIP-18 lands, the Method-target dispatch path adds:

```python
def dispatch_method(actor, route, request, path_params):
    if route.pays == "caller":
        proof = extract_payment_proof(request.headers)        # CIP-18
        if proof is None or not verify_payment(proof, route.price):
            return cip18_402_response(route.price)            # CIP-18
    # ... existing dispatch
```

Receipt accounting, refunds for failed handler runs, and so on are all CIP-18 concerns.

---

## 6. Phase 5 — CORS, conditional requests, compression

Per CIP-15 §9 / §8.9 / §8.10. Note the precedence rule in §9.4: for `Method`-target routes, actor-set `Access-Control-*` headers in the response envelope are authoritative — the Gateway only fills in CORS from `cors_config` when the actor sets none. For `Volume`-target routes, the Gateway applies `cors_config` rules; the default permissive CORS policy applies when no `_meta/cors.json` exists.

---

## 7. Phase 6 — Optimization

After correctness:

- Hedged parallel shard fetch (CIP-15 §8.7).
- Compressed variants in the cache.
- Cache warming on actor registration.
- Coalescing concurrent requests for the same object.

None of this is on the critical path for shipping this CIP.

---

## 8. Operational surface

What ops needs to see:

- Per-Gateway: cache hit ratio (object, metadata, routes), cache size, evictions.
- Per-actor: requests/s, dispatch breakdown (volume vs method, by verb), routes-table state_root churn rate.
- Per-route: hit count, p50/p95/p99 latency.
- Errors: validation failures (per actor), proof failures, 502s from integrity failures.

The `X-Cowboy-Source` header (`"static"` or `"dynamic"`) on responses already gives clients a debugging signal.

---

## 9. Open questions (confirm before merging the PR)

1. **`GET_STATE` RPC.** Confirmed (r2) as **not specified and not implemented** — see §2.2. Either start a sibling CIP or extend CIP-14 v2 Part II §5 `read_handler` family. Blocks Phase 1 shipping with full proof-checked routes cache.
2. **Path-param delivery.** This CIP specifies the Gateway extracts `path_params` and passes them in the `HttpRequestEnvelope`. Confirm with the runtime team that the envelope schema can carry them, or extend it.
3. **Named-handler dispatch.** Confirm the runner-side dispatcher accepts arbitrary handler names on the CIP-14 query and command paths (it should — that's how non-HTTP messages work — but verify).
4. **CIP-18 readiness.** r2 elevates CIP-18 from Companion to Requires for Phase 4 — track CIP-18 r2 PaymentGate `0x11` deployment. Ship Phase 4 only after CIP-18 settles.
5. **Rollout.** Is there an existing actor that's a good first canary? `17-hn-feed`? A toy actor in a devnet?

---

## 10. What success looks like

- Existing actors keep working with zero changes.
- Actors that write a `__cowboy/routes` value get verb-aware dispatch + named handlers + per-route payment policy without redeploys.
- Static asset serving meets CDN-class latency for cache hits (sub-10ms p99 from a warm Gateway).
- Routes updates land in Gateway caches within 6 seconds of commit.
- A FastAPI/axum/Hono developer can read a CIP-15 actor and immediately understand what it does.
