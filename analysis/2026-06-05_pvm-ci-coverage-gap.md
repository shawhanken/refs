# node CI gap: the `pvm/` workspace is never tested in CI

**Found while reviewing PR #609 (COW-366 local PVM `--strict`).** A broken
strict happy path shipped twice with green CI because the `pvm/` tests never run
there.

## Root cause

`pvm/` is a **workspace-excluded separate Cargo workspace** (excluded from
`node/Cargo.toml`). The `Pipeline` workflow's test step runs only the main
workspace:

- `.github/workflows/pipeline.yml` — `Test (shard …)`:
  `cargo nextest run --workspace …` (run from repo root → main workspace only)
- `Lint`: `cargo clippy --workspace …` (main workspace only)

`--workspace` does **not** descend into the excluded `pvm/` workspace, so
`pvm/crates/pvm-runtime/tests/…` (incl. the `simulate` strict-determinism
regression suite) is never compiled or run in CI. Note the `Format` job already
treats `pvm/` as a separate unit (`cargo fmt --check (pvm workspace)` with
`working-directory: pvm`) — Test/Lint just never got the same treatment.

Concrete escape: PR #609 had 4 red `pvm-runtime` regression tests
(`run_simulation_strict_allows_*`, `…_lenient_by_default_…`) on a clean
checkout, yet every CI check was green.

## Fix — add a `pvm/` test job (drop into `pipeline.yml`)

Mirrors the existing `Test` shard scaffolding (toolchain pin, sccache,
rust-cache, build deps, cross-repo git credential helper) but scoped to `pvm/`
via `working-directory`. `pvm/` is small enough not to need sharding.

```yaml
  # ===========================================================================
  # TEST (pvm workspace) — pvm/ is workspace-excluded from node/Cargo.toml, so
  # `cargo …​ --workspace` from the repo root never compiles or runs it. Run its
  # suite explicitly (mirrors the `Format` job's pvm step). Without this, red
  # pvm-runtime tests pass CI silently (see COW-366 / PR #609).
  # ===========================================================================
  test-pvm:
    name: Test (pvm workspace)
    if: github.event_name == 'push' || github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request'
    needs: [lint]
    runs-on: ubuntu-latest-m
    env:
      RUSTC_WRAPPER: sccache
      SCCACHE_GHA_ENABLED: "true"
    steps:
      - name: Checkout
        uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4

      # Same cross-repo PAT / GIT_ASKPASS setup the lint/test jobs use, if the
      # pvm workspace resolves any private [patch.crates-io] deps. Copy the
      # "Configure git credential helper for cross-repo fetches" step verbatim
      # from the Test job if needed.

      - name: Install Rust ${{ env.RUST_VERSION }}
        uses: dtolnay/rust-toolchain@29eef336d9b2848a0b548edc03f92a220660cdb8 # stable
        with:
          toolchain: ${{ env.RUST_VERSION }}

      - name: Install sccache
        uses: mozilla-actions/sccache-action@2df7dbab909c49ab7d3382d05da469f3f975c2d6 # v0.0.7

      - name: Rust cache
        uses: Swatinem/rust-cache@42dc69e1aa15d09112580998cf2ef0119e2e91ae # v2
        with:
          workspaces: pvm

      - name: Install build dependencies
        run: |
          # copy the same apt/deps step the Test job uses

      - name: Run pvm tests
        working-directory: pvm
        run: cargo test --workspace
        env:
          CARGO_BUILD_JOBS: 4
```

### Notes
- Uses plain `cargo test` (not `nextest`): the `pvm/` workspace may not ship a
  `nextest` `ci` profile / partition config. Swap to `cargo nextest run
  --workspace` if `pvm/.config/nextest.toml` exists.
- `Rust cache` `workspaces: pvm` keys the cache to the pvm workspace dir.
- Alternative (lower effort, less parallelism): append a step to the existing
  `Test` shard job guarded by `if: matrix.shard == 1` —
  `working-directory: pvm`, `run: cargo test --workspace`. A dedicated job is
  preferred so a pvm failure is attributable and runs in parallel.

## Complementary guard (already in place)

Marshal ratchet **`esc-20260605-pvm-ci-gap`** registers invariant
`pvm.strict_simulation_allows_valid_code`
(`marshal/src/marshal_pack_cowboy/pack.py`), which runs the strict happy-path
test via `cargo test --manifest-path pvm/Cargo.toml -p pvm-runtime …` on every
Marshal gate touching `pvm/crates/pvm-runtime/src/{simulate,determinism,lib}`.
That catches it at review time; this CI job catches it on every push.
