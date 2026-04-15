# 开发任务清单 (2026-02-25)

**客户确认**: Martin Aceto & Charles DePue (2026-02-25, #devnet-eng)

---

## 一、Account CLI 命令

**仓库**: `cowboyinc/node` | **文件**: `cli/src/commands.rs` + `cli/src/main.rs`

实现 4 个 `cowboy account` 子命令，通过 REST API 查询任意公钥地址的链上信息：

| 命令 | 功能 | API |
|------|------|-----|
| `cowboy account balance -a <hex>` | 查余额，显示 CBY 和 wei | `GET /account/0x{addr}` |
| `cowboy account nonce -a <hex>` | 查 nonce | `GET /account/0x{addr}` |
| `cowboy account info -a <hex>` | 查完整信息（类型+余额+nonce） | `GET /account/0x{addr}` |
| `cowboy account faucet -a <hex>` | 请求测试代币（仅 local/dev） | `POST /faucet` body: `{"address":"0x..."}` |

**客户额外要求**: 所有参数同时支持 `--address` 和 `-a` 简写。

### 任务清单

- [ ] **实现 `account balance`** — `commands.rs` 第 228-236 行 TODO 存根，用 `reqwest` 调 `GET /account/0x{addr}`，解析返回的 `balance` 字段，按 `1 CBY = 10^9 wei` 换算显示
- [ ] **实现 `account nonce`** — `commands.rs` 第 237-245 行 TODO 存根，同上 API，只显示 `nonce` 字段
- [ ] **实现 `account info`** — `commands.rs` 第 246-254 行 TODO 存根，显示 type + balance + nonce
- [ ] **新增 `account faucet`** — 在 `AccountCommand` 枚举（第 37 行后）加 `Faucet { address }` 变体，实现时 `POST /faucet`，body 为 `{"address":"0x..."}`，返回 `{tx_hash, amount_cby}`
- [ ] **修正 10^12 → 10^9** — 以下 4 处 `1_000_000_000_000` 全部改为 `1_000_000_000`：
  - 第 580 行（`WalletCommand::Balance`）
  - 第 1319 行（`RunnerCommand::Register`）
  - 第 1415 行（`RunnerCommand::Get`）
  - 第 1462 行（`handle_transfer_command`）
  - 建议在文件顶部加常量 `const WEI_PER_CBY: u64 = 1_000_000_000;`

---

## 二、Runner 自动注册

runner 启动后不能自动注册到 validator，必须手动跑 `cowboy runner register` CLI 命令才能让心跳正常工作。客户觉得这个流程很麻烦，尤其是每次链重置后都要重新手动注册。

所以他提出了一个功能需求：让 runner 在启动时自动注册到链上，不再需要手动操作。他在 Notion 上写了一个详细的技术方案草案 [英文提案](https://cb.ai-api.top/docs/#notion%2F20260225_Runner_auto_registration.md) [中文翻译](https://cb.ai-api.top/docs/#notion%2F20260225_Runner_auto_registration_zh.md) ，同时表示"你们如果有其他想法可以随意修改，最终方案确定后他也愿意帮忙一起实现"。

