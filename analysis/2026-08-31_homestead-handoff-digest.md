# Homestead 交接：完整解读与行动要点

**整理日期：2026-08-31（周一）｜来源：Charles DePue 的 Slack 留言 + `cowboyinc/homestead` 仓库的四份文档 + 本地 git 核实**

---

## 0. 一句话

Chad 判定 Homestead 基建 PR 太复杂、暂不落 `devnet`，于是 Charles 在四个仓库各开了一条 `homestead` 分支并把相关 PR 全部合入，`devnet` 一字未动；我们（Tony 团队）的 CIP-39 排队重写要建在这条线上，目标是**后天（周三 2026-09-02）会议前有东西跑起来**。

但核实后发现一个 Charles 留言里没有涉及、也不在 `HANDOFF.md` 里的结构性问题：**这条 homestead 线与我们已经在 devnet 上推进的 CIP-39 v2 程序正面冲突**，见 §3。这是接手前必须先解决的问题。

---

## 1. Charles 留言的实质

他这条消息传达五件事：

1. **为什么有 homestead 这条线** —— 不是技术偏好，是 Chad 的决定：Homestead 基建 PR 太复杂，现在不适合落共享的 `devnet`。四个仓库各开一条 `homestead` 分支，`devnet` 完全不受影响。他强调 "devnet completely untouched" 是在给这点背书：我们接手不会被指污染共享分支。

2. **四条分支已建好并填充完毕，不是空壳** —— 合并是真的做完了，不是建了分支等我们填。gateway 那棵合并后的树 444/444 测试全绿。

3. **merge commit 那段是提前挡问题** —— 仓库策略是 squash-only，他绕过去直接 push 了 merge commit。这不是随意操作，理由已被本地 git 证实（见 §2）。

4. **`HANDOFF.md` 是入口文档，且有意精简** —— 运维直接引用现有 `deploy.md` 不重复写，它只写这批分支引入的 delta。

5. **他说"正在补的三份文档"现在已经进仓库了** —— 在 `docs/handoff/`，随提交 `d0f9408`（"docs: check in the three deep handoff docs for the CIP-39 rewrite"）。

---

## 2. 分支线的真实状态（含 git 核实）

### 2.1 分支表（出自 `HANDOFF.md`）

| 仓库 | `homestead` head | 内容 |
|---|---|---|
| `cowboyinc/node` | `98d8882d` | `devnet` + #1461（typed `submit_wait` admission、经 mempool in-flight fence 的幂等精确重试）+ #1462（认证的 `/proof/account` 叶子、缺席账户排除证明、加固的证明验证器） |
| `cowboyinc/gateway` | `6b99ded` | `devnet`（含 #89 route-proof freshness）+ #91（测试确定性、IPv6 SSRF 前缀）+ #90（typed admission errors、`/_cowboy/submit-ready` reserve probe） |
| `cowboyinc/cowboy-protocol` | `87d5bb9` | finality-jump 感知的 `cbqs-client`（`cbd/ce0a9f8-finality-jump` 血统）。Homestead 应用和 collab relay 钉这里，**不是** devnet 的 pin |
| `cowboyinc/cbqs` | `6ccfcd9` | 与当时的 `devnet` 相同——纯粹为分支名统一而建 |
| `cowboyinc/homestead` | `main` | 产品仓库本身（apps、actor、collab relay、webeditor）。无独立分支，`main` 就是 homestead 线 |

### 2.2 merge commit 的理由已被证实

gateway 的 `Cargo.toml` 把 `cowboy-proof-verifier` 钉在 node rev `07d88a9b`。本地核实：`07d88a9b`（`fix(proof): absence carries nothing but the exclusion; taxonomy unspoofable`）**只存在于 `node/homestead`，不在 `devnet` 上**——它是 #1462 的中间提交。若走 squash，这个 sha 会变成孤儿、将来 fetch 不到，gateway 直接构建失败。

> **约束：这几条分支不可 rebase、不可 squash。** 真要动历史，先给 gateway 重新 pin。

他还说这"解开了 Marshal 的 cross-rev 循环"——意思是四个 PR 一次性在 homestead 上合齐，之前那种"跨仓库谁先合、rev 互相等"的排序死结不存在了。**这个说法对这四个 PR 成立，但不覆盖 §3 的问题。**

### 2.3 本地核实的分歧（2026-08-31 执行）

```
node:  origin/devnet    = 1ab1634c (2026-09-01 09:30 +0800)
       origin/homestead = 98d8882d (2026-08-30 18:45 -0700)
       devnet 有而 homestead 没有：6 个提交
       homestead 有而 devnet 没有：12 个提交（#1461/#1462 的内容 + 两个 merge commit）

cbqs:  origin/devnet    = f0ab2f4  "chore: delete the cbqsd v1-only surface (#39)"
       origin/homestead = 6ccfcd9  "ci(cbqs): deploy cbqsd to canyon on a main push (#38)"
       homestead 是 devnet 的祖先，devnet 恰好领先 1 个提交
```

`node` 上 devnet 领先的 6 个提交：

```
1ab1634c chore(ras): delete the dead relay-handshake copy (COW-3276 follow-up) (#1452)
e319e850 chore: delete the CIP-39 v1 chain surface and chain-proof RPC (#1465)   ←
064045d0 feat(execution): stable per-site slugs for CBSS rotation InvalidData rejections (#1439)
6cdcd7f7 fix(actor-build): harden compiler load-time validation (#1463)
a1a6b437 test(bridge): golden builder↔node tie, actor suites in CI, pin fixes (COW-3326) (#1394)
ba6234b0 fix(bridge): discover MessageSent from the proven receipts, not a pre-finality get_logs snapshot (COW-3324) (#1382)
```

---

## 3. ⚠️ 最大的未决问题：homestead 线 vs CIP-39 v2 程序

**这一节不在 Charles 的留言里，也不在 `HANDOFF.md` 里。它是本次核实发现的，且优先级高于其他所有事项。**

我们自己的 CIP-39 v2 程序（27 个 Linear issue，COW-3600..3626）一直在往 **`devnet`** 落代码，其中 D1/D2 是大规模删除 v1 表面：

- **D2 / COW-3625** = node PR #1465 → devnet `e319e850`，"delete the CIP-39 v1 chain surface and chain-proof RPC"，约 −15.3k 行
- **D1 / COW-3624** = cbqs PR #39 → devnet `f0ab2f4`，"delete the cbqsd v1-only surface"，约 −18k 行（fast / key-batch / dead-letter / dedupe / request-sigs / anchors / long-poll 全部删除）
- **C1+C2** = cowboy-protocol PR #115 → devnet `80ab157`（`cbqs_v2` 模块）

而两条 homestead 分支**恰好停在这些删除之前**：`cbqs/homestead` = devnet 减去 v1 拆除那一个提交；`node/homestead` 不含 `e319e850`。

冲突点在于：

- CIP-39 v2 文档（2026-08-24 修订）明确 **"supersedes v1 in full"，且激活方式 = reset**。
- Homestead 的**在线集群跑在 v1 的 fast 流上**——`fast_batch_max_bytes`、credit 的双维度、anchors、receipts、fast lane retention，正是 D1 删掉的那一批。
- 而 `HANDOFF.md` 结尾写的是："Whatever the rewrite produces: land it on `cbqs/homestead` + `node/homestead`（+ this repo），same branch discipline as above."

### 3.1 更进一步：CIP-39 v2 已经把 Homestead 整个移出文档

对 v2 规范正文（`cowboy/docs/cips/cip-39-cowboy-queue-system.md`，210KB，2026-08-24 修订）的核查结果，比"排序冲突"严重得多：

**v2 的 Goal 段明确列出"本文档之外、需要后续 CIP"的能力，其中四项恰好是 Homestead 的命脉：**

> "The following are outside this document and require follow-up CIPs: **an async-durable delivery class for repairable logs**, **per-lane cryptographic verification**, provider reassignment, provider staking or slashing, shared durable cursors, scheduled delivery, capacity-priced or tiered billing, **platform-managed encryption**, **CBFS archival integration**, and transport bindings other than the one in §11."

对照 Homestead 的实际依赖：async-durable 类 = 它跑的 fast 流；per-lane 密码学验证 = 它的 P3 信任拆分（每 lane 的 manifest + provider 检查点收据在 WASM 里验证）；platform-managed encryption = 它的加密流；CBFS 归档集成 = 它的 snapshotter。**四项全中。**

**量化核查：**

| 检查项 | v2 规范正文 |
|---|---|
| `fast` 出现次数 | **1**（且是 "as fast as"，与投递类无关） |
| `homestead` / `collab` / `CRDT` / `Yjs` 出现次数 | **0** |
| §16 现在是什么 | "Chain events"——**§16.2 应用边界节已不存在** |

**这直接推翻了 `cip-39-coverage-review.md` 的结论。** 那份文档"CIP-39 全面覆盖 Homestead"的判定，逐条都建立在 v1 的构造上：实时推送答案是"§12 的 fast 投递类"，应用边界是"§16.2"，验收是 v1 的 Acceptance 3/4。这些在 v2 里全部消失。**那份评审是 v1 时代的产物，已被 v2 作废——但 Charles 在 2026-08-30 把它作为"给 CIP-39 重写读的"文档 check 进了仓库。**

其余的结构性不兼容（来自 `~/workspace/cip39-v2-vs-code-gap-2026-08-31.md`）：

- v2 §4.2 从 `stream_id` 的 preimage 里删掉 `chain_id` 前缀 → **所有现存 stream id 不可达（规范有意如此）**。Homestead 那两条在线流直接失效。
- v2 §18 激活 = reset；store marker 从 `cbqs/v3` 改为 `cbqs/store-format = 2` → **现有 cbqsd store 按 v2 规则应在开启时被拒**。
- v2 的 credit **只有 bytes 维度**；而 Homestead 是刻意跑 record 维度、把 byte 维度关掉的（`session.ts` 里那个 1 TiB 常量）。**两者恰好相反。**
- v2 删除每次 append 的签名收据、删除稀疏 Merkle lane 证明——Homestead 的 proof-bundle 信任模型正建立在这两者之上。

### 3.2 结论与可选方案

**方案 A（把 v2 落到 homestead 线上）在技术上不成立**，不是代价高低的问题：v2 没有 fast 类、没有 per-lane 验证、没有平台加密、没有 CBFS 集成，Homestead 的实时协作路径在 v2 里**没有落脚点**。强行落地等于拆掉这条分支线存在的理由。

剩下两个：

- **方案 B**：homestead 线继续跑 v1 直到 Homestead 需要的四项能力有了后续 CIP，再一次性 cutover。代价是 homestead 会越拖越远离 devnet，且我们的"重写"实际上不落在 homestead 分支上——与 `HANDOFF.md` 的字面指示矛盾。
- **方案 C（推荐）**：homestead 线只承载 Homestead 自己需要的增量并保持 v1 可运行（这也是周三演示唯一可行的路径）；CIP-39 v2 继续走 devnet（C1/C2、D1、D2 已在那里）；cutover 作为独立事项排期，前置条件是那四个后续 CIP。

> **结论：Charles 说的"没有 devnet 排序问题可争了"仅对那四个基建 PR 成立。真正的问题不是排序，而是 CIP-39 v2 已经不再覆盖 Homestead——这需要 Chad 层面的产品裁决，不是分支管理问题。这是我们回给他的第一个问题。**

### 3.3 如果要让 Homestead 直接跑 v2，需要做什么

按 v2 规范正文（§8/§9/§10/§11/§12/§18）逐条核对的结果，分三类。

#### A. 能直接映射过去的（不需要新设计）

- **一 workspace 一条 stream、一页一条 lane** —— v2 §8 的 lane 仍然是 Goal 6 的"cheap logical room or document creation inside one stream"。
- **实时推送 + 背压** —— v2 §11.2 的 `Cursor` 订阅（`start = Head`）配 credit 就是 Homestead ops 分发需要的形状。Homestead 不是竞争消费，用不到 consumer group / lease 那一套。
- **写回持久化 + 快照** —— §10 的批提交 + `CheckpointReceiptV2` 仍在，snapshotter"只物化已检查点的记录"这条原则照旧成立。
- **保留期** —— §12 的 time-or-bytes 覆盖了 Homestead 的 1h 窗口需求（但见 B5）。

#### B. 必须搬进 Homestead 应用层的（v1 白送、v2 不再提供）

1. **加密与密钥轮换（最大的一块）。** v2 明确 "Payload confidentiality as a platform service, key distribution and rotation ... are **not** goals"，并把责任推给应用："applications that need confidentiality encrypt payloads"，且"confidentiality is exactly as strong as the application's own key management"。v1 的加密流、key generation、成员移除时的原子换代与前向排除（v1 §9 + Acceptance 6）全部消失。Homestead 要自建载荷加密、密钥分发、成员变更换代——一个独立且安全关键的子系统。
2. **lane 目录。** v1 的 lane id 是 `SHA-256("homestead/lane/v1\0<docId>\0<channel>\0<kind>")`，**确定性**，浏览器和 relay 各自独立算出同一个 id、无需协调。v2 §8 规定 "**`lane_id` is assigned by the broker, not chosen by the client**"，是从 1 起的 broker 计数器。因此需要新建一个持久、可认证、relay 与浏览器一致的映射（docId+channel+kind → u64），且它落在每次 join 的关键路径上——新的应用状态，也是新的故障面。
3. **去重。** v2 §9.1 "**The broker does not deduplicate appends**"——重试的 `Append` 会产生第二条记录和第二个 sequence（v1 有 broker 侧去重存储）。Yjs 层对重复相对宽容，但 relay 的 materializer 与 snapshotter 需要显式确认这一点。
4. **checkpoint 改为拉取。** v2 §10 "**There is no server-pushed checkpoint frame**"。snapshotter 现在的触发是"每个覆盖了脏 ops lane 的父 checkpoint"，要改成轮询 `GetCheckpoint`。改动不大，但会影响发布节奏与保留窗口的赛跑。
5. **credit 策略反转（但这一条 v2 更好）。** v2 §11.2 的 credit **只有 bytes 维度**，而 Homestead 刻意跑 record 维度、byte 一次性授予 1 TiB——原因是 wasm 投影丢掉了剩余余额，byte 估算偏低会造成与"空闲流"无法区分的停滞。v2 下这个规避手段不可用，必须做真正的字节记账；**但 v2 给了 `CreditShort { needed_bytes }`**，broker 会主动报还差多少字节，恰好补上 v1 缺的那个信息。所以这一项在 v2 下反而更容易做对。

#### C. 在 v2 里没有答案的——真正的硬阻塞

**per-lane 密码学验证。** 规范自己把这条说死了：

> §9：「`records_digest` is flat over the batch, so verifying a receipt means recomputing that digest — which requires holding **every** record in the batch. A party that holds only some of it **cannot**, and **no arrangement of this receipt changes that**.」
>
> §10：「a subscriber holding **only some lanes cannot verify a checkpoint at all**, because the digest is flat over the batch」
>
> §9：「Per-record binding — a Merkle path over the batch — would make a producer's own proof checkable, and is **deliberately not here** ... §11 already **declines lane-scoped verification** on the same ground.」
>
> §8：「A lane-scoped grant restricts what an honest broker serves; **it is not a cryptographic boundary.**」

Homestead 的浏览器信任模型正好是被这几句否定的那个形状：一个只被授权访问某一页的浏览器，订阅该页的 lane，在 WASM 里验证该 lane 的 manifest + provider 检查点收据。**v2 下这个动作在密码学上不可能**——要验证任何东西，必须持有整个批次的每一条记录，也就是该 workspace 所有页面的记录。

于是只剩两条路，都不可接受：

- **让浏览器订阅整条 stream**（workspace 全部页面）。违背 ACL 模型（只授权一页的成员会拿到所有页的密文）、带宽爆炸，而 §8 已经声明 lane 不是密码学边界。
- **放弃对 broker 的密码学验证**，改为信任 relay/broker。而这恰恰是 homestead#51/#53 明确拒绝的东西——`cbqs-handoff.md` 的原话是"actor 拒绝把自己的回声当证明正是这两个 PR 的用意"，并警告不要用 debug hook 绕过证明门。

> **所以"Homestead 直接用 v2"的前置条件，是 v2 Goal 段里那句 "per-lane cryptographic verification ... require follow-up CIPs" 先兑现。在那个后续 CIP 落地之前，这不是工作量问题，是没有可用的原语。**

#### D. 一次性迁移代价（无论何时 cutover 都要付）

§18 规定 "An operator MUST NOT carry version-1 chain state, broker stores, **or archived snapshot bundles** across this boundary"——**已发布的 snapshot generation 也作废**；§4.2 删掉 `stream_id` preimage 里的 `chain_id` 前缀，现存 stream id 不可达。因此 cutover 必然是一次全新 genesis + 全部 workspace 重建，用户可见内容需从 CBFS body 侧重新播种（Homestead 的持久真相在 CBFS，这一点帮了大忙）。

#### E. 建议的推进顺序

1. **先要 Chad 对 per-lane verification 后续 CIP 的表态** —— 这是唯一的硬阻塞，其余都是工作量。
2. 在那之前 **Homestead 留在 v1**（即 homestead 分支线），这也是周三演示的路径。
3. **可以立刻并行开工、且不依赖 per-lane 证明的自有工作**：把加密/密钥轮换（B1）和 lane 目录（B2）搬进应用层。这两块无论 v2 何时到来都要做，提前做等于把 cutover 的关键路径缩短。

---

## 4. 部署与运维 delta（出自 `HANDOFF.md`）

完整运维看仓库里的 `deploy.md`（拓扑为 GCP `sitch-cb`，`homestead-rpc-01` / `homestead-gateway-01` / `homestead-collab-01`，IAP 访问、充值规则、genesis 重置 runbook）。以下只是 homestead 分支引入的增量。

### 4.1 构建 / 部署顺序（有强制性）

1. **node** ← `node/homestead` → 部署到 `homestead-rpc-01`。新 wire 面（`/proof/account` 的 `encoded_operation` + 排除证明、`submit_wait` skip summary + 错误码 2023）必须先于消费它的 gateway 存在。
2. **gateway** ← `gateway/homestead` → 部署到 `homestead-gateway-01`。对着旧 node，其 `/_cowboy/submit-ready` 会**永久**报 `readiness-unknown`（fail-closed，设计如此），并在启动时打印签名。
3. **collab relay** ← homestead 仓库 `services/collab-relay` → 部署到 `homestead-collab-01`。relay 构建需要 `cowboy-protocol/homestead`（`87d5bb9`）的协议 pin。

### 4.2 Gateway 钱包：4,250 CBY 下限

每笔 gateway 签名交易声明的最坏成本是 **4,250 CBY**（16M cycles × 250k fee + 1M cells × 250k）。node 拒绝任何低于此值的钱包准入——**且 #1461 之前是静默拒绝，这就是 08-28 卡死演示的那个 bug。**

- 给 `homestead-gateway-01` 的钱包 `0xD95B906c…CAFAA` 充值要远高于下限（现维持约 400k CBY）。实际消耗约 **130–220 CBY 每次*写*调用**；sidebar/pages 轮询走免费的 `/actor/read`，因为这些路由带 `mode=read`。
- 监控 `GET /_cowboy/submit-ready`（503 + `X-Cowboy-Reason` 会说明是哪种情况：储备不足 / fee cap 低于 basefee / 缺签名者 / unknown）以及 `/_cowboy/metrics` 上的 `gateway_submit_*`（有后台探针保持新鲜）。**编排器健康检查指向 `/_cowboy/health`，绝不要指向 submit-ready。**
- 签名钱包**不得持有 vesting 锁定资金**——探针读的是原始叶子余额，node 扣的是可花余额。

### 4.3 Actor 与路由

workspace actor 在 `actor/`。路由表改动走 `actor/tools/lower_routes.py` → `routes.cbor` → owner-key `set_routes`（owner key 在 rpc-01 的 `~/deployer.key`；需要 `--cycles-limit 40000000 --cells-limit 2000000`，payload 文件放在 `$HOME` 下）。只读 handler 加 `@hs_base.read_only` 装饰器，降级为 `mode=read` 并走免费读路径。**部署了 `gateway/homestead` 之后，`set_routes` 不需要重启 gateway**——路由缓存约一个 poll epoch 内从认证状态刷新（#89）。

### 4.4 常驻定时器 / 重新 genesis

- Google JWKS 约每两周轮换。自动刷新定时器已装：collab-01（`homestead-jwks-refresh`，09:17 UTC）和 rpc-01（actor `set_jwks`，09:23 UTC）。**登录挂了先查这两个。**
- 任何 genesis 重置之后：重新注册 runner、重新给 gateway 钱包充值，并记住 **`chain_instance_id` 在 genesis 文件不变时会存活下来**——要用全新的 nonce。
- relay 日志在 collab-01 的 `/var/log/collab.log`（不是 journald）；validator 日志在 rpc-01 的 `/var/log/cowboy/validator.log`。

### 4.5 部署后的快速自检

```bash
# node 起来了、在提供证明
curl -s http://10.60.0.10:4000/height
curl -s http://10.60.0.10:4000/proof/account/0xD95B906c02bd787fCef210D73D99eD40025CAFAA | head -c 200

# gateway 可以提交了（503 的 reason 会说明缺什么）
curl -si https://<gateway-host>/_cowboy/submit-ready | head -5

# 路由是活的（今天 44 条路由，其中 3 条 mode=read）
curl -s https://<gateway-host>/_cowboy/routes/<actor> | head -c 400
```

---

## 5. 三份深度文档的要点

位置：`docs/handoff/`。定位是"**动 stream 生命周期之前先读这个，别从代码反推**"。三份都是**时点快照**——结论和拓扑可信，版本号要对着集群重新核实。

### 5.1 `cbqs-handoff.md`（812 行，状态截至 2026-08-23，起点文档）

**集群是活的，CBQS 切换已上线。** 08-22/23 做了完整 genesis 重置 + 重建：

| 组件 | 版本 |
|---|---|
| chain | node devnet `12a8300b` + `MAX_TOTAL_LIB_BYTES` 提升 |
| broker | cbqs devnet `550487c`（全新 V3 store） |
| relay | `v0.1.3-de7a26f`（强制 `google-jwt + actor-acl` 认证，CBQS 铸造 + snapshotter 启用） |
| gateway | 从 main 重建 + write-gas 修复 |
| actor | `0x710F7c871BDc7415786aC5997EF32C5A6749f7bE`，拆成 4 个 CIP-26 库 |

两条 stream（collab + suite verification）均为 fast、加密、generation 0、retention 1h，各充约 3,000 CBY（按 `rate_per_block` 74,767 够一年多）。

**打通这条路要先拆掉 5 个"天花板"**，每一个都是"限制值与机器实际能执行的不匹配"：

1. `cowboy-protocol-cbqs-client` **根本无法构造**——协议 #89 起 `SessionCore::new` 需要 `TrustedStreamBinding`，而其唯一生产者是 `pub(crate)`。CI 看不见，因为该 crate 通过 `#[cfg(test)] #[path = "../tests/session_core.rs"] mod` 走了自己的 test-only 后门。修复：cowboy-protocol#106。
2. actor 部署不了：339,562 字节 × 200 cells/字节 对 40M 每交易上限 = 超 1.70×。拆成 CIP-26 库。
3. `MAX_TOTAL_LIB_BYTES` 是**所有 pin 加总**的 131,072（不是每库），提升到 393,216（node#1408）。
4. `cowboy lib publish` gas 算错（4× 费率、20M 平坦钳制）并静默截断（node#1410）。
5. gateway 写路径只给 10M cycles 而读给 20M，导致冷加载已 pin 的库（53 cycles/字节 × 229,864 = 12.2M）**每次 POST 都 revert**（gateway#86）。

**链上验证出来、规范里没写的硬规矩（COW-3405 / COW-3404）：**

- CIP-26 的 pin **只**来自 actor 自己的顶层 import，传递性库依赖不解析（E1737）。
- 一个库只能 import **字母序更靠前**的兄弟库——库按排序顺序执行和安装，反序部署直接失败（E1210）。**库命名是承重的**：`hs_base` 排在 `hs_policy`/`hs_ws`/`hs_misc` 之前，而后者 import 它。
- 函数内（延迟）import 被 guard **禁止**。
- 实际发布上限是 User lane（`LANE_USER_CYCLES` 22,222,222 ÷ 201 = 110,558 字节），低于 `MAX_LIBRARY_CODE_BYTES`（131,072）。
- **永远不要把 handler 拆进 mixin**：`@actor` 只包 `vars(cls)` 不走 MRO，而 `_actor_methods` 用 `dir(cls)` 且 dispatch 经它解析。于是基类上的 handler 可达但**永远不会被权限包装**——`@public` 和 `@callable_by` 静默失效。Homestead 的拆分把全部 145 个方法留在类上，只把**函数体**搬进库。

**当时的两个 Open（需与 §5.3 对照）：**

- **用户测试跑不了，原因不是登录。** Google 登录能用、workspace 能激活，但 **workspace sync 在 native 和浏览器两条路径上都被同一个门禁挡住**：`WorkspaceSync.swift:292` 依赖 `core.matchesTrustedCacheEpoch`，其唯一写入者 `AppModel.admitTrustedCacheEpoch` 的**生产调用方为零**（只有测试）；`RelayEndpoint.swift:242` 在等一个 proof-bound 的 native CBQS writer；`bootstrap.ts` 的 `openCbqsTransport` 以 `trusted-stream-binding-unavailable` 拒绝。文档强调 **actor 的行为是正确的**——拒绝把自己的回声当证明正是 homestead#51/#53 的用意，并明确警告"**不要用 debug hook 来'解锁'测试**：绕过证明门拿到的通过，对持久性什么都没证明"。
- **workspace 激活是双门机器，两个门在本集群上都是手工的。** `services/role-driver` 和 `services/storage-provisioner` 未部署，workspace 停在 `billing_state=pending` / `provisioning_state=created`，所有写入返回 **409 "workspace is not active"**。手工驱动步骤：`set_billing_keys`(OWNER) → POST `/api/billing/state` 签 `homestead.billing-auth.v1`；然后 `set_role_driver_keys`(OWNER) → POST `/api/provisioning/allowance` → POST `/api/provisioning/state`。`set_billing_keys []` / `set_role_driver_keys []` 是 O(1) 吊销。

**"已定、不要再争"的决定（对重写最关键的几条）：**

- **一切留在 v1，不做协议版本升级。** lane 分区的承诺就地改变 v1 字节。（注：这是 v1 时代的决定；v2 程序是另一条轨——见 §3。）
- **只有一份 wire 实现**：Rust core + WASM binding，**绝不手写 TS 协议**。
- **lane 成员关系是按 `lane_id` 索引的稀疏树**，不是排序 map——排序 map 的缺席证明会为 *n* 个缺席 lane 泄漏 *2n* 个未授权 lane id。
- **公开分享永不接触 CBQS。** broker 只持密文且无法投影；投影由 Homestead 服务按允许清单计算（§16.2）。
- **snapshot generation 是 per lane，不是 per stream**（2026-08-15，`d72c984`，**反转了**更早的规则）。旧规则会让一次编辑就为流里每个页面重写签名 manifest 和 head 条目，反复重盖相同字节。跨流的必须是 **cursor 而非发布**——cursor 是独立的保留对象 `__cbqs_snapshot_cursor__`（未签名、relay 私有），只在一轮里每个 lane 都持久化后才写。**不要"简化"成从最小 lane head 恢复**：一个月没动的页面会把 cursor 拉回到 fast retention 之外，直接让订阅失败。默认发布间隔 5 分钟（只需跑赢 1h 上限）。
- **Homestead 跑 credit 的 record 维度，byte 维度关掉**（2026-08-15，`f032e1a`）。credit 是每订阅的流控，与链上资金无关。record 可精确计数，byte 不行——broker 扣的是完整编码帧，客户端只看到解密后的载荷，且 credit 响应里的剩余余额在 wasm 投影时就被丢弃了。估算偏低会让订阅停滞，且与"流是空闲的"无法区分。所以浏览器一次性授予远超会话所需的 byte，只补充 record——**`webeditor/src/cbqs/session.ts` 里那个 1 TiB 常量是故意的，不是笔误**。relay snapshotter 仍然两维都计量，因为 native 代码持有编码后的投递、能精确测量。
- 另有：admission head 是新鲜度元数据而非持久性证明；一个授权域一个 session；发布前无兼容机制（部署即擦链）。

**"Carry forward: the failure shapes"（比任何单个修复都更有用的 review checklist）：**

1. **描述了状态却没描述其转换。** frame 发射、epoch 重置、predecessor cursor、批次溢出、配置采纳、错误归因、finalized-view cursor——规范按链的序列描述，实现却按并发读的到达顺序。
2. **从诚实路径推出保证。** 每个错误论断都是**缺席论断**——"不可能被省略"、"不泄漏任何东西"、"被限制为两个"、"伪造需要两把钥匙"。攻击者根本不走诚实路径。
3. **用可变的当前状态而非固定的历史做决策。** anchor-conflict guard 是最干净的例子：它读订阅的*可变*检查点位置，而缓存的 transition 会把它置空，于是它恰好在会话持有签名证明时**自我解除**。
4. **规范里记下的决定，在到达实现之前不算决定。** v2 revert 在 CIP-39 里躺了 12 小时，codec 和 broker 同时 ship 了相反的东西，PR review 还是干净的——因为 diff 自洽，只有 CIP 不同意。**当一个 spec 提交反转了某个选择时，去代码里 grep 它反转掉的那个东西。**

三条给操作者的：**看工具报告的版本，不是你要求的版本**（本地 clippy 整天干净而 CI 一直红，破绽是帮助链接写着 `rust-1.97.0`）；**一个会丢弃自己没请求的帧的测试，会在恰好不发那些帧的机器上通过**；**绿和红都不是证明**（一个 209/0 的全套通过之后几分钟，同一套里就撞上了 15% 概率的竞态；修复的验收门槛是 6/40 → 0/60，不是"下一次跑绿了"）。

### 5.2 `cip-39-coverage-review.md`（97 行）

> ⚠️ **这份文档已被 CIP-39 v2 作废，见 §3.1。** 它的每条论证都建立在 v1 的构造上（§12 fast 投递类、§16.2 应用边界、v1 的 Acceptance 3/4），而这些在 2026-08-24 修订的 v2 里全部消失。以下内容仅作为**理解 Homestead 依赖什么**的清单来读，不能作为"CIP-39 覆盖我们"的现行依据。

**（v1 语境下的）结论前置：CIP-39 全面覆盖 Homestead 用例**——Homestead 本来就被设计进 CIP，有自己的应用边界章节（§16.2）和两个强制 genesis 验收 fixture（Acceptance 3 和 4）。

需求逐条对照：多 Yjs 房间不产生 463 条链记录 → 一条链上 stream 对应一个统一的加密成员/保留/提供者/计费域（通常是一个 workspace），每页一条 broker **lane**；廉价连接认证 → **StreamGrant**（管理员签名的持有证明能力）；CRDT / 光标 / presence 实时推送 → **fast** 投递类；写回持久化 + 快照 → 每批次的持久检查点，CBFS 快照只从已检查点的记录物化，**快照节奏必须跑赢保留期**；离线恢复 → manifest 发现 → 快照水合 → replay → 本地 diff 重新 append；损坏事件不再静默 → broker epoch 带签名的 Clean/Void transition。

**四个 caveat（都在 CIP 里披露，均不阻塞）：**

1. **幽灵 presence**：v1 没有 broker 生成的订阅者离开事件，粗暴断连会留下过期 presence 直到 awareness 超时。
2. **链上没有 provider 失效的补救**：broker 消失时 v1 唯一的路径是从现存持久锚点做迁移。**对 Homestead 而言这让 CBFS 快照节奏成为硬可用性要求，而不是卫生习惯。**
3. **跨机密边界共享页面是一次迁移**，不是一个开关：新父流、重新加密、重定向、验证锚点、关闭旧 lane。
4. **加密搜索的代价是边界扩张**：搜索 workload 成为加密域成员，拥有被授权的明文访问。

**CIP-33 交叉依赖**：snapshotter 和 search indexer 是**两个不同的特权域**，需要分别 scope 的卷/前缀，且搜索 workload 额外持有 CBQS 加密成员资格。CIP-33 v1 的绑定是每次 hire 一对（runner, artifact），所以 Homestead 要么**跑两个 hire**（今天可行，文档建议这个），要么等多绑定 hire。两个付费时钟**互相独立**：CBQS stream 租金是自己的 escrow（§6），与 Trading Post 的 `paid_through` 没有原子耦合——服务必须把"订阅过期"和"stream 租金耗尽"当成两个独立的存活状态，编排规则是：订阅过期 → 停止写入，但**继续把租金续到保留窗口之外，好让锚点存活**。

**排序建议**：CIP-33 的改动小且立刻解锁十个 store 应用，CBQS 大且只卡 Homestead 的实时层——先落 ServingBinding，CBQS 走自己的轨道并以 Homestead fixture 作为验收驱动。

### 5.3 `finality-jump-handoff.md`（137 行，2026-08-27 晚）

Chad 要求从源头修 checkpoint-too-old 的设计缺陷（"Eve 休假回来，她的客户端再也用不了了"）。

**已 ship 并线上验证的锚定 finality jump**：比 65536 头视野更旧的检查点永远无法再同步，而中间高度的证明不可服务——任何离线约一天的客户端就砖了。关键洞察是：连接头本来就是**未认证的摘要原像**，只有 tip 的门限证书在固定共识身份下被验证；因此超出连续视野的**单头 bundle 在信任上等价于完整 walk**。已部署到 `homestead-rpc-01`，线上实测：checkpoint_height=4713（超出视野 77k）→ 200、一个头、3.3KB、0.18 秒。同时把 `CBQS_CHAIN_PROOF_RATE_PER_SEC` 默认值从 1 提到 10（证明缩到约 3.3KB 后，1/秒的限流反而饿死了多客户端 relay）。

**清掉它之后暴露的五个既有缺陷连锁**（文档标注"不要重新发现"）：courier 隧道死掉（已恢复）；checkpoint too old（已修）；应用防篡改——手工编辑受信协议下限会被 keychain 持有的摘要检测到；relay grant caps（relay 用固定 1MiB caps 铸造 StreamGrantV1，超过链上 StreamRecord 的 `max_message_bytes=65536`，proof-bound 客户端 fail-closed；已修为 `min(constant, stream cap)`）；以及——

> **仍然是 REAL BUG，只有 workaround：gateway actor POST 会楔死。** actor POST 走 `submit_wait` 交易，并发派发会竞争 gateway 账户 nonce，且**任何 validator 重启都会清空 mempool 并让 nonce 搁浅**。症状：`pages/list` 的 POST 永久挂起，mempool 计量往上爬。绕过办法：`systemctl restart cowboy-gateway`——**每次 validator 重启后都要做，编辑器开页突发之后也常要做**。

**empty-lane origin 已裁决并 ship（08-27 19:52Z，Chad 定的）**：broker 的分类是诚实的——剪枝之后它无法证明 scope 为空；而"对已验证的 Pruned 失败关闭"只在 lane 是应用**唯一**持久性来源时才正确。持久真相在 lane 之外的应用（Homestead：CBFS body + snapshotter）现在**显式 opt-in** 从签名的剪枝边界加入：Pruned 在签名的 `previous_checkpoint` 下把验证锚定到 `first_retained`（保留后缀完整验证），FullyPruned 则越过 `last_pruned` 转入实时，缺口经既有的 history-gap 通知浮出。**绝不重新标记为 empty**（Codex 关于"洗白"的顾虑被尊重）。实现落在 `SessionCore::set_join_pruned_origin` + `from_origin_pruned` / `from_origin_fully_pruned`、wasm `openSession` 的尾随 `joinPrunedOrigin` 标志、以及 webeditor 的 `session.ts` join 分支和 bootstrap 选项；提交在**两条** protocol 分支上（devnet `bd66e14`，deployment base `87d5bb9`）。

**当晚的实况证明**：全新页面 `2b713e51` 走通 challengeAccepted → sessionOpened → subscriptionOpened ×3 → creditAccepted → appendProvisional seq4..12 且投递匹配——"**这条栈上第一个可用的 proof-bound 编辑器会话**"。UI 显示了设计好的 history-gap 提示，无失败状态。旧页面 `8fc6bf39` 仍被正确拒绝（verified-pruned 且无快照——按设计就是死的）。

---

## 6. 对我们 CIP-39 重写的直接约束

**分支纪律**：基于 `homestead` 开发，PR 回到 `homestead`，成果落 `cbqs/homestead` + `node/homestead`（+ homestead 仓库）。不碰 `devnet`。不 rebase / 不 squash 这几条分支。**——但这条纪律与 §3 的冲突直接相关，落地前需先解决 §3。**

**必须保留或有意识替换的不变量**：`webeditor/src/cbqs/bootstrap.ts` 是 `HANDOFF.md` 点名的那个文件——hydrated-snapshot 与 pruned-lane 的 origin 处理、有界的 hydration-drop 回退、以及"有损加入仅限 document-writer"这个契约。若重写改变 stream origin / 剪枝语义，这些就是要保留或明确替换的对象。

**lane id 的双实现契约**：`SHA-256("homestead/lane/v1\0<docId>\0<channel>\0<kind>")`，在 `webeditor/src/cbqs/lanes.ts` 和 `services/collab-relay/src/lanes.rs` 各实现一份。**Rust 测试钉的是 TypeScript 侧生成的向量**——两边一致是 snapshotter 和浏览器叫同一个 lane 的唯一保证。

**proof-bundle 的授权形状**：`GET /rooms/:room/cbqs/proof-bundle` 按房间做 ACL 门禁。**stream 是服务配置，lane 集合由被授权的房间派生——两者都不是请求参数。** 若其中任一变成请求参数，一个只被授权访问某页的调用者就能点名另一页的 lane 去读它的快照。

**escrow 是 base units（wei 级）**：broker 错误 **3902** 就是传了整数 CBY 的症状。正确尺寸是 `rate_per_block × 86,400 × days`。（历史教训：`stream-create --escrow 1000000` 只买到 13 个块，然后每个 session 都被 `3902 stream is economically suspended` 拒绝。）

**一个我们会直接继承的缺口**：CIP-39 §6 的**最低费率下限 `CBQS_MIN_RATE_PER_BLOCK = 8,000` 至今未实现**，因此一个零费率报价今天可以合法跳过销毁。创建费本身已由 node#1343 落地（不可退还的 `rate × 604,800` 原子性地与 escrow 一起烧到零地址）。这一项在 `cbqs-handoff.md` 里标注为"对 Chad 开放"。**如果重写要碰计费面，这是现成的继承缺口。**

**审查面的空白（我们自己要补）**：Marshal **从未审过 `cbqs` 仓库的任何东西**（0 条评论，对比 `node` 的 454 条）；`cowboy-protocol` 的不变量门是空的（`cli invariants --repo cowboy-protocol` 返回 `[]`）——COW-3099 在跟。此外 **wasm 桥没有字节等价性门**：`cowboy-protocol-cbqs-wasm` 出的浏览器收据验证器由 CI 构建、打包、冒烟跑，但**没有任何东西把它的字节和 native 验证器的字节做比较**（`cbss-wasm` 有对committed 向量语料库的比对，CBQS 没有）。**在那个语料库存在之前，浏览器路径是"构造上验证"而不是"门禁验证"。**

---

## 7. 陷阱清单（可直接当 checklist）

- **`stream-create --class fast` 用默认 flag 会被静默拒绝**——`--retention-ms` 默认 7 天，超过 fast 的 24h 上限，而 CLI 只打印一个 tx hash。必须显式传小于 24h 的值。
- **provider 的 base-rate 预留在十条默认流之后耗尽**，之后每次创建都被拒，CLI 照样打印 tx hash。要传 `--retained-bytes 16777216`，不要用 CLI 默认的 1 GiB。只有 `stream-close` 会返回上限信息。
- **`COWBOY_PRIVATE_KEY` 必须导出**，否则 `stream-create` 报 `insufficient_balance` 却仍然打印 tx hash。
- **`VerificationModeV1::None` 永远收不到检查点帧。** fast 消费者若要验证过的检查点，必须用 `FullStream` 或 `ScopedProofs`（且 `ScopedProofs` 拒绝 `Any` scope）。最自然的第一次尝试会挂起。
- **epoch-transition 的 announce 会与请求响应交错。** 一个"读下一帧当作响应"的客户端会坏掉。必须缓冲非请求帧——丢弃它们正是之前那个平台相关挂起的成因。
- **未加密的流完全拒绝 wasm 客户端**（`!stream.encrypted` 时 nonce 必须为零，而 wasm 总是加密）。对 Homestead 无碍，对其他人是真实的能力缺口。
- **Grant 生命期上限**：`expires - not_before > cbqs.max_grant_ttl_ms`（默认 24h）→ 3906。`not_before` 取 epoch+1 会被直接拒绝。
- **e2e harness 三个二进制都用 `target/debug`。** 重新 `--release` 构建不改变任何行为，却要花一小时——文档说这比任何真实缺陷浪费的时间都多。
- **磁盘耗尽会说谎。** 100% 时表现为 `extern location for X does not exist`、`could not parse/generate dep info`、后台命令输出为空——**从不表现为磁盘错误**。
- **squash merge 之后要重新 pin。** 分支头上的 pin 是一根松线头。

---

## 8. 需要回给 Charles / Chad 的问题

1. **（最高优先，需 Chad 产品裁决）CIP-39 v2 已经把 Homestead 移出文档** —— 见 §3。v2 的 Goal 段把 async-durable 投递类、per-lane 密码学验证、平台加密、CBFS 归档集成**四项全部列为"本文档之外、需要后续 CIP"**，而这四项正是 Homestead 的命脉；v2 全文 `fast` 只出现 1 次（且无关）、`homestead`/`collab`/`CRDT`/`Yjs` 出现 **0** 次，§16.2 应用边界节已不存在。因此：**我们不能把 CIP-39 v2 落到 homestead 分支上**，而 Charles check 进仓库的 `cip-39-coverage-review.md` 是 v1 时代的产物、结论已被作废。需要 Chad 决定 Homestead 的实时协作路径归属，以及那四个后续 CIP 的排期。
2. **`HANDOFF.md` 有一处陈旧描述** —— 它说 finality-jump 文档留着"一个待团队裁决的 open item（empty-lane origin）"，但该文档开头就写着已于 08-27 19:52Z 裁决并 ship（提交在 `bd66e14` / `87d5bb9`）。这恰好是 `HANDOFF.md` 里唯一让人以为还有 blocker 的地方，建议他改掉。
3. **CIP-39 §6 最低费率下限未实现** —— `CBQS_MIN_RATE_PER_BLOCK = 8,000`，零费率报价可合法跳过销毁；`cbqs-handoff.md` 里标注为对 Chad 开放，至今未见处置。
4. **gateway nonce 楔死是 REAL BUG，目前只有重启 workaround** —— 每次 validator 重启后都要 `systemctl restart cowboy-gateway`。周三演示前需要知道这个是否已被排期，还是我们照旧带着 workaround 跑。
5. **ACL actor 的历史遗留** —— `cbqs-handoff.md` 记录旧 ACL actor `0xa7835273…` 随旧链消失、其 Caddy vhost 仍 502；不确定当前 actor `0x710F7c87…` 是否已完全取代它。建议确认。

---

## 9. 出处与核实方法

- Charles DePue 的 Slack 留言（上午 11:23）。
- `cowboyinc/homestead` 仓库根目录 `HANDOFF.md`（151 行，2026-08-30 起草，随 `d0f9408` 提交）。
- `cowboyinc/homestead` 仓库 `docs/handoff/`：`cbqs-handoff.md`（812 行）、`cip-39-coverage-review.md`（97 行）、`finality-jump-handoff.md`（137 行）。
- §2.3 与 §3 的 git 事实由本地 `git fetch` + `git log` / `git rev-list` / `git merge-base` 于 2026-08-31 核实，命令与输出见正文。
- CIP-39 v2 程序状态（COW-3600..3626、C1+C2 `80ab157`、D1 `f0ab2f4`、D2 `e319e850`）来自我们自己的程序记录，并已对 `cbqs` / `node` 仓库核对。

> 三份深度文档均为时点快照。**结论和拓扑可信，版本号请对着集群重新核实**——这是文档作者自己的告诫。
