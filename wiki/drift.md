---
type: comparison
tags: [drift, consistency, audit]
sources:
  - refs/analysis/2026-04-15_documentation_amendments.md
  - refs/cips/cip-13-runner-delegation.md
  - refs/cips/cip-14-dns-addressable-actors.md
  - refs/cips/cip-15-public-asset-hosting.md
  - refs/cips/cip-16-custom-domains.md
  - refs/cips/cip-23-tee-execution.md
last_updated: 2026-04-20
status: authoritative
---

# 文档-代码漂移看板

跟踪 `refs/` 中文档与 workspace 代码实际实现之间的不一致。

**权威文件**: [`refs/analysis/2026-04-15_documentation_amendments.md`](../analysis/2026-04-15_documentation_amendments.md) — 修正案正文与精确引用。

本页是 wiki 内的摘要看板，便于快速扫视和追踪状态。

---

## 当前活跃漂移（25 项，按严重性排序）

### 高严重性（10）

| ID | 主题 | 现状 |
|---|---|---|
| A-1 | `BLOCK_CYCLES_TARGET` 10M vs 20M | ✅ 修正案已发布；CIP-3 顶部 banner |
| A-2 | `BLOCK_CELLS_TARGET` 500K vs 4M | ✅ 同上 |
| A-3 | Basefee 公式（α=8 / 简化线性 / ALPHA=96）| ✅ 同上 |
| B | System Actor 地址表 0x01-0x0B | ✅ CIP-2 顶部 banner；workspace CLAUDE.md 待更新 |
| C | Runner stake 公式（1.5× vs 10×）| ✅ CIP-2 顶部 banner |
| E-1 | Timer 执行顺序（CIP-1 与代码相反）| ✅ CIP-1 顶部 banner |
| H-1 | Runner 地址 20 字节 ETH（非 Ed25519 32 字节）| ✅ runner/DOCUMENTATION.md 4 处已修 |
| H-2 | VerificationMode `HappyCase` 非法 | ✅ 4 份 runner 文档 JSON 示例已修 |
| H-3 | MCP/Job 示例缺 mode 字段（runners/threshold/checks）| ✅ 修正案 §六·补³ 给出完整 schema |
| **I-1** | **CIP-13 opcode 40–44 与现有 40 `UpdateSettlementConfig` / 41 `FundActor` / 42 `KeyDelivery` / 43 `UpgradeActor` 冲突** | ⚠️ **CIP-13 Draft 内含 TODO**；实现前必须重排（建议 44–48 或下一空段）。源：`node/types/src/execution.rs:1281-1294` |
| **N-1** | **CIP-15 要求 CIP-9 §16.3 新增 `GET_MANIFEST` Relay Node RPC** | ⚠️ CIP-9 现文只列 `PUT_SHARD / GET_SHARD / LIST_SHARDS` 三种；CIP-15 §8.4 显式标 "CIP-9 amendment required"。实现前必须决策：是否就地修订 CIP-9 还是单独升 minor 版本 |
| **N-2** | **CIP-15 §8.5 规范化了 canonical manifest serialization 与 `manifest_root` Merkle 算法；CIP-9 对此无 normative 描述** | ⚠️ CIP-9 现文用 `manifest_root` 但未规定叶子 CBOR 顺序、奇数叶复制规则、hash 函数。若 CIP-15 不是 CIP-9 权威扩展，两方会不兼容实现 |
| **TEE-1** | **CIP-23 amends CIP-2 §5.4 / §9 but CIP-2 source still says "runner must declare TEE support"** | ⚠️ CIP-23 Draft 把 Dispatcher 过滤与 Result Verifier 的 Deterministic 模式语义都重写了；CIP-2 文档未并入。实现时以 CIP-23 为准，CIP-2 下次修订应合文 |

### 中严重性（9）

| ID | 主题 | 现状 |
|---|---|---|
| A-4 | Transfer 成本（21K/0 → 5K/500）| ✅ CIP-3 顶部 banner |
| D | VerificationMode 4 → 6 variants | ✅ CIP-2 顶部 banner |
| E-2 | CIP-5 Globalbox EOB 未实现 | ✅ CIP-5 顶部 banner |
| F | Address ETH-style 已落地 | ✅ ADDRESS_MIGRATION 提案标 ✅已实施 |
| G-1 | Token hook 50K 为阶段 1 声明未扣费 | ✅ CIP-20 顶部 banner |
| G-2 | Runner stake 两层门槛（10K/50K）| ✅ Entitlement 顶部 banner；DOCUMENTATION.md 3 处已修 |
| M-1 | VerificationMode 字段级 schema 缺失 | ✅ 修正案 §六·补³ 补齐；建议回填到 DOCUMENTATION.md |
| M-4 | CallbackInfo.actor 地址格式未声明 | ✅ 修正案说明；建议补 DOCUMENTATION.md |
| — | workspace `/home/ubuntu/workspace/CLAUDE.md` 常量 | ⚠️ 待更新（BLOCK_* 与 System Actor 地址）|

### 低严重性（5）

| ID | 主题 | 现状 |
|---|---|---|
| L-1 | Timer 预算未在 runner 文档说明 | 修正案记录，文档中未补 |
| L-2 | 默认端口表缺失（RPC 4000 / indexer 8080）| 修正案记录 |
| L-3 | pvm/01 过时警告缺权威源链接 | 修正案记录 |
| **L-4** | **CIP-12 `SystemActorUpgrade` Payload（Tier 3）与现有 opcode 43 `UpgradeActor` 的关系未明确**：前者是治理负载，后者是已有 SystemInstruction，CIP-12 未说明合并/废弃。 | ⚠️ 实现阶段裁决 |
| **L-5** | **块时间假设不一致**: CIP-14 `BLOCKS_PER_YEAR=31,536,000` 按 1 block/sec 算；CIP-23 `MAX_QUOTE_AGE = 150 blocks ≈ 75s @ 500ms` 假设 500ms；与 `refs/plans/block-time-500ms-to-1000ms.md` 的未决决策耦合。影响所有以 blocks 表达的时间窗口。 | ⚠️ 待块时间统一后重新核对所有时间常量 |
| **L-6** | **CIP-14 `RouteRegistration` vs CIP-16 `DomainBinding` schema 差异**：后者是前者超集（新增 `namespace_kind` / `tld_kind` / `status` / 外部验证字段）。CIP-14 未更新以对齐。 | ⚠️ 实现时直接用 `DomainBinding`；CIP-14 下次修订应合并文本 |

---

## 监控维度

在 lint 时扫描这些线索，发现新漂移时追加到修正案：

1. 代码常量变更（`node/types/src/constants.rs`、`execution/src/basefee.rs`、`execution/src/gas.rs`）
2. 新枚举 variant（`VerificationMode`、`SystemInstruction`、`ActorInstruction`）
3. CIP 修订（`refs/cips/` 中 `Revised:` 字段）
4. 白皮书更新（`refs/whitepaper/` — 受保护，只读对比）
5. 新 System Actor（`node/runner/src/system_actors.rs`）

---

## 更新流程

当发现新漂移：
1. 验证代码侧实际值
2. 追加条目到 `refs/analysis/2026-04-15_documentation_amendments.md`（或当月新修正案）
3. 在受影响的 CIP / raw source 顶部加 Warning banner 指向修正案
4. 本文件（`drift.md`）追加条目到对应严重性区
5. `wiki/log.md` append `## [YYYY-MM-DD] lint | <摘要>`
6. 相关 `wiki/parameters.md` / concept 页同步更新

---

## 相关
- [[parameters]] — 参数权威表（漂移修复后的结果在此）
- [`refs/analysis/2026-04-15_documentation_amendments.md`](../analysis/2026-04-15_documentation_amendments.md) — 修正案正文
