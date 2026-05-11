---
title: "CIP-15: Public Asset Hosting (v2.r2)"
description: Code-aligned v2 — separates ingress.static, conforms terminology to CIP-9 / CBFS, fixes routing & CORS precedence, ties serving to existing CIP-9 status; r2 corrects Merkle description and shifts system actor address segment +1
---

# CIP-15 v2

> **Versioning.** This is v2 of CIP-15. v1 is the canonical document `cip-15-public-asset-hosting.md` (preserved verbatim as Part I). v2 = v1 + the alignment revision (Part II) + the cross-cutting conventions (Part III).
>
> **Conflict rule:** Part II is canonical wherever it contradicts Part I. CIP-15 v2 also depends on `cip-9-runner-storage-v2.md` Part II for the small set of Relay-Node / event additions.
>
> **Revision history**
>
> - **r2 (2026-05-11)** — Two corrections grounded in current code:
>   1. **CBFS Merkle algorithm description corrected** — `cbfs/manifest/src/merkle.rs:42-44` uses **power-of-2 padded BLAKE3 binary Merkle** (`leaves.resize(padded_len, ContentHash([0u8;32]))` then standard balanced bottom-up), **not** RFC-6962 imbalanced-tree promotion. Earlier v2 changelog and Part II §3 claim of "RFC-6962-style imbalanced-tree promotion" was incorrect — the algorithm pads to the next power of two with zero-hashes and then forms a perfect binary tree. Both schemes avoid CVE-2012-2459 (duplicate-last-leaf), but they are different schemes. Part II §3 + cross references rewritten.
>   2. **System actor address shifts paired with CIP-14 v2.r2** — `0x0C = SESSION_ACTOR` (code at `system_actors.rs:35`); v2 sequence shifted +1: ROUTE_REGISTRY `0x0D` / GATEWAY_REGISTRY `0x0E` / RECEIPT_REGISTRY `0x0F` / CONTAINER_REGISTRY `0x10` / PAYMENT_GATE `0x11` (Part III §1 table updated).
> - **r1 (2026-04-21)** — Initial v2 alignment round 6 (ingress.static, route manifest on-chain, status mapping, etc.).
>
> **Summary of v2 changes**
>
> - **`ingress.static` is a separate entitlement**, not nested params under `ingress.http` (the latter would require a `ParamValue::Object` variant the codec does not have).
> - **CBFS terminology** — `Visibility::Public` (canonical name in CIP-9 §7.6 and `cbfs/types/src/lib.rs:126`); `volume_id = keccak256(account || name)` reused from CIP-9 §11.1.
> - **Strict route priority ordering** — `min(dynamic_routes.priority) > max(static_routes.priority)` enforced at `update_route_manifest` validation. Prevents static fallback from silently shadowing dynamic API on a priority typo.
> - **Route manifest moved on-chain** to `STORAGE_MANAGER`, keyed by `actor_address` — decouples routing lifecycle from any single volume.
> - **`X-Cowboy-Manifest-Root` response header** alongside `X-Cowboy-Block` — closes the dual-versioning gap.
> - **CORS precedence reversed for dynamic routes** — actor-set `Access-Control-*` headers in the response envelope win; `cors_config` is fallback.
> - **Gateway serving authority tied to existing CIP-9 status states** (`ACTIVE` / `GRACE_PERIOD` / `DELETED` / `GARBAGE_COLLECTING`) — no new `DELINQUENT` status.
> - **CBFS Merkle reused** (**power-of-2 padded BLAKE3 binary Merkle** per `cbfs/manifest/src/merkle.rs` — pad to next power of two with zero-hash leaves, then balanced bottom-up; **not** Bitcoin-style duplicate-last-leaf, CVE-2012-2459).
> - **Errata.** An earlier draft of this v2 over-claimed CIP-9 was missing `StorageCommitment` / `commit_manifest` / `volume_id` formula. They are not — see `cip-9-runner-storage-v2.md` Part II §9.

---

## Part I — v1 Specification (verbatim from `cip-15-public-asset-hosting.md`)


<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-03-07
  **Requires:** CIP-9 (Runner Attached Storage), CIP-14 (DNS-Addressable Actors)
</Note>

## 1. Abstract

This proposal defines **Public Asset Hosting** — a system for serving static files (HTML, CSS, JavaScript, images, fonts) from CIP-9 public volumes through the CIP-14 Gateway network. The core primitive is a **route manifest** that tells Gateways which URL paths serve static assets from a volume and which paths dispatch to the actor's `http.request` handler.

This CIP specifies:

- A route manifest schema (`_meta/routes.json`) stored in the CIP-9 public volume.
- A route resolution algorithm that determines static vs. dynamic dispatch per request.
- An extension to the `ingress.http` entitlement with `static_volumes` and `max_static_response_bytes` parameters.
- A Gateway-to-Relay-Node fetch protocol for retrieving, reconstructing, caching, and serving public volume objects.
- A CORS configuration schema (`_meta/cors.json`) with sensible defaults for static assets.
- Cache invalidation driven by on-chain `manifest_root` changes.

This CIP intentionally defers the following to future CIPs:

- Pre-compressed asset variants (`.gz`, `.br` files in the volume).
- Small object inlining (bypassing erasure coding for tiny files).
- Image optimization or resizing at the Gateway edge.
- Range requests and chunked transfer for streaming large assets.

---

## 2. Motivation

CIP-14 makes actors reachable via HTTP. Every request — even a simple `GET /style.css` — executes the actor's `http.request` handler through the `queryActor` RPC, consuming PVM cycles and Gateway compute. For a typical web application, 80–95% of HTTP requests are for static assets that never change between deployments: bundled JavaScript, CSS stylesheets, images, fonts, favicon.

This is wasteful. The actor's handler receives the request, reads the file from storage, wraps it in an `HttpResponseEnvelope`, and returns it. The Gateway deserializes the envelope and sends the bytes. Every step is unnecessary — the file is already sitting on Relay Nodes in a public volume, ready to serve.

Public asset hosting eliminates the actor from the static serving path:

1. **No PVM cycles**: Static assets are served directly from the Gateway's cache or reconstructed from Relay Node shards. The actor handler is never invoked.
2. **No query-path metering**: The actor's `max_query_cycles` budget is preserved for dynamic requests that actually need computation.
3. **CDN-like performance**: Gateways cache reconstructed objects locally, serve conditional requests via ETags, and set proper `Cache-Control` headers — all without actor involvement.
4. **Atomic deploys**: The route manifest lives in the same CIP-9 volume as the assets. A single `commit_manifest` transaction atomically updates both the files and the routing rules.

---

## 3. Design Goals

- Serve static assets without invoking the actor's `http.request` handler or consuming PVM cycles.
- Let actors declare which URL paths are static and which are dynamic, with explicit priority ordering.
- Support SPA (single-page application) fallback patterns (`index.html` for all non-file paths).
- Reuse CIP-9's existing `_meta/content_types.json` and `_meta/cache_config.json` for HTTP header generation.
- Provide CORS headers for static assets by default (browsers need them).
- Define the Gateway-to-Relay-Node fetch protocol: shard retrieval, reconstruction, integrity verification, and caching.
- Extend the existing `ingress.http` entitlement — no new entitlement type.

## 4. Non-Goals

- Replacing the actor's `http.request` handler for dynamic requests. Static and dynamic coexist; the route manifest controls which path goes where.
- Server-side rendering. Actors that need SSR use the dynamic route path.
- Pre-compressed asset variants (`.gz`, `.br`). v1 uses on-the-fly compression.
- Image optimization, resizing, or transformation at the Gateway edge.
- Range requests (`Range` header) for partial content delivery.
- Payment gating for static assets. Public volume assets are free to access.
- Custom domain support. CIP-15 works with `*.cowboy.network` subdomains via CIP-14's Route Registry.

---

## 5. Definitions

- **Static route**: A URL path prefix that the Gateway serves directly from a CIP-9 public volume, without invoking the actor's handler.
- **Dynamic route**: A URL path prefix that the Gateway dispatches to the actor's `http.request` handler via the normal CIP-14 query or command path.
- **Route manifest**: A JSON document (`_meta/routes.json`) in a CIP-9 public volume that declares static and dynamic routes with priority ordering.
- **Object**: A single file stored in a CIP-9 volume (e.g., `assets/logo.png`). Objects are erasure-coded into shards and distributed across Relay Nodes.
- **Shard**: One piece of an erasure-coded object, stored on a single Relay Node. Any K of K+M shards are sufficient to reconstruct the original object.

---

## 6. Route Manifest

### 6.1 Location and Rationale

The route manifest is stored at `_meta/routes.json` within a CIP-9 public volume. This location was chosen over alternatives:

- **Actor KV storage** would require a `queryActor` call on every request just to determine whether a path is static — defeating the purpose of avoiding actor execution.
- **Entitlement parameters** are immutable after deployment (CIP-2), so changing routes would require redeploying the actor. Website route structures change frequently.
- **Convention-based** (e.g., `/static/*` always from volume) is too rigid. A path like `/app.js` might be static in one actor and dynamic in another.

Storing the manifest in the volume ensures it updates atomically with the assets via `commit_manifest`. When a developer deploys new assets, the route manifest changes in the same transaction.

### 6.2 Schema

```
RouteManifest {
  version:            u8,                    // schema version (1 for this CIP)
  static_routes:      list<StaticRoute>,     // paths served from the volume
  dynamic_routes:     list<DynamicRoute>,     // paths forwarded to actor handler
  default_behavior:   string                 // "dynamic" | "static"
}

StaticRoute {
  volume_name:        string,     // which static_volumes binding to serve from
  path_prefix:        string,     // URL path prefix to match (e.g., "/", "/assets/")
  strip_prefix:       bool,       // if true, strip the matched prefix before volume lookup
  volume_path_prefix: string,     // prefix prepended to the remaining path for volume lookup
  priority:           u16,        // higher value wins when multiple routes match
  fallback:           string?,    // object path to serve when requested path not found in volume
  fallback_status:    u16         // HTTP status for fallback response (200 for SPA, 404 for not-found page)
}

DynamicRoute {
  path_prefix:        string,     // URL path prefix to match
  priority:           u16         // higher value wins
}
```

### 6.3 Example: Full-Stack Application (Single Volume)

```json
{
  "version": 1,
  "static_routes": [
    {
      "volume_name": "web-assets",
      "path_prefix": "/assets/",
      "strip_prefix": false,
      "volume_path_prefix": "assets/",
      "priority": 10,
      "fallback": null,
      "fallback_status": 404
    },
    {
      "volume_name": "web-assets",
      "path_prefix": "/",
      "strip_prefix": false,
      "volume_path_prefix": "",
      "priority": 0,
      "fallback": "index.html",
      "fallback_status": 200
    }
  ],
  "dynamic_routes": [
    {
      "path_prefix": "/api/",
      "priority": 100
    }
  ],
  "default_behavior": "static"
}
```

In this configuration:

- `GET /api/users` → matches dynamic route (priority 100) → dispatched to actor's `http.request` handler.
- `GET /assets/logo.png` → matches static route (priority 10) → served from `web-assets` volume at `assets/logo.png`.
- `GET /about` → matches static route (priority 0) → looks up `about` in `web-assets` volume. If not found, serves `index.html` with status `200` (SPA fallback).
- `GET /_cowboy/health` → reserved path, always Gateway-intercepted (CIP-14 §8.6), never reaches route manifest.

### 6.4 Example: Multi-Volume (API Docs + App Assets)

An actor can reference multiple volumes. Each `static_route` specifies which `volume_name` it reads from:

```json
{
  "version": 1,
  "static_routes": [
    {
      "volume_name": "docs-site",
      "path_prefix": "/docs/",
      "strip_prefix": true,
      "volume_path_prefix": "",
      "priority": 10,
      "fallback": "index.html",
      "fallback_status": 200
    },
    {
      "volume_name": "app-assets",
      "path_prefix": "/assets/",
      "strip_prefix": false,
      "volume_path_prefix": "assets/",
      "priority": 10,
      "fallback": null,
      "fallback_status": 404
    }
  ],
  "dynamic_routes": [
    {
      "path_prefix": "/api/",
      "priority": 100
    }
  ],
  "default_behavior": "dynamic"
}
```

Here `GET /docs/getting-started` strips the `/docs/` prefix and looks up `getting-started` in the `docs-site` volume. `GET /assets/logo.png` is served from the `app-assets` volume. Both volumes must be listed in the actor's `static_volumes` entitlement binding.

### 6.5 Route Manifest Location with Multiple Volumes

When an actor declares multiple `static_volumes` in its entitlement, the Gateway reads `_meta/routes.json` from the **first** volume in the `static_volumes` array. This is the **primary route manifest**. All `volume_name` references in the manifest's `static_routes` MUST match one of the declared `static_volumes` bindings.

Validation: If a `static_route` references a `volume_name` that is not in the actor's `static_volumes` entitlement, the Gateway ignores that route and logs a warning.

### 6.6 Route Resolution Algorithm

When a Gateway receives an HTTP `GET` or `HEAD` request for a registered actor that has `static_volumes` configured:

1. **Reserved paths**: If the path starts with `/_cowboy/`, handle per CIP-14 §8.6. This is always highest priority and not overridable by the route manifest.

2. **Collect matching routes**: Find all `static_routes` and `dynamic_routes` whose `path_prefix` is a prefix of the request path.

3. **Select winner**: Among matching routes, select the one with the highest `priority` value. Ties are broken by:
   - Longer (more specific) `path_prefix` wins.
   - If still tied, `dynamic_routes` win over `static_routes` (safety: prefer the actor handler when ambiguous).

4. **Static route wins**: Identify the volume from the route's `volume_name` field. Resolve the volume object path (§6.7). If the object exists, serve it from that volume. If the object does not exist and `fallback` is set, serve the fallback object (from the same volume) with `fallback_status`. If no fallback, return `404 Not Found`.

5. **Dynamic route wins**: Dispatch to the actor's `http.request` handler via CIP-14 query path (GET/HEAD) or command path (POST/PUT/PATCH/DELETE).

6. **No route matches**: Follow `default_behavior`. If `"dynamic"`, dispatch to actor handler. If `"static"`, attempt to resolve as a volume object; `404` if not found.

**Non-GET/HEAD requests**: `POST`, `PUT`, `PATCH`, and `DELETE` requests always dispatch to the actor handler via the CIP-14 command path, regardless of route manifest. Static routes only apply to `GET` and `HEAD`.

### 6.7 Volume Object Path Resolution

Given a static route match and a request path:

```
request_path = "/docs/getting-started"
matched_route = { path_prefix: "/docs/", strip_prefix: true, volume_path_prefix: "documentation/" }

1. Extract remainder:
   remainder = request_path.removePrefix(matched_route.path_prefix)
   // remainder = "getting-started"

2. Build volume path:
   volume_path = matched_route.volume_path_prefix + remainder
   // volume_path = "documentation/getting-started"

3. Look up volume_path in the volume manifest's ShardMap list.
   - If found: serve the object.
   - If not found and fallback is set: serve the fallback object.
   - If not found and no fallback: return 404.
```

If `strip_prefix` is `false`, the full request path (minus leading `/`) is used:

```
request_path = "/assets/logo.png"
matched_route = { path_prefix: "/assets/", strip_prefix: false, volume_path_prefix: "assets/" }

// strip_prefix=false → use request path directly (minus leading "/")
volume_path = "assets/logo.png"
```

### 6.8 Validation

Gateways MUST validate the route manifest on load:

- `version` MUST be `1`. Unknown versions are rejected (Gateway serves all paths dynamically as fallback).
- `static_routes` MUST NOT exceed `MAX_STATIC_ROUTES` entries.
- `dynamic_routes` MUST NOT exceed `MAX_DYNAMIC_ROUTES` entries.
- Total manifest size MUST NOT exceed `MAX_ROUTE_MANIFEST_SIZE`.
- `path_prefix` values MUST start with `/`.
- `path_prefix` MUST NOT be `/_cowboy/` or start with `/_cowboy/` (reserved by CIP-14).
- `fallback_status` MUST be a valid HTTP status code (100–599).
- `default_behavior` MUST be `"dynamic"` or `"static"`.
- Each `static_route` MUST include a `volume_name` that matches one of the actor's `static_volumes` entitlement bindings.

If validation fails, the Gateway logs a warning and treats all paths as dynamic (CIP-14 behavior). The actor's HTTP ingress continues to work — only static serving is disabled.

---

## 7. Entitlement Extension

### 7.1 New Parameters

CIP-15 extends the `ingress.http` entitlement (CIP-14 §6.2) with two new parameters:

| Param | Type | Description | Default |
| --- | --- | --- | --- |
| `static_volumes` | `array<StaticVolumeBinding>` | Public volumes the Gateway may serve as static assets. | `[]` (no static serving) |
| `max_static_response_bytes` | `u64` | Maximum size of a single static asset response. | `10_485_760` (10 MiB) |

```
StaticVolumeBinding {
  volume_name:      string,    // must be a PUBLIC volume owned by the same account
  max_cache_bytes:  u64        // maximum Gateway cache space this volume may consume (per Gateway)
}
```

The existing CIP-14 parameters (`allowlist_methods`, `max_request_bytes`, `max_response_bytes`, `max_query_cycles`) are unchanged and continue to govern dynamic route behavior. `max_static_response_bytes` is separate from `max_response_bytes` because static assets (images, video thumbnails, font files) are typically much larger than dynamic API responses.

### 7.2 Example Manifest

```json
{
  "entitlements": [
    {"id": "ingress.http", "params": {
      "allowlist_methods": ["GET", "HEAD", "POST"],
      "max_request_bytes": 1048576,
      "max_response_bytes": 1048576,
      "max_query_cycles": 10000000,
      "static_volumes": [
        {"volume_name": "web-assets", "max_cache_bytes": 104857600}
      ],
      "max_static_response_bytes": 10485760
    }},
    {"id": "storage.kv", "params": {"max_bytes": 10485760}},
    {"id": "econ.hold_balance"},
    {"id": "econ.transfer"}
  ]
}
```

### 7.3 Enforcement

- **Deployment-time**: The deployment transaction verifies that each `volume_name` in `static_volumes` references a `PUBLIC` volume owned by the deploying account. If any volume does not exist or has `visibility = PRIVATE`, deployment is rejected. The `volume_id` is deterministic (`keccak256(account_address || volume_name)`), so cross-account references are impossible.
- **Gateway enforcement**: Gateways MUST only serve static assets from volumes listed in `static_volumes`. Objects larger than `max_static_response_bytes` return HTTP `413 Content Too Large`. Gateways MUST respect `max_cache_bytes` per volume when allocating cache space.
- **Volume lifecycle**: If a volume listed in `static_volumes` is deleted (via CIP-9 `delete_volume`), the Gateway returns `404` for all static routes referencing that volume. The entitlement remains valid — the volume reference is stale. The actor owner must redeploy with updated `static_volumes` to restore static serving.

### 7.4 Why `max_cache_bytes` Is in the Entitlement

Cache limits are a resource commitment by the Gateway. Entitlements are the established mechanism for declaring resource quotas that the protocol enforces. Placing cache limits in the route manifest — which is actor-mutable without redeployment — would let actors arbitrarily expand their cache footprint on Gateways without any on-chain governance check.

---

## 8. Gateway-to-Relay-Node Fetch Protocol

### 8.1 Request Flow

When a Gateway receives an HTTP request that resolves to a static route:

```
Client                    Gateway                         Relay Nodes
  |                         |                                 |
  |--- GET /app.js -------->|                                 |
  |                         |--- 1. Check object cache        |
  |                         |   key: (volume_id, "app.js")    |
  |                         |                                 |
  |                         |   [CACHE HIT + fresh]           |
  |<-- 200 + body ----------|                                 |
  |                         |                                 |
  |                         |   [CACHE HIT + If-None-Match]   |
  |<-- 304 Not Modified ----|                                 |
  |                         |                                 |
  |                         |   [CACHE MISS]                  |
  |                         |--- 2. Fetch volume manifest --->|
  |                         |   (public, no CapToken)         |
  |                         |<--- manifest bytes -------------|
  |                         |                                 |
  |                         |--- 3. Look up ShardMap for      |
  |                         |   "app.js" in manifest          |
  |                         |                                 |
  |                         |--- 4. Fetch K shards in ------->|
  |                         |   parallel from K Relay Nodes   |
  |                         |<--- shard 0 --------------------|
  |                         |<--- shard 1 --------------------|
  |                         |<--- shard 2 --------------------|
  |                         |<--- shard 3 --------------------|
  |                         |                                 |
  |                         |--- 5. Reed-Solomon reconstruct  |
  |                         |--- 6. Verify content_hash       |
  |                         |--- 7. Read content-type + cache |
  |                         |--- 8. Store in object cache     |
  |                         |                                 |
  |<-- 200 + headers + body-|                                 |
```

### 8.2 Gateway-Side Caching

The Gateway maintains a two-layer cache:

**Layer 1: Metadata Cache** (always warm for active volumes)

```
MetadataCache {
  route_manifest:       RouteManifest,       // _meta/routes.json
  content_type_map:     ContentTypeMap,       // _meta/content_types.json (CIP-9 §7.6.5)
  cache_config:         CacheConfig,          // _meta/cache_config.json (CIP-9 §7.6.6)
  volume_manifest:      VolumeManifest,       // full ShardMap list
  manifest_root:        bytes32,              // on-chain StorageCommitment.manifest_root
  last_verified_block:  BlockHeight           // block at which manifest_root was checked
}
```

Keyed by `volume_id`. Refreshed when the on-chain `manifest_root` changes.

**Layer 2: Object Cache** (LRU, bounded)

```
ObjectCacheEntry {
  body:             bytes,          // reconstructed plaintext
  content_hash:     bytes32,        // BLAKE3, used as ETag
  content_type:     string,         // resolved MIME type
  content_length:   u64,
  cached_at:        BlockHeight,
  max_age:          u32             // from cache_config
}
```

Keyed by `(volume_id, object_path)`. Bounded by `max_cache_bytes` per volume (from entitlement) and `MAX_GATEWAY_CACHE_BYTES` total across all volumes. Eviction follows LRU with frequency weighting — frequently accessed objects are retained longer.

### 8.3 Cache Invalidation

Cache invalidation is driven by changes to the on-chain `StorageCommitment.manifest_root`. When volume contents change (new deploy via `commit_manifest`), the manifest root changes.

**Protocol:**

1. The Gateway polls the on-chain `StorageCommitment.manifest_root` for each actively-cached volume every `MANIFEST_POLL_INTERVAL` blocks (default: 6, ~6 seconds at 1 block/sec).
2. If `manifest_root` has changed:
   a. Fetch the new volume manifest from any Relay Node.
   b. Diff old and new manifests to identify changed, added, and removed objects.
   c. Evict all changed and removed objects from the object cache.
   d. Update the metadata cache (route manifest, content-type map, cache config).
3. If `manifest_root` is unchanged, all cached objects remain valid.

**Why polling, not push:** Relay Nodes are dumb storage without push notification capability. Subscribing to on-chain events for every cached volume creates scaling concerns. Polling the `manifest_root` (a single 32-byte on-chain read) is cheap and sufficient — static asset invalidation latency of a few seconds is acceptable.

### 8.4 Relay Node RPC

Gateways interact with Relay Nodes using the existing CIP-9 `GET_SHARD` RPC (CIP-9 §16.3) plus a new `GET_MANIFEST` RPC defined by this CIP.

> **CIP-9 amendment required:** CIP-9 §16.3 defines three Relay Node RPCs: `PUT_SHARD`, `GET_SHARD`, `LIST_SHARDS`. Adoption of CIP-15 MUST add `GET_MANIFEST` as a fourth Relay Node RPC in CIP-9. Until that amendment lands, Relay Nodes are not required to support `GET_MANIFEST`.

#### `GET_MANIFEST` (new — added by CIP-15)

Retrieves the canonical serialized volume manifest for a given volume.

```
GET_MANIFEST {
  volume_id:      bytes32    // keccak256(account_address || volume_name)
}
→ {
  manifest:       bytes,     // canonical serialized manifest (see §8.5)
  manifest_root:  bytes32    // Merkle root — must match on-chain StorageCommitment
}
```

- For **public** volumes: served without CapToken.
- For **private** volumes: requires a CapToken with `READ_WRITE` access.
- The `manifest_root` in the response MUST match the on-chain `StorageCommitment.manifest_root` for the volume. If it does not, the Gateway MUST reject the response and try another Relay Node.

Relay Nodes store the latest committed manifest for each volume they hold shards for. When a Runner calls `commit_manifest`, the updated manifest is propagated to all Relay Nodes holding shards in that volume.

#### `GET_SHARD` (existing CIP-9 §16.3)

```
GET_SHARD {
  shard_id:     bytes32,    // from ShardMap
  shard_index:  u8          // which of the K+M shards
}
→ {
  shard_bytes:  bytes,
  shard_hash:   bytes32     // BLAKE3 for verification
}
```

For public volumes, no CapToken is required (CIP-9 §7.6.3). The Gateway verifies every shard against its `shard_hash` from the ShardMap. Shards that fail verification are discarded and replacements are fetched from alternative Relay Nodes.

### 8.5 Canonical Manifest Serialization and Verification

The volume manifest returned by `GET_MANIFEST` is the list of all `ShardMap` entries for the volume. To enable deterministic verification against the on-chain `manifest_root`, CIP-15 specifies the canonical serialization format.

**Canonical serialization:**

1. Each `ShardMap` entry is serialized to CBOR (RFC 8949) with **deterministically sorted keys** (shortest key first, then lexicographic — per CBOR §4.2.1 Core Deterministic Encoding).
2. The list of serialized `ShardMap` entries is sorted lexicographically by `object_path` (UTF-8 byte ordering).
3. The serialized manifest is the CBOR-encoded array of these sorted entries.

**Merkle root computation:**

The `manifest_root` committed on-chain (CIP-9 `StorageCommitment.manifest_root`) is a binary Merkle tree root over the sorted `ShardMap` entries:

```
1. For each ShardMap entry i, compute:
   leaf[i] = BLAKE3(cbor_serialize(shard_map[i]))

2. Build a binary Merkle tree over the leaf hashes:
   - If the number of leaves is odd, duplicate the last leaf.
   - Internal nodes: BLAKE3(left_child || right_child)
   - Root = top of the tree.

3. manifest_root = merkle_root(leaf[0], leaf[1], ..., leaf[N-1])
```

**Gateway verification protocol:**

1. Fetch the manifest via `GET_MANIFEST(volume_id)`.
2. Deserialize the CBOR manifest into the sorted list of `ShardMap` entries.
3. Re-compute the Merkle root using the algorithm above.
4. Compare the computed root against the on-chain `StorageCommitment.manifest_root`.
5. If they match, the manifest is authentic. If not, reject the manifest and try another Relay Node.

This ensures the Gateway can verify the manifest without trusting the Relay Node — the on-chain Merkle root is the trust anchor.

### 8.6 Integrity Verification

The Gateway MUST verify every layer of the integrity chain:

1. **Manifest integrity**: Verify the fetched manifest against the on-chain `manifest_root` using the Merkle verification protocol (§8.5). A manifest that does not match the on-chain root MUST be rejected.
2. **Shard integrity**: For each fetched shard, verify `BLAKE3(shard_bytes) == shard_hash` from the ShardMap. Shards that fail verification are discarded; the Gateway fetches a replacement from an alternative Relay Node.
3. **Object integrity**: After Reed-Solomon reconstruction, verify `BLAKE3(reconstructed_bytes) == content_hash` from the ShardMap. If verification fails, the Gateway MUST NOT serve the object and MUST return HTTP `502 Bad Gateway`.

### 8.7 Parallel Fetch and Hedging

For latency-sensitive serving, the Gateway employs adaptive parallel fetch:

1. **Initial fetch**: Request K shards from the K lowest-latency Relay Nodes (based on historical RTT for that volume's shard assignments).
2. **Hedged requests**: If any shard request takes longer than `HEDGE_THRESHOLD_MS` (default: 100ms), issue a speculative request to an alternative Relay Node for a parity shard. Use whichever response arrives first.
3. **Shard selection**: The Gateway prefers data shards (indices `0..K-1`) but accepts parity shards. Any K of the K+M shards suffice for reconstruction.
4. **Concurrency cap**: No more than `MAX_CONCURRENT_SHARD_FETCHES` (default: 8) outstanding shard requests per object reconstruction.

### 8.8 HTTP Response Headers

When serving a static asset, the Gateway sets the following headers:

```
HTTP/1.1 200 OK
Content-Type: text/javascript; charset=utf-8
Content-Length: 45231
ETag: "b3_a1b2c3d4e5f6..."
Cache-Control: public, max-age=86400, immutable
X-Cowboy-Block: 1234567
X-Cowboy-Volume: web-assets
X-Cowboy-Source: static
Vary: Accept-Encoding
```

| Header | Source | Notes |
|--------|--------|-------|
| `Content-Type` | `_meta/content_types.json` (CIP-9 §7.6.5). Falls back to extension-based MIME inference. | |
| `ETag` | `"b3_" + hex(content_hash)`. The `b3_` prefix distinguishes BLAKE3 from other hash formats. | |
| `Cache-Control` | `_meta/cache_config.json` (CIP-9 §7.6.6). Falls back to `public, max-age=3600`. | |
| `X-Cowboy-Block` | Block height of the manifest used to resolve the object. | Same header as CIP-14 dynamic responses. |
| `X-Cowboy-Volume` | Volume name (informational). | |
| `X-Cowboy-Source` | `"static"` for CIP-15 served assets, distinguishes from CIP-14 `"dynamic"` responses. | |
| `Vary` | `Accept-Encoding` if compression is applied. | |

### 8.9 Conditional Requests

- **`If-None-Match`**: The Gateway compares the client's ETag against the cached object's `content_hash`. If they match and the manifest has not changed, return `304 Not Modified` with no body.
- **`If-Modified-Since`**: Not directly supported. Volume objects do not have per-file modification timestamps. Clients SHOULD use `If-None-Match` (ETag-based) for conditional requests.

### 8.10 Compression

Gateways SHOULD support `Accept-Encoding: gzip, br` and compress responses on-the-fly for compressible content types: `text/html`, `text/css`, `application/javascript`, `application/json`, `image/svg+xml`, `text/plain`, `application/xml`.

Binary content types (`image/png`, `image/jpeg`, `font/woff2`, `application/octet-stream`) MUST NOT be compressed — they are already optimally encoded and compression wastes CPU.

Gateways MAY cache compressed variants alongside the uncompressed object to avoid re-compressing on subsequent requests.

### 8.11 Relay Node Bandwidth Economics

CIP-9 specifies that Relay Nodes earn storage fees proportional to the shards they store (CIP-9 §10). CIP-15 introduces Gateways as a major reader class — potentially fetching shards at high volume for popular static sites. The bandwidth cost model:

**Who pays for shard reads:**

- The **volume owner** (actor's account) pays for Relay Node storage via per-epoch storage fees (CIP-9 §10). These fees cover the cost of storing *and serving* shards.
- Gateways do NOT pay per-shard-fetch fees directly. The bandwidth cost is absorbed into the Relay Node's storage fee revenue, analogous to how a CDN origin server absorbs bandwidth from CDN edge pulls.

**Rationale:** Introducing per-read micropayments between Gateways and Relay Nodes would add significant protocol complexity (payment channels, per-request accounting) for marginal benefit. The storage fee model already compensates Relay Nodes for both storage and bandwidth — nodes that serve more popular volumes earn proportionally more storage fees because those volumes persist (the owner keeps paying). If a volume is not worth paying storage fees for, it gets garbage-collected.

**Relay Node abuse protection:**

Relay Nodes MAY enforce local rate limits on `GET_SHARD` and `GET_MANIFEST` requests to prevent bandwidth abuse:

- Per-source-IP rate limiting (suggested: `MAX_SHARD_READS_PER_SECOND = 1000` per IP).
- Per-volume rate limiting (suggested: `MAX_SHARD_READS_PER_VOLUME_PER_SECOND = 500` per volume per IP).
- Total bandwidth throttling per connection.

These limits are locally enforced by each Relay Node and are not protocol-mandated constants. Relay Node operators MAY adjust them based on their infrastructure capacity.

**Future work:** A follow-on CIP may introduce actor-funded bandwidth budgets — actors deposit CBY into a bandwidth pool that compensates Relay Nodes for read traffic proportional to actual serving volume. This would align incentives more precisely but requires a per-read accounting mechanism that is not justified for v1.

---

## 9. CORS

### 9.1 Why CORS Is Specified Here

CIP-15 is the first CIP where browsers will directly consume Gateway responses. Static HTML pages served from one actor's domain will fetch JavaScript, CSS, and API endpoints from the same or other actors. Without CORS headers, browsers block cross-origin requests. Deferring CORS any further would make CIP-15 unusable for real web applications.

### 9.2 Configuration

CORS is configured via `_meta/cors.json` in the CIP-9 public volume:

```
CorsConfig {
  rules:  list<CorsRule>    // evaluated in order; first matching path_prefix wins
}

CorsRule {
  path_prefix:       string,           // URL path prefix to match
  allowed_origins:   list<string>,     // "*" permits all origins
  allowed_methods:   list<string>,     // HTTP methods permitted
  allowed_headers:   list<string>,     // request headers permitted
  expose_headers:    list<string>,     // response headers exposed to browser
  max_age:           u32,              // seconds for Access-Control-Max-Age
  allow_credentials: bool              // Access-Control-Allow-Credentials
}
```

### 9.3 Example

```json
{
  "rules": [
    {
      "path_prefix": "/api/",
      "allowed_origins": ["https://myagent.cowboy.network"],
      "allowed_methods": ["GET", "POST", "OPTIONS"],
      "allowed_headers": ["Content-Type", "Authorization", "X-Cowboy-Min-Block"],
      "expose_headers": ["X-Cowboy-Block", "X-Cowboy-Request-Id"],
      "max_age": 86400,
      "allow_credentials": false
    },
    {
      "path_prefix": "/",
      "allowed_origins": ["*"],
      "allowed_methods": ["GET", "HEAD", "OPTIONS"],
      "allowed_headers": [],
      "expose_headers": ["X-Cowboy-Block"],
      "max_age": 86400,
      "allow_credentials": false
    }
  ]
}
```

### 9.4 Default CORS Policy

When no `_meta/cors.json` exists, the Gateway applies a **permissive default** for static routes:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, HEAD, OPTIONS
Access-Control-Max-Age: 86400
```

**Rationale:** Static assets in a `PUBLIC_READ` volume are public by definition. Restricting their CORS policy by default would break most web applications. The permissive default matches CDN behavior (Cloudflare, Fastly, S3).

For dynamic routes, the Gateway does NOT apply any default CORS headers. The actor's `http.request` handler is responsible for setting CORS headers in the `HttpResponseEnvelope`. If `_meta/cors.json` includes rules matching dynamic route prefixes, the Gateway applies those rules, overriding any CORS headers the actor sets.

### 9.5 Preflight Handling

The Gateway handles `OPTIONS` requests for all routes (static and dynamic) directly, without dispatching to the actor:

1. Match the request path against `_meta/cors.json` rules (or the default policy for static routes).
2. If the `Origin` header matches `allowed_origins` and the `Access-Control-Request-Method` matches `allowed_methods`, return `204 No Content` with the appropriate `Access-Control-*` headers.
3. If no match, return `204 No Content` with no `Access-Control-*` headers (the browser will block the actual request).

This prevents actors from needing to implement preflight handling in their `http.request` handler, which would require listing `OPTIONS` in the `allowlist_methods` entitlement parameter and waste query-path cycles on a pure CORS check.

---

## 10. Protocol Constants

```
// Route manifest
MAX_STATIC_ROUTES                = 100             // maximum entries in static_routes
MAX_DYNAMIC_ROUTES               = 100             // maximum entries in dynamic_routes
MAX_ROUTE_MANIFEST_SIZE          = 65_536          // bytes; maximum _meta/routes.json size

// Manifest caching
MANIFEST_POLL_INTERVAL           = 6               // blocks between manifest_root checks (~6s)
METADATA_CACHE_TTL               = 60              // seconds; _meta/* cached between root changes

// Object caching
MAX_GATEWAY_CACHE_BYTES          = 10_737_418_240  // 10 GiB total per Gateway
DEFAULT_MAX_CACHE_PER_VOLUME     = 104_857_600     // 100 MiB default if not set in entitlement

// Static serving limits
DEFAULT_MAX_STATIC_RESPONSE_BYTES  = 10_485_760    // 10 MiB default max single asset
PROTOCOL_MAX_STATIC_RESPONSE_BYTES = 104_857_600   // 100 MiB hard ceiling

// Fetch optimization
HEDGE_THRESHOLD_MS               = 100             // ms before issuing hedged shard requests
MAX_CONCURRENT_SHARD_FETCHES     = 8               // max parallel shard requests per object

// CORS
DEFAULT_CORS_MAX_AGE             = 86_400          // seconds for preflight cache (24 hours)
MAX_CORS_RULES                   = 50              // maximum entries in _meta/cors.json
```

---

## 11. Rationale

### 11.1 Why Route Manifest in the Volume

Placing the route manifest at `_meta/routes.json` in the CIP-9 volume ensures atomicity: when a developer runs `commit_manifest`, the route configuration and the assets it references are committed in the same transaction. There is no window where the manifest points to files that do not exist or vice versa.

The alternative — storing routes in the actor's KV storage — would require the Gateway to call `queryActor` on every request to read the route config. This defeats the core performance goal of CIP-15 (no PVM cycles for static requests) and introduces a dependency on the actor being functional for static serving.

### 11.2 Why Extend `ingress.http` Instead of a New Entitlement

Static serving is a mode of HTTP ingress, not a fundamentally different capability. The actor still receives HTTP requests — some are just served from a volume instead of the actor handler. A separate `ingress.static` entitlement would require checking two entitlements on every request and complicate the Gateway's dispatch logic. Extending `ingress.http` keeps the parameter space unified.

### 11.3 Why Polling-Based Cache Invalidation

Relay Nodes are dumb shard storage (CIP-9 §16.3) — they do not support push notifications. Subscribing to on-chain events for every cached volume creates scaling concerns as the number of active volumes grows. Polling the `StorageCommitment.manifest_root` (a single 32-byte on-chain read per volume) is cheap and sufficient. The resulting invalidation latency (up to `MANIFEST_POLL_INTERVAL` blocks, ~6 seconds) is acceptable for static asset deployments — end-users will not notice a 6-second delay between a deploy and seeing the new version.

### 11.4 Why Include CORS

CIP-15 is the first specification where browsers will directly consume Gateway responses at scale. Without CORS headers, a static HTML page served from `myapp.cowboy.network` cannot load JavaScript from `api.cowboy.network` or fetch data from its own `/api/` endpoints if they are on a different subdomain. Deferring CORS to yet another CIP would make CIP-15 impractical for real web applications.

### 11.5 Why Permissive CORS Default for Static Assets

Public volume assets are, by definition, publicly readable. Any party can fetch them from Relay Nodes directly without authentication. Restricting CORS origins by default would create a mismatch: the data is public, but browsers cannot access it. This matches the behavior of every major CDN and static hosting provider.

### 11.6 Why `b3_` ETag Prefix

ETags are opaque strings in HTTP, but clients and intermediary caches may compare them. The `b3_` prefix:

- Distinguishes BLAKE3 hashes from MD5, SHA-256, or other ETag formats used by other servers.
- Enables clients that understand BLAKE3 to verify content integrity end-to-end by stripping the prefix and comparing against `BLAKE3(response_body)`.
- Avoids collision with weak ETags (which use the `W/` prefix per RFC 7232).

---

## 12. Security Considerations

### 12.1 Cache Poisoning

**Threat**: A compromised Relay Node serves corrupted shards, causing the Gateway to cache and serve incorrect content.

**Mitigation**: The Gateway verifies every layer of the integrity chain (§8.5):

- Manifest against on-chain `manifest_root` (Merkle root).
- Each shard against its `shard_hash` (BLAKE3) from the ShardMap.
- Reconstructed object against its `content_hash` (BLAKE3).

To poison the cache, an attacker would need to produce a BLAKE3 collision (computationally infeasible with 256-bit output) or forge the on-chain `manifest_root` (requires consensus compromise).

### 12.2 Volume Impersonation

**Threat**: An actor declares `static_volumes` pointing to a volume it does not own, serving another account's data under its own domain.

**Mitigation**: Deployment-time validation (§7.3) ensures each `volume_name` references a `PUBLIC` volume owned by the deploying account. The `volume_id` is deterministic: `keccak256(account_address || volume_name)`. Cross-account references are impossible because the `account_address` component differs.

### 12.3 Large Asset DoS

**Threat**: An actor stores very large objects in a public volume and drives traffic to them, exhausting Gateway resources.

**Mitigations**:

- `max_static_response_bytes` caps individual object sizes (default 10 MiB, ceiling 100 MiB). Objects exceeding this limit return `413 Content Too Large`.
- `max_cache_bytes` per volume caps Gateway cache consumption.
- `MAX_GATEWAY_CACHE_BYTES` caps total cache across all volumes.
- CIP-14 rate limits apply: `MAX_REQUESTS_PER_SECOND = 100` per actor per Gateway.
- CIP-9 storage billing makes hosting large volumes expensive for the account owner.

### 12.4 Stale Manifest

**Threat**: A Gateway serves content from an old manifest after the volume owner has deployed an update (e.g., serving a version with a known security vulnerability).

**Mitigation**: `MANIFEST_POLL_INTERVAL` (6 blocks) bounds the maximum staleness to ~6 seconds. The `X-Cowboy-Block` response header tells the client which block's manifest was used. Clients requiring strict freshness can include `X-Cowboy-Min-Block` in requests (CIP-14 §8.3).

### 12.5 Route Manifest Manipulation

**Threat**: A malicious route manifest redirects dynamic paths (e.g., `/api/`) to static files, bypassing the actor's authentication logic.

**Mitigation**: The route manifest is authored by the actor owner — they control both the routing configuration and the actor code. If the route manifest is malicious, the actor owner is the attacker, which is outside the protocol's threat model. The protocol cannot protect users from malicious actors they choose to interact with. Critically, `/_cowboy/*` paths are always Gateway-intercepted (CIP-14 §8.6) regardless of the route manifest.

### 12.6 CORS Misconfiguration

**Threat**: An overly permissive CORS configuration (`allowed_origins: ["*"]` with `allow_credentials: true`) could enable credential-leaking cross-origin attacks.

**Mitigation**: Gateways MUST reject CORS configurations where `allowed_origins` includes `"*"` and `allow_credentials` is `true` — this is explicitly forbidden by the CORS specification (the browser would reject it anyway, but the Gateway should catch it at validation time). If detected, the Gateway falls back to the default CORS policy.

---

## 13. Future Work

| Item | Scope | Status |
|------|-------|--------|
| **Pre-Compressed Assets** | Store `.gz` and `.br` variants alongside source files in the volume. Gateway selects the pre-compressed variant matching `Accept-Encoding`, avoiding on-the-fly compression CPU cost. | Deferred to a follow-on CIP. |
| **Small Object Inlining** | For objects under a threshold (e.g., 64 KiB), store the object directly in the ShardMap rather than erasure-coding into K+M shards. Eliminates multi-Relay-Node fetch overhead for tiny files. | Deferred. Requires CIP-9 manifest schema extension. |
| **Image Optimization** | Gateway-side image resizing, format conversion (WebP/AVIF), and responsive `srcset` generation. | Deferred to a follow-on CIP. |
| **Range Requests** | Support `Range` header for partial content delivery (`206 Partial Content`). Required for video streaming and large file downloads. | Deferred to a follow-on CIP. |
| **Gateway Cache Warming** | Protocol for Gateways to proactively fetch and cache objects from newly-deployed volumes before the first user request arrives. | Deferred. |
| **CDN Peering** | Integration with external CDN providers (Cloudflare, Fastly) for edge caching beyond the Gateway network. | Deferred. |

---

## 14. Backwards Compatibility

CIP-15 is fully backwards compatible:

- Actors without `static_volumes` in their `ingress.http` params are unaffected. Gateways dispatch all requests to the actor's `http.request` handler as before (CIP-14 behavior).
- The new entitlement parameters (`static_volumes`, `max_static_response_bytes`) are optional. When absent, defaults preserve existing behavior: `static_volumes = []` (no static serving) and `max_static_response_bytes = 10_485_760`.
- Existing `PUBLIC_READ` volumes gain no new behavior unless an actor explicitly references them in `static_volumes`.
- The `_meta/routes.json`, `_meta/cors.json` files are optional. Volumes without them work exactly as they do today.
- Gateway nodes must be upgraded to support CIP-15 behavior. Gateways that have not been upgraded will ignore `static_volumes` and dispatch all requests to the actor handler — safe degradation with no data loss or protocol violations.

---

## Part II — v2 Revision (canonical; verbatim from former `cip-15-aligned.md`)


<Note>
  **Status:** Draft (alignment revision; non-modifying companion to `cip-15-public-asset-hosting.md`)
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-04-21
  **Companion to:** `cip-15-public-asset-hosting.md`
  **Reads with:** Part III of this document, `cip-14-dns-addressable-actors-v2.md` (Part II)
</Note>

## 0. What this document is

A code-aligned revision of CIP-15. The original is mostly correct against CIP-9 but uses inconsistent terminology (`PUBLIC_READ` vs. CIP-9's `Visibility::Public`), assumes a different `volume_id` formula than CIP-9 §11.1 actually pins down, and silently nests an `array<StaticVolumeBinding>` object inside `ingress.http.params` that the codec cannot encode. This revision conforms terminology to CIP-9 / CBFS, factors static-asset hosting into a separate `ingress.static` entitlement, and tightens four points where the original under-specifies (priority ordering, dual-versioning headers, storage-delinquency halt, CORS precedence).

> **Errata.** The first revision of this document claimed CIP-9 was missing `StorageCommitment`, `commit_manifest`, the `volume_id = keccak256(...)` formula, and `Visibility::Public`. They are NOT missing — all four are in CIP-9 today (§11.1 and §12.2). The corrected upstream-amendment surface is much smaller and is documented in `cip-9-runner-storage-v2.md` (Part II).

It also:

- Separates static-asset hosting into a new `ingress.static` entitlement (the original's nested `StaticVolumeBinding` exceeds `ParamValue` capability).
- Imposes a structural priority rule that prevents static fallback from silently shadowing dynamic API routes.
- Adds `X-Cowboy-Manifest-Root` headers to close the dual-versioning gap between dynamic `X-Cowboy-Block` and static manifest-root caching.
- Halts serving on storage-fee delinquency (avoids turning Gateway cache into free CDN at Relay-Node expense).
- Reverses CORS precedence so actor-set CORS headers win on dynamic responses.

---

## 1. Preconditions

| Amendment | Source | Required for |
|-----------|--------|---------------|
| AMEND 9-G | `cip-9-runner-storage-v2.md` (Part II) §2 | `GET_MANIFEST` Relay Node RPC — direct manifest fetch |
| AMEND 9-H | `cip-9-runner-storage-v2.md` (Part II) §4 | `ManifestCommitted` chain event — eager Gateway invalidation |
| `cip-9-runner-storage-v2.md` (Part II) §3 | — | Pin canonical manifest serialization to `cbfs/manifest/src/merkle.rs` |
| `cip-9-runner-storage-v2.md` (Part II) §5 | — | Gateway HTTP serving authority over existing CIP-9 status states |
| Part III of this document §2.2 | — | Add `ingress.static` to entitlement registry |

The first two (AMEND 9-G/H) are the only true protocol additions; the third and fourth are documentation alignments over CIP-9's existing `manifest_root` and `status` fields. If AMEND 9-G/H have not landed, CIP-15-aligned can still be partially deployed by falling back to indirect manifest fetch (`GET_SHARD` against `__manifest__`) plus polling — at the cost of higher per-request latency and slower invalidation.

---

## 2. Scope

Functionally equivalent to original §1 with three differences:

- Separate `ingress.static` entitlement (rather than overloading `ingress.http`'s param schema with nested objects, which `ParamValue` cannot encode).
- CBFS terminology: `Visibility::Public` (not `PUBLIC_READ`), opaque `VolumeId` (not `keccak256`-derived).
- Route manifest stored on-chain at `STORAGE_MANAGER`, not in the "first volume" — decouples routing lifecycle from any one volume.

---

## 3. The `ingress.static` entitlement

Registry entry: Part III of this document §2.2.

```
ingress.static.params:
  static_volume_names:        StrArray  (required, ≤ 8)
  max_static_response_bytes:  Uint      (default 10_485_760, ceiling 104_857_600)
  max_cache_bytes_total:      Uint      (default 104_857_600; advisory)
```

### 3.1 Deploy-time validation

For each `name` in `static_volume_names`:

1. Resolve `volume_id` via the on-chain `Volume` record at `STORAGE_MANAGER`. The volume's `owner` MUST equal the deploying account.
2. The volume's `visibility` MUST be `Visibility::Public` (`cbfs/types/src/lib.rs:128`).

Failure rejects the deploy. CIP-9 §11.1 already pins the formula `volume_id = keccak256(account_address || volume_name)`; deploy-time validation can compute the expected `volume_id` directly from the supplied name and the deploying account, then look it up in `STORAGE_MANAGER` to confirm existence and visibility.

### 3.2 Coexistence with `ingress.http`

`ingress.static` is meaningful only in conjunction with `ingress.http`. An actor declaring `ingress.static` without `ingress.http` is rejected at deploy time (the Gateway has no way to handle dynamic fallback for non-static paths).

---

## 4. Route manifest

### 4.1 Location: on-chain at `STORAGE_MANAGER`

The route manifest is stored on-chain at `STORAGE_MANAGER=0x0A`, keyed by `actor_address`. The actor owner updates it via an `update_route_manifest(actor_address, manifest_bytes)` ActorMessage to `STORAGE_MANAGER` — the STORAGE_MANAGER handler enforces `tx.sender == actor.owner`. **This is an ordinary ActorMessage, not a new `SystemInstruction` opcode** — STORAGE_MANAGER is an existing system actor (`0x0A`) and its handlers are addressable via standard messaging. No opcode allocation is needed.

Rationale (departure from original §6.1, which placed it at `_meta/routes.json` in the volume):

- The original §6.5 forces a "primary route manifest = first volume's `_meta/routes.json`" convention. Multi-volume actors then have routing tied to one specific volume's lifecycle. If that volume is deleted or its visibility flips, routing breaks for *all* volumes.
- On-chain residence lets `update_route_manifest` and `commit_manifest` be independent: a developer can publish new assets without re-publishing routes, and vice versa.
- Cost is a single on-chain write per routing change. Routing changes are infrequent.

### 4.2 Schema

```
RouteManifest {
  version:           u8 (= 1),
  static_routes:     [StaticRoute],         // ≤ 100
  dynamic_routes:    [DynamicRoute],         // ≤ 100
  default_behavior:  u8                     // 0 = DYNAMIC, 1 = STATIC
}

StaticRoute {
  volume_name:        string,
  path_prefix:        string,
  strip_prefix:       bool,
  volume_path_prefix: string,
  priority:           u16,
  fallback_path:      string?,
  fallback_status:    u16
}

DynamicRoute {
  path_prefix:        string,
  priority:           u16
}
```

Same shape as original §6.2; `default_behavior` is an integer to match codec norms. `version` carries on the manifest itself (not implicit per-route).

### 4.3 Strict priority ordering (corrects original §6.6)

The original §6.6 tie-breaks with "longer prefix wins, then dynamic > static". A typo in a new dynamic route's priority can let `/api/login` match a `/` static fallback, silently breaking authentication. CIP-15-aligned imposes a structural constraint at `update_route_manifest` validation time:

> **`min(dynamic_routes.priority) > max(static_routes.priority)`**, or `update_route_manifest` is rejected with `ERR_ROUTE_PRIORITY_INVERSION`.

This makes "dynamic routes always shadow static routes when they match" structural rather than best-effort. Within a class, longer prefix wins; same prefix length within the same class is rejected at validation (`ERR_ROUTE_PREFIX_DUPLICATE`).

### 4.4 Volume object path resolution

Unchanged from original §6.7.

### 4.5 SPA fallback semantics (clarified)

The original §6.6 step 4 reads "if no fallback, return 404" and step 6 reads "follow `default_behavior`". The order is ambiguous: if a static route matches but the object is missing and no fallback is set, does control fall through to `default_behavior` or terminate at 404?

**Aligned semantics:** within a matched route, `fallback` is the only fallback; if it's null and the object is missing, return 404 (do not fall through). `default_behavior` only applies when **no route matches at all**.

### 4.6 Validation summary

Same as original §6.8 plus:
- `min(dynamic_routes.priority) > max(static_routes.priority)` (§4.3).
- No two routes within the same class share a `path_prefix`.

---

## 5. Cache invalidation and consistency

### 5.1 Two-version-number gap (closed)

The original §8.3 polls `manifest_root` per volume; the dynamic path uses `X-Cowboy-Block`. Two version namespaces over the same response surface lets a Gateway return `body @ manifest_root_N-1` with `X-Cowboy-Block: N`, masking staleness. CIP-15-aligned response headers always carry both:

```
X-Cowboy-Block:          <committed block height>
X-Cowboy-Manifest-Root:  <hex(manifest_root)>             // static responses only
X-Cowboy-Volume:         <volume_name>                    // static responses only
X-Cowboy-Source:         "static" | "dynamic"
```

Clients can pin both via:

- `X-Cowboy-Min-Block: N` (existing CIP-14 mechanism)
- `X-Cowboy-Manifest-Root: <hex>` request header — Gateway returns `409 Conflict` if its cached manifest does not match.

### 5.2 Polling + event hint

`MANIFEST_POLL_INTERVAL = 6` blocks (unchanged) is the **floor** for invalidation reliability. Additionally, every successful `commit_manifest` emits `ManifestCommitted{volume_id, manifest_root, block_height, raw_size_delta, visibility}` (AMEND 9-H per `cip-9-runner-storage-v2.md` (Part II) §4). Gateways subscribed to chain events invalidate eagerly on the event; polling catches up if events are missed.

### 5.3 Gateway serving authority by storage status

CIP-9 already has the relevant lifecycle states (`ACTIVE → GRACE_PERIOD → DELETED → GARBAGE_COLLECTING`, CIP-9 §13). CIP-15-aligned does **not** introduce a new `DELINQUENT` status; it maps the existing CIP-9 statuses to HTTP behavior per the table in `cip-9-runner-storage-v2.md` (Part II) §5:

| `StorageCommitment.status` | Gateway behavior |
|---|---|
| `ACTIVE` | Serve normally |
| `GRACE_PERIOD` | Serve, with advisory header `X-Cowboy-Storage-Status: grace` |
| `DELETED` | `503 Service Unavailable` + `X-Cowboy-Error: VOLUME_DELETED` |
| `GARBAGE_COLLECTING` | `410 Gone` + `X-Cowboy-Error: VOLUME_GC` |

Continuing to serve in `GRACE_PERIOD` is intentional — the owner may top up at any moment, and abrupt 503s would be a worse user experience than serving with an advisory header. The hard halt happens at `DELETED` (intentional removal) and `GARBAGE_COLLECTING` (irreversible).

This addresses the original "free CDN" externality (Gateway caches keep serving after the owner stops paying) by tying Gateway authority to a CIP-9 state that already terminates within `STORAGE_GRACE_EPOCHS`. It does so without inventing a new status enum value.

---

## 6. Gateway-to-Relay-Node fetch

### 6.1 RPCs

`GET_SHARD` (existing CIP-9 §16.3) plus `GET_MANIFEST` (AMEND 9-G per `cip-9-runner-storage-v2.md` (Part II) §2). CIP-15-aligned does not redefine either. Gateways MUST fall back to indirect manifest fetch via `GET_SHARD` against the well-known manifest shard address (`BLAKE3(volume_id || "__manifest__")`) when `GET_MANIFEST` is unavailable, marking the Relay as outdated rather than malfunctioning.

### 6.2 Manifest verification (uses CBFS canonical Merkle)

CIP-15-aligned defers to `cip-9-runner-storage-v2.md` (Part II) §3 for canonical serialization (CBFS bincode + **power-of-2 padded BLAKE3 binary Merkle** per `cbfs/manifest/src/merkle.rs:32-66`: leaves are `BLAKE3(bincode(ManifestEntry))`, padded to next power of two with `ContentHash([0u8;32])`, then balanced bottom-up `BLAKE3(left||right)`). The `manifest_root` returned by `GET_MANIFEST` MUST match the on-chain `StorageCommitment.manifest_root` byte-for-byte; mismatch → reject manifest, fetch from another Relay Node, mark the offending Relay as suspect.

The "if odd, duplicate the last leaf" passage in original §8.5 is dropped — that pattern carries the CVE-2012-2459 second-preimage shape. CBFS uses zero-hash power-of-2 padding instead (an earlier v2 draft mis-described this as RFC-6962-style; corrected in v2.r2), and CIP-15-aligned binds to the CBFS implementation rather than redefining the algorithm.

### 6.3 Shard fetch, hedging, integrity

Unchanged from original §8.6–8.7.

### 6.4 Response headers

§5.1 above plus the originals from §8.8 (`Content-Type`, `ETag`, `Cache-Control`, `Vary`).

### 6.5 Conditional requests, compression

Unchanged from original §8.9–8.10.

### 6.6 Bandwidth economics

Unchanged from original §8.11 except that §5.3 above bounds the externality.

---

## 7. CORS

### 7.1 Configuration location

Stored on-chain at `STORAGE_MANAGER` keyed by `actor_address` (parallel to the route manifest §4.1). Updated via an `update_cors_config(actor_address, config)` ActorMessage to `STORAGE_MANAGER` (sender == actor owner enforced by the handler). Same schema as original §9.2. Same as §4.1, this is an ordinary ActorMessage, not a new `SystemInstruction` opcode.

Co-locating with `route_manifest` lets one transaction update both atomically.

### 7.2 Default policy

Unchanged from original §9.4 (permissive default for static `GET`/`HEAD`/`OPTIONS`; no default for dynamic routes).

### 7.3 Precedence (reversed from original §9.4)

The original last paragraph of §9.4 reads "[for dynamic routes] the Gateway applies those rules, **overriding any CORS headers the actor sets**." This silently strips actor-authored CORS that the actor may consider load-bearing for its security posture. CIP-15-aligned reverses this:

> **Dynamic routes**:
> 1. If the actor's `HttpResponseEnvelope` includes any `Access-Control-*` headers, those are passed through unmodified. Gateway adds nothing.
> 2. Otherwise, Gateway applies `cors_config` rules.
> 3. Otherwise, no CORS headers are added.
>
> **Static routes**: Gateway applies `cors_config` rules. Default policy applies if no `cors_config` is set.

This restores the actor's authority over its own dynamic-response CORS while preserving the Gateway-handled flow for static assets (where the actor isn't even invoked).

### 7.4 Preflight handling

Unchanged from original §9.5 (Gateway handles `OPTIONS` directly, never dispatches to actor).

---

## 8. Constants

```
// Inherited from original §10
MAX_STATIC_ROUTES                 = 100
MAX_DYNAMIC_ROUTES                = 100
MAX_ROUTE_MANIFEST_SIZE           = 65_536
MANIFEST_POLL_INTERVAL            = 6
METADATA_CACHE_TTL                = 60
MAX_GATEWAY_CACHE_BYTES           = 10_737_418_240
DEFAULT_MAX_CACHE_PER_VOLUME      = 104_857_600
DEFAULT_MAX_STATIC_RESPONSE_BYTES = 10_485_760
PROTOCOL_MAX_STATIC_RESPONSE_BYTES = 104_857_600
HEDGE_THRESHOLD_MS                = 100
MAX_CONCURRENT_SHARD_FETCHES      = 8
DEFAULT_CORS_MAX_AGE              = 86_400
MAX_CORS_RULES                    = 50

// New in CIP-15-aligned
ROUTE_PRIORITY_GAP                = 1                    // min separation between max(static) and min(dynamic)
// Note: storage-grace handling reuses CIP-9 STORAGE_GRACE_EPOCHS; no new constant needed.
```

---

## 9. Security delta vs. original

| Threat | Aligned mitigation |
|---|---|
| Static fallback shadowing dynamic API on priority typo | §4.3 structural inversion check at `update_route_manifest` |
| Gateway returning stale body with fresh `X-Cowboy-Block` | §5.1 dual versioning headers + `X-Cowboy-Manifest-Root` |
| Stale volumes turning Gateway cache into free CDN after owner stops paying | §5.3 hard halt at CIP-9 `DELETED` / `GARBAGE_COLLECTING`; advisory at `GRACE_PERIOD` |
| `cors_config` silently overriding actor-set CORS on dynamic responses | §7.3 reversed precedence |
| Multi-volume manifest tied to one volume's lifecycle | §4.1 on-chain manifest, independent of any volume |
| `static_volumes` requiring nested-object `ParamValue` | §3 separate `ingress.static` with flat `StrArray` schema |
| Bitcoin-style Merkle CVE-2012-2459 surface | §6.2 reuses CBFS Merkle (`cbfs/manifest/src/merkle.rs`) |
| Cache poisoning (unchanged threat) | §6.2 manifest_root match + §6.3 shard hash verify (carried) |
| Volume impersonation (unchanged threat) | §3.1 deploy-time owner check (carried) |

---

## 10. Backwards compatibility

CIP-15-aligned is additive over both the original CIP-15 (draft only), CIP-9, and the running codebase. It adds:

- One entitlement registry entry (`ingress.static`, per Part III of this document §2.2).
- Two `STORAGE_MANAGER` record kinds (route manifest, CORS config).
- Two new ActorMessage handlers on `STORAGE_MANAGER` (`update_route_manifest`, `update_cors_config`) — **no new `SystemInstruction` opcodes needed**; STORAGE_MANAGER's handlers enforce `sender == actor.owner`.
- One new Relay RPC (`GET_MANIFEST`, per `cip-9-runner-storage-v2.md` (Part II) §2).
- One new chain event (`ManifestCommitted`, per `cip-9-runner-storage-v2.md` (Part II) §4).

It does NOT modify any existing CBFS types, the `StorageCommitment` schema, or the `commit_manifest` signature — those are already in CIP-9.

Actors without `ingress.static` are unaffected — Gateways dispatch all requests to the actor's `http.request` handler as in CIP-14-aligned. Gateways without CIP-15 implementation degrade safely: they ignore `ingress.static` and serve everything as dynamic.

---

## 11. Future work

| Item | Status |
|------|--------|
| Pre-compressed asset variants (`.gz`, `.br`) | Deferred (carried from original §13) |
| Small object inlining (≤ 64 KiB) | Deferred (carried) |
| Image optimization (Gateway-side) | Deferred (carried) |
| Range requests (`Range:` header) | Deferred (carried) |
| Gateway cache warming | Deferred (carried) |
| External CDN peering | Deferred (carried) |
| Per-read bandwidth accounting between Gateway and Relay | Deferred (carried §8.11) |

---

## Part III — Cross-Cutting Conventions (verbatim from former `alignment-conventions.md`)

# Alignment Conventions for CIP-14 / CIP-15 / CIP-16

**Status:** Draft alignment companion (non-modifying)
**Created:** 2026-04-21
**Scope:** Cross-cutting conventions used by `cip-14-dns-addressable-actors-v2.md` (Part II), Part II of this document, `cip-16-custom-domains-v2.md` (Part II). Anything that would otherwise be repeated across all three drafts lives here.

This document also enumerates upstream amendments these aligned drafts assume in CIP-2, CIP-3, CIP-5, CIP-9, and the normative entitlement registry — without modifying those source documents. Each `AMEND` item is a precondition: implementing CIP-14/15/16 requires the corresponding amendment to land first.

---

## 1. System actor address allocation

The current low-byte sequence (`node/types/src/constants.rs`, `node/runner/src/system_actors.rs:13-35`) ends at `0x0C` (`SESSION_ACTOR`). The aligned drafts continue the same dense sequence rather than jumping into the `0x10`+ range used by the original CIP-14 (`0x0011`, `0x0012`).

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
| `0x0C` | `SESSION_ACTOR` (MPP session model, `system_actors.rs:35`) | existing |
| `0x0D` | `ROUTE_REGISTRY` (CIP-14-aligned §4) | new (v2.r2: shifted from `0x0C`) |
| `0x0E` | `GATEWAY_REGISTRY` (CIP-14-aligned §7) | new (v2.r2: shifted from `0x0D`) |
| `0x0F` | `RECEIPT_REGISTRY` (CIP-14-aligned §8) | new (v2.r2: shifted from `0x0E`) |
| `0x10` | `CONTAINER_REGISTRY` (CIP-10 v2 Part II §1) | new (v2.r2: shifted from `0x0F`) |
| `0x11` | `PAYMENT_GATE` (CIP-18 §8) | new (v2.r2: shifted from `0x0013`) |
| `0x12` | `STREAM_KEY_MANAGER` (CIP-7 r2 §4) | new (r2: shifted from `0x06` which conflicts with DUAL_BASEFEE) |

Rationale: keeping the sequence dense matches `system_actors.rs` convention and avoids the appearance of a reserved block. Original CIP-14 v1 numbers (`0x0011` / `0x0012`) are renumbered to `0x0D` / `0x0E` (v2.r2 shift; the v2.r1 draft used `0x0C` / `0x0D`, but `0x0C` was subsequently committed to code as `SESSION_ACTOR`).

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

Several flows in CIP-14-aligned and CIP-16-aligned require an actor to trust that a specific selector was invoked **only** by a specific system actor (e.g. `GATEWAY_REGISTRY=0x0E`, `RESULT_VERIFIER=0x03`). The aligned drafts implement this in the system-instruction dispatcher (`node/execution/src/system_instruction.rs`) rather than relying on SDK-side `ctx.sender` checks.

The pattern (matches the existing `BASEFEE_SYSTEM_ACTOR=0x06` idiom for `UpdateBasefee`):

1. Define a new `SystemInstruction` opcode (e.g. `IngressDispatch`, `ExternalDomainCallback`) carrying `(target_actor, selector, payload)`.
2. The dispatch handler enforces a sender allowlist: only the named system actor address may emit the opcode.
3. The dispatcher synthesises an internal `ActorMessage` whose `ctx.sender` is set to the system actor address. Ordinary `send_message` / `call_actor` from arbitrary accounts cannot reproduce this `ctx.sender` value because the message router populates `ctx.sender` from the calling tx's signer (it cannot be forged by the caller's own code).
4. **Receiving actors MUST verify `ctx.sender` against the canonical sender for that selector** (e.g. `ctx.sender == GATEWAY_REGISTRY=0x0E` for `"http.request"`; `ctx.sender == RESULT_VERIFIER=0x03` for `"_dns.callback"`). The SDK (CIP-6) decorator-based handlers MUST include this check by default; raw handlers MUST include it manually.

> **Note (revision).** An earlier draft described a 4th step in which the PVM message router would *additionally* reserve the corresponding selectors. **That proposal was withdrawn** (see `cip-14-dns-addressable-actors-v2.md` (Part II) §6.2 Note) because it broke legitimate router-actor forwarding patterns. The handler-side `ctx.sender` check above is sufficient.

This makes ingress / verifier authenticity a protocol property: `ctx.sender` is set by the message router from on-chain signer state. SDK-default sender checks at the receiving handler are mandatory.

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
- **Pin canonical manifest serialization** to `cbfs/manifest/src/merkle.rs` (`cip-9-runner-storage-v2.md` (Part II) §3). Reuses existing CBFS bincode + power-of-2 padded BLAKE3 binary Merkle (avoids the Bitcoin-style duplicate-last-leaf shape; CVE-2012-2459 free).
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

CIP-14-aligned defines a `RECEIPT_REGISTRY=0x0F` system actor that owns receipt storage and lifetime. See `cip-14-dns-addressable-actors-v2.md` (Part II) §8 for the full schema. Two key properties:

- Receipts are written by the `IngressDispatch` system instruction post-handler-return, not by actor code. Actors do not consume their own KV or timer budget for receipt management.
- A single registry-wide pruning loop expires receipts via TTL, replacing per-request timers. One timer slot total, not one per pending request.

---

## 11. Whitepaper alignment

These aligned drafts respect every WP principle exercised by CIP-14/15/16. The companion the WP v2 Part III enumerates the principles and the specific clauses that uphold them, including three places where the aligned drafts knowingly bend WP framing (Gateway as a fourth node class, receipt registry as a new state surface, ACME / TLD centralization at v1).
