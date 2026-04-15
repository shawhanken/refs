# 客户待回应事项清单

> **生成日期**：2026-02-18  
> **数据来源**：Slack #devnet-eng 频道对话记录  
> **团队成员**：Tony、pavilion  
> **客户方**：Charles DePue、patrick、Martin Aceto、Ryan Chan、Josh  

---

## 1. 🔴 CI/CD 测试指引文档（高优先级）

**欠谁**：Martin Aceto  
**承诺时间**：2026-02-11  
**当前状态**：❌ 未交付

### 背景
Martin 已完成 CI/CD 部署流水线搭建（GitHub Actions + Terraform），devnet 分支部署已自动化运行。但 pipeline 中缺少测试环节，Martin 明确请求我们提供指引。

### 需要交付的内容

- [ ] **各仓库部署分支名称清单**
  - `cowboyinc/node` 仓库：用于 Dev / Staging / Prod 的分支名
  - `cowboyinc/pvm` 仓库：对应分支名
  - `cowboyinc/runner` 仓库：对应分支名
- [ ] **部署前测试（Pre-deployment Tests）**
  - 列出需要在部署前运行的单元测试命令
  - 例如：`cargo test` 的具体 package 或 test suite
  - 编译检查命令
- [ ] **部署后冒烟测试（Post-deployment Smoke Tests）**
  - Health check 端点验证（如 `/health`、`/metrics`）
  - 区块高度增长验证
  - Actor 部署端到端测试（如部署 `counter_actor.py` 验证完整流程）
  - 其他关键功能验证项

### 相关引用
- Tony（2/11）原话：*"sounds good, I think we can get you a documentation about: 1/Branch names from each repository for the deployment, 2/Which unit tests to run before the deployment, 3/Which unit tests to run after the deployment"*
- Martin（2/12）原话：*"The missing step are the tests, I will need your guidance to setup the testing on the pipeline"*

---

## 2. 🔴 白皮书与代码对照报告（高优先级）

**欠谁**：Charles DePue  
**承诺时间**：2026-02-15  
**当前状态**：❌ 未交付

### 背景
Charles 提交了大幅简化的白皮书 PR（https://github.com/cowboyinc/cowboy/pull/22），Tony 承诺内部讨论后产出对照报告。

### 需要交付的内容

- [ ] **对照分析报告**
  - 当前代码已实现但白皮书未提及的功能
  - 白皮书中描述但代码尚未实现的功能
  - 代码实现与白皮书描述不一致的地方
- [ ] **对 PR #22 的正式 Review**
  - 在 GitHub PR 上留下具体的 review comments
  - 标注我们认为需要调整或补充的内容

### 相关引用
- Tony（2/15）原话：*"We will discuss internally to see what's matching and what's not, and create a report based on the latest whitepaper."*
- Charles 补充：*"the goal was to clarify inconsistencies and make a doc that we can share publicly"*

---

## 3. 🔴 Linear Issue 分配与 Review（高优先级）

**欠谁**：patrick  
**承诺时间**：2026-02-11  
**当前状态**：❌ 未回复

### 背景
patrick 在 Linear 上创建了 86 个 DevEx Issue，按 Phase 1-4 里程碑分组，并设置了优先级。他请求 Martin、Tony、pavilion 一起 review 并认领分配。

### 需要交付的内容

- [ ] **Review Linear "End-to-End Demo & Docs" 项目中的 86 个 Issue**
  - 项目链接：https://linear.app/cowboy-labs/project/end-to-end-demo-and-docs-84eab8b62844/
- [ ] **Issue 认领与分配**
  - Tony / pavilion 认领属于我们团队负责的 issue
  - 对不合理或需要讨论的 issue 标注 comment
- [ ] **回复 patrick 确认已完成 review**

### 相关引用
- patrick（2/11）原话：*"I got the 86 dev ex issues added to the project grouped by milestone and priority. PTAL and assign out."*

---

## 4. 🟡 Runner CIP 文档（中优先级）

**欠谁**：Charles DePue  
**承诺时间**：2026-02-17  
**当前状态**：⏳ 起草中

### 背景
Charles 重写了 CIP-7（Simple Stream Protocol），Tony 回复说我们也在起草一份 Runner CIP 文档，完成后会提交 PR。

### 需要交付的内容

- [ ] **起草 Runner CIP 文档**
  - 详细描述 Runner 的工作机制
  - 参考 CIP-7 的格式和风格
  - 覆盖：Runner 注册、任务分发、结果提交、验证机制等
- [ ] **提交 PR 到 cowboyinc/cowboy 仓库**
- [ ] **通知 Charles 和 Ryan Chan review**

### 相关引用
- Tony（2/17）原话：*"we are also trying to draft another CIP which is talking into details about how exactly Runner is working, will PR once it is drafted."*

---

## 5. 🟡 部署策略的最终对齐确认（中优先级）

**欠谁**：Martin Aceto  
**承诺时间**：2026-02-11  
**当前状态**：⏳ 部分讨论

### 背景
Martin 发布了部署策略文档（Notion），定义了 dev/stg/prd 环境的代码推进流程。Charles 表示 deployment/testing 部分没问题，但不确定是否与 Tony 团队的工作流一致。Tony 有过初步交流但尚未最终确认。

### 需要交付的内容

- [ ] **Review Martin 的部署策略文档**
  - Notion 链接：https://www.notion.so/Deployment-strategy-2fdd57da9b1b8089831de9d2f4002715
- [ ] **确认或提出修改意见**
  - Dev 环境的分支策略和自动部署触发条件
  - Staging 环境的准入标准和测试流程
  - Production 环境的发布流程
- [ ] **正式回复 Martin 确认对齐**

### 相关引用
- Martin（2/11）原话：*"will be awesome if we can define how the team will work on dev, stg, and prd"*
- Charles（2/4）原话：*"i'd say i am definitely pro the pieces of this that are the deployment/testing, less sure of the branching system logic bc i don't know how Tony's team works"*

---

## 6. 🟡 patrick 的产品与架构讨论（中优先级）

**欠谁**：patrick  
**提出时间**：2026-02-18  
**当前状态**：❌ 未回复

### 背景
patrick 提出了多个产品方向和架构设计问题，涉及协议扩展、代币经济、隐私计算等方面。这些问题虽然不是紧急交付物，但需要我们团队给出意见或讨论方向。

### 需要回应的问题

- [ ] **XMTP 支持**：是否需要支持 XMTP 协议让 Actor 可以与非 Cowboy 的 agent 通信？
- [ ] **Agent Token 设计**
  - Actor 发行的 token 是否应赋予服务访问权 / 治理权？
  - 费用收入分成模型是否可行？
- [ ] **Cowboy Gold 代币经济**
  - 新用户免费 gas 补贴方案
  - 仅限 CowChat 用户还是包含 CLI 用户？
  - 免费提供 Cowboy 自有 Watchtower Feed 的可行性
- [ ] **Runner 网络扩展**
  - 是否支持 storage 和 sandboxing？
  - 本地 Runner 方案（敏感数据路由到用户自己的 Runner）
  - 混合 Runner 架构（本地 + 开放网络的混合模式）
  - 自我证明验证机制
- [ ] **AI NFT / 共享所有权**
  - Actor 的共享所有权 / 访问权模型

### 相关引用
- patrick（2/18）的完整讨论串，涉及 agent tokens、cowboy gold、local storage/sandboxes、AI NFTs

---

## 7. 🟢 Docs 网站反爬虫问题跟进（低优先级）

**欠谁**：patrick  
**提出时间**：2026-01-31  
**当前状态**：❌ 无后续跟进

### 背景
patrick 反映 docs 页面无法被 AI agent 索引，页面对机器人不可访问。Tony 回复可能是 Cloudflare 的防护，但未进一步排查。（注：docs 已迁移到 cowboy.inc 域名，问题可能已自行解决，但需确认）

### 需要交付的内容

- [ ] **确认当前 docs.cowboy.inc 是否仍然存在反爬虫问题**
- [ ] **如果问题仍存在，排查 Cloudflare 或 Mintlify 的 robots.txt / bot 策略**
- [ ] **回复 patrick 确认状态**

### 相关引用
- patrick（1/31）原话：*"do you control docs rn? the page isn't getting indexed at all... and isn't accessible to agents"*
- Tony（1/31）原话：*"I don't think we add any anti-bot manually, it is passing through cloudflare, it could be cloudflare actively preventing bots, I'm not sure"*

---

## 📊 优先级汇总

| 优先级 | # | 事项 | 欠谁 | 类型 |
|--------|---|------|------|------|
| 🔴 高 | 1 | CI/CD 测试指引文档 | Martin | 文档交付 |
| 🔴 高 | 2 | 白皮书与代码对照报告 | Charles | 报告交付 |
| 🔴 高 | 3 | Linear 86 Issue 分配 | patrick | Review & 回复 |
| 🟡 中 | 4 | Runner CIP 文档 PR | Charles | 文档交付 |
| 🟡 中 | 5 | 部署策略最终对齐 | Martin | 确认回复 |
| 🟡 中 | 6 | patrick 的产品架构讨论 | patrick | 讨论回复 |
| 🟢 低 | 7 | Docs 反爬虫问题跟进 | patrick | 排查确认 |

---

## 建议行动计划

1. **本周内**：优先完成 #1（CI/CD 测试指引）和 #3（Linear Issue 分配），这两项直接阻塞客户方的开发与协作
2. **本周内**：启动 #2（白皮书对照报告），至少给 Charles 一个初步反馈
3. **下周**：提交 #4（Runner CIP）PR，完成 #5（部署策略确认）
4. **持续**：回复 #6 中 patrick 的讨论问题，可以在周会或 Slack 异步讨论
5. **空闲时**：确认 #7 docs 反爬虫状态
