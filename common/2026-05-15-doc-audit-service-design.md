# 文档审计服务 — 完整设计文档

**日期：** 2026-05-15
**状态：** 草案
**负责人：** 待定
**关联文档：** [`2026-05-15-cip-consistency-bot-design.md`](./2026-05-15-cip-consistency-bot-design.md)（本设计在其架构基础上扩展为多维度、多仓库的通用服务）

---

## 0. 与既有 CIP Bot 设计的关系

本服务把既有 CIP 一致性 Bot 的范围从「单仓库 CIP/白皮书一致性检查」扩展为「**任意仓库、任意文档目录、多维度审计**」的通用服务：

| 维度 | CIP Bot（既有） | 本服务（新） |
|---|---|---|
| 触发 | 单仓库 PR | 任意接入仓库 PR |
| 检查维度 | 一致性（结构化资源 + 跨文档规则 + 语义） | 一致性 + 安全 + 技术可行性 + 架构可行性 + 风格（可插拔） |
| 部署形态 | Composite GitHub Action（self-contained） | **Action 客户端 + 服务器后端**（混合架构） |
| 状态持久化 | 无（每次 PR 独立） | 索引缓存、代码符号索引、跨 PR 漂移历史、预算账本 |
| 配置 | Action 输入 | 仓库内 `.github/doc-audit.yml` + 服务器侧策略 |
| 代码比对 | LLM 现场 Grep | 服务器侧预建 `code_index`，精确查找 + LLM 兜底 |
| 第三方信号 | 无 | 融合 GitHub Secret Scanning / gitleaks 等 |
| Finding 去重 | 字面哈希 | 字面哈希 + LLM 语义去重（G-Eval 风格） |

**既有 CIP Bot 的所有数据 schema、规则定义、错误降级策略都被本设计完整继承**，只是把语义 pass 与多维度 LLM 调用从 Action 内迁出到服务器侧。

---

## 1. 目的

当任意接入仓库的 PR 修改了配置中声明的文档目录时，自动触发多维度审计：

1. **一致性** —— 跨文档术语、引用、结构化资源（opcode/地址/编号等）冲突
2. **安全性** —— 文档示例中的敏感信息泄露、危险操作建议、权限模型漏洞
3. **技术可行性** —— 文档描述与同仓库代码现实是否吻合
4. **架构可行性** —— 是否违背项目已有架构原则、是否引入循环依赖或破坏性变更
5. **风格 / 术语** —— 术语表偏移、链接失效、格式异常

输出方式：
- **Check Run** 在 PR 页面顶部展示总览状态
- **Annotations** 在 "Files changed" 视图直接行内标注
- **Sticky PR Comment** 给出完整结构化报告
- **可选 SARIF** 输出至 GitHub Code Scanning
- **硬冲突阻断合并**（按维度分别配置严重度门槛）

## 2. 非目标

- **不替代人工审查** —— bot 是若干信号之一，最终判定权在 reviewer
- **不做风格 linter** —— 现有的 markdownlint / vale 等工具更适合做格式检查；本服务专注语义层
- **不做自动 fix-up 提交** —— 只在评论里给文本性修改建议，不替开发者改文件
- **不覆盖文档与代码漂移的全量检查** —— 只在与 PR 改动直接相关的范围内做技术可行性核对，全量审计仍由人工 + 专门的漂移跟踪机制承担
- **不做跨仓库一致性** —— 每次审计的语料范围是单个仓库内配置声明的目录

## 3. 架构总览

### 3.1 数据流

```
PR opened / synchronize / reopened / ready_for_review
        │
        ▼
.github/workflows/doc-audit.yml   （仓库内）
        │
        ▼
.github/actions/doc-audit  (composite action, thin client)
        │
        ├─ ① extract_index.py    (base + head → index_*.json)
        ├─ ② diff.py             (资源级 diff → diff.json)
        ├─ ③ rules.py            (确定性一致性检查 → findings_rules.json)
        ├─ ④ dispatch.py         (POST → Audit Service Server)
        │                                │
        │                                ▼
        │                    ┌─────────────────────────┐
        │                    │  Audit Service Server   │
        │                    │                         │
        │                    │  ┌───────────────────┐  │
        │                    │  │ Orchestrator      │  │
        │                    │  └─┬─────────────────┘  │
        │                    │    │                    │
        │                    │    ├─ Consistency Agent │
        │                    │    ├─ Security Agent    │
        │                    │    ├─ Technical Agent   │
        │                    │    ├─ Architecture Agent│
        │                    │    └─ Style Agent       │
        │                    │                         │
        │                    │  Cache (Redis)          │
        │                    │  Budget Ledger          │
        │                    │  Audit History (PG)     │
        │                    └─────────────────────────┘
        │                                │
        │                                ▼   findings_semantic_*.json
        ├─ ⑤ aggregate.py        (合并 + 校验 + 去重)
        └─ ⑥ report.py           (Check Run + Annotations + PR Comment + SARIF)
```

### 3.2 职责边界

| 组件 | 职责 | 不做什么 |
|---|---|---|
| **Action（thin client）** | 触发、抽索引、跑确定性规则、调用服务器、发布结果 | 不调 LLM、不持久化任何状态 |
| **服务器** | LLM 编排、跨 PR 缓存、预算管理、审计历史 | 不直接访问 GitHub API、不发 PR 评论 |

**关键设计决定：服务器永远不调 GitHub API。** 这条边界让服务器成为"纯计算后端"，可以无状态扩容，鉴权模型也大幅简化。所有 GitHub 写操作仍由 Action 用其原生 token 完成。

### 3.3 设计原则

继承既有 CIP Bot 设计的全部原则，并补充：

- **规则 pass = 硬证据。** 每条发现必须引用具体 `file:line`。硬发现可阻断合并。
- **语义 pass = 仅供参考。** LLM 发现必须给出可校验的 `file:line`，校验失败即丢弃。语义发现按维度独立配置严重度（默认 warn-only）。
- **降级而非崩溃。** 服务器宕机 → Action 仅基于 rules pass 出报告；某维度 LLM 调用失败 → 该维度标 `degraded`，其余继续。
- **Action 端 0 长期状态。** 所有跨 PR 状态在服务器；Action 每次 cold start。
- **服务器无 GitHub 写权限。** Action 持 GitHub token，服务器持 LLM token，权限完全分离。
- **每个维度可独立启用 / 关闭 / 调严重度。** 通过仓库内 `.github/doc-audit.yml` 配置，不需要重新部署服务器。
- **各阶段产物落盘 JSON + Actions artifact 上传。** 便于本地复现和单元测试。
- **优先精确比对，LLM 留给真正模糊的部分。** 能用规则、符号索引、第三方扫描器解决的，绝不交给 LLM。LLM 只处理需要语义理解的剩余部分——这是降噪、降本、提速的核心杠杆。
- **跨 PR 语义去重而非字面去重。** 同一本质问题在不同 PR 反复出现时必须被识别，否则开发者会被噪音淹没。

### 3.4 为什么不用 GitHub App + 纯服务器架构

权衡过三种形态：

| 形态 | 优势 | 代价 | 结论 |
|---|---|---|---|
| 纯 Action（既有 CIP Bot） | 0 运维、自包含 | 无跨 PR 缓存、无中央预算 | 单仓库够用，多仓库 / 多维度浪费 |
| 纯 GitHub App + 服务器 | 完整中央控制 | 服务器持 GitHub token、需公网 webhook、复刻 80% 的 Actions 能力 | 重 |
| **混合（本设计）** | Action 的原生集成 + 服务器的中央能力，权限分离 | 需两端协同部署 | **采纳** |

混合方案的关键回报：服务器宕机时整个系统降级到「等价于既有 CIP Bot」继续工作，而不是停摆。

## 4. 触发与配置

### 4.1 Workflow 模板（仓库侧）

```yaml
# .github/workflows/doc-audit.yml
name: Doc Audit
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    paths:
      - 'docs/**'
      - 'refs/**'
      - '.github/doc-audit.yml'
permissions:
  contents: read
  pull-requests: write
  checks: write
  # security-events: write   # 启用 SARIF 时打开
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: your-org/doc-audit-action@v1
        with:
          config: .github/doc-audit.yml
          server_url: ${{ vars.DOC_AUDIT_SERVER_URL }}
          server_token: ${{ secrets.DOC_AUDIT_TOKEN }}
          anthropic_key_fallback: ${{ secrets.ANTHROPIC_API_KEY }}  # 服务器不可达时本地降级用
```

### 4.2 仓库审计配置（`.github/doc-audit.yml`）

```yaml
# 一份配置可声明多个 target，每个 target 独立配置维度与门槛
targets:
  - name: cips
    paths:
      - refs/cips/**
      - refs/whitepaper/**
    glossary: refs/glossary.md
    related_code:
      - node/
      - runner/
    dimensions:
      consistency:    { enabled: true,  severity_gate: block }
      security:       { enabled: true,  severity_gate: warn }
      technical:      { enabled: true,  severity_gate: warn }
      architecture:   { enabled: true,  severity_gate: warn }
      style:          { enabled: false }

  - name: user-docs
    paths:
      - docs/user/**
    dimensions:
      consistency: { enabled: true, severity_gate: warn }
      style:       { enabled: true, severity_gate: warn }

global:
  max_usd_per_run: 2.00
  comment_marker: doc-audit-bot
  ignore_file: .doc-audit-ignore   # 列出 finding-id，逐次审计跳过

```

`severity_gate` 的取值：
- `block` —— 该维度发现 ≥`block` 严重度时让 Check 失败、阻断合并
- `warn` —— 该维度发现仅展示，不阻断
- `off` —— 该维度的发现不展示（同 `enabled: false`）

### 4.3 路径过滤逻辑

Action 启动时计算 `git diff --name-only base..head`，对每个 target：
- 若 target.paths 与 changed_files 无交集 → 跳过该 target
- 全部 target 都跳过 → action 短路成功退出，不调用服务器，不发评论

## 5. 审计维度

### 5.1 维度对照表

| 维度 | 实现方式 | Pass | 输出严重度上限 | 主要产物 |
|---|---|---|---|---|
| 一致性 | 规则 + LLM | rules + semantic | block | 资源冲突、悬空引用、跨文档矛盾 |
| 安全性 | 规则 + LLM | rules + semantic | block | 敏感信息、危险建议、权限漏洞 |
| 技术可行性 | LLM | semantic | warn | 文档描述与代码不符 |
| 架构可行性 | LLM | semantic | warn | 违背架构原则、循环依赖 |
| 风格 / 术语 | 规则（首选） + LLM | rules + semantic | warn | 术语漂移、链接失效 |

### 5.2 一致性维度

完整继承既有 CIP Bot 的规则集（R001-R006）作为初始集合，扩展规则可加：

| ID | 规则 | 严重度 | 描述 |
|---|---|---|---|
| R001 | `opcode_collision` | block | 新增 opcode 与已存在冲突 |
| R002 | `address_collision` | block | 系统 actor 地址冲突 |
| R003 | `opcode_without_wp_update` | block | 改 opcode 未同步白皮书 §9.2 |
| R004 | `dangling_xref` | block | 交叉引用悬空 |
| R005 | `cip_number_collision` | block | CIP 编号冲突 |
| R006 | `status_regression` | block | CIP 状态倒退 |
| R007 | `terminology_drift` | warn | 术语在不同文档定义不一致 |
| R008 | `link_rot` | warn | 内部链接失效 |
| R009 | `constant_value_mismatch` | block | 同一常量在不同文档值不同 |

LLM 补充检查：跨文档语义矛盾（"timer X 允许" vs "禁止"）、参数默认值漂移、版本号叙述不一致。

### 5.3 安全性维度

**三层叠加（外部信号 + 规则 + LLM）：**

**第一层 — 第三方信号融合：**
- 拉取 GitHub 自带 Secret Scanning 在该 PR 上的 alert（通过 `secret_scanning_alerts` API）
- 拉取仓库已配置的其他扫描器结果（如 gitleaks、trufflehog 的 SARIF 产物）
- 这些 finding 直接归并到本维度输出，标记 `source: external`，归到对应 `locations[]`

**第二层 — 规则 pass（覆盖第三方未覆盖的文档专属场景）：**
- 正则匹配 markdown 代码块中常见 secret 格式（API key、private key、JWT、AWS credential）—— 注意 Secret Scanning 主要扫已 commit 的代码文件，对 markdown 代码块覆盖较弱
- 检查代码块中的危险命令（`rm -rf /`、`chmod 777`、`curl | bash`）

**第三层 — LLM pass 的 prompt 不变量：**
1. 不重复前两层已报的 finding（前两层结果作为输入喂给 agent 去重）
2. 只关注本 PR 改动行附近的内容
3. 重点检测：示例代码中的硬编码凭证、文档建议读者执行的危险操作、权限放宽建议（"为简化测试，关闭鉴权"）、对密钥/token 的不安全处理
4. 每条发现必须包含 `locations[]` 与简短威胁说明
5. 不评估"理论安全风险"——只报告文档中明确给出的不安全做法

**为什么三层叠加（取自 Almanax 的经验）：** 让 LLM 聚焦在它真正擅长的语义层（"权限放宽建议"这类规则难写的场景），把 secret 模式匹配这类已经有成熟工具的部分让出去。降噪 + 省钱。

### 5.4 技术可行性维度

**输入：** 改动文档 + 配置中 `related_code` 声明的代码目录 + 服务器侧 `code_index`（§6.2）

**两阶段实现（精确为主、LLM 兜底）：**

**阶段 A — 基于代码符号索引的精确比对（处理 80% 场景）：**
1. 从 `index_head.json` 的 `code_symbols_referenced` 字段拿到本次文档变更中提到的所有代码符号（函数名、常量名、文件路径）
2. 在服务器侧 `code_index` 中查存在性、查实际值、查签名
3. 比对结果直接产出 finding，**不调 LLM**：
   - 符号不存在 → `T001_symbol_not_found` (block)
   - 常量值不一致 → `T002_constant_mismatch` (block)
   - 文件路径不存在 → `T003_path_not_found` (warn)
   - API 签名不匹配 → `T004_signature_mismatch` (warn)

**阶段 B — LLM pass（仅处理阶段 A 覆盖不到的语义比对）：**
- 输入：阶段 A 的 finding 列表 + 改动文档 + `code_index` 检索结果
- 关注：API 返回结构语义、文档描述的行为是否与代码逻辑一致、含糊技术声明的合理性核对
- prompt 不变量：
  1. 不重复阶段 A 已报的 finding
  2. 仅在文档明确做出技术声明时才评估；含糊描述（"高效"、"快速"）不评
  3. 每条 finding 必须引用 `code_index` 检索到的具体代码位置

工具：允许 `Read`（仅限服务器已 fetch 的代码片段）、`code_index_query`；禁止网络访问与写操作。

**为什么这样分阶段（取自 Almanax 的经验教训）：** 让 LLM 现场用 Grep 探索代码，在跨文件场景下表现差（Almanax 实测约 15% 命中）。改用预建的符号索引做精确查找，把 LLM 留给真正需要语义理解的部分。

### 5.5 架构可行性维度

**输入：** 改动文档 + 仓库内已有架构原则（`ARCHITECTURE.md`、设计文档目录）

**LLM pass 的 prompt 不变量：**
1. 提取本次改动隐含的新架构约束（新依赖、新边界、新接口契约）
2. 与已有架构原则比对，找出冲突
3. 检测潜在的循环依赖、违反分层、破坏既有 invariant
4. 每条发现必须引用：本次改动的具体段落 + 被违背的架构文档段落

### 5.6 风格 / 术语维度

**规则 pass：**
- 链接 HEAD 检查（避免 link rot）
- markdownlint 兼容输出（如果仓库已有 markdownlint 配置则复用）
- 术语表（glossary）中关键词的拼写一致性

**LLM pass 仅在规则 pass 之外检测：** 同一概念多个表达（"Actor" vs "actor" vs "智能体"）。

## 6. 组件细节

### 6.1 Action 端组件

#### `extract_index.py`
继承既有设计 §4.1，扩展点：
- 支持多 target 配置，输出 `index_<target_name>_<base|head>.json`
- 索引 schema 增加 `dimension_inputs` 字段，预先抽取各维度需要的辅助数据（如安全维度需要的"代码块清单"、技术维度需要的"代码符号引用"）

#### `diff.py`
继承既有设计 §4.2，无变化。

#### `rules.py`
继承既有设计 §4.3，扩展点：
- 规则按维度归组：`rules/consistency/`、`rules/security/`、`rules/style/`
- 每条规则声明 `dimension` 字段，输出时按维度归类
- 注册机制不变：加一个函数 + 装饰器，无需改其他代码

#### `dispatch.py`（新）
**职责：** 把 `index_head.json`、`diff.json`、`changed_files`、配置切片打包，POST 到服务器。

**请求体（schema 见 §7.3）：**
```json
{
  "request_id": "<uuid>",
  "repo": {"owner": "...", "name": "...", "default_branch": "main"},
  "pr": {"number": 123, "base_sha": "...", "head_sha": "..."},
  "target": {"name": "cips", "config": { ... }},
  "payload": {
    "index_head": { ... },
    "diff": { ... },
    "changed_files": ["..."],
    "rules_findings": [ ... ],
    "documents": {
      "docs/cips/cip-29-...": "...full content...",
      ...
    }
  },
  "budget_remaining_usd": 1.85
}
```

**关键决定：**
- **文档全文随请求走** —— 服务器不去 clone 仓库，避免给服务器 GitHub 凭证。代价是请求体可能 MB 级，可接受（gzip + HTTP/2）。
- 单次请求超过 10MB 时，分维度多次请求。
- 请求超时 5 分钟，失败重试 1 次（指数退避）。
- 失败后回退到 `claude -p` 本地降级（如果配置了 `anthropic_key_fallback`）。

#### `aggregate.py`（新）
**职责：** 合并 rules + 各维度 semantic 发现，校验 LLM 发现的 `file:line`，去重，排序，定级。

**步骤：**
1. 加载 `findings_rules.json` + 服务器返回的所有维度 `findings_semantic_*.json`
2. 对每条语义发现：检查 `locations[].file` 在 head SHA 下存在、`line` ≤ 文件行数；不通过即丢弃
3. 若任一维度丢弃比例 >30%，将该维度整体降级为 "低置信度"
4. 跨维度去重（同一 `file:line` 被多个维度命中时，保留最高严重度的，其余作为"相关发现"挂在主条目下）
5. 按 (severity, file, line) 排序

#### `report.py`
继承既有设计 §4.5，扩展点：
- 多维度分组渲染（每个维度独立段落）
- Check Run 按维度配置的 `severity_gate` 决定单 Check 的 conclusion；多个 Check（每维度一个）
- Annotations 上限 50 条 / Check，超出走 PR review comments
- Sticky PR comment 用统一 marker `<!-- doc-audit-bot -->` 识别旧评论 edit-last
- SARIF 输出（按维度分文件）

### 6.2 服务器端组件

#### API 接口

```
POST /v1/audit
  body: <§7.3 请求 schema>
  auth: Bearer <repo_token>
  → 200 with <§7.4 响应 schema>
  → 503 with degraded reason  (LLM provider 不可用 / 预算耗尽)

GET /v1/audit/{request_id}
  → 查询历史审计结果（用于 PR 评论里的"查看完整日志"链接）

GET /v1/health
  → liveness + 各 provider 状态

GET /v1/budget/{repo}
  → 当月剩余预算
```

#### Orchestrator
**职责：** 把请求按维度分解为多个 agent 调用，并行执行，汇总结果。

```python
async def orchestrate(req: AuditRequest) -> AuditResponse:
    enabled_dims = [d for d in req.target.dimensions if d.enabled]
    corpus_cache_key = compute_cache_key(req.payload.documents)
    
    # 关键优化：所有维度共享同一个 prompt cache 块
    # —— 把 documents 打包为一个 cached system prompt，供 5 个 agent 复用
    
    tasks = [
        run_agent(dim, req, corpus_cache_key)
        for dim in enabled_dims
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return aggregate(results, req)
```

#### Dimension Agents
每个维度一个独立模块（`agents/consistency.py`、`agents/security.py` ...），实现统一接口：

```python
class DimensionAgent(Protocol):
    name: str
    
    async def run(
        self,
        request: AuditRequest,
        corpus_cache_block: CachedBlock,
    ) -> list[Finding]: ...
```

每个 agent 内部用 Anthropic SDK 直接调 Claude，**而不是** shell out 到 `claude -p`：
- 服务器端可以更精细地控制 prompt cache、tool use、token 计数
- Agent 可以做多步推理（先用 Grep 找证据，再做判断），在服务器侧的 token 流式控制更可靠
- 失败重试、降级策略集中

每个 agent 必须遵守的不变量：
1. 输出严格匹配 §7.5 的 finding schema
2. 每条 finding 必须有可校验的 `locations[]`
3. 不输出本 PR 改动范围之外的 finding
4. 不重复 rules pass 已经覆盖的硬冲突（rules findings 作为输入喂给 agent）

#### Code Index（新，服务于技术可行性维度）

**职责：** 维护接入仓库的轻量级代码符号索引，供 §5.4 阶段 A 的精确比对使用。

**索引粒度：**
- 文件级：路径 + 最后 commit SHA
- 符号级：函数/类/常量名 + 定义位置（file:line）+ 签名/值
- 引用级：符号被哪些文件引用

**实现选型：**
- 解析器：[tree-sitter](https://tree-sitter.github.io/) 多语言支持，对 Rust / Python / TypeScript / Go 都有现成 grammar
- 存储：Postgres 单表 `(repo, ref_sha, symbol_name, kind, file, line_start, line_end, signature, value)`，加 GIN 索引

**更新策略：**
- 首次接入仓库 → 全量索引（异步任务，可能数十分钟）
- 后续 push → 增量更新（仅重新解析改动文件 + 受影响的引用）
- PR 触发审计时：
  - 若 head SHA 已索引 → 直接查
  - 若未索引 → 同步快速增量（基于 diff 中变更的代码文件），最多等 30 秒
  - 超时 → 该维度降级为"仅 LLM pass"

**查询接口（供 dimension agent 用）：**
```python
class CodeIndex(Protocol):
    def get_symbol(self, repo: str, ref: str, name: str) -> Symbol | None: ...
    def get_constant_value(self, repo: str, ref: str, name: str) -> str | None: ...
    def get_signature(self, repo: str, ref: str, name: str) -> Signature | None: ...
    def file_exists(self, repo: str, ref: str, path: str) -> bool: ...
```

**关键设计决定：** code_index 的代码内容是 Action 端在 dispatch 时上传的（`related_code_excerpts` 字段），服务器**不主动 clone 仓库**——保持服务器无 GitHub 凭证的边界。代价是首次接入时需要 Action 跑一次"全量索引上传"工作流。

#### Dedup Agent（新，跨 PR 语义去重）

**职责：** 识别本次 PR 的 finding 是否与历史 finding 本质相同，把"新发生"和"重复发生"区分开。

**为什么需要：** 既有 `finding_id` 哈希只能去重字面相同的 finding。同一本质问题在不同 PR 里 message 措辞略有差异就会被当成新 finding，开发者会觉得"怎么反复在报同一件事"。

**算法（取自 Almanax 的 G-Eval 改造）：**
1. 对每条新 finding，从审计历史 PG 库拉取近 90 天该仓库内**同一 dimension + 同一 file 路径**的 finding 候选集
2. 用 LLM 做 chain-of-thought 比对，输出 `[similar, different, ambiguous]` 三类
3. 同时取该判断的 token log probability，转换为 0-1 的置信度
4. 置信度 >0.8 且判定为 `similar` → 标记为"重复发生"，复用旧 `finding_id`，累计 `historical_occurrences`
5. 其余作为新 finding

**输出（写回 finding 上）：**
- `historical_occurrences: int`（含本次）
- `first_seen_pr: int`、`first_seen_at: timestamp`
- `dedup_confidence: float`

**成本控制：** dedup 调用模型用更便宜的 Haiku（足够做相似度判断），单 PR 成本通常 <$0.01。

**降级：** dedup 失败不影响主流程，finding 按"新"处理。

#### 缓存层（Redis）

| Key | Value | TTL | 用途 |
|---|---|---|---|
| `index:<repo>:<sha>` | `index.json` | 7 天 | base ref 的索引跨 PR 复用 |
| `code_index:<repo>:<sha>:<symbol>` | Symbol 查询结果 | 7 天 | code_index 热查询缓存 |
| `corpus_cache:<hash(documents)>` | Anthropic prompt cache breakpoint | 5 分钟（Anthropic 上限） | 跨维度复用 |
| `audit_result:<request_id>` | `AuditResponse` | 30 天 | 历史查询、相同请求去重 |
| `negative:<hash(diff)>` | "no findings" | 1 天 | 同样的 diff 不重复跑 |
| `dedup:<finding_signature>` | dedup_agent 判定结果 | 7 天 | 同一签名的 finding 反复出现时复用判定 |

#### 预算账本

每仓库（或每 GitHub org）维护一个月度预算。每次审计完成后写入：
```json
{
  "request_id": "...",
  "repo": "owner/name",
  "pr": 123,
  "timestamp": "2026-05-15T10:23:00Z",
  "tokens_input": 12500,
  "tokens_output": 800,
  "tokens_cached_read": 38000,
  "cost_usd": 0.045,
  "duration_ms": 18500,
  "dimensions_run": ["consistency", "security", "technical"]
}
```

预算超限时：
- 软上限（80%）—— 邮件 / Slack 通知接入方管理员
- 硬上限（100%）—— 服务器返回 503，Action 仅出 rules 报告并在 PR 评论顶部说明

#### 审计历史（PostgreSQL）
存储每次审计的请求 / 响应快照。用途：
- PR 评论中"查看完整日志"链接
- 跨 PR 漂移分析（"某术语在过去 3 次 PR 都被标过不一致"）
- 误报反馈：开发者通过 `/audit ignore <finding-id>` 标记后写入此表，下次 audit 跳过同模式

### 6.3 鉴权

| 通道 | 方式 |
|---|---|
| Action → 服务器 | Bearer token，服务器侧按 `(token, repo_full_name)` 双因子校验，token 与仓库绑定 |
| 服务器 → Anthropic | 服务器侧持有的 Anthropic API key，per-org 隔离不同 key（可选） |
| 仓库管理员 → 服务器（管理 API） | 独立的 admin token，受 IP 白名单约束 |

token 通过控制台手动签发，写入仓库的 `secrets.DOC_AUDIT_TOKEN`。

### 6.4 部署形态

最小部署：单机 Docker Compose
```
services:
  api:        FastAPI / Uvicorn (服务器主体)
  redis:      缓存
  postgres:   审计历史 + 预算账本
  worker:     后台任务（异步通知、报表）
```

水平扩展：
- API 无状态，可放 ALB 后多实例
- Worker 走 Redis queue
- Postgres 单主即可（写入量低）

## 7. 数据 Schema

### 7.1 工作区布局（Action 侧）

```
$RUNNER_TEMP/doc-audit/
  config.resolved.json
  index_<target>_base.json
  index_<target>_head.json
  diff_<target>.json
  findings_rules_<target>.json
  findings_semantic_<target>_<dimension>.json
  findings_aggregated.json
  report.md
  doc-audit.sarif        （可选）
  dispatch_request.json  （调试，含敏感数据，仅 artifact，不打印日志）
  dispatch_response.json （调试）
```

artifact 名称：`doc-audit-<run-id>`，retention 默认 7 天。

### 7.2 `index.json`（继承 + 扩展）

```json
{
  "ref": "main | <sha>",
  "target": "cips",
  "opcodes":   [{"id": 48, "name": "...", "file": "...", "line": 1234, "cip_refs": ["CIP-5"]}],
  "addresses": [{"id": "0x01", "name": "...", "file": "...", "line": 1500}],
  "errors":    [{"code": "ERR_TIMER_EXPIRED", "file": "...", "line": 800}],
  "cips":      [{"id": 5, "title": "...", "status": "Final", "file": "...", "anchors": ["§3.1"]}],
  "xrefs":     [{"from": "CIP-9", "to": "CIP-5 §3.1", "file": "...", "line": 220}],
  "terms":     [{"term": "fee_payer", "definition_file": "...", "line": 410}],
  "code_blocks": [{"file": "...", "line": 100, "lang": "bash", "content_hash": "..."}],
  "code_symbols_referenced": [{"symbol": "ExecutionEngine::set_basefee", "file": "...", "line": 250}]
}
```

### 7.3 审计请求 Schema（Action → 服务器）

```json
{
  "schema_version": "1",
  "request_id": "uuid-v4",
  "repo": {
    "owner": "string",
    "name": "string",
    "default_branch": "string"
  },
  "pr": {
    "number": 123,
    "title": "string",
    "base_sha": "string",
    "head_sha": "string",
    "is_draft": false,
    "is_fork": false
  },
  "target": {
    "name": "cips",
    "paths": ["..."],
    "dimensions": {"consistency": {...}, "security": {...}}
  },
  "payload": {
    "index_head": { ... },
    "diff": { ... },
    "changed_files": ["..."],
    "rules_findings": [ ... ],
    "documents": {
      "<file_path>": {
        "content": "...full content...",
        "sha": "blob-sha"
      }
    },
    "related_code_excerpts": {
      "<file_path>": "..."
    }
  },
  "budget_hint": {
    "max_usd": 2.00,
    "max_duration_seconds": 240
  },
  "client_version": "doc-audit-action@v1.2.3"
}
```

### 7.4 审计响应 Schema（服务器 → Action）

```json
{
  "schema_version": "1",
  "request_id": "uuid-v4",
  "status": "ok | partial | degraded | failed",
  "findings_by_dimension": {
    "consistency": [<finding>, ...],
    "security": [<finding>, ...],
    ...
  },
  "dimension_status": {
    "consistency": {"status": "ok", "duration_ms": 3200, "cost_usd": 0.012},
    "security":    {"status": "degraded", "reason": "anthropic_timeout"},
    ...
  },
  "totals": {
    "tokens_input": 12500,
    "tokens_output": 800,
    "tokens_cached_read": 38000,
    "cost_usd": 0.045,
    "duration_ms": 18500
  },
  "remaining_budget_usd": 1.84,
  "view_url": "https://audit.your-org.com/runs/<request_id>"
}
```

### 7.5 Finding Schema（继承 + 扩展）

```json
{
  "finding_id": "stable-hash",
  "rule_id": "R001_opcode_collision",
  "source": "rules | semantic | external",
  "external_provider": "github_secret_scanning | gitleaks | null",
  "dimension": "consistency | security | technical | architecture | style",
  "severity": "block | warn | info",
  "title": "Opcode 0x42 与 CIP-5 冲突",
  "locations": [
    {"file": "...", "line_start": 87, "line_end": 87, "anchor": "§3.2"}
  ],
  "evidence": "CIP-29 第 87 行新增 0x42；白皮书 §9.2 已分配 0x42 给 SYS_FOO",
  "message": "...",
  "suggestion": "按 WP §9.2 取下一个空闲位（当前为 0x4F）",
  "related_findings": ["finding_id_1", "finding_id_2"],
  "confidence": 0.95,
  "agent_meta": {
    "model": "claude-opus-4-7",
    "tokens": 1500
  },
  "history": {
    "historical_occurrences": 3,
    "first_seen_pr": 87,
    "first_seen_at": "2026-04-22T08:15:00Z",
    "dedup_confidence": 0.92,
    "dedup_method": "g_eval | hash | none"
  }
}
```

**字段语义：**
- `finding_id` —— 由 `(rule_id, dimension, locations[0].file, locations[0].line_start, hash(message))` 计算得出。本质相同但措辞不同的 finding 经 §6.2 dedup_agent 判定后，会**复用旧的 finding_id**，让历史可追踪。
- `source: external` —— 来自第三方扫描器（如 GitHub Secret Scanning），`external_provider` 标识来源
- `history.historical_occurrences` —— 含本次的累计出现次数；用于在 PR 评论里展示"该问题已在过去 N 个 PR 出现"，提示开发者这是反复发生的模式
- `history.dedup_method` —— `hash` 表示字面去重，`g_eval` 表示语义去重，`none` 表示首次出现

## 8. GitHub 展示层

### 8.1 三层展示

| 层 | API | 内容 | 触发条件 |
|---|---|---|---|
| Check Run | Checks API | 总览状态 + 每维度通过 / 失败 + 关键 finding 摘要 + token 用量 | 每次审计 |
| Annotations | Checks API（annotations 字段） | 行内标注（最多 50 条 / Check） | 有 finding 且能映射到 PR diff |
| Sticky PR Comment | Issues API | 完整结构化报告 + 历史对比 + 操作命令说明 | 每次审计，用 marker 原地更新 |
| SARIF | Code Scanning API | 跨 PR 持久化的漏洞跟踪 | `enable_sarif: true` 时 |

### 8.2 Check Run 设计

每个维度一个独立 Check Run（`Doc Audit / Consistency`、`Doc Audit / Security` ...），便于：
- 独立配置 branch protection（"`Doc Audit / Consistency` 必须通过才能合并"）
- 用户可针对单维度 re-run
- 失败原因清晰归属到维度

Summary 模板：
```markdown
## 一致性维度 — ❌ 阻断

| 严重度 | 计数 |
|--------|------|
| block  | 2    |
| warn   | 5    |

### 关键发现
- **R001** Opcode 0x42 与 CIP-5 冲突 — `cip-29.md:87`
- **R003** 修改 opcode 但未同步白皮书 — `cip-29.md:120`

[查看完整报告](https://audit.your-org.com/runs/...)
```

### 8.3 Sticky PR Comment 模板

```markdown
<!-- doc-audit-bot -->
## 📋 文档审计报告

**总览：** 2 block, 7 warn, 3 info  
**对比上次：** +1 block, -2 warn  
**预算：** $0.045 / $2.00（剩余 $1.84）

<details>
<summary>🔴 一致性 — 2 block, 3 warn</summary>

### R001 Opcode 0x42 与 CIP-5 冲突 — `block`
**位置：** `docs/cips/cip-29.md:87` `docs/whitepaper/wp.md:1502`  
**证据：** ...  
**建议：** ...

### R007 术语 "fee_payer" 在 CIP-9 与 CIP-12 定义不一致 — `warn`  ⚠️ 第 4 次出现
**位置：** `docs/cips/cip-12.md:88`  
**首次发现：** PR #87（2026-04-22）  
**说明：** 该问题已在过去 3 个 PR 出现并被忽略，建议本次彻底解决或在 `.doc-audit-ignore` 中加注理由。

</details>

<details>
<summary>🟡 安全性 — 0 block, 2 warn</summary>

包含 1 条来自 GitHub Secret Scanning 的 finding（`source: external`）
...
</details>

---
**操作：**
- `/audit rerun` — 重跑审计
- `/audit rerun consistency` — 仅重跑某维度
- `/audit ignore <finding-id>` — 永久忽略某条 finding（需仓库写权限）
- `/audit explain <finding-id>` — 让 bot 详细解释某条发现
```

### 8.4 PR 命令交互

通过监听 `issue_comment` event 实现（额外的 workflow，复用同一 action）：

| 命令 | 行为 |
|---|---|
| `/audit rerun [<dim>]` | 触发重跑（指定维度则只跑该维度） |
| `/audit ignore <finding-id>` | 写入 `.doc-audit-ignore`，下次跳过 |
| `/audit explain <finding-id>` | 服务器调 LLM 给详细解释，回复评论 |
| `/audit budget` | 查询当月剩余预算 |

`/audit ignore` 需要 PR 作者或 reviewer 触发；权限校验通过 GitHub API 完成。

## 9. 错误处理与降级

继承既有设计 §6 全部条目，扩展：

| 失败场景 | 行为 |
|---|---|
| 服务器 503 / 网络超时 | Action 仅基于 rules 出报告；PR 评论顶部说明"语义检查降级"。**不**让 action 失败。 |
| 服务器 503 + `anthropic_key_fallback` 已配置 | 退回既有 CIP Bot 的 `claude -p` 本地路径 |
| 单维度 LLM 调用失败 | 该维度标 `degraded`，其他维度照常出报告 |
| 服务器返回的 finding 校验失败 | 丢弃（同既有设计 §6） |
| 预算耗尽 | 服务器拒绝新请求，Action 仅出 rules 报告 |
| Action 重复触发同一 SHA（`synchronize` 抖动） | 服务器侧用 `negative cache` + `audit_result:<request_id>` 去重，5 分钟内同 SHA 直接返回缓存结果 |
| 单文档超过 corpus cache 上限 | 分块、按文档级别 partial cache；记 `partial_cache_hit` metric |
| Fork PR 拿不到 secret | 用 `pull_request_target` + 显式 PR head checkout + 收窄 `permissions`；服务器 token 不可用时仅跑 rules |
| 同一 PR 反复 push | sticky comment 原地更新，audit_result 缓存命中减少重复消耗 |
| 服务器宕机持续 >1 小时 | Action 触发降级路径自动开启；监控告警接入方运维 |
| LLM 输出非合法 JSON | retry 1 次（temperature 0），仍失败则该维度 `degraded` |

## 10. 安全

### 10.1 威胁模型

| 威胁 | 缓解 |
|---|---|
| 恶意 PR 注入 prompt 让 LLM 输出虚假 finding | LLM 输出严格 schema 校验 + `locations` 反向校验，无效 finding 丢弃 |
| 恶意 PR 让 LLM 调外部资源 | Agent 工具白名单（`Read`、`Grep`、只读 `Bash`），不允许网络访问 |
| Fork PR 偷服务器 token | `pull_request` 事件下 fork PR 拿不到 secrets；用 `pull_request_target` 时显式不向 fork 暴露 token |
| 服务器 token 泄露 | token 与仓库绑定，泄露后只能审计该仓库；可立即 revoke 重发 |
| 服务器侧文档内容泄露 | 文档内容仅在请求生命周期内驻留内存；`audit_result` 缓存中的 finding 不含文档全文 |
| LLM 训练数据泄露 | 与 Anthropic 走 zero-retention 协议（如可获得） |

### 10.2 Webhook 签名（如未来引入 GitHub App）
本设计不需要 webhook（Action 主动 POST 到服务器）。如果未来加 GitHub App 直连，强制 HMAC 校验 `X-Hub-Signature-256`。

### 10.3 服务器端 PII

文档可能含有：内部仓库路径、内部人名邮箱、未发布的功能描述。
- 不向第三方监控系统（如 Sentry）发送文档内容；只发摘要 + 错误类型
- 审计历史的 PG 库做 at-rest 加密
- 30 天后自动清理 `audit_result` 中的文档全文（保留 finding 摘要）

## 11. 成本与性能

### 11.1 单次 PR 成本目标

| 场景 | 目标 |
|---|---|
| 仅触发 rules（小改动） | <$0.001（无 LLM 调用） |
| 触发 1 个维度 LLM | <$0.10 |
| 触发全部 5 个维度 LLM | <$0.50 |
| 硬上限（`max_usd_per_run`） | $2.00 |

### 11.2 关键优化

1. **跨维度 prompt cache** —— 文档语料一次写入 cache，5 个维度复用，理论上节省 4× input token（实际看维度间 prompt 模板差异）
2. **跨 PR 索引缓存** —— base ref 的 `index.json` 按 SHA 缓存 7 天，命中时跳过 base 索引抽取
3. **negative cache** —— 同一 diff 1 天内不重复跑（开发者反复 force-push 同一变更时省钱）
4. **维度独立超时** —— 单维度超时不拖累其他维度；并行执行
5. **早终止** —— rules pass 已发现 ≥10 条 block 时跳过 LLM pass（语义 finding 价值已被淹没）
6. **code_index 精确比对优先于 LLM** —— 技术可行性维度的阶段 A 命中率越高，阶段 B 的 LLM 调用就越短（context 更小、目标更明确）。预期可降低该维度 60% 的 token 消耗
7. **dedup_agent 用 Haiku 而非 Opus** —— 相似度判断不需要旗舰模型，单 PR 去重成本控制在 $0.01 内
8. **第三方扫描器结果直接归并** —— Secret Scanning / gitleaks 的 finding 不调 LLM，零成本

### 11.3 性能门槛

| 场景 | 门槛 |
|---|---|
| 仅 rules（小改动） | <30 秒 |
| 单维度 LLM | <90 秒 |
| 全维度并行 | <5 分钟 |
| Action 端冷启动 + 抽索引 | <60 秒 |

性能门槛在 selftest workflow 通过超时断言强制。

## 12. 测试策略

### 12.1 Action 端单元测试
- `extract_index.py` —— 每种结构化资源准备 fixture（继承既有设计 §7.1）
- `rules.py` —— 每条规则 1 正例 + 1 反例
- `dispatch.py` —— mock 服务器响应，验证降级路径
- `aggregate.py` —— `locations` 校验、跨维度去重、严重度归并
- `report.py` —— Markdown / SARIF snapshot

### 12.2 服务器端单元测试
- 每个 dimension agent 独立测试，使用录制的 Anthropic 响应（VCR-style）
- Orchestrator 测试：维度并发、单维度失败不影响其他维度
- 预算账本：并发写入正确性
- 缓存层：TTL、key 冲突、命中率

### 12.3 集成测试
继承既有设计 §7.2 五个 "黄金 PR"，扩展：
6. 安全维度命中（PR 在示例代码中加了硬编码 API key）
7. 技术可行性命中（PR 文档里的常量值与代码不一致）
8. 架构可行性命中（PR 引入与现有架构原则冲突的设计）
9. 服务器宕机降级路径（mock 服务器 503，验证 Action 仅出 rules 报告）
10. 多维度 + ignore 文件（验证 `.doc-audit-ignore` 跳过指定 finding）

### 12.4 端到端 selftest
`.github/workflows/doc-audit-selftest.yml`：
- 每日跑一次本仓库的 dogfood PR
- 周期性回归：所有 fixture 对真实 LLM 跑一次（阈值监控误报率）

### 12.5 LLM 回归
- CI 不跑真实 LLM；服务器侧测试用录制 fixture
- 真 LLM 冒烟测试每周 cron，结果作为报告，不阻塞 CI
- 模型升级时（Claude 4.7 → 下一版）必须重跑全量回归 + 人工抽样

## 13. 部署

### 13.1 服务器侧

最小化部署（v1）：
```bash
docker compose up -d
# api / redis / postgres / worker
```

环境变量：
```
ANTHROPIC_API_KEY=...
DATABASE_URL=postgres://...
REDIS_URL=redis://...
SERVER_BASE_URL=https://audit.your-org.com
LOG_LEVEL=info
DEFAULT_MAX_USD_PER_RUN=2.00
```

监控：
- `/metrics` Prometheus endpoint
- 关键指标：QPS、p95 延迟、各维度错误率、token 消耗、预算使用率

### 13.2 接入方仓库

1. 仓库管理员通过控制台申请 token，写入 `secrets.DOC_AUDIT_TOKEN`
2. 拷贝 `.github/workflows/doc-audit.yml` 模板
3. 创建 `.github/doc-audit.yml` 配置
4. （可选）在 branch protection 中要求 `Doc Audit / *` 必须通过

### 13.3 Action 发布

`your-org/doc-audit-action` 独立仓库，用 git tag 发版（`v1.0.0`、`v1`）。重大破坏性变更走 `v2`。

## 14. 监控与运营

### 14.1 服务器侧仪表板

| 维度 | 指标 |
|---|---|
| 健康度 | API 可用率、p95/p99 延迟、错误率 |
| 用量 | 每仓库 / 每 org QPS、token 消耗、成本 |
| 质量 | 各维度的 finding 数分布、误报反馈数（来自 `/audit ignore`）、`degraded` 比率 |
| 缓存 | 索引缓存命中率、prompt cache 命中率 |

### 14.2 接入方报表
按月发送邮件/Slack：
- 当月审计次数、阻断 PR 数、关键 finding 类别 top-10
- 当月成本、剩余预算
- 各维度 `/audit ignore` 数（暗示规则可能需要调整）

### 14.3 误报治理
- 每周从 `/audit ignore` 表中导出反馈，人工 review
- 误报率高的规则降级（block → warn）或下线
- 漏报跟踪：维护一个 "应该被发现但没被发现" 的 fixture 集合，每月跑一次

## 15. 上线计划

| 阶段 | 范围 | 时长 |
|---|---|---|
| 0 | 基于既有 CIP Bot 设计，跑通 Action-only 路径（一致性维度） | 2 周 |
| 1 | 服务器骨架（FastAPI + 一致性维度 agent）+ Action `dispatch.py` | 2 周 |
| 2 | 安全维度（含第三方信号融合：Secret Scanning / gitleaks）+ 缓存 + 预算 | 2 周 |
| 3 | `code_index` 服务 + 技术可行性维度（阶段 A 精确比对）+ 架构维度 | 3 周 |
| 4 | `dedup_agent`（G-Eval 风格语义去重）+ Finding 历史展示 | 2 周 |
| 5 | Sticky comment + Annotations + PR 命令交互 | 1 周 |
| 6 | 在本仓库 dogfood 2 周（warn-only） | 2 周 |
| 7 | 一致性维度切到 block；其他维度保持 warn | — |
| 8 | 第二个接入仓库 | — |
| 9 | SARIF 输出、跨 PR 漂移分析、自动报表 | 后续迭代 |

每阶段交付物：可运行 + 测试覆盖率 ≥80% + 文档更新。

## 16. 开放问题

1. **是否引入 GitHub App 直连？** v1 走 Action POST 服务器，避免运营 webhook。如果未来出现"PR 之外的触发场景"（比如 push 到 main 后做事后审计），再加 App。
2. **是否做 in-PR override？** 既有 CIP Bot 设计明确不做（§6），本设计沿用。如果误报率高到影响开发者体验，再考虑加 `/audit override <finding-id> <reason>` 命令（写入审计日志而非屏蔽）。
3. **是否支持自定义 agent？** 接入方提供自己的 prompt + 工具集。v1 不支持，等出现第二个明确需求再做。
4. **是否提供 Web 控制台？** v1 仅 `view_url` 展示单次审计详情；管理控制台（仓库列表、token 管理、预算配置）在阶段 7 后做。
5. **是否做与既有 `cip-todo.md` 的双向同步？** 同既有设计 §9，多半应做，但 v1 不做。
6. **多语言文档**（中英文双版本）**漂移检测？** 同既有设计明确不做。如果接入方需要，作为独立维度（`bilingual`）后续加。

## 17. 与既有 CIP Bot 设计的迁移路径

既有设计是本设计的真子集。迁移分两步：

**第一步（无服务器，纯增强）：** 把既有 CIP Bot 的 `semantic.py` prompt 拆成"按维度的 prompt 集合"，让 Action 内的 `claude -p` 顺序跑多个维度。这一步不需要服务器，已经能把审计维度从"一致性"扩展到"一致性 + 安全 + 技术"。

**第二步（引入服务器）：** 当出现以下任一信号时切换：
- 接入第二个仓库
- 单 PR 成本经常触及 `MAX_USD_PER_RUN`
- 想做跨 PR 漂移分析
- 想做误报治理（需要历史数据）

切换路径：把现有 `semantic.py` 整体搬到服务器侧的某个 agent，Action 端用 `dispatch.py` 替换原地的 `claude -p` 调用。其他所有脚本（`extract_index.py`、`diff.py`、`rules.py`、`report.py`）零改动。

---

**附：本设计未覆盖的内容**
- 具体的 agent prompt 全文（在 `agents/<dim>/prompt.md` 中维护，按 PR 评审）
- 服务器侧 API 详细 OpenAPI spec（在 `docs/api.yaml` 中生成，前端自动校验）
- 部署到 K8s 的 manifest（v1 不在范围；v2 视用量决定）
