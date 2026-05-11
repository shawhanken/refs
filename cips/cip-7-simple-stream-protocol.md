---
title: "CIP-7: Simple Stream Protocol (r2)"
description: One actor-native streaming protocol with deterministic signatures, bounded replay, header filters, VM-level payload encryption, CBY-native per-epoch key billing, and optional timer-driven ingestion. r2 reallocates Stream Key Manager from 0x06 to 0x12 to resolve a long-standing conflict with code's DUAL_BASEFEE at 0x06.
icon: rss
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-02-17
  **Updated:** 2026-05-11 (r2)
  **Requires:** CIP-2 (Off-Chain Compute), CIP-3 (Dual-Metered Gas), CIP-5 (Timers)
</Note>

> **Revision history**
>
> - **r2 (2026-05-11)** — **Stream Key Manager system actor address moved `0x06` → `0x12`**. The original v1 draft claimed `0x06`, but `node/runner/src/system_actors.rs:23` has held `0x06 = DUAL_BASEFEE` (CIP-3) since well before CIP-7 was first drafted. This was a long-standing CIP-7-vs-code drift, deferred through the v2 alignment round 6 (2026-04-21) and the v2.r2 system actor segment shift (2026-05-11). With the v2.r2 sequence completing at `0x11 = PAYMENT_GATE` (CIP-18 r2), `0x12` is the next free single-byte slot and is the canonical home for Stream Key Manager. All references to the system actor address (§4 table + body prose) have been updated from `0x06` to `0x12`. The **internal storage prefix `0x6`** used inside the actor's own KV namespace (§5.x storage layout) is **unchanged** — it is an internal convention within the actor's storage trie, orthogonal to the system actor address. CIP-18 r2 §22 cross-reference and `wiki/drift.md` "CIP-7 0x06 conflict" entry are now resolved by this revision.
> - **r1 (initial, 2026-02-17)** — Original Simple Stream Protocol draft.

## Summary

This CIP defines one simple streaming protocol for Cowboy.

A `StreamActor` is the canonical feed primitive. Publishers append ordered messages to a stream. Consumers use push, pull, or push-with-pull-fallback delivery. Filtering is deterministic and evaluated only on message headers. The protocol stores payloads inline with a bounded on-chain replay window.

For paid streams, encryption and decryption are VM-level host functions and key issuance is a native platform billing event settled in `CBY`. Keys are scoped to accounts so multiple authorized actors can consume the same entitlement. The protocol collects a configurable fee on every key-epoch purchase.

## Abstract

CIP-7 standardizes:

- One `StreamMessage` format for news, pricing, alerts, and other stream kinds
- Explicit message versioning for forward compatibility
- Strictly increasing per-stream sequence numbers with no gaps
- Subscription and delivery semantics for `PUSH`, `PULL`, and `PUSH_WITH_PULL_FALLBACK`
- A deterministic JSON filter DSL over headers/tags
- A bounded replay window (`10,000` messages) with explicit `CURSOR_TOO_OLD`
- Optional timer-driven ingestion through CIP-2 runners
- Single active publisher key with deterministic key rotation cutover
- Optional subscriber-paid access with VM-level encryption, on-chain entitlements, epoch keying, and native `CBY` billing

## Motivation

CIP-7 optimizes for:

- Fast deployment with one actor pattern
- Real-time multicast delivery
- Deterministic replay and filtering behavior
- Practical support for news feeds and higher-volume pricing via micro-batching
- Platform-managed encryption so actors never implement crypto
- Native `CBY` value capture from paid stream economics

## Design Goals

- One protocol, one actor model
- Deterministic behavior for sequence, signing, filters, and replay
- Push and pull both first-class
- Explicit resource bounds for storage and fan-out work
- Optional ingestion without changing core stream semantics
- VM-level encryption/decryption primitives for paid mode
- Native per-key-epoch billing with protocol fee support
- Account-scoped keys with sponsored purchases (`payer != beneficiary`)
- Rolling entitlement windows

## Non-goals

- Permanent storage guarantees
- Exactly-once delivery
- Ack/retry protocol in core spec
- Payload-level query language
- External payload URI hosting guarantees
- Actor-defined custom cryptography for paid streams
- Custom billing assets beyond `CBY` in v1
- Off-protocol key marketplaces or resale
- On-chain key escrow or multi-operator key distribution (future CIP)
- Refundable prepaid balances (future CIP)

## Protocol Constants

- `MAX_INLINE_PAYLOAD_BYTES = 16_384` (16 KiB)
- `DEFAULT_RING_BUFFER_CAPACITY = 10_000`
- `MAX_GET_SINCE_LIMIT = 500`
- `DEFAULT_MAX_SUBSCRIBERS = 10_000`
- `DEFAULT_INGEST_INTERVAL_BLOCKS = 1`
- `DEFAULT_KEY_EPOCH_BLOCKS = 600`
- `BILLING_ASSET = CBY` (paid mode v1 REQUIRED)
- `MAX_PROTOCOL_FEE_BPS = 5_000` (50% cap)
- `CONTENT_CIPHER = XCHACHA20_POLY1305` (paid mode v1 REQUIRED)
- `NONCE_BYTES = 24`
- `TAG_BYTES = 16`
- `MAX_EFFECTIVE_PLAINTEXT_BYTES = 16_344` (16,384 - 24 - 16)
- `DEFAULT_MIN_PURCHASE_EPOCHS = 1`
- `MAX_ACCOUNT_KEYS_PER_ACCOUNT = 8`
- `MAX_ACTOR_AUTHORIZATIONS_PER_STREAM = 64`

## Definitions

- **StreamActor**: Actor implementing this CIP's interface
- **StreamMessage**: Canonical message envelope with ordered sequence
- **Cursor**: Last consumed sequence used with `get_since`
- **Header filter**: Deterministic filter over `kind`, `tags`, `sequence`, `timestamp_unix_ms`
- **Head sequence**: Latest published sequence
- **Floor sequence**: Oldest retained sequence in ring buffer
- **Key epoch**: Time window (measured in blocks) during which a single content encryption key is active
- **Beneficiary account**: Account that receives key-epoch entitlement and decryption access
- **Payer account**: Account charged in `CBY` for entitlement extension (may differ from beneficiary)
- **Account key**: Account-scoped X25519 key registration used for wrapped epoch-key delivery
- **Rolling entitlement window**: `active_until_key_epoch` upper bound per `(stream_id, beneficiary_account)`

## Stream Model

Each stream is represented by one actor with:

- `stream_id`
- `head_sequence` (starts at `0`; first publish becomes `1`)
- `floor_sequence` (starts at `1`; advances as pruning occurs)
- single active `publisher_key`
- key schedule history for signature verification across rotations
- `ring_buffer_capacity` (default `10,000`)
- `max_subscribers`
- `subscription_policy`
- push delivery work limits
- optional ingestion configuration
- optional paid-mode configuration for VM-managed encryption and key-access billing

## Platform Architecture (Paid Mode)

Paid stream encryption and billing are handled by a **Stream Key Manager** system actor and **VM-level host functions**, not by actor code. This eliminates per-actor crypto overhead and makes every decrypted epoch a native `CBY` billing event.

### Stream Key Manager System Actor

A new system actor is added at deterministic seed `0x12` (r2; original v1 draft claimed `0x06` but code allocates `0x06 = DUAL_BASEFEE` per CIP-3):

| Seed | System Actor |
|------|-------------|
| `0x01` | Runner Registry |
| `0x02` | Job Dispatcher |
| `0x03` | Result Verifier |
| `0x04` | Secrets Manager |
| `0x05` | TEE Verifier |
| `0x06` | DualBasefee (CIP-3) |
| `0x07` | Entitlement Registry |
| `0x08` | Treasury |
| `0x09` | Governance |
| `0x0A` | Storage Manager (CIP-9) |
| `0x0B` | Relay Registry (CIP-9) |
| `0x0C` | Session Actor (CIP-8) |
| `0x0D` | Route Registry (CIP-14 v2.r2) |
| `0x0E` | Gateway Registry (CIP-14 v2.r2) |
| `0x0F` | Receipt Registry (CIP-14 v2.r2) |
| `0x10` | Container Registry (CIP-10 v2.r2) |
| `0x11` | Payment Gate (CIP-18 r2) |
| **`0x12`** | **Stream Key Manager (this CIP, r2)** |

The Stream Key Manager is the single authority for:

- Epoch content-key derivation and storage
- Account key registration
- Actor authorization for account-scoped decryption
- Entitlement tracking and `CBY` billing
- Protocol fee collection

### HostApi Extensions

Four new methods are added to the `HostApi` trait, exposed to actor Python code as VM host functions:

```rust
fn stream_encrypt(
    &mut self,
    stream_id: &[u8],
    key_epoch: u64,
    aad: &[u8],
    plaintext: &[u8],
) -> HostResult<Bytes>;

fn stream_decrypt(
    &mut self,
    stream_id: &[u8],
    beneficiary_account: &[u8],
    key_epoch: u64,
    ciphertext: &[u8],
    aad: &[u8],
) -> HostResult<Bytes>;

fn acquire_epoch_access(
    &mut self,
    params: &[u8],  // CBOR-encoded AcquireEpochAccessParams
) -> HostResult<Bytes>;  // CBOR-encoded KeyAccessReceipt

fn register_account_key(
    &mut self,
    params: &[u8],  // CBOR-encoded RegisterAccountKeyParams
) -> HostResult<Bytes>;  // CBOR-encoded AccountKeyRegistration
```

These are synchronous host calls — the actor calls `stream_encrypt(...)` and gets ciphertext back in the same execution frame with no message-passing overhead.

### Storage Layout

The Stream Key Manager uses storage prefix `0x6` under its system actor address `0x12`:

```
0x6 || 0x01 || keccak(stream_id)                                     -> PaidStreamConfig
0x6 || 0x02 || keccak(account)                                       -> [AccountKeyRegistration...]
0x6 || 0x03 || keccak(account) || keccak(actor) || keccak(stream_id) -> ActorAuthorization
0x6 || 0x04 || keccak(stream_id) || keccak(account)                  -> Entitlement
0x6 || 0x05 || keccak(stream_id) || key_epoch_be64                   -> epoch_content_key (encrypted at rest)
```

> **Namespace note (r2):** The leading `0x6` here is an **internal storage key prefix** inside this actor's own KV namespace — orthogonal to the actor's system address `0x12`. The choice of `0x6` as the prefix is historical (originally aligned with the proposed system actor address before r2 reallocated to `0x12`); kept here to avoid storage-key migration. It does **not** collide with the system actor at `0x06` (`DUAL_BASEFEE`) because system actor addresses and per-actor storage key prefixes live in disjoint namespaces (20-byte account addresses in the global account trie vs. arbitrary-length keys inside a single actor's storage trie).

All state is committed through the standard MPT path and included in `state_root`.

## Data Types

### 1. StreamConfig

Fields:

- `stream_id` (bytes32/string)
- `owner` (address)
- `publisher_key` (bytes): active ed25519 public key
- `current_signing_key_id` (uint64): key identifier for `publisher_key`
- `ring_buffer_capacity` (uint32): default `10,000`
- `max_subscribers` (uint32): default `10,000`
- `subscription_policy` (enum): `PUBLIC` | `PRIVATE_ALLOWLIST`
- `max_push_deliveries_per_block` (uint32)
- `max_push_cycles_per_block` (uint64)
- `access_mode` (enum): `OPEN` | `PLATFORM_MANAGED` (alias: `SUBSCRIBER_PAID`)
- `paid_stream_config` (optional `PaidStreamConfig`)
- `ingestion` (optional `IngestionConfig`)

Rules:

- `ring_buffer_capacity` MUST be > 0
- `current_signing_key_id` MUST be >= 1
- `max_subscribers` MUST be > 0
- Push limits MUST be finite and non-zero
- `SUBSCRIBER_PAID` is an accepted alias for `PLATFORM_MANAGED` for migration compatibility; implementations MUST treat them as identical
- If `access_mode == PLATFORM_MANAGED`, `paid_stream_config` MUST be set
- If `access_mode == OPEN`, `paid_stream_config` MUST be absent

### 2. PaidStreamConfig (optional)

Fields:

- `fee_per_key_epoch_cby` (uint64): publisher amount per newly covered key epoch, in CBY wei
- `protocol_fee_bps` (uint16): basis points applied on top of publisher amount
- `publisher_treasury` (address): where publisher revenue is credited
- `protocol_treasury` (address): where protocol fee is credited
- `key_epoch_blocks` (uint32): default `600`
- `content_cipher` (enum/string): `XCHACHA20_POLY1305` (v1 REQUIRED)
- `key_scope` (enum): `ACCOUNT` (v1 REQUIRED)
- `min_purchase_epochs` (uint32): default `1`

Rules:

- `fee_per_key_epoch_cby` MUST be > 0
- `protocol_fee_bps` MUST be in `[0, MAX_PROTOCOL_FEE_BPS]`
- `key_epoch_blocks` MUST be > 0
- `content_cipher` MUST be `XCHACHA20_POLY1305` in this CIP version
- `key_scope` MUST be `ACCOUNT` in this CIP version (future CIPs may introduce `ACTOR` or other scoping)
- `min_purchase_epochs` MUST be >= 1; purchases covering fewer than `min_purchase_epochs` newly-charged epochs MUST fail with `MIN_PURCHASE_NOT_MET`
- `publisher_treasury` MUST be a valid account address
- `protocol_treasury` is set at genesis or via governance; publishers MAY NOT override it

### 3. StreamMessage

Fields:

- `version` (uint8): MUST be `1` for this CIP revision
- `stream_id` (bytes32/string)
- `sequence` (uint64)
- `timestamp_unix_ms` (uint64)
- `kind` (string): examples `news`, `price_batch`, `alert`
- `content_type` (string): payload media type, default `application/json`
- `tags` (`map<string, string | float64 | bool>`)
- `payload_format` (enum): `PLAINTEXT` | `CIPHERTEXT`
- `payload_inline` (bytes): MUST be ≤ 16 KiB
- `payload_hash` (bytes32): `SHA-256(payload_inline)`
- `key_epoch` (optional uint64): REQUIRED when `payload_format == CIPHERTEXT`
- `signing_key_id` (uint64): publisher-key identifier active at this sequence
- `publisher_sig` (bytes): ed25519 signature over canonical signing bytes

Rules:

- `version` MUST be `1`
- `payload_inline` is REQUIRED
- `payload_inline` size MUST be ≤ `MAX_INLINE_PAYLOAD_BYTES`
- `sequence` MUST be strictly increasing and contiguous (`prev + 1`)
- `payload_hash` MUST match `payload_inline`
- If `payload_format == CIPHERTEXT`, subscribers require the corresponding epoch key to decrypt
- In `PLATFORM_MANAGED` mode, stream MUST publish `CIPHERTEXT` messages
- In `PLATFORM_MANAGED` mode, ciphertext payloads MUST be produced by the `stream_encrypt` VM host function
- In `CIPHERTEXT` mode, `payload_inline` MUST be encoded as: `nonce(24 bytes) || ciphertext_with_tag`
- In `CIPHERTEXT` mode, the 16 KiB limit applies to the full encrypted envelope (`nonce + ciphertext + tag`)
- For `XCHACHA20_POLY1305`, effective maximum plaintext size is `16_384 - 24 - 16 = 16_344` bytes

### 4. Subscription

Fields:

- `subscriber` (address)
- `mode` (enum): `PUSH`, `PULL`, `PUSH_WITH_PULL_FALLBACK`
- `filter` (JSON Filter DSL)
- `created_at_sequence` (uint64)
- `account_key_id` (optional uint64): preferred account key for wrapped epoch-key delivery; hint only
- `status` (enum): `ACTIVE`, `PAUSED`, `CANCELLED`

Rules:

- `subscribe` MUST validate filter schema before activation
- New subscription MUST fail with `SUBSCRIBER_CAP_REACHED` when full
- In `PRIVATE_ALLOWLIST`, non-allowlisted addresses MUST fail with `SUBSCRIPTION_NOT_ALLOWED`
- Subscription controls **delivery** (push/pull routing). In `PLATFORM_MANAGED` mode, decryption access is controlled separately by entitlements on the Stream Key Manager.
- `account_key_id` is an optional hint that identifies the subscriber's preferred account key for key wrapping. It does NOT grant entitlement and does NOT trigger billing. It is informational for SDK and indexer convenience.
- In `OPEN` mode, no payment or entitlement is required for subscription.

### 5. Entitlement (paid mode)

Fields:

- `stream_id` (bytes32/string)
- `beneficiary_account` (address)
- `active_until_key_epoch` (uint64)

Semantics:

- Entitlement is rolling and account-scoped
- Account is entitled for all key epochs `<= active_until_key_epoch`
- Purchasing access to epoch `T` when current entitlement is `E` charges for epochs `E+1..T` inclusive
- Repeated calls for already-entitled epochs are idempotent and free
- Past epochs remain accessible indefinitely within the window
- Entitlement is per `(stream_id, beneficiary_account)` pair

### 6. AccountKeyRegistration (paid mode)

Fields:

- `account` (address)
- `account_key_id` (uint64): auto-incrementing per account
- `scheme` (string): `"X25519"` (v1 REQUIRED)
- `public_key` (bytes): X25519 public key for epoch key wrapping
- `status` (enum): `ACTIVE` | `REVOKED`
- `registered_at` (uint64): block height

Rules:

- Keys are owned by the **account**, not by any actor
- An account MAY register up to `MAX_ACCOUNT_KEYS_PER_ACCOUNT` keys
- `account_key_id` is assigned sequentially starting at `1`
- Revoked keys MUST NOT be used for future key wrapping or decryption
- Key registration MUST be signed by the account holder

### 7. ActorAuthorization (paid mode)

Fields:

- `account` (address)
- `actor` (address)
- `stream_id` (bytes32)
- `scope` (enum): `STREAM_DECRYPT`
- `status` (enum): `ACTIVE` | `REVOKED`
- `granted_at` (uint64): block height

Rules:

- An actor MUST be explicitly authorized by an account to decrypt on that account's behalf for a specific stream
- Authorization is per `(account, actor, stream_id)` triple
- An account MAY authorize up to `MAX_ACTOR_AUTHORIZATIONS_PER_STREAM` actors per stream
- Revocation is immediate: revoked actors MUST NOT decrypt from the next block onward
- The account owner's own actors (where `actor.creator == account`) are auto-authorized unless explicitly revoked

### 8. KeyAccessReceipt (paid mode)

Fields:

- `stream_id` (bytes32)
- `beneficiary_account` (address)
- `payer_account` (address)
- `from_key_epoch` (uint64): first newly-charged epoch (E+1)
- `to_key_epoch` (uint64): last charged epoch (T)
- `epochs_charged` (uint64): T - E (may be 0 if idempotent)
- `publisher_amount_cby` (uint64)
- `protocol_fee_cby` (uint64)
- `total_amount_cby` (uint64)

### 9. IngestionConfig (optional)

Fields:

- `enabled` (bool)
- `interval_blocks` (uint32): default `1`
- `task_definition` (object): CIP-2 task request
- `result_schema` (object)
- `transform_method` (optional string)
- `num_runners` (uint8)
- `proof_type` (enum from CIP-2)

Rules:

- When enabled, actor MUST schedule recurring timer callbacks
- Actor MUST submit CIP-2 tasks using configured `num_runners` and `proof_type`
- Ingestion failures MUST NOT increment sequence

## Canonical Hashing and Signing (Normative)

This CIP fixes signature and encoding rules now.

- `signature_scheme`: ed25519
- `hash_alg`: SHA-256
- `canonical_encoding`: Deterministic CBOR (RFC 8949 canonical form)

Signing payload object keys and values:

- `stream_id`
- `version`
- `sequence`
- `timestamp_unix_ms`
- `kind`
- `content_type`
- `tags`
- `payload_format`
- `payload_hash`
- `key_epoch` (or `null` when `payload_format == PLAINTEXT`)
- `signing_key_id`

Procedure:

1. Compute `payload_hash = SHA-256(payload_inline)`
2. Build the signing payload object with exactly the keys above
3. Encode using deterministic CBOR
4. Sign bytes with ed25519 private key
5. Store signature in `publisher_sig`

Verification:

- Consumer MUST recompute `payload_hash`
- Consumer MUST rebuild deterministic-CBOR signing payload
- Consumer MUST verify `publisher_sig` against key schedule entry effective at that sequence
- Consumers MAY resolve key schedule via `get_key_at_sequence` or cached `get_key_history` output

Tag canonicalization for signing payload:

- `tags` keys MUST be CBOR text strings.
- String tag values MUST be CBOR text strings.
- Boolean tag values MUST be CBOR `true`/`false`.
- Numeric tag values MUST be finite IEEE-754 binary64 and encoded as CBOR float64 (major type 7, additional info 27).
- Producers MUST NOT encode numeric tags as CBOR integers in signing payload bytes.

Ciphertext nonce format:

- For `XCHACHA20_POLY1305`, nonce MUST be exactly 24 bytes.
- Nonce MUST be carried inline as the first 24 bytes of `payload_inline`.
- In `PLATFORM_MANAGED` mode, nonce generation is handled by the VM and incorporates `actor_nonce` (per-actor monotonic counter) to prevent reuse. Nonce reuse with the same content key is forbidden.

## Actor Interface

### Required Methods

#### `publish(kind, content_type?, tags, payload_format, payload_inline, key_epoch?, publisher_sig)`

Behavior:

1. Validate payload size ≤ 16 KiB
2. If `content_type` omitted, set `content_type = application/json`
3. Compute `payload_hash = SHA-256(payload_inline)`
4. Validate `payload_format` and `key_epoch` consistency
5. If `PLATFORM_MANAGED` mode, require `payload_format == CIPHERTEXT`
6. Validate signature against active publisher key using signing payload that includes computed `payload_hash`
7. Set `next_sequence = head_sequence + 1`
8. Persist message at `next_sequence` with `version=1`, `content_type`, and `signing_key_id`
9. Update `head_sequence = next_sequence`
10. Prune ring buffer deterministically (see pruning section)
11. Emit `StreamMessagePublished`
12. Enqueue message for push delivery

Paid mode publish flow:

1. Publisher actor composes plaintext payload, metadata, tags, and kind.
2. Actor computes `key_epoch = floor(block_height / key_epoch_blocks)`.
3. Actor calls `stream_encrypt(stream_id, key_epoch, aad, plaintext)` — a VM host function.
4. VM returns ciphertext envelope (`nonce || ciphertext || tag`).
5. Actor sets `payload_format = CIPHERTEXT`, `payload_inline = ciphertext_envelope`.
6. Actor signs and calls `publish(...)` as normal.

#### `subscribe(mode, filter, start_cursor?, account_key_id?)`

Behavior:

- Validate `mode` and filter schema
- Enforce subscription policy and subscriber cap
- Create or update subscription
- If `start_cursor` omitted, set to current `head_sequence`
- Emit `SubscriberUpdated`

Re-subscribe / update semantics:

- `subscribe` is an upsert keyed by `subscriber`.
- On update, subscriber MAY change `mode`, `filter`, and `account_key_id`.
- `created_at_sequence` MUST remain unchanged on update.
- `start_cursor` applies only on create; on update it is ignored.

Note: In `PLATFORM_MANAGED` mode, subscription controls delivery routing only. Billing occurs on key-access acquisition (via `acquire_epoch_access`), not on subscription creation or renewal. The `account_key_id` parameter is an optional hint for key wrapping preference and does not trigger any payment.

#### `unsubscribe()`

Behavior:

- Set status to `CANCELLED`
- Emit `SubscriberUpdated`

#### `renew_subscription(target_key_epoch, beneficiary_account?, payer_account?, account_key_id?)`

Behavior:

- Convenience wrapper over native `acquire_epoch_access` for SDK ergonomics.
- If `access_mode != PLATFORM_MANAGED`, fail with `NOT_PLATFORM_MANAGED_STREAM`.
- If `beneficiary_account` omitted, defaults to caller account.
- If `payer_account` omitted, defaults to caller account.
- If caller has no active subscription, fail with `PAYMENT_REQUIRED` (subscribe first, then acquire access).
- If `account_key_id` provided, updates the subscription's `account_key_id` hint.
- MUST delegate to `acquire_epoch_access` on the Stream Key Manager and return the resulting `KeyAccessReceipt`.

Notes:

- This method is OPTIONAL. Clients MAY call `acquire_epoch_access` directly via the platform host function.
- Billing occurs on key-access acquisition, not on subscription creation. This method exists solely for backward compatibility and SDK convenience.

#### `get_since(cursor, limit)`

Inputs:

- `cursor`: last consumed sequence
- `limit`: `1..500`

Behavior:

- Reject invalid limit with `LIMIT_EXCEEDED`
- If `cursor < floor_sequence - 1`, return `CURSOR_TOO_OLD`
- Return messages where `sequence > cursor`, ascending
- Return at most `limit`

Paid mode pull rule:

- `get_since` returns ciphertext messages regardless of entitlement status.
- Entitlement gates decryption key access, not ciphertext retrieval.

#### `get_head()`

Returns:

- `head_sequence`
- `floor_sequence`
- stream metadata required for consumers

#### `rotate_publisher_key(new_key)`

Behavior:

- Owner-only
- Allocate `new_signing_key_id = current_signing_key_id + 1`
- Set `effective_sequence = head_sequence + 1`
- New key is active from `effective_sequence` onward
- Append key schedule entry `{signing_key_id, pubkey, effective_sequence}`
- Emit `PublisherKeyRotated(old_key, new_key, old_signing_key_id, new_signing_key_id, effective_sequence)`

#### `get_key_at_sequence(sequence)`

Returns key schedule resolution for verification:

- `signing_key_id`
- `publisher_key`
- `effective_sequence`

#### `get_key_history(from_signing_key_id?, limit?)`

Returns ordered key schedule entries for batch verification use.

#### `announce_key_epoch(key_epoch)`

Behavior:

- Owner-only
- Announces key epoch progression metadata on-chain
- `key_epoch` MUST be non-decreasing relative to previous announcement
- Emit `KeyEpochRotated(stream_id, key_epoch, effective_block_height, announced_by)`

Notes:

- This method does not publish key material on-chain.
- It anchors key-epoch progression for indexers, subscribers, and auditing.

#### `set_subscription_policy(policy)`

Behavior:

- Owner-only
- Set `PUBLIC` or `PRIVATE_ALLOWLIST`

#### `allowlist_add(address)` / `allowlist_remove(address)`

Behavior:

- Owner-only
- Manage allowlist used when policy is `PRIVATE_ALLOWLIST`

### Platform Key Management Methods

These methods are exposed as VM host functions and backed by the Stream Key Manager system actor. They are available to any actor during execution.

#### `stream_encrypt(stream_id, key_epoch, aad, plaintext) -> ciphertext`

Caller: Publisher actor (or any actor with publish rights on the stream).

Behavior:

1. Validate `access_mode == PLATFORM_MANAGED` for this stream.
2. Derive the epoch content key: `content_key = KDF(master_seed, stream_id, key_epoch)`.
3. Generate a deterministic nonce: `nonce = HKDF-Expand(content_key, stream_id || key_epoch || actor_nonce, 24)`.
4. Encrypt: `ciphertext = XChaCha20-Poly1305-Encrypt(content_key, nonce, aad, plaintext)`.
5. Return `nonce(24) || ciphertext || tag(16)`.

Gas cost:

- Cycles: `500 + (plaintext.len() * 2)`
- Cells: output envelope size

Rules:

- Actors MUST NOT implement their own encryption for `PLATFORM_MANAGED` streams.
- `plaintext.len()` MUST be ≤ `MAX_EFFECTIVE_PLAINTEXT_BYTES` (16,344 bytes).
- `aad` SHOULD include `stream_id`, `sequence`, `key_epoch`, `kind`, `content_type` for binding.
- Nonce reuse with the same content key is prevented by incorporating `actor_nonce` (auto-incremented).

#### `stream_decrypt(stream_id, beneficiary_account, key_epoch, ciphertext, aad) -> plaintext`

Caller: Any actor authorized by `beneficiary_account` for this stream.

Behavior:

1. Resolve calling actor's address from execution context.
2. Verify `ActorAuthorization` for `(beneficiary_account, caller_actor, stream_id)` is `ACTIVE`.
3. Verify `Entitlement` for `(stream_id, beneficiary_account)` includes `key_epoch` (i.e., `key_epoch ≤ active_until_key_epoch`).
4. Derive epoch content key (same KDF as encrypt).
5. Extract nonce from first 24 bytes of `ciphertext`.
6. Decrypt: `plaintext = XChaCha20-Poly1305-Decrypt(content_key, nonce, aad, ciphertext_body)`.
7. Return `plaintext`.

Gas cost:

- Cycles: `500 + (ciphertext.len() * 2)`
- Cells: plaintext output size

Error conditions:

- `ACTOR_NOT_AUTHORIZED_FOR_ACCOUNT` — actor lacks authorization
- `ENTITLEMENT_REQUIRED` — epoch not within entitlement window
- `DECRYPTION_FAILED` — ciphertext tampered or wrong key
- `NOT_PLATFORM_MANAGED_STREAM` — stream is `OPEN`

#### `acquire_epoch_access(stream_id, beneficiary_account, payer_account, target_key_epoch) -> KeyAccessReceipt`

Caller: Any actor (on behalf of `payer_account`). The transaction MUST be signed by `payer_account` or the payer must have delegated spending authority.

Behavior:

1. Validate `access_mode == PLATFORM_MANAGED` for this stream.
2. Resolve current entitlement: `E = active_until_key_epoch` for `(stream_id, beneficiary_account)`. If no entitlement exists, `E = current_key_epoch - 1` (no free retroactive access).
3. If `target_key_epoch ≤ E`: return idempotent receipt with `epochs_charged = 0`, `total_amount_cby = 0`. Emit `EpochAccessIdempotent`.
4. Compute `epochs_charged = target_key_epoch - E`.
5. If `epochs_charged < min_purchase_epochs`, fail with `MIN_PURCHASE_NOT_MET`.
6. Compute fees:
   ```
   publisher_amount = epochs_charged * fee_per_key_epoch_cby
   protocol_fee     = floor(publisher_amount * protocol_fee_bps / 10_000)
   total            = publisher_amount + protocol_fee
   ```
7. Transfer `total` CBY from `payer_account` balance. Fail with `INSUFFICIENT_CBY_BALANCE` if insufficient.
8. Credit `publisher_amount` to `publisher_treasury`.
9. Credit `protocol_fee` to `protocol_treasury`.
10. Set `active_until_key_epoch = target_key_epoch` for `(stream_id, beneficiary_account)`.
11. Emit `EpochAccessPurchased`.
12. Return `KeyAccessReceipt`.

Gas cost:

- Cycles: `5,000` (fixed)
- Cells: `500`

Rules:

- `payer_account` MAY differ from `beneficiary_account` (sponsorship).
- Entitlement accrues to `beneficiary_account`, never to `payer_account`. The payer has no implicit access to decryption keys.
- Repeated calls for already-entitled epochs MUST be idempotent and non-charging.
- `target_key_epoch` MUST be >= `current_key_epoch`. Purchasing purely historical epochs without current coverage is not allowed in v1.
- This method is the **canonical and only billing point** for paid stream decryption.

#### `register_account_key(account, scheme, public_key) -> AccountKeyRegistration`

Caller: Account holder.

Behavior:

1. Verify transaction is signed by `account`.
2. Validate `scheme` is `"X25519"` (v1).
3. Validate `public_key` length (32 bytes for X25519).
4. Check account has fewer than `MAX_ACCOUNT_KEYS_PER_ACCOUNT` active keys.
5. Assign `account_key_id = next_id` for this account (auto-increment).
6. Store `AccountKeyRegistration`.
7. Emit `AccountKeyRegistered`.
8. Return registration.

Gas cost:

- Cycles: `2,000`
- Cells: `200`

#### `authorize_actor(account, actor, stream_id) -> ActorAuthorization`

Caller: Account holder.

Behavior:

1. Verify transaction is signed by `account`.
2. Validate actor address exists.
3. Check authorization count for `(account, stream_id)` is below `MAX_ACTOR_AUTHORIZATIONS_PER_STREAM`.
4. Store `ActorAuthorization` with `status = ACTIVE`.
5. Emit `ActorAuthorizationGranted`.

Gas cost:

- Cycles: `1,000`
- Cells: `100`

#### `revoke_actor(account, actor, stream_id)`

Caller: Account holder.

Behavior:

1. Verify transaction is signed by `account`.
2. Set `ActorAuthorization.status = REVOKED`.
3. Emit `ActorAuthorizationRevoked`.

Gas cost:

- Cycles: `500`
- Cells: `50`

#### `revoke_account_key(account, account_key_id)`

Caller: Account holder.

Behavior:

1. Verify transaction is signed by `account`.
2. Set `AccountKeyRegistration.status = REVOKED`.
3. Emit `AccountKeyRevoked`.

Gas cost:

- Cycles: `500`
- Cells: `50`

## Push Delivery Semantics

- Push is best-effort multicast
- Delivery is at-least-once
- No protocol-level ack or retry
- Push message includes full `StreamMessage`, including full inline payload
- Consumers MUST deduplicate by `(stream_id, sequence)`

Paid mode delivery rule:

- Push delivery is a transport concern and MAY deliver ciphertext regardless of key entitlement.
- Decryption remains gated by account entitlement and actor authorization on the Stream Key Manager.

### Push Work Bounds and Economics

- Stream actor execution pays push fan-out costs
- Owner is responsible for funding actor operations
- Actor MUST enforce:
  - `max_push_deliveries_per_block`
  - `max_push_cycles_per_block`
- Undelivered subscribers remain pending for subsequent blocks
- Push delivery MUST never exceed configured per-block bounds

## `PUSH_WITH_PULL_FALLBACK` Semantics

`PUSH_WITH_PULL_FALLBACK` means:

- Actor behavior is same as `PUSH` (best-effort, no retries)
- Subscriber behavior additionally includes periodic pull catch-up using `get_since`
- Fallback is subscriber-driven, not actor-driven
- No automatic mode switching is performed by actor

## Pull Delivery Semantics

- Pull consumers track local cursor
- Consumers call `get_since(cursor, limit)`
- Stale cursors are explicit via `CURSOR_TOO_OLD`

Paid mode pull rule:

- `get_since` returns ciphertext messages regardless of entitlement status.
- Entitlement gates key issuance/decryption, not ciphertext retrieval.

## Payments and Key Management (Normative)

This section defines how subscriber-paid monetization works with VM-level encryption and native `CBY` billing.

### On-chain entitlements

- In `PLATFORM_MANAGED` mode, entitlement is tracked per `(stream_id, beneficiary_account)` via `active_until_key_epoch` on the Stream Key Manager
- Key epoch is computed as `floor(block_height / paid_stream_config.key_epoch_blocks)`
- Entitlement window is rolling: access check for epoch `k` succeeds iff `k ≤ active_until_key_epoch`

### Payload confidentiality

- Stream publishes inline `CIPHERTEXT` payloads in `PLATFORM_MANAGED` mode
- Ciphertext remains globally readable, but plaintext requires key access and actor authorization
- Encryption/decryption MUST use VM-native host functions

### Epoch content keys

- Platform manages one content key per stream per key epoch
- `StreamMessage.key_epoch` binds each message to a key epoch
- Actor code MUST NOT implement custom content-key cryptography in `PLATFORM_MANAGED` mode

### Key distribution flow

1. Caller invokes `acquire_epoch_access` with `stream_id`, `beneficiary_account`, `payer_account`, and `target_key_epoch`
2. Platform resolves current entitlement end `E`
3. If `target_key_epoch ≤ E`, no charge (idempotent)
4. Else compute `epochs_charged = target_key_epoch - E`; reject if below `min_purchase_epochs`
5. Bill for newly covered epochs `E+1..target_key_epoch`:
   - `publisher_amount = epochs_charged * fee_per_key_epoch_cby`
   - `protocol_fee = floor(publisher_amount * protocol_fee_bps / 10_000)`
   - `total = publisher_amount + protocol_fee`
6. Transfers `total` in `CBY` from `payer_account`
7. Credits publisher and protocol treasuries
8. Sets `active_until_key_epoch = target_key_epoch`
9. Emits `EpochAccessPurchased`

### Account-scoped keys and actor reuse

- Keys are registered per account (not per actor or per subscription)
- Authorized actors MAY decrypt on behalf of that account for specific streams
- Actor authorization and account key revocation are immediate
- This model means one subscription payment covers all of an account's actors consuming the same stream

### Sponsored purchases

- `payer_account` MAY be any funded account, including a third party
- `CBY` is debited from `payer_account`; entitlement accrues to `beneficiary_account`
- The payer has no implicit access to decryption keys
- Use cases: employer sponsors employee access, DAO treasury funds member access, trial/promotional grants

### Protocol fee

- Configurable per-stream at creation within `[0, MAX_PROTOCOL_FEE_BPS]`
- Additive: total cost = publisher price + protocol fee on top
- `protocol_treasury` address is set at genesis or via governance; publishers MAY NOT override it
- Protocol fee creates direct `CBY` demand proportional to paid stream usage across the ecosystem

### CBY value flow

```
Payer Account
    |
    |── publisher_amount ──> Publisher Treasury (stream owner revenue)
    |
    └── protocol_fee ──────> Protocol Treasury (ecosystem value capture)
                                |
                                |── Burned (deflationary pressure)
                                |── Staking rewards
                                └── Development fund
                                    (distribution is governance-defined)
```

### Scalability guidance

- Use epoch keys (for example, 10-minute epochs at 1-second blocks = 600 blocks) rather than per-message keys
- Rolling windows and idempotent purchase semantics avoid duplicate charging
- Model supports large subscriber sets (100, 1,000, 10,000) with stable delivery and billing overhead

## Ring Buffer Pruning (Deterministic)

State:

- `head_sequence`
- `floor_sequence`
- `ring_buffer_capacity`

On every successful publish:

1. Append message at `head_sequence + 1`
2. Set `head_sequence = head_sequence + 1`
3. If `(head_sequence - floor_sequence + 1) > ring_buffer_capacity`:
   - delete message at `floor_sequence`
   - set `floor_sequence = floor_sequence + 1`

Empty-stream rule:

- When `head_sequence == 0`, stream has no retained messages.
- In that state, pruning condition MUST NOT be evaluated.
- `get_since` MUST return an empty result set for valid limits.

Stale cursor rule:

- `cursor` is stale iff `cursor < floor_sequence - 1`

## JSON Filter DSL

Filters are evaluated only on:

- `kind`
- `tags.<key>`
- `sequence`
- `timestamp_unix_ms`

Operators:

- `eq`, `ne`, `in`, `nin`, `gte`, `lte`, `exists`

Logical forms:

- `{"all": [ ... ]}` (AND)
- `{"any": [ ... ]}` (OR)
- `{"not": { ... }}`

Example:

```json
{
  "all": [
    {"field": "kind", "op": "eq", "value": "price_batch"},
    {"field": "tags.symbol", "op": "in", "value": ["BTC", "ETH"]},
    {"field": "tags.venue", "op": "eq", "value": "coinbase"},
    {"field": "tags.confidence", "op": "gte", "value": 0.9}
  ]
}
```

Determinism constraints:

- Maximum depth: `4`
- Maximum predicates: `16`
- Unknown fields/operators MUST fail subscription validation

## Ingestion Flow (Optional)

When `ingestion.enabled == true`:

1. Timer fires every `interval_blocks` (default `1`)
2. Actor submits CIP-2 task using configured:
   - `task_definition`
   - `result_schema`
   - `num_runners`
   - `proof_type`
3. Runner callback returns result
4. Actor transforms result into publishable payloads
5. For `PLATFORM_MANAGED` mode, actor calls `stream_encrypt(...)` before publish
6. Actor calls `publish(...)` for each transformed payload
7. Actor reschedules next ingestion timer

Failure behavior:

- Increment `ingest_fail_count`
- Emit `IngestFailed(reason, timestamp_unix_ms)`
- Do not increment sequence on failed attempts

## High-Volume Pricing Guidance (Non-normative)

For 1-second block cadence, pricing streams SHOULD micro-batch:

- Publish one `price_batch` message per block
- Include multiple ticks in one inline payload
- Keep payload ≤ 16 KiB
- Use tags such as `symbol`, `venue`, `window_ms`, `count` for filtering

## Events

### `StreamMessagePublished`

- `stream_id`
- `version`
- `sequence`
- `kind`
- `content_type`
- `payload_format`
- `payload_hash`
- `key_epoch` (nullable)
- `signing_key_id`
- `timestamp_unix_ms`

### `SubscriberUpdated`

- `stream_id`
- `subscriber`
- `mode`
- `status`

### `PublisherKeyRotated`

- `stream_id`
- `old_key`
- `new_key`
- `old_signing_key_id`
- `new_signing_key_id`
- `effective_sequence`

### `EpochAccessPurchased`

- `stream_id`
- `beneficiary_account`
- `payer_account`
- `from_key_epoch`
- `to_key_epoch`
- `epochs_charged`
- `publisher_amount_cby`
- `protocol_fee_cby`
- `total_amount_cby`

### `EpochAccessIdempotent`

- `stream_id`
- `beneficiary_account`
- `target_key_epoch`
- `active_until_key_epoch`

### `AccountKeyRegistered`

- `account`
- `account_key_id`
- `scheme`
- `block_height`

### `AccountKeyRevoked`

- `account`
- `account_key_id`
- `block_height`

### `ActorAuthorizationGranted`

- `account`
- `actor`
- `stream_id`
- `scope`
- `block_height`

### `ActorAuthorizationRevoked`

- `account`
- `actor`
- `stream_id`
- `block_height`

### `KeyEpochRotated`

- `stream_id`
- `key_epoch`
- `effective_block_height`
- `announced_by` (address)

### `IngestFailed`

- `stream_id`
- `timestamp_unix_ms`
- `reason`

## Error Codes

Actor method errors:

- `INVALID_SIGNATURE`
- `PAYLOAD_TOO_LARGE`
- `INVALID_FILTER`
- `CURSOR_TOO_OLD`
- `LIMIT_EXCEEDED`
- `UNAUTHORIZED`
- `SUBSCRIBER_CAP_REACHED`
- `SUBSCRIPTION_NOT_ALLOWED`

Platform key management errors:

- `NOT_PLATFORM_MANAGED_STREAM`
- `PAYMENT_REQUIRED` — no entitlement exists and caller has not initiated a purchase
- `ACTOR_NOT_AUTHORIZED_FOR_ACCOUNT`
- `ENTITLEMENT_REQUIRED`
- `INSUFFICIENT_CBY_BALANCE`
- `INVALID_TARGET_KEY_EPOCH`
- `MIN_PURCHASE_NOT_MET`
- `DECRYPTION_FAILED`
- `INVALID_ACCOUNT_KEY`
- `ACCOUNT_KEY_LIMIT_REACHED`
- `AUTHORIZATION_LIMIT_REACHED`
- `KEY_REVOKED`

Error mapping:

- `publish`: `INVALID_SIGNATURE`, `PAYLOAD_TOO_LARGE`, `UNAUTHORIZED`
- `subscribe`: `INVALID_FILTER`, `SUBSCRIBER_CAP_REACHED`, `SUBSCRIPTION_NOT_ALLOWED`
- `renew_subscription`: `PAYMENT_REQUIRED`, `INSUFFICIENT_CBY_BALANCE`, `INVALID_TARGET_KEY_EPOCH`, `MIN_PURCHASE_NOT_MET`, `NOT_PLATFORM_MANAGED_STREAM`
- `get_since`: `LIMIT_EXCEEDED`, `CURSOR_TOO_OLD`
- `rotate_publisher_key`: `UNAUTHORIZED`
- `set_subscription_policy`: `UNAUTHORIZED`
- `allowlist_add` / `allowlist_remove`: `UNAUTHORIZED`
- `announce_key_epoch`: `UNAUTHORIZED`
- `stream_encrypt`: `NOT_PLATFORM_MANAGED_STREAM`, `PAYLOAD_TOO_LARGE`
- `stream_decrypt`: `NOT_PLATFORM_MANAGED_STREAM`, `ACTOR_NOT_AUTHORIZED_FOR_ACCOUNT`, `ENTITLEMENT_REQUIRED`, `DECRYPTION_FAILED`, `KEY_REVOKED`
- `acquire_epoch_access`: `NOT_PLATFORM_MANAGED_STREAM`, `INSUFFICIENT_CBY_BALANCE`, `INVALID_TARGET_KEY_EPOCH`, `MIN_PURCHASE_NOT_MET`
- `register_account_key`: `INVALID_ACCOUNT_KEY`, `ACCOUNT_KEY_LIMIT_REACHED`, `UNAUTHORIZED`
- `authorize_actor`: `AUTHORIZATION_LIMIT_REACHED`, `UNAUTHORIZED`
- `revoke_actor`: `UNAUTHORIZED`
- `revoke_account_key`: `UNAUTHORIZED`, `KEY_REVOKED`

## Security Considerations

- Consumers MUST verify signature and payload hash before trusting data
- Push may duplicate deliveries; consumers MUST implement idempotent handling
- Filter validation limits reduce DoS risk from pathological expressions
- Subscriber caps and push work limits reduce fan-out abuse risk
- Deterministic key-rotation cutover avoids signer ambiguity at sequence boundaries
- Paid mode decryption MUST enforce both entitlement and actor authorization checks
- Account key compromise grants access to all entitled epochs for that account across all streams; accounts SHOULD rotate keys periodically
- Revocation of actor authorization MUST immediately block future decrypt calls for that actor
- Account key revocation blocks all future wrapping and decryption tied to that key ID
- Epoch-key compromise exposes all messages encrypted under that epoch key; operators SHOULD use short key epochs to reduce blast radius
- VM-native crypto MUST use constant-time implementations audited for side-channel resistance
- Nonce uniqueness is guaranteed by incorporating `actor_nonce` into nonce derivation
- Sponsored purchases do not leak key material to the payer
- Protocol treasury address is governance-controlled; compromise of a publisher treasury does not affect protocol fee collection
- Entitlement state is on-chain and verifiable; no off-chain key service trust assumptions

## Backwards Compatibility

This CIP can be adopted independently.

Migration from prior stream implementations:

1. Map existing feed messages into `StreamMessage`
2. Reuse subscriber logic through `subscribe` + `get_since`
3. Remove dependence on retention-specific protocol primitives for core streaming
4. For actor-managed paid streams: switch `access_mode` to `PLATFORM_MANAGED` (or use `SUBSCRIBER_PAID` alias for migration compatibility), remove actor encryption code, register account keys, use `acquire_epoch_access` for billing
5. Push delivery no longer gates on entitlement — ciphertext is delivered to all subscribers regardless of payment status. Decryption is the access-control boundary, not transport.

## Reference Implementation Notes (Non-normative)

- SDK `StreamActor` should expose the full actor method set
- SDK should include convenience wrappers for `stream_encrypt`, `stream_decrypt`, and `acquire_epoch_access`
- Pruning should be O(1) amortized
- Push scheduler should use deterministic round-robin over active subscribers
- Entitlement lookup should be O(1) by `(stream_id, beneficiary_account)`
- VM host function implementations should use libsodium or equivalent audited AEAD library

## Rationale

### Why VM-level, not actor-level encryption?

Encryption at the actor level requires every paid stream to independently implement crypto in Python, paying interpreted-execution gas costs for operations that should be native. A 16 KiB encrypt costs ~180,000 cycles in Python vs ~33,000 cycles as a VM host function. Beyond gas savings, VM-level crypto eliminates an entire class of actor bugs (nonce reuse, wrong cipher mode, key leakage in actor storage).

### Why VM host functions, not system actor messages?

System actor messages require deferred transaction overhead (send message, wait for callback in next block). VM host functions are synchronous — the actor calls `stream_encrypt(...)` and gets ciphertext back in the same execution frame. This is critical for the publish path.

### Why account-scoped, not actor-scoped keys?

An account is the natural billing entity. Actors are programs; accounts are economic agents. If account A deploys five consumer actors that all read the same price feed, they should share one entitlement and one key registration. Actor-scoped keys force five separate payments for the same economic relationship.

### Why rolling window, not static ranges?

Static ranges (`from_epoch..to_epoch`) create complexity around gaps, overlaps, and partial refunds. A rolling upper bound is simpler: one integer per entitlement, monotonically increasing, idempotent extension. It supports buy-as-you-go, sponsored top-ups, and continuous consumption without subscription lifecycle management.

### Why protocol fee on top (additive), not embedded?

An additive fee (`total = publisher_price + protocol_cut`) is transparent. Publishers set their price; the protocol adds its fee. There is no ambiguity about who gets what. An embedded fee (protocol takes X% of publisher's stated price) creates incentive misalignment where publishers inflate prices to offset the cut.

### Why separate subscription from entitlement?

Subscription controls delivery routing (push/pull). Entitlement controls decryption access (key epochs). Separating them means a subscriber can receive ciphertext via push without paying (they just can't decrypt), and an account can pre-purchase epoch access before any actor subscribes. This is cleaner than coupling payment to subscription lifecycle.

## Open Questions

- Should `protocol_fee_bps` be globally fixed or per-stream configurable within bounds?
- Should a future extension define bulk epoch purchase discounts?
- Should a future extension define on-chain key escrow for operator failover?
- Should `protocol_treasury` distribution (burn vs. stake vs. fund) be specified in this CIP or deferred to a governance CIP?
- Should there be a maximum `key_epoch_blocks` to prevent publishers from setting excessively long epochs that reduce billing granularity?
- Should a future extension add optional delivery receipts without retries?
- Should a future extension define refundable prepaid balances or proration?
- Should there be a `StreamConfigUpdated` event emitted when `access_mode` or `paid_stream_config` is changed?
