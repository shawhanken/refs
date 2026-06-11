# Node Hardening backlog — easy-to-hard triage (2026-06-10)

**Scope:** Linear project **"Node Hardening, Tooling & Supporting Work"**, unresolved
issues (Todo / In Progress / Backlog) assigned to **pavilionledger** or **unassigned**.
**166 issues** total at query time (3 In Progress, 54 Todo, 109 Backlog; 33 assigned
to pavilionledger, 133 unassigned).

**Method:** Linear GraphQL export (title, description, priority, state, assignee,
labels) cross-checked against the local workspace:

- Audit-finding target files verified present: `node/cli/src/key_format.rs`,
  `node/client/src/rpc.rs`, `node/indexer/test/test_indexer.sh`.
- `cowboy/examples/` verified: all 33 example directories exist, plus shared
  harness scripts (`_run_examples_common.sh` etc.).
- The CIP-15 gateway crates (`crates/gateway-server`, `gateway-cbfs`,
  `gateway-cache`, `gateway-chain`, `gateway-x402`) referenced by COW-878…903 are
  **not in this workspace** — that repo must be cloned before any Tier 5 work.

Difficulty here means *effort + risk to land a correct change*, not value. Within
each tier, items are listed in recommended execution order.

---

## Tier 0 — excluded / do not start (≈25 issues)

| Reason | Issues |
|---|---|
| Umbrella/parent containers, not independent work items | COW-482 (CLI), COW-492 (SDK), COW-495 (Error Messages), COW-498 (AI Context) |
| Explicit placeholder / blocked on another CIP | COW-220 (access list "reserved"), COW-883 (blocked on CIP-18), COW-891 (blocked on Volume serving landing) |
| Other team's scope + needs spec decision | COW-2199 (JobSpec protocol caps — CIP-2 is owned by another team) |
| Needs cloud/infra credentials, not a code-difficulty problem | COW-508, COW-513, COW-514, COW-515 (AWS API Gateway / Tailscale / terraform); COW-462, COW-473 (public RPC + monitoring infra); PyPI-publishing half of COW-751 |
| Code not in this workspace (console/dashboard product) | COW-525, COW-526, COW-527, COW-823, COW-2172 |
| Very large greenfield or non-engineering | COW-439–445 (playground, explorer, marketplace, grants — all prio 4) |

---

## Tier 1 — easiest: security-audit LOW cluster (hours each, single-file)

All target files verified to exist; fixes are prescribed in the findings.
Recommended first batch — clearable in about a week:

1. **COW-628** — `indexer/test/test_indexer.sh`: add `--` separator to curl, validate
   `BASE_URL` against `^https?://`. Shell one-liner class.
2. **COW-620** — `cli/src/key_format.rs`: bound PEM body size (reject non-32-byte keys).
3. **COW-627** *(pavilionledger)* — `client/src/rpc.rs`: validate/URL-encode caller
   strings interpolated into URL paths.
4. **COW-707** *(pavilionledger)* — warn when default dev RPC endpoint is plain HTTP.
5. **COW-705** *(pavilionledger)* — restrict or document `actor execute --payload @<file>`
   as privileged.
6. **COW-754** *(pavilionledger)* — gate Swagger UI / OpenAPI spec exposure behind config
   (off by default on devnet).
7. **COW-762** — redact `/health/detailed` (version, uptime, component status).

## Tier 2 — easy but time-consuming: docs & static files (no breakage risk)

- **AI-context files:** COW-397 (SKILL.md), COW-399 / COW-500 (.cursorrules in init
  output), COW-400 / COW-501 (llms.txt), COW-499 (Skills for Claude/Codex/OpenClaw).
  Note 399/500 and 400/501 are near-duplicates — handle as pairs.
- **Ops runbooks (pure writing):** COW-474 (snapshots + restore), COW-475 (incident
  runbook).
- **Developer docs:** COW-57 / COW-408 (quick start; near-duplicates), COW-120 (actor
  tutorial), COW-143 (deployment), COW-173 (config reference), COW-179
  (troubleshooting), COW-87 (RPC API reference), COW-409 / COW-410 / COW-412
  (concepts / how-to guides / PVM reference — all pavilionledger, Todo), COW-413
  (annotated examples), COW-422 (architecture deep-dives), COW-502 (getting started +
  example actors), COW-503 (pvm_host API docs), COW-749 (README + quickstart).
- **COW-411** (auto-generated SDK reference) — toolchain setup, end of this tier.

## Tier 3 — medium: well-bounded single-repo code features

1. **COW-819** — expose `schedule_timer` / `cancel_timer` in the Python SDK runtime
   (already implemented on pvm_host; labeled Bug).
2. **COW-880 / COW-881** *(pavilionledger)* — verify `path_params` delivery and
   named-handler dispatch through `/actor/read` + `/submit_wait` ("likely already
   works" — mostly tracing + adding e2e tests).
3. **COW-490 / COW-491 / COW-489** — CLI wallet create / account info / actor logs
   (490 and 491 are In Progress — check existing code first; may be near-done).
4. **COW-392** — JUnit XML test output for CI.
5. **COW-2092** — speed up node CI (parallelize clippy, decouple build from test
   gate; measurable outcome).
6. **COW-149** — CLI `tx sign` command.
7. **COW-393** — pre-deploy gate (tests must pass).
8. **COW-373** — `cowboy.yaml` local-dev config format (small design first).
9. **COW-364 + COW-402** — `cowboy init` scaffolding + minimal Hello World template
   (do together).
10. **COW-218** — RPC API version in URL path.
11. **COW-363** — CLI secrets management (can build on existing `cbss/`).

## Tier 4 — medium-hard: examples cluster (dependency-ordered)

Infrastructure first, then individual examples:

1. **COW-1344** (Docker example harness) → **COW-1346** (examples CI smoke suite) →
   **COW-1347** (CLI/read semantics compatibility).
2. **COW-824** — Mesa validator fails loading actors whose `runner.llm()` prompt is
   built from multi-line f-string concatenation (PVM import/load bug; likely a root
   cause behind several failing examples — investigate early).
3. Then the 31 per-example issues (COW-481, COW-750, COW-1310…1342):
   - Non-runner examples first (01-tokens, 18-ring-demo, 21-pure-timer-scheduler, …).
   - External-API-dependent examples are hardest (08-audio-transcription,
     09-image-generation, LLM-based ones).
   - **COW-1329** (19-texas-holdem) and **COW-1342** (erlangcowboydemo) lack READMEs —
     extra scoping work; do last.

## Tier 5 — hard: CIP-15 gateway cluster (COW-878…903) — ⚠ repo not in workspace

`crates/gateway-*` must be cloned first. Specs are detailed (CIP-15 + impl-guide
references in each issue). Easy-to-hard order within the cluster:

**COW-889** (resolve_volume_path pure function + unit tests) →
**COW-895** (fail-closed on malformed CBOR routes; mostly tests) →
**COW-890** (SPA fallback object) →
**COW-884 / COW-885** (per-volume metadata cache; object LRU) →
**COW-898 / COW-899 / COW-901** (ETag/If-None-Match; Accept-Encoding variants; compressed-variant cache) →
**COW-896 / COW-897** (CORS precedence for Method routes; CORS for Volume routes + preflight) →
**COW-893** (MANIFEST_POLL_INTERVAL refresh loop) →
**COW-903** (single-flight coalescing) →
**COW-902** (cache warming on registration) →
**COW-887 / COW-888** (GET_SHARD client + K-shard Reed-Solomon reconstruction +
BLAKE3 integrity chain — heaviest pieces) →
**COW-900** (hedged parallel shard fetch) →
**COW-892** (retire HttpCbfsClient prototype; depends on 887/888) →
**COW-879** (storage-status-driven Volume serving; depends on the whole Volume path) →
**COW-878 / COW-882** (churn metric; ops metrics surface).

Also in this dependency chain: **COW-891** (405 on non-GET/HEAD) — unblocked once
Volume serving lands (currently Tier 0/blocked).

## Tier 6 — hardest: consensus-sensitive core / large greenfield

- **COW-69** — block ring buffer for immediate timers (node core, consensus-sensitive;
  needs Marshal-level review).
- **COW-234** — block production pause/resume API (engine management plane).
- **COW-389** — message-sequence fuzzing / property testing.
- **Frontend SDK:** COW-432 → COW-435 → COW-433 *(435/433 pavilionledger)* → COW-434 →
  COW-436. Large, but `wallet/` already has byte-compatible secp256k1 + deterministic
  CBOR signing to reuse.
- **Templates:** COW-403–407 (depend on DEX/oracle/Watchtower components that are not
  stable yet).
- **IDE/Linter:** COW-394 first (PVM linter can reuse `validate_actor_code` rules from
  `node/execution/src/pvm_executor.rs`), then COW-390 / 391 / 395 / 396 / 398 / 421
  (VS Code extension greenfield).
- **Advanced CLI:** COW-414 (TUI dashboard), COW-418 (cross-block trace), COW-416
  (MCP doc server), COW-419 (snippet registry), COW-401 (CI auto-generate context).
- **Upgrades:** COW-420 → COW-428 → COW-429 → COW-430 → COW-415 (versioned upgrades +
  state migration + rollback; design-first).

---

## Recommended starting sequence

1. **Tier 1 (7 security LOWs)** — small, prescribed, four already assigned to
   pavilionledger (627, 705, 707, 754).
2. **COW-819** — real bug, small surface.
3. **COW-880 / COW-881** — verification-style tasks with e2e-test deliverables.
4. Then either the docs lane (Tier 2) in parallel with Tier 3 code items, or the
   examples-infra chain (COW-1344 → 1346) if example reliability is the priority.

*Raw export: full issue list with state/assignee in `/tmp/node_issues.tsv` (ephemeral);
query: Linear GraphQL, project id `53a491c6-293e-40b2-a6ea-a35a364421f5`, states
triage/backlog/unstarted/started, assignee pavilionledger or null.*
