# Marshal 全量代码审计 —— 第二轮(pass 2)

- **日期:** 2026-06-16 · 接 `2026-06-16_marshal-full-codebase-audit.md`(pass 1)
- **方法:** 7 个并行 agent 覆盖 **pass 1 未碰的子系统**(node chain/共识、调度器/timer/消息、token/治理/委托、升级/库/CIP-16/RAS、cbss 守护进程协议、cbfs 传输/fuse/store、wallet 字节兼容)+ completeness-critic;对 pass 1 的 13 条发现去重(只报新的)。**所有 HIGH/CRITICAL 本人独立复核**(读关键行/grep/比对 spec)。
- **结果:** 7 条新 HIGH/CRITICAL + 3 条 MED + 8 条 LOW。其中 **node `token_mint` 任意铸造是本轮最严重(CRITICAL)**。

---

## 一、确认的新 HIGH / CRITICAL(7)

### N1 — [CRITICAL][node] PVM `token_mint` host op 无 mint_authority 校验 → 任意代币无限增发
- **位置:** `execution/src/pvm_host.rs:3379-3403`(host op)+ `:515-532`(apply)。
- **机制(本人复核):** `token_mint(token_id,to,amount)` 暴露给 actor Python;检查仅 `deny_if_read_only` + gas + `to.len()==20 && amount!=0` + cache 存在 —— **完全没有 `mint_authority` 检查**。apply 步 `total_supply.saturating_add(amount)` + `to_bal+amount` 写入,**无授权、无 max_supply、无 checked_add**;余额贷记甚至在 mint 记录存在判断之外(无条件)。系统指令路径 `token/core.rs:448` 却有 `mint.mint_authority != caller` 检查 —— host-op 路径是绕过。
- **影响:** 任意已部署 actor 一句 `token_mint(任意token, 攻击者, 巨量)` → 凭空增发供应 + 余额,彻底破坏代币价值守恒。
- **建议棘轮(invariant):** `econ.token_mint_requires_authority` —— host-op mint 必须 load mint 记录并要求 `actor_address == mint.mint_authority`,enforce max_supply + checked_add;测试:非 authority 调 host `token_mint` 不得改 total_supply/余额。

### N2 — [HIGH][node] 每高度 TimerList 写无上限、读拒 >16384 → 永久 liveness 停摆
- **位置:** `storage/src/timers.rs:85-99`(`set_timer` push 无每高度上限)· `storage/src/types.rs:264-281`(`TimerList::read` 拒 `count > MAX_TIMER_LIST_SIZE=16384`)· `storage/src/speculative.rs:735`(解码错误致命传播)。
- **机制(本人复核):** 唯一上限是每 actor `MAX_TIMERS_PER_ACTOR=1024`,无每高度跨 actor 总量上限。~17 个攻击者 actor(17×1024=17408>16384)在同一攻击者选定的未来高度各排满定时器 → 该高度 TimerList 不可解码 → 链到该高度时每个验证者一致 decode 失败 → 区块执行报错 → 确定性永久停摆。写路径能持久化一个永远读不回的列表。
- **建议棘轮(invariant):** `state.timer_list_height_bound` —— `set_timer` push 前 enforce 每高度上限,超限可恢复地拒绝排程;测试:跨 actor 排 >16384 于一高度,断言被拒且 `get_timers_by_height` 仍可解码。

### N3 — [MED-HIGH][node] 跨 actor 重入根 actor → 读到陈旧值 + 静默丢写
- **位置:** `execution/src/pvm_host.rs:2250`(`call_actor` 仅 `target != caller` 才快照切换)· `:1506-1511`(callee 缓存 seed 缺失)· `:1006-1009`(commit 循环 `if *address == self.actor_address { continue }` 跳过根 actor 写集)。
- **机制(本人复核 + agent repro):** A(写x=1)→B→A(读x:空/陈旧;写x=2)。重入 A 帧的写集 keyed 在 root_addr,被 commit 循环 `continue` 跳过 → 最终状态 x=1,重入的 x=2 被丢弃,且重入读 x 陈旧。无任何重入守卫。确定性(非分叉),但破坏 actor 自身不变量(如重入锁/余额计数经路由自调用)→ 可被用来打破 token 类 actor 的不变量。
- **建议棘轮:** `contract.no_reentrancy_stale_state` —— 禁止重入已在调用栈的 actor,或把根 actor 写集并入其活缓存;测试 A→B→A 同键,断言最终反映内层写、内层观察到外层写。

### N4 — [HIGH][cbfs] AuditGetShard 返回完整分片字节、**零请求认证**
- **位置:** `node/src/handler.rs:1257-1361`(handler)· `types/src/lib.rs:858`(`AuditGetShardRequest` **无签名字段**)· 测试 `:2250 audit_get_shard_returns_signed_found_receipt_without_token_auth`(断言 `auth.requests().is_empty()`)。
- **机制(本人复核):** 兄弟 peer-drain handler 要求(Ed25519 签名 + on-chain `Draining` + sender∈assignments),本 handler 顶着同样的"故意不走 AuthProvider"注释却**一个都没做**;请求类型连签名字段都没有。仅校验 `node_id` 回显 + 60s 时窗。命中返回整个 `shard_bytes`。node_id 在每条 PlacementRecord 里广播、shard_id 也在其中 → 任何见过 placement 记录的人即可拉取任意分片明文字节,绕过 GetShard 的 token 鉴权与公开读卷绑定。
- **建议棘轮:** `cbfs.audit_get_shard_authenticated` —— 要求链上身份签名 + Draining + assignee,或只返签名回执(hash+len)不返原始字节;测试:未签名 AuditGetShard 在配置 relay_registry 时被拒。

### N5 — [HIGH][cbfs] PutPlacement / ReplicatePlacement 不绑定记录 volume_id 到 cap token → 跨卷 placement 伪造/覆盖
- **位置:** `node/src/handler.rs:1036-1122`(PutPlacement)、`1127-1182`(ReplicatePlacement)调 `authorize_placement(..., None)`;对照 `:545-557` PutShard 强制 `token_volume==payload.volume_id`。
- **机制(本人复核):** 两 handler 传 `volume_id: None`,随后解码完全由调用方控制的 `PlacementRecord`(volume_id/assignments/shard_hashes/erasure 参数全不交叉校验)。`validate_owner_cap_token` 只证 token 对**自己卷**有效,无法发现记录指向**别的卷**。持任意 placement cap(卷 A)者可对任意卷 B 的 PlacementRecord 插入(version+1 CAS)或 last-writer merge → 把修复重定向到攻击者节点、损坏 erasure 元数据、或 DoS victim 卷。
- **建议棘轮:** `cbfs.placement_record_volume_bound_to_cap` —— 解码后用 `Some(record.volume_id)` 调 authorize,token 卷 ≠ record 卷则拒(对称 PutShard);测试 volume-A cap 写 volume-B 记录 → ErrAuth。

### N6 — [HIGH][wallet] 内容盲签的 `signMessage` = 交易伪造预言机 → 静默盗币
- **位置:** `src/background/service-worker.js:644-658`(签任意 32 字节 hash)+ `src/popup/approve.js`(`showSignMessageApproval` 仅显示 origin + "Sign Message" + 地址,**从不显示 message/hash 字节**)。
- **机制(本人复核):** 链的签名输入恰是 `keccak256(PayloadSign CBOR)`(`node/types/src/execution.rs:151-176`,`verify` 从该 hash recover)。恶意 dApp 已知地址(connect)+ nonce(getAccount),本地构造攻击者有利的 `Transfer{to:攻击者,amount:全部}` 的 PayloadSign,keccak256 后调 `signMessage(该hash)`;用户只见"Sign Message",dApp 用返回签名组装完整 Transaction POST `/submit` → 节点接受 → **盗币**。无域分离使 message-sign 与 tx-sign 前像碰撞。
- **建议棘轮(hazard):** `wallet.message_sign_domain_separated` —— signMessage 必须对域分离 digest 签名(EIP-191 式前缀,不可与 tx 签名前像碰撞)且 UI 展示完整内容;验证:用 signMessage 签 `keccak256(payload_bytes)` 再提交 devnet 应被拒。

### N7 — [MED-HIGH][node] 升级 subset 检查可被**删除约束参数**绕过 → 权限/配额放大
- **位置:** `execution/src/entitlement/param_match.rs:16-33`(`grant_compatible` 只遍历 new grant 的参数;new 参数为 None 直接返 true)· 运行时把缺省参数当无限(`pvm_host.rs:1773` storage.kv max_bytes、`:2812/2828` oracle.llm)。
- **机制(本人复核 + agent repro):** subset 规则"键只缩不增"只在 entitlement-id 粒度查,不在 per-param 粒度。新 manifest 保留 `storage.kv` 但**删掉 `max_bytes`** → `grant_compatible` 循环无项可查 → true;`validate_manifest` 接受(配额参数 required:false)→ 运行时 `if let Some(max_bytes)=...` 缺省即不限 → actor 升级后获无限 storage/llm 配额、或放大 `http.fetch` allowlist_domains(本应只能收窄)。现有 `broadening_params_rejected` 测试只覆盖抬高存在值,不覆盖删键。
- **建议棘轮:** `contract.upgrade_subset_param_drop_is_broadening` —— `validate_upgrade_subset` 须遍历 current grant 的每个键,new 缺失即拒(或把缺省可选参数归一为最严);测试扫 {删 max_bytes / max_tokens / allowlist_domains}。

---

## 二、新 MED(3)

| ID | 仓 | 位置 | 摘要 |
|---|---|---|---|
| N8 | cbfs | `node/src/handler.rs:502-613` | PutShard 不绑定 `shard_id` 到授权卷(store 无条件覆盖)→ 持卷 A 写 cap 者可用卷 B 的 shard_id 覆盖 B 的字节(shard 投毒);erasure/修复部分缓解 |
| N9 | cbss | `partial_sign.rs:165-247` + `chain_authorizer.rs` | proxy 无 PartialSign 重放/去重(`release_nonce` 被忽略)→ 捕获的请求可在 384 块窗口内向每个 proxy 重放,每次触发 ~5 次链查 + 一笔 SubmitReleaseReceipt → 回执/链交易 spam(非未授权释放,σ_i 确定不泄新料) |
| N10 | cbss | `tls.rs:112` + `transport.rs` + `wire.rs:40` | QUIC 端点无客户端认证、无 per-source 限速、每流 16MiB 预分配 → 256 流 × 16MiB ≈ 4GiB 瞬时 RSS 内存耗尽 DoS |

---

## 三、新 LOW / INFO

- **[node]** 区块 `extra_data` 不进 digest(`types/src/execution.rs:3879`)→ 1MiB/块 wire 可塑性/放大(生产恒空,故 LOW)。
- **[node]** 延迟 tx 在 mempool 选择中绝对优先 → 用户 tx 短暂饿死(全局 4096 上限使约一块内排空,非永久)。
- **[node]** mempool `deferred_queue` 无自身计数上限(仅共享字节上限 + 信任生产侧)。
- **[cbss]** 同 scope 并发 ceremony 按 scope+kind 查、忽略 epoch → 路由可能非确定(需链允许同 scope 重叠事件)。
- **[cbfs]** GetShard 是存在性预言机(ErrAuth vs ErrNotFound,与 GetPlacement 的存在性隐藏修复不一致)。
- **[cbfs]** 写路径无配额(`max_capacity_bytes`/`AuthDecision.max_bytes` 仅作建议)→ 授权写者可写满磁盘 DoS。
- **[wallet]** 默认私钥明文存 `chrome.storage.local`(passkey 加密为可选)→ 本地/profile 泄露面(非远程 dApp 向量)。
- **[node/wallet]** `PayloadSign` 不含 chain-id/genesis → 同账户+nonce 跨 Cowboy 网络重放(node 设计缺口,wallet 继承)。

## 四、确认仍 live 的既知缺口
- **[node]** CIP-9 RAS route-manifest §6.8 卷-entitlement 授权仍未实现(`system_instruction.rs:3329` TODO,COW-1293 棘轮已在册)—— 任何可自管 actor 可声明 static_route volume 绑定而不过 entitlement 检查。

## 五、pass-1 "干净"结论复核(completeness-critic)
本轮各 agent 复核了 pass-1 未深入的相邻面并确认:node chain propose/verify/report 对称 + 失败 fail-stop(非分叉)、mempool nonce/caps 稳、CIP-20 系统指令路径授权齐、治理 0x09 全门控、CIP-13 委托守恒、CIP-16 域名(既有棘轮已修)、cbss 链授权器非 fail-open + DKG 签名门控、cbfs transport 帧长预校验 + TOFU 证书钉、fuse 无路径穿越、wallet 签名 crypto(low-S/RFC6979)+ 字节兼容 PayloadSign 正确。pass-1 的 clean 结论未被推翻。

---

*Generated by Marshal (risk-tiering + invariant gate + adversarial review). Advisory only.*
