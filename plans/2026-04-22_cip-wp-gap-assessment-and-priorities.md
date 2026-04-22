# Cowboy 代码 ↔ 文档差异度评估与优先级建议

**日期**: 2026-04-22
**范围**: `node/` + `runner/` 两个 Rust workspace vs `refs/cips/*.md` (CIP-1~23) + `refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md`
**基线**: `refs/analysis/2026-04-15_documentation_amendments.md`(一周前的修正案)
**方法**: 6 个并行 Explore 智能体按 CIP 分组复核代码,+ 2026-04-15 后新 commits 增量核查

---

## 第一部分 — 差异度评估

### 一、CIP 实现度总览表

| CIP | 主题 | 实现度 | 等级 | 差异严重性 |
|-----|------|--------|------|-----------|
| **CIP-1** | Actor 调度 / GBA / Timer | ~70% | 🟡 大部分 | Tiered Calendar Queue / GBA bid 未做,实际 FIFO |
| **CIP-2** | Runner Off-chain Compute | ~80% | 🟢 大部分 | ZK-Proof 模式未做;代码多了 StructuredMatch/SemanticSimilarity |
| **CIP-3** | Fee Model (dual basefee) | 100% | 🟢 完全 | 常量与公式与 04-15 amendments 一致 |
| **CIP-4** | 存储 (MPT → QMDB) | ~70% | 🟡 大部分 | MPT 已放弃;Proof Packaging / Fork replay 未完整 |
| **CIP-5** | Timers | 100% | 🟢 完全 | `ecf4975` (04-20) 补齐 `fee_payer/gas_limit_per_fire/expires_at` |
| **CIP-6** | SDK Ergonomics | ~70% | 🟡 大部分 | SDK 框架完整,但 `runner.llm()` / `runner.http()` 是存根 |
| **CIP-7** | Simple Stream Protocol | ~20% | 🔴 部分 | 仅 basic publish/subscribe;环缓冲、加密、付费流、过滤 DSL 全缺 |
| **CIP-9** | Runner Storage (RAS) | ~55% | 🟡 部分 | on-chain billing 骨架有(`ras/`);CapToken 链上验证、volume escrow 缺 |
| **CIP-10** | Runner Containers | ~5% | 🔴 未实现 | 无 OCI/cgroups/namespaces;Container Registry 0x0F 不存在 |
| **CIP-12** | Governance | ~20% | 🔴 部分 | SubmitProposal/CastVote/Execute 骨架有;bicameral/Council/timelock 均缺 |
| **CIP-13** | Runner Delegation | 0% | 🔴 未实现 | DelegateStake/Undelegate 指令完全缺失 |
| **CIP-14** | DNS Addressable Actors | ~5% | 🔴 未实现 | Route Registry 0x0011 / Gateway Registry 0x0012 不存在 |
| **CIP-15** | Public Asset Hosting | 0% | 🔴 未实现 | 依赖 CIP-14 |
| **CIP-16** | Custom Domains | 0% | 🔴 未实现 | 依赖 CIP-14 |
| **CIP-20** | Fungible Tokens (hook cap) | ~40% | 🟡 部分 | 50K cycles cap "声明但未强制"(阶段 1) |
| **CIP-21** | Liquidity Pools | 0% | 🔴 未实现 | 无 AMM/factory/router |
| **CIP-22** | Continuous Clearing Auctions | 0% | 🔴 未实现 | dispatcher 仍基于 VRF 选择,非拍卖 |
| **CIP-23** | TEE Execution | ~15% | 🔴 占位 | 0x05 地址定义;Deterministic mode 只做字节匹配,无 DCAP/NRAS/CAE 验证 |

### 二、2026-04-15 之后(一周内)新增的代码变更

| Commit | 影响 CIP | 新差异? |
|--------|---------|--------|
| `ecf4975` Feat/cip 5 timers (#401) | CIP-5 补齐 per-fire fee | ❌ 无新差异,反而消除差异 |
| `56dcdd7` timer-governance + deploy-code CLI | CIP-1/CIP-12 | ❌ CLI 层补充 |
| `45423ee` Post-genesis relay registration (#403) | CIP-9 RAS | ❌ 代码超前 WP;`node/ras/` 新增 273 行 |
| `ea1ed41` Cross-chain settlement (#405) | **WP 与 CIP 均未覆盖的新能力** | ⚠️ 代码大幅超前文档:新 `JobType::PublishCowboyRoot`、bridge examples、Merkle proof 接口 |

### 三、四类差异分布

#### A. 参数/常量(04-15 amendments 已覆盖,仍准确)
- `BLOCK_CYCLES_TARGET=20M` / `BLOCK_CELLS_TARGET=4M`
- Basefee: `ALPHA=96, MIN=10,000, MAX=10²⁴` 几何更新
- Transfer: `5K cycles / 500 cells`
- System Actor 表: 0x01–0x0B (11 槽,WP 仅列 5)
- Runner stake: `max(10K, 1.5× max_job_value)` 注册 floor + 50K 工作门槛
- VerificationMode: 6 variants (WP 仅列 4)
- Address: 20 字节 ETH 风格 secp256k1(迁移已完成)

#### B. 架构/流程(与 WP 基本一致)
- ✅ Block lifecycle: propose/verify 走 `speculative.rs`,report 持久化 — 与 WP §6.2 一致
- ✅ Timer 在交易之后执行 — 与 WP/CIP-5 一致(CIP-1 v1 文字错误)
- ✅ Token hook interface 骨架与 CIP-20 一致(但无强制)

#### C. 代码超前文档(WP/CIP 未描述但代码已实现)
1. **跨链结算**(`examples/bridge/`, `ea1ed41`): Merkle proof 验证、CBYBridge.sol、`JobType::PublishCowboyRoot` — 整个子系统无对应 CIP
2. **RAS 中继注册/结算** (`node/ras/`): heartbeat、CapToken 发行(v1 owner-issued)、10% burn/90% relay split — WP §10 只提 bridge 但未讲 relay 结算
3. **Entitlement Registry (0x07)**: 已在代码中启用,CIP-2 仅提框架
4. **Per-key actor storage + governance basefee** (#394/#399): 与 CIP-12 governance 分支同步

#### D. 文档超前代码(WP v2 Part II 提案中未采纳的)
1. **Read-only handler execution**(WP v2 §6.x): PVM query-only mode 禁止 state_write/emit — 未实现
2. **System-reserved selector routing**(WP v2 §6.y): PVM router 硬禁止 `http.request` 非系统 sender — 未实现(改为 SDK 侧检查)
3. **EventListener 0x08 跨链订阅**(WP §10.2): 0x08 已分配给 Treasury,EventListener 延后
4. **GATEWAY_REGISTRY 0x0D** (WP v2 §9.x CIP-14 依赖): 不存在

### 四、差异度汇总

**按 CIP 数量分布**(18 个 CIP):
- 🟢 完全/大部分实现: **7** (CIP-1/2/3/4/5/6/9)
- 🔴 部分/占位: **4** (CIP-7/12/20/23)
- 🔴 完全未实现: **7** (CIP-10/13/14/15/16/21/22)

**加权平均实现度(按 CIP 重要性粗估)**: ~**42%**
- 核心共识+执行+计费(CIP-1/2/3/4/5/20): ~77% 已实现,生产可用
- Runner 生态完整性(CIP-2/9/10/13/23): ~32%,仅 runner job model 完整,存储/容器/委托/TEE 都是大缺口
- 应用层能力(CIP-7/14/15/16/21/22): ~4%,Web 托管与 DeFi 原语几乎全空白
- 治理(CIP-12): ~20%,演示级

### 五、关键结论

1. **04-15 amendments 在 04-22 仍 100% 准确**,无参数漂移
2. **CIP-5 Timer 是过去一周唯一有实质推进的 CIP** (`ecf4975`),已达完全实现
3. **最大差异集中在 CIP-10/13/14/15/16/21/22 七个 CIP**,均处于 0-5% 状态
4. **CIP-23 TEE** 处于"假货预警"状态 — 地址和接口齐全,但 `tee-verifier` crate 是空桩,Deterministic mode 只做字节匹配,易被误读为已实现
5. **CIP-20 token hook cap** 是 latent bug 预警 — 常量声明但未强制,阶段 2 启用时会 breaking change
6. **代码已超越 WP v2 的部分**(跨链结算、RAS)建议启动新 CIP 立案或 WP v3 修订

---

## 第二部分 — 优先级建议

### 🔴 Tier 0 — 红线项(本周/下周必须处理)

高风险、已埋雷或文档与代码错位,不做会造成生产事故、审计失败、社区信任损耗。

#### T0-1. CIP-23 TEE verifier 桩代码警示
- **问题**: 地址、接口、错误码齐全,但 `runner/crates/tee-verifier/` 的 `verify()` 是空实现,`Deterministic` 模式只做字节匹配。外部会误读为"已有 TEE"。
- **动作**:
  - 立即在 `VerificationMode::Deterministic` 路径与 `TEE_VERIFIER=0x05` actor 的对外描述中打 `UNIMPLEMENTED` 警告
  - 考虑临时禁用 Deterministic 模式接收真实 job,或在 dispatcher 拒绝 `tee_required=true` 的作业
- **参考**: `refs/plans/cowboy-tee-execution-design.md`

#### T0-2. CIP-20 hook gas cap "声明但未强制"
- **问题**: `token_hook_max_cycles=50_000` 常量存在,但当前路径不中断超额执行。任何启用阶段 2 的 PR 都会变成 breaking change。
- **动作**:
  - 在 `gas.rs` / `pvm_executor.rs` 加入真正的 cycle cap 中断
  - 或至少在 CIP-20 文件顶栏加"阶段 1 未强制"标识(04-15 amendments §六·补 已部分做到,但 CIP-20 文件本身无 banner)

#### T0-3. 跨链结算(`ea1ed41`)缺对应 CIP
- **问题**: `JobType::PublishCowboyRoot`、CBYBridge.sol、Merkle proof 验证、publish_root dedup 这套机制已合入 main,但 CIP 目录下无 `cip-24-cross-chain-settlement.md`。三周后无人记得设计决策。
- **动作**: 按 `ea1ed41` diff 立案 CIP-24(或 CIP-25,看编号政策),沉淀"runner 三元组签根 + L1 轻客户端验证 + dedup per-height"三个关键设计点。

#### T0-4. WP 与 CIP 的"代码反超"内容沉淀
同上,**RAS 中继注册结算**(`#403`)和 **Entitlement Registry 0x07** 也缺 CIP 或 CIP 条款过时。建议在下次 WP 修订前把这些补到 CIP-9/CIP-2。

---

### 🟠 Tier 1 — 解锁型依赖(2-4 周,必须在 Tier 2 之前)

这些项本身价值中等,但不做就堵死后续工作。

#### T1-1. CIP-12 Governance MVP(最小治理框架)
- **为什么优先**: 现在所有参数(basefee 常量、lane 预算、设置费率)只能硬分叉。当 Tier 2 推进时必然有参数调整需求。
- **最小切片**(按 `refs/plans/governance-7phase-roadmap.md` 第 1-2 阶段):
  - ERC20Votes-style 代币快照(CIP-20 扩展)
  - TimelockController + 单层 proposal(不做 bicameral/Council)
  - 允许治理修改 basefee 参数与 SettlementConfig
- **成本**: ~3 周,代码已有骨架(`UpdateSettlementConfig` 和 0x09 actor)

#### T1-2. CIP-13 Runner Delegation 最小原语
- **为什么优先**: 没有委托,runner 经济天花板就是"单 runner 自质押 50K",扩不出去;CIP-10 容器化后对 runner 的经济需求更大。
- **最小切片**:
  - `DelegateStake` / `Undelegate` / `ClaimUnbonded` 三个 opcode(52/55/56)
  - `DelegationTranche` 数据结构
  - `verifier.rs` 中的结算分割(commission bps + 委托者分账)
- **成本**: ~3 周。当前 0% 实现,但数据模型 CIP-13 v2 已很具体。

#### T1-3. CIP-9 CapToken 链上验证(P1 级)
- **为什么优先**: RAS 中继注册已合入 main,但 CapToken 仍是 owner-issued v1。链下 runner 到链上结算之间的信任链不闭合。
- **最小切片**:
  - `CapToken` secp256k1 链上签名验证(`node/ras/src/lib.rs`)
  - Volume escrow 与账户 storage reserve 同步
- **成本**: ~2 周

---

### 🟡 Tier 2 — 核心价值承诺(4-8 周,Tier 1 基础上启动)

这些是"Cowboy 的核心卖点"——没做出来,定位叙事就撑不起来。

#### T2-1. CIP-10 Runner Containers(关键)
- **为什么**: Cowboy 的核心定位是"可验证链下计算",MCP/LLM 工具调用要靠容器隔离。当前 0x0F Container Registry 不存在,`OffchainTask` 无 `runtime_config` 字段,runner daemon 无 OCI/cgroups 代码。
- **分期**:
  - P1: Container Registry actor 0x0F + `RuntimeConfig` struct + image hash 白名单
  - P2: runner daemon 接入 runc/crun + cgroups v2 + namespace 隔离
  - P3: 网络隔离 + egress allowlist + `ContainerNetworkEgress` Entitlement
- **成本**: 6-8 周,3 人力。是目前最大的工作量块。

#### T2-2. CIP-23 TEE P1/P2(真实验证)
承接 T0-1,把桩代码换成真实 DCAP/NRAS 根证书链验证、CAE 信封解析、measurement_binding 查询、nonce 防重放。**与 CIP-10 并行**,因为 Deterministic 模式需要容器。
- **成本**: ~4 周

#### T2-3. CIP-7 Stream Protocol 补齐
- **为什么**: runner LLM streaming 输出需要;当前只有 publish/subscribe 外壳。
- **最小切片**: StreamMessage 数据结构 + 环形缓冲 + Stream Key Manager 0x06 加密原语。付费流(PLATFORM_MANAGED)可延后。
- **成本**: ~3 周

---

### 🟢 Tier 3 — 应用层能力(8+ 周,可按市场反馈调整)

#### T3-1. CIP-14 DNS Addressable Actors(解锁 15/16)
Route Registry 0x0011 + Gateway Registry 0x0012 + HTTP envelope。CIP-15/16 是其子能力,必须先做 14。

#### T3-2. CIP-22 → CIP-21 顺序
- **CIP-22 连续清算拍卖**先做:与现有 dispatcher/timer 集成度高,可改造为 runner job 分配机制
- **CIP-21 流动性池**最独立,可随时启动但对核心价值增量最低

#### T3-3. CIP-4 Proof Packaging + Fork Replay 补全
核心功能已用 QMDB 替代 MPT,但批量 proof 压缩和 fork 重组时的 ledger replay 仍未完整。这是长尾健壮性项,可排到最后。

---

## 第三部分 — 推荐排期概览

```
周1-2   ████ T0-1 ~ T0-4  (红线修复/CIP 追认)
周3-6   ████ T1-1 Governance MVP ──┐
周3-6   ████ T1-2 Delegation       ├─ 可并行
周3-5   ████ T1-3 CapToken         ┘
周7-14  ████████████████ T2-1 Container Runtime (主线)
周7-10  ████████ T2-2 TEE P1/P2   ──┐
周7-10  ████████ T2-3 Stream       ┘ 与 T2-1 并行
周15+   ████████ T3-1 DNS → T3-2 CIP-22/21 → T3-3 Proof Packaging
```

---

## 第四部分 — 关键权衡

| 决策点 | 推荐 | 理由 |
|--------|------|------|
| **CIP-10 vs CIP-14** 谁先? | CIP-10 | 核心产品承诺,runner 容器无容器就没有 LLM 故事 |
| **CIP-12 全量 vs MVP**? | MVP 先上 | 7 阶段 roadmap 太重,MVP 够解锁参数调整 |
| **CIP-23 修桩 vs 禁用**? | 立即加 UNIMPLEMENTED 警告,4 周内 P1 完成真实验证 | 当前"假 TEE"是信任风险 |
| **CIP-22 vs CIP-21**? | CIP-22 先 | 与 runner dispatcher 强耦合,能直接复用 timer |

---

## 第五部分 — 一句话结论

**Tier 0(一周) → Governance + Delegation(月) → Containers + TEE(两月) → DNS/HTTP 生态(季度)** 是最合理的路径。最大的不可忽视项是 **CIP-10 容器化**——它既是产品承诺又是最大工作量。

---

## 附录 — 权威顺序

(沿用 `refs/analysis/2026-04-15_documentation_amendments.md` 第八节约定)

**代码 > 本文档 > 04-15 amendments > CIP > whitepaper > 其它文档**
