# CIP-33 Trading Post — 上线协调 Checklist(Marshal 四件套结论汇总)

> 配套文档:[`2026-06-14_cip-33-trading-post-explainer.md`](./2026-06-14_cip-33-trading-post-explainer.md)(机制/商业企图/时序图)
> 整理:2026-06-14 · 依据 Marshal 对四个 PR 的审计(gate run_ids 161/162/165/167)
> 全部判 **NEEDS_HUMAN**——**没有阻断性代码缺陷**,但这是**跨四仓的共识/安全激活机制**,必须协调上线。

---

## 0. 为什么四个 PR 必须一起看

CIP-33 = "actor 雇佣 + 分销 + 计费 + 解密垄断式版权保护",落地横跨四个独立仓库,彼此有**编译期 + 运行期 + 规格**依赖:

```
cowboy #180  (规格 CIP-33)            ── 规范来源,定义 9 MUST
      ▲
node #700    (Trading Post 系统actor) ── 钱账本 + /trading-post/lease-authorize 端点 + 0x1E
      ▲ 运行期(HTTP 端点)              + cip33 query 处理
      │
cbss #24     (CBSS lease authorizer)  ── cbssd 按 node 端点谓词决定是否发 DEK 份额
      ▲ 编译期(runner 的 Cargo 依赖)    + 给 release 请求体加 cip33 字段
      │
runner #113  (runner 侧 hire-lease)   ── 构造 cip33 请求 + job↔hire 绑定 + 两点租约执行
```

**依赖方向:** runner#113 →(编译)cbss#24 →(运行/HTTP)node#700;三者都 →(规范)cowboy#180。

---

## 1. 四个 PR 的 Marshal 结论速查

| PR | 角色 | head | 判决 | 关键结论 |
|----|------|------|------|----------|
| cowboy **#180** | 规格 | `3236666` | NEEDS_HUMAN | 规格良构;实现尚未满足 **3 条 MUST**(见 §3) |
| node **#700** | 实现 | `f701d26f` | NEEDS_HUMAN | **2 latent HIGH 已上棘轮**(见 §2)+ 2 MEDIUM DoS + econ 覆盖缺口;HIGH 因 `reserved` 生产从不充值而 dormant |
| cbss **#24** | 授权器 | `88d485af` | NEEDS_HUMAN | 授权器 **fail-closed、稳**;依赖未合并的 node#700 端点+cip33;线格向后兼容 |
| runner **#113** | runner 执行 | `38b4a99` | NEEDS_HUMAN | 执行 **fail-closed、纵深防御**;Cargo 依赖**指向未合并的 cbss#24 rev**(须 repoint) |

> 所有四个 PR 的安全/不变量门禁都通过(authorizer 与 runner 执行均 fail-closed;node 不变量与 cbss/runner 契约测试全绿;Almanax 各 0)。判决全是**协调性**,不是阻断性缺陷——唯二实质缺陷是 node#700 的两个 **latent**(休眠)HIGH。

---

## 2. 阻断项:node #700 的两个 latent HIGH(必须先解,已上棘轮)

二者目前 **dormant**——`hire.reserved` 在生产中**从不充值**(init 0,仅 `#[cfg(test)]` 赋非零),故 `SettlePerCall` fail-closed。**一旦实现"session open 把 reservation 移入 reserved"(规格 §2.5.1/§2.6.3 的 MUST),两 HIGH 即激活。**

- [ ] **HIGH-1 pay-then-fail**:`settle_per_call` 在可失败的 `prepaid.checked_sub` **之前**就 `apply_custody_payment`,投机引擎对 Err 不回滚 → 可致托管资不抵债。
  - 修:`apply_custody_payment` 前校验 `settled ≤ prepaid`,整体 fail-closed(规格 §2.4)。
  - 棘轮:`esc-20260614-tradingpost-settle-pay-then-fail` → **proptest `econ.trading_post_settle_conservation`**(待实现)。
- [ ] **HIGH-2 未签名 stub validator**:`Cip8PerCallReceiptValidatorStub` 无签名校验,信任攻击者提供的 `settled/released`;**无守卫**阻止 stub 状态下充值 reserved(规格 §2.6.3 要求 receipt 双方签名)。
  - 修:实现真·签名 receipt validator,**或**加硬守卫使 reserved 充值路径在 stub 仍在时无法上线。
  - 棘轮:`esc-20260614-tradingpost-percall-unsigned-stub` → **proptest `tp.percall_settle_fail_closed_under_stub`**(待实现)。

**铁律:在实现 `reserved` 充值路径之前,上面两条 proptest 必须先写实并绿。**

---

## 3. 规格↔实现缺口(cowboy #180 的 MUST vs node #700)

- [ ] **§2.6.3** receipt MUST 双方签名 → 实现是未签名 stub(= HIGH-2)。
- [ ] **§2.4** settlement MUST "fail closed as a whole" → 实现 pay-then-fail(= HIGH-1)。
- [ ] **§2.5.1/§2.6.3** session open MUST 把 reservation 移入 `reserved` → 实现尚未建该路径(= 两 HIGH 的激活前提)。
- [x] **§2.7** attestation 开放(any address may attest)= 规格本意 → 实现 ungated 符合;仅 `artifacts_by_store`/attest 索引**无界增长 + flat-cost 计量**是轻微实现 DoS(MEDIUM,见 §4)。
- [ ] **req-14**:policy check MUST 有 **live devnet e2e 测试**(cbss#24 已加 e2e harness;确认 node#700 的 lease-authorize 也被 e2e 覆盖)。

---

## 4. 次要项(MEDIUM / LOW,非阻断)

- [ ] node#700 `artifacts_by_store` 无界、`Attest` 索引无界 + flat-cost 计量 → cheap DoS(Almanax 也命中 storage.rs:289 MEDIUM)。建议按字节计量 + 加界/prune。
- [ ] cbss#24 ↔ node 线格**定义漂移**:cbss-client `ReleaseRequestBody` 有 `cip33`,node `types/src/cbss.rs` 无(`hire_id` 经 URL query 到 node,不在体内)。运行时良性,契约不变量抓不到 → 确认 node 有意不带。
- [ ] runner#113 `Cargo.toml` 把 `cbss-client/cbss-crypto/cbssd` 从 `tag v0.0.8` 改指 **rev `88d485af`(未合并 cbss#24 head)** → 合并前 **repoint 到 cbss main 的 merged rev**。

---

## 5. 建议上线顺序(原子升级)

> 共识相关:node#700 的新系统 actor 0x1E + opcodes + CIP-29 事件进 `receipt_root` → 与其他 receipt 影响型 PR 协调成一次验证者升级。

**合并顺序:**
1. [ ] **node #700** 先行——它是端点 + 类型 + 账本的来源。合并前:解决 §2 两 HIGH 或确保 reserved 充值路径**不随本 PR 上线**且两条棘轮 proptest 已绿;补 econ proptest;加 Consensus/coordinated-rollout 说明。
2. [ ] **cbss #24** 其次——需要 node#700 的 lease-authorize 端点;确保 cbss `main` 含 #24。
3. [ ] **runner #113** 最后——把 Cargo 依赖 repoint 到 cbss merged-main rev(不要留 PR-branch rev);需 node#700 已**部署**。
4. [ ] **cowboy #180** 规格作为规范参照随同落地;其 MUST 措辞须与实现状态一致(签名 receipt 等若仍是未来,规格应注明)。

**部署:** 必须原子——node(端点)先 live,否则 cbss/runner 的 tradingpost 路径**全部 fail-closed**(拒发密钥/拒执行 = 安全但功能不可用)。

---

## 6. 上线前最终验证 checklist

- [ ] node#700 两条棘轮 proptest(`econ.trading_post_settle_conservation`、`tp.percall_settle_fail_closed_under_stub`)已实现并绿。
- [ ] 若实现了 reserved 充值:HIGH-1/HIGH-2 已实修(`settled ≤ prepaid` 前置校验 + 真签名 validator)。
- [ ] live devnet e2e:hire→派工→lease-authorize→cbssd 发 DEK→runner 执行 全链路过(req-14)。
- [ ] 撤销/欠费 e2e:≤1 个 lease_epoch 内 cbssd 停发份额、runner 边界重检挡住 reveal。
- [ ] runner Cargo 依赖已 repoint 到 cbss merged-main;四仓版本互相对齐。
- [ ] node 线格类型(cbss.rs / runner types)与 cbss-client / runner-common 契约一致(`contract.cbss_wire_round_trip`、`contract.runner_types_serde` 绿)。

---

_本 checklist 由 Marshal 审计(gate run_ids 161=node#700 早期, 162=cowboy#180, 165=cbss#24, 167=runner#113;另两条棘轮 esc-20260614-tradingpost-*)汇总。各 PR 评论里有逐条证据。_
