# 里程碑日程安排

**起始日期：** 2026-03-17  
**目标上线：** 2026-04-15 (Devnet Release)  
**内部冻结：** 2026-04-11 (提前4天冻结代码)  

---

## 总览

```
W1 (3/17-23)  ████████ 紧急安全修复 + 稳定性验证
W2 (3/24-30)  ████████ 安全加固 + 产块稳定
W3 (3/31-4/6) ████████ 核心规格修复
W4 (4/7-13)   ████████ 功能完善 + 测试覆盖
    4/11      ──────── 代码冻结
    4/14      ──────── Release Candidate
    4/15      ★★★★★★★★ Devnet Release
```

---

## W1：紧急安全修复 + 稳定性基线（3/17 - 3/23）

### 目标
消除所有 HIGH 级别安全风险，确认内存/产块稳定性基线。

### 任务

| 日期 | 任务 | 负责 | 产出 |
|------|------|------|------|
| 3/17 Mon | P1-1: 私钥文件权限修复 | Dev | PR |
| 3/17 Mon | P1-3: watchtower init() 修复 | Dev | PR |
| 3/18 Tue | P1-2: Genesis 默认配置安全化 | Dev | PR |
| 3/18 Tue | P1-4: CLI bootstrap 校验 | Dev | PR |
| 3/19 Wed | 部署最新代码，启动内存稳定性 24h 测试 | Ops | 监控报告 |
| 3/20 Thu | 分析内存测试结果 | Dev | 结论 |
| 3/21 Fri | 产块时间稳定性测试（1000块） | Dev | 数据报告 |
| 3/22-23 | 重新运行 Almanax.ai 扫描（最新代码） | Tony | 新报告 |

### 交付物
- [ ] 4 个 HIGH 安全修复 PR 全部合并
- [ ] 内存 24h 测试报告
- [ ] 产块稳定性数据

### 里程碑检查点
> ✅ 所有 HIGH 安全问题已修复  
> ✅ 内存稳定性确认（或发现新问题并有修复计划）

---

## W2：安全加固 + 系统稳定（3/24 - 3/30）

### 目标
修复所有 MEDIUM 安全问题；确认产块时间可接受。

### 任务

| 日期 | 任务 | 负责 | 产出 |
|------|------|------|------|
| 3/24 Mon | P2-1: CORS 策略收紧 | Dev | PR |
| 3/24 Mon | P2-5: 私钥从日志/序列化移除 | Dev | PR |
| 3/25 Tue | P2-2: API 速率限制（全局 + Faucet） | Dev | PR |
| 3/25 Tue | P2-3: 请求体大小限制 | Dev | PR |
| 3/26 Wed | P2-4: 查询分页（indexer 全部端点） | Dev | PR |
| 3/26 Wed | P2-6: Unbounded channel → bounded | Dev | PR |
| 3/27 Thu | feed_subscriber/watchtower 修复（M-11~12） | Dev | PR |
| 3/28 Fri | Entitlement ID + API key + 其余 MEDIUM | Dev | PR |
| 3/29-30 | 安全回归测试全覆盖验证 | QA | 测试报告 |

### 交付物
- [ ] 23 个 MEDIUM 安全修复 PR 全部合并
- [ ] 安全回归测试套件通过率 100%

### 里程碑检查点
> ✅ 全部 HIGH + MEDIUM 安全问题已修复  
> ✅ 安全回归测试自动化运行

---

## W3：核心规格修复（3/31 - 4/6）

### 目标
修复影响正确性和互操作的规格差距。

### 任务

| 日期 | 任务 | 负责 | 产出 |
|------|------|------|------|
| 3/31-4/1 | P3-1: cowboy-runner-types 共享 crate | Dev | PR |
| 4/1-2 | P3-2: VRF 选择算法修正 | Dev | PR |
| 4/2 | P3-3: Runner 结果签名实现 | Dev | PR |
| 4/2 | P3-5: Runner 注册签名验证 | Dev | PR |
| 4/3 | P3-4: Runner 候选过滤补全（6项） | Dev | PR |
| 4/3 | P3-6: 最低质押量统一 | Dev | PR |
| 4/4 | P3-7: Gas 常量修正 | Dev | PR |
| 4/4 | P3-8: JobSpec runner_pool 字段 | Dev | PR |
| 4/5 | P3-9: CBOR HTTP/MCP/Custom 解析 | Dev | PR |
| 4/5-6 | 集成测试：Node ↔ Runner 类型兼容 | QA | 测试报告 |

### 交付物
- [ ] 共享类型 crate 发布
- [ ] VRF + 签名 + 过滤 + Gas 修复全部合并
- [ ] Node ↔ Runner 集成测试通过

### 里程碑检查点
> ✅ 数据类型 Node/Runner 完全统一  
> ✅ VRF 选择算法符合 CIP-2  
> ✅ 签名链路端到端验证

---

## W4：功能完善 + 验收准备（4/7 - 4/13）

### 目标
完成高优功能项（超时重选、Entitlement、Basefee）；建立完整测试覆盖；确定 Release 范围。

### 任务

| 日期 | 任务 | 负责 | 产出 |
|------|------|------|------|
| 4/7 Mon | P4-1: 超时重选机制 | Dev | PR |
| 4/7 Mon | P4-7: Runner 自动注册 + 心跳上链 | Dev | PR |
| 4/8 Tue | P4-3: Entitlement 约束检查 | Dev | PR |
| 4/8 Tue | P4-4: EIP-1559 Basefee | Dev | PR |
| 4/9 Wed | P4-2: Commit-Reveal 阶段一（多结果链上投票） | Dev | PR |
| 4/9 Wed | P4-5: Multisig 评估文档 | PM | 文档 |
| 4/9 Wed | P4-6: Runner 文件写入（待 Charles Demo） | Dev | PR |
| 4/10 Thu | LOW 安全问题批量修复 | Dev | PR |
| 4/10 Thu | 端到端验收测试全流程 | QA | 测试报告 |
| 4/10 Thu | Devnet 功能支持声明文档 | PM | 文档 |
| **4/11 Fri** | **🔒 代码冻结** | All | — |
| 4/12-13 | 最终验证 + Release Candidate 打包 | All | RC Build |

### 交付物
- [ ] 超时重选 + 自动注册 PR 合并
- [ ] Devnet 功能支持声明完成
- [ ] 端到端验收测试 100% 通过
- [ ] Release Candidate 构建

### 里程碑检查点
> ✅ 代码冻结，无新功能合入  
> ✅ Release Candidate 构建成功  
> ✅ 功能支持/不支持声明对外准备就绪

---

## 发布日：4/15

| 时间 | 事项 |
|------|------|
| AM | 最终确认 RC 状态，Tag 发布 |
| AM | 更新文档/README/CHANGELOG |
| PM | 对外发布 Devnet Release |

---

## 风险项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 内存泄漏未完全修复 | 长时间运行崩溃 | W1 优先验证，有问题立即修复 |
| 共享 types crate 改动影响面大 | 两个仓库编译问题 | 在独立分支先验证 |
| Commonware 产块精度无法改善 | 客户不满 | 文档化限制 + 后续版本改进 |
| 多节点测试发现新问题 | 时间不够修复 | Devnet 先以单节点形态发布 |
| Charles DePue 的文件写入 Demo 延迟 | 功能缺失 | 先设计框架，Demo 到后填充 |
