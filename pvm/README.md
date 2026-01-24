# PVM 相关文档索引

**最后更新**: 2026-01-24  
**文档数量**: 5 个综合文档

---

## 📋 文档分类原则

PVM 目录包含虚拟机相关的所有文档，包括核心功能、Python 解释器实现、PVM 内部机制等。所有文档已整合为 5 篇综合文档，便于阅读和维护。

---

## 📚 文档导航

### 🚨 必读文档（按优先级）

1. **01-API参考与使用指南.md** ⭐⭐⭐⭐⭐ **首先阅读**
   - Host API 和 Runtime API 完整参考
   - 基本使用示例
   - Continuation 使用示例
   - Python Actor 示例
   - 阅读时间：20-30 分钟

2. **04-编码规范与最佳实践.md** ⭐⭐⭐⭐⭐
   - 支持的 Python 特性
   - 限制和禁止的操作
   - Checkpoint 使用规范
   - 确定性执行要求
   - 常见错误和陷阱
   - 阅读时间：30-40 分钟

3. **02-功能设计与Continuation.md** ⭐⭐⭐⭐
   - Continuation 设计草案
   - SDK API 说明
   - 编译期约束
   - FSM 编译形态
   - CBOR Schema
   - Guard 机制
   - 阅读时间：40-50 分钟

4. **03-Checkpoint-Resume实现指南.md** ⭐⭐⭐⭐
   - 函数级 Checkpoint 支持
   - Block Stack 支持
   - Checkpoint File/Bytes API
   - 实现挑战和解决方案
   - 阅读时间：30-40 分钟

5. **05-测试评估与升级.md** ⭐⭐⭐
   - 测试覆盖率报告
   - 真实完成度评估
   - 升级安全防护方案
   - 可行性分析与路线图
   - 阅读时间：30-40 分钟

---

## 📖 文档详细说明

### 01-API参考与使用指南.md

**内容**:
- HostApi Trait 完整定义
- HostContext 和 HostError
- Runtime API（execute_tx, execute_tx_with_options）
- ExecutionOptions 和 ContinuationOptions
- 基本使用示例
- Continuation 使用示例
- Python Actor 示例

**适合人群**:
- 所有开发者
- 需要了解 API 的任何人
- 新加入的开发者

---

### 02-功能设计与Continuation.md

**内容**:
- Continuation 设计草案（Actor↔Actor, Actor↔Runner）
- SDK API 草案（Python 侧）
- 编译期约束
- Continuation 编译形态（FSM）
- CBOR Schema（消息与状态）
- Guard 机制
- capture() 允许的类型
- Continuation 和 Checkpoint 功能说明

**适合人群**:
- 需要实现 Continuation 功能的开发者
- 需要了解 FSM 编译的开发者
- 架构设计师

---

### 03-Checkpoint-Resume实现指南.md

**内容**:
- 函数级 Checkpoint 支持（问题分析和解决方案）
- Block Stack Checkpoint/Resume 支持
- Checkpoint 文件模式 + Bytes API
- 实现挑战和解决方案
- 使用约束

**适合人群**:
- 需要实现 Checkpoint 功能的开发者
- 需要了解实现细节的开发者
- 调试 Checkpoint 问题的开发者

---

### 04-编码规范与最佳实践.md

**内容**:
- 完全支持的 Python 特性
- 有限制或需要特别注意的特性
- 不支持或禁止的特性
- Checkpoint 使用规范
- 确定性执行要求
- 常见错误和陷阱
- 最佳实践

**适合人群**:
- 所有 Python 开发者
- 需要编写 PVM Actor 的开发者
- 需要了解限制的开发者

---

### 05-测试评估与升级.md

**内容**:
- 测试覆盖率报告（124 个测试）
- 真实完成度评估（35-40%）
- 升级安全防护方案
- 可行性分析与路线图
- 实现路径建议

**适合人群**:
- 测试工程师
- 项目管理者
- 需要了解项目状态的任何人

---

## 🎯 按角色阅读

### 👨‍💻 开发者（新加入）
1. **01-API参考与使用指南.md** - 了解 API
2. **04-编码规范与最佳实践.md** - 了解如何编写代码
3. **02-功能设计与Continuation.md** - 了解 Continuation 机制

### 👨‍💻 开发者（已参与）
1. **01-API参考与使用指南.md** - API 参考
2. **03-Checkpoint-Resume实现指南.md** - 实现细节
3. **04-编码规范与最佳实践.md** - 编码规范

### 🏗️ 架构师
1. **02-功能设计与Continuation.md** - Continuation 设计
2. **05-测试评估与升级.md** - 可行性分析
3. **03-Checkpoint-Resume实现指南.md** - 实现细节

### 🧪 测试工程师
1. **05-测试评估与升级.md** - 测试报告
2. **04-编码规范与最佳实践.md** - 测试场景

---

## 🔍 按问题查找

### "如何使用 PVM API？"
→ **01-API参考与使用指南.md**

### "Continuation 机制如何工作？"
→ **02-功能设计与Continuation.md**

### "如何实现 Checkpoint？"
→ **03-Checkpoint-Resume实现指南.md**

### "哪些 Python 特性支持？"
→ **04-编码规范与最佳实践.md**

### "测试覆盖如何？"
→ **05-测试评估与升级.md**

### "项目完成度如何？"
→ **05-测试评估与升级.md**

---

## 📊 文档统计

### 完整度
```
API 文档:     1 个 ✅ 完整
功能文档:     1 个 ✅ 完整
实现文档:     1 个 ✅ 完整
规范文档:     1 个 ✅ 完整
测试文档:     1 个 ✅ 完整
索引文档:     1 个 ✅ 本文档
────────────────────────
总计:        6 个
```

### 覆盖范围
```
API 参考:     ✅ 01-API参考与使用指南
功能设计:     ✅ 02-功能设计与Continuation
实现细节:     ✅ 03-Checkpoint-Resume实现指南
编码规范:     ✅ 04-编码规范与最佳实践
测试验证:     ✅ 05-测试评估与升级
项目管理:     ✅ 05-测试评估与升级
```

---

## 🚀 快速命令

### 查看所有文档
```bash
cd /home/ubuntu/workspace/refs/pvm
ls -lh *.md
```

### 搜索关键词
```bash
cd /home/ubuntu/workspace/refs/pvm
grep -r "关键词" *.md
```

### 查看文档大小
```bash
cd /home/ubuntu/workspace/refs/pvm
wc -l *.md
```

---

## 📝 文档维护

### 更新频率
- **01-API参考与使用指南.md**: API 变更时更新
- **02-功能设计与Continuation.md**: 设计变更时更新
- **03-Checkpoint-Resume实现指南.md**: 实现变更时更新
- **04-编码规范与最佳实践.md**: 规范变更时更新
- **05-测试评估与升级.md**: 测试结果或评估更新时更新

### 归档策略
- 每个主要版本完成后，创建快照
- 重要里程碑时，打 git tag
- 主要版本时，归档到 `_archive_/` 目录

---

## 🔗 相关资源

### 代码仓库
- **主仓库**: `/home/ubuntu/workspace/pvm/`
- **关键文件**:
  - `crates/pvm-host/src/lib.rs` - Host API
  - `crates/pvm-runtime/src/lib.rs` - Runtime API
  - `crates/vm/src/vm/checkpoint.rs` - Checkpoint 实现
  - `crates/vm/src/vm/snapshot.rs` - Snapshot 实现

### 相关文档
- `chain/PVM_CHAIN_INTEGRATION_CN.md` - PVM 链集成方案
- `whitepaper/` - 核心技术白皮书

---

## ⚡ 核心要点（TL;DR）

### 已实现 ✅
- Host API 和 Runtime API
- Checkpoint 模式（基础功能）
- 函数级 Checkpoint 支持
- Block Stack 支持
- 测试覆盖率 80%

### 部分实现 ⚠️
- FSM 模式（代码存在但默认未启用）
- 确定性执行（部分实现）

### 未实现 ❌
- Runner 系统（只有接口框架）
- Guard 机制
- 完整确定性执行

### 下一步 🎯
1. **启用 FSM 编译器**：设置 `pvm_fsm: true`
2. **完善确定性执行**：SoftFloat、stdlib 白名单
3. **实现 Runner 系统**：完整实现链下计算
4. **实现 Guard 机制**：并发控制

---

**索引版本**: 2.0  
**创建时间**: 2026-01-24  
**维护者**: 开发团队
