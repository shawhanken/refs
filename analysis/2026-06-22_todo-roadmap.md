# Todo Issue 維修路線圖 — 2026-06-22

**來源**：Linear COW team，state=Todo，assignee ∈ {pavilionledger, null}，共 **29 條**。
**現狀核實**：5 個並行 Explore agent 對 `node/` + `node/pvm/` 程式碼逐簇核實（非僅憑記憶）。
**決策**：用戶拍板 — 全 29 條納入本團隊路線圖（含原屬 CIP-2/3/4、gateway/infra 簇）；落檔；先啟動 Wave 1。

> 注意：CIP-2/3/4 與 gateway/terraform 簇依過往分工記憶屬其他團隊，且 terraform 倉庫不在本工作區。
> 本路線圖按用戶要求全部接手，但對「倉庫不在本地 / 須跨團隊協調」者明確標註前置條件。

---

## 一、程式碼現狀速查（已核實）

| Issue | 標題（節錄） | 現狀 | 關鍵檔案 |
|---|---|---|---|
| COW-1248 | PVM 例外映射決定性 | **近乎 DONE** — COW-2290 `scrub_runtime_identity()` 已在共識邊界脫敏堆指標，例外字串進 receipt_root 前已決定化 | `execution/src/structured_error_map.rs`；`pvm-runtime/src/lib.rs:1368` |
| COW-62 | checkpoint 序列化格式 | **DONE(碼)/缺規格** — `SNAPSHOT_VERSION=3` + canonical CBOR 已落地 | `pvm/crates/vm/src/vm/snapshot.rs:23` |
| COW-105 | resume 狀態驗證 | **PARTIAL** — guard/timeout/CBOR 已驗；lasti 語意、locals/blocks/stack、handler 預檢缺 | `pvm/crates/vm/src/vm/checkpoint.rs` |
| COW-94 | FSM 狀態轉移合法性 | **NOT STARTED** — resume 不檢查 state 範圍、可跳任意狀態 | `pvm/crates/codegen/src/pvm_fsm.rs:449` |
| COW-123 | 區塊頭版本欄位 | **NOT STARTED** — 完全可套 COW-177(tx 版本)範式 | `node/types/src/execution.rs:3831/3879` |
| COW-166 | compact block | **NOT STARTED** — 需設計(tx-hash-only/BIP-152)+傳播層改造，依賴 123 | `node/types/src/execution.rs:4042` |
| COW-137 | PvmHost 批次讀 | **NOT STARTED** — feasibility 標**共識級**(改 read 計量/原子性) | `execution/src/pvm_host.rs:1719`；`storage/src/traits.rs:63` |
| COW-963 | 指令成本表(字串/list concat) | **NOT STARTED** — gas.rs 只有 scalar base cost | `node/execution/src/gas.rs:1-205` |
| COW-964 | 大整數加價 | **NOT STARTED**(runtime) — 僅 deploy gate(COW-2293)+_GuardedInt 攔截；無 per-op bitlen 加價 | `pvm-runtime/src/lib.rs:136`；`gas.rs` |
| COW-979 | 歷史狀態查詢(光客戶端) | **PARTIAL** — CIP-17 當前態證明 DONE；COW-977 快照基礎在；缺 time-travel 查詢層+過去高度證明 | `rpc/src/handlers/proof.rs:340`；`storage/src/state_sync.rs`；`rpc/handlers/actor.rs:84`(pinned-height 已明確拒) |
| COW-957 | TEE attestation pipeline | 前提過時 — 大部分已實作(cbss.rs)；真缺口=Nitro+鏈上 cert-chain | (CIP-2) |
| COW-962 | dispute window 鏈上 handler | `dispute_window_blocks` 欄位在、無 handler | (CIP-2) |

---

## 二、分波路線圖（依風險/工序/依賴）

### Wave 1 — 速贏（非共識/文件/已近完成）★ 先啟動
- **COW-1248**：核實 COW-2290 是否完整關閉 → 補一條回歸測試（兩 PVM 實例相同輸入→相同 receipt）→ 關單/標 Done。
- **COW-62**：碼已 DONE，寫 checkpoint 格式規格小節（CIP/ARCHITECTURE）→ 關。
- **COW-2266**：白皮書 genesis 參數 vs 參考實作對帳（純文件，可搭 COW-1260 通脹曲線）。

### Wave 2 — 範例維護（Tier-4，沿用 SMOKE harness）
- **COW-1342** erlangcowboydemo、**COW-1341** 32-cowbot、**COW-1329** 19-texas-holdem：逐例實跑修復（仿 cowboy PR #160）。
- **COW-1308** CIP-2 v3 e2e 經濟範例：建在範例 harness 上。
- 母票 **COW-1344**(Docker harness)、**COW-1347**(CLI/read 語意相容) 作 epic 容器，由子票推進。

### Wave 3 — 節點共識變更（flag-day，套既有範式）
- **COW-123** 區塊頭版本：照搬 COW-177，`Block::compute_digest`+Write/Read/EncodeSize 首位加 `CURRENT_BLOCK_VERSION=1`，穿 4 個 digest 呼叫點。風險低、模式現成、須協調 flag-day。
- **COW-94 + COW-105**（同檔 checkpoint.rs，同批）：續體存 FSM metadata(max_states/handler registry)，resume 校驗 state 範圍+handler 預檢+lasti/locals/blocks/stack。**須以執行層測試驗證**(審續體只信執行層測試)。

### Wave 4 — CIP-3 gas（須 VM-level hooks，兩條相關同批）
- **COW-963** 指令成本表：BUILD_STRING/concat/slice 加 per-operand-size 加價。
- **COW-964** 大整數 runtime 加價：BINARY_OP 依 bitlen 計量。
- 兩者都需在 PVM 解譯器層抽 operand size 餵 `charge_gas` → 共識變更，flag-day。

### Wave 5 — 大型/重協調（設計先行）
- **COW-962** dispute window：鏈上 challenge/evidence/re-verification handler（CIP-2）。
- **COW-957** TEE pipeline：補 Nitro + 鏈上 cert-chain（前提已過時，先重評範圍）。
- **COW-979** 歷史狀態查詢：暴露 COW-977 快照重建為 RPC + 過去高度證明 + `GET /state/at/{height}/...`（CIP-4）。
- **COW-1274** 解耦 timer 執行於 propose 關鍵路徑（架構，關聯 PR#580 timer-basefee）。
- **COW-166** compact block：依賴 COW-123，先出設計。
- **COW-137** PvmHost 批次讀：共識級(原子性順序)，排最後。

### Wave 6 — 前端/錢包
- **COW-433**(wallet connection secp256k1)、**COW-435**(tx building/signing) Frontend SDK：確認與 wallet 團隊邊界；關聯 wallet#14 tx-canonical。
- **COW-2313** 明文私鑰：設計題(無密碼即無 KEK)，標 design-decision，低優先。

### Wave 7 — 基建/Infra（**前置：terraform 倉庫不在本工作區**）
- **COW-508** API Gateway module、**COW-513** Tailscale ACL、**COW-514** usage plan/API keys、**COW-515** IP allowlist。
- 須先取得 gateway/infra 倉庫存取權；否則僅能寫設計/評論。

### 治理/Release Epic（非純工程）
- **COW-2265** mainnet：打包 devnet 共識規則差量 — 是大量「needs_human flag-day 待協調上線」PR（#742/#777/#784…）的總傘票，當 release checklist 管理。
- **COW-1265** genesis 供給分配(1B CBY split)：經濟，搭 COW-1260/COW-2266 治理軌。

---

## 三、執行順序

```
Wave 1（速贏關單）→ Wave 2（範例並行）→ Wave 3（123 先，94+105 同批）
→ Wave 4（963+964 gas）→ Wave 5（設計先行：962/957/979/1274/166/137）
→ Wave 6（前端）→ Wave 7（infra，須倉庫存取）
治理軌：2265/1265 當 release/economics epic 獨立管理
```

**flag-day 共識變更清單**（須協調上線）：123、94/105、963/964、137、979、2265。
**可乾淨快速關單**：1248、62、2266 + 範例簇。
