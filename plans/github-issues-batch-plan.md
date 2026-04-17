# GitHub Issues 分类与批量实施计划

## Context

对 `cowboyinc/node` 仓库的 95 个未关闭 Issue 进行分类分析，找出可合并处理的同类问题，制定优先级批次计划。探索结果显示：部分安全审计 Issue 已自然修复，其余问题按文件/模块聚合度较高，适合按批次并行实施。

---

## 一、安全审计 Issue 分类（共 29 个）

### 1-A：Inspector 恐慌修复（#256, #257, #259）
**可合并为 1 个 PR**

**文件：`/node/inspector/src/main.rs`**
- #259: `from_hex_formatted(identity).expect(...)` + `Identity::decode(...).expect(...)` → 用户输入触发 panic
- #257: `message.expect("Failed to receive message")` → 网络流错误触发 panic
- #256: `client.seed_get(query).await.expect(...)` × 多处 → HTTP 返回错误触发 panic

**实现**：将全部 `.expect()` 替换为 `match` / `?` 传播，返回友好 JSON 错误。
**难度**：极低（单文件，纯 Rust 错误处理）

---

### 1-B：RPC CORS 配置修复（#232, #233）
**可合并为 1 个 PR**

**文件：`/node/rpc/src/rpc.rs:187`**
- 现状：`CorsLayer::permissive()` — 允许任意来源
- 对比：`/node/indexer/src/lib.rs:574-577` 已实现基于 `CORS_ALLOWED_ORIGINS` 环境变量的白名单模式

**实现**：将 RPC 的 CorsLayer 迁移为与 Indexer 相同的环境变量配置方案。
**难度**：低（模式已有参考）

---

### 1-C：Shell 脚本安全加固（#251, #255, #263, #262, #261, #265）
**可合并为 1 个 PR**

**文件：`/node/scripts/` 目录**（restart_validator.sh, start_validator.sh, register_runner.sh）
- #263: `rm -rf test/*.db` 相对路径 → 改为 `"$ROOT_DIR/test/"` 绝对路径
- #255: `pkill -f "validator.*--config"` 模式过宽 → 改用 PID 文件或更精确模式
- #251: grep+awk 提取 PID 不稳定 → 改用 `pgrep -x` 或 PID 文件
- #262: curl 中的 `$RPC_URL` 可能被注入选项 → 验证 URL scheme（必须 http/https）
- #261: JSON 模板中变量未充分转义 → 统一使用 `jq` 构造 JSON 或 printf 转义
- #265: `tail -50 validator.log` 可能追踪符号链接 → 增加 `-L` 检测或 readlink 验证

**难度**：低（脚本编辑，每项几行）

---

### 1-D：日志/信息泄露（#238, #264, #246）
**可合并为 1 个 PR**

**文件：多处**
- #238: 私钥出现在 tracing span 或日志中 → 为 `PrivateKey` 实现 `Debug`/`Display` 时只显示 `[REDACTED]`；检查 `scripts/register_runner.sh:235`
- #264: `rpc/src/error.rs` 的 `raw_error` 字段将 PVM 错误原文返回给客户端 → 在 non-dev 模式下从 `details` 中删除 `raw_error` 字段
- #246: 大型提交内容被全量记录，填满磁盘 → 在日志中截断超长 payload（如 > 512 bytes 只打印长度）

**难度**：低

---

### 1-E：加密/认证弱点（#253, #247）
**独立 PR，暂缓**

- #253: 16-bit checksum 允许密钥替换 — 需评估 checksum 算法，改为更强哈希（cryptographic MAC）
- #247: 确定性 genesis 领导者密钥 — 设计级别问题，需单独 RFC，风险高

**暂缓原因**：影响核心密钥安全设计，需要独立评审。

---

### 1-F：已自然修复的审计项（#234, #235, #237, #240）
**无需实施**

探索确认：
- #237/235/234: Indexer 已有 `MAX_TX_LIMIT=1000`, `default_tx_limit()=10`, 翻页保护
- #240: RPC 已有 `DefaultBodyLimit::max(1_048_576)` 1MB 请求体限制

**建议**：关闭这 4 个 issue，说明已通过现有代码满足。

---

### 1-G：未在代码库中找到对应实现点（#236, #254, #260, #248, #258, #239）
**需进一步调查**

- #236 (unbounded get_blocks) — 未找到 `get_blocks` 端点，可能在 commonware 上游
- #254 (PEM 解析) — 未找到 PEM 解析代码
- #260 (vector encoding in entitlement) — 未定位
- #248 (TLS expect) — 未找到 TLS 中的 expect
- #258 (WASM leader selection panic) — WASM 共识逻辑在外部依赖
- #239 (config path overwrite) — 需进一步定位

**建议**：逐一在上游 (commonware) 仓库追踪，或请 issue 提交者补充复现路径。

---

## 二、协议功能 Issue 分类（共 66 个）

### 2-A：Receipt 丰富化（#24, #44, #75, #90, #103）
**可合并为 1 个 PR**

**文件：`/node/storage/src/types.rs`（TransactionReceipt，lines 378-495）**

所有 5 个 issue 都是向同一个 struct 增加字段：
| Issue | 字段 | 说明 |
|-------|------|------|
| #75 | `cumulative_cycles_used: u64`, `cumulative_cells_used: u64` | 块内累计 gas |
| #103 | `logs_root: Digest` | 事件日志的 keccak256 根哈希 |
| #90 | `bloom: [u8; 256]` | 事件 Bloom 过滤器（EIP-2 style） |
| #24 | `post_tx_state_root: Digest` | 交易后状态根（需执行层配合输出） |
| #44 | Merkle proof 生成函数 | 基于 receipt_root 生成包含证明 |

**实施顺序**：#75 → #103 → #90（三者仅需 struct 字段 + 计算）→ #24（需执行层传出 state root）→ #44（需 Merkle 树工具函数）

**难度**：中（#24 需执行层修改；#44 需 Merkle 库）

---

### 2-B：Block 结构增强（#28, #39, #63, #94）
**2 个 PR**

**PR B-1：Block 字段 + 签名验证（#39, #63）**
文件：`/node/types/src/execution.rs`（Block struct, lines 1210-1420）
- #63: 增加 `version: u8` 字段到 Block header
- #39: 增加 `producer_signature: EthSignature` 字段；在 `validate()` 中验证

**PR B-2：Block 验证方法（#28）+ 紧凑表示（#94）**
- #28: 实现 `Block::validate()` 方法（检查 tx 数量、hash 一致性、签名、height 连续性）
- #94: 新增 `CompactBlock { header: BlockHeader, tx_hashes: Vec<Digest> }` struct

**难度**：中

---

### 2-C：Transaction 类型系统（#81, #101）
**可合并为 1 个 PR**

**文件：`/node/types/src/execution.rs`（Transaction struct, lines 66-99）**
- #101: 增加 `version: u8` 字段（当前默认 0）
- #81: 新增 `TransactionEnvelope` enum：
  ```rust
  enum TransactionEnvelope {
      Legacy(Transaction),       // version 0
      EIP1559(Transaction),      // version 1 (已有 priority fee 字段)
  }
  ```
- #133（Access list）：预留字段 `access_list: Option<Vec<AccessEntry>>`，暂不实现逻辑（reserved）

**难度**：中（需更新所有序列化/反序列化路径）

---

### 2-D：Mempool 增强（#65, #77, #95）
**可合并为 1 个 PR**

**文件：`/node/chain/src/mempool.rs`（单文件 860 行）**
- #95: 增加 `max_size_bytes: usize` 字段，跟踪 `current_size_bytes`，`add()` 时检查
- #65: 在 `next()` 中扩展优先级评分（当前仅按 fee；增加 fee_per_byte + age 复合分）
- #77: 实现 eviction 策略：当 size 超限或 backlog 满时，驱逐得分最低的 tx（当前直接丢弃最远 nonce）

**难度**：低（单文件，逻辑相对独立）

---

### 2-E：RPC/API 扩展（#97, #110, #131）
**2 个 PR**

**PR E-1：批量请求 + API 版本（#97, #131）**
文件：`/node/rpc/src/rpc.rs`
- #131: 在所有响应中增加 `X-API-Version` 头，或增加 `/version` 端点
- #97: 增加 `/batch` POST 端点，接收 `Vec<Request>`，串行执行并返回 `Vec<Response>`

**PR E-2：WebSocket 订阅（#110）**
文件：新增 `/node/rpc/src/ws.rs`
- 实现 `ws://host/subscribe/{topic}` 端点（blocks, transactions, events）
- 参考现有 mempool_listener 的 WebSocket 实现

**难度**：中（E-1 低；E-2 中高）

---

### 2-F：Timer 系统完善（#26, #35, #41, #47, #57, #85, #118）
**3 个 PR，按依赖顺序**

**PR F-1：基础约束（#35, #114 部分）**
文件：`/node/execution/src/pvm_host.rs`, `/node/storage/src/timers.rs`
- #35: `schedule_timer` 时检查 actor 已有定时器数量（max 1024），超出返回错误

**PR F-2：经济模型（#41, #47, #85）**
文件：`/node/execution/src/pvm_host.rs`, `/node/execution/src/basefee.rs`
- #85: 将 Timer 操作接入 DualBasefee（动态 base fee）
- #47: 同块内多次调度定时器使用指数递增价格
- #41: 注册定时器时收取押金（deposit），存入系统账户，触发后退还

**PR F-3：长期定时器索引（#57, #118）+ 即时触发（#26）**
文件：`/node/storage/src/timers.rs`
- #118: 超长期定时器（> N 块）使用溢出排序集（BTreeMap by height）
- #57: 中期定时器（N-1000 块）使用 epoch 队列批处理
- #26: 实现 immediate timer ring buffer（same-block 触发）

**难度**：F-1 低；F-2 中；F-3 高（架构设计复杂）

---

### 2-G：Mailbox 系统完善（#21, #37, #69, #80, #88, #100, #107, #114）
**2 个 PR**

**PR G-1：队列增强（#21, #37, #69, #100）**
文件：`/node/storage/src/mailbox.rs`, `/node/storage/src/types.rs`（Message struct）
- #100: Message 增加 `correlation_id: Option<Digest>` 字段
- #69: Message 增加 `priority: u8` 字段；mailbox 改为分优先级 VecDeque
- #37: 增加 `sequence_num: u64` 字段保证消息全序
- #21: 上述字段补充后，VecDeque 结构趋于完整

**PR G-2：生命周期（#80, #88, #107, #114）**
文件：`/node/storage/src/mailbox.rs`
- #80: Message 增加 `expiry_height: Option<u64>`；collect_deferred_transactions 时跳过过期消息
- #107: 处理失败的消息移入 `dead_letter_queue: VecDeque<Message>`（per-actor）
- #114: Actor 删除时调用 `clear_mailbox(actor_address)` 清理
- #88: mailbox 读写使用细粒度锁（或 actor-level 版本号保护 CAS）

**难度**：中

---

### 2-H：DeferredTx 系统完善（#22, #32, #56, #70, #83, #89, #96）
**2 个 PR**

**PR H-1：调度 API（#22, #32, #70）**
文件：`/node/execution/src/pvm_host.rs`, `/node/types/src/execution.rs`
- #22: 实现 `schedule_deferred_tx(target_height, handler, payload)` host function
- #32: 在 create_deferred 路径增加 `target_height` 字段校验（must be > current_height）
- #70: 实现 `cancel_deferred_tx(deferred_tx_hash)` host function

**PR H-2：管理与查询（#56, #83, #89, #96）**
文件：`/node/execution/src/execution/engine.rs`
- #96: `pending_deferred_txs` 从 HashMap 改为 `BTreeMap<Priority, Transaction>` 优先队列
- #56: 增加 `MAX_PENDING_DEFERRED_TXS = 10_000` 上限检查
- #89: DeferredTx 增加 `expiry_height: u64`；执行前检查过期
- #83: 增加 `/deferred/{hash}` RPC 端点查询状态（pending/executed/failed/expired）

**难度**：中

---

### 2-I：Gas/GasCost 完善（#27, #36, #42, #59, #84）
**2 个 PR**

**PR I-1：计量精度（#36, #42）**
文件：`/node/execution/src/pvm_host.rs`, `/node/execution/src/gas.rs`
- #36: `call_actor()` 入口对 calldata（参数字节）收取 cells 费用
- #42: 统一 host function 调用基础成本到 `GasCosts` struct（当前部分是硬编码数字）

**PR I-2：估算与退款（#59, #84）**（暂缓 #27）
文件：`/node/execution/src/execution/engine.rs`, `/node/rpc/src/handlers/`
- #84: Receipt 增加 `gas_refund: u64`；执行完成后退还未使用的 sub-allocation
- #59: 增加 `/estimate_gas` 端点（dry-run 执行，不提交状态变更，返回 cycles/cells 用量）
- #27（Python bytecode costs）：需单独计划，依赖 PVM 字节码规范，暂缓

**难度**：I-1 低；I-2 中

---

### 2-J：PvmHost 存储隔离（#34, #43）
**可合并为 1 个 PR**

**文件：`/node/execution/src/pvm_host.rs`**
- #34: `storage_read/storage_write` 增加 actor 地址前缀隔离（`prefix = keccak256(actor_addr)[:4]`）
- #43: Actor state 增加 `storage_quota: u64`；每次写入后检查已用空间是否超配额

**难度**：中（需更新所有存储 key 格式，有数据迁移影响）

---

### 2-K：Genesis 根哈希计算（#29, #67）
**可合并为 1 个 PR**

**文件：`/node/chain/src/genesis.rs`, `/node/chain/src/application.rs:71-87`**
- #67: 在 `make_genesis()` 中计算 genesis block hash（当前 `Sha256Digest::EMPTY`）
- #29: 在 genesis 初始化账户后，计算 state root（Merkle Patricia Trie 或简化 keccak hash）

**难度**：中（#67 低；#29 依赖是否需要完整 MPT）

---

### 2-L：Engine 可观测性（#62, #68, #104, #144）
**可合并为 1 个 PR**

**文件：`/node/chain/src/engine.rs`, `/node/chain/src/application.rs`**
- #68 + #104: 增加 Prometheus metrics：`block_production_total`, `block_production_duration_seconds`
- #62: 实现 graceful shutdown（监听 SIGTERM → drain mempool → 等待当前块完成 → 退出）
- #144: 增加 `pause_production: bool` 控制标志（通过 Admin RPC `/admin/pause` 设置）

**难度**：中

---

### 2-M：Application 块约束（#23, #145）
**合并为 1 个 PR**

**文件：`/node/types/src/execution.rs`, `/node/storage/src/speculative.rs`**
- #23: 在 `Block::new()` 和 block validation 中增加字节大小限制（`MAX_BLOCK_BYTES = 4_194_304` 4MB）
- #145: 在 `finalize_block_basefee` 后增加 block reward placeholder（向 proposer 地址转固定奖励或 0，留 TODO）

**难度**：低

---

### 2-N：Transaction 编码优化（#151）
**独立 PR，低优先级**

文件：`/node/types/src/execution.rs` 编码路径
- 评估 CBOR vs 自定义二进制编码的大小差异
- 分析 `extra_data`, `metadata`, `additional_signers` 等字段的压缩空间

**难度**：中（需基准测试）

---

### 2-O：CLI tx 签名命令（#82）
**独立 PR**
文件：`/node/cli/` 或 cowboy-cli 目录
- 实现 `cowboy tx sign --key ... --tx ...` 命令

---

### 2-P：文档类（#18, #38, #61, #78, #98, #102, #122）
**合并为持续维护任务**
- 7 个文档 issue：quick start、API reference、Actor tutorial、deployment guide、config reference、troubleshooting、code examples
- 建议单独文档 repo 或 docs/ 目录，批量完成

---

### 2-Q：Demo 脚本（#87, #93）
**合并为 1 个 PR**
- #87: tx demo script
- #93: deferred tx demo（待 H-1 完成后实现）

---

## 三、全部 Issue 分组总览

| 批次 | Issue 编号 | 数量 | 聚合依据 | 优先级 | 难度 |
|------|-----------|------|---------|-------|------|
| **1-A** | #256, #257, #259 | 3 | 同文件 inspector/src/main.rs | 🔴 高 | 极低 |
| **1-B** | #232, #233 | 2 | 同模式 CorsLayer | 🔴 高 | 低 |
| **1-C** | #251, #255, #263, #262, #261, #265 | 6 | 同目录 scripts/ | 🔴 高 | 低 |
| **1-D** | #238, #264, #246 | 3 | 同类 logging leakage | 🟠 中 | 低 |
| **1-E** | #253, #247 | 2 | 加密设计缺陷 | 🔴 高 | 高 |
| **1-F** | #234, #235, #237, #240 | 4 | **已修复，直接关闭** | — | — |
| **1-G** | #236, #254, #260, #248, #258, #239 | 6 | 代码库中未定位 | 🟡 待查 | 未知 |
| **2-A** | #24, #44, #75, #90, #103 | 5 | 同 struct TransactionReceipt | 🟠 中 | 中 |
| **2-B** | #28, #39, #63, #94 | 4 | 同 struct Block | 🟠 中 | 中 |
| **2-C** | #81, #101, #133 | 3 | 同 struct Transaction | 🟡 低 | 中 |
| **2-D** | #65, #77, #95 | 3 | 同文件 mempool.rs | 🟠 中 | 低 |
| **2-E** | #97, #110, #131 | 3 | 同层 RPC | 🟡 低 | 中 |
| **2-F** | #26, #35, #41, #47, #57, #85, #118 | 7 | Timer 系统 | 🟠 中 | 高 |
| **2-G** | #21, #37, #69, #80, #88, #100, #107, #114 | 8 | Mailbox 系统 | 🟠 中 | 中 |
| **2-H** | #22, #32, #56, #70, #83, #89, #96 | 7 | DeferredTx 系统 | 🟠 中 | 中 |
| **2-I** | #36, #42, #59, #84 | 4 | Gas 计量精度 | 🟡 低 | 中 |
| **2-J** | #34, #43 | 2 | 同文件 pvm_host.rs 存储 | 🟠 中 | 中 |
| **2-K** | #29, #67 | 2 | 同模块 Genesis | 🟡 低 | 中 |
| **2-L** | #62, #68, #104, #144 | 4 | 同层 Engine | 🟡 低 | 中 |
| **2-M** | #23, #145 | 2 | 块执行约束 | 🟡 低 | 低 |
| **2-N** | #151 | 1 | 编码优化 | 🟡 低 | 中 |
| **2-O** | #82 | 1 | CLI | 🟡 低 | 低 |
| **2-P** | #18, #38, #61, #78, #98, #102, #122 | 7 | 文档 | 🟡 低 | 低 |
| **2-Q** | #87, #93 | 2 | Demo | 🟡 低 | 低 |
| **暂缓** | #247, #253, #27 | 3 | 需单独设计 | — | 高 |

**总计：95 issue → 24 个批次 → 约 24 个 PR（其中 4 个直接关闭）**

---

## 四、建议执行顺序

### 阶段一：安全修复（立即执行，1-2 周）
```
1-A：Inspector panic 修复（3 issues → 1 PR）
1-B：CORS 配置修复（2 issues → 1 PR）
1-C：Shell 脚本安全（6 issues → 1 PR）
1-D：日志信息泄露（3 issues → 1 PR）
1-F：关闭已修复 issues（4 issues → 0 PR）
1-G：上游追踪（6 issues → 调查后决策）
```

### 阶段二：协议数据结构（2-3 周）
```
2-A：Receipt 丰富化（5 issues → 1 PR）
2-D：Mempool 增强（3 issues → 1 PR）
2-B：Block 结构增强（4 issues → 2 PR）
2-M：块执行约束（2 issues → 1 PR）
2-K：Genesis 根哈希（2 issues → 1 PR）
```

### 阶段三：核心系统完善（3-4 周）
```
2-G-1：Mailbox 队列增强（4 issues → 1 PR）
2-H-1：DeferredTx 调度 API（3 issues → 1 PR）
2-J：PvmHost 存储隔离（2 issues → 1 PR）
2-G-2：Mailbox 生命周期（4 issues → 1 PR）
2-H-2：DeferredTx 管理（4 issues → 1 PR）
2-F-1：Timer 基础约束（1 issue → 1 PR）
```

### 阶段四：功能扩展（4-6 周）
```
2-E：RPC API 扩展（3 issues → 2 PR）
2-L：Engine 可观测性（4 issues → 1 PR）
2-C：Transaction 类型系统（3 issues → 1 PR）
2-I：Gas 计量精度（4 issues → 2 PR）
2-F-2/3：Timer 经济模型 + 长期索引（6 issues → 2 PR）
```

### 阶段五：文档与工具（持续）
```
2-P：文档类（7 issues → 持续维护）
2-Q：Demo 脚本（2 issues → 1 PR）
2-O：CLI tx 签名（1 issue → 1 PR）
2-N：编码优化（1 issue → 1 PR，需基准测试）
1-E：加密设计缺陷（2 issues → 单独 RFC）
```

---

## 五、关键文件路径速查

| 批次 | 主要修改文件 |
|------|------------|
| 1-A | `/node/inspector/src/main.rs` |
| 1-B | `/node/rpc/src/rpc.rs:187` |
| 1-C | `/node/scripts/*.sh` |
| 1-D | `/node/rpc/src/error.rs`, logging spans |
| 2-A | `/node/storage/src/types.rs` (TransactionReceipt) |
| 2-B | `/node/types/src/execution.rs` (Block) |
| 2-C | `/node/types/src/execution.rs` (Transaction) |
| 2-D | `/node/chain/src/mempool.rs` |
| 2-E | `/node/rpc/src/rpc.rs`, `/node/rpc/src/ws.rs`（新） |
| 2-F | `/node/storage/src/timers.rs`, `/node/execution/src/pvm_host.rs` |
| 2-G | `/node/storage/src/mailbox.rs`, `/node/storage/src/types.rs` |
| 2-H | `/node/execution/src/execution/engine.rs`, `/node/execution/src/pvm_host.rs` |
| 2-I | `/node/execution/src/gas.rs`, `/node/execution/src/pvm_host.rs` |
| 2-J | `/node/execution/src/pvm_host.rs` |
| 2-K | `/node/chain/src/genesis.rs`, `/node/chain/src/application.rs` |
| 2-L | `/node/chain/src/engine.rs`, `/node/chain/src/application.rs` |
| 2-M | `/node/types/src/execution.rs`, `/node/storage/src/speculative.rs` |
