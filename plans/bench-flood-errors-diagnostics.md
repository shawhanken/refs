# 实现方案：修复洪水测试错误 + Bench 报告诊断增强

## Context

**假设验证结论（2026-04-01）：**

运行 `bench:all` 后出现 191 笔错误（2.6% 错误率）。最初怀疑 basefee 在洪水期间飙升导致 `maxFeePerCycle` 不足。验证过程：

1. 查询 RPC 当前 basefee → **始终为 7**（洪水前后未变化）→ basefee 假设**已证伪**
2. 分析 validator.log → 洪水期间（06:16–06:20）**零 tx 拒绝**；仅有洪水前残留的 nonce 过期错误
3. 薄块（1–10 tx）为**波动伪像**：600ms 提交间隔 ≈ 573ms 出块周期形成同步脉冲，非真实容量瓶颈
4. **真实根因**：RPC 全局限速 **100 req/s**，洪水阶段提交速率 ~90–200 req/s；`submitRaw()` 在 3 次重试（500ms/1000ms/1500ms）后抛出 `RpcError(429)`，计入错误计数

**目标**：(A) 从报告中看到错误原因（errorBreakdown）；(B) 从报告中看到 basefee 趋势（block_samples）；(C) 提升 devnet RPC 限速上限，消除误报错误。

---

## 修改清单

### Fix 1：errorBreakdown 暴露到报告（诊断可见性）

**文件：`node/bench/src/cowboy/types.ts`**

在 `FloodTestReport` 接口中添加：
```typescript
error_breakdown?: Record<string, number>;
```

**文件：`node/bench/src/cowboy/report.ts`**

在 `buildReport()` 构建 `flood_test` 对象时，将 `floodResult.errorBreakdown` 写入：
```typescript
error_breakdown: Object.keys(floodResult.errorBreakdown).length > 0
    ? floodResult.errorBreakdown
    : undefined,
```

### Fix 2：BlockSample 增加 basefee 字段（趋势可见性）

**文件：`node/bench/src/cowboy/types.ts`**

在 `BlockSample` 接口中添加：
```typescript
basefee_cycles?: number;
basefee_cells?: number;
```

**文件：收集 block_samples 的位置**（需在探索时确认，可能在 `bench.ts` 或 `monitor.ts`）

采集区块时，如果 RPC 返回 basefee 信息则填充；若 RPC 不返回则留 undefined（不为此单独发 RPC 请求，避免增加 bench 期间的请求压力）。

> 注意：若当前 RPC block 响应不含 basefee，则暂不填充，仅添加字段声明，等 RPC 扩展后自然接入。

### Fix 3：提高 devnet RPC 全局限速（消除误报）

**文件：`node/rpc/src/rpc.rs`**

将全局限速从 100 req/s 调高至 **1000 req/s**（devnet 单节点，不存在 DoS 风险）：

```rust
// 修改前：
let rate_limiter = RateLimiter::new(100, Duration::from_secs(1));
// 修改后：
let rate_limiter = RateLimiter::new(1000, Duration::from_secs(1));
```

Faucet 限速（5 req/min）保持不变。

---

## 关键文件路径

| 文件 | 变更 |
|------|------|
| `node/bench/src/cowboy/types.ts` | FloodTestReport 增加 `error_breakdown`；BlockSample 增加 `basefee_cycles/cells` |
| `node/bench/src/cowboy/report.ts` | `buildReport()` 中写入 `error_breakdown` |
| `node/rpc/src/rpc.rs` | 全局限速 100 → 1000 req/s |

---

## 验证方案

```bash
# 1. 编译验证（TypeScript）
cd node/bench && npm run build

# 2. 编译验证（Rust）
cd node && cargo build -p cowboy-rpc

# 3. 重新运行 bench
npm run bench:all

# 期望结果：
# - cowboy-logs/*.json 中 flood_test.error_breakdown 出现（能看到是 "rate limited" 还是其他原因）
# - flood_test.total_errors 接近 0（限速提升后 429 消失）
# - block_samples 中 basefee_cycles/basefee_cells 字段存在（即使暂为 undefined）
```
