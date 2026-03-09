"""
Token Actor Template — Cowboy SDK (CIP-6)
==========================================
An on-chain token Actor using the CIP-20 Host Token API.
Demonstrates: reentrancy_guard, call(), token_* runtime API, owner checks.

PYTHONPATH=node/pvm/Lib python token_actor.py  # local syntax check
"""
import json
from cowboy_sdk import actor, reentrancy_guard, runtime

# ── Storage Keys ────────────────────────────────────────────────────────────
KEY_OWNER = "owner"
KEY_TOKEN_ID = "token_id"
KEY_NAME = "token:name"
KEY_SYMBOL = "token:symbol"
KEY_DECIMALS = "token:decimals"


# ── Actor ────────────────────────────────────────────────────────────────────

@actor
class TokenActor:

    # ------------------------------------------------------------------
    # init — creates the token
    # ------------------------------------------------------------------
    def init(self, payload):
        """
        Create a new platform token.
        payload JSON: {
            "name": "MyCoin",
            "symbol": "MC",
            "decimals": 18,
            "initial_supply": 1000000
        }
        """
        runtime.charge_gas(2000)
        obj = _parse(payload) or {}
        sender = runtime.get_sender()

        name = str(obj.get("name", "MyCoin")).encode("utf-8")
        symbol = str(obj.get("symbol", "MC")).encode("utf-8")
        decimals = int(obj.get("decimals", 18))
        initial_supply = int(obj.get("initial_supply", 1_000_000))

        # Create the token via PVM host API
        token_id = runtime.token_create(
            name=name,
            symbol=symbol,
            decimals=decimals,
            initial_supply=initial_supply,
            max_supply=None,    # None = unlimited
            transfer_hook=None,
            metadata_uri=None,
        )

        self.storage[KEY_OWNER] = sender.hex() if sender else ""
        self.storage[KEY_TOKEN_ID] = token_id.hex()  # store as hex
        self.storage[KEY_NAME] = name.decode("utf-8")
        self.storage[KEY_SYMBOL] = symbol.decode("utf-8")
        self.storage[KEY_DECIMALS] = decimals

        runtime.emit_event("token.created", {
            "token_id": token_id.hex(),
            "name": name.decode("utf-8"),
            "symbol": symbol.decode("utf-8"),
            "initial_supply": initial_supply,
        })
        return json.dumps({"token_id": token_id.hex()}).encode("utf-8")

    # ------------------------------------------------------------------
    # transfer — @reentrancy_guard prevents re-entrant attacks
    # ------------------------------------------------------------------
    @reentrancy_guard
    def transfer(self, payload):
        """
        Transfer tokens from caller to recipient.
        payload JSON: {"to": "0x...", "amount": 100}
        """
        runtime.charge_gas(500)
        obj = _parse(payload) or {}
        to_hex = str(obj.get("to", "")).strip()
        amount = int(obj.get("amount", 0))

        if not to_hex or amount <= 0:
            return b"error: invalid to or amount"

        token_id = self._get_token_id()
        if not token_id:
            return b"error: token not initialized"

        to_bytes = bytes.fromhex(to_hex.lstrip("0x").zfill(40))
        runtime.token_transfer(token_id, to_bytes, amount)

        runtime.emit_event("token.transfer", {
            "from": runtime.get_sender().hex(),
            "to": to_hex,
            "amount": amount,
        })
        return b"ok"

    # ------------------------------------------------------------------
    # approve — allow spender to transfer on your behalf
    # ------------------------------------------------------------------
    def approve(self, payload):
        """
        Approve spender allowance.
        payload JSON: {"spender": "0x...", "amount": 100}
        """
        runtime.charge_gas(300)
        obj = _parse(payload) or {}
        spender_hex = str(obj.get("spender", "")).strip()
        amount = int(obj.get("amount", 0))

        token_id = self._get_token_id()
        if not token_id:
            return b"error: token not initialized"

        spender = bytes.fromhex(spender_hex.lstrip("0x").zfill(40))
        runtime.token_approve(token_id, spender, amount)
        runtime.emit_event("token.approval", {"spender": spender_hex, "amount": amount})
        return b"ok"

    # ------------------------------------------------------------------
    # transfer_from — spend allowance
    # ------------------------------------------------------------------
    @reentrancy_guard
    def transfer_from(self, payload):
        """
        Transfer via allowance.
        payload JSON: {"from": "0x...", "to": "0x...", "amount": 100}
        """
        runtime.charge_gas(600)
        obj = _parse(payload) or {}
        from_hex = str(obj.get("from", "")).strip()
        to_hex = str(obj.get("to", "")).strip()
        amount = int(obj.get("amount", 0))

        token_id = self._get_token_id()
        if not token_id:
            return b"error: token not initialized"

        from_addr = bytes.fromhex(from_hex.lstrip("0x").zfill(40))
        to_addr = bytes.fromhex(to_hex.lstrip("0x").zfill(40))
        runtime.token_transfer_from(token_id, from_addr, to_addr, amount)
        return b"ok"

    # ------------------------------------------------------------------
    # mint — owner only
    # ------------------------------------------------------------------
    def mint(self, payload):
        """
        Mint new tokens. Owner only.
        payload JSON: {"to": "0x...", "amount": 1000}
        """
        runtime.charge_gas(500)
        if not self._is_owner():
            return b"error: only owner can mint"

        obj = _parse(payload) or {}
        to_hex = str(obj.get("to", "")).strip()
        amount = int(obj.get("amount", 0))

        token_id = self._get_token_id()
        to_addr = bytes.fromhex(to_hex.lstrip("0x").zfill(40))
        runtime.token_mint(token_id, to_addr, amount)
        runtime.emit_event("token.minted", {"to": to_hex, "amount": amount})
        return b"ok"

    # ------------------------------------------------------------------
    # burn — reduce caller's balance
    # ------------------------------------------------------------------
    def burn(self, payload):
        """
        Burn tokens from caller's balance.
        payload JSON: {"amount": 100}
        """
        runtime.charge_gas(300)
        obj = _parse(payload) or {}
        amount = int(obj.get("amount", 0))
        token_id = self._get_token_id()
        runtime.token_burn(token_id, amount)
        runtime.emit_event("token.burned", {"amount": amount})
        return b"ok"

    # ------------------------------------------------------------------
    # get_balance — query
    # ------------------------------------------------------------------
    def get_balance(self, payload):
        """Query balance. payload JSON: {"address": "0x..."}"""
        runtime.charge_gas(100)
        obj = _parse(payload) or {}
        addr_hex = str(obj.get("address", "")).strip()
        token_id = self._get_token_id()
        if not addr_hex or not token_id:
            return b"error: missing address or token_id"
        owner_bytes = bytes.fromhex(addr_hex.lstrip("0x").zfill(40))
        balance = runtime.token_balance_of(token_id, owner_bytes)
        return json.dumps({"balance": balance or 0}).encode("utf-8")

    # ------------------------------------------------------------------
    # get_info — query token metadata
    # ------------------------------------------------------------------
    def get_info(self, payload):
        """Return token metadata."""
        runtime.charge_gas(100)
        token_id = self._get_token_id()
        supply = runtime.token_total_supply(token_id) if token_id else 0
        return json.dumps({
            "token_id": self.storage.get(KEY_TOKEN_ID, ""),
            "name": self.storage.get(KEY_NAME, ""),
            "symbol": self.storage.get(KEY_SYMBOL, ""),
            "decimals": self.storage.get(KEY_DECIMALS, 18),
            "total_supply": supply or 0,
            "owner": self.storage.get(KEY_OWNER, ""),
        }).encode("utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_token_id(self):
        """Return token_id as bytes, or None if not initialized."""
        hex_id = self.storage.get(KEY_TOKEN_ID)
        return bytes.fromhex(hex_id) if hex_id else None

    def _is_owner(self):
        sender = runtime.get_sender()
        sender_hex = sender.hex() if sender else ""
        owner = self.storage.get(KEY_OWNER, "")
        return not owner or sender_hex == owner


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse(payload):
    if payload is None: return None
    if isinstance(payload, dict): return payload
    try:
        raw = payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
        return json.loads(raw)
    except Exception:
        return None


# ── PVM Entry Points ─────────────────────────────────────────────────────────

def _a(): return TokenActor()

def init(payload):          return _a().init(payload)
def transfer(payload):      return _a().transfer(payload)
def approve(payload):       return _a().approve(payload)
def transfer_from(payload): return _a().transfer_from(payload)
def mint(payload):          return _a().mint(payload)
def burn(payload):          return _a().burn(payload)
def get_balance(payload):   return _a().get_balance(payload)
def get_info(payload):      return _a().get_info(payload)
