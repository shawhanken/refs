# 109 条 Issue 的解决难易度评估

**评估日期**：2026-08-11（代码对比更新）
**配套文档**：`20260805_Issue_Fix_Checklist_109_CN.md`（优先级）、`20260806_Issue_Checklist_109_Code_Verification_CN.md`（代码核验）
**代码基线**：`node@devnet b06bbdbf`、`cbfs@devnet 232c8e4`、`runner@devnet baea4fb`、`cowboy-protocol@devnet d5ed2c8`、`cowboy@devnet 7226b6f`、`gateway@main 392b4ad`。另对照未合入的配对授权 PR：`node#1303@486f5ffa`、`cbfs#131@79cc28e`。

> **更新 2026-08-07。** 本文的评级在后续两轮深挖中被多次修订，此处汇总当前状态，详见 §8。
> - **三条 XS 已完成并关闭**：COW-1143 / COW-1283 / COW-1620（均为零代码的决策/范围问题）
> - **COW-2842 已合并**（cbss#83 → cbss `main`）：CIP-24 release-receipt spawned e2e，真跑打通并抓出 7 个真 bug + 一个陈旧 pin，详见 §8.6
> - **COW-2834 已从“开工中”推进到 FUSE 半边已合并**（cbfs PR #129）；链上/协议授权半边仍未闭合
> - **又有 6 条从 S 降为 M**：COW-1911 / COW-1917 / COW-1575 / COW-1578 / COW-1147 / COW-1152
> - **CIP-25 分档理由已澄清**：客户方正在建 §1.4 原生后端，但 109 清单的范围定义是对的
> - **COW-2830 建议 close**（08-07 复核，见 §8.7）：CIP-9 §9.2 读路径有 v1/v2 两版——v1（Dispatcher 遞交 partials，runner 本地解密）**已 landed**；「endpoint discovery / direct-fetch」半属 **COW-1546（v2，未 landed）**，v2 落地前无消费者。已贴 comment，final call 归 COW-2099 owner
> - **COW-937 已合并**（runner PR #213）：真实 QUIC + FUSE 的访问模式、manifest round-trip、cache stress 集成测试已经进入 `runner/devnet`
> - **COW-3038 / COW-3132 的 node↔cbfs 配对 PR 尚未合入**：新增 target-volume 绑定和授权矩阵锁，但 rollout 仍允许缺失/畸形字段；本轮还发现共享 shard 生命周期与 commit authority 的残余风险，详见 §9

优先级回答「该不该先做」，这份回答「做起来多难、难在哪」。两者不是一回事——本次评估里最值得注意的结论就是：**清单里排第 2、3 位的两条，是全部 109 条里最难的一档。**

---

## 1. 难度模型

在这个代码库里，难度基本不由代码量决定，而由**影响半径**决定。核验过程中反复出现的五个因子：

| 因子 | 含义 | 为什么是难度放大器 |
|---|---|---|
| **D1 共识面** | 改动进入 `state_root` / `receipt_root` / 状态转换 | 需要激活高度 + 协调的验证者滚动升级；混版本机群会分叉 |
| **D2 线格式** | 改动落在 `cowboy-protocol` 编解码上 | 全网双端同时升级，且旧编码要继续可解 |
| **D3 跨仓** | 涉及 node / cbfs / cbss / runner / gateway / cowboy-protocol | 每多一个仓就多一轮版本对齐（先例：COW-2922 canyon convergence） |
| **D4 规范缺口** | CIP 没写、写错、或自相矛盾 | 要先出规范修订/勘误，编码才有依据 |
| **D5 决策门 / 前置** | 需客户方拍板，或被另一条 Issue 卡住 | **与工作量无关**——投再多人也开不了工 |

### 评级

| 级别 | 判据 | 量级参考 |
|---|---|---|
| **XS** | 骨架已在，只差接通或改一个值 | < 1 天 |
| **S** | 单仓、不进共识、规范明确 | 1–3 天 |
| **M** | 单仓但触及共识面（需激活门），或跨 2 仓 | 1–2 周 |
| **L** | 新的链上机制，或 D1+D3 同时命中 | 3–6 周 |
| **XL** | 线格式变更 + 跨仓 + 激活门，且往往要先改规范 | 1.5 个月以上 |
| **⛔** | 决策门——难度不由我方决定 | — |
| **⏳** | 被前置条目阻塞 | — |

**证据等级**：✅ = 本轮已读代码核验；🔶 = 有定向 grep 证据；⬜ = 未核验，按 CIP 与同类条目推定。

---

## 2. 必须做（第 1–8 行）

| 序 | Issue | 难度 | 证据 | 难在哪 |
|---:|---|---|:--:|---|
| 1 | COW-2915 平台费密钥 | **⛔** / 技术侧 S | ✅ | 生成多签 + 写创世本身很小。但门限、签名人、托管、恢复路径要客户方定；且**创世后不可补**，是时间窗问题不是难度问题 |
| 2 | COW-2113 公开卷前缀限定 | **XL** | ✅ | D1+D2+D3+D4 全中。`CommitManifestInstruction` 里没有任何路径信息，`validate_commit_authorization`（`ras.rs:4221`）三条授权分支无一处可挂。要先给提交指令加**清单差分见证**：CIP-9 规范改 → cowboy-protocol 编解码 → node + cbfs 双端 → 激活门 |
| 3 | COW-2152 中继增量核对 | **XL**（与第 2 行合并做则边际 M） | ✅ | 同一根因。`TaggedShardRef` 只有 shard_id/index/chunk_root，**没有字节数**，链上无从反推每中继字节。必须与第 2 行同一次线格式变更一起做 |
| 4 | COW-1012 会话链标识 | **L** | ✅ | 表面是改一个常量（S）。但 `rpc/src/handlers/cbss.rs:828-840` 记录：这个值同时绑着 CIP-9 volume-DEK 封装，直接改会让所有已封装的卷密钥解不开（`AadMismatch`）。真实工作是**跨 CIP-8/CIP-9 的协调切换 + 已封装 DEK 的重封装迁移**，跨 node/cbfs/runner |
| 5 | COW-2896 CBFS 计费取数 | **M** | ✅ | 改动局限在 `cbfs/registry-proto`，但落在结算路径上（`settle_volume_epoch:1342`），进共识面。共三处（另含 `split_storage_fee` 的 `STORAGE_FEE_BURN_BPS`、`auth/chain_state.rs:295`）。与第 13 行合包；**当前未发现直接修复 PR**，cbfs#127 只是 protocol pin 更新 |
| 6 | COW-1073 桥 CIP | **XL（写作型）** | ⬜ | 不是编码难，是**从零写一份规范**并覆盖锁定/铸造的资金安全论证。8 月窗口内不到四周，是全表时间压力最大的一条 |
| 7 | COW-1902 `tx.fee_payer_override` | **L** | ✅ | 交易级新字段 = D2 线格式变更（cowboy-protocol 编解码）+ 签名域变化 + 激活门。注意现有的 `fee_payer_override` 只存在于**定时器/调度指令**上（`actor_instruction.rs:1415`），不是交易级，不能复用 |
| 8 | COW-1904 代付方解析 | **M** ⏳依赖第 7 行 | ✅ | 本身是执行层的查找逻辑，字段落地后不难 |

---

## 3. 应该做（第 9–17 行）

| 序 | Issue | 难度 | 证据 | 难在哪 |
|---:|---|---|:--:|---|
| 9 | COW-1274 定时器脱离出块路径 | **L→XL** | ✅ | 耦合本身清楚（`speculative.rs` 第 9 步由 propose/verify 的 `execute_speculative` 执行）。难在**四层加固已经叠在这个耦合之上**：COW-1457 两阶段 EOB、COW-2635 wall-weight 截断、规范前缀校验、拍卖上限。且分类顺序是共识可见不变量（`cip5_5_1_due_timers_classified_before_handlers_execute`），新结构必须逐字复现 |
| 10 | COW-1911 BankErr 错误族 | ~~S/M~~ → **M** | ✅ | **08-07 复核降级。** 模板现成（`structured_error_map.rs` + RAS 的 slug 模式），现状也确实糟（`bank/handlers.rs` 里 `InvalidData` 出现 61 次）。但该文件开头明写 `code` 是 **consensus-hashed 进 `receipt_root`**，并记着 COW-2290 的分叉教训 → 拆错误码 = 改收据字节 = 需激活门 |
| 11 | COW-2834 卷访问模式 | **拆两半** | ✅ | **FUSE 侧 S，已合并**：挂载 RO、读写门控、权限位屏蔽和真实挂载测试均已落地；**链上侧 XL**：访问模式与 commit authority 仍需随第 2/3 行的协议和激活主线闭合 |
| 12 | COW-1139 银行九事件 | **S** ⏳依赖 COW-1143 | ✅ | 八种已发出。补 `BankRegistered` 本身很小，但链上没有开户执行路径（`system_instruction.rs:1129` 直接 `Err(InvalidData)`）。另加事件是共识变更，需协调升级 |
| 13 | COW-2914 参数改名/拆分 | **M** 🔨 修复中 | ✅ | 两个 Draft PR 正在推进：node#1221、cbfs#118。真正工作是**拆成两个参数** + 创世种子 + 跨 node/cbfs 同步，且要避开被第 5 行的编译期常量回滚；**不应重复分配** |
| 14 | COW-962 争议窗口 | **L** | ✅ | 新指令 + 链上挑战/证据记录 + 重验证委员会调度。**有先例可抄**：CIP-10 的容器争议窗口已实装（`container_registry.rs:859-923` + `system_instruction.rs:5905`），记录/索引/翻转的形状可直接复用，所以是 L 不是 XL |
| 15 | COW-1543 Runner 会话启动 | **M/L** | ✅ | `/session/observe` 只存在于 `examples/`，生产 runner **完全没有这条路径**。不是替换一个坏实现，是新建，跨 node + runner |
| 16 | COW-2109 罚没分配 | **⛔ + ⏳** / 技术侧 S | ✅ | 分账机制已全在，`submitter_bps` 就是 challenger 档。但 `(10000,0,0)` 是白皮书 §8.4 C7 的既定承诺，挪动它要 **Tier-3 提案 + 同步修订白皮书**（客户方），且必须等 COW-962 产出 challenger 身份 |
| 17 | COW-2824 guard_keys | ~~S~~ → **M**（优先级不降） | ✅ | **08-06 复核降级。** 改动确实小（3 文件 + pypi 镜像），但 `pvm/Lib/cowboy_sdk` 是随节点二进制发布的 RustPython 标准库，FSM 编译发生在**链上 import 时** → 混版本机群分叉，需旗日升级。另发现 `timeout_blocks` 同样失效。node#1158 虽 OPEN，但明确标注 **out of scope / pre-existing**，不是 COW-2824 的实际修复；**目前不可视为有人在修** |

---

## 4. 可以缓（第 18–57 行）——有代码证据的部分

| 序 | Issue | 难度 | 证据 | 说明 |
|---:|---|---|:--:|---|
| 18 | COW-1277 storage_root 重算 | **L** | ✅ | 每次 `state_set`/`state_delete` 维护 trie + 写集分级回滚 + 读路径对齐。已有钉住测试（`genesis.rs:3281`）。**必须走激活门**：字段已进 actor 叶子（`impl Write for Actor` 写 `storage_root`），首次写真值即改 `state_root` |
| 19 | COW-1103 证明先于注册 | **M** | ⬜ | 注册顺序调整 + 0x05 跨调用 |
| 20 | COW-927 挑战接口 + 链上记录 | **L** | ⬜ | 新 RPC + 新链上记录类型 |
| 21 | COW-2832 版本/格式协商 | **M** | ⬜ | 跨 node + runner |
| 23 | COW-1578 CIP-10 参数集 | ~~S/M~~ → **M** | ✅ | **08-07 复核降级。** `MAX_CPU_MILLICORES` 等全仓零命中；治理参数框架（`CONTAINER_SETTLEMENT_CONFIG_KEY` + `load_*_config`）只是最后 10%，计量点本身不存在 |
| 27 | COW-2178 卷绑定校验 | **M** ✅ 已合并 | ✅ | 已由 [node#1282](https://github.com/cowboyinc/node/pull/1282) 合并；使用 `StrArray` + activation gate 落地，纯函数和 handler 接线均已完成。后续只剩 flag-day 前的 open items，不应重复分配 |
| 28 | COW-2884 事件 gas 隔离 | **M** ✅ backstop 已合并 | ✅ | 已由 [node#1198](https://github.com/cowboyinc/node/pull/1198) 合并 per-fire cells cap；完整闭合仍需 **CIP-29 cells-budget 修订**（D4），这是规范/activation 收尾，不是同一份代码修复 |
| 29 | COW-1283 迁移策略 | **XS** ✅ **已关闭** | ✅ | 08-07 定「测试网清空重来」；零实现成本已核实 |
| 30 | COW-1406 辅助索引重建 | **M** ✅ 已合并 | ✅ | 已由 [node#1298](https://github.com/cowboyinc/node/pull/1298) 合并；非共识的 `tx_index` full/incremental rebuild 已落地，不应重复分配 |
| 31 | COW-1620 CIP-11 常量 | ~~S~~ → **XS** ✅ **已关闭** | ✅ | **08-07 §13 全表核验：一个常量都不用加。** 详见 §8.2 |
| 32 | COW-2538 应答超时重选 | **M** | ⬜ | 需先定做法（D4 小），改动在选择路径上，触共识面 |
| 34 | COW-2830 加密卷密钥读取 | ~~M~~ → **建议 close** | ✅ | **08-07 复核。** 读路径分 v1/v2：**v1 已 landed**——`CbssVolumeKeyRelease`（partials+vss）随 job 送进 `VolumeRuntimeAttachment.cbss_key_release`（`runner-common/types.rs:423`），runner **本地** HPKE-open→verify→combine（`runner-storage/lib.rs:555-603`），对 partials 无任何网络 fetch。「endpoint discovery」半 = **COW-1546（v2 Secrets-Manager direct-fetch，未 landed）**，v2 前无消费者，现造 = 投机码。陷阱：`/cbss/proxies` 的 `network_addr` 是 QUIC partial-sign 位址，非 runner 消费的密文 blob 端点。已贴 comment 建议折进 COW-1546 |
| 37 | COW-937 CIP-9 集成测试 | **S** ✅ 已合并 | ✅ | runner PR #213 已加入真实 QUIC + FUSE 的 access-mode、manifest round-trip、cache-stress 测试；链上共识授权仍由 recording hooks 代替，不应把该测试完成等同于链上授权闭合 |
| 39 | COW-1281 fork O(1) | **XS** ⏳依赖第 18 行 | ✅ | 继承语义**已在** `pvm_host.rs:3535`（`storage_root: parent_actor.storage_root`），只因父根恒空而是空操作。COW-1277 之后基本自动生效 |
| 40 | COW-1575 镜像拉取计费 | ~~S~~ → **M** | ✅ | **08-07 复核降级。** `EGRESS_FEE_PER_BYTE` / `pull_cost` 全仓零命中，`execution/` 下**连计量点都没有**。不是「缺一个数」，是计量器要从零建 |
| 44 | COW-1280 trie gas 公式 | **M** ⏳依赖第 18 行 | 🔶 | 零实现；gas 公式进共识面 |
| 46 | COW-2184 中继持续奖励 | ~~S~~ → **M** | ✅ | **08-06 复核降级。** 公式在（`ras/src/lib.rs:2801`），两个调用点硬传 age=`1`，但**链上没有分片龄数据**——`RelayNodeProfile`（`ras/src/types.rs:355`）只有 `shards_held` 和中继自身的 `registered_epoch`/`activated_epoch`。用后者会付反激励。要加累计字段 = 结构编解码变更 + 迁移 + 激活门 |
| 49/52/55 | COW-1917 / 1152 / 1147（CIP-29 三条） | ~~S–M~~ → **M** | ✅ | **08-07 复核降级。** COW-1917 要改宿主 ABI（`pvm_host.rs:2871` 的 `emit_event` 返回 `HostResult<()>`）；COW-1147 往收据加字段；COW-1152 让拒绝行为进共识。三条都触共识面 |
| 56/57 | COW-1282 / COW-1285 | **S** ⏳依赖第 18 行 | 🔶 | 存储根为空之前没有可暴露的证明 |
| 36/42 | COW-2826 / COW-1798（CIP-20） | **M** | 🔶 | 均零命中；二级索引触状态面，actor-token 接口是新机制 |

未逐条列出的其余条目（22、24、25、26、33、35、38、41、43、45、47、48、50、51、53、54）以 ⬜ 推定，整体落在 **S–M**，其中 COW-1143（第 24 行）经核验应收窄到 **S**（详见核验文档 §2.5）。

---

## 5. 第四、五段的块级评估

| 块 | 条数 | 难度 | 证据 | 说明 |
|---|---:|---|:--:|---|
| CIP-25 跨链（第 58–64 行） | 7 | **L–XL** | ✅ | **08-07 澄清（见 §8.3）**：§1.4 有四个后端各一条 Issue。**原生后端 COW-1898 归客户方（caleb）且 In Progress**，4 个 PR 在飞；清单里的 COW-1896（ZK）/ COW-1897（乐观）是另外两个后端，**不是重复**。清单范围定义正确，未漏。但另有 3 条无人负责的上线门控跟进项不在 109 里 |
| CIP-14 网关（第 65–80 行） | 16 | **XL（块级）** | ✅ | devnet 上只有两个地址常量，`GatewayProfile` / `IngressDispatch` / `complete_receipt` 全仓零命中。要新建两个系统 actor + 两个系统操作码（65 / 66）+ 一个新的网关节点角色。四条核心必须先做 |
| CIP-19 MCP（第 81–90 行） | 10 | **M（块级）**，全部 ⏳依赖 CIP-14 | ⬜ | 本身多是协议翻译层，不难；难在底座不存在 |
| CIP-16 域名（第 91–109 行） | 19 | **M（块级）** | ✅ | **已有 1662 行底座**（`types/src/domain.rs` 341 + `execution/src/runner/domain.rs` 1321），路由注册表 0x0E 在跑。19 条多是增量功能（外部域名接入、DNS 验证、重验证），**不被 CIP-14 卡住** |

---

## 6. 三份可直接用的清单

### 6.1 快赢——难度 S 或以下、不被阻塞、现在就能开工

> **⚠️ 本节已被 `20260806_QuickWins_DeepDive_CN.md` 逐条复查并修订。** 初版列了六条，深挖后**两条评错（COW-2824、COW-2184 升为 M）、一条性质改变（COW-1620 改为范围修订）**。下表为修订后版本，判据见深挖文档。

| Issue | 难度 | 一句话 |
|---|---|---|
| **COW-2834 的 FUSE 半边**（第 11 行） | S ✅ 已合并 | ✅ **cbfs PR #129 已合入 `devnet`**。`MountOption::RO`、`require_read/require_write`、权限位屏蔽和 FUSE sink 测试已落地；链上/协议授权半边仍是 XL，不能把 FUSE 合并视为整个 COW-2834 完成 |
| **COW-937**（第 37 行） | S ✅ 已完成 | ✅ **2026-08-11 已合入 runner `devnet`（PR #213）**。真实 QUIC/FUSE 访问模式、manifest round-trip、cache stress 测试已进入 CI；测试使用 recording hooks 代替真实链，因此不覆盖链上授权边界 |
| **COW-1143**（第 24 行） | XS | ✅ **2026-08-07 已完成关闭**。创世银行预置已实装（`genesis.rs` 的 `bank_operator` / `bank_stablecoin_whitelist` / `bank_fiat_mint_signer` / `bank_cby_reserve`）；决定「216 保持休眠不移除」并记录冲突结论 |
| **COW-1283**（第 29 行） | XS | ✅ **2026-08-07 已完成关闭**。决定「测试网清空重来，在线迁移留给将来主网」；零实现成本已核实（仓里没有任何状态迁移机制） |

**从快赢移出的三条：**

| Issue | 改判 | 原因 |
|---|:--:|---|
| **COW-2824**（第 17 行） | S → **M**，优先级不降 | `pvm/Lib/cowboy_sdk` 是随节点二进制发布的 RustPython 标准库，FSM 编译发生在链上 import 时 → 混版本机群分叉，需旗日升级。另发现 `timeout_blocks` 同样失效（Issue 未记） |
| **COW-2184**（第 46 行） | S → **M** | `RelayNodeProfile` 里**没有任何分片龄数据**（只有 `registered_epoch` 等中继自身时间）。要加累计字段 = 链上结构编解码变更 + 迁移 + 激活门。「把硬编码的 1 换掉」是错的 |
| **COW-1620**（第 31 行） | S → **XS** ✅ **已关闭** | 2026-08-07 完成 §13 全表核验，结论比预想更干净：**一个常量都不用加**。`SUBSET_EPOCH_BLOCKS` 在 r1.3 里零命中（幻影）；`STALE_HEARTBEAT_BLOCKS` 被 r1.3 主动废止；两个「缺失」的 `RESULT_TX_*` 其实在 **runner 仓** `crates/chain-client/src/client.rs:392-393` 且取值就是规范值；其余 7 个全部在 launch 时不可达（6 个 Mode A 专用 + `OVERLAP_BLOCKS` 等 §5.4） |

### 6.2 陷阱——排位靠前但实际难度远高于描述

| Issue | 清单位置 | 看起来 | 实际 | 差在哪 |
|---|---|---|---|---|
| **COW-2113 / COW-2152** | 必须做 第 2、3 位 | 加两道校验 | **XL** | 提交指令的线格式里没有可校验的数据，要先加清单差分见证 |
| **COW-1012** | 必须做 第 4 位 | 改一个常量 | **L** | 同时绑着 CIP-9 DEK 封装，需重封装迁移 |
| **COW-1902** | 必须做 第 7 位 | 加一个字段 | **L** | 交易级字段 = 线格式 + 签名域 + 激活门 |
| **COW-1274** | 应该做 第 1 位 | 拆开两条路径 | **L→XL** | 四层加固已叠在这个耦合之上 |

### 6.3 工作量无关——投人也开不了工

| Issue | 卡在谁 | 备注 |
|---|---|---|
| **COW-2915**（第 1 行） | 客户方：多签门限 / 签名人 / 托管 / 恢复 | 技术侧只有 S，但**创世后不可补**，时间窗最硬 |
| **COW-2109**（第 16 行） | 客户方：白皮书 §8.4 C7 修订 + 前置 COW-962 | 原清单标为「可以马上开工」，需更正 |

---

## 7. 一句话结论

按难度重排一次「先动哪只手」（已按快赢深挖结果修订）：

1. **已经落袋的**：COW-2834 的 FUSE 半边和 COW-937 的真实集成测试均已合并；剩下的是链上/协议授权闭合。COW-1143 / COW-1283 两条文书与 COW-1620 的范围修订也已完成。
2. **同时把决策推给对应的人**：COW-2915（多签，创世后不可补）和 COW-1073（桥 CIP，8 月窗口）——这两条卡的是时间窗不是人力。
3. **攒一次共识旗日升级窗口**，把 COW-2824（静默失效的守卫 + 续延超时）和 COW-2184（中继奖励累计字段）合并进去——两条都小，但各自单独开一次旗日不划算。
4. **尽早启动 COW-2113 + COW-2152 的合并线格式变更**——那是全表最长的一条链（CIP-9 规范 → 编解码 → node+cbfs 双端 → 激活门）。COW-2834 的 FUSE 半边和 COW-937 已不再是前置阻塞，但链上授权仍依赖这条主线。


---

## 8. 2026-08-07 更新汇总

### 8.1 三条 XS 已完成并关闭（零代码）

| Issue | 结论 |
|---|---|
| **COW-1143** | CIP-36 v3 优先于 CIP-28 §3.4，且该形态**代码里已经是了**（创世预置 `genesis.rs:314-355` + 运行时注册被 `system_instruction.rs:1129` 拒绝）。决定：**System 操作码 216 保持休眠不移除**——移除是线格式变更要协调滚动升级，留着零成本 |
| **COW-1283** | 决定「测试网清空重来，在线迁移留给将来主网」。清空这一支**零实现成本**：`storage/src/` 与 `chain/src/` 里没有任何状态迁移机制（`height_recovery.rs:70` 注释自称 "there is nothing to migrate"） |
| **COW-1620** | 见 §8.2 |

### 8.2 COW-1620 的 §13 全表核验结果

结论：**一个常量都不用加。**

- **两个是幻影**：`SUBSET_EPOCH_BLOCKS` 在 CIP-11 r1.3 里**零命中**（不在 §13 表、正文不提）；`STALE_HEARTBEAT_BLOCKS` 是 r1.3 主动废止的（规范第 1109 / 576 行）
- **两个「缺失」的其实存在，在 runner 仓**：`RESULT_TX_INCLUSION_GRACE_BLOCKS` / `RESULT_TX_REBROADCAST_INTERVAL_BLOCKS` 在 `runner/crates/chain-client/src/client.rs:392-393`，取值就是规范的 2 和 2，旁边有活的重播监视器 `rebroadcast_due:1089`。§10.3 本来就是 runner 侧行为，放那儿是对的——只 grep node 仓会误判
- **其余 7 个确实没有，但 launch 时全部不可达**：6 个 Mode A 专用（`PRESENCE_HARD_EXCLUDE_ENABLED` 默认 `false` + §8.4 守卫），1 个 `OVERLAP_BLOCKS` 等 §5.4 consensus 依赖。现在加进去就是没有消费者的死常量

**重开条件**：治理若启用 Mode A 硬排除，那 6 个常量变为必需。

### 8.3 CIP-25 分档理由澄清

CIP-25 项目共 25 条，**13 条已 Done**。§1.4 定义了四个验证后端，各一条 Issue：

| 后端 | Issue | 状态 | 负责人 | 在 109 里 |
|---|---|---|---|---|
| runner-committee | COW-1114 | Done | — | — |
| **原生 LC**（BLS12-381 同步委员会） | **COW-1898** | **In Progress** | **caleb@cowboy.inc（客户方）** | ❌ |
| ZK LC | COW-1896 | Todo | 我方 | ✅ 第 58 行 |
| 乐观 | COW-1897 | Todo | 我方 | ✅ 第 61 行 |

**109 清单没有漏。** node 上 4 个开放 bridge PR（#1191/#1200/#1257/#1271）是客户方在做 COW-1898，按「归我方处理」的范围定义被正确排除。

**COW-1896 不能因为原生后端要来了就关掉**：COW-1121（双后端 K-of-N 纵深防御，**已 Done 且归我方**）的验收要求两个锚点一致才接受承诺；原生是第一个，ZK 或乐观得有一个当第二个。

**但有三条无人负责的上线门控跟进项不在 109 里**（8/5–8/6 才建，均为 COW-1898 的 Marshal 复审跟进）：

- **COW-2973** —— 原生 LC 的失败被刻意做成不可归责（无法区分伪造分支与 `lc_electra_epoch` 配错）。代价：伪造分支的中继**照拿报酬、`completions += 1`、EMA 满分**，影响委员会选举与 VRF 权重
- **COW-2977** —— `MAX_ANCESTRY_WALK` 从 8192 降到 2048，中继侧拷贝还是 8192，且中继分支从未推送。后果是「拿钱不干活且无人察觉」（落进 COW-2973 的免费搭车类）
- **COW-3012** —— 激活高度**只门控节点不门控中继**；部署带中继的构建后，一次 `register_chain(backend=1)` 就能让桥卡死

这三条的紧迫性高于 109 里那 7 条 CIP-25。

### 8.4 「在修 / 已修」扫描结果

扫了 8 个仓的开放 PR、分支名与近 4 个月合并 commit：

- **真正在修 1 条**：COW-2914（node#1221 + cbfs#118，OPEN Draft，修复中）
- **✅ 8/7 已合并 1 条**：COW-2842（cbss#83，squash 合入 cbss `main`，见 §8.6）
- **已合并部分修复 1 条**：COW-2884（commit `a07dfed9`，7/31）
- **⚠️ 误报 2 条**：COW-2824 被 node#1158 引用，但该 PR body 明写 "Out of scope, pre-existing … filed as COW-2824"；COW-2896 被 cbfs#127 的文件清单牵连，但 diff 里没有任何费率改动
- **事实上已（大部分）完成但 Issue 状态滞后 5 条**：COW-1139 / COW-1143 / COW-1281 / COW-2178 / COW-2109；其中 COW-2178 已由 node#1282 明确关闭
- **其余约 100 条完全没动**
- **代码状态补充（08-11）**：COW-2834 FUSE 半边已由 cbfs#129 合并；COW-937 已由 runner#213 合并；两者不再应标记为“进行中/等待 FUSE 半边”

### 8.5 修订后的动手顺序

1. ✅ COW-1143 / COW-1283 / COW-1620 —— 已关闭
2. ✅ **COW-2834 FUSE 半边 + COW-937** —— 已合并；应转入验收和链上边界补齐
3. 攒一次共识旗日窗口，合并 COW-2824 / COW-2184 / COW-1911 / COW-1917 / COW-1147 / COW-1152
4. 尽早启动 COW-2113 + COW-2152 的合并线格式变更（全表最长的链）
5. 把 §8.3 的三条 CIP-25 门控项拉进视野

### 8.6 COW-2842 完成记录（cbss#83，2026-08-07 合并）

CIP-24 release-receipt 的 spawned e2e（`cbss/crates/cbssd/tests/e2e/`），**是第一个端到端跑通 `handle_cbss_submit_release_receipt` 记录 `cbss.release.receipt_recorded` 的东西**。合并进 cbss `main`（squash）。

**难度实证：看起来是「补个测试」，实际是 M——难在两处影响半径而非代码量：**

1. **可达性设计**（对应难度模型的 D1 授权链）：receipt 授权链要求 `body.actor` 既是 job submitter 又是已部署 actor，而部署 actor 是无私钥的衍生地址、当不了 tx sender ⇒ 只能走 **actor-initiated**：部署带 `secrets.read`+`storage.kv` manifest 的 guest actor,由它 `runner.mcp(...)` 发 deferred JobSubmit,submitter 才=actor。原 build map 的「harness 直送 JobSubmit」不可达。
2. **真跑才暴露的 7 个 bug**（unit test / `--no-run` compile-gate 全看不见）：fresh 账户 404 funding、actor 按**模块级函数**解析 entrypoint（`@actor` 类方法要加 wrapper）、FSM 存续约需 `storage.kv`、`runner.mcp` 的 **server/tool 必须传 kwarg**(FSM 编译器把位置参数塞进 `payload.args`,node `build_intent` 读 `tool_name` 只认 kwargs)、以及诊断管线。

**并且揪出一个跨仓陷阱（本文难度模型 D3 的活样本)**:最后一步 `E1726 malformed partial / BLS pairing` **不是 live bug**——是**分支陈旧**:cbss `main` 已在 #80(`f6224c7`)port 了 COW-2923(mpk 绑进 release identity,pin `cowboy-protocol@76942600`=node 同 rev),而 PR 分支建于 #80 前、仍 pin `b25f67d`(pre-COW-2923)。cbssd 签无-mpk 的 identity、node 验有-mpk 的 ⇒ 配对失败。**merge main 后即绿。**

**教训(补进难度模型)**:(a) **测试没真 spawned-run 跑过 ≠ 已验证**——compile-gate 与 unit test 都抓不到 runtime/跨仓 skew;(b) 诊断跨仓 crypto 一致性前**先把分支 rebase 到最新 base**,否则陈旧 pin 会伪装成 live 跨仓 bug。这条也印证了 §1 的核心判断:**难度由影响半径(可达性设计 + 跨仓 pin)决定,不由代码量。**


---

## 9. 2026-08-11 代码对比更新：哪些已落地，哪些只是把风险锁进测试

本节不重新计算 109 条 Issue 的原始排序，而是把 08-06 文档与当前 `devnet`、已合并 commit、以及 `node#1303`/`cbfs#131` 配对 PR 的实际代码逐项对照。重点是区分三种状态：**功能已合并**、**测试已合并但链上边界仍未闭合**、**新增代码只是把现有行为显式记录下来**。

### 9.1 本次对比的精确版本

| 仓库 | 当前工作基线 | 与本评估直接相关的事实 |
|---|---|---|
| `node` | `devnet@b06bbdbf` | `node#1303@486f5ffa` 尚未合入；target-volume 参数、授权矩阵和 rollout 逻辑只存在于该 PR 头 |
| `cbfs` | `devnet@232c8e4e` | cbfs#129（COW-2834 FUSE）和 SDK/test-support placement 已合入；cbfs#131 当前头 `79cc28e` 尚未合入 |
| `runner` | `devnet@baea4fb0` | runner#213（COW-937）已合入真实 QUIC + FUSE 集成测试 |
| `cowboy-protocol` | `devnet@d5ed2c8` | 本轮没有新的 COW-2113/2152 线格式变更落地 |
| `cowboy` | `devnet@7226b6f` | CIP-9 规范仍是评估链上授权边界的依据 |
| `gateway` | `main@392b4ad` | 本轮未发现会改变 109 条清单难度判断的合并 |

### 9.2 逐项代码对比结论

#### A. COW-2834：FUSE 访问模式的 S 级部分已完成，但链上部分没有随之完成

当前 cbfs 已有三层 FUSE 侧防线：

- `fuse/src/lib.rs:67-99, 209-210` 将 `ReadOnly` 映射为 `MountOption::RO`，并保留 `ReadOnly` / `WriteOnly` / `ReadWrite` 的显式模式；
- `fuse/src/fs.rs:142-226` 的 `require_read`、`require_write` 和 `open` 访问模式检查覆盖了内核无法表达的 WriteOnly 读限制；
- `fuse/src/fs.rs` 的读、写、目录、删除、重命名等 sink 均先经过相应门控，且权限位按 grant 被屏蔽。

这些不是只读代码：cbfs#129 已合入，runner#213 又通过真实挂载验证了 `EROFS`、`EACCES`、`0o444/0o644` 和可写正例。因此原文“FUSE 半边开工中、等待 COW-937”的判断已经过时，应改为“FUSE 半边完成，COW-937 已完成”。

但这不等于 CIP-9 授权整体完成。node 当前授权路径仍允许 runner token 进入 `COMMIT_MANIFEST`，而 `execution/src/ras.rs:534-600, 4221-4319` 没有按 private/public visibility 强制 stage/finalize、prefix 或 token quota；这正是 COW-2113、COW-2152 以及新增 COW-3134 类工作的链上部分。

#### B. COW-937：真实客户端/存储栈测试已合并，链上仍是 recording hook

runner#213 新增：

- `crates/runner-storage/tests/cip9_access_modes.rs`：真实 FUSE 挂载下的 RO/WO/RW 读写边界，并在 FUSE 不可用时 **fail** 而不是静默 skip；
- `cip9_manifest_roundtrip.rs`：真实 QUIC 节点、纠删码、shard 上传、placement、manifest commit、重新打开和根一致性；
- `cip9_cache_stress.rs`：缓存压力路径。

这把 COW-937 的“测试工程”从 S/⏳推进到 **已合并**。但 `manifest_roundtrip` 明确使用 recording hooks 代替真实链，因此它证明的是 runner↔cbfs 存储闭环，不证明 node 执行层的 commit authorization。换言之，COW-937 不再阻塞 FUSE 验收，也不能降低 COW-2113/2152 的 XL 难度。

#### C. COW-2113 / COW-2152：node#1303 与 cbfs#131 没有实现这两条链上校验

当前配对 PR 增加的是“请求目标卷”信息和授权矩阵锁：

- node RPC `rpc/src/handlers/ras.rs:2850-2910` 解析可选 `volume_id`；
- node 的 runner/owner validator 在 `ras/src/lib.rs:2246-2316, 2677-2713` 对**存在且格式正确**的请求卷做相等性检查；
- cbfs hook 在 `hooks/src/cowboy.rs:1498-1506` 开始把 volume 发到 `/ras/tokens/validate`。

但 `CommitManifestInstruction` 仍没有 public manifest 差分或路径见证，`TaggedShardRef` 仍不能让链上反推出每个 relay 的真实字节增量。故原文把 COW-2113/2152 评为 XL 仍然成立；新 PR 只是补了另一条授权维度，不是这两条的实现。

#### D. 新增关联：COW-3038 / COW-3132 的难点是跨仓 rollout，不是比较函数本身

`node#1303` 的纯 validator 测试已经覆盖“同卷允许、异卷拒绝”，但生产 rollout 仍有两个明确的兼容窗口：

1. `request_volume_from` 对缺失、非法 hex、错误长度返回 `None`，validator 以 `is_none_or` 放行；旧 relay 或畸形请求因此暂时没有 target-volume binding；
2. execution commit path 仍把 `request_volume` 传为 `None`。当前 helper 之前已经检查 `token.volume_id == commitment.volume_id`，所以这条 `None` 本身不能直接构成跨卷 commit，但它没有把 execution 的真实路径纳入新矩阵，也没有替代 future activation。

因此：COW-3038 的本地矩阵锁可评 **M**；COW-3132 的完整交付应评 **L**（node + cbfs 协同、旧 relay 兼容、endpoint 测试、fleet cutover、最终拒绝缺失字段），不能按“加一个可选字段”评 S。

#### E. 新增关联：COW-3135 触及 shared shard 的数据与生命周期，难度高于单点授权修复

cbfs#131 的目标是让同一个 shard 记录多个引用卷，但当前 diff 暴露出三类必须一起处理的状态问题：

- `node/src/handler.rs:973-981` 在 shared-delete 分支用 `store.put(..., &[], &updated)` 更新 metadata；`BlobStore::put` 的 data 是完整 payload，因此可能把仍被引用的 shard bytes 写成空值；
- `node/src/volume_events.rs:72-85, 286-305, 325-340, 415-456` 明确只让 authorization 读取 `cbfs.volume_ids`，poller、promotion 和 volume GC 仍按单一 `cbfs.volume_id` 工作；最后写入卷的删除/GC 可能误删另一个卷仍在使用的 bytes；
- `hooks/src/cowboy_owner_auth.rs:92-106` 的 public read 仍只检查单值 metadata，早先引用卷可能被拒绝读取；同时 read/merge/write 的普通 `put` 没有 CAS，并发加入引用可能 lost update。

这不是把一个字段加入 metadata 的 S/M 工作，而是 storage API、事件归属、GC、public read 和并发更新的联合改造。当前应将 COW-3135 评为 **L→XL**，并要求数据保留、生命周期和并发不变量的端到端测试。

#### F. 新增关联：COW-3134/commit authority 是共识激活问题，不是 runner 测试问题

node 当前 `validate_commit_authorization` 对存储中的 runner token 使用 `RunnerBinding::TrustToken`，并把 runner operation 固定为 `COMMIT_MANIFEST`。`validate_token` 对 `WRITE_ONLY` 允许该操作，之后直接进入 `apply_manifest_commit`。CIP-9 §7.3.1 要求 private WriteOnly 子代理只能 stage，由 DEK 持有者 finalize；当前路径还没有执行 `path_prefix`、累计 `max_bytes` 或 runner principal 绑定。

这条风险在 node#1303 的 PR body 中被标为后续工作，但它改变的是共识状态转换的可接受集合，不能直接在所有节点升级前“顺手补一行”。需要 activation height、旧/新节点兼容策略、runner/cbfs 联合发布和 execution-level 回归测试。因此 COW-3134 应评 **XL**，并与 COW-2113/2152 的链上授权主线协调，而不是归入 COW-937 的测试收尾。

### 9.3 修订后的难度表（只列本轮发生变化或新增的项）

| Issue / 工作项 | 原评估 | 当前代码对比后的结论 | 依据 |
|---|---:|---:|---|
| COW-2834 FUSE 半边 | S，进行中 | **S ✅ 已合并** | cbfs#129；FUSE 门控、权限位和挂载级测试均在 `devnet` |
| COW-937 | S，等待 COW-2834 | **S ✅ 已合并** | runner#213；真实 QUIC/FUSE 测试进入 CI，但链由 recording hook 代替 |
| COW-2834 链上/协议半边 | XL | **XL，未降级** | commit authority、visibility、prefix、quota 仍需共识/跨仓协调 |
| COW-2113 + COW-2152 | XL | **XL，未降级** | target-volume 绑定不是 manifest 差分见证，也不是 relay delta 核对 |
| COW-3038 | 原清单未单列 | **M** | node/cbfs 双份矩阵和 source lock；本地可测，但无机械 parity CI |
| COW-3132 | 原清单未单列 | **L** | RPC rollout、旧 relay 兼容、畸形输入、fleet cutover 和最终拒绝门 |
| COW-3134 | 原清单未单列 | **XL** | execution 共识边界、stage/finalize、quota、principal 和 activation height |
| COW-3135 | 原清单未单列 | **L→XL** | shared bytes 的 metadata、GC/promotion、public read 和 CAS 并发一起改 |

### 9.3.1 当前协作状态（防止重复修复）

| Issue | 当前状态 | 证据 | 是否继续分配开发人员 |
|---|---|---|---|
| **COW-2914** | 🔨 **正在修复** | [node#1221](https://github.com/cowboyinc/node/pull/1221) 和 [cbfs#118](https://github.com/cowboyinc/cbfs/pull/118) 均为 OPEN Draft | **否**；先由现有 PR owner 收敛设计和跨仓变更 |
| **COW-2178** | ✅ **已合并** | [node#1282](https://github.com/cowboyinc/node/pull/1282)，2026-08-10 | **否** |
| **COW-1406** | ✅ **已合并** | [node#1298](https://github.com/cowboyinc/node/pull/1298)，2026-08-10 | **否** |
| **COW-2884** | ✅ **代码 backstop 已合并** | [node#1198](https://github.com/cowboyinc/node/pull/1198)；剩余为 CIP-29 规范闭合 | 不再安排同一代码修复；另立规范/activation 工作 |
| **COW-2824** | ⚠️ **没有实际修复 PR** | [node#1158](https://github.com/cowboyinc/node/pull/1158) 明确写明 COW-2824 为 out-of-scope / pre-existing | 可分配，但需新建专门 PR，不能把 #1158 视为已接手 |
| **COW-2896** | ⬜ **未发现直接修复** | cbfs#127 是 protocol pin 更新，不是计费取数修复 | 可分配；建议先由结算/共识 owner 确认三处参数来源 |

### 9.4 对执行顺序的修订

1. 将 **COW-2834 FUSE 半边**和 **COW-937** 从“待开工/前置阻塞”改为“已合并，进入验收维护”。
2. 不要因为 COW-937 真跑通过，就关闭或降级 COW-2113/2152；它们的证据仍缺在 node 的共识 commit path。
3. 先为 COW-3132 定义 rollout 完成条件：所有 relay 发送 32-byte volume、endpoint 对 malformed/absent 有测试、观测期结束后再启用缺失字段拒绝。
4. 将 COW-3134 与 COW-2113/2152 放进同一个 CIP-9 commit-authority 设计/activation 窗口，避免先修 relay 侧而让链上仍接受越权 commit。
5. COW-3135 先补“bytes 不变、引用集合不丢、任一引用卷事件可存活、并发 merge 不丢更新”的不变量，再决定是 L 还是 XL 的具体拆分。

**更新后的核心判断**：当前系统已经从“FUSE/集成测试未落地”进入“客户端数据面已能真跑，但 node 共识授权和 shared-shard 生命周期仍未闭合”的阶段。难度瓶颈已经从测试可达性转移到**跨仓协议契约、共识激活和状态生命周期不变量**。
