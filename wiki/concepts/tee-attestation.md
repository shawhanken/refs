---
type: concept
tags: [tee, attestation, cae, deterministic, cip-23, cip-2, cip-10]
sources:
  - refs/cips/cip-23-tee-execution.md
  - refs/cips/cip-23-tee-execution-zh.md
  - refs/plans/cowboy-tee-execution-design.md
  - refs/cips/cip-2-offchain-compute.md
  - refs/cips/cip-10-runner-containers.md
last_updated: 2026-04-20
status: draft
---

# TEE Execution & Composite Attestation (CIP-23)

Hardware-rooted attestation pipeline that turns CIP-2 `VerificationMode::Deterministic + tee_required` from a field-presence flag into a cryptographically enforced guarantee. Introduces the **Composite Attestation Envelope (CAE)** binding a CPU TEE quote (TDX / SEV-SNP / Nitro) + NVIDIA NCC GPU report + service signature into one receipt, and turns TEE Verifier `0x05` from a stub into a real verification actor.

---

## 为什么存在

当前代码（`runner/crates/tee-verifier` / `result-verifier` / `node/execution/src/runner/dispatcher.rs` / `secrets-manager`）把 `tee_required` 实现成**字段存在性检查**或**自声明布尔位**。任何 Runner 可以谎称支持 TEE 却不提交任何密码学证据。CIP-23 把这整条链路换成硬件根信任。

---

## CAE v1 结构（D-CBOR）

```rust
CompositeAttestation {
  version,                             // = 1
  cpu: CpuAttestation  { tee_type, quote, cert_chain_cid, measurement, pcr_extension },
  gpu: Option<GpuAttestation {tee_type=NvidiaNcc, nras_token, gpu_measurement, bound_cpu_pubkey}>,
  service_sig: { scheme, service_pubkey, sig },    // sig over (task_id‖req_hash‖H(result)‖attest_digest)
  freshness: { nonce, deadline, generated_at },
}
```

**核心绑定规则 (MANDATORY)**:

```
quote.REPORTDATA  ==  keccak256(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)
```

CPU quote ↔ 服务签名密钥 ↔ GPU NCC 报告 ↔ 任务 nonce 四者互相绑定，任何一个被替换都使整包失效。

---

## TEE Verifier 系统 Actor (0x05) 验证流水线

7 步：**Freshness → Replay → Cert chain → Measurement → Binding → Service sig → NRAS**。

| 根信任 | 链 |
|---|---|
| TDX | PCS root → TD Module → TD quote |
| SEV-SNP | AMD root → VCEK → Report |
| Nitro | AWS Nitro root → signing cert → attestation doc |
| GPU | NVIDIA NRAS root pubkey → JWT claims |

Measurement 白名单**不**重复存放在 TEE Verifier —— 存在 Runner Registry 的 `measurement_binding` 里。

**opcodes 50–53**（新增，不与 CIP-12 / CIP-13 Draft opcode 40–44 冲突，见 [[../drift]] I-1）:

| Op | 指令 | Caller |
|---|---|---|
| 50 | `VerifyCae { cae, job_id, req_hash, result_hash }` | Result Verifier `0x03` |
| 51 | `UpdateCpuRoot { tee_type, cert_der, effective_at }` | Governance `0x09` (delay ≥ 1w) |
| 52 | `UpdateNrasRoot { pubkey, effective_at }` | Governance `0x09` |
| 53 | `GcNonces { upto_block }` | Permissionless |

**Gas**: TDX + NCC 全验证 ≈ 200k cycles，远低于 `BLOCK_CYCLES_TARGET = 20M`，每块可验证 ~50 个 CAE。

---

## Attestation-first Runner Registration（CIP-2 §5.4 修订）

弃用 `runner.capabilities.tee_support` 布尔 —— Dispatcher 改查 Registry 的 `MeasurementBinding`：

```rust
MeasurementBinding {
  cpu_tee_type, allowed_cpu_measurements, allowed_gpu_measurements,
  service_pubkey, bound_at, expires_at, status ∈ {Active, Deprecated, Revoked}
}
```

注册时 Runner 必须提交 `initial_cae`，Registry 跨 actor 调 `0x05::VerifyCae` 通过后才写入绑定。`BINDING_RENEWAL_PERIOD` 默认 ≈ 7 天，过期降级为 `Deprecated`（历史结果仍可验证，但不再入候选池）。

---

## Deterministic 模式的升级（CIP-2 §9 修订）

| 维度 | 旧 | CIP-23 后 |
|---|---|---|
| `tee_required` 过滤 | 查 `runner.capabilities.tee_support` 布尔 | 查 Registry `measurement_binding.status == Active && expires_at > now` |
| Deterministic 结果验证 | 字节级比较 + 检查 `tee_attestation` 字段不为空 | 字节级 + **强制** 调用 `0x05::VerifyCae` per result；任一 CAE 失败整 Job 失败 |
| 其他模式（None / EconomicBond / MajorityVote / StructuredMatch / SemanticSimilarity）| 不变 | 不变；CAE 可选，如附带则必须通过验证 |

**SGX = legacy**: IAS/EPID 2025-04-02 EOL；SGX 明确不进 Deterministic 候选池，只允许 EconomicBond。

---

## Secrets Manager (0x04) 强制 CAE 校验

`get_secret()` 旧签名接 `Option<TeeAttestation>` 但忽略之。CIP-23 后变成 MANDATORY CAE + 策略比对：

```
require(attestation.cpu.measurement ∈ policy.allowed_measurements)
require(attestation.service_sig.service_pubkey ∈ policy.allowed_services)
→ 调 0x05::VerifyCae → 返回 HPKE 封装的密文（只在 CVM 内解密）
```

---

## BillingAttestation 统一到 CAE（CIP-10 §12.3 修订）

CIP-10 原 `BillingAttestation.tee_signature: Option<Vec<u8>>` 改为 `Option<CompositeAttestation>`，复用 `0x05::VerifyCae` 管道（`result_hash = keccak(billing_fields_rlp)`）。不引入独立 attestation 协议。

---

## 存储策略（避免 state 膨胀）

| 字段 | 位置 |
|---|---|
| `attest_digest = keccak(cae_cbor)` | 链上 `task/result/<task_id>.cae_digest`（审计句柄）|
| `cpu_measurement` / `gpu_measurement` / `service_pubkey` | Runner Registry `measurement_binding` |
| 完整 CAE（30–100 KiB，quote + cert chain）| CIP-9 Relay Node / IPFS，链上只存 CID |
| `seen_nonces[task_id]` | TEE Verifier state；GC 窗口 = `DISPUTE_WINDOW_BLOCKS = 75` |

---

## 硬件栈选型（`refs/plans/cowboy-tee-execution-design.md` §4）

| Tier      | 选择                                             |
| --------- | ---------------------------------------------- |
| **主 CPU** | Intel TDX                                      |
| **主 GPU** | NVIDIA NCC (H100 / H200)                       |
| **次 CPU** | AMD SEV-SNP, AWS Nitro Enclaves                |
| **三线**    | ARM CCA（年轻），SGX（legacy）                        |
| **启用层**   | Confidential Containers (CoCo) + Trustee / KBS |

CVM 基础镜像：`cowboy/runner-tee-base:v1`，CIP-10 §5.5 扩展；Yocto / buildroot 可复现构建。

---

## 路线图（18 周）

| Phase | 时长 | 交付 |
|---|---|---|
| P0 Scaffolding | 2w | 类型 + opcode 骨架（stub 逻辑）|
| P1 TDX-only MVP | 6w | 端到端 DCAP + 注册-首证 + Deterministic 验证闭环 |
| P2 CPU + GPU + CoCo | 6w | NCC + NRAS + Trustee KBS + Secrets Manager TEE-gating |
| P3 多 backend + Billing | 4w | SEV-SNP / Nitro + BillingAttestation 接 `0x05` |

---

## 不做的事（明确边界）

- 不在 PVM 内部跑 enclave（PVM 确定性不变，`tee_call` 只是 SDK helper 翻译成 `SubmitJob`）
- 不自研 attestation SDK / enclave framework（用 DCAP + NRAS + CoCo 现成栈）
- 不在 L1 state 上存整份 quote（只锚 digest + CID）
- 不要求所有 Runner 都跑 TEE；非 TEE Runner 继续承担其他 VerificationMode

---

## 源文档冲突 / 漂移

- **System Actor 地址权威**: CIP-23 §3.2 明确 supersede `CLAUDE.md` 与 `node/types/README.md` 中 `0x91-0x95` 老列表。已在 [[../drift]] B 条记录；workspace CLAUDE.md 待更新。
- **块时间假设**: `MAX_QUOTE_AGE = 150 blocks`（CIP-23 注 "≈75s @ 500ms"），但现有协议文档多处假设 1s / block。与 `refs/plans/block-time-500ms-to-1000ms.md` 的未决决策耦合，记入 drift 监控。
- **CIP-2 §5.4 / §9 修订**: CIP-2 源文档仍写 "runner must declare TEE support"，未并入 CIP-23 的 attestation-first 语言；实现时以 CIP-23 为准。

---

## 相关

- [[runner-verification]] — VerificationMode 6 variants；Deterministic 加强
- [[../entities/runner-lifecycle]] — Phase 1 attestation-first 注册
- [[../entities/system-actors]] — `0x05` TEE Verifier 角色
- [[../drift]] — 地址权威 / 块时间 / CIP-2 修订

## Sources

- `refs/cips/cip-23-tee-execution.md` — 规范 EN（Draft, 2026-04-20）
- `refs/cips/cip-23-tee-execution-zh.md` — 规范 ZH（Draft, 2026-04-20）
- `refs/plans/cowboy-tee-execution-design.md` — 实施设计（§12 代码改造清单，§13 4-phase 路线图）
- `refs/cips/cip-2-offchain-compute.md` / `refs/cips/cip-10-runner-containers.md` — 被修订对象
