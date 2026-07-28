# CBQS → CBSS 团队：释放路径问题清单

**背景**：CBQS 设计稿（`2026-07-27_cbqs-design.zh.md`）§1.4.4 第 4 点与 §1.15 #2 把「CBSS persistent-workload release path」列为需要与 CBSS 团队共同设计的扩展。审计（`2026-07-27_cbqs-design-review.zh.md` H2）判定：CBQS v1 最大的自建件（envelope 扇出）是这个缺口的 fallback，因此必须先确认缺口是否真的存在。

**核对结论：缺口不存在 —— 它已经被设计、审计、合并，然后被一个无关 PR 误删。** 详见 §0.1。

---

## 0 摘要

### 0.1 关键发现：CIP-24 §3.4.7 operator-principal 释放类已合并后被误删

| 事实 | 证据 |
|---|---|
| CIP-24 §3.4.7「operator-principal release class」于 2026-07-12 合并进 `cowboyinc/cowboy` main | PR#227，merge commit `d8a5d44`，+219/−2 于 `docs/cips/cip-24-secrets-manager.md`；Marshal 审计 run 548/550，fixup PR#228 已合并 |
| 该节在 `d8a5d44` 时确实存在 | `git show d8a5d44:docs/cips/cip-24-secrets-manager.md` → `3.4.7` 出现 11 次，文件 1888 行 |
| **当前 `origin/main` 完全没有该节** | `git show origin/main:…` → `3.4.7` 出现 **0** 次，`OperatorReleaseGrant` **0** 次，文件 1738 行 |
| 删除者是一个 Twilio 示例 PR | pickaxe `git log -S OperatorReleaseGrant` 只命中两个 commit：`d8a5d44`（加入）与 `5027a0c`（删除）。`5027a0c` = PR#242「feat(gallery): CIP-33 store-hireable Twilio two-way SMS actor…」，对 cip-24 做了 **+21/−226**，且 `5027a0c` 是 `d8a5d44` 的后代 → 陈旧分支覆盖，非有意撤销 |

**连带损伤**（同一 commit）：

- `cip-8-mpp-session.md`（−15）：删掉了 2026-07 的 spec↔code 更正。**当前 main 因此又带着一句已知为假的断言** —— 第 435 行仍写「MPP Session never claimed numeric opcodes」，而被删的更正明确指出「That is false in shipped code」（实际是 `SystemInstruction` 变体，opcode 52–57，见 `cowboy-protocol-codec/src/instruction.rs`）。这是一条尚未修复的活体规格漂移回归。
- `cip-31-cbfs-rent-schedule.md`（−27/+20）：费用分账被从 10/2/88 退回 10/1/89。后续 PR#274 独立确认 10/1/89 才是部署值 → **无实质损伤**（结果正确纯属巧合）。
- `cowboy-storage-whitepaper.md`（−2）、`cowboy-design-decisions.md`（±1）。

**同类事故已发生过**：`cc2ced0`「docs(cip-10): restore persistent workload specification」（PR#272，分支 `jw/cip10-workload-spec-repair`）就是同一失效模式的修复。这不是孤例，是 docs 仓库的复发性缺陷。

### 0.2 因此问题清单的问法变了

不是「请为我们新增一个 persistent-workload 释放模式」，而是：

1. **§3.4.7 恢复**是流程问题，不是设计问题（Q1）。
2. **一个委员会上已经长出五条互不相同的授权路径**，其中两条在 CIP-24 里没有规范位置（§1）。真正该问的是能否泛化（Q3）。
3. CBQS 有两条互斥的接入路线，选哪条决定 v1 是否需要 envelope 子系统（Q2 vs Q4）。这是唯一真正阻塞 CBQS 的决策。

---

## 1 事实基线：一个委员会，五条授权路径

所有路径共用同一个 CBSS 委员会、同一个 `MPK`、同一套 shares 与 PSS。差异只在**谁被允许触发释放、凭什么**。

| # | 路径 | 授权凭据 | 收件人 | CIP-24 中的规范位置 | 实现状态 |
|---|---|---|---|---|---|
| P1 | Actor / job-bound 机密释放 | `SecretPolicy.actors` ∩ manifest entitlement ∩ dispatcher job 指派 ∩ 抗重放（§3.7） | VRF 选中的 runner | §3.4.3（正文） | 已上链实现（`node/execution/src/cbss.rs`） |
| P2 | Time-lock 释放 | 仅高度门控，**无 ACL、无 job 绑定、permissionless** | 任何观察者（到点公开） | §3.4.6（2026-06-29 修正案，已合并） | 参考实现 TBD |
| P3 | **Operator-principal 释放** | 链上 `OperatorReleaseGrant` + `K_auth` 签名，**取代** job 指派 + manifest + ACL 三件套 | 发起者自己的常驻链下服务 | **§3.4.7 —— 已合并后被误删（见 §0.1）** | 参考实现未做（node `0x04` op154/155） |
| P4 | CIP-7 per-epoch content key seal | SKM（`0x0D`）链上 `StreamAccess` + `SealRequest`；**无 ACL、无 job 绑定、无 manifest** | 收件人的已注册 account X25519 key（`AccountKeyRegistration`） | **CIP-24 未收录为释放模式**（仅在 `MAX_IBE_AAD_BYTES` 注释里被提及「CIP-7 AADs are variable-length」） | **已实现**：`cbss/crates/cbssd/src/cip7_content_key_seal.rs`（739 行，含可插拔 `Cip7SealAuthorizer` trait + 链上授权查询）、`cbss-client/tests/cip7_vectors.rs`、`cbss-crypto/src/identity.rs`；node 侧 `stream_key_manager.rs` |
| P5 | CIP-9 volume-DEK seal at mount | node 构建 `SealRequest`；hold-until-key-delivery | 被指派的 runner | §9.3 / §11 有记载，非独立「释放类」 | 已实现 |

**观察**：P3 与 P4 解决的是同一类问题 —— **常驻的、非 job 绑定的主体需要机密密钥** —— 却各自长了一套授权凭据（grant + `K_auth` 签名 vs SKM 链上访问记录）。P4 甚至已经把授权抽成了 trait（`Cip7SealAuthorizer::authorize`），但没有被提升为规范概念。CBQS 若再长第六条，是可预见的重复。

---

## 2 给 CBSS 团队的问题

每条标注：**阻塞性**（是否阻塞 CBQS v1 范围决策）· **为什么问**（CBQS 哪个决定依赖它）。

### Q1 §3.4.7 的恢复 — 谁来做、走什么流程？

**阻塞：是（但是流程阻塞，非设计阻塞）**

§0.1 的事实：merged → 被无关 PR 覆盖 → 至今未恢复。CBQS 无法把设计建在一个「规格上不存在但历史上存在过」的节上。

- 恢复由谁发起 —— CBSS 团队（原作者）还是我们提 restore PR（照 PR#272 `jw/cip10-workload-spec-repair` 的先例）？
- 恢复时是否顺便处理 PR#228 留下的治理岔路？该 fixup 就 F1（in-body 1-byte arm discriminant 是否也要加到 runner 侧 `release_request_signing_bytes` / `release_id`）留了 option (a) 向后兼容 / option (b) 显式 flag-day 两个选项给作者定夺，我们当时刻意不替裁。恢复 PR 需要带上这个未决项还是先按 option (a) 落地？
- **顺带**：同一 commit 也让 CIP-8 带回了一句已知为假的 opcode 断言（§0.1），是否一并修？这不属于 CBSS 范围，但属于同一次事故。

### Q2 §3.4.7 能否直接服务 CBQS 的 rotation authority？

**阻塞：是**

CBQS 的 rotation authority = stream owner 的常驻轮换工作负载，需要拿到该 stream 的根密钥来派发下一代。这与 §3.4.7 的动机逐字吻合：「常驻链下服务握长寿签名金鑰，既非 dispatcher-assigned runner，又非公开 tlock 消费者」。

- §3.4.7 草案明写 `OperatorReleaseGrant` 是 **same-account only**（`secret_id.account` MUST 等于 grant 发起者）。CBQS 的 rotation workload 由 stream owner 自己运营、读 owner 自己的秘密 → **同账户，约束成立**。这个理解对吗？
- 三金钥分离（`K_root` 冷 / `K_auth` 暖 / `K_sign` 被托管）映射到 CBQS：`K_sign` = stream 根密钥（或每代密钥）。**但 CBQS 的用法与 §3.4.7 的原始设想不同** —— §3.4.7 假设 `K_sign` 是瞬时重建后立即签名；CBQS 的轮换工作负载拿到根密钥后要做 N 次 HPKE 封装。这个使用模式是否仍在 §3.4.7 的威胁模型内，还是需要补一条？
- 撤销语义：§3.4.7 的撤销 = **未来释放 cut-off + 有界完整释放宽限窗**，非 retroactive seal。CBQS 移除成员时依赖的是「提升 generation 后旧 producer 写不进新代」，两者是否有冲突？

### Q3 五条授权路径是否应泛化为一个 authorizer 接口？

**阻塞：否（但决定 CBQS 该提交什么形态的变更）**

P4 已经在 cbssd 里把授权抽成了 `Cip7SealAuthorizer` trait（`authorize(seal_request_id, request) -> Cip7SealAuthorization`，含 committee-epoch 与 release-key scope 校验、链上查询失败显式建模）。

- 这个 trait 是有意的通用扩展点，还是 CIP-7 专用？
- 若通用：CBQS 应该实现一个 `CbqsSealAuthorizer`（读 CBQS stream record 的 generation + 成员集合），还是复用 P3 的 grant 路径？
- 若要泛化，CIP-24 是否愿意接受一节「释放授权类清点」把 P1–P5 收进同一张表？**现状是 P4 在规格上无家可归**，任何人想理解「CBSS 一共能被谁触发」都必须读三个 CIP 加代码。

### Q4 CBQS 能否直接复用 P4（CIP-7 content-key seal），从而完全不需要新释放模式？

**阻塞：是 —— 这是决定 CBQS v1 范围的单一最大问题**

CIP-7 ↔ CBQS 对照表（`2026-07-27_cbqs-vs-cip7-comparison.zh.md` R2）建议 CBQS 复用 `0x0D` 的 `AccountKeyRegistration` 作为成员 HPKE 收件人身份。若同时复用 P4 的释放路径，则：

- 100 人房间 = 100 个账户各一把已注册 X25519 key，扇出由 CBSS 委员会承担（与 CIP-7 明写支持的 10,000 订阅者路径同构）；
- **CBQS 的 envelope 子系统、companion key stream、per-member HPKE 双密钥、三步轮换状态机整套从 v1 消失**（审计 H2 消解）。

需要 CBSS 团队判断的是：

1. P4 的授权面（`Cip7SealAuthorizer`）能否接受一个非 SKM 的授权源（CBQS stream record + generation），还是它硬绑 `0x0D` 的 `StreamAccess`？
2. P4 的扇出成本模型：CIP-7 是「一个 epoch 一个 `WrappedContentKey` 行 + 每买家每 epoch 一个 SealRequest」。CBQS 若 100 成员 × 每代，是 100 个 SealRequest / 代。这与 CIP-7 的 10,000 订阅者宣称是同一量级还是不同？`MAX_EPOCHS_PER_ACQUIRE = 256` 之类的上限如何映射？
3. P4 是 subscriber-paid 语义（买家自己付费触发 SealRequest）；CBQS 是 owner-paid。谁触发释放、谁付费，在 P4 的实现里是否可分离？

**这三问的答案决定 CBQS v1 是「复用 P4，砍掉 envelope」还是「走 P3，自建 envelope」。** 在拿到答案前，CBQS 不应开始实现 §1.4.4。

### Q5 释放延迟与轮换 SLO

**阻塞：否（但决定验收测试能否通过）**

CBQS 的验收测试第一项是 100 人聊天室，成员进出触发轮换。已知数字：CIP-7 报「典型 4–5 块」端到端，上限 `REQUEST_FRESHNESS_BLOCKS = 384`；CIP-24 §3.7 校验在 **current head** 做，ACL 在请求块允许但提交前被撤销会导致 receipt 被拒（proxy 白干一次）。

- 一次轮换（取 generation N+1）的现实延迟分布是多少？p50 / p99？
- 成员移除的紧急性与这个延迟的冲突如何处理 —— 有无「先切授权、后换密钥」的建议序列？（CBQS §1.4.4 的三步状态机把提升 authorization generation 与 encryption generation 分开，正是为此，但没有给延迟预算。）
- 高频轮换是否会撞 `MAX_RELEASES_PER_ACTOR_PER_HOUR` 或 `MAX_RELEASE_OVERDRAFT`？CBQS 的 rotation workload 不是 actor，这些配额如何适用？

### Q6 CBSS 降级行为

**阻塞：否**

CBQS §1.15 #2 直接问了这条：「CBSS 降级行为（cached keys？grace generations？）」。

- 委员会不可用时（< t 个 proxy 响应），CBQS 的正确姿态是什么 —— 拒绝新成员加入但保持现有 stream 可读（cached key），还是 fail-closed？
- 是否存在官方推荐的 grace 语义，或这属于消费者自决？（对比 CIP-34 sealed-bid 的做法：CIP-34 自己拥有 liveness fallback `AUCTION_GRACE`，CBSS 不提供。）

### Q7 委员会 epoch / reshare 与 CBQS generation 的交互

**阻塞：否（但是共识安全类风险）**

CBSS 有 `committee_epoch`、`wrap_epoch`、`quorum_epoch` 三个 epoch 概念，且有硬性单-epoch quorum 规则（跨 epoch 组合 Lagrange 会得到错误 σ → `MixedEpochReceipts`）。CIP-7 把 `committee_epoch` 绑进了 `WrappedDek.aad`，并要求 `register_content_keys` 时校验 `committee_epoch` 与当前一致（否则 `COMMITTEE_EPOCH_MISMATCH`）。

- CBQS 的 encryption-key generation 必须绑 `committee_epoch` 吗？（看起来必须，否则 reshare 会让已发布的 envelope 不可解。）
- reshare 发生在 CBQS 三步轮换的步骤之间会怎样？CBQS 声称「停在步骤之间也是安全的」，但如果步骤 (1) 取到的 N+1 绑在旧 committee_epoch 上，步骤 (3) 之后是否仍可解？
- P3（operator-principal）的 `release_id` 曾漏 `serve_epoch`，PR#228 的 F2 就是修这条（跨 reshare 重用 nonce → 撞旧 `quorum_epoch` → `MixedEpochReceipts` 卡死）。CBQS 若走 P3，是否会踩同一个坑？

### Q8 `MAX_ACL_ACTORS = 64` 是否需要动？

**阻塞：否**

审计已确认这是 §4.5 治理参数、且 ACL 是 runtime gate 不是密码学收件人清单（`wrapped_dek` 是 O(1)、改 ACL 零 re-wrap）。CBQS 设计稿把它当成结构性墙，是论据错位。

- 若 CBQS 走 P3 或 P4，`MAX_ACL_ACTORS` 完全不参与，对吗？（我们的理解：P3 由 grant 取代 ACL，P4 由 SKM 访问记录取代 ACL，两条都不消耗 ACL 条目。）
- 若某个混合方案仍要用 actor ACL，把 64 调到 256 的实际成本是什么（存储、校验、gas）？我们**不倾向**走这条，只想确认它不是唯一出路。

### Q9 `tee_required` 与威胁模型边界

**阻塞：否**

§3.4.7 的诚实限制是：消除明文静态存储 + 可撤销 + 门槛 + 审计，但**不**消除瞬时重建（签名瞬间密钥在服务内存），除非 `tee_required`（依赖 §9.5.1 的 `0x05` grant-scoped attestation companion，跨仓依赖，尚未落地）。

- CBQS 的 rotation workload 是同一个姿态（轮换瞬间根密钥在内存）。这一点是否需要在 CBQS 的信任姿态章节显式声明，还是可以引用 §3.4.7 §8.9？
- `0x05` TEE companion 的时间表是否会成为 CBQS 的依赖，或 CBQS 可以在 non-TEE 下先上？

---

## 3 依赖矩阵：哪条答案改变 CBQS 的哪个决定

| 问题 | 若答案是 A | 若答案是 B |
|---|---|---|
| **Q4**（复用 P4？） | 复用 → **v1 删除 envelope 子系统 + companion key stream + 双密钥 + 三步轮换**；审计 H2 消解、M1 闭合；成员密钥改走 `0x0D` 注册表 | 不可复用 → 走 P3，保留 envelope，但 §1.4.4 应改写为「基于 §3.4.7 grant 的轮换授权」，不再自创授权面 |
| **Q2**（§3.4.7 适用？） | 适用 → CBQS 的 CBSS 集成缩成「注册一个 `OperatorReleaseGrant`」，§1.15 #2 大部分关闭 | 不适用 → 才需要真正的新释放模式，此时应作为 CIP-24 修正案提出（而非 CBQS 私有机制） |
| **Q1**（§3.4.7 恢复） | CBSS 团队恢复 → 我们只需引用 | 我们恢复 → 我们提 restore PR，并带上 PR#228 的 F1 未决项 |
| **Q3**（泛化 authorizer） | 泛化 → CBQS 提交一个 `CbqsSealAuthorizer` 实现 | 不泛化 → CBQS 沿用 P3 的 grant，接受五条路径继续并存 |
| **Q5**（延迟） | p99 可接受 → 100 人房间验收可跑 | 不可接受 → 成员移除需要「先切授权后换密钥」，且 CBQS 必须给出显式延迟预算 |
| **Q7**（epoch 交互） | 需绑 `committee_epoch` → CBQS generation 定义要改（多一个字段） | 无需 → 现状 OK（但我们倾向必须绑，请确认） |

**排序建议**：Q4 → Q2 → Q1 是关键路径，其余可并行。Q4 一个答案就能决定 v1 是否砍掉一整个子系统，值得优先安排一次同步会议而不是异步往返。

---

## 4 附：本次核对暴露的流程问题（非 CBSS 范围，但建议提出）

`cowboyinc/cowboy` docs 仓库出现了至少两次「陈旧分支覆盖已合并规格修正案」：

- PR#242（Twilio 示例）覆盖 CIP-24 §3.4.7（本文 §0.1），**至今未修复**；同 commit 让 CIP-8 带回一句已知为假的 opcode 断言。
- CIP-10 persistent workloads 曾遭同类损失，由 PR#272 `jw/cip10-workload-spec-repair` 修复。

两次都是「示例/无关变更的 PR 携带 spec 文件的陈旧版本」。建议护栏（任选其一即可大幅降低复发率）：

1. **CODEOWNERS**：`docs/cips/**` 与 `docs/whitepaper/**` 要求规格 owner 审批，示例目录的变更不得顺带修改这两个路径。
2. **CI 检查**：PR 若同时改动 `examples/**` 与 `docs/cips/**`，标记并要求显式确认。
3. **行数回归门禁**：任何使 `docs/cips/*.md` 净减少超过 N 行的 PR 需在描述中说明删除理由（本例是 −226 行无说明）。
4. **合并前 rebase 强制**：陈旧分支覆盖的根因是 merge 而非 rebase；对 `docs/**` 要求 up-to-date branch。

这条建议应走治理渠道（CIP-12 / 仓库管理），不属于 CBSS 团队职责，但事故是在核对 CBSS 释放路径时才被发现的，因此记录在此。

---

_核对人：Marshal 认知回路。一手源：`cowboyinc/cowboy` origin/main（已 `git fetch`）+ PR#227/#228/#242 的 GitHub 元数据 + `git log -S` pickaxe + `cbss/crates/cbssd/src/cip7_content_key_seal.rs` + `node/execution/src/stream_key_manager.rs` + `refs/analysis/2026-07-06-cip24-operator-principal-release-amendment-draft.md`。建议态，非阻断。_
