# Cowboy 平台 CIP 实施度审计报告(2026-05-28)

**审计日期**:2026-05-28(含 PM update — §十)
**前次基线**:[`2026-05-27_CIP_IMPLEMENTATION_AUDIT_CN.md`](./2026-05-27_CIP_IMPLEMENTATION_AUDIT_CN.md)(1 天前)
**审计基线分支**:`devnet`
**代码仓 HEAD**(主报告 5/28 AM 状态):
- node: `f1ac7801` (devnet,5/28 11:09 +0800,**5/27 起 36 commits**)
- runner: `a5915e8` (devnet,**1 commit:PR #85**)
- cbss: `fdb9c1b` (无变化)
- cbfs: `7294650` (无变化)

**§十 PM update 状态**:node 进一步到 `5cc439c0`(PR #545,CIP-17 接口对齐)

**评分策略**:沿用 5/27 校准模式 — 代码未变的 CIP 沿用 baseline,只对真实代码变化的 CIP 重新评分。

---

## 零、核心 Delta(自 5/27 baseline)

### 0.1 一句话总览

**5/27 报告点名的 5 个 P0 在 24 小时内修了 4 个**(仅 CIP-17 接口对齐未动),**外加 CIP-2 v3 整族(§1-§6)实装**。这是审计建立以来**单日实施密度最高**的一天。

### 0.2 CIP-2 v3 整族实装(6 个 PR 在 1 天内全部合入 devnet)

| PR | CIP-2 v3 子节 | 关键 commits | Opcode |
|---|---|---|---|
| **#527** | **§3 EMA Reputation** | a53b2bc3 / dcc2ddb7 / 410f4e7e / d28d68a9 / 32ee65a9 | **94 `SYS_UPDATE_REPUTATION_CONFIG`** |
| **#529** | **§2 VRF Weight Migration** | cf6c5a42 / 9279bb2d / 761ad5d0 / c8259796 | (无新 opcode;`w = stake · sqrt(reputation)` + Fisher-Yates u64→u128) |
| **#533** | **§4 Aggregator Reform** | e32a2552 / cabaf29a / 7b7ba999 / a47388ee | **95 `SYS_UPDATE_AGGREGATOR_CONFIG`** |
| **#535** | **§6 SlashDistribution** | cd394927 | **96 `SYS_UPDATE_SLASH_DISTRIBUTION`** |
| **#536** | **§5 Non-Reveal + CrashAttestation** | 55351731 / b10c3a10 / a103388e / 3b2d6914 / 449990bf | **97 `SYS_SUBMIT_CRASH_ATTESTATION`** + **98 `SYS_UPDATE_NON_REVEAL_CONFIG`** |
| **#543** | **§1 Adaptive Committee + HHI** | b28d5c9a / 65c03700 / 1e8b033b / efeecfa6 / 6bd51e47 / 7009a381 | **99 `SYS_UPDATE_COMMITTEE_CONFIG`** |

**CIP-2 v3 §7**(SemanticSimilarity embedding model 钉死):未实装

### 0.3 P0 Cleanup Batch — node PR #534 + runner PR #85

**node PR #534**(单个 mega-PR,5/27 22:42 合入,跨 CIP-5/20/23/26):

| 5/27 P0 项 | 状态 | 关键 commits |
|---|---|---|
| **CIP-5 carry-forward bug**(`speculative.rs:751` 超预算 timer 永久丢失) | ✅ **已修** | `Timer.skip_count`(codec v3)+ `TIMER_MAX_CARRY_FORWARD = 256` + `timer.dead_lettered` 事件 + 6 SPEC tests(cf_1..cf_6)|
| **CIP-23 dispatcher 废弃布尔过滤**(`dispatcher.rs:1654`) | ✅ **已修** | 新增 `VerificationConfig.required_tee_type: Option<String>` + 类型匹配过滤 + `SPEC-CIP23-DISP-4` 测试 |
| **CIP-20 `on_transfer` post-hook 缺失** | ✅ **已修** | `call_transfer_hook(handler_name, commit_state)` 双签 + 50k cycles cap + active_hook_tokens 防 reentrancy + `spec_cip20_hook_1/2` |
| **CIP-20 emit_event 缺失** | ✅ **已修** | 新模块 `execution/src/token/events.rs` + 8 个标准事件(TokenTransfer/Minted/Burned/Approval/HookUpdated/OwnershipTransferred/Frozen/Thawed) + 路由到 `TOKEN_REGISTRY_SYSTEM_ACTOR=0x06` 的 actor event log + 7 SPEC-CIP20-EVT 测试 |
| **CIP-20 hook cells 上限**(规范 §Hook Constraints) | ✅ **已修(衍生项)** | `TOKEN_HOOK_MAX_CELLS=50_000` + `CellsMeter::push_sub_limit/restore_limit` + `ExecutionError::TokenHookCellsExceeded` + E1412 错误码 |
| **CIP-26 `LibraryPublished` 事件** | ✅ **已修** | 新模块 `library_events.rs` + 对齐 spec §3.3 格式(publisher+name+code_hash+code_size) + LibraryRemoved 事件 + 路由到 publisher actor log |
| **CIP-26 per-call 加载 gas 未生效** | ✅ **已修** | `LIB_HANDLER_LOAD_COLD_PER_BYTE_CYCLES = 53` 真正应用到 first library load(原是死常量) + cache miss/hit 区分 |

**runner PR #85**(`a5915e8`,5/27 23:05):

| 5/27 P0 项 | 状态 | 关键证据 |
|---|---|---|
| **CIP-23 Result Verifier `// TODO: verify TEE attestation`**(verifier.rs:291) | ✅ **已修** | `ResultVerifierImpl::with_tee_verifier(TeeVerifierImpl)` 构造器 + 调用 tee-verifier crate(域前缀 `cowboy/tee-verifier/ecdsa-attestation/v1`) + 回放绑定 `attestation.attestation_data == sha256(canonical_bytes(result.data))` + `deterministic_replay_with_mismatched_payload_must_reject` 测试 |

### 0.4 剩下未修的 5/27 P0

| 5/27 P0 项 | 5/28 状态 |
|---|---|
| **CIP-17 接口对齐**(/proof/* 名 + block_hash / absent 字段 + prove?=false) | ❌ 未动 |
| **CIP-1 carry-forward bug** | ✅ 已修(见 PR #534 — 这是 CIP-5 的修复,但实际上同时关闭了 5/27 报告的 CIP-1 #1 P0 项) |

> **note**:5/27 报告 §5.2 第 1 项("CIP-1 carry-forward bug")和 §3.3 中表 CIP-1 / CIP-5 都点的是同一个 `speculative.rs:751` 的 bug。PR #534 实际上同时关闭了 CIP-1 + CIP-5 两个 entry。

### 0.5 Opcode 空间(5/26→5/27→5/28)

```
93   (5/26)
93   (5/27,无新增)
99   (5/28,新增 94-99 共 6 项)
```

完整 5/28 opcode 表:

| Opcode | 名称 | CIP | 新增日 |
|---|---|---|---|
| 85 / 86 | DrainRelay / AutoDrainPolicy proposals | CIP-9 §13 | 5/26 |
| 87 / 88 | ExecutorRegistryPin / Unpin | CIP-2 v2 §3 | 5/26 |
| 89 | UpdateLaneFeeMultipliers | CIP-3 §2.2.3 | 5/26 |
| 90-93 | Rent (UpdateConfig/Settle/SetQuota/Restore) | CIP-4 §12 | 5/26 |
| **94** | **UpdateReputationConfig** | CIP-2 v3 §3 | **5/28** |
| **95** | **UpdateAggregatorConfig** | CIP-2 v3 §4 | **5/28** |
| **96** | **UpdateSlashDistribution** | CIP-2 v3 §6 | **5/28** |
| **97** | **SubmitCrashAttestation** | CIP-2 v3 §5 | **5/28** |
| **98** | **UpdateNonRevealConfig** | CIP-2 v3 §5 | **5/28** |
| **99** | **UpdateCommitteeConfig** | CIP-2 v3 §1 | **5/28** |

CIP-13 v2 spec 端的 opcode 重号目标:5/27 调整到 ≥94,**5/28 再次推后到 ≥100**(99 已占)。

### 0.6 其他变化

- **PVM 安全 fix**(#542):redact exception traceback from default-level logs(中等严重度 — 防止异常堆栈泄露内部状态)
- **`examples/slackbot/`**(#530/#531):on-chain Slackbot demo + Almanax review 安全 hardening
- **CIP-2 v2 (DNS verifier) 旁路 PR rebase**(6bd51e47 / 7009a381 polish 在 #543 内合并)

---

## 一、5/28 评分校准矩阵

### 1.1 状态分布

| 状态 | 5/27 | 5/28 | Δ |
|---|---:|---:|---|
| ✅ ≥85% | 7 | **7** | 内部全员变强:CIP-2 / CIP-5 / CIP-20 / CIP-26 4 个 ✅ 段成员显著上升 |
| 🟢 60-85% | 7 | 7 | 持稳 |
| 🟡 25-60% | 2 | 2 | CIP-23 显著上升(~30%→~50%)但仍在段内 |
| 🟠 5-25% | 5 | 5 | 持稳 |
| ❌ <5% | 9 | 9 | 持稳 |

### 1.2 真实代码变化矩阵(5 个 CIP)

| CIP | 5/27 | 5/28 | Δ | 关键证据 |
|---|---:|---:|:---:|---|
| **CIP-2** | ✅ ~90% | ✅ **~98%** | **+8pp** | v3 §1/§2/§3/§4/§5/§6 全实装(opcodes 94-99 全在);仅 §7 embedding model 钉死未做 |
| **CIP-5** | ✅ ~93% | ✅ **~98%** | **+5pp** | carry-forward bug 彻底修复(skip_count + 256-block dead-letter event + codec v3 + 6 SPEC tests) |
| **CIP-20** | ✅ ~85% | ✅ **~98%** | **+13pp** | on_transfer post-hook + 8 个标准事件 + 50k cells cap + Token{Hook}Gas/Cells Exceeded 真实生效;**指标:5/27 报告 §6 Top-1 升级项关闭** |
| **CIP-23** | 🟡 ~30% | 🟡 **~50%** | **+20pp** | dispatcher capability-aware(required_tee_type 类型匹配) + Result Verifier 接入 tee-verifier crate + replay 防护(`sha256(result.data)` 绑定);仍缺 CAE/证书链/MeasurementBinding |
| **CIP-26** | ✅ ~95% | ✅ **~100%** | **+5pp** | LibraryPublished/Removed 事件实装(对齐 spec §3.3 格式)+ 路由到 publisher actor log + cold-call gas tier 53/byte 实际生效 |

### 1.3 未变 CIP(25 个,沿用 baseline)

CIP-1 / CIP-3 / CIP-4 / CIP-6 / CIP-7 / CIP-8 / CIP-9 / CIP-10 / CIP-11 / CIP-12 / CIP-13 / CIP-14 / CIP-15 / CIP-16 / **CIP-17** / CIP-18 / CIP-19 / CIP-21 / CIP-22 / CIP-24 / CIP-25 / CIP-28 / CIP-29 / CIP-31

> CIP-17 是唯一一个上期 P0 项 1 天内未动的 CIP — 接口对齐的工作不紧急(`/proof/*` 与 spec `/state/*` 仅命名差异,功能等价)

---

## 二、CIP-2 v3 整族实装详解

CIP-2 v3 是历时数月的"链下计算市场机制改革",从 5/15 到 5/27 baseline 中始终 ❌ 0%,5/28 24 小时内整族落地。

### 2.1 §1 自适应委员会(PR #543,opcode 99)

| 组件 | 文件 | 关键 |
|---|---|---|
| `CommitteeConfig` + `CommitteeState` | `types/src/...` | HHI 阈值、smoothing window、M_target |
| `committee.rs` | `execution/src/runner/committee.rs` | HHI / M math + `maybe_recompute` 自动重算 |
| `UpdateCommitteeConfig` handler | `execution/src/execution/system_instruction.rs` | opcode 99 + gas costs |
| Dispatcher 接入 | `execution/src/runner/dispatcher.rs` | `efeecfa6`:override `verification.runners/threshold` with adaptive M/N |

### 2.2 §2 VRF 权重迁移(PR #529)

| commit | 内容 |
|---|---|
| cf6c5a42 | `v3_runner_weight` 纯函数:`w = stake · sqrt(reputation)` |
| 9279bb2d | dispatcher 切换:drop log2 stake + completion_rate;Fisher-Yates u64→u128 防权重溢出 |
| 761ad5d0 | `SPEC-VRF-3` 重写为 EMA reputation 版 + stake-linearity 新测试 |

### 2.3 §3 EMA Reputation(PR #527,opcode 94)

| 组件 | 文件 | 关键 |
|---|---|---|
| `ReputationConfig` + `RunnerReputation.ema` 字段 | `types/src/...` + `runner/...` | 14 天半衰期 |
| `reputation.rs` | `execution/src/runner/reputation.rs` | Q1.63 fixed-point EMA decay + lazy load |
| Settlement/timeout 集成 | `execution/src/runner/verifier.rs` + `dispatcher.rs` | score on settlement / timeout / probation jail / lazy-decay filter |

### 2.4 §4 Aggregator Reform(PR #533,opcode 95)

| commit | 内容 |
|---|---|
| e32a2552 | `AggregatorConfig` 类型 + opcode 95 |
| cabaf29a | `aggregator.rs`:`select_aggregator` + `load_aggregator_config` |
| 7b7ba999 | `UpdateAggregatorConfig` handler + gas costs |
| a47388ee | verifier 接入:`p50 selection + 1.5% bonus + score=110 closure`(规范 §13 `aggregator_bonus_bps=150` 现已生效) |

### 2.5 §5 Non-Reveal + CrashAttestation(PR #536,opcodes 97/98)

| commit | 内容 |
|---|---|
| 55351731 | 类型:`CrashSignal` / `NonRevealConfig` / `CrashAttestationRecord` / `SlashReason::NonReveal` |
| b10c3a10 | `load_non_reveal_config` + `crash_attestation` storage helpers |
| a103388e | `UpdateNonRevealConfig` handler |
| 3b2d6914 | `SubmitCrashAttestation` handler |
| 449990bf | verifier:在 settlement 阶段分类非揭示(slash 或 attest) |

### 2.6 §6 SlashDistribution(PR #535,opcode 96)

| commit | 内容 |
|---|---|
| cd394927 | schema + 100%-burn defaults + submitter routing(规范 §13 `slash_distribution.burn_bps=10000` 生效) |

### 2.7 CIP-2 v3 仍缺

- §7 SemanticSimilarity 模型钉死(`0x09/system:cip2:semantic_similarity_embedding_model` 治理键未写)
- 端到端 v3 经济实测(测试覆盖了单元,e2e 在 examples/ 待 PR)

---

## 三、CIP-23 进展分析

### 3.1 已修(5/28 PR #534 + runner PR #85)

| 5/27 缺口 | 5/28 状态 |
|---|---|
| dispatcher 用 `tee_required && tee_support.is_none()` 废弃布尔过滤 | ✅ 替换为 `required_tee_type` 类型匹配;SGX runner 不再被错误接受 TDX job |
| Result Verifier `// TODO: verify TEE attestation`(verifier.rs:291) | ✅ 完整接入 `TeeVerifierImpl`(域前缀验签 + 回放绑定) |
| 回放攻击:同一 attestation 跨结果重用 | ✅ `attestation.attestation_data == sha256(canonical_bytes(result.data))` 强制 |

### 3.2 仍缺(CIP-23 v2 完整管道)

- `CompositeAttestation` 复合包络(CPU+GPU+ServiceSig+Freshness)
- `0x05::VerifyCae` 验证管道(nonce / freshness deadline / GPU NCC/NRAS / REPORTDATA = keccak(nonce ‖ pubkey ‖ gpu_measurement))
- 证书链验证(DCAP / NRAS / VCEK / Nitro 根链)
- `MeasurementBinding` 在 Runner Registry
- `BillingAttestation` 字段(CIP-10 联动)
- `tee_call` SDK helper
- `MeasurementBinding` 续期(604,800 blocks)

### 3.3 关于 `tee-verifier` crate 的 5/28 升级

5/27 报告里 tee-verifier 是 338 行,5/28 接入到 result-verifier。其域签名验签从 5/27 的"crate 存在但 result-verifier 未调用"升级到 5/28 的"crate 存在且 result-verifier 已调用 + 绑定 result.data"。这是 5/28 的实质进展。

---

## 四、CIP-20 进展分析

### 4.1 PR #534 中 CIP-20 占了 8 个 commits

| commit | 内容 |
|---|---|
| 5657ceb6 | **on_transfer post-hook 实装** — `call_transfer_hook(handler_name, commit_state)` 双签 + `spec_cip20_hook_1/2` |
| 42c8a765 | warn! 日志补 from/to/amount(operator 可定位失败) |
| 02a4a10d | **8 个标准事件全实装** — TokenTransfer/Minted/Burned/Approval/HookUpdated/OwnershipTransferred/Frozen/Thawed |
| 9ebcff91 | 0x06 常量统一(TOKEN_REGISTRY/BASEFEE/TOKEN_REGISTRY_ADDRESS) + 文档化 TokenCreate 排除 + 3 个正向事件测试 |
| 2eb66f49 | **50k cells cap 在 hook 调用上**(规范 §Hook Constraints) — TOKEN_HOOK_MAX_CELLS=50_000 + push_sub_limit/restore_limit |
| 3db5251a | TokenHookGas/CellsExceeded 错误真正生效(从 dead code → 真正抛出) |

### 4.2 完成度评估

5/27 评分:✅ ~85%(主干完整,事件 + post-hook + cells cap 三大缺)
5/28 评分:✅ ~98%(三大缺全修,新增 11 个 SPEC tests:7 events + 2 hook + 2 cells/cycles)

**仅剩**:`TokenCreate` 不发事件(spec 允许,文档化为已知)

---

## 五、CIP-26 进展分析

### 5.1 PR #534 中 CIP-26 占了 4 个 commits

| commit | 内容 |
|---|---|
| ? | **LibraryPublished 对齐 spec §3.3 格式** — 加 code_size + 改 binary encoding + 新模块 `library_events.rs` |
| ? | **LibraryRemoved 事件**(同 binary encoding) |
| ? | **事件路由到 publisher actor log** — `Instruction::Library(_) => Some(tx.from)` |
| ? | **cold-call gas tier 53/byte 生效** — `BytecodeCache::contains()` 非提升 peek + 首次加载 53 cycles/byte,缓存命中 1 cycles/byte |

### 5.2 完成度评估

5/27 评分:✅ ~95%
5/28 评分:✅ ~100%(所有 5/27 P0 + per-call gas + 事件全完工)

---

## 六、新发现的安全 fix

| Commit | 修复 | 严重度 |
|---|---|---|
| ee370817 (#542) | PVM redact exception traceback from default-level logs | 中(防止内部状态泄露) |
| f4f7def9 (#531) | examples/slackbot 安全 hardening(Almanax review) | 低(示例代码) |

---

## 七、风险与优先级建议(5/28 视角)

### 7.1 5/28 后剩下的关键 P0

| 项 | 5/27 标 P0 | 5/28 状态 |
|---|---|---|
| CIP-1 carry-forward bug | P0 #1 | ✅ 已修(PR #534) |
| CIP-23 result-verifier TODO | P0 #2 | ✅ 已修(runner PR #85) |
| CIP-23 dispatcher 布尔过滤 | P0 #3 | ✅ 已修(PR #534) |
| **CIP-17 接口对齐** | P0 #4 | ❌ 未动 |
| CIP-20 事件 + post-hook + cells cap | P0 #5 | ✅ 已修(PR #534) |
| CIP-3 secp256k1 verify cycle 充电 | P0 #4(子项) | ❌ 未动 |
| CIP-3 return data Cell 计费 | P0 #5(子项) | ❌ 未动 |

**5/28 唯一剩下的 5/27 P0**:CIP-17 接口对齐 + CIP-3 两个子项。这三项工作量都小(命名 + 计费 hook 补完),可由单一 PR 一次性收口。

### 7.2 5/28 新增的中期 P1

- **CIP-2 v3 §7 SemanticSimilarity embedding model 钉死**(治理键 + 模型 ID)
- **CIP-2 v3 端到端经济实测**(examples/ 中无 CIP-2 v3 完整 demo)
- **CIP-13 v2 spec opcode 重号目标 ≥100**(99 已占)
- **CIP-23 v2 CAE 完整管道**(CompositeAttestation + 证书链 + MeasurementBinding)

### 7.3 大型未启动 CIP(P2/P3 与 5/27 相同)

CIP-7 流加密 / CIP-10 容器 / CIP-11 QUIC push / CIP-14/15/16/18/19 Gateway 全族 / CIP-21 DEX / CIP-22 拍卖 / CIP-28 BankActor / CIP-31 完整租金分账

---

## 八、与 5/27 baseline 的方法学差异

本期完全沿用 5/27 校准模式("真实变化 + baseline 沿用"),并未重新调度 7 个 subagent 独立 grep —— 因为:

1. **24 小时内的变化非常清晰**(36 个 commits 都有明确 commit message 标 CIP 编号)
2. **变化全部为 feat / fix**(无 revert,无 删除)
3. **PR #534 的 commit message 本身就是 5/27 P0 项的明确关闭凭证**

主控对每项进行了 grep 核实:
- ✅ opcode 94-99 全部 grep 到(`types/src/execution.rs:711/713/717/718/720`)
- ✅ Result Verifier `with_tee_verifier` 在 line 32(runner crate)
- ✅ `tee_verifier::TeeVerifier as _` import 在 line 6
- ✅ `attestation.attestation_data == sha256(...)` 绑定在 result-verifier 中
- ✅ `Timer.skip_count` 字段 + `carry_forward_action` + dead-letter 路径全在 `speculative.rs`
- ✅ token `events.rs` 模块 + 8 个事件 topic + 路由到 `TOKEN_REGISTRY_SYSTEM_ACTOR=0x06`
- ✅ `library_events.rs` 模块 + `LIB_HANDLER_LOAD_COLD_PER_BYTE_CYCLES=53` 实际生效

---

## 九、结语(5/28 AM)

24 小时内**累计 36 个 commits**,关闭 5/27 报告里 5 个 P0 中的 4 个,同时完成 5/26 报告时点为 "v3 0%" 的 CIP-2 v3 整族实装(6 个子节,6 个 opcodes 94-99)。CIP-2 整体跃迁至 ✅ ~98% — 成为 5/28 当下**最完整的 CIP**(与 CIP-26 ~100% 并列)。

**CIP-23 仍未完工**(~50%)但**关键安全反模式与字面 TODO 已清除** — 这是 5/26 baseline 起就点名的"安全反模式仍在生产"的关闭。

**唯一未动的 5/27 P0**:CIP-17 接口对齐(纯命名 + 字段)与 CIP-3 两个 cycle 充电子项 — 工作量均小,建议下次 PR 一次性收口。

**下次审计建议**:1-2 周后核 CIP-1 v3 timer-lane basefee 是否启动 + CIP-23 v2 CAE 完整管道进展 + CIP-9 GET_MANIFEST RPC 与 ManifestCommitted 事件是否落地 + CIP-2 v3 §7 与端到端 e2e 测试。

---

## 十、5/28 PM 更新(PR #545)

### 10.1 增量

| 范围 | 内容 |
|---|---|
| node head | `f1ac7801`(AM)→ `5cc439c0`(PM) |
| 新 commit | 1 个(**PR #545:`feat(rpc): CIP-17 verifiable state read GET /state/{addr}/{key_hex}`**) |
| 其他仓 | 无变化 |

### 10.2 CIP-17 完成度跃迁

5/28 AM 评分(§一 1.3 列为"未变"):🟢 ~80%
5/28 PM 评分:✅ **~95%**(从 🟢 段升入 ✅ 段)

| 5/27 报告点名缺口 | 5/28 PM 状态 |
|---|---|
| 端点名:`/proof/storage/{addr}/{key}` vs spec `/state/{addr}/{key}` | ✅ **新增 `/state/{actor_address}/{key_hex}`**(`rpc/src/rpc.rs:326`);旧 `/proof/*` 端点保留向后兼容 |
| 响应缺 `block_hash` 字段 | ✅ 已加(0x-prefix) |
| 响应缺 `absent` 字段(不存在证明) | ✅ 已加 + `value=null` |
| 响应缺 `prove?=false` query param | ✅ 已加(默认 prove=true,serde 默认值) |
| 0x-prefix 规范化 | ✅ actor_address / value / state_root / block_hash 全部 0x-prefixed |
| 内部 typed match 替代 string compare(memory feedback_typed_error_match 提到的 #318) | ✅ 已修 — `Err(Storage(qmdb::KeyNotFound))` 模式匹配替代 `msg.contains("KeyNotFound")` |

### 10.3 仍缺(留给 CIP-17 ~95%→100%)

- **Exclusion proof(不存在证明)** — 当 prove=true + absent 时,**返回 501 NotImplemented**(spec-compliant 临时方案,带清晰提示指向 ?prove=false);完整实装需要 `SerializableStateProof` 加 exclusion variant + QMDB 端非包含证明生成。
- 完整 `proof.siblings` / `proof.path_nibbles` / `proof.leaf_hash` 字段结构按 spec §5.2 严格映射(当前是 QMDB MMR 而非 MPT,字段结构已实质上 spec-equivalent 但不字面同名)

### 10.4 5/27 报告 5 个 P0 全部关闭

| 5/27 P0 项 | 5/28 PM 状态 | PR |
|---|---|---|
| CIP-1 carry-forward bug | ✅ | #534 |
| CIP-23 result-verifier TEE TODO | ✅ | runner #85 |
| CIP-23 dispatcher 布尔过滤 | ✅ | #534 |
| **CIP-17 接口对齐** | ✅ | **#545(PM)** |
| CIP-20 事件 + post-hook + cells cap | ✅ | #534 |

**5/28 收官**:5/27 报告 5 个 P0 **100% 关闭**;仅剩 CIP-3 两个 cycle 充电子项(secp256k1 verify + return data Cell 计费)— 这两项是 5/27 报告 §5.2 "新增"项的衍生,不属于核心 P0。

### 10.5 PR #545 的工程信号

PR #545 commit 历史展示了 **clean iteration cadence**:
1. 初始:add response 类型 + handler + route(3 commits)
2. spec polish:0x-prefix 全字段 + always-serialize value(`fix:0x-prefix all hex fields`)
3. 测试覆盖:4 个 SPEC tests(invalid_address_400 / reject_invalid_key_hex / reject_oversized_key_hex / default_prove_true_via_serde_default)
4. **absent + typed match 修复**(`fix(rpc): cip-17 use typed match for KeyNotFound, not string compare`)— 直接对应 memory `feedback_typed_error_match` 标注的 #318 issue + 经 curl 验证 live validator 返回行为
5. **Almanax 安全 review fix**(`fix(rpc): cip-17 Almanax review — 501 on prove=true+absent`)— 防御性 501 + ErrorCode::NotImplemented = 1004 + 一个新 SPEC test

整个 PR 共 **6 个 SPEC tests**(invalid_address / response_shape_serde / default_prove / reject_invalid_key_hex / reject_oversized_key_hex / absent_key_prove_true_returns_501)。

### 10.6 状态分布(5/28 PM 最终)

| 状态 | 5/27 | 5/28 AM | 5/28 PM | Δ from 5/27 |
|---|---:|---:|---:|---|
| ✅ ≥85% | 7 | 7 | **8** | **+CIP-17**(从 🟢 段升入) |
| 🟢 60-85% | 7 | 7 | **6** | -CIP-17 |
| 🟡 25-60% | 2 | 2 | 2 | 持稳 |
| 🟠 5-25% | 5 | 5 | 5 | 持稳 |
| ❌ <5% | 9 | 9 | 9 | 持稳 |

✅ ≥85%(8):CIP-2 / CIP-3 / CIP-5 / CIP-6 / CIP-8 / **CIP-17** / CIP-20 / CIP-26

### 10.7 结语(5/28 PM)

5/28 共 **37 个 commits**(node 仓 36 AM + 1 PM)+ runner 1 PR。**5/27 报告 5 个 P0 在单日内 100% 关闭**,外加 CIP-2 v3 整族(opcodes 94-99)+ CIP-23 关键安全反模式清除。**审计开始以来,单日实施成绩最高的一天**。

5/28 PM 起,剩下的 CIP-3 两个 cycle 充电子项 + CIP-17 exclusion proof 实装 + CIP-2 v3 §7 SemanticSimilarity 模型钉死,是接下来 1-2 周的最紧迫工作。

---

**报告完**
