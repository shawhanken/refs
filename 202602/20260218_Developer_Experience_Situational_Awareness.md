# Developer Experience Situational Awareness

- [\~\~Skill.md](http://skill.md/) in domain\~\~  
- ~~CLI docs? (modal?)1~~  
- ~~Docs domain~~  
  - ~~Can’t be scraped~~  
- ~~Cursor/VS Code Plugin~~  
- ~~Bad tests~~  
- ~~DNS how does it work w cowboy~~  
- ~~On chain privacy? what’s our story short and long term? Zama “is going to win this” \- research~~

---

## Executive Summary

Cowboy asks Python developers to adopt a novel programming model: actor-based execution, message-passing continuations, deterministic sandboxing, and dual-metered gas. The protocol is powerful, but the distance from intent to deployed actor is too large. This document lays out every piece of developer-facing infrastructure needed to close that gap, organized into four phases, with clear priority.

The target experience: a developer with Python experience and basic blockchain familiarity should go from zero to a deployed, tested actor on devnet in under 30 minutes, and to mainnet in under an hour.

---

## Priority Levels

| Priority | Label | Meaning |
| :---- | :---- | :---- |
| **P0** | Must-have for launch | Without this, developers cannot build or will churn immediately. |
| **P1** | Should-have for launch | Significantly improves adoption velocity. Painful without, but workarounds exist. |
| **P2** | Fast follow (M1–M2 post-launch) | Differentiator that separates Cowboy from other chains. Not blocking. |
| **P3** | Future (M3+) | Nice to have. Build when the ecosystem demands it. |

---

## Phase 1: Foundation

The tools a developer touches in their first hour. Everything here must exist and be polished before public launch.

### 1.1 The CLI (`cowboy`)

A single binary that is the primary interface between a developer and the Cowboy network. Modeled on Modal's CLI with Vercel's zero-config philosophy.

### Core Commands

| Command | Priority | Description |
| :---- | :---- | :---- |
| `cowboy init` | **P0** | Scaffold a new actor project. Prompts for archetype (arb bot, oracle, watcher, trading bot, Watchtower provider, Wrangler market). Generates a working, deployable actor with `pyproject.toml`, tests, and a README. |
| `cowboy dev` | **P0** | Local development server. Spins up a local PVM, simulates block production on a clock or manual advance, mocks Runner responses, enables hot-reload on file changes. This is where developers spend 90% of their time. |
| `cowboy test` | **P0** | Run test suite against a simulated PVM. Includes determinism checking (cross-platform comparison), message sequence fuzzing, and state snapshot assertions. |
| `cowboy actor deploy` | **P0** | Deploy an actor to devnet (default) or mainnet (`--mainnet` flag). Shows cost estimate and pre-deploy checklist before confirming. Returns actor address. |
| `cowboy actor logs` | **P0** | Tail actor logs in real time. Filter by handler, log level, or time range. Show timer executions, Runner job results, state changes, and errors. |
| `cowboy inspect` | **P0** | Inspect a live actor's state. Show handler names, storage contents, active timers, pending Runner jobs, and recent transactions. |
| `cowboy upgrade` | **P0** | Deploy a new version of an actor. Handles state migration, reference updates, and provides easy rollback. |
| `cowboy actor send` | **P1** | Send a message to an actor on devnet/mainnet. Interactive REPL mode for rapid testing: `cowboy send <addr> <handler> <payload>`. |
| `cowboy secrets` | **P1** | Manage secrets stored via the Secrets Manager (0x08). Subcommands: `set`, `get`, `list`, `delete`. Handles encryption transparently. |
| `cowboy cost` | **P1** | Estimate running costs before deploy. Analyzes timer frequency, Runner job specs, storage usage, and gas. Outputs CBY/hour, CBY/day, CBY/month with runway estimate based on wallet balance. |
| `cowboy trace` | **P2** | Trace the execution path of a transaction or message chain across blocks. Shows message flow with state diffs at each step. |
| `cowboy watch` | **P2** | Watch mode for live actors. Combines logs \+ cost ticker \+ timer countdown \+ Runner job status in a single TUI dashboard. |

### CLI Design Principles

- **Zero-config defaults:** Devnet is always the default target. Mainnet requires an explicit flag. No config files needed to get started.  
- **Progressive disclosure:** `cowboy init` generates the simplest possible actor. Advanced features (entitlements, GBA, verification modes) are documented but never forced.  
- **Rich error output:** Every CLI error includes: what went wrong, why, what to do instead, and a docs link. Modeled on Rust's compiler errors.  
- **Machine-readable:** `-json` flag on every command for scripting and CI integration.

---

### 1.2 Local Development Environment

**Priority: P0**

The local dev environment is the most important piece of DX infrastructure. Without it, every iteration requires deploying to devnet, which destroys flow state and makes the experience feel like writing Solidity in 2017\.

### Requirements

- **Local PVM:** A lightweight, embeddable Python VM that enforces all determinism rules (module whitelist, softfloat math, `ordered_set`, fixed hash seed, no JIT, recursion limit, cycle metering).  
- **Block simulation:** Produce blocks on a configurable clock (default: 1s, matching mainnet) or manually via `cowboy dev advance`. Simulated block height, timestamp, basefees, and randomness beacon.  
- **Timer simulation:** Timers fire at their scheduled block heights. GBA is simulated with configurable congestion levels.  
- **Runner mocking:** Mock responses for LLM, HTTP, and compute jobs. Configurable via a `mocks.yaml` file or inline in tests. Support for simulating failures, timeouts, and N-of-M divergence.  
- **Hot reload:** File changes automatically redeploy the actor to the local chain. State is optionally preserved or reset.  
- **State inspector:** Built-in web UI or TUI that shows actor storage, mailbox contents, timer queue, and transaction history. Accessible at localhost during `cowboy dev`.  
- **Multi-actor:** Support multiple actors in a single local environment. Essential for testing actor-to-actor messaging, Watchtower subscriptions, and multi-actor workflows.

### Dev Environment Config (`cowboy.yaml`)

Minimal config file. Most fields optional with sensible defaults.

actors:

  \- path: ./my\_bot.py

    initial\_balance: 1000

mocks:

  runner:

    llm: ./mocks/llm\_responses.yaml

    http: ./mocks/api\_responses.yaml

chain:

  block\_time: 1s

  initial\_basefee\_cycle: 100

  initial\_basefee\_cell: 10

---

### 1.3 SDK & Language Tooling

**Priority: P0**

### `cowboy_sdk` Package

- Full type annotations (PEP 484\) for all public APIs. IDE autocomplete must work perfectly out of the box.  
- Ergonomic decorators: `@actor`, `@runner.continuation`, `@timer`, `@handler`.  
- Built-in helpers that compensate for PVM restrictions: `cowboy_sdk.vrf` (randomness), `cowboy_sdk.time` (block-based timestamps), `cowboy_sdk.math` (deterministic math).  
- Watchtower client: `watchtower.get()`, `watchtower.subscribe()`, `watchtower.unsubscribe()` as first-class SDK functions.  
- Storage utilities: typed storage wrappers, serialization helpers, migration scaffolding.  
- Correlation ID management: `generate_id()`, correlation tracking patterns as built-in helpers, not boilerplate every developer copies.

### Type Stubs & Inline Docs

- Ship `.pyi` stub files so type checkers (mypy, pyright, Pylance) understand the SDK even in restricted environments.  
- Every public function has a docstring with: description, parameters, return type, example usage, and a link to the full docs.  
- Common patterns (timeout handling, re-validation after continuation, idempotent handlers) documented as copy-pasteable recipes in the SDK docstrings themselves.

---

### 1.4 Testing Framework

**Priority: P0** — Bugs in actors mean lost money. This is not optional.

### Test Primitives

| Primitive | What It Does |
| :---- | :---- |
| `SimulatedChain` | In-memory chain with configurable parameters. Runs the actual PVM. Supports multiple actors. |
| `advance_blocks(n)` | Advance the chain by n blocks, firing any due timers and processing pending messages. |
| `send_message(actor, handler, payload)` | Send a message to an actor and execute the handler. Returns state diff and outbound messages. |
| `mock_runner(job_type, response)` | Register a canned Runner response. Supports conditional responses based on job spec fields. |
| `deliver_runner_result(correlation_id, result)` | Manually deliver a Runner result to an actor's callback handler. Useful for testing continuation flows. |
| `assert_storage(actor, key, value)` | Assert an actor's storage contains a specific key-value pair. |
| `snapshot()` | Capture the full chain state. Use for before/after comparisons. |
| `determinism_check()` | Run the actor on multiple simulated platforms (x86, ARM) and compare state transitions, cycle counts, and outputs. |
| `fuzz_messages(actor, n, invariants)` | Generate n random message sequences and verify invariants hold after each. Property-based testing for actors. |

### CI Integration

- `cowboy test` outputs JUnit XML for CI systems (GitHub Actions, CircleCI, etc.).  
- `cowboy test --determinism` runs cross-platform determinism checks as part of CI.  
- Pre-deploy hook: `cowboy deploy` refuses to deploy if tests fail (overridable with `-force`).

---

### 1.5 Error Messages & Diagnostics

**Priority: P0**

The PVM has an unusually large surface area of forbidden operations. Every `DeterminismError`, `ImportError`, and `RuntimeError` a developer encounters is a potential churn moment. Error quality is a retention lever.

### Error Message Standard

Every error emitted by the PVM, CLI, or SDK must include four components:

1. **What happened:** "You used `random.randint()` on line 42 of `trading_bot.py`."  
2. **Why it's not allowed:** "The PVM forbids non-deterministic operations to ensure all nodes produce identical results."  
3. **What to do instead:** "Use `cowboy_sdk.vrf.randint()` which derives randomness from the chain's VRF beacon."  
4. **Where to learn more:** "See: docs.cowboy.lat/determinism/randomness"

### Common Error Mapping (Ship with PVM)

| Developer Writes | PVM Error | Suggested Fix |
| :---- | :---- | :---- |
| `import os` | ImportError: os not in whitelist | Use `cowboy_sdk` equivalents |
| `random.randint()` | DeterminismError | Use `cowboy_sdk.vrf.randint()` |
| `time.time()` | DeterminismError | Use `current_block().timestamp` |
| `import numpy` | ImportError: C extensions forbidden | Use `math` module (deterministic impl) |
| `set({1, 2, 3})` | (Silent: becomes `ordered_set`) | Document behavior, warn in linter |
| `import pickle` | ImportError: pickle forbidden | Use `cowboy_sdk` CBOR serialization |
| `eval("code")` | DeterminismError | No alternative — explain why |
| `x is "hello"` | Warning: identity on strings | Use `==` for comparisons |

---

## Phase 2: Acceleration

Tools that multiply developer velocity and make Cowboy competitive with the best developer platforms in any ecosystem.

### 2.1 PVM Linter & VS Code Extension

**Priority: P1**

Catch PVM violations before deploy, not at runtime. This is more valuable than most tests because it prevents entire categories of errors at the source.

### Linter Rules

- **Forbidden imports:** Flag any import outside the module whitelist.  
- **Forbidden builtins:** Flag `eval()`, `exec()`, `compile()`, `__import__()`.  
- **Non-deterministic patterns:** Flag `time.time()`, `random.*`, `os.*`, `socket.*`, `subprocess.*`.  
- **Identity comparisons:** Warn on `is` for strings and numbers. Suggest `==`.  
- **Recursion depth:** Warn when static analysis suggests possible deep recursion (\>256).  
- **Storage size:** Estimate storage usage and warn if approaching the 1 MiB default quota.  
- **Cycle estimation:** Static analysis of loop bounds and function calls to estimate cycle consumption per handler.

### VS Code / Cursor Extension Features

- **Real-time diagnostics:** Red squiggles under PVM violations with quickfix suggestions.  
- **Go-to-definition:** Navigate to `cowboy_sdk` source and type stubs.  
- **Inline cost estimates:** Show estimated cycles/cells per handler as CodeLens annotations.  
- **Actor graph view:** Visualize message flow between actors, triggers, conditions, and actions.  
- **Deploy from editor:** Command palette integration for `cowboy deploy`, `cowboy logs`, `cowboy send`.  
- **Snippet library:** Insertable patterns for common tasks (timeout handling, re-validation, Watchtower subscription, etc.).

---

### 2.2 AI-Assisted Development Context

**Priority: P1**

AI coding assistants are a force multiplier. If Claude, Cursor, or Copilot can write correct Cowboy actors, the effective developer community is 10x larger than just the people who've read the docs.

### Context Layer Stack

| Layer | Target | Content |
| :---- | :---- | :---- |
| `SKILL.md` | Claude / Cowork | Full SDK reference, PVM restrictions, common patterns, verification modes. Hosted at cowboy.lat domain. Updated from the same source as docs. |
| `.cursorrules` | Cursor IDE | Project-level rules file. Included in `cowboy init` output. Covers PVM restrictions, SDK patterns, and common mistakes. |
| `llms.txt` | All AI assistants | Hosted at `docs.cowboy.lat/llms.txt`. Structured summary of the Cowboy programming model for any AI tool that supports the convention. |
| MCP Server | Claude Code / IDEs | A Model Context Protocol server that can query live docs, look up SDK methods, and validate actor code. The richest integration. |
| Snippet Registry | All | A searchable registry of working actor patterns (not just snippets — full, tested examples). AI tools can pull from this when generating code. |

### Content Generation Pipeline

- All AI context artifacts are generated from the same source: the SDK docstrings \+ docs Markdown.  
- CI step: when docs or SDK changes ship, regenerate SKILL.md, `.cursorrules`, and `llms.txt` automatically.  
- Version the AI context: when the SDK changes, the AI context changes. Stale context is worse than no context.

---

### 2.3 Templates & Starter Projects

**Priority: P1**

Every template must be a working, deployable actor, not a skeleton full of TODOs. The goal: `cowboy init` → `cowboy dev` → see something working → modify → deploy. Under 10 minutes.

### Template Catalog

| Template | What It Does | Demonstrates |
| :---- | :---- | :---- |
| `minimal` | Bare-bones actor with one handler. The Hello World. | `@actor`, storage, messages, deployment |
| `arb-bot` | Monitors price differentials across two Watchtower feeds. Executes swaps when spread exceeds threshold. | Timers, Watchtower pull, conditions, cost optimization |
| `trading-bot` | Subscribes to price feeds, runs LLM analysis via Runner, executes trades based on signals. | Push subscriptions, Runner continuation, re-validation |
| `oracle-provider` | A Watchtower provider that fetches from a REST API and publishes to the registry. | `WatchtowerProvider` base class, HTTP jobs, verification config |
| `watcher` | Monitors an on-chain condition and sends alerts via messages to other actors. | Timer-based monitoring, actor-to-actor messaging |
| `prediction-market` | A Wrangler market with LLM resolution, Watchtower data source, and betting logic. | Multi-actor system, off-chain verification, economic design |

---

### 2.4 Documentation Site

**Priority: P1**

### Information Architecture

- **Getting Started:** Install → Init → Dev → Deploy. One page, runnable end to end. Target: 10 minutes.  
- **Concepts:** The actor model, message passing, timers, Runners, Watchtower, Cycles/Cells, state rent. Explain the why, not just the how.  
- **Guides:** Task-oriented walkthroughs. "How to call an LLM from an actor," "How to set up a price feed," "How to handle timeouts."  
- **SDK Reference:** Auto-generated from docstrings. Every function, every type, every decorator.  
- **PVM Reference:** The module whitelist, determinism rules, forbidden operations, metering tables. The stuff developers will bookmark.  
- **Examples:** Full, working actors with line-by-line annotations. Pulled from the template catalog and kept in sync.  
- **Architecture:** The whitepaper content, restructured for developers who want to understand the protocol deeply.

### Anti-Scraping Strategy

The tension: you want AI tools to help developers write Cowboy code, but you don't want competitors scraping your docs to clone the developer surface.

**Recommendation:** Make docs public and crawlable. Use the SKILL.md / MCP / llms.txt stack to provide better-than-scraped context to AI tools. The developers who find Cowboy through search or AI are the ones you want. The protocol itself (the whitepaper) is the moat, not the docs site.

If anti-scraping is still required: implement rate limiting and bot detection on the docs domain, but serve clean HTML for search engines. Block aggressive crawlers, not legitimate indexing.

---

## Phase 3: Ecosystem

Tools that support a growing developer community and enable more sophisticated use cases.

### 3.1 Observability & Debugging

**Priority: P2**

### Actor Dashboard (in Cowchat)

- **Live state viewer:** Browse actor storage key-value pairs in real time.  
- **Timer timeline:** Visualize scheduled, executing, and completed timers on a block-height axis.  
- **Runner job tracker:** Show job submission, runner selection, execution, result delivery, and payment for each off-chain job.  
- **Message trace:** Follow a message chain across actors and blocks. Click to expand state diffs at each step.  
- **Cost breakdown:** Real-time spend by category (timers, Runner jobs, gas, storage rent). Trend over time.

### CLI Observability

- **`cowboy logs --follow`:** Tail logs in real time. Filter by handler, severity, or keyword.  
- **`cowboy trace <tx_hash>`:** Show the full execution trace of a transaction, including cross-block continuations.  
- **`cowboy status <actor_address>`:** Snapshot of actor health: balance, storage usage, active timers, recent errors, estimated runway.

---

### 3.2 Versioning, Upgrades & Rollback

**Priority: P2**

Deploying an update to a live actor is the scariest thing a developer does on any blockchain. Cowboy needs to make it safe.

### Upgrade Flow

1. **Diff:** `cowboy upgrade --dry-run` shows a code diff \+ estimated impact (new handlers, removed handlers, storage schema changes).  
2. **Migrate:** If storage schema changed, run a migration function that transforms old state to new state. The CLI generates a migration stub from the schema diff.  
3. **Deploy to devnet:** Upgrade deploys to devnet first by default. Run the test suite against the upgraded actor with migrated state.  
4. **Deploy to mainnet:** `cowboy upgrade --mainnet`. Shows the pre-deploy checklist: tests passed, migration validated, cost estimate, wallet funded.  
5. **Rollback:** `cowboy rollback` reverts to the previous version. State migration is reversed if reversible; otherwise, restores from the pre-upgrade snapshot.

### Version History

- Every deployed version is recorded on-chain (code hash, block height, deployer).  
- `cowboy versions <actor_address>` shows the full history with diffs between versions.  
- Cowchat dashboard shows version timeline with annotations for each upgrade.

---

### 3.3 Frontend SDK (JavaScript / TypeScript)

**Priority: P2**

The ethers.js / viem equivalent for Cowboy. Without it, Cowchat is the only frontend and developers can't build custom UIs for their actors.

### Core Capabilities

- Connect wallet (secp256k1, shared with Ethereum).  
- Read actor storage and query state.  
- Build, sign, and submit transactions.  
- Subscribe to actor events and messages (WebSocket).  
- Watchtower feed queries from the browser.  
- TypeScript-first with full type safety. Auto-generate types from actor interface definitions.

---

### 3.4 Actor Interface Definitions

**Priority: P2**

If actors communicate via messages, other developers need to know what messages an actor accepts. This is the ABI equivalent.

- Auto-generate interface definitions from actor code (handler names, message schemas, storage layout).  
- `cowboy inspect <actor_address>` displays the interface for any deployed actor.  
- Publish interfaces to an on-chain registry so actors can discover each other's capabilities.  
- Import interfaces in code: `from cowboy_sdk import interface; bot = interface("0x...")` enables typed message construction.

---

## Phase 4: Scale

Long-term investments that compound as the ecosystem grows.

### 4.1 Reusable Component Registry

**Priority: P3**

- A registry of reusable actor components (base classes, utility libraries, verified patterns).  
- Import and compose: `from cowboy_registry import DCAStrategy` enables developers to build on each other's work.  
- Incentive alignment: component authors can earn CBY when their components are used in deployed actors (via on-chain attribution).  
- Quality signals: usage count, audit status, determinism-verified badge.

### 4.2 Web-Based Playground / REPL

**Priority: P3**

- Browser-based PVM playground. Write an actor, deploy to an in-browser devnet, send messages, see state changes.  
- No install required. The fastest path from curiosity to understanding.  
- Shareable links: share a working actor example as a URL.  
- Embedded in docs: every code example in the docs is a runnable playground link.

### ~~4.3 Corral IDE~~

**~~Priority: P3~~**

~~The Cowchat spec references a "Corral IDE" for developers who want to write code directly rather than use the visual builder. This needs definition: is it a web IDE (like Remix), a VS Code fork, or just the VS Code extension \+ CLI with "Corral" as the marketing name?~~

**\~\~Recommendation:** Don't build a custom IDE. Invest in the VS Code extension and CLI. Developers are already in VS Code or Cursor. Meet them there. Call the extension "Corral" if you want the brand.\~\~

### 4.4 Community & Ecosystem Infrastructure

**Priority: P3**

- Block explorer with actor-aware features: view actor source, browse storage, trace messages, see timer history.  
- Actor marketplace: discover and fork deployed actors. Like "View Source" for on-chain agents.  
- Bounty board: Cowboy Foundation posts bounties for high-value actors, Watchtower feeds, and tooling.  
- Developer grants program: fund developers building on Cowboy. Modeled on Ethereum Foundation grants.  
- Changelog and migration guides: when the PVM, SDK, or protocol changes, developers need clear upgrade paths.

---

## Full Checklist

Every deliverable in one view.

### CLI

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| `cowboy init` (scaffolding with templates) | P0 | 1 | 要做 |
| `cowboy dev` (local development server) | P0 | 1 | 会议决定不需要做 |
| `cowboy test` (testing against simulated PVM) | P0 | 1 | 会议决定不需要做 |
| `cowboy actor deploy` (deploy to devnet/mainnet) | P0 | 1 | Implemented |
| `cowboy actor logs` (tail actor logs) | P0 | 1 | 我们在NODE中加一个LOG功能，计划将LOG写到链上的数据库里面。 |
| `cowboy actor send` (send messages to actors) | P1 | 1 | Implemented |
| `cowboy secrets` (manage encrypted secrets) | P1 | 1 | 会议决定不需要做 |
| `cowboy cost` (estimate running costs) | P1 | 1 | 会议决定不需要做 |
| `cowboy inspect` (inspect live actor state) | P2 | 3 | Partial |
| `cowboy upgrade` (versioned upgrades) | P2 | 3 | ☐ |
| `cowboy trace` (cross-block execution trace) | P2 | 3 | ☐ |
| `cowboy watch` (live actor TUI dashboard) | P2 | 3 | ☐ |
| `cowboy rollback` (revert to previous version) | P2 | 3 | ☐ |
| `cowboy runner get` |  |  | Implemented |
| `cowboy runner list` |  |  | Implemented |
| `cowboy runner register` |  |  | Implemented |
| `cowboy job get` |  |  | Implemented |
| `cowboy job status` |  |  | Implemented |
| `cowboy job runners` |  |  | Implemented |
| `cowboy job results` |  |  | Implemented |
| `cowboy job verified` |  |  | Implemented |
| `cowboy job submit` |  |  | Implemented |
| `cowboy transfer` |  |  | Implemented |

### Local Development ： 我们觉得这个不合适在目前实现，本地化部署目前不现实，因为现在开发出来的COWBOY DEVNET NODE是有实际网络功能的。所以本地开发这部分在**Phase1就暂时不去实现了**。

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| Local PVM with full determinism enforcement | P0 | 1 | ☐ |
| Block simulation (clock or manual) | P0 | 1 | ☐ |
| Timer simulation with GBA | P0 | 1 | ☐ |
| Runner mocking (LLM, HTTP, compute) | P0 | 1 | ☐ |
| Hot reload on file changes | P0 | 1 | ☐ |
| Multi-actor local environment | P1 | 1 | ☐ |
| State inspector (web UI or TUI) | P1 | 1 | ☐ |
| `cowboy.yaml` config format | P1 | 1 | ☐ |

### SDK

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| Full type annotations (PEP 484\) \+ `.pyi` stubs | P0 | 1 | Partial |
| Ergonomic decorators (`@actor`, `@runner.continuation`, `@timer`) | P0 | 1 | Minimal |
| PVM-safe helpers (vrf, time, math) | P0 | 1 | 会议上表达已经实现了，TONY留言：What's exactly the PVM-safe helper work with (vrf, time, math) ? can you give some examples? |
| Watchtower client (get, subscribe, unsubscribe) | P1 | 1 | 这个会议上明确没有 |
| Correlation ID and timeout handling helpers | P1 | 1 | 可以问他需要什么样的timeout handling helpers？ |
| Storage utilities and migration scaffolding | P1 | 1 | Stub only |
| Copy-pasteable pattern recipes in docstrings | P1 | 1 | ☐ |
| Context manager |  |  | Implemented |
| JSON-RPC client |  |  | Implemented |

### Testing

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| `SimulatedChain` with in-memory PVM | P0 | 1 | TONY留言：We are maintaining the SimulatedChain at this stage because the fast pace of the Cowboy node development. |
| Block advancement and timer triggering | P0 | 1 | TONY留言：Since we don’t have the SimulatedChain environment, we are not able to advance a block on the public DevNet |
| Runner mocking with conditional responses | P0 | 1 | 这个也没有，因为跟第一条同样的原因 |
| State snapshot assertions | P0 | 1 | ☐ |
| Determinism checking (cross-platform) | P0 | 1 | ☐ |
| Message sequence fuzzing / property testing | P1 | 2 | ☐ |
| JUnit XML output for CI | P1 | 2 | ☐ |
| Pre-deploy gate (tests must pass) | P1 | 2 | ☐ |

### Error Messages

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| Four-part error format (what, why, fix, link) | P0 | 1 | 可以考虑实现 |
| Common error mapping table in PVM | P0 | 1 | ☐ |
| Contextual suggestions in CLI output | P1 | 1 | ☐ |

### IDE & Linter

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| PVM linter (forbidden imports, non-determinism) | P1 | 2 | ☐ |
| VS Code extension with real-time diagnostics | P1 | 2 | ☐ |
| Quickfix suggestions for PVM violations | P1 | 2 | ☐ |
| Inline cost estimates (CodeLens) | P2 | 2 | ☐ |
| Actor graph visualization | P2 | 3 | ☐ |
| Snippet library for common patterns | P2 | 2 | ☐ |
| Deploy/logs commands in command palette | P2 | 2 | ☐ |

### AI Context

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| SKILL.md for Claude / Cowork | P1 | 2 | ☐ |
| `.cursorrules` in `cowboy init` output | P1 | 2 | ☐ |
| `llms.txt` at docs domain root | P1 | 2 | ☐ |
| MCP Server for live doc queries | P2 | 3 | ☐ |
| Snippet registry for AI code generation | P2 | 3 | ☐ |
| CI pipeline: auto-generate from source | P2 | 2 | ☐ |

### Templates

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| `minimal` (Hello World actor) | P1 | 2 | ☐ |
| `arb-bot` (price differential trading) | P1 | 2 | ☐ |
| `trading-bot` (LLM signal \+ execution) | P1 | 2 | ☐ |
| `oracle-provider` (Watchtower feed) | P1 | 2 | ☐ |
| `watcher` (monitoring \+ alerts) | P2 | 2 | ☐ |
| `prediction-market` (Wrangler) | P2 | 2 | ☐ |

### Documentation

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| Getting Started guide (zero to deploy in 10 min) | P1 | 2 | ☐ |
| Concepts section (actor model, continuations, etc.) | P1 | 2 | ☐ |
| Task-oriented guides (how to do X) | P1 | 2 | ☐ |
| Auto-generated SDK reference | P1 | 2 | ☐ |
| PVM reference (whitelist, rules, metering) | P1 | 2 | ☐ |
| Annotated full examples | P2 | 2 | ☐ |
| Architecture deep-dives (from whitepaper) | P2 | 3 | ☐ |

### Observability

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| Live state viewer in Cowchat | P2 | 3 | ☐ |
| Timer timeline visualization | P2 | 3 | ☐ |
| Runner job tracker | P2 | 3 | ☐ |
| Message trace visualization | P2 | 3 | ☐ |
| Cost breakdown and trending | P2 | 3 | ☐ |

### Upgrades

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| `cowboy upgrade` with dry-run diff | P2 | 3 | ☐ |
| State migration generation and validation | P2 | 3 | ☐ |
| Rollback support with state restoration | P2 | 3 | ☐ |
| Version history on-chain and in CLI | P2 | 3 | ☐ |

### Frontend SDK

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| JS/TS SDK for browser interaction | P2 | 3 | ☐ |
| Wallet connection (secp256k1) | P2 | 3 | ☐ |
| Actor storage queries | P2 | 3 | ☐ |
| Transaction building and signing | P2 | 3 | ☐ |
| WebSocket event subscriptions | P2 | 3 | ☐ |

### Interfaces

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| Auto-generated interface definitions from code | P2 | 3 | ☐ |
| `cowboy inspect` for any deployed actor | P2 | 3 | ☐ |
| On-chain interface registry | P3 | 4 | ☐ |

### Ecosystem

| Deliverable | Priority | Phase | Status |
| :---- | :---- | :---- | :---- |
| Reusable component registry | P3 | 4 | ☐ |
| Web-based playground / REPL | P3 | 4 | ☐ |
| Actor-aware block explorer | P3 | 4 | ☐ |
| Actor marketplace (view source, fork) | P3 | 4 | ☐ |
| Bounty board and grants program | P3 | 4 | ☐ |
| Corral IDE (or VS Code extension branding) | P3 | 4 | ☐ |

---

## Appendix: Open Decisions

Decisions that need resolution before or during implementation.

**CLI distribution:** How do developers install the CLI? Martin留下评论：“ I like B and C I think as engineer I will be using these ones. The option A for the Python SDK”   Options: (a) `pip install cowboy-cli`, (b) `brew install cowboy`, (c) standalone binary (like Vercel's CLI), (d) `npx cowboy`. Recommendation: pip for Python developers (primary audience), with standalone binaries for those who don't want a Python environment.

**Local PVM scope:** Does `cowboy dev` run the actual PVM reference implementation, or a simplified simulation? Full PVM is more accurate but heavier to distribute. Simulation is faster to ship but may have divergences. Recommendation: ship simulation first, gate mainnet deploys behind a CI determinism check.

**Corral IDE vs. extension:** Build a custom IDE or invest in VS Code/Cursor extensions? Custom IDEs are expensive to maintain and developers resist switching. Recommendation: VS Code extension, branded as Corral. Redirect IDE budget to CLI and testing tools.

**Docs anti-scraping:** Block crawlers or embrace openness? Blocking crawlers hurts SEO and discoverability. Recommendation: public docs \+ superior AI context via SKILL.md/MCP. Let the protocol be the moat.

**Config file format:** `cowboy.yaml` vs. `pyproject.toml [tool.cowboy]` section vs. dedicated `cowboy.toml`. Recommendation: `pyproject.toml` for SDK/project config, `cowboy.yaml` for dev environment config (mocks, chain params).

**Devnet as a service:** Do you run a persistent public devnet, or does `cowboy dev` always spin up a local instance? Both have value: local for fast iteration, public for multi-user testing and cross-actor integration. Recommendation: local by default, public devnet for integration testing. `cowboy deploy` defaults to public devnet.

**Testing framework integration:** Build a custom test runner or integrate with pytest? Developers expect pytest. Recommendation: build Cowboy test primitives as a pytest plugin (`pytest-cowboy`). `cowboy test` is a thin wrapper around pytest with the plugin auto-loaded.

**Frontend SDK timing:** Build before or after launch? Depends on whether third-party frontends are a launch priority or if Cowchat is sufficient. Recommendation: post-launch (Phase 3). Cowchat covers launch use cases.  
