# PVM FSM codegen 冷编译误拒 stdlib —— warm-pool 掩蔽的顺序依赖假绿

**发现场景**:Marshal 复审 node PR #665(COW-2226 reflection guard + COW-2048 recursion pin),gate run 83,2026-06-10。
**棘轮**:escape `esc-20260610-pvm-fsm-stdlib-cold-misreject` → spawned check `pvm.cold_determinism_stdlib_import_allowed`(pending,severity high,WP §3)。
**相关**:COW-366(pvm/ workspace-excluded → CI 盲区)、COW-1273(warm interpreter pool)。

## 现象(全部在干净 worktree 实测)

| 运行方式 | PR head `48e3b40c` | base devnet `2a286711` |
|---|---|---|
| `cargo test … --test lib`(全套件) | 241 个,211 passed **0 failed** | 同样全绿 |
| `cargo test … --test lib determinism_hardening`(过滤) | **3 FAILED** | **1 FAILED**(`decimal_default_context_is_deterministic`) |

head 上挂的三条:`recursion_limit_is_pinned_under_determinism`、`setrecursionlimit_does_not_leak_across_transactions`(两条均为 #665 新增)、`decimal_default_context_is_deterministic`(基线既有)。**基线也挂 ⇒ 根因非 #665 引入**;但 #665 的 COW-2048 性质只在 warm 掩蔽下被"验证"过。

## 根因链

1. `pvm/crates/codegen/src/pvm_fsm.rs::continuation_meta`(~L110):对带装饰器的(async)函数,装饰器不是 `@runner/actor.continuation` 一律
   `SyntaxError: continuation functions must only use @runner.continuation/@actor.continuation`。
2. stdlib `pylib/Lib/_collections_abc.py` 有 `@abstractmethod async def __anext__/asend/athrow`(L217/242/249)。
3. determinism 路径下 preamble `import re` → enum → functools → collections → `_collections_abc` → **冷解释器必须编译它 → 必死**(报 `exec: InvalidInput`)。
4. **掩蔽**:interpreter pool 按线程复用;全套件跑时,先跑的 lenient 测试把 stdlib 灌进该解释器 `sys.modules`,后续 determinism 测试吃缓存不重编 → 全绿。过滤/单跑 = 新进程 = 冷池 → 触发。
5. CI 永远看不见:pvm/ 是独立 workspace,被 node CI exclude(COW-366 同一盲区)。

## 风险

- **测试学**:任何 determinism 路径测试在全套件下的绿都不可信,必须问"冷池下还绿吗"。
- **共识面(未证实,待查)**:刚重启的节点(冷池)对 import 链触达 `_collections_abc` 编译的 tx,和暖节点结论可能不同(误拒 vs 成功)→ 潜在 cold-vs-warm 分叉。需查生产 pool 预热(COW-1273)是否在 lenient 模式下预灌 stdlib 兜底。

## 修复方向

`continuation_meta`(或其调用方 pvm_fsm 变换入口)对**非 actor 代码**(stdlib/特权编译)跳过 FSM 校验,或对非 continuation 装饰器返回 `Ok(None)` 而非报错——只在确认是 continuation 候选(如 async def 且装饰器列表含 `*.continuation`)时才施加"不得有额外装饰器"约束。

## 测试骨架(去 node 实现;落 `pvm/crates/pvm-runtime/tests/regression/determinism_hardening.rs`)

```rust
/// Marshal invariant `pvm.cold_determinism_stdlib_import_allowed`
/// (escape esc-20260610-pvm-fsm-stdlib-cold-misreject, WP §3).
///
/// A COLD interpreter must compile the whitelisted stdlib import chain under
/// determinism enforcement. The spawned thread is the point of the test: the
/// interpreter pool is per-thread, so a fresh thread = cold pool, making this
/// order-independent even inside a full-suite run (warm-pool sys.modules
/// caching is exactly what masked the bug).
#[test]
#[ignore = "esc-20260610-pvm-fsm-stdlib-cold-misreject: pvm_fsm::continuation_meta mis-rejects stdlib decorated async defs (e.g. @abstractmethod async def in _collections_abc.py) on cold determinism compile; un-ignore — and flip the pack invariant to active — once the codegen skips non-actor/non-continuation decorators"]
fn cold_interpreter_compiles_whitelisted_stdlib_under_determinism() {
    use pvm_runtime::simulate::{SimulationHost, default_simulation_context};
    use pvm_runtime::{DeterminismOptions, ExecutionOptions, execute_tx_with_options};

    let out = std::thread::spawn(|| {
        let code = br#"
import re
def main(p):
    return re.match(r"c", "cold").group(0).encode()
"#;
        let mut host = SimulationHost::new(10_000_000, default_simulation_context());
        let exec = ExecutionOptions::default()
            .with_entrypoint("main")
            .with_determinism(DeterminismOptions::actor_execution());
        execute_tx_with_options(&mut host, code, b"", &exec)
    })
    .join()
    .expect("thread");

    let out = out.expect(
        "cold determinism execution must compile whitelisted stdlib \
         (re -> enum -> functools -> collections -> _collections_abc)",
    );
    assert_eq!(String::from_utf8(out).unwrap(), "c");
}
```

注册的 run_command 故意是**单测过滤跑**(新进程=冷池),别"优化"成全套件:

```
cargo test --manifest-path pvm/Cargo.toml -p pvm-runtime --test lib \
  regression::determinism_hardening::cold_interpreter_compiles_whitelisted_stdlib_under_determinism -- --exact
```

(骨架用了 spawn-thread 双保险:即便有人在全套件里跑它,也仍然是冷池。落地时先验证 spawn 线程确实拿到冷池——若 pool 不是 thread-local 则去掉 spawn,仅靠过滤跑。)

## 复现命令

```bash
# 任一干净 checkout(head 或 devnet base 均可):
cargo test --manifest-path pvm/Cargo.toml -p pvm-runtime --test lib determinism_hardening
# → decimal_default_context_is_deterministic FAILED(+ head 上两条 recursion)
cargo test --manifest-path pvm/Cargo.toml -p pvm-runtime --test lib
# → 全绿(warm-pool 掩蔽)
```
