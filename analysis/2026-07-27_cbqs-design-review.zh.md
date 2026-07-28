# CBQS 设计稿深度审计：可行性、技术风险、新概念涌现度

**审计对象**：`refs/analysis/2026-07-27_cbqs-design.zh.md`
**审计日期**：2026-07-27
**判决**：`escalate` — 方向成立，失败模式写得比一般设计稿诚实，但存在 **2 个 HIGH 级前提错误**足以改变 v1 范围决策，另有 1 个 v1 边界自相矛盾。

**本次审计的范围与限制（如实声明）**：审计对象是设计文档而非代码 diff，因此 marshal 的不变量门禁与 `/code-review ultra` 对抗式 review **均不适用、均未运行**。以下全部结论来自对一手源（`cowboy/docs/cips/`、`cowboy/docs/whitepaper/`、`node/`、`cowboy-protocol/`、`cbss/`、`runner/` 的实际代码与规格）的逐条核对，证据路径均以 `文件:行号` 形式给出，可独立复核。未派遣子代理。

---

## 0 结论摘要

**判决：`escalate`。方向对，但 v1 范围必须先改再动工。**

### 三句话版本

CBQS 想补的洞（持久链下协调层）是真的，失败模式写得比一般设计稿诚实。但它的两个关键论据建在错误前提上：**它把一个已经部署在链上的协议当成草案**，并且**用一个治理可调参数当作结构性阻挡**。修正这两点之后，v1 有 30–50% 的新概念会直接消失。

### 两个 HIGH 级前提错误

1. **CIP-7 Watchtower 不是草案，是已部署的正典 stream 协议**（系统 actor `0x0D`、2390 行 handler、CIP-25 硬依赖）。它已经有 push/pull、replay window、`CURSOR_TOO_OLD`、per-epoch 密钥轮换、CBSS 托管、X25519 收件人、`WrappedContentKey`、CBY 计费，并明写支持 100–10,000 订阅者。CBQS 在链下把这整套词汇重造一遍且语义不同。
2. **「CBSS 64-principal ACL 上限」不是墙**，是 §4.5 治理参数；CIP-24 的 ACL 是 runtime gate、`wrapped_dek` 是 O(1)。真阻挡是 job 绑定。结果是 v1 最大的自建件（envelope 扇出 + companion key stream）建在一个 CBSS 团队可能自己补掉的洞上。

### 一个不可交付的边界

provider handoff 同时是「CIP 前待设计的开放问题」和「v1 验收门槛」，而 v1 交付清单里 epoch / fencing / continuity anchor 一项都没有。单 provider 独占 hash chain + leases + cursors = 单点故障，CBFS 靠抹除码与自主修复回避的问题，CBQS 全部承接却没有对应机制。

### 新概念涌现度：**高**

约 25 个新名词，其中约 8 个与 CIP-7 同名不同义（这是最贵的一类，会长期毒害 SDK 与文档）、约 4 个与 CBFS 同义但语义漂移。`consumer group` 会成为体系里第一个「有权威却没有链上记录」的对象。量级上这是 **CIP-9 等级的子系统**，同时是第三个链下 daemon 家族与第二套 stream 协议 —— **不是一个 slice，是多季度工程**。

### 最短的正确下一步（两项阻塞，都是文书工作不是码工）

1. 做 CIP-7 逐项对照表，回答「为什么不能是 CIP-7 v2 的链下 delivery class」。
2. 跟 CBSS 团队敲定 persistent-workload release path。可行则 envelope 子系统整个离开 v1，两个 HIGH 一个 MED 一起降级。

其余四项属于范围收敛：grantee 绑 CIP-10 Persistent Workload 注册记录（`0x13`）而非自创 holder key、v1 明说单 provider 不承诺 handoff、`fast` class 延到 v2、补 `0x17` 起的地址与 opcode 配置。

**值得保留的**：诚实的信任姿态、rotation 三步中断安全性论证、fast class 的丢失可见性设计、live records 永不静默驱逐。这几点比同类设计稿强，收敛时不要一起砍掉。

---

## 1 前提核对（一手源）

| 稿件宣称 | 核对结果 | 证据 |
|---|---|---|
| Watchtower/CIP-7 是「**拟议的**草案、public actor-native stream」 | ❌ **错**。CIP-7 自称「the canonical stream protocol for Cowboy」，1317 行规格，且**已落地代码**：Stream Key Manager 系统 actor `0x0D`、2390 行 handler、PVM host seed | `cowboy/docs/cips/cip-7-simple-stream-protocol.md:1-30`；`node/runner/src/system_actors.rs:57`；`node/execution/src/stream_key_manager.rs`（2390 行）；`node/pvm/crates/pvm-host/src/lib.rs:694` |
| CBSS 因「64 个 actor ACL 上限」不适合聊天室规模 | ⚠️ **论据错位**。`MAX_ACL_ACTORS = 64` 是 §4.5 **治理可调参数**；CIP-24 明说 ACL 是 runtime gate 而非密码学收件人清单，`wrapped_dek` 是 **O(1)**、与 ACL 大小无关、改 ACL 零 re-wrap。真正的结构性阻挡是 §3.7 的 `(actor, runner_id, job_id, secret_id)` job 绑定 + freshness 窗口 | `cip-24-secrets-manager.md:1257`（参数表）、`:134`、`:209`、`:533` vs `:660`、`:822` |
| CIP-7 不能做成员规模扇出 | ❌ CIP-7 明写「Model supports large subscriber sets (100, 1,000, 10,000)」，用 **account-scoped X25519 + CBSS 门限代理重加密 + epoch key**，且已有 `WrappedContentKey` 类型 | `cip-7-simple-stream-protocol.md:923-963`、`:340` |
| `OwnerCapTokenV1` 是 owner-only、bearer、只有粗粒度 access mode + path prefix | ✅ 正确 | `cowboy-protocol/crates/cowboy-protocol-codec/src/cbfs_signing.rs:87-101` |
| `delegated_request_signing_bytes` + delegation-cert 层可复用 | ✅ 存在，且已被 COW-2649 收敛为单一权威来源（node/cbfs 各自的副本已删除） | 同文件 `:201`、`:246`；模块头注释 |
| HPKE envelope 有先例 | ✅ `hpke 0.12`（`x25519` feature）已是 cbss / runner 的 workspace 依赖 | `cbss/Cargo.toml:116`、`runner/Cargo.toml:211`、`runner/crates/runner-storage/Cargo.toml:31` |
| Provider registry「CBFS-relay 模式，创建时分配 stream」 | ⚠️ 只有控制面像。CBFS 数据面是**多 relay 抹除码 + PlacementRecord + CAS 版本 + 自主修复 + drain 再平衡**，不是单一指派 | `cip-9-runner-storage.md:267`、`:289`、`:307`、`:311` |
| 配套草案 `cowboy/internal-docs/engineering/cbmq-high-level-design.md` | ❌ 工作区不存在（`cowboy/internal-docs/engineering/` 下只有 `testing/`） | `find` 无命中 |
| 「Cowboy 不提供持久链下 backplane」 | ⚠️ 部分成立。持久链下**工作负载**已存在：CIP-10 v2 的 Persistent Workloads 有强制链上注册记录（Container Registry `0x13`）管 identity/ownership/lifecycle。稿件通篇未引用 | `cip-10-runner-containers.md:1192`、`:1200`、`:1216` |

---

## 2 HIGH 级风险

### H1 — 与已部署的 CIP-7 概念正面碰撞，稿件没做整合分析

CIP-7 已拥有：stream 模型、`PUSH` / `PULL` / `PUSH_WITH_PULL_FALLBACK` 三种投递、bounded replay window + 显式 `CURSOR_TOO_OLD`、per-epoch content key 与确定性轮换切换、CBSS 托管密钥、X25519 收件人身份、`WrappedContentKey`（即「wrapped envelope」）、发布者密钥轮换、canonical hashing/signing、CBY 计费与协议费。

CBQS 把这整套词汇在链下**重新发明一遍且语义不同**。稿件 §1.11 一句「在方便时共享 envelope/cursor/SDK conventions」不是整合分析。更严重的是 CIP-25 把 CIP-7 列为硬依赖（`cip-25-cross-chain-architecture.md:13`、`:279`、`:301`），两套 stream 协议共存会直接污染跨链那条线。

**要求**：进 CIP 前必须有一节逐项对照，明确回答「**为什么这不能是 CIP-7 v2 的一个链下 delivery class**」，而不是把 CIP-7 降格成「草案」。

**已完成**：逐项对照表见 `2026-07-27_cbqs-vs-cip7-comparison.zh.md`（30 项能力对照：11 缺口 / 6 重复 / 10 复用-延伸 / 3 分歧）。结论：CBQS 作为独立协议**正当**（单写者、消费者投递状态为零、吞吐成本三个结构性缺口 CIP-7 补不起），但控制面必须复用 CIP-7 的四项工件；复用后 H2 与 M1、M6 可一并消解。

### H2 — 最大的新子系统（envelope 扇出）建在一个可能会被填掉的洞上

§1.4.4 的 companion key stream 带来的成本：每个加密 stream 多一条链上记录、成员双密钥（holder signing + HPKE recipient）、签名 envelope 链、三步轮换状态机、每代 N 份 envelope。

而 §1.4.4 第 4 点自己承认：「一个直接的 CBSS persistent-workload release path 可以让小 stream 跳过 envelope 机制」，并把它丢进 §1.15 开放问题。也就是说 **v1 最大的自建件，是一个 CBSS 缺口的 fallback，而那个缺口 CBSS 团队可能自己补**。叠加 H1 的事实（CIP-7 已经用 CBSS + account-scoped key 做到 10,000 订阅者），这条路径值得先花两周与 CBSS 团队敲定，而不是先盖 envelope。

### H3 — v1 边界自相矛盾：provider handoff 同时是「开放问题」和「验收门槛」

- §1.15 #4：handoff「CIP 前需要一次设计 pass」。
- §1.13 验收测试：要求「live traffic 下的 provider-handoff 演练」。
- §1.13 v1 交付清单：**没有** provider epoch / signing-key transition / fencing / continuity anchor / rollback detection 任何一项。

同时 §1.10 自己承认一个 stream 的 provider 独占其签名 hash chain、leases、cursors —— 这是**单点故障**设计。CBFS 靠抹除码 + PlacementRecord + 自主修复回避的可用性问题，CBQS 全部承接却没有对应机制。这是全案最大的工程风险，却没有进入 v1 scope。当前这种「开放问题 + 验收门槛」的组合是不可交付的。

---

## 3 MED 级风险

### M1 — workload 身份没有链上锚

StreamGrant 绑定 grantee holder public key，但稿件没说 runner 上的 workload 的 holder key 从哪来、容器被重排到另一台 runner 之后如何延续：

- 放在容器 image 里 → runner operator 可直接抽走密钥；
- 每实例现场生成 → 每次重启都要 owner 在线重签 grant，直接打脸 §1.4.4 末尾「死亡参与者永远不能冻结成员关系」的卖点。

**现成解**：CIP-10 v2 的 Persistent Workloads 有**强制链上注册记录**管 identity / ownership / lifecycle / route eligibility（Container Registry `0x13`）。StreamGrant 的 grantee 应绑定这条记录，让撤销与轮换有链上锚，而不是自创一套松散的 holder key 生命周期。

### M2 — 没有系统 actor 地址与 opcode 配置

CBQS 至少需要一个 stream registry（外加 provider registry）系统 actor。白皮书 §9.1 规定：新系统 actor **MUST** 取密集序列的下一个空位（当前为 `0x17`）并在同一次变更中更新地址表（`cowboy/docs/whitepaper/cowboy-technical-whitepaper.md:861`）。同时需要新的 system instruction opcode band（create / config / delete stream、轮换 admin key、bump 两种 generation、注册 / 分配 provider）。

本仓库有地址撞车（`0x11`/`0x13` 对账，见 `cowboy-technical-whitepaper.md:863`）与 opcode 撞车（CIP-12 治理 opcode 103-107 撞 CIP-16）的前科，这两项不能留白。

### M3 — 撤销延迟无界

broker 不逐请求读链，靠追踪 stream record 判断 generation。因此撤销实效 = broker 追链延迟 + grant TTL。稿件两者都没有给上界，也没说 broker 如何追链（RPC 轮询？重组处理？）。Cowboy 用 Simplex BFT 有最终性、重组风险有界，但这需要写进规格作为显式假设，而不是默认。

### M4 — 成员异动的控制面成本被低估

移除一名成员的完整路径 = CBSS release 给 rotation workload（t-of-n 往返，受 `REQUEST_FRESHNESS_BLOCKS` ≈ 6 分钟窗口约束）+ 发布 N 份 envelope + 一笔链上 generation bump 交易。100 人房间高频进出 → rotation 风暴。

「数据路径零链写入」的说法成立，但**成员异动路径是链上的、且是 CBSS-latency-bound 的**，而 §1.13 验收测试第一项就是 100 人聊天室。§1.15 #2 把 release latency 列为开放问题，但验收会直接撞上它。

### M5 — fast class 让审查变得便宜且可否认

broker epoch bump + void statement 在密码学上与真实崩溃**无法区分**。恶意 provider 可以用「崩溃」抹掉 last durable checkpoint 之后的任何内容，且对外表现与硬件故障一致。稿件说非投递只能举证不能预防（诚实），但没有点出 fast class 把**举证能力本身**也一并削掉。叠加 v1 不质押（§1.10），fast class 在对抗模型下基本无保障 —— 而 §1.13 验收的 ClawChat 与 Homestead CRDT 两项都跑在 fast 上。

附带的应用负担：consumer 会看到 provisional 记录并可能据此更新 UI（聊天消息已显示），void 时应用必须回滚本地状态。SDK 暴露 void event 只是把这份 reconciliation 工作推给应用。

### M6 — 计费与真实消耗脱钩

租金在链上按 class 从 owner account 收取，但真实资源消耗（bytes、停滞 group pin 住的 retention）发生在链下 broker。CBFS 有 Proof-of-Retrievability + challenge bond + 签名 usage report（`relay_usage_signing_bytes` / `ReportUsageRequest`）把两边绑住；CBQS v1 全无，broker 唯一的杠杆是 backpressure refusal。另外自托管 broker 情形下租金付给谁，稿件未定义。

---

## 4 新概念涌现度（相对既有 Cowboy 体系）

稿件引入的新名词计约 **25 个**：

`cbqsd`、stream record、StreamGrant、holder signing key / HPKE recipient key 双密钥、authorization generation、encryption-key generation、consumer group、lease、terminal state 三态（ACKED / DEAD_LETTERED / EXPIRED）、dead-letter lane、redrive cycle、delivery class、provisional / durable watermark、broker epoch、void statement、checkpoint receipt、hash-chain append receipt、key stream、rotation authority、envelope set / rotation id、provider epoch / fencing / continuity anchor、idempotency horizon、backpressure refusal、actor bridge helper、inline limit。

分布：

1. **约 8 个与 CIP-7 同名或同义**：stream、cursor、replay window、cursor-too-old、key generation / epoch、wrapped envelope、push/pull、subscription。**这是最贵的一类** —— 同名不同义会长期毒害 SDK、文档与新人上手。
2. **约 4 个与 CBFS 同义但语义不同**：owner cap → grant、provider registry、retention/quota、rent。
3. **`consumer group` 是体系里第一个「有权威、但没有链上记录」的对象**（§1.4.1 明说它不是链上对象，由 broker 在 stream 的 admin authority 下创建配置）。对比：CBFS 的 volume 有 `StorageCommitment`、CBSS 的 secret 有链上 SecretVersion、CIP-10 的 persistent workload 有强制注册记录。这是一个**新的信任类别**，稿件没有正面论证它为什么可以没有锚。

**量级评估**：这是 **CIP-9 等级的子系统**，同时是体系的**第三个链下 daemon 家族**（cbfs relay、cbssd、cbqsd）和**第二套 stream 协议**。§1.13 的 v1 清单有 14 项交付，含新 daemon + 新 auth 协议 + 新密钥分发子系统 + 两种投递类别 + 带 flow control 的 push transport + SDK + CBFS 组合 + 配额，还外挂一个 provider-handoff 演练。以团队当前同时在跑 CIP-28 / CIP-34 / CIP-36 的负载看，**这不是一个 slice，是多季度工程**。

---

## 5 建议的收敛路径

1. **先做 CIP-7 对照表**（阻塞项）。逐条列 CIP-7 已有能力 vs CBQS 需求，明确回答「为什么不是 CIP-7 v2 的链下 delivery class」。这一步可能直接砍掉 30–50% 的新概念。
2. **先问 CBSS 团队 persistent-workload release path**（阻塞项）。若可行，envelope 子系统整个从 v1 拿掉，降两个 HIGH、一个 MED。
3. **grantee 绑定 CIP-10 persistent-workload 注册记录**，不自创 holder key 生命周期（解 M1）。
4. **v1 砍成单一 provider、不承诺 handoff**：明写「v1 = 单 provider，故障即停机，这是 SLA 问题而非 correctness 问题」，把 handoff 连同 §1.13 那条验收一起移到 v2。
5. **`fast` class 延到 v2**，或明写它在 v1（无质押）下不提供对抗性保证。先让 standard + hash-chain receipt 站稳。
6. **补齐地址 / opcode 配置**（自 `0x17` 起）并与白皮书 §9.1 同步更新。
7. 修掉 `cbmq-high-level-design.md` 这条 dangling 引用。

---

## 6 值得保留的部分

以下几点是这份稿件相对同类设计文档的真实优势，收敛时不应丢失：

- **信任姿态说得诚实**：明确只保护内容机密性、不承诺隐藏通信拓扑，并逐层列出链上记录 / CBSS 活动 / broker 元数据各自泄露什么。这比含糊承诺隐私的设计强。
- **rotation 三步状态机的中断安全性论证**（§1.4.4 第 3 点）：停在步骤之间仍然安全，N+1 处于惰性状态。这类「部分完成也正确」的论证正是本仓库历史事故（pay-then-fail 守恒洞）最缺的。
- **fast class 的丢失可见性设计**（§1.6.1）：`(broker epoch, sequence)` 身份 + 不跨 epoch 复用 sequence + 显式 void statement，比「尽力而为、静默丢失」诚实得多。M5 批评的是它的对抗性上限，不是它的工程设计。
- **拒绝方案清单（§1.14）写了理由而非结论**，包括为什么托管 RabbitMQ 不能作为面向客户端的系统。
- **Live records 永不静默驱逐**（§1.7）：cap 触发 backpressure 而非 eviction。这是正确的默认值。

---

_审计人：Marshal 认知回路（人工核对一手源，未运行不变量门禁 / 未派子代理）。建议态，非阻断。_
