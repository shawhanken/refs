# GitHub Issues 分类与批量实施计划

> 创建日期：2026-03-21
> 仓库：`cowboyinc/node`（涉及 node / runner / steamtrain）
> 总计：95 个未关闭 Issue → 24 个批次 → 约 24 个 PR

---

## 执行模式（参考 1-A 建立）

每批流程：
1. 实施（subagent implementer）
2. Spec compliance review（subagent）
3. Code quality review（subagent code-reviewer）
4. 修复 review 发现的问题
5. 三个集成测试（`examples/token`, `examples/multi_call`, `examples/llm_chat` 各跑 `--test`）
6. 等待人工确认后进入下一批

---

## 一、安全审计 Issue（共 29 个）

### 1-A：Inspector 恐慌修复（#256, #257, #259）✅ 已完成
**文件：`/node/inspector/src/main.rs`**
- 所有 `.expect()` 替换为 `anyhow::Context` + `?`
- `main()` 返回 `Result<(), anyhow::Error>`
- 6 处 clap `.unwrap()` 加 `// SAFETY:` 注释
- 移除未使用的 `thiserror` 依赖

---

### 1-B：RPC CORS 配置修复（#232, #233）
**文件：`/node/rpc/src/rpc.rs:187`**
- 现状：`CorsLayer::permissive()` — 允许任意来源
- 目标：迁移为 `CORS_ALLOWED_ORIGINS` 环境变量白名单
- 参考：`/node/indexer/src/lib.rs:574-577` 已有相同模式

---

### 1-C：Shell 脚本安全加固（#251, #255, #261, #262, #263, #265）
**文件：`/node/scripts/` 目录**
- #263: `rm -rf test/*.db` 相对路径 → 绝对路径
- #255: `pkill -f "validator.*--config"` 过宽 → PID 文件或精确模式
- #251: grep+awk 提取 PID → `pgrep -x` 或 PID 文件
- #262: curl `$RPC_URL` 注入风险 → 验证 scheme（必须 http/https）
- #261: JSON 模板变量未充分转义 → 使用 `jq` 或 printf 转义
- #265: `tail -50` 可能追踪符号链接 → 增加 readlink 检测

---

### 1-D：日志/信息泄露（#238, #246, #264）
**文件：多处**
- #238: 私钥出现在日志 → `PrivateKey` 的 Debug/Display 显示 `[REDACTED]`
- #264: `rpc/src/error.rs` 的 `raw_error` 字段暴露给客户端 → non-dev 模式下删除
- #246: 大型 payload 全量记录 → 超过 512 bytes 只打印长度

---

### 1-E：加密/认证弱点（#253, #247）— 暂缓
- #253: 16-bit checksum → 需独立 RFC
- #247: 确定性 genesis 领导者密钥 → 设计级问题，需单独评审

---

### 1-F：已自然修复（#234, #235, #237, #240）— 直接关闭
- Indexer 已有翻页保护、请求体大小限制等

---

### 1-G：未定位（#236, #254, #260, #248, #258, #239）— 待上游追踪

---

## 二、协议功能 Issue（共 66 个）

### 2-A：Receipt 丰富化（#24, #44, #75, #90, #103）
**文件：`/node/storage/src/types.rs`（TransactionReceipt）**
- #75: `cumulative_cycles_used`, `cumulative_cells_used`
- #103: `logs_root: Digest`
- #90: `bloom: [u8; 256]`
- #24: `post_tx_state_root: Digest`
- #44: Merkle proof 生成函数

### 2-B：Block 结构增强（#28, #39, #63, #94）
**文件：`/node/types/src/execution.rs`（Block struct）**

### 2-C：Transaction 类型系统（#81, #101, #133）
**文件：`/node/types/src/execution.rs`（Transaction struct）**

### 2-D：Mempool 增强（#65, #77, #95）
**文件：`/node/chain/src/mempool.rs`**

### 2-E：RPC/API 扩展（#97, #110, #131）
**文件：`/node/rpc/src/rpc.rs`**

### 2-F：Timer 系统完善（#26, #35, #41, #47, #57, #85, #118）
**文件：`/node/storage/src/timers.rs`, `/node/execution/src/pvm_host.rs`**

### 2-G：Mailbox 系统完善（#21, #37, #69, #80, #88, #100, #107, #114）
**文件：`/node/storage/src/mailbox.rs`**

### 2-H：DeferredTx 系统完善（#22, #32, #56, #70, #83, #89, #96）
**文件：`/node/execution/src/execution/engine.rs`**

### 2-I：Gas/GasCost 完善（#27, #36, #42, #59, #84）
**文件：`/node/execution/src/gas.rs`**

### 2-J：PvmHost 存储隔离（#34, #43）
**文件：`/node/execution/src/pvm_host.rs`**

### 2-K：Genesis 根哈希计算（#29, #67）
**文件：`/node/chain/src/genesis.rs`**

### 2-L：Engine 可观测性（#62, #68, #104, #144）
**文件：`/node/chain/src/engine.rs`**

### 2-M：Application 块约束（#23, #145）
**文件：`/node/types/src/execution.rs`**

### 2-N：Transaction 编码优化（#151）— 低优先级

### 2-O：CLI tx 签名命令（#82）

### 2-P：文档类（#18, #38, #61, #78, #98, #102, #122）— 持续维护

### 2-Q：Demo 脚本（#87, #93）

---

## 三、执行顺序

### 阶段一：安全修复（立即执行）
```
1-A ✅  Inspector panic 修复（3 issues）
1-B     RPC CORS 配置（2 issues）
1-C     Shell 脚本安全（6 issues）
1-D     日志信息泄露（3 issues）
1-F     关闭已修复 issues（4 issues）
```

### 阶段二：协议数据结构
```
2-A  Receipt 丰富化（5 issues）
2-D  Mempool 增强（3 issues）
2-B  Block 结构增强（4 issues）
2-M  块执行约束（2 issues）
2-K  Genesis 根哈希（2 issues）
```

### 阶段三：核心系统完善
```
2-G-1  Mailbox 队列增强
2-H-1  DeferredTx 调度 API
2-J    PvmHost 存储隔离
2-G-2  Mailbox 生命周期
2-H-2  DeferredTx 管理
2-F-1  Timer 基础约束
```

### 阶段四：功能扩展
```
2-E    RPC API 扩展
2-L    Engine 可观测性
2-C    Transaction 类型系统
2-I    Gas 计量精度
2-F-2/3 Timer 经济模型 + 长期索引
```

### 阶段五：文档与工具
```
2-P  文档（持续维护）
2-Q  Demo 脚本
2-O  CLI tx 签名
2-N  编码优化
1-E  加密设计缺陷（独立 RFC）
```

---

## 四、关键文件路径

| 批次 | 主要修改文件 |
|------|------------|
| 1-A ✅ | `/node/inspector/src/main.rs` |
| 1-B | `/node/rpc/src/rpc.rs:187` |
| 1-C | `/node/scripts/*.sh` |
| 1-D | `/node/rpc/src/error.rs`, logging spans |
| 2-A | `/node/storage/src/types.rs` (TransactionReceipt) |
| 2-B | `/node/types/src/execution.rs` (Block) |
| 2-C | `/node/types/src/execution.rs` (Transaction) |
| 2-D | `/node/chain/src/mempool.rs` |
| 2-E | `/node/rpc/src/rpc.rs`, `/node/rpc/src/ws.rs`（新） |
| 2-F | `/node/storage/src/timers.rs`, `/node/execution/src/pvm_host.rs` |
| 2-G | `/node/storage/src/mailbox.rs`, `/node/storage/src/types.rs` |
| 2-H | `/node/execution/src/execution/engine.rs` |
| 2-I | `/node/execution/src/gas.rs`, `/node/execution/src/pvm_host.rs` |
| 2-J | `/node/execution/src/pvm_host.rs` |
| 2-K | `/node/chain/src/genesis.rs` |
| 2-L | `/node/chain/src/engine.rs` |
| 2-M | `/node/types/src/execution.rs` |
