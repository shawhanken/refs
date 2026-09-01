# CIP-39 V2 Marshal 深度审核结论

日期：2026-08-25  
审查对象：`docs/cips/cip-39-cowboy-queue-system.md`  
Base：`beb1e5c1e23351e619d18dea6a6f85f292e77d1a` (`origin/main`)  
Head：`4567d3ee74bad3515a862265635e27e4966a8de4`  
Marshal review run：`31`

## GateDecision

**Escalate。CIP-39 V2 可以继续作为 Draft 迭代，但不应以当前文本进入实现冻结或网络激活。**

V2 的方向明显优于 V1：它删除了 Fast delivery、平台加密、per-action receipts、
lane proofs、provider quote、per-stream economics 等大块机制，并把链从消息数据路径移除。
但这次变化主要完成了“删功能”，尚未完成“压缩模型”。当前规范仍有约 3,124 行、
142 个 `MUST`、33 个治理参数、18 个数据面方法、46 个 wire error，以及 61 个目标与
one-hop 概念面。

Marshal 的四视角审查和独立 prove 最终确认 13 项问题：9 项 high、4 项 medium。
其中存在合规输入触发的静默重复 append、无界 broker 状态增长，以及多个会使两个诚实
实现产生不同结果的状态机缺口。

## V2 相对 V1 的有效简化

以下方向应当保留：

- 链退回治理与注册平面，消息路径不再逐请求读取链状态；
- 经济状态收敛为每个 `(owner, provider)` 一个预付账户；
- 删除 Fast/async-durable class、broker epoch 和 clean/void lineage；
- 删除平台加密、key stream、HPKE envelope 和 root escrow；
- per-record/per-ack receipt 收敛为 batch checkpoint；
- lane id 从客户端 nonce/hash 改为 broker 分配的单调整数；
- stream settings 从链状态移动到 broker，并由治理 ceiling 约束；
- provider reassignment、slashing、CBFS archival 和其他 transport 明确推迟。

这些变化证明 V2 已经摆脱 V1 中最明显的机制堆叠。不过，剩余正文仍自行定义了一套接近
Kafka/SQS/NATS 规模的 broker：认证、session、flow control、group、lease、DLQ、
producer dedupe、checkpoint、retention、typed errors 和 canonical wire codec 全部由 CIP
重新设计。

## High：阻断项

### 1. Dedupe floor 可在合规执行下静默制造重复 append

位置：[§9.1](../../docs/cips/cip-39-cowboy-queue-system.md#91-idempotent-append)

`dedupe floor` 使用 broker 的 `received_at_ms`，而是否拒绝旧请求比较的是允许领先 broker
最多 `max_clock_skew_ms` 的 `client_created_at_ms`。容量淘汰又被明确允许在两个 deadline
之前发生。

默认参数下可构造完整反例：

1. 首次请求 A 在 broker 时间 `R` 到达，客户端时间戳为合法的 `R + 60,000`；
2. 请求 B 在 `R + 1` 到达；
3. broker 为释放容量删除 A，floor 推进到 B 的 `received_at_ms = R + 1`；
4. A 在 `R + 2` 重试；
5. A 的时间戳仍大于 floor，也仍满足 `client_created_at_ms <= received_at + skew`；
6. A 的 key 已被删除，broker 因而把它作为新消息再次提交。

这直接破坏 §9.1 和 §19 声称的“删除 dedupe key 后不静默提交 duplicate”。删除最后一条
entry 后 floor 本身也失去定义，但上述反例不依赖空 store。

### 2. Checkpoint 没有兑现 Goal 5 的可举证承诺

位置：[Goal](../../docs/cips/cip-39-cowboy-queue-system.md#goal)、
[§10](../../docs/cips/cip-39-cowboy-queue-system.md#10-durability-and-checkpoints)、
[§11.1](../../docs/cips/cip-39-cowboy-queue-system.md#111-frames)

`Appended` 只返回 `sequence`，checkpoint receipt 必须随后通过另一个 `GetCheckpoint` 请求
获取。如果 provider 在 append 已确认、客户端首次拉取 checkpoint 之前删除或拒绝提供
首个批次，客户端只持有未签名的 sequence：没有 provider signature、batch range 或 digest
可用于证明已确认数据丢失。首个批次也没有后继 checkpoint 可暴露链缺口。

原子 durable commit 和 receipt retention 只约束合规 broker，不能约束 checkpoint 本来要
审计的恶意 provider。因此“签名 provider commitment 使 acknowledged-data loss 可检测”
在 acknowledgement 时并不成立。

### 3. Create/Delete Group churn 绕过 active-group 上限

位置：[§9.2](../../docs/cips/cip-39-cowboy-queue-system.md#92-consumer-groups)

持有 `GROUP_ADMIN` 的付费 stream 可以不断使用新 `group_id` 执行 Create → Delete。任意时刻
active group 只有 0 或 1，所以不会触发 `max_groups_per_stream`；每次删除却产生一个保存至
`idempotency_horizon_ms` 的新墓碑。

规范没有 group create/delete rate、墓碑计数或墓碑 byte budget。`retained_bytes_limit`
仅覆盖 records 和 checkpoint receipts。即使非常保守地限制为每秒 100 次循环，默认一天
仍可产生 864 万个墓碑，最低约 415–691 MB/stream；最大七天 horizon 则达到数 GB。

### 4. ACKED/EXPIRED delivery cycle 没有回收边界

位置：[§9.2](../../docs/cips/cip-39-cowboy-queue-system.md#92-consumer-groups)、
[§12](../../docs/cips/cip-39-cowboy-queue-system.md#12-retention)

每条 record 对每个 applicable group 创建一个 cycle，Redrive 还会继续创建新 cycle。
`DEAD_LETTERED` 明确有 TTL 后的删除规则，但 `ACKED` 和 `EXPIRED` 没有任何回收时点。

- 永久保留：状态按 `records × groups + redrives` 无界增长；
- 回收：旧 lease 的响应会从 `DeliveryTerminal` 变为 `LeaseStale`，但转换时点未定义。

`retained_bytes_limit` 不覆盖这些状态，因而反驳了“provider durable footprint 由 per-stream
ceilings 完整约束”的声明。

### 5. Consumer Group 的 `Head` 起点未定义

位置：[GroupConfigV2](../../docs/cips/cip-39-cowboy-queue-system.md#92-consumer-groups)

Group 配置声明 `start = Head | At(sequence)`，但只定义了 `At` 的合法性。唯一明确的
`Head` 语义属于 Cursor subscription，且绑定 subscription-open；持久 Group 可以先创建，
之后由多个 subscription 连接，不能复用该定义。

诚实实现可以分别把 Group.Head 解释为 retention floor、group 创建时 tail、首次 subscription
时 tail 或创建后的第一条 record，导致不同的 delivery range 和 at-least-once 结果。

### 6. `Extend` 的 `max_visibility_ms` 缺少时间锚点

位置：[§9.2 Extend](../../docs/cips/cip-39-cowboy-queue-system.md#92-consumer-groups)

初始 lease expiry 明确是 `issued_at + visibility_timeout_ms`，但 Extend 只说不得超过
`max_visibility_ms`，没有说明这个 duration 相对 `issued_at`、当前时间、当前 expiry 还是最近
一次 Extend 计算。

相同的重复 Extend 序列在 issue-anchored 实现中会被拒绝，在 rolling-anchored 实现中可以
持续成功，直到 record deadline。相同合法请求因而产生不同 wire 结果。

### 7. Group 管理没有协议内读取闭环

位置：[§9.2](../../docs/cips/cip-39-cowboy-queue-system.md#92-consumer-groups)、
[§11.1 methods](../../docs/cips/cip-39-cowboy-queue-system.md#111-frames)

`UpdateGroup` 的请求体是完整 `GroupConfigV2`，并要求五个不可变字段与现存记录精确一致；
协议却没有 `GetGroup` 或 `ListGroups`，response union 也不返回 group config。

新获得 `GROUP_ADMIN` 的 holder 无法只凭 grant 知道现存的 `start`、`mode`、
`max_in_flight_per_holder` 等字段，因此无法确定构造一个可接受的 UpdateGroup。唯一办法是
依赖协议外保存和移交完整配置，这与“GROUP_ADMIN is full control”不一致。

### 8. 错误版本同时匹配两个稳定 wire error

位置：[§14](../../docs/cips/cip-39-cowboy-queue-system.md#14-typed-errors)

非 `2` 的 frame 或嵌套对象 version 同时满足：

- `MalformedFrame`：按 §4 canonical rules 解码失败；
- `UnsupportedVersion`：version byte 不是 `2`。

§14 没有把 version error 从 `MalformedFrame` 排除，还明确让 version refusal 与其他类别无序。
两个完全诚实的实现可对同一输入返回不同的稳定错误码。

### 9. §19 没有覆盖 §18 的关键 activation MUST

位置：[§18](../../docs/cips/cip-39-cowboy-queue-system.md#18-activation-and-removed-surface)、
[§19](../../docs/cips/cip-39-cowboy-queue-system.md#19-conformance)

§18 要求 closed-world genesis、`0x17` 无旧记录和余额、拒绝 V1 instruction/records、拒绝
缺少 `cbqs/store-format = 2` 的 broker store，并禁止携带 V1 chain/broker/archive state。
§19 的九组 conformance 条件没有完整覆盖这些要求。

现有 `cip-lint.py`、`cip-numbers.py`、V2 gas vectors 和 system-address invariant 可以全部
通过，同时 Node 继续使用 V1 decoder、V1 genesis keys 和 V1 store surface。当前 Node 仍是
V1 本身是 Draft 阶段的实现进度，不是单独缺陷；真正的问题是规范自称完整的 activation
gate 并不能证明这些边界已经满足。

## Medium：已确认问题

1. **自然超时耗尽 `max_attempts` 的终态未定义。** `max_attempts = 1` 时，首次 lease
   自然超时可以被解释为直接 `DEAD_LETTERED`，也可以先回队列再投递第二次。
2. **Grant skew 接纳与 session expiry 冲突。** Grant 在 raw `expires_at_ms` 后的 skew
   窗口仍通过时间校验，但 session termination 条件已经成立，可产生拒绝、瞬时打开或延迟
   终止三种解释。
3. **`DeleteGroup` 没有定义未决 lease/cycle 的原子处置。** 删除后 Ack 可以成功、返回
   `LeaseStale`、`GroupNotFound` 或 `DeliveryTerminal`；自然超时也没有可返回的 group。
4. **外部可观测例外清单不完整。** 文档宣称所有 normative requirement 都可从链状态、
   wire bytes 或 broker response 验证，且 §19 A–H 是穷尽例外；但 application durable-copy
   的 `MUST` 无法从这些表面验证，也未进入例外清单。

## 关于“优雅简化”的建议

### 1. 从核心 V2 删除 checkpoint，或让 receipt 与 append ack 原子交付

当前 v2 没有 dispute、stake 或 slash。Checkpoint 却引入 provider signing-key history、
receipt chain、receipt index、retention coupling、三种 verifier verdict、GetCheckpoint API 和
大量 conformance。文档已经用“没有可执行争议路径”为理由删除 lane proofs，同一原则也应
重新审视 checkpoint。

最简选择是把 checkpoint 整体移到后续 auditability CIP。若必须保留，完整签名 receipt
必须与每个受其覆盖的 append acknowledgement 原子交付，而不是事后 pull。

### 2. 从基础协议删除 producer dedupe

CBQS 已经明确是 at-least-once，应用也必须让消费 effect 幂等。Producer retry 产生 duplicate
与这一模型一致，不需要 broker 再提供近似 exactly-once append。

当前 dedupe 默认最小容量约 195 GB/stream，是默认 retained budget 的 182 倍；为了逃离该
容量又设计 floor 和提前淘汰，最终产生静默 duplicate。删除整个 dedupe store、两个 horizon、
floor、`IdempotencyConflict`/`Expired` 和相关 tombstone 逻辑，是比继续修补更干净的简化。

### 3. 压平 Group 和 lease 生命周期

建议形成一个单一、可测试的模型：

- `Head` 固定为 group 创建原子边界之后的第一条 sequence；
- Update 使用 patch，或者提供 GetGroup，二选一；
- DeleteGroup 原子失效全部 subscription/lease，之后统一返回 `LeaseStale`；
- terminal state 可在确定边界压缩或删除，不再长期区分 `DeliveryTerminal`；
- `max_visibility_ms` 固定锚定最初 `issued_at_ms`；
- timeout 和 Nack 使用同一个 attempt-exhaustion transition。

### 4. 把 `cbqsd` 收敛为链授权适配层

“Kafka/NATS/RabbitMQ 不能验证 StreamGrant”与“必须重新定义完整 broker”之间还有更简单的
方案：由薄的 chain-aware authorization/tenancy adapter 验证 StreamGrant，把持久化、消费组、
重试和 backpressure 映射到成熟 broker。

当前 rejected alternative 把选择写成“原样采用现有 broker”或“全部自行定义”的二选一，
这是假的二分。薄适配层才更符合 V2 希望达到的架构简化。

### 5. 让 provider 的协议权利与 trust model 一致

规范承认 provider 可以随时 censor、delay 或 destroy data，因此链上“付费客户不能被 provider
退出”并不提供真实可用性保护，只保留了 `assigned_streams`、`max_streams`、不可下调规则和
线下协商负担。

该问题经 prove 后不构成当前规范的自相矛盾，因为文档明确把它作为产品选择；但从简化目标看，
允许 provider 明确关闭服务并让应用迁移，反而更诚实，也可以删除一组虚假的容量保护状态。

## 被证伪或降级的假设

- **未 pin codec revision 导致 V1 也可能被当成 V2：证伪。** V2 object/envelope、signing
  domain 和 activation rejection 足以让旧 codec 明确不 conform；当前 Node 仍是 V1 是发布
  readiness debt，而不是规范允许的 byte ambiguity。
- **flat rent + provider 不可退出本身构成规范矛盾：证伪为 blocking finding。** 触发路径
  真实，但文档明确接受该经济取舍，并由 per-stream ceilings 和 `max_streams` 给出瞬时上限。
  它保留为产品与简化 advisory。

## 验证证据

- 风险分类：`high`，命中 `cross_repo_contract:sys-actor-addr`；
- 四个计划 lens 全部返回：`spec`、`correctness`、`econ`、
  `ratchet:cross-repo-contract`；
- 每条保留假设均由新的 prove agent 独立给出 `confirmed/refuted` 和触发路径；
- Marshal quorum：9 个 high escalated，4 个 medium confirmed；
- `scripts/cip-lint.py`：0 structural problems；
- `scripts/cip-numbers.py`：通过，V2 gas artifact 27 vectors、0 mismatch、SHA pinned；
- `git diff --check origin/main...HEAD`：通过；
- Node invariant `system_actors::tests::addresses_are_unique`：1 passed、0 failed；
- 审查过程为只读，没有修改 CIP 或实现代码。

Marshal run `31` 已记录 findings `23`–`35`。按 Marshal 的 human-verdict gate，这些 finding
仍等待人工标记为 `accepted`、`rejected` 或 `modified`，因此 run 保持 open；上述分析结论和
GateDecision 已完成。
