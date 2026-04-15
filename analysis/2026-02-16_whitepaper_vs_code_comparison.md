# Cowboy 白皮书 vs 代码实现 对比分析报告

> **白皮书版本**: Cowboy Technical Whitepaper (Draft for internal review, Updated 2026‑02‑15)
> **白皮书在线地址**: <a href="https://cb.ai-api.top/docs/#20260216_cowboy_whitepaper.md" target="_blank">📄 点击查看白皮书原文（新标签页打开）</a>
> **白皮书本地文件**: [`20260216_cowboy_whitepaper.md`](file:///home/ubuntu/cowboydocs/20260216_cowboy_whitepaper.md)
> **代码仓库**: `node` / `pvm` / `runner` (均在 `main` 分支)
> **分析时间**: 2026-02-16 (基于 MD 格式白皮书重新校对)

---

## 表一：白皮书与代码实现存在偏差的内容

白皮书中有定义，代码也有实现，但两者之间存在差异。

| # | 白皮书定义 | 白皮书位置 | 代码实现 | 代码位置 | 差异说明 |
|---|----------|-----------|---------|---------|---------|
| 1 | EOA 使用 **secp256k1** (ECDSA) 签名，Actor 地址使用 CREATE2 风格的 keccak256 推导 | §1.4 (L107-124): *"External Accounts (EOAs): Controlled by private keys"*; §1 (L614-628): *"External accounts MUST use secp256k1 (ECDSA) with chain‑id separation."*; §16.1 (L1050-1057): *"Cowboy external accounts (EOAs) MUST use the same secp256k1 elliptic curve"* | 代码使用 **Ed25519** 签名方案，所有 PublicKey / PrivateKey / Signature 类型均为 ed25519；无任何 secp256k1 引用 | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L7) — `use ed25519`; [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L39-L44) — Transaction struct 使用 `ed25519::PublicKey` / `ed25519::Signature` | **密码学方案不一致**: 白皮书在 §1.1, §16.1 多处明确指定 secp256k1 (ECDSA)，代码全面使用 Ed25519。这影响以太坊互操作性和地址统一 |
| 2 | Timer 使用**分层日历队列**: Tier 1 Block Ring Buffer (O(1)), Tier 2 Epoch Queue (O(1) amortized), Tier 3 Overflow Sorted Set (O(log n)) | §1.5.1 (L145-153): *"Tier 1 — Block Ring Buffer... Tier 2 — Epoch Queue... Tier 3 — Overflow Sorted Set"* | Timer 实现为简单的 `schedule_timer(height, payload)` 和 `set_timer` / `remove_timer` 存储层直接写入/读取，无分层结构 | `node` 仓库, [pvm_host.rs](file:///home/ubuntu/cowboyinc/node/chain/src/pvm_host.rs#L414) — `schedule_timer()` 直接存入 storage; [execution.rs](file:///home/ubuntu/cowboyinc/node/chain/src/execution.rs#L1107-L1129) — 直接遍历 timer | **数据结构差异**: 白皮书设计了高性能分层队列结构，代码采用扁平化存储（无 Ring Buffer / Epoch Queue / Overflow Set 分层） |
| 3 | Timer **速率限制**: 每个 Actor 最多 **256** 个活跃 timer | §1.5.1 (L181): *"Per‑actor timer limit: 256 active timers."* | 代码中 `schedule_timer` 无数量限制检查，任意 Actor 可以无限创建 timer | `node` 仓库, [pvm_host.rs](file:///home/ubuntu/cowboyinc/node/chain/src/pvm_host.rs#L414) 和 `pvm` 仓库, [module.rs](file:///home/ubuntu/cowboyinc/pvm/crates/pvm-runtime/src/module.rs#L99-L104) | **缺少限制**: 无 per-actor timer 数量上限检查 |
| 4 | Timer **递进押金**: `deposit(n) = base_deposit × (1 + floor(n / 100))` | §1.5.1 (L170-171): *"Progressive deposit: deposit(n) = base_deposit × (1 + floor(n / 100))"* | `schedule_timer` 不收取任何押金 | `node` 仓库, [pvm_host.rs](file:///home/ubuntu/cowboyinc/node/chain/src/pvm_host.rs#L99-L104) — `schedule_timer()` 无押金逻辑 | **缺少机制**: 无递进押金实现 |
| 5 | Timer **同块指数附加费**: `surcharge(k) = base_cost × 2^max(0, k - 16)` | §1.5.1 (L174-175): *"Exponential same‑block surcharge: surcharge(k) = base_cost × 2^max(0, k - 16)"* | 无同块附加费计算逻辑 | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/chain/src/execution.rs) — 整个文件中无 surcharge 相关逻辑 | **缺少机制**: 无 DoS 防护附加费 |
| 6 | World State 映射: `State : Address → { balance, nonce, code_hash?, storage?, metadata }` | §1.4 (L121): *"State : Address → { balance, nonce, code_hash?, storage?, metadata }"* | Account 结构仅含 `nonce` 和 `balance`（L1203-1207）；Actor 结构含 `code_hash`, `code`, `storage`, `mailbox`, `balance`, `nonce`，但**无 `metadata` 字段** | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L1013-L1021) — Actor struct; [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L1203-L1207) — Account struct | **字段缺失**: Actor 有 `code_hash` 但缺少 `metadata`；Account 缺少 `code_hash`（符合设计，EOA 无代码）和 `metadata` |
| 7 | Runner 信任模型包含 **TEE 验证** 和 **ZK-Proof (v2)** | §1.9 (L341-354): *"TEE Attestation: Execution within a Trusted Execution Environment..."*; *"ZK‑Proof (v2): Runners provide zk‑SNARKs"* | TEE 验证有数据结构定义 (`TeeAttestation`, `TeeType` 含 Sgx/Tdx/Sev)，但 `runner-tee` crate 仅有骨架代码；ZK-Proof 无任何实现 | `runner` 仓库, [types.rs](file:///home/ubuntu/cowboyinc/runner/crates/runner-common/src/types.rs#L674-L685) — `TeeAttestation` 结构; `runner` 仓库, `crates/runner-tee/` 目录 | **部分实现**: TEE 有类型定义但实现不完整；ZK-Proof 完全未实现 |
| 8 | Secrets 通过**系统 Actor `0x08`** 管理，使用 TEE 加密解密 | §9 (L928): *"0x08 Secrets Manager: Secure credential storage and access control for TEE runners."* | Secrets Manager 只有 trait 定义和空的 stub 实现，所有方法体为 `Ok(())` + TODO 注释 | `runner` 仓库, [manager.rs](file:///home/ubuntu/cowboyinc/runner/crates/secrets-manager/src/manager.rs#L60-L116) — `SecretsManagerImpl` 全部为空实现 | **stub 实现**: 接口层定义了，但存储/加密/TEE 验证逻辑全部为空 |
| 9 | SDK 命名为 **`cowboy_sdk`** / **`cowboy-py`** | §1.7.1 (L258-259): *"ordered_set from cowboy_sdk.collections"*; §10 (L932): *"A primary Python SDK (cowboy-py) is provided."* | 代码使用 `pvm_sdk` 命名，包含子模块: pvm_time, pvm_random, pvm_sys, runtime, continuation, runner, actor, verify, types | `pvm` 仓库, [determinism.rs](file:///home/ubuntu/cowboyinc/pvm/crates/pvm-runtime/src/determinism.rs#L81-L91) — whitelist 中的 pvm_sdk 子模块 | **命名不一致**: 白皮书使用 `cowboy_sdk` / `cowboy-py`，代码使用 `pvm_sdk` |
| 10 | 交易编码必须使用 **canonical CBOR** (RFC 8949) | §2.5 (L657-669): *"Transactions MUST be encoded as canonical CBOR (RFC 8949, deterministic encoding)"* | `pvm_executor.rs` 的 whitelist 中包含 `cbor2`，但 node 仓库的交易序列化/反序列化未使用 CBOR，Transaction 使用自定义二进制编码 (`Digestible`, `Read/Write` traits) | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs) — Transaction 的 Read/Write impl (自定义格式); `pvm` 仓库, [pvm_executor.rs](file:///home/ubuntu/cowboyinc/node/chain/src/pvm_executor.rs#L130) — cbor2 在 PVM whitelist 中 | **编码差异**: 白皮书指定 CBOR 编码，代码使用自定义二进制格式 |
| 11 | Transaction 必须包含 **chain_id, to, value, tip_per_cycle, tip_per_cell, access_list** | §2.1 (L634-636): *"A transaction MUST include: chain_id, nonce, to, value, cycles_limit, cells_limit, max_fee_per_cycle, max_fee_per_cell, tip_per_cycle, tip_per_cell, access_list?, payload, signature"*; Appendix A (L1279-1292): Test Vector 1 包含所有字段 | Transaction struct 仅包含: `nonce`, `instruction`, `cycles_limit`, `cells_limit`, `max_fee_per_cycle`, `max_fee_per_cell`, `public`, `signature`, `additional_signers`, `origin_tx_hash`, `origin_remaining_cycles/cells`。**缺少 6 个必填字段** | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L28-L55) — Transaction struct | **结构差异**: 缺少 `chain_id`（无跨链重放保护）、`to`（20 字节目标地址）、`value`（转账金额）、`tip_per_cycle/cell`（小费字段）、`access_list` |
| 12 | 地址为 **20 字节**，Actor 地址 CREATE2 风格推导 | §1.4 (L118): *"Each object has a 20‑byte address"*; §2.5 (L664): *"to is a 20‑byte address"* | 地址使用 **32 字节** ed25519 PublicKey；Actor 地址通过 `SHA256(creator||salt||code_hash)` → `ed25519::PrivateKey::from_seed()` → PublicKey 推导 | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L983-L1009) — `derive_actor_address()` | **地址格式**: 白皮书 20 字节 vs 代码 32 字节；推导方法也不同（SHA256+ed25519 seed vs keccak256） |
| 13 | 签名哈希使用 **keccak256** | §2.5 (L668-669): *"The signing hash MUST be keccak256(CBOR(Tx_without_signature))"* | Transaction digest 使用 `SHA256`；Tx.digest() 直接 SHA256 所有字段 | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L438-L457) — `Digestible for Transaction` | **哈希函数**: 白皮书指定 keccak256，代码使用 SHA256 |
| 14 | API 成本表: `send_message()` = **1,000 cycles**; `storage_read()` = **500 cycles + 1/byte**; `storage_write()` = **5,000 cycles + 10/byte** | §17.3 (L1137-1145): Actor API Costs 表 | `GasCosts` 默认值: `actor_message_send_cycles` = **10,000**; `storage_read_cycles` = **50**; `storage_write_cycles` = **10,000**; PVM host 的 `state_set` 收费 `100 + value.len * 10` (cells)，`state_get` **不收费** | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/chain/src/execution.rs#L85-L121) — GasCosts defaults; [pvm_host.rs](file:///home/ubuntu/cowboyinc/node/chain/src/pvm_host.rs#L300-L319) — 实际收费逻辑 | **费用差异**: send_message 10× 偏高, storage_read 10× 偏低, storage_write 2× 偏高。且 PVM host 的 state_get 不收 cycles（白皮书要求 500 cycles） |
| 15 | Transfer 内在成本 = **21,000 cycles + 0 cells** | §17.2 (L1119-1121): *"Transfer 21,000 0 EOA-to-EOA value transfer"* | `GasCosts::transfer_cycles` = **10,000** cycles; `transfer_cells` = **1,000** cells | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/chain/src/execution.rs#L92-L95) — `transfer_cycles: 10_000, transfer_cells: 1_000` | **参数差异**: Transfer cycles 偏低 (10K vs 21K)，且白皮书指定 cells=0 但代码收取 1,000 cells |
| 16 | 随机数: 验证者使用 **threshold-BLS VRF** 产生 `R_n = VRF_sk_epoch(QC_{n-1})`，Actor 调用 `HKDF(R_n, label)` | §3.4 (L720-721): *"Validators MUST generate a threshold‑BLS VRF per block"* | `randomness()` 实现为 `SHA256(block_hash || domain)` — 无 VRF、无 threshold BLS、无 HKDF | `node` 仓库, [pvm_host.rs](file:///home/ubuntu/cowboyinc/node/chain/src/pvm_host.rs#L384-L395) — `randomness()` | **随机源差异**: SHA256(block_hash) 不具备 VRF 的不可预测性保证，可被区块提议者操纵 |
| 17 | PVM 白名单应包含 `decimal`；**禁止** `weakref`, `_weakref`, `_weakrefset`, `_thread` | §1.7.1 (L270): Module Whitelist 含 `decimal`; §1.7.1 (L285): *"weakref.\* (non‑deterministic collection timing)"* — Forbidden; §1.7.1 (L286): *"threading.\*, multiprocessing.\*, concurrent.\*"* — Forbidden; §1.7.1 (L284): *"gc.\*"* — Forbidden | 白名单包含 `weakref`(L67), `_weakref`(L66), `_weakrefset`(L65), `_thread`(L68) — 均为白皮书明确禁止的模块；白名单**缺少** `decimal`; 黑名单**缺少** `gc`, `concurrent` | `pvm` 仓库, [determinism.rs](file:///home/ubuntu/cowboyinc/pvm/crates/pvm-runtime/src/determinism.rs#L24-L131) — whitelist (L24-L96) 和 blacklist (L102-L131) | **确定性风险**: `weakref`/`_thread` 在白名单中（白皮书明确禁止），可引入非确定性; `decimal` 缺失影响确定性浮点计算 |
| 18 | Block 结构应包含 **VRF output/proof** | §6.1 (L801-814): Simplex BFT 共识, L813: *"Each block header MUST include the proposer's VRF output and proof"*; §3.4 (L720): *"threshold-BLS VRF per block"* | Block struct 仅含 `parent`, `height`, `timestamp`, `transactions`, `digest` — 无 VRF output/proof/proposer_signature 字段 | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L764-L780) — Block struct | **共识数据缺失**: Block 无法携带 VRF 信息用于链上验证和随机数生成 |

---

## 表二：白皮书中有定义，但代码中未实现的功能

| # | 白皮书定义 | 白皮书位置 | 期望实现位置 | 说明 |
|---|----------|-----------|------------|------|
| 1 | **Gas Bidding Agent (GBA)**: Actor 动态竞价 timer 执行优先级 | §1.5.1 (L155-161): *"GBA — another actor that dynamically bids for timer execution on its behalf"* | 预期在 `node` 仓库 `chain/src/execution.rs` | 白皮书描述了完整的 GBA 竞价机制（read-only call, 返回 competitive bid, intra-block auction），代码中完全没有此机制 |
| 2 | **分层日历队列 (Tiered Calendar Queue)** | §1.5.1 (L145-153): 三层 timer 存储结构 | 预期在 `node` 仓库 `chain/src/` | 白皮书定义了 Block Ring Buffer + Epoch Queue + Overflow Sorted Set，代码采用扁平存储 |
| 3 | **ZK-Proof 验证模式 (v2)** | §1.9 (L350): *"ZK‑Proof (v2): Runners provide zk‑SNARKs for cryptographic verification"* | 预期在 `runner` 仓库 `crates/` 中新增 crate | 白皮书提到 v2 版本将支持 ZK-Proof，当前代码无任何 ZK 相关实现 |
| 4 | **Oracle Snapshot Modes**: `first_valid`, `median`, `majority`, `latest` | §1.9.3 (L452-454): *"first_valid, median, majority, or latest"* | 预期在 `runner` 仓库 `crates/runner-http/` | 白皮书定义了四种快照聚合模式，代码中无任何 Snapshot Mode 实现 |
| 5 | **Extraction-Based Verification**: 结构化网页数据提取验证 | §1.9.3 (L455-457): *"runners apply extraction rules (CSS selectors, XPath, JSONPath, regex)"* | 预期在 `runner` 仓库 `crates/runner-http/` | 有 `ExtractionConfig` 类型定义但无实际提取验证逻辑 |
| 6 | **系统 Actor `0x08` (Secrets Manager)** 链上注册与指令 | §9 (L928): *"0x08 Secrets Manager"* | 预期在 `node` 仓库 `chain/src/execution.rs` | `SystemInstruction` 枚举无 Secret 相关操作，也无 `0x08` 系统 Actor 注册 |
| 7 | **Secret 链上加密存储** | §9 (L928): Secrets Manager 定义 | 预期在 `node` 仓库和 `runner` 仓库 | 链上无 Secret 加密存储实现；Runner 端全部为空实现 |
| 8 | Timer **递进押金**和**同块附加费**公式 | §1.5.1 (L170-175): deposit(n) 和 surcharge(k) 公式 | 预期在 `node` 仓库 `chain/src/execution.rs` 或 `pvm_host.rs` | 白皮书定义了详细的经济模型公式，代码无任何实现 |
| 9 | Timer **Per-Actor 256 上限**限制 | §1.5.1 (L181): *"Per‑actor timer limit: 256 active timers"* | 预期在 `node` 仓库 `chain/src/pvm_host.rs` 的 `schedule_timer` 中 | 代码中无 Actor timer 数量限制检查 |
| 10 | **`set_interval` API**: 周期性定时器 | §3.3 (L711-712): *"timer_id = set_interval(every_n_blocks, handler, data)"* | 预期在 `node` 仓库 PVM host 函数和 `pvm` 仓库 module.rs | `node` 和 `pvm` 仓库中无 `set_interval` 实现（仅 `cowboy` 仓库有定义），只有 `set_timer` 一次性定时器 |
| 11 | **Entitlements 权限系统 (§15)**: Actor/Runner 声明式权限框架 | §15 (L1016-1042): *"A declarative, composable permissions system governs the capabilities of actors and runners."* 含 4 条 MUST 规则 | 预期在 `node` 仓库 (部署时检查) 和 `runner` 仓库 (调度匹配) | `node` 仓库无任何 `entitlement` 引用；`runner` 仅在 `SecretsManagerImpl` 有一个 `entitlements: Vec<String>` 字段。白皮书定义的完整权限框架（requires ⊆ provides 匹配、syscall gate 强制执行、inheritable 传递）完全未实现 |
| 12 | **Ethereum 互操作 (§16)**: 账户统一、Bridge、EventListener (0x06) | §16 (L1044-1094): *"Account Unification"* (secp256k1 共用), *"Bridge Infrastructure"* (wETH/wERC-20, cross-chain messaging), *"Event Subscription"* (0x06 EventListener) | 预期在 `node` 仓库系统 Actor 和新增 bridge 模块 | 代码中无 bridge 相关代码、无 EventListener 系统 Actor、无 EIP-712 验证 host call。由于密码学方案也不同（Ed25519 vs secp256k1），整个互操作层未实现 |
| 13 | **CIP-20 Platform Token 操作** | §17.3 (L1147-1162): `token_transfer()`, `token_mint()`, `token_burn()`, `token_create()`, `token_approve()`, `token_balance_of()`, `token_transfer_from()` | 预期在 `node` 仓库 Actor API 层 | 白皮书定义了完整的 platform token 操作及其 cycle/cell 成本，代码中无任何 token 相关实现 |
| 14 | **Dedicated Lanes (专用通道)**: System 5%, Timer 20%, Runner 25%, User 50% | §6.3 (L827-844) 和 §17.9 (L1236-1249): 含具体 cycle budget (500K/2M/2.5M/5M) | 预期在 `node` 仓库 `chain/src/execution.rs` 的交易选择和调度逻辑中 | 代码中无 `lane` 概念，所有交易同等处理，无 lane 分区、优先级、fee multiplier |
| 15 | **Inflation 通胀计划**: Year 1-2: 8%, Year 3-4: 5%, ... Year 10+: 1% | §8.2 (L902-908): 递减通胀时间表 | 预期在 `node` 仓库共识或经济模块 | 代码中无 `inflation` 相关逻辑，无区块奖励铸造 |
| 16 | **State Rent (状态租金)**: 基于状态大小动态调整的租金机制 | §1.12.2 (L555-569), §4.4 (L761-763), §17.5 (L1173-1188): 含 grace period, eviction, rent formula | 预期在 `node` 仓库 storage 层 | 代码中无 `rent` 相关逻辑，无 grace period/eviction/rent epoch 实现 |
| 17 | **Slashing (罚没)**: Double signing → slash 1%, extended downtime → jail | §1.11.3 (L503-516): *"Double signing: Jail + slash 1% of stake"* | 预期在 `node` 仓库共识模块 | 代码中无 `slashing`、`slash`、`challenge` 相关逻辑 |
| 18 | **Governance (治理)**: Foundation 5-of-9 multisig → on-chain governance, 7-day timelock | §11 (L938-943): *"Foundation 5‑of‑9 multisig sunsets after ~12 months"* | 预期在 `node` 仓库 | 代码中无 `governance` 相关逻辑 |
| 19 | **消息去重 (Message Dedup)**: per-actor dedup set, 至少 `dedup_window` 保留 | §3.3 (L696-699): *"message ID MUST be keccak256(sender||nonce||msg_hash) and recorded in a per‑actor dedup set"*; §13 (L975-976): *"dedup_window = 10,000 blocks"* | 预期在 `node` 仓库 execution 层的消息处理 | `execution.rs` L217 有 `// Message deduplication set (cross-transaction)` 注释，但无完整的 per-actor dedup set 实现和 10,000 blocks 窗口 |
| 20 | **Blob Store 系统 Actor `0x04`** | §9 (L924): *"0x04 Blob store: Commit/retrieve blob multihashes."*; §7 (L887-896) | 预期在 `node` 仓库系统 Actor | 代码中无 blob store 系统 Actor 和 multihash commit/retrieve 功能 |
| 21 | **PVM Host API**: `get_balance()`, `transfer()`, `read_mailbox()`, `log()`, `verify_signature()`, `hash()` | §3.3 (L694-716): Messaging/Reentrancy/Timers API; §17.3 (L1139-1145): Actor API Costs 含 `send_message`, `storage_read/write`, `hash()`, `verify_signature()`, `get_block_info()`, `emit_event()` | PVM host 已实现: `get_state/set_state/delete_state/emit_event/charge_gas/gas_left/context/randomness/send_message/schedule_timer/cancel_timer/submit_job/create_deferred_tx`。`context()` 已提供 `actor_addr`（≈self_address）和 `block_height/block_hash`（≈get_block_info）。**仍缺少**: `get_balance`, `transfer`, `read_mailbox`, `verify_signature`, `hash`, `log` |
| 22 | **Basefee 调整逻辑** (EIP-1559 双通道独立) | §17.8 (L1220-1231): *"next_basefee = basefee × (1 + δ × (usage - target) / target)"*, Cycle target=10M, Cell target=500K, δ=0.125 | 预期在 `node` 仓库出块逻辑中 | 代码中无任何 `basefee` / `base_fee` 相关逻辑，无费用调整，用户的 `max_fee_per_cycle/cell` 不参与 EIP-1559 机制 |
| 23 | **chain_id 重放保护** | §2.1 (L634): *"chain_id"* 为必填字段; §2.5 (L661): CBOR 数组第一个字段 | 预期在 Transaction struct 和签名验证中 | 代码中无 `chain_id` 概念，Transaction payload 不包含 chain_id，无跨链重放保护 |
| 24 | **Per-Tx 消息扇出限制: 1,024** | §1.5 (L136-137): *"a transaction (including all nested sends) MUST NOT enqueue more than 1,024 messages"* | 预期在 `node` 仓库 execution 的消息处理中 | `send_message` 无扇出计数或限制检查 |
| 25 | **Reentrancy 递归深度限制 = 32** | §3.3 (L706): *"Recursion/await depth cap = 32"* | 预期在 `node` 仓库 execution 或 `pvm` runtime 中 | 代码中无重入深度计数器或递归深度限制 |
| 26 | **Per-Call 内存限制: 10 MiB** | §3.2 (L688): *"Per‑call memory limit: 10 MiB heap memory"* | 预期在 `pvm` 仓库 runtime 的 VM 初始化中 | 代码中无内存限制配置（grep 无 `memory_limit`/`heap_limit`/`10.*MiB` 匹配） |
| 27 | **Scratch Space /tmp: 256 KiB** | §3.1 (L683-684): *"Scratch space: /tmp MUST be per‑invocation, capped at 256 KiB"* | 预期在 `pvm` 仓库 filesystem 隔离中 | 代码中无 `/tmp` 配额限制或 per-invocation 清理逻辑 |
| 28 | **Runner 最低 Stake: ≥10× 平均 job 价值** | §17.7 (L1214): *"runner_stake >= 10 × average_job_value"*; 白皮书未指定具体金额 | 预期在 `node` 仓库 runner registry | 代码硬编码 `MIN_STAKE = 50_000_000_000_000`（按 L16-18 注释为 50,000 CBY），为静态值非动态计算，且白皮书要求根据 `average_job_value` 动态调整 |

---

## 表三：代码中已实现，但白皮书中未提及的功能

| # | 代码实现 | 代码位置 | 说明 |
|---|---------|---------|------|
| 1 | **MCP (Model Context Protocol) Job 类型**: 支持 MCP 服务器工具调用 | `runner` 仓库, [types.rs](file:///home/ubuntu/cowboyinc/runner/crates/runner-common/src/types.rs#L264-L274) — `JobType::Mcp`; `runner` 仓库, `crates/runner-mcp/` 完整 crate | 白皮书只提到 LLM inference 和 HTTP/API 调用，未提及 MCP 协议支持 |
| 2 | **Custom Job 类型**: 通过 executor_hash 扩展自定义任务 | `runner` 仓库, [types.rs](file:///home/ubuntu/cowboyinc/runner/crates/runner-common/src/types.rs#L276-L283) — `JobType::Custom` | 白皮书未提及可扩展的自定义任务类型 |
| 3 | **多签名交易 (Multi-Signature)**: 支持多个签名者联合签名 | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L151-L201) — `Transaction::sign_multi()`; `additional_signers` 字段 | 白皮书未描述多签名交易机制 |
| 4 | **Deferred Transaction (延迟交易)**: Actor 可创建延迟交易，继承原始交易的 gas 预算 | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L218-L264) — `Transaction::create_deferred()`; [module.rs](file:///home/ubuntu/cowboyinc/pvm/crates/pvm-runtime/src/module.rs#L118-L124) — `create_deferred_tx` PVM host 函数 | 白皮书未明确描述延迟交易机制（Section 1.6 提到 Message-Passing Continuation，但未描述 `create_deferred_tx` API 和 gas 继承） |
| 5 | **PVM Continuation 模式**: Python 执行中的 continuation 和 runtime config | `pvm` 仓库, [continuation.rs](file:///home/ubuntu/cowboyinc/pvm/crates/pvm-runtime/src/continuation.rs) — `ContinuationOptions`, `RuntimeConfig` | 白皮书只提到概念，代码有具体实现 |
| 6 | **PVM Import Guard**: 完整的模块导入拦截和别名系统 | `pvm` 仓库, [guard.rs](file:///home/ubuntu/cowboyinc/pvm/crates/pvm-runtime/src/guard.rs#L8-L163) — `_PvmImportGuard`, `_ALIAS` dict (time→pvm_time, random→pvm_random) | 白皮书提到 "strict whitelist"，但代码实现了更复杂的别名重定向系统和 trace/blocked 记录 |
| 7 | **Runner Rate Card**: 包含 LLM / HTTP / MCP / Compute 的详细定价维度 | `runner` 仓库, [types.rs](file:///home/ubuntu/cowboyinc/runner/crates/runner-common/src/types.rs#L550-L577) — `RateCard` struct | 白皮书 §17.7 仅提到 "Runners post quotes"，但未详述 Rate Card 的具体字段（llm_input_token, http_request_base, mcp_call_base 等） |
| 8 | **Runner Health / Reputation 系统**: HealthStatus (Healthy/Unhealthy/Paused/Deregistered) + reputation score (0-100) | `runner` 仓库, [types.rs](file:///home/ubuntu/cowboyinc/runner/crates/runner-common/src/types.rs#L602-L636) — `HealthStatus`, `RunnerRegistration.reputation` | 白皮书 §1.9.1 (L363-367) 提到 "reputation scoring and anomaly detection" 但未详述健康状态和评分系统 |
| 9 | **Source Attestation**: HTTP job 的源数据证明（含 TLS 证书指纹） | `runner` 仓库, [types.rs](file:///home/ubuntu/cowboyinc/runner/crates/runner-common/src/types.rs#L687-L702) — `SourceAttestation` struct | 白皮书 §1.9.3 提到 oracle 语义但未详述 Source Attestation 结构 |
| 10 | **PVM Host 函数: `randomness(domain)`**: 通过 domain 参数获取确定性随机数 | `pvm` 仓库, [module.rs](file:///home/ubuntu/cowboyinc/pvm/crates/pvm-runtime/src/module.rs#L84-L88) — `randomness` pyfunction | 白皮书 §3.4 (L720-721) 提到 `HKDF(R_n, label)` API 但未描述 PVM 层面的具体 `randomness(domain)` 接口 |
| 11 | **Block Explorer / Indexer / Scanner**: 区块浏览器、索引器、扫描器模块 | `node` 仓库, `explorer/` (33 files), `indexer/` (3 files), `scan/` (32 files), `scan-server/` (4 files) | 白皮书未描述这些基础设施组件 |
| 12 | **Runner Consensus Crate**: Runner 节点的共识模块 | `runner` 仓库, `crates/runner-consensus/` (4 files) | 白皮书未详述 Runner 之间的共识协议实现 |
| 13 | **6 种 VerificationMode 变体**: None, EconomicBond, MajorityVote, StructuredMatch, Deterministic, **SemanticSimilarity** | `runner` 仓库, [types.rs](file:///home/ubuntu/cowboyinc/runner/crates/runner-common/src/types.rs#L358-L407) — VerificationMode enum; 含 InferenceConfig / VerifierCheck / similarity_threshold | 白皮书 §5 只提到 TEE Attestation, Majority Vote, ZK-Proof(v2), Economic Bond。**SemanticSimilarity** 和 **StructuredMatch** 验证模式为代码独有 |
| 14 | **Custom Instruction 类型**: `Instruction::Custom { module, action, data }` | `node` 仓库, [execution.rs](file:///home/ubuntu/cowboyinc/node/types/src/execution.rs#L518-L523) — Custom variant | 白皮书未定义通用可扩展的自定义指令模块 |

---

## 关键发现总结

### 🔴 严重偏差（阻碍白皮书兼容性）
1. **密码学方案**: secp256k1 (ECDSA) vs Ed25519 — 基础架构级，影响以太坊互操作
2. **地址格式**: 20 字节 vs 32 字节 ed25519 PublicKey — 破坏所有地址相关规范
3. **Transaction 结构**: 缺少 `chain_id`/`to`/`value`/`tip_per_cycle`/`tip_per_cell`/`access_list` — 6 个必填字段缺失
4. **交易编码**: canonical CBOR vs 自定义二进制 — 传输层不兼容
5. **签名哈希函数**: keccak256 vs SHA256 — 签名验证不兼容
6. **Basefee 调整**: EIP-1559 双通道机制完全未实现 — 费用模型核心缺失

### 🟠 重要偏差（影响安全/确定性）
1. **随机数**: threshold-BLS VRF vs SHA256(block_hash) — 可被 proposer 操纵
2. **PVM 确定性白名单**: 包含 `weakref`/`_thread` 等非确定性模块
3. **GasCosts 参数**: 多项费用偏差 10 倍以上（transfer 10K vs 21K, storage_read 50 vs 500, send_message 10K vs 1K）
4. **Block 无 VRF**: 无法链上验证随机性
5. **无 fanout/reentrancy 限制**: 缺少 1,024 消息上限和 32 层递归深度限制
6. **无内存/tmp 限制**: 缺少 10 MiB heap 和 256 KiB scratch 限制

### 🟡 功能缺失（按重要性排序）
1. **Entitlements 权限系统** (§15)
2. **Ethereum 互操作** (§16): Bridge, EventListener, EIP-712
3. **Dedicated Lanes 专用通道** (§17.9): 4 条执行通道
4. **PVM Host API 缺失**: `get_balance`/`transfer`/`read_mailbox`/`verify_signature`/`hash`/`log`（注: `self_address` 和 `get_block_info` 已通过 `context()` 提供）
5. **Timer 全套机制**: 分层队列、GBA 竞价、递进押金、附加费、256 上限
6. **CIP-20 Platform Token 操作**
7. **State Rent**: 租金、eviction、grace period
8. **Inflation / Block Rewards**
9. **Slashing / Governance**
10. **chain_id 重放保护**
11. **Oracle Snapshot Modes**
12. **ZK-Proof (v2)**
13. **`set_interval` 周期性定时器**
14. **Blob Store `0x04`** / **Secrets Manager `0x08`**
15. **消息去重 dedup set** / **Scratch space /tmp 隔离**
16. **Runner 动态 Stake 要求** (≥10× avg job value)

### 🟢 代码超前实现
1. **MCP 支持**: 完整的 MCP 工具调用 job 类型
2. **多签名交易**: 完整的多签支持
3. **延迟交易**: 完整的 deferred transaction 机制
4. **PVM Import Guard**: 精细的模块别名重定向系统
5. **Runner Rate Card / Health / Reputation**: 比白皮书更详细
6. **VerificationMode**: SemanticSimilarity 和 StructuredMatch 为代码独有
7. **Custom Instruction**: 通用可扩展指令模块
