#!/usr/bin/env python3
"""
Cowboy Actor MCP Server
========================
Exposes Cowboy Actor development tools to Claude Code (and any MCP client).

Tools:
  cowboy_deploy      — Deploy actor code to chain
  cowboy_call        — Call an actor handler (write)
  cowboy_query       — Call an actor handler (read-only, lower gas)
  cowboy_status      — Get actor storage state summary
  cowboy_validate    — Syntax-check + PVM rule lint actor code
  cowboy_sdk_docs    — Return SDK documentation for a topic
  cowboy_logs        — Tail recent indexer events for an actor

Install:
  pip install mcp

Run (stdio mode, for Claude Code):
  python cowboy_mcp_server.py

Config in Claude Code (~/.claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "cowboy": {
        "command": "python",
        "args": ["/path/to/cowboy_mcp_server.py"],
        "env": {
          "RPC_URL": "http://localhost:4000",
          "COWBOY_WORKSPACE": "/path/to/workspace",
          "PRIVATE_KEY_FILE": "/path/to/.cowboy/key"
        }
      }
    }
  }
"""

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# ── Configuration ──────────────────────────────────────────────────────────────

RPC_URL = os.environ.get("RPC_URL", "http://localhost:4000")
WORKSPACE = Path(os.environ.get("COWBOY_WORKSPACE", Path(__file__).parent))
PRIVATE_KEY_FILE = os.environ.get(
    "PRIVATE_KEY_FILE", str(WORKSPACE / ".cowboy" / "key")
)
# PVM_LIB: SDK source tree (for cowboy_sdk import in validator)
# Falls back to None when cowboy_sdk is pip-installed system-wide
_pvm_lib_default = WORKSPACE / "node" / "pvm" / "Lib"
PVM_LIB = Path(os.environ.get("PVM_LIB", str(_pvm_lib_default)))
DEFAULT_CYCLES = int(os.environ.get("DEFAULT_CYCLES", "5000000"))
DEFAULT_CELLS = int(os.environ.get("DEFAULT_CELLS", "5000000"))

# CLI resolution: COWBOY_CLI_PATH > PATH 'cowboy' binary > cargo fallback
_cowboy_cli_path = os.environ.get("COWBOY_CLI_PATH", "")

def _resolve_cli() -> list[str]:
    """Return the command prefix to invoke the cowboy CLI."""
    if _cowboy_cli_path:
        return [_cowboy_cli_path]
    # Check if 'cowboy' binary is on PATH
    import shutil
    if shutil.which("cowboy"):
        return ["cowboy"]
    # Fallback: cargo run (full node dev setup)
    return ["cargo", "run", "-q", "-p", "cowboy-cli", "--bin", "cowboy", "--"]

# ── MCP Server ─────────────────────────────────────────────────────────────────

server = Server("cowboy-actor")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run a shell command, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE),
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def _cowboy_cli(*args: str, timeout: int = 60) -> tuple[int, str, str]:
    """Run cowboy CLI with standard flags. Uses pre-built binary or cargo fallback."""
    cmd = [
        *_resolve_cli(),
        "--indexer-url", RPC_URL,
        *args,
    ]
    return _run(cmd, timeout=timeout)


def _hex_payload(json_str: str) -> str:
    """Encode JSON string to hex bytes for --payload arg."""
    return json_str.encode("utf-8").hex()


def _decode_storage_val(hex_val: str) -> Any:
    """Attempt to decode a CBOR storage value."""
    try:
        import sys as _sys
        lib = str(PVM_LIB)
        if lib not in _sys.path:
            _sys.path.insert(0, lib)
        from cowboy_sdk import codec
        return codec.decode(bytes.fromhex(hex_val))
    except Exception:
        return f"<hex:{hex_val[:20]}...>" if len(hex_val) > 20 else f"<hex:{hex_val}>"


def _format_storage(storage: dict) -> str:
    """Format actor storage for readable output."""
    lines = []
    for k_hex, v_hex in sorted(storage.items()):
        try:
            key = bytes.fromhex(k_hex).decode("utf-8", errors="replace")
        except Exception:
            key = k_hex
        val = _decode_storage_val(v_hex)
        val_str = repr(val)
        if len(val_str) > 100:
            val_str = val_str[:97] + "..."
        lines.append(f"  {key:<32} = {val_str}")
    return "\n".join(lines) if lines else "  (empty)"


# ── PVM Rule Linter ────────────────────────────────────────────────────────────

FORBIDDEN_PATTERNS = [
    (r"\bimport time\b",          "Rule 1: use `from cowboy_sdk import pvm_time` instead of `import time`"),
    (r"\bimport random\b",        "Rule 2: use `from cowboy_sdk import pvm_random` instead of `import random`"),
    (r"\bset\(\)",                "Rule 4: use `ordered_set` from cowboy_sdk.types instead of `set()`"),
    (r"\bpickle\b",               "Rule 5: use `cowboy_sdk.codec` (CBOR) instead of `pickle`"),
    (r"\btime\.time\(\)",         "Rule 1: use `pvm_time.time()` instead of `time.time()`"),
    (r"\brandom\.\w+\(",          "Rule 2: use `pvm_random.*` instead of `random.*`"),
    (r"async def.*:\n(?:(?!@runner\.continuation|@actor\.continuation).*\n)*\s+await ",
     "Rule: async functions with `await` must use @runner.continuation or @actor.continuation"),
]

def _lint_pvm_rules(code: str) -> list[str]:
    """Check code for PVM violations. Returns list of warning strings."""
    warnings = []
    lines = code.splitlines()

    # Check for forbidden imports/patterns
    for pattern, message in FORBIDDEN_PATTERNS[:6]:  # simple patterns only
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                warnings.append(f"  Line {i}: {message}\n    → {line.strip()}")

    # Check for async def without @runner.continuation
    for i, line in enumerate(lines, 1):
        if re.match(r"\s+async def \w+", line):
            # Look back for decorator
            j = i - 2
            has_decorator = False
            while j >= 0 and j >= i - 4:
                prev = lines[j].strip()
                if "runner.continuation" in prev or "actor.continuation" in prev:
                    has_decorator = True
                    break
                if prev.startswith("def ") or (prev.startswith("@") and "continuation" not in prev):
                    break
                j -= 1
            if not has_decorator:
                warnings.append(
                    f"  Line {i}: async def missing @runner.continuation decorator\n"
                    f"    → {line.strip()}"
                )

    # Check for capture() usage
    for i, line in enumerate(lines, 1):
        if "await runner." in line or "await actor." in line:
            # Look for capture() call before this
            found_capture = any("capture()" in lines[j] for j in range(max(0, i - 20), i))
            if not found_capture:
                warnings.append(
                    f"  Line {i}: `await` found without `capture()` above it\n"
                    f"    → {line.strip()}\n"
                    f"    Add: ctx = capture() before this await"
                )
            break  # Only report first occurrence

    # Check for __resume entry points
    continuation_methods = []
    module_funcs = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("@runner.continuation") or stripped.startswith("@actor.continuation"):
            # Next def is the continuation method
            for j in range(i, min(i + 5, len(lines))):
                m = re.match(r"\s+(?:async )?def (\w+)\(", lines[j])
                if m:
                    continuation_methods.append(m.group(1))
                    break
        m = re.match(r"^def (\w+)\(", stripped)
        if m:
            module_funcs.append(m.group(1))

    for method in continuation_methods:
        resume_name = f"{method}__resume"
        if resume_name not in module_funcs:
            warnings.append(
                f"  Missing module-level entry point: `def {resume_name}(payload):`\n"
                f"    PVM cannot route Runner callbacks without it"
            )

    # Check charge_gas in handlers
    in_method = False
    method_name = ""
    has_charge_gas = False
    for i, line in enumerate(lines, 1):
        m = re.match(r"    (?:async )?def (\w+)\(self", line)
        if m:
            if in_method and not has_charge_gas and method_name not in ("__init__",):
                warnings.append(
                    f"  Method `{method_name}` is missing `runtime.charge_gas()`"
                )
            in_method = True
            method_name = m.group(1)
            has_charge_gas = False
        if in_method and "charge_gas" in line:
            has_charge_gas = True

    return warnings


# ── Tools ──────────────────────────────────────────────────────────────────────

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="cowboy_deploy",
            description=(
                "Deploy a Cowboy Actor Python file to the chain. "
                "Returns the deployed Actor address. "
                "Use this after writing or editing actor code."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code_path": {
                        "type": "string",
                        "description": "Absolute or workspace-relative path to the .py actor file"
                    },
                    "salt": {
                        "type": "string",
                        "description": "32-hex-char deployment salt (default: random-ish based on filename)",
                        "default": ""
                    },
                },
                "required": ["code_path"],
            },
        ),
        types.Tool(
            name="cowboy_call",
            description=(
                "Call an Actor handler that writes state (transaction). "
                "Use for init, transfer, chat, and other state-modifying handlers."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "actor_address": {"type": "string", "description": "Actor address (0x...)"},
                    "handler": {"type": "string", "description": "Handler method name"},
                    "payload": {
                        "type": "string",
                        "description": "JSON payload string, e.g. '{\"message\": \"Hello\"}'",
                        "default": "{}"
                    },
                    "cycles_limit": {
                        "type": "integer",
                        "description": "Gas limit (default 5000000)",
                        "default": 5000000
                    },
                },
                "required": ["actor_address", "handler"],
            },
        ),
        types.Tool(
            name="cowboy_query",
            description=(
                "Call an Actor handler that reads state (lower gas, for queries). "
                "Use for get_balance, get_status, get_response, get_info, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "actor_address": {"type": "string", "description": "Actor address (0x...)"},
                    "handler": {"type": "string", "description": "Handler method name"},
                    "payload": {
                        "type": "string",
                        "description": "JSON payload string",
                        "default": "{}"
                    },
                },
                "required": ["actor_address", "handler"],
            },
        ),
        types.Tool(
            name="cowboy_status",
            description=(
                "Get the current storage state of an Actor. "
                "Shows all stored key-value pairs (CBOR decoded). "
                "Use after calling handlers to verify state changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "actor_address": {"type": "string", "description": "Actor address (0x...)"},
                },
                "required": ["actor_address"],
            },
        ),
        types.Tool(
            name="cowboy_validate",
            description=(
                "Syntax-check and PVM lint an Actor Python file. "
                "Detects: import time/random violations, missing @runner.continuation, "
                "missing capture(), missing __resume entry points, missing charge_gas(). "
                "Always run this before cowboy_deploy."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code_path": {
                        "type": "string",
                        "description": "Path to the .py actor file to validate"
                    },
                },
                "required": ["code_path"],
            },
        ),
        types.Tool(
            name="cowboy_sdk_docs",
            description=(
                "Return SDK documentation and code examples for a specific topic. "
                "Use when unsure about API usage. "
                "Topics: actor, call, send, continuation, capture, runner, verify, "
                "types, guards, bounded_loop, retry, taskgroup, token, errors, rules"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to look up",
                        "enum": [
                            "actor", "call", "send", "continuation", "capture",
                            "runner", "verify", "types", "guards", "bounded_loop",
                            "retry", "taskgroup", "token", "errors", "rules", "deploy"
                        ]
                    },
                },
                "required": ["topic"],
            },
        ),
        types.Tool(
            name="cowboy_logs",
            description=(
                "Fetch recent events emitted by an Actor from the indexer. "
                "Useful to verify LLM callbacks arrived or trace execution flow."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "actor_address": {"type": "string", "description": "Actor address (0x...)"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent events to return (default 20)",
                        "default": 20
                    },
                },
                "required": ["actor_address"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = await _dispatch_tool(name, arguments)
    except Exception as e:
        result = f"❌ Tool error: {e}"
    return [types.TextContent(type="text", text=result)]


async def _dispatch_tool(name: str, args: dict) -> str:
    if name == "cowboy_deploy":
        return await _tool_deploy(args)
    elif name == "cowboy_call":
        return await _tool_call(args)
    elif name == "cowboy_query":
        return await _tool_query(args)
    elif name == "cowboy_status":
        return await _tool_status(args)
    elif name == "cowboy_validate":
        return await _tool_validate(args)
    elif name == "cowboy_sdk_docs":
        return _tool_sdk_docs(args)
    elif name == "cowboy_logs":
        return await _tool_logs(args)
    else:
        return f"Unknown tool: {name}"


# ── Tool Implementations ───────────────────────────────────────────────────────

async def _tool_deploy(args: dict) -> str:
    code_path_str = args["code_path"]
    code_path = (WORKSPACE / code_path_str).resolve()
    if not code_path.exists():
        return f"❌ File not found: {code_path}"

    salt = args.get("salt", "")
    if not salt:
        # Generate deterministic salt from filename
        name_bytes = code_path.stem.encode("utf-8")[:8].ljust(8, b"\x00")
        salt = name_bytes.hex().ljust(32, "0")

    if not Path(PRIVATE_KEY_FILE).exists():
        return f"❌ Private key not found: {PRIVATE_KEY_FILE}\nSet PRIVATE_KEY_FILE env var."

    # First validate
    code = code_path.read_text()
    warnings = _lint_pvm_rules(code)
    warn_block = ""
    if warnings:
        warn_block = "\n⚠️  Lint warnings (non-fatal):\n" + "\n".join(warnings) + "\n"

    rc, stdout, stderr = _cowboy_cli(
        "actor", "deploy",
        "--code", str(code_path),
        "--salt", salt,
        "--private-key", PRIVATE_KEY_FILE,
        "--cycles-limit", str(DEFAULT_CYCLES * 2),
        "--cells-limit", str(DEFAULT_CELLS * 2),
        "--nonce", "0",
        timeout=120,
    )

    if rc != 0:
        return (
            f"❌ Deploy failed (exit {rc})\n"
            f"{warn_block}"
            f"stderr: {stderr}\nstdout: {stdout}"
        )

    # Try to extract actor address from output
    addr_match = re.search(r"0x[0-9a-fA-F]{40}", stdout + stderr)
    addr = addr_match.group(0) if addr_match else "(check indexer)"

    return (
        f"✅ Deployed successfully!\n"
        f"Actor address: {addr}\n"
        f"Salt: {salt}\n"
        f"File: {code_path.name}\n"
        f"{warn_block}"
        f"\nNext steps:\n"
        f"  1. cowboy_call('{addr}', 'init', '{{...}}')\n"
        f"  2. cowboy_status('{addr}')"
    )


async def _tool_call(args: dict) -> str:
    actor = args["actor_address"]
    handler = args["handler"]
    payload = args.get("payload", "{}")
    cycles = args.get("cycles_limit", DEFAULT_CYCLES)

    if not Path(PRIVATE_KEY_FILE).exists():
        return f"❌ Private key not found: {PRIVATE_KEY_FILE}"

    hex_payload = _hex_payload(payload)
    rc, stdout, stderr = _cowboy_cli(
        "actor", "execute",
        "--actor", actor,
        "--handler", handler,
        "--payload", hex_payload,
        "--private-key", PRIVATE_KEY_FILE,
        "--cycles-limit", str(cycles),
        "--cells-limit", str(DEFAULT_CELLS),
        timeout=60,
    )

    combined = (stdout + "\n" + stderr).strip()
    if rc != 0:
        return f"❌ Call failed (exit {rc})\n{combined}"

    return (
        f"✅ Called {handler} on {actor}\n"
        f"Payload: {payload}\n"
        f"Output: {combined or '(none)'}"
    )


async def _tool_query(args: dict) -> str:
    """Same as call but with lower gas limit — semantically read-only."""
    args_copy = dict(args)
    args_copy.setdefault("cycles_limit", 1_000_000)
    return await _tool_call(args_copy)


async def _tool_status(args: dict) -> str:
    actor = args["actor_address"]

    try:
        import urllib.request
        url = f"{RPC_URL}/actor/{actor}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return f"❌ Could not fetch actor state: {e}\nURL: {RPC_URL}/actor/{actor}"

    storage = data.get("storage", {})
    formatted = _format_storage(storage)

    return (
        f"Actor: {data.get('address', actor)}\n"
        f"Balance: {data.get('balance', 0)}\n"
        f"Nonce: {data.get('nonce', 0)}\n"
        f"Storage ({len(storage)} keys):\n"
        f"{formatted}"
    )


async def _tool_validate(args: dict) -> str:
    code_path_str = args["code_path"]
    code_path = (WORKSPACE / code_path_str).resolve()
    if not code_path.exists():
        return f"❌ File not found: {code_path}"

    code = code_path.read_text()

    # 1. Python syntax check
    rc, stdout, stderr = _run(
        [sys.executable, "-m", "py_compile", str(code_path)]
    )
    if rc != 0:
        return f"❌ Syntax error:\n{stderr}"

    # 2. Import check with PVM_LIB on path
    env = os.environ.copy()
    pythonpath = str(PVM_LIB)
    if "PYTHONPATH" in env:
        pythonpath = f"{pythonpath}:{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    result = subprocess.run(
        [sys.executable, "-c", f"import importlib.util; "
         f"spec = importlib.util.spec_from_file_location('actor', '{code_path}'); "
         f"mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); "
         f"print('import OK')"],
        capture_output=True, text=True, env=env, timeout=15, cwd=str(WORKSPACE)
    )
    import_ok = result.returncode == 0
    import_msg = result.stdout.strip() if import_ok else result.stderr.strip()

    # 3. PVM lint
    warnings = _lint_pvm_rules(code)

    # 4. Check module-level entry points
    handler_pattern = re.compile(r"^    (?:async )?def (\w+)\(self", re.MULTILINE)
    module_pattern = re.compile(r"^def (\w+)\(", re.MULTILINE)
    class_methods = handler_pattern.findall(code)
    module_fns = module_pattern.findall(code)

    missing_entry_points = []
    for method in class_methods:
        if method.startswith("_"):
            continue
        if method not in module_fns:
            missing_entry_points.append(method)

    lines = []
    if import_ok:
        lines.append(f"✅ Syntax OK")
        lines.append(f"✅ Import OK")
    else:
        lines.append(f"❌ Import error:\n{import_msg}")

    if warnings:
        lines.append(f"\n⚠️  PVM Rule Violations ({len(warnings)}):")
        lines.extend(warnings)
    else:
        lines.append("✅ No PVM rule violations")

    if missing_entry_points:
        lines.append(f"\n⚠️  Missing module-level entry points:")
        for m in missing_entry_points:
            lines.append(f"  def {m}(payload): return _get_actor().{m}(payload)")
    else:
        lines.append("✅ All entry points present")

    return "\n".join(lines)


def _tool_sdk_docs(args: dict) -> str:
    topic = args.get("topic", "")
    docs = _SDK_DOCS.get(topic, f"Unknown topic: {topic}. Available: {', '.join(_SDK_DOCS)}")
    return docs


async def _tool_logs(args: dict) -> str:
    actor = args["actor_address"]
    limit = args.get("limit", 20)

    try:
        import urllib.request
        url = f"{RPC_URL}/actor/{actor}/events?limit={limit}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        # Fallback: try generic events endpoint
        return (
            f"Could not fetch events: {e}\n"
            f"Try: curl {RPC_URL}/actor/{actor}/events\n"
            f"or:  curl {RPC_URL}/events?actor={actor}&limit={limit}"
        )

    if isinstance(data, list):
        events = data[:limit]
    else:
        events = data.get("events", data.get("items", []))[:limit]

    if not events:
        return f"No events found for {actor}"

    lines = [f"Recent events for {actor} (last {len(events)}):"]
    for ev in events:
        name = ev.get("name", ev.get("event", "?"))
        payload = ev.get("payload", ev.get("data", {}))
        block = ev.get("block_height", ev.get("block", "?"))
        lines.append(f"  [{block}] {name}: {json.dumps(payload)[:120]}")

    return "\n".join(lines)


# ── SDK Documentation Snippets ─────────────────────────────────────────────────

_SDK_DOCS: dict[str, str] = {
    "actor": textwrap.dedent("""
        # @actor — Actor Decorator

        from cowboy_sdk import actor, runtime

        @actor
        class MyActor:
            # Injected automatically:
            #   self.address  — Actor's 20-byte address (bytes)
            #   self.storage  — CBOR key-value store proxy

            def init(self, payload):
                runtime.charge_gas(500)
                self.storage["owner"] = runtime.get_sender().hex()
                return b"ok"

        # REQUIRED: module-level entry points
        def _a(): return MyActor()
        def init(payload): return _a().init(payload)
    """).strip(),

    "call": textwrap.dedent("""
        # call() — Synchronous cross-Actor call (T+0, atomic)

        from cowboy_sdk import call

        result = call(
            target="0xActorAddress...",   # 20-byte address
            method="get_balance",
            args={"user": "alice"},
            cycles_limit=5000            # explicit limit required
        )
        # result is CBOR-decoded return value of target method
        # Failure in callee cascades rollback to caller
        # Max call depth: 32 levels
    """).strip(),

    "send": textwrap.dedent("""
        # send() — Async one-way message (T+N, next block, irrevocable)

        from cowboy_sdk import send

        send(target="0xActorAddress...", payload={"action": "notify"})

        # ⚠️ CRITICAL: Always call() first, send() last
        # ✅ Correct pattern:
        result = call(target, "reserve", args)
        if not result["ok"]:
            raise Exception("failed")
        send(notify_target, {"msg": "done"})  # Only after all calls succeed
    """).strip(),

    "continuation": textwrap.dedent("""
        # @runner.continuation — FSM async compilation

        from cowboy_sdk import actor, runner, capture, runtime

        @actor
        class MyActor:
            @runner.continuation                         # Required!
            async def process(self, payload):
                runtime.charge_gas(1000)

                ctx = capture()                          # BEFORE await
                ctx.data = json.loads(payload)["input"]  # Only primitives

                result = await runner.llm(ctx.data)      # FSM split point

                # Below runs in __resume (next block)
                self.storage["result"] = str(result)
                return b"ok"

            def on_runner_result(self, payload):
                from cowboy_sdk import codec
                msg = codec.decode(payload) if isinstance(payload, bytes) else payload
                if isinstance(msg, dict) and msg.get("reply_handler"):
                    runner.handle_runner_result(self, msg)
                return b"ok"

        # REQUIRED module-level entry points:
        def _a(): return MyActor()
        def process(payload):          return _a().process(payload)
        def process__resume(payload):  return _a().process__resume(payload)
        def on_runner_result(payload): return _a().on_runner_result(payload)
    """).strip(),

    "capture": textwrap.dedent("""
        # capture() — Cross-block variable persistence

        from cowboy_sdk import capture

        ctx = capture()              # Create context (call before await)
        ctx.user_id = "alice"        # str ✅
        ctx.amount = 100             # int ✅
        ctx.items = ["a", "b"]       # list ✅
        ctx.data = {"k": "v"}        # dict ✅
        ctx.flag = True              # bool ✅
        ctx.model = MyModel(...)     # ❌ Use ctx.model = MyModel(...).to_dict()
        ctx.fn = lambda x: x        # ❌ CaptureTypeError - no closures!

        result = await runner.llm(ctx.user_id)

        # After resume, ctx is restored automatically
        print(ctx.user_id)           # "alice"
    """).strip(),

    "runner": textwrap.dedent("""
        # runner.* — Off-chain computation tasks

        from cowboy_sdk import runner

        # Inside @runner.continuation async function:

        # LLM inference
        result = await runner.llm(
            "What is Bitcoin?",
            system_prompt="Answer concisely",
            max_tokens=512,
            temperature=0.7,
        )

        # HTTP request
        result = await runner.http(
            "https://api.example.com/price",
            method="GET",
        )

        # MCP tool
        result = await runner.mcp("filesystem", "read_file", path="/data.txt")

        # With timeout + verification
        result = await runner.llm(
            prompt,
            timeout_blocks=100,
            verify=(Verify.builder()
                .mode("consensus").runners(3).threshold(2)
                .check(Verify.no_prompt_leak())
                .build()),
        )
    """).strip(),

    "verify": textwrap.dedent("""
        # Verify — Runner result verification

        from cowboy_sdk import Verify

        spec = (Verify.builder()
            .mode("consensus")           # none / consensus / deterministic / tee
            .runners(3)                  # 1-21 nodes
            .threshold(2)               # min agreement
            .check(Verify.json_schema_valid(MyModel.schema()))
            .check(Verify.numeric_range("price", 0.01, 9999))
            .check(Verify.no_prompt_leak())
            .check(Verify.contains_all(["recommendation:"]))
            .check(Verify.length_bounds(10, 500))
            .timeout_blocks(100)
            .build())

        # Checkers: exact_match, json_schema_valid, structured_match,
        # majority_vote, supermajority_vote, numeric_tolerance, numeric_range,
        # set_equality, contains_all, contains_none, regex_match,
        # length_bounds, semantic_similarity, no_prompt_leak,
        # entropy_check, custom, custom_actor, format_check, field_exists
    """).strip(),

    "types": textwrap.dedent("""
        # PVM-safe types

        from cowboy_sdk.types import SoftFloat, ordered_set, BlockHeight, Address
        from cowboy_sdk import CowboyModel

        # CowboyModel — structured data with CBOR support
        class Order(CowboyModel):
            id: str
            amount: int
            price: float       # SoftFloat on PVM
            items: list
            # FORBIDDEN: set, frozenset fields

        order = Order(id="1", amount=100, price=1.5, items=["a"])
        cbor = order.to_cbor()
        d = order.to_dict()           # store in self.storage
        o2 = Order.from_dict(d)       # restore from self.storage
        schema = Order.schema()       # for Verify.json_schema_valid()

        # ordered_set — deterministic iteration
        s = ordered_set(["a", "b", "c"])
        s.add("d"); "a" in s

        # BlockHeight — semantic wrapper for int
        h = BlockHeight(12345)  # prints as "block#12345"

        # Address — 20-byte Ethereum address
        addr = Address.from_hex("0x1234...abcd")
    """).strip(),

    "guards": textwrap.dedent("""
        # Safety guards

        from cowboy_sdk import reentrancy_guard, storage_guard, GuardSet

        # 1. @reentrancy_guard — prevent re-entrant calls
        @actor
        class Token:
            @reentrancy_guard
            def transfer(self, payload):  # Raises ReentrancyError if re-entered
                ...

        # 2. storage_guard — protect state across await
        @runner.continuation(guard_keys=["balance"])  # decorator style
        async def safe_trade(self, msg):
            ctx = capture()
            ctx.result = await runner.llm(...)
            # If "balance" changed during await → StateConflictError
            self.execute()

        # 3. Object-level guard
        balance = storage_guard("balance")
        initial = balance.value             # read
        result = await runner.llm(...)
        if balance.value != initial:        # detects change
            raise StateConflictError("balance changed!")
    """).strip(),

    "bounded_loop": textwrap.dedent("""
        # @bounded_loop — required for loops with await

        from cowboy_sdk import bounded_loop, BoundedRange

        # For loops with await
        @runner.continuation
        @bounded_loop(max_iterations=5)
        async def process_items(self, msg):
            ctx = capture()
            ctx.items = [1, 2, 3, 4, 5]
            ctx.results = []
            for item in BoundedRange(ctx.items):  # BoundedRange enforces limit
                r = await runner.llm(str(item))
                ctx.results.append(r)

        # For loops without await (still good practice)
        @bounded_loop(max_iterations=100)
        def batch_process(self, items):
            for item in BoundedRange(items):
                self.process(item)
    """).strip(),

    "retry": textwrap.dedent("""
        # Retry — deterministic backoff (block-based)

        from cowboy_sdk import Retry

        retry = Retry(
            max_attempts=3,           # max 4
            on_error=True,
            on_empty=False,
            on_validation_fail=False,
        )
        # Backoff sequence (blocks): [1, 2, 4, 8]

        # As Runner job config
        spec = retry.to_dict()

        # Iteration
        for delay in retry:
            print(f"Retry after {delay} blocks")
    """).strip(),

    "taskgroup": textwrap.dedent("""
        # TaskGroup — parallel Runner tasks

        from cowboy_sdk import TaskGroup, runner, capture

        @runner.continuation
        async def parallel(self, msg):
            ctx = capture()
            async with TaskGroup() as tg:
                t1 = tg.create_task(runner.llm("analyze risk"))
                t2 = tg.create_task(runner.http("https://api.prices.com"))
                t3 = tg.create_task(runner.mcp("github", "list_issues"))
                # Max 8 tasks

            ctx.risk = t1.result()    # Access after TaskGroup completes
            ctx.price = t2.result()
            ctx.issues = t3.result()
    """).strip(),

    "token": textwrap.dedent("""
        # CIP-20 Token API (via runtime)

        from cowboy_sdk import runtime

        # Create token
        token_id = runtime.token_create(
            name=b"MyCoin", symbol=b"MC", decimals=18,
            initial_supply=1_000_000, max_supply=None,
            transfer_hook=None, metadata_uri=None,
        )  # returns 32-byte token_id

        # Query
        bal = runtime.token_balance_of(token_id, owner_20bytes)
        supply = runtime.token_total_supply(token_id)
        alw = runtime.token_allowance(token_id, owner, spender)

        # Transfers
        runtime.token_transfer(token_id, to_20bytes, amount)
        runtime.token_approve(token_id, spender_20bytes, amount)
        runtime.token_transfer_from(token_id, from_20bytes, to_20bytes, amount)

        # Mint / Burn
        runtime.token_mint(token_id, to_20bytes, amount)
        runtime.token_burn(token_id, amount)
    """).strip(),

    "errors": textwrap.dedent("""
        # Error hierarchy (all inherit CowboyError)

        from cowboy_sdk import (
            DeterminismError,     # Non-deterministic operation
            StateConflictError,   # Guard: state changed during await
            ReentrancyError,      # @reentrancy_guard triggered
            LoopBoundExceeded,    # @bounded_loop limit hit
            CaptureTypeError,     # Non-serializable value in capture()
            ContinuationLimitError,  # >8 awaits, nested await, etc.
            RunnerTimeoutError,   # timeout_blocks expired
            RunnerValidationError,  # Result failed verification
            CodecError,           # CBOR encode/decode failure
            AddressError,         # Invalid 20-byte address
            ActorNotFoundError,   # call() target not found
            ActorCallError,       # call() target threw exception
            CallDepthExceeded,    # call() depth > 32
        )
    """).strip(),

    "rules": textwrap.dedent("""
        # PVM Iron Rules (10 rules — never break)

        ❌ Forbidden          ✅ Use Instead
        ─────────────────────────────────────────────────
        import time           from cowboy_sdk import pvm_time
        import random         from cowboy_sdk import pvm_random
        set()                 ordered_set (cowboy_sdk.types)
        pickle                cowboy_sdk.codec (CBOR)
        call() depth > 32     limit chains + cycles_limit
        > 8 await per fn      split into multiple continuations
        await in loop         @bounded_loop(max_iterations=N)
        no capture()          ctx = capture() BEFORE await
        send() before call()  call() first, send() last
        return early before await  raise ValueError() instead
    """).strip(),

    "deploy": textwrap.dedent("""
        # Deployment via cowboy CLI

        # 1. Deploy
        cargo run -p cowboy-cli --bin cowboy -- \\
            --indexer-url http://localhost:4000 \\
            actor deploy \\
            --code ./my_actor.py \\
            --salt 00000000000000000000000000000001 \\
            --private-key .cowboy/key \\
            --cycles-limit 10000000 --cells-limit 10000000 --nonce 0

        # 2. Call handler
        PAYLOAD=$(echo -n '{"key":"val"}' | xxd -p -c 9999)
        cargo run -p cowboy-cli --bin cowboy -- \\
            --indexer-url http://localhost:4000 \\
            actor execute \\
            --actor <ADDRESS> --handler init \\
            --payload "$PAYLOAD" \\
            --private-key .cowboy/key \\
            --cycles-limit 5000000 --cells-limit 5000000

        # 3. Query state
        curl http://localhost:4000/actor/<ADDRESS>
    """).strip(),
}

# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="cowboy-actor",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
