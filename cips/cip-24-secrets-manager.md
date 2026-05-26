---
title: "CIP-24: Cowboy Secret Service (CBSS)"
description: A threshold-IBE secret release service for actors, using BLS12-381 with a drand-style "tlock" construction. Secrets are account-level; owners encrypt to a per-account master public key (MPK) whose master secret (MSK) is never reified — only Shamir-shared across a committee of staked CBSS proxies via threshold BLS DKG (vetted libraries: blstrs, Commonware BLS DKG, tlock). At job time, t of n proxies return BLS partial signatures on a per-version identity; the runner Lagrange-combines them into the IBE decryption key. The dispatcher is not in the trust path and TEE is not the trust root. Defines the on-chain registry, the new SecretsProxy operator role, the threshold cryptography stack, the runner pull flow with per-proxy receipts, the liveness-challenge protocol, and the SDK surface.
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-04-29
  **Requires:** CIP-2 (off-chain compute), CIP-6 (SDK + entitlements), CIP-9 (CBFS-backed runner storage), CIP-12 (governance)
  **Related:** whitepaper §9.2 (master opcode allocation), CIP-23 (TEE Execution — optional additional gate, not the trust root)
</Note>

## 1. Abstract

CIP-24 specifies the **Cowboy Secret Service (CBSS)**: how an account stores third-party API credentials such that

1. plaintext is never visible on chain or to validators,
2. secrets can be deleted forever (no archival ciphertext that becomes decryptable as cryptography ages),
3. only the specific keys an actor names at the call site are released to the runner,
4. release is just-in-time and the dispatcher is not in the trust path,
5. cross-account sharing is supported, and
6. the trust root is **t-of-n proxy non-collusion**, not a hardware enclave.

The on-chain surface is the system actor at `0x0000…0004`. Off chain, CBSS introduces a new staked operator role — the **CBSS Proxy** (`SecretsProxy`) — running the `cbssd` daemon. Secrets are owned by **accounts**, not actors; an account's actors are *consumers* gated by per-secret ACL. Each per-account release keypair `(MPK ∈ G2, MSK ∈ scalar field)` is established by a single threshold BLS DKG ceremony among `n` proxies — once per account, regardless of how many actors or secrets that account ever has. `MSK` is never reified, only Shamir-shared. At release time, any `t` proxies return BLS partial signatures on the per-version identity; the runner Lagrange-combines them into the IBE decryption key and unwraps the DEK. Defaults: `n = 5`, `t = 4`, BLS12-381. The threshold follows the vetted Commonware `N3f1` DKG quorum for the five-proxy default.

For high-value secrets where the per-account blast radius is unacceptable, an owner MAY specify a **per-secret committee override** at `SetSecret` time. The override triggers a one-off DKG for that specific secret-version with its own `(MPK, MSK, committee, t, n)`, isolated from the account default. This is the escape hatch for owners who want a unique committee for `STRIPE_LIVE_KEY` while letting `SLACK_API_KEY` ride the account default.

CBSS rejects TEE as the trust root for secret release. CIP-23 TEE attestation remains available as an *additional* gate per secret (the `tee_required` flag), but the underlying release is unconditionally non-TEE. Rationale in §10.

**Crypto stack:** CBSS uses **BLS12-381** with a **threshold identity-based-encryption (IBE)** construction, equivalent to drand's "tlock" scheme. Vetted libraries are required — `blstrs` for curve ops, the pinned Commonware BLS DKG state machine (or an equivalent vetted threshold-BLS DKG), and `tlock` (drand) for the IBE construction. BLS12-381 is a new curve dependency for Cowboy but does not replace secp256k1 (account keys remain secp256k1); it lives alongside it as a CBSS-specific primitive. See §3.4.

The whole design rests on one structural decision: **the cryptographic principal is a stable on-chain identity (account by default, secret on override) whose private key is never reified — only Shamir-shared across the proxy committee.** This is the load-bearing change that makes pull-without-dispatcher and pull-without-TEE both work. The owner is offline at job time so cannot be the principal; the runner is VRF-selected at job time so per-recipient material cannot be pre-issued; therefore the principal is an on-chain identity whose key materializes only as a t-of-n threshold operation.

## 2. Motivation

### 2.1 The problem

Actors call third-party APIs (Slack, OpenAI, GitHub, Stripe, etc.) that require credentials. Today there is no protocol surface for storing them. Naive solutions — hard-coding into actor source, reading from a CBFS plaintext file, decrypting in actor PVM Python — all violate at least one of:

- **Validator privacy:** validators replay actor execution; anything readable in the PVM is readable on chain.
- **Eventual decryptability:** anything written to chain history is decryptable forever as cryptography ages. Secrets leak retroactively.
- **Runtime isolation:** an actor that can read `OPENAI_API_KEY` should not also be able to read `STRIPE_LIVE_KEY` just because the same account owns both.
- **Dispatcher trust:** the dispatcher-unwrap scheme in CIP-9 §9.2 puts the dispatcher in the trust path for DEK release. Acceptable for actor-private storage; not acceptable for third-party credentials.

### 2.2 Design philosophy

The protocol provides the **minimal release surface**: encrypted at-rest in CBFS, threshold-released through a registered proxy network, and delivered into an in-memory runner bundle for a single runner-op (with explicit subprocess env maps only when required). Every other concern — rotation policies, audit pipelines, HSM-backed wrapping, DAO-controlled secrets — is built by application-layer actors on top of this primitive. Following the precedent set by CIP-13 §2.1: protocol provides hooks, ecosystem builds products.

### 2.3 Why not TEE-rooted release

CIP-23 ships TEE-attested *execution*. That solves a different problem: bounding the runner host's introspection of in-flight actor state. Using the same anchor for *secret release* would mean every secret on the network becomes retroactively exfiltratable on a single CPU-vendor microarchitectural break (Foreshadow / Plundervolt / SGAxe / CipherLeaks have all happened to deployed TEEs). Secret ciphertext is durable; an enclave compromise is forever for the secrets it ever wrapped.

CBSS instead anchors trust in **t-of-n proxy non-collusion plus economic slashing**. The failure mode (≥ t simultaneous proxy compromises) is independent of any single hardware vendor and is hardenable through operator diversity policy. §9 quantifies the trade.

---

## 3. Specification

### 3.1 New data structures

#### SecretId

```
SecretId {
    account:   Address
    key_hash:  Bytes32             // == keccak256(account || key_name); chain never sees plaintext key_name
}
```

`KeyName` (plaintext, regex `[A-Z][A-Z0-9_]{0,127}`, case-sensitive ASCII) appears in CLI / SDK input, in actor manifest entitlements, and in the runner sandbox during a runner-op. **Chain instructions (§3.5) take `key_hash` directly**, never plaintext, so the mempool, tx args, storage paths, and event fields don't observe literal key names. The CLI computes `keccak256(account || key_name)` locally before submitting any tx. Plaintext names are still visible in deployed manifests (validator-readable) and dictionary-guessable for common names (e.g., `OPENAI_API_KEY`); see §3.2 for the realistic privacy boundary.

Keys are namespaced per owning account via the `account` field. Cross-account access is granted at the policy layer (§3.1.5), not the namespace layer.

#### SecretMetadata

The on-chain record for a secret. Stored at `0x04` keyed by `SecretId`.

```
SecretMetadata {
    id:                SecretId
    latest_version:    u64
    active_versions:   Vec<u64>                    // index of currently-active version numbers (NOT inlined SecretVersion records); each version's full state lives at secret_version:{account}:{H_key}:{version_be8}. Pruned per MAX_VERSIONS_PER_SECRET.
    created_at:        BlockHeight
    last_updated_at:   BlockHeight
}
```

#### SecretVersion

Immutable per `(SecretId, version)`. Created by `SetSecret`; deletable by `DeleteSecretVersion`.

```
SecretVersion {
    version:         u64
    pending:         bool                 // true between SetSecret(override-path) and FinalizeSecretVersion; false otherwise. Release attempts on pending versions fail with SecretPending.
    recipient:       ReleaseKeyRef        // always set; points to AccountReleaseKey (default) or per-secret SecretReleaseKey (override). For override path, the SecretReleaseKey may not exist yet (DkgPending) until RotateCommittee commits it.
    policy:          SecretPolicy         // always set
    // The following three fields are populated when pending=false. On the override path they are None at SetSecret time and filled in by FinalizeSecretVersion. Default-path SetSecret populates them immediately.
    wrap_epoch:      Option<u64>          // committee_epoch at the time this version was wrapped; IMMUTABLE once set
    cbfs_pointer:    Option<CbfsPointer>  // CIP-9 envelope; private volume. CIP-9 carries its own AEAD nonce/AAD for the outer DEK→plaintext encryption; CBSS does not duplicate that here.
    wrapped_dek:     Option<WrappedDek>   // single envelope (DEK encrypted under IBE-derived K); WrappedDek carries its own nonce + aad (see §3.5). aad is canonically derivable from (account, key_hash, version, wrap_epoch) so SecretVersion does not store it separately.
    created_at:      BlockHeight
    creator_sig:     Bytes                // tx-level sender signature is the source of truth; the chain records the signing block and signer in event metadata. NO separate finalizer_sig — FinalizeSecretVersion is itself a tx and its sender signature serves the same role.
}

// Invariant: pending == true ⇔ wrap_epoch.is_none() ⇔ cbfs_pointer.is_none() ⇔ wrapped_dek.is_none()
// On override-path SetSecret: pending = true and ALL three Option fields are None until FinalizeSecretVersion lands. wrap_epoch is set THEN, not at SetSecret time.

enum ReleaseKeyRef {
    Account(Address),                     // wraps under AccountReleaseKey[Address].mpk (default path)
    SecretSpecific(SecretId, u64),        // wraps under SecretReleaseKey[(SecretId, version)].mpk (override path)
}
```

A single `wrapped_dek` regardless of ACL size: ACL is purely a runtime gate, not a cryptographic recipient list. Adding or removing an actor from the ACL is a metadata-only update with no chain re-wrap. Storage cost per version is `O(1)`.

#### SecretPolicy

```
SecretPolicy {
    actors:        Option<Vec<ActorAddress>>     // None = all of owner's actors at release time
    tee_required:  bool                          // additional gate; layered on top of threshold release
}
```

`actors == None` resolves at release time to "any actor whose owning account == this secret's owning account." `actors == Some([...])` is an explicit allowlist and MAY include actors owned by other accounts (cross-account grant; unilateral, no acknowledgment from the recipient account required).

**Effective access** = (actor's CIP-6 manifest declares the key in its `secrets.read` entitlement) **AND** (`SecretPolicy` allows the actor) **AND** (if `tee_required`, runner provides a valid CIP-23 attestation).

#### AccountReleaseKey (default path)

The threshold-shared per-account keypair. Stored at `0x04` keyed by `Address`. Created by the DKG ceremony (§3.6.1); rotated by reshare (§3.6.2). Reused across all of an account's secrets that don't specify a per-secret override.

```
AccountReleaseKey {
    account:              Address
    mpk:                  G2Point                  // BLS12-381 G2, 96 B compressed (master public key); preserved across reshare
    committee:            Vec<ProxyId>             // current committee, exactly `n` distinct entries; mutable on reshare
    threshold:            u8                       // `t`, with 1 ≤ t ≤ n
    committee_epoch:      u64                      // increments on each successful reshare; tracks share-polynomial version, NOT ciphertext binding
    last_reshare_block:   BlockHeight
    vss_commitments:      Vec<G2Point>             // per-proxy VSS commitments S_i = s_i · G2 under the current committee_epoch; n entries
}
```

`committee_epoch` is bookkeeping for the share polynomial. It does **not** appear in the IBE identity or AEAD AAD — those are bound to a per-version `wrap_epoch` (see §3.4.3). PSS preserves `MSK` across reshare, so a proxy's *current* share validly partial-signs any identity ever wrapped under `MPK`, regardless of the wrap_epoch on the original SecretVersion.

#### SecretReleaseKey (override path)

Same shape as `AccountReleaseKey` but scoped to a single `(SecretId, version)`. Stored at `0x04` keyed by that pair. Created lazily when an owner submits `SetSecret` with `committee_override = Some(...)`. Allows per-secret committee parameters (size, threshold, member preference) for high-value secrets that should not share blast radius with the rest of an account's secrets.

```
SecretReleaseKey {
    secret_id:            SecretId
    version:              u64
    mpk:                  G2Point
    committee:            Vec<ProxyId>             // exactly `n` distinct entries
    threshold:            u8
    committee_epoch:      u64
    last_reshare_block:   BlockHeight
    vss_commitments:      Vec<G2Point>
}
```

A `SecretReleaseKey` is single-use in the sense that it is only consumed by its one owning `(SecretId, version)`. Deleting that secret-version (`DeleteSecretVersion` or `DeleteSecret`) cascades to the deletion of the corresponding `SecretReleaseKey` and emits a `ShareZeroizationRequested` event; share zeroization on committee members is best-effort, not chain-enforced (see `DeleteSecret` Effects in §3.5).

#### CbssProxy

The on-chain record of a registered proxy operator. Stored at `0x04` keyed by `ProxyId`.

```
CbssProxy {
    id:               ProxyId
    operator:         Address
    pubkey:           PublicKey                 // secp256k1; used for runner→proxy authentication
    hpke_pubkey:      HpkePublicKey             // X25519 HPKE key used for recipient-specific DKG/reshare payloads
    tls_spki:         Bytes                     // DER SubjectPublicKeyInfo pin for QUIC TLS verification
    network_addr:     NodeAddr                  // QUIC endpoint
    stake:            U256                      // CBY wei; ≥ MIN_PROXY_STAKE
    registered_at:    BlockHeight
    eligible_after:   BlockHeight               // registered_at + PROXY_SOAK_PERIOD
    health:           ProxyHealth               // updated by liveness pings; affects VRF weight
    suspended:        bool                      // true while a slashing case is open
    unbond_at:        Option<BlockHeight>       // Some iff DeregisterCbssProxy called
}
```

#### WrappedDek (IBE envelope)

The encrypted DEK on chain. AES-256-GCM with the IBE-derived key K (see §3.4.3). No public-key envelope per recipient — the IBE construction means there is exactly one ciphertext regardless of ACL size, and the recipient is implicit in the per-version identity `I = hash_to_G1( canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch), domain = "cbss/ibe/v1" )`.

```
WrappedDek {
    ciphertext:  Bytes        // AES-256-GCM(K, DEK, nonce, aad)
    nonce:       [u8; 12]
    aad:         Bytes        // == canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)
}
```

### 3.2 Storage layout in `0x04`

**Privacy scope.** Plaintext key names are kept off chain in **storage paths and tx args** — see §3.5 instructions, all of which take `key_hash: Bytes32` directly. Plaintext key names DO appear in:

1. **CLI / SDK input** (the user types `OPENAI_API_KEY` into `cowboy secrets set`).
2. **Actor manifest entitlements** (`secrets.read.keys: [...]`). Manifests are owner-deployed and validated by the chain; their entitlement keys are visible to validators, indexers, and any node that fetches the manifest. Owners who require unguessable key names should use random suffixes there too (see §5.1).
3. **The runner sandbox** during a single runner-op (as the substituted plaintext value's identifier).

The chain's storage paths and tx args use **`key_hash = keccak256(account || key_name)`**. Validators and chain observers see only `key_hash` in storage paths, tx args, and event fields. This is dictionary-guessable for common names — see "H(key) honesty" below — but does prevent passive scraping.

```
secret:{account_hex}:{H(key)_hex}                       → SecretMetadata (JSON)
secret_version:{account_hex}:{H(key)_hex}:{version_be8} → SecretVersion (JSON)
secret_version_tombstone:{account_hex}:{H(key)_hex}:{version_be8} → {deleted_at_block: u64, was_pending: bool} (permanent; lets lookups return SecretVersionDeleted instead of SecretNotFound)
account_release_key:{account_hex}                       → AccountReleaseKey (JSON)
secret_release_key:{H(key)_hex}:{version_be8}           → SecretReleaseKey (JSON, override path only)
cbss_proxy:{proxy_id_hex}                               → CbssProxy (JSON)
cbss_proxy_index_by_operator:{operator_hex}             → Vec<ProxyId>
committee_membership_account:{account_hex}              → Vec<ProxyId> (mirrors AccountReleaseKey.committee)
committee_membership_secret:{H(key)_hex}:{ver_be8}      → Vec<ProxyId> (mirrors SecretReleaseKey.committee)
release_receipt:{release_id_hex}                        → { quorum_epoch: u64, entries: Map<ProxyId, ReleaseReceipt> } (per-(release_id, proxy) dedup + audit; quorum_epoch is initialized to body.serve_epoch on the first accepted receipt — runner-pinned, NOT first-receipt-wins. All subsequent receipts must have committee_epoch_at_serve == quorum_epoch == body.serve_epoch or are rejected with MixedEpochReceipts.)
liveness_challenge:{challenge_id_hex}                   → LivenessChallenge (JSON; carries the verbatim SignedReleaseRequest)
liveness_challenge_index:{release_id_hex}:{proxy_hex}   → challenge_id (per-(release_id, proxy_id) dedup; one open challenge per logical release per proxy)
prior_committee_epochs:{release_key_id_hex}             → Vec<{epoch: u64, committee: Vec<ProxyId>, vss_commitments: Vec<G2Point>, expires_at: BlockHeight}> (multi-slot, capped at MAX_PRIOR_COMMITTEE_EPOCHS; each entry retained for RESHARE_GRACE_BLOCKS after its RotateCommittee then GC'd; if cap is hit before GC, RotateCommittee fails — see §3.5)
```

For `tee_required` secrets, CBSS also reads TEE Verifier (`0x05`) state at `tee_att:{job_id_32}:{runner_20}`. The value is a `TeeAttestationRecord { job_id, runner, tee_type, measurement_hash, attested_at_block, expires_at_block, revoked }`; CBSS never accepts a proxy-supplied TEE assertion. The TEE Verifier owns the companion trust store `tee_key:{tee_type}:{measurement_hash_32} → Vec<EncodedEcdsaPublicKey>`: SGX/TDX entries are uncompressed P-256 SEC1 public keys, and SEV-SNP entries are uncompressed P-384 SEC1 public keys. Records are written only by a signed-attestation path that verifies the canonical `cbss/tee-attestation/v1` payload over the job, runner, normalized TEE type, measurement, expiry, and quote bytes. This is the current devnet verifier boundary. Full Intel DCAP/TDX collateral validation and AMD SEV-SNP VLEK certificate-chain validation are deferred to the v1.1 / pre-mainnet TEE milestone.

Plaintext key names appear only in: (a) the owner's local CLI, (b) actor manifest entitlements (which are owner-controlled and meant to be public anyway), (c) the runner sandbox during a single runner-op. Chain state never holds them.

### 3.3 Master opcode allocation update

CIP-24 claims opcodes **68–84** from the master table maintained in whitepaper §9.2. The amended row block (to be merged in the same PR as this CIP):

| Opcode | Instruction | Source |
|---:|---|---|
| 68 | `SetSecret` | CIP-24 §3.5 |
| 69 | `UpdateSecretPolicy` | CIP-24 §3.5 |
| 70 | `DeleteSecretVersion` | CIP-24 §3.5 |
| 71 | `DeleteSecret` | CIP-24 §3.5 |
| 72 | `RegisterCbssProxy` | CIP-24 §3.5 |
| 73 | `DeregisterCbssProxy` | CIP-24 §3.5 |
| 74 | `RotateCommittee` | CIP-24 §3.5 |
| 75 | `SlashCbssProxy` | CIP-24 §3.5 |
| 76 | `SubmitReleaseReceipt` | CIP-24 §3.5 (per-proxy submission) |
| 77 | `RequestAccountDkg` | CIP-24 §3.5 |
| 78 | `FinalizeSecretVersion` | CIP-24 §3.5 (supports two-phase override flow) |
| 79 | `SubmitLivenessChallenge` | CIP-24 §3.5 (anchors a runner's liveness challenge against a proxy) |
| 80 | `LivenessChallengeResponse` | CIP-24 §3.5 (proxy's response to a challenge) |
| 81 | `ExpireDkgPending` | CIP-24 §3.5 (permissionless cleanup of an expired DkgPending record + bond settlement) |
| 82 | `ExpireLivenessChallenge` | CIP-24 maintenance (permissionless transition of expired pending challenges) |
| 83 | `RequestReshare` | CIP-24 reshare maintenance (owner-triggered committee refresh for an existing release key) |
| 84 | `ForcedDeregisterCbssProxy` | CIP-24 / CIP-12 governance remediation (governance-mediated proxy removal for persistent faults or disclosed leaks) |

TEE Verifier support instructions take opcodes **60–63** and are consumed by the `0x05` actor state that CIP-24 reads: `RegisterTeeTrustedKey` (60), `RevokeTeeTrustedKey` (61), `SubmitTeeAttestation` (62), and `RevokeTeeAttestation` (63). These are live in `node/types/src/execution.rs` (`SYS_REGISTER_TEE_TRUSTED_KEY=60` etc.) and are **the canonical assignments** for these slots — superseding earlier draft claims in CIP-13 v2 §1 / CIP-23 v2 / CIP-10 v2 that proposed `GcNonces` / container ops at these opcodes. The pre-activation drafts of those CIPs need their own renumbering against the code-based master table; see CIP-13 §1 (revised 2026-05-26).

### 3.4 Cryptography

#### 3.4.1 Vetted-library mandate

CBSS does not roll its own crypto. The protocol is built as a thin (~few hundred lines) integration layer over published, externally-reviewed primitives:

| Primitive | Library | Vetted-ness |
|---|---|---|
| BLS12-381 curve operations + pairings | `blstrs` (Filecoin-maintained) | Production at Ethereum, Filecoin, Drand mainnet scale |
| Hash-to-curve (G1) | `blstrs` (RFC 9380) | Same |
| Threshold BLS DKG | Commonware BLS DKG or equivalent vetted threshold-BLS DKG | Pinned Commonware `N3f1` state machine in the devnet implementation; external integration review before mainnet |
| Threshold IBE construction | `tlock` (drand reference) | Drand mainnet randomness beacon ships this in production for time-lock encryption |
| Symmetric encryption | `aes-gcm` (RustCrypto) | RustCrypto-reviewed; ubiquitous |
| KDF / hash | `hkdf`, `sha2`, `sha3` (RustCrypto) | Standard |

The integration glue (~few hundred lines: identity construction, ciphertext envelope, validation, share storage layer) lives in `runner/crates/cbss-crypto`. **Proactive secret sharing** (committee resharing) is the one sub-protocol where a vetted Rust library does not yet exist; CBSS implements a thin wrapper following drand's published resharing protocol. External crypto review deferred to June 2026; this is a pre-mainnet governance gate, not a current implementation-completion blocker.

#### 3.4.2 Curve choice: BLS12-381

CBSS uses **BLS12-381**, not secp256k1 (which Cowboy account keys use). Reasons:

1. **Vetted threshold-encryption libraries exist on BLS12-381.** Drand, Lit, the Ethereum-adjacent ecosystem, and Filecoin all ship BLS12-381 threshold tooling at production scale. On secp256k1 the equivalent threshold-encryption tooling does not exist in vetted form; a CBSS implementation on secp256k1 would require hand-rolling the DKG, partial decryption, and NIZK glue — exactly the cryptographic engineering anti-pattern this CIP rejects.
2. **Pairing-friendly groups** make threshold IBE possible with the simple Boneh-Franklin construction: encryption to an "identity" plus a threshold BLS signature on that identity is the IBE decryption key. No bespoke key-switching primitive required.
3. **Production scale** — Ethereum's beacon chain, Filecoin proofs, Drand all use BLS12-381 at ≥ million-share scale, so library quality is high and corner cases are well-understood.

The cost: BLS12-381 is a new curve dependency for Cowboy. It does **not** replace secp256k1 — account keys, runner registry keys, and proxy registry keys remain secp256k1. BLS12-381 lives alongside as a CBSS-internal primitive used only for threshold encryption. Pairings are 1–3 ms on modern hardware; well within the 250 ms p50 release latency budget.

#### 3.4.3 Construction: threshold IBE ("tlock" applied to secret release)

The construction is exactly drand's `tlock`, applied with a CBSS-specific identity binding instead of a future-round binding. Standard Boneh-Franklin IBE plus threshold BLS signatures.

**Pairing orientation (used throughout this CIP):** the BLS12-381 pairing is `e: G1 × G2 → GT`. `I` lives in G1; `MPK` and `S_i` live in G2; `σ` and `σ_i` live in G1. All pairing expressions follow this orientation: G1 element first, G2 element second.

**Epoch model:** a SecretVersion is bound at SetSecret time to the **wrap_epoch** = the release key's `committee_epoch` at that moment. `wrap_epoch` is then immutable. Reshare changes the release key's `committee_epoch` and rotates the share polynomial, but PSS preserves `MSK`, so a proxy's *current* share validly partial-signs any identity ever derived under any historical `wrap_epoch` of the same release key. The IBE envelope and AAD bind only `wrap_epoch`, never the live `committee_epoch`.

**Setup (per `AccountReleaseKey` or `SecretReleaseKey`):**

1. The n CBSS proxies in the committee run a threshold BLS DKG (the devnet implementation uses the pinned Commonware BLS DKG state machine; an equivalent vetted threshold-BLS DKG may be substituted by governance-reviewed implementation update). Round-2 share payloads are recipient-specific and HPKE-encrypted to each recipient's on-chain `CbssProxy.hpke_pubkey`. If timeout or complaint handling excludes a dealer, the daemon finalizes over an explicit qualified dealer set of at least `t` members. Output: master public key `MPK ∈ G2`, Shamir shares `s_1 … s_n ∈ Fr` of the implicit master secret key `MSK ∈ Fr`. Threshold `t`. `MSK` is never reified.
2. `MPK` and the per-proxy commitments `S_i = s_i · G2 ∈ G2` are published on chain in `AccountReleaseKey` or `SecretReleaseKey`.

**Storage (per secret-version):**

3. Let `wrap_epoch` = the release key's `committee_epoch` at SetSecret/FinalizeSecretVersion time. Owner derives the per-version identity using the canonical encoding (§3.5 SubmitReleaseReceipt):
   `I = hash_to_G1( canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch), domain = "cbss/ibe/v1" )`
   (RFC 9380 hash-to-curve). `I ∈ G1`. The owner, the proxies, and the chain all compute `I` from these same inputs in the same byte encoding.
4. Owner computes the IBE encryption key for `I`:
   `K = HKDF-SHA256( serialize(e(I, MPK)), "cbss/ibe/v1" || aad )`
   where `e(I, MPK) ∈ GT` is the BLS12-381 pairing and `aad = canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)`.
5. Owner generates a fresh DEK (256 bits, CSPRNG). AES-256-GCM-encrypts the plaintext value with DEK + a fresh nonce + AAD. Uploads the AES-GCM ciphertext to a private CBFS volume → `cbfs_pointer`.
6. Owner AES-256-GCM-encrypts DEK with `K` + a separate nonce, AAD = `canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)` (byte-identical to step 4), producing `wrapped_dek`.
7. Owner publishes `wrapped_dek + cbfs_pointer + wrap_epoch + recipient + policy` on chain via `SetSecret` (default path) or `FinalizeSecretVersion` (override path; see §3.5).

**Release (per job):**

8. Runner signs the `ReleaseRequestBody` directly with its **runner-registry key** (the secp256k1 key registered with `0x01` Runner Registry, the same key it uses for any other authenticated runner→chain interaction). No ephemeral key is involved — the IBE construction does not require a runner-bound ciphertext, so there is no per-request ephemeral keypair. Both proxies (at PartialSign serve time) and the chain (at SubmitReleaseReceipt validation) verify `runner_sig` against the runner registry.
9. Runner reads the SecretVersion (carrying `wrap_epoch`) and the referenced ReleaseKey (carrying current committee + `S_i`s) from chain. Runner sends a release request to t proxies. Each proxy validates ACL/manifest/job-assignment/anti-replay (§3.7).
10. Each proxy computes the identity exactly as the owner did, using the SecretVersion's `wrap_epoch` and the canonical encoding from step 3:
    `I = hash_to_G1( canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch), domain = "cbss/ibe/v1" )`,
    then its **partial signature**:
    `σ_i = s_i · I ∈ G1` (using the proxy's *current* share s_i — PSS guarantees this works regardless of the relationship between `wrap_epoch` and the proxy's current share epoch).
11. Each proxy returns `σ_i` to the runner. **Verification is the standard BLS partial-signature check**: validate `e(σ_i, G2_gen) == e(I, S_i)` where `S_i ∈ G2` is the proxy's published VSS commitment. No bespoke NIZK required — the BLS pairing equation is its own proof of correctness.
12. Runner combines t partial signatures via Lagrange interpolation in G1:
    `σ = Σ λ_i · σ_i = MSK · I ∈ G1`
    (the full threshold BLS signature on `I`, equivalently the IBE decryption key for `I`).
13. Runner derives `K = HKDF-SHA256( serialize(e(σ, G2_gen)), "cbss/ibe/v1" || aad )`. By bilinearity, `e(σ, G2_gen) = e(MSK · I, G2_gen) = e(I, MSK · G2_gen) = e(I, MPK)` — the same `K` the owner computed at step 4.
14. Runner AES-256-GCM-decrypts `wrapped_dek` with `K` → DEK.
15. Runner fetches the CBFS object via `cbfs_pointer`, AES-256-GCM-decrypts ciphertext with DEK → plaintext.

#### 3.4.4 Security properties

- **t-of-n threshold:** any t honest proxies can complete a release; t-1 cannot reconstruct `σ` and therefore cannot derive `K`. Standard BLS-DKG threshold property.
- **Per-`(secret_id, version, wrap_epoch)` σ:** a leaked `σ` decrypts only the wrapped DEK for that exact identity. Compromising a different secret version requires a separate t-of-n collusion to derive its σ. Reshare does NOT invalidate σ values for prior identities; PSS preserves `MSK` and hence preserves σ for any identity I.
- **No bespoke NIZK:** BLS partial-signature verification is a single pairing check, covered by `blstrs` and the vetted threshold-BLS implementation.
- **Anti-replay, ACL, audit:** enforced at the proxy validation layer (§3.7) and via per-proxy receipts (§3.5). Cryptographic envelope intentionally does NOT bind to runner ephemeral key — see §3.4.5 for why.
- **Reshare:** proactive secret sharing on `MSK` rotates shares without changing `MPK`. Stored secrets remain decryptable. In-flight release requests are NOT invalidated by reshare; a proxy's freshly-resharded share still produces valid partials for any prior-epoch identity.
- **Insider rotation:** the value of reshare is bounding the window during which a specific share-holder's compromised share is useful. After reshare, that specific s_i is replaced; the attacker must re-compromise the new s_i' to keep contributing to t-of-n.

#### 3.4.5 Why threshold IBE, not threshold ElGamal with key-switching

The candidate alternative is threshold ElGamal on secp256k1 with a custom "key-switching to runner ephemeral pubkey" construction. Two problems:

1. **No vetted Rust library exists.** Threshold ElGamal on secp256k1 requires hand-rolling the DKG, partial-decrypt construction, and Chaum-Pedersen NIZK. Standard cryptographic-engineering hygiene says: don't roll your own crypto when a vetted equivalent exists. BLS12-381 + threshold IBE has vetted equivalents (Commonware BLS DKG, `tlock`, `blstrs`); secp256k1 + threshold ElGamal does not.
2. **Key-switching to runner ephemeral pubkey** was solving a problem we don't actually have. The runner is the legitimate recipient of DEK; cryptographically binding the ciphertext to a runner-ephemeral pubkey adds protocol complexity without buying additional security beyond what proxy-side anti-replay/ACL already provide. Threshold IBE produces DEK directly to the runner; the runner zeroizes after use; revocation/replay/audit happen at validation time, not in the envelope.

The threshold-IBE construction is what drand's `tlock` ships in production. CBSS uses the same primitive with a CBSS-specific identity binding.

### 3.5 New system instructions

Each instruction's `Sender` column gives who is authorized to submit it. Gas costs in §4.1.

#### SetSecret (opcode 68)

The instruction is **shape-asymmetric across the two recipient types** because in the override path the recipient `MPK` does not exist at SetSecret time — it must be produced by a fresh DKG ceremony first. The default path stays one-shot; the override path is two-phase, with `FinalizeSecretVersion` (opcode 78) attaching the ciphertext after DKG finalizes.

```
SetSecret {
    key_hash:             Bytes32                        // == keccak256(sender || key_name); plaintext key_name never crosses the wire
    recipient:            ReleaseKeyRef                  // Account(sender) for default; SecretSpecific(SecretId, next_version) for override
    policy:               SecretPolicy
    // Default path (recipient = Account(_)) carries ciphertext immediately:
    cbfs_pointer:         Option<CbfsPointer>            // Some on default path; None on override path. CIP-9 envelope; carries the outer plaintext-encryption nonce internally.
    wrap_epoch:           Option<u64>                    // Some on default path (== AccountReleaseKey.committee_epoch); None on override path
    wrapped_dek:          Option<WrappedDek>             // Some on default path (carries inner DEK-wrap nonce + aad); None on override path
    // Override path carries committee parameters:
    committee_override:   Option<CommitteeOverride>      // Some on override path; None on default path
}

struct CommitteeOverride {
    n:                 u8                     // 5 ≤ n ≤ MAX_OVERRIDE_N
    t:                 u8                     // MIN_OVERRIDE_T ≤ t ≤ n
    preferred_proxies: Option<Vec<ProxyId>>   // hints; final committee is VRF-selected from this set if Some
}

struct WrappedDek {
    ciphertext:  Bytes              // AES-256-GCM ciphertext of the DEK
    nonce:       [u8; 12]
    aad:         Bytes              // == canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)
}
```

**Sender:** owner of the account.

**Effects:**

- **Default path (`recipient = Account(sender)`):** must carry `cbfs_pointer + wrap_epoch + wrapped_dek` (DEK encrypted under the IBE key derived from the account's existing `MPK`; nonces and AAD are inside `WrappedDek` and the CIP-9 CBFS envelope). The instruction is rejected with `MissingAccountReleaseKey` if the sender has no `AccountReleaseKey` on file (the `cowboy` CLI auto-issues `RequestAccountDkg` on first use). Creates `SecretVersion(version = latest + 1)` under `SecretId(sender, key)` with `pending = false`. Emits `SecretCreated`.

- **Override path (`recipient = SecretSpecific(SecretId, next_version)`):** must NOT carry `cbfs_pointer / wrap_epoch / wrapped_dek`. Instead carries `committee_override`. Effects:
    1. Creates `SecretVersion(version = next_version)` with `pending = true`, `wrap_epoch = None`, `cbfs_pointer = None`, `wrapped_dek = None`. (The §3.1 invariant requires all three Option fields are None on a pending version.) `wrap_epoch` is populated by `FinalizeSecretVersion` once `MPK` exists.
    2. Locks `DKG_BOND` from the sender, VRF-selects an n-proxy committee per the override spec, and writes a `DkgPending(SecretSpecific(SecretId, next_version), committee, deadline, bond_amount, requester = sender)` record.
    3. Off-chain DKG runs (§3.6.1). On commit, the committee submits `RotateCommittee { scope: SecretSpecific(...), new_committee_epoch: 1, ... }`, which writes the new `SecretReleaseKey` and exposes `MPK` on chain.
    4. Owner reads `MPK + committee_epoch` from chain, sets `wrap_epoch = committee_epoch` (= 1 here), computes `K = HKDF(serialize(e(I, MPK)), aad)`, encrypts DEK to `K`, uploads CBFS ciphertext, and submits `FinalizeSecretVersion` (opcode 78) to attach `cbfs_pointer + wrapped_dek + wrap_epoch` and clear `pending`.
    5. Until step 4 lands, release attempts against this version fail closed with `SecretPending`.

**Validation rules** (chain-enforced):

- Default path: `wrap_epoch == account_release_key.committee_epoch` at SetSecret block; `wrapped_dek.aad == canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)`. Rejects with `WrapEpochMismatch` / `AadMismatch` otherwise.
- Override path: `committee_override.n` and `t` within `(MIN_OVERRIDE_T, MAX_OVERRIDE_N)`; `preferred_proxies` (if Some) all eligible.
- Both paths: `key_hash` is a well-formed 32-byte value; quotas not exceeded. (Plaintext `KeyName` regex enforcement is **CLI/SDK-side**, since the chain never sees plaintext.)

Emits `SecretCreated { id, version, recipient_kind, pending: bool, ... }`.

#### FinalizeSecretVersion (opcode 78)

Attaches ciphertext to a `pending = true` `SecretVersion` after its DKG ceremony has committed. Used only on the override path.

```
FinalizeSecretVersion {
    key_hash:      Bytes32
    version:       u64
    wrap_epoch:    u64                  // == secret_release_key.committee_epoch at this submission's block
    cbfs_pointer:  CbfsPointer          // CIP-9 envelope; carries outer plaintext-encryption nonce internally
    wrapped_dek:   WrappedDek           // carries inner DEK-wrap nonce + aad
}
```

**Sender:** owner of the account.

**Effects:** validates that:

- `SecretVersion` exists, has `pending = true`, and `recipient = SecretSpecific(_, version)`.
- The corresponding `SecretReleaseKey` is committed (exists on chain) and its `committee_epoch ≥ 1`.
- `wrap_epoch == secret_release_key.committee_epoch` at FinalizeSecretVersion block (no resharing in between, OR the owner explicitly accepts re-wrapping under the new epoch).
- `wrapped_dek.aad == canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)`.

On success, sets `cbfs_pointer`, `wrap_epoch`, `wrapped_dek` on the `SecretVersion` and clears `pending`. From this point release proceeds normally.

Emits `SecretVersionFinalized { id, version }`.

If the owner never finalizes (e.g., abandons the secret), the version remains `pending` indefinitely and consumes a quota slot. A future garbage-collection mechanism MAY reclaim long-pending versions; out of scope here.

#### UpdateSecretPolicy (opcode 69)

```
UpdateSecretPolicy {
    key_hash:    Bytes32
    version:     u64
    new_policy:  SecretPolicy
}
```

**Sender:** owner of the account.

**Effects:** replaces the policy on the named `SecretVersion`. **No re-wrap is required** — the cryptographic recipient is the account (or per-secret override key), not the individual ACL actors. ACL changes are pure metadata and propagate atomically to all subsequent release attempts. ACL semantics on update: **replace, not merge** (the new policy fully supersedes the old).

This is one of the operational wins of per-account anchoring vs per-actor: granting or revoking an actor's access is a single chain tx with no proxy round-trips, no re-encryption, no chain-storage fan-out.

Emits `SecretPolicyUpdated`.

#### DeleteSecretVersion (opcode 70)

```
DeleteSecretVersion { key_hash: Bytes32, version: u64 }
```

**Sender:** owner.

**Effects:** removes `SecretVersion` from chain state, **adds an entry to `secret_version_tombstone:{account_hex}:{H(key)_hex}:{version_be8}`** (singular path; matches §3.2 storage layout). Tombstone carries `{deleted_at_block, was_pending}` so future lookups can distinguish "deleted" from "never existed", never the ciphertext. If `pending == false`, also emits a CBFS drop instruction for the `cbfs_pointer`; if `pending == true`, no CBFS object exists, so the CBFS drop is skipped. Subsequent release attempts against this version fail closed with `SecretVersionDeleted` (the tombstone is what makes this distinguishable from `SecretNotFound`). Pending releases that referenced this version (already in flight at proxies) fail at the proxy validation step.

#### DeleteSecret (opcode 71)

```
DeleteSecret { key_hash: Bytes32 }
```

**Sender:** owner.

**Effects:** atomically deletes all versions of the secret. Drops each version's CBFS pointer (skipping pending versions which have none). Each version gets a tombstone entry as in `DeleteSecretVersion`. `SecretMetadata` removed. The account's `AccountReleaseKey` is **not** removed (it may serve other secrets). Any per-secret `SecretReleaseKey` records owned by the deleted versions ARE cascaded into deletion: the chain emits a `ShareZeroizationRequested { release_key_id }` event per affected SecretReleaseKey. Committee members SHOULD respond by zeroizing their local shares and recording the action in their cbssd audit log; **the chain does NOT enforce zeroization** (no quorum signature or attestation is required by the protocol — false attestations would be evidence in a future leak case but cannot be objectively verified at deletion time). This is documented and accepted: deletion is a request to the operator network, not a cryptographic guarantee. Owners should treat zeroization as best-effort and not rely on it for forward secrecy.

#### RegisterCbssProxy (opcode 72)

```
RegisterCbssProxy {
    pubkey:        PublicKey
    hpke_pubkey:   HpkePublicKey
    tls_spki:      Bytes                  // DER SubjectPublicKeyInfo pin for QUIC TLS verification
    network_addr:  NodeAddr
    stake_amount:  U256                  // ≥ MIN_PROXY_STAKE; locked from operator's account
}
```

**Sender:** any account with sufficient CBY balance.

**Effects:** locks `stake_amount` CBY in the proxy's escrow, mints a fresh `ProxyId`, writes `CbssProxy` with `eligible_after = current_block + PROXY_SOAK_PERIOD`. The proxy is not VRF-eligible until soak completes.

#### DeregisterCbssProxy (opcode 73)

```
DeregisterCbssProxy { proxy_id: ProxyId }
```

**Sender:** the registered proxy operator.

**Effects:** sets `unbond_at = current_block`. Stake remains locked for `UNBOND_COOLDOWN`. If the proxy is currently a member of any `AccountReleaseKey.committee` or `SecretReleaseKey.committee`, `RotateCommittee` is enqueued for each affected release key. After cooldown elapses with no slashing case, stake is returned and the `CbssProxy` record is purged.

#### RotateCommittee (opcode 74)

```
RotateCommittee {
    scope:               ReleaseKeyScope
    new_committee:       Vec<ProxyId>          // exactly `n` distinct, all eligible
    new_committee_epoch: u64                   // == old + 1; for fresh DKG (initial), == 1
    new_mpk:             G2Point               // 96 B compressed; on initial DKG this is the freshly-generated MPK; on reshare this MUST equal the prior MPK (chain enforces; PSS preserves MSK so MPK is preserved)
    vss_commitments:     Vec<G2Point>          // n entries, S_i = s_i · G2 ∈ G2 (matches §3.4 verification e(σ_i, G2_gen) == e(I, S_i))
    new_committee_sigs:  Vec<Signature>        // ≥ t signatures FROM new_committee MEMBERS attesting to the DKG output. REQUIRED on both initial DKG and reshare. Each sig is over keccak256("cbss/dkg-commit/v1" || serialize(scope) || u64_le(new_committee_epoch) || serialize(new_mpk) || serialize(vss_commitments)) under the proxy's registered identity key.
    prior_committee_sigs: Vec<Signature>       // ≥ t signatures from PRIOR committee attesting they zeroized old shares. REQUIRED on reshare; OMITTED on initial DKG (no prior committee exists). Each sig is over keccak256("cbss/reshare-zeroize/v1" || serialize(scope) || u64_le(new_committee_epoch)) under the prior proxy's identity key.
}

enum ReleaseKeyScope {
    Account(Address),
    SecretSpecific(SecretId, u64),
}
```

**Sender:** any one member of the new committee, on behalf of the committee. The submitter's authority comes from the threshold signature set in `new_committee_sigs`, not from being the lone submitter.

**Effects:** verifies VSS commitments (each `S_i ∈ G2`) and quorum signatures (when applicable), atomically updates the targeted `AccountReleaseKey` or `SecretReleaseKey` and increments `committee_epoch`. **Reshare grace:** before overwriting, the prior `(committee_epoch_old, committee_old, vss_commitments_old, expires_at = current_block + RESHARE_GRACE_BLOCKS)` is appended to `prior_committee_epochs:{release_key_id}` (a Vec, NOT a single slot — handles back-to-back reshares within one grace window). On append, any entries whose `expires_at < current_block` are GC'd first. If the resulting Vec would exceed `MAX_PRIOR_COMMITTEE_EPOCHS` (§4.2, default 4), the RotateCommittee instruction is **rejected** with `ReshareGraceCapacity` — the operator must wait for at least one prior epoch to expire, OR governance can override via a CIP-12 emergency proposal that prunes oldest entries. This bounds storage growth while preventing the one-slot-overwrite bug.

Receipts whose `committee_epoch_at_serve` matches any retained entry in `prior_committee_epochs` (and whose submission is before that entry's `expires_at`) are accepted; outside any retained entry's window, they're rejected with `StaleCommitteeEpoch`. Old committee members MUST zeroize their old shares before signing the quorum attestation; failure to do so is not directly slashable but the signing under false attestation is future-evidence for a leak case. Existing `SecretVersion` records keep their original `wrap_epoch` (immutable per version); the IBE identity for those versions is unchanged. New `SetSecret` calls after this RotateCommittee bind to the new `committee_epoch` as their `wrap_epoch`.

`mpk` is preserved across reshare (proactive secret sharing); only the share polynomial changes. This is true for both account-scoped and secret-scoped keys.

This instruction is also used to commit the result of an *initial* DKG ceremony triggered by `RequestAccountDkg` or by the override path of `SetSecret`. In that case, `prior_committee_sigs` is empty (there is no prior committee to attest zeroization from), but `new_committee_sigs` is **still required** — at least t signatures from members of the freshly-DKG'd new committee over the canonical DKG-commit payload (see the field comments in the struct above). This is what authenticates the initial DKG output; without it, a single nominated proxy could commit an arbitrary `(MPK, S_i)` set.

#### SlashCbssProxy (opcode 75)

On-chain-provable fault classes are limited to those that admit objective, on-chain evidence. **Liveness is excluded from automatic slashing entirely** — packet-delivery non-receipt is fundamentally not provable on chain (a malicious or broken runner can submit a valid signed request without ever delivering it to the proxy; the proxy cannot prove a network negative). Liveness instead drives a **health score** (§4.4) that affects VRF selection weight, and persistent extreme degradation triggers governance review (CIP-12 Tier 1 `ForcedDeregisterCbssProxy`). The on-chain `SubmitLivenessChallenge` / `LivenessChallengeResponse` remain as the **audit trail** that feeds the health score, but they do not by themselves cause stake loss.

**`PlaintextLeak` is also removed** from protocol-level slashing because its evidence ("here is the recovered DEK plus t-1 partials") would publish the secret on chain. Off-chain disclosure → governance → `ForcedDeregisterCbssProxy` is the channel.

```
SlashCbssProxy {
    proxy_id:    ProxyId
    fault_class: FaultClass
    evidence:    SlashEvidence
}

enum FaultClass {
    InvalidPartialReencrypt,             // BLS partial-sig pairing check fails on a submitted σ_i
    DkgSabotage,                         // VSS commitment / share mismatch in DKG round 2
    Equivocation,                        // Two distinct signed responses (same request_hash, distinct payloads)
}
```

**Sender:** any account that holds the corresponding evidence.

**Effects:** evaluates the evidence per fault class (§4.3). On valid evidence, applies the schedule penalty to `CbssProxy.stake`, sets `suspended = true` pending governance review.

#### SubmitLivenessChallenge (opcode 79)

Anchors on chain that a runner experienced a non-response from a proxy. Feeds the proxy's health score; does NOT by itself trigger slashing.

```
SubmitLivenessChallenge {
    runner_request:             SignedReleaseRequest  // the original signed request the runner claims went unanswered (body + runner_sig)
    proxy_id:                   ProxyId               // proxy alleged non-responsive
    challenge_sig:              Signature             // exact byte layout: see "Canonical domain-separated signature payloads"
                                                      // following the request hash definitions earlier in §3.5.
                                                      // Signed under the runner registry key with the "cbss/liveness-challenge/v1" domain prefix.
                                                      // (No challenged_at in the signed payload — chain assigns it on inclusion.)
}
```

`challenged_at` is **NOT a tx arg** — the chain sets it to the inclusion block height when the instruction is processed. This prevents future-dating or backdating attacks on the response-deadline timing.

**Sender:** the runner identified by `runner_request.body.runner_id`.

**Effects:** all validation at **current head** (no historical reads), matching the receipt model:

1. `runner_request.runner_sig` verifies `request_hash = keccak256(serialize(runner_request.body))` against the on-chain runner registry pubkey for `body.runner_id` at current head.
2. ACL/manifest/job-assignment for `(body.actor, body.runner_id, body.job_id, body.secret_id)` valid at current head.
3. `SecretVersion[body.secret_id, body.version].pending == false` — challenges against pending versions are rejected with `SecretPending` (a pending version is never releasable, so a missed-request claim against it is meaningless).
4. `body.request_block + MIN_CHALLENGE_DELAY_BLOCKS ≤ submission_block ≤ body.request_block + LIVENESS_CHALLENGE_MAX_AGE_BLOCKS`. The lower bound (premature → `ChallengePremature`) gives the proxy time to serve + submit a receipt before being challenged. The upper bound (default `MIN_CHALLENGE_DELAY_BLOCKS + LIVENESS_RESPONSE_BLOCKS`, ~32 min) bounds how stale a challenge can be; older challenges fail with `StaleChallenge`. (`challenged_at` is set to `submission_block` by the handler.)
5. `body.recipient == SecretVersion[body.secret_id, body.version].recipient` (same recipient-consistency check as receipts; prevents committee-substitution challenges).
6. `proxy_id` is a member of the referenced release key's **current committee OR any retained prior committee** (i.e., any entry of `prior_committee_epochs:{release_key_id}` whose `expires_at > submission_block`). The challenge does NOT carry a `committee_epoch_at_serve` (unlike receipts); the chain accepts membership in any currently-recognized committee. Rationale: the challenge is alleging the proxy failed to respond at SOME point during its tenure; pinning a specific epoch would require the runner to know which committee_epoch the proxy was supposed to serve under, which the runner doesn't necessarily know at challenge time.
7. `challenge_sig` verifies the outer challenge envelope under `body.runner_id`'s registry key.
8. **Per-release liveness dedup.** No prior `liveness_challenge_index:{release_id}:{proxy_id}` entry exists. A `(release_id, proxy_id)` pair admits at most ONE on-chain liveness challenge regardless of whether the previous challenge is pending or terminal. Duplicate submissions are rejected with `LivenessChallengeAlreadyOpen`. This bounds health-score impact to one challenge per logical release per proxy and prevents repeated false-alarm bond transfers.
9. The chain checks whether `release_receipt:{release_id}.entries[proxy_id]` already exists. An existing receipt is **not** a rejection: it proves the proxy already served and makes the challenge immediately `Resolved`; the runner forfeits the bond to the challenged proxy.

On success, locks `LIVENESS_CHALLENGE_BOND` from the runner's account and writes `liveness_challenge_index:{release_id}:{proxy_id} → challenge_id` so subsequent duplicate challenges are rejected. If a receipt for `(release_id, proxy_id)` already exists, the handler writes `LivenessChallenge { id, runner_request, bond_amount, challenged_at = submission_block, status: Resolved, deadline = submission_block }` and transfers the bond to the challenged proxy. Otherwise it writes `LivenessChallenge { id, runner_request, bond_amount, challenged_at = submission_block, status: Pending, deadline = submission_block + LIVENESS_RESPONSE_BLOCKS }`. The proxy has until `deadline` to dispute.

**Admission-time receipt resolution.** Because `MIN_CHALLENGE_DELAY_BLOCKS` is strictly greater than `REQUEST_FRESHNESS_BLOCKS`, every receipt that can pass receipt freshness validation is already either on chain or impossible to submit by the time a liveness challenge is admissible. Runners are expected to check `release_receipt:{release_id}.entries[proxy_id]` before challenging. If they challenge despite an existing receipt, the chain resolves the challenge immediately and transfers the bond to the proxy. The receipt itself does NOT need to be fresh per `REQUEST_FRESHNESS_BLOCKS` for this purpose — persistent `release_receipt` state is the authoritative record of "did the proxy ever submit a paid receipt for this release_id." `Resolved` is therefore an admission-time state, not a response-time state.

If a proxy served but failed to submit a receipt before the receipt freshness window closed, it cannot later create chain-verifiable receipt evidence. Its only on-chain response path is an `Unverifiable` reason (typically `NeverReceived` or structured local-failure evidence), which is health-neutral but does not produce a positive liveness signal.

After `deadline`, a still-`Pending` challenge transitions to `Unanswered`, refunds the bond to the runner, and applies the standard negative health-score decrement to the proxy. **No automatic slash follows.** The challenge is recorded in the proxy's audit history. Persistent unanswered challenges may justify a governance proposal under CIP-12.

#### LivenessChallengeResponse (opcode 80)

A proxy's structured response to a liveness challenge. Records chain-unverifiable response evidence; does NOT by itself prevent governance action.

```
LivenessChallengeResponse {
    challenge_id:  Bytes32
    proxy_id:      ProxyId
    reason:        ChallengeReason
    evidence:      ChallengeResponseEvidence
    proxy_sig:     Signature                         // see "Signed payload" below
}

enum ChallengeReason {
    // NOT chain-verifiable (logged for governance pattern detection):
    InvalidRequest,           // proxy claims the request failed validation at serve time (ACL, manifest, job assignment, sig). NOT auto-resolving because chain re-derivation at response time would use later state and the admission-time snapshot is not stored. Logged with the proxy's structured reason for governance pattern detection.
    RateLimited,              // proxy claims its local rate-limiter rejected the request. Per-actor rate limits are proxy-local sliding-window state and the chain has no way to verify the proxy's claim.
    NeverReceived,            // proxy claims the network request did not arrive; not provable on chain.
}

// Domain-separated signed payload. Implementations MUST sign exactly these bytes:
proxy_sig := sign(proxy_priv,
              keccak256( "cbss/liveness-response/v1" ||
                         challenge_id ||
                         proxy_id ||
                         u8(reason) ||
                         keccak256(serialize(evidence)) ))
```

**Sender:** the challenged proxy.

**Effects:** validates `proxy_sig` over the exact byte layout above against `CbssProxy.pubkey`, then evaluates evidence per `reason`. The chain transitions the challenge to a terminal state with bond disposition that matches the chain's view of who was right:

- **`Resolved`** — not produced by `LivenessChallengeResponse`; produced only by the admission-time receipt check in `SubmitLivenessChallenge`. Chain dereferences `release_receipt:{release_id}` and confirms the entry exists with `proxy_id` matching. Health-score impact on the proxy: small positive (proved liveness via receipt). Bond disposition: forfeited to the challenged proxy.
- **`Unverifiable`** — proxy submits `LivenessChallengeResponse` with `InvalidRequest` / `RateLimited` / `NeverReceived` before deadline. Chain cannot re-derive any of these. **Bond → refunded to the runner** (the runner submitted a good-faith challenge; whether the proxy's response is honest is unknowable on-chain). Health-score impact on the proxy: NEUTRAL — no automatic decrement. Pattern detection lives in off-chain governance.
- **`Unanswered`** — proxy submits no response by `deadline`. The runner was right — the proxy is genuinely silent. **Bond → refunded to the runner**. Health-score impact on the proxy: standard negative decrement. Persistent unanswered patterns flag the proxy for governance review per §4.4.

The runner loses money only when the chain can prove the runner was wrong (`Resolved` via an existing receipt); in all other cases (proxy went silent or proxy gave an unverifiable response) the runner gets the bond back.

**Anti-spam friction.** A naive runner could still try to challenge proxies before they've had time to submit their receipts. To prevent this, `SubmitLivenessChallenge` enforces `body.request_block + MIN_CHALLENGE_DELAY_BLOCKS ≤ submission_block` (see §4.2). Challenges submitted too soon after the original request are rejected with `ChallengePremature`. The default delay is `REQUEST_FRESHNESS_BLOCKS + 32` (~12 min), giving honest proxies a generous window to either serve + submit a receipt (which then resolves any later challenge at admission) or fail loudly.

Only the admission-time receipt check is chain-verifiable and resolves to `Resolved`. `Unverifiable` captures "the proxy responded with chain-unverifiable evidence" without penalizing either party. Repeated `Unverifiable` patterns by the same proxy escalate via off-chain governance, not protocol-level slashing or health-score automation.

#### SubmitReleaseReceipt (opcode 76)

**Per-proxy submission**, not aggregate. Each proxy that served a partial submits its own receipt independently. The receipt **carries the runner's original signed release request verbatim AND the proxy's BLS partial signature `σ_i`**. The chain re-derives the request hash, verifies the runner's signature, and verifies the BLS pairing equation `e(σ_i, G2_gen) == e(I, S_i)` — providing cryptographic proof that the proxy actually computed honest work, not just that the runner asked for it. A proxy that submits a receipt without computing `σ_i` cannot pass the pairing check.

```
SubmitReleaseReceipt {
    runner_request:             SignedReleaseRequest    // the original, replayed verbatim
    proxy_id:                   ProxyId                 // this submitter
    sigma_i:                    G1Bytes                 // 48-byte compressed BLS12-381 G1 point; the partial sig the proxy returned to the runner
    committee_epoch_at_serve:   u64                     // the release key's committee_epoch when the proxy computed σ_i
    served_at_block:            BlockHeight             // when the proxy computed σ_i
    proxy_sig:                  Signature               // see "Canonical domain-separated signature payloads" later in §3.5; signed under the proxy identity key with "cbss/partial-sign-response/v1" prefix.
    // Note: tee_attested is NOT a field — chain computes it (§3.5 step 10) from TEE Verifier state
}

struct ReleaseRequestBody {                   // unsigned; this is the message the runner signs
    secret_id:       SecretId                 // == { account, key_hash }; carries the secret-owning account, NOT the requesting actor's account
    version:         u64
    actor:           ActorAddress             // the requesting actor (may be cross-account)
    runner_id:       RunnerAddress
    recipient:       ReleaseKeyRef
    job_id:          JobId
    release_nonce:   Bytes32                  // fresh CSPRNG per fetch_for_op call
    request_block:   BlockHeight              // chain block runner pinned; freshness-checked at submission
    serve_epoch:     u64                      // committee_epoch the runner intends partials to come from; pins the quorum_epoch up front. Proxies whose current committee_epoch differs MUST reject the PartialSign with EpochMismatch.
}

struct SignedReleaseRequest {
    body:        ReleaseRequestBody
    runner_sig:  Signature                    // see "Canonical domain-separated signature payloads" later in §3.5; signed under the runner registry key with "cbss/release-request/v1" prefix.
}

request_hash := keccak256(serialize(ReleaseRequestBody))
              // Defined OVER THE BODY ONLY (not the signature). No circularity.

release_id   := keccak256(canonical(body.secret_id) || u64_le(body.version) || body.actor || body.runner_id || body.job_id || body.release_nonce)
              // Stable per release attempt; does NOT include request_block. Used for proxy bloom + chain dedup.

canonical(SecretId) := secret_id.account || secret_id.key_hash       // 20 + 32 = 52 bytes, fixed encoding
```

**Canonical domain-separated signature payloads.** All sigs use a domain-string prefix to prevent cross-protocol replay; implementations MUST sign exactly these byte layouts:

```
runner_sig (in SignedReleaseRequest):
    sign(runner_registry_priv,
         keccak256("cbss/release-request/v1" || request_hash))

proxy_sig (in PartialSignResponse, also reused in SubmitReleaseReceipt verbatim):
    sign(proxy_identity_priv,
         keccak256("cbss/partial-sign-response/v1" ||
                   request_hash ||
                   proxy_id ||
                   serialize(sigma_i) ||
                   u64_le(committee_epoch_at_serve) ||
                   u64_le(served_at_block)))

challenge_sig (in SubmitLivenessChallenge):
    sign(runner_registry_priv,
         keccak256("cbss/liveness-challenge/v1" ||
                   request_hash ||
                   proxy_id))

response proxy_sig (in LivenessChallengeResponse):
    sign(proxy_identity_priv,
         keccak256("cbss/liveness-response/v1" ||
                   challenge_id ||
                   proxy_id ||
                   u8(reason) ||
                   keccak256(serialize(evidence))))

new_committee_sig / prior_committee_sig (in RotateCommittee):
    see §3.5 RotateCommittee for the exact payloads, also domain-separated under
    "cbss/dkg-commit/v1" and "cbss/reshare-zeroize/v1" respectively.
```

**Identity binding (used by IBE encryption AND receipt pairing-check, must agree byte-for-byte):**

`I := hash_to_G1( canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch),  domain = "cbss/ibe/v1" )`

The owner (at SetSecret/FinalizeSecretVersion), the proxy (at PartialSign), and the chain (at SubmitReleaseReceipt pairing-check) all compute `I` from the same inputs in the same encoding. AAD on the AES-GCM `wrapped_dek` envelope uses the same canonical encoding: `aad = canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)`.

**Sender:** the proxy identified by `proxy_id` (its `proxy_sig` must verify against `CbssProxy.pubkey`).

**Chain validation** (current-head; the chain does not read historical state):

1. `request_hash` and `release_id` are recomputed from `runner_request.body` (NOT including the signature; see request_hash definition above).
2. `body.request_block ∈ [head − REQUEST_FRESHNESS_BLOCKS, submission_block]`. Out of range → `StaleRequestBlock`.
3. `runner_request.runner_sig` verifies `request_hash` against the runner registry at **current head**.
4. **Recipient consistency.** Look up `SecretVersion[body.secret_id, body.version]`. The receipt's `body.recipient` MUST equal the stored `SecretVersion.recipient`. Reject with `RecipientMismatch` otherwise. (Without this, a malicious runner could request a partial under a different release key's MPK; the partial passes pairing under that other MPK but doesn't decrypt this SecretVersion's `wrapped_dek`.) Also require `SecretVersion.pending == false`.
5. ACL/manifest/job-assignment for `(actor, runner_id, job_id, secret)` valid at **current head**. **Trade-off:** if the ACL was permitted at `request_block` but revoked within the freshness window before the proxy submits, the receipt is **rejected** — the proxy ate the work for that one request. This is the cost of avoiding a historical-read API. Bounded by `REQUEST_FRESHNESS_BLOCKS` (~6 min); proxies should submit promptly, and runners who try to weaponize this lose more from gas + grief than they gain.
6. **Reshare-aware committee lookup.** Resolve `(committee, vss_commitments)` for `committee_epoch_at_serve`:
   - If `committee_epoch_at_serve == release_key.committee_epoch` (current): use the live committee + commitments.
   - Else if `prior_committee_epochs:{release_key_id}` contains an entry with `epoch == committee_epoch_at_serve` AND `submission_block < entry.expires_at`: use that entry's committee + commitments. (Vec lookup; multiple prior epochs may be retained simultaneously per §3.5 RotateCommittee.)
   - Else: reject with `StaleCommitteeEpoch`.
   `proxy_id` must be a member of the resolved committee at that epoch.
7. `proxy_sig` verifies over `(request_hash, proxy_id, sigma_i, committee_epoch_at_serve, served_at_block)` under `proxy_id`'s registered pubkey.
8. **BLS partial-signature pairing check**: chain reads `wrap_epoch` from the SecretVersion (chain has it; it's immutable). Computes `I = hash_to_G1( canonical(body.secret_id) || u64_le(body.version) || u64_le(wrap_epoch), domain = "cbss/ibe/v1" )` — identical encoding to the one the owner used at encryption time. Looks up the proxy's `S_i ∈ G2` from the resolved release key's `vss_commitments` (current epoch or grace-window prior). Checks `e(sigma_i, G2_gen) == e(I, S_i)`. Fail → `InvalidPartialReencrypt` (chain emits a slashing-evidence event automatically; receipt rejected; no payment).
9. `(release_id, proxy_id)` not previously recorded in `release_receipt`. **Dedup is on `release_id`** (which includes `release_nonce`), not `request_hash` — a runner who re-pins a fresh `request_block` for the same nonce cannot get a second receipt billed by the same proxy. A runner who issues a fresh `release_nonce` for a legitimate second pull within the same job CAN receive a second receipt — that's the intended use of the nonce.
9a. **Single-epoch quorum (runner-pinned).** `committee_epoch_at_serve == body.serve_epoch`. The quorum_epoch is fixed by the runner up front in the signed body; the chain enforces every receipt's `committee_epoch_at_serve` matches the runner's declared `serve_epoch`. Mismatch → `MixedEpochReceipts`. Lagrange combine works only over partials from the same Shamir polynomial; pinning the epoch in the signed request prevents a racing off-epoch proxy from locking the quorum_epoch to a value the runner did not intend. If a reshare lands between the runner's `request_block` and PartialSign serve time, proxies whose current `committee_epoch` no longer matches `body.serve_epoch` reject with `EpochMismatch` (see §3.7); the runner must re-issue with a fresh `release_nonce` and updated `serve_epoch`.
9b. **Quorum cap.** `release_receipt:{release_id}.entries.len() < threshold` (where `threshold` is read from the referenced release key for `body.serve_epoch`, the same epoch stored as `quorum_epoch` once the first receipt is accepted). Once t receipts are recorded for a `release_id`, additional receipts (from any of the other n-t proxies the runner may have fanned out to) are rejected with `QuorumAlreadyReached`. This caps payment at exactly t receipts per logical release, regardless of fanout. Proxies that respond after the t-th have already submitted have done valid work but are not paid — they MUST observe this and stop attempting submission once they see the t-th receipt on chain.
10. `served_at_block ≤ submission_block`, and `served_at_block ≥ body.request_block`.
11. **`tee_attested` is chain-derived, not proxy-asserted.** The chain looks up `0x05` TEE Verifier state at `tee_att:{body.job_id}:{body.runner_id}` AT submission time. If the SecretVersion's `policy.tee_required = true`, the record must exist, be non-revoked, match the request's `job_id` and `runner_id`, have `attested_at_block <= submission_block <= expires_at_block`, and use a TEE type matching the runner registration. TEE Verifier records are produced by `SubmitTeeAttestation`, which verifies a registered ECDSA attestation key over the canonical attestation payload before writing: P-256 for SGX/TDX, P-384 for SEV-SNP. Otherwise the receipt is rejected with `SecretRequiresTEE`. The resulting boolean is what gets emitted in events; proxies do not declare it.

On success: if `release_receipt:{release_id}` does not yet exist, initializes it with `quorum_epoch = body.serve_epoch` and an empty `entries` map. Then inserts `(proxy_id → ReleaseReceipt)` into `entries`. Debits `RELEASE_FEE_PER_RECEIPT` from `actor.account`; credits `proxy_id`.

**Overdraft / delinquency.** If `actor.account.balance < RELEASE_FEE_PER_RECEIPT`, the receipt is **still recorded and the proxy is still credited**, with the actor's release-payment balance going negative (capped at `MAX_RELEASE_OVERDRAFT`, governance-tunable, default 16 × RELEASE_FEE_PER_RECEIPT). Implementations whose base account codec cannot represent negative balances MAY store the negative portion in a separate release-debt ledger; the Cowboy node currently stores this as CBSS `ActorReleaseDebt`. The actor account transitions to `delinquent` status, which suspends new job dispatching to that actor until the negative balance is repaid. On Cowboy, `JobSubmit` rejects outstanding `ActorReleaseDebt`; `FundActor` repays that debt before any newly funded balance becomes spendable and emits `cbss.actor.debt_repaid` when repayment is applied. If overdraft would exceed `MAX_RELEASE_OVERDRAFT`, the receipt is rejected with `ActorAccountInsufficient` and no payment occurs — proxies that observe this on chain SHOULD stop accepting `PartialSign` requests from this actor until repayment is observed. This separates "honest proxy was paid for honest work" (always succeeds within overdraft cap) from "actor pays its bills" (enforced by delinquency suspension + cap).

**Each receipt** emits one event:

```
event ReleaseReceiptRecorded {
    release_id:    Bytes32             // stable across t receipts for the same logical release
    request_hash:  Bytes32             // identifies the specific signed request this receipt fulfilled
    account:       Address
    actor:         ActorAddress
    runner:        RunnerAddress
    key_hash:      Bytes32             // == secret_id.key_hash; same caveat as §3.2 (dictionary-guessable)
    version:       u64
    proxy_id:      ProxyId             // single proxy per event
    tee_attested:  bool                 // chain-derived from TEE Verifier state at submission
    block:         BlockHeight
}
```

**`SecretReleased` (quorum event)** is emitted when the t-th receipt for a given `release_id` lands, carrying the actual `proxy_set: [ProxyId; t]` accumulated in `release_receipt:{release_id}`:

```
event SecretReleased {
    release_id:    Bytes32
    account:       Address
    actor:         ActorAddress
    runner:        RunnerAddress
    key_hash:      Bytes32
    version:       u64
    tee_attested:  bool                 // chain-derived; aggregates true iff every contributing receipt observed valid TEE attestation
    proxy_set:     Vec<ProxyId>         // exactly the t proxies whose receipts crossed the quorum threshold
    block:         BlockHeight
}
```

This separates "proxy was paid for honest work" (per-receipt event, one per receipt) from "the secret was successfully released" (quorum event, one per release). The chain knows the threshold `t` from the referenced release key, so the threshold-cross detection is deterministic.

#### RequestAccountDkg (opcode 77)

```
RequestAccountDkg {}                           // sender = the account itself
```

**Sender:** the account owner. Triggered explicitly by an owner or implicitly by the cowboy CLI on first `SetSecret` if no `AccountReleaseKey` exists yet.

**Effects:** Locks `DKG_BOND` from the requesting account. VRF-selects `n = DEFAULT_N` proxies from the eligible set, weighted by `stake × health_score` (see §4.4). Writes a `DkgPending { scope, committee, deadline = current_block + DKG_FINALIZE_BLOCKS, bond_amount, requester }` record at `dkg_pending:{scope_serialized}`. Off-chain, the selected committee runs the DKG ceremony (§3.6.1) and posts the result via `RotateCommittee` with `scope = Account(sender)` and `new_committee_epoch = 1`. On successful `RotateCommittee`, the chain refunds `DKG_BOND` in full and clears the `DkgPending` record.

If the DKG ceremony fails to commit by `deadline`, the `DkgPending` record stays on chain until expired by **`ExpireDkgPending`** (see below).

#### ExpireDkgPending (opcode 81)

Permissionless cleanup of an expired `DkgPending` record. Settles the bond and emits a public failure event so the requester can retry.

```
ExpireDkgPending {
    scope: ReleaseKeyScope    // identifies the DkgPending entry to expire
}
```

**Sender:** any account.

**Effects:** validates that:

1. `dkg_pending:{scope_serialized}` exists.
2. `current_block >= DkgPending.deadline`.
3. No `RotateCommittee` for this scope has landed (i.e., the DKG didn't complete in some other path).

On success: refunds `(DkgPending.bond_amount - DKG_TIMEOUT_SLASH)` to `DkgPending.requester`; routes `DKG_TIMEOUT_SLASH` to the slashing pool (a small fraction, default 5% of the bond, governance-tunable); also pays a small fixed reward to the calling account from the slashing pool to incentivize permissionless cleanup. Deletes `dkg_pending:{scope_serialized}`. If the `scope` was an override-path `SecretSpecific(secret_id, version)`, the corresponding pending `SecretVersion` is **erased without a tombstone** — pending versions are not "real" versions until finalized, so they're treated as never-having-existed when expired. The chain also rolls back `SecretMetadata.latest_version` if it was advanced by the abandoned `SetSecret`, freeing the version slot for retry. Emits `DkgExpired { scope, requester, refunded, slashed }`.

The requester may retry by submitting a fresh `RequestAccountDkg` (default path) or `SetSecret` with `committee_override` (override path). VRF re-selects a committee — likely overlapping but possibly different given health-score and stake updates.

Per-secret DKG (override path) is initiated by `SetSecret` itself with `committee_override`; there is no separate instruction for it. The same `DkgPending` record is created (keyed by `(SecretId, version)` instead of account) and the same off-chain ceremony commits via `RotateCommittee` with `scope = SecretSpecific(...)`.

### 3.6 Threshold ceremonies

#### 3.6.1 DKG (initial keypair establishment)

Triggered by `RequestAccountDkg` (account-scoped) or by `SetSecret` with `committee_override` (secret-scoped). Off-chain protocol:

The protocol is the standard threshold BLS DKG (FROST-derived for BLS sigs) as exposed by the chosen vetted library. The devnet implementation uses the pinned Commonware BLS DKG state machine. Sketch:

1. **Round 1.** Each proxy `i` samples a random degree-`t-1` polynomial `f_i(x)` over the BLS12-381 scalar field and broadcasts Feldman/Pedersen commitments to its coefficients (peer-to-peer over the committee mesh; no on-chain anchor).
2. **Round 2.** Each proxy `i` sends `f_i(j)` to each peer `j`, encrypted under `j`'s registry pubkey. Recipients verify the share against the broadcast commitments using a single G2 multi-scalar multiplication.
3. **Aggregation.** Each proxy computes its share `s_i = Σ_j f_j(i)` (a scalar), summing only the qualified dealers when timeout/complaint handling excluded a dealer. The group `MPK = Σ_j C_{j,0}` ∈ G2 (sum of each qualified polynomial's constant-term commitment in G2). Each proxy's published VSS commitment `S_i = s_i · G2` is computable from the aggregated polynomial commitments at index `i`.
4. **On-chain commit.** Once each proxy has its share `s_i` and the group `MPK`, the committee assembles `new_committee_sigs` — t-of-n signatures over the canonical DKG-commit payload (see RotateCommittee). One proxy posts `RotateCommittee(scope, new_committee_epoch = 1, new_mpk, vss_commitments = [S_1..S_n], new_committee_sigs)`. The chain verifies: (a) each `S_i` is a valid G2 point, (b) `new_committee_sigs.len() >= threshold` and all sigs are from members of `new_committee` over the canonical payload, (c) on a reshare, `new_mpk == prior_release_key.mpk`. **The chain does NOT verify Shamir consistency on chain** — that's the committee's responsibility off-chain via VSS during DKG, attested to by the threshold signatures. (A naive "sum(S_i) == MPK" check would be mathematically wrong since S_i are polynomial evaluations, not coefficient commitments.)

If any proxy is detected sending malformed shares (verifiable: VSS commitment mismatch), it can be slashed for `DkgSabotage` (§4.3) by any party submitting the equivocation evidence.

Implementation note: `cbss-crypto` exposes qualified-set finalization so an offline or excluded dealer no longer forces unanimous abort. This does not weaken the ship requirement that the final DKG be vetted and bias-free; the qualified-set hook is ceremony liveness plumbing, not a replacement for the audited DKG protocol.

#### 3.6.2 Reshare (proactive secret sharing)

Triggered by:
- **Scheduled rotation:** every `RESHARE_INTERVAL_BLOCKS` (default ~6 months) for both `AccountReleaseKey` and `SecretReleaseKey` records.
- **Committee churn:** when the count of healthy committee members drops to `t + RESHARE_SAFETY_MARGIN`.
- **Owner request:** the owner of the account (or of the secret in the override case) pays for an immediate reshare.

Protocol: standard proactive secret sharing on the existing `MPK`. Output is a fresh share polynomial of the same secret, distributed to a possibly-different committee of `n` proxies. `MPK` is preserved; `committee_epoch` increments. **Existing SecretVersions retain their `wrap_epoch`** — reshare does not invalidate stored ciphertext or in-flight release requests; PSS guarantees the new shares produce valid partials for any historical identity under the same MPK.

#### 3.6.3 Threshold partial signature (release)

The runtime release operation, per the threshold-IBE construction in §3.4.3.

Inputs at the proxy:
- The runner's release request (signed; carries `recipient`, `job_id`, `request_block`, `serve_epoch`, and request-binding fields). `serve_epoch` pins which share-polynomial epoch the runner expects partials from; proxies reject with `EpochMismatch` if their current release-key `committee_epoch` differs. The IBE identity still comes from the SecretVersion's immutable `wrap_epoch`, not from `serve_epoch`.
- The proxy's local Shamir share `s_i ∈ scalar field of BLS12-381` of the implicit `MSK`.

Each proxy:

1. Validates the request (§3.7), looking up the relevant `AccountReleaseKey` or `SecretReleaseKey` per the request's `recipient` field and checking `body.serve_epoch == release_key.committee_epoch` at current head.
2. Reads `wrap_epoch` from the SecretVersion on chain. Computes the identity using the canonical encoding:
   `I = hash_to_G1( canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch), domain = "cbss/ibe/v1" )`.
3. Computes its partial BLS signature on the identity:
   `σ_i = s_i · I` (a point in G1).
4. Returns the canonical `PartialSignResponse` wire shape:
   ```
   PartialSignResponse {
       sigma_i:                 G1Bytes
       proxy_id:                ProxyId
       committee_epoch_at_serve: u64                   // current release_key.committee_epoch at the time of partial-sign
       served_at_block:         BlockHeight
       proxy_sig:               Signature              // exact byte layout: see "Canonical domain-separated signature payloads" earlier in §3.5; signed under the proxy identity key with the "cbss/partial-sign-response/v1" domain prefix. SAME bytes as the receipt's proxy_sig — proxy can hand the response into the receipt verbatim.
   }
   ```
   The proxy does NOT include its own VSS commitment in the response — the chain looks up `S_i` from the release key's `vss_commitments` (current or retained-prior epoch) keyed by `proxy_id` + `committee_epoch_at_serve`. This prevents a malicious proxy from substituting a different commitment.

No NIZK construction is required — verification (at receipt-submission time) is the standard BLS partial-signature pairing check `e(σ_i, G2_gen) == e(I, S_i)` against the on-chain VSS commitment `S_i ∈ G2`.

The runner combines `t` partials via Lagrange interpolation in G1 to obtain the threshold signature `σ = MSK · I ∈ G1`, then derives the IBE key `K = HKDF(serialize(e(σ, G2_gen)), "cbss/ibe/v1" || aad)` and AES-GCM-decrypts `wrapped_dek` with `K`.

### 3.7 Proxy-side validation of release requests

Each proxy enforces, on every `PartialSign` RPC, that:

Proxies validate release requests against chain state at the **current head** (not historical). The table below is the canonical proxy-side validation checklist.

| Check | Source of truth |
|---|---|
| `request_block ∈ [head - REQUEST_FRESHNESS_BLOCKS, head]` | proxy local clock + chain head |
| Runner registry membership and active status | `0x01` (Runner Registry) at current head |
| Runner currently assigned to `job_id` | `0x02` (Job Dispatcher) at current head |
| Actor's CIP-6 manifest declares the requested `key` | actor's deployed manifest at current head |
| `SecretPolicy.actors` permits this actor (or `None` and same-account) | `SecretVersion.policy` at current head |
| If `tee_required`, runner has a live non-revoked `tee_att:{job_id}:{runner}` record written through a trusted-key signed-attestation path | `0x05` (TEE Verifier) |
| Anti-replay: `(release_id, proxy_id)` not previously served | proxy local bloom (24h) + chain `release_receipt` (dedup is on `release_id`, the stable per-(secret, version, actor, runner, job) tuple — `request_hash` is fresh per `request_block` and is NOT used for dedup) |
| Per-actor rate limit: ≤ `MAX_RELEASES_PER_ACTOR_PER_HOUR` | proxy local |
| Proxy is a member of the referenced release key's `committee` at current head | `0x04` |
| `body.serve_epoch == release_key.committee_epoch` at current head (proxy rejects with `EpochMismatch` if reshare landed between request_block and serve time) | `0x04` |
| `SecretVersion.pending == false` | `0x04` |

**Revocation propagation semantics.** Revocations (e.g., `UpdateSecretPolicy` removing an actor) are effective at chain finality. Proxies MAY cache chain reads with TTL ≤ `PROXY_CACHE_TTL_BLOCKS`. Net worst-case revocation latency is `finality_blocks + PROXY_CACHE_TTL_BLOCKS` × `block_time`. There is no "instant atomic" revocation claim — revocation is "effective at finality + cache TTL of any participating proxy." A runner who tries to use a revoked credential between revocation and propagation gets a partial that's authorized at the now-stale cached state; this is a documented and bounded window, NOT a vulnerability.

Failures are reported with structured error codes (`StaleRequestBlock`, `SecretAccessDenied`, `SecretPending`, `SecretCommitteeUnavailable`, etc.); the runner retries with corrected inputs.

### 3.8 Runner pull flow

```
1. Actor task invokes runner.http(..., secrets=["SLACK_API_KEY"]).
2. Runner R looks up the secret-owning account (the actor's owning account by default,
   or the explicit cross-account owner if the entitlement uses {account, key} form).
   The runner-side SDK computes key_hash = keccak256(account || "SLACK_API_KEY") locally;
   plaintext key never leaves the runner sandbox.
3. Runner R syscalls SYS_FETCH_SECRET_METADATA(secret_id = SecretId{account, key_hash},
   version_or_latest) → SecretMetadata + the referenced ReleaseKey snapshot
   (Account or SecretSpecific). The syscall takes SecretId, not plaintext.
4. Runner R picks t of n committee proxies (prefers non-suspended, healthier, low-latency proxies; fall-through to remaining n-t on failure).
5. Runner R generates a fresh release_nonce (CSPRNG, 32 B), reads the release key's
   current committee_epoch as serve_epoch, assembles ReleaseRequestBody
   with request_block = current chain head and serve_epoch = committee_epoch,
   signs it with its runner-registry key
   (NOT an ephemeral key — see §3.4.5 / §3.5 for the registry-key requirement).
   Sends SignedReleaseRequest = { body, runner_sig } to t of n committee proxies in parallel
   (preferring non-suspended, healthier, low-latency proxies; fall-through to remaining n-t on failure).
6. Each proxy validates (§3.7), decrypts its local sealed share with AAD bound to `(release-key scope, committee_epoch)`, verifies the scalar against the VSS commitment polynomial, and returns its BLS partial signature σ_i on the identity
   (PartialSignResponse with sigma_i, committee_epoch_at_serve, served_at_block, proxy_sig).
7. Runner R verifies each σ_i with a single pairing check against the proxy's VSS commitment
   (looked up on chain by proxy_id + committee_epoch_at_serve);
   rejects duplicate proxy indexes, and Lagrange-combines σ_i to produce σ = MSK · I.
8. Runner R derives K = HKDF(serialize(e(σ, G2_gen)), "cbss/ibe/v1" || aad); AES-GCM-decrypts wrapped_dek → DEK.
9. Runner R fetches CBFS object, AES-GCM-decrypts with DEK + AAD verification → plaintext.
10. Runner R passes plaintext to the in-memory ${SLACK_API_KEY} substitutor at request-construction
    in runner-http / runner-mcp. NO process-wide env var injection on the default path
    (see §3.9).
11. Runner R executes the templated request.
12. Runner R zeroizes plaintext, DEK, σ partials.
13. Each of the t participating proxies independently submits SubmitReleaseReceipt
    (handing the SignedReleaseRequest verbatim into the receipt). Runner does NOT submit
    any audit/payment tx; payment flows directly proxy ← actor account, capped at quorum t.
```

Latency target: < 250 ms p50 for the threshold round (5 proxies, 3 same-continent, parallel) + pairing-verify + AES-GCM-decrypt + CBFS fetch. Bottleneck: the threshold round-trip and CBFS fetch (parallelizable with the threshold round).

### 3.9 Runtime sandbox: in-memory secret bundle (default), env vars only for spawned subprocesses

**Default path: in-memory template substitution, no process env vars.** Process-wide environment is leaky — other threads, libraries, signal handlers, `/proc/$pid/environ` reads, and crash dumps can all observe it; serialization mutexes only help cooperating code. The default release path therefore:

- Holds plaintext in a `Zeroizing<Vec<u8>>` `SecretBundle` keyed by KeyName.
- Performs `${KEY}` substitution **at request-construction time** inside `runner-http` / `runner-mcp` (against headers, URL, body, JSON tool args) — the substitution layer reads the bundle directly without touching the process environment.
- Drops the bundle (zeroizes) at the end of the runner-op.
- Never sets `os.environ[KEY]` for HTTP / MCP / LLM tool calls.

**Subprocess path: explicit env map, no process env mutation.** Some integrations (notably MCP stdio servers spawned by the runner) require a child process that reads its credentials from the environment. For these:

- Build an explicit `env: HashMap<String, Zeroizing<String>>` for the child.
- Pass via `Command::env_clear().envs(env)` — the child inherits ONLY the named entries, not the parent's environment.
- The parent's process environment is never mutated.
- Drop the `Command` builder immediately after spawn and zeroize the source env map.
- Residual exposure: Rust's `std::process::Command` copies env values into its own platform-specific storage before spawning, and the standard library does not guarantee that copy is zeroized. Treat subprocess env delivery as an explicit compatibility exception, not the default secret path.

**PVM Python guardrails:**

- The actor's PVM Python code observes only `${KEY}` placeholders. The PVM does not have a `SecretBundle` reference; substitution happens at the runner layer, after the syscall boundary.
- Direct `os.environ[KEY]` reads from PVM Python are blocked by the sandbox for any key declared in the actor's `secrets.read` entitlement (deny-list installed at sandbox init).
- Logging adapters scrub strings matching active bundle values from spans and trace events on a best-effort basis. The primary defense is preventing PVM Python from ever holding the value.

Process-wide env injection is unsafe by default for the reasons listed above. The bundle-and-substitute pattern keeps plaintext bounded to the request-construction code path.

---

## 4. Parameters

All parameters governance-tunable via CIP-12 Tier 0 proposals.

### 4.1 Gas

| Instruction | Default cost | Notes |
|---|---:|---|
| `SetSecret` (default path) | `12_000` | Single wrapped_dek, no DKG. |
| `SetSecret` (override path, intent only) | `8_000 + 30_000 + DKG_BOND` | No ciphertext yet; just enqueues DKG. |
| `FinalizeSecretVersion` | `8_000` | Attaches ciphertext post-DKG; cheap. |
| `UpdateSecretPolicy` | `6_000` | Pure metadata; no re-wrap. |
| `DeleteSecretVersion` | `5_000` + CBFS-drop fee | CBFS-drop reuses CIP-9 §6 cost. Cascades to `SecretReleaseKey` deletion if override. |
| `DeleteSecret` | `5_000 × num_versions` | Linear in versions; bounded by `MAX_VERSIONS_PER_SECRET`. |
| `RegisterCbssProxy` | `15_000` | One-time. |
| `DeregisterCbssProxy` | `8_000` | Plus reshare costs incurred by `RotateCommittee`. |
| `RotateCommittee` | `25_000 + 1_000 × n` | Heavy because of VSS verification. |
| `SlashCbssProxy` | `12_000 + evidence-verification cost` | Verification varies per `FaultClass`. |
| `SubmitReleaseReceipt` | `8_500` | Two pairing checks (BLS partial-sig verify) + runner sig verify + proxy sig verify per receipt. Submitted independently by each of t proxies. |
| `RequestAccountDkg` | `30_000 + DKG_BOND` | DKG bond returned on success, partially slashed on timeout. |
| `SubmitLivenessChallenge` | `5_000` | Anchors a challenge; deducted from runner. |
| `LivenessChallengeResponse` | `4_000` | Proxy's response. |

### 4.2 Stake / committee

| Parameter | Default | Description |
|---|---:|---|
| `MIN_PROXY_STAKE` | `10,000 CBY × 10⁹ wei` | Minimum operator stake. |
| `PROXY_SOAK_PERIOD` | `216,000 blocks` (~30 days) | Before VRF-eligibility. |
| `UNBOND_COOLDOWN` | `100,800 blocks` (~14 days) | Stake locked during slashing window. |
| `MIN_COMMITTEE_SIZE_FLOOR` | `5` | If eligible-set < 5, new DKGs are queued; existing keys continue to function. |
| `DEFAULT_N` | `5` | Default committee size for account-scoped DKG. |
| `DEFAULT_T` | `4` | Default release threshold for the five-proxy account DKG. This matches the vetted Commonware `N3f1` quorum for `DEFAULT_N = 5`; override path admits up to `MAX_OVERRIDE_N`. |
| `MIN_OVERRIDE_T` | `3` | Floor on per-secret override threshold. |
| `MAX_OVERRIDE_N` | `15` | Ceiling on per-secret override committee size. Bounds DKG cost. |
| `RESHARE_INTERVAL_BLOCKS` | `1,300,000` (~6 months) | Scheduled reshare cadence (per release key, account or secret-scoped). |
| `RESHARE_SAFETY_MARGIN` | `1` | Trigger reshare when healthy < `t + margin`. |
| `DKG_FINALIZE_BLOCKS` | `300` (~1 hour) | DKG ceremony deadline. |
| `LIVENESS_RESPONSE_BLOCKS` | `100` (~20 min) | Window for a proxy to respond to a `SubmitLivenessChallenge` before the challenge transitions to `Unanswered`. Note: NO automatic slash follows — it's a health-score signal only. |
| `REQUEST_FRESHNESS_BLOCKS` | `32` (~6 min) | Maximum age of `request_block` accepted by proxies and chain receipts. Bounds revocation propagation latency. |
| `RESHARE_GRACE_BLOCKS` | `100` (~20 min) | Window after a `RotateCommittee` during which receipts under that prior epoch are still accepted (paired against retained prior commitments). After expiry, the entry is GC'd and stale-epoch receipts are rejected. |
| `MAX_PRIOR_COMMITTEE_EPOCHS` | `4` | Maximum simultaneously-retained prior committee epochs per release key. Allows up to 4 reshares within one `RESHARE_GRACE_BLOCKS` window without losing prior-epoch receipts. Exceeding the cap causes `RotateCommittee` to fail with `ReshareGraceCapacity` until at least one prior epoch's grace window expires. |
| `PROXY_CACHE_TTL_BLOCKS` | `4` (~48 s) | Maximum staleness of proxy-cached chain reads. |
| `RELEASE_FEE_PER_RECEIPT` | `governance-tunable` | Fee debited from actor account on each `SubmitReleaseReceipt`. Goes to the submitting proxy. |
| `MAX_RELEASE_OVERDRAFT` | `16 × RELEASE_FEE_PER_RECEIPT` | Maximum negative release-payment balance an actor may incur from receipts before further receipts are rejected with `ActorAccountInsufficient`. Below this cap, the proxy is paid even on insufficient balance and the actor is marked `delinquent`. Implementations may represent this with negative account balance or a separate release-debt ledger. |
| `LIVENESS_CHALLENGE_BOND` | `governance-tunable` (lean: 10× standard tx fee) | Bond locked from the runner at `SubmitLivenessChallenge`. On `Resolved`, forfeited to the challenged proxy. Refunded to the runner on `Unverifiable` and `Unanswered`. |
| `MIN_CHALLENGE_DELAY_BLOCKS` | `REQUEST_FRESHNESS_BLOCKS + 32` (~12 min) | Minimum elapsed blocks between a `body.request_block` and a `SubmitLivenessChallenge` referencing it. MUST be greater than `REQUEST_FRESHNESS_BLOCKS`, so valid receipts are either already on chain or impossible to submit by the time a challenge is admissible. Premature challenges rejected with `ChallengePremature`. |
| `LIVENESS_CHALLENGE_MAX_AGE_BLOCKS` | `MIN_CHALLENGE_DELAY_BLOCKS + LIVENESS_RESPONSE_BLOCKS` (~32 min) | Maximum elapsed blocks between `body.request_block` and challenge submission. Must be meaningfully greater than `MIN_CHALLENGE_DELAY_BLOCKS`; older requests can no longer be challenged. |
| `DKG_BOND` | `governance-tunable` | Refundable bond locked at `RequestAccountDkg` / override-`SetSecret` time. Refunded on successful DKG commit; reduced by `DKG_TIMEOUT_SLASH` on `ExpireDkgPending`. |
| `DKG_TIMEOUT_SLASH` | `5%` of `DKG_BOND` | Portion of the DKG bond forfeited to the slashing pool when `ExpireDkgPending` settles an expired `DkgPending` record. Caller of `ExpireDkgPending` receives a small fixed cleanup reward from this pool. |
| `MIN_HEALTH_FLOOR` | `0.05` | Floor on the per-proxy health-score multiplier applied to VRF weight. Prevents complete exclusion that would block reshare unanimity. |
| `GOVERNANCE_REVIEW_BLOCKS` | `216,000` (~30 days) | Window of sustained `health_score < 0.1` required to flag a proxy for an automatic CIP-12 Tier 1 deregistration proposal. |
| `MAX_LEAK_REIMBURSEMENT` | `100,000 CBY × 10⁹ wei` | Cap on the remediation-pool payout per disclosed plaintext-leak incident (governance-mediated; see §4.3). |

### 4.3 Slashing schedule

Provable on-chain only. `PlaintextLeak` and liveness non-receipt are NOT auto-slash:

- **PlaintextLeak**: evidence requires publishing the secret. Handled via off-chain disclosure → CIP-12 Tier 1 `ForcedDeregisterCbssProxy`.
- **Liveness non-receipt**: not provable on chain (packet delivery is not chain-witnessable). Handled via the §4.4 health score → governance review.

| Fault | Penalty | Detection |
|---|---|---|
| `InvalidPartialReencrypt` | 5% | BLS partial-signature pairing check fails on a submitted `σ_i` (any party can submit the failing partial as evidence) |
| `DkgSabotage` | 5% | VSS commitment / share mismatch in DKG round 2 |
| `Equivocation` | 50% | Two distinct signed responses to the same `request_hash` |

PlaintextLeak handling: a disclosed leak triggers a CIP-12 Tier 1 proposal that, if passed, calls `ForcedDeregisterCbssProxy(proxy_id)` and routes the entire stake to a remediation pool. The remediation-pool payout itself is governance-mediated (lean: capped at `MAX_LEAK_REIMBURSEMENT = 100,000 CBY` per incident).

Liveness handling: see §4.4 health score. No automatic stake loss on liveness; persistent degradation drives governance review.

### 4.4 Health score

Each proxy carries a health score in `[0.0, 1.0]`, decayed and updated based on observable behavior. Used as a multiplier on VRF selection weight; persistent low scores escalate to governance review.

| Signal | Effect |
|---|---|
| `SubmitReleaseReceipt` (positive completion) | small positive |
| `SubmitLivenessChallenge → Resolved` via admission-time receipt check (chain-verifiable; proved liveness via receipt) | small positive on the proxy; bond forfeited to the challenged proxy. |
| `SubmitLivenessChallenge → Unverifiable` via `LivenessChallengeResponse` with `InvalidRequest`, `RateLimited`, or `NeverReceived` (chain-unverifiable) | **NEUTRAL on proxy** — no automatic decrement. Bond refunded to runner. Pattern detection in off-chain governance. |
| `SubmitLivenessChallenge → Unanswered` (proxy submits no response by `deadline`) | negative on proxy; bond refunded to runner. |
| Slashing event (any FaultClass) | large negative |
| Sustained healthy uptime (per epoch) | small positive |

Concrete coefficients are governance parameters (CIP-12). The protocol enforces only that VRF weight = `stake × max(MIN_HEALTH_FLOOR, health_score)`, where `MIN_HEALTH_FLOOR` (default 0.05) prevents complete exclusion that would block reshare unanimity.

Persistent extreme degradation (health < 0.1 for ≥ `GOVERNANCE_REVIEW_BLOCKS` ≈ 30 days) flags the proxy for an automatic CIP-12 Tier 1 deregistration proposal. Governance vote follows.

### 4.5 Quotas / limits

Carrying forward from the design notes §5.4 with no changes:

| Parameter | Default | Description |
|---|---:|---|
| `MAX_SECRETS_PER_ACCOUNT` | 256 | Total distinct keys per owner. |
| `MAX_VERSIONS_PER_SECRET` | 32 | Active versions retained. |
| `MAX_SECRET_VALUE_BYTES` | 65,536 | Per-version plaintext cap. |
| `MAX_ACL_ACTORS` | 64 | Distinct actor addresses per ACL. |
| `MAX_SECRETS_PER_RUNNER_OP` | 8 | `secrets=[...]` length. |
| `MAX_RELEASES_PER_ACTOR_PER_HOUR` | 1,000 | Per-proxy-enforced rate limit. |

---

## 5. SDK surface (CIP-6 extension)

### 5.1 New entitlement

```json
{ "id": "secrets.read",
  "params": {
    "keys": [
      "SLACK_API_KEY",
      "OPENAI_API_KEY",
      { "account": "0xacct1...", "key": "SHARED_API_KEY" }
    ]
  }
}
```

Subset upgrade rule (CIP-6 §12.1) applies: an actor upgrade may remove keys from this list but never add them. Cross-account form `{"account", "key"}` is the canonical wire shape.

The CIP-6 §12.3 entitlement registry table MUST be amended in the same PR to add:

| Entitlement | Scope | Action | Constraints | Role |
|---|---|---|---|---|
| `secrets.read` | secret | read | `params.keys: List<KeyName \| {account, key}>` | actor |

### 5.2 Runner-op kwarg

```python
await runner.http(
    "https://hooks.slack.com/services/...",
    headers={"Authorization": "Bearer ${SLACK_API_KEY}"},
    secrets=["SLACK_API_KEY"],
)

await runner.mcp(
    server="github",
    tool="create_issue",
    args={"token": "${GITHUB_TOKEN}", "title": "..."},
    secrets=["GITHUB_TOKEN"],
)

# Pin a specific version:
await runner.http(..., secrets=[("SLACK_API_KEY", {"version": 3})])

# Cross-account:
await runner.http(..., secrets=[("SHARED_API_KEY", {"account": "0xacct1..."})])
```

`runner.llm` accepts `secrets=[...]` only when the LLM op orchestrates server-side tool calls that need them (e.g., MCP tool plumb-through). Plain text-completion calls reject `secrets=[...]` with `SecretsNotApplicableHere`.

### 5.3 Errors

Canonical error names — implementations MUST use these to avoid divergent vocabularies. SDK / runner / proxy / chain handlers all map their failure modes to this set.

```
// Lookup / state failures
SecretNotFound                 // no SecretMetadata for (account, key_hash)
SecretVersionDeleted           // version was deleted by owner
SecretPending                  // override-path version awaiting FinalizeSecretVersion
SecretAccessDenied             // ACL or manifest entitlement does not permit (actor, runner)
SecretRequiresTEE              // policy.tee_required = true and runner has no valid CIP-23 attestation
SecretQuotaExceeded            // hit MAX_SECRETS_PER_ACCOUNT / MAX_VERSIONS_PER_SECRET / MAX_ACL_ACTORS / etc.
SecretCommitteeUnavailable     // < t proxies responsive at fetch time
SecretDkgInProgress            // initial ceremony in flight (account or secret-scoped override)
SecretsNotApplicableHere       // runner.llm with secrets=[...] but no server-side tool plumbing

// Setup-time failures
MissingAccountReleaseKey       // SetSecret-time failure on default path with no AccountReleaseKey on file
WrapEpochMismatch              // SetSecret/FinalizeSecretVersion: claimed wrap_epoch ≠ release_key.committee_epoch at submission
AadMismatch                    // wrapped_dek.aad ≠ canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)
RecipientMismatch              // runner_request.body.recipient ≠ SecretVersion.recipient (anti-committee-substitution)

// Freshness / ordering
StaleRequestBlock              // body.request_block outside REQUEST_FRESHNESS_BLOCKS window
StaleChallenge                 // SubmitLivenessChallenge submitted after LIVENESS_CHALLENGE_MAX_AGE_BLOCKS from body.request_block
StaleCommitteeEpoch            // committee_epoch_at_serve neither current nor in retained prior_committee_epochs
EpochMismatch                  // proxy's current release_key.committee_epoch differs from body.serve_epoch (runner pinned a different epoch than the proxy's current view); runner must re-issue with fresh release_nonce + updated serve_epoch
ReshareGraceCapacity           // RotateCommittee would exceed MAX_PRIOR_COMMITTEE_EPOCHS; wait for grace window to expire

// Signature / proof failures
InvalidRunnerSignature         // runner_request.runner_sig fails verification against runner registry
InvalidProxySignature          // SubmitReleaseReceipt.proxy_sig or PartialSignResponse.proxy_sig fails verification
InvalidPartialReencrypt        // BLS pairing check e(σ_i, G2_gen) == e(I, S_i) fails — auto-emits slashing-evidence event

// Receipt / dedup failures
ReceiptAlreadyRecorded         // (release_id, proxy_id) already exists in release_receipt
ReceiptOrderingInvalid         // served_at_block < request_block, or > submission_block
QuorumAlreadyReached           // release_receipt:{release_id} already has t entries; additional receipts rejected (caps payment at quorum)
MixedEpochReceipts             // committee_epoch_at_serve ≠ body.serve_epoch / quorum_epoch initialized from the runner-pinned serve_epoch; reject (Lagrange combine requires single-polynomial partials)
ActorAccountInsufficient       // SubmitReleaseReceipt would push actor release debt past −MAX_RELEASE_OVERDRAFT; receipt rejected, proxy not paid for this attempt
LivenessChallengeAlreadyOpen   // (release_id, proxy_id) already has an open challenge (per-release dedup)
ChallengePremature             // SubmitLivenessChallenge submitted before MIN_CHALLENGE_DELAY_BLOCKS elapsed since body.request_block

// Decryption failures (runner-side / SDK)
CiphertextCorrupted            // AES-GCM auth tag mismatch on wrapped_dek or CBFS object
```

### 5.4 CLI

```
cowboy secrets set <key> <value> [--actors=A,B] [--account=...] [--tee-required] [--committee-override] [--threshold=T/N]
cowboy secrets list [--account=...]
cowboy secrets versions <key>
cowboy secrets policy <key> [--add-actor=...] [--remove-actor=...] [--tee-required=true|false]
cowboy secrets delete <key> [--version=N]
cowboy proxy register --stake 10000CBY  # operator-side; publishes network_addr + HPKE public key
cowboy proxy status
cowboy proxy reshare-status
```

---

## 6. Implementation notes

### 6.1 Crate layout

| Crate | Status | Purpose |
|---|---|---|
| `runner/crates/secrets-manager` | implemented for devnet | Hosts the runner-side `SecretsClient`. The pre-existing trait (`store_secret` / `get_secret` / `update_secret` / `delete_secret`) is removed; those owner-side operations are CLI/chain-client concerns. Current implementation has the threshold combiner/decrypt helper, a trait-based `ThresholdSecretsClient` core with bounded concurrent fanout/fallback and per-proxy timeouts across committee members, `HttpChainSecretMetadataResolver` for the node `GET /cbss/secret/{account}/{key_hash}?version=` metadata endpoint, `Secp256k1ReleaseRequestSigner` for chain-compatible runner request signatures, and encrypted ciphertext fetchers for the CBSS/CBFS blob path. `ProxyEndpoint` carries TLS SPKI pins plus chain health/suspension metadata, snapshots without pins fail closed, and suspended proxies are skipped while healthier active proxies are preferred before fanout. `cbssd` supplies the QUIC `PartialSign` proxy adapter with endpoint-derived SPKI-pinned client config, and `runner-node` can opt into this threshold path with `CBSS_THRESHOLD_ENABLED`. Local latency EWMA, adaptive retry tuning, and broader receipt-observation ergonomics remain v1.1/operator-hardening work. |
| `runner/crates/cbss-crypto` | implemented for devnet | Thin wrapper over vetted BLS / IBE libraries and the Commonware BLS DKG integration target (`blstrs`, Commonware, `tlock`, `aes-gcm`, `hkdf`). Identity construction, ciphertext envelope, validation, HPKE recipient-specific DKG/reshare payloads, and share storage are in place. Proactive secret sharing and the Commonware adapter are included in the June 2026 external review packet as a pre-mainnet governance gate. |
| `runner/crates/cbssd` | implemented for devnet | Operator daemon. Hosts Commonware-backed DKG ceremony orchestration, reshare orchestration, threshold-partial-sig service over QUIC+bincode, share storage at rest, audit log, slashing tx submission, and cbssd-native chain broadcasting. Current implementation has the transport-independent `PartialSignService` core, frame dispatcher, generic Tokio stream I/O helpers, `quinn` server/client adapters, `cbssd serve` health binding, persisted daemon TLS and secp256k1 operator identities, chain-compatible proxy-response signing, SPKI-pinned client verification, chain proxy TLS-SPKI metadata, endpoint-derived SPKI-pinned proxy-client construction, a runner-side QUIC `PartialSign` proxy adapter, a receipt submitter, and a current-head HTTP chain release authorizer that verifies runner signatures, freshness, ACL policy, job/runner assignment, actor manifest entitlements, TEE-required fail-closed state, and local committee membership before signing. |
| `node/execution/src/cbss.rs` | implemented for devnet | On-chain handlers for §3.5 instructions: secret registry, proxy registration/deregistration/slashing, release receipts, DKG/reshare commit, liveness challenge/response/expiry, TEE-attestation reads, and gas/receipt validation. |
| `node/rpc/src/handlers/cbss.rs` | implemented for devnet | CBSS RPC surfaces for proxy metadata, account/secret release keys, secret metadata resolution, and TEE-attestation lookup. |
| `node/cli/src/commands.rs` | implemented for devnet | `cowboy secrets *`, `cowboy proxy *`, and TEE-attestation submission surfaces. |
| `cbfs` `/v1/cbss/blob` route | implemented for devnet | HTTP route used by the owner upload / runner ciphertext-fetch path for encrypted CBSS blobs. |
| `cowboy/docs/cips/cip-9-runner-storage.md` | edit | §9.2 forward-reference: "CIP-TBD" → "CIP-24". |
| `cowboy/docs/cips/cip-2-offchain-compute.mdx` | edit | §Specification system actor table: footnote on `0x04` → CIP-24. |
| `cowboy/docs/cips/cip-6-sdk.md` | edit | §12.3 entitlement registry table: add `secrets.read`. |
| `cowboy/docs/whitepaper/cowboy-technical-whitepaper.md` | edit | §9.2 master opcode allocation: insert rows 68–84 per §3.3 above. |

### 6.2 Runner-side `SecretsClient` trait

```rust
#[async_trait]
pub trait SecretsClient: Send + Sync {
    async fn fetch_for_op(
        &self,
        ctx: &JobContext,
        actor: ActorAddress,
        keys: &[SecretRef],            // (account, key, optional version)
    ) -> Result<SecretBundle, SecretsError>;
}

pub struct SecretBundle {
    entries: Vec<(SecretRef, Zeroizing<Vec<u8>>)>,
}

impl Drop for SecretBundle {
    fn drop(&mut self) { /* explicit zeroize per entry */ }
}
```

Implementation: chain client metadata fetch → t parallel `PartialSign` RPCs over QUIC+bincode → BLS partial-signature pairing-verify → Lagrange combine → IBE decrypt of `wrapped_dek` (`K = HKDF(serialize(e(σ, G2_gen)), aad)`) → fetch CBFS object and AES-GCM-decrypt with DEK → return `Zeroizing<Vec<u8>>` per key. The bundle drops at end of runner-op. **No env-var injection on the default path** — `runner-http` / `runner-mcp` perform `${KEY}` substitution from the bundle directly at request-construction time (see §3.9). Only spawned subprocesses receive env vars, via an explicit env map (`Command::env_clear().envs(...)`).

### 6.3 No persistent owner-side DEK cache

The per-account anchoring + IBE construction means owners do not need a local DEK cache. ACL changes (`UpdateSecretPolicy`) are pure metadata and require no re-wrapping. The `cowboy secrets set` CLI holds a DEK in process memory only for the duration of one set/finalize operation, and zeroizes on exit. There is no on-disk cache to manage, prune, or seal.

### 6.4 RPC additions

In `rpc/`:

```
secrets_getMetadata(secret_id: SecretId, version_or_latest) → SecretMetadata
                  // SecretId = { account, key_hash }; raw RPC takes key_hash, not plaintext.
                  // SDK / CLI wrappers convert plaintext key_name → key_hash before calling.
secrets_getAccountReleaseKey(account) → AccountReleaseKey
secrets_getSecretReleaseKey(secret_id, version) → Option<SecretReleaseKey>   // Some iff override path
secrets_listProxies(filter) → Vec<CbssProxy>
secrets_getReleaseHistory(secret_id: SecretId, range) → Vec<SecretReleased>
proxy_health(proxy_id) → ProxyHealth
proxy_committees(proxy_id) → Vec<ActorAddress>     // which actors this proxy serves
```

---

## 7. Implementation tracking

Implementation is tracked in `cbssd-implementation-plan.md` as a single delivery split across parallelizable workstreams (chain skeleton, `cbss-crypto`, `cbssd` DKG/reshare, release path, SDK/CLI/docs). The current implementation is intended for devnet merge and wider devnet testing, not a mainnet feature-flag flip. The external crypto review is deferred to June 2026 as a separate pre-mainnet governance gate. See the plan for per-workstream deliverables and test scenarios.

The implementation review now uses `cbss-coverage-manifest.tsv` as the B12
coverage index. That manifest maps the release-path, SDK/CLI/liveness, e2e,
stress, and adversarial scenarios from the implementation plan to concrete
source/test anchors, and `cbss-review.sh` validates those anchors on each run.
Known v1.1 / pre-mainnet follow-ups are tracked outside this CIP text: full Intel
DCAP/TDX and AMD SEV-SNP/VLEK vendor-collateral validation, restoration of the
full spawned §5.9 DKG proof matrix in the current cargo harness, high-rate
stress against a spawned validator, a fake-cbssd Byzantine binary over QUIC,
and broader real-validator negative/recovery scenario coverage. External crypto
review remains deferred to June 2026; it is a separate mainnet flag-flip gate.
The reviewer packet is `cowboy/docs/security/cbss-crypto-external-review-packet.md`.

---

## 8. Security considerations

### 8.1 The t-collusion question

For the default `(n, t) = (5, 4)`, an attacker needs to compromise 4 of 5 specific operators simultaneously. With per-account anchoring (§10.2), a successful t-collusion exposes **all of the account's default-path secrets** for the duration of the compromise window, retroactively decrypting any wrapped DEKs the colluding proxies could observe at release time. Hardening levers:

- **Operator diversity** (governance): jurisdictional, software-version, hardware-source, organizational. Governance MAY refuse to admit registrations that concentrate the proxy set.
- **Governance teeth on disclosed leaks:** PlaintextLeak is NOT auto-slashable on chain (§4.3) because objective on-chain evidence would publish the secret. A disclosed leak triggers a CIP-12 Tier 1 governance proposal that, if passed, calls `ForcedDeregisterCbssProxy(proxy_id)` and routes the offending proxy's stake to a remediation pool (default cap `MAX_LEAK_REIMBURSEMENT`). With `MIN_PROXY_STAKE = 10,000 CBY` and default `t = 4`, t-collusion still risks at least `t × MIN_PROXY_STAKE` plus permanent ban — but the slash is governance-mediated, not protocol-automatic.
- **VRF committee selection:** attacker cannot pre-position; committee membership is determined per-account at DKG time.
- **Proactive reshare (insider rotation, NOT cryptographic invalidation):** every `RESHARE_INTERVAL_BLOCKS`, the share polynomial rotates. PSS preserves `MSK`, so a retained old share can still partial-sign any historical-`wrap_epoch` identity off-chain — there is no cryptographic invalidation of old share material. What reshare DOES do: (a) replaces the share at-rest in cbssd's storage (an honest proxy zeroizes per `DeleteSecretVersion`/reshare protocol), (b) rotates committee membership so previously-compromised proxies must be re-compromised under the new committee_epoch to keep contributing to t-of-n, (c) makes the prior committee no longer accepted by the chain for receipts past `RESHARE_GRACE_BLOCKS`. The honest-share-zeroization assumption is operational, not cryptographic. An attacker who exfiltrates a share before reshare retains an offline capability to threshold-sign historical identities indefinitely; deletion of the underlying secret (`DeleteSecret`) is the only way to actually invalidate.
- **Per-secret committee override:** for secrets where the per-account blast radius is unacceptable, the `committee_override` path triggers a one-off DKG with its own committee, isolating that secret's compromise surface from the rest of the account. Owners SHOULD use override for `STRIPE_LIVE_KEY`-class secrets and let routine credentials ride the account default.

### 8.2 Owner key compromise

If the owner's account key is compromised, the attacker can issue `UpdateSecretPolicy` to add an attacker-controlled actor to the ACL, then fetch any of that owner's secrets. CBSS does not defend against this and does not attempt to: account-key compromise is the limit of the model and is recovered from out-of-band (account-recovery flows are out of scope for this CIP).

### 8.3 Compromised runner

A compromised runner can exfiltrate the plaintext for the secrets it is *currently authorized to fetch*. It cannot:
- Fetch secrets retroactively (release is anti-replayed per `(job_id, secret_id, runner)`).
- Impersonate other runners (signatures over runner registry key).
- Fetch secrets for jobs it isn't currently assigned to (proxy validates dispatcher's on-chain assignment).

This is consistent with the trust model of CIP-2: the runner is in the trust path for the duration of the job, period. CBSS does not change that.

### 8.4 Validator / dispatcher / chain-observer privacy

| Party | Sees |
|---|---|
| Validator | `wrapped_dek` (AES-GCM under IBE-derived K, unrecoverable without σ), CBFS pointers, ACL, `key_hash` in storage/tx/events (dictionary-guessable for common names), audit events. Plaintext `KeyName` from deployed actor manifests (the entitlement params). NOT plaintext secret values, NOT DEKs, NOT shares. |
| Dispatcher | Job assignments only — no DEK material, no CBFS plaintext |
| Chain observer | Same as validator. `key_hash = keccak256(account || key_name)` hides literal key names from passive scraping but is **dictionary-guessable** for common names (`OPENAI_API_KEY`, `STRIPE_LIVE_KEY`, etc.) — an observer with the public account address can trivially reproduce the hash for any guessed name. Owners who require unguessability use random suffixes. |

### 8.5 Anti-replay and freshness

- Per release: `(release_id, proxy_id)` is the dedup key. `release_id` is defined canonically in §3.5 next to `ReleaseRequestBody`; it is stable across `request_block` re-pinning and includes `release_nonce`, so legitimate second pulls within a job get a distinct release_id. Proxies maintain a 24-hour bloom keyed on `(release_id, proxy_id)`; chain `release_receipt:{release_id} → { quorum_epoch, entries: Map<ProxyId, ReleaseReceipt> }` provides eventual-finality dedup and single-epoch quorum enforcement. `request_hash` (which includes `request_block`) is used only for sig verification on the specific request, not for dedup.
- Pinned-version pulls fail closed if the version was deleted (`SecretVersionDeleted`).
- `wrap_epoch` is read from the SecretVersion on chain (immutable per version); reshare does NOT invalidate in-flight requests since PSS preserves MSK and the proxy's current share validly partial-signs any historical identity.

### 8.6 DKG correctness and liveness

- **Correctness:** Pedersen VSS commitments allow any party to verify share validity. A proxy submitting a malformed share is detectable and slashable for `DkgSabotage`.
- **Liveness:** if the ceremony fails to finalize within `DKG_FINALIZE_BLOCKS`, the requesting tx's DKG bond is partially slashed and refunded; the owner may retry. Lean: VRF-select `n + 2` proxies and require `n` to complete (over-sample for ceremony liveness).

### 8.7 Future-shock: cryptographic break

A break of BLS12-381 (pairing-based DDH or co-CDH), AES-256-GCM, or secp256k1 ECDLP is a full-platform compromise — none unique to CBSS, all shared with the broader Ethereum/Filecoin/Cowboy ecosystems. The mitigation specific to secrets is `DeleteSecret`: dropping the CBFS object means a future cryptanalytic break finds nothing to decrypt. The chain history retains only the encrypted `wrapped_dek`, which without the CBFS ciphertext is useless. Curve agility (e.g., upgrading the IBE construction to BLS12-461 or a post-quantum threshold scheme) is a future CIP, out of scope here.

### 8.8 Comparison vs TEE-based release

| Property | TEE-rooted release | CBSS (this design) |
|---|---|---|
| Trust root | CPU-vendor attestation | t-of-n proxy non-collusion + slashing |
| Failure mode | TEE break → all secrets exfiltratable retroactively for the lifetime of the wrap | t-collusion → secrets observed by colluders during their committee tenure |
| Hardware requirement | TEE-capable runner | Standard hardware |
| Latency | Single-hop unwrap on TEE | t-of-n threshold round (~250 ms target) |
| Operational footprint | TEE provisioning per runner | New operator role; DKG ceremonies |
| Ecosystem | TEE vendors (Intel, AMD) | CBY-staked operators |
| Auditability | TEE attestation logs | On-chain `SecretReleased` events + per-proxy receipts carrying the runner-signed request |

CIP-24 picks the right column. CIP-23 keeps the left column available for *execution* (and as an additional gate via `tee_required`); the two layer cleanly.

---

## 9. Interaction with other CIPs

### 9.1 CIP-2 (Off-chain compute)

CIP-24 fills the system-actor reservation at `0x0000…0004` declared in CIP-2 §Specification. CIP-2 §Specification table SHOULD be updated to footnote-reference CIP-24 in the same PR.

### 9.2 CIP-6 (SDK + entitlements)

`secrets.read` is registered in the entitlement registry. The subset-on-upgrade invariant (CIP-6 §12.1) applies: an actor cannot expand the keys it can request without redeploying.

### 9.3 CIP-9 (Runner storage)

CIP-9 §9.2's forward-reference to a Secrets Manager system actor is fulfilled by CIP-24. The "CIP-TBD" placeholder MUST be replaced with "CIP-24" in the same PR. Note that CIP-9 §9.2's dispatcher-unwrap design remains the model for *actor-private storage*, NOT for third-party credentials. CIP-24 is for the latter; the two coexist.

### 9.4 Whitepaper §9.2 (Master opcode allocation)

CIP-24 claims opcodes 68–84 in the master allocation table. The table in whitepaper §9.2 MUST be amended in the same PR (§3.3 of this CIP shows the exact rows to insert).

### 9.5 CIP-23 (TEE Execution)

CIP-23 attestation is *optional* per secret via the `tee_required` flag. When set, the runner MUST present a CIP-23 attestation valid for the active `job_id`; the chain validates it against `0x05` (TEE Verifier) at receipt submission, and proxy serving must fail closed unless the node authorizer path can confirm a live attestation. The current devnet TEE Verifier validates registered P-256/P-384 ECDSA attestation keys over canonical CBSS attestation bytes. It does **not** yet validate Intel DCAP/TDX or AMD SEV-SNP/VLEK vendor collateral; that is a v1.1 / pre-mainnet milestone. TEE here is defense-in-depth on top of threshold release, not the trust root.

---

## 10. Rationale

### 10.1 Why threshold IBE on BLS12-381

See §3.4.5 for the full argument. Short version: vetted libraries exist for threshold BLS signatures and IBE on BLS12-381 (`blstrs`, Commonware BLS DKG, `tlock`); they do not exist for threshold ElGamal on secp256k1. The cryptographic-engineering rule "don't roll your own crypto" trumps the curve-reuse argument that originally motivated secp256k1.

The IBE construction does not use kfrags or proxy re-encryption; it uses BLS signature shares as IBE decryption keys. The recipient-targeting problem that kfrag-based PRE designs address is solved here by binding the IBE identity to per-version metadata that all parties can compute deterministically.

### 10.2 Why per-account by default, with per-secret override

Three candidate granularities: per-secret, per-actor, per-account. We picked per-account default + per-secret override.

- **Per-secret committees** scale `O(num_secrets × n)` system-wide with a fresh DKG every time someone stores a credential. Bootstrap-prohibitive.
- **Per-actor committees** isolate an actor's secrets from the rest of an account's secrets, but the isolation only materializes when ACLs are narrow. Once a secret's ACL fans out across multiple actors, an attacker just attacks the *weakest* of those committees — per-actor is no better than per-account in the wide-ACL case. Per-actor also pays a DKG every time you deploy a new actor, and forces a chain re-wrap on every ACL edit (since each ACL actor needs its own wrapped DEK). Operationally heavy with limited security gain in realistic usage patterns.
- **Per-account committees** match the practical sharing patterns of production secret management (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault are all account/project-scoped). Bootstrap is one DKG amortized over the account's lifetime. ACL edits are pure metadata. Storage is `O(1)` wrapped DEK per version regardless of ACL size.

The trade with per-account is **bigger blast radius per t-collusion**: an attacker who compromises ≥ t proxies in an account's committee can decrypt every secret that account ever wrapped under its `MPK`. Mitigations:

1. **Tunable `(n, t)` per account** — high-value accounts can raise `n` and `t` through governance-supported account parameters once larger vetted DKG quorums are enabled, instead of using the default `(5, 4)`.
2. **Per-secret committee override** — a single high-value secret (`STRIPE_LIVE_KEY`) can opt into its own committee at `SetSecret` time, isolating its blast radius from the rest of the account's secrets. This is the escape hatch.
3. **Proactive resharing** — every `RESHARE_INTERVAL_BLOCKS`, the share polynomial rotates. An attacker has a finite window.
4. **Operator diversity governance** — committee admission policy can require jurisdictional / vendor / org diversity.

Per-account-with-override is the right default: cheap and simple in the common case, with explicit isolation available for the cases that need it.

### 10.3 Why a new operator role, not extending Relay Nodes

Different failure semantics, slashing math, and operator profile (§3.1). A node can register as both Relay and Proxy; the protocol roles stay distinct.

### 10.4 Why in-memory bundle by default (and explicit subprocess env when required)

Limits blast radius. Plaintext exists only in the runner-op execution context, only as the substituted final-form request. Never enters PVM Python state; cannot be accidentally logged, persisted, or echoed in error messages.

### 10.5 Why two-layer access control (manifest ∩ ACL)

Manifest is the actor's *advertised need* (caught at deploy-time review). ACL is the owner's *consent* (caught at the runtime gate). Both layers answer different threats: a malicious actor lying about its needs is caught at deploy time; a compromised owner key that grants too broadly is at least bounded by the manifest of each individual recipient actor.

### 10.6 Why CIP-24, not CIP-23

CIP-23 is occupied by TEE Execution (Created 2026-04-20). Earlier design notes proposed CIP-23 for the secrets manager because that slot was free at design-time; that proposal is now stale. CIP-24 is the next sequential available slot. Reusing freed slots (CIP-8, CIP-17, CIP-19) creates onboarding confusion with old links and PRs.

### 10.7 Why `MPK` is preserved on reshare

Owners encrypt to `MPK`. If reshare changed `MPK`, every existing wrapped DEK on chain would become un-decryptable, forcing owner re-encryption en masse. Preserving `MPK` across reshare (proactive secret sharing on the same `MSK`) means reshare is invisible to owners — only the share polynomial rotates.

Note: the per-version IBE identity is bound to the SecretVersion's immutable `wrap_epoch`, not to the live `committee_epoch`. Reshare changes `committee_epoch` but does NOT change any existing version's `wrap_epoch`. New `SetSecret` calls after a reshare bind to the then-current `committee_epoch` as their `wrap_epoch`. The threshold-sig math works for any historical identity because PSS preserves MSK across reshare.

### 10.8 Why per-proxy receipts, not a single aggregate `RecordSecretRelease`

A single aggregate audit/payment instruction submitted "by the runner or any participating proxy" would leave payment dependent on either runner cooperation (which the runner has no incentive to provide once it has the plaintext) or implicit proxy coordination (unspecified, and prone to gas-bidding wars or drop-on-the-floor).

`SubmitReleaseReceipt` (opcode 76) instead makes each proxy submit its own receipt independently. Each accepted receipt debits `RELEASE_FEE_PER_RECEIPT` from the actor's account (subject to overdraft cap) and credits the submitting proxy. **Payment is capped at quorum**: only the first t receipts per `release_id` are paid; receipts t+1..n (which a runner may have triggered by over-fanning out) are rejected with `QuorumAlreadyReached`. Properties:

- **Runner is removed from the payment path.** Cannot grief proxies by withholding submission.
- **No coordination required.** Each proxy decides independently when to submit; the **first t** proxies to land on chain are paid; later submissions for the same release_id (whether from the n-t over-fanout or from the same proxy on a re-pin) are rejected. Proxies SHOULD watch `release_receipt:{release_id}.entries` and stop attempting once `entries.len() == t`.
- **Auditable.** `release_receipt:{release_id} → { quorum_epoch, entries: Map<ProxyId, ReleaseReceipt> }` accumulates the full t-of-n proof of release on chain, each entry carrying the verbatim runner-signed request and the verified `σ_i`. The `SecretReleased` event fires when the t-th entry lands, carrying the actual `proxy_set` of t contributors.
- **Cost:** t txs per release instead of one. Acceptable for a system whose default release rate is O(1 per actor-job); for very-high-frequency cases, an aggregator pattern is possible later without breaking the on-chain interface.

---

## 11. Future work

### 11.1 Optional Umbral outer hop

No outer Umbral / kfrag hop is part of CBSS. Per-account anchoring + IBE already gives ACL changes as pure metadata; cross-account grants resolve via ACL alone with no additional cryptographic hop.

If a future need for an outer hop arises (e.g., true cross-curve interop with non-CBSS systems), it would be a separate CIP.

### 11.2 Owner self-fetch (audit / recovery)

Let the owner re-fetch their own secret as if they were a runner — useful for audit (verifying that the stored ciphertext still decrypts to the expected plaintext) or recovery (if the owner lost their local copy of the secret value but still controls the account). CBSS has no persistent owner-side DEK cache and does not require self-fetch for normal operation; this is an opt-in capability for high-assurance operators.

### 11.3 Auto-rotation hooks

Webhook to the owner before a TTL expires; owner refreshes the secret value. Out of scope; build as an actor-layer service.

### 11.4 Cross-chain secret release

An actor on Cowboy fetching a secret stored on Ethereum (or vice versa). Out of scope.

### 11.5 HSM-backed wrapping keys

For now, owner wrapping keys derive from the account secret (HKDF). HSM integration is owner-side tooling, not protocol.

### 11.6 Quorum-issued secrets

A DAO-controlled key with k-of-n unlock among DAO members. Build as an actor-layer wrapper that owns the secret on behalf of the DAO. Not protocol.

### 11.7 Weighted DKG for high-value secrets

Per-secret tunable `(n, t)` exists only through the `committee_override` path; default account-scoped keys use `DEFAULT_N` / `DEFAULT_T`. A future enhancement could weight DKG shares by stake (so a single high-stake proxy effectively counts as multiple shares), making collusion proportionally more expensive for high-value secrets at the cost of decentralization.

---

## 12. Implementation hardening checklist

The following implementation choices are reflected by the devnet code and remain the review checklist for later hardening:

1. **DKG / threshold-IBE library stack:** locked. `blstrs` for curve ops, Commonware BLS DKG (or equivalent vetted threshold-BLS DKG) for ceremony transcripts, and `tlock` (drand reference) for the IBE construction. The principle "no rolled-our-own crypto primitives" is non-negotiable. Current qualified-set finalization support is timeout/complaint liveness plumbing around the vetted DKG path, not a substitute for the DKG protocol itself.
2. **Owner-side DEK cache:** the per-account model substantially reduces the need for one — owners only need the DEK at `SetSecret` time, not on ACL edits. Lean: no persistent local DEK cache; the cowboy CLI keeps DEKs in memory only for the duration of the `SetSecret` flow.
3. **Cross-account ACL canonical wire form:** `{"account": "0x...", "key": "..."}`.
4. **Operator role naming:** `SecretsProxy` in code, "CBSS Node" in user-facing docs.
5. **Reshare cadence default:** 6 months. Adjustable per release key (account or secret-scoped) via owner-paid `RotateCommittee`.
6. **TEE-required secret behavior on a CBSS-only deployment:** if `tee_required = true` and the runner network has no TEE-capable runners, releases fail closed with `SecretRequiresTEE` until governance enables a TEE-capable runner pool.
7. **Override committee parameter ranges:** lean `MAX_OVERRIDE_N = 15`, `MIN_OVERRIDE_T = 3`. Higher ceilings ↔ better isolation at the cost of release latency and DKG fees. Confirm.

---

## 13. Acknowledgments

CBSS draws on:
- **Drand** for the threshold-IBE ("tlock") construction this CIP adopts directly. Drand mainnet randomness beacon ships this scheme in production for time-lock encryption; CBSS uses the same primitive with a CBSS-specific identity binding.
- **Boneh-Franklin** for the underlying IBE construction.
- **FROST and threshold-BLS** for the DKG patterns; Commonware and the broader BLS12-381 ecosystem (Ethereum, Filecoin) for vetted curve and pairing implementations.
- **Lit Protocol** for showing that threshold-decryption-as-a-service is operationally viable at network scale.
- The proxy-re-encryption framing of NuCypher / Umbral is an antecedent in the literature, but CBSS uses threshold IBE rather than kfrag-based PRE; kfrags do not feature in the design.
