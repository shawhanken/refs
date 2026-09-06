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

---

# 追加(2026-09-06):替換 actor 的遷移與回退

移植之後又做了一次**線上服務的切換**——為了讓 macOS app 與 web demo
同時能用,必須換掉 workspace actor(舊 actor 的 `shared_audiences`
與 `actor_artifact_profile` 都無法事後修改)。這一節是那次切換的回退法。

## 現在跑的是什麼

| 東西 | 值 |
|---|---|
| workspace actor(新) | `0xB1870df1140356644c8ffa986a6a2Ea0ff2Cc5D8` |
| workspace actor(舊,原封不動) | `0xc81a7103777Ab37F8472566d8c11dd5449275640` |
| artifact profile | `local-dev` |
| shared audiences | Web + Desktop 兩個 Google client id |
| relay 二進位 | `proof-bound-development-embedded`,含多 audience 修改 |

舊 actor 的 274 個 key 一個都沒被動過,它仍然是一個完整可用的 actor。
回退因此是「把三個檔案指回去,重啟兩個 process」,不需要任何鏈上交易。

## 回退步驟

```bash
C=~/.homestead-devnet
cp $C/actor-address.txt.pre-b187            $C/actor-address.txt
cp $C/run/gateway/gateway.toml.pre-b187     $C/run/gateway/gateway.toml
cp $C/run/start-relay.sh.pre-b187           $C/run/start-relay.sh

kill $(cat $C/run/gateway.pid); sleep 2
(cd /home/ubuntu/workspace/gateway && nohup ./target/release/gateway \
   --config $C/run/gateway/gateway.toml >> $C/run/gateway.log 2>&1 &
 echo $! > $C/run/gateway.pid)

kill $(cat $C/run/relay.pid); sleep 2
(cd $C/run && nohup ./start-relay.sh >> relay.log 2>&1 & echo $! > relay.pid)
```

回退後 macOS 的 Desktop audience 會再度被拒(那正是切換前的狀態),
web demo 照常。

## 遷移產物(要重跑或稽核時用)

- `/home/ubuntu/workspace/.migration/batch-{1..5}.json` — 62 個 key 的狀態
- `/home/ubuntu/workspace/.migration/routes.cbor` — 44 條 HTTP route
- `/home/ubuntu/workspace/.migration/audiences.json` — 兩個 audience
- `/home/ubuntu/workspace/.migration/init-complete.json` — 三個 init flag
  (`migration_open` + readiness 公鑰 + `local_dev_allow_unverified_billing`)
- 工具:`node/` 旁的 `scripts/actor-migration/`(commit `54af25e`)

## 這次踩到、值得記住的兩件事

1. **`init` 不可重入。** 少給一個 flag 就得重新 deploy 一次;
   `init` 第二次呼叫會以 `E1230` unmapped exception 被鏈拒絕。
   所以 init payload 要一次給齊。
2. **切換前一定要證明 data plane 真的開著。** 方法是拿 relay key 簽一次
   `/api/acl/check`,看 `allow` / `billing_state` / `development_readiness`
   三個欄位;再用本地 JWKS 簽的 token 打一次 `/cbqs/session`。
   上一輪就是跳過這一步,結果線上開檔全掛(403 not authorized for room)。

## 每小時輪換的相互作用

crontab 的 `rotate-trusted-checkpoint.sh` 每小時 :17 會**重建 relay 並重啟**,
用的是 `/home/ubuntu/workspace/homestead` 當下 checkout 的分支。多 audience
的修改在 `macos-cip39-v2-port`(PR #80)上,所以切到別的分支會讓 macOS 的
audience 靜默失效——換分支時記得這件事。
