# MPP Session 集成实施方案（Cowboy）

> 来源研究：`refs/runner/2026-04-28_MPP_Session_Research.md`
> 落地目标：把研究文档第 §5–§6 的设计转化为可执行的工程任务表。
> 批准后第一步：把本方案复制到 `/home/ubuntu/workspace/refs/plans/2026-05-06_mpp_session_implementation.md`（plan-mode 当前只能写指定 plan 文件，所以正式的方案档要在退出 plan mode 后落到 refs/plans 目录）。

---

## 1. Context

**为什么要做**：CIP-2 现有的 Job-Submit 路径要求每次链下调用都对应「链上托管 → 多人 commit-reveal → 链上 settle」一整圈，对 LLM token 计费这种高频微付费场景成本过高。MPP 协议（Stripe + Tempo Labs）通过「链上 Open 一次 → 链下 N 次累积 voucher → 链上 Close 一次」的 session 模式，把 N 次微调用摊薄到 2 笔链上 tx。研究文档结论：调用 Runner 不必经过 Cowboy，但**结算放在 Cowboy 上**，CBY 作为初期结算资产。

**核心架构变化**：
- 链上新增 `SessionActor (0x0C)`：托管 / 累积结算 / 退款 / 仲裁入口
- 链下 Runner 新增 axum HTTP server：实现 MPP 的 `WWW-Authenticate: Payment` / `Authorization: Payment` 协议头，验证 voucher (`ecrecover` + 累积单调 + nonce + expires_at) 后直接调用既有 `runner-llm` / `runner-http` / `runner-mcp` executor
- Voucher 用 EIP-712 签名，复用 wevm/mppx 客户端，仅替换 domain

**不动的部分**：CIP-2 既有 Job-Submit + commit-reveal + slashing 全部保留，作为 dispute 仲裁 fallback；SettlementConfig（governance 0x09，默认 89/10/1）共用；DISPUTE_WINDOW_BLOCKS=75 复用。

---

## 2. 分支策略（用户硬约束）

**两个 repo 当前都在 `devnet` 分支**。两边都从 devnet 新建工作分支：

```bash
# node 仓库
cd /home/ubuntu/workspace/node
git fetch origin
git checkout devnet
git pull origin devnet
git checkout -b feature/mpp-session

# runner 仓库
cd /home/ubuntu/workspace/runner
git fetch origin
git checkout devnet
git pull origin devnet
git checkout -b feature/mpp-session
```

后续所有修改都在各自的 `feature/mpp-session` 分支上提交。**不直接修改 devnet**。

---

## 3. 链上：SessionActor（PoC 范围）

### 3.1 新增地址常量

**`node/runner/src/system_actors.rs`**（在 `RELAY_REGISTRY 0x0B` 之后）：
```rust
pub const SESSION_ACTOR: Address = Address::from_low_u64(0x0C);
```
并在该文件 L64-65 的便利函数区域添加访问器（仿 `runner_registry()` 写法）。

### 3.2 新增 opcode 与 SystemInstruction 变体

**`node/types/src/execution.rs`**（接在 `SYS_DEPLOY_CODE = 51` 之后，L552 附近）：
```rust
pub const SYS_SESSION_OPEN: u8     = 52;
pub const SYS_SESSION_DEPOSIT: u8  = 53;
pub const SYS_SESSION_SETTLE: u8   = 54;
pub const SYS_SESSION_CLOSE: u8    = 55;
pub const SYS_SESSION_FINALIZE: u8 = 56;
pub const SYS_SESSION_SLASH: u8    = 57;
```

同文件 `SystemInstruction` 枚举（L560-795）末尾追加 6 个变体，结构遵循研究文档 §5.3 的 Op 表，参数最小化：
```rust
SessionOpen { session_id: [u8; 32], runner: Address, asset: SessionAsset,
              max_amount: u128, expires_at: u64, price_advert_digest: [u8; 32] },
SessionDeposit { session_id: [u8; 32], amount: u128 },
SessionSettle { session_id: [u8; 32], voucher: SessionVoucher },
SessionClose { session_id: [u8; 32] },
SessionFinalize { session_id: [u8; 32] },
SessionSlash { session_id: [u8; 32], evidence: SessionDispute },
```

(`SessionAsset` / `SessionVoucher` / `SessionDispute` 在 §3.3 引入。)

### 3.3 新增类型

**`node/types/src/session.rs`**（新文件，并在 `node/types/src/lib.rs` 导出）：
```rust
pub struct Session {
    pub session_id: [u8; 32],
    pub payer: Address,
    pub runner: Address,
    pub asset: SessionAsset,
    pub deposit: u128,
    pub spent: u128,
    pub max_amount: u128,
    pub price_advert_digest: [u8; 32],
    pub opened_at_block: u64,
    pub expires_at_block: u64,
    pub last_voucher_nonce: u64,
    pub status: SessionStatus,
}

pub enum SessionAsset { Cby, Cip20 { actor: Address } }
pub enum SessionStatus { Open, Closing { closed_at: u64 }, Settled, Refunded, Disputed }

pub struct SessionVoucher {
    pub session_id: [u8; 32],
    pub cumulative_amount: u128,
    pub nonce: u64,
    pub expires_at: u64,
    pub usage_digest: [u8; 32],
    pub signature: [u8; 65],
}

pub struct SessionDispute { /* 仲裁证据，PoC 阶段先空壳，§3.6 详述 */ }
```

EIP-712 domain 与 typehash 常量（`name="Cowboy MPP Session", version="1"`, chainId, verifyingContract=SESSION_ACTOR）放在 `node/types/src/session_eip712.rs`，同时被 runner-common 引用。

### 3.4 SessionActor handlers（链上核心）

**`node/execution/src/runner/session.rs`**（新文件，仿 `dispatcher.rs` 风格；handler 函数签名沿用 `handle_job_submit` 模板：`async fn handle_session_xxx<S: StateStore>(&self, store, tx, ..., gas_meters, block_height) -> Result<(), ExecutionError>`）。

**`node/execution/src/runner/mod.rs`** 中 `pub mod session;`。

**关键 handler 行为表**：

| Handler | 行为 | 复用代码 |
|---|---|---|
| `handle_session_open` | 校验 expires_at、max_amount > 0、runner 已在 RunnerRegistry 注册；从 payer 账户扣 max_amount → 加到 SESSION_ACTOR 账户（escrow），仿 `dispatcher.rs:678-708`；写入 `Session{status:Open}` 到 `set_actor_storage(SESSION_ACTOR, session_key)` | dispatcher.rs:684-707 escrow 模式 |
| `handle_session_deposit` | session.status==Open；payer 扣款 → escrow 加；session.deposit += amount | 同上 |
| `handle_session_settle` | 1) 加载 session，确认 status∈{Open,Closing}；2) 验签：`ecrecover(domain_sep_hash, voucher.signature)` 必须等于 `session.payer`；3) `voucher.cumulative_amount > session.spent` 且 `≤ session.deposit`；4) `voucher.nonce > session.last_voucher_nonce`；5) `voucher.expires_at >= current_block`；6) `increment = voucher.cumulative_amount - session.spent`；7) **复用** `verifier.rs:357-365` 读 SettlementConfig；8) `runner_share = increment * runner_percent / 100`，burn / treasury 同理；9) escrow→runner / 0x00 / 0x08 转账（仿 `verifier.rs:378-450`）；10) 更新 `session.spent = voucher.cumulative_amount`、`last_voucher_nonce = voucher.nonce` | verifier.rs:351-465 settlement |
| `handle_session_close` | tx.from == session.payer；status: Open→Closing{closed_at: block_height} | — |
| `handle_session_finalize` | 任意人；要求 `block_height >= closed_at + DISPUTE_WINDOW_BLOCKS` 且 status==Closing；`refund = session.deposit - session.spent` 转回 payer；status→Refunded | constants.rs:232 |
| `handle_session_slash` | PoC 阶段先返回 `ExecutionError::Unsupported`，预留接口给 §3.6 后续启用 | — |

**Storage layout**：以 `SESSION_ACTOR` 作 actor address，key = `b"session:" || session_id (32B)`，value = bincode(Session)。voucher 不入链存储（只在内存中比较 cumulative）。

### 3.5 路由接入

**`node/execution/src/execution/system_instruction.rs`** 的 dispatch match（L32-630）末尾追加 6 个分支，调用 §3.4 的 handler。

### 3.6 Slashing / Dispute（PoC 后段）

研究文档 §5.6 的 dispute 路径**完全复用** CIP-2 既有 Verifier(0x03) commit-reveal + slash。PoC 第一轮**只做接口预留**：`handle_session_slash` 直接返回 `ExecutionError::Unsupported`，不在第一轮启用。第二轮再实现 Evidence 收集与 N-of-M 重跑（任务列入 §7 后续工作，不在本方案 PoC 范围）。

### 3.7 单元测试目标（execution crate）

新增 `node/execution/src/runner/session_tests.rs`（或并入 `session.rs` 文件 `#[cfg(test)] mod tests`），覆盖：

- `SPEC-SES-1` Open 后 escrow 余额正确转移到 SESSION_ACTOR
- `SPEC-SES-2` Settle 校验 signature / cumulative monotonic / nonce 单调 / expires_at
- `SPEC-SES-3` Settle 累积 increment 正确按 89/10/1 切分
- `SPEC-SES-4` Settle 后 spent 与 last_voucher_nonce 正确更新
- `SPEC-SES-5` Close → Finalize 在 dispute window 之前 finalize 失败
- `SPEC-SES-6` Close → 等过 DISPUTE_WINDOW_BLOCKS=75 → Finalize 退款给 payer
- `SPEC-SES-7` 重复 voucher（nonce <= last）拒绝
- `SPEC-SES-8` cumulative_amount > deposit 拒绝
- `SPEC-SES-9` 非 payer 调 Close 失败
- `SPEC-SES-10` 加 Deposit 后能继续 Settle 到更高 cumulative

预期至少新增 10 个测试，使 execution crate 总数从 130 → ~140。

---

## 4. 链下：Runner 端

### 4.1 Workspace 依赖

**`runner/Cargo.toml`** 在 `[workspace.dependencies]` 加入：
```toml
axum = "0.7"
secp256k1 = { version = "0.29", features = ["recovery"] }   # 已经在用，确认 features 含 recovery
```
(hyper / tower / tower-http 已存在，无需新增。)

### 4.2 runner-common 类型增量

**`runner/crates/runner-common/src/types.rs`** 在 `RunnerResult` 之后（L644 附近）添加：
```rust
pub struct SessionVoucher { /* 镜像 node/types/session.rs 的 SessionVoucher */ }
pub struct PriceAdvert { /* 单位定价：CBY / token, CBY / http_call, ... */ }
```
EIP-712 domain 编码与 ecrecover helper 放 `runner/crates/runner-common/src/voucher.rs`（新文件）：
```rust
pub fn voucher_digest(domain_sep: &[u8; 32], v: &SessionVoucher) -> [u8; 32];
pub fn recover_signer(digest: &[u8; 32], sig: &[u8; 65]) -> Result<Address>;
pub fn sign_voucher(sk: &SigningKey, domain_sep: &[u8; 32], v: &mut SessionVoucher);
```

### 4.3 chain-client 扩展

**`runner/crates/chain-client/src/client.rs`** 在 `ChainClient` trait（L12-51）追加：
```rust
async fn submit_session_settle(&self, session_id: [u8;32], voucher: SessionVoucher) -> Result<()>;
async fn submit_session_finalize(&self, session_id: [u8;32]) -> Result<()>;
async fn get_session(&self, session_id: [u8;32]) -> Result<Option<Session>>;
```
`HttpChainClient` 中实现：构造 `SystemInstruction::SessionSettle` tx → 用 `runner_key_bytes` 签名 → POST 到 RPC（参考 `submit_result_via_rest()` L276-446 的模板）。

### 4.4 Runner daemon 新增 session_handler

**`runner/crates/runner-node/src/session/`**（新模块）：

- `session/mod.rs`：导出 manager / server
- `session/manager.rs`：`SessionManager` 维护 `HashMap<[u8;32], LocalSession>`（含 `v_max: SessionVoucher`、`payer: Address`、`deposit: u128`、`expires_at`）。提供：
  - `pub async fn observe_session_opened(&self, session: Session)`：从 chain 事件或 polling 同步
  - `pub async fn validate_and_advance(&self, voucher: SessionVoucher) -> Result<()>`：实施 §3.4 同款 5 项校验
  - `pub fn v_max(&self, session_id) -> Option<SessionVoucher>`
- `session/server.rs`：axum HTTP server。路由：
  - `POST /chat`、`POST /http`、`POST /mcp` → 入口
  - 中间件解析 `Authorization: Payment <base64(SessionVoucher)>`；缺失时返回 `402 Payment Required` + `WWW-Authenticate: Payment realm="cowboy", session_actor=0x0C, price_advert=...`
  - 通过 `SessionManager.validate_and_advance` 校验后，把 body 拼成 `JobSpec` → `executors.get_executor(job_type).execute(&job_spec)` → 200 OK + `Payment-Receipt`
- `session/scheduler.rs`：周期任务（每 N 块或当 `v_max.cumulative_amount / deposit > 阈值`、或 expires_at 临近）→ `chain_client.submit_session_settle(id, v_max)`；session 关闭检测 → finalize

**`runner/crates/runner-node/src/node.rs`**：
- `RunnerNode::new` 接收 `Option<SessionConfig>`；
- `start()` 增加第 4 个并发任务 `start_session_server()` 拉起 axum；
- 配置新增 env `RUNNER_SESSION_BIND=0.0.0.0:8088`，未设置则不启用（向后兼容）。

**`runner/src/main.rs`**：从 env 读 `RUNNER_SESSION_BIND`，把 `SessionConfig` 传入 `RunnerNode::new`。

### 4.5 Runner 端测试

**`runner/crates/runner-node/tests/session_integration.rs`**（新）：
- 启动 mock chain（沿用现有 chain-client 测试 fixture），mock executor（直接返回固定 result）
- 客户端用 mock secp256k1 sk 签 voucher，POST 到 server
- 校验 200 OK / 402 / V_max 推进 / 重放 voucher 拒绝 / settle 调用次数

预期 6-8 个 integration test。

---

## 5. CLI 与示例

### 5.1 CLI

**`node/cli/src/cmd/session.rs`**（新，挂在 `cowboy session` 子命令下）：
- `cowboy session open --runner <addr> --max-amount <n> --expires <block>`
- `cowboy session deposit --id <hex> --amount <n>`
- `cowboy session close --id <hex>`
- `cowboy session finalize --id <hex>`
- `cowboy session list --payer <addr>`

### 5.2 端到端示例

**`node/examples/llm_session/`**（新，仿 `examples/llm_chat/` 目录结构）：
- `start_all.sh --test`：拉起 validator → 启动 runner（带 `RUNNER_SESSION_BIND=127.0.0.1:8088`）→ 开 session → 5 次 LLM 调用（用 mppx-style client 脚本，`bench/src/` 下新建 `mpp-session.ts`）→ close → 等 75 块 → finalize
- 验收：链上仅产生 3 笔 tx（Open / Settle / Finalize）；Alice 退款金额 = `deposit - sum(per-call price)`；runner 余额按 89% 增加。

---

## 6. Verification（验收方法）

按以下顺序，每一步必须 green 才进下一步：

1. `cd node && cargo build --workspace` — 编译通过
2. `cd node && cargo test -p cowboy-execution -- SPEC-SES` — §3.7 全部 10 个新测试通过
3. `cd node && cargo test --workspace` — 既有 130+ 测试 + 新增不退步
4. `cd runner && cargo build --workspace && cargo test --workspace` — runner-node session_integration 通过
5. `cd node && ./scripts/run_build.sh && ./scripts/start_validator.sh` — devnet 起来
6. `cd node/examples/llm_session && NODE_DIR=/home/ubuntu/workspace/node ./start_all.sh --test` — e2e 通过，链上 tx 数 = 3，runner / burn / treasury 余额比例 89/10/1
7. **回归测试**：跑既有三个 e2e 不退步：
   - `cd node/examples/token && ./start_all.sh --test`
   - `cd node/examples/multi_call && ./start_all.sh --test`
   - `cd node/examples/llm_chat && ./start_all.sh --test`

---

## 7. 关键文件清单（速查）

### node 仓库（feature/mpp-session 分支）

| 文件 | 动作 | 关键点 |
|---|---|---|
| `node/runner/src/system_actors.rs` | 编辑 (L33-65 区域) | 新增 `SESSION_ACTOR=0x0C` |
| `node/types/src/constants.rs` | 只读复用 | 复用 `DISPUTE_WINDOW_BLOCKS=75`（L232） |
| `node/types/src/execution.rs` | 编辑 (L552, L795) | 新增 6 opcode + 6 枚举变体 |
| `node/types/src/session.rs` | 新建 | Session / SessionAsset / SessionStatus / SessionVoucher / SessionDispute |
| `node/types/src/session_eip712.rs` | 新建 | domain & typehash 常量 |
| `node/types/src/lib.rs` | 编辑 | `pub mod session; pub mod session_eip712;` |
| `node/execution/src/runner/session.rs` | 新建 | 6 handlers，仿 dispatcher.rs 风格 |
| `node/execution/src/runner/mod.rs` | 编辑 | `pub mod session;` |
| `node/execution/src/execution/system_instruction.rs` | 编辑 (L32-630 末尾) | 路由 6 个新指令 |
| `node/execution/src/runner/dispatcher.rs` | **不改** | 仅作参考 (escrow L678-708) |
| `node/execution/src/runner/verifier.rs` | **不改** | 仅作参考 (settlement L351-465) |
| `node/runner/src/types.rs` | **不改** | SettlementConfig 直接复用 (L746-779) |
| `node/cli/src/cmd/session.rs` | 新建 | CLI 入口 |
| `node/examples/llm_session/` | 新建 | e2e demo |

### runner 仓库（feature/mpp-session 分支）

| 文件 | 动作 | 关键点 |
|---|---|---|
| `runner/Cargo.toml` | 编辑 | 加 axum |
| `runner/crates/runner-common/src/types.rs` | 编辑 (L644 附近) | SessionVoucher / PriceAdvert |
| `runner/crates/runner-common/src/voucher.rs` | 新建 | EIP-712 digest / sign / ecrecover |
| `runner/crates/chain-client/src/client.rs` | 编辑 (L12-51 trait, L276+ impl) | submit_session_settle / finalize / get_session |
| `runner/crates/runner-node/src/session/mod.rs` | 新建 | 模块入口 |
| `runner/crates/runner-node/src/session/manager.rs` | 新建 | LocalSession 缓存与校验 |
| `runner/crates/runner-node/src/session/server.rs` | 新建 | axum HTTP server, 402/voucher 解析 |
| `runner/crates/runner-node/src/session/scheduler.rs` | 新建 | 周期 settle / finalize |
| `runner/crates/runner-node/src/node.rs` | 编辑 (L61-310) | 增加第 4 个并发任务 |
| `runner/crates/runner-node/src/key_manager.rs` | **不改** | 复用 secp256k1 sk |
| `runner/src/main.rs` | 编辑 (L162-168) | 读 SessionConfig 传给 RunnerNode |
| `runner/crates/runner-node/tests/session_integration.rs` | 新建 | 端到端测试 |

---

## 8. 开发顺序建议（PoC 2-3 周）

按强依赖顺序：

1. **Day 1-2** — node types: §3.1 + §3.2 + §3.3（地址、opcode、Session 结构、EIP-712 domain）。`cargo build -p cowboy-types` 通过。
2. **Day 3-5** — node SessionActor handlers: §3.4 + §3.5。配套 §3.7 的 10 个测试 (SPEC-SES-1 到 SPEC-SES-10) 一并写出来。`cargo test -p cowboy-execution -- SPEC-SES` 通过。
3. **Day 6** — runner-common voucher.rs + types 同步：§4.1 + §4.2。`cargo build --workspace`（runner）通过。
4. **Day 7-8** — chain-client 扩展：§4.3。`cargo test -p chain-client` 通过（基于 mock RPC）。
5. **Day 9-12** — runner session_handler：§4.4 (manager / server / scheduler)。§4.5 integration test 通过。
6. **Day 13-14** — CLI + 示例：§5。e2e 通过 §6 第 6 步。
7. **Day 15** — 回归 §6 第 7 步；写 PR description；提交两个 PR（node 一个、runner 一个）。

---

## 9. 后续工作（不在 PoC 范围）

- **CIP 草案**：起 `refs/cips/cip-2x-mpp-session.md`，把本方案 spec 化（消息接口 + 状态机 + voucher schema + 安全考量）
- **Slash / Dispute 实装**：§3.6 接入 CIP-2 既有 Verifier 的 commit-reveal 重跑
- **CIP-20 token 作 session 资产**：`SessionAsset::Cip20` 分支落地
- **TEE 增强**：voucher.usage_digest 与 CIP-23 TEE attestation 绑定
- **跨链 session bridge**：与 wevm/mppx / Tempo 互通（写一个 mppx 的 cowboy method 适配器）

---

## 10. 风险与待澄清

- **EIP-712 domain.chainId**：Cowboy 当前 chain_id 取值需查证（`node/types/src/constants.rs` 是否定义？或在 validator 启动配置里？）。第一个实现要先确认源头，避免和未来 chain_id 治理调整冲突。
- **price_advert 协商**：研究文档 §5.3 把 price_advert 作为 OpenSession 的入参之一，但具体编码方式（结构 / digest）方案里折中为 `price_advert_digest: [u8;32]`，链上只存哈希，链下细节走 HTTP 协商。如果产品侧要求 price_advert 上链可审计，需要扩成完整结构 — 这会让 Open tx 体积变大，需要决策。
- **expires_at 单位**：研究文档同时提到 block height 与 timestamp。本方案统一选择 **block height**（与 DISPUTE_WINDOW_BLOCKS 同源，避免双时钟）。
- **Session ID 生成**：研究文档未明确。本方案建议由 payer 在 Open 时提供 `session_id = keccak256(payer || runner || nonce || block_height)`，链上校验 `!exists(session_id)` 即可——无需链上分配 ID。
- **Voucher 大小**：145 bytes，按 CIP-3 calldata 1 Cell/byte 计费；Settle tx Cell 成本可控（< 1k）。
