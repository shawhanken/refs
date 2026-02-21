# 2026-02-21 实施清单 (Implementation Manifest)

本会话完成的 SoftFloat + VRF 实施，详细报告见：

- **中文**: [20260221_SoftFloat_VRF_Implementation_Report_CN.md](./20260221_SoftFloat_VRF_Implementation_Report_CN.md)
- **English**: [20260221_SoftFloat_VRF_Implementation_Report_EN.md](./20260221_SoftFloat_VRF_Implementation_Report_EN.md)

---

## 测试结果 (Test Results)

| 模块 Module | 通过 Passed | 失败 Failed |
|-------------|-------------|-------------|
| rustpython-vm::softfloat | 56 | 0 |
| cowboy-chain::pvm_host | 11 | 0 |
| runner-registry::ecvrf | 11 | 0 |
| runner-consensus::threshold_bls_vrf | 11 | 0 |
| **合计 Total** | **89** | **0** |

---

## 变更文件列表 (Changed Files)

### SoftFloat
- `node/pvm/crates/vm/src/softfloat.rs`
- `node/pvm/crates/stdlib/src/math.rs`
- `node/pvm/.github/workflows/softfloat-cross-platform.yml`

### VRF Layer 1 (HKDF)
- `node/chain/Cargo.toml`
- `node/chain/src/pvm_host.rs`
- `node/chain/src/execution.rs`

### VRF Layer 2 (EC-VRF)
- `runner/Cargo.toml`
- `runner/crates/runner-registry/Cargo.toml`
- `runner/crates/runner-registry/src/ecvrf.rs` **(NEW)**
- `runner/crates/runner-registry/src/lib.rs`
- `runner/crates/runner-registry/src/registry.rs`
- `runner/crates/job-dispatcher/Cargo.toml`
- `runner/crates/job-dispatcher/src/dispatcher.rs`

### VRF Layer 3 (Threshold-BLS)
- `runner/crates/runner-consensus/Cargo.toml`
- `runner/crates/runner-consensus/src/threshold_bls_vrf.rs` **(NEW)**
- `runner/crates/runner-consensus/src/lib.rs`

---

路径均相对于仓库根目录。Paths are relative to repo root.
