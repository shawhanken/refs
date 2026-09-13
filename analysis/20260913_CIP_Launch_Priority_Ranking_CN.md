# CIP 当期可推进 Issue · 按上线优先级排序

- **数据时点：2026 年 09 月 13 日 17:55（北京时间）**
- 范围：负责人为我方或尚未指派、且当期可推进的 65 条，与 `20260913_CIP_Ours_And_Unassigned_Issues_CN.md` 同一份清单。
- 已扣除：外部条件未具备 8 条、已判定为发币之后处理 73 条、客户方名下的 Issue。

## 排序标准

这一版的标准就是这次要上线的四个系统——Homestead、Cowchat、Marshal、Watchtower——能不能按时上线、上线之后会不会出事。和这次移出 Post launch 用的是同一把尺子：一条 Issue 要防的事在「所有节点、runner、中继都由我方运行，没有外部参与者」这个条件下会不会发生，四个应用的数据面走不走这条路。

分五档：10 条 P0、15 条 P1、26 条 P2、11 条 P3、3 条等决定。同一档之内，在办的（In Progress / In Review / Todo）排在 Backlog 前面，然后按 CIP 编号。

Linear 自带的 priority 字段没有参与排序：工作区里大部分条目没填，而未填在 Linear 里记作 0，直接按它排会把没填的顶到最前面。

「本周期排入」这一列对应 9 月 14 日至 16 日那份计划里的 17 项：P0 十条全部排入，另有 6 条 P1 与 1 条等决定。列里写的是这条在计划中的动作标注。


## P0 · 10 条

**上线阻塞**：不做就上不了线，或者一上线就会出事。创世参数、共识正确性，以及四个应用的数据面上已经证实的缺陷。

| # | Issue | CIP | 状态 | 归属 | 本周期排入 | 为什么排在这一档 | 标题 |
|---:|---|---|---|---|---|---|---|
| 1 | [COW-3337](https://linear.app/cowboy-labs/issue/COW-3337/block-digest-preimage-is-non-injective-one-finality-signature-vouches) | CIP-25 | In Review | 我方 | 是 · PR 等合并 | 区块摘要原像不唯一，一个最终性签名能同时为两个不同区块背书，属共识正确性，PR 在审 | Block digest preimage is non-injective — one finality signature vouches for two different blocks |
| 2 | [COW-2622](https://linear.app/cowboy-labs/issue/COW-2622/volume-create-succeeds-with-0-relays-when-auto-assign-cant-satisfy-km) | CIP-9 | Todo | 我方 | 是 · 开始动手 | 中继数不够也能建出卷，卷不可用且押金卡住；创世重置后中继注册表是空的，一上来就会踩 | volume create succeeds with 0 relays when auto-assign can't satisfy k+m — unusable volume, stuck escrow |
| 3 | [COW-3586](https://linear.app/cowboy-labs/issue/COW-3586/cbsssecurityhigh-f-c-2-the-release-request-is-a-transferable-bearer) | CIP-24 | Todo | 我方 | 是 · 开始动手 | 释放请求是谁拿到都能用的通行凭据，旁观者可自行凑齐法定人数完成释放 | [CBSS][Security][High] F-C-2: the release request is a transferable bearer credential — an observer can self-a |
| 4 | [COW-3585](https://linear.app/cowboy-labs/issue/COW-3585/cbsssecurityhigh-f-c-1-a-chain-observer-can-reconstruct-the-dek-of-any) | CIP-24 | Todo | 我方 | 是 · 开始动手 | 链上观察者仅凭公开数据就能还原任意已释放版本的数据加密密钥 | [CBSS][Security][High] F-C-1: a chain observer can reconstruct the DEK of any released secret version from pub |
| 5 | [COW-3584](https://linear.app/cowboy-labs/issue/COW-3584/cbsssecuritycritical-f-i-1-reshare-accepts-the-threshold-from-the-wire) | CIP-24 | Todo | 我方 | 是 · 开始动手 | CBSS 重分享采信数据包里的门限值，t-of-n 可被静默压成 1-of-n 且不可撤销，私有卷的托管根基 | [CBSS][Security][Critical] F-I-1: reshare accepts the threshold from the wire payload — a t-of-n key can silen |
| 6 | [COW-4023](https://linear.app/cowboy-labs/issue/COW-4023/cbfs-concurrent-opens-intermittently-see-manifest-node-placement) | CIP-9 | Backlog | 无主 | 是 · 开始动手 | 多进程并发打开同一个卷偶发失败且十几秒重试不恢复，表现就是用户打不开文档，9/11 四次跑批命中三次 | CBFS: concurrent opens intermittently see `manifest node placement unavailable` for a just-committed root |
| 7 | [COW-4022](https://linear.app/cowboy-labs/issue/COW-4022/node-owner-volume-gets-serve-the-raw-commitment-behind-a-delegation) | CIP-9 | Backlog | 无主 | 是 · 开始动手 | 抓到一次委托请求头重放就能拿到包好的数据密钥，Homestead 每个用户的私有卷都在这条路径上 | node: owner volume GETs serve the raw commitment behind a delegation-cert-only check |
| 8 | [COW-3460](https://linear.app/cowboy-labs/issue/COW-3460/proveshard-authorizes-with-volume-idnone-cross-tenant-shard-read) | CIP-9 | Backlog | 我方 | 是 · 开始动手 | ProveShard 不带卷号做授权，可以读到别的卷的分片，Homestead 是多用户共用一套中继 | ProveShard authorizes with volume_id=None — cross-tenant shard read |
| 9 | [COW-2915](https://linear.app/cowboy-labs/issue/COW-2915/platform-fee-account-0x18-generate-the-multisig-owner-key-before) | CIP-31 | Backlog | 无主 | 是 · 先要结论 | 平台费账户 0x18 的多签密钥必须在创世之前生成，下一次重建创世前拿不到就没法开链 | Platform Fee Account (0x18): generate the multisig owner key before genesis |
| 10 | [COW-3085](https://linear.app/cowboy-labs/issue/COW-3085/flag-day-chain-id-cutover-retire-chain-id1-assign-canyon-26901-mesa) | CIP-40 | Backlog | 无主 | 是 · 先要结论 | 链 ID 切换是随创世重置一次做完的动作，牵动五处仓库的常量，晚做就要再来一次重置 | Flag-day chain-id cutover: retire chain_id=1, assign canyon 26901 / mesa 26909 |

## P1 · 15 条

**上线前应当做完**：上线能跑起来，但这些问题四个应用会真的踩到，或者暴露面大到不该带着上线。

| # | Issue | CIP | 状态 | 归属 | 本周期排入 | 为什么排在这一档 | 标题 |
|---:|---|---|---|---|---|---|---|
| 11 | [COW-3336](https://linear.app/cowboy-labs/issue/COW-3336/cip-39protocol-canonicalize-provider-endpoint-scheme-casing-across) | CIP-39 | In Progress | 我方 | 是 · 本周期做完 | 协议层端点大小写的统一写法，五个 PR 已全部合入，只差置为完成 | [CIP-39][Protocol] Canonicalize provider endpoint scheme casing across admission and dialers |
| 12 | [COW-3365](https://linear.app/cowboy-labs/issue/COW-3365/skm-0x0d-unbounded-kv-growth-cross-tenant-griefing-exhausts-the-10k) | CIP-7 | Todo | 无主 | — | 密钥管理模块的键值行只写不删，同链其他租户能把每个 actor 一万个键的额度耗光，Watchtower 走这条路 | SKM (0x0D) unbounded KV growth + cross-tenant griefing exhausts the 10k actor-key cap |
| 13 | [COW-3168](https://linear.app/cowboy-labs/issue/COW-3168/node-a-garbage-collected-volume-stays-in-the-por-challenge-universe) | CIP-9 | Todo | 我方 | 是 · 开始动手 | 已回收的卷永远留在抽查范围里，连续三次不过就把一个诚实中继踢出去——踢的是我方自己的中继 | [Node] A garbage-collected volume stays in the PoR challenge universe forever — three challenges evict an hone |
| 14 | [COW-2113](https://linear.app/cowboy-labs/issue/COW-2113/node-public-volume-commit-prefix-confinement-check) | CIP-9 | Todo | 我方 | 是 · 继续推进 | 公开卷提交不校验改动路径是否在提交者的前缀内，只读写权限的持有者可以覆盖整份清单 | [Node] Public-volume commit prefix-confinement check |
| 15 | [COW-3591](https://linear.app/cowboy-labs/issue/COW-3591/cbsssecurity-f-s-1-the-cip-7cip-9-seal-path-lacks-the-account-paths) | CIP-24 | Todo | 我方 | — | CIP-7/CIP-9 的封装路径缺少独立复核，授权判断退化成自己和自己比 | [CBSS][Security] F-S-1: the CIP-7/CIP-9 seal path lacks the account path's independent re-verification |
| 16 | [COW-3588](https://linear.app/cowboy-labs/issue/COW-3588/cbssrunnersecurity-f-i-2-the-runners-chain-rpc-is-unvalidated-and-its) | CIP-24 | Todo | 我方 | 是 · 继续推进 | runner 的链上 RPC 不做校验，而它的响应是整条密钥释放链路的信任根 | [CBSS/Runner][Security] F-I-2: the runner's chain RPC is unvalidated, and its response feeds the entire releas |
| 17 | [COW-3587](https://linear.app/cowboy-labs/issue/COW-3587/cbsssecurity-f-c-3-one-authorization-replays-indefinitely-partialsign) | CIP-24 | Todo | 我方 | 是 · 继续推进 | 一次授权可以无限重放，去重键用的正是规格明令禁止的那一个 | [CBSS][Security] F-C-3: one authorization replays indefinitely — PartialSign dedup uses the key CIP-24 3.7 for |
| 18 | [COW-4024](https://linear.app/cowboy-labs/issue/COW-4024/ras-dek-rotation-instruction-rewrapvolume-keeps-the-dek-dek-version) | CIP-9 | Backlog | 无主 | — | 重新封装卷不换数据密钥，撤销一个直连客户端的授权之后对方手里的密钥仍然有效 | RAS: DEK rotation instruction (RewrapVolume keeps the DEK; dek_version never advances) |
| 19 | [COW-4021](https://linear.app/cowboy-labs/issue/COW-4021/cbfs-volume-bound-shard-ids-placement-store-collides-across-volumes) | CIP-9 | Backlog | 无主 | — | 分片编号只按内容推导，两个卷存了相同字节就会撞号、放置记录互相覆盖 | CBFS: volume-bound shard ids (placement store collides across volumes) |
| 20 | [COW-3599](https://linear.app/cowboy-labs/issue/COW-3599/noderas-duplicates-six-cbfs-proof-of-drain-digests-on-a-live-consensus) | CIP-9 | Backlog | 我方 | 是 · 继续推进 | 六个排空证明摘要域在共识可达路径上手抄了一遍，两份一旦不一致就静默分叉，且没有漂移检测 | node/ras duplicates six CBFS proof-of-drain digests on a live consensus path with no drift detector |
| 21 | [COW-3443](https://linear.app/cowboy-labs/issue/COW-3443/gate-the-write-relayer-api-key-cap-relayer-responses-json-path) | CIP-9 | Backlog | 我方 | — | 写中继的 API key 会明文发往非 TLS 地址，这把 key 是付手续费用的 | Gate the write-relayer API key + cap relayer responses (JSON path) |
| 22 | [COW-3274](https://linear.app/cowboy-labs/issue/COW-3274/cbfs-add-write-deadlines-alternate-placement-and-an-explicit) | CIP-9 | Backlog | 我方 | — | 写入要求 K+M 全部成功且不重试备选中继，一个慢中继就废掉纠删码的可用性 | [CBFS] Add write deadlines, alternate placement, and an explicit durability quorum |
| 23 | [COW-3264](https://linear.app/cowboy-labs/issue/COW-3264/cbfs-fence-fuse-writers-or-rebase-root-conflicts-without-a-permanent) | CIP-9 | Backlog | 我方 | — | FUSE 写者没有围栏，根冲突会永久卡死或静默丢更新，Homestead 的挂载走这条路 | [CBFS] Fence FUSE writers or rebase root conflicts without a permanent wedge |
| 24 | [COW-3263](https://linear.app/cowboy-labs/issue/COW-3263/cbfs-make-root-placement-discoverability-part-of-commit-atomicity) | CIP-9 | Backlog | 我方 | — | 根放置记录的可发现性不在提交的原子性之内，新读者可能打不开刚提交的清单，与 COW-4023 同源 | [CBFS] Make root placement discoverability part of commit atomicity |
| 25 | [COW-3088](https://linear.app/cowboy-labs/issue/COW-3088/prairie-public-testnet-bring-up) | CIP-40 | Backlog | 无主 | — | 公开测试网 Prairie 的拉起，属于上线动作本身，排期上跟着上线窗口走 | Prairie: public testnet bring-up |

## P2 · 26 条

**上线后短期必修**：不挡上线，但运维代价或暴露面会在上线后很快显出来。

| # | Issue | CIP | 状态 | 归属 | 本周期排入 | 为什么排在这一档 | 标题 |
|---:|---|---|---|---|---|---|---|
| 26 | [COW-3169](https://linear.app/cowboy-labs/issue/COW-3169/nodespec-volume-delete-grace-epochs-does-not-exist-the-undelete-window) | CIP-9 | Todo | 我方 | — | 规格承诺的删除宽限期在代码里不存在，撤销删除的窗口最多一个纪元且期间不计费 | [Node/Spec] VOLUME_DELETE_GRACE_EPOCHS does not exist — the undelete window is at most one epoch and fees do n |
| 27 | [COW-3149](https://linear.app/cowboy-labs/issue/COW-3149/cbfs-get-manifest-ships-without-manifest-root-its-verifying-client) | CIP-9 | Todo | 我方 | — | 取清单的接口没带清单根，校验型客户端那条路是死的，公开卷的鉴权与规格不一致 | [CBFS] GET_MANIFEST ships without manifest_root, its verifying client path is dead, and public auth diverges f |
| 28 | [COW-2670](https://linear.app/cowboy-labs/issue/COW-2670/sdk-shorthand-rw-volume-mounts-must-mint-nonzero-write-quota) | CIP-9 | Todo | 我方 | — | SDK 简写方式挂载的读写卷写入额度是 0，挂得上、读得到、写不进 | SDK shorthand RW volume mounts must mint nonzero write quota |
| 29 | [COW-3594](https://linear.app/cowboy-labs/issue/COW-3594/cbsssecurity-f-42-1-the-cip-42-operator-statusz-endpoint-is-bindable) | CIP-24 | Todo | 我方 | — | 运维状态接口可绑定到非本机地址且无任何认证 | [CBSS][Security] F-42-1: the CIP-42 operator statusz endpoint is bindable off-loopback with no authentication |
| 30 | [COW-3593](https://linear.app/cowboy-labs/issue/COW-3593/cbsssecurity-f-o-1-two-security-alert-metrics-are-structurally-always) | CIP-24 | Todo | 我方 | — | 两个安全告警指标结构性恒为零，另一个可被客户端笔误伪造出攻击信号 | [CBSS][Security] F-O-1: two security alert metrics are structurally always zero, and a third can be fabricated |
| 31 | [COW-3589](https://linear.app/cowboy-labs/issue/COW-3589/cbsssecurity-f-i-3-four-of-eight-authorization-guards-have-zero-test) | CIP-24 | Todo | 我方 | — | 八道授权守卫里有四道零测试覆盖，删掉它们持续集成照样全绿 | [CBSS][Security] F-I-3: four of eight authorization guards have zero test coverage (mutants survive the CI sui |
| 32 | [COW-3386](https://linear.app/cowboy-labs/issue/COW-3386/cbss-reshare-grace-window-is-unreachable-from-cbssd) | CIP-24 | Todo | 我方 | — | CBSS 的重分享宽限期链上支持、cbssd 到不了，退役周期的分片被立刻删掉 | CBSS reshare grace window is unreachable from cbssd |
| 33 | [COW-3440](https://linear.app/cowboy-labs/issue/COW-3440/enforce-authoritative-cbfs-account-and-volume-ceilings) | CIP-9 | Backlog | 我方 | — | 账户与卷的数量、大小上限在节点侧没有强制，白皮书 §1.4 要求的四个天花板缺三个 | Enforce authoritative CBFS account and volume ceilings |
| 34 | [COW-3439](https://linear.app/cowboy-labs/issue/COW-3439/protect-decrypted-cbfs-delegated-keys-in-memory) | CIP-9 | Backlog | 我方 | — | 解密后的委托密钥没有锁内存也没有禁核心转储，属纵深防御 | Protect decrypted CBFS delegated keys in memory |
| 35 | [COW-3277](https://linear.app/cowboy-labs/issue/COW-3277/cbfs-add-placement-tombstones-and-bounded-lifecycle-indexes) | CIP-9 | Backlog | 无主 | — | 删除的分片没有墓碑记录，修复与同步会无限扫描历史放置状态 | [CBFS] Add placement tombstones and bounded lifecycle indexes |
| 36 | [COW-3269](https://linear.app/cowboy-labs/issue/COW-3269/cbfs-reserve-capacity-atomically-and-enforce-cumulative-capability) | CIP-9 | Backlog | 我方 | — | 容量预留是先读后写、出错时放行，配额按单次请求而不是累计量算 | [CBFS] Reserve capacity atomically and enforce cumulative capability quotas |
| 37 | [COW-3268](https://linear.app/cowboy-labs/issue/COW-3268/cbfs-reconcile-pruned-volume-event-gaps-before-gc) | CIP-9 | Backlog | 我方 | — | 裁剪过的卷事件有空档，垃圾回收可能把已提交的分片收走或把已删的字节永久留下 | [CBFS] Reconcile pruned volume-event gaps before GC |
| 38 | [COW-3267](https://linear.app/cowboy-labs/issue/COW-3267/cbfs-chunk-and-stream-object-writes-so-the-advertised-max-size-is) | CIP-9 | Backlog | 我方 | — | 超过 256 MiB 的对象写入没有分块，1 GiB 私有对象会撑爆瞬时内存 | [CBFS] Chunk and stream object writes so the advertised max size is representable |
| 39 | [COW-3266](https://linear.app/cowboy-labs/issue/COW-3266/cbfs-replace-full-payload-repair-probes-with-a-bounded-incremental) | CIP-9 | Backlog | 无主 | — | 每五分钟的修复探测要扫完所有本地分片并从每个同伴拉整块，代价随数据量线性上升 | [CBFS] Replace full-payload repair probes with a bounded incremental scrub |
| 40 | [COW-3024](https://linear.app/cowboy-labs/issue/COW-3024/cbfs-consolidate-relay-sled-dbs-into-one-db-trees-for-cross-store) | CIP-9 | Backlog | 无主 | — | 中继开了三个各自独立的本地库，跨库没有事务，崩溃后状态可能互相对不上 | [CBFS] Consolidate relay sled DBs into one Db + Trees for cross-store atomicity |
| 41 | [COW-2623](https://linear.app/cowboy-labs/issue/COW-2623/cow-918-follow-up-batchpipeline-por-response-submission-to-restore) | CIP-9 | Backlog | 无主 | — | 存储证明应答没有批量提交，每个中继同时开着的挑战上限被迫从 64 降到 16 | COW-918 follow-up: batch/pipeline PoR response submission to restore open-challenge cap |
| 42 | [COW-927](https://linear.app/cowboy-labs/issue/COW-927/node-post-raschallenge-endpoint-chain-state-challenge-records) | CIP-9 | Backlog | 我方 | — | 存储服务的挑战应答端点与链上挑战记录缺失，重放保护靠它 | [Node] POST /ras/challenge endpoint + chain-state challenge records |
| 43 | [COW-3595](https://linear.app/cowboy-labs/issue/COW-3595/cbsssecurityinvestigation-f-a-16-f-o-2-adjudicate-the-seven) | CIP-24 | Backlog | 我方 | — | 七项未裁定的可用性与审计留痕问题，要逐条给出证明或否证 | [CBSS][Security][Investigation] F-A-1..6 + F-O-2: adjudicate the seven undetermined availability and audit-tra |
| 44 | [COW-3592](https://linear.app/cowboy-labs/issue/COW-3592/cbsssecurity-f-d-1-at-rest-share-key-is-colocated-with-the-identity) | CIP-24 | Backlog | 我方 | — | 静态存储的分片密钥与身份密钥同源，且实现与文档描述不符 | [CBSS][Security] F-D-1: at-rest share key is colocated with the identity keys, and the implementation contradi |
| 45 | [COW-3590](https://linear.app/cowboy-labs/issue/COW-3590/cbsssecurity-f-i-4-the-only-security-named-test-suite-is-largely) | CIP-24 | Backlog | 我方 | — | 仓库里唯一以对抗性命名的测试套件大量是恒真断言，0.017 秒跑完 | [CBSS][Security] F-I-4: the only security-named test suite is largely tautological |
| 46 | [COW-3092](https://linear.app/cowboy-labs/issue/COW-3092/add-atomic-grantsecretactor-instruction-to-cbss) | CIP-24 | Backlog | 无主 | — | 给 actor 授权密钥现在要读改写整份策略，有竞态；客户方的 Dashboard 在用这条路 | Add atomic GrantSecretActor instruction to CBSS |
| 47 | [COW-2671](https://linear.app/cowboy-labs/issue/COW-2671/add-authenticated-evidence-for-cbss-threshold-wide-withholding) | CIP-24 | Backlog | 无主 | — | 门限级别的集体扣留没有可归责的证据，出问题时无法认定是谁不干活 | Add authenticated evidence for CBSS threshold-wide withholding |
| 48 | [COW-2884](https://linear.app/cowboy-labs/issue/COW-2884/node-cip-29-23-gas-isolation-not-enforced-for-cells-in-async-event) | CIP-29 | Backlog | 无主 | — | 异步事件触发时按格计量没有隔离，发事件的一方替订阅方付了费用 | [Node] CIP-29 §2.3 gas isolation not enforced for cells in async event-fire (emitter pays subscriber cells) |
| 49 | [COW-1281](https://linear.app/cowboy-labs/issue/COW-1281/node-fork-o1-clone-childstorage-root-parentstorage-root-replaces) | CIP-30 | Backlog | 无主 | — | 状态树引擎：fork 现在靠枚举拷贝，长键哈希后根本枚举不全 | [Node] fork() O(1) clone: child.storage_root = parent.storage_root (replaces enumeration stopgap) |
| 50 | [COW-1280](https://linear.app/cowboy-labs/issue/COW-1280/node-gas-formula-for-trie-updates-deterministic-bounded-cost-per-state) | CIP-30 | Backlog | 无主 | — | 状态树引擎：树更新的燃料公式缺失，深树写入的成本无界 | [Node] Gas formula for trie updates: deterministic, bounded cost per state_set / state_delete |
| 51 | [COW-1277](https://linear.app/cowboy-labs/issue/COW-1277/node-state-set-state-delete-recompute-storage-root-in-cross-call-write) | CIP-30 | Backlog | 我方 | — | 状态树引擎：写入时不维护每个 actor 的状态承诺，CIP-27 的分叉也卡在它上面 | [Node] state_set / state_delete recompute storage_root in cross-call write-set |

## P3 · 11 条

**可以往后排**：质量、测试、文档，以及生效高度还关着、现在跑不到的那一块。

| # | Issue | CIP | 状态 | 归属 | 本周期排入 | 为什么排在这一档 | 标题 |
|---:|---|---|---|---|---|---|---|
| 52 | [COW-1115](https://linear.app/cowboy-labs/issue/COW-1115/node-fraud-proof-window-slashing-for-runner-committee-backend) | CIP-25 | In Review | 我方 | — | 委员会后端的欺诈证明窗口与罚没，PR 在审；跨链不在这次上线范围内 | [Node] Fraud-proof window + slashing for runner-committee backend |
| 53 | [COW-3471](https://linear.app/cowboy-labs/issue/COW-3471/remove-cip-16-docs-reconcile-cip-142122-deprecation) | CIP-14 | Todo | 无主 | — | 给四个废弃的 CIP 文档加废弃说明并写明移除日期与 PR 编号，文档收尾 | Remove CIP-16 docs; reconcile CIP-14/21/22 deprecation |
| 54 | [COW-3283](https://linear.app/cowboy-labs/issue/COW-3283/native-lc-one-malformed-result-aborts-committee-verification-for-the) | CIP-25 | Todo | 我方 | — | 一条格式错误的结果会让整批委员会校验失败；同上 | Native-LC: one malformed result aborts committee verification for the whole batch |
| 55 | [COW-3282](https://linear.app/cowboy-labs/issue/COW-3282/native-lc-receipt-proofs-attest-inclusion-but-not-completeness-a) | CIP-25 | Todo | 我方 | — | 原生轻客户端的回执证明只证包含不证完整，runner 可以漏报消息；同上，功能关着 | Native-LC: receipt proofs attest inclusion but not completeness — a runner can censor MessageSent logs |
| 56 | [COW-3258](https://linear.app/cowboy-labs/issue/COW-3258/native-lc-metering-activation-height-test-seam-and-lcstore-reset-path) | CIP-25 | Todo | 我方 | — | 原生轻客户端的计量、激活高度测试接缝与本地存储重置路径；同上 | Native-LC: metering, activation-height test seam, and lc:store reset path |
| 57 | [COW-3257](https://linear.app/cowboy-labs/issue/COW-3257/native-lc-split-the-stale-fault-class-so-an-honest-crash-attestation) | CIP-25 | Todo | 我方 | — | 原生轻客户端的故障分级倒挂；同上，功能关着 | Native-LC: split the Stale fault class so an honest crash attestation is not worse than revealing junk |
| 58 | [COW-3256](https://linear.app/cowboy-labs/issue/COW-3256/native-lc-retained-anchors-a-single-sliding-walk-anchor-strands-older) | CIP-25 | Todo | 我方 | — | 原生轻客户端的保留锚点问题；该功能的生效高度是最大值，现在跑不到 | Native-LC: retained anchors — a single sliding walk anchor strands older admitted jobs |
| 59 | [COW-1139](https://linear.app/cowboy-labs/issue/COW-1139/node-emit-nine-event-types-cardissued-carddeposited-cardwithdrawn) | CIP-28 | Backlog | 无主 | — | 按 §3.6 发卡片事件——核对后发现链上已经在发一整套，更像是已完成待核销，下期先做关闭核对 | [Node] Emit nine event types (CardIssued, CardDeposited, CardWithdrawn, GasCharged, Frozen, Unfrozen, PolicyUp |
| 60 | [COW-1917](https://linear.app/cowboy-labs/issue/COW-1917/2124-emitresult-return-value-not-surfaced) | CIP-29 | Backlog | 我方 | — | 发事件的返回值没有透出，调用方看不到同步结果与延迟订阅数 | §2.1/§2.4 EmitResult return value NOT surfaced |
| 61 | [COW-1152](https://linear.app/cowboy-labs/issue/COW-1152/nodesdk-payload-schema-validation-at-emit-subscribe-time) | CIP-29 | Backlog | 无主 | — | 发布与订阅两侧的载荷结构校验，两边编码不一致时现在是静默失败 | [Node/SDK] Payload schema validation at emit + subscribe time |
| 62 | [COW-1147](https://linear.app/cowboy-labs/issue/COW-1147/node-receipt-schema-triggered-by-emit-field-for-async-causality) | CIP-29 | Backlog | 无主 | — | 回执里缺少与触发它的事件之间的关联字段，异步链路排查不便 | [Node] Receipt schema: triggered_by_emit field for async causality correlation |

## 等决定 · 3 条

**先要结论再动手**：等客户方给出开启时点或放行口径，这个周期要拿到的是答案，不是代码。

| # | Issue | CIP | 状态 | 归属 | 本周期排入 | 为什么排在这一档 | 标题 |
|---:|---|---|---|---|---|---|---|
| 63 | [COW-3134](https://linear.app/cowboy-labs/issue/COW-3134/node-direct-commitmanifest-ignores-private-stagefinalize-token-max) | CIP-9 | Todo | 我方 | 是 · 先要结论 | 直接提交清单绕过私有卷的分阶段流程：同上，代码已合并，等生效高度 | [Node] Direct CommitManifest ignores private stage/finalize, token max_bytes, and the runner-to-sender binding |
| 64 | [COW-2114](https://linear.app/cowboy-labs/issue/COW-2114/node-private-volume-staged-commit-finalize-authority-dek-holder) | CIP-9 | Todo | 我方 | — | 私有卷分阶段提交的最终确认权限：代码已合并，生效高度设成最大值，等客户方定开启高度 | [Node] Private-volume staged-commit finalize authority (DEK-holder) |
| 65 | [COW-4025](https://linear.app/cowboy-labs/issue/COW-4025/node-finalized-state-proof-export-is-1-reqs-per-source-clients-and) | CIP-9 | Backlog | 无主 | — | 已确认状态的证明导出限每秒一次，要先定下对哪几类调用方各放行多少 | node: finalized-state proof export is 1 req/s per source; clients and origins need a real budget |
