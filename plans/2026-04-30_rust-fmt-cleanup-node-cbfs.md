# Plan: Rust Formatting Cleanup — node + cbfs

**Owner:** Tony / Pavilion (merge gatekeepers)
**Status:** Proposed (2026-04-30)
**Source:** Charles DePue's Slack post + on-repo measurement
**Affected repos:** `node` (4 workspaces), `cbfs` (1 workspace), `runner` (1 workspace)

---

## 1. Context

### 1.1 Symptom
PRs to `node` and `cbfs` consistently land with diffs that are 80–90% reformatting noise (import reordering, line-wrap changes, brace/blank-line tweaks) and only 10–20% real code change. Two recent examples Charles cited:

| PR | Original diff | After manual format-only revert | Real change |
|---|---|---|---|
| `node#408` | 62 files / +15,000 lines | 30 files / +13,000 lines | ~5 files / ~800 lines |
| `cbfs#5` | 40 files / +8,000 lines | 27 files / +8,000 lines | similar ratio |

The manual revert took ~2 hours per PR and could not safely strip all noise. Cost: review fatigue, missed bugs, blame churn, false merge conflicts.

### 1.2 Root causes (all four must be fixed)
1. **No pinned toolchain.** Neither repo has `rust-toolchain.toml`. Each contributor uses whatever rustfmt their local rustup happens to install. rustfmt output differs between versions (new style options, default flips).
2. **No `rustfmt.toml`.** No explicit style declaration — output depends on rustfmt's defaults, which are coupled to `edition`. Both repos are on `edition = "2024"`, whose defaults differ from `2021`.
3. **No CI enforcement.** `cargo fmt --check` is not a required check; unformatted code lands and accumulates.
4. **Editor format-on-save.** Most contributors have VSCode / RustRover format-on-save enabled. When a contributor with a different rustfmt version touches any file, the entire file gets reflowed. This is the actual amplifier — without it, drift would accumulate slowly; with it, every edit explodes.

### 1.3 Measured drift (as of 2026-04-30)

Run on each repo's `devnet` HEAD with `rustfmt 1.8.0-stable` (verified identical output under both rustc 1.92.0 and 1.93.0):

| Workspace | Files needing reformat | Diff hunks |
|---|---|---|
| `node/` (main workspace) | **148** | 3,147 |
| `node/pvm/` (workspace-excluded, separate workspace) | **44** | 585 |
| `runner/` | **58** | 765 |
| `cbfs/` | **35** | 118 |
| **Total** | **285 files** | **4,615 hunks** |

> Charles's post said `node = 103` and `cbfs = 35`. The cbfs number matches exactly. The node number (103 vs our 192) differs because Charles measured only the main workspace and skipped `pvm/` (44 files), and there's been further drift in the intervening 2 weeks.

### 1.4 Concrete examples (from `chain/src/application.rs`)
**Import regrouping** (edition 2024 default `style_edition` behavior):
```diff
-use cowboy_types::{Address, Block, Context, Scheme, Transaction, EPOCH, MAX_BLOCK_TRANSACTIONS, SYNCHRONY_BOUND};
+use cowboy_types::{
+    Address, Block, Context, EPOCH, MAX_BLOCK_TRANSACTIONS, SYNCHRONY_BOUND, Scheme, Transaction,
+};
```

**Long-type wrapping policy change**:
```diff
-    dyn Fn(Block) -> std::pin::Pin<Box<dyn std::future::Future<Output = Option<SpeculativeResult>> + Send>>
+    dyn Fn(
+            Block,
+        )
+            -> std::pin::Pin<Box<dyn std::future::Future<Output = Option<SpeculativeResult>> + Send>>
```

**Generic argument folding back to single line**:
```diff
-                        Output = Result<
-                            (Vec<Transaction>, cowboy_types::BlockTableReport),
-                            String,
-                        >,
+                        Output = Result<(Vec<Transaction>, cowboy_types::BlockTableReport), String>,
```

None of these change behavior. All of them appear in PRs as additions/deletions and pollute review.

---

## 2. Scope

### 2.1 In scope
- `node/` — main workspace
- `node/pvm/` — independent workspace (workspace-excluded from `node/Cargo.toml`)
- `runner/` — independent workspace (lives in separate repo)
- `cbfs/` — independent workspace

> Charles's original post named only "node and cbfs". `runner` is a separate repo with the same problem class (765 hunks across 58 files) and the same fix applies — recommend including it in this campaign rather than leaving it for a third pass later.

### 2.2 Out of scope
- TypeScript / JavaScript files (`bench/`, `examples/`, frontend) — not Rust, not affected.
- Generated code (`target/`, `node/pvm/Lib/` if vendored Python).
- Refactoring, lint cleanup, clippy fixes — strictly format-only changes.
- CIP/spec docs and Markdown — out of rustfmt's scope entirely.

### 2.3 Toolchain version pin
Pin to **`1.93.0`** across all three repos.

**Why 1.93 (not Charles's suggested 1.85):**
- Charles proposed 1.85 because that was the Rust release that stabilized edition 2024. Reasonable starting point.
- **Reality (audited 2026-04-30):** all three repos already pin a specific patch version in CI:
  - `node/`: `RUST_VERSION: "1.93.0"` in `pipeline.yml` and `cli-pipeline.yml`
  - `cbfs/`: `RUST_VERSION: "1.93.0"` in `pipeline.yml` and `cbfs-cli-pipeline.yml`
  - `runner/`: `RUST_VERSION: "1.92.0"` in `pipeline.yml`
- All use `dtolnay/rust-toolchain@stable` with explicit `toolchain: ${{ env.RUST_VERSION }}` — so CI is deterministic per repo.
- **The local-toolchain pin must match what CI runs**, not a different version. If we pin local to 1.85 while CI runs 1.93, rustfmt outputs may differ across that 8-version gap → CI's fmt-check rejects code that was just `cargo fmt`'d locally → developers get the worst possible UX (lint failures on freshly-formatted code).

**Action item for Phase 1:** also bump `runner/.github/workflows/pipeline.yml` `RUST_VERSION` from `"1.92.0"` → `"1.93.0"` so the three repos are aligned. One-line change, can ride in the same Phase 1 PR.

### 2.4 CI trigger gap on devnet (discovered 2026-05-02)

When prepping Phase 1 we found that **CI doesn't currently run on devnet** for two of three repos:

| Repo | `pipeline.yml` triggers (before fix) | devnet covered? |
|---|---|---|
| `node` | `push` to any branch (with paths-ignore for cli/) + `workflow_dispatch` | ✅ yes |
| `runner` | `push` only to `main` / `feature/*` / `fix/*` / `hotfix/*`; **no `pull_request` trigger at all** | ❌ no |
| `cbfs` | `push` only to `main`; `pull_request` only with base=`main` | ❌ no |

This means devnet has been an unprotected branch — no automated build/test verification on push or PR to it. For our campaign that's a hard blocker: Phase 2's tree-wide format pass MUST be CI-verified, and Phase 3's fmt-check gate is meaningless if CI doesn't run on devnet at all.

**Action item, bundled into Phase 1 PRs:**
- `cbfs/.github/workflows/pipeline.yml`: add `devnet` to both `push.branches` and `pull_request.branches` (alongside existing `main`).
- `runner/.github/workflows/pipeline.yml`: add `devnet` to `push.branches`, and add a new `pull_request` trigger with `branches: [main, devnet]`.
- `node/`: no change needed — already triggers on any branch.

Note: the trigger extension PR's *own* pull_request to devnet won't run CI yet (workflows are loaded from base branch, which still has the old triggers). That's fine — the toolchain-pin commits in the same PR are validated by local smoke build (§2.5), and once merged, future PRs to devnet (Phase 2/3) will run CI normally.

Out of scope for this campaign (do later if anyone cares): cbfs's `cbfs-cli-pipeline.yml` and node's `cli-pipeline.yml` still only trigger on main. They have path filters that don't match fmt changes anyway, so leaving them alone is fine.

**Sanity check we ran:** rustfmt's internal binary version is `1.8.0-stable` in **both** rustc 1.92 and 1.93. Verified by running `cargo fmt --all -- --check` under both toolchains — file count and hunk count are byte-identical across all four workspaces. So the current 1.92↔1.93 skew between runner and node/cbfs has been benign by luck. We should not rely on this going forward; lockstep the version anyway.

**Why a fixed patch version (vs "stable"):** future rustfmt updates become a deliberate, reviewable bump-PR rather than a silent surprise. When the team is ready, it's a one-line change to `rust-toolchain.toml` + `RUST_VERSION` + a new format-pass PR.

---

## 3. Three-Phase Plan

### Phase 1 — Pin the toolchain (pure config, no code)
**Goal:** Stop version drift. After this lands, every clone gets the same rustfmt automatically.

**Per repo**, add at the repo root:

`rust-toolchain.toml`:
```toml
[toolchain]
channel = "1.93.0"
components = ["rustfmt", "clippy"]
profile = "minimal"
```

**Plus, only for `runner/`**, update `.github/workflows/pipeline.yml`:
```diff
- RUST_VERSION: "1.92.0"
+ RUST_VERSION: "1.93.0"
```
to bring runner's CI in line with node/cbfs.

**Note for `node/`**: also place a copy at `node/pvm/rust-toolchain.toml` since `pvm/` is a separate workspace. (rustup respects the file at the root of whichever workspace `cargo` is invoked from. Without a copy in `pvm/`, contributors running `cargo fmt` in `pvm/` would silently use their global toolchain.)

**Optionally (recommended)** add a `rustfmt.toml` at each workspace root:
```toml
edition = "2024"
max_width = 100
```

Why bother if defaults are fine? Two reasons:
1. Future-proofing: if someone bumps the toolchain to a version where the `edition` default flips again, this file makes the intent explicit.
2. Self-documentation: a reader sees the style choice without having to reason about rustfmt defaults.

Only stable rustfmt options. **Do not** use `group_imports`, `imports_granularity`, `wrap_comments`, or anything else that requires nightly — they will break `cargo fmt` for stable users (which is everyone on CI).

**Acceptance for Phase 1:**
- [ ] PRs merged to `node/devnet`, `runner/devnet`, `cbfs/devnet` (all three target the same branch name; `origin/devnet` confirmed to exist on all three repos as of 2026-04-30)
- [ ] `cargo --version` after fresh clone reports 1.93.0 in all three repos
- [ ] `cargo fmt --version` reports `rustfmt 1.8.0-stable` (matching what 1.93.0 ships)
- [ ] runner's CI `RUST_VERSION` bumped to `1.93.0`
- [ ] No code under `*.rs` changed in this phase

**Phase 1 PR is a no-op for behavior. Land it first, independent of the format pass.** This isolates the toolchain pin from the format churn so that if anything goes wrong with Phase 2, we can revert it without losing the pin.

---

### Phase 2 — Tree-wide format pass
**Goal:** One-shot apply `cargo fmt` everywhere using the now-pinned toolchain. Establishes a clean baseline.

#### 2.1 Pre-flight checklist
**Repo context:** all three repos are private with a small, controllable contributor set (Tony, Pavilion, Martin, Charles, plus a handful of others). No external contributors. This means coordination is direct chat, not formal scheduling.

- [ ] Phase 1 has merged to all three repos (no need for a 24h soak — re-clone locally, confirm `cargo fmt --version` reports `rustfmt 1.8.0-stable`, that's enough)
- [ ] Quick Slack check with **Martin** that no big node PR is mid-merge (per CLAUDE.md he drives big merges). One-message ack is sufficient.
- [ ] `gh pr list` on each repo: identify any open PRs targeting `devnet`. Ping each author with a heads-up that they'll need a quick rebase + `cargo fmt --all` after the format PR lands. (Number of authors should be small enough to ping individually.)
- [ ] Confirm Tony **and** Pavilion are both online during the window (one drives, one reviews — don't single-point this).

#### 2.2 Execution (per repo)
**All three repos target their `devnet` branches.** Verified 2026-04-30: `origin/devnet` exists in all three. cbfs's `origin/devnet` was just created from current `main` (same commit), so it has no divergence from main yet.

For each repo, run:
```bash
git checkout devnet
git pull
git checkout -b chore/tree-wide-fmt-pass

cargo fmt --all                      # in each workspace root

# Verify build + test still pass
cargo build --workspace --all-targets
cargo test --workspace               # full suite

git add -A
git commit -m "chore: tree-wide cargo fmt pass

No semantic changes. Locks in formatter output produced by rustfmt
pinned via rust-toolchain.toml so future PRs only contain real code
changes, not format churn."
git push origin chore/tree-wide-fmt-pass
```

**For `node/`**: must run `cargo fmt --all` separately in **both** `node/` and `node/pvm/` since they're independent workspaces. Recommend a single PR containing both formatted trees so the cleanup is atomic.

```bash
# In the node repo:
( cd .       && cargo fmt --all )    # main workspace (147 files)
( cd pvm     && cargo fmt --all )    # pvm workspace (44 files)
cargo build --workspace --all-targets
cargo test --workspace
( cd pvm && cargo build --workspace --all-targets && cargo test --workspace )
git add -A && git commit ...
```

#### 2.3 PR review
This PR is intentionally large but **mechanically reviewable**:
- Every line should be a format change.
- Reviewer's job is to spot-check that **no semantic change snuck in**.
- Tooling: `git log -p --diff-filter=M | grep -E '^[+-]' | grep -v '^\(+++\|---\)' | grep -vE '^[+-]\s*$'` to find non-trivial token changes — they should all be import reorderings or whitespace.
- Required CI check: `cargo build --workspace --all-targets` and `cargo test --workspace` both green.

Merge **fast** once approved. Every hour open = more in-flight PR conflicts.

#### 2.4 Add `.git-blame-ignore-revs`
**This step is non-optional.** Without it, `git blame` on any line touched by the format pass will point to the format commit, hiding the original author/intent.

After the format PR merges, get its commit SHA, and as a follow-up PR (can be tiny) add at the repo root:

`.git-blame-ignore-revs`:
```
# Tree-wide cargo fmt pass — chore/tree-wide-fmt-pass
<full-40-char-sha>
```

Then update `CLAUDE.md` (or README) with one line:
```
Run once per clone: git config blame.ignoreRevsFile .git-blame-ignore-revs
```

GitHub's web blame view honors this file automatically — no per-user setup needed for that.

#### 2.5 In-flight PR rebase guidance
Send to all open-PR authors after the format PR lands:
```bash
git fetch origin
git checkout my-branch
git merge origin/<main>
# Conflicts will be format-only.
cargo fmt --all                      # also: cd pvm && cargo fmt --all if node
git add -u
git commit
git push
```
The merge conflict markers may look scary but `cargo fmt` after the merge resolves them deterministically.

**Acceptance for Phase 2:**
- [ ] `cargo fmt --all -- --check` returns clean (zero diff) on `node/`, `node/pvm/`, `runner/`, `cbfs/`
- [ ] All test suites green on each workspace
- [ ] `.git-blame-ignore-revs` in place in each repo
- [ ] All in-flight PRs have been rebased and reformatted

---

### Phase 3 — CI enforcement
**Goal:** Make format drift impossible. Required check on protected branches.

#### 3.1 Add CI job
The existing CI lives in `.github/workflows/pipeline.yml` in each repo (not `ci.yml`). Add a new top-level job there:

```yaml
fmt:
  name: cargo fmt
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Install Rust toolchain (rust-toolchain.toml is honored)
      uses: dtolnay/rust-toolchain@stable
      with:
        toolchain: ${{ env.RUST_VERSION }}
        components: rustfmt
    - name: cargo fmt --check (main workspace)
      run: cargo fmt --all -- --check
```

Match the install pattern already used by other jobs in `pipeline.yml` (uses `dtolnay/rust-toolchain@stable` + explicit `RUST_VERSION` env var) for consistency. Once `rust-toolchain.toml` is in place, the explicit `with: toolchain` is technically redundant — the file wins — but keeping it matches the existing CI style and means the env var is the single source of truth if someone later changes it.

**For `node/` only**, add a second step for the pvm workspace:
```yaml
    - name: cargo fmt --check (pvm workspace)
      working-directory: pvm
      run: cargo fmt --all -- --check
```

#### 3.2 Make it a required check
GitHub branch protection rules → `devnet` on **all three repos** (node, cbfs, runner):
- Add `cargo fmt` (or whatever the job name resolves to in GitHub Checks UI) to **required status checks**.
- Do **not** enable this until Phase 2 merges — otherwise every open PR's CI breaks instantly.

#### 3.3 Optional: pre-commit hook (developer-side)
For belt-and-suspenders, optionally provide a `.githooks/pre-commit` script in each repo:
```bash
#!/usr/bin/env bash
set -e
cargo fmt --all -- --check || {
  echo "rustfmt check failed. Run 'cargo fmt --all' and re-commit."
  exit 1
}
```
And document `git config core.hooksPath .githooks` in CONTRIBUTING / CLAUDE.md.

> This is optional. CI is the contract; the hook just gives faster feedback. Skip if it adds friction.

**Acceptance for Phase 3:**
- [ ] CI fmt job runs on every PR to `devnet` / `main`
- [ ] Required status check enabled in branch protection
- [ ] A test PR with deliberate format drift gets blocked

---

## 4. Coordination & Timeline

### 4.1 No formal "freeze window"

All three repos are private with a small contributor set (Tony, Pavilion, Martin, Charles, plus a few others). No external contributors. We do **not** need scheduled freeze events, calendar invites, T-24h pre-announcements, or timezone matrices.

The Phase 2 "freeze" is just an ad-hoc chat message: *"starting fmt pass, please hold devnet merges for ~2h"*. That's the entire ceremony.

Roles:
- **Tony** drives — opens PRs, runs the format pass
- **Pavilion** reviews — second pair of eyes on the Phase 2 PR
- **Martin** — one async ack in chat that no big PR is mid-merge; per CLAUDE.md he runs the larger node merges
- **Charles** — informational only (this campaign is his initiative)

### 4.2 Rollout (~2 working days)

| When | Action | Owner |
|---|---|---|
| Day 1 morning | Open + merge Phase 1 PRs (toolchain pin × 3 repos + runner CI bump 1.92→1.93). Small, mechanical, can ride normal review flow. | Tony |
| Day 1 end of day | Re-clone each repo locally, confirm `cargo fmt --version` reports `rustfmt 1.8.0-stable`. Catches any toolchain surprise before Day 2. | Tony |
| Day 2 (Tue/Wed/Thu, afternoon) | T-30min: chat ping to Martin asking if any big PR is incoming. T-0: chat says *"starting fmt pass on 3 repos, please hold devnet merges for ~2h"*. Then open Phase 2 PRs in parallel; Pavilion reviews; merge as each goes CI-green. | Tony, Pavilion |
| Day 2 right after merges | Follow-up PR per repo adding `.git-blame-ignore-revs` with the format-pass SHA. Direct-message any open-PR authors with the rebase recipe (§2.5). | Tony |
| Day 3 | Phase 3: open CI-enforcement PRs; once merged, enable as required status check in branch protection. | Tony |
| Day 3 + 1 week | Verification audit (§7). | Tony |

Total elapsed: ~2-3 working days. No scheduled events, no formal windows.

### 4.3 Soft heuristics for picking the Day-2 afternoon

Anything that makes both Tony and Pavilion available for ~2 hours works. Light preferences:

- Mid-week (Tue/Wed/Thu); avoid Monday backlog and Friday-evening risk
- Avoid known active merge times if any pattern is obvious
- No need to optimize for Martin/Charles timezones — they only need to ack in chat asynchronously

### 4.4 Hard ordering (the only thing that's strict)

**Phase 1 → Phase 2 → Phase 3.** Phases 1 and 2 can be hours or days apart. Phase 3 must come *after* Phase 2 merges — otherwise the new CI gate fails every open PR instantly.

### 4.5 If something gets in the way

Just postpone Phase 2 by a day. If Martin says "actually I'm pushing a big PR in 30 minutes," do his PR first, then run the fmt pass after. Phase 1 doesn't need to wait — toolchain pins are inert.

---

## 5. Risk & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `cargo fmt` introduces a syntactic bug (rare but documented in rustfmt history) | Low | High | Phase 2 PR runs full `cargo build --workspace --all-targets` + `cargo test --workspace`. If anything breaks, revert immediately. |
| Open PRs become un-rebasable | Low | Low | Small contributor set, ping each author directly. Rebase recipe in §2.5; format conflicts resolve via `cargo fmt` — the easiest possible conflict class. |
| Pinned toolchain (1.93) lacks features we use | Very low | High | Already known to work — node and cbfs CI run 1.93 today; runner runs 1.92 with no apparent feature gap. Phase 1 day-1 verification step catches any surprise. |
| `rust-toolchain.toml` triggers unwanted toolchain download for users with limited bandwidth / restricted networks | Low | Low | `profile = "minimal"` keeps download small (~80 MB). Document the requirement in README. |
| CI becomes blocking before Phase 2 lands | Low | High | Strict ordering: Phase 3 PR is **last** and enabling the required check is a **separate manual step** done after Phase 3 merges. |
| Blame churn from format commit annoys someone investigating history | High | Low | `.git-blame-ignore-revs` (§2.4) — both local and GitHub Web blame honor this. |
| Someone re-introduces drift via a hotfix that bypasses CI | Low | Medium | Branch protection + required check makes bypass impossible without admin override. |

### Hard "do not" list
- **Do not** mix any non-format change into the Phase 2 PR (no clippy --fix, no comment cleanups, no rename, no import ergonomics improvements). Pure rustfmt output only — anything else destroys the PR's mechanical-reviewability property.
- **Do not** use unstable rustfmt options (anything requiring nightly). They break `cargo fmt` for stable users including CI.
- **Do not** skip Phase 1. Without a pinned toolchain, drift returns within months and we redo this work.
- **Do not** enable Phase 3 CI gate before Phase 2 merges.
- **Do not** force-push the format PR after merge — `.git-blame-ignore-revs` references the SHA.

---

## 6. Open questions / decisions needed

### 6.1 What rust version does CI currently run? (RESOLVED 2026-04-30)
Audited:
- `node/`: 1.93.0
- `cbfs/`: 1.93.0
- `runner/`: 1.92.0

Decision: pin all three local toolchains to **1.93.0**, and bump `runner/`'s CI to 1.93.0 in the Phase 1 PR. See §2.3 for full rationale.

### 6.2 Include `runner` repo in this campaign?
Recommend yes. Same problem (58 files / 765 hunks), same fix, same effort. Splitting it out costs another freeze window later.

### 6.3 Add explicit `rustfmt.toml` or rely on defaults?
Recommend yes (explicit). Cost: 2 lines per repo. Benefit: future-proofing against rustfmt default changes; self-documenting style.

### 6.4 Pre-commit hook?
Skip for now. CI is the enforcement; hooks add per-developer setup friction. Revisit if drift starts re-appearing despite CI.

---

## 7. Verification (post-rollout)

Run **one week** after Phase 3 enables:

```bash
# In each repo, on the latest devnet:
cargo fmt --all -- --check && echo "CLEAN" || echo "DRIFT DETECTED"

# In node specifically:
( cd pvm && cargo fmt --all -- --check ) && echo "PVM CLEAN" || echo "PVM DRIFT"
```

Expected: all `CLEAN`. If any drift detected, investigate which PR introduced it — most likely cause is a CI gap (e.g. fmt job didn't run on a specific path, or branch protection wasn't actually enforcing it on a particular branch).

Also do a spot-check on a recent PR's diff: original PR diff size should be roughly proportional to the number of lines actually changed. No more "62 files / 15k lines for an 800-line feature".

---

## 8. Rollback procedures

### Phase 1 rollback
Trivial: revert the `rust-toolchain.toml` PR. No code state was changed.

### Phase 2 rollback
- If found within hours: `git revert <fmt-pass-sha>` and force-merge the revert. In-flight PRs that already rebased onto the format pass will need to rebase again (annoying but recoverable).
- If found after `.git-blame-ignore-revs` is in place: revert both PRs.
- If discovered weeks later: do not revert — the cost of reverting outweighs the benefit. Open a fix-forward PR for whatever specific issue surfaced.

### Phase 3 rollback
- Disable the required-check setting in branch protection (instant).
- Then revert the CI workflow change.

---

## 9. Summary of artifacts to produce

| File | Repos | Purpose |
|---|---|---|
| `rust-toolchain.toml` (channel = `1.93.0`) | node (root + pvm/), cbfs, runner | Pin rustfmt version |
| `rustfmt.toml` (optional but recommended) | each workspace root | Make style explicit |
| `RUST_VERSION` bump 1.92→1.93 in `pipeline.yml` | runner only | Align runner CI with node/cbfs |
| `.git-blame-ignore-revs` | node, cbfs, runner | Hide format commit from blame |
| Format-pass commit | each repo on `devnet` (4 workspaces total: node main, node/pvm, runner, cbfs) | The actual reformat |
| CI fmt job in `pipeline.yml` | each repo (the existing pipeline file, not a new ci.yml) | Enforce going forward |
| Branch protection update | each repo (GitHub UI) | Make CI fmt required |
| README / CLAUDE.md note | each repo | Document `git config blame.ignoreRevsFile` |

---

## 10. References
- Charles DePue's Slack post (2026-04-30): root cause analysis + 3-step proposal
- `node/CLAUDE.md`: workspace structure (`node/` main + `node/pvm/` separate workspace; `runner/` and `cbfs/` are separate repos)
- Measured drift data: §1.3 above (collected 2026-04-30 with rustfmt 1.8.0-stable, verified identical under rustc 1.92.0 and 1.93.0)
- CI version audit (2026-04-30): node + cbfs pin `1.93.0`, runner pins `1.92.0`. All use `dtolnay/rust-toolchain@stable` with explicit `RUST_VERSION` env var.
- Rust 1.85 release notes: https://blog.rust-lang.org/2025/02/20/Rust-1.85.0/ (edition 2024 stabilization — context for why 1.85 was Charles's initial suggestion)
