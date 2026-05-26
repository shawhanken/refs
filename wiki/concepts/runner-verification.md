---
type: concept
tags: [runner, verification, cip-2, cip-16, cip-23]
sources:
  - node/runner/src/types.rs
  - refs/cips/cip-2-offchain-compute.md
  - refs/cips/cip-16-custom-domains.md
  - refs/cips/cip-23-tee-execution.md
  - refs/runner/2026-02-05_DOCUMENTATION.md
last_updated: 2026-04-21
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
| 4 | `Deterministic` | TEE + 字节级完全一致，不一致者 slash；**CIP-23 Draft：`tee_required = true` 强制，结果必须附 CAE 并通过 `0x05::VerifyCae`** |
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

`VerifierCheck` 允许 Job 自定义额外校验规则（`runner/src/types.rs:177-201` 现有 6 + CIP-2 v2 §2 新增 2 个）：

| Variant | 出处 | 说明 |
|---|---|---|
| `MajorityVote { field }` | 现有 | 字段级多数投票 |
| `JsonSchemaValid { schema }` | 现有 | JSON schema 校验 |
| `StructuredMatch { fields }` | 现有 | 指定字段集精确匹配 |
| `NumericTolerance { field, tolerance }` | 现有 | 数值容差比较 |
| `NumericRange { field, min, max }` | 现有 | 数值区间检查 |
| `Custom { actor_hex, method }` | 现有 | 调用另一 Actor 作自定义校验 |
| **`DnsTxtRecordMatch { fqdn, expected_value, min_resolvers }`** | **CIP-2 v2 AMEND 2-A** | 各 verifier 查 `min_resolvers` 个独立 DNS resolver，多数决；CIP-16 v2 外部域 TXT 挑战用 |
| **`DnsCnameMatch { fqdn, expected_target, min_resolvers }`** | **CIP-2 v2 AMEND 2-B** | 同上但检查 CNAME 链是否终止于 `expected_target` (`MAX_CNAME_HOPS = 8`) |

**为什么 DNS check 用 `MajorityVote` 而非 `Deterministic`**：DNS resolver 之间会因 TTL / cache / anycast routing 看到不同字节内容；`Deterministic` 要求 byte-identical + TEE，不适合非确定性 DNS 查询。CIP-2 v2 §2.4 明确这点；CIP-16 v2 据此修正了 v1 §9.6 的 `Deterministic` 错配。

---

## CIP-23 v2 扩展：Deterministic 模式的密码学强制

当前代码对 `Deterministic + tee_required` 只做"字段存在性检查"，Runner 可自声明 `tee_support = Some(Sgx)` 而不交任何证明。CIP-23 v2 修订：

- **Dispatcher 过滤**：`tee_required` 改查 Registry 的 `MeasurementBinding.status == Active && expires_at > now`；废弃 `runner.capabilities.tee_support` 布尔。
- **Result Verifier**：每条结果必须附 `CompositeAttestation` (CAE)，逐条调 `0x05::VerifyCae`（**opcode 57**，CIP-23 v2 §4 从 v1 §3.6.2 的 50 修正）；任一失败整 Job 失败。
- **SGX legacy**：IAS/EPID 2025-04-02 EOL；SGX 从此仅可用于 `EconomicBond`，**不再** 进 Deterministic 候选池（CIP-23 v2 §2 表）。
- **`tee_type` 与 mode 资格映射**（CIP-23 v2 §2）：tdx / sev / nitro 全 mode 含 Deterministic；sgx 排除 Deterministic
- **`nitro` 待加入 `CANONICAL_TEE_TYPES`**（CIP-23 v2 §2 precondition；现 `registry.rs:211` 仅 `["sgx", "sev", "tdx"]`）
- **其他模式下的 CAE**：可选携带；携带则必须验证通过。

详见 [[tee-attestation]]。

---

## 源文档冲突 / 漂移

白皮书 §5 只列 4 种模式（TEE Attestation / MajorityVote / ZK-Proof / EconomicBond）：
- 代码扩增 StructuredMatch、SemanticSimilarity
- ZK-Proof 未实现

CIP-2 §5.4 / §9 现文未并入 CIP-23 的 attestation-first 语言；实现时以 CIP-23 为准。

见 [[../drift]] 条目 D / TEE-1。

---

## 相关
- [[../entities/runner-lifecycle]] — Phase 4 验证步骤
- [[vrf-runner-selection]] — 上游 Runner 选择
- [[settlement-slashing]] — 验证失败的经济惩罚
- [[tee-attestation]] — CIP-23 Draft：Deterministic 模式的密码学强制
