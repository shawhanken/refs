---
title: "CIP-17: Verifiable State Read RPC"
description: A single-KV-with-Merkle-proof read RPC against a Cowboy full node or Runner, returning `(value, merkle_proof, state_root, block_height)`. Required by CIP-15 v2.r2 Gateway routes-table fetch and CIP-19 `tools/list` derivation. No new on-chain state; pure read-path addition.
icon: shield-check
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core (RPC)
  **Created:** 2026-05-11
  **Requires:** CIP-4 (State & Merkle Proofs)
  **Required by:** CIP-15 v2.r2 §6 (Gateway routes-table fetch), CIP-15 gateway-implementation r2 §2.2 (Phase 1 routes resolver), CIP-19 §10.1 (MCP `tools/list` derivation)
  **Companions:** CIP-14 v2.r2 §5 (`read_handler` RPC — complementary, distinct purpose)
</Note>

## 1. Abstract

This CIP specifies `GET_STATE` — a verifiable single-key state-read RPC exposed by Cowboy full nodes and Runners. Given an `actor_address` and a storage `key`, it returns the current value plus a Merkle inclusion proof against the actor's `state_root` at a known block height. Clients (Gateways, off-chain indexers, light clients) verify the proof locally before trusting the value.

`GET_STATE` is **not** a handler-invocation RPC — that role belongs to CIP-14 v2.r2 §5 `read_handler`. `GET_STATE` is a raw, deterministic, proof-attached KV read. It is the building block CIP-15 v2.r2 needs to fetch a target actor's `__cowboy/routes` table without invoking the actor (no PVM cycles), and that CIP-19 §10.1 needs to derive `tools/list` deterministically from on-chain routes.

The current RPC layer (`node/rpc/src/rpc.rs:168-213`) exposes `/actor/{address}` and `/actors/{address}/storage` for unverified state reads. `GET_STATE` adds the Merkle-proof attachment that closes the trust model: a Gateway no longer has to trust a single Runner — it verifies the response against the actor's `state_root` from a recent block.

---

## 2. Motivation

CIP-15 v2.r2 Gateway implementation depends on a per-actor `Routes` table stored at the actor's KV key `__cowboy/routes`. The Gateway fetches this table on every block of activity, caches it, and resolves incoming HTTP requests against it. Without a verifiable read:

1. **Single point of trust.** A Gateway fetching from one Runner has no way to detect a malicious or stale response. The Runner could return a forged routes table redirecting traffic.
2. **Cache invalidation theory only.** CIP-15 v2.r2 §6 says "poll `manifest_root` every `MANIFEST_POLL_INTERVAL` blocks." But polling for `state_root` changes requires a verifiable read in the first place — otherwise the polled value is itself a trust assumption.
3. **CIP-19 `tools/list` consequence.** CIP-19 §10.1 step 1 reads the routes table identically. The same trust gap applies.

The current `/actor/{address}` and `/actors/{address}/storage` endpoints (`node/rpc/src/rpc.rs:168-213`) return raw KV values with no proof. CIP-15 gateway-implementation r2 §2.2 explicitly flags this as the **single hardest blocker** for Phase 1 shipping.

The fix is a small, well-scoped addition: take the existing KV-read path, attach the Merkle proof against the actor's storage trie root (already maintained per CIP-4), and expose the bundle through a new RPC endpoint.

---

## 3. Design Goals

- **Verifiable.** Response carries everything a client needs to reconstruct the actor's state-root commitment for the read leaf, with no further round-trip.
- **Cheap on the server.** The proof is a single Merkle path; node maintains the storage trie anyway (CIP-4) so generation is microseconds, not milliseconds.
- **Stateless on the client.** No subscription, no session, no pagination. One KV → one response.
- **Reusable.** Applicable to any system actor or user actor; not specialized to Gateway routes.
- **Compatible with light clients.** A future Cowboy light client (per CIP-25 §1.4 native-light-client backend) consumes the same proofs.

## 4. Non-goals

- **Handler invocation.** That is CIP-14 v2.r2 §5 `read_handler`.
- **Streaming subscriptions.** A future CIP may add `SUBSCRIBE_STATE` (push notifications when a key changes); v1 here is pull-only.
- **Multi-key proofs.** v1 returns one proof per call. Batch reads with a combined proof are a future optimization.
- **Cross-actor proofs.** v1 proves inclusion of `(key, value)` within **one** actor's storage trie. Cross-actor relations require multiple `GET_STATE` calls.
- **Historical reads.** v1 reads at the latest committed block. A future revision may add `at_block: u64` for historical Merkle reads (CIP-25 §1.4 cross-chain backends would need this).

---

## 5. RPC Endpoint

### 5.1 HTTP route

```
GET  /state/{actor_address}/{key_hex}
```

Path parameters:
- `actor_address` — 20-byte hex-encoded address with `0x` prefix (e.g. `0x0000...000D`)
- `key_hex` — hex-encoded raw KV key bytes with `0x` prefix; same encoding as used by the actor when writing via `state_set`

Query parameters:
- `prove`: boolean, default `true`. If `false`, behaves identically to the existing `/actors/{address}/storage` lookup — value only, no proof. Provided for parity with cheap unverified reads.

### 5.2 Response

```json
{
  "actor_address":  "0x0000…000D",
  "key":            "0x...",
  "value":          "0x..."  | null,
  "state_root":     "0x...",
  "block_height":   12345678,
  "block_hash":     "0x...",
  "proof": {
    "siblings":     ["0x...", "0x...", ...],
    "leaf_hash":    "0x...",
    "path_nibbles": [0, 5, 12, ...]
  },
  "absent":         false
}
```

Fields:
- **`value`** — raw bytes of the KV value, hex-encoded with `0x` prefix. `null` if the key does not exist (see `absent` below).
- **`state_root`** — the actor's storage trie root at `block_height`. Matches `account_state.state_root` for `actor_address` in the block's account trie.
- **`block_height`** — the block height at which the proof was generated; always the latest committed block at the time of RPC handling.
- **`block_hash`** — block-header hash for cross-verification with the node's block-explorer view.
- **`proof.siblings`** — ordered Merkle path siblings from leaf to root, per the existing CIP-4 / MPT primitives Cowboy uses for actor storage.
- **`proof.leaf_hash`** — the leaf hash `keccak256(key || value)` (or whichever convention the existing MPT impl uses; pinned by the implementation, not redefined here).
- **`proof.path_nibbles`** — the nibble path used to navigate the MPT; redundant given `key` but explicit for proof-verifier ergonomics.
- **`absent`** — `true` if the key does not exist in the actor's storage at `block_height`. The proof is then an exclusion proof (the path to where the key would be, terminating in a divergent node). Clients verify exclusion identically to inclusion.

### 5.3 Proof verification (client-side)

```python
def verify_state_read(response, expected_actor_address):
    # 1. Confirm block header is current (out-of-band — block subscription, etc.).
    # 2. Reconstruct leaf: leaf_hash == hash_leaf(key, value, absent)
    # 3. Walk siblings + path_nibbles to compute root.
    # 4. Compare computed root with response.state_root.
    # 5. Compare response.state_root with the account-trie entry for expected_actor_address
    #    in the block (requires a second proof against the block's state_root; out of scope
    #    for v1 — clients that need account-trie verification call GET_STATE against a
    #    system actor (e.g. ACCOUNTS_REGISTRY) for the account trie. Future revision may
    #    bundle.)
    return computed_root == response.state_root
```

The 5-step verification (line 5 in particular) reveals a known limitation: a Gateway verifying a routes-table read needs both the actor's storage proof AND a proof that the actor's `state_root` claim matches the block's account trie. v1 expects the Gateway to obtain the account trie root through the existing block-header subscription (which a Gateway already maintains for CIP-14 v2.r2 cache invalidation) and trust it equally with `block_hash`. A v2 revision may bundle the account-trie path into the same response.

### 5.4 Error responses

```
404 Not Found            — actor_address does not exist
400 Bad Request          — malformed key/address hex
500 Internal Server Error — node-side proof generation failure (should not occur)
503 Service Unavailable  — node temporarily not synced (block_height stale beyond grace)
```

The "absent" case (key not in actor storage) is NOT a 404 — it returns 200 with `value: null` and `absent: true` plus a valid exclusion proof.

---

## 6. Use Cases

### 6.1 CIP-15 v2.r2 Gateway routes fetch (primary motivator)

Per `cip-15-gateway-implementation.md` r2 §2.3, the Gateway's poll loop calls:

```python
state_resp = http_get(f"https://runner.example.com/state/{actor_address}/0x{hex('__cowboy/routes')}")
if not verify_state_read(state_resp, actor_address):
    log_warning("Runner returned invalid proof; trying another runner")
    continue
routes_cbor = state_resp.value
if state_resp.state_root == cache[actor_address].state_root:
    continue  # nothing changed
cache[actor_address] = ActorRoutesCache(
    routes=cbor.decode(routes_cbor),
    state_root=state_resp.state_root,
    last_verified_block=state_resp.block_height,
)
```

### 6.2 CIP-19 `tools/list` derivation

The MCP `tools/list` generator (CIP-19 §10.1 step 1) uses the same call to fetch the routes table; the rest of §10.1 is independent of how the table was fetched.

### 6.3 Off-chain indexer audit

Indexers building cross-actor views (token balance trackers, governance vote tallies) issue `GET_STATE` calls against the canonical balance / vote keys and **verify each proof** before incorporating values into their derived state. Eliminates the "indexer trusts a single node" failure mode.

### 6.4 Light client support (future)

A Cowboy light client (per CIP-25 §1.4 "native light client" backend on a destination chain) consumes `GET_STATE` responses verbatim. The destination-chain verifier code is just the §5.3 procedure compiled into the destination's VM.

---

## 7. Implementation Sketch (non-normative)

The node side requires:

1. **One new HTTP route** in `node/rpc/src/rpc.rs` (after the existing `/actors/{address}/storage` handler at line 168-213): `GET /state/{actor_address}/{key_hex}`.
2. **One new method** on the existing storage interface that returns `(value, proof)` instead of just `value`. The MPT crate Cowboy uses for actor storage already maintains the proof primitives — exposing them is a few-line API surface addition.
3. **One new struct** in `node/types/src/rpc.rs` (or equivalent) for the response envelope.

Estimated implementation size: < 200 lines including tests. No new on-chain state, no new consensus, no new storage layout.

Existing primitives:
- Actor storage trie maintained per `node/storage/src/blockchain_storage.rs` (per CIP-4).
- Block header / state-root view via `node/chain/src/engine.rs`.
- HTTP route boilerplate per other endpoints in `node/rpc/src/rpc.rs`.

The implementation is intentionally orthogonal to any other in-flight work; it lands as a Phase 0 deliverable ahead of CIP-15 v2.r2 / CIP-19 activation.

---

## 8. Relationship to Other CIPs

| CIP | Relationship |
|---|---|
| **CIP-4** (State & Merkle Proofs) | Source of the MPT primitives `GET_STATE` exposes. CIP-17 does not redefine the trie shape; it only adds the RPC surface. |
| **CIP-14 v2.r2** §5 (`read_handler`) | Complementary, distinct. `read_handler` invokes the actor's PVM in read-only mode; `GET_STATE` reads raw KV with proof. A Gateway needs both: `read_handler` for `GET /api/users/{id}`-style dispatched logic, `GET_STATE` for `__cowboy/routes` fetch. Different latency, different trust model. |
| **CIP-15 v2.r2** | Primary consumer. CIP-15-gateway-implementation r2 §2.2 lists `GET_STATE` as the single hardest Phase 1 prerequisite. |
| **CIP-19** | Secondary consumer. §10.1 step 1. |
| **CIP-25** §1.4 (native light client) | Future consumer; `GET_STATE` responses are exactly the leaf primitive a cross-chain light client verifies. |

---

## 9. Security Considerations

- **Trust model.** A Gateway / indexer / light client verifies the Merkle proof locally before trusting the value. A malicious node returning a forged `(value, proof)` either trips proof verification (proof doesn't reconstruct to the claimed `state_root`) or returns a `state_root` that doesn't match the block header the client has from a separate trusted source (e.g. another node, or its own block subscription).
- **Stale reads.** Responses always reflect the latest committed block at RPC handling time. Clients that need monotonic reads should compare `block_height` across successive calls and reject regression.
- **DoS surface.** Proof generation is cheap (single Merkle path), but a flood of `GET_STATE` calls against large actor states could pressure a node. Mitigation: standard rate-limit middleware (already deployed for `/actors/{address}/storage` at 100 req/s default per `node/rpc/src/rpc.rs`).
- **Absent-key fingerprinting.** Returning an exclusion proof reveals "this key does not exist" deterministically. This is the same information already exposed by `/actors/{address}/storage`; no new leak.
- **Key encoding edge cases.** Implementations MUST decode `key_hex` strictly (reject non-hex chars, odd length, etc.) to prevent ambiguity between, e.g., `0x__cowboy/routes` (literal nine-byte string) and a typoed escape sequence.

---

## 10. Backwards Compatibility

Fully additive. New HTTP route; no existing RPC, on-chain state, or PVM syscall is modified. Clients that don't speak `GET_STATE` continue to use `/actor/{address}` and `/actors/{address}/storage` unchanged.

If `GET_STATE` lands in node code, the `cip-15-gateway-implementation` companion's §9 open-question item 1 is resolved.

---

## 11. Future Work

- **`at_block: u64` query param** for historical reads (needed by CIP-25 §1.4 native light client backend).
- **Batch reads.** `POST /state/batch` with multiple `(actor, key)` pairs returning combined proofs.
- **Subscribe API.** WebSocket-based push when a watched key changes — useful for Gateway cache invalidation tighter than CIP-15's `MANIFEST_POLL_INTERVAL`.
- **Bundled account-trie proof.** Resolve §5.3 limitation by returning both the actor's storage proof AND the account-trie proof for `actor_address.state_root` in one response.
- **CIP-25 cross-chain extension.** A cross-chain L1 anchor (CIP-25 §1) can carry `GET_STATE`-style proofs over the L1 mailbox, allowing destination-chain L3 apps to verify Cowboy state directly.

---

## 12. References

- `node/rpc/src/rpc.rs:168-213` — existing unverified state endpoints
- `node/storage/src/blockchain_storage.rs` — actor storage trie
- CIP-4 — MPT / Merkle proof primitives
- CIP-14 v2.r2 §5 — `read_handler` (complementary RPC)
- CIP-15 v2.r2 §6 + `cip-15-gateway-implementation.md` r2 §2.2 — primary use case
- CIP-19 §10.1 — secondary use case
- CIP-25 §1.4 — native light client future use case
