# Cowboy Project — Comprehensive Technical Architecture Overview

> **Date:** 2026-02-12  
> **Repositories Covered:**  
> - `cowboyinc/node` — Branch: `devnet`  
> - `cowboyinc/pvm` — Branch: `main`  
> - `cowboyinc/runner` — Branch: `main`  

---

## 1. Comprehensive Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                              COWBOY — ACTOR-MODEL LAYER-1 BLOCKCHAIN                         ║
║                              with Verifiable Off-Chain Compute                               ║
╠══════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                              ║
║   External Users / Developers                                                                ║
║   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────┐    ║
║   │  CLI Client    │  │ Block Explorer │  │  DApp Frontend │  │  Python Smart Contract  │    ║
║   │  (clap)        │  │ (Explorer)     │  │  (Web)         │  │  Developer (Actors)     │    ║
║   └───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └───────────┬─────────────┘    ║
║           │                   │                   │                       │                  ║
║           └───────────────────┴───────────────────┴───────────────────────┘                  ║
║                                         │                                                    ║
║                                         ▼                                                    ║
║ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ ║
║ ┃                         RPC API Layer (Axum REST + OpenAPI/Swagger)                      ┃ ║
║ ┃                                                                                          ┃ ║
║ ┃  TX Submit       Account Query   Actor Query     Block Query   Health       Runner/Job   ┃ ║
║ ┃  POST /submit    GET /account    GET /actor      GET /block    GET /health  GET /runners ┃ ║
║ ┃  GET /tx/{hash}  GET /tx/receipt GET /actor/code GET /height   /detailed    GET /runner  ┃ ║
║ ┃  GET /mempool/tx                                               /ready       GET /job     ┃ ║
║ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ ║
║                                         │                                                    ║
║                                         ▼                                                    ║
║ ┌──────────────────────────────────────────────────────────────────────────────────────────┐ ║
║ │                          NODE Core Layer (cowboyinc/node repo)                           │ ║
║ │                          Branch: devnet                                                  │ ║
║ │                                                                                          │ ║
║ │  ┌────────────────────────────────────────────────────────────────────────────────────┐  │ ║
║ │  │                  Consensus Layer — Simplex BFT (commonware framework)              │  │ ║
║ │  │                                                                                    │  │ ║
║ │  │  • BLS12-381 threshold signatures  • 2/3+ supermajority finality                   │  │ ║
║ │  │  • 1-second block interval         • leader_timeout = 1s, notarization_timeout = 2s│  │ ║
║ │  │                                                                                    │  │ ║
║ │  └────────────────────────────────────────────────────────────────────────────────────┘  │ ║
║ │                                       │                                                  │ ║
║ │                                       ▼                                                  │ ║
║ │  ┌─────────────────────────────────────────────────────────────────────────────────────┐ │ ║
║ │  │              TX Execution Engine — Dual-Gas Metering (Cycles + Cells)               │ │ ║
║ │  │                                                                                     │ │ ║
║ │  │  Cycles = Compute Gas              Cells = Storage Gas                              │ │ ║
║ │  │  Users set independent limits and prices for each dimension                         │ │ ║
║ │  │                                                                                     │ │ ║
║ │  │┌────────── System Instructions ────────────────┐┌── Actor Instructions ────────────┐│ │ ║
║ │  ││ • CreateAccount      [Create Account]         ││ • DeployActor [Deploy Contr.].   ││ │ ║
║ │  ││ • Transfer           [Native Transfer]        ││   ├─ CREATE2 det. addr           ││ │ ║
║ │  ││ • RunnerRegister     [Runner Registration]    ││   └─ SHA256(creator+salt+code_hash)│ │ ║
║ │  ││ • RunnerUpdateRateCard[Update Rate Card]      ││ • ExecuteActor[Execute Contr.].  ││ │ ║
║ │  ││ • RunnerHeartbeat    [Runner Heartbeat]       ││   └─ Execute Python via PVM      ││ │ ║
║ │  ││ • RunnerDeregister   [Runner Deregistration]  ││                                  ││ │ ║
║ │  ││ • JobSubmit          [Submit Off-Chain Job]   ││ • Custom      [Extension]        ││ │ ║
║ │  ││ • JobResultSubmit    [Submit Off-Chain Result]││   └─ module + action + data      ││ │ ║
║ │  ││ • JobCancel          [Cancel Off-Chain Job]   ││                                  ││ │ ║
║ │  │└───────────────────────────────────────────────┘└──────────────────────────────────┘│ │ ║
║ │  └─────────────────────────────────────────────────────────────────────────────────────┘ │ ║
║ │                         │                              │                                 │ ║
║ │            ┌────────────┘                              └────────────┐                    │ ║
║ │            ▼                                                        ▼                    │ ║
║ │  ┌──────────────────────┐                                ┌──────────────────────────┐    │ ║
║ │  │ Deferred TX          │                                │  Actor Model             │    │ ║
║ │  │ Mechanism            │                                │  (Smart Contracts)       │    │ ║
║ │  │                      │                                │                          │    │ ║
║ │  │ • Cross-block async  │                                │  Each Actor owns:        │    │ ║
║ │  │   execution          │                                │  • code (Python source)  │    │ ║
║ │  │ • Shared parent TX   │                                │  • storage (KV store)    │    │ ║
║ │  │   Gas pool           │                                │  • mailbox (msg queue)   │    │ ║
║ │  │ • System-triggered   │                                │  • balance               │    │ ║
║ │  │   independent Gas    │                                │  • nonce (sequence #)    │    │ ║
║ │  │ • Callback chains    │                                │                          │    │ ║
║ │  └──────────────────────┘                                └─────────────┬────────────┘    │ ║
║ │                                                                        │                 │ ║
║ │                                       ┌────────────────────────────────┘                 │ ║
║ │                                       │                                                  │ ║
║ │                                       ▼                                                  │ ║
║ │  ┌──── 5 System Actors (Initialized at genesis, deterministic seed addresses) ────────┐  │ ║
║ │  │                                                                                    │  │ ║
║ │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                  │  │ ║
║ │  │  │ Runner Registry  │  │ Job Dispatcher   │  │ Result Verifier  │                  │  │ ║
║ │  │  │ (Seed: 0x01)     │  │ (Seed: 0x02)     │  │ (Seed: 0x03)     │                  │  │ ║
║ │  │  │                  │  │                  │  │                  │                  │  │ ║
║ │  │  │ • Register/      │  │ • Task dispatch  │  │ • Result         │                  │  │ ║
║ │  │  │   Deregister     │  │ • Committee      │  │   collection     │                  │  │ ║
║ │  │  │ • Stake ≥50K CBY │  │   selection      │  │ • Multi-mode     │                  │  │ ║
║ │  │  │ • Heartbeat      │  │ • Task queue     │  │   verification   │                  │  │ ║
║ │  │  │   health check   │  │   management     │  │ • Callback       │                  │  │ ║
║ │  │  │ • Rate card mgmt │  │ • Deterministic  │  │   triggering     │                  │  │ ║
║ │  │  │                  │  │   assignment     │  │ • Dispute        │                  │  │ ║
║ │  │  │                  │  │                  │  │   resolution     │                  │  │ ║
║ │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘                  │  │ ║
║ │  │  ┌──────────────────┐  ┌──────────────────┐                                        │  │ ║
║ │  │  │ Secrets Manager  │  │ TEE Verifier     │  ← Reserved Modules (Placeholder)      │  │ ║
║ │  │  │ (Seed: 0x04)     │  │ (Seed: 0x05)     │                                        │  │ ║
║ │  │  └──────────────────┘  └──────────────────┘                                        │  │ ║
║ │  └────────────────────────────────────────────────────────────────────────────────────┘  │ ║
║ │                                                                                          │ ║
║ │  ┌────────────────────────────────┐   ┌──────────────────────────────────────────────┐   │ ║
║ │  │ Mempool (TX Pool)              │   │ Blockchain Storage                           │   │ ║
║ │  │ • Round-Robin fair scheduling  │   │ • Journal (persistent) + Buffer Pool (cache) │   │ ║
║ │  │ • Max 32,768 pending TXs       │   │ • Buffer Pool: 8KB pages / 1MB capacity      │   │ ║
║ │  │ • Max 16 TXs per account       │   │                                              │   │ ║
║ │  └────────────────────────────────┘   └──────────────────────────────────────────────┘   │ ║
║ │                                                                                          │ ║
║ │  ┌────────── Sub-modules ─────────────────────────────────────────────────────────────┐  │ ║
║ │  │ • indexer (block indexing)  • inspector (diagnostics)  • Multiple demo examples    │  │ ║
║ │  │ • client (consensus client)                                                        │  │ ║
║ │  └────────────────────────────────────────────────────────────────────────────────────┘  │ ║
║ └──────────────────────────────────────────────────────────────────────────────────────────┘ ║
║                                         │                                                    ║
║ ═══════════════════════════════ HostApi Boundary ═══════════════════════════════════════════ ║
║                                         │                                                    ║
║                                         ▼                                                    ║
║ ┌────────────────────────────────────────────────────────────────────────────────────────┐   ║
║ │                       PVM Layer (cowboyinc/pvm repo, Branch: main)                     │   ║
║ │                   Python Virtual Machine — Deterministic Python 3 Interpreter          │   ║
║ │                                                                                        │   ║
║ │  ┌────────────────── pvm-runtime (Core Execution Engine) ──────────────────────────┐   │   ║
║ │  │                                                                                 │   │   ║
║ │  │  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────────┐    │   │   ║
║ │  │  │ Determinism       │  │ Import Guard      │  │ Resumable Execution       │    │   │   ║
║ │  │  │ Subsystem         │  │ System            │  │ (Checkpoint)              │    │   │   ║
║ │  │  │                   │  │                   │  │                           │    │   │   ║
║ │  │  │ • Fixed hash_seed │  │ • Whitelist (70   │  │ • Checkpoint mode         │    │   │   ║
║ │  │  │ • SoftFloat (cross│  │   modules)        │  │   (snapshot/serialize)    │    │   │   ║
║ │  │  │   platform parity)│  │ • Blacklist (23   │  │ • Cross-block resume      │    │   │   ║
║ │  │  │ • Gas metering    │  │   modules)        │  │ • VM state                │    │   │   ║
║ │  │  │   integration     │  │ • Alias mapping   │  │   serialize/deserialize   │    │   │   ║
║ │  │  │ • Environment     │  │ • Block I/O &     │  │                           │    │   │   ║
║ │  │  │   isolation       │  │   network access  │  │                           │    │   │   ║
║ │  │  │                   │  │ • Prefix matching │  │                           │    │   │   ║
║ │  │  └───────────────────┘  └───────────────────┘  └───────────────────────────┘    │   │   ║
║ │  │                                                                                 │   │   ║
║ │  │  ┌────────────── Python SDK Bridge (pvm_host module) ────────────────────┐      │   │   ║
║ │  │  │  State Mgmt: get_state / set_state / delete_state                     │      │   │   ║
║ │  │  │  Gas:        charge_gas / gas_left                                    │      │   │   ║
║ │  │  │  Events:     emit_event                                               │      │   │   ║
║ │  │  │  Messaging:  send_message / schedule_timer / cancel_timer             │      │   │   ║
║ │  │  │  Context:    context (block_height, block_hash, tx_hash,              │      │   │   ║
║ │  │  │             sender, timestamp_ms, actor_addr, msg_id, nonce)          │      │   │   ║
║ │  │  │  Randomness: randomness (deterministic PRNG)                          │      │   │   ║
║ │  │  │  Off-chain:  submit_job                                               │      │   │   ║
║ │  │  │  Deferred:   create_deferred_tx                                       │      │   │   ║
║ │  │  │                                                                       │      │   │   ║
║ │  │  │  pvm_sdk Modules (high-level Python SDK):                             │      │   │   ║
║ │  │  │    pvm_sdk.runtime / pvm_sdk.actor / pvm_sdk.runner                   │      │   │   ║
║ │  │  │    pvm_sdk.continuation / pvm_sdk.verify / pvm_sdk.types              │      │   │   ║
║ │  │  │    pvm_sdk.pvm_time / pvm_sdk.pvm_random / pvm_sdk.pvm_sys            │      │   │   ║
║ │  │  └───────────────────────────────────────────────────────────────────────┘      │   │   ║
║ │  └─────────────────────────────────────────────────────────────────────────────────┘   │   ║
║ │                                                                                        │   ║
║ │  ┌─── pvm-host (HostApi Trait, 13 methods) ─┐  ┌─── pvm-simulator (FS backend) ────┐   │   ║
║ │  │  Pure trait definition, zero deps        │  │  FsHost local test implementation │   │   ║
║ │  │  Node's CowboyHost implements this trait │  │  execute_tx_fs local execution    │   │   ║
║ │  └──────────────────────────────────────────┘  └───────────────────────────────────┘   │   ║
║ │                                                                                        │   ║
║ │  ┌─── Underlying VM: Modified RustPython ───────────────────────────────────────────┐  │   ║
║ │  │  compiler → bytecode → VM executor                                               │  │   ║
║ │  │  stdlib / SoftFloat (soft floating-point engine) / Checkpoint (serialization)    │  │   ║
║ │  │  21 Rust crates, 192+ core VM files                                              │  │   ║
║ │  └──────────────────────────────────────────────────────────────────────────────────┘  │   ║
║ └────────────────────────────────────────────────────────────────────────────────────────┘   ║
║                                                                                              ║
║ ═════════════════════ On-Chain ↔ Off-Chain Interaction Boundary ════════════════════════════ ║
║       (Runner polls tasks via REST API, submits results via signed REST)                     ║
║                                                                                              ║
║ ┌────────────────────────────────────────────────────────────────────────────────────────┐   ║
║ │                     Runner Layer (cowboyinc/runner repo, Branch: main)                 │   ║
║ │                  Off-Chain Execution Node — Operated by staked operators               │   ║
║ │                                                                                        │   ║
║ │  ┌────────────────── runner-node (Node Orchestration) ────────────────────────────┐    │   ║
║ │  │                                                                                │    │   ║
║ │  │  main.rs                                                                       │    │   ║
║ │  │    1. Load config (environment variables)                                      │    │   ║
║ │  │    2. KeyManager load/generate Ed25519 keypair                                 │    │   ║
║ │  │    3. HttpChainClient connect to chain node                                    │    │   ║
║ │  │    4. RunnerRegistrar register (stake ≥50K CBY)                                │    │   ║
║ │  │    5. Build ExecutorRegistry                                                   │    │   ║
║ │  │    6. RunnerNode::run() → Launch 3 async tasks                                 │    │   ║
║ │  │                                                                                │    │   ║
║ │  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────────┐    │    │   ║
║ │  │  │ Job Listener     │ │ Heartbeat        │ │ Job Executor                 │    │    │   ║
║ │  │  │                  │ │                  │ │                              │    │    │   ║
║ │  │  │ Poll /runner/    │ │ Send heartbeat   │ │ max_concurrent_jobs counter  │    │    │   ║
║ │  │  │ {addr}/jobs      │ │ every 10s to     │ │ (default 10 concurrent)      │    │    │   ║
║ │  │  │ Exponential      │ │ maintain Healthy │ │ Submission dedup (HashSet)   │    │    │   ║
║ │  │  │ backoff retry(3x)│ │ status           │ │ Auto-match executor type     │    │    │   ║
║ │  │  └──────────────────┘ └──────────────────┘ └──────────────────────────────┘    │    │   ║
║ │  └────────────────────────────────────────┬───────────────────────────────────────┘    │   ║
║ │                                           │                                            │   ║
║ │                                           ▼                                            │   ║
║ │  ┌────────────────────────────────────────────────────────────────────────────┐        │   ║
║ │  │                   ExecutorRegistry (Executor Registry)                     │        │   ║
║ │  │                                                                            │        │   ║
║ │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │        │   ║
║ │  │  │  LLM Executor    │  │  HTTP Executor   │  │  MCP Executor            │  │        │   ║
║ │  │  │  (runner-llm)    │  │  (runner-http)   │  │  (runner-mcp)            │  │        │   ║
║ │  │  │                  │  │                  │  │                          │  │        │   ║
║ │  │  │ • OpenAI client  │  │ • GET/POST/PUT/  │  │ • JSON-RPC over stdio    │  │        │   ║
║ │  │  │   (custom base)  │  │   DELETE/PATCH.. │  │ • MCP 2024-11-05 proto   │  │        │   ║
║ │  │  │ • Anthropic      │  │ • Data extraction│  │ • Connection pooling     │  │        │   ║
║ │  │  │   client         │  │   CSS / JSONPath │  │ • Tool caching           │  │        │   ║
║ │  │  │ • Local models   │  │   / Regex        │  │ • Param Schema           │  │        │   ║
║ │  │  │   (reserved)     │  │ • Source proof   │  │   validation             │  │        │   ║
║ │  │  │ • Structured     │  │   (Attestation)  │  │ • Timeout control        │  │        │   ║
║ │  │  │   output (JSON   │  │                  │  │                          │  │        │   ║
║ │  │  │   Schema)        │  │                  │  │                          │  │        │   ║
║ │  │  │ • Token usage    │  │                  │  │                          │  │        │   ║
║ │  │  │   tracking       │  │                  │  │                          │  │        │   ║
║ │  │  └────────┬─────────┘  └────────┬─────────┘  └────────────┬─────────────┘  │        │   ║
║ │  └───────────┼─────────────────────┼─────────────────────────┼────────────────┘        │   ║
║ │              ▼                     ▼                         ▼                         │   ║
║ │       ┌───────────┐          ┌───────────┐             ┌──────────────┐                │   ║
║ │       │ OpenAI    │          │ External  │             │  MCP Server  │                │   ║
║ │       │ Anthropic │          │ Web API   │             │ (stdio proc) │                │   ║
║ │       │ (or compat│          │ Services  │             │              │                │   ║
║ │       │  API)     │          │           │             │              │                │   ║
║ │       └───────────┘          └───────────┘             └──────────────┘                │   ║
║ │                                                                                        │   ║
║ │  ┌──── Common Foundation ──────────────────────────────────────────────────────┐       │   ║
║ │  │  runner-common:     Shared types / JobExecutor Trait / Ed25519 crypto / err │       │   ║
║ │  │  chain-client:      ChainClient Trait / HTTP impl / signed REST protocol    │       │   ║
║ │  │  runner-consensus:  N-of-M consensus client / inter-Runner result agg       │       │   ║
║ │  │  runner-registry:   Runner registration / rate cards / health / reputation  │       │   ║
║ │  │  job-dispatcher:    Task intake / Runner selection / queue / timeout mgmt   │       │   ║
║ │  │  result-verifier:   Multi-mode verify (N-of-M / structured / semantic)      │       │   ║
║ │  │  runner-tee:        TEE runtime / attestation proof generation              │       │   ║
║ │  │  secrets-manager:   Secure key management / TEE integration                 │       │   ║
║ │  │  tee-verifier:      TEE attestation verification                            │       │   ║
║ │  └─────────────────────────────────────────────────────────────────────────────┘       │   ║
║ └────────────────────────────────────────────────────────────────────────────────────────┘   ║
║                                                                                              ║
║ ┌────────── Implemented Demo Applications ──────────────────────────────────────────┐        ║
║ │                                                                                   │        ║
║ │  ┌───────────────────┐  ┌───────────────────────────────────┐                     │        ║
║ │  │ llm_chat          │  │ deferred_counter_demo             │                     │        ║
║ │  │ LLM Chat          │  │ Deferred TX Chain Counter         │                     │        ║
║ │  │ (Runner+AI Infer) │  │                                   │                     │        ║
║ │  └───────────────────┘  └───────────────────────────────────┘                     │        ║
║ └───────────────────────────────────────────────────────────────────────────────────┘        ║
║                                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════════════════════╣
║                              Development Output Summary                                      ║
║                                                                                              ║
║  NODE Repo (8 Rust crates):                                                                  ║
║    chain / cli / client / indexer / inspector / runner / storage / types                     ║
║                                                                                              ║
║  PVM Repo (21 Rust crates):                                                                  ║
║    pvm-host / pvm-runtime / pvm-simulator + modified RustPython (compiler, VM, stdlib ..)    ║
║                                                                                              ║
║  RUNNER Repo (13 Rust crates):                                                               ║
║    runner-node / runner-common / chain-client / runner-llm / runner-http / runner-mcp        ║
║    runner-consensus / runner-registry / job-dispatcher / result-verifier                     ║
║    runner-tee / secrets-manager / tee-verifier                                               ║
║                                                                                              ║
║  Total: 42 Rust crates, covering Consensus → Execution → VM → Off-Chain Compute              ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Module Interaction Data Flow (Simplified)

```
User DApp                                 Runner Operator
    │                                       │
    │  Submit TX                            │  Register + Stake ≥ 50K CBY
    ▼                                       ▼
┌────────┐  Consensus ┌───────────────┐  REST API  ┌──────────┐
│  CLI   │───────────▶│     NODE      │◄──────────▶│  RUNNER  │
│        │            │               │            │          │
└────────┘            │   Execution   │            │ Execution│
                      │   Engine      │            │ Framework│
                      │      │        │            │    │     │
                      │      ▼        │            │    ▼     │
                      │   ┌──────┐    │            │ ┌─────┐  │
                      │   │ PVM  │    │  HostApi   │ │ LLM │  │
                      │   │Python│    │            │ │ HTTP│  │
                      │   │ VM   │    │            │ │ MCP │  │
                      │   └──────┘    │            │ └─────┘  │
                      │               │            │    │     │
                      │  5 System     │            │    ▼     │
                      │  Actors:      │  On-chain  │ OpenAI   │
                      │  Registry     │◄──Result───│ Web API  │
                      │  Dispatcher   │ Validation │ MCP Svr  │
                      │  Verifier     │  Callback  │          │
                      │  SecretsMgr   │            │          │
                      │  TEEVerifier  │            │          │
                      └───────────────┘            └──────────┘

Flow: User TX → Consensus → Execution Engine → Actor(PVM) → submit_job
     → Job Dispatcher assigns → Runner polls & picks up → Execute (LLM/HTTP/MCP)
     → Signed result submission → Result Verifier majority vote verification
     → Trigger callback (Deferred TX) → Actor receives result
```

---

## 3. Three Repository Core Capabilities at a Glance

### NODE Repo (`devnet` branch) — 8 Rust Crates

| # | Crate | Core Capabilities |
|---|-------|-------------------|
| 1 | **cowboy-chain** | Simplex BFT consensus engine, dual-Gas execution engine (Cycles+Cells), 9 SystemInstructions + 2 ActorInstructions + Custom, Actor model smart contracts, 5 system Actors, deferred TX mechanism, TX processing & block production |
| 2 | **cowboy-cli** | CLI client (clap), TX submission, account/Actor/block queries, key management |
| 3 | **cowboy-client** | Consensus client, inter-node communication, BLS12-381 threshold signatures, message broadcast |
| 4 | **cowboy-indexer** | Block indexing service, historical TX retrieval, on-chain data query optimization |
| 5 | **cowboy-inspector** | Diagnostic tools, chain state inspection, debugging utilities |
| 6 | **cowboy-runner** | Runner on-chain interaction module, chain-side logic for registration/heartbeat/task management |
| 7 | **cowboy-storage** | Blockchain storage engine, Journal (persistent) + Buffer Pool (hot cache), 8KB pages / 1MB capacity |
| 8 | **cowboy-types** | Shared type definitions, TX/block/Actor/Account data structures, RPC API (Axum REST + OpenAPI/Swagger) |

### PVM Repo (`main` branch) — 21 Rust Crates

| # | Crate | Core Capabilities |
|---|-------|-------------------|
| 1 | **rustpython** | Top-level workspace entry, Python interpreter executable |
| 2 | **pvm-host** | HostApi Trait definition (13 methods), pure interface with zero deps, Node's CowboyHost implements this Trait |
| 3 | **pvm-runtime** | Core execution engine, determinism subsystem (fixed hash_seed), Gas metering integration, environment isolation |
| 4 | **pvm-simulator** | Filesystem backend (FsHost), local test/simulator implementation, execute_tx_fs local execution |
| 5 | **rustpython-compiler** | Python source compiler, AST parsing, bytecode compilation pipeline |
| 6 | **rustpython-compiler-core** | Compiler core data structures, compilation pipeline foundation |
| 7 | **rustpython-compiler-source** | Compiler source management, source location tracking (marked DEPRECATED) |
| 8 | **rustpython-codegen** | Python bytecode code generator, compiling AST to bytecode |
| 9 | **rustpython-literal** | Python literal parsing, numeric/string literal handling |
| 10 | **rustpython-vm** | VM executor core, bytecode interpretation, object system, frame management |
| 11 | **rustpython-pylib** | Python standard library (pure Python portion), built-in modules |
| 12 | **rustpython-stdlib** | Standard library (Rust implementation portion), performance-critical modules |
| 13 | **rustpython-common** | Common utilities, shared data structures & helper functions |
| 14 | **rustpython-derive** | Procedural macros (derive macros), PyClass/PyModule macro definitions |
| 15 | **rustpython-derive-impl** | Derive macro concrete implementation, Rust language extensions & macro logic |
| 16 | **rustpython-doc** | Documentation generation tools, API docs |
| 17 | **rustpython-sre_engine** | Regular expression engine (SRE), Python re module backend |
| 18 | **rustpython-jit** | JIT compilation support (reserved), performance optimization |
| 19 | **rustpython-wtf8** | WTF-8 encoding implementation, loosely-valid UTF-8 string handling |
| 20 | **rustpython-venvlauncher** | Lightweight venv launcher, virtual environment management |
| 21 | **rustpython_wasm** | WebAssembly compilation target, browser-side Python interpreter |

### RUNNER Repo (`main` branch) — 13 Rust Crates

| # | Crate | Core Capabilities |
|---|-------|-------------------|
| 1 | **runner-node** | Node orchestration, 3 async tasks (Job Listener / Heartbeat / Job Executor), max_concurrent_jobs counter (default 10 concurrent) |
| 2 | **runner-common** | Shared types, JobExecutor Trait, Ed25519 cryptography, error hierarchy definitions |
| 3 | **chain-client** | ChainClient Trait, HTTP implementation, signed REST submission protocol |
| 4 | **runner-llm** | LLM Executor, OpenAI/Anthropic clients, structured output (JSON Schema), token usage tracking |
| 5 | **runner-http** | HTTP Executor, GET/POST/PUT/DELETE/PATCH requests, data extraction (CSS/JSONPath/Regex), source proof (Attestation) |
| 6 | **runner-mcp** | MCP Executor, JSON-RPC over stdio, MCP 2024-11-05 protocol, connection pooling, tool caching, param Schema validation |
| 7 | **runner-consensus** | N-of-M consensus client, inter-Runner result aggregation & communication |
| 8 | **runner-registry** | Runner registration/deregistration, rate card management, heartbeat health checks, reputation system |
| 9 | **job-dispatcher** | Task intake & dispatching, Runner selection, task queue management, timeout handling, deterministic assignment |
| 10 | **result-verifier** | Multi-mode result verification (N-of-M / structured matching / semantic similarity), callback triggering, dispute resolution |
| 11 | **runner-tee** | TEE runtime, isolated execution environment, attestation proof generation |
| 12 | **secrets-manager** | Secure key management, TEE integration support |
| 13 | **tee-verifier** | TEE attestation verification, proof validation |

> **Total: 42 Rust Crates**, covering Consensus → Execution → VM → Off-Chain Compute full pipeline

---

## 4. Key Technical Decisions

| # | Decision | Description |
|---|----------|-------------|
| 1 | **Actor Model** (not EVM) | Each smart contract is an independent Actor with its own state/mailbox/balance, communicating via messages |
| 2 | **Dual Gas Metering** (Cycles + Cells) | Compute and storage costs are separated; users set independent prices for each dimension |
| 3 | **PVM (Python VM)** | Modified RustPython for deterministic Python execution, lowering the developer barrier to entry |
| 4 | **Runner Off-Chain Compute** | Staked operators execute LLM/HTTP/MCP tasks, with on-chain multi-mode verification (N-of-M / structured matching / semantic similarity) and inter-Runner consensus aggregation |
| 5 | **Deferred Transactions** | Cross-block async execution, shared parent TX Gas pool, callback chain support |
| 6 | **CREATE2 Addresses** | `SHA256(creator + salt + code_hash)`, predictable addresses before deployment |
| 7 | **Simplex BFT** | BLS12-381 threshold signatures, 1-second blocks, 2/3+ finality, leader_timeout=1s, notarization_timeout=2s |
| 8 | **SoftFloat** | Pure software floating-point arithmetic, bit-level consistency across ARM/x86/WASM |
| 9 | **REST + OpenAPI** | Standardized API with built-in Swagger documentation and numeric error codes |
| 10 | **Runner Consensus** | N-of-M consensus client, inter-Runner data sync & result aggregation, extensible verification modes |
| 11 | **Reputation System** | Runner reputation scoring, rate card management, heartbeat health checks, automated trust management |
| 12 | **TEE Support (Reserved)** | TEE runtime isolated execution, attestation proof generation & verification, secure key management |

---

