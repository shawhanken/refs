---
title: "CIP-2: Verifiable Off-Chain Compute (v2)"
description: Code-aligned v2 — adds DNS verification primitives required by CIP-16 v2 and clarifies the Custom executor extension pattern
---

# CIP-2 v2

> **Versioning.** This is v2 of CIP-2. v1 is the canonical document `cip-2-offchain-compute.md` (preserved verbatim as Part I). v2 = v1 + the alignment revision (Part II).
>
> **Conflict rule:** Part II is canonical wherever it contradicts Part I.
>
> **Summary of v2 changes**
>
> - Adds two `VerifierCheck` variants — `DnsTxtRecordMatch` and `DnsCnameMatch` — required by CIP-16 v2 for DNS-based external-domain verification.
> - Documents `JobType::Custom { executor_hash, params }` as the established mechanism for new built-in verifier executors without expanding `JobType` discriminants.
> - Notes `VerificationMode::MajorityVote` (already implemented) as the structurally correct mode for non-deterministic operations like DNS resolution.
> - Carries forward the existing 2026-04-15 amendment block on system actor table, runner stake formula, and `VerificationMode` discriminants — no further change to those items.

---

## Part I — v1 Specification (verbatim from `cip-2-offchain-compute.md`)


<Note>
  **Status:** Draft for Internal Review  
  **Type:** Standards Track  
  **Category:** Core  
  **Created:** 2025-10-02  
  **Revised:** 2026-03-09
</Note>

<Tip>
  This specification defines the verifiable, asynchronous off‑chain compute framework. Revision 2026-03-05 replaces the ring-buffer VRF selection with Fisher-Yates VRF + stake-weighted sortition, removes the `skip_task` mechanism in favor of timeout-based re-selection, and introduces the commit-reveal aggregator model for result verification. Revision 2026-03-09 expands §7 to reflect the implemented Entitlement type system (Scope / Action / Constraints / Role), updates the system actor table to include Secrets Manager (`0x04`) and TEE Verifier (`0x05`), and clarifies the Pool membership grant flow.
</Tip>

<Warning>
  **修正案（2026-04-15）**: 以下条目以代码为准，本 CIP 文中相应表述以修正案为准。
  - **System Actor 地址表**：`0x01-0x0B` 共 11 个槽位（包含 ENTITLEMENT_REGISTRY `0x07`、TREASURY `0x08`、GOVERNANCE `0x09`、STORAGE_MANAGER `0x0A`、RELAY_REGISTRY `0x0B`）
  - **Runner 质押公式**：`stake >= max(10,000 CBY, 1.5 × declared_max_job_value)`（非 10× average_job_value）
  - **VerificationMode**：6 variants — None / EconomicBond / MajorityVote / StructuredMatch / Deterministic / SemanticSimilarity（ZK-Proof 未实现）

  详见 [`analysis/2026-04-15_documentation_amendments.md`](../analysis/2026-04-15_documentation_amendments.md) 条目 B / C / D。
</Warning>

# CIP-2: Verifiable Asynchronous Off-chain Computation Framework

---

### **Abstract**

This proposal introduces a framework for executing verifiable, off-chain computations within the Cowboy ecosystem. It defines a standardized, asynchronous protocol for smart contracts to request external data fetching, complex computations, or AI model inferences from a decentralized network of off-chain "Runners." The architecture is built on a deterministic, stake-weighted VRF selection mechanism using Fisher-Yates shuffle, ensuring verifiable task assignment that is resistant to correlation attacks and Sybil manipulation. The core design philosophy emphasizes user-centric verification, task clarity through mandatory result schemas, and on-chain stability via a deferred transaction model for callbacks (per CIP-1).

---

### **Motivation**

To unlock advanced use cases involving AI/ML, large datasets, or Web2 APIs, smart contracts need a secure and reliable bridge to the off-chain world. This CIP proposes a flexible and unopinionated approach, tailored for Cowboy's on-chain Python environment, that addresses the limitations of existing oracle solutions.

This framework empowers developers to:

1. **Integrate Complex Logic:** Run Python-based AI model inferences or heavy computations off-chain.  
2. **Preserve On-chain Stability:** Utilize an asynchronous, deferred transaction model to prevent network congestion from off-chain interactions.  
3. **Achieve Verifiable Decentralization:** Leverage a stake-weighted VRF-based system to eliminate centralized schedulers and allow anyone to verify task assignments.  
4. **Enforce Clarity:** Mandate task and result schemas to reduce ambiguity and ensure Runners can reliably execute and be verified.  
5. **Choose Their Trust Model:** Allow developers to select the number of Runners, the verification mode, and optional Runner pool constraints for their specific application's security needs.

---

### **Specification**

The framework consists of seven on-chain System Actor components and the off-chain Runner network:

| Address | System Actor | Role |
|---------|-------------|------|
| `0x0000…0001` | **Runner Registry** | Runner registration, staking, capabilities, health, reputation |
| `0x0000…0002` | **Job Dispatcher** | Job submission, VRF selection, job lifecycle management |
| `0x0000…0003` | **Result Verifier** | Commit-reveal aggregation, result verification, callback dispatch |
| `0x0000…0004` | **Secrets Manager** | Encrypted secret storage and TEE-gated secret release |
| `0x0000…0005` | **TEE Verifier** | Remote attestation verification for TEE-based runners |
| `0x0000…0007` | **Entitlement Registry** | Permission management: Runner Pool access control and general RBAC (see §7) |
| — | **Off-chain Runners** | External nodes that execute tasks and submit results |

> **Address gap note:** `0x0006` is reserved for future use.

#### **1. Task Definition and Result Schema**

Every off-chain task submission **must** include a `result_schema`. This mandatory payload defines the explicit output constraints of the task, enabling objective validation by the protocol.

The schema defines at minimum:

* `max_return_bytes`: Maximum result size to prevent gas-bombing attacks.  
* `expected_execution_ms`: Target execution time to help Runners assess feasibility.  
* `data_format`: Expected data structure (e.g., JSON schema, binary format).

#### **2. Job Specification**

Every job submitted to the Dispatcher carries a `JobSpec`:

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | H256 | Unique job identifier |
| `job_type` | JobType | `Llm`, `Http`, `Mcp`, or `Custom` |
| `bounds` | ResourceBounds | Resource limits for execution |
| `verification` | VerificationConfig | Verification mode and parameters |
| `max_price` | U256 | Maximum price (CBY wei) |
| `tip` | U256 | Priority tip |
| `timeout_blocks` | u64 | Timeout in blocks |
| `callback` | CallbackInfo | Callback Actor and handler |
| `submitter` | Address | Submitting Actor's address |
| `submitted_at` | u64 | Submission block height |
| `required_runner_pool` | `Option<Vec<u8>>` | Optional: Pool ID bytes; only Runners holding a `RunnerJoinPool(pool_id)` Entitlement may be selected (§7) |

#### **3. Core Workflow (Asynchronous & Deferred)**

```
Actor calls submit_job(job_spec)
    │  → Job Dispatcher (0x0000...0002)
    │
    ▼
1. Validate JobSpec (bounds ≠ 0, max_price > 0, timeout > 0)
2. Record submission_block → fixes the candidate snapshot
3. Generate VRF seed: seed = Keccak256(block_hash || "cowboy-runner-select-v2:" || job_id || submitted_at_le8)
4. Build candidate list (see §4)
5. Run Fisher-Yates VRF selection (see §5) → assign M runners
6. Store job → JobStatus::Assigned

Runner polls get_assigned_jobs(runner_addr)
    │
    ├── Execute → submit commitment → Aggregator collects → submit_result
    └── Do not execute → job times out → automatic re-selection (see §6)

Result Verifier (0x0000...0003)
    └── Verify commitments → produce VerifiedResult → deferred callback to Actor
```

#### **4. Runner Registry & Candidate List Construction**

**System Actor:** `0x0000...0001`

The Registry maintains runners with full registration data including stake, capabilities, rate card, health, and reputation.

**Candidate list construction** (at `submission_block`):

1. **Health filter:** `HealthStatus::Healthy` (heartbeat received within `heartbeat_timeout_blocks`)  
2. **Reputation filter:** `reputation ≥ 50`  
3. **Capability filter:** Runner supports the required `JobType`  
4. **TEE filter:** If `tee_required`, runner must declare TEE support (attestation verified by TEE Verifier `0x05`)  
5. **Price filter:** Estimated cost ≤ `job_spec.max_price`  
6. **Concurrency filter:** `active_jobs < max_concurrent_jobs`  
7. **Entitlement filter** *(optional)*: If `required_runner_pool = Some(pool_id)`, the Entitlement Registry (`0x07`) must confirm that the runner holds an Entitlement with `Scope::RunnerPool(pool_id)` and `Action::RunnerJoinPool(pool_id)` that has not expired and has not exceeded its `max_uses` (see §7.3)

**Candidate list ordering:** After filtering, candidates are **sorted ascending by address bytes** to produce a globally consistent, deterministic ordered list. This sort is mandatory — different nodes must arrive at the identical ordered list.

**Candidate list snapshot:** The filtered and sorted list is fixed at `submission_block`. Runners who join or leave after submission do not affect the selection for this job.

#### **5. Verifiable Runner Selection (Fisher-Yates VRF)**

<Warning>
  The ring-buffer selection from the original CIP-2 draft (start_index + consecutive indices) is **superseded** by this specification. Ring-buffer selection is vulnerable to correlation attacks: an adversary controlling M adjacent positions in the list can guarantee selection for any M-runner job.
</Warning>

**VRF Seed (deterministic, no private key required):**

```
seed = Keccak256(
    block_hash              // consensus-fixed, globally consistent
    || "cowboy-runner-select-v2:"  // domain separator (prevents cross-context collisions)
    || job_id               // unique per job
    || submitted_at_le8     // 8-byte LE block height
)
```

`block_hash` is the hash of the `submission_block`, already fixed by consensus. No private key is required. `block_hash` is a public value — all nodes agree on it — so HMAC's key-hiding property is unnecessary here. A domain separator achieves the same cross-context isolation.

> **Implementation note:** Use `cowboy_types::keccak256`, which is the project-standard hash primitive (consistent with job ID generation, timer ID generation, token ID generation, etc.). The `pvm_host::randomness()` API uses HKDF-SHA256 specifically because it is a security-critical PRF exposed to Actor code; the runner selection seed has no such requirement.


**Stake-Weighted Fisher-Yates Shuffle (select M from N):**

```
candidates ← sorted filtered list (length N)
weights[i] ← stake_to_weight(candidates[i].stake)
   where stake_to_weight(s) = floor(log2(s / MIN_STAKE + 1)) + 1
   (logarithmic compression: 1024× stake → 11× weight, preventing whale monopoly)

current_seed ← seed
for i in 0..M:
    total_remaining ← sum(weights[i..N])
    hash ← Keccak256(current_seed || i_le8)
    r ← u64_from_le(hash[0..8]) mod total_remaining
    j ← weighted_pick(weights[i..N], r)   // cumulative weight lookup → O(N)
    swap(candidates[i], candidates[i+j])
    swap(weights[i], weights[i+j])
    current_seed ← hash

selected ← candidates[0..M].addresses
```

**Properties:**
- Selected runners are **pairwise independent**: no two selections are correlated
- Higher stake → higher probability of selection (Sybil resistance)
- Same `seed` + same `candidates` always produces the same result (determinism)
- Any node can independently verify the selection (verifiability)

**On-chain verification** (in Result Verifier and Job Dispatcher):  
Given `(candidates_snapshot, seed, M)`, re-run the above algorithm to verify that `msg.sender` is among the selected set. The `candidates_snapshot` Merkle root is stored at submission time.

#### **6. Timeout-Based Re-selection (replaces skip_task)**

<Note>
  The `skip_task` interface is **removed** from this revision. Explicit skipping creates adverse incentives (runners cherry-picking jobs) and unnecessary on-chain transactions. Timeout-based re-selection achieves the same liveness guarantee with better economic alignment.
</Note>

**Timeout re-selection protocol:**

1. Selected runners have `timeout_blocks` to submit their result commitment.  
2. If no commitment is received within `timeout_blocks`:  
   - All timed-out runners receive `reputation -= TIMEOUT_PENALTY` (default: 5)  
   - Dispatcher triggers re-selection:  
     `retry_seed = Keccak256(original_seed || "retry:" || retry_count_le4)`  
   - Timed-out runners are excluded from the retry candidate list  
   - A new set of M runners is selected from the remaining candidates  
3. After `MAX_RETRIES` (default: 3) consecutive failures, the job transitions to `Failed` and `reputation -= SLASH_THRESHOLD` for persistent non-responders  
4. After `SLASH_THRESHOLD` consecutive slashes, a stake slash is triggered

**Economic alignment:** Not executing = passive timeout = reputation loss. Runners are incentivized to either execute or proactively avoid accepting jobs they cannot execute (by not heartbeating for job types they lack).

#### **7. Entitlement Registry (`0x0000…0007`)**

The Entitlement Registry is a system Actor that provides a unified, on-chain permission management layer. For this CIP, its primary role is **Runner Pool access control** (gating job assignments to a curated set of runners). It also provides general RBAC infrastructure consumed by other subsystems (Token admin delegation, Actor access control, etc.).

##### **7.1 Core Type System**

The Entitlement type system is defined in `cowboy_types::entitlement`:

```rust
/// Scope — defines the resource boundary a permission applies to
pub enum Scope {
    Global,                   // chain-wide
    Actor(Address),           // specific Actor
    Token([u8; 32]),          // specific Token (token_id)
    Runner(Address),          // specific Runner
    RunnerPool(Vec<u8>),      // Runner Pool membership (pool_id bytes)
    Namespace(Vec<u8>),       // custom named namespace
}

/// Action — defines the permitted operation (single action per Entitlement record)
pub enum Action {
    All,                                       // wildcard
    // Token actions
    TokenTransfer, TokenMint, TokenBurn,
    TokenFreeze, TokenSetHook, TokenTransferOwnership,
    // Actor actions
    ActorDeploy, ActorSendMessage,
    ActorExecuteHandler(Vec<u8>),              // handler name
    // Runner actions
    RunnerRegister { min_stake_override: Option<u128> },
    RunnerSubmitJob, RunnerSubmitResult,
    RunnerJoinPool(Vec<u8>),                   // pool_id — grants pool membership
    // System actions
    SystemTransfer, SystemCreateAccount, SystemUpgrade,
    // Custom
    Custom(Vec<u8>),
}

/// Constraints — use conditions attached to an Entitlement
pub struct Constraints {
    pub valid_from:          Option<u64>,   // block height activation
    pub valid_until:         Option<u64>,   // block height expiry
    pub max_uses:            u64,           // 0 = unlimited
    pub used_count:          u64,
    pub max_amount_per_use:  Option<u64>,
    pub max_total_amount:    Option<u64>,
    pub total_amount_used:   u64,
    pub rate_limit:          Option<RateLimit>,
    pub delegatable:         bool,
    pub delegation_depth_max: u8,           // max delegation chain depth (0 = non-delegatable)
    pub revocable:           bool,
}

/// A single Entitlement record (one scope + one action per record)
pub struct Entitlement {
    pub grantee:    Address,
    pub scope:      Scope,
    pub action:     Action,
    pub constraints: Constraints,
    pub parent_id:  Option<EntitlementId>,  // set when derived via delegation
}

pub type EntitlementId = [u8; 32];  // keccak256(grantee || scope || action || parent_id?)

/// Named permission set (RBAC role)
pub struct Role {
    pub name:        Vec<u8>,
    pub scopes:      Vec<Scope>,
    pub actions:     Vec<Action>,
    pub constraints: Constraints,
}
```

> **Design note:** Each `Entitlement` record covers **one** `(Scope, Action)` pair. Granting multiple actions requires multiple `Grant` calls (or an `AssignRole` that references a `Role` collecting them). This keeps revocation granular: revoking one action does not affect others.

##### **7.2 System Instructions (instruction numbers 30–39)**

```rust
pub enum SystemInstruction {
    // ... existing instructions 0–29 ...

    // Entitlement instructions (30–39)
    EntitlementGrant {
        grantee:     Address,
        scope:       Vec<u8>,       // codec-encoded Scope
        action:      Vec<u8>,       // codec-encoded Action
        constraints: Vec<u8>,       // codec-encoded Constraints
    },                                              // 30
    EntitlementRevoke {
        entitlement_id: [u8; 32],
    },                                              // 31
    EntitlementDelegate {
        entitlement_id: [u8; 32],
        delegatee:      Address,
        constraints:    Vec<u8>,    // must be a strict subset of parent constraints
    },                                              // 32
    EntitlementCreateRole {
        name:          Vec<u8>,
        scopes:        Vec<u8>,     // codec-encoded Vec<Scope>
        actions:       Vec<u8>,     // codec-encoded Vec<Action>
        constraints:   Vec<u8>,
    },                                              // 33
    EntitlementAssignRole {
        role_id:  [u8; 32],
        assignee: Address,
    },                                              // 34
    EntitlementRevokeRole {
        role_id:  [u8; 32],
        assignee: Address,
    },                                              // 35
}
```

##### **7.3 Runner Pool Membership Model**

A **Runner Pool** is an on-chain access-control list identified by an arbitrary `pool_id: Vec<u8>`. Membership is represented as an Entitlement:

```
Scope::RunnerPool(pool_id) + Action::RunnerJoinPool(pool_id)
```

**Grant flow:**

```
Pool Owner / Governance
    │
    └── EntitlementGrant {
            grantee:  <runner_address>,
            scope:    Scope::RunnerPool(pool_id),
            action:   Action::RunnerJoinPool(pool_id),
            constraints: Constraints {
                valid_until: Some(expiry_block),  // optional time-bound
                max_uses: 0,                      // unlimited while valid
                delegatable: false,               // pool membership is non-delegatable
                revocable: true,
                ..Default::default()
            },
        }
```

**Candidate filter check** (step 7 of §4, at `submission_block`):

```
EntitlementRegistry.check(
    grantee = runner_address,
    scope   = Scope::RunnerPool(required_runner_pool),
    action  = Action::RunnerJoinPool(required_runner_pool),
    at_block = submission_block,
) → bool
```

The check passes if at least one non-expired, non-exhausted Entitlement matching `(grantee, scope, action)` exists. `used_count` is **not** incremented by the membership check — only by explicit `max_uses`-bounded grants (e.g. one-time trial membership).

**Access modes enabled:**

| Mode | `required_runner_pool` | Effect |
|------|----------------------|--------|
| **Open** (default) | `None` | Any qualified runner may be selected |
| **Whitelist** | `Some(trusted_pool_id)` | Only runners with pool Entitlement |
| **Compliance-gated** | `Some(eu_tee_pool_id)` | Only runners with regional or TEE-certified Entitlement |
| **Governance-curated** | `Some(dao_pool_id)` | DAO grants pool membership via on-chain governance |

##### **7.4 Gas Costs**

| Operation | Cycles | Cells |
|-----------|--------|-------|
| `EntitlementGrant` | 5,000 | 500 |
| `EntitlementRevoke` | 2,000 | 100 |
| `EntitlementDelegate` | 3,000 | 300 |
| `EntitlementCreateRole` | 5,000 | 500 |
| `EntitlementAssignRole` / `RevokeRole` | 2,000 | 100 |
| Entitlement check (per candidate, §4 filter) | 500 | 0 |

##### **7.5 Safety Limits**

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max Entitlements per address | 256 | Prevent storage inflation |
| Max delegation chain depth | 5 (`delegation_depth_max`) | Prevent unbounded chains |
| Max Roles per address | 64 | Bound role-expansion attacks |
| Lazy expiry cleanup | On-access | Expired Entitlements deleted on first check post-expiry |

##### **7.6 Backwards Compatibility**

1. **Default pass-through:** If the Entitlement Registry Actor does not exist, all checks return `false` (no runner is admitted via pool filter). Jobs with `required_runner_pool = None` are unaffected.  
2. **Existing subsystems:** Token `owner == caller` checks remain the first-priority gate; Entitlement provides an additional delegation path, not a replacement.  
3. **Instruction numbering isolation:** Instructions 30–39 do not conflict with existing instructions 0–29.

#### **8. Result Submission: Commit-Reveal + Designated Aggregator**

<Note>
  This revision replaces the original model (all runners independently submit full results to chain) with a commit-reveal + aggregator model that reduces on-chain Gas by ~(N-1)/N and prevents runners from copying each other's results after seeing them.
</Note>

**Participants:**
- **Runners:** All M selected runners execute the job independently
- **Aggregator:** The selected runner with the highest reputation (deterministic, ties broken by address order). Acts as the coordinator.

**Submission flow:**

```
Step 1 – Commit (all M runners, on-chain, low cost):
    commit(runner_addr, job_id, hash(result_bytes || runner_sig))
    Deadline: submitted_at + commit_deadline_blocks

Step 2 – Collect (Aggregator, off-chain):
    Aggregator receives result_bytes from other runners via direct HTTP push
    Aggregator runs verification logic (majority vote, structured match, etc.)

Step 3 – Reveal (Aggregator, on-chain):
    submit_verified_result(job_id, VerifiedResult, reveals[])
    reveals[i] = { runner, result_bytes, runner_sig }
    Aggregator receives a small bonus reward for honest aggregation

Step 4 – On-chain verification (Result Verifier):
    For each reveal[i]:
        assert hash(result_bytes || runner_sig) == stored_commitment[i]
        assert runner_sig is valid Ed25519 over result_bytes
    Run verification mode checks (MajorityVote, StructuredMatch, etc.)
    Produce VerifiedResult → trigger deferred callback (CIP-1)
```

**Safety properties:**
- Runners cannot copy others' results after seeing them (commitment pre-locks the result)
- Aggregator cannot forge other runners' results (commitment-bound)
- Aggregator failure: other runners may submit individual reveals after `aggregator_timeout_blocks`; Result Verifier falls back to self-aggregation

#### **9. Verification Modes**

| Mode | Runners | Description |
|------|---------|-------------|
| **None** | 1 | No verification. Dev/test only. |
| **EconomicBond** | 1 | Single runner with economic stake bond. |
| **MajorityVote** | N ≥ 3 | Extract `vote_field`, majority wins with threshold. |
| **StructuredMatch** | N ≥ 2 | Pipeline of checks: JsonSchema, field matching, numeric tolerance, numeric range, per-field majority. |
| **Deterministic** | N ≥ 2 | Byte-identical match across all results. Requires `tee_required = true` for meaningful guarantees (LLM inference is inherently non-deterministic without TEE + fixed model hash). TEE attestation verified by TEE Verifier (`0x05`). |
| **SemanticSimilarity** | N ≥ 3 | Cosine similarity clustering; largest cluster meeting threshold wins. |

#### **10. Randomness Evolution Path**

The VRF seed source evolves across three phases without changing the selection algorithm or Actor-facing APIs:

| Phase | Seed IKM | Security Assumption |
|-------|----------|---------------------|
| **L1 (current)** | `block_hash` of `submission_block` | Honest supermajority of block proposers |
| **L2 (near-term)** | `block_vrf_output` = EC-VRF output by block proposer (in block header) | Honest block proposer per round |
| **L3 (long-term)** | `block_vrf_output` = Threshold-BLS t-of-n beacon | t-of-n validators honest |

The `pvm_host.rs` randomness API is designed for zero-Actor-code-change migration: only the IKM source switches internally.

---

### **Rationale**

* **Fisher-Yates VRF over ring-buffer:** The original ring-buffer selection (selecting N consecutive indices) is vulnerable to correlation attacks — an adversary controlling adjacent positions in the active list is always selected together for any N-runner job. Fisher-Yates with independent weighted draws eliminates this correlation entirely.

* **Stake-weighting:** Equal-probability selection ignores stake, making Sybil attacks cheap (register 100 minimal-stake accounts = 100× chance). Logarithmic stake weighting provides proportional incentives without enabling whale monopoly.

* **No private key for VRF seed:** Using `Keccak256(block_hash || domain || job_id)` instead of a dispatcher private key eliminates both the hardcoded-key security hole and the single-node selection bias. `block_hash` is consensus-fixed and globally consistent.

* **Timeout re-selection over skip_task:** `skip_task` creates adverse incentives (runners selectively skip low-value jobs) and adds unnecessary on-chain transactions. Passive timeout with reputation penalty provides the same liveness guarantee with better economic alignment.

* **Commit-reveal aggregator:** All-runners-submit to chain costs Gas × N and allows result copying. Commit-reveal prevents copying; designating the highest-reputation runner as aggregator is deterministic and Gas-efficient.

* **Deferred Transactions (CIP-1):** Callbacks are delivered as deferred transactions, decoupling off-chain execution latency from the main chain execution path.

* **Mandatory Result Schemas:** Creates a clear contract between developers and Runners, prevents gas-bombing, and simplifies result verification.

* **Entitlement as membership proof (not just a flag):** Pool membership is represented as an on-chain Entitlement record (with expiry, rate-limit, delegatability) rather than a simple boolean flag. This allows time-bounded trial access, revocable membership, and delegation to sub-pools without protocol changes.

* **Single action per Entitlement record:** Each record carries one `(Scope, Action)` pair. This enables fine-grained revocation without affecting co-granted actions, and keeps the membership check path O(1) per action.

---

### **Backwards Compatibility**

This CIP is fully backwards compatible with the core protocol. System Actor addresses are unchanged (`0x01`–`0x05`, `0x07`; `0x06` is reserved). The `skip_task` interface is removed; existing task submissions that relied on skip behavior will rely on timeout re-selection instead, which provides equivalent liveness guarantees.

---

### **Security Considerations**

* **VRF Grinding:** A submitter could attempt to choose `submitted_at` to influence the seed. Since `seed = Keccak256(block_hash || domain || job_id || submitted_at)` and `block_hash` is consensus-fixed before the submitter can observe it, this attack requires pre-computing the block hash — equivalent to breaking the consensus security assumption.

* **Stake Concentration:** The logarithmic weight compression `log2(stake/MIN_STAKE + 1) + 1` limits the selection advantage of high-stake runners. A runner with 1024× the minimum stake gets only 11× the selection weight, not 1024×. `MIN_STAKE = 10,000 CBY`.

* **Aggregator Collusion:** The Aggregator sees all results before submitting to chain. Mitigations: (1) other runners' commitments are locked before Aggregator submits; (2) other runners can independently reveal if Aggregator is unresponsive; (3) Aggregator's extra reward is forfeit if the submitted VerifiedResult is later challenged.

* **Active List Manipulation:** Minimum stake (`MIN_STAKE`) and reputation threshold (`min_reputation = 50`) provide economic deterrence. The Entitlement pool mechanism (§7) allows job submitters to further restrict runner eligibility.

* **Callback Griefing:** A malicious developer could write a callback that always fails, preventing runners from being paid. The `failed_callbacks` counter accrues as a reputational penalty, and runners may blacklist actors with high failure rates.

* **Historical Snapshot Integrity:** The candidate list is fixed at `submission_block`. The Merkle root of the candidate list must be stored on-chain at submission time to enable re-selection verification. Runners who join or leave post-submission do not affect the snapshot.

* **Entitlement Inflation:** Each address is limited to 256 active Entitlements and 64 assigned Roles. `EntitlementGrant` consumes 500 Cells to deter spam. Expired Entitlements are lazily cleaned on first post-expiry check.

* **Delegation Chain Depth:** `delegation_depth_max` (max 5) and the requirement that delegated constraints be a strict subset of parent constraints prevent privilege escalation through chained delegation.

* **Pool Membership Expiry:** Pool Entitlements with `valid_until` set are automatically ineligible after the specified block. Node operators running compliance-sensitive pools should set time-bounded grants and renew via governance.

---

## Part II — v2 Revision (canonical; verbatim from former `cip-2-aligned.md`)


<Note>
  **Status:** Draft (alignment addendum; non-modifying companion to `cip-2-offchain-compute.md`)
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-04-21
  **Companion to:** `cip-2-offchain-compute.md`
  **Reads with:** former `alignment-conventions.md` (now inlined as Part III of cip-14/15/16 v2 docs), `cip-16-custom-domains-v2.md` (Part II)
</Note>

## 0. What this document is

A code-aligned addendum to CIP-2. CIP-2 already carries a 2026-04-15 amendment block that addresses system actor addresses, runner stake formula, and `VerificationMode` discriminants; this document layers two more amendments on top:

- **AMEND 2-A** — `VerifierCheck::DnsTxtRecordMatch` variant (required by CIP-16-aligned §5.3).
- **AMEND 2-B** — `VerifierCheck::DnsCnameMatch` variant (required by CIP-16-aligned §5.3).

It also clarifies how `JobType::Custom` (`runner/src/types.rs:146-149`) is the established mechanism for adding new verifier executors without forking `JobType` discriminants.

This document does not change CIP-2's existing primitives. The seven on-chain System Actor components, Fisher-Yates VRF selection, commit-reveal aggregation, deferred-tx callbacks, and Pool membership rules all stand.

---

## 1. Preconditions

None. The amendments here are additive over CIP-2's current content.

---

## 2. New `VerifierCheck` variants

Add two variants to the `VerifierCheck` enum (`runner/src/types.rs:177-201`). The current variants are `MajorityVote`, `JsonSchemaValid`, `StructuredMatch`, `NumericTolerance`, `NumericRange`, `Custom`. The additions:

```rust
pub enum VerifierCheck {
    // existing variants (unchanged)
    MajorityVote     { field: String },
    JsonSchemaValid  { schema: String },
    StructuredMatch  { fields: Vec<String> },
    NumericTolerance { field: String, tolerance: f64 },
    NumericRange     { field: String, min: f64, max: f64 },
    Custom           { actor_hex: String, method: String },

    // NEW (AMEND 2-A)
    DnsTxtRecordMatch {
        fqdn:           String,
        expected_value: String,
        min_resolvers:  u32,
    },

    // NEW (AMEND 2-B)
    DnsCnameMatch {
        fqdn:            String,
        expected_target: String,
        min_resolvers:   u32,
    },
}
```

### 2.1 `DnsTxtRecordMatch` semantics

Each verifier runner queries `min_resolvers` independent recursive resolvers (operator-configured public list — see §2.3). For each resolver, the runner reports whether the TXT records at `fqdn` contain `expected_value` (exact byte match against any single record). The check passes for that runner if a strict majority of its resolvers confirm.

Aggregation under `VerificationMode::MajorityVote` (the only mode that makes sense for non-deterministic DNS — see §3): the result verifier counts runner-level pass/fail and the binding transitions only if ≥ `threshold` runners report pass.

### 2.2 `DnsCnameMatch` semantics

Same shape as 2.1 but follows the CNAME chain for `fqdn`, requiring it to terminate at `expected_target`. The chain is followed up to `MAX_CNAME_HOPS = 8` per RFC 1034 §3.6.2; longer chains report fail.

### 2.3 Resolver pool configuration

Each runner advertises a configurable list of recursive resolvers in its capabilities. Recommended public defaults:

```
1.1.1.1            (Cloudflare)
8.8.8.8            (Google Public DNS)
9.9.9.9            (Quad9)
208.67.222.222     (OpenDNS)
```

A runner whose advertised resolver pool is smaller than the job's `min_resolvers` MUST decline the job during VRF selection rather than re-querying the same resolver to hit the count. This prevents single-resolver bias from being laundered as multi-resolver consensus.

### 2.4 Why `MajorityVote` and not `Deterministic`

DNS resolution is not byte-identical across resolvers — TTL state, edge anycast routing, and per-resolver caching produce divergent observed records even when the authoritative zone is consistent. `VerificationMode::Deterministic` (`runner/src/types.rs:217`) requires byte-identical output and TEE attestation; using it for DNS would either fail constantly (different resolvers see different bytes) or force runners into a single shared resolver that defeats the point of multi-runner verification.

`MajorityVote` already exists and is the structurally correct mode. The original CIP-16 §9.6's choice of `Deterministic` was the mismatch CIP-16-aligned corrects.

---

## 3. `JobType::Custom` as the extension pattern (clarification)

CIP-2's existing `JobType::Custom { executor_hash: [u8; 32], params: Vec<u8> }` (`runner/src/types.rs:146-149`) is the established mechanism for adding new verifier-bearing job types without expanding the `JobType` discriminant set.

Pattern for a new built-in verifier (DNS verification is the first instance; future TLS-cert validation, on-chain proof verification, RPC liveness checks, etc. should follow):

1. Build the verifier as a deterministic executor binary (Rust → reproducible build).
2. Hash the binary with BLAKE3.
3. Pin the hash via governance: write a record at `GOVERNANCE_SYSTEM_ACTOR=0x09` keyed `system:executor_registry:<name>`.
4. Issue jobs as `JobType::Custom { executor_hash: PINNED_HASH, params: <serialized job-specific params> }`.
5. Runners that have whitelisted the executor execute the job. Verification proceeds via the standard `VerifierCheck` chain — §2 above adds DNS checks; future amendments add their own.

This avoids fragmenting `JobType` for every new built-in verifier and keeps the discriminant space stable. CIP-16-aligned uses this for `DNS_VERIFIER_EXECUTOR_HASH`; the same hash-pinning pattern works for any future system-pinned executor.

### 3.1 Governance pinning vs. open executors

`JobType::Custom` accepts any `executor_hash`, including user-supplied ones — the protocol does not require governance pinning. Governance pinning is the convention for **protocol-level** executors used by system actors; user-deployed verification jobs (e.g., a DAO running custom market-data validation) can use any hash they trust.

The distinction is purely operational: governance-pinned executors can be referenced by system actors (e.g., the Route Registry calling DNS verification) because the hash is itself part of the chain's normative state. User-supplied hashes are the user's own trust assumption.

---

## 4. `JobSpec` shape (no change)

`JobSpec` (`runner/src/types.rs:101-117`) is unchanged. The new `VerifierCheck` variants slot into the existing `verification.checks: Vec<VerifierCheck>` field. CIP-16-aligned §5.3 shows the full `JobSpec` template for DNS verification, which uses only existing `JobSpec` fields.

---

## 5. Backwards compatibility

Additive over CIP-2 and the running codebase:

- Two new `VerifierCheck` variants. Existing consumers must add match arms for `DnsTxtRecordMatch` / `DnsCnameMatch`; otherwise unchanged.
- `JobType::Custom` is unchanged; §3 documents an existing extension mechanism.
- No existing job type, RPC, storage format, or VRF semantics is modified.

Runners that have not been upgraded to support DNS executors simply do not advertise the resolver capability and are not selected for DNS verification jobs (existing capability-matching logic in `runner-registry`).

---

## 6. Summary

| Amendment | Required by | Impact |
|---|---|---|
| AMEND 2-A — `DnsTxtRecordMatch` variant | CIP-16-aligned §5.3 | New enum variant; new runner capability |
| AMEND 2-B — `DnsCnameMatch` variant | CIP-16-aligned §5.3 | New enum variant; reuses resolver pool |
| §3 — `JobType::Custom` extension pattern (documentation) | Future built-in verifiers | No code change; pinning convention |
