#!/bin/bash
# Universal Cowboy Actor Deploy Script
# =====================================
# Works for any Actor code file.
#
# Usage:
#   ./deploy.sh deploy <actor_code.py> [salt]
#   ./deploy.sh call   <actor_address> <handler> '<json_payload>'
#   ./deploy.sh query  <actor_address> <handler> '<json_payload>'
#   ./deploy.sh status <actor_address>
#
# Environment:
#   RPC_URL          Chain RPC endpoint (default: http://localhost:4000)
#   PRIVATE_KEY_FILE Path to private key file (default: .cowboy/key)

set -e

RPC_URL="${RPC_URL:-http://localhost:4000}"
PRIVATE_KEY_FILE="${PRIVATE_KEY_FILE:-.cowboy/key}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Color output ──────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[cowboy]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC} $*"; }
error()   { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── Helpers ───────────────────────────────────────────────────────────────────
check_key() {
    if [ ! -f "$PRIVATE_KEY_FILE" ]; then
        error "Private key not found: $PRIVATE_KEY_FILE\nSet PRIVATE_KEY_FILE or place key at .cowboy/key"
    fi
}

cowboy_cli() {
    cargo run -q -p cowboy-cli --bin cowboy -- \
        --indexer-url "$RPC_URL" \
        "$@"
}

encode_payload() {
    # Encode JSON string to hex for --payload argument
    echo -n "$1" | xxd -p -c 9999
}

# ── Commands ──────────────────────────────────────────────────────────────────
cmd_deploy() {
    local code_path="${1:-}"
    local salt="${2:-00000000000000000000000000000001}"
    [ -z "$code_path" ] && error "Usage: deploy <actor_code.py> [salt]"
    [ ! -f "$code_path" ] && error "File not found: $code_path"
    check_key

    info "Deploying: $code_path"
    info "Salt: $salt"
    info "RPC: $RPC_URL"

    cowboy_cli actor deploy \
        --code "$code_path" \
        --salt "$salt" \
        --private-key "$PRIVATE_KEY_FILE" \
        --cycles-limit 10000000 \
        --cells-limit 10000000 \
        --nonce 0

    info "Deploy submitted. Check indexer for actor address."
}

cmd_call() {
    local actor="${1:-}"; local handler="${2:-}"; local payload="${3:-{}}"
    [ -z "$actor" ] && error "Usage: call <actor_address> <handler> '<json>'"
    [ -z "$handler" ] && error "Usage: call <actor_address> <handler> '<json>'"
    check_key

    info "Calling $handler on $actor"
    local encoded
    encoded=$(encode_payload "$payload")

    cowboy_cli actor execute \
        --actor "$actor" \
        --handler "$handler" \
        --payload "$encoded" \
        --private-key "$PRIVATE_KEY_FILE" \
        --cycles-limit 5000000 \
        --cells-limit 5000000
}

cmd_query() {
    # Same as call but with smaller limits (for read-only handlers)
    local actor="${1:-}"; local handler="${2:-}"; local payload="${3:-{}}"
    [ -z "$actor" ] && error "Usage: query <actor_address> <handler> '<json>'"
    check_key

    info "Querying $handler on $actor"
    local encoded
    encoded=$(encode_payload "$payload")

    cowboy_cli actor execute \
        --actor "$actor" \
        --handler "$handler" \
        --payload "$encoded" \
        --private-key "$PRIVATE_KEY_FILE" \
        --cycles-limit 1000000 \
        --cells-limit 1000000
}

cmd_status() {
    local actor="${1:-}"
    [ -z "$actor" ] && error "Usage: status <actor_address>"

    info "Actor status: $actor"
    curl -s "$RPC_URL/actor/$actor" | python3 -c "
import sys, json
data = json.load(sys.stdin)
storage = data.get('storage', {})
print(f'  Address : {data.get(\"address\", \"?\")}')
print(f'  Balance : {data.get(\"balance\", 0)}')
print(f'  Nonce   : {data.get(\"nonce\", 0)}')
print(f'  Storage : {len(storage)} keys')
print()

try:
    import cbor2
    decode = lambda v: cbor2.loads(bytes.fromhex(v))
except ImportError:
    decode = lambda v: f'<hex: {v[:24]}...>'

for k, v in sorted(storage.items()):
    try:
        key = bytes.fromhex(k).decode('utf-8', errors='replace')
    except Exception:
        key = k
    try:
        val = decode(v)
        # Truncate long values
        s = repr(val)
        if len(s) > 80:
            s = s[:77] + '...'
    except Exception:
        s = f'<raw: {v[:24]}>'
    print(f'  {key:30s} = {s}')
" 2>/dev/null || curl -s "$RPC_URL/actor/$actor"
}

cmd_init() {
    # Convenience: deploy + immediately call init with payload
    local code_path="${1:-}"; local init_payload="${2:-{}}"
    [ -z "$code_path" ] && error "Usage: init <actor_code.py> '<init_json>'"
    check_key

    warn "This will deploy the Actor. Record the address from output!"
    cmd_deploy "$code_path"
    echo ""
    warn "After deploy, run: ./deploy.sh call <actor_address> init '$init_payload'"
}

cmd_help() {
    cat << EOF
Cowboy Actor Deploy Script

Commands:
  deploy  <actor.py> [salt]                 Deploy Actor code
  call    <address> <handler> '<json>'      Call a handler (write)
  query   <address> <handler> '<json>'      Query a handler (read, lower gas)
  status  <address>                         Show Actor state summary
  init    <actor.py> '<init_json>'          Deploy guide (shows next step)

Examples:
  ./deploy.sh deploy simple_actor.py
  ./deploy.sh call   0xAbCd...1234 init '{"greeting":"Hello"}'
  ./deploy.sh call   0xAbCd...1234 increment '{}'
  ./deploy.sh query  0xAbCd...1234 get_status '{}'
  ./deploy.sh status 0xAbCd...1234

  # LLM Actor
  ./deploy.sh call   0xAbCd...1234 chat '{"message":"What is Bitcoin?"}'
  ./deploy.sh query  0xAbCd...1234 get_response '{"chat_id":0}'

  # Token Actor
  ./deploy.sh call   0xAbCd...1234 init '{"name":"MyCoin","symbol":"MC","initial_supply":1000000}'
  ./deploy.sh call   0xAbCd...1234 transfer '{"to":"0x...","amount":100}'
  ./deploy.sh query  0xAbCd...1234 get_balance '{"address":"0x..."}'
  ./deploy.sh query  0xAbCd...1234 get_info '{}'

Environment:
  RPC_URL          (default: http://localhost:4000)
  PRIVATE_KEY_FILE (default: .cowboy/key)
EOF
}

# ── Main ──────────────────────────────────────────────────────────────────────
cmd="${1:-help}"
shift 2>/dev/null || true

case "$cmd" in
    deploy)  cmd_deploy  "$@" ;;
    call)    cmd_call    "$@" ;;
    query)   cmd_query   "$@" ;;
    status)  cmd_status  "$@" ;;
    init)    cmd_init    "$@" ;;
    help|--help|-h|*) cmd_help ;;
esac
