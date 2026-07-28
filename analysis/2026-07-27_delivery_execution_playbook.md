# Delivery Commitment — 內部作戰手冊

> 來源承諾書：`refs/analysis/Cowboy CIP · Delivery Commitment for Open Issues.html`（Data as of 2026-07-26 Beijing）
> 本手冊建立日：2026-07-27 · 讀者：本團隊（pavilionledger + 自動化）· 對外承諾以原 HTML 為準，本檔是「怎麼真的做出來」。

---

## 0. 承諾快照 + 算術核對

| 桶 | 數量 | 說明 |
|----|-----:|------|
| **我方承諾** | **94** | assignee = `pavilionledger` 或未指派 |
| ├ Phase 1｜現在能開工 | 62 | 5 週 W1–W5，每週 12–13 個 |
| ├ Phase 2｜blocked | 13 | 3 組，各有解卡條件 |
| └ Phase 3｜November batch | 19 | CIP-21 DEX + CIP-22 拍賣，token launch 後 |
| Cowboy team 自持 | 24 | 只記錄、無我方日期 |
| **本 sheet 合計** | **118** | 94 + 24 |
| 待 Cowboy team 勘誤裁定 | 161 | 見 Errata sheet，不在本檔 |
| **30 CIP 全部 open** | **279** | 118 + 161 |

算術：62 + 13(7+1+5) + 19 = **94**；94 + 24 = **118**；118 + 161 = **279**。✅

**關鍵日期**
- W1 起跑：**2026-07-27（今天）**
- Phase 1 收官週：**2026-08-30**
- Phase 2：CIP-14 組承諾「決策日 D 起 3 週內」；其餘無日期（外部/參數依賴）
- Phase 3：**11 月**，token launch 之後，CIP-21 → CIP-22 順序

---

## 1. 常駐紀律（每個 PR 都必須守）

來自團隊既有規則，違反會被門禁擋或被 shawhanken 駁：

- **PR base = `devnet`**（repo 有 devnet 分支就用；node/runner/cbss/cbfs/gateway/cowboy-protocol 皆有）。
- **commit message 不帶任何 AI 屬名**（no `Co-Authored-By: Claude…`）。
- **提交前 `cargo fmt --all`**，CI Format 必過。
- **加共享 struct 必填欄位**：push 前全倉 grep 構造點 + `cargo build --workspace --all-targets`，別只 `-p` 單 crate（會漏 validator/cli）。
- **marshal 門禁在乾淨 worktree、PR head 跑**；`running 0 tests` / `has no symbol` 先查 checkout。
- **PR 附面向客戶總結**，如實不拔高。
- **Linear / GitHub 評論一律英文**（聊天中文）。
- 單一工作目錄 `checkout -b`，別另開 worktree 平行目錄。
- 規格權威來源 = `cowboy/docs/`（cips/、whitepaper/），refs/ 僅鏡像。動工前回一手源核對 premise。

---

## 2. 單 issue 執行生命週期（作戰 SOP）

每個 issue 走同一條流水線，Definition of Done 一致：

```
1. start-issue-fix COW-XXXX
   └ 讀 Linear issue → 回 cowboy/docs/cips 核 premise → 選 repo → checkout -b → 寫 plan.md
2. 【前提核對關卡】issue 描述 vs 現行 CIP/devnet 代碼是否一致？
   └ 不一致 → 若屬「自修勘誤」四票之一，先修描述/代碼；否則標 errata 退回
3. TDD 實作（先寫失敗測試複現/定義驗收，再實作）
4. cargo fmt --all  +  cargo build --workspace --all-targets  +  對應 crate 測試
5. 【marshal 深審門禁】分級 + 不變量 gate + 對抗 review + 棘輪
   └ verdict = pass → 出 PR；escalate/block → 修到 pass
6. PR into devnet（附客戶總結）→ almanax 核對 → CI 全綠
```

**Definition of Done（逐 issue）**：對應 crate 測試綠 + `build --workspace --all-targets` 綠 + `cargo fmt` 乾淨 + marshal pass + PR 開到 devnet + CI 全綠 + Linear issue 連結 PR。

**叢集加速**：同 CIP、同 repo、低難度（T0/T4）的票打包給 `batch-issue-loop`（單分支、單 PR into devnet、循環跑 marshal + almanax 到綠）。高難度（T5）或觸及共識/激活的票**單獨**走 `start-issue-fix` + 單獨 marshal 深審，不混批。

---

## 3. CIP → repo → 工具 路由表

| CIP | 主題 | 落點 repo | 主要 skill | 驗收指令（範例） |
|-----|------|-----------|-----------|------------------|
| CIP-2 | 鏈下計算/爭議 | `node`（runner 系統 actor）, `runner`, `examples` | start-issue-fix | `cargo test -p cowboy-execution` |
| CIP-3 | 費用/PVM 成本/確定性 | `node/execution`, `pvm/`(獨立 workspace) | start-issue-fix | `cargo test -p cowboy-execution -- <name>`；PVM 看 branch push Pipeline |
| CIP-4/5 | fast-sync / 索引 / 狀態根 | `node/storage` | start-issue-fix | `cargo test -p cowboy-storage`；devnet start_all |
| CIP-6/25 | 跨鏈 bridge/streaming | `node`, `runner`, `examples` | start-issue-fix | e2e 跨鏈整合測試 |
| CIP-7 | streams / filter DSL | `node`, PVM SDK | start-issue-fix | `cowboy_sdk_tests` + pvm-runtime 真 PVM |
| CIP-9 | RAS/儲存 | `cbfs`, `node/ras` | start-issue-fix | `cargo test`（cbfs）+ node RPC；FUSE mount |
| CIP-10 | CADP | `cowpilot`, `node` | start-issue-fix | *(回避令已於 2026-07-27 解除)* |
| CIP-11 | runner wire/共識 | `node`, `runner`, `cowboy-protocol` | start-issue-fix / sweep | `cargo test -p cowboy-execution`；多驗證 e2e |
| CIP-19 | MCP endpoint | `gateway` | — (Phase 2 blocked) | 待 CIP-14 Gateway |
| CIP-20 | 代幣 | `node`, explorer/SDK | start-issue-fix | `cargo test -p cowboy-token` |
| CIP-21 | AMM/DEX | `node`, `examples` | batch/ start-issue-fix | pvm 測試單線程 fork/ECHILD |
| CIP-22 | 連續清算拍賣 | `examples` | batch (依賴 CIP-21) | clearing math edge tests |
| CIP-23 | TEE 認證 | `node`, `runner` | start-issue-fix | `types/src/tee.rs`；attestation e2e |
| CIP-24 | CBSS 秘密服務 | `cbss`, `node`, `runner` | start-issue-fix | `make test`（cbss）；real-validator 場景 |
| CIP-26 | actor lib/code table | `node` | — (Phase 2 blocked GC) | — |
| CIP-28 | bank/cards | `node`, `cowboy-protocol` | start-issue-fix | `cargo test -p cowboy-execution`；激活=10 flag-day |
| CIP-29 | runner 統一/infra | `runner`, infra | start-issue-fix | `cargo test`（runner） |
| CIP-30 | per-actor merkle/狀態根遷移 | `node/storage` | start-issue-fix | cross-validator conformance test |

> **PVM 陷阱（常駐）**：`pvm/` 是 workspace-excluded，CI PR-event 會 skip，真驗證看 branch push Pipeline；pvm 測試並行有 fork/ECHILD 假失敗 → 單線程跑。sim(Rust pvm_fsm) ≠ prod(Python _compiler.py)，審續體/actor 加載只信**執行層**測試。

---

## 4. Phase 1 — 62 個「現在能開工」的 5 週逐週計畫

> 難度標記沿用承諾書 T0（小）… T5（大）。依賴用「→」表示先後。

### W1 · 2026-07-27 → 08-02 · 13 個 · CIP 3·6·8·25 ·（T4×6 T5×7）

| Issue | Repo | 型別 | 難度 | 依賴/備註 |
|-------|------|------|:----:|-----------|
| COW-1119 Runner-side reorg detection daemon + `commitment_revoked` | runner | code | T5 | 跨鏈基石，先做 |
| COW-1120 `min_confirmations` per source chain（機率終局性） | node/runner | code | T4 | → 1119 |
| COW-1121 Dual-backend defense-in-depth（雙獨立錨） | node | code | T5 | → 1120 |
| COW-1124 Cross-chain example dapp（bridge/oracle/lending） | examples | code | T4 | → 1119/1120/1121 |
| COW-1125 E2E cross-chain integration + adversarial | tests | test | T5 | → 1124（最後做，收口全鏈路） |
| COW-1899 §1.6 Multi-destination cost reduction | node | code | T4 | |
| COW-1901 §2.5/2.6 Cross-chain streaming | node | code | T5 | |
| COW-1397 §2.2.4.2 built-in fn cost ∝ arg size（sum/max） | node/execution | code | T4 | PVM 成本，禁 float |
| COW-1398 §2.2.4.10 string encoding determinism cost | node/execution | code | T4 | |
| COW-1401 §2.2.4.4 Deterministic GC | node/execution | code | T5 | 確定性；共識敏感 |
| COW-988 `@on_stream` decorator + `stream_publish()`（CIP-7） | node SDK | code | T5 | |
| COW-993 E2E continuation tests on live PVM sandbox | CI/pvm | test | T4 | 真 PVM，看 push Pipeline |
| COW-1543 §4/§5 Runner session bootstrap（去 PoC HTTP push） | runner | code | T5 | |

**W1 打法**：跨鏈鏈（1119→1120→1121→1124→1125）單線串行、單獨 marshal（涉共識機率終局性）；PVM 成本三票（1397/1398/1401）可打包 batch，但 **1401 Deterministic GC 單獨深審**（確定性=共識，禁 float，用整數 `ilog2`）。**前提核對**：跨鏈屬 CIP-6/25，回 `cowboy/docs/cips` 核 §1.6/§2.5/§2.6 章節號未漂移。

### W2 · 2026-08-03 → 08-09 · 13 個 · CIP 24·28 ·（T3×1 T4×5 T5×7）

| Issue | Repo | 型別 | 難度 | 依賴/備註 |
|-------|------|------|:----:|-----------|
| COW-1905 §3.2 SetDefaultCard（caller==agent\|owner） | node + cowboy-protocol | code | T4 | 建在 BankActor 0x16 上 |
| COW-1906 §3.3 PauseBank / UnpauseBank（caller==operator） | node + cowboy-protocol | code | T4 | council-pause 語義小心 |
| COW-1907 §3.4 SetBankOperator（operator\|governance） | node + cowboy-protocol | code | T4 | |
| COW-1908 §3.4 SetBankFiatMintSigner（operator） | node + cowboy-protocol | code | T4 | |
| COW-1910\* §4.4 Edge-case（frozen/expired after reserve） | node | code+errata | T4 | **先修描述**：補齊 8 選 2 缺的邊界，對齊 devnet；no CIP change |
| COW-1915 §6.1 Inter-bank state isolation（bank_id-scoped） | node | code | T5 | 多 bank 隔離；接 M5 multi-bank |
| COW-1145 E2E card lifecycle integration tests | node | test | T3 | 收口 CIP-28 卡生命週期 |
| COW-1050 Restore lost §5.9 spawned DKG e2e（DOD-04） | cbss | test | T5 | |
| COW-1052 Real-validator stress test（DOD-08） | cbss | test | T5 | |
| COW-1053 Fake-cbssd forged σ_i over QUIC（DOD-09） | cbss | test | T5 | 對抗測試 |
| COW-1054 Real-validator scenario matrix（DOD-05/07） | cbss | test | T5 | → 1052 |
| COW-2667 CBSS 提交者不得比終局性更快預留 nonce gap | cbss/node | code | T5 | 共識敏感 |
| COW-2672 CBSS loopback QUIC stream capacity 可配 + load test | cbss | code | T4 | |

**W2 打法**：CIP-28 四個 instruction（1905/1906/1907/1908）同區、每 opcode 5 觸點（dispatch/handler/auth/gas/codec），**接續現有 in-flight**（BankActor 0x16、M5 multi-bank plan、cbp#60/#61 opcode band 200–216）——先跟這些分支對齊避免撞號。⚠️ **CIP-28 激活高度=10 是硬 flag-day**，凡動到激活後語義的必單獨深審（參 §7）。CBSS 五票（1050/1052/1053/1054）是**恢復失去的 e2e 套件 + 真 validator 壓測**，多為測試工程，可半批。**1910\* 動工前先改 issue 描述**（errata 自修）。

### W3 · 2026-08-10 → 08-16 · 12 個 · CIP 9·20·23 ·（T0×3 T4×4 T5×5）

| Issue | Repo | 型別 | 難度 | 依賴/備註 |
|-------|------|------|:----:|-----------|
| COW-886 GET_MANIFEST RPC client（公卷單趟） | cbfs/node | code | T4 | |
| COW-927 POST /ras/challenge endpoint + 鏈態 challenge 記錄 | node/ras | code | T5 | 共識（receipt/挑戰）敏感 |
| COW-937 CIP-9 integration tests（manifest 往返/access mode/cache） | runner/cbfs | test | T4 | → 886 |
| COW-1545 §12.3 reserve_storage_balance / get_storage_usage | node | code | T4 | |
| COW-2099 CIP-9 rewrite epic：triage mesa bring-up findings | cbfs/node | spec+code | T5 | epic，先拆子項 |
| COW-2183 CBFS PoR challenge/response + PoR-miss slashing | cbfs/node | code | T5 | slashing→共識，單獨深審 |
| COW-2205 Harden cowboy-ras-write-relayer（簽名+bootstrap 驗+S3 immut） | cbfs | code | T4 | follow-up COW-2188 |
| COW-2663 CBFS FUSE manifest refresh 算出 zero root（RW sync 後） | cbfs | bugfix | T5 | 對照 node zero-root restart 修法 |
| COW-1103 Attestation-first runner registration（→0x05::VerifyCae） | node/runner | code | T5 | 跨 call；系統 actor 位址核對 |
| COW-1849 §3.6.3 execute-in-TEE body | runner | code | T5 | |
| COW-1082 Token balance + transfer history UI | explorer | code | T0 | |
| COW-1083 Allowance pagination + bulk-query | node SDK | code | T0 | |

**W3 打法**：CIP-9 群（886/927/937/1545/2099/2183/2205/2663）是本週主體；**927 與 2183 涉挑戰/slashing→共識與 receipt_root，單獨深審**（事件/錯誤碼進 receipt_root=共識）。2663 是 bug，先寫複現測試（zero-root 對照既有 node 重啟恢復修法）。1082/1083 是 T0 前端/SDK，打包 batch 快速清。**前提核對**：1103 的 `0x05::VerifyCae` 與 §9.1 系統 actor 位址表核對（別重蹈 0x11/0x13 錯位）。

### W4 · 2026-08-17 → 08-23 · 12 個 · CIP 11·30 ·（T0×8 T5×4）

> ⚠️ **本週第一件事 = COW-2555**：先定位 1/6 機率 flaky 的 cowboy-execution 測試，否則同週 CIP-11 票的 marshal 門禁在乾淨 worktree 跑 PR 測試會出**假失敗**，全週被卡。

| Issue | Repo | 型別 | 難度 | 依賴/備註 |
|-------|------|------|:----:|-----------|
| **COW-2555 定位 1/6 flaky cowboy-execution test** | node | bugfix | — | **前置，最先做** |
| COW-1600 §6.5 CapabilityDelta（0x13）advisory 更新 | node/cowboy-protocol | code | T0 | |
| COW-1607 §9.3 MRU weight multiplier（Fisher-Yates iter 0 only） | node | code | T0 | |
| COW-1608 §9.4 New dispatcher state | node | code | T0 | → 1609 |
| COW-1609 §9.4 Result Verifier write path | node | code | T0 | ← 1608 |
| COW-1612 §10.4 JobProgress（0x22）streaming progress | node/runner | code | T0 | |
| COW-1616 §11.3 QUIC connection-loss + backoff reconnect | runner | code | T0 | |
| COW-1621 §14 Three-phase migration（Shadow/Hot/Sunset） | node | code | T0 | |
| COW-1276 Per-actor Merkle subtree commitment | node/storage | code | T5 | → 1277 → 1284 |
| COW-1277 state_set/delete recompute storage_root（cross-call write-set） | node/storage | code | T5 | ← 1276 |
| COW-1283 Migration policy：wipe(devnet) vs online(mainnet) + 實作 | node/storage | code | T5 | 治理決策點 |
| COW-1284 Cross-validator root-computation conformance test | node/storage | test | T5 | ← 1276/1277 |

**W4 打法**：八個 CIP-11 T0（1600/1607/1608/1609/1612/1616/1621）**打包 batch-issue-loop**（前置 2555 綠之後），注意 1608→1609 順序。CIP-30 狀態根四票（1276→1277→1284 串行，1283 並行）**全是 T5 且改狀態根=共識回歸**，逐一單獨 marshal 深審 + cross-validator conformance。

### W5 · 2026-08-24 → 08-30 · 12 個 · CIP 2·4·5·7·10·29 ·（T0×5 T2×1 T3×1 T4×5）

| Issue | Repo | 型別 | 難度 | 依賴/備註 |
|-------|------|------|:----:|-----------|
| COW-962 Dispute window：on-chain challenge/evidence/re-verify handler | node | code | T4 | 共識敏感 |
| COW-1308 CIP-2 v3 end-to-end 經濟 e2e example + case study | examples | code | T4 | |
| COW-1403 §8.1 Fast sync（下載 height H 的 QMDB state） | node/storage | code | T4 | → 2177 |
| COW-1406 §7.3 Auxiliary-index full/incremental rebuild | node/storage | code | T4 | |
| COW-2177 Benchmark fast-sync speedup vs genesis replay（>10x） | node | test/bench | T2 | ← 1403；COW-977 acceptance |
| COW-986 CIP-9 §12 example：schedule_timer_ex(fee_payer=…) | docs | docs | T0 | |
| COW-997 Filter DSL（depth≤4, ≤16 predicates）驗證+編譯+求值 | node/SDK | code | T4 | |
| COW-1003 Optional CIP-2 ingestion config（timer→task→transform→encrypt→publish） | node/SDK | code | T3 | |
| COW-2504\* CIP-10 TEE-signed BillingAttestation（CIP-23 CompositeAttestation） | node | code+errata | T4 | ⚠️ **動工前必先修 `0x11`→`0x13`**（Container Registry），否則驗證路由到錯 system actor |
| COW-2615 runner：統一兩個 runner-node mains | runner | refactor | T0 | |
| COW-2617 infra：cowboy-runner ExecStartPre 截斷 runner.env | infra | bugfix | T0 | |
| COW-1923 §6.3 P1-E emitter actor upgrade/redeployment 語義 | node | code | T4 | emitter provenance 相關 |

**W5 打法**：T0 五票（986/2615/2617 + 兩個）快速清或 batch。**2504 是四個自修勘誤之一且「動工前必修」**——第一步就把位址從 0x11 改成 0x13（WP §9.1 + 代碼），再實作 BillingAttestation。962 dispute window 涉再驗證/證據→共識，單獨深審。1403→2177 串行（benchmark 需 fast-sync 先成）。

---

## 5. Phase 2 — 13 個 blocked，依「等什麼」分組

### 組 1｜等我方 CIP-14 Gateway（7 個 · CIP-19）
COW-1764 / 1774 / 1777 / 1778 / 1780 / 1781 / 1788 —— 全部 gateway repo 的 MCP endpoint 工作。

- **前置（也是我方的）**：CIP-14 Gateway 尚未實作，devnet 只有位址常數。需先做 COW-1670（GATEWAY_REGISTRY 系統 actor）、COW-1671（gateway lifecycle）、COW-1672（IngressDispatch opcode 65）、COW-1673（system-mediated http.request）。
- **但**這 16 個 CIP-14 issue 本身在等 Cowboy team 的 Errata 裁定。
- **解卡觸發器**：Errata 決策日 **D** → 我方實作 CIP-14 Gateway 四件 → **D 起 3 週內**交付這 7 個。
- **該催誰**：Cowboy team（Errata sheet 的 CIP-14 行）。**行動**：本週就把 CIP-14 待裁項整理成一封 decision-request，主動推 D 早日落定（我方有權起草治理/跨團隊決策備忘）。

### 組 2｜等 CIP-10 §13 參數（1 個 · CIP-10）
COW-1575 §12.2 image-pull egress fee（`pull_cost = size × EGRESS_FEE_PER_BYTE`）。

- issue 本身與 §12.2 一致、無需勘誤；缺的是 `EGRESS_FEE_PER_BYTE` 的**值**，整個 CIP-10 §13 參數集只命名未賦值（Errata 行 COW-1578）。
- **解卡觸發器**：COW-1578 給出參數值。**該催誰**：Cowboy team。**行動**：把 §13 參數缺值一併併入組 1 的 decision-request。
- *(CIP-10 回避令已解除，實作端我方可做，僅卡在參數值。)*

### 組 3｜等上游/第三方/硬體（5 個）
| Issue | CIP | 卡在 | 最早可開工觸發器 |
|-------|-----|------|------------------|
| COW-1051 TEE vendor-quote chain-of-trust | 24 | Intel DCAP / AMD VLEK 真憑證鏈 + 真 TEE 硬體 | 取得 vendor 憑證服務通道 |
| COW-1111\* NVIDIA NCC GPU attestation（NRAS） | 23 | NVIDIA NRAS 遠端認證服務 + 憑證鏈；`types/src/tee.rs` 現僅型別 | 取得 NVIDIA 通道（errata：RunnerResult 命名我方自修，不卡） |
| COW-1365 §3.9 future-GC reachability guard | 26 | code table 從不收集、GC 機制不存在（spec 自承「currently impossible」） | GC 機制啟動後 |
| COW-1582 §14.6 GPU side-channel（MIG isolation） | 10 | 真 GPU 硬體；CIP-10 GPU 計費/排程整體未定義（Errata COW-2506） | GPU 硬體 + COW-2506 定義 |
| COW-2283 canyon-reset Ansible | 24 | `aws-infrastructure` repo，我方 PAT 無存取（已核實 no-access） | 取得 repo 存取；**描述稱已從零跑綠兩次，可能其實已完成只是沒關單** |

- **行動**：COW-2283 先跟 Cowboy team 確認是否已完成可關單（省一件）。1051/1111/1582 開一張「外部依賴採購/通道」追蹤（vendor 憑證、NVIDIA NRAS、GPU 硬體），非工程能解。1365 掛在 GC epic 之後。

### Phase 2 的 4 個自修勘誤（無需 Cowboy team 輸入）
| Issue | 處理（我方自決，no CIP change） |
|-------|--------------------------------|
| COW-1111\* (CIP-23) | issue 造了 CIP-23 不存在的型別名 `RunnerResult` → 對齊 CIP-23 既有命名 |
| COW-1200\* (CIP-22) | 引用「CIP-22 line 873 見 examples/cca/」失效 → 更新為 §Example: Token Launch / §Reference Implementation |
| COW-1910\* (CIP-28) | 描述仍當 CIP-28 是 spec-only、§4.4 只列 6/8 邊界 → 對齊 devnet + 補兩個缺的 |
| COW-2504\* (CIP-10) | `0x11 → 0x13`（Container Registry；0x11 是 validator-set 快照）→ **動工前必修** |

> 這 4 個已分別在 Phase 1/2/3 出現（W2/W3/W5 及 blocked 表），不重複計數；此處只集中列處理法。

---

## 6. Phase 3 — 19 個 November batch（CIP-21 → CIP-22）

**閘門**：CIP-21（DEX）+ CIP-22（拍賣）在 **$COWBOY token launch 之後**才 go-live，Cowboy team 已確認開發也排在 launch 後。19 個仍在我方 94 承諾內，只是時間移到 11 月。CIP-22（9 個）依賴 CIP-21 先完成，同批內 CIP-21 → CIP-22 順序。

- **CIP-21（10 · T5 · node+examples）**：COW-1086（V3 集中流動性池）/1088（swap routers）/1091（V3 position manager NFT）/1096（多跳+factory+hooks+TWAP 測試）/1799（IV2Pool extras）/1800（canonical token sorting）/1801（on-chain limit orders via timers）/1802（MEV+KYC hooks）/1803（Sync event）/1805（reference platform impl `amm.rs`）。
- **CIP-22（9 · T0 · examples）**：COW-1193（per-block clearing SortedMap）/1200\*（reference auction actor，errata 自修引用）/1201（clearing math edge tests）/1809（Bid 結構）/1810（AuctionState）/1814（claim_batch）/1815（query methods）/1816（`_remaining_demand`）/1822（ICCAFactory）。

**可提前開跑的預備工（不等 launch）**：
1. 讀 CIP-21/22 規格（`cowboy/docs/cips`），確認章節號未漂移（1200\* 已知漂移）。
2. 建 `examples/<NN>-cca/` 鷹架 + 測試骨架（CIP-22 全 T0，骨架先行）。
3. CIP-21 建在既有 AMM 基礎上（7 個原語已交付 node PR#1116→devnet；SortedMap COW-1199 PR#1123 已交付）——盤點缺口，避免重造。
4. pvm 測試環境：並行 fork/ECHILD 假失敗 → 單線程；byte-exact Uniswap 對齊。

> 另有 31 個 CIP-21/22 issue 需 Cowboy team 先做 errata 裁定，不在本檔（見 Errata sheet 的 November 標記）。

---

## 7. 風險與衝突清單

| # | 風險 | 影響 | 緩解 |
|---|------|------|------|
| R1 | ~~CIP-10 回避令 vs 承諾~~ | ~~3 票~~ | **已解除**（2026-07-27 用戶解禁），COW-2504/1575/1582 正常排入 |
| R2 | **W4 flaky test COW-2555** | 同週 CIP-11 票 marshal 假失敗，全週卡 | 列為 W4 第一件事，前置解阻塞 |
| R3 | **CIP-28 激活高度=10 硬 flag-day** | W2 動到激活後語義的票需 fleet 協調，不能 self-merge | 凡碰激活後語義單獨深審 + 標 flag-day，跟現有 PR#1133/1134 對齊 |
| R4 | **狀態根/共識回歸票**（W4 CIP-30、W3 927/2183、W5 962、W1 1401） | 改狀態根/receipt/slashing = 共識回歸，錯了分叉 | 全部單獨 marshal 深審，不進 batch；cross-validator conformance |
| R5 | **Phase 2 組 1/2 無日期** | 7+1 票承諾「D 起 3 週」但 D 未定 | 本週主動起草 CIP-14 + §13 參數 decision-request 推 Cowboy team 早裁 |
| R6 | **容量現實性**：62 票 / 5 週 ≈ 12–13/週，含大量 T5 | 排程過緊 | T0 打包 batch-issue-loop，T5 單獨；每週留 buffer；狀態滾動誠實回報，落後即揭示不拔高 |
| R7 | **系統 actor 位址錯位**（0x11/0x13 類） | 驗證路由到錯 actor | 動工前一律回 WP §9.1 位址表核對（見既有位址表記憶） |
| R8 | PVM CI 盲區（pvm/ workspace-excluded，PR-event skip） | 假綠 | 真驗證看 branch push Pipeline，不信 PR check |

---

## 8. 每週節奏 checklist

**週一（kickoff）**
- [ ] 選出本週 12–13 票，`git fetch` 各 repo（本地追蹤引用會陳舊）
- [ ] 逐票回 `cowboy/docs/cips` 核 premise + 章節號 + 系統 actor 位址
- [ ] 標出本週的「共識/激活敏感」票（走單獨深審）與「T0 可打包」票
- [ ] 各票 `start-issue-fix` 開分支（單一工作目錄 checkout -b）

**週中**
- [ ] 每票走 §2 SOP；T0 叢集丟 `batch-issue-loop`
- [ ] 每個 PR 前：`cargo fmt --all` + `build --workspace --all-targets` + marshal pass
- [ ] 共享 struct 加欄位 → 全倉 grep 構造點

**週五（收口）**
- [ ] `marshal-pr-sweep` 掃本週所有待 merge PR（跨 7 repo）
- [ ] 狀態滾動：本週 done / 進行中 / 落後，如實回報（PR 附客戶總結，不拔高）
- [ ] 更新 Linear issue 連 PR

---

## 附錄：Cowboy team 自持 24 票（只記錄、我方無日期）
COW-1036/1037/1038/1043/1047（Gateway）· 1304（pvm-runtime linecache）· 1363（CBFS erasure fan-out）· 2128（mempool gap-aware）· 2154（QMDB speculative root mismatch）· 2206（runner heartbeat stagger）· 2219/2220/2222/2223/2510/2527/2630（CIP-11 一系列）· 2256/2264/2784（CBSS/crypto）· 2494/2495（Gateway cache）· 2539/2540（ops m=1 reroute）。
—— 若這些成為我方票的隱形前置（如 CIP-11 W4 票依賴 2223 dispatcher 修法），在對應週的前提核對中標出並跟 Cowboy team 對齊。

---

_本手冊隨執行滾動更新；對外承諾以原 HTML 為準。_
