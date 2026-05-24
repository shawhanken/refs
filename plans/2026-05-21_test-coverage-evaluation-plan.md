# Cowboy 项目代码测试覆盖度评估实施方案

**计划日期**：2026-05-21
**评估范围**：`node/`(Rust 链)+ `runner/`(off-chain runner)+ `steamtrain/`(存储层)
**目标**:量化三个 workspace 的测试覆盖现状,识别薄弱区域,给出可执行的提升建议,并把覆盖率纳入 CI 防回归。

---

## Context

当前项目有约 130+ 单元测试集中在 `cowboy-execution`,但缺乏全局视角:
- `storage` crate 几乎没有单元测试(MEMORY 记录:0 tests)
- 没有跑过任何形式的覆盖率工具
- CI 未追踪覆盖率,无法发现回归
- 关键模块(`verifier.rs` slashing、`pvm_executor.rs` 黑名单分支、`process_block.rs` basefee 生命周期)的真实测试质量未量化

本方案分 6 个阶段,每阶段产物明确,可独立验收。**只评估和加 CI,不修改业务逻辑**。新增测试如果范围扩大,会拆到单独的 PR/计划。

---

## 验收目标(SMART)

完成后应同时满足:
1. `refs/analysis/2026-05-XX_test_coverage_baseline.md` 给出三个 workspace 的**行 / 分支覆盖率基线**数字。
2. 给出 **Top-10 低覆盖文件清单**(按代码行数加权),每个文件附最薄弱的 2-3 个未覆盖分支。
3. CI 中至少 `node/` workspace 在 PR 上自动产出覆盖率报告;PR diff 覆盖率低于阈值时给出警告(不强制失败)。
4. 至少在一个关键模块上跑过一次 **mutation testing**(`cargo-mutants`),输出存活变异列表。
5. 输出 **最终评估报告** `refs/analysis/2026-05-XX_test_coverage_assessment.md`,含结论 + 后续改进建议。

---

## 阶段 1 — 工具安装与基线产出

### 1.1 安装覆盖率工具

```bash
# 全局安装(一次性)
cargo install cargo-llvm-cov --locked
rustup component add llvm-tools-preview

# 验证
cargo llvm-cov --version
```

**为什么选 `cargo-llvm-cov`,不选 `tarpaulin`**:
- 基于 LLVM source-based coverage,**支持分支覆盖**(tarpaulin 只支持行)
- 与 stable Rust 兼容,无需 nightly
- 输出多种格式(HTML / lcov / cobertura / json)

### 1.2 跑全 workspace 基线(三个仓库各跑一次)

```bash
# node/
cd /home/ubuntu/workspace/node
cargo llvm-cov --workspace --html --output-dir target/coverage-html --ignore-filename-regex '(tests/|benches/|examples/)'
cargo llvm-cov --workspace --summary-only --ignore-filename-regex '(tests/|benches/|examples/)' \
  | tee /home/ubuntu/workspace/refs/analysis/_coverage_node_summary.txt

# runner/
cd /home/ubuntu/workspace/runner
cargo llvm-cov --workspace --html --output-dir target/coverage-html
cargo llvm-cov --workspace --summary-only \
  | tee /home/ubuntu/workspace/refs/analysis/_coverage_runner_summary.txt

# steamtrain/
cd /home/ubuntu/workspace/steamtrain
cargo llvm-cov --workspace --html --output-dir target/coverage-html
cargo llvm-cov --workspace --summary-only \
  | tee /home/ubuntu/workspace/refs/analysis/_coverage_steamtrain_summary.txt
```

**预期产出**:
- 三份纯文本 summary(committed 到 `refs/analysis/`)
- HTML 报告本地保存(不入库,加到 `.gitignore`:`target/coverage-html/`)

### 1.3 已知坑位与规避

| 风险 | 处理 |
|------|------|
| `pvm/` 是 workspace-excluded(独立 workspace) | 单独跑:`cd node/pvm && cargo llvm-cov --workspace --summary-only` |
| `examples/` 下有大量 E2E 脚本,LLM_CHAT 测试会真调外部 API | 用 `--ignore-filename-regex 'examples/'` 排除 |
| `cargo test --workspace` 在 `node/` 已知 `test_backfill` stack overflow(MEMORY 中已记录) | 单独跑用 `--exclude cowboy-chain --tests test_backfill`,或在 `--no-default-features` 下跑 |
| benches 不应计入 | `--ignore-filename-regex` 包含 `benches/` |
| RustPython 大量第三方代码 | 用 `--ignore-filename-regex` 排除 `pvm/crates/.*/vendor` 之类,具体路径待 1.2 跑完后看 |

### 1.4 阶段 1 验收

- [ ] `cargo llvm-cov --version` 输出版本号
- [ ] 三份 summary.txt 文件存在且非空
- [ ] HTML 报告本地可访问
- [ ] `refs/analysis/_coverage_*_summary.txt` 提交到 git

---

## 阶段 2 — 按 crate 维度拆解

### 2.1 按 crate 跑覆盖率

对 `node/` 内的关键 crate 单独出数,便于横向对比(以下命令依次执行):

```bash
cd /home/ubuntu/workspace/node

for crate in cowboy-types cowboy-storage cowboy-execution cowboy-chain cowboy-rpc cowboy-runner; do
  echo "=== $crate ===" >> /home/ubuntu/workspace/refs/analysis/_coverage_per_crate.txt
  cargo llvm-cov -p $crate --summary-only --ignore-filename-regex '(tests/|benches/|examples/)' \
    >> /home/ubuntu/workspace/refs/analysis/_coverage_per_crate.txt 2>&1
  echo "" >> /home/ubuntu/workspace/refs/analysis/_coverage_per_crate.txt
done
```

### 2.2 输出分支覆盖率(单独跑)

llvm-cov 默认输出的 summary 是行覆盖。要看**分支覆盖**(更有意义),用 lcov 中间格式:

```bash
cd /home/ubuntu/workspace/node
cargo llvm-cov --workspace --lcov --output-path target/coverage.lcov \
  --ignore-filename-regex '(tests/|benches/|examples/)'

# 分支覆盖在 lcov 里以 BRDA: 行体现,统计:
grep -c '^BRDA:' target/coverage.lcov               # 分支总数
grep '^BRDA:' target/coverage.lcov | awk -F',' '$NF=="-"' | wc -l   # 未覆盖分支数
```

输出到 `_coverage_branch_stats.txt`。

### 2.3 阶段 2 验收

- [ ] `_coverage_per_crate.txt` 包含 6 个 crate 的行/区域覆盖率
- [ ] `_coverage_branch_stats.txt` 给出全 workspace 分支总数与未覆盖数
- [ ] 在评估报告中能给出一张表:每个 crate 的 行% / 分支%

---

## 阶段 3 — 重点模块人工审计(Top-10 文件)

### 3.1 从 HTML 报告产出薄弱清单

打开 `target/coverage-html/index.html`,按文件**行数 × (1 - 覆盖率)** 降序,挑出 Top-10 文件作为人工审计对象。

预期热门候选(基于 MEMORY 与 CLAUDE.md 已知风险点):

| 文件 | 已知风险 |
|------|---------|
| `node/execution/src/runner/verifier.rs` | `slash_runner()`、各 VerificationMode 分支 |
| `node/execution/src/pvm_executor.rs` | `validate_actor_code()` 黑名单、INT_GUARD 路径 |
| `node/execution/src/execution/transaction.rs` | basefee 校验、fee burn/tip 分支 |
| `node/storage/src/process_block.rs` | basefee 生命周期、deferred sweep |
| `node/storage/src/speculative.rs` | Lane 分区、burn/tip 分配 |
| `node/execution/src/runner/dispatcher.rs` | escrow / 1.5× stake 检查 / cancel 路径 |
| `node/execution/src/pvm_host.rs` | `ActorStorageCache.read_count`、CIP-20 hook |
| `node/runner/src/types.rs` | 自定义 serde、VerifierCheck 各 variant |
| `node/execution/src/basefee.rs` | MIN_BASEFEE、target 偏离边界 |
| `node/rpc/src/handlers/*.rs` | rate limiting、faucet 路径 |

### 3.2 每个文件填写审计表

为每个 Top-10 文件,在评估报告中产出一行:

```markdown
#### {file_path}
- 行覆盖率:XX%(YY/ZZ)
- 分支覆盖率:XX%
- 未覆盖关键分支:
  1. `fn xxx` line N — 当 yyy 条件时走的 else 分支
  2. ...
- 建议:补 N 个测试 / 加 property-based test / 加集成测试
```

### 3.3 阶段 3 验收

- [ ] Top-10 清单已确定并附覆盖率数字
- [ ] 每个文件至少列出 2 个具体的未覆盖分支(带行号)

---

## 阶段 4 — 测试质量评估(数字之外)

高覆盖率 ≠ 好测试。本阶段做四个定性检查。

### 4.1 断言密度检查

```bash
cd /home/ubuntu/workspace/node
# 测试函数总数
grep -rhE '^\s*(#\[test\]|#\[tokio::test\])' --include='*.rs' | wc -l
# 包含 assert 的测试函数中 assert 的总次数
grep -rE 'assert(_eq|_ne|!)' --include='*.rs' | wc -l
```

**红线**:平均每个 `#[test]` 函数少于 2 个 `assert` → 需要在评估报告中点名。

### 4.2 Mock 滥用扫描

MEMORY 中 feedback:"集成测试必须真打数据库,不能 mock"。检查测试代码里 `mock` 的使用:

```bash
cd /home/ubuntu/workspace/node
grep -rE '\b(mock|Mock|stub|Stub)\b' --include='*.rs' \
  | grep -v 'target/' | grep -v 'mocked_basefee' \
  > /home/ubuntu/workspace/refs/analysis/_mock_usage.txt
```

逐行审查 `_mock_usage.txt`,标记可疑的 mock(尤其是 storage、basefee、chain client)。

### 4.3 错误路径覆盖

在 HTML 报告中关注:
- `Err(...)` / `bail!(...)` / `return Err(...)` 行的覆盖率
- `ExecutionError::*` 各 variant 是否都有测试匹配过

辅助命令:

```bash
# 所有 ExecutionError variant
grep -E 'pub enum ExecutionError' -A 200 /home/ubuntu/workspace/node/execution/src/error.rs \
  | grep -E '^\s+[A-Z][a-zA-Z]+' | head -50

# 每个 variant 在测试中的出现次数
for variant in $(grep -E 'pub enum ExecutionError' -A 200 /home/ubuntu/workspace/node/execution/src/error.rs | grep -oE '^\s+[A-Z][a-zA-Z]+' | tr -d ' '); do
  count=$(grep -rE "ExecutionError::$variant" --include='*.rs' /home/ubuntu/workspace/node | wc -l)
  echo "$variant: $count"
done | sort -t: -k2 -n > /home/ubuntu/workspace/refs/analysis/_error_variant_usage.txt
```

出现次数为 0 或 1 的 variant 在评估报告中点名。

### 4.4 变异测试(Mutation Testing)— 在一个关键模块跑

```bash
cargo install cargo-mutants --locked

cd /home/ubuntu/workspace/node
# 只对一个高风险模块跑,因为 mutation 测试很慢(每个 mutant 跑全套测试)
cargo mutants --package cowboy-execution --file 'execution/src/runner/verifier.rs' \
  --output /home/ubuntu/workspace/refs/analysis/_mutants_verifier/
```

**判读**:
- **caught**:存活变异被测试抓到 ✅
- **missed**:变异未被任何测试发现 ❌(测试有盲区)
- **timeout / unviable**:忽略

把 missed 列表纳入评估报告。

### 4.5 阶段 4 验收

- [ ] 断言密度数字给出
- [ ] `_mock_usage.txt` 审查完毕,可疑 mock 列入报告
- [ ] `_error_variant_usage.txt` 给出零覆盖 variant 列表
- [ ] `_mutants_verifier/` 报告存在,missed 列表已抓取

---

## 阶段 5 — CI 集成(可选,但强烈推荐)

### 5.1 添加 GitHub Actions workflow

新增 `.github/workflows/coverage.yml`(以 `node/` 为例,其他两个仓库同理):

```yaml
name: Coverage

on:
  pull_request:
  push:
    branches: [public, devnet]

jobs:
  coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: llvm-tools-preview
      - uses: taiki-e/install-action@cargo-llvm-cov
      - name: Generate coverage
        working-directory: node
        run: |
          cargo llvm-cov --workspace --lcov --output-path lcov.info \
            --ignore-filename-regex '(tests/|benches/|examples/)' \
            --exclude cowboy-chain   # 暂时排除已知 test_backfill stack overflow
      - uses: codecov/codecov-action@v4
        with:
          files: node/lcov.info
          fail_ci_if_error: false
```

### 5.2 Codecov 配置 — `codecov.yml`(repo 根)

```yaml
coverage:
  status:
    project:
      default:
        target: auto
        threshold: 1%      # 整库覆盖率允许下降 1%
    patch:
      default:
        target: 70%        # 新增/修改代码必须达到 70%
        threshold: 0%
comment:
  layout: "reach, diff, flags, files"
  behavior: default
```

### 5.3 阶段 5 验收

- [ ] CI workflow 至少在一次 PR 上跑通,Codecov 评论可见
- [ ] PR diff 覆盖率显示在评论中

---

## 阶段 6 — 输出最终评估报告

### 6.1 报告文件

新建 `/home/ubuntu/workspace/refs/analysis/2026-05-21_test_coverage_assessment.md`,结构:

```markdown
# Cowboy 项目测试覆盖度评估报告

**评估日期**:2026-05-21
**评估范围**:node / runner / steamtrain

## 一、总览(基线数字表)
| Workspace | 行覆盖 | 分支覆盖 | 测试数 |
|-----------|--------|----------|--------|
| node/     | XX%    | XX%      | NNN    |
| runner/   | XX%    | XX%      | NNN    |
| steamtrain/ | XX%  | XX%      | NNN    |

## 二、按 crate 拆解
(填阶段 2 数据)

## 三、Top-10 低覆盖文件
(填阶段 3 数据)

## 四、测试质量定性问题
- 断言密度
- Mock 滥用清单
- 零覆盖错误 variant
- Mutation testing 缺口

## 五、CI 接入情况

## 六、改进建议(分优先级)
- P0 必做:storage crate 0 测试 → 至少补 N 个核心测试
- P1 建议:verifier.rs slashing 分支补测
- P2 长期:全库引入 property-based testing (proptest)

## 七、后续计划
建议拆分到独立 PR/计划的工作项清单
```

### 6.2 阶段 6 验收

- [ ] 报告文件存在,所有占位符已填
- [ ] MEMORY.md 添加一行引用该报告
- [ ] 报告中给出明确的 P0/P1 后续工作清单(每条对应一个未来 PR)

---

## 工时估算

| 阶段 | 工作量 | 备注 |
|------|--------|------|
| 1 工具+基线 | 0.5 天 | 主要是等编译 |
| 2 按 crate 拆解 | 0.5 天 | |
| 3 Top-10 审计 | 1.0 天 | 人工读 HTML 报告 |
| 4 测试质量评估 | 1.0 天 | mutation 跑得慢,可挂后台 |
| 5 CI 集成 | 0.5 天 | 取决于是否已有 workflow 基建 |
| 6 报告输出 | 0.5 天 | |
| **总计** | **~4 天** | 单人,可并行阶段 4 与阶段 5 |

---

## 范围之外(明确 Out of Scope)

本方案**只评估**,不做以下事情(留给后续 PR):
- 实际补写测试代码
- 修复已知 `test_backfill` stack overflow
- 引入 fuzzing / property-based testing 框架
- 重构难测的模块

这些会在阶段 6 的"后续计划"清单里列出,作为独立 PR 提报。

---

## 风险与依赖

- **依赖**:`cargo-llvm-cov` 在某些老旧 toolchain 上需要 `llvm-tools-preview`。本机 Rust 版本检查:`rustc --version`
- **风险**:`pvm/` workspace 独立,如果 HTML 报告体积过大可能需要 `--ignore-filename-regex` 收紧路径
- **风险**:mutation testing 在 `cowboy-execution` 跑全 crate 可能数小时;**已限定到单文件**

---

## 后续衔接

完成本方案后,自然衍生出几个独立计划:

1. **storage crate 测试补全计划**(预计 P0)
2. **verifier.rs slashing 分支测试补全**(预计 P1)
3. **PVM 黑名单分支 property-based testing 引入**(P2)
4. **CI 覆盖率阈值收紧路线图**(P2)

每个独立写一份 `refs/plans/2026-XX-XX_*.md`。
