---
title: "CIP-9: Runner Attachable Storage"
description: Protocol definition for attaching persistent encrypted volumes to ephemeral runner jobs
icon: hard-drive
---

<Note>
  **Status:** Draft for Internal Review
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-03-18
  **Depends on:** CIP-2 (off-chain compute), CIP-3 (fee model)
</Note>

<Tip>
  CIP-9 defines the on-chain control plane and cross-component interface protocol for attaching persistent, encrypted storage volumes to ephemeral runner jobs. The storage data plane is implemented by a separate `steamtrain-client` library. CIP-10 (Container Runtime) builds on top of this CIP.
</Tip>

# CIP-9: Runner Attachable Storage

---

## Abstract

Runners in the Cowboy off-chain compute system (CIP-2) are stateless by design — each job executes in an isolated environment and terminates. This creates a gap for use cases that require persistent data: storing API keys and certificates without exposing them on-chain, accumulating large artifacts (binaries, datasets, logs) too large for on-chain storage (64 KiB inline cap, §7 whitepaper), passing intermediate state between runners in a multi-step workflow, and maintaining database or cache state for long-lived containerized services (CIP-10).

This CIP introduces **Runner Attachable Storage**: a protocol for attaching encrypted persistent volumes to runner jobs. The on-chain layer handles access control, authorization token issuance (CapTokens), and manifest-root anchoring for global consensus on data integrity. The off-chain storage data plane is implemented by **Steamtrain**, a distributed encrypted storage engine exposed to runners as a POSIX FUSE filesystem.

---

## Motivation

The four pain points that motivate this design are:

1. **Secret Management.** Runners need access to API keys, certificates, and credentials without exposing them to the public chain. These secrets must only be decryptable by authorized runners, optionally gated by TEE attestation.

2. **Off-Chain Output.** Computation frequently produces artifacts exceeding the 64 KiB on-chain inline cap (whitepaper §7). These must be stored off-chain with a verifiable content commitment anchored on-chain.

3. **Tool-Chain Data Flow.** Multi-runner workflows (e.g., OpenClaw tool pipelines) require passing large intermediate data between sequential runners without round-tripping through the chain.

4. **Container Persistence.** CIP-10 container runtimes require persistent storage layers for stateful applications, databases, and caching across job restarts.

---

## Specification

### 1. System Actor: Volume Registry (`0x0000…0009`)

The Volume Registry is a system actor at address `0x0000000000000000000000000000000000000009`. It manages the lifecycle of storage volumes, issues CapTokens for runner access, and records manifest-root anchors.

It complements the existing runner subsystem actors:

| Address | System Actor | Role |
|---------|-------------|------|
| `0x0000…0001` | Runner Registry | Runner staking and capabilities |
| `0x0000…0002` | Job Dispatcher | Job lifecycle and VRF selection |
| `0x0000…0003` | Result Verifier | Result verification and callback |
| `0x0000…0009` | **Volume Registry** | Volume lifecycle, CapToken issuance, manifest anchoring |

### 2. Core Types

#### 2.1 VolumeId

```rust
/// A globally unique volume identifier.
/// Computed as: keccak256(owner_address || nonce_le8)
pub type VolumeId = [u8; 32];
```

#### 2.2 VolumeMode

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VolumeMode {
    /// Full read-write access.
    ReadWrite,
    /// Write-only access (runner can write but not read existing data).
    /// Useful for output collection without read access to prior state.
    WriteOnly,
    /// Read-only access (runner can read but not modify).
    ReadOnly,
}
```

#### 2.3 VolumeMetadata

Stored in the Volume Registry actor's storage under key `volume:{volume_id}`:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumeMetadata {
    pub volume_id: VolumeId,
    /// Owner address — the only party that can grant/revoke access and delete the volume.
    pub owner: Address,
    /// Default access mode for newly issued CapTokens (overridable per-grant).
    pub default_mode: VolumeMode,
    /// Block height when the volume was created.
    pub created_at: u64,
    /// Most recent manifest root anchored on-chain (32 bytes, algorithm-agnostic).
    /// `None` until the first VolumeAnchorManifest is submitted.
    pub manifest_root: Option<[u8; 32]>,
    /// Block height of the last manifest anchor.
    pub manifest_anchored_at: Option<u64>,
    /// Whether the volume has been marked as deleted (soft-delete before GC).
    pub deleted: bool,
}
```

Storage key pattern: `b"vol:" || volume_id` (36 bytes).

#### 2.4 CapToken

A CapToken is a short-lived bearer credential that grants a specific runner the right to mount a specific volume. It is signed by the volume owner using **secp256k1** (the same key type used for all external accounts, per whitepaper §1.1), enabling the Steamtrain storage layer to verify it without an on-chain round-trip.

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapToken {
    /// Unique token ID: keccak256(volume_id || grantee || expires_at_le8 || nonce_le8)
    pub token_id: [u8; 32],
    /// The volume this token grants access to.
    pub volume_id: VolumeId,
    /// The runner address authorized to use this token.
    /// MUST match the runner's registered address in the Runner Registry (0x01).
    pub grantee: Address,
    /// Access mode granted by this token.
    pub mode: VolumeMode,
    /// This token is invalid after this block height.
    /// MUST be > current block height at issuance. Recommended: current + 1000 blocks.
    pub expires_at_block: u64,
    /// Monotonically increasing per-(owner, volume) counter to prevent replay.
    pub nonce: u64,
    /// secp256k1 recoverable ECDSA signature over the canonical serialization of all
    /// fields above (commonware_codec binary encoding, field order as declared).
    /// The signing key MUST be the volume owner's key (recoverable address == owner).
    pub signature: [u8; 65],
}
```

**CapToken verification** (performed by Steamtrain, not on-chain):
1. Recover the signer address from `signature` over the canonical encoding of all non-signature fields.
2. Assert `recovered_address == volume_owner` (look up via the on-chain Volume Registry).
3. Assert `current_block <= expires_at_block` (fetch current block from node RPC).
4. Assert `grantee == presenting_runner_address`.
5. Assert the volume's `manifest_root` entry exists (volume is initialized).

CapToken storage key in Volume Registry: `b"cap:" || token_id` (36 bytes) — stored for revocation lookup.

#### 2.5 VolumeMount

Used in `JobSpec` to declare which volumes the job requires:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumeMount {
    /// The volume to mount.
    pub volume_id: VolumeId,
    /// The CapToken authorizing this runner to mount the volume.
    /// Issued by the job submitter (actor) via VolumeGrantAccess before job submission.
    pub cap_token: CapToken,
    /// Filesystem path where the volume is mounted inside the runner environment.
    /// MUST start with `/mnt/`. Example: `/mnt/steamtrain` or `/mnt/secrets`.
    pub mount_path: String,
}
```

### 3. JobSpec Extension

`JobSpec` (defined in `runner-common`) is extended with an optional volume mount list. The field uses `serde(default)` for full backward compatibility with existing serialized job specs.

```rust
pub struct JobSpec {
    // ... all existing fields unchanged ...

    /// Volumes to attach before job execution (CIP-9).
    /// Empty by default; backward-compatible.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub volume_mounts: Vec<VolumeMount>,
}
```

The Job Dispatcher (0x02) MUST validate:
- Each `CapToken.grantee` matches the selected runner's address.
- Each `CapToken.expires_at_block > submitted_at_block + timeout_blocks` (token must not expire before the job could complete).
- The corresponding volume exists and is not deleted in the Volume Registry.

### 4. System Instructions (40–49)

CIP-9 adds six new `SystemInstruction` variants dispatched to the Volume Registry (0x09). Instruction numbers 40–49 are reserved for volume operations.

```rust
pub enum SystemInstruction {
    // ... existing instructions 0–35 ...

    // ── CIP-9: Volume Instructions (40–49) ─────────────────────────────────

    /// Create a new volume.
    /// Caller becomes the volume owner.
    /// Emits: VolumeCreated { volume_id, owner }
    VolumeCreate {
        /// Desired access mode for the volume.
        default_mode: VolumeMode,
        /// Arbitrary caller-chosen bytes used in volume_id derivation. May be empty.
        salt: Vec<u8>,
    },                                                              // 40

    /// Issue a CapToken granting a runner access to a volume.
    /// Only the volume owner may call this.
    /// Emits: VolumeAccessGranted { volume_id, grantee, token_id, expires_at_block }
    VolumeGrantAccess {
        volume_id: VolumeId,
        /// Runner address to grant access to.
        grantee: Address,
        /// Access mode for this token (may differ from volume default_mode).
        mode: VolumeMode,
        /// How many blocks from submission_block this token is valid.
        /// MUST be in range [10, 10_000]. Default recommendation: 1000.
        duration_blocks: u64,
    },                                                              // 41

    /// Revoke a previously issued CapToken before it expires.
    /// Only the volume owner may call this.
    /// Emits: VolumeAccessRevoked { token_id }
    VolumeRevokeAccess {
        token_id: [u8; 32],
    },                                                              // 42

    /// Anchor a Steamtrain manifest root on-chain.
    /// Called by the runner after job completion (typically bundled with JobResultSubmit).
    /// The caller MUST hold a valid non-expired CapToken with ReadWrite or WriteOnly access.
    /// Emits: VolumeManifestAnchored { volume_id, manifest_root, anchored_by, height }
    VolumeAnchorManifest {
        volume_id: VolumeId,
        /// 32-byte content-addressed root of the Steamtrain volume Merkle tree.
        /// Algorithm-agnostic: stored as opaque bytes. Steamtrain uses BLAKE3 internally.
        manifest_root: [u8; 32],
        /// The CapToken authorizing this update (must have ReadWrite or WriteOnly mode).
        cap_token_id: [u8; 32],
    },                                                              // 43

    /// Delete a volume (soft-delete; storage GC is off-chain).
    /// Only the volume owner may call this.
    /// Emits: VolumeDeleted { volume_id }
    VolumeDelete {
        volume_id: VolumeId,
    },                                                              // 44

    /// Transfer volume ownership to a new address.
    /// Only the current owner may call this.
    /// Emits: VolumeOwnershipTransferred { volume_id, old_owner, new_owner }
    VolumeTransferOwnership {
        volume_id: VolumeId,
        new_owner: Address,
    },                                                              // 45

    // 46–49 reserved for future volume operations
}
```

### 5. Volume Lifecycle

```
Actor calls VolumeCreate
    │
    ▼
Volume Registry (0x09)
    ├── Derive volume_id = keccak256(caller || nonce_le8 || salt)
    ├── Store VolumeMetadata { owner=caller, manifest_root=None, ... }
    └── Emit VolumeCreated

Actor calls VolumeGrantAccess(volume_id, runner_addr, mode, duration)
    │
    ▼
Volume Registry
    ├── Assert caller == volume.owner
    ├── Derive token_id = keccak256(volume_id || grantee || expires_at_le8 || nonce_le8)
    ├── Sign CapToken with owner's on-chain signing key (secp256k1)
    ├── Store CapToken in registry (for revocation lookup)
    ├── Return CapToken bytes to caller
    └── Emit VolumeAccessGranted

Actor calls JobSubmit(job_spec with volume_mounts=[{ volume_id, cap_token, "/mnt/data" }])
    │
    ▼
Job Dispatcher (0x02)
    ├── Validate CapToken fields (grantee matches selected runner, not expired)
    ├── Include CapToken bytes in job assignment message to runner
    └── Proceed with VRF selection (CIP-2 §5)

Runner receives assigned job
    ├── Verify CapToken signature (off-chain, against Volume Registry data)
    ├── Call Steamtrain: mount_volume(cap_token, "/mnt/data")
    ├── Execute job handler (reads/writes to /mnt/data)
    └── Call Steamtrain: unmount_volume(volume_id) → returns manifest_root: [u8; 32]

Runner submits result
    ├── JobResultSubmit (CIP-2)
    └── VolumeAnchorManifest(volume_id, manifest_root, cap_token_id)  ← atomic or sequential
```

### 6. Steamtrain Client Interface

The Steamtrain storage engine is implemented as a **separate `steamtrain-client` crate** (independent library). CIP-9 defines the interface traits that it MUST implement. This decouples the runner runtime from the specific Steamtrain implementation and allows future alternative storage backends.

```rust
/// Implemented by the `steamtrain-client` crate.
/// Called by the runner before and after job execution.
#[async_trait]
pub trait VolumeProvider: Send + Sync {
    /// Mount a volume into the local filesystem at the specified path.
    /// Validates the CapToken off-chain before mounting.
    /// Returns the current manifest root (before writes).
    async fn mount_volume(
        &self,
        cap_token: &CapToken,
        mount_path: &str,
    ) -> Result<[u8; 32], StorageError>;

    /// Unmount a volume and flush all pending writes.
    /// Returns the new manifest root reflecting all writes since mount.
    async fn unmount_volume(
        &self,
        volume_id: &VolumeId,
    ) -> Result<[u8; 32], StorageError>;

    /// Verify a CapToken is valid without mounting (used for pre-job validation).
    async fn verify_cap_token(
        &self,
        cap_token: &CapToken,
        current_block: u64,
        volume_owner: &Address,
    ) -> Result<(), StorageError>;
}

/// Authorization hook — implemented by the runner to validate CapTokens.
/// Provided to the Steamtrain engine at initialization.
#[async_trait]
pub trait AuthProvider: Send + Sync {
    async fn validate(
        &self,
        token: &CapToken,
        presenting_runner: &Address,
        current_block: u64,
    ) -> Result<VolumeClaims, StorageError>;
}

/// Claims extracted from a validated CapToken.
pub struct VolumeClaims {
    pub volume_id: VolumeId,
    pub mode: VolumeMode,
    pub expires_at_block: u64,
}

/// Consensus hook — implemented by the node to anchor manifest roots.
/// Called by Steamtrain after a Two-Phase Commit consensus among storage nodes.
#[async_trait]
pub trait AuthoritativeStore: Send + Sync {
    /// Anchor a manifest root on-chain.
    /// Returns the transaction hash of the VolumeAnchorManifest instruction.
    async fn commit_manifest_root(
        &self,
        volume_id: &VolumeId,
        manifest_root: [u8; 32],
        cap_token_id: [u8; 32],
    ) -> Result<[u8; 32], StorageError>;  // returns tx_hash
}

/// Volume lifecycle hook — for managing metadata and GC.
#[async_trait]
pub trait ManifestRegistry: Send + Sync {
    async fn get_volume_metadata(&self, volume_id: &VolumeId) -> Result<VolumeMetadata, StorageError>;
    async fn prune_expired_tokens(&self, before_block: u64) -> Result<u64, StorageError>;
}

#[derive(Debug, thiserror::Error)]
pub enum StorageError {
    #[error("invalid CapToken: {reason}")]
    InvalidCapToken { reason: String },
    #[error("volume not found: {volume_id:?}")]
    VolumeNotFound { volume_id: VolumeId },
    #[error("mount failed: {reason}")]
    MountFailed { reason: String },
    #[error("permission denied: {reason}")]
    PermissionDenied { reason: String },
    #[error("network error: {0}")]
    Network(String),
}
```

**Repository structure:**

```
steamtrain-client/          ← new standalone crate (this CIP)
  src/
    lib.rs                  ← re-exports traits and types
    traits.rs               ← VolumeProvider, AuthProvider, AuthoritativeStore, ManifestRegistry
    types.rs                ← CapToken, VolumeMount, VolumeMode, StorageError (shared with runner-common)
    fuse.rs                 ← FUSE mount implementation backed by Steamtrain engine
    quic.rs                 ← QUIC transport to Steamtrain storage nodes
    crypto.rs               ← CapToken signature verification (secp256k1)
```

This crate is added as a dependency of the `runner` workspace only. The `node` crate does not depend on it.

### 7. Gas Costs

Gas costs are consensus-critical. All values are in Cycles and Cells per the CIP-3 dual-metered model.

| Instruction | Cycles | Cells | Notes |
|-------------|--------|-------|-------|
| `VolumeCreate` | 5,000 | 500 | Stores ~200 bytes of VolumeMetadata |
| `VolumeGrantAccess` | 3,000 | 150 | Stores CapToken + emits event |
| `VolumeRevokeAccess` | 1,000 | 50 | Marks token revoked |
| `VolumeAnchorManifest` | 1,000 | 32 | Stores 32-byte manifest root |
| `VolumeDelete` | 500 | 0 | Soft-delete flag only |
| `VolumeTransferOwnership` | 1,000 | 50 | Updates owner field |
| CapToken validation (per mount, pre-job) | 500 | 0 | Off-chain secp256k1 verify; no on-chain cost |

**Off-chain storage pricing** is not gas-metered. Steamtrain operators publish pricing (CBY per byte per period) off-chain, analogous to runner rate cards. Actors prepay storage via escrow at volume creation time. This model is consistent with §17.7 of the whitepaper (runner marketplace off-chain pricing).

### 8. Entitlement Integration

CIP-9 extends the Entitlement system (CIP-2 §7) with a new `Scope` and `Action` variant to enable on-chain governance of volume access policies:

```rust
// Additions to cowboy_types::entitlement

pub enum Scope {
    // ... existing variants ...
    /// Scope limited to a specific storage volume.
    Volume(VolumeId),
}

pub enum Action {
    // ... existing variants ...
    /// Read access to a volume.
    VolumeRead(VolumeId),
    /// Write access to a volume.
    VolumeWrite(VolumeId),
    /// Full read-write access to a volume.
    VolumeReadWrite(VolumeId),
}
```

This allows volume access to be governed via the Entitlement Registry (0x07) for enterprise or compliance use cases, in addition to the direct CapToken flow. When a job's `required_runner_pool` is set (CIP-2 §7.3), the job dispatcher MAY additionally verify that the selected runner holds the relevant volume Entitlement.

### 9. Backwards Compatibility

- `JobSpec.volume_mounts` uses `#[serde(default)]` — all existing job specs remain valid with an empty mounts list.
- New instructions 40–49 do not conflict with any existing instruction numbers.
- The Volume Registry system actor at `0x09` is a new address; no existing actor uses it.
- Runners without the `steamtrain-client` dependency can safely ignore `volume_mounts` (they will fail at mount time if volumes are attached to their jobs — the failure is reported as a job fault, not a consensus failure).

### 10. Security Considerations

**CapToken forgery.** CapTokens are secp256k1-signed by the volume owner. A forged token requires breaking ECDSA over secp256k1, which is infeasible given the security assumption already relied upon by all external accounts (whitepaper §1.1).

**Replay attacks.** The `nonce` field in CapTokens is monotonically increasing per `(owner, volume)`. The Volume Registry tracks the last issued nonce; replay of old tokens is detected and rejected.

**Token expiry manipulation.** A runner cannot extend a CapToken's expiry — the `expires_at_block` is fixed at issuance and covered by the owner's signature. The Job Dispatcher validates expiry at submission time.

**Manifest root spoofing.** Only the holder of a valid CapToken with ReadWrite or WriteOnly mode can submit a `VolumeAnchorManifest`. The Volume Registry verifies the CapToken ID is in its store and has not been revoked.

**Storage availability.** Steamtrain's erasure coding (K data + M parity shards, Reed-Solomon) ensures that the volume remains accessible even if up to M storage nodes fail simultaneously. This is an off-chain durability guarantee; the on-chain protocol does not verify shard availability.

**Client-side encryption guarantee.** Data is encrypted with AES-256-GCM before leaving the runner. Storage nodes never receive plaintext. Encryption keys are ephemeral and managed by the `steamtrain-client` crate. Loss of the encryption key means permanent data loss — actors are responsible for key management.

**DoS via volume spam.** `VolumeCreate` costs 5,000 Cycles + 500 Cells, making bulk volume creation economically deterred. A per-actor volume limit of **256** active volumes (governance-tunable) prevents storage inflation in the Volume Registry actor's state.

---

## Rationale

**Why a separate `steamtrain-client` crate?** The Steamtrain engine is an independent subsystem with its own release cycle, storage node network, and operational requirements. Coupling it into the runner binary creates an untenable dependency footprint. A trait-based interface (analogous to how the runner interfaces with the node via RPC) allows the runner to remain storage-backend-agnostic.

**Why CapTokens rather than on-chain Entitlements directly?** On-chain Entitlement checks require a chain round-trip at the time of volume mount (job execution time). CapTokens are pre-issued before job submission, carried in the `JobSpec`, and verified off-chain by Steamtrain — adding zero latency to the critical path. On-chain Entitlements remain as the governance layer for standing access policies.

**Why anchor manifest roots on-chain?** Without on-chain anchoring, there is no globally consistent, tamper-evident record of what data a volume contains. Any party can independently verify the integrity of a volume by fetching the manifest root from chain and comparing it against the Steamtrain content hash — the same trust model as blob multihash references (whitepaper §7.2).

**Why `VolumeAnchorManifest` separate from `JobResultSubmit`?** A job may mount multiple volumes and write to only some of them. Anchoring is per-volume and only required when a write-capable token was used. Keeping it separate preserves composability and avoids modifying the existing `JobResultSubmit` instruction. Runners SHOULD submit both in the same transaction to keep the result and storage state atomic.

---

## Parameters (Genesis Defaults)

| Parameter | Value | Governance-tunable |
|-----------|-------|-------------------|
| `max_volumes_per_actor` | 256 | Yes |
| `cap_token_min_duration_blocks` | 10 | Yes |
| `cap_token_max_duration_blocks` | 10,000 | Yes |
| `cap_token_recommended_duration_blocks` | 1,000 | No |
| `volume_registry_actor` | `0x0000…0009` | No |
| `max_cap_tokens_per_volume` | 64 | Yes |
| `manifest_root_bytes` | 32 | No |
