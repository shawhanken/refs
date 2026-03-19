---
title: "CIP-10: Container Runtime"
description: Protocol definition for executing OCI-compliant container images as verifiable off-chain compute jobs
icon: container
---

<Note>
  **Status:** Draft for Internal Review
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-03-18
  **Depends on:** CIP-2 (off-chain compute), CIP-3 (fee model), CIP-9 (runner attachable storage)
</Note>

<Tip>
  CIP-10 extends CIP-2 with a native container execution mode. Runners execute OCI-compliant images in Linux namespace sandboxes. CIP-9 volumes provide persistent filesystem state across container restarts. The Container Image Registry (system actor `0x0A`) manages the on-chain authorization of permitted images.
</Tip>

# CIP-10: Container Runtime

---

## Abstract

This CIP specifies a container execution mode for the Cowboy off-chain compute system (CIP-2). While the existing job types (`Llm`, `Http`, `Mcp`, `Custom`) cover well-scoped request-response workloads, a large class of compute tasks — ML pipeline stages, data transformation jobs, multi-binary workflows, stateful microservices — require native execution environments with full OS-level isolation. The container model, based on the OCI (Open Container Initiative) image specification, provides exactly this: reproducible, content-addressed execution units with well-understood resource isolation semantics.

CIP-10 introduces:

- The `Container` `JobType` variant and the `ContainerSpec` struct for describing container job parameters.
- The **Container Image Registry** (system actor `0x0000…000A`), which maintains an on-chain allowlist of verified image hashes, preventing execution of arbitrary or tampered images.
- A runner-side lifecycle protocol for pulling, verifying, sandboxing, and executing container images, with full integration of CIP-9 volume mounts.
- A `RateCard` extension for runners to advertise container execution capability.

---

## Motivation

The four use cases motivating this design are:

1. **Native Toolchain Execution.** Many data processing workloads require compiled binaries (ffmpeg, ImageMagick, custom CLI tools) that cannot be expressed as Python actors or HTTP calls. Packaging them as OCI images provides a universal distribution mechanism.

2. **Reproducible ML Inference.** Inference runtimes (vLLM, Triton, ONNX Runtime) ship as container images with known digests. Pinning `image_hash` in a `ContainerSpec` makes the execution environment part of the protocol-level job specification, verifiable by all parties.

3. **Multi-Runner Pipelines.** Tool pipelines (e.g., OpenClaw) chain runners sequentially. CIP-9 volumes carry intermediate data between stages. Container images can implement pipeline stages with arbitrary languages and dependencies, decoupled from the runner's own runtime.

4. **Stateful Services.** Long-running processes (database servers, caching layers) require both persistent storage (CIP-9) and process-level isolation. Container runtimes provide the isolation; this CIP provides the protocol binding.

---

## Specification

### 1. System Actor: Container Image Registry (`0x0000…000A`)

The Container Image Registry is a system actor at address `0x000000000000000000000000000000000000000A`. It maintains an on-chain allowlist of authorized container image hashes. A runner MUST NOT execute an image whose hash is not present in the registry (unless the image was submitted by the job owner with an explicit `allow_unregistered: true` flag, which requires a TEE attestation per §9.3).

| Address | System Actor | Role |
|---------|-------------|------|
| `0x0000…0001` | Runner Registry | Runner staking and capabilities |
| `0x0000…0002` | Job Dispatcher | Job lifecycle and VRF selection |
| `0x0000…0009` | Volume Registry | Volume lifecycle, CapToken issuance, manifest anchoring |
| `0x0000…000A` | **Container Image Registry** | Image hash allowlist, policy management |

#### 1.1 ImageEntry

Stored under key `b"img:" || image_hash` (36 bytes):

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageEntry {
    /// 32-byte content hash of the OCI image manifest.
    pub image_hash: [u8; 32],
    /// Hash algorithm used to produce `image_hash`.
    pub hash_algo: ImageHashAlgo,
    /// Human-readable name/version tag. Not used for verification — informational only.
    pub label: String,
    /// Block height when this entry was registered.
    pub registered_at: u64,
    /// Address that registered this image.
    pub registrant: Address,
    /// Whether this image is currently permitted for execution.
    pub active: bool,
    /// Optional policy governing which runners may execute this image.
    pub policy: Option<ImagePolicy>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ImageHashAlgo {
    /// SHA-256 (standard OCI/Docker default)
    Sha256,
    /// BLAKE3 (used in Steamtrain and Cowboy storage primitives)
    Blake3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ImagePolicy {
    /// Any registered runner may execute this image.
    AnyRunner,
    /// Only runners with a valid TEE attestation may execute this image.
    TeeRequired,
    /// Only runners listed in the specified Entitlement pool may execute this image.
    EntitlementPool { pool_id: [u8; 32] },
}
```

### 2. Core Types

#### 2.1 ContainerSpec

The full specification of a container job. Carried inside `JobType::Container`.

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerSpec {
    /// OCI image content hash.
    /// MUST match a registered, active `ImageEntry` in the Container Image Registry (0x0A),
    /// unless `allow_unregistered` is true (requires TEE attestation, §9.3).
    pub image_hash: [u8; 32],
    /// Hash algorithm for `image_hash`.
    #[serde(default)]
    pub image_hash_algo: ImageHashAlgo,
    /// Optional OCI image reference for pull purposes (e.g. "docker.io/library/python:3.12").
    /// Runners use this as a hint to locate the image; the hash is the authoritative identity.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub image_ref: Option<String>,
    /// Override the image's default ENTRYPOINT.
    /// If empty, the image's declared entrypoint is used.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub entrypoint: Vec<String>,
    /// Arguments passed to the entrypoint.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub args: Vec<String>,
    /// Additional environment variables as (KEY, value) pairs.
    /// These are merged with (and may override) the image's default ENV declarations.
    /// MUST NOT include secrets — use CIP-9 volumes mounted at well-known paths instead.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub env: Vec<(String, String)>,
    /// Resource limits enforced by the runner via cgroup v2.
    pub limits: ContainerLimits,
    /// Working directory inside the container.
    /// Defaults to the image's declared WORKDIR, or `/` if not set.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub working_dir: Option<String>,
    /// If true, allow execution of images not registered in the Container Image Registry.
    /// Requires TEE attestation from the runner (see §9.3). Default: false.
    #[serde(default)]
    pub allow_unregistered: bool,
}

impl Default for ImageHashAlgo {
    fn default() -> Self {
        ImageHashAlgo::Sha256
    }
}
```

#### 2.2 ContainerLimits

Resource limits enforced by the runner via cgroup v2 + Linux namespaces. These are negotiated against the runner's `RateCard` (see §6).

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerLimits {
    /// Maximum resident memory in bytes.
    /// Enforced via cgroup v2 `memory.max`. Default: 512 MiB.
    #[serde(default = "ContainerLimits::default_memory")]
    pub memory_bytes: u64,
    /// CPU allocation in millicores (1000 = 1 physical core).
    /// Enforced via cgroup v2 `cpu.max` (quota/period). Default: 1000.
    #[serde(default = "ContainerLimits::default_cpu")]
    pub cpu_millicores: u32,
    /// Maximum wall-clock execution time in seconds.
    /// Container is SIGKILL'd after this deadline. Default: 60.
    /// MUST be ≤ the job's `ResourceBounds.max_wall_time_seconds`.
    #[serde(default = "ContainerLimits::default_timeout")]
    pub timeout_secs: u32,
    /// Maximum ephemeral layer disk usage in bytes (writes to the container filesystem).
    /// Does NOT include CIP-9 volume mounts (those have their own quotas).
    /// Enforced via overlayfs quota or dm-thin. Default: 1 GiB.
    #[serde(default = "ContainerLimits::default_disk")]
    pub disk_bytes: u64,
    /// Maximum number of PIDs inside the container.
    /// Enforced via cgroup v2 `pids.max`. Default: 512.
    #[serde(default = "ContainerLimits::default_pids")]
    pub pids_max: u32,
}

impl ContainerLimits {
    fn default_memory() -> u64 { 512 * 1024 * 1024 }     // 512 MiB
    fn default_cpu() -> u32 { 1000 }                       // 1 core
    fn default_timeout() -> u32 { 60 }                     // 60 seconds
    fn default_disk() -> u64 { 1024 * 1024 * 1024 }       // 1 GiB
    fn default_pids() -> u32 { 512 }
}
```

### 3. JobType Extension

`JobType` (defined in `runner-common`) gains a new `Container` variant:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum JobType {
    // ... existing variants (Llm, Http, Mcp, Custom) unchanged ...

    /// Execute an OCI container image (CIP-10).
    Container {
        /// Full container execution specification.
        spec: ContainerSpec,
    },
}
```

The `#[serde(tag = "type")]` discriminant for this variant is `"Container"`, consistent with the existing Rust enum serde convention.

### 4. JobSpec Extension

`JobSpec` already carries `volume_mounts: Vec<VolumeMount>` (CIP-9). No structural changes to `JobSpec` are needed for CIP-10 — the container spec is embedded inside `JobType::Container`. However, the following validation rules are added for container jobs:

**Job Dispatcher (0x02) MUST:**
1. Verify `spec.image_hash` exists in the Container Image Registry (0x0A) as an active entry, OR `spec.allow_unregistered == true` with a valid TEE attestation in the job metadata.
2. Verify the selected runner's `RateCard.supported_job_types` includes `"Container"`.
3. Verify `spec.limits.timeout_secs ≤ job.bounds.max_wall_time_seconds`.
4. Apply all CIP-9 `VolumeMount` validations (CapToken grantee, expiry, volume existence).

**Runner MUST:**
1. Verify image hash post-pull (§5.3) before executing.
2. Enforce all `ContainerLimits` via cgroup v2.
3. Mount CIP-9 volumes into the container namespace at their declared `mount_path`.

### 5. Runner Container Lifecycle

The runner executes the following sequence for a `Container` job. Each step is mandatory; failure at any step results in a `JobFault` (CIP-2 §6.4) rather than a `JobResult`.

```
 1. RECEIVE job assignment (CIP-2 §5)
    │
 2. VALIDATE container spec
    │  ├── Check image_hash in Container Image Registry (0x0A) via node RPC
    │  ├── Check runner's own capability (OCI runtime present?)
    │  └── Validate ContainerLimits against runner's RateCard
    │
 3. PULL image
    │  ├── Check local image cache (keyed by image_hash)
    │  ├── If not cached: fetch from image_ref (OCI registry) or peer runners
    │  └── Verify pulled manifest hash == spec.image_hash (ABORT if mismatch)
    │
 4. MOUNT CIP-9 VOLUMES (for each VolumeMount in job_spec.volume_mounts)
    │  ├── Verify CapToken signature off-chain (VolumeProvider::verify_cap_token)
    │  └── steamtrain_client.mount_volume(cap_token, mount_path)
    │
 5. PREPARE SANDBOX
    │  ├── Create Linux namespaces: user, mount, pid, uts, ipc
    │  │   (network namespace: isolated by default — no internet access unless
    │  │    the runner has a Network Entitlement for this job, CIP-2 §7)
    │  ├── Set up overlayfs: lower=image_layers, upper=ephemeral_rw_layer
    │  ├── Bind-mount CIP-9 volume FUSE mountpoints into container mount namespace
    │  ├── Apply cgroup v2 limits (memory, cpu, pids, io)
    │  └── Set UID/GID map (user namespace: container root → unprivileged host UID)
    │
 6. EXECUTE
    │  ├── Start container process: entrypoint + args, env, working_dir
    │  ├── Capture stdout/stderr (pipe, up to 1 MiB each)
    │  └── Wait for: process exit OR timeout_secs deadline (SIGKILL on timeout)
    │
 7. COLLECT OUTPUT
    │  ├── exit_code: u32
    │  ├── stdout: Vec<u8> (truncated to 1 MiB)
    │  └── stderr: Vec<u8> (truncated to 64 KiB, for diagnostics only)
    │
 8. UNMOUNT CIP-9 VOLUMES (for each mounted volume)
    │  └── steamtrain_client.unmount_volume(volume_id) → manifest_root: [u8; 32]
    │
 9. SUBMIT RESULTS (in a single transaction where possible)
    │  ├── JobResultSubmit (CIP-2 §6.3): { exit_code, stdout, stderr_hash }
    │  └── VolumeAnchorManifest (CIP-9 §4, instruction 43): one per written volume
```

#### 5.1 Output Encoding

Container job results are encoded as `ContainerOutput`:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerOutput {
    /// Process exit code. 0 = success. Non-zero = application-level failure.
    pub exit_code: i32,
    /// Captured stdout, up to 1 MiB. UTF-8 encouraged but not required.
    pub stdout: Vec<u8>,
    /// BLAKE3 hash of the full stderr stream (stored off-chain if requested).
    pub stderr_hash: [u8; 32],
    /// Wall-clock execution duration in milliseconds.
    pub duration_ms: u64,
    /// Peak resident memory usage in bytes.
    pub peak_memory_bytes: u64,
}
```

The `stdout` payload is used as the canonical job output for verification purposes (CIP-2 §6.2). A non-zero `exit_code` is treated as a job failure by the Result Verifier (0x03) unless the actor's callback explicitly handles it.

#### 5.2 Image Cache Management

Runners maintain a local OCI layer cache. The cache is keyed by `(image_hash, hash_algo)`. Cached layers are shared across jobs. LRU eviction applies when the cache exceeds the runner's configured limit (not protocol-specified; runner-local configuration). The runner MUST NOT evict a layer that is currently in use by an executing container.

#### 5.3 Hash Verification

After pulling an image, the runner recomputes the hash of the OCI image manifest JSON and compares it against `spec.image_hash`. The algorithm to use is `spec.image_hash_algo`:

- **Sha256**: `sha256(manifest_json_bytes)` — compatible with `docker pull`/`skopeo` standard `sha256:` digest.
- **Blake3**: `blake3(manifest_json_bytes)` — faster and consistent with Steamtrain's internal hashing.

If the computed hash does not match `spec.image_hash`, the runner MUST NOT start the container and MUST report a `JobFault` with `reason: ImageHashMismatch`.

### 6. RateCard Extension

`RateCard` (defined in `runner/types.rs`, extended in CIP-2 C-1) gains fields for container capability advertisement:

```rust
pub struct RateCard {
    // ... all existing fields ...

    /// Whether this runner supports CIP-10 container job execution.
    /// Default: false (runners opt in explicitly).
    #[serde(default)]
    pub supports_containers: bool,

    /// Maximum ContainerLimits this runner will accept.
    /// Jobs with limits exceeding these values are rejected at dispatch time.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub container_limits: Option<ContainerCapacity>,

    /// OCI image pull sources this runner supports.
    /// Runners may restrict to trusted registries or peer-pull only.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub allowed_image_registries: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerCapacity {
    pub max_memory_bytes: u64,
    pub max_cpu_millicores: u32,
    pub max_timeout_secs: u32,
    pub max_disk_bytes: u64,
    pub max_volume_mounts: u32,
}
```

### 7. System Instructions (50–54)

CIP-10 adds five new `SystemInstruction` variants dispatched to the Container Image Registry (0x0A). Instruction numbers 50–54 are reserved for container image management.

```rust
pub enum SystemInstruction {
    // ... existing instructions 0–49 ...

    // ── CIP-10: Container Image Instructions (50–54) ────────────────────────

    /// Register a container image hash in the allowlist.
    /// The caller becomes the `registrant` and may revoke or update the entry.
    /// Emits: ContainerImageRegistered { image_hash, registrant, label }
    ContainerImageRegister {
        /// 32-byte content hash of the OCI image manifest.
        image_hash: [u8; 32],
        /// Hash algorithm used.
        hash_algo: ImageHashAlgo,
        /// Human-readable label (name + version tag). Max 128 bytes.
        label: String,
        /// Optional execution policy. Default: AnyRunner.
        policy: Option<ImagePolicy>,
    },                                                          // 50

    /// Deactivate a registered image (prevents new jobs from using it).
    /// Only the original `registrant` OR a governance actor may call this.
    /// Existing running jobs are NOT affected.
    /// Emits: ContainerImageRevoked { image_hash, revoked_by }
    ContainerImageRevoke {
        image_hash: [u8; 32],
    },                                                          // 51

    /// Update the execution policy for a registered image.
    /// Only the original `registrant` may call this.
    /// Emits: ContainerImagePolicyUpdated { image_hash, new_policy }
    ContainerImageSetPolicy {
        image_hash: [u8; 32],
        policy: ImagePolicy,
    },                                                          // 52

    /// Re-activate a previously revoked image.
    /// Only the original `registrant` may call this.
    /// Emits: ContainerImageReactivated { image_hash }
    ContainerImageReactivate {
        image_hash: [u8; 32],
    },                                                          // 53

    // 54 reserved for future container image operations
}
```

### 8. Networking Model

By default, container jobs execute in an **isolated network namespace** with no internet access. This is consistent with the determinism and isolation requirements of CIP-2: runner outputs must be reproducible and not depend on external state that other parties cannot verify.

Internet access for container jobs follows the **Entitlement model** (CIP-2 §7):

```rust
// Extension to CIP-2 entitlement types
pub enum Action {
    // ... existing ...
    /// Allow container jobs submitted by actor_address to reach internet endpoints.
    ContainerNetworkEgress { allowed_hosts: Vec<String> },
}
```

When a container job holds a valid `ContainerNetworkEgress` Entitlement, the runner creates a network namespace with a NAT-gateway connection to the allowed hosts (via iptables egress filtering). The job operator is responsible for ensuring determinism of any network-sourced data (e.g., by using CIP-9 volumes as a write-through cache anchored on-chain before verification).

### 9. Security Considerations

#### 9.1 Image Hash Pinning

The `image_hash` in `ContainerSpec` is the authoritative identity of the image. Runners verify the hash after pull and before execution. A mismatch causes an unconditional `JobFault`. This prevents supply chain attacks where a registry is compromised but the image digest in the job spec remains unchanged.

#### 9.2 Namespace Isolation

All container jobs execute in isolated Linux namespaces:

| Namespace | Purpose |
|-----------|---------|
| `user` | Map container root to unprivileged host UID (no privilege escalation) |
| `mount` | Isolated filesystem view; host filesystem not visible |
| `pid` | Isolated PID space; host processes not visible |
| `uts` | Isolated hostname (prevents hostname-based fingerprinting) |
| `ipc` | Isolated System V IPC and POSIX message queues |
| `net` | Isolated network (no internet by default; see §8) |

**`cgroup` v2** enforces `memory.max`, `cpu.max`, `pids.max`, and `io.max`. The runner MUST use cgroup v2; runners on kernels without cgroup v2 support MUST NOT advertise `supports_containers: true`.

#### 9.3 Unregistered Image Execution

`allow_unregistered: true` permits execution of images not in the Container Image Registry. This is intended for development workflows and trusted TEE environments only. Requirements:

1. The job MUST include a `tee_attestation` field in its metadata (per CIP-2 TEE attestation protocol, §5.5).
2. The runner MUST be registered with `TeeCapability` in the Runner Registry (0x01).
3. The TEE Verifier (0x05) MUST validate the attestation before the job is dispatched.

This mechanism allows TEE-protected runners to execute proprietary images without publishing their hash, while still providing cryptographic proof of execution integrity.

#### 9.4 Volume Mount Isolation

CIP-9 volumes are mounted into the container via FUSE bind-mounts inside the container's mount namespace. The runner's host filesystem is never accessible from inside the container. Volume `WriteOnly` mounts are enforced at the FUSE layer: read operations return `EPERM`.

#### 9.5 Ephemeral Layer Cleanup

After job completion (regardless of exit code), the runner destroys the ephemeral overlayfs upper layer. Sensitive data written to the container filesystem (not to a CIP-9 volume) is lost. Actors that need persistence MUST use CIP-9 volumes.

#### 9.6 Environment Variable Secrets

Environment variables are carried in the `JobSpec`, which is distributed to the assigned runner via the CIP-2 job assignment protocol. They are **not secret** — they are visible to the runner and to anyone with access to the job spec. Sensitive configuration (API keys, credentials) MUST be stored in CIP-9 volumes, not in `ContainerSpec.env`.

---

## Rationale

**Why OCI images rather than a custom image format?** OCI is the industry standard with a rich ecosystem (Docker, Podman, BuildKit, containerd). Reusing it avoids reinventing distribution, layering, and tooling. Content-addressed digests map naturally to the protocol's hash-pinned identity model.

**Why a Container Image Registry on-chain?** Without an on-chain allowlist, any job operator could submit arbitrary image hashes and runners would execute them without protocol-level oversight. The registry provides a governance layer: operators register known-good images, governance actors can revoke compromised ones, and the policy system supports enterprise isolation requirements (TEE, entitlement pools).

**Why not use the Secrets Manager (0x04) for image credentials?** The Secrets Manager is intentionally isolated from off-chain runners (it operates within the PVM). Container image registry credentials are operational runner configuration, not protocol-level secrets. Runners configure their own OCI registry auth (docker login credentials, etc.) out-of-band.

**Why separate `ContainerLimits` from `ResourceBounds`?** `ResourceBounds` is a CIP-2 concept centered on token budget (`max_input_tokens`, `max_output_tokens`) relevant to LLM jobs. Container jobs have entirely different resource axes (memory, CPU, disk, pids). Reusing `ResourceBounds` would require adding CPU/disk fields that are meaningless for non-container jobs. Separate structs keep both clean.

**Why network isolation by default?** Non-determinism is the primary threat to the CIP-2 verification model. A container that fetches external data will produce different outputs on different runners, causing verification failures. Opt-in networking via Entitlements forces the job operator to explicitly acknowledge this risk and take responsibility for ensuring determinism of network-sourced data.

---

## Backwards Compatibility

- The new `JobType::Container` variant uses `#[serde(tag = "type")]` with discriminant `"Container"`. Existing deserializers that use `#[serde(other)]` or ignore unknown variants will skip it gracefully.
- Runners without container support (`supports_containers: false`) will never be assigned `Container` jobs by the Job Dispatcher — the dispatch logic already filters by RateCard capabilities.
- Instruction numbers 50–54 do not conflict with any existing instruction numbers (0–49).
- The Container Image Registry at `0x0A` is a new address with no conflicts.

---

## Gas Costs

All values are in Cycles and Cells per the CIP-3 dual-metered model.

| Instruction | Cycles | Cells | Notes |
|-------------|--------|-------|-------|
| `ContainerImageRegister` | 10,000 | 200 | Stores `ImageEntry` + label |
| `ContainerImageRevoke` | 1,000 | 0 | Flips `active` flag |
| `ContainerImageSetPolicy` | 2,000 | 100 | Overwrites policy field |
| `ContainerImageReactivate` | 1,000 | 0 | Flips `active` flag |
| Job Dispatch (Container) | Same as base CIP-2 | + `ContainerSpec` bytes as Cells | `ContainerSpec` counted toward job submission cell cost |

**Container execution cost** is priced off-chain via the runner's RateCard, consistent with the CIP-2 marketplace model (§4). Runners may price container jobs higher than LLM/HTTP jobs to reflect infrastructure costs (image cache storage, OCI runtime overhead, cgroup management).

---

## Parameters (Genesis Defaults)

| Parameter | Value | Governance-tunable |
|-----------|-------|-------------------|
| `container_image_registry_actor` | `0x0000…000A` | No |
| `max_image_label_bytes` | 128 | Yes |
| `max_container_stdout_bytes` | 1,048,576 (1 MiB) | Yes |
| `max_container_stderr_bytes` | 65,536 (64 KiB) | Yes |
| `default_container_memory_bytes` | 536,870,912 (512 MiB) | Yes |
| `default_container_cpu_millicores` | 1,000 | Yes |
| `default_container_timeout_secs` | 60 | Yes |
| `default_container_disk_bytes` | 1,073,741,824 (1 GiB) | Yes |
| `default_container_pids_max` | 512 | Yes |
| `max_container_volume_mounts` | 8 | Yes |
