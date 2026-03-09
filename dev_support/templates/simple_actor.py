"""
Simple Actor Template — Cowboy SDK (CIP-6)
==========================================
A minimal stateful Actor without off-chain computation.
Copy this file, rename MyActor and its handlers, then adapt deploy.sh.

PYTHONPATH=node/pvm/Lib python simple_actor.py  # local syntax check
"""
import json
from cowboy_sdk import actor, runtime

# ── Storage key constants ──────────────────────────────────────────────────────
KEY_OWNER = "owner"
KEY_COUNTER = "counter"


# ── Actor ──────────────────────────────────────────────────────────────────────

@actor
class SimpleActor:

    # ------------------------------------------------------------------
    # init — called once at deploy time
    # ------------------------------------------------------------------
    def init(self, payload):
        """
        Initialize Actor state.
        payload (bytes | dict): optional JSON config, e.g. {"greeting": "Hello"}
        """
        runtime.charge_gas(500)
        ctx = runtime.context()
        sender = runtime.get_sender()

        # Store owner address as hex string
        self.storage[KEY_OWNER] = sender.hex() if sender else ""
        self.storage[KEY_COUNTER] = 0

        obj = _parse(payload) or {}
        self.storage["greeting"] = obj.get("greeting", "Hello from Cowboy!")

        runtime.emit_event("init", {"owner": self.storage[KEY_OWNER]})
        return b"ok: initialized"

    # ------------------------------------------------------------------
    # increment — modify state
    # ------------------------------------------------------------------
    def increment(self, payload):
        """Increment counter. Returns new value."""
        runtime.charge_gas(200)
        count = self.storage.get(KEY_COUNTER, 0)
        self.storage[KEY_COUNTER] = count + 1
        runtime.emit_event("incremented", {"counter": count + 1})
        return json.dumps({"counter": count + 1}).encode("utf-8")

    # ------------------------------------------------------------------
    # get_status — read state (no mutation)
    # ------------------------------------------------------------------
    def get_status(self, payload):
        """Return current Actor status."""
        runtime.charge_gas(100)
        result = {
            "owner": self.storage.get(KEY_OWNER, ""),
            "counter": self.storage.get(KEY_COUNTER, 0),
            "greeting": self.storage.get("greeting", ""),
        }
        return json.dumps(result).encode("utf-8")

    # ------------------------------------------------------------------
    # set_greeting — owner-only admin action
    # ------------------------------------------------------------------
    def set_greeting(self, payload):
        """Update greeting. Owner only."""
        runtime.charge_gas(300)
        sender = runtime.get_sender()
        sender_hex = sender.hex() if sender else ""
        owner = self.storage.get(KEY_OWNER, "")

        if owner and sender_hex != owner:
            return b"error: only owner can set greeting"

        obj = _parse(payload) or {}
        greeting = str(obj.get("greeting", "")).strip()
        if not greeting:
            return b"error: greeting cannot be empty"

        self.storage["greeting"] = greeting
        runtime.emit_event("greeting_updated", {"greeting": greeting})
        return b"ok"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse(payload):
    """Parse JSON payload (bytes, str, or dict)."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    try:
        raw = payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
        return json.loads(raw)
    except Exception:
        return None


# ── PVM Entry Points (module-level, required by PVM) ──────────────────────────

def _get_actor():
    return SimpleActor()

def init(payload):         return _get_actor().init(payload)
def increment(payload):    return _get_actor().increment(payload)
def get_status(payload):   return _get_actor().get_status(payload)
def set_greeting(payload): return _get_actor().set_greeting(payload)
