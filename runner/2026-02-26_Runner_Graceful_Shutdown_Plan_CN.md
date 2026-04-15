# Runner 节点优雅关闭（Graceful Shutdown）方案

> **状态**: 草稿（基于当前实现与 CIP-2 修订）  
> **作者**: Cowboy 核心团队  
> **创建日期**: 2026-02-26  
> **适用范围**: `cowboyinc/runner` 仓库，Runner 节点进程  

---

## 1. 设计目标

- **安全**: 避免直接杀死正在执行的 LLM / HTTP / MCP 任务，最大限度减少结果丢失与双重执行。
- **协议一致性**: 与链上 Runner Registry / Job Dispatcher 的健康状态与任务分发语义严格对齐，不在协议层制造“幽灵 Runner”或“悬空 Job”。
- **可运维**: 支持二进制替换（binary-swap）部署：`stop → swap binary → start`，并与 `systemd` 超时机制配合良好。
- **可观测**: 在日志与指标中清晰暴露 shutdown 状态、排空进度，以及未完成任务的统计。
- **可演进**: 分阶段落地，兼容现有实现（仅有 `Healthy/Unhealthy`），再逐步引入 `Paused` 等更精细的状态与链侧 RPC。

---

## 2. 现状回顾（Runner 节点与链侧协议）

### 2.1 Runner 节点结构（链下）

参考 `runner/crates/runner-node/src/node.rs` 与 `refs/runner/RUNNER_SYSTEM_DESIGN.md`：

- `RunnerNode::start()` 当前会启动 3 个长期运行的异步任务：
  - **Job Listener**: 轮询链侧 REST `GET /runner/{address}/jobs`，把新任务推入本地 `job_queue`。
  - **Health Checker**: 周期性调用链侧 `heartbeat` 接口，更新链上 `last_heartbeat`。
  - **Job Executor**: 从 `job_queue` 拉取 Job，根据 `max_concurrent_jobs` 控制并发，调用具体执行器（LLM / HTTP / MCP），并通过链侧 REST 提交结果。

### 2.2 链侧 Runner Registry / Dispatcher 行为

- **Registry 健康判定**（`node/chain/src/runner/registry.rs`）：
  - 维护 `RunnerRegistration`，字段包括 `health`、`last_heartbeat` 等。
  - 超过 `HEARTBEAT_TIMEOUT_BLOCKS = 100` 区块未收到心跳，则 `health = Unhealthy`，不再参与任务分发。
- **Job Dispatcher 分发逻辑**（`node/chain/src/runner/dispatcher.rs`）：
  - 每次分发从 `get_active_runners` 结果中过滤 `health == Healthy` 的 Runner。
  - 对选中的 Runner，将 Job ID 写入 `runner_jobs_key(runner)`，供其 `GET /runner/{addr}/jobs` 拉取。
  - 当前协议**没有**“取消分配 / 暂停分发”的显式 API，依赖健康状态与超时。

### 2.3 现存问题

在现有实现上直接“收到 SIGTERM 后停 listener + health checker + drain 活跃任务”，会产生：

- **健康窗口问题**: 停止 heartbeat 之后的 0～约 100 秒内，链上仍视 Runner 为 `Healthy`，仍可能分配新任务，但本地 listener 已停，不再拉取，导致这些 Job 只能等超时。
- **队列语义问题**: 已经写入 `runner_jobs` 的 Job，但尚未被 Runner 拉取或尚在本地 `job_queue` 中，如果在 shutdown 过程中被直接丢弃，则从链侧视角是“已分配但从未尝试执行”。

本方案旨在**显式建模“关闭中的 Runner”状态**，并给出与链侧协议匹配的行为规约。

---

## 3. Shutdown 总体模型

### 3.1 状态机

我们为 Runner 节点引入 3 个运行状态：

1. **Running**
   - 正常工作：监听任务、发送心跳、执行 Job。
2. **Draining**
   - 已收到 shutdown 信号（SIGTERM / SIGINT），不再接受新任务，排空当前在本地已知的任务（执行中 + 队列中）。
3. **Stopped**
   - 所有本地 Job 已完成（或达到 drain 超时阈值），主进程退出。

对应的状态机转换：

- `Running --(SIGTERM/SIGINT)--> Draining`
- `Draining --(active_jobs == 0 且 job_queue 为空)--> Stopped`
- `Draining --(drain 超时)--> Stopped`（可能有未完成 Job，被后续协议超时或处罚接管）

### 3.2 核心约束

- **约束 1：Draining 期间不得产生新分配**
  - 一旦 Runner 进入 `Draining`，应尽快让链侧 `get_active_runners` 不再返回该 Runner，从而防止 Dispatcher 继续向其分配新 Job。
- **约束 2：本地已知 Job 的处理策略一致**
  - 对已在本地掌握的 Job（已拉取 / 已排队 / 正在执行），行为需要明确：
    - 默认策略：**尽量全部执行并提交结果**，除非超过 drain 超时。
- **约束 3：超时与惩罚语义透明**
  - drain 超时后被 systemd SIGKILL 强制终止时，可能存在未完成 Job；这些 Job 后续由协议级超时与可能的惩罚处理，需要在文档中清晰记录，不隐瞒风险。

---

## 4. 信号处理与系统集成

### 4.1 信号来源与优先级

- **SIGTERM**
  - 主要用于进程优雅关闭，由 `systemd`、部署脚本或手动 `kill` 发送。
  - 本方案中作为**唯一正式的优雅关闭入口**。
- **SIGINT**
  - 用户 `Ctrl-C` 时触发，行为与 SIGTERM 一致，便于本地开发时验证。
- **SIGKILL**
  - 仅由操作系统或 `systemd` 在超时等异常情况下强制发送。
  - 无法捕获，也无法执行任何清理逻辑，是“最后手段”。

### 4.2 systemd 单元推荐配置

建议在 Runner 的 systemd unit（独立 PR 中落地）中配置：

```ini
[Service]
Type=simple
ExecStart=/usr/local/bin/cowboy-runner
Restart=on-failure
KillSignal=SIGTERM
TimeoutStopSec=330

# 确保 SIGTERM 在超时后才升级为 SIGKILL
KillMode=mixed
```

- **KillSignal=SIGTERM**: 触发 Runner 进入 `Draining` 状态。
- **TimeoutStopSec=330**: 比 Runner 内部 `drain_timeout_seconds`（默认 300s）略大，给日志与清理留有缓冲。
- **KillMode=mixed**: 先对主进程发送 SIGTERM，必要时再对子进程发送 SIGKILL。

### 4.3 部署流水线约定

在 CI / 运维层面，约定 Runner 部署步骤：

1. `systemctl stop cowboy-runner`（发送 SIGTERM → 等待 drain 完成或超时）
2. 替换 Runner 二进制（例如从 S3 下载并原子替换）
3. `systemctl start cowboy-runner`

要求：

- 部署脚本**不得直接发送 SIGKILL**，统一使用 `systemctl stop`。
- 如需快速回滚，优先选择 `start` 启动旧版本，而非强杀未完成 drain 的进程。

---

## 5. Runner 进程内的 Shutdown 设计

### 5.1 Shutdown 控制接口

在 `runner-node` 内部抽象一个轻量级的 shutdown 控制器：

- 使用 `tokio::sync::watch::channel<ShutdownState>`（或 `bool` + 辅助枚举）传播状态：
  - `Running` / `Draining`。
- 提供以下只读句柄：
  - `shutdown_rx_for_listener`
  - `shutdown_rx_for_health_checker`
  - `shutdown_rx_for_executor`
- 提供只写接口（仅主线程 / 信号处理使用）：
  - `fn initiate_shutdown(reason: ShutdownReason)`：将状态切换为 `Draining`，记录时间戳与原因。

### 5.2 信号处理逻辑

主函数（`runner/src/main.rs`）中：

1. 启动时创建 `ShutdownController`（内部持有 `watch::Sender` 与 `Instant::now()`）。
2. 注册 SIGTERM / SIGINT 监听：
   - 收到**首次**信号时：
     - 记录日志（包括当前活跃 Job 数与队列长度）。
     - 调用 `ShutdownController::initiate_shutdown(Reason::Signal(SigTerm))`。
     - 启动一个 `drain()` 异步任务（见下节）并监控其超时。
   - 收到**后续**信号时：
     - 仅记录简短日志（避免 log spam），不重复 init。

### 5.3 三个子任务的 Shutdown 行为

#### 5.3.1 Job Listener

`start_job_listener` 应该：

- 在循环的每一轮迭代开始时检查 `shutdown_rx`：
  - 若状态为 `Draining`，立刻跳出循环并 `return Ok(())`。
- 不再发起新的 `get_assigned_jobs` 请求。
- 允许当前正在进行的 HTTP 请求完成（避免在中间取消，而是在下一轮检查状态）。

这样可以保证：

- **进入 Draining 后不会再从链上拉取新 Job**。
- 但链上已经写入 `runner_jobs` 的 Job 仍然存在，只是 Runner 不再拉取（下一节通过链侧 `Paused` 状态解决）。

#### 5.3.2 Health Checker

`start_health_checker` 需要区别对待：

- 在 `Running` 状态：按现有逻辑定期发送心跳。
- 当进入 `Draining` 时：
  1. **优先发送一次“下线意图”RPC**（见第 6 章链侧改造），将 Runner 状态标记为 `Paused`。
  2. 一旦确认链侧状态更新为 `Paused`，即可**终止心跳循环**，避免继续向一个“已下线” Runner 发送心跳。

这样可以显著缩短“链上仍认为 Runner 健康但实际正在下线”的窗口。

#### 5.3.3 Job Executor

`start_executor` 在 `Draining` 状态下的行为：

- 不再考虑“新增 Job 限流”以外的行为改变，而是：
  - 当 `shutdown_state == Draining` 时：
    - 仍然从 `job_queue` 中 **继续消费已入队的 Job**，直至队列为空，确保“已拉取 Job 尽力执行”这一语义。
    - 但不再因为 listener 已停止而新增队列元素。
- 当 `job_queue` 为空且 `active_jobs == 0` 时：
  - 可以安全地 `return Ok(())`，向上层表明 Executor 已经排空。

注意：

- 不建议在 `Draining` 状态下“清空队列但不执行”，否则会与链侧“已分配 Job 需执行或超时”的语义不一致。

### 5.4 Drain 协调逻辑

`RunnerNode::start()` 的主逻辑应从当前的 `tokio::select!` 改造成显式 drain 流程：

1. 启动三个子任务（listener / health_checker / executor），并持有它们的 `JoinHandle`。
2. 在 `Running` 状态下，主任务不主动 `join` 任何一个子任务；子任务在正常情况下不会返回。
3. 当 `ShutdownController` 进入 `Draining`：
   - 主任务启动一个 `drain()` 协程：
     - 等待：
       - listener 和 health_checker 因状态变为 `Draining` 而正常返回；
       - executor 在 `job_queue` 为空且 `active_jobs == 0` 时返回。
     - 外围包裹 `tokio::time::timeout(drain_timeout_seconds, ...)`。
   - `drain()` 完成后，主任务退出，进程返回 `0`。

drain 超时时：

- 记录错误级别日志：
  - 未完成 Job 数量
  - 超时时间
  - 可选：列出部分 Job ID（截断防止日志过长）。
- 交由 `systemd` 在 `TimeoutStopSec` 后发送 SIGKILL。

---

## 6. 链侧协议支持：Paused 状态与下线 RPC

为了消除“健康窗口问题”，需要在链侧 Runner Registry / Dispatcher 增加对“暂停中 Runner”的显式支持。

### 6.1 HealthStatus 扩展与语义

Registry 侧已经定义：

- `HealthStatus::Healthy`
- `HealthStatus::Unhealthy`
- `HealthStatus::Paused`
- `HealthStatus::Deregistered`

本方案约定：

- **Healthy**: 正常接受新任务并执行。
- **Paused**: Runner 正在下线或维护中：
  - **不会参与新 Job 的分发**；
  - 但仍然可以提交已有 Job 的结果。
- **Unhealthy**: 节点故障或长时间未发送心跳：
  - 不参与新 Job 分发；
  - 协议方可根据需要实施惩罚 / 声誉衰减。
- **Deregistered**: 完全从 Runner 集合中移除，需要重新注册。

### 6.2 下线 / 恢复 RPC 设计（链侧）

在链侧 REST / JSON-RPC 接口中新增：

1. **Pause Runner**
   - `POST /runner/{address}/pause`
   - 作用：
     - 将对应 `RunnerRegistration.health` 设置为 `Paused`。
   - 前置条件：
     - 仅允许由该 Runner 对应的签名密钥调用（同注册 / heartbeat 的身份认证）。
   - 效果：
     - `get_active_runners` / Runner 选择逻辑中不再返回该 Runner。
2. **Resume Runner**
   - `POST /runner/{address}/resume`
   - 作用：
     - 将 `health` 从 `Paused` 恢复为 `Healthy`，并刷新 `last_heartbeat`。

### 6.3 Runner 触发时机

- 在 Runner 进入 `Draining` 状态时：
  1. Health Checker 检测到 `shutdown_state == Draining`。
  2. 立即发送一次 `Pause Runner` 请求。
  3. 若调用成功：
     - 记录“Runner 进入 Paused 状态”的日志；
     - 停止后续 heartbeat。
  4. 若调用失败（网络异常等）：
     - 按指数退避重试若干次（例如重试 3 次，总时长不超过 10 秒）。
     - 如果仍失败，则回退到“仅停止 heartbeat，依赖 100 blocks timeout”的策略，并在日志中明确记录。

这样可以在大部分场景下，将“仍被视为 Healthy 的窗口”缩短到 **一个 RPC 往返时间** 的级别。

---

## 7. 队列与任务语义

### 7.1 Job 分类

从 Runner 视角，可以将 Job 分为 3 类：

1. **尚未写入 `runner_jobs` 的 Job**：
   - 这些 Job 还没被分配给该 Runner，不需要考虑。
2. **已写入 `runner_jobs`，但尚未被 Runner 拉取的 Job**：
   - 由链侧负责是否在后续重新分配（未来可考虑增加再分发逻辑）。
3. **已被 Runner 拉取的 Job**：
   - 包括：
     - 正在 `job_queue` 中排队等待执行；
     - 已经被 Job Executor 拿出并执行中的任务。

本方案重点约束第 3 类 Job。

### 7.2 Draining 期间的处理策略

**强约束**：

- 对**已拉取 Job**，Runner 应当：
  - 在不超过 `drain_timeout_seconds` 的前提下，尽最大努力执行并提交结果；
  - 除非任务本身因为远端错误等原因失败（正常错误路径）。

具体行为：

- Job Listener 停止后，**不会再拉取新的 Job**，但队列中的 Job 继续由 Executor 消费。
- Executor 在 `Draining` 状态下：
  - 继续从 `job_queue` 取出 Job 执行；
  - 执行完成后照常通过链侧提交结果；
  - 不再新增“多余的并发度”之外的特殊逻辑。

### 7.3 超时与未完成 Job

如果在 `drain_timeout_seconds` 内仍有 Job 未完成：

- Runner 会在日志中记录：
  - `remaining_active_jobs`
  - `remaining_queued_jobs`
  - 部分 Job ID 列表（截断）。
- 然后退出，由 `systemd` 在 `TimeoutStopSec` 到达后可能发 SIGKILL。
- 从链侧视角：
  - 这些 Job 将在 `timeout_blocks` 到达后被认定为超时；
  - 随着经济模型完善，可能触发相关惩罚逻辑（例如 `SlashingReason::Timeout`）。

这部分风险**无法通过单个 Runner 的 shutdown 逻辑完全消除**，但“完美方案”的目标是在大多数实际场景中，将未完成 Job 的数量压缩到可接受的极小值。

---

## 8. 配置与参数建议

### 8.1 Runner 侧参数

新增或强调以下配置（可以通过环境变量或配置文件注入）：

- `RUNNER_DRAIN_TIMEOUT_SECONDS`（默认 `300`）
  - 控制 `Draining` 状态下的最长排空等待时间。
- `RUNNER_SHUTDOWN_LOG_INTERVAL_SECONDS`（默认 `5`）
  - 在 Draining 阶段定期输出排空进度日志的间隔。

同时建议对现有参数给出约束：

- `heartbeat_interval_seconds`（现默认 10s）：
  - 应远小于 `HEARTBEAT_TIMEOUT_BLOCKS` 映射的时间，以便快速发现“心跳缺失”。
- `job_poll_interval_seconds`：
  - 在 Draining 前可以保持现状；
  - 不需要因为 shutdown 专门调整。

### 8.2 任务级超时约定

为减少“任务超过 drain 窗口”的概率，建议：

- 对 LLM / HTTP / MCP 执行器中的 `max_wall_time_seconds` 给出默认上限（例如 240 秒），并在文档中提示运维人员：
  - 若要配置长于 drain 时间的大任务，应明确接受“shutdown 时可能被打断”的风险。

---

## 9. 测试与验证计划

### 9.1 单元测试

- **Shutdown 控制器测试**
  - 验证多次 `initiate_shutdown` 仅第一次生效。
  - 验证 `watch` 订阅者能及时收到状态变化。
- **Job Listener 行为**
  - 模拟 `shutdown_state` 从 `Running` 切换到 `Draining`，验证不再产生新的 `get_assigned_jobs` 调用。
- **Health Checker 行为**
  - 模拟成功与失败的 `Pause Runner` 调用，验证重试与回退逻辑。
- **Job Executor 行为**
  - 验证在 `Draining` 状态下：
    - 队列中的 Job 仍能全部执行；
    - 当队列为空且 `active_jobs == 0` 时，Executor 正常退出。

### 9.2 集成测试

- 本地集成环境下：
  1. 启动 Cowboy node + Runner。
  2. 提交一批 Job（包括 LLM / HTTP / MCP）。
  3. 在不同时机发送 SIGTERM：
     - 无 Job 时；
     - 有少量短Job执行中时；
     - 有多个长Job执行中时。
  4. 验证：
     - Job 结果提交情况；
     - 链侧 Runner 状态转为 `Paused`；
     - 超时 Job 数量符合预期。

### 9.3 运维级演练

- 在 dev / staging 环境执行完整的 binary-swap 流程：
  - 使用 `systemctl stop/start` 进行多轮替换。
  - 统计每次部署过程中：
    - 未完成 Job 数量；
    - 部署总耗时；
    - 是否出现“长时间仍分配新 Job 给将下线 Runner”的情况。

---

## 10. 总结与后续工作

本方案为 Runner 提供了一套**与链侧协议一致、对运维友好、对任务友好的优雅关闭模型**，核心包括：

1. 在 Runner 内部显式建模 `Running/Draining/Stopped` 状态，并通过 watch channel 驱动 3 个子任务的退出时机。
2. 通过新增 `Pause Runner` / `Resume Runner` RPC 与 `HealthStatus::Paused` 语义，消除“健康窗口”带来的协议级不一致。
3. 明确对已拉取 Job 的排空策略与超时风险，使运维与协议方都能预期 shutdown 行为。

后续工作包括：

- 在 `runner-node` 与链侧 REST 接口中逐步落地本方案的各个部分。
- 将关键参数暴露为可配置项，并在 `README` / 运维手册中补充最佳实践。
- 随着经济模型与惩罚逻辑的完善，进一步评估“drain 超时导致 Job 超时”的经济影响，并根据需要调整默认参数。

