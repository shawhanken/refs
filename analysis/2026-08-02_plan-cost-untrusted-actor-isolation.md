# Plan-Cost 报告 — Untrusted-Actor Isolation: Current Gaps in the PVM

| | |
|---|---|
| **Plan** | `/home/ubuntu/workspace/refs/analysis/2026-07-31_untrusted-actor-isolation-gaps.pdf`(35 页) |
| **Plan 版本** | 2026-07-31,pin 在 `cowboyinc/node origin/devnet 2b2e73ab` |
| **Domain pack** | `cowboy`(34 个概念) |
| **生成日期** | 2026-08-02 |
| **verdict** | **`cost-only`** — 这是成本画像,**不含 go/no-go 建议** |

> **本报告的诚实分离原则**
> - **确定性成本**(§1)由 `marshal_core.cli plan-cost` 计算,从真实概念树/锚点推出。
> - **plan → 概念映射**(§1 的 op 选择)与**工期估算**(§3)是 agent 的判断,可被质疑。
> - `hinted_cost` 是 agent 标注的、**可被玩弄**的部分,§2 逐项交叉核对。
> - Marshal 不知道你的预算和发布窗口,**不替你决定值不值**。

---

## 0. 我怎么读这份 plan(范围判定)

这份文档是**发现登记册(findings register)+ Appendix B 的 15 张待归档 ticket(B1–B15)**,
不是架构方案。它自己划了四个 bucket:

| Bucket | 内容 | 是否计价 |
|---|---|:---:|
| 1 | Fix now,与架构决策无关(B1 / B2 / B3 / B4 / B4b) | ✅ |
| 2 | Bridge controls,现在降风险、将来被边界取代(B5–B9c) | ✅ |
| 3 | **per-channel 补丁关不掉的**(A5, A6, A30–A34, A37, A38) | ❌ **本文明确排除** |
| 4 | Unassessed(A11, A15, A23, A24, A35 → B13 / B14) | ✅ |
| — | Tooling & evidence(B10 / B11 / B12 / B15) | ✅ |

**bucket 3 没有计入。** 文档自己把它交给 companion 的 `pvm-interpreter-isolation-proposal.pdf`
(长驻沙箱 worker 进程,每个 actor frame fork 干净解释器快照)。那是另一份 plan,量级更大,
**需要单独跑一次 plan-cost**。

所以本次计价范围 = **bucket 1 + 2 + 4 + tooling(B1–B15)**。

---

## 1. 确定性成本(CLI 计算)

```
weighted_concept_cost    96
  ├─ grounded_cost       48   (redefine — 从真实概念树/锚点推出,不可 gaming)
  └─ hinted_cost         48   (add — agent 标注,占 50%,见 §2 交叉核对)
highest_tier_touched    high
blast_radius            speculative-execution, timer-mechanism
impacted_repos          node
unknown_redefines       (无)
unknown_ops             (无)
```

### 1.1 Redefine — 被重定义的既有概念(grounded 48)

| 概念 | tier | 子树 | repos | 权重 | 判定依据 |
|---|---|---:|---:|---:|---|
| `execution` | high | 5 | 1 | **28** | B4 的机检 store-write choke point;§4.7 指出 `rollback()`(`pvm_host.rs:1304-1328`)清不掉已落 store 的写,且 `ExecutionSideEffects`(`pvm_executor.rs:54-67`)**不等于**"这笔 tx 提交了什么"。这是 per-tx 原子性契约的改写 |
| `pvm` | high | 0 | 1 | **8** | B5 / B6 / B9c 改的是 actor 环境的**构成方式**:stock-environment-minus-blocklist → 正向构造的 default-deny allowlist(B6 原话:把完整性负担从 per-name 变成可枚举) |
| `actor-model` | high | 0 | 1 | **8** | 概念页写"每个 Actor 独立状态 + 无共享内存";§4.1 证明 pool key(`runtime/lib.rs:486-503`)**不带 actor 地址和 code hash**,且事务内 sibling 共享 warm interpreter(`:606-629`, `:703-715`)。B6/B7/B8 落地后这条属性才成立 |
| `continuation` | mid | 0 | 1 | **4** | B1(PR #1110)把 `checkpoint*()` pyfunctions 和 `maybe_checkpoint_request` gate 在 continuation/checkpoint 模式上;§2.1 的 residuals(reflection-guard skip、import-whitelist 放宽到 os/posix/importlib、pooling-off、COW-2434 barrier bypass)全是 Checkpoint-mode 专属 |

`execution` 的 28 里,来源是它的 5 个子概念(actor-model / continuation / dual-gas-model /
speculative-execution / timer-mechanism)—— **反映的是波及面,不是工作量**。

### 1.2 Add — 新增概念(hinted 48,agent 标注)

| 概念 | importance | est_scope | 权重 | 对应 ticket |
|---|---|---|---:|---|
| `actor-isolation-boundary` | high | **large** | **36** | B4b + B5 + B6 + B7 + B8 + B9 + B9c —— 横跨 `pvm/crates/vm/`、`pvm/crates/stdlib/`、`pvm-runtime/guard.rs`、`pvm/Lib/io.py`、`execution/pvm_executor.rs` |
| `store-write-atomicity` | high | medium | **12** | B4 —— 单张 ticket,但是结构性的(≥10 条 host path + 机检 choke point) |

### 1.3 波及面

- **`blast_radius` = `speculative-execution`, `timer-mechanism`**(两者都在 `execution` 的
  `depends_on` 传递闭包内)。
- **`impacted_repos` = `node`**(单 repo)—— 但见 §2.3 的盲区警告。

---

## 2. 交叉核对(hinted 占 50%)

### 2.1 我的标注是否往小标了?

| 检查项 | 结论 |
|---|---|
| `actor-isolation-boundary` 标 large | **成立,没有往小标。** 它是 8 张 ticket;B6 自己说要把完整性负担"从 per-name 变成可枚举",这是子系统重写而不是打补丁 |
| `store-write-atomicity` 标 **medium 而不是 large** | **这是本报告最该被质疑的一格。** 理由是它是单一子系统写路径的重构(pvm_host + stream_key_manager + CIP-29 订阅 mutators + 一个 lint),不是重写整个 actor 环境模型 |

**如果你认为 `store-write-atomicity` 该是 large:**

| | medium(本报告采用) | large |
|---|---:|---:|
| `weighted_concept_cost` | 96 | **120** |
| `grounded_cost` | 48 | 48(不变) |
| `hinted_cost` | 48 | **72** |
| `highest_tier_touched` | high | high(不变) |

文档自己说 item 4"是结构性工作而不是补丁,且不被任何隔离边界取代"—— 这是支持 large 的论据。
我选了 medium 以保持与 `actor-isolation-boundary` 的相对排序清晰。**这一格值得你自己按。**

### 2.2 我刻意没有触及的概念(以及理由)

| 概念 | 不触及的理由 |
|---|---|
| `consensus` | A10(id() cold/warm 分歧)的修复要走 coordinated genesis replacement,但那是**部署约束**,不改 Simplex propose / verify / report 本身 |
| `speculative-execution` / `storage` | §4.7 的锚点全在 `execution/pvm_host.rs` 和 `execution/stream_key_manager.rs`,是**执行侧不是存储侧**。两者出现在 `blast_radius` 里,不在触及集里 |
| `gas` / `dual-gas-model` | A38(计量已接线但不 enforce,`pvm_instr_gas_price_ppm` 默认 0,fee 计算时才折算 → 永远无法中途 abort)被文档自己放进 **bucket 3**,本 plan 不提出补丁。它是**被诊断,不是被修** |
| 独立的 float/libm 概念(B9b + B15) | 归在 `pvm` 的 redefine 里。若你认为"构建目标约束"该独立成概念,再加约 8–12 |

### 2.3 锚点覆盖不到的盲区

> **`impacted_repos` 只有 `node`,但这掩盖了两件事:**
>
> 1. **大量改动落在 `node/pvm/`** —— 那是一个 workspace-excluded 的独立 Rust workspace,
>    概念锚点没有代表它(现有锚点指向 `execution/src/*.rs`,不指向 `pvm/crates/vm/`)。
> 2. **B6 可能打断已部署 actor 和 `cowboy_sdk` 的兼容性。** 这个下游面**没有任何锚点捕捉到**,
>    完全不在 96 这个数字里。文档 §5 bucket 2 note 提到 SDK 刻意规避 asyncio(COW-2331),
>    说明 SDK 与 PVM 环境的耦合是真实的。

---

## 3. 工期估算(agent 判断,**不是 CLI 计算**)

**confidence: low–medium。** 这是在 RustPython fork 上做安全加固,**兼容性回归的量最难预测**
(B6 尤其)。相对排序比绝对数值可信。

### 3.1 Bucket 1 — Fix now

| Ticket | est_impl_days | 备注 |
|---|---:|---|
| **B1** 落地 rustpython_checkpoint gate(COW-2731) | 2–3 | PR #1110 已开未合;主要工作是补 production-config 回归 —— 现有 corpus 跑 `continuation: Some(...)`,强制 `checkpoint_exit=false`,**恰好掩盖了这个 kill** |
| **B3** 落地 id() cold/warm 确定性修复 | 3–5 工程日 + **协调升级的日历时间** | PR #1106 已开(head `eeeb0b5f`)。改变 actor 可见的 `id()`/`repr()` → STF 变更,**必须随 genesis replacement 走,不能原地打补丁** |
| **B4** 机检 store-write choke point | 12–20 | 结构性;≥10 条路径 + 编译期/lint 强制。文档说"至少十条"是**下界不是计数** |
| **B4b** 关闭 import-boundary 逃逸类 | 10–15 | 四个子改动;其中"把 allowlist 检查提到 `sys.modules` 命中之前"动的是 `vm/vm/mod.rs:821-890` 的 import 核心 |
| B2 `_signal` | — | 文档自己说折进 B5,不单独计 |

### 3.2 Bucket 2 — Bridge controls

| Ticket | est_impl_days | 备注 |
|---|---:|---|
| **B6** 正向构造最小 actor 环境 | **20–30** | **最大单项,兼容性风险也最大** |
| **B5** native OS 模块运行时默认拒 | 5–8 | 必须**运行时** enforce(动态 `__import__` 绕过 deploy AST scan),还要盖 preamble 已加载的模块 |
| **B8** 中和 settrace/setprofile + StoreGlobal 审计 | 4–6 | 第二半(`PyDict::set_item` 跳过 `writable()`,`threading.settrace` 写 `_trace_hook`)最容易漏 |
| **B7** `_thread` API 全面 gate | 3–5 | 只禁创建不够 —— `get_ident` 无需 spawn 且可直接返回 |
| **B9b** float 决策(依赖 B15) | 3–5 | 决策项,可能变成构建目标约束 |
| **B9** asyncio TLS scoped 存/恢复 | 3–4 | 是 save/restore **不是** denial(asyncio 依赖这些 hook) |
| **B9c** `write_bytecode = false` | 0.5 | 一行 + 一个防上游默认漂移的测试 |

### 3.3 Tooling / Assessment

| Ticket | est_impl_days | 备注 |
|---|---:|---|
| **B10 / B11 / B12** differential harness | 5–8 | B11(harness 指向生产配置)是前提 —— 没它,B1 这类"默认配置下看不见"的问题会继续被掩盖 |
| **B13** 评估 `_ssl` / `fcntl` + 删掉死的 `_fcntl` 条目 | 2–3 | `_fcntl` 在 allowlist 上但**没有这个模块**(注册名是 `fcntl`)—— 一条没人发现是惰性的条目 |
| **B14** id() 地址复用探针 | 2–3 | B3 修的是 counter offset,**不是指针复用** |
| **B15** 测量 actor 可达的 float 运算是否真的分歧 | 3–5 | 便宜,且是 B9b 决策的前置 |

### 3.4 合计

> **≈ 75–115 工程日**(单人计)
>
> 并行度受限:**B4b / B5 / B6 都动同一片 import 路径**,不能简单除以人数。

### 3.5 est_debt_weeks(技术债)

- **只做 bucket 1、推后 bucket 2** → name-based 控制会随 RustPython 版本持续增长,
  约 **0.5–1 周 / 每次 RustPython 版本更新,无限期**。
- **做完 bucket 1 + 2 也不消除这笔 carry**,只是压小。文档 §3.3 / bucket 3 的核心论点:
  可达面是**整个 stock interpreter**,type 列表**不是我们的**,是 RustPython 的,按他们的发布节奏增长。
  "A name-based control can be made correct on any given day. Keeping it correct is an ongoing
  obligation that scales with someone else's codebase."
- 消除它是 **bucket 3 的主张,而 bucket 3 不在这份 plan 里**。

### 3.6 与另一份 plan-cost 的交叉点(值得知道)

> 本 plan 的 **B4(机检 store-write choke point)**提议**修掉**"引擎在 handler 返 `Err` 时不回滚
> 部分写"这个缺陷。
>
> 而 **CIP-36**(`2026-08-02_plan-cost-cip-36.md`)§6.2 / §6.3 选择**绕过**同一个缺陷 ——
> 把 check-then-apply 定为 PaymentGate 与 `settle_provider` handler 的规范。
>
> **两份 plan 在同一个引擎缺陷上做了相反的决定。** 这不是 Marshal 替你选,但你应该知道:
> - 若 **B4 先落地**,CIP-36 的 check-then-apply 规范从"必需的规避"降级为"额外的稳健性";
> - 若 **CIP-36 先落地**,B4 的重构就要动一批已经按 check-then-apply 写死的 handler。

---

## 4. 你自己要判断的四件事

1. **96 里有 48 是 agent 的提示(50%)。** 尤其 `store-write-atomicity` 的 medium / large 那一格 ——
   按一下就是 96 vs 120。
2. **`highest_tier_touched = high`,没到 constitutional。** 但 §2.3 是**链上确认的 root RCE**
   (部署的 actor 跑 `id` 返回 `uid=0(root)`、读了 `/etc/shadow`)、§2.1 是**链上确认的 validator halt**
   (RestartCount 0→1)。**概念层级和安全严重性是两把尺子,这个 tier 不代表严重性。**
3. **bucket 3 没被计价。** 这份 plan 的成本是"把 Python 层屏障修到当天正确"的成本,
   **不是**"让这一类不可达"的成本。后者(companion 的进程边界提案)要跑另一份 plan-cost。
4. **`impacted_repos = node` 掩盖了 `node/pvm/` 独立 workspace 和 SDK / 已部署 actor 的兼容性面**
   —— 它们不在 96 里(§2.3)。

---

## 附录 A — 复现命令

```bash
PY=/home/ubuntu/workspace/marshal/.venv/bin/python

$PY -m marshal_core.cli plan-cost \
  --domain-pack cowboy \
  --concepts-dir /home/ubuntu/workspace/marshal/src/marshal_pack_cowboy/concepts \
  --repo-root node=/home/ubuntu/workspace/node \
  --touches /tmp/pc-touches.json
```

## 附录 B — touches(本次映射的完整输入)

```json
[
  {"concept_id": "actor-isolation-boundary", "op": "add", "importance": "high", "est_scope": "large"},
  {"concept_id": "store-write-atomicity",    "op": "add", "importance": "high", "est_scope": "medium"},
  {"concept_id": "pvm",          "op": "redefine"},
  {"concept_id": "actor-model",  "op": "redefine"},
  {"concept_id": "execution",    "op": "redefine"},
  {"concept_id": "continuation", "op": "redefine"}
]
```

**§2.1 的变体**:把 `store-write-atomicity` 的 `est_scope` 改成 `"large"`
即可复现 120 / hinted 72 的那一列。

## 附录 C — 计价范围外的 bucket 3 条目(供参考)

| ID | 通道 | 为何 per-channel 补丁关不掉 |
|---|---|---|
| A5 | pool key 不含 actor identity | 池复用是设计,不是 bug |
| A6 | 事务内 sibling 复用解释器 | per-transaction reset 够不着 |
| A30 | `copy.deepcopy` 的 `_nil=[]` default | defaults tuple 不是被遍历的容器类型 |
| A31 | closure-cell 替换 | cell 是**刻意**跳过的 |
| A32 | `_abc_registry` WeakSet | 不属于 freeze walk 的四种容器类型 |
| A33 | property descriptor | 既非结构类型也非容器,walk 停在这里 |
| A34 | lazy-import `sys.modules` 持久化 | 缓存条目留存,下一个 actor 读到变化的 `len(sys.modules)` |
| A37 | actor 执行外无 catch 边界 | `.with_catch_panics(false)`,panic 直接 resume_unwind 整个进程 |
| A38 | 计量已接线但不 enforce | 需要**循环内**计量 + 中途 abort(2026-07-14 mesa halt 的机制) |

**这 9 条 = companion 提案(`pvm-interpreter-isolation-proposal.pdf`)要解决的人群。**
