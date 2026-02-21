# Client Alignment Analysis: Bridging the Development-Expectation Gap

> **Date**: 2026-02-19
> **Purpose**: Synthesize findings from all available source materials to identify the specific gap between what the team is building and what the client expects, and propose concrete actions to close it.
> **Source Materials Analyzed**:
> - Slack: `devnet_eng.md`, `Charles_DePue_patrick_Tony.md`
> - Notion: Devnet Milestone, Developer Experience Situational Awareness, Deployment Strategy
> - Meeting Minutes: 3 internal meetings (2/11 and 2/18)
> - Whitepaper: `20260216_cowboy_whitepaper.md`
> - Existing Strategy: `20260219_client_followup_strategy.md`

---

## Executive Summary

**The core misalignment is architectural**: The team has invested heavily in deep infrastructure (42 Rust crates covering consensus, execution, VM, and off-chain compute), while the client's priorities center on the **developer-facing surface area** — CLI tooling, SDK polish, documentation, local dev environment, and UI dashboards.

Both sides have valid perspectives. The team built the hard, foundational pieces first (correct engineering order). The client needs visible, usable tools to onboard external developers (correct market order). The gap is not about missing work — it's about **which layer** the work has been applied to.

**Three critical technical discrepancies** also exist between the whitepaper and the implementation that must be proactively disclosed to the client before they discover them independently.

---

## 1. The Perception Gap — Why It Exists

### What the Team Has Built (Bottom-Up)

From the codebase across three repositories (node, pvm, runner):

| Layer | Status | Details |
|-------|--------|---------|
| **Consensus Engine** | ✅ Complete | Simplex BFT, BLS12-381 signatures, 1s block time, multi-node |
| **Execution Engine** | ✅ Complete | Dual-metered gas (Cycles + Cells), deferred TX, mempool, block storage |
| **Actor Model** | ✅ Complete | 5 system actors (Registry, Dispatcher, Verifier, SecretsMgr, TEEVerifier), CREATE2 addresses |
| **PVM** | ✅ Complete | Deterministic Python VM, SoftFloat, gas metering, import guard, checkpointing |
| **Runner Network** | ✅ Complete | 3 executor types (LLM/HTTP/MCP), distributed consensus, N-of-M verification, TEE runtime, rate cards |
| **RPC/API** | ✅ Complete | Axum REST + OpenAPI/Swagger, full endpoint coverage |
| **CLI (basic)** | ✅ Partial | deploy, send, query, runner mgmt, job lifecycle, transfer |

### What the Client Expects (Top-Down)

From the Devnet Milestone and DevEx Situational Awareness documents:

| Layer | Client Priority | Current Status |
|-------|----------------|----------------|
| **CLI Tooling** (`init`, `dev`, `test`, `logs`) | P0 | ❌ Not implemented |
| **SDK** (type stubs, decorators, PyPI/npm) | P0 | ⚠️ Minimal skeleton |
| **Error Experience** (4-part format, error map) | P0 | ❌ Not implemented |
| **Documentation** (Getting Started, API docs) | P0 | ❌ Not implemented |
| **Local Dev Environment** | P0→P1 | ❌ Not implemented (pvm-simulator exists as foundation) |
| **Faucet** | P0 | ❌ Not implemented |
| **Cowchat/Explorer/Status Page** | P0 | ❌ Not implemented |
| **Wallet Connect** | Listed | ❌ Not implemented |

### The Visual Gap

```
CLIENT'S FOCUS                          TEAM'S FOCUS
─────────────                          ────────────

  ┌─────────────────────┐
  │  UI Layer            │ ← Client expects this    ← Team: ❌ not started
  │  (Cowchat, Explorer) │
  ├─────────────────────┤
  │  DX Layer            │ ← Client's top priority  ← Team: ⚠️ minimal
  │  (CLI, SDK, Docs)    │
  ├─────────────────────┤
  │  Infra Layer         │ ← Client assumes done    ← Team: ⚠️ partial
  │  (Faucet, Monitoring)│
  ╞═════════════════════╡
  │  Core Protocol       │ ← Client doesn't see     ← Team: ✅ deep work here
  │  (42 Rust Crates)    │
  └─────────────────────┘
```

**Key Insight**: The client's Devnet Milestone document lists 11 Protocol items, 5 Cowchat items, and 17+ DevEx items. The team has strong coverage on Protocol core but almost zero coverage on Cowchat and DevEx tooling — which represent **~65% of the client's checklist by item count**.

---

## 2. Detailed Gap Analysis by Client Document

### 2.1 Devnet Milestone — Protocol (11 items)

| # | Client Requirement | Status | Gap |
|---|-------------------|--------|-----|
| 1 | Multi-node support w/ Simplex, leader election | ✅ Done | None |
| 2 | Public RPC/API | ✅ Done | Confirm public exposure strategy |
| 3 | Public testnet RPC endpoint + Status Page | ⚠️ Partial | RPC endpoint deployed (`validator-01.dev.cowboylabs.net`), **no Status Page** |
| 4 | Testnet faucet | ❌ | New build required |
| 5 | CIP 1-6 core protocol | ⚠️ Mostly done | SDK surface needs work |
| 6 | CIP-7 (streaming) | ⚠️ In review | Charles rewrote doc; Tony reviewing |
| 7 | CIP-20 (tokens) | ❌ | Tony asked "Where's CIP-21?" — scope unclear |
| 8 | Genesis + chain config freeze | ⚠️ | Config exists but not frozen |
| 9 | Basic chain monitoring + alerting | ❌ | New build required |
| 10 | Snapshots + restore runbook | ❌ | New documentation/tooling required |
| 11 | Incident runbook | ❌ | New documentation required |

**Protocol Score**: 2/11 fully complete, 4/11 partial, 5/11 not started

### 2.2 Devnet Milestone — Cowchat (5 items)

| # | Client Requirement | Status |
|---|-------------------|--------|
| 1 | Simple v0 dashboard + public block explorer | ❌ |
| 2 | Network status panel | ❌ |
| 3 | Builder with lightweight node UI to create actors | ❌ |
| 4 | Wallet connect | ❌ |
| 5 | Faucet request UI + response state | ❌ |

**Cowchat Score**: 0/5 complete

### 2.3 Developer Experience — P0 Items (17 items)

| # | Client Requirement | Status | Notes |
|---|-------------------|--------|-------|
| 1 | `cowboy init` (scaffolding) | ❌ | CLI only has deploy/send/query |
| 2 | `cowboy dev` (local dev server) | ❌ | pvm-simulator could serve as foundation |
| 3 | `cowboy test` | ❌ | |
| 4 | `cowboy actor deploy` | ✅ | Verified end-to-end by Martin |
| 5 | `cowboy actor logs` | ❌ | |
| 6 | `cowboy inspect` | ⚠️ | Inspector crate exists; needs CLI wrapping |
| 7 | SDK type annotations + .pyi stubs | ⚠️ | pvm_sdk has basic modules |
| 8 | Ergonomic decorators (`@actor`, `@timer`) | ⚠️ | Basic implementation exists |
| 9 | 4-part error format | ❌ | |
| 10 | Common error mapping table | ❌ | |
| 11 | Getting Started guide | ❌ | Only deployment guide exists |
| 12 | pvm_host API docs | ❌ | |
| 13 | Shell script install / prebuilt binaries | ❌ | |
| 14 | AI Context (SKILL.md, .cursorrules) | ❌ | P1, can follow later |
| 15 | `cowboy wallet create` | ❌ | Only `wallet address` exists |
| 16 | Account balance/nonce/info queries | ⚠️ | CLI code exists but prints "not yet implemented" |
| 17 | SDK on PyPI/npm | ❌ | |

**DevEx P0 Score**: 1/17 fully complete, 4/17 partial, 12/17 not started

### 2.4 Aggregated Gap Score

```
                    Complete    Partial    Not Started    Total
Protocol:              2          4            5           11
Cowchat:               0          0            5            5
DevEx P0:              1          4           12           17
─────────────────────────────────────────────────────────────
TOTAL:                 3          8           22           33
                      (9%)      (24%)        (67%)
```

**67% of client-listed items have not been started.**

---

## 3. Critical Technical Discrepancies (Must Disclose Proactively)

These emerged from cross-referencing the whitepaper with meeting discussions and code analysis. **All three must be communicated to the client before they discover them independently.**

### 3.1 No Proof-of-Stake (PoS)

| Aspect | Whitepaper Says | Current Implementation |
|--------|----------------|----------------------|
| Consensus | "Simplex BFT consensus with proof-of-stake" | Simplex BFT with f+1 voting, **no stake weighting** |
| Validator selection | Stake-weighted | Equal-weight — all validators have same voting power |
| Impact | Client may assume PoS is live | Must clarify this is not implemented yet |

**Source**: Meeting 3 (2/18), extensive discussion about PoS absence.

### 3.2 Signature Scheme Mismatch (ED25519 vs secp256k1)

| Aspect | Whitepaper Says | Current Implementation |
|--------|----------------|----------------------|
| Signature scheme | secp256k1 (Ethereum-compatible) | ED25519 (32-byte, not ETH-compatible) |
| Address format | "Cowboy adopts Ethereum's 20-byte address model" | ED25519-based addresses |
| Impact | **Ethereum wallet compatibility is broken** — MetaMask, wagmi, etc. won't work |

**Source**: Meeting 3 (2/18), team noted this is a "core concern of the client's direction." Research needed on whether migration is feasible.

### 3.3 Whitepaper vs Code Feature Gaps

| Whitepaper Feature | Code Status | Notes |
|-------------------|-------------|-------|
| State rent & eviction | ❌ Not implemented | Mentioned in whitepaper §State Rent |
| Stake delegation/slashing | ❌ Not implemented | Depends on PoS |
| Fungible token standard (CIP-20) | ❌ Not implemented | Client asking about it |
| Storage pricing model (Cells) | ⚠️ Partial | Cycles metering works, Cells TBD |

---

## 4. Unreported Strengths (Exceed Client Expectations)

These are implemented features **not listed in the client's milestone documents** that should be highlighted as value-add:

| Feature | Repository | Significance |
|---------|-----------|-------------|
| 5 System Actors | node | Registry, Dispatcher, Verifier, SecretsMgr, TEEVerifier — client unaware |
| Runner Verify mechanism | runner | On-chain replay verification of off-chain results |
| Runner distributed consensus | runner | Cross-runner data sync and result aggregation |
| Deferred TX mechanism | node | Cross-block async execution with callback chains |
| Dual-Metered Gas (Cycles + Cells) | node | More sophisticated than typical single-gas models |
| CREATE2 deterministic addresses | node | Predictable actor deployment addresses |
| Runner Rate Cards | runner | Pricing/quoting mechanism for off-chain compute |
| Runner CLI commands | CLI | `runner get/list/register`, `job get/status/runners/results/verified/submit` |
| Transfer command | CLI | Native token transfers |

---

## 5. Root Causes of Misalignment

Based on meeting transcripts and Slack analysis, five root causes:

1. **Different planning horizons**: The team works bottom-up (protocol → DX), the client plans top-down (DX → protocol). Neither checked whether the other's assumptions held.

2. **Documentation gap**: The team built significant infrastructure without corresponding client-visible documentation. The client has no way to know what exists unless told.

3. **Public vs Private Devnet confusion**: The client expects a public Devnet; the team has been building a private Devnet. The 2/11 meeting defined Private Devnet (Feb-Mar) → Public Devnet (end of March), but this timeline was not clearly communicated to the client.

4. **Planning document quality concerns**: The team perceives the client's planning documents as "hastily created" (Meeting 2), leading to dismissiveness rather than proactive engagement. Meanwhile, the client perceives silence as lack of progress.

5. **Communication channel fragmentation**: Work is tracked across Google Sheets, Notion, Slack, and GitHub without a single source of truth. Tony explicitly asked about missing CIPs in Slack without getting a clear response.

---

## 6. Recommended Action Plan

### Immediate (This Week)

| # | Action | Owner Suggestion | Purpose |
|---|--------|-----------------|---------|
| 1 | Send Architecture Overview (EN) to client | Team Lead | Demonstrate infrastructure depth; show 42 crates, full consensus→execution→VM→runner pipeline |
| 2 | Post whitepaper-vs-code discrepancy analysis to Slack (EN) | Tech Lead | Proactively disclose PoS absence, ED25519 issue, state rent gap |
| 3 | Reply to Tony's CIP-7 review with substantive feedback | Charles/Tony liaison | Shows engagement; CIP-7 has been "in review" too long |
| 4 | Reply to Patrick's product ideas in Slack (brief + links) | PM | Acknowledge XMTP, Agent Tokens, Cowboy Gold; defer to docs |
| 5 | Freeze Genesis + chain config for Devnet | Infra | Quick win; client expects this |

### Short-Term (Phase 1: Private Devnet close-out by March 8)

| # | Action | Details |
|---|--------|---------|
| 1 | CIP-2 update (incorporate Runner concepts) | Meeting 2/18 decided: update CIP-2 instead of creating CIP-8 |
| 2 | Write Snapshots + restore runbook | Operational documentation |
| 3 | Write Incident runbook | Operational documentation |
| 4 | Create CI/CD test guidance document | For Martin; deployment validation |
| 5 | Add SDK status comments | Explain why partial/minimal in code comments |
| 6 | Deliver architecture visualization (non-ASCII, professional) | For Tony to share with broader client team |
| 7 | Complete ED25519 → secp256k1 feasibility research | Determine if migration is needed/possible |

### Medium-Term (Phase 2: Public Devnet by March 31)

**DX Layer (highest priority)**:
- `cowboy init` (project scaffolding)
- `cowboy actor logs` (log retrieval from chain DB/indexer)
- `cowboy wallet create`
- Complete `account balance/nonce/info` implementation (currently stubs)
- Error messages: 4-part format (what/why/fix/link)
- Common error mapping table
- SDK full type annotations (PEP 484) + .pyi stubs
- SDK decorators (`@actor`, `@timer`, etc.)
- SDK published to PyPI/npm
- Getting Started documentation + example actors
- pvm_host API documentation
- SimulatedChain local dev environment (basic version) — **added per 2/18 meeting**

**UI Layer**:
- Cowchat Dashboard + Builder UI
- Block Explorer (basic, with network status panel)
- Testnet Faucet UI + request state
- Status Page
- Wallet Connect (basic integration)

**Protocol/Infra**:
- Testnet Faucet API
- Basic monitoring + alerting (block lag, RPC error rate, peer count)
- ED25519 → secp256k1 migration (if research confirms necessity)

### Explicitly Deferred (Not Phase 1 or 2)

Per meeting discussions, these are **not in scope** for the current two phases:
- `cowboy dev` (full version) / `cowboy test`
- Runner mocking / Block advancement
- State snapshot assertions
- Determinism checking (cross-platform)
- PoS implementation (depends on ED25519 research outcome)
- AI Context files (SKILL.md, .cursorrules) — after SDK completion

---

## 7. Communication Strategy

### Key Messages to Convey

1. **"The foundation is solid"** — 42 Rust crates, consensus→execution→VM→runner fully operational, Martin has deployed actors end-to-end on devnet.

2. **"The gap is in the developer experience layer, not the protocol"** — CLI commands like `init`/`dev`/`test`/`logs` are new surface features, not missing core functionality. The pvm-simulator already provides the technical foundation for `cowboy dev`.

3. **"We have a concrete sprint plan with weekly deliverables"** — Not vague promises but specific items with GitHub issues and regular demos.

4. **"We're proactively disclosing technical differences"** — PoS, signature scheme, whitepaper gaps. Transparency builds trust.

### What to Avoid

- ❌ Don't say "we've been doing the hard stuff" — sounds like an excuse
- ❌ Don't use code volume as a progress metric — client cares about usability
- ❌ Don't say "yes" to everything — clearly defer P2/P3 items with reasoning
- ❌ Don't write long Slack messages — short replies + document links

### Proposed Communication Cadence

- **Twice-weekly sync** (Tue/Thu, 30 min) with Tony + Martin
- **Bi-weekly demo**: Show latest working functionality to client
- **GitHub Issues as single source of truth**: All committed deliverables tracked publicly

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Client sees 67% "not started" and loses confidence | High | High | Lead with architecture overview + hidden strengths; frame DX as additive, not missing |
| ED25519→secp256k1 migration is infeasible | Medium | Critical | Research immediately; inform client of constraints early |
| Phase 2 scope overload (DX + UI + Infra in 3 weeks) | High | Medium | Prioritize DX over UI; Cowchat/Explorer can slip |
| Client changes scope mid-phase (Patrick's ideas) | Medium | Medium | Acknowledge ideas; explicitly defer to future phases |
| Team burnout from catch-up sprint | Medium | High | Realistic scoping; don't commit to everything |

---

## Appendix: Source Cross-Reference

| Finding | Source(s) |
|---------|----------|
| Public vs Private Devnet timeline | Meeting 1 (2/11), DevEx doc |
| PoS absence | Meeting 3 (2/18), Whitepaper §Consensus |
| ED25519 vs secp256k1 | Meeting 3 (2/18), Whitepaper §Account Management |
| Runner complexity underestimated by client | Meeting 2 (2/18), Whitepaper §Runners |
| Client planning docs "hastily created" | Meeting 2 (2/18) |
| Tony asking about CIP-21 | Slack: Charles_DePue_patrick_Tony.md |
| Martin devnet deployment verification | Slack: devnet_eng.md |
| SimulatedChain added to Phase 2 scope | Meeting 3 (2/18) — Tony confirmed |
| CIP-8 → CIP-2 update decision | Meeting 2 (2/18) |
| Demo apps narrowed to llm_chat + deferred_counter_demo | Meeting 2 (2/18) |
