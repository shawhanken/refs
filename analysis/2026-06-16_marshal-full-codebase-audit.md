# Marshal 全量代码审计 —— cowboy / node / runner / cbss / cbfs

- **日期:** 2026-06-16
- **方法:** Marshal flow A(对抗式 review,默认怀疑)铺到五仓全量代码,按 crown-jewel(共识 / 经济 / 安全 / 加密)切片,9 个并行审计 agent。**所有标 HIGH/CRITICAL 的发现均由本人独立复核**(grep 零调用点 / 读关键行 / 跑 PoC / 跑探针 actor),不是直接转述 agent。
- **底座态势:** CIP MUST→不变量覆盖仅 **24.1%**(29 CIP 中 7 个有 ≥1 不变量),所以静态代码审计是发现新问题的主战场。
- **范围:** node(execution/storage/rpc/pvm/runner-actors)、runner(off-chain daemon)、cbss(crypto/daemon)、cbfs(auth/crypto/erasure/manifest)、cowboy(docs,conformance 已覆盖,无可构建代码)。
- **针对版本:** 各仓当前本地 HEAD(devnet/main 一线代码)。注:CIP-24 purpose-aware/`secrets.verify` 逻辑尚在 PR(#729,未合 devnet),故 CBSS 现网仍是单一 `secrets.read`。

---

## 一、确认的 HIGH / CRITICAL 发现(7)

> 全部已独立复核。多数命中**已合并/现网代码**,按 Marshal flow A 第 7 步应转流 C 上棘轮。

### C1 — [CRITICAL][node/pvm] `import os`(及任何预缓存的黑名单模块)绕过沙箱守卫 → 共识分叉 + 验证者机密泄露
- **位置:** `pvm/crates/vm/src/vm/mod.rs:682-699`(`import_inner` 的 sys.modules 短路)+ `pvm/crates/vm/src/import.rs:38`(`os` 在解释器初始化即预加载)+ 守卫 `pvm/crates/pvm-runtime/src/guard.rs`(只 hook `builtins.__import__`)。
- **机制:** 普通 `import os`(无点、level 0、空 from_list)由 `import_inner` 直接从 `sys.modules` 命中返回,**根本不走 `__import__`**,守卫的 deny 检查从不触发。`os` 在 init 时已入 `sys.modules`,故永远预缓存。
- **独立复核(consensus 路径 `actor_execution()` warm-pool,本人跑探针 actor):**
  - `import os; os.getpid()` → `Ok("392245")`(真实 PID,非确定)
  - `import os; os.urandom(4)` → `Ok([19,145,81,176])`(**真 OS 随机 → 每个验证者必分叉**)
  - 对照 `import pickle`(非预缓存)→ `Err(Forbidden)`,精确隔离出"预缓存短路"这个洞;`from os import getpid`(走 from_list)→ Forbidden。
- **影响:** 任意已部署 actor 一行 `import os` 即可取 `os.urandom`/`os.environ`/`os.uname`/`os.getpid` → 状态根分叉(共识 fork)+ 读取验证者进程环境变量(**机密泄露**)。**这不是已知的 COW-2228 反射洞**,是新洞。`pvm/` 还 workspace-excluded、node CI 不跑,回归风险极高。
- **建议棘轮(hazard):** `pvm.blacklisted_module_blocked_even_if_precached` —— 对 `stdlib_blacklist` 每个名字,actor 内 `import <name>`(普通形式)即使预缓存也必须 raise。修向:在 `import_inner` 的 sys.modules 短路**之前**执行 deny 检查,或守卫安装后从 `sys.modules` 驱逐/None 毒化黑名单名。回归测试必须接入**真会跑**的套件(绕开 pvm CI 盲点)。

### C2 — [HIGH][cbfs] owner cap-token 的 `owner_signature` 从不校验 → 委托所有者授权绕过
- **位置:** `registry-proto/src/lib.rs:879`(`validate_owner_cap_token`)+ 唯一调用方 `hooks/src/cowboy_owner_auth.rs:168-237`。验证函数 `verify_owner_cap_token_signature`(`registry-proto/src/lib.rs:654`)**全仓零调用点**(本人 grep 复核确认)。
- **机制:** owner cap token 带两个签名:delegation_cert 的 secp256k1(钱包签)+ `owner_signature`(对 token 具体字段的 Ed25519,cbfs key 签)。`validate_owner_cap_token` 校验了 cert、owner 匹配、volume、TTL、时窗、access-mode→op,**唯独不验 `owner_signature`**;调用方也不验。函数自己的 doc 明说调用方 MUST 验 —— 没人验。
- **复核:** agent 跑了 PoC:用合法 victim cert + `owner_signature=[0u8;64]` 造一个 `ReadWrite` token,`validate_owner_cap_token(...,"PUT_SHARD",...)` 返回 `allowed=true`;同 token 上 `verify_owner_cap_token_signature` 返回 `false`。本人复核 grep 确认零调用点。
- **影响:** delegation_cert 是 bearer-visible(明文 `X-Cbfs-Delegation` header + QUIC token 内嵌)。任何看到 victim 一次请求的人(存储/relay 节点、链路观察者)可复制其 cert,自铸 `access_mode=ReadWrite`、任意 `path_prefix`、新时窗的 token,owner_signature 填垃圾 → 节点接受 → **对他人私有卷分片的完整读写/删除**。
- **建议棘轮(hazard):** `cbfs.owner_cap_token_signature_verified` —— owner_signature 不是 `delegation_cert.cbfs_public_key` 对 `owner_cap_token_signing_bytes` 的合法 Ed25519 签名则必须拒绝(即便 cert 合法)。现有 `forged_token_fails_validation` 只覆盖 runner token,owner 路径无对抗签名覆盖。

### C3 — [HIGH][node] runner 结果重复结算:`handle_job_result_submit` 无终态守卫 → 抽干共享 escrow + 重复支付
- **位置:** `execution/src/runner/verifier.rs:111-745`(结算块 253-742,escrow 扣 578-588,支付 608-639,状态置 Completed 581-582)。
- **机制:** 唯一准入门是 `assigned_runners.contains(&result.runner)`;**没有"job 是否仍 Assigned"的读检查**,`put_runner_result` 直接覆盖、无"已 reveal"去重(本人复核:函数内只在 581-582 **写** Completed,无前置状态守卫读)。对任意 `threshold < runners` 的 job(如 MajorityVote 3/2,normalize.rs:529 允许):第 T 个 reveal 触发结算 → escrow 扣、各 runner 付、状态 Completed;但其余 assigned runner 仍在委员会列表里,其 reveal 再次进入 → 无守卫 → **整个结算块重跑**:escrow 二次扣、各 runner 二次付。单个 runner 重复重提同一 reveal 即可任意次重触发。
- **影响:** dispatcher 账户是**所有 job 共享的 escrow 池**;重复结算抽走属于其它待结算 job 的 escrow + 铸造重复支付 = 直接盗取池内 escrow + 价值创造。投机引擎对成功 tx 不回滚。
- **建议棘轮(invariant):** `econ.job_settles_at_most_once` —— `handle_job_result_submit` 在 `get_job_status != Assigned` 时必须 early-return(如 `JobAlreadyComplete`),且拒绝同地址二次 reveal。

### C4 — [HIGH][node] 延迟 tx 费用超额铸造:`block_burn += 全额 burn` 不顾实际扣款 → 价值不守恒
- **位置:** `execution/src/execution/transaction.rs:808-846`(铸造点 844-845)+ sink 铸造 `storage/src/speculative.rs:516-539`。
- **机制(本人复核 836-846):** 用户延迟(`is_system_triggered==false`)成功路径:只 best-effort 扣 `from_actor = min(fee, actor_bal)` 和可能的 `from_owner`,但无条件 `self.block_burn = block_burn.saturating_add(deferred_fees.burn)`(**全额** burn)。actor+owner 不足时,记入 ZERO/burn sink 的额度 > 实际扣除额 → 向 burn sink **铸造** CBY,破坏 `Σ铸造 == Σ销毁+转账+tip`。非延迟路径有 escrow + sender 兜底所以安全;**延迟路径无 escrow 无兜底**却铸全额 burn。现有守恒 proptest 是 Transfer-only/非延迟,覆盖不到。
- **建议棘轮(invariant):** `econ.deferred_fee_conservation` —— 延迟 fire 后 `block_burn` 增量 == 实际扣除额(`from_actor+from_owner`),proptest 驱动欠资 actor 断言全局守恒。
- **关联 M:** 延迟 burn 用 lane-effective(倍率)basefee 计算却无 max-fee 上限/escrow(`transaction.rs:796-806`),放大本洞(目前倍率默认可能为 1,故列 MED)。

### C5 — [HIGH][node] CBSS `actors==None` 缺同账户检查 → 跨账户机密外泄(违反 CIP-24 §3.1.5)
- **位置:** `execution/src/cbss.rs:3188-3198`(`validate_release_policy_acl`)。
- **机制(本人复核代码 + spec):** spec line 130 规范明确:`actors==None` 解析为"**owning account == 该 secret 拥有账户**的任意 actor";line 904 表格亦"(`None` and same-account)"。代码:`if let Some(actors)=... else Ok(())` —— None 时**无条件放行**,无 `body.actor == secret_id.account` 检查。manifest 是消费方自声明(非 owner 授权),且 `parse_secret_manifest_entry` 认可跨账户 `"0xVICTIM:KEY"` 形式。
- **攻击路径:** victim 拥有 secret 且 `policy.actors=None`(默认"仅我自己的 actor"意图、最省配置)。攻击者部署 actor manifest 写 `secrets.read.keys=["0xVICTIM:KEY"]`,提交自己的 job(submitter==actor)、派自己 runner、提交 release receipt → ACL 放行(None→无条件 Ok)、manifest 放行 → 链上重组出 IBE key → **victim 机密被释放给非授权跨账户 actor**。
- **建议棘轮(invariant):** `cbss.none_policy_is_same_account` —— `policy.actors==None` 时要求 `body.actor == secret_id.account`;回归:None+跨账户必 `Unauthorized`。通用 hazard:每个 `Option` 型 ACL 必须按 spec 定义并强制其 `None` 语义,不可默认放行。

### C6 — [HIGH/MED][node] `active_jobs` 从不自增 → 并发上限与聚合质押下限双双失效(质押不足)
- **位置:** `dispatcher.rs:2095`(Filter 6 读)、`2127-2136`(Filter 9 仅单 job)。本人复核:`active_jobs` 生产代码**无任何写**(只测试里 5881/9234 赋值)。
- **机制:** `active_jobs` 恒 0 → Filter 6(`>= max_concurrent_jobs`)永假,并发上限从不拒绝;Filter 9 只校验**当前单个** job 的 `1.5×max_price ≤ stake`,不聚合在飞 job。质押 S 的 runner 可接无限并发 job、每个值至 S/1.5,总敞口 ≫ S,作恶全失约时最大可罚仅 S。CLAUDE.md 宣称的"1.5×/active job"超额抵押实际未跨 job 强制。
- **建议棘轮(invariant):** `econ.aggregate_active_job_stake_bound` —— `Σ(1.5×max_price over Assigned jobs) ≤ effective_stake`,或落地真正自增/自减的锁定质押计数器。

### C7 — [HIGH][node] 默认对象 `repr` 的堆指针(`<… at 0x…>`)经 PVM 异常文本进入 `receipt_root` → 共识分叉
- **位置:** `pvm/crates/vm/src/builtins/object.rs:438/445`(默认 `object.__repr__` 用 `get_id()` 格式化 `0x…`)→ `pvm/crates/vm/src/object/ext.rs:509`(`unique_id()=self as *const _ as usize` 裸指针)→ `pvm-runtime/src/lib.rs:1445-1489`(`build_fault_detail` 不脱敏)→ `execution/src/structured_error_map.rs:85-118`(detail→StructuredError.why/context)→ `storage/src/types.rs:614-617`(写入 receipt)→ `storage/src/merkle_utils.rs:25-34`(receipt_root = keccak(receipt))。
- **机制:** 失败 actor tx 的异常若渲染默认 repr 对象 —— `raise ValueError(self)`、`raise Exception(SomeObj())` 或任意 2+ 参异常(每参走 repr)—— 把对象**裸堆地址 0x<ptr>** 嵌入异常 str/traceback。`get_id()` 是 ASLR+分配器相关的活进程指针,每验证者不同 → 落进 receipt 的 `why`/`context` → receipt_root 的 keccak 叶 → 两诚实验证者同 tx 得不同 receipt_root → **verify 失败/分叉**。攻击者可任意触发。
- **复核状态:** 每一跳源码已读通(本人复核链路),agent 未做活 repro(pvm 独立 workspace)。机制完整,高置信但未执行端到端。
- **建议棘轮(invariant/hazard):** `consensus.receipt_text_no_runtime_identity` —— 进 receipt 的 PVM 异常文本必须脱敏对象身份(正则归一 `object at 0x…`,或 `get_id()` 改确定计数器,或把 `why`/`traceback` 移出共识 receipt codec 入非共识 sidecar)。同 tx 两 VM 跑应得字节一致 StructuredError。

---

## 二、MED 发现

| ID | 仓 | 位置 | 摘要 |
|---|---|---|---|
| M1 | node/pvm | 作用域(无 guard) | `id()` / 默认 `hash()` / 默认 `repr()` 暴露裸指针(`id(object())`、`repr` 含 `0x…`)→ 与 C7 同类,actor 放入返回/状态即分叉(agent 已 demo id/repr) |
| M2 | node/pvm | `pvm_executor.rs:897-946` / `determinism.rs:58-107` | 白名单内 I/O/进程模块(socket/subprocess/select/signal/threading/ssl/inspect)链上可 `import`(`socket.gethostname()`→`cowboy-001` 已 demo);只在本地 `--strict` sim 拦,共识部署/运行时不拦 |
| M3 | node/pvm | `pvm-runtime/src/lib.rs:130-134` | 裸大整数字面量 `2**20000` 绕过 4096-bit int guard(已 demo,bit_length 20001);deploy gate 只查十进制 >1234 位字面量,漏 `**`/`0x` |
| M4 | node | `pvm_executor.rs:1022-1060` | 代币 hook 的 `max_cycles/cells` 上限在 storage-read 结算(`consume_tracked`)**之前**就 `restore_limit` → 读 gas 漏到父预算,hook 隔离上限被绕(确定性,非分叉,是 griefing 上限洞) |
| M5 | runner | `runner-http/src/executor.rs:44` | 已释放 secret 经 HTTP 请求 URL 进 INFO 日志(`${VAR}` 替换后 url 被 `info!` 打印);secret-in-URL 是受支持模式 |
| M6 | runner | `runner-http/src/executor.rs:48-80` | 无 SSRF/URL 校验:submitter 控 url,无 scheme/loopback/`169.254.169.254`/私网过滤 → 结合 entitled secret 可外泄到攻击者端点 / 打内网元数据 |

---

## 三、LOW / INFO

- **[node/pvm] F4 反射再获取**(`import builtins; builtins.eval` + `types.FunctionType(code,globals)()` 已 demo)—— 已知开放,棘轮 `esc-20260610-pvm-reflection-bypass`(pending)。注意与 C1 交互:`import builtins` 普通形式因预缓存可能仍绕过。
- **[runner] Http/Llm 渲染 secret 不 zeroize**(`node.rs:978-982` 只覆盖 Mcp;Http url/header/body、Llm prompt 拷进普通 String 不擦)。
- **[runner] `runner-consensus::aggregate_results` 是死代码**(返回 results[0] 不校验一致;只被自身测试引用)—— 误导性,真防护靠链上 commit-reveal。
- **[rpc] ras.rs ~25 处把内部 codec/serde 错误 `Display` 回显到响应体**(泄露内部结构字段名,无机密);faucet 限速是全局非 per-IP(双重 chain_id 门控,不达主网)。
- **[cbss] `combine_partials` 设计上不认证**(取前 t 个不逐个 verify),安全靠 type-state `VerifiedReleasePartial` 守卫(当前唯一调用方已先验);reshare 要求全部旧签名者响应(liveness 限制,非 soundness)。

---

## 四、各 agent 复核为"干净"的面(节选,供覆盖参考)

- **node econ:** EIP-1559 双 basefee 更新数学(防 0/防溢/对称)、burn/tip 分摊无除法丢精、settlement sum==100 且 auth 门控、非延迟费用守恒、self-transfer 守卫(COW-389)—— 均稳。
- **node runner-actors:** 注册签名绑定、result.runner 用认证 sender 覆盖、commit-reveal 绑定、slash 路由守恒、deregister 冷却守卫 —— 稳(两 HIGH 之外)。
- **node state-root:** 作用域内 HashMap 均不进 root(timer auction 有确定 tie-break,recent_by_actor 是 BTreeMap);state_root 走 QMDB key-ordered;logs_root/bloom BE 一致;PROPOSE 期 `Instant::now()` captured 进 manifest 由 verifier 重放 —— 仅 C7 一处。
- **node rpc:** 所有状态变更 POST 走签名 tx + `admit_submission`;签名信封(cert+Ed25519+时窗+nonce 重放缓存);body 512KB/batch 50/permit 信号量/多处 list clamp;无攻击者可达 panic —— 边界已硬化(Almanax/Marshal 驱动)。
- **cbss crypto:** 阈值 soundness(任 t 重组、任 t-1 失败,proptest)、VSS 恶意份额检测、pairing/IBE 正确性(对 arkworks 交叉验)、子群/曲上点检查、域分离、AAD 绑定、nonce 不复用、DKG saboteur 检测 —— 45/45 测试过,稳。
- **cbfs:** AES-GCM 每写新 nonce + AAD、erasure 重组前验 BLAKE3 分片哈希 + 重组后验 ciphertext/content hash、manifest CID 内容寻址绑定、peer-drain RPC 强签名+重放缓存+节流 —— 仅 C2 一处。

---

## 五、覆盖态势与建议

- **底座:** 37 不变量(34 来自棘轮),逃逸 1 open(`esc-20260615` 错误码冲突)/ 38 closed;CIP 符合度 24.1%。本次审计揭示**多数 crown-jewel 不变量缺失**(econ 守恒只覆盖非延迟 Transfer;PVM 沙箱/确定性几无不变量;CBSS ACL None 语义无测试;cbfs owner-token 签名无对抗测试)。
- **建议优先级(按可利用性 × 影响):**
  1. **C1 PVM `import os`** —— 一行即分叉+泄密,且 CI 不跑 pvm;最高优先,先上棘轮 + 接入真跑套件。
  2. **C2 cbfs owner_signature** —— bearer cert 复制即接管他人卷;一行修(加 verify 调用)。
  3. **C3 重复结算 / C4 延迟铸造 / C5 CBSS None / C6 active_jobs** —— 经济/授权,均现网。
  4. **C7 receipt repr 指针** —— 共识分叉,需脱敏。
- **七条 HIGH 各对应一条候选棘轮**(见各条"建议棘轮")。建议逐条经用户确认根因后 `ratchet-open/close`,并在对应仓落地 proptest/hazard。

---

*Generated by Marshal (risk-tiering + invariant gate + adversarial review). Advisory only.*
