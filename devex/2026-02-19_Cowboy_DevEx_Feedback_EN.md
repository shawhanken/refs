# Cowboy Development Update & DevEx Feedback

**Date**: February 19, 2026

---

Over the past six weeks, our team has been fully focused on the core development of the Cowboy chain (Node), PVM, and Runner network. The Python-based PVM and cross-block transaction execution approach have no precedent in the market — everything was built from scratch. All three core modules now have a solid foundation, and during the development process we also implemented several additional features for completeness (deferred transactions, CREATE2 address derivation, N-of-M result verification, TEE support, etc.). We also built two working demos to validate the code's effectiveness.

In fact, the core business flow of **a developer writing a Python Actor → deploying it to Devnet → executing calls → querying results** has already been repeatedly implemented and tested internally by our development team — the entire pipeline works end-to-end without issues. Our CLI already supports `actor deploy`, `actor execute`, `account balance/nonce/info`, `transaction get/status` and other complete workflows, and our RPC API provides 25+ endpoints covering all on-chain operations.

However, for external third-party developers, there is currently a lack of good interfaces, tools, and guided pathways to help them complete this flow smoothly. So our next priority is **how to present this proven capability to third-party developers through great tooling and interaction design** — including `cowboy init` for project scaffolding, SDK decorators to simplify code writing, friendly error messages for debugging, and getting-started documentation for onboarding.

We've compiled all currently implemented features into a separate **Architecture Overview** document for your reference.

---

## Item-by-Item Feedback on the DevEx Requirements List

We've carefully reviewed every message in Slack, as well as the Devnet Milestone, Developer Experience planning documents, and all product discussions on Notion. We've cross-referenced each requirement against our current implementation, and below is our item-by-item feedback on the DevEx checklist in the Devnet Milestone.

> **Note**: The priority assessments and timelines below are our initial recommendations based on our current understanding — **they are absolutely open for discussion and adjustment**. If there's anything we've misunderstood or overlooked, please don't hesitate to let us know and we'll correct it right away.

### CLI

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 1 | Shell script to install from GitHub | 📋 To Confirm | Need to confirm distribution method and target platforms |
| 2 | Pre-built CLI binary distribution | 📋 To Confirm | Need to confirm distribution channel (GitHub Release? Homebrew?) |
| 3 | `cowboy init` (scaffolding with templates) | 🔜 Planned | We've assessed this and believe it's feasible — will support project template generation |
| 4 | `cowboy dev` (local development server) | ⏸️ Next Milestone | Local dev environment requires maintaining a simulated chain. Given the fast iteration pace of our chain, maintaining two environments is costly. We plan to provide local dev capability via SimulatedChain in the next milestone |
| 5 | `cowboy test` (testing against simulated PVM) | ⏸️ Next Milestone | Depends on the local dev environment; requires SimulatedChain as a foundation. Planned for next milestone |
| 6 | `cowboy actor deploy` | ✅ Implemented | Supports deploying Python Actors to Devnet, including CREATE2 address derivation, gas configuration, etc. |
| 7 | `cowboy actor logs` | 🔜 Planned | We've assessed this and believe it's feasible. Logs will be stored in the chain's database, queried via RPC through CLI |
| 8 | `cowboy wallet` create | 📋 To Confirm | Listed in the Devnet Milestone — could you clarify what specific wallet features are needed? |
| 9 | Account balance/nonce/info | ✅ Implemented | CLI already supports `account balance`, `account nonce`, and `account info` commands |

### SDK

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 10 | Full type annotations (PEP 484) + `.pyi` stubs | 🔜 Planned | PVM already has pvm_sdk modules (actor, runner, continuation, etc. — 10 modules). Need to add complete type annotations and .pyi stubs |
| 11 | Ergonomic decorators (`@actor`, `@runner.continuation`, `@timer`) | 🔜 Planned | PVM's underlying logic already supports these features. Currently implemented via hardcoding in Actor code — need to wrap as decorators in the SDK |

### Error Messages

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 12 | Four-part error format (what, why, fix, link) | 🔜 Planned | We agree with this direction — it will also improve our own debugging efficiency |
| 13 | Common error mapping table in PVM | 🔜 Planned | Partial error mapping exists; needs expansion to cover more common scenarios |

### AI Context

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 14 | Skills for Claude/Codex/OpenClaw | ⏸️ After SDK | We think this is a great idea, but after internal assessment we believe it should be developed after the SDK is finalized — otherwise Skills would need repeated updates as the SDK changes |
| 15 | `.cursorrules` in `cowboy init` output | ⏸️ After SDK | Same as above — depends on SDK stability |
| 16 | `llms.txt` at docs domain root | ⏸️ After SDK | Same as above |

### Other

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 17 | Initial getting started guide + example actors | 🔜 Partially Ready | We currently have 2 working demos (llm_chat, deferred_counter_demo). The getting started guide needs to be written — could you share your expectations on depth and format? |
| 18 | pvm_host API docs | 📋 To Confirm | Need to confirm the target audience and scope of the documentation |
| 19 | SDK on PyPI/npm | 📋 To Confirm | Can be published once SDK packaging is complete — need to confirm package name and versioning strategy |
| 20 | Core examples compile | ⚠️ Partially Ready | Currently maintaining llm_chat and deferred_counter_demo as the two core examples |

### Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented — already working in current codebase |
| 🔜 | Planned — assessed as feasible, will be developed |
| ⏸️ | Deferred — pushed to next milestone or pending dependency |
| 📋 | To Confirm — need your input to clarify scope or requirements |
| ⚠️ | Partially Ready — some work done, needs completion |

---

## Technical Questions for Discussion

During our review, we identified several technical questions that need to be discussed and confirmed together:

- **Signature scheme**: The whitepaper specifies secp256k1 (Ethereum-compatible), but our current implementation uses ED25519. If Ethereum compatibility is a hard requirement, we need to evaluate a migration plan.

- **Feature prioritization**: Some requirements have dependencies (e.g., AI Context depends on a stable SDK). We'd like to confirm the overall priority ordering with the team.


---

## Discussion on Target Use Cases

Lastly, we'd like to explore the core use case for the first version of Devnet after it goes live.

Based on our review of Slack discussions and Notion documents, we believe the current core use case is:

> **Enable a developer to set up their development environment from scratch in the shortest time possible, and successfully deploy and interact with an Actor on Devnet.**

In other words, a complete **Install → Initialize → Write → Deploy → Interact** end-to-end flow.

The good news is that our development team has already repeatedly run and validated this flow internally — writing an Actor, deploying it, calling it, querying results — the entire pipeline works without issues. The core question we need to solve next is: **how to present this proven capability to third-party developers through great tools, interfaces, and guided pathways**, so they can also get started quickly and complete the flow smoothly. This is the core direction of our DevEx work in the next phase.

If this understanding is accurate, we'll prioritize development around this use case to ensure every step of the flow works seamlessly.

We'd also love to learn whether there are other use cases or business goals you're particularly focused on beyond this. For example:

- Are there specific types of Actors that need priority support? (e.g., quantitative trading, oracle, AI agent, etc.)
- Are there external integrations that should be prioritized? (e.g., wallet integration, OpenClaw integration, etc.)
- What is the target audience for Devnet after launch? (Internal testing? Investor demos? Developer public beta?)

Understanding these scenarios will help us align our development direction more precisely and prioritize around the use cases that truly matter.

---

Looking forward to your feedback! 
