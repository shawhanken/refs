# Node Repository CI/CD Deployment Plan

> This document defines the CI/CD deployment configuration for the `cowboyinc/node` repository, for Martin to finalize the GitHub Actions Pipeline.
> The current scope is limited to **Dev environment** auto-deployment only. Staging and Production will be discussed separately.

---

## 0. Scope of This Document

Our development team is responsible for **code development, testing, and deployment to the Dev environment only**. The promotion flow from Dev → Staging → Production (including tag-based promotion, approval gates, etc.) is managed by Martin and the infrastructure team.

This document provides the specific details Martin needs from our team to configure the Dev environment CI/CD pipeline:
1. Branch names for deployment
2. Pre-deployment tests to run
3. Post-deployment tests (smoke tests) to run

---

## 1. Deployment Branch

| Repository | Deployment Branch | Description |
|---|---|---|
| `cowboyinc/node` | `main` | Auto-deploy triggered on every merge to `main` |

**Development Workflow:**

- The development team creates feature branches for development and testing (e.g., `devnet-runner-integration`, `feature/xxx`, etc.)
- Once development is complete and the branch has been tested and stabilized, it is merged into `main` via Pull Request
- A merge to `main` indicates the code has been verified by the development team and is ready for deployment
- Branch naming is not enforced at this time. If the Feature branch ephemeral environment functionality is needed in the future, we will adopt the `feature/*` naming convention as described in Martin's Deployment Strategy

**Related Repositories:**

| Repository | Relationship | CI/CD Notes |
|---|---|---|
| `cowboyinc/node` | Primary — the validator node | Full CI/CD pipeline (this document) |
| `cowboyinc/pvm` | Git submodule of `node` | PVM changes are pulled into `node` via submodule update; `node` CI automatically builds and tests PVM code. No separate pipeline needed. |
| `cowboyinc/runner` | Independent service | Runner has its own build/test cycle. A separate CI/CD plan will be provided when runner deployment is included in the pipeline. |

---

## 2. Pre-deployment Testing

After code is merged into `main`, the Pipeline automatically executes the following steps:

### 2.1 Build Check

```bash
cargo build --release
```

Verifies that the code compiles successfully in the CI environment.

### 2.2 Unit Tests

```bash
cargo test --workspace
```

Runs all unit tests across all crates in the workspace (including the PVM submodule).

> **Note:** Test cases are maintained by the development team within the code repository (`tests/` directories and `#[test]` annotations within each crate), and are updated alongside the business code. The Pipeline configuration only needs to call `cargo test --workspace` — no Pipeline modifications are required when test content changes.

---

## 3. Post-deployment Testing (Smoke Test)

After deployment to the Dev environment is complete, the Pipeline executes a health check script:

```bash
./scripts/smoke-test.sh
```

### 3.1 Script Location

The script is stored in the `cowboyinc/node` repository:

```
cowboyinc/node/
           └── scripts/
                  └── smoke-test.sh
```

### 3.2 Check Items

The script is maintained by the development team. Initial check items include the following (to be expanded as needed):

| Check Item | Method | Pass Criteria |
|---|---|---|
| Node Health | `GET /health` | Returns HTTP 200 |
| RPC Availability | Call basic RPC method | Returns valid response |
| Block Sync | Query latest block height | Height > 0 |

> **Note:** Same as pre-deployment testing, the specific Smoke Test checks are maintained by the development team within the repository. The Pipeline configuration only needs to call `./scripts/smoke-test.sh` — no Pipeline modifications are required when check content changes.

---

## 4. Pipeline Configuration Suggestions (For Reference Only)

Based on the above, the `pipeline.yml` test job can be updated to:

```yaml
test:
  name: Test
  if: github.event_name == 'push'
  runs-on: ubuntu-latest
  steps:
    - name: Checkout
      uses: actions/checkout@v4
      with:
        submodules: recursive  # Ensure PVM submodule is checked out

    - name: Install Rust
      uses: dtolnay/rust-toolchain@stable
      with:
        toolchain: "1.89.0"  # Must match rust-toolchain.toml in the repository

    - name: Build
      run: cargo build --release

    - name: Unit Tests
      run: cargo test --workspace
```

Add a Smoke Test step after deployment:

```yaml
# Add after "Wait for Instance Refresh" and before Slack notification in the deploy-dev job:
    - name: Smoke Test
      run: |
        chmod +x ./scripts/smoke-test.sh
        ./scripts/smoke-test.sh
```

---
