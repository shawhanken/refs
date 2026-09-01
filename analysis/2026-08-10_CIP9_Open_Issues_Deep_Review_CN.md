# CIP-9 未完成 Issue 深度审核

**首版日期**：2026-08-10
**复核更新**：2026-08-13（对齐 Linear 现况 + 回到当前 `origin/devnet` 重核代码）
**实施更新**：2026-08-14（6 条动手：COW-3150/3147/3134 已合入 devnet；COW-3148 转 draft；COW-2113/2152 pinned finding。详见 §0-C）
**范围**：Linear `CIP-9: Cowboy File System (CBFS)-Backed Runner Storage` 项目下全部未完成条目
**基线（首版）**：`cbfs@devnet 2a90d55`、`node@origin/devnet 9864e376`
**基线（复核）**：`cbfs@origin/devnet 7a62d99`、`node@origin/devnet 512260e7`
**方法**：不以 Issue 描述为准，逐条回到代码核验；分歧处以代码为准并写明

**证据等级**：✅ 已读代码核验 ｜ 🔶 定向 grep 佐证 ｜ ⬜ 仅据描述，未核验

---

## 0-A. 本次复核（08-13）的变化摘要

三天里发生的事比预期多。**首版的核心预测全部兑现，且冒出一整批首版没有的新工作。**

**（1）首版判为「应当 Done」的都已 Done。** 首版说 COW-2808 状态滞后、应置 Done——现已 Done（08-13）。首版判为「这一族最直接的删数据路径、还开着」的 COW-2817——已 Done（08-10）。COW-2814 也已 Done。COW-2808 家族在 Linear 里其实还有三条首版没枚举到的 follow-up，均已 Done：**COW-2816**（peer-drain 空元数据）、**COW-2818**（首部署 live set 空启动的 GC↔repair churn）、**COW-2868**（poller 跳页 + head-behind-cursor 回归）。**数据完整性一族里「COW-2808 机制本身」的边界情况已经基本收口。**

**（2）首版判为「杠杆最高」的 COW-3038（cbfs 不变量注册表为空）已 Done**（08-12，cbfs#131）。同批把 **COW-937**（CIP-9 集成测试）也做完了（08-12，cbfs#130 + runner#213）。

**（3）出现一整批 08-12 的安全审查新 Issue（COW-3131 ~ COW-3151），首版完全未涵盖。** 这批多数由 cbfs#131/#132/#137、node#1303/#1304、runner#213 的 Marshal 深审引出，且**几条直接延长首版已有的族**：
- **COW-3148（Urgent，无人）** —— 公共清单节点跨卷共享却无卷绑定，purge 一个卷会销毁另一个卷已提交的数据。**无需攻击者**，是数据完整性一族里的新 P0，比首版任何一条都更接近「静默永久丢数据」。
- **COW-3150（High，无人）** —— volume-events 响应有 4 MiB 客户端上限但服务端只按条数封顶，一个超大事件永久卡死 poller → **通往 COW-2808 同一结局的第四条路径**。
- **COW-3151（High，进行中）** —— placement gossip 不钉 `volume_id` + repair 依据它重绑，被污染的记录让分片删除「自我续期」。
- **COW-3132（Urgent，已 Done）** —— 卷作用域的 owner token 授权了 `SYNC_PEERS`，一个卷能力被花在全局控制面变更上。已修（cbfs#131），但留下 COW-3135/3147/3148 三条残留。
- **COW-3133 / COW-3134（High）** —— FUSE unlink/rename 在写授权下成功（违反 §7.2 delete=No）；直接 `CommitManifest` 忽略私有卷 stage/finalize、token `max_bytes`、runner↔sender 绑定（**是首版 COW-2113/2152 的三条兄弟缺口**）。

**（4）新的净变化让「无人负责」这一栏更严重。** 08-12 这批新 Issue 绝大多数 `assignee=None`，且含两条 Urgent。

> 处理建议见 §八（已按新现况重排）。首版原文的判断除 COW-2808/2817 的状态语外，代码层结论经复核仍然成立，行号随基线漂移已就地更新。

---

## 0-B. 总览（08-13 复核后）

| 族 | 首版开启 | 现仍开启 | 本次新增 | 性质 |
|---|---:|---:|---:|---|
| 一、数据完整性 | 7 | 4（+3 新） | COW-3148 / 3150 / 3151 | 已写入的数据消失，或以为写入了其实没有 |
| 二、可恢复性 | 2 | 2 | — | 出事之后能不能救回来 |
| 三、授权与计费正确性 | 4 | 4（+2 新） | COW-3134 / 3147 | 需要有人主动攻击才发生（COW-3148 例外，无需攻击者，归一族） |
| 四、访问控制与密钥 | 6 | 6（+2 新） | COW-3131 / 3133 | 功能缺口 + 规范决策 + 访问模式一致性 |
| 五、工程债与可观测性 | 5 | 4（COW-3038 已 Done）+1 新 | COW-3149 | 不直接致害，但让前四族更难发现 |
| 六、功能缺口 | 4 | 3（COW-937 已 Done） | — | 纯增量 |
| 七、产品方向决策 | 6 | 6 | — | 需要结论而非编码 |

**已从「开启」移出（Done / 终态）**：COW-2808、COW-2814、COW-2817、COW-2816、COW-2818、COW-2868、COW-2834、COW-937、COW-3038、COW-3132（Done）；COW-3135（Canceled，拆入 COW-3148）。

**归属分布（现开启项）**：我方（`pavilionledger`）约 8 条、客户方（`nicolashussein`/`chad` 等，多为已 Done 的 2808 家族）少数、**无人（`assignee=None`）超过 20 条——含 COW-3148 / COW-3150 两条待认领的高危**。

**本次审核推翻/改写的描述**：

1. **COW-2808 / COW-2817 / COW-2814 均已 Done**（首版预测兑现）。首版对 COW-2817 的「delete_expired_tentative 只做三件事、不查活跃集」是**修复前的描述**；现该路径已纳入 committed 否决 + 事件推导活跃集（cbfs `node/src/volume_events.rs` 全文已重构，`committed_metadata_with` 明确标注「COW-2817: PutShard 需要它在过期前重新盖章已提交分片」）。
2. **COW-3025 的诊断改写**（首版已给）：清单节点**有**版本字节且解码报错，问题是 COW-2112 改了叶子布局却没升版本号——复核确认 `manifest/src/dag.rs:12 NODE_VERSION=1`、`:397-399` 解码报错仍在。
3. **COW-3022 的代码里有一段成文反驳理由**（纠删码容忍单中继崩溃时的近期分片丢失）——复核确认仍在 `store/src/sled_store.rs:92-98`。
4. **首版遗漏了 08-12 的整批新 Issue**——本次补齐（见各族「本次新增」小节）。

---

## 0-C. 本轮实施更新（2026-08-14）—— 6 条动手，5 个 PR，4 合入、1 转 draft

从审核转入实施。**每个 PR 都走 Marshal 深审 + 逐轮 mutation-testing 巩固循环**（Marshal 每轮用变异测试揭示安全关键行未被测试钉住，逐一补齐后才合）。

| Issue | 交付 | 状态 |
|---|---|---|
| **COW-3150** volume-events 双封顶 | node#1322（服务端字节封顶 `cap_events_by_bytes`）+ cbfs#141（读 cap 4→64 MiB） | ✅ **两半均 MERGED** → **闭环** |
| **COW-3147** DeleteShard 存在性预言机 | cbfs#143（**item 1**：镜像 handle_get，统一 Ok + gate 于 `present && authorized`，mutation 验证 + denied-present 观测 warn!） | ✅ **item 1 MERGED**；item 2（未归属分片可读）仍开，需 peer-push wire 带卷 |
| **COW-3134** direct CommitManifest 三缺口 | node#1326（三检查 behind 一个 flag-day 激活高度，**dormant `u64::MAX`**；stage 路径也加 gap-2/3；CommitAuthorizer 返回） | ✅ **MERGED（dormant，未激活）** |
| **COW-3148** 清单节点跨卷 purge | cbfs#142（teardown 豁免 content-addressed 节点） | ⬅ **转 DRAFT（见下 §重大更正）** |
| **COW-2113 + COW-2152** | 无代码——pinned finding：**两者需合并一个 commit line-format 变更**（非门控检查） | 🔍 已升 Linear，未实现 |

### ⚠️ 重大更正一：COW-3148 的「止血」在生产中是 no-op（我三轮自评全错）

cbfs#142 的思路是「teardown 时豁免 content-addressed manifest 节点」，判别器 `is_content_addressed_manifest_node` 对存储在 `(shard_id, index)` 的字节做 `BLAKE3(bytes) == manifest_node_shard_id`。**但 manifest 节点是 erasure 编码成 fragment 存的**（`sdk/src/commit.rs:638` `cbfs_erasure::encode(stored_blob, k, m)`，每 fragment 一个 index），节点 id 由**整个 blob** 的 hash 派生 ⇒ `BLAKE3(fragment) == id` 在 `k≥2`（默认 k=4）下**永远为假**。所以 `teardown_shards_to_delete` 行为等同 pre-PR——**COW-3148 的数据丢失未被关闭**。

- Marshal 用 **production-shaped probe**（存整 blob vs SDK 实际的 fragment）在第 4 次再审抓到；**我前三轮「它有效、只是成本」的自评、以及 Marshal 前三次 review 全错**——根因是我的测试种了整-blob（SDK 从不产生的形状），byte-shape 盲点骗过所有 review。
- **同一盲点在 `handle_put` 的 content-addressed arm**（`handler.rs:900-903`，我「复用」的那个 predicate）：`put_payload.bytes` 也是 fragment ⇒ 该 arm 在生产中同样不触发，**COW-2304 的 TOFU 豁免是装饰性的**。
- **第二删除路径**（COW-3148 issue 早有记录，Marshal 第 3 轮重新证实）：普通 per-event removal 路径（`apply_event_batch`→`removals_for_volume`）同样删共享节点、无 content-addressed 豁免，且**比 teardown 更频繁**。
- **动作**：cbfs#142 转 draft（不能假关闭 live issue），PR/Linear 记录。**正确修法需 fragment-aware 判别器**（把 `ShardRefKind::ManifestNode` 从事件流穿到本地 mirror → promote 时写 metadata marker → teardown **和** removal 两路径都查），是非平凡再设计，**折入 durable fix（per-volume reference set）**。

### ⚠️ 重大更正二：COW-2113 + COW-2152 需合并一个 line-format 变更（非门控检查）

深追 SDK 记账后**证伪了「像 COW-3134 那样加个门控检查即可」**：
- **COW-2152**：`TaggedShardRef.shard_size` 现已存在（COW-2621/917 P5），但 per-relay delta 用**每-shard 的 `placement.assignments[*].node_id`**，而 commit wire 只带 `shard_index`；`relay_nodes[shard_index]` 在 rebalance/rotation/manifest-node（用独立 relay 列表）下**都不可靠** ⇒ 鏈无法用现有数据重算，用它实现会**分叉**。需 per-shard node 上 wire。
- **COW-2113**：`path_tag = compute_path_tag(path_tag_key, seq, path)` 是 keyed hash，鏈上无 key、无法验前缀 ⇒ 需 manifest diff witness。
- **两者都需 commit-instruction 新 wire 数据**，应合并一个 CIP-9 line-format 变更 + 一个激活门 + 很可能一个 spec 决策。**不是门控检查。**

### COW-3134 落地形态（已合但 dormant）

node#1326 把三个检查 behind `RAS_DIRECT_COMMIT_RUNNER_HARDENING_ACTIVATION_HEIGHT = u64::MAX`（dormant，合入 byte-identical）。**激活前须人拍板**：① 激活高度须 `≤` COW-2114（否则 gap-1 私有卷可经 stage→self-finalize 绕过）；② `max_bytes` 语义（结果总量 ≤ budget = 天花板；stage 路径是 stage-time 检查，finalize 不复查 ⇒ TOCTOU，若取天花板义须在 finalize 复查）；③ activated-path 无引擎级集成测试（纯函数已测）。

---

## 一、数据完整性 —— 现开启 4 条 + 本次新增 3 条

这一族仍是 CIP-9 最真实的风险面。首版的「写进去被删掉」主线（COW-2808 家族）已收口；现在的开口在「对偶风险」（该删的没删）、「落盘前 ack」，以及**本次新增的三条**——其中 COW-3148 是无需攻击者的新数据销毁路径。

### COW-2808 — 中继孤儿 GC 删光所有分片 ｜ **Done（08-13）** ｜ Urgent ｜ 客户方 ✅

**已闭环。** 根因修复 cbfs#109（07-27）合并，本次 08-13 状态终于置 Done（首版预测的「状态滞后」已纠正）。当前 `node/src/gc.rs` 双信号设计（committed 否决 + 事件推导活跃集）+ 隔离期结束前复查仍在。**本条不再是开口。** 家族 follow-up（下列）中 2816/2818/2868 已 Done，仅 2815/2819 仍开。

> 复核补记：cbfs devnet 在 #137（forward-port 2808 家族到 devnet）与 #139（`fix/gc-runs-after-a-clean-poll`：把孤儿 GC 收尾到一次干净 poll 之后、并按本 pass 实际轮询到的卷收窄）之后，GC 时序进一步收紧。

### COW-2817 — tentative 过期清扫不查活跃集 ｜ **Done（08-10）** ｜ High ｜ 客户方 ✅

**已闭环。** 首版判为「这一族最直接的删数据路径」——现已修复。tentative 清扫已纳入 committed 否决与活跃集；`PutShard` 重新盖章逻辑改为 `committed_metadata_with`（`volume_events.rs:142` 注释直接标 COW-2817）。**首版对此条的整段描述为修复前状态，保留作史。**

### COW-2814 — GONE 分支丢弃恢复载荷 ｜ **Done（08-10）** ｜ High ｜ 客户方 ✅

**已闭环。** 与 COW-2868（poller 跳页/回退）同批处理。注意其失败签名（poller 永久卡死 → 分片泄漏/被删）在**本次新增的 COW-3150 里以另一条路径复活**，见下。

### COW-2815 — committed 标记单向不可降级 ｜ Backlog ｜ Med ｜ 客户方 🔶

**仍开启，且随 COW-2808/2817 修复而风险上升。** committed 否决信号现在是主要保护，越强则「该删的留着」越危险。复核：`volume_events.rs` 有 `committed_metadata` / `committed_metadata_with` / `volume_bound_metadata`（只绑卷不盖 committed，注释明确「不让 GC 的 committed 否决把从未/不再属于已提交集的分片永生化」），但**仍无降级/清除 committed 的路径**，与首版一致。

**与本次新增的关系**：COW-3151 的自我续期删除、COW-3147 的未归属分片，都与「元数据单向/无卷维度」同源。

### COW-2819 — COW-2808 加固汇总 ｜ Backlog ｜ Low ｜ 客户方 ✅（部分）

**仍开启。** 首版建议「把『活跃集不裁剪』拆出来单排」仍成立——`live_shards` 只增不减是长期内存/存储增长问题。其余打包项随家族收口价值下降。

### COW-3022 — PutShard 落盘前就 ack ｜ **Todo** ｜ 无优先级 ｜ **无人** ✅

**仍开启。** 复核确认：
- `store/src/sled_store.rs:99-100 should_flush_per_write()` 默认 `false`，仅 `CBFS_FLUSH_EVERY_PUT=1` 开启 —— ✅
- 成文反驳仍在 `sled_store.rs:92-98`（K+M 纠删 + 自主修复容忍单中继崩溃丢近期分片；per-write fsync 在 macOS APFS 上 ~30ms/put 打死吞吐）—— ✅

**判断不变**：需要裁决而非直接改默认值；Issue 自给的 **group commit** 方向同时满足两边，且是 COW-3023 的同一答案。

> ⚠️ **优先级注记**：首版标此条为「P0」。Linear 现字段为 **No priority**（Todo）。首版的 P0 是风险判断而非 Linear 字段；两者不一致，处理时以风险判断为准，但别把 Linear 当成已标 P0。

### COW-3023 — blob_http store 同样先 ack 后持久 ｜ **Todo（08-12 由 Backlog 升）** ｜ 无人 ✅

**仍开启，状态已推进到 Todo。** 与 COW-3022 同一个解（group commit 给 fsync 频率上界），**应合并为一条工作**。「未鉴权路由」既是持久性问题也是资源耗尽面。

### ➕ COW-3148（本次新增）— 公共清单节点跨卷共享无卷绑定，purge 一卷销毁另一卷已提交数据 ｜ **Todo** ｜ **Urgent** ｜ **无人** ✅

> **[08-14 更新]** 试过 teardown 豁免止血（cbfs#142），**Marshal 证明在生产中是 no-op**（manifest 节点是 erasure fragment、predicate 永不触发）→ 已转 draft，**数据丢失仍全开**（且有第二删除路径 = removal）。正确修法需 fragment-aware 判别器、折入 durable fix。详见 §0-C 重大更正一。

**这是本族新的 P0，且无需攻击者。** 从 COW-3135（已 Canceled）拆出的残留。

**核验**：`shard_id = BLAKE3(volume_id ‖ path ‖ write_id)` 的卷绑定**对清单节点不成立**——`manifest/src/dag.rs` 里 `Public` 分支 `stored_blob = plaintext`，`volume_id` 只用于 `Private` 分支，于是 `locator = BLAKE3(plaintext)`（`dag.rs:539`）、`shard_id = BLAKE3("cbfs.manifest-node.v1" ‖ locator)`（域串 `dag.rs:15`、hasher `:237`）**完全不含卷**。两个公共卷任何字节相同的 DAG 节点落到同一物理分片。

**数据丢失路径**（`volume_events.rs` 单标量 `cbfs.volume_id` 槽、last-writer-wins）：卷 7 写节点 N → 卷 8 写同字节 N 覆盖归属为 8 → 卷 8 进入 Deleted/GC → purge「归属卷 8」的每个分片含 N → 卷 7 已提交清单仍引用 N，字节已没。CIP-9 §13.3 purge 不可逆，无恢复路径。

**判断**：**先要一个规范答案**——「一个物理分片能否被多卷引用」，牵动 §10.2 租金归属、§5.6 PoR 覆盖、§13.3 purge 是否变「除非另有卷引用」。**不能靠本地推断解决**（COW-3135 试过，四视角评审后被回退）。次生：token 读路径 `handler.rs:1057-1060` 的 `auth_volume = shard_volume.or(volume_id)` 让卷 7 token 在覆盖后读不到共享节点。

### ➕ COW-3150（本次新增）— volume-events 4 MiB 客户端上限 vs 仅按条数的服务端封顶 → 一个超大事件永久卡死 poller ｜ ✅ **DONE（08-14）** ｜ High

> **[08-14 更新]** **已闭环**：node#1322（服务端 `cap_events_by_bytes` 字节封顶 + 保证 ≥1 事件）+ cbfs#141（读 cap 4→64 MiB）**两半均已合入 devnet**。两半须成对合，node 先——已按此序合。详见 §0-C。

**通往 COW-2808 同一结局的第四条路径。** `devnet`/`main` 上均既存，cbfs#137 只把字面量提成常量。

**核验**：中继端封 4 MiB（`node/src/volume_events.rs:22 MAX_VOLUME_EVENTS_RESPONSE_BYTES`），链端只按条数封 `limit.clamp(1, 1024)`（`node/rpc/src/handlers/ras.rs:2069`）且整体序列化无字节上限。`TaggedShardRef` 把每个 `[u8;32]` 序列化成 32 个十进制数（约 438 B/ref）。单事件上限 `MAX_COMMIT_FINALIZE_SHARDS=65_536`（`node/ras/src/types.rs:584`）→ 65536×438 ≈ 27.4 MiB ≈ 6.9× 客户端上限，**任何 `limit` 值（含 1）都取不到可解析页**。`read_limited_json` 是硬错非截断，`?` 在写游标前吞掉，客户端 `limit` 是 `const` 不退避。410 GONE 重播也救不了（prune 要全部 relay ack，卡死 relay 高水位冻结）。poller 卡死 → 分片不晋升不标 live → 孤儿 GC 删除（`gc.rs:81-102`），**与 COW-2808 同一终态**。

**判断**：服务端按字节 + 条数双封顶并回报实际到达位置为最小修法；客户端 halving 退避只能救普通页，救不了单超大事件。

### ➕ COW-3151（本次新增）— placement gossip 不钉 volume_id + repair 依据它重绑 → 分片删除自我续期 ｜ **In Progress** ｜ High ｜ 无人 ✅

**核验**：`handle_peer_placement_update`（`node/src/handler.rs:2529`，diff 策略体 `~:2565-2604`）比对 k/m/密文大小/`shard_hashes`/`(shard_index,node_id)` 对称差，**不钉 `new_record.volume_id == old_record.volume_id`**（复核：全函数 grep `new_record.volume_id == old_record.volume_id` 零命中）；`validate_placement_record`、`merge_replica`（version-LWW）也都不看卷。被污染记录持久落地后，`repair.rs` 用 `record.volume_id` 重绑（`:451-467`/`:515`/`:536`）→ repair 变成删除的「投递机制」：重构→重绑到被拆卷→poller teardown 删→循环，**损失自我续期而非可修复**。

**前提**：需要链上已注册、被 owner 翻到 `Draining` 的中继（受损/有 bug 的 relay，非无权攻击者）→ 定 High 非 Critical。**修法**：diff 策略钉 volume_id（必要不充分）+ drain handoff 覆盖签名 / 从链上派生卷 + 给 teardown 分支（`volume_events.rs:302-318`）加上 GC 已有的 committed 否决 + live-set 两道否决（同时覆盖 `UndeleteVolume` 窗口）。

---

## 二、可恢复性 —— 2 条

### COW-3025 — 清单节点线格式不向前兼容 ｜ Backlog ｜ 无优先级 ｜ **无人** ✅（诊断需改写）

**仍开启。** 复核确认诊断改写成立：`manifest/src/dag.rs:12 NODE_VERSION=1`、编码 `:371`、解码校验并报错 `:397-399`（"unsupported manifest node version"）。**问题是 COW-2112 改了 `ObjectDescriptor` 布局却没升版本号**，新旧都自称 v1，解码器按新布局解旧字节得语义错误而非版本错误。

**修法两段**：(1) 立「改布局必须升版本」纪律（黄金向量测试锁住）；(2) 为已写出的 v1 存储做布局探测/回退解码——**历史债，纪律解决不了**。「静默返回空」是最坏失败模式。

> 关联：COW-3149（本次新增，见五族）与 COW-2832 同属「版本演进纪律」主题。COW-3025 的 P0 同样是风险判断，Linear 字段为 No priority。

### COW-3024 — 中继多库无跨库原子性 ｜ Backlog ｜ 无人 ✅

**仍开启。** 复核确认三处 `sled::open`（行号随基线再移）：

```
node/src/main.rs:158  sled::open(.../"placements")
node/src/main.rs:201  sled::open(.../"registry")
node/src/main.rs:370  sled::open(.../"volume_events")
```

与 COW-3022 是同一根因两面（单库不 fsync / 跨库无排序）。方向（合为一 `Db` + 多 `Tree`）正确，与 COW-3029（blob 改普通文件）互补不矛盾。

---

## 三、授权与计费正确性 —— 现开启 4 条 + 本次新增 2 条

首版关键差别仍在：**这一族多数需要有人主动攻击才发生**（COW-3148 是例外，已归数据完整性一族）。

### COW-2113 — 公开卷提交前缀限定 ｜ **Todo** ｜ High ｜ 我方 ✅

> **[08-14 更新]** pinned finding：`path_tag` 是 keyed hash（`compute_path_tag(key,seq,path)`），链上无 key、**前缀根本不可验** ⇒ 需 manifest diff witness（line-format 变更），**与 COW-2152 合并一个 commit line-format 变更 + 激活门**。非门控检查。详见 §0-C 重大更正二。

**仍开启。** 复核确认 `execution/src/ras.rs:4221 validate_commit_authorization` 三条授权分支仍无路径前缀检查；`CommitManifestInstruction` 仍无路径信息，也不约束 `new_root` 是 `prev_root` 有界差分的见证。修法是给提交指令加**清单差分见证**（CIP-9 线格式变更 → 编解码 → node+cbfs 双端 → 激活门），工作量比 Issue 暗示高一个量级。

> **新增关联 COW-3134**（见下）是本条的三条兄弟缺口——同一个 `validate_commit_authorization` runner 分支。

### COW-2152 — per_relay_effective_deltas 核对 ｜ Backlog ｜ High ｜ **无人** ✅

> **[08-14 更新]** pinned finding（**推翻「加个门控检查即可」**）：`TaggedShardRef.shard_size` 现已存在，但 per-relay delta 用**每-shard 的 placement 节点**，commit wire 只带 `shard_index`，`relay_nodes[shard_index]` 在 rebalance/rotation/manifest-node 下不可靠 ⇒ 链无法重算、用它实现会**分叉**。需 per-shard node 上 wire，与 COW-2113 合并一个 line-format 变更。详见 §0-C 重大更正二。

**仍开启。** 复核确认 `execution/src/ras.rs:3864 validate_relay_deltas` 只做三件事（条数上限、node_id 不重复、求和等于 `effective_size_delta`），从不引用 `added_shards`/`removed_shards`；`TaggedShardRef` 无字节数，链上无从反推每中继字节。与 COW-2113 同一根因，**必须同一次线格式变更一起做**。

### ➕ COW-3134（本次新增）— 直接 CommitManifest 忽略私有 stage/finalize、token max_bytes、runner↔sender 绑定 ｜ **MERGED（dormant，08-14）** ｜ High

> **[08-14 更新]** 三检查已实现并合入（node#1326），behind flag-day 激活高度 **`u64::MAX`（dormant，合入 byte-identical）**；gap-2/3 也应用到 stage 路径（防 leaked token 经 stage→self-finalize 绕过）。**激活前须人拍板**：激活高度 `≤` COW-2114、max_bytes 语义（+ stage TOCTOU）、activated-path 集成测试。详见 §0-C。

**是 COW-2113/2152 的三条兄弟缺口**（Issue 自己点明：2113 管公共卷前缀、2152 管每中继 delta，本条管另外三样）。`validate_commit_authorization` 的 runner-token 分支（`~ras.rs:4236`）检查 `token.volume_id==commitment.volume_id`、`valid_from`、`validate_token`（WriteOnly 允许 COMMIT_MANIFEST）后即应用提交，**不检查**：

1. **私有卷无 stage/finalize 路由** —— `commitment.visibility` 在授权路径从不被读，私有卷 WriteOnly runner 直接 finalize，绕过 DEK-holder 边界（stage 路径已建，无人强制走）。
2. **token `max_bytes` 提交时不校验** —— `max_bytes` 在 `ras.rs` 全文不出现；`~:4529` 的 `QuotaExceeded` 是 `MAX_COMMIT_FINALIZE_SHARDS` 分片数上限，非字节预算。
3. **token `runner_address` 不绑交易 sender** —— 泄漏的 runner CapToken 可被任意 sender 重放至过期。

**修法约束**（与 COW-3132 的 node#1304 同一函数）：每条新增检查都改变验证者接受的内容 → **需要激活门与协调 rollout，非直接补丁**。回归测试要断言「决策」而非参数。

### COW-927 — `/ras/challenge` 接口 + 链上挑战记录 ｜ Backlog ｜ Med ｜ 我方 ⬜

**仍开启。** 存储承诺的验证入口；无它则 PoR 缺可外部触发的起点。与 COW-2623 同属 PoR 面。

### COW-2184 — 中继持续奖励 ｜ Backlog ｜ Low ｜ **无人** ✅

**仍开启。** 复核（行号已移）：`relay_reward_weight(shard_count, shard_age_epochs)` 现在 `ras/src/lib.rs:2949`（方法）与 `:3019`（自由函数），两个活调用点 `execution/src/ras.rs:1532`、`:3456` 仍硬传 age `1`；`RelayNodeProfile` 仍无分片龄数据。正确解是 profile 加按 epoch 累加字段（链上结构编解码变更 + 迁移 + 激活门），**不是换掉硬编码 1**。

### ➕ COW-3147（本次新增）— DeleteShard 存在性预言机 + 未归属分片可被任意卷 token 读取 ｜ **item 1 DONE（08-14）** ｜ High ｜ 无人 ✅

> **[08-14 更新]** **item 1（存在性预言机）已修并合入**（cbfs#143）：handle_delete 镜像 handle_get，统一 Ok + gate 于 `present && authorized`，mutation 验证 + denied-present 观测 warn!；**item 2（未归属分片可读）仍开**——peer-drain producer 已被 COW-2816 消除，剩历史 pre-key 分片，需 peer-push wire 带卷才能把 `.or(volume_id)` 改拒绝。详见 §0-C。

**COW-3132 修复刻意留下的两个授权缺口**（GitHub cbfs#136）。

1. **DeleteShard 成存在性预言机（#131 引入的回归）**：分片自身卷现在到达验证者，「present 但卷不符 → ErrAuth」与「absent → Ok」分歧，持任意卷 token 者可区分「本中继是否持分片 X」。违反 COW-2311 存在性隐藏纪律（状态/载荷/时序三者要在非授权结局间一致）。可利用性低（`shard_id=BLAKE3(volume_id‖path‖write_id)`、`write_id` 128-bit CSPRNG，探测 X 须已持 X），但**低可利用 ≠ 合规，是否能带此回归发布应由规范 owner 明确拍板**。
2. **未归属 present 分片可被任意卷 token 读**：`handle_get` 用 `shard_volume.or(volume_id)`，无 `cbfs.volume_id` 的分片让调用方自选被校验的卷。`handle_peer_relay_push_shard`（`handler.rs:2216`，Issue 引 ~2061 已随基线漂移）存 `HashMap::new()`，**每个 drain 吸收的分片无卷**（repair 无此形状，写 `repaired_metadata`，`repair.rs:451/515/536`）。修法：peer-push 线格式带上卷（兼容步骤），之后 `.or(volume_id)` 回退可改拒绝。

---

## 四、访问控制与密钥 —— 现开启 6 条 + 本次新增 2 条

### COW-2829 — 卷访问提升为一等权限类别 ｜ Backlog ｜ 我方 ⬜
CIP-9 §7 的技术方案选择，我方可定。

### COW-2830 — sealed-DEK 读取路径 + CBSS 端点发现 ｜ Backlog ｜ 我方 ✅
**核验（首版）**：runner 侧分片解密已实现（`runner/crates/runner-storage/src/lib.rs:608`、`:643 decrypt_sealed_dek_partial`）。缺链上端点发现 + 两端串联。**比标题窄。** 与 COW-1546 二选一（见下）。

### COW-1546 — Secrets-Manager 直取 sealed-DEK ｜ Backlog ｜ **无人** ⬜
CIP-9 v2 方案选择，与 COW-2830 是同一问题两条路线，**应二选一**。

### COW-2833 — 长效流式写入凭证 ｜ Backlog ｜ 我方 ⬜
与 COW-2113 前缀限定有交互——凭证越长效，前缀缺口暴露窗口越大。

### COW-3036 — 写-only 挂载下同步守护的语义 ｜ **Todo（08-12 由 Backlog 升）** ｜ Med ｜ **无人** ✅
**来源**：cbfs#129（COW-2834）Marshal 五轮反复提出。核验：`cbfs/fuse/src/sync.rs` 在 COW-2834 分支零 diff，无 `access_mode` 引用；`GET_SHARD`/`PUT_SHARD`/`COMMIT_MANIFEST` 在守护路径不受限。**这是 CIP-9 规范问题**——拉取周期是推送增量基准，写-only 上禁掉很可能让写不了；§12.1.4 对后台同步只字未提。**先定语义再实现。**

### COW-3039 — chmod 在部分授权挂载上静默保留看不见的位 ｜ **Todo（08-12 由 Backlog 升）** ｜ Low ｜ **无人** ✅
核验：被掩位读回是 0，「回显视图」与「清掉该位」线上相同；cbfs#129 选择保留（否则每个 `cp -p` 失败），代价是 `chmod 0600` 在写-only 上报成功不生效。**需 CIP-9 §12.1.4 补一句 chmod 语义**（该节现对 chmod 只字未提）。

### ➕ COW-3131（本次新增）— access_mode 被两处相反地解读 ｜ **Todo** ｜ 无优先级 ｜ 无人 ✅
COW-937 集成测试（runner#213）暴露，测试钉住、刻意不在那里修。`ManagedAttachment.access_mode` 是无校验的 wire `String`，两处默认相反：`open_volumes`（`runner-storage/src/lib.rs:271`/`:281`：`!= "READ_ONLY"` → 未知串**可写**、fail-open）vs `is_writable`（`:810`：`== "READ_WRITE" || "WRITE_ONLY"` → 未知串**非授权**、fail-closed）。未知串（`"rw"`、空串、大小写错）→ 挂成读写 + per-job，而 caller 被告知不可写，无日志。今日受限于「只有自家调度器产生该值」。修法首选：边界解析成 enum，两消费者读 enum 不再分歧。

### ➕ COW-3133（本次新增）— FUSE unlink/rename 在写授权下成功，违反 §7.2 delete=No ｜ **Todo** ｜ High ｜ 无人 ✅
cbfs#131 引出。§7.2 三种模式（含 READ_WRITE）`Delete Objects` 均为 **No**，§12.1.4 映射 `unlink→EPERM`、`rename→ENOTSUP` 无条件。但 `fuse/src/fs.rs:608 unlink_at` / `:662 rename_at` 只 `require_write()?` 后即执行 → WRITE_ONLY/READ_WRITE 挂载能删/改名，删除进 staged manifest 并被 sync 用 runner token 提交、node 接受、**持久**。shard 级 `DELETE_SHARD` 正确拒 runner，但这在清单级绕过。cbfs#129 从无守卫改成写门控（更接近正确但仍违 §7.2），并把两者从「read-write 授权允许每个 mutating 入口」的正向控制里移出记为偏差。**修法**：两者改无条件拒绝（`EPERM`/`ENOTSUP`），**是行为破坏**（编辑器 rename-into-place、agent shell 的 `rm` 都会开始失败），需 runner UX owner 拍板 + 查 sync daemon 是否自身依赖 unlink/rename。

---

## 五、工程债与可观测性 —— 现开启 4 条（COW-3038 已 Done）+ 本次新增 1 条

### COW-3038 — cbfs 不变量注册表为空 ｜ **Done（08-12，cbfs#131）** ｜ Med ✅
**已闭环。首版判为「本族杠杆最高」——已做。** cbfs#131（`test/cow-3038-cip9-invariant-anchors`）锁住访问模式矩阵、强制每个 Operation 被分类、锁验证者实际应用的策略、把 sink 表从「defending a spec violation」拉正并把两张网格绑定。**后续各族回归的自动捕获能力已建立。**（同 PR 顺带修了 COW-3132 owner token 绑定。）

### COW-3026 — 多数 `InvalidData` 无日志 ｜ Backlog ｜ **无人** ✅
**仍开启。** 复核：`execution/src/ras.rs` 有 **178 个** `RasInvalidDataSite::` 站点（数量未变），`ras_diag`/`track_caller` 命中仍极少。放大一、二、三族的排查成本。

### COW-3040 — synthesized uid/gid/times 原样入清单 ｜ Backlog ｜ Med ｜ **无人** ✅
**仍开启（既有代码）。** `make_attr_with` 合成挂载主机 uid/gid/墙钟，`setattr_at` 原样存回 → `cp -p` 往返把主机本地值写进 `PosixMetadata` 并哈希进内容寻址 DAG，**同一对象清单字节取决于哪台主机做的往返**。（与 COW-3148 同一「内容寻址却掺入非确定输入」主题：`fuse/src/sync.rs` 对不在 inode 表的目录供 `PosixMetadata::default()`，正是跨卷字节相同的配方。）

### COW-3037 — FUSE `access()` 忽略 mask ｜ **Todo（08-12 由 Backlog 升）** ｜ Low ｜ **无人** ✅
**仍开启（既有）。** cbfs#129 让报告的权限位受授权掩码收窄，但 handler 仍自说自话。

### COW-2832 — Runner↔验证者版本/格式协商 ｜ Backlog ｜ 我方 ⬜
**仍开启。** 格式不符时静默失败而非明确报错——`cowboy-protocol` 仓要根治的那类。与 COW-3025、COW-3149 同属「版本演进纪律」。

### ➕ COW-3149（本次新增）— GET_MANIFEST 缺 manifest_root、验证客户端路径是死代码、公共 auth 偏离 §5.3.2 ｜ **Todo** ｜ Med ｜ 无人 ✅
查 COW-920（AMEND 9-G）能否关闭时暴露（COW-920 已 Duplicate 终态）。RPC dispatch 真实完整（`cbfs/types/src/lib.rs:459` → `handler.rs:1322 handle_get_manifest`），但三处偏离 CIP-9：(1) 响应不带 `manifest_root`（§5.3.2 MUST 验证不可实现——root 反而是**请求**字段 `GetManifestPayloadV2`）；(2) 唯一验根客户端函数 `sdk/src/fetch_manifest.rs:398 verify_public_manifest_response` **零生产调用者**（生产仍走 K-shard DAG 路径 `volume.rs:350`/`:770`），AMEND 9-G 号称 ~5× 提速的单-RPC 路径是死代码；(3) 公共 auth 与 §5.3.2 分歧。**修法**：响应补 `manifest_root` 或修订 §5.3.2 描述实际的 client-supplies-root 设计。

---

## 六、功能缺口 —— 现开启 3 条（COW-937 已 Done）

- **COW-937**（集成测试，我方）—— **Done（08-12）**。cbfs#130 + runner#213；随 COW-2834（FUSE 访问模式，Done）解锁后完成，并**衍生出 COW-3131**（access_mode 双读）。
- **COW-2831**（零配置客户端，我方 ⬜）—— 从手工配置改为链上自发现。
- **COW-2623**（PoR 响应批量提交，无人 ⬜）—— 恢复并发挑战上限。与 COW-927 同属 PoR 面。
- **COW-1363**（节点侧纠删扇出，客户方 ⬜）—— 上传一次、节点间自行纠删，写入 RPC 降约 5×。**与 COW-3022 有交互**（改写入路径持久性边界），两者应互相知会。

---

## 七、产品方向决策 —— 6 条

共同点不变：**需要一个结论，不是一段代码。** 躺 Backlog 排期是错的形态。（本族 08-13 无状态变化。）

### COW-3053 — 单写者卷约束要不要放开 ⬜
代价具体：杀掉 Homestead「每客户端拥有自己的卷、直接写」的自然架构，逼出「actor 作为单写者」。

### COW-3031 — 未提交读可见性 ⬜
§18.2 future work。带版本分片 ID（含 `write_id`）下，读者无法预测未提交写的分片地址，协调者读不到子智能体尚未提交的输出。**与 COW-3053 应一起决策**（都决定 CBFS 能否支撑多智能体协作，答案互相牵制）。

### COW-3029 — 分片 blob 存储改普通文件（git 式）⬜
声明**不是对 sled 的指控**（小型记录继续留 KV，即 COW-3024 范围）。sled 维护现状：稳定版 `0.34.7`（2021）、1.0 重写停在 `1.0.0-alpha.124`（2024-10）。

### COW-3028 — 独立（无 Cowboy）上手路径从未被外部验证 ⬜
§11 记录七个 hook 本地实现、`hooks` crate 有 `standalone` feature，但**团队外没人跑通**。而此路径是「CBFS 是通用系统而非 Cowboy 子系统」定位的全部依据。

### COW-3027 — 对比 S3/Storj 基准 + 分片尺寸分布 ⬜
探索性，是 COW-3029 的输入（不知分片尺寸分布无法判断改普通文件是否划算）。

### COW-2099 — CIP-9 重写总单 ｜ Med ｜ 我方 ⬜
原参考文档 `cip-9-rewrite-ideas.md` 已找不到。**办法：不要再找那份文档**，照现在的代码与 CIP-9 重列范围。本文档（含 08-12 新批）可作该重列输入。子任务 COW-2827/2828/2829/2830/2831/2832/2833 挂在本条下，其中 2827/2828 已 Done。

---

## 八、建议顺序（08-13 复核后重排）

> **[08-14]** 下表为审核期建议顺序，**实施状态以 §0-C 为准**：COW-3150 已闭环、COW-3147 item 1 与 COW-3134（dormant）已合入；COW-3148 的止血被证明 no-op（转 draft，数据丢失仍全开，需 durable fix）；COW-2113+2152 确认需合并一个 line-format 变更。剩余待推进的高危：COW-3148（durable fix + §4 规格决策）、COW-3151、COW-3022/3023、COW-3147 item 2。

首版顺序里 1/2/3/4 的多数已 Done。重排后：**新的 Urgent 数据销毁项排前，规范决策与线格式变更居中**。

| # | 动作 | 条目 | 理由 |
|---|---|---|---|
| 1 | **拍板 COW-3148 的规范问题（多卷能否共享一分片）再实现** | Urgent，无人 | 无需攻击者的数据销毁；本地推断解决不了（COW-3135 已被回退证明）；牵动租金/PoR/purge |
| 2 | **修 COW-3150（volume-events 双封顶）** | High，无人 | 通往 COW-2808 同一终态的第四条路径；服务端字节+条数封顶是最小修法 |
| 3 | **完成 COW-3151（placement 钉 volume_id + teardown 加双否决）** | High，进行中 | 已 In Progress；顺带覆盖 UndeleteVolume 窗口 |
| 4 | **定 COW-3022 + COW-3023 的 group commit 方案** | 无人 | 两条同一解；代码里的反驳要裁决，不是直接改默认值 |
| 5 | **COW-3132 的三条残留**：3147（DeleteShard 预言机 / 未归属分片）、3134（直接 CommitManifest 三缺口）、3135 拆出的 3148 | High/Urgent | 都在 COW-3132 修好的边界上；3147 item 1 的「能否带回归发布」需规范 owner 拍板 |
| 6 | **合并做 COW-2113 + COW-2152 + COW-3134** | High | 同一次 CIP-9 线格式 / 同一 `validate_commit_authorization`；全表最长依赖链；均需激活门 |
| 7 | **收尾 COW-2808 族残留**：2815 / 2819 | 客户方 | 家族主体已 Done；建议把 2819 的「活跃集不裁剪」拆出单排 |
| 8 | **访问模式一致性 + spec 决策**：3131（enum 化）、3133（unlink/rename 拒绝，行为破坏需拍板）、3036 / 3039（写-only 语义 / chmod，§12.1.4 补文） | High/Med/Low | 多数是 CIP-9 §7.2/§12.1.4 规范先行 |
| 9 | **给 COW-3053 + COW-3031 一个结论** | 产品决策 | 不该在 Backlog 等排期 |
| 10 | 其余按族推进 | — | COW-3149/3025/2832 同属版本演进纪律，可同批 |

### 需要人拍板（08-13）

1. **COW-3148**（新，最高）—— 一个物理分片能否被多卷引用？租金/PoR/purge 三处都要跟着答。「shards 永不共享」也是合法答案，但与已发布、刻意、带测试的 dedup 行为冲突。
2. **COW-3022 的性能与持久性取舍** —— 「多中继同时掉电」是否在威胁模型内。
3. **COW-3147 item 1** —— 能否带一个已知违反存在性隐藏纪律的回归发布 COW-3132 的收尾。
4. **COW-3133 / COW-3131** —— unlink/rename 无条件拒绝是行为破坏；access_mode 未知串该 fail-open 还是 fail-closed。
5. **COW-3053 / COW-3031** —— CBFS 要不要支撑多写者与未提交读。
6. **COW-2830 vs COW-1546** —— sealed-DEK 两条路线二选一。

### Linear 卫生（08-13）

- **首版旗舰卫生问题已解决**：COW-2808 已置 Done，COW-2817/2814 亦 Done。
- **新问题**：08-12 一整批（COW-3131~3151，除 3132 Done / 3135 Canceled）**几乎全部 `assignee=None`，含 COW-3148 / 3150 两条待认领高危**。建议至少给这两条派人并把 COW-3148 标 Urgent 的规范决策挂到 owner。
- **优先级字段**：COW-3022 / COW-3025 首版称 P0，Linear 字段实为 No priority——风险判断与字段不一致，处理时以风险判断为准。
