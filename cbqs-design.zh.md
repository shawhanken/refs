# CBQS - Cowboy Queue System：设计

## 1 CBQS - Cowboy Queue System

高层设计。尚未形成 CIP。配套草案（早于简化为 CBFS 模式控制平面的版本）：`cowboy/internal-docs/engineering/cbmq-high-level-design.md`。

### 1.1 背景

Cowboy 为共识 actor 提供确定性的邮箱，通过 runner 提供链下计算，通过 CBFS 提供加密的持久存储，并通过 CBSS 提供授权的密钥释放。但它并不提供一个持久的链下 backplane，让托管在 runner 上的工作负载可以协调。任何多个 agent 协作的系统，例如一个协调器面对聊天界面、多个 worker agent 运行在不同 runner 上，都必须自行重建消息持久化、重试、扇出、消费者游标、崩溃恢复和凭证分发。现有 Cowboy 多 agent 构建已经反复重建这些部件。

链交易不是数据路径的答案：它们慢、每条消息都要消耗 gas，而且每条消息都会成为公开状态。Actor 邮箱用于公开的、与共识相关的状态转换，而不是高频传输。

### 1.2 目标

构建一个持久 stream/queue 原语，与 CBFS 和 CBSS 对等，并建立在同样的架构模式上，使 runner 工作负载能够以至少一次投递、重放、工作分发和亚秒级推送投递来交换消息。消息内容默认端到端加密；队列的存在、所有权和运维元数据采用与 CBFS volume 相同的信任姿态。

### 1.3 信任姿态

CBQS 做出一个强隐私声明，并有意不做第二个声明：

1. 内容机密性（默认开启，可按 stream 选择关闭）。加密 stream 端到端传输密文；broker 和链永远不持有数据密钥。payload 语义和 CBFS 引用都保留在密文内部。对于不需要该开销的场景，可以创建未加密 stream。

2. 拓扑不隐藏，并明确说明。三层信息可见：链上可见 stream 记录（存在性、所有者、配置、provider、计费）以及任何密钥托管策略活动；CBSS 可见策略和释放回执，这些可能暴露参与者成员关系和访问活动，而不仅是通用元数据；broker 可见哪些工作负载连接到哪些 stream、大小、时间信息（consumer group id 仍只在链下 broker 侧存在）。这就是 CBFS 的姿态：平台保护你说了什么，而不是保护你正在说话这一事实。自托管 broker 可以向托管运营方隐藏 broker 流量元数据，但不能隐藏链上记录或 CBSS 活动。需要通信图保密的应用不在范围内。

这取代了早先严格拓扑隐私的设计；那种设计的成本（专门的 provisioning 和 capability 协议）收益很小：单个运营的 broker 无论如何都能从时间和连接元数据推断通信图。

### 1.4 架构

与 CBFS 和 CBSS 相同的拆分：链是控制平面，链下服务是数据平面。数据路径上零链写入。

#### 1.4.1 控制平面（链）

- Stream 生命周期：通过链交易创建、配置、删除 stream。stream 记录包含：owner、admin public key、delivery class、retention/quota config、assigned provider、encryption flag、authorization generation、current encryption-key generation、billing params。
- Owner 在 v1 中是一个账户。恢复和撤销是链操作：owner 通过交易轮换 admin key，或提升 authorization generation；admin key 丢失可通过账户权限恢复。Actor-owned streams（actor 拥有创建、配置、轮换权限，并具有 actor 专属恢复机制）推迟实现；v1 中由 actor 的 operator account 代表它拥有 stream。
- 计费：按 stream 收取租金（retention x throughput class），使用 CBY，建模方式参考 CBFS 存储费用，从 owner account 支付。
- Provider registry：broker 在链上注册（CBFS-relay 模式），并在创建时分配 stream。

Consumer group 不是链上对象，而是运维状态，由 broker 侧在 stream 的 admin authority 下创建和配置。

#### 1.4.2 数据平面（broker）

`cbqsd` 是 v1 中由 Cowboy 运营的服务（支持自托管）。它持有 hot window，执行投递（groups、leases、terminal states、dead-letter lanes），提供 push subscriptions，并签发 receipts。对于加密 stream，它存储密文，且永远不接收数据密钥。

#### 1.4.3 认证 - StreamGrant

这是一个新的、刻意保持小型的协议。CBFS 已实现的 token（OwnerCapTokenV1）只面向 owner，并且在其数据路径上是 bearer token；它只有粗粒度访问模式和路径前缀，没有 holder binding、没有逐请求 proof、没有 authorization generation。因此它是设计先例，但不是可复用代码。可复用的是：`cowboy-protocol-codec` 已有 delegation-cert 层，以及 challenge-bound request-signing primitive（`delegated_request_signing_bytes`，用于 RAS 控制平面）；StreamGrant 将这些现有原语应用到队列数据路径。

StreamGrant 由 stream 的链上 admin key 直接签名（没有 delegation chains，没有 attenuation），并携带：stream id；grantee holder public key（proof-of-possession，即每个请求都签署 nonce/context，因此被截获的 grant 字节本身无用）；作用域 verbs，来自 `{append, consume, acknowledge, replay, group-admin}`；expiry；caveats（最大消息大小、append 速率、in-flight 限制）；签发时对应的 authorization generation。broker 根据 stream 记录中的 admin key 和当前 generation 验证 grant，不需要逐请求读取链（broker 像 CBFS relay 跟踪 volume state 一样跟踪 stream records）。撤销 = generation bump（owner 链交易）+ 短有效期。Holder keys 可以是普通 workload keys；没有不可关联性要求。跨账户使用直接成立：owner 为另一方的 holder keys 签发 grants。

StreamGrant 是新的 wire surface，需要自己的兼容性和安全审查。它比早期可衰减 capability chain 设计小得多，但并非零成本。

#### 1.4.4 密钥管理 - CBSS 托管 + wrapped-envelope 分发

加密 stream 使用带显式 generation 的对称数据密钥。分发必须服务于聊天室规模的持久工作负载，而当前 CBSS release path 做不到这一点：CIP-24 release 绑定到一个存储的 JobSpec `secret_ref`、manifest entitlement 和一个 assigned runner，并有明确的 64 个 actor ACL 上限。因此 v1 将任务拆开：

- CBSS 持有根：每个加密 stream 的密钥材料（root 和/或每代密钥）在 owner policy 下托管于 CBSS。owner 的 rotation workload 是一个普通的、CIP-24 授权的 job，CBSS 将密钥释放给它。CBSS 是恢复和托管权威，而不是扇出机制。
- 成员通过专用 key stream 上的 wrapped envelope 获得密钥：这是一个 standard-class companion stream，随主 stream 一起创建，并从其链上记录链接。只有 rotation authority 对它拥有 append；成员拥有 consume/replay；其 retention 至少与成员可重放的加密 generation 一样长；其链上创建成本属于 stream setup 的一部分（每个加密 stream 两条记录）。成员有两个注册密钥：holder signing key（StreamGrant proof-of-possession，Ed25519/secp，不能解密）和 HPKE recipient key（X25519 类，不能签名），二者都在 grant/membership state 中携带算法/版本标签。每个 envelope 都由 rotation authority 对以下内容签名：stream id、encryption generation、recipient HPKE key、envelope ciphertext hash、previous envelope-set/rotation id。因此，恶意 appender 或 broker 都不能替换假的下一代 envelope 来分裂成员关系或发起 DoS。成员读取自己的 envelope 并在本地 unwrap。成员扩展依赖 envelope 数量，而不是 ACL 条目；100 人房间就是每个 generation 100 个 envelope。（key stream 在 stream 层面是 unencrypted class；envelopes 本身已经是密文。）
- Rotation 是一个定义明确的状态机，而不是三个无关更新：（1）owner 通过 CBSS 获取/创建 generation N+1；（2）向 key stream 发布保留成员集合的 N+1 envelopes；（3）提升 stream 记录中的 current encryption-key generation（链交易，可选择同时提升 authorization generation 以切断 grants）。在步骤（3）之后，broker 拒绝声明旧 key generation 的 append，因此被移除的 producer 不能继续写旧 generation 密文；reader 保留旧 generations 用于 replay。若 rotation 停在步骤之间也是安全的：在（3）之前，N 仍是当前 generation，N+1 处于惰性状态。
- 一个直接的 CBSS persistent-workload release path（policy 命名 workloads/accounts，无 job binding，超过 64 个 principals）可以让小 stream 跳过 envelope 机制。这是需要与 CBSS 团队共同设计的 CBSS 扩展，作为开放问题跟踪，而不是默认假设。

没有 coordinator 角色：rotation authority 是 stream owner，也就是一个具有普通账户恢复能力的链身份。死亡参与者永远不能冻结成员关系。

### 1.5 核心模型

一个原语：持久 stream，即一个有序、append-only 的记录序列，并带有有界 hot window。没有 partitions；每个 stream 有一个全局 append 顺序。Consumer groups 在其上持有投递状态：

| 应用行为 | CBQS 表示 |
| --- | --- |
| Work queue | 一个 stream、一个 group、多个竞争 workers |
| Fan-out topic | 一个 stream，每类 subscriber 一个 group |
| Chat room | 一个 stream，每个 participant 一个 cursor 或 group |
| Agent RPC | request stream 加 reply-stream grant |
| Event log / CRDT op log | 一个 stream、保留 replay、独立 cursors |

broker 可见的 record 携带队列机制：stream id、broker sequence、client message id（producer idempotency key）、payload（根据 stream 配置为密文或明文）、payload hash、visibility and expiry times、key generation。应用语义存在于 payload 中。

### 1.6 投递类别

在 stream 创建时设置。两种类别在其 retention 内都是有序且可重放的；差异在于持久性模型和每条消息的开销。

- `standard` - 完整契约：durable-commit-gated、每次 append 都有签名 hash-chain receipts；visibility leases，支持 ack / nack / extend / terminal reject；terminal lifecycle（ACKED / DEAD_LETTERED / EXPIRED），带每个 group 的 dead-letter lanes 和 inspection TTLs；在定义的 horizon 内支持 idempotent appends。适用于 work queues、接近结算的流程，以及任何丢消息就是事故的场景。
- `fast`（async-durable）- 适用于 CRDT op logs、presence、telemetry、cursor broadcast。Appends 在 fsync 前被 provisional acknowledge（“batch-committed”：磁盘以有界 batch 提交）；durable frontier 在每个 batch commit 时前进，并作为 checkpoint receipt 发布。broker 崩溃可能丢失 durable frontier 之后的 provisional records；这是一个有界、明确、SDK 可见的窗口。消费只基于 cursor fan-out（没有 leases、没有 dead-letter；consumer 是 reader，不是竞争 worker）；retention 可低至秒级。每条消息明显更便宜（目标约 10 倍，待测量）。presence/typing/awareness 的惯用法是一个短 retention 的 fast stream。

#### 1.6.1 精确定义 fast 语义

- 两个 watermarks：provisional sequence（订阅者已观察到的内容）和 durable checkpoint sequence（broker 已提交并签名的内容）。Consumer cursors 永远不会被持久推进到 durable watermark 之后。
- 丢失必须明显，并且范围诚实：fast 中的 record identity 是（broker epoch, sequence）。崩溃的 broker 无法知道自己确切的 provisional high-water，因此它不声明这一点；重启时它提升 broker epoch 并签署 void statement，即上一 epoch 中 last durable checkpoint 之后的所有 record 都作废。客户端把自己观察到的 watermark 与该 statement 比较，计算自己的丢失；sequence identity 永远不会跨 epoch 复用。Producer 使用 application op ids 重新发送；SDK 暴露 void event，让应用从本地状态重新发送（CRDT ops 需要显式 op ids/reconciliation，不能假设天然幂等）。
- Checkpoint receipts 绑定：stream id、provider epoch、inclusive sequence range、ordered range digest（或 Merkle root）、previous checkpoint digest、durable high-water、signature。客户端存储最新 checkpoint chain，以证明 inclusion 和 continuity。Snapshot manifests 只能绑定到 durable checkpoint，绝不能绑定到 provisional sequence。

### 1.7 投递语义（standard）

- 在诚实且可用的 provider 下，每个 consumer group 直到 terminal state 都是至少一次投递。Consumer 根据 client message id 去重。不声明 exactly-once。
- Idempotent append：在 idempotency horizon 内，相同重试返回原 receipt；冲突复用会明确失败；超过 horizon 后返回明确的 idempotency-expired 错误，绝不静默产生第二次 append。
- Leases：一次投递同一时间 lease 给一个 consumer，consumer 可以 ack、nack（retry delay）、extend，或 terminal reject 直接进入 dead-letter lane。lease 过期后可能出现重复。Delivery receipts 是 lease-specific；过期 consumer 不能 ack 后续重新投递。
- Terminal lifecycle：每个 delivery cycle 以 ACKED、DEAD_LETTERED 或 EXPIRED（显式 group-configured deadline）结束。Terminality 单调；redrive 会在 group tail 打开新的 audited cycle；append cursor 永不回退。Live records 永远不会被静默驱逐：cap 触发 backpressure refusal，而不是 eviction。停滞 group 只会在其 quota 和 deadline 内 pin storage。
- Ordering：每个 group 可配置为 strict-FIFO 或 concurrent；terminal states 填补 cursor holes；不可解密/垃圾 records 自动 nack 到 dead-letter，因此 poison record 不会卡死 strict-FIFO group。
- Group lifecycle：group 从 HEAD 或 retained sequence 开始，只从其起点 pin retention；删除 group 会释放其 pins。
- Retention：在 fully-terminal history 上有 hot window（time/byte bounds）；低于 floor 时返回明确的 cursor-too-old，并带 signed checkpoint anchor。

### 1.8 传输

Push-first。基准传输是持久双向连接（WebSocket 或 gRPC stream）：subscriptions 在 records commit 时投递（fast 下为 provisional），带 flow-control credits；appends 和 acks 在同一连接上传输。重连从 durable group cursor 恢复。push 是基于同一 cursor/lease 语义的投递优化，而不是独立一致性模型。Long-poll 作为受限客户端的 fallback。Consumers 只发起 outbound 连接；没有 inbound routes，数据路径上没有 Gateway。

### 1.9 完整性

每个 standard append 都返回 provider 签名的 receipt，签名对象是 canonical record digest（protocol version、stream id、client message id、payload hash、visible_after、expires_at、key generation），并按 stream 形成 hash chain；只有在 provider durable-commit boundary 之后才签发。Receipts 也在读取路径上传递，因此任何 consumer 都能验证 continuity，且冲突历史可以用 provider 签名证明。fast appends 返回 provisional status；完整性覆盖通过 checkpoint-receipt chain 获得。非投递只能被举证，不能被预防：恶意 provider 可以审查或销毁数据；enforcement（bonds/slashing）推迟到设计完成后。在 standard 中，所有改变状态的操作（ack、nack、extend、reject、redrive、admin changes）都返回用于审计的签名 receipts。

### 1.10 Provider 模型与存储

构建一个薄 broker；不要把客户端直接拼接到托管队列上。`cbqsd` 是建立在可插拔存储引擎之上的协议层：auth、receipts、delivery-state machine、push。v1 使用 embedded log/KV engine（RocksDB 类或 segmented log；困难点在 delivery-state machine，而不是 engine）。托管 stream engine（NATS JetStream、Redpanda、RabbitMQ Streams）可以在 provider 内部作为后端，只要它保留可观察契约，但客户端永远不直接与它通信。托管 RabbitMQ 曾被评估并拒绝作为 client-facing system：它的 auth model（users/vhosts）不能验证 StreamGrants，不能签发签名 hash-chain receipts，它的 queue/DLX 语义不能表达 terminal delivery cycles 或 redrive audit，第三方 host 会持有密文和拓扑，而修复这一切的 adaptation layer 正是 `cbqsd`。

`cbqsd` 是新的 server 类型：在链上注册（provider registry），v1 由 Cowboy 运营，可自托管。v1 不质押；receipts 是证据性的，staking/slashing 只有在 enforcement mechanism 设计好后才引入，这与 CBFS relays 的启动方式一致。

Provider handoff 是设计工作，不只是运维演练。一个 stream 的 provider 拥有其签名 hash chain、leases 和 cursors。重新分配（故障或迁移）需要：provider-epoch 方案，并在 stream record 中记录 signing-key transitions；权威状态转移（或 provider 内部复制）直到 continuity anchor；fencing 旧 provider，防止它继续签发看似有效的 receipts；以及 handoff 期间的 rollback detection，以便证明 stream fork。没有这些，failover 可能分叉历史或恢复过期 leases。托管服务需要声明 availability target，acceptance gate 必须在 live traffic 下演练 handoff；自托管是应对 operator risk 的逃生口，而不是逃避 correctness work。

### 1.11 集成边界

- CBFS：超过 inline limit（默认 256 KiB）的 payload 存在 CBFS 中并通过 reference 携带；对于加密 stream，reference 位于密文内部。Hot-window overflow 归档到应用管理的 CBFS volumes；交给 late joiner 的 snapshot 由应用签名的 manifest 绑定（snapshot hash/ref、stream id、covered sequence，即 durable checkpoint 而非 provisional sequence、key generation、checkpoint anchor）。
- CBSS：如上所述，作为加密 stream 的 root escrow 和 rotation authority。永远不在逐消息路径上。
- Watchtower（CIP-7，草案）：拟议的 public、actor-native、consensus-visible stream 方案。CBQS 是链下补充；在方便时共享 envelope/cursor/SDK conventions。
- Actor bridge（SDK application helper）：当 consensus actor 必须响应 stream traffic 时，授权 consumer workload 读取、构造调用方选择的 projection，并提交到链上。broker 永远不会自动调用 actors。Projection content 和 timing 会变为公开信息，这会在 helper 文档中说明。

### 1.12 跨账户使用

Grant 由 owner 签发，因此跨账户参与（受雇 actor 的 workload 消费客户 stream，两个团队共享 stream）自然成立：owner 为另一方的 holder keys 签署 StreamGrants，并为他们发布 key envelopes。未受邀 ingress（向未给你任何 grant 的 owner stream 发送）仍被排除；spam economics 是后续设计。

### 1.13 初始产品边界

v1 交付：chain-anchored streams，带 owner recovery 和基于 generation 的撤销；StreamGrant auth；默认加密 payload，带 CBSS root escrow 和 wrapped-envelope key distribution，并支持 per-stream opt-out；standard 和 fast delivery classes，带 watermark/loss-event contract；push-first transport，并有 long-poll fallback；durable consumer groups，带 leases、terminal lifecycle、dead-letter lanes、redrive；idempotent appends；读取路径上的 hash-chain 和 checkpoint receipts；CBFS composition；per-account quotas；SDK，包括 runner-side client 和 actor-bridge helper。

初始默认值（需经测量验证）：standard 的 hot window 为 7 天或 byte cap；inline limit 为 256 KiB。

v1 排除：unsolicited ingress、provider staking/slashing、actor-owned streams、public topics（Watchtower 的角色）、server-side semantic filters、generic KV/cache/locks、exactly-once claims、cross-stream transactions、communication-graph secrecy、traffic-analysis resistance。

验收测试：一个 ClawChat 等价聊天应用（standard + fast streams，通过 key envelopes 支持 100 人 membership）、一个 Homestead 风格 CRDT document（fast stream + checkpoint-bound CBFS snapshots）、一个 coordinator-with-five-workers demo，以及 live traffic 下的 provider-handoff 演练；全部基于 SDK，且没有专门定制的 transport code。

### 1.14 被拒绝的替代方案

- On-chain mailbox actor：区块延迟、每条消息 gas、所有消息公开。链仍适合承载需要最终性的消息，即拟议的 Watchtower 或 actor bridge。
- 严格拓扑隐私（所有东西都不透明、链下 provisioning rendezvous、可衰减 capability chains、blind billing）：成本与收益不成比例，因为 broker operator 仍可从时间推断通信图。保留内容加密；图保密明确不是目标。
- 原样复用 CBFS OwnerCapTokenV1：owner-only、bearer、没有 scopes。先例是对的，但工件不足，因此需要 StreamGrant。
- CBSS 作为成员密钥扇出机制：CIP-24 release path 绑定 job，且有 64-principal ACL 上限；不适合聊天室规模成员。CBSS 保留 root；envelopes 负责 fan-out。
- 面向客户端的托管 RabbitMQ/NATS：auth、receipts 和 lifecycle semantics 对不上，适配层本身就是产品。Managed engines 仍可作为契约之后的后端。
- RabbitMQ 语义（exchange/binding algebra）：表面积超过 agent 协调所需；一个 stream primitive 覆盖 queue、fan-out、chat、RPC。
- Redis 风格服务：语义杂糅，容易诱导 KV/lock 误用，持久性故事较弱。
- Per-runner sidecar：不能跨 runner；违反 no-sidecar 规则。
- 通过 validators 路由：把共识放到数据路径上，没有收益。

### 1.15 开放问题

1. StreamGrant wire format：encoding、nonce/context scheme、group-admin scope；兼容性和安全审查（虽小但真实，因为这是新的 auth surface）。
2. CBSS 集成细节：escrow object shape、rotation workload 的 CIP-24 authorization、rotation path 上的 release latency、CBSS 降级行为（cached keys？grace generations？），以及与 CBSS 团队讨论可能的 direct persistent-workload release extension。
3. Rotation 边界情况：跨 generation 边界 replay、envelope-lane retention、generation 中途新增 member。
4. Provider handoff：epoch/signing-key transition record、state transfer mechanism、fencing、continuity anchor；CIP 前需要一次设计 pass。
5. fast 参数：batch-commit interval、checkpoint cadence、measured loss-window bounds、loss event 的 SDK surface。
6. Push flow control：credit scheme、slow-consumer policy、同一连接上跨 groups 的公平性。
7. Storage engine：v1 的 embedded engine 选择；验证 managed engine 是否能置于契约之后的标准。
8. Retention/inline defaults：用验收应用流量验证。
9. Security validation：StreamGrant conformance tests、lease/terminal-state adversarial tests、rotation-exclusion test（被移除成员在 rotation 后不能读取或 append）、日志中无 plaintext 或 grants，以及 stated-leak review（chain records、CBSS policy/release activity、broker metadata）。

## 内容特色与重点分析

### 文章的核心定位

这篇设计稿不是单纯提出一个队列服务，而是在 Cowboy 体系中补齐“持久链下协调层”。它把 CBQS 定位为与 CBFS、CBSS 对等的基础设施原语：链负责控制平面，broker 负责数据平面，消息内容默认端到端加密，数据路径不写链。

### 最突出的设计特色

1. **控制平面与数据平面清晰分离**  
   链上只保存 stream 生命周期、所有权、provider、计费、generation 等控制信息；消息 append、消费、ack、重试、推送全部在链下 broker 完成。这避免了高频消息上链导致的延迟、gas 和公开性问题。

2. **隐私边界说得很诚实**  
   文章明确只保护内容机密性，不承诺隐藏通信拓扑。链、CBSS 和 broker 各自会暴露哪些元数据都被写清楚。这是很工程化的取舍：承认 broker 可从连接和时序推断通信图，因此不为昂贵但收益有限的严格拓扑隐私付费。

3. **认证机制专门为队列数据路径设计**  
   StreamGrant 没有直接复用 CBFS 的 OwnerCapTokenV1，而是加入 holder binding、逐请求证明、scoped verbs、expiry、caveats 和 authorization generation。它解决的是跨账户、细粒度授权和可撤销性问题。

4. **密钥分发采用“CBSS 托管根 + envelope 扇出”**  
   CBSS 不承担聊天室规模的每成员扇出，而只作为根密钥托管与恢复权威。成员通过 key stream 获取针对自己 HPKE key 包装的 envelope。这个设计绕开了 CIP-24 的 job-bound release 和 64-principal ACL 上限。

5. **一个 stream 原语覆盖多种协作模式**  
   work queue、fan-out topic、chat room、agent RPC、CRDT/event log 都映射到同一个 durable stream 模型，只是 consumer group/cursor/retention/delivery class 不同。这降低了系统表面积。

6. **standard 与 fast 两类投递契约区分明确**  
   standard 强调 durable commit、lease、dead-letter、redrive、hash-chain receipt，适合不能丢消息的工作流。fast 接受 bounded loss window，以 checkpoint 和 void event 明确暴露风险，换取更低成本和更低延迟，适合 presence、CRDT op log、telemetry。

7. **完整性与审计是系统一等公民**  
   standard 的 append 和状态变更都有签名 receipt，并形成 hash chain；fast 通过 checkpoint receipt chain 证明连续性。文章承认恶意 provider 仍可审查或销毁数据，但至少能留下可举证材料，惩罚机制推迟到以后设计。

8. **拒绝直接暴露 RabbitMQ/NATS 等现成系统**  
   文章不是否定这些引擎作为内部存储/stream 后端，而是否定它们作为客户端直接面对的系统，因为它们无法原生表达 StreamGrant、签名 receipts、terminal delivery cycles、redrive audit 等 Cowboy 所需契约。

### 设计重点

- **v1 的关键交付面**：chain-anchored streams、StreamGrant、默认加密、CBSS root escrow、envelope key distribution、standard/fast delivery、push-first transport、durable consumer groups、idempotent append、receipts、CBFS composition、SDK。
- **明确不做的东西**：exactly-once、通信图保密、抗流量分析、未授权 ingress、provider 质押/惩罚、actor-owned streams、public topics、generic KV/cache/locks、cross-stream transactions。
- **最需要后续设计的风险点**：StreamGrant wire format 与安全审查、CBSS 集成与降级行为、rotation 边界、provider handoff、防止 fork/rollback、fast 的 loss window 参数、push flow control、公平性和 storage engine 选择。

### 总体评价

这篇文章的重点不是“怎样做一个队列”，而是“怎样在 Cowboy 的链上/链下信任模型里做一个可审计、可恢复、可撤销、默认加密的多 agent 协调层”。它最有价值的地方在于边界清楚：哪些交给链、哪些交给 broker、哪些交给 CBSS、哪些明确不承诺。设计风格偏务实，尤其强调失败模式、撤销、重放、provider handoff、审计证据和验收测试，而不是只描述理想路径。
