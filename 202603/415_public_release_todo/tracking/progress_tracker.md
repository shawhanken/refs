# 进度追踪

**最后更新：** 2026-03-16  

---

## Phase 1：紧急安全修复（W1: 3/17-3/23）

- [ ] P1-1: 私钥文件权限修复 (HIGH)
- [ ] P1-2: Genesis 默认配置安全化 (HIGH)
- [ ] P1-3: watchtower init() 重入修复 (HIGH)
- [ ] P1-4: CLI bootstrap 校验 (HIGH)
- [ ] P2-7: 内存泄漏 24h 测试
- [ ] P2-8: 产块时间稳定性测试
- [ ] 重新运行 Almanax.ai 扫描

## Phase 2：安全加固（W2: 3/24-3/30）

> 共 23 个 MEDIUM 项，以下按 `01_security_fixes.md` 编号。P2-1~P2-6 为 master plan 编号，M-7~M-23 为 Almanax 分类编号。

- [ ] P2-1 / M-1~M-2: CORS 策略收紧（2项）
- [ ] P2-2 / M-8~M-9: API 速率限制（Faucet + 全局）
- [ ] P2-3 / M-10: 请求体大小限制
- [ ] P2-4 / M-3~M-6: 查询分页（4项 indexer 端点）
- [ ] P2-5 / M-7: 私钥从日志移除
- [ ] P2-6 / M-16: Unbounded channel → bounded
- [ ] M-11: feed_subscriber 消息认证
- [ ] M-12: feed_subscriber 订阅授权
- [ ] M-13: Config-controlled path traversal
- [ ] M-14: API key 改 Header 方式
- [ ] M-15: Unbounded feed 注册 DoS
- [ ] M-17: WebSocket 空帧 panic
- [ ] M-18: Entitlement ID 含 constraints
- [ ] M-19: Unbounded response body
- [ ] M-20: Config Serialize 屏蔽私钥
- [ ] M-21: Indexer 绑定 127.0.0.1
- [ ] M-22: Unbounded hex decode
- [ ] M-23: Unbounded queue + detached task
- [ ] 安全回归测试 100%

## Phase 3：核心规格修复（W3: 3/31-4/6）

- [ ] P3-1: cowboy-runner-types 共享 crate（Gap §二）
- [ ] P3-2: VRF 选择算法修正（Gap §一）
- [ ] P3-3: Runner 结果签名（Gap §十三）
- [ ] P3-4: Runner 候选过滤补全（Gap §三）
- [ ] P3-5: Runner 注册签名验证（Gap §十一）
- [ ] P3-6: 最低质押量统一（Gap §十二）
- [ ] P3-7: Gas 常量修正（Gap §七）
- [ ] P3-8: JobSpec runner_pool 字段（Gap §九）
- [ ] P3-9: CBOR HTTP/MCP/Custom（Gap §十五）

## Phase 4：功能完善（W4: 4/7-4/13）

- [ ] P4-1: 超时重选机制（Gap §四）
- [ ] P4-2: Commit-Reveal 阶段一（Gap §五）
- [ ] P4-3: Entitlement 约束检查（Gap §十四）
- [ ] P4-4: EIP-1559 Basefee（Gap §八）
- [ ] P4-5: Multisig 评估文档
- [ ] P4-6: Runner 文件写入
- [ ] P4-7: Runner 自动注册+心跳
- [ ] LOW 安全问题批量修复（24项）

## 关键节点

- [ ] 🔒 4/11: 代码冻结
- [ ] 📦 4/14: Release Candidate
- [ ] 🚀 4/15: Devnet Release
