# Blocked Todo issues — pavilionledger / unassigned (2026-06-24)

Analysis of every Linear **COW** issue in **Todo** state that is assigned to
`pavilionledger@gmail.com` or unassigned (null) and **cannot currently be
fixed end-to-end**, with the concrete blocker for each.

**Scope note:** team ownership is intentionally ignored here — every issue is
analyzed on its *technical* blocker, not on "which team owns it". (In day-to-day
batch work, several of these are also out of our team's lane, but that is not the
reason listed below.)

Snapshot: 16 pavilion/null Todo issues. **15 are blocked** (this doc).
**1 (COW-1236) appears actionable** and is listed separately at the end.

Already resolved this cycle and out of the pool: **COW-2313** (wallet plaintext
key → Done, PR #15 merged), **COW-1664** (CIP-14 label constraints → node PR #825,
In Review), **COW-2275** (Canyon halt → reproduction merged node PR #824, root
cause confirmed; the fix itself remains owner-side).

---

## Blocker categories

| # | Category | Meaning |
|---|----------|---------|
| A | Target code not in this workspace | The thing to change lives in an infra/IaC repo that is not checked out locally — there is no source here to edit. |
| B | Coordination/rollout tracker | Not a code change at all; an action item that only becomes real at a future operational event. |
| C | Gated on an undecided decision | A spec/governance/tokenomics decision must be made before any code is correct to write. |
| D | Needs a design that doesn't exist | A non-trivial mechanism must be designed (often CIP-level) before implementation; no key/spec source exists today. |
| E | Premature — no benefit yet | Implementable, but delivers zero measurable value until a future condition (multi-validator, scale) holds; deferred by design. |
| F | Blocked on external prerequisites | Needs a running gateway/relay/runner/LLM/multi-validator stack or private deps that aren't available locally. |
| G | Large feature / stale premise | Substantial multi-part feature (not a discrete fix); in one case the issue's premise is now out of date and needs re-scoping. |

---

## The table

| Issue | Title (short) | Area / repo | Cat | Concrete blocker — why it can't be fixed now | What would unblock it |
|-------|---------------|-------------|:---:|----------------------------------------------|-----------------------|
| **COW-508** | API Gateway module for key-gated RPC | AWS API Gateway (`modules/api-gateway`) | A | The deliverable is a Terraform/IaC module proxying to RPC :4000 with usage plans + API keys + DNS. That repo (infra/`aws-infrastructure`) is **not in this workspace** — no source to edit; it's also an AWS provisioning task, not a node/runner code change. | Clone/access the infra repo; do it as IaC + AWS console work. |
| **COW-513** | Tailscale ACLs for Mesa tags | Tailscale ACL policy | A | Edit Tailscale ACL JSON (mesa-validator/rpc/user tags, peering rules) + generate auth keys. Pure network-operations config; **no file in this workspace**. | Access to the Tailscale tailnet admin + the ACL policy repo. |
| **COW-514** | Deploy API Gateway + usage plan + keys | AWS (stg env) | A | Deploy the `api-gateway` module to staging, create usage plan, issue first API key, wire DNS. Depends on COW-508 existing first; **deployment/ops task, not local code**. | COW-508 merged + AWS staging access. |
| **COW-515** | IP allowlist var in `terraform.tfvars` | Terraform (stg) | A | Add `mesa_rpc_allowed_ips` to a `terraform.tfvars` and document the add/remove process. The `.tfvars` lives in the infra repo, **not here**. | Access to the staging Terraform config. |
| **COW-2265** | Bundle devnet consensus deltas into mainnet activation | node (genesis/activation) | B | A **tracker**, not a code task: node#686 (receipt code 1613) and node#707 (64 KiB inline-blob cap) are already merged to devnet; this records that they need a coordinated activation height on a multi-validator mainnet. Nothing to implement until that bring-up exists. | Mainnet / multi-validator network bring-up; then encode an activation height. |
| **COW-2266** | Reconcile WP genesis params vs reference impl | node (`basefee.rs`, `constants.rs`) + spec | C | The whitepaper's genesis defaults (T_c, T_b, alpha, delta, state-rent, lane budgets) **disagree with the code** (e.g. WP T_c=10M vs code 20M). Which side is canonical is a **CIP-3/4 parameter-governance decision**; writing either value "wins" without that ruling just moves the drift. Decision memo issued but the ruling itself isn't landed. | A governance ruling fixing the canonical values (then it's a mechanical edit + a conformance test). |
| **COW-1265** | Genesis supply allocation (1B CBY split) | node (genesis config) | C | WP §8.3 gives an exact split (Company Reserve 66.67% / Network 33.33% with line items), but the scope also demands a **vesting schedule** that the spec does not fully define, and hardcoding a consensus-genesis allocation is a tokenomics/legal sign-off, not an engineering call. Genesis currently loads arbitrary accounts with **no enforcement**. | Final, signed-off allocation **and** vesting schedule; then hardcode/checksum-validate + test. |
| **COW-137** | PvmHost storage batch read optimization | node (`pvm_host.rs`) | D | "Pre-fetch *potentially needed* keys" has **no key-set source** in the model — there is no storage access-list (`storage.kv` grants carry only `max_bytes`), and PVM handlers read arbitrary keys at runtime. The only self-contained variant (bounded whole-actor warm-load) over-reads for sparse handlers and is an unproven perf bet. | A storage access-list design (CIP-level), **or** a benchmark justifying a speculative warm-load. |
| **COW-166** | Compact block representation | node (`chain/`, commonware) | D, E | BIP-152-style compact blocks need a new `CompactBlock` wire type + reconstruction + missing-tx round-trip, **hosted inside commonware-broadcast/resolver** (likely needs commonware support). It is also **premature**: on the single-validator devnet there is *zero* network overhead to reduce. | A wire-format + reconstruction design, commonware support, and an actual multi-validator network where it matters. |
| **COW-1274** | Decouple timer exec from propose critical path | node (`chain/`, `storage/speculative`) | E | The issue itself states this is the **next** architectural step *after* COW-1272 (wall-clock budget) and COW-1273 (warm PVM pool), which "buy us 1–2 years". A large refactor (timers out of `propose()`'s state-root path) with **no benefit at current scale**. | Workloads beyond Frontier scale (thousands of self-timed actors) that exceed the warm-pool budget. |
| **COW-1308** | CIP-2 v3 economic end-to-end example | node `examples/` | F | A full demo of job submit → committee sizing → VRF selection → settlement → slashing. Needs the **entire CIP-2 v3 economic pipeline runnable end-to-end** plus an e2e harness (runner stack, settlement). Unit tests exist per-component; the integrated runnable flow + harness is the blocker. | A working CIP-2 v3 economic stack + the Docker/e2e harness (cf. COW-1344). |
| **COW-1341** | Example: 32-cowbot | node `examples/gallery/cowbot` | F | Relocated to `examples/gallery/cowbot`, deliberately in `NON_DEFAULT_SWEEP_EXAMPLES`; its `local-smoke.sh` **requires gateway/relay + LLM prerequisites** that aren't available locally, so it can't be verified green here. | A reachable gateway/relay + LLM endpoint (and the harness from COW-1344). |
| **COW-1344** | Maintain Docker example harness | node tooling / infra | F | "Bring up the required validator/runner topology from a clean checkout" with **private-dependency access** and **multivalidator + runner-enabled stacks**. Blocked on private dep access + a multi-node topology that isn't provisionable in this environment. | Private-dep credentials in CI/dev + a provisionable multivalidator/runner topology. |
| **COW-957** | TEE attestation verification pipeline | node (`execution/nitro.rs`, `cbss.rs`) + runner | G | **Premise is stale**: the issue says "0x05 is a stub with no verification logic", but `execution/src/nitro.rs`, `cbss.rs`, `cli/commands_tee.rs`, and TEE paths in dispatcher/system_instruction now exist (CIP-23 v3 TEE work landed). The *remaining* work — full SGX/SEV-SNP/TDX quote parsers + on-chain certificate-chain verification + pinned-measurement governance — is a **large multi-vendor attestation feature**, not a discrete fix, and the ticket needs re-scoping first. | Re-scope against current code; then implement the remaining vendor parsers + on-chain cert-chain (sizable, needs TEE hardware/fixtures). |
| **COW-962** | Dispute window: challenge/evidence/re-verify | node (`runner/verifier.rs`) | G | `dispute_window_blocks` exists in config but there is **no on-chain handler**. Building it = a new system instruction `(job_id, evidence, challenger_bond)` + fresh-committee re-selection + re-run-and-compare + slash distribution + bond refund. A **substantial CIP-2 protocol feature**, not a small fix. | Design + implement the dispute protocol (committee re-selection, evidence format, slash-distribution wiring). |

---

## Not blocked — actionable candidate

| Issue | Title | Area | Assessment |
|-------|-------|------|------------|
| **COW-1236** | Cross-system-actor reentrancy / call-graph integration tests | node `execution/` | **Appears actionable.** The pieces (job dispatcher, result verifier, treasury credit, reentrancy guard) already exist in `execution/`; this asks for an integration test of the Runner-Registry → Dispatcher → Verifier → Treasury chain asserting per-step state-root deltas and no reentrancy. That is a test-authoring task on existing code (same shape as the COW-2275 / COW-1664 test work), with no external prerequisite. Candidate to pick up next. Needs a premise check that the full flow can be driven in the execution test harness. |

---

## Summary by category

- **A — code not in workspace (4):** COW-508, 513, 514, 515 — all AWS API-Gateway / Tailscale / Terraform infra; nothing to edit here.
- **B — rollout tracker (1):** COW-2265 — coordinate at mainnet bring-up.
- **C — undecided decision (2):** COW-2266 (param drift ruling), COW-1265 (allocation + vesting sign-off).
- **D — needs design (2):** COW-137 (access-list), COW-166 (compact-block wire format; also E).
- **E — premature (1, +166):** COW-1274.
- **F — external prerequisites (3):** COW-1308, 1341, 1344 — gateway/relay/runner/LLM/multivalidator stacks.
- **G — large feature / stale premise (2):** COW-957 (TEE; premise stale), COW-962 (dispute protocol).

**Net:** of the 15 blocked, only **COW-957** has a materially *stale* premise (TEE is largely built); the rest are genuinely blocked on a decision (C), a design (D), an absent repo (A), a future condition (B/E), or an external stack (F). **COW-1236** is the one currently-fixable item.
