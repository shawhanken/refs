# Almanax.ai 安全问题修复方案

**日期：** 2026-03-16  
**报告来源：** Almanax.ai Security Scan — cowboyinc/node (commit: 395150f8)  

> [!WARNING]
> Almanax 报告 Summary 表格声称 47 项（0C/4H/17M/25L/1I），但逐条统计正文实际有 **52 项**（4H/23M/24L/1I）。本文档以**正文实际条目**为准。

**实际统计：** 4 HIGH / 23 MEDIUM / 24 LOW / 1 INFO = **52 Total**  

---

## 🔴 HIGH 级别（4项）

### H-1. 私钥文件权限不安全 — `cli/src/commands.rs`
- **状态：** 待修复
- **方案：** `fs::write` → `OpenOptions::create_new().mode(0o600)`，涉及 wallet create/upgrade/init/mnemonic
- **合并门控测试：** `test_key_file_has_600_permissions`

### H-2. Genesis 默认管理员使用公知密钥 — `chain/src/genesis.rs`
- **状态：** 待修复
- **方案：** 非测试构建禁止 `GenesisConfig::default()`，要求显式配置文件，使用 `public_key_hex`
- **合并门控测试：** `test_genesis_requires_explicit_config`

### H-3. Watchtower Registry init() 可重入 — `cli/actors/watchtower_registry.py`
- **状态：** 待修复
- **方案：** 添加 `owner` 已存在检测，已初始化后拒绝
- **合并门控测试：** `test_init_cannot_be_called_twice`

### H-4. CLI Bootstrap 无校验 — `cli-bootstrap.sh`
- **状态：** 待修复
- **方案：** 添加 SHA-256 校验 + API key 改 HTTP Header
- **合并门控测试：** 手动验证下载校验流程

---

## 🟠 MEDIUM 级别（23项）

| # | 问题 | 文件 | 方案概要 |
|---|------|------|----------|
| M-1 | CORS any origin (credentials) | indexer/src/lib.rs | 改配置化白名单 |
| M-2 | CORS permissive + WebSocket | indexer/src/lib.rs (API) | 白名单 + WS Origin 校验 |
| M-3 | 地址交易查询无上限 | indexer/src/lib.rs | limit 限幅 + 分页 |
| M-4 | 最新交易查询无上限 | indexer/src/lib.rs | limit 限幅（默认100） |
| M-5 | get_blocks 无范围限制 | indexer/src/lib.rs | MAX_PAGE_SIZE=100 |
| M-6 | 多个查询端点无 OOM 保护 | indexer 全局 | 统一分页中间件 |
| M-7 | 私钥进入 tracing span | chain/src/application.rs | 移除，改用公钥 |
| M-8 | Faucet 无速率限制/金额上限 | chain/src/application.rs | governor/tower限流 + 金额cap |
| M-9 | RPC 全局无速率限制 | chain/src/application.rs | RateLimitLayer 全局 + 分级 |
| M-10 | /submit 无 body size 限制 | chain/src/application.rs | DefaultBodyLimit::max(1MB) |
| M-11 | feed_subscriber 消息伪造 | cli/actors/feed_subscriber.py | ctx.sender == feed_address 校验 |
| M-12 | feed_subscriber 订阅可劫持 | cli/actors/feed_subscriber.py | owner 授权检查 |
| M-13 | Config-controlled path traversal | cli/src/commands.rs (upgrade) | 拒绝绝对路径和 `..` |
| M-14 | API key 暴露在 URL | cli-bootstrap.sh | 改 Authorization Header |
| M-15 | Unbounded feed 注册 DoS | cli/actors/watchtower_registry.py | 限制 feed 数量/字段长度 |
| M-16 | Unbounded channel 内存耗尽 | client/src/consensus.rs | bounded(1024) + Drop abort |
| M-17 | WebSocket 空帧 panic | client/src/consensus.rs | 前置 is_empty() 检查 |
| M-18 | Entitlement ID 不含 constraints | types/src/entitlement.rs | ID preimage 加入 constraints |
| M-19 | Unbounded response body OOM | client/src/rpc.rs | Content-Length 检查 + 流式 |
| M-20 | Config 含私钥可 Serialize | chain/src/lib.rs | #[serde(skip_serializing)] |
| M-21 | Indexer API 绑定 0.0.0.0 | indexer/src/main.rs | 默认 127.0.0.1 可配 |
| M-22 | Unbounded hex decode OOM | runner/src/types.rs | 先验证长度=64再 decode |
| M-23 | Unbounded queue + detached task | client/src/events.rs | bounded channel + Drop abort |

---

## 🟡 LOW 级别（24项）

| # | 问题 | 文件 | 方案概要 |
|---|------|------|----------|
| L-1 | 日志记录完整交易内容 | indexer submit | 只记录 hash/count |
| L-2 | Genesis leader key 硬编码 | chain/application | 可配化 genesis seed |
| L-3 | 消息 payload 无大小限制 | cli/actors/feed_subscriber | max payload size 检查 |
| L-4 | Actor 名称缺 Windows 过滤 | cli/commands | 正则白名单 `^[a-zA-Z0-9_-]+$` |
| L-5 | TLS expect crash | client/lib | 改 Result 返回 |
| L-6 | HTTP 客户端无超时 | client/lib | connect_timeout + timeout |
| L-7 | URI scheme panic | client/lib | 改 Result 返回 |
| L-8 | cd 失败后执行 cargo | diagnose_runner.sh | set -euo pipefail |
| L-9 | PID grep kill 误杀 | restart_validator.sh | PID 文件替代 |
| L-10 | 符号链接删除风险 | restart_validator.sh | realpath 验证 |
| L-11 | 16-bit checksum 碰撞 | cli/key_format | 文档标注非安全用途 |
| L-12 | PEM parser 无大小限制 | cli/key_format | 限制 base64 长度=44 |
| L-13 | pkill 匹配过宽 | start_validator.sh | 精确路径 + PID 文件 |
| L-14 | Faucet 默认开启 | start_validator.sh | 默认 ENABLE_FAUCET=0 |
| L-15 | Inspector expect panic (single) | inspector/main | 改 match/? 处理 |
| L-16 | Inspector stream panic | inspector/main | 错误处理 + 重连 |
| L-17 | WASM participants panic | types/wasm | 改返回值/错误 |
| L-18 | WASM identity panic | types/wasm | 改 JsValue::NULL |
| L-19 | Entitlement Vec 无边界 | types/entitlement | Write 端加长度检查 |
| L-20 | URL path injection | client/rpc | URL 编码 + 格式校验 |
| L-21 | Genesis balance 溢出 | chain/genesis | checked_add / u128 |
| L-22 | 未转义 BASE_URL | indexer/test | 校验 scheme + `--` |
| L-23 | rm -rf 相对路径 | run_build.sh | 相对脚本目录 |
| L-24 | PVM 错误信息泄漏 | chain/error | 服务端记录，客户端屏蔽 |

---

## ℹ️ INFO 级别（1项）

| # | 问题 | 文件 | 方案 |
|---|------|------|------|
| I-1 | tail 固定路径符号链接泄漏 | diagnose_runner.sh | 文档注明 + stat 检查 |
