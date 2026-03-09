# Cowboy MCP Server — Setup & Integration Guide

## Overview

`cowboy_mcp_server.py` is a [Model Context Protocol](https://modelcontextprotocol.io) server
that gives Claude Code (or any MCP client) direct control over the Cowboy chain.
With it, Claude can **deploy → test → fix → redeploy** actors autonomously in a closed loop.

## Tools Exposed

| Tool | Description |
|------|-------------|
| `cowboy_validate` | Syntax check + PVM rule lint (detects all 10 iron rule violations) |
| `cowboy_deploy` | Deploy actor .py to chain, returns actor address |
| `cowboy_call` | Call a state-modifying handler (write transaction) |
| `cowboy_query` | Call a read-only handler (lower gas) |
| `cowboy_status` | Fetch actor storage (CBOR-decoded key-value dump) |
| `cowboy_sdk_docs` | Return SDK docs for a topic (actor/runner/continuation/…, 16 topics) |
| `cowboy_logs` | Fetch recent on-chain events emitted by actor |

---

## Installation

```bash
pip install mcp
```

---

## Configuration

### Claude Code (`~/.claude.json` or `.mcp.json` in project root)

```json
{
  "mcpServers": {
    "cowboy": {
      "command": "python3",
      "args": ["/home/ubuntu/workspace/refs/dev_support/cowboy_mcp_server.py"],
      "env": {
        "RPC_URL": "http://localhost:4000",
        "COWBOY_WORKSPACE": "/home/ubuntu/workspace",
        "PRIVATE_KEY_FILE": "/home/ubuntu/workspace/.cowboy/key",
        "DEFAULT_CYCLES": "5000000"
      }
    }
  }
}
```

> **Project-local config**: Create `.mcp.json` in workspace root. Claude Code auto-loads it.

### Test the server manually

```bash
# Run in debug mode (prints JSON-RPC to stderr)
cd /home/ubuntu/workspace
RPC_URL=http://localhost:4000 \
COWBOY_WORKSPACE=/home/ubuntu/workspace \
PRIVATE_KEY_FILE=.cowboy/key \
python3 refs/dev_support/cowboy_mcp_server.py
```

---

## Typical Vibe Coding Session

Once configured, Claude Code can run the full development loop autonomously:

```
USER: "Create a simple voting actor where anyone can create proposals and vote on them."

Claude (internally):
  1. cowboy_sdk_docs("actor")         ← learns Actor structure
  2. cowboy_sdk_docs("rules")         ← checks PVM restrictions
  3. [writes voting_actor.py]
  4. cowboy_validate("voting_actor.py")  ← catches any mistakes
  5. [fixes warnings if any]
  6. cowboy_deploy("voting_actor.py")    ← deploys → gets address
  7. cowboy_call(addr, "init", "{}")     ← initializes
  8. cowboy_call(addr, "create_proposal", '{"title":"Upgrade fees"}')
  9. cowboy_call(addr, "vote", '{"proposal_id":0,"choice":"yes"}')
  10. cowboy_query(addr, "get_results", '{"proposal_id":0}')
  11. cowboy_status(addr)               ← verify final state
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RPC_URL` | `http://localhost:4000` | Chain RPC / indexer URL |
| `COWBOY_WORKSPACE` | server's parent dir | Workspace root |
| `PRIVATE_KEY_FILE` | `$WORKSPACE/.cowboy/key` | Deployer private key |
| `DEFAULT_CYCLES` | `5000000` | Default gas for `cowboy_call` |

---

## Lint Rules (`cowboy_validate`)

The validator automatically detects:

- `import time` / `import random` violations
- `set()` usage (non-deterministic)
- `async def` without `@runner.continuation`
- `await` without preceding `capture()`
- Missing `__resume` module-level entry points
- Missing `runtime.charge_gas()` in handlers
- Missing module-level entry points for class methods

---

## Architecture

```
Claude Code
    │  (MCP stdio transport)
    ▼
cowboy_mcp_server.py
    ├── cowboy_validate   → py_compile + regex lint
    ├── cowboy_deploy     → $ cargo run -p cowboy-cli actor deploy
    ├── cowboy_call       → $ cargo run -p cowboy-cli actor execute
    ├── cowboy_query      → $ cargo run -p cowboy-cli actor execute (low gas)
    ├── cowboy_status     → GET $RPC_URL/actor/<addr>
    ├── cowboy_sdk_docs   → in-memory topic lookup
    └── cowboy_logs       → GET $RPC_URL/actor/<addr>/events
```
