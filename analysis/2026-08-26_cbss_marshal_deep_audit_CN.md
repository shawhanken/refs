# CBSS 全仓安全面深审报告(Marshal 流 A-deep)

**审计对象**:`cowboyinc/cbss` @ `origin/devnet` `0e52d3995b730cf5b6bad914e693324e3e91c3c5`
**审计日期**:2026-08-26
**方法**:Marshal 流 A-deep(闭包 → 多 lens 假说枚举 → 逐假说证真/证伪)+ 自建变异表
**判决**:**`escalate`** —— 建议态,不阻断任何 merge
**落库**:`review_run` **35**(status `degraded`)· `gate_decision` run **1373**

| 项 | 值 |
|---|---|
| 分级 | `high` |
| 命中契约 | `cip24-cbss`(repos = cbss + node) |
| 命中 hazard | `cbss-mpk-rpc-exposure`(review-only,`invariant_able: false`) |
| 子系统范围 | 门限密码 / 链上授权 / 释放编排 / 外部输入边界 |
| lens 计划 / 返回 | 12 / 12(完整性闸通过) |
| prove 派发 / 确认 / 证伪 | 6 / 3 / 3 |
| 聚合结果 | 6 escalate · 5 advisory · 2 weak |
| 规模 | 4 crates / 45.7k 行 Rust |

> **姊妹文档**:本文是**流程域**报告(门禁判决、不变量状态、lens 完整性、降级披露、复现指引)。
> 按**安全域**组织的分析 —— 威胁模型、信任边界、攻击面、按被破坏安全属性分类的发现、
> 系统性根因、修复路线图 —— 见 [`2026-08-26_cbss_security_audit_CN.md`](2026-08-26_cbss_security_audit_CN.md)。

> **完整性闸备注**:最慢返回的 lens(`release-orch::correctness`,624 秒)载着头条级发现。
> 若按「先回 N 个就出判决」,会系统性漏掉它。这条纪律在本次得到实证。

---

## 一、执行摘要

### 三条 CONFIRMED(均带实测触发)

| ID | 标题 | 严重度 | 位置 |
|---|---|---|---|
| **F-CRIT-1** | reshare 从线上载荷取多项式次数,一个裸旧法定人数可把 t-of-n 静默塌成 1-of-n | **CRITICAL** | `cbss-crypto/src/reshare.rs:237` |
| **F-CRIT-2** | `SignedReleaseRequest` 是可转让持有者凭证且被收据原样重发上链,观察者可从未服务过的 proxy 收割剩余 partial | **HIGH** | `cbssd/src/partial_sign.rs:389` |
| **F-SPEC-1** | CIP-24 强制把原始 σ_i 上链,与其自身 §3.4.6 / §8.4 的机密性主张矛盾 | **HIGH**(条件性 CRITICAL) | `cbssd/src/receipt_submitter.rs:130` |

### 门禁自身的缺陷

| ID | 标题 | 严重度 |
|---|---|---|
| **F-GATE-1** | `contract.cbss_wire_round_trip` 是幽灵闸,且是契约 `cip24-cbss` 的**唯一**跨仓检查 | HIGH |
| **F-GATE-2** | `crypto.cbss_ibe_roundtrip` 结构性不可选中 | HIGH |
| **F-GATE-4** | `authorize()` 八道守卫中四道零覆盖 | HIGH |
| **F-GATE-3** | cbss 完全没配 Almanax | MEDIUM |

### 其余 advisory / latent

`F-SPEC-2`(去重键违背规格)· `F-TEST-1`(adversarial 套件恒真式)· `F-CONF-2`(两个拒绝原因指标恒为零)· `F-RUNNER-1`(runner 信任根经未校验 transport)· `F-CONF-1`(IPv6 SSRF 谓词死代码,潜伏)· `F-LATENT-1`(rotate 签名前像非单射,潜伏)· `release_id` 前像与 CIP-24 §3.5 偏离

---

## 二、CONFIRMED 发现

### F-CRIT-1 · reshare 门限降级(CRITICAL,生产可达,实测)

**机制**

```rust
// crates/cbss-crypto/src/reshare.rs:234-240
let first = payloads.first().ok_or(Error::InvalidThreshold)?;
let old_signer_indexes = first.old_signer_indexes.clone();
let new_participants  = first.new_participants.clone();
let threshold_u8      = first.threshold;        // ← 新多项式次数来自线上载荷
validate_threshold(threshold_u8, new_participants.len())?;

// crates/cbss-crypto/src/dkg.rs:324-329
fn validate_threshold(threshold: u8, participants: usize) -> Result<(), Error> {
    if threshold == 0 || participants == 0 || threshold as usize > participants {
        return Err(Error::InvalidThreshold);
    }
    Ok(())                                       // ← 只有 1 ≤ t ≤ n,无下限,不比对链上门限
}
```

生产入口 `ReshareCoordinator::finalize_encrypted`(`reshare.rs:304-316`,**未 cfg-gate**)由
`cbssd/src/orchestrator.rs:1626` 调用。链上声明的门限 `state.threshold` 在 finalize 时**就在手边**
(`orchestrator.rs:1594-1642`,经 `ReshareRequestedEventData` 到达),只是从来没被读取。
mpk 保全检查(`reshare.rs:293`)与多项式次数无关,结构上挡不住这个。

**共谋前提不是额外的**:`node/execution/src/cbss.rs:5143` 的
`let old_signer_count = material.threshold as usize;` 让链**恰好点名 t 个旧签名者**当 dealer ——
这 t 个按定义本来就持有 MSK。`reshare.rs:262` 要求所有被点名 dealer 一致,故单个流氓 dealer 只造成 DoS。

**实测(四探针,含对照组;探针档已删除,worktree 已还原)**

| 探针 | 线上门限 | 结果 |
|---|---|---|
| A | `1` | ACCEPTED;`vss_len=1`;本地索引 1/2/3 的 `share_scalar` **全等于 MSK** |
| B | `2`,高次系数填 G2 identity | ACCEPTED;`vss_len=2`;share **全等于 MSK**;`[mpk, identity]` **通过链上校验 ⇒ rotation 落链** |
| C(对照) | `2` 诚实 | ACCEPTED;share ≠ MSK(证明探针非恒真式) |
| D | — | `public_share_from_commitments([mpk,id,id], i) == mpk`(i=1,2,3) |

**探针 B 为何是要害** —— 探针 A 的裸 t=1 会被链上挡下,但**只被一道长度检查**挡下:

```rust
// node/execution/src/cbss.rs:5875-5889  (已在 origin/devnet 逐字复核)
if threshold == 0
    || vss_commitments.len() < threshold as usize
    || vss_commitments.first() != Some(mpk)
{ return Err(ExecutionError::InvalidData); }
let mpk_point = g2_from_bytes(mpk)?;
if mpk_point == G2Projective::identity() { return Err(ExecutionError::InvalidData); }
for commitment in vss_commitments { let _ = g2_from_bytes(commitment)?; }   // ← 不拒 identity
```

`g2_from_bytes` 不拒绝 G2 identity;唯一的 identity 守卫(node `cbss.rs:7310`)查的是**求值后**的
`S_i`,而此处它恰好等于 mpk。所以 `[mpk, identity]` 在 t=2 下满足每一条。

**后果**:链上记录 threshold=2,而**任何单个**新委员会 proxy 持有 MSK,可独自解密该账户全部密钥,
永久有效。探针 D 显示每个 proxy 的 partial 仍能对已发布承诺验证通过、`combine_partials` 仍返回正确 σ
⇒ **零可观测异常**。且它能挺过之后所有诚实 reshare(每次都保全 mpk,而每个 dealer 的
`λ_i · S_old(i)` 都源自一个已经等于 MSK 的 share)。

**⚠️ 修法必须给机制,不能给极性**

只加 `if first.threshold != expected { reject }` 会关掉探针 A,**放探针 B 大摇大摆过去**。需要:

1. `finalize_plaintext` / `finalize_encrypted` 收 `expected_threshold`(来自 `state.threshold`)并比对;**且**
2. 拒绝任何非常数项承诺为 G2 identity 的 dealer —— 等价于要求聚合后的 `vss_commitments_g2[1..]`
   不含 identity 点。`for_dealer` 采样 `(1..threshold)` 个随机系数,诚实 dealer 命中 identity 的概率可忽略;**且**
3. node 侧 `validate_release_key_material` 补同一道 identity 检查 —— 它还顺带覆盖初始 DKG 路径。

`dkg.rs` 的 `finalize_qualified` 有同形状的线上门限洞,但该路径在 cbssd 里整条 `#[cfg(test)]`
(已单独证明)。若将来重新启用,一并修。

**未裁定的邻接风险**:`t_wire > t_chain` 同样通过长度检查,后果是**砖化**而非泄露。需另开探针。

---

### F-CRIT-2 · 释放请求是可转让持有者凭证(HIGH,实跑证明)

**实跑证明**(两个探针跑的是**生产型别**;补丁存于产物目录):

- `probe_replayed_request_authorizes_at_a_proxy_that_never_served` —— 真 `HttpChainReleaseAuthorizer`
  + wiremock node,2 人委员会:proxy A 授权(proxy_index 1),随后**同一份序列化往返后的请求**
  在 proxy B 上照样授权(proxy_index 2)。
- `probe_same_signed_request_yields_partials_from_two_distinct_proxies` —— 真 `PartialSignService`、
  真 DKG share、两个独立 store:proxy 1 服务;proxy 1 拒绝自己的第二次(`ReplayedRequest`);
  proxy 2 用**同样的字节**服务并返回另一个有效 σ_i。

`test result: ok. 2 passed; 0 failed`

**结构性原因**

- 签名前像(`cbss-client/src/types.rs:234-262`,委派给 `cowboy-protocol-cbss-crypto` 的规范布局)
  字段为:chain_id, secret_account, secret_key_hash, version, actor, runner_id, recipient,
  job_id, release_nonce, request_block, serve_epoch, cip33_hire_id
  —— **无 proxy_id、无 partial 收件人、无 per-proxy nonce**。
- 线上请求 `PartialSignRequest { version_byte, request }`(`protocol.rs:55-58`)**不携带任何呼叫方身份**。
- QUIC 监听器 `.with_no_client_auth()`(`tls.rs:113`);入站仅有 per-IP 连接数上限,无委员会白名单。
  (`SpkiPinnedServerVerifier` 是**客户端**校验器,不闸入站。)
- `authorize()` 每一道闸都是**请求本身**或 **proxy 自己**的性质。`verify_runner_signature`
  认证的是字节的**作者**,不是**出示者** —— 签名就在被重放的字节里。
- 重放守卫是 **per-proxy 持久**的(`ServedRequests`,`partial_sign.rs:81-152`),从未服务过的 proxy 没有记录。
- 唯一的委员会级去重在**收据**路径(node `cbss.rs:1321-1336` / `1444-1446`),而
  `submit_system_instruction` 在 `/submit` 返回 tx hash 时即返回 —— **仅入 mempool**,
  执行层的 `QuorumAlreadyReached` 永远到不了 proxy,也就拦不住 σ_i 被写回 QUIC 流。

**观察者需驱动的 proxy 数** = `t − k`(k = 链上已可读的 partial 数)。新鲜度窗口
`REQUEST_FRESHNESS_BLOCKS = 384`(≈6.4 分);收据抖动最多 10 × 250 ms,几乎整个窗口都还在。
**观察者不需要任何链下信息。**

**规格层证据**:CIP-24 §3.4.5 item 2 明确**放弃**了本可挡住此攻击的收件人绑定 ——
理由是「proxy 侧 anti-replay/ACL 已经提供足够保障」。而那个 anti-replay 是 per-proxy 的。

**诚实的边界**

- 每次收割都迫使被驱动的 proxy **先广播一笔收据交易** —— 这会向受害 actor 计费
  (node `cbss.rs:1448-1450`)并留下响亮的链上痕迹。**这不是隐蔽收割**。
- 对一次已正常完成的释放,F-SPEC-1 已经把 t 个 partial 放上链了,此处边际泄露为零。

**真正的升级点(两条,都成立)**

1. 观察者可以把一次**止步于法定人数之前**的释放(runner 崩溃、被分区、或在一个 proxy 应答后放弃拉取)
   仅凭链上公开数据驱动到法定人数 —— 这是现有设计本应不可能的事。
2. 它是**独立路径**,能挺过对 F-SPEC-1 的显然修法:把 σ_i 从收据里删掉**关不掉它**,
   因为收据仍在重新发布那张凭证。

**修法**:必须**移除或哈希收据中的 `runner_request`**,**并且**给释放请求绑定收件人。
同仓一路之隔就有现成范式 —— CIP-9 在请求里放链上锚定的 `runner_x25519_pubkey`
并把 partial HPKE 封装给它(`cip9_volume_seal.rs:284-289`,收件人密钥锚定于 `:97`)。

---

### F-SPEC-1 · 规格强制公开 σ_i,与自身机密性主张矛盾(HIGH,条件性 CRITICAL)

**这不是代码缺陷。** `receipt_submitter.rs:129-167` 是 CIP-24 §3.5 的忠实实现。矛盾在规格内部。

强制公开的一侧:

> §3.5(opcode 76):「The receipt **carries the runner's original signed release request verbatim
> AND the proxy's BLS partial signature `σ_i`**. The chain re-derives the request hash, verifies
> the runner's signature, and verifies the BLS pairing equation `e(σ_i, G2_gen) == e(I, S_i)`」
> §10.8:「…accumulates the full t-of-n proof of release on chain, each entry carrying the verbatim
> runner-signed request and the verified `σ_i`.」

主张相反性质的一侧:

> §3.4.6 模式表:「| Who may obtain `σ` | **the authorized runner only** | anyone (public) |」(左列 = 账户密钥释放)
> §3.4.6 规则:「**A tlock identity MUST NOT be used to wrap an account secret**(its key is public
> at `target_height`);the domain tag enforces this structurally, not by policy.」
> §8.4 验证者可见清单:「`wrapped_dek`(… unrecoverable without σ …)… **NOT DEKs**, NOT shares.」
> §3.8 step 12:「Runner R zeroizes plaintext, DEK, **σ partials**」—— 紧接着 step 13 就是 t 个 proxy 把同样的 partial 发上链。
> §3.5(opcode 153)反向印证:「No per-proxy receipt/audit record is written (unlike
> `SubmitReleaseReceipt`): time-lock release is public, so there is no access to audit.」

**触发(每一步都未认证)**

1. `GET /cbss/secret/{account}/{key_hash}?version=v`(node `rpc/src/routes.rs:385`,`ReadLocal`)
   → `wrapped_dek{ciphertext, nonce, ephemeral_u, aad}` + `release_key` + `cbfs_pointer`
2. `GET /state/0x04/{hex("release_receipt:"+release_id)}`(`routes.rs:557`)或 `GET /transaction/{hash}`
   (`routes.rs:325`)或直接读区块体 → `ReleaseReceiptSet`,恰好 `threshold` 条原始 48 字节压缩 G1
   (node `cbss.rs:1314-1318` 构造;`:1444-1452` 以 `release_key.threshold` 封顶 —— 正好是 Lagrange 门限)
3. `proxy_index = position(proxy_id in release_key.committee) + 1` —— 链自己就是这样推的(node `cbss.rs:1385-1390`)
4. 喂给**本仓自己发布的库函数** `cbss_client::verify_combine_and_decrypt`
   (`combiner.rs:55-71`)—— 五个参数全是链上公开量 —— 返回 DEK。
   已实跑本仓自带测试:`cargo test -p cbss-client --lib combiner`
   → `verify_combine_and_decrypt_recovers_wrapped_dek ... ok`(3 passed)
5. 唯一的链下步骤:取 `cbfs_pointer.uri` 的对象并用还原出的 DEK + 172 字节 base_aad 做 AES-GCM 解密。

**同族的不对称(说明这个选择很可能未经推敲)**

| 路径 | σ_i 上链前是否封装 |
|---|---|
| CIP-7 `cip7_content_key_seal.rs:270-290` | **HPKE 封装**;`Cip7PartialDelivery` 无 σ_i 字段 |
| CIP-9 `cip9_volume_seal.rs:266-290`、`cip9_service_volume_seal.rs:370` | **HPKE 封装** |
| 账户密钥 `receipt_submitter.rs:130-167` | **原始明文** |

**爆炸半径(精确)** —— **一个 secret-version**。σ = MSK·I,而
`I = hash_to_G1(u64_be(chain_id) ‖ account(20) ‖ key_hash(32) ‖ u64_le(version) ‖ u64_le(wrap_epoch) ‖ mpk_g2(96), "cbss/ibe/v1")`,
**不含** release_nonce / job_id / actor / release_id。所以:

- 还原 σ **不会**还原 MSK(§3.4.4 明确说明);
- 但同一 `(secret_id, version)` 的**每一次**释放都产生逐字节相同的 σ_i ⇒ 一次泄露覆盖该版本**永久**;
- §3.4.4:「Reshare does **NOT** invalidate σ values for prior identities; PSS preserves `MSK`」
  ⇒ ACL 编辑、移除 actor、注销 runner、reshare **全都撤不回**。唯一撤销手段 `force_rekey` 会让全部密文变砖。

**为何定 HIGH 而非 CRITICAL,以及确切的升级条件**

纯链上观察者拿到的是 **DEK 而非明文**:§3.4.3 step 5 把 `AES-GCM(DEK, plaintext)` 放在 CIP-9
**私有** CBFS 卷里,而该卷自己的 volume-DEK 走的正是**做了封装**的 CIP-9 路径。还剩一层。

> ⚠️ **留给人裁的未决依赖**:若链上观察者能读到 CBFS 私有卷对象,本条即升为**完整明文击穿(CRITICAL)**。
> 这压在 cbfs 授权绕过集群 **COW-2285 / COW-2300 / COW-2301** 上。
> **本次审计未测试 CBFS 可达性,不做任何断言。** 分诊 F-SPEC-1 的人必须先把这件事定下来。

**修法形状(分诊参考,未实现)**

不能只改 `receipt_submitter.rs` —— §3.5 step 8 的服务证明**就是**配对检查
`e(σ_i, G2_gen) == e(I, S_i)`,它需要明文 σ_i 在链上。需要规格修正案:改为 σ_i 的知识证明,
或把 σ_i HPKE 封装给 runner 并附上「封装内含有效 partial」的证明。
连带需要重新设计的明文 partial 消费方:

- `InvalidPartialReencryptEvidence`(`receipt_submitter.rs:70`)
- 等价物罚没路径(node `cbss.rs:5988-6224`,它会比较并排序两个 `sigma_i`)

---

### F-SPEC-2 · 反重放键用了规格点名禁止的那个值(HIGH)

**规格原文**(`cowboy/docs/cips/cip-24-secrets-manager.md:1084`):

> | Anti-replay: `(release_id, proxy_id)` not previously served | proxy local bloom (24h) + chain
> `release_receipt`(dedup is on `release_id`, the stable per-(secret, version, actor, runner, job)
> tuple — **`request_hash` is fresh per `request_block` and is NOT used for dedup**) |

**代码**(`cbssd/src/partial_sign.rs:389-401`):

```rust
let request_key: [u8; 32] = release_request_hash(&request.request.body)?  // ← 正是被禁止的那个键
    .as_bytes().try_into().expect("release request hash is 32 bytes");
let reservation = ServedRequests::reserve(
    &self.served, request_key,
    request.request.body.request_block.saturating_add(REQUEST_FRESHNESS_BLOCKS))?;
```

留存窗口 384 块(≈6.4 分)而非规格要求的 **24 小时 bloom**;授权路径上**不存在**任何对链上
`release_receipt` 的读取(规格把它列为去重的另一半)。

**为何要紧 —— σ_i 与 nonce 无关**(`partial_sign.rs:455-464`):被签名的
`IdentityInput { chain_id, account, key_hash, version, wrap_epoch, mpk_g2 }` 不含 release_nonce /
job_id / actor / runner_id / request_block。因为 `request_hash` **随 `request_block` 变**
(规格自己在同一句里这么说),所以连磨 nonce 都不必 —— 换个区块重发同一请求就是新键、直接过闸,
拿回**一模一样**的 σ_i。

**后果**:一次授权可无限重复释放,每次还额外产生一份**新的链上收据** —— 也就是制造更多
F-SPEC-1 所需的公开 partial。

**同路径上其他缺失的 §3.7 清单行**

- `MAX_RELEASES_PER_ACTOR_PER_HOUR`(§4.5 = 1,000):PartialSign 路径上**根本没有限流器**;
  cbssd 里唯一的 `RateLimiter` 接在 CBFS ingest 服务上。
- Runner Registry 成员/活跃状态(`0x01`):`authorize()` 读了 job 分配(`0x02`)但从不读 registry。
- `SecretVersion.pending == false`:`CbssSecretResolutionResponse` 没有 `pending` 字段。

---

## 三、门禁自身的缺陷

### F-GATE-1 · `contract.cbss_wire_round_trip` 是幽灵闸(HIGH)

注册于 marshal pack `pack.py:290`,`location_repo=node`,`location_test=cbss::tests::release_request_body_round_trip`。
它是契约 `cip24-cbss`(`pack.py:197-202`,`repos=["cbss","node"]`)的**唯一** `verify_invariants` 条目 ——
即 CIP-24 wire 契约的**唯一跨仓检查**。

实证(node worktree @ `origin/devnet` `fd955abf5`):

```
$ cargo test -p cowboy-types --lib cbss::tests::release_request_body_round_trip
running 0 tests
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 555 filtered out
exit 0                                   ← 静默假过

$ cargo nextest list ... cbss::tests
cbss::tests::cbss_state_dtos_serde_roundtrip
cbss::tests::proxy_health_legacy_record_decodes_with_defaults
cbss::tests::release_receipt_set_legacy_record_decodes_without_attempt_proof
3 tests, 0 benchmarks                    ← 注册的那个测试不存在
```

与棘轮先例 `econ.fee_conservation` 同形状(注册了、测试体不存在、cargo 无匹配即 exit 0)。

**已排除的过度指控**:cbss 自带的 `crates/cbssd/tests/chain_byte_equality.rs`(2 个测试,CI 真跑)
是硬编码 golden hex。查证后 node 与 cbss devnet **pin 同一个** `cowboy-protocol-codec` rev
`706612ff2189828b713b8ceb116e9de9d4268275`,所以编码器今天就是同一份代码,该 golden 确实能抓
「pin 一挪、字节就变」。**残留缺口**是 `check-cowboy-protocol-revisions.py`(cbss `pipeline.yml:79`,
node、runner 亦有)按其 docstring 只强制**单个 Cargo.lock 内部**的 one-rev,**不跨仓** ——
而跨仓正是这条死闸的职责。

### F-GATE-2 · `crypto.cbss_ibe_roundtrip` 结构性不可选中(HIGH)

- 测试体**是真的**:cbss `crates/cbss-crypto/src/ibe.rs:293` `ibe::tests::ibe_round_trip_matches_bilinearity`
- 触发前缀是 **node 相对路径**:`_CRYPTO_PREFIXES = ("cbss-crypto/", "cowboy-py/")`(`pack.py:479`)
- 这两个目录在 node devnet **不存在**:`git ls-tree -d origin/devnet cbss-crypto cowboy-py` → 空
- 在 cbss 仓里碰**装着这个测试的那个文件**也选不中它:
  `invariants --repo cbss --paths crates/cbss-crypto/src/ibe.rs` → `['cbss.threshold_any_t_recovers']`

`pack.py:473-478` 的注释自称 cbss 仓路径「由下面的 `_CBSS_PREFIXES` / `_CBSS_INVARIANTS` 处理」,
但 `_CBSS_PREFIXES` 只选 `_CBSS_INVARIANTS`,不选 `_CRYPTO_INVARIANTS`。
**净效果**:改写 IBE 加密的 cbss PR,IBE 不变量覆盖为零。

### F-GATE-4 · `authorize()` 八道守卫中四道零覆盖(HIGH,变异实测)

变异表跑的是 **CI 实际用的那条 suite**:`cargo nextest run --workspace --locked -E 'not binary(e2e)' --no-fail-fast`
(401 测试)。每个变异体还原时都 bust 了 mtime(避免复用旧产物造成假 KILLED)。

| # | 被摘掉的守卫 | 结果 | 杀手 |
|---|---|---|---|
| M1 | `validate_policy_acl(..)?` → `let _ =` | KILLED | `http_chain_authorizer_rejects_none_acl_cross_account` |
| **M2** | 新鲜度 `StaleRequestBlock` → `if false` | **SURVIVED** | — |
| **M3** | 元数据等值 → `Unauthorized` → `if false` | **SURVIVED** | — |
| **M4** | scope → `ScopeMismatch` → `if false` | **SURVIVED** | — |
| M5 | `verify_runner_signature(request)?` → `let _ =` | KILLED | `..._rejects_forged_runner_signature` |
| M6 | `validate_job_assignment(..)?` → `let _ =` | KILLED | `..._rejects_submitter_mismatch` ×2 |
| **M7** | `validate_actor_manifest(..)?` → `.unwrap_or(None)` | **SURVIVED** | — |
| M8 | `chain_id` 检查 → `if false` | KILLED | `..._rejects_foreign_chain_before_network_access` |

**全部八次变异下,`cbssd::adversarial` 均为 21/21 PASS。**

四道无闸守卫各自保护的东西:

- **M3 元数据等值** —— 请求的 `secret_id`/`version`/`recipient` 是否等于链上返回值。
- **M7 CIP-6 actor manifest 权限** —— CIP-24 req-7 把它列为 Effective access 的必要合取项;
  它还产出 `trading_post_label`,喂给 ACL 的跨账户判定。
- **M4 scope** —— account-scope vs secret-scope 混淆。
- **M2 新鲜度/重放窗口**。

> **诚实定性**:这四处**代码今天是对的**。缺的是**闸**。将来任何一次编辑弄坏它们,CI 全绿放行。
> 所以严重度是「测试覆盖/回归风险 HIGH」,**不是**「授权当前可绕过」。

**M3 为何 SURVIVED —— 结构性原因(非仅缺测试)**:`chain_authorizer.rs:40-48` 用
`request.body.secret_id` 与 `request.body.version` **构造** metadata URL;node 从 URL 路径取
`secret_id`、从查询参数取 `version`,再原样回显。所以

```rust
if secret_id != request.body.secret_id || metadata.version != request.body.version { ... }
```

是拿一个值和**生成它的那个值**比较,对诚实 node **永远不可能触发**。
只有 `recipient != request.body.recipient`(`:132`)读的是请求没规定的状态。
⇒ 任何修法应**专门钉 `recipient` 那一项**;给前两项加测试等于测一个恒真式。

### F-GATE-3 · cbss 没配 Almanax(MEDIUM)

`grep -rn -i almanax <worktree>/.github/` 零命中。与 cbfs / cbqs 同形状。
**含义**:第三方自动扫描对本仓贡献为零;深审时**变异表与 lens 表不能省**。

### CI 覆盖实证(`nextest list`,CI 的精确选择器)

```
401 tests 真跑
  cbssd 199 | cbss-client 81 | cbss-crypto 63 | cbssd::bin/cbssd 27
  cbssd::adversarial 21 | cbss-types 3 | cbssd::chain_byte_equality 2
  cbss-client::cip7_vectors 2 | cip7-prewrap 2 | cip7-unseal 1

cbssd::e2e     13 个测试 —— CI 中只编不跑(独立 --no-run 步骤)。含 COW-2842 release-receipt 场景
stress         0 —— feature 门控,CI 中连编都没编(1248 行惰性代码)
```

---

## 四、Advisory 与潜伏项

### F-TEST-1 · adversarial 套件大量恒真式(MEDIUM)

`crates/cbssd/tests/adversarial/cbss_adversarial.rs`(1330 行,21 测试,CI 真跑)。
档头是裸 import(第 1-14 行),**没有任何 doc comment 声明 scope 限制** ——
所以不存在「仅字节绑定、行为拒绝在 e2e 覆盖」这种既定说法可以为它开脱。

**真拒绝断言(7)**:`forged_partial_sig_rejected_by_pairing`、`wrapped_dek_aad_tamper_rejected`、
`dkg_timeout_partial_refund_too_few_dealers_rejected`、`share_disk_corruption_aad_tamper_rejected`、
`finalize_with_wrong_recipient_apk_fails_decrypt_authentication`、`t_proxies_collude_full_decrypt_boundary`、
`dkg_malformed_round2_rejected`

**仅「摘要不同」/ 字段搬运,不触发任何拒绝路径(13-14)** —— 举证三例:

```rust
// L204-207 —— 最严重的一例
fn unauthorized_job_release_scope_mismatch_changes_identity() {
    let req = request(8, 100);
    assert_ne!(identity_for(&req, 7), identity_for(&req, 8));
}
// 同一个请求,两个不同 epoch 参数。只断言「epoch 是身份哈希的输入之一」。
// 测试名声称的授权、job scope、释放拒绝,一样都没碰。

// L239-244
fn cross_actor_leak_attempt_changes_release_id() {
    let mut attacker = req.clone();
    attacker.body.actor = Address::from_low_u64_be(0xdead);
    assert_ne!(req.body.release_id(), attacker.body.release_id());
}
// 纯哈希单射性。守护进程是否拒绝外来 actor 的释放,与它无关。

// L134-142
fn replay_partial_sign_same_release_id_dedup_boundary() {
    newer.body.request_block = 200;
    assert_eq!(request(2,100).body.release_id(), newer.body.release_id());
    assert_ne!(request(2,100).body.request_hash().unwrap(), newer.body.request_hash().unwrap());
}
// 名字承诺 dedup 覆盖,正文一次都没调用 dedup 代码。
```

整个二进制 **0.017 秒**跑完 —— 无守护进程、无 I/O、无链交互。
与变异表互证:八次守卫变异下全部 21/21 绿。

### F-CONF-2 · 两个拒绝原因指标结构性不可达(MEDIUM)

```
构造:  IngestError::BadRequest("body_mismatch")   → Display "bad request: body_mismatch"
匹配:  text.contains("body hash")                 → 永不匹配
构造:  IngestError::Unauthorized("wrong_chain")   → Display "unauthorized: wrong_chain"
匹配:  text.contains("chain id")                  → 永不匹配
```

(`ingest.rs:804-816` vs `:883` / `:886`)两者都落进 `"bad_request"` 兜底(`:815`),
喂给 `cbssd_envelope_verify_failures_total{reason}`。
**后果**:运维用来告警**请求体篡改**与**跨链重放**的那两个计数器**恒为零**。
反向误判:畸形的 `x-cowboy-cbss-signature` **头部**产生的文本含 "signature"(`:954`),
被计为 `bad_sig`,用打字错误灌水伪造告警信号。
对照:同档下一个函数 `ingest_status_label`(`:793-801`)是对 enum 的穷尽 match —— 派生而非枚举。

### F-RUNNER-1 · runner 的链 RPC 未校验且供给整个释放信任根(MEDIUM,强证据未实跑)

`runner/crates/runner-node/src/node.rs:501` 从 `config.chain_rpc_url` 构造
`HttpChainSecretMetadataResolver` ← 环境变量 `CHAIN_RPC_URL`(`entry.rs:62-67`),
默认 `"http://localhost:4000"`(`config.rs:141`)。
`grep -rn 'require_https_or_loopback' /home/ubuntu/workspace/runner` → **0 命中**。

`resolve_secret` 的响应供给:`vss_commitments_g2[0]`(在 `threshold_client.rs:334` **被当作 mpk_g2 使用**)、
委员会 proxy 端点**及其 tls_spki pin**、`wrapped_dek`、`cbfs_pointer`。
明文链 RPC 上的 MITM 可以自洽地替换全部,runner 便会对攻击者运行的 proxy 完成一次门限释放,
并把攻击者选定的密钥**值**注入 job 环境。

⇒ **秘密注入 / 完整性破坏**,不是真实密钥的泄露(真密钥仍封给诚实委员会)。
今天只被「运维恰好用 loopback」这一点约束。
**由数据流阅读确立,未构建可运行 exploit。** 修法是本仓惯例的一行:让构造函数可失败并调用
`require_https_or_loopback`,正如 `HttpSecretsClient::new` 已经做的那样。

### F-CONF-1 · IPv6 SSRF 谓词死代码(LOW 可利用性 / MEDIUM 潜伏)

`url::Url::host_str()` 对 IPv6 返回**带方括号**的字符串,`.parse::<IpAddr>()` 失败,
`is_ok_and(..)` 短路为 false ⇒ `host_is_private_or_loopback`(`http_util.rs:144-158`)
整个 `IpAddr::V6` 匹配臂经 URL 路径**不可达**。

以独立探针 crate(pin `url =2.5.8`,谓词逐字复制)实测:

```
https://[::ffff:169.254.169.254]/   host_str="[::ffff:a9fe:a9fe]"  parses=false  private_or_meta=FALSE
https://[fd00::1]/                  host_str="[fd00::1]"           parses=false  private_or_meta=FALSE
https://[::ffff:127.0.0.1]/         host_str="[::ffff:7f00:1]"     parses=false  private_or_meta=FALSE
http://127.0.0.1:4000               host_str="127.0.0.1"           parses=true   private_or_meta=TRUE   (对照)
https://100.100.100.200/            parses=true                    private_or_meta=FALSE  ← 阿里云元数据
https://100.64.0.1/                 parses=true                    private_or_meta=FALSE  ← RFC 6598 CGNAT
```

`private_or_metadata_v4`(`:180-188`)是**手工枚举**:loopback/private/link_local/broadcast/
documentation/`0.0.0.0-8`/`[169,254,169,254]`。最后那个字面量本已被 `is_link_local` 覆盖 ——
即枚举了一家云的元数据 IP 就停下了。派生谓词(`Ipv4Addr::is_global` 或显式 CIDR 表)才是修法形状。

**为何不是可利用的 SSRF** —— 允许清单闸 **fail-closed 且排在前面**:

```rust
// http_util.rs:78-82
if allowed_hosts.is_empty() || !allowed_hosts.iter().any(|allowed| allowed == host) {
    return Err(.. "CBSS pointer URI host is not allowlisted");
}
if host == "169.254.169.254" || ... || host_is_private_or_loopback(&parsed) { return Err(..) }
```

空清单拒绝一切,而 `ciphertext_fetcher` 默认 `Vec::new()`(`:146` / `:154`)。
要走到坏掉的谓词,运维得先把**规范化后的带括号字符串**原样加进允许清单。

**潜伏风险很具体**:把允许清单改成可选(一个非常自然的「让运维可以不填」改动)会**立刻**打开它,
而现有那条 IPv6 测试(`:271-274`)传的是**已解析的 `IpAddr`**,压根不经过 `host_str()` ——
绿着,而它代表的路径不可达。

### F-LATENT-1 · rotate-committee 签名前像非单射(LOW,潜伏)

```rust
// receipt_submitter.rs:983-1002
bytes.extend_from_slice(&submission.new_mpk);                        // Vec<u8>,无长度前缀
bytes.extend_from_slice(&(submission.vss_commitments.len() as u32).to_be_bytes());  // 只框「个数」
for commitment in &submission.vss_commitments {
    bytes.extend_from_slice(commitment);                             // Vec<u8>,无长度前缀
}
```

类型(`orchestrator.rs:353-354`)确为 `new_mpk: Vec<u8>` / `vss_commitments: Vec<Vec<u8>>` ——
**签名时变长**;96 字节强制(`g2_bytes`)发生在 `receipt_submitter.rs:912`,即构造链上 args 时、**签名之后**。

**为何今天不可利用**(升级前已排除):proxy 签的是自己本地推导的提交(`output.mpk_g2` 天然 96 字节),
而任何真能落链的碰撞伙伴也必须全部 96 字节 —— 那就退化成相等。
故**不采纳**「一个签名可授权换成另一个 MPK」的定级。

**仍要记录的理由**:唯一撑住它的是「所有生产者恰好都吐 96 字节」。这道守卫会在有人加一个变体
(不同曲线、压缩/非压缩开关、可选字段)的当天失效。同 daemon 的 `append_ceremony_common`
(`protocol.rs:181-183`)**是**框长度的,所以此处是异类,修法便宜且符合本仓惯例。
现有测试 `rotate_committee_hash_matches_chain_args_preimage`(`:1683`)两边用**同一套未框定编码**
对算,属 code-vs-code,结构上抓不到非单射。

### `release_id` 前像与 CIP-24 §3.5 偏离(MEDIUM,规格过时)

代码(`cbss-client/src/types.rs:265-276`)8 个字段:
`chain_id, secret_account, secret_key_hash, version, actor, runner_id, job_id, release_nonce, serve_epoch`

规格(`cip-24-secrets-manager.md:761`)6 个:

> `release_id := keccak256(canonical(body.secret_id) || u64_le(body.version) || body.actor || body.runner_id || body.job_id || body.release_nonce)`

即代码**前置 `chain_id`、后缀 `serve_epoch`**。查证 node 侧 `release_id(body)` 委派给
`body.release_id()`,而两仓 pin 同一个 `cowboy-protocol` rev ⇒ **这是规格 vs 代码(规格过时),
不是跨仓分叉**。但 `release_id` 是**共识可见值**(键 `release_receipt:{release_id}`、进
`ReleaseReceiptRecorded`/`SecretReleased` 事件、进 `liveness_challenge_index`),
任何照 CIP-24 §3.5 独立实现的客户端会算出不同的值。

**修法是更新 CIP-24 §3.5**(加 chain_id + serve_epoch 是严格改进:跨链与跨 epoch 域分隔);
改代码会是共识面 flag-day。

### 三条 lens 收敛但未证到触发的一项

cbssd 的 `public_share_commitment` 缺少两个兄弟副本都有的 identity 拒绝:

| 无检查 | 有检查 |
|---|---|
| `cbssd/src/partial_sign.rs:678-691` | `cbss-crypto/src/threshold.rs:69-71` |
| `cbssd/src/cip9_volume_seal.rs:449-462` | `cbss-client/src/combiner.rs:88-93`(注释引 CIP-24 §3.4.3 step 11) |
| `cbssd/src/cip7_content_key_seal.rs:387-400` | |

一个原语五份副本、两套守卫 —— 而**没有守卫的那三份,正是决定 proxy 是否签名的那三份**。
这与 F-CRIT-1 修法第 (3) 条要求的 identity 检查是同一件事,应统一修。

---

## 五、主动驳回(记录在案,避免重复上报)

> 以下均为 scout 报出、经 prove 或本人一手核查后**证伪**的项。记录理由:防止下一轮重新提出,
> 尤其是最后一条 —— 照它修会**同时**破坏 CIP-24 §9.3 与三个仓的字节一致性。

| 假说 | 驳回依据 |
|---|---|
| `combine_partials` 组合未验证 partial | **typestate 闸**:`VerifiedReleasePartial.sigma_i` 是**私有**字段(`combiner.rs:19-22`),唯一构造函数 `verify_release_partial` 先做配对验证(`:31`)。以外部测试 target 触发 `error[E0451]: field sigma_i is private` 实证。子claim「threshold=1 使单个 partial 成为释放密钥」实验为**假**(AEAD 认证失败)。另:cbssd 从不 combine,只签名并自验(`main.rs:1590`) |
| DKG 从线上载荷取委员会配置 | **生产不可达**:cbssd 里每条 `DkgCoordinator` 路径都 `#[cfg(test)]`;生产走 `vetted_dkg.rs`(Commonware)。实证:给 `dkg.rs` 四个 finalize 入口加 `#[cfg(test)]` 后 `cargo check --workspace` **零错误**编出 daemon |
| CIP-9 volume-DEK AAD 缺 mpk 承诺 | **原理上驳回**:mpk **传递绑定** —— `mpk_g2 → account_release_key_material_hash → volume_dek_identity`(第 6 个字段,`node/ras/src/lib.rs:445-466`)→ 同时喂给 IBE 身份与 base AAD。往 AAD 直接加 mpk 会破坏 CIP-24 §9.3 的 32/128 字节 MUST,并分叉三份逐字节相同的实现(node/ras、cbfs/registry-proto、runner-storage)。**照报即自造回归** |
| CIP-9 legacy 路径签任意身份 | 身份由**共识代码**派生(node `dispatcher.rs:1448`);`Cip9SealRequest` **无入站路由**(是拉取循环);owner 绑定另有两道独立守卫(`cip9_volume_seal.rs:218` / `:243`)。正确表述是「legacy 路径被 PR #98 的 finalized-proof 加固落下了」= **COW-2889**,已在 `main.rs:1382-1384` 自认 |
| `chain_resolver` 无 transport 闸 | **不可达**:`resolve_account_release_key` 在 cbss 与所有消费仓**零调用方**。真正的 owner 侧封装是 `cbfs/cli/src/connect.rs:61` 的手写副本,那里同一缺口已在行内注释中作为 **COW-2925** 追踪。仅剩潜在 API 风险(四个函数都是 `pub`) |
| **TEE 闸没有允许清单**(**两条 lens 同时指认**) | CIP-24 把信任存储与签名校验分配给 **TEE Verifier `0x05`**,不是 proxy。§257:「CBSS **never accepts a proxy-supplied TEE assertion**…The TEE Verifier owns the companion trust store」;§1083(proxy 该做的那一行):「runner has a live non-revoked `tee_att:{job_id}:{runner}` record **written through a trusted-key signed-attestation path** \| `0x05`」;§840 链在收据提交时再查一次。代码检的 job_id/runner/revoked/valid_now/区块窗口**正是那一行** |
| zizmor template-injection HIGH @ `pipeline.yml:236` | 展开的是 `${{ job.status }}`,受控枚举(success/failure/cancelled) |

> ⚠️ **方法学教训**:两条独立 lens 收敛于同一主张**不构成证据**。TEE 那条上,两条 lens 都只从代码推理,
> 没有查规格把哪件事分配给哪个组件。

---

## 六、需要人裁的三件事

1. **链上观察者能否读到 CBFS 私有卷内容?**
   这决定 F-SPEC-1 停在 HIGH 还是升为完整明文击穿(CRITICAL)。压在 cbfs 授权绕过集群
   **COW-2285 / COW-2300 / COW-2301** 上。**本次未测试,不做断言。**
2. **F-CRIT-1 的修法必须给机制不给极性** —— 只加期望门限检查会留下 identity 系数变体。
3. **F-CRIT-2 必须独立修** —— 它挺得过对 F-SPEC-1 的显然修法。需**移除/哈希收据中的 `runner_request`**
   **并**给释放请求绑定收件人。

---

## 七、方法学与降级披露

**执行的确定性检查**

| 检查 | 结果 |
|---|---|
| `inv.cbss.threshold_any_t_recovers` | **PASS** —— `running 1 test … ok`(1 passed / 62 filtered),真闸 |
| `inv.contract.cbss_wire_round_trip` | **DEGRADED** —— `running 0 tests` / exit 0,幽灵闸 |
| `cli ci-scan`(zizmor) | **COMPLETE** —— 36 findings(29 high / 6 medium / 1 info),1 条 high 已举证驳回 |
| Almanax | **UNAVAILABLE** —— PR 域工具且本仓未配置。**如实记为 unavailable,不是「0 findings」** |
| `nextest list`(CI 精确选择器) | 401 tests;e2e 只编不跑;stress 不编 |
| 8 变异体变异表 | 4 SURVIVED / 4 KILLED;污染自查已排除 |

**降级(如实记录,run 35 status = `degraded`)**

- 不变量阶段:2 条选中中 1 条是幽灵;第 3 条 CIP-24 不变量结构性不可选中。
- 外部扫描:Almanax 不可用。

**方法学偏差(主动披露)**

变异表与并发运行的 prove agent **共用了同一个 worktree**,违反隔离纪律。
事后污染自查**已排除**:八次变异运行全部恰好 **401 tests**(等于基线),
且所有变异日志中 prove agent 临时测试档零命中。

**基建插曲**:根盘曾 100% 满(484G),导致一次后台任务 exit 0 却**零输出** ——
这是「log 空得像没跑到」的典型伪装,不能当作结论。已按安全顺序清出 72G,
只删孤儿构建产物(`~/.marshal/cargo-target` 38G 孤儿、`marshal-pr-sweep/workspace` 25G、
node `target/debug/incremental` 10G),**未碰任何 worktree 本体**。

---

## 八、复现指引

```bash
# 1) 干净 worktree(不要放 /tmp —— 会被中途清理)
git -C <workspace>/cbss worktree add --detach /home/ubuntu/marshal-worktrees/cbss-deep-0826 \
    0e52d3995b730cf5b6bad914e693324e3e91c3c5

# 2) 复现幽灵闸(在 node origin/devnet 的干净 worktree 上)
cargo test -p cowboy-types --lib cbss::tests::release_request_body_round_trip
#   → running 0 tests … exit 0
cargo test -p cowboy-types --lib cbss::tests -- --list
#   → 只有三个测试,注册的那个不在其中

# 3) 复现 CI 的精确选择
cargo nextest list --workspace --locked -E 'not binary(e2e)'

# 4) 复现变异表(注意 --no-fail-fast,还原时 bust mtime)
#    驱动脚本见产物目录 mutate.py

# 5) 复现 F-CRIT-2 的两个探针
#    产物目录 cbss_replay_probe.patch(279 行),应用到一份**抛弃式副本**,不要动审计 worktree
```

### 随报告入库的产物(本目录)

| 文件 | 内容 |
|---|---|
| `2026-08-26_cbss_audit_mutate.py` | 变异表驱动脚本(8 个变异体;还原时 `os.utime` bust mtime) |
| `2026-08-26_cbss_audit_mutation_table.json` | 变异表结果(含每个变异体的杀手测试名与 adversarial 计数) |
| `2026-08-26_cbss_audit_replay_probe.patch` | **F-CRIT-2 的可复现探针**(279 行)。应用到一份**抛弃式副本**,不要动审计 worktree |

### 仅存于审计机的产物(未入库,体积过大)

`/home/ubuntu/marshal-worktrees/_deep0826/`

- `closure-{crypto,chain-authz,release-orch,input-boundary}.md` —— 4 份中立闭包 bundle,共 7228 行
- `findings-{invariant-phase,mutation-table,adversarial-suite,critical}.md`
- `mut-*.log` —— 每个变异体的完整 401 测试输出
- `evidence.json`、`gate.json`、`findings.json` —— 落库用的 manifest

审计 worktree `cbss-deep-0826` 已验证**干净**停在 `0e52d39`。
落库记录:`review_run` 35(`degraded`)、`gate_decision` run 1373 —— 可用
`marshal review-run-show --run-id 35` 回读完整 evidence manifest。

---

*Generated by Marshal (risk-tiering + invariant gate + adversarial review). Advisory only.*
