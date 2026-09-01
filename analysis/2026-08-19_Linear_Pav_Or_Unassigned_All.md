# Linear：指派 pavilionledger 或未指派的 issue 全量清单

**查询口径**：`assignee == pavilionledger@gmail.com` 或 `assignee == null`；状态类型排除 completed / canceled / duplicate。
数据时点：2026-08-19。团队 COW + DES 全部 project，无其他过滤。

**合计 537 条**（COW 427 · DES 110；pavilionledger 69 · 无人 468）

状态分布：Backlog 416 · Todo 53 · Triage 39 · In Review 19 · In Progress 8 · In Iteration 1 · Blocked 1

---

## (无 project) — 109 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2291 | In Progress | pav | [MED][node/pvm] Object identity surfaces (`id()`, default `hash()`, default `repr()`) are observable to actor code → consensus fork if returned/stored |
| COW-2906 | In Progress | — | [Node/PVM] COW-1401 memory-allocation guard misses InplaceMultiply (x *= n) — bypasses the metering flag-day |
| COW-3099 | In Progress | pav | CI/release security: register Marshal invariants for cowboy-protocol (+ enable on cbqs), and gate all three wasm publish workflows |
| COW-2614 | In Review | — | gateway: retry in-flight E1002 nonce reverts internally instead of surfacing to clients |
| COW-2909 | In Review | — | [Node/PVM] sys.getrefcount() leaks warm-pool-dependent Arc strong count -> consensus fork (tracking) |
| COW-3127 | In Review | — | SetActorQuota bond debits atto against wei balance — 1e9 overcharge (shrink over-refunds) |
| DES-126 | In Iteration | — | Drag-to-CBFS: drop states, cost preview, progress & resume |
| DES-43 | Triage | — | Design OG share image (1200×630) + high-res brand logo for cowboy.inc |
| DES-44 | Triage | — | Approve canonical brand boilerplate; align X / GitHub / Discord descriptions |
| DES-45 | Triage | — | Verify cowboyinc GitHub org (domain verification) |
| DES-46 | Triage | — | Link whitepaper on site somewhere |
| DES-48 | Triage | — | Set up Google Search Console for cowboy.inc + submit sitemap |
| COW-2994 | Todo | — | harness: action-result takes the action owner before verifying the signature |
| COW-2995 | Todo | — | dashboard: conversation + agent APIs are unauthenticated (wallet address treated as authorization) |
| COW-2998 | Todo | — | skills repo: add a policies/ folder for company-wide engineering policies |
| COW-3003 | Todo | — | gateway: consume CIP-15 route types from cowboy-protocol and delete the local copy |
| COW-3005 | Todo | — | CIP-15: canonicalize verb ordering is declaration order, spec says alphabetical |
| COW-3006 | Todo | — | gateway: WorkloadId encoder emits raw bytes, decoder expects a string |
| COW-3007 | Todo | — | CIP-15: runner timeout is 120000 in gateway, 300000 in the spec |
| COW-3008 | Todo | — | cowchat: warn when an agent is alone in a room (silent split-brain deadlock) |
| COW-3014 | Todo | — | CI: PR-authored code executes with cross-repo PAT readable (macos ungated, runner label-gated) |
| COW-3015 | Todo | — | macOS release.yml: bridge builds authorize cargo but never enable the git CLI fetcher |
| COW-3016 | Todo | — | macOS: replace the .protocol-src symlink with a rev-pinned git dependency |
| COW-3017 | Todo | — | macOS: protocol-codec-ffi docs contradict the merged implementation |
| COW-3018 | Todo | — | macOS: open the signing gate — wire CowboyProtocolCodec into the transaction approval path |
| COW-3209 | Todo | — | [Node] A previous owner can silently overwrite a TRANSFERRED volume by re-creating it under the same name |
| COW-2231 | Backlog | — | AI builder sends referenced local .py files to dashboard_url without confirmation |
| COW-2332 | Backlog | — | [CI/Infra] GitHub-hosted Actions runners unavailable ~6.7h — all node PRs blocked (recurring, 2nd today) |
| COW-2340 | Backlog | — | Reconcile continuation/checkpoint model: two divergent SDK record formats + fsm-vs-checkpoint mode docs drift |
| COW-2414 | Backlog | — | Canyon-reset: re-register RAS owner delegations post-genesis + volume-create success-gate (COW-2341 ops follow-up) |
| COW-2415 | Backlog | — | cbss.reshare.requested watcher completeness under burst — actor event log 1000-cap trims oldest (COW-2338 follow-up) |
| COW-2442 | Backlog | — | CIP-24/CBSS: salted or name-encrypted key_hash — secret key-name privacy is dictionary-limited |
| COW-2500 | Backlog | — | CIP-34 chat demo: transfer leg mints instead of debiting a real source account |
| COW-2529 | Backlog | — | Corroborate /height tip across the anchor quorum (state-proof freshness) [gateway] |
| COW-2530 | Backlog | — | Add fetch_and_verify_absence stale-proof unit test (gateway HTTP mock) [gateway] |
| COW-2545 | Backlog | — | Re-sync local-tools/cbfs-pinned vendored tree (stale epoch + rent constants) |
| COW-2546 | Backlog | — | Standalone cowboy-ras repo carries drifted rent constants — align with cowboy-protocol params or archive |
| COW-2547 | Backlog | — | RAS write relayer: unreachable-relay report retry storm (~45k/day) — reports rejected because target relay is Active |
| COW-2574 | Backlog | — | [Node/RAS] PoR P5 slashing prerequisites: validate challenged shard/range membership + make challenges costly |
| COW-2622 | Backlog | — | volume create succeeds with 0 relays when auto-assign can't satisfy k+m — unusable volume, stuck escrow |
| COW-2678 | Backlog | — | CIP-18 P2.5 (deferred): headerless subscription free-serve needs gateway account-auth verification |
| COW-2702 | Backlog | — | [Node] BankActor: TransferOwnership + SetPolicy card instructions (CIP-28 §5.4) |
| COW-2732 | Backlog | — | Activate canonical result.data preimage (lower CANONICAL_RESULT_PREIMAGE_ACTIVATION_HEIGHT) — WP §207 |
| COW-2735 | Backlog | — | Defer dashboard deployment identity validation until wallet-session auth |
| COW-2743 | Backlog | — | Split app target per environment to stop Xcode scheme BuildableName churn |
| COW-2785 | Backlog | — | Make publish_chain_root committee-mode structural (chain-enforced) — COW-2550 EconomicBond default silently downgrades it to a single relayer |
| COW-2786 | Backlog | — | CI retries=1 masks a class of load-flakes in the big_stack --workspace tests (PVM/bank/emit + cowboy-chain test_200) |
| COW-2787 | Backlog | — | python-sdk CI never installs the native cowboy-crypto wheel → CBSS AAD/wrap-key parity vectors skip in CI |
| COW-2795 | Backlog | — | [CIP-28 §5.3] Card lazy-expiry conformance follow-up (H2 + advisories) before COW-1140 activation |
| COW-2798 | Backlog | pav | [PVM] Complete CIP-3 §2.2.4.4 memory metering: incremental-growth + sized-iterable constructors (COW-1401 follow-up) |
| COW-2799 | Backlog | — | [PVM] Audit + meter remaining native bulk-materialization sinks (join-family, sorted result, %/format) — CIP-3 §2.2.4.4 |
| COW-2801 | Backlog | — | [/bug] sometimes the screen scrolls so far down the conversation looks blank |
| COW-2840 | Backlog | pav | [PVM] COW-2434 baseline freeze is not applied on the continuation/checkpoint path — every baseline object is mutable there |
| COW-2841 | Backlog | — | node: emit execution-error codes from cowboy-protocol-types::error_codes consts + cross-repo equivalence test |
| COW-2845 | Backlog | — | STF Actor/Custom/Library instruction arm lacks per-transaction state atomicity (pre-existing) |
| COW-2848 | Backlog | — | Complete System writeback-boundary + executor-buffer atomicity (deferred from #1169, non-exploitable) |
| COW-2849 | Backlog | — | Bank lazy-expiry write-then-Err transitions are reverted by the STF guard-rejection rollback — fix before COW-1140 activation |
| COW-2885 | Backlog | pav | stdlib_manifest_digest is never pinned or compared — guest-stdlib drift detection is inert |
| COW-2886 | Backlog | — | examples: the three runner-continuation gates admit runner-http's `{raw, content_type}` fallback (newly reachable after cowboy#293) |
| COW-2892 | Backlog | — | [Node] CIP-18 actor-funded budget deduct_budget skips the §18 revenue split (deducted CBY burned, protocol fee uncollected) |
| COW-2902 | Backlog | — | [Node] CIP-24 §3.5: CBSS proxy registration stake is never returned (unbond completion unimplemented) — live fund loss + registry brick |
| COW-2917 | Backlog | — | CBQS 0x17: unbounded permanent chain-state growth at gas-only cost (launch blocker) |
| COW-2946 | Backlog | pav | Actor-authored credit to tx.from is erased — transfer_balance(get_sender(), x) destroys CBY (stale sender snapshot overwrites flush_balances) |
| COW-2951 | Backlog | — | WS-E follow-up: pin the deferred-System-SUCCESS path with a golden + clean up the now-dead system_events clear |
| COW-2952 | Backlog | — | [TEE] Nitro on-chain attestation verification is an unbuilt CIP-23 P3 stub — Nitro attestations never verify end-to-end |
| COW-2966 | Backlog | — | [/bug] something broke |
| COW-2967 | Backlog | — | [/bug] something broke |
| COW-2978 | Backlog | — | cbfs: committed-immutability guard is check-then-put — racing PutShard can land tentative over committed bytes |
| COW-3035 | Backlog | — | [Node/CI] pvm-runtime test suite is order-dependent — same tree gives 1 or 114 failures |
| COW-3041 | Backlog | — | [PVM] memory_cells_budget is baked into the interpreter but derived per frame — stale budget on a pool hit |
| COW-3101 | Backlog | — | [PVM] preflight namespace verdict discards a working netns: `enter_full().is_ok()` collapses Full/Skip on hosts where only the id-map write fails |
| COW-3106 | Backlog | — | Rent settlement subtracts atto from wei balance — drains entire actor balance at first settlement |
| COW-3107 | Backlog | — | BankActor default-card gas: any caller drains a card-funded agent's caps (no caller dimension); policy denial bricks instead of falling through |
| COW-3108 | Backlog | — | pvm_sdk checkpoint helper faults snapshot on _HashedSeq |
| COW-3130 | Backlog | — | Reconcile gas-lane assignment: deployed tx_lane routes non-Job system instructions (incl. TEE attestation) to System lane; WP lane tables say Runner |
| COW-3146 | Backlog | — | DeleteShard existence oracle + unattributed shards readable under any volume token |
| COW-3165 | Backlog | — | Consolidate AccessMode into a single cowboy-protocol type |
| COW-3179 | Backlog | — | [CBFS] VolumeStatus enum drift: registry-proto has 4 variants vs the chain's 6, with no #[serde(other)] |
| COW-3184 | Backlog | — | cowboy CLI: add `volume create` verb + `put` pointer stub |
| COW-3186 | Backlog | — | [CBFS] cbfs rebalance reports failure on a committed placement, and repeats the same move forever |
| COW-3187 | Backlog | — | [CBFS] classify_publish_outcomes calls a conflict BELOW the caller's baseline `Superseded`, and the CLI then re-baselines downward |
| COW-3192 | Backlog | — | explorer-v2: token created_at height never indexed (field-name mismatch) |
| COW-3193 | Backlog | — | explorer-v2: /api/admin/* endpoints unauthenticated (incl. destructive delete-actors) |
| COW-3195 | Backlog | — | Agent jobs do not execute on current devnet runners — #209 removed the in-runner AgentExecutor pending cowboy-harness |
| COW-3201 | Backlog | — | runner.agent has no plain-chat mode — plain chatbots always get empty answers (tools always sent + tool_choice=auto; codegen tools hardcoded) |
| COW-3207 | Backlog | — | [Node] devnet is red: 4 cow2930_diff_tests fail when the module runs together, pass in isolation |
| COW-3208 | Backlog | — | Resolve agent model discovery against the declared catalog, not live /v1/models |
| COW-3227 | Backlog | — | canyon regenesis cannot mirror the funded keypair to Secrets Manager, so genesis-keypairs is silently chains-stale |
| COW-3228 | Backlog | — | the canyon reset's e2e success gate cannot pass against the versions it pins, and swallows the error that says why |
| COW-3236 | Backlog | — | [CBFS] repair_prefers_highest_capacity_replacement takes 150s against a 240s hard kill and dominates CI wall time |
| COW-3237 | Backlog | — | [CBFS] Tests write ~87 files into $HOME/.cbfs and require HOME to be set |
| COW-3239 | Backlog | — | Dashboard network-status probe budget is below real canyon latency |
| COW-3240 | Backlog | — | Faucet fetch budget sits at the observed latency ceiling |
| COW-3241 | Backlog | — | SDK: pending-diff reconciliation can permanently wedge a volume (merged in #144) |
| COW-3243 | Backlog | — | Runner heartbeat lockout: saturated nonce window has no admissible nonce — clamp was a no-op |
| COW-3245 | Backlog | — | [CBFS] No implemented surface can remove a ManifestEntry::Directory — not even for the owner |
| COW-3251 | Backlog | — | [CBFS] prune_empty_dirs deletes a freshly mkdir'd directory's inode on the next pull, and its mode is then committed as default |
| COW-3252 | Backlog | — | [CBFS] Manifest::insert has no kind check, so a file write can overwrite a Directory or Symlink entry |
| COW-3278 | Backlog | — | [CBFS] chmod/chown on a directory learned from a pull is silently dropped |
| COW-3279 | Backlog | — | [CBFS] Metadata the owner CLEARED is resurrected by a stale local inode on the next push |
| COW-3280 | Backlog | — | [CBFS] fsync performs a full manifest commit whenever any metadata op is outstanding |
| COW-3287 | Backlog | — | A mesa deploy today rolls it back 6 weeks — envs/mesa.yml pins `latest`, and mesa's `latest` pointers are frozen at 2026-06-18 |
| DES-125 | Backlog | — | Import wizard: scan → review → import (the switch) |
| DES-127 | Backlog | — | Gateway suggestions on the dashboard (installed-app detection) |
| DES-128 | Backlog | — | Menu bar: icon states + panel |
| DES-129 | Backlog | — | Files surface: local folders + volumes side by side (two-tier model) |
| DES-130 | Backlog | — | First-run splash: sign-in handoff |
| DES-159 | Backlog | — | Homestead — Gallop design pass |
| DES-34 | Backlog | — | Partner SDK: drop-in mobile chat components |

## Dashboard Beta — 80 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| DES-21 | Blocked | — | Account switching |
| DES-100 | Triage | — | Actor detail: main action + action row (Top up, Edit in Builder, New conversation) |
| DES-101 | Triage | — | Hired actor page: Hire panel, access states, Restart |
| DES-102 | Triage | — | Actor detail tabs: Activity, Messages, Jobs, Timers, Transactions, Connections, Data |
| DES-103 | Triage | — | Listing management section on the actor page |
| DES-104 | Triage | — | Actor type modules: trading, feeds, website, automation, research, decisions, posse, token |
| DES-105 | Triage | — | Posse: index grouping + Members section on the coordinator page |
| DES-106 | Triage | — | Share card + onramp flow |
| DES-107 | Triage | — | Store landing: Featured / Charts / Categories / Search + small-catalog layout |
| DES-108 | Triage | — | Store charts: four commerce charts + model/runner usage lists |
| DES-109 | Triage | — | Actor listing pages: paid / free + shared template |
| DES-11 | Triage | — | Secrets location |
| DES-110 | Triage | — | Hire checkout & confirmation |
| DES-111 | Triage | — | Posse listing page: members module + combined running cost |
| DES-112 | Triage | — | Creator profile & handle setup |
| DES-113 | Triage | — | Feed subscribe & manage flow |
| DES-115 | Triage | — | Indicate if you are chatting with builder actor or other actor (from chat nav + in sidebar) |
| DES-132 | Triage | — | Actor page: Adjustable variables — typed settings, no redeploy |
| DES-133 | Triage | — | Actor page: Connections module + per-actor notification controls |
| DES-134 | Triage | — | Gateway tab shell and left rail |
| DES-135 | Triage | — | Connections list and status model |
| DES-136 | Triage | — | Connection detail pane |
| DES-137 | Triage | — | Add-connection wizards |
| DES-138 | Triage | — | Channels zone and setup flows |
| DES-139 | Triage | — | Notification routing matrix and settings |
| DES-140 | Triage | — | Notification bell and history page |
| DES-141 | Triage | — | Notification content: families and structured owner messages |
| DES-142 | Triage | — | Alert-actor creation flow |
| DES-18 | Triage | — | Notifications |
| DES-19 | Triage | — | Settings |
| DES-23 | Triage | — | Send/Receive |
| DES-9 | Triage | — | Builder Chat Action Buttons |
| DES-91 | Triage | — | [Product Design request] submission |
| DES-98 | Triage | — | Actors index: Owned/Hired filter, attention system, hired cards |
| DES-99 | Triage | — | Actor detail: health states, chart metrics, Code tab, search |
| COW-2520 | Todo | — | Notifications |
| DES-116 | Todo | — | Hero: headline metric dropdown + chart (Total balance / P&L / Spend / Activity / Earnings) |
| DES-117 | Todo | — | Stat tiles: the fleet's work under the chart |
| DES-118 | Todo | — | View details: account ledger, cost breakdown, category taxonomy |
| DES-119 | Todo | — | Runway card: real burn math, committed split, first to run dry |
| DES-120 | Todo | — | Status panel: real state counts + Waiting on you row |
| DES-121 | Todo | — | Alerts strip |
| DES-122 | Todo | — | Recent / Up next: names and values in the feed, a real Up next tab |
| DES-123 | Todo | — | Landing rule, empty & sparse states, Gold module |
| DES-151 | Todo | — | Chatting with an actor (not builder actor) in sidebar |
| DES-65 | Todo | — | Actors and Individual Actors |
| DES-81 | Todo | — | Refreshed Overview in dashboard |
| DES-86 | Todo | — | Files |
| DES-93 | Todo | — | New volume modal |
| DES-94 | Todo | — | Add a dedicated "Skills" volume by default in Files |
| DES-96 | Todo | — | Indicator if file or volume is synced locally |
| DES-97 | Todo | — | Search results view |
| COW-3091 | Backlog | — | Show and revoke actor access to Dashboard secrets |
| COW-3229 | Backlog | — | add /loop |
| DES-153 | Backlog | — | Hired actor: Setup tasks + blocked main action |
| DES-154 | Backlog | — | Historical Hire page: after access ends |
| DES-155 | Backlog | — | Dormant actor: rent warnings + Restore flow |
| DES-156 | Backlog | — | Store search + category result pages |
| DES-157 | Backlog | — | Connection failure and recovery flows |
| DES-16 | Backlog | — | Account |
| DES-17 | Backlog | — | Account personalisation |
| DES-181 | Backlog | — | Volume list revisions |
| DES-182 | Backlog | — | File browser |
| DES-183 | Backlog | — | File viewer |
| DES-20 | Backlog | — | Private key/recovery phrase backup |
| DES-22 | Backlog | — | Account deletion flow |
| DES-33 | Backlog | — | Rename the "New chat" tab |
| DES-35 | Backlog | — | CBFS file picker in builder |
| DES-55 | Backlog | — | Store listing formats: feeds, models, runners |
| DES-56 | Backlog | — | Store trust & verification layer |
| DES-57 | Backlog | — | Publish flow with CUSD pricing |
| DES-70 | Backlog | — | Developer tab in dashboard |
| DES-71 | Backlog | — | Custom-URL theming for published actors |
| DES-72 | Backlog | — | Post-publish share upsell (Telegram, etc.) |
| DES-80 | Backlog | — | Generated icon/graphic for each actor |
| DES-82 | Backlog | — | Chat vs. Build mode: default interaction model |
| DES-83 | Backlog | — | Upsell General Store supply inside the builder |
| DES-84 | Backlog | — | Runner picker in builder |
| DES-85 | Backlog | — | Public listing & creator pages (outside the dashboard) |
| DES-90 | Backlog | — | Bring back flow of funds / visualization in builder |

## Node Hardening, Tooling & Supporting Work — 78 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-482 | In Progress | pav | CLI |
| COW-2665 | In Review | — | Validator restart must safely recover finalized placeholder zero roots |
| COW-2666 | In Review | — | Proposer must not finalize empty blocks while executable mempool work is pending |
| COW-1341 | Todo | pav | Example: 32-cowbot |
| COW-1344 | Todo | — | Project: Maintain Docker example harness |
| COW-2265 | Todo | — | mainnet launch: bundle devnet consensus-rule deltas (node#686 receipt code 1613, node#707 64 KiB inline-blob cap) into genesis / activation height |
| COW-2266 | Todo | — | Reconcile whitepaper genesis parameter defaults vs reference implementation (basefee T_c/T_b/alpha/delta, state-rent rate, lane budgets) |
| COW-508 | Todo | — | Create API Gateway module for key-gated RPC access |
| COW-513 | Todo | — | Configure Tailscale ACLs for Mesa tags |
| COW-514 | Todo | — | Set up API Gateway with usage plan and initial API keys |
| COW-515 | Todo | — | Configure IP allowlist variable in terraform.tfvars |
| COW-2172 | Backlog | — | need an option to login with a different account |
| COW-2362 | Backlog | — | Canyon RAS write-relayer: public TLS termination (port mesa #955) so chain-discovery cbfs clients work |
| COW-2919 | Backlog | — | Two canonical-CBOR encoders on node devnet disagree on integral floats — consensus bytes ≠ actor bytes |
| COW-2920 | Backlog | — | The STF timeout pass has no callback channel — terminal job failures cannot notify the actor |
| COW-3090 | Backlog | pav | Store key preimage with hashed (>32B) actor-storage rows — kills the enumeration-loss bug class |
| COW-3221 | Backlog | pav | VRF intra-block tx ordering (whitepaper §6.4) has no implementation — block order is mempool pop order |
| COW-373 | Backlog | — | Local dev: cowboy.yaml config format |
| COW-379 | Backlog | — | SDK: storage utilities and migration scaffolding (stub) |
| COW-390 | Backlog | — | IDE/Linter: VS Code extension with real-time diagnostics |
| COW-391 | Backlog | — | IDE/Linter: quickfix suggestions for PVM violations |
| COW-395 | Backlog | — | IDE/Linter: inline cost estimates (CodeLens) |
| COW-396 | Backlog | — | IDE/Linter: deploy/logs commands in command palette |
| COW-398 | Backlog | — | IDE/Linter: snippet library for common patterns |
| COW-401 | Backlog | — | AI Context: CI pipeline auto-generate from source |
| COW-403 | Backlog | — | Templates: arb-bot template for price differential trading |
| COW-404 | Backlog | — | Templates: trading-bot template (LLM signal + execution) |
| COW-405 | Backlog | — | Templates: oracle-provider template for Watchtower feed |
| COW-406 | Backlog | — | Templates: watcher template for monitoring + alerts |
| COW-407 | Backlog | — | Templates: prediction-market template (Wrangler) |
| COW-414 | Backlog | — | CLI: cowboy watch live actor TUI dashboard |
| COW-415 | Backlog | — | CLI: cowboy rollback revert to previous version |
| COW-416 | Backlog | — | AI Context: MCP server for live doc queries |
| COW-418 | Backlog | — | CLI: cowboy trace cross-block execution trace |
| COW-419 | Backlog | — | AI Context: snippet registry for AI code generation |
| COW-420 | Backlog | — | CLI: cowboy upgrade versioned upgrades |
| COW-421 | Backlog | — | IDE/Linter: actor graph visualization |
| COW-423 | Backlog | — | Observability: live state viewer in Cowchat |
| COW-424 | Backlog | — | Observability: timer timeline visualization |
| COW-425 | Backlog | — | Observability: runner job tracker |
| COW-426 | Backlog | — | Observability: message trace visualization |
| COW-427 | Backlog | — | Observability: cost breakdown and trending |
| COW-428 | Backlog | — | Upgrades: cowboy upgrade with dry-run diff |
| COW-429 | Backlog | — | Upgrades: state migration generation and validation |
| COW-430 | Backlog | — | Upgrades: rollback support with state restoration |
| COW-432 | Backlog | — | Frontend SDK: JS/TS SDK for browser interaction |
| COW-434 | Backlog | — | Frontend SDK: actor storage queries |
| COW-436 | Backlog | — | Frontend SDK: WebSocket event subscriptions |
| COW-437 | Backlog | — | Interfaces: auto-generate interface definitions from code |
| COW-439 | Backlog | — | Interfaces: on-chain interface registry |
| COW-440 | Backlog | — | Ecosystem: web-based playground / REPL |
| COW-441 | Backlog | — | Ecosystem: actor-aware block explorer |
| COW-442 | Backlog | — | Ecosystem: reusable component registry |
| COW-443 | Backlog | — | Ecosystem: actor marketplace (view source, fork) |
| COW-444 | Backlog | — | Ecosystem: bounty board and grants program |
| COW-445 | Backlog | — | Ecosystem: Corral IDE (or VS Code extension branding) |
| COW-462 | Backlog | — | Public testnet RPC endpoint (+ Status Page) |
| COW-473 | Backlog | — | Basic chain monitoring + alerting (block lag, RPC error rate, peer count) |
| COW-492 | Backlog | pav | SDK |
| COW-495 | Backlog | pav | Error Messages |
| COW-498 | Backlog | — | AI Context |
| COW-525 | Backlog | — | New version checks |
| COW-526 | Backlog | — | Install CLI as dependency |
| COW-527 | Backlog | — | Use runners from console |
| COW-751 | Backlog | pav | API reference and PyPI publishing |
| COW-823 | Backlog | — | need a list of sessions on the sidebar |
| COW-878 | Backlog | — | Routes-table churn metric (per-actor state_root change rate) |
| COW-882 | Backlog | — | Operational metrics surface (hit/miss, per-actor RPS, per-route p50/p95/p99) |
| COW-884 | Backlog | — | Per-volume metadata cache (manifest + content_types + cache_config + cors_config) |
| COW-888 | Backlog | — | Reed-Solomon reconstruction + BLAKE3 integrity chain |
| COW-893 | Backlog | — | MANIFEST_POLL_INTERVAL-driven cache refresh loop |
| COW-895 | Backlog | — | Verify fail-closed on malformed CBOR routes write |
| COW-896 | Backlog | pav | CORS precedence for Method routes (actor wins, gateway fills from cors_config) |
| COW-897 | Backlog | pav | CORS for Volume routes (apply cors_config + permissive default) |
| COW-899 | Backlog | — | Compression: Accept-Encoding → serve precomputed gzip/br variants |
| COW-900 | Backlog | — | Hedged parallel shard fetch |
| COW-901 | Backlog | — | Compressed variants in object cache |
| COW-902 | Backlog | — | Cache warming on actor registration |

## CIP-9: Cowboy File System (CBFS)-Backed Runner Storage — 40 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-3036 | In Progress | pav | [CBFS] Decide and enforce sync-daemon semantics under a write-only volume grant |
| COW-3039 | In Progress | pav | [CBFS] chmod on a partially-granted mount silently preserves bits it cannot see — decide vs POSIX apply-or-fail |
| COW-2300 | In Review | pav | [HIGH][cbfs] `AuditGetShard` returns full shard bytes with zero request authentication |
| COW-3022 | In Review | pav | [CBFS] PutShard acks before the shard is durable → torn commits |
| COW-3023 | In Review | pav | [CBFS] node blob_http store also acks before durable |
| COW-3148 | In Review | — | [CBFS/Spec] Public manifest nodes are shared across volumes with no volume binding — purging one volume destroys another's committed data |
| COW-3259 | In Review | pav | [CBFS] Fail closed on standalone volume reopen and persist key state atomically |
| COW-2113 | Todo | pav | [Node] Public-volume commit prefix-confinement check |
| COW-3149 | Todo | — | [CBFS] GET_MANIFEST ships without manifest_root, its verifying client path is dead, and public auth diverges from CIP-9 5.3.2 |
| COW-3168 | Todo | — | [Node] A garbage-collected volume stays in the PoR challenge universe forever — three challenges evict an honest relay |
| COW-2099 | Backlog | pav | [CIP-9] Rewrite epic: triage grounded findings from mesa bring-up (cip-9-rewrite-ideas.md) |
| COW-2152 | Backlog | — | [Node] Validate per_relay_effective_deltas at commit (caller-trust blast radius) |
| COW-2184 | Backlog | — | CBFS: full relay rewards distribution (pro-rata by shard count x age) |
| COW-2623 | Backlog | — | COW-918 follow-up: batch/pipeline PoR response submission to restore open-challenge cap |
| COW-2829 | Backlog | pav | [Spec/Node] CIP-9 §7 — elevate volume access to first-class access classes |
| COW-2831 | Backlog | pav | [CBFS] Zero-config CBFS client — full chain-discovery bootstrap |
| COW-2832 | Backlog | pav | [Node/Runner] Runner↔validator version & tx-format compatibility negotiation |
| COW-2833 | Backlog | pav | [CBFS] Long-lived write cap tokens for large streaming writes |
| COW-3024 | Backlog | — | [CBFS] Consolidate relay sled DBs into one Db + Trees for cross-store atomicity |
| COW-3025 | Backlog | — | [CBFS] Manifest node wire format is not forward-compatible — salvage needs version archaeology |
| COW-3027 | Backlog | — | [CBFS] Benchmark the data plane vs S3/Storj + capture shard-size distribution |
| COW-3028 | Backlog | — | [CBFS] Verify the standalone (no-Cowboy) on-ramp works for an outside user |
| COW-3029 | Backlog | — | [CBFS] Shard blob store: move to plain files (git-style), not another KV |
| COW-3053 | Backlog | — | [CBFS] Single-writer volumes — revisit the constraint |
| COW-3169 | Backlog | — | [Node/Spec] VOLUME_DELETE_GRACE_EPOCHS does not exist — the undelete window is at most one epoch and fees do not accrue |
| COW-3260 | Backlog | — | [CBFS][Security] Bound pre-auth QUIC memory and slow-read exposure |
| COW-3263 | Backlog | — | [CBFS] Make root placement discoverability part of commit atomicity |
| COW-3264 | Backlog | — | [CBFS] Fence FUSE writers or rebase root conflicts without a permanent wedge |
| COW-3265 | Backlog | — | [CBFS] Store plaintext and ciphertext lengths separately |
| COW-3266 | Backlog | — | [CBFS] Replace full-payload repair probes with a bounded incremental scrub |
| COW-3267 | Backlog | — | [CBFS] Chunk and stream object writes so the advertised max size is representable |
| COW-3268 | Backlog | — | [CBFS] Reconcile pruned volume-event gaps before GC |
| COW-3269 | Backlog | — | [CBFS] Reserve capacity atomically and enforce cumulative capability quotas |
| COW-3270 | Backlog | — | [CBFS] Make path_prefix an enforceable relay authorization boundary |
| COW-3271 | Backlog | — | [CBFS] Supervise safety loops and derive readiness from real state |
| COW-3274 | Backlog | — | [CBFS] Add write deadlines, alternate placement, and an explicit durability quorum |
| COW-3275 | Backlog | — | [CBFS/CBSS][Security] Authenticate release-key and relayer discovery against finalized state |
| COW-3276 | Backlog | — | [CBFS][Security] Channel-bind relay identity and persist transport trust |
| COW-3277 | Backlog | — | [CBFS] Add placement tombstones and bounded lifecycle indexes |
| COW-927 | Backlog | pav | [Node] POST /ras/challenge endpoint + chain-state challenge records |

## CIP-39: Cowboy Queue System (CBQS) — 17 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-3293 | In Review | pav | [CBQS] Fail readiness when durable storage or Fast flushing is unhealthy |
| COW-3294 | In Review | pav | [CBQS][Security] Bound and expire pending session and challenge state |
| COW-3298 | In Review | pav | [CBQS][Security] Bound WebSocket ingress, handshakes, idle time, and concurrency |
| COW-3301 | In Review | pav | [CBQS] Run fault-injection crash coverage in CI |
| COW-3302 | In Review | pav | [CBQS] Make the load harness fail closed and add capacity SLO gates |
| COW-3303 | In Review | pav | [CBQS Client][Security] Parse loopback broker URLs structurally |
| COW-3304 | In Review | pav | [CBQS] Reconcile packaging and public docs with the supported surface |
| COW-3288 | Backlog | — | [CBQS] Include every durable lane when planning Standard retention |
| COW-3289 | Backlog | — | [CBQS] Enforce retained_bytes_limit with atomic storage accounting |
| COW-3290 | Backlog | — | [CBQS] Drive retention and group maintenance from a durable broker-wide catalog |
| COW-3291 | Backlog | — | [CBQS] Page group replay to a frozen tail before switching live |
| COW-3292 | Backlog | — | [CBQS] Move RocksDB and fsync work to a bounded storage executor |
| COW-3295 | Backlog | — | [CBQS][Security] Make client payload encryption safe by default |
| COW-3296 | Backlog | — | [CBQS Client] Add reconnect, request deadlines, and subscription restoration |
| COW-3297 | Backlog | — | [CBQS Client] Add a complete typed Standard consumer API |
| COW-3299 | Backlog | — | [CBQS] Define machine-loss durability and implement broker fencing and failover |
| COW-3300 | Backlog | — | [CBQS] Ship store migration, checkpoint, restore, and rollback tooling |

## CIP-25: Cross-Chain Architecture — 6 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1122 | Todo | — | [Runner] Runner job type `generate_inclusion_proof` (third-party proof service) |
| COW-1896 | Todo | pav | §1.4/§1.5/§A.5 ZK light-client backend |
| COW-1897 | Todo | pav | §1.4/§A.5 Optimistic backend with challenger bonds/incentives |
| COW-1901 | Todo | pav | §2.5/§2.6 Cross-chain streaming |
| COW-1899 | Backlog | pav | §1.6 Multi-destination cost reduction |
| COW-1900 | Backlog | — | §1.3 state_root / parent_hash commitment fields |

## Money & Payments — 12 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| DES-49 | Todo | — | Add-funds flow: Stripe/Apple Pay → USD balance |
| DES-50 | Todo | — | USD-first money display system |
| DES-53 | Todo | — | Gold tab in dashboard |
| DES-143 | Backlog | — | Gold: plan catalog & plan card |
| DES-144 | Backlog | — | Gold: pool meter, sources & Add funds |
| DES-145 | Backlog | — | Gold: usage breakdown & benefits |
| DES-146 | Backlog | — | Gold: lifecycle — renewal, grace, restriction |
| DES-147 | Backlog | — | Gold: join, activation & plan changes |
| DES-148 | Backlog | — | Gold: cross-surface entitlement (Mac / CLI / iOS) |
| DES-149 | Backlog | — | Overview: Gold module |
| DES-158 | Backlog | — | Gold & Free: spending permission (Set spending) |
| DES-54 | Backlog | — | Wallet menu redesign: USD-first |

## Whitepaper — Python Actor VM (PVM) — 6 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1240 | In Progress | pav | [PVM] Graceful stack-overflow handling (remove RUST_MIN_STACK workaround) |
| COW-137 | Todo | — | [PvmHost] Add storage batch read optimization |
| COW-1239 | Backlog | pav | [PVM] Enforce per-call heap cap (10 MiB); currently MAX_MEMORY_SIZE = isize::MAX |
| COW-1241 | Backlog | pav | [PVM] Explicit GC disable + cycle-detection rejection |
| COW-1243 | Backlog | pav | [PVM] Cross-platform determinism CI test (Linux x86 vs macOS ARM) |
| COW-2056 | Backlog | — | Standardized C-ABI cross-VM call wrapper for PVM<->future-EVM (WP Storage |

## Follower Node Mode — RPC/Consensus Decoupling — 6 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2723 | In Progress | — | Canonical genesis fingerprint via commonware-codec (fix COW-2711 reformat-brick without reintroducing upgrade-instability) |
| COW-2718 | Backlog | — | Divergence recovery — fail-stop + durable marker + quarantine + circuit-breaker→FAILED |
| COW-2719 | Backlog | — | Consumer cutover to followers — dashboard/gateway/cbfs (deferred, after read-parity) |
| COW-2722 | Backlog | — | COW-2711 follow-up: chain-identity marker robustness (state colocation, re-template brick, migration TOFU, dead None branch) |
| COW-2736 | Backlog | — | Follower Node Mode — Terraform: follower EC2 instances + Secrets Manager grants (enablement gate) |
| COW-2737 | Backlog | — | Canyon-reset §8 guard: tolerate an unreachable validator only when no follower row is in play (incident ergonomics) |

## CIP-33: Actor Hiring & Distribution — 4 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2669 | In Review | — | Twilio conversation locks must reclaim abandoned async workflows |
| COW-3096 | Backlog | — | Blueprint validator drift: TS (store-admin) accepts paths the Rust harness cache rejects |
| COW-3097 | Backlog | — | Live Store resolver: recompute CBFS manifest root + carry signed attest txs in cache |
| COW-3098 | Backlog | — | Tighten blueprint route-path validation charset |

## CIP-2: Verifiable Off-Chain Compute — 3 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-962 | Todo | pav | [Node] Dispute window: on-chain challenge / evidence / re-verification handler |
| COW-1377 | Backlog | pav | §8 'Aggregator collects result_bytes via direct HTTP push' + |
| COW-2109 | Backlog | — | Activate 50/30/20 slash split + wire challenger payout + fix the split-value inconsistency |

## CIP-31: CBFS Rent Schedule — 3 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2896 | In Review | pav | CBFS registry-proto bills from the compile-time fee const, not the governance param |
| COW-2914 | Backlog | — | Rename fee_split.burn_bps -> treasury_bps (and cbqs.rent.burn_bps) |
| COW-2915 | Backlog | — | Platform Fee Account (0x18): generate the multisig owner key before genesis |

## CIP-5: Native Timer Mechanism — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1274 | Todo | pav | Architectural: decouple timer execution from propose's critical path |

## Canyon / Mesa Bug Triage — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2664 | Todo | — | Guard runner fleet restart/resume with nonce reconciliation canaries |

## CIP-22: Continuous Clearing Auctions [Blocked on CIP-21] — 35 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1191 | Backlog | — | [Node/Examples] ContinuousClearingAuction actor skeleton + clear_block algorithm |
| COW-1192 | Backlog | — | [Examples] Bid submission + escrow: place_bid / withdraw_bid / increase_bid / update_max_price |
| COW-1193 | Backlog | — | [Examples] Per-block clearing logic: SortedMap by max_price + pro-rata fill |
| COW-1194 | Backlog | — | [Examples] Release schedule parsing: ReleaseStep iteration by block-height offset |
| COW-1195 | Backlog | — | [Examples] CIP-21 pool graduation: factory.get_or_create_v2\|v3_pool() + mint_position() |
| COW-1196 | Backlog | — | [Examples] Anti-manipulation: TWAP checkpoints, flash-loan guards, bid duration locks, MEV-guard for timer |
| COW-1197 | Backlog | — | [Examples] FAILED path: min_currency_raised threshold + claim() refund logic |
| COW-1198 | Backlog | — | [Examples] ICCAHook integration: validation hooks at place_bid / withdraw_bid / claim |
| COW-1200 | Backlog | — | [Examples] Reference auction example actor at examples/<NN>-cca/ |
| COW-1201 | Backlog | — | [Tests] Clearing math edge cases (pro-rata rounding, tie-break, partial fill, max u256) |
| COW-1806 | Backlog | — | AuctionConfig data structure (token_id |
| COW-1807 | Backlog | — | ReleaseStep data structure (rate_mps u24 |
| COW-1808 | Backlog | — | PoolType enum (V2_FULL_RANGE / V3_CONCENTRATED) |
| COW-1809 | Backlog | — | Bid data structure (bid_id |
| COW-1810 | Backlog | — | AuctionState data structure (current_block |
| COW-1811 | Backlog | — | Checkpoint data structure (block |
| COW-1812 | Backlog | — | AuctionStatus enum (PENDING/ACTIVE/ENDED/GRADUATED/FAILED) |
| COW-1813 | Backlog | — | ICCA.claim(bid_id)->(tokens |
| COW-1814 | Backlog | — | ICCA.claim_batch(bid_ids) |
| COW-1815 | Backlog | — | Query methods |
| COW-1816 | Backlog | — | _remaining_demand(bid |
| COW-1817 | Backlog | — | Checkpoint append per block for pro-rata claim accounting |
| COW-1819 | Backlog | — | Timer integration |
| COW-1821 | Backlog | — | ICCAFactory.create_auction(...)->address with end>start |
| COW-1822 | Backlog | — | ICCAFactory.create_auction_with_token(name |
| COW-1824 | Backlog | — | Event AuctionCreated |
| COW-1825 | Backlog | — | Event AuctionStarted |
| COW-1826 | Backlog | — | Event AuctionEnded |
| COW-1827 | Backlog | — | Event AuctionGraduated(final_price |
| COW-1828 | Backlog | — | Event AuctionFailed(currency_raised |
| COW-1829 | Backlog | — | Event BidPlaced |
| COW-1830 | Backlog | — | Event BidWithdrawn |
| COW-1831 | Backlog | — | Event BidIncreased |
| COW-1832 | Backlog | — | Event BidPriceUpdated |
| COW-1833 | Backlog | — | Event TokensClaimed(tokens |

## CIP-21: DEX & Liquidity Pools — 15 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1086 | Backlog | pav | [Node/Examples] V3 concentrated-liquidity pool: ticks, positions, fee accumulators |
| COW-1087 | Backlog | — | [Node/Examples] Pool factory + registry (create_v2_pool, create_v3_pool, get_pool by (tokenA, tokenB, fee)) |
| COW-1088 | Backlog | pav | [Node/Examples] Swap routers: actor-router (flexible) + platform-router (amm_swap_exact_in/_out) |
| COW-1089 | Backlog | — | [Node/Examples] Validation hooks: can_swap, on_swap, can_add_liquidity, can_remove_liquidity |
| COW-1090 | Backlog | — | [Node/Examples] Native TWAP oracle via timer-driven price-cumulative tracking |
| COW-1091 | Backlog | pav | [Node/Examples] V3 position manager: positions as transferable NFTs |
| COW-1092 | Backlog | — | [Node/Examples] CIP-22 auction → CIP-21 pool graduation |
| COW-1093 | Backlog | — | [Node/Examples] Fee handling: protocol fee vault + DAO treasury distribution |
| COW-1096 | Backlog | pav | [Tests] Multi-hop routing + factory + hooks + TWAP integration tests |
| COW-1799 | Backlog | pav | IV2Pool extras |
| COW-1800 | Backlog | pav | Canonical token sorting in init (token_a>token_b swap) - spec ref impl |
| COW-1801 | Backlog | pav | On-chain limit orders via state-triggered timers (6.2 LimitOrderBook) |
| COW-1802 | Backlog | pav | MEV-protection hook (6.3) and KYC/compliance hook (6.4) - absent (no hook |
| COW-1803 | Backlog | pav | Sync event (events section) - example emits liquidity/swap events but no |
| COW-1805 | Backlog | pav | Reference platform impl cowboy-core/src/runtime/amm.rs (spec §Reference |

## Dashboard Agentic harness — 14 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2475 | Backlog | — | [Verify] Tool access — every tool works & is exposed correctly |
| COW-2476 | Backlog | — | [Verify] Control loop — plan → act → observe → retry, and stop conditions |
| COW-2477 | Backlog | — | [Verify] Memory / context — memory, session_search, skills, workspace, codegen corpus |
| COW-2478 | Backlog | — | [Verify] Safety bounds — signature gates, deny, sandbox, secrets-out-of-LLM |
| COW-2480 | Backlog | — | [Verify] Observability — trace, artifacts, and the persistence gap |
| COW-2481 | Backlog | — | [Verify] Orchestration — delegate_task + model-role routing |
| COW-2559 | Backlog | — | [Build] Tier 1.2 — Run-journal analytics: per-run metrics + weekly weakness clustering |
| COW-2561 | Backlog | — | [Build] Tier 2.1 — Actor discovery + lifecycle tools (list_my_actors, get_actor_source, estimate_cost, wait_for_tx, transfer_cby) |
| COW-2562 | Backlog | — | [Verify/Build] Tier 2.2 — set_routes signed end-to-end on canyon + corpus follow-ups |
| COW-2563 | Backlog | — | [Build] Tier 2.3 — Parallel delegate_task children (lower priority) |
| COW-2570 | Backlog | — | [Future] Tier 4 pilot — measure the improvement-loop proposer's gate pass rate |
| COW-2571 | Backlog | — | [Future] Tier 4.1 — Prompt evolution on the existing improvement rails |
| COW-2572 | Backlog | — | [Future] Tier 4.2 — Config search over loop parameters |
| COW-2573 | Backlog | — | [Blocked] B.1 — CBFS-canonical-store cleanup (blocked on node #643 CBFS volume GC bug) |

## Whitepaper — Consensus, P2P & Randomness — 13 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1202 | Backlog | — | [Node] VRF-based transaction ordering inside a block (WP §6.5) |
| COW-1203 | Backlog | — | [Node] Validator set lifecycle: register / activate / exit / withdraw + epoch snapshot |
| COW-1206 | Backlog | — | [Node] Validator equivocation detection + slashing aggregation (Cowboy-side) |
| COW-1207 | Backlog | — | [Node] Cowboy-level integration tests for consensus invariants (finality, view change, validator-set transition) |
| COW-1210 | Backlog | — | [Node] P2P peer scoring + anti-spam at gossip layer |
| COW-1962 | Backlog | — | Proposer selection is VRF-based but NOT stake-weighted |
| COW-1963 | Backlog | — | Per-header VRF output+proof field is not on the block header. WP §6.1 |
| COW-1964 | Backlog | — | Mempool selection diverges from WP §6.4 |
| COW-1965 | Backlog | — | Dedicated-lane BLOCK-SPACE partitioning + cascade is not implemented at |
| COW-1966 | Backlog | — | QUIC over TLS 1.3 is NOT the transport. WP §6.2 'Implementations MUST |
| COW-1967 | Backlog | — | Peer discovery is bit-vector gossip |
| COW-1969 | Backlog | — | Epoch boundaries (3600 blocks) with per-epoch validator-set / slashing / |
| COW-613 | Backlog | pav | [L7] Deterministic genesis leader key enables chain replay |

## Builder — 9 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2208 | Backlog | — | add advanced mode |
| COW-2209 | Backlog | — | add ability to see your files on CBFS and edit them (like edit the prompt on the chatbot) |
| COW-2210 | Backlog | — | add "next up" helpers - |
| COW-2212 | Backlog | — | add CBSS support |
| COW-2213 | Backlog | — | add support for Telegram, and SMS. These should probably be actors that you just hire |
| COW-2214 | Backlog | — | Agent cannot modify templated chatbot actor on 8k runner because write_actor exceeds prompt budget |
| COW-2215 | Backlog | — | Agent misroutes “don’t simulate” correction into simulate_actor because of brittle regex intent detection |
| COW-2216 | Backlog | — | Agent loops on cowboy_knowledge and stops after 3 calls instead of using results to revise actor |
| COW-2257 | Backlog | — | add image models |

## Lasso Agentic harness — 9 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2462 | Backlog | — | 08 · [Exec] Sandboxed local_exec for build/test scripts (approval-gated) |
| COW-2468 | Backlog | — | 14 · [Sync] sync status + conflict handling |
| COW-2470 | Backlog | — | 16 · [Secrets] Wire request_secret → local prompt + store |
| COW-2471 | Backlog | — | 17 · [UX] Approval prompt UI + artifact cards + rendering polish |
| COW-2473 | Backlog | — | 19 · [Protocol] Shared protocol/types package across backend/frontend/lasso |
| COW-2474 | Backlog | — | 20 · [Tests] Renderer snapshot + bridge/local-tool/sync tests |
| COW-2569 | Backlog | — | [Future] Tier 3.2 — Lasso runs the shared agent core (real loop, not regex extraction) |
| COW-2634 | Backlog | — | [Safety] TOCTOU-safe local writes — atomic no-follow write within the sandbox |
| COW-2684 | Backlog | — | [Local FS] Safe regex mode for local_search (linear engine / worker) |

## CIP-10: Runner Container Runtime — 7 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1575 | Backlog | — | §12.2 image-pull egress fees (pull_cost = size * EGRESS_FEE_PER_BYTE |
| COW-1578 | Backlog | — | §13 parameter set (MAX_CPU_MILLICORES |
| COW-1582 | Backlog | — | §14.6 GPU side-channel mitigations (NVIDIA MIG isolation |
| COW-2506 | Backlog | — | CIP-10: GPU billing + scheduling |
| COW-2507 | Backlog | — | CIP-10: networked containers + egress accounting/billing |
| COW-2617 | Backlog | — | infra: cowboy-runner ExecStartPre truncates runner.env, dropping operator RUNNER_CONTAINER_* vars |
| COW-2618 | Backlog | — | infra: enforced-cgroup containers on canyon need dbus-user-session for the cowboy service user |

## Mainnet / TGE (November) — 6 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| DES-74 | Backlog | — | Earn / Stake / Govern tab |
| DES-75 | Backlog | — | Native mode: CBY toggle |
| DES-76 | Backlog | — | Runner registration & operator dashboard |
| DES-87 | Backlog | — | Faucet & indexer entry points |
| DES-88 | Backlog | — | Tokens tab in dashboard |
| DES-89 | Backlog | — | Mailbox tab in dashboard |

## CIP-20: Fungible Token Standard — 5 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1073 | Backlog | pav | [Spec] Bridge / lock-and-mint CIP for ETH ↔ Cowboy L1 (blocking $COWBOY Aug 2026 launch) |
| COW-1082 | Backlog | pav | [Explorer] Token balance + transfer history UI |
| COW-1798 | Backlog | — | ICIP20Actor actor-token interface / actor-based tokens (fee-on-transfer |
| COW-2826 | Backlog | pav | [Node/Spec] CIP-20 on-chain allowance/spender secondary index (re-scope of COW-1083) |
| COW-3089 | Backlog | pav | CIP-20 holder enumeration — index or preimage-scan (blocked by COW-3090) |

## CIP-30: Per-Actor Storage Root — 5 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1277 | Backlog | pav | [Node] state_set / state_delete recompute storage_root in cross-call write-set |
| COW-1280 | Backlog | — | [Node] Gas formula for trie updates: deterministic, bounded cost per state_set / state_delete |
| COW-1281 | Backlog | — | [Node] fork() O(1) clone: child.storage_root = parent.storage_root (replaces enumeration stopgap) |
| COW-1282 | Backlog | — | [Node/RPC] Expose per-actor proof endpoint: `GET Actor.storage_root` + opens against subtree |
| COW-1285 | Backlog | — | [Tooling] Pre-image table for hashed long keys (debugger / explorer enumeration) |

## CIP-24: Cowboy Secret Service (CBSS) — 4 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1051 | Backlog | — | [CBSS] TEE vendor-quote chain-of-trust (DOD-07-TEE v1.1) |
| COW-2283 | Backlog | — | canyon-reset Ansible: one-command wipe + rebuild at pinned versions |
| COW-2671 | Backlog | — | Add authenticated evidence for CBSS threshold-wide withholding |
| COW-3092 | Backlog | — | Add atomic GrantSecretActor instruction to CBSS |

## CIP-28: Cowboy Agent Banking — 4 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1139 | Backlog | — | [Node] Emit nine event types (CardIssued, CardDeposited, CardWithdrawn, GasCharged, Frozen, Unfrozen, PolicyUpdated, OwnershipTransferred, BankRegistered) (§3.6) |
| COW-1902 | Backlog | — | §1.3 New tx-level field tx.fee_payer_override |
| COW-1904 | Backlog | — | §2.7/§4.1 fee_payer resolution fork (card-address lookup → |
| COW-1911 | Backlog | — | §4.5 BankErr error family + engine ErrorMap (CardNotFound |

## CIP-29: On-Chain Event Hooks — 4 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1147 | Backlog | — | [Node] Receipt schema: triggered_by_emit field for async causality correlation |
| COW-1152 | Backlog | — | [Node/SDK] Payload schema validation at emit + subscribe time |
| COW-1917 | Backlog | pav | §2.1/§2.4 EmitResult return value NOT surfaced |
| COW-2884 | Backlog | — | [Node] CIP-29 §2.3 gas isolation not enforced for cells in async event-fire (emitter pays subscriber cells) |

## CIP-40: EIP-712 Signing & WalletConnect — 4 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-3085 | Backlog | — | Flag-day chain-id cutover: retire chain_id=1, assign canyon 26901 / mesa 26909 |
| COW-3086 | Backlog | — | Ethereum facade: POST /eth JSON-RPC stub on node RPC |
| COW-3087 | Backlog | — | Registry PRs to ethereum-lists/chains (mesa 26909, prairie 26900, mainnet 2690) |
| COW-3088 | Backlog | — | Prairie: public testnet bring-up |

## Trail of Bits Audit — 4 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2438 | Backlog | — | 📎 Trail of Bits — Week 1: full report (PDF) |
| COW-2638 | Backlog | pav | [ToB High] TOB-COWBOY-22: TEE-required runner eligibility can rely on self-asserted attestation |
| COW-2647 | Backlog | — | 📎 Trail of Bits — Week 2: full report (PDF) |
| COW-2648 | Backlog | — | 📎 Trail of Bits — Week 3: full report (PDF) |

## Whitepaper — Economics, Entitlements & Genesis — 4 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1259 | Backlog | — | [Node] Validator reward minting: per-block inflation for the 180M CBY validator pool |
| COW-1261 | Backlog | — | [Node] Treasury (0x08) state model: TreasuryState struct + inbound-flow accounting + governance withdrawal |
| COW-2019 | Backlog | — | §8.3 Vesting schedules absent |
| COW-2020 | Backlog | pav | §8.4 Slashed stake -> 100% burned |

## CIP-16: Custom Domains & First-Party TLDs — 3 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1720 | Backlog | — | §10/§7 Gateway resolution & serving policy (ACTIVE-only |
| COW-1721 | Backlog | — | §7.3 verified_fqdn + namespace_kind injection into HttpRequestEnvelope by |
| COW-1722 | Backlog | — | §10.3/§7.4 first-party TLD DNS authority serving from Route Registry |

## CIP-19: Gateway MCP Ingress — 3 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1761 | Backlog | — | §7 `ingress.mcp` entitlement id with params (server_name |
| COW-1774 | Backlog | — | §10.3 Input schema derivation from path params + OpenAPI doc |
| COW-1788 | Backlog | — | §14.3 Per-actor tool-list cache keyed by (actor |

## CIP-8: MPP Session Semantics — 3 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1012 | Backlog | — | [Node/Runner] Pin production COWBOY_SESSION_CHAIN_ID |
| COW-1542 | Backlog | — | §6.4/§16 SessionAsset::Cip20 token-escrow path |
| COW-1543 | Backlog | pav | §4/§5 Runner session bootstrap relies on a PoC /session/observe HTTP push |

## Whitepaper — Data Availability, Blobs & Storage — 3 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1258 | Backlog | — | [Tests] Integration tests for blob lifecycle (inline cap, CBFS anchoring, volume eviction) |
| COW-2009 | Backlog | — | CBFS §6.3 RELAY_UNSTAKE_DELAY=7,200-block cooldown after full drain |
| COW-2010 | Backlog | — | CBFS §8.1 fee components VOLUME_CREATION_FEE=1,000 CBY |

## Whitepaper — State Transition Function, System Actors & Precompiles — 3 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1233 | Backlog | — | [Node] Cross-system-actor reentrancy + call-graph audit |
| COW-2085 | Backlog | — | §3.1 /tmp scratch space per-invocation cap at 256 KiB |
| COW-2090 | Backlog | — | §3.3 Exactly-once-after-finality vs at-least-once-before-finality delivery |

## CIP-23: TEE Execution & Composite Attestation — 2 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1103 | Backlog | pav | [Node] Attestation-first runner registration (registry → 0x05::VerifyCae cross-call) |
| COW-1111 | Backlog | — | [Node/Runner] NVIDIA NCC GPU attestation (NRAS token + verification) |

## CIP-6: In-PVM Actor SDK (cowboy_sdk) — 2 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2824 | Backlog | pav | [SDK] Guard verification is inert for every compiled FSM actor — guard_keys never reaches save_cont |
| COW-987 | Backlog | — | [SDK] Actor-side runtime.mount(volume_id, access_mode) for CBFS workflows |

## CIP-11: Runner Connectivity & Push Job Delivery — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2661 | Backlog | — | [Canyon] Enable model-aware runner selection and split provider credentials |

## CIP-18: Payments — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1184 | Backlog | — | [Node/Runner] EVM bridge facilitator: bridge.facilitate.evm entitlement + BridgeEvidence + credit_inbound |

## CIP-26: Account-Scoped Actor Libraries — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1365 | Backlog | — | §3.9 future-GC reachability guard (GC must check union of live |

## Deploy Process & Runbooks — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-3194 | Backlog | — | outpost river tooling gaps surfaced in Slice-2 zygote validation (cbss dual chain_id, cbqs support, zygote wiring) |

## Explorer Design & Navigation — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-3019 | Backlog | — | make explorer chat based |

## Google Login — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2439 | Backlog | — | Pepper rotation / wallet rewrap path for Google-backed wallets |

## Marketing Site v2 — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| DES-79 | Backlog | — | "Request for Agents" page |

## Node Simplification — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-2860 | Backlog | — | NODE — decide whether node still publishes the `cowboy-sdk` PyPI name (collides with python-sdk) |

## Onboarding — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| DES-62 | Backlog | — | Bring-your-own-memory import flow |

## Whitepaper — Accounts, Transactions & Mempool — 1 条

| Issue | 状态 | 归属 | 标题 |
|---|---|---|---|
| COW-1934 | Backlog | — | §1.2 python_source canonicalization (UTF-8 |
