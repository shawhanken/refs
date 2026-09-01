# CIP-39：Cowboy Queue System（Cowboy 队列系统）

> **⚠️ 本文是翻译件，不是权威规格。**
> 权威文本是英文原文 **`cowboy/docs/cips/cip-39-cowboy-queue-system.md`**。
> 两者不一致时**一律以英文原文为准**，本文视为过时。
>
> - **译自**：`cowboyinc/cowboy` 分支 `spec/cip-39-v2`，commit **`3b26751`**（2026-08-24）
> - **文档版本**：document version 2（v1 已被整体取代，见 §19）
> - **配套产物**：`cowboy/docs/cips/cip-39-gas-vectors-v2.json`（规范性 gas 向量，SHA-256 钉在 §16.1）
> - **精简方案与前后对比**：[`refs/analysis/2026-08-24_cip39_v2_simplification_plan.md`](../analysis/2026-08-24_cip39_v2_simplification_plan.md)
>
> 英文原文若有更新而本文未同步，请以上面那个 commit 为基准做 diff。

---

- **状态**：Draft
- **类型**：Standards Track
- **类别**：Core
- **创建**：2026-07-27
- **修订**：2026-08-24 —— document version 2
- **依赖（Requires）**：CIP-3（费用处理）、CIP-12（治理，以及 §6.1 读取的紧急暂停）、CIP-31（§4，§6.2 引用的 Platform Fee Account 规则）
- **相关（Related）**：CIP-2 与 CIP-10（作为 CBQS 客户端的 runner 工作负载）、CIP-7（公开流）、CIP-42（`/statusz`）

### 规范性关键词对照

原文按 RFC 2119 使用关键词。本译文固定采用下表译法，**加粗**即为规范性要求：

| 英文 | 中文 |
| --- | --- |
| MUST / REQUIRED / SHALL | **必须** |
| MUST NOT | **禁止** |
| SHOULD | **应当** |
| SHOULD NOT | **不应** |
| MAY | **可以** |

**所有标识符一律保留英文原样**：字段名、类型名、参数名（`cbqs.*`）、错误码名、域分隔符、代码块内容均不翻译，以免与实现产生歧义。章节编号与英文原文完全一致，可直接对照引用。

---

## 摘要

本提案引入 **Cowboy Queue System（CBQS）**：一个面向运行在不同 Cowboy Runner 上的工作负载的、持久化的链下消息服务。CBQS 只提供**一种有序流（stream）原语**，应用在其上构造工作队列、发布/订阅、请求/应答、以及可重放的事件日志。broker 侧的 **lane** 让许多相关的房间或文档共享同一条链上创建的流。

Cowboy 链是**治理与注册平面（governance and registry plane）**。它记录：谁拥有一条流、哪个 provider 服务它、哪把密钥可以授权访问它、以及它的 owner 是否付过钱。新的链下服务 `cbqsd` 是数据平面：存储记录、管理消费者组与投递租约（lease）、向已连接的客户端推送记录、并按批次持久化提交。

两个平面是**刻意解耦**的。追加、投递、确认、重放消息都不需要链上交易，任何消息路径上都不发生链上往返。broker 从一份**周期性刷新的注册表快照**提供服务，并在链不可达时**继续服务**；链上权威是在一个**有界且明示**的滞后内生效，而不是逐请求生效。

消息 payload 对 broker 是不透明字节。CBQS **不定义密钥分发机制**；需要机密性的应用在追加前自行加密。

## 背景

Cowboy 的 actor 与 actor 间消息属于共识执行。它们是承载最终性应用状态的正确路径，但不适合链下工作负载之间的高频协调。

Cowboy Runner 在共识之外执行任务与常驻工作负载，但彼此之间没有共享的消息骨干。一个要与多个专门 agent 通话的协调者，否则就得把持久化、重试、扇出、游标、租约、重连、授权、崩溃恢复统统当成应用基础设施自己实现一遍。

CBQS 就是这条骨干。它本质上是一个**普通的消息 broker**，只不过它的租户归属、授权与计费恰好记在区块链上；本规格的写法也确保 broker 的稳态行为就是一个普通消息 broker 的行为。

## 目标

CBQS **必须**提供：

1. 跨 runner 的消息交换，数据路径上**既无共识写入也无链上读取**；
2. 有序重放与至少一次（at-least-once）的工作投递；
3. 带**有界且显式背压**的推送投递；
4. 由 owner 控制、经链上权威撤销的授权，在**有界滞后**内生效；
5. 确认前先持久化提交，并附一份 provider 签名的承诺，使「已确认数据丢失」在**批次粒度**上可检测；
6. 在一条流内廉价地创建逻辑房间或文档；
7. 链不可用期间数据平面**持续服务**。

以下**不是**目标：把 payload 机密性做成平台服务、密钥分发与轮换、恰好一次（exactly-once）的应用副作用、通信图谱保密、共识发布、语义路由、分布式事务，以及通用的 Redis 式 KV / 锁操作。

以下在本文之外，需要后续 CIP：面向可修复日志的异步持久化投递类别、按 lane 的密码学验证、provider 重指派、provider 质押或罚没、共享持久游标、定时投递、按容量计价或分档计费、平台托管的加密、CBFS 归档集成，以及 §12 之外的传输绑定。

## 规格

本文中的关键词按 RFC 2119 解释（见上方对照表）。

本文中的每一条规范性要求，都写成**可以从被约束实现的外部观察**：从链上状态、从线上的规范字节（canonical bytes）、或从 broker 的响应。§20 给出符合性面（conformance surface）。

### 1. 术语

| 术语 | 定义 |
| --- | --- |
| **Stream（流）** | 一条有序、只追加、保留期有界的记录序列。 |
| **Lane** | 流内部一个不透明的、broker 侧的过滤视图。lane 继承父流的 provider、计费、保留策略与成员关系。 |
| **Provider** | 已注册的 `cbqsd` 运营者。 |
| **Consumer group（消费者组）** | broker 侧的投递状态，让一个或多个消费者竞争每条记录。 |
| **Registry snapshot（注册表快照）** | broker 最近一次在某个 finalized 高度读到的 Stream Registry 状态；在下次刷新前，授权与计费判定都基于它。 |
| **Authorization generation（授权代次）** | 嵌在每张 StreamGrant 里、由链控制的计数器。递增一次即让所有旧 grant 失效。 |
| **Checkpoint（检查点）** | provider 对一段连续的、已持久化提交记录的签名承诺。 |

### 2. 信任模型

链对以下内容具有权威：流的存在、归属、provider 指派、admin key、授权代次、流状态、以及 owner 的预付余额。`cbqsd` 对它已接受的记录、lane、组与投递状态具有权威。

payload 对 broker 是不透明字节。broker 能看到、且本文**不加隐藏**的是：哪些工作负载在连接、流/lane/组的标识符、消息大小、时序、流量、投递状态。链上另外公开：流的存在、owner、provider、计费活动、授权代次变更。

provider 可以审查、延迟或销毁数据。checkpoint 让部分不当行为**事后可证**；它**不提供可用性**，且 v2 没有链上争议、质押或罚没路径。数据必须在其 provider 之外存活的应用，**必须**自行维护持久副本。

需要 payload 机密性的应用在追加前自行加密。broker 永远拿不到密钥、也从不检视 payload，因此机密性的强度**恰好等于**应用自身密钥管理的强度。

### 3. 架构

```text
        CHAIN (governance + registry plane)
   provider records, stream ownership, admin keys,
   authorization generations, prepaid balances,
   governance parameters
                 |
                 |  periodic finalized snapshot read
                 |  (GET /cbqs/broker-state)
                 v
        +-----------------+          +-------------------------+
        |      cbqsd      | <======> |   runner workloads      |
        | records, lanes, |  push +  |   producers + consumers |
        | groups, leases, |  credit  |   (StreamGrant auth)    |
        | checkpoints     |          |                         |
        +-----------------+          +-------------------------+
```

链**禁止**接收消息 payload、lane 操作、组操作、投递租约、确认、或游标推进。

Stream Registry 系统 actor 分配在 `0x17`。CBQS 只占用一个顶层系统指令 opcode：

```text
SYS_CBQS = 218
```

其 payload 是有界的、带版本的 `CbqsInstructionV2`（§5）。

**数据平面独立性。** broker **必须**从其注册表快照提供追加、投递、确认与重放服务，期间不联系链。它**必须**至少每 `cbqs.snapshot_refresh_ms` 尝试刷新一次。刷新失败时，它**必须**继续服务上一份快照中出现的每一条流，并**必须**通过 `/statusz` 与 `/metrics`（§18）报告该状况。

有两道边界防止「独立」滑成「无界权威」，二者作用于不同操作：

- **已建立的会话继续服务**，只要其 grant 仍有效，无论快照多旧。这正是解耦要买的性质。
- **新会话要求快照不旧于 `cbqs.max_snapshot_age_blocks`。** 超过该期限，broker **必须**以 `ChainStateStale` 拒绝 `OpenSession`，同时继续服务已有会话。没有这道边界，一个干脆永不刷新的 broker 会满足本文其它每一条规则，却无限期忽略每一次撤销、暂停与关闭 —— 上面那条刷新规则约束的是**尝试**，不是**年龄**。

`SessionOpened` 会报告该会话被准入时的 `snapshot_height`，好让客户端**观察**自己的 broker 有多旧，而不是只能信任它。

有界的后果是被明说而非被抹掉的：链上的授权或状态变更，最早在下一次成功刷新时才到达一个已建立的会话；链中断期间根本不会到达。§7 用 grant 生命期约束由此产生的敞口；§16 固定刷新间隔、最大快照年龄及其上限。

**快照本身。** broker 通过从一个 Cowboy 节点（实践中就是它自己的节点）读取 finalized 的 Stream Registry 状态来获得快照，并**必须**用**同一份快照**评估同一个请求的每一项判定，而不是把不同高度读到的值混用。快照对它覆盖的每条流**必须**携带：`StreamRecordV2`、owner 的 `CbqsAccountV2`、被指派的 `ProviderRecordV2`、§16 的参数值、取快照时的 finalized `(height, block_hash)`，以及 §6 定义的**有效租金高度（effective rent height）** `H`。本文中的 `H_snapshot` 一律指这个被携带的值，**绝不是**物理高度。承载它的节点 RPC 形式属于实现细节；规范的是上述内容与原子性。

客户端直连 provider 端点。Cowboy Gateway 不在消息数据路径上。

### 4. 链上对象

本文中所有 CBQS 对象都是 **document version 2**。下文中每个带 `version` 字段的规范 CBQS 对象，其首字段为 `version: u8 = 2`，解码器**禁止**接受任何其它值，包括被取代文档的 version-1 字节。携带该字段的对象是：每个链上记录（§4.1、§4.2、§4.3）、每个生命期长于一次连接的 broker 记录（§8、§10.2、§14）、进入签名摘要的记录头（§9）、以及每个签名对象（§7、§11）。指令 payload（§5）与传输帧（§12.1）由其信封统一版本化 —— `CbqsInstructionV2` 的版本字节与帧的 `version: u8 = 2` —— 不在每个结构体内重复。

公钥携带显式算法标签。v2 只定义一种：

```text
SigningPublicKey = alg_tag_u8 || key_bytes    // Ed25519 = 1, 32 key bytes
```

共识准入**必须**拒绝以下 `SigningPublicKey`：`alg_tag` 不为 `1`、密钥字节不恰好 32 字节、或不是素数阶的规范 Ed25519 点 —— 与下文验证方所用的严格程度一致。准入一把没有任何签名能对其验证通过的密钥，等于给一条**可计费却永远无法授权**的流安上了权威。

本文定义的每一次 Ed25519 验证 —— `StreamGrantV2`（§7）、`SessionProofV2`（§7）、`CheckpointReceiptV2`（§11）—— 使用纯 Ed25519（RFC 8032），32 字节公钥、64 字节签名，并采用严格语义：要求规范的点与标量编码，拒绝弱的或小阶的公钥与 `R` 值。验证方**必须**逐个验证签名，**禁止**接受批量验证的结果。v2 的链上指令**没有任何一条携带签名**，所以这条规则的对象是 broker 与任何链下验证方，**不是**共识代码。

**规范编码。** 所有 CBQS 规范字节由 `cowboy-protocol-codec::cbqs` 产出。整数按其声明宽度以无符号大端编码。定长字节串与地址就是其原始定宽字节。变长字节串是 `u32 length || bytes`。option 缺席为 `0`、在场为 `1 || value`。vector 是 `u32 count || elements`。枚举标签取各定义处列出的数值标签；未知标签无效。结构体字段按此处列出的顺序出现。字段名与 map 键**从不**进入规范字节。

本文中每个 option 都以显式在场标签编码。实现**禁止**把缺席的 option 编成定宽哨兵值：**两个不同的值禁止共享同一串规范字节**。

**签名注册表。** 对每个签名对象，下表点名的 codec 函数返回 `domain_separator || canonical(除 signature 外的所有字段)`，签名者对这串字节的 Keccak-256 摘要签名。本表就是完整的 v2 注册表；实现**禁止**从 JSON、传输帧、或本地重复拼接字段来重建原像。

| 签名对象 | 域分隔符 | 唯一的 signing-bytes 函数 |
| --- | --- | --- |
| `StreamGrantV2` | `cbqs/stream-grant/v2` | `stream_grant_signing_bytes_v2` |
| `SessionProofV2` | `cbqs/session/v2` | `session_proof_signing_bytes_v2` |
| `CheckpointReceiptV2` | `cbqs/checkpoint-receipt/v2` | `checkpoint_signing_bytes_v2` |

三个域互不相同，因此对某一类对象有效的签名，对其它每一类都无效。

#### 4.1 ProviderRecordV2

```text
ProviderStatusV2 = Active = 1 | Deregistered = 2

ProviderRecordV2 {
  version:            u8,      // 2
  chain_instance_id:  Bytes32,
  provider:           Address,
  signing_key:        SigningPublicKey,
  signing_key_since:  u64,     // block at which signing_key took effect
  endpoints:          Vec<Bytes>,     // each a wss:// URI, ASCII only
  accepts_new:        bool,
  max_streams:        u64,
  assigned_streams:   u64,
  status:             ProviderStatusV2,
  metadata_hash:      Bytes32,
  registered_block:   u64,
}
```

没有 `Draining` 状态：`accepts_new = false` 已经能在不打扰既有流的前提下拒绝新流，而两个字段编码同一个谓词就会互相矛盾。

端点就是一个 URI，别无它物 —— v2 只定义一种传输，传输标签会变成一个只有一个合法值的字段。

共识准入按下列规则校验每个端点，遇到第一次失败即拒绝该指令：

1. 端点列表非空，且长度不超过 `cbqs.max_provider_endpoints`；
2. 每个 URI 非空，且不超过 `cbqs.max_provider_endpoint_uri_bytes` 字节；
3. **URI 的每个字节都落在 `0x21`–`0x7E` 范围内** —— 可打印 ASCII，排除空格与所有控制字节；且
4. 每个 URI 以字节串 `wss://` 开头，**按字节精确比较**。

规则 3 与 4 存在的理由只有一个：准入**原样存储** URI，因此「URL 解析器读出来的」与「逐字节扫描的读者读出来的」如果不同，就等于让一个共识可见字段有了两种含义。这里排除的是**全部非 ASCII**而不仅是控制字节，因为 IDNA 映射会把 U+3002、U+FF0F 之类的字符折叠成 `.` 与 `/`，于是解析器与日志会从同一串已准入的字节推出不同的主机。`WSS://` 被拒绝而非归一化，也是同一个理由。

以下向量是规范性的；符合规格的实现**必须**接受每个 accept、拒绝每个 reject：

```text
ACCEPT   wss://cbqs.example/ws
ACCEPT   wss://[2606:4700:4700::1111]/ws
ACCEPT   wss://198.51.100.7:8443/ws
REJECT   https://cbqs.example/ws          (rule 4: scheme)
REJECT   WSS://cbqs.example/ws            (rule 4: case)
REJECT   wss://cbqs.example/a<TAB>b       (rule 3: control byte)
REJECT   wss://cbqs.example/a b           (rule 3: space)
REJECT   wss://169。254。169。254/ws       (rule 3: non-ASCII)
REJECT   wss://good.example／evil/ws      (rule 3: non-ASCII)
```

准入不做任何其它解析。**在此准入的 URI 并不表示该端点可以安全拨号。** 客户端**必须**对它解析出的每个地址施加 §12.4 的拨号策略：连接前一次，每次重定向后再一次；§20 第 7 项使之可测。

注册表维护 `assigned_streams`：每次 `CreateStream` 点名该 provider 时加一，该流转入 `Closed`（v2 唯一的终态）时减一。`RegisterProvider` **必须**把它置零，且没有任何指令可以直接设置它。当被点名的 provider 不是 `Active`、`accepts_new` 为 false、或 `assigned_streams` 已等于 `max_streams` 时，`CreateStream` **必须**被拒绝。`UpdateProvider` **禁止**把 `max_streams` 降到当前 `assigned_streams` 之下，也**禁止**在 `assigned_streams` 非零时设 `status = Deregistered`。§5 中 provider 侧的 `CloseStream` 正是让这条退出路径在 owner 已不再参与时仍然可达的东西。

provider **禁止**把保留的系统地址注册为自身地址，尤其是 `0x17` 与 `0x18`：§6 会在一次转移中同时改动 custody 账户、provider 账户与 Platform Fee Account，其中任意两者互为别名都会让一次入账覆盖另一次。

更换 provider 签名密钥是**前瞻的**。`UpdateProvider` **必须**把 `signing_key_since` 设为其提交所在高度，§11 用它判定新密钥管辖哪些 checkpoint，因此从被泄露密钥的轮换会对**其后提交的每个 checkpoint**生效。

provider 注册是无许可的，且不产生可罚没的质押。

#### 4.2 StreamRecordV2

```text
StreamStatusV2 = Active = 1 | Suspended = 2 | Closed = 3

StreamRecordV2 {
  version:                  u8,      // 2
  chain_instance_id:        Bytes32,
  stream_id:                Bytes32,
  owner:                    Address,
  owner_nonce:              u64,
  admin_key:                SigningPublicKey,
  provider:                 Address,
  authorization_generation: u64,
  status:                   StreamStatusV2,
  rate_per_block:           u128,    // snapshotted at creation, immutable
  last_settled_block:       u64,     // effective rent height (§6)
  created_at_block:         u64,     // effective rent height (§6)
}
```

流 id 为：

```text
stream_id =
  keccak256(
    "cbqs/stream-id/v2" ||
    chain_id_u64_be ||
    chain_instance_id ||
    owner_address_20 ||
    owner_nonce_u64_be
  )
```

`chain_instance_id` 是 genesis 配置指纹。genesis **必须**在任何 CBQS 指令能执行之前，把它播种进一个 Stream Registry 单例。处理器**必须**读取该单例而非节点本地配置，并**必须**拒绝缺失或格式错误的单例。

Stream Registry **必须**拒绝 `(owner, owner_nonce)` 已被使用过的 `CreateStream`，包括那条流已经关闭之后。**owner nonce 永不可重用。**

`owner`、`owner_nonce`、`provider`、`rate_per_block` 在流的整个生命期内不可变。把应用迁到另一个 provider 属于应用迁移；§4.4 给出其顺序义务。

**本记录中存储的每一个高度都是有效租金高度（§6），绝不是物理区块高度。** `CreateStream` 把 `created_at_block` 与 `last_settled_block` 都设为其提交时的有效租金高度。于是两个时钟永远不会相减，暂停也永远不会让「已过区块数」变成负数 —— 否则 `settle` 会被永久卡死，并连带卡死 `CloseStream` 以及一切依赖它的退出路径。

**`rate_per_block` 是快照的，不是实时读取的。** `CreateStream` 把 `cbqs.stream_rate_per_block` 复制进记录，`settle` 只读这份副本。于是一次治理写入只对其后创建的流定价，**永远不会对已经过去的区块重新计价**。若实时读取该参数，一次治理写入就能把全网每一段未结算区间按新费率追溯重算 —— 最多可达 `cbqs.settlement_interval_blocks` 那么长的欠费 —— 那正是 §16 所说「治理变更是前瞻的」的反面。这个选择的代价被明说而非隐藏：v2 **没有**为既有流重新定价的机制，引入它需要后续 CIP。

流**在链上不携带任何配置**。保留期、消息大小与投递默认值都是 broker 侧设置（§14），由治理参数（§16）设上限。这正是「链必须裁决的」（谁拥有这条流、谁可以对它动作）与「只有 broker 执行的」之间的分界。

#### 4.3 CbqsAccountV2

```text
CbqsAccountV2 {
  version:        u8,       // 2
  owner:          Address,
  balance:        u128,     // nano-CBY held in registry custody
  active_streams: u64,
}
```

每个 owner 一条账户记录，持有该 owner **所有**流的预付余额。计费按账户而非按流：没有按流托管、没有按流费率协商、没有报价单。

`active_streams` 统计该 owner 处于 `Active` 或 `Suspended` 的流。`CreateStream` 令其加一；转入 `Closed` 令其减一。当会超过 `cbqs.max_streams_per_owner` 时，`CreateStream` **必须**被拒绝。

**托管（custody）。** 存入的余额是由 Stream Registry 系统 actor **`0x17`** 真实持有的托管资金，也就是处理器自身运行所在的账户。`TopUpAccount` 在同一次转移中把原生 CBY 从付款方转入 `0x17` 并等额贷记 `balance`；每一次对 `balance` 的借记都在同一次转移中从 `0x17` 转出等额资金。处理器**必须** fail closed，而不是贷记一笔它无法从托管中借出的份额。由于原生账户余额的位宽窄于 `u128`，无法用原生位宽表示的贷记或借记**必须** fail closed，而不是截断。

**账户记录不是永久的。** 使 `balance == 0` 且 `active_streams == 0` 的处理器**必须**删除它。没有这条规则，`TopUpAccount` 就能以每条 1 nano-CBY 的代价铸出无限多的永久记录；有了它，唯一能比其资金活得更久的注册表状态就只剩流，而流要付 §6 的创建费。

当 `account` 是保留系统地址时，`TopUpAccount` **必须**被拒绝，理由与 §4.1 的别名问题相同。

#### 4.4 应用迁移

provider 指派不可变，所以把应用迁到另一个 provider —— 也是 v2 在 provider 停止服务时提供的唯一补救 —— 是一次由应用自己执行的迁移：

1. 创建一条点名新 provider 的新流；
2. 从应用自己掌控的持久来源复制或重放数据；
3. 签发新的 grant 并重定向客户端；然后
4. **只有在验证目标流最新的 checkpoint 已覆盖源流所持有的全部内容之后，才关闭旧流。**

第 4 步的顺序是**义务**，不是建议：先关闭会把一次迁移变成一次数据丢失，而 v2 没有任何争议路径能把它捞回来。目标流拥有独立的 `stream_id` 与独立的 checkpoint 链。SDK **应当**把这套流程作为单一流程暴露出来。

### 5. 链上指令

`CbqsInstructionV2` 的结构是 `version: u8 = 2 || tag: u8 || body`，包含以下变体：

| Tag | 指令 | 授权方 | 效果 |
| --: | --- | --- | --- |
| 1 | `RegisterProvider` | 调用者账户 | 创建 `ProviderRecordV2`。 |
| 2 | `UpdateProvider` | provider 账户 | 变更端点、密钥、metadata、准入或状态。 |
| 3 | `CreateStream` | owner 账户 | 创建流、收取创建费、递增 provider 与账户计数器。 |
| 4 | `UpdateStream` | owner 账户 | 轮换 admin key 且/或递增授权代次。 |
| 5 | `CloseStream` | owner 账户；或流处于 `Suspended` 时的被指派 provider | 结算租金并转入 `Closed`。 |
| 6 | `TopUpAccount` | 付款账户 | 把 CBY 转入指定 owner 的 CBQS 余额。 |
| 7 | `SettleStream` | 无许可 | 结算已过租金，并落实暂停或恢复。 |
| 8 | `WithdrawAccount` | owner 账户 | 在该 owner 没有存活流时提取余额。 |

规范 payload 为：

```text
RegisterProviderV2 {
  signing_key:   SigningPublicKey,
  endpoints:     Vec<Bytes>,
  max_streams:   u64,
  accepts_new:   bool,
  metadata_hash: Bytes32,
}

UpdateProviderV2 {
  signing_key:   Option<SigningPublicKey>,
  endpoints:     Option<Vec<Bytes>>,
  max_streams:   Option<u64>,
  accepts_new:   Option<bool>,
  metadata_hash: Option<Bytes32>,
  status:        Option<ProviderStatusV2>,
}

CreateStreamV2 {
  owner_nonce: u64,
  provider:    Address,
  admin_key:   SigningPublicKey,
}

UpdateStreamV2 {
  stream_id:                     Bytes32,
  admin_key:                     Option<SigningPublicKey>,
  bump_authorization_generation: bool,
}

CloseStreamV2      { stream_id: Bytes32 }
TopUpAccountV2     { account: Address, amount: u128 }
SettleStreamV2     { stream_id: Bytes32 }
WithdrawAccountV2  { amount: u128 }
```

携带 `admin_key` 的 `UpdateStream` **必须**递增 `authorization_generation`，无论 `bump_authorization_generation` 取值如何；既不带新 admin key 也不带 `bump_authorization_generation = true` 的 `UpdateStream` **必须**作为空操作被拒绝。一次不让在外 grant 失效的密钥轮换，会让旧密钥签发的 grant 继续存活，那与轮换的目的正好相反。

当流处于 `Closed` 时，`UpdateStream` 与 `CloseStream` **必须**被拒绝。

**`CloseStream` 有两类被授权的调用者。** owner 任何时候都可以关闭。被指派的 provider 可以关闭一条落实状态为 `Suspended` 的流 —— 也就是 owner 已停止付费的流 —— 否则对一条被遗弃的流，`assigned_streams` 永不递减，provider 既无法调低 `max_streams`，也永远到不了 `Deregistered`（§4.1）。provider 的关闭不是扣押：它的结算与 owner 关闭时完全一致，不会转移任何 owner 本来不欠的余额。

`TopUpAccount` 点名它所贷记的账户，因此第三方**可以**为某个 owner 充值。账户记录不存在时由它创建。当 `amount` 为零时**必须**被拒绝。

`WithdrawAccount` **必须**被拒绝，除非 `active_streams == 0`、`amount <= balance` 且 `amount` 非零。`active_streams == 0` 意味着该 owner 曾拥有的每条流都已在关闭时结算过，因此对余额不再有**可收取**的债权。它**并不**意味着每笔债权都被付清：§6 的部分支付分支只支付余额所能覆盖的部分，其余被核销 —— 这正是 §6 的 broker 侧可用性检查采取保守而非乐观策略的原因。

### 6. 计费

CBQS 就「一条流的存在」收取**按流的固定费率**，从该 owner 的账户余额中扣除。它**不计量**消息数、字节数或容量：provider 的敞口改由 §16 的按流治理上限（broker 执行）与其自身的 `max_streams` 来约束。

每条流的费率是创建时快照进其记录的 `rate_per_block`（§4.2）。

#### 6.1 有效租金高度

租金以**有效租金高度**而非物理区块高度计量，这样在 CIP-12 对 Stream Registry 的紧急暂停期间 —— 期间没有 CBQS 指令能执行，因而没有 owner 能充值 —— 不会累积一笔谁也无法支付的租金。

注册表的暂停记账记录位于治理键 `"system:gov:pause-accounting:" || 0x17`，内容为 `{ completed_pause_blocks: u64, active: Option<{ paused_at_block: u64, expires_at_block: u64 }> }`。对物理 finalized 高度 `P`：

```text
coverage(P) = completed_pause_blocks +
              active.map(|a| min(P, a.expires_at_block) - a.paused_at_block)
                    .unwrap_or(0)

H = P - coverage(P)                       // checked; fails closed on underflow
```

**只有上面这个表达式是符合规格的。** 暂停的到期是惰性的 —— 一段已过期的区间会一直留在 `active` 里，直到某条指令把它折进 `completed_pause_blocks` —— 因此 `coverage` **必须**在读取时用对 `expires_at_block` 取 `min` 的方式现算。省掉 active 区间会让时钟在暂停到期时整段跳进；省掉那个上限则会让租金时钟永久冻结，把每个 provider 钉死在无偿服务里。

每条 CBQS 指令都按 CIP-12 §7 做了暂停分类，且 `0x17` 在该节的可暂停集合内。

#### 6.2 结算

结算只在此处定义一次，其它每一节都引用这个函数：

```text
settle(stream, H):
  require stream.status in {Active, Suspended}
  require H >= stream.last_settled_block          // §4.2 keeps both on one clock
  account = account_of(stream.owner)

  if stream.status == Suspended:
      // A suspended stream is served nothing (§7), so it accrues nothing.
      // Revival starts the meter again at the current height.
      if account.balance >= stream.rate_per_block:
          stream.last_settled_block = H
          stream.status = Active
      distribute(0, stream.provider)
      return 0

  due = (H - stream.last_settled_block) * stream.rate_per_block   // checked u128

  if account.balance >= due:
      account.balance -= due
      stream.last_settled_block = H
      paid = due
  else:
      paid_blocks = account.balance / stream.rate_per_block
      paid        = paid_blocks * stream.rate_per_block
      account.balance -= paid
      stream.last_settled_block += paid_blocks
      stream.status = Suspended
  distribute(paid, stream.provider)
  return paid
```

`stream.rate_per_block` 非零（§16 约束了它所复制的那个参数），因此除法有定义；而且除法只出现在 `else` 分支，全零费率根本到不了那里 —— 那时 `due` 为零。

**`Suspended` 的流不累积租金。** broker 对它不提供任何服务（§7），因此对该时段计费等于向 owner 收取「没有服务」的费用，还会让一条被遗弃的流的欠费无界增长 —— 留给 owner 一张只能靠支付「几个月毫无投递的时间」才能摆脱的账单。所以暂停是**计价表停摆**，不是债务滚存；恢复时从当前高度重新计时，而不是回填缺口。

`distribute` 把每一笔已付金额从托管中拆分出去：

```text
provider_share = paid * cbqs.rent.provider_bps / 10000
platform_share = paid - provider_share
```

任何治理写入之后，`cbqs.rent.provider_bps + cbqs.rent.platform_bps == 10000` **必须**成立（在提案侧强制执行），且 genesis 校验**必须**拒绝违反它的播种值。`provider_share` 贷记给 provider 账户；`platform_share` 贷记给 **Platform Fee Account，系统 actor `0x18`**，与 CIP-31 §4 是同一个账户、同一条规则。该地址是固定的，所以结算无需读状态即可定位它，也没有任何治理写入能改道这笔份额。整数除法向零截断，而平台份额取的是**精确补数**，因此对任意输入都有 `provider_share + platform_share == paid`，且托管被借记的正好是 `paid`。

**两笔贷记都无条件执行，金额为零时也一样。** 一个跳过零值写入的处理器，其计量与不跳过的处理器不同，二者会在同一个区块里对 gas 产生分歧。这也是为什么 `settle` 的 suspended 分支仍要调用 `distribute(0, …)`。

#### 6.3 创建费

`CreateStream` **必须**从 **owner 的原生账户**（**而非**其 CBQS 余额）借记 `CBQS_STREAM_CREATION_CHARGE`，并在写入流记录的同一次转移中贷记给零地址；无法完成该借记时**必须**失败且不创建流。

```text
CBQS_STREAM_CREATION_CHARGE = 5_000_000_000     // nano-CBY
```

这句话里有三个承重性质。它是**协议常量**而非治理参数，因此没有任何治理写入能把永久注册表状态定价为零。它**贷记给零地址** —— 与 CIP-3 对销毁价值的处置一致 —— 因此自营 provider 的 owner 无法像回收 `provider_bps` 那样通过租金分账把它拿回去。它从**原生**账户而非托管中借记，因此不会吃掉 provider 已经赚到但尚未结算的余额 —— 一次跑在 provider 债权前面的销毁，会摧毁 owner 本来就欠下的价值。

重新调整该常量属于协调发布的协议变更，与 §16.1 的计量常量同理。

#### 6.4 暂停、可用性与结算节奏

`Suspended` 意味着在上一次结算时 owner 的余额不足以覆盖已累积的租金。broker 会拒绝一条 `Suspended` 流的每一次变更操作（§7）。它通过一次 `TopUpAccount` 加一次发现余额足够覆盖至少一个区块的 `SettleStream` 而恢复；`settle` 在该路径上会置 `status = Active`，因此恢复不需要单独的指令。**没有宽限期，也没有过期状态**：一条被暂停的流的数据能存活多久，是 provider 的保留策略决定的（§13），不是共识状态 —— 因为共识观察不到数据是否还在。

**broker 侧可用性。** broker 从快照而非仅从落实状态推导可服务性，因为无许可结算可能滞后。对一条读起来是 `Active` 的流，它计算

```text
due_stream = (H_snapshot - last_settled_block) * rate_per_block
required   = due_stream * account.active_streams        // checked u128
```

并在 `account.balance < required` 时拒绝变更操作。**那个乘法正是这套检查在共享余额下仍然成立的原因**：`due_stream` 是按流的，而 `balance` 是按 owner 的，所以逐流比较会让「一条流的资金」买到该 owner 全部流的服务 —— 最多可达 `cbqs.max_streams_per_owner` 条，分散在同样多的不同 provider 上，而它们彼此看不见对方的债权。`active_streams` 就在 broker 已经读取的同一条账户记录里，因此这个界可以从快照算出来。它**刻意保守**：owner 必须为整个流群备足资金，而不是只为最便宜的一条。溢出或 `H_snapshot < last_settled_block` 时 fail closed。

结算是无许可的。没人有义务提交它，因此想拿钱、或想让暂停在链上可见的 provider，会自己提交 `SettleStream`。provider **应当**至少每 `cbqs.settlement_interval_blocks` 为其每条流结算一次。未结算的余量是 provider 的信用风险。在共享余额下，该风险**并不**只由 owner 的余额封顶 —— 另一个 provider 处的兄弟流可能先把余额抽干 —— 因此 provider 实际握住的界是：自它上次结算以来它所提供的服务量。这正是上述节奏才是关键杠杆的原因，也是 broker 侧可用性检查必须保守的原因。

### 7. 授权

由流当前的 admin key 签发 `StreamGrantV2`。owner 通过 `UpdateStream` 控制这把密钥。**owner 账户签名本身不是有效的 grant 签名。**

```text
StreamGrantV2 {
  version:                  u8,      // 2
  chain_instance_id:        Bytes32,
  stream_id:                Bytes32,
  authorization_generation: u64,
  grant_nonce:              Bytes32,
  holder_signing_key:       SigningPublicKey,
  verbs:                    u16,
  lane_scope:               Any = 1 | Exact = 2 (Bytes32) | Set = 3 (Vec<Bytes32>),
  group_scope:              Any = 1 | Exact = 2 (Bytes32),
  not_before_ms:            u64,
  expires_at_ms:            u64,
  max_message_bytes:        u32,
  max_append_bytes_per_sec: u64,
  max_in_flight:            u32,
  max_lane_creates_per_min: u32,
  signature:                Signature,
}

grant_id = keccak256(stream_grant_signing_bytes_v2(grant))
```

verb 位为：

| Bit | Verb |
| --: | --- |
| 0 | `APPEND` |
| 1 | `CONSUME` |
| 2 | `ACKNOWLEDGE` |
| 3 | `REPLAY` |
| 4 | `GROUP_ADMIN` |
| 5 | `REDRIVE` |
| 6 | `LANE_ADMIN` |
| 7 | `STREAM_ADMIN` |

高于 7 的位**必须**被拒绝。位 0–6 的含义与 document version 1 完全一致，因此 v1 的 verb 表可原样移植；`STREAM_ADMIN` 是位 7 上的新增项，授权 §14 的设置变更。

broker **必须**从其当前快照校验：

1. admin key 对 `stream_grant_signing_bytes_v2` 的签名；
2. `chain_instance_id` 与 `stream_id` 精确一致；
3. `authorization_generation` 等于快照中的值；
4. 时间窗口，允许至多 `cbqs.max_clock_skew_ms` 的偏差；
5. `expires_at_ms - not_before_ms <= cbqs.max_grant_ttl_ms`，且 `Set` 型 lane scope 至多含 `cbqs.max_lane_ids_per_grant` 个已排序、去重的 id；
6. 所请求的 verb，以及**两个** scope 维度：**group scope 永远不会放宽 lane scope**，因此对键为 `(stream_id, L, group_id)` 的组做操作，要求 `L` 落在 grant 的 lane scope 内**且** `group_id` 落在其 group scope 内；以及
7. grant 的各项限制与 §16 上限、§14 设置的交集 —— 有效界是三者的最小值。

**会话建立。** 连接建立时，broker 发送一个随机 32 字节 challenge 与一个 `session_id`（两者都不可预测），以及一个 `expires_at_ms`。客户端返回：

```text
SessionProofV2 {
  version:           u8,       // 2
  chain_instance_id: Bytes32,
  stream_id:         Bytes32,
  grant_id:          Bytes32,
  session_id:        Bytes32,
  challenge:         Bytes32,
  signature:         Signature,
}
```

由 grant 的 holder key 对 `keccak256(session_proof_signing_bytes_v2(proof))` 签名。broker **必须**拒绝该 proof，除非以下全部成立；遇到第一次失败即**必须**关闭连接：

- `proof.session_id` 与 `proof.challenge` 正是本连接被签发的那一对，且该对**从未**完成过会话 —— `session_id` 是**一次性的**，因此一个被截获的 `CompleteSession` 帧打不开任何东西；
- proof 在 `expires_at_ms` 之前到达；
- 对 `OpenSession` 中携带的 grant，有 `proof.grant_id == grant_id(grant)`，且 `proof.stream_id` 与 `proof.chain_instance_id` 等于该 grant 的对应值；以及
- 签名在 `grant.holder_signing_key` 下验证通过。

因此，没有 holder 私钥的被截获 grant 打不开会话，而一个被截获的 proof 也打不开第二个会话。

**会话内的请求不逐条签名。** 每个 `Request` 帧携带它所执行于其下的 `session_id`（§12.1），broker **必须**用**恰好那个会话的 grant** 执行它，**必须**拒绝 body 中点名了非本会话 `stream_id` 的请求，并**必须**拒绝在发送它的连接上并未开启的 `session_id`。**权威来自会话，不来自 body。**

由此接受的敞口写在「安全性考量」里：能向一个已建立的 TLS 会话注入的攻击者，就以该会话的权威行事。逐请求签名同样挡不住同一个攻击者重排或丢弃帧。

**撤销。** 一次 `authorization_generation` 递增会让该流全部在外 grant 失效。有两条规则约束一张被撤销的 grant 还能被用多久：

- broker **必须**终止每一个 grant 已与快照不符的会话，最晚不迟于「观察到该变更的那次刷新之后它所服务的第一个请求」，并**禁止**在未通过该检查的 grant 下服务请求；以及
- broker **禁止**基于旧于 `cbqs.max_snapshot_age_blocks` 的快照开启新会话（§3）。

一个**空闲**会话在它发出请求之前不会被第一条规则终止，这没有危害 —— 空闲会话不执行任何操作 —— 但这意味着该保证是**以已服务请求为度量**，不是以墙钟时间为度量。§20 第 4 项按此处所述的规则来测试。

把密钥从被泄露的 holder 处轮换走的 owner，**必须**把 grant 自身的到期时间当作有保证的那个界，这也是 `cbqs.max_grant_ttl_ms` 设上限的原因。

对以下三种流，broker **必须**拒绝开启会话：快照中状态不是 `Active` 的流、不在快照中的流、以及 owner 余额未通过 §6 可用性检查的流。对应错误码为：`Closed` 流用 `StreamNotActive`，`Suspended` 流或余额检查失败用 `StreamSuspended`，快照中不含的流用 `StreamUnknownToBroker`（§15）。

### 8. Lane

全零的 `lane_id` 是默认 lane，每条流都有。额外的 lane 属于 broker 侧状态：

```text
LaneRecordV2 {
  version:       u8,       // 2
  stream_id:     Bytes32,
  lane_id:       Bytes32,
  status:        Active = 1 | Closed = 2,
  created_at_ms: u64,
  metadata_hash: Bytes32,
}

lane_id = keccak256("cbqs/lane-id/v2" || stream_id || lane_nonce)
```

持有 `LANE_ADMIN` 的客户端通过选取一个随机 `lane_nonce` 创建 lane。`metadata_hash` 是不透明的应用元数据，创建时固定，由 `ListLanes` 返回；broker 从不解释它。lane 的创建与关闭不需要链上交易，也不单独计租。

有两道界，各自约束不同的集合：

- `cbqs.max_lanes_per_stream` 约束**活跃** lane 数（含默认 lane）；且
- `cbqs.max_lane_tombstones_per_stream` 约束为防重用而保留的已关闭 lane id 数。到达该界时，broker **必须**以 `LaneLimitExceeded` 拒绝进一步的 lane 关闭，而不是忘掉一个墓碑 —— 忘掉一个墓碑就等于允许一个已关闭 id 带着另一段历史被重建。

grant 的 `max_lane_creates_per_min` 按 `(stream_id, grant_id)` 在 60 秒滚动窗口上强制执行：在时刻 `T`，只有当 `(T - 60_000 ms, T]` 内被准入的创建数少于该值时，broker 才准入一次创建；取值为零则拒绝一切 lane 创建。在准入之前就被拒绝的请求不消耗额度。没有这条 caveat，单个 `LANE_ADMIN` 持有者就能在一次连接里烧光该流的整个 lane 命名空间 —— 而那是永久的。

已关闭的 lane 拒绝新的追加，但在保留地板之上仍可重放。**已关闭的 lane id 禁止重用。**

broker 提供有界、分页的 lane 枚举，按调用者的 lane scope 过滤，并以 `cbqs.max_lane_list_page` 封顶。`ListLanes` 要求 `CONSUME`、`REPLAY`、`LANE_ADMIN` 三者至少其一；单有 `APPEND` **不**授权拓扑发现。`after_lane_id` 是排他游标。broker 先施加 lane scope 再施加页大小，且仅当还有另一条被授权的 lane 时才返回 `next_after_lane_id`。

lane 是一个总序之上的路由过滤器。lane 没有独立的 provider、计费、保留策略或定序权威，也没有按 lane 的配额切分：一条热 lane 消耗全流共享的吞吐，并可能对其兄弟 lane 造成背压。按 lane 限定的 grant 限制的是**一个诚实 broker 会提供什么**；它**不是**密码学边界。

### 9. 记录模型

```text
AppendRequestV2 {
  stream_id:            Bytes32,
  lane_id:              Bytes32,
  client_message_id:    Bytes32,
  client_created_at_ms: u64,
  expires_at_ms:        u64,
  payload:              Bytes,
}

RecordHeaderV2 {
  version:           u8,       // 2
  stream_id:         Bytes32,
  lane_id:           Bytes32,
  client_message_id: Bytes32,
  created_at_ms:     u64,
  expires_at_ms:     u64,
}
```

一条记录由 broker 分配的 `sequence: u64` 标识。流的第一条记录 `sequence = 0`；每提交一条记录 sequence 恰好加一，在流内单调，且永不重用。broker 把 `client_created_at_ms` 复制到 `created_at_ms`。`expires_at_ms = 0` 表示该记录没有应用层截止时间。

`RecordHeaderV2` **携带版本字节**，因为它是 `record_digest`（§11）内部的规范原像，而后者会被 provider 签名：两个对「这个字节是否存在」有分歧的实现，会对同一条记录产出不同的签名摘要。

应用语义、应答路由、存储引用、加密封装、应用层去重标识符，统统属于 payload 内部。broker 可见的记录头只含投递机制所需内容；broker **禁止**解释 payload 字节。

超过有效 `max_message_bytes`（§14 设置、grant 限制、`cbqs.max_message_bytes` 三者的最小值）的 payload **必须**以 `MessageTooLarge` 拒绝。

### 10. 投递

只有在记录跨过 §11 的持久化提交边界之后，一次追加才被确认。broker **禁止**从内存或操作系统页缓存确认。

#### 10.1 幂等追加

去重键是 `(stream_id, holder_signing_key_id, client_message_id)`，其中

```text
holder_signing_key_id = keccak256("cbqs/signing-key-id/v2" || canonical(key))
```

首次接受时 broker 记录它自己的 `received_at_ms`。若新键的 `client_created_at_ms` 晚于 `received_at_ms + cbqs.max_clock_skew_ms`，或早于 `received_at_ms - (cbqs.idempotency_horizon_ms + cbqs.max_clock_skew_ms)`，则**必须**拒绝。首次接受后条目至少保留 `cbqs.idempotency_horizon_ms`；客户端时钟不会缩短该保留期。在该时窗内：完全相同的重试返回原结果；以不同规范请求字节复用同一键返回 `IdempotencyConflict`；超出时窗后的重试返回 `IdempotencyExpired`。

#### 10.2 消费者组

组是 broker 侧对象，**不是**链上状态。

```text
GroupConfigV2 {
  version:                u8,       // 2
  group_id:               Bytes32,
  lane_id:                Bytes32,
  mode:                   StrictFifo = 1 | Concurrent = 2,
  start:                  Head = 1 | At = 2 (sequence: u64),
  visibility_timeout_ms:  Option<u64>,
  max_visibility_ms:      Option<u64>,
  max_in_flight:          Option<u32>,
  max_attempts:           Option<u16>,
  record_deadline_ms:     Option<u64>,
  dead_letter_ttl_ms:     Option<u64>,
}
```

这六个可配置字段是 option，因为 §14 允许组在省略它们时继承流的设置；缺席的 option 用显式缺席标签，**绝不是**零哨兵（§4）。当一个在场的值违反下列任一条时，返回 `GroupConfigInvalid`，并在 `details` 中点名出错字段：

| 字段 | 规则 |
| --- | --- |
| `visibility_timeout_ms` | 非零，且 `<=` 同一记录的 `max_visibility_ms` |
| `max_visibility_ms` | 非零，且 `<= cbqs.visibility_ms` |
| `max_in_flight` | 非零，且 `<= cbqs.max_in_flight_per_group` |
| `max_attempts` | 非零，且 `<= cbqs.max_attempts` |
| `record_deadline_ms` | 非零，且 `<= cbqs.retention_ms` |
| `dead_letter_ttl_ms` | 非零，且 `<= cbqs.retention_ms` |
| `start = At(sequence)` | 位于该流 `first_retained_sequence` 之上，否则 `CursorTooOld` |

`record_deadline_ms` 被 `cbqs.retention_ms` 封顶，理由是**活性**而不是整洁：§13 只把保留地板推过「对每个组都已终态」**或**「已过该组截止时间」的记录，而 §10 又禁止在压力下驱逐存活记录。一个不设上限的截止时间，会让某个永不确认的组把地板永久钉住、把 `retained_bytes_limit` 塞满，于是每条 lane 上的每个生产者都永久收到 `Backpressure`，与此同时固定租金还在照常累积。

broker 状态以 `(stream_id, lane_id, group_id)` 为组的键。创建、更新或删除组需要同时对该组及其 lane 生效的 `GROUP_ADMIN`（§7 第 6 项）。`cbqs.max_groups_per_stream` 约束每条流的活跃组数，`cbqs.max_group_tombstones_per_stream` 约束保留的删除墓碑数；**这个三元组禁止重用**。

每条记录至少一次地投递给每个适用的组，直到出现一个终态：

```text
ACKED | DEAD_LETTERED | EXPIRED
```

投递会创建一个 lease，其中记有组、记录 id、投递周期 id、尝试次数、消费者 `holder_signing_key_id` 与到期时间。`Ack`、`Nack`、`Extend`、`Reject` **必须**点名该 lease；并且 **broker 必须以 `LeaseStale` 拒绝那些「会话的 `holder_signing_key_id` 与 lease 签发对象不同」的 lease 操作**。没有这道检查，任何持有 `ACKNOWLEDGE` 的 holder 都能终结另一个 holder 在途的记录 —— `Reject` 直接转入 `DEAD_LETTERED` —— 而在会话级权威下，行为主体的身份已经不再逐请求出现在线上。过期的 lease 不能变更更晚的投递周期。

- `Ack` 把该周期转入 `ACKED`。
- `Nack` 在一个有界延迟后释放它以便重试；若本次尝试用尽 `max_attempts`，则转入 `DEAD_LETTERED`。
- `Extend` 推进到期时间，但**绝不**超过该组自身有效的 `max_visibility_ms`。
- `Reject` 直接转入 `DEAD_LETTERED`。
- `record_deadline_ms` 到期则转入 `EXPIRED`。

一个 `DEAD_LETTERED` 周期在成为终态后的 `dead_letter_ttl_ms` 内仍可检视与 redrive，此后 broker **可以**丢弃其投递状态；记录本身仍只受 §13 保留策略约束。

终态是单调的。`Redrive` 在组尾创建一个新的投递周期；它**不会**抹掉先前的终态，也不会回卷日志。

`StrictFifo` 只暴露最低的非终态记录；一个终态会填上游标空洞。`Concurrent` 可以租出更靠后的记录，上限为 `max_in_flight`。

两道在途上限同时生效，一次 lease 必须在两者下都有余量：`GroupConfigV2.max_in_flight` 约束该组跨所有 holder 的在途 lease 数；`StreamGrantV2.max_in_flight` 约束单个 `holder_signing_key_id` 在该流上跨所有组与连接持有的 lease 数。当多张有效 grant 点名同一把 holder key 时，该 holder 的上限取这些 grant 的**最大值**：owner 签发了其中每一份额度，而取最小值会让一张更晚的窄 grant 悄悄撤销一张仍在有效期内的宽 grant。被按-holder 上限拒绝的 lease 返回 `HolderInFlightLimitExceeded`（不会随其它 holder 排空而自行缓解）；被组上限拒绝的返回 `Backpressure`（会缓解）。

按-holder 计数**必须**持久化，**必须**与其伴随的 lease 在同一次原子写入中释放，**必须**通过扫描存活 lease 重建而不是信任客户端，并且**必须在 lease 准备之后**而非之前检查 —— 这样操作期间到期的 lease 会先被释放；对着陈旧计数做前置检查，会在一个已封顶 holder 的 lease 到期后把它**永久卡死**。

存活记录**禁止**在容量压力下被驱逐；broker 改为返回 `Backpressure`。

### 11. 持久化与 checkpoint

broker 按**批次**提交追加，**每条流一个批次**。当 `cbqs.commit_batch_max_ms` 到期且至少缓冲了一条记录，或缓冲了 `cbqs.commit_batch_max_records` 条记录时，该流的批次关闭，并由一次同步持久化写入提交它。只有在包含某条追加的批次提交之后，该追加才被确认，因此**批次既是持久化单位也是签名单位**。broker **可以**在一次物理写入中提交多条流的批次；但一个 checkpoint 所证明的批次永远只属于一条流。

**没有记录的批次不产生 checkpoint**：checkpoint 的区间字段只在至少有一条记录时才有定义。

每个已提交批次产生一个签名 checkpoint：

```text
CheckpointReceiptV2 {
  version:             u8,       // 2
  chain_instance_id:   Bytes32,
  stream_id:           Bytes32,
  provider:            Address,
  first_sequence:      u64,
  last_sequence:       u64,      // >= first_sequence
  records_digest:      Bytes32,
  previous_checkpoint: Bytes32,
  committed_at_ms:     u64,
  snapshot_height:     u64,
  signature:           Signature,
}

checkpoint_id = keccak256(checkpoint_signing_bytes_v2(receipt))
```

```text
record_digest(r) =
  keccak256("cbqs/record/v2" || canonical(RecordHeaderV2) || keccak256(payload))

records_digest =
  keccak256(
    "cbqs/records-digest/v2" ||
    record_count_u32_be ||
    record_digest(first) || ... || record_digest(last)
  )
```

批次内的 sequence 是连续的，因此 `record_count` 等于 `last_sequence - first_sequence + 1`，是**推导**出来的而不是携带的：携带一份副本就可能与它所伴随的区间不一致。摘要把这个计数与拼接内容一起承诺，因此两个不同批次不可能靠重新分组撞出同一个摘要。

`previous_checkpoint` 是该流紧邻前一个 checkpoint 的 `checkpoint_id`。流的第一个 checkpoint 使用

```text
checkpoint_genesis = keccak256("cbqs/checkpoint-genesis/v2" || chain_instance_id || stream_id)
```

于是 checkpoint 链是该流已提交历史上的一个总序，锚定在一个双方都能独立推导的值上。

**签名与密钥解析。** provider 对 `keccak256(checkpoint_signing_bytes_v2(receipt))` 签名。`snapshot_height` **必须**是 provider 确实读到过的 finalized 高度，沿一条流的 checkpoint 链**禁止**递减，且**必须**不早于该流的 `created_at_block`。验证方按如下方式解析签名密钥：当 `snapshot_height >= signing_key_since` 时取 provider 记录的 `signing_key`，否则**必须**拒绝该 receipt；因此 `signing_key_since`（§4.1）正是让一次轮换**撤销**旧密钥、而不只是「不再使用」它的机制。验证方还**必须**拒绝 `provider` 与流记录所点名的 `provider` 不一致的 receipt，这样已注册的 provider 就无法为它并不服务的流签发 checkpoint。

一个批次的原子持久化提交集合是：记录字节、已分配的 sequence、这些记录的去重条目、checkpoint receipt、以及 checkpoint 链尾。恢复时**必须**把未完成的事务作为一个整体重放或回滚。broker **禁止**确认一次追加、暴露一个 sequence、或服务一条其批次尚未提交的记录。

对组与投递的变更，原子提交集合是：投递或组状态、lease 状态、以及按-holder 的在途计数。

**一个 checkpoint 能证明什么、不能证明什么。** 持有某区间全部记录的订阅者可以重算 `records_digest` 并与签名值比对；不匹配、`previous_checkpoint` 链接断裂、或同一区间出现两个不同 checkpoint，都是 provider 不当行为的**签名证据**。有三条限制是明说而非暗示的：

- 只持有流中部分 lane 的订阅者**无法**验证 checkpoint，因为摘要在整个批次上是扁平的 —— 按 lane 的验证被推迟，今天需要它的应用改用「一条流一个验证域」；
- **没有任何共识状态锚定任何 checkpoint 链。** 一个向两个订阅者提供两条分歧链的 provider，只有在同时持有两个分支的一方那里才可能被发现；而且 `checkpoint_genesis` 是可公开推导的，因此仅凭 receipt 本身，一条被重启的链与一条新流的首个 checkpoint 无法区分。需要这一点的客户端**应当**把自己最新的 `checkpoint_id` 保存在 provider 之外，并在重连时比对；以及
- 不导出任何可用性保证。v2 没有争议或罚没路径，provider 停止服务时的补救是应用自己的持久副本。

### 12. 传输与流控

#### 12.1 帧

传输是承载二进制帧的双向 TLS WebSocket。一个 WebSocket 消息恰好含一个规范帧：`version: u8 = 2`、一字节帧标签、然后是规范 body。大于 `cbqs.max_wire_frame_bytes` 的帧**必须**在分配内存之前被拒绝；帧内每个变长字段**必须在解码时**就按其 §16 上界封顶 —— 尤其是 grant 的 `Set` 型 lane scope 按 `cbqs.max_lane_ids_per_grant` —— 而不是只在验证时才封顶，这样未认证的对端就无法让 broker 在这些界之外分配内存或做验签。

```text
CbqsClientFrameV2 =
  1 OpenSession     { request_id: Bytes32, grant: StreamGrantV2 } |
  2 CompleteSession { request_id: Bytes32, proof: SessionProofV2 } |
  3 Request         { request_id: Bytes32, session_id: Bytes32, body: CbqsRequestBodyV2 }

CbqsServerFrameV2 =
  1 SessionChallenge { request_id, session_id, challenge, expires_at_ms } |
  2 SessionOpened    { request_id, session_id, snapshot_height } |
  3 Response         { request_id, body: CbqsResponseBodyV2 } |
  4 Delivery         { session_id, subscription_id, lease, header, sequence, payload } |
  5 Checkpoint       { session_id, receipt: CheckpointReceiptV2 } |
  6 Error            { request_id: Option<Bytes32>, code: u16, message: Bytes, details: Bytes } |
  7 DeliveryState    { session_id, subscription_id, group_id, sequence, state }
```

`Request.session_id` 正是把一个请求绑定到「已证明持有权的那份权威」的东西：§7 要求 broker 用恰好该会话的 grant 执行请求，并拒绝 body 点名其它流的请求。`request_id` 是服务端回显的不透明关联 id。`message` 与 `details` 各自**必须**不超过 `cbqs.max_error_message_bytes`；除非 §15 为某个错误码定义了 payload，否则 `details` 为空。

一个连接**必须**在其首帧之后的 `cbqs.session_handshake_timeout_ms` 内完成会话建立，否则被关闭；并且**必须**至多持有 `cbqs.max_sessions_per_connection` 个开启的会话与 `cbqs.max_subscriptions_per_connection` 个开启的订阅，后者超限返回 `SubscriptionLimitExceeded`。

`CbqsRequestBodyV2` 是一个带标签联合，标签即下表的方法标签，body 即所列结构：

| Tag | 方法 | Body | 所需 verb |
| --: | --- | --- | --- |
| 1 | `Append` | `AppendRequestV2`（§9） | `APPEND` |
| 2 | `CreateLane` | `{ lane_nonce: Bytes32, metadata_hash: Bytes32 }` | `LANE_ADMIN` |
| 3 | `CloseLane` | `{ lane_id: Bytes32 }` | `LANE_ADMIN` |
| 4 | `ListLanes` | `{ after_lane_id: Option<Bytes32>, limit: u32 }` | `CONSUME`、`REPLAY` 或 `LANE_ADMIN` |
| 5 | `CreateGroup` | `GroupConfigV2`（§10.2） | `GROUP_ADMIN` |
| 6 | `UpdateGroup` | `GroupConfigV2` | `GROUP_ADMIN` |
| 7 | `DeleteGroup` | `{ lane_id: Bytes32, group_id: Bytes32 }` | `GROUP_ADMIN` |
| 8 | `OpenSubscription` | `{ subscription_id: Bytes32, lane_scope, start }` | `CONSUME` 或 `REPLAY` |
| 9 | `CloseSubscription` | `{ subscription_id: Bytes32 }` | — |
| 10 | `Credit` | `{ subscription_id: Bytes32, bytes: u64 }` | — |
| 11 | `Ack` | `{ lease: Bytes32 }` | `ACKNOWLEDGE` |
| 12 | `Nack` | `{ lease: Bytes32, delay_ms: u64 }` | `ACKNOWLEDGE` |
| 13 | `Extend` | `{ lease: Bytes32, extend_ms: u64 }` | `ACKNOWLEDGE` |
| 14 | `Reject` | `{ lease: Bytes32 }` | `ACKNOWLEDGE` |
| 15 | `Redrive` | `{ lane_id: Bytes32, group_id: Bytes32, limit: u32 }` | `REDRIVE` |
| 16 | `SetStreamSettings` | `StreamSettingsV2`（§14） | `STREAM_ADMIN` |
| 17 | `GetStreamSettings` | `{}` | 任意 |

未知方法标签无效。**没有任何请求 body 携带 `stream_id`：由会话决定它。**

#### 12.2 credit

一个订阅持有以「编码后帧字节数」计的 credit 余额。broker **禁止**发送编码后超出剩余 credit 的投递帧，并**必须**按它实际发送的编码字节长度精确扣减。`Credit` 增加该余额。

当一个订阅的 credit 已经**足以容纳下一条待投递帧**、且在 `cbqs.slow_consumer_timeout_ms` 内什么也没接收时，它才是**慢消费者**，此时**必须**以 `SlowConsumer` 关闭。该条件是按「credit 足以覆盖队首帧」而不是按「credit 存在」来陈述的：credit 只是小于下一帧的客户端其实**正在遵守**上面那条规则，把它关掉等于惩罚做对事的一方。当某订阅的 credit 低于队首帧大小时，broker **必须**在一个 `DeliveryState` 帧中报告该大小，好让客户端知道该补多少。

一个连接上跨订阅的调度**必须**有饥饿上界：一个既有足够 credit 又有待投递记录的订阅，**必须**在 `cbqs.max_subscriptions_per_connection` 个调度轮次内被服务到 —— 这让该要求**可测**，而不只是「有限」。

#### 12.3 重放

`OpenSubscription` 点名一个 lane scope 与一个起始位置：`Head = 1`、`At = 2 (sequence: u64)`、或 `Checkpoint = 3 (checkpoint_id: Bytes32)`。起点落在保留地板之下返回 `CursorTooOld`（§13）。`Checkpoint` 起点若点名的 id 不是该流的 checkpoint，返回 `CheckpointNotFound`；broker **必须**用有界索引查找来解析它，而不是扫描历史。一次重放**必须**把每个响应所物化的字节量限制在 `cbqs.max_wire_frame_bytes` 之内，并**必须**在每条 lane 内按 sequence 升序投递。

#### 12.4 拨号策略

客户端**禁止**连接到解析结果为 loopback、unspecified、link-local、unique-local、multicast，或落在私有/特殊用途范围内的端点。具体而言，它**必须**拒绝解析出的任何落在以下范围的 IPv4 地址：`0.0.0.0/8`、`10.0.0.0/8`、`100.64.0.0/10`、`127.0.0.0/8`、`169.254.0.0/16`、`172.16.0.0/12`、`192.0.0.0/24`、`192.0.2.0/24`、`192.88.99.0/24`、`192.168.0.0/16`、`198.18.0.0/15`、`198.51.100.0/24`、`203.0.113.0/24`、`224.0.0.0/3`；以及任何落在全球单播 `2000::/3` 之外，或落在 `2001::/23`、`2001:db8::/32`、`2002::/16`、`3ffe::/16`、`3fff::/20` 之内的 IPv6 地址。

它**必须**对它解析出的**每一个**地址施加该检查，**必须**只连接到它检查过的那个地址 —— 解析一次并连接到该结果，**绝不**在检查与连接之间重新解析 —— 并**必须**在每次重定向后重新施加。该检查是**客户端**的义务，因为只有客户端知道一个名字解析成了什么；共识准入（§4.1）做不到，也不试图去做。§20 第 7 项让它可以按上面这份地址清单来测试，而不是按散文来测试。

### 13. 保留

broker 为每条流保留一个有界的热窗口，由有效的 `retention_ms` 与 `retained_bytes_limit` 设置（§14）约束。保留地板只推过「对每个组都已终态」或「已过该组 `record_deadline_ms`」的记录。

在地板之下，broker 返回 `CursorTooOld`，其 `details` 以大端 `u64` 携带当前的 `first_retained_sequence`。客户端从该 sequence 或其之后重新进入。**该地板按流单调，永不回退。**

`Closed` 或 `Suspended` 的流的数据保留由 provider 自行决定；provider **应当**在其注册的 metadata 中声明其策略。这不是共识状态。

### 14. broker 侧的流设置

```text
StreamSettingsV2 {
  version:                     u8,      // 2
  retention_ms:                u64,
  retained_bytes_limit:        u64,
  max_message_bytes:           u32,
  max_append_bytes_per_sec:    u64,
  max_delivered_bytes_per_sec: u64,
  default_visibility_ms:       u64,
  default_max_visibility_ms:   u64,
  default_max_attempts:        u16,
  default_max_in_flight:       u32,
  default_record_deadline_ms:  u64,
  default_dead_letter_ttl_ms:  u64,
}
```

持有 `STREAM_ADMIN` 的一方通过 `SetStreamSettings` 设置它们。每次变更时，每个字段都按下表点名的上限校验 —— 这里**逐项列举而不是给一条通则**，因为这些上限的命名并不遵循同一套约定 —— 没有显式设置的流使用这些参数的默认值。每个字段都**必须**非零。

| 设置 | 上限 |
| --- | --- |
| `retention_ms` | `cbqs.retention_ms` |
| `retained_bytes_limit` | `cbqs.max_retained_bytes_per_stream` |
| `max_message_bytes` | `cbqs.max_message_bytes` |
| `max_append_bytes_per_sec` | `cbqs.max_append_bytes_per_sec` |
| `max_delivered_bytes_per_sec` | `cbqs.max_delivered_bytes_per_sec` |
| `default_visibility_ms` | 同一记录的 `default_max_visibility_ms` |
| `default_max_visibility_ms` | `cbqs.visibility_ms` |
| `default_max_attempts` | `cbqs.max_attempts` |
| `default_max_in_flight` | `cbqs.max_in_flight_per_group` |
| `default_record_deadline_ms` | `cbqs.retention_ms` |
| `default_dead_letter_ttl_ms` | `cbqs.retention_ms` |

`GroupConfigV2` 中缺席的字段，取组**创建时**生效的同名 `default_*` 设置，并把解析后的值**存入组内**：之后的设置变更不会悄悄重定义一个已存在的组。

设置属于 broker 状态：不需要链上交易、不改变该流的费率；provider **可以**通过返回 `SettingsRejected` 拒绝它不愿服务的设置。

provider **必须**执行已接受的设置。`max_append_bytes_per_sec` 与 `max_delivered_bytes_per_sec` 以返回 `RateLimited` 的限流方式执行，**不是**静默丢弃。

**调低某项设置不等于追溯删除。** 调低 `retention_ms` 或 `retained_bytes_limit` 改变的是自此之后 broker 驱逐什么；它**禁止**把数据裁剪到已向客户端公布的地板之下，且 §13 的地板保持单调。这一点重要，是因为 `STREAM_ADMIN` 是唯一一个「效果比其 grant 活得更久」的 verb，安全性考量里对此直说。

### 15. 类型化错误

所有绑定都暴露稳定的类型化错误。凡条件在 v2 中仍存在的，错误码**沿用 document version 1 的数值**，这样升级中的实现不必重新映射它已经处理过的东西。**被退休的码禁止被赋予新的含义。**

| Code | Name | 何时返回 |
| ---: | --- | --- |
| 3901 | `StreamNotActive` | 快照中流状态为 `Closed` |
| 3902 | `StreamSuspended` | 状态为 `Suspended`，或 §6 可用性检查未通过 |
| 3904 | `AuthorizationGenerationStale` | grant 的代次不是快照中的代次 |
| 3906 | `InvalidGrant` | 签名、上下文、scope 或界检查失败 |
| 3907 | `GrantExpired` | 在 grant 的时间窗之外 |
| 3908 | `VerbDenied` | grant 缺少该方法所需的 verb |
| 3909 | `GroupScopeDenied` | 该组在 grant 的 group scope 之外 |
| 3910 | `InvalidProofOfPossession` | 会话 proof 未通过任一 §7 检查 |
| 3912 | `MessageTooLarge` | payload 超过有效 `max_message_bytes` |
| 3913 | `RateLimited` | 超出 §14 的限流；退避后重试 |
| 3914 | `Backpressure` | credit 或组容量耗尽；退避后重试 |
| 3915 | `IdempotencyConflict` | 同一键以不同规范字节复用 |
| 3916 | `IdempotencyExpired` | 超过幂等时窗后的重试 |
| 3917 | `CursorTooOld` | 起点在保留地板之下；`details` = 地板值，u64 大端 |
| 3918 | `GroupNotFound` | 无此 `(stream_id, lane_id, group_id)` |
| 3919 | `LeaseStale` | lease 未知、已被取代、或属于另一个 holder |
| 3920 | `DeliveryTerminal` | 该周期已到达终态 |
| 3925 | `ChainStateStale` | `OpenSession` 所依据的快照旧于 `cbqs.max_snapshot_age_blocks` |
| 3926 | `LaneNotFound` | 无此 lane |
| 3927 | `LaneClosed` | 向已关闭 lane 追加 |
| 3928 | `LaneScopeDenied` | 该 lane 在 grant 的 lane scope 之外 |
| 3929 | `LaneLimitExceeded` | 活跃 lane 或墓碑数达到上界 |
| 3932 | `SubscriptionLimitExceeded` | 达到每连接订阅数上界 |
| 3937 | `UnsupportedVersion` | 版本字节不是 `2` |
| 3938 | `ChainInstanceMismatch` | 对象的 `chain_instance_id` 不是 broker 的 |
| 3939 | `GroupConfigInvalid` | 违反 §10.2 的组配置规则；`details` 点名字段 |
| 3940 | `HolderInFlightLimitExceeded` | 触及 grant 的按-holder 在途上界 |
| 3948 | `SlowConsumer` | §12.2 的慢消费者条件 |
| 3949 | `SettingsRejected` | provider 不愿服务这组 §14 设置 |
| 3950 | `StreamUnknownToBroker` | 该流不在 broker 的快照中 |
| 3951 | `CheckpointNotFound` | `Checkpoint` 起点点名了未知的 `checkpoint_id` |

`StreamNotFound`（3900）已**退休**：v2 中 broker 是从快照判定的，因此「注册表没有这条流」与「这条流不在我的快照里」是同一个观测，而 `StreamUnknownToBroker`（3950）在陈述它时不会暗示 broker 在请求时读过链。两者都保留会让两个码对应同一个条件。

以下码随其所报告的面一起退休（§19）：3900、3903、3905、3911、3921、3923、3924、3930、3933、3934、3935、3936、3941、3942、3943、3944、3945、3946、3947。

客户端**必须**把未知的未来错误原样保留为 `(code, message, details)`，而不是映射成成功或重试。

### 16. 参数与边界

所有解码期的集合长度与字节长度，**必须**在分配内存之前封顶。

两列限定每一行。**Read by（读者）**说明谁读它：`C` 共识处理器、`B` broker（经其快照）、`G` 仅治理提案侧的守卫。**Class（类别）**说明一次变更**何时**到达一个对象，这一列正是让治理写入保持前瞻的关键：

- **Admission（准入）** —— 在请求或指令被准入时读取；被接受的对象此后不再查阅它。调低它会阻止新工作，而不会重新审视任何已被接受的东西。
- **Ceiling（上限）** —— 在某个值被设置的那一刻约束它（§14 设置、§10.2 组配置）。被接受的记录存下自己解析后的值，因此之后的写入不会悄悄重定义既有的流或组。
- **Runtime（运行时）** —— 由 broker 持续读取；变更随携带它的那份快照生效。只有运营类限制放在这里。
- **Codec（编解码）** —— 一个解码界。它的 Maximum 等于 Default：它本质是协议常量，写成参数行只是为了让解码路径有一个统一的读取处，治理无法移动它。

对 `cbqs.*` 各行的 CIP-12 变更都属于 Tier 0（参数调优），但 `Codec` 类别的行**根本不可由治理写入**。

| 参数 | 默认值 | 最大值 | Read by | Class |
| --- | --- | --- | --- | --- |
| `cbqs.stream_rate_per_block` | 80,000 | 10,000,000 | C | Admission |
| `cbqs.max_streams_per_owner` | 1,024 | 16,384 | C | Admission |
| `cbqs.max_provider_endpoints` | 4 | 8 | C | Admission |
| `cbqs.max_provider_endpoint_uri_bytes` | 2,048 | 2,048 | C | Codec |
| `cbqs.rent.provider_bps` | 9,000 | 10,000 | C | Runtime |
| `cbqs.rent.platform_bps` | 1,000 | 10,000 | G | Runtime |
| `cbqs.settlement_interval_blocks` | 604,800 | 2,592,000 | B | Runtime |
| `cbqs.snapshot_refresh_ms` | 2,000 | 60,000 | B | Runtime |
| `cbqs.max_snapshot_age_blocks` | 300 | 3,000 | B | Runtime |
| `cbqs.max_clock_skew_ms` | 60,000 | 300,000 | B | Admission |
| `cbqs.max_grant_ttl_ms` | 86,400,000 | 604,800,000 | B | Admission |
| `cbqs.session_handshake_timeout_ms` | 10,000 | 60,000 | B | Runtime |
| `cbqs.max_sessions_per_connection` | 64 | 1,024 | B | Runtime |
| `cbqs.max_message_bytes` | 262,144 | 1,048,576 | B | Ceiling |
| `cbqs.max_retained_bytes_per_stream` | 1,073,741,824 | 1,099,511,627,776 | B | Ceiling |
| `cbqs.max_append_bytes_per_sec` | 1,048,576 | 1,073,741,824 | B | Ceiling |
| `cbqs.max_delivered_bytes_per_sec` | 4,194,304 | 4,294,967,296 | B | Ceiling |
| `cbqs.retention_ms` | 604,800,000 | 2,592,000,000 | B | Ceiling |
| `cbqs.visibility_ms` | 30,000 | 900,000 | B | Ceiling |
| `cbqs.max_attempts` | 10 | 100 | B | Ceiling |
| `cbqs.max_in_flight_per_group` | 4,096 | 65,536 | B | Ceiling |
| `cbqs.idempotency_horizon_ms` | 86,400,000 | 604,800,000 | B | Ceiling |
| `cbqs.max_groups_per_stream` | 4,096 | 65,536 | B | Admission |
| `cbqs.max_group_tombstones_per_stream` | 16,384 | 262,144 | B | Admission |
| `cbqs.max_lanes_per_stream` | 16,384 | 65,536 | B | Admission |
| `cbqs.max_lane_tombstones_per_stream` | 65,536 | 1,048,576 | B | Admission |
| `cbqs.max_lane_ids_per_grant` | 4,096 | 16,384 | B | Codec |
| `cbqs.max_lane_list_page` | 256 | 1,024 | B | Admission |
| `cbqs.max_subscriptions_per_connection` | 256 | 4,096 | B | Runtime |
| `cbqs.max_wire_frame_bytes` | 5,242,880 | 5,242,880 | B | Codec |
| `cbqs.max_error_message_bytes` | 2,048 | 2,048 | B | Codec |
| `cbqs.slow_consumer_timeout_ms` | 60,000 | 900,000 | B | Runtime |
| `cbqs.commit_batch_max_ms` | 20 | 1,000 | B | Runtime |
| `cbqs.commit_batch_max_records` | 1,024 | 65,536 | B | Runtime |

`cbqs.stream_rate_per_block` 在任何治理写入之后与在 genesis 都**必须**非零：§4.2 把它复制进每条流记录，而 §6.2 会对该副本做除法。

有两个协议常量**刻意不做成参数**，因为把任一个由治理写成零，都会让永久状态定价为零：

```text
CBQS_STREAM_CREATION_CHARGE = 5_000_000_000    // nano-CBY (§6.3)
```

以及 §16.1 的计量常量。重新调整任一个都属于协调发布的协议变更。

#### 16.1 状态 I/O 预留与计量成本

每条指令在其第一次状态操作之前，恰好预留下表这么多次读与写。这些数对是**协议常量**：不随流的形态、余额或任何被观测状态变化，改动其中之一属于共识变更，需要新的文档版本。在被钉住的路径上，实际次数等于预留次数。

| 指令 | 预留读 | 预留写 |
| --- | ---: | ---: |
| `RegisterProvider` | 4 | 1 |
| `UpdateProvider` | 4 | 1 |
| `CreateStream` | 9 | 5 |
| `UpdateStream` | 2 | 1 |
| `CloseStream` | 9 | 6 |
| `TopUpAccount` | 4 | 3 |
| `SettleStream` | 8 | 5 |
| `WithdrawAccount` | 4 | 3 |

每个处理器都会读取 Stream Registry 单例。除此之外，各行恰好是：

| 指令 | 单例之外的读 | 写 |
| --- | --- | --- |
| `RegisterProvider`、`UpdateProvider` | `cbqs.max_provider_endpoints`、`cbqs.max_provider_endpoint_uri_bytes`、provider 记录 | provider 记录 |
| `CreateStream` | 暂停记账记录、`cbqs.max_streams_per_owner`、`cbqs.stream_rate_per_block`、provider 记录、账户记录、流槽位、owner 的原生账户、零地址 | 流记录、账户记录、provider 记录、owner 的原生账户、零地址 |
| `UpdateStream` | 流记录 | 流记录 |
| `CloseStream` | 暂停记账记录、`cbqs.rent.provider_bps`、流记录、账户记录、custody 账户、provider 的原生账户、Platform Fee Account、provider 记录 | 流记录、账户记录、custody 账户、provider 的原生账户、Platform Fee Account、provider 记录 |
| `SettleStream` | 暂停记账记录、`cbqs.rent.provider_bps`、流记录、账户记录、custody 账户、provider 的原生账户、Platform Fee Account | 流记录、账户记录、custody 账户、provider 的原生账户、Platform Fee Account |
| `TopUpAccount`、`WithdrawAccount` | 账户记录、custody 账户、对手方的原生账户 | 同样这三项 |

`CreateStream` 读取暂停记账记录，是因为 §4.2 要求它存储一个有效租金高度；它**不**读 `cbqs.rent.provider_bps`，因为它不做结算。`CloseStream` 与 `SettleStream` **不**读 `cbqs.stream_rate_per_block`：§6.2 使用流记录中快照的费率。**不存在第三条结算指令。**

处理器**必须**无条件执行其贷记写入（金额为零时也一样），并且 **`settle` 的两个分支 —— 全额支付与部分支付，以及 suspended 的空操作 —— 执行相同的读与写。** 一个跳过零值写入、或在某个分支走了更省路径的处理器，其计量与不这么做的实现不同，二者会在同一个区块里对 gas 产生分歧。这是**要求**，不是观察：下面两个 `SettleStream` 向量在每个计量字段上逐字节相同，**正是因为**这些分支必须相同；partial 分支计量不同的实现即为不符合规格。

每条指令的精确计量成本被钉成一份规范性产物，与本文并列存放于 `cip-39-gas-vectors-v2.json`（schema `cowboy.cbqs.gas-vectors.v2`）：十个向量覆盖全部八条指令、genesis 默认四端点下的最大尺寸 `RegisterProvider` payload、以及 `SettleStream` 的部分支付分支。每个向量记录 payload 字节数、预留计数、实际与被计费的读写计数、hash 原像长度、签名数，以及精确的 cycles 与 cells。符合规格的实现**必须**精确复现每一个向量，并以该产物为准；其 SHA-256 见英文原文 §16.1（本译本不重复该摘要值，以免两处漂移 —— 请从英文原文与产物本身读取）。

每个向量在 §19 规则 1 所强制的 genesis 参数集下都是可达的；没有一个需要事先的治理写入。

该产物的 `constants` 块复现的是**平台已实现的计量表**（包括按状态写入的固定 Cell 计费），而不是重述 CIP-3 §2.2.2 的按字节 `state_set` 模型（后者描述的是 PVM 宿主计量）。CIP-39 不重定义两者中的任何一个；二者不一致时，调和它们是 CIP-3 的事，不在本文范围内。

这些向量的作用域是 CBQS 分发：每个向量覆盖本文定义的解码附加费，加上其处理器的 hash、签名与状态 I/O 工作；**不含**交易基础费、内在 calldata cells、外层系统指令分发、以及事件发射（§17）—— 这些都是平台在本族之外统一收取的。hash 计费为 `max(1, ceil(len / 32))` 个字。拒绝路径不被钉住；被拒绝的指令不持久化任何东西，也不发射事件。

### 17. 链上事件

事件是共识数据：发射者、topic、payload 字节与顺序都经 `logs_root` 提交进 `receipt_root`，因此下面每个字段都是规范的。topic 是所示的精确 UTF-8 字节串；payload 恰好是所列的那一个定长标识符 —— 没有编码信封，也没有额外字段。事件背后的注册表细节从事件所在区块的 `0x17` 状态读取，而不是复制进日志。

| 指令 | Topic | Payload |
| --- | --- | --- |
| `RegisterProvider` | `cbqs.provider.registered` | 20 字节 provider 地址 |
| `UpdateProvider` | `cbqs.provider.updated` | 20 字节 provider 地址 |
| `CreateStream` | `cbqs.stream.created` | 32 字节 `stream_id` |
| `UpdateStream` | `cbqs.stream.updated` | 32 字节 `stream_id` |
| `SettleStream` | `cbqs.stream.settled` | 32 字节 `stream_id` |
| `CloseStream` | `cbqs.stream.closed` | 32 字节 `stream_id` |
| `TopUpAccount` | `cbqs.account.credited` | 20 字节 owner 地址 |
| `WithdrawAccount` | `cbqs.account.debited` | 20 字节 owner 地址 |

**每条成功的指令恰好发射一个事件 —— 它所在行的那个 —— 被拒绝的指令一个都不发射。**

v2 发布的是**电平（level），不是边沿（edge）**，并且直说其后果，而不是声称电平等价于边沿。需要知道「某一次结算究竟是暂停了还是恢复了某条流」的消费者，**无法**从日志中读出来：它要比对 `cbqs.stream.settled` 事件前后两个区块的 `StreamRecordV2.status`；而同一区块内对同一条流的两次结算，其中间状态是不可观测的。事件同样不携带金额，因此 provider 收入、平台累计与创建销毁都要从余额差额而非日志重建。两者都是「每指令一事件」规则的代价；如果索引方需要，边沿与金额事件集可以由后续 CIP 提供。

### 18. 运营面

`cbqsd` 暴露 `/statusz`（CIP-42 自述，能应答本身就是存活信号）、`/readyz`，以及 Prometheus 文本格式的 `/metrics`。

`/readyz` **只**报告数据平面就绪度：当存储不可写、提交回路在有记录等待时停止推进、或某个后台回路停止心跳时返回 503。**注册表快照刷新失败禁止让 broker 变成 unready。** §3 要求 broker 在链中断期间继续服务，而一个因链可达性失败的就绪探针，会让负载均衡器恰好摘掉那些仍有能力服务的 broker。该状况改为以 `/statusz` 的 degraded 标志、以及一个携带当前快照年龄的 `/metrics` gauge 报告，这样运维能看见它，而数据平面不被撤出。

### 19. 激活与被移除的面

**document version 2 整体取代 version 1。** CBQS 从未在任何「状态必须被保留」的网络上激活过，而 version 1 本身就把自己规定为 reset-only 且 pre-launch。因此激活是**重置，不是迁移**：

1. genesis **必须**播种 Stream Registry 单例与每个 §16 参数的默认值，**必须**校验 `cbqs.rent.provider_bps + cbqs.rent.platform_bps == 10000` 且 `cbqs.stream_rate_per_block` 非零，并**禁止**播种 base-rate schedule 记录；version-1 的 schedule 键**必须**不出现在 genesis 状态中；
2. genesis 校验**必须**拒绝含有下面「被退休的键」清单中任一 version-1 键的参数集；
3. 处理器**必须**拒绝版本字节不是 `2` 的 `SYS_CBQS` payload；
4. 解码器**必须**拒绝版本字节不是 `2` 的任何已存储 CBQS 记录 —— §4 给每条已存储记录（链上侧与 broker 侧）都加了该字节，**正是为了让这条规则有作用对象**；以及
5. broker 存储**必须**携带在创建时写入的存储格式标记 `cbqs/store-format = 2`，且 version-2 的 `cbqsd` **必须**拒绝打开标记缺失或不为 `2` 的存储，而不是尝试部分解码。

运营方**禁止**把 version-1 的链上状态、broker 存储或归档快照包跨过这条边界带过来。

**被退休的治理键。** genesis 校验拒绝以下任一：`cbqs.base_rate.standard.retained_unit_bytes`、`cbqs.base_rate.standard.retained_unit_rate_per_block`、`cbqs.base_rate.standard.throughput_unit_bytes_per_sec`、`cbqs.base_rate.standard.throughput_unit_rate_per_block`、`cbqs.base_rate.standard.delivered_unit_bytes_per_sec`、`cbqs.base_rate.standard.delivered_unit_rate_per_block`、`cbqs.base_rate.fast.retained_unit_bytes`、`cbqs.base_rate.fast.retained_unit_rate_per_block`、`cbqs.base_rate.fast.throughput_unit_bytes_per_sec`、`cbqs.base_rate.fast.throughput_unit_rate_per_block`、`cbqs.base_rate.fast.delivered_unit_bytes_per_sec`、`cbqs.base_rate.fast.delivered_unit_rate_per_block`、`cbqs.max_inline_message_bytes`、`cbqs.max_key_envelopes_per_batch`、`cbqs.max_key_envelopes_per_chunk`、`cbqs.max_key_batch_chunk_bytes`、`cbqs.max_proof_lanes_per_subscription`、`cbqs.max_server_frames_per_batch`、`cbqs.max_error_details_bytes`、`cbqs.max_lane_creates_per_min`、`cbqs.max_chain_staleness_blocks`、`cbqs.suspend_grace_blocks`、`cbqs.standard.retention_ms`、`cbqs.standard.idempotency_horizon_ms`、`cbqs.standard.visibility_ms`、`cbqs.standard.max_attempts`、`cbqs.fast.retention_ms`、`cbqs.fast.batch_max_ms`、`cbqs.fast.batch_max_records`（共 29 个）。这份清单**逐一写出而不是用通配符**，好让一个 genesis 校验器仅凭本文就能构建出来。

**被移除的面。** 下表每一行点名 version 1 定义了什么、以及被什么取代。升级到 version 2 的实现，删掉左列。

| Version-1 的面 | 在 version 2 中的处置 |
| --- | --- |
| v1 §4.1 `PricingBasisV1`、`pricing_generation`、`escrow_balance`、`suspended_at_block`、`suspension_grace_deadline_block`、`provider_epoch`、`encryption_generation`、`linked_stream_id`、`purpose`、`delivery_class`、`encrypted`、按流固定的 `provider_signing_key` | 移除。计费按账户、按快照的固定费率（§6）；只有一种投递类别；没有平台加密；没有 key stream。provider 密钥改由 `signing_key_since` 解析（§4.1、§11）。 |
| v1 §4.1 `DataExpired` 状态 | 移除。共识观察不到数据是否还在；保留由 provider 决定（§13），而它原先提供的退出路径由 §5 的 provider 侧 `CloseStream` 接手。 |
| v1 §4.2 `StreamConfigV1`、其 LIVE/IMMUTABLE 校验表、以及 `max_message_bytes × fast_batch_max_records` 交叉字段规则 | 从链上移除。等价旋钮成为 broker 设置（§14），由 §16 上限约束。 |
| v1 §4.3 `BaseRateAdmissionV1`、`BaseRateReservationTotalsV1`、跨两种定价基准的 `live_assigned_streams`、`ProviderStatusV1::Draining` | 由 `accepts_new`、`max_streams`、单个 `assigned_streams` 计数器与二值状态取代（§4.1）。 |
| v1 §4.3 五条端点准入规则（WHATWG 解析、raw authority 扫描、IPv4/IPv6 段清单）及其 30 条 URI 向量 | 由 §4.1 的四条字节级规则与九条向量取代；地址策略移到 §12.4 并写出具体网段，由 §20 第 7 项检验。 |
| v1 §4.4 `PriceQuoteV1` 与报价校验 | 移除。一个价格，不做按流协商。 |
| v1 §4.5 `BaseRateScheduleV1`、`BaseRateSchedulesV1`、`active_at(H)`、十二行 `cbqs.base_rate.*`、schedule 摘要 | 移除。改为单个 `cbqs.stream_rate_per_block`，按流快照（§4.2）。 |
| v1 §5 `SetProviderStatus`、`TopUpStream`、`SettleStreamRent`、`ActivateKeyGeneration` | 移除或替换：状态并入 `UpdateProvider`；充值与结算移到账户层；密钥激活没有链上步骤。 |
| v1 §6 宽限期、`CBQS_CREATION_CHARGE_BLOCKS`、`CBQS_MIN_RATE_PER_BLOCK`、`TopUpStream` 的双次结算及其拒绝顺序 | 移除。`settle`（§6.2）是唯一的状态转移；固定的 `CBQS_STREAM_CREATION_CHARGE` 为注册表状态定价。 |
| v1 §6 `0x17` 的暂停分类、其 `"system:gov:pause-accounting:"` 记录、以及 `coverage(H)` / `effective_rent_height(H)` | **保留**，在 §6.1 重述。这是 version 2 仍然读取的、唯一一处 version-1 机制。 |
| v1 §7 grant 上的 `holder_hpke_key`；v1 的 verb 位编号 | HPKE 密钥随平台加密一起移除。位 0–6 不变；`STREAM_ADMIN` 是位 7 上的新增（§7）。 |
| v1 §7.1 `RequestProofV1` 逐请求签名与请求 body 哈希注册表 | 由会话权威 + 每个请求帧上的 `session_id` 取代（§7、§12.1）。 |
| v1 §7 `cbqs.max_chain_staleness_blocks` fail-closed 规则 | 由 `cbqs.max_snapshot_age_blocks` 取代，且只闸新会话（§3）；已建立的会话在中断期间继续。 |
| v1 §9 平台加密：记录加密、HPKE 信封、`stream_root` CBSS 托管、轮换 actor、`KeyRotationBatchV1`、`KeyBatchReceiptV1`、分块上传、key stream | 移除。payload 不透明；应用自行加密与分发密钥。 |
| v1 §10 `RecordOriginV1`、`RecordKindV1`、`LaneEventV1` provider 事件、`visible_after_ms`、`nonce`、记录头中的 `encryption_generation` | 移除。lane 拓扑通过 `ListLanes` 发现（§8）；`visible_after_ms` 在 v1 中被要求恒为零，本就没有行为。 |
| v1 §11.2 `GroupConfigV1.retention_pin_until_ms`、按组的 `max_visibility_ms` | pin 由被 `cbqs.retention_ms` 封顶的 `record_deadline_ms` 取代（§10.2），那正是保留地板保持活性的机制；`max_visibility_ms` 作为组字段保留。 |
| v1 §12 `fast` 投递类别：暂定确认、`broker_epoch`、`FastLineageV1`、`BrokerEpochTransitionV1`、水位线、lineage 采纳 | 推迟到后续 CIP。 |
| v1 §12.2 `merkle_root_v1`、`sparse_root_v1`、按 lane 分区的区间根、`LaneProofV1`、遗漏检测、验证型订阅的定序、`ScopedProofs`/`FullStream` | 与上面的类别一起推迟。§11 改签一个扁平的按批次摘要，并写明其代价。 |
| v1 §13.2 HTTPS 长轮询回退及其虚拟会话 | 移除。WebSocket 是 v2 唯一的绑定。 |
| v1 §14.1 按记录的 `AppendReceiptV1`、v1 §14.2 按动作的 `DeliveryStateReceiptV1` 与按组的回执链、全局与按 lane 的回执链及其 genesis 锚 | 由每个持久批次一个签名 checkpoint 取代（§11）。 |
| v1 §15 `StandardRetentionAnchorV1`、`GroupRetentionAnchorV1`、`FastRetentionAnchorV1`、`CbqsSnapshotManifestV1`、CBFS 归档 | 由 `CursorTooOld` 中一个朴素的 `first_retained_sequence` 取代（§13）。 |
| v1 §16 actor-bridge 投影规则、v1 §16.1 应用迁移 | 投影规则随平台加密移除；迁移的顺序义务保留在 §4.4。 |
| v1 §16.2 Homestead 应用边界 | 移除。应用指引不是协议要求。 |
| v1 §17 十四个对象的签名注册表 | 由 §4 的三对象注册表取代。 |
| v1 §18 四类参数划分 | 以紧凑形式保留：§16 的 Class 列。 |
| v1 §18 被退休的键 | 在上面的「被退休的键」清单中逐一点名。 |
| v1 §19 `cbqs.stream.topped_up`、`cbqs.stream.rent_settled`、`cbqs.stream.suspended`、`cbqs.stream.reactivated`、`cbqs.stream.key_generation_activated`、`cbqs.stream.data_expired`、`cbqs.provider.status_changed` 及净状态边沿规则 | 由 §17 的「每指令一事件」表取代，该表发布电平并直说这一点。 |
| `cip-39-gas-vectors-v1.json` | 由 `cip-39-gas-vectors-v2.json` 取代（§16.1）。 |

### 20. 符合性

一个实现在满足以下各项时符合本规格：

1. 它准入与拒绝的链上指令恰好是 §4–§6 所定义的，且具有 §6 定义的状态效果与 §17 定义的事件 —— 包括 §4.1 的九条端点向量，以及在有记录在案的暂停下 §6.1 的 `coverage`/`H` 表达式；
2. 它在 §19 规则 1 的 genesis 参数集下、且无任何事先治理写入的前提下，精确复现 `cip-39-gas-vectors-v2.json` 中的每个向量，并让 `settle` 两个分支的计量完全一致（§16.1）；
3. 它的规范编码能通过 `cowboy-protocol-codec::cbqs` 往返，对 §4 赋予版本字节的每个对象都拒绝非 `2` 的版本字节，并对 §4 注册表的三个条目产出逐字节一致的签名原像；
4. 它的 broker 按 §7 与 §12 的定义接受与拒绝会话及请求 —— 包括链中断模拟下已建立会话的持续服务（§3）、超过 `cbqs.max_snapshot_age_blocks` 后对 `OpenSession` 的拒绝、`session_id`/`challenge` 的一次性、对「`session_id` 未在该连接上开启」或「body 点名其它流」的请求的拒绝，以及在观察到代次递增的那次刷新之后、于其所服务的第一个请求上终止该会话（§7）；
5. 它拒绝任何非 lease 签发对象发起的 lease 操作，并按交集方式评估 lane 与 group scope（§7 第 6 项、§10.2）；
6. 它的 broker 在包含某条追加的批次持久化之前不确认该追加；每条被确认的记录都出现在某个 `records_digest` 可重算的 checkpoint 中；checkpoint 的 `snapshot_height` 沿链非递减；且由「在其 `snapshot_height` 之前即已退休的密钥」所签的 receipt 被拒绝（§11）；
7. 它的客户端在解析之后与每次重定向之后都拒绝 §12.4 清单中的每个地址，并且只连接到它检查过的那个地址；以及
8. 在持久写入边界两侧任一处注入崩溃后重启，留下的要么是「没有记录也没有确认」，要么是「记录、其 sequence、其去重条目与其 checkpoint 同时存在」（§11）。

---

## 安全性考量、设计取舍与被拒方案

英文原文的 **Security Considerations** 与 **Rationale** 两节篇幅较长且以论证为主。本译本给出其要点；**做实现或评审判断时请以英文原文为准**。

### 安全性考量要点

- **会话权威。** 会话内请求不逐条签名，每个请求携带其 `session_id` 并由 broker 绑定到该会话的 grant（§7）。能向已建立 TLS 会话注入的攻击者，就以该会话的权威行事，直到会话关闭。v1 的逐请求签名对同一个攻击者同样无效（它们绑定到 session id，同样的注入位置照样能重排与丢帧），代价却是每消息一次签名与一次验签。v1 的计数器真正提供的、且 §7 显式替代的，是**把请求绑定到其会话**：一次性的 `session_id`/`challenge` 对、握手截止时间、以及 broker 会检查的按请求 `session_id`。holder 密钥**应当**按工作负载限定，会话**应当**短，grant **应当**取实际可行的最短有效期。
- **撤销滞后。** 链上权威在下一次成功刷新时到达已建立的会话，链中断期间根本不到达。两道边界防止其无界化：`cbqs.max_snapshot_age_blocks` 阻止 broker（包括故意永不刷新的）基于陈旧状态准入**新**会话；`cbqs.max_grant_ttl_ms` 封顶任何在外 grant 的存活时间。把密钥从被泄露 holder 处轮换走的 owner **必须**假定：在链与 broker 被分区时，旧 grant 在已建立会话上一直可用到它自己过期。
- **`STREAM_ADMIN` 的效果比它的 grant 活得久。** 位 7 改的是 broker 状态而非会话状态：调低 `retention_ms` 或 `retained_bytes_limit` 的持有者改变了此后该流保留什么，撤销该 grant 也无法恢复其后被驱逐的数据。§14 禁止裁剪到已公布地板之下，把损害限制在未来的驱逐上，但它仍是本文中唯一一个撤销后效果仍存续的能力。owner **应当**窄发它，且**不应**把它放进签给消费者的 grant。
- **计费敞口。** 租金在链上累积、由无许可结算收取，因此从不结算的 provider 把未付余量当作信用风险自担。在共享的按-owner 余额下，该余量**并不**由 owner 的余额封顶：另一个 provider 处的兄弟流可能先把余额抽干，而没有哪个 provider 看得见兄弟的债权。每个 provider 真正能约束的是它自上次结算以来提供的服务量 —— 这正是 §6.4 给出节奏、以及 broker 的可用性检查要乘上 `active_streams` 而不是拿单条流的欠费去比对资金池的原因。对称地，无法刷新快照的 broker 可能在链已暂停某条流之后仍继续服务它，持续时间为该次中断的长度。
- **固定定价。** 每条流无论流量都付同样费率，因此重流被轻流交叉补贴。provider 的敞口由 §16 的按流上限与它自己的 `max_streams` 约束，而不是由价格约束。不愿按治理费率服务的 provider 设 `accepts_new = false` —— 这拒绝的是每一个新对手方，而不是某一个：v2 **没有**按对手方的拒绝能力，因此面对惯性违约方的 provider 依 §5 关闭被遗弃的流，必要时停止接受新流。
- **注册表增长。** `CBQS_STREAM_CREATION_CHARGE` 是贷记给零地址的协议常量，因此永久的流状态花的是不可回收的资本，且没有治理写入能把它设为零；它从 owner 的原生账户借记，因此不会吃掉 provider 已赚到的租金。`max_streams_per_owner` 与各 provider 的 `max_streams` 从另外两个方向约束数量。账户记录不是永久的：§4.3 删除既无余额也无流的账户，这正是阻止 `TopUpAccount` 以 1 nano-CBY 铸出注册表状态的机制。
- **checkpoint 是证据，不是可用性。** 签名 checkpoint 让「被改写或被遗漏的区间」对持有记录的一方可证；只持有部分 lane 的订阅者根本无法验证，且没有任何共识状态锚定 checkpoint 链，因此提供两条分歧链的 provider 只有在同时持有两个分支的一方那里才可能被发现（§11）。v2 没有争议、质押或罚没路径。provider 停止服务时的补救是应用自己的持久副本加上 §4.4 的迁移；有可用性要求的应用**应当**持续维护该副本。
- **机密性是应用的事。** broker 存储它收到的任何字节。不加密的应用等于把明文交给了它的 provider。CBQS 对流量分析不作任何声称：流/lane/组标识符、大小与时序对 provider 可见，而流的存在、归属、provider 指派与计费活动在链上公开。
- **端点可达性。** 共识准入并不确立一个已注册端点可以安全拨号；注册时准入的主机名之后可能解析到私有地址空间，而 DNS 在两次解析之间可能改变。因此 §12.4 把检查放在客户端、写出具体网段，并要求客户端连接到它检查过的那个地址而不是重新解析 —— 那正是 check-then-dial 客户端否则会留下的重绑定缺口。§20 第 7 项让该义务可测而非停留在建议。
- **拒绝服务。** 每个变长字段都在解码时按 §16 的界封顶，发生在分配内存与任何验签之前，因此未认证的对端无法让 broker 越界分配或验签；未在 `cbqs.session_handshake_timeout_ms` 内完成握手的连接被关闭。命名空间耗尽从两侧受限：grant 的 `max_lane_creates_per_min` 限制创建速率，`cbqs.max_lane_tombstones_per_stream` / `cbqs.max_group_tombstones_per_stream` 限制永久的防重用集合。`record_deadline_ms` 被 `cbqs.retention_ms` 封顶，因此没有单个组能永久钉住保留地板、把该流上的每个生产者卡在 `Backpressure` 后面。
- **投递。** 至少一次投递会重复应用副作用。消费者**必须**把副作用做成幂等的，或在自己的状态里去重。lease 只能由签发给它的那个 holder 变更（§10.2），因此一个消费者无法把另一个消费者的记录打进死信。`StrictFifo` 会让一条毒记录阻塞其后的记录，直到消费者拒绝它、尝试次数耗尽、或其截止时间到期；组截止时间与死信检视是对应的运维手段。

### 设计取舍要点（Rationale）

- **链是治理平面，不是数据平面。** v1 让 broker 逐请求读取 finalized 链上状态，并在状态老于某个界时 fail closed，结果是一个「链停它就停」的消息队列，其稳态延迟与可用性被绑到共识上 —— 而它所判定的东西（归属、一把 admin key、一个余额）是以「天」为尺度变化的。v2 把同样的判定留在链上，但改从周期刷新的快照施加，于是数据平面的故障域是它自己的存储，链的角色回到裁决身份、权威与钱。
- **固定的、按账户的计费，及其代价。** v1 在共识里实现了一个容量市场：按流三维定价、两条准入路径（provider 签名报价 / genesis 冻结表）、`pricing_generation`、四个按-provider 预留计数器、按流托管、以及靠钉住的宽限期落实暂停。它比固定费率多买到的是「大流与小流之间的价格歧视」—— 真实但不是首个版本需要的 —— 代价是注册表的大部分状态、大部分指令与大部分故障模式。v2 从一个余额按一个费率收一条流，并用 broker 本就要执行的按流上限约束容量。代价有三，均已写进正文：没有价格歧视；因费率被快照，**没有**为既有流重新定价的办法；以及 provider 的应收不再与该 owner 的其它流隔离，于是结算节奏取代托管成为它的保护，broker 的可用性检查也必须保守。
- **只保留一种投递类别。** v1 在同一份文档里同时规定了至少一次类别与异步持久类别，各有独立的持久化模型、崩溃恢复与标识符形状。v2 保留工作队列所需的至少一次类别，推迟另一个。需要暂定确认的 CRDT 或 presence 工作负载，由一份「针对已运行的 v2 撰写的后续 CIP」来服务，好过在两者都还没有用户时就先规定第二个类别。
- **用批次 checkpoint 取代按记录回执。** v1 对每次追加、每次确认、每次组变更、每次保留推进都签一份回执，维护全局与按 lane 两条回执链，并要求按记录同步持久化。v2 按批次提交、每批签一个 checkpoint。证据变粗（验证者把不当行为定位到批次而非单条记录），而签名、验签与 fsync 的成本按批大小下降。组提交正是普通 broker 达到其吞吐的方式；没有理由让一个链锚定的 broker 为「当前谁也无法据以行动的证据」按记录付费。
- **lane 证明是被推迟，不是被单纯丢弃。** v1 的稀疏 Merkle lane 承诺解决了一个真实缺陷：看不到其它 lane 的按-lane 订阅者无法校验扁平的批次摘要，于是按 lane 的静默遗漏不可检测。v2 在 §11 把这条限制**明说**而不是藏起来，且今天就有替代做法 —— 一条流一个验证域。等到出现让「检测」可以据以行动的争议路径时，这套机制值得重新引入；在那之前，它是几百行保护着一项无人能强制执行的主张的、贴近共识面的密码学。
- **配置属于 broker 状态。** 保留期、消息大小、可见性与尝试上限都由 broker 执行、由 broker 观测。把它们放进共识记录，会让每一次调优都变成一笔交易，还带来一张有两个真相来源的校验表，以及流与其 key stream 之间的跨记录不变量。v2 把上限留在治理里（对每个 provider 统一约束），把设置留在 broker 里（在那里被执行）。
- **被拒方案**：保留 v1 逐步修（被移除的面大多互为承重，逐个拆会让文档在每个中间步骤都自相矛盾）；直接采用现成 broker（Kafka/NATS/RabbitMQ 无法校验 StreamGrant 或执行链控代次，`cbqsd` 保留的正是这一层，其存储引擎仍可插拔）；彻底不要链（归属与撤销正是平台存在的理由，一个自带私有客户表的 broker 不是 Cowboy 服务）；保留逐请求签名（每消息一签一验，而防的是一个既已取得注入位置、本就能重排与丢帧的攻击者）；按消息/按字节计量（需要信任 provider 上报的计数器或把用量上链，固定费率加 broker 本就执行的按流上限把两者都挡在门外）。
