# SoftFloat + VRF 实施结果报告

**日期**: 2026-02-21  
**范围**: 会话内完成的 SoftFloat 确定性浮点与 VRF 三层实现

---

## 一、测试结果汇总

| 模块 | 测试数 | 状态 |
|------|--------|------|
| `rustpython-vm::softfloat` | 56 passed | ✅ |
| `cowboy-chain::pvm_host` | 11 passed | ✅ |
| `runner-registry::ecvrf` | 11 passed | ✅ |
| `runner-consensus::threshold_bls_vrf` | 11 passed | ✅ |

**合计：89 个测试，全部通过，0 失败。**

---

## 二、SoftFloat 实施详情

### 2.1 目标

将 PVM 中依赖硬件浮点的函数全部替换为基于 `softfloat` crate 的纯软件 F64 运算，保证 x86_64 / aarch64 / riscv64 / wasm32 等架构上比特级一致。

### 2.2 `node/pvm/crates/vm/src/softfloat.rs`

**已替换的 12 个函数（原为硬件 f64 + 无意义“归一化”）：**

| 函数 | 实现方式 |
|------|----------|
| `tan` | `sin(x) / cos(x)` |
| `pow` | `exp(b·ln(a))`，含 NaN/±∞/负底数等 IEEE 754 边界处理 |
| `sinh` | `(e^x − e^{-x}) / 2`，小值直接返回 x 避免抵消误差 |
| `cosh` | `(e^x + e^{-x}) / 2` |
| `tanh` | `(e^{2x}−1)/(e^{2x}+1)`，\|x\|≥19 饱和为 ±1 |
| `asinh` | `ln(x + √(x²+1))` |
| `acosh` | `ln(x + √(x²−1))`，定义域 x≥1 |
| `atanh` | `ln((1+x)/(1−x)) / 2`，定义域 \|x\|<1 |
| `atan` | 两步 Range Reduction（\|x\|>tan(3π/8)、\|x\|>tan(π/8)）+ 21 项 Taylor 多项式（Horner） |
| `asin` | `atan(x/√(1−x²))`，用 (1−x)(1+x) 避免 x≈±1 时精度损失 |
| `acos` | `π/2 − asin(x)` |
| `atan2` | 象限判断 + `atan(y/x)` 的 SoftFloat 版本 |

**新增/扩展测试：**

- 基础运算、根式、指数对数、三角/反三角、双曲/反双曲、取整、取模、floor_div
- 跨平台比特级确定性：`test_cross_platform_bits_*`（add/sin/cos/tan/atan/atan2/asin/acos/sinh/cosh/tanh/pow/sqrt/exp/ln/floor_ceil_trunc）
- IEEE 754 特殊值：`test_ieee754_special_values`（NaN 传播、±∞、±0、pow 边界）
- 精度：`test_accuracy_ulp`（与原生 f64 对比，≤20 ULP）

**测试数量：** 38 → 56。

### 2.3 `node/pvm/crates/stdlib/src/math.rs`

**补全 10 个 Python `math` 函数的 `enable_softfloat` 分支：**

- `exp2`：`exp(x·ln(2))`
- `expm1`：`exp(x) − 1`
- `log`：`ln(x)/ln(base)`，含 int 转 float 的 softfloat 路径
- `log2`：`ln(x)/ln(2)`，含 BigInt 路径
- `log10`：`ln(x)/ln(10)`
- `log1p`：`ln(1+x)` 改为 `ln(softfloat::add(1, x))` 保证确定性
- `cos`：`rustpython_vm::softfloat::cos`
- `asin`：`rustpython_vm::softfloat::asin`
- `cbrt`：`sign(x)·exp(ln(|x|)/3)`，零与无穷直接返回
- `fmod`（`py_fmod`）：`rustpython_vm::softfloat::modulo`，y 无穷且 x 有限时返回 x
- `hypot`：增加 `vm` 参数，softfloat 模式下 `sqrt(sum of squares)` 全用 softfloat

### 2.4 CI 工作流 `node/pvm/.github/workflows/softfloat-cross-platform.yml`

- **矩阵目标：** x86_64、aarch64、**riscv64gc-unknown-linux-gnu**、**wasm32-wasip1**
- x86_64/aarch64/riscv64：`cross` 交叉编译 + 运行 `softfloat::tests`
- wasm32：`CARGO_TARGET_WASM32_WASIP1_RUNNER="wasmtime run --"` 编译并运行测试
- 新增 job：`softfloat-bit-consistency`，下载各目标测试输出，比较通过/失败并写入 `GITHUB_STEP_SUMMARY`

---

## 三、VRF 实施详情

### 3.1 Layer 1：PVM 随机数 — HKDF-SHA256

**文件：** `node/chain/src/pvm_host.rs`

**变更：**

- `randomness(domain)` 由 `SHA256(block_hash || domain)` 改为 **HKDF-SHA256**：
  - IKM = `block_hash`（32 字节）
  - Salt = `b"cowboy-pvm-randomness-v1"`
  - Info = 调用方传入的 `domain`
  - 输出 32 字节，API 不变

**依赖：** `node/chain/Cargo.toml` 新增 `sha2 = "0.10"`, `hmac = "0.12"`, `hkdf = "0.12"`。

**测试：**

- `test_hkdf_deterministic`、`test_hkdf_domain_separation`、`test_hkdf_block_hash_sensitivity`
- `test_hkdf_output_is_32_bytes_of_entropy`、`test_hkdf_known_vector`（RFC 5869 Test Case 1 前 32 字节）

**信标接入点：** 注释中说明，未来共识层提供 `block_vrf_output` 时，仅需将 IKM 从 `block_hash` 改为 `block_vrf_output` 即可。

**顺带修复：** `node/chain/src/execution.rs` 中 `filter(|(k, _)| k != "_handler")` 改为 `k.as_str() != "_handler"`，消除预存编译错误。

### 3.2 Layer 2：Runner 委员会选择 — EC-VRF (RFC 9381)

**新文件：** `runner/crates/runner-registry/src/ecvrf.rs`

**内容：**

- IETF EC-VRF-EDWARDS25519-SHA512-TAI（RFC 9381），基于 `curve25519-dalek` + `sha2::Sha512`。
- 类型：`VrfSecretKey`、`VrfPublicKey`、`VrfProof`（80 字节）、`VrfOutput`（64 字节）。
- API：`vrf_prove(sk, alpha)` → `(VrfOutput, VrfProof)`；`vrf_verify(pk, alpha, proof)` → `VrfOutput`。
- 辅助：`vrf_output_to_seed(&output)` 取输出前 32 字节作为选择种子。

**依赖：** `runner-registry` 增加 `curve25519-dalek`、`sha2`、`hmac`、`ed25519-dalek`、`zeroize`、`serde_bytes`、`hex`。

**`runner/crates/runner-registry/src/registry.rs`：**

- `vrf_select_runners` 由 Keccak256 迭代哈希改为 **HMAC-SHA256**：以 `vrf_seed` 为密钥，对 slot 序号做 HMAC，得到 u64 再 mod 候选数，无重复选取。

**`runner/crates/job-dispatcher/src/dispatcher.rs`：**

- `generate_vrf_seed` 改为完整 EC-VRF 证明流程：alpha = job_id || block_height(LE) || submitter；使用 `VrfSecretKey`（占位或 `DISPATCHER_VRF_SK_HEX` 环境变量）调用 `vrf_prove`，得到 output 后 `vrf_output_to_seed` 作为 32 字节种子；失败时回退到 SHA256(alpha)。

**测试：** 11 个 ecvrf 单元测试（roundtrip、确定性、不同 alpha/sk、错误 alpha/pk 验证失败、proof 序列化、tampered 验证失败等）。

### 3.3 Layer 3：共识层 — Threshold-BLS VRF 框架

**新文件：** `runner/crates/runner-consensus/src/threshold_bls_vrf.rs`

**设计：**

- t-of-n Shamir 秘密分享；每验证者持 `BlsSecretShare`，聚合公钥 `BlsAggregatePublicKey`（G2）。
- 每轮输入 `round_input = block_height || QC_{n-1}`；每验证者计算 `share_i = H(round_input)^{sk_i}`（BLS 签名形式）。
- 聚合：`threshold_vrf_aggregate(shares, threshold)` 用 Lagrange 插值在指数上重建 `H(round_input)^{sk}`。
- 验证：`ThresholdVrfOutput::verify(pk, round_input)` 使用双线性配对 `e(out, G2) == e(H(input), PK)`。

**类型：** `BlsSecretShare`、`BlsAggregatePublicKey`、`VrfShare`（index + 48 字节 G1 压缩）、`ThresholdVrfOutput`、`ThresholdVrfError`。

**hash_to_g1：** 当前为 SHA-512 到 64 字节，再 `Scalar::from_bytes_wide` 后乘以 G1 生成元；文档注明生产环境应改为 RFC 9380 hash-to-curve。

**依赖：** `runner-consensus` 增加 `bls12_381`、`sha2`、`serde_bytes`、`hex`。

**文档：** 模块头注释说明与 pvm_host 的集成方式（将 `block_vrf_output` 作为 HKDF IKM）、区块头需扩展的字段（`vrf_output`、`vrf_proof_shares`）、L1/L2/L3 迁移路径表。

**测试：** 11 个（hash_to_g1 确定性/不同输入、份额确定性、1-of-1 聚合、份额不足/重复索引错误、输出 48 字节、序列化、配对验证、Lagrange 常数多项式恢复等）。

---

## 四、修改文件清单

### 4.1 SoftFloat

| 路径 | 变更类型 |
|------|----------|
| `node/pvm/crates/vm/src/softfloat.rs` | 重写：12 个函数纯 SoftFloat，测试 38→56 |
| `node/pvm/crates/stdlib/src/math.rs` | 补全 cos/asin/log/log2/log10/exp2/expm1/cbrt/fmod/hypot 的 softfloat 分支，log1p 用 softfloat add |
| `node/pvm/.github/workflows/softfloat-cross-platform.yml` | 矩阵增加 riscv64、wasm32，新增 bit-consistency job |

### 4.2 VRF Layer 1

| 路径 | 变更类型 |
|------|----------|
| `node/chain/Cargo.toml` | 新增 sha2, hmac, hkdf 依赖 |
| `node/chain/src/pvm_host.rs` | randomness() 改为 HKDF-SHA256，增加 HKDF 单元测试 |
| `node/chain/src/execution.rs` | 修复 filter 中 String 与 str 比较（k.as_str()） |

### 4.3 VRF Layer 2

| 路径 | 变更类型 |
|------|----------|
| `runner/Cargo.toml` | 工作区新增 curve25519-dalek, hmac |
| `runner/crates/runner-registry/Cargo.toml` | 新增 sha2, hmac, curve25519-dalek, ed25519-dalek, zeroize, serde_bytes, hex |
| `runner/crates/runner-registry/src/ecvrf.rs` | **新文件**：EC-VRF RFC 9381 实现 |
| `runner/crates/runner-registry/src/lib.rs` | 导出 ecvrf 模块及公共 API |
| `runner/crates/runner-registry/src/registry.rs` | vrf_select_runners 改为 HMAC-SHA256 选择 |
| `runner/crates/job-dispatcher/Cargo.toml` | 新增 sha2, hmac, curve25519-dalek, ed25519-dalek, hex |
| `runner/crates/job-dispatcher/src/dispatcher.rs` | generate_vrf_seed 集成 vrf_prove，dispatcher_vrf_secret_key 支持 DISPATCHER_VRF_SK_HEX |

### 4.4 VRF Layer 3

| 路径 | 变更类型 |
|------|----------|
| `runner/crates/runner-consensus/Cargo.toml` | 新增 bls12_381, sha2, serde_bytes, hex |
| `runner/crates/runner-consensus/src/threshold_bls_vrf.rs` | **新文件**：Threshold-BLS VRF 框架 |
| `runner/crates/runner-consensus/src/lib.rs` | 导出 threshold_bls_vrf 及公共 API |

---

## 五、运行测试命令

```bash
# SoftFloat
cd node/pvm && cargo test -p rustpython-vm --lib softfloat

# PVM HKDF
cd node && cargo test -p cowboy-chain --lib pvm_host

# EC-VRF
cd runner && cargo test -p runner-registry --lib ecvrf

# Threshold-BLS VRF
cd runner && cargo test -p runner-consensus --lib threshold_bls_vrf
```

---

## 六、后续建议

1. **SoftFloat：** 若需在 CI 中启用需 stdlib 的 pvm-runtime 集成测试，需先解决 `rustpython-stdlib` 中 `random.rs` 与 `mt19937`/`rand_core` 版本不兼容的预存编译错误。
2. **EC-VRF：** 生产环境通过配置或安全存储注入 `DISPATCHER_VRF_SK_HEX`；链上验证逻辑可在需要时读取 `VrfProof` 并调用 `vrf_verify(pk, alpha, proof)`。
3. **Threshold-BLS：** 生产环境将 `hash_to_g1` 换为 RFC 9380 hash-to-curve；在共识/区块头中增加 `vrf_output` 与 `vrf_proof_shares` 字段，并在执行上下文中向 pvm_host 提供 `block_vrf_output` 以完成信标集成。
