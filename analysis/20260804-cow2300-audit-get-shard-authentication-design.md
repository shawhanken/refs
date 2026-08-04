# COW-2300 — Authenticating the drain-audit `AuditGetShard` RPC

**Status:** design (2026-08-04). Interim rate-limit shipped in cbfs#122; full authentication scoped below.
**Repos:** cbfs (`node/src/handler.rs`, `types/src/lib.rs`) + node (`rpc/src/drain_audit_sampler.rs`, cbfs pin).

## 1. Problem

`handle_audit_get_shard` (cbfs `node/src/handler.rs`) serves the full shard bytes with **no request authentication**: it checks only `node_id`/`shard_id`/`shard_index` (all broadcast in `PlacementRecord`s) + timestamp freshness. `AuditGetShardRequest` (`types/src/lib.rs:782`) carries no signature. So any peer that can name a shard pulls its bytes (ciphertext for private volumes, plaintext for public) and gets a signed `(status, payload_len, payload_hash)` existence/size/content oracle. Escape `esc-20260616-cbfs-audit-get-shard-unauth`, ratchet `cbfs.audit_get_shard_authenticated`.

## 2. Why "receipt-only" (the first attempt) was wrong

Returning only the signed receipt (`shard_bytes = None`) **breaks drain-fraud detection**:

- The production consumer is `node/rpc/src/drain_audit_sampler.rs` (spawned unconditionally in `rpc.rs`, `RAS_DRAIN_AUDIT_SAMPLER_ENABLED` defaults **true**). Its `validate_audit_response` rejects a `Found` receipt whose `shard_bytes` is `None` (`InvalidReceipt`) → `submit_fraud` never fires → **every relay carrying that change is permanently un-slashable**.
- `payload_hash = blake3("cbfs:peer_shard_bytes:v1" || bytes)` (domain-tagged) ≠ `PlacementRecord.shard_hashes = blake3(bytes)` (untagged), so the receipt is **not independently verifiable** without the bytes. The sampler must re-hash the returned bytes; the bytes are load-bearing.

Lesson: the audit is a **proof-of-possession that requires returning the bytes** (the sampler re-hashes them). The fix must therefore **authenticate the requester**, not remove the payload.

## 3. Architecture (the reason this is cross-team, not a one-file fix)

- **cbfs relay** = a `cbfs-node` process; loads `relay_identity_key` (`cbfs/node/src/config.rs:172`), registered in the on-chain **relay registry** (`cowboy_ras::storage_keys::relay_registry`). Serves `AuditGetShard`.
- **Auditor** = the **Cowboy validator** (`node/` repo) running `drain_audit_sampler`. It is a **different process/role**: it does not embed a cbfs `NodeHandler`, its `AppState` holds **no cbfs relay signing key**, and it is **not** in the relay registry.
- The handler's only identity-resolution machinery is `relay_registry.relay_profile(node_id) -> relay_identity_pubkey` (used by `verify_peer_signature` for `PeerRelayPushShard`). It has **no validator-set / auditor concept**.

So authenticating the auditor requires giving the auditor an identity the relay can resolve on-chain. That is new plumbing on both sides.

## 4. Auth-model options

| Option | Auditor identity | Handler verification | New infra | Notes |
|---|---|---|---|---|
| **A. Auditor registers as a relay** | validator gets a `relay_identity_key` + registers in the relay registry | reuse existing `relay_profile` lookup | validator key-gen + **on-chain relay registration** for every validator | reuses all handler machinery; conflates validator/relay roles; registration flow is the cost |
| **B. Dedicated auditor registry** | validator registers an auditor pubkey in a new on-chain `audit_registry` actor | new `audit_profile` lookup in cbfs | new actor + genesis + registration + cbfs cache | clean separation; most new code |
| **C. Verify against the consensus validator set** | validator signs with its consensus identity | cbfs reads the on-chain validator set | **cbfs↔consensus coupling** (cbfs must read validator-set storage layout) | couples storage to consensus internals; highest blast radius |

**Recommendation: Option A** (auditor = registered relay) — it adds *no new verification path* in the security-critical handler (reuses `verify_peer_signature` + `relay_profile`, already audited for `PeerRelayPushShard`). The cost is operational (each auditing validator must hold a registered relay identity). Authorization predicate: **signer is a relay registered and in good standing** (NOT `Draining`/assignee — those are push-direction checks that do not apply to an auditor).

## 5. Concrete change list (Option A)

**cbfs `types/src/lib.rs`**
- Add to `AuditGetShardRequest`: `auditor_node_id: NodeId`, `signature: Vec<u8>` (Ed25519, 64 B).
- Add `audit_get_shard_request_digest(chain_id, network, &req_without_sig) -> [u8;32]` binding **all** request fields incl. `nonce` + `timestamp_ms` (challenge-binding) under a fresh domain tag `"cbfs:audit_get_shard_req:v1"`.

**cbfs `node/src/handler.rs` — `handle_audit_get_shard`**
- After decode: `relay_profile(auditor_node_id)` → pubkey; reject (`ErrAuth`) if absent/not-good-standing.
- `verify_peer_signature(pubkey, digest, sig)`; reject on failure.
- Keep returning `Some(bytes)` on Found. Keep the interim `allow_read_probe` wrap.
- Un-ignore `audit_get_shard_requires_auth_and_returns_no_raw_bytes` → repurpose to assert an **unsigned/foreign-signed** request is `ErrAuth`; drop the sibling test's `auth.requests().is_empty()` "bypass is intended" assertion.

**node `rpc/src/drain_audit_sampler.rs`**
- Thread a cbfs relay `SigningKey` (+ its `node_id`) into `DrainAuditSamplerConfig`/`spawn_drain_audit_sampler` from node config.
- Set `auditor_node_id`, compute the digest, sign, populate `signature`.

**node** — bump the cbfs dependency pin to the head carrying the type change; **lockstep** (old sampler + new handler = all audits rejected → fraud detection down; gate with a rollout flag, see §6).

## 6. Rollout (must be lockstep-safe)

1. Ship the cbfs type field + handler that **accepts either** a valid signature **or** (temporarily) an unsigned request, logging unsigned as deprecated — behind `RAS_AUDIT_REQUIRE_SIG` default **false**.
2. Roll out the node sampler that signs.
3. Flip `RAS_AUDIT_REQUIRE_SIG` → true once the fleet signs. Then unsigned requests are rejected and the disclosure is closed.

A hard flag-day (reject-unsigned from day one) would take fraud detection down for every not-yet-upgraded validator, so the soft-verify window is required.

## 7. Open decisions (need owner input)

- **Auditor set policy**: any registered relay, or a curated subset? (§4 assumes "any registered relay in good standing".)
- **Should validators be relays at all** (Option A) vs. a dedicated auditor registry (Option B)? Operational vs. code cost.
- **PoR alternative**: replace byte-return with a challenge-response proof-of-retrievability so audits stay permissionless *and* leak nothing — larger, but removes the confidentiality question entirely. Worth weighing before committing to A/B.
- The protocol is currently **specified nowhere** (absent from the storage whitepaper's RPC list) — whichever option lands should be written up.

## 8. Interim shipped (cbfs#122)

`AuditGetShard` wrapped in `allow_read_probe` (it was the one read op bypassing the COW-2311 probe limiter, letting an attacker BLAKE3 a full shard per unthrottled request). Non-regressive: bytes still returned, fraud detection intact. Does **not** close the disclosure — that is §5.
