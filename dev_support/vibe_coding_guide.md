# Cowboy Vibe Coding Guide — AI-Assisted Actor Development

> How to use Claude Code (or Codex) to build Cowboy Actors with minimal manual effort.

---

## Quick Start with Claude Code

### 1. Setup (One-time)

```bash
# Clone or enter the Cowboy workspace
cd /path/to/workspace

# Verify CLAUDE.md exists at root (already created)
ls CLAUDE.md

# Set PYTHONPATH for local syntax checking
export PYTHONPATH=$(pwd)/node/pvm/Lib
```

### 2. Start Claude Code

```bash
claude code .
```

Claude Code will automatically read `CLAUDE.md` at startup — it now knows all Cowboy rules.

### 3. Example Prompts

**Build from scratch:**
```
Create a voting Actor where users can create proposals and vote on them.
Each vote is recorded on-chain. After voting closes (determined by block height),
anyone can call a finalize method to determine the winner.
```

**Extend a template:**
```
Modify llm_actor.py to support multi-turn conversation history.
Store the last 10 messages per user in storage and include them
in the LLM prompt for context continuity.
```

**Add a feature:**
```
Add a rate_limiter to simple_actor.py that prevents any single sender
from calling increment more than 3 times per block.
```

**Debug:**
```
The chat__resume function is not being called after the Runner returns.
Look at on_runner_result in llm_actor.py and find what's wrong.
```

---

## GitHub Copilot Setup

### 1. Create instructions file

```bash
mkdir -p .github
cat refs/dev_support/cowboy_sdk_developer_manual.md | head -200 > .github/copilot-instructions.md
echo "" >> .github/copilot-instructions.md
echo "## IRON RULES (never break these)" >> .github/copilot-instructions.md
cat CLAUDE.md | grep -A 20 "IRON RULES" >> .github/copilot-instructions.md
```

### 2. Use with VS Code

Open `.vscode/settings.json`:
```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    { "file": ".github/copilot-instructions.md" }
  ]
}
```

---

## File Structure for Developer Kits

```
workspace/
├── CLAUDE.md                               ← AI rules (auto-loaded by Claude Code)
├── .github/
│   └── copilot-instructions.md             ← Copilot rules
├── refs/dev_support/
│   ├── cowboy_sdk_developer_manual.md      ← Full reference manual
│   ├── vibe_coding_guide.md                ← This file
│   └── templates/
│       ├── simple_actor.py                 ← Minimal Actor template
│       ├── llm_actor.py                    ← LLM continuation template
│       ├── token_actor.py                  ← CIP-20 Token template
│       └── deploy.sh                       ← Universal deploy script
└── node/pvm/Lib/cowboy_sdk/               ← SDK source (auto-read by Claude Code)
```

---

## Workflow: Vibe Coding Loop

```
1. PROMPT  →  Tell Claude what Actor you want to build
2. GENERATE →  Claude writes Actor code following CLAUDE.md rules
3. CHECK   →  python -c "import my_actor"  (syntax check, detects violations)
4. DEPLOY  →  ./templates/deploy.sh deploy my_actor.py
5. TEST    →  ./templates/deploy.sh call <addr> <handler> '<json>'
6. ITERATE →  Tell Claude to fix issues or add features
```

### Common Claude Prompts for Iteration

| Goal | Prompt |
|------|--------|
| Fix import error | "The module has an import error: [error msg]. Fix it." |
| Add validation | "Add input validation to the `transfer` handler — check amount > 0 and address is 40 hex chars." |
| Add more handlers | "Add a `get_all_proposals` handler that returns proposals paginated by offset/limit." |
| Improve LLM prompt | "Improve the system_prompt in the chat handler to make the LLM respond more concisely in the user's language." |
| Add verification | "Add Verify.json_schema_valid() to the LLM call in chat() using a CowboyModel schema." |

---

## Common Mistakes Claude Will Avoid (thanks to CLAUDE.md)

| Mistake | Why dangerous |
|---------|--------------|
| `import time; time.time()` | Non-deterministic — different wall clock per node |
| `import random; random.random()` | PRNG state differs per node |
| `set()` | Iteration order varies per Python version/platform |
| Missing `capture()` before `await` | Variables lost at FSM boundary |
| Missing `chat__resume` entry point | PVM can't find resume handler → callback stuck |
| `return b"error"` before `await` | FSM still queues Runner job → orphaned job |

---

## Tips

- **Always `charge_gas()`** in every handler — even read-only queries
- **Test locally first**: `PYTHONPATH=node/pvm/Lib python3 -c "import my_actor; print('OK')"`
- **Check storage** with `deploy.sh status <address>` after calls
- **Monitor events** via indexer WebSocket or event logs after each call
- **Continuation limit**: one Actor can have at most 100 active LLM jobs simultaneously
