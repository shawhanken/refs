# 统一测试策略

**日期：** 2026-03-16  
**目标：** 建立完整的测试体系，支持 Devnet 按期发布  

---

## 一、测试分层

```
┌──────────────────────────────────────────────┐
│              CI 自动化（每次 PR/main 合并）      │
│  ┌────────────────────────────────────────┐  │
│  │         集成测试 / E2E 测试              │  │
│  │  ┌──────────────────────────────────┐  │  │
│  │  │         单元测试                   │  │  │
│  │  └──────────────────────────────────┘  │  │
│  └────────────────────────────────────────┘  │
│              安全回归测试（Almanax.ai）        │
│              压力/稳定性测试（定期）            │
└──────────────────────────────────────────────┘
```

---

## 二、单元测试（开发测试）

**目标：** 每个功能修改/新增对应至少一个单元测试

### 新增测试文件清单

| 类别 | 测试文件路径 | 覆盖内容 |
|------|-------------|----------|
| VRF 选择 | `execution/src/runner/vrf_tests.rs` | 种子计算、权重公式、确定性 |
| 类型兼容 | `runner-common/src/types_compat_tests.rs` | 序列化/反序列化往返 |
| 过滤条件 | `execution/src/runner/dispatcher_filter_tests.rs` | 7 个过滤条件 |
| 超时重选 | `execution/src/runner/timeout_tests.rs` | 超时检测、声誉惩罚、VRF 重选 |
| 签名验证 | `execution/src/runner/registry_sig_tests.rs` | 注册签名、篡改检测 |
| 结果签名 | `runner-common/tests/signature_tests.rs` | 签名/验证/篡改 |
| Gas 常量 | `execution/src/gas_tests.rs` | CIP-3 对照 |
| Basefee | `execution/src/fee_tests.rs` | EIP-1559 机制 |
| Entitlement | `execution/src/entitlement/constraint_tests.rs` | 有效期/次数/深度 |
| CBOR 解析 | `execution/src/runner/cbor_parse_tests.rs` | HTTP/MCP/Custom |
| 定时器 | `execution/src/tests/timer_tests.rs` | bid_fp、state_watch |
| Pool 过滤 | `execution/src/runner/dispatcher_pool_tests.rs` | runner pool |
| 密钥安全 | `cli/src/tests/key_permissions_tests.rs` | 文件权限 |
| 存储键格式 | `storage/src/key_format_tests.rs` | vm_ns 隔离 |

---

## 三、安全回归测试

**目标：** Almanax.ai 报告中每个已修复的问题对应一个不可回归的测试

### 安全测试 Tag 标记

所有安全测试使用 `#[cfg(test)]` 标注 `// SEC-{severity}-{number}`：

```rust
#[test]
// SEC-HIGH-001: 私钥文件权限
fn test_key_file_permissions_are_600() { ... }

#[test]
// SEC-MEDIUM-007: 私钥不应出现在日志中
fn test_no_private_key_in_tracing_span() { ... }
```

### 最小安全回归测试套件

```
cargo test -- --test-threads=1 \
  test_key_file_has_600_permissions \
  test_genesis_requires_explicit_config \
  test_init_cannot_be_called_twice \
  test_cors_rejects_unknown_origin \
  test_rate_limit_returns_429 \
  test_body_size_limit_rejects_large_payload \
  test_no_private_key_in_tracing_span \
  test_config_serialize_excludes_secrets
```

---

## 四、集成验收测试（上线测试）

**目标：** 面向外部的端到端验收，Devnet 发布前全部通过

### 核心流程测试

| 测试场景 | 描述 | 预期结果 |
|----------|------|----------|
| Actor 部署和调用 | 部署 Python Actor + 调用 handler | 返回正确执行结果 |
| Token 创建和转账 | 创建 Token + 跨账户转账 | 余额正确变更 |
| LLM Job 端到端 | 提交 LLM Job → Runner 执行 → 结果上链 | callback 触发 |
| HTTP Job 端到端 | 提交 HTTP Job → Runner 抓取 → 结果返回 | 数据提取正确 |
| 定时器触发 | schedule_timer → 等待块高 → 触发 | 指定区块触发 |
| Faucet 水龙头 | 请求 Faucet → 检查余额 | 余额增加 |
| Wallet 交互 | 钱包签名交易 → 提交到链 | 交易确认 |
| Explorer 查询 | 区块/交易/账户查询 | 返回正确数据 |

### 压力/稳定性测试

| 测试场景 | 持续时间 | 通过标准 |
|----------|----------|----------|
| 内存稳定性 | 24 小时 | RSS 增长 < 10% |
| 产块稳定性 | 1000 块 | 平均间隔 950-1050ms |
| 并发交易 | 100 TPS × 10 分钟 | 无 crash、无丢块 |

---

## 五、CI 集成方案

### 触发条件

| 事件 | 触发的测试 |
|------|-----------|
| PR 提交 | 单元测试 + cargo clippy + fmt |
| PR 合并到 main | 单元测试 + 集成测试 + 安全回归 |
| 每日定时 (nightly) | 全量测试 + 压力测试 |
| Release tag | 全量测试 + E2E 验收 |

### GitHub Actions 配置

```yaml
name: CI
on:
  pull_request:
    branches: [main, devnet]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Unit Tests
        run: cargo test --workspace
      - name: Clippy
        run: cargo clippy --workspace -- -D warnings
      - name: Format
        run: cargo fmt --all -- --check

  integration:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Validator
        run: cargo build --release -p validator
      - name: Integration Tests
        run: cargo test --test integration -- --test-threads=1
      - name: Security Regression
        run: cargo test -- --test-threads=1 $(grep -r "SEC-" tests/ | ...)
```

与 Martin Aceto 对接后集成到 cowboyinc GitHub CI pipeline。

---

## 六、测试优先级排序

### Devnet 4/15 前必须完成

1. **安全回归测试**：4 个 HIGH + 23 个 MEDIUM 问题的测试
2. **类型兼容测试**：Node ↔ Runner 序列化往返
3. **VRF 选择测试**：确定性 + 权重
4. **签名链路测试**：注册签名 + 结果签名
5. **Gas 常量对照测试**：CIP-3/20 参数验证
6. **端到端流程测试**：Actor/Token/Job 三个核心流程

### Devnet 后补全

7. Entitlement 约束测试
8. Basefee 调节测试
9. 定时器三层队列测试
10. P2P/Aggregation 测试
