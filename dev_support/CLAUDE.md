# Cowboy Actor Development — Claude Code Rules

You are developing on-chain Actors for the **Cowboy blockchain** using `cowboy_sdk` (CIP-6).
Cowboy runs a deterministic Python VM (PVM). Every node replays the same code and must produce
identical state. Breaking determinism causes consensus failure (chain fork).

> Always read `refs/dev_support/cowboy_sdk_developer_manual.md` before writing Actor code.
> Reference implementation: `node/examples/llm_chat2/llm_actor2.py`
> SDK source: `node/pvm/Lib/cowboy_sdk/`

---

## 🚨 PVM IRON RULES — Never Violate

| ❌ Forbidden | ✅ Use Instead |
|-------------|--------------|
| `import time` | `from cowboy_sdk import pvm_time` |
| `import random` | `from cowboy_sdk import pvm_random` |
| `set()` or `frozenset()` | `from cowboy_sdk.types import ordered_set` |
| `pickle` | `from cowboy_sdk import codec` (Canonical CBOR) |
| `call()` depth > 32 | Limit call chains; always pass `cycles_limit` |
| > 8 `await` in one async fn | Split into multiple continuation functions |
| `await` in loops without guard | Use `@bounded_loop(max_iterations=N)` |
| `return` in `@runner.continuation` before `await` | Use `raise ValueError(...)` for early exit |
| Closures/lambdas in `capture()` | Only primitives: int, str, bytes, float, bool, None, list, dict |

`float` hardware FPU is globally replaced by SoftFloat in PVM runtime — no need to change code,
but use `SoftFloat` as a type annotation for clarity.

---

## Actor Structure Pattern

Every Actor MUST follow this pattern:

```python
import json
from cowboy_sdk import actor, runner, capture, CowboyModel, codec, runtime

@actor
class MyActor:
    def init(self, payload):
        """Initialize state. Called once on deploy."""
        runtime.charge_gas(500)
        # self.storage auto CBOR-encodes/decodes
        self.storage["key"] = "value"
        return b"ok"

    def my_handler(self, payload):
        """Synchronous handler."""
        runtime.charge_gas(200)
        obj = json.loads(payload) if isinstance(payload, (str, bytes)) else (payload or {})
        # ... logic ...
        return json.dumps({"result": "..."}).encode("utf-8")

    @runner.continuation          # REQUIRED for any async def with await
    async def async_handler(self, payload):
        """Async handler with off-chain computation."""
        runtime.charge_gas(1000)
        obj = json.loads(payload) if isinstance(payload, (str, bytes)) else (payload or {})

        # REQUIRED before any await: declare cross-block variables
        ctx = capture()
        ctx.my_var = obj.get("key")   # Only CBOR-serializable types!

        # FSM splits here — Runner job is sent, tx ends
        result = await runner.llm(
            ctx.my_var,
            system_prompt="...",
            max_tokens=512,
        )
        # Code below runs in __resume (next block after Runner callback)

        self.storage["result"] = str(result)
        runtime.emit_event("done", {"result": str(result)[:100]})
        return b"ok"

    def on_runner_result(self, payload):
        """Runner callback entry — routes to __{method}__resume."""
        msg = codec.decode(payload) if isinstance(payload, bytes) else payload
        if isinstance(msg, dict) and msg.get("reply_handler"):
            runner.handle_runner_result(self, msg)
        return b"ok"


# ── PVM ENTRY POINTS (module-level, required) ────────────────────
def _a(): return MyActor()

def init(payload):              return _a().init(payload)
def my_handler(payload):        return _a().my_handler(payload)
def async_handler(payload):     return _a().async_handler(payload)
def async_handler__resume(payload): return _a().async_handler__resume(payload)
def on_runner_result(payload):  return _a().on_runner_result(payload)
```

**Rules for module-level functions:**
- Every method on the `@actor` class needs a matching module-level function
- For every `@runner.continuation` method `foo`, also expose `foo__resume`
- The PVM finds functions by name — don't rename them

---

## self.storage

```python
self.storage["key"] = value          # Write (auto CBOR encode)
val = self.storage["key"]            # Read (auto CBOR decode) — KeyError if missing
val = self.storage.get("key", None)  # Read with default
del self.storage["key"]              # Delete
"key" in self.storage                # Check existence
```

Supported value types: `int`, `float`, `str`, `bytes`, `bool`, `None`, `list`, `dict`

---

## Structured Data (CowboyModel)

```python
from cowboy_sdk import CowboyModel

class Order(CowboyModel):
    id: str
    amount: int
    status: str = "pending"   # Optional field with default

order = Order(id="1", amount=100)
self.storage["order:1"] = order.to_dict()          # Store
raw = self.storage.get("order:1")
order = Order.from_dict(raw) if raw else None       # Restore
```

Do NOT use `set` or `frozenset` fields in CowboyModel.

---

## Runner Tasks

```python
# LLM inference
result = await runner.llm(prompt, system_prompt="...", max_tokens=1024)

# HTTP request
result = await runner.http("https://api.example.com/data", method="GET")

# MCP tool
result = await runner.mcp("filesystem", "read_file", path="/data.txt")

# With verification
result = await runner.llm(
    prompt,
    verify=(Verify.builder()
        .mode("consensus")
        .runners(3).threshold(2)
        .check(Verify.json_schema_valid(MyModel.schema()))
        .build()),
    timeout_blocks=100,
)
```

---

## Deterministic Time & Random

```python
# Time (NOT import time)
from cowboy_sdk import pvm_time
height = pvm_time.block_height()   # Current block number
ts = pvm_time.time()                # Seconds since epoch (block-based)

# Random (NOT import random)
from cowboy_sdk import pvm_random
n = pvm_random.randint(1, 100)
item = pvm_random.choice(["a", "b", "c"])
```

---

## Runtime API

```python
from cowboy_sdk import runtime

ctx = runtime.context()            # Full execution context
sender = runtime.get_sender()      # bytes (20-byte address)
height = runtime.get_block_height()
runtime.charge_gas(1000)           # Required in every handler
runtime.emit_event("name", {...})  # Emit on-chain event
```

---

## Deployment

```bash
# Deploy
cargo run -p cowboy-cli --bin cowboy -- \
    --indexer-url "${RPC_URL:-http://localhost:4000}" \
    actor deploy \
    --code ./my_actor.py \
    --salt 00000000000000000000000000000001 \
    --private-key .cowboy/key \
    --cycles-limit 10000000 --cells-limit 10000000 --nonce 0

# Call a handler
PAYLOAD=$(echo -n '{"key":"value"}' | xxd -p -c 9999)
cargo run -p cowboy-cli --bin cowboy -- \
    --indexer-url "${RPC_URL:-http://localhost:4000}" \
    actor execute \
    --actor <ACTOR_ADDRESS> --handler my_handler \
    --payload "$PAYLOAD" \
    --private-key .cowboy/key \
    --cycles-limit 5000000 --cells-limit 5000000
```

---

## Common Mistakes

1. **No `runtime.charge_gas()`** — Every handler must charge gas
2. **Missing `__resume` entry point** — Always expose `foo__resume` alongside `foo`
3. **`capture()` after business logic** — Place `capture()` at the START of the continuation fn, set all ctx vars before `await`
4. **`send()` before `call()`** — Always complete fallible operations first
5. **`return b"..."` before `await`** — Use `raise ValueError(...)` for early exit in continuations
6. **Storing Python objects in `capture()`** — Only primitives; convert models with `.to_dict()`
