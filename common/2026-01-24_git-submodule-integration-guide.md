# Git Submodule 集成指南：将 PVM 项目链接到 Node 项目

本文档记录了如何将 GitHub 中的 PVM 项目作为子模块集成到 Node 项目中的完整指南。

## 项目信息

- **Node 项目地址**：git@github.com:cowboyinc/node.git
- **Node 项目分支**：devnet_pvm_integration
- **PVM 项目地址**：git@github.com:cowboyinc/pvm.git

## 目录

1. [日常开发注意事项](#日常开发注意事项)
2. [使用 Git Submodule 链接项目](#使用-git-submodule-链接项目)
3. [修改子模块代码](#修改子模块代码)
4. [最佳实践](#最佳实践)
5. [常见问题](#常见问题)
6. [故障排除：子模块引用无法提交](#故障排除子模块引用无法提交)

---

## 日常开发注意事项

### ⚠️ 最重要的注意事项

#### 1. 克隆项目时必须初始化子模块
```bash
# 克隆时使用 --recurse-submodules
git clone --recurse-submodules -b devnet_pvm_integration git@github.com:cowboyinc/node.git

# 如果已经克隆，需要手动初始化
git submodule update --init --recursive
```

#### 2. 修改子模块代码后必须提交
- ✅ **推荐使用自动化脚本**：
  ```bash
  ./commit_pvm_changes.sh -m "你的修改说明" -s
  ```
  脚本会自动完成：提交子模块修改 → 推送到远程 → 更新父项目引用

- ✅ **手动方式**：
  ```bash
  # 在子模块目录内提交并推送
  cd pvm
  git add .
  git commit -m "你的修改说明"
  git push origin main
  
  # 回到父项目更新引用
  cd ..
  git add pvm
  git commit -m "更新 pvm 子模块"
  ```
- ❌ **不要只做本地修改而不提交**，否则更新时会丢失

#### 3. 使用正确的分支
- Node 项目使用 `devnet_pvm_integration` 分支
- 操作前确认分支：
  ```bash
  git checkout devnet_pvm_integration
  ```

#### 4. 更新子模块的正确方式
```bash
# 方法1：更新到远程最新版本
git submodule update --remote pvm
git add pvm
git commit -m "更新 pvm 子模块"

# 方法2：手动进入子模块更新
cd pvm
git pull origin main
cd ..
git add pvm
git commit -m "更新 pvm 子模块"
```

#### 5. 检查子模块状态
```bash
# 查看子模块状态
git status
# 会显示：modified:   pvm (new commits) 如果有新提交

# 查看子模块当前指向的提交
cd pvm
git log -1
```

#### 6. 团队协作注意事项
- 确保团队成员都使用 `--recurse-submodules` 克隆
- 提交父项目时，如果子模块有更新，必须同时提交子模块引用
- 拉取代码后如果子模块有更新，需要执行：
  ```bash
  git pull
  git submodule update --init --recursive
  ```

#### 7. PVM 是 Rust 项目
- 需要先编译才能使用：
  ```bash
  cd pvm
  cargo build --release
  ```
- 编译产物在 `pvm/target/release/` 目录

#### 8. 避免的操作
- ❌ 不要只修改子模块而不提交
- ❌ 不要在子模块目录外直接修改子模块文件
- ❌ 不要忘记在父项目中提交子模块的新引用

#### 9. 快速检查清单
每次提交前确认：
- [ ] 子模块的修改已提交并推送到远程
- [ ] 父项目中已提交子模块的新引用
- [ ] 当前在正确的分支（`devnet_pvm_integration`）

---

## 使用 Git Submodule 链接项目

### 方法 1：使用 Git Submodule（推荐）

在 Node 项目目录中执行以下命令：

```bash
# 1. 进入你的 node 项目目录
cd /path/to/your/node/project

# 2. 添加 pvm 作为子模块
git submodule add git@github.com:cowboyinc/pvm.git pvm

# 或者指定特定的分支/标签
git submodule add -b main git@github.com:cowboyinc/pvm.git pvm

# 3. 提交子模块引用
git add .gitmodules pvm
git commit -m "Add pvm as submodule"
```

### 克隆包含子模块的项目

```bash
# 克隆项目时同时初始化子模块（使用 devnet_pvm_integration 分支）
git clone --recurse-submodules -b devnet_pvm_integration git@github.com:cowboyinc/node.git

# 或者如果已经克隆了项目，初始化子模块
git submodule update --init --recursive
```

### 更新子模块

```bash
# 更新子模块到最新提交
git submodule update --remote pvm

# 或者进入子模块目录手动更新
cd pvm
git pull origin main
cd ..
git add pvm
git commit -m "Update pvm submodule"
```

### 方法 2：在 Node.js 中使用 PVM

如果需要在 Node.js 代码中使用 PVM，可以通过子进程调用编译后的二进制文件：

```javascript
const { execFile } = require('child_process');
const path = require('path');

// 假设 pvm 已经编译并位于子模块中
const pvmPath = path.join(__dirname, 'pvm', 'target', 'release', 'pvm');

execFile(pvmPath, ['script.py'], (error, stdout, stderr) => {
  if (error) {
    console.error(`执行错误: ${error}`);
    return;
  }
  console.log(stdout);
});
```

### 方法 3：直接引用 GitHub URL

如果 PVM 项目有 `package.json`，可以在 Node 项目的 `package.json` 中直接引用：

```json
{
  "dependencies": {
    "pvm": "git+ssh://git@github.com/cowboyinc/pvm.git"
  }
}
```

---

## 修改子模块代码

### 可以修改，但需要正确管理

#### 1. 直接修改子模块代码

```bash
# 进入子模块目录
cd node-project/pvm

# 修改任何文件（例如修改 src/main.rs）
# ... 进行修改 ...

# 在子模块中提交更改
git add .
git commit -m "修改 pvm 的某个功能"
git push origin main  # 推送到 pvm 的远程仓库
```

#### 2. 修改后的状态管理

修改子模块后，父项目（Node 项目）会检测到子模块指向了新的提交：

```bash
# 回到 node 项目根目录
cd ..

# 查看状态，会显示子模块有新的提交
git status
# 输出会显示：modified:   pvm (new commits)

# 提交子模块的新引用
git add pvm
git commit -m "更新 pvm 子模块到新版本"
```

### 修改策略

#### 方案 A：修改并推送到 PVM 的原始仓库（推荐）

如果修改是通用的、应该合并到 PVM 主项目：

```bash
cd pvm
# 修改代码
git add .
git commit -m "功能改进"
git push origin main  # 推送到 pvm 的 GitHub 仓库

# 然后在 node 项目中更新引用
cd ..
git add pvm
git commit -m "更新 pvm 子模块"
```

#### 方案 B：Fork 并维护自己的版本

如果修改是 Node 项目特有的，建议 Fork PVM：

```bash
# 1. Fork pvm 到自己的 GitHub 账号
# 2. 更新子模块指向你的 fork
cd node-project
git submodule deinit pvm
git rm pvm
git submodule add git@github.com:cowboyinc/pvm.git pvm

# 3. 在 fork 的仓库中进行修改
cd pvm
# 修改代码
git add .
git commit -m "node 项目特定的修改"
git push origin main
```

#### 方案 C：本地修改但不提交（不推荐）

如果只是临时测试，可以修改但不提交：

```bash
cd pvm
# 修改代码（但不要 commit）
# 注意：这种方式修改会在更新子模块时丢失
```

---

## 最佳实践

### 1. 使用分支管理修改

```bash
cd pvm
git checkout -b node-project-customizations
# 进行修改
git add .
git commit -m "为 node 项目定制的修改"
git push origin node-project-customizations

# 在 node 项目中指向这个分支
cd ..
git config -f .gitmodules submodule.pvm.branch node-project-customizations
git submodule update --remote

# 注意：确保在 node 项目的 devnet_pvm_integration 分支上操作
git checkout devnet_pvm_integration
```

### 2. 使用自动化脚本管理子模块（推荐）⭐

项目根目录提供了两个自动化脚本，简化子模块的日常操作：

#### 更新子模块脚本：`update_pvm_submodule.sh`

用于更新子模块到最新版本并提交引用：

```bash
# 基本用法：更新到最新版本
./update_pvm_submodule.sh

# 使用自定义提交信息
./update_pvm_submodule.sh -m "更新到最新版本"

# 使用 --remote 方式更新
./update_pvm_submodule.sh -r

# 更新到指定提交
./update_pvm_submodule.sh --commit-hash abc123

# 仅检查状态，不执行更新
./update_pvm_submodule.sh -c

# 强制更新（会丢弃子模块中的未提交更改）
./update_pvm_submodule.sh -f

# 查看帮助信息
./update_pvm_submodule.sh --help
```

脚本功能：
- ✅ 自动检查 git 仓库和子模块状态
- ✅ 检查当前分支（建议使用 `devnet_pvm_integration`）
- ✅ 检测 detached HEAD 状态并自动修复
- ✅ 检测未提交的更改并提示
- ✅ 自动提交子模块引用
- ✅ 彩色输出和清晰的错误提示

### 3. 在 Node 项目中添加脚本管理

在 Node 项目的 `package.json` 中添加脚本：

```json
{
  "scripts": {
    "update-pvm": "git submodule update --remote pvm",
    "build-pvm": "cd pvm && cargo build --release",
    "init-pvm": "git submodule update --init --recursive"
  }
}
```

### 3. 文档化修改

在 Node 项目中创建 `PVM_MODIFICATIONS.md` 记录所有修改：

```markdown
# PVM 子模块修改记录

## 修改日期：2024-XX-XX
- 文件：src/main.rs
- 原因：添加 node 项目特定的功能
- 提交：commit-hash
```

### 5. 编译 PVM

由于 PVM 是 Rust 项目，需要先编译才能使用二进制文件：

```bash
cd pvm
cargo build --release
```

编译后的二进制文件位于：`pvm/target/release/pvm`

---

## 常见问题

### Q: 修改后如何更新子模块？

```bash
cd pvm
git pull origin main
cd ..
git add pvm
git commit -m "更新 pvm 子模块"
```

### Q: 如何撤销对子模块的修改？

```bash
cd pvm
git checkout -- .
# 或者重置到特定提交
git reset --hard <commit-hash>
```

### Q: 如何查看子模块的修改历史？

```bash
cd pvm
git log
```

### Q: 如何移除子模块？

```bash
# 方法 1：使用 git submodule deinit
git submodule deinit pvm
git rm pvm
rm -rf .git/modules/pvm

# 方法 2：手动移除
git rm --cached pvm
rm -rf pvm
rm -rf .git/modules/pvm
# 编辑 .gitmodules 文件，删除 pvm 相关条目
```

### Q: 子模块指向了错误的提交怎么办？

```bash
cd pvm
git checkout <正确的commit-hash>
cd ..
git add pvm
git commit -m "修正 pvm 子模块提交引用"
```

---

## 故障排除：子模块引用无法提交

### 问题描述

在尝试提交子模块引用时遇到问题，`git add pvm` 后无法正常提交。

### 常见原因和解决方案

#### 1. 子模块处于 detached HEAD 状态 ⚠️ 最常见

**诊断：**
```bash
cd pvm
git status
# 如果显示 "HEAD detached at ..." 就是这个问题
```

**解决：**
```bash
cd pvm
git checkout main  # 切换到主分支
git pull origin main  # 拉取最新代码
cd ..
git add pvm
git commit -m "更新 pvm 子模块引用"
```

#### 2. 子模块有未提交的更改

**诊断：**
```bash
cd pvm
git status
# 查看是否有未提交的文件
```

**解决：**
```bash
# 方案A：提交子模块的更改
cd pvm
git add .
git commit -m "你的修改说明"
git push origin main
cd ..
git add pvm
git commit -m "更新 pvm 子模块"

# 方案B：丢弃子模块的更改（如果不需要）
cd pvm
git checkout -- .
cd ..
```

#### 3. 子模块未初始化或目录为空

**诊断：**
```bash
ls -la pvm
# 如果目录为空或只有 .git 文件
```

**解决：**
```bash
git submodule update --init --recursive
# 或者
git submodule init
git submodule update
```

#### 4. 子模块指向的提交不存在

**诊断：**
```bash
cd pvm
git log -1
git fetch origin
git log origin/main --oneline | head -5
# 检查当前提交是否在远程存在
```

**解决：**
```bash
cd pvm
git fetch origin
git checkout main
git reset --hard origin/main
cd ..
git add pvm
git commit -m "修正 pvm 子模块引用"
```

#### 5. 权限问题

**诊断：**
```bash
# 检查父项目状态
git status
# 检查是否有写权限
git push --dry-run
```

**解决：**
- 确认有父项目的写权限
- 确认能访问子模块仓库（SSH 密钥配置正确）

#### 6. 子模块配置问题

**诊断：**
```bash
cat .gitmodules
git config --file .gitmodules --list
```

**解决：**
```bash
# 检查并修复配置
git submodule sync
git submodule update --init --recursive
```

### 完整诊断流程

按以下步骤排查：

```bash
# 1. 检查父项目状态
git status

# 2. 检查子模块状态
cd pvm
git status
git branch -a  # 查看所有分支
git log -1     # 查看当前提交
cd ..

# 3. 检查子模块配置
cat .gitmodules
git config --file .gitmodules --list

# 4. 尝试同步子模块
git submodule sync
git submodule update --init --recursive

# 5. 如果子模块在 detached HEAD，切换到分支
cd pvm
git checkout main
cd ..

# 6. 再次尝试提交
git add pvm
git commit -m "更新 pvm 子模块"
```

### 快速修复命令（通用）

如果以上都不行，可以尝试重置子模块：

```bash
# 备份当前状态
git status > /tmp/git_status_backup.txt

# 重置子模块到正确状态
git submodule deinit -f pvm
git submodule update --init --recursive pvm

# 如果还有问题，完全重新初始化
rm -rf pvm
git submodule update --init --recursive pvm
```

---

## 注意事项

1. **PVM 是 Rust 项目**：需要先编译才能使用二进制文件
2. **确保 .gitignore 配置正确**：避免提交不必要的文件（如 `target/` 目录）
3. **修改要提交**：避免只做本地修改而不提交，否则更新时会丢失
4. **团队协作**：确保团队成员都了解子模块的使用方式，克隆项目时使用 `--recurse-submodules` 参数
5. **使用正确的分支**：Node 项目使用 `devnet_pvm_integration` 分支，克隆和操作时请注意分支切换

---

## 总结

- ✅ 可以修改子模块代码
- ✅ 建议将修改提交到 PVM 的仓库（原始仓库或你的 Fork）
- ✅ 在 Node 项目中提交子模块的新引用
- ❌ 避免只做本地修改而不提交，否则更新时会丢失

---

**文档创建日期**：2024年
**最后更新**：2024年（已补充日常开发注意事项和故障排除指南）

## 快速参考命令

### 克隆 Node 项目（包含 PVM 子模块）
```bash
git clone --recurse-submodules -b devnet_pvm_integration git@github.com:cowboyinc/node.git
```

### 在 Node 项目中添加 PVM 子模块
```bash
cd node
git checkout devnet_pvm_integration
git submodule add git@github.com:cowboyinc/pvm.git pvm
git add .gitmodules pvm
git commit -m "Add pvm as submodule"
```

### 更新 PVM 子模块

**方法 1：使用自动化脚本（推荐）**
```bash
cd node
git checkout devnet_pvm_integration
./update_pvm_submodule.sh
```

**方法 2：手动更新**
```bash
cd node
git checkout devnet_pvm_integration
git submodule update --remote pvm
git add pvm
git commit -m "Update pvm submodule"
```
