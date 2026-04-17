# Cowboy 社区治理：可行性与七阶段路径图
# Cowboy Community Governance: Feasibility & 7-Phase Roadmap

---

## 1. 背景 / Context

**中文**：Cowboy 已在 `refs/cips/cip-12-governance.md` 中草拟了一份 ~95% 完成度的治理规范（双院投票、5 级提案、Security Council、系统 Actor 升级路径等），但链上只实现了其中最窄的一片：`SettlementConfig`（0x09 存储、opcode 40 `UpdateSettlementConfig`、发送方必须为 0x09 的 auth 门）。本计划结合 refs 中既有设计与以太坊生态（OpenZeppelin Governor / TimelockController / ERC20Votes、Optimism Token House + Citizens' House、Polkadot OpenGov、Cosmos `x/gov`、Beanstalk 漏洞等）的成熟经验，为社区治理从 0→1 落地给出可执行的七阶段路径图。

**English**: Cowboy already has a ~95% complete governance spec in `refs/cips/cip-12-governance.md` (bicameral voting, 5-tier proposals, Security Council, system-actor upgrade path). On-chain, only the narrowest slice is live: `SettlementConfig` (stored at `0x09`, mutated via opcode 40 `UpdateSettlementConfig`, with a sender==0x09 auth gate). This plan fuses the existing CIP-12 design with battle-tested Ethereum-ecosystem patterns (OZ Governor / TimelockController / ERC20Votes, Optimism's bicameral house model, Polkadot OpenGov, Cosmos `x/gov`, and the Beanstalk flash-loan exploit post-mortem) to deliver an executable 0→1 roadmap.

**目标 / Goal**:
- 证明治理系统的可行性 / Establish feasibility of on-chain community governance on Cowboy.
- 给出一条风险可控的渐进式落地路径 / Lay out a risk-bounded, progressive rollout path.
- 把 CIP-12 的文字规范映射到具体的代码改动清单 / Map CIP-12 prose into a concrete code-change punch list.

---

## 2. 可行性评估 / Feasibility Assessment

| 维度 / Dimension | 评估 / Verdict | 依据 / Evidence |
|---|---|---|
| **架构兼容性 / Arch fit** | 高 / High | System-actor pattern at `0x09` is production-proven for `SettlementConfig`; extending to more params is near-linear effort. `types/src/constants.rs:138-142`, `execution/src/execution/system_instruction.rs:457-460`. |
| **设计成熟度 / Spec maturity** | 高 / High | CIP-12 已详细规定双院投票、5 级门槛、Council 有限权限、升级路径、回滚窗口、griefing cap。Spec is draft-complete; 7 open questions listed in CIP-12 §9. |
| **投票原语 / Voting primitives** | 中 / Medium | CIP-20 token lacks ERC20Votes-style checkpoints & delegation. Must add snapshot infra before any token-weighted vote is safe (Beanstalk lesson). `node/execution/src/token/`. |
| **验证人集合治理 / Validator-set governance** | 中-低 / Medium-Low | 当前 validator set 在 genesis 静态注册，无在链 register/exit/slash-by-gov 路径。`node/chain/src/lib.rs` `register_validators()` 仅 bootstrap。重建需 1 个独立 CIP。 |
| **升级通道 / Upgrade channel** | 中 / Medium | `UpgradeActor` opcode 43 已存在但 gated by fixed `genesis.system_deployers` list，不是治理门。需改写 gate 或新增 `SystemActorUpgrade` opcode。`execution/src/execution/system_instruction.rs:573-610`。 |
| **应急机制 / Emergency stop** | 低 / Low | No chain-wide pause. Token has per-account freeze; runner has `Paused` health state only. `execution/src/token/admin.rs`, `runner/src/types.rs:94`. |
| **基础费治理 / Basefee governance** | 低 / Low | All EIP-1559 constants (ALPHA=96, BLOCK_CYCLES_TARGET=20M, MIN/MAX_BASEFEE, lane splits) are compile-time in `types/src/constants.rs` and `execution/src/basefee.rs:83-118`. No update opcode. |

**结论 / Bottom line**：可行性为"高"。`0x09` actor 范式、`UpdateSettlementConfig` 实例、`UpgradeActor` 机制三者之和已占治理落地工程量的 ~30%。剩余 ~70% 主要是：(1) 可快照委托的投票代币、(2) 提案-投票-时锁-执行状态机、(3) 把一批现有参数/升级通道从硬编码或 genesis-only 迁到 governance-gated、(4) Security Council 签名+紧急通道。
Feasibility is **high**. Three existing pieces (the `0x09` actor pattern, the `UpdateSettlementConfig` precedent, the `UpgradeActor` opcode) cover ~30% of the eventual surface. The remaining ~70% is (1) checkpointed, delegatable voting tokens, (2) the proposal→vote→timelock→execute state machine, (3) migrating hardcoded/genesis-only surfaces to gov-gated instructions, and (4) the Security Council signature + emergency path.

---

## 3. 指导原则 / Guiding Principles

借鉴以太坊生态的经验教训 / Distilled from Ethereum-ecosystem lessons:

1. **快照即提案创建时刻 / Snapshot at proposal creation, never at execution** — Beanstalk 2022 丢失 $182M 的直接原因。CIP-12 已暗含（voting 期前有 temp check），但必须在实现层强制 `proposal.created_block → token.checkpoint(created_block)`。
2. **永远存在时锁 / Timelock is non-negotiable** — Compound/Uniswap/ENS 皆用 ≥48h。CIP-12 Tier 0 时锁 24h、Tier 4 时锁 14d 与行业一致；坚持不压缩。
3. **守护者只能暂停，不能升级 / Guardian pauses, never upgrades** — Compound Pause Guardian 的范例。CIP-12 Council 的三项能力（cancel-queued / fast-track Tier 3 / circuit-break 7d auto-pause）正符合该原则。
4. **所有治理参数本身可治理 / All governance parameters are themselves Tier-4 adjustable** — CIP-12 已采此设计；避免"治理的治理"不可改而导致社会分叉。
5. **分阶段解锁，训练轮先行 / Progressive decentralization with training wheels** — L2Beat Stage 0→1→2 框架；Optimism / Arbitrum 都是先多签再逐步打开。第一版上链治理应**只暴露最少的参数面**。
6. **代币权重≠人头权重 / Token-weighted ≠ one-person-one-vote** — CIP-12 双院（stake + validator）已对冲鲸鱼风险；未来可参考 Optimism Citizens' House 引入非代币权重的第二院（可选）。
7. **升级要可回滚 / Upgrades must be revertible** — CIP-12 §7.2 的 7-day rollback slot + Tier-3 fast-track 回滚，对应 Audius 2022 漏洞的教训。
8. **低配额场景要有公开名单和委托 / Delegation + public delegate registry** — Tally/Boardroom 经验；Cosmos 常见投票率 <40% 即是前车之鉴。

---

## 4. 现状盘点 / Current State Inventory

### 4.1 refs/ 中已有的治理素材 / Governance material already in refs/

| 文档 / Doc | 路径 / Path | 摘要 / Summary |
|---|---|---|
| **CIP-12** | `refs/cips/cip-12-governance.md` | 双院投票、Tier 0-4 阈值表、Council 三项权力、系统 Actor 升级路径、circuit-break、griefing cap、7 个 open questions。~95% 完成度。 |
| **CIP-13** | `refs/cips/cip-13-runner-delegation.md` | Runner 质押委托；所有参数声明为 Tier 0 可调，依赖 CIP-12 上线。 |
| **CIP-3** | `refs/cips/cip-3-fee-model.md` | 所有 EIP-1559 常量声明为 Tier 0 可调；但代码端尚未暴露更新 opcode。 |
| **Wiki Governance** | `refs/wiki/concepts/governance.md` | 指出 `SettlementConfig` 已实现、voting/council/upgrade 未实现；标记 opcode 40-43 与 CIP-13 存在号段冲突风险。 |
| **Wiki Parameters** | `refs/wiki/parameters.md` | 权威参数表，逐项标注 Tier 归属。 |
| **Wiki System Actors** | `refs/wiki/entities/system-actors.md` | `0x01-0x0B` 登记表。`0x08=TREASURY`，`0x09=GOVERNANCE`（not pausable, Tier-4-only upgradeable）。 |
| **分析报告** | `refs/analysis/2026-03-17_conflict_analysis.md` | P0 冲突：System Actor 地址 / 燃气表 / Timer 顺序；治理落地前需先收敛。 |

### 4.2 代码侧已实现 / Already implemented in code

| 功能 / Feature | 位置 / Location | 备注 / Note |
|---|---|---|
| `GOVERNANCE_SYSTEM_ACTOR = 0x09` | `node/types/src/constants.rs:138-142` | 仅 storage + auth 约定，尚无业务逻辑。 |
| `SETTLEMENT_CONFIG_KEY` | 同上 / same | JSON 序列化至 `0x09` 存储。 |
| `UpdateSettlementConfig`（opcode 40） | `execution/src/execution/system_instruction.rs:448-510` | Auth：sender 必须为 `0x09`；sum 必须为 100。是现有治理实现的 **唯一** 范例。 |
| Treasury Actor `0x08` | `runner/src/system_actors.rs:26-27` | 被动接收 `treasury_percent` 与 50% slash。无支出指令。 |
| `UpgradeActor`（opcode 43） | `execution/src/execution/system_instruction.rs:573-610` | Auth：sender 必须在 genesis `system_deployers`。尚非治理门。 |
| Entitlement 系统 / framework | `execution/src/entitlement/grant.rs:59-61` | Global-scope grant 限 0x09 可发。可被治理体系复用。 |
| Dual Basefee 存储 `0x06` | `types/src/constants.rs:135-136`, `execution/src/basefee.rs` | EIP-1559 逻辑完备，但无参数更新通道。 |

### 4.3 差距清单 / Gap list

- ❌ 投票权原语（checkpointing、delegation、`getPastVotes`）/ Voting-power primitives (ERC20Votes analogue).
- ❌ 提案/投票/时锁/执行状态机 / Proposal → vote → timelock → execute FSM.
- ❌ Security Council 多签 & circuit-break / Council multisig & circuit-breaker pause.
- ❌ 链上 validator set register/exit/slash 治理 / On-chain validator-set governance.
- ❌ Basefee/GasCosts/DelegationConfig 更新 opcode / Parameter-update opcodes for the rest of Tier 0 surface.
- ❌ `SystemActorUpgrade` opcode（CIP-12 §7.1-7.2：字节码校验 + 迁移 + 原子回滚 + 7 天 rollback）/ The governance-gated system-actor upgrade opcode with bytecode whitelist, migration fn, atomic rollback, 7-day rollback slot.
- ❌ 治理相关 RPC 查询面 / Governance RPC read surface (proposal list, voting power at block, delegate registry, council signers).
- ❌ 链上 pause flag / Chain-wide pause flag.

---

## 5. 目标架构 / Target Architecture

**中文**：最终态由 3 个系统 Actor + 1 个扩展后的代币层组成，围绕 `0x09` 为唯一治理入口。

**English**: End-state = 3 system actors + an extended token layer, with `0x09` as the single governance entry point.

```
┌───────────────────────────────┐
│  CIP-20 Token + Checkpoint &  │  ← voting power source
│  Delegation (ERC-5805 風格)    │    (ERC-5805 style)
└──────────────┬────────────────┘
               │ getPastVotes(addr, block)
               ▼
┌──────────────────────────────────────────────────────┐
│  0x09 GOVERNANCE Actor                               │
│  ├── SettlementConfig (existing)                     │
│  ├── ProposalQueue  { id → Proposal{tier, state, …} }│
│  ├── VoteTally      { proposal_id → (stake, validator)│
│  ├── Timelock       { eta → [payloads] }             │
│  ├── CouncilSigners { pubkey[] }  7-of-9             │
│  ├── CircuitBreaker { paused_actor → expiry }        │
│  └── GovParams      { tier_thresholds, windows, … }  │
└──────────────┬───────────────────────────────────────┘
               │ on execute()
               ▼
┌─────────────────────┬─────────────────┬──────────────┐
│ Parameter updates   │ SystemActor-    │ Treasury     │
│ (UpdateBasefeeCfg,  │ Upgrade         │ Disburse     │
│  UpdateDelegCfg,    │ (opcode 44)     │ (opcode 45)  │
│  UpdateGasCosts)    │                 │              │
└─────────────────────┴─────────────────┴──────────────┘
```

**双院投票 / Bicameral tally**：
- **Stake chamber**：`getPastVotes(voter, proposal.created_block)` 权重求和 / stake-weighted sum.
- **Validator chamber**：每个 active validator 一票 / one-validator-one-vote on the validator set snapshot at `proposal.created_block`.
- 通过条件：两院**同时**过 tier-specific quorum + approval 阈值（CIP-12 §5.2）。

**快照关键约束 / Critical snapshot invariant**：`Proposal.created_block` 写入 storage 时必须与 token checkpoint、validator set snapshot 使用同一 block。实现上建议在 `submit_proposal` handler 中记录 `speculative_block_height` 并在后续 vote 校验时强制读 `get_votes_at(voter, that_height)`。

---

## 6. 七阶段路径图 / 7-Phase Roadmap

### Phase 0 — 训练轮 / Training Wheels （~Month 0–3 post-mainnet）

**目标 / Goal**：上线，但不打开在链治理。`0x09` 的唯一业务仍是 `SettlementConfig`，sender 由**基金会多签**（链下 7-of-9 Council keyset）签发后以 0x09 身份广播。公开承诺 sunset 日期。

**代码改动 / Code changes**：
- 新增 validator config 字段 `council_signers: Vec<PubKey>` + 一个轻量 authz 适配层，让 Council 多签脚本可产生 "以 0x09 为 sender" 的交易（通过验证人协商/预签名而非智能合约）。短期临时方案。
- 公开 Council 成员、任期、可执行动作范围（CIP-12 §3 三项权力）。
- 部署 `refs/cips/cip-12-governance.md` 的 stable 版本（移出 Draft）。
- 增加 RPC：`/governance/council/signers`、`/governance/settlement_config`、`/governance/sunset_schedule`。

**成功判据 / Exit criteria**：
- Council 公开签出 ≥1 次 SettlementConfig 调整，区块浏览器可验证。
- 社区白皮书承诺 Phase 1 启动日期（建议 ≤ 90 天）。

**风险 / Risks**：Council 即"中心化事实"。缓解：公开行动日志；给出 sunset。

---

### Phase 1 — 参数治理（Tier 0 半自动）/ Parameter Governance (Tier 0, semi-automated)

**目标 / Goal**：把所有"CIP-3/CIP-12/CIP-13 声明为 Tier 0"的参数从常量迁到 `0x09` 存储；新增一批 sender=0x09 的 opcode。投票仍由 Council 链下完成，但提案/执行通道上链。

**代码改动 / Code changes**：
1. **新增 SystemInstruction**（统一 opcode 段 44-47；避免与 41-43 冲突）：
   - `UpdateBasefeeConfig { alpha, denom, min, max, block_cycles_target, block_cells_target, lane_splits }` → 写入 `0x06` BASEFEE actor storage（由 0x09 gate）。
   - `UpdateGasCosts { GasCosts struct }` → 写入 `0x09`，运行时 `GasCosts::load()` 从 `0x09` 读。
   - `UpdateDelegationConfig { unbonding_blocks, min_self_bond_bps, max_delegators, commission_min_bps, commission_max_bps, slash_cap_bps }` → 写入 `0x01` RUNNER_REGISTRY。
   - `UpdateDisputeWindow { blocks }` → 写入 `0x03` RESULT_VERIFIER。
2. **迁移硬编码**：
   - `BasefeeManager::update()` 先从 0x06 读 `BasefeeConfig` 结构体再 fallback 到常量。`execution/src/basefee.rs:83-118`.
   - `GasCosts::default()` 从 const 改为 "load-from-storage-or-default"；调用点 `execution/src/execution/engine.rs`、`pvm_host.rs` 等。
3. **Auth**：所有 4 个新 opcode 强制 `sender == GOVERNANCE_SYSTEM_ACTOR`，复用 `UpdateSettlementConfig` 的 auth 模板（`system_instruction.rs:457-460` 的 pattern）。
4. **测试**：每个 opcode 至少 3 个 test：happy path、unauthorized sender rejection、invariant validation（如 `block_cycles_target > 0`）。复用 `execution/src/execution/tests.rs:1258-1350` 的模板。
5. **RPC**：`/governance/params` 聚合端点，返回所有可治理参数的当前值 + 每项的"最近一次修改提案 ID"。

**成功判据 / Exit criteria**：
- 至少 3 类参数由 Council 多签发起的 on-chain 交易成功修改；区块浏览器记录完整。
- 审计：所有 Tier 0 参数无遗留硬编码（`grep -r "const.*BASEFEE" node/` 只剩默认值，非使用点）。

**改动范围估计 / Effort estimate**：≈ 800-1200 行 Rust，4-6 周。

---

### Phase 2 — 投票权原语（ERC20Votes 风格）/ Voting-Power Primitives (ERC20Votes-style)

**目标 / Goal**：给 CIP-20 代币加 checkpointing & delegation，让"代币权重投票"在密码学上安全。**这是 Beanstalk 攻击的直接防御层**。

**代码改动 / Code changes**：
1. **扩展 token storage**（`execution/src/token/core.rs`）：
   - `delegates: Map<address, address>`：委托关系。
   - `checkpoints: Map<(token, address), Vec<(block, balance_at_delegate)>>`：二分查找的历史投票权。
   - 写入点：`transfer`、`mint`、`burn`、`delegate` hook 后均需 `_move_voting_power(from_delegate, to_delegate, amount, current_block)`。
   - 参考 OpenZeppelin `ERC20Votes.sol` 的 checkpoint 压缩策略（per-block last-write-wins）。
2. **新增指令 / New instructions**：
   - `Delegate { token, delegatee }` — 代币层操作，sender 任意。
   - `Actor`-level helper: `get_past_votes(token, addr, block) -> u128`（供 0x09 查询）。
3. **PVM host 接口**：暴露 `get_past_votes` 给 actor 调用（配合 `actor_instruction.rs`）。
4. **Gas**：checkpoint 追加记为 cells 写；`get_past_votes` 二分读计 cycles。成本应预算化，避免攻击者通过大量小额转账膨胀其他用户 checkpoint 列表长度。
5. **测试**：含 flash-loan 攻击模拟（借-投-还三连）→ 应在 `proposal.created_block < loan_block` 时零权重。

**成功判据 / Exit criteria**：
- `get_past_votes` 单测通过；压力测试下 checkpoint 读写 < 5% 的 block gas。
- 一个 devnet demo：提案创建后，攻击者 flash-borrow 代币不会获得投票权。

**改动范围 / Effort**：≈ 600-1000 行，4 周。

---

### Phase 3 — 提案引擎上线（Tier 0-1）/ Proposal Engine Live (Tier 0-1)

**目标 / Goal**：把 Phase 1 的 Council 多签"虚拟治理"替换为真正的链上投票；仅开放 Tier 0（参数微调）和 Tier 1（注册表/白名单更新）。

**代码改动 / Code changes**：
1. **Proposal state machine（`0x09` 内部）**：
   ```
   Pending(temp_check) → Active(voting) → Succeeded → Queued(timelock) → Executed
                                        ↘ Defeated / Cancelled / Expired
   ```
2. **新增 opcode（48-53）**：
   - `SubmitProposal { tier, payload: Vec<SystemInstruction>, description_hash, deposit }` — deposit 扣押，记入 `0x09`。
   - `CastVote { proposal_id, support: For/Against/Abstain, reason_hash }` — 只做 stake chamber；validator chamber 自动从 validator 身份派生。
   - `QueueProposal { proposal_id }` — 投票结束且通过后任意人可调用；计算 `eta = now + tier.timelock`。
   - `ExecuteProposal { proposal_id }` — `now >= eta` 时任意人可调用；逐条 apply `payload` 中的 SystemInstruction，使用 `sender = 0x09`。
   - `CancelProposal { proposal_id }` — sender 必须是 Council 多签（见 §3.3）；只能取消 Tier 0-3 queued。
   - `RefundDeposit { proposal_id }` — 通过或败于非 griefing 条件时退押金；Tier 4 失败且参与度 <1% 则没收 50%。
3. **Council multisig verification**：`0x09` 内存储 `council_signers: Vec<PubKey>` + `council_threshold: u8`（默认 7）。`CancelProposal` 需要附 ≥threshold 数量的签名 blob。
4. **Bicameral tally（`0x09` 内核）**：
   - Stake chamber：累加 `get_past_votes(CBY_TOKEN, voter, proposal.created_block)` × `support`。
   - Validator chamber：验证人登记在 `chain` 层 → `0x09` 读 validator set snapshot at `proposal.created_block`；每人一票。
   - 通过条件：两院均过 `tier.quorum` 且 `For/(For+Against) > tier.approval_threshold`。
5. **Deposit 机制**：deposit 转入 0x09 临时 escrow；决策后返还或没收。参考 Cosmos `x/gov` deposit period。
6. **RPC**：`/governance/proposals`（分页 + filter state）、`/governance/proposal/{id}`、`/governance/voting_power/{addr}?at_block=N`。
7. **Tests**（新增 `execution/src/execution/governance_tests.rs`）：
   - Happy path：Tier 0 修改 basefee 参数。
   - Snapshot safety：flash-loan 不获权重。
   - Quorum 不足：不执行。
   - Timelock：提前执行失败。
   - Council 取消：带足够签名成功，不足失败。
   - Deposit：通过返还、失败没收。

**成功判据 / Exit criteria**：
- 至少 5 个 Tier 0 提案、2 个 Tier 1 提案走完完整生命周期。
- Council 在 Phase 0 的临时权限正式替换为链上 `CancelProposal` 能力。
- 外部安全审计报告（至少 1 家 third-party）签发。

**改动范围 / Effort**：≈ 2000-3000 行，10-14 周（含审计）。

---

### Phase 4 — 金库治理（Tier 2）/ Treasury Governance (Tier 2)

**目标 / Goal**：解锁金库（0x08）支出；让社区可通过 Tier 2 提案拨款。

**代码改动 / Code changes**：
1. **新增 opcode 45 `DisburseFromTreasury { recipient, amount, reason_hash }`**：sender 必须为 0x09。
2. **可选流式支付 / Optional streaming**：参考 Sablier 设计，加入 `CreateStream { recipient, rate_per_block, start, end }`；允许长期拨款不必每次走提案。
3. **审计事件 / Audit events**：所有 treasury 支出发射专用 event，blockchain explorer 可索引。
4. **Tier 2 额度门槛**：CIP-12 §5.2 定义 15% quorum、7 天投票；严格执行。

**成功判据 / Exit criteria**：
- 至少 3 次社区拨款（grant、bug bounty、infra 成本）完成。
- Treasury 余额与公链浏览器显示一致。

**改动范围 / Effort**：≈ 400-700 行，3-4 周。

---

### Phase 5 — 系统 Actor 升级治理（Tier 3）/ System Actor Upgrade Governance (Tier 3)

**目标 / Goal**：实现 CIP-12 §7.1-7.2 的 `SystemActorUpgrade`：字节码校验 → 可选 migration → 原子回滚 → 7 天 rollback slot；把现有 `UpgradeActor`（opcode 43）重新定位为仅用于普通用户 actor 的 entitlement-gated 升级。

**代码改动 / Code changes**：
1. **新增 opcode 44 `SystemActorUpgrade { target, new_code_hash, code_ref, migration: Option<MigrationSpec>, activation_delay, rollback_window }`**：
   - Auth：sender 必须是 0x09（意即必须走 Tier 3 提案通过）。
   - 禁止 target == 0x09 本身（防自举失控）；0x09 升级走 Tier 4 独立路径。
2. **字节码白名单 / Bytecode validation**：复用 `pvm_executor.rs::validate_actor_code()`；额外校验 size ≤ 512 KiB（CIP-12 §7.1）。
3. **Migration 执行 / Migration execution**：
   - 若 `migration.is_some()`：在升级 block 内按顺序 (a) quiesce target（标记 paused）、(b) 调 `migration.func` 处理存储迁移、(c) 若 fn 失败则原子回滚所有写入（利用 `speculative.rs` 的 batch rollback 能力）。
4. **Rollback slot**：存储 `previous_code_hash` + `upgraded_at_block`；在 `rollback_window`（≥7 天）内，Tier 3 fast-track 提案可无字节码校验地回退。
5. **Circuit-breaker 入口 / Circuit-breaker entry**：
   - 新增 opcode 46 `CircuitBreakActor { target, expiry_block }` — sender 为 Council 多签（签名 blob 校验同 Phase 3）。
   - 自动发射 Tier 3 ratification proposal（deposit=0，跳过 temp check）。CIP-12 §7.7。
6. **Tests**：
   - Happy path upgrade with no migration（原子 code-pointer swap）。
   - Upgrade with migration success。
   - Migration fn 中 panic → 原子回滚。
   - Rollback within window。
   - Rollback after window 失败。
   - Circuit-break auto-generates ratification proposal。

**成功判据 / Exit criteria**：
- 一次 devnet 完整演练：升级 0x02 JOB_DISPATCHER（含 migration）→ 回滚 → 再升级。
- 社区在 testnet 自主通过 Tier 3 完成一次升级。

**改动范围 / Effort**：≈ 1500-2200 行，8-10 周。**高风险**阶段，需第二轮独立审计。

---

### Phase 6 — 验证人集合治理 / Validator-Set Governance

**目标 / Goal**：使验证人集合的注册/退出/惩罚在链上可治理；**注意**：共识算法（Simplex BFT）与签名方案的变更仍需硬分叉，不在此阶段。

**代码改动 / Code changes**：
1. **为 CIP-13 增加修正案 / Amend CIP-13** (`refs/cips/cip-13-runner-delegation.md`)：新增 §X "Validator Set Governance" 章节，定义 validator lifecycle（register/exit/slash/param-update）的治理表面。CIP-13 已涵盖 runner stake delegation 与 validator 质押经济，validator 集合治理是其自然延伸。
2. **新 SystemInstruction**：`RegisterValidator`、`ExitValidator`、`SlashValidator`（治理触发）、`UpdateValidatorParams`（min stake, jailing duration）— 均纳入 CIP-13 的 opcode 段。
3. **Epoch boundary apply**：validator set 变更在下一 epoch 生效；参考 Cosmos `x/staking`。
4. **与共识层的接口 / Chain-layer integration**：`node/chain/src/lib.rs` 的 `register_validators` 从 genesis-only 改为"读 0x09 存储，在 epoch 边界 reconcile validator set"。
5. **Slashing as gov action**：consensus-detected slashing（double-signing）仍走 `chain` 层自动路径；**治理-triggered slashing**（社会层面违规，如 MEV 行为）走 Tier 2 提案。

**成功判据 / Exit criteria**：
- Devnet 演练：通过治理增加/移除 validator；通过治理 slash 一个模拟恶意 validator。
- CIP-13 修正案经 Tier 4 批准进入主网。

**改动范围 / Effort**：≈ 2000-3000 行（含 chain/consensus 改动），12-16 周。

---

### Phase 7 — 宪法层 / Constitutional Tier (Tier 4)

**目标 / Goal**：完整开放 CIP-12 Tier 4：治理参数本身、Council 组成/罢免、`0x09` 自身升级、非 Tier-3 可及的 breaking change。

**代码改动 / Code changes**：
1. **Tier 4 阈值启用 / Enable Tier 4 thresholds**：100k CBY deposit、20% quorum、66% approval、14 天时锁、不可 fast-track。
2. **`0x09` 自升级 / Self-upgrade of 0x09**：最敏感的路径。特殊化处理：要求 Tier 4 通过 + 至少 30 天社区公告期 + 公开审计报告 + rollback_window ≥ 30 天。
3. **Council 罢免 / Council recall**：Tier 4 提案可替换 `council_signers` 中任一成员；要求 ≥90 天提前公告。
4. **Cancellation griefing 自动检测 / Cancellation griefing auto-detection**：`0x09` 维护 90 天 Council cancellation 计数；超过 3 次自动生成 Tier 4 review proposal（deposit=0，CIP-12 §7.8）。
5. **硬分叉协调 / Hard-fork coordination**：Ethereum-style，Tier 4 提案只作为 social signal；实际硬分叉由 validator 客户端协调 + 社会共识（不放 on-chain）。参考 Cosmos `x/upgrade` 的 halt-height 机制作为未来增强。

**成功判据 / Exit criteria**：
- 一次 Tier 4 提案完整通过（可以是很小的参数调整，目的是验证流程）。
- Council recall 流程至少走过一次演练。
- 治理文档（`refs/wiki/concepts/governance.md`）从 Draft 升级为 Stable。

**改动范围 / Effort**：≈ 500-900 行（大部分是阈值/流程细节），4-6 周 + 长期运营投入。

---

### 时间线总览 / Timeline Summary

| Phase | 名称 / Name | 时长 / Duration | 累计月 / Cumulative | 工程量 / LoC |
|---|---|---|---|---|
| 0 | 训练轮 Council | 1 月 / month | M1 | <500 |
| 1 | 参数治理 Tier 0 | 1.5 月 | M2.5 | ~1000 |
| 2 | ERC20Votes 原语 | 1 月 | M3.5 | ~800 |
| 3 | 提案引擎 Tier 0-1 + 审计 | 3 月 | M6.5 | ~2500 |
| 4 | 金库 Tier 2 | 1 月 | M7.5 | ~500 |
| 5 | 系统升级 Tier 3 + 审计 | 2.5 月 | M10 | ~1800 |
| 6 | Validator-set 治理（CIP-14） | 3.5 月 | M13.5 | ~2500 |
| 7 | 宪法层 Tier 4 | 1.5 月 | M15 | ~700 |

**总计约 15 个月 / ~15 months**，吻合 Optimism / Arbitrum 从 token launch 到 full-decentralized-gov 的量级。

---

## 7. 关键设计决策 / Critical Design Decisions

需要在 Phase 3 启动前与社区/团队共识 / Need consensus before Phase 3 starts:

1. **CIP-12 §9 中 7 个 open questions** — 必须逐条落地决议。最关键：
   - Q: 当 stake chamber 通过但 validator chamber 否决，是否允许"多数强制"覆盖？默认：不允许（双院都必须过）。
   - Q: 代币委托的递归深度上限？默认：1 级（被委托人不可再转委托）以避免委托链混淆。
   - Q: Temperature check 阶段的 vote 是否计入最终 tally？默认：不计入，纯信号。

2. **快照粒度 / Snapshot granularity**：按 block 还是按 epoch？建议按 block（与 OZ Governor 一致），代价是 checkpoint 列表可能较长；可通过 per-epoch 采样做二级压缩。

3. **Council 人员选择 / Council membership**：genesis 固定 vs. Tier 4 可选举。建议：genesis 固定 + Tier 4 可替换（CIP-12 已采此设计）。

4. **Opcode 号段分配 / Opcode allocation**：必须先解决 `refs/analysis/2026-03-17_conflict_analysis.md` 标注的 40-43 段 CIP-13 冲突；建议治理占用 40-55 段，CIP-13 让号或两者重新协调。

5. **投票代币 = CBY 本币 / Voting token = native CBY**：Phase 2 checkpointing 应直接加在 CBY 代币上，而非发行新治理代币。理由：避免双代币割裂（Uniswap UNI vs 流动性提供者的紧张关系即是前车之鉴）；与 Cosmos / Tezos 的 staked-native-token 模型一致。

6. **委托租借防御 / Defenses against delegation renting**：借鉴 Compound/Uniswap，考虑引入"delegation cooldown"（例如委托变更 24h 后才生效），防止闪电委托攻击。

---

## 8. 风险与缓解 / Risks & Mitigations

| 风险 / Risk | 严重度 / Severity | 缓解 / Mitigation |
|---|---|---|
| 闪电贷治理攻击（Beanstalk）/ Flash-loan governance attack | 极高 / Critical | Phase 2 的 snapshot-at-proposal-created-block 是强制前置条件；没有 Phase 2 不能启动 Phase 3。 |
| 低投票率导致鲸鱼通过恶意提案 / Low turnout + whale capture | 高 / High | Temp check + 两院双重 quorum + Council cancel 权 + 延长窗口（CIP-12 §6.5）。 |
| Council 滥用取消权 griefing / Council griefing | 中 / Medium | 90 天 3-cancellation cap → 自动 Tier 4 review（CIP-12 §7.8）。 |
| 0x09 自升级失控 / 0x09 self-upgrade rugpull | 极高 / Critical | Phase 7 特殊化处理：30d 公告 + 30d rollback_window + Tier 4 + 审计强制。 |
| 升级时存储迁移半失败 / Partial migration failure | 高 / High | Phase 5 的原子 rollback（CIP-12 §7.2）+ 7 天 rollback slot。 |
| Opcode 号段冲突 / Opcode number collision | 中 / Medium | Phase 1 开始前收敛 CIP-13 / CIP-12 opcode 分配；更新 `refs/wiki/entities/system-actors.md`。 |
| 治理参数本身不可治理导致死锁 / Governance-of-governance deadlock | 中 / Medium | 所有 Tier-thresholds/windows 本身均为 Tier-4-adjustable（CIP-12 已采此）。 |
| Validator 集合治理与共识层脱节 / Validator gov vs. consensus drift | 中 / Medium | Phase 6 单独 CIP-14 + epoch boundary reconcile + 硬分叉逃生通道（Phase 7）。 |
| 监管/法律风险 / Regulatory risk | 未知 / Unknown | Foundation 与协议权限彻底分离（CIP-12 §3）；基金会无 protocol authority。 |

---

## 9. 关键文件与改动点 / Critical Files & Modification Points

按 Phase 顺序给出 key file paths（所有基于 `/home/ubuntu/workspace/node/`）：

**Phase 1 要改 / Files for Phase 1**:
- `types/src/execution.rs` — 新 SystemInstruction variants (opcode 44-47)。
- `execution/src/execution/system_instruction.rs` — 新 handler + auth checks（模板见 `:457-460`）。
- `execution/src/basefee.rs` — 把 `BasefeeManager::update()` 的常量读取改为"从 0x06 读结构体"。
- `execution/src/gas.rs` — `GasCosts::default()` → "load from 0x09 storage fallback default"。
- `rpc/src/handlers/chain.rs` — 新 `/governance/params` 端点（对照现有 `/basefee` @ `:1062-1094`）。

**Phase 2 要改 / Files for Phase 2**:
- `execution/src/token/core.rs` — 加 checkpoints + delegates storage。
- `execution/src/token/core.rs` — transfer/mint/burn 后调 `_move_voting_power`。
- `execution/src/pvm_host.rs` — 暴露 `get_past_votes` host API。
- `types/src/execution.rs` — `Delegate` instruction。

**Phase 3 要改 / Files for Phase 3**:
- 新文件 / New file: `execution/src/governance/mod.rs`（Proposal FSM、Tally、Timelock）。
- `types/src/execution.rs` — opcode 48-53 variants。
- `execution/src/execution/system_instruction.rs` — 入口 dispatch。
- `rpc/src/handlers/governance.rs` — 全新 RPC 模块。
- 新测试文件 / New test: `execution/src/execution/governance_tests.rs`。

**Phase 5 要改 / Files for Phase 5**:
- `execution/src/execution/system_instruction.rs:573-610`（现 `UpgradeActor`） — 重新定义语义或拆分。
- `execution/src/pvm_executor.rs::validate_actor_code()` — 新增 size-≤512KiB 检查。
- `storage/src/speculative.rs` — 确认 batch rollback 能跨 instruction（已有基础能力但需单测）。
- 新模块 / New module: `execution/src/governance/upgrade.rs`（migration runner + rollback slot store）。

**Phase 6 要改 / Files for Phase 6**:
- `chain/src/lib.rs::register_validators()` — genesis-only → epoch-boundary reconcile。
- CIP-13 修正案 / Amend: `refs/cips/cip-13-runner-delegation.md` — 新增 validator-set governance 章节。
- `types/src/execution.rs` — validator lifecycle opcodes。

---

## 10. 验证方案 / Verification Plan

每个 phase 必须满足 / Each phase must satisfy:

1. **单元测试 / Unit tests**：新 opcode 至少 5 个 test cases（happy path + 3 失败路径 + invariant）。
2. **集成测试 / Integration tests**：devnet 端到端，使用 `examples/` 目录下的脚本模式（类比 `examples/token/start_all.sh --test`）。
3. **审计 / External audit**：Phase 3 & Phase 5 必须有外部审计报告；其他 phase 内部 review 即可。
4. **文档同步 / Docs sync**：`refs/wiki/concepts/governance.md`、`refs/wiki/parameters.md`、`refs/wiki/entities/system-actors.md` 与代码同步更新；`refs/analysis/` 添加每次 phase 的 drift analysis。
5. **Devnet 演练 / Devnet rehearsal**：每个 phase 在 testnet 运行 ≥2 周，且完成至少一次真实治理动作（例如 Phase 1 修改 min basefee、Phase 3 通过一个 Tier 0 提案、Phase 5 完成一次系统升级与回滚）。
6. **RPC 探针 / RPC smoke**：每 phase 新增 RPC 端点，通过 `cargo run -p rpc` 启动 + curl 脚本在 CI 中验证。
7. **治理仪表盘 / Governance dashboard**：Phase 3 起，必须有对外 UI（类似 Tally 样式）供社区查看提案、投票、时锁状态；此为采用率关键。

---

## 11. 最小可行交付 / Minimum Viable Deliverable

如果需要立刻启动：第一版 PR 目标为 **Phase 0 + Phase 1 的第一个参数**（即把 `UpdateBasefeeConfig` 做出来，由 Council 多签在链下协调后以 `0x09` 身份签发）。这是最小的端到端切片，可验证整个 roadmap 的架构假设。

If a "start now" PR is needed, the MVD is Phase 0 + the first opcode of Phase 1 — specifically `UpdateBasefeeConfig`, signed off-chain by the Council multisig and broadcast as sender=`0x09`. That tiny slice exercises every architectural assumption in this roadmap end-to-end.
