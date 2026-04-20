# Cowboy TEE Execution — 实施设计方案

**Status:** Draft · Design · 2026-04-20
**Scope:** `node/` + `runner/` + `pvm/` + `refs/cips`
**Related:** CIP-2, CIP-10, CIP-3, CIP-1, Cowboy TEE Secure-Kernel Research, TEE_revision_2026_04

---

## 0. 摘要 (TL;DR)

本方案把 **硬件 TEE（CPU Confidential VM + GPU NCC）** 作为 Cowboy Runner 执行 AI/私密工作负载的"安全内核"，并给出从现状（纯占位桩）到生产可用（端到端远程证明 + 确定性重放）的**单一、分阶段路径**。关键决策：

| 维度 | 选择 | 理由 |
|---|---|---|
| **CPU TEE 主线** | Intel TDX（机密 VM） | 2026 年产业方向已从 SGX enclave 切到 VM 级机密计算（TDX/SEV-SNP）；主流云（Azure/GCP/阿里）原生支持；无需重写 Runner 代码 |
| **GPU TEE 主线** | NVIDIA Confidential Compute (NCC / H100/H200) | AI 负载刚需；原生配合 TDX passthrough；Private ML SDK (dstack/NearAI) 已跑通 99% 性能 |
| **次要后端** | AMD SEV-SNP, AWS Nitro Enclaves, ARM CCA | Runner 可选注册；用同一 CAE 信封适配，不改链上协议 |
| **启用层** | Confidential Containers (CoCo) + Trustee / KBS | 与 CIP-10 OCI 容器天然对齐，避免 bespoke enclave SDK |
| **证明格式** | CAE v1 (Composite Attestation Envelope) | CPU Quote + GPU NCC Report + 证书链 + 服务签名；on-chain 只存摘要/锚点，完整证据在 receipts 存储层 |
| **验证路径** | verify / replay 解耦 | 链节点**不**再次访问 TEE，只验证签名和 measurement 锚点；任意节点可重放达到相同状态 |
| **不做的事** | 不在 PVM 内部跑 enclave、不自研 attestation SDK、不在 L1 state 上存整份 quote | 降本保 simplicity；用既有产业栈 |

**当前代码基线（2026-04-20）**：TEE Verifier Actor（`0x05`）、`TeeAttestation` 结构、Deterministic 模式已落位；`TeeVerifier::verify()` 无条件返回 `Ok(())`、dispatcher 只检查 `tee_support` 布尔位、Runner 无 quote 生成代码。本方案把这些桩替换为真实签名验证与 attestation 流程，并补齐 CAE、Registry、Billing Attestation 三条链路。

---

## 1. 动机

### 1.1 现状问题
来自 `Explore` 审计（见 §12 代码改造清单）：

1. `runner/crates/tee-verifier/src/verifier.rs:108-113`：`verify()` **无条件返回 `Ok(())`**，没有签名/测量/证书链校验。
2. `runner/crates/result-verifier/src/verifier.rs:258-265`：Deterministic 模式只检查 `tee_attestation` **字段是否存在**，从不调用 verifier。
3. `node/execution/src/runner/dispatcher.rs`（候选过滤）：`tee_required` 只对 `runner.capabilities.tee_support.is_some()` 做布尔判断，Runner 可以任意声明自己"支持 SGX"而无需任何证据。
4. `runner/crates/secrets-manager/src/manager.rs:29-101`：`get_secret(tee_attestation: Option<…>)` 参数接收但**完全未使用**。
5. `runner/` 整棵树无任何 Intel DCAP / NVIDIA NRAS / AMD SEV / AWS Nitro / gVisor / Kata 调用；`TeeAttestation { tee_type, attestation_data, measurement_hash, signature }` 字段在测试中全是 `0u8`。
6. CIP-10 §12.3 定义了 `BillingAttestation` 但代码里**完全未实现**。

### 1.2 白皮书与 Cowboy 内部研究要求（见 `research/`）

- **"四不知"问题**：Runner 在哪、跑什么、谁在跑、怎么跑。只有硬件证明能把这四问答完。
- **计算/共识解耦**：AI 不可能在每个 L1 节点上重新执行；必须"一次计算、多方验证、任意节点重放"。
- **端到端远程证明**：证书链 → CPU TDX 测量 → GPU NCC 测量 → 服务签名 → 时效/防重放 → 原子提交。任一环失败都回滚。
- **两类 Python 域**：链上 `pyvm-contract`（确定性子集）只能调用 `tee_call` 这一个 syscall；链下 `pyvm-agent`（在 TEE 内）跑完整 Python + AI 栈。

### 1.3 设计目标（优先级排序）

| # | 目标 | 不做的事 |
|---|---|---|
| G1 | 能在 L1 上对 CPU+GPU 复合证明做可重放的验证 | 不在链节点内拉取 quote |
| G2 | Runner 注册即绑定 measurement；无证明不得进入 VRF 候选池 | 不信任 Runner 自声明的 `tee_support` 布尔 |
| G3 | Deterministic + TEE 模式真正做签名与 measurement 比对 | 不做 PVM 内部 enclave |
| G4 | Secrets Manager 在释放密钥前强制验证 attestation 新鲜度 | 不在链上存明文 secret |
| G5 | 与 CIP-10 CoCo/Trustee 容器栈对齐，复用 BillingAttestation 做 TEE 签名计费 | 不自研容器运行时 |
| G6 | 向后兼容：non-TEE Runner 继续用 EconomicBond/MajorityVote 工作 | 不强制全网 TEE |

---

## 2. 威胁模型

**受保护资产**：用户输入、模型权重（若敏感）、推理中间态、短期 secret（API key）、计费证据。

**可信根**：
- Intel：Root CA → PCS（Platform Certification Service）→ TDX Module → TD（Trust Domain）measurement
- NVIDIA：NVIDIA Root → GPU Attestation Root → Per-GPU NCC report + measurement (MRTD 等价物)
- AMD：AMD Root → VCEK → SEV-SNP report
- AWS：Nitro PCR → Nitro attestation doc（COSE_Sign1）

**威胁/对抗者能力**：
| 威胁 | 防御 |
|---|---|
| 恶意 Runner 伪造 attestation | DCAP/NRAS 根证书链 + measurement 白名单（on-chain） |
| Runner 物理节点被攻破后抓 quote | TDX/NCC 内存加密 + 完整性保护；IAS EPID 已 EOL，只接受 DCAP/ITA |
| Quote 重放 | `nonce = H(task_id ‖ req_hash ‖ deadline)` 强制写入 report `user_data`；on-chain 校验 nonce 与 task 绑定 |
| Measurement 被偷偷升级 | Registry 要求 measurement 升级走治理 / 延迟生效；旧 measurement 在 `deprecated` 状态下可验证历史结果但不可接新任务 |
| 链节点侧信道 | 链节点只做 verify/replay，**不做 AI 计算**，侧信道不波及共识 |
| GPU 内存残留 | NCC + 强制 MIG/single-tenant 模式（CIP-10 §14.6）+ 结束时 memory clear |
| Secrets 从 kernel 泄漏 | TEE sealed storage；链上只存 encrypted-with-measurement 密文 |
| Billing 作弊 | TEE 签名的 `BillingAttestation` 权威；非 TEE fallback 到 `max_compute_cost` 已锁定额度（CIP-10 §12.3）|

**非目标**：防御 TEE 硬件厂商后门、防御物理内存解焊（学术级物理攻击）。

---

## 3. 与现有 CIP/代码的关系

| 接口 | CIP 地址 | 代码符号 | TEE 方案改动 |
|---|---|---|---|
| Runner Registry | `0x01` | `runner/src/registry.rs` | **新增** `measurement_binding` 字段；注册走 attestation-first |
| Job Dispatcher | `0x02` | `node/execution/src/runner/dispatcher.rs` | `tee_required` 改为查 Registry 的 measurement 绑定状态，而非 runner 自声明 |
| Result Verifier | `0x03` | `node/execution/src/runner/verifier.rs`, `runner/crates/result-verifier` | Deterministic/TEE 模式真正调 Verifier Actor；验证 CAE 信封 |
| Secrets Manager | `0x04` | `runner/crates/secrets-manager` | 释放前强制 verify(attestation, freshness) |
| **TEE Verifier** | `0x05` | `runner/crates/tee-verifier`（桩） | 本方案主要改造对象 |
| Entitlement Registry | `0x07` | `node/runner/src/entitlement.rs` | 新增 `Scope::TeePool(measurement)` 用于合规分组 |
| Runner Container | CIP-10 | `runner/crates/runner-node` | CVM 镜像 + CoCo/Trustee 集成；`BillingAttestation` 落地 |

### 3.1 与 PVM 的关系
**不动 PVM 确定性约束**。TEE 完全是链下 Runner 侧的事；PVM 只负责把 `submit_job(tee_required=true)` 传下去、把 VerifiedResult 回传上来。Cowboy 内部研究中"单入口 syscall `tee_call(service_id, payload, mode="async")`"的设计意图，在 Cowboy 上直接由 `SystemInstruction::SubmitJob{ verification: { mode: Deterministic, tee_required: true, … } }` 承担——对 Actor 代码无变化。

---

## 4. 硬件栈选型（证据：`research/TEE_revision_2026_04__en.csv`）

| 栈 | 主线 | 备选 | 备注 |
|---|---|---|---|
| **CPU** | Intel TDX（机密 VM） | AMD SEV-SNP、AWS Nitro | SGX enclave **不做主线**——IAS EPID 2025-04-02 EOL；SGX 生态整体降温 |
| **GPU** | NVIDIA NCC（H100/H200） | ARM CCA + Accelerator CC（远期） | 对 AI Runner 不可替代；dstack/NearAI 已在生产 |
| **启用层** | Confidential Containers (CoCo) + Trustee/KBS | Kata UVM | 对齐 CIP-10 OCI；Trustee 统一了 TDX/SNP/SGX/CCA attestation 验证 |
| **Attestation 服务** | Intel Trust Authority (ITA) 或自托管 PCCS（DCAP） + NVIDIA NRAS | Azure Attestation, GCP CAS | 离线验证路径走 DCAP 根证书 + PCS collateral；不强依赖 Intel SaaS |
| **Runtime 选择** | `runc` + nvidia-container-runtime（CIP-10 §15.1 已选） | `crun`/`runsc` | 与 CIP-10 保持一致 |

**关键放弃**：
- ❌ Gramine/Occlum（SGX LibOS）：SGX 降温，2GB EPC 限制对 LLM 不友好
- ❌ Open Enclave SDK：偏 C/C++ 开发框架，不是部署层
- ❌ Keystone（RISC-V）、Hex Five（归档）、Sanctum（2017 停更）：研究阶段

---

## 5. 整体架构

```
                      ┌─────────────────────────────────────┐
  链上 (deterministic) │            Cowboy L1                │
                      │                                     │
   ┌───────┐          │  ┌───────────┐   ┌───────────────┐  │
   │ Actor │──tx─────▶│  │ Dispatcher│──▶│ Result        │  │
   │ code  │          │  │   (0x02)  │   │ Verifier      │  │
   │(PVM)  │          │  └─────┬─────┘   │   (0x03)      │  │
   └───────┘          │        │         └──────┬────────┘  │
                      │        ▼                ▼           │
                      │  ┌───────────┐   ┌───────────────┐  │
                      │  │ Runner    │   │ TEE Verifier  │  │
                      │  │ Registry  │◀──│    (0x05)     │  │
                      │  │  (0x01)   │   │  CAE verify   │  │
                      │  └─────┬─────┘   └──────┬────────┘  │
                      │        │                │           │
                      │        │         ┌──────▼────────┐  │
                      │        │         │ Secrets Mgr   │  │
                      │        │         │   (0x04)      │  │
                      │        │         └───────────────┘  │
                      └────────┼─────────────────────────────┘
                               │ submit_result + CAE
                               │
  链下 (TEE Runner)             ▼
  ┌────────────────────────────────────────────────────────┐
  │ Host (untrusted)                                       │
  │  ┌─────────────────────────────────────────────────┐   │
  │  │ CoCo + Kata UVM / Confidential VM               │   │
  │  │  ┌─────────────────────────────────────────┐   │   │
  │  │  │ TD (TDX) / CVM (SNP)                    │   │   │
  │  │  │  ┌───────────────────────────────────┐  │   │   │
  │  │  │  │ OCI Container (CIP-10 image)      │  │   │   │
  │  │  │  │  - pyvm-agent / model harness     │  │   │   │
  │  │  │  │  - CIP-9 FUSE mounts              │  │   │   │
  │  │  │  │  - GPU passthrough (NCC on H100)  │  │   │   │
  │  │  │  └───────────────────────────────────┘  │   │   │
  │  │  │  - guest-agent (quote gen, key derive)  │  │   │   │
  │  │  └─────────────────────────────────────────┘  │   │   │
  │  │                                                 │   │   │
  │  │  Trustee KBS (secret release gated by quote)    │   │   │
  │  └─────────────────────────────────────────────────┘   │
  │  Runner daemon (untrusted): job polling, result submit │
  └────────────────────────────────────────────────────────┘
```

**数据流（一个 `tee_required=true` 任务）**：

1. Actor 调 `submit_job(verification.mode=Deterministic, tee_required=true)` → Dispatcher
2. Dispatcher 从 Registry 拉取**仅包含有效 measurement 绑定**的候选集，Fisher-Yates VRF 选 M 个
3. Runner 拉取任务 → guest-agent 生成 `quote(user_data = H(task_id ‖ req_hash ‖ nonce))`
4. CVM 内执行 AI 推理（pyvm-agent 或 OCI 容器）
5. Runner 构造 CAE envelope → 提交 `commit(H(result))` → 后续 reveal
6. Verifier (`0x03`) 调 TEE Verifier (`0x05`) 做 CAE 验证：证书链 → measurement → 服务签名 → nonce 绑定 → 时效
7. 通过后 emit `AIFulfill`、触发 deferred callback（CIP-1）
8. 任意节点重放：用 on-chain 存的 CAE 摘要 + Registry anchor 重算，不再访问 TEE

---

## 6. CAE v1：Composite Attestation Envelope 规范

### 6.1 结构（codec = D-CBOR，与 CIP-3 保持一致的确定性编码）

```rust
// cowboy_types::tee
pub struct CompositeAttestation {
    pub version: u16,                         // = 1
    pub cpu: CpuAttestation,
    pub gpu: Option<GpuAttestation>,          // AI 任务必须有；HTTP 纯转发可无
    pub service_sig: ServiceSignature,
    pub freshness: FreshnessAnchor,
    pub extra: BTreeMap<String, Vec<u8>>,     // 预留扩展
}

pub struct CpuAttestation {
    pub tee_type: CpuTeeType,                 // Tdx | SevSnp | Nitro | Sgx (legacy)
    pub quote: Vec<u8>,                       // raw quote (TDX: TDQuoteV4; SNP: AMD Report)
    pub cert_chain_cid: Cid,                  // 证书链放 IPFS/relay，on-chain 只存 CID
    pub measurement: [u8; 48],                // MRTD (TDX) / LAUNCH_DIGEST (SNP) / PCR0..3 (Nitro)
    pub pcr_extension: Option<[u8; 32]>,      // RTMR0..3 扩展哈希（TDX）
}

pub struct GpuAttestation {
    pub tee_type: GpuTeeType,                 // NvidiaNcc
    pub nras_token: Vec<u8>,                  // NRAS 签发的 JWT (EAT 格式)
    pub gpu_measurement: [u8; 48],            // NCC measurement
    pub bound_cpu_pubkey: [u8; 32],           // 证明 CPU-GPU channel 已绑定（dstack 协议）
}

pub struct ServiceSignature {
    pub scheme: SigScheme,                    // Ed25519 | EcdsaP256
    pub service_pubkey: [u8; 32],
    /// sig = Sign_service(task_id ‖ req_hash ‖ H(result) ‖ attest_digest)
    pub sig: Vec<u8>,
}

pub struct FreshnessAnchor {
    pub nonce: [u8; 32],                      // = keccak(task_id ‖ req_hash ‖ submission_block_hash)
    pub deadline: u64,                        // block height
    pub generated_at: u64,                    // block height when quote was requested
}
```

`user_data` (TDX `REPORTDATA` / SNP `REPORT_DATA` / Nitro `user_data`) **必须等于**：
```
user_data = keccak256(nonce ‖ service_pubkey ‖ gpu_measurement_if_any)
```
这把 CPU quote ↔ service 签名 ↔ GPU NCC ↔ 任务绑定成一个不可分拆的证据包。

### 6.2 验证顺序（Verifier Actor 0x05）

```text
fn verify_cae(cae, task_id, req_hash, registry):
    1. 时效：now < deadline && (now - generated_at) < MAX_QUOTE_AGE (=150 blocks)
    2. 防重放：nonce 未在 seen_nonces[task_id] 中命中
    3. 证书链：按 cae.cpu.tee_type 选根证书，验证 cae.cpu.quote 签发链
       - TDX: PCS root → TD Module → TD
       - SNP: AMD root → VCEK → Report
       - Nitro: AWS Nitro root → Signing cert → attestation doc
    4. measurement 匹配：cae.cpu.measurement ∈ registry[service_id].allowed_cpu_measurements
       AND cae.gpu.gpu_measurement ∈ registry[service_id].allowed_gpu_measurements
    5. user_data 绑定：quote.REPORTDATA == keccak(nonce ‖ service_pubkey ‖ gpu_measurement?)
    6. 服务签名：Verify(service_pubkey, task_id ‖ req_hash ‖ H(result) ‖ attest_digest, sig)
    7. GPU NRAS token：Verify(NRAS_root_pubkey, nras_token) && token.claims.measurement == gpu_measurement
    8. 全通过 → 返回 Ok；写 seen_nonces[task_id] ← nonce
    任一失败 → 对应错误码
```

### 6.3 On-chain 存储策略
| 字段 | 位置 | 理由 |
|---|---|---|
| `attest_digest = keccak(cae_cbor)` | `task/result/<task_id>.cae_digest` | 审计可查 |
| `service_pubkey` + `cpu_measurement` + `gpu_measurement` | 已在 Registry | 无需重复 |
| 整个 CAE（几十 KB 的 quote + 证书链） | Relay Node (CIP-9) 或 IPFS，只在链上存 CID | 不压 state 膨胀 |
| `seen_nonces[task_id]` | 临时，75 blocks 后 GC（与 `DISPUTE_WINDOW_BLOCKS` 对齐） | 防重放 |

---

## 7. TEE Verifier 系统 Actor (`0x05`)

### 7.1 状态

```rust
pub struct TeeVerifierState {
    // 根证书锚点（治理更新）
    pub roots: BTreeMap<CpuTeeType, Vec<RootCert>>,          // Intel/AMD/AWS 根证书
    pub nras_root: Vec<u8>,                                  // NVIDIA NRAS 公钥
    // measurement 白名单（per service，reference 到 Registry）
    // 防重放：per-task nonces，GC 策略见 §6.3
    pub seen_nonces: BTreeMap<JobId, BTreeSet<[u8; 32]>>,
    pub last_gc_block: u64,
}
```

### 7.2 Handlers（SystemInstruction 扩展）

| Opcode | Handler | Caller | 动作 |
|---|---|---|---|
| 50 | `VerifyCae { cae, job_id, req_hash, result_hash }` | Result Verifier `0x03` | 按 §6.2 执行；返回 `Ok` / 结构化错误码 |
| 51 | `UpdateCpuRoot { tee_type, cert_der, effective_at }` | Governance `0x09` | 治理更新根证书，`effective_at` 延迟生效 ≥ 1 week |
| 52 | `UpdateNrasRoot { pubkey, effective_at }` | Governance | 同上 |
| 53 | `GcNonces { upto_block }` | Anyone (permissionless gc) | 清理过期 seen_nonces |

**Gas 估算**（参考 CIP-3 常量比例）：
| 操作 | Cycles | Cells |
|---|---|---|
| `VerifyCae` (TDX+NCC) | 200,000 | 64 (digest only) |
| 证书链验证（7 层 ECDSA） | ~120,000 | 0 |
| measurement 查 Registry | 500 | 0 |
| nonce set 写入 | 1,000 | 32 |

总计 ~200k Cycles 远低于 `BLOCK_CYCLES_TARGET = 10M`，每 block 可验证 ~50 个 CAE。

### 7.3 错误码（Cowboy TEE 规范约定，映射到 `runner_common::errors::VerificationError`）

```rust
pub enum TeeVerifyError {
    AttestFail,         // 证书链失败
    RegistryMismatch,   // measurement 不在白名单
    SigInvalid,         // 服务签名错误
    TaskExpired,        // deadline 已过
    TaskReplayed,       // nonce 命中 seen_nonces
    InvalidResultHash,  // attest_digest 中的 H(result) 与实际不符
    UnsupportedTeeType, // 根证书未配置
    TeeUnavailable,     // sync 路径下 Runner 拿不到 quote（非 verifier 错，但共用枚举）
    NonceBindingFail,   // user_data != keccak(nonce‖pubkey‖gpu_m)
}
```

---

## 8. Runner 侧改造

### 8.1 镜像与部署

**CVM image（新）**：`cowboy/runner-tee-base:v1`（CIP-10 §5.5 扩展）
- Base: Ubuntu 22.04 + TDX guest kernel + nvidia-container-toolkit
- 预装：`guest-agent`（quote 生成）、CoCo attestation-agent、`cowboy-runner` 二进制
- Measurement 可复现构建（Yocto 或 buildroot 固定 layer 哈希）

**Host 约束**：
- Host OS 不可信；只运行 KVM + QEMU-TDX + `dstack-vmm` 等价物
- 每个 Job 启动一个全新 CVM；run-to-completion；销毁时擦除 memory

### 8.2 注册流程（attestation-first）

取代当前"Runner 自声明 `tee_support: Some(Sgx)`"的做法：

```text
1. Runner 启动 CVM，guest-agent 生成 ephemeral ed25519 keypair (service_key)
2. 调 RegisterRunner(
       stake, rate_card,
       initial_attestation: CpuAttestation + GpuAttestation,
       service_pubkey: pub(service_key),
       measurement_refs: claimed measurement IDs,
   )
3. Runner Registry 调 TeeVerifier.VerifyAttestation(initial_attestation)
   - user_data 绑定 = keccak(runner_addr ‖ registration_block_hash)
   - 必须证书链有效 + measurement ∈ 已批准白名单
4. 成功 → 存入 Registry.runners[addr].measurement_binding = {
       cpu_measurement, gpu_measurement, service_pubkey, bound_at, expires_at
   }
5. 失败 → 拒绝注册；stake 不扣（未动过）
```

**续约**：measurement_binding 每 ~7 天（12096 blocks @ 500ms）必须续约（提交新 CAE）。到期未续约自动降级到 non-TEE（如允许），或从 TEE 候选池移除。

### 8.3 Job 执行

```python
# guest-agent 内部（对 Runner 应用透明）
nonce = keccak256(task_id ‖ req_hash ‖ submission_block_hash)
result = run_job_in_cvm(task)     # pyvm-agent or OCI entrypoint
gpu_report = nvidia_nccli.generate_report(measurement, bound_to=service_pubkey)
user_data = keccak256(nonce ‖ service_pubkey ‖ gpu_report.measurement)
tdx_quote = tdx.get_quote(user_data)
nras_token = requests.post(NRAS, gpu_report)    # off-CVM 调用
service_sig = ed25519.sign(service_key, task_id ‖ req_hash ‖ H(result) ‖ attest_digest)
cae = CompositeAttestation(...)
# 上链
submit_commit(task_id, H(result ‖ runner_sig))
# reveal 阶段（CIP-2 §8）
submit_verified_result(task_id, result, cae_digest, cae_cid)
```

### 8.4 代码位置（新）
```
runner/crates/tee-runtime/            # 新 crate
    src/
        quote_tdx.rs                  # TDX quote 生成 (via /dev/tdx_guest or vsock)
        quote_snp.rs                  # AMD SEV-SNP
        quote_nitro.rs                # AWS Nitro
        gpu_ncc.rs                    # NVIDIA NCC + NRAS client
        cae.rs                        # CAE 构造 & 签名
        attestation_client.rs         # DCAP/ITA collateral 拉取 + 本地验证
runner/crates/tee-verifier/           # 改造现有桩
    src/
        verifier.rs                   # 删除 TODO，接入真正验证
        dcap.rs                       # Intel DCAP 验证（封装 sgx-quote-verify rust 库或 FFI 到 SGX-DCAP-quote-verification）
        snp.rs                        # SEV-SNP 验证
        nras.rs                       # NVIDIA NRAS JWT 验证
        roots.rs                      # 根证书存储
```

---

## 9. 验证模式映射

### 9.1 CIP-2 VerificationMode × TEE

| Mode | 当前实现 | TEE 改造 |
|---|---|---|
| `None` | 单 Runner，不验 | 不变 |
| `EconomicBond` | 单 Runner，仅靠 stake | **可选** 加 `tee_required=true` → 单 TEE Runner + CAE；适用于私密推理 |
| `MajorityVote` | N-of-M 字段多数 | 不变；TEE 可选 |
| `StructuredMatch` | 字段级校验 | 不变；TEE 可选 |
| `Deterministic` | 字节级相同 + `tee_required` 字段检查 | **强制** `tee_required=true`；**强制** 验 CAE；非 CAE 结果直接 reject |
| `SemanticSimilarity` | N-of-M 语义聚类 | 不变；TEE 可选 |

### 9.2 Result Verifier 改造（`node/execution/src/runner/verifier.rs` 与 `runner/crates/result-verifier`）

替换 `verifier.rs:258-265` 的占位：

```rust
// 伪代码
if job_spec.verification.tee_required {
    for result in results {
        let cae = result.tee_attestation
            .as_ref()
            .ok_or(VerificationError::MissingTeeAttestation)?;
        // 调链上 TEE Verifier Actor
        engine.call_system(TEE_VERIFIER, VerifyCae {
            cae: cae.clone(),
            job_id,
            req_hash,
            result_hash: keccak256(&result.data_bytes),
        })?;
    }
}
// 在 Deterministic 模式下再做字节级比对
if mode == Deterministic {
    require_byte_identical(&results)?;
}
```

---

## 10. Secrets Manager (`0x04`) 与 TEE-gated 释放

### 10.1 释放流程

```text
1. Actor 调 GetSecret { secret_id, task_id }（间接通过 SubmitJob 传递，不直出给用户）
2. Secrets Manager Actor 查 AccessPolicy:
     - allowed_measurements: BTreeSet<[u8; 48]>
     - allowed_services: BTreeSet<Pubkey>
     - min_attestation_age_blocks
3. Runner 在 CVM 内调 Trustee/KBS
4. KBS 要求最新 CAE → Cowboy L1 反查（见 §10.2 拉模式 vs 推模式）
5. 验证通过 → KBS wrap secret using service_pubkey（ECIES/HPKE）
6. Runner 收到后只能在 CVM 内解密；明文永不落盘
```

### 10.2 on-chain vs off-chain KBS 选择

**推荐**：**链上登记 + 链下 KBS 执行**
- Cowboy L1 只存 `encrypted_blob + allowed_measurements_merkle_root`（encrypted to KBS master key）
- KBS 节点（信任分散，例如 3-of-5 threshold）做实际释放
- 优点：链上不存明文 / 不做 HPKE 运算；利用 CoCo Trustee 现成协议（CoCo attestation-agent 已有）
- 代价：KBS 集群需要独立运维；本阶段可以先跑中心化 KBS，后续治理迁移到 threshold

### 10.3 代码改造

`runner/crates/secrets-manager/src/manager.rs:29`：
```rust
async fn get_secret(
    &self,
    secret_id: SecretId,
    tee_attestation: Option<CompositeAttestation>,
    task_id: JobId,
) -> Result<SealedSecret> {
    let att = tee_attestation.ok_or(MissingAttestation)?;
    let policy = self.policies.get(&secret_id).ok_or(NotFound)?;
    // 新增：强制校验
    self.tee_verifier.verify_cae_for_secret(&att, &policy)?;
    // 只返回 HPKE 密文（由 KBS 预 wrap），Runner 在 TEE 内解
    Ok(self.kbs.fetch_wrapped(secret_id, att.service_pubkey).await?)
}
```

---

## 11. PVM / Agent 分层与 `tee_call` 语义

Cowboy TEE 研究中提出的"单入口 `tee_call`"开发体验**不引入新的 PVM syscall**，而是对 Actor 开发者以 SDK helper 形式呈现，内部翻译为现有的 `SubmitJob` SystemInstruction：

```python
# cowboy_sdk/tee.py（新）
def tee_call(
    service_id: str,
    payload: dict | bytes,
    *,
    mode: Literal["async"] = "async",
    deadline_blocks: int = 50,
    opts: dict | None = None,
) -> TaskId:
    """统一 syscall：对 Actor 透明地走 VRF → TEE Runner → CAE → deferred callback。"""
    return cowboy_sdk.submit_job(
        job_type=JobType.Llm(service_id=service_id, payload=payload, opts=opts or {}),
        verification=VerificationConfig(
            mode=VerificationMode.Deterministic,
            tee_required=True,
            runners=1,                # EconomicBond + TEE = 1 Runner
            dispute_window_blocks=75,
        ),
        callback=CallbackInfo(handler="on_fulfill"),
        timeout_blocks=deadline_blocks,
    )
```

**两类 Python 域**：
- `pyvm-contract`（on-chain）：保持现有确定性子集（见 `pvm/crates/pvm-runtime`），`tee_call` 只是生成一笔 tx，不引入任何不确定源
- `pyvm-agent`（in-TEE）：CoCo 容器里跑的 CPython 3.13（**不是** RustPython），允许完整网络 + GPU + LLM 栈；产物哈希锚定在 Registry

---

## 12. 代码改造清单（文件级）

### 12.1 新增

| Path | 内容 |
|---|---|
| `node/types/src/tee.rs` | `CompositeAttestation`、`CpuTeeType`、`GpuTeeType`、`MeasurementBinding`、`TeeVerifyError` |
| `node/execution/src/tee_verifier/mod.rs` | TEE Verifier Actor 状态与 handlers（见 §7） |
| `node/execution/src/tee_verifier/dcap.rs` | DCAP 封装（走 FFI to `sgx-dcap-quote-verification` 或纯 Rust `tdx-quote` 库） |
| `node/execution/src/tee_verifier/snp.rs` | SEV-SNP 验证 |
| `node/execution/src/tee_verifier/nras.rs` | NVIDIA NRAS JWT 验证 |
| `node/execution/src/tee_verifier/roots.rs` | 根证书治理表 |
| `runner/crates/tee-runtime/` | Runner 侧 quote 生成整 crate（见 §8.4） |
| `refs/cips/cip-23-tee-execution.md` | 正式化为 CIP-23（本文件是其前身） |

### 12.2 修改

| Path | 行为变更 |
|---|---|
| `node/runner/src/registry.rs` | `RunnerRecord` 加 `measurement_binding: Option<MeasurementBinding>`；`register` 流程加 attestation-first 校验 |
| `node/execution/src/runner/dispatcher.rs`（~380）| 候选过滤：`if tee_required { runner.measurement_binding.as_ref().is_some_and(\|b\| b.is_valid(now)) }`；删除对 `runner.capabilities.tee_support` 的依赖 |
| `node/execution/src/runner/verifier.rs` | Deterministic 模式调 `TEE_VERIFIER.VerifyCae` |
| `runner/crates/tee-verifier/src/verifier.rs:108-113` | 替换 `Ok(())` TODO 为真实验证（其实这一层移到链上 actor，runner 侧 crate 只保留本地 sanity check 用于提交前自检） |
| `runner/crates/secrets-manager/src/manager.rs:29,101` | `get_secret` 强制验 attestation（见 §10.3） |
| `runner/crates/result-verifier/src/verifier.rs:258-265` | 改为调 TEE Verifier Actor；删除 field-only 检查 |
| `runner/crates/runner-common/src/types.rs:589-598` | `TeeAttestation` → 替换为 `CompositeAttestation`（或保留旧名作兼容 alias） |
| `node/pvm/Lib/cowboy_sdk/` | 新增 `tee.py` helper；文档更新 `TEE_VERIFIER 0x05` |
| `runner/crates/runner-node/src/config.rs` | 新增 TEE 运行配置：root cert 路径、PCCS URL、NRAS URL |
| `node/types/README.md` | 修正 address 表（目前 `0x94/0x95` 与代码 `0x04/0x05` 不一致；以代码为准） |
| `/home/ubuntu/workspace/CLAUDE.md` | 同步修正 `0x91-0x95` → `0x01-0x05` |

### 12.3 CIP 改动

| CIP | 改动 |
|---|---|
| CIP-2 | §5 候选过滤加 measurement_binding 有效性条件；§9 Deterministic 模式明示 "必须含 CAE，由 `0x05` 验证" |
| CIP-10 §12.3 | `BillingAttestation.tee_signature` 改为 CAE 子集（共用签名/证书路径，不重复造轮子） |
| **新增 CIP-23** | 正式化本设计（CAE 格式、0x05 接口、根证书治理） |

---

## 13. 路线图（4 阶段）

| Phase | 时长 | 交付 | 退出条件 |
|---|---|---|---|
| **P0: Scaffolding** | 2 周 | `node/types/src/tee.rs`、CAE 结构体、`0x05` handler 骨架（仍返回 Ok）、`runner/crates/tee-runtime` 空骨架 | 所有类型编译通过，测试用 mock CAE |
| **P1: TDX-only MVP** | 6 周 | Intel TDX DCAP 真验证；Runner 用 QEMU-TDX + `/dev/tdx_guest` 生成 quote；注册流程 attestation-first；Deterministic+TEE 端到端能走通 | `examples/llm_chat` 在 TDX 节点上跑通；红队渗透：伪造 quote 必须被拒；Measurement mismatch 必须被拒 |
| **P2: GPU NCC + CoCo 集成** | 6 周 | H100 NCC + NRAS；CoCo Kata UVM + Trustee KBS；Secrets Manager TEE-gated 释放 | 跨 CPU+GPU 的复合证明端到端；一个真实的 Llama/Qwen 推理任务带 CAE 上链 |
| **P3: 多后端 + BillingAttestation** | 4 周 | SEV-SNP、Nitro Enclave 次级后端；CIP-10 BillingAttestation 复用 CAE 签名路径；measurement 白名单治理流程 | ≥2 个 TEE 后端并行运行；计费争议窗口实测；CIP-23 定稿 |

**总时长**：~18 周（4.5 个月）。与 CIP-10 容器运行时落地并行，共享 CoCo/Trustee 栈。

---

## 14. 开放问题与风险

| # | 问题 | 缓解 |
|---|---|---|
| R1 | Intel DCAP Rust 生态不够成熟（`sgx-dcap-quote-verification` 是 C 库，Rust wrapper 有但不完备） | P1 先 FFI；后续替换为纯 Rust `tdx-quote` 社区实现或 Automata 的 on-chain verifier 代码移植 |
| R2 | 链上 DCAP 验证 gas 偏高（单次 ~200k Cycles）| 用 Result Verifier 批次验证 + Merkle 聚合；高频任务走 ZK proof of attestation（研究阶段） |
| R3 | NVIDIA NRAS 是中心化服务 | P2 接受 NRAS 中心化；P3 研究 on-chain 缓存 + 多签 fallback |
| R4 | Measurement 白名单治理攻击（恶意添加后门 measurement） | `UpdateCpuRoot`/`UpdateNrasRoot` 强制 7 天延迟 + DAO 多签 |
| R5 | TDX 供给集中（Azure/GCP 机型有限） | Runner pool 分区：`TeePool(tdx-azure-v5)`, `TeePool(tdx-gcp-c3)`，任务可选指定或任选 |
| R6 | CAE 大（quote+证书链 30-100KB）| 只存 digest 上链，完整 CAE 走 CIP-9 relay；验证时按需拉取 |
| R7 | CVM 启动慢（10-30s 冷启动） | Warm pool：Runner 预起 N 个 CVM idle 待命；与 CIP-10 §5.4 image cache 协同 |
| R8 | 共识节点本身不跑 TEE，能否信任 | 共识只验证"别人在 TEE 里跑过"的证明；共识节点自己是否 TEE 正交（可选增强） |
| R9 | SGX EOL 风险 | 文档/代码显式标记 SGX = "legacy, EconomicBond only"；Deterministic 模式禁用 SGX |

---

## 15. 验收测试矩阵

| 测试 | 目的 | 期望 |
|---|---|---|
| `test_cae_valid_tdx_ncc_passes` | 正向：真实 TDX quote + NRAS token | verify_cae 返回 Ok |
| `test_cae_tampered_quote_rejected` | 负向：quote 中翻一个 bit | AttestFail |
| `test_cae_wrong_measurement_rejected` | 负向：TDX measurement 不在白名单 | RegistryMismatch |
| `test_cae_replayed_rejected` | 防重放：同 task_id 同 nonce 二次提交 | TaskReplayed |
| `test_cae_expired_rejected` | 时效：generated_at 超过 150 blocks | TaskExpired |
| `test_cae_missing_gpu_for_llm` | 业务语义：LLM 任务必须有 GPU CAE | RegistryMismatch |
| `test_user_data_binding_mismatch` | 强绑定：REPORTDATA 与 nonce 不一致 | NonceBindingFail |
| `test_registration_attestation_required` | Runner 注册必须过 TEE Verifier | 无有效 CAE 无法注册 |
| `test_deterministic_mode_requires_cae` | Deterministic + tee_required 下无 CAE | MissingTeeAttestation |
| `test_secret_release_denied_on_untrusted_measurement` | KBS 释放检查 measurement | Denied |
| `test_bench_verify_cae_cycles_under_250k` | Gas 预算 | cycles < 250,000 |

---

## 附录 A：Cowboy TEE 研究术语 ↔ 实施映射

| 研究术语 | Cowboy 实现 |
|---|---|
| `tee_call` syscall | `cowboy_sdk.tee.tee_call()` → `SubmitJob` 指令（无新 syscall） |
| CAE (Composite Attestation Envelope) | `cowboy_types::tee::CompositeAttestation` |
| Service Registry (`service/<service_id>`) | CIP-2 Runner Registry 加 `measurement_binding` 子结构 |
| `MsgFulfillAIRequest` | CIP-2 `submit_verified_result`（commit-reveal 路径） |
| `AIRequest` / `AIFulfill` events | CIP-2 `JobSubmitted` / `JobFulfilled`（可加 `TeeAttested` flag） |
| pyvm-contract / pyvm-agent | Cowboy PVM (RustPython) / CIP-10 OCI 容器内 CPython |
| verify/replay 路径 | Cowboy 的 speculative execution + cached batch apply 天然就是这个语义 |

## 附录 B：参考文献

**研究与白皮书**
- Cowboy 内部研究 — PythonVM × 安全内核系列笔记（归档于 `research/`）
- Cowboy 内部研究 — PythonVM × TEE 安全内核技术白皮书草案（归档于 `research/`）
- `research/TEE_revision_2026_04__en.csv`（2026-04 硬件栈现状调研）

**CIP 与白皮书**
- `refs/cips/cip-2-offchain-compute.md`（Runner framework, VerificationMode）
- `refs/cips/cip-10-runner-containers.md`（OCI container, BillingAttestation §12.3）
- `refs/cips/cip-3-fee-model.md`（双 gas 模型）
- `refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised.md`（§ TEE Attestation）

**外部规范**
- Intel TDX ABI Spec (DCAP/ITA)：https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/
- NVIDIA Confidential Computing / Remote Attestation Service (NRAS)
- AMD SEV-SNP ABI：https://www.amd.com/en/products/processors/server/epyc/confidential-computing.html
- Confidential Containers / Trustee：https://confidentialcontainers.org/docs/attestation/
- CoCo + Kata 白皮书
- Dstack / Private ML SDK（NearAI）：Yocto 可复现构建 + dstack-kms + TDX+NCC 组合

---

**Next step**：把本方案的核心决策摘要（§5 架构图、§6 CAE、§7 Verifier 接口、§13 路线图）提炼为 `refs/cips/cip-23-tee-execution.md` 走正式 CIP 流程；然后在 `refs/plans/` 下拆出 P0-P3 的四个独立实施计划（`tee-p0-scaffolding.md` 等）。
