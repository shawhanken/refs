---
title: "CIP-7: 简单流协议"
description: 一个 Actor 原生的流协议，具备确定性签名、有界重放、消息头过滤、VM 级载荷加密、CBY 原生按 epoch 密钥计费，以及可选的定时器驱动数据摄取
icon: rss
---

<Note>
  **状态：** 草案
  **类型：** 标准跟踪
  **类别：** 核心
  **创建日期：** 2026-02-17
  **依赖：** CIP-2（链下计算）、CIP-3（双计量 Gas）、CIP-5（定时器）
</Note>

## 摘要

本 CIP 为 Cowboy 定义了一个简单的流协议。

`StreamActor` 是规范的数据流原语。发布者向流中追加有序消息。消费者使用推送、拉取或"推送 + 拉取回退"方式接收。过滤是确定性的，仅在消息头上进行评估。协议将载荷内联存储，并设有有界的链上重放窗口。

对于付费流，加密和解密是 VM 级别的宿主函数，密钥发放是原生平台计费事件，以 `CBY` 结算。密钥以账户为作用域，因此多个授权 Actor 可以共享同一份权益。协议对每次 key-epoch 购买收取可配置的费用。

## 概述

CIP-7 标准化了以下内容：

- 一种适用于新闻、定价、告警和其他流类型的 `StreamMessage` 格式
- 显式消息版本控制，支持前向兼容
- 每个流严格递增且无间隔的序列号
- `PUSH`、`PULL` 和 `PUSH_WITH_PULL_FALLBACK` 的订阅和投递语义
- 基于消息头/标签的确定性 JSON 过滤 DSL
- 有界重放窗口（`10,000` 条消息），带有明确的 `CURSOR_TOO_OLD` 错误
- 通过 CIP-2 Runner 的可选定时器驱动数据摄取
- 单个活跃发布者密钥，带确定性密钥轮换切换
- 可选的订阅者付费访问，包含 VM 级加密、链上权益、epoch 密钥管理和原生 `CBY` 计费

## 动机

CIP-7 针对以下方面进行优化：

- 使用单一 Actor 模式实现快速部署
- 实时多播投递
- 确定性的重放和过滤行为
- 通过微批处理实际支持新闻源和高频定价
- 平台管理的加密，Actor 无需自行实现密码学
- 从付费流经济中原生捕获 `CBY` 价值

## 设计目标

- 一个协议，一个 Actor 模型
- 序列、签名、过滤和重放的确定性行为
- 推送和拉取均为一等公民
- 存储和扇出工作的显式资源边界
- 可选的数据摄取，不改变核心流语义
- VM 级别的加密/解密原语（用于付费模式）
- 原生按 key-epoch 计费，支持协议费用
- 账户作用域的密钥，支持代付购买（`payer != beneficiary`）
- 滚动权益窗口

## 非目标

- 永久存储保证
- 精确一次投递
- 核心规范中的确认/重试协议
- 载荷级查询语言
- 外部载荷 URI 托管保证
- Actor 自定义密码学（用于付费流）
- v1 中超出 `CBY` 的自定义计费资产
- 链下密钥市场或转售
- 链上密钥托管或多运营商密钥分发（未来 CIP）
- 可退还的预付余额（未来 CIP）

## 协议常量

- `MAX_INLINE_PAYLOAD_BYTES = 16_384`（16 KiB）
- `DEFAULT_RING_BUFFER_CAPACITY = 10_000`
- `MAX_GET_SINCE_LIMIT = 500`
- `DEFAULT_MAX_SUBSCRIBERS = 10_000`
- `DEFAULT_INGEST_INTERVAL_BLOCKS = 1`
- `DEFAULT_KEY_EPOCH_BLOCKS = 600`
- `BILLING_ASSET = CBY`（付费模式 v1 必须）
- `MAX_PROTOCOL_FEE_BPS = 5_000`（50% 上限）
- `CONTENT_CIPHER = XCHACHA20_POLY1305`（付费模式 v1 必须）
- `NONCE_BYTES = 24`
- `TAG_BYTES = 16`
- `MAX_EFFECTIVE_PLAINTEXT_BYTES = 16_344`（16,384 - 24 - 16）
- `DEFAULT_MIN_PURCHASE_EPOCHS = 1`
- `MAX_ACCOUNT_KEYS_PER_ACCOUNT = 8`
- `MAX_ACTOR_AUTHORIZATIONS_PER_STREAM = 64`

## 定义

- **StreamActor**：实现本 CIP 接口的 Actor
- **StreamMessage**：带有有序序列的规范消息信封
- **Cursor（游标）**：与 `get_since` 一起使用的最后消费序列号
- **消息头过滤器**：基于 `kind`、`tags`、`sequence`、`timestamp_unix_ms` 的确定性过滤器
- **头部序列（Head sequence）**：最新发布的序列号
- **底部序列（Floor sequence）**：环形缓冲区中保留的最旧序列号
- **Key epoch**：单个内容加密密钥处于活跃状态的时间窗口（以区块数度量）
- **受益账户（Beneficiary account）**：接收 key-epoch 权益和解密访问权的账户
- **付款账户（Payer account）**：以 `CBY` 支付权益延长费用的账户（可与受益账户不同）
- **账户密钥（Account key）**：账户作用域的 X25519 密钥注册，用于包装 epoch 密钥交付
- **滚动权益窗口（Rolling entitlement window）**：每个 `(stream_id, beneficiary_account)` 的 `active_until_key_epoch` 上限

## 流模型

每个流由一个 Actor 表示，包含：

- `stream_id`
- `head_sequence`（从 `0` 开始；首次发布变为 `1`）
- `floor_sequence`（从 `1` 开始；随修剪推进）
- 单个活跃 `publisher_key`
- 用于跨轮换签名验证的密钥调度历史
- `ring_buffer_capacity`（默认 `10,000`）
- `max_subscribers`
- `subscription_policy`
- 推送投递工作限制
- 可选的数据摄取配置
- 可选的付费模式配置（VM 管理的加密和密钥访问计费）

## 平台架构（付费模式）

付费流的加密和计费由 **流密钥管理器（Stream Key Manager）** 系统 Actor 和 **VM 级宿主函数** 处理，而非由 Actor 代码处理。这消除了每个 Actor 的密码学开销，使每次解密的 epoch 成为原生 `CBY` 计费事件。

### 流密钥管理器系统 Actor

在确定性种子 `0x0000000000000006` 处添加新系统 Actor：

| 种子 | 系统 Actor |
|------|-----------|
| `0x01` | Runner 注册表 |
| `0x02` | 任务调度器 |
| `0x03` | 结果验证器 |
| `0x04` | 密钥管理器 |
| `0x05` | TEE 验证器 |
| **`0x06`** | **流密钥管理器** |

流密钥管理器是以下功能的唯一权威：

- Epoch 内容密钥的派生和存储
- 账户密钥注册
- 账户作用域解密的 Actor 授权
- 权益跟踪和 `CBY` 计费
- 协议费用收取

### HostApi 扩展

在 `HostApi` trait 中添加四个新方法，作为 VM 宿主函数暴露给 Actor Python 代码：

```rust
fn stream_encrypt(
    &mut self,
    stream_id: &[u8],
    key_epoch: u64,
    aad: &[u8],
    plaintext: &[u8],
) -> HostResult<Bytes>;

fn stream_decrypt(
    &mut self,
    stream_id: &[u8],
    beneficiary_account: &[u8],
    key_epoch: u64,
    ciphertext: &[u8],
    aad: &[u8],
) -> HostResult<Bytes>;

fn acquire_epoch_access(
    &mut self,
    params: &[u8],  // CBOR 编码的 AcquireEpochAccessParams
) -> HostResult<Bytes>;  // CBOR 编码的 KeyAccessReceipt

fn register_account_key(
    &mut self,
    params: &[u8],  // CBOR 编码的 RegisterAccountKeyParams
) -> HostResult<Bytes>;  // CBOR 编码的 AccountKeyRegistration
```

这些是同步宿主调用——Actor 调用 `stream_encrypt(...)` 并在同一执行帧中获得密文返回，无消息传递开销。

### 存储布局

流密钥管理器在其系统 Actor 地址下使用存储前缀 `0x6`：

```
0x6 || 0x01 || keccak(stream_id)                                     -> PaidStreamConfig
0x6 || 0x02 || keccak(account)                                       -> [AccountKeyRegistration...]
0x6 || 0x03 || keccak(account) || keccak(actor) || keccak(stream_id) -> ActorAuthorization
0x6 || 0x04 || keccak(stream_id) || keccak(account)                  -> Entitlement
0x6 || 0x05 || keccak(stream_id) || key_epoch_be64                   -> epoch_content_key（静态加密存储）
```

所有状态通过标准 MPT 路径提交，并包含在 `state_root` 中。

## 数据类型

### 1. StreamConfig

字段：

- `stream_id`（bytes32/string）
- `owner`（address）
- `publisher_key`（bytes）：活跃的 ed25519 公钥
- `current_signing_key_id`（uint64）：`publisher_key` 的密钥标识符
- `ring_buffer_capacity`（uint32）：默认 `10,000`
- `max_subscribers`（uint32）：默认 `10,000`
- `subscription_policy`（enum）：`PUBLIC` | `PRIVATE_ALLOWLIST`
- `max_push_deliveries_per_block`（uint32）
- `max_push_cycles_per_block`（uint64）
- `access_mode`（enum）：`OPEN` | `PLATFORM_MANAGED`（别名：`SUBSCRIBER_PAID`）
- `paid_stream_config`（可选 `PaidStreamConfig`）
- `ingestion`（可选 `IngestionConfig`）

规则：

- `ring_buffer_capacity` 必须 > 0
- `current_signing_key_id` 必须 >= 1
- `max_subscribers` 必须 > 0
- 推送限制必须有限且非零
- `SUBSCRIBER_PAID` 是 `PLATFORM_MANAGED` 的已接受别名，用于迁移兼容性；实现必须将两者视为相同
- 如果 `access_mode == PLATFORM_MANAGED`，则 `paid_stream_config` 必须设置
- 如果 `access_mode == OPEN`，则 `paid_stream_config` 必须为空

### 2. PaidStreamConfig（可选）

字段：

- `fee_per_key_epoch_cby`（uint64）：每个新覆盖的 key epoch 的发布者金额，以 CBY wei 为单位
- `protocol_fee_bps`（uint16）：在发布者金额之上应用的基点
- `publisher_treasury`（address）：发布者收入记入的地址
- `protocol_treasury`（address）：协议费用记入的地址
- `key_epoch_blocks`（uint32）：默认 `600`
- `content_cipher`（enum/string）：`XCHACHA20_POLY1305`（v1 必须）
- `key_scope`（enum）：`ACCOUNT`（v1 必须）
- `min_purchase_epochs`（uint32）：默认 `1`

规则：

- `fee_per_key_epoch_cby` 必须 > 0
- `protocol_fee_bps` 必须在 `[0, MAX_PROTOCOL_FEE_BPS]` 范围内
- `key_epoch_blocks` 必须 > 0
- `content_cipher` 在本 CIP 版本中必须为 `XCHACHA20_POLY1305`
- `key_scope` 在本 CIP 版本中必须为 `ACCOUNT`（未来 CIP 可能引入 `ACTOR` 或其他作用域）
- `min_purchase_epochs` 必须 >= 1；覆盖少于 `min_purchase_epochs` 个新收费 epoch 的购买必须以 `MIN_PURCHASE_NOT_MET` 失败
- `publisher_treasury` 必须是有效的账户地址
- `protocol_treasury` 在创世时或通过治理设置；发布者不可覆盖

### 3. StreamMessage

字段：

- `version`（uint8）：本 CIP 修订版必须为 `1`
- `stream_id`（bytes32/string）
- `sequence`（uint64）
- `timestamp_unix_ms`（uint64）
- `kind`（string）：示例 `news`、`price_batch`、`alert`
- `content_type`（string）：载荷媒体类型，默认 `application/json`
- `tags`（`map<string, string | float64 | bool>`）
- `payload_format`（enum）：`PLAINTEXT` | `CIPHERTEXT`
- `payload_inline`（bytes）：必须 ≤ 16 KiB
- `payload_hash`（bytes32）：`SHA-256(payload_inline)`
- `key_epoch`（可选 uint64）：当 `payload_format == CIPHERTEXT` 时必须提供
- `signing_key_id`（uint64）：此序列号处活跃的发布者密钥标识符
- `publisher_sig`（bytes）：对规范签名字节的 ed25519 签名

规则：

- `version` 必须为 `1`
- `payload_inline` 是必需的
- `payload_inline` 大小必须 ≤ `MAX_INLINE_PAYLOAD_BYTES`
- `sequence` 必须严格递增且连续（`prev + 1`）
- `payload_hash` 必须与 `payload_inline` 匹配
- 如果 `payload_format == CIPHERTEXT`，订阅者需要相应的 epoch 密钥来解密
- 在 `PLATFORM_MANAGED` 模式下，流必须发布 `CIPHERTEXT` 消息
- 在 `PLATFORM_MANAGED` 模式下，密文载荷必须由 `stream_encrypt` VM 宿主函数生成
- 在 `CIPHERTEXT` 模式下，`payload_inline` 必须编码为：`nonce(24 字节) || ciphertext_with_tag`
- 在 `CIPHERTEXT` 模式下，16 KiB 限制适用于完整的加密信封（`nonce + ciphertext + tag`）
- 对于 `XCHACHA20_POLY1305`，有效最大明文大小为 `16_384 - 24 - 16 = 16_344` 字节

### 4. Subscription（订阅）

字段：

- `subscriber`（address）
- `mode`（enum）：`PUSH`、`PULL`、`PUSH_WITH_PULL_FALLBACK`
- `filter`（JSON 过滤 DSL）
- `created_at_sequence`（uint64）
- `account_key_id`（可选 uint64）：用于包装 epoch 密钥交付的首选账户密钥；仅为提示
- `status`（enum）：`ACTIVE`、`PAUSED`、`CANCELLED`

规则：

- `subscribe` 必须在激活前验证过滤器模式
- 已满时新订阅必须以 `SUBSCRIBER_CAP_REACHED` 失败
- 在 `PRIVATE_ALLOWLIST` 模式下，非白名单地址必须以 `SUBSCRIPTION_NOT_ALLOWED` 失败
- 订阅控制**投递**（推送/拉取路由）。在 `PLATFORM_MANAGED` 模式下，解密访问由流密钥管理器上的权益单独控制。
- `account_key_id` 是可选提示，标识订阅者用于密钥包装的首选账户密钥。它不授予权益，不触发计费。仅为 SDK 和索引器的便利信息。
- 在 `OPEN` 模式下，订阅不需要付款或权益。

### 5. Entitlement（权益，付费模式）

字段：

- `stream_id`（bytes32/string）
- `beneficiary_account`（address）
- `active_until_key_epoch`（uint64）

语义：

- 权益是滚动的，以账户为作用域
- 账户有权访问所有 key epoch `<= active_until_key_epoch`
- 当当前权益为 `E` 时，购买 epoch `T` 的访问权将对 `E+1..T`（含）收费
- 对已有权益的 epoch 的重复调用是幂等的且免费
- 过去的 epoch 在窗口内无限期可访问
- 权益按 `(stream_id, beneficiary_account)` 对计算

### 6. AccountKeyRegistration（账户密钥注册，付费模式）

字段：

- `account`（address）
- `account_key_id`（uint64）：按账户自增
- `scheme`（string）：`"X25519"`（v1 必须）
- `public_key`（bytes）：用于 epoch 密钥包装的 X25519 公钥
- `status`（enum）：`ACTIVE` | `REVOKED`
- `registered_at`（uint64）：区块高度

规则：

- 密钥由**账户**拥有，而非任何 Actor
- 一个账户最多可注册 `MAX_ACCOUNT_KEYS_PER_ACCOUNT` 个密钥
- `account_key_id` 从 `1` 开始顺序分配
- 已吊销的密钥不得用于未来的密钥包装或解密
- 密钥注册必须由账户持有者签名

### 7. ActorAuthorization（Actor 授权，付费模式）

字段：

- `account`（address）
- `actor`（address）
- `stream_id`（bytes32）
- `scope`（enum）：`STREAM_DECRYPT`
- `status`（enum）：`ACTIVE` | `REVOKED`
- `granted_at`（uint64）：区块高度

规则：

- Actor 必须由账户明确授权才能代表该账户对特定流进行解密
- 授权按 `(account, actor, stream_id)` 三元组计算
- 一个账户每个流最多可授权 `MAX_ACTOR_AUTHORIZATIONS_PER_STREAM` 个 Actor
- 吊销立即生效：被吊销的 Actor 从下一个区块开始不得解密
- 账户所有者自己的 Actor（其中 `actor.creator == account`）自动授权，除非被显式吊销

### 8. KeyAccessReceipt（密钥访问收据，付费模式）

字段：

- `stream_id`（bytes32）
- `beneficiary_account`（address）
- `payer_account`（address）
- `from_key_epoch`（uint64）：首个新收费的 epoch（E+1）
- `to_key_epoch`（uint64）：最后收费的 epoch（T）
- `epochs_charged`（uint64）：T - E（幂等时可能为 0）
- `publisher_amount_cby`（uint64）
- `protocol_fee_cby`（uint64）
- `total_amount_cby`（uint64）

### 9. IngestionConfig（数据摄取配置，可选）

字段：

- `enabled`（bool）
- `interval_blocks`（uint32）：默认 `1`
- `task_definition`（object）：CIP-2 任务请求
- `result_schema`（object）
- `transform_method`（可选 string）
- `num_runners`（uint8）
- `proof_type`（enum，来自 CIP-2）

规则：

- 启用时，Actor 必须调度循环定时器回调
- Actor 必须使用配置的 `num_runners` 和 `proof_type` 提交 CIP-2 任务
- 摄取失败不得递增序列号

## 规范哈希和签名（规范性）

本 CIP 固定了签名和编码规则。

- `signature_scheme`：ed25519
- `hash_alg`：SHA-256
- `canonical_encoding`：确定性 CBOR（RFC 8949 规范形式）

签名载荷对象的键和值：

- `stream_id`
- `version`
- `sequence`
- `timestamp_unix_ms`
- `kind`
- `content_type`
- `tags`
- `payload_format`
- `payload_hash`
- `key_epoch`（当 `payload_format == PLAINTEXT` 时为 `null`）
- `signing_key_id`

过程：

1. 计算 `payload_hash = SHA-256(payload_inline)`
2. 使用上述键构建签名载荷对象
3. 使用确定性 CBOR 编码
4. 用 ed25519 私钥签名
5. 将签名存储在 `publisher_sig` 中

验证：

- 消费者必须重新计算 `payload_hash`
- 消费者必须重建确定性 CBOR 签名载荷
- 消费者必须使用在该序列号处生效的密钥调度条目验证 `publisher_sig`
- 消费者可以通过 `get_key_at_sequence` 或缓存的 `get_key_history` 输出解析密钥调度

签名载荷的标签规范化：

- `tags` 键必须是 CBOR 文本字符串
- 字符串标签值必须是 CBOR 文本字符串
- 布尔标签值必须是 CBOR `true`/`false`
- 数值标签值必须是有限的 IEEE-754 binary64，编码为 CBOR float64（主类型 7，附加信息 27）
- 生产者不得在签名载荷字节中将数值标签编码为 CBOR 整数

密文 nonce 格式：

- 对于 `XCHACHA20_POLY1305`，nonce 必须恰好为 24 字节
- Nonce 必须作为 `payload_inline` 的前 24 字节内联携带
- 在 `PLATFORM_MANAGED` 模式下，nonce 生成由 VM 处理，并结合 `actor_nonce`（每 Actor 单调递增计数器）以防止重用。禁止在同一内容密钥下重用 nonce。

## Actor 接口

### 必需方法

#### `publish(kind, content_type?, tags, payload_format, payload_inline, key_epoch?, publisher_sig)`

行为：

1. 验证载荷大小 ≤ 16 KiB
2. 如果省略 `content_type`，设置 `content_type = application/json`
3. 计算 `payload_hash = SHA-256(payload_inline)`
4. 验证 `payload_format` 和 `key_epoch` 一致性
5. 如果是 `PLATFORM_MANAGED` 模式，要求 `payload_format == CIPHERTEXT`
6. 使用包含计算出的 `payload_hash` 的签名载荷，验证签名与活跃发布者密钥匹配
7. 设置 `next_sequence = head_sequence + 1`
8. 在 `next_sequence` 处持久化消息，包含 `version=1`、`content_type` 和 `signing_key_id`
9. 更新 `head_sequence = next_sequence`
10. 确定性修剪环形缓冲区（见修剪章节）
11. 触发 `StreamMessagePublished` 事件
12. 将消息加入推送投递队列

付费模式发布流程：

1. 发布者 Actor 组成明文载荷、元数据、标签和类型。
2. Actor 计算 `key_epoch = floor(block_height / key_epoch_blocks)`。
3. Actor 调用 `stream_encrypt(stream_id, key_epoch, aad, plaintext)` — 一个 VM 宿主函数。
4. VM 返回密文信封（`nonce || ciphertext || tag`）。
5. Actor 设置 `payload_format = CIPHERTEXT`，`payload_inline = ciphertext_envelope`。
6. Actor 正常签名并调用 `publish(...)`。

#### `subscribe(mode, filter, start_cursor?, account_key_id?)`

行为：

- 验证 `mode` 和过滤器模式
- 强制执行订阅策略和订阅者上限
- 创建或更新订阅
- 如果省略 `start_cursor`，设置为当前 `head_sequence`
- 触发 `SubscriberUpdated` 事件

重新订阅 / 更新语义：

- `subscribe` 是以 `subscriber` 为键的 upsert 操作
- 更新时，订阅者可以更改 `mode`、`filter` 和 `account_key_id`
- 更新时 `created_at_sequence` 必须保持不变
- `start_cursor` 仅在创建时适用；更新时忽略

注意：在 `PLATFORM_MANAGED` 模式下，订阅仅控制投递路由。计费发生在密钥访问获取时（通过 `acquire_epoch_access`），而非在订阅创建或续订时。`account_key_id` 参数是密钥包装偏好的可选提示，不触发任何付款。

#### `unsubscribe()`

行为：

- 将状态设置为 `CANCELLED`
- 触发 `SubscriberUpdated` 事件

#### `renew_subscription(target_key_epoch, beneficiary_account?, payer_account?, account_key_id?)`

行为：

- 原生 `acquire_epoch_access` 的便捷包装，用于 SDK 人体工程学。
- 如果 `access_mode != PLATFORM_MANAGED`，以 `NOT_PLATFORM_MANAGED_STREAM` 失败。
- 如果省略 `beneficiary_account`，默认为调用者账户。
- 如果省略 `payer_account`，默认为调用者账户。
- 如果调用者没有活跃订阅，以 `PAYMENT_REQUIRED` 失败（请先订阅，然后获取访问权）。
- 如果提供 `account_key_id`，更新订阅的 `account_key_id` 提示。
- 必须委托给流密钥管理器上的 `acquire_epoch_access` 并返回结果 `KeyAccessReceipt`。

注意：

- 此方法是可选的。客户端可以直接通过平台宿主函数调用 `acquire_epoch_access`。
- 计费发生在密钥访问获取时，而非订阅创建时。此方法仅为向后兼容和 SDK 便利而存在。

#### `get_since(cursor, limit)`

输入：

- `cursor`：最后消费的序列号
- `limit`：`1..500`

行为：

- 使用 `LIMIT_EXCEEDED` 拒绝无效 limit
- 如果 `cursor < floor_sequence - 1`，返回 `CURSOR_TOO_OLD`
- 返回 `sequence > cursor` 的消息，升序排列
- 最多返回 `limit` 条

付费模式拉取规则：

- `get_since` 无论权益状态如何都返回密文消息
- 权益控制的是解密密钥访问，而非密文检索

#### `get_head()`

返回：

- `head_sequence`
- `floor_sequence`
- 消费者所需的流元数据

#### `rotate_publisher_key(new_key)`

行为：

- 仅所有者可用
- 分配 `new_signing_key_id = current_signing_key_id + 1`
- 设置 `effective_sequence = head_sequence + 1`
- 新密钥从 `effective_sequence` 开始生效
- 追加密钥调度条目 `{signing_key_id, pubkey, effective_sequence}`
- 触发 `PublisherKeyRotated(old_key, new_key, old_signing_key_id, new_signing_key_id, effective_sequence)` 事件

#### `get_key_at_sequence(sequence)`

返回用于验证的密钥调度解析：

- `signing_key_id`
- `publisher_key`
- `effective_sequence`

#### `get_key_history(from_signing_key_id?, limit?)`

返回有序的密钥调度条目，用于批量验证。

#### `announce_key_epoch(key_epoch)`

行为：

- 仅所有者可用
- 在链上公布 key epoch 进展元数据
- `key_epoch` 相对于之前的公布必须非递减
- 触发 `KeyEpochRotated(stream_id, key_epoch, effective_block_height, announced_by)` 事件

注意：

- 此方法不在链上发布密钥材料
- 它为索引器、订阅者和审计锚定 key-epoch 进展

#### `set_subscription_policy(policy)`

行为：

- 仅所有者可用
- 设置 `PUBLIC` 或 `PRIVATE_ALLOWLIST`

#### `allowlist_add(address)` / `allowlist_remove(address)`

行为：

- 仅所有者可用
- 管理策略为 `PRIVATE_ALLOWLIST` 时使用的白名单

### 平台密钥管理方法

这些方法作为 VM 宿主函数暴露，由流密钥管理器系统 Actor 支撑。在执行期间任何 Actor 均可使用。

#### `stream_encrypt(stream_id, key_epoch, aad, plaintext) -> ciphertext`

调用者：发布者 Actor（或对该流有发布权的任何 Actor）。

行为：

1. 验证此流的 `access_mode == PLATFORM_MANAGED`。
2. 派生 epoch 内容密钥：`content_key = KDF(master_seed, stream_id, key_epoch)`。
3. 生成确定性 nonce：`nonce = HKDF-Expand(content_key, stream_id || key_epoch || actor_nonce, 24)`。
4. 加密：`ciphertext = XChaCha20-Poly1305-Encrypt(content_key, nonce, aad, plaintext)`。
5. 返回 `nonce(24) || ciphertext || tag(16)`。

Gas 成本：

- Cycles：`500 + (plaintext.len() * 2)`
- Cells：输出信封大小

规则：

- Actor 不得为 `PLATFORM_MANAGED` 流实现自己的加密。
- `plaintext.len()` 必须 ≤ `MAX_EFFECTIVE_PLAINTEXT_BYTES`（16,344 字节）。
- `aad` 应包含 `stream_id`、`sequence`、`key_epoch`、`kind`、`content_type` 以进行绑定。
- 通过结合 `actor_nonce`（自动递增）防止与同一内容密钥重用 nonce。

#### `stream_decrypt(stream_id, beneficiary_account, key_epoch, ciphertext, aad) -> plaintext`

调用者：由 `beneficiary_account` 为此流授权的任何 Actor。

行为：

1. 从执行上下文解析调用 Actor 的地址。
2. 验证 `(beneficiary_account, caller_actor, stream_id)` 的 `ActorAuthorization` 为 `ACTIVE`。
3. 验证 `(stream_id, beneficiary_account)` 的 `Entitlement` 包含 `key_epoch`（即 `key_epoch ≤ active_until_key_epoch`）。
4. 派生 epoch 内容密钥（与加密相同的 KDF）。
5. 从 `ciphertext` 前 24 字节提取 nonce。
6. 解密：`plaintext = XChaCha20-Poly1305-Decrypt(content_key, nonce, aad, ciphertext_body)`。
7. 返回 `plaintext`。

Gas 成本：

- Cycles：`500 + (ciphertext.len() * 2)`
- Cells：明文输出大小

错误条件：

- `ACTOR_NOT_AUTHORIZED_FOR_ACCOUNT` — Actor 缺少授权
- `ENTITLEMENT_REQUIRED` — epoch 不在权益窗口内
- `DECRYPTION_FAILED` — 密文被篡改或密钥错误
- `NOT_PLATFORM_MANAGED_STREAM` — 流为 `OPEN` 模式

#### `acquire_epoch_access(stream_id, beneficiary_account, payer_account, target_key_epoch) -> KeyAccessReceipt`

调用者：任何 Actor（代表 `payer_account`）。交易必须由 `payer_account` 签名，或付款者必须已委托消费权限。

行为：

1. 验证此流的 `access_mode == PLATFORM_MANAGED`。
2. 解析当前权益：`E = active_until_key_epoch`（针对 `(stream_id, beneficiary_account)`）。如果不存在权益，`E = current_key_epoch - 1`（无免费追溯访问）。
3. 如果 `target_key_epoch ≤ E`：返回幂等收据，`epochs_charged = 0`，`total_amount_cby = 0`。触发 `EpochAccessIdempotent` 事件。
4. 计算 `epochs_charged = target_key_epoch - E`。
5. 如果 `epochs_charged < min_purchase_epochs`，以 `MIN_PURCHASE_NOT_MET` 失败。
6. 计算费用：
   ```
   publisher_amount = epochs_charged * fee_per_key_epoch_cby
   protocol_fee     = floor(publisher_amount * protocol_fee_bps / 10_000)
   total            = publisher_amount + protocol_fee
   ```
7. 从 `payer_account` 余额转移 `total` CBY。余额不足时以 `INSUFFICIENT_CBY_BALANCE` 失败。
8. 将 `publisher_amount` 记入 `publisher_treasury`。
9. 将 `protocol_fee` 记入 `protocol_treasury`。
10. 设置 `(stream_id, beneficiary_account)` 的 `active_until_key_epoch = target_key_epoch`。
11. 触发 `EpochAccessPurchased` 事件。
12. 返回 `KeyAccessReceipt`。

Gas 成本：

- Cycles：`5,000`（固定）
- Cells：`500`

规则：

- `payer_account` 可以与 `beneficiary_account` 不同（代付）。
- 权益累积给 `beneficiary_account`，绝不给 `payer_account`。付款者没有隐式的解密密钥访问权。
- 对已有权益的 epoch 的重复调用必须是幂等的且不收费。
- `target_key_epoch` 必须 >= `current_key_epoch`。v1 中不允许仅购买历史 epoch 而不覆盖当前。
- 此方法是付费流解密的**规范性唯一计费点**。

#### `register_account_key(account, scheme, public_key) -> AccountKeyRegistration`

调用者：账户持有者。

行为：

1. 验证交易由 `account` 签名。
2. 验证 `scheme` 为 `"X25519"`（v1）。
3. 验证 `public_key` 长度（X25519 为 32 字节）。
4. 检查账户的活跃密钥少于 `MAX_ACCOUNT_KEYS_PER_ACCOUNT`。
5. 分配此账户的 `account_key_id = next_id`（自增）。
6. 存储 `AccountKeyRegistration`。
7. 触发 `AccountKeyRegistered` 事件。
8. 返回注册信息。

Gas 成本：

- Cycles：`2,000`
- Cells：`200`

#### `authorize_actor(account, actor, stream_id) -> ActorAuthorization`

调用者：账户持有者。

行为：

1. 验证交易由 `account` 签名。
2. 验证 Actor 地址存在。
3. 检查 `(account, stream_id)` 的授权数量低于 `MAX_ACTOR_AUTHORIZATIONS_PER_STREAM`。
4. 存储 `ActorAuthorization`，`status = ACTIVE`。
5. 触发 `ActorAuthorizationGranted` 事件。

Gas 成本：

- Cycles：`1,000`
- Cells：`100`

#### `revoke_actor(account, actor, stream_id)`

调用者：账户持有者。

行为：

1. 验证交易由 `account` 签名。
2. 设置 `ActorAuthorization.status = REVOKED`。
3. 触发 `ActorAuthorizationRevoked` 事件。

Gas 成本：

- Cycles：`500`
- Cells：`50`

#### `revoke_account_key(account, account_key_id)`

调用者：账户持有者。

行为：

1. 验证交易由 `account` 签名。
2. 设置 `AccountKeyRegistration.status = REVOKED`。
3. 触发 `AccountKeyRevoked` 事件。

Gas 成本：

- Cycles：`500`
- Cells：`50`

## 推送投递语义

- 推送是尽力多播
- 投递是至少一次
- 无协议级确认或重试
- 推送消息包含完整的 `StreamMessage`，包括完整的内联载荷
- 消费者必须通过 `(stream_id, sequence)` 进行去重

付费模式投递规则：

- 推送投递是传输层关注点，可以不考虑密钥权益状态投递密文。
- 解密仍然由流密钥管理器上的账户权益和 Actor 授权控制。

### 推送工作边界和经济学

- 流 Actor 执行承担推送扇出成本
- 所有者负责资助 Actor 运行
- Actor 必须强制执行：
  - `max_push_deliveries_per_block`
  - `max_push_cycles_per_block`
- 未投递的订阅者保持等待，在后续区块中处理
- 推送投递绝不得超过配置的每区块边界

## `PUSH_WITH_PULL_FALLBACK` 语义

`PUSH_WITH_PULL_FALLBACK` 含义：

- Actor 行为与 `PUSH` 相同（尽力投递，无重试）
- 订阅者行为额外包括使用 `get_since` 的定期拉取追赶
- 回退是订阅者驱动的，非 Actor 驱动
- Actor 不执行自动模式切换

## 拉取投递语义

- 拉取消费者跟踪本地游标
- 消费者调用 `get_since(cursor, limit)`
- 过期游标通过 `CURSOR_TOO_OLD` 明确告知

付费模式拉取规则：

- `get_since` 无论权益状态如何都返回密文消息
- 权益控制密钥发放/解密，而非密文检索

## 支付和密钥管理（规范性）

本节定义了订阅者付费变现如何与 VM 级加密和原生 `CBY` 计费协同工作。

### 链上权益

- 在 `PLATFORM_MANAGED` 模式下，权益通过流密钥管理器上的 `active_until_key_epoch` 按 `(stream_id, beneficiary_account)` 跟踪
- Key epoch 计算公式：`floor(block_height / paid_stream_config.key_epoch_blocks)`
- 权益窗口是滚动的：epoch `k` 的访问检查在 `k ≤ active_until_key_epoch` 时成功

### 载荷保密性

- 流在 `PLATFORM_MANAGED` 模式下发布内联 `CIPHERTEXT` 载荷
- 密文全局可读，但明文需要密钥访问权和 Actor 授权
- 加密/解密必须使用 VM 原生宿主函数

### Epoch 内容密钥

- 平台为每个流每个 key epoch 管理一个内容密钥
- `StreamMessage.key_epoch` 将每条消息绑定到一个 key epoch
- 在 `PLATFORM_MANAGED` 模式下，Actor 代码不得实现自定义内容密钥密码学

### 密钥分发流程

1. 调用者使用 `stream_id`、`beneficiary_account`、`payer_account` 和 `target_key_epoch` 调用 `acquire_epoch_access`
2. 平台解析当前权益终点 `E`
3. 如果 `target_key_epoch ≤ E`，不收费（幂等）
4. 否则计算 `epochs_charged = target_key_epoch - E`；低于 `min_purchase_epochs` 则拒绝
5. 对新覆盖的 epoch `E+1..target_key_epoch` 收费：
   - `publisher_amount = epochs_charged * fee_per_key_epoch_cby`
   - `protocol_fee = floor(publisher_amount * protocol_fee_bps / 10_000)`
   - `total = publisher_amount + protocol_fee`
6. 从 `payer_account` 转移 `total` CBY
7. 将收入记入发布者和协议金库
8. 设置 `active_until_key_epoch = target_key_epoch`
9. 触发 `EpochAccessPurchased` 事件

### 账户作用域密钥和 Actor 复用

- 密钥按账户注册（而非按 Actor 或按订阅）
- 授权的 Actor 可以代表该账户对特定流进行解密
- Actor 授权和账户密钥吊销立即生效
- 此模型意味着一次订阅付款覆盖了一个账户消费同一流的所有 Actor

### 代付购买

- `payer_account` 可以是任何有资金的账户，包括第三方
- `CBY` 从 `payer_account` 扣除；权益累积给 `beneficiary_account`
- 付款者没有隐式的解密密钥访问权
- 用例：雇主为员工代付访问权、DAO 金库为成员提供资金、试用/促销赠送

### 协议费用

- 创建时在 `[0, MAX_PROTOCOL_FEE_BPS]` 范围内按流可配置
- 叠加式计算：总费用 = 发布者价格 + 额外的协议费用
- `protocol_treasury` 地址在创世时或通过治理设置；发布者不可覆盖
- 协议费用创造与整个生态系统中付费流使用量成正比的直接 `CBY` 需求

### CBY 价值流

```
付款账户
    |
    |── publisher_amount ──> 发布者金库（流所有者收入）
    |
    └── protocol_fee ──────> 协议金库（生态系统价值捕获）
                                |
                                |── 燃烧（通缩压力）
                                |── 质押奖励
                                └── 发展基金
                                    （分配由治理决定）
```

### 可扩展性指导

- 使用 epoch 密钥（例如，10 分钟 epoch，1 秒出块 = 600 个区块）而非按消息密钥
- 滚动窗口和幂等购买语义避免重复收费
- 模型支持大型订阅者集合（100, 1,000, 10,000），投递和计费开销稳定

## 环形缓冲区修剪（确定性）

状态：

- `head_sequence`
- `floor_sequence`
- `ring_buffer_capacity`

每次成功发布时：

1. 在 `head_sequence + 1` 处追加消息
2. 设置 `head_sequence = head_sequence + 1`
3. 如果 `(head_sequence - floor_sequence + 1) > ring_buffer_capacity`：
   - 删除 `floor_sequence` 处的消息
   - 设置 `floor_sequence = floor_sequence + 1`

空流规则：

- 当 `head_sequence == 0` 时，流没有保留的消息
- 在此状态下，不得评估修剪条件
- `get_since` 对有效 limit 必须返回空结果集

过期游标规则：

- 当 `cursor < floor_sequence - 1` 时游标过期

## JSON 过滤 DSL

过滤器仅在以下字段上评估：

- `kind`
- `tags.<key>`
- `sequence`
- `timestamp_unix_ms`

运算符：

- `eq`、`ne`、`in`、`nin`、`gte`、`lte`、`exists`

逻辑形式：

- `{"all": [ ... ]}`（AND）
- `{"any": [ ... ]}`（OR）
- `{"not": { ... }}`

示例：

```json
{
  "all": [
    {"field": "kind", "op": "eq", "value": "price_batch"},
    {"field": "tags.symbol", "op": "in", "value": ["BTC", "ETH"]},
    {"field": "tags.venue", "op": "eq", "value": "coinbase"},
    {"field": "tags.confidence", "op": "gte", "value": 0.9}
  ]
}
```

确定性约束：

- 最大深度：`4`
- 最大谓词数：`16`
- 未知字段/运算符必须使订阅验证失败

## 数据摄取流程（可选）

当 `ingestion.enabled == true` 时：

1. 定时器每 `interval_blocks` 个区块触发一次（默认 `1`）
2. Actor 使用配置的以下参数提交 CIP-2 任务：
   - `task_definition`
   - `result_schema`
   - `num_runners`
   - `proof_type`
3. Runner 回调返回结果
4. Actor 将结果转换为可发布的载荷
5. 对于 `PLATFORM_MANAGED` 模式，Actor 在发布前调用 `stream_encrypt(...)`
6. Actor 为每个转换后的载荷调用 `publish(...)`
7. Actor 重新调度下一个摄取定时器

失败行为：

- 递增 `ingest_fail_count`
- 触发 `IngestFailed(reason, timestamp_unix_ms)` 事件
- 失败尝试不递增序列号

## 高频定价指导（非规范性）

对于 1 秒出块节奏，定价流应使用微批处理：

- 每个区块发布一条 `price_batch` 消息
- 在一个内联载荷中包含多个价格点
- 保持载荷 ≤ 16 KiB
- 使用 `symbol`、`venue`、`window_ms`、`count` 等标签进行过滤

## 事件

### `StreamMessagePublished`

- `stream_id`
- `version`
- `sequence`
- `kind`
- `content_type`
- `payload_format`
- `payload_hash`
- `key_epoch`（可为 null）
- `signing_key_id`
- `timestamp_unix_ms`

### `SubscriberUpdated`

- `stream_id`
- `subscriber`
- `mode`
- `status`

### `PublisherKeyRotated`

- `stream_id`
- `old_key`
- `new_key`
- `old_signing_key_id`
- `new_signing_key_id`
- `effective_sequence`

### `EpochAccessPurchased`

- `stream_id`
- `beneficiary_account`
- `payer_account`
- `from_key_epoch`
- `to_key_epoch`
- `epochs_charged`
- `publisher_amount_cby`
- `protocol_fee_cby`
- `total_amount_cby`

### `EpochAccessIdempotent`

- `stream_id`
- `beneficiary_account`
- `target_key_epoch`
- `active_until_key_epoch`

### `AccountKeyRegistered`

- `account`
- `account_key_id`
- `scheme`
- `block_height`

### `AccountKeyRevoked`

- `account`
- `account_key_id`
- `block_height`

### `ActorAuthorizationGranted`

- `account`
- `actor`
- `stream_id`
- `scope`
- `block_height`

### `ActorAuthorizationRevoked`

- `account`
- `actor`
- `stream_id`
- `block_height`

### `KeyEpochRotated`

- `stream_id`
- `key_epoch`
- `effective_block_height`
- `announced_by`（address）

### `IngestFailed`

- `stream_id`
- `timestamp_unix_ms`
- `reason`

## 错误码

Actor 方法错误：

- `INVALID_SIGNATURE`
- `PAYLOAD_TOO_LARGE`
- `INVALID_FILTER`
- `CURSOR_TOO_OLD`
- `LIMIT_EXCEEDED`
- `UNAUTHORIZED`
- `SUBSCRIBER_CAP_REACHED`
- `SUBSCRIPTION_NOT_ALLOWED`

平台密钥管理错误：

- `NOT_PLATFORM_MANAGED_STREAM`
- `PAYMENT_REQUIRED` — 不存在权益且调用者未发起购买
- `ACTOR_NOT_AUTHORIZED_FOR_ACCOUNT`
- `ENTITLEMENT_REQUIRED`
- `INSUFFICIENT_CBY_BALANCE`
- `INVALID_TARGET_KEY_EPOCH`
- `MIN_PURCHASE_NOT_MET`
- `DECRYPTION_FAILED`
- `INVALID_ACCOUNT_KEY`
- `ACCOUNT_KEY_LIMIT_REACHED`
- `AUTHORIZATION_LIMIT_REACHED`
- `KEY_REVOKED`

错误映射：

- `publish`：`INVALID_SIGNATURE`、`PAYLOAD_TOO_LARGE`、`UNAUTHORIZED`
- `subscribe`：`INVALID_FILTER`、`SUBSCRIBER_CAP_REACHED`、`SUBSCRIPTION_NOT_ALLOWED`
- `renew_subscription`：`PAYMENT_REQUIRED`、`INSUFFICIENT_CBY_BALANCE`、`INVALID_TARGET_KEY_EPOCH`、`MIN_PURCHASE_NOT_MET`、`NOT_PLATFORM_MANAGED_STREAM`
- `get_since`：`LIMIT_EXCEEDED`、`CURSOR_TOO_OLD`
- `rotate_publisher_key`：`UNAUTHORIZED`
- `set_subscription_policy`：`UNAUTHORIZED`
- `allowlist_add` / `allowlist_remove`：`UNAUTHORIZED`
- `announce_key_epoch`：`UNAUTHORIZED`
- `stream_encrypt`：`NOT_PLATFORM_MANAGED_STREAM`、`PAYLOAD_TOO_LARGE`
- `stream_decrypt`：`NOT_PLATFORM_MANAGED_STREAM`、`ACTOR_NOT_AUTHORIZED_FOR_ACCOUNT`、`ENTITLEMENT_REQUIRED`、`DECRYPTION_FAILED`、`KEY_REVOKED`
- `acquire_epoch_access`：`NOT_PLATFORM_MANAGED_STREAM`、`INSUFFICIENT_CBY_BALANCE`、`INVALID_TARGET_KEY_EPOCH`、`MIN_PURCHASE_NOT_MET`
- `register_account_key`：`INVALID_ACCOUNT_KEY`、`ACCOUNT_KEY_LIMIT_REACHED`、`UNAUTHORIZED`
- `authorize_actor`：`AUTHORIZATION_LIMIT_REACHED`、`UNAUTHORIZED`
- `revoke_actor`：`UNAUTHORIZED`
- `revoke_account_key`：`UNAUTHORIZED`、`KEY_REVOKED`

## 安全考量

- 消费者在信任数据前必须验证签名和载荷哈希
- 推送可能产生重复投递；消费者必须实现幂等处理
- 过滤器验证限制降低了来自病态表达式的 DoS 风险
- 订阅者上限和推送工作限制降低了扇出滥用风险
- 确定性密钥轮换切换避免了序列边界处的签名者歧义
- 付费模式解密必须同时执行权益和 Actor 授权检查
- 账户密钥泄露会授予该账户在所有流上所有已授权 epoch 的访问权；账户应定期轮换密钥
- Actor 授权吊销必须立即阻止该 Actor 未来的解密调用
- 账户密钥吊销阻止与该密钥 ID 关联的所有未来包装和解密
- Epoch 密钥泄露会暴露该 epoch 密钥下加密的所有消息；运营商应使用短 key epoch 以减少影响范围
- VM 原生密码学必须使用经过侧信道抗性审计的常数时间实现
- 通过将 `actor_nonce` 纳入 nonce 派生来保证 nonce 唯一性
- 代付购买不会向付款者泄露密钥材料
- 协议金库地址由治理控制；发布者金库的泄露不影响协议费用收取
- 权益状态在链上且可验证；无链下密钥服务信任假设

## 向后兼容性

本 CIP 可独立采用。

从先前流实现的迁移：

1. 将现有的 feed 消息映射到 `StreamMessage`
2. 通过 `subscribe` + `get_since` 复用订阅者逻辑
3. 移除对保留专属协议原语的核心流依赖
4. 对于 Actor 管理的付费流：将 `access_mode` 切换为 `PLATFORM_MANAGED`（或使用 `SUBSCRIBER_PAID` 别名以兼容迁移），移除 Actor 加密代码，注册账户密钥，使用 `acquire_epoch_access` 进行计费
5. 推送投递不再以权益为门控 — 密文投递给所有订阅者，无论付款状态如何。解密是访问控制边界，而非传输。

## 参考实现说明（非规范性）

- SDK `StreamActor` 应暴露完整的 Actor 方法集
- SDK 应包含 `stream_encrypt`、`stream_decrypt` 和 `acquire_epoch_access` 的便捷包装
- 修剪应为 O(1) 摊销
- 推送调度器应使用对活跃订阅者的确定性轮询
- 权益查找应通过 `(stream_id, beneficiary_account)` 实现 O(1)
- VM 宿主函数实现应使用 libsodium 或等效的经审计 AEAD 库

## 设计理由

### 为什么是 VM 级而非 Actor 级加密？

在 Actor 级进行加密要求每个付费流独立在 Python 中实现密码学，并为应该是原生的操作支付解释执行的 gas 成本。16 KiB 加密在 Python 中约需 ~180,000 cycles，而作为 VM 宿主函数仅需 ~33,000 cycles。除了 gas 节省外，VM 级密码学消除了一整类 Actor 错误（nonce 重用、错误的密码模式、Actor 存储中的密钥泄露）。

### 为什么是 VM 宿主函数而非系统 Actor 消息？

系统 Actor 消息需要延迟交易开销（发送消息，在下一个区块等待回调）。VM 宿主函数是同步的 — Actor 调用 `stream_encrypt(...)` 并在同一执行帧中获得密文返回。这对发布路径至关重要。

### 为什么是账户作用域而非 Actor 作用域密钥？

账户是自然的计费实体。Actor 是程序；账户是经济主体。如果账户 A 部署了五个消费 Actor，它们都读取相同的价格流，它们应该共享一个权益和一个密钥注册。Actor 作用域密钥强制对同一经济关系进行五次单独付款。

### 为什么是滚动窗口而非静态范围？

静态范围（`from_epoch..to_epoch`）在间隙、重叠和部分退款方面增加了复杂性。滚动上限更简单：每个权益一个整数，单调递增，幂等扩展。它支持按需购买、代付充值和持续消费，无需订阅生命周期管理。

### 为什么协议费用是叠加式（附加）而非嵌入式？

叠加式费用（`total = publisher_price + protocol_cut`）是透明的。发布者设定价格；协议添加其费用。谁得到什么没有歧义。嵌入式费用（协议从发布者声明的价格中抽取 X%）会产生激励错位，发布者会抬高价格以抵消抽成。

### 为什么将订阅与权益分离？

订阅控制投递路由（推送/拉取）。权益控制解密访问（key epochs）。将两者分离意味着订阅者可以通过推送接收密文而无需付款（只是不能解密），账户可以在任何 Actor 订阅之前预购 epoch 访问权。这比将付款与订阅生命周期耦合更清晰。

## 开放问题

- `protocol_fee_bps` 应该全局固定还是在边界内按流可配置？
- 未来扩展是否应定义批量 epoch 购买折扣？
- 未来扩展是否应定义链上密钥托管以支持运营商故障转移？
- `protocol_treasury` 的分配（燃烧 vs. 质押 vs. 基金）应在本 CIP 中指定还是推迟到治理 CIP？
- 是否应该有一个最大 `key_epoch_blocks` 以防止发布者设置过长的 epoch 从而降低计费粒度？
- 未来扩展是否应添加可选的投递收据（无重试）？
- 未来扩展是否应定义可退还的预付余额或按比例退款？
- 当 `access_mode` 或 `paid_stream_config` 变更时，是否应触发 `StreamConfigUpdated` 事件？
