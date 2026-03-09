"""
LLM Actor Template — Cowboy SDK (CIP-6)
========================================
Actor with off-chain LLM inference via @runner.continuation FSM.
The async function is compiled at import time into two sync functions:
  chat(self, payload)         → initial call: save state, submit LLM job
  chat__resume(self, msg)     → Runner callback: resume, write result

PYTHONPATH=node/pvm/Lib python llm_actor.py  # local syntax check
"""
import json
from cowboy_sdk import actor, runner, capture, CowboyModel, codec, runtime

# ── Data Model ─────────────────────────────────────────────────────────────────

class ChatEntry(CowboyModel):
    """A single chat record stored in Actor state."""
    id: int
    sender: str
    message: str
    status: str              # "pending" | "done" | "error"
    block_submitted: int
    response: str = None
    block_responded: int = None


# ── Storage Keys ───────────────────────────────────────────────────────────────

KEY_OWNER = "owner"
KEY_COUNT = "chat_count"
KEY_SYSTEM_PROMPT = "cfg:system_prompt"
KEY_MAX_TOKENS = "cfg:max_tokens"
KEY_MODEL = "cfg:model"


# ── Actor ──────────────────────────────────────────────────────────────────────

@actor
class LLMChatActor:

    # ------------------------------------------------------------------
    # init
    # ------------------------------------------------------------------
    def init(self, payload):
        """Initialize Actor. payload JSON: {"system_prompt": "...", "model": "gpt-4o-mini"}"""
        runtime.charge_gas(1000)
        obj = _parse(payload) or {}
        sender = runtime.get_sender()

        self.storage[KEY_OWNER] = sender.hex() if sender else ""
        self.storage[KEY_COUNT] = 0
        self.storage[KEY_SYSTEM_PROMPT] = obj.get(
            "system_prompt",
            "You are a helpful AI assistant. Answer concisely.",
        )
        self.storage[KEY_MAX_TOKENS] = int(obj.get("max_tokens", 1024))
        self.storage[KEY_MODEL] = obj.get("model", "gpt-4o-mini")

        runtime.emit_event("llm.init", {"owner": self.storage[KEY_OWNER]})
        return b"ok: initialized"

    # ------------------------------------------------------------------
    # configure — owner-only
    # ------------------------------------------------------------------
    def configure(self, payload):
        """Update LLM config. Owner only. JSON: {"system_prompt":"...", "max_tokens":1024}"""
        runtime.charge_gas(500)
        sender = runtime.get_sender()
        sender_hex = sender.hex() if sender else ""
        owner = self.storage.get(KEY_OWNER, "")
        if owner and sender_hex != owner:
            return b"error: only owner can configure"

        obj = _parse(payload) or {}
        if "system_prompt" in obj:
            self.storage[KEY_SYSTEM_PROMPT] = str(obj["system_prompt"])
        if "max_tokens" in obj:
            self.storage[KEY_MAX_TOKENS] = int(obj["max_tokens"])
        if "model" in obj:
            self.storage[KEY_MODEL] = str(obj["model"])

        runtime.emit_event("llm.configured", obj)
        return b"ok: configured"

    # ------------------------------------------------------------------
    # chat — @runner.continuation FSM
    # ------------------------------------------------------------------
    @runner.continuation
    async def chat(self, payload):
        """
        Submit a message to LLM and store the response.
        payload JSON: {"message": "What is Bitcoin?"}

        FSM compiler splits at the `await` point:
          Phase 1 (chat):         parse input → save entry → submit LLM job
          Phase 2 (chat__resume): receive result → update entry → emit event
        """
        runtime.charge_gas(2000)
        obj = _parse(payload) or {}
        message = str(obj.get("message", "")).strip()
        if not message:
            raise ValueError("error: message is required")

        sender = runtime.get_sender()
        sender_hex = sender.hex() if sender else "unknown"
        chat_id = self.storage.get(KEY_COUNT, 0)
        self.storage[KEY_COUNT] = chat_id + 1

        # Save pending entry
        entry = ChatEntry(
            id=chat_id,
            sender=sender_hex,
            message=message,
            status="pending",
            block_submitted=runtime.get_block_height(),
        )
        self.storage[f"chat:{chat_id}"] = entry.to_dict()
        runtime.emit_event("llm.chat_submitted", {"id": chat_id, "message": message[:80]})

        # ── Declare capture BEFORE await ──────────────────────────────
        # All variables needed after resume must go into ctx
        ctx = capture()
        ctx.chat_id = chat_id
        ctx.sender = sender_hex

        # ── FSM split point ───────────────────────────────────────────
        result = await runner.llm(
            message,
            system_prompt=self.storage.get(KEY_SYSTEM_PROMPT, ""),
            max_tokens=self.storage.get(KEY_MAX_TOKENS, 1024),
            model=self.storage.get(KEY_MODEL, "gpt-4o-mini"),
        )
        # ── Below runs in chat__resume (next block) ───────────────────

        response = _extract_text(result)
        raw = self.storage.get(f"chat:{ctx.chat_id}") or {}
        raw["response"] = response
        raw["status"] = "done"
        raw["block_responded"] = runtime.get_block_height()
        self.storage[f"chat:{ctx.chat_id}"] = raw

        runtime.emit_event("llm.chat_done", {
            "id": ctx.chat_id,
            "response": response[:200],
        })
        return b"ok"

    # ------------------------------------------------------------------
    # on_runner_result — Runner callback entry
    # ------------------------------------------------------------------
    def on_runner_result(self, payload):
        """Routes Runner callback to the correct __resume method."""
        runtime.charge_gas(1000)
        try:
            msg = codec.decode(payload) if isinstance(payload, bytes) else payload
        except Exception:
            msg = _parse(payload) or {}

        if isinstance(msg, dict) and msg.get("reply_handler"):
            runner.handle_runner_result(self, msg)
            return b"ok"
        return b"error: unrecognized callback format"

    # ------------------------------------------------------------------
    # get_response — query
    # ------------------------------------------------------------------
    def get_response(self, payload):
        """Query a response. JSON: {"chat_id": 0}  (omit for latest)"""
        runtime.charge_gas(200)
        obj = _parse(payload) or {}
        chat_id = obj.get("chat_id")
        if chat_id is None:
            chat_id = self.storage.get(KEY_COUNT, 1) - 1
        entry = self.storage.get(f"chat:{int(chat_id)}")
        if not entry:
            return b"error: not found"
        return json.dumps(entry).encode("utf-8")

    # ------------------------------------------------------------------
    # get_history — query list
    # ------------------------------------------------------------------
    def get_history(self, payload):
        """Query history. JSON: {"offset": 0, "limit": 10}"""
        runtime.charge_gas(500)
        obj = _parse(payload) or {}
        offset = int(obj.get("offset", 0))
        limit = min(int(obj.get("limit", 10)), 50)
        total = self.storage.get(KEY_COUNT, 0)
        history = [
            self.storage.get(f"chat:{i}")
            for i in range(offset, min(offset + limit, total))
            if self.storage.get(f"chat:{i}")
        ]
        return json.dumps({"total": total, "chats": history}).encode("utf-8")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse(payload):
    if payload is None: return None
    if isinstance(payload, dict): return payload
    try:
        raw = payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
        return json.loads(raw)
    except Exception:
        return None


def _extract_text(data):
    """Extract text from various Runner response formats."""
    if data is None: return ""
    if isinstance(data, str): return data
    if isinstance(data, dict):
        for k in ("content", "text", "response", "result"):
            v = data.get(k)
            if isinstance(v, str): return v
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "text" in item:
                        return str(item["text"])
    return str(data)


# ── PVM Entry Points ───────────────────────────────────────────────────────────

def _a(): return LLMChatActor()

def init(payload):             return _a().init(payload)
def configure(payload):        return _a().configure(payload)
def chat(payload):             return _a().chat(payload)
def chat__resume(payload):     return _a().chat__resume(payload)
def on_runner_result(payload): return _a().on_runner_result(payload)
def get_response(payload):     return _a().get_response(payload)
def get_history(payload):      return _a().get_history(payload)
