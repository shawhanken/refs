# Cowboy 项目测试覆盖度终评估报告(本轮 campaign 收尾)

**评估日期**:2026-05-24 (本轮 campaign 全部收尾后)
**评估范围**:`node/` + `runner/`(`steamtrain/` 仍不存在)
**节点位置**:
- `node` @ `5df0dcf3`(devnet HEAD,已含 PR #486–#513 全部 merged,共 **21 个**)
- `runner` @ `da67533`(devnet HEAD,已含 PR #70–#79 全部 merged,共 **10 个**)
**工具**:`cargo-llvm-cov 0.8.5`
**前两份报告**:
- `refs/analysis/2026-05-21_test_coverage_assessment.md`(基线)
- `refs/analysis/2026-05-23_test_coverage_reassessment.md`(第一次再评估)
- `refs/analysis/2026-05-24_test_coverage_reassessment.md`(第二次再评估,5-24 早期,#507/#506/#505 刚 merged)

---

## 一、Workspace 总览(4 个时间点)

| Workspace | 指标 | 2026-05-21 | 2026-05-23 | 2026-05-24 早 | **2026-05-24 终** | Δ 21→终 |
|-----------|------|-----------|-----------|---------------|---------------------|---------|
| **node/** | Regions 覆盖 | 72.27% | 73.26% | 73.92% | **74.77%** | **+2.50pp** |
| | Functions 覆盖 | 68.49% | 69.57% | 70.72% | **72.28%** | **+3.79pp** |
| | Lines 覆盖 | 71.26% | 72.23% | 72.96% | **74.06%** | **+2.80pp** |
| | 总 regions | 151,601 | 154,662 | 156,286 | 157,910 | +6,309(代码增长) |
| | 缺失 regions | 42,042 | 41,351 | 40,765 | **39,836** | **−2,206** |
| | 缺失 lines | 29,803 | 29,342 | 28,859 | **27,975** | **−1,828** |
| **runner/** | Regions 覆盖 | 83.47% | 83.47% | 84.22% | **86.14%** | **+2.67pp** |
| | Functions 覆盖 | — | — | 81.68% | **84.13%** | — |
| | Lines 覆盖 | 83.55% | 83.55% | 84.23% | **86.37%** | **+2.82pp** |
| | 缺失 lines | 2,146 | 2,146 | 2,098 | **1,911** | **−235** |

**判读**:
- **node 行覆盖率 +2.80pp 累计**(71.26% → 74.06%)。4 天里代码量净增 ~4,145 行(新功能持续),但缺失行数反而减少 1,828 行 — **净覆盖率提升来自真实测试增量,不是代码量稀释**。
- **runner +2.82pp** — 与 node 持平。runner 终于在本轮拿到了 10 个 PR 的实质性补测。
- **两个 workspace 都跨过了关键阈值**:node 进入 70% 区,runner 进入 86% 区。

---

## 二、Per-Crate Delta(node,4 个时间点)

按当前覆盖率升序排列(`*` 标示本次复盘期(5-24 早 → 终)有变化):

| Crate | 5-21 | 5-23 | 5-24 早 | **5-24 终** | Δ 5-24 早→终 | 备注 |
|-------|------|------|---------|----------|---------|------|
| dev_runner / inspector / tools / validator | 0% | 0% | 0% | 0% | 0 | binary 入口,E2E 才能命中 |
| **cli** | 46.93% | 50.11% | 50.11% | **51.67%** | **+1.56pp** ✓ | PR #511(commands_session 0%→50%)|
| **rpc** | 45.47% | 47.15% | 49.01% | **53.59%** | **+4.58pp** ✓ | PR #509/#510/#512 三批早返回 |
| ras | 71.79% | 71.92% | 72.55% | 72.55% | 0 | (`ras/` 是独立 crate,不是 rpc/handlers/ras.rs)|
| **execution** | 77.40% | 77.97% | 78.40% | 78.40% | 0 | 本次复盘期未触及 |
| **indexer** | 72.63% | 72.63% | 75.21% | **80.06%** | **+4.85pp** ✓ | PR #513(lib.rs 67%→77%)|
| chain | 76.75% | 84.08% | 87.06% | 87.06% | 0 | 已饱和(本次复盘期未触及)|
| storage | 91.40% | 91.46% | 91.46% | 91.46% | 0 | 已饱和 |
| **types** | 91.53% | 91.53% | 91.53% | **92.30%** | **+0.77pp** ✓ | PR #508(session/manifest/signature)|
| runner(node 内 crate) | 94.62% | 93.66% | 93.66% | 93.66% | 0 | C-1 类型缺口未补 |
| client | 93.75% | 93.75% | 93.75% | 93.75% | 0 | — |
| proof-verifier | 98.60% | 98.60% | 98.60% | 98.60% | 0 | 饱和 |
| token | 99.60% | 99.60% | 99.60% | 99.60% | 0 | 饱和 |

**关键观察**:
- **rpc +4.58pp 在本次复盘期是最大单 crate 增益** —— PR #509 (runner.rs) + #510 (chain.rs) + #512 (governance + proof) 都是同一早返回方法学的连续应用,4 PR 把 rpc 整体推进了近 5pp。
- **indexer 跨过 80% 桶** —— PR #513 单 PR 27 个测试,推 lib.rs 67% → 77%,带动 crate +4.85pp。
- **cli 突破** —— PR #511 单文件 0% → 50% 是本轮最高效 PR(21 tests / +50.12pp 单文件)。
- **execution 静止** —— 本次复盘期没动 execution crate(已经 78.40%,后续优化需要更深的基建)。

---

## 三、Per-Crate Delta(runner,4 个时间点)

| Crate | 5-21 | 5-23 | 5-24 早 | **5-24 终** | Δ 5-24 早→终 |
|-------|------|------|---------|----------|---------|
| workspace-root(`src/main.rs`)| 35.0% | 35.0% | 34.98% | 34.98% | 0 |
| runner-storage | 61.8% | 61.8% | 61.79% | **77.89%** | **+16.10pp** ✓ PR #77 |
| **runner-agent** | (~30%) | ~70% | 70.46% | 70.46% | 0(PR #70/#71 已 merged 在 5-24 早)|
| **runner-node** | (~70%) | (~75%) | 76.86% | **82.24%** | **+5.38pp** ✓ PR #78 |
| **runner-tee** | (~65%) | (~75%) | 81.34% | **86.61%** | **+5.27pp** ✓ PR #79 |
| chain-client | — | — | 86.68% | 86.68% | 0 |
| runner-common | — | — | 90.15% | 90.15% | 0 |
| job-dispatcher | — | — | 91.34% | 91.34% | 0 |
| runner-http | — | — | 91.90% | 91.90% | 0 |
| runner-mcp | — | — | 92.19% | 92.57% | +0.38pp(小波动)|
| tee-verifier | — | — | 95.00% | 95.00% | 0 |
| runner-llm | — | — | 95.42% | 95.42% | 0 |
| runner-registry | — | — | 97.92% | 97.92% | 0 |
| result-verifier | — | — | 98.21% | 98.21% | 0 |
| runner-consensus | — | — | 100% | 100% | 0 |

**关键观察**:
- **3 个大跨度 crate 推进**:runner-storage **+16pp**、runner-node **+5pp**、runner-tee **+5pp** —— 都集中在本次复盘期(PR #77/#78/#79)
- **runner-storage 突破 75%** —— PR #77 的 10 个 helper 测试把整个 CIP-9 安全契约从 62% 推到 78%,这是本轮 runner 最大单 crate 涨幅
- **runner-node session/server.rs 95.31%** —— PR #78 单文件从 65% 推到 95% (+30.52pp)
- **5 个 crate 仍在 90%+**:job-dispatcher、runner-http、runner-mcp、tee-verifier、runner-llm、runner-registry、result-verifier、runner-consensus
- **runner-consensus 100%** ✓

---

## 四、本轮 Campaign 总览(2026-05-21 → 2026-05-24,4 天)

### Node 21 个 PR merged

| # | 日期 | 主题 | 影响 |
|---|------|------|------|
| #486 | 5-21 | CI workflow + Codecov | 基建 |
| #487 | 5-21 | 4 个 0% RPC handler + test_helpers | rpc |
| #488 | 5-21 | registry slash_runner + pay_rescue_bonus | execution |
| #489 | 5-21~22 | RAS helper batch1 | rpc |
| #490 | 5-21 | CI 删 `--skip` 黑名单 | CI 清理 |
| #491 | 5-22~23 | CLI cbor_to_json + status | cli |
| #499 | 5-23 | cbss helpers + actor-release-debt | execution |
| #500 | 5-23 | session 错误路径 | execution |
| #501 | 5-23 | chain 三个 0% 文件 | chain |
| #502 | 5-23 | dispatcher.rs 纯 helpers | execution |
| #503 | 5-23 | system_instruction validators | execution |
| #504 | 5-23 | indexer db.rs roundtrips | indexer |
| #505 | 5-24 | rpc/handlers/cbss.rs pure helpers | rpc |
| #506 | 5-24 | pvm_host detect_job_type + tee_required | execution |
| #507 | 5-24 | ras 9 早返回路径 | rpc(**方法学突破**)|
| #508 | 5-24 | types codec contracts(session/manifest/signature)| types |
| #509 | 5-24 | runner.rs 15 早返回 | rpc |
| #510 | 5-24 | chain.rs 18 早返回 | rpc |
| #511 | 5-24 | commands_session 0%→50% | cli |
| #512 | 5-24 | governance + proof 早返回 | rpc |
| #513 | 5-24 | indexer/lib.rs 27 早返回 | indexer |

### Runner 10 个 PR merged

| # | 日期 | 主题 | 影响 |
|---|------|------|------|
| #70 | 5-23 | runner-agent load_session edges | runner-agent agent_loop +27pp |
| #71 | 5-23 | runner-agent tool_schema(0%)| runner-agent tool_schema 0%→99% |
| #72 | 5-24 | runner-tee quote_collector helpers | runner-tee |
| #73 | 5-24 | runner-storage CIP-9 hash + AAD | runner-storage |
| #74 | 5-24 | runner-node session/server helpers | runner-node |
| #75 | 5-23 | runner-node session/scheduler | runner-node |
| #76 | 5-24 | runner-mcp executor edges | runner-mcp |
| #77 | 5-24 | runner-storage 10 helper paths | runner-storage 62%→78% |
| #78 | 5-24 | runner-node session/server handler validation | server.rs 65%→95% |
| #79 | 5-24 | runner-tee quote_collector file I/O + env | quote_collector 66%→82% |

### 累计 31 个 PR / 约 **470 个新测试**

---

## 五、本次复盘期的"早返回方法学"全家族

PR #507 开始的早返回方法学共有 **9 个 PR**,统一基建(`run_with_app_state` / 直接调用 handler 函数),跨 **5 个 crate**:

| PR | Crate | File(s) | 新测试 | 单文件 Δpp | pp/test |
|----|-------|---------|-------|----------|---------|
| #507 | rpc | handlers/ras.rs | 9 | +4.45 | 0.49 |
| #509 | rpc | handlers/runner.rs | 15 | +11.64 | 0.78 |
| #510 | rpc | handlers/chain.rs | 18 | +12.76 | 0.71 |
| #511 | cli | commands_session.rs | 21 | **+50.12** | **2.39** |
| #512 | rpc | handlers/governance.rs + proof.rs | 11 | +18.49 / +12.01 | **1.50–6.16** |
| #513 | indexer | indexer/lib.rs | 27 | +9.56 | 0.35 |
| #77 | runner-storage | runner-storage/lib.rs | 10 | +16.10 | 1.61 |
| #78 | runner-node | session/server.rs | 8 | **+30.52** | **3.82** |
| #79 | runner-tee | quote_collector.rs | 10 | +16.02 | 1.60 |

**累计**:**129 个测试,10 个文件,跨 5 个 crate**

**最高 ROI 测试**:`get_governance_params_returns_200_on_empty_store` —— 单测试覆盖约 50 行(6.16pp/test on governance.rs 单文件维度)。

**最大单文件涨幅**:`cli/commands_session.rs` 0% → 50.12%(PR #511,21 个测试)

---

## 六、Top-10 低覆盖文件(2026-05-24 终)

按缺失行绝对量排序,与之前对比:

| # | 文件 | 5-21 缺失 | 5-23 缺失 | 5-24 早 缺失 | **5-24 终 缺失** | Δ 全程 |
|---|------|----------|----------|--------------|-------------|--------|
| 1 | `rpc/src/handlers/ras.rs` | 4,289 | 4,323 | 4,166 | **4,166** | −123 |
| 2 | `cli/src/commands.rs` | 3,877 | 3,705 | 3,705 | **3,705** | −172 |
| 3 | `rpc/src/handlers/chain.rs` | 1,309 | 1,309 | 1,309 | **1,073** | **−236** ✓ |
| 4 | `rpc/src/handlers/runner.rs` | 1,396 | 1,395 | 1,395 | **1,173** | **−223** ✓ |
| 5 | `execution/src/pvm_host.rs` | 1,206 | 1,206 | 1,156 | **1,156** | −50 |
| 6 | `execution/src/runner/registry.rs` | 1,174 | 1,162 | 1,162 | **1,162** | −12 |
| 7 | `execution/src/cbss.rs` | 1,107 | 1,060 | 1,060 | **1,060** | −47 |
| 8 | `execution/src/runner/dispatcher.rs` | 911 | 971 | 948 | **948** | +37(代码增长)|
| 9 | `execution/src/execution/system_instruction.rs` | 905 | 905 | 905 | **905** | 0 |
| 10 | `indexer/src/lib.rs` | 760 | 760 | 760 | **607** | **−153** ✓ |

**改善**:
- chain.rs 缺失 **−236**(PR #510)
- runner.rs 缺失 **−223**(PR #509)
- indexer/lib.rs 缺失 **−153**(PR #513)

**未动**:
- ras.rs 仍 4,166 miss(早返回方法学只能解锁 ~5pp,完整突破需 tokio 桥接基建)
- commands.rs 仍 3,705 miss(需 Client mock 基建,本轮没投入)
- pvm_host.rs / registry.rs / cbss.rs / system_instruction.rs 都没动(execution crate 本次复盘期未触及)

---

## 七、对比 5-21 P0/P1 目标的最终完成度

| 5-21 P0 | 状态 | 当前数字 |
|---------|------|---------|
| 1. `rpc/handlers/ras.rs` → ≥60% | ⚠️ 进行中 | 17.8% → 22.15%(早返回方法学已用完;完整突破需要 tokio 桥接基建)|
| 2. `cli/commands.rs` → ≥60% | ⚠️ 进行中 | 46.3% → 50%(需 Client mock 基建,本轮未做;但 commands_session.rs 0%→50% 是相关收益)|
| 3. `execution/runner/registry.rs` → ≥80% | ⚠️ 部分 | 55.8% → 59.78%(PR #488 已 pin slash 路径,缺口仍大)|
| 4. `runner-agent/agent_loop.rs` → ≥60% | ⚠️ 部分 | 18.9% → 46.15%(PR #70 大幅推进,但仍未达 60%;需 LLM mock 才能再推)|
| 5. test_backfill stack overflow | ✅ 完成 | PR #490 验证通过,从 --skip 名单移除 |

| 5-21 P1 | 状态 |
|---------|------|
| 6. `execution/pvm_host.rs` → ≥75% | ⚠️ 58.9% → 61.56%(+2.66pp) |
| 7. `rpc/handlers/runner.rs` / `chain.rs` → ≥70% | ⚠️ 推到 58.23% / 60.77%(+12-13pp 但仍未达 70%)|
| 8. 零测试引用 ExecutionError variant 补负路径 | ⚠️ PR #500 覆盖部分 |
| 9. verifier.rs 全量 mutation 测试 | ❌ 未推进 |

**新增 P0(本次复盘新发现的风险已解决)**:
- ~~cli/commands_session.rs 0%~~ ✅ PR #511 推到 50% |
- runner repo 沉睡状态 ✅ PR #70-#79 共 10 PR 全 merged
- ras handler 完整突破 ⚠️ 仍受 tokio 桥接限制

---

## 八、CI 工程进展

| 项 | 5-21 | 5-23 | 5-24 早 | **5-24 终** |
|----|------|------|---------|-------------|
| `.github/workflows/coverage.yml` | ✅(#486)| ✅ | ✅ | ✅ 每 PR 触发 |
| `--skip` 黑名单 | 4 个 | 0 个 | 0 个 | 0 个 |
| `devnet` 分支保护 | 未明确 | 未明确 | 未明确 | ✅ **本次确认:必须 PR + Format 检查通过**(直接 push 会被 GH013 拒)|
| Codecov token | ❌ | ❌ | ❌ | ❌ **仍待 repo admin** |
| submodule 抖动 | 0 | 4-5 次 | 7+ 次 | **持续**(每隔几个 PR 需手动重触发) |

**新发现的合规风险**:本次复盘中诊断了一次本地 `git push origin devnet:devnet` 被拒(GH013 规则违反)。证实 devnet 分支强制 PR + `Format` 必需检查通过,这是好事(防止直接绕过 CI)。但 cargo resolver 偶尔会自动改 Cargo.lock(`http-body-util` transitive dep 漂移),不小心 commit 后会被卡死;**应规范化:每个 PR commit 前显式 `git checkout Cargo.lock` 扔掉自动漂移**。本轮所有 PR 都遵守了这点。

---

## 九、4 天累计一句话总结

> **4 天、31 个 merged PR(21 node + 10 runner)、约 470 个新测试**,node 行覆盖率 71.26% → **74.06%**(+2.80pp,缺失行 −1,828),runner 行覆盖率 83.55% → **86.37%**(+2.82pp,缺失行 −235)。两个 workspace 都跨过关键阈值。本轮孵化的"早返回方法学"在 5 个 crate 上成功复用 9 次,**129 个最小基建测试**覆盖了 10 个文件的输入验证 + NOT_FOUND + 反 DoS 契约。
>
> **最大单 PR 涨幅**:#511 cli/commands_session.rs **+50.12pp**(0% → 50%),CIP-9 MPP session 资金安全契约全 pin。
> **最大单 crate 跨度**:runner-storage **+16.10pp**(PR #77,CIP-9 CBSS 密钥派发链路安全契约)。
> **最高 ROI 测试**:`get_governance_params_returns_200_on_empty_store`(1 个测试,~50 行覆盖,6.16pp/test)。
>
> **未解决遗留**:ras.rs 完整突破需要 tokio 桥接基建;commands.rs 完整突破需要 Client mock 基建;agent_loop.rs 完整突破需要 LLM mock 基建;execution crate 内深层 PVM/registry/dispatcher 优化需要更深的工程投入。这些都是 P1 后续 sprint 的目标。
>
> **基建升级**:`run_with_app_state` test harness 横跨 rpc/cli/indexer 3 个 crate 复用;runner repo 的 `Arc<Indexer>` direct-handler-call 模式跨 runner-storage/runner-node/runner-tee 复用。同一最小基建模式被验证可移植到任何 axum-based 或 store-based 模块。

---

## 十、产物清单

| 文件 | 类型 |
|------|------|
| `refs/analysis/2026-05-24_test_coverage_final.md` | 本报告(终评估)|
| `/tmp/node_cov_final.txt` | node 全文件 llvm-cov 原始输出 |
| `/tmp/runner_cov_final.txt` | runner 全文件 llvm-cov 原始输出 |

---

## 十一、下一阶段 4 个候选 sprint(更新版)

按 ROI / 风险综合排序:

### A. tokio 桥接基建(P0)
解锁 ras.rs / proof.rs 等 ~30 个 handler 的 scan_actor_storage 路径;一次基建投入,带来 5-7 个 PR 的连锁收益。预计 node 行覆盖率 +1.5-2.0pp。

### B. CLI Client mock 基建(P0)
解锁 commands.rs 完整突破;wallet/registry/proof 命令的 happy path 都能测。预计 cli crate +20-30pp。

### C. LLM executor mock(P1)
解锁 agent_loop.rs 完整突破 + handle_chat 的 LLM 派遣路径。覆盖率收益较小但触达 CIP-9 agent 安全契约。

### D. execution 深层补强(P2)
pvm_host.rs / registry.rs / dispatcher.rs / system_instruction.rs / cbss.rs 共 ~5,200 missed lines,需要 PVM fixture + 完整 actor 部署测试基建。一次性投入大,但能把 execution crate 推到 90%+。

### 短期可挑(无新基建)
- `cli/key_format.rs` / `cli/config.rs` 已 97-98%,留作收尾
- `runner-agent/fs_tools.rs` 79.81%,可继续补
- `runner-agent/executor.rs` 61.24%,需要 LLM mock(回到 C)
- node 的 ras crate (不是 rpc/handlers/ras.rs)72.55% 还有空间
