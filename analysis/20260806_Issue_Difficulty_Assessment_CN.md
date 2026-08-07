# 109 条 Issue 的解决难易度评估

**评估日期**：2026-08-06
**配套文档**：`20260805_Issue_Fix_Checklist_109_CN.md`（优先级）、`20260806_Issue_Checklist_109_Code_Verification_CN.md`（代码核验）
**代码基线**：`node@origin/devnet 9864e376`、`cbfs@devnet 2a90d55`、`runner@devnet 54fb0ec`、`cowboy-protocol@main 2affb5f`、`cowboy@main d2d8d37`

> **更新 2026-08-07。** 本文的评级在后续两轮深挖中被多次修订，此处汇总当前状态，详见 §8。
> - **三条 XS 已完成并关闭**：COW-1143 / COW-1283 / COW-1620（均为零代码的决策/范围问题）
> - **COW-2842 已合并**（cbss#83 → cbss `main`）：CIP-24 release-receipt spawned e2e，真跑打通并抓出 7 个真 bug + 一个陈旧 pin，详见 §8.6
> - **COW-2834 已开工**（`cbfs` 分支 `feat/cow-2834-fuse-access-mode-enforcement`）
> - **又有 6 条从 S 降为 M**：COW-1911 / COW-1917 / COW-1575 / COW-1578 / COW-1147 / COW-1152
> - **CIP-25 分档理由已澄清**：客户方正在建 §1.4 原生后端，但 109 清单的范围定义是对的
> - **COW-2830 建议 close**（08-07 复核，见 §8.7）：CIP-9 §9.2 读路径有 v1/v2 两版——v1（Dispatcher 遞交 partials，runner 本地解密）**已 landed**；「endpoint discovery / direct-fetch」半属 **COW-1546（v2，未 landed）**，v2 落地前无消费者。已贴 comment，final call 归 COW-2099 owner

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
| 5 | COW-2896 CBFS 计费取数 | **M** | ✅ | 改动局限在 `cbfs/registry-proto`，但落在结算路径上（`settle_volume_epoch:1342`），进共识面。共三处（另含 `split_storage_fee` 的 `STORAGE_FEE_BURN_BPS`、`auth/chain_state.rs:295`）。与第 13 行合包 |
| 6 | COW-1073 桥 CIP | **XL（写作型）** | ⬜ | 不是编码难，是**从零写一份规范**并覆盖锁定/铸造的资金安全论证。8 月窗口内不到四周，是全表时间压力最大的一条 |
| 7 | COW-1902 `tx.fee_payer_override` | **L** | ✅ | 交易级新字段 = D2 线格式变更（cowboy-protocol 编解码）+ 签名域变化 + 激活门。注意现有的 `fee_payer_override` 只存在于**定时器/调度指令**上（`actor_instruction.rs:1415`），不是交易级，不能复用 |
| 8 | COW-1904 代付方解析 | **M** ⏳依赖第 7 行 | ✅ | 本身是执行层的查找逻辑，字段落地后不难 |

---

## 3. 应该做（第 9–17 行）

| 序 | Issue | 难度 | 证据 | 难在哪 |
|---:|---|---|:--:|---|
| 9 | COW-1274 定时器脱离出块路径 | **L→XL** | ✅ | 耦合本身清楚（`speculative.rs` 第 9 步由 propose/verify 的 `execute_speculative` 执行）。难在**四层加固已经叠在这个耦合之上**：COW-1457 两阶段 EOB、COW-2635 wall-weight 截断、规范前缀校验、拍卖上限。且分类顺序是共识可见不变量（`cip5_5_1_due_timers_classified_before_handlers_execute`），新结构必须逐字复现 |
| 10 | COW-1911 BankErr 错误族 | ~~S/M~~ → **M** | ✅ | **08-07 复核降级。** 模板现成（`structured_error_map.rs` + RAS 的 slug 模式），现状也确实糟（`bank/handlers.rs` 里 `InvalidData` 出现 61 次）。但该文件开头明写 `code` 是 **consensus-hashed 进 `receipt_root`**，并记着 COW-2290 的分叉教训 → 拆错误码 = 改收据字节 = 需激活门 |
| 11 | COW-2834 卷访问模式 | **拆两半** | ✅ | **FUSE 侧 S**：挂载加只读标志 + 写路径加校验，单仓 cbfs、不进共识，**且它才是解锁 COW-937 的那一半**。**链上侧 XL**：随第 2 行的线格式变更走 |
| 12 | COW-1139 银行九事件 | **S** ⏳依赖 COW-1143 | ✅ | 八种已发出。补 `BankRegistered` 本身很小，但链上没有开户执行路径（`system_instruction.rs:1129` 直接 `Err(InvalidData)`）。另加事件是共识变更，需协调升级 |
| 13 | COW-2914 参数改名/拆分 | **M** | ✅ | 两个 PR 已开着（node#1221 / cbfs#118）。真正工作是**拆成两个参数** + 创世种子 + 跨 node/cbfs 同步，且要避开被第 5 行的编译期常量回滚 |
| 14 | COW-962 争议窗口 | **L** | ✅ | 新指令 + 链上挑战/证据记录 + 重验证委员会调度。**有先例可抄**：CIP-10 的容器争议窗口已实装（`container_registry.rs:859-923` + `system_instruction.rs:5905`），记录/索引/翻转的形状可直接复用，所以是 L 不是 XL |
| 15 | COW-1543 Runner 会话启动 | **M/L** | ✅ | `/session/observe` 只存在于 `examples/`，生产 runner **完全没有这条路径**。不是替换一个坏实现，是新建，跨 node + runner |
| 16 | COW-2109 罚没分配 | **⛔ + ⏳** / 技术侧 S | ✅ | 分账机制已全在，`submitter_bps` 就是 challenger 档。但 `(10000,0,0)` 是白皮书 §8.4 C7 的既定承诺，挪动它要 **Tier-3 提案 + 同步修订白皮书**（客户方），且必须等 COW-962 产出 challenger 身份 |
| 17 | COW-2824 guard_keys | ~~S~~ → **M**（优先级不降） | ✅ | **08-06 复核降级。** 改动确实小（3 文件 + pypi 镜像），但 `pvm/Lib/cowboy_sdk` 是随节点二进制发布的 RustPython 标准库，FSM 编译发生在**链上 import 时** → 混版本机群分叉，需旗日。另发现 `timeout_blocks` 同样失效（Issue 未记） |

---

## 4. 可以缓（第 18–57 行）——有代码证据的部分

| 序 | Issue | 难度 | 证据 | 说明 |
|---:|---|---|:--:|---|
| 18 | COW-1277 storage_root 重算 | **L** | ✅ | 每次 `state_set`/`state_delete` 维护 trie + 写集分级回滚 + 读路径对齐。已有钉住测试（`genesis.rs:3281`）。**必须走激活门**：字段已进 actor 叶子（`impl Write for Actor` 写 `storage_root`），首次写真值即改 `state_root` |
| 19 | COW-1103 证明先于注册 | **M** | ⬜ | 注册顺序调整 + 0x05 跨调用 |
| 20 | COW-927 挑战接口 + 链上记录 | **L** | ⬜ | 新 RPC + 新链上记录类型 |
| 21 | COW-2832 版本/格式协商 | **M** | ⬜ | 跨 node + runner |
| 23 | COW-1578 CIP-10 参数集 | ~~S/M~~ → **M** | ✅ | **08-07 复核降级。** `MAX_CPU_MILLICORES` 等全仓零命中；治理参数框架（`CONTAINER_SETTLEMENT_CONFIG_KEY` + `load_*_config`）只是最后 10%，计量点本身不存在 |
| 27 | COW-2178 卷绑定校验 | **M** | ✅ | 纯函数 `validate_route_volumes` **已实现且已测**，卡在 `ParamValue` 编不了 `array<StaticVolumeBinding>`。扩编码是主要工作，之后接线很小 |
| 28 | COW-2884 事件 gas 隔离 | **M** | ✅ | 兜底已合并且带 flag-day（`event_fire.rs:22-93`）。完整闭合需 **CIP-29 cells-budget 修订**（D4），代码侧不大 |
| 29 | COW-1283 迁移策略 | **XS** ✅ **已关闭** | ✅ | 08-07 定「测试网清空重来」；零实现成本已核实 |
| 30 | COW-1406 辅助索引重建 | **M** | 🔶 | 全仓零命中，新建；非共识面 |
| 31 | COW-1620 CIP-11 常量 | ~~S~~ → **XS** ✅ **已关闭** | ✅ | **08-07 §13 全表核验：一个常量都不用加。** 详见 §8.2 |
| 32 | COW-2538 应答超时重选 | **M** | ⬜ | 需先定做法（D4 小），改动在选择路径上，触共识面 |
| 34 | COW-2830 加密卷密钥读取 | ~~M~~ → **建议 close** | ✅ | **08-07 复核。** 读路径分 v1/v2：**v1 已 landed**——`CbssVolumeKeyRelease`（partials+vss）随 job 送进 `VolumeRuntimeAttachment.cbss_key_release`（`runner-common/types.rs:423`），runner **本地** HPKE-open→verify→combine（`runner-storage/lib.rs:555-603`），对 partials 无任何网络 fetch。「endpoint discovery」半 = **COW-1546（v2 Secrets-Manager direct-fetch，未 landed）**，v2 前无消费者，现造 = 投机码。陷阱：`/cbss/proxies` 的 `network_addr` 是 QUIC partial-sign 位址，非 runner 消费的密文 blob 端点。已贴 comment 建议折进 COW-1546 |
| 37 | COW-937 CIP-9 集成测试 | **S** ⏳依赖第 11 行 FUSE 半边 | ✅ | 只要 COW-2834 的 FUSE 侧落地就能立刻做 |
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
| **COW-2834 的 FUSE 半边**（第 11 行） | S | 🔨 **2026-08-07 开工中**（`cbfs` 分支 `feat/cow-2834-fuse-access-mode-enforcement`）。挂载加只读标志 + 12 个 sink 按模式拒绝，全在 `cbfs/fuse` 一个 crate。**做完解锁 COW-937**；但链上那半是 XL，不能因此关掉 COW-2834 |
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

1. **一到两周内能落袋的**：COW-2834 的 FUSE 半边（唯一一条真工程，解锁 COW-937）+ COW-1143 / COW-1283 两条文书 + COW-1620 的范围修订。
2. **同时把决策推给对应的人**：COW-2915（多签，创世后不可补）和 COW-1073（桥 CIP，8 月窗口）——这两条卡的是时间窗不是人力。
3. **攒一次共识旗日升级窗口**，把 COW-2824（静默失效的守卫 + 续延超时）和 COW-2184（中继奖励累计字段）合并进去——两条都小，但各自单独开一次旗日不划算。
4. **尽早启动 COW-2113 + COW-2152 的合并线格式变更**——那是全表最长的一条链（CIP-9 规范 → 编解码 → node+cbfs 双端 → 激活门），越晚开工越挤，且 COW-2834 的链上半边、COW-937 的完整验收都挂在它后面。


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

- **真正在修 1 条**：COW-2914（node#1221 + cbfs#118，OPEN 但停滞）
- **✅ 8/7 已合并 1 条**：COW-2842（cbss#83，squash 合入 cbss `main`，见 §8.6）
- **已合并部分修复 1 条**：COW-2884（commit `a07dfed9`，7/31）
- **⚠️ 误报 2 条**：COW-2824 被 node#1158 引用，但该 PR body 明写 "Out of scope, pre-existing … filed as COW-2824"；COW-2896 被 cbfs#127 的文件清单牵连，但 diff 里没有任何费率改动
- **事实上已（大部分）完成但 Issue 过期 5 条**：COW-1139 / COW-1143 / COW-1281 / COW-2178 / COW-2109
- **其余约 100 条完全没动**

### 8.5 修订后的动手顺序

1. ✅ COW-1143 / COW-1283 / COW-1620 —— 已关闭
2. 🔨 **COW-2834 FUSE 半边** —— 进行中，唯一的真 S 代码修复
3. COW-937 —— 紧随其后，访问模式那一项立刻可测
4. 攒一次共识旗日窗口，合并 COW-2824 / COW-2184 / COW-1911 / COW-1917 / COW-1147 / COW-1152
5. 尽早启动 COW-2113 + COW-2152 的合并线格式变更（全表最长的链）
6. 把 §8.3 的三条 CIP-25 门控项拉进视野

### 8.6 COW-2842 完成记录（cbss#83，2026-08-07 合并）

CIP-24 release-receipt 的 spawned e2e（`cbss/crates/cbssd/tests/e2e/`），**是第一个端到端跑通 `handle_cbss_submit_release_receipt` 记录 `cbss.release.receipt_recorded` 的东西**。合并进 cbss `main`（squash）。

**难度实证：看起来是「补个测试」，实际是 M——难在两处影响半径而非代码量：**

1. **可达性设计**（对应难度模型的 D1 授权链）：receipt 授权链要求 `body.actor` 既是 job submitter 又是已部署 actor，而部署 actor 是无私钥的衍生地址、当不了 tx sender ⇒ 只能走 **actor-initiated**：部署带 `secrets.read`+`storage.kv` manifest 的 guest actor,由它 `runner.mcp(...)` 发 deferred JobSubmit,submitter 才=actor。原 build map 的「harness 直送 JobSubmit」不可达。
2. **真跑才暴露的 7 个 bug**（unit test / `--no-run` compile-gate 全看不见）：fresh 账户 404 funding、actor 按**模块级函数**解析 entrypoint（`@actor` 类方法要加 wrapper）、FSM 存续约需 `storage.kv`、`runner.mcp` 的 **server/tool 必须传 kwarg**(FSM 编译器把位置参数塞进 `payload.args`,node `build_intent` 读 `tool_name` 只认 kwargs)、以及诊断管线。

**并且揪出一个跨仓陷阱（本文难度模型 D3 的活样本)**:最后一步 `E1726 malformed partial / BLS pairing` **不是 live bug**——是**分支陈旧**:cbss `main` 已在 #80(`f6224c7`)port 了 COW-2923(mpk 绑进 release identity,pin `cowboy-protocol@76942600`=node 同 rev),而 PR 分支建于 #80 前、仍 pin `b25f67d`(pre-COW-2923)。cbssd 签无-mpk 的 identity、node 验有-mpk 的 ⇒ 配对失败。**merge main 后即绿。**

**教训(补进难度模型)**:(a) **测试没真 spawned-run 跑过 ≠ 已验证**——compile-gate 与 unit test 都抓不到 runtime/跨仓 skew;(b) 诊断跨仓 crypto 一致性前**先把分支 rebase 到最新 base**,否则陈旧 pin 会伪装成 live 跨仓 bug。这条也印证了 §1 的核心判断:**难度由影响半径(可达性设计 + 跨仓 pin)决定,不由代码量。**
