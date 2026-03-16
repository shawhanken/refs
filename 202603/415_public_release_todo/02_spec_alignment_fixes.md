# 白皮书/CIP 规格差异修复方案

**日期：** 2026-03-16  
**详细技术方案原文：** `source/gap_analysis_20260316.md`  
**本文为精简索引版，包含优先级排序和 Devnet 适用性判断。**  

---

## 优先级分类

### 🔴 严重（影响正确性和安全性）— 必须在 4/15 前修复

| # | 问题 | CIP | 工作量 | 详细方案章节 |
|---|------|-----|--------|------------|
| 二 | Node/Runner 数据类型大量不一致 | CIP-2 | 3-5天 | Gap Analysis §二 |
| 一 | VRF 选择算法不符规格 | CIP-2 | 1-2天 | Gap Analysis §一 |
| 十三 | Runner 结果签名为零 | CIP-2 | 1天 | Gap Analysis §十三 |
| 五 | Commit-Reveal 未实现（需阶段一） | CIP-2 | 1-2周 | Gap Analysis §五 |

### 🟠 高（功能缺失）— 尽量在 4/15 前完成

| # | 问题 | CIP | 工作量 | 详细方案章节 |
|---|------|-----|--------|------------|
| 四 | 超时重选机制未实现 | CIP-2 | 3-5天 | Gap Analysis §四 |
| 十四 | Entitlement 权限检查未建立 | CIP-2 | 3-5天 | Gap Analysis §十四 |
| 八 | EIP-1559 Basefee 未实现 | CIP-3 | 3-5天 | Gap Analysis §八 |
| 三 | Runner 候选过滤缺 5 项 | CIP-2 | 1天 | Gap Analysis §三 |

### 🟡 中（规格偏差）— 4/15 前完成

| # | 问题 | CIP | 工作量 | 详细方案章节 |
|---|------|-----|--------|------------|
| 七 | Gas 成本数值与规格不符 | CIP-3/20 | 0.5天 | Gap Analysis §七 |
| 九 | JobSpec 缺 `required_runner_pool` | CIP-2 | 0.5天 | Gap Analysis §九 |
| 十五 | CBOR JobSpec 只支持 LLM | — | 1天 | Gap Analysis §十五 |
| 十二 | 最低质押量不一致 | CIP-2 | 0.5天 | Gap Analysis §十二 |
| 十一 | Runner 注册签名验证缺失 | CIP-2 | 1天 | Gap Analysis §十一 |

### ⬜ 低（4/15 后迭代）

> [!IMPORTANT]
> 以下部分项目在 Gap Analysis 原文中被标记为**"高"优先级**（问题六、十），此处根据 4/15 Devnet deadline 的可行性**主动降级**，不代表这些功能不重要。Devnet 发布后应优先排入后续迭代。

| # | 问题 | CIP | 工作量 | 原始优先级 | 说明 |
|---|------|-----|--------|-----------|------|
| 六 | CIP-5 定时器三层队列 + GBA | CIP-5 | 1-2周 | **高→低** | 当前 height-timer 足够 devnet |
| 十 | Secrets Manager / TEE Verifier | CIP-2 | 2周+ | **高→低** | 依赖硬件环境 |
| 十六 | Runner P2P 共识通信 | CIP-2 | 3-5天 | 低 | 短期用链协调替代 |
| 十七 | Anthropic/本地 LLM | — | 1天 | 低 | OpenAI 足够 devnet |
| 十八 | HTTP XPath/JSONPath | CIP-2 | 1-2天 | 低 | CSS Selector 已覆盖 |
| 十九 | CIP-1 Actor 调度器 | CIP-1 | 1-2周 | 低 | 复杂度高 |
| 二十 | CIP-4 双 VM 命名空间 | CIP-4 | 3-5天 | 中 | 需先调查现状 |

---

## 关键技术决策

### 决策 1：数据类型统一方案
**选择：** 新建 `cowboy-runner-types` 共享 crate  
**理由：** 从根本上消除类型分歧，而非继续用自定义反序列化器打补丁  
**影响范围：** Node `runner/src/types.rs` + Runner `crates/runner-common/src/types.rs`

### 决策 2：Commit-Reveal 分阶段
**选择：** 先实现"多结果直接链上提交投票"（阶段一），后迭代完整 Commit-Reveal  
**理由：** 完整 Commit-Reveal 需要 P2P 基础设施，时间不够  
**Devnet 可用：** 阶段一足够支持 MajorityVote 验证模式

### 决策 3：TEE/Secrets Manager 延后
**选择：** 标注为"规划中"，4/15 后迭代  
**理由：** 依赖真实 TEE 硬件环境；可先实现 optional 字段

### 决策 4：产块时间
**选择：** 文档化当前限制（±50ms 精度），不在 4/15 前大改  
**理由：** Commonware 框架限制，改动风险大

---

## 每项修复的核心验收测试

详细测试代码见 `source/gap_analysis_20260316.md` 各章节的"测试验收方案"。

| # | 核心测试函数 |
|---|------------|
| 一 | `test_vrf_seed_matches_cip2_spec`、`test_stake_weight_formula` |
| 二 | `test_job_spec_roundtrip_node_to_runner` |
| 三 | `test_unhealthy_runner_excluded`、`test_low_reputation_runner_excluded` |
| 四 | `test_job_timeout_triggers_reputation_penalty`、`test_retry_vrf_seed_differs` |
| 五 | `test_on_chain_verifier_accepts_valid_reveals` |
| 七 | `test_token_hook_max_cycles_is_50000`、`test_storage_read_cycles_is_10` |
| 八 | `test_basefee_increases_when_above_target` |
| 九 | `test_required_runner_pool_filters_candidates` |
| 十一 | `test_valid_signature_accepted`、`test_wrong_key_signature_rejected` |
| 十二 | `test_min_stake_constant_is_unified` |
| 十三 | `test_result_signature_is_nonzero`、`test_tampered_result_signature_fails` |
| 十四 | `test_entitlement_expired_rejected`、`test_delegation_depth_limit` |
| 十五 | `test_cbor_http_job_parsed_correctly` |
