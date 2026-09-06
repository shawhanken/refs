# 回退指南 — macOS app CIP-39 v2 移植嘗試(2026-09-05)

這份檔案**故意放在 `refs/`**,而不是 `homestead/`:即使把 homestead 整個 reset 掉,
這份說明也還在。

## 一句話

移植工作全部發生在 **新分支 `macos-cip39-v2-port`** 上,已開成 **PR #80**
(base 是 `homestead-based-on-cip-39-v2`,**我沒有合併**)。
`homestead-based-on-cip-39-v2` 這條分支**沒有被動過**,所以「什麼都不做」就是回退:
不合併 PR 即可。

## 錨點

| 名稱 | 值 | 說明 |
|---|---|---|
| tag | `pre-macos-cip39v2-port-20260905` | 已推到 origin,不可變 |
| 快照分支 | `snapshot/pre-macos-port-20260905` | 已推到 origin |
| commit | `7f32f9c448c7b8329e7ef3ddefb15c1d1e97cbfb` | 「No page, no paper」 |

## 回退指令

```bash
cd /home/ubuntu/workspace/homestead

# 情況 A(預設):什麼都沒合進去 —— 關掉 PR,丟掉工作分支
gh pr close 80
git checkout homestead-based-on-cip-39-v2
git branch -D macos-cip39-v2-port
git push origin --delete macos-cip39-v2-port     # 可選

# 情況 B:已經合進 homestead-based-on-cip-39-v2,要整條退回
git checkout homestead-based-on-cip-39-v2
git reset --hard pre-macos-cip39v2-port-20260905
git push --force-with-lease origin homestead-based-on-cip-39-v2

# 情況 C:只想看當時的樹,不動任何分支
git worktree add /home/ubuntu/workspace/homestead-snapshot pre-macos-cip39v2-port-20260905
```

## 回退後要重建的東西

只有一項:`webeditor/dist`。公網部署跑的是已經 build 好的產物,
`git reset` 不會動到執行中的服務,但如果期間重新 build 過,回退後要再跑一次

```bash
cd /home/ubuntu/workspace/homestead/webeditor && npm run build
```

**不需要**重啟 relay / broker / 鏈節點——移植工作不碰它們。
每小時輪換信任錨點的 crontab 也不受影響。

## 當時所有 repo 的狀態(只有 homestead 會被動)

| repo | branch | HEAD |
|---|---|---|
| Avenor | main | ce54235 |
| cbfs | homestead-based-on-cip-39-v2 | 8c667b9 |
| cbqs | homestead-based-on-cip-39-v2 | e354757 |
| cbss | homestead-based-on-cip-39-v2 | 3fe1012 |
| cowboy-protocol | homestead-based-on-cip-39-v2 | fc1662a |
| cowboy | homestead-based-on-cip-39-v2 | 62dd45e |
| cowchat | main | 2cac7de |
| dashboard | main | 6ac2b50 |
| gateway | homestead-based-on-cip-39-v2 | 7042ce1 |
| **homestead** | **homestead-based-on-cip-39-v2** | **7f32f9c** |
| macos | devnet | c7c9af9(本來就 dirty,與本次無關) |
| marshal | main | 71d91c1(本來就 dirty) |
| node | homestead-based-on-cip-39-v2 | afa9b0370 |
| refs | main | 7cb7596 |
| runner | homestead-based-on-cip-39-v2 | 98c17f4 |
| store-admin | main | 4cbb73f |
| wallet | main | 8c631f3 |

## 進度紀錄

移植過程的逐步紀錄寫在同目錄的
`2026-09-05_macos_port_log.md`,早上起來看那份。
