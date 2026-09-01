# 当期可推进 Issue 里「好修的那些」

**筛选日期**：2026-08-18
**来源报告**：`refs/analysis/Cowboy CIP · Issue Disposition Snapshot (how many issues each CIP still has left).html`（数据时点 2026-08-17 24:00 北京时间，口径 = ours/unassigned，排除客户方）
**Linear 实况**：2026-08-18 直接查 GraphQL 复核，见 §1
**代码基线**：`node@devnet 99042956`、`cbfs@devnet 7b55d09`、`runner@devnet ebf2054`、`cowboy@devnet 62cd3ae`
**配套文档**：`2026-08-06_Issue_Difficulty_Assessment_CN.md`（109 条难度评估，08-11 代码对比更新）、`2026-08-10_CIP9_Open_Issues_Deep_Review_CN.md`（CIP-9 深度审核）

> 本文回答的是「**现在就能开工、且开工后不会被共识面/跨仓/决策门拖住**的是哪几条」。
> 每条 A/B 级都在上面的代码基线上**实地看过改点**（文件:行号列在表里），不是按 Issue 标题推定。

---

## 1. 口径与数字

| | 条数 | 说明 |
|---|---:|---|
| 快照 08-17 的 left | 145 | 报告口径：in progress + todo，ours/unassigned |
| Linear 08-18 实况（CIP projects，ours/unassigned，未完成未取消） | 166 | 差额 21 = **08-18 新开 19 条 CIP-9/CBFS**（COW-3259 ~ COW-3277）+ 2 条与快照口径差 |
| − 十一月递延（CIP-21 15 + CIP-22 35） | −50 | 报告「deferred to after the November token launch」 |
| − 外部前置缺失 | −8 | COW-1051 / 1111 / 1582 / 1365 / 2283 / 2617 / 2618 / 2661 |
| **= 当期可动** | **107** | 逐条清单见附录 A |

**重要**：报告快照之后（08-18 02:07–02:10）一次性新开了 19 条 CBFS issue，本文 A 级里有一半出自这一批——它们带精确的 `文件:行号` 证据，是目前性价比最高的一档。

---

## 2. A 级：现在就能开工

判据：**单仓** + **不进共识面**（不改 `state_root`/`receipt_root`/线格式）+ **改点已定位** + **无前置阻塞**。量级 ≈ 半天到 1 天（含测试）。

| Issue | 仓 | 已实证的改点 | 修法 | 备注 |
|---|---|---|---|---|
| **COW-3272** | cbfs | `node/src/main.rs:175` — `std::env::var("CBFS_ACCEPT_ALL_AUTH").is_ok()` | 解析成明确 bool；非 loopback / 生产绑定时拒绝 unsafe 模式 | 安全；填 `0` 或 `false` 现在一样开全放行 |
| **COW-3273** | cbfs | `cli/src/commands/mount.rs` — `refresh_fn` 里 `mint_owner_token(&open, AccessMode::ReadWrite, …)` 写死，而外层函数收了 `access_mode` 参数 | 把原始 mode（+ audience）透传；补 RO/WO 跨过期回归测试 | 安全；token 刷新静默放宽持有者权限 |
| **COW-3037** | cbfs | `fuse/src/fs.rs:1691` — `fn access(…, _mask: AccessFlags, …)` 只调 `access_inode` 查存在性 | 按 mask 判定，与 `require_read`/`require_write` 及上报的 masked mode 对齐 | cbfs#129 已把上报 mode 做成 grant-masked，这里是残余 |
| **COW-3170** | node | `rpc/src/handlers/ras.rs:3182-3188` — RUNNER 分支**已经载入 `StorageCommitment`**（为取 `last_owner_transfer_block`），但从不看 `status` | 同一个 match 臂加状态检查（DELETED / GARBAGE_COLLECTING 拒绝） | RPC 读路径，不改共识状态；cbfs#140 已关掉 owner 侧同一个洞 |
| **COW-3131** | runner | `runner-storage/src/lib.rs:309/319`（`!= "READ_ONLY"` ⇒ 可写）对 `:868`（`== READ_WRITE \|\| == WRITE_ONLY` ⇒ 不是授权） | 边界处校验 `access_mode`，统一 fail-closed | **钉住测试已在树里**：`unknown_access_mode_is_read_two_opposite_ways` |
| ~~**COW-3052**~~ | node/pvm | **已在 devnet 修好** —— node#1340（`d14d0f44`，08-16 19:31 UTC 合入）cfg-gate 了 `SOCK_CLOEXEC` + `fcntl` 兜底 | 无需再做 | 08-18 实证：`cargo check --target aarch64-apple-darwin -p pvm-ipc` 在 `c7339ba5` 通过。另：`SockType::SeqPacket` 在 nix 0.30 **不是** Linux-only（`libc::SOCK_SEQPACKET` 无 cfg），issue 那半条描述不成立 |

**核对过无重复劳动**：以上 6 条在 `cowboyinc/cbfs`、`cowboyinc/runner`、`cowboyinc/node` 的开放 PR 列表里都没有对应 PR（2026-08-18 查）。

### 08-18 执行结果

| Issue | 结果 |
|---|---|
| COW-3272 / COW-3273 / COW-3037 | **cbfs#153**（base devnet，三个 commit） |
| COW-3170 | **node#1347** |
| COW-3131 | **runner#218** |
| COW-3052 | **无需做** —— devnet 上已由 node#1340 修好（实证见上表），已在 Linear 贴 comment 建议 close |

每条都跑了变异验证（把修复原样倒回 ⇒ 点名的新测试必红）。node#1347 另跑了 pack 选中的 6 条 econ 不变量，**6/6 绿**（含 `econ.fee_waterfall_alias_conservation`，该测试现在树里有了）。

---

## 3. B 级：小，但要拍一个板，或半径稍大（1–3 天）

| Issue | 仓 | 情况 | 卡点 |
|---|---|---|---|
| **COW-3171** | cbfs | 孤儿 GC 失败闭合后不可见；树里目前**没有**连续跳过计数/最后成功回收时间戳 | 纯加观测，Issue 自己按成本排好了三个挂载点，选哪个是取舍不是难度 |
| **COW-3261** | runner | `runner-node/src/node.rs:1099` 把 `session.finalize()` 的 `Err` 只 `warn!` 掉并丢弃 roots；`runner-storage` 侧 `finalize()` **已经 fail-closed**（COW-2668 注释在） | 调用缝改成传播失败 + 把 committed roots 带进终态结果 ⇒ 碰结果形状，要看 runner-common 的 schema |
| **COW-3040** | cbfs | `fuse/src/fs.rs:1100-1106` — `entry.uid/gid/atime` 原样落盘，宿主本地值进内容寻址清单 | 与 cbfs#129 已修好的 `mode` 同形状，照抄即可；要决定归一化策略 |
| **COW-3262** | cbfs | `node/src/repair.rs:629-637` 修复上传发裸 shard bytes + `auth_token: vec![]`，生产 handler 要 `PutShardPayloadV2` | 改走正规 RPC envelope 不难；empty-auth 那半要和 COW-2675 协调 |
| **COW-3028** | cbfs | standalone（无 Cowboy）上手路径从没有外部用户实跑过 | 无风险，但掉出来的修法大小未知 |
| **COW-3122** | cowboy(docs) | 纯文档 errata，三句话两个文件 | ⚠️ **前提要重推**，见下 |

### ✅ COW-3122 的前提已在 devnet 上成立（08-18 当天翻转）

早些时候我核到 `runners_unrewarded` 只存在于 `feature/eth-lc-finality-update`（commit `78096dfa`，node#1257/#1271），因此判「errata 三句里有一句现在写下去是错的」。**这个判断在同一天被推翻**：node#1257 已合入 devnet（`c7339ba5`），现在：

- `git grep -c unrewarded origin/devnet` → `execution/src/runner/verifier.rs:57` 等四个文件命中；
- `verifier.rs` §9.4 写路径的注释现在明写「ineligible 是 `runners_to_slash` **UNION** 每个结果没通过验证的提交者」，而 `cowboy/docs/cips/cip-11-runner-connectivity.md` 的 §9.4 仍写「not in `runners_to_slash`」⇒ **规格与代码确实分歧了**；
- 第二半（§8.1 的 MRU banner）也仍然成立：`MRU_ACTIVATION_HEIGHT` 在 devnet 上还是 `u64::MAX`（dormant），banner 若宣称 MRU 已生效即为假。

⇒ COW-3122 现在是**干净的纯文档 errata**，不再有「等 PR 合入」的前置。教训见 [[feedback_fix_premise_upstream_changed_may_be_false]] 的反向：**前提可能在你写完判断后被合入翻转，落笔前重查一次 base**。

## 4. 看着像小改、其实不是（别当快赢领走）

| Issue | 表面 | 实际 |
|---|---|---|
| **COW-2914** | 改个字段名 | 实为拆两个参数 + 创世种子 + 跨 node/cbfs；**已在 cbfs#118 / node#1221 进行中**，不要重复分配 |
| **COW-1012** | 改一个常量 | 同时绑着 CIP-9 volume-DEK 封装，直改 ⇒ `AadMismatch`，需重封装迁移。L |
| **COW-2824** | 3 个文件 | `pvm/Lib/cowboy_sdk` 随节点二进制发布，FSM 编译发生在链上 import 时 ⇒ 混版本机群分叉，需旗日 |
| **COW-1139 / 1911 / 1917 / 1147 / 1152** | diff 都很小 | 错误码 / 事件 / 收据字段 / 宿主 ABI 都进 `receipt_root` 或状态转换 ⇒ 共识变更 |
| **COW-1281 / 1282 / 1285** | XS / S | 全部卡在 COW-1277（storage_root 重算，L + 激活门） |
| **COW-3169** | 补一个规格常量 | 修法落在 `node/ras/src/lib.rs` 的 `settle_volume_escrow` ⇒ 共识面 + 激活门 |
| **COW-2184** | 把硬编码的 `age=1` 换掉 | 链上根本没有分片龄数据（`RelayNodeProfile` 只有 `shards_held` + 中继自身 epoch）⇒ 结构编解码变更 + 迁移 |
| **COW-1575 / 1578** | 补几个常量 | `EGRESS_FEE_PER_BYTE` / `MAX_CPU_MILLICORES` 全仓零命中，**计量点本身不存在** |
| **COW-2113 / 2152** | 加两道校验 | 提交指令线格式里没有可校验的数据，要先加清单差分见证。XL，且两条必须同一次线格式变更一起做 |
| **COW-2915** | 生成一把多签密钥 | 技术侧确实小，但门限/签名人/托管要客户方定，且创世后不可补 |
| **COW-3087** | 提几个 registry PR | 工作量近零，但要等 COW-3086 / 3085 的 facade 在公网可答 `eth_chainId` |

---

## 5. 本文没有逐条评估的部分

107 条里，A/B 级之外的绝大多数在 `2026-08-06_Issue_Difficulty_Assessment_CN.md` 里已有 M/L/XL 评级（并在 08-07 / 08-11 两轮里多条从 S 降为 M），本文不重复。**没有单独评级**的是 08-18 新开那批里的重活：COW-3260（pre-auth QUIC 内存边界）、3263（root placement 进提交原子性）、3264（FUSE writer fencing / rebase）、3266（增量 scrub）、3267（分块流式写）、3268（prune gap 对账）、3269（原子容量预留 + 累计配额）、3270（`path_prefix` 授权边界）、3274（写截止 + 耐久 quorum）、3275/3276（release-key 与中继身份认证）、3277（placement tombstone）——这些是设计题，不是快赢。

---

## 附录 A：当期可动 107 条

口径：CIP projects · assignee = pavilionledger 或 无人 · 未完成未取消 · 已剔除 CIP-21/22（十一月递延 50 条）与 8 条外部前置缺失。数据时点 2026-08-18。

| Issue | CIP | 归属 | 状态 | 创建 | 标题 |
|---|---|---|---|---|---|
| COW-1377 | CIP-2 | 我方 | Backlog | 2026-05-31 | §8 'Aggregator collects result_bytes via direct HTTP push' + |
| COW-2109 | CIP-2 | 无人 | Backlog | 2026-06-01 | Activate 50/30/20 slash split + wire challenger payout + fix the split-value inconsistency |
| COW-962 | CIP-2 | 我方 | Todo | 2026-05-26 | [Node] Dispute window: on-chain challenge / evidence / re-verification handler |
| COW-1274 | CIP-5 | 我方 | Todo | 2026-05-27 | Architectural: decouple timer execution from propose's critical path |
| COW-2824 | CIP-6 | 我方 | Backlog | 2026-07-27 | [SDK] Guard verification is inert for every compiled FSM actor — guard_keys never reaches save_ |
| COW-987 | CIP-6 | 无人 | Backlog | 2026-05-26 | [SDK] Actor-side runtime.mount(volume_id, access_mode) for CBFS workflows |
| COW-1012 | CIP-8 | 无人 | Backlog | 2026-05-26 | [Node/Runner] Pin production COWBOY_SESSION_CHAIN_ID |
| COW-1542 | CIP-8 | 无人 | Backlog | 2026-05-31 | §6.4/§16 SessionAsset::Cip20 token-escrow path |
| COW-1543 | CIP-8 | 我方 | Backlog | 2026-05-31 | §4/§5 Runner session bootstrap relies on a PoC /session/observe HTTP push |
| COW-2099 | CIP-9 | 我方 | Backlog | 2026-06-01 | [CIP-9] Rewrite epic: triage grounded findings from mesa bring-up (cip-9-rewrite-ideas.md) |
| COW-2113 | CIP-9 | 我方 | Todo | 2026-06-02 | [Node] Public-volume commit prefix-confinement check |
| COW-2152 | CIP-9 | 无人 | Backlog | 2026-06-04 | [Node] Validate per_relay_effective_deltas at commit (caller-trust blast radius) |
| COW-2184 | CIP-9 | 无人 | Backlog | 2026-06-05 | CBFS: full relay rewards distribution (pro-rata by shard count x age) |
| COW-2300 | CIP-9 | 我方 | Backlog | 2026-06-16 | [HIGH][cbfs] `AuditGetShard` returns full shard bytes with zero request authentication |
| COW-2623 | CIP-9 | 无人 | Backlog | 2026-07-13 | COW-918 follow-up: batch/pipeline PoR response submission to restore open-challenge cap |
| COW-2829 | CIP-9 | 我方 | Backlog | 2026-07-28 | [Spec/Node] CIP-9 §7 — elevate volume access to first-class access classes |
| COW-2831 | CIP-9 | 我方 | Backlog | 2026-07-28 | [CBFS] Zero-config CBFS client — full chain-discovery bootstrap |
| COW-2832 | CIP-9 | 我方 | Backlog | 2026-07-28 | [Node/Runner] Runner↔validator version & tx-format compatibility negotiation |
| COW-2833 | CIP-9 | 我方 | Backlog | 2026-07-28 | [CBFS] Long-lived write cap tokens for large streaming writes |
| COW-3022 | CIP-9 | 无人 | Todo | 2026-08-06 | [CBFS] PutShard acks before the shard is durable → torn commits |
| COW-3023 | CIP-9 | 无人 | Todo | 2026-08-06 | [CBFS] node blob_http store also acks before durable |
| COW-3024 | CIP-9 | 无人 | Backlog | 2026-08-06 | [CBFS] Consolidate relay sled DBs into one Db + Trees for cross-store atomicity |
| COW-3025 | CIP-9 | 无人 | Backlog | 2026-08-06 | [CBFS] Manifest node wire format is not forward-compatible — salvage needs version archaeology |
| COW-3027 | CIP-9 | 无人 | Backlog | 2026-08-06 | [CBFS] Benchmark the data plane vs S3/Storj + capture shard-size distribution |
| COW-3028 | CIP-9 | 无人 | Backlog | 2026-08-06 | [CBFS] Verify the standalone (no-Cowboy) on-ramp works for an outside user |
| COW-3029 | CIP-9 | 无人 | Backlog | 2026-08-06 | [CBFS] Shard blob store: move to plain files (git-style), not another KV |
| COW-3036 | CIP-9 | 无人 | Todo | 2026-08-07 | [CBFS] Decide and enforce sync-daemon semantics under a write-only volume grant |
| COW-3037 | CIP-9 | 无人 | Todo | 2026-08-07 | [CBFS] FUSE `access()` handler ignores its mask |
| COW-3039 | CIP-9 | 无人 | Todo | 2026-08-07 | [CBFS] chmod on a partially-granted mount silently preserves bits it cannot see — decide vs POS |
| COW-3040 | CIP-9 | 无人 | Backlog | 2026-08-07 | [CBFS] setattr stores synthesized uid/gid/times verbatim — host-local values reach the content- |
| COW-3053 | CIP-9 | 无人 | Backlog | 2026-08-07 | [CBFS] Single-writer volumes — revisit the constraint |
| COW-3131 | CIP-9 | 无人 | Todo | 2026-08-11 | [Runner] access_mode is read two opposite ways — unknown mode string is writable to the mounter |
| COW-3148 | CIP-9 | 无人 | In Review | 2026-08-12 | [CBFS/Spec] Public manifest nodes are shared across volumes with no volume binding — purging on |
| COW-3149 | CIP-9 | 无人 | Todo | 2026-08-12 | [CBFS] GET_MANIFEST ships without manifest_root, its verifying client path is dead, and public  |
| COW-3151 | CIP-9 | 无人 | Backlog | 2026-08-12 | [CBFS] Placement gossip does not pin volume_id, and repair re-binds from it — a swapped record  |
| COW-3168 | CIP-9 | 无人 | Todo | 2026-08-13 | [Node] A garbage-collected volume stays in the PoR challenge universe forever — three challenge |
| COW-3169 | CIP-9 | 无人 | Backlog | 2026-08-13 | [Node/Spec] VOLUME_DELETE_GRACE_EPOCHS does not exist — the undelete window is at most one epoc |
| COW-3170 | CIP-9 | 无人 | Backlog | 2026-08-13 | [Node] /ras/tokens/validate has no volume-status check — a runner token still reads a DELETED v |
| COW-3171 | CIP-9 | 无人 | Backlog | 2026-08-13 | [CBFS] Orphan GC observability: a fail-closed gate that stays closed is invisible |
| COW-3259 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Fail closed on standalone volume reopen and persist key state atomically |
| COW-3260 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS][Security] Bound pre-auth QUIC memory and slow-read exposure |
| COW-3261 | CIP-9 | 无人 | Backlog | 2026-08-18 | [Runner/CBFS] Fail jobs when volume finalization fails and return committed roots |
| COW-3262 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Encode repair replacement uploads through the production PutShard wire |
| COW-3263 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Make root placement discoverability part of commit atomicity |
| COW-3264 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Fence FUSE writers or rebase root conflicts without a permanent wedge |
| COW-3265 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Store plaintext and ciphertext lengths separately |
| COW-3266 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Replace full-payload repair probes with a bounded incremental scrub |
| COW-3267 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Chunk and stream object writes so the advertised max size is representable |
| COW-3268 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Reconcile pruned volume-event gaps before GC |
| COW-3269 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Reserve capacity atomically and enforce cumulative capability quotas |
| COW-3270 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Make path_prefix an enforceable relay authorization boundary |
| COW-3271 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Supervise safety loops and derive readiness from real state |
| COW-3272 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS][Security] Parse CBFS_ACCEPT_ALL_AUTH as an explicit boolean |
| COW-3273 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS][Security] Preserve requested access mode across mount token refresh |
| COW-3274 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Add write deadlines, alternate placement, and an explicit durability quorum |
| COW-3275 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS/CBSS][Security] Authenticate release-key and relayer discovery against finalized state |
| COW-3276 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS][Security] Channel-bind relay identity and persist transport trust |
| COW-3277 | CIP-9 | 无人 | Backlog | 2026-08-18 | [CBFS] Add placement tombstones and bounded lifecycle indexes |
| COW-927 | CIP-9 | 我方 | Backlog | 2026-05-26 | [Node] POST /ras/challenge endpoint + chain-state challenge records |
| COW-1575 | CIP-10 | 无人 | Backlog | 2026-05-31 | §12.2 image-pull egress fees (pull_cost = size * EGRESS_FEE_PER_BYTE |
| COW-1578 | CIP-10 | 无人 | Backlog | 2026-05-31 | §13 parameter set (MAX_CPU_MILLICORES |
| COW-2506 | CIP-10 | 无人 | Backlog | 2026-07-06 | CIP-10: GPU billing + scheduling |
| COW-2507 | CIP-10 | 无人 | Backlog | 2026-07-06 | CIP-10: networked containers + egress accounting/billing |
| COW-1720 | CIP-16 | 无人 | Backlog | 2026-05-31 | §10/§7 Gateway resolution & serving policy (ACTIVE-only |
| COW-1721 | CIP-16 | 无人 | Backlog | 2026-05-31 | §7.3 verified_fqdn + namespace_kind injection into HttpRequestEnvelope by |
| COW-1722 | CIP-16 | 无人 | Backlog | 2026-05-31 | §10.3/§7.4 first-party TLD DNS authority serving from Route Registry |
| COW-1184 | CIP-18 | 无人 | Backlog | 2026-05-26 | [Node/Runner] EVM bridge facilitator: bridge.facilitate.evm entitlement + BridgeEvidence + cred |
| COW-1761 | CIP-19 | 无人 | Backlog | 2026-05-31 | §7 `ingress.mcp` entitlement id with params (server_name |
| COW-1774 | CIP-19 | 无人 | Backlog | 2026-05-31 | §10.3 Input schema derivation from path params + OpenAPI doc |
| COW-1788 | CIP-19 | 无人 | Backlog | 2026-05-31 | §14.3 Per-actor tool-list cache keyed by (actor |
| COW-1073 | CIP-20 | 我方 | Backlog | 2026-05-26 | [Spec] Bridge / lock-and-mint CIP for ETH ↔ Cowboy L1 (blocking $COWBOY Aug 2026 launch) |
| COW-1082 | CIP-20 | 我方 | Backlog | 2026-05-26 | [Explorer] Token balance + transfer history UI |
| COW-1798 | CIP-20 | 无人 | Backlog | 2026-05-31 | ICIP20Actor actor-token interface / actor-based tokens (fee-on-transfer |
| COW-2826 | CIP-20 | 我方 | Backlog | 2026-07-28 | [Node/Spec] CIP-20 on-chain allowance/spender secondary index (re-scope of COW-1083) |
| COW-3089 | CIP-20 | 我方 | Backlog | 2026-08-08 | CIP-20 holder enumeration — index or preimage-scan (blocked by COW-3090) |
| COW-1103 | CIP-23 | 我方 | Backlog | 2026-05-26 | [Node] Attestation-first runner registration (registry → 0x05::VerifyCae cross-call) |
| COW-2671 | CIP-24 | 无人 | Backlog | 2026-07-15 | Add authenticated evidence for CBSS threshold-wide withholding |
| COW-3092 | CIP-24 | 无人 | Backlog | 2026-08-08 | Add atomic GrantSecretActor instruction to CBSS |
| COW-1122 | CIP-25 | 无人 | Todo | 2026-05-26 | [Runner] Runner job type `generate_inclusion_proof` (third-party proof service) |
| COW-1896 | CIP-25 | 我方 | Todo | 2026-05-31 | §1.4/§1.5/§A.5 ZK light-client backend |
| COW-1897 | CIP-25 | 我方 | Todo | 2026-05-31 | §1.4/§A.5 Optimistic backend with challenger bonds/incentives |
| COW-1899 | CIP-25 | 我方 | Backlog | 2026-05-31 | §1.6 Multi-destination cost reduction |
| COW-1900 | CIP-25 | 无人 | Backlog | 2026-05-31 | §1.3 state_root / parent_hash commitment fields |
| COW-1901 | CIP-25 | 我方 | Todo | 2026-05-31 | §2.5/§2.6 Cross-chain streaming |
| COW-3012 | CIP-25 | 无人 | Backlog | 2026-08-06 | Native-LC: activation height gates the node but not the relayer — backend=1 is live on deploy |
| COW-3122 | CIP-25 | 无人 | Backlog | 2026-08-10 | CIP errata: §9.4 and §8.1 no longer match the code (exclusion widened, MRU banner false) |
| COW-1139 | CIP-28 | 无人 | Backlog | 2026-05-26 | [Node] Emit nine event types (CardIssued, CardDeposited, CardWithdrawn, GasCharged, Frozen, Unf |
| COW-1902 | CIP-28 | 无人 | Backlog | 2026-05-31 | §1.3 New tx-level field tx.fee_payer_override |
| COW-1904 | CIP-28 | 无人 | Backlog | 2026-05-31 | §2.7/§4.1 fee_payer resolution fork (card-address lookup → |
| COW-1911 | CIP-28 | 无人 | Backlog | 2026-05-31 | §4.5 BankErr error family + engine ErrorMap (CardNotFound |
| COW-1147 | CIP-29 | 无人 | Backlog | 2026-05-26 | [Node] Receipt schema: triggered_by_emit field for async causality correlation |
| COW-1152 | CIP-29 | 无人 | Backlog | 2026-05-26 | [Node/SDK] Payload schema validation at emit + subscribe time |
| COW-1917 | CIP-29 | 我方 | Backlog | 2026-05-31 | §2.1/§2.4 EmitResult return value NOT surfaced |
| COW-2884 | CIP-29 | 无人 | Backlog | 2026-07-31 | [Node] CIP-29 §2.3 gas isolation not enforced for cells in async event-fire (emitter pays subsc |
| COW-1277 | CIP-30 | 我方 | Backlog | 2026-05-27 | [Node] state_set / state_delete recompute storage_root in cross-call write-set |
| COW-1280 | CIP-30 | 无人 | Backlog | 2026-05-27 | [Node] Gas formula for trie updates: deterministic, bounded cost per state_set / state_delete |
| COW-1281 | CIP-30 | 无人 | Backlog | 2026-05-27 | [Node] fork() O(1) clone: child.storage_root = parent.storage_root (replaces enumeration stopga |
| COW-1282 | CIP-30 | 无人 | Backlog | 2026-05-27 | [Node/RPC] Expose per-actor proof endpoint: `GET Actor.storage_root` + opens against subtree |
| COW-1285 | CIP-30 | 无人 | Backlog | 2026-05-27 | [Tooling] Pre-image table for hashed long keys (debugger / explorer enumeration) |
| COW-2896 | CIP-31 | 无人 | Backlog | 2026-08-01 | CBFS registry-proto bills from the compile-time fee const, not the governance param |
| COW-2914 | CIP-31 | 无人 | Backlog | 2026-08-02 | Rename fee_split.burn_bps -> treasury_bps (and cbqs.rent.burn_bps) |
| COW-2915 | CIP-31 | 无人 | Backlog | 2026-08-03 | Platform Fee Account (0x18): generate the multisig owner key before genesis |
| COW-3052 | CIP-39 | 无人 | Todo | 2026-08-07 | pvm-ipc does not compile on macOS |
| COW-3085 | CIP-40 | 无人 | Backlog | 2026-08-08 | Flag-day chain-id cutover: retire chain_id=1, assign canyon 26901 / mesa 26909 |
| COW-3086 | CIP-40 | 无人 | Backlog | 2026-08-08 | Ethereum facade: POST /eth JSON-RPC stub on node RPC |
| COW-3087 | CIP-40 | 无人 | Backlog | 2026-08-08 | Registry PRs to ethereum-lists/chains (mesa 26909, prairie 26900, mainnet 2690) |
| COW-3088 | CIP-40 | 无人 | Backlog | 2026-08-08 | Prairie: public testnet bring-up |
---

## 附录 B：复现方法

```python
# LINEAR_API_KEY 在 ~/.claude/settings.json 的 env 里
# 1) 取 initiative "Validator / Whitepaper / CIPs" 下的 41 个 project
# 2) 每个 project 拉 issues，filter: {state:{type:{nin:["completed","canceled"]}}}
# 3) 过滤 assignee == null || "pavilionledger"，且 project.name 以 "CIP-" 开头
# 4) 剔除 CIP-21 / CIP-22 与 8 条外部前置缺失
```

报告本身的口径写在 HTML 末尾：*"left = in progress + todo; completion rate = completed ÷ (total − canceled)"*，
且明确排除 6 个不在该 initiative 内的 CIP（27 / 33 / 34 / 35 / 36 / 39 —— 其中 CIP-39 自本期起纳入，只剩 COW-3052 一条属我方）。

---

# 附录 C：D 级 104 条 —— 从易到难排序（2026-08-19）

**口径**：这 104 条已经是「无指派 或 指派 pavilionledger」过滤后的全集（Backlog 93 / Todo 10 / In Review 1；无人 81 / pavilionledger 23）。
**证据强度**：只有 D1 里被标 ✔ 的少数几条我在 A/B/C 轮里顺手核过代码；**其余全部是按标题+描述+所在子系统推断的**，没有逐条落到 file:line。
按 C 级那轮的经验（7 条候选里 2 条已被别的 PR 修掉、1 条其实是新建），**真开工时会有几条掉进「陷阱」栏**。

## D1 — 直接可做（单点 / 配置 / 决策题，当天可完）9 条

| # | Issue | CIP | 为什么易 |
|---|-------|-----|---------|
| 1 | COW-3303 | 39 | loopback 判定用字符串前缀 → 结构化解析 URL + 拒 userinfo。单函数 + 表驱动测试，与 A 级 `resolve_accept_all_auth` 同形 |
| 2 | COW-3301 | 39 | 18 条 fault-injection 测试**已存在**，只是被 CI 默认排除 → 改 workflow + 让期望测试数可见 |
| 3 | COW-3302 | 39 | cbqs-demo 报告了错误却 `return success` → fail-closed + 加阈值常量 |
| 4 | COW-3293 | 39 | readiness 只查链可达 → 把已被吞掉的 storage / Fast-flush 错误暴露出来 |
| 5 | COW-3304 | 39 | 纯文档：协议版本、cbqs-client、broker endpoint 与实际支持面对齐 |
| 6 | COW-2896 | 31 | `registry-proto` 用编译期常量 450 计费、node 用治理参数 → 改读治理参数。**先确认这条路径活着**，否则是死码（等价变异） |
| 7 | COW-3039 | 9 | chmod 部分授权保留看不见的位 —— 产出是决策 + 一段 spec + 一个 guard |
| 8 | COW-3036 | 9 | write-only grant 下 sync daemon 语义 —— 同上，规格题不是缺守卫 |
| 9 | COW-2915 | 31 | 0x18 多签 owner key 在 genesis 前生成 —— 运维仪式，不是代码，但有时间窗 |

## D2 — 单仓局部加固（改点清楚、能写测试、不碰共识面）28 条

**CBQS 边界 / 安全（7）**：COW-3294 pending session 无上限无过期 · COW-3298 WS 帧上限/握手 deadline/idle/连接上限 · COW-3295 README 承诺 e2e 但 `Session::append` 送明文 · COW-3288 retention 只扫看得见的 lane · COW-3291 replay 停在 1024 就切 live（签名链断口）· COW-3296 client 重连/超时/订阅恢复 · COW-3297 typed Standard consumer API（量大但机械）

**CBFS 边界 / 安全（7）**：COW-3260 5 字节声明 256 MiB → 先认证再大分配 · COW-3269 容量 read-then-write 且 fail-open + 配额只按单请求 · COW-3277 移除的 shard 无 tombstone · COW-3266 每 5 分钟全量 hash 当存活探针 → 有界增量 scrub · COW-3271 metering 写死 health、四个安全循环无监督 · COW-3276 TLS pin 只在内存 → channel-bind · COW-3270 cap token 带 path_prefix 但 shard RPC 拿不到 object path

**CBFS 正确性（4）**：COW-3263 root placement 可发现性进 commit 原子性 · COW-3264 stale root 冲突永久卡死 FUSE · COW-3268 剪枝推进 cursor 却重建不了 horizon 以下 · COW-3265 密文长度被当文件长度（会动 `ObjectDescriptor`，与 COW-3025 耦合）

**node / runner（8）**：COW-2623 PoR 响应批量提交 · COW-2832 runner↔validator 版本协商 · COW-1152 emit/subscribe payload schema 校验 · COW-1911 BankErr 错误族 + ErrorMap · COW-1139 BankActor 九个事件（**若 BankActor 已上链则升 D3**）· COW-1543 CIP-8 PoC HTTP push → 链事件订阅 · COW-1542 SessionAsset::Cip20 escrow 接线 · COW-1122 `generate_inclusion_proof` runner job（可复用现有 `/proof/*`）

**工具 / 测量（2）**：COW-1285 hashed 长 key 的 pre-image 表 · COW-3027 数据面 benchmark vs S3/Storj（工程量在测量不在改码）

## D3 — 改点可能不大，但踩共识面 / 治理 / 被阻塞 22 条

| Issue | CIP | 卡在哪 |
|-------|-----|--------|
| COW-2914 | 31 | `burn_bps`→`treasury_bps`：**治理键名改名 = 共识变更**，要 flag-day |
| COW-1012 | 8 | pin 生产 session chain id —— 两个常量，但与 COW-3085 cutover 耦合 |
| COW-2109 | 2 | 激活 50/30/20 slash split + challenger payout：默认值改动 = 共识 |
| COW-2152 | 9 | commit 校验 `per_relay_effective_deltas`（caller-trust 爆炸半径） |
| COW-2113 | 9 | public volume commit 前缀 confinement |
| COW-3169 | 9 | `VOLUME_DELETE_GRACE_EPOCHS` 根本不存在，undelete 窗口最多一个 epoch |
| COW-3168 | 9 | GC 掉的 volume 永远留在 PoR 挑战宇宙（三选一，本条最大） |
| COW-1147 | 29 | receipt 加 `triggered_by_emit` → receipt schema 进 root |
| COW-2884 | 29 | §2.3 cells gas isolation 未强制，**已在 devnet 活着** |
| COW-1917 | 29 | `emit_event` 返回值没露出来 —— 动 pvm_host + `runtime.py`（冻结 SDK 面） |
| COW-2824 | 6 | `guard_keys` 从不到达编译后的 FSM actor —— 修在冻结 SDK 里 = 共识 |
| COW-2826 | 20 | allowance 次级索引：原 ask 不可实现，要重设 key 布局 |
| COW-3089 | 20 | holder 枚举 —— **被 COW-3090 阻塞** |
| COW-1798 | 20 | ICIP20Actor scaffold —— 要先定 runtime 接口 |
| COW-3148 | 9 | 公开 manifest node 跨 volume 共享无 volume 绑定（有实证数据问题） |
| COW-2184 | 9 | relay rewards pro-rata —— 动奖励分配 = 共识 |
| COW-927 | 9 | `POST /ras/challenge` + 链上 challenge record：树里零引用，等于新建 |
| COW-3092 | 24 | 原子 `GrantSecretActor` 指令 —— 新指令 = 共识 |
| COW-1900 | 25 | `IChainAnchor.commitment` 加 state_root/parent_hash —— 已部署接口要版本化 |
| COW-1103 | 23 | attestation-first 注册（registry → `0x05::VerifyCae`）= 改注册流程 |
| COW-1082 | 20 | explorer token UI —— **被事件发射阻塞** |
| COW-3087 | 40 | ethereum-lists/chains PR —— **被「facade 公网能答 eth_chainId」阻塞**（registry CI 真去打 RPC） |

## D4 — 新建子系统 / 跨仓协调 / 架构决策 45 条

- **CIP-30 每-actor storage_root（4，最大一块）**：COW-1277 write-set 维护 root · COW-1280 trie 更新 gas 公式 · COW-1281 `fork()` O(1) clone · COW-1282 per-actor proof RPC
- **CIP-25 跨链（4）**：COW-1896 ZK backend · COW-1897 optimistic + bond 经济 · COW-1899 BLS 聚合 / BroadcastRelay / threshold-ECDSA · COW-1901 跨链 streaming
- **CIP-28 fee_payer（2）**：COW-1902 新 tx 顶层字段 · COW-1904 fee 结算分叉（tx wire + flag-day）
- **CIP-16 Gateway（3）**：COW-1720 解析/serving policy · COW-1721 `verified_fqdn` 注入 · COW-1722 first-party TLD DNS —— 树里没有 Gateway
- **CIP-19 ingress.mcp（3）**：COW-1761 entitlement id · COW-1774 schema 派生 · COW-1788 tool-list 缓存 —— entitlement 系统本身要先有
- **CIP-10 容器（4）**：COW-1575 image-pull egress 计费 · COW-1578 参数集 · COW-2506 GPU 排程/计量 · COW-2507 网络容器 + egress 计费
- **CIP-2（2）**：COW-962 争议/挑战 handler · COW-1377 designated aggregator 离链收集
- **桥（2）**：COW-1184 EVM bridge facilitator · COW-1073 bridge CIP 规格（挡 $COWBOY 2026-08 上线）
- **CIP-6 / CIP-5（2）**：COW-987 `runtime.mount` · COW-1274 timer 脱离 propose 关键路径（架构 + 共识）
- **CBQS 平台级（5）**：COW-3289 retained_bytes 原子记账 · COW-3290 durable broker catalog · COW-3292 有界 storage executor · COW-3299 复制/fencing/failover · COW-3300 迁移/checkpoint/rollback 工具
- **CBFS 平台级（10）**：COW-3024 合并 sled DB · COW-3025 manifest wire 版本化（salvage 要精确 revision）· COW-3029 shard 存平文件 · COW-3053 single-writer 限制 · COW-3267 分块流式写 · COW-3274 写 deadline + durability quorum · COW-3275 release-key/relayer 发现对最终化状态验证 · COW-2829 access class 一级化 · COW-2831 零配置引导 · COW-2833 长效写 cap token
- **CBSS（1）**：COW-2671 threshold-wide withholding 的可归责证据（设计题）
- **网络 / 基建（2）**：COW-3085 chain-id flag-day cutover（跨仓：genesis + terraform + CBFS relay）· COW-3088 Prairie 公网测试网
- **伞票（1）**：COW-2099 CIP-9 rewrite epic —— 先拆票，不直接做
