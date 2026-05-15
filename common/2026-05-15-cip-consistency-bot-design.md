# CIP 一致性 Bot — 设计文档

**日期：** 2026-05-15
**状态：** 草案
**负责人：** 待定

## 1. 目的

当一个 pull request 修改了 CIP（`docs/cips/*.md*`）或白皮书（`docs/whitepaper/*.md`）文档时，自动检测这些改动与现有文档语料之间的冲突与不一致，将结构化的审查报告作为评论回贴到 PR，并对硬冲突阻断合并。

"冲突"涵盖三类：
1. **结构化资源冲突** —— opcode、系统 actor 地址、错误码、CIP 编号、版本号等可枚举资源的占用冲突。
2. **跨文档规则未满足** —— 例如白皮书 §9.2 收尾注释里那条硬规则（"任何新增 opcode 必须在同一 PR 内修改白皮书 §9.2"），章节交叉引用悬空、CIP 状态回退等。
3. **语义/规范性矛盾** —— 例如某 CIP 写"timer X 允许"而另一 CIP 写"禁止"；术语漂移；参数默认值不一致。

明确**不在范围内**：
- 中英文版本漂移（例如 `cip-28-cowboy-agent-banking-zh.md` 与 `cip-28-cowboy-agent-banking.md` 之间的同步）。
- 文档与代码之间的漂移（已经由 `cip-todo.md` 人工跟踪）。
- 自动生成 fix-up 分支；bot 只在 PR 评论里给文本性修改建议。

## 2. 非目标

- 取代人工审查。Bot 只是众多信号之一。
- 覆盖所有可能的不一致。规则和 LLM 启发式都覆盖不到的长尾类别仍由 `cip-todo.md` 接住。
- 充当风格 linter。这是一致性检查器，不是代码风格工具。

## 3. 架构总览

```
PR opened / synchronize
        │
        ▼
.github/workflows/cip-pr-check.yml
        │
        ▼
uses: .github/actions/cip-consistency  (composite action)
        │
        ├─ ① extract_index.py   (base ref → index_base.json)
        ├─ ② extract_index.py   (head ref → index_head.json)
        ├─ ③ diff.py            (资源级 diff → diff.json)
        ├─ ④ rules.py           (确定性规则检查 → findings_rules.json)
        ├─ ⑤ semantic.py        (shell out claude -p → findings_semantic.json)
        └─ ⑥ report.py          (PR 评论 + SARIF + exit code)
```

### 设计原则

- **规则 pass = 硬证据。** 每条发现都必须引用具体的 `file:line` 位置。硬发现可以让 check 失败（阻断合并）。
- **语义 pass = 仅供参考。** LLM 发现必须给出可验证的 `file:line` span；`report.py` 反向校验每个 span，校验失败则丢弃。语义发现只 warn，永不 block。
- **Self-contained action。** 跑在 `ubuntu-latest`，唯一的外部依赖是仓库 secret `ANTHROPIC_API_KEY`。
- **复用既有约定。** 沿用 `.github/actions/opcode-lint` 和 `.github/workflows/sync-whitepaper.yml` 的目录结构和发布风格。
- **各阶段产物落盘为 JSON 文件** —— 便于本地复现、单元测试、Actions artifact 上传。

## 4. 组件

### 4.1 `extract_index.py`
**职责：** 把指定 git ref 上的文档语料解析为结构化索引。

**输入：** 一个 git ref（`main`、`HEAD` 或任意 SHA）以及文档根 `docs/`。

**输出：** `index.json`（schema 见 §5.2）。

**抽取内容：**
- **Opcode 表** —— 主源是白皮书 §9.2；与 CIP 里出现的 `opcode 0xNN` 交叉校验。
- **系统 actor 地址表** —— 主源是白皮书 §9.1。
- **错误码 / 常量** —— 按 `ERR_*`、`SYS_*` 标识符模式匹配。
- **CIP 元数据** —— 编号、标题、状态，从 frontmatter 或标题行抽。
- **章节锚点** —— `§N.M(.K)` 引用，产出有向交叉引用图。
- **术语表** —— 尽力而为：粗体或标题中首次定义的关键词。

解析器走 markdown-aware 路线（用宽松的 markdown 解析器，而非裸 regex，以便正确处理表格和 fenced block），但对格式有缺陷的章节容错（warn 后继续）。

### 4.2 `diff.py`
**职责：** 计算 `index_base.json` 和 `index_head.json` 之间的资源级 delta。

**输出：** `diff.json`，按资源类型分组的 `added`、`removed`、`modified`，外加 `git diff --name-only` 得到的 `changed_files`。

### 4.3 `rules.py`
**职责：** 对 `diff.json` 和两份索引跑确定性检查。

**输出：** `findings_rules.json` —— 发现列表，每条形如 `{rule_id, source: "rules", severity, locations[], message, suggestion}`。

**初始规则目录：**

| ID   | 规则                          | 严重度 | 描述 |
|------|-------------------------------|--------|------|
| R001 | `opcode_collision`            | block  | HEAD 新增的 opcode 与 base 里已存在的冲突。 |
| R002 | `address_collision`           | block  | HEAD 新增的系统 actor 地址与 base 里已存在的冲突。 |
| R003 | `opcode_without_wp_update`    | block  | PR 新增/修改了 CIP 的 opcode 但没有修改白皮书 §9.2。 |
| R004 | `dangling_xref`               | block  | 交叉引用指向了在 HEAD 中不存在的章节。 |
| R005 | `cip_number_collision`        | block  | HEAD 之后两个 CIP 共用同一编号。 |
| R006 | `status_regression`           | block  | CIP 状态倒退（例如 `Final` → `Draft`）。 |

每条规则一个 Python 函数 + docstring 描述触发条件。新增规则 = 加一个函数并注册到列表 —— 无需改动其他管线代码。

### 4.4 `semantic.py`
**职责：** 检测规则覆盖不到的语义/规范性矛盾。

**输入：** `index_head.json`、`diff.json`、改动文件列表。

**机制：** shell out 到 `claude -p`（Claude Code headless），传入：
- 一个 prompt，包含 diff 摘要、HEAD 的结构化索引、改动文件列表。
- 允许的工具：`Read`、`Grep`、`Bash`（只读命令）。
- `--output-format json`。
- `--max-turns 8` 用于绑死 agent 运行时长和成本。

**Prompt 不变量（必须逐字出现在 system prompt 中）：**
1. 只报告涉及本 PR 改动章节的矛盾。
2. 每条发现 **必须** 包含 `locations[]`，至少一个 `{file, line}` 指向存在的文件。
3. 不要重复 rules pass 已经覆盖的硬冲突（rules pass 输出会一并喂给 agent 供其去重）。
4. 输出严格符合 §5.3 的 JSON schema；不确定时宁可少报。

**输出：** `findings_semantic.json`，`source: "semantic"`，severity 封顶为 `warn`。

### 4.5 `report.py`
**职责：** 合并发现、校验、渲染、发布。

**步骤：**
1. 加载两份 `findings_*.json`。
2. 对语义发现：校验 `locations[].{file,line}` 是否存在（`file` 存在于仓库，`line` ≤ 文件行数）。校验失败的整条丢弃，记录丢弃数。
3. 如果丢弃比例 >30%，将整批语义发现降级为"低置信度"，并在 PR 评论顶部加备注。
4. 按严重度分组，渲染 Markdown。
5. 通过 `gh pr comment` 发布或更新 PR 评论，用隐藏 marker `<!-- cip-consistency-bot -->` 识别旧评论并 edit-last，避免刷屏。
6. 可选写出 SARIF 给 GitHub Code Scanning（受 `sarif: true` 输入控制）。
7. 当存在任何 `block` 级发现时，以非零退出码退出。

## 5. 数据 Schema

### 5.1 工作区布局
```
$RUNNER_TEMP/cip-consistency/
  index_base.json
  index_head.json
  diff.json
  findings_rules.json
  findings_semantic.json
  report.md
  cip-consistency.sarif   （可选）
  semantic_claude_stdout.log   （调试）
```
所有文件作为名为 `cip-consistency-<run-id>` 的 Actions artifact 上传。

### 5.2 `index.json`
```json
{
  "ref": "main | <sha>",
  "opcodes":  [{"id": 48, "name": "SYS_CANCEL_TIMER", "file": "...", "line": 1234, "cip_refs": ["CIP-5"]}],
  "addresses":[{"id": "0x01", "name": "scheduler", "file": "...", "line": 1500}],
  "errors":   [{"code": "ERR_TIMER_EXPIRED", "file": "...", "line": 800}],
  "cips":     [{"id": 5, "title": "Timers", "status": "Final", "file": "...", "anchors": ["§3.1"]}],
  "xrefs":    [{"from": "CIP-9", "to": "CIP-5 §3.1", "file": "...", "line": 220}],
  "terms":    [{"term": "fee_payer", "definition_file": "...", "line": 410}]
}
```

### 5.3 `findings_*.json`
```json
[
  {
    "rule_id": "R001_opcode_collision",
    "source": "rules | semantic",
    "severity": "block | warn | info",
    "title": "Opcode 0x42 与 CIP-5 冲突",
    "locations": [
      {"file": "docs/cips/cip-29-on-chain-event-hooks.md", "line": 87},
      {"file": "docs/whitepaper/cowboy-technical-whitepaper.md", "line": 1502}
    ],
    "message": "CIP-29 引入 opcode 0x42，但白皮书 §9.2 已将 0x42 分配给 SYS_FOO。按 WP §9.2 收尾注释要求，opcode 在整个注册表中必须唯一。",
    "suggestion": "按 WP §9.2 取下一个空闲位（当前为 0x4F）。"
  }
]
```

## 6. 错误处理

| 失败场景 | 行为 |
|---|---|
| `claude -p` 非零退出 / 超时 / 输出非 JSON | 语义 pass 标记为 `degraded`。仅基于规则结果继续。PR 评论说明降级。**不**让 action 失败。 |
| 语义发现 `locations` 校验失败 | 丢弃该条（记日志）。丢弃比例 >30% → 整批降级为"低置信度"。 |
| `extract_index.py` 在单个文件上抛异常 | catch + warn，继续。 |
| HEAD 索引比 base 索引少 ≥10% 资源（疑似 parser 大面积失败） | Action 失败 —— 防止"什么都没检查到"的假绿。 |
| PR 未改动文档 | 短路：action 直接成功退出，不评论、不调 LLM。 |
| PR 来自 fork（拿不到 secret） | 用 `pull_request_target` + 显式 checkout PR head + 收窄 `permissions`。若 `ANTHROPIC_API_KEY` 仍不可用，跳过语义 pass，在评论里说明。 |
| 作者认为规则误报 | 不实现 in-PR override。每条发现附带规则文档链接以及 issue tracker URL 用于上报误报。 |
| 同一 PR 反复 push | 通过 `<!-- cip-consistency-bot -->` marker 原地更新评论。 |
| 成本兜底 | base ref 的 `extract_index.py` 产物按 base SHA 缓存到 Actions cache。`semantic.py` 强制 `--max-turns 8` 并读取 `CIP_BOT_MAX_USD_PER_RUN` 作为单次预算硬上限。 |

## 7. 测试策略

### 7.1 单元测试（`tests/unit/`）
- `extract_index.py` —— 每种结构化资源准备小型 markdown fixture（10-30 行）。必须覆盖的 corner case：多行 opcode 表、`.mdx` frontmatter、多级锚点（`§9.2.3`）、跨文件引用。
- `rules.py` —— 每条规则 `R00N` 至少 1 个正例 + 1 个反例。fixture 是手写的 `index_*.json` pair，不依赖真实语料。
- `report.py` —— Markdown 渲染和 SARIF 输出的 snapshot 测试。

### 7.2 集成测试（`tests/integration/`）
五个"黄金 PR" fixture，每个一个临时 git 仓库带 base + head 两个提交：
1. 仅改外观 → 零发现，exit 0。
2. Opcode 冲突 → `R001` block。
3. 改了 opcode 但没动 §9.2 → `R003` block。
4. 悬空交叉引用 → `R004` block。
5. 语义矛盾（例如 timer 同块调度） → 期望 `semantic warn`，**仅在启用 LLM stub 时**。

测试 runner 把每个 fixture 喂给 composite action 的 `entrypoint.sh`，断言 exit code 与 `findings_*.json` 内容。

### 7.3 端到端自检
`.github/workflows/cip-consistency-selftest.yml` 在本仓库的 dogfood 分支上跑 action，作为新 CIP 落地时的 parser 兼容回归保险。

### 7.4 LLM 相关测试
- CI 中不跑真实 LLM 调用。`semantic.py` 暴露 `--mock <fixture-dir>` 用于回放录制的 `claude` 输出。
- 真 LLM 冒烟测试位于 `tests/llm/`，**仅本地手动 + 每周 cron**，非阻塞，结果作为报告发布。模型行为漂移仅做观测，不做强制。
- Schema 校验测试（locations 反向校验、严格 JSON）在 CI 上跑，针对录制输出。

### 7.5 性能门槛
- PR 单次总耗时 ≤5 分钟（含 LLM）。
- 仅规则 pass ≤30 秒。
- 在 selftest workflow 中通过超时断言强制。

## 8. 仓库文件布局

```
.github/
  actions/
    cip-consistency/
      action.yml                  # composite action 清单
      entrypoint.sh
      requirements.txt
      src/
        extract_index.py
        diff.py
        rules.py
        semantic.py
        report.py
      tests/
        unit/
        integration/
        llm/
        fixtures/
  workflows/
    cip-pr-check.yml              # PR 触发 cip-consistency
    cip-consistency-selftest.yml  # 每周 + 手动 selftest
docs/
  superpowers/
    specs/
      2026-05-15-cip-consistency-bot-design.md   # 本文件
```

## 9. 开放问题

- `report.py` 是否也要写回 `cip-todo.md`，把每 PR 的结构化漂移自动登记？（多半应做，但放到后续 PR —— v1 聚焦 PR-time 信号即可。）
- 长期：结构化索引是否要变成 checked-in artifact（由独立 workflow 重新生成），供其他工具（文档站、看板）消费？等出现第二个消费者再说。

## 10. 上线计划

1. 先上 composite action，仅 R001–R006 规则，语义 pass 由 `enable_semantic: false` 输入屏蔽。
2. 在真实 PR 上 dogfood 一周（所有规则 warn-only）。
3. R001–R006 切到 `block` 严重度。
4. 录制 LLM fixture 测试套件就绪后，启用语义 pass（warn-only）。
5. 根据真实的误报/漏报反馈逐步增加新规则。
