---
title: "CIP-7: Retention Contracts"
description: Off-chain data availability with SLA-backed blob storage
icon: cloud-arrow-up
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2025-01-18
</Note>

## Summary

This CIP specifies a unified mechanism for publishing and consuming Watchtower data feeds (e.g., news headlines) using (i) content-addressed blobs, (ii) on-chain retention contracts with explicit SLA-like terms, and (iii) Watchtower-driven auditing that gates provider payments and penalties. The same primitives are intended to generalize to non-feed blobs (artifacts, traces, datasets) without introducing separate storage semantics.

## **Abstract**

A **Feed Publisher** produces signed feed updates and publishes them as immutable blobs referenced by a **BlobRef** (e.g., ipfs://CID, ar://txid, or equivalent). A **Retention Contract** commits funds and defines a retention policy (duration, replication, audit cadence, penalty schedule) for one or more BlobRefs. **Providers** accept retention obligations by staking and serving blob ranges/chunks via a standard retrieval endpoint. **Watchtower** challenges providers, verifies responses against the BlobRef commitment, and posts attestations on-chain. Payments are released per-epoch conditioned on successful attestations; failures result in non-payment and optional slashing.

This CIP defines:

- Canonical data types: BlobRef, RetentionPolicy, RetentionContract, ProviderCommitment, AvailabilityAttestation, FeedUpdateEnvelope
- Standard provider retrieval protocol for range/chunk serving
- Watchtower audit procedure and attestation semantics
- Payment/penalty mechanics tied to attestations
- Recommended batching strategy for feed updates

## **Motivation**

Watchtower feeds require:

- **Authenticity** (did this come from AP or an authorized publisher?)
- **Availability** (can consumers fetch the update reliably with bounded latency?)
- **Clear retention** (how long is the update guaranteed retrievable and by whom?)
- **Economics** (who gets paid, when, and for what? what happens on failure?)

Traditional off-chain feeds rely on centralized hosting or implicit availability. Pure IPFS references do not guarantee persistence. This CIP makes availability explicit and enforceable at the Cowboy layer, while allowing multiple storage substrates (Cowboy-run infra, IPFS pinsets, Arweave archival, etc.) to participate behind a uniform interface.

## **Non-goals**

- Truthfulness of feed content beyond signature/auth policy (semantic correctness, misinformation detection, etc.) is out of scope.
- Permanent storage guarantees are not mandated; permanence may be achieved by policy + substrate selection.
- This CIP does not require storing blob bytes in consensus.

## **Definitions**

- **Blob**: Immutable byte sequence.
- **BlobRef**: Verifiable identifier for a Blob (content-addressed).
- **Feed Publisher**: Entity authorized to publish feed updates (e.g., AP).
- **Feed Operator**: Entity that packages updates into blobs and submits retention contracts (often the publisher or its partner).
- **Provider**: Entity that commits to serving blobs under retention policy, with stake.
- **Watchtower**: Network function that audits providers and posts attestations.
- **Epoch**: Chain-defined discrete time unit used for billing and auditing. Default: 600 blocks (~10 minutes at 1s block time). Epoch boundaries are deterministic: `epoch_number = block_height / epoch_length`.

## **Data Types**

### **1. BlobRef**

BlobRef identifies content and how it is verified.

Fields:

- uri (string): canonical locator scheme, e.g. `ipfs://<cid>`, `ar://<txid>`, `blob://<hash>`
- digest (bytes32 or bytes): hash digest of canonical bytes or canonical chunked encoding
- hash_alg (enum): e.g. SHA256, BLAKE3, KECCAK256
- size_bytes (uint64)
- codec (enum/string): e.g. raw, json, car, protobuf, gzip+json
- chunking (optional object):
    - chunk_size (uint32)
    - chunk_hash_alg (enum)
    - merkle_root (bytes32) if using merkle/chunk commitments
- encryption (optional object):
    - enc_alg (enum)
    - key_id (bytes/string reference)
    - aad (optional bytes)

Verification rule (minimum):

- The `digest` ALWAYS refers to the hash of the **stored bytes** (post-encoding). If `codec` is `gzip+json`, the digest is over the gzip-compressed bytes, not the decoded JSON.
- If chunking absent: fetched bytes MUST hash to digest under hash_alg.
- If chunking present: fetched chunk proofs MUST validate against merkle_root, and reconstructed stream MUST match size_bytes.

### **2. FeedUpdateEnvelope (authenticity container)**

Feed updates SHOULD be wrapped so consumers can verify origin independently from storage.

Fields:

- publisher_id (string): e.g. AP
- issued_at_unix_ms (uint64)
- sequence (uint64): monotonically increasing per publisher or per feed channel
- payload_codec (string/enum): e.g. json
- payload (bytes): headlines batch, normalized
- signature_scheme (enum): e.g. ed25519, secp256k1
- signature (bytes)
- signing_key_id (bytes/string): key reference resolvable on-chain or via registry CIP

Verification rule:

- Consumers MUST validate signature against authorized key for publisher_id.

Sequence handling:

- Consumers SHOULD track the last seen sequence per publisher_id.
- Sequence gaps indicate missed updates; consumers MAY query for missing sequences via feed_id index.
- Duplicate sequences (same publisher_id + sequence) MUST be rejected; first-seen wins.

### **3. RetentionPolicy**

Fields:

- start_epoch (uint64)
- end_epoch (uint64) exclusive
- min_replica_count (uint16)
- audit_cadence (enum/object):
    - e.g. PER_EPOCH, PER_N_EPOCHS, or PER_BLOCK (discouraged)
- max_latency_ms (optional uint32): coarse bucket boundary used for measurement
- availability_target_bps (optional uint16): e.g. 999 = 99.9% (advisory)
- sampling (object):
    - mode (enum): RANGE, CHUNK_INDEX
    - sample_size_bytes (uint32) for RANGE
    - num_samples_per_audit (uint16)
- payment_terms (object):
    - asset (enum): CBY (or multi-asset via separate CIP)
    - rate_per_epoch (uint256) per provider meeting requirements
    - escrow_amount (uint256) minimum locked at contract creation
- penalty_terms (object):
    - missed_audit_penalty (enum): NO_PAY, SLASH, BOTH
    - slash_amount (uint256) or slash_bps (uint16)
    - max_strikes (uint16) before ejection

### **4. RetentionContract**

Fields:

- contract_id (bytes32)
- feed_id (optional bytes32/string): logical channel, e.g. AP_HEADLINES_US
- blob_refs (array): one or more blobs governed by this contract (see batching)
- policy (RetentionPolicy)
- operator (address): creator and payer
- metadata (optional bytes): human-readable or indexable tags

Rules:

- MUST lock escrow_amount at creation.
- MUST reject `end_epoch <= start_epoch`.
- MAY allow extension via new contract; mutation of existing contract is discouraged.

### **5. ProviderCommitment**

Fields:

- provider (address)
- contract_id (bytes32)
- stake_amount (uint256)
- service_endpoint (string or bytes): standardized locator (e.g., URL, multiaddr, or Cowboy-native endpoint ID)
- accepted_at_epoch (uint64)

Rules:

- Provider MUST stake per policy minimum (defined elsewhere or in this CIP).
- Provider MUST implement the retrieval protocol for all blobs in RetentionContract.

### **6. AvailabilityAttestation**

Fields:

- contract_id (bytes32)
- provider (address)
- epoch (uint64)
- audit_id (bytes32): `keccak256(epoch_randomness || contract_id || provider || epoch)` where `epoch_randomness` is the block hash at epoch start
- result (enum): SUCCESS, FAIL, TIMEOUT, INVALID_BYTES
- latency_bucket (optional enum): e.g. `<250ms`, `<500ms`, `<1s`, `>1s`
- proof (optional bytes): compact evidence (e.g., sampled range hash), not required to store full bytes
- watchtower_sig (bytes)

Rules:

- Watchtower MUST post at most one final attestation per (contract_id, provider, epoch) unless superseded with a higher-finality rule.

## **Provider Retrieval Protocol**

Providers MUST expose a method for Watchtower and consumers to retrieve sampled bytes deterministically.

Minimum required operations:

### **Operation A: Range Fetch**

Request:

- blob_uri
- offset (uint64)
- length (uint32)
- audit_id (bytes32) optional (for signed responses)

Response:

- bytes (length)
- provider_sig (optional): signature over (blob_uri, offset, length, audit_id, bytes_hash)

### **Operation B: Chunk Fetch (if chunking is used)**

Request:

- blob_uri
- chunk_index (uint32)
- audit_id optional

Response:

- chunk_bytes
- chunk_proof (if merkle commitment)
- provider_sig optional

Transport:

- This CIP is transport-agnostic (HTTP, libp2p, etc.), but implementations SHOULD support HTTP range semantics for simplicity.

Verification:

- Watchtower MUST verify returned bytes/proofs match BlobRef commitment.

## **Watchtower Audit Procedure**

For each epoch where policy requires audits:

1. Compute deterministic audit_seed from chain randomness and tuple:
    - (contract_id, provider, epoch)
2. Derive num_samples_per_audit samples:
    - RANGE: choose offsets uniformly in [0, size_bytes - sample_size_bytes]
    - CHUNK_INDEX: choose indices uniformly in [0, num_chunks-1]
3. Issue requests to provider endpoint.
4. Measure latency as coarse bucket.
5. Verify content matches BlobRef (direct hash or merkle proof).
6. Post AvailabilityAttestation on-chain.

Failure conditions:

- Timeout beyond an implementation-defined cap (policy may specify).
- Invalid bytes/proof.
- Incorrect size/range response.

Partial failure handling:

- An audit is SUCCESS only if ALL samples pass verification.
- If any sample fails, the entire audit is marked FAIL.
- Rationale: Partial availability is effectively unavailability for consumers who need specific ranges.

## **Payment and Penalty Semantics**

At end of each audited epoch:

- If attestation SUCCESS:
    - Provider accrues rate_per_epoch (or portion if multi-sample scoring is adopted later).
- If FAIL/TIMEOUT/INVALID_BYTES:
    - Provider accrues zero for epoch.
    - If penalty_terms includes slashing:
        - slash as specified.
    - Increment strike counter; if strikes exceed max_strikes, provider is ejected from eligibility for this contract.

Escrow:

- Escrow is debited per-epoch as providers are paid.
- If escrow is insufficient for upcoming epochs, contract MAY be considered underfunded and providers MAY stop service without penalty (recommended to encode explicitly).

Contract expiration:

- After `end_epoch`, remaining escrow is automatically refundable to the operator.
- Providers MAY delete blob data after `end_epoch + grace_period` (default: 10 epochs).
- Consumers SHOULD NOT rely on availability after `end_epoch`.
- Operators wishing extended retention MUST create a new contract before expiration.

Replication:

- min_replica_count is satisfied if at least that many providers have active commitments and are successfully attested in the epoch.
- Consumers SHOULD prefer fetching from successfully attested providers.

## **Consumer Discovery**

Consumers locate retention contracts and fetch blobs as follows:

1. **By feed_id**: Query chain state for active contracts matching `feed_id` (e.g., `AP_HEADLINES_US`).
2. **By contract_id**: Direct lookup if contract_id is known.
3. **Provider selection**: From matched contracts, select providers with recent SUCCESS attestations.
4. **Fetch**: Request blob via provider retrieval protocol; verify against BlobRef.
5. **Authenticity**: Verify FeedUpdateEnvelope signature against registered publisher key.

Recommended: Indexers SHOULD maintain a `feed_id → [contract_id]` mapping for efficient lookup.

## **Feed Batching and Contract Granularity (recommended)**

To reduce on-chain churn, feed operators SHOULD:

- Batch updates into time windows (e.g., 1–10 minutes) per blob.
- Create retention contracts that cover:
    - either one blob per contract (simpler), or
    - a bounded array of blob_refs for a window (e.g., “next hour”) if supported efficiently.

A common pattern:

- One contract per hour, with 6 blobs (10-minute batches), retention of 24 hours.

## **Example: AP Headlines via Watchtower**

1. AP signs FeedUpdateEnvelope for 10-minute headline batch.
2. Operator uploads bytes to IPFS/Cowboy blob infra, obtains BlobRef.
3. Operator creates RetentionContract for 24h with replication=3, audits per epoch.
4. Three providers accept and stake; publish endpoints.
5. Each epoch, Watchtower samples 2 ranges per provider; posts attestations.
6. Payments release per epoch to providers with SUCCESS.
7. Consumers fetch by contract_id → choose attested providers → verify BlobRef hash and AP signature.

## **Security Considerations**

- **Authenticity vs Availability**: This CIP enforces availability; authenticity is provided by publisher signatures and key registry.
- **Provider equivocation**: Providers could serve correct samples but fail full retrieval. Mitigation: multiple samples, occasional full fetch audits, and/or CAR/block-level audits.
- **Watchtower trust**: If Watchtower is a single actor, it can lie. Mitigation options:
    - multiple watchtowers with quorum attestations
    - slashing for watchtower misbehavior (separate CIP)
    - client-side verification using provider-signed responses and challenge seeds
- **DoS and abuse**: Providers should rate-limit unauthenticated requests; Watchtower requests may use authentication tokens or on-chain allowlists.
- **Endpoint validation**: Provider `service_endpoint` MUST be validated before acceptance: (i) resolve to non-private IP ranges (no 10.x, 127.x, 169.254.x, 192.168.x), (ii) support TLS for HTTP endpoints, (iii) respond to health check within timeout. This prevents SSRF attacks against Watchtower infrastructure.
- **Encryption**: If blobs are encrypted, Watchtower can only audit availability of ciphertext, not plaintext correctness. This is acceptable; consumers manage keys separately.
- **Gateway centralization**: If Cowboy runs default gateways, ensure multi-provider resolution and do not make consensus depend on any single gateway.

## **Backwards Compatibility**

N/A (new standard).

## **Reference Implementation Notes (non-normative)**

- Prefer HTTP range fetch for initial implementations.
- Use merkle chunk commitments for very large blobs to enable low-bandwidth audits.
- Keep latency buckets coarse to avoid measurement gaming and timestamp disputes.

## **Open Questions (for follow-on CIPs)**

- Provider minimum stake and global reputation model.
- Multi-watchtower quorum and dispute resolution.
- Multi-asset payments (stablecoin) and fee markets.
- Standard key registry for publisher_id and signing_key_id.
- Latency enforcement: Should `max_latency_ms` in policy result in FAIL if exceeded, or only affect provider reputation scoring? Current design treats latency as advisory.
- Data type versioning scheme for schema evolution.