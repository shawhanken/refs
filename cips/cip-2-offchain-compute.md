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

---

## Part III — v3 Mechanism Revisions (canonical; runner-marketplace reform)

### 0. What this revision does

v3 patches **seven** Part I mechanism specifications surfaced by the 2026-04 architecture review as P1/P2 gaps. The fix-set is internally coherent: each change either replaces an unspecified mechanism with a normative one (reputation formula, non-reveal classification, aggregator-bonus magnitude) or replaces a vulnerable mechanism with a hardened one (static committee → adaptive; pure-stake VRF → stake×reputation; aggregator lock-in → eligibility threshold). Distribution of slashed stake is intentionally held at **100% burn** (consistent with WP §8.4 commitment C7) — the field structure for fractional bounty payouts is introduced but defaults zero, awaiting an explicit Tier-3 governance proposal that pre-clears the C7 amendment.

**What v3 changes:**

1. **Adaptive committee sizing** (§1) replaces static `M = 5, N = 3`.
2. **VRF weight** (§2) becomes `w = stake · sqrt(reputation)` instead of `floor(log2(stake / MIN_STAKE + 1)) + 1`. Stake-only weighting amplifies "rich-get-richer"; the square-root reputation term provides a graceful merit signal without enabling pure reputation-mining attacks.
3. **EMA reputation** (§3) — closes the long-standing gap that Part I references reputation throughout but never defines decay or recovery. 14-day half-life at 1-second blocks = 1,209,600 blocks (Tier-0 tunable).
4. **Aggregator reform** (§4): eligibility-threshold (≥ p50 reputation) + uniform-random selection + 1.5%-of-gross bonus. Replaces "highest reputation in committee" lock-in (Part I §8) which permanently locks out new runners.
5. **Non-reveal classification** (§5): commit-without-reveal within an exemption window is treated as proven dishonesty by default, with a single `CrashAttestation`-gated grace path for legitimate crashes. Replaces the timeout-only reputation-penalty path in Part I §6 — which the reviewer correctly identified as a denial-of-verification attack vector (an adversary commits garbage, waits for other commits, then refuses to reveal if the consensus is unfavourable).
6. **Slash distribution schema** (§6): introduces `SlashDistribution { burn_bps, submitter_bps, treasury_bps }` with HOLD-path defaults `(10000, 0, 0)`. The field structure makes a future Tier-3 governance amendment (50/30/20 challenger/burn/treasury) a flag flip rather than a CIP rewrite, but the WP §8.4 C7 commitment is **preserved** until that amendment lands.
7. **SemanticSimilarity embedding pinning** (§7): the verification mode currently leaves the embedding model unspecified, allowing a runner to collude with embedding choice. v3 pins the model at `0x09` under `system:cip2:semantic_similarity_embedding_model`; changes require Tier-3 governance (consensus-criticality carve-out from the default Tier-1 model-registry path).

**What v3 does NOT change:**

- **Runner stake floor** remains `max(10,000 CBY, 1.5 × declared_max_job_value)` (CBY-denominated). The USD-pegged variant proposed by the architecture review is **deferred** per Decision #4 default — no consensus-layer oracle dependency is introduced in v3. A future CIP MAY re-peg once an oracle module exists.
- **Fisher-Yates VRF mechanism** (Part I §5) — the *weight formula* changes (§2 above), but the selection algorithm is unchanged.
- **Commit-reveal flow** (Part I §8) — only the aggregator-selection rule and the bonus formula change; commit/collect/reveal/verify stages are unchanged.
- **Verification modes enum** (Part I §9) — six modes unchanged; only the SemanticSimilarity sub-rule on embedding model is added.
- **VerifierCheck variants** (Part II) — unchanged.
- **System-instruction opcodes** — unchanged.

### 1. Adaptive committee sizing (supersedes Part I §5 fixed M/N)

```
M_target(N_active, HHI) = ceil(2 · log₂(N_active) / max(HHI, HHI_min))
M       = clip(M_target, M_min, M_max)
N_threshold = ceil(2 · M / 3)
```

Parameters (Tier-0 tunable, stored at `0x09` under `system:cip2:committee.*`):

| Parameter | Default | Notes |
|---|---|---|
| `M_min` | 3 | Floor for the committee size (matches BFT N≥3 minimum) |
| `M_max` | 9 | Ceiling (caps verification cost per job) |
| `HHI_min` | 0.01 | Numerical floor on the denominator — prevents division blow-up when HHI is computed over near-uniform stake distribution |
| `HHI_smoothing_alpha` | 0.125 | EMA smoothing factor applied to HHI to prevent committee-size flapping on single-block stake shocks |
| `committee_recompute_period` | 1 epoch (= 3,600 blocks at 1s, per WP §13) | Frequency of M recomputation; on each recompute boundary, jobs in flight retain their committee, new dispatches use the new M |

**HHI computation.**

```
shares       = effective_stake[i] / Σ effective_stake[i]    over registered + healthy runners
HHI_instant  = Σ shares[i]²                                  ∈ (0, 1]
HHI          = HHI_smoothing_alpha · HHI_instant + (1 − HHI_smoothing_alpha) · HHI_prior_epoch
```

`effective_stake` per CIP-13 §3.2 is `registration.stake + delegation_totals.total_active`.

**Worked example.**

| `N_active` | `HHI` | `M_target` | `M` (after clip) | `N_threshold` |
|---|---|---|---|---|
| 20 | 0.40 | ceil(2·4.32 / 0.40) = 22 | 9 (clip @ M_max) | 6 |
| 50 | 0.20 | ceil(2·5.64 / 0.20) = 57 | 9 (clip) | 6 |
| 100 | 0.05 | ceil(2·6.64 / 0.05) = 266 | 9 (clip) | 6 |
| 100 | 0.30 | ceil(2·6.64 / 0.30) = 45 | 9 (clip) | 6 |
| 100 | 1.00 (1 runner monopoly) | ceil(2·6.64 / 1.00) = 14 | 9 (clip) | 6 |
| 8 | 0.40 | ceil(2·3.00 / 0.40) = 15 | 9 (clip) | 6 |
| 4 | 0.50 | ceil(2·2.00 / 0.50) = 8 | 8 | 6 |
| 3 | 0.40 | ceil(2·1.58 / 0.40) = 8 | 8 (limited by N_active in dispatch) | 6 |

Empirically: at low concentration (HHI ≤ 0.30), M saturates at `M_max = 9`; at very concentrated runner sets (HHI > 0.40) and small `N_active`, M scales back toward the floor. The clip bounds prevent both committee-size explosion (DoS via large committees) and undersized committees on small networks.

**Migration from static M=5/N=3.** At activation block `H_v3`, the static spec in Part I §5 is replaced; jobs submitted at or after `H_v3` use the adaptive formula. Jobs in flight at `H_v3` retain their static committee. The committee size for the first epoch after `H_v3` is computed from the live `N_active` and `HHI` at the epoch boundary.

### 2. VRF weight `w = stake · sqrt(reputation)` (supersedes Part I §5 stake-only)

```
w_i = effective_stake[i] · max(sqrt(reputation[i] / REPUTATION_NORMALIZER), w_min_floor)
```

Parameters (Tier-0 tunable):

| Parameter | Default | Notes |
|---|---|---|
| `REPUTATION_NORMALIZER` | 100 | Treats reputation as 0..100 score; sqrt(1) = 1 means a runner at the normalizer value gets the same weight as pure stake |
| `w_min_floor` | 0.1 | Cold-start protection — a brand-new runner (zero reputation) still gets `weight = 0.1 · stake` rather than zero |

Why `sqrt(r)` and not `r^1` or `log(r)`:
- `r^0` (Part I) gives no reputation signal — vulnerable to pure stake-monopoly.
- `r^1` rewards established runners too aggressively — locks out new entrants the way the old aggregator rule did.
- `r^0.5` (= `sqrt(r)`) is the geometric-mean middle ground; a 4× reputation differential becomes a 2× selection-probability differential. Matches the heuristic Polkadot uses in NPoS phragmen and the staking-as-collateral literature.

**Migration.** Old runner reputation values from Part I (which were never formally bounded) are mapped: `reputation_new = clip(reputation_old, 0, 200)`. New runners enter at `reputation = 50` (network-median-equivalent starting point).

### 3. EMA reputation with 14-day half-life (NEW)

Part I references reputation as a filter (≥ 50 floor), as a penalty target (`-= TIMEOUT_PENALTY`), and as the aggregator-selector key — but never defines decay, recovery, or update mechanics. v3 pins:

```
on each timer fire / job settlement, for runner i:
    score_i_block = f(success, latency, slash_event)    in [0, 100]

    α = ln(2) / HALF_LIFE_BLOCKS                          // = ln(2) / 1_209_600  ≈ 5.73e-7
    reputation_i = reputation_i + α · (score_i_block − reputation_i)
    reputation_i = clip(reputation_i, REPUTATION_FLOOR, REPUTATION_CEILING)
```

Score function (Tier-2 tunable):

| Outcome | Score contribution |
|---|---|
| Successful settlement | 100 |
| Successful settlement as aggregator (bonus) | 110 (clipped at REPUTATION_CEILING) |
| Timeout (no commit) | 0 |
| Commit-without-reveal (non-reveal) | 0 (+ slash per §5–§6 below) |
| Invalid reveal (proof mismatch) | 0 (+ slash per §5–§6 below) |
| Jail (multiple consecutive failures) | reputation reset to `JAIL_EXIT_FLOOR` |

Parameters (stored at `0x09` under `system:cip2:reputation.*`):

| Parameter | Default | Mutability |
|---|---|---|
| `HALF_LIFE_BLOCKS` | 1,209,600 (= 14 days at 1s blocks per WP §13) | Tier-2 |
| `REPUTATION_FLOOR` | 0 | Tier-2 |
| `REPUTATION_CEILING` | 200 | Tier-2 |
| `JAIL_EXIT_FLOOR` | `max(round(0.1 · network_median_reputation), 50)` | Tier-2 |
| `REPUTATION_NORMALIZER` | 100 (used by §2 VRF weight) | Tier-2 |

**Reviewer's "250k blocks at 5s" arithmetic correction.** The architecture review proposed a 14-day half-life and computed it as "~250,000 blocks at 5-second slots". Cowboy runs **1-second blocks** per WP §13, so 14 days = **1,209,600 blocks**. This CIP uses the corrected value; the analysis at `refs/notion/cowboy-vm-shared/_analysis/03-runner-marketplace.md` captures the original error.

**Reputation in flight at `H_v3`.** Existing `reputation` integers from Part I are interpreted as the initial value of the EMA at `H_v3`; the first decay tick fires on the next job settlement involving that runner.

### 4. Aggregator reform (supersedes Part I §8 "highest reputation")

```
eligible = { runner in committee : reputation[runner] >= aggregator_eligibility_percentile_of(committee) }
   where aggregator_eligibility_percentile = 50 (Tier-0 tunable; key `system:cip2:aggregator.eligibility_percentile`)

if eligible == ∅:
    eligible = committee     // fallback: no one meets p50; use full committee

aggregator = uniform_random_from(eligible, seed = Keccak256(job_id || "agg-select-v3"))
```

**Bonus formula (replaces Part I §8 "a small bonus"):**

```
aggregator_bonus = gross_job_payment · aggregator_bonus_bps / 10000     // default bps = 150 = 1.5%
```

paid from the **runner share** (89% of gross under WP §8.4) — i.e. the bonus does not change the burn / treasury split. Conceptually: 89% runner share splits into `(89% − 1.5%) = 87.5%` divided across non-aggregator runners pro-rata to commit-reveal weight, plus `1.5%` aggregator bonus.

| Parameter | Default | Mutability |
|---|---|---|
| `aggregator_eligibility_percentile` | 50 (p50 reputation) | Tier-0 |
| `aggregator_bonus_bps` | 150 (1.5% of gross) | Tier-0 |
| `aggregator_selection_seed_domain` | `"agg-select-v3"` | fixed (consensus-relevant domain separator) |

**Why eligibility + uniform-random and not pure highest-reputation:**
- "Highest reputation" gives new runners zero probability of aggregating — they cannot bootstrap their reputation by aggregating successfully.
- Eligibility threshold (p50) ensures aggregators are competent without locking new runners out permanently — once a new runner crosses p50, they enter the eligibility pool.
- Uniform random within the eligible set prevents any deterministic-tie-breaker from concentrating aggregator share at a single high-reputation runner.

**Aggregator bonus paid only on successful settlement** (verification mode check passes, no slash event). Failed aggregations cost the aggregator the bonus; the §5 non-reveal classification handles outright dishonesty.

### 5. Non-reveal classification (supersedes Part I §6 timeout-only path)

The Part I §6 timeout protocol only penalizes reputation (with eventual stake slash after MAX_RETRIES consecutive failures). This creates a denial-of-verification attack: an adversary can commit `hash(garbage_result || sig)` in step 1, observe other commits' result hashes in step 2, then refuse to reveal in step 3 — costing the adversary only modest reputation but corrupting the verification outcome.

**v3 classification:**

```
classify_non_reveal(runner, job, commit_block, reveal_window_blocks):
    if reveal_received(runner, job) within commit_block + reveal_window_blocks:
        → success path (no penalty)

    if CrashAttestation(runner, sig, height ∈ [commit_block, commit_block + reveal_window_blocks])
       was submitted before commit_block + reveal_window_blocks:
        → "operational failure" path: reputation penalty per §3 (-= 0 deferred decay) + 
           `CrashAttestation` event emitted; no stake slash; runner exempted from slash this round

    otherwise:
        → "proven dishonesty" path:
           - reputation reset to 0
           - stake slash per §6 below
           - `NonRevealSlash` event emitted
```

**`CrashAttestation` mechanism.** A runner that legitimately crashes between commit and reveal can submit a signed attestation:

```
CrashAttestation {
    runner:        Address
    job_id:        bytes32
    crash_signal:  enum { OOM, NetworkPartition, HardwareFault, TEEAttestationLost, Other }
    timestamp:     Block
    self_signature: Signature   // runner's own key signing the structure
}
```

Submitted by the runner (or by an authorized off-chain watchdog with the runner's pre-issued signature) at or before `commit_block + crash_exemption_blocks` (Tier-2 tunable, default 50 blocks ≈ 50s at 1s blocks). The attestation does not get the runner the job payment, but it converts the non-reveal from "proven dishonesty" (slash) to "operational failure" (reputation hit only).

**Why an exemption mechanism instead of pure slash:**
- Without exemption, legitimate hardware faults cause runner stake destruction → discourages decentralised runner participation.
- Without slash by default, a denial-of-verification attack costs only reputation.
- With exemption: runners must take an explicit action to claim "crash" status, leaving an on-chain trail. Repeated CrashAttestations from the same runner trigger Tier-2 review (default: ≥ 5 attestations in 1,000-block window → automatic flag).

**Reveal window:** `reveal_window_blocks` defaults to `commit_deadline_blocks + 60` (i.e. 60 blocks after commit deadline; ~1 minute at 1s blocks). Tier-2 tunable.

| Parameter | Default | Mutability |
|---|---|---|
| `crash_exemption_blocks` | 50 (at 1s blocks ≈ 50 s) | Tier-2 |
| `reveal_window_blocks` | commit_deadline_blocks + 60 | Tier-2 |
| `crash_attestation_review_threshold` | 5 per 1,000 blocks | Tier-2 |

### 6. Slash distribution schema (HOLD path = 100% burn; Tier-3 to amend)

```
SlashDistribution {
    burn_bps:      u16,      // 0..10000; default 10000 (100% burn) — matches WP §8.4 C7
    submitter_bps: u16,      // 0..10000; default 0           — challenger/submitter share, inactive at v3 launch
    treasury_bps:  u16,      // 0..10000; default 0           — treasury share, inactive at v3 launch
    // invariant: burn_bps + submitter_bps + treasury_bps == 10000
}
```

Stored at `0x09` under `system:cip2:slash_distribution.{burn_bps, submitter_bps, treasury_bps}`. Genesis values `(10000, 0, 0)` — consistent with WP §8.4 commitment C7 ("Slashed stake | 100% | Burned"). Submitter and treasury shares are **inactive** at v3 launch; the schema exists so that a future amendment is a flag flip rather than a CIP rewrite.

**Mutability.** Any non-trivial change (any `bps` shifted away from the `(10000, 0, 0)` default) requires a **Tier-3 governance proposal** that also amends WP §8.4 C7 in lockstep — the schema-level flexibility does **not** unilaterally override the C7 commitment. CIP-12 §5.1 Tier-3 row implicitly covers this because changing slash distribution is a substantive economic-mechanism change, not a scalar tweak.

**Why a Tier-0 schema with Tier-3 mutability:** the field structure lives in code from v3 onward (no migration when the C7 amendment lands); only governance authority changes per-amendment. This avoids the "schema added later" trap that creates two competing code paths.

**Non-reveal slash magnitude (used in §5 path 3):**

```
non_reveal_slash_amount = min(
    runner_effective_stake · non_reveal_slash_bps / 10000,
    max_non_reveal_slash_cby
)
```

| Parameter | Default | Mutability |
|---|---|---|
| `non_reveal_slash_bps` | 2500 (25% of effective stake) | Tier-2 |
| `max_non_reveal_slash_cby` | 100,000 CBY | Tier-2 |

(The reviewer's recommended 25% fractional slash is adopted as the bps value; the absolute cap prevents catastrophic overshoot on extremely large stake positions.)

### 7. SemanticSimilarity embedding pinning (supersedes Part I §9 unspecified)

Part I §9 lists `SemanticSimilarity` as a verification mode (N ≥ 3; cosine similarity clustering; largest cluster wins). The embedding model used to compute similarity is unspecified — leaving it as a free parameter that any runner could collude with. v3 pins:

```
system:cip2:semantic_similarity_embedding_model = "sentence-transformers/all-mpnet-base-v2"
                                                  (default; see model_registry below)
```

The value is a model identifier resolvable via the existing model registry (`model_id` field in CIP-2 v1 §2). Changes follow the **consensus-criticality carve-out**:

- **Default routing.** Per CIP-12 §5.1, "model flags/bans" are Tier 1 (15% quorum / >55% approval). The general model-registry path remains Tier 1.
- **Carve-out.** The specific entry `system:cip2:semantic_similarity_embedding_model` is flagged Tier-3 (15% quorum / >60% approval) because changes alter consensus-verification semantics — a runner colluding with the embedding-model choice could swing similarity clustering. The carve-out is documented here (CIP-2 §7) rather than in CIP-12; the registry path remains Tier 1 for non-consensus-critical entries.

**Backwards compatibility.** Jobs scheduled before `H_v3` that use SemanticSimilarity verification used an undefined embedding model — the dispatcher at activation time MUST refuse to settle such jobs without an explicit re-submission specifying the canonical embedding model. This is a one-time migration cost; the analysis at `refs/notion/cowboy-vm-shared/_analysis/03-runner-marketplace.md` items #24/#65 capture the reasoning.

### 8. Stake floor (Decision #4 default — keep CBY-denominated)

Per the architecture-review Decision Register item #4, the analysis default is **CBY-denominated stake floor with documented Tier-0 monitoring cadence** rather than USD-pegged via TWAP oracle. v3 preserves Part I §4's `max(10,000 CBY, 1.5 × declared_max_job_value)` formula and adds:

- **Monitoring cadence.** The Cowboy Foundation publishes monthly the implied USD value of the 10,000-CBY floor and the median runner's effective stake. If the implied USD floor drifts outside the target band `[$1,000, $10,000]` for two consecutive monthly reviews, a **Tier-0 governance proposal** MUST be filed to adjust `MIN_RUNNER_STAKE_CBY`.
- **No oracle dependency.** v3 does NOT introduce a consensus-layer CBY/USD oracle. Re-pegging is a future option gated on a forthcoming oracle CIP.
- **Failure mode.** If CBY appreciates 10×+ and the 10,000-CBY floor becomes punitive for small runners, the monitoring cadence above triggers a Tier-0 adjustment. The dispatcher continues to admit runners meeting the formula until that proposal lands.

Decision Register item #4 status: **HOLD on CBY-denominated**. Re-evaluation triggers: (a) availability of a battle-tested oracle module (e.g., a CIP-31-style oracle parameter spec), or (b) sustained USD floor drift outside the target band beyond what Tier-0 cadence can address.

### 9. Activation and migration

v3 activates at a single block `H_v3` via Tier-3 governance proposal. At activation:

| Subsystem | Pre-`H_v3` | Post-`H_v3` |
|---|---|---|
| Committee size | Static `M=5, N=3` | Adaptive (§1) |
| VRF weight | `floor(log2(stake/MIN_STAKE+1))+1` | `stake · sqrt(reputation)` (§2) |
| Reputation update | Unspecified | EMA, 14-day half-life (§3) |
| Aggregator selection | "Highest reputation in committee" | Eligibility ≥ p50 + uniform random (§4) |
| Aggregator bonus | "A small bonus" (unspecified) | 1.5% of gross from runner share (§4) |
| Non-reveal handling | Reputation penalty only | Proven-dishonesty + `CrashAttestation` exemption (§5) |
| Slash distribution | Implicit 100% burn | Explicit `SlashDistribution { 100/0/0 }` schema (§6) — Tier-3 to flip |
| SemanticSimilarity embedding | Unspecified | Pinned at `system:cip2:semantic_similarity_embedding_model` (§7) |
| Stake floor | `max(10k CBY, 1.5 × declared_max_job_value)` | Unchanged (Decision #4 HOLD; §8) |

Jobs in flight at `H_v3` retain their committee, aggregator, and verification mode for completion; new jobs use v3 rules.

### 10. Open questions deferred to Phase-5 simulation

- **HHI-based committee shock.** If a single large runner exits/enters and HHI shifts 0.10 → 0.50 in one epoch, M halves. The smoothing factor `α = 0.125` damps this, but extreme cases may still cause perceptible per-job cost swings. Phase-5: simulate with realistic runner-set dynamics.
- **Reputation half-life calibration.** 14 days is the launch default; longer is more stable but slower to recover from rare-event mistakes; shorter is more reactive but lets recent bad runners re-enter selection too fast.
- **`crash_exemption_blocks = 50` default.** Long enough for hardware reboot signal propagation, short enough to deter "stall, observe, decide" tactical non-reveals. Phase-5: model attacker dwell time against block-time-to-attestation latency.
- **VRF weight `sqrt(reputation)` calibration.** Whether `r^0.5` or `r^0.4` better matches empirical merit signals — sensitivity to the exponent is high in the upper tail.
- **SlashDistribution `(10000, 0, 0)` HOLD vs `(5000, 2000, 3000)` AMEND** — gated on Decision Register #1 (WP §8.4 C7 amendment).

### 11. Backwards compatibility

- All Part II VerifierCheck variants and the `JobType::Custom` extension pattern remain in force.
- Runners that haven't upgraded to v3 see no API breakage at the runner protocol layer; the changes are protocol-internal mechanisms in `0x01`/`0x02`/`0x03` system actors. Runners SHOULD watch for `CrashAttestation` event reception (a new event type at `0x03`) — operational tooling that does not emit `CrashAttestation` simply pays the slash cost on unexpected crashes.
- Existing reputation integers carry forward at `H_v3` as the initial EMA value.
- No syscall, opcode, or message-format changes at the actor boundary.
