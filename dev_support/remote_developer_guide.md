# Cowboy Actor Developer — Remote Onboarding Guide

> **This guide is for developers who do NOT have the full Cowboy node codebase.**
> Everything you need is in this guide: SDK installation, wallet setup, Claude Code integration, and deployment.

---

## What You Need

| Item | How to get it |
|------|--------------|
| Python ≥ 3.11 | System install |
| `cowboy_sdk` | `pip install cowboy-sdk` *(or see manual install below)* |
| `cowboy` CLI binary | Download from GitHub Releases *(see below)* |
| Claude Code | `npm install -g @anthropic-ai/claude-code` |
| A text editor | VS Code, Cursor, etc. |

No Rust, no full node, no local chain required.

---

## Step 1 — Install the SDK

### Option A: pip (when published)

```bash
pip install cowboy-sdk
```

### Option B: Install directly from source (current)

```bash
# Clone just the SDK (no full node needed)
pip install "git+https://github.com/cowboylabs/cowboy.git#subdirectory=node/pvm/Lib"

# Or if you have the tarball/zip:
pip install ./cowboy_sdk-0.1.0.tar.gz
```

Verify installation:
```bash
python3 -c "from cowboy_sdk import actor, runner, capture; print('✅ SDK OK')"
```

---

## Step 2 — Install the cowboy CLI

### Download pre-built binary

```bash
# Linux x86_64
curl -L https://github.com/cowboylabs/cowboy/releases/latest/download/cowboy-linux-x86_64 \
     -o ~/.local/bin/cowboy
chmod +x ~/.local/bin/cowboy

# macOS ARM64
curl -L https://github.com/cowboylabs/cowboy/releases/latest/download/cowboy-macos-arm64 \
     -o ~/.local/bin/cowboy
chmod +x ~/.local/bin/cowboy

cowboy --version
```

---

## Step 3 — Initialize Your Project

```bash
mkdir my-actor && cd my-actor

# Initialize project, generate wallet, get testnet funds automatically
cowboy init dev

# Output:
#   Created .cowboy/key
#   Created .cowboy/config.json (network: dev, rpc: http://validator-01.dev.cowboylabs.net:4000)
#   Created actors/hello/main.py
#   Wallet address: 0xABCD...1234
#   Requesting funds from faucet... Funded: 1000 CBY
```

This creates:
```
my-actor/
├── .cowboy/
│   ├── key            ← your secp256k1 private key (keep secret!)
│   └── config.json    ← { "network": "dev", "rpc_url": "..." }
├── actors/
│   └── hello/
│       └── main.py    ← starter actor template
└── cowboy.toml
```

---

## Step 4 — Download Claude Code Rules

```bash
# Download CLAUDE.md into your project root
curl -L https://raw.githubusercontent.com/cowboylabs/cowboy/main/refs/dev_support/CLAUDE.md \
     -o CLAUDE.md

# Download MCP server
curl -L https://raw.githubusercontent.com/cowboylabs/cowboy/main/refs/dev_support/cowboy_mcp_server.py \
     -o cowboy_mcp_server.py

pip install mcp
```

---

## Step 5 — Configure Claude Code

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "cowboy": {
      "command": "python3",
      "args": ["./cowboy_mcp_server.py"],
      "env": {
        "RPC_URL": "http://validator-01.dev.cowboylabs.net:4000",
        "COWBOY_WORKSPACE": ".",
        "PRIVATE_KEY_FILE": ".cowboy/key",
        "DEFAULT_CYCLES": "5000000"
      }
    }
  }
}
```

Launch Claude Code:
```bash
claude code .
```

Claude Code will automatically:
1. Load `CLAUDE.md` — knows all Cowboy SDK rules
2. Connect to the MCP server — can deploy, call, and query actors

---

## Step 6 — Start Building

### Write actor code from scratch (vibe coding)

Tell Claude Code:
```
Create a counter actor with init, increment, decrement, and get_count handlers.
```

Claude will use `cowboy_validate` → `cowboy_deploy` → `cowboy_call` automatically.

### Or use a template

```bash
# Get templates
curl -L https://raw.githubusercontent.com/cowboylabs/.../simple_actor.py  -o actors/simple/main.py
curl -L https://raw.githubusercontent.com/cowboylabs/.../llm_actor.py     -o actors/llm/main.py
curl -L https://raw.githubusercontent.com/cowboylabs/.../token_actor.py   -o actors/token/main.py
```

### Manual deploy (without MCP)

```bash
# Deploy
cowboy actor deploy --code actors/hello/main.py

# Call handler
cowboy actor execute \
  --actor 0xYOURACTORADDRESS \
  --handler init \
  --payload $(echo -n '{"greeting":"Hello!"}' | xxd -p -c 9999)

# Query status
curl http://validator-01.dev.cowboylabs.net:4000/actor/0xYOURACTORADDRESS
```

---

## Dev Network Info

| Parameter | Value |
|-----------|-------|
| Network | **Devnet** |
| RPC URL | `http://validator-01.dev.cowboylabs.net:4000` |
| Faucet | `POST {RPC_URL}/faucet` with `{"address": "0x..."}` |
| Block time | ~2 seconds |
| Supported LLMs | `gpt-4o-mini`, `gpt-4o`, `claude-3-haiku` |

Get testnet funds manually:
```bash
curl -X POST http://validator-01.dev.cowboylabs.net:4000/faucet \
     -H "Content-Type: application/json" \
     -d '{"address": "0xYOUR_ADDRESS"}'
```

---

## Local SDK Validation (Offline)

You can validate actor code without any chain connection:

```bash
# Syntax + PVM lint (no chain needed)
python3 -c "
import subprocess, sys
result = subprocess.run([sys.executable, '-m', 'py_compile', 'actors/hello/main.py'])
print('✅ Syntax OK' if result.returncode == 0 else '❌ Syntax error')
"
```

---

## Project Layout (Recommended)

```
my-actor/
├── .cowboy/
│   ├── key              ← private key (gitignore this!)
│   └── config.json      ← { "rpc_url": "http://validator-01..." }
├── .mcp.json            ← MCP server config for Claude Code
├── CLAUDE.md            ← Claude Code rules (download from repo)
├── cowboy_mcp_server.py ← MCP server (download from repo)
├── cowboy.toml          ← project config
└── actors/
    ├── hello/
    │   └── main.py      ← your actor code
    └── token/
        └── main.py
```

### .gitignore

```gitignore
.cowboy/key
__pycache__/
*.pyc
```

---

## Common Claude Code Prompts for Remote Dev

```
1. "Create a voting actor where users submit proposals and vote. 
    Deploy it and try creating a proposal."

2. "My actor is deployed at 0xABC...123. Add rate limiting 
    so each address can only call 'submit' 3 times per block."

3. "Add an LLM-powered function that generates a product description 
    given a product name and price. Use @runner.continuation."

4. "Show me the current storage state of 0xABC...123 and 
    explain what each key means."
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: cowboy_sdk` | `pip install cowboy-sdk` or set `PYTHONPATH` |
| `Private key not found` | Run `cowboy init dev` or check `.cowboy/key` exists |
| `Balance: 0` | `cowboy wallet balance` then request faucet funds |
| `cycles_limit exceeded` | Increase `--cycles-limit` in deploy script |
| `__resume not called` | Check that `on_runner_result` is exposed as module-level function |
| `CBOR decode error in storage` | Use `self.storage.get(key)` not `self.storage[key]` for optional keys |
