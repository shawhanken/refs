# Cowboy SDK Developer Manual

> **Version**: 0.1.0 | **Spec**: CIP-6 | **Status**: Production-ready for Devnet

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Architecture Overview](#2-architecture-overview)
3. [Actor System](#3-actor-system)
4. [Call Primitives](#4-call-primitives)
5. [Runner & Continuation (FSM)](#5-runner--continuation-fsm)
6. [State Management](#6-state-management)
7. [Type System](#7-type-system)
8. [Safety Mechanisms](#8-safety-mechanisms)
9. [Verification System](#9-verification-system)
10. [Async Tools](#10-async-tools)
11. [CIP-20 Token API](#11-cip-20-token-api)
12. [Error Handling](#12-error-handling)
13. [PVM Compatibility Rules](#13-pvm-compatibility-rules)
14. [Deployment Guide](#14-deployment-guide)
15. [Complete Example](#15-complete-example)
16. [API Reference](#16-api-reference)

---

## 1. Quick Start

### 1.1 Minimal Actor

```python
import json
from cowboy_sdk import actor, runner, capture, CowboyModel, runtime

@actor
class HelloActor:
    def init(self, payload):
        """Called once on first deploy. Initialize state."""
        runtime.charge_gas(100)
        self.storage["greeting"] = "Hello, Cowboy!"
        return b"ok"

    def greet(self, payload):
        """Synchronous handler — returns immediately."""
        runtime.charge_gas(100)
        msg = self.storage.get("greeting", "Hi")
        return json.dumps({"message": msg}).encode("utf-8")

# PVM entry points (module-level functions)
def _get_actor():
    return HelloActor()

def init(payload):
    return _get_actor().init(payload)

def greet(payload):
    return _get_actor().greet(payload)
```

### 1.2 Environment Setup

```bash
# PVM auto-sets sys.path with pvm/Lib — cowboy_sdk can be imported directly on-chain.
# For local development/testing:
export PYTHONPATH=/path/to/node/pvm/Lib

# Run tests
cd node/pvm/Lib/cowboy_sdk
python -m pytest tests/ -v
```

### 1.3 Project Structure

```
my_actor/
├── my_actor.py          # Actor code (deployed to chain)
├── deploy.sh            # Deploy & interact script
└── frontend/            # Optional web UI
    ├── index.html
    └── app.js
```

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Developer Code (Python)                   │
│  @actor class + @runner.continuation + CowboyModel          │
├─────────────────────────────────────────────────────────────┤
│                     cowboy_sdk (CIP-6)                       │
│  actor │ call │ send │ runner │ continuation │ verify │ ... │
├─────────────────────────────────────────────────────────────┤
│                   runtime (pvm_host bridge)                  │
│  context │ get/set_state │ send_message │ call_actor │ ...  │
├─────────────────────────────────────────────────────────────┤
│                PVM (Deterministic Python VM)                 │
│  SoftFloat │ CBOR │ Fixed Hash Seed │ No JIT                │
├─────────────────────────────────────────────────────────────┤
│              Cowboy Chain (Consensus Layer)                  │
└─────────────────────────────────────────────────────────────┘
```

### SDK Module Map

| Module | Purpose |
|--------|---------|
| `actor` | `@actor` decorator, `ActorRef`, `self.storage`, message dispatch |
| `call` | Synchronous cross-Actor call (`call()`) |
| `send` | Async fire-and-forget message (`send()`) |
| `runner` | Runner task interface (`runner.llm/http/mcp`), `@runner.continuation` |
| `continuation` | `capture()`, `Capture`, `save_cont/load_cont/delete_cont` |
| `_compiler` | FSM AST compiler (internal, not developer-facing) |
| `models` | `CowboyModel` structured data base class |
| `types` | `SoftFloat`, `ordered_set`, `BlockHeight`, `Address` |
| `guards` | `@reentrancy_guard`, `GuardedValue`, `storage_guard`, `GuardSet` |
| `bounded_loop` | `@bounded_loop`, `BoundedRange`, `check_iteration` |
| `verify` | `Verify` builder + 17+ checkers |
| `retry` | `Retry` backoff policy |
| `taskgroup` | `TaskGroup` structured concurrency |
| `codec` | Canonical CBOR encode/decode |
| `runtime` | PVM host wrapper (context, state, gas, events, token) |
| `pvm_random` | Deterministic random (replaces `import random`) |
| `pvm_time` | Block-based time (replaces `import time`) |
| `pvm_sys` | Chain/PVM metadata |
| `errors` | Complete error hierarchy |

---

## 3. Actor System

### 3.1 @actor Decorator

The `@actor` decorator transforms a plain Python class into a Cowboy Actor:

```python
from cowboy_sdk import actor

@actor
class MyActor:
    # @actor injects:
    #   self.address  — Actor's own 20-byte Ethereum address (bytes)
    #   self.storage  — CBOR-encoded key-value store proxy
    pass
```

**What `@actor` does internally:**
1. Injects `self.address` (from `runtime.get_actor_address()`)
2. Injects `self.storage` (an `_ActorStorage` proxy with CBOR auto-encode/decode)
3. Scans for `@runner.continuation` / `@actor.continuation` methods and installs `__resume` handlers
4. Adds `_dispatch(method_name, msg)` for message routing

### 3.2 self.storage — Actor State

`self.storage` is a dict-like proxy that automatically CBOR-encodes values on write and decodes on read.

```python
@actor
class TokenActor:
    def init(self, payload):
        # Write (auto CBOR encode)
        self.storage["total_supply"] = 1000000
        self.storage["name"] = "MyCoin"
        self.storage["balances"] = {"alice": 500, "bob": 300}

    def get_balance(self, payload):
        # Read (auto CBOR decode)
        balances = self.storage.get("balances", {})
        return json.dumps(balances).encode("utf-8")

    def transfer(self, payload):
        obj = json.loads(payload)
        balances = self.storage["balances"]  # KeyError if not found
        # ... modify balances ...
        self.storage["balances"] = balances  # Write back
```

**Storage API:**

| Method | Description |
|--------|-------------|
| `self.storage[key]` | Read value (CBOR decode). Raises `KeyError` if missing |
| `self.storage[key] = val` | Write value (CBOR encode) |
| `self.storage.get(key, default)` | Read with default |
| `key in self.storage` | Check key existence |
| `del self.storage[key]` | Delete key |
| `self.storage.get_raw(key)` | Read raw bytes (no decode) |
| `self.storage.set_raw(key, data)` | Write raw bytes (no encode) |
| `self.storage.guard(key)` | Get a `GuardedValue` for cross-block protection |

### 3.3 Handler Dispatch & PVM Entry Points

PVM looks for **module-level functions** as entry points. The recommended pattern:

```python
@actor
class MyActor:
    def init(self, payload): ...
    def do_something(self, payload): ...

# Module-level entry points for PVM
def _get_actor():
    return MyActor()

def init(payload):
    return _get_actor().init(payload)

def do_something(payload):
    return _get_actor().do_something(payload)
```

> **Important**: For `@runner.continuation` methods, you must also expose the `__resume` function:
> ```python
> def chat__resume(payload):
>     return _get_actor().chat__resume(payload)
> ```

### 3.4 ActorRef — Syntactic Sugar

```python
from cowboy_sdk import ActorRef

oracle = ActorRef("0x4444...")
price = oracle.get_price("ETH")  # Compiles to call(target, method, args)
```

### 3.5 Address System

All addresses are 20-byte Ethereum-style (secp256k1 + keccak256):

```python
from cowboy_sdk.types import Address

# From hex string
addr = Address.from_hex("0x1234...abcd")

# From bytes
addr = Address(b'\x12\x34...')

# System Actor addresses (like EVM precompiles)
Address.RUNNER_REGISTRY   # 0x0000...0001
Address.JOB_DISPATCHER    # 0x0000...0002
Address.RESULT_VERIFIER   # 0x0000...0003
Address.SECRETS_MANAGER   # 0x0000...0004
Address.TEE_VERIFIER      # 0x0000...0005
Address.TOKEN_REGISTRY    # 0x0000...0006
```

---

## 4. Call Primitives

Cowboy provides three call primitives with different delivery semantics:

| Primitive | Timing | Return Value | Atomic | Use Case |
|-----------|--------|-------------|--------|----------|
| `call()` | T+0 (same tx) | ✅ Yes | ✅ Yes | State queries, atomic operations |
| `send()` | T+N (next block) | ❌ None | ❌ No | Notifications, fire-and-forget |
| `await runner.*` | T+N (after off-chain) | ✅ On resume | ❌ No | LLM, HTTP, cross-Actor async |

### 4.1 call() — Synchronous Call

```python
from cowboy_sdk import call

def check_balance(self, payload):
    balance = call(
        target="0x1111...",        # Target Actor address
        method="get_balance",       # Method name
        args={"user": "alice"},     # CBOR-serializable args
        cycles_limit=5000           # Max cycles (default: 100,000)
    )
    return json.dumps({"balance": balance}).encode("utf-8")
```

**Constraints:**
- Call depth limit: **32 levels** (cumulative, including nested calls)
- Args and return values must be CBOR-serializable
- Failure in callee cascades rollback to caller

**Fluent API alternative:**
```python
from cowboy_sdk.call import call_builder

result = (call_builder("0x1111...")
    .method("get_balance")
    .args({"user": "alice"})
    .cycles(5000)
    .execute())
```

### 4.2 send() — Async Message

```python
from cowboy_sdk import send

def notify(self, payload):
    # Fire-and-forget — no return value, irrevocable
    send(target="0x3333...", payload={"action": "order_created", "id": 42})
    send(target="0x4444...", payload={"action": "audit", "id": 42})
```

> ⚠️ **Critical Pattern**: Always complete all `call()` operations that may fail **before** any `send()`:
> ```python
> # ✅ Correct: call() first, send() last
> result = call(target, "reserve_inventory", args)
> if not result["success"]:
>     raise InventoryError()
> send(target2, {"action": "order_created"})  # Only after success
> ```

---

## 5. Runner & Continuation (FSM)

### 5.1 Runner Task Types

The Runner system provides off-chain verifiable computation:

```python
from cowboy_sdk import runner

# LLM inference
result = await runner.llm(prompt, system_prompt="...", max_tokens=1024)

# HTTP request
result = await runner.http(url, method="GET", headers={...})

# MCP tool call
result = await runner.mcp("filesystem", "read_file", path="/data/input.txt")
```

> These can **only** be used inside `@runner.continuation` decorated async functions.

### 5.2 @runner.continuation — FSM Compilation

The SDK compiles async functions into **Finite State Machines** at import time. Each `await` point becomes a state transition.

```python
from cowboy_sdk import actor, runner, capture, runtime

@actor
class AnalysisActor:
    @runner.continuation
    async def analyze(self, payload):
        """FSM compiler splits this into analyze() + analyze__resume()"""
        runtime.charge_gas(1000)
        obj = json.loads(payload)
        
        # capture() declares variables to persist across await
        ctx = capture()
        ctx.query = obj["query"]
        ctx.sender = runtime.get_sender().hex()
        
        # ── await point: FSM splits here ──
        # Before await: save continuation state, send Runner job
        # After await (in __resume): restore state, continue
        result = await runner.llm(
            ctx.query,
            system_prompt="You are an analyst.",
            max_tokens=500,
        )
        # ── __resume segment starts here ──
        
        response = str(result) if result else ""
        self.storage[f"analysis:{ctx.sender}"] = response
        runtime.emit_event("analysis.done", {"query": ctx.query})
        return b"ok"
```

**What the compiler generates:**
1. `analyze(self, payload)` — Initial call: runs code before `await`, saves continuation, sends Runner job
2. `analyze__resume(self, msg)` — Callback: loads continuation, runs code after `await`, cleans up

### 5.3 capture() — Cross-Block Variable Persistence

Variables captured with `capture()` are CBOR-serialized into continuation state:

```python
ctx = capture()              # Create Capture context
ctx.user_id = "alice"        # Only CBOR-serializable types allowed
ctx.scores = [1, 2, 3]      # ✅ list, dict, str, int, float, bytes, bool, None
ctx.callback = lambda x: x  # ❌ CaptureTypeError! No closures/functions
```

**Allowed types**: `int`, `float`, `str`, `bytes`, `bool`, `None`, `list`, `tuple`, `dict` (and nested combinations).

### 5.4 With Parameters

```python
@runner.continuation(timeout_blocks=100, guard_keys=["balance"])
async def guarded_analysis(self, msg):
    ctx = capture()
    # guard_keys: if "balance" changes during await, StateConflictError on resume
    ctx.result = await runner.llm("analyze market")
    self.storage["decision"] = ctx.result
```

### 5.5 Handling Runner Callbacks

When Runner returns a result, the message is routed to the `__resume` function. Use `runner.handle_runner_result()` for routing:

```python
@actor
class MyActor:
    @runner.continuation
    async def chat(self, payload):
        ctx = capture()
        ctx.result = await runner.llm("Hello")
        return b"ok"

    def on_runner_result(self, payload):
        """Generic Runner callback entry point."""
        msg = codec.decode(payload) if isinstance(payload, bytes) else payload
        if isinstance(msg, dict) and msg.get("reply_handler"):
            runner.handle_runner_result(self, msg)
            return b"ok"

# Module-level
def chat(payload):        return _get_actor().chat(payload)
def chat__resume(payload): return _get_actor().chat__resume(payload)
def on_runner_result(payload): return _get_actor().on_runner_result(payload)
```

### 5.6 Continuation Constraints

| Constraint | Limit |
|-----------|-------|
| Max sequential `await` per function | **8** |
| Max active continuations per Actor | **100** |
| Max continuation state size | **64 KiB** |
| `await` in nested functions | ❌ Not allowed |
| `await` in loops | Must use `@bounded_loop` |
| Recursive `await` | ❌ Not allowed |

---

## 6. State Management

### 6.1 runtime Module

```python
from cowboy_sdk import runtime

# Execution context
ctx = runtime.context()          # Full context dict
sender = runtime.get_sender()    # 20-byte sender address
addr = runtime.get_actor_address()  # Actor's own address
height = runtime.get_block_height()
tx = runtime.get_tx_hash()       # 32-byte tx hash
ts = runtime.get_timestamp_ms()  # Block timestamp (ms)

# Gas
runtime.charge_gas(1000)

# Events
runtime.emit_event("my_event", {"key": "value"})
runtime.emit_event("transfer", b"raw_bytes")

# Low-level state (prefer self.storage)
runtime.get_state(b"key")
runtime.set_state(b"key", b"value")
runtime.delete_state(b"key")
```

### 6.2 Canonical CBOR Codec

```python
from cowboy_sdk import codec

encoded = codec.encode({"name": "Alice", "age": 30})  # bytes
decoded = codec.decode(encoded)                         # dict
```

Rules: RFC 8949 Canonical CBOR — sorted map keys, shortest integer encoding, no indefinite-length, float64 only.

---

## 7. Type System

### 7.1 CowboyModel — Structured Data

```python
from cowboy_sdk import CowboyModel

class Order(CowboyModel):
    id: str
    amount: int
    price: float          # SoftFloat on PVM
    buyer: str
    items: list

# Usage
order = Order(id="ord-001", amount=100, price=1.5, buyer="alice", items=["a", "b"])
cbor_bytes = order.to_cbor()               # Serialize
restored = Order.from_cbor(cbor_bytes)      # Deserialize
schema = Order.schema()                     # JSON Schema (for Verify)
d = order.to_dict()                         # Python dict
order2 = Order.from_dict(d)                 # From dict
order.validate()                            # Check required fields
```

### 7.2 PVM-Safe Types

| Type | Replaces | Import |
|------|----------|--------|
| `SoftFloat` | `float` | `from cowboy_sdk.types import SoftFloat` |
| `ordered_set` | `set` | `from cowboy_sdk.types import ordered_set` |
| `BlockHeight` | `int` | `from cowboy_sdk.types import BlockHeight` |
| `Address` | `bytes` | `from cowboy_sdk.types import Address` |

```python
from cowboy_sdk.types import SoftFloat, ordered_set, BlockHeight

# SoftFloat = float (PVM runtime replaces float globally with softfloat)
score = SoftFloat(0.95)  # Type alias for documentation/schema

# ordered_set — insertion-ordered, deterministic iteration
tags = ordered_set(["defi", "nft", "dao"])
tags.add("gamefi")
for tag in tags:  # Always same order across all nodes
    print(tag)

# BlockHeight — semantic int wrapper
height = BlockHeight(12345)
print(height)  # "block#12345"
```

---

## 8. Safety Mechanisms

### 8.1 @reentrancy_guard

Prevents the same method from being called recursively within one Actor:

```python
from cowboy_sdk import actor, reentrancy_guard

@actor
class SafeToken:
    @reentrancy_guard
    def transfer(self, payload):
        # If this method calls another Actor which calls back transfer(),
        # ReentrancyError is raised automatically
        ...
```

### 8.2 Guard Mechanisms (Cross-Block State Protection)

**Decorator-level guard:**
```python
@runner.continuation(guard_keys=["user_balance", "config"])
async def execute(self, msg):
    ctx = capture()
    ctx.result = await runner.llm("...")
    # If user_balance or config changed during await → StateConflictError
    self.execute_trade(ctx.result)
```

**Object-level guard:**
```python
from cowboy_sdk import storage_guard, GuardSet

balance = storage_guard("balance")       # Single key
val = balance.value                       # Read current value
balance.verify(expected_hash)             # Manual verify

guards = GuardSet("balance", "allowance") # Multiple keys
# guards.keys → for save_cont()
```

### 8.3 @bounded_loop

Required for any loop containing `await` points:

```python
from cowboy_sdk import bounded_loop, BoundedRange

@bounded_loop(max_iterations=10)
def process_items(self, items):
    for item in BoundedRange(items):
        self.process(item)
    # Raises LoopBoundExceeded if iterations > 10
```

---

## 9. Verification System

### 9.1 Verify Builder

```python
from cowboy_sdk import Verify

spec = (Verify.builder()
    .mode("consensus")           # consensus / deterministic / tee / zk / optimistic / none
    .runners(3)                  # Number of Runner nodes (1-21)
    .threshold(2)                # Min agreement count
    .check(Verify.json_schema_valid(Order.schema()))
    .check(Verify.numeric_range("price", 0.01, 999999))
    .check(Verify.no_prompt_leak())
    .timeout_blocks(100)
    .build())

result = await runner.llm(prompt="...", verify=spec)
```

### 9.2 Built-in Checkers (17+)

| Checker | Description |
|---------|-------------|
| `Verify.exact_match(value?)` | Byte-for-byte equality |
| `Verify.json_schema_valid(schema)` | JSON Schema validation |
| `Verify.structured_match(fields)` | Specified fields must match |
| `Verify.majority_vote(field?, threshold?)` | >50% agree |
| `Verify.supermajority_vote(field, threshold?)` | ≥67% agree |
| `Verify.numeric_tolerance(field, tol)` | Value within ±tolerance |
| `Verify.numeric_range(field, min?, max?)` | Value in [min, max] |
| `Verify.set_equality(field)` | Unordered set equality |
| `Verify.contains_all(substrings)` | Must contain all strings |
| `Verify.contains_none(substrings)` | Must not contain strings |
| `Verify.regex_match(pattern)` | Regex match |
| `Verify.length_bounds(min, max?)` | Length constraint |
| `Verify.semantic_similarity(ref?, threshold?)` | Embedding similarity |
| `Verify.no_prompt_leak()` | No system prompt in output |
| `Verify.entropy_check(min_entropy?)` | Not repetitive/degenerate |
| `Verify.custom(name, **kwargs)` | Custom rule by name |
| `Verify.custom_actor(addr, method, args?)` | Custom Actor validator |
| `Verify.not_empty()` | Result not empty |
| `Verify.format_check(format_type)` | json/xml/csv/url/email/uuid/... |
| `Verify.field_exists(*fields)` | Required fields exist |
| `Verify.deterministic_output()` | All Runners identical |
| `Verify.signature_valid(pubkey)` | Digital signature check |
| `Verify.tee_attestation(measurement?)` | TEE remote attestation |

---

## 10. Async Tools

### 10.1 Retry

```python
from cowboy_sdk import Retry

retry = Retry(max_attempts=3, on_error=True)
# Backoff sequence (blocks): [1, 2, 4, 8]
# Max 4 retries

while retry.has_next():
    delay = retry.next_delay()   # Consume one attempt, get wait blocks
    # ...

spec = retry.to_dict()  # For Runner job config
```

### 10.2 TaskGroup — Parallel Tasks

```python
from cowboy_sdk import TaskGroup

@runner.continuation
async def parallel_analysis(self, msg):
    ctx = capture()
    async with TaskGroup() as tg:
        t1 = tg.create_task(runner.llm("analyze risk"))
        t2 = tg.create_task(runner.http("https://api.prices.com/eth"))
        t3 = tg.create_task(runner.mcp("github", "get_issues", repo="myrepo"))
    # Max 8 parallel tasks
    ctx.risk = t1.result()
    ctx.price = t2.result()
    ctx.issues = t3.result()
```

### 10.3 Deterministic Random

```python
from cowboy_sdk import pvm_random

pvm_random.seed(42)                    # Deterministic seed
n = pvm_random.randint(1, 100)         # Random integer
f = pvm_random.random()                # [0, 1) float
item = pvm_random.choice(["a", "b"])   # Random choice
pvm_random.shuffle(my_list)            # In-place shuffle
b = pvm_random.randbytes(32)           # Random bytes
```

### 10.4 Block-Based Time

```python
from cowboy_sdk import pvm_time

height = pvm_time.block_height()       # Current block number
ts = pvm_time.time()                   # Block timestamp (seconds, float)
ts_ms = pvm_time.time_ms()             # Block timestamp (milliseconds)
```

---

## 11. CIP-20 Token API

```python
from cowboy_sdk import runtime

# Create token
token_id = runtime.token_create(
    name=b"MyCoin", symbol=b"MC", decimals=18,
    initial_supply=1000000, max_supply=None,
    transfer_hook=None, metadata_uri=None,
)

# Query
balance = runtime.token_balance_of(token_id, owner_addr)
supply = runtime.token_total_supply(token_id)
allowance = runtime.token_allowance(token_id, owner, spender)

# Transfer
runtime.token_transfer(token_id, to_addr, amount)
runtime.token_approve(token_id, spender_addr, amount)
runtime.token_transfer_from(token_id, from_addr, to_addr, amount)

# Mint / Burn (requires authority)
runtime.token_mint(token_id, to_addr, amount)
runtime.token_burn(token_id, amount)
```

---

## 12. Error Handling

All SDK errors inherit from `CowboyError`:

```
CowboyError
├── DeterminismError            # Non-deterministic operation used
├── StateConflictError          # Guard detected stale state
├── ReentrancyError             # Reentrant call blocked
├── LoopBoundExceeded           # @bounded_loop limit hit
├── CaptureTypeError            # Non-serializable capture value
├── ContinuationLimitError      # >8 awaits, nested await, etc.
├── ContinuationNotFoundError   # Missing continuation state
├── ContinuationCorruptedError  # State data corrupted
├── ContinuationSizeLimitError  # >64 KiB state
├── ContinuationCountLimitError # >100 active continuations
├── CycleLimitExceeded          # Out of compute cycles
├── CallDepthExceeded           # call() depth > 32
├── RunnerTimeoutError          # Runner task timed out
├── RunnerValidationError       # Result failed verification
├── DeterministicValidationError # Runners disagree
├── CodecError                  # CBOR encode/decode failure
├── AddressError                # Invalid address format
├── ActorNotFoundError          # Target Actor doesn't exist
└── ActorCallError              # call() target threw exception
```

---

## 13. PVM Compatibility Rules

These rules are **enforced by the PVM runtime**. Violating them causes consensus failure (chain fork).

| # | ❌ Forbidden | ✅ Alternative |
|---|-------------|---------------|
| 1 | `import time` | `from cowboy_sdk import pvm_time` |
| 2 | `import random` | `from cowboy_sdk import pvm_random` |
| 3 | Hardware `float` (FPU) | `SoftFloat = float` (PVM replaces globally) |
| 4 | `set()` | `ordered_set` from `cowboy_sdk.types` |
| 5 | `pickle` | `cowboy_sdk.codec` (Canonical CBOR) |
| 6 | `call()` depth > 32 | Limit call chains; use `cycles_limit` |
| 7 | > 8 `await` points per function | Split into multiple continuation functions |
| 8 | `await` in loops without `@bounded_loop` | Decorate with `@bounded_loop(max_iterations=N)` |
| 9 | Implicit cross-block variables | Use `capture()` explicitly |
| 10 | Rely on `send()` rollback | Complete `call()` ops first, then `send()` |

---

## 14. Deployment Guide

### 14.1 Deploy Actor

```bash
# Using cowboy CLI
cargo run -p cowboy-cli --bin cowboy -- \
    --indexer-url http://localhost:4000 \
    actor deploy \
    --code ./my_actor.py \
    --salt 00000000000000000000000000000001 \
    --private-key .cowboy/key \
    --cycles-limit 10000000 \
    --cells-limit 10000000 \
    --nonce 0
```

### 14.2 Call Handler

```bash
# Execute a handler
PAYLOAD=$(echo -n '{"message":"Hello"}' | xxd -p -c 9999)
cargo run -p cowboy-cli --bin cowboy -- \
    --indexer-url http://localhost:4000 \
    actor execute \
    --actor <ACTOR_ADDRESS> \
    --handler chat \
    --payload "$PAYLOAD" \
    --private-key .cowboy/key \
    --cycles-limit 5000000 \
    --cells-limit 5000000
```

### 14.3 Query Actor State

```bash
curl -s http://localhost:4000/actor/<ACTOR_ADDRESS>
```

### 14.4 Environment Variables

| Variable | Description |
|----------|-------------|
| `RPC_URL` | Chain RPC endpoint (default `http://localhost:4000`) |
| `PRIVATE_KEY_FILE` | Deployer private key file path |
| `OPENAI_API_KEY` | Required on Runner side for LLM tasks |
| `OPENAI_API_BASE` | OpenAI API base URL |
| `ANTHROPIC_API_KEY` | For Anthropic models |

---

## 15. Complete Example

A full LLM Chat Actor using all major SDK features:

```python
"""LLM Chat Actor — Complete cowboy_sdk example."""
import json
from cowboy_sdk import actor, runner, capture, CowboyModel, codec, runtime

# ── Data Model ──
class ChatEntry(CowboyModel):
    id: int
    sender: str
    message: str
    status: str
    block_submitted: int
    response: str = None

# ── Actor ──
@actor
class LLMChatActor:
    def init(self, payload):
        runtime.charge_gas(1000)
        ctx = runtime.context()
        self.storage["owner"] = ctx.get("sender", b"").hex()
        self.storage["chat_count"] = 0
        self.storage["cfg:system_prompt"] = "You are a helpful assistant."
        self.storage["cfg:max_tokens"] = 1024
        return b"ok: initialized"

    @runner.continuation
    async def chat(self, payload):
        runtime.charge_gas(2000)
        obj = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        message = str(obj.get("message", "")).strip()
        if not message:
            raise ValueError("empty message")

        chat_id = self.storage.get("chat_count", 0)
        self.storage["chat_count"] = chat_id + 1

        entry = ChatEntry(
            id=chat_id, sender=runtime.get_sender().hex(),
            message=message, status="pending",
            block_submitted=runtime.get_block_height(),
        )
        self.storage[f"chat:{chat_id}"] = entry.to_dict()

        # Persist variables across await
        ctx = capture()
        ctx.chat_id = chat_id

        # FSM splits here: send LLM job → wait → resume
        result = await runner.llm(
            message,
            system_prompt=self.storage.get("cfg:system_prompt", ""),
            max_tokens=self.storage.get("cfg:max_tokens", 1024),
        )

        # __resume segment
        response = str(result) if result else ""
        raw = self.storage.get(f"chat:{ctx.chat_id}", {})
        raw["response"] = response
        raw["status"] = "done"
        self.storage[f"chat:{ctx.chat_id}"] = raw
        runtime.emit_event("chat.done", {"chat_id": ctx.chat_id})
        return b"ok"

    def on_runner_result(self, payload):
        msg = codec.decode(payload) if isinstance(payload, bytes) else payload
        if isinstance(msg, dict) and msg.get("reply_handler"):
            runner.handle_runner_result(self, msg)
        return b"ok"

    def get_response(self, payload):
        runtime.charge_gas(200)
        obj = json.loads(payload) if isinstance(payload, (str, bytes)) else payload or {}
        chat_id = obj.get("chat_id", self.storage.get("chat_count", 1) - 1)
        entry = self.storage.get(f"chat:{int(chat_id)}")
        return json.dumps(entry).encode("utf-8") if entry else b"not found"

# ── PVM Entry Points ──
def _a(): return LLMChatActor()
def init(p):              return _a().init(p)
def chat(p):              return _a().chat(p)
def chat__resume(p):      return _a().chat__resume(p)
def on_runner_result(p):  return _a().on_runner_result(p)
def get_response(p):      return _a().get_response(p)
```

---

## 16. API Reference

### Top-Level Imports

```python
from cowboy_sdk import (
    # Actor system
    actor, ActorRef, derive_actor_address,
    # Call primitives
    call, send,
    # Continuation
    capture, Capture, save_cont, load_cont, delete_cont,
    # Runner (use as runner.llm, runner.continuation, etc.)
    runner,
    # Safety
    reentrancy_guard, storage_guard, GuardedValue, GuardSet,
    bounded_loop, BoundedRange, check_iteration,
    # Verification
    Verify, VerifyBuilder,
    # Async tools
    Retry, TaskGroup,
    # Type system
    CowboyModel, SoftFloat, ordered_set, BlockHeight, Address,
    # Sub-modules
    codec, runtime, pvm_random, pvm_time, pvm_sys, errors,
)
```

### Key Function Signatures

```python
# call.py
call(target, method: str, args=None, cycles_limit: int = 100_000) -> any

# send.py
send(target, payload=None, *, raw: bool = False) -> None

# continuation.py
capture() -> Capture
save_cont(cid, state, ctx, handler, timeout_blocks=0, guard_keys=None)
load_cont(cid) -> dict
delete_cont(cid)
new_cid(self_obj, name: str) -> bytes

# runner.py
runner.llm(*args, **kwargs) -> _RunnerAwaitable
runner.http(*args, **kwargs) -> _RunnerAwaitable
runner.mcp(server, tool, *args, **kwargs) -> _RunnerAwaitable
runner.continuation  # Decorator
runner.handle_runner_result(self, msg) -> None

# runtime.py
runtime.context() -> dict
runtime.get_sender() -> bytes
runtime.get_actor_address() -> bytes
runtime.get_block_height() -> int
runtime.get_tx_hash() -> bytes
runtime.get_timestamp_ms() -> int
runtime.charge_gas(amount: int) -> None
runtime.emit_event(name: str, payload) -> None
runtime.get_state(key: bytes) -> bytes | None
runtime.set_state(key: bytes, value: bytes) -> None
runtime.delete_state(key: bytes) -> None
runtime.token_create(...) -> bytes
runtime.token_balance_of(token_id, owner) -> int | None
runtime.token_transfer(token_id, to, amount) -> None
# ... (see runtime.py for full token API)

# codec.py
codec.encode(value) -> bytes
codec.decode(data: bytes) -> any

# models.py
CowboyModel.to_cbor() -> bytes
CowboyModel.from_cbor(data: bytes) -> CowboyModel
CowboyModel.to_dict() -> dict
CowboyModel.from_dict(d: dict) -> CowboyModel
CowboyModel.schema() -> dict
CowboyModel.validate() -> None
```

---

> **Source Code**: `node/pvm/Lib/cowboy_sdk/`
> **Tests**: `node/pvm/Lib/cowboy_sdk/tests/` & `node/pvm/Lib/cowboy_sdk_tests/`
> **Examples**: `node/examples/llm_chat2/` (SDK version), `node/examples/token/`
> **Spec**: `refs/cips/cip-6-sdk.md`
