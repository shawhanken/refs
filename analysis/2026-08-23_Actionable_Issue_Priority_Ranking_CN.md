# 当期可推进 Issue 优先处理清单（107 条）

数据时点 2026-08-22 16:01（北京）。口径：负责人为 pavilionledger 或无人认领，落在「Validator / Whitepaper / CIPs」倡议内 32 个 CIP 项目下，已扣除外部条件不具备的 8 条和推迟到 11 月发币之后的 50 条。

**排序规则**：队列系统 CIP-39 的 Issue 全部排在最前面；两段之内先按档位（P0 最紧急、P3 最不紧急，「等决定」表示要先有一个规格结论才能动手，「等前置」表示要等另一条 Issue 先完成），再比分数。P2 与 P3 这两档条目多、单条紧急度接近，所以额外加一条：同一档位之内，已经在办的（In Progress / In Review / Todo）排在还没开工的（Backlog）前面，先把开了头的收口。P0 与 P1 不用这条——那两档里一条还停在 Backlog 恰恰是问题本身，不该因此往后排。

**为什么 CIP-39 排在最前**：客户方 8 月 21 日在 devnet-eng 里说明，他们正在批量合并 CBQS 的改进，并确认与我方的工作不冲突。这个方向双方当下都在推，我方提出的排查结果能最快被消化。这 23 条里已有 11 条在办。

**本清单不覆盖的三类工作**，避免误读：一是 Marshal 的迁移与新版本上线，它不是 CIP，也不在任何 CIP 项目下，但这十天里占了客户方的主要注意力；二是 CIP-37、CIP-43、CIP-44 这几份新规格，尚未在 Linear 建项目；三是 8 月 20 日被撤回的 CIP-14 与 CIP-16，其下 Issue 已全部取消。

---

## 一、CIP-39 队列系统 CBQS（23 条 · 优先处理）

| # | Issue | 档位 | 状态 | 归属 | 说明 |
|---:|---|---|---|---|---|
| 1 | [COW-3295](https://linear.app/cowboy-labs/issue/COW-3295/cbqssecurity-make-client-payload-encryption-safe-by-default) | P1 | Backlog | 无主 | 说明文档承诺默认端到端加密，实际的追加接口直接转发原始字节，演示程序发的就是明文。 |
| 2 | [COW-3299](https://linear.app/cowboy-labs/issue/COW-3299/cbqs-define-machine-loss-durability-and-implement-broker-fencing-and) | P1 | Backlog | 无主 | 已确认的标准档数据只存在一个进程和本地一份 RocksDB 里，没有复制、没有跨主机隔离、也没验证过接管。 |
| 3 | [COW-3338](https://linear.app/cowboy-labs/issue/COW-3338/cbqssecurity-serialize-material-view-admission-with-mutation-commit) | P1 | Todo | 无主 | 规格 §7 禁止用比已观察到的实质变更更旧的视图去提交或签名。 |
| 4 | [COW-3288](https://linear.app/cowboy-labs/issue/COW-3288/cbqs-include-every-durable-lane-when-planning-standard-retention) | P2 | In Review | 无主 | 保留策略只从一次 1024 条的扫描里看到的通道推导锚点，而提交要求覆盖每一条持久通道，一条空的或稀疏的通道就能把清理卡死。 |
| 5 | [COW-3293](https://linear.app/cowboy-labs/issue/COW-3293/cbqs-fail-readiness-when-durable-storage-or-fast-flushing-is-unhealthy) | P2 | In Review | 我方 | 就绪检查只看链是否可达，快速档的刷盘失败被吞掉，存储和任务的健康状况完全不上报。 |
| 6 | [COW-3294](https://linear.app/cowboy-labs/issue/COW-3294/cbqssecurity-bound-and-expire-pending-session-and-challenge-state) | P2 | In Review | 我方 | 开启会话时在持有者证明之前就分配了状态，待定会话和用过的挑战既没有全局上限也没有定期清扫，断开连接时的清理也不完整。 |
| 7 | [COW-3298](https://linear.app/cowboy-labs/issue/COW-3298/cbqssecurity-bound-websocket-ingress-handshakes-idle-time-and) | P2 | In Review | 我方 | WebSocket 的默认设置会组装远超协议帧上限的消息，服务端也没有握手期限、空闲超时、全局连接上限和来源限制。 |
| 8 | [COW-3328](https://linear.app/cowboy-labs/issue/COW-3328/cbqs-make-standard-replay-floor-checks-atomic-with-record-scans) | P2 | In Review | 无主 | 标准档重放把「无游标」当作序号 0，绕过了保留下限检查；显式游标时下限校验与记录扫描分两次拿锁，中间保留策略可以把记录删掉。 |
| 9 | [COW-3336](https://linear.app/cowboy-labs/issue/COW-3336/cip-39protocol-canonicalize-provider-endpoint-scheme-casing-across) | P2 | In Progress | 我方 | 服务端地址的协议前缀大小写，规格说不区分、编解码库区分、节点命令行只认小写、连接库又拒绝保留大写的写法。 |
| 10 | [COW-3303](https://linear.app/cowboy-labs/issue/COW-3303/cbqs-clientsecurity-parse-loopback-broker-urls-structurally) | P2 | In Review | 我方 | 判断是否本机回环用的是字符串前缀匹配，把 localhost 放进网址的用户信息段就能骗过它去授权一台远程主机。 |
| 11 | [COW-3334](https://linear.app/cowboy-labs/issue/COW-3334/cbqs-return-signed-cursortooold-for-stale-groupstartat) | P2 | Todo | 无主 | 用一个过旧的记录号创建分组时，应当返回带签名锚点的「游标过旧」，现在没有。 |
| 12 | [COW-3290](https://linear.app/cowboy-labs/issue/COW-3290/cbqs-drive-retention-and-group-maintenance-from-a-durable-broker-wide) | P2 | Todo | 无主 | 维护动作只覆盖当前有订阅的分组，保留策略只发现进程启动后被改动过的流，冷流和不活跃分组就此停止推进。 |
| 13 | [COW-3289](https://linear.app/cowboy-labs/issue/COW-3289/cbqs-enforce-retained-bytes-limit-with-atomic-storage-accounting) | P2 | Backlog | 无主 | 客户付费买的保留字节上限根本没有强制执行，投递元数据和去重墓碑还长在载荷清理范围之外。 |
| 14 | [COW-3291](https://linear.app/cowboy-labs/issue/COW-3291/cbqs-page-group-replay-to-a-frozen-tail-before-switching-live) | P2 | Backlog | 无主 | 分组与死信重放到 1024 条更新就停下且没有续传，然后直接切到实时，签名的收据链上就出现一个缺口。 |
| 15 | [COW-3300](https://linear.app/cowboy-labs/issue/COW-3300/cbqs-ship-store-migration-checkpoint-restore-and-rollback-tooling) | P2 | Backlog | 无主 | 还没有存储快照、备份、恢复校验和演练过的恢复流程，也没有迁移与回滚工具。 |
| 16 | [COW-3292](https://linear.app/cowboy-labs/issue/COW-3292/cbqs-move-rocksdb-and-fsync-work-to-a-bounded-storage-executor) | P2 | Backlog | 无主 | 同步的 RocksDB 扫描和同步写直接跑在 Tokio 任务上，且共用一把进程级数据库锁，互不相干的流会互相堵住。 |
| 17 | [COW-3296](https://linear.app/cowboy-labs/issue/COW-3296/cbqs-client-add-reconnect-request-deadlines-and-subscription) | P2 | Backlog | 无主 | 原生客户端只连一次，没有请求超时，套接字一断就永久关闭，却对外声称支持重连。 |
| 18 | [COW-3297](https://linear.app/cowboy-labs/issue/COW-3297/cbqs-client-add-a-complete-typed-standard-consumer-api) | P2 | Backlog | 无主 | 高层客户端缺少标准档的重放、分组、死信、租约生命周期、自动配额和消费循环，使用方只能自己拼原始协议请求。 |
| 19 | [COW-3301](https://linear.app/cowboy-labs/issue/COW-3301/cbqs-run-fault-injection-crash-coverage-in-ci) | P3 | In Review | 我方 | 故障注入的崩溃恢复测试默认不进 CI，要显式打开特性才跑。 |
| 20 | [COW-3302](https://linear.app/cowboy-labs/issue/COW-3302/cbqs-make-the-load-harness-fail-closed-and-add-capacity-slo-gates) | P3 | In Review | 我方 | 压测程序把建立、生产、消费、确认四类错误都报出来了，却仍然返回成功，也没有任何延迟、收敛、公平性和资源阈值。 |
| 21 | [COW-3335](https://linear.app/cowboy-labs/issue/COW-3335/cbqs-protocol-document-standardretentionanchorv1-as-a-shared-global) | P3 | In Review | 我方 | 协议库把一个字段的含义注释写错了，要改成「全流共享的删除边界」。 |
| 22 | [COW-3304](https://linear.app/cowboy-labs/issue/COW-3304/cbqs-reconcile-packaging-and-public-docs-with-the-supported-surface) | P3 | In Review | 我方 | 公开文档钉的协议版本不对、漏掉客户端库、服务端地址写错，也没有可用的部署打包。 |
| 23 | [COW-3323](https://linear.app/cowboy-labs/issue/COW-3323/cbqsrunner-pilot-a-non-authoritative-cbqs-backhaul-with-cbfs-artifact) | P3 | Backlog | 无主 | 在 Runner 上试点一条默认关闭、非权威的队列回传通道，大输出先写进 CBFS 再发引用。 |

---

## 二、其余 CIP（84 条）

| # | Issue | CIP | 档位 | 状态 | 归属 | 说明 |
|---:|---|---|---|---|---|---|
| 1 | [COW-2915](https://linear.app/cowboy-labs/issue/COW-2915/platform-fee-account-0x18-generate-the-multisig-owner-key-before) | CIP-31 | P0 | Backlog | 无主 | 平台费账户 0x18 的多签持有人密钥必须在创世之前生成。 |
| 2 | [COW-3085](https://linear.app/cowboy-labs/issue/COW-3085/flag-day-chain-id-cutover-retire-chain-id1-assign-canyon-26901-mesa) | CIP-40 | P0 | Backlog | 无主 | 链标识现在是 1，与以太坊主网相同。 |
| 3 | [COW-2113](https://linear.app/cowboy-labs/issue/COW-2113/node-public-volume-commit-prefix-confinement-check) | CIP-9 | P0 | Todo | 我方 | 公开卷提交时不检查被改动的节点是否落在提交者被授权的路径范围内。 |
| 4 | [COW-2152](https://linear.app/cowboy-labs/issue/COW-2152/node-validate-per-relay-effective-deltas-at-commit-caller-trust-blast) | CIP-9 | P0 | Backlog | 无主 | 提交时只核对各中继节点字节增减之和，不比对实际增删的分片。 |
| 5 | [COW-1012](https://linear.app/cowboy-labs/issue/COW-1012/noderunner-pin-production-cowboy-session-chain-id) | CIP-8 | P0 | In Review | 我方 | 会话凭证里的链标识被写死，与节点实际的链标识对不上，一个网络上的凭证可以拿到另一个网络重复使用。 |
| 6 | [COW-1902](https://linear.app/cowboy-labs/issue/COW-1902/13-new-tx-level-field-txfee-payer-override) | CIP-28 | P0 | Backlog | 无主 | 交易里新增「由谁代付手续费」这个字段。 |
| 7 | [COW-1904](https://linear.app/cowboy-labs/issue/COW-1904/2741-fee-payer-resolution-fork-card-address-lookup) | CIP-28 | P0 | Backlog | 无主 | 手续费付款方的解析分支（先查卡片地址再回落）。 |
| 8 | [COW-3168](https://linear.app/cowboy-labs/issue/COW-3168/node-a-garbage-collected-volume-stays-in-the-por-challenge-universe) | CIP-9 | P1 | In Progress | 我方 | 被回收的卷永远留在存储证明的抽查名单里，三次抽查就能把一个诚实的中继节点罚出局。 |
| 9 | [COW-3260](https://linear.app/cowboy-labs/issue/COW-3260/cbfssecurity-bound-pre-auth-quic-memory-and-slow-read-exposure) | CIP-9 | P1 | Backlog | 无主 | 五个未经认证的字节就能声明一个约 256 MiB 的帧，256 条慢速连接可以占住约 64 GiB 内存和全部服务端许可。 |
| 10 | [COW-1911](https://linear.app/cowboy-labs/issue/COW-1911/45-bankerr-error-family-engine-errormap-cardnotfound) | CIP-28 | P1 | Backlog | 无主 | 银行相关的错误类型与错误码映射。 |
| 11 | [COW-1274](https://linear.app/cowboy-labs/issue/COW-1274/architectural-decouple-timer-execution-from-proposes-critical-path) | CIP-5 | P1 | Todo | 我方 | 定时器的执行与出块提议绑在同一条路径上，需要拆开。 |
| 12 | [COW-962](https://linear.app/cowboy-labs/issue/COW-962/node-dispute-window-on-chain-challenge-evidence-re-verification) | CIP-2 | P1 | Todo | 我方 | 链上没有争议处理入口——提出异议、提交证据、重新验证这一整套都没有。 |
| 13 | [COW-2914](https://linear.app/cowboy-labs/issue/COW-2914/rename-fee-splitburn-bps-treasury-bps-and-cbqsrentburn-bps) | CIP-31 | P1 | Backlog | 无主 | 同一个治理参数同时控制着两件经济上不同的事：存储费进国库、中继被罚没的钱销毁。 |
| 14 | [COW-1139](https://linear.app/cowboy-labs/issue/COW-1139/node-emit-nine-event-types-cardissued-carddeposited-cardwithdrawn) | CIP-28 | P1 | Backlog | 无主 | 发卡、充值、提现、扣手续费、冻结等九种事件都没有发出。 |
| 15 | [COW-2109](https://linear.app/cowboy-labs/issue/COW-2109/activate-503020-slash-split-wire-challenger-payout-fix-the-split-value) | CIP-2 | P1 | Backlog | 无主 | 罚没的钱现在仍然全部销毁，提异议的人拿不到回报；且规格 §6 与 §10 自己给了两组不同的分配比例，动手前要先统一取哪一组。 |
| 16 | [COW-2824](https://linear.app/cowboy-labs/issue/COW-2824/sdk-guard-verification-is-inert-for-every-compiled-fsm-actor-guard) | CIP-6 | P1 | Backlog | 我方 | 编译出来的状态机程序全都没有传 guard_keys 参数，CIP-6 §10.3 用来防止读到过期状态的保护在编译这条路径上完全没起作用。 |
| 17 | [COW-1543](https://linear.app/cowboy-labs/issue/COW-1543/45-runner-session-bootstrap-relies-on-a-poc-sessionobserve-http-push) | CIP-8 | P1 | Backlog | 我方 | Runner 会话的启动过程依赖一个演示性质的 HTTP 推送接口，这不是可以上线的做法。 |
| 18 | [COW-3275](https://linear.app/cowboy-labs/issue/COW-3275/cbfscbsssecurity-authenticate-release-key-and-relayer-discovery) | CIP-9 | P1 | Backlog | 无主 | 密钥释放绑定和写入中继名单都来自同一个配置的 RPC，恶意来源可以塞进一套自洽的假密钥和假接收方，客户端就会把数据加密给攻击者。 |
| 19 | [COW-3276](https://linear.app/cowboy-labs/issue/COW-3276/cbfssecurity-channel-bind-relay-identity-and-persist-transport-trust) | CIP-9 | P1 | Backlog | 无主 | 客户端的 TLS 指纹只存在进程内存里，首次连接时的中间人可以转发一次合法的身份挑战并顺带看到访问令牌。 |
| 20 | [COW-3365](https://linear.app/cowboy-labs/issue/COW-3365/skm-0x0d-unbounded-kv-growth-cross-tenant-griefing-exhausts-the-10k) | CIP-7 | P2 | Todo | 无主 | 密钥管理模块（操作码 0x0D）按纪元和订阅者写入的键值行从不删除，而每个链上程序共享一万个键的上限。 |
| 21 | [COW-3385](https://linear.app/cowboy-labs/issue/COW-3385/slashing-never-fires-on-the-live-cbss-release-path) | CIP-24 | P2 | Todo | 我方 | 罚没代码写好了也做了单元测试，但线上的密钥释放路径从头到尾没有一处调用它。 |
| 22 | [COW-3149](https://linear.app/cowboy-labs/issue/COW-3149/cbfs-get-manifest-ships-without-manifest-root-its-verifying-client) | CIP-9 | P2 | Todo | 我方 | 读取文件清单的接口没有一并返回用于校验的根哈希，客户端那条带校验的读取路径实际是死代码，公开卷的鉴权方式也与 CIP-9 §5.3.2 不一致。 |
| 23 | [COW-3386](https://linear.app/cowboy-labs/issue/COW-3386/cbss-reshare-grace-window-is-unreachable-from-cbssd) | CIP-24 | P2 | Todo | 我方 | 链上支持轮换委员会时的宽限期，但守护进程一确认轮换就立刻删掉上一代的份额，释放授权也只认当前一代。 |
| 24 | [COW-1277](https://linear.app/cowboy-labs/issue/COW-1277/node-state-set-state-delete-recompute-storage-root-in-cross-call-write) | CIP-30 | P2 | Backlog | 我方 | 跨程序调用时，写入和删除状态之后没有重新计算存储根。 |
| 25 | [COW-1103](https://linear.app/cowboy-labs/issue/COW-1103/node-attestation-first-runner-registration-registry-0x05verifycae) | CIP-23 | P2 | Backlog | 我方 | Runner 应当先通过硬件证明再注册，现在顺序反过来，可以先注册再补证明，等于给没通过证明的节点留了一个窗口。 |
| 26 | [COW-927](https://linear.app/cowboy-labs/issue/COW-927/node-post-raschallenge-endpoint-chain-state-challenge-records) | CIP-9 | P2 | Backlog | 我方 | 缺少发起挑战的接口和链上的挑战记录。 |
| 27 | [COW-2832](https://linear.app/cowboy-labs/issue/COW-2832/noderunner-runnervalidator-version-and-tx-format-compatibility) | CIP-9 | P2 | Backlog | 我方 | Runner 与验证者之间没有版本和交易格式的协商机制。 |
| 28 | [COW-3263](https://linear.app/cowboy-labs/issue/COW-3263/cbfs-make-root-placement-discoverability-part-of-commit-atomicity) | CIP-9 | P2 | Backlog | 无主 | 放置失败可以在正式提交之前被吞掉，而新读者要靠根放置记录才能打开文件清单。 |
| 29 | [COW-3268](https://linear.app/cowboy-labs/issue/COW-3268/cbfs-reconcile-pruned-volume-event-gaps-before-gc) | CIP-9 | P2 | Backlog | 无主 | 剪枝恢复时游标照样往前走，但它自己承认水位线以下的增删无法重建。 |
| 30 | [COW-3269](https://linear.app/cowboy-labs/issue/COW-3269/cbfs-reserve-capacity-atomically-and-enforce-cumulative-capability) | CIP-9 | P2 | Backlog | 无主 | 容量准入是先读后写的检查，账目出错时是放行而不是拦截；而且容量上限按单次请求算，不是按累计算。 |
| 31 | [COW-3265](https://linear.app/cowboy-labs/issue/COW-3265/cbfs-store-plaintext-and-ciphertext-lengths-separately) | CIP-9 | P2 | Backlog | 无主 | 私有对象把密文长度记成了文件大小，重新挂载之后文件系统显示的就是密文长度，不是真实内容长度。 |
| 32 | [COW-3264](https://linear.app/cowboy-labs/issue/COW-3264/cbfs-fence-fuse-writers-or-rebase-root-conflicts-without-a-permanent) | CIP-9 | P2 | Backlog | 无主 | 文件系统挂载出现根冲突后会永久卡住：脏状态阻止拉取，之后每次循环都重复同一个冲突；独立模式则相反，直接忽略上一个根、丢掉更新。 |
| 33 | [COW-3271](https://linear.app/cowboy-labs/issue/COW-3271/cbfs-supervise-safety-loops-and-derive-readiness-from-real-state) | CIP-9 | P2 | Backlog | 无主 | 计量模块把健康状态写死成正常，而修复、放置同步、事件跟随、垃圾回收这几个循环没有任何监管。 |
| 34 | [COW-3274](https://linear.app/cowboy-labs/issue/COW-3274/cbfs-add-write-deadlines-alternate-placement-and-an-explicit) | CIP-9 | P2 | Backlog | 无主 | 写入要求选中的每一个中继全部成功，且不重试备选节点，一个慢节点或满节点就让纠删码的冗余失去意义。 |
| 35 | [COW-1542](https://linear.app/cowboy-labs/issue/COW-1542/6416-sessionassetcip20-token-escrow-path) | CIP-8 | P2 | Backlog | 无主 | 会话里还不支持用 CIP-20 代币做托管。 |
| 36 | [COW-1184](https://linear.app/cowboy-labs/issue/COW-1184/noderunner-evm-bridge-facilitator-bridgefacilitateevm-entitlement) | CIP-18 | P2 | Backlog | 无主 | 以太坊桥代付方的权限与凭证。 |
| 37 | [COW-3266](https://linear.app/cowboy-labs/issue/COW-3266/cbfs-replace-full-payload-repair-probes-with-a-bounded-incremental) | CIP-9 | P2 | Backlog | 无主 | 每轮修复都要扫描并哈希本地全部分片，还每五分钟向其他每个持有者完整拉取一次分片来探活。 |
| 38 | [COW-3267](https://linear.app/cowboy-labs/issue/COW-3267/cbfs-chunk-and-stream-object-writes-so-the-advertised-max-size-is) | CIP-9 | P2 | Backlog | 无主 | 一个 1 GiB 的私有对象加上加密开销就超过默认 256 MiB 的帧上限，还会产生 5 GiB 以上的临时内存。 |
| 39 | [COW-3169](https://linear.app/cowboy-labs/issue/COW-3169/nodespec-volume-delete-grace-epochs-does-not-exist-the-undelete-window) | CIP-9 | P2 | Backlog | 无主 | 规格 §13.3 承诺删除卷之后有一个宽限期可以撤销删除、期间继续计费，代码里根本没有这个参数：撤销窗口最多一个纪元，费用也不累计。 |
| 40 | [COW-3092](https://linear.app/cowboy-labs/issue/COW-3092/add-atomic-grantsecretactor-instruction-to-cbss) | CIP-24 | P2 | Backlog | 无主 | 控制台现在只能用「读出来、合并、再写回去」的方式给程序授权，存在竞态，还要求钱包去签一份包含多个程序的替换策略。 |
| 41 | [COW-2826](https://linear.app/cowboy-labs/issue/COW-2826/nodespec-cip-20-on-chain-allowancespender-secondary-index-re-scope-of) | CIP-20 | P2 | Backlog | 我方 | 链上缺少授权额度的二级索引，查不出某个账户授权了哪些人代扣。 |
| 42 | [COW-1901](https://linear.app/cowboy-labs/issue/COW-1901/2526-cross-chain-streaming) | CIP-25 | P3 | Todo | 我方 | 跨链流式发送与总序，没有任何实现。 |
| 43 | [COW-3277](https://linear.app/cowboy-labs/issue/COW-3277/cbfs-add-placement-tombstones-and-bounded-lifecycle-indexes) | CIP-9 | P3 | Backlog | 无主 | 删掉的分片不会留下持久的墓碑记录，修复和同步会无限期保留并扫描历史放置状态。 |
| 44 | [COW-1281](https://linear.app/cowboy-labs/issue/COW-1281/node-fork-o1-clone-childstorage-root-parentstorage-root-replaces) | CIP-30 | P3 | Backlog | 无主 | 复制程序时应当直接继承父级的存储根，做到常数时间完成；现在是逐条枚举复制的临时做法。 |
| 45 | [COW-987](https://linear.app/cowboy-labs/issue/COW-987/sdk-actor-side-runtimemountvolume-id-access-mode-for-cbfs-workflows) | CIP-6 | P3 | Backlog | 无主 | 程序侧还没有挂载卷的接口，这是链上程序在跑任务时读写 CBFS 卷的入口。 |
| 46 | [COW-1798](https://linear.app/cowboy-labs/issue/COW-1798/icip20actor-actor-token-interface-actor-based-tokens-fee-on-transfer) | CIP-20 | P3 | Backlog | 无主 | 缺少程序形态的代币接口，也就无法支持转账时收费这类自定义行为。 |
| 47 | [COW-3024](https://linear.app/cowboy-labs/issue/COW-3024/cbfs-consolidate-relay-sled-dbs-into-one-db-trees-for-cross-store) | CIP-9 | P3 | Backlog | 无主 | 中继节点同时打开至少三个互相独立的 sled 数据库，各自独立刷盘、没有跨库事务，所以一次涉及多个库的提交无法保证要么全成要么全不成。 |
| 48 | [COW-2671](https://linear.app/cowboy-labs/issue/COW-2671/add-authenticated-evidence-for-cbss-threshold-wide-withholding) | CIP-24 | P3 | Backlog | 无主 | 密钥服务整组节点都不响应时，拿不到可以验证的证据，也就无法追究责任。 |
| 49 | [COW-1280](https://linear.app/cowboy-labs/issue/COW-1280/node-gas-formula-for-trie-updates-deterministic-bounded-cost-per-state) | CIP-30 | P3 | Backlog | 无主 | 状态树更新还没有 gas 计费公式，要求结果确定且有上限。 |
| 50 | [COW-2184](https://linear.app/cowboy-labs/issue/COW-2184/cbfs-full-relay-rewards-distribution-pro-rata-by-shard-count-x-age) | CIP-9 | P3 | Backlog | 无主 | 中继节点的奖励分配还没做完（按分片数量与存放时长按比例分）。 |
| 51 | [COW-2623](https://linear.app/cowboy-labs/issue/COW-2623/cow-918-follow-up-batchpipeline-por-response-submission-to-restore) | CIP-9 | P3 | Backlog | 无主 | 存储证明的响应现在逐条提交，要改成批量或流水线提交，才能把同时处理挑战的上限恢复回去。 |
| 52 | [COW-2831](https://linear.app/cowboy-labs/issue/COW-2831/cbfs-zero-config-cbfs-client-full-chain-discovery-bootstrap) | CIP-9 | P3 | Backlog | 我方 | CBFS 客户端现在要手工填配置，需要改成自己从链上读取配置来启动。 |
| 53 | [COW-1917](https://linear.app/cowboy-labs/issue/COW-1917/2124-emitresult-return-value-not-surfaced) | CIP-29 | P3 | Backlog | 我方 | 发布事件之后的返回值没有传给调用方。 |
| 54 | [COW-2833](https://linear.app/cowboy-labs/issue/COW-2833/cbfs-long-lived-write-cap-tokens-for-large-streaming-writes) | CIP-9 | P3 | Backlog | 我方 | 大文件流式写入需要长期有效的写入凭证，目前没有。 |
| 55 | [COW-1082](https://linear.app/cowboy-labs/issue/COW-1082/explorer-token-balance-transfer-history-ui) | CIP-20 | P3 | Backlog | 我方 | 浏览器里的代币余额与转账历史界面。 |
| 56 | [COW-1152](https://linear.app/cowboy-labs/issue/COW-1152/nodesdk-payload-schema-validation-at-emit-subscribe-time) | CIP-29 | P3 | Backlog | 无主 | 发布事件和订阅事件时都没有校验数据结构是否符合约定。 |
| 57 | [COW-3027](https://linear.app/cowboy-labs/issue/COW-3027/cbfs-benchmark-the-data-plane-vs-s3storj-capture-shard-size) | CIP-9 | P3 | Backlog | 无主 | 规格 §15 公布的延迟数字没有任何实测支撑。 |
| 58 | [COW-1147](https://linear.app/cowboy-labs/issue/COW-1147/node-receipt-schema-triggered-by-emit-field-for-async-causality) | CIP-29 | P3 | Backlog | 无主 | 收据里缺少「由哪次发布触发」的字段，异步事件一环触发一环的过程就追查不出来。 |
| 59 | [COW-1899](https://linear.app/cowboy-labs/issue/COW-1899/16-multi-destination-cost-reduction) | CIP-25 | P3 | Backlog | 我方 | 多目的地成本优化（BLS12-381 聚合、广播中继扇出、门限 ECDSA 兜底），三项都没实现。 |
| 60 | [COW-1900](https://linear.app/cowboy-labs/issue/COW-1900/13-state-root-parent-hash-commitment-fields) | CIP-25 | P3 | Backlog | 无主 | 跨链区块头里的状态根与父哈希承诺字段还没有。 |
| 61 | [COW-1282](https://linear.app/cowboy-labs/issue/COW-1282/noderpc-expose-per-actor-proof-endpoint-get-actorstorage-root-opens) | CIP-30 | P3 | Backlog | 无主 | 还没有按程序单独提供存储根证明的接口。 |
| 62 | [COW-1285](https://linear.app/cowboy-labs/issue/COW-1285/tooling-pre-image-table-for-hashed-long-keys-debugger-explorer) | CIP-30 | P3 | Backlog | 无主 | 缺少长键哈希对应原文的对照表，调试工具与浏览器无法列出这些键。 |
| 63 | [COW-3028](https://linear.app/cowboy-labs/issue/COW-3028/cbfs-verify-the-standalone-no-cowboy-on-ramp-works-for-an-outside-user) | CIP-9 | P3 | Backlog | 无主 | 规格声称 CBFS 可以脱离 Cowboy 账号独立使用，但至今没有团队之外的人真的克隆、编译、跑通过这条路径。 |
| 64 | [COW-3029](https://linear.app/cowboy-labs/issue/COW-3029/cbfs-shard-blob-store-move-to-plain-files-git-style-not-another-kv) | CIP-9 | P3 | Backlog | 无主 | 分片数据块的存储改成 git 那样的普通文件，不再用另一个键值库。 |
| 65 | [COW-1073](https://linear.app/cowboy-labs/issue/COW-1073/spec-bridge-lock-and-mint-cip-for-eth-cowboy-l1-blocking-dollarcowboy) | CIP-20 | 等决定 | Backlog | 我方 | 以太坊到本链的锁仓铸币桥规格与时间表未定。 |
| 66 | [COW-1377](https://linear.app/cowboy-labs/issue/COW-1377/8-aggregator-collects-result-bytes-via-direct-http-push) | CIP-2 | 等决定 | Backlog | 我方 | 结果收集方式还没定：由聚合方直接推送，还是链上自行聚合。 |
| 67 | [COW-1575](https://linear.app/cowboy-labs/issue/COW-1575/122-image-pull-egress-fees-pull-cost-size-egress-fee-per-byte) | CIP-10 | 等决定 | Backlog | 无主 | CIP-10 §13 那套参数只写了名字没给数值，出口流量计费写不了。 |
| 68 | [COW-1578](https://linear.app/cowboy-labs/issue/COW-1578/13-parameter-set-max-cpu-millicores) | CIP-10 | 等决定 | Backlog | 无主 | 同上，整套参数取值未定。 |
| 69 | [COW-1761](https://linear.app/cowboy-labs/issue/COW-1761/7-ingressmcp-entitlement-id-with-params-server-name) | CIP-19 | 等决定 | Backlog | 无主 | MCP 接入的权限标识。 |
| 70 | [COW-1774](https://linear.app/cowboy-labs/issue/COW-1774/103-input-schema-derivation-from-path-params-openapi-doc) | CIP-19 | 等决定 | Backlog | 无主 | 从路径参数推导输入结构并生成接口文档。 |
| 71 | [COW-1788](https://linear.app/cowboy-labs/issue/COW-1788/143-per-actor-tool-list-cache-keyed-by-actor) | CIP-19 | 等决定 | Backlog | 无主 | 按程序缓存工具清单，键里带着路由注册表的状态根。 |
| 72 | [COW-1896](https://linear.app/cowboy-labs/issue/COW-1896/1415a5-zk-light-client-backend) | CIP-25 | 等决定 | Todo | 我方 | 零知识轻客户端后端，这条 Issue 的范围本身要重写。 |
| 73 | [COW-2099](https://linear.app/cowboy-labs/issue/COW-2099/cip-9-rewrite-epic-triage-grounded-findings-from-mesa-bring-up-cip-9) | CIP-9 | 等决定 | Backlog | 我方 | CIP-9 重写总单，它引用的原始文档 cip-9-rewrite-ideas.md 已经找不到，无法据此拆分子项。 |
| 74 | [COW-2506](https://linear.app/cowboy-labs/issue/COW-2506/cip-10-gpu-billing-scheduling) | CIP-10 | 等决定 | Backlog | 无主 | GPU 计费与调度，同样卡在 §13 参数取值。 |
| 75 | [COW-2507](https://linear.app/cowboy-labs/issue/COW-2507/cip-10-networked-containers-egress-accountingbilling) | CIP-10 | 等决定 | Backlog | 无主 | 联网容器与出口流量记账，同样卡在 §13 参数取值。 |
| 76 | [COW-2829](https://linear.app/cowboy-labs/issue/COW-2829/specnode-cip-9-7-elevate-volume-access-to-first-class-access-classes) | CIP-9 | 等决定 | Backlog | 我方 | 卷的访问权限要不要单独做成一类权限，这是规格改动，要先有结论。 |
| 77 | [COW-2884](https://linear.app/cowboy-labs/issue/COW-2884/node-cip-29-23-gas-isolation-not-enforced-for-cells-in-async-event) | CIP-29 | 等决定 | Backlog | 无主 | 订阅方在事件触发时用掉的存储单元记到谁头上，这是 CIP-29 §2.3 的修订，要先有结论。 |
| 78 | [COW-3053](https://linear.app/cowboy-labs/issue/COW-3053/cbfs-single-writer-volumes-revisit-the-constraint) | CIP-9 | 等决定 | Backlog | 无主 | CBFS 的卷只允许一个所有者提交，所有多人写入的场景都得在应用层绕开。 |
| 79 | [COW-1122](https://linear.app/cowboy-labs/issue/COW-1122/runner-runner-job-type-generate-inclusion-proof-third-party-proof) | CIP-25 | 等前置 | Todo | 无主 | 把生成包含性证明做成一种 Runner 作业类型。 |
| 80 | [COW-1897](https://linear.app/cowboy-labs/issue/COW-1897/14a5-optimistic-backend-with-challenger-bondsincentives) | CIP-25 | 等前置 | Todo | 我方 | 带挑战保证金的乐观验证后端。 |
| 81 | [COW-3086](https://linear.app/cowboy-labs/issue/COW-3086/ethereum-facade-post-eth-json-rpc-stub-on-node-rpc) | CIP-40 | 等前置 | Backlog | 无主 | 以太坊风格的 JSON-RPC 外观接口。 |
| 82 | [COW-3087](https://linear.app/cowboy-labs/issue/COW-3087/registry-prs-to-ethereum-listschains-mesa-26909-prairie-26900-mainnet) | CIP-40 | 等前置 | Backlog | 无主 | 向以太坊链名录提交登记。 |
| 83 | [COW-3088](https://linear.app/cowboy-labs/issue/COW-3088/prairie-public-testnet-bring-up) | CIP-40 | 等前置 | Backlog | 无主 | 公开测试网 Prairie 的搭建。 |
| 84 | [COW-3089](https://linear.app/cowboy-labs/issue/COW-3089/cip-20-holder-enumeration-index-or-preimage-scan-blocked-by-cow-3090) | CIP-20 | 等前置 | Backlog | 我方 | 代币持有人枚举。 |

