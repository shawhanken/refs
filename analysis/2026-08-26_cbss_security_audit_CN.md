# CBSS 安全审计分析报告

**审计对象**:`cowboyinc/cbss` @ `origin/devnet` `0e52d3995b730cf5b6bad914e693324e3e91c3c5`(2026-08-26)
**范围**:4 crates / 45.7k 行 Rust —— `cbss-crypto`(门限密码)、`cbssd`(守护进程)、`cbss-client`、`cbss-types`
**方法**:闭包提取 → 12 条视角并行假说枚举 → 逐假说证真/证伪 → 变异表验证闸的有效性

> **与门禁报告的关系**:本文是**安全域**分析 —— 威胁模型、信任边界、攻击面、按被破坏的安全属性
> 分类的发现、系统性根因、修复路线图。同日的
> [`2026-08-26_cbss_marshal_deep_audit_CN.md`](2026-08-26_cbss_marshal_deep_audit_CN.md)
> 是**流程域**报告(门禁判决、不变量状态、lens 完整性、降级披露、复现指引)。
> 两者共享同一批证据,不重复彼此的结构。需要复现步骤与产物清单请看那一篇。

---

## 证据等级(全文统一使用)

| 标记 | 含义 |
|---|---|
| **【实测】** | 写了探针并跑通,产生了具体触发或具体反例。最高等级 |
| **【核查】** | 我一手读代码/规格原文并交叉验证过,但未构造运行时触发 |
| **【未裁定】** | 视角枚举时提出,有具体 file:line 依据,但**没有**证真也没有证伪。列出是为了不丢失攻击面,**不可当作缺陷上报** |
| **【已驳回】** | 曾被提出,经证据推翻。记录以防重复提出 |

> 本报告刻意把「未裁定」单独成节而不混入发现列表。把未经证实的假说和实测触发并列,
> 是安全报告最常见的失信方式。

---

## 一、系统与信任模型

### 1.1 CBSS 保护什么

CBSS(CIP-24 Secrets Manager)是 Cowboy 的门限秘密释放服务。核心承诺:**没有任何单点持有明文密钥**,
释放需要 n 个 proxy 中的 t 个协作。

密钥层级(理解全部发现的前提):

```
MSK   门限主密钥 —— 从不重建;以 Shamir 份额分散在 n 个 proxy
  │   通过 DKG 生成;通过 reshare 轮换份额(但 MSK 本身不变)
  ▼
σ = MSK · I     对某个身份 I 的 BLS 签名 = t 个 σ_i 的 Lagrange 组合
  │             I = hash_to_G1(chain_id ‖ account ‖ key_hash ‖ version ‖ wrap_epoch ‖ mpk_g2)
  ▼
K = HKDF(e(σ, U))   IBE 派生的封装密钥
  │
  ▼
DEK   数据加密密钥 —— 存于链上 wrapped_dek(AES-GCM under K)
  │
  ▼
plaintext   密钥明文 —— AES-GCM(DEK, ·),存于 CIP-9 私有 CBFS 卷
```

**关键性质**:`I` 只绑定 `(chain_id, account, key_hash, version, wrap_epoch, mpk_g2)` ——
**不含** `release_nonce`、`job_id`、`actor`、`release_id`。
因此同一 `(secret_id, version)` 的每一次释放,每个 proxy 产出的 σ_i **逐字节相同**。
这一条同时是 F-C-1、F-C-3 与 S-2 的根因,值得单独记住。

### 1.2 参与方与信任假设

| 参与方 | 假设中的信任 | 实际由什么强制 |
|---|---|---|
| **Proxy(委员会成员)** | t−1 个可以是拜占庭的 | 门限密码学 |
| **Runner** | 半可信;须被 job 分配 | 链上 job dispatcher 记录 + 签名 |
| **Actor** | 须持有 CIP-6 manifest 权限 | 链上 manifest + `SecretPolicy` ACL |
| **Node RPC(`node_endpoint`)** | **完全可信**(隐含假设) | ⚠️ **什么都没有** —— 见 S-1 |
| **链** | 可信排序与状态 | 共识 |
| **CBFS** | 存密文;访问受控 | ⚠️ 本次未审计,见 §六 |
| **运维** | 可信配置 | 配置无校验 |

> ⚠️ 「Node RPC 完全可信」是本系统**最大的未言明假设**。代码在 `main.rs:1382-1384` 自认了这一点
> (「authenticating that view against a hostile node_endpoint is the tracked COW-2889 follow-up」),
> 而 CIP-9 service 路径已在本次审计的 HEAD(`0e52d39`,PR #98)针对它做了加固 ——
> 要求两个独立信使的 light-client 已终局状态证明。**释放路径与 CIP-9 legacy 路径没有跟上。**

---

## 二、攻击面清单

### 2.1 入站 —— QUIC 监听器(无客户端认证)

```rust
// crates/cbssd/src/tls.rs:107-121
let mut server_crypto = rustls_023::ServerConfig::builder()
    .with_no_client_auth()          // ← 任何网络对端都能建连
    .with_single_cert(cert_chain, key)
```

| 流类型 | 值 | 前置认证 | 每请求实工 |
|---|---|---|---|
| `PartialSign` | `0x01` | **无** | 最多 6 次串行 node RPC + 门限签名 + 一笔链上收据交易 |
| `Health` | `0x02` | **无** | 返回 `share_count` / `eligible` / `suspended` / `hpke_public_key` / `chain_lag_blocks` |
| `DkgRound` | `0x10` | 逐消息签名 | DKG 状态机推进 |
| `ReshareRound` | `0x11` | 逐消息签名 | reshare 状态机推进 |

限额:`MAX_ACTIVE_CONNECTION_TASKS = 256`、`MAX_ACTIVE_STREAM_TASKS = 256`、
`MAX_CONNECTIONS_PER_IP = 16`(**loopback 豁免**)、`MAX_FRAME_LEN = 16 MiB`。

> `SpkiPinnedServerVerifier`(`tls.rs:182-230`)是**客户端**用来校验对方服务器证书的,
> **不闸入站**。入站没有委员会白名单、没有客户端证书、没有 SPKI pin。

### 2.2 入站 —— HTTP(三个监听器)

| 监听器 | 路由 | 闸 |
|---|---|---|
| `serve`(`ingest.rs:325`) | `POST /v1/cbss/envelope` | 签名 + 过期 + body hash + chain_id;**明文 TCP,无 TLS** |
| `serve_ops`(`:473`) | `/metrics` 等 | **拒绝非 loopback**(`:478-482`) |
| `serve_statusz_operator`(`:512`) | statusz | ⚠️ **无 loopback 闸、无认证**,而其 handler 的 doc 自称「Loopback-only like /metrics」 |

### 2.3 出站(SSRF / MITM 面)

| 目标 | 构造点 | 是否过 `require_https_or_loopback` |
|---|---|---|
| 释放授权用的 node RPC | `chain_authorizer.rs:107` | ✅ **是**(唯一一处) |
| 链监听器 node RPC | `chain_watcher.rs:252-260` | ❌ 否 |
| 收据提交 node RPC | `receipt_submitter.rs:429` | ❌ 否 |
| solver / intent feed node RPC | `solver_loop.rs:272`、`intent_feed.rs:220` | ❌ 否 |
| CBFS 扇出端点 | `ingest.rs:1072-1087` | ❌ 否(连 scheme 都不校验) |
| Proxy QUIC 拨号 | `transport.rs:455-459` | ❌ 否(`quic://` 前缀可选,无地址策略) |

`chain.node_endpoint` 的出厂默认是 `"http://localhost:8545"`(`config.rs:165`),**配置载入时零校验**。

### 2.4 链上(全部未认证 `ReadLocal` 路由)

- `GET /cbss/secret/{account}/{key_hash}?version=v` → `wrapped_dek{ciphertext, nonce, ephemeral_u, aad}` + `release_key` + `cbfs_pointer`
- `GET /state/0x04/{key}` → `release_receipt:{release_id}` 集合(**含原始 σ_i**)
- `GET /transaction/{hash}`、区块体 → 收据交易的完整 calldata
- `GET /cbss/proxies`、release-key 快照 → 委员会 `network_addr` 与 `tls_spki`

---

## 三、对手模型

| # | 对手 | 能力 | 本报告中命中的发现 |
|---|---|---|---|
| **A-1** | **链上观察者** | 只读公开链数据与未认证 RPC。零特权 | **F-C-1**、**F-C-2** |
| **A-2** | **任意网络对端** | 能连到 proxy 的 QUIC 端口 | **F-C-2**、F-A-1 |
| **A-3** | **旧委员会的法定人数**(t 个旧 proxy) | 按定义已持有 MSK | **F-I-1**(把 MSK 扩散到诚实节点并永久降级门限) |
| **A-4** | **被攻陷/敌对的 `node_endpoint`** | 控制 proxy 看到的链视图 | S-1 名下多条 |
| **A-5** | **链 RPC 链路上的 MITM** | 明文 HTTP 时可改写 | **F-I-2** |
| **A-6** | **被授权但恶意的 runner/actor** | 一次合法授权 | **F-C-3** |

> A-3 的门槛值得强调:**它不是额外假设**。`node/execution/src/cbss.rs:5143` 的
> `let old_signer_count = material.threshold as usize;` 让链**恰好点名 t 个旧签名者**当 reshare dealer。
> 这 t 个按定义本来就持有 MSK —— 所以 F-I-1 的共谋前提就是协议自己指定的那一组人。

---

## 四、发现 —— 按被破坏的安全属性分类

### 4.1 机密性(Confidentiality)

#### F-C-1 · 链上观察者可从公开数据还原任意已释放版本的 DEK 【实测】

**对手**:A-1(零特权) · **影响**:一个 secret-version 的 DEK 永久公开 · **可撤销性**:**不可**

释放收据把每个 proxy 的**原始 48 字节 G1 partial** 原样写上链,恰好 `threshold` 条
(node `cbss.rs:1444-1452` 以 `release_key.threshold` 封顶 —— 正好是 Lagrange 门限)。
`wrapped_dek`(含 `ephemeral_u`)本身也是链上状态并由未认证 RPC 全文提供。
`proxy_index` 由公开委员会向量推出(链自己就这么推,node `cbss.rs:1385-1390`)。

于是攻击链的每一步输入都是公开量,而最后一步用的是**本仓自己发布的库函数**:

```rust
// crates/cbss-client/src/combiner.rs:55-71 —— 五个参数全部链上可得
pub fn verify_combine_and_decrypt(
    identity_input: &IdentityInput, wrapped_dek: &WrappedDek, threshold: usize,
    vss_commitments_g2: &[Vec<u8>], partials: &[ReleasePartial],
) -> Result<Zeroizing<Vec<u8>>, SecretsError>
```

已实跑本仓自带测试验证该路径可用:`cargo test -p cbss-client --lib combiner`
→ `verify_combine_and_decrypt_recovers_wrapped_dek ... ok`(3 passed)。

**这不是代码缺陷 —— 是规格自我矛盾。** `receipt_submitter.rs:129-167` 忠实实现了 CIP-24 §3.5。

| CIP-24 强制公开 | CIP-24 主张相反性质 |
|---|---|
| §3.5:「The receipt **carries the runner's original signed release request verbatim AND the proxy's BLS partial signature `σ_i`**」 | §3.4.6 模式表:「Who may obtain `σ` \| **the authorized runner only** \| anyone (public)」(左列=账户密钥) |
| §10.8:「each entry carrying the verbatim runner-signed request and the verified `σ_i`」 | §3.4.6:「**A tlock identity MUST NOT be used to wrap an account secret**(its key is public at `target_height`)」 |
| | §8.4 验证者可见清单:「… **NOT DEKs**, NOT shares.」 |
| | §3.8 step 12:「Runner R zeroizes plaintext, DEK, **σ partials**」—— 而 step 13 就是把同样的 partial 发上链 |

§3.4.6 甚至用第一人称把这个攻击对 tlock 族**写了出来**:「The accumulated partials are a **public**
chain artifact: **anyone** reads ≥ `t` of them, Lagrange-combines σ, and derives K」——
账户路径的收据在结构上完全相同。

**同族的不对称**(说明这个选择很可能未经推敲):

| 路径 | σ_i 上链前 |
|---|---|
| CIP-7(`cip7_content_key_seal.rs:270-290`) | **HPKE 封装**;`Cip7PartialDelivery` 无 σ_i 字段 |
| CIP-9(`cip9_volume_seal.rs:266-290`) | **HPKE 封装** |
| 账户密钥(`receipt_submitter.rs:130-167`) | **原始明文** |

**爆炸半径(精确,不夸大)** —— 一个 secret-version。σ = MSK·I 不能反推 MSK(§3.4.4 明确)。
但因为 `I` 不含任何 per-release 字段(见 §1.1),一次泄露覆盖该版本**所有过去与未来的释放**;
且 §3.4.4:「Reshare does **NOT** invalidate σ values for prior identities」——
ACL 编辑、移除 actor、注销 runner、reshare 全都撤不回,唯一手段 `force_rekey` 会让全部密文变砖。

**为何定 HIGH 而非 CRITICAL,以及升级条件**:纯链上观察者拿到 **DEK 而非明文** ——
明文密文在 CIP-9 私有 CBFS 卷里,而该卷的 volume-DEK 走的正是**做了封装**的 CIP-9 路径。还剩一层。

> ⚠️ **未决依赖(必须由人裁定)**:若链上观察者能读到 CBFS 私有卷对象,本条即为**完整明文击穿(CRITICAL)**。
> 这压在 cbfs 授权绕过集群 **COW-2285 / COW-2300 / COW-2301** 上。
> **本次审计未测试 CBFS 可达性,不做任何断言。**

---

#### F-C-2 · 释放请求是可转让的持有者凭证,观察者可自行凑齐法定人数 【实测】

**对手**:A-1 + A-2 · **影响**:把「止步于法定人数之前的释放」推到完成 · **前置**:384 块窗口内

两个探针跑的是**生产型别**,`test result: ok. 2 passed; 0 failed`:

- `probe_replayed_request_authorizes_at_a_proxy_that_never_served` —— 真 `HttpChainReleaseAuthorizer`
  + wiremock node,2 人委员会:proxy A 授权后,**同一份序列化往返后的请求**在 proxy B 上照样授权。
- `probe_same_signed_request_yields_partials_from_two_distinct_proxies` —— 真 `PartialSignService`、
  真 DKG share、两个独立 store:proxy 1 服务;proxy 1 拒绝**自己的**第二次(`ReplayedRequest`);
  proxy 2 用**同样的字节**服务并返回另一个有效 σ_i。

**为什么每一道闸都拦不住** —— `authorize()` 的完整闸表,按「这道闸检的是谁的性质」分类:

| 闸 | 位置 | 性质属于 | 重放者是否通过 |
|---|---|---|---|
| `chain_id` 相等 | `chain_authorizer.rs:104` | 请求 | ✅ |
| `require_https_or_loopback` | `:107` | **proxy 自己的 base_url** | ✅(根本不检查对端) |
| `verify_runner_signature` | `:109` | 请求 | ✅ **认证的是字节的作者,不是出示者** —— 签名就在被重放的字节里 |
| 密钥元数据拉取 | `:111-116` | 请求 | ✅ |
| 新鲜度窗口 | `:117-126` | 请求 | ✅(只限定**何时**重放,不限定**谁**) |
| 元数据等值 | `:128-134` | 请求 | ✅ |
| `validate_job_assignment` | `:137` | 请求 | ✅ `submitter` 绑的是 **job↔actor**,不是**呼叫方↔runner**;runner 私钥在服务时根本不参与 |
| `validate_actor_manifest` | `:144` | 请求 | ✅ |
| `validate_policy_acl` | `:145-150` | 请求 | ✅ ACL 是 actor-vs-actor,从来不是 caller 检查 |
| 交易站租约(CIP-33) | `:151-153` | 请求 | ✅ |
| TEE 证明 | `:154-156` | 请求 | ✅ 证明是 **runner 的**,窗口内一直有效,重放者不需要 TEE |
| scope 匹配 | `:158-161` | 请求 | ✅ |
| 委员会成员资格 | `:162-168` | **proxy 自己的 proxy_id** | ✅ 只限定可打哪些 proxy,不限定谁能问 |
| 重放预留 | `partial_sign.rs:389-403` | 请求 | ✅ **per-proxy**;没服务过的 proxy 没有记录 |

线上请求 `PartialSignRequest { version_byte, request }`(`protocol.rs:55-58`)
**根本没携带任何呼叫方身份** —— 就算想加 caller 检查,协议里也没有可读的字段。

**为何链上的法定人数上限拦不住**:`submit_system_instruction` 在 `/submit` 返回 tx hash 时即返回 ——
**仅入 mempool**。执行层的 `QuorumAlreadyReached` 永远到不了 proxy,拦不住 σ_i 被写回 QUIC 流。(见 S-6)

**规格层证据**:CIP-24 §3.4.5 item 2 明确**放弃**了本可挡住此攻击的收件人绑定,理由是
「proxy 侧 anti-replay/ACL 已经提供足够保障」—— 而那个 anti-replay 是 per-proxy 的。**前提不成立。**

**诚实的边界**:每次收割都迫使被驱动的 proxy **先广播一笔收据交易** —— 向受害 actor 计费
(node `cbss.rs:1448-1450`)并留下响亮的链上痕迹。**这不是隐蔽收割。**
对一次已正常完成的释放,F-C-1 已经把 t 个 partial 放上链,此处边际泄露为零。

**真正的升级点(两条)**:
1. 可以把一次**止步于法定人数之前**的释放(runner 崩溃、被分区、或在一个 proxy 应答后放弃)
   仅凭链上公开数据驱动到完成 —— 现有设计本应不可能。
2. 它是**独立路径**,挺得过对 F-C-1 的显然修法:把 σ_i 从收据里删掉**关不掉它**,
   因为收据仍在重新发布那张凭证。

---

#### F-C-3 · 一次授权可无限重复释放,且违背规格点名的去重键 【核查】

**对手**:A-6 · **影响**:制造更多 F-C-1 所需的公开 partial;绕过一切释放次数意图

CIP-24 §3.7(`cip-24-secrets-manager.md:1084`)**原文**:

> Anti-replay: `(release_id, proxy_id)` not previously served | proxy local bloom (24h) + chain
> `release_receipt`(dedup is on `release_id` … — **`request_hash` is fresh per `request_block`
> and is NOT used for dedup**)

代码用的**正是被点名禁止的那个键**:

```rust
// crates/cbssd/src/partial_sign.rs:389-401
let request_key: [u8; 32] = release_request_hash(&request.request.body)?  // ← 规格说这个不能用
    .as_bytes().try_into().expect("release request hash is 32 bytes");
ServedRequests::reserve(&self.served, request_key,
    request.request.body.request_block.saturating_add(REQUEST_FRESHNESS_BLOCKS))?;
```

因为 σ_i 与 nonce 无关(见 §1.1),而 `request_hash` **随 `request_block` 变**(规格自己在同一句说的),
所以连磨 nonce 都不必 —— **换个区块重发同一请求**就是新键、直接过闸,拿回一模一样的 σ_i。

同路径其他缺失的 §3.7 清单行:

- 留存窗口 384 块(≈6.4 分)而非规格要求的 **24 小时 bloom**;
- 授权路径上**不存在**任何对链上 `release_receipt` 的读取(规格把它列为去重的另一半);
- `MAX_RELEASES_PER_ACTOR_PER_HOUR`(§4.5 = 1,000):PartialSign 路径**根本没有限流器**
  (cbssd 里唯一的 `RateLimiter` 接在 CBFS ingest 服务上);
- Runner Registry 成员/活跃状态(`0x01`):`authorize()` 读了 job 分配(`0x02`)但从不读 registry;
- `SecretVersion.pending == false`:`CbssSecretResolutionResponse` 没有 `pending` 字段。

---

### 4.2 授权与完整性(Authorization & Integrity)

#### F-I-1 · reshare 可把 t-of-n 密钥静默塌成 1-of-n 【实测 · 本次最严重】

**对手**:A-3(协议自己点名的那 t 个人) · **影响**:该账户全部密钥的永久单点掌控 · **可观测性**:**零**

```rust
// crates/cbss-crypto/src/reshare.rs:234-240
let first = payloads.first().ok_or(Error::InvalidThreshold)?;
let threshold_u8 = first.threshold;          // ← 新多项式次数取自线上载荷
validate_threshold(threshold_u8, new_participants.len())?;

// crates/cbss-crypto/src/dkg.rs:324-329
if threshold == 0 || participants == 0 || threshold as usize > participants { Err }
// ← 只有 1 ≤ t ≤ n。无下限,且从不与链上声明的门限比对
```

生产入口 `ReshareCoordinator::finalize_encrypted`(`reshare.rs:304-316`,**未 cfg-gate**)
由 `orchestrator.rs:1626` 调用。链上声明的门限 `state.threshold` **在 finalize 时就在手边**
(`orchestrator.rs:1594-1642`),只是从来没被读。mpk 保全检查(`reshare.rs:293`)与多项式次数无关,
结构上挡不住。

**实测四探针(含对照组)**:

| 探针 | 线上门限 | 结果 |
|---|---|---|
| A | `1` | ACCEPTED;三个新节点 `share_scalar` **全等于 MSK** |
| B | `2` + 高次系数填 G2 identity | ACCEPTED;share **全等于 MSK**;**通过链上校验 ⇒ rotation 落链** |
| C(**对照**) | `2` 诚实 | ACCEPTED;share ≠ MSK(证明探针非恒真式) |
| D | — | `public_share_from_commitments([mpk,id,id], i) == mpk`(i=1,2,3) |

**探针 B 为何是要害** —— 探针 A 的裸 t=1 会被链上挡下,但**只被一道长度检查**挡下:

```rust
// node/execution/src/cbss.rs:5875-5889 —— 已在 origin/devnet 逐字复核
if threshold == 0
    || vss_commitments.len() < threshold as usize      // ← 长度检查,不是次数检查
    || vss_commitments.first() != Some(mpk)
{ return Err(ExecutionError::InvalidData); }
for commitment in vss_commitments { let _ = g2_from_bytes(commitment)?; }  // ← 不拒 identity
```

`g2_from_bytes` 不拒绝 G2 identity;唯一的 identity 守卫(node `cbss.rs:7310`)查的是**求值后**的
`S_i`,而此处它恰好等于 mpk。所以 `[mpk, identity]` 在 t=2 下满足每一条。

**后果**:链上记录 threshold=2,而**任何单个**新委员会 proxy 独自持有 MSK。
探针 D 显示每个 proxy 的 partial 仍能对已发布承诺验证通过、`combine_partials` 仍返回正确 σ
⇒ **零可观测异常**。它还能挺过之后所有诚实 reshare(每次都保全 mpk,而每个 dealer 的
`λ_i · S_old(i)` 都源自一个已经等于 MSK 的 share)。

---

#### F-I-2 · runner 的链 RPC 未校验,而其响应供给整个释放信任根 【未构造 exploit,数据流已追通】

**对手**:A-5 · **影响**:秘密**注入**(完整性),非泄露 · **跨仓**:runner

`runner/crates/runner-node/src/node.rs:501` 从 `config.chain_rpc_url` 构造解析器 ←
环境变量 `CHAIN_RPC_URL`(`entry.rs:62-67`),默认 `"http://localhost:4000"`(`config.rs:141`)。
`grep -rn 'require_https_or_loopback' <workspace>/runner` → **0 命中**。

`resolve_secret` 的响应供给:`vss_commitments_g2[0]`(在 `threshold_client.rs:334` **被当作 mpk_g2 使用**)、
委员会 proxy 端点**及其 tls_spki pin**、`wrapped_dek`、`cbfs_pointer`。
明文链路上的 MITM 可以**自洽地**替换全部 —— runner 便会对攻击者运行的 proxy 完成一次门限释放,
并把攻击者选定的密钥**值**注入 job 环境。真实密钥仍封给诚实委员会,**所以这是完整性破坏而非泄露**。

今天只被「运维恰好用 loopback」这一点约束。修法是本仓惯例的一行:让构造函数可失败并调用
`require_https_or_loopback`,正如 `HttpSecretsClient::new` 已经做的那样。

---

#### F-I-3 · 授权链八道守卫中四道零测试覆盖 【实测】

变异表跑 **CI 实际用的那条 suite**(401 测试,`--no-fail-fast`,还原时 bust mtime):

| 被摘掉的守卫 | 结果 | 保护的安全属性 |
|---|---|---|
| `validate_policy_acl` | KILLED | — |
| **新鲜度 `StaleRequestBlock`** | **SURVIVED** | 重放窗口 |
| **元数据等值 → `Unauthorized`** | **SURVIVED** | 请求命名的密钥 = 链上解析的密钥 |
| **scope → `ScopeMismatch`** | **SURVIVED** | account-scope vs secret-scope 混淆 |
| `verify_runner_signature` | KILLED | — |
| `validate_job_assignment` | KILLED | — |
| **`validate_actor_manifest`** | **SURVIVED** | **CIP-6 权限(CIP-24 req-7 的必要合取项)** |
| `chain_id` | KILLED | — |

**八次变异下 `cbssd::adversarial` 均为 21/21 PASS。**

> **诚实定性**:这四处**代码今天是对的**,缺的是**闸**。将来任何一次编辑弄坏它们,CI 全绿放行。
> 这是回归风险,不是「授权当前可绕过」。

其中 **元数据等值** 的 SURVIVED 有结构性原因(不只是缺测试):
`chain_authorizer.rs:40-48` 用 `request.body.secret_id` 与 `version` **构造** metadata URL;
node 从 URL 路径取 `secret_id`、从查询参数取 `version` 再原样回显。所以那个比较是
**拿一个值和生成它的那个值比**,对诚实 node 永远不可能触发。三个合取项里只有
`recipient != request.body.recipient` 读的是请求没规定的状态。
⇒ 修法应**专门钉 `recipient` 那一项**;给前两项加测试等于测一个恒真式。

---

#### F-I-4 · 「对抗性」测试套件大量是恒真式 【核查】

`crates/cbssd/tests/adversarial/cbss_adversarial.rs`(1330 行,21 测试,CI 真跑)。
档头是裸 import,**没有任何 doc comment 声明 scope 限制**,所以不存在「仅字节绑定、行为在 e2e 覆盖」
这种既定说法可以为它开脱。整个二进制 **0.017 秒**跑完 —— 无守护进程、无 I/O、无链交互。

真拒绝断言 7 条(`.is_err()` / `!verify_partial(..)`);其余 13–14 条只断言「摘要不同」。三例:

```rust
// L204-207 —— 最严重
fn unauthorized_job_release_scope_mismatch_changes_identity() {
    assert_ne!(identity_for(&req, 7), identity_for(&req, 8));
}
// 同一个请求、两个 epoch 参数。只断言「epoch 是身份哈希的输入」。
// 测试名声称的授权、job scope、释放拒绝,一样都没碰。

// L239-244
fn cross_actor_leak_attempt_changes_release_id() {
    attacker.body.actor = Address::from_low_u64_be(0xdead);
    assert_ne!(req.body.release_id(), attacker.body.release_id());
}
// 纯哈希单射性,与守护进程是否拒绝外来 actor 无关

// L134-142
fn replay_partial_sign_same_release_id_dedup_boundary() { /* 一次都没调用 dedup 代码 */ }
```

**安全含义**:这是本仓**唯一以安全命名**的测试二进制,它的存在会让人相信授权面有对抗性覆盖。
与 F-I-3 互证:八次守卫变异下全部 21/21 绿。

---

### 4.3 可用性(Availability)

> 门限系统里,**无响应的委员会成员会被罚没** —— 所以可用性缺陷在这里直接转化为经济损失。

| # | 问题 | 位置 | 证据 |
|---|---|---|---|
| F-A-1 | QUIC accept 循环在全局连接信号量上 `await`,而 **loopback 豁免** per-IP 上限 ⇒ 单一本地来源可占满 256 槽,此后**连拒绝远端都做不到** | `transport.rs:194`、`:219` | 【未裁定】 |
| F-A-2 | 16 MiB 帧 × 256 并发流的未认证缓冲(约 4 GiB),`read_frame` 在任何版本/签名检查**之前**读完整个帧体 | `wire.rs:40-66` | 【未裁定】 |
| F-A-3 | 诚实 proxy 被抖动 + 阻塞 fsync 推过请求方 5 秒 deadline ⇒ 算对了 σ_i、付了收据钱,仍被提交**活性挑战** | `dispatcher.rs:266-272`、`partial_sign.rs:173-188` | 【未裁定】 |
| F-A-4 | 单个畸形的链上委员会元数据条目(空 `tls_spki` / 非字面量 `network_addr` / 地址冲突)使 `from_proxy_metadata` **整体失败**,该 proxy 对**所有**诚实对端都发不出 DKG/reshare 消息 | `proxy_client.rs:82-98`、`:150-164` | 【未裁定】 |
| F-A-5 | 重放缓存上限 65,536 且**fail-closed 在收据已上链之后**;每次 partial sign 都全量重写 + fsync(窗口内 O(n²)) | `partial_sign.rs:74`、`:138-157` | 【未裁定】 |
| F-A-6 | 释放路径上多处 `std::sync::Mutex` + `.expect(...)`,一次 panic 即**永久毒化**;`Drop for ReplayReservation` 在同一次展开中重新加锁 ⇒ abort | `partial_sign.rs:115`、`:193-203` | 【未裁定】 |

---

### 4.4 可观测性(Observability)

#### F-O-1 · 两个安全告警指标结构性恒为零 【核查】

```
构造:  IngestError::BadRequest("body_mismatch")   → Display "bad request: body_mismatch"
匹配:  text.contains("body hash")                 → 永不匹配
构造:  IngestError::Unauthorized("wrong_chain")   → Display "unauthorized: wrong_chain"
匹配:  text.contains("chain id")                  → 永不匹配
```

(`ingest.rs:804-816` vs `:883`/`:886`)两者都落进 `"bad_request"` 兜底,喂给
`cbssd_envelope_verify_failures_total{reason}`。**运维用来告警「请求体篡改」与「跨链重放」
的两个计数器永远读零。** 反向误判:畸形的 `x-cowboy-cbss-signature` **头部**产生的文本含
"signature",被计为 `bad_sig` —— 用打字错误灌水伪造攻击信号。

对照:同档下一个函数 `ingest_status_label`(`:793-801`)是对 enum 的**穷尽 match** —— 派生而非枚举。

#### F-O-2 · 生产路径上被拒绝的 PartialSign 从不写审计 【未裁定】

`dispatcher.rs:273` 只在成功臂调用 `audit_result(..., Ok(&response))`,更早的失败全部 `?` 提前返回。
而审计日志是 proxy 面对**活性挑战**时唯一的自辩证据 —— 一个正当拒绝了请求的 proxy,
在挑战时会被答成 `ChallengeReason::NeverReceived`。

---

## 五、系统性根因

> 这一节是本报告的核心价值。逐条修复上面的发现只能治标;下面七个模式解释了**为什么会反复长出同类缺陷**。

### S-1 · 信任锚点就是正在被验证的那个响应

`current_head = metadata.request_block`(`chain_authorizer.rs:117`)—— 取自正在被验证的
`/cbss/secret/...` 响应本身。这一个值同时驱动:

- 新鲜度窗口判定(`:117-126`)
- `served_at_block` → 份额激活闸 `record.is_active_at()`(`partial_sign.rs:421-423`)
- TEE 证明的三个区块窗口比较(`:303-305`)
- 重放缓存的 `prune_expired`(`partial_sign.rs:173`)

daemon **自己有**独立的 `ChainWatcher::chain_head()`(`GET /height`,`chain_watcher.rs:280-299`),
`authorize()` 从不调用它。**tlock 路径已经因为 COW-2889 加了独立 `/height` 读取**,理由白纸黑字写在
`main.rs:1516-1519`(「the signer does NOT trust the unauthenticated due-set as the sole authority
for the reveal HEIGHT」)—— **释放路径没跟上**。

一个推论值得单独指出:`prune_expired` 与新鲜度判定用**同一个**不可信、非单调的数值 ⇒
一次头部回退会**同时**让重放记录被删、且让旧请求重新变新鲜。

### S-2 · per-proxy 状态被当作委员会级守卫

F-C-2 的根因。CIP-24 §3.4.5 item 2 明确以「proxy 侧 anti-replay/ACL 已足够」为由放弃收件人绑定 ——
而那个 anti-replay 是 per-proxy 的,对「换一个 proxy 问」完全无效。
规格的**论证前提**与实现的**实际性质**之间的落差,就是攻击面。

### S-3 · 兄弟通道信任姿态相反(最高产的一类)

| 对照 | 严格的一侧 | 宽松的一侧 |
|---|---|---|
| σ_i 上链 | CIP-7 / CIP-9 **HPKE 封装** | 账户路径**原始明文** |
| IBE 身份 | CIP-7 `cip7_content_key_seal.rs:224-233` 重算并比对;CIP-9 service `:82` 同样 | CIP-9 legacy `cip9_volume_seal.rs:265` **取自请求** |
| 链视图认证 | CIP-9 service:两个独立信使的 finalized-state proof(PR #98,即本 HEAD) | legacy / 释放路径:**原样信任 `node_endpoint`** |
| 失败方向 | `fetch_chain_id` **fail-closed** | `fetch_nonce` **默认 0**(`receipt_submitter.rs:761`) |
| 重复消息 | `insert_unique` → `DuplicateProxyMessage` | Committed 臂 `or_insert` **静默丢弃**(`orchestrator.rs:297`) |
| identity 拒绝 | `threshold.rs:69-71`、`combiner.rs:88-93` | cbssd **三份副本都没有**(`partial_sign.rs:678`、`cip9_volume_seal.rs:449`、`cip7_content_key_seal.rs:387`) |
| 监听器 | `serve_ops` **拒绝非 loopback** | `serve_statusz_operator` **无闸**(doc 却自称 loopback-only) |
| 签名前像 | `append_ceremony_common` **框长度** | `rotate_committee_hash` **不框**(`receipt_submitter.rs:983-1002`) |
| 计数器 | `reshare_driver.rs:365` 成功后才 `+1` | `dkg_driver.rs:421` 发送**前**就 `+1` |

**判据**:凡是同一件事在本仓有两份实现,而其中一份多一道检查 —— **没有那道检查的那一份,通常就是可达的那一份**。

### S-4 · 安全参数取自线上载荷,而非本地/链上策略

F-I-1 的根因。同形状还有 `dkg.rs::finalize_qualified`(生产不可达,整条 `#[cfg(test)]`,已单独证明)。

> ⚠️ 这类修法**必须给机制,不能给极性**。只加 `if first.threshold != expected { reject }`
> 会关掉探针 A、**放探针 B 大摇大摆过去**。正确的修法有三条,缺一不可:
> (1) finalize 收 `expected_threshold` 并比对;**且**
> (2) 拒绝任何非常数项承诺为 G2 identity 的 dealer;**且**
> (3) node 侧 `validate_release_key_material` 补同一道 identity 检查(顺带覆盖初始 DKG 路径)。

### S-5 · 枚举集合替代派生谓词

| 位置 | 枚举了什么 | 漏了什么 |
|---|---|---|
| `private_or_metadata_v4`(`http_util.rs:180-188`) | loopback/private/link_local/broadcast/documentation/`0.0.0.0-8`/`[169,254,169,254]` | RFC 6598 `100.64.0.0/10`(含阿里云元数据 `100.100.100.200`)、`198.18.0.0/15`、`224.0.0.0/4` |
| 元数据主机名(`:83-84`) | `169.254.169.254`、`metadata.google.internal` 两个字面量 | `metadata.goog`、裸 `metadata`、其他云 |
| `verify_failure_reason`(`ingest.rs:804`) | 五个字符串子串 | 见 F-O-1:两个分支**永不可达** |
| `get_json`(`chain_authorizer.rs:322`) | `404 \| 409 \| 410` → `Unauthorized` | 401 / 403 / 451 落进 transport 类错误,被调用方当**瞬时**而非**终局拒绝** |

对照:`ingest_status_label` 是对 enum 的穷尽 match。**同一档案里,派生写法与枚举写法并存。**

一个自成一类的例子:`url::Url::host_str()` 对 IPv6 返回**带方括号**的字符串,`.parse::<IpAddr>()` 失败
⇒ `host_is_private_or_loopback` 整个 `IpAddr::V6` 匹配臂**不可达**。以独立探针 crate
(pin `url =2.5.8`,谓词逐字复制)实测:

```
https://[::ffff:169.254.169.254]/   parses=false  private_or_meta=FALSE   ← 云元数据被判为「公网」
https://[fd00::1]/                  parses=false  private_or_meta=FALSE
https://[::ffff:127.0.0.1]/         parses=false  private_or_meta=FALSE
http://127.0.0.1:4000               parses=true   private_or_meta=TRUE    ← 对照组
```

**但今天不可利用** —— 允许清单闸 fail-closed 且排在前面(`http_util.rs:78-82`),
而 `ciphertext_fetcher` 默认空清单(拒绝一切)。潜伏风险很具体:把清单改成可选
(一个非常自然的「让运维可以不填」改动)会**立刻**打开它,而现有那条 IPv6 测试(`:271-274`)
传的是**已解析的 `IpAddr`**,压根不经过 `host_str()` —— 绿着,而它代表的路径不可达。

### S-6 · 入 mempool 被当作已交付

`submit_system_instruction`(`receipt_submitter.rs:673-712`)在 `/submit` 返回 tx hash 时即返回;
node 的准入只查 nonce/fee/签名,**不含任何 CBSS 语义、不做模拟**。后果沿着整条路径扩散:

- 收据 outbox 据此标记 `submitted`(`receipt_outbox.rs:127-133`);
- 重放守卫据此 commit,而 `partial_sign.rs:335-336` 的注释声称「只在对应收据已 durable 后才 commit」;
- **F-C-2**:执行层的 `QuorumAlreadyReached` 永远到不了 proxy,拦不住 σ_i 被写回。

同档 `await_transaction_execution`(`:391-424`)**确实**等执行结果 —— 但只有 force-rekey 恢复路径用它。
又一个 S-3 实例。

### S-7 · 未认证面上做实工

| 面 | 未认证时已发生的工作 |
|---|---|
| QUIC PartialSign | 最多 6 次串行 node RPC + 门限签名 + 一笔链上交易 |
| QUIC Health | 委员会份额清单(`share_count`/`eligible`/`suspended`) |
| HTTP envelope | blake3 + **secp256k1 recover** 排在限流器**之前**(`ingest.rs:690` vs `:701`) |
| statusz | 全量 `registry.gather()` + 文件系统 stat,泄露 `shares_active`/`committee_epoch`/队列深度 |

---

## 六、修复路线图

> 排序依据:**可利用性 × 不可撤销性 × 修复独立性**。同一编号内的子项**缺一不可**。

### P0 —— 立刻(不可撤销的损害)

**P0-1 · 关闭 reshare 门限降级(F-I-1)** —— 三条缺一不可,见 S-4 的机制说明。
**P0-2 · 定夺 CBFS 可达性** —— 这不是修复,是**分诊前置**:它决定 F-C-1 是 HIGH 还是完整明文击穿。
先查 COW-2285/2300/2301 的现状。

### P1 —— 短期(需要设计,但路径清晰)

**P1-1 · 给释放请求绑定收件人(F-C-2)** —— 同仓一路之隔就有现成范式:CIP-9 在请求里放
链上锚定的 `runner_x25519_pubkey` 并把 partial HPKE 封装给它(`cip9_volume_seal.rs:284-289`)。
**同时**必须移除或哈希收据中的 `runner_request` —— 只做其一都关不掉。

**P1-2 · 去重键改回规格(F-C-3)** —— 改用 `(release_id, proxy_id)`,加上链上 `release_receipt` 读取,
留存窗口对齐 24 小时。**注意**:`release_id` 前像目前是 8 字段而 CIP-24 §3.5 公布的是 6 字段
(代码前置 `chain_id`、后缀 `serve_epoch`;两仓共用同一份 `cowboy-protocol` 实现,
所以是**规格过时**而非跨仓分叉)—— 动这块之前先把 §3.5 更新掉,否则会把一个共识可见值的
定义分歧固化进新逻辑。

**P1-3 · 独立的链头读取(S-1)** —— 把 `authorize()` 的 `current_head` 换成
`ChainWatcher::chain_head()`,并加单调性下限。tlock 路径的现成写法可直接搬。

**P1-4 · 补上四道零覆盖守卫的闸(F-I-3)** —— 但**元数据等值那条只钉 `recipient` 分量**,
另两个合取项是恒真式,给它们加测试等于测 `A == A`。

### P2 —— 规格层(需要修正案,不能只改代码)

**P2-1 · CIP-24 σ_i 公开性的自我矛盾(F-C-1)** —— 不能只改 `receipt_submitter.rs`:
§3.5 step 8 的服务证明**就是**配对检查 `e(σ_i, G2_gen) == e(I, S_i)`,它需要明文 σ_i 在链上。
需规格修正案(σ_i 的知识证明,或封装给 runner 并附「封装内含有效 partial」的证明)。
连带需重新设计的明文 partial 消费方:`InvalidPartialReencryptEvidence`(`receipt_submitter.rs:70`)、
等价物罚没路径(node `cbss.rs:5988-6224`,它会比较并排序两个 `sigma_i`)。

**P2-2 · 更新 CIP-24 §3.5 的 `release_id` 公式** —— 加 `chain_id` + `serve_epoch`
(代码的做法是严格改进:跨链与跨 epoch 域分隔)。改代码会是共识面 flag-day。

### P3 —— 卫生与纵深防御

- 统一 `require_https_or_loopback` 到全部五类出站构造点(含 runner 仓,F-I-2)
- `private_or_metadata_v4` 换成派生谓词;修 IPv6 括号(S-5)
- 把 identity 拒绝补进 cbssd 的三份 `public_share_commitment` 副本(S-3)
- `rotate_committee_hash` 补长度框定(S-3);现有测试两边同一编码对算,抓不到
- 修 `verify_failure_reason`(F-O-1);失败路径也写审计(F-O-2)
- `serve_statusz_operator` 补 loopback 闸(S-3)

---

## 七、未裁定的攻击面清单

> 以下**全部**有具体 file:line 依据,但**没有**被证真也没有被证伪。
> 列出是为了不丢失攻击面。**不可当作缺陷上报**,需要各自的探针。

**密码学层**:reshare 不使旧份额失效(PSS 保全 MSK ⇒ `wrap_epoch` 不提供前向保密);
DKG/reshare 载荷无 epoch/session/ceremony 标识(跨仪式重放);HPKE Base 模式无发送方认证而
`dealer_index` 是载荷内自述字段(可诬陷诚实 dealer);`Vec::contains` 的二次复杂度由 16 MiB 载荷驱动;
秘密多项式系数未 zeroize 且 `derive(Debug)`;DKG/reshare 采样缺 `CryptoRng` 约束;
CIP-34 密封出价身份不含 chain_id 与 mpk。

**授权层**:交易站标签解码是**多对一**(`0x` 前缀可重复剥离、`u32` 接受前导零与 `+`)⇒
四种拼法映射到同一个 `TradingPostLabel`,一份租约覆盖全部变体;`lease_gated` 为真时
**完全跳过** ACL 检查而租约查询从不指名 `request.body.actor`;`wrap_epoch` 来自 RPC 且
进入被签名的身份却无任何交叉核对;委员会成员用 `find` 取首个匹配(重复条目静默择一)。

**编排层**:收据在重放守卫 commit **之前**发布 ⇒ commit 失败会为同一请求产生第二份**不同签名**的收据;
outbox 去重键含 `served_at_block` ⇒ 换个头部重发即绕过;DKG finalize 按 **HashMap 迭代序**
喂 commit 给 commonware(而 reshare 兄弟用确定性 Vec 序)⇒ 若 commonware 对顺序敏感则委员会静默分裂;
CIP-9 key delivery 硬编码空 `vss_commitments_g2`。

**输入边界**:envelope 的 `nonce` 进签名前像却从不比对任何 seen-set;`insert_pending`
无条件重置 ack 账本并延后 deadline;CBFS 扇出响应是**唯一**未限长读取的响应体;
失败扇出队列**只增不减**;intent_feed 在瞬时错误上**永久丢弃**区块(与其自身 doc 相抵触)。

---

## 八、主动驳回(记录以防重复提出)

| 曾提出的假说 | 驳回依据 |
|---|---|
| `combine_partials` 组合未验证的 partial | **typestate 闸**:`VerifiedReleasePartial.sigma_i` 是**私有**字段,唯一构造函数先做配对验证。以外部 test target 触发 `error[E0451]` 实证。子claim「threshold=1 使单个 partial 成为释放密钥」实验为**假**(AEAD 认证失败) |
| DKG 从线上载荷取委员会配置 | **生产不可达**:cbssd 里每条 `DkgCoordinator` 路径都 `#[cfg(test)]`。实证:给四个 finalize 入口加 `#[cfg(test)]` 后 `cargo check --workspace` **零错误**编出 daemon |
| CIP-9 volume-DEK AAD 缺 mpk 承诺 | **原理上驳回**:mpk **传递绑定**(`mpk_g2 → release_key_material_hash → volume_dek_identity` → 同时喂给 IBE 身份与 AAD)。⚠️ **照它修会同时破坏 CIP-24 §9.3 的 32/128 字节 MUST 与三个仓的逐字节一致性** |
| CIP-9 legacy 签任意身份 | 身份由**共识代码**派生(node `dispatcher.rs:1448`);`Cip9SealRequest` **无入站路由**;owner 绑定另有两道独立守卫。正确表述是「legacy 路径被 PR #98 的加固落下了」= COW-2889 |
| `chain_resolver` 无 transport 闸 | **不可达**:`resolve_account_release_key` 在所有仓**零调用方**。真正的 owner 侧封装是 `cbfs/cli/src/connect.rs:61` 的手写副本,同一缺口已作为 **COW-2925** 在行内追踪 |
| **TEE 闸没有允许清单**(**两条独立视角同时指认**) | CIP-24 把信任存储与签名校验分配给 **TEE Verifier `0x05`**,不是 proxy。§257:「CBSS **never accepts a proxy-supplied TEE assertion**」;§1083(proxy 该做的那一行)只要求「live non-revoked record **written through a trusted-key signed-attestation path**」;§840 链在收据提交时再查一次。代码检的正是那一行 |

> ⚠️ **方法学教训**:两条独立视角收敛于同一主张**不构成证据**。TEE 那条上,两条视角都只从代码推理,
> 没有查规格把哪件事分配给哪个组件。

---

## 九、覆盖范围与残余风险

**已覆盖**:门限密码(DKG/reshare/IBE/threshold)、链上授权(`chain_authorizer` 全闸链)、
释放编排(orchestrator/partial_sign/dispatcher/receipt_submitter)、外部输入边界
(ingest/transport/proxy_client/intent_feed)、CI 供应链(zizmor,36 findings)。

**未覆盖 —— 明确声明,不做任何断言**:

1. **CBFS 私有卷的实际可达性** —— F-C-1 的严重度分级悬在此处。
2. **node 侧执行逻辑** —— 仅在 F-I-1 与 F-C-1 需要时逐点核查,未系统审计。
3. **Commonware DKG 库内部** —— 生产 DKG 走它,本次只审了 cbss 侧的封装。
   `vetted_dkg.rs` 的 `public_sig`/`private_sig` 字段声明了、恒为空、且全仓无人读取 —— 这条【未裁定】。
4. **运行时/部署配置** —— 多条发现的实际风险取决于运维是否用 loopback、是否填允许清单。
5. **`e2e` 与 `stress` 测试路径的行为** —— CI 里 e2e 只编不跑、stress 连编都没编,
   所以它们所覆盖的行为在本次没有任何执行证据。

**自动化闸的实际强度(影响本报告的可信度基线)**:cbss **完全没配 Almanax**;
marshal 为本仓选中的两条不变量里,一条是幽灵闸(`0 tests` / exit 0),
第三条 CIP-24 不变量结构性不可选中。**这意味着本仓的自动安全闸贡献接近零** ——
上面每一条【实测】与【核查】都是人工构造的,而【未裁定】那一节,今天没有任何自动机制会去碰。

---

*本报告的判定分级与产物清单见同日的 [Marshal 门禁报告](2026-08-26_cbss_marshal_deep_audit_CN.md)。*
*Generated by Marshal (risk-tiering + invariant gate + adversarial review). Advisory only.*
