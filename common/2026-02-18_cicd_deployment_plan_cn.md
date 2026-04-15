# Node 仓库 CI/CD 部署方案

> 本文档定义了 `cowboyinc/node` 仓库的 CI/CD 部署配置，供 Martin 完成 GitHub Actions Pipeline 的最终配置。
> 当前范围仅限于 **Dev 环境** 的自动部署。Staging 和 Production 环境将另行讨论。

---

## 0. 本文档范围

我们开发团队**仅负责代码开发、测试以及部署到 Dev 环境**。从 Dev → Staging → Production 的推进流程（包括 tag promotion、审批门禁等）由 Martin 和基础设施团队管理。

本文档提供 Martin 配置 Dev 环境 CI/CD 流水线所需的具体细节：
1. 部署使用的分支
2. 部署前需要运行的测试
3. 部署后需要运行的测试（冒烟测试）

---

## 1. 部署分支

| 仓库 | 部署分支 | 说明 |
|---|---|---|
| `cowboyinc/node` | `main` | 每次合并到 `main` 时自动触发部署 |

**开发工作流：**

- 开发团队创建功能分支进行开发和测试（例如 `devnet-runner-integration`、`feature/xxx` 等）
- 开发完成后，分支经过测试和稳定验证，通过 Pull Request 合并到 `main`
- 合并到 `main` 表示代码已通过开发团队验证，可以进行部署
- 目前不强制要求分支命名规范。如果未来需要功能分支临时环境功能，将按照 Martin 部署策略中描述的 `feature/*` 命名约定执行

**相关仓库：**

| 仓库 | 关系 | CI/CD 说明 |
|---|---|---|
| `cowboyinc/node` | 主仓库 — 验证节点 | 完整的 CI/CD 流水线（本文档） |
| `cowboyinc/pvm` | `node` 的 Git 子模块 | PVM 的变更通过子模块更新拉入 `node`；`node` 的 CI 会自动构建和测试 PVM 代码，无需单独流水线。 |
| `cowboyinc/runner` | 独立服务 | Runner 有自己的构建/测试周期。当 Runner 部署纳入流水线时，将另行提供 CI/CD 方案。 |

---

## 2. 部署前测试

代码合并到 `main` 后，Pipeline 自动执行以下步骤：

### 2.1 构建检查

```bash
cargo build --release
```

验证代码在 CI 环境中能够成功编译。

### 2.2 单元测试

```bash
cargo test --workspace
```

运行工作空间中所有 crate 的全部单元测试（包括 PVM 子模块）。

> **注意：** 测试用例由开发团队在代码仓库中维护（各 crate 中的 `tests/` 目录和 `#[test]` 注解），并随业务代码一同更新。Pipeline 配置只需调用 `cargo test --workspace` — 测试内容变更时无需修改 Pipeline。

---

## 3. 部署后测试（冒烟测试）

部署到 Dev 环境完成后，Pipeline 执行健康检查脚本：

```bash
./scripts/smoke-test.sh
```

### 3.1 脚本位置

脚本存放在 `cowboyinc/node` 仓库中：

```
cowboyinc/node/
           └── scripts/
                  └── smoke-test.sh
```

### 3.2 检查项

该脚本由开发团队维护。初始检查项包括以下内容（可根据需要扩展）：

| 检查项 | 方法 | 通过标准 |
|---|---|---|
| 节点健康状态 | `GET /health` | 返回 HTTP 200 |
| RPC 可用性 | 调用基本 RPC 方法 | 返回有效响应 |
| 区块同步 | 查询最新区块高度 | 高度 > 0 |

> **注意：** 与部署前测试相同，具体的冒烟测试检查项由开发团队在仓库中维护。Pipeline 配置只需调用 `./scripts/smoke-test.sh` — 检查内容变更时无需修改 Pipeline。

---

## 4. Pipeline 配置建议（仅供参考）

基于以上内容，`pipeline.yml` 的测试任务可更新为：

```yaml
test:
  name: Test
  if: github.event_name == 'push'
  runs-on: ubuntu-latest
  steps:
    - name: Checkout
      uses: actions/checkout@v4
      with:
        submodules: recursive  # 确保 PVM 子模块被检出

    - name: Install Rust
      uses: dtolnay/rust-toolchain@stable
      with:
        toolchain: "1.89.0"  # 必须与仓库中的 rust-toolchain.toml 一致

    - name: Build
      run: cargo build --release

    - name: Unit Tests
      run: cargo test --workspace
```

在部署完成后添加冒烟测试步骤：

```yaml
# 在 deploy-dev 任务中，"Wait for Instance Refresh" 之后、Slack 通知之前添加：
    - name: Smoke Test
      run: |
        chmod +x ./scripts/smoke-test.sh
        ./scripts/smoke-test.sh
```

---
