# Almanax Security Scan Report

**Repository:** cowboyinc/node  
**Commit:** 395150f8f449d6c80d5a9144fea96ae4819f3de5  
**Date:** 2026-03-16  

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 4 |
| Medium | 17 |
| Low | 25 |
| Info | 1 |
| **Total** | **47** |

---

## indexer/src/lib.rs

### 🟠 MEDIUM — CORS allows any origin with credentials

**Description:**

The indexer's HTTP layer uses `CorsLayer::very_permissive()`, which sets `Access-Control-Allow-Origin: *`. While this alone does not allow credentialed cross-origin requests (browsers ignore `Access-Control-Allow-Credentials: true` when the origin is `*`), it does mean any website can read the indexer's API responses. If the indexer runs on a known/predictable address (e.g., `localhost:8080`, an internal IP, or a public endpoint without auth), any malicious page a user visits can silently query and exfiltrate chain data (blocks, transactions, seeds, notarizations) from the indexer via JavaScript. Additionally, should the CORS configuration later be changed to echo the request origin (a common "fix") instead of `*`, credentialed requests would immediately become exploitable without further code changes.

**Affected Code:**

```rust
let cors = CorsLayer::very_permissive();

let app = Router::new()
    .route("/health", get(health))
    .route("/block/{key}", get(get_block))
    // ... other routes
    .layer(cors)
```

**Recommendation:**

> Restrict the allowed origins to only the hosts that legitimately need cross-origin access. For a local-only indexer, bind to `127.0.0.1` and do not add CORS at all (same-origin pages can already reach it). If specific frontends need access, list them explicitly with `CorsLayer::new().allow_origin(["https://explorer.cowboy.inc".parse().unwrap()])`. Never combine a permissive origin with credentials in the future.

---

### 🟠 MEDIUM — Permissive CORS allows cross-origin API access

**Description:**

The API router enables `CorsLayer::permissive()`, which allows any website origin to make cross-origin XHR/fetch requests to this service and read responses. If this indexer is reachable from a victim's browser (common for localhost/LAN deployments), a malicious site can silently query endpoints (e.g., `/account/{query}`, `/transaction/{query}`, `/events/{query}`) and exfiltrate returned data. The router also exposes WebSocket endpoints without any Origin validation; browsers can establish cross-site WebSocket connections to `/consensus/ws` and `/mempool` and stream data to an attacker-controlled page.

**Affected Code:**

```rust
pub fn router(self) -> Router {
    Router::new()
        .route("/consensus/ws", get(consensus_ws))
        .route("/mempool", get(mempool_ws))
        // ...
        .layer(CorsLayer::permissive())
        .with_state(self.indexer)
}
```

**Recommendation:**

> Replace `CorsLayer::permissive()` with an allowlist of trusted origins/methods/headers. For WebSockets, validate the `Origin` header (or require an explicit auth token) before upgrading. Consider binding to localhost by default and documenting safe reverse-proxy/TLS deployment.

---

### 🟠 MEDIUM — Address transactions query can exhaust resources

**Description:**

`/transactions/{query}` accepts an unbounded `limit` query parameter and sorts the full per-address transaction list before applying the limit. For addresses with large histories, an attacker can request very large limits repeatedly, triggering expensive sort/serialization work and potentially very large responses, leading to resource exhaustion.

**Affected Code:**

```rust
let mut txs = indexer.get_transactions_by_address(&addr);
// Latest first (by height descending), then take up to limit
txs.sort_by(|a, b| b.1.cmp(&a.1));
let limit = params.limit as usize;
let txs = txs.into_iter().take(limit);
let result: Vec<serde_json::Value> = txs
    .map(|(hash, height, is_se
... (truncated)
```

**Recommendation:**

> Clamp `limit` to a reasonable maximum and implement pagination (cursor/height-based). Avoid sorting the full list on every request; store transactions in the desired order or use partial selection.

---

### 🟠 MEDIUM — Latest transactions query can exhaust resources

**Description:**

`get_latest_transactions(limit)` uses the caller-provided `limit` to decide how many transactions to collect and return, but does not enforce an upper bound. The HTTP handler (`/transactions`) takes an unbounded `limit` from the query string, allowing a client to request extremely large responses. On a node with substantial history this can cause high CPU (iteration/serialization) and memory usage, potentially leading to DoS.

**Affected Code:**

```rust
pub fn get_latest_transactions(&self, limit: usize) -> Vec<(Digest, u64, Address)> {
    let state = self.state.read().unwrap();
    let mut result = Vec::with_capacity(limit.min(256));
    for (height, view) in state.finalized_height_to_view.iter().rev() {
        let Some(finalized) = state.finali
    ... (truncated)
```

**Recommendation:**

> Enforce a server-side maximum for `limit` (e.g., clamp to 100/1000) and return `400` for unreasonable values. Consider pagination instead of large limits.

---

### 🟠 MEDIUM — Unbounded `get_blocks` range can exhaust memory

**Description:**

`get_blocks(start, end)` reads every block in the half-open range `[start, end)` into a `Vec` and serializes the entire collection as a single JSON response. A client can request an arbitrarily large range (e.g., 0..u64::MAX) causing the indexer to attempt loading millions of blocks into memory, which can trigger OOM, extreme GC pressure, or prolonged CPU usage in the serialization path. Because the endpoint has no authentication and CORS is permissive (see the CORS finding), any external page can trigger this.

**Affected Code:**

```rust
pub async fn get_blocks(
    ...
    let blocks = state.db.get_blocks(start, end);
    ...
    Json(BlocksResponse { blocks })
)
```

**Recommendation:**

> Enforce a maximum page size (e.g., `let end = end.min(start + MAX_PAGE_SIZE)`) and return a `400` or paginated response when the requested range exceeds it. Consider also streaming the results with `axum::body::StreamBody` instead of collecting everything into a `Vec`.

---

### 🟠 MEDIUM — Unbounded query results can OOM the indexer

**Description:**

Several query endpoints (`/blocks`, `/transactions`, `/runners`, ...) pass caller-controlled range parameters straight to the database layer without capping the result-set size. A request asking for all blocks/transactions since genesis (for example, `start=0&end=999999999`) forces the indexer to load, serialize, and buffer the entire history in memory before sending the response. At small chain sizes this is merely slow; as the chain grows (or if an attacker seeds many transactions) a single request can exhaust memory and crash the process, denying service to all other users.

**Affected Code:**

```rust
pub async fn get_blocks(
    State(state): State<Arc<IndexerState>>,
    Path((start, end)): Path<(u64, u64)>,
) -> impl IntoResponse {
    let blocks = state.db.get_blocks(start, end);
    Json(BlocksResponse { blocks })
}
... (truncated)
```

**Recommendation:**

> Add an enforced maximum page size to every list/range endpoint (e.g., `const MAX_PAGE: u64 = 100; let end = start.saturating_add(MAX_PAGE).min(end);`). Return HTTP 400 if the client asks for more than the limit, or silently clamp and include a `next_cursor`/`Link` header for pagination. Also consider streaming results instead of buffering the full `Vec`.

---

### 🟡 LOW — Logging full submissions enables disk-fill DoS

**Description:**

The `/submit` endpoint logs the full, user-supplied transaction list at INFO level. An attacker can repeatedly submit near-maximum sized request bodies (up to Axum's default body limit) to generate large log volume and potentially exhaust disk space or degrade performance.

**Affected Code:**

```rust
Submission::Transactions(txs) => {
    indexer.submit_transactions(txs.clone());
    info!("submitted transactions to mempool: {:?}", txs.clone());
    StatusCode::OK
}
```

**Recommendation:**

> Avoid logging full untrusted payloads at INFO (log counts/hashes instead), lower verbosity, and add rate limiting. Consider structured logging with truncation.

---

## chain/src/application.rs

### 🟠 MEDIUM — Private key logged in `tracing` span

**Description:**

The `run` function creates a top-level `tracing` span that includes the node's private key in the span fields. Tracing spans are emitted to all configured subscribers (stdout, log files, external telemetry services, etc.), meaning the private key will be written to plain text in logs and potentially forwarded to third-party logging infrastructure. An attacker or insider with access to logs can recover the private key and impersonate the validator, sign arbitrary consensus messages, or forge transactions from the validator's account.

**Affected Code:**

```rust
pub async fn run(config: Config, ...) {
    let span = info_span!("node",
        private_key = %config.private_key,
        ...
    );
    ...
}
```

**Recommendation:**

> Remove the private key (and any other secret material such as `share`, `polynomial`) from span fields and log messages. If operator identification is needed in traces, log a _public_ identifier instead (e.g., the corresponding public key or address).

---

### 🟠 MEDIUM — Faucet endpoint lacks rate limiting and amount caps

**Description:**

The `/faucet` endpoint mints tokens and sends them to a caller-supplied address with no per-address or global rate limit and no cap on the amount per request. An attacker (or bot) can loop requests to drain the faucet account or inflate token supply arbitrarily fast, potentially exhausting the pre-funded balance in seconds and/or bloating state with many small dust UTXOs.

**Affected Code:**

```rust
.route("/faucet", post(faucet))

async fn faucet(
    State(state): State<Arc<AppState>>,
    Json(req): Json<FaucetRequest>,
) -> impl IntoResponse {
    // ... directly processes mint/transfer with no rate limiting
}
```

**Recommendation:**

> Add a per-IP and/or per-address rate limiter (e.g., a token-bucket via `governor` or `tower::limit`), enforce a maximum amount per request, and consider a global cooldown. On non-local networks, the faucet should be behind authentication or a CAPTCHA.

---

### 🟠 MEDIUM — No per-IP or global rate limiting on RPC

**Description:**

All RPC/HTTP endpoints (submit, execute, query, faucet, ...) are served without any rate limiting. A single client can open many connections and send unlimited requests, consuming CPU, memory, and disk I/O, potentially starving legitimate users and degrading consensus performance.

**Affected Code:**

```rust
let app = Router::new()
    .route("/submit", post(submit))
    .route("/query/{address}", get(query))
    .route("/faucet", post(faucet))
    ... // no rate-limit middleware
```

**Recommendation:**

> Add a rate-limiting middleware layer (e.g., `tower::limit::RateLimitLayer`, `governor`, or a custom axum middleware) that enforces per-IP and/or global request rate caps. Consider separate limits for computationally expensive endpoints (e.g., `/submit`, `/execute`) vs. read-only ones.

---

### 🟠 MEDIUM — Unbounded transaction payload accepted by `/submit`

**Description:**

The `/submit` endpoint deserializes the full request body without enforcing a maximum size. An attacker can POST a very large JSON body (megabytes/gigabytes) causing the node to allocate and parse it, leading to excessive memory consumption or OOM.

**Affected Code:**

```rust
async fn submit(
    State(state): State<Arc<AppState>>,
    Json(req): Json<SubmitRequest>,
) -> impl IntoResponse {
    ...
}
```

**Recommendation:**

> Add a request body size limit using `axum::extract::DefaultBodyLimit::max(MAX_BYTES)` or `tower_http::limit::RequestBodyLimitLayer`. Choose a maximum that accommodates legitimate transactions but prevents abuse (e.g., 1 MB).

---

### 🟡 LOW — Deterministic genesis leader key enables chain replay

**Description:**

The genesis block's consensus context hard-codes the genesis leader to `ed25519::PrivateKey::from_seed(0).public_key()`. Combined with the fixed `GENESIS` constant, every deployment using this code will produce the same genesis block context/digest. If transaction signatures and consensus identities are not additionally domain-separated by a unique chain-id/genesis hash elsewhere, this can enable cross-network replay/confusion: an attacker can reuse signed data and/or consensus identity assumptions between networks that share this identical genesis. Exploitation path: stand up a second network using the same code; because genesis is identical, signed artifacts that don't include a chain-specific domain separator (e.g., transactions, notarizations) may be accepted on both networks, allowing replay of actions across networks. Note: exploitability depends on whether the wider codebase includes a proper per-chain domain separator (chain-id/genesis hash) in signatures; this file makes accidental identical-genesis deployments easy.

**Affected Code:**

```rust
const GENESIS: &[u8] = b"commonware is neat";

let genesis_context = Context {
    round: Round::new(EPOCH, View::zero()),
    leader: ed25519::PrivateKey::from_seed(0).public_key(),
    parent: (View::zero(), Digest::EMPTY),
};
```

**Recommendation:**

> Make genesis configuration explicit per network (unique genesis seed/message/chain-id) and avoid deriving any production identities from constant seeds. Ensure all signed objects are domain-separated by a chain-id or genesis hash.

---

## cli/actors/feed_subscriber.py

### 🟠 MEDIUM — Any caller can inject fake stream messages

**Description:**

`handle_message()` accepts and stores any JSON object as a "stream-data" message without verifying that the call actually came from the subscribed feed actor (or that the `publisher` field matches an expected value). Because actor handlers can be executed directly by any transaction sender, an attacker can call `handle_message` repeatedly to store arbitrary fabricated messages, corrupting the subscriber's on-chain message history and misleading any downstream consumer that relies on `get_messages()`.

**Affected Code:**

```python
def handle_message(payload):
    ...
    ctx = pvm_host.context()
    ...
    data = _extract_payload(payload)
    if not isinstance(data, dict):
        return b"error: expected stream_data message"

    stream_payload = data.get("payload", {})
    publisher = data.get("publisher", "unknown")

    ... (truncated)
```

**Recommendation:**

> Authenticate the message source in `handle_message()` by checking `ctx["sender"]` (or equivalent) against the stored subscribed `feed_address`, and reject calls from unauthorized senders. Optionally validate message schema (type, publisher, payload) before storing.

---

### 🟠 MEDIUM — Unauthorized users can change subscribed feed target

**Description:**

The actor records an owner in `init()`, but `subscribe_to_feed()` does not verify that the caller is that owner (or otherwise authorized). Any account can execute this handler to (1) overwrite the stored `feed_address` and (2) make the actor send a `{"method":"subscribe","subscriber":...}` message to an arbitrary 20-byte target address. This lets an attacker redirect what this subscriber considers its feed, or abuse the actor as a message-sending gadget toward other actors (e.g., subscribe this actor to a malicious feed that then spams it; or send unsolicited subscribe messages to third-party actors).

**Affected Code:**

```python
def subscribe_to_feed(payload):
    ...
    ctx = pvm_host.context()
    ...
    target = _hex_to_bytes(feed_addr)
    subscribe_msg = ('{"method":"subscribe","subscriber":"' + my_addr + '"}').encode("utf-8")
    pvm_host.send_message(target, subscribe_msg)

    _set_str(b"feed_address", feed_addr)

    ... (truncated)
```

**Recommendation:**

> Enforce authorization in `subscribe_to_feed()` (e.g., compare `ctx["sender"]` against the stored `owner`), and validate `feed_address` length/format before sending messages. Consider separating "set feed address" from "send subscribe message", and/or require an allowlist of feed actors.

---

### 🟡 LOW — Unbounded message payload can bloat actor state

**Description:**

Stored messages are capped to the last 100 entries, but each entry's `payload` is stored verbatim with no size limit or depth limit. A caller can submit a very large/nested JSON payload to `handle_message()`, causing large state writes (and potentially high CPU from `_json_dumps`/`_json_loads`) each time, which can be used to exhaust execution resources or inflate the actor's on-chain storage footprint/cost.

**Affected Code:**

```python
def handle_message(payload):
    ...
    stream_payload = data.get("payload", {})
    ...
    messages.append({
        "payload": stream_payload,
        ...
    })
    ...
    _set_str(b"messages", _json_dumps(messages))
```

**Recommendation:**

> Enforce maximum payload size and maximum nesting/field limits before storing. Consider storing only a hash/summary, or truncating large fields. Ensure gas/storage costs scale with data size so the caller pays for large writes.

---

## cli/src/commands.rs

### 🔴 HIGH — Private keys written with default file permissions

**Description:**

The CLI writes newly generated/imported private keys to disk using `fs::write` without setting restrictive file permissions. On many systems this results in files created with mode `0o666` & `umask` (often `0644`), making the private key readable by other local users. A local attacker (or malware running as another user) could read `.cowboy/keys/<network>` or other output paths and steal the secp256k1 private key, enabling signing arbitrary transactions and draining funds.

**Affected Code:**

```rust
// wallet create
let pem = crate::key_format::encode_pem(&key_bytes);
fs::write(&output, &pem)?;

// wallet upgrade
let pem = crate::key_format::encode_pem(&key_bytes);
fs::write(&key_path, &pem)?;

// init
let pem = crate::key_format::encode_pem(&key_bytes);
fs::write(&key_path, &pem)?;

// mnemoni
... (truncated)
```

**Recommendation:**

> Create key files with restrictive permissions (Unix: `0o600`) using `OpenOptions::create_new(true)` + `set_mode(0o600)` (via `std::os::unix::fs::OpenOptionsExt`) and write the contents to the opened file. Consider atomic writes (write to temp + rename) and verify permissions on existing key files. O... (truncated)

---

### 🟠 MEDIUM — Config-controlled path can overwrite arbitrary files

**Description:**

`WalletCommand::Upgrade` selects the key path from `.cowboy/config.json` (`cfg.key_file`) and joins it with `cfg.cowboy_dir` without validating that the result remains within the `.cowboy/` directory. If `key_file` is an absolute path (or otherwise escapes via platform-specific semantics), `PathBuf::join` will ignore the base directory and return the attacker-chosen path. If a user runs `cowboy wallet upgrade` in a directory containing a malicious `.cowboy/config.json`, the command can be tricked into overwriting an arbitrary existing file writable by that user (e.g., `~/.bashrc`, project source files), causing data loss or potentially enabling code execution depending on what file is overwritten and later interpreted.

**Affected Code:**

```rust
// from config
let key_file = env_config.get("key_file")
    .and_then(|v| v.as_str())
    .unwrap_or("key")
    .to_string();

// upgrade path resolution + overwrite
let candidate = cfg.cowboy_dir.join(&cfg.key_file);
...
fs::write(&key_path, &pem)?;
```

**Recommendation:**

> Treat `key_file` in config as a *relative* path only: reject absolute paths, reject path components like `..`, and (optionally) canonicalize and verify the resolved path is under `cfg.cowboy_dir` before reading/writing. Prefer storing only relative paths in config and enforcing that invariant at loa... (truncated)

---

### 🟡 LOW — Actor name validation misses Windows path separators

**Description:**

`handle_actor_new` validates the actor name by rejecting `/`, `..`, and whitespace, but does not reject Windows path separators (`\\`) or drive/UNC absolute paths (e.g., `C:\\...`, `\\\\server\\share`). On Windows, `PathBuf::join` treats such inputs as absolute paths, allowing `cowboy actor new <name>` to create directories and write `main.py` outside the intended `actors/` directory. If a user runs this in an untrusted environment (e.g., copy/pasting a command), it can overwrite/create files at attacker-chosen locations writable by the user.

**Affected Code:**

```rust
if name.contains('/') || name.contains("..") || name.contains(' ') || name.is_empty() {
    return Err(anyhow::anyhow!(...));
}

let actor_dir = PathBuf::from("actors").join(name);
...
fs::create_dir_all(&actor_dir)?;
let actor_path = actor_dir.join("main.py");
fs::write(&actor_path, ACTOR_TEMPLATE)
... (truncated)
```

**Recommendation:**

> Use strict allowlisting for actor names (e.g., `^[a-zA-Z0-9_-]+$`), explicitly reject `\`, `:`, and any absolute-path inputs, and/or canonicalize and ensure the resolved path stays within the `actors/` directory before writing.

---

## client/src/lib.rs

### 🟡 LOW — TLS setup uses expect causing process crash

**Description:**

ClientBuilder::build() uses multiple expect() calls when loading/parsing/adding certificates. If custom TLS cert bytes are loaded from configuration or other untrusted sources, supplying malformed DER will crash the process. Additionally, failure to load or add native certificates (environmental issues) will also crash, turning transient system misconfiguration into a hard DoS.

**Affected Code:**

```rust
for cert_der in &self.tls_certs {
    let cert = reqwest::Certificate::from_der(cert_der).expect("invalid DER certificate");
    http_builder = http_builder.add_root_certificate(cert);
}
let http_client = http_builder.build().expect("failed to build HTTP client");

let mut root_store = rustls::RootC
... (truncated)
```

**Recommendation:**

> Propagate errors instead of panicking (return Result<Client<S>, Error>), and handle malformed custom certificates gracefully (e.g., skip invalid certs with explicit error reporting).

---

### 🟡 LOW — No HTTP client timeouts enables hanging requests

**Description:**

The reqwest Client is built without configuring any request/connection timeouts. A slow or malicious endpoint can keep connections open indefinitely, causing client tasks to hang and potentially exhausting resources under concurrency (DoS risk), especially since downstream methods await .send() without an external timeout.

**Affected Code:**

```rust
// Build HTTP client
let mut http_builder = reqwest::Client::builder();
for cert_der in &self.tls_certs {
    let cert = reqwest::Certificate::from_der(cert_der).expect("invalid DER certificate");
    http_builder = http_builder.add_root_certificate(cert);
}
let http_client = http_builder.build().ex
... (truncated)
```

**Recommendation:**

> Configure reasonable timeouts on the reqwest client builder (e.g., connect_timeout and overall timeout), and/or apply per-request timeouts in call sites.

---

### 🟡 LOW — Panic on unexpected URI scheme input

**Description:**

ClientBuilder::new() validates the URI scheme by string prefix checks and calls panic!() if the URI does not start with "http://" or "https://". If the URI is sourced from untrusted or user-provided configuration/CLI input, this allows a trivial process crash (denial of service) by providing an unsupported/invalid scheme (or even a leading whitespace/case change that fails the prefix check).

**Affected Code:**

```rust
pub fn new(uri: &str, identity: Identity, strategy: S) -> Self {
    let uri = uri.to_string();
    let ws_uri = if let Some(rest) = uri.strip_prefix("https://") {
        format!("wss://{rest}")
    } else if let Some(rest) = uri.strip_prefix("http://") {
        format!("ws://{rest}")
    } else {
    ... (truncated)
```

**Recommendation:**

> Return a typed error (e.g., Result<Self, Error>) instead of panicking, and parse/validate using a URL parser (e.g., url::Url) to robustly validate scheme/host.

---

## ./cli-bootstrap.sh

### 🔴 HIGH — Unverified binary download installed with sudo

**Description:**

The script downloads an executable over the network and installs it into a privileged location (often via `sudo`) without any cryptographic integrity/authenticity verification (e.g., signature verification, pinned hashes, TUF, etc.). If the download endpoint, DNS, TLS trust chain (CA), or build/publish pipeline is compromised, an attacker can supply a trojaned `cowboy` binary that will be installed and later executed by users (potentially giving full code execution on developer machines/hosts).

**Affected Code:**

```bash
VERSION="$(curl -fsSL "${BASE_URL}/latest?key=${KEY}")"
...
curl -fsSL -o "$TMPFILE" "$URL"
chmod +x "$TMPFILE"
...
sudo mv "$TMPFILE" "${INSTALL_DIR}/cowboy"
```

**Recommendation:**

> Verify the downloaded binary before executing/installing it: publish and verify a detached signature (e.g., minisign/cosign/GPG) or a pinned SHA-256 hash fetched from a separate trusted channel; consider certificate/key pinning or a framework like TUF; fail closed if verification fails. Also conside... (truncated)

---

### 🟠 MEDIUM — API key exposed in URL and process list

**Description:**

The API key is placed into query parameters and passed on the `curl` command line. This can leak the key via process listings (`ps`/`top`), shell history (when passed as `--key`), proxy/CDN/server access logs, and referer/header propagation in some environments. Anyone with access to those logs or the local machine's process list during execution may be able to recover the key and reuse it.

**Affected Code:**

```bash
KEY="${COWBOY_KEY:-}"
...
VERSION="$(curl -fsSL "${BASE_URL}/latest?key=${KEY}")"
...
URL="${BASE_URL}/${VERSION}/${BINARY}?key=${KEY}"
...
curl -fsSL -o "$TMPFILE" "$URL"
```

**Recommendation:**

> Avoid putting secrets in URLs. Send the key in an HTTP header (e.g., `Authorization: Bearer ...`) or request body. If you must use environment variables, avoid echoing/printing them and avoid passing them as command-line args; consider prompting for the key (no-echo) when not set. Ensure server-side... (truncated)

---

## ./diagnose_runner.sh

### 🟡 LOW — Cargo executed even if cd fails

**Description:**

The script changes directory and then runs `cargo run`, but it does not check whether `cd /home/ubuntu/workspace/node` succeeded. In bash, a failed `cd` does not stop execution by default, so `cargo run` will execute in the caller's current working directory. If an operator runs this script from an attacker-controlled directory (or if `/home/ubuntu/workspace/node` is missing/mis-mounted), an attacker could place a malicious Rust project/Cargo config in the working directory so the script builds/executes attacker-controlled code under the operator's privileges.

**Affected Code:**

```bash
cd /home/ubuntu/workspace/node
RUNNER_INFO=$(cargo run -q -p cowboy-cli --bin cowboy -- --indexer-url "$RPC_URL" runner get --address "$RUNNER_ADDR" 2>&1)
```

**Recommendation:**

> Fail fast and verify directory changes before executing build/run steps, e.g. `set -euo pipefail` and `cd /home/ubuntu/workspace/node || exit 1`. Consider using `cargo --manifest-path /home/ubuntu/workspace/node/Cargo.toml ...` to avoid dependency on CWD.

---

### ℹ️ INFO — Tailing fixed path allows symlink data leak

**Description:**

The script tails a fixed log file path in the user's home directory. If that path is writable by another local user/process (or can be influenced, e.g., via symlink replacement), running the script could disclose contents of an arbitrary file by tailing a symlink target. This becomes more impactful if the script is ever run with elevated privileges.

**Affected Code:**

```bash
tail -20 /home/ubuntu/.cursor/projects/home-ubuntu-workspace/terminals/7.txt 2>/dev/null | \
    grep -E "INFO|WARN|ERROR" | tail -5 || echo "  无法读取 Runner 日志"
```

**Recommendation:**

> Avoid reading from paths that can be replaced; ensure the file is owned by the expected user and is a regular file before reading (e.g., check with `test -f` and `stat`), and avoid running the script as root.

---

## ./restart_validator.sh

### 🟡 LOW — Grepped PID kill can terminate wrong process

**Description:**

The script finds a PID by grepping the process list for a substring and then kills it. Any local user able to run a process whose command line matches `target/release/validator` could cause the script to kill an unintended process (denial-of-service). Additionally, multiple matches can result in killing multiple PIDs.

**Affected Code:**

```bash
OLD_PID=$(ps aux | grep "target/release/validator" | grep -v grep | awk '{print $2}')
if [ -n "$OLD_PID" ]; then
    kill $OLD_PID 2>/dev/null || true
```

**Recommendation:**

> Use a PID file, `pkill -x`/`pgrep` with strict matching, or match by full executable path/inode. For example, start the validator with a known pidfile and kill only that PID after verifying it is the expected binary.

---

### 🟡 LOW — Symlinked test directory can delete arbitrary files

**Description:**

The script deletes files using relative paths (e.g., `test/*.db`, `test/storage`) after `cd` into a fixed directory. If an attacker (or compromised process) can replace `test/` with a symlink to another directory before the script runs, the glob expansion can resolve outside the intended test directory and `rm -rf` may delete unintended files accessible to the script's user (or far worse if run with sudo/root).

**Affected Code:**

```bash
cd /home/ubuntu/workspace/node
rm -rf test/*.db test/*.log test/storage 2>/dev/null || true
```

**Recommendation:**

> Defend against symlink/path attacks before deletion: resolve and verify the real path (`realpath`) is within the expected workspace, refuse to operate if `test` is a symlink, and consider using `rm -rf --one-file-system -- test/...` with explicit paths. Example: `TESTDIR=$(realpath -P test) && [[ "$... (truncated)

---

## cli/src/key_format.rs

### 🟡 LOW — 16-bit checksum allows easy key substitution

**Description:**

The PEM "Checksum" is only the first 2 bytes (16 bits) of SHA-256. This is fine for catching accidental corruption, but it is too small to provide meaningful integrity against an attacker who can modify the key file: they can generate a different 32-byte private key with the same 16-bit checksum in ~2^16 attempts and replace the file while preserving the displayed/expected checksum value. Realistic abuse path: on a system where an attacker can tamper with the wallet key file (or trick a user into importing a malicious PEM), the attacker can craft a replacement key that collides on the 4-hex checksum so the CLI/user "checksum verification" does not signal tampering, potentially causing transactions to be signed under the wrong key if the user relies on the checksum as a fingerprint.

**Affected Code:**

```rust
/// Compute checksum: first 4 hex chars of SHA-256(key_bytes)
fn compute_checksum(key_bytes: &[u8; 32]) -> String {
    let hash = Sha256::digest(key_bytes);
    hex::encode(&hash[..2])
}
```

**Recommendation:**

> If the checksum is intended only for accidental-error detection, document it clearly (e.g., rename to "CRC"/"fingerprint" and warn it is not security). If it is intended as a tamper check/fingerprint, increase it substantially (e.g., 128+ bits, or full SHA-256) and/or use an authenticated format (e.... (truncated)

---

### 🟡 LOW — Unbounded PEM body parsing can exhaust memory

**Description:**

The PEM decoder concatenates all non-header lines between BEGIN/END into a single string and then base64-decodes it, without any early size limit. If an attacker can cause the CLI/library to process an unexpectedly large "key file" content (e.g., a huge file path provided to the CLI, or a maliciously large pasted PEM), this can cause large allocations (lines vector + joined body string + decoded bytes) and lead to memory exhaustion / denial of service.

**Affected Code:**

```rust
let mut body_parts: Vec<&str> = Vec::new();

for line in &lines[1..lines.len() - 1] {
    let line = line.trim();
    if let Some(val) = line.strip_prefix("Curve:") {
        curve = Some(val.trim());
    } else if let Some(val) = line.strip_prefix("Checksum:") {
        checksum = Some(val.trim());
    ... (truncated)
```

**Recommendation:**

> Reject PEM bodies that are not exactly the expected size for a 32-byte key (base64 length 44 with padding for STANDARD encoding), or enforce a small maximum (e.g., a few KB) before joining/decoding. Consider streaming validation instead of collecting/joining all lines.

---

## cli/actors/watchtower_registry.py

### 🔴 HIGH — Unrestricted init allows registry state reset

**Description:**

The `init()` handler can be executed by any caller at any time and unconditionally overwrites critical state (`owner` and the full `feeds` list). This lets an attacker re-initialize an already-deployed registry, wiping all registered feeds and setting themselves as owner (even though `owner` is currently unused, the wipe is impactful). Exploitation path: after a legitimate deployment and feed registrations, an attacker submits an `ExecuteActor` transaction to the registry with handler `init`. The contract resets `feeds` to `[]`, effectively deleting the directory. Subsequent `get_feeds`/`get_feed_info` calls will fail or return empty results.

**Affected Code:**

```python
def init(payload):
    pvm_host.charge_gas(2000)
    ctx = pvm_host.context()
    owner = _sender_hex(ctx)

    _set_str(b"owner", owner)
    _set_json(b"feeds", [])

    pvm_host.emit_event("registry.init", ("owner=" + owner).encode())
    return b"ok: registry initialized"
```

**Recommendation:**

> Make initialization one-time and/or owner-restricted. Common patterns: (1) store an `initialized` flag in state and reject subsequent `init` calls; and/or (2) require `ctx.sender` equals the deployer/owner before allowing `init` to run. Also consider using the stored `owner` for future admin-only op... (truncated)

---

### 🟠 MEDIUM — Unbounded feed registrations enable storage/gas DoS

**Description:**

`register_feed()` allows any caller to append arbitrary `feed_address`, `name`, and `description` to on-chain state without size limits. The registry maintains an ever-growing `feeds` array, and query handlers (`get_feeds`, `get_feeds_by_creator`) iterate over the entire list while charging a fixed small amount of gas, and emit the full result as an event. Exploitation path: an attacker repeatedly calls `register_feed` with unique, very large `feed_address` strings (and large `name`/`description`). This bloats state and makes `get_feeds`/`get_feeds_by_creator` increasingly expensive, potentially causing out-of-gas/limits failures for honest users or excessive resource consumption during execution/event emission.

**Affected Code:**

```python
def register_feed(payload):
    ...
    feed_address = data.get("feed_address", "")
    ...
    name = data.get("name", "")
    description = data.get("description", "")

    feeds = _get_json(b"feeds") or []
    ...
    feeds.append(feed_address)
    _set_json(b"feeds", feeds)

    feed_key = ("fee
    ... (truncated)
```

**Recommendation:**

> Enforce strict validation and bounds: validate `feed_address` format/length (e.g., 20-byte hex), cap `name`/`description` lengths, and consider a maximum number of feeds or pagination for listing methods. Charge gas proportional to `len(feeds)` and payload sizes, and avoid emitting unbounded-sized e... (truncated)

---

## ./start_validator.sh

### 🟡 LOW — Overbroad pkill may terminate unrelated processes

**Description:**

The stop logic uses `pkill -f "validator.*--config"`, which matches any process whose full command line contains a substring matching that regex. If this script is run by an operator (especially as a privileged user), it can unintentionally kill other processes that happen to match (including other validators or unrelated processes with similar args), causing an avoidable denial of service.

**Affected Code:**

```bash
if [ "${1:-}" = "--stop" ]; then
    echo "停止 Validator..."
    if pkill -f "validator.*--config" 2>/dev/null; then
        echo "Validator 已停止"
    else
        echo "未找到运行中的 validator 进程"
    fi
    exit 0
fi
```

**Recommendation:**

> Track and stop the specific PID you started (e.g., write `$!` to a pidfile under `$NODE_DIR/test/validator.pid` and `kill $(cat ...)'), or constrain pkill with additional predicates (exact binary path, `-u $(id -u)`, and a stricter pattern).

---

### 🟡 LOW — Faucet enabled by default may expose funds

**Description:**

The script enables the validator's `/faucet` endpoint by default (`ENABLE_FAUCET` defaults to `1`). While the Rust code adds an additional safety check (only local/dev chain IDs), running a public/staging network with a local/dev chain_id or misconfigured genesis would expose an unauthenticated faucet that can be spammed to drain the faucet account and/or flood the mempool.

**Affected Code:**

```bash
# Faucet 端点：本地/开发链默认开启 (=1)，生产环境请显式设置 ENABLE_FAUCET=0
export ENABLE_FAUCET="${ENABLE_FAUCET:-1}"

EXTRA_ARGS=()
[ "${ENABLE_FAUCET}" = "1" ] && EXTRA_ARGS+=(--enable-faucet)
```

**Recommendation:**

> Default `ENABLE_FAUCET` to `0` in this script (require explicit opt-in), and/or require an allowlist/token/rate-limiting on the faucet endpoint for any non-local use.

---

## inspector/src/main.rs

### 🟡 LOW — Single-shot GET requests panic on indexer errors

**Description:**

In the `get` subcommand, the single-item request paths (and the optional `--prepare` call) use `expect(...)` on network operations. A malicious/compromised indexer (or network fault) can return invalid data, fail signature verification, or drop the connection; the client returns an error and the inspector panics, terminating the process. Exploit path: user runs `inspector get ... latest` (or any single query); indexer responds with malformed bytes or an invalid signature; `client.*_get(...).await` returns `Err`, triggering an `expect` panic and stopping the tool.

**Affected Code:**

```rust
if prepare_flag {
    client.health().await.expect("Failed to prepare connection");
    info!("connection prepared");
}

IndexQueryKind::Single(query) => {
    let start = std::time::Instant::now();
    let seed = client.seed_get(query).await.expect("Failed to get seed");
    log_latency(start);

    ... (truncated)
```

**Recommendation:**

> Handle `Result` from `health()` and `*_get()` with `match`/`?` and print a user-friendly error (and non-zero exit code). Avoid panics on remote/IO failures.

---

### 🟡 LOW — Malformed stream message crashes inspector listener

**Description:**

In the `listen` subcommand, the code unwraps (`expect`) both the initial WebSocket connection and each received stream item. If the indexer closes the connection, sends a malformed/invalid message, or triggers a signature/decoding error (which the client surfaces as `Err(...)` items), `message.expect(...)` will panic and terminate the inspector process. Exploit path: a malicious/compromised indexer (or a network attacker that can interfere with the WebSocket connection) sends an invalid binary frame or forces an error; `client.listen()` yields an `Err`, and the inspector panics, stopping monitoring.

**Affected Code:**

```rust
let mut stream = client.listen().await.expect("Failed to connect to indexer");
info!("listening for consensus messages...");
while let Some(message) = stream.next().await {
    let message = message.expect("Failed to receive message");
    match message {
        Message::Seed(seed) => log_seed(seed
        ... (truncated)
```

**Recommendation:**

> Replace `expect(...)` on network operations with explicit error handling. For `listen`, log the error and continue/reconnect as appropriate; at minimum, exit gracefully with a non-zero status instead of panicking.

---

## client/src/consensus.rs

### 🟠 MEDIUM — Unbounded channel enables memory exhaustion

**Description:**

`listen()` bridges the WebSocket reader to an *unbounded* MPSC channel. If the server sends messages faster than the consumer reads them (or if the consumer is slow/stalled), messages will accumulate in memory without backpressure, allowing a remote endpoint to drive unbounded memory growth and potentially crash the process (DoS).

**Affected Code:**

```rust
// Create an unbounded channel for streaming consensus messages
let (sender, receiver) = unbounded();
tokio::spawn({
    let certificate_verifier = self.certificate_verifier.clone();
    let strategy = self.strategy.clone();
    async move {
        read.for_each(|message| async {
            // ...
    ... (truncated)
```

**Recommendation:**

> Use a bounded channel and apply backpressure (e.g., `tokio::sync::mpsc::channel(n)` or a bounded futures channel). Decide on an overflow policy (drop, disconnect, or apply per-message limits). Also consider enforcing maximum WebSocket message size.

---

### 🟠 MEDIUM — Empty WebSocket frame can panic client

**Description:**

In `listen()`, the code indexes the first byte of a received WebSocket binary message (`data[0]`) without checking that the message is non-empty. A malicious or compromised server (or MitM in non-TLS `ws://` mode) can send a zero-length binary frame, triggering an out-of-bounds panic inside the spawned task. This can terminate the listener task and effectively DoS any component relying on the stream.

**Affected Code:**

```rust
read.for_each(|message| async {
    match message {
        Ok(TMessage::Binary(data)) => {
            // Get kind
            let kind = data[0];
            let Some(kind) = Kind::from_u8(kind) else {
                let _ = sender.unbounded_send(Err(Error::UnexpectedResponse));
                r
    ... (truncated)
```

**Recommendation:**

> Before reading `data[0]`/slicing `data[1..]`, check `data.is_empty()` and treat empty frames as an error (or ignore them). Consider also validating a minimum length for each message type before decoding.

---

## types/src/wasm.rs

### 🟡 LOW — Large participants value can panic leader selection

**Description:**

`leader_index` converts `participants` to `u32` with `expect("too many participants")`. If this function is ever built/run in an environment where `usize` can exceed `u32` (or bindings allow passing an oversized value), an attacker-controlled `participants` can trigger a panic (WASM trap) causing denial of service. Exploitation path: attacker supplies an excessively large `participants` value to the exported WASM function, triggering the `expect` and trapping.

**Affected Code:**

```rust
pub fn leader_index(seed: JsValue, participants: usize) -> usize {
    ...
    Random::select_leader::<MinSig>(
        round,
        u32::try_from(participants).expect("too many participants"),
        (round.view().get() != 1).then_some(seed.signature),
    )
    .get() as usize
}
```

**Recommendation:**

> Avoid `expect` on untrusted inputs. Return a sentinel/error on overflow (e.g., `if participants > u32::MAX as usize { return 0; }`) and consider validating `participants > 0` before calling into leader selection logic.

---

### 🟡 LOW — Invalid identity input triggers WASM panic

**Description:**

The WASM-exposed parsing helpers decode `identity` using `.expect("invalid identity")`. Any caller that supplies malformed/short bytes will trigger a Rust panic (WASM trap), potentially crashing the module or aborting the current execution context (denial of service) instead of returning `JsValue::NULL` like other decode/verify failures. Exploitation path: if a web app/server uses these helpers to parse attacker-controlled network data (including an attacker-supplied/overridden `identity` parameter), the attacker can send a malformed `identity` to reliably trigger a trap and disrupt processing.

**Affected Code:**

```rust
pub fn parse_seed(identity: Vec<u8>, bytes: Vec<u8>) -> JsValue {
    let identity = Identity::decode(identity.as_ref()).expect("invalid identity");
    ...
}

pub fn parse_notarized(identity: Vec<u8>, bytes: Vec<u8>) -> JsValue {
    let identity = Identity::decode(identity.as_ref()).expect("invali
    ... (truncated)
```

**Recommendation:**

> Replace `.expect(...)` with fallible handling consistent with the rest of the file (e.g., `let Ok(identity) = Identity::decode(...) else { return JsValue::NULL; };`). Consider returning a richer error to JS (e.g., `Result<JsValue, JsValue>`) rather than trapping.

---

## types/src/entitlement.rs

### 🟠 MEDIUM — Entitlement ID omits constraints enabling overwrite

**Description:**

`Entitlement::id()` hashes only `grantee`, `scope`, `action`, and optional `parent_id`, but excludes `constraints`. The entitlement registry uses this ID as the storage key, so creating another entitlement with the same `(grantee, scope, action, parent_id)` but different `constraints` will deterministically collide and overwrite the existing entitlement record. Exploitation path: an authorized grantor (e.g., the Actor for `Scope::Actor`) or delegator can grant/delegate an entitlement with restrictive constraints, then later grant/delegate again with the same fields but weaker constraints (e.g., `max_uses=0`, wider validity, etc.), overwriting the stored entitlement under the same ID. Any logic that assumes the ID uniquely binds the constraints (or uses the ID as a stable reference for audit/revocation) can be bypassed or confused because the referenced entitlement can change without changing its ID.

**Affected Code:**

```rust
impl Entitlement {
    pub fn id(&self) -> EntitlementId {
        let mut buf = Vec::new();
        self.grantee.write(&mut buf);
        self.scope.write(&mut buf);
        self.action.write(&mut buf);
        if let Some(parent) = self.parent_id {
            buf.extend_from_slice(&parent);

    ... (truncated)
```

**Recommendation:**

> Include `constraints` (and any other fields that must be immutable for a given ID) in the ID preimage, or alternatively treat `(grantee, scope, action, parent_id)` as a composite key and store constraints under a separate versioned/append-only structure. If updates are intended, implement an explici... (truncated)

---

### 🟡 LOW — Unbounded vector encoding can create oversized payloads

**Description:**

Several `Write` implementations serialize `Vec<u8>` without enforcing the same maximum lengths that the corresponding `Read` implementations require via `RangeCfg` (e.g., `Scope::RunnerPool`, `Scope::Namespace`, `Action::ActorExecuteHandler`, `Action::RunnerJoinPool`, `Action::Custom`). This mismatch means internal code can construct and encode values larger than what decoders accept (or expect) and potentially create oversized transactions/messages before they are rejected elsewhere. Exploitation path: if any user-controlled input can reach these `Vec<u8>` fields prior to size checks (e.g., via JSON/Serde or RPC inputs), an attacker can cause the node to allocate/serialize large buffers (memory/CPU DoS) or create data that fails to decode on other components, leading to avoidable resource usage and interoperability failures.

**Affected Code:**

```rust
Self::RunnerPool(pool_id) => {
    4u8.write(writer);
    pool_id.write(writer);
}
Self::Namespace(ns) => {
    5u8.write(writer);
    ns.write(writer);
}
...
Self::ActorExecuteHandler(handler) => {
    9u8.write(writer);
    handler.write(writer);
}
...
Self::RunnerJoinPool(pool_id) => {
    13u8.w
    ... (truncated)
```

**Recommendation:**

> Enforce the same maximum lengths on construction/serialization as on deserialization (e.g., use newtypes with validated constructors, or check lengths in `write()` and return an error instead of blindly writing). Consider reducing maximums and applying limits at RPC/transaction boundaries as well.

---

## client/src/rpc.rs

### 🟠 MEDIUM — Unbounded response bodies may exhaust memory

**Description:**

All RPC methods read the full HTTP response into memory via `result.text().await` and then (often) parse JSON from that string. A malicious or compromised RPC endpoint (or MITM when using plain HTTP) can return an extremely large response body, causing high memory usage or OOM, potentially crashing a long-running client process/service that uses this library.

**Affected Code:**

```rust
let result = self
    .http_client
    .get(url)
    .send()
    .await
    .map_err(Error::Reqwest)?;

if !result.status().is_success() {
    return Err(Error::Failed(result.status()));
}

let text = result.text().await.map_err(Error::Reqwest)?;
let response: T = serde_json::from_str(&text).map_err
... (truncated)
```

**Recommendation:**

> Avoid buffering unbounded responses in memory. Prefer streaming and enforce size limits (e.g., check `Content-Length`, cap bytes read, or use `Response::bytes_stream()` with a max). Also configure request/response timeouts on the underlying `reqwest::Client` builder to reduce hang/slowloris-style re... (truncated)

---

### 🟡 LOW — Unescaped path segments enable URL path injection

**Description:**

Several RPC methods interpolate caller-provided strings directly into URL paths (e.g., `key`, `job_id`, `address`) without URL-encoding or validating allowed characters. If these values come from untrusted input in an application using this client, an attacker can inject reserved characters (`..`, `/`, `?`, `#`, `%2f`, etc.) to alter the requested path/query and reach unintended endpoints on the same RPC origin (e.g., `key="../health"` causing `/block/../health`).

**Affected Code:**

```rust
pub async fn rpc_get_block(&self, key: &str) -> Result<BlockResponse> {
    let url = format!("{}/block/{}", self.uri, key);
    ...
}

pub async fn rpc_get_runner(&self, address: &str) -> Result<RunnerResponse> {
    let url = format!("{}/runner/{}", self.uri, address);
    ...
}

pub async fn rpc_
... (truncated)
```

**Recommendation:**

> Treat these parameters as untrusted: validate against strict expected formats (e.g., hex/base58/UUID) and/or URL-encode path segments (build URLs with `url::Url` and `path_segments_mut()`; reject segments containing `/` or dot-segments). Prefer strongly-typed inputs (as done with `Address` elsewhere... (truncated)

---

## chain/src/genesis.rs

### 🔴 HIGH — Default genesis creates publicly known admin key

**Description:**

`GenesisConfig::default()` provisions a funded "admin" account using a deterministic seed (`seed=0`). `address_from_seed(0)` explicitly forces the scalar to `1`, yielding a well-known secp256k1 private key. If a node/network is started without an explicit genesis config file (see engine uses `GenesisConfig::default()` when `genesis_config_path` is `None`), any attacker can derive the corresponding private key, sign transactions as the genesis-funded account, and steal funds / exercise any privileges tied to that account. Additionally, allowing genesis accounts to be specified by `seed` generally makes those accounts' private keys derivable by anyone with the genesis file.

**Affected Code:**

```rust
fn address_from_seed(seed: u64) -> Address {
    let mut scalar = [0u8; 32];
    let bytes = seed.to_le_bytes();
    scalar[..8].copy_from_slice(&bytes);
    // Ensure non-zero scalar (FAUCET_SEED = u64::MAX gives a different pattern)
    if scalar == [0u8; 32] {
        scalar[31] = 1;
    }
    le
    ... (truncated)
```

**Recommendation:**

> Remove/disable seed-based key derivation for non-test builds, and require `public_key_hex` (address only) in genesis. Avoid shipping a funded default genesis; require an explicit genesis file (or generate keys securely and store private keys out-of-band). At minimum, refuse `GenesisConfig::default()... (truncated)

---

### 🟡 LOW — Total balance sum can overflow in validation

**Description:**

`GenesisConfig::validate()` computes `total_balance` by summing `u64` balances. In release builds, `u64` addition overflows with wraparound, so a malicious/erroneous genesis config can make `total_balance` wrap to a small value and incorrectly pass the `total_balance > total_supply` check. If callers rely on `validate()` to enforce the supply invariant, this can permit genesis allocations that exceed `total_supply`. Note: in the current codebase, `validate()` does not appear to be called before genesis initialization, which reduces immediate exploitability but increases the chance that future callers rely on a flawed check.

**Affected Code:**

```rust
pub fn validate(&self) -> Result<(), String> {
    let total_balance: u64 = self.accounts.iter().map(|acc| acc.balance).sum();

    if total_balance > self.total_supply {
        return Err(format!(
            "Total account balances {} exceed total supply {}",
            total_balance, self.total
    ... (truncated)
```

**Recommendation:**

> Use checked arithmetic (e.g., `try_fold` with `checked_add`) or accumulate in `u128`, and fail validation on overflow.

---

## indexer/test/test_indexer.sh

### 🟡 LOW — Untrusted BASE_URL enables curl option injection

**Description:**

BASE_URL is taken directly from the first script argument and concatenated into `url`, which is then passed to `curl` without a `--` end-of-options marker. If a user/CI job passes a BASE_URL beginning with `-` (e.g., `--config=...`, `-o...`, etc.), `curl` can interpret it as additional options rather than a URL, potentially causing unexpected file reads/writes (via curl config/output flags) or network requests.

**Affected Code:**

```bash
BASE_URL="${1:-http://localhost:8080}"
...
url="${BASE_URL}${endpoint}"

if [ -n "$data" ]; then
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" -d "$data" 2>/dev/null || echo -e "\n000")
else
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" 2>/dev/null || echo -e "\n000
    ... (truncated)
```

**Recommendation:**

> Validate BASE_URL to only allow expected schemes/characters (e.g., require it to match `^https?://`), and pass the URL to curl after `--` to prevent option parsing: `curl ... -- "$url"`. Consider also rejecting BASE_URL values starting with `-`.

---

## ./run_build.sh

### 🟡 LOW — Relative rm -rf may delete unintended directory

**Description:**

The script deletes a relative path (`rm -rf test`) without first ensuring it is running from the repository root (or otherwise constraining the target path). If this script is executed from an unexpected working directory (e.g., in CI or by another wrapper), it may delete an unintended `./test` directory in that context, potentially causing data loss or disrupting the build environment.

**Affected Code:**

```bash
rm -rf test
```

**Recommendation:**

> Resolve paths relative to the script location and add basic safety guards. Example: `set -euo pipefail; SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; rm -rf -- "$SCRIPT_DIR/test"` (optionally verify the directory exists and matches expectations before deleting).

---

## chain/src/lib.rs

### 🟠 MEDIUM — Serializable config includes validator private key

**Description:**

`chain::Config` derives `Serialize` and contains highly sensitive fields (`private_key`, `share`, `polynomial`). This makes it easy for other parts of the codebase (or downstream users of the crate) to accidentally serialize and persist/emit these secrets (e.g., logging the config as YAML/JSON for debugging, returning it from an admin API, or including it in crash reports/telemetry). In this repository, the config type is explicitly used for YAML configs (e.g., validator setup tooling writes `Config` to disk). If such config output is ever exposed (misconfigured log shipping, world-readable config directory, accidental RPC endpoint), the validator's signing key can be recovered and used to impersonate the validator and sign arbitrary consensus/network messages as that identity.

**Affected Code:**

```rust
#[derive(Deserialize, Serialize)]
pub struct Config {
    pub private_key: String,
    pub share: String,
    pub polynomial: String,
    ...
}
```

**Recommendation:**

> Avoid deriving `Serialize` for types that contain secrets, or ensure secret fields are skipped/redacted during serialization (e.g., `#[serde(skip_serializing)]` or custom `Serialize` that emits "****"). Consider splitting into (1) a loadable on-disk config struct and (2) an in-memory runtime config... (truncated)

---

## indexer/src/main.rs

### 🟠 MEDIUM — Indexer API exposed on all interfaces

**Description:**

The indexer binds its HTTP server to `0.0.0.0` unconditionally, exposing all routes (including state-mutating POST endpoints like `/submit`, `/seed`, `/notarization`, `/finalization` and websocket streams) to any network that can reach the host. Since this binary provides no option to bind to localhost or restrict access, a default run on a machine with a public/reachable interface can be abused by remote users to spam submissions, open websocket connections, and generally increase attack surface/DoS risk. Exploitation path: an attacker on the same network/Internet connects to the host's `:8080` (or chosen port) and repeatedly POSTs large/invalid payloads and/or opens many websocket connections, consuming CPU/memory/bandwidth and polluting downstream consumers.

**Affected Code:**

```rust
// Start server
let addr = format!("0.0.0.0:{}", args.port);
let listener = tokio::net::TcpListener::bind(&addr).await?;
axum::serve(listener, app).await?;
```

**Recommendation:**

> Make the bind address configurable (default to `127.0.0.1` for a "local activity" indexer), and/or add network-layer protections (auth, mTLS, IP allowlist, reverse proxy). Consider adding request body limits and connection/rate limiting in the server stack.

---

## runner/src/types.rs

### 🟠 MEDIUM — Unbounded hex decode enables memory exhaustion

**Description:**

`JobSpec` and `RunnerResult` custom deserializers hex-decode the `job_id` string into a `Vec<u8>` before checking that it is exactly 32 bytes. An attacker can submit JSON with a very large `job_id` hex string (e.g., via job submission or result submission transaction payloads) causing `hex::decode()` to allocate proportional memory and burn CPU before failing the length check, potentially leading to process OOM or degraded node performance (DoS). This is reachable because the execution layer deserializes untrusted `job_spec_bytes` / `result_bytes` with `serde_json::from_slice`.

**Affected Code:**

```rust
let job_id_bytes =
    hex::decode(h.job_id.trim_start_matches("0x")).map_err(serde::de::Error::custom)?;
if job_id_bytes.len() != 32 {
    return Err(serde::de::Error::invalid_length(
        job_id_bytes.len(),
        &"32 bytes",
    ));
}
let mut job_id = [0u8; 32];
job_id.copy_from_slice(&job_
... (truncated)
```

**Recommendation:**

> Reject oversized/invalid `job_id` strings before decoding. After stripping an optional `0x` prefix, require exactly 64 hex characters, and decode directly into a fixed `[u8; 32]` buffer (e.g., `hex::decode_to_slice`) to avoid large allocations. Consider enforcing an overall max size for job spec/res... (truncated)

---

## chain/src/error.rs

### 🟡 LOW — Raw PVM error details echoed to clients

**Description:**

`actor_execution_error()` attaches the raw PVM error string to the HTTP JSON response (`details.raw_error`) and, in the generic fallback, also embeds the raw error into the user-facing `message`. If the PVM runtime error contains stack traces, file paths, runtime versions, or other internal diagnostics, a remote caller can intentionally trigger failures (e.g., by submitting actor code that raises exceptions) and have the node disclose environment/internal implementation details in the API response.

**Affected Code:**

```rust
pub fn actor_execution_error(raw: &str) -> Self {
    // Attempt to produce a more actionable message from known PVM error patterns
    let (message, why, suggestion, docs_url) = pvm_error_guidance(raw);
    let mut err = Self::new(
        StatusCode::UNPROCESSABLE_ENTITY,
        ErrorCode::ActorE
    ... (truncated)
```

**Recommendation:**

> Do not return raw runtime errors to untrusted clients. Return a stable high-level error code/message and log the raw error server-side (optionally gate raw error behind an explicit debug flag and/or redact sensitive patterns; enforce a max length on returned error strings).

---

## client/src/events.rs

### 🟠 MEDIUM — Unbounded queue and detached task enable DoS

**Description:**

`Stream::new` and `Stream::new_with_verifier` spawn a background task that continuously reads from a WebSocket and forwards decoded messages into an **unbounded** MPSC channel. If the consumer is slow (or stops consuming), an attacker-controlled/compromised server can send messages faster than they are processed, causing unbounded memory growth and process OOM. Additionally, the spawned task is stored only as a `JoinHandle` and is never aborted on `Stream` drop. In Tokio, dropping a `JoinHandle` detaches the task; if the receiver is dropped while the WebSocket is idle (no further sends to fail), the task can remain blocked on `ws.next().await` indefinitely, keeping the socket and task alive. Repeated connect/drop cycles can accumulate tasks and open connections, leading to file-descriptor/task exhaustion. Exploitation path: connect to the client's websocket endpoint (or MITM/compromised endpoint), then (a) flood binary frames to build an unbounded backlog, or (b) keep connections idle while the client drops/replaces streams (e.g., reconnect logic), causing leaked background tasks and sockets until resource exhaustion.

**Affected Code:**

```rust
pub struct Stream<T: ReadExt + Send + Sync + 'static> {
    receiver: mpsc::UnboundedReceiver<Result<T>>,
    _handle: tokio::task::JoinHandle<()>,
}

pub(crate) fn new<S>(mut ws: WebSocketStream<S>) -> Self {
    let (tx, rx) = mpsc::unbounded_channel();
    let handle = tokio::spawn(async move {

    ... (truncated)
```

**Recommendation:**

> Use a bounded channel (e.g., `mpsc::channel(n)`) and apply backpressure (await on send) or drop/close on overflow. Enforce websocket read/message size limits (via tungstenite config where the connection is created). Implement `Drop` for `Stream` to abort the task (e.g., `self._handle.abort()`), or a... (truncated)
