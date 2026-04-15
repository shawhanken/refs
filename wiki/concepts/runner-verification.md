---
type: concept
tags: [runner, verification, cip-2]
sources:
  - node/runner/src/types.rs
  - refs/cips/cip-2-offchain-compute.mdx
  - refs/runner/2026-02-05_DOCUMENTATION.md
last_updated: 2026-04-15
status: authoritative
---

# Runner 验证模式（VerificationMode）

每个 Job 声明一种验证策略，决定 Result Verifier（`0x03`）如何判定 Runner 提交的结果可信。

---

## 6 种 Variants（代码权威）

源：`node/runner/src/types.rs`

| # | Variant | 语义 |
|---|---|---|
| 0 | `None` | 单 Runner，信任首个结果（无冗余）|
| 1 | `EconomicBond` | 单 Runner 可信，stake 大小为经济担保 |
| 2 | `MajorityVote` | N-of-M Runner 投票，少数派 slash |
| 3 | `StructuredMatch` | 比较指定 JSON 字段（fallback 全 JSON 比较）|
| 4 | `Deterministic` | TEE + 字节级完全一致，不一致者 slash |
| 5 | `SemanticSimilarity` | 语义相似度匹配（LLM 场景）|

---

## 选择逻辑

| 场景 | 推荐模式 |
|---|---|
| 简单 HTTP GET（幂等）| None 或 EconomicBond |
| 多源数据聚合 | MajorityVote |
| LLM 推理（非确定但结构化）| StructuredMatch 或 SemanticSimilarity |
| 可复现计算 / MCP 工具 | Deterministic（需 TEE 支持）|

---

## 聚合（Commit-Reveal）

MajorityVote / StructuredMatch 使用 **commit-reveal**：
1. 各 Runner 先提交 commit（结果 hash）
2. 所有 commit 齐后 reveal 明文
3. 聚合多数 / 按字段比较

避免先提交者的答案被其它 Runner 抄袭。

---

## VerifierCheck

`VerifierCheck` 允许 Job 自定义额外校验规则：
- `NumericRange { field, min, max }` — 数值区间检查
- `Custom { actor_hex, method }` — 调用另一 Actor 作自定义校验

---

## 源文档冲突 / 漂移

白皮书 §5 只列 4 种模式（TEE Attestation / MajorityVote / ZK-Proof / EconomicBond）：
- 代码扩增 StructuredMatch、SemanticSimilarity
- ZK-Proof 未实现

见 [[../drift]] 条目 D。

---

## 相关
- [[../entities/runner-lifecycle]] — Phase 4 验证步骤
- [[vrf-runner-selection]] — 上游 Runner 选择
- [[settlement-slashing]] — 验证失败的经济惩罚
