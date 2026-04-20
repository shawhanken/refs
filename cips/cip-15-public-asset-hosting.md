---
title: "CIP-15: Public Asset Hosting"
description: Gateway-side static asset serving from CIP-9 public volumes, with route manifests, caching, CORS, and a Gateway-to-Relay-Node fetch protocol
icon: image
---

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
