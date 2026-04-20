---
title: "CIP-23：TEE 执行与复合证明"
description: 基于硬件可信执行环境 + CPU + GPU 复合远程证明的可验证链下计算
icon: shield-check
---

<Note>
  **状态：** Draft<br/>
  **类型：** Standards Track<br/>
  **类别：** Core<br/>
  **创建：** 2026-04-20<br/>
  **依赖：** CIP-2、CIP-3、CIP-10<br/>
  **相关：** CIP-1（deferred callback）、CIP-9（CAE 正文的链下存储）
</Note>

## 1. 摘要

本提案为 Cowboy 定义 **TEE 执行**路径——面向链下 AI 与隐私敏感工作负载的、硬件根信任、端到端可验证的执行框架。核心内容：

1. 规范化 **复合证明信封（Composite Attestation Envelope, CAE）**：把 Intel TDX（或 AMD SEV-SNP / AWS Nitro）CPU quote、NVIDIA NCC GPU 报告、服务签名绑定为单一可上链验证的凭证。
2. 把 `TEE Verifier` 系统 Actor（`0x05`）从目前的占位桩升级为真实的 attestation 验证流水线。
3. 把 `CIP-2 VerificationMode::Deterministic + tee_required` 从"字段存在性检查"升级为"强制密码学校验"。

关键性质：

- **硬件根信任**：每个 TEE 结果都携带 CAE，其 CPU quote（TDX `TDQuoteV4`、SNP `AttestationReport`、Nitro `COSE_Sign1`）可沿链上登记的厂商根证书追溯。
- **CPU + GPU 复合**：AI 工作负载既需要机密 VM 隔离也需要 GPU 内存保护。CAE 通过 `user_data = keccak(nonce ‖ service_pubkey ‖ gpu_measurement)` 写入 CPU quote 把两者强绑定。
- **verify / replay 解耦**：链上一次验证通过后，任何节点可基于 Registry 锚点确定性重放，不再访问 TEE。
- **不新增 syscall**：单入口 `tee_call` 开发体验以 SDK helper 形式呈现，底层仍是 CIP-2 `SubmitJob`。PVM 确定性不受影响，Actor 代码零改动。
- **Confidential Containers 对齐**：CVM 镜像遵循 CoCo + Trustee 规范，复用 CIP-10 OCI 栈，避免自研 enclave SDK。
- **先证明再注册**：Runner 必须在注册时绑定有效的 CPU（及可选 GPU）measurement 才能进入 TEE 候选池。

本 CIP **不要求**全网 Runner 都跑 TEE；非 TEE Runner 继续承担 `None`、`EconomicBond`、`MajorityVote`、`StructuredMatch`、`SemanticSimilarity` 类任务，行为不变。

---

## 2. 动机

CIP-2 引入了 `tee_required` 标志和 `Deterministic` 验证模式，并预留 `0x05` 为 TEE Verifier。然而当前代码仅为脚手架：

- `runner/crates/tee-verifier/src/verifier.rs` — `verify()` 无条件返回 `Ok(())`。
- `runner/crates/result-verifier/src/verifier.rs` — `Deterministic + tee_required` 仅检查 `tee_attestation` 字段是否存在，从不调用任何验证器。
- `node/execution/src/runner/dispatcher.rs` — `tee_required` 过滤依赖 Runner 自声明的 `capabilities.tee_support` 布尔值，无任何密码学证明。
- `runner/crates/secrets-manager/src/manager.rs` — `get_secret()` 接收 attestation 参数但完全忽略。
- `runner/` 整棵树没有 quote 生成代码，也没有 DCAP/NRAS/SNP 客户端或 CVM/CoCo 集成。

与此同时，大量 Cowboy 设计输出（关于 PythonVM × TEE 安全内核模式的前期研究、2026-04 TEE 业态调研、修订版白皮书 §5.5 "TEE option"、CIP-10 §12.3 `BillingAttestation`）都假定真实的 attestation 流水线将会存在。本 CIP 定义该流水线。

2026-Q2 的产业现状也决定了具体选型：Intel IAS/EPID 已于 2025-04-02 EOL，生态已转向 DCAP / Intel Trust Authority，以及 VM 级机密计算（TDX、SEV-SNP）；NVIDIA Confidential Compute（NCC，H100/H200）已是 AI GPU TEE 事实标准；Confidential Containers（CoCo）+ Trustee 成为裸硬件 enclave 之上的可部署平台层。

---

## 3. 规范

### 3.1 术语

- **CVM** — Confidential Virtual Machine，机密虚拟机。其内存由硬件加密并可证明（TDX Trust Domain、SEV-SNP VM、Nitro Enclave）。
- **NCC** — NVIDIA Confidential Compute。每 GPU 的硬件证明，产物由 NVIDIA 根签发密钥签名，并配有来自 NVIDIA Remote Attestation Service (NRAS) 的 EAT token。
- **Quote** — 由 TEE 硬件生成的、绑定到 enclave/VM measurement 和调用者提供的 `user_data` 的签名证明。
- **Measurement** — TEE 初始状态的哈希（如 TDX `MRTD`、SNP `LAUNCH_DIGEST`、Nitro `PCR0..3`）。
- **CAE** — Composite Attestation Envelope，见 §3.4。
- **Measurement Binding** — 链上 Registry 记录，在注册时把 Runner 地址绑定到具体的 CPU/GPU measurement 和服务公钥。
- **Freshness Anchor** — CAE 中嵌入的 `(nonce, deadline, generated_at)` 三元组，用于防重放。

### 3.2 系统 Actor 地址表（权威）

本 CIP 修正 `CLAUDE.md` 与 `node/types/README.md` 中冲突的地址表述。以代码 `node/runner/src/system_actors.rs` 为准：

| 地址 | Actor | 角色 |
|---|---|---|
| `0x01` | Runner Registry | 质押、capability、**measurement binding（新增）** |
| `0x02` | Job Dispatcher | VRF 选择、候选过滤 |
| `0x03` | Result Verifier | commit-reveal、验证模式分发 |
| `0x04` | Secrets Manager | TEE-gated secret 释放（调 `0x05`）|
| `0x05` | **TEE Verifier** | CAE 验证（本 CIP）|

### 3.3 硬件栈

| 档位 | 选择 | 定位 |
|---|---|---|
| **主线 CPU** | Intel TDX | 机密 VM，VM 级隔离 |
| **主线 GPU** | NVIDIA NCC（H100 / H200）| AI 用机密 GPU |
| **次选 CPU** | AMD SEV-SNP、AWS Nitro Enclaves | 备用后端，共用 CAE |
| **第三梯队** | ARM CCA、Intel SGX（legacy，仅 `EconomicBond`）| 不得用于 `Deterministic` |
| **启用层** | Confidential Containers (CoCo) + Trustee / KBS | attestation agent、密钥代理 |
| **证明服务** | Intel DCAP 或 Intel Trust Authority；NVIDIA NRAS；AMD VCEK；AWS Nitro 根 | Quote collateral 与验证 |

CVM 基础镜像：`cowboy/runner-tee-base:v1`（扩展自 CIP-10 §5.5），采用可复现构建（Yocto/buildroot），measurement 公开可验证。

### 3.4 复合证明信封（CAE v1）

采用 D-CBOR 编码（与 CIP-3 同确定性保证）。顶层结构：

```rust
pub struct CompositeAttestation {
    pub version:     u16,                         // = 1
    pub cpu:         CpuAttestation,
    pub gpu:         Option<GpuAttestation>,      // AI 任务必须
    pub service_sig: ServiceSignature,
    pub freshness:   FreshnessAnchor,
    pub extra:       BTreeMap<String, Vec<u8>>,   // 预留
}

pub struct CpuAttestation {
    pub tee_type:       CpuTeeType,               // Tdx | SevSnp | Nitro | Sgx
    pub quote:          Vec<u8>,                  // 原始 quote
    pub cert_chain_cid: Cid,                      // 证书链的 CIP-9 CID
    pub measurement:    [u8; 48],                 // MRTD / LAUNCH_DIGEST / PCR0..3
    pub pcr_extension:  Option<[u8; 32]>,         // RTMR (TDX runtime measurement)
}

pub struct GpuAttestation {
    pub tee_type:          GpuTeeType,            // NvidiaNcc
    pub nras_token:        Vec<u8>,               // NRAS 签发的 EAT (JWT)
    pub gpu_measurement:   [u8; 48],
    pub bound_cpu_pubkey:  [u8; 32],              // dstack 风格 CPU↔GPU 绑定
}

pub struct ServiceSignature {
    pub scheme:         SigScheme,                // Ed25519 | EcdsaP256
    pub service_pubkey: [u8; 32],
    pub sig:            Vec<u8>,                  // Sign(sk, task_id ‖ req_hash ‖ H(result) ‖ attest_digest)
}

pub struct FreshnessAnchor {
    pub nonce:        [u8; 32],                   // keccak(task_id ‖ req_hash ‖ submission_block_hash)
    pub deadline:     u64,                        // block height
    pub generated_at: u64,                        // quote 生成时的 block height
}
```

**强制绑定规则**：CPU quote 的 `REPORTDATA`（SNP `REPORT_DATA` / Nitro `user_data`）**必须等于**：

```
user_data = keccak256(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)
```

此绑定把 CPU 证明、服务签名密钥、GPU NCC measurement 与任务结合为不可分拆的凭证包。

### 3.5 链上存储策略

| 字段 | 位置 | 理由 |
|---|---|---|
| `attest_digest = keccak(cae_cbor)` | `task/result/<task_id>.cae_digest` | 审计锚点 |
| `cpu_measurement`、`gpu_measurement`、`service_pubkey` | Runner Registry `measurement_binding` | 避免重复 |
| 完整 CAE（30–100 KiB）| CIP-9 Relay Node / IPFS，链上只存 CID | 避免 state 膨胀 |
| `seen_nonces[task_id]` | TEE Verifier 状态，过 `DISPUTE_WINDOW_BLOCKS` 后 GC | 防重放 |

### 3.6 TEE Verifier Actor (`0x05`)

#### 3.6.1 状态

```rust
pub struct TeeVerifierState {
    pub cpu_roots: BTreeMap<CpuTeeType, Vec<RootCert>>,   // 治理更新
    pub nras_root: Vec<u8>,                                // NVIDIA NRAS 公钥
    pub seen_nonces: BTreeMap<JobId, BTreeSet<[u8; 32]>>,  // 防重放
    pub last_gc_block: u64,
}
```

measurement 白名单由 Runner Registry（per-service / per-runner `measurement_binding`）维护，不在此处重复。

#### 3.6.2 系统指令（opcode 50–53）

| Opcode | 指令 | Caller | 行为 |
|:---:|---|---|---|
| 50 | `VerifyCae { cae, job_id, req_hash, result_hash }` | Result Verifier `0x03` | 运行 §3.6.3 流水线 |
| 51 | `UpdateCpuRoot { tee_type, cert_der, effective_at }` | Governance `0x09` | `effective_at` 必须 ≥ 1 周延迟 |
| 52 | `UpdateNrasRoot { pubkey, effective_at }` | Governance `0x09` | 同上延迟策略 |
| 53 | `GcNonces { upto_block }` | Permissionless | 清理过期 `seen_nonces` |

#### 3.6.3 验证流水线

```text
fn verify_cae(cae, job_id, req_hash, result_hash, registry) -> Result<(), TeeVerifyError>:
    1. 时效：   now ≤ cae.freshness.deadline
             AND (now − cae.freshness.generated_at) ≤ MAX_QUOTE_AGE         (= 150 blocks)
    2. 防重放： cae.freshness.nonce ∉ seen_nonces[job_id]
    3. 证书链： 按 cae.cpu.tee_type 选根，验证 cae.cpu.quote
             — TDX  ：PCS 根 → TD Module → TD
             — SNP  ：AMD 根 → VCEK → Report
             — Nitro：AWS Nitro 根 → 签名证书 → attestation doc
    4. measurement：cae.cpu.measurement  ∈ registry.binding(service).allowed_cpu_measurements
                AND cae.gpu?.gpu_measurement ∈ registry.binding(service).allowed_gpu_measurements
    5. 绑定： quote.REPORTDATA == keccak(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)
    6. 服务签名：verify(service_pubkey, task_id ‖ req_hash ‖ result_hash ‖ attest_digest, sig)
    7. NRAS（若有 GPU）：对 nras_root 验证 JWT
                       且 token.claims.measurement == cae.gpu.gpu_measurement
    8. 全通过 → 将 nonce 写入 seen_nonces[job_id]；否则 → 对应 TeeVerifyError
```

#### 3.6.4 错误码

```rust
pub enum TeeVerifyError {
    AttestFail,         // 证书链失败
    RegistryMismatch,   // measurement 不在白名单
    SigInvalid,         // 服务签名无效
    TaskExpired,        // deadline 或 MAX_QUOTE_AGE 超限
    TaskReplayed,       // nonce 已出现过
    InvalidResultHash,  // 信封中签名的 result_hash 与实际不符
    UnsupportedTeeType, // 对应 TEE 类型根证书未配置
    NonceBindingFail,   // REPORTDATA 与绑定公式不一致
    TeeUnavailable,     // 同步调用方 Runner 拿不到 quote 时复用此枚举
}
```

#### 3.6.5 Gas 预算

| 操作 | Cycles | Cells |
|---|:---:|:---:|
| `VerifyCae` (TDX + NCC)，总计 | 200,000 | 64 |
| — 证书链（约 7 层 ECDSA）| 120,000 | — |
| — Registry measurement 查询 | 500 | — |
| — nonce set 写入 | 1,000 | 32 |
| `UpdateCpuRoot` / `UpdateNrasRoot` | 5,000 | 500 |
| `GcNonces`（每 1,000 条）| 10,000 | 0 |

按 `BLOCK_CYCLES_TARGET = 10_000_000` 计算，每 block 可验证约 50 条 CAE，远高于 Runner lane 实际需求。

### 3.7 Runner Registry 扩展

`RunnerRecord` 新增：

```rust
pub struct MeasurementBinding {
    pub cpu_tee_type:             CpuTeeType,
    pub allowed_cpu_measurements: BTreeSet<[u8; 48]>,
    pub allowed_gpu_measurements: BTreeSet<[u8; 48]>,     // 空 → 不要求 GPU
    pub service_pubkey:           [u8; 32],
    pub bound_at:                 u64,                     // block height
    pub expires_at:               u64,                     // 默认 bound_at + RENEWAL_PERIOD
    pub status:                   BindingStatus,           // Active | Deprecated | Revoked
}
```

注册流程（替换现有"只看 flag"的做法）：

```text
1. Runner 启动 CVM；guest-agent 派生服务密钥对。
2. Runner 提交 RegisterRunner(stake, rate_card, initial_cae, service_pubkey, claimed_measurements)。
3. Runner Registry 跨 Actor 调 TEE Verifier `0x05::VerifyCae`，其中：
       nonce = keccak(runner_addr ‖ registration_block_hash)
4. 成功 → 写入 MeasurementBinding，status = Active。
5. 失败 → 注册被拒，stake 未动。
```

**续约**：binding 必须每 `BINDING_RENEWAL_PERIOD`（默认 12,096 blocks，约 500 ms 下 7 天）续约一次。到期后转 `Deprecated`，不再进入 TEE 候选池，但此前已签发结果仍可验证。

### 3.8 Dispatcher 过滤器修订（CIP-2 §5.4 修正）

CIP-2 §5.4 第 4 条修订为：

> 4. **TEE 过滤**：若 `tee_required`，Runner 的 Registry 记录必须含有 `measurement_binding` 且 `status == Active` 并 `expires_at > submission_block`。本 CIP 生效后，`capabilities.tee_support` 自声明布尔值**不再**作为 TEE 能力证据。

### 3.9 Result Verifier 修订（CIP-2 §9 修正）

对于 `VerificationMode::Deterministic`：

1. 每个结果必须携带 `CompositeAttestation`。
2. 字节级比对之前，Result Verifier 对每个结果调用 `TEE_VERIFIER::VerifyCae`。
3. 任意 CAE 失败即整个 job 失败（不接受部分结果）。

其他模式可选择附带 CAE；若附带，则必须验证通过，但缺失不导致失败。

### 3.10 Secrets Manager 集成

Secrets Manager (`0x04`) 修订 `get_secret`：

```rust
async fn get_secret(
    secret_id: SecretId,
    attestation: CompositeAttestation,           // 改为必传
    task_id: JobId,
) -> Result<SealedSecret, SecretError> {
    let policy = self.policies.get(&secret_id).ok_or(NotFound)?;
    // 跨 Actor 调 TEE Verifier
    verify_cae(&attestation, task_id, req_hash, result_hash = H(""))?;
    require!(policy.allowed_measurements.contains(&attestation.cpu.measurement));
    require!(policy.allowed_services.contains(&attestation.service_sig.service_pubkey));
    Ok(self.kbs.fetch_wrapped(secret_id, attestation.service_sig.service_pubkey).await?)
}
```

Secret 以 HPKE 方式 wrap 到 Runner 的 `service_pubkey`；明文仅在 CVM 内部存在。

### 3.11 `tee_call` SDK Helper

**不新增 PVM syscall**。`cowboy_sdk.tee.tee_call(...)` 是一个纯 Python 封装，发出一笔 `VerificationMode::Deterministic + tee_required = true` 的 `SubmitJob` 指令。PVM 确定性无任何变化。

### 3.12 BillingAttestation 复用（CIP-10 §12.3 修正）

`BillingAttestation.tee_signature` 字段重定义为：

```rust
pub tee_signature: Option<CompositeAttestation>,
```

计费路径的 CAE 验证复用 `0x05::VerifyCae`，其中 `result_hash = keccak(billing_fields_rlp)`。不引入另一套 attestation 协议。

### 3.13 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `MAX_QUOTE_AGE` | 150 blocks（约 75 s @ 500 ms）| Quote 新鲜度窗口 |
| `BINDING_RENEWAL_PERIOD` | 12,096 blocks（约 7 天）| measurement binding 续约周期 |
| `ROOT_UPDATE_DELAY` | 1 周 | `UpdateCpuRoot` / `UpdateNrasRoot` 治理延迟 |
| `SEEN_NONCE_GC_WINDOW` | = `DISPUTE_WINDOW_BLOCKS`（75）| nonce 可 GC 的窗口 |
| `MAX_CAE_ON_CHAIN_BYTES` | 64（仅 digest）| 完整 CAE 走 CIP-9 链下存储 |

---

## 4. 设计理由

- **CPU + GPU 通过 `REPORTDATA` 绑定**：分开的 CPU 与 GPU 证明若不交叉绑定可被攻击者"拼接"。`user_data = keccak(nonce ‖ pubkey ‖ gpu_measurement)` 规则使 CPU quote 离开匹配的 GPU 报告和服务密钥即无效。
- **链上存摘要，链下存正文**：一份完整 TDX quote + 证书链约 30–100 KiB；仅锚定 `attest_digest` 让 state 增长随 `block_count` 线性，而不是随 attestation 大小增长。完整 CAE 在 CIP-9 Relay Node 上按需拉取做审计。
- **先证明再注册 vs. 每任务再证明**：仅在 job 时证明存在竞态——Runner 可先 attest，再换二进制，再回答任务。注册时 binding + 每任务 CAE 强绑 `user_data` nonce 一起关闭该窗口——任何二进制替换同时使 binding 和单任务 quote 失效。
- **`0x04` 与 `0x05` 分离**：Secrets Manager 面向消费者且策略复杂；TEE Verifier 是一个 primitive。分开后其他消费者（Registry 注册、BillingAttestation、未来 CIP）可复用 verifier，不必引入 secret 释放语义。
- **仅存 digest 的 nonce set + `DISPUTE_WINDOW_BLOCKS` GC**：nonce 只需在争议窗口内防重放，过度保留浪费 state。
- **不新增 PVM syscall**：在 PVM 层引入 `tee_call` 会有注入不确定性的风险。直接发出 `SubmitJob(Deterministic + tee_required)` 实现同样的开发体验且 VM 接口零变更。

---

## 5. 向后兼容

- **无 TEE 的 Runner** 继续工作；它们不能被 `tee_required = true` 的任务选中（CIP-2 原本就如此约定，只是此前未做密码学强制）。
- **自声明的 `runner.capabilities.tee_support`** 废弃。本 CIP 激活后 dispatcher 忽略该字段；`measurement_binding` 为权威。现在声明为 TEE 的 Runner 必须在激活区块前用有效 CAE 重新注册。
- **现有的 `Deterministic` 任务** 此前依赖非强制的 `tee_required`，必须同步升级；Runner 操作者必须在激活前 attest 以免任务失败。Result Verifier 提供一次性的 `--tee-soft-fail` 标志，仅发出 warning 不拒绝，仅保留一个 release 周期即移除。
- **CIP-10 `BillingAttestation`** 的 `tee_signature` 获得更丰富的类型。旧记录若该字段为空仍按非 TEE 争议窗口路径处理（CIP-10 §12.3 不变）。

---

## 6. 安全考量

- **伪造 quote**：由根证书链验证拒绝。IAS/EPID（SGX legacy）明确不得用于 `Deterministic` 模式，其于 2025-04-02 已 EOL。
- **重放**：`nonce` 绑定在 `REPORTDATA` 内，并在整个争议窗口内对 `seen_nonces[task_id]` 去重。
- **治理后门添加 measurement**：`UpdateCpuRoot` / `UpdateNrasRoot` 强制 ≥ 7 天延迟 + Governance 控制的签名，与现有 `GOVERNANCE_SYSTEM_ACTOR = 0x09` 模式一致。
- **NRAS 中心化**：NVIDIA 证明服务是中心化的，本 CIP 在 Phase 2 阶段接受该依赖；threshold 多方证明 fallback 留待后续 CIP。
- **CAE 可用性**：若 CIP-9 Relay Node 不可达，链上 `attest_digest` 仍证明 receipt 存在但审计性降级。Runner 至少应将 CAE pin 到 `k` 个 Relay Node，其中 `k ≥ 纠删码重建阈值`。
- **GPU 内存残留**：参见 CIP-10 §14.6（MIG 隔离、memory clearing），此处不重复规范。
- **TEE 硬件侧信道**：已知侧信道类（如 foreshadow、downfall、platypus）由厂商逐步修补。治理可通过 `UpdateCpuRoot` collateral 临时将某个 CPU microcode 版本列入黑名单。
- **TDX 供给集中**：目前 TDX 主要在 Azure 和 GCP 实例族上。`Scope::RunnerPool(tdx_pool_id)`（CIP-2 §7）允许提交方指定特定云或地域；本 CIP 不对偏好池做限定。
- **Soft-fail 窗口风险**：过渡期 `--tee-soft-fail` 标志临时接受未验证的 attestation；操作者必须在该窗口内监控异常结果。

---

## 7. 实施路线图

| 阶段 | 时长 | 交付 | 退出条件 |
|:---:|:---:|---|---|
| **P0 — 脚手架** | 2 周 | 类型定义、opcode 50–53（stub 实现）、`tee-runtime` crate 骨架 | workspace 编译通过；测试用 mock CAE 往返 |
| **P1 — TDX-only MVP** | 6 周 | 链上 Intel DCAP 验证；Runner 通过 `/dev/tdx_guest` 生成 quote；注册 attestation-first；`Deterministic + tee_required` 端到端打通 | `examples/llm_chat` 在 TDX 硬件上运行；红队：伪造/不匹配/重放 quote 全部被拒 |
| **P2 — CPU + GPU + CoCo** | 6 周 | NVIDIA NCC + NRAS；CoCo Kata UVM + Trustee KBS；Secrets Manager TEE-gated 释放 | 真实的 LLM 推理任务携带复合 CAE 上链 fulfill |
| **P3 — 多后端 + 计费** | 4 周 | SEV-SNP、Nitro 次级后端；CIP-10 `BillingAttestation.tee_signature` 接入 `0x05`；measurement 治理更新流程 | ≥ 2 个 TEE 后端并行运行；对恶意 Runner 行使争议窗口 |

合计约 18 周。与 CIP-10 容器运行时并行，共享 CoCo + Trustee 栈。

---

## 附录 A：前期研究术语 ↔ Cowboy 术语映射

| 前期研究术语 | Cowboy 实现 |
|---|---|
| `tee_call` syscall | `cowboy_sdk.tee.tee_call()` → `SubmitJob` 指令 |
| CAE | `cowboy_types::tee::CompositeAttestation` |
| Service Registry | CIP-2 Runner Registry + `measurement_binding` |
| `MsgFulfillAIRequest` | `submit_verified_result`（CIP-2 commit-reveal）|
| `AIRequest` / `AIFulfill` events | `JobSubmitted` / `JobFulfilled`（可加 `tee_attested` flag）|
| pyvm-contract / pyvm-agent | Cowboy PVM (RustPython) / CIP-10 OCI CPython 容器 |
| verify / replay 路径 | Cowboy speculative execution + cached batch apply |

## 附录 B：2026-04 TEE 业态调研

本附录记录了为 §3.3 硬件选型、§3.9 `Deterministic` 模式限制与 §7 路线图后端排序提供依据的 TEE 生态快照。"Cowboy 定位"一列记录本 CIP 对每项条目的采纳态度。

### B.1 硬件 / 平台 / 云执行环境

| 项目 | 架构 | 实现类型 | 安全隔离机制 | 是否开源 | 云服务集成 | 2026-04 现状与 Cowboy 定位 |
|---|---|---|---|---|---|---|
| **Intel SGX** | x86 | Enclave | CPU 级内存加密 + EPC + enclave | 部分（硬件专有，Linux 栈开源）| Azure Confidential Compute（SGX VM / AKS 节点）| IAS/EPID 已于 2025-04-02 EOL；生态转向 DCAP / Intel Trust Authority。Linux SGX 栈仍维护。**Cowboy：** `legacy` 档位；仅允许在 `EconomicBond` 模式下使用，**不得**用于 `Deterministic`（§3.3、§3.9）。|
| **Intel TDX** | x86 | Confidential VM | VM 级硬件隔离 + 内存加密 + Trust Domain | 部分（硬件专有，生态部分开源）| Azure / Google / Alibaba | Intel 将 TDX 定位为 newest confidential computing technology；Azure 与 Google 均已提供相关 confidential VM 路线。**Cowboy：** **主线 CPU 后端**（§3.3）；P1 MVP 目标（§7）。|
| **AMD SEV / SEV-ES / SNP** | x86 | VM 内存加密 | 每 VM 密钥 + 页级内存加密；SNP 额外完整性保护 | 部分（硬件专有，QEMU / KVM 开源）| Azure Confidential VM、Google Confidential VM | 当前公开生态已明显由 SEV / SEV-ES 转向 SEV-SNP；主流云均强调无需代码改动的 VM 级机密计算。**Cowboy：** **次选后端**（§3.3）；P3 目标（§7）。|
| **AWS Nitro Enclaves** | Nitro 平台（Intel / AMD / Graviton）| 隔离 enclave VM | Nitro 隔离 + vsock-only 本地通信 + 无外网 / 无持久化 | 部分（平台专有，CLI / SDK 开源）| AWS EC2 / KMS | AWS 成熟路线；支持多数 Intel / AMD / Graviton Nitro 实例。parent instance 可用 Linux 或 Windows Server 2016+，enclave 本体仅运行 Linux。**Cowboy：** **次选后端**（§3.3）；P3 目标（§7）。|
| **ARM TrustZone / OP-TEE** | ARM | Secure World TEE | Secure / Normal World 分离 | 是（OP-TEE）| OP-TEE / 设备厂商生态 | OP-TEE 组织仓库在 2025 年仍持续更新；TrustZone 仍是移动与嵌入式设备侧主流 TEE。**Cowboy：** **不纳入**本 CIP——设备侧 TEE 不在服务端链下计算范围。|
| **Arm CCA / RME / Realm** | Armv9-A | Realm / Confidential VM | RME + Realm World + Root/Monitor | 部分（参考栈开源）| Arm 参考生态（新兴）| Arm 已把 CCA 作为面向云端与 AI 的 confidential computing 路线，并提供 Realm 与 attestation 相关文档 / 示例；生态尚新。**Cowboy：** **第三梯队**（§3.3）；待商用供给稳定后再评估。|

### B.2 运行时 / SDK / 容器落地层

| 项目 | 平台 | 实现类型 | 隔离 | 是否开源 | 2026-04 现状与 Cowboy 定位 |
|---|---|---|---|---|---|
| **Gramine** | x86（SGX）| LibOS for SGX | LibOS + SGX enclave | 是 | 官方文档仍将其定位为在 Intel SGX 中运行 Linux 应用；GitHub 最新 release v1.9。SGX 主线 LibOS，非多后端。**Cowboy：** **不采用**——CIP-23 放弃 SGX LibOS，转向 VM 级机密计算（TDX/SNP）。|
| **Occlum** | x86（SGX）| LibOS for SGX | 单 enclave 内多进程 LibOS + SGX | 是（Apache-2.0 / BSD）| GitHub releases 最新 0.31.0（2025-03-24），继续聚焦高性能 SGX LibOS。**Cowboy：** **不采用**——理由同 Gramine。|
| **Open Enclave SDK** | x86 / ARM | Enclave SDK | SDK 抽象 + 后端 enclave / TEE | 是（MIT）| README 仍强调 Intel SGX 与 preview 级 OP-TEE / TrustZone 支持；repo 2025 年仍有更新。偏开发 SDK，而非少改动迁移工具。**Cowboy：** **不采用**——CIP-23 直接基于 DCAP + NRAS，不走抽象 enclave SDK 层。|
| **Confidential Containers (CoCo) / Trustee** | 多架构 | 机密容器栈 | Kata UVM / TEE + remote attestation + KBS secret release | 是 | 官方 docs 已把 TDX / SNP / SGX / Arm CCA attestation 纳入 Trustee；CoCo 已成为容器化落地的重要一层。**Cowboy：** **主线启用层**（§3.3、§3.10）；复用自 CIP-10 容器运行时。Trustee/KBS 是 `Secrets Manager (0x04)` 密钥释放的基础。|

### B.3 研究 / 仿真 / 已归档项目（非生产选项）

| 项目 | 平台 | 实现类型 | 是否开源 | 2026-04 现状与 Cowboy 定位 |
|---|---|---|---|---|
| **Open-TEE** | x86 / Linux | Virtual TEE / 仿真框架 | 是（Apache-2.0）| 开发 / 测试工具，面向 GP API 原型；不适合作为生产级硬件机密计算方案。**Cowboy：** **不采用**；仅可用于本地测试脚手架。|
| **Keystone** | RISC-V | Enclave framework | 是 | 官方文档仍强调当前版本 0.X、未成熟且建议仅用于研究；GitHub 2025 年仍有更新。**Cowboy：** 保留在 RISC-V / 研究路线；非商用目标。|
| **Hex Five MultiZone** | RISC-V | Embedded partition TEE | 是（主仓库已于 2025-05-07 archived / read-only）| 已归档，仅供历史参考。**Cowboy：** **不考虑**。|
| **Sanctum** | RISC-V / 研究原型 | Secure processor architecture | 是（研究原型）| MIT CSAIL 项目页最后更新时间仍为 2017-10-13；为历史研究项目。**Cowboy：** **不考虑**。|

### B.4 权威来源

- Intel TDX：<https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/overview.html> · <https://learn.microsoft.com/en-us/azure/confidential-computing/virtual-machine-options> · <https://cloud.google.com/confidential-computing/confidential-vm/docs/supported-configurations>
- Intel SGX / IAS EOL：<https://community.intel.com/t5/Intel-Software-Guard-Extensions/IAS-End-of-Life-Announcement/td-p/1545831> · <https://github.com/intel/confidential-computing.sgx> · <https://learn.microsoft.com/en-us/azure/confidential-computing/confidential-nodes-aks-overview>
- AMD SEV / SEV-SNP：<https://www.amd.com/en/products/processors/server/epyc/confidential-computing.html> · <https://www.qemu.org/docs/master/system/i386/amd-memory-encryption.html> · <https://cloud.google.com/confidential-computing/confidential-vm/docs/confidential-vm-overview> · <https://learn.microsoft.com/en-us/azure/confidential-computing/skr-flow-confidential-vm-sev-snp>
- AWS Nitro Enclaves：<https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave.html> · <https://docs.aws.amazon.com/enclaves/latest/user/getting-started.html> · <https://docs.aws.amazon.com/enclaves/latest/user/hello-kms.html>
- ARM TrustZone / OP-TEE：<https://optee.readthedocs.io/en/latest/general/about.html> · <https://github.com/op-tee>
- Arm CCA / Realm：<https://www.arm.com/architecture/security-features/arm-confidential-compute-architecture> · <https://learn.arm.com/learning-paths/cross-platform/cca_rme/cca/> · <https://learn.arm.com/learning-paths/servers-and-cloud-computing/cca-container/overview/>
- Gramine：<https://gramine.readthedocs.io/> · <https://github.com/gramineproject/gramine/releases>
- Occlum：<https://github.com/occlum/occlum> · <https://github.com/occlum/occlum/releases>
- Open Enclave SDK：<https://github.com/openenclave/openenclave>
- Confidential Containers / Trustee：<https://confidentialcontainers.org/docs/overview/> · <https://confidentialcontainers.org/docs/attestation/> · <https://confidentialcontainers.org/docs/attestation/installation/>
- Open-TEE：<https://github.com/Open-TEE/Open-TEE> · <https://open-tee.github.io/documentation/>
- Keystone：<https://docs.keystone-enclave.org/en/latest/Getting-Started/index.html> · <https://github.com/keystone-enclave>
- Hex Five MultiZone：<https://github.com/hex-five/multizone-sdk>
- Sanctum：<https://www.csail.mit.edu/research/sanctum-secure-processor>
- Cowboy 内部研究 — PythonVM × TEE 安全内核架构笔记（参见 `research/`）
- 设计背景：`refs/plans/cowboy-tee-execution-design.md`
