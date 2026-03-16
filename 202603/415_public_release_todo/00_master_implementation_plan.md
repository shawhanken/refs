# Cowboy Devnet 全面实施计划

**日期：** 2026-03-16  
**目标上线日期：** 2026-04-15  
**文档来源：**
1. 2026-03-16 项目会议纪要  
2. Almanax.ai 安全扫描报告（cowboyinc/node, commit 395150f8）  
3. Node/Runner 代码与规格文档差距分析报告  

**关联仓库：** `cowboyinc/node`、`cowboyinc/runner`  
**关联规格：** CIP-1 至 CIP-20、白皮书 20260216  

---

## 一、总体目标

在 2026-04-15 前完成 Devnet Release，确保：
1. **安全性**：Almanax.ai 报告中的 4 个 HIGH 和 23 个 MEDIUM 级安全问题全部修复（报告正文实际 52 项，Summary 表格误报为 47 项）
2. **规格一致性**：Node/Runner 代码与 CIP 规格文档的 20 项差距全部修复或有明确计划
3. **稳定性**：内存泄漏修复验证、产块时间稳定性确认
4. **可测试性**：完整的测试用例体系（开发测试 + 上线安全测试 + CI 集成）
5. **新功能**：Multisig 支持评估、Runner 文件写入能力

---

## 二、实施项目汇总

### Phase 1：紧急安全修复（第1周：3/17 - 3/23）

#### P1-1. 私钥文件权限修复 🔴 HIGH

**来源：** Almanax.ai 报告 — `cli/src/commands.rs`

**问题描述：** CLI 使用 `fs::write` 写入私钥文件，默认权限可能为 0644，其他用户可读取。

**技术解决方案：**
```rust
// cli/src/commands.rs — 所有 fs::write(&key_path, &pem) 替换为：
use std::os::unix::fs::OpenOptionsExt;
let file = std::fs::OpenOptions::new()
    .create_new(true)
    .write(true)
    .mode(0o600)
    .open(&key_path)?;
std::io::Write::write_all(&mut file, pem.as_bytes())?;
```

**涉及位置：** `wallet create`、`wallet upgrade`、`init`、`mnemonic` 四个命令的私钥写入。

**测试验收方案：**

*单元测试（`cli/src/tests/key_permissions_tests.rs`）：*
```rust
#[test]
fn test_key_file_has_600_permissions() {
    let dir = tempdir().unwrap();
    let key_path = dir.path().join("test_key.pem");
    write_key_file_secure(&key_path, &test_key_bytes()).unwrap();
    let metadata = std::fs::metadata(&key_path).unwrap();
    let mode = metadata.permissions().mode() & 0o777;
    assert_eq!(mode, 0o600, "私钥文件权限必须为 0600");
}
```

*集成验收标准：*
- [ ] `cowboy wallet create` 创建的密钥文件权限为 `0600`
- [ ] `cowboy wallet upgrade` 升级后的密钥文件权限为 `0600`
- [ ] 非所有者用户无法读取私钥文件

---

#### P1-2. Genesis 默认管理员密钥安全 🔴 HIGH

**来源：** Almanax.ai 报告 — `chain/src/genesis.rs`

**问题描述：** `GenesisConfig::default()` 使用 `address_from_seed(0)` 生成管理员账户，私钥可被任何人推导。

**技术解决方案：**
```rust
// chain/src/genesis.rs
impl GenesisConfig {
    pub fn default() -> Self {
        // 非测试环境禁止使用 seed-based 密钥
        #[cfg(not(test))]
        panic!("GenesisConfig::default() is not allowed in non-test builds. \
                Please provide an explicit genesis config file.");
        
        #[cfg(test)]
        Self::test_default()
    }
}

// 启动时强制要求 genesis_config_path
fn load_genesis(path: Option<&str>) -> Result<GenesisConfig, Error> {
    match path {
        Some(p) => GenesisConfig::from_file(p),
        None => Err(Error::GenesisConfigRequired),
    }
}
```

**测试验收方案：**

*单元测试：*
```rust
#[test]
fn test_genesis_default_panics_in_non_test_mode() {
    // 在非 #[cfg(test)] 编译条件下 GenesisConfig::default() 应 panic
    // 此测试在 test 模式下验证 test_default 仍可用
    let config = GenesisConfig::test_default();
    assert!(!config.accounts.is_empty());
}

#[test]
fn test_genesis_requires_explicit_public_key() {
    // genesis config 中的 accounts 应使用 public_key_hex 而非 seed
    let config = load_genesis_from_str(r#"
        accounts:
          - public_key_hex: "0x1234..."
            balance: 1000000
    "#).unwrap();
    assert!(config.accounts[0].seed.is_none());
}
```

*集成验收标准：*
- [ ] 不提供 genesis 配置文件时节点启动失败并给出明确错误
- [ ] genesis 配置文件中支持 `public_key_hex` 方式指定地址
- [ ] 测试环境仍可使用 `test_default()` 快速启动

---

#### P1-3. Watchtower Registry Init() 可重入漏洞 🔴 HIGH

**来源：** Almanax.ai 报告 — `cli/actors/watchtower_registry.py`

**问题描述：** `init()` 可被任何人调用并重置注册表，覆盖 owner 和清空 feeds 列表。

**技术解决方案：**
```python
# cli/actors/watchtower_registry.py
def init(payload):
    pvm_host.charge_gas(2000)
    ctx = pvm_host.context()
    
    # 检查是否已初始化
    existing_owner = _get_str(b"owner")
    if existing_owner and len(existing_owner) > 0:
        return b"error: already initialized"
    
    owner = _sender_hex(ctx)
    _set_str(b"owner", owner)
    _set_json(b"feeds", [])
    pvm_host.emit_event("registry.init", ("owner=" + owner).encode())
    return b"ok: registry initialized"
```

**测试验收方案：**

*单元测试：*
```python
def test_init_cannot_be_called_twice():
    # 第一次 init 成功
    result1 = call_handler("init", b"")
    assert result1 == b"ok: registry initialized"
    
    # 第二次 init 被拒绝
    result2 = call_handler("init", b"")
    assert result2 == b"error: already initialized"

def test_init_preserves_existing_feeds():
    call_handler("init", b"")
    call_handler("register_feed", feed_payload)
    
    # 恶意尝试重新初始化
    result = call_handler("init", b"")
    assert result == b"error: already initialized"
    
    feeds = json.loads(call_handler("get_feeds", b""))
    assert len(feeds) == 1  # feeds 未被清空
```

*集成验收标准：*
- [ ] 已初始化的 Registry 执行 init 返回错误，不覆盖现有数据
- [ ] feeds 列表在 init 重入攻击后完好无损

---

#### P1-4. CLI Bootstrap 二进制下载校验 🔴 HIGH

**来源：** Almanax.ai 报告 — `cli-bootstrap.sh`

**问题描述：** 通过 curl 下载的二进制文件未经签名或哈希校验即安装到系统。

**技术解决方案：**
```bash
# cli-bootstrap.sh
# 下载二进制及对应的 SHA-256 校验文件
curl -fsSL -o "$TMPFILE" "$URL"
curl -fsSL -o "${TMPFILE}.sha256" "${URL}.sha256"

# 校验文件完整性
EXPECTED_HASH=$(cat "${TMPFILE}.sha256" | awk '{print $1}')
ACTUAL_HASH=$(sha256sum "$TMPFILE" | awk '{print $1}')

if [ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]; then
    echo "ERROR: 文件校验失败。下载可能已被篡改。"
    echo "  期望: $EXPECTED_HASH"
    echo "  实际: $ACTUAL_HASH"
    rm -f "$TMPFILE" "${TMPFILE}.sha256"
    exit 1
fi

# API key 用 Header 传递，不暴露在 URL 中
curl -fsSL -H "Authorization: Bearer ${KEY}" -o "$TMPFILE" "$URL"
```

**测试验收方案：**

*集成验收标准：*
- [ ] 下载后校验 SHA-256 哈希，不匹配时中止安装
- [ ] API key 通过 `Authorization` Header 传递，不出现在 URL 中
- [ ] 哈希校验文件从可信渠道获取

---

### Phase 2：安全加固与稳定性修复（第2周：3/24 - 3/30）

#### P2-1. CORS 策略收紧 🟠 MEDIUM

**来源：** Almanax.ai — `indexer/src/lib.rs`

**问题描述：** Indexer 使用 `CorsLayer::very_permissive()` / `CorsLayer::permissive()`，允许任意来源跨域访问。

**技术解决方案：**
```rust
// indexer/src/lib.rs
use tower_http::cors::{CorsLayer, AllowOrigin};

let allowed_origins = std::env::var("CORS_ALLOWED_ORIGINS")
    .unwrap_or_else(|_| "http://localhost:3000".to_string());

let origins: Vec<HeaderValue> = allowed_origins
    .split(',')
    .filter_map(|o| o.trim().parse().ok())
    .collect();

let cors = CorsLayer::new()
    .allow_origin(AllowOrigin::list(origins))
    .allow_methods([Method::GET, Method::POST])
    .allow_headers(Any);
```

**测试验收方案：**

*单元测试：*
```rust
#[tokio::test]
async fn test_cors_rejects_unknown_origin() {
    let app = make_app_with_cors("https://explorer.cowboy.inc");
    let resp = app.oneshot(Request::builder()
        .header("Origin", "https://malicious.site")
        .uri("/health")
        .body(Body::empty()).unwrap()).await.unwrap();
    // 应无 Access-Control-Allow-Origin 回复或被拒绝
    assert!(resp.headers().get("access-control-allow-origin").is_none());
}
```

*集成验收标准：*
- [ ] 非白名单来源的跨域请求被拒绝
- [ ] WebSocket 端点验证 Origin header
- [ ] 通过 `CORS_ALLOWED_ORIGINS` 环境变量可配置

---

#### P2-2. API 端点速率限制 🟠 MEDIUM

**来源：** Almanax.ai — `chain/src/application.rs`

**问题描述：** 所有 RPC/HTTP 端点无速率限制，可被 DoS 攻击。包括 Faucet 端点缺少单独限制。

**技术解决方案：**
```rust
// chain/src/application.rs
use tower::limit::RateLimitLayer;
use std::time::Duration;

// 全局速率限制
let rate_limit = RateLimitLayer::new(100, Duration::from_secs(1)); // 100 req/s

// Faucet 单独限制
let faucet_limit = RateLimitLayer::new(5, Duration::from_secs(60)); // 5 req/min

let app = Router::new()
    .route("/submit", post(submit))
    .route("/query/{address}", get(query))
    .route("/faucet", post(faucet).layer(faucet_limit))
    .layer(rate_limit);
```

**测试验收方案：**

*集成验收标准：*
- [ ] 超过全局速率限制后返回 HTTP 429
- [ ] Faucet 端点每分钟超过 5 次请求后返回 429
- [ ] 单次 Faucet 请求有最大金额限制

---

#### P2-3. 请求体大小限制 🟠 MEDIUM

**来源：** Almanax.ai — `/submit` 端点

**问题描述：** `/submit` 无请求体大小限制，可被大 payload 攻击导致 OOM。

**技术解决方案：**
```rust
use axum::extract::DefaultBodyLimit;

let app = Router::new()
    .route("/submit", post(submit))
    // ...
    .layer(DefaultBodyLimit::max(1_048_576)) // 1 MB
```

**测试验收方案：**
- [ ] 超过 1MB 的请求体返回 HTTP 413 Payload Too Large
- [ ] 正常交易请求不受影响

---

#### P2-4. 查询端点分页与范围限制 🟠 MEDIUM

**来源：** Almanax.ai — Indexer 多个端点

**问题描述：** `/blocks/{start}/{end}`、`/transactions`、`/transactions/{query}` 等端点接受无上限的范围查询。

**技术解决方案：**
```rust
const MAX_PAGE_SIZE: u64 = 100;

pub async fn get_blocks(
    State(state): State<Arc<IndexerState>>,
    Path((start, end)): Path<(u64, u64)>,
) -> impl IntoResponse {
    let clamped_end = end.min(start.saturating_add(MAX_PAGE_SIZE));
    let blocks = state.db.get_blocks(start, clamped_end);
    Json(BlocksResponse {
        blocks,
        has_more: end > clamped_end,
        next_start: if end > clamped_end { Some(clamped_end) } else { None },
    })
}
```

**测试验收方案：**
- [ ] 请求 `blocks/0/999999` 最多返回 100 个块，并带 `has_more` 分页标记
- [ ] `transactions` 的 `limit` 参数被服务端限制在 ≤1000
- [ ] 返回体中有 `next_start`/`next_cursor` 支持分页

---

#### P2-5. 私钥从日志/Span/Serialize 中移除 🟠 MEDIUM

**来源：** Almanax.ai — `chain/src/application.rs` + `chain/src/lib.rs`

**问题描述：** 
- `run()` 的 tracing span 中包含 `private_key`
- `Config` 结构体 derive `Serialize`，私钥可被序列化

**技术解决方案：**
```rust
// application.rs — 移除私钥，仅用公钥标识
let span = info_span!("node",
    public_key = %config.public_key(), // 改为公钥
    // private_key 完全删除
);

// lib.rs — Config 中敏感字段跳过序列化
#[derive(Deserialize, Serialize)]
pub struct Config {
    #[serde(skip_serializing)]
    pub private_key: String,
    #[serde(skip_serializing)]
    pub share: String,
    #[serde(skip_serializing)]
    pub polynomial: String,
    // ...公开字段保留 Serialize
}
```

**测试验收方案：**
- [ ] 节点启动日志中无 `private_key`、`share`、`polynomial` 明文
- [ ] `serde_json::to_string(&config)` 的输出不包含私钥字段
- [ ] 日志中仅显示公钥或地址用于运维标识

---

#### P2-6. Unbounded Channel 改为 Bounded 🟠 MEDIUM

**来源：** Almanax.ai — `client/src/consensus.rs` + `client/src/events.rs`

**问题描述：** WebSocket 消息通过 unbounded channel 转发，恶意服务端可导致无限内存增长。

**技术解决方案：**
```rust
// 改用 bounded channel
let (tx, rx) = tokio::sync::mpsc::channel(1024); // 缓冲 1024 条

// Stream 的 Drop 实现
impl<T> Drop for Stream<T> {
    fn drop(&mut self) {
        self._handle.abort();
    }
}
```

**测试验收方案：**
- [ ] Channel 满时，背压机制生效（丢弃或不再读取新消息）
- [ ] Stream drop 后 WebSocket 背景任务被中止

---

#### P2-7. 内存泄漏稳定性验证

**来源：** 会议纪要 — 客户方反馈 Node 运行一段时间后内存持续上涨（Tony 转述）

**问题描述：** 客户方反馈（基于 2月下旬代码版本）运行多个 Runner 和 Timer 后 Node OOM。说话人3确认3月初已修复过内存问题，需验证当前版本是否仍有问题。

**技术解决方案：**
1. 使用当前最新 devnet 代码部署单节点
2. 启动 5+ Runner，注册 50+ 定时器
3. 运行 24 小时，监控 RSS 内存变化
4. 使用 `heaptrack` 或 `valgrind --tool=massif` 分析内存分配

**测试验收方案：**
- [ ] 24小时运行后 RSS 内存增长 < 10%（相对初始值）
- [ ] 无明显的单调递增内存趋势
- [ ] Heaptrack 报告无持续增长的分配点

---

#### P2-8. 产块时间稳定性

**来源：** 会议纪要 — 客户反馈产块时间不稳定（1秒1块 vs 1秒2块）

**问题描述：** Commonware 框架本身无法精确控制产块时间，当前通过判断时间间隔来仿真 1 秒产块。

**技术解决方案：**
1. **短期**：确认当前的时间间隔判断逻辑是否准确，优化精度
2. **中期**：升级 Commonware 版本，检查是否有新的时间控制 API
3. **文档化**：在 Devnet 文档中明确说明产块时间的精度范围（±50ms）

**测试验收方案：**
- [ ] 连续运行 1000 个区块，平均产块间隔在 950ms-1050ms
- [ ] 最大单块偏差不超过 ±200ms
- [ ] 不出现连续两个块间隔 < 500ms 的情况

---

### Phase 3：规格一致性修复 — 核心（第3周：3/31 - 4/6）

#### P3-1. Node/Runner 数据类型统一 ⚠️ 严重

**来源：** Gap Analysis 问题二

**问题描述：** 两个代码库之间存在大量类型分歧（`stake` u64 vs U256、`CallbackInfo` 字段不同、`VerificationConfig` 结构不同等），导致互操作性问题。

**技术解决方案：**

新建 `cowboy-runner-types` crate 作为单一真相来源（Single Source of Truth），同时被 node 和 runner 两个工作区依赖。

详见 `02_spec_alignment_fixes.md` — 问题二。

**测试验收方案：**
- [ ] Node 序列化的所有 `JobSpec` / `RunnerResult` / `VerificationConfig` JSON 均可被 Runner 反序列化，无字段丢失
- [ ] Runner 序列化的 `RunnerRegistration` 均可被 Node RPC 层正确解析
- [ ] 新建 `cowboy-runner-types` 后，两侧编译均无类型警告
- [ ] 现有集成测试全部通过

---

#### P3-2. VRF 选择算法修正 ⚠️ 严重

**来源：** Gap Analysis 问题一

**问题描述：** Node 直接取 `job_id[0..8]` 作为 seed 用取模轮转选择，无 VRF、无 block_hash、无质押权重；与 CIP-2 规格完全不符。

**技术解决方案：**

替换为 `Keccak256(block_hash || "cowboy-runner-select-v2:" || job_id || submitted_at_le8)` 种子 + Fisher-Yates + `stake_to_weight(s) = floor(log2(s/MIN_STAKE + 1)) + 1` 权重。

详见 `02_spec_alignment_fixes.md` — 问题一。

**测试验收方案：**
- [ ] 给定固定 block_hash、job_id、submitted_at，选择结果与 CIP-2 公式手算一致
- [ ] 两个相同配置的节点对同一 Job 的 Runner 选择结果完全一致
- [ ] 高质押（100x MIN_STAKE）Runner 的长期入选频率高于低质押 Runner

---

#### P3-3. Runner 结果签名实现 ⚠️ 严重

**来源：** Gap Analysis 问题十三

**问题描述：** 所有 Runner Executor（HTTP/LLM/MCP）返回 `Signature::zero()` 占位符，Node 验证器未验证签名。

**技术解决方案：**

在 `runner-node/src/executor.rs` 的提交流程中统一签名，Node 验证器添加 `ecrecover` 验证。

详见 `02_spec_alignment_fixes.md` — 问题十三。

**测试验收方案：**
- [ ] Runner 提交结果时 `signature` 字段非全零
- [ ] Node 链上 Verifier 对每个提交的结果执行 `ecrecover` 验证，不匹配则拒绝
- [ ] 端到端：LLM Job 完整流程通过

---

#### P3-4. Runner 候选过滤条件补全

**来源：** Gap Analysis 问题三

**问题描述：** CIP-2 要求 7 个过滤条件，Node 只实现了 Health 过滤。

**技术解决方案：**

补充 Reputation≥50、Capability 匹配、TEE、Price、Concurrency、Entitlement 六个过滤条件。

详见 `02_spec_alignment_fixes.md` — 问题三。

**测试验收方案：**
- [ ] 所有 7 个过滤条件各有至少 1 个失败情形的测试用例覆盖

---

#### P3-5. Runner 注册签名验证

**来源：** Gap Analysis 问题十一

**问题描述：** 注册请求无签名验证（两处均有 TODO 注释）。

**技术解决方案：**

实现 ecrecover 注册验证逻辑。

**测试验收方案：**
- [ ] 使用错误私钥签名的注册请求被节点拒绝
- [ ] Runner node 启动时产生的注册交易签名可通过链上验证

---

#### P3-6. 最低质押量统一

**来源：** Gap Analysis 问题十二

**问题描述：** Runner Node 50,000 CBY vs Runner Registry 10,000 CBY。

**技术解决方案：** 提取为共享常量 `MIN_STAKE_CBY_WEI = 10,000 * 10^18`。

**测试验收方案：**
- [ ] Node 端和 Runner 端 `MIN_STAKE_CBY_WEI` 值完全一致
- [ ] 低于最低质押的注册请求在 node 和 runner 两侧均被拒绝

---

#### P3-7. Gas 成本数值修正

**来源：** Gap Analysis 问题七

**问题描述：** 多项 Gas 常量与 CIP-3/CIP-20 规格不符（`token_hook_max_cycles` 500k→50k，`storage_write_cycles` 10k→50 等）。

**技术解决方案：** 修正 gas.rs 常量，`token_create` Cells 改为动态计算。

**测试验收方案：**
- [ ] 所有 Gas 常量与 CIP-3/CIP-20 表格逐项对照无差异

---

#### P3-8. JobSpec 缺少 `required_runner_pool` 字段

**来源：** Gap Analysis 问题九

**技术解决方案：** Node 和 Runner 的 `JobSpec` 各添加 `required_runner_pool: Option<Vec<u8>>`。

**测试验收方案：**
- [ ] 含 `required_runner_pool` 的 Job 只分配给拥有对应 pool Entitlement 的 Runner

---

#### P3-9. CBOR 格式 JobSpec 补全 HTTP/MCP/Custom

**来源：** Gap Analysis 问题十五

**技术解决方案：** 在 `parse_job_spec` 的 CBOR 分支中补充 `"http"`、`"mcp"`、`"custom"` 解析。

**测试验收方案：**
- [ ] 四种 job type 的 CBOR 数据均可被 node 正确解析

---

### Phase 4：功能完善与高级特性（第4周：4/7 - 4/13）

#### P4-1. 超时重选机制

**来源：** Gap Analysis 问题四

**技术解决方案：** End-of-Block 超时检查 + 声誉惩罚 + VRF 重选逻辑 + 实现 `RunnerDeregister` 和 `JobCancel` 指令。

**测试验收方案：**
- [ ] Job 超时后 Runner 声誉 -5
- [ ] 第 4 次超时后 Job 状态变为 `Failed`
- [ ] `RunnerDeregister` 和 `JobCancel` 指令可正常执行

---

#### P4-2. Commit-Reveal 聚合协议（阶段一）

**来源：** Gap Analysis 问题五

**技术解决方案：** 先实现多结果直接链上提交投票；完整 Commit-Reveal 后续迭代。

**测试验收方案：**
- [ ] N 个 Runner 各自独立提交结果后，threshold 达到时触发 callback
- [ ] 链上 Verifier 能区分一致结果与异常结果

---

#### P4-3. Entitlement 约束检查完善

**来源：** Gap Analysis 问题十四

**技术解决方案：** 补全 grant.rs 中的约束检查（有效期、使用次数、委托深度）+ Actor 调用前置拦截。

**测试验收方案：**
- [ ] `valid_until` 到期后拒绝所有操作
- [ ] `max_uses` 耗尽后拒绝继续使用
- [ ] 委托深度超限被拒绝

---

#### P4-4. EIP-1559 Basefee 动态调节

**来源：** Gap Analysis 问题八

**技术解决方案：** 新增 `FeeState` + `finalize_block` 末尾更新 + 交易验证拦截。

**测试验收方案：**
- [ ] 连续满载区块 basefee 每块涨幅 12.5%
- [ ] `max_fee_per_cycle < basefee_cycle` 的交易被拒绝

---

#### P4-5. Multisig 支持评估

**来源：** 会议纪要 — Tony 提出参考 [Safe](https://safe.global/) 实现多签

**技术解决方案：**
1. 调研 Safe 合约架构（Threshold Signature、Transaction Queue、Confirmation 机制）
2. 评估在 Cowboy PVM 上实现 Multisig Actor 的可行性
3. 设计方案文档（独立 CIP 或 Actor 模板）

**交付物：** Multisig 技术评估文档
**测试验收方案：** 评估文档完成后由 Tony 和团队审核

---

#### P4-6. Runner 文件写入能力

**来源：** 会议纪要 — Charles DePue 提出 Runner 需要写文件能力

**问题描述：** Runner 在 session 维度需要有本地文件写入能力，每个 session 有独立目录。

**技术解决方案：**
```rust
// runner-node/src/session.rs
pub struct SessionFileManager {
    base_dir: PathBuf,
    session_id: String,
}

impl SessionFileManager {
    pub fn new(base_dir: &Path, session_id: &str) -> Self {
        let session_dir = base_dir.join("sessions").join(session_id);
        std::fs::create_dir_all(&session_dir).expect("创建 session 目录");
        Self { base_dir: session_dir, session_id: session_id.into() }
    }
    
    pub fn write_file(&self, name: &str, data: &[u8]) -> Result<PathBuf> {
        // 安全检查：名称不含 ../ 等路径穿越
        Self::validate_filename(name)?;
        let path = self.base_dir.join(name);
        std::fs::write(&path, data)?;
        Ok(path)
    }
    
    pub fn read_file(&self, name: &str) -> Result<Vec<u8>> {
        Self::validate_filename(name)?;
        Ok(std::fs::read(self.base_dir.join(name))?)
    }
}
```

**注：** Charles DePue 将提交 Demo 实现，待其提交后对照实现。

**测试验收方案：**
- [ ] Session 隔离：不同 session 的文件目录相互独立
- [ ] 路径穿越防护：`../` 等路径注入被拒绝
- [ ] Session 结束后文件可被清理

---

#### P4-7. Runner 注册与心跳上链

**来源：** 会议纪要 — 当前 Runner 注册和心跳均为手动操作

**问题描述：** Runner 注册需通过命令行在链端手工操作，不可通过标准交易流程完成。心跳虽有实现但为手工触发。

**技术解决方案：**
1. Runner 启动时自动构造注册交易并签名提交到链上
2. 心跳改为定时任务（如每 60 个区块一次），自动提交心跳交易
3. Node 侧实现 `RunnerHeartbeat` 系统指令处理（更新 Runner 的 last_heartbeat_block）

**测试验收方案：**
- [ ] Runner 启动后自动注册，无需手动干预
- [ ] 心跳交易每 60 个区块自动提交
- [ ] 超过 3 个心跳周期无心跳的 Runner 被标记为 Unhealthy

---

### Phase 5：Devnet 上线前 — 低优先级与待评估项目

以下项目根据时间和资源情况评估是否在 4/15 前完成：

| 编号 | 问题 | 来源 | 建议 |
|------|------|------|------|
| P5-1 | CIP-5 定时器三层队列 + GBA | Gap #6 | **4/15 后**：当前 height-triggered 可满足 devnet |
| P5-2 | Secrets Manager 实现 | Gap #10 | **4/15 后**：先用文档标注为"规划中" |
| P5-3 | TEE Verifier 实现 | Gap #10 | **4/15 后**：依赖硬件环境 |
| P5-4 | Runner P2P 共识 | Gap #16 | **4/15 后**：短期用链上协调替代 |
| P5-5 | CIP-1 Actor 调度器 | Gap #19 | **4/15 后**：复杂度高 |
| P5-6 | CIP-4 双 VM 命名空间 | Gap #20 | **需调查**：检查现有实现是否已覆盖 |
| P5-7 | LLM Anthropic/本地模型 | Gap #17 | **酌情**：OpenAI 足够 devnet 使用 |
| P5-8 | HTTP XPath/JSONPath | Gap #18 | **酌情**：CSS Selector 已覆盖主要场景 |

---

### Almanax.ai 其余安全问题修复

以下为 Almanax.ai 报告中 LOW/INFO 级别的问题（共 24 LOW + 1 INFO），按优先级排列：

| 级别 | 问题 | 文件 | 状态 |
|------|------|------|------|
| LOW | 日志记录完整交易内容（磁盘填满） | indexer/submit | 待修复 |
| LOW | Genesis leader key 硬编码 | chain/application | 待修复 |
| LOW | Feed subscriber 消息无大小限制 | cli/actors | 待修复 |
| LOW | Actor 名称未过滤 Windows 路径 | cli/commands | 待修复 |
| LOW | TLS 设置使用 expect 导致 crash | client/lib | 待修复 |
| LOW | HTTP 客户端无超时设置 | client/lib | 待修复 |
| LOW | URI scheme 不支持时 panic | client/lib | 待修复 |
| LOW | cd 失败后仍执行 cargo | diagnose_runner.sh | 待修复 |
| LOW | 符号链接可导致文件删除 | restart_validator.sh | 待修复 |
| LOW | PID grep kill 可误杀 | restart_validator.sh | 待修复 |
| LOW | 16-bit checksum 可碰撞 | cli/key_format | 文档注明 |
| LOW | PEM body 解析无大小限制 | cli/key_format | 待修复 |
| LOW | pkill 匹配过宽 | start_validator.sh | 待修复 |
| LOW | Faucet 默认开启 | start_validator.sh | 待修复 |
| LOW | Inspector single-shot GET panic | inspector/main | 待修复 |
| LOW | Inspector stream 崩溃重连 | inspector/main | 待修复 |
| LOW | WASM participants 值过大 panic | types/wasm | 待修复 |
| LOW | WASM identity 无效输入 panic | types/wasm | 待修复 |
| LOW | Entitlement Vec 无边界编码 | types/entitlement | 待修复 |
| LOW | URL path injection | client/rpc | 待修复 |
| LOW | Genesis balance 溢出 | chain/genesis | 待修复 |
| LOW | 未转义 BASE_URL | indexer/test | 待修复 |
| LOW | rm -rf 相对路径风险 | run_build.sh | 待修复 |
| LOW | PVM 错误信息泄漏 | chain/error | 待修复 |
| INFO | tail 固定路径符号链接 | diagnose_runner.sh | 文档注明 |

> [!NOTE]
> 原始报告 Summary 表格声称 47 项（17M/25L），但正文实际有 52 项（23M/24L）。Unbounded hex decode、Indexer 0.0.0.0 绑定、Config path traversal、Unbounded feed 注册、Unbounded response body、Unbounded queue + detached task 共 6 项在正文中标注为 MEDIUM，已归入 `01_security_fixes.md` 的 M-13 至 M-23。

---

## 三、测试策略概览

详见 `04_test_strategy.md`，核心分为：

1. **开发测试（Feature Tests）**：每个新功能/修复对应的单元测试
2. **安全测试（Security Tests）**：针对 Almanax.ai 报告中各项问题的回归测试
3. **上线测试（Release Tests）**：面向外部的验收测试套件
4. **CI 集成**：所有测试接入 GitHub Actions，每次 PR 合并到 main 时自动运行

---

## 四、里程碑日程

详见 `05_milestone_schedule.md`

| 周次 | 日期范围 | 重点工作 | 交付物 |
|------|----------|----------|--------|
| W1 | 3/17-3/23 | 4 个 HIGH 安全修复 + 内存稳定性验证 | PR 提交 + 安全修复确认 |
| W2 | 3/24-3/30 | MEDIUM 安全加固 + 产块稳定性 | API 安全加固完成 |
| W3 | 3/31-4/6 | 核心规格修复（类型统一、VRF、签名） | 共享类型 crate + VRF 实现 |
| W4 | 4/7-4/13 | 功能完善 + 集成测试套件 + 新功能 | 完整测试覆盖 |
| — | 4/14 | 预发布验证 + 冻结代码 | Release Candidate |
| — | **4/15** | **Devnet Release** | 对外发布 |

---

## 五、明确的支持范围声明

**Devnet 支持的功能：**
- 单节点 Validator 运行
- Python Actor 部署和执行（PVM）
- Runner Job 提交和执行（LLM/HTTP/MCP）
- Token 创建和转账
- 定时器（HEIGHT 模式）
- 浏览器和钱包连接
- Faucet 水龙头

**Devnet 不支持/待实现的功能：**
- 多节点 Validator 共识（POS 权重）
- 完整 Commit-Reveal 聚合
- TEE 可信执行环境
- Secrets Manager 密钥管理
- STATE_WATCH 定时器
- GBA Gas 竞价代理
- P2P Runner 通信
- EVM Actor 支持

> **说明：** 以上"不支持"项需在 Devnet 文档中明确标注，避免客户产生错误预期。

