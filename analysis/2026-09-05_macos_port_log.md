# macOS CIP-39 v2 移植 — 進度紀錄(夜間無人值守)

回退說明在同目錄的 `2026-09-05_macos_port_ROLLBACK.md`。
分支:`macos-cip39-v2-port`(從 `homestead-based-on-cip-39-v2` @ `7f32f9c` 開出)。
**`homestead-based-on-cip-39-v2` 本身一行都沒動。**

## 結果:PR #80,全綠

| check | 結果 |
|---|---|
| `app`(macos-26,兩個 trust profile) | ✅ 26m6s |
| `collab-relay-tests` | ✅ 34m54s |
| `ffi-profile-tests` | ✅ 6m55s |
| `web-tests` | ✅ 6m20s |
| `core-tests` | ✅ 5m10s |
| `billing-store-tests` | ✅ 5m58s |

**Swift app 382 個測試 / 33 個 suite,development 與 production 兩個 trust profile
都通過,並完成 app artifact 組裝與隔離驗證** —— v2 移植以來第一次。
臨時加的 CI trigger 已經拿掉,上面這一輪是走正常的 `pull_request` 路徑跑出來的。
**我沒有合併。**

過程共跑了 9 輪 CI(macOS runner 是這台機器唯一能用的 Swift 編譯器)。

## 為什麼之前沒人發現

移植卡住的原因**不在 Swift**,而在 CI 從來沒有能力建置這個分支:

| 問題 | 實情 |
|---|---|
| sibling pin 過期 | `CBFS_REV` 落後 131 個 commit、`NODE_REV` 落後 **1806** 個 |
| `cbqs` 根本沒被 checkout | v2 讓 `cbqs-client` 成為 workspace 根與 relay 的 path 依賴,每個 Rust job 都在 `cargo metadata` 就死了 |
| relay job 一個 sibling 都沒 checkout | 它透過 `homestead-cbqs` 會走到 workspace 根 |
| `@cowboyinc/cbqs-wasm` 不再是已發佈套件 | 變成指向 cbqs 的 `file:` 連結,而那個 `pkg/` 是 cbqs 忽略掉的 wasm-pack 產物 |
| wasm 在 macOS 上編不起來 | `blst` 要把 C 編到 wasm32,Apple clang 沒有 wasm target(Linux clang 有,所以只有 macOS 掛) |
| macOS `app` job 被 `if:` 擋掉 | 只在 main/devnet/PR 跑 |

一句話:**這條線的紅燈是工具鏈的,不是程式的**。CI 一被修好,底下真正的問題才浮出來。

## 修掉的東西

### CI
三個 sibling pin 對齊、新增 `CBQS_REV` 與四處 checkout、relay job 補上三個 sibling、
web/app/app-release 在 `npm ci` 前先建 wasm 套件(macOS 用 Homebrew LLVM)。

### relay 三個 profile 首次全部可編可 lint
- **featureless**:兩處在沒有 cfg 的情況下匹配 `PersistenceConfig::ProofBoundDevelopmentEmbedded`,而且那兩個 arm 在任何 profile 下都是死的 —— 上面那段有 gate 的正規化早就把該 variant 換掉了。
- **production**:移植把 protocol 706 那一組(`proof-codec`/`light-client`/`service-release`)一起搬到 CBQS v2 的 rev。這三個必須跟著被 pin 的 cbfs 走;統一之後同一個套件掛兩個名字,cargo 直接拒絕整份 manifest。已還原成 `706612ff`。接著三個 production 專屬呼叫點還在讀 v2 已改名的 `finalized_block_hash`。
- 兩則孤兒 v1 doc comment、一個沒用到的 example binding、一個沒有呼叫者的方法,以及機械式 clippy。

### dev-readiness 工具測試
測試還在建 v1 的 Main/Key 雙 stream 世界,recorder 早就只讀一份 v2 snapshot。
配對漂移與重試那些案例因為 v2 拿掉了「配對」而消失,取而代之的是 v2 的身分與參數面。
**對 recorder 打了五個變異,五個全被殺掉。**

### Swift(核心)
1. `ProofBoundNativeCbqsFactory` 還宣告著 v2 FFI 不再匯出的 `...V1` 型別。
2. ⚠️ `TrustedStreamFloor` 帶的是 stream **config** generation(`isStrictlyValid()` 拿它跟 workspace floor 的 `streamConfigGeneration` 比對),移植把它改名成 `authorizationGeneration`,**連留給遷移用的 legacy v3 形狀一起改**,而每個寫入端都還在傳 config generation。legacy 形狀上改名更糟:那些欄位名就是**已安裝 app 已經寫到磁碟的 JSON key**,解不出來的 floor 等於一道單調回滾防護悄悄消失。
3. `verifyHomesteadDevelopmentReadinessBindingV1` 在 v2 多了兩個參數,兩個呼叫點都沒改:development 路徑還在傳 `minimumConfigGeneration` 而且完全沒指定 provider;production 路徑則已經在要 `proofMinimums` 根本不回傳的成員。`proofMinimums` 現在回傳 workspace floor 上的 authorization generation —— v2 唯一存活的單調 floor。
4. ⭐ **`resolvedPageLanes` 宣告了、被讀取,但從來沒有人寫入。** v1 從 `(stream id, page slot)` 推導四條 lane,所以 `browserCbqsAuthority(forPageID:)` 是純函式;v2 §8 把指派交給 broker,移植把推導換成讀一個永遠是 nil 的欄位 —— 於是**每一頁都沒有 browser authority,連帶沒有留言能力、沒有內容編輯**。新增 `PageLaneResolution.swift`:照 `webeditor/src/shell/authority.ts` 的做法,每個 channel mint 一次、快取一次,兩次 mint 必須彼此一致且與 epoch 的 stream 一致才採信。
5. v2 lane id 是 broker 指派的整數,測試還在餵 32 bytes hex。
6. Swift 測試自己複製了一份簽章 receipt,而那份還是 v1(blob version byte 1、110 bytes,v2 要 2 和 118)。已從 `services/dev-readiness/testdata` 的正本重新產生,並**加了一道在 Linux 跑的閘**把 Swift 檔讀回來比對 —— 簽章 fixture 的副本正是會無聲腐爛的東西,而它確實爛了。

## 還沒做完 / 要你決定的

⚠️ **一個設計問題我沒有擅自決定**:v1 的 lane 是本地推導,所以
`canCommentPage`/`canEditPageContent` 這類**能力判定**是純函式;v2 之後它們變成
「我們跟 relay mint 過了沒有」的**網路狀態**判定。我保留了現有語意(沒 mint 到就沒有能力),
測試則用一個 DEBUG-only 的 seam 合成 lane —— 跟既有的
`assumedNativeCbqsMetadataWriterEpochForTest` 同一個慣例。
比較乾淨的做法可能是把「這頁有沒有資格開 CBQS session」和「lane 到了沒」拆開,
但那會動到跟權限有關的判定,我不想在你睡覺時自己拍板。

另外還修了三處只存在於 production profile 的編譯錯誤(v2 從兩個 projection
拿掉了 `streamConfigGeneration`),以及兩道還在斷言移植前名字的 CI 閘。

**還沒做的**:`app-release`(公證/簽章)與 `publish` 只在 `main` 上跑,這次沒碰到;
app 與真實 v2 devnet 的端到端也還沒跑過(PORT-PLAN 說的那條「沒有 live devnet e2e」
對 app 仍然成立,web 版已經有了)。

## 我沒有動的東西

執行中的公網部署、relay/broker/鏈節點、每小時輪換信任錨點的 crontab。
`homestead-based-on-cip-39-v2` 分支本身。其他 8 個 repo。
