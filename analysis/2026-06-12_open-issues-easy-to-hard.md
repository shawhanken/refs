# 未解决 Issue 全列表 — 由易到难(2026-06-13 二次更新,Linear 实时数据)

**范围:** Linear COW 团队,state ∉ {completed, canceled},assignee ∈ {pavilionledger(PL), 未指派(—)} — 共 **644 条**(570 Backlog / 68 Todo / 5 In Progress / 1 In Review;PL 120 / 未指派 524)。

**排序依据:** 6 档分级,继承上一版各 issue 档位;本次刷新状态、扣除已闭环、并把 COW-938 由 Tier-1 重分到 Tier-4(其「14 参数搬治理」实为共识级改动,非 Tier-1)。⚠ = In Progress/In Review。

**自上一版(658 条)闭环 16 条**:COW-697, COW-970, COW-986, COW-1081, COW-1155, COW-1211, COW-1237, COW-1247, COW-1250, COW-1251, COW-1253, COW-1257, COW-1271, COW-1303, COW-2095, COW-2118。

**新增 2 条**:COW-2265, COW-2266。

**本会话 Tier-1 清理成果(2026-06-12→13)**:
- 已合并:COW-1237/1247/1257/1271(#169)、1155/1251/1211(#170)、1250(#171)
- 核验关单:COW-1303(1s 出块一致)、COW-1081(token host-call 已全包装)
- 留开有因:COW-970(计划已交付,留 BasefeeConfig 代码)、COW-986(CIP-5↔CIP-9 fee_payer 矛盾待 owner 决策)、COW-938(重分 Tier-4)

**Tier-1 剩余基本是硬骨头**:COW-1064(cbss 小工具,需编译);内容写作 10 条(143 部署指南 / 474·475 runbook / 413 注释样例 / 422 架构深挖 / 411 SDK 参考 / 397·499·500·501 AI-context);绿地或阻塞 4 条(1097·1084 CIP-21 未建成 / 1144 Big Sky 平台不在盘 / 1133 CIP-26 带 CLI 功能)。

---

## Tier 1 — 最易 — 纯文档 / 决策记录 / 验证型一行修(每条数小时)(15 条)

| Issue | Title | Project | State | Asg |
|---|---|---|---|---|
| COW-1097 | [Docs] CIP-21 implementation roadmap + ETAs in cip21_reference.py | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1084 | [Docs] CIP-20 ↔ CIP-21 interaction worked examples | CIP-20: Fungible Token Standard | Backlog | — |
| COW-1133 | [Docs] Manifest interaction: tooling guidance for displaying expected pins | CIP-26: Account-Scoped Actor Libraries | Backlog | — |
| COW-1144 | [Decision] MOOLA ↔ BankActor semantics: can a card pay gas in MOOLA? | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-397 | AI Context: SKILL.md for Claude / Cowork | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-500 | .cursorrules in cowboy init output | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-501 | llms.txt at docs domain root | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-499 | Skills for Claude/Codex/OpenClaw | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-413 | Docs: annotated full examples | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-422 | Docs: architecture deep-dives (from whitepaper) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-143 | [Docs] Implement deployment guide | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-474 | Snapshots + restore runbook | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-475 | Incident runbook (degraded mode / halt / restart) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-411 | Docs: auto-generated SDK reference | Node Hardening, Tooling & Supporting Wor | Backlog | PL |
| COW-1064 | [CBSS] DOD-01 aggregate cargo log | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |

## Tier 2 — 小型有界代码修复(每条 ≤1 天)(14 条)

| Issue | Title | Project | State | Asg |
|---|---|---|---|---|
| COW-758 | [mesa-bot] System actor code readable via /actor/{addr}/code endpoint | WP—State Transition Function, System Act | Backlog | — |
| COW-940 | [Docs] Resolve CBFS Phase 2 open questions: PoD frequency, scoring weights, clock skew bound | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-1712 | execute_dns_job NOT production-wired into runner worker loop | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1131 | [PVM] Dynamic imports inside handler body: explicit error rather than silent unresolvable | CIP-26: Account-Scoped Actor Libraries | Backlog | — |
| COW-989 | [SDK] Entitlement subset comparison operator | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | — |
| COW-990 | [SDK] Reentrancy guard: optional per-call key arg to avoid factory-pattern collisions | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | — |
| COW-1506 | §11.5 canonical-ordering residual (minor/partial) | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | PL |
| COW-1507 | §14.3 token.* entitlement IDs (token.create/transfer/mint/burn) are NOT | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | — |
| COW-767 | [mesa-bot] CLI accepts token operations with nonexistent token IDs without validation | CIP-20: Fungible Token Standard | Backlog | PL |
| COW-1080 | [CI] Integrate examples/01-tokens/demo.sh into CI test suite | CIP-20: Fungible Token Standard | Backlog | PL |
| COW-1893 | §5.3 canonical error vocabulary | CIP-24: Cowboy Secret Service (CBSS) | Backlog | PL |
| COW-2258 | [Indexer/Wallet] Add big-endian decoders for the new on-chain receipt events (session / mani | — | Todo | PL |
| COW-2262 | cbss-crypto: zeroize the IBE encryption ephemeral r (blstrs Scalar has no Zeroize impl) | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |
| COW-2263 | node Coverage (cargo llvm-cov) job flakes on PVM interpreter init — red on live devnet | — | Backlog | — |

## Tier 3 — 中等 — 边界清晰的功能 / 测试 / 接线(每条数天)(86 条)

| Issue | Title | Project | State | Asg |
|---|---|---|---|---|
| COW-1310 | Example: 01-tokens | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1311 | Example: 02-liquidity-pools | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1312 | Example: 03-rebalancing-agent | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1315 | Example: 06-content-recommendations | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1316 | Example: 07-sentiment-analysis | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1317 | Example: 08-audio-transcription | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1318 | Example: 09-image-generation | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1319 | Example: 10-content-moderator | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1320 | Example: 11-alerts-and-schedulers | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1321 | Example: 12-liquidation-oracle | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1322 | Example: 13-dao-copilot | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1323 | Example: 14-compliance | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1324 | Example: 15-fraud-watcher | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1325 | Example: 16-contract-summarizer | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1326 | Example: 17-hn-feed | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1327 | Example: 18-ring-demo | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1328 | Example: 19-multi-actor-workflow | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1329 | Example: 19-texas-holdem | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1331 | Example: 21-pure-timer-scheduler | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1332 | Example: 22-actor-escrow-workflow | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1333 | Example: 23-read-through-oracle-cache | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1334 | Example: 24-failure-recovery | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1335 | Example: 25-auth-roles | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1339 | Example: 29-casino-rounds | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1340 | Example: 30-blackjack | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1341 | Example: 32-cowbot | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1342 | Example: erlangcowboydemo | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1344 | Project: Maintain Docker example harness | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-1347 | Project: Keep CLI/read semantics compatible with examples | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-920 | [CBFS] Add GetManifest Relay RPC (AMEND 9-G) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2120 | [CBFS/Node] GET_MANIFEST relay RPC (public assembly + cache) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-914 | Volume commit events silently lost when using cbfs put-many | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-925 | [CBFS] Ship `cbfs auth setup/rotate/revoke/status/whoami` CLI commands | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-926 | [CBFS] Signed request envelope on all /ras/ control-plane endpoints | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-928 | [CBFS] OwnerCapTokenV1 client-signed validation path on relays | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | PL |
| COW-931 | [CBFS] CLI connection pooling within process | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-932 | [CBFS] Volume metadata + OwnerCapToken caching | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-933 | [CBFS] Multi-source relay registry refresh + background fetch | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-934 | [CBFS] Convert 34 production panic!/unimplemented!/todo! to typed errors | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | PL |
| COW-936 | [CBFS] Add tests for packages currently with zero coverage | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | PL |
| COW-937 | [Runner] Add CIP-9 integration tests (manifest round-trip, access modes, cache stress) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2186 | Observability: Prometheus metrics for Gateway + RAS | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-987 | [SDK] Actor-side runtime.mount(volume_id, access_mode) for CBFS workflows | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | — |
| COW-1050 | [CBSS] Restore lost §5.9 spawned DKG e2e suite (DOD-04 v1.1) | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |
| COW-1052 | [CBSS] Real-validator stress test (DOD-08 v1.1) | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |
| COW-1054 | [CBSS] Real-validator scenario matrix (DOD-05/07 v1.1) | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |
| COW-1057 | [CBSS] DKG sabotage evidence remains provable post-rotate | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |
| COW-1894 | §4.4 health-score automation | CIP-24: Cowboy Secret Service (CBSS) | Backlog | PL |
| COW-1895 | §3.6.2 automatic reshare triggers | CIP-24: Cowboy Secret Service (CBSS) | Backlog | PL |
| COW-1011 | [Runner] Extend session integration tests to full E2E flow | CIP-8: MPP Session Semantics | Backlog | PL |
| COW-1542 | §6.4/§16 SessionAsset::Cip20 token-escrow path | CIP-8: MPP Session Semantics | Backlog | — |
| COW-1543 | §4/§5 Runner session bootstrap relies on a PoC /session/observe HTTP push | CIP-8: MPP Session Semantics | Backlog | — |
| COW-1308 | [Examples] CIP-2 v3 end-to-end economic e2e example and case study | CIP-2: Verifiable Off-Chain Compute | Todo | PL |
| COW-1212 | [Node] VERIFY: chain_id in transaction signing payload (cross-fork replay risk) | WP—Accounts, Transactions & Mempool | Backlog | — |
| COW-1219 | [Node] Mempool: per-peer rate limit + sustained-load eviction tests | WP—Accounts, Transactions & Mempool | Backlog | — |
| COW-1226 | [Node] Register unallocated system actors: 0x0D-0x12 (Route Registry, Gateway Registry, Rece | WP—State Transition Function, System Act | Backlog | — |
| COW-1230 | [Node] Epoch boundary processing order: define & test pre-tx vs post-tx ordering of rent/inf | WP—State Transition Function, System Act | Backlog | — |
| COW-1232 | [Node] Document precompile gas-cost table + verify against WP §3.5 examples | WP—State Transition Function, System Act | Backlog | — |
| COW-1234 | [Node] Genesis: ensure all system actors (0x01..0x0C + 0x1D + reserved 0x0D..0x12) have code | WP—State Transition Function, System Act | Backlog | — |
| COW-1243 | [PVM] Cross-platform determinism CI test (Linux x86 vs macOS ARM) | WP—Python Actor VM (PVM) | Backlog | PL |
| COW-1244 | [PVM] Activate determinism integration tests currently marked #[ignore] | WP—Python Actor VM (PVM) | Todo | PL |
| COW-1945 | Appendix A TV1 (unsigned) and TV2 (signed) test vectors (exact CBOR hex | WP—Accounts, Transactions & Mempool | Backlog | PL |
| COW-1305 | [Node] Align proof endpoint paths: /proof/* → /state/*, add block_hash field, handle absent  | CIP-17: Verifiable State Read RPC | Backlog | PL |
| COW-1754 | §5.2 happy-path handler integration tests (prove=true present key | CIP-17: Verifiable State Read RPC | Backlog | — |
| COW-2100 | [Node] Wire fast-sync into bootstrap + ≥10× bench (COW-977 follow-up) | CIP-4: State Storage & Persistence | Backlog | — |
| COW-2177 | [Node] Benchmark fast-sync bootstrap speedup vs genesis replay (>10x, COW-977 acceptance) | CIP-4: State Storage & Persistence | Backlog | PL |
| COW-1403 | §8.1 Fast sync (download QMDB state at height H | CIP-4: State Storage & Persistence | Backlog | PL |
| COW-1404 | §8.1/§11 Height-indexed QMDB snapshots + SNAPSHOT_INTERVAL (1024) | CIP-4: State Storage & Persistence | Backlog | — |
| COW-117 | [Gas] Add gas estimation API | CIP-3: Dual-Metered Fee Model | Todo | PL |
| COW-2089 | §3.3 dedup_window retention guarantee (entries retained ≥ | WP—State Transition Function, System Act | Backlog | — |
| COW-2235 | Centralize chain-event emission to hard-enforce consensus event-topic registration | — | Backlog | — |
| COW-363 | CLI: cowboy secrets manage encrypted secrets | Node Hardening, Tooling & Supporting Wor | Backlog | PL |
| COW-373 | Local dev: cowboy.yaml config format | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-376 | SDK: PVM-safe helpers (vrf, time, math) | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | PL |
| COW-378 | SDK: correlation ID and timeout handling helpers | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | — |
| COW-386 | Errors: four-part error format (what, why, fix, link) | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | PL |
| COW-988 | [SDK] @on_stream(stream_id) decorator + stream_publish() helpers (CIP-7) | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | — |
| COW-992 | [SDK] Mirror missing continuation features in standalone `cowboy` package | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | PL |
| COW-993 | [CI] E2E continuation tests on live PVM sandbox | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | PL |
| COW-1003 | [Node/SDK] Optional CIP-2 ingestion config: timer → task submission → transform → encrypt →  | CIP-7: Watchtower (Simple Stream Protoco | Backlog | — |
| COW-1153 | [SDK] @emit / @on_event decorators in cowboy_sdk | CIP-29: On-Chain Event Hooks | Backlog | PL |
| COW-1083 | [SDK] Allowance pagination + bulk-query for large holder lists | CIP-20: Fungible Token Standard | Backlog | — |
| COW-1074 | [Node] Permits / EIP-2612-equivalent gasless approval + increase_allowance / decrease_allowa | CIP-20: Fungible Token Standard | Backlog | — |
| COW-1076 | [Node] Multi-token aggregator / multicall for batch operations across token IDs | CIP-20: Fungible Token Standard | Backlog | — |
| COW-1029 | [Node] Foundation-separation enforcement: protocol prevents Foundation from being added to s | CIP-12: On-Chain Governance & System Act | Backlog | — |
| COW-1751 | §5.2 proof field-shape divergence | CIP-17: Verifiable State Read RPC | Backlog | — |

## Tier 4 — 较难 — 子系统级:状态机 / 经济 / 计量(每条 1–2 周;多处碰共识需协调上线)(89 条)

| Issue | Title | Project | State | Asg |
|---|---|---|---|---|
| COW-938 | [Node] Verify CIP-31 Tier-0 parameter wiring vs hardcoded Rust constants | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-924 | [Gateway] Direct RAS+QUIC reader replacing HTTP wrapper | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-929 | [Node] Relay registry: add relay_identity_pubkey + chain-verified handshake | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | PL |
| COW-930 | [CBFS] Cowboy-mode `cbfs mount` token-refresh design + implementation | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | PL |
| COW-2115 | [CBFS] Wire owner-auth signing to canonical encoding (registry-proto) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | PL |
| COW-2152 | [Node] Validate per_relay_effective_deltas at commit (caller-trust blast radius) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-1545 | §12.3 reserve_storage_balance / get_storage_usage AccountStorageSummary | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2009 | CBFS §6.3 RELAY_UNSTAKE_DELAY=7,200-block cooldown after full drain | WP—Data Availability, Blobs & Storage | Backlog | — |
| COW-2010 | CBFS §8.1 fee components VOLUME_CREATION_FEE=1,000 CBY | WP—Data Availability, Blobs & Storage | Backlog | — |
| COW-2184 | CBFS: full relay rewards distribution (pro-rata by shard count x age) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2205 | Harden cowboy-ras-write-relayer distribution: signing + verify-on-bootstrap + S3 immutabilit | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-1053 | [CBSS] Fake-cbssd binary serving forged σ_i over QUIC (DOD-09 v1.1) | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |
| COW-1546 | §9.2 (v2) Secrets-Manager direct sealed-DEK fetch path replacing | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-962 | [Node] Dispute window: on-chain challenge / evidence / re-verification handler | CIP-2: Verifiable Off-Chain Compute | Todo | PL |
| COW-2109 | Activate 50/30/20 slash split + wire challenger payout + fix the split-value inconsistency | CIP-2: Verifiable Off-Chain Compute | Backlog | — |
| COW-1148 | [Node] Refund mechanism: actually credit cycle refunds to subscriber accounts | CIP-29: On-Chain Event Hooks | Backlog | — |
| COW-1147 | [Node] Receipt schema: triggered_by_emit field for async causality correlation | CIP-29: On-Chain Event Hooks | Backlog | — |
| COW-1150 | [Node] Manifest entitlement gating for event subscription (prevent untrusted spam) | CIP-29: On-Chain Event Hooks | Backlog | — |
| COW-1152 | [Node/SDK] Payload schema validation at emit + subscribe time | CIP-29: On-Chain Event Hooks | Backlog | — |
| COW-1917 | §2.1/§2.4 EmitResult return value NOT surfaced | CIP-29: On-Chain Event Hooks | Backlog | PL |
| COW-1918 | §2.6 update_bid / topup_subscription NOT routed as 0x1D system-actor WRITE | CIP-29: On-Chain Event Hooks | Backlog | PL |
| COW-1919 | §2.5 payload billing is approximate | CIP-29: On-Chain Event Hooks | Backlog | PL |
| COW-1920 | §2.3 'commit subscriber writeset on sync-fire success' diverges from spec | CIP-29: On-Chain Event Hooks | Backlog | PL |
| COW-1921 | §2.5 ASYNC_FIRE_DEFERRAL_BLOCKS not explicitly applied as a configurable | CIP-29: On-Chain Event Hooks | Backlog | PL |
| COW-1922 | §2.3 zombie subscription bid/REGISTRATION_FEE handling on reap not | CIP-29: On-Chain Event Hooks | Backlog | PL |
| COW-1923 | §6.3 P1-E emitter actor upgrade / redeployment semantics for existing | CIP-29: On-Chain Event Hooks | Backlog | — |
| COW-1924 | §5.1 Phase-0 @hookable pure-SDK prototype not present as a distinct | CIP-29: On-Chain Event Hooks | Backlog | PL |
| COW-1457 | §5.1 step5 / Appendix-A 'enqueue into a deferred queue | CIP-5: Native Timer Mechanism | Backlog | PL |
| COW-1458 | §5.4 last paragraph 'If the fire-time self-destruct check has already | CIP-5: Native Timer Mechanism | Backlog | PL |
| COW-1460 | §5.1/§6.3 Spec frames pre-charge/execute/refund as a per-timer step5 over | CIP-5: Native Timer Mechanism | Backlog | PL |
| COW-1274 | Architectural: decouple timer execution from propose's critical path | CIP-5: Native Timer Mechanism | Todo | PL |
| COW-69 | [Timer] Implement block ring buffer for immediate timers | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-1306 | [Node] Charge PVM secp256k1 verify opcode at correct cycle cost per spec §2.3 | CIP-3: Dual-Metered Fee Model | Backlog | PL |
| COW-1307 | [Node] Meter return-data Cell consumption per spec §2.4 | CIP-3: Dual-Metered Fee Model | Backlog | PL |
| COW-963 | [Node] Complete per-bytecode instruction cost table (string/list concat dynamic surcharges) | CIP-3: Dual-Metered Fee Model | Todo | PL |
| COW-964 | [Node] Large-integer arithmetic surcharge: base_cost + max(bitlen(a), bitlen(b))/64 | CIP-3: Dual-Metered Fee Model | Todo | PL |
| COW-1397 | §2.2.4.2 Built-in function cost proportional to argument size (sum()/max() | CIP-3: Dual-Metered Fee Model | Backlog | — |
| COW-1398 | §2.2.4.10 String encoding determinism cost '10 + len(input) cycles' for | CIP-3: Dual-Metered Fee Model | Backlog | PL |
| COW-1399 | §2.2.4.8 Import penalty cycle costs not charged | CIP-3: Dual-Metered Fee Model | Backlog | — |
| COW-1400 | §2.2.4.6 Exception-handling cost metering (fixed cycles for raise / | CIP-3: Dual-Metered Fee Model | Backlog | — |
| COW-1401 | §2.2.4.4 Deterministic GC | CIP-3: Dual-Metered Fee Model | Backlog | PL |
| COW-1402 | §2.2.4.11 async/await deterministic FIFO scheduling + ban on | CIP-3: Dual-Metered Fee Model | Backlog | — |
| COW-1239 | [PVM] Enforce per-call heap cap (10 MiB); currently MAX_MEMORY_SIZE = isize::MAX | WP—Python Actor VM (PVM) | Backlog | PL |
| COW-1241 | [PVM] Explicit GC disable + cycle-detection rejection | WP—Python Actor VM (PVM) | Backlog | PL |
| COW-1249 | [PVM] Bytecode cache: instrumentation + persistence across handler calls | WP—Python Actor VM (PVM) | Backlog | PL |
| COW-2054 | set_interval(every_n_blocks | WP—Python Actor VM (PVM) | Backlog | — |
| COW-62 | [Continuation] Add checkpoint serialization format definition | WP—Python Actor VM (PVM) | Todo | PL |
| COW-94 | [Continuation] Implement FSM state machine validation | WP—Python Actor VM (PVM) | Todo | PL |
| COW-105 | [Continuation] Add resume state validation | WP—Python Actor VM (PVM) | Todo | PL |
| COW-119 | [PvmHost] Implement state snapshot optimization | WP—Python Actor VM (PVM) | Todo | PL |
| COW-137 | [PvmHost] Add storage batch read optimization | WP—Python Actor VM (PVM) | Todo | — |
| COW-175 | [PvmHost] Add storage size tracking | CIP-4: State Storage & Persistence | Todo | PL |
| COW-202 | [PvmHost] Add storage access logging | WP—Python Actor VM (PVM) | Todo | PL |
| COW-231 | [PvmHost] Add Host function call tracing | WP—Python Actor VM (PVM) | Todo | PL |
| COW-95 | [PvmHost] Implement storage quota enforcement | CIP-4: State Storage & Persistence | Todo | PL |
| COW-1254 | [Node] Two-tier blob pricing: inline (≤64 KiB cells-metered) vs CBFS (>64 KiB storage-rent) | WP—Data Availability, Blobs & Storage | Backlog | — |
| COW-1255 | [Node] Implement `host: blob commit (per KiB) = 40 cycles` metering | WP—Data Availability, Blobs & Storage | Backlog | — |
| COW-1256 | [Spec/Node] Align CIP-4 actor-state rent epoch and CIP-9 CBFS volume rent epoch (avoid orpha | WP—Data Availability, Blobs & Storage | Backlog | — |
| COW-1258 | [Tests] Integration tests for blob lifecycle (inline cap, CBFS anchoring, volume eviction) | WP—Data Availability, Blobs & Storage | Backlog | — |
| COW-1228 | [Node] Reconcile STORAGE_EPOCH_BLOCKS: code 7200 (1h) vs WP §13 rent_epoch_length 86400 (1d) | WP—State Transition Function, System Act | Backlog | — |
| COW-720 | [Audit LOW] L-22: Non-atomic commit across multiple databases | CIP-4: State Storage & Persistence | Todo | PL |
| COW-1406 | §7.3 Auxiliary-index full/incremental rebuild-from-ledger routine | CIP-4: State Storage & Persistence | Backlog | — |
| COW-1407 | §8.2 Batch-proof node deduplication across keys | CIP-4: State Storage & Persistence | Backlog | — |
| COW-979 | [Node] Historical state queries (proof-of-historical-state for light clients) | CIP-4: State Storage & Persistence | Todo | PL |
| COW-1405 | §5.4/CIP-17 Non-existence (exclusion) proofs for absent keys | CIP-4: State Storage & Persistence | Backlog | — |
| COW-1233 | [Node] Cross-system-actor reentrancy + call-graph audit | WP—State Transition Function, System Act | Backlog | — |
| COW-1236 | [Node] Cross-system-actor reentrancy/call-graph integration tests | WP—State Transition Function, System Act | Backlog | — |
| COW-2085 | §3.1 /tmp scratch space per-invocation cap at 256 KiB | WP—State Transition Function, System Act | Backlog | — |
| COW-2088 | §3.3 Per-tx fanout hard limit of 1,024 messages (incl nested) | WP—State Transition Function, System Act | Backlog | — |
| COW-2090 | §3.3 Exactly-once-after-finality vs at-least-once-before-finality delivery | WP—State Transition Function, System Act | Backlog | — |
| COW-1265 | [Node] Genesis supply allocation: 1B CBY split 66.67% Company Reserve / 33.33% Network Distr | WP—Economics, Entitlements & Genesis | Todo | — |
| COW-1266 | [Node] Initial governance parameter state at 0x09 at genesis | WP—Economics, Entitlements & Genesis | Todo | PL |
| COW-1267 | [Node] Entitlement Registry (0x07): state schema + grant/revoke history + audit trail | WP—Economics, Entitlements & Genesis | Todo | PL |
| COW-2021 | §13 Container Image Registry (0x0A) per WP §9 table not deployed as a | WP—Economics, Entitlements & Genesis | Backlog | — |
| COW-1028 | [Node] Replace vote-weight=1 with stake-weighted ERC20Votes-style checkpoints | CIP-12: On-Chain Governance & System Act | Backlog | — |
| COW-1637 | §5.3 Content-addressed body_ref (CBFS) | CIP-12: On-Chain Governance & System Act | Backlog | — |
| COW-1640 | §5.4 Circuit payload (Pause/Unpause/RatifyExtend/Cancel) | CIP-12: On-Chain Governance & System Act | Backlog | — |
| COW-1642 | §7.7 Circuit-breaker pause (paused_actors | CIP-12: On-Chain Governance & System Act | Backlog | — |
| COW-996 | [Node] Ring buffer + strict per-stream sequence (head_sequence, floor_sequence, gap detectio | CIP-7: Watchtower (Simple Stream Protoco | Backlog | PL |
| COW-997 | [Node/SDK] Filter DSL (depth ≤4, ≤16 predicates) — validation + compilation + evaluation | CIP-7: Watchtower (Simple Stream Protoco | Backlog | PL |
| COW-1002 | [Node] Paid-mode billing: fee_per_key_epoch_cby, protocol_fee_bps, key_epoch_blocks | CIP-7: Watchtower (Simple Stream Protoco | Backlog | PL |
| COW-1005 | [Node] Deterministic stream event emission | CIP-7: Watchtower (Simple Stream Protoco | Backlog | PL |
| COW-1012 | [Node/Runner] Pin production COWBOY_SESSION_CHAIN_ID | CIP-8: MPP Session Semantics | Backlog | — |
| COW-2178 | [Node] Land on-chain ingress.http + static_volumes binding (prereq for CIP-15 §6.8 route-vol | CIP-15: Public Asset Hosting & HTTP Rout | Backlog | — |
| COW-1798 | ICIP20Actor actor-token interface / actor-based tokens (fee-on-transfer | CIP-20: Fungible Token Standard | Backlog | — |
| COW-1544 | §13.4 transfer_volume(volume_name | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2113 | [Node] Public-volume commit prefix-confinement check | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2114 | [Node] Private-volume staged-commit finalize authority (DEK-holder) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2005 | WP §4.3/§State-Rent dynamic rent_rate adjustment | WP—Data Availability, Blobs & Storage | Backlog | — |

## Tier 5 — 最难 — 共识核心 / 密码学 / 大型绿地(按 epic 规划)(236 条)

| Issue | Title | Project | State | Asg |
|---|---|---|---|---|
| COW-1215 | [Node] Access-list validation: replace empty stub with actual checks | WP—Accounts, Transactions & Mempool | Backlog | PL |
| COW-2112 | [CBFS/Node] PoR: per-shard chunk-roots + shard_root + challenge nonce | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-917 | [Node/RAS] Implement Proof-of-Retrievability (PoR) on-chain mechanism | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-918 | [CBFS] Spot-check responder for PoR challenges | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-919 | [Node] PoR challenge timer via CIP-5 with fee_payer = STORAGE_MANAGER | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2007 | CBFS §7.1/§7.2/§7.4 on-chain PoR challenge loop | WP—Data Availability, Blobs & Storage | Backlog | — |
| COW-2183 | CBFS: Proof-of-Retrievability challenge/response + PoR-miss slashing | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-1275 | [Node] Add `storage_root: Digest` field to Actor record + Actor codec version bump | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1276 | [Node] Per-actor Merkle subtree commitment in state store | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1277 | [Node] state_set / state_delete recompute storage_root in cross-call write-set | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1279 | [Node] Define the well-known empty-trie root constant for the chosen scheme | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1280 | [Node] Gas formula for trie updates: deterministic, bounded cost per state_set / state_delet | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1281 | [Node] fork() O(1) clone: child.storage_root = parent.storage_root (replaces enumeration sto | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1282 | [Node/RPC] Expose per-actor proof endpoint: `GET Actor.storage_root` + opens against subtree | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1283 | [Node] Migration policy: pick wipe (devnet/testnet) vs online (any future mainnet) + impleme | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1284 | [Node] Cross-validator root-computation conformance test | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1285 | [Tooling] Pre-image table for hashed long keys (debugger / explorer enumeration) | CIP-30: Per-Actor Storage Root | Backlog | — |
| COW-1202 | [Node] VRF-based transaction ordering inside a block (WP §6.5) | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1962 | Proposer selection is VRF-based but NOT stake-weighted | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1963 | Per-header VRF output+proof field is not on the block header. WP §6.1 | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1964 | Mempool selection diverges from WP §6.4 | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1965 | Dedicated-lane BLOCK-SPACE partitioning + cascade is not implemented at | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1966 | QUIC over TLS 1.3 is NOT the transport. WP §6.2 'Implementations MUST | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1967 | Peer discovery is bit-vector gossip | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1968 | Stake-weighted block rewards + 100% proposer tip payout is unimplemented. | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1969 | Epoch boundaries (3600 blocks) with per-epoch validator-set / slashing / | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1203 | [Node] Validator set lifecycle: register / activate / exit / withdraw + epoch snapshot | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1206 | [Node] Validator equivocation detection + slashing aggregation (Cowboy-side) | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1205 | [Node] Block QC signer bitmap (finality-proof verification) | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1209 | [Node/Spec] Full state sync protocol: state-trie chunk download + recovery | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1210 | [Node] P2P peer scoring + anti-spam at gossip layer | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-123 | [Block] Add version field to block header | WP—Consensus, P2P & Randomness | Todo | — |
| COW-166 | [Block] Implement compact block representation | WP—Consensus, P2P & Randomness | Todo | — |
| COW-1207 | [Node] Cowboy-level integration tests for consensus invariants (finality, view change, valid | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-701 | [Audit MEDIUM] M-16: Unbounded spawned tasks can accumulate indefinitely | WP—Consensus, P2P & Randomness | Todo | — |
| COW-613 | [L7] Deterministic genesis leader key enables chain replay | WP—Consensus, P2P & Randomness | Backlog | PL |
| COW-915 | Canyon validator stuck at height 449k after PR #474 deploy — consensus engine tracks 0 peers | WP—Consensus, P2P & Randomness | Backlog | — |
| COW-1259 | [Node] Validator reward minting: per-block inflation for the 180M CBY validator pool | WP—Economics, Entitlements & Genesis | Backlog | — |
| COW-1260 | [Node] Inflation schedule: decreasing 8%/6%/4%/3%/2% curve + security-floor trigger | WP—Economics, Entitlements & Genesis | Backlog | — |
| COW-1261 | [Node] Treasury (0x08) state model: TreasuryState struct + inbound-flow accounting + governa | WP—Economics, Entitlements & Genesis | Backlog | — |
| COW-2019 | §8.3 Vesting schedules absent | WP—Economics, Entitlements & Genesis | Backlog | — |
| COW-2020 | §8.4 Slashed stake -> 100% burned | WP—Economics, Entitlements & Genesis | Backlog | PL |
| COW-1934 | §1.2 python_source canonicalization (UTF-8 | WP—Accounts, Transactions & Mempool | Backlog | — |
| COW-1935 | §1.2 exact derivation formula deviates | WP—Accounts, Transactions & Mempool | Backlog | — |
| COW-1937 | §2.1 field-set deviation | WP—Accounts, Transactions & Mempool | Backlog | — |
| COW-1941 | §2.4 EBNF Header field order | WP—Accounts, Transactions & Mempool | Backlog | PL |
| COW-1942 | §2.5 canonical-CBOR ARRAY encoding in fixed field order (Tx = [chain_id | WP—Accounts, Transactions & Mempool | Backlog | — |
| COW-1943 | §2.5 to=null for actor creation and access_list as null\|[[address | WP—Accounts, Transactions & Mempool | Backlog | — |
| COW-1944 | §2.5 signing hash defined as keccak256(CBOR(Tx_without_signature)) over | WP—Accounts, Transactions & Mempool | Backlog | — |
| COW-177 | [Transaction] Implement transaction version field | WP—Accounts, Transactions & Mempool | Todo | PL |
| COW-1240 | [PVM] Graceful stack-overflow handling (remove RUST_MIN_STACK workaround) | WP—Python Actor VM (PVM) | Backlog | PL |
| COW-1248 | [PVM] Exception-mapping determinism: identical input → identical `HostError` across validato | WP—Python Actor VM (PVM) | Todo | PL |
| COW-2055 | Runtime integer bit-length enforcement (>4096 bits produced via arithmetic | WP—Python Actor VM (PVM) | Backlog | PL |
| COW-2056 | Standardized C-ABI cross-VM call wrapper for PVM<->future-EVM (WP Storage | WP—Python Actor VM (PVM) | Backlog | — |
| COW-46 | [DEVNET][CIP-6] Loop + await: loop detection and continuation state explosion risk | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | PL |
| COW-1188 | [Node/Gateway] Nonce replay protection: atomic consumption on settlement | CIP-18: Payments | Backlog | PL |
| COW-1085 | [PVM] Build platform AMM host functions (amm_get_amount_out / amm_get_amount_in / amm_quote  | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1086 | [Node/Examples] V3 concentrated-liquidity pool: ticks, positions, fee accumulators | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1087 | [Node/Examples] Pool factory + registry (create_v2_pool, create_v3_pool, get_pool by (tokenA | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1088 | [Node/Examples] Swap routers: actor-router (flexible) + platform-router (amm_swap_exact_in/_ | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1089 | [Node/Examples] Validation hooks: can_swap, on_swap, can_add_liquidity, can_remove_liquidity | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1090 | [Node/Examples] Native TWAP oracle via timer-driven price-cumulative tracking | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1091 | [Node/Examples] V3 position manager: positions as transferable NFTs | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1092 | [Node/Examples] CIP-22 auction → CIP-21 pool graduation | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1114 | [Node/Runner] Runner-committee attestation verifier (2-of-3 signature aggregation, threshold | CIP-25: Cross-Chain Architecture | Backlog | PL |
| COW-1119 | [Runner] Runner-side reorg detection daemon + commitment_revoked primitive | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1116 | [Node] Cross-chain message timeout + cancellation (expiry, reclaim, on_timeout) | CIP-25: Cross-Chain Architecture | Backlog | PL |
| COW-1117 | [Node] Cross-chain fee prepayment + relayer bounty (20% treasury / 80% relayer) | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1896 | §1.4/§1.5/§A.5 ZK light-client backend | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1897 | §1.4/§A.5 Optimistic backend with challenger bonds/incentives | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1898 | §1.4/§A.5 Native light client backend (BLS12-381 sync-committee / | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1124 | [Examples] Cross-chain example dapp(s): bridge / oracle / lending demo | CIP-25: Cross-Chain Architecture | Backlog | PL |
| COW-1125 | [Tests] End-to-end cross-chain integration tests + adversarial cases | CIP-25: Cross-Chain Architecture | Backlog | PL |
| COW-1098 | [Node] CompositeAttestation envelope (CAE v1) struct + canonical encoding | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1099 | [Node] Composite attestation binding rule: REPORTDATA = keccak(nonce ‖ service_pubkey ‖ gpu_ | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1100 | [Node] TEE Verifier `0x05` system actor: opcodes 57–60 (VerifyCae / UpdateCpuRoot / UpdateNr | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1101 | [Node] 8-step verify_cae pipeline (freshness, replay, cert chain, measurement, REPORTDATA, s | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1102 | [Node] MeasurementBinding type + Runner Registry extension (per-runner allowed measurements  | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1103 | [Node] Attestation-first runner registration (registry → 0x05::VerifyCae cross-call) | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1107 | [Node] Quote-format parsers: TDX TDQuoteV4, SNP AttestationReport, Nitro COSE_Sign1 | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1108 | [Node] Root certificate registry + governance-delayed UpdateCpuRoot / UpdateNrasRoot | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1109 | [Node] CRL / TCB-update lifecycle handling | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1110 | [Node] FreshnessAnchor: nonce + deadline + generated_at, with replay tracking | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1111 | [Node/Runner] NVIDIA NCC GPU attestation (NRAS token + verification) | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1301 | [Node/Runner] BillingAttestation CAE freshness audit: per-event generation, no cached reuse | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1309 | [SDK] `tee_call` PVM SDK helper for invoking attested off-chain compute | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1844 | §3.4 ServiceSignature (scheme/service_pubkey/sig over | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1845 | §3.6.5 VerifyCae gas budget (200k cycles / cert-chain 120k etc.) not | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1846 | §3.5 On-chain storage strategy | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1849 | §3.6.3 execute-in-TEE body | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1850 | v2 §3 CIP-13 delegation interaction (effective_stake VRF weight vs | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1851 | §6 governance microcode-revision blacklist via UpdateCpuRoot collateral + | CIP-23: TEE Execution & Composite Attest | Backlog | — |
| COW-1748 | §5.2/§5.4/§6.1 MARQUEE FEATURE | CIP-17: Verifiable State Read RPC | Backlog | — |
| COW-1753 | §5.3 step-5 / §11 bundled account-trie proof binding actor.state_root to | CIP-17: Verifiable State Read RPC | Backlog | — |
| COW-877 | GET_STATE RPC + Merkle-proof verification on routes fetch | CIP-17: Verifiable State Read RPC | Backlog | PL |
| COW-432 | Frontend SDK: JS/TS SDK for browser interaction | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-435 | Frontend SDK: transaction building and signing | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-433 | Frontend SDK: wallet connection (secp256k1) | Node Hardening, Tooling & Supporting Wor | Todo | PL |
| COW-434 | Frontend SDK: actor storage queries | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-436 | Frontend SDK: WebSocket event subscriptions | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-403 | Templates: arb-bot template for price differential trading | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-405 | Templates: oracle-provider template for Watchtower feed | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-406 | Templates: watcher template for monitoring + alerts | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-407 | Templates: prediction-market template (Wrangler) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-390 | IDE/Linter: VS Code extension with real-time diagnostics | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-391 | IDE/Linter: quickfix suggestions for PVM violations | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-395 | IDE/Linter: inline cost estimates (CodeLens) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-396 | IDE/Linter: deploy/logs commands in command palette | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-398 | IDE/Linter: snippet library for common patterns | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-421 | IDE/Linter: actor graph visualization | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-414 | CLI: cowboy watch live actor TUI dashboard | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-416 | AI Context: MCP server for live doc queries | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-418 | CLI: cowboy trace cross-block execution trace | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-419 | AI Context: snippet registry for AI code generation | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-401 | AI Context: CI pipeline auto-generate from source | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-420 | CLI: cowboy upgrade versioned upgrades | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-428 | Upgrades: cowboy upgrade with dry-run diff | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-429 | Upgrades: state migration generation and validation | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-430 | Upgrades: rollback support with state restoration | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-415 | CLI: cowboy rollback revert to previous version | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-437 | Interfaces: auto-generate interface definitions from code | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-438 | Interfaces: cowboy inspect for any deployed actor | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-1082 | [Explorer] Token balance + transfer history UI | CIP-20: Fungible Token Standard | Backlog | — |
| COW-1073 | [Spec] Bridge / lock-and-mint CIP for ETH ↔ Cowboy L1 (blocking $COWBOY Aug 2026 launch) | CIP-20: Fungible Token Standard | Backlog | PL |
| COW-1659 | §3.1/§6.2 ingress.http param schema (allowlist_methods | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1660 | §3.3/§6.4 deploy-time manifest_validate of ingress.http params (unknown | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1663 | §4.2/§7.2 naming hierarchy + subdomain_policy (OWNER_ONLY default / | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1664 | §4.3/§7.3 name constraints ([a-z0-9-] | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1665 | §4.4/§7.4 register handler (caller auth | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1666 | §4.5/§7.5 registration economics | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1667 | §4.5/§6 RegistrySettlementConfig + system:registry_settlement_config + | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1668 | §4.6/§7.6 renewal (extend from current expiry) | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1669 | §4.7/§7.7 Route Registry API | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1670 | §7/§9.2 GATEWAY_REGISTRY (0x0E) system actor + GatewayProfile | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1671 | §7.2/§9.2 gateway lifecycle | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1672 | §6.1 SystemInstruction::IngressDispatch (opcode 65) command-path | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1673 | §6.1/§6.2 system-mediated http.request | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1674 | §6.3 gateway gas | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1675 | §7.4/§9.4 gateway serving-fee pool | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1676 | §8/§10 RECEIPT_REGISTRY (0x0F) system actor + Receipt record | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1677 | §8.2 complete_receipt system call (opcode 66) + registry-wide TTL pruning | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1678 | §8.3/§6.4 command-path async flow | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1679 | §8.4 receipt privacy (private flag | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1680 | §8.1/§8.2 (orig) HttpRequestEnvelope / HttpResponseEnvelope canonical | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1681 | §8.6/§9.1-9.6 Gateway node role | CIP-14: DNS-Addressable Actors | Backlog | — |
| COW-1698 | §7.2/§3.1 RouteRegistration→DomainBinding one-time migration with legacy | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1705 | §9.2/§5.2 begin_attach_external (nonce gen | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1706 | §9.2/§5.6 complete_attach_external system-mediated callback | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1707 | §9.2 reverify_external / detach_external / suspend_external methods | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1708 | §5.2/§Part-III-§2.3 dns.attach_external entitlement registry entry | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1709 | §5.6/§9 SystemInstruction::ExternalDomainCallback opcode 67 with | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1710 | §5.6 SuspendBinding failure-path opcode (0x03 allowlist) for | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1711 | §5.3 begin_attach_external enqueuing a DNS-verification JobSpec into | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1713 | maybe_enable_dns_capability boot-time self-check NOT production-wired | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1714 | §5.7/§5.10 reverification flow | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1715 | §5.8 EXTERNAL_REVERIFY_FEE charged from owner per firing | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1716 | §5.10 reverify timer fee_payer=owner + TimerCancelledInsufficientFunds | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1718 | §9.4/§5.4 CANONICAL_EDGE_HOSTNAME (anycast default | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1719 | §9.5/§5.5 ACME DNS-01 delegation (_acme-challenge CNAME → | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1720 | §10/§7 Gateway resolution & serving policy (ACTIVE-only | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1721 | §7.3 verified_fqdn + namespace_kind injection into HttpRequestEnvelope by | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1722 | §10.3/§7.4 first-party TLD DNS authority serving from Route Registry | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1723 | §12/§8 external constants CHALLENGE_EXPIRY_BLOCKS | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1724 | §11 security considerations (reverification mandatory | CIP-16: Custom Domains & First-Party TLD | Backlog | — |
| COW-1177 | [Node/Spec] PaymentGate system actor address: resolve 0x0013 (CIP-18) vs 0x11 (WP r2) | CIP-18: Payments | Backlog | — |
| COW-1178 | [Node] PaymentGate system actor: state schema + instructions (settle, credit_inbound, refund | CIP-18: Payments | Backlog | — |
| COW-1179 | [Node] MPP wire format: WWW-Authenticate: Payment header + HMAC-SHA256 binding | CIP-18: Payments | Backlog | — |
| COW-1180 | [Gateway] x402 wire format verifier (replace 501 stub) | CIP-18: Payments | Backlog | — |
| COW-1181 | [Node] PaymentIntent normalization (MPP and x402 → single shape) | CIP-18: Payments | Backlog | — |
| COW-1182 | [Node] PaymentAuthorization struct + Ed25519 signing semantics | CIP-18: Payments | Backlog | — |
| COW-1183 | [Node] Four payment models: per-request, actor-funded budget, prepaid pass, epoch subscripti | CIP-18: Payments | Backlog | — |
| COW-1184 | [Node/Runner] EVM bridge facilitator: bridge.facilitate.evm entitlement + BridgeEvidence + c | CIP-18: Payments | Backlog | — |
| COW-1185 | [Gateway] PaymentPolicy cache + per-route lookup | CIP-18: Payments | Backlog | — |
| COW-1186 | [Gateway] CIP-19 MCP gating: /_cowboy/mcp endpoint + JSON-RPC error -32402 | CIP-18: Payments | Backlog | — |
| COW-1187 | [Node] payment.gate entitlement registration | CIP-18: Payments | Backlog | — |
| COW-1189 | [Gateway] /_cowboy/payment/openapi.json discovery endpoint | CIP-18: Payments | Backlog | — |
| COW-1190 | [Tests] End-to-end payment test suite (MPP + x402 + bridge + replay + refund) | CIP-18: Payments | Backlog | — |
| COW-1755 | §9.5.3 method="tempo" (reserved) | CIP-18: Payments | Backlog | — |
| COW-1756 | §16.1 did:cowboy:<hex> DID format in MPP source field | CIP-18: Payments | Backlog | — |
| COW-1757 | §16.2/§16.3 Payment-derived identity + account signature over (challenge.id | CIP-18: Payments | Backlog | — |
| COW-1758 | §18 Revenue distribution | CIP-18: Payments | Backlog | — |
| COW-1759 | §19 Protocol constants (PAYMENT_GATE_ADDRESS=0x11 | CIP-18: Payments | Backlog | — |
| COW-1760 | §24 Genesis deployment of PaymentGate at 0x11 | CIP-18: Payments | Backlog | — |
| COW-1093 | [Node/Examples] Fee handling: protocol fee vault + DAO treasury distribution | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1096 | [Tests] Multi-hop routing + factory + hooks + TWAP integration tests | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1799 | IV2Pool extras | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1800 | Canonical token sorting in init (token_a>token_b swap) - spec ref impl | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1801 | On-chain limit orders via state-triggered timers (6.2 LimitOrderBook) | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1802 | MEV-protection hook (6.3) and KYC/compliance hook (6.4) - absent (no hook | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1803 | Sync event (events section) - example emits liquidity/swap events but no | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1804 | Hook resource cap enforcement (50k Cycles/Cells | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1805 | Reference platform impl cowboy-core/src/runtime/amm.rs (spec §Reference | CIP-21: DEX & Liquidity Pools | Backlog | — |
| COW-1115 | [Node] Fraud-proof window + slashing for runner-committee backend | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1120 | [Node/Runner] min_confirmations configurable per source chain (probabilistic finality) | CIP-25: Cross-Chain Architecture | Backlog | PL |
| COW-1121 | [Node] Dual-backend defense-in-depth (B.6 pattern 1): combine two independent anchors | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1122 | [Runner] Runner job type `generate_inclusion_proof` (third-party proof service) | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1123 | [Node] Cross-chain proof TTL enforcement (finalized_at + max_age) | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1899 | §1.6 Multi-destination cost reduction | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1900 | §1.3 state_root / parent_hash commitment fields | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1901 | §2.5/§2.6 Cross-chain streaming | CIP-25: Cross-Chain Architecture | Backlog | — |
| COW-1134 | [Node] BankActor system actor `0x0D`: registration + state schema + handler stubs | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1135 | [Node] Card address derivation: keccak256 domain (§2.6) | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1136 | [Node] charge_gas pipeline: Phase 1 reservation + Phase 2 settlement (§4.2) | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1137 | [Node] SpendWindow rolling-window enforcement (hourly / daily / monthly, M1 fixed-window) | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1138 | [Node] Whitelist enforcement: allowed_receivers + allowed_syscall_kinds | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1139 | [Node] Emit nine event types (CardIssued, CardDeposited, CardWithdrawn, GasCharged, Frozen,  | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1140 | [Node] Card state machine: Active / Frozen / Closed / Expired transitions (§5.3) | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1141 | [Node] Timer-deferred tx double-accounting (§4.3) | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1142 | [Node] FiatMintVoucher signature verification + replay protection (§3.3, §6.2) | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1143 | [Node] CIP-12 governance integration for RegisterBank (§3.4) | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1145 | [Tests] End-to-end card lifecycle integration tests | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1902 | §1.3 New tx-level field tx.fee_payer_override | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1903 | §2.3 Day-1 gas_payment_token whitelist constraint (Native CBY or official | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1904 | §2.7/§4.1 fee_payer resolution fork (card-address lookup → | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1905 | §3.2 SetDefaultCard instruction (caller==agent or card.owner | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1906 | §3.3 PauseBank / UnpauseBank instructions (caller==operator | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1907 | §3.4 SetBankOperator instruction (caller==operator or governance | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1908 | §3.4 SetBankFiatMintSigner instruction (caller==operator | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1909 | §4.2 Async discipline using block_on_local for !Send futures in charge_gas | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1910 | §4.4 Edge-case handling (frozen/expired after reserve | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1911 | §4.5 BankErr error family + engine ErrorMap (CardNotFound | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1912 | §4.6 GasCharged receipts with tx_digest for Indexer join / card-statement | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1913 | §5.4 locked_after_transfer precise semantics (owner==agent && locked → | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1914 | §6.1 Cowboy Banking genesis bank entry (bank_id=1 | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1915 | §6.1 Inter-bank state isolation (bank_id-scoped operator freeze/pause | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-1916 | §7.3 Feature gate governance parameter bank_activation_height | CIP-28: Cowboy Agent Banking | Backlog | — |
| COW-927 | [Node] POST /ras/challenge endpoint + chain-state challenge records | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-379 | SDK: storage utilities and migration scaffolding (stub) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-404 | Templates: trading-bot template (LLM signal + execution) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-423 | Observability: live state viewer in Cowchat | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-424 | Observability: timer timeline visualization | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-425 | Observability: runner job tracker | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-426 | Observability: message trace visualization | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-427 | Observability: cost breakdown and trending | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-2265 | mainnet launch: bundle devnet consensus-rule deltas (node#686 receipt code 1613, node#707 64 | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-2266 | Reconcile whitepaper genesis parameter defaults vs reference implementation (basefee T_c/T_b | Node Hardening, Tooling & Supporting Wor | Todo | — |

## Tier 0 — 排除项 — 回避令 / 被阻塞 / 他团队 / 仓库不在本地 / in-flight(不建议拿)(204 条)

| Issue | Title | Project | State | Asg |
|---|---|---|---|---|
| COW-1568 | §10.1–10.2 full container lifecycle (image pull → create | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1569 | §10.3 failure-mode handling (OOM kill | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1570 | §10.4 container exit-code → CIP-2 status mapping (0→COMPLETED | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1571 | §11.1 OffchainTask.runtime_config | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1572 | §11.2 Container Registry system actor (BaseImageEntry | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1573 | §11.3 CIP-4 STORAGE key-space layout for image/class entries (keccak256 | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1574 | §12.1 compute-resource billing (max_compute_cost lock at submit_task from | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1575 | §12.2 image-pull egress fees (pull_cost = size * EGRESS_FEE_PER_BYTE | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1576 | §12.3 BillingAttestation {cpu_used | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1577 | §12.4 attestation-based compute settlement distinct from CIP-3 Cycles/Cells | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1578 | §13 parameter set (MAX_CPU_MILLICORES | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1579 | §14.1 container-escape mitigations (namespace isolation | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1580 | §14.2 image supply-chain (digest pinning | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1581 | §14.5 clean container env / no host-fs / no docker socket / TEE-sealed | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1582 | §14.6 GPU side-channel mitigations (NVIDIA MIG isolation | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1583 | Appendix B default seccomp profile (allowed/blocked syscall categories) | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1584 | v2 §1 Container Registry actor address 0x10 | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1585 | v2 §2 ContainerSettlementConfig {runner 89% / treasury 1% / burn 10%} | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1586 | v2 §3 three-flow independent escrow model with container flow settling at | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1587 | v2 §4 BillingAttestation.tee_signature | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-1588 | v2 §5 system instruction opcodes 61–64 (RegisterBaseImage / | CIP-10: Runner Container Runtime [Cancel | Backlog | — |
| COW-894 | ManifestCommitted chain event subscription | CIP-9: Cowboy File System (CBFS)-Backed  | In Review ⚠ | PL |
| COW-921 | [Node] Emit ManifestCommitted chain event on successful commit_manifest (AMEND 9-H) | CIP-9: Cowboy File System (CBFS)-Backed  | In Progress ⚠ | PL |
| COW-1056 | [CBSS] Release receipt release_id collateral fields | CIP-24: Cowboy Secret Service (CBSS) | In Progress ⚠ | PL |
| COW-1058 | [CBSS] Liveness challenge health-score attrition rate limit | CIP-24: Cowboy Secret Service (CBSS) | In Progress ⚠ | — |
| COW-1063 | [CBSS] Handler 404/410/409 branch tests | CIP-24: Cowboy Secret Service (CBSS) | In Progress ⚠ | — |
| COW-482 | CLI | Node Hardening, Tooling & Supporting Wor | In Progress ⚠ | PL |
| COW-492 | SDK | Node Hardening, Tooling & Supporting Wor | Backlog | PL |
| COW-495 | Error Messages | Node Hardening, Tooling & Supporting Wor | Backlog | PL |
| COW-498 | AI Context | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-220 | [Transaction] Add access list support (reserved) | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-2099 | [CIP-9] Rewrite epic: triage grounded findings from mesa bring-up (cip-9-rewrite-ideas.md) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-2237 | Tracking: CIP-24 hardening — IBE confidentiality fix + spec-review remediation (fold into CI | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |
| COW-765 | Entitlements implementation doesn't match the spec | WP—Economics, Entitlements & Genesis | Backlog | — |
| COW-1191 | [Node/Examples] ContinuousClearingAuction actor skeleton + clear_block algorithm | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1192 | [Examples] Bid submission + escrow: place_bid / withdraw_bid / increase_bid / update_max_pri | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1193 | [Examples] Per-block clearing logic: SortedMap by max_price + pro-rata fill | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1194 | [Examples] Release schedule parsing: ReleaseStep iteration by block-height offset | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1195 | [Examples] CIP-21 pool graduation: factory.get_or_create_v2\|v3_pool() + mint_position() | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1196 | [Examples] Anti-manipulation: TWAP checkpoints, flash-loan guards, bid duration locks, MEV-g | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1197 | [Examples] FAILED path: min_currency_raised threshold + claim() refund logic | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1198 | [Examples] ICCAHook integration: validation hooks at place_bid / withdraw_bid / claim | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1199 | [PVM] Q96 math + SortedMap availability (host functions or SDK library) | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1200 | [Examples] Reference auction example actor at examples/<NN>-cca/ | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1201 | [Tests] Clearing math edge cases (pro-rata rounding, tie-break, partial fill, max u256) | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1806 | AuctionConfig data structure (token_id | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1807 | ReleaseStep data structure (rate_mps u24 | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1808 | PoolType enum (V2_FULL_RANGE / V3_CONCENTRATED) | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1809 | Bid data structure (bid_id | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1810 | AuctionState data structure (current_block | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1811 | Checkpoint data structure (block | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1812 | AuctionStatus enum (PENDING/ACTIVE/ENDED/GRADUATED/FAILED) | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1813 | ICCA.claim(bid_id)->(tokens | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1814 | ICCA.claim_batch(bid_ids) | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1815 | Query methods | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1816 | _remaining_demand(bid | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1817 | Checkpoint append per block for pro-rata claim accounting | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1818 | Hook gas/cell cap enforcement (50,000 Cycles / 50,000 Cells | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1819 | Timer integration | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1820 | Timer integration | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1821 | ICCAFactory.create_auction(...)->address with end>start | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1822 | ICCAFactory.create_auction_with_token(name | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1823 | Overflow guard | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1824 | Event AuctionCreated | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1825 | Event AuctionStarted | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1826 | Event AuctionEnded | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1827 | Event AuctionGraduated(final_price | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1828 | Event AuctionFailed(currency_raised | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1829 | Event BidPlaced | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1830 | Event BidWithdrawn | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1831 | Event BidIncreased | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1832 | Event BidPriceUpdated | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-1833 | Event TokensClaimed(tokens | CIP-22: Continuous Clearing Auctions [Bl | Backlog | — |
| COW-883 | Wire CIP-18 payment gating (replace NotReadyVerifier) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-891 | 405 Method Not Allowed on non-GET/HEAD to Volume routes | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-1013 | [Code] When Slash milestone activates, extend Disputed with opened_at: u64 | CIP-8: MPP Session Semantics | Backlog | — |
| COW-1051 | [CBSS] TEE vendor-quote chain-of-trust (DOD-07-TEE v1.1) | CIP-24: Cowboy Secret Service (CBSS) | Backlog | — |
| COW-1847 | §3.10 Secrets Manager get_secret(attestation) TEE-gating | CIP-23: TEE Execution & Composite Attest | Backlog | PL |
| COW-508 | Create API Gateway module for key-gated RPC access | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-513 | Configure Tailscale ACLs for Mesa tags | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-514 | Set up API Gateway with usage plan and initial API keys | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-515 | Configure IP allowlist variable in terraform.tfvars | Node Hardening, Tooling & Supporting Wor | Todo | — |
| COW-462 | Public testnet RPC endpoint (+ Status Page) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-473 | Basic chain monitoring + alerting (block lag, RPC error rate, peer count) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-751 | API reference and PyPI publishing | Node Hardening, Tooling & Supporting Wor | Backlog | PL |
| COW-525 | New version checks | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-526 | Install CLI as dependency | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-527 | Use runners from console | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-823 | need a list of sessions on the sidebar | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-2172 | need an option to login with a different account | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-2207 | add login with google | Builder | Backlog | — |
| COW-2208 | add advanced mode | Builder | Backlog | — |
| COW-2209 | add ability to see your files on CBFS and edit them (like edit the prompt on the chatbot) | Builder | Backlog | — |
| COW-2210 | add "next up" helpers - | Builder | Backlog | — |
| COW-2211 | General Store | Builder | Backlog | — |
| COW-2212 | add CBSS support | Builder | Backlog | — |
| COW-2213 | add support for Telegram, and SMS. These should probably be actors that you just hire | Builder | Backlog | — |
| COW-2214 | Agent cannot modify templated chatbot actor on 8k runner because write_actor exceeds prompt  | Builder | Backlog | — |
| COW-2215 | Agent misroutes “don’t simulate” correction into simulate_actor because of brittle regex int | Builder | Backlog | — |
| COW-2216 | Agent loops on cowboy_knowledge and stops after 3 calls instead of using results to revise a | Builder | Backlog | — |
| COW-2257 | add image models | Builder | Backlog | — |
| COW-2231 | AI builder sends referenced local .py files to dashboard_url without confirmation | — | Backlog | — |
| COW-878 | Routes-table churn metric (per-actor state_root change rate) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-879 | CIP-9 §13.5 storage-status-driven Volume serving | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-882 | Operational metrics surface (hit/miss, per-actor RPS, per-route p50/p95/p99) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-886 | GET_MANIFEST RPC client (single round trip for public volumes) | CIP-9: Cowboy File System (CBFS)-Backed  | Backlog | — |
| COW-884 | Per-volume metadata cache (manifest + content_types + cache_config + cors_config) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-885 | Object LRU cache keyed by (volume_id, object_path) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-888 | Reed-Solomon reconstruction + BLAKE3 integrity chain | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-889 | resolve_volume_path (strip_prefix + volume_path_prefix) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-890 | Volume fallback object + status (SPA support) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-892 | Replace HttpCbfsClient prototype with manifest/shard split | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-893 | MANIFEST_POLL_INTERVAL-driven cache refresh loop | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-895 | Verify fail-closed on malformed CBOR routes write | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-896 | CORS precedence for Method routes (actor wins, gateway fills from cors_config) | Node Hardening, Tooling & Supporting Wor | Backlog | PL |
| COW-897 | CORS for Volume routes (apply cors_config + permissive default) | Node Hardening, Tooling & Supporting Wor | Backlog | PL |
| COW-898 | Conditional requests via If-None-Match against per-object ETags | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-899 | Compression: Accept-Encoding → serve precomputed gzip/br variants | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-900 | Hedged parallel shard fetch | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-901 | Compressed variants in object cache | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-902 | Cache warming on actor registration | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-903 | Concurrent-request coalescing (single-flight per object) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-1761 | §7 `ingress.mcp` entitlement id with params (server_name | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1762 | §7 Prerequisite enforcement | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1763 | §7 Composition with payment.gate | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1764 | §8 MCP endpoint at /_cowboy/mcp over streamable HTTP transport (POST/GET) | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1765 | §8 405 Method Not Allowed for other methods on /_cowboy/mcp | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1766 | §8 Endpoint intercepted before route resolution (Gateway pre-routing) | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1767 | §8.1 Session lifecycle | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1768 | §8.1 Session termination via DELETE or MCP_SESSION_IDLE_TIMEOUT_SECONDS | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1769 | §8.1 Session state limited to | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1770 | §9 initialize capability negotiation | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1771 | §9 Non-advertisement of resources/prompts/completions/sampling capabilities | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1772 | §10.1 tools/list generation algorithm | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1773 | §10.2 Tool entry shape (name/description/inputSchema/_meta.cowboy) | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1774 | §10.3 Input schema derivation from path params + OpenAPI doc | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1775 | §10.3 Schema-compatibility check across routes sharing a method name (skip | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1776 | §10.4 Tool name mapping = tool_name_prefix + sanitize(target.name) | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1777 | §11.1 tools/call request handling (name | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1778 | §11.2 Translation to synthetic HttpRequestEnvelope (path param substitution | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1779 | §11.3 Dispatch | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1780 | §11.4 Response mapping HttpResponseEnvelope→MCP content[]/isError/_meta | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1781 | §11.5 Error mapping | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1782 | §12.1 No-payment dispatch for pays=actor routes | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1783 | §12.2 Payment-required -32402 error frame with MPP challenges + x402_compat | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1784 | §12.3 Credential normalization to PaymentIntent + PaymentGate verify/settle | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1785 | §12.4 pass/subscription credential evaluation ahead of charge per CIP-18 | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1786 | §13 Reserved _cowboy_* tool-name namespace | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1787 | §14.1 Gateway MCP server impl | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1788 | §14.3 Per-actor tool-list cache keyed by (actor | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1789 | §16 Protocol constants (MCP_PROTOCOL_VERSION | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1790 | §17 Security controls | CIP-19: Gateway MCP Ingress | Backlog | — |
| COW-1590 | §4.1/§6.1 Persistent QUIC (RFC9000)+TLS1.3 runner->validator control | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1591 | §4.1/§10.1 Push job delivery | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1592 | §5.1 Connectivity Subset function Sub(R,t)=first k validators by | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1593 | §5.1 Subset size k = clamp(ceil(log2(\|V\|))+1 | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1594 | §5.2 Validator-side DoS gate | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1595 | §5.3 Subset rotation per SUBSET_EPOCH_BLOCKS / VALIDATOR_CHURN_THRESHOLD | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1596 | §6.2 Pubkey-bound TLS handshake + Hello/HelloAck (0x01/0x02) frames with | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1597 | §6.2 Per-IP Hello rate-limit for connection-storm DoS | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1598 | §6.3 Control-stream HeartbeatPing/HeartbeatPong (0x10/0x11) once per | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1599 | §6.4 BackpressureSignal (0x12) accepting_new=false -> validator clears bit | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1600 | §6.5 CapabilityDelta (0x13) advisory runtime capability/entitlement updates | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1601 | §7.1 Vote payload extension | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1602 | §7.2 Per-validator bitmap construction (open auth stream + recent ping + | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1603 | §8.1 Canonical Presence Bitmap P(H) derived deterministically from | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1604 | §8.2 presence_threshold(n)=floor((n-1)/3)+1 (f+1) | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1605 | §8.4 Registry-order indexing of bitmaps as of parent block | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1606 | §9.1 Dispatcher Filter 1.5 Presence | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1607 | §9.3 MRU weight multiplier on Fisher-Yates iteration 0 only | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1608 | §9.4 New dispatcher state | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1609 | §9.4 Result Verifier write path | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1610 | §10.2 JobAck (0x21) with AckStatus Accepted/Duplicate/Reject | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1611 | §10.3 JobResult (0x23) streamed back on job stream + signature | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1612 | §10.4 JobProgress (0x22) optional streaming progress | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1613 | §10.5 JobCancel (0x24) push frame on reassignment/expiry/failure | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1614 | §10.6 Dispatch Outcome classification | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1615 | §11.1 Per-dispatch ACK_TIMEOUT_BLOCKS HardFailure -> clear presence | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1616 | §11.3 QUIC connection-loss handling + exponential-backoff reconnect | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1617 | §12.1/§12.2 Length-prefixed CBOR frame envelope + full frame-type table | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1618 | §12.3 VotePresenceBitmap inter-validator encoding | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1619 | §12.4 Hello.version=1 versioning + Goodbye{unsupported_version} on | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1620 | §13 CIP-11 system constants (MIN/MAX_SUBSET | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1621 | §14 Three-phase migration (Shadow / Hot Path / Sunset) gated by | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1622 | §15.6 QUIC+TLS1.3 transport replacing plaintext HTTP for job content | CIP-11: Runner Connectivity & Push Job D | Backlog | — |
| COW-1372 | §1 Mandatory result_schema (max_return_bytes | CIP-2: Verifiable Off-Chain Compute | Backlog | — |
| COW-1374 | §5/Security 'candidates_snapshot Merkle root stored on-chain at submission | CIP-2: Verifiable Off-Chain Compute | Backlog | — |
| COW-1375 | §5/§3 VRF seed uses block_height (LE-padded into 32-byte proxy) as a | CIP-2: Verifiable Off-Chain Compute | Backlog | PL |
| COW-1377 | §8 'Aggregator collects result_bytes via direct HTTP push' + | CIP-2: Verifiable Off-Chain Compute | Backlog | PL |
| COW-1378 | §8 'aggregator_timeout_blocks fallback to individual reveals / | CIP-2: Verifiable Off-Chain Compute | Backlog | — |
| COW-957 | [Node/Runner] TEE attestation verification pipeline (SGX, SEV-SNP, TDX, AWS Nitro) | CIP-2: Verifiable Off-Chain Compute | Todo | PL |
| COW-1373 | §3 step1 full JobSpec validation (bounds != 0 | CIP-2: Verifiable Off-Chain Compute | Backlog | — |
| COW-439 | Interfaces: on-chain interface registry | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-440 | Ecosystem: web-based playground / REPL | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-441 | Ecosystem: actor-aware block explorer | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-442 | Ecosystem: reusable component registry | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-443 | Ecosystem: actor marketplace (view source, fork) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-444 | Ecosystem: bounty board and grants program | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-445 | Ecosystem: Corral IDE (or VS Code extension branding) | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-1365 | §3.9 future-GC reachability guard (GC must check union of live | CIP-26: Account-Scoped Actor Libraries | Backlog | PL |
| COW-399 | AI Context: .cursorrules in cowboy init output | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-400 | AI Context: llms.txt at docs domain root | Node Hardening, Tooling & Supporting Wor | Backlog | — |
| COW-496 | Four-part error format (what, why, fix, link) | Node Hardening, Tooling & Supporting Wor | Backlog | PL |
| COW-387 | Errors: common error mapping table in PVM | CIP-6: In-PVM Actor SDK (cowboy_sdk) | Backlog | PL |
