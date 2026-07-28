# CBQS ↔ CIP-7 Watchtower 逐项对照表

**目的**：回答 CBQS 设计审计（`2026-07-27_cbqs-design-review.zh.md` H1）留下的阻塞问题 —— **「为什么 CBQS 不能是 CIP-7 v2 的一个链下 delivery class？」**
**方法**：CIP-7 全文（`cowboy/docs/cips/cip-7-simple-stream-protocol.md`，1317 行）+ 已部署实现（`node/execution/src/stream_key_manager.rs`、`node/runner/src/system_actors.rs:57`）逐项核对 CBQS 设计稿 §1.4–§1.13 的需求。

---

## 0 结论（一句话三段）

**CBQS 作为独立协议是正当的，但它现在的形态里约三分之一是重复发明。**

1. **不能挂进 CIP-7**：CIP-7 的每一条投递、保留、完整性性质都是「消息是链上共识状态」的**推论**。把数据面搬到链下，这些推论全部失效，必须重新论证 —— 所以「加一个 delivery class」在架构上不成立，不是工作量问题。
2. **三个结构性缺口是真的**：单写者、消费者投递状态为零、吞吐/成本/延迟。这三项 CIP-7 补不起（补法本身就是 CBQS），构成 CBQS 存在的正当理由。
3. **但六项必须复用**：收件人身份注册、generation/撤销语义、wrapped-key identity 布局、cursor/陈旧游标错误契约、CBY 计费流向、canonical 签名域。复用这六项可消掉 CBQS v1 约 1/3 的新概念，并顺手解决审计报告的 M1（身份锚）与 M6（租金付给谁）。

---

## 1 架构分野（根因表）

这张表是全部结论的根因。左右两栏不是「实现选择不同」，而是**保证的推导前提不同**。

| 维度 | CIP-7（已部署） | CBQS（设计稿） |
|---|---|---|
| 消息存放 | 链上 actor 状态，进 `state_root` | broker 本地 log/KV，不进链 |
| append 路径 | 一笔交易 + gas（`publish`，§Actor Interface:583） | 持久连接上的 RPC，**零链写** |
| 顺序保证来源 | 执行确定性：`sequence` MUST 严格递增且连续（`prev + 1`，§StreamMessage:384） | broker 单一全局 append 顺序 |
| retention 机制 | 确定性 ring buffer 剪枝，是**状态转换**（§Ring Buffer Pruning:965-985） | broker hot window + consumer group pin |
| 完整性来源 | **链本身就是收据**；publisher ed25519 签名任何人可验（§Canonical Hashing:492-527） | provider 签名 hash chain / checkpoint chain |
| 写入者数量 | **单一 active `publisher_key`**（`init` 收一个 key，`rotate_publisher_key` 单一 active） | 任意多 appender（StreamGrant `append` verb） |
| 消费者投递状态 | **不存在**。pull consumer「track local cursor」（§Pull Delivery:867） | consumer group + lease + terminal state + DLQ |
| payload 上限 | 16 KiB inline，`MAX_EFFECTIVE_PLAINTEXT_BYTES = 16_344` | 256 KiB inline + 超限走 CBFS reference |
| replay 窗口 | `DEFAULT_RING_BUFFER_CAPACITY = 10_000` 条消息 | 7 天或 byte cap（standard）；秒级（fast） |
| 加密粒度 | per-epoch content key，`DEFAULT_KEY_EPOCH_BLOCKS = 600` | per-generation 对称数据密钥 |
| 密钥托管人 | CBSS 委员会（IBE to MPK），t-of-n 门限释放 | CBSS 持根 + 成员 HPKE envelope 扇出 |
| 谁付费 | **subscriber** 付费买 epoch access（`acquire_epoch_access`） | **owner** 付 stream 租金 |
| 交付延迟 | 密钥交付 4–5 块，上限 `REQUEST_FRESHNESS_BLOCKS = 384` | 亚秒级推送（数据面） |

**读法**：CIP-7 之所以不需要 ack/retry/lease/receipt，是因为链上状态本身提供了这些性质的替代品（消息在共识里 = 已投递且不可否认）。CBQS 把消息移出共识之后，必须自己造 receipt chain、lease、terminal state —— 这不是 CIP-7 的一个选项开关，是另一套推导。

---

## 2 逐项能力对照

判定列取值：**复用**（CBQS 应直接用 CIP-7 的既有工件）· **延伸**（同一概念但需扩展语义）· **缺口**（CIP-7 无且补不起）· **重复**（CBQS 在重造 CIP-7 已有的东西）

| # | 能力 | CIP-7 现状 | CBQS 需求 | 判定 |
|---|---|---|---|---|
| 1 | 有序 append-only 序列 | 有。`head_sequence` / `floor_sequence`，sequence 连续 | 有。broker sequence | 延伸（语义同，位置不同） |
| 2 | 多写者 append | **无**。单一 active `publisher_key` | 必需（work queue 多 producer、100 人聊天室） | **缺口** |
| 3 | 写入授权（scoped verb） | 无。只有 `subscription_policy: PUBLIC \| PRIVATE_ALLOWLIST` 管**订阅**，写入=持 publisher key | StreamGrant `{append, consume, acknowledge, replay, group-admin}` | **缺口** |
| 4 | 跨账户参与 | 部分。`payer_account` ≠ `beneficiary_account`（sponsored purchase）；但仍单写者 | owner 为他方 holder key 签 grant | **缺口**（读侧已有，写侧无） |
| 5 | consumer group / 竞争消费 | **无** | 一 stream 一 group 多竞争 worker | **缺口** |
| 6 | lease / ack / nack / extend | **无**。§Non-goals:68 明列「Ack/retry protocol in core spec」 | 必需（standard class 核心） | **缺口** |
| 7 | terminal lifecycle / dead-letter / redrive | **无** | 必需 | **缺口** |
| 8 | at-least-once + 客户端去重 | 有。push 是 at-least-once，「Consumers MUST deduplicate by `(stream_id, sequence)`」（§Push:836-839） | 同语义，去重键为 client message id | 复用（语义已定，别改说法） |
| 9 | exactly-once | 明确不承诺（§Non-goals:67） | 明确不承诺（§1.13） | 一致 ✓ |
| 10 | idempotent append | 无（append 是交易，天然由 nonce 去重） | idempotency horizon + 原 receipt 重放 | 缺口（但因 #1 位置不同而必需） |
| 11 | push 投递 | 有。`PUSH`，actor 付 fan-out gas，`max_push_deliveries_per_block` / `max_push_cycles_per_block` 上限 | push-first，持久双向连接 + flow-control credits | 延伸（CIP-7 的 push 有链上 per-block 预算，CBQS 无此约束） |
| 12 | pull / long-poll fallback | 有。`PULL`、`PUSH_WITH_PULL_FALLBACK`、`get_since(cursor, limit)`、`MAX_GET_SINCE_LIMIT = 500` | long-poll 作为受限客户端 fallback | 复用（**三种模式的命名应沿用**） |
| 13 | 陈旧游标错误 | 有。`cursor < floor_sequence - 1` → `CURSOR_TOO_OLD`（§965-989） | cursor-too-old + signed checkpoint anchor | **重复**（错误码与边界必须对齐，见 R4） |
| 14 | 保留窗口 | 有。ring buffer 条数上限，确定性剪枝 | 时间/字节 hot window + group pin，**cap 触发 backpressure 而非驱逐** | 延伸（CBQS 的 no-silent-eviction 是新性质，是对的） |
| 15 | 消息完整性 | 有。publisher ed25519 over deterministic-CBOR 签名载荷 + `payload_hash` | provider 签名 hash chain receipt | 延伸（签名者从 publisher 变 provider，因为链不再作证） |
| 16 | 连续性证明 | 隐含（链上 sequence 连续 + 状态根） | hash chain + checkpoint chain 显式 | 缺口（必需，因为离链） |
| 17 | payload 加密 | 有。XChaCha20-Poly1305，per-epoch content key，AAD 绑 `{stream_id, sequence, key_epoch, kind, content_type}` | 默认端到端加密，per-generation 数据密钥 | 延伸（**AAD 绑 envelope 防重排/重放这条应照抄**） |
| 18 | 密钥托管根 | 有。IBE to CBSS committee MPK，t-of-n 门限 | CBSS 持根 | 复用 ✓ |
| 19 | 成员扇出 | 有。account-scoped X25519 + 一次购买覆盖账户下所有委派进程；明写支持 100/1,000/10,000 订阅者（§959-963） | 每成员一份 HPKE envelope，100 人 = 100 份/代 | **重复**（见 R1/R2；CBQS 的 per-member envelope 比 CIP-7 的 account-scoped 更贵且更复杂） |
| 20 | 收件人身份注册 | 有。`AccountKeyRegistration`（链上、account-scoped、`MAX_ACCOUNT_KEYS_PER_ACCOUNT = 8`、`ACTIVE`/`REVOKED`、须账户签名） | 成员 HPKE recipient key（无链上注册） | **重复**（应直接复用 `0x0D` 注册表，见 R2） |
| 21 | 密钥代际与撤销 | 有。`generation` 计数器（`0xD \|\| 0x06 \|\| keccak(stream_id) \|\| u64_be(epoch)`）；re-wrap bump identity → 旧 σ 对新密文失效；已解开的旧密钥不追溯撤销 | encryption-key generation + authorization generation 双计数器 + 三步轮换状态机 | **重复**（同一不变量的另一种写法，见 R3） |
| 22 | 前后向隔离 | 有且更强。`stream_secret` 永不出 publisher keystore，`content_key_e = HKDF(...)` 逐 epoch 独立，拿到一代推不出另一代 | 未明确论证跨代隔离 | **CIP-7 更强，CBQS 应补齐这条论证** |
| 23 | 计费与价值流向 | 有。publisher treasury + protocol fee → System Treasury `0x08`，`MAX_PROTOCOL_FEE_BPS = 5_000` | 按 stream 收租金（参考 CBFS 存储费） | **重复**（应走同一条 CBY 流向，见 R5） |
| 24 | canonical 编码/签名域 | 有。deterministic CBOR (RFC 8949) + ed25519 + SHA-256 + tag 规范化（float64-only 等） | StreamGrant wire format「开放问题」 | **重复**（见 R6；且 `cowboy-protocol-codec` 已是签名域单一权威） |
| 25 | 大 payload 外置 | 无（§Non-goals:70「External payload URI hosting guarantees」，§1060 列为 future） | >256 KiB 存 CBFS，密文内携带 reference | 缺口（CBQS 领先，可反哺 CIP-7） |
| 26 | 头部过滤 | 有。确定性 JSON Filter DSL over `kind`/`tags`/`sequence`/`timestamp` | **明确排除**（§1.13「server-side semantic filters」） | 分歧（CBQS 主动放弃，合理） |
| 27 | provider/broker 角色 | 无（无链下 broker；validator 即数据面） | `cbqsd` 新 server 类型 + provider registry + handoff | **缺口**（也是最大风险，见审计 H3） |
| 28 | 有界丢失投递类别 | 无（链上无「provisional」概念） | `fast` class：provisional/durable watermark + broker epoch + void statement | **缺口**（无链上对应物） |
| 29 | actor 桥接 | 天然（stream 就是 actor） | actor bridge SDK helper，「broker 永不自动调用 actor」 | 分歧（CIP-7 更强，CBQS 刻意更弱以避免共识耦合） |
| 30 | 定时摄取 | 有。`IngestionConfig` + CIP-5 timer + CIP-2 任务 | 无 | CIP-7 独有 |

**统计**：30 项中 —— 缺口 11 项（CBQS 的正当性）· 重复 6 项（应删）· 复用/延伸 10 项（应对齐命名与错误契约）· 分歧 3 项（各自合理）。

---

## 3 三个结构性缺口 —— CBQS 的正当理由

这三项是 CIP-7 **补不起**的，补法本身就等于 CBQS。这是设计稿真正该写进 Motivation 的论证。

### G1 单写者

`init(stream_id, initial_publisher_key, ...)` 只接受一个 publisher key；`publish` 第 6 步「Validate signature against active publisher key」；`rotate_publisher_key` 维持单一 active + key schedule 供历史验签。

**后果**：100 人聊天室（每人都写）、work queue（多 producer）、agent RPC（request/reply 双向）**在 CIP-7 里无法表达**。要补 = 多 publisher 授权模型 + per-writer 顺序或全局序列化 + 写入侧撤销 —— 等于重做整个 auth 层，而这正是 StreamGrant。

### G2 消费者投递状态为零

CIP-7 §Non-goals 第 3 条明写「Ack/retry protocol in core spec」不在范围；pull consumer「track local cursor」纯客户端；push「best-effort、no protocol-level ack or retry」。

**后果**：**work queue（一 stream、一 group、多竞争 worker）—— 多 agent 协调的头号用例 —— 在 CIP-7 里完全没有对应物**。要补 = 把 per-message × per-consumer 的 lease/terminal 状态放上链 = 每条消息多次链写，正是两份文档都明确拒绝的东西（CBQS §1.14「On-chain mailbox actor」、CIP-7 自身的 gas 模型）。

### G3 吞吐 / 成本 / 延迟

16 KiB inline 上限、每条 `publish` 一笔交易 + gas、push fan-out 由 actor 付费且受 `max_push_deliveries_per_block` 约束、replay 窗口 10,000 条、密钥交付 4–5 块。

**后果**：presence / typing / awareness / CRDT op log（CBQS `fast` class 的目标：约 10× 更便宜、秒级 retention、亚秒推送）在链上不可能。这不是调参能解决的。

---

## 4 六项重复发明 —— 应复用而非重造

### R1 wrapped-key identity 布局与 generation 语义

CIP-7 已经把这件事做到字节级：DST `cbss/ibe/cip7-content-key/v1`、`content_key_identity_bytes`（含 `stream_id` 长度前缀防碰撞）、`base_wrapped_dek_aad`（绑 `committee_epoch` + `selector_byte` + `override_hash`）、`aad = base || compress(U)`（绑 BF ephemeral，这是 CIP-24 机密性修复的核心）、`generation` bump 使旧 σ 失效。

**建议**：CBQS envelope 直接沿用这套 identity/AAD 布局与 generation 语义，只把收件人从 committee MPK 换成成员 HPKE key，DST 换成 `cbss/ibe/cbqs-stream-key/v1`（域分离规则照 CIP-7 §258-264 的四层论证）。**不要重新设计一套 envelope 签名字段**（设计稿 §1.4.4 现在自定义了 stream id / generation / recipient key / ciphertext hash / previous rotation id 五元组签名）。

### R2 收件人身份注册 —— 直接复用 `0x0D`

CIP-7 `AccountKeyRegistration` 已经是：链上、account-scoped、X25519、`MAX_ACCOUNT_KEYS_PER_ACCOUNT = 8`、`ACTIVE`/`REVOKED` 状态机、须账户签名、私钥永不上链、明确写了「account holder 负责把私钥委派给消费进程（CLI / off-chain worker / CIP-2 runner）」。

CBQS 的「成员 HPKE recipient key」是同一个东西，但没有链上注册、没有撤销状态、没有身份锚。

**建议**：复用 `0x0D` 的 account key 注册表作为 CBQS 成员的 HPKE 收件人身份。收益有三：① 删掉一整套成员密钥状态；② **直接解决审计 M1 的身份锚问题**（撤销有链上记录）；③ 与 CIP-7 订阅者共享同一把账户密钥，跨两套协议的应用不需要管两套密钥。

### R3 撤销语义与术语

CIP-7 的 `generation`（每 epoch 一个计数器，re-wrap 时 bump）+ `key_epoch`（时间窗口）是**两个正交概念**。CBQS 的 `encryption-key generation` 把两者混在一个计数器里，同时又引入第二个 `authorization generation`。三个同名不同义的 generation 在同一个体系里，是可预见的长期混淆源。

**建议**：术语裁定。要么 CBQS 沿用 `key_epoch` + `generation` 两层，要么显式改名（如 `grant_epoch` / `dek_version`）并在规格里写明与 CIP-7 的映射关系。**同名不同义比换名字贵得多。**

同时 CIP-7 已经写清了一条 CBQS 缺失的不变量：**re-wrap 不追溯撤销已解开的旧密钥，只作废 pending/future 释放**。CBQS §1.4.4 的三步轮换应显式声明同一性质。

### R4 cursor / 陈旧游标错误契约

CIP-7：`cursor` 陈旧 iff `cursor < floor_sequence - 1` → `CURSOR_TOO_OLD`；`subscribe(start_cursor)` 也用同一判据。CBQS：「低于 floor 时返回明确的 cursor-too-old，并带 signed checkpoint anchor」。

**建议**：错误码与边界判据逐字对齐（CBQS 是超集，多带一个 checkpoint anchor）。**绝不能一个叫 `CURSOR_TOO_OLD` 一个叫 `cursor-too-old` 而 off-by-one 边界不同** —— 这类差异在 SDK 层会长成真 bug。同理 `PUSH` / `PULL` / `PUSH_WITH_PULL_FALLBACK` 三个模式名应沿用。

### R5 CBY 计费流向

CIP-7 已定：publisher amount → publisher treasury；protocol fee（`[0, MAX_PROTOCOL_FEE_BPS]`）→ System Treasury `0x08`（CIP-2 §5.4 共享汇），再由治理分配到 burn / staking / dev fund。

CBQS 只说「按 stream 收租金，建模参考 CBFS 存储费用，从 owner account 支付」，没说协议费、没说钱去哪、没说自托管 broker 情形下租金付给谁（审计 M6）。

**建议**：走同一条流向与同一个 protocol-fee 机制。自托管 broker 情形下，租金应类比 CBFS relay 的 89% relay 份额（CIP-31）由 provider 领取，协议费仍进 `0x08`。这样 M6 不需要新机制。

### R6 canonical 编码与签名域

CIP-7 固定了 deterministic CBOR (RFC 8949 canonical) + ed25519 + SHA-256，连 tag 的 float64-only 规则都写死了。更重要的是 `cowboy-protocol-codec` 的 `cbfs_signing.rs` 已经是 CBFS/RAS 签名域的**单一权威**，其模块头记录了教训：node 与 cbfs 各持一份字节相同的副本、只靠一个 parity test 维系，正是 2026-07-11 停机（COW-2608）的成因；COW-2649 因此禁用 bincode 并收敛为单一实现。

**建议**：StreamGrant 的签名字节必须落在 `cowboy-protocol-codec` 里，沿用同一 `Encoder` 约定（大端定宽整数、`u64`-BE 长度前缀、地址为 EIP-55 checksum 字符串、`bool` 单字节、`Option<T>` 显式 tag），**签名字节绝不经 serde/bincode**。设计稿 §1.15 #1 把 wire format 列为开放问题是对的，但答案已经存在，不需要重新选型。

---

## 5 结论：分工边界（这是两套协议共存的前提）

> **CIP-7 Watchtower** = **单写者 · 共识可见 · subscriber 付费**的广播。消息是链上状态，链本身是收据。适用：新闻/价格/告警 feed、公开或付费订阅、需要最终性与公开可验证的消息、跨链 egress（CIP-25 §2.6）。
>
> **CBQS** = **多写者 · 链下 · owner 付费**的私有协调。消息在 broker，provider 签名是收据。适用：work queue、agent RPC、聊天室、presence、CRDT op log —— 即需要 per-consumer 投递状态或高频低成本传输的场景。
>
> **判据（写进规格）**：需要**共识可见性或最终性** → CIP-7。需要**多写者或 per-consumer 投递状态** → CBQS。两者都不需要 → 用 actor mailbox。

这条边界必须写进 CBQS 的 CIP §Motivation 和 CIP-7 的 §Non-goals（互相指认），否则第二套 stream 协议会在 SDK 与文档层持续制造混淆。

**回答原始问题**：CBQS 不能是 CIP-7 v2 的一个链下 delivery class，因为 CIP-7 的投递/保留/完整性保证全部由「消息是共识状态」推导而来，移出共识后这些推导前提失效，需要另一套论证与另一套工件。**但**控制面的四项 —— 收件人注册（R2）、generation/撤销语义（R3）、计费流向（R5）、canonical 签名域（R6）—— 必须复用 CIP-7/既有工件；复用后 CBQS v1 约 1/3 的新概念消失，H2（envelope 子系统）的规模显著缩小，M1（身份锚）与 M6（租金归属）直接闭合。

---

## 6 待裁决

1. **CBQS stream 是否需要一个链上锚对象，以及用什么形态？**
   - 方案 A（新建）：CBQS 自有 stream record（设计稿现状）。独立、干净，但与 `StreamConfig` 概念重叠，且需要新系统 actor（`0x17`）。
   - 方案 B（复用）：CBQS stream 的链上记录复用 CIP-7 `StreamConfig` 的扩展形态，落在 `0x0D`，新增 `delivery_mode: ONCHAIN | OFFCHAIN_BROKER` 判别。省一个系统 actor，共享 account key 注册表与计费流向，但把两套语义压进一个 actor，`0x0D` 的 storage 布局与 gas 模型都要重审。
   - **推荐 A，但强制复用 `0x0D` 的 `AccountKeyRegistration` 与 protocol-fee 流向**：即控制面工件复用、控制面对象独立。这样既不把两套投递语义混进一个 actor，又拿到 R2/R5 的全部收益。

2. **成员密钥：per-member HPKE envelope 与 CIP-7 account-scoped 单钥，是否需要同时支持？**
   若复用 R2，account-scoped 单钥已覆盖「一个账户的所有委派进程」；per-member envelope 只在**需要按成员单独撤销**时才必要。建议 v1 只做 account-scoped（100 人房间 = 100 个账户各一把已注册密钥，扇出由 CBSS 承担，与 CIP-7 的 10,000 订阅者路径同构），把 per-member envelope 降为 v2 的细粒度撤销选项。**这条若成立，审计 H2 直接消解。**

---

_审计人：Marshal 认知回路（人工核对一手源：CIP-7 全文 + 已部署实现 + CIP-24/9/10/31 + `cowboy-protocol-codec`）。建议态，非阻断。_
