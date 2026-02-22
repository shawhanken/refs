# Validator 日志中常见 WARN 说明

## 1. `requested buffer capacity is too low, increasing it to floor floor=16384`

**来源**：`commonware_runtime::utils::buffer::pool::append`

**原因**：创建 Append 写缓冲时，传入的 `capacity` 小于库要求的最小值（`page_size * 2 = 16384`）。本仓库里原先对各个存储分区使用了 `mmr_write_buffer: 1024`，commonware 会强制提升到 16384 并打 WARN。

**处理**：已在 `storage` 中把所有 `mmr_write_buffer` 从 1024 改为 16384，满足库的最小要求，此类 WARN 应不再出现。

---

## 2. `MMR lags behind journal, replaying journal to catch up journal_size=... replay_count=...`

**来源**：`commonware_storage::journal::authenticated`

**原因**：打开某个分区（actors、actor_events、timers 等）的认证 journal 时，MMR（Merkle Mountain Range）索引的条目数少于 journal 当前长度。常见于**每次区块提交后**我们调用 `reinitialize_actors_storage` 等重新打开存储视图：新实例会从持久化状态加载，若 MMR 尚未与 journal 同步，就会回放 journal 追平并打一条 WARN。

**是否正常**：是。这是 commonware-storage 的预期行为，用于保证 MMR 与 journal 一致，不影响正确性。

**若想减少日志噪音**：可对依赖库单独降级日志级别，例如在启动脚本中设置：

```bash
export RUST_LOG="info,commonware_runtime=error,commonware_storage=error"
```

这样会同时压低上述两类 WARN；若需要排查存储/MMR 问题，可临时改回 `info` 或 `debug`。
