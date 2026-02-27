# Runner Node Graceful Shutdown Plan

> **Status**: Draft (aligned with current implementation and CIP-2)  
> **Author**: Cowboy Core Team  
> **Created**: 2026-02-26  
> **Scope**: `cowboyinc/runner` repo, Runner node process  

---

## 1. Design Goals

- **Safety**: Avoid killing in-flight LLM / HTTP / MCP jobs whenever possible, minimizing lost results and duplicate executions.
- **Protocol Consistency**: Align strictly with on-chain Runner Registry / Job Dispatcher semantics for health status and job assignment; do not create “ghost runners” or “dangling jobs” at the protocol level.
- **Operability**: Support binary-swap deployments (`stop → swap binary → start`) and integrate cleanly with `systemd` timeouts.
- **Observability**: Clearly expose shutdown state, drain progress, and unfinished job counts via logs and metrics.
- **Evolvability**: Roll out in phases, compatible with the current implementation (only `Healthy/Unhealthy`), then incrementally introduce `Paused` and related chain-side RPCs.

---

## 2. Current State (Runner Node & Chain Protocol)

### 2.1 Runner Node Structure (Off-Chain)

See `runner/crates/runner-node/src/node.rs` and `refs/runner/RUNNER_SYSTEM_DESIGN.md`:

- `RunnerNode::start()` currently spawns three long-running async tasks:
  - **Job Listener**: Polls chain REST `GET /runner/{address}/jobs` and pushes new jobs into the local `job_queue`.
  - **Health Checker**: Periodically calls the chain `heartbeat` endpoint to update `last_heartbeat` on-chain.
  - **Job Executor**: Pops jobs from `job_queue`, enforces `max_concurrent_jobs`, invokes concrete executors (LLM / HTTP / MCP), and submits results via chain REST.

### 2.2 On-Chain Runner Registry / Dispatcher Behavior

- **Registry health check** (`node/chain/src/runner/registry.rs`):
  - Maintains `RunnerRegistration`, including fields like `health` and `last_heartbeat`.
  - If no heartbeat is received for more than `HEARTBEAT_TIMEOUT_BLOCKS = 100` blocks, sets `health = Unhealthy`, and the runner stops participating in job assignment.
- **Job Dispatcher assignment** (`node/chain/src/runner/dispatcher.rs`):
  - For each assignment, filters for runners with `health == Healthy` from `get_active_runners`.
  - For selected runners, writes the job ID into `runner_jobs_key(runner)`, which is then returned by `GET /runner/{addr}/jobs`.
  - There is **no explicit “cancel assignment / pause dispatch” API** today; behavior is driven by health status and timeouts.

### 2.3 Existing Issues

If we simply “stop listener and health checker on SIGTERM, then drain active jobs” on top of the current implementation, we get:

- **Health window issue**: After stopping heartbeat, the chain still sees the runner as `Healthy` for roughly 0–100 seconds and may continue assigning new jobs. The local listener has stopped and will not pull them, so these jobs can only expire by timeout.
- **Queue semantics issue**: Jobs already written into `runner_jobs` but not yet pulled or still sitting in the local `job_queue`—if dropped during shutdown—appear on-chain as “assigned but never attempted”.

This plan’s goal is to **explicitly model a “runner shutting down” state** and define behavior consistent with the chain-side protocol.

---

## 3. Overall Shutdown Model

### 3.1 State Machine

We introduce three runtime states for a Runner node:

1. **Running**
   - Normal operation: listening for jobs, sending heartbeats, executing jobs.
2. **Draining**
   - Shutdown signal (SIGTERM / SIGINT) received; stop accepting new work and drain all locally known jobs (in-flight + queued).
3. **Stopped**
   - All local jobs are finished (or drain timeout reached); the main process exits.

State transitions:

- `Running --(SIGTERM/SIGINT)--> Draining`
- `Draining --(active_jobs == 0 && job_queue empty)--> Stopped`
- `Draining --(drain timeout)--> Stopped` (some jobs may be unfinished and will be handled by protocol-level timeouts / penalties).

### 3.2 Core Constraints

- **Constraint 1: No new assignments while Draining**
  - Once a runner enters `Draining`, we must ensure `get_active_runners` quickly stops returning it, so the dispatcher no longer assigns new jobs to it.
- **Constraint 2: Uniform handling for locally known jobs**
  - For jobs the runner is already aware of (pulled / queued / in execution), behavior must be clearly defined:
    - Default strategy: **do our best to execute and submit results** unless we hit the drain timeout.
- **Constraint 3: Transparent timeout / penalty semantics**
  - If `systemd` eventually sends SIGKILL after our drain timeout, some jobs may remain unfinished; these are subject to protocol-level timeouts and potential penalties and must be clearly documented.

---

## 4. Signal Handling & System Integration

### 4.1 Signal Sources & Priorities

- **SIGTERM**
  - Primary entry point for graceful shutdown, sent by `systemd`, deployment scripts, or manual `kill`.
  - Serves as the **canonical trigger** for graceful shutdown in this design.
- **SIGINT**
  - From user `Ctrl-C`. Treated the same as SIGTERM to simplify local development and testing.
- **SIGKILL**
  - Sent only by the OS or `systemd` in extreme cases (timeouts, hard failures).
  - Cannot be caught; no cleanup logic can run. Considered the “last resort”.

### 4.2 Recommended systemd Unit

Runner’s systemd unit (implemented in a separate PR) should look like:

```ini
[Service]
Type=simple
ExecStart=/usr/local/bin/cowboy-runner
Restart=on-failure
KillSignal=SIGTERM
TimeoutStopSec=330

# Ensure SIGTERM is sent first; SIGKILL is only used after timeout.
KillMode=mixed
```

- **KillSignal=SIGTERM**: Triggers the runner to enter `Draining`.
- **TimeoutStopSec=330**: Slightly larger than the internal `drain_timeout_seconds` (default 300s) to leave room for logging and cleanup.
- **KillMode=mixed**: Sends SIGTERM to the main process first; SIGKILL is used only if necessary.

### 4.3 Deployment Pipeline Contract

At CI / ops level, deployments should follow:

1. `systemctl stop cowboy-runner` (send SIGTERM → wait for drain completion or timeout).
2. Replace the runner binary (e.g., download from S3 and atomically swap).
3. `systemctl start cowboy-runner`.

Requirements:

- Deployment scripts **MUST NOT** send SIGKILL directly; always use `systemctl stop`.
- For fast rollback, prefer restarting the old binary with `systemctl start` instead of force-killing a draining process.

---

## 5. In-Process Shutdown Design

### 5.1 Shutdown Control Interface

Inside `runner-node`, introduce a lightweight shutdown controller:

- Use `tokio::sync::watch::channel<ShutdownState>` (or `bool` + an enum wrapper) to broadcast state:
  - `Running` / `Draining`.
- Expose read-only handles:
  - `shutdown_rx_for_listener`
  - `shutdown_rx_for_health_checker`
  - `shutdown_rx_for_executor`
- Provide a write API (used only by the main thread / signal handler):
  - `fn initiate_shutdown(reason: ShutdownReason)` – switches state to `Draining`, records timestamp and reason.

### 5.2 Signal Handling Logic

In the main binary (`runner/src/main.rs`):

1. On startup, create a `ShutdownController` (holding the `watch::Sender` and `Instant::now()`).
2. Register handlers for SIGTERM / SIGINT:
   - On the **first** signal:
     - Log details (including current active job count and queue length).
     - Call `ShutdownController::initiate_shutdown(Reason::Signal(SigTerm))`.
     - Spawn a `drain()` async task (see below) and monitor its timeout.
   - On **subsequent** signals:
     - Only log a short message (to avoid log spam); do not re-initiate.

### 5.3 Shutdown Behavior of the Three Subtasks

#### 5.3.1 Job Listener

`start_job_listener` should:

- At the beginning of each loop iteration, check `shutdown_rx`:
  - If state is `Draining`, immediately break the loop and `return Ok(())`.
- Avoid starting new `get_assigned_jobs` requests in `Draining`.
- Allow any in-flight HTTP requests to complete; check shutdown state on the next iteration instead of cancelling mid-request.

This guarantees:

- **No new jobs are pulled after entering Draining**.
- Jobs already written into `runner_jobs` still exist on-chain but will no longer be pulled by this runner (the `Paused` state on-chain will handle future assignments).

#### 5.3.2 Health Checker

`start_health_checker` needs to distinguish states:

- In `Running`: behave as today, periodically sending heartbeats.
- On entering `Draining`:
  1. **First send a “going offline” RPC** (see Section 6) to mark the runner’s on-chain state as `Paused`.
  2. Once `Paused` is confirmed, **terminate the heartbeat loop**, avoiding heartbeats from a runner that is already offline.

This shrinks the window where “the chain believes the runner is healthy but it is actually shutting down” to one RPC round trip.

#### 5.3.3 Job Executor

`start_executor` behavior in `Draining`:

- Do not change concurrency accounting beyond what is already implemented, but:
  - When `shutdown_state == Draining`:
    - Continue **consuming jobs already present in `job_queue`** until the queue is empty, ensuring that we make a best effort for jobs we’ve already pulled.
    - Do not add new jobs to the queue (listener is already stopped).
- When `job_queue` is empty and `active_jobs == 0`:
  - Safely `return Ok(())`, indicating the executor has fully drained.

Note:

- It is **not** recommended to “clear the queue without executing” in `Draining`, otherwise protocol semantics (“assigned jobs must either be executed or time out”) are violated.

### 5.4 Drain Coordination Logic

The main logic of `RunnerNode::start()` should be refactored from the current `tokio::select!` pattern into an explicit drain flow:

1. Spawn the three subtasks (listener / health_checker / executor) and keep their `JoinHandle`s.
2. In `Running`, do not proactively `await` any of them; under normal operation, they never return.
3. When the `ShutdownController` enters `Draining`:
   - Spawn a `drain()` coroutine that:
     - Waits for:
       - Listener and health_checker to return normally once they see `Draining`.
       - Executor to return once `job_queue` is empty and `active_jobs == 0`.
     - Wrap the wait in `tokio::time::timeout(drain_timeout_seconds, ...)`.
   - Once `drain()` completes, exit the main task and return exit code `0`.

On drain timeout:

- Log at error level:
  - Number of unfinished jobs.
  - Timeout duration.
  - Optionally a truncated list of job IDs (to avoid bloated logs).
- Let `systemd` send SIGKILL if `TimeoutStopSec` is reached.

---

## 6. Chain-Side Support: Paused State & Offline RPC

To eliminate the “health window” problem, the on-chain Runner Registry / Dispatcher must explicitly support a “runner in maintenance / shutting down” state.

### 6.1 HealthStatus Extensions & Semantics

The Registry already defines:

- `HealthStatus::Healthy`
- `HealthStatus::Unhealthy`
- `HealthStatus::Paused`
- `HealthStatus::Deregistered`

This plan assigns the following semantics:

- **Healthy**: Fully operational; accepts and executes new jobs.
- **Paused**: Runner is undergoing maintenance or shutting down:
  - **Must not participate in new job assignment**;
  - Still allowed to submit results for already assigned jobs.
- **Unhealthy**: Node failure or long-term heartbeat loss:
  - Excluded from new job assignment;
  - Subject to reputation decay or penalties as the economics model evolves.
- **Deregistered**: Completely removed from the active runner set; requires re-registration.

### 6.2 Pause / Resume RPC Design (Chain-Side)

Extend the chain REST / JSON-RPC API with:

1. **Pause Runner**
   - `POST /runner/{address}/pause`
   - Behavior:
     - Set `RunnerRegistration.health` for the given runner to `Paused`.
   - Preconditions:
     - Only callable by the runner’s own keypair (same auth as registration / heartbeat).
   - Effect:
     - `get_active_runners` and runner selection logic no longer return this runner.
2. **Resume Runner**
   - `POST /runner/{address}/resume`
   - Behavior:
     - Set `health` from `Paused` back to `Healthy`, and refresh `last_heartbeat`.

### 6.3 Runner Trigger Points

When the runner enters `Draining`:

1. The Health Checker observes `shutdown_state == Draining`.
2. It immediately sends a `Pause Runner` request.
3. If the call succeeds:
   - Log that the runner entered `Paused`.
   - Stop subsequent heartbeats.
4. If the call fails (e.g., network failure):
   - Retry with exponential backoff a limited number of times (e.g., 3 retries within ~10 seconds).
   - If still failing, fall back to “stop heartbeat and rely on the 100-block timeout”, and log this explicitly.

In most cases, this reduces the “Healthy but actually shutting down” window to **one RPC round-trip**.

---

## 7. Queue & Job Semantics

### 7.1 Job Categories

From a runner’s perspective, jobs fall into three categories:

1. **Jobs not yet written into `runner_jobs`**:
   - Not assigned to this runner; irrelevant for shutdown.
2. **Jobs written into `runner_jobs` but not yet pulled by this runner**:
   - Whether they are later reassigned is up to the chain (future protocol could add reassignment).
3. **Jobs already pulled by the runner**:
   - Including:
     - Jobs currently queued in `job_queue`.
     - Jobs already taken out by the executor and actively running.

This plan focuses on Category 3.

### 7.2 Behavior While Draining

**Hard requirement**:

- For **already pulled jobs**, the runner should:
  - Make a best effort to execute and submit results within `drain_timeout_seconds`;
  - Except when the job itself fails for normal reasons (e.g., remote API error).

Concretely:

- After the Job Listener stops, it **never pulls new jobs**, but jobs already in `job_queue` continue to be processed by the executor.
- In `Draining`, the executor:
  - Keeps taking jobs from `job_queue` and executing them.
  - Submits results to the chain as usual once they complete.
  - Does not introduce new behavior beyond honoring the concurrency limit.

### 7.3 Timeouts & Unfinished Jobs

If jobs remain unfinished when `drain_timeout_seconds` elapses:

- The runner logs:
  - `remaining_active_jobs`
  - `remaining_queued_jobs`
  - A truncated list of job IDs.
- Then exits, and `systemd` may eventually send SIGKILL once `TimeoutStopSec` is reached.
- From the chain’s point of view:
  - These jobs will be considered timed out once `timeout_blocks` elapses.
  - As the economics model matures, they may trigger penalties (e.g., `SlashingReason::Timeout`).

This risk **cannot be completely eliminated** by shutdown logic within a single runner, but a “near-perfect” design minimizes the number of unfinished jobs under realistic workloads.

---

## 8. Configuration & Parameter Recommendations

### 8.1 Runner-Side Parameters

Introduce or emphasize the following configs (via env vars or config files):

- `RUNNER_DRAIN_TIMEOUT_SECONDS` (default `300`)
  - Maximum time spent in `Draining` waiting for local jobs to finish.
- `RUNNER_SHUTDOWN_LOG_INTERVAL_SECONDS` (default `5`)
  - Interval for periodic drain progress logs while in `Draining`.

Constraints on existing settings:

- `heartbeat_interval_seconds` (currently default 10s):
  - Should be significantly smaller than the time mapped by `HEARTBEAT_TIMEOUT_BLOCKS`, to detect missing heartbeats quickly.
- `job_poll_interval_seconds`:
  - Can remain as-is before entering `Draining`;
  - No special tuning is required specifically for shutdown.

### 8.2 Per-Job Timeout Guidelines

To reduce the probability that jobs outlive the drain window, we recommend:

- Setting reasonable defaults for `max_wall_time_seconds` in LLM / HTTP / MCP executors (e.g., 240 seconds), and documenting for ops that:
  - If they configure longer execution times than the drain window, they **must** accept the risk that some jobs may be interrupted during shutdown.

---

## 9. Testing & Validation Plan

### 9.1 Unit Tests

- **Shutdown controller tests**
  - Verify multiple calls to `initiate_shutdown` only take effect once.
  - Verify `watch` subscribers receive state transitions promptly.
- **Job Listener behavior**
  - Simulate `shutdown_state` transitioning from `Running` to `Draining` and assert no further `get_assigned_jobs` calls occur.
- **Health Checker behavior**
  - Simulate successful and failed `Pause Runner` calls; verify retry and fallback logic.
- **Job Executor behavior**
  - In `Draining`, verify:
    - All jobs currently in the queue are executed.
    - The executor exits when the queue is empty and `active_jobs == 0`.

### 9.2 Integration Tests

- In a local integration environment:
  1. Start Cowboy node + Runner.
  2. Submit a batch of jobs (LLM / HTTP / MCP).
  3. Send SIGTERM at different times:
     - When there are no jobs.
     - When a few short jobs are running.
     - When multiple long-running jobs are in flight.
  4. Verify:
     - Job result submission behavior.
     - Runner status transitions to `Paused` on-chain.
     - The number of timed-out jobs matches expectations.

### 9.3 Ops-Level Drills

- In dev / staging, run full binary-swap drills:
  - Use `systemctl stop/start` in multiple deployment cycles.
  - Record for each deployment:
    - Count of unfinished jobs.
    - Total deployment duration.
    - Whether jobs continued to be assigned to a runner that was already shutting down.

---

## 10. Summary & Follow-Ups

This plan provides a **protocol-consistent, ops-friendly, and job-friendly** graceful shutdown model for runners, centered on:

1. Explicitly modeling `Running / Draining / Stopped` inside the runner and using a watch channel to coordinate the three core subtasks.
2. Introducing `Pause Runner` / `Resume Runner` RPCs and `HealthStatus::Paused` semantics to eliminate protocol-level inconsistencies during shutdown.
3. Clarifying the drain strategy and timeout risks for already pulled jobs, so both ops and protocol engineers can reason about shutdown behavior.

Follow-up work:

- Incrementally implement this plan in `runner-node` and the chain REST API.
- Expose key parameters as configuration options and document best practices in the `README` and operations guides.
- As the economics / slashing model matures, further evaluate the impact of “drain timeout → job timeout” and adjust default settings accordingly.

